"""The icon Windows' Explorer shows for a program, shortcut or folder, as a small PNG data link for the page.

Borrowed from Waypoint (Widgets\\Waypoint\\desktop\\wpcore.py, shell_icon): IShellItemImageFactory.GetImage with
ICONONLY through plain ctypes COM, so it is the real icon and never a preview of contents. Here Pillow makes the PNG.
"""
import base64
import ctypes
import io
from ctypes import wintypes
from pathlib import Path

from PIL import Image

shell32, ole32, gdi32, user32 = ctypes.windll.shell32, ctypes.windll.ole32, ctypes.windll.gdi32, ctypes.windll.user32


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(self))


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long), ("bmWidthBytes", ctypes.c_long),
                ("bmPlanes", ctypes.c_ushort), ("bmBitsPixel", ctypes.c_ushort), ("bmBits", ctypes.c_void_p)]


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_ushort),
                ("biBitCount", ctypes.c_ushort), ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


_IID_IMAGE_FACTORY = "{BCC18B79-BA16-442F-80C4-8A59C30C463B}"
_GETIMAGE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, _SIZE, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
_RELEASE = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
shell32.SHCreateItemFromParsingName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
gdi32.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

_cache = {}


_KNOWN = {"Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
          "Music": "{4BD8D571-6D19-48D3-BE97-422220080E43}"}
shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]


def known_folder(name):
    """The real Desktop, Videos or Music folder (OneDrive may have moved it, Dutch Windows calls it Bureaublad), asked from Windows."""
    ptr = ctypes.c_wchar_p()
    if shell32.SHGetKnownFolderPath(ctypes.byref(GUID(_KNOWN[name])), 0, None, ctypes.byref(ptr)) != 0 or not ptr.value:
        return str(Path.home() / name)
    try:
        return ptr.value
    finally:
        ole32.CoTaskMemFree(ptr)


def icon(path, px=64):
    """'data:image/png;base64,…' of the icon Explorer shows for path, or '' (cached per path and size)."""
    key = (str(path).lower(), px)
    if key in _cache:
        return _cache[key]
    _cache[key] = _read(str(path), px)
    return _cache[key]


def _read(path, px):
    init = ole32.CoInitializeEx(None, 2)                      # this thread may not have COM yet
    try:
        fac = ctypes.c_void_p()
        if shell32.SHCreateItemFromParsingName(path, None, ctypes.byref(GUID(_IID_IMAGE_FACTORY)), ctypes.byref(fac)) != 0 or not fac:
            return ""
        vt = ctypes.cast(ctypes.cast(fac, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        hbm = ctypes.c_void_p()
        try:
            hr = _GETIMAGE(vt[3])(fac, _SIZE(px, px), 0x4, ctypes.byref(hbm))      # 0x4 = SIIGBF_ICONONLY
        finally:
            _RELEASE(vt[2])(fac)
        if hr != 0 or not hbm:
            return ""
        try:
            bm = _BITMAP()
            gdi32.GetObjectW(hbm, ctypes.sizeof(bm), ctypes.byref(bm))
            w, h = bm.bmWidth, abs(bm.bmHeight)
            if not (0 < w <= 512 and 0 < h <= 512):
                return ""
            hdr = _BMIH(ctypes.sizeof(_BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)      # top-down, 32-bit BGRA
            buf = ctypes.create_string_buffer(w * h * 4)
            dc = user32.GetDC(None)
            try:
                got = gdi32.GetDIBits(dc, hbm, 0, h, buf, ctypes.byref(hdr), 0)
            finally:
                user32.ReleaseDC(None, dc)
            if got != h:
                return ""
            img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)
            if not img.getchannel("A").getextrema()[1]:          # no see-through information at all: make it solid
                img.putalpha(255)
            else:                                                # Windows multiplied the colours by alpha: undo that
                img = Image.frombuffer("RGBa", (w, h), img.tobytes(), "raw", "RGBa", 0, 1).convert("RGBA")
            out = io.BytesIO()
            img.save(out, "PNG")
            return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
        finally:
            gdi32.DeleteObject(hbm)
    except Exception:
        return ""
    finally:
        if init in (0, 1):
            ole32.CoUninitialize()
