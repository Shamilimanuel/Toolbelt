"""App guard's scans (his ask, 18 Oct: "also add a scan too"; he picked all four, plus the USB stick and Downloads checks).

- Program check: Toolbelt's own scan of the places programs hide or arrive (Downloads, Desktop, the Startup folders,
  what the Run keys start, Temp). Every program file and every disguised file gets App guard's checks: signature
  (one PowerShell call for the whole list), disguised name, Mark of the Web, and a Defender scan of the risky ones.
- Defender quick / full scan: Microsoft Defender's own scans (MpCmdRun, no admin). Defender handles what it finds
  itself; Toolbelt shows the detections afterwards. Cancelling needs admin (seen 18 Oct: 0x80070005), so there's no Cancel.
- Folder or drive: Defender scans that folder and reports (it removes nothing; he decides), plus App guard's checks.
- USB stick: the same folder scan, started by itself when a stick is plugged in, plus the old USB tricks: autorun.inf
  and shortcuts that start cmd / PowerShell / wscript.
- Downloads: each new download is checked as soon as it's complete; a warning only when something is wrong.
Nothing is uploaded; nothing is deleted without him.
"""
import ctypes
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import appguard

NO_WINDOW = 0x08000000
EXEC_EXT = {".exe", ".msi", ".scr", ".com", ".pif", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta", ".jar", ".lnk"}
SIGNABLE = {".exe", ".msi", ".scr", ".com", ".ps1", ".vbs", ".js", ".cab", ".dll", ".sys"}
PARTIAL = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}
FOLDERS = {"downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
           "startup": "{B97D20BB-F46A-4C97-BA10-5E3608430854}", "common_startup": "{82A5EA35-D9CD-47C5-9629-E15D2F714E6E}"}


class _GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]


def known_folder(name):
    """Windows' own idea of where Downloads / Desktop / Startup are (they can be moved to another drive)."""
    u = uuid.UUID(FOLDERS[name])
    g = _GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    out = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
            path = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except OSError:
        pass
    return None


def _walk(folder, depth, limit):
    """Files under folder, at most `depth` folders down, at most `limit` of them."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found, stack = [], [(folder, 0)]
    while stack and len(found) < limit:
        here, d = stack.pop()
        try:
            for entry in os.scandir(here):
                if entry.is_file(follow_symlinks=False):
                    found.append(Path(entry.path))
                    if len(found) >= limit:
                        break
                elif entry.is_dir(follow_symlinks=False) and d < depth and not entry.name.startswith("$"):
                    stack.append((Path(entry.path), d + 1))
        except OSError:
            continue
    return found


def _run_key_targets():
    """The programs the Run / RunOnce keys start (his and the machine's; reading needs no admin)."""
    import winreg
    out = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for sub in (r"Software\Microsoft\Windows\CurrentVersion\Run", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        cmd = os.path.expandvars(str(winreg.EnumValue(key, i)[1]))
                        m = re.match(r'^\s*"([^"]+)"|^\s*(\S+\.(?:exe|bat|cmd|vbs|ps1|js))', cmd, re.I)
                        if m:
                            out.append(Path(m.group(1) or m.group(2)))
            except OSError:
                continue
    return [p for p in out if p.is_file()]


def interesting(path):
    """A program file, or any file whose name pretends to be something else (photo.jpg.exe, report.pdf .scr …)."""
    name = path.name.lower()
    if path.suffix.lower() in EXEC_EXT:
        return True
    parts = name.split(".")
    return len(parts) >= 3 and "." + parts[-1] in EXEC_EXT


def program_places():
    """(label, files) for the Program check."""
    temp = Path(os.environ.get("TEMP", ""))
    places = [("Downloads", _walk(known_folder("downloads") or Path.home() / "Downloads", 3, 20000)),
              ("Desktop", _walk(known_folder("desktop") or Path.home() / "Desktop", 2, 5000)),
              ("Startup", _walk(known_folder("startup") or Path(), 1, 500) + _walk(known_folder("common_startup") or Path(), 1, 500) + _run_key_targets()),
              ("Temp", _walk(temp, 1, 20000) if temp.is_dir() else [])]
    return [(label, [f for f in files if interesting(f)]) for label, files in places]


def signatures(paths, chunk=150):
    """Windows' signature check for many files in one PowerShell call per chunk: {path: check.signature-like dict}."""
    out = {}
    paths = [str(p) for p in paths if Path(p).suffix.lower() in SIGNABLE]
    for i in range(0, len(paths), chunk):
        part = paths[i:i + chunk]
        listing = ",".join("'%s'" % p.replace("'", "''") for p in part)
        script = ("@(%s) | ForEach-Object { $s = Get-AuthenticodeSignature -LiteralPath $_ -ErrorAction SilentlyContinue; "
                  "[pscustomobject]@{P=$_; S=if($s){$s.Status.ToString()}else{'UnknownError'}; N=if($s -and $s.SignerCertificate){$s.SignerCertificate.Subject}else{''}} } | ConvertTo-Json -Compress") % listing
        try:
            done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=300, creationflags=NO_WINDOW)
            data = json.loads(done.stdout.strip() or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
        for row in data if isinstance(data, list) else [data]:
            cn = re.search(r"CN=\"?([^,\"]+)", row.get("N") or "")
            out[row.get("P")] = {"status": row.get("S", ""), "signer": cn.group(1) if cn else "", "title": {"HashMismatch": "Changed after signing", "NotTrusted": "Signed, but the signer isn't trusted"}.get(row.get("S"), row.get("S", ""))}
    return out


def check_files(job, files, guard=None, scan=True, label="", start=0.0, span=100.0):
    """App guard's checks on a list of (place, path). Returns findings (risky first) and how many looked fine."""
    import check
    files = [(place, Path(p)) for place, p in files]
    trusted = {appguard._key(t["path"]) for t in (guard.data["trusted"] if guard else [])}
    sigs = signatures([p for _, p in files])
    findings, fine = [], 0
    for i, (place, path) in enumerate(files):
        if job:
            job.check()
            job.report(start + span * i / max(len(files), 1), "%s: %d of %d · %s" % (label or "Checking", i + 1, len(files), path.name[:40]))
        if appguard._key(path) in trusted or not path.is_file():
            continue
        sig = sigs.get(str(path)) or {"status": "NotSignable" if path.suffix.lower() not in SIGNABLE else "UnknownError", "signer": "", "title": ""}
        risky_name = check.sniff(path).get("verdict") == "danger"
        web = appguard.mark_of_the_web(path)
        do_scan = scan and (sig["status"] != "Valid" or risky_name or web["internet"])
        r = appguard.inspect(path, scan=do_scan, signature=lambda p, s=sig: s)
        if path.suffix.lower() == ".lnk" and not risky_name:
            target = shortcut_target(path)
            if re.search(r"\\(cmd|powershell|pwsh|wscript|cscript|mshta|rundll32)\.exe$", target or "", re.I):
                r["checks"].insert(0, ["bad", "A shortcut that starts %s: a trick USB worms use" % Path(target).name])
                r["verdict"] = "danger"
            elif r["verdict"] != "danger":
                fine += 1
                continue
        if r["verdict"] == "safe" or (r["verdict"] == "unknown" and sig["status"] == "NotSignable" and not risky_name and not web["internet"]):
            fine += 1                                          # signed, or a script / shortcut made on this PC: nothing to say
            continue
        findings.append({"path": str(path), "name": path.name, "place": place, "verdict": r["verdict"], "checks": r["checks"],
                         "size": path.stat().st_size if path.exists() else 0})
    findings.sort(key=lambda f: (f["verdict"] != "danger", f["place"], f["name"].lower()))
    return findings, fine


def shortcut_target(lnk):
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                               "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % str(lnk).replace("'", "''")],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, creationflags=NO_WINDOW)
        return done.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def parse_threats(text):
    """MpCmdRun's list of detected threats: [{name, files: [...]}]."""
    threats, cur = [], None
    for line in text.splitlines():
        m = re.match(r"\s*Threat\s*:\s*(.+)", line)
        if m:
            cur = {"name": m.group(1).strip(), "files": []}
            threats.append(cur)
            continue
        m = re.match(r"\s*file\s*:\s*(.+)", line, re.I)
        if m and cur is not None:
            cur["files"].append(m.group(1).strip())
    return threats


def defender(job, kind, folder=None, remediate=True):
    """Runs one Defender scan: kind quick / full / folder. Reports elapsed time (Defender gives no percentage)."""
    if not appguard.DEFENDER.exists():
        raise RuntimeError("Microsoft Defender's scanner (MpCmdRun.exe) isn't there.")
    args = [str(appguard.DEFENDER), "-Scan", "-ScanType", {"quick": "1", "full": "2", "folder": "3"}[kind]]
    if kind == "folder":
        args += ["-File", str(folder)]
    if not remediate:
        args += ["-DisableRemediation"]
    began = time.time()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    lines = []
    import threading
    reader = threading.Thread(target=lambda: lines.extend(proc.stdout), daemon=True)
    reader.start()
    expect = {"quick": 300, "full": 3600, "folder": 120}[kind]
    while proc.poll() is None:
        if job:
            job.report(min(95.0, 95 * (time.time() - began) / expect), "Defender %s scan · %d:%02d so far" % ({"quick": "quick", "full": "full", "folder": "folder"}[kind], (time.time() - began) // 60, (time.time() - began) % 60))
            if job.cancelled():
                proc.kill()                                    # stops waiting; Defender itself may finish the scan (cancelling needs admin)
                break
        time.sleep(1)
    reader.join(5)
    text = "".join(lines)
    return {"threats": parse_threats(text), "code": proc.returncode, "seconds": int(time.time() - began), "clean": "found no threats" in text}


def usb_tricks(root):
    """The classic USB stick tricks at the top of a drive: autorun.inf and look-alike shortcuts."""
    root = Path(root)
    found = []
    if (root / "autorun.inf").exists():
        found.append({"path": str(root / "autorun.inf"), "name": "autorun.inf", "place": "USB stick", "verdict": "danger", "size": 0,
                      "checks": [["bad", "autorun.inf: tries to start something when the stick is opened (Windows ignores it, but it's a bad sign)"]]})
    return found


def removable_drives():
    """Drive letters of USB sticks and memory cards right now."""
    out = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if mask & (1 << i):
            root = "%s:\\" % chr(65 + i)
            if ctypes.windll.kernel32.GetDriveTypeW(root) == 2:                # DRIVE_REMOVABLE
                out.append(root)
    return out


def drive_label(root):
    buf = ctypes.create_unicode_buffer(261)
    try:
        ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0)
    except OSError:
        pass
    return buf.value or "USB stick"
