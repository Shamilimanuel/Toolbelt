"""Rename many files at once (Handy tools, 15 Oct).

He picks the files (or a folder); the rules make a new name for each one; the page shows old → new before anything
happens. Renaming goes in two steps (first to temporary names, then to the final ones), so swapping two names or
numbering over existing names can't trip over itself. The last rename can be undone; the record of it is kept in
%LOCALAPPDATA%\\Toolbelt\\rename-undo.json until the next rename.
Only files he picked through Windows' own picker are ever touched (main.py keeps that list).
"""
import json
import os
import re
import time
import uuid
from pathlib import Path

from settings import DATA

UNDO = DATA / "rename-undo.json"
BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}


def _date_of(path, which):
    """The photo's own date (EXIF, when it has one) or the file's last-changed date, as 2026-10-15."""
    if which == "taken":
        try:
            from PIL import Image
            with Image.open(path) as img:
                exif = img.getexif()
                raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)      # DateTimeOriginal, else DateTime
                if raw:
                    return str(raw)[:10].replace(":", "-")
        except Exception:
            pass
    return time.strftime("%Y-%m-%d", time.localtime(Path(path).stat().st_mtime))


def _case(text, how):
    if how == "lower":
        return text.lower()
    if how == "upper":
        return text.upper()
    if how == "title":
        return " ".join(w[:1].upper() + w[1:].lower() for w in text.split(" "))
    return text


def new_name(path, index, rules):
    """The new file name for one file. rules: find, replace, regex, prefix, suffix, case, number (off / before / after /
    only), start, digits, sep, date (off / taken / changed), ext_case (keep / lower / upper), base (a new name for all)."""
    p = Path(path)
    stem, ext = p.stem, p.suffix
    if rules.get("base"):
        stem = str(rules["base"])
    find = str(rules.get("find") or "")
    if find:
        rep = str(rules.get("replace") or "")
        if rules.get("regex"):
            try:
                stem = re.sub(find, rep, stem)
            except re.error as error:
                raise ValueError("The pattern isn't valid: %s" % error)
        else:
            stem = re.sub(re.escape(find), lambda m: rep, stem, flags=0 if rules.get("match_case") else re.I)
    stem = _case(stem, rules.get("case", "keep"))
    sep = str(rules.get("sep", " - "))
    if rules.get("date", "off") != "off":
        stem = _date_of(p, rules["date"]) + sep + stem
    stem = str(rules.get("prefix") or "") + stem + str(rules.get("suffix") or "")
    mode = rules.get("number", "off")
    if mode != "off":
        n = str(int(rules.get("start", 1) or 0) + index).zfill(max(1, min(6, int(rules.get("digits", 2) or 1))))
        stem = n if mode == "only" else (n + sep + stem if mode == "before" else stem + sep + n)
    if rules.get("ext_case") == "lower":
        ext = ext.lower()
    elif rules.get("ext_case") == "upper":
        ext = ext.upper()
    return stem.strip().rstrip(".") + ext


def plan(paths, rules):
    """[{path, old, new, problem}] for the page; nothing is renamed."""
    out, seen = [], {}
    targets = {str(Path(p)).lower() for p in paths}
    for i, path in enumerate(paths):
        p = Path(path)
        item = {"path": str(p), "old": p.name, "new": p.name, "problem": ""}
        try:
            name = new_name(p, i, rules)
        except ValueError as error:
            item["problem"] = str(error)
            out.append(item)
            continue
        item["new"] = name
        stem = Path(name).stem
        if not stem:
            item["problem"] = "empty name"
        elif BAD.search(name):
            item["problem"] = 'can\'t contain \\ / : * ? " < > |'
        elif stem.upper() in RESERVED:
            item["problem"] = "Windows keeps this name for itself"
        elif len(str(p.parent / name)) > 255:
            item["problem"] = "too long"
        key = str(p.parent / name).lower()
        if not item["problem"]:
            if key in seen:
                item["problem"] = "same name as %s" % seen[key]
            elif key != str(p).lower() and (p.parent / name).exists() and key not in targets:
                item["problem"] = "a file with this name is already there"
        seen[key] = p.name
        out.append(item)
    return out


def apply(items):
    """Renames the planned items (only those without a problem and with a new name). Returns how many, and keeps
    the undo record."""
    todo = [it for it in items if not it.get("problem") and it["old"] != it["new"]]
    if not todo:
        return {"ok": False, "message": "Nothing to rename."}
    stage, done = [], []
    try:
        for it in todo:                                           # step 1: out of the way, to temporary names
            src = Path(it["path"])
            tmp = src.with_name(".tb-rename-%s%s" % (uuid.uuid4().hex[:10], src.suffix))
            os.rename(src, tmp)
            stage.append((src, tmp, src.with_name(it["new"])))
        for src, tmp, dst in stage:                               # step 2: to the new names
            if dst.exists():
                raise OSError("%s appeared in the meantime" % dst.name)
            os.rename(tmp, dst)
            done.append((src, dst))
    except OSError as error:
        moved = dict(done)                                        # put everything back: new names → temporary, then → old
        for src, tmp, dst in stage:
            if moved.get(src) == dst:
                try:
                    os.rename(dst, tmp)
                except OSError:
                    pass
        for src, tmp, dst in stage:
            try:
                if tmp.exists() and not src.exists():
                    os.rename(tmp, src)
            except OSError:
                pass
        return {"ok": False, "message": "Stopped and put back: %s" % str(error)[:160]}
    UNDO.parent.mkdir(parents=True, exist_ok=True)
    UNDO.write_text(json.dumps([[str(a), str(b)] for a, b in done], ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "message": "Renamed %d file%s. Undo is there until the next rename." % (len(done), "" if len(done) == 1 else "s"),
            "renamed": [[str(a), str(b)] for a, b in done]}


def can_undo():
    try:
        return len(json.loads(UNDO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def undo():
    try:
        pairs = json.loads(UNDO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "message": "There's nothing to undo."}
    items = [{"path": new, "old": Path(new).name, "new": Path(old).name, "problem": "" if Path(new).exists() else "gone"} for old, new in pairs]
    missing = [it for it in items if it["problem"]]
    result = apply([it for it in items if not it["problem"]])
    if result["ok"]:
        UNDO.unlink(missing_ok=True)
        result["message"] = "Put %d name%s back%s." % (len(result["renamed"]), "" if len(result["renamed"]) == 1 else "s",
                                                       (" (%d file%s had moved)" % (len(missing), "" if len(missing) == 1 else "s")) if missing else "")
    return result
