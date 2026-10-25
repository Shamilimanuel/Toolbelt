"""Tests for hotkey.py: the Win+T rules, and that the keyboard hook installs and goes away again. No keys are pressed
(that would act on his real desktop); toggle() is tried on a window title that doesn't exist."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import hotkey                                                 # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


T, A = hotkey.VK_T, 0x41
d = hotkey.decide
expect("Win+T down acts (and is swallowed)", d(T, True, True, False, False, False) == "press")
expect("holding T while Win is down doesn't act again", d(T, True, True, False, False, True) == "swallow")
expect("letting go of T is swallowed too, so Windows never sees half a Win+T", d(T, False, True, False, False, True) == "swallow")
expect("T released after Win was let go first is still swallowed", d(T, False, False, False, False, True) == "swallow")
expect("plain T passes (typing works)", d(T, True, False, False, False, False) == "pass")
expect("Ctrl/Shift/Alt + Win + T pass (left for Windows and other apps)", d(T, True, True, True, False, False) == "pass")
expect("Toolbelt's own fake keys are ignored", d(T, True, True, False, True, False) == "pass")
expect("other keys with Win pass (Win+A, Win+E…)", d(A, True, True, False, False, False) == "pass")

w = hotkey.WinT(lambda: None)
expect("the hook installs", w.start() and w.running())
w.stop()
time.sleep(0.3)
expect("and is removed again", not w.running())
expect("a second start works (switch off and on in Settings)", w.start() and w.running())
w.stop()
expect("toggle without a Toolbelt window says so", hotkey.toggle("No such window 12345") == "missing")

# the hook in its own process (15 Oct): starts, holds the hook, and goes away by itself when Toolbelt's process ends
import subprocess                                             # noqa: E402
stand_in = subprocess.Popen(["ping", "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL, creationflags=0x08000000)   # plays "Toolbelt"
helper = hotkey.Helper("No such window 12345", parent=stand_in.pid)
t0 = time.time()
started = helper.start()
expect("the helper process starts and its hook is in (%.1f s)" % (time.time() - t0), started and helper.running())
stand_in.kill()
stand_in.wait()
for _ in range(50):
    if not helper.running():
        break
    time.sleep(0.1)
expect("when Toolbelt's process ends, the helper ends by itself", not helper.running())
helper.stop()
expect("the helper says how it catches Win+T (%s)" % helper.mode, helper.mode in ("hotkey", "hook"))

# Windows' own Win+T in Windows' settings (DisabledHotkeys), on a test key: his real setting isn't touched
import winreg                                                 # noqa: E402
real_key = hotkey.ADVANCED
hotkey.ADVANCED = r"Software\ToolbeltTest\Advanced"
try:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, hotkey.ADVANCED) as k:
        winreg.SetValueEx(k, "DisabledHotkeys", 0, winreg.REG_SZ, "S")
    expect("switching off adds W (Toolbelt's key) and keeps his S", hotkey.set_windows_wint(off=True) and hotkey.windows_wint_off()
           and winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, hotkey.ADVANCED), "DisabledHotkeys")[0] == "SW")
    expect("doing it twice changes nothing", hotkey.set_windows_wint(off=True) is False)
    expect("switching back on removes only W", hotkey.set_windows_wint(off=False) and not hotkey.windows_wint_off()
           and winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, hotkey.ADVANCED), "DisabledHotkeys")[0] == "S")
    winreg.DeleteValue(winreg.OpenKey(winreg.HKEY_CURRENT_USER, hotkey.ADVANCED, 0, winreg.KEY_SET_VALUE), "DisabledHotkeys")
    hotkey.set_windows_wint(off=True)
    hotkey.set_windows_wint(off=False)
    try:
        winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, hotkey.ADVANCED), "DisabledHotkeys")
        empty_gone = False
    except OSError:
        empty_gone = True
    expect("with nothing else in the list, switching back removes the setting completely", empty_gone)
finally:
    hotkey.ADVANCED = real_key
    for sub in (r"Software\ToolbeltTest\Advanced", r"Software\ToolbeltTest"):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except OSError:
            pass
mine = hotkey.Helper("No such window 12345")
expect("Toolbelt's own Helper: start, then stop from Settings", mine.start() and mine.running())
mine.stop()
expect("…stopped", not mine.running())

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_hotkey)")
