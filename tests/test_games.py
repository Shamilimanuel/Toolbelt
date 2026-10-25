"""Tests for games.py (Steam's files, HoYoPlay, merging) and jumplist.py (written under a test identity, then removed)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import games                                                  # noqa: E402
import jumplist                                               # noqa: E402
import brand                                                  # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- Valve's text format ----------
vdf = games.parse_vdf('"AppState"\n{\n\t"appid"\t\t"271590"\n\t"name"\t\t"Grand Theft Auto V Legacy"\n\t"LastPlayed"\t\t"1791917954"\n\t"Nested" { "a" "1" "b" { "c" "x\\"y" } }\n}')
expect("vdf: keys, values and nested blocks", vdf["AppState"]["appid"] == "271590" and vdf["AppState"]["Nested"]["b"]["c"] == 'x"y')
expect("vdf: broken text doesn't crash", games.parse_vdf('"a" { "b"') == {"a": {}})

# ---------- a pretend Steam folder ----------
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "steamapps").mkdir()
    (root / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders" { "0" { "path" "%s" } "1" { "path" "D:\\\\Nope" } }' % str(root).replace("\\", "\\\\"), encoding="utf-8")
    (root / "steamapps" / "appmanifest_10.acf").write_text('"AppState" { "appid" "10" "name" "Counter-Strike" "LastPlayed" "1700000000" }', encoding="utf-8")
    (root / "steamapps" / "appmanifest_228980.acf").write_text('"AppState" { "appid" "228980" "name" "Steamworks Common Redistributables" "LastPlayed" "0" }', encoding="utf-8")
    (root / "userdata" / "1" / "config").mkdir(parents=True)
    (root / "userdata" / "1" / "config" / "localconfig.vdf").write_text('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "10" { "LastPlayed" "1791000000" } } } } } }', encoding="utf-8")
    (root / "appcache" / "librarycache" / "10").mkdir(parents=True)
    (root / "appcache" / "librarycache" / "10" / "abc.jpg").write_bytes(b"x" * 100)
    (root / "appcache" / "librarycache" / "10" / "library_hero.jpg").write_bytes(b"x" * 100)
    found = games.steam_games(root)
    expect("one real game found, the redistributables skipped", [g["name"] for g in found] == ["Counter-Strike"])
    g = found[0]
    expect("Steam's own newer 'last played' wins", g["last_played"] == "2026-10-03T04:00:00Z")
    expect("the small picture is the icon, steam:// starts it", g["icon"].endswith("abc.jpg") and g["play"] == ["steam://rungameid/10"])
expect("no Steam folder: empty list, no crash", games.steam_games(Path(tempfile.gettempdir()) / "nope-steam") == [])

# ---------- merging ----------
def r1():
    return [{"key": "playnite:1", "name": "Green Hell", "source": "Steam", "last_played": "2026-09-11T11:37:39Z", "playtime": 100, "installed": True, "icon": "", "play": ["p.exe"]},
            {"key": "playnite:2", "name": "HoYoPlay", "source": "Playnite", "last_played": "2026-10-14T06:00:00Z", "playtime": 0, "installed": True, "icon": "", "play": ["launcher.exe"], "launcher": True},
            {"key": "playnite:3", "name": "Gone", "source": "Steam", "last_played": "", "playtime": 0, "installed": False, "icon": "", "play": []}]


def r2():
    return [{"key": "steam:815370", "name": "Green Hell", "source": "Steam", "last_played": "2026-10-01T00:00:00Z", "playtime": 0, "installed": True, "icon": "g.jpg", "play": ["steam://rungameid/815370"]},
            {"key": "hoyo:hk4e_global", "name": "Genshin Impact", "source": "HoYoPlay", "last_played": "", "playtime": 0, "installed": True, "icon": "", "play": []}]


def broken():
    raise OSError("nope")


merged = games.all_games(readers=[r1, r2, broken])
names = [g["name"] for g in merged]
expect("the same game in Playnite and Steam is one entry; a broken reader is ignored", names.count("Green Hell") == 1 and "Gone" not in names and "HoYoPlay" not in names)
gh = games.find("playnite:1", merged)
expect("Playnite's entry kept, with Steam's newer time and icon", gh and gh["last_played"] == "2026-10-01T00:00:00Z" and gh["icon"] == "g.jpg" and gh["playtime"] == 100)
gi = games.find("hoyo:hk4e_global", merged)
expect("Genshin gets HoYoPlay's 'last played' and launcher, and comes first", gi and gi["last_played"] == "2026-10-14T06:00:00Z" and gi["play"] == ["launcher.exe"] and names[0] == "Genshin Impact")
expect("play refuses a game it can't start", games.play({"name": "X", "play": []}) == (False, "Toolbelt doesn't know how to start X."))

# ---------- Epic's manifests ----------
with tempfile.TemporaryDirectory() as tmp:
    import json
    (Path(tmp) / "a.item").write_text(json.dumps({"DisplayName": "Fortnite", "InstallLocation": tmp, "LaunchExecutable": "x.exe", "CatalogNamespace": "fn", "CatalogItemId": "4fe7", "AppName": "Fortnite", "bIsIncompleteInstall": False}), encoding="utf-8")
    (Path(tmp) / "b.item").write_text(json.dumps({"DisplayName": "Half", "InstallLocation": tmp, "bIsIncompleteInstall": True}), encoding="utf-8")
    (Path(tmp) / "c.item").write_text("{broken", encoding="utf-8")
    ep = games.epic_games(tmp)
    expect("Epic: one finished game, launched through Epic's link", len(ep) == 1 and ep[0]["name"] == "Fortnite" and ep[0]["play"] == ["com.epicgames.launcher://apps/fn%3A4fe7%3AFortnite?action=launch&silent=true"] and ep[0]["folder"] == tmp)

# ---------- his own store: added games, favourites, hidden, artwork ----------
real_store, real_art = games.STORE, games.ART_DIR
with tempfile.TemporaryDirectory() as tmp:
    games.STORE, games.ART_DIR = Path(tmp) / "games.json", Path(tmp) / "art"
    try:
        exe = Path(tmp) / "MyGame.exe"
        exe.write_bytes(b"MZ")
        added = games.add_custom(exe)
        expect("add a game by its .exe", added["ok"] and added["key"].startswith("custom:") and games.custom_games()[0]["name"] == "MyGame")
        expect("the same .exe twice is refused", not games.add_custom(exe)["ok"])
        expect("a missing .exe is refused", not games.add_custom(Path(tmp) / "nope.exe")["ok"])
        key = added["key"]
        games.set_flag(key, "favourites", True)
        games.set_flag("steam:1", "hidden", True)
        games.set_fx(key, "glow")
        games.set_fx(key, "nonsense")
        from PIL import Image
        pic = Path(tmp) / "cover.png"
        Image.new("RGB", (60, 90), (200, 50, 50)).save(pic)
        art = games.set_art(key, "cover", pic)
        expect("a cover is copied into the art folder", art["ok"] and art["kind"] == "pic" and list(games.ART_DIR.glob("*-cover.png")))
        expect("a program file can't be a cover", not games.set_art(key, "cover", exe)["ok"])
        clip = Path(tmp) / "loop.webm"
        clip.write_bytes(b"\x1aE\xdf\xa3 test")
        vid = games.set_art("steam:1", "cover", clip)              # covers may be videos too (his ask, 15 Oct)
        deco_v = games.decorate([{"key": "steam:1", "name": "S", "cover": "", "banner": ""}])
        expect("a short video can be a cover too", vid["ok"] and vid["kind"] == "video" and deco_v[0]["cover_kind"] == "video" and deco_v[0]["cover"].endswith("-cover.webm"))
        games.clear_art("steam:1", "cover")
        # several backgrounds per game (his ask, 15 Oct): added to a list, reordered, removed, the launcher's own back
        hero = Path(tmp) / "hero.jpg"
        Image.new("RGB", (64, 20), (10, 10, 200)).save(hero)
        bg1, bg2 = Path(tmp) / "one.png", Path(tmp) / "two.webm"
        Image.new("RGB", (64, 20), (200, 10, 10)).save(bg1)
        bg2.write_bytes(b"\x1aE\xdf\xa3 test")
        base = lambda: games.decorate([{"key": "steam:5", "name": "Five", "cover": "", "banner": str(hero)}])[0]     # noqa: E731
        expect("no backgrounds of his: the launcher's own is the one", [(b["own"], b["kind"]) for b in base()["banners"]] == [(True, "pic")])
        r1, r2 = games.set_art("steam:5", "banner", bg1), games.set_art("steam:5", "banner", bg2)
        d = base()
        expect("adding backgrounds keeps the launcher's own first and adds his after it", r2["count"] == 3 and [(b["own"], b["kind"]) for b in d["banners"]] == [(True, "pic"), (False, "pic"), (False, "video")]
               and d["banner"] == str(hero) and d["custom_banner"])
        games.move_banner("steam:5", 2, -1)
        expect("◀ moves one earlier", [b["kind"] for b in base()["banners"]] == ["pic", "video", "pic"])
        games.remove_banner("steam:5", 0)
        d = base()
        expect("✕ on the launcher's own leaves it out (and offers it back)", [b["own"] for b in d["banners"]] == [False, False] and d["own_banner"] and d["banner_kind"] == "video")
        games.add_own_banner("steam:5")
        expect("…and back it comes, first", [b["own"] for b in base()["banners"]] == [True, False, False])
        files = [b["path"] for b in base()["banners"] if not b["own"]]
        games.clear_art("steam:5", "banner")
        expect("🗑 All yours: back to only the launcher's own, his copies deleted", [b["own"] for b in base()["banners"]] == [True] and not any(Path(f).exists() for f in files))
        old = games._load_store()                                 # a store from before lists: one "banner"
        old["art"]["steam:6"] = {"banner": {"path": str(bg1), "kind": "pic"}}
        games._save_store(old)
        d6 = games.decorate([{"key": "steam:6", "name": "Six", "cover": "", "banner": str(hero)}])[0]
        expect("an old single background carries over as the only one", [(b["own"], b["path"]) for b in d6["banners"]] == [(False, str(bg1))])
        deco = games.decorate([{"key": key, "name": "MyGame", "cover": "", "banner": ""}, {"key": "steam:1", "name": "S", "cover": "", "banner": ""}])
        expect("decorate adds favourite, hidden, effect and the custom cover", deco[0]["favourite"] and deco[0]["fx"] == "glow" and deco[0]["custom_cover"] and deco[0]["cover"].endswith("-cover.png") and deco[1]["hidden"] and not deco[1]["favourite"])
        expect("hidden games are left out of the menus", [g["key"] for g in games.visible(deco)] == [key])
        cleared = games.clear_art(key, "cover")
        expect("clearing the cover removes the copy", cleared["ok"] and not list(games.ART_DIR.glob("*-cover.png")))
        expect("remove a hand-added game; others can't be removed", games.remove_custom(key)["ok"] and not games.remove_custom("steam:1")["ok"] and games.custom_games() == [])
    finally:
        games.STORE, games.ART_DIR = real_store, real_art
try:
    games.fetch_art("ftp://nope")
    expect("fetch_art refuses a non-web link", False)
except ValueError as error:
    expect("fetch_art refuses a non-web link", "web link" in str(error))
expect("search links point at SteamGridDB", "steamgriddb.com/search/heroes?term=Green%20Hell" in games.search_links("Green Hell", "banner") and "/grids?" in games.search_links("x", "cover"))

# ---------- the real launchers on this PC (whatever is there; must not crash) ----------
real = games.all_games()
expect("the real list reads without errors (%d games)" % len(real), isinstance(real, list) and all(g["name"] and g["key"] for g in real))
expect("real games have a time or an icon", not real or any(g["last_played"] for g in real))

# ---------- the jump list, under a test identity so his real one is untouched ----------
TEST_ID = "Shamil.ToolbeltTest"
with tempfile.TemporaryDirectory() as tmp:
    from PIL import Image
    png = Path(tmp) / "game.png"
    Image.new("RGBA", (40, 64), (255, 0, 0, 255)).save(png)
    ico = jumplist.icon_file(png)
    expect("a PNG game icon becomes a square .ico in the cache", ico.endswith(".ico") and Path(ico).exists() and Image.open(ico).size == (64, 64))
    expect("an .ico or .exe is used as it is; nothing for a missing file", jumplist.icon_file(brand.icon_path("cartridge")) == str(brand.icon_path("cartridge")) and jumplist.icon_file(Path(tmp) / "gone.png") == "")
fake = [{"key": "steam:10", "name": "Counter-Strike", "icon": str(brand.icon_path("cartridge"))}, {"key": "x:1", "name": "No icon game", "icon": "pic.jpg"}]
ok, message = jumplist.update(fake, sys.executable, str(Path(__file__).resolve().parent.parent / "main.py"), app_id=TEST_ID)
expect("a jump list is written: " + message, ok and "2 games" in message)
expect("and removed again", jumplist.clear(TEST_ID))

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_games)")
