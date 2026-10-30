"""Tests for step 5's Python side: saved gradients (kept in a temporary file here) and a picture's main colours."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from PIL import Image, ImageDraw

import colours

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


with tempfile.TemporaryDirectory() as tmp:
    real = colours.STORE
    colours.STORE = Path(tmp) / "colours.json"
    try:
        expect("nothing saved at first", colours.load() == {"saved": [], "last": None})
        r = colours.save_gradient("Demo gold", ["#ffd86b", "#FF8A3D"])
        expect("a gradient is saved, colours in capitals", r["ok"] and r["saved"][0] == {"n": "Demo gold", "s": ["#FFD86B", "#FF8A3D"]})
        colours.save_gradient("Ocean", ["#2AF5FF", "#3D7BFF", "#7B3DFF"])
        expect("newest first", [s["n"] for s in colours.load()["saved"]] == ["Ocean", "Demo gold"])
        colours.save_gradient("Gold again", ["#FFD86B", "#FF8A3D"])
        expect("the same colours saved again replace the old one", [s["n"] for s in colours.load()["saved"]] == ["Gold again", "Ocean"])
        expect("one colour is refused", not colours.save_gradient("x", ["#FFFFFF"])["ok"])
        expect("seven colours are refused", not colours.save_gradient("x", ["#FFFFFF"] * 7)["ok"])
        expect("a non-colour is refused", not colours.save_gradient("x", ["#FFFFFF", "red"])["ok"])
        expect("delete removes it", [s["n"] for s in colours.delete_gradient(0)["saved"]] == ["Ocean"])
        colours.remember({"text": "Hi", "stops": ["#000000", "#FFFFFF"], "fmt": "mm", "secret": "nope"})
        last = colours.load()["last"]
        expect("the current gradient is remembered (only known fields)", last == {"text": "Hi", "stops": ["#000000", "#FFFFFF"], "fmt": "mm"})
        colours.STORE.write_text('{"saved": [{"n": "bad", "s": ["#GGGGGG", "#000000"]}, {"n": "ok", "s": ["#000000", "#FFFFFF"]}]}', encoding="utf-8")
        expect("broken saved entries are dropped, good ones kept", [s["n"] for s in colours.load()["saved"]] == ["ok"])
        colours.STORE.write_text("not json", encoding="utf-8")
        expect("an unreadable file starts empty", colours.load()["saved"] == [])
    finally:
        colours.STORE = real

    pic = Image.new("RGB", (300, 200), (30, 90, 200))
    d = ImageDraw.Draw(pic)
    d.rectangle((0, 0, 100, 200), fill=(240, 200, 40))
    d.rectangle((250, 0, 300, 200), fill=(220, 40, 40))
    path = Path(tmp) / "flag.png"
    pic.save(path)
    pal = colours.picture_palette(path, 6)
    expect("a picture's main colours, biggest first, no look-alikes", pal == ["#1E5AC8", "#F0C828", "#DC2828"])

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_colours)")
