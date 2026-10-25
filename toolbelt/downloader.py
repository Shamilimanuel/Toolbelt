"""The video downloader: looks a link up, then downloads video + sound, video only, or just the sound, up to 4K.

It runs the official yt-dlp.exe (with Deno for YouTube's challenges and ffmpeg for joining and MP3s), all from
%LOCALAPPDATA%\\Toolbelt\\engines. Every outside program runs with no console window. The pure helpers at the top
(quality list, file names, progress lines) have no side effects, so the tests can check them without the internet.
"""
import base64
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

import engines
from settings import DATA

NO_WINDOW = 0x08000000
CACHE = DATA / "cache"
AUDIO_FORMATS = {"mp3": "MP3", "m4a": "M4A", "opus": "Opus"}
VIDEO_EXTS = ("mp4", "mkv", "webm")
LINK = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?[^\s]*v=|shorts/|live/)|youtu\.be/)[\w-]{6,}[^\s]*", re.I)


class DownloadError(Exception):
    pass


# ---------- pure helpers ----------

def find_link(text):
    """The first YouTube video link in some text, or None."""
    if not isinstance(text, str) or len(text) > 4000:
        return None
    m = LINK.search(text)
    return m.group(0).rstrip(").,]>\"'") if m else None


def quality_options(info):
    """From yt-dlp's info: the heights you can pick (best first) with an estimated size, and the sound sizes."""
    duration = info.get("duration") or 0
    formats = info.get("formats") or []

    def size(f):
        s = f.get("filesize") or f.get("filesize_approx")
        if not s and duration and f.get("tbr"):
            s = f["tbr"] * 1000 / 8 * duration
        return s or 0

    audios = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    best_audio = max((size(f) for f in audios), default=0)
    heights = {}
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") in (None, "none"):
            continue
        heights[h] = max(heights.get(h, 0), size(f))
    picks = []
    for h in sorted(heights, reverse=True):
        if h > 4320 or any(p["height"] == h for p in picks):
            continue
        label = {4320: "8K", 2160: "4K", 1440: "1440p"}.get(h, "%dp" % h)
        picks.append({"height": h, "label": label, "size": int(heights[h] + best_audio), "video_only": int(heights[h])})
    picks = [p for p in picks if p["height"] >= 360] or picks
    # sound only, estimated from the length: MP3 at about 245 kbit/s (best VBR), M4A/Opus from the real stream
    sound = {"mp3": int(duration * 245000 / 8), "m4a": int(best_audio or duration * 130000 / 8), "opus": int(best_audio * 0.95 or duration * 120000 / 8)}
    return {"heights": picks, "sound": sound}


def summary(info):
    q = quality_options(info)
    return {"id": info.get("id"), "title": info.get("title") or "Untitled", "channel": info.get("channel") or info.get("uploader") or "",
            "duration": info.get("duration") or 0, "url": info.get("webpage_url") or info.get("original_url"),
            "heights": q["heights"], "sound": q["sound"], "is_live": bool(info.get("is_live"))}


def quality_tag(mode, height=None, audio="mp3"):
    if mode == "audio":
        return AUDIO_FORMATS.get(audio, audio.upper())
    label = {4320: "8K", 2160: "2160p"}.get(height, "%sp" % height) if height else "best"
    return label + (" no sound" if mode == "video" else "")


def safe_text(text):
    """Text that may go into a file name: Windows' forbidden characters swapped, length capped."""
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(text)).strip(" .")
    return text[:150] or "download"


def output_template(folder, pattern, title, quality, n=1):
    """yt-dlp's -o value: the person's name pattern with the title and quality filled in, {ext} left to yt-dlp."""
    name = pattern.replace("{title}", safe_text(title)).replace("{quality}", safe_text(quality))
    name = name.replace("%", "%%").replace("{ext}", "\x00")
    if n > 1:
        stem, dot, rest = name.partition(".\x00")
        name = stem + " (%d)" % n + dot + rest if dot else name + " (%d)" % n
    name = name.replace("\x00", "%(ext)s")
    return str(Path(folder) / name)


def free_template(folder, pattern, title, quality, never_overwrite=True, exts=VIDEO_EXTS + tuple(AUDIO_FORMATS)):
    """Adds (2), (3)… when a file with that name already exists and overwriting is off."""
    n = 1
    while True:
        tpl = output_template(folder, pattern, title, quality, n)
        taken = any(Path(tpl.replace("%(ext)s", e).replace("%%", "%")).exists() for e in exts)
        if not taken or not never_overwrite or n > 99:
            return tpl
        n += 1


SUB_LANGS = "en.*,ja.*,nl.*"                                 # English, Japanese and Dutch (his languages), any variant


def build_args(mode, height, audio, template, deno, ffmpeg_bin, info_file, subs="off"):
    """yt-dlp's command line for one download. mode: both (video + sound), video (no sound) or audio."""
    args = ["--load-info-json", str(info_file), "--no-playlist", "--js-runtimes", "deno:" + str(deno),
            "--ffmpeg-location", str(ffmpeg_bin), "--windows-filenames", "--no-mtime", "--encoding", "utf-8",
            "--newline", "--progress", "--no-colors", "-o", template,
            "--progress-template", "download:TBPROG %(progress.status)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
            "--progress-template", "postprocess:TBPP %(progress.postprocessor)s|%(progress.status)s",
            "--print", "after_move:TBFILE %(filepath)s"]
    h = int(height) if height else 2160
    if mode == "audio":
        args += ["-f", "ba/b", "-x", "--audio-format", audio, "--audio-quality", "0",
                 "--embed-metadata", "--embed-thumbnail", "--convert-thumbnails", "jpg"]
    elif mode == "video":
        args += ["-f", "bv*[height<=%d]/bv*" % h, "--remux-video", "mp4/mkv"]
    else:
        args += ["-f", "bv*[height<=%d]+ba/b[height<=%d]/bv*+ba/b" % (h, h), "--merge-output-format", "mp4/mkv", "--embed-metadata"]
    if mode != "audio" and subs in ("made", "auto"):            # subtitles inside the video, switchable in any player (15 Oct)
        args += ["--write-subs", "--sub-langs", SUB_LANGS, "--embed-subs"] + (["--write-auto-subs"] if subs == "auto" else [])
    return args


def parse_progress(line):
    """One TBPROG line -> dict (numbers may be None while yt-dlp doesn't know them yet)."""
    if not line.startswith("TBPROG "):
        return None
    parts = line[7:].strip().split("|")
    if len(parts) != 6:
        return None

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    status, got, total, estimate, speed, eta = parts
    return {"status": status, "got": num(got) or 0, "total": num(total) or num(estimate), "speed": num(speed), "eta": num(eta)}


# ---------- talking to yt-dlp ----------

def tools():
    yt, deno, ff = engines.path_of("yt-dlp"), engines.path_of("deno"), engines.path_of("ffmpeg")
    missing = [n for n, p in (("yt-dlp", yt), ("Deno", deno), ("ffmpeg", ff)) if not p]
    if missing:
        raise DownloadError("Install " + ", ".join(missing) + " first (Engines, or the button on this page).")
    return yt, deno, ff.parent


def run_env():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def look_up(url):
    """Asks yt-dlp about a link. Keeps the full answer in the cache (so the download needn't ask again)."""
    if not find_link(url):
        raise DownloadError("That doesn't look like a YouTube video link.")
    yt, deno, ff_bin = tools()
    done = subprocess.run([str(yt), "-J", "--no-playlist", "--no-warnings", "--js-runtimes", "deno:" + str(deno),
                           "--ffmpeg-location", str(ff_bin), url],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW, env=run_env())
    if done.returncode != 0 or not done.stdout.strip():
        lines = [line for line in done.stderr.splitlines() if "ERROR" in line] or done.stderr.strip().splitlines()[-1:]
        raise DownloadError(clean_error(lines[0] if lines else "yt-dlp couldn't read that link."))
    info = json.loads(done.stdout)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / ("%s.info.json" % safe_text(info.get("id") or "video"))).write_text(done.stdout, encoding="utf-8")
    result = summary(info)
    result["thumb"] = thumbnail(info)
    return result


def clean_error(text):
    text = re.sub(r"^ERROR:\s*(\[\w+\]\s*[\w-]+:\s*)?", "", text.strip())
    if "Sign in to confirm" in text or "age" in text.lower() and "restricted" in text.lower():
        return "YouTube wants a signed-in account for this video (age-restricted or members only)."
    if "Private video" in text:
        return "This video is private."
    if "Video unavailable" in text:
        return "This video isn't available (removed, or blocked in your country)."
    return text[:300]


def thumbnail(info):
    """The video's picture as a data link (Python fetches it, so the page itself never goes online)."""
    thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url") and (t.get("width") or 0) <= 1280]
    thumbs.sort(key=lambda t: (t.get("width") or 0) * (1 if ".jpg" in t["url"] or "jpg" in t["url"] else 0.5))
    url = thumbs[-1]["url"] if thumbs else info.get("thumbnail")
    if not url:
        return ""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Toolbelt"}), timeout=10) as r:
            data = r.read(2_000_000)
            kind = r.headers.get_content_type() or "image/jpeg"
        return "data:%s;base64,%s" % (kind, base64.b64encode(data).decode("ascii"))
    except Exception:
        return ""


def kill_tree(proc):
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception:
        proc.kill()


def download(job, video_id, mode, height, audio, folder, pattern, never_overwrite, subs="off"):
    """Runs one download as a background job. Returns the finished file's path."""
    yt, deno, ff_bin = tools()
    info_file = CACHE / ("%s.info.json" % safe_text(video_id))
    if not info_file.exists():
        raise DownloadError("Look the link up again first (the saved details are gone).")
    info = json.loads(info_file.read_text(encoding="utf-8"))
    Path(folder).mkdir(parents=True, exist_ok=True)
    quality = quality_tag(mode, height, audio)
    template = free_template(folder, pattern, info.get("title") or video_id, quality, never_overwrite)
    args = [str(yt)] + build_args(mode, height, audio, template, deno, ff_bin, info_file, subs)
    before = existing_with_stem(template)
    parts = 2 if mode == "both" else 1
    job.extra.update({"video_id": video_id, "mode": mode, "quality": quality, "channel": info.get("channel") or info.get("uploader") or "",
                      "duration": info.get("duration") or 0, "speed": 0, "eta": None, "got": 0, "total": None, "stage": "Starting"})
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            creationflags=NO_WINDOW, env=run_env())
    finished_parts, final, errors, started = 0, None, [], False
    try:
        for line in proc.stdout:
            if job.cancelled:
                kill_tree(proc)
                break
            line = line.rstrip("\r\n")
            p = parse_progress(line)
            if p:
                started = True
                if p["status"] == "finished":
                    finished_parts += 1
                    continue
                frac = (p["got"] / p["total"]) if p["total"] else 0
                overall = 90 * (min(finished_parts, parts - 1) + min(frac, 1)) / parts
                job.extra.update({"speed": p["speed"] or 0, "eta": p["eta"], "got": p["got"], "total": p["total"],
                                  "stage": ("Picture" if finished_parts == 0 else "Sound") if parts == 2 else ("Sound" if mode == "audio" else "Picture")})
                job.report(overall, "%s · %s left" % (fmt_speed(p["speed"]), fmt_eta(p["eta"])))
            elif line.startswith("TBPP ") and started:             # ignore preparation steps before the download
                stage = {"Merger": "Joining picture and sound", "ExtractAudio": "Making the %s" % quality, "EmbedThumbnail": "Adding the cover",
                         "FFmpegMetadata": "Writing title and artist", "Metadata": "Writing title and artist", "VideoRemuxer": "Finishing the file"}.get(line[5:].split("|")[0], "Finishing")
                job.extra.update({"stage": stage, "speed": 0})
                job.report(max(job.progress, 92), stage)
            elif line.startswith("TBFILE "):
                final = line[7:].strip()
            elif line.startswith("ERROR"):
                errors.append(clean_error(line))
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            kill_tree(proc)
    if job.cancelled:
        tidy(template, before)
        job.check()
    final = find_final(final, template, before)
    if proc.returncode != 0 or not final:
        raise DownloadError(errors[0] if errors else "yt-dlp stopped without making a file (code %s)." % proc.returncode)
    job.extra.update({"stage": "Done", "speed": 0, "path": final, "size": Path(final).stat().st_size if Path(final).exists() else 0})
    return final


def find_final(reported, template, before):
    """The finished file: the path yt-dlp reported if it exists, else the newest new file with this download's name."""
    if reported and Path(reported).is_file():
        return reported
    stem = Path(template.replace("%%", "%")).name.split("%(ext)s")[0]
    folder = Path(template).parent
    if not stem or not folder.exists():
        return None
    new = [f for f in folder.iterdir() if f.is_file() and f.name.startswith(stem) and f.name not in before
           and f.suffix.lower().lstrip(".") in VIDEO_EXTS + tuple(AUDIO_FORMATS)]
    return str(max(new, key=lambda f: f.stat().st_mtime)) if new else None


def existing_with_stem(template):
    """Names of files that already start with this download's name, before it begins."""
    stem = Path(template.replace("%%", "%")).name.split("%(ext)s")[0]
    folder = Path(template).parent
    if not stem or not folder.exists():
        return set()
    return {f.name for f in folder.iterdir() if f.name.startswith(stem)}


def tidy(template, before):
    """After Cancel: removes only the files this download created (never one that was there before it started)."""
    stem = Path(template.replace("%%", "%")).name.split("%(ext)s")[0]
    folder = Path(template).parent
    if not stem or not folder.exists():
        return
    for f in folder.iterdir():
        if f.name.startswith(stem) and f.name not in before and f.is_file():
            f.unlink(missing_ok=True)


def fmt_speed(bps):
    if not bps:
        return "…"
    return "%.1f MB/s" % (bps / 1048576) if bps >= 1048576 else "%.0f KB/s" % (bps / 1024)


def fmt_eta(seconds):
    if seconds is None:
        return "…"
    s = int(seconds)
    return "%d:%02d" % (s // 60, s % 60) if s < 3600 else "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60)
