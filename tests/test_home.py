"""Tests for step 4, Home: reading status files, finding his projects, launch actions, adding / removing apps,
and (on his PC) that every project's launch target really exists. Nothing is started: run() is only tried on
harmless targets in a temporary folder."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import apps

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- reading notes ----------
NOTES = """# Snipper — status and checklist

```
# run it
pythonw main.py
```

<!-- progress:start -->
**Progress: 87%** `███` 7 of 8 done
<!-- progress:end -->

## Next up
- [x] something done
- [ ] **Polish the tray menu** (the [icons](x.png) are blurry)
- [ ] **Try it for real** and report what feels wrong ← recommended
  and tell me about the shortcut too
- [ ] later thing

## Done
- [ ] an open item outside Next up
"""
title, progress, nxt = apps.parse_status(NOTES)
expect("title from the first real heading, not a code-block comment", title == "Snipper")
expect("progress read from the progress line", progress == 87)
expect("the item marked ← recommended wins", nxt == "Try it for real and report what feels wrong")
expect("markdown is cleaned", apps.clean_md("**Bold** `code` [link](u) ← next") == "Bold code link")
t2, p2, n2 = apps.parse_status("# Courier\n\nNo checklist.\n")
expect("no progress line and no items are fine", p2 is None and n2 == "")
t3, p3, n3 = apps.parse_status("# X\n## Next up\n- [ ] first open\n  continues here\n- [ ] second\n")
expect("without a marker the first open item is used, continuation joined", n3 == "first open continues here")
long = apps.parse_status("# X\n## Next up\n- [ ] " + "word " * 60 + "\n")[2]
expect("long items are trimmed with …", len(long) <= 140 and long.endswith("…"))

# ---------- finding projects in a pretend Visual Studio Code folder ----------
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "Widgets" / "Snipper").mkdir(parents=True)
    (root / "Widgets" / "Snipper" / "status.md").write_text(NOTES, encoding="utf-8")
    (root / "Housecall").mkdir()
    (root / "Housecall" / "TASK.md").write_text("# Housecall\n**Progress: 93%**\n## Next up\n- [ ] Real test\n", encoding="utf-8")
    (root / "Leeromgeving" / "Leeromgeving").mkdir(parents=True)
    (root / "Leeromgeving" / "Leeromgeving" / "TASK.md").write_text("# Leeromgeving\n**Progress: 63%**\n", encoding="utf-8")
    (root / "random-folder").mkdir()
    (root / "_ideas").mkdir()
    (root / "_ideas" / "status.md").write_text("# hidden\n", encoding="utf-8")
    apps.LAUNCH = {"Widgets\\Snipper": {"name": "Snipper"}, "Leeromgeving": {"status": "Leeromgeving\\TASK.md"}}   # the test's own launch table (his is in AppData)
    found = {p["id"]: p for p in apps.find_projects(root)}
    expect("projects with a status file are found, in Widgets too", "Housecall" in found and "Widgets\\Snipper" in found)
    expect("folders without notes and _folders are skipped", "random-folder" not in found and "_ideas" not in found)
    expect("a status file one folder deeper (Leeromgeving) is found", found.get("Leeromgeving", {}).get("progress") == 63)
    expect("names come from the launch table", found["Widgets\\Snipper"]["name"] == "Snipper")

    # ---------- launch actions, tried on harmless things ----------
    expect("an unknown action is explained", not apps.run(None)["ok"] and not apps.run({"weird": 1})["ok"])
    expect("a missing program is explained", "isn't there" in apps.run({"exe": str(root / "nope.exe")})["message"])
    expect("a missing venv is explained", "Python folder" in apps.run({"py": str(root / "venv" / "Scripts" / "pythonw.exe")})["message"])
    expect("a missing script is explained", "start script" in apps.run({"ps1": "launch.ps1"}, str(root))["message"])
    expect("only web links open as websites", not apps.run({"url": "file:///C:/Windows"})["ok"])
    expect("an unknown Start-menu name is explained", "Start menu" in apps.run({"startmenu": "No Such App 12345"})["message"])

    # ---------- adding and removing apps (in a temporary apps.json) ----------
    real_store = apps.STORE
    apps.STORE = root / "apps.json"
    try:
        exe = root / "Discord.exe"
        exe.write_bytes(b"MZ")
        r = apps.add("exe", str(exe))
        expect("an .exe is added under its own name", r["ok"] and apps.load()["added"][0]["name"] == "Discord")
        expect("adding it twice doesn't duplicate", apps.add("exe", str(exe))["ok"] and len(apps.load()["added"]) == 1)
        expect("a website needs https://", not apps.add("url", "hoyolab")["ok"])
        r = apps.add("url", "https://www.hoyolab.com/home")
        expect("a website is added with a short name", r["ok"] and apps.load()["added"][1]["name"] == "hoyolab.com")
        expect("a missing file can't be added", not apps.add("exe", str(root / "gone.exe"))["ok"])
        first = apps.load()["added"][0]["id"]
        expect("remove takes it off Home", apps.remove(first)["ok"] and len(apps.load()["added"]) == 1)
        expect("the file itself is untouched by remove", exe.exists())
        apps.STORE.write_text("{broken", encoding="utf-8")
        expect("a broken apps.json starts empty instead of crashing", apps.load() == {"added": [], "overrides": {}, "hidden": []})
    finally:
        apps.STORE = real_store

# ---------- his real PC ----------
real = apps.find_projects()
names = [p["name"] for p in real]
expect("his projects are found (Waypoint, Leyline, Housecall, Toolbelt…)", all(n in names for n in ("Waypoint", "Leyline", "Housecall", "Toolbelt", "Snipper")))
missing = []
for p in real:
    o = p.get("open") or {}
    target = None
    if "py" in o:
        target = Path(p["folder"]) / o["py"] if o.get("local_py") else Path(os.path.expandvars(o["py"]))
    elif "exe" in o:
        target = Path(os.path.expandvars(o["exe"]))
    elif "file" in o:
        target = Path(p["folder"]) / os.path.expandvars(o["file"])
    elif "ps1" in o:
        target = Path(p["folder"]) / o["ps1"]
    if target is not None and not target.exists():
        missing.append("%s: %s" % (p["name"], target))
expect("every launch target on this PC exists", not missing)
for m in missing:
    print("      missing: " + m)
sm = apps.start_menu()
expect("the Start menu is read, 'Uninstall X' shortcuts left out (Revo Uninstaller itself stays)",
       len(sm) > 10 and not any(a["name"].lower().startswith("uninstall ") for a in sm))
expect("VS Code is found", apps.vscode() is not None)

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_home)")
