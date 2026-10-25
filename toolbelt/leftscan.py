r"""The Revo-style uninstall flow (his ask, 15 Oct): restore point, the program's own uninstaller, then a leftover scan
in three depths, shown as a registry tree and a files tree with tick boxes.

Safe      the program's own folders (its install folder, Program Files / ProgramData / AppData by name, also inside its
          company's folder, a Windows app's data folder) and its own registry keys (Software\<name>,
          Software\<company>\<name>, its Uninstall entry once the uninstaller is gone).
Moderate  + Start-menu and desktop shortcuts, temp files, file types and links (Classes), App Paths, startup entries.
Advanced  + a walk through the whole registry (HKCU\Software, HKLM\Software) for keys named after it and values pointing
          into its install folder, and folders named after it inside the Microsoft / Windows folders ("Windows area").

Only remove() deletes, and only items a scan reported (the page sends ids, the items stay here). Every item is checked
again against the rails right before: Windows' main folders and keys, pccare's protected lists, and "still in use" by
anything installed. Registry items are exported to a .reg file first (backups in %LOCALAPPDATA%\Toolbelt\backups),
files and folders go to the Recycle Bin. What needs admin is done by this same file started elevated (one UAC question),
which re-checks every item itself.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
import winreg
from ctypes import wintypes
from pathlib import Path

import pccare

DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Toolbelt"
HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
MODES = ("safe", "moderate", "advanced")
NO_WINDOW = 0x08000000

# folder names that say nothing about the program (C:\...\Copilot\Application → the program's folder is Copilot)
GENERIC = {"application", "app", "apps", "bin", "bin64", "bin32", "program", "programs", "x64", "x86", "amd64", "win64", "win32",
           "current", "files", "common", "data", "lib", "runtime", "client", "release", "stable", "main", "install", "installer"}
# registry key names that are Windows' own furniture: never deleted, whatever matched
STRUCTURAL = {"software", "microsoft", "windows", "windows nt", "currentversion", "run", "runonce", "uninstall", "app paths", "explorer",
              "shell", "shell folders", "user shell folders", "classes", "applications", "policies", "services", "control", "appcompatflags",
              "compatibility assistant", "store", "layers", "muicache", "userassist", "startupapproved", "capabilities",
              "registeredapplications", "wow6432node", "fileexts", "openwithlist", "openwithprogids", "shellex", "defaulticon", "command",
              "open", "clsid", "interface", "typelib", "appid", "bags", "bagmru", "notifications", "settings", "winlogon", "appx", "appmodel",
              "packages", "repository", "system", "setup", "default", "config", "local settings", "internet settings", "installer",
              "run32", "startupfolder", "currentcontrolset", "users", "volatile environment", "environment", "console", "keyboard layout"}
# whole registry areas the scan never walks into and remove() never touches (Windows Installer, servicing, apps' bookkeeping)
DEEP_SKIP = (r"software\microsoft\windows\currentversion\installer", r"software\classes\installer", r"software\microsoft\windows\currentversion\appx",
             r"software\microsoft\windows\currentversion\appmodel", r"software\microsoft\windows nt\currentversion\profilelist",
             r"software\microsoft\cryptography", r"software\microsoft\windows defender", r"software\microsoft\windows\currentversion\winevt",
             r"software\policies", r"software\microsoft\windows\currentversion\sidebyside", r"software\microsoft\windows\currentversion\setup",
             r"software\microsoft\windows nt\currentversion\image file execution options", r"software\microsoft\windows\currentversion\component based servicing",
             r"software\classes\local settings", r"software\microsoft\windows\currentversion\deliveryoptimization",
             r"software\microsoft\windows nt\currentversion\winlogon", r"software\microsoft\windows nt\currentversion\svchost",
             r"software\microsoft\windows search", r"software\classes\clsid", r"software\classes\interface", r"software\classes\typelib",
             r"software\microsoft\windows\currentversion\explorer\fileexts", r"software\microsoft\windows\currentversion\explorer\userassist")
WINDOWS_AREA = {"microsoft", "windows", "windows nt"}
START_KEEP = {"startup", "accessibility", "accessories", "administrative tools", "system tools", "windows powershell", "windows tools",
              "maintenance", "windows accessories", "windows administrative tools", "windows ease of access", "windows system"}
UNINSTALL_ROOTS = (("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"), ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                   ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"))
RUN_KEYS = [(h, p + "\\" + r) for h in ("HKCU", "HKLM") for p in (r"Software\Microsoft\Windows\CurrentVersion", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion")
            for r in ("Run", "RunOnce")]
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
PATH_IN_TEXT = re.compile(r"[A-Za-z]:\\[^\"*?<>|\r\n]+")


# ---------- names ----------
def _flat(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def clean_name(name):
    """'Copilot - 32-bit' → Copilot; '7-Zip 24.08 (x64)' → 7-Zip; 'Python 3.13.0 (64-bit)' → Python."""
    n = re.sub(r"\(.*?\)|\[.*?\]", " ", str(name or ""))
    n = re.sub(r"\s+[-–—]\s+.*$", "", n)
    n = re.sub(r"(?i)\b(x64|x86|amd64|arm64|64-bit|32-bit|v?\d+(?:\.\d+)+)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip(" .-_,")


def clean_company(publisher):
    """'Discord Inc.' → Discord; 'Valve Corporation' → Valve. Windows' own makers (Microsoft…) give ''."""
    c = re.sub(r"(?i)[,.]?\s*\b(inc|incorporated|ltd|limited|llc|corp|corporation|co|gmbh|b\.?v|s\.?a|ag|pty|plc|s\.?r\.?l)\b\.?", " ", str(publisher or ""))
    c = re.sub(r"\s+", " ", c).strip(" .,-")
    return "" if _protected_name(c) or len(_flat(c)) < 3 else c


def _protected_name(name):
    low = str(name).strip().lower()
    return low in pccare.PROTECTED_DIRS or low in pccare.PROTECTED_KEYS or low.startswith(pccare.PROTECTED_PREFIX) or _flat(low) in {_flat(x) for x in pccare.PROTECTED_KEYS}


def loose(needle, name):
    """Top-level match: the name's words start like the needle's (Git → Git, GitForWindows; 'lock' ↛ CustomClock)."""
    return len(_flat(needle)) >= 3 and pccare.name_matches(needle, name)


def strong(needle, name):
    """Deep-scan match, stricter: the same name, or (for longer names) the same words at the start."""
    n, l = _flat(needle), _flat(name)
    if len(n) < 3 or not l:
        return False
    if n == l:
        return True
    return len(n) >= 6 and pccare.name_matches(needle, name) and len(l) <= len(n) + 12


def _generic(name):
    low = name.lower()
    return low in GENERIC or bool(re.fullmatch(r"(app-)?v?\d+([._]\d+)*", low))


# ---------- where things live ----------
def _shell_folder(name, fallback):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return os.path.expandvars(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return fallback


def start_menus():
    return [str(Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"),
            str(Path(os.environ.get("ProgramData", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs")]


def desktops():
    return [_shell_folder("Desktop", str(Path.home() / "Desktop")), str(Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop")]


def temp_dir():
    return os.environ.get("TEMP") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Temp")


def local_low():
    return str(Path(os.environ.get("USERPROFILE", str(Path.home()))) / "AppData" / "LocalLow")


def all_roots():
    """(folder, kind), most specific first: kind is program, start, desktop or temp."""
    roots = [(r, "program") for r in pccare._program_roots()] + [(local_low().lower(), "program")]
    roots += [(str(Path(r)).lower().rstrip("\\"), "start") for r in start_menus()]
    roots += [(str(Path(r)).lower().rstrip("\\"), "desktop") for r in desktops()]
    roots.append((str(Path(temp_dir())).lower().rstrip("\\"), "temp"))
    seen, out = set(), []
    for r, kind in sorted(roots, key=lambda x: -len(x[0])):
        if r and r not in seen:
            seen.add(r)
            out.append((r, kind))
    return out


def _command_exe(command):
    """The program file of a command line: '"C:\\x\\unins000.exe" /SILENT' → C:\\x\\unins000.exe."""
    command = os.path.expandvars(str(command or "")).strip()
    m = re.match(r'\s*"([^"]+)"', command) or re.match(r"\s*(.+?\.(exe|dll|bat|cmd))\b", command, re.I)
    return m.group(1) if m else ""


def _uninstall_alive(hive, path):
    """An Uninstall entry still belongs to something installed when its uninstaller is still there (MSI ones always count)."""
    try:
        with winreg.OpenKey(HIVES[hive], path) as k:
            cmd = str(pccare._value(k, "UninstallString") or pccare._value(k, "QuietUninstallString") or "")
    except OSError:
        return False
    if not cmd or re.match(r'(?i)\s*"?msiexec', cmd):
        return True
    exe = _command_exe(cmd)
    return not exe or Path(exe).exists()


def _top_of(location, needles):
    r"""C:\Program Files (x86)\Microsoft\Copilot\Application → ...\Microsoft\Copilot (the program's folder, not the company's)."""
    if not location:
        return None
    roots = {r for r, _k in all_roots()}
    cur = Path(location)
    while True:
        parent = cur.parent
        if parent == cur or str(parent).lower().rstrip("\\") in roots:
            break
        if _generic(cur.name) or any(strong(n, parent.name) for n in needles):
            cur = parent
            continue
        break
    return None if not cur.name or _generic(cur.name) or str(cur).lower().rstrip("\\") in roots else cur


def _exes(location, limit=80):
    names = []
    if location and Path(location).is_dir():
        base = len(Path(location).parts)
        for dirpath, dirs, files in os.walk(location):
            if len(Path(dirpath).parts) - base >= 3:
                dirs[:] = []
            names += [f.lower() for f in files if f.lower().endswith(".exe")]
            if len(names) >= limit:
                break
    return sorted(set(names))[:limit]


def _size(path, cap=40000):
    total, n = 0, 0
    p = Path(path)
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    for dirpath, _d, files in os.walk(path):
        for f in files:
            n += 1
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
            if n > cap:
                return total
    return total


def lnk_target(path):
    """Where a .lnk shortcut points (its LinkInfo local path), or ''. Read from the file itself, no COM."""
    try:
        data = Path(path).read_bytes()
        if data[:4] != b"\x4c\x00\x00\x00":
            return ""
        u32 = lambda at: int.from_bytes(data[at:at + 4], "little")
        flags, pos = u32(20), 76
        if flags & 0x01:
            pos += 2 + int.from_bytes(data[pos:pos + 2], "little")
        if not flags & 0x02:
            return ""
        start, header, li_flags = pos, u32(pos + 4), u32(pos + 8)
        if not li_flags & 0x01:
            return ""
        if header >= 0x24 and u32(pos + 28):
            at = start + u32(pos + 28)
            end = at
            while data[end:end + 2] != b"\x00\x00":
                end += 2
            return data[at:end].decode("utf-16-le", "replace")
        at = start + u32(pos + 16)
        return data[at:data.index(b"\x00", at)].decode("mbcs", "replace")
    except (OSError, ValueError, IndexError):
        return ""


# ---------- the profile: what a program looked like before it was removed ----------
def profile_for_program(p):
    """Taken BEFORE the uninstall: afterwards its install folder and exe names may be gone."""
    where = {"machine": ("HKLM", UNINSTALL_ROOTS[0][1]), "machine32": ("HKLM", UNINSTALL_ROOTS[1][1]), "user": ("HKCU", UNINSTALL_ROOTS[2][1])}
    kind, _sep, sub = str(p.get("id", "")).partition("\\")
    hive, root = where.get(kind, ("", ""))
    location = str(p.get("location") or "")
    if not location and p.get("icon") and Path(p["icon"]).suffix.lower() == ".exe":
        location = str(Path(p["icon"]).parent)
    roots = {r for r, _k in all_roots()}
    if location and str(Path(location)).lower().rstrip("\\") in roots:
        location = ""                                           # a program "installed" in Program Files itself: too wide
    name = clean_name(p.get("name", "")) or str(p.get("name", ""))
    needles = [name]
    top = _top_of(location, [name])
    if top is not None and not _protected_name(top.name) and _flat(top.name) != _flat(name) and len(_flat(top.name)) >= 3:
        needles.append(top.name)
    return {"label": p.get("name", ""), "needles": needles, "company": clean_company(p.get("publisher", "")),
            "location": str(Path(location)) if location else "", "top": str(top) if top is not None else "", "exes": _exes(location),
            "uninstall": [hive, root + "\\" + sub] if hive and sub else None, "family": "", "kind": "program"}


def profile_for_app(a):
    """A Windows (Store) app: its name, its package name without the maker's prefix, and its data folder."""
    package = str(a.get("package", ""))
    short = package.split(".", 1)[1] if "." in package else package
    needles = [n for n in (clean_name(a.get("name", "")), short) if len(_flat(n)) >= 3]
    return {"label": a.get("name", ""), "needles": list(dict.fromkeys(needles)), "company": "", "location": "", "top": "", "exes": [],
            "uninstall": None, "family": str(a.get("family", "")), "kind": "app"}


def profile_for_name(name):
    """Leftover hunt: only a name (the program is long gone)."""
    name = str(name).strip()
    return {"label": name, "needles": [name], "company": "", "location": "", "top": "", "exes": [], "uninstall": None, "family": "", "kind": "hunt"}


# ---------- the scan ----------
class Found:
    def __init__(self):
        self.registry, self.files, self._keys, self._paths = [], [], set(), set()
        self._use = {}

    def has_key(self, full):
        low = full.lower()
        return any(low == k or low.startswith(k + "\\") for k in self._keys)

    def has_path(self, path):
        low = str(path).lower().rstrip("\\")
        return any(low == k or low.startswith(k + "\\") for k in self._paths)

    def key(self, hive, path, how, mode):
        full = hive + "\\" + path
        if self.has_key(full) or refusal_key_shape(hive, path):
            return
        self._keys.add(full.lower())
        self.registry = [r for r in self.registry if not (r["hive"] + "\\" + r["path"]).lower().startswith(full.lower() + "\\")]
        values, more = [], 0
        try:
            with winreg.OpenKey(HIVES[hive], path) as k:
                nsub, nval, _t = winreg.QueryInfoKey(k)
                for i in range(min(nval, 6)):
                    name, data, _typ = winreg.EnumValue(k, i)
                    values.append([name or "(default)", _short(data)])
                more = max(0, nval - 6) + nsub
        except OSError:
            return
        use = _key_use(hive, path)
        self.registry.append({"kind": "key", "hive": hive, "path": path, "name": "", "data": "", "how": how, "mode": mode, "area": _area(path),
                              "inUse": use if not use or "still" in use else "%s still uses it" % use, "values": values, "more": more,
                              "size": _key_size(hive, path)})

    def value(self, hive, path, name, data, how, mode, ref="", ref_root=""):
        full = hive + "\\" + path
        if self.has_key(full) or any(r["kind"] == "value" and r["hive"] == hive and r["path"].lower() == path.lower() and r["name"] == name for r in self.registry):
            return
        use = ""
        if ref_root:
            if ref_root not in self._use:
                self._use[ref_root] = _ref_refusal(ref_root)
            use = self._use[ref_root]
        self.registry.append({"kind": "value", "hive": hive, "path": path, "name": name, "data": _short(data), "how": how, "mode": mode,
                              "area": _area(path), "inUse": use, "ref": ref, "refRoot": ref_root, "values": [], "more": 0,
                              "size": _data_size(name, data)})

    def path(self, p, how, mode, area=""):
        p = Path(p)
        if not p.exists() or self.has_path(p):
            return
        low = str(p).lower().rstrip("\\")
        self._paths.add(low)
        self.files = [f for f in self.files if not f["path"].lower().startswith(low + "\\")]
        self.files.append({"kind": "folder" if p.is_dir() else "file", "path": str(p), "size": _size(p), "how": how, "mode": mode,
                           "area": area, "inUse": path_refusal(p, deep=area == "windows")})


def _data_size(name, data):
    """Roughly what a value takes in the registry: its name and its data (text counts 2 bytes a letter)."""
    if isinstance(data, bytes):
        n = len(data)
    elif isinstance(data, list):
        n = sum(len(str(x)) + 1 for x in data) * 2
    elif isinstance(data, int):
        n = 4 if data < 2 ** 32 else 8
    else:
        n = (len(str(data)) + 1) * 2
    return n + len(name or "") * 2


def _key_size(hive, path, budget=None):
    """A key with everything inside it (stops counting after 5000 keys: enough to say KB or MB)."""
    budget = budget if budget is not None else [5000]
    total = len(path.rsplit("\\", 1)[-1]) * 2
    try:
        with winreg.OpenKey(HIVES[hive], path) as k:
            nsub, nval, _t = winreg.QueryInfoKey(k)
            for i in range(nval):
                try:
                    name, data, _typ = winreg.EnumValue(k, i)
                except OSError:
                    break
                total += _data_size(name, data)
            subs = []
            for i in range(nsub):
                try:
                    subs.append(winreg.EnumKey(k, i))
                except OSError:
                    break
    except OSError:
        return total
    for sub in subs:
        budget[0] -= 1
        if budget[0] <= 0:
            break
        total += _key_size(hive, path + "\\" + sub, budget)
    return total


def _short(data):
    if isinstance(data, bytes):
        return "(%d bytes)" % len(data)
    if isinstance(data, list):
        data = "; ".join(str(x) for x in data)
    data = str(data)
    return data if len(data) <= 160 else data[:157] + "…"


def _area(path):
    parts = [p.lower() for p in path.split("\\")]
    return "windows" if any(p in WINDOWS_AREA for p in parts[1:-1]) else ""


def _key_use(hive, path):
    parts = path.split("\\")
    if len(parts) >= 2 and "\\".join(parts[:-1]).lower() in [r.lower() for _h, r in UNINSTALL_ROOTS]:
        return "that program is still installed" if _uninstall_alive(hive, path) else ""
    return pccare.key_in_use(hive + "\\" + path)


def _subkeys(hive, path):
    try:
        with winreg.OpenKey(HIVES[hive], path) as k:
            out, i = [], 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                except OSError:
                    return out
                i += 1
    except OSError:
        return []


def _values(hive, path):
    try:
        with winreg.OpenKey(HIVES[hive], path) as k:
            out, i = [], 0
            while True:
                try:
                    out.append(winreg.EnumValue(k, i))
                except OSError:
                    return out
                i += 1
    except OSError:
        return []


def _dirs(root):
    try:
        return [e for e in os.scandir(root) if e.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def _entries(root):
    try:
        return list(os.scandir(root))
    except OSError:
        return []


def scan(profile, mode="moderate", progress=None, cancelled=None):
    """Profile → {"registry": [...], "files": [...]}. progress(percent, text) and cancelled() are optional."""
    mode = mode if mode in MODES else "moderate"
    tell = progress or (lambda pct, text: None)
    stop = cancelled or (lambda: False)
    needles = [n for n in profile["needles"] if len(_flat(n)) >= 3]
    company = profile.get("company") or ""
    hit = lambda name: any(loose(n, name) for n in needles)
    sure = lambda name: any(strong(n, name) for n in needles)
    f = Found()
    if not needles:
        return {"registry": [], "files": [], "mode": mode}
    tell(3, "Asking Windows what is still installed…")
    pccare.installed_index(fresh=True)                         # the program just removed must no longer count as "in use"

    # ----- safe: folders -----
    tell(12, "Program folders…")
    if profile.get("top"):
        f.path(profile["top"], "its install folder", "safe", "windows" if _first_protected(profile["top"]) else "")
    packages = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Packages").lower()
    if profile.get("family"):
        f.path(Path(packages) / profile["family"], "its app data", "safe")
    for root, kind in all_roots():
        if kind != "program":
            continue
        for e in _dirs(root):
            low = e.name.lower()
            if root == packages:
                if not low.startswith(pccare.PROTECTED_PREFIX) and not low.endswith("_cw5n1h2txyewy") and hit(e.name.split("_")[0].split(".", 1)[-1]):
                    f.path(e.path, "an app data folder named like it", "safe")
                continue
            if low in pccare.PROTECTED_DIRS or low.startswith(pccare.PROTECTED_PREFIX):
                continue
            if hit(e.name):
                f.path(e.path, "named like it", "safe")
            elif company and loose(company, e.name):
                inside = _dirs(e.path)
                mine = [c for c in inside if hit(c.name)]
                if mine and len(mine) == len(inside) and not _entries_files(e.path):
                    f.path(e.path, "its company's folder (only it inside)", "safe")
                else:
                    for c in mine:
                        f.path(c.path, "in its company's folder", "safe")
    if stop():
        return _result(f, mode)

    # ----- safe: registry keys -----
    tell(25, "Its registry keys…")
    for hive, base in (("HKCU", "Software"), ("HKLM", "Software"), ("HKLM", r"Software\WOW6432Node")):
        for sub in _subkeys(hive, base):
            low = sub.lower()
            if low in pccare.PROTECTED_KEYS or low in STRUCTURAL:
                continue
            if hit(sub):
                f.key(hive, base + "\\" + sub, "named like it", "safe")
            elif company and loose(company, sub):
                inside = _subkeys(hive, base + "\\" + sub)
                mine = [c for c in inside if hit(c)]
                if mine and len(mine) == len(inside):
                    f.key(hive, base + "\\" + sub, "its company's key (only it inside)", "safe")
                else:
                    for c in mine:
                        f.key(hive, base + "\\" + sub + "\\" + c, "in its company's key", "safe")
    own = profile.get("uninstall")
    for hive, root in UNINSTALL_ROOTS:
        for sub in _subkeys(hive, root):
            path = root + "\\" + sub
            mine = own and own[0] == hive and own[1].lower() == path.lower()
            if not mine:
                try:
                    with winreg.OpenKey(HIVES[hive], path) as k:
                        mine = sure(str(pccare._value(k, "DisplayName") or ""))
                except OSError:
                    continue
            if mine and not _uninstall_alive(hive, path):
                f.key(hive, path, "its entry in Windows' program list (the uninstaller is gone)", "safe")
    if mode == "safe" or stop():
        return _result(f, mode)

    # ----- moderate: shortcuts, temp, startup, App Paths, file types -----
    tell(38, "Shortcuts and temporary files…")
    for menu in start_menus():
        for e in _entries(menu):
            if e.name.lower() in START_KEEP:
                continue
            if _shortcut_or_dir(e) and hit(Path(e.name).stem):
                f.path(e.path, "a Start-menu entry", "moderate")
            elif e.is_dir():
                for c in _entries(e.path):
                    if _shortcut_or_dir(c) and hit(Path(c.name).stem):
                        f.path(c.path, "a Start-menu entry", "moderate")
    for desk in desktops():
        for e in _entries(desk):
            if e.is_file() and Path(e.name).suffix.lower() in (".lnk", ".url") and hit(Path(e.name).stem):
                f.path(e.path, "a desktop shortcut", "moderate")
    for e in _entries(temp_dir()):
        if hit(Path(e.name).stem if e.is_file() else e.name):
            f.path(e.path, "temporary files", "moderate")
    tell(48, "Startup entries, App Paths, file types…")
    location = (profile.get("location") or "").lower()
    anchor = profile.get("top") or profile.get("location") or ""          # the folder a pointing value is judged by
    exes = set(profile.get("exes") or [])
    for hive, path in RUN_KEYS:
        for name, data, _t in _values(hive, path):
            exe = _command_exe(data)
            if hit(name) or (location and exe.lower().startswith(location + "\\")):
                f.value(hive, path, name, data, "starts with Windows" if exe and Path(exe).exists() else "a startup entry whose program is gone", "moderate",
                        exe, anchor if location and exe.lower().startswith(location + "\\") else exe)
    run_names = {n.lower() for h, p in RUN_KEYS for n, _d, _t in _values(h, p)}
    for hive in ("HKCU", "HKLM"):
        for sub in ("Run", "Run32", "StartupFolder"):
            for name, data, _t in _values(hive, APPROVED + "\\" + sub):
                if hit(Path(name).stem) and name.lower() not in run_names and not _in_startup_folder(name):
                    f.value(hive, APPROVED + "\\" + sub, name, data, "an on/off switch for a startup entry that's gone", "moderate")
    for hive, root in (("HKCU", r"Software\Microsoft\Windows\CurrentVersion\App Paths"), ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
                       ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths")):
        for sub in _subkeys(hive, root):
            if sub.lower() in exes or hit(Path(sub).stem):
                target = _default(hive, root + "\\" + sub)
                if not target or not Path(target.strip('"')).exists() or (location and target.lower().strip('"').startswith(location + "\\")):
                    f.key(hive, root + "\\" + sub, "where Windows finds its program", "moderate")
    for hive in ("HKCU", "HKLM"):
        base = r"Software\Classes"
        for sub in _subkeys(hive, base):
            if sub[:1] in (".", "{", "*") or sub.lower() in STRUCTURAL:
                continue
            if hit(sub):
                exe = _command_exe(_default(hive, base + "\\" + sub + r"\shell\open\command"))
                if not exe or not Path(exe).exists() or (location and exe.lower().startswith(location + "\\")):
                    f.key(hive, base + "\\" + sub, "a file type or link it registered", "moderate")
        for exe in exes:
            if exe in {s.lower() for s in _subkeys(hive, base + r"\Applications")}:
                f.key(hive, base + r"\Applications" + "\\" + exe, "its entry in Open with", "moderate")
    if mode == "moderate" or stop():
        return _result(f, mode)

    # ----- advanced: the whole registry, and folders inside the Windows areas -----
    tell(55, "Advanced: going through the whole registry…")
    walks = [("HKCU", "Software", 55, 62), ("HKLM", "Software", 62, 90)]
    for hive, base, a, b in walks:
        tops = [s for s in _subkeys(hive, base) if not (hive == "HKLM" and s.lower() == "classes")]
        for i, top in enumerate(tops):
            if stop():
                return _result(f, mode)
            tell(a + (b - a) * i / max(1, len(tops)), "Advanced: %s\\%s\\%s…" % (hive, base, top))
            _walk(f, hive, base + "\\" + top, 2, sure, needles, location, anchor)
    tell(92, "Advanced: folders inside the Windows areas…")
    for root, kind in all_roots():
        if kind != "program" or root == packages or root.endswith("\\temp"):
            continue
        for e in _dirs(root):
            low = e.name.lower()
            if low in ("windowsapps", "packages", "temp", "windows defender") or low.endswith("_cw5n1h2txyewy"):
                continue
            area = "windows" if (low in pccare.PROTECTED_DIRS or low.startswith(pccare.PROTECTED_PREFIX)) else ""
            for c in _dirs(e.path):
                if sure(c.name) and not _generic(c.name):
                    f.path(c.path, "named like it, one folder deeper", "advanced", area)
    return _result(f, mode)


def _skipped(path):
    """Inside an area the scan never walks and remove() never touches (also its WOW6432Node twin)."""
    low = str(path).lower().replace("\\wow6432node", "")
    return any(low == s or low.startswith(s + "\\") for s in DEEP_SKIP)


def _in_uninstall(path):
    low = str(path).lower()
    return any(low.startswith(r.lower() + "\\") for _h, r in UNINSTALL_ROOTS)


def _walk(f, hive, path, depth, sure, needles, location, anchor, limit=12):
    if _skipped(path) or f.has_key(hive + "\\" + path):
        return
    leaf = path.rsplit("\\", 1)[-1]
    if depth >= 3 and sure(leaf) and not leaf.startswith("{"):
        f.key(hive, path, "named like it, deep in the registry", "advanced")
        return
    if not _in_uninstall(path):                                  # Uninstall entries are judged whole (safe mode), never by value
        for name, data, typ in _values(hive, path):
            if not name:
                continue
            # a value is only offered when it is ABOUT the program: the path is its name (Windows' compatibility and
            # name caches), or its name carries the program's name. A path inside someone else's record stays.
            ref, root = _dead_ref(name, location, anchor, sure)
            if not ref and any(loose(n, name) for n in needles) and typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ, winreg.REG_MULTI_SZ):
                ref, root = _dead_ref("\n".join(data) if isinstance(data, list) else str(data), location, anchor, sure)
            if ref:
                f.value(hive, path, name, data, "points into its folder" if location and ref.lower().startswith(location) else "points to a folder named like it",
                        "advanced", ref, root)
    if depth >= limit:
        return
    for sub in _subkeys(hive, path):
        _walk(f, hive, path + "\\" + sub, depth + 1, sure, needles, location, anchor, limit)


def _dead_ref(text, location, anchor, sure):
    """A path in a value that belongs to the program: inside its install folder, or a folder named like it that is
    gone or is itself a removable leftover. Returns (the path, the folder it is judged by)."""
    if ":\\" not in text:
        return "", ""
    for m in PATH_IN_TEXT.finditer(text):
        p = m.group(0).strip().rstrip(".,;")
        low = p.lower()
        if location and (low == location or low.startswith(location + "\\")):
            return p, anchor or location
        parts = Path(p).parts
        for i, part in enumerate(parts[1:], 1):
            if sure(Path(part).stem if i == len(parts) - 1 else part):
                root = str(Path(*parts[:i + 1]))
                if not Path(root).exists() or not path_refusal(root, deep=True):
                    return p, root
                break
    return "", ""


def _default(hive, path):
    try:
        with winreg.OpenKey(HIVES[hive], path) as k:
            return os.path.expandvars(str(winreg.QueryValueEx(k, "")[0] or ""))
    except OSError:
        return ""


def _entries_files(path):
    return [e for e in _entries(path) if e.is_file()]


def _shortcut_or_dir(e):
    return e.is_dir() or Path(e.name).suffix.lower() in (".lnk", ".url")


def _in_startup_folder(name):
    folders = [Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
               Path(os.environ.get("ProgramData", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"]
    return any((d / name).exists() for d in folders)


def _first_protected(path):
    target = str(Path(path)).lower()
    for r, kind in all_roots():
        if target.startswith(r + "\\"):
            first = target[len(r) + 1:].split("\\")[0]
            return first in pccare.PROTECTED_DIRS or first.startswith(pccare.PROTECTED_PREFIX)
    return False


def _result(f, mode):
    reg = sorted(f.registry, key=lambda r: (r["hive"], r["path"].lower(), r["name"].lower()))
    files = sorted(f.files, key=lambda x: x["path"].lower())
    return {"registry": reg, "files": files, "mode": mode}


# ---------- the rails ----------
def refusal_key_shape(hive, path):
    """Why a key (by its place alone) may never be deleted, or ''."""
    if hive not in HIVES:
        return "not a registry place Toolbelt cleans"
    parts = [p for p in str(path).split("\\") if p]
    if len(parts) < 2 or parts[0].lower() != "software":
        return "outside Software"
    if _skipped("\\".join(parts)):
        return "part of Windows' own bookkeeping"
    leaf = parts[-1].lower()
    if leaf in pccare.PROTECTED_KEYS or leaf in STRUCTURAL:
        return "a key Windows or your drivers need"
    if len(parts) == 2 and leaf.startswith(pccare.PROTECTED_PREFIX):
        return "a key Windows needs"
    return ""


def path_refusal(p, deep=False):
    """Why this file or folder may not be deleted, or ''. Only inside the program, Start-menu, desktop and temp folders,
    never one of them itself, never Windows' own; deep (Advanced, 'Windows area') allows a named folder inside them."""
    p = Path(p)
    if not p.exists():
        return "already gone"
    target = str(p).lower().rstrip("\\")
    roots = all_roots()
    if target in [r for r, _k in roots]:
        return "that is a main folder of Windows itself"
    match = next(((r, k) for r, k in roots if target.startswith(r + "\\")), None)
    if not match:
        return "outside the program folders"
    root, kind = match
    rel = target[len(root) + 1:].split("\\")
    first, leaf = rel[0], rel[-1]
    if kind == "start" and first in START_KEEP:
        return "a Start-menu folder Windows needs"
    if p.is_file():
        if kind in ("start", "desktop") and p.suffix.lower() not in (".lnk", ".url"):
            return "only shortcuts are removed there"
        if kind == "program" and len(rel) < 2:
            return "a loose file in a main folder"
    protected_first = first in pccare.PROTECTED_DIRS or first.startswith(pccare.PROTECTED_PREFIX) or first.endswith("_cw5n1h2txyewy")
    if kind == "program" and protected_first:
        if not deep or len(rel) < 2 or leaf in pccare.PROTECTED_DIRS or leaf.startswith(pccare.PROTECTED_PREFIX) or _generic(leaf):
            return "a folder Windows, a driver or Toolbelt needs"
    elif kind == "program" and p.is_dir() and leaf in pccare.PROTECTED_DIRS:
        return "a folder Windows, a driver or Toolbelt needs"
    if p.is_file() and p.suffix.lower() == ".lnk":
        aim = lnk_target(p)                                     # a shortcut to a program that is still there stays
        if aim and Path(aim).exists() and path_refusal(Path(aim).parent, deep=True):
            return "its program is still there"
    still = pccare.in_use(p.parent / p.stem if p.is_file() else p)
    return ("%s still uses it" % still) if still else ""


def _ref_refusal(ref_root):
    """A value pointing at a path: fine when the path is gone or is itself a removable leftover."""
    target = Path(ref_root)
    if not target.exists():
        return ""
    if target.is_file():
        target = target.parent
    why = path_refusal(target, deep=True)
    return ("its program is still there (%s)" % why) if why else ""


def refusal(item):
    """The last check before anything is deleted (also run by the elevated helper)."""
    kind = item.get("kind")
    if kind in ("key", "value"):
        hive, path = item.get("hive", ""), item.get("path", "")
        if kind == "key":
            why = refusal_key_shape(hive, path)
            if why:
                return why
            try:
                winreg.OpenKey(HIVES[hive], path).Close()
            except OSError:
                return "already gone"
            still = _key_use(hive, path)
            if still:
                return still if "still" in still else "%s still uses it" % still
            names = [n for n, _d in pccare.installed_index()]
            for sub in _subkeys(hive, path)[:200]:              # a company key holding an installed product's key (Riot Games\Riot Client)
                if sub.lower() in STRUCTURAL or sub.startswith("{"):
                    continue
                inner = next((n for n in names if strong(n, sub)), "")
                if inner:
                    return "%s still uses a key inside it" % inner
            return ""
        parts = [p for p in str(path).split("\\") if p]
        if hive not in HIVES or len(parts) < 2 or parts[0].lower() != "software":
            return "outside Software"
        low = "\\".join(parts).lower()
        if _skipped(low):
            return "part of Windows' own bookkeeping"
        if _in_uninstall(low):
            return "part of a program's entry in Windows' list"
        name = item.get("name", "")
        if not name:
            return "a key's main value is left alone"
        if not any(n == name for n, _d, _t in _values(hive, path)):
            return "already gone"
        if item.get("refRoot"):
            return _ref_refusal(item["refRoot"])
        if not low.startswith(APPROVED.lower() + "\\"):
            return "Toolbelt only removes values that point to the program"
        return ""
    if kind in ("folder", "file"):
        return path_refusal(item.get("path", ""), deep=item.get("area") == "windows")
    return "unknown kind of item"


# ---------- deleting: .reg backup first, files to the Recycle Bin ----------
class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR)]


def recycle(path):
    """Sends a file or folder to the Recycle Bin, without questions or windows. Returns Windows' code (0 = done)."""
    op = _SHFILEOPSTRUCTW(None, 3, str(path) + "\0", None, 0x0004 | 0x0010 | 0x0040 | 0x0400, False, None, None)
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))


def _reg_text(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _reg_line(name, data, typ):
    head = '"%s"=' % _reg_text(name) if name else "@="
    if typ == winreg.REG_SZ:
        return head + '"%s"' % _reg_text(str(data))
    if typ == winreg.REG_DWORD:
        return head + "dword:%08x" % (int(data) & 0xFFFFFFFF)
    if typ == winreg.REG_EXPAND_SZ:
        raw = (str(data) + "\0").encode("utf-16-le")
        return head + "hex(2):" + ",".join("%02x" % b for b in raw)
    if typ == winreg.REG_MULTI_SZ:
        raw = ("\0".join(data or []) + "\0\0").encode("utf-16-le")
        return head + "hex(7):" + ",".join("%02x" % b for b in raw)
    if typ == winreg.REG_QWORD:
        return head + "hex(b):" + ",".join("%02x" % b for b in int(data).to_bytes(8, "little"))
    raw = data if isinstance(data, bytes) else b""
    return head + ("hex:" if typ == winreg.REG_BINARY else "hex(%x):" % typ) + ",".join("%02x" % b for b in raw)


def _full_hive(hive):
    return {"HKCU": "HKEY_CURRENT_USER", "HKLM": "HKEY_LOCAL_MACHINE"}[hive]


def backup_key(hive, path, file):
    done = subprocess.run(["reg", "export", hive + "\\" + path, str(file), "/y"], capture_output=True, creationflags=NO_WINDOW, timeout=60)
    if done.returncode != 0:
        raise OSError("couldn't back it up first, so it was left alone")


def backup_value(hive, path, name, file):
    with winreg.OpenKey(HIVES[hive], path) as k:
        data, typ = winreg.QueryValueEx(k, name)
    text = "Windows Registry Editor Version 5.00\r\n\r\n[%s\\%s]\r\n%s\r\n" % (_full_hive(hive), path, _reg_line(name, data, typ))
    Path(file).write_text(text, encoding="utf-16")


def _delete_key(hive, path):
    with winreg.OpenKey(HIVES[hive], path, 0, winreg.KEY_ALL_ACCESS) as k:
        while True:
            try:
                sub = winreg.EnumKey(k, 0)
            except OSError:
                break
            _delete_key(hive, path + "\\" + sub)
    winreg.DeleteKey(HIVES[hive], path)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def remove(items, backup_dir=None, to_bin=True):
    """Deletes the items (dicts from a scan, each with an "id"). Returns done ids, failed [id, why] and the ids that need admin.
    to_bin=False deletes files for good (the tests use it, so his Recycle Bin doesn't fill with test folders)."""
    import shutil
    backup_dir = Path(backup_dir or DATA / "backups" / time.strftime("%Y-%m-%d %H%M%S"))
    done, failed, need_admin, n = [], [], [], 0
    for item in items:
        why = refusal(item)
        if why == "already gone":
            done.append(item["id"])
            continue
        if why:
            failed.append([item["id"], why])
            continue
        try:
            if item["kind"] in ("key", "value"):
                backup_dir.mkdir(parents=True, exist_ok=True)
                n += 1
                file = next(backup_dir / ("%03d.reg" % i) for i in range(1, 100000) if not (backup_dir / ("%03d.reg" % i)).exists())
                if item["kind"] == "key":
                    backup_key(item["hive"], item["path"], file)
                    _delete_key(item["hive"], item["path"])
                else:
                    backup_value(item["hive"], item["path"], item["name"], file)
                    with winreg.OpenKey(HIVES[item["hive"]], item["path"], 0, winreg.KEY_SET_VALUE) as k:
                        winreg.DeleteValue(k, item["name"])
            elif not to_bin:
                (shutil.rmtree if Path(item["path"]).is_dir() else os.remove)(item["path"])
            else:
                code = recycle(item["path"])
                if code or Path(item["path"]).exists():
                    raise PermissionError(5, "Windows said no (code %s)" % code) if _needs_admin(item["path"]) else OSError("a program has a file in it open (code %s)" % code)
            done.append(item["id"])
        except PermissionError:
            need_admin.append(item["id"])
        except OSError as error:
            if getattr(error, "winerror", 0) == 5 or getattr(error, "errno", 0) == 13:
                need_admin.append(item["id"])
            else:
                failed.append([item["id"], str(error)[:120]])
    if need_admin and is_admin():                              # already admin: then it's really refused
        failed += [[i, "Windows refused, even as admin"] for i in need_admin]
        need_admin = []
    return {"done": done, "failed": failed, "needAdmin": need_admin, "backup": str(backup_dir) if n else ""}


def _needs_admin(path):
    low = str(path).lower()
    machine = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData", "PUBLIC")]
    return any(m and low.startswith(m.lower() + "\\") for m in machine) and not is_admin()


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def shell_run(file, params, admin=True, show=0):
    """Starts a program (as admin: Windows asks) and gives back its process handle, or raises OSError (1223 = he said no)."""
    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x100                                   # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.lpVerb = "runas" if admin else "open"
    info.lpFile, info.lpParameters, info.nShow = str(file), params, show
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        raise ctypes.WinError()
    return info.hProcess


class Handle:
    """A started process, by its Windows handle (for programs started through ShellExecuteEx)."""
    def __init__(self, handle):
        self.handle = handle

    def poll(self):
        if ctypes.windll.kernel32.WaitForSingleObject(self.handle, 0) == 0x102:
            return None
        code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code))
        return code.value

    def wait(self, timeout=None):
        ctypes.windll.kernel32.WaitForSingleObject(self.handle, 0xFFFFFFFF if timeout is None else int(timeout * 1000))
        return self.poll()


def remove_as_admin(items, backup_dir=None, timeout=600):
    """The same remove(), in this file started elevated: one UAC question. The elevated side checks every item again."""
    work = DATA / "admin"
    work.mkdir(parents=True, exist_ok=True)
    stamp = "%d" % (time.time() * 1000)
    inp, out = work / ("remove %s.json" % stamp), work / ("result %s.json" % stamp)
    inp.write_text(json.dumps({"items": items, "backup": str(backup_dir or "")}), encoding="utf-8")
    try:
        handle = Handle(shell_run(sys.executable, subprocess.list2cmdline([str(Path(__file__).resolve()), "--remove", str(inp), str(out)])))
    except OSError as error:
        inp.unlink(missing_ok=True)
        if getattr(error, "winerror", 0) == 1223:
            return {"done": [], "failed": [], "needAdmin": [i["id"] for i in items], "backup": "", "message": "The admin question was cancelled."}
        raise
    handle.wait(timeout)
    inp.unlink(missing_ok=True)
    if not out.exists():
        return {"done": [], "failed": [[i["id"], "the admin helper gave no answer"] for i in items], "needAdmin": [], "backup": ""}
    result = json.loads(out.read_text(encoding="utf-8"))
    out.unlink(missing_ok=True)
    return result


# ---------- the program's own uninstaller ----------
def uninstall_command(program):
    cmd = os.path.expandvars(str(program.get("uninstall") or program.get("quiet") or "")).strip()
    if re.match(r'(?i)^"?msiexec', cmd):
        cmd = re.sub(r"(?i)/I\s*(\{)", r"/X\1", cmd)              # "modify / repair / remove" → straight to remove, like Revo
    return cmd


def launch_uninstaller(program):
    """Starts its uninstaller and returns something with poll() (to see when its window closes)."""
    cmd = uninstall_command(program)
    if not cmd:
        raise OSError("That program has no uninstaller.")
    try:
        return subprocess.Popen(cmd)                            # Windows splits the command line itself (also unquoted paths)
    except OSError as error:
        if getattr(error, "winerror", 0) == 740:                # it insists on admin: start it the way Explorer would
            exe = _command_exe(cmd)
            params = cmd.strip()[len(exe) + (2 if cmd.strip().startswith('"') else 0):].strip()
            return Handle(shell_run(exe, params, admin=True, show=1))
        if isinstance(error, FileNotFoundError):
            return subprocess.Popen(cmd, shell=True)
        raise


# ---------- the flow, for the page ----------
class Session:
    """One uninstall (or hunt) at a time: the steps, the scan, the found items (only these can be deleted)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        self.label, self.kind, self.profile, self.steps = "", "", None, []
        self.phase, self.error, self.proc, self.listed_fn, self.listed = "idle", "", None, None, None
        self.scan_state = {"progress": 0, "message": "", "mode": ""}
        self.items, self.found, self._cancel, self._checked = {}, None, False, 0.0
        self.removed, self.backups, self._pending = set(), [], None

    def _step(self, key, state, note=""):
        for s in self.steps:
            if s["key"] == key:
                s["state"], s["note"] = state, note or s["note"]

    def begin(self, label, profile, restore_fn, remove_fn, listed_fn=None, kind="program"):
        """restore_fn() → {ok, message} or None to skip; remove_fn() → a process (poll()) or (ok, message)."""
        with self._lock:
            if self.phase in ("working", "scanning"):
                return {"ok": False, "message": "Another uninstall is still busy."}
            self.reset()
            self.label, self.kind, self.profile, self.listed_fn = label, kind, profile, listed_fn
            self.steps = ([{"key": "rp", "text": "Creating a System Restore Point", "state": "todo", "note": ""}] if restore_fn else []) + \
                [{"key": "run", "text": "Starting the program's own uninstaller" if kind == "program" else "Removing the app from Windows", "state": "todo", "note": ""},
                 {"key": "scan", "text": "After the uninstaller has finished, pick a scan mode and press Scan to look for leftovers",
                  "state": "todo", "note": ""}]
            self.phase = "working"
        threading.Thread(target=self._work, args=(restore_fn, remove_fn), daemon=True).start()
        return {"ok": True}

    def _work(self, restore_fn, remove_fn):
        if restore_fn:
            self._step("rp", "busy")
            try:
                res = restore_fn() or {}
            except Exception as error:
                res = {"ok": False, "message": str(error)}
            if not res.get("ok"):
                self._step("rp", "failed", res.get("message", ""))
                self.phase, self._pending = "rp-failed", remove_fn
                return
            self._step("rp", "done", res.get("message", ""))
        self._run(remove_fn)

    def go_on_without_rp(self):
        if self.phase != "rp-failed":
            return {"ok": False, "message": "Nothing is waiting."}
        self.phase = "working"
        self._step("rp", "skipped", "Went on without a restore point.")
        threading.Thread(target=self._run, args=(self._pending,), daemon=True).start()
        return {"ok": True}

    def _run(self, remove_fn):
        self._step("run", "busy")
        try:
            got = remove_fn()
        except Exception as error:
            self._step("run", "failed", str(error)[:200])
            self.phase = "uninstalled"
            return
        if isinstance(got, tuple):
            ok, message = got
            self._step("run", "done" if ok else "failed", message)
            self.phase = "uninstalled"
            return
        self.proc = got
        self._step("run", "busy", "Its window may be behind Toolbelt. Follow its steps.")
        while self.proc.poll() is None:
            time.sleep(0.4)
        self._step("run", "done", "The uninstaller closed. If it's still working in another window, wait for it, then press Scan.")
        self.phase = "uninstalled"

    def _listed(self):
        if self.listed_fn and self.phase in ("uninstalled", "scanned") and time.time() - self._checked > 2:
            self._checked = time.time()
            try:
                self.listed = bool(self.listed_fn())
            except Exception:
                self.listed = None
        return self.listed

    def hunt(self, name, mode):
        name = str(name).strip()
        if len(_flat(name)) < 3:
            return {"ok": False, "message": "Type at least 3 letters of the name."}
        if _protected_name(name):
            return {"ok": False, "message": "That's a part of Windows or a driver: Toolbelt doesn't hunt for it."}
        with self._lock:
            if self.phase in ("working", "scanning"):
                return {"ok": False, "message": "Another uninstall is still busy."}
            self.reset()
            self.label, self.kind, self.profile = name, "hunt", profile_for_name(name)
        return self.scan(mode)

    def scan(self, mode):
        if not self.profile or self.phase in ("working", "scanning"):
            return {"ok": False, "message": "Nothing to scan for yet."}
        self.phase, self._cancel = "scanning", False
        self.scan_state = {"progress": 0, "message": "Starting…", "mode": mode}
        self._step("scan", "busy")

        def tell(pct, text):
            self.scan_state.update(progress=round(pct), message=text)

        def work():
            try:
                found = scan(self.profile, mode, tell, lambda: self._cancel)
            except Exception as error:
                self.phase, self.error = "uninstalled" if self.kind != "hunt" else "idle", "The scan failed: %s" % error
                self._step("scan", "failed", str(error)[:200])
                return
            items = {}
            for i, it in enumerate(found["registry"]):
                it["id"] = "r%d" % i
                items[it["id"]] = it
            for i, it in enumerate(found["files"]):
                it["id"] = "f%d" % i
                items[it["id"]] = it
            self.items, self.found = items, found
            self._step("scan", "done", "%d registry items, %d files and folders" % (len(found["registry"]), len(found["files"])))
            self.phase = "scanned" if not self._cancel else ("uninstalled" if self.kind != "hunt" else "idle")

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def cancel_scan(self):
        self._cancel = True
        return {"ok": True}

    def status(self):
        return {"phase": self.phase, "label": self.label, "kind": self.kind, "steps": [dict(s) for s in self.steps], "error": self.error,
                "running": bool(self.proc and self.proc.poll() is None), "listed": self._listed(), "scan": dict(self.scan_state)}

    def result(self):
        if not self.found:
            return {"ok": False, "message": "No scan yet."}
        strip = lambda it: {k: v for k, v in it.items() if k != "refRoot"}
        return {"ok": True, "label": self.label, "mode": self.found["mode"], "removed": sorted(self.removed),
                "registry": [strip(it) for it in self.found["registry"]], "files": [strip(it) for it in self.found["files"]]}

    def delete(self, ids, admin=False):
        picked = [self.items[i] for i in ids if i in self.items and i not in self.removed]
        if not picked:
            return {"ok": False, "message": "Tick something first."}
        stamp = time.strftime("%Y-%m-%d %H%M%S") + " " + re.sub(r'[\\/:*?"<>|]+', "_", self.label)[:40]
        backup = DATA / "backups" / stamp
        res = remove_as_admin(picked, backup) if admin else remove(picked, backup)
        self.removed.update(res.get("done", []))
        res["freed"] = sum(int(self.items[i].get("size") or 0) for i in res.get("done", []) if i in self.items)
        if res.get("backup"):
            self.backups.append(res["backup"])
        parts = ["%d removed" % len(res.get("done", []))]
        if res.get("needAdmin"):
            parts.append("%d need admin" % len(res["needAdmin"]))
        if res.get("failed"):
            parts.append("%d refused" % len(res["failed"]))
        res["ok"] = not res.get("failed") and not res.get("needAdmin")
        res["message"] = res.get("message") or ", ".join(parts) + (". Registry backup kept; files are in the Recycle Bin." if res.get("done") else ".")
        return res


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--remove":
    # the elevated helper: read the list, check and remove, write the answer
    job = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    answer = remove(job.get("items", []), job.get("backup") or None)
    Path(sys.argv[3]).write_text(json.dumps(answer), encoding="utf-8")
