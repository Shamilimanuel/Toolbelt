"""The game library screen in an invisible Chrome with a pretend Python side: full-screen art (the banner fills the
screen, the covers sit in a shelf), HD upscaling arriving in the background, search, filters, favourites, hiding,
artwork buttons (file / link / find online / remove), background effects, add and remove."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from page import build_page                                   # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


FAKE = r"""
(() => {
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: '', banner_dwell: 1};
  const PNG ='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  const store = {fav: [], hidden: [], fx: {}, art: {}};
  let custom = [];
  const base = [
    {key: 'steam:271590', name: 'Grand Theft Auto V Legacy', source: 'Steam', last_played: new Date(Date.now() - 3600e3 * 5).toISOString(), playtime: 36000, installed: true, icon_data: PNG, cover: 'c', banner: 'b', description: 'Los Santos. ' + 'x'.repeat(500)},
    {key: 'hoyo:hk4e_global', name: 'Genshin Impact', source: 'HoYoPlay', last_played: '', playtime: 0, installed: true, icon_data: PNG, cover: '', banner: '', description: ''},
    {key: 'playnite:2', name: 'Lunar Client', source: 'Playnite', last_played: new Date(Date.now() - 86400e3 * 3).toISOString(), playtime: 600, installed: true, icon_data: PNG, cover: 'c', banner: '', description: 'Minecraft client.'}];
  function games() {
    return base.concat(custom).map(g => {
      const art = store.art[g.key] || {};
      return Object.assign({}, g, {cover_data: (art.cover || g.cover) ? PNG : '', has_banner: !!(art.banner || g.banner), favourite: store.fav.includes(g.key), hidden: store.hidden.includes(g.key), fx: store.fx[g.key] || 'off',
        cover_kind: art.cover === 'gif' ? 'gif' : 'pic', banner_kind: art.banner === 'video' ? 'video' : 'pic', custom_cover: !!art.cover, custom_banner: !!art.banner,
        cover_video: (g.key === 'playnite:2' && window.__coverVideo) || '',
        hd_banner: !!window.__hd && g.key === 'steam:271590', hd_cover: false, hd_wait: !window.__hd && g.key === 'steam:271590',
        banner_count: window.__multi && g.key === 'steam:271590' ? 3 : 1,
        banner_list: window.__multi && g.key === 'steam:271590' ? [0, 1, 2].map(i => ({kind: i === 2 ? 'video' : 'pic', own: i === 0, thumb: window.__bgs[i], hd: false})) : []});
    });
  }
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.7', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]), engines: () => ok({engines: [], total: 0, folder: ''}),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, message: '', settings}); },
    jobs: () => ok([]), cancel_job: () => ok({ok: true}), clear_jobs: () => ok({ok: true}), check_updates: () => ok({}), clipboard_offer: () => ok(null), mail: () => { const m = window.__mail || []; window.__mail = []; return ok(m); },
    games: (refresh, everything) => { window.__calls.push(['games', !!everything]); return ok(everything ? games() : games().filter(g => !g.hidden)); },
    games_hd_status: () => ok(window.__hd ? {now: {}, waiting: [], waitingNames: []} : {now: {key: 'steam:271590', which: 'banner', kind: 'pic', progress: 45, message: 'Sharpening on the graphics card', seconds: 6, name: 'Grand Theft Auto V Legacy'}, waiting: ['playnite:2'], waitingNames: ['Lunar Client']}),
    game_banner_edit: (k, what, i) => { window.__calls.push(['bgedit', k, what, i]); return ok({ok: true, message: ''}); },
    game_banner: (k, i) => { window.__calls.push(['banner', k]); (window.__bcalls = window.__bcalls || []).push([k, i || 0]);
      if (window.__multi && k === 'steam:271590') return ok({ok: true, kind: 'pic', data: window.__bgs[(i || 0) % 3], hd: false}); const a = store.art[k] || {}; return ok(a.banner === 'video' ? {ok: true, kind: 'video', data: 'data:video/mp4;base64,AAAA'} : k === 'steam:271590' ? {ok: true, kind: 'pic', data: PNG, hd: !!window.__hd} : {ok: false, kind: 'pic', data: ''}); },
    game_set: (k, what, v) => { window.__calls.push(['set', k, what, v]); if (what === 'favourite') store.fav = v ? store.fav.concat([k]) : store.fav.filter(x => x !== k); if (what === 'hidden') store.hidden = v ? store.hidden.concat([k]) : store.hidden.filter(x => x !== k); if (what === 'fx') store.fx[k] = v; return ok({ok: true, message: ''}); },
    game_art_pick: (k, which) => { window.__calls.push(['pick', k, which]); (store.art[k] = store.art[k] || {})[which] = which === 'banner' ? 'video' : 'gif'; return ok({ok: true, message: 'Saved the new ' + which + '.'}); },
    game_art_url: (k, which, url) => { window.__calls.push(['url', k, which, url]); if (!/^https:/.test(url)) return ok({ok: false, message: "That isn't a web link (it should start with https://)."}); (store.art[k] = store.art[k] || {})[which] = 'pic'; return ok({ok: true, message: 'Saved the new ' + which + '.'}); },
    game_art_clear: (k, which) => { window.__calls.push(['clear', k, which]); delete (store.art[k] || {})[which]; return ok({ok: true, message: 'Back to the launcher\'s own ' + which + '.'}); },
    game_art_search: (k, which) => { window.__calls.push(['find', k, which]); return ok({ok: true, message: 'Opened SteamGridDB for GTA.'}); },
    game_add: () => { window.__calls.push(['add']); custom.push({key: 'custom:abc', name: 'MyGame', source: 'Added by hand', last_played: '', playtime: 0, installed: true, icon_data: PNG, cover: '', banner: '', description: ''}); return ok({ok: true, message: 'Added MyGame', key: 'custom:abc'}); },
    game_remove: (k) => { window.__calls.push(['remove', k]); custom = custom.filter(c => c.key !== k); return ok({ok: true, message: 'Removed.'}); },
    game_folder: (k) => { window.__calls.push(['folder', k]); return ok({ok: true, message: 'Opened'}); },
    play_game: (k) => { window.__calls.push(['play', k]); return ok({ok: true, message: 'Starting'}); },
    refresh_jumplist: () => { window.__calls.push(['jumplist']); return ok({ok: true, message: 'Jump list updated: 3 games'}); },
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
  }};
})();
"""

# a real little video for the video cover (his ask, 15 Oct): this Chrome plays WebM
import subprocess                                             # noqa: E402
import engines                                                # noqa: E402
cover_clip = OUT / "games_cover.webm"
if not cover_clip.exists():
    subprocess.run([str(engines.path_of("ffmpeg")), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=200x300:rate=30", "-t", "3",
                    "-c:v", "libvpx-vp9", "-b:v", "150k", str(cover_clip)], check=True, creationflags=0x08000000)

page_file = OUT / "page_games.html"
page_file.write_text(build_page(), encoding="utf-8")


def calls(pg):
    return pg.evaluate("window.__calls")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1320, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.add_init_script("window.__coverVideo = %r;" % cover_clip.as_uri())
    import base64, io                                         # noqa: E401
    from PIL import Image
    pngs = []
    for colour in ((200, 40, 40), (40, 160, 60), (40, 70, 200)):
        buf = io.BytesIO()
        Image.new("RGB", (32, 18), colour).save(buf, "PNG")
        pngs.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
    pg.add_init_script("window.__bgs = %s;" % json.dumps(pngs))
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    pg.evaluate("window.toolbelt.go('games')")
    pg.wait_for_function("document.querySelectorAll('[data-game]').length === 3", timeout=5000)
    expect("three tiles, the newest played picked first", pg.get_attribute('[data-game="steam:271590"]', "aria-pressed") == "true" and "games · 3" in pg.inner_text(".libtop").lower())      # innerText keeps the heading's uppercase styling
    expect("the library asks for every game (hidden ones too)", ["games", True] in calls(pg))
    expect("a game without a cover shows its icon on a plain tile", pg.locator('[data-game="hoyo:hk4e_global"].nocover .gicon').count() == 1)
    pg.wait_for_function("document.querySelector('.libbg .layer.on img')", timeout=5000)
    expect("the chosen game's art fills the screen: sharp on top, a soft copy behind it", pg.locator(".libbg .layer.on img.sharp").count() == 1 and pg.locator(".libbg .layer.on img.soft").count() == 1 and ["banner", "steam:271590"] in calls(pg))
    expect("the covers sit in one shelf along the bottom", pg.evaluate("getComputedStyle(document.querySelector('#gameGrid')).gridAutoFlow") == "column" and pg.locator(".shelf #gameGrid [data-game]").count() == 3)
    expect("a small banner says it's being sharpened", "making HD" in pg.inner_text("#hero"))
    pg.wait_for_function("document.querySelector('#hdTag .t') && document.querySelector('#hdTag .t').textContent.indexOf('45%') !== -1", timeout=4000)
    expect("…with how far it is: a bar by the title, and a line in the top bar with what's waiting", pg.evaluate("document.querySelector('#hdTag .hdbar i').style.width") == "45%"
           and "HD: Grand Theft Auto V Legacy background 45% · 1 more waiting" in pg.inner_text("#hdLine"))
    expect("the spotlight: name, source, hours, time, description", "Grand Theft Auto V Legacy" in pg.inner_text(".logo-t") and "Steam · 10 h played · 5 h ago" in pg.inner_text("#spot") and "Los Santos" in pg.inner_text(".gdesc") and pg.inner_text(".gdesc").endswith("…"))
    pg.screenshot(path=str(OUT / "games_library.png"))

    # Python finished the HD copy: the page swaps it in by itself
    n = sum(1 for c in calls(pg) if c == ["banner", "steam:271590"])
    pg.evaluate("window.__hd = true; window.__mail = [{games_hd: 'steam:271590', which: 'banner'}]")
    pg.wait_for_function("document.querySelector('#hero .tag.hd')", timeout=5000)
    expect("when the HD copy is ready it's swapped in (HD tag, background fetched again)", sum(1 for c in calls(pg) if c == ["banner", "steam:271590"]) == n + 1 and "making HD" not in pg.inner_text("#hero"))
    expect("…and the background stays up while it swaps (no blank flash)", pg.locator(".libbg .layer.on img.sharp").count() >= 1)
    pg.focus('[data-game="steam:271590"]')
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(200)
    expect("← → walk the shelf like a console", pg.get_attribute('[data-game="steam:271590"]', "aria-pressed") == "false" and pg.locator('[data-game][aria-pressed="true"]').count() == 1)
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(200)

    # pick another, with no banner: background clears, spotlight changes
    pg.click('[data-game="playnite:2"]')
    pg.wait_for_timeout(300)
    expect("picking a game changes the spotlight; no banner = plain hero", "Lunar Client" in pg.inner_text(".logo-t") and pg.locator("#hero.nocover").count() == 1)
    tile_video = "document.querySelector('[data-game=\"playnite:2\"] video.gtv')"
    expect("a video cover sits in its shelf tile, and plays now that it's picked", pg.evaluate("!!" + tile_video) and pg.evaluate(tile_video + ".paused") is False)
    expect("…and plays by the title too", pg.locator("#hero .mini video").count() == 1)
    pg.click('[data-game="steam:271590"]')
    pg.wait_for_timeout(200)
    expect("in the shelf only the picked one moves (it stops when another game is picked)", pg.evaluate(tile_video + ".paused") is True)
    # Settings > Appearance > Moving game covers (his ask): Always move, then Still
    for mode in ("always", "still"):
        pg.evaluate("window.toolbelt.go('settings')")
        pg.click('[data-set="look"]')
        pg.click('[data-cmot="%s"]' % mode)
        pg.wait_for_timeout(250)
        pg.evaluate("window.toolbelt.go('games')")
        pg.wait_for_selector('[data-game="playnite:2"] video.gtv', timeout=4000)
        pg.mouse.move(5, 5)
        if mode == "always":
            pg.wait_for_timeout(500)
            expect("'Always move': the video cover plays even when it isn't picked", pg.evaluate(tile_video + ".paused") is False)
        else:
            pg.click('[data-game="playnite:2"]')
            pg.mouse.move(5, 5)
            pg.wait_for_timeout(400)
            expect("'Still': the cover stays still, also when picked and by the title", pg.evaluate(tile_video + ".paused") is True
                   and pg.evaluate("document.querySelector('#hero .mini video').paused") is True)
    pg.evaluate("window.toolbelt.go('settings')")
    pg.click('[data-set="look"]')
    pg.click('[data-cmot="hover"]')
    pg.wait_for_timeout(250)
    pg.evaluate("window.toolbelt.go('games')")
    pg.wait_for_selector('[data-game="playnite:2"]', timeout=4000)
    pg.click('[data-game="playnite:2"]')
    pg.wait_for_timeout(200)
    pg.dblclick('[data-game="playnite:2"]')
    pg.wait_for_timeout(200)
    expect("double-click plays", ["play", "playnite:2"] in calls(pg))
    pg.click("[data-play]")
    pg.click("#gmFolder")
    pg.wait_for_timeout(200)
    expect("Play and Folder go through Python", calls(pg).count(["play", "playnite:2"]) == 2 and ["folder", "playnite:2"] in calls(pg))

    # search, sort, filters
    pg.fill("#gmQ", "gen")
    expect("search narrows the tiles", pg.locator("[data-game]").count() == 1 and "Genshin" in pg.inner_text("#gameGrid"))
    pg.fill("#gmQ", "")
    pg.click('[data-gsort="name"]')
    pg.wait_for_timeout(200)
    expect("A–Z sorts the tiles", pg.locator("[data-game]").first.get_attribute("data-game") == "hoyo:hk4e_global")
    pg.click('[data-game="hoyo:hk4e_global"]')
    pg.click("#gmFav")
    pg.wait_for_function("document.querySelector('[data-game=\"hoyo:hk4e_global\"] .star')", timeout=5000)
    expect("★ Favourite marks the tile", ["set", "hoyo:hk4e_global", "favourite", True] in calls(pg))
    pg.click('[data-gfilter="fav"]')
    pg.wait_for_timeout(200)
    expect("the Favourites filter shows only it", pg.locator("[data-game]").count() == 1)
    pg.click('[data-gfilter="all"]')
    pg.wait_for_timeout(200)
    pg.click('[data-game="playnite:2"]')
    pg.click("#gmHide")
    pg.wait_for_function("document.querySelectorAll('[data-game]').length === 2", timeout=5000)
    expect("Hide takes it out of the list", ["set", "playnite:2", "hidden", True] in calls(pg))
    pg.click('[data-gfilter="hidden"]')
    pg.wait_for_timeout(200)
    expect("the Hidden filter shows it, with Show again", pg.locator("[data-game]").count() == 1 and "Show again" in pg.inner_text("#spot"))
    pg.click("#gmHide")
    pg.wait_for_timeout(300)
    pg.click('[data-gfilter="all"]')
    pg.wait_for_function("document.querySelectorAll('[data-game]').length === 3", timeout=5000)

    # artwork: file, link (bad and good), find online, remove; effects
    pg.click('[data-game="steam:271590"]')
    pg.wait_for_timeout(200)
    expect("the artwork editor is hidden until asked for", pg.locator(".artcard").count() == 0 and pg.locator("#gmEdit").count() == 1)
    expect("picking a game plays the reveal (details slide in)", pg.locator("#hero.reveal").count() == 1 and pg.locator(".spotinfo.reveal").count() == 1)
    pg.click("#gmEdit")
    pg.wait_for_selector(".artcard", timeout=3000)
    expect("Edit artwork opens the editor; the button says Done editing", "Done editing" in pg.inner_text("#gmEdit"))
    pg.click('[data-art="pick:banner"]')
    pg.wait_for_function("document.querySelector('.libbg .layer.on video')", timeout=5000)
    expect("a banner file (video) shows as a looping video, tagged", ["pick", "steam:271590", "banner"] in calls(pg) and "video loop" in pg.inner_text("#hero") and "yours" in pg.inner_text(".artgrid"))
    pg.click('[data-art="link:cover"]')
    pg.fill("#artUrl", "ftp://nope")
    pg.click("#artUrlGo")
    pg.wait_for_timeout(300)
    expect("a bad link is explained", "web link" in pg.inner_text("#toast"))
    pg.click('[data-game="steam:271590"]')
    pg.wait_for_timeout(150)
    expect("picking a game again closes the editor", pg.locator(".artcard").count() == 0)
    pg.click("#gmEdit")
    pg.click('[data-art="link:cover"]')
    pg.fill("#artUrl", "https://example.com/cover.png")
    pg.press("#artUrl", "Enter")
    pg.wait_for_timeout(400)
    expect("a pasted link is fetched for the cover", any(c[0] == "url" and c[2] == "cover" and c[3] == "https://example.com/cover.png" for c in calls(pg)))
    pg.click('[data-art="find:banner"]')
    pg.wait_for_timeout(200)
    expect("Find online opens SteamGridDB through Python", ["find", "steam:271590", "banner"] in calls(pg))
    pg.click('[data-art="clear:banner"]')
    pg.wait_for_timeout(400)
    expect("🗑 goes back to the launcher's own banner", ["clear", "steam:271590", "banner"] in calls(pg))
    pg.click('[data-fx="shine"]')
    pg.wait_for_function("document.querySelector('.libbg.fx-shine')", timeout=5000)
    expect("a banner effect is saved and applied", ["set", "steam:271590", "fx", "shine"] in calls(pg))
    pg.screenshot(path=str(OUT / "games_art.png"))

    # several backgrounds per game (his ask): they take turns, each fading in OVER the one that is up (no dip, no flash)
    pg.evaluate("""(function(){
      window.__swaps = [];
      var watch = new MutationObserver(function (list) { list.forEach(function (m) {
        var el = m.target; if (!el.classList.contains('layer') || !el.classList.contains('on') || (m.oldValue || '').indexOf('on') !== -1) return;
        var other = document.querySelector(el.id === 'bgA' ? '#bgB' : '#bgA');
        var img = el.querySelector('img.sharp'); window.__swaps.push({overOld: !!(other && other.classList.contains('on') && other.innerHTML), onTop: el.style.zIndex === '2', shown: img ? window.__bgs.indexOf(img.getAttribute('src')) : -9});
      }); });
      watch.observe(document.querySelector('#screen'), {attributes: true, attributeFilter: ['class'], attributeOldValue: true, subtree: true});
      window.__multi = true; window.__bcalls = [];
    })()""")
    pg.click("#gmRefresh")
    pg.wait_for_selector('[data-game="steam:271590"]', timeout=4000)
    pg.click('[data-game="steam:271590"]')
    pg.wait_for_function("(window.__swaps || []).map(function (s) { return s.shown; }).join(',').indexOf('0,1,2,0') !== -1", timeout=15000)
    expect("the backgrounds take turns: 1, 2, 3, then 1 again (one second each in this test)", True)
    swaps = pg.evaluate("window.__swaps")
    expect("each one fades in on top while the one before is still fully up (%d swaps)" % len(swaps), len(swaps) >= 3 and all(s["overOld"] and s["onTop"] for s in swaps[1:]))
    pg.click("#gmEdit")
    pg.wait_for_selector(".bgthumb", timeout=3000)
    expect("the editor shows the game's backgrounds in order, with the launcher's own marked", pg.locator(".bgthumb").count() == 3 and "Steam's" in pg.inner_text(".bglist"))
    pg.evaluate("window.__bcalls = []")
    pg.evaluate("window.__swaps = []")
    pg.click('[data-bgshow="2"]')
    pg.wait_for_timeout(400)
    first_shown = pg.evaluate("(window.__swaps[0] || {}).shown")
    expect("clicking one shows it now (shown: %s)" % first_shown, first_shown == 2 and pg.locator(".bgthumb.on").count() == 1)
    pg.click('[data-bgedit="left:2"]')
    pg.wait_for_timeout(300)
    pg.click("#gmEdit") if pg.locator("#gmEdit").inner_text().startswith("✎") else None
    pg.wait_for_selector('[data-bgedit="remove:1"]', timeout=3000)
    pg.click('[data-bgedit="remove:1"]')
    pg.wait_for_timeout(300)
    expect("◀ ▶ ✕ go through Python", ["bgedit", "steam:271590", "left", 2] in calls(pg) and ["bgedit", "steam:271590", "remove", 1] in calls(pg))
    pg.screenshot(path=str(OUT / "games_backgrounds.png"))
    pg.evaluate("window.__multi = false")
    pg.click("#gmRefresh")
    pg.wait_for_selector('[data-game="steam:271590"]', timeout=4000)

    # add by exe, then remove
    pg.click("#gmAdd")
    pg.wait_for_function("document.querySelectorAll('[data-game]').length === 4", timeout=5000)
    pg.click('[data-game="custom:abc"]')
    pg.wait_for_selector("#gmRemove", timeout=3000)
    pg.click("#gmRemove")
    pg.wait_for_function("document.querySelectorAll('[data-game]').length === 3", timeout=5000)
    expect("+ Add game and Remove go through Python", ["add"] in calls(pg) and ["remove", "custom:abc"] in calls(pg))
    pg.click("#gmJump")
    pg.wait_for_timeout(200)
    expect("Update the taskbar menu", ["jumplist"] in calls(pg))
    expect("nothing sticks out sideways", pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"))
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_games)")
