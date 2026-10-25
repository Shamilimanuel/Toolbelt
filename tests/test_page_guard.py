"""App guard on the page (18 Oct), in an invisible Chrome with a pretend Python side: the App guard screen (switch,
Trusted / Quarantine / Activity / Settings, Forget / Restore / Delete) and the warning window (web/guard.html)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from page import build_guard, build_page                      # noqa: E402
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: '', guard_on: true, guard_signed: true, guard_scan: true};
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  const G = window.__g = {trusted: [{path: 'E:\\Tools\\my-tool.exe', name: 'my-tool.exe', signed: false, when: '2026-10-18 12:00'}],
    quarantine: [{id: 'q1', name: 'cheat-loader.exe', original: 'E:\\Downloads\\cheat-loader.exe', stored: 'x', when: '2026-10-18 12:05', why: 'Defender: Trojan:Win32/Wacatac'}],
    log: [{t: '2026-10-18 12:05', what: 'cheat-loader.exe · stopped and moved to quarantine'}], known: 68,
    scans: {program: {kind: 'program', label: 'Program check', when: '2026-10-18 13:00', checked: 24, fine: 21, findings: [
      {path: 'C:/Users/you/Downloads/photo.jpg.exe', name: 'photo.jpg.exe', place: 'Downloads', verdict: 'danger', size: 1, checks: [['bad', 'A program pretending to be a jpg'], ['warn', 'Not signed']]},
      {path: 'C:/Temp/setup.exe', name: 'setup.exe', place: 'Temp', verdict: 'unknown', size: 1, checks: [['warn', 'Not signed']]}]},
      quick: {kind: 'quick', label: 'Defender quick scan', when: '2026-10-18 12:00', findings: [], threats: [], seconds: 260, clean: true}},
    downloads: [{path: 'C:/Users/you/Downloads/song.mp3', name: 'song.mp3', verdict: 'safe', checks: [['ok', 'Defender: nothing found']], when: '2026-10-18 13:10', site: 'example.test'}]};
  const pending = window.__pending = [
    {id: 1, pid: 10, path: 'E:\\Downloads\\invoice.pdf.exe', name: 'invoice.pdf.exe', verdict: 'danger', signed: false, when: '2026-10-18 12:31', checks: [['bad', 'A Windows program with a second, fake ending (.pdf). Don\'t open it.'], ['warn', 'Not signed'], ['warn', 'Downloaded from free-files.example'], ['ok', 'Defender: nothing found']]},
    {id: 3, kind: 'notice', name: 'USB stick E: (KINGSTON) checked', path: '', verdict: 'danger', when: '2026-10-18 12:40', actions: ['show', 'ok'], checks: [['bad', '2 risky things found'], ['ok', '12 programs checked']]},
    {id: 2, pid: 11, path: 'C:\\Users\\you\\Projects\\tool.exe', name: 'tool.exe', verdict: 'unknown', signed: false, when: '2026-10-18 12:32', checks: [['warn', 'Not signed (normal for your own programs)'], ['ok', 'Name and file type match']]}];
  window.__calls = [];
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '1', data: 'x', logos: {}}), gpus: () => ok([]), jobs: () => ok(window.__jobs || []),
    guard_scan: (kind) => { window.__calls.push(['scan', kind]); window.__jobs = [{id: 9, title: 'Program check', kind: 'Scan', progress: 40, state: 'running', message: 'Program check: 10 of 24', extra: {scan: kind}}]; return ok({ok: true, job: 9, message: 'Started'}); },
    guard_finding: (p, a) => { window.__calls.push(['finding', p, a]); if (a !== 'show') G.scans.program.findings = G.scans.program.findings.filter(f => f.path !== p); return ok({ok: true, message: a}); }, clipboard_offer: () => ok(null), mail: () => ok([]),
    engines: () => ok({engines: [], total: 0, folder: 'x'}), check_updates: () => ok({}), net_state: () => ok({installed: true, state: 'on'}),
    set_setting: (k, v) => { settings[k] = v; window.__calls.push(['set', k, v]); return ok({ok: true, settings}); },
    open_folder: (w) => { window.__calls.push(['open', w]); return ok({ok: true}); },
    guard_status: () => ok(Object.assign({on: settings.guard_on, running: settings.guard_on, pending: pending.length}, G)),
    guard_switch: (on) => { settings.guard_on = on; window.__calls.push(['switch', on]); return ok({ok: true, message: on ? 'watching' : 'off'}); },
    guard_forget: (p) => { G.trusted = G.trusted.filter(t => t.path !== p); window.__calls.push(['forget', p]); return ok({ok: true, message: 'forgotten'}); },
    guard_restore: (id) => { G.quarantine = G.quarantine.filter(q => q.id !== id); window.__calls.push(['restore', id]); return ok({ok: true, message: 'restored'}); },
    guard_delete: (id) => { G.quarantine = G.quarantine.filter(q => q.id !== id); window.__calls.push(['delete', id]); return ok({ok: true, message: 'deleted'}); },
    guard_pending: () => ok({pending}),
    guard_decide: (id, action) => { const i = pending.findIndex(p => p.id === id); if (i >= 0) pending.splice(i, 1); window.__calls.push(['decide', id, action]); return ok({ok: true, message: action}); },
  }};
})();
"""


def calls(pg, name):
    return pg.evaluate("window.__calls.filter(c => c[0] === %r)" % name)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors = []
    # ---------- the App guard screen ----------
    pg = browser.new_page(viewport={"width": 1320, "height": 860})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(FAKE)
    f = OUT / "page_guard.html"
    f.write_text(build_page(), encoding="utf-8")
    pg.goto(f.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    expect("App guard is in the sidebar", "App guard" in pg.inner_text("#side"))
    pg.evaluate("window.toolbelt.go('guard')")
    pg.wait_for_selector(".gstate", timeout=4000)
    expect("it says it's watching, with the counts", "Watching for new programs" in pg.inner_text("main") and "68 programs known" in pg.inner_text("main"))
    expect("Trusted lists my-tool.exe", "my-tool.exe" in pg.inner_text("main"))
    pg.screenshot(path=str(OUT / "guard_screen.png"))
    pg.click('[data-gforget]')
    pg.wait_for_timeout(300)
    expect("Forget reaches Python with the path", calls(pg, "forget") == [["forget", "E:\\Tools\\my-tool.exe"]])
    pg.click('[data-gtab="stopped"]')
    pg.wait_for_selector('[data-grestore="q1"]', timeout=3000)
    expect("Quarantine shows why it was stopped", "Trojan" in pg.inner_text("main"))
    pg.click('[data-grestore="q1"]')
    pg.wait_for_timeout(300)
    expect("Restore reaches Python", calls(pg, "restore") == [["restore", "q1"]])
    pg.click('[data-gtab="log"]')
    expect("Activity lists what happened", "stopped and moved to quarantine" in pg.inner_text("main"))
    pg.click('[data-gtab="settings"]')
    pg.click("#gScan")
    pg.wait_for_timeout(200)
    expect("Settings: the Defender switch saves", ["set", "guard_scan", False] in pg.evaluate("window.__calls"))
    pg.click('[data-open="quarantine"]')
    pg.wait_for_timeout(200)
    expect("Settings: Open the quarantine folder", calls(pg, "open") == [["open", "quarantine"]])
    pg.click('[data-gtab="scan"]')
    pg.wait_for_selector('[data-gscan="program"]', timeout=3000)
    expect("Scan: four scans to start, with when each last ran", pg.locator("[data-gscan]").count() == 4 and "Last: 2026-10-18 13:00" in pg.inner_text("main"))
    expect("Scan: the latest result shows what to look at", "2 to look at" in pg.inner_text("main") and "photo.jpg.exe" in pg.inner_text("main") and "24 programs checked" in pg.inner_text("main"))
    pg.screenshot(path=str(OUT / "guard_scan.png"), full_page=True)
    pg.click('[data-gfind="quarantine"][data-path="C:/Users/you/Downloads/photo.jpg.exe"]')
    pg.wait_for_timeout(400)
    expect("Scan: Quarantine on a find reaches Python and it leaves the list", calls(pg, "finding")[-1][2] == "quarantine" and "photo.jpg.exe" not in pg.inner_text("main"))
    pg.click('[data-gres="quick"]')
    expect("Scan: earlier scans stay viewable (quick scan: nothing risky)", "Nothing risky found" in pg.inner_text("main"))
    pg.click('[data-gscan="program"]')
    pg.wait_for_selector("#gScanRun", timeout=4000)
    expect("Scan: starting one shows its bar, and the buttons wait", calls(pg, "scan") == [["scan", "program"]] and pg.is_disabled('[data-gscan="quick"]'))
    pg.evaluate("window.__jobs = []")
    pg.click('[data-gtab="downloads"]')
    expect("Downloads: checked downloads are listed", "song.mp3" in pg.inner_text("main") and "FINE" in pg.inner_text("main"))
    pg.click('[data-gtab="settings"]')
    pg.click("#gUsb")
    pg.wait_for_timeout(200)
    expect("Settings: the USB stick check can be switched", ["set", "guard_usb", False] in pg.evaluate("window.__calls"))
    pg.click("#gOn")
    pg.wait_for_timeout(400)
    expect("the big switch turns it off", calls(pg, "switch") == [["switch", False]] and "App guard is off" in pg.inner_text("main"))
    for look in ("glass", "glassdark"):
        pg.evaluate("window.pywebview.api.set_setting('look', %r)" % look)
        r = pg.evaluate("window.toolbelt.walkScreens()")
        expect("every screen opens in %s (%d)" % (look, r["count"]), not r["failed"])

    # ---------- the warning window ----------
    w = browser.new_page(viewport={"width": 380, "height": 470})
    w.on("pageerror", lambda e: errors.append(str(e)))
    w.add_init_script(FAKE)
    f2 = OUT / "page_guardwin.html"
    f2.write_text(build_guard(), encoding="utf-8")
    w.goto(f2.as_uri())
    w.wait_for_selector("#aStop", timeout=5000)
    text = w.inner_text("#card")
    expect("the warning shows the oldest question: name, DANGER, the checks", "invoice.pdf.exe" in text and "DANGER" in text and "fake ending" in text)
    expect("and that more wait", "2 more waiting" in text)
    no_scroll = w.evaluate("document.querySelector('.gin').scrollHeight <= document.querySelector('.gin').clientHeight + 2")
    expect("it fits its 380 × 470 window without scrolling", no_scroll)
    w.screenshot(path=str(OUT / "guard_window.png"))
    w.click("#aStop")
    w.wait_for_selector('[data-act="show"]', timeout=4000)
    expect("Stop it answers Python; next a USB stick note with Show in Toolbelt / OK", w.evaluate("window.__calls") == [["decide", 1, "stop"]] and "KINGSTON" in w.inner_text("#card"))
    w.screenshot(path=str(OUT / "guard_notice.png"))
    w.click('[data-act="ok"]')
    w.wait_for_function("document.querySelector('#card').innerText.indexOf('tool.exe') !== -1", timeout=4000)
    expect("OK on the note answers Python, then the last question shows", w.evaluate("window.__calls")[-1] == ["decide", 3, "ok"] and "UNKNOWN" in w.inner_text("#card"))
    w.click("#aTrust")
    w.wait_for_function("document.querySelector('#card').innerText.indexOf('Nothing to decide') !== -1", timeout=4000)
    expect("Trust it on the last one empties the window", w.evaluate("window.__calls")[-1] == ["decide", 2, "trust"])
    expect("no errors on either page", not errors)
    for e in errors[:4]:
        print("      " + e)
    browser.close()

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
