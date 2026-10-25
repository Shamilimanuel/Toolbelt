"""Tests for gameart.py: which game pictures get upscaled, where the HD copies go, and one real 4× upscale on the
graphics card through the background worker (in a temporary folder: his own HD copies are not touched)."""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from PIL import Image, ImageDraw                              # noqa: E402

import gameart                                                # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def size(path):
    with Image.open(path) as img:
        return img.size


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    gameart.HD_DIR = tmp / "hd"
    small_cover, big_cover, banner, big_banner = tmp / "cover-small.jpg", tmp / "cover-big.jpg", tmp / "banner-small.jpg", tmp / "banner-big.jpg"
    for path, wh in ((small_cover, (150, 225)), (big_cover, (600, 900)), (banner, (480, 155)), (big_banner, (2600, 840))):
        img = Image.new("RGB", wh, (40, 90, 160))
        d = ImageDraw.Draw(img)
        d.ellipse((wh[0] * .3, wh[1] * .2, wh[0] * .7, wh[1] * .8), fill=(230, 180, 60))
        d.line((0, 0, wh[0], wh[1]), fill=(255, 255, 255), width=3)
        img.save(path, quality=90)
    expect("a small cover and a small banner need HD", gameart.needs(small_cover, "cover") and gameart.needs(banner, "banner"))
    expect("big enough ones are left alone (600 px cover, 2600 px banner)", not gameart.needs(big_cover, "cover") and not gameart.needs(big_banner, "banner"))
    expect("other kinds of file are left alone", not gameart.needs(small_cover, "cover", "audio") and not gameart.needs(banner, "logo", "pic"))
    expect("a missing file is never queued", not gameart.needs(tmp / "nope.jpg", "cover"))
    first = gameart.hd_file(banner, "banner")
    expect("the HD copy has a stable name in AppData\\Toolbelt\\art\\hd", first == gameart.hd_file(banner, "banner") and first.parent == gameart.HD_DIR)
    expect("until it's made, the original is used", gameart.best(banner, "banner") == banner and not gameart.is_hd(banner, "banner"))
    os.utime(banner, (time.time() + 5, time.time() + 5))
    expect("a changed picture gets a new HD name (an old copy is never shown for new art)", gameart.hd_file(banner, "banner") != first)

    if gameart.available():
        done = []
        ev = threading.Event()
        worker = gameart.Worker(on_done=lambda key, which: (done.append((key, which)), ev.set() if len(done) == 2 else None))
        t0 = time.time()
        queued = [worker.want("steam:1", small_cover, "cover"), worker.want("steam:1", banner, "banner")]
        expect("the worker takes both, once (asking again doesn't queue twice)", queued == [True, True] and not worker.want("steam:1", banner, "banner") and worker.waiting(banner, "banner"))
        ev.wait(240)
        print("      (two real 4× upscales in the background: %.1f s)" % (time.time() - t0))
        expect("both are done and the page is told (games_hd)", sorted(done) == [("steam:1", "banner"), ("steam:1", "cover")])
        expect("cover: 150 × 225 → 600 × 900", size(gameart.best(small_cover, "cover")) == (600, 900))
        expect("banner: 480 × 155 → 1920 × 620 (4×, under the 3840 cap)", size(gameart.best(banner, "banner")) == (1920, 620))
        expect("now the HD copies are used, and nothing is queued again", gameart.is_hd(small_cover, "cover") and gameart.is_hd(banner, "banner") and not worker.want("steam:1", banner, "banner"))
        expect("the originals are untouched", size(small_cover) == (150, 225) and size(banner) == (480, 155))
        expect("no half-written files are left", not list(gameart.HD_DIR.glob("*.part")))
        # the progress bar (his ask): make() says how far it is; the worker passes it on with what's waiting
        seen = []
        extra = tmp / "progress-cover.jpg"
        Image.new("RGB", (200, 300), (90, 30, 120)).save(extra)
        gameart.make(extra, "cover", "pic", progress=lambda pct, msg="": seen.append(pct))
        expect("sharpening reports how far it is (%d steps, up to %d%%)" % (len(seen), max(seen) if seen else 0), len(seen) >= 3 and max(seen) >= 95 and seen == sorted(seen))
        w3 = gameart.Worker()
        snapshots = []
        banner2 = tmp / "progress-banner.jpg"
        Image.new("RGB", (640, 207), (20, 90, 60)).save(banner2)
        w3.want("steam:3", banner2, "banner")
        for _ in range(200):
            st = w3.status()
            if st["now"]:
                snapshots.append(st["now"]["progress"])
            if not w3.pending():
                break
            time.sleep(0.05)
        expect("the worker's status says which game and how far (%s)" % snapshots[-3:], snapshots and max(snapshots) > 0)

        # animated (his follow-up): a small GIF cover and a short video banner, sharpened frame by frame
        import subprocess
        import engines as eng
        gif, vid, long_vid = tmp / "anim-cover.gif", tmp / "anim-banner.mp4", tmp / "anim-long.mp4"
        frames = [Image.new("RGB", (120, 180), (30 + i * 30, 60, 140)) for i in range(6)]
        for i, f in enumerate(frames):
            ImageDraw.Draw(f).ellipse((20 + i * 8, 50, 70 + i * 8, 100), fill=(240, 200, 80))
        frames[0].save(gif, save_all=True, append_images=frames[1:], duration=120, loop=0)
        ff = str(eng.path_of("ffmpeg"))
        for path, secs in ((vid, 1), (long_vid, 70)):
            subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15", "-t", str(secs),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True, creationflags=0x08000000)
        expect("a small GIF cover and a short video banner need HD", gameart.needs(gif, "cover", "gif") and gameart.needs(vid, "banner", "video"))
        expect("a video over a minute is left alone (every frame would take ages)", not gameart.needs(long_vid, "banner", "video"))
        expect("the step picks the × that gets closest (GIF 120 px → 4×, video 320 px → 4×, 800 px banner → 2×)",
               gameart.scale_for(120, "cover") == 4 and gameart.scale_for(320, "banner") == 4 and gameart.scale_for(800, "banner") == 2)
        done.clear()
        ev2 = threading.Event()
        worker2 = gameart.Worker(on_done=lambda key, which: (done.append((key, which)), ev2.set() if len(done) == 2 else None))
        t0 = time.time()
        worker2.want("steam:2", vid, "banner", "video")
        worker2.want("steam:2", gif, "cover", "gif")
        ev2.wait(600)
        print("      (a GIF and a video sharpened in the background: %.1f s)" % (time.time() - t0))
        hd_gif, hd_vid = gameart.best(gif, "cover", "gif"), gameart.best(vid, "banner", "video")
        expect("both done and the page told", sorted(done) == [("steam:2", "banner"), ("steam:2", "cover")])
        with Image.open(hd_gif) as anim:
            expect("the GIF came back as an animated WebP, 4× (480 × 720), all 6 frames", hd_gif.endswith(".webp") and anim.size == (480, 720) and getattr(anim, "n_frames", 1) == 6)
        import media
        info = media.probe(hd_vid)
        expect("the video came back as an MP4, 4× (1280 × 720)", hd_vid.endswith(".mp4") and (info["width"], info["height"]) == (1280, 720))
        # a longer video (his backgrounds never finished, 15 Oct): 210 frames froze Real-ESRGAN at ~48 before the fix;
        # stopped after its first batch of 96 (as when Toolbelt quits) it must carry on from there, not from zero
        import upscale
        long_bg = tmp / "anim-long-banner.mp4"
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=30", "-t", "7",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(long_bg)], check=True, creationflags=0x08000000)
        work = gameart.HD_DIR / "work" / gameart.hd_file(long_bg, "banner", "video").stem
        first = {"error": None}

        def quit_in_batch_two(pct, msg=""):                       # Toolbelt quits while the second batch is being upscaled
            if msg.startswith("Upscaling frames 97"):
                upscale.stop_all()
        t0 = time.time()
        try:
            gameart.make(long_bg, "banner", "video", timeout=600, progress=quit_in_batch_two)
        except Exception as error:
            first["error"] = error
        kept = sorted(p.name for p in work.glob("part*.mkv"))
        expect("stopping halfway keeps the finished batch (%s; first run: %s)" % (kept, str(first["error"])[:120]), first["error"] is not None and kept[:1] == ["part0000.mkv"])
        steps = []
        out = gameart.make(long_bg, "banner", "video", timeout=600, progress=lambda pct, msg="": steps.append(msg))
        print("      (210-frame video: %.1f s in all)" % (time.time() - t0))
        reading = [s for s in steps if s.startswith("Reading frames")]
        expect("the next run carries on from frame 97, not from 1 (%s)" % (reading[:1]), reading and reading[0].startswith("Reading frames 97"))
        info = media.probe(out)
        expect("…and the whole video comes out (all 210 frames, 640 × 360), its batches cleaned up", (info["width"], info["height"]) == (640, 360)
               and abs(info["duration"] - 7) < 0.3 and not work.exists())
    else:
        print("      (Real-ESRGAN isn't installed here: the real upscale was skipped)")
        expect("without Real-ESRGAN nothing is queued", not gameart.Worker().want("k", small_cover, "cover"))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_gameart)")
