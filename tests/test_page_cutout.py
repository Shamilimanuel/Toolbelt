"""Tests the Cut out screen in an invisible Chrome, with a pretend Python side. No window appears, no model runs.

Walks: install the model, open a picture, the cut-out arriving, background choices, the sticker outline, save, copy,
Discord sizes, Ctrl+V, a dropped picture, and the earlier-this-session strip.
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
  const PIC = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200"><rect width="320" height="200" fill="#7FB6E8"/><circle cx="160" cy="110" r="60" fill="#E8893A"/></svg>');
  const CUTPIC = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200"><circle cx="160" cy="110" r="60" fill="#E8893A"/></svg>');
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false,
    open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true};
  let model = false, jobs = [], nextId = 1, cuts = {};
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  function tick() {
    jobs.forEach(j => {
      if (j.state === 'waiting') j.state = 'running';
      else if (j.state === 'running') { j.progress = Math.min(100, j.progress + 50); j.message = 'Cutting out on the graphics card';
        if (j.progress >= 100) { j.state = 'done'; if (j.kind === 'Engine') model = true; } }
    });
  }
  function start(name) {
    const token = 'c' + nextId; cuts[token] = {bg: 'none', colour: '#FFFFFF', outline: 0, shadow: false, name};
    jobs.unshift({id: nextId++, title: 'Cut out ' + name, kind: 'Cut out', progress: 0, state: 'waiting', message: '', result: null, extra: {token}});
    return ok({ok: true, id: nextId - 1, token, before: PIC});
  }
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.3', data: 'x', prototype: 'p'}), gpus: () => ok(['AMD Radeon RX 9060 XT']),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, settings}); },
    engines: () => ok({engines: [{id: 'birefnet', name: 'BiRefNet', what: 'cut-outs', licence: 'MIT', approx: '~930 MB', installed: model, size: 0, version: '', step: 3}], total: 0, folder: 'x'}),
    jobs: () => { tick(); return ok(jobs); }, clear_jobs: () => ok({ok: true}), cancel_job: () => ok({ok: true}),
    install_engines: (ids) => { window.__calls.push(['install', ids]); jobs.unshift({id: nextId++, title: 'Install the BiRefNet model', kind: 'Engine', progress: 0, state: 'waiting', message: '', result: null, extra: {engine: 'birefnet'}}); return ok({ok: true, message: 'Installing 1 engine'}); },
    cut_pick: () => { window.__calls.push(['pick']); return start('cat-photo'); },
    cut_paste: () => { window.__calls.push(['paste']); return start('pasted picture'); },
    cut_data: (name, data) => { window.__calls.push(['data', name, data.slice(0, 22)]); return start(name.replace(/\.\w+$/, '')); },
    cut_result: (token) => { const c = cuts[token]; return ok({ok: true, token, name: c.name, before: PIC, after: CUTPIC, width: 1600, height: 1000, seconds: 8.1, device: 'graphics card', options: c}); },
    cut_set: (token, o) => { window.__calls.push(['set', o]); Object.assign(cuts[token], o); return ok({ok: true, after: CUTPIC, options: cuts[token]}); },
    cut_background_picture: (token) => { cuts[token].bg = 'picture'; return ok({ok: true, after: CUTPIC, options: cuts[token]}); },
    cut_save: (token) => { window.__calls.push(['save', token]); return ok({ok: true, message: 'Saved cat-photo - cut out.png'}); },
    cut_copy: (token, kind) => { window.__calls.push(['copy', token, kind || '']); return ok({ok: true, message: 'Copied'}); },
    cut_discord: (token) => { window.__calls.push(['discord', token]); return ok({ok: true, message: 'Saved the emoji, sticker and server icon.'}); },
    clipboard_offer: () => ok(null), songs: () => ok({songs: []}), check_updates: () => ok({}),
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
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
    pg.evaluate("window.toolbelt.go('bg')")
    pg.wait_for_timeout(300)

    expect("without the model it offers to install it", pg.locator("#cutInstall").count() == 1 and "928 MB" in pg.inner_text("main"))
    pg.click("#cutInstall")
    pg.wait_for_selector("#cutOpen", timeout=10000)
    expect("after installing, the drop zone appears", pg.locator("#cutDrop").count() == 1)

    pg.click("#cutOpen")
    pg.wait_for_selector("#cutBa", timeout=8000)
    text = pg.inner_text("main")
    expect("the cut-out arrives with time and device", "8.1 s on the graphics card" in text and "1600 × 1000" in text)
    expect("before/after slider shows both pictures", pg.locator("#cutBa img").count() == 2)
    pg.screenshot(path=str(OUT / "cutout_result.png"))

    pg.click('[data-bg="white"]')
    pg.wait_for_timeout(250)
    expect("White asks Python for a white background", ["set", {"bg": "white"}] in pg.evaluate("window.__calls"))
    expect("sticker options only show for see-through", pg.locator("#cutOutline").count() == 0)
    pg.click('[data-bg="colour"]')
    pg.wait_for_timeout(250)
    expect("Colour shows a colour picker", pg.locator("#cutColour").count() == 1)
    pg.click('[data-bg="none"]')
    pg.wait_for_timeout(250)
    pg.eval_on_selector("#cutOutline", "el => { el.value = 12; el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); }")
    pg.wait_for_timeout(250)
    pg.click("#cutShadow")
    pg.wait_for_timeout(250)
    calls = pg.evaluate("window.__calls")
    expect("outline and shadow reach Python", ["set", {"outline": 12}] in calls and ["set", {"shadow": True}] in calls)

    pg.click("#cutSave")
    pg.click("#cutCopy")
    pg.click('[data-dc="emoji"]')
    pg.click("#cutDiscord")
    pg.wait_for_timeout(300)
    calls = pg.evaluate("window.__calls")
    token = next((c[1] for c in calls if c[0] == "save"), None)
    expect("save, copy, emoji copy and Discord sizes all go through Python, for this cut-out",
           token and ["copy", token, ""] in calls and ["copy", token, "emoji"] in calls and ["discord", token] in calls)

    pg.keyboard.press("Control+v")
    pg.wait_for_selector("#cutBa", timeout=8000)
    pg.wait_for_timeout(400)
    expect("Ctrl+V cuts out the clipboard picture", ["paste"] in pg.evaluate("window.__calls") and "pasted picture" in pg.inner_text("main"))
    expect("the earlier cut-out is in the strip", pg.locator("[data-recent]").count() == 2)

    # a dropped picture (the page reads the file and sends it to Python)
    pg.evaluate("""() => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array([137,80,78,71])], 'holiday.png', {type: 'image/png'}));
      window.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    }""")
    pg.wait_for_timeout(1500)
    expect("a dropped picture is sent to Python and cut out", any(c[0] == "data" and c[1] == "holiday.png" and c[2].startswith("data:image/png") for c in pg.evaluate("window.__calls")))
    pg.evaluate("""() => {
      const dt = new DataTransfer();
      dt.items.add(new File(['hi'], 'notes.txt', {type: 'text/plain'}));
      window.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    }""")
    pg.wait_for_timeout(300)
    expect("a dropped non-picture without a path is explained, not opened", "Pick a file" in pg.inner_text("#toast"))

    for look in ["glass", "glassdark"]:
        pg.evaluate("window.toolbelt.go('settings')")
        pg.click('[data-look="%s"]' % look)
        pg.wait_for_timeout(200)
        pg.evaluate("window.toolbelt.go('bg')")
        pg.wait_for_timeout(400)
        over = pg.evaluate("(() => { const m = document.querySelector('main'); return m.scrollWidth > m.clientWidth + 2; })()")
        expect(look + ": nothing sticks out sideways", not over)
        pg.screenshot(path=str(OUT / ("cutout_%s.png" % look)))
    expect("no script errors", errors == [])
    if errors:
        print("    " + "\n    ".join(errors[:10]))
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_cutout)")
