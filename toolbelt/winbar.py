"""Toolbelt's own window bar (his ask, 15 Oct: Windows' grey bar looked out of place).

Windows' title bar is taken away, but the window keeps everything else Windows gives it: the resize edges, the
shadow, the rounded corners, Win+arrows. The page's top bar becomes the title bar:
- pressing the mouse on the bar calls start_drag: Windows gets the same "move" a real title bar sends, so it moves the
  window itself (drag to an edge snaps, to the top maximises); double-click maximises (the page calls Api.win_max).
  WebView2's CSS `app-region: drag` was tried first: it didn't move the window in Toolbelt's window mode (15 Oct);
- WM_NCCALCSIZE (a window subclass) gives the caption's height to the page; when maximised the frame Windows hides
  off-screen is taken off again so nothing is cut;
- minimise / maximise / close are the page's own buttons (Api.win_*).
Settings > About > "Own window bar" switches all of it off (takes effect after a restart).
"""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
comctl32 = ctypes.windll.comctl32

WM_NCCALCSIZE = 0x0083
WM_NCDESTROY = 0x0082
SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x20, 0x2, 0x1, 0x4, 0x10
SM_CXPADDEDBORDER, SM_CYFRAME = 92, 33
LRESULT = ctypes.c_ssize_t
SUBCLASSPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
comctl32.SetWindowSubclass.argtypes = [wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t]
comctl32.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
comctl32.DefSubclassProc.restype = LRESULT
comctl32.RemoveWindowSubclass.argtypes = [wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


_procs = {}                                                      # keep the callbacks alive as long as the windows


def _frame(hwnd):
    dpi = user32.GetDpiForWindow(hwnd) or 96
    return user32.GetSystemMetricsForDpi(SM_CYFRAME, dpi) + user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)


def _make_proc():
    @SUBCLASSPROC
    def proc(hwnd, msg, wparam, lparam, uid, ref):
        if msg == WM_NCCALCSIZE and wparam:
            params = ctypes.cast(lparam, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
            top = params.rgrc[0].top
            result = comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)   # Windows works out the side and bottom frames
            params.rgrc[0].top = top + (_frame(hwnd) if user32.IsZoomed(hwnd) else 0)   # …and the caption goes to the page
            return result
        if msg == WM_NCDESTROY:
            comctl32.RemoveWindowSubclass(hwnd, _procs.get(hwnd), 1)
            _procs.pop(hwnd, None)
        return comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
    return proc


def _on_ui(form, fn):
    """Runs fn on the window's own thread (Windows wants subclassing done there)."""
    from System import Action
    if form.InvokeRequired:
        form.Invoke(Action(fn))
    else:
        fn()


def install(window):
    """Takes Windows' title bar away and lets the page's bar be dragged. Returns (ok, why)."""
    form = getattr(window, "native", None)
    if form is None:
        return False, "the window isn't ready"
    result = {"ok": False, "why": ""}

    def work():
        hwnd = form.Handle.ToInt64()
        if form.browser is None or form.browser.webview.CoreWebView2 is None:
            result["why"] = "WebView2 isn't ready yet"
            return
        proc = _make_proc()
        if not comctl32.SetWindowSubclass(hwnd, proc, 1, 0):
            result["why"] = "Windows refused the window hook"
            return
        _procs[hwnd] = proc
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        result["ok"] = True

    try:
        _on_ui(form, work)
    except Exception as error:
        return False, str(error)[:120]
    return result["ok"], result["why"]


WM_NCLBUTTONDOWN, HTCAPTION = 0x00A1, 2
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def start_drag(window):
    """The mouse went down on the page's bar: hand Windows the same "move this window" a real title bar sends.
    Windows then moves it itself, so snapping to edges, drag-to-maximise and dragging out of maximised all work.
    (WebView2's CSS drag areas didn't move the window in Toolbelt's window mode, his test 15 Oct.)"""
    form = getattr(window, "native", None)
    if form is None:
        return False
    from System import Action
    hwnd = form.Handle.ToInt64()

    def work():
        user32.ReleaseCapture()                                  # the page holds the mouse; let go so Windows can take it
        user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)   # Windows' own move loop, until the button comes up
    form.BeginInvoke(Action(work))                               # on the window's thread, without waiting for the drag to end
    return True


def caption_gone(window):
    """For the tests: the page starts at the window's top edge (no Windows caption above it)."""
    form = getattr(window, "native", None)
    if form is None:
        return False
    hwnd = form.Handle.ToInt64()
    win, pt = wintypes.RECT(), wintypes.POINT(0, 0)
    user32.GetWindowRect(hwnd, ctypes.byref(win))
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return abs(pt.y - win.top) <= 1


def is_maximized(window):
    form = getattr(window, "native", None)
    return bool(form is not None and user32.IsZoomed(form.Handle.ToInt64()))
