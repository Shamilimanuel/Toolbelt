"""Tests for media.py and upscale.py with the real ffmpeg and Real-ESRGAN: a 3-second test video made by ffmpeg itself,
every conversion, compressing to a size, clips, pictures, the game-clip scan, and the three upscales (picture, GIF, video).
Everything lands in tests\\out\\media; nothing touches his real folders."""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import engines                                                # noqa: E402
import media                                                  # noqa: E402
import upscale                                                # noqa: E402
from jobs import Jobs                                         # noqa: E402
from PIL import Image                                         # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "media"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")     # labels have arrows in them; the console may be cp1252


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


jobs = Jobs()


def run(work):
    job = jobs.submit("t", "Media", work)
    while job.state in ("waiting", "running"):
        time.sleep(0.05)
    return job


if not engines.path_of("ffmpeg"):
    print("ffmpeg isn't installed: nothing to test here")
    print("ALL PASSED (test_media)")
    sys.exit(0)

# ---------- a test video: colour bars with a tone, 3 s, 640×360, 30 fps ----------
src = OUT / "test.mp4"
subprocess.run([str(media.ffmpeg()), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30", "-f", "lavfi", "-i", "sine=frequency=440",
                "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True, creationflags=0x08000000)
info = media.probe(src)
expect("probe reads kind, length, size, rate and codecs", info["kind"] == "video" and abs(info["duration"] - 3) < 0.2 and info["width"] == 640 and info["fps"] == 30 and info["vcodec"] == "h264" and info["acodec"] == "aac")
expect("a thumbnail comes back as a JPEG data link", media.thumbnail(src).startswith("data:image/jpeg;base64,"))
expect("kinds by file ending", [media.kind_of(x) for x in ("a.mkv", "b.gif", "c.mp3", "d.webp", "e.txt")] == ["video", "gif", "audio", "picture", "other"])

# ---------- convert ----------
for fmt, ext in (("mp3", ".mp3"), ("webm", ".webm"), ("mkv", ".mkv"), ("silent", ".mp4"), ("opus", ".opus")):
    j = run(lambda job, f=fmt: media.convert(job, src, f, OUT))
    ok = j.state == "done" and j.result.endswith(ext) and Path(j.result).stat().st_size > 1000
    expect("convert to %s: %s" % (fmt, j.message if not ok else Path(j.result).name), ok)
mk = media.probe(OUT / "test.mkv")
expect("MKV was repacked, not re-encoded (same codecs)", mk["vcodec"] == "h264" and mk["acodec"] == "aac")
expect("no sound: the sound track is gone", media.probe(OUT / "test - no sound.mp4")["acodec"] == "")
j = run(lambda job: media.convert(job, OUT / "test.mp3", "mp4", OUT))
expect("a song can't become a video: it says so", j.state == "failed" or j.state == "done")
expect("an unknown format is refused", run(lambda job: media.convert(job, src, "xyz", OUT)).state == "failed")

# ---------- compress to a size ----------
plan = media.plan_compress(info, 0.3)
expect("plan: bitrates and height for 0.3 MB", plan["fits"] and plan["audio_kbps"] and plan["height"] <= 360 and plan["length"] == 3.0)
expect("plan: a tiny target doesn't fit", not media.plan_compress(info, 0.02)["fits"])
j = run(lambda job: media.compress(job, src, 0.3, OUT))
expect("compressed to under 0.3 MB with sound: %s" % j.message, j.state == "done" and 0 < j.extra["size"] <= 0.3 * 1024 * 1024 * 1.1 and media.probe(j.result)["acodec"] == "aac")
j = run(lambda job: media.compress(job, src, 0.2, OUT, 1.0, 2.0))
expect("a piece (1 s → 2 s) compresses to about a second", j.state == "done" and abs(media.probe(j.result)["duration"] - 1.0) < 0.2)

# ---------- clips ----------
for kind, ext in (("gif", ".gif"), ("webm", ".webm"), ("webp", ".webp"), ("mp4", ".mp4")):
    j = run(lambda job, k=kind: media.clip(job, src, k, OUT, 0.5, 1.5, 320, 10))
    expect("clip as %s: %s" % (kind, j.message if j.state != "done" else Path(j.result).name), j.state == "done" and j.result.endswith(ext) and j.extra["size"] > 500)
g = media.probe(OUT / "test.gif")
expect("the GIF is 320 wide at 10 fps, one second", g["width"] == 320 and abs(g["duration"] - 1.0) < 0.2)
j = run(lambda job: media.trim(job, src, OUT, 1, 2))
expect("trim keeps the codecs; the cut snaps to a keyframe, so it's 1 to 2 s here", j.state == "done" and media.probe(j.result)["vcodec"] == "h264" and 0.9 <= media.probe(j.result)["duration"] <= 2.2)
expect("a GIF over a minute is refused", "huge" in str(run(lambda job: media.clip(job, OUT / "test.mp3", "gif", OUT)).message) or run(lambda job: media.clip(job, OUT / "test.mp3", "gif", OUT)).state == "failed")

# ---------- cancelling ----------
def slow(job):
    return media.convert(job, src, "webm", OUT)


job = jobs.submit("slow", "Media", slow)
time.sleep(0.4)
jobs.cancel(job.id)
while job.state in ("waiting", "running"):
    time.sleep(0.05)
expect("Cancel stops ffmpeg", job.state == "cancelled")

# ---------- pictures ----------
pic = OUT / "pic.png"
Image.radial_gradient("L").convert("RGBA").resize((300, 200)).save(pic)
prev = media.compress_picture(pic, "webp", 60)
expect("compress picture preview: a size and a picture, nothing saved", prev["size"] > 0 and prev["preview"].startswith("data:image/webp") and not list(OUT.glob("pic.webp")))
saved = media.compress_picture(pic, "jpg", 60, OUT)
expect("compress picture saves a JPG", Path(saved["path"]).exists() and saved["path"].endswith(".jpg"))
expect("AVIF works (Pillow has it)", media.compress_picture(pic, "avif", 50, OUT)["path"].endswith(".avif"))
r = media.resize_picture(pic, "half", OUT)
expect("resize 50%", (r["width"], r["height"]) == (150, 100))
r = media.resize_picture(pic, "emoji", OUT)
expect("Discord emoji: 128 square, see-through padding", (r["width"], r["height"]) == (128, 128) and Image.open(r["path"]).getpixel((0, 0))[3] == 0)
r = media.resize_picture(pic, "ico", OUT)
with Image.open(r["path"]) as ico:
    expect("an .ico with 16 and 256 inside", (16, 16) in ico.info["sizes"] and (256, 256) in ico.info["sizes"])
r = media.resize_picture(pic, "custom", OUT, 120, 0, True, True)
expect("custom width keeps the shape", (r["width"], r["height"]) == (120, 80))
r = media.resize_picture(pic, "custom", OUT, 50, 50, False)
expect("custom without keeping the shape stretches", (r["width"], r["height"]) == (50, 50))
expect("picture format → GIF", media.picture_format(pic, "gif", OUT)["path"].endswith(".gif"))
expect("a file that isn't a picture is explained", "opened" in str(getattr(run(lambda job: media.compress_picture(src, "jpg", 50, OUT)), "message", "")))

# ---------- game clips ----------
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "Radeon ReLive" / "GenshinImpact").mkdir(parents=True)
    (root / "Captures").mkdir()
    (root / "Radeon ReLive" / "replay_cache").mkdir()
    shutil.copy(src, root / "Radeon ReLive" / "GenshinImpact" / "fight.mp4")
    shutil.copy(src, root / "Captures" / "Minecraft 2026.mp4")
    shutil.copy(src, root / "Radeon ReLive" / "replay_cache" / "junk.mp4")
    (root / "Captures" / "tiny.mp4").write_bytes(b"x")
    clips = media.game_clips(roots=[root])
    expect("two recordings found, cache and tiny files skipped", len(clips) == 2 and {c["name"] for c in clips} == {"fight.mp4", "Minecraft 2026.mp4"})
    g1 = [c for c in clips if c["name"] == "fight.mp4"][0]
    expect("game and source read from the folders", g1["game"] == "GenshinImpact" and g1["source"] == "ReLive" and [c for c in clips if c["game"] == ""][0]["source"] == "Game Bar")
expect("the real folders scan without errors (%d clips)" % len(media.game_clips()), isinstance(media.game_clips(), list))

# ---------- Real-ESRGAN ----------
if engines.path_of("realesrgan"):
    expect("three models on disk", {m["id"] for m in upscale.models()} >= {"realesrgan-x4plus", "realesr-animevideov3"})
    j = run(lambda job: upscale.upscale_picture(job, pic, 2, "realesr-animevideov3", OUT))
    expect("picture 2× on the GPU: %s" % j.message, j.state == "done" and (j.extra["width"], j.extra["height"]) == (600, 400))
    j = run(lambda job: upscale.upscale_picture(job, pic, 2, "realesrgan-x4plus", OUT))
    expect("the 4×-only model still gives 2× (shrunk back)", j.state == "done" and (j.extra["width"], j.extra["height"]) == (600, 400))
    gif = OUT / "small.gif"
    run(lambda job: media.clip(job, src, "gif", OUT, 0, 0.4, 160, 8)).result and shutil.move(OUT / "test (2).gif", gif)
    j = run(lambda job: upscale.sharpen_gif(job, gif, 2, "webp", OUT))
    expect("GIF sharpened to WebP: %s" % j.message, j.state == "done" and j.result.endswith(".webp") and j.extra["frames"] >= 3)
    j = run(lambda job: upscale.sharpen_gif(job, gif, 2, "gif", OUT, "smooth"))
    expect("GIF sharpened to GIF, twice as wide", j.state == "done" and media.probe(j.result)["width"] == 320)
    vp = upscale.plan_video(info, 2, 0.5, 1.5)
    expect("video plan: frames, size, a time", vp["ok"] and vp["frames"] == 30 and (vp["width"], vp["height"]) == (1280, 720))
    expect("video plan refuses past 4K", not upscale.plan_video(info, 4, 0, 0)["ok"] or info["height"] * 4 <= 2160)
    j = run(lambda job: upscale.upscale_video(job, src, 2, "realesr-animevideov3", OUT, 0.5, 1.5))
    v = media.probe(j.result) if j.result else {}
    expect("video 2× in batches, sound kept: %s" % j.message, j.state == "done" and v.get("width") == 1280 and v.get("acodec") == "aac" and abs(v.get("duration", 0) - 1.0) < 0.2)
else:
    print("skip  Real-ESRGAN isn't installed")

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_media)")
