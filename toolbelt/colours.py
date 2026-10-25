"""Colours: his saved gradients (kept in %LOCALAPPDATA%\\Toolbelt\\colours.json) and the main colours of a picture.

The gradient maker itself runs in the page (it has to react to every key press); Python only keeps what should last.
"""
import json
import os
import re

from PIL import Image

from settings import DATA

STORE = DATA / "colours.json"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load():
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    saved = [s for s in data.get("saved", []) if isinstance(s, dict) and isinstance(s.get("n"), str)
             and isinstance(s.get("s"), list) and 2 <= len(s["s"]) <= 6 and all(isinstance(c, str) and HEX.match(c) for c in s["s"])]
    return {"saved": saved[:100], "last": data.get("last") if isinstance(data.get("last"), dict) else None}


def store(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STORE)


def save_gradient(name, stops):
    stops = [str(c).upper() for c in (stops or [])]
    if not (2 <= len(stops) <= 6) or not all(HEX.match(c) for c in stops):
        return {"ok": False, "message": "A gradient needs 2 to 6 colours like #FF5F6D."}
    data = load()
    data["saved"] = [{"n": str(name).strip()[:40] or "Gradient", "s": stops}] + [s for s in data["saved"] if s["s"] != stops]
    store(data)
    return {"ok": True, "message": "Saved", "saved": data["saved"]}


def delete_gradient(index):
    data = load()
    if 0 <= int(index) < len(data["saved"]):
        data["saved"].pop(int(index))
        store(data)
    return {"ok": True, "saved": data["saved"]}


def remember(state):
    """The gradient he was working on, so it's still there next time."""
    if not isinstance(state, dict):
        return {"ok": False}
    data = load()
    data["last"] = {k: state[k] for k in ("text", "stops", "fmt", "b", "i", "u", "s", "k", "sh", "shc", "sha") if k in state}
    store(data)
    return {"ok": True}


def picture_palette(path, count=6):
    """The main colours of a picture, biggest first, as #RRGGBB."""
    img = Image.open(path)
    img.thumbnail((120, 120))
    img = img.convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img.getchannel("A"))
    total = flat.width * flat.height
    groups = []                     # [count, [r, g, b]]: each group shows its most common real pixel; look-alikes merged
    for n, rgb in sorted(flat.getcolors(total), reverse=True):
        for g in groups:
            if sum((a - b) ** 2 for a, b in zip(g[1], rgb)) < 48 ** 2:     # looks the same to a person: merge
                g[0] += n
                break
        else:
            groups.append([n, list(rgb)])
    groups = [g for g in sorted(groups, key=lambda g: -g[0]) if g[0] / total >= 0.015]    # drop specks
    return ["#%02X%02X%02X" % tuple(g[1]) for g in groups][:count]
