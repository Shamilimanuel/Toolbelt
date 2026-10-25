"""Toolbelt's icon by the clock (the "notification area" or "tray").

Left-click opens the games pop-up, right-click a small menu (Open Toolbelt / Games / Quit). The icon lives on a tiny
invisible window with its own message loop in its own thread, because Windows delivers tray clicks as window messages.
When the look changes the icon swaps with it. If Explorer restarts, Windows says "TaskbarCreated" and the icon is put back.
"""
import ctypes
import threading
from ctypes import wintypes

import brand

user32, shell32, kernel32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
WM_TRAY = 0x0400 + 1            # WM_USER + 1
WM_COMMAND, WM_CLOSE, WM_DESTROY, WM_LBUTTONUP, WM_RBUTTONUP, WM_LBUTTONDBLCLK = 0x0111, 0x0010, 0x0002, 0x0202, 0x0205, 0x0203
MENU_OPEN, MENU_GAMES, MENU_QUIT, MENU_CALC = 1, 2, 3, 4

user32.DefWindowProcW.restype = ctypes.c_long
user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
user32.CreateWindowExW.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.LoadImageW.restype = ctypes.c_void_p
user32.LoadImageW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.CreatePopupMenu.restype = ctypes.c_void_p
user32.AppendMenuW.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.DestroyMenu.argtypes = [ctypes.c_void_p]
user32.DestroyWindow.argtypes = [ctypes.c_void_p]
user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
user32.RegisterWindowMessageW.restype = ctypes.c_uint
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)


class _WNDCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p), ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class _GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]


class _NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", ctypes.c_void_p), ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", ctypes.c_void_p), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", _GUID), ("hBalloonIcon", ctypes.c_void_p)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class Tray:
    """start() puts the icon up; on_click / on_open / on_games / on_quit are called on the tray thread, so they should only post work."""

    def __init__(self, look, on_click, on_open, on_games, on_quit, tip="Toolbelt", on_calc=None):
        self.look, self.tip = look, tip
        self.on_click, self.on_open, self.on_games, self.on_quit, self.on_calc = on_click, on_open, on_games, on_quit, on_calc or (lambda: None)
        self.hwnd = None
        self.hicon = None
        self.ready = threading.Event()
        self.ok = False
        self._proc = WNDPROC(self._wndproc)                    # kept on self, or Python frees it while Windows still calls it
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

    def start(self):
        self._thread.start()
        self.ready.wait(3)
        return self.ok

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, None, None)

    def set_look(self, look):
        self.look = look
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TRAY + 1, None, None)      # swap the icon on the tray thread

    # ---------- inside the tray thread ----------
    def _run(self):
        cls = _WNDCLASS()
        cls.lpfnWndProc = self._proc
        cls.hInstance = kernel32.GetModuleHandleW(None)
        cls.lpszClassName = "ToolbeltTray"
        user32.RegisterClassW(ctypes.byref(cls))
        self.hwnd = user32.CreateWindowExW(0, "ToolbeltTray", "Toolbelt tray", 0, 0, 0, 0, 0, None, None, cls.hInstance, None)
        self.ok = bool(self.hwnd) and self._notify(0)          # NIM_ADD
        self.ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _data(self, flags):
        data = _NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = self.hwnd
        data.uID = 1
        data.uFlags = flags
        data.uCallbackMessage = WM_TRAY
        data.szTip = self.tip
        return data

    def _load_icon(self):
        path = brand.icon_path(self.look)
        new = user32.LoadImageW(None, str(path), 1, 16, 16, 0x10) if path.exists() else None       # IMAGE_ICON, LR_LOADFROMFILE
        if new and self.hicon:
            user32.DestroyIcon(ctypes.c_void_p(self.hicon))
        self.hicon = new or self.hicon
        return self.hicon

    def _notify(self, action):
        """action 0 = add, 1 = modify, 2 = delete."""
        data = self._data(0x1 | 0x2 | 0x4)                     # NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.hIcon = self._load_icon()
        return bool(shell32.Shell_NotifyIconW(action, ctypes.byref(data)))

    def _menu(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, 0, MENU_OPEN, "Open Toolbelt")
        user32.AppendMenuW(menu, 0, MENU_GAMES, "Games")
        user32.AppendMenuW(menu, 0, MENU_CALC, "Calculator")
        user32.AppendMenuW(menu, 0x800, 0, None)              # MF_SEPARATOR
        user32.AppendMenuW(menu, 0, MENU_QUIT, "Quit Toolbelt")
        pt = _POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)                  # or the menu wouldn't close when he clicks elsewhere
        choice = user32.TrackPopupMenu(menu, 0x100 | 0x80 | 0x2, pt.x, pt.y, 0, self.hwnd, None)      # TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON
        user32.DestroyMenu(menu)
        {MENU_OPEN: self.on_open, MENU_GAMES: self.on_games, MENU_CALC: self.on_calc, MENU_QUIT: self.on_quit}.get(choice, lambda: None)()

    def _wndproc(self, hwnd, message, wparam, lparam):
        try:
            if message == WM_TRAY:
                event = (lparam or 0) & 0xFFFF
                if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.on_click()
                elif event == WM_RBUTTONUP:
                    self._menu()
                return 0
            if message == WM_TRAY + 1:
                self._notify(1)
                return 0
            if message == self._taskbar_created:
                self._notify(0)
                return 0
            if message == WM_CLOSE:
                self._notify(2)
                user32.DestroyWindow(hwnd)
                return 0
            if message == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)


def work_area():
    """The screen minus the taskbar: (left, top, right, bottom)."""
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)      # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


def foreground_is(title):
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value == title
