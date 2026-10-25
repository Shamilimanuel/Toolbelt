"""Tests the Home screen in an invisible Chrome, with a pretend Python side. No window appears, nothing starts.

Walks: the apps grid with progress and Next up, Open / Settings / Folder / VS Code, Toolbelt's own Settings button,
the right-click menu (change how it opens, hide, notes), filters, adding apps from the Start menu, a website, removing.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolbelt"))
from page import build_page                                   # noqa: E402
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false,
    open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true};
  const ICON = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" rx="6" fill="#E8893A"/></svg>');
  let projects = [
    {id: 'Widgets\\Waypoint', name: 'Waypoint', what: 'Genshin-style file manager', folder: 'C:\\VSC\\Widgets\\Waypoint', status: 'status.md', progress: 94, next: 'Desktop step 2: everything else on real files', icon: ICON, can_open: true, has_settings: true, hidden: false, self: false},
    {id: 'Widgets\\Leyline', name: 'Leyline', what: 'Genshin-style Task Manager', folder: 'C:\\VSC\\Widgets\\Leyline', status: 'status.md', progress: 74, next: 'Character screen', icon: '', can_open: true, has_settings: false, note: "Leyline's settings are its own Settings page: open Leyline.", hidden: false, self: false},
    {id: 'Courier', name: 'Courier', what: 'file courier', folder: 'C:\\VSC\\Courier', status: '', progress: null, next: '', icon: ICON, can_open: false, has_settings: true, hidden: false, self: false},
    {id: 'Toolbelt', name: 'Toolbelt', what: 'this app', folder: 'C:\\VSC\\Toolbelt', status: 'status.md', progress: 59, next: '4 Home', icon: ICON, can_open: true, has_settings: true, hidden: false, self: true},
  ];
  let added = [];
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  const call = (name) => (...a) => { window.__calls.push([name, ...a]); return ok({ok: true, message: name + ' done'}); };
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.4', data: 'x', prototype: 'p'}), gpus: () => ok([]),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, settings}); },
    engines: () => ok({engines: [], total: 0, folder: 'x'}), jobs: () => ok([]), clipboard_offer: () => ok(null),
    home: () => ok({projects, added, vscode: true, root: 'C:\\VSC'}),
    home_open: (id) => { window.__calls.push(['home_open', id]); return ok(id === 'Toolbelt' ? {ok: true, message: "You're already in it."} : {ok: true, message: 'Opening ' + id}); },
    home_settings: (id) => { window.__calls.push(['home_settings', id]); return ok(id === 'Toolbelt' ? {ok: true, message: '', go: 'settings'} : {ok: true, message: 'settings'}); },
    home_folder: call('home_folder'), home_code: call('home_code'), home_notes: call('home_notes'), home_reset: call('home_reset'),
    home_change: (id, which) => { window.__calls.push(['home_change', id, which]); return ok({ok: true, message: 'Opens with Waypoint.lnk'}); },
    home_hide: (id, h) => { window.__calls.push(['home_hide', id, h]); projects.forEach(p => { if (p.id === id) p.hidden = h; }); return ok({ok: true, message: h ? 'Hidden from Home' : 'Back on Home'}); },
    start_menu: () => ok([{name: 'Discord', path: 'C:\\SM\\Discord.lnk', group: 'Discord Inc', icon: ICON}, {name: 'OBS Studio', path: 'C:\\SM\\OBS Studio.lnk', group: '', icon: ICON}, {name: 'Steam', path: 'C:\\SM\\Steam.lnk', group: 'Steam', icon: ''}]),
    home_add_many: (paths) => { window.__calls.push(['add_many', paths]); paths.forEach((p, i) => added.push({id: 'a' + (added.length + 1), kind: 'lnk', target: p, name: p.split('\\').pop().replace('.lnk', ''), group: '', icon: ICON, missing: false})); return ok({ok: true, message: 'Added ' + paths.length + ' apps'}); },
    home_add: (kind, target) => { window.__calls.push(['add', kind, target]); if (!/^https?:\/\//.test(target)) return ok({ok: false, message: 'A website starts with https://'}); added.push({id: 'a' + (added.length + 1), kind, target, name: 'hoyolab.com', group: '', icon: '', missing: false}); return ok({ok: true, message: 'Added hoyolab.com'}); },
    home_add_exe: () => ok({ok: false, message: ''}),
    home_remove: (id) => { window.__calls.push(['remove', id]); added = added.filter(a => a.id !== id); return ok({ok: true, message: 'Removed from Home'}); },
  }};
})();
"""

page_file = OUT / "page.html"
page_file.write_text(build_page(), encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1320, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    pg.evaluate("window.toolbelt.go('home')")
    pg.wait_for_selector(".appc", timeout=5000)

    expect("all four projects show", pg.locator(".appc").count() == 4)
    text = pg.inner_text("main")
    expect("progress and Next up are shown", "94%" in text and "Desktop step 2" in text and "no bar" in text)
    expect("real icons where there are, a letter where not", pg.locator(".appc img.appicon").count() == 3 and pg.locator(".appc .badge").count() == 1)
    expect("Leyline's Settings is disabled (its settings are inside the app)", pg.is_disabled('[data-app="Widgets\\\\Leyline"] [data-a="settings"]'))
    pg.screenshot(path=str(OUT / "home.png"))

    way = '[data-app="Widgets\\\\Waypoint"]'
    for action in ["open", "settings", "folder", "code"]:
        pg.click(way + ' [data-a="%s"]' % action)
    pg.wait_for_timeout(300)
    calls = pg.evaluate("window.__calls")
    expect("Open / Settings / Folder / VS Code reach Python", all(["home_" + a, "Widgets\\Waypoint"] in calls for a in ["open", "settings", "folder", "code"]))
    pg.click('[data-app="Toolbelt"] [data-a="settings"]')
    pg.wait_for_timeout(300)
    expect("Toolbelt's own Settings button opens its Settings screen", pg.evaluate("window.toolbelt.state().screen") == "settings")
    pg.evaluate("window.toolbelt.go('home')")
    pg.wait_for_selector(".appc")

    # right-click menu
    pg.click(way, button="right")
    expect("right-click shows the app menu", pg.locator("#appMenu").count() == 1 and "Change how it opens" in pg.inner_text("#appMenu"))
    pg.click('#appMenu [data-m="change-open"]')
    pg.wait_for_timeout(300)
    expect("Change how it opens goes to Python", ["home_change", "Widgets\\Waypoint", "open"] in pg.evaluate("window.__calls"))
    pg.click('[data-app="Courier"]', button="right")
    pg.click('#appMenu [data-m="hide"]')
    pg.wait_for_timeout(500)
    expect("hiding removes it and offers to show it again", pg.locator(".appc").count() == 3 and pg.locator("#homeUnhide").count() == 1)
    pg.click("#homeUnhide")
    pg.wait_for_timeout(500)
    expect("…and it comes back", pg.locator(".appc").count() == 4)

    # edit mode (25 Oct): wiggle + ✕ on every card, marks are only applied on Done
    calls_before = len(pg.evaluate("window.__calls"))
    pg.click("#homeEdit")
    expect("Edit: every card wiggles with a ✕, the buttons rest", pg.locator(".appc.wig").count() == 4 and pg.locator(".appc .ex").count() == 4 and pg.locator("#homeDone").count() == 1 and pg.locator("#homeAdd").count() == 0)
    pg.click('[data-app="Courier"] .ex')
    expect("clicking ✕ marks it (dimmed, ↶ to undo), Done counts it", pg.locator(".appc.gone").count() == 1 and "Hidden" in pg.inner_text('[data-app="Courier"] .gonetag') and "1 change" in pg.inner_text("#homeDone"))
    pg.screenshot(path=str(OUT / "home_edit.png"))
    pg.click('[data-app="Courier"]')
    expect("clicking it again keeps it", pg.locator(".appc.gone").count() == 0 and pg.inner_text("#homeDone").strip() == "Done")
    pg.click('[data-app="Courier"] .ex')
    pg.click("#homeCancel")
    expect("Cancel forgets the marks: nothing reached Python", pg.locator(".appc.wig").count() == 0 and pg.locator(".appc").count() == 4 and len(pg.evaluate("window.__calls")) == calls_before)
    pg.click("#homeEdit")
    pg.click('[data-app="Courier"] .ex')
    pg.click("#homeDone")
    pg.wait_for_timeout(500)
    expect("Done hides it for real", ["home_hide", "Courier", True] in pg.evaluate("window.__calls") and pg.locator(".appc").count() == 3 and pg.locator("#homeUnhide").count() == 1)
    pg.click("#homeEdit")
    expect("in Edit, hidden apps show up dimmed, ready to come back", pg.locator(".appc").count() == 4 and pg.locator('[data-app="Courier"].gone').count() == 1)
    pg.click('[data-app="Courier"] .ex')
    pg.click("#homeDone")
    pg.wait_for_timeout(500)
    expect("…and Done brings it back", ["home_hide", "Courier", False] in pg.evaluate("window.__calls") and pg.locator(".appc").count() == 4 and pg.locator(".appc.wig").count() == 0)

    # adding apps
    pg.click("#homeAdd")
    pg.wait_for_selector(".additem", timeout=4000)
    expect("the Start menu list shows", pg.locator(".additem").count() == 3)
    pg.fill("#addQ", "dis")
    expect("search filters it", pg.locator(".additem").count() == 1)
    pg.click(".additem")
    pg.fill("#addQ", "")
    pg.locator(".additem", has_text="OBS").click()
    expect("two picked", "2 picked" in pg.inner_text("#addN"))
    pg.click("#addGo")
    pg.wait_for_timeout(500)
    expect("picked apps are added to Home", pg.locator(".appc").count() == 6 and "Discord" in pg.inner_text("main"))
    pg.click("#homeAdd")
    pg.fill("#addUrl", "hoyolab")
    pg.click("#addUrlGo")
    pg.wait_for_timeout(300)
    expect("a website without https:// is explained", "https://" in pg.inner_text("#toast"))
    pg.fill("#addUrl", "https://www.hoyolab.com/home")
    pg.click("#addUrlGo")
    pg.wait_for_timeout(500)
    expect("a website is added", "hoyolab.com" in pg.inner_text("main"))
    pg.click('[data-f="added"]')
    expect("the Added filter shows only added apps", pg.locator(".appc").count() == 3)
    pg.click('[data-f="mine"]')
    expect("the Mine filter shows only his projects", pg.locator(".appc").count() == 4)
    pg.click('[data-f="all"]')
    pg.locator(".appc", has_text="Discord").locator('[data-a="remove"]').click()
    pg.wait_for_timeout(500)
    expect("Remove takes it off Home", "Discord" not in pg.inner_text("main"))
    pg.screenshot(path=str(OUT / "home_added.png"), full_page=True)

    for look in ["glass", "glassdark"]:
        pg.evaluate("window.toolbelt.go('settings')")
        pg.click('[data-look="%s"]' % look)
        pg.wait_for_timeout(200)
        pg.evaluate("window.toolbelt.go('home')")
        pg.wait_for_timeout(400)
        over = pg.evaluate("(() => { const m = document.querySelector('main'); return m.scrollWidth > m.clientWidth + 2; })()")
        expect(look + ": nothing sticks out sideways", not over)
        pg.screenshot(path=str(OUT / ("home_%s.png" % look)))
    expect("no script errors", errors == [])
    if errors:
        print("    " + "\n    ".join(errors[:10]))
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_home)")
