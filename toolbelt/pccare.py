r"""PC care (step 9): the installed programs (for the Revo-style uninstaller), what starts with Windows, and restore points.

Everything is read from where Windows itself keeps it:
- programs: the registry's Uninstall keys (64-bit, 32-bit and per-user), the same list Settings > Apps shows;
- startup: the Run keys and the Startup folders, with Windows' own on/off switch (StartupApproved, 02 = on, 03 = off);
- a restore point needs admin, so Windows asks (UAC) once when that button is pressed.
"""
import os
import re
import subprocess
import time
import winreg
from pathlib import Path

NO_WINDOW = 0x08000000
UNINSTALL_KEYS = [(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "machine"),
                  (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "machine32"),
                  (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "user")]


def _value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _url(value):
    """Only real web links from a program's entry (the right-click menu opens them)."""
    value = str(value or "").strip()
    return value if re.match(r"(?i)^https?://[^\s\"'<>]+$", value) else ""


def programs():
    """Every installed program with version, company, size, date and how it uninstalls. Newest installed first."""
    out, seen = [], set()
    for hive, path, where in UNINSTALL_KEYS:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        name = _value(k, "DisplayName")
                        if not name or _value(k, "SystemComponent") == 1 or (_value(k, "ParentKeyName") and not _value(k, "UninstallString")):
                            continue
                        if _value(k, "ReleaseType") in ("Update", "Hotfix", "Security Update") or re.match(r"^(KB\d+|Update for|Security Update)", str(name)):
                            continue
                        uninstall = _value(k, "UninstallString") or ""
                        if not uninstall and not _value(k, "QuietUninstallString"):
                            continue
                        key_id = (str(name).strip().lower(), str(_value(k, "DisplayVersion") or ""))
                        if key_id in seen:
                            continue
                        seen.add(key_id)
                        size = _value(k, "EstimatedSize")
                        date = str(_value(k, "InstallDate") or "")
                        date = "%s-%s-%s" % (date[:4], date[4:6], date[6:8]) if re.match(r"^\d{8}$", date) else ""
                        icon = str(_value(k, "DisplayIcon") or "").split(",")[0].strip('"')
                        location = str(_value(k, "InstallLocation") or "").strip('"')
                        out.append({"id": "%s\\%s" % (where, sub), "name": str(name).strip(), "version": str(_value(k, "DisplayVersion") or ""),
                                    "publisher": str(_value(k, "Publisher") or ""), "size": int(size) * 1024 if isinstance(size, int) else 0,
                                    "date": date, "uninstall": uninstall, "quiet": _value(k, "QuietUninstallString") or "", "location": location,
                                    "icon": icon if icon and Path(icon).exists() else (location if location and Path(location).exists() else ""),
                                    "where": where, "msi": uninstall.lower().startswith("msiexec"),
                                    "key": "%s\\%s\\%s" % ("HKEY_CURRENT_USER" if hive == winreg.HKEY_CURRENT_USER else "HKEY_LOCAL_MACHINE", path, sub),
                                    "about": _url(_value(k, "URLInfoAbout")), "help": _url(_value(k, "HelpLink")), "update": _url(_value(k, "URLUpdateInfo"))})
                except OSError:
                    continue
    out.sort(key=lambda p: (p["date"], p["name"].lower()), reverse=True)
    return out


# Folders and keys that look like leftovers by name but that Windows, drivers, launchers or Toolbelt itself need.
PROTECTED_DIRS = {"microsoft", "windows", "windowsapps", "packages", "programs", "temp", "common files", "windows defender", "windows nt",
                  "windows mail", "windows media player", "windows photo viewer", "windows sidebar", "windowspowershell", "internet explorer",
                  "microsoft.net", "reference assemblies", "package cache", "toolbelt", "python", "pip", "nvidia", "nvidia corporation", "amd", "ati",
                  "intel", "realtek", "d3dscache", "crashdumps", "connecteddevicesplatform", "comms", "history", "virtualstore", "uninstall information",
                  "modifiablewindowsapps", "dotnet", "msbuild", "ssh", "regid.1991-06.com.microsoft", "usoshared", "ssh", "desktop.ini"}
PROTECTED_KEYS = {"microsoft", "classes", "policies", "wow6432node", "clients", "registeredapplications", "odbc", "intel", "amd", "ati technologies",
                  "nvidia corporation", "realtek", "python", "windows", "khronos", "partner", "defaultuserenvironment", "wow6432node"}


def _program_roots():
    roots = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData", "LOCALAPPDATA", "APPDATA")]
    roots.append(str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"))
    roots.append(str(Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"))
    return [str(Path(r)).lower().rstrip("\\") for r in roots if r]


_INSTALLED = {"at": 0.0, "items": [], "families": set()}
PROTECTED_PREFIX = ("microsoft", "windows")                   # Windows' own folders: never offered as leftovers by name


def all_families():
    """Every installed app package family, system and runtime ones included (their data folders are never leftovers)."""
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                               "(Get-AppxPackage -PackageTypeFilter Main,Framework,Resource,Bundle,Optional).PackageFamilyName | Sort-Object -Unique"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, creationflags=NO_WINDOW)
        return {line.strip().lower() for line in done.stdout.splitlines() if line.strip()}
    except Exception:
        return None                                            # unknown: then every Packages folder counts as in use


def installed_index(fresh=False):
    """Every installed thing: (name, folders it uses). Programs + Windows apps (their install and data folders).
    Cached for 60 s, so a leftover scan asks Windows once."""
    if not fresh and _INSTALLED["items"] and time.time() - _INSTALLED["at"] < 60:
        return _INSTALLED["items"]
    items = []
    for p in programs():
        dirs = [str(p.get("location") or ""), str(Path(p["icon"]).parent) if p.get("icon") and Path(p["icon"]).suffix else ""]
        items.append((p["name"], [d.lower().rstrip("\\") for d in dirs if d]))
    for a in store_apps():
        items.append((a["name"], [d.lower().rstrip("\\") for d in (a.get("location"), a.get("data")) if d]))
    for s in startup():                                       # things that start with Windows are in use too (his own widgets, 15 Oct)
        m = re.match(r'\s*"([^"]+)"', s.get("command") or "") or re.match(r"\s*(\S+\.exe)", s.get("command") or "", re.I)
        named = os.path.expandvars(m.group(1)) if m else ""
        if named and os.path.isabs(named) and not Path(named).exists():
            continue                                          # a startup entry whose program is gone protects nothing (it IS a leftover)
        items.append((s["name"], [str(Path(s["exe"]).parent).lower()] if s.get("exe") else []))
    _INSTALLED.update(at=time.time(), items=items, families=all_families())
    return items


def in_use(path):
    """The name of an installed program or app that uses this folder (by its folders, or by a folder named like it),
    else ''. Such folders can't be ticked or removed."""
    target = str(Path(path)).lower().rstrip("\\")
    leaf = Path(path).name.lower()
    index = installed_index()
    packages = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Packages").lower()
    if target.startswith(packages + "\\"):                  # an app's data folder: in use while any package of its family exists
        fams = _INSTALLED["families"]
        if fams is None or leaf in fams or leaf.endswith("_cw5n1h2txyewy"):
            return "Windows (an installed app package)"
    core = re.sub(r"[^a-z0-9]", "", leaf)
    for name, dirs in index:
        flat = re.sub(r"[^a-z0-9]", "", name.lower())
        if core and len(core) >= 4 and (any(core == re.sub(r"[^a-z0-9]", "", w) for w in name.lower().split())
                                        or (len(core) >= 6 and flat.startswith(core))):
            return name                                        # .minecraft ↔ Minecraft Launcher, CustomClock ↔ Custom Clock Feeder
    for name, dirs in index:
        for d in dirs:
            if d == target or d.startswith(target + "\\"):
                return name
        n = name.lower()
        if len(leaf) >= 3 and (leaf == n or n.startswith(leaf + " ") or leaf.startswith(n + " ") or leaf.split("_")[0] in [x.split("_")[0] for x in (Path(d).name for d in dirs)]):
            return name
    return ""


def key_in_use(key):
    r"""The installed program whose registry key this looks like (Software\Spotify ↔ Spotify), else ''."""
    leaf = str(key).split("\\")[-1]
    core = re.sub(r"[^a-z0-9]", "", leaf.lower())
    if len(core) < 3:
        return ""
    first = (_words(leaf) or [""])[0]
    for name, _dirs in installed_index():
        flat = re.sub(r"[^a-z0-9]", "", name.lower())
        words = [re.sub(r"[^a-z0-9]", "", w) for w in name.lower().split()]
        if core in words or flat.startswith(core) or (len(flat) >= 4 and core.startswith(flat)) or (len(first) >= 4 and flat.startswith(first)):
            return name                                        # ROBLOX Corporation ↔ RobloxPlayerBeta
    return ""


def folder_refusal(p):
    """Why this folder may not be deleted, or '' when it may: only folders strictly inside the program folders, never one
    of the protected ones, never a folder an installed program still uses."""
    p = Path(p)
    if not p.is_dir():
        return "not there"
    target = str(p).lower().rstrip("\\")
    roots = _program_roots()
    if target in roots:
        return "that is a main folder of Windows itself"
    parent = next((r for r in roots if target.startswith(r + "\\")), "")
    if not parent:
        return "outside the program folders"
    first = target[len(parent) + 1:].split("\\")[0]
    if first in PROTECTED_DIRS or p.name.lower() in PROTECTED_DIRS or first.startswith(PROTECTED_PREFIX) or p.name.lower().endswith("_cw5n1h2txyewy"):
        return "a folder Windows, a driver or Toolbelt needs"
    still = in_use(p)
    if still:
        return "%s still uses it" % still
    return ""


def _words(name):
    """CustomClock → ['custom', 'clock']; Microsoft.WindowsTerminal_8we → ['microsoft', 'windows', 'terminal', '8we']."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", str(name))
    return [w for w in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if w]


def name_matches(query, folder_name):
    """A name search matches the START of a word, so 'lock' doesn't find CustomClock (seen 15 Oct) but 'clock' does."""
    q = _words(query)
    if not q:
        return False
    w = _words(folder_name)
    for i in range(len(w)):
        if w[i].startswith(q[0]) and all(i + k < len(w) and w[i + k].startswith(q[k]) for k in range(1, len(q))):
            return True
    return "".join(q) == "".join(w)


# ---------- Windows (Store) apps (his ask, 15 Oct) ----------
# Packages that need care on HIS PC: a warning in the list, never hidden (he decides).
CAREFUL = {
    "PythonSoftwareFoundation.PythonManager": ("danger", "Toolbelt's own Python comes from this. Removing it breaks Toolbelt."),
    "Microsoft.WindowsStore": ("warn", "The Microsoft Store: without it you can't get these apps back easily."),
    "Microsoft.StorePurchaseApp": ("warn", "Part of the Microsoft Store."),
    "Microsoft.DesktopAppInstaller": ("warn", "winget and app installers use it."),
    "Microsoft.Winget.Source": ("warn", "winget's app list."),
    "Microsoft.GamingServices": ("danger", "Needed by the Xbox app and the Minecraft Launcher."),
    "Microsoft.XboxIdentityProvider": ("warn", "Xbox sign-in (Minecraft and Xbox games use it)."),
    "Microsoft.Xbox.TCUI": ("warn", "Xbox sign-in screens (Minecraft uses them)."),
    "Microsoft.XboxGamingOverlay": ("warn", "Game Bar: it records your Captures clips and the Win+G overlay."),
    "AdvancedMicroDevicesInc-RSXCM": ("danger", "Part of AMD Software (your graphics driver's control panel)."),
    "ASUSAmbientHAL64": ("warn", "Part of Armoury Crate / Aura lighting."),
    "RealtekSemiconductorCorp.RealtekAudioControl": ("warn", "Realtek Audio Console: your sound card's settings."),
    "Claude": ("warn", "The Claude app."),
    "MicrosoftWindows.Client.WebExperience": ("warn", "Widgets on the taskbar."),
    "Microsoft.Windows.Photos": ("info", "Windows' picture viewer; pictures still open in other apps."),
}
CAREFUL_PREFIX = [("MicrosoftCorporationII.WinAppRuntime", ("danger", "A runtime other apps need. Leave it.")),
                  ("Microsoft.VCLibs", ("danger", "A runtime other apps need. Leave it.")),
                  ("Microsoft.UI.Xaml", ("danger", "A runtime other apps need. Leave it.")),
                  ("Microsoft.NET", ("danger", "A runtime other apps need. Leave it."))]
CODEC_HINT = ("info", "A codec: Photos, Explorer thumbnails or videos use it for this format.")


def store_apps():
    """Windows apps for the current user, with their Start-menu name, icon id and a care note. Hidden parts flagged."""
    script = ("$start = @{}; Get-StartApps | ForEach-Object { $pfn = ($_.AppID -split '!')[0]; if (-not $start.ContainsKey($pfn)) { $start[$pfn] = $_ } }; "
              "@(Get-AppxPackage -PackageTypeFilter Main | Where-Object { -not $_.NonRemovable -and $_.SignatureKind -ne 'System' -and -not $_.IsFramework } | ForEach-Object { "
              "$s = $start[$_.PackageFamilyName]; [pscustomobject]@{Name=$_.Name; Full=$_.PackageFullName; Family=$_.PackageFamilyName; Version=$_.Version; "
              "Publisher=$_.Publisher; Kind=$_.SignatureKind; Display=$(if ($s) { $s.Name } else { '' }); AppID=$(if ($s) { $s.AppID } else { '' }); "
              "Location=$_.InstallLocation; Date=$(try { (Get-Item -LiteralPath $_.InstallLocation -ErrorAction Stop).CreationTime.ToString('yyyy-MM-dd') } catch { '' })} }) | ConvertTo-Json -Compress")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=90, creationflags=NO_WINDOW)
        import json
        data = json.loads(done.stdout.strip() or "[]")
        data = data if isinstance(data, list) else [data]
    except Exception:
        return []
    out = []
    local_packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
    for a in data:
        if not a:
            continue
        name = a.get("Name", "")
        care = CAREFUL.get(name)
        if not care:
            care = next((c for prefix, c in CAREFUL_PREFIX if name.startswith(prefix)), None)
        if not care and re.search(r"(Video|Image|Media)Extension", name):
            care = CODEC_HINT
        publisher = re.search(r"CN=([^,]+)", a.get("Publisher") or "")
        data_dir = local_packages / (a.get("Family") or "")
        out.append({"id": "appx\\" + (a.get("Full") or ""), "name": a.get("Display") or _nice_package(name), "package": name, "full": a.get("Full") or "",
                    "family": a.get("Family") or "", "version": str(a.get("Version") or ""), "publisher": publisher.group(1).strip('"') if publisher else "",
                    "date": a.get("Date") or "", "size": 0, "appid": a.get("AppID") or "", "visible": bool(a.get("AppID")),
                    "care": care[0] if care else "", "careWhy": care[1] if care else "", "data": str(data_dir) if data_dir.is_dir() else "",
                    "location": a.get("Location") or "", "icon": "", "where": "appx"})
    out.sort(key=lambda x: (not x["visible"], x["name"].lower()))
    return out


def _nice_package(name):
    """Microsoft.HEVCVideoExtension → HEVC Video Extension; MicrosoftCorporationII.WinAppRuntime.Main.1.8 → Win App Runtime Main 1.8."""
    rest = name.split(".", 1)[1] if "." in name else name
    rest = re.sub(r"\.(?!\d)|(?<!\d)\.", " ", rest)                     # dots become spaces, except inside version numbers
    rest = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", rest)
    return re.sub(r"\s+", " ", rest).strip() or name


def remove_store_app(full_name):
    """Remove-AppxPackage for this user (no admin). Returns (ok, message)."""
    if not re.match(r"^[\w.\-~]+_[\w.\-~]*_[\w.\-~]*_[\w.\-~]*_[\w]+$", str(full_name)):
        return False, "That isn't a Windows app package name."
    script = "Remove-AppxPackage -Package '%s' -ErrorAction Stop; 'OK'" % full_name.replace("'", "''")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=300, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, "Windows took too long removing it."
    if "OK" in done.stdout:
        return True, "Removed. Press Scan for leftovers to see if anything stayed behind."
    err = (done.stderr.strip().splitlines() or ["unknown error"])[0]
    return False, "Windows refused: %s" % err[:200]

# ---------- what starts with Windows ----------
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def startup():
    """Run keys and Startup folders, each with Windows' own on/off state."""
    out = []
    for hive, hname in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        approved = {}
        try:
            with winreg.OpenKey(hive, APPROVED + r"\Run") as a:
                i = 0
                while True:
                    try:
                        n, v, _t = winreg.EnumValue(a, i)
                    except OSError:
                        break
                    i += 1
                    approved[n.lower()] = not (isinstance(v, bytes) and v and v[0] % 2 == 1)      # 02 on, 03 off (odd = off)
        except OSError:
            pass
        try:
            with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                i = 0
                while True:
                    try:
                        n, v, _t = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    out.append({"id": "%s\\Run\\%s" % (hname, n), "name": n, "command": str(v), "where": "Registry (%s)" % ("you" if hname == "HKCU" else "all users"),
                                "enabled": approved.get(n.lower(), True), "canToggle": hname == "HKCU", "exe": _exe_of(str(v))})
        except OSError:
            pass
    for folder, hname in ((Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup", "HKCU"),
                          (Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs/StartUp", "HKLM")):
        if not folder.is_dir():
            continue
        approved = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER if hname == "HKCU" else winreg.HKEY_LOCAL_MACHINE, APPROVED + r"\StartupFolder") as a:
                i = 0
                while True:
                    try:
                        n, v, _t = winreg.EnumValue(a, i)
                    except OSError:
                        break
                    i += 1
                    approved[n.lower()] = not (isinstance(v, bytes) and v and v[0] % 2 == 1)
        except OSError:
            pass
        for entry in folder.iterdir():
            if entry.name.lower() == "desktop.ini" or not entry.is_file():
                continue
            out.append({"id": "%s\\StartupFolder\\%s" % (hname, entry.name), "name": entry.stem, "command": str(entry), "where": "Startup folder",
                        "enabled": approved.get(entry.name.lower(), True), "canToggle": hname == "HKCU", "exe": str(entry)})
    out.sort(key=lambda s: (not s["enabled"], s["name"].lower()))
    return out


def _exe_of(command):
    m = re.match(r'\s*"([^"]+)"', command) or re.match(r"\s*(\S+\.exe)", command, re.I)
    path = os.path.expandvars(m.group(1)) if m else ""
    return path if path and Path(path).exists() else ""


def set_startup(entry_id, enabled):
    """Switches an entry of yours on or off the way Task Manager does (the program stays installed)."""
    try:
        hname, kind, name = entry_id.split("\\", 2)
    except ValueError:
        return {"ok": False, "message": "Unknown entry."}
    if hname != "HKCU":
        return {"ok": False, "message": "That one starts for all users: switching it needs admin. Use Task Manager > Startup for it."}
    value = bytes([2 if enabled else 3]) + bytes(11)
    if not enabled:
        value = bytes([3]) + int(time.time() * 10000000 + 116444736000000000).to_bytes(8, "little") + bytes(3)
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APPROVED + "\\" + ("Run" if kind == "Run" else "StartupFolder")) as a:
            winreg.SetValueEx(a, name, 0, winreg.REG_BINARY, value)
        return {"ok": True, "message": ("%s starts with Windows again." if enabled else "%s no longer starts by itself. It stays installed.") % name}
    except OSError as error:
        return {"ok": False, "message": "Windows refused: %s" % error}


# ---------- restore point (admin) ----------
def restore_point(description="Toolbelt, before a change"):
    """Asks Windows (UAC) and makes a restore point. Windows allows one per 24 h unless told otherwise; that is reported."""
    script = ("Checkpoint-Computer -Description '%s' -RestorePointType MODIFY_SETTINGS; "
              "if ($?) { 'OK' } else { 'FAIL' }") % description.replace("'", "''")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                               "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile','-NonInteractive','-Command',\"%s\"" % script.replace('"', '`"')],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "message": "Couldn't ask Windows for a restore point: %s" % str(error)[:120]}
    if done.returncode != 0:
        return {"ok": False, "message": "No restore point: the admin question was cancelled, or System Protection is off (Settings > System > About > System protection)."}
    return {"ok": True, "message": "Restore point asked for. Windows makes at most one every 24 hours; if one exists already, it keeps that one."}


def restore_points():
    """The restore points Windows has (what you could go back to)."""
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-ComputerRestorePoint | Select-Object SequenceNumber,Description,@{n='When';e={$_.ConvertToDateTime($_.CreationTime).ToString('yyyy-MM-dd HH:mm')}} | ConvertTo-Json -Compress"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
        import json
        data = json.loads(done.stdout.strip() or "[]")
        return data if isinstance(data, list) else [data]
    except Exception:
        return []
