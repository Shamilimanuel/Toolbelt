"""The installer (setup.ps1 / Install.cmd, 25 Oct) for real, but only in temporary folders and under a test name in
Settings > Apps: install (Python found, app copied, its own Python folder made, the Apps entry), install again (an
update keeps the data), uninstall (app, Apps entry and data gone). Packages, starting Toolbelt and undoing this PC's
real Windows changes are skipped; undo_windows_changes is checked with stand-ins instead."""
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


REG = "ToolbeltSetupTest"
KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" % REG


def setup(*args):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "setup.ps1"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, creationflags=0x08000000)


def reg_values():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            return {n: winreg.QueryValueEx(k, n)[0] for n in ("DisplayName", "DisplayVersion", "UninstallString", "InstallLocation", "DisplayIcon")}
    except OSError:
        return None


with tempfile.TemporaryDirectory(prefix="toolbelt-setup-") as tmp:
    target, data = Path(tmp) / "Programs" / "Toolbelt", Path(tmp) / "Data"
    common = ["-Target", str(target), "-Data", str(data), "-RegName", REG, "-Yes"]
    try:
        r = setup(*common, "-NoStart", "-SkipPackages")
        expect("install finishes (exit 0)", r.returncode == 0)
        expect("Python 3.12+ is found", "Python:" in r.stdout)
        expect("the app is copied: main.py, toolbelt\\, web\\, setup.ps1", all((target / f).exists() for f in ("main.py", "toolbelt/apps.py", "web/index.html", "setup.ps1", "requirements.txt")))
        expect("no notes or private files come along", not (target / "status.md").exists() and not (target / "docs").exists() and not (target / "publish_public.py").exists())
        venv_py = data / "venv" / "Scripts" / "python.exe"
        expect("Toolbelt's own Python folder is made", venv_py.exists() and subprocess.run([str(venv_py), "-c", "print(1)"], capture_output=True, text=True).stdout.strip() == "1")
        v = reg_values() or {}
        expect("it's in Settings > Apps with an Uninstall command that names its folders", v.get("DisplayName") == "Toolbelt" and "-Uninstall" in v.get("UninstallString", "") and REG in v.get("UninstallString", "")
               and str(target) in v.get("UninstallString", "") and str(data) in v.get("UninstallString", "")
               and v.get("InstallLocation") == str(target) and Path(v.get("DisplayIcon", "x")).exists())
        expect("its version is read from main.py", v.get("DisplayVersion", "").startswith("1."))
        (data / "settings.json").write_text("{}", encoding="utf-8")
        (target / "toolbelt" / "old_module.py").write_text("", encoding="utf-8")
        r = setup(*common, "-NoStart", "-SkipPackages")
        expect("installing again (an update) replaces the code but keeps the data", r.returncode == 0 and not (target / "toolbelt" / "old_module.py").exists() and (data / "settings.json").exists())
        (data / "quarantine").mkdir()
        (data / "quarantine" / "x.exe.blocked").write_bytes(b"x")
        r = setup(*common, "-Uninstall", "-SkipCleanup")
        expect("uninstall finishes", r.returncode == 0 and "uninstalled" in r.stdout)
        expect("it warns about quarantined files before removing the data", "quarantine" in r.stdout and "gone for good" in r.stdout)
        expect("the app, the Apps entry and (on yes) the data are gone", not target.exists() and reg_values() is None and not data.exists())
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY)
        except OSError:
            pass

# main.py --uninstall: what it puts back, with stand-ins (the real ones would change this PC)
import main                                                    # noqa: E402

calls = []


class Nets:
    def installed(self):
        return "Ethernet"

    def remove(self):
        calls.append("net")
        return {"ok": True, "message": "removed"}


class Keys:
    KEY_LETTER = "W"

    def set_windows_wint(self, off):
        calls.append(("wint", off))
        return True


class Mark:
    def calc_key(self, command):
        calls.append(("calc", command))

    def remove_shortcuts(self):
        calls.append("shortcuts")
        return ["Toolbelt.lnk"]


said = main.undo_windows_changes({"calc_key": True, "win_t": True}, Nets(), Keys(), Mark())
expect("--uninstall puts back the Calculator key, Win+W, the internet switch and the shortcuts",
       calls == [("calc", None), ("wint", False), "net", "shortcuts"] and len(said) == 4)
calls.clear()
said = main.undo_windows_changes({"calc_key": False, "win_t": False}, type("N", (), {"installed": lambda s: None})(), Keys(), Mark())
expect("…and leaves alone what Toolbelt never changed", calls == ["shortcuts"])

with tempfile.TemporaryDirectory() as tmp:
    import brand                                               # noqa: E402
    start = Path(tmp) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start.mkdir(parents=True)
    (start / "Toolbelt.lnk").write_bytes(b"xx" + "C:\\x\\main.py".encode("utf-16-le"))
    (start / "Calculator.lnk").write_bytes(b"another calculator app")
    gone = brand.remove_shortcuts(tmp)
    expect("only shortcuts that point at Toolbelt are removed", gone == ["Toolbelt.lnk"] and (start / "Calculator.lnk").exists())

print("ALL PASSED (test_setup)" if not failures else "%d FAILED: %s" % (len(failures), ", ".join(failures)))
sys.exit(1 if failures else 0)
