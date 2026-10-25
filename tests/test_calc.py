"""The maths engine (web/calc.js) checked in an invisible Chrome: exact fractions, roots, powers, reading what was typed,
fraction steps, tables, equations with the abc-formule, and the numeric fallback."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from playwright.sync_api import sync_playwright                # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


ENGINE = (Path(__file__).resolve().parent.parent / "web" / "calc.js").read_text(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page()
    pg.set_content('<!doctype html><meta charset="utf-8"><title>calc</title><script>' + ENGINE + "</script>")   # the engine has √ × ÷ π in it

    def ev(expr, mode="exact"):
        return pg.evaluate("([e, m]) => { try { return calc.format(calc.calc(e), m); } catch (err) { return 'ERR ' + err.message; } }", [expr, mode])

    # arithmetic, exactness
    expect("1/3 + 1/6 = 1/2 (exact)", ev("1/3 + 1/6") == "1/2")
    expect("0.25 + 0.5 = 3/4 exactly, 0.75 as decimal", ev("0.25 + 0.5") == "3/4" and ev("0.25 + 0.5", "decimal") == "0.75")
    expect("mixed numbers: 7/4 = 1 3/4", ev("7/4", "mixed") == "1 3/4")
    expect("2^10 = 1024, 2^-2 = 1/4, (2/3)^2 = 4/9", ev("2^10") == "1024" and ev("2^-2") == "1/4" and ev("(2/3)^2") == "4/9")
    expect("√16 = 4, √(4/9) = 2/3, ∛27 = 3, root(4, 81) = 3", ev("√16") == "4" and ev("sqrt(4/9)") == "2/3" and ev("∛27") == "3" and ev("root(4, 81)") == "3")
    expect("√2 is a decimal", ev("√2").startswith("1.41421356"))
    expect("8^(1/3) = 2 exactly, 27^(2/3) = 9", ev("8^(1/3)") == "2" and ev("27^(2/3)") == "9")
    expect("school typing: 2x with x=3 → 6, 3(4+5) = 27, 2² = 4, 5! = 120, 20% = 1/5", pg.evaluate("calc.format(calc.calc('2x', {x: calc.R(3n)}))") == "6" and ev("3(4+5)") == "27" and ev("2²") == "4" and ev("5!") == "120" and ev("20%") == "1/5")
    expect("commas work as decimal points: 1,5 × 2 = 3", ev("1,5 × 2") == "3")
    expect("π and e; sin 30 in degrees = 1/2 (as 0.5)", ev("2π").startswith("6.2831853") and ev("sin(30)") == "0.5" and ev("cos 60") == "0.5")
    expect("precedence: 2 + 3 × 4 = 14, -2^2 = -4, 2^3^2 = 512", ev("2 + 3 × 4") == "14" and ev("-2^2") == "-4" and ev("2^3^2") == "512")
    expect("big numbers stay exact: 50! has 65 digits", "65 digits" in ev("50!"))
    expect("dividing by zero is explained", ev("1/0").startswith("ERR") and "nul" in ev("1/0"))
    expect("a typo is explained", ev("2 +* 3").startswith("ERR") and ev("hello").startswith("ERR"))
    expect("√ of a negative is explained", "negatief" in ev("√-4"))

    # the natural display
    h = pg.evaluate("calc.html('1/3 + 1/6')")
    expect("a fraction is drawn stacked: numerator over denominator", h.count('class="fr"') == 2 and '<span class="nu">1</span><span class="de">3</span>' in h)
    expect("√ gets its bar, powers go up, × shows as ×", 'class="rad">16' in pg.evaluate("calc.html('√16')") and "2<sup>10</sup>" in pg.evaluate("calc.html('2^10')") and "3×4" in pg.evaluate("calc.html('3*4')"))
    expect("brackets come back where they matter: 3(4 + 5), (1/2)^3", pg.evaluate("calc.html('3(4+5)')") == "3(4 + 5)" and pg.evaluate("calc.html('(1/2)^3')").startswith("(<span"))
    expect("a half-typed sum still shows something", pg.evaluate("calc.html('2 +')") == "2 +")
    expect("a result draws as a fraction, mixed or decimal", 'class="fr"' in pg.evaluate("calc.htmlValue(calc.calc('7/4'), 'exact')") and pg.evaluate("calc.htmlValue(calc.calc('7/4'), 'mixed')").startswith("1<span") and pg.evaluate("calc.htmlValue(calc.calc('7/4'), 'decimal')") == "1.75")

    # programmer mode
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('0xFF AND 0b1010', 10, 8))"))
    expect("hex AND bin in 8 bits: 10 = 0A = 00001010", pr["unsigned"] == "10" and pr["hex"] == "0A" and pr["bin"] == "00001010" and pr["binGrouped"] == "0000 1010")
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('FF AND 0F', 16, 16))"))
    expect("in hex, AND is a word, not the digit A: FF AND 0F = 000F", pr["hex"] == "000F")
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('FF << 4', 16, 16))"))
    expect("plain FF in hex base, shifted: 0FF0", pr["hex"] == "0FF0" and pr["unsigned"] == "4080")
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('-1', 10, 8))"))
    expect("-1 in 8 bits reads as FF (two's complement), signed stays -1", pr["hex"] == "FF" and pr["signed"] == "-1" and pr["unsigned"] == "255")
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('1 + 2 * 3 | 8 ^ 1', 10, 32))"))
    expect("C precedence: * before +, then ^, then |", pr["unsigned"] == str((1 + 2 * 3) | (8 ^ 1)))
    pr = json.loads(pg.evaluate("JSON.stringify(calc.prog('NOT 0', 10, 8))"))
    expect("NOT 0 in 8 bits = FF", pr["hex"] == "FF")
    expect("a bad digit for the base is explained", "base 2" in pg.evaluate("(function(){ try { calc.prog('102', 2, 8); return ''; } catch (e) { return e.message; } })()"))
    expect("bits back to a number", json.loads(pg.evaluate("JSON.stringify(calc.progFromBits([true,false,true,false,false,false,false,false], 8))"))["hex"] == "A0")

    # units
    u = {r["unit"]: r["value"] for r in json.loads(pg.evaluate("JSON.stringify(calc.convert('length', 1, 'mile'))"))}
    expect("1 mile = 1609.344 m = 1.609344 km", abs(u["m"] - 1609.344) < 1e-9 and abs(u["km"] - 1.609344) < 1e-9)
    u = {r["unit"]: r["value"] for r in json.loads(pg.evaluate("JSON.stringify(calc.convert('temperature', 100, '°C'))"))}
    expect("100 °C = 212 °F = 373.15 K", abs(u["°F"] - 212) < 1e-9 and abs(u["K"] - 373.15) < 1e-9)
    u = {r["unit"]: r["value"] for r in json.loads(pg.evaluate("JSON.stringify(calc.convert('data', 1, 'GiB'))"))}
    expect("1 GiB = 1073.741824 MB = 1024 MiB", abs(u["MB"] - 1073.741824) < 1e-6 and abs(u["MiB"] - 1024) < 1e-9)
    expect("eleven kinds of units", pg.evaluate("Object.keys(calc.UNITS).length") == 11)

    # dates
    d = json.loads(pg.evaluate("JSON.stringify(calc.dateDiff('2026-10-14', '2027-01-01'))"))
    expect("14 Oct 2026 → 1 Jan 2027 = 79 days = 11 weeks and 2 days = 2 months 18 days", d["days"] == 79 and d["weeks"] == 11 and d["restDays"] == 2 and d["months"] == 2 and d["daysLeft"] == 18 and d["weekdayFrom"] == "woensdag")
    d = json.loads(pg.evaluate("JSON.stringify(calc.dateDiff('01-01-2027', '14-10-2026'))"))
    expect("the other way round counts negative, Dutch day order works", d["days"] == -79)
    a = json.loads(pg.evaluate("JSON.stringify(calc.dateAdd('2026-01-31', 1, 'months'))"))
    expect("31 Jan + 1 month rolls into March like JavaScript (3 Mar)", a["date"] == "2026-03-03")
    expect("30 Feb is refused", "exist" in pg.evaluate("(function(){ try { calc.parseDate('2026-02-30'); return ''; } catch (e) { return e.message; } })()"))

    # fractions with steps
    fs = pg.evaluate("JSON.stringify((function () { var r = calc.fractionSteps('1/3 + 1/6'); return {exact: r.exact, mixed: r.mixed, decimal: r.decimal, steps: r.steps}; })())")
    fs = json.loads(fs)
    expect("fraction steps: common denominator shown, then simplified", fs["exact"] == "1/2" and len(fs["steps"]) == 1 and "noemer 6" in fs["steps"][0] and "vereenvoudigd" in fs["steps"][0] and fs["decimal"] == "0.5")
    fs2 = json.loads(pg.evaluate("JSON.stringify(calc.fractionSteps('2/3 ÷ 4/5').steps)"))
    expect("dividing fractions: flip and multiply", "omkeren" in fs2[0] and "5/4" in fs2[0] and "10/12" in fs2[0] and "5/6" in fs2[0])
    fs3 = json.loads(pg.evaluate("JSON.stringify(calc.fractionSteps('1/2 + 1/3 + 1/6').steps)"))
    expect("a chain of three fractions gives two steps", len(fs3) == 2)

    # tables
    tt = pg.evaluate("JSON.stringify(calc.times(7, 10))")
    expect("the 7 times table up to 10", json.loads(tt)[6] == [7, 7, 49] and len(json.loads(tt)) == 10)
    vt = json.loads(pg.evaluate("JSON.stringify(calc.table('y = 2x^2 + 3', -2, 1, 5))"))
    expect("a value table of y = 2x² + 3 from -2 step 1", [r["y"] for r in vt] == ["11", "5", "3", "5", "11"] and vt[0]["x"] == "-2")
    vt2 = json.loads(pg.evaluate("JSON.stringify(calc.table('1/x', 0, 0.5, 3))"))
    expect("a value table shows — where the formula breaks (1/0)", vt2[0]["y"] == "—" and vt2[1]["y"] == "2")

    # equations
    def solve(eq):
        return json.loads(pg.evaluate("e => { try { var r = calc.solve(e); return JSON.stringify({kind: r.kind, roots: r.roots.map(x => calc.format(x)), steps: r.steps}); } catch (err) { return JSON.stringify({kind: 'ERR', msg: err.message}); } }", eq))

    s = solve("2x + 3 = 11")
    expect("linear: 2x + 3 = 11 → x = 4 with steps", s["kind"] == "linear" and s["roots"] == ["4"] and any("2x = 8" in st for st in s["steps"]))
    s = solve("x^2 - 5x + 6 = 0")
    expect("quadratic: abc-formule, D = 1, x = 3 or 2", s["kind"] == "quadratic" and s["roots"] == ["3", "2"] and any("D = b² − 4ac" in st and "= 1" in st for st in s["steps"]))
    s = solve("(x + 1)(x - 2) = 0")
    expect("brackets multiplied out: x = 2 or -1", sorted(s["roots"]) == ["-1", "2"])
    s = solve("x^2 + 1 = 0")
    expect("D < 0: no solution", s["kind"] == "none" and any("D < 0" in st for st in s["steps"]))
    s = solve("x^2 + 2x + 1 = 0")
    expect("D = 0: one solution x = -1", s["roots"] == ["-1"])
    s = solve("x^2 = 2")
    expect("√2 stays a decimal in the roots", s["kind"] == "quadratic" and s["roots"][0].startswith("1.41421"))
    s = solve("2x + 1 = 2x + 1")
    expect("always true is said", s["kind"] == "all")
    s = solve("x^3 - x = 0")
    expect("a cubic falls back to a numeric search: three roots", s["kind"] == "numeric" and sorted(float(r) for r in s["roots"]) == [-1.0, 0.0, 1.0])
    s = solve("2x + 3")
    expect("no = is explained", s["kind"] == "ERR" and "=" in s["msg"])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_calc)")
