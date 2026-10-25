"""Game artwork in HD (his ask, 15 Oct): small covers and banners are upscaled once with Real-ESRGAN, in the background,
on the graphics card, and kept in %LOCALAPPDATA%\\Toolbelt\\art\\hd. The originals are never changed.

- Still pictures: a banner narrower than 2560 px (Steam's are 1920 × 620) becomes up to 3840 px wide; a cover narrower
  than 600 px (Steam's small ones are 300 × 450) becomes 600 × 900. realesrgan-x4plus, 4×, then sized.
- Animated (his follow-up, 15 Oct: "also videos and GIFs"): a GIF or a video banner narrower than 1280 px, or
  cover narrower than 400 px, is sharpened frame by frame with the animation model (realesr-animevideov3) at 2-4×,
  towards 1920 px (banner) / 600 px (cover). GIFs come back as animated WebP (better colours, smaller), videos as MP4.
  GIFs up to 30 s and 600 frames; videos up to 60 s and 3 billion output pixels (every frame goes through the card).
- Still pictures go first (seconds); animated ones after (a minute or more each).
- Each HD copy is named after the original's path, size and date, so new art from a link or a file gets its own HD
  copy and old ones are simply no longer used.
"""
import hashlib
import itertools
import os
import queue
import shutil
import tempfile
import threading
import time
from pathlib import Path

from PIL import Image

import engines

HD_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Toolbelt" / "art" / "hd"
TARGET = {"banner": (2560, 3840), "cover": (600, 600)}          # still: (upscale when narrower than, make it this wide at most)
ANIM = {"banner": (1280, 1920), "cover": (400, 600)}            # animated: (upscale when narrower than, aim for this wide)
MODEL = "realesrgan-x4plus"                                     # painted / rendered key art: the general model looks best
ANIM_MODEL = "realesr-animevideov3"
EXT = {"pic": ".jpg", "gif": ".webp", "video": ".mp4"}
MAX_SECONDS, MAX_FRAMES = 30, 600                               # GIFs (what the step-6 GIF sharpener accepts)
VIDEO_SECONDS, VIDEO_WORK = 60, 3_000_000_000                    # videos: up to a minute and 3 billion output pixels


def hd_file(path, which, kind="pic"):
    """Where the HD copy of this picture / GIF / video lives (it may not be there yet)."""
    try:
        st = Path(path).stat()
    except OSError:
        return None
    key = hashlib.sha1(("%s|%d|%d|%s" % (str(path).lower(), st.st_size, int(st.st_mtime), which)).encode("utf-8")).hexdigest()[:20]
    return HD_DIR / ("%s-%s%s" % (which, key, EXT.get(kind, ".jpg")))


def _anim_facts(path, kind):
    """(width, height, seconds, frames) of a GIF or a video, or None."""
    try:
        if kind == "gif":
            with Image.open(path) as img:
                frames = getattr(img, "n_frames", 1)
                ms = 0
                for i in range(min(frames, MAX_FRAMES + 1)):
                    img.seek(i)
                    ms += img.info.get("duration", 100) or 100
                return img.width, img.height, ms / 1000, frames
        import media
        info = media.probe(path)
        return info["width"], info["height"], info["duration"] or 0, int((info["duration"] or 0) * (info["fps"] or 30))
    except Exception:
        return None


def scale_for(width, which):
    """2, 3 or 4: the one that brings it closest to the animated target width."""
    return max(2, min(4, int(round(ANIM[which][1] / max(1, width)))))


def needs(path, which, kind="pic"):
    """True when this one is small enough that the full-screen library would show it soft (and it's doable)."""
    if not path or which not in TARGET or kind not in EXT:
        return False
    if kind == "pic":
        try:
            with Image.open(path) as img:
                return img.width < TARGET[which][0] and img.width * img.height <= 3000 * 3000
        except Exception:
            return False
    facts = _anim_facts(path, kind)
    if not facts:
        return False
    width, height, seconds, frames = facts
    s = scale_for(width, which)
    if not (0 < width < ANIM[which][0] and frames > 0 and height * s <= 2160):
        return False
    if kind == "gif":                                           # the GIF sharpener's own limits (step 6)
        return seconds <= MAX_SECONDS and frames <= MAX_FRAMES
    # a video: up to a minute, as long as the work stays sane (frames × output pixels; his 60 fps Minecraft loop,
    # 1892 frames at 1700 × 548, is 1.8 billion: about two minutes)
    return seconds <= VIDEO_SECONDS and frames * width * s * height * s <= VIDEO_WORK


def best(path, which, kind="pic"):
    """The HD copy when it's ready, else the original."""
    if kind in EXT and path:
        hd = hd_file(path, which, kind)
        if hd and hd.exists():
            return str(hd)
    return path


def is_hd(path, which, kind="pic"):
    return bool(path) and best(path, which, kind) != path


def available(kind="pic"):
    exe = engines.path_of("realesrgan")
    if not exe:
        return False
    models = exe.parent / "models"
    return (models / (MODEL + ".bin")).exists() if kind == "pic" else any(models.glob(ANIM_MODEL + "*.bin"))


class _Quiet:
    """Stands in for a job: the step-6 upscalers report progress and check for Cancel; the progress goes to `tell`."""
    def __init__(self, tell=None):
        self.extra = {}
        self._tell = tell

    def report(self, percent, message=""):
        if self._tell:
            self._tell(float(percent), message)

    def check(self):
        pass


def make(path, which, kind="pic", timeout=300, progress=None):
    """Upscales one picture / GIF / video and sizes it to the target. Returns the HD file. Raises on failure.
    progress(percent, message) is told how far it is (his ask, 15 Oct: "making HD" takes long, show a bar)."""
    import re
    import subprocess
    tell = progress or (lambda pct, msg="": None)
    exe = engines.path_of("realesrgan")
    if not exe:
        raise RuntimeError("Real-ESRGAN isn't installed.")
    dest = hd_file(path, which, kind)
    HD_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.stem + ".part" + dest.suffix)
    if kind in ("gif", "video"):
        import upscale
        width = _anim_facts(path, kind)[0]
        work = HD_DIR / "work" / dest.stem                     # a video's finished batches stay here across restarts
        with tempfile.TemporaryDirectory(prefix="toolbelt-hd-") as tmp:
            if kind == "gif":
                out = upscale.sharpen_gif(_Quiet(tell), path, scale_for(width, which), "webp", tmp)
            else:
                out = upscale.upscale_video(_Quiet(tell), path, scale_for(width, which), ANIM_MODEL, tmp, work_dir=work)
            shutil.move(out, part)
        os.replace(part, dest)
        shutil.rmtree(work, ignore_errors=True)
        return dest
    with Image.open(path) as src:
        img = src.convert("RGB")
    with tempfile.TemporaryDirectory(prefix="toolbelt-hd-") as tmp:
        inp, out = Path(tmp) / "in.png", Path(tmp) / "out.png"
        img.save(inp, "PNG")
        tell(2, "Sharpening on the graphics card")
        proc = subprocess.Popen([str(exe), "-m", str(exe.parent / "models"), "-i", str(inp), "-o", str(out), "-n", MODEL, "-s", "4", "-f", "png"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=0x08000000)
        tail, started = [], time.time()
        for line in proc.stderr:                               # Real-ESRGAN prints "12.50%" as it goes
            tail = (tail + [line.strip()])[-4:]
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                tell(2 + 93 * min(1.0, float(m.group(1)) / 100), "Sharpening on the graphics card")
            if time.time() - started > timeout:
                proc.kill()
                break
        proc.wait()
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError("Real-ESRGAN stopped: " + (tail[-1][:160] if tail else "unknown error"))
        tell(96, "Saving")
        with Image.open(out) as big:
            big = big.convert("RGB")
            width = min(TARGET[which][1], big.width)
            if big.width != width:
                big = big.resize((width, round(big.height * width / big.width)), Image.Resampling.LANCZOS)
            big.save(part, "JPEG", quality=92, optimize=True, progressive=True)
    os.replace(part, dest)
    return dest


class Worker:
    """One at a time, in the background; still pictures before animated ones. on_done(game_key, which) after each."""

    def __init__(self, on_done=None):
        self._q = queue.PriorityQueue()
        self._seq = itertools.count()
        self._queued, self._failed = set(), set()
        self._on_done = on_done
        self._thread = None
        self.busy = ""
        self.now = {}                                          # what is being sharpened right now, and how far it is
        self._keys = {}                                        # ident -> game key, for the waiting list

    def want(self, game_key, path, which, kind="pic"):
        """Queues it when it's small, not done yet, not already waiting and not failed before. Returns True if queued."""
        if not path or kind not in EXT or not available(kind):
            return False
        ident = (str(path).lower(), which)
        if ident in self._queued or ident in self._failed or is_hd(path, which, kind) or not needs(path, which, kind):
            return False
        self._queued.add(ident)
        self._keys[ident] = game_key
        self._q.put((0 if kind == "pic" else 1, next(self._seq), (game_key, path, which, kind, ident)))
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return True

    def pending(self):
        return len(self._queued)

    def waiting(self, path, which):
        return bool(path) and (str(path).lower(), which) in self._queued

    def status(self):
        """For the page's progress bar: {"now": {key, which, kind, progress, message, seconds}, "waiting": [game keys]}."""
        now = dict(self.now)
        if now:
            now["seconds"] = int(time.time() - now.pop("started", time.time()))
        current = (now.get("key"), now.get("which"))
        waiting = [self._keys.get(i, "") for i in self._queued if (self._keys.get(i), i[1]) != current]
        return {"now": now, "waiting": waiting}

    def _run(self):
        while True:
            try:
                _prio, _n, (game_key, path, which, kind, ident) = self._q.get(timeout=5)
            except queue.Empty:
                return
            self.busy = game_key
            self.now = {"key": game_key, "which": which, "kind": kind, "progress": 0.0, "message": "Starting", "started": time.time()}

            def tell(pct, message=""):
                self.now["progress"] = round(max(self.now.get("progress", 0), min(100.0, float(pct))), 1)
                if message:
                    self.now["message"] = message
            try:
                make(path, which, kind, timeout=1800 if kind != "pic" else 300, progress=tell)
                ok = True
            except Exception:
                self._failed.add(ident)
                ok = False
            self._queued.discard(ident)
            self.busy, self.now = "", {}
            if ok and self._on_done:
                try:
                    self._on_done(game_key, which)
                except Exception:
                    pass
            time.sleep(0.2)
