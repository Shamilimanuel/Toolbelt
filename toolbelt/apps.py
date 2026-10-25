"""Home: his own apps (found from their status files) and any Windows app he adds.

His projects live next to Toolbelt in Visual Studio Code (and in Visual Studio Code\\Widgets). Each keeps a status.md /
TASK.md / TASKS.md / STATUS.md: its progress line ("**Progress: 94%**") and the first open item under "## Next up" are
read straight from it, so Home is always as fresh as the notes. How each app starts (and where its settings are) comes
from launch.json (see LAUNCH below); he can change any of it on the page (it's saved
in %LOCALAPPDATA%\\Toolbelt\\apps.json, never in a project folder).
"""
import json
import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path

from settings import DATA

ROOT = Path(__file__).resolve().parents[2]                # ...\Visual Studio Code
STORE = DATA / "apps.json"
STATUS_NAMES = ("status.md", "STATUS.md", "TASK.md", "TASKS.md")
NO_WINDOW = 0x08000000
DETACHED = 0x00000008
# How each project starts and where its settings are. Kept in %LOCALAPPDATA%\Toolbelt\launch.json (25 Oct: moved out of
# the code so the public copy carries no personal project list), keyed by the folder relative to ROOT, e.g.
#   "Widgets\Snipper": {"name": "Snipper", "what": "screenshots", "open": {"py": "...pythonw.exe", "args": ["main.py"]},
#                        "hint": "...", "settings": {"file": "%APPDATA%\Snipper\settings.json"}, "settings_hint": "..."}
# Open kinds: file / exe / py (+ args, local_py) / ps1 / startmenu / url. "status" points at a status file deeper inside,
# "icon_file" at a picture, "self": true marks Toolbelt itself. Projects not listed still show up from their status file.
LAUNCH_FILE = DATA / "launch.json"


def _load_launch():
    table = {"Toolbelt": {"name": "Toolbelt", "what": "this app", "self": True}}
    try:
        table.update(json.loads(LAUNCH_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return table


LAUNCH = _load_launch()
START_MENUS = [Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
               Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"]


# ---------- reading a status file ----------

def clean_md(text):
    """Markdown bits removed: **bold**, `code`, [links](...), a trailing "← recommended"."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    text = re.split(r"\s+←", text)[0]
    return " ".join(text.split()).strip(" :")


def parse_status(text):
    """(title, progress or None, first open 'Next up' item or '')."""
    title = ""
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)       # code blocks can hold "# comments"
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        title = re.split(r"\s+[—–-]\s+", m.group(1).strip())[0].strip()
    pm = re.search(r"\*\*Progress:\s*(\d{1,3})%", text)
    progress = int(pm.group(1)) if pm else None
    nxt = ""
    section = re.search(r"^##\s+Next up\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    for block in ([section.group(1)] if section else []) + [text]:
        items = open_items(block)
        if items:
            marked = [i for i in items if re.search(r"←\s*(next|now|recommended)", i, re.I)]
            nxt = clean_md((marked or items)[0])
            break
    if len(nxt) > 140:
        nxt = nxt[:137].rsplit(" ", 1)[0] + "…"
    return title, progress, nxt


def open_items(block):
    """The open "- [ ]" items of a block, each with its indented continuation lines joined on."""
    items, current = [], None
    for line in block.splitlines():
        m = re.match(r"^\s*- \[ \]\s+(.+)$", line)
        if m:
            current = [m.group(1)]
            items.append(current)
        elif current is not None and line.startswith("  ") and not re.match(r"^\s*- \[", line):
            current.append(line.strip())
        else:
            current = None
    return [" ".join(i) for i in items]


def find_projects(root=None):
    """Every project folder with a status file, in Visual Studio Code and Visual Studio Code\\Widgets."""
    root = Path(root or ROOT)
    found = []
    for parent in (root, root / "Widgets"):
        if not parent.is_dir():
            continue
        for folder in sorted(parent.iterdir(), key=lambda p: p.name.lower()):
            if not folder.is_dir() or folder.name.startswith((".", "_")) or folder.name == "Widgets":
                continue
            rel = str(folder.relative_to(root))
            nested = LAUNCH.get(rel, {}).get("status")
            status = folder / nested if nested and (folder / nested).is_file() else next((folder / n for n in STATUS_NAMES if (folder / n).is_file()), None)
            if status is None and rel not in LAUNCH:
                continue
            title, progress, nxt = ("", None, "")
            if status is not None:
                try:
                    title, progress, nxt = parse_status(status.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
            info = LAUNCH.get(rel, {})
            found.append({"id": rel, "name": info.get("name") or title or folder.name, "folder": str(folder),
                          "status": str(status.relative_to(folder)) if status else "", "progress": progress, "next": nxt,
                          "what": info.get("what", ""), "open": info.get("open"), "settings": info.get("settings"), "note": info.get("note", ""),
                          "hint": info.get("hint", ""), "settings_hint": info.get("settings_hint", ""), "self": bool(info.get("self")),
                          "icon_file": str(folder / info["icon_file"]) if info.get("icon_file") else ""})
    return found


# ---------- his own choices (apps.json) ----------

def load():
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("added", [])
    data.setdefault("overrides", {})
    data.setdefault("hidden", [])
    return data


def save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STORE)


def projects():
    data = load()
    out = []
    for p in find_projects():
        o = data["overrides"].get(p["id"], {})
        p.update({k: v for k, v in o.items() if k in ("open", "settings") and v})
        p["hidden"] = p["id"] in data["hidden"]
        out.append(p)
    return out


# ---------- starting things ----------

def run(action, cwd=None):
    """Runs one launch action. action is a dict: {"py": venv, "args": [...]} (a Python app with its own venv),
    {"exe": path, "args": [...]}, {"ps1": path} (a PowerShell script, hidden), {"url": "https://..."},
    {"file": path} (opened like a double-click), or {"folder": path}."""
    if not isinstance(action, dict):
        return {"ok": False, "message": "Toolbelt doesn't know how to open this one yet."}
    expand = lambda s: os.path.expandvars(str(s))
    cwd = cwd and str(cwd)
    try:
        if "startmenu" in action:
            link = next((a["path"] for a in start_menu() if a["name"].lower() == str(action["startmenu"]).lower()), None)
            if not link:
                return {"ok": False, "message": "There's no \"%s\" in your Start menu." % action["startmenu"]}
            os.startfile(link)
        elif "py" in action:
            exe = Path(expand(action["py"]))
            if action.get("local_py") and cwd:
                exe = Path(cwd) / exe
            if not exe.is_file():
                return {"ok": False, "message": "Its Python folder isn't there: " + str(exe.parent.parent)}
            subprocess.Popen([str(exe)] + [expand(a) for a in action.get("args", [])], cwd=cwd, creationflags=DETACHED | NO_WINDOW)
        elif "exe" in action:
            exe = expand(action["exe"])
            if not Path(exe).is_file() and not shutil.which(exe):
                return {"ok": False, "message": "That program isn't there: " + exe}
            subprocess.Popen([exe] + [expand(a) for a in action.get("args", [])], cwd=cwd, creationflags=DETACHED)
        elif "ps1" in action:
            script = Path(cwd or ".") / expand(action["ps1"])
            if not script.is_file():
                return {"ok": False, "message": "Its start script isn't there: " + str(script)}
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script)],
                             cwd=cwd, creationflags=DETACHED | NO_WINDOW)
        elif "url" in action:
            url = str(action["url"])
            if not url.startswith(("https://", "http://")):
                return {"ok": False, "message": "Only web links can be opened as a website."}
            webbrowser.open(url)
        elif "file" in action or "folder" in action:
            target = Path(expand(action.get("file") or action.get("folder")))
            if not cwd or target.is_absolute():
                pass
            else:
                target = Path(cwd) / target
            if not target.exists():
                return {"ok": False, "message": "That isn't there any more: " + str(target)}
            os.startfile(str(target))
        else:
            return {"ok": False, "message": "Toolbelt doesn't know how to open this one yet."}
    except OSError as error:
        return {"ok": False, "message": "Windows couldn't start it: %s" % error}
    return {"ok": True, "message": ""}


def vscode():
    """Code.exe (no console window), or the code command, or None."""
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
              Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft VS Code" / "Code.exe"):
        if p.is_file():
            return str(p)
    return shutil.which("code")


def open_in_vscode(folder):
    code = vscode()
    if not code:
        return {"ok": False, "message": "VS Code wasn't found."}
    subprocess.Popen([code, str(folder)], creationflags=DETACHED | (NO_WINDOW if code.lower().endswith(".cmd") else 0))
    return {"ok": True, "message": "Opening in VS Code"}


# ---------- other Windows apps ----------

def start_menu():
    """Every app shortcut in the Start menu (his and all users'), without uninstallers, help files and duplicates."""
    seen, apps = set(), []
    skip = re.compile(r"\b(uninstall|uninst|help|readme|manual|documentation|release notes|license|website|support)\b", re.I)
    for base in START_MENUS:
        if not base.is_dir():
            continue
        for link in base.rglob("*.lnk"):
            name = link.stem
            if skip.search(name) or name.lower() in seen:
                continue
            seen.add(name.lower())
            group = link.parent.name if link.parent != base else ""
            apps.append({"name": name, "path": str(link), "group": "" if group in ("Programs",) else group})
    return sorted(apps, key=lambda a: a["name"].lower())


def add(kind, target, name="", group=""):
    """Adds a Windows app (a Start-menu shortcut, an .exe or a website) to Home."""
    target = str(target).strip()
    if kind == "url":
        if not re.match(r"^https?://[^\s]+\.[^\s]+", target):
            return {"ok": False, "message": "A website starts with https:// (for example https://hoyolab.com)."}
        name = name or re.sub(r"^https?://(www\.)?", "", target).split("/")[0]
    elif kind in ("lnk", "exe"):
        if not Path(target).is_file():
            return {"ok": False, "message": "That file isn't there."}
        name = name or Path(target).stem
    else:
        return {"ok": False, "message": "Unknown kind of app."}
    data = load()
    if any(a["target"].lower() == target.lower() for a in data["added"]):
        return {"ok": True, "message": name + " is already on Home."}
    data["added"].append({"id": "a%d" % (max([int(a["id"][1:]) for a in data["added"]] or [0]) + 1), "kind": kind, "target": target,
                          "name": str(name)[:60], "group": str(group)[:30]})
    save(data)
    return {"ok": True, "message": "Added " + name}


def remove(app_id):
    data = load()
    before = len(data["added"])
    data["added"] = [a for a in data["added"] if a["id"] != app_id]
    save(data)
    return {"ok": len(data["added"]) < before, "message": "Removed from Home (the app itself is untouched)."}


def open_added(app):
    if app["kind"] == "url":
        return run({"url": app["target"]})
    return run({"file": app["target"]})
