"""Tests for pccare.py on this PC, read-only except one startup switch flipped and flipped back under a test name."""
import sys
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import pccare                                                 # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


progs = pccare.programs()
expect("the installed programs are read (%d found)" % len(progs), len(progs) >= 20 and all(p["name"] and p["uninstall"] or p["quiet"] for p in progs))
names = [p["name"] for p in progs]
expect("known ones are there: Git, AMD Software", any(n.startswith("Git") for n in names) and any("AMD" in n for n in names))
expect("no Windows updates in the list", not any(n.startswith("KB") or n.startswith("Update for") for n in names))
expect("sizes and dates where Windows knows them", any(p["size"] > 0 for p in progs) and any(p["date"] for p in progs))
expect("no duplicates (same name + version)", len({(p["name"].lower(), p["version"]) for p in progs}) == len(progs))
expect("each program knows its registry key and only real web links", all(p["key"].startswith("HKEY_") for p in progs)
       and all(not p[k] or p[k].startswith(("http://", "https://")) for p in progs for k in ("about", "help", "update")))
expect("some programs have an About link (the right-click menu)", any(p["about"] for p in progs))

s = pccare.startup()
expect("startup entries are read (%d), with on/off from Windows" % len(s), len(s) >= 3 and any(not e["enabled"] for e in s) and any(e["enabled"] for e in s))
expect("his Startup folder shortcuts are in it", any(e["where"] == "Startup folder" for e in s))
expect("all-users entries can't be switched here", all(not e["canToggle"] for e in s if e["id"].startswith("HKLM")))
test_id = "HKCU\\Run\\ToolbeltTestEntry"
r = pccare.set_startup(test_id, False)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pccare.APPROVED + r"\Run") as a:
    raw = winreg.QueryValueEx(a, "ToolbeltTestEntry")[0]
expect("switching off writes 03 the way Task Manager does", r["ok"] and raw[0] == 3 and len(raw) == 12)
r = pccare.set_startup(test_id, True)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pccare.APPROVED + r"\Run") as a:
    raw = winreg.QueryValueEx(a, "ToolbeltTestEntry")[0]
expect("switching on writes 02", r["ok"] and raw[0] == 2)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pccare.APPROVED + r"\Run", 0, winreg.KEY_SET_VALUE) as a:
    winreg.DeleteValue(a, "ToolbeltTestEntry")
expect("an all-users entry is refused politely", "admin" in pccare.set_startup("HKLM\\Run\\X", False)["message"])
# ---------- Windows apps ----------
apps = pccare.store_apps()
names = {a["package"]: a for a in apps}
expect("Windows apps are read (%d), with Start-menu names" % len(apps), len(apps) >= 10 and any(a["visible"] and a["appid"] for a in apps))
if "PythonSoftwareFoundation.PythonManager" in names:
    expect("the Python install manager is marked 'keep' (Toolbelt's Python comes from it)", names["PythonSoftwareFoundation.PythonManager"]["care"] == "danger")
expect("runtimes are marked 'keep'", all(a["care"] == "danger" for a in apps if a["package"].startswith("MicrosoftCorporationII.WinAppRuntime")))
expect("names are readable (no bare numbers)", not any(a["name"].strip().isdigit() for a in apps))
expect("a made-up package name is refused before Windows is asked", pccare.remove_store_app("not a package") == (False, "That isn't a Windows app package name."))

# ---------- the safety rails of the leftover remover ----------
import os                                                     # noqa: E402
L, A, PF = os.environ["LOCALAPPDATA"], os.environ["APPDATA"], os.environ["ProgramFiles"]
for path, why in ((L, "main folder"), (L + r"\Microsoft", "needs"), (L + r"\Toolbelt", "needs"), (PF + r"\Common Files", "needs"),
                  (str(Path.home()), "outside"), (os.environ["SystemRoot"], "outside"), (L + r"\Packages", "main folder"),
                  (L + r"\Packages\Microsoft.Windows.StartMenuExperienceHost_cw5n1h2txyewy", "needs")):
    expect("refused: %s (%s)" % (path.split("\\")[-1] or path, why), why in pccare.folder_refusal(path))
expect("an installed program's folder is refused (Git)", "still uses it" in pccare.folder_refusal(PF + r"\Git"))
if Path(A, ".minecraft").exists():
    expect("your Minecraft worlds folder is refused", "Minecraft" in pccare.folder_refusal(Path(A, ".minecraft")))
expect("a name search matches word starts only ('lock' doesn't find CustomClock)", not pccare.name_matches("lock", "CustomClock") and pccare.name_matches("clock", "CustomClock")
       and pccare.name_matches("minecraft", ".minecraft") and pccare.name_matches("github cli", "GitHub CLI"))

rp = pccare.restore_points()
expect("restore points can be listed (%d)" % len(rp), isinstance(rp, list))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_pccare)")
