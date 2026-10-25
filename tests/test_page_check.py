"""The Check a file screen in an invisible Chrome with a pretend Python side: fingerprints + paste, signatures, compare,
a folder's list, what-is-it-really, a dropped file, and the command door (run check / run cutout from outside)."""
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: '', calc_key: false};
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  const exe = {token: 'f1', name: 'some-installer.exe', kind: 'other', size: 84e6, duration: 0, width: 0, height: 0, fps: 0, vcodec: '', acodec: '', frames: 0, thumb: ''};
  const zip = {token: 'f2', name: 'modpack-v2 (1).zip', kind: 'other', size: 412e6, duration: 0, width: 0, height: 0, fps: 0, vcodec: '', acodec: '', frames: 0, thumb: ''};
  const H = {md5: '5d41402abc4b2a76b9719d911017c592', sha1: 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d', sha256: '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824', sha512: '9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043'};
  let jobs = [], nextId = 1, mail = [];
  window.__calls = []; window.__mail = (m) => mail.push(m); window.__next = exe;
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.9', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]), engines: () => ok({engines: [], total: 0, folder: ''}),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, message: '', settings}); },
    jobs: () => { jobs.forEach(j => { if (j.state === 'waiting') j.state = 'running'; else if (j.state === 'running') { j.progress += 50; if (j.progress >= 100) { j.state = 'done'; if (j.extra.action === 'hash') Object.assign(j.extra, H); if (j.extra.action === 'compare') Object.assign(j.extra, {same: true, why: 'Same size and the same SHA-256 fingerprint: you can safely delete one.'}); if (j.extra.action === 'folder-make') Object.assign(j.extra, {path: 'E:\\Backups\\PrimalMines.sha256', files: 1204, bytes: 6.8e9}); if (j.extra.action === 'folder-verify') Object.assign(j.extra, {checked: 1204, changed: ['world/level.dat'], missing: [], new: ['new.txt'], ok: false}); } } }); return ok(jobs); },
    cancel_job: () => ok({ok: true}), clear_jobs: () => ok({ok: true}), check_updates: () => ok({}), clipboard_offer: () => ok(null), games: () => ok([]),
    mail: () => { const m = mail; mail = []; return ok(m); },
    check_pick: (what) => { window.__calls.push(['pick', what]); return ok(what === 'folder' ? {ok: true, folder: 'E:\\Backups\\PrimalMines', name: 'PrimalMines', files: 1204, list: false} : {ok: true, file: window.__next}); },
    media_drop: (p) => { window.__calls.push(['drop', p]); return ok({ok: true, file: window.__next}); },
    check_hash: (t) => { window.__calls.push(['hash', t]); jobs.unshift({id: nextId++, title: 'Fingerprints', kind: 'Check', progress: 0, state: 'waiting', message: '', result: null, extra: {action: 'hash', token: t}}); return ok({ok: true, id: nextId - 1}); },
    check_match: (found, pasted) => { const code = pasted.toLowerCase().replace(/[^0-9a-f]/g, ''); const algo = {32: 'md5', 40: 'sha1', 64: 'sha256', 128: 'sha512'}[code.length]; if (!code) return ok({ok: false, algo: '', message: 'Paste a fingerprint first.'}); if (!algo) return ok({ok: false, algo: '', message: "That's " + code.length + ' characters: not an MD5 (32), SHA-1 (40), SHA-256 (64) or SHA-512 (128).'}); const same = found[algo] === code; return ok({ok: same, algo, message: same ? 'The SHA-256 fingerprint matches: the file is exactly what the site published.' : 'The SHA-256 fingerprint is DIFFERENT. Don\'t run it, download it again.'}); },
    check_sign: (t) => { window.__calls.push(['sign', t]); return ok({ok: true, status: 'Valid', level: 'ok', title: 'Signed by Example Software Ltd', why: "The signature is valid and the file hasn't been changed since.", signer: 'Example Software Ltd', issuer: 'Example Trust CA', from: '2026-10-02', until: '2028-03-01', timestamp: 'Example Timestamp'}); },
    check_sniff: (t) => { window.__calls.push(['sniff', t]); return ok({ok: true, name: 'some-installer.exe', ext: '.exe', real: 'Windows program (EXE / DLL)', want: '.exe', verdict: 'ok', advice: '', size: 84e6}); },
    check_compare: (a, b) => { window.__calls.push(['compare', a, b]); jobs.unshift({id: nextId++, title: 'Compare', kind: 'Check', progress: 0, state: 'waiting', message: '', result: null, extra: {action: 'compare'}}); return ok({ok: true, id: nextId - 1}); },
    check_folder: (f, what) => { window.__calls.push(['folder', f, what]); jobs.unshift({id: nextId++, title: 'Folder', kind: 'Check', progress: 0, state: 'waiting', message: '', result: null, extra: {action: 'folder-' + what, folder: f}}); return ok({ok: true, id: nextId - 1}); },
    copy_text: (t) => { window.__calls.push(['copy', t]); return ok({ok: true, message: 'Copied'}); },
    cut_token: (t) => { window.__calls.push(['cut', t]); return ok({ok: false, message: 'no model in the test'}); },
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
  }};
})();
"""

page_file = OUT / "page_check.html"
page_file.write_text(build_page(), encoding="utf-8")


def calls(pg):
    return pg.evaluate("window.__calls")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1320, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    pg.evaluate("window.toolbelt.go('check')")
    pg.wait_for_selector("#ckPick", timeout=5000)
    expect("Check a file is a real screen now, with its five tabs", pg.locator("[data-chk]").count() == 5 and "step 8" not in pg.inner_text("main"))

    # fingerprints
    pg.click("#ckPick")
    pg.wait_for_function("document.querySelectorAll('.hashrow').length === 4", timeout=6000)
    expect("picking a file lists the four fingerprints", "2cf24dba" in pg.inner_text(".hashrow:nth-child(3)") and ["hash", "f1"] in calls(pg))
    pg.fill("#ckPaste", " 2CF24DBA5FB0A30E26E83B2AC5B9E29E1B161E5C1FA7425E73043362938B9824 ")
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('Matches')", timeout=4000)
    expect("a pasted SHA-256 matches and lights that row", pg.locator(".hashrow.hit").count() == 1)
    pg.fill("#ckPaste", "0000000000000000000000000000000000000000000000000000000000000000")
    pg.wait_for_function("document.querySelector('.verdict').innerText.includes('NOT')", timeout=4000)
    expect("a wrong one says NOT match", "download it again" in pg.inner_text(".verdict"))
    pg.click('[data-ckcopy]')
    pg.wait_for_timeout(100)
    expect("Copy sends the fingerprint through Python", any(c[0] == "copy" and c[1] == "5d41402abc4b2a76b9719d911017c592" for c in calls(pg)))
    pg.screenshot(path=str(OUT / "check_hash.png"))

    # signed by
    pg.click('[data-chk="sign"]')
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('Signed by')", timeout=4000)
    expect("the signature verdict with signer, issuer and validity", "Example Software Ltd" in pg.inner_text(".kv") and "Example Trust CA" in pg.inner_text(".kv") and "2028-03-01" in pg.inner_text(".kv"))

    # what is it really
    pg.click('[data-chk="what"]')
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('Really a')", timeout=4000)
    expect("what-is-it-really reads the first bytes", "Windows program" in pg.inner_text(".verdict") and ["sniff", "f1"] in calls(pg))

    # compare two: the second file comes by dropping it
    pg.click('[data-chk="compare"]')
    pg.wait_for_selector("#ckPickOther", timeout=4000)
    pg.evaluate("window.__next = {token: 'f2', name: 'modpack-v2 (1).zip', kind: 'other', size: 412e6, duration: 0, width: 0, height: 0, fps: 0, vcodec: '', acodec: '', frames: 0, thumb: ''}")
    pg.evaluate("(function(){var dt=new DataTransfer();var f=new File(['x'],'modpack-v2 (1).zip');Object.defineProperty(f,'pywebviewFullPath',{value:'D:\\\\modpack-v2 (1).zip'});dt.items.add(f);window.dispatchEvent(new DragEvent('drop',{dataTransfer:dt}));})()")
    pg.wait_for_selector("#ckCompare", timeout=4000)
    expect("dropping on Compare fills the second slot", "modpack-v2 (1).zip" in pg.inner_text("main") and any(c[0] == "drop" for c in calls(pg)))
    pg.click("#ckCompare")
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('Identical')", timeout=6000)
    expect("Compare runs as a job and says Identical", ["compare", "f1", "f2"] in calls(pg) and "safely delete" in pg.inner_text(".verdict"))

    # whole folder
    pg.click('[data-chk="folder"]')
    pg.wait_for_selector("#ckFolder", timeout=4000)
    pg.click("#ckFolder")
    pg.wait_for_selector("#ckMake", timeout=4000)
    expect("a folder is picked; Check is off until a list exists", "1204 files" in pg.inner_text("main") and pg.is_disabled("#ckVerify"))
    pg.click("#ckMake")
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('List saved')", timeout=6000)
    expect("the list is made, and Check becomes possible", "PrimalMines.sha256" in pg.inner_text(".verdict") and pg.is_enabled("#ckVerify"))
    pg.click("#ckVerify")
    pg.wait_for_function("document.querySelector('.verdict') && document.querySelector('.verdict').innerText.includes('problem')", timeout=6000)
    expect("verifying lists the changed and the new files", "world/level.dat" in pg.inner_text("main") and "new.txt" in pg.inner_text("main"))
    pg.screenshot(path=str(OUT / "check_folder.png"))

    # the command door: a file handed over from outside
    pg.evaluate("window.__mail({run: 'check', token: 'f1', file: {token: 'f1', name: 'handed.exe', kind: 'other', size: 10, thumb: ''}})")
    pg.wait_for_function("window.toolbelt.state().screen === 'check' && document.querySelector('main').innerText.includes('handed.exe')", timeout=5000)
    expect("run check <file> opens Check a file with that file", True)
    pg.evaluate("window.__mail({run: 'cutout', token: 'f1', file: {token: 'f1', name: 'cat.png', kind: 'picture', size: 10, thumb: ''}})")
    pg.wait_for_function("window.toolbelt.state().screen === 'bg'", timeout=5000)
    pg.wait_for_timeout(200)
    expect("run cutout <file> opens Cut out with that file", ["cut", "f1"] in calls(pg))
    expect("nothing sticks out sideways", pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"))
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_check)")
