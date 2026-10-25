"""Tests the page in an invisible Chrome (Playwright), with a stand-in for the Python side. No window appears.

Builds the page exactly like the app does (page.build_page), so the fonts and scripts are the real ones.
Screenshots land in tests\\out (ignored by git).
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolbelt"))
import brand                                                  # noqa: E402
from page import build_page                                   # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# A pretend Python side: same method names and answers as main.py's Api, kept in the browser.
FAKE = """
(() => {
  const settings = {look: 'cartridge', accent: '', animations: true, save_to: 'C:\\\\Users\\\\you\\\\Downloads\\\\Toolbelt',
                    name_pattern: '{title} - {quality}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: true};
  const jobs = [{id: 2, title: 'Test job', kind: 'Self-test', progress: 40, state: 'running', message: 'Counting', result: null},
                {id: 1, title: 'Finished job', kind: 'Self-test', progress: 100, state: 'done', message: '', result: 'x'}];
  window.__calls = [];
  const ok = (v) => Promise.resolve(v);
  window.pywebview = {api: {
    settings: () => ok({...settings}),
    set_setting: (k, v) => {
      window.__calls.push(['set_setting', k, v]);
      if (k === 'name_pattern' && !String(v).includes('{ext}')) return ok({ok: false, message: 'Keep {ext} in it, so files get the right ending.', settings: {...settings}});
      settings[k] = v; return ok({ok: true, message: '', settings: {...settings}});
    },
    choose_folder: () => { settings.save_to = 'D:\\\\Stuff'; return ok({ok: true, message: '', settings: {...settings}}); },
    jobs: () => ok(jobs.map(j => ({...j}))),
    cancel_job: (id) => { window.__calls.push(['cancel_job', id]); const j = jobs.find(x => x.id === id); if (j) j.state = 'cancelled'; return ok({ok: true, message: 'Cancelling…'}); },
    clear_jobs: () => { for (let i = jobs.length - 1; i >= 0; i--) if (!['running', 'waiting'].includes(jobs[i].state)) jobs.splice(i, 1); return ok({ok: true, message: ''}); },
    engines: () => ok({engines: [
      {id: 'yt-dlp', name: 'yt-dlp', what: 'downloads videos', licence: 'Unlicense', approx: '~3 MB', installed: false, size: 0, version: '', step: 2},
      {id: 'ffmpeg', name: 'ffmpeg', what: 'joins, converts, compresses', licence: 'GPL', approx: '~110 MB', installed: true, size: 115343360, version: '9.0.2', step: 2}],
      total: 115343360, folder: 'C:\\\\Users\\\\you\\\\AppData\\\\Local\\\\Toolbelt\\\\engines'}),
    gpus: () => ok(['AMD Radeon RX Example']),
    info: () => ok({version: '0.1 (step 1: the frame)', data: 'C:\\\\…\\\\Toolbelt', logos: __LOGOS__}),
    open_folder: (w) => { window.__calls.push(['open_folder', w]); return ok({ok: true, message: 'Opened'}); },
    games: () => ok([{key: 'steam:1', name: 'Green Hell', source: 'Steam', last_played: new Date(Date.now() - 7200e3).toISOString(), playtime: 7300, icon_data: '', cover_data: '', has_banner: false, favourite: false, hidden: false, fx: 'off', cover_kind: 'pic', banner_kind: 'pic', installed: true, description: 'Survive.'}]),
    game_banner: () => ok({ok: false, kind: 'pic', data: ''}),
    play_game: (k) => { window.__calls.push(['play', k]); return ok({ok: true, message: 'Starting Green Hell'}); },
    refresh_jumplist: () => { window.__calls.push(['jumplist']); return ok({ok: true, message: 'Jump list updated: 1 games'}); },
    mail: () => { const m = window.__mail || []; window.__mail = []; return ok(m); },
    win_state: () => ok({own: true, max: !!window.__max}),
    win_min: () => { window.__calls.push(['win_min']); return ok({ok: true}); },
    win_drag: () => { window.__calls.push(['win_drag']); return ok({ok: true}); },
    win_max: () => { window.__calls.push(['win_max']); window.__max = !window.__max; return ok({own: true, max: window.__max}); },
    win_close: () => { window.__calls.push(['win_close']); return ok({ok: true}); },
    wint_info: () => ok({on: true, windowsOff: true, mode: window.__wintMode || 'hook'}),
    wint_restart_explorer: () => { window.__calls.push(['restart_explorer']); window.__wintMode = 'hotkey'; return ok({ok: true, message: 'Explorer restarted.'}); },
    pc_programs: () => ok([{id: 'machine/Git', name: 'Git', version: '2.55', publisher: 'The Git Development Community', size: 350e6, date: '2026-08-22', uninstall: 'x', quiet: '', location: 'C:/Program Files/Git', icon: '', icon_data: '', where: 'machine', msi: false}]),
    pc_startup: () => ok([{id: 'HKCU/Run/Discord', name: 'Discord', command: 'C:/x/Update.exe', where: 'Registry (you)', enabled: true, canToggle: true, exe: '', icon_data: ''}]),
    open_prototype: () => { window.__calls.push(['open_prototype']); return ok({ok: true, message: 'Opened the prototype in your browser.'}); },
  }};
})();
"""

FAKE = FAKE.replace("__LOGOS__", json.dumps({look: brand.svg(look, 22) for look in brand.LOOKS}))
html = build_page()
expect("the page has no outside links (no internet needed)", "https://fonts" not in html and "<link" not in html)
expect("the fonts are built in", html.count("data:font/woff2;base64,") == 4)
page_file = OUT / "page.html"
page_file.write_text(html, encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for size in [(1320, 860), (920, 620)]:
        pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.add_init_script(FAKE)
        pg.goto(page_file.as_uri())
        try:
            pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
        except Exception:
            print("NOT READY:", errors[:3], pg.evaluate("window.toolbelt && JSON.stringify(window.toolbelt.errors)"))
            raise
        tag = "%dx%d" % size
        walk = pg.evaluate("window.toolbelt.walkScreens()")
        expect(tag + ": all 14 screens open (with Handy tools and App guard)", walk["count"] == 14 and walk["failed"] == [])
        # the own window bar: the top bar is the drag area, its three buttons go to Python, the maximise icon flips
        pg.wait_for_function("document.querySelector('#root').classList.contains('ownbar')", timeout=4000)
        box = pg.locator(".tb .grow").bounding_box()
        pg.mouse.click(box["x"] + 5, box["y"] + box["height"] / 2)
        pg.click("#omni")
        pg.wait_for_timeout(150)
        drags = [c[0] for c in pg.evaluate("window.__calls")].count("win_drag")
        expect(tag + ": own window bar: buttons show; pressing on the bar moves the window, on the paste box it doesn't", pg.is_visible("#winClose") and drags == 1)
        pg.wait_for_timeout(500)
        pg.mouse.click(box["x"] + 5, box["y"] + box["height"] / 2)
        pg.mouse.click(box["x"] + 5, box["y"] + box["height"] / 2)
        pg.wait_for_timeout(200)
        expect(tag + ": double-click on the bar maximises", pg.get_attribute("#winMax", "aria-label") == "Restore")
        pg.click("#winMax")
        pg.wait_for_timeout(200)
        pg.click("#winMax")
        pg.wait_for_function("document.querySelector('#root').classList.contains('winmax')", timeout=3000)
        expect(tag + ": maximise flips to Restore", pg.get_attribute("#winMax", "aria-label") == "Restore")
        pg.click("#winMax")
        pg.wait_for_timeout(200)
        pg.click("#winMin")
        pg.click("#winClose")
        pg.wait_for_timeout(200)
        calls_now = [c[0] for c in pg.evaluate("window.__calls")]
        expect(tag + ": minimise, maximise and close go through Python", all(w in calls_now for w in ("win_min", "win_max", "win_close")))
        # Toolbelt's key (Win+W): the row says how Toolbelt catches it (Windows 11 keeps Win+W for Widgets, so: the key
        # watcher), or that it's a normal shortcut when Windows let go of it; no Restart Explorer promise any more
        if tag == "1320x860":
            pg.evaluate("window.toolbelt.go('settings')")
            pg.click('[data-set="about"]')
            pg.wait_for_function("document.querySelector('#wintInfo') && document.querySelector('#wintInfo').textContent.indexOf('key watcher') !== -1", timeout=4000)
            expect(tag + ": Settings says Toolbelt catches Win+W first (Widgets never opens), no Restart Explorer button", not pg.is_visible("#wintRestart"))
            pg.evaluate("window.__wintMode = 'hotkey'")
            pg.click('[data-set="look"]')
            pg.click('[data-set="about"]')
            pg.wait_for_function("document.querySelector('#wintInfo').textContent.indexOf('normal shortcut') !== -1", timeout=4000)
            expect(tag + ": …or that it's a normal shortcut when Windows let go of it", True)
        for look in ["cartridge", "glass", "glassdark"]:
            pg.evaluate("window.toolbelt.go('settings')")
            pg.click('[data-set="look"]')
            pg.click('[data-look="%s"]' % look)
            pg.wait_for_timeout(250)
            root = pg.get_attribute("#root", "class")
            expect(tag + ": look " + look + " applies", ("glass-dark" in root) if look == "glassdark" else (("look-" + look) in root and "glass-dark" not in root))
            mark = pg.inner_html("#mark")
            expect(tag + ": the logo follows the look " + look, ("crispEdges" in mark) if look == "cartridge" else ("tbg-" + look in mark))
            for screen in ["home", "engines", "settings", "video"]:
                pg.evaluate("window.toolbelt.go('%s')" % screen)
                pg.wait_for_timeout(450)
                over = pg.evaluate("(() => { const m = document.querySelector('main'); return m.scrollWidth > m.clientWidth + 2; })()")
                expect("%s %s %s: nothing sticks out sideways" % (tag, look, screen), not over)
                if size[0] > 1000:
                    pg.screenshot(path=str(OUT / ("%s_%s.png" % (look, screen))))
        # back to Cartridge, then settings: accent, a switch, the name pattern check, the folder picker
        pg.evaluate("window.toolbelt.go('settings')")
        pg.click('[data-set="look"]')
        pg.click('[data-look="cartridge"]')
        pg.wait_for_timeout(150)
        pg.click('[data-acc="#FF5C8A"]')
        pg.wait_for_timeout(150)
        expect(tag + ": accent changes the look right away", pg.evaluate("getComputedStyle(document.getElementById('root')).getPropertyValue('--accent').trim()") == "#FF5C8A")
        pg.click('#setAnim')
        pg.wait_for_timeout(100)
        expect(tag + ": animations off adds no-anim", "no-anim" in pg.get_attribute("#root", "class"))
        pg.click('#setAnim')
        pg.click('[data-set="files"]')
        pg.fill("#pattern", "{title}")
        pg.click("#patSave")
        pg.wait_for_timeout(150)
        expect(tag + ": a bad name pattern is explained", "Keep {ext}" in pg.inner_text("#patErr"))
        pg.click("#pickFolder")
        pg.wait_for_timeout(150)
        expect(tag + ": the folder picker's choice shows", "D:\\Stuff" in pg.inner_text("main"))

        # jobs drawer
        pg.click("#jobsBtn")
        pg.wait_for_timeout(700)
        expect(tag + ": the drawer lists the jobs", pg.locator(".job").count() == 2 and pg.inner_text("#jobsN") == "1")
        pg.click('[data-cancel="2"]')
        pg.wait_for_timeout(700)
        expect(tag + ": cancel reaches Python", ["cancel_job", 2] in pg.evaluate("window.__calls"))
        pg.click("#jobsClear")
        pg.wait_for_timeout(700)
        expect(tag + ": clear finished empties it", pg.locator(".job").count() == 0)
        pg.click("#jobsClose")

        # engines and the graphics card
        pg.evaluate("window.toolbelt.go('engines')")
        pg.wait_for_timeout(200)
        text = pg.inner_text("main")
        expect(tag + ": engines shows installed and missing", "installed" in text and "not installed" in text and "AMD Radeon RX Example" in text)
        pg.click('[data-open="engines"]')
        calls = pg.evaluate("window.__calls")
        expect(tag + ": open folder goes through Python", ["open_folder", "engines"] in calls)
        # the Games screen: the quick list, Play, the taskbar menu button, and "open this screen" notes from Python
        pg.evaluate("window.toolbelt.go('games')")
        pg.wait_for_function("document.querySelector('#gameGrid')", timeout=5000)
        expect(tag + ": Games shows the game tile and its spotlight with source, hours and time", "Green Hell" in pg.inner_text("#gameGrid") and "Steam · 2 h played · 2 h ago" in pg.inner_text("#spot"))
        pg.click('[data-play="steam:1"]')
        pg.click("#gmJump")
        pg.wait_for_timeout(300)
        calls = pg.evaluate("window.__calls")
        expect(tag + ": Play and the taskbar menu go through Python", ["play", "steam:1"] in calls and ["jumplist"] in calls)
        pg.evaluate("window.__mail = [{open: 'video'}]")
        pg.wait_for_function("window.toolbelt.state().screen === 'video'", timeout=4000)
        expect(tag + ": a note from the taskbar menu opens that screen", True)
        expect(tag + ": no script errors", errors == [])
        if errors:
            print("    " + "\n    ".join(errors[:10]))
        pg.close()

    # without the Python side: the page must say so, not hang silently
    pg = browser.new_page(viewport={"width": 1000, "height": 700})
    pg.goto(page_file.as_uri())
    pg.wait_for_timeout(500)
    expect("without Python it says it isn't connected", "not connected" in pg.inner_text("#foot"))
    pg.close()
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page)")
