"""The Calculator screen in an invisible Chrome: keypad and typing, history, fractions with steps, roots / powers / percents,
times tables with practice, a value table, equations, and the graph drawing."""
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: ''};
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.8', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]), engines: () => ok({engines: [], total: 0, folder: ''}),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, message: '', settings}); },
    jobs: () => ok([]), check_updates: () => ok({}), clipboard_offer: () => ok(null), mail: () => ok([]), games: () => ok([]),
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
    copy_text: (t) => { window.__calls.push(['copy', t]); return ok({ok: true, message: 'Copied ' + t}); },
    calc_show: () => { window.__calls.push(['calc_show']); return ok({ok: true}); },
  }};
  window.__calls = [];
})();
"""

page_file = OUT / "page_calc.html"
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
    pg.evaluate("window.toolbelt.go('calc')")
    pg.wait_for_selector("#cNat", timeout=5000)
    expr = lambda: pg.get_attribute("#cNat", "data-expr")

    def typed(text):                                           # what he'd type on the keyboard, from an empty box
        pg.click('[data-ck="ac"]')
        pg.focus("#cNat")
        pg.keyboard.type(text)

    # Rekenen: keys, typing, exact / decimal, history
    # the device: keys like a Casio / TI, typing straight into stacked fractions (25 Oct; ▶ leaves the fraction, like the Casio)
    for k in ["3", "frac", "4", "right", "add", "1", "frac", "8"]:
        pg.click('[data-ck="%s"]' % k)
    expect("the display types 3/4 + 1/8 as two stacked fractions", pg.locator("#cNat .fr").count() == 2 and expr() == "3/4+1/8")
    pg.click('[data-ck="eq"]')
    pg.wait_for_timeout(100)
    expect("= gives 7/8 as a stacked fraction, with 0.875 next to it", pg.locator("#cRes .fr").count() == 1 and "7" in pg.inner_text("#cRes .nu") and "0.875" in pg.inner_text("#cRes .dec"))
    expect("after = the sum stays, stacked", pg.locator("#cNat .fr").count() == 2 and expr() == "3/4+1/8")
    pg.click('[data-ck="sd"]')
    pg.wait_for_timeout(100)
    expect("S⇔D switches to the decimal 0.875", pg.inner_text("#cRes .big").strip() == "0.875" and "Decimal" in pg.inner_text(".cind"))
    pg.click('[data-ck="format"]')
    pg.wait_for_timeout(100)
    expect("FORMAT cycles back to the fraction", pg.locator("#cRes .fr").count() == 1 and "d/c" in pg.inner_text(".cind"))
    pg.click('[data-ck="ac"]')
    pg.click('[data-ck="shift"]')
    expect("SHIFT lights the small labels", pg.locator(".ckey.shifted").count() > 5 and pg.inner_text(".cind").startswith("S"))
    pg.click('[data-ck="sq"]')
    expect("SHIFT + x² inserts the cube", expr() == "^3" and pg.locator("#cNat .mpow").count() == 1 and pg.locator(".ckey.shifted").count() == 0)
    pg.click('[data-ck="ac"]')
    for k in ["2", "sqrt", "1", "6", "right"]:
        pg.click('[data-ck="%s"]' % k)
    expect("√▢ draws the root with its bar", expr() == "2√(16)" and pg.locator("#cNat .rad").count() == 1)
    pg.click('[data-ck="left"]')
    pg.click('[data-ck="left"]')
    pg.click('[data-ck="del"]')
    expect("◀ ◀ DEL deletes inside the sum (the 1 of 16)", expr() == "2√(6)")
    typed("sqrt(16)+2^10")
    expect("typing ^ raises what comes after", pg.locator("#cNat .mpow").count() == 1 and expr() == "sqrt(16)+2^10")
    pg.keyboard.press("Enter")
    expect("typing sqrt(16) + 2^10 = 1028", "1028" in pg.inner_text("#cRes"))
    typed("ans / 4")
    expect("/ after ans puts ans on top", pg.locator("#cNat .fr").count() == 1 and expr() == "ans/4")
    pg.keyboard.press("Enter")
    expect("ans uses the previous answer: 257", "257" in pg.inner_text("#cRes"))
    typed("1/0")
    pg.keyboard.press("Enter")
    expect("dividing by zero is explained", "nul" in pg.inner_text("#cRes"))
    expect("history lists the sums, drawn naturally", pg.locator("[data-hist]").count() >= 3 and pg.locator("#cHist .fr").count() >= 1)
    pg.click('[data-hist="1"]')
    pg.wait_for_timeout(100)
    expect("clicking a history line brings it back, in its shapes", "1028" in pg.inner_text("#cRes") and pg.locator("#cNat .mpow").count() == 1 and pg.locator("#cNat .sq").count() == 1 and expr() == "√(16)+2^10")
    typed("(1+2)/3")
    expect("/ after a bracket puts the whole bracket on top", pg.locator("#cNat .fr .nu").first.inner_text().replace("\n", "") == "(1+2)" and expr() == "(1+2)/3")
    typed("sin(30)")
    pg.keyboard.press("Enter")
    expect("degrees by default: sin(30) = 0.5", "0.5" in pg.inner_text("#cRes"))
    pg.click('[data-cdeg="false"]')
    pg.wait_for_timeout(100)
    expect("radians: sin(30) ≈ -0.988", "-0.988" in pg.inner_text("#cRes"))
    pg.click('[data-cdeg="true"]')
    typed("2x+1")
    pg.click('[data-ck="shift"]')
    pg.wait_for_selector(".ckey.shifted", timeout=3000)
    pg.click('[data-ck="format"]')
    pg.wait_for_selector("#cTf", timeout=3000)
    expect("SHIFT + FORMAT = table: the sum goes to the Tabel tab", pg.input_value("#cTf") == "y = 2x+1")
    pg.click('[data-ctab2="calc"]')
    pg.wait_for_selector("#cNat", timeout=3000)
    typed("2/3")
    pg.keyboard.press("ArrowRight")
    pg.keyboard.type(":4/5")
    pg.keyboard.press("Enter")
    expect("2/3 ÷ 4/5 = 5/6, the ÷ drawn between two fractions", pg.locator("#cNat .fr").count() == 2 and "5" in pg.inner_text("#cRes .nu") and "÷" in pg.inner_text("#cHist"))
    pg.screenshot(path=str(OUT / "calc_rekenen.png"))

    # memory keys, Esc, Ctrl+C, the mini button
    typed("3/4")
    pg.click('[data-ck="mplus"]')
    pg.wait_for_timeout(150)
    expect("M+ stores the answer and lights M", "M" in pg.inner_text(".cind") and pg.evaluate("window.toolbeltCalc.state().mem") == "3/4")
    pg.click('[data-ck="ac"]')
    pg.click('[data-ck="2"]')
    pg.click('[data-ck="mul"]')
    pg.click('[data-ck="mr"]')
    pg.click('[data-ck="eq"]')
    pg.wait_for_timeout(150)
    expect("MR puts the memory in the sum as a fraction: 2 × 3/4 = 3/2", expr() == "2×3/4" and pg.locator("#cNat .fr").count() == 1 and pg.locator("#cRes .fr").count() == 1 and pg.inner_text("#cRes .nu").strip() == "3")
    pg.click('[data-ck="mminus"]')
    pg.wait_for_timeout(150)
    expect("M− subtracts: 3/4 − 3/2 = -3/4", pg.evaluate("window.toolbeltCalc.state().mem") == "-3/4")
    pg.click('[data-ck="mc"]')
    pg.wait_for_timeout(150)
    expect("MC clears the memory", pg.evaluate("window.toolbeltCalc.state().mem") is None)
    pg.focus("#cNat")
    pg.keyboard.press("Control+c")
    pg.wait_for_timeout(150)
    expect("Ctrl+C with nothing selected copies the answer through Python", ["copy", "3/2"] in pg.evaluate("window.__calls"))
    pg.focus("#cNat")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    expect("Esc = AC", expr() == "" and pg.inner_text("#cRes").strip() == "")
    pg.click("#cMini")
    pg.wait_for_timeout(100)
    expect("Floating mini asks Python to show the small window", ["calc_show"] in pg.evaluate("window.__calls"))

    # Programmer
    pg.click('[data-ctab2="prog"]')
    pg.wait_for_selector("#cPexpr", timeout=3000)
    pg.fill("#cPexpr", "FF AND 0F")
    pg.press("#cPexpr", "Enter")
    pg.wait_for_selector(".bases", timeout=3000)
    expect("hex: FF AND 0F = 0F, shown in all four bases", "000F" in pg.inner_text(".brow.on") and "15" in pg.inner_text(".bases") and "1111" in pg.inner_text(".bases"))
    pg.click('[data-pbase="10"]')
    pg.wait_for_timeout(150)
    expect("switching to DEC converts the sum's value: 15", pg.input_value("#cPexpr") == "15")
    pg.click('[data-bit="4"]')
    pg.wait_for_timeout(150)
    expect("flipping bit 4 adds 16: 31", pg.input_value("#cPexpr") == "31")
    pg.click('[data-pbits="8"]')
    pg.fill("#cPexpr", "-1")
    pg.press("#cPexpr", "Enter")
    pg.wait_for_timeout(150)
    expect("-1 in 8 bits shows FF and the signed reading", "FF" in pg.inner_text(".bases") and "signed -1" in pg.inner_text(".bases"))
    pg.click('[data-pcopy]')
    pg.wait_for_timeout(100)
    expect("Copy sends the hex through Python", ["copy", "FF"] in pg.evaluate("window.__calls"))
    pg.screenshot(path=str(OUT / "calc_prog.png"))

    # Eenheden
    pg.click('[data-ctab2="units"]')
    pg.wait_for_selector("#cUval", timeout=3000)
    expect("1 km shows every length at once", "1000" in pg.inner_text(".urow:nth-child(3)") or "1000" in pg.inner_text(".card") and "mile" in pg.inner_text(".card"))
    pg.click('[data-ukind="temperature"]')
    pg.wait_for_timeout(150)
    pg.fill("#cUval", "100")
    pg.wait_for_timeout(150)
    expect("100 °C = 212 °F", "212" in pg.inner_text(".card"))
    pg.click('[data-ukind="data"]')
    pg.wait_for_timeout(100)
    pg.select_option("#cUfrom", "GiB")
    pg.wait_for_timeout(150)
    expect("100 GiB in MB and TiB", "107374.1824" in pg.inner_text(".card") and "0.09765625" in pg.inner_text(".card"))

    # Datum
    pg.click('[data-ctab2="date"]')
    pg.wait_for_selector("#cD1", timeout=3000)
    expect("days between 14 Oct 2026 and 1 Jan 2027: 79, woensdag → vrijdag", "79 dagen" in pg.inner_text("main") and "woensdag" in pg.inner_text("main") and "vrijdag" in pg.inner_text("main"))
    expect("14 Oct 2026 + 30 days = 13 Nov 2026", "2026-11-13" in pg.inner_text("main"))
    pg.click('[data-dunit="months"]')
    pg.wait_for_timeout(150)
    expect("+30 months = 14 Apr 2029", "2029-04-14" in pg.inner_text("main"))
    pg.fill("#cD2", "2026-02-30")
    pg.wait_for_timeout(150)
    expect("a date that doesn't exist is explained", "exist" in pg.inner_text(".err"))
    pg.screenshot(path=str(OUT / "calc_date.png"))

    # Breuken: typed straight into stacked boxes like his fx-82 (25 Oct)
    READ = r"""(sel) => [...document.querySelectorAll(sel)].map(b => { const c = b.cloneNode(true);
      c.querySelectorAll('.mcar').forEach(x => x.remove());
      c.querySelectorAll('.fr').forEach(f => f.replaceWith(' ' + f.querySelector('.nu').textContent + '/' + f.querySelector('.de').textContent));
      return c.textContent.replace(/\s+/g, ' ').trim(); })"""
    pg.click('[data-ctab2="frac"]')
    pg.wait_for_selector("#cFracEd", timeout=3000)
    pg.wait_for_timeout(200)
    expect("Breuken opens with 1/3 + 1/6 stacked, = 1/2 and a step", pg.locator("#cFracEd .fr").count() == 2 and pg.evaluate(READ, "#cFracOut .big") == ["= 1/2"] and "noemer 6" in pg.inner_text("#cFracSteps"))
    expect("the steps are stacked fractions too", pg.locator("#cFracSteps .fr").count() >= 4)
    pg.click("#cFracEd")
    pg.keyboard.press("Escape")
    pg.keyboard.type("1851/250")
    pg.keyboard.press("ArrowRight")
    pg.keyboard.type("*w36")
    pg.wait_for_timeout(100)
    expect("typing 1851/250 makes a stacked fraction (1851 on top), w makes a root", pg.evaluate(READ, "#cFracEd") == ["1851/250×√36"] and pg.locator("#cFracEd .sq").count() == 1)
    expect("his photo's sum: 1851/250 × √36 = 5553/125 = 44 53/125", pg.evaluate(READ, "#cFracOut .big") == ["= 5553/125", "= 44 53/125"] and "44.424" in pg.inner_text("#cFracOut .dec"))
    pg.screenshot(path=str(OUT / "calc_breuken.png"))
    pg.click('[data-fk="ac"]')
    for k in ["2", "frac", "3", "right", "÷", "4", "frac", "5"]:
        pg.click('[data-fk="%s"]' % k)
    pg.click('[data-fk="eq"]')
    expect("the keys: 2/3 ÷ 4/5 = 5/6, flip and multiply", pg.evaluate(READ, "#cFracOut .big") == ["= 5/6"] and "omkeren" in pg.inner_text("#cFracSteps"))
    pg.click('[data-fk="ac"]')
    for k in ["frac", "1", "down", "2"]:
        pg.click('[data-fk="%s"]' % k)
    expect("an empty fraction first, ▼ goes under the bar: 1/2", pg.evaluate(READ, "#cFracOut .big") == ["= 1/2"])
    pg.click('[data-fk="ac"]')
    pg.click('[data-fk="frac"]')
    pg.click('[data-fk="eq"]')
    expect("an empty box says so on =", "leeg vakje" in pg.inner_text("#cFracOut") and pg.locator("#cFracEd .mslot").count() == 2)
    pg.keyboard.press("Backspace")
    expect("DEL on an empty fraction takes it away", pg.locator("#cFracEd .fr").count() == 0)
    pg.click('[data-fq="1 1/2 + 2/3"]')
    pg.wait_for_timeout(100)
    expect("a mixed number: 1 1/2 + 2/3 = 13/6 = 2 1/6", pg.locator("#cFracEd .mmix").count() == 1 and pg.evaluate(READ, "#cFracOut .big") == ["= 13/6", "= 2 1/6"])
    pg.click('[data-fk="ac"]')
    pg.keyboard.type("2 1/4")
    expect("space after a number makes it a mixed number: 2 1/4 = 9/4", pg.locator("#cFracEd .mmix").count() == 1 and pg.evaluate(READ, "#cFracOut .big") == ["= 9/4", "= 2 1/4"])
    pg.click('[data-ctab2="calc"]')
    pg.click('[data-ctab2="frac"]')
    expect("the sum is still there after switching tabs", pg.evaluate(READ, "#cFracOut .big") == ["= 9/4", "= 2 1/4"])

    # Wortels & machten & procenten
    pg.click('[data-ctab2="roots"]')
    pg.wait_for_selector("#cRootN", timeout=3000)
    expect("root 2 of 16 = 4, 2^10 = 1024, 20% of 150 = 30", "4" in pg.inner_text(".cres") and "1024" in pg.inner_text("main") and "30" in pg.inner_text("#cPct"))
    pg.fill("#cRootN", "3")
    pg.fill("#cRootX", "27")
    pg.wait_for_timeout(150)
    expect("3√27 = 3", pg.inner_text(".cres").strip().startswith("3"))
    pg.fill("#cPowY", "1/2")
    pg.wait_for_timeout(150)
    expect("2^(1/2) is a decimal 1.414…", "1.41421" in pg.inner_text("main"))

    # Tafels + oefenen
    pg.click('[data-ctab2="times"]')
    pg.wait_for_selector("#cTafel", timeout=3000)
    expect("the 7 times table", "7 × 7" in pg.inner_text(".ctable") and "49" in pg.inner_text(".ctable"))
    pg.click('[data-tafel="9"]')
    pg.wait_for_timeout(100)
    expect("another table from the chips", "9 × 9" in pg.inner_text(".ctable") and "81" in pg.inner_text(".ctable"))
    pg.click("#cQuizOne")
    pg.wait_for_selector("#cQuizIn", timeout=3000)
    q = pg.evaluate("window.toolbeltCalc.state().quiz")
    pg.fill("#cQuizIn", str(q[0] * q[1]))
    pg.press("#cQuizIn", "Enter")
    pg.wait_for_timeout(150)
    expect("a right answer counts: 1 goed van 1", "Goed" in pg.inner_text("main") and "1 goed van 1" in pg.inner_text("main"))
    pg.click("#cQuizAll")
    pg.wait_for_selector("#cQuizIn", timeout=3000)
    pg.fill("#cQuizIn", "0")
    pg.click("#cQuizGo")
    pg.wait_for_timeout(150)
    expect("a wrong answer shows the right one: 1 goed van 2", "Nee" in pg.inner_text("main") and "1 goed van 2" in pg.inner_text("main"))

    # Tabel
    pg.click('[data-ctab2="table"]')
    pg.wait_for_selector("#cTf", timeout=3000)
    pg.fill("#cTf", "y = 2x^2 + 3")
    pg.wait_for_timeout(150)
    expect("a value table of y = 2x^2 + 3 from -5", pg.locator(".ctable tbody tr").count() == 11 and "53" in pg.inner_text(".ctable"))
    pg.fill("#cTfrom", "0")
    pg.wait_for_timeout(150)
    expect("changing the start redraws (x = 0 → y = 3 on the first row)", pg.inner_text(".ctable tbody tr").startswith("0"))

    # Vergelijkingen
    pg.click('[data-ctab2="solve"]')
    pg.wait_for_selector("#cEq", timeout=3000)
    pg.wait_for_timeout(200)
    expect("2x + 3 = 11 → x = 4 with steps", "x = 4" in pg.inner_text(".cres") and "2x = 8" in pg.inner_text(".steps"))
    pg.click('[data-eq="x^2 - 5x + 6 = 0"]')
    pg.wait_for_timeout(200)
    expect("abc-formule: x = 3 of x = 2, D shown", "x = 3" in pg.inner_text(".cres") and "x = 2" in pg.inner_text(".cres") and "D = b² − 4ac" in pg.inner_text(".steps"))
    pg.screenshot(path=str(OUT / "calc_solve.png"))

    # Grafiek
    pg.click('[data-ctab2="graph"]')
    pg.wait_for_selector("#cCanvas", timeout=3000)
    pg.wait_for_timeout(200)
    painted = pg.evaluate("""() => { const c = document.querySelector('#cCanvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let pink = 0, blue = 0; for (let i = 0; i < d.length; i += 4) { if (d[i] > 200 && d[i+1] < 120 && d[i+2] > 100) pink++; if (d[i] < 120 && d[i+1] > 150 && d[i+2] > 200) blue++; } return [pink, blue]; }""")
    expect("two formulas are drawn in their colours", painted[0] > 300 and painted[1] > 300)
    pg.hover("#cCanvas", position={"x": 380, "y": 230})
    pg.wait_for_timeout(100)
    expect("hovering reads x and y", "x =" in pg.inner_text("#cHover") and "y =" in pg.inner_text("#cHover"))
    pg.fill('[data-gf="2"]', "y = 1/x")
    pg.wait_for_timeout(150)
    expect("a third formula with a hole (1/x) draws without errors", errors == [])
    pg.click("#cGZoomIn")
    v = pg.evaluate("window.toolbeltCalc.state().view")
    expect("zoom in narrows the view", v["x1"] - v["x0"] < 20)
    pg.screenshot(path=str(OUT / "calc_graph.png"))
    expect("nothing sticks out sideways", pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"))
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_calc)")
