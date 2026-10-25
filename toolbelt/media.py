r"""Pictures & video (step 6): convert, compress, resize, clips, game clips. ffmpeg does the video work, Pillow the pictures.

Every long job gets a `job` (jobs.Job) to report progress to and to be cancelled through. ffmpeg is started with
`-progress pipe:1`, which prints "out_time_us=…" lines while it works; that becomes the progress bar.
Files land in his save folder (Settings > Files), never overwriting an existing file.
"""
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image, ImageOps

import engines
import shellicon
from cutout import free_path
from jobs import Cancelled
from settings import DATA

try:                                                        # iPhone photos (.heic), agreed 15 Oct: pillow-heif teaches Pillow to open them
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

NO_WINDOW = 0x08000000
CACHE = DATA / "cache" / "media"
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".wmv", ".flv", ".mpg", ".mpeg"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".opus", ".ogg", ".flac", ".aac", ".wma"}
PICTURE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".avif", ".ico", ".heic", ".heif"}

# the "Turn it into" choices: id -> (ending, what it is, ffmpeg bits)
VIDEO_OUT = {
    "mp4": ("MP4", "plays everywhere"), "webm": ("WebM", "small, for the web and Discord"), "mkv": ("MKV", "keeps everything, no re-encoding"),
    "mov": ("MOV", "for Apple editors"), "mp3": ("MP3", "just the sound"), "m4a": ("M4A", "sound, smaller than MP3"),
    "wav": ("WAV", "sound, uncompressed"), "opus": ("Opus", "sound, smallest"), "flac": ("FLAC", "sound, lossless"),
    "silent": ("Video without sound", "same file, sound taken out"),
}
PICTURE_OUT = {"png": "PNG", "jpg": "JPG", "webp": "WebP", "avif": "AVIF", "bmp": "BMP", "gif": "GIF", "ico": "Icon (.ico)", "tiff": "TIFF"}
# resize presets: id -> (label, width, height, mode)  mode: fit (keep shape), square (pad to square), percent, ico
RESIZE = {
    "half": ("50%", 0, 0, "percent"), "1920": ("1920 wide", 1920, 0, "fit"), "1280": ("1280 wide", 1280, 0, "fit"),
    "emoji": ("Discord emoji · 128", 128, 128, "square"), "sticker": ("Discord sticker · 320", 320, 320, "square"),
    "profile": ("Profile picture · 512", 512, 512, "square"), "mcskin": ("Minecraft skin · 64", 64, 64, "exact"),
    "mcicon": ("Minecraft server icon · 64", 64, 64, "square"), "ico": ("Windows icon (.ico)", 256, 256, "ico"),
}
# compress-video targets, MB
TARGETS = {"10": 10, "25": 25, "50": 50, "100": 100, "500": 500}
# the smallest bitrate (kbps) at which each height still looks fine (h264)
LADDER = [(2160, 12000), (1440, 7000), (1080, 3500), (720, 1600), (480, 700), (360, 350), (240, 150)]


class MediaError(Exception):
    pass


def ffmpeg():
    path = engines.path_of("ffmpeg")
    if not path:
        raise MediaError("Install ffmpeg first (Engines).")
    return path


def ffprobe():
    return ffmpeg().with_name("ffprobe.exe")


def kind_of(path):
    ext = Path(path).suffix.lower()
    if ext == ".gif":
        return "gif"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in PICTURE_EXT:
        return "picture"
    return "other"


# ---------- what is this file? ----------
def probe(path):
    """Facts about a file: kind, size, and for video/sound the length, picture size, frame rate and codecs."""
    path = Path(path)
    info = {"path": str(path), "name": path.name, "kind": kind_of(path), "size": path.stat().st_size if path.exists() else 0,
            "duration": 0.0, "width": 0, "height": 0, "fps": 0.0, "vcodec": "", "acodec": "", "frames": 0}
    if info["kind"] == "picture":
        try:
            with Image.open(path) as img:
                info["width"], info["height"] = img.size
                info["frames"] = getattr(img, "n_frames", 1)
        except Exception:
            pass
        return info
    if info["kind"] == "other" or not engines.path_of("ffmpeg"):
        return info
    try:
        done = subprocess.run([str(ffprobe()), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=NO_WINDOW)
        data = json.loads(done.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return info
    try:
        info["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
    except ValueError:
        pass
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["vcodec"]:
            info["vcodec"] = s.get("codec_name", "")
            info["width"], info["height"] = int(s.get("width", 0) or 0), int(s.get("height", 0) or 0)
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            try:
                num, den = rate.split("/")
                info["fps"] = round(float(num) / float(den), 3) if float(den) else 0.0
            except (ValueError, ZeroDivisionError):
                pass
            try:
                info["frames"] = int(s.get("nb_frames", 0) or 0)
            except ValueError:
                pass
            if not info["duration"]:
                try:
                    info["duration"] = float(s.get("duration", 0) or 0)
                except ValueError:
                    pass
        elif s.get("codec_type") == "audio" and not info["acodec"]:
            info["acodec"] = s.get("codec_name", "")
    return info


def thumbnail(path, at=1.0, width=480):
    """A small JPEG of one frame as a data link (cached under AppData), or '' for sound and unreadable files."""
    path = Path(path)
    try:
        stamp = "%s|%d|%d|%d" % (path, path.stat().st_mtime_ns, path.stat().st_size, width)
    except OSError:
        return ""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / (hashlib.sha1(stamp.encode("utf-8")).hexdigest() + ".jpg")
    if not cached.exists():
        kind = kind_of(path)
        try:
            if kind == "picture":
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img).convert("RGB")
                    img.thumbnail((width, width))
                    img.save(cached, "JPEG", quality=82)
            elif kind in ("video", "gif"):
                when = min(at, max(0.0, probe(path)["duration"] - 0.1)) if kind == "video" else 0
                subprocess.run([str(ffmpeg()), "-y", "-v", "error", "-ss", str(when), "-i", str(path), "-frames:v", "1", "-vf", "scale=%d:-2" % width, "-q:v", "4", str(cached)],
                               capture_output=True, timeout=60, creationflags=NO_WINDOW)
            else:
                return ""
        except Exception:
            return ""
    try:
        return "data:image/jpeg;base64," + base64.b64encode(cached.read_bytes()).decode("ascii")
    except OSError:
        return ""


# ---------- running ffmpeg with a progress bar ----------
def run(job, args, duration, label, start=0.0, span=100.0, timeout=4 * 3600, cwd=None):
    """Runs ffmpeg; progress goes to the job (start..start+span); Cancel kills it. Raises MediaError on failure."""
    cmd = [str(ffmpeg()), "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1"] + [str(a) for a in args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW, cwd=cwd)
    errors = []
    drain = threading.Thread(target=lambda: errors.append(proc.stderr.read()), daemon=True)
    drain.start()
    deadline = time.time() + timeout
    try:
        job.report(start, label)
        for line in proc.stdout:
            job.check()
            if time.time() > deadline:
                raise MediaError("That took too long and was stopped.")
            if line.startswith("out_time_us=") and duration > 0:
                try:
                    done = int(line.split("=", 1)[1]) / 1e6
                except ValueError:
                    continue
                job.report(start + span * min(1.0, done / duration), label)
    except (Cancelled, MediaError):
        proc.kill()
        proc.wait()
        raise
    proc.wait()
    drain.join(5)
    if proc.returncode != 0:
        text = (errors[0] if errors else "").strip().splitlines()
        raise MediaError(text[-1][:200] if text else "ffmpeg stopped with an error.")
    job.report(start + span, label)


def out_path(folder, stem, ext):
    Path(folder).mkdir(parents=True, exist_ok=True)
    return free_path(Path(folder), stem, ext)


def _copy_ok(info, container):
    """Can the picture and sound go into this container untouched?"""
    v, a = info["vcodec"], info["acodec"]
    if container == "mkv":
        return True
    if container in ("mp4", "mov"):
        return v in ("h264", "hevc", "av1", "mpeg4", "") and a in ("aac", "mp3", "alac", "ac3", "")
    if container == "webm":
        return v in ("vp8", "vp9", "av1", "") and a in ("opus", "vorbis", "")
    return False


# ---------- convert ----------
def convert(job, src, fmt, folder):
    """Turns a video or sound file into `fmt` (see VIDEO_OUT). Copies the streams when the new container takes them as they are."""
    src = Path(src)
    info = probe(src)
    if fmt not in VIDEO_OUT:
        raise MediaError("Unknown format.")
    if fmt == "silent":
        dest = out_path(folder, src.stem + " - no sound", src.suffix if src.suffix.lower() in VIDEO_EXT else ".mp4")
        run(job, ["-i", src, "-an", "-c:v", "copy", dest], info["duration"], "Taking the sound out")
        return str(dest)
    if fmt in ("mp3", "m4a", "wav", "opus", "flac"):
        if not info["acodec"]:
            raise MediaError("That file has no sound in it.")
        codec = {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"], "m4a": ["-c:a", "aac", "-b:a", "192k"], "wav": ["-c:a", "pcm_s16le"],
                 "opus": ["-c:a", "libopus", "-b:a", "128k"], "flac": ["-c:a", "flac"]}[fmt]
        dest = out_path(folder, src.stem, "." + fmt)
        run(job, ["-i", src, "-vn"] + codec + [dest], info["duration"], "Making the " + VIDEO_OUT[fmt][0])
        return str(dest)
    dest = out_path(folder, src.stem, "." + fmt)
    if _copy_ok(info, fmt) and src.suffix.lower() != "." + fmt:
        args = ["-i", src, "-c", "copy"] + (["-movflags", "+faststart"] if fmt in ("mp4", "mov") else []) + [dest]
        label = "Repacking as " + VIDEO_OUT[fmt][0] + " (no quality lost)"
    elif fmt == "webm":
        args = ["-i", src, "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k", dest]
        label = "Encoding WebM"
    else:
        args = ["-i", src, "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dest]
        label = "Encoding " + VIDEO_OUT[fmt][0]
    run(job, args, info["duration"], label)
    return str(dest)


# ---------- compress video to a size ----------
def plan_compress(info, target_mb, start=0.0, end=0.0):
    """How to fit the video under target_mb: the bitrates and the height. Pure maths, so the page can show it before starting."""
    length = max(0.1, (end - start) if end > start else info["duration"])
    total_kbps = target_mb * 1024 * 1024 * 8 / 1000 / length * 0.95      # 5% headroom for the container
    audio = 128 if total_kbps > 2500 else 96 if total_kbps > 900 else 64 if info["acodec"] else 0
    if not info["acodec"]:
        audio = 0
    video = max(80, total_kbps - audio)
    height = info["height"] or 1080
    for h, need in LADDER:
        if h <= height and video >= need:
            height = h
            break
    else:
        height = 240
    scale = height < (info["height"] or height)
    return {"video_kbps": int(video), "audio_kbps": audio, "height": height, "scale": scale, "length": round(length, 1),
            "mb": round(target_mb, 1), "fits": video >= 150, "percent": int(100 - 100 * target_mb * 1024 * 1024 / max(1, info["size"])) if info["size"] else 0}


def compress(job, src, target_mb, folder, start=0.0, end=0.0):
    """Two passes of h264, aimed at the size: the first pass measures, the second spends the bits well."""
    src = Path(src)
    info = probe(src)
    if info["kind"] != "video":
        raise MediaError("That isn't a video.")
    plan = plan_compress(info, float(target_mb), start, end)
    if not plan["fits"]:
        raise MediaError("Too long to fit in %s MB and still be watchable. Trim it first, or pick a bigger size." % target_mb)
    dest = out_path(folder, "%s - %s MB" % (src.stem, int(target_mb)), ".mp4")
    trim = (["-ss", str(start)] if start > 0 else []) + (["-to", str(end)] if end > start else [])
    vf = ["-vf", "scale=-2:%d" % plan["height"]] if plan["scale"] else []
    with tempfile.TemporaryDirectory(prefix="toolbelt-2pass-") as tmp:
        log = str(Path(tmp) / "pass")
        common = ["-i", src] + trim + ["-c:v", "libx264", "-b:v", "%dk" % plan["video_kbps"], "-maxrate", "%dk" % int(plan["video_kbps"] * 1.3),
                  "-bufsize", "%dk" % (plan["video_kbps"] * 2), "-preset", "medium", "-pix_fmt", "yuv420p"] + vf + ["-passlogfile", log]
        run(job, common + ["-pass", "1", "-an", "-f", "null", "NUL"], plan["length"], "Measuring (pass 1 of 2)", 0, 45)
        audio = ["-c:a", "aac", "-b:a", "%dk" % plan["audio_kbps"]] if plan["audio_kbps"] else ["-an"]
        run(job, common + ["-pass", "2"] + audio + ["-movflags", "+faststart", dest], plan["length"], "Compressing (pass 2 of 2)", 45, 55)
    job.extra["plan"] = plan
    job.extra["size"] = dest.stat().st_size
    return str(dest)


# ---------- GIF / WebM / looping MP4 from a piece of video ----------
def clip(job, src, kind, folder, start=0.0, end=0.0, width=480, fps=15, dither="bayer"):
    src = Path(src)
    info = probe(src)
    if info["kind"] not in ("video", "gif"):
        raise MediaError("Pick a video (or a GIF) first.")
    length = (end - start) if end > start else info["duration"]
    if kind == "gif" and length > 60:
        raise MediaError("A GIF longer than a minute gets huge. Pick a shorter piece.")
    trim = (["-ss", str(start)] if start > 0 else []) + (["-t", str(length)] if end > start else [])
    scale = "fps=%s,scale=%d:-2:flags=lanczos" % (fps, int(width))
    if kind == "gif":
        dest = out_path(folder, src.stem, ".gif")
        dith = "floyd_steinberg" if dither == "smooth" else "bayer:bayer_scale=5"
        vf = scale + ",split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=%s:diff_mode=rectangle" % dith
        args = trim + ["-i", src, "-vf", vf, "-loop", "0", dest]
        label = "Making the GIF"
    elif kind == "webm":
        dest = out_path(folder, src.stem, ".webm")
        args = trim + ["-i", src, "-vf", scale, "-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-row-mt", "1", "-an", dest]
        label = "Making the WebM"
    elif kind == "webp":
        dest = out_path(folder, src.stem, ".webp")
        args = trim + ["-i", src, "-vf", scale, "-c:v", "libwebp", "-lossless", "0", "-q:v", "80", "-loop", "0", "-an", dest]
        label = "Making the animated WebP"
    else:
        dest = out_path(folder, src.stem + " - loop", ".mp4")
        args = trim + ["-i", src, "-vf", scale, "-c:v", "libx264", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", dest]
        label = "Making the looping MP4"
    run(job, args, length, label)
    job.extra["size"] = dest.stat().st_size
    return str(dest)


def trim(job, src, folder, start, end):
    """Just the piece between start and end, nothing re-encoded (cuts land on the nearest keyframe)."""
    src = Path(src)
    info = probe(src)
    dest = out_path(folder, "%s - %s-%s" % (src.stem, _hms(start), _hms(end)), src.suffix)
    run(job, ["-ss", str(start), "-to", str(end), "-i", src, "-c", "copy", "-avoid_negative_ts", "make_zero", dest], end - start, "Trimming")
    job.extra["size"] = dest.stat().st_size
    return str(dest)


def _hms(seconds):
    seconds = int(seconds)
    return "%d.%02d" % (seconds // 60, seconds % 60)


# ---------- pictures (Pillow) ----------
def open_picture(path):
    try:
        img = Image.open(path)
        img.load()
        return ImageOps.exif_transpose(img)
    except Exception:
        raise MediaError("That picture couldn't be opened." + ("" if HEIC or Path(path).suffix.lower() not in (".heic", ".heif") else " (HEIC needs pillow-heif.)"))


def encode(img, fmt, quality=80, lossless=False):
    """The picture as bytes in `fmt` at `quality`; returns (bytes, ending)."""
    buf = io.BytesIO()
    fmt = fmt.lower()
    if fmt in ("jpg", "jpeg"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA", "P"):
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
        else:
            bg = img.convert("RGB")
        bg.save(buf, "JPEG", quality=int(quality), optimize=True, progressive=True)
        return buf.getvalue(), ".jpg"
    if fmt == "webp":
        img.convert("RGBA" if "A" in img.getbands() else "RGB").save(buf, "WEBP", quality=int(quality), lossless=lossless, method=4)
        return buf.getvalue(), ".webp"
    if fmt == "avif":
        img.convert("RGBA" if "A" in img.getbands() else "RGB").save(buf, "AVIF", quality=int(quality))
        return buf.getvalue(), ".avif"
    if fmt == "png":
        out = img
        if lossless is False and img.mode in ("RGB", "RGBA") and quality < 100:
            out = img.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
        out.save(buf, "PNG", optimize=True)
        return buf.getvalue(), ".png"
    if fmt == "gif":
        img.convert("RGBA").convert("P", palette=Image.Palette.ADAPTIVE).save(buf, "GIF")
        return buf.getvalue(), ".gif"
    if fmt == "bmp":
        img.convert("RGB").save(buf, "BMP")
        return buf.getvalue(), ".bmp"
    if fmt == "tiff":
        img.save(buf, "TIFF", compression="tiff_lzw")
        return buf.getvalue(), ".tiff"
    if fmt == "ico":
        sizes = [s for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(img.size) or s == 16]
        square = ImageOps.pad(img.convert("RGBA"), (max(img.size), max(img.size)), color=(0, 0, 0, 0))
        square.save(buf, "ICO", sizes=[(s, s) for s in sizes])
        return buf.getvalue(), ".ico"
    raise MediaError("Unknown picture format.")


def preview_data(img, side=900):
    small = img.copy()
    small.thumbnail((side, side))
    data, _ = encode(small, "webp", 85)
    return "data:image/webp;base64," + base64.b64encode(data).decode("ascii")


def compress_picture(src, fmt, quality, folder=None, lossless=False):
    """Returns {size, path?} and when folder is None only the size + a preview of what it would look like."""
    img = open_picture(src)
    data, ext = encode(img, fmt, quality, lossless)
    if folder is None:
        after = Image.open(io.BytesIO(data)) if ext not in (".ico",) else img
        return {"size": len(data), "preview": preview_data(after)}
    dest = out_path(folder, Path(src).stem, ext)
    dest.write_bytes(data)
    return {"size": len(data), "path": str(dest)}


def resize_picture(src, preset, folder, width=0, height=0, keep_shape=True, pixel_art=False, fmt=""):
    img = open_picture(src)
    sampler = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    if preset == "custom":
        w, h = int(width), int(height)
        if not w and not h:
            raise MediaError("Give a width or a height.")
        mode = "fit" if keep_shape else "exact"
    else:
        if preset not in RESIZE:
            raise MediaError("Unknown size.")
        _, w, h, mode = RESIZE[preset]
    if mode == "percent":
        out = img.resize((max(1, img.width // 2), max(1, img.height // 2)), sampler)
    elif mode == "ico":
        data, ext = encode(img, "ico")
        dest = out_path(folder, Path(src).stem, ext)
        dest.write_bytes(data)
        return {"path": str(dest), "width": 256, "height": 256}
    elif mode == "square":
        out = ImageOps.pad(img.convert("RGBA"), (w, h), method=sampler, color=(0, 0, 0, 0))
    elif mode == "exact":
        out = img.resize((w or img.width, h or img.height), sampler)
    else:                                                       # fit: keep the shape inside w×h
        if not w:
            w = int(img.width * h / img.height)
        if not h:
            h = int(img.height * w / img.width)
        out = img.copy()
        out.thumbnail((w, h), sampler)
        if pixel_art:                                           # thumbnail() ignores the sampler for pixel art; do it by hand
            ratio = min(w / img.width, h / img.height)
            out = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), sampler)
    fmt = fmt or ("png" if "A" in out.getbands() or pixel_art or mode == "square" else Path(src).suffix.lstrip(".").lower().replace("jpeg", "jpg"))
    if fmt not in PICTURE_OUT:
        fmt = "png"
    data, ext = encode(out, fmt, 92, lossless=True)             # a resized PNG keeps all its colours and see-through parts
    dest = out_path(folder, "%s - %dx%d" % (Path(src).stem, out.width, out.height), ext)
    dest.write_bytes(data)
    return {"path": str(dest), "width": out.width, "height": out.height}


def picture_format(src, fmt, folder, quality=90):
    img = open_picture(src)
    data, ext = encode(img, fmt, quality)
    dest = out_path(folder, Path(src).stem, ext)
    dest.write_bytes(data)
    return {"path": str(dest), "size": len(data)}


# ---------- game clips: the recordings already on this PC ----------
def other_drives():
    """Drive letters besides C: that exist (his videos and pictures live on E:, C: is for games; 15 Oct)."""
    import string
    return [Path("%s:\\" % d) for d in string.ascii_uppercase[3:] if Path("%s:\\" % d).exists()]


def media_root(kind="Videos"):
    """Where to start a file picker: the first other drive's Videos / Pictures folder, else Windows' own."""
    for drive in other_drives():
        if (drive / kind).is_dir():
            return drive / kind
    return Path(shellicon.known_folder(kind if kind in ("Videos", "Music") else "Videos"))


def clip_folders():
    """Where ReLive, Game Bar, Steam, OBS and the like put recordings, on every drive. Only folders that exist."""
    home = Path.home()
    roots = [Path(shellicon.known_folder("Videos")), home / "Videos", home / "OneDrive" / "Video's", home / "OneDrive" / "Videos",
             home / "Videos" / "Steam Recordings"] + [d / "Videos" for d in other_drives()]
    seen, out = set(), []
    for r in roots:
        try:
            key = str(r.resolve()).lower()
        except OSError:
            continue
        if r.is_dir() and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def source_of(path, root):
    parts = [p.lower() for p in Path(path).relative_to(root).parts[:-1]]
    text = " ".join(parts)
    for mark, name in (("relive", "ReLive"), ("captures", "Game Bar"), ("steam", "Steam"), ("obs", "OBS"), ("moments", "Moments"), ("nvidia", "ShadowPlay"), ("medal", "Medal"), ("clips", "Clips")):
        if mark in text:
            return name
    return "Videos"


def game_clips(limit=60, roots=None):
    """The newest recordings, newest first: name, game (its folder), where it came from, size, when."""
    found = []
    for root in roots or clip_folders():
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() not in ("replay_cache", "desktop.ini", ".tmp") and Path(dirpath, d).relative_to(root).parts.__len__() < 4]
            for name in files:
                if Path(name).suffix.lower() not in VIDEO_EXT:
                    continue
                path = Path(dirpath) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                if st.st_size < 20 * 1024:                      # a broken or empty recording
                    continue
                parent = path.parent
                game = parent.name if parent != root and parent.name.lower() not in ("radeon relive", "captures", "videos", "unknown") else ""
                found.append({"path": str(path), "name": path.name, "game": game, "source": source_of(path, root), "size": st.st_size,
                              "when": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)), "mtime": st.st_mtime})
    found.sort(key=lambda c: c["mtime"], reverse=True)
    for c in found:
        c.pop("mtime", None)
    return found[:limit]


def save_folder(settings, sub="Media"):
    s = settings
    return Path(s["save_to"]) / (sub if s["folder_per_tool"] else "")


def unique_key(path):
    return re.sub(r"[^a-z0-9]", "", hashlib.sha1(str(path).lower().encode("utf-8")).hexdigest()[:12])


# ---------- playing inside Toolbelt (viewer.py) ----------
PREVIEW = DATA / "cache" / "preview"


def preview_copy(path, make=False, job=None):
    """A light H.264 copy (720p at most) for videos WebView2 can't play itself (unusual codecs), kept in AppData by the
    original's path, size and date. make=False only says whether one is there already."""
    path = Path(path)
    try:
        st = path.stat()
    except OSError:
        return None
    key = hashlib.sha1(("%s|%d|%d" % (str(path).lower(), st.st_size, int(st.st_mtime))).encode("utf-8")).hexdigest()[:20]
    out = PREVIEW / ("%s.mp4" % key)
    if out.exists() or not make:
        return out if out.exists() else None
    PREVIEW.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    part = out.with_name(out.stem + ".part.mp4")

    class _Quiet:                                                 # no job: still run, just without progress
        def report(self, *a):
            pass

        def check(self):
            pass
    run(job or _Quiet(), ["-i", path, "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", part],
        info.get("duration") or 0, "Making a copy Toolbelt can play")
    part.replace(out)
    return out


def picture_size(path):
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


# ---------- crop (15 Oct) ----------
RATIOS = {"1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3), "3:2": (3, 2), "4:5": (4, 5), "3:1": (3, 1), "21:9": (21, 9)}


def centre_box(width, height, ratio):
    """The biggest box of this shape in the middle of the picture."""
    rw, rh = RATIOS[ratio]
    if width * rh > height * rw:                                  # too wide: trim the sides
        w = height * rw // rh
        return {"x": (width - w) // 2, "y": 0, "w": w, "h": height}
    h = width * rh // rw
    return {"x": 0, "y": (height - h) // 2, "w": width, "h": h}


def crop_picture(src, box, folder, fmt=""):
    """box = {x, y, w, h} in the picture's own pixels, or a ratio like "16:9" for the middle. Saved as a new file."""
    img = open_picture(src)
    if isinstance(box, str):
        if box not in RATIOS:
            raise MediaError("Unknown shape.")
        box = centre_box(img.width, img.height, box)
    try:
        x, y, w, h = (int(round(float(box[k]))) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        raise MediaError("Draw the part to keep first.")
    x, y = max(0, min(x, img.width - 1)), max(0, min(y, img.height - 1))
    w, h = max(1, min(w, img.width - x)), max(1, min(h, img.height - y))
    out = img.crop((x, y, x + w, y + h))
    fmt = fmt or Path(src).suffix.lstrip(".").lower().replace("jpeg", "jpg")
    if fmt not in PICTURE_OUT or fmt in ("ico", "gif"):
        fmt = "png" if "A" in out.getbands() else "jpg"
    data, ext = encode(out, fmt, 92, lossless=True)
    dest = out_path(folder, "%s - cropped %dx%d" % (Path(src).stem, w, h), ext)
    dest.write_bytes(data)
    return {"path": str(dest), "width": w, "height": h, "size": len(data)}


# ---------- many pictures at once (15 Oct) ----------
BATCH_ACTIONS = {"icomp": "Compressed", "resize": "Resized", "format": "Converted", "crop": "Cropped"}


def batch_pictures(job, sources, action, opts, folder):
    """One action on many pictures. Everything lands in one new folder; a picture that fails is skipped and named."""
    if action not in BATCH_ACTIONS:
        raise MediaError("Unknown action.")
    sources = [Path(p) for p in sources]
    out = out_folder(folder, "%s %s" % (BATCH_ACTIONS[action], time.strftime("%Y-%m-%d %H.%M")))
    done, failed, before, after = [], [], 0, 0
    for i, src in enumerate(sources):
        job.check()
        job.report(i * 100 / max(len(sources), 1), "%d of %d · %s" % (i + 1, len(sources), src.name[:50]))
        try:
            if action == "icomp":
                r = compress_picture(src, str(opts.get("fmt", "webp")), int(opts.get("quality", 80)), out, bool(opts.get("lossless")))
            elif action == "resize":
                r = resize_picture(src, str(opts.get("preset", "half")), out, int(opts.get("width", 0) or 0), int(opts.get("height", 0) or 0),
                                   bool(opts.get("keep", True)), bool(opts.get("pixel")), str(opts.get("fmt", "")))
            elif action == "format":
                r = picture_format(src, str(opts.get("fmt", "jpg")), out, int(opts.get("quality", 90)))
            else:
                r = crop_picture(src, str(opts.get("ratio", "1:1")), out)
            before += src.stat().st_size
            after += Path(r["path"]).stat().st_size
            done.append(r["path"])
        except (MediaError, OSError) as error:
            failed.append("%s (%s)" % (src.name, str(error)[:80]))
    job.report(100, "%d done%s" % (len(done), (", %d skipped" % len(failed)) if failed else ""))
    if not done:
        try:
            out.rmdir()
        except OSError:
            pass
        raise MediaError("None of the pictures worked: " + "; ".join(failed[:3]))
    return {"folder": str(out), "done": len(done), "failed": failed, "before": before, "after": after, "first": done[0]}


def out_folder(folder, name):
    base = Path(folder)
    base.mkdir(parents=True, exist_ok=True)
    target, n = base / name, 2
    while target.exists():
        target, n = base / ("%s (%d)" % (name, n)), n + 1
    target.mkdir()
    return target


# ---------- sound (15 Oct): cut with fades, even out the loudness ----------
AUDIO_CODEC = {".mp3": ["-c:a", "libmp3lame", "-b:a", "320k"], ".m4a": ["-c:a", "aac", "-b:a", "256k"], ".aac": ["-c:a", "aac", "-b:a", "256k"],
               ".wav": ["-c:a", "pcm_s16le"], ".flac": ["-c:a", "flac"], ".opus": ["-c:a", "libopus", "-b:a", "160k"], ".ogg": ["-c:a", "libopus", "-b:a", "160k"]}
LOUDNESS = {"spotify": (-14, "Spotify / YouTube"), "podcast": (-16, "Voice, podcasts"), "loud": (-9, "Loud, like clubs"), "quiet": (-23, "TV / film")}


def _audio_out(src):
    """Sound files keep their own kind; a video keeps its picture untouched and gets AAC sound."""
    ext = Path(src).suffix.lower()
    if ext in AUDIO_CODEC:
        return ext, AUDIO_CODEC[ext]
    if ext == ".wma":
        return ".mp3", AUDIO_CODEC[".mp3"]
    return (ext if ext in (".mp4", ".mkv", ".mov", ".m4v") else ".mp4"), ["-c:v", "copy", "-c:a", "aac", "-b:a", "256k"]


def cut_sound(job, src, folder, start, end, fade_in=0.0, fade_out=0.0):
    """A piece of a song (or a video's sound track kept with the picture), with optional fade in / out."""
    info = probe(src)
    length = float(info.get("duration") or 0)
    end = end if end and end > start else length
    if end - start < 0.2:
        raise MediaError("Pick a piece first (From and To).")
    ext, codec = _audio_out(src)
    fades = []
    if fade_in > 0:
        fades.append("afade=t=in:st=0:d=%.2f" % fade_in)
    if fade_out > 0:
        fades.append("afade=t=out:st=%.2f:d=%.2f" % (max(0.0, end - start - fade_out), fade_out))
    if info["kind"] == "video" and "-c:v" in codec:
        codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "256k"]   # an exact cut needs re-encoding
    dest = out_path(folder, "%s - %dm%02ds to %dm%02ds" % (Path(src).stem, int(start) // 60, int(start) % 60, int(end) // 60, int(end) % 60), ext)
    args = ["-ss", "%.3f" % start, "-t", "%.3f" % (end - start), "-i", src, "-map", "0:a:0"] + (["-map", "0:v:0?"] if info["kind"] == "video" else ["-map", "0:v?", "-c:v", "copy", "-disposition:v", "attached_pic"] if ext in (".mp3", ".m4a") else []) + \
        (["-af", ",".join(fades)] if fades else []) + codec + ["-map_metadata", "0", dest]
    run(job, args, end - start, "Cutting")
    return str(dest)


def measure_loudness(job, src, duration):
    """Pass 1 of ffmpeg's loudnorm: how loud the file really is (EBU R128 numbers)."""
    cmd = [str(ffmpeg()), "-hide_banner", "-nostats", "-i", str(src), "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    text = []
    try:
        for line in proc.stderr:
            job.check()
            text.append(line)
            m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
            if m and duration:
                job.report(min(45.0, 45 * (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) / duration), "Listening how loud it is")
    except Cancelled:
        proc.kill()
        raise
    proc.wait()
    blob = "".join(text)
    found = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", blob, re.S)
    if proc.returncode != 0 or not found:
        raise MediaError("ffmpeg couldn't measure the loudness.")
    return json.loads(found.group(0))


def normalise(job, src, folder, target="spotify"):
    """Even out the loudness to a target (two passes, so it's exact and never clips). Returns (path, before LUFS, after)."""
    if target not in LOUDNESS:
        raise MediaError("Unknown loudness.")
    lufs = LOUDNESS[target][0]
    info = probe(src)
    if not info.get("acodec"):
        raise MediaError("That file has no sound.")
    m = measure_loudness(job, src, info.get("duration") or 0)
    ext, codec = _audio_out(src)
    flt = ("loudnorm=I=%d:TP=-1:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
           % (lufs, m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))
    rate = ["-ar", "48000"] if ext in (".opus", ".ogg", ".mp4", ".mkv", ".mov", ".m4v", ".m4a", ".aac") else ["-ar", "44100"]
    dest = out_path(folder, "%s - even %d LUFS" % (Path(src).stem, lufs), ext)
    maps = ["-map", "0:a:0"] + (["-map", "0:v:0?"] if info["kind"] == "video" else ["-map", "0:v?", "-c:v", "copy"] if ext in (".mp3", ".m4a") else [])
    run(job, ["-i", src] + maps + ["-af", flt] + rate + codec + ["-map_metadata", "0", dest], info.get("duration") or 0, "Evening out the loudness", 45, 55)
    return str(dest), float(m["input_i"]), lufs


# ---------- subtitles (15 Oct): whisper.cpp on his own PC ----------
SUB_LANGS = {"auto": "Find out by itself", "en": "English", "ja": "Japanese", "nl": "Dutch", "ko": "Korean", "zh": "Chinese", "es": "Spanish", "de": "German", "fr": "French"}


def subtitles(job, src, folder, lang="auto", translate=False, put_in="srt"):
    """Speech to text with whisper.cpp: an .srt next to the result, and optionally the video with the subtitles in it
    (put_in = "srt" only, "track" = a subtitle track you can switch on, "burn" = written into the picture)."""
    cli = engines.path_of("whisper")
    model = engines.path_of("whispermodel")
    if not cli or not model:
        raise MediaError("Install whisper.cpp and the Whisper model first (the button on this page).")
    if lang not in SUB_LANGS:
        raise MediaError("Unknown language.")
    info = probe(src)
    if not info.get("acodec"):
        raise MediaError("That file has no sound to listen to.")
    duration = float(info.get("duration") or 0)
    work = Path(tempfile.mkdtemp(prefix="toolbelt-subs-"))
    try:
        wav = work / "sound.wav"
        run(job, ["-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], duration, "Taking the sound out", 0, 8)
        threads = max(2, min(16, (os.cpu_count() or 4) - 1))
        cmd = [str(cli), "-m", str(model), "-f", str(wav), "-l", lang, "-t", str(threads), "-osrt", "-of", str(work / "subs"), "-pp", "-np"] + (["-tr"] if translate else [])
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                creationflags=NO_WINDOW, cwd=str(cli.parent))
        tail = []
        try:
            for line in proc.stderr:
                job.check()
                tail = (tail + [line])[-20:]
                m = re.search(r"progress\s*=\s*(\d+)%", line)
                if m:
                    job.report(8 + 80 * int(m.group(1)) / 100, "Listening and writing it down (%s%%)" % m.group(1))
        except Cancelled:
            proc.kill()
            raise
        proc.wait()
        srt = work / "subs.srt"
        if proc.returncode != 0 or not srt.is_file():
            raise MediaError("whisper.cpp stopped: " + ("".join(tail).strip().splitlines() or ["unknown error"])[-1][:200])
        stem = Path(src).stem + (" - English" if translate else "")
        dest_srt = out_path(folder, stem, ".srt")
        dest_srt.write_bytes(srt.read_bytes())
        if put_in == "srt" or info["kind"] != "video":
            job.report(100, "Subtitles written")
            return str(dest_srt), str(dest_srt)
        if put_in == "track":
            ext = ".mkv" if Path(src).suffix.lower() in (".mkv", ".webm") else ".mp4"
            dest = out_path(folder, stem + " - with subtitles", ext)
            run(job, ["-i", src, "-i", dest_srt, "-map", "0", "-map", "1", "-c", "copy", "-c:s", "srt" if ext == ".mkv" else "mov_text",
                      "-metadata:s:s:0", "language=" + ("eng" if translate or lang == "en" else {"ja": "jpn", "nl": "nld", "ko": "kor", "zh": "zho", "es": "spa", "de": "deu", "fr": "fra"}.get(lang, "und")), dest],
                duration, "Adding the subtitle track", 88, 12)
            return str(dest), str(dest_srt)
        # burn: the subtitles filter wants the path written with forward slashes and the drive's colon escaped
        local = work / "subs.srt"
        font = "Segoe UI" if translate else {"ja": "Yu Gothic UI", "zh": "Microsoft YaHei UI", "ko": "Malgun Gothic"}.get(lang, "Segoe UI")
        if lang == "auto" and not translate and re.search(r"[぀-ヿ一-鿿가-힯]", local.read_text(encoding="utf-8", errors="replace")):
            font = "Yu Gothic UI"                                 # it heard Japanese / Chinese / Korean: a font that has those letters
        dest = out_path(folder, stem + " - subtitled", ".mp4")
        run(job, ["-i", src, "-vf", "subtitles=subs.srt:force_style='FontName=%s,FontSize=22,Outline=2,Shadow=0,MarginV=28'" % font, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                  "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dest], duration, "Writing them into the picture", 88, 12, cwd=str(work))
        local.unlink(missing_ok=True)
        return str(dest), str(dest_srt)
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
