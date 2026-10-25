r"""Win+W (was Win+T, see KEY_LETTER) opens or hides Toolbelt (his ask, 15 Oct). Windows keeps Win+T for itself (it walks through the taskbar), so a
normal RegisterHotKey can't have it: this uses a low-level keyboard hook (WH_KEYBOARD_LL) that sees Win+T first and
swallows it. He chose this knowing two catches: Windows' own Win+T is gone while it's on, and some games' anti-cheat
dislikes global hooks; Settings > About has the switch to turn it off.

The hook runs in its own thread with its own message loop and does almost nothing inside the callback (Windows drops a
hook that takes too long). When Win+T is swallowed, a harmless unused key (vkE8, as AutoHotkey does) is sent so that
letting go of Win doesn't open the Start menu.
"""
import ctypes
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WH_KEYBOARD_LL, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_QUIT = 13, 0x100, 0x101, 0x104, 0x105, 0x12
VK_LWIN, VK_RWIN, VK_SHIFT, VK_CONTROL, VK_MENU, VK_MASK = 0x5B, 0x5C, 0x10, 0x11, 0x12, 0xE8
# Toolbelt's key: Win + this letter (was T; his wish 15 Oct evening: W, Windows only uses it for Widgets, which he
# doesn't use). Change it here and everything follows (the hook, the hotkey, Windows' DisabledHotkeys letter).
KEY_LETTER = "W"
VK_KEY = ord(KEY_LETTER)
VK_T = VK_KEY                                                  # the old name, kept for the tests
LLKHF_INJECTED, KEYEVENTF_KEYUP = 0x10, 0x2
MOD_WIN, MOD_NOREPEAT, WM_HOTKEY = 0x8, 0x4000, 0x312
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]

# Windows' own Win+key shortcuts can be switched off per letter: HKCU\...\Explorer\Advanced, DisabledHotkeys (a string of
# letters). Explorer reads it when it starts. His wish (15 Oct): Windows' Win+T off in Windows itself.
ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"


def windows_wint_off(letter=None):
    """True when Windows' own Win+<letter> (Toolbelt's key) is switched off in its settings (the letter in DisabledHotkeys)."""
    letter = (letter or KEY_LETTER).upper()
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
            return letter in str(winreg.QueryValueEx(k, "DisabledHotkeys")[0]).upper()
    except OSError:
        return False


def set_windows_wint(off, letter=None):
    """Switches Windows' own Win+<letter> off (adds the letter) or back on (removes it), keeping his other letters (he has S).
    Returns True when the setting changed (Explorer has to restart before it counts)."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ADVANCED) as k:
        try:
            now, kind = winreg.QueryValueEx(k, "DisabledHotkeys")
        except OSError:
            now, kind = "", winreg.REG_SZ
        now = str(now)
        letter = (letter or KEY_LETTER).upper()
        new = (now if letter in now.upper() else now + letter) if off else "".join(c for c in now if c.upper() != letter)
        if new == now:
            return False
        if new:
            winreg.SetValueEx(k, "DisabledHotkeys", 0, kind if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) else winreg.REG_SZ, new)
        else:
            winreg.DeleteValue(k, "DisabledHotkeys")
        return True


def restart_explorer():
    """Explorer reads DisabledHotkeys when it starts: restart it (the taskbar blinks, open folder windows close)."""
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True, creationflags=0x08000000)
    time.sleep(1.0)
    subprocess.Popen(["explorer.exe"], creationflags=0x08000000)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.GetModuleHandleW.restype = ctypes.c_void_p


def decide(vk, is_down, win_down, other_down, injected, already_down):
    """What to do with one key event: 'press' (swallow and act), 'swallow' (swallow quietly) or 'pass'."""
    if injected or vk != VK_KEY or not win_down or other_down:
        return "pass" if not (vk == VK_KEY and already_down and not is_down) else "swallow"
    if is_down:
        return "swallow" if already_down else "press"          # holding T repeats keydown: act only once
    return "swallow"


class WinT:
    def __init__(self, on_press, prefer_hotkey=False):
        self.on_press = on_press
        self.prefer_hotkey = prefer_hotkey
        self.mode = ""                                         # "hotkey" (registered) or "hook" (the keyboard hook)
        self._proc = HOOKPROC(self._callback)                  # kept on self: Windows calls it for as long as the hook lives
        self._hook = None
        self._thread = None
        self._tid = 0
        self._down = False
        self.ok = False
        self._ready = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return self.ok
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="win-t", daemon=True)
        self._thread.start()
        self._ready.wait(3)
        return self.ok

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(2)
        self.ok = False

    def running(self):
        return bool(self._thread and self._thread.is_alive() and self.ok)

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()
        # When Windows' own Win+T is switched off (DisabledHotkeys contains T, after Explorer restarted), Win+T is free:
        # an ordinary registered hotkey then does it, no keyboard hook at all (anti-cheats don't mind those).
        if self.prefer_hotkey and user32.RegisterHotKey(None, 1, MOD_WIN | MOD_NOREPEAT, VK_KEY):
            self.mode, self.ok = "hotkey", True
            self._ready.set()
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    threading.Thread(target=self._act, daemon=True).start()
            user32.UnregisterHotKey(None, 1)
            self._tid = 0
            return
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        self.ok = bool(self._hook)
        self.mode = "hook" if self._hook else ""
        self._ready.set()
        if not self._hook:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        self._tid = 0

    def _act(self):
        try:
            self.on_press()
        except Exception:
            pass

    def _callback(self, code, wparam, lparam):
        try:
            if code == 0:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == VK_KEY:
                    is_down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    win = bool((user32.GetAsyncKeyState(VK_LWIN) | user32.GetAsyncKeyState(VK_RWIN)) & 0x8000)
                    other = bool((user32.GetAsyncKeyState(VK_SHIFT) | user32.GetAsyncKeyState(VK_CONTROL) | user32.GetAsyncKeyState(VK_MENU)) & 0x8000)
                    what = decide(info.vkCode, is_down, win, other, bool(info.flags & LLKHF_INJECTED), self._down)
                    if what == "press":
                        self._down = True
                        threading.Thread(target=self._fire, daemon=True).start()
                        return 1
                    if what == "swallow":
                        if not is_down:
                            self._down = False
                        return 1
        except Exception:
            pass
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _fire(self):
        user32.keybd_event(VK_MASK, 0, 0, 0)                   # so letting go of Win doesn't open the Start menu
        user32.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)
        try:
            self.on_press()
        except Exception:
            pass


def bring_forward(hwnd):
    """Puts a window in front, also when another program has the focus (Windows guards that; joining its input thread lets us)."""
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.SwitchToThisWindow.argtypes = [ctypes.c_void_p, wintypes.BOOL]
    # Windows only lets the program that got the last input pull a window to the front (the "foreground lock"). With
    # Win+T as a registered hotkey nothing was typed by the helper, so Windows quietly refused (his report, 15 Oct).
    # A tap of an unused key (vkE8) makes the helper the last input; then join the front window's input and ask.
    user32.keybd_event(VK_MASK, 0, 0, 0)
    user32.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)
    fg = user32.GetForegroundWindow()
    mine = kernel32.GetCurrentThreadId()
    theirs = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if theirs and theirs != mine:
        user32.AttachThreadInput(mine, theirs, True)
    try:
        user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)     # SW_RESTORE / SW_SHOW
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if theirs and theirs != mine:
            user32.AttachThreadInput(mine, theirs, False)
    if user32.GetForegroundWindow() != hwnd:                  # still refused: Windows' own "switch to this window"
        user32.SwitchToThisWindow(hwnd, True)
        time.sleep(0.05)
    return user32.GetForegroundWindow() == hwnd


def find(title, owner=0):
    """The top-level window with exactly this title (of process `owner` when given: an Explorer window showing the
    Toolbelt folder is also called "Toolbelt")."""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _l):
        n = user32.GetWindowTextLengthW(hwnd)
        if n == len(title):
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if buf.value == title and (not owner or pid.value == owner):
                found.append(hwnd)
                return False
        return True
    user32.EnumWindows(each, 0)
    return found[0] if found else None


def toggle(title="Toolbelt", owner=0):
    """Win+T: Toolbelt in front → it goes down; otherwise it comes up."""
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    hwnd = find(title, owner)
    if not hwnd:
        return "missing"
    if user32.GetForegroundWindow() == hwnd and not user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 6)                             # SW_MINIMIZE
        return "hidden"
    return "shown" if bring_forward(hwnd) else "refused"


# ---------- the hook in its own small process (15 Oct: "Win+T doesn't open it") ----------
# Inside Toolbelt the hook shared Python with everything else (video pieces, HD upscaling, scans). A low-level hook must
# answer Windows within about a second for every key pressed anywhere; when Python was busy it answered late once, and
# Windows silently removes such a hook for good. In a process that does nothing else it always answers at once.
class Helper:
    """Starts and stops `hotkey.py --watch <Toolbelt's pid> <title>`; it ends by itself when Toolbelt's process ends."""

    def __init__(self, title="Toolbelt", parent=None):
        self.title, self.parent, self.proc, self.mode = title, parent or os.getpid(), None, ""

    def start(self, wait=8):
        if self.running():
            return True
        self.proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--watch", str(self.parent), self.title],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=0x08000000)
        answer = []
        reader = threading.Thread(target=lambda: answer.append(self.proc.stdout.readline().decode("ascii", "replace").strip()), daemon=True)
        reader.start()
        reader.join(wait)
        if not (answer and answer[0].startswith("ready ok")):
            self.stop()
            return False
        self.mode = answer[0].split()[-1]                      # hotkey or hook
        return True

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def running(self):
        return bool(self.proc and self.proc.poll() is None)


def _watch(parent, title):
    """The helper process: hook in, then wait (without using Python) until Toolbelt's process is gone."""
    SYNCHRONIZE = 0x00100000
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, parent)
    if not handle:
        print("ready fail", flush=True)
        return
    log = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Toolbelt" / "wint.log"

    def press():                                               # every Win+T leaves one line, so a failure can be found
        result = toggle(title, parent)
        try:
            lines = log.read_text(encoding="utf-8").splitlines()[-40:] if log.exists() else []
            log.write_text("\n".join(lines + [time.strftime("%Y-%m-%d %H:%M:%S") + " " + result]) + "\n", encoding="utf-8")
        except OSError:
            pass
    hook = WinT(press, prefer_hotkey=True)
    print("ready ok " + hook.mode if hook.start() else "ready fail", flush=True)
    kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)            # sleeps here, Python free, until Toolbelt quits
    hook.stop()


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--watch":
    _watch(int(sys.argv[2]), sys.argv[3])
