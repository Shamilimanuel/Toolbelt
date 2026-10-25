r"""Tests for leftscan.py, the Revo-style leftover scan: names, the rails, and one real round trip with made-up leftovers
(ZzToolbeltLeftoverTest: a registry key, a folder, a temp file, a dead startup entry, a deep key and a deep value) that
are scanned in all three modes and then removed, with .reg backups. Nothing of his is touched; the Recycle Bin is tried
once on a temp file, which is then taken out of the bin again."""
import json
import os
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import leftscan                                               # noqa: E402
import pccare                                                 # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- names ----------
expect("clean names: 'Copilot - 32-bit', '7-Zip 24.08 (x64)', 'Python 3.13.0 (64-bit)'",
       leftscan.clean_name("Copilot - 32-bit") == "Copilot" and leftscan.clean_name("7-Zip 24.08 (x64)") == "7-Zip" and leftscan.clean_name("Python 3.13.0 (64-bit)") == "Python")
expect("companies: 'Discord Inc.' → Discord, 'Valve Corporation' → Valve, Microsoft → '' (never a search word)",
       leftscan.clean_company("Discord Inc.") == "Discord" and leftscan.clean_company("Valve Corporation") == "Valve" and leftscan.clean_company("Microsoft Corporation") == "")
expect("top-level match by word starts (Git ↔ GitForWindows; 'lock' ↛ CustomClock)", leftscan.loose("Git", "GitForWindows") and not leftscan.loose("lock", "CustomClock"))
expect("deep match is strict (Copilot ↔ Copilot, W~MSCopilot; Git ↛ GitHub)", leftscan.strong("Copilot", "Copilot") and not leftscan.strong("Git", "GitHub")
       and leftscan.strong("Discord", "Discord.exe") and not leftscan.strong("ab", "ab"))
expect("install folder → the program's own folder (…\\Microsoft\\Copilot\\Application → …\\Microsoft\\Copilot)",
       str(leftscan._top_of(os.environ["ProgramFiles(x86)"] + r"\Microsoft\Copilot\Application", ["Copilot"])).endswith(r"Microsoft\Copilot"))
expect("an install folder that is Program Files itself gives nothing", leftscan._top_of(os.environ["ProgramFiles"] + r"\bin", ["x"]) is None)
expect("MSI 'modify' (/I) becomes remove (/X), like Revo", leftscan.uninstall_command({"uninstall": "MsiExec.exe /I{1234-AB}"}) == "MsiExec.exe /X{1234-AB}")
expect("the program file of a command line", leftscan._command_exe(r'"C:\x y\unins000.exe" /SILENT') == r"C:\x y\unins000.exe"
       and leftscan._command_exe(r"C:\x\Update.exe --uninstall") == r"C:\x\Update.exe")

# ---------- the rails: keys ----------
for hive, path in (("HKCU", "Software"), ("HKCU", r"Software\Microsoft"), ("HKLM", r"Software\Classes"), ("HKCU", r"Software\Policies\X"),
                   ("HKLM", r"Software\WOW6432Node\Policies\Microsoft\Windows\WindowsCopilot"), ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
                   ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"), ("HKLM", r"System\CurrentControlSet\Services\X"),
                   ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Installer\UserData\X"), ("HKCU", r"Software\Classes\CLSID\{1}")):
    expect("never deleted: %s\\%s" % (hive, path), leftscan.refusal({"kind": "key", "hive": hive, "path": path}) != "")
expect("a value that doesn't point to the program is refused", "only removes values" in leftscan.refusal(
    {"kind": "value", "hive": "HKCU", "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer", "name": "ShellState"}) or "already gone" in leftscan.refusal(
    {"kind": "value", "hive": "HKCU", "path": r"Software\Microsoft\Windows\CurrentVersion\Explorer", "name": "ShellState"}))
expect("a key's main value is never deleted", "main value" in leftscan.refusal({"kind": "value", "hive": "HKCU", "path": r"Software\X", "name": ""}))
expect("values inside a program's Uninstall entry are left alone", "entry" in leftscan.refusal(
    {"kind": "value", "hive": "HKLM", "path": r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{X}", "name": "InstallSource", "refRoot": "C:\\nope"}))
spotify = next((p for p in pccare.programs() if p["name"] == "Spotify"), None)
if spotify:
    expect("an installed program's key is in use (Software\\Spotify)", "still" in leftscan.refusal({"kind": "key", "hive": "HKCU", "path": r"Software\Spotify"}))

# ---------- the rails: files ----------
L, A, PF = os.environ["LOCALAPPDATA"], os.environ["APPDATA"], os.environ["ProgramFiles"]
for path, deep in ((L, True), (L + r"\Microsoft", True), (PF + r"\Common Files", True), (str(Path.home()), True), (os.environ["SystemRoot"], True),
                   (L + r"\Packages", True), (L + r"\Toolbelt", True), (A + r"\Microsoft\Windows\Start Menu\Programs\Startup", True),
                   (A + r"\Microsoft\Windows\Start Menu\Programs", True), (leftscan.temp_dir(), True)):
    expect("never deleted: %s" % path, leftscan.path_refusal(path, deep=deep) != "")
expect("inside Microsoft's folder only with Advanced ('Windows area') and a named folder", leftscan.path_refusal(L + r"\Microsoft\Edge", deep=False) != "")
if spotify:
    expect("an installed program's folder is in use (Spotify)", "still" in leftscan.path_refusal(A + r"\Spotify"))

# ---------- a real round trip with made-up leftovers ----------
NAME = "ZzToolbeltLeftoverTest"
HK = winreg.HKEY_CURRENT_USER
folder = Path(L) / NAME
area = r"Software\ZzToolbeltTestArea"
temp_file = Path(leftscan.temp_dir()) / (NAME + ".log")
run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"


def clean():
    for p in (folder, temp_file):
        if p.is_dir():
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    for path in (r"Software" + "\\" + NAME, area):
        try:
            leftscan._delete_key("HKCU", path)
        except OSError:
            pass
    try:
        with winreg.OpenKey(HK, run_key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, NAME)
    except OSError:
        pass


clean()
try:
    folder.mkdir()
    (folder / "settings.json").write_text("{}")
    temp_file.write_text("log")
    with winreg.CreateKey(HK, "Software\\" + NAME + "\\Window") as k:
        winreg.SetValueEx(k, "Width", 0, winreg.REG_DWORD, 800)
        winreg.SetValueEx(k, "Title", 0, winreg.REG_SZ, 'with "quotes" and \\ backslash')
    with winreg.CreateKey(HK, area + "\\Sub\\" + NAME) as k:
        winreg.SetValueEx(k, "x", 0, winreg.REG_SZ, "1")
    with winreg.CreateKey(HK, area + "\\Store") as k:
        winreg.SetValueEx(k, str(folder / "tool.exe"), 0, winreg.REG_BINARY, b"\x01\x02")
        winreg.SetValueEx(k, "Unrelated", 0, winreg.REG_SZ, "C:\\Windows\\notepad.exe")
    with winreg.OpenKey(HK, run_key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, '"C:\\Nowhere\\%s\\%s.exe" --tray' % (NAME, NAME))

    prof = leftscan.profile_for_name(NAME)
    seen = {}
    for mode in leftscan.MODES:
        t = time.time()
        steps = []
        seen[mode] = leftscan.scan(prof, mode, lambda pct, text: steps.append(pct))
        print("      (%s: %.1f s, %d registry, %d files)" % (mode, time.time() - t, len(seen[mode]["registry"]), len(seen[mode]["files"])))
    keyset = lambda r: {(i["hive"], i["path"], i["name"]) for i in r["registry"]}
    pathset = lambda r: {i["path"].lower() for i in r["files"]}
    s, m, a = seen["safe"], seen["moderate"], seen["advanced"]
    expect("safe: its key and its AppData folder", ("HKCU", "Software\\" + NAME, "") in keyset(s) and str(folder).lower() in pathset(s))
    expect("safe: not yet the temp file or the startup entry", str(temp_file).lower() not in pathset(s) and not any(i["name"] == NAME for i in s["registry"]))
    expect("moderate: + the temp file and the dead startup entry", str(temp_file).lower() in pathset(m) and ("HKCU", run_key, NAME) in keyset(m))
    expect("moderate: not yet the deep key", ("HKCU", area + "\\Sub\\" + NAME, "") not in keyset(m))
    expect("advanced: + the key deep in the registry and the value whose name is a path into its folder %s" % sorted(keyset(a)),
           ("HKCU", area + "\\Sub\\" + NAME, "") in keyset(a) and ("HKCU", area + "\\Store", str(folder / "tool.exe")) in keyset(a))
    expect("advanced: a value pointing elsewhere is not offered", not any(i["name"] == "Unrelated" for i in a["registry"]))
    expect("nothing of it is 'in use' %s" % [(i.get("path"), i.get("name"), i["inUse"]) for i in a["registry"] + a["files"] if i["inUse"]],
           all(not i["inUse"] for i in a["registry"] + a["files"]))
    key_item = next(i for i in a["registry"] if i["path"] == "Software\\" + NAME)
    expect("a found key shows what's inside it (Revo's tree)", key_item["more"] >= 1)
    expect("every item says how big it is (key with its values: %d bytes; folder: %d bytes)" % (key_item["size"], next(i["size"] for i in a["files"] if i["kind"] == "folder")),
           all(i["size"] > 0 for i in a["registry"] + a["files"]) and key_item["size"] > 60 and next(i["size"] for i in a["files"] if i["kind"] == "folder") == 2)

    # remove everything found, through the helper's command line (the same code the elevated helper runs)
    items = [dict(i, id="r%d" % n) for n, i in enumerate(a["registry"])] + [dict(i, id="f%d" % n) for n, i in enumerate(a["files"])]
    with tempfile.TemporaryDirectory() as tmp:
        job, out, bk = Path(tmp) / "job.json", Path(tmp) / "out.json", Path(tmp) / "backup"
        res = leftscan.remove(items[:1], bk, to_bin=False)
        expect("remove(): the first item goes, with a .reg backup", res["done"] == ["r0"] and list(bk.glob("*.reg")))
        job.write_text(json.dumps({"items": items[1:], "backup": str(bk)}), encoding="utf-8")
        subprocess.run([sys.executable, str(Path(leftscan.__file__)), "--remove", str(job), str(out)], timeout=120, check=False)
        res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"done": [], "failed": [["?", "no answer"]]}
        expect("the helper (what runs as admin) removes the rest: %s" % (res.get("failed") or "all"), not res["failed"] and not res["needAdmin"] and len(res["done"]) == len(items) - 1)
        texts = [f.read_text(encoding="utf-16") for f in bk.glob("*.reg")]
        expect("every registry item has a .reg backup that regedit can read", len(texts) == len(a["registry"]) and all(t.startswith("\ufeffWindows Registry Editor Version 5.00") or t.startswith("Windows Registry Editor Version 5.00") for t in texts))
        expect("the backup keeps values exactly (dword, quotes, backslashes)", any('"Width"=dword:00000320' in t for t in texts) and any(r'\"quotes\" and \\ backslash' in t for t in texts))
    after = leftscan.scan(prof, "advanced")
    expect("scanning again finds nothing left", not after["registry"] and not after["files"])
    try:
        winreg.OpenKey(HK, area + "\\Store").Close()
        expect("the unrelated value next to it is still there", any(n == "Unrelated" for n, _d, _t in leftscan._values("HKCU", area + "\\Store")))
    except OSError:
        expect("the unrelated value next to it is still there", False)

    # the Recycle Bin, once, on a temp file (then taken back out of the bin)
    bin_file = Path(leftscan.temp_dir()) / (NAME + " bin.txt")
    bin_file.write_text("x")
    code = leftscan.recycle(bin_file)
    expect("files go to the Recycle Bin (code %s)" % code, code == 0 and not bin_file.exists())
    sid = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout.strip().split(",")[-1].strip('"')
    purged = 0
    for drive_bin in [Path(bin_file.drive + "\\$Recycle.Bin") / sid]:
        for info in drive_bin.glob("$I*"):
            try:
                if (NAME + " bin.txt") in info.read_bytes()[24:].decode("utf-16-le", "ignore"):
                    (drive_bin / ("$R" + info.name[2:])).unlink(missing_ok=True)
                    info.unlink()
                    purged += 1
            except OSError:
                pass
    print("      (taken back out of the Recycle Bin: %d)" % purged)
finally:
    clean()

# ---------- the flow (Session) with a pretend uninstaller ----------
class FakeProc:
    def __init__(self):
        self.n = 0

    def poll(self):
        self.n += 1
        return None if self.n < 3 else 0


sess = leftscan.Session()
r = sess.begin("Pretend", leftscan.profile_for_name("Pretend Program"), lambda: {"ok": True, "message": "made"}, FakeProc, lambda: False)
expect("a second uninstall can't start meanwhile", not sess.begin("x", leftscan.profile_for_name("xyz"), None, FakeProc)["ok"])
for _ in range(50):
    if sess.status()["phase"] == "uninstalled":
        break
    time.sleep(0.1)
st = sess.status()
expect("the steps: restore point done, uninstaller done, then it waits for Scan", r["ok"] and [s["state"] for s in st["steps"]] == ["done", "done", "todo"] and st["phase"] == "uninstalled")
expect("Windows no longer lists it (checked after the uninstaller)", st["listed"] is False)
sess.scan("safe")
for _ in range(600):
    if sess.status()["phase"] != "scanning":
        break
    time.sleep(0.1)
res = sess.result()
expect("scan → a result, every item with an id (%s)" % sess.status()["phase"], res.get("ok") and all(i.get("id") for i in res["registry"] + res["files"]))
expect("ids the scan didn't give can't be deleted", sess.delete(["r999"])["ok"] is False)
sess2 = leftscan.Session()
sess2.begin("Failing", leftscan.profile_for_name("Pretend Program"), lambda: {"ok": False, "message": "System Protection is off"}, FakeProc)
for _ in range(30):
    if sess2.status()["phase"] == "rp-failed":
        break
    time.sleep(0.1)
expect("a failed restore point stops and asks first", sess2.status()["phase"] == "rp-failed")
sess2.go_on_without_rp()
for _ in range(50):
    if sess2.status()["phase"] == "uninstalled":
        break
    time.sleep(0.1)
expect("…and goes on only when told", [s["state"] for s in sess2.status()["steps"]][:2] == ["skipped", "done"])
expect("a hunt needs 3 letters and never hunts for Windows itself", "3 letters" in leftscan.Session().hunt("ab", "safe")["message"] and "Windows" in leftscan.Session().hunt("Microsoft", "safe")["message"])
proc = leftscan.launch_uninstaller({"uninstall": "cmd.exe /c exit 3"})
expect("the uninstaller is started and watched until it closes", proc.wait(timeout=10) == 3)

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_leftscan)")
