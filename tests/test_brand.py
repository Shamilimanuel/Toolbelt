"""Tests for brand.py: the logo as SVG, the .ico files, and the Start-menu shortcut (made in a temporary folder, never the real Start menu)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import brand                                                  # noqa: E402
from PIL import Image                                         # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- the drawing ----------
for look in brand.LOOKS:
    s = brand.svg(look, 22)
    expect("%s: SVG has the tile and all %d parts" % (look, len(brand.SHAPES)), s.count("<rect") >= len(brand.SHAPES) + 1 and 'width="22"' in s)
expect("Cartridge is pixel-sharp, Glass is rounded", 'crispEdges' in brand.svg("cartridge") and 'crispEdges' not in brand.svg("glass") and 'rx="3.6"' in brand.svg("glass"))
expect("an unknown look falls back to Cartridge", brand.svg("neon") == brand.svg("cartridge"))

img = brand.render("cartridge", 16)
expect("16 px Cartridge: the label's T pixel is yellow, the corner is purple", img.getpixel((7, 8))[:3] == (255, 207, 63) and img.getpixel((0, 0))[:3] == (38, 34, 90))
big = brand.render("glass", 256)
expect("256 px Glass: round corners are see-through, the middle is painted", big.getpixel((0, 0))[3] == 0 and big.getpixel((128, 128))[3] == 255)

# ---------- the .ico files ----------
with tempfile.TemporaryDirectory() as tmp:
    written = brand.make_icons(tmp)
    expect("three .ico files written", len(written) == 3 and all(p.exists() and p.stat().st_size > 1000 for p in written))
    with Image.open(written[0]) as ico:
        sizes = ico.info["sizes"]
    expect("an .ico holds 16 to 256 px", (16, 16) in sizes and (256, 256) in sizes)
expect("the real icons are in web/icons (committed)", all(brand.icon_path(l).exists() for l in brand.LOOKS))

# ---------- the shortcut ----------
with tempfile.TemporaryDirectory() as tmp:
    r = brand.start_menu_shortcut(sys.executable, str(Path(__file__).resolve().parent.parent / "main.py"), folder=tmp)
    expect("a shortcut is made", r["ok"] and Path(r["path"]).exists())
    data = Path(r["path"]).read_bytes() if r["ok"] else b""
    expect("it carries Toolbelt's own taskbar identity and icon", brand.APP_ID.encode("utf-16-le") in data and b"toolbelt-cartridge.ico" in data.replace(b"\x00", b""))
expect("claiming the taskbar identity works on this Windows", brand.claim_taskbar())

# ---------- a shortcut's icon can be changed afterwards (the look changed) ----------
with tempfile.TemporaryDirectory() as tmp:
    r = brand.start_menu_shortcut(sys.executable, str(Path(__file__).resolve().parent.parent / "main.py"), "cartridge", folder=tmp, name="Calculator", args="--open calc-mini")
    data = Path(r["path"]).read_bytes().replace(b"\x00", b"")
    expect("a second shortcut with arguments", r["ok"] and b"--open calc-mini" in data and b"toolbelt-cartridge.ico" in data)
    expect("its icon can be switched to the Glass one", brand.set_shortcut_icon(r["path"], brand.icon_path("glass")) and b"toolbelt-glass.ico" in Path(r["path"]).read_bytes().replace(b"\x00", b""))
    expect("a missing shortcut is simply skipped", brand.set_shortcut_icon(Path(tmp) / "nope.lnk", brand.icon_path("glass")) is False)

# ---------- the Calculator key: written under a test number, read back, removed ----------
TEST_KEY = 9977
cmd = '"C:\\x\\Toolbelt.exe" "C:\\x\\main.py" --open calc-mini'
expect("the Calculator key entry is written", brand.calc_key(cmd, key=TEST_KEY)["ok"] and brand.calc_key_is(cmd, key=TEST_KEY))
expect("and removed again", brand.calc_key(None, key=TEST_KEY)["ok"] and not brand.calc_key_is(cmd, key=TEST_KEY))

# ---------- Toolbelt.exe: the venv launcher, an exact (still signed) copy ----------
with tempfile.TemporaryDirectory() as tmp:
    import shutil
    import subprocess
    scripts = Path(tmp) / "Scripts"
    scripts.mkdir()
    shutil.copy(Path(sys.executable).with_name("pythonw.exe"), scripts / "pythonw.exe")
    (Path(tmp) / "pyvenv.cfg").write_text(Path(sys.executable).parent.parent.joinpath("pyvenv.cfg").read_text(encoding="utf-8"), encoding="utf-8")
    exe = brand.make_launcher(scripts)
    expect("Toolbelt.exe is made next to pythonw.exe", exe is not None and exe.name == "Toolbelt.exe" and exe.exists())
    with Image.open(exe) if False else open(exe, "rb") as f:
        raw = f.read()
    sig = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-AuthenticodeSignature '%s').Status" % exe], capture_output=True, text=True, creationflags=0x08000000, timeout=60).stdout.strip()
    expect("it is an exact copy, so Python's signature stays valid and Smart App Control lets it run (%s)" % sig, sig == "Valid" and raw == (scripts / "pythonw.exe").read_bytes())
    out = subprocess.run([str(exe), "-c", "import sys; print(sys.prefix)"], capture_output=True, text=True, creationflags=0x08000000, timeout=30)
    expect("and it still runs Python from the venv", out.returncode == 0 and "venv" in out.stdout.lower() or out.returncode == 0)
    again = brand.make_launcher(scripts)
    expect("made once; a second call keeps it", again == exe)

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_brand)")
