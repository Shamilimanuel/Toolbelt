"""Cut-outs: removes a picture's background on this PC with the BiRefNet model (pictures never leave the PC).

Runs on the graphics card through DirectML when it can (his RX 9060 XT), else on the processor.
The model's recipe is BiRefNet's own, as rembg uses it: the picture is resized to 1024 × 1024, colours are
normalised with the usual ImageNet values, the model gives a mask, which is sized back up and used as see-through.
Afterwards the cut-out can get a new background, a sticker outline and shadow, and Discord sizes.
"""
import io
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

import engines

SIZE = 1024
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MAX_SIDE = 8000                                   # bigger pictures are scaled down first (the mask is 1024 anyway)
DISCORD = {"emoji": (128, 256 * 1024), "sticker": (320, 512 * 1024), "icon": (512, None)}

_session = None
_device = ""
_lock = threading.Lock()


class CutError(Exception):
    pass


def session():
    """Loads the model once (a few seconds), on the graphics card if possible."""
    global _session, _device
    with _lock:
        if _session is None:
            model = engines.path_of("birefnet")
            if not model:
                raise CutError("Install the BiRefNet model first (the button on this page, or Engines).")
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.log_severity_level = 3
            try:
                _session = ort.InferenceSession(str(model), options, providers=["DmlExecutionProvider", "CPUExecutionProvider"])
            except Exception:
                _session = ort.InferenceSession(str(model), options, providers=["CPUExecutionProvider"])
            _device = "graphics card" if "DmlExecutionProvider" in _session.get_providers() else "processor"
        return _session


def device():
    return _device


def open_picture(source):
    """A path or bytes -> an RGB picture the right way up (phones store rotation separately)."""
    try:
        img = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
        img.load()
    except Exception:
        raise CutError("That isn't a picture Toolbelt can read (try PNG, JPG or WebP).")
    img = ImageOps.exif_transpose(img)
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")


def prepare(img):
    """The model's input: 1 × 3 × 1024 × 1024, normalised."""
    small = img.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    arr = np.asarray(small, dtype=np.float32)
    arr = arr / max(float(arr.max()), 1e-6)
    arr = (arr - MEAN) / STD
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def to_mask(output, size):
    """The model's raw answer -> a mask the size of the picture (0 = background, 255 = subject)."""
    pred = 1 / (1 + np.exp(-output[0, 0]))
    lo, hi = float(pred.min()), float(pred.max())
    pred = (pred - lo) / (hi - lo) if hi > lo else np.zeros_like(pred)
    mask = Image.fromarray((pred * 255).astype("uint8"), mode="L")
    return mask.resize(size, Image.Resampling.LANCZOS)


_cpu_session = None


def cpu_session():
    """The same model on the processor: the fallback when the graphics card is full (a game running, 15 Oct)."""
    global _cpu_session
    with _lock:
        if _cpu_session is None:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.log_severity_level = 3
            _cpu_session = ort.InferenceSession(str(engines.path_of("birefnet")), options, providers=["CPUExecutionProvider"])
        return _cpu_session


def cpu_run(feed):
    """The model on the processor, in a fresh helper process: after DirectML ran out of memory, this process often can't
    load a second copy ("bad allocation", 15 Oct), a new one always can."""
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory(prefix="toolbelt-cut-") as tmp:
        inp, out = Path(tmp) / "in.npy", Path(tmp) / "out.npy"
        np.save(inp, feed)
        done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--cpu", str(inp), str(out)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600, creationflags=0x08000000)
        if done.returncode != 0 or not out.exists():
            raise CutError("The processor couldn't do it either: " + ((done.stderr or "").strip().splitlines() or ["unknown error"])[-1][:160])
        return np.load(out)


def gpu_full(error):
    """DirectML's "not enough memory" (0x8007000E): the graphics card is busy, not broken."""
    text = str(error)
    return "8007000E" in text or "Not enough memory" in text or "E_OUTOFMEMORY" in text


def cut(img):
    """Picture -> (RGBA cut-out, seconds, device). When the graphics card is full, it runs on the processor instead."""
    s = session()
    t = time.time()
    feed = prepare(img)
    try:
        out = s.run(None, {s.get_inputs()[0].name: feed})[0]
        used = device()
    except Exception as error:
        if not gpu_full(error) or device() != "graphics card":
            raise
        try:                                                 # DirectML's first run after loading often says "full" once
            out = s.run(None, {s.get_inputs()[0].name: feed})[0]   # and works the second time (seen 15 Oct): try again
            used = device()
        except Exception as again:
            if not gpu_full(again):
                raise
            out = cpu_run(feed)                              # really full (a game holds the card): the processor, ~20-40 s
            used = "processor (the graphics card was full)"
    mask = to_mask(out, img.size)
    if img.mode == "RGBA":                                   # keep see-through parts the picture already had
        mask = ImageChops.multiply(mask, img.getchannel("A"))
    rgba = img.convert("RGB").convert("RGBA")
    rgba.putalpha(mask)
    return rgba, time.time() - t, used


# ---------- what goes behind it ----------

def cover(img, size):
    """Scales and crops a picture to fill size exactly (like a desktop wallpaper)."""
    return ImageOps.fit(img.convert("RGB"), size, Image.Resampling.LANCZOS)


def compose(cutout, original, background="none", colour="#FFFFFF", picture=None):
    """The cut-out on its new background: none (see-through), white, colour, blur (the original, blurred) or picture."""
    w, h = cutout.size
    if background == "none":
        return cutout.copy()
    if background == "white":
        base = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    elif background == "colour":
        try:
            rgb = tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
        except (ValueError, TypeError):
            rgb = (255, 255, 255)
        base = Image.new("RGBA", (w, h), rgb + (255,))
    elif background == "blur":
        base = blur_behind(original, cutout.getchannel("A")).convert("RGBA")
    elif background == "picture" and picture is not None:
        base = cover(picture, (w, h)).convert("RGBA")
    else:
        return cutout.copy()
    base.alpha_composite(cutout)
    return base


def _box(arr, r):
    """A fast box blur along both axes (three of these in a row look like a Gaussian blur)."""
    for axis in (0, 1):
        pad = [(0, 0)] * arr.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(arr, pad, mode="edge"), axis=axis)
        n = arr.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        arr = (hi - lo) / (2 * r + 1)
    return arr


def blur_behind(original, alpha):
    """Portrait mode: blurs only the background. The subject's own colours are left out of the blur (a "normalised"
    blur: each spot is the average of the background around it), so no glow of the subject leaks around it."""
    w, h = original.size
    scale = max(1, max(w, h) // 900)                       # blur a smaller copy: same look, much faster
    sw, sh = max(1, w // scale), max(1, h // scale)
    img = np.asarray(original.convert("RGB").resize((sw, sh), Image.Resampling.BILINEAR), dtype=np.float32) / 255
    keep = 1 - np.asarray(alpha.resize((sw, sh), Image.Resampling.BILINEAR), dtype=np.float32) / 255
    keep = np.clip((keep - 0.1) / 0.9, 0, 1)                # only clearly-background pixels count
    r = max(2, int(max(sw, sh) / 90))
    num, den = img * keep[..., None], keep
    for _ in range(3):
        num, den = _box(num, r), _box(den, r)
    filled = num / np.maximum(den[..., None], 1e-4)
    # deep inside a large subject no background is near: fall back to a plain wide blur there
    far = den < 0.02
    if far.any():
        wide = img
        for _ in range(3):
            wide = _box(wide, r * 4)
        filled[far] = wide[far]
    out = Image.fromarray((np.clip(filled, 0, 1) * 255).astype("uint8"), "RGB")
    return out.resize((w, h), Image.Resampling.BICUBIC)


def sticker(cutout, outline=0, shadow=False):
    """A white outline around the subject (outline = width in pixels) and/or a soft drop shadow."""
    if not outline and not shadow:
        return cutout
    pad = outline + (24 if shadow else 0) + 2
    w, h = cutout.size
    canvas = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    alpha = Image.new("L", canvas.size, 0)
    alpha.paste(cutout.getchannel("A"), (pad, pad))
    if outline:
        grown = alpha.filter(ImageFilter.MaxFilter(outline * 2 + 1)).point(lambda v: 255 if v > 24 else 0).filter(ImageFilter.GaussianBlur(1))
    else:
        grown = alpha
    if shadow:
        shade = grown.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.45))
        canvas.paste(Image.new("RGBA", canvas.size, (0, 0, 0, 255)), (8, 10), shade)
    if outline:
        canvas.alpha_composite(Image.merge("RGBA", (Image.new("L", canvas.size, 255),) * 3 + (grown,)))
    canvas.alpha_composite(cutout, (pad, pad))
    return canvas.crop(canvas.getbbox() or (0, 0) + canvas.size)


def trim(img, margin=0.04):
    """Crops away empty see-through space around the subject, keeping a small margin."""
    box = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        return img
    m = int(max(box[2] - box[0], box[3] - box[1]) * margin)
    return img.crop((max(0, box[0] - m), max(0, box[1] - m), min(img.width, box[2] + m), min(img.height, box[3] + m)))


def square(img, side):
    """Fits the picture into a see-through square of side × side."""
    fitted = img.copy()
    fitted.thumbnail((side, side), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(fitted, ((side - fitted.width) // 2, (side - fitted.height) // 2))
    return canvas


def discord_png(img, kind):
    """PNG bytes for a Discord emoji / sticker / server icon, kept under Discord's size limit."""
    side, limit = DISCORD[kind]
    out = square(trim(img), side)
    data = png_bytes(out)
    if limit and len(data) > limit:                          # rare at these sizes: fewer colours make it smaller
        data = png_bytes(out.quantize(256, method=Image.Quantize.FASTOCTREE).convert("RGBA"))
    return data


def png_bytes(img, optimize=True):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=optimize)
    return buf.getvalue()


def preview(img, side=1100, checker=False):
    """A small JPEG/PNG data link for the page (the full-size picture stays in Python)."""
    import base64
    small = img.copy()
    small.thumbnail((side, side), Image.Resampling.LANCZOS)
    if small.mode == "RGBA" and not checker:
        return "data:image/png;base64," + base64.b64encode(png_bytes(small, optimize=False)).decode("ascii")
    buf = io.BytesIO()
    small.convert("RGB").save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def free_path(folder, stem, ext=".png"):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target, n = folder / (stem + ext), 2
    while target.exists():
        target = folder / ("%s (%d)%s" % (stem, n, ext))
        n += 1
    return target


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--cpu":                # the helper: one run on the processor (see cpu_run)
        session_cpu = cpu_session()
        np.save(sys.argv[3], session_cpu.run(None, {session_cpu.get_inputs()[0].name: np.load(sys.argv[2])})[0])
