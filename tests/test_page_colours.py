"""Tests the Colours screen in an invisible Chrome, with a pretend Python side. No window appears.

The gradient codes are checked against the exact output the approved prototype gave on 13 Oct (for "Hi there",
#ff5f6d → #ffc371, bold), so the move into the real app can't have changed a single character.
"""
import json
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
  let saved = [{n: 'Ocean', s: ['#2AF5FF', '#3D7BFF', '#7B3DFF']}];
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.5', data: 'x', prototype: 'p'}), gpus: () => ok([]),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, settings}); },
    engines: () => ok({engines: [], total: 0, folder: 'x'}), jobs: () => ok([]), clipboard_offer: () => ok(null), home: () => ok({projects: [], added: [], vscode: false}),
    colours: () => ok({saved, last: null}),
    colours_save: (n, s) => { window.__calls.push(['save', n, s]); saved = [{n, s}].concat(saved); return ok({ok: true, saved}); },
    colours_delete: (i) => { window.__calls.push(['delete', i]); saved.splice(i, 1); return ok({ok: true, saved}); },
    colours_remember: (g) => { window.__calls.push(['remember', g.text]); return ok({ok: true}); },
    colours_from_picture: () => ok({ok: true, colours: ['#1E5AC8', '#F0C828', '#DC2828'], name: 'flag'}),
    copy_text: (t) => { window.__calls.push(['copy', t]); return ok({ok: true, message: 'Copied'}); },
  }};
})();
"""

# what the prototype produced (13 Oct) for "Hi there", #ff5f6d → #ffc371, bold on
EXPECTED = {
    "amp": "&#ff5f6d&lH&#ff6d6e&li &#ff8a6f&lt&#ff986f&lh&#ffa670&le&#ffb570&lr&#ffc371&le",
    "mm": "<b><gradient:#ff5f6d:#ffc371>Hi there</gradient></b>",
    "sk": "<##ff5f6d>&lH<##ff6d6e>&li <##ff8a6f>&lt<##ff986f>&lh<##ffa670>&le<##ffb570>&lr<##ffc371>&le",
    "x": "&x&f&f&5&f&6&d&lH&x&f&f&6&d&6&e&li &x&f&f&8&a&6&f&lt&x&f&f&9&8&6&f&lh&x&f&f&a&6&7&0&le&x&f&f&b&5&7&0&lr&x&f&f&c&3&7&1&le",
}

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

    for fmt, want in EXPECTED.items():
        got = pg.evaluate("window.toolbelt.gradientCode({text: 'Hi there', stops: ['#ff5f6d', '#ffc371'], fmt: '%s', b: true, i: false, u: false, s: false, k: false, sh: false, shc: '#000000', sha: 60}).out" % fmt)
        expect("%s: same code as the approved prototype" % fmt, got == want)
    js = pg.evaluate("window.toolbelt.gradientCode({text: 'Ab', stops: ['#ff0000', '#0000ff'], fmt: 'json', b: false, i: true, u: false, s: false, k: false, sh: true, shc: '#3A0A2A', sha: 60}).out")
    parsed = json.loads(js)
    expect("tellraw JSON: valid, italic, with a shadow_color number", parsed[0] == "" and parsed[1]["italic"] is True and isinstance(parsed[1]["shadow_color"], int))
    mm = pg.evaluate("window.toolbelt.gradientCode({text: 'x', stops: ['#ff0000', '#0000ff', '#00ff00'], fmt: 'mm', b: false, i: false, u: true, s: true, k: true, sh: true, shc: '#3A0A2A', sha: 50}).out")
    expect("MiniMessage: styles and shadow open and close in order", mm == "<u><st><obf><shadow:#3A0A2A:0.50><gradient:#ff0000:#0000ff:#00ff00>x</gradient></shadow></obf></st></u>")

    pg.evaluate("window.toolbelt.go('color')")
    pg.wait_for_selector("#grOut")
    pg.fill("#grText", "Hi there")
    pg.wait_for_timeout(100)
    expect("the screen shows the Skript code by default (for PrimalMines)", pg.input_value("#grOut") == EXPECTED["sk"].replace("ff5f6d", "ff5f6d"))
    pg.click('[data-preset="4"]')                                  # Rainbow: 6 colours
    expect("a 6-colour preset fills the colours and disables + Add", pg.locator(".stop").count() == 6 and pg.is_disabled("#grAdd"))
    pg.click('[data-st="k"]')
    pg.wait_for_timeout(200)
    a = pg.inner_text("#grPrev")
    pg.wait_for_timeout(200)
    expect("obfuscated letters scramble in the preview", a != pg.inner_text("#grPrev"))
    pg.click('[data-fmt="json"]')
    expect("JSON shows a note about tellraw", "tellraw" in pg.inner_text("#fmtNote"))
    pg.click("#shOn")
    expect("shadow note mentions 1.21.4", "1.21.4" in pg.inner_text("#fmtNote"))
    pg.click("#grCopy")
    pg.click("#grSave")
    pg.wait_for_timeout(1500)
    calls = pg.evaluate("window.__calls")
    expect("Copy code goes through Python's clipboard", any(c[0] == "copy" and c[1].startswith('["",') for c in calls))
    expect("Save keeps the gradient", any(c[0] == "save" and len(c[2]) == 6 for c in calls))
    expect("the gradient being worked on is remembered", any(c[0] == "remember" for c in calls))
    pg.screenshot(path=str(OUT / "colours_gradient.png"))

    pg.click('[data-ctab="saved"]')
    expect("Saved lists both", pg.locator("[data-use]").count() == 2)
    pg.click('[data-use="1"]')
    pg.wait_for_timeout(200)
    expect("Use loads it into the gradient maker", pg.locator(".stop").count() == 3 and pg.locator("#grOut").count() == 1)
    pg.click('[data-ctab="saved"]')
    pg.click('[data-unsave="0"]')
    pg.wait_for_timeout(200)
    expect("Delete removes it", pg.locator("[data-use]").count() == 1)

    pg.click('[data-ctab="codes"]')
    pg.fill("#hxIn", "#FF8800")
    pg.wait_for_timeout(100)
    rows = pg.inner_text("#hxRows")
    expect("one colour in every format", "rgb(255, 136, 0)" in rows and "hsl(32, 100%, 50%)" in rows and "16746496" in rows and "<##ff8800>" in rows)
    pg.locator(".codeitem", has_text="Discord").click()
    pg.wait_for_timeout(200)
    expect("clicking a format copies it", ["copy", "16746496"] in pg.evaluate("window.__calls"))
    pg.eval_on_selector("#cA", "el => { el.value = '#777777'; el.dispatchEvent(new Event('input')); }")
    pg.eval_on_selector("#cB", "el => { el.value = '#888888'; el.dispatchEvent(new Event('input')); }")
    expect("grey on grey is called hard to read", "Hard to read" in pg.inner_text("#cVerdict"))

    pg.click('[data-ctab="pal"]')
    pg.click('[data-harm="2"]')
    expect("triadic gives three colours", pg.locator(".pcol").count() == 3)
    pg.click("#palPic")
    pg.wait_for_timeout(300)
    expect("from a picture shows its colours", [t.strip() for t in pg.locator(".pcol").all_inner_texts()] == ["#1E5AC8", "#F0C828", "#DC2828"])
    pg.click("#palGrad")
    pg.wait_for_timeout(200)
    expect("Use as gradient carries the palette over", pg.locator(".stop").count() == 3)

    for look in ["glass", "glassdark"]:
        pg.evaluate("window.toolbelt.go('settings')")
        pg.click('[data-look="%s"]' % look)
        pg.wait_for_timeout(200)
        pg.evaluate("window.toolbelt.go('color')")
        pg.wait_for_timeout(300)
        over = pg.evaluate("(() => { const m = document.querySelector('main'); return m.scrollWidth > m.clientWidth + 2; })()")
        expect(look + ": nothing sticks out sideways", not over)
        pg.screenshot(path=str(OUT / ("colours_%s.png" % look)))
    expect("no script errors", errors == [])
    if errors:
        print("    " + "\n    ".join(errors[:10]))
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_colours)")
