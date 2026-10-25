"""The floating mini calculator page in an invisible Chrome: the shared device works there, keys, S⇔D, hide, open full."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from page import build_calcpop                                # noqa: E402
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
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok({look: 'glassdark', accent: ''}), info: () => ok({version: 'x', logos: {}}),
    copy_text: (t) => { window.__calls.push(['copy', t]); return ok({ok: true, message: 'Copied'}); },
    calc_hide: () => { window.__calls.push(['hide']); return ok({ok: true}); },
    show_main: (s) => { window.__calls.push(['main', s]); return ok({ok: true}); },
  }};
})();
"""

page_file = OUT / "calcpop.html"
page_file.write_text(build_calcpop(), encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 380, "height": 560})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("document.querySelector('#root').classList.contains('glass-dark')", timeout=8000)
    expect("the mini window takes the look and has the keys", pg.locator("[data-ck]").count() == 44 and pg.evaluate("window.calcPop.state().keys") == 44)
    for k in ["1", "frac", "3", "right", "add", "1", "frac", "6", "eq"]:   # ▶ leaves the fraction, like the Casio
        pg.click('[data-ck="%s"]' % k)
    pg.wait_for_timeout(100)
    expect("1/3 + 1/6 = 1/2, stacked", pg.locator("#cRes .fr").count() == 1 and pg.inner_text("#cRes .nu").strip() == "1" and pg.inner_text("#cRes .de").strip() == "2")
    pg.click('[data-ck="sd"]')
    pg.wait_for_timeout(100)
    expect("S⇔D shows 0.5", pg.inner_text("#cRes .big").strip() == "0.5")
    pg.click('[data-ck="copy"]')
    pg.wait_for_timeout(100)
    expect("COPY sends the answer through Python", ["copy", "0.5"] in pg.evaluate("window.__calls"))
    pg.screenshot(path=str(OUT / "calcpop.png"))
    pg.click("#full")
    pg.click("#close")
    pg.wait_for_timeout(100)
    calls = pg.evaluate("window.__calls")
    expect("⤢ opens the full calculator, ✕ hides", ["main", "calc"] in calls and ["hide"] in calls)
    expect("the header is the drag handle", pg.locator(".ph.pywebview-drag-region").count() == 1)
    expect("nothing sticks out sideways", pg.evaluate("document.documentElement.scrollWidth") <= 380)
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_calcpop)")
