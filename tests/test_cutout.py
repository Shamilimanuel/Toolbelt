"""Tests for step 3, cut-outs: backgrounds, sticker outline, the halo-free blur, Discord sizes, and, when the
BiRefNet model is installed, one real cut-out on the graphics card (a drawn cat on a drawn landscape)."""
import io
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import numpy as np
from PIL import Image, ImageDraw

import cutout
import engines
from main import safe_stem

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


def scene(w=800, h=500):
    """A red disk (the subject) on a blue sky over green grass, plus its perfect mask."""
    img = Image.new("RGB", (w, h), (120, 180, 235))
    d = ImageDraw.Draw(img)
    d.rectangle((0, int(h * .7), w, h), fill=(90, 150, 80))
    d.ellipse((w * .35, h * .2, w * .65, h * .8), fill=(220, 40, 40))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((w * .35, h * .2, w * .65, h * .8), fill=255)
    cut = img.convert("RGBA")
    cut.putalpha(mask)
    return img, cut


img, cut = scene()

# ---------- preparing for the model ----------
x = cutout.prepare(img)
expect("model input is 1 × 3 × 1024 × 1024 float32", x.shape == (1, 3, 1024, 1024) and x.dtype == np.float32)
expect("colours are normalised around 0", -3 < float(x.mean()) < 3)
raw = np.full((1, 1, 1024, 1024), -8.0, dtype=np.float32)
raw[0, 0, 300:700, 300:700] = 8.0
m = cutout.to_mask(raw, (400, 250))
expect("the mask comes back at the picture's size", m.size == (400, 250))
expect("inside is solid, outside see-through", m.getpixel((200, 125)) > 250 and m.getpixel((5, 5)) < 5)
try:
    cutout.open_picture(b"definitely not a picture")
    expect("a non-picture is refused", False)
except cutout.CutError as e:
    expect("a non-picture is refused with a reason", "picture" in str(e))
big = io.BytesIO()
Image.new("RGB", (9000, 300), "white").save(big, "PNG")
expect("huge pictures are scaled down to 8000 px", max(cutout.open_picture(big.getvalue()).size) == 8000)

# ---------- backgrounds ----------
expect("see-through keeps the alpha", cutout.compose(cut, img, "none").getpixel((10, 10))[3] == 0)
expect("white fills the background", cutout.compose(cut, img, "white").getpixel((10, 10)) == (255, 255, 255, 255))
expect("colour fills with that colour", cutout.compose(cut, img, "colour", "#5B6CFF").getpixel((10, 10))[:3] == (91, 108, 255))
expect("the subject stays on top", cutout.compose(cut, img, "white").getpixel((400, 250))[:3] == (220, 40, 40))
pic = Image.new("RGB", (300, 300), (10, 200, 10))
expect("a picture background covers it all", cutout.compose(cut, img, "picture", picture=pic).getpixel((5, 5))[:3] == (10, 200, 10))
blur = cutout.compose(cut, img, "blur")
near = blur.getpixel((int(800 * .35) - 12, 250))[:3]
expect("blur: no red glow just outside the subject (portrait mode)", near[0] < 160 and near[2] > near[0])
expect("blur: the sky stays sky-coloured", abs(blur.getpixel((40, 40))[2] - 235) < 20)

# ---------- sticker and Discord ----------
st = cutout.sticker(cut, 10, True)
expect("a sticker is bigger than the subject (room for outline and shadow)", st.width > cutout.trim(cut, 0).width)
column = [st.getpixel((st.width // 2, y)) for y in range(st.height)]
first_solid = next(p for p in column if p[3] > 200)              # above it is only the shadow's soft edge
expect("the outline is white", min(first_solid[:3]) > 230)
expect("no outline, no shadow = unchanged", cutout.sticker(cut, 0, False) is cut)
for kind, (side, limit) in cutout.DISCORD.items():
    data = cutout.discord_png(st, kind)
    sized = Image.open(io.BytesIO(data))
    expect("%s is %d × %d and under Discord's limit" % (kind, side, side), sized.size == (side, side) and (not limit or len(data) <= limit))
t = cutout.trim(cut)
expect("trim crops to the subject with a small margin", t.width < 800 and t.width > 240)
expect("preview is a small data link", cutout.preview(cut, 300).startswith("data:image/png;base64,") and cutout.preview(img, 300).startswith("data:image/jpeg"))
with tempfile.TemporaryDirectory() as tmp:
    a = cutout.free_path(tmp, "cat - cut out")
    a.write_bytes(b"x")
    expect("an existing name gets (2)", cutout.free_path(tmp, "cat - cut out").name == "cat - cut out (2).png")
expect("names are made safe for files", safe_stem('a/b:c*?"<>|') == "a_b_c______" and safe_stem("   ") == "picture")

# ---------- the real model, on the graphics card ----------
if engines.path_of("birefnet"):
    cat = Image.new("RGB", (1200, 750), (127, 182, 232))
    d = ImageDraw.Draw(cat)
    d.rectangle((0, 520, 1200, 750), fill=(94, 140, 79))
    d.ellipse((960, 160, 1060, 260), fill=(255, 231, 163))
    d.ellipse((420, 400, 780, 700), fill=(232, 137, 58))                 # body
    d.ellipse((470, 180, 730, 440), fill=(232, 137, 58))                 # head
    d.polygon([(485, 260), (500, 120), (580, 200)], fill=(232, 137, 58))  # ears
    d.polygon([(715, 260), (700, 120), (620, 200)], fill=(232, 137, 58))
    d.ellipse((545, 280, 575, 325), fill=(42, 26, 16))
    d.ellipse((625, 280, 655, 325), fill=(42, 26, 16))
    d.ellipse((510, 500, 690, 690), fill=(247, 211, 168))
    t0 = time.time()
    out, secs, device = cutout.cut(cat)
    a = out.getchannel("A")
    print("      (real cut-out: %.1f s on the %s, %.1f s with loading)" % (secs, device, time.time() - t0))
    expect("real model: the cat is kept", a.getpixel((600, 300)) > 200 and a.getpixel((600, 600)) > 200)
    expect("real model: sky and grass are removed", a.getpixel((100, 100)) < 40 and a.getpixel((100, 700)) < 40)
    expect("real model: runs on the graphics card (or the processor when the card is full)", device in ("graphics card", "processor (the graphics card was full)"))
    expect("the 'card is full' error is recognised", cutout.gpu_full(RuntimeError("... 8007000E Not enough memory resources ...")) and not cutout.gpu_full(RuntimeError("other")))

    # a full graphics card (a game running) falls back to the processor instead of failing (seen in the full run, 15 Oct)
    from unittest import mock
    real = cutout.session()

    class FullCard:
        def get_inputs(self):
            return real.get_inputs()

        def run(self, *a, **k):
            raise RuntimeError("DmlFusedNode 8007000E Not enough memory resources are available to complete this operation.")
    with mock.patch.object(cutout, "session", return_value=FullCard()), mock.patch.object(cutout, "device", return_value="graphics card"):
        out2, secs2, device2 = cutout.cut(cat)
    print("      (processor fallback, in a helper process: %.1f s)" % secs2)
    expect("a full graphics card falls back to the processor, same result", device2.startswith("processor") and out2.getchannel("A").getpixel((600, 300)) > 200 and out2.getchannel("A").getpixel((100, 100)) < 40)

    class FlakyCard:                                          # DirectML's warm-up hiccup: "full" once, then fine (15 Oct)
        def __init__(self):
            self.calls = 0

        def get_inputs(self):
            return real.get_inputs()

        def run(self, *a, **k):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("8007000E Not enough memory resources are available to complete this operation.")
            return real.run(*a, **k)
    flaky = FlakyCard()
    with mock.patch.object(cutout, "session", return_value=flaky), mock.patch.object(cutout, "device", return_value="graphics card"):
        out3, _secs3, device3 = cutout.cut(cat)
    expect("a one-off 'full' on the card is tried again on the card (no slow fallback)", device3 == "graphics card" and flaky.calls == 2 and out3.getchannel("A").getpixel((600, 300)) > 200)
else:
    print("      (BiRefNet isn't installed here: the real-model checks were skipped)")

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_cutout)")
