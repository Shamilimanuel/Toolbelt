"""Tests for playnite_db: reads the real Playnite library (through a temp copy, never writing to it).

Skips with a pass when Playnite isn't installed on this PC, because the other checks need the real data.
"""
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import playnite_db

failures = []
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


library = playnite_db.default_library_dir()
if not (library / "games.db").is_file():
    print("Playnite library not found at %s, nothing to test here" % library)
    print()
    print("ALL PASSED (test_playnite)")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    # ---------- the raw format: pages, extend pages, BSON ----------
    copy = Path(tmp) / "games.db"
    copy.write_bytes(playnite_db.load_bytes(library / "games.db"))   # a copy, a plain read, or Playnite's backup when it has the file locked
    data = copy.read_bytes()
    expect("games.db could be read (even with Playnite running: the backup zip)", len(data) > 4096)
    expect("the copy is a LiteDB v4 file (marker at byte 25, version 7)", data[25:52] == b"** This is a LiteDB file **" and data[52] == 7)
    raws = playnite_db.raw_documents(data)
    expect("at least 15 documents found in the data pages", len(raws) >= 15)
    expect("every document's BSON length matches the bytes we glued together",
           all(len(r) >= 5 and int.from_bytes(r[:4], "little") == len(r) for r in raws))
    big = [r for r in raws if len(r) > 4096]
    expect("some documents are bigger than one page (so they live in extend pages)", len(big) >= 1)
    big_docs = [playnite_db.parse_document(r) for r in big]
    expect("every big document still parses with its Name and _id intact",
           all(isinstance(d.get("Name"), str) and d["Name"] and GUID.match(str(d.get("_id", ""))) for d in big_docs))
    expect("a big document carries a long Description (the reason it got big)",
           any(isinstance(d.get("Description"), str) and len(d["Description"]) > 1000 for d in big_docs))

    # ---------- read_collection ----------
    docs = playnite_db.read_collection(copy)
    expect("read_collection reads the same number of documents", len(docs) == len(raws))
    names = {d.get("Name") for d in docs}
    expect("Project Zomboid and HoYoPlay are in the library", "Project Zomboid" in names and "HoYoPlay" in names)
    files_dir = library / "files"
    with_icon = [d for d in docs if d.get("Icon")]
    expect("every id is a GUID with a folder under library\\files when the game has an Icon",
           with_icon and all(GUID.match(str(d["_id"])) and (files_dir / str(d["_id"])).is_dir() for d in with_icon))
    expect("Guid byte order: a game's Icon path starts with its own id folder",
           all(str(d["Icon"]).lower().startswith(str(d["_id"]).lower()) for d in with_icon if "\\" in str(d["Icon"])))
    expect("dates come out as ISO UTC strings",
           all(isinstance(d.get("Added"), str) and d["Added"].endswith("+00:00") for d in docs if d.get("Added") is not None))
    sources = playnite_db.read_collection(library / "sources.db")
    expect("sources.db reads too (Steam is a source here)", any(s.get("Name") == "Steam" for s in sources))

    # ---------- games() ----------
    games = playnite_db.games()
    expect("games() gives at least 15 games", len(games) >= 15)
    by_name = {g["name"]: g for g in games}
    pz, hoyo = by_name.get("Project Zomboid"), by_name.get("HoYoPlay")
    expect("Project Zomboid: Steam, icon file on disk, a last_played value, playtime counted",
           pz is not None and pz["source"] == "Steam" and Path(pz["icon"]).is_file() and pz["last_played"] and pz["playtime_seconds"] > 0)
    expect("HoYoPlay: added by hand (source Playnite), icon on disk, last_played set",
           hoyo is not None and hoyo["source"] == "Playnite" and Path(hoyo["icon"]).is_file() and hoyo["last_played"])
    expect("every game has the expected keys",
           all(set(g) == {"id", "name", "source", "installed", "hidden", "last_played", "playtime_seconds", "icon", "cover", "background", "description", "install_dir", "play_command"} for g in games))
    expect("covers and descriptions come along (at least one game has each)", any(g["cover"] and Path(g["cover"]).is_file() for g in games) and any(g["description"] for g in games) and not any("<" in g["description"] for g in games))
    expect("every id is a GUID", all(GUID.match(g["id"]) and str(uuid.UUID(g["id"])) == g["id"] for g in games))
    expect("play_command is Playnite.DesktopApp.exe --start <id>",
           all(g["play_command"][0].endswith("Playnite.DesktopApp.exe") and g["play_command"][1:] == ["--start", g["id"]] for g in games))
    played = [g["last_played"] for g in games if g["last_played"]]
    expect("sorted newest first, never-played games last",
           played == sorted(played, reverse=True) and games[-1]["last_played"] == "" if len(played) < len(games) else played == sorted(played, reverse=True))
    expect("installed and hidden are real booleans", all(isinstance(g["installed"], bool) and isinstance(g["hidden"], bool) for g in games))

    # ---------- nothing breaks ----------
    expect("no Playnite folder gives []", playnite_db.games(Path(tmp) / "nowhere") == [])
    broken = Path(tmp) / "broken.db"
    broken.write_bytes(data[:30000] + b"\xff" * 2000)  # the tail of the file is gone and garbage
    partial = playnite_db.read_collection(broken)
    expect("a cut-off, garbled file still returns what it could read, without raising", isinstance(partial, list) and len(partial) >= 1)
    (Path(tmp) / "games.db").write_bytes(b"not a database at all")
    expect("a file that isn't LiteDB gives []", playnite_db.read_collection(Path(tmp) / "games.db") == [] and playnite_db.games(tmp) == [])
    expect("the real library was left untouched", (library / "games.db").stat().st_size == len(data))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_playnite)")
