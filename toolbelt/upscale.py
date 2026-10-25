"""AI upscaling with Real-ESRGAN (the ncnn-vulkan build, so it runs on his AMD card through Vulkan).

- `upscale_picture`: one picture, 2× / 3× / 4×, with a model that suits photos or drawings.
- `sharpen_gif`: a GIF is taken apart into frames (ffmpeg), every frame is upscaled (the anime model is made for
  this), and the frames are put back together as a GIF, an animated WebP or a looping MP4.
Real-ESRGAN prints a percentage while it works on one picture; for a folder of frames progress is counted by
the files it has finished.
"""
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image

import engines
import media
from jobs import Cancelled

NO_WINDOW = 0x08000000
MODELS = [
    ("realesrgan-x4plus", "Photos and screenshots", "sharp and natural; the slow, careful one", (4,)),
    ("realesrgan-x4plus-anime", "Drawings and anime", "clean lines, no noise", (4,)),
    ("realesr-animevideov3", "GIFs and anime video", "fast; the one for GIF sharpening", (2, 3, 4)),
]


def exe():
    path = engines.path_of("realesrgan")
    if not path:
        raise media.MediaError("Install Real-ESRGAN first (the button on this page).")
    return path


def models():
    """The models that are really on disk, for the page."""
    folder = engines.path_of("realesrgan")
    folder = folder.parent / "models" if folder else None
    out = []
    for name, good_for, note, scales in MODELS:
        if folder and (folder / (name + ".bin")).exists() or name == "realesr-animevideov3" and folder and any(folder.glob(name + "-x*.bin")):
            out.append({"id": name, "for": good_for, "note": note, "scales": list(scales)})
    return out


RUNNING = set()                 # Real-ESRGAN processes started here, so quitting Toolbelt can stop them (stop_all)


def stop_all():
    for proc in list(RUNNING):
        try:
            proc.kill()
        except OSError:
            pass


def _run(job, args, label, start, span, total_files=0, out_dir=None):
    cmd = [str(exe()), "-m", str(exe().parent / "models")] + [str(a) for a in args]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    RUNNING.add(proc)
    job.report(start, label)
    tail, pct = [], [None]

    # Real-ESRGAN writes a line per frame / tile. That text MUST be read all the time: when nobody read it, Windows'
    # pipe filled up after ~48 frames and Real-ESRGAN froze for good (his game-art videos never finished, 15 Oct).
    def drain():
        for line in proc.stderr:
            tail.append(line.strip())
            del tail[:-5]
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                pct[0] = float(m.group(1))
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        while proc.poll() is None:
            job.check()
            time.sleep(0.3)
            if total_files and out_dir:
                done = len([n for n in os.listdir(out_dir) if n.lower().endswith(".png")])
                job.report(start + span * min(1.0, done / total_files), "%s (%d of %d)" % (label, done, total_files))
            elif pct[0] is not None:
                job.report(start + span * min(1.0, pct[0] / 100), label)
    except Cancelled:
        proc.kill()
        proc.wait()
        raise
    finally:
        RUNNING.discard(proc)
    proc.wait()
    reader.join(5)
    if proc.returncode != 0:
        raise media.MediaError("Real-ESRGAN stopped: " + (tail[-1][:200] if tail else "unknown error"))
    job.report(start + span, label)


def upscale_picture(job, src, scale, model, folder):
    src = Path(src)
    scale = int(scale)
    if model not in [m[0] for m in MODELS]:
        raise media.MediaError("Unknown model.")
    if model != "realesr-animevideov3" and scale != 4:
        allowed = 4
    else:
        allowed = scale if scale in (2, 3, 4) else 4
    img = media.open_picture(src)
    if img.width * img.height > 4000 * 4000:
        raise media.MediaError("That picture is already bigger than 16 megapixels; upscaling it would be enormous.")
    with tempfile.TemporaryDirectory(prefix="toolbelt-up-") as tmp:
        inp = Path(tmp) / "in.png"
        img.convert("RGBA" if "A" in img.getbands() else "RGB").save(inp, "PNG")
        out = Path(tmp) / "out.png"
        _run(job, ["-i", inp, "-o", out, "-n", model, "-s", allowed, "-f", "png"], "Upscaling %d× on the graphics card" % allowed, 0, 90)
        result = Image.open(out)
        result.load()
    if allowed != scale:                                        # x4 models only do 4×: shrink back to what he asked
        result = result.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    ext = ".png" if "A" in result.getbands() or src.suffix.lower() == ".png" else ".jpg"
    data, ext = media.encode(result, ext.lstrip("."), 94)
    dest = media.out_path(folder, "%s - %dx" % (src.stem, scale), ext)
    dest.write_bytes(data)
    job.extra.update({"size": dest.stat().st_size, "width": result.width, "height": result.height})
    return str(dest)


CHUNK = 96                      # frames per batch: at 4K output about 1 GB of temporary PNGs, then they are deleted


def plan_video(info, scale, start=0.0, end=0.0):
    """What a video upscale would mean: frames to do, output size, a rough time. For the page before he starts."""
    length = (end - start) if end > start else info["duration"]
    fps = info["fps"] or 30
    frames = int(length * fps)
    scale = int(scale)
    out_h = info["height"] * scale
    ok, why = True, ""
    if out_h > 2160:
        ok, why = False, "That would be %d pixels tall; Toolbelt stops at 4K. Pick a smaller ×." % out_h
    elif frames > 18000:
        ok, why = False, "That's %d frames (over 10 minutes): trim it to a piece first." % frames
    elif not info["height"]:
        ok, why = False, "That isn't a video."
    per_frame = 0.08 * (out_h / 1080) ** 2                      # seconds per frame on a card like his, roughly
    return {"frames": frames, "width": info["width"] * scale, "height": out_h, "minutes": max(1, int(frames * per_frame / 60 + 0.5)), "ok": ok, "why": why}


def upscale_video(job, src, scale, model, folder, start=0.0, end=0.0, work_dir=None):
    """Video → frames → Real-ESRGAN → video, in batches so the disk never fills up. The original sound is put back.
    work_dir: keep the finished batches there, so a restart of Toolbelt carries on instead of starting over (the game
    art's HD worker uses it; his video backgrounds were restarted from zero with every restart, 15 Oct)."""
    import contextlib
    src = Path(src)
    info = media.probe(src)
    plan = plan_video(info, scale, start, end)
    if not plan["ok"]:
        raise media.MediaError(plan["why"])
    scale = int(scale)
    fps = info["fps"] or 30
    length = (end - start) if end > start else info["duration"]
    total = plan["frames"]
    fast = model != "realesrgan-x4plus"
    run_scale = scale if fast else 4                            # the photo model only does 4×; shrink afterwards
    name = "realesr-animevideov3" if fast else "realesrgan-x4plus"
    dest = media.out_path(folder, "%s - %dx" % (src.stem, scale), ".mp4")
    t0 = time.time()
    holder = contextlib.nullcontext(str(work_dir)) if work_dir else tempfile.TemporaryDirectory(prefix="toolbelt-video-")
    with holder as tmp:
        tmp = Path(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        for wip in tmp.glob("wip-*.mkv"):                         # a batch that was being saved when Toolbelt stopped
            wip.unlink()
        chunks = sorted(tmp.glob("part*.mkv")) if work_dir else []
        done = resumed = len(chunks) * CHUNK                       # batches finished before a restart are kept
        while done < total:
            job.check()
            n = min(CHUNK, total - done)
            frames, sharp = tmp / "frames", tmp / "sharp"
            for d in (frames, sharp):
                if d.exists():
                    for f in d.iterdir():
                        f.unlink()
                d.mkdir(exist_ok=True)
            at = start + done / fps - 0.4 / fps                  # a hair before the frame, so rounding never skips it
            pct = 92.0 * done / total
            media.run(job, ["-ss", "%.6f" % max(0.0, at), "-i", src, "-vf", "fps=%s" % fps, "-frames:v", n, "-fps_mode", "passthrough", str(frames / "%05d.png")],
                      n / fps, "Reading frames %d–%d of %d" % (done + 1, done + n, total), pct, 1.0)
            got = len(list(frames.glob("*.png")))
            if not got:
                break
            left = ""
            if done > resumed:
                rate = (time.time() - t0) / (done - resumed)
                left = ", about %d min left" % max(1, int(rate * (total - done) / 60 + 0.5))
            _run(job, ["-i", frames, "-o", sharp, "-n", name, "-s", run_scale, "-f", "png"], "Upscaling frames %d–%d of %d%s" % (done + 1, done + got, total, left),
                 pct + 1.0, 92.0 * got / total - 2.0, got, sharp)
            part = tmp / ("part%04d.mkv" % len(chunks))
            wip = tmp / ("wip-%04d.mkv" % len(chunks))             # only a finished batch gets its part name
            vf = ["-vf", "scale=%d:%d:flags=lanczos" % (info["width"] * scale, info["height"] * scale)] if run_scale != scale else ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
            media.run(job, ["-framerate", fps, "-i", str(sharp / "%05d.png")] + vf + ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", str(wip)],
                      got / fps, "Saving frames %d–%d" % (done + 1, done + got), pct + 92.0 * got / total - 1.0, 1.0)
            os.replace(wip, part)
            chunks.append(part)
            done += got
            if got < n:
                break
        if not chunks:
            raise media.MediaError("No frames came out of that video.")
        listing = tmp / "parts.txt"
        listing.write_text("".join("file '%s'\n" % str(p).replace("'", "'\\''") for p in chunks), encoding="utf-8")
        trim = (["-ss", str(start)] if start > 0 else []) + (["-to", str(end)] if end > start else [])
        args = ["-f", "concat", "-safe", "0", "-i", str(listing)] + trim + ["-i", src, "-map", "0:v:0"]
        if info["acodec"]:
            args += ["-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k"]
        args += ["-c:v", "copy", "-shortest", "-movflags", "+faststart", str(dest)]
        media.run(job, args, length, "Putting the sound back", 93, 7)
    job.extra.update({"size": dest.stat().st_size, "width": plan["width"], "height": plan["height"], "frames": done, "seconds": int(time.time() - t0)})
    return str(dest)


def sharpen_gif(job, src, scale, out_kind, folder, dither="bayer"):
    """GIF → frames → Real-ESRGAN (anime video model) → GIF / animated WebP / looping MP4."""
    src = Path(src)
    info = media.probe(src)
    if info["kind"] not in ("gif", "video"):
        raise media.MediaError("Pick a GIF first.")
    scale = int(scale) if int(scale) in (2, 3, 4) else 2
    fps = info["fps"] or 12
    if info["duration"] > 30:
        raise media.MediaError("That one is longer than 30 seconds: sharpening every frame would take ages. Trim it first.")
    with tempfile.TemporaryDirectory(prefix="toolbelt-gif-") as tmp:
        frames, sharp = Path(tmp) / "frames", Path(tmp) / "sharp"
        frames.mkdir()
        sharp.mkdir()
        media.run(job, ["-i", src, "-fps_mode", "passthrough", str(frames / "%05d.png")], info["duration"], "Taking the GIF apart", 0, 8)
        count = len(list(frames.glob("*.png")))
        if not count:
            raise media.MediaError("No frames came out of that file.")
        if count > 600:
            raise media.MediaError("%d frames is too many for one go; trim the GIF first." % count)
        _run(job, ["-i", frames, "-o", sharp, "-n", "realesr-animevideov3", "-s", scale, "-f", "png"], "Sharpening %d frames on the graphics card" % count, 8, 80, count, sharp)
        inp = ["-framerate", str(fps), "-i", str(sharp / "%05d.png")]
        if out_kind == "gif":
            dest = media.out_path(folder, "%s - sharp %dx" % (src.stem, scale), ".gif")
            dith = "floyd_steinberg" if dither == "smooth" else "bayer:bayer_scale=5"
            vf = "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=%s:diff_mode=rectangle" % dith
            args = inp + ["-vf", vf, "-loop", "0", str(dest)]
        elif out_kind == "webp":
            dest = media.out_path(folder, "%s - sharp %dx" % (src.stem, scale), ".webp")
            args = inp + ["-c:v", "libwebp", "-lossless", "0", "-q:v", "82", "-loop", "0", str(dest)]
        else:
            dest = media.out_path(folder, "%s - sharp %dx" % (src.stem, scale), ".mp4")
            args = inp + ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)]
        media.run(job, args, info["duration"], "Putting it back together as " + out_kind.upper(), 88, 12)
    job.extra.update({"size": dest.stat().st_size, "frames": count})
    return str(dest)
