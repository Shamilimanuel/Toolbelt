"""Toolbelt's logo: the Cartridge mark he picked on 14 Oct (docs/logo.html, idea 2), in all three looks.

One list of rectangles on a 16×16 grid is the single source of truth. From it:
- `svg()` draws the mark for the page (the title bar shows the one that belongs to the current look),
- `make_icons()` writes `web/icons/toolbelt-<look>.ico` with Pillow (16, 24, 32, 48, 64, 128, 256 px),
- `set_window_icon()` puts that .ico on the window and the taskbar (WM_SETICON), swapped when the look changes,
- `claim_taskbar()` gives the process its own taskbar identity (AppUserModelID), so Windows stops grouping
  Toolbelt under "Python" and a jump list can belong to it later,
- `start_menu_shortcut()` makes a Start-menu shortcut carrying the same identity, so he can pin Toolbelt.
The same rectangles live in web/app.js (LOGO); test_page checks that the two copies match.
"""
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

APP_ID = "Shamil.Toolbelt"
ICONS_DIR = Path(__file__).resolve().parents[1] / "web" / "icons"
LOOKS = ("cartridge", "glass", "glassdark")

# [x, y, w, h, colour]: body, notch, label, the T (bar + stem), grip stripe
SHAPES = [[3, 1, 10, 14, "main"], [11, 1, 2, 3, "hole"], [5, 5, 6, 7, "ink"], [6, 6, 4, 1, "main"], [7, 7, 2, 4, "main"], [4, 13, 8, 1, "accent"]]

PALETTES = {
    "cartridge": {"tile": ("#26225A", "#26225A"), "hole": "#26225A", "bevel": "#4A43A0", "main": "#FFCF3F", "accent": "#FF5C8A", "ink": "#0B0920", "rx": 0.0, "srx": 0.0},
    "glass":     {"tile": ("#2A8FE6", "#0A4E8F"), "hole": "#1468B8", "bevel": "", "main": "#FFFFFF", "accent": "#9EDBFF", "ink": "#083B6B", "rx": 3.6, "srx": 0.8},
    "glassdark": {"tile": ("#3A3F5C", "#1B1E2E"), "hole": "#262A40", "bevel": "", "main": "#60CDFF", "accent": "#FFFFFF", "ink": "#0B1020", "rx": 3.6, "srx": 0.8},
}


def look_of(look):
    return look if look in PALETTES else "cartridge"


def svg(look, px=22):
    """The mark as inline SVG for the page, same drawing as the .ico."""
    p = PALETTES[look_of(look)]
    out = []
    if p["tile"][0] == p["tile"][1]:
        fill = p["tile"][0]
    else:
        out.append('<defs><linearGradient id="tbg-%s" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient></defs>'
                   % (look, p["tile"][0], p["tile"][1]))
        fill = "url(#tbg-%s)" % look
    out.append('<rect width="16" height="16" rx="%s" fill="%s"/>' % (p["rx"], fill))
    if p["bevel"]:
        out.append('<rect x="1" y="1" width="14" height="1" fill="%s"/><rect x="1" y="1" width="1" height="14" fill="%s"/>' % (p["bevel"], p["bevel"]))
    for x, y, w, h, c in SHAPES:
        out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%s" fill="%s"/>' % (x, y, w, h, p["srx"], p[c]))
    crisp = ' shape-rendering="crispEdges"' if look_of(look) == "cartridge" else ""
    return '<svg width="%d" height="%d" viewBox="0 0 16 16"%s role="img" aria-label="Toolbelt">%s</svg>' % (px, px, crisp, "".join(out))


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def render(look, px):
    """One PNG-style picture of the mark at px pixels (Pillow Image, RGBA). Drawn 8× too big and shrunk, so round corners stay smooth."""
    from PIL import Image, ImageDraw
    p = PALETTES[look_of(look)]
    scale = 8 if look_of(look) != "cartridge" else max(1, px // 16)
    side = 16 * scale if look_of(look) == "cartridge" else px * scale
    unit = side / 16
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if p["tile"][0] == p["tile"][1]:
        draw.rounded_rectangle((0, 0, side - 1, side - 1), radius=p["rx"] * unit, fill=_hex(p["tile"][0]))
    else:                                                       # a diagonal gradient, then the rounded tile as a mask
        a, b = _hex(p["tile"][0]), _hex(p["tile"][1])
        grad = Image.new("RGBA", (side, side))
        gp = grad.load()
        for yy in range(side):
            for xx in range(side):
                t = (xx + yy) / (2 * side - 2)
                gp[xx, yy] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=p["rx"] * unit, fill=255)
        img.paste(grad, (0, 0), mask)
        draw = ImageDraw.Draw(img)
    if p["bevel"]:
        draw.rectangle((unit, unit, 15 * unit - 1, 2 * unit - 1), fill=_hex(p["bevel"]))
        draw.rectangle((unit, unit, 2 * unit - 1, 15 * unit - 1), fill=_hex(p["bevel"]))
    for x, y, w, h, c in SHAPES:
        box = (x * unit, y * unit, (x + w) * unit - 1, (y + h) * unit - 1)
        if p["srx"]:
            draw.rounded_rectangle(box, radius=p["srx"] * unit, fill=_hex(p[c]))
        else:
            draw.rectangle(box, fill=_hex(p[c]))
    if side != px:
        img = img.resize((px, px), Image.Resampling.LANCZOS if look_of(look) != "cartridge" else Image.Resampling.NEAREST)
    return img


def icon_path(look):
    return ICONS_DIR / ("toolbelt-%s.ico" % look_of(look))


def make_icons(folder=ICONS_DIR):
    """Writes the three .ico files (and a 256 px PNG of each, for shortcuts and docs). Run: python brand.py"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for look in LOOKS:
        sizes = [16, 24, 32, 48, 64, 128, 256]
        pictures = [render(look, s) for s in sizes]
        target = folder / ("toolbelt-%s.ico" % look)
        pictures[-1].save(target, format="ICO", sizes=[(s, s) for s in sizes], append_images=pictures[:-1])
        pictures[-1].save(folder / ("toolbelt-%s.png" % look), format="PNG")
        written.append(target)
    return written


# ---------- Toolbelt.exe: the venv's own pythonw launcher, copied unchanged ----------
def make_launcher(scripts_dir, look="cartridge"):
    """Makes <venv>/Scripts/Toolbelt.exe: an exact copy of pythonw.exe (the venv launcher, which must stay in that folder
    to find pyvenv.cfg), so Task Manager and Waypoint's command door see "Toolbelt.exe".
    18 Oct: it used to get Toolbelt's icon written into it, but changing the file breaks the Python Software Foundation's
    signature, and Smart App Control then blocked Toolbelt ("did not meet the signing level requirements"). An exact copy
    keeps the signature valid (the file name isn't part of it). The icon comes from the shortcuts and the window instead.
    Returns the path, or None when it couldn't be made. `look` is kept for the callers; it no longer matters here."""
    import filecmp
    import shutil
    import time as _time
    scripts_dir = Path(scripts_dir)
    source, target = scripts_dir / "pythonw.exe", scripts_dir / "Toolbelt.exe"
    if not source.exists():
        return None
    for old in scripts_dir.glob("Toolbelt.old-*.exe"):        # earlier ones that were in use when they were replaced
        try:
            old.unlink()
        except OSError:
            pass
    try:
        if target.exists() and filecmp.cmp(source, target, shallow=False):
            return target
        tmp = target.with_suffix(".tmp.exe")
        shutil.copy2(source, tmp)
        try:
            os.replace(tmp, target)
        except PermissionError:                                # Toolbelt.exe is running: a running program can be renamed
            target.rename(target.with_name("Toolbelt.old-%d.exe" % int(_time.time())))
            os.replace(tmp, target)
        return target
    except OSError:
        return None


def _put_icon(exe, ico):
    """Writes the .ico's pictures into the exe as its first icon group (RT_ICON + RT_GROUP_ICON) through UpdateResource."""
    import struct
    data = Path(ico).read_bytes()
    count = struct.unpack_from("<H", data, 4)[0]
    entries = []
    for i in range(count):
        w, h, colors, _r, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        entries.append((w, h, colors, planes, bits, size, data[offset:offset + size]))
    kernel32 = ctypes.windll.kernel32
    kernel32.BeginUpdateResourceW.restype = ctypes.c_void_p
    kernel32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel32.UpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, wintypes.DWORD]
    kernel32.EndUpdateResourceW.argtypes = [ctypes.c_void_p, wintypes.BOOL]
    handle = kernel32.BeginUpdateResourceW(str(exe), False)
    if not handle:
        return False
    ok = True
    lang = 0x0409                                               # English (US), what Python's own resources use
    group = struct.pack("<HHH", 0, 1, count)
    for n, (w, h, colors, planes, bits, size, image) in enumerate(entries, 1):
        buf = ctypes.create_string_buffer(image, len(image))
        ok &= bool(kernel32.UpdateResourceW(handle, ctypes.c_void_p(3), ctypes.c_void_p(n), lang, buf, len(image)))   # RT_ICON
        group += struct.pack("<BBBBHHIH", w, h, colors, 0, planes, bits, size, n)
    gbuf = ctypes.create_string_buffer(group, len(group))
    ok &= bool(kernel32.UpdateResourceW(handle, ctypes.c_void_p(14), ctypes.c_void_p(1), lang, gbuf, len(group)))     # RT_GROUP_ICON, id 1
    return bool(kernel32.EndUpdateResourceW(handle, not ok)) and ok


# ---------- Windows: the window icon, the taskbar identity, the Start-menu shortcut ----------
def claim_taskbar(app_id=APP_ID):
    """Call before the window exists: Toolbelt gets its own taskbar button instead of Python's."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except (AttributeError, OSError):
        return False


def set_window_icon(look, title="Toolbelt", hwnd=None):
    """Puts the look's .ico on the window (small, in the title bar) and the taskbar (big). Returns True when it worked."""
    user32 = ctypes.windll.user32
    hwnd = hwnd or user32.FindWindowW(None, title)
    path = icon_path(look)
    if not hwnd or not path.exists():
        return False
    ok = False
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SendMessageW.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
    for which, size in ((0, 16), (1, 32)):                         # ICON_SMALL, ICON_BIG
        handle = user32.LoadImageW(None, str(path), 1, size, size, 0x10)      # IMAGE_ICON, LR_LOADFROMFILE
        if handle:
            user32.SendMessageW(hwnd, 0x80, which, handle)             # WM_SETICON
            ok = True
    return ok


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(self))


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", wintypes.USHORT), ("r1", wintypes.USHORT), ("r2", wintypes.USHORT), ("r3", wintypes.USHORT), ("pwszVal", ctypes.c_wchar_p), ("pad", ctypes.c_void_p)]


def _method(obj, index, *argtypes):
    """Calls method number `index` of a COM object's table through ctypes."""
    vtable = ctypes.cast(ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    return proto(vtable[index])


def start_menu_shortcut(python, script, look="cartridge", folder=None, app_id=APP_ID, name="Toolbelt", args=""):
    """Toolbelt.lnk in the Start menu (or `folder`), started with pythonw, carrying Toolbelt's icon and taskbar identity.

    Pinning that shortcut to the taskbar gives the pinned button the same identity as the running window, so they merge.
    """
    ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32
    folder = Path(folder) if folder else Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (name + ".lnk")
    init = ole32.CoInitializeEx(None, 2)
    link = ctypes.c_void_p()
    try:
        hr = ole32.CoCreateInstance(ctypes.byref(_GUID("{00021401-0000-0000-C000-000000000046}")), None, 1,
                                    ctypes.byref(_GUID("{000214F9-0000-0000-C000-000000000046}")), ctypes.byref(link))
        if hr != 0 or not link:
            return {"ok": False, "message": "Windows wouldn't make a shortcut (%d)." % hr}
        # IShellLinkW's table: 20 SetPath, 11 SetArguments, 9 SetWorkingDirectory, 17 SetIconLocation, 7 SetDescription
        _method(link, 20, ctypes.c_wchar_p)(link, str(python))
        _method(link, 11, ctypes.c_wchar_p)(link, ('"%s" %s' % (script, args)).strip())
        _method(link, 9, ctypes.c_wchar_p)(link, str(Path(script).parent))
        _method(link, 17, ctypes.c_wchar_p, ctypes.c_int)(link, str(icon_path(look)), 0)
        _method(link, 7, ctypes.c_wchar_p)(link, "Shamil's own tools in one place")
        store = ctypes.c_void_p()
        _method(link, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(link, ctypes.byref(_GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")), ctypes.byref(store))
        if store:
            key = _PROPERTYKEY(_GUID("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"), 5)        # PKEY_AppUserModel_ID
            value = _PROPVARIANT(31, 0, 0, 0, app_id, None)                                 # VT_LPWSTR
            _method(store, 6, ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT))(store, ctypes.byref(key), ctypes.byref(value))   # SetValue
            _method(store, 7)(store)                                                        # Commit
            _method(store, 2)(store)                                                        # Release
        pfile = ctypes.c_void_p()
        _method(link, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(link, ctypes.byref(_GUID("{0000010B-0000-0000-C000-000000000046}")), ctypes.byref(pfile))
        if not pfile:
            return {"ok": False, "message": "Windows wouldn't save the shortcut."}
        hr = _method(pfile, 6, ctypes.c_wchar_p, ctypes.c_int)(pfile, str(target), 1)       # IPersistFile::Save
        _method(pfile, 2)(pfile)
        if hr != 0:
            return {"ok": False, "message": "Saving the shortcut failed (%d)." % hr}
        shell32.SHChangeNotify(0x08000000, 0x0005, None, None)                              # SHCNE_ASSOCCHANGED: refresh icons
        return {"ok": True, "message": "Toolbelt is in your Start menu. Right-click it there to pin it to the taskbar.", "path": str(target)}
    finally:
        if link:
            _method(link, 2)(link)
        if init in (0, 1):
            ole32.CoUninitialize()


def set_shortcut_icon(lnk, ico):
    """Points an existing shortcut at another .ico (the look changed). Returns True when it was rewritten."""
    ole32 = ctypes.windll.ole32
    lnk, ico = Path(lnk), Path(ico)
    if not lnk.exists() or not ico.exists():
        return False
    init = ole32.CoInitializeEx(None, 2)
    link = ctypes.c_void_p()
    try:
        if ole32.CoCreateInstance(ctypes.byref(_GUID("{00021401-0000-0000-C000-000000000046}")), None, 1,
                                  ctypes.byref(_GUID("{000214F9-0000-0000-C000-000000000046}")), ctypes.byref(link)) != 0 or not link:
            return False
        pfile = ctypes.c_void_p()
        _method(link, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(link, ctypes.byref(_GUID("{0000010B-0000-0000-C000-000000000046}")), ctypes.byref(pfile))
        if not pfile:
            return False
        try:
            if _method(pfile, 5, ctypes.c_wchar_p, wintypes.DWORD)(pfile, str(lnk), 0) != 0:           # IPersistFile::Load
                return False
            _method(link, 17, ctypes.c_wchar_p, ctypes.c_int)(link, str(ico), 0)                        # SetIconLocation
            ok = _method(pfile, 6, ctypes.c_wchar_p, ctypes.c_int)(pfile, str(lnk), 1) == 0            # Save
        finally:
            _method(pfile, 2)(pfile)
        return ok
    finally:
        if link:
            _method(link, 2)(link)
        if init in (0, 1):
            ole32.CoUninitialize()


def follow_look(look):
    """The look changed: the Start-menu shortcuts and the pinned taskbar button get that look's icon too (his report, 14 Oct)."""
    ico = icon_path(look)
    appdata = Path(os.environ.get("APPDATA", ""))
    places = [appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Toolbelt.lnk",
              appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Calculator.lnk",
              appdata / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / "Toolbelt.lnk"]
    changed = [p.name for p in places if set_shortcut_icon(p, ico)]
    if changed:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0005, None, None)                           # tell Explorer the icons changed
    return changed


APPKEY_CALC = 18                                                # Windows' number for the keyboard's Calculator key


def calc_key(command=None, key=APPKEY_CALC):
    """Makes the keyboard's Calculator key start `command` (HKCU ...\\Explorer\\AppKey\\18, ShellExecute), or removes that
    again when command is None. Only this user's registry; Windows falls back to its own calculator when the entry is gone."""
    import winreg
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\AppKey\%d" % key
    try:
        if command is None:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except FileNotFoundError:
                pass
            return {"ok": True, "message": "The Calculator key is Windows' own again."}
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as handle:
            winreg.SetValueEx(handle, "ShellExecute", 0, winreg.REG_SZ, command)
        return {"ok": True, "message": "The Calculator key now opens Toolbelt's calculator."}
    except OSError as error:
        return {"ok": False, "message": "Windows refused: %s" % error}


def calc_key_is(command, key=APPKEY_CALC):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\AppKey\%d" % key) as handle:
            return winreg.QueryValueEx(handle, "ShellExecute")[0] == command
    except OSError:
        return False


if __name__ == "__main__":
    for path in make_icons():
        print("wrote", path, path.stat().st_size, "bytes")
    sys.exit(0)
