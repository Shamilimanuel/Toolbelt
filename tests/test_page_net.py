"""The internet switch's button (17 Oct) in an invisible Chrome with a pretend Python side: set up from Settings,
off, on, and "No connection"."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


from page import build_page                                   # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

FAKE = r"""
(() => {
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: ''};
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.__net = {installed: false, state: 'on'}; window.__calls = [];
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '1', data: 'x', logos: {}}), gpus: () => ok([]), jobs: () => ok([]), clipboard_offer: () => ok(null), mail: () => ok([]),
    engines: () => ok({engines: [], total: 0, folder: 'x'}), check_updates: () => ok({}), set_setting: (k, v) => ok({ok: true, settings}),
    net_state: () => ok(window.__net),
    net_setup: () => { window.__calls.push('setup'); window.__net.installed = true; return ok({ok: true, message: 'ready'}); },
    net_set: (on) => { window.__calls.push(on ? 'on' : 'off'); window.__net.state = on ? 'on' : 'off'; return ok({ok: true, state: window.__net.state, message: on ? 'Internet back on' : 'Internet off'}); },
    net_remove: () => ok({ok: true, message: 'removed'}), wint_info: () => ok({}), win_state: () => ok({own: false}),
  }};
})();
"""
out = Path(__file__).resolve().parent / "out"
out.mkdir(exist_ok=True)
page_file = out / "page_net.html"
page_file.write_text(build_page(), encoding="utf-8")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1320, "height": 860})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    pg.wait_for_timeout(300)
    expect("the top bar shows 🌐 Online", pg.inner_text("#netTxt").strip() == "Online")
    pg.hover("#netBtn")
    pg.wait_for_timeout(600)
    expect("hovering says what a click does (set up first)", pg.is_visible("#netTip") and pg.evaluate("getComputedStyle(document.querySelector('#netTip')).opacity") == "1" and "set up" in pg.inner_text("#netTip"))
    pg.screenshot(path=str(out / "net_hover.png"), clip={"x": 820, "y": 0, "width": 500, "height": 180})
    pg.click("#netBtn")
    pg.wait_for_selector("#netSetup", timeout=3000)
    expect("before the setup, the button leads to Settings > About with a Set up button", pg.evaluate("window.toolbelt.state().screen") == "settings")
    pg.click("#netSetup")
    pg.wait_for_selector("#netRemove", timeout=3000)
    expect("Set up reaches Python and the row then offers Remove", pg.evaluate("window.__calls") == ["setup"])
    pg.click("#netBtn")
    pg.wait_for_function("document.querySelector('#netBtn').getAttribute('data-state') === 'off'", timeout=3000)
    expect("a press switches it off: red Offline", pg.inner_text("#netTxt") == "Offline")
    expect("…and the hover now says a click turns it back on", "turn it back on" in pg.evaluate("document.querySelector('#netTipText').textContent"))
    pg.screenshot(path=str(out / "net_off.png"), clip={"x": 700, "y": 0, "width": 620, "height": 60})
    pg.click("#netBtn")
    pg.wait_for_function("document.querySelector('#netBtn').getAttribute('data-state') === 'on'", timeout=3000)
    expect("a second press switches it back on (works offline: it's all on this PC)", pg.evaluate("window.__calls") == ["setup", "off", "on"])
    pg.evaluate("window.__net.state = 'nocable'")
    pg.wait_for_function("document.querySelector('#netBtn').getAttribute('data-state') === 'nocable'", timeout=5000)
    expect("unplugged / router off shows No connection", pg.inner_text("#netTxt") == "No connection")
    expect("no errors in the page", not errors)
    browser.close()

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
