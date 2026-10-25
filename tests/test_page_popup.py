"""The tray pop-up page, in an invisible Chrome with a pretend Python side: looks, filter, search, Play, Escape."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import brand                                                  # noqa: E402
from page import build_popup                                  # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


FAKE = r"""
(() => {
  const settings = {look: 'cartridge', accent: ''};
  const games = [
    {key: 'playnite:1', name: 'Grand Theft Auto V Legacy', source: 'Steam', last_played: new Date(Date.now() - 3600e3 * 5).toISOString(), playtime: 0, icon_data: ''},
    {key: 'hoyo:hk4e_global', name: 'Genshin Impact', source: 'HoYoPlay', last_played: '', playtime: 0, icon_data: ''},
    {key: 'playnite:2', name: 'Lunar Client', source: 'Playnite', last_played: new Date(Date.now() - 86400e3 * 3).toISOString(), playtime: 0, icon_data: ''}];
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: 'x', logos: __LOGOS__}), games: () => ok(games),
    play_game: (k) => { window.__calls.push(['play', k]); return ok({ok: k !== 'playnite:2', message: k === 'playnite:2' ? "Couldn't start Lunar Client" : 'Starting'}); },
    popup_hide: () => { window.__calls.push(['hide']); return ok({ok: true}); },
    show_main: (s) => { window.__calls.push(['main', s]); return ok({ok: true}); },
  }};
  window.__setLook = (l) => { settings.look = l; };
})();
""".replace("__LOGOS__", json.dumps({look: brand.svg(look, 18) for look in brand.LOOKS}))

page_file = OUT / "popup.html"
page_file.write_text(build_popup(), encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 320, "height": 470})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("document.querySelectorAll('[data-key]').length === 3", timeout=8000)
    expect("three games listed with source and time", "Steam · 5 h ago" in pg.inner_text("#list") and "not played yet" in pg.inner_text("#list") and "3 days ago" in pg.inner_text("#list"))
    expect("the logo is in the header", pg.locator("#mark svg").count() == 1 and "crispEdges" in pg.inner_html("#mark"))
    expect("filter chips: All + each launcher", [c.strip() for c in pg.inner_text("#filt").split("\n") if c.strip()] == ["All", "HoYoPlay", "Playnite", "Steam"])
    pg.screenshot(path=str(OUT / "popup_cartridge.png"))
    pg.click('[data-src="Steam"]')
    expect("a launcher filter narrows the list", pg.locator("[data-key]").count() == 1)
    pg.click('[data-src="All"]')
    pg.fill("#q", "gen")
    expect("search narrows the list", pg.locator("[data-key]").count() == 1 and "Genshin" in pg.inner_text("#list"))
    pg.fill("#q", "")
    pg.click('[data-key="playnite:1"]')
    pg.wait_for_timeout(200)
    calls = pg.evaluate("window.__calls")
    expect("Play asks Python and closes the pop-up", ["play", "playnite:1"] in calls and ["hide"] in calls)
    pg.click('[data-key="playnite:2"]')
    pg.wait_for_timeout(200)
    expect("a failed start shows why, under the name", "Couldn't start" in pg.inner_text('[data-key="playnite:2"]'))
    pg.keyboard.press("Escape")
    pg.click("#lib")
    pg.wait_for_timeout(200)
    calls = pg.evaluate("window.__calls")
    expect("Escape hides, Open library opens the Games screen", calls.count(["hide"]) >= 2 and ["main", "games"] in calls)
    pg.evaluate("window.__setLook('glassdark')")
    pg.evaluate("window.toolbeltPopup.reload()")
    pg.wait_for_timeout(300)
    expect("reload picks up the look and its logo", "glass-dark" in pg.get_attribute("#root", "class") and "tbg-glassdark" in pg.inner_html("#mark"))
    pg.screenshot(path=str(OUT / "popup_glassdark.png"))
    expect("nothing sticks out sideways", pg.evaluate("document.documentElement.scrollWidth") <= 320)
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_popup)")
