"""Notices when a YouTube link is copied anywhere, so the page can offer to download it.

Only while Toolbelt runs, only when the setting is on, and it only looks at text: it keeps nothing except the
last video link it saw. Uses Windows' clipboard directly (no extra package): a cheap "has it changed?" number
first, and only then the text.
"""
import ctypes
import threading
import time

from downloader import find_link

CF_UNICODETEXT = 13
CF_DIB = 8
GMEM_MOVEABLE = 0x0002
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
user32.RegisterClipboardFormatW.restype = ctypes.c_uint
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]


def _global(data):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise OSError("Windows had no memory for the clipboard.")
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    return handle


def copy_image(png, flat_bmp):
    """Puts a picture on the clipboard twice: as PNG (keeps see-through edges: Discord, browsers, Word) and as a
    plain bitmap on white (for programs like Paint). flat_bmp is a .bmp file's bytes; its 14-byte file header is dropped."""
    for _ in range(10):                                   # another program may hold the clipboard for a moment
        if user32.OpenClipboard(None):
            break
        import time
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        for fmt, data in ((user32.RegisterClipboardFormatW("PNG"), png), (CF_DIB, flat_bmp[14:])):
            handle = _global(data)
            if not user32.SetClipboardData(fmt, handle):
                kernel32.GlobalFree(handle)
        return True
    finally:
        user32.CloseClipboard()


def copy_text(text):
    """Puts text on the clipboard (gradient codes, colour codes)."""
    data = (str(text) + "\0").encode("utf-16-le")
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        import time
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = _global(data)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def grab_image():
    """The picture on the clipboard (a screenshot, or a copied image file), or None."""
    from PIL import Image, ImageGrab
    try:
        got = ImageGrab.grabclipboard()
    except Exception:
        return None
    if isinstance(got, list):                              # copied files: take the first picture among them
        for name in got:
            try:
                img = Image.open(name)
                img.load()
                return img
            except Exception:
                continue
        return None
    return got


def read_text():
    """The clipboard's text, or None (another program may hold the clipboard for a moment)."""
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)[:4000]
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


class Watcher:
    def __init__(self, is_on):
        self._is_on = is_on                    # a function: is the setting on right now?
        self._seen = user32.GetClipboardSequenceNumber()
        self._last_link = None
        self._offer = None
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            time.sleep(1)
            try:
                number = user32.GetClipboardSequenceNumber()
                if number == self._seen:
                    continue
                self._seen = number
                if not self._is_on():
                    continue
                link = find_link(read_text() or "")
                if link and link != self._last_link:
                    self._last_link = link
                    with self._lock:
                        self._offer = {"url": link, "at": time.time()}
            except Exception:
                pass                                # the clipboard is best-effort; never crash the app

    def take_offer(self):
        """The newest copied link not shown yet (shown once), or None."""
        with self._lock:
            offer, self._offer = self._offer, None
        return offer if offer and time.time() - offer["at"] < 60 else None

    def paste(self):
        """For the Paste button: whatever text is on the clipboard now."""
        return read_text() or ""
