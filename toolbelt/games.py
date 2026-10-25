r"""The games on this PC, read from the launchers he already has (14 Oct): Playnite, Steam and HoYoPlay.

Nothing here talks to the internet. Each reader returns the same shape:
    {"key": "steam:271590", "name": "...", "source": "Steam", "last_played": "2026-10-13T20:19:14Z" or "",
     "playtime": seconds, "installed": True, "icon": r"C:\...\x.ico" or "", "play": ["steam://rungameid/271590"]}
`play` is what to run: a URL (steam://…), or a program with its arguments.
Games that appear in two launchers (Playnite imports Steam) are merged by name; the newest "last played" wins.
"""
import hashlib
import json
import os
import re
import time
import winreg
from datetime import datetime, timezone
from pathlib import Path

from settings import DATA

try:
    import playnite_db
except ImportError:                                           # the Playnite reader is its own module
    playnite_db = None

LAUNCHERS = {"Steam", "Playnite", "HoYoPlay"}
NOT_GAMES = {"steamworks common redistributables", "steam", "discord", "epic games launcher", "revo uninstaller", "wallpaper engine", "hoyoplay"}


def iso(unix):
    try:
        unix = int(unix)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(unix, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if unix > 0 else ""


# ---------- Valve's text format (.vdf / .acf): "key" "value" and "key" { ... } ----------
_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def parse_vdf(text):
    stack = [{}]
    key = None
    for match in _TOKEN.finditer(text):
        word, brace = match.group(1), match.group(2)
        if brace == "{":
            new = {}
            stack[-1][key] = new
            stack.append(new)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif key is None:
            key = word.replace('\\"', '"').replace("\\\\", "\\")
        else:
            stack[-1][key] = word.replace('\\"', '"').replace("\\\\", "\\")
            key = None
    return stack[0]


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------- Steam ----------
def steam_dir():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            path = Path(winreg.QueryValueEx(key, "SteamPath")[0])
            if path.is_dir():
                return path
    except OSError:
        pass
    for guess in (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam", Path(r"C:\Program Files\Steam")):
        if guess.is_dir():
            return guess
    return None


def steam_art(root, appid):
    """Steam keeps pictures per game in appcache\\librarycache\\<appid>\\: a small square icon (<hash>.jpg), the cover
    (library_600x900.jpg) and the wide banner (library_hero.jpg)."""
    folder = root / "appcache" / "librarycache" / str(appid)
    if not folder.is_dir():
        return "", "", ""
    small = [p for p in folder.glob("*.jpg") if not p.name.startswith("library_") and p.stat().st_size < 50000]
    cover = folder / "library_600x900.jpg"
    hero = folder / "library_hero.jpg"
    return (str(small[0]) if small else ""), (str(cover) if cover.exists() else ""), (str(hero) if hero.exists() else "")


def steam_icon(root, appid):
    return steam_art(root, appid)[0]


def steam_games(root=None):
    root = Path(root) if root else steam_dir()
    if not root:
        return []
    libraries = [root]
    folders = parse_vdf(_read(root / "steamapps" / "libraryfolders.vdf")).get("libraryfolders", {})
    for entry in folders.values():
        if isinstance(entry, dict) and entry.get("path"):
            path = Path(entry["path"])
            if path.is_dir() and path not in libraries:
                libraries.append(path)
    # Steam's own record of when each game was last played (also games that aren't installed any more)
    played = {}
    for cfg in root.glob("userdata/*/config/localconfig.vdf"):
        apps = parse_vdf(_read(cfg)).get("UserLocalConfigStore", {}).get("Software", {}).get("Valve", {}).get("Steam", {}).get("apps", {})
        for appid, info in apps.items():
            if isinstance(info, dict) and info.get("LastPlayed"):
                played[appid] = max(played.get(appid, 0), int(info["LastPlayed"]) if info["LastPlayed"].isdigit() else 0)
    out = []
    for lib in libraries:
        for manifest in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
            app = parse_vdf(_read(manifest)).get("AppState", {})
            appid, name = app.get("appid", ""), app.get("name", "")
            if not appid or not name or name.lower() in NOT_GAMES:
                continue
            last = max(int(app.get("LastPlayed", "0") or 0), played.get(appid, 0))
            icon, cover, hero = steam_art(root, appid)
            out.append({"key": "steam:" + appid, "name": name, "source": "Steam", "last_played": iso(last), "playtime": 0,
                        "installed": True, "icon": icon, "cover": cover, "banner": hero, "play": ["steam://rungameid/" + appid],
                        "folder": str(lib / "steamapps" / "common" / app.get("installdir", "")) if app.get("installdir") else ""})
    return out


# ---------- Epic Games (Fortnite and friends) ----------
def epic_games(manifests=None):
    """Epic writes one .item (JSON) per installed game in ProgramData. Starting goes through its launcher link."""
    folder = Path(manifests) if manifests else Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    out = []
    if not folder.is_dir():
        return out
    for item in sorted(folder.glob("*.item")):
        try:
            d = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name, where = d.get("DisplayName", ""), d.get("InstallLocation", "")
        if not name or d.get("bIsIncompleteInstall") or not where or not Path(where).is_dir():
            continue
        exe = Path(where) / d.get("LaunchExecutable", "")
        link = "com.epicgames.launcher://apps/%s%%3A%s%%3A%s?action=launch&silent=true" % (d.get("CatalogNamespace", ""), d.get("CatalogItemId", ""), d.get("AppName", ""))
        newest = 0
        try:
            newest = int(exe.stat().st_atime) if exe.exists() else 0
        except OSError:
            pass
        out.append({"key": "epic:" + str(d.get("AppName") or item.stem), "name": name, "source": "Epic", "last_played": "", "playtime": 0,
                    "installed": True, "icon": str(exe) if exe.exists() else "", "cover": "", "banner": "", "play": [link], "folder": where})
    return out


# ---------- Minecraft (the launcher from the Store / Xbox app) ----------
def minecraft_games():
    for exe in (Path(r"C:\XboxGames\Minecraft Launcher\Content\Minecraft.exe"), Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Minecraft Launcher" / "MinecraftLauncher.exe"):
        if exe.exists():
            return [{"key": "minecraft", "name": "Minecraft", "source": "Minecraft", "last_played": "", "playtime": 0, "installed": True,
                     "icon": str(exe), "cover": "", "banner": "", "play": [str(exe)], "folder": str(Path(os.environ.get("APPDATA", "")) / ".minecraft")}]
    return []


# ---------- HoYoPlay (Genshin and friends) ----------
def hoyoplay_games():
    out = []
    try:
        base = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Cognosphere\HYP\1_0")
    except OSError:
        return out
    names = {"hk4e": "Genshin Impact", "hkrpg": "Honkai: Star Rail", "nap": "Zenless Zone Zero", "bh3": "Honkai Impact 3rd"}
    launcher = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "HoYoPlay" / "launcher.exe"
    with base:
        i = 0
        while True:
            try:
                biz = winreg.EnumKey(base, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(base, biz) as key:
                    path = winreg.QueryValueEx(key, "GameInstallPath")[0]
                    icon = ""
                    try:
                        icon = winreg.QueryValueEx(key, "GameIconPath")[0]
                    except OSError:
                        pass
            except OSError:
                continue
            if not path or not Path(path).is_dir():
                continue                                       # listed by the launcher, not installed
            name = names.get(biz.split("_")[0], biz)
            newest = 0
            for exe in Path(path).glob("*.exe"):
                try:
                    newest = max(newest, int(exe.stat().st_atime))
                except OSError:
                    pass
            out.append({"key": "hoyo:" + biz, "name": name, "source": "HoYoPlay", "last_played": "", "playtime": 0,
                        "installed": True, "icon": icon if icon and Path(icon).exists() else "", "cover": "", "banner": "",
                        "play": [str(launcher)] if launcher.exists() else [str(Path(path))], "folder": path})
    return out


# ---------- Playnite ----------
def playnite_games():
    if playnite_db is None:
        return []
    out = []
    for g in playnite_db.games():
        name = g.get("name") or ""
        if g.get("hidden") or not name or (name.lower() in NOT_GAMES and name.lower() != "hoyoplay"):
            continue
        out.append({"key": "playnite:" + g["id"], "name": name, "source": g.get("source") or "Playnite",
                    "last_played": (g.get("last_played") or "").replace("+00:00", "Z"), "playtime": int(g.get("playtime_seconds", 0) or 0),
                    "installed": bool(g.get("installed", True)), "icon": g.get("icon", ""), "cover": g.get("cover", ""), "banner": g.get("background", ""),
                    "description": g.get("description", ""), "folder": g.get("install_dir", ""), "play": g.get("play_command", []),
                    "launcher": name.lower() == "hoyoplay"})           # Playnite starts Genshin through HoYoPlay, so its time counts
    return out


# ---------- his own additions: games added by their .exe, favourites, hidden ones, custom artwork ----------
STORE = DATA / "games.json"
ART_DIR = DATA / "art"


def _load_store():
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {"custom": list(data.get("custom", [])), "hidden": list(data.get("hidden", [])), "favourites": list(data.get("favourites", [])),
                    "art": dict(data.get("art", {})), "fx": dict(data.get("fx", {}))}
    except (OSError, ValueError):
        pass
    return {"custom": [], "hidden": [], "favourites": [], "art": {}, "fx": {}}


def _save_store(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, STORE)


def custom_games():
    out = []
    for c in _load_store()["custom"]:
        exe = c.get("exe", "")
        if not exe:
            continue
        out.append({"key": "custom:" + c.get("id", ""), "name": c.get("name", Path(exe).stem), "source": "Added by hand", "last_played": c.get("last_played", ""),
                    "playtime": 0, "installed": Path(exe).exists(), "icon": exe, "cover": "", "banner": "", "play": [exe], "folder": str(Path(exe).parent)})
    return out


def add_custom(exe, name=""):
    exe = str(exe)
    if not Path(exe).is_file():
        return {"ok": False, "message": "That program isn't there."}
    data = _load_store()
    for c in data["custom"]:
        if c.get("exe", "").lower() == exe.lower():
            return {"ok": False, "message": "%s is already in the list." % c.get("name", "It")}
    new = {"id": hashlib.sha1(exe.lower().encode("utf-8")).hexdigest()[:10], "exe": exe, "name": name or Path(exe).stem, "added": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    data["custom"].append(new)
    _save_store(data)
    return {"ok": True, "message": "Added " + new["name"], "key": "custom:" + new["id"]}


def remove_custom(key):
    data = _load_store()
    before = len(data["custom"])
    data["custom"] = [c for c in data["custom"] if "custom:" + c.get("id", "") != key]
    if len(data["custom"]) == before:
        return {"ok": False, "message": "Only games you added by hand can be removed; hide the others instead."}
    _save_store(data)
    return {"ok": True, "message": "Removed."}


def set_flag(key, which, on):
    """which: 'hidden' or 'favourites'."""
    data = _load_store()
    items = [k for k in data[which] if k != key]
    if on:
        items.append(key)
    data[which] = items
    _save_store(data)
    return {"ok": True, "message": ""}


def set_fx(key, fx):
    data = _load_store()
    if fx in ("off", "shine", "tilt", "scan", "glow"):
        data["fx"][key] = fx
        _save_store(data)
    return {"ok": True, "message": ""}


def _kind_of(path):
    ext = Path(path).suffix.lower()
    return "video" if ext in (".mp4", ".webm", ".mov", ".m4v") else "gif" if ext == ".gif" else "pic" if ext in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp") else ""


def _banner_list(art):
    """The game's backgrounds in order (his ask, 15 Oct: several per game, slowly fading from one to the next).
    Entries are {"path", "kind"} for his own files and {"own": True} for the launcher's own (Steam's hero…).
    Before lists there was one "banner": that becomes a list of one; nothing set = the launcher's own."""
    if isinstance(art.get("banners"), list):
        return [dict(b) for b in art["banners"] if isinstance(b, dict) and (b.get("own") or b.get("path"))]
    if art.get("banner"):
        return [dict(art["banner"])]
    return [{"own": True}]


def _save_banners(data, key, banners):
    entry = data["art"].setdefault(key, {})
    entry.pop("banner", None)
    entry["banners"] = banners


def set_art(key, which, source):
    """A cover he picked, or one more background (picture, GIF or video): copied into AppData\\Toolbelt\\art so it
    stays even if he moves the file. A new cover replaces the old one; a new background is added to the game's list."""
    source = Path(str(source))
    if which not in ("cover", "banner") or not source.is_file():
        return {"ok": False, "message": "That file isn't there."}
    ext = source.suffix.lower()
    kind = _kind_of(source)
    if not kind:                                              # covers may be short videos too (his ask, 15 Oct)
        return {"ok": False, "message": "Use a picture, a GIF or a short video (MP4, WebM)."}
    if source.stat().st_size > 40 * 1024 * 1024:
        return {"ok": False, "message": "That file is bigger than 40 MB; a short clip or a smaller picture works better here."}
    ART_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9]", "_", key.lower())
    import shutil
    data = _load_store()
    if which == "cover":
        target = ART_DIR / ("%s-cover%s" % (stem, ext))
        shutil.copy(source, target)
        data["art"].setdefault(key, {})["cover"] = {"path": str(target), "kind": kind}
        _save_store(data)
        return {"ok": True, "message": "Saved the new cover.", "kind": kind}
    target = ART_DIR / ("%s-banner-%d%s" % (stem, int(time.time() * 1000), ext))   # each background its own file
    shutil.copy(source, target)
    banners = _banner_list(data["art"].get(key, {}))
    banners.append({"path": str(target), "kind": kind})
    _save_banners(data, key, banners)
    _save_store(data)
    n = len(banners)
    return {"ok": True, "message": "Added a background (%d now: they fade from one to the next)." % n if n > 1 else "Saved the new background.", "kind": kind, "count": n}


def remove_banner(key, index):
    """Takes one background out of the game's list (his own file is deleted; the launcher's own is just left out)."""
    data = _load_store()
    banners = _banner_list(data["art"].get(key, {}))
    if not 0 <= int(index) < len(banners):
        return {"ok": False, "message": "That background isn't there any more."}
    gone = banners.pop(int(index))
    if gone.get("path"):
        try:
            Path(gone["path"]).unlink()
        except OSError:
            pass
    _save_banners(data, key, banners)
    _save_store(data)
    return {"ok": True, "message": "Removed that background." if banners else "No backgrounds left: the game shows its plain colours."}


def move_banner(key, index, step):
    """Moves one background earlier (-1) or later (+1) in the order they fade through."""
    data = _load_store()
    banners = _banner_list(data["art"].get(key, {}))
    i, j = int(index), int(index) + int(step)
    if not (0 <= i < len(banners) and 0 <= j < len(banners)):
        return {"ok": False, "message": ""}
    banners[i], banners[j] = banners[j], banners[i]
    _save_banners(data, key, banners)
    _save_store(data)
    return {"ok": True, "message": ""}


def add_own_banner(key):
    """Puts the launcher's own background (back) into the list, at the start."""
    data = _load_store()
    banners = [b for b in _banner_list(data["art"].get(key, {})) if not b.get("own")]
    _save_banners(data, key, [{"own": True}] + banners)
    _save_store(data)
    return {"ok": True, "message": "The launcher's own background is back in the list."}


SGDB_THUMB = re.compile(r"^(https?://cdn\d*\.steamgriddb\.com/)(hero|grid|logo|icon)_thumb/([0-9a-f]+)\.(\w+)(?:\?.*)?$", re.I)


def full_size_links(url):
    """SteamGridDB's pages show previews: "Copy image address" gives .../hero_thumb/<id>.jpg (849 × 274) while the real
    file is .../hero/<id>.<png|jpg|webp|webm|gif> (often 3840 × 1240). Found 16 Oct: his backgrounds looked like 360p.
    Returns the links to try, the full-size ones first, the link itself last."""
    m = SGDB_THUMB.match(str(url).strip())
    if not m:
        return [url]
    base, kind, ident, ext = m.group(1), m.group(2).lower(), m.group(3), m.group(4).lower()
    exts = [ext] + [e for e in ("png", "jpg", "webp", "webm", "gif") if e != ext]
    return ["%s%s/%s.%s" % (base, kind, ident, e) for e in exts] + [url]


def _open_full_size(url, request):
    """Opens the first of full_size_links() that answers; a 404 just means "try the next ending"."""
    import urllib.error
    last = None
    for link in full_size_links(url):
        try:
            return request.urlopen(request.Request(link, headers={"User-Agent": "Mozilla/5.0 Toolbelt/1.0"}), timeout=30)
        except urllib.error.HTTPError as error:
            last = error
            if error.code not in (403, 404):
                raise
    raise last


def fetch_art(url):
    """Downloads a picture / GIF / short video he linked (only when he pastes a link: Toolbelt never fetches art on its own).
    Returns the temporary file's path, or raises ValueError with a plain reason."""
    import tempfile
    import urllib.request
    url = str(url).strip()
    if not re.match(r"^https?://", url):
        raise ValueError("That isn't a web link (it should start with https://).")
    with _open_full_size(url, urllib.request) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "image/avif": ".avif", "video/mp4": ".mp4", "video/webm": ".webm"}.get(ctype, "")
        if not ext:
            guess = Path(url.split("?")[0]).suffix.lower()
            ext = guess if guess in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".mp4", ".webm") else ""
        if not ext:
            raise ValueError("That link isn't a picture, GIF or video (it says %s). Open the picture itself and copy its address." % (ctype or "unknown"))
        data = resp.read(40 * 1024 * 1024 + 1)
    if len(data) > 40 * 1024 * 1024:
        raise ValueError("That file is bigger than 40 MB.")
    tmp = Path(tempfile.gettempdir()) / ("toolbelt-art-%d%s" % (int(time.time() * 1000), ext))
    tmp.write_bytes(data)
    return tmp


def search_links(name, which):
    """Where to look for art on the web: SteamGridDB has covers (grids) and banners (heroes) for nearly every game."""
    from urllib.parse import quote
    term = quote(name)
    if which == "banner":
        return "https://www.steamgriddb.com/search/heroes?term=" + term
    return "https://www.steamgriddb.com/search/grids?term=" + term


def clear_art(key, which):
    """Back to the launcher's own cover, or the backgrounds back to only the launcher's own (his files deleted)."""
    data = _load_store()
    art = data["art"].get(key, {})
    if which == "banner":
        for b in _banner_list(art):
            if b.get("path"):
                try:
                    Path(b["path"]).unlink()
                except OSError:
                    pass
        art.pop("banner", None)
        art.pop("banners", None)
        _save_store(data)
        return {"ok": True, "message": "Back to the launcher's own background."}
    entry = art.pop(which, None)
    if entry:
        try:
            Path(entry["path"]).unlink()
        except OSError:
            pass
    _save_store(data)
    return {"ok": True, "message": "Back to the launcher's own " + which + "."}


def decorate(games):
    """Adds his flags and artwork choices to a list of games (in place) and returns it."""
    data = _load_store()
    for g in games:
        art = data["art"].get(g["key"], {})
        g["favourite"] = g["key"] in data["favourites"]
        g["hidden"] = g["key"] in data["hidden"]
        g["fx"] = data["fx"].get(g["key"], "off")
        g["cover_kind"] = art.get("cover", {}).get("kind", "pic")
        if art.get("cover"):
            g["cover"] = art["cover"]["path"]
        g["custom_cover"] = bool(art.get("cover"))
        # the backgrounds, in order: his own files and/or the launcher's own (when the launcher has one)
        launcher = g.get("banner") or ""
        banners = []
        for b in _banner_list(art):
            if b.get("own"):
                if launcher:
                    banners.append({"path": launcher, "kind": _kind_of(launcher) or "pic", "own": True})
            elif Path(b["path"]).exists():
                banners.append({"path": b["path"], "kind": b.get("kind") or _kind_of(b["path"]) or "pic", "own": False})
        g["banners"] = banners
        g["banner"] = banners[0]["path"] if banners else ""
        g["banner_kind"] = banners[0]["kind"] if banners else "pic"
        g["custom_banner"] = any(not b["own"] for b in banners)
        g["own_banner"] = bool(launcher)                     # the launcher has one, to offer it back after removal
    return games


# ---------- all together ----------
def _same(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def all_games(readers=None):
    """Every game once, newest played first. Playnite's entry is kept when a game is in Playnite and Steam, with Steam's
    newer "last played" and Steam's icon when Playnite has none."""
    readers = readers or (playnite_games, steam_games, epic_games, hoyoplay_games, minecraft_games, custom_games)
    merged = {}
    for reader in readers:
        try:
            found = reader()
        except Exception:                                      # one broken launcher must not hide the others
            found = []
        for g in found:
            k = _same(g["name"])
            if k not in merged:
                merged[k] = dict(g)
                continue
            have = merged[k]
            if g["last_played"] > have["last_played"]:
                have["last_played"] = g["last_played"]
            for field in ("icon", "cover", "banner", "description", "folder"):
                if not have.get(field) and g.get(field):
                    have[field] = g[field]
            if not have["play"] and g["play"]:
                have["play"] = g["play"]
            have["playtime"] = max(have["playtime"], g["playtime"])
            have["installed"] = have["installed"] or g["installed"]
    hoyo = [g for g in merged.values() if g.get("launcher")]
    if hoyo:                                                   # the launcher's "last played" belongs to its games
        for g in merged.values():
            if g["source"] == "HoYoPlay" and not g.get("launcher"):
                g["last_played"] = max(g["last_played"], hoyo[0]["last_played"])
                g["play"] = g["play"] or hoyo[0]["play"]
    games = [g for g in merged.values() if g["installed"] and not g.get("launcher")]
    for g in games:
        g.pop("launcher", None)
        for field in ("cover", "banner", "description", "folder"):
            g.setdefault(field, "")
    games.sort(key=lambda g: (g["last_played"], g["name"].lower()), reverse=True)
    return decorate(games)


def visible(games):
    return [g for g in games if not g.get("hidden")]


def find(key, games=None):
    for g in games or all_games():
        if g["key"] == key:
            return g
    return None


def play(game):
    """Starts a game: a steam:// link through Windows, or its program. Returns (ok, message)."""
    import subprocess
    cmd = game.get("play") or []
    if not cmd:
        return False, "Toolbelt doesn't know how to start " + game["name"] + "."
    try:
        if cmd[0].startswith("steam://") or cmd[0].startswith("com.epicgames.launcher://") or cmd[0].lower().endswith(".lnk"):
            os.startfile(cmd[0])
        else:
            subprocess.Popen(cmd, cwd=str(Path(cmd[0]).parent) if Path(cmd[0]).exists() else None)
        return True, "Starting " + game["name"]
    except OSError as error:
        return False, "Couldn't start %s: %s" % (game["name"], error)
