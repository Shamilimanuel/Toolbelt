"""The Uninstall and PC care screens in an invisible Chrome with a pretend Python side: the program list and its three
views, the right-click menu, the Revo-style flow (confirm with restore point → steps → scan mode → registry tree → files
tree, delete and delete as admin), Windows apps, the leftover hunt, Windows tools, startup switches, drivers with the
Windows Update question, and the ping tab (graph, table, verdict, adding a host)."""
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:/x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: '', calc_key: false};
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  let jobs = [], nextId = 1, tick = 0;
  const revo = {phase: 'idle', kind: '', polls: 0, steps: [], listed: null, scan: {progress: 0, message: '', mode: ''}};
  const progs = [
    {id: 'machine/Git', name: 'Git', version: '2.55.0', publisher: 'The Git Development Community', size: 350e6, date: '2026-08-22', uninstall: 'x', quiet: '', location: 'C:/Program Files/Git', icon: 'C:/Program Files/Git/git-bash.exe', icon_data: '', where: 'machine', msi: false,
     key: 'HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Git_is1', about: '', help: 'https://git-scm.com/', update: ''},
    {id: 'machine/ShareX', name: 'ShareX', version: '21.0', publisher: 'ShareX Team', size: 540e6, date: '2026-07-15', uninstall: 'x', quiet: '', location: '', icon: '', icon_data: '', where: 'machine', msi: false},
    {id: 'user/Discord', name: 'Discord', version: '1.0.9', publisher: 'Discord Inc.', size: 0, date: '', uninstall: 'x', quiet: '', location: '', icon: '', icon_data: '', where: 'user', msi: false}];
  const startup = [{id: 'HKCU/Run/Discord', name: 'Discord', command: 'C:/x/Update.exe --processStart', where: 'Registry (you)', enabled: true, canToggle: true, exe: '', icon_data: ''},
                   {id: 'HKLM/Run/SecurityHealth', name: 'SecurityHealth', command: 'C:/Windows/System32/SecurityHealthSystray.exe', where: 'Registry (all users)', enabled: true, canToggle: false, exe: '', icon_data: ''}];
  const drv = {board: {maker: 'Example Boards', model: 'EX-500 PRO', bios: '1234', biosDate: '2026-01-04', page: 'https://example.com/support/ex-500'},
    drivers: [{name: 'AMD Radeon RX 9060 XT', group: 'Graphics', version: '32.0.31041.1004', date: '2026-08-17', age: 59, provider: 'Advanced Micro Devices, Inc.', maker: 'AMD', page: 'https://www.amd.com/en/support/download/drivers.html', state: 'ok', why: '', signed: true, hardware: true, inf: 'oem1.inf'},
              {name: 'Realtek PCIe GbE', group: 'Network & Wi-Fi', version: '10.1', date: '2019-01-02', age: 2477, provider: 'Realtek', maker: 'Realtek', page: '', state: 'old', why: 'This driver is 6 years old.', signed: true, hardware: true, inf: 'oem2.inf'},
              {name: 'Virtual Audio', group: 'Sound', version: '1.0', date: '2021-10-14', age: 1460, provider: 'Nahimic', maker: 'Nahimic', page: '', state: 'ok', why: '', signed: true, hardware: false, inf: 'oem3.inf'}]};
  window.__apps = [{id: 'appx/EarTrumpet', name: 'EarTrumpet', package: '40459File-New-Project.EarTrumpet', full: 'x_2.3_x64__1sdd', family: '40459File-New-Project.EarTrumpet_1sdd', version: '2.3.0.0', publisher: 'File-New-Project', date: '', size: 0, appid: 'x!EarTrumpet', visible: true, care: '', careWhy: '', data: '', location: '', icon: '', icon_data: '', where: 'appx'},
    {id: 'appx/Python', name: 'Python install manager', package: 'PythonSoftwareFoundation.PythonManager', full: 'p', family: 'p', version: '26.4', publisher: 'Python Software Foundation', date: '', size: 0, appid: 'p!Py', visible: true, care: 'danger', careWhy: "Toolbelt's own Python comes from this. Removing it breaks Toolbelt.", data: '', location: '', icon: '', icon_data: '', where: 'appx'},
    {id: 'appx/HEVC', name: 'HEVC Video Extension', package: 'Microsoft.HEVCVideoExtension', full: 'h', family: 'h', version: '2.5', publisher: 'Microsoft Corporation', date: '', size: 0, appid: '', visible: false, care: 'info', careWhy: 'A codec.', data: '', location: '', icon: '', icon_data: '', where: 'appx'}];
  window.__calls = [];
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.12', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]), engines: () => ok({engines: [], total: 0, folder: ''}),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, message: '', settings}); },
    jobs: () => { jobs.forEach(j => { if (j.state === 'waiting') j.state = 'running'; else if (j.state === 'running') { j.state = 'done'; j.extra.updates = [{Title: 'Advanced Micro Devices - Display - 32.0.31050.1', Maker: 'AMD', Class: 'Display', Date: '2026-09-30', Size: 512e6}]; } }); return ok(jobs); },
    cancel_job: () => ok({ok: true}), clear_jobs: () => ok({ok: true}), check_updates: () => ok({}), clipboard_offer: () => ok(null), mail: () => ok([]), games: () => ok([]),
    pc_programs: () => { window.__calls.push(['programs']); return ok(progs); },
    pc_restore_point: () => { window.__calls.push(['restore_point']); return ok({ok: true, message: 'Restore point asked for.'}); },
    pc_run: (id) => { window.__calls.push(['run', id]); return ok({ok: true, message: 'Starting Git'}); },
    pc_open_location: (id) => { window.__calls.push(['where', id]); return ok({ok: true, message: 'Opened'}); },
    pc_program_action: (id, a) => { window.__calls.push(['action', id, a]); return ok({ok: true, message: 'Searching the web for Git'}); },
    pc_export_programs: (fmt) => { window.__calls.push(['export', fmt]); return ok({ok: true, message: 'Saved Installed programs.csv'}); },
    pc_open_backups: () => { window.__calls.push(['backups']); return ok({ok: true, message: 'Registry backups'}); },
    pc_tool: (w) => { window.__calls.push(['tool', w]); return ok({ok: true, message: ''}); },
    pc_restore_points: () => ok([{SequenceNumber: 1, Description: 'Toolbelt, before a change', When: '2026-10-15 09:00'}]),
    pc_store_apps: () => { window.__calls.push(['apps']); return ok(window.__apps); },
    // the Revo-style flow: a little state machine that moves on each time the page asks for the status
    pc_revo_begin: (kind, id, rp) => { window.__calls.push(['begin', kind, id, rp]); revo.kind = kind; revo.phase = 'working'; revo.polls = 0; revo.listed = null;
      revo.steps = (rp ? [{key: 'rp', text: 'Creating a System Restore Point', state: 'busy', note: ''}] : []).concat([{key: 'run', text: "Starting the program's own uninstaller", state: 'todo', note: ''}, {key: 'scan', text: 'After the uninstaller has finished, press Scan', state: 'todo', note: ''}]);
      return ok({ok: true}); },
    pc_revo_go_on: () => ok({ok: true}),
    pc_revo_status: () => { revo.polls++;
      if (revo.phase === 'working') { revo.steps.forEach(s => { if (s.key === 'rp') s.state = 'done'; if (s.key === 'run') s.state = revo.polls > 2 ? 'done' : 'busy'; }); if (revo.polls > 2) { revo.phase = 'uninstalled'; revo.listed = false; } }
      else if (revo.phase === 'scanning') { revo.scan.progress = Math.min(100, revo.scan.progress + 40); revo.scan.message = 'Its registry keys…'; if (revo.polls > 2) revo.phase = 'scanned'; }
      return ok({phase: revo.phase, label: 'x', kind: revo.kind, steps: revo.steps, error: '', running: revo.phase === 'working', listed: revo.listed, scan: revo.scan}); },
    pc_revo_scan: (mode) => { window.__calls.push(['scan', mode]); revo.phase = 'scanning'; revo.polls = 0; revo.scan = {progress: 0, message: 'Starting…', mode}; return ok({ok: true}); },
    pc_revo_hunt: (name, mode) => { window.__calls.push(['hunt', name, mode]); if (name.length < 3) return ok({ok: false, message: 'Type at least 3 letters of the name.'});
      revo.kind = 'hunt'; revo.phase = 'scanning'; revo.polls = 0; revo.scan = {progress: 0, message: 'Starting…', mode}; return ok({ok: true}); },
    pc_revo_cancel: () => ok({ok: true}),
    pc_revo_result: () => ok(revo.kind === 'hunt' ? {ok: true, label: 'roblox', mode: revo.scan.mode, removed: [], registry: [
        {id: 'r0', kind: 'key', hive: 'HKCU', path: 'Software\\ROBLOX Corporation', name: '', data: '', how: 'named like it', mode: 'safe', area: '', inUse: 'RobloxPlayerBeta still uses it', values: [], more: 3}],
        files: [{id: 'f0', kind: 'folder', path: 'C:\\Users\\you\\AppData\\Local\\Roblox Old', size: 10e6, how: 'named like it', mode: 'safe', area: '', inUse: ''}]}
      : {ok: true, label: 'Git', mode: revo.scan.mode, removed: [], registry: [
        {id: 'r0', kind: 'key', hive: 'HKCU', path: 'Software\\GitForWindows', name: '', data: '', how: 'named like it', mode: 'safe', area: '', inUse: '', values: [['CurrentVersion', '2.55.0']], more: 0, size: 2048},
        {id: 'r1', kind: 'value', hive: 'HKCU', path: 'Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Compatibility Assistant\\Store', name: 'C:\\Program Files\\Git\\git-bash.exe', data: '(28 bytes)', how: 'points into its folder', mode: 'advanced', area: 'windows', inUse: '', values: [], more: 0, size: 72},
        {id: 'r2', kind: 'key', hive: 'HKLM', path: 'Software\\GitForWindows', name: '', data: '', how: 'named like it', mode: 'safe', area: '', inUse: '', values: [], more: 2, size: 5000},
        {id: 'r3', kind: 'key', hive: 'HKCU', path: 'Software\\Classes\\git-shell', name: '', data: '', how: 'a file type or link it registered', mode: 'moderate', area: '', inUse: 'Git Extensions still uses it', values: [], more: 0, size: 300}],
        files: [{id: 'f0', kind: 'folder', path: 'C:\\Program Files\\Git', size: 12e6, how: 'its install folder', mode: 'safe', area: '', inUse: ''},
                {id: 'f1', kind: 'file', path: 'C:\\Users\\you\\AppData\\Local\\Temp\\git-setup.log', size: 300, how: 'temporary files', mode: 'moderate', area: '', inUse: ''}]}),
    pc_revo_delete: (ids, admin) => { window.__calls.push(['delete', ids, admin]);
      const admins = admin ? [] : ids.filter(i => i === 'r2' || i === 'f0');
      const sizes = {r0: 2048, r1: 72, r2: 5000, f0: 12e6, f1: 300};
      return ok({ok: !admins.length, done: ids.filter(i => admins.indexOf(i) < 0), failed: [], needAdmin: admins, backup: 'C:/b', freed: ids.filter(i => admins.indexOf(i) < 0).reduce((t, i) => t + (sizes[i] || 0), 0), message: (ids.length - admins.length) + ' removed' + (admins.length ? ', ' + admins.length + ' need admin' : '')}); },
    pc_revo_close: () => { window.__calls.push(['close']); revo.phase = 'idle'; return ok({ok: true}); },

    pc_startup: () => ok(startup),
    pc_set_startup: (id, on) => { window.__calls.push(['startup', id, on]); startup.forEach(s => { if (s.id === id) s.enabled = on; }); return ok({ok: true, message: on ? 'starts again' : 'no longer starts by itself'}); },
    pc_drivers: () => { window.__calls.push(['drivers']); return ok(drv); },
    pc_wu_drivers: () => { window.__calls.push(['wu']); jobs.unshift({id: nextId++, title: 'Driver updates', kind: 'PC care', progress: 0, state: 'waiting', message: '', result: null, extra: {action: 'wu'}}); return ok({ok: true, id: nextId - 1}); },
    pc_open_url: (which, url) => { window.__calls.push(['url', which, url || '']); return ok({ok: true, message: 'Opened'}); },
    ping_start: (hosts) => { window.__calls.push(['ping_start', hosts]); tick = 0; return ok({ok: true}); },
    ping_stop: () => { window.__calls.push(['ping_stop']); return ok({ok: true}); },
    ping_snapshot: () => { tick++; const mk = (name, ip, base) => ({name, host: ip, ip, now: base, avg: base, jitter: 1, lost: 0, count: tick, samples: Array.from({length: tick}, (_, i) => base + (i % 3))});
      const t = {router: mk('Your router', '192.168.1.1', 3), internet: mk('Internet (Cloudflare)', '1.1.1.1', 8), hypixel: mk('Hypixel', '172.65.197.160', 13)};
      return ok({running: true, targets: t, order: Object.keys(t), verdict: {level: tick >= 3 ? 'ok' : 'wait', text: tick >= 3 ? 'Your connection is fine.' : 'Measuring…'}, events: tick >= 3 ? [{at: '09:00', target: 'Hypixel', what: 'spike to 90 ms (usually 13)'}] : []}); },
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
  }};
})();
"""

page_file = OUT / "page_pc.html"
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

    # ---------- Uninstall: the list, its views, the right-click menu ----------
    pg.evaluate("window.toolbelt.go('unin')")
    pg.wait_for_selector(".utable tbody tr", timeout=5000)
    expect("Details view lists the programs with company, version, size, date", pg.locator(".utable tbody tr").count() == 3 and "The Git Development Community" in pg.inner_text(".utable") and "2026-08-22" in pg.inner_text(".utable"))
    pg.fill("#uQ", "share")
    pg.wait_for_timeout(100)
    expect("search narrows the list", pg.locator(".utable tbody tr").count() == 1)
    pg.fill("#uQ", "")
    pg.click('[data-uview="icons"]')
    expect("Icons view", pg.locator(".mgrid [data-prog]").count() == 3)
    pg.click('[data-uview="list"]')
    expect("List view", pg.locator(".list [data-prog]").count() == 3)
    pg.click('[data-uview="details"]')
    pg.click('tr[data-prog="machine/Git"]')
    pg.wait_for_selector("#uUn", timeout=3000)
    pg.click("#uRunIt")
    pg.click("#uWhere")
    pg.wait_for_timeout(100)
    expect("a picked program can be run and its folder opened", ["run", "machine/Git"] in calls(pg) and ["where", "machine/Git"] in calls(pg))
    pg.click('tr[data-prog="machine/Git"]', button="right")
    pg.wait_for_selector("#appMenu", timeout=2000)
    menu = pg.inner_text("#appMenu")
    expect("right-click: Revo's menu (uninstall, search online, links, install location, registry key, export)",
           all(w in menu for w in ("Uninstall", "Search online", "About link", "Install location", "registry key", "Export list")))
    expect("links the program doesn't have are greyed", pg.is_disabled('[data-pm="about"]') and pg.is_enabled('[data-pm="regedit"]'))
    pg.screenshot(path=str(OUT / "pc_menu.png"))
    pg.click('[data-pm="google"]')
    pg.click('tr[data-prog="machine/Git"]', button="right")
    pg.click('[data-pm="csv"]')
    pg.wait_for_timeout(150)
    expect("the menu searches online and exports the list", ["action", "machine/Git", "google"] in calls(pg) and ["export", "csv"] in calls(pg))

    # ---------- the Revo flow: confirm → steps → scan mode → registry tree → files tree ----------
    pg.click("#uUn")
    pg.wait_for_selector("#rvDim #rvGo", timeout=3000)
    box = pg.inner_text("#rvDim").lower()
    expect("it asks first, with size, version, date, company and the uninstall command", "are you sure you want to uninstall the selected program?" in box and "2.55.0" in box and "the git development community" in box)
    expect("'Make a System Restore Point' is ticked by default", pg.is_checked("#rvRp"))
    pg.screenshot(path=str(OUT / "pc_revo_confirm.png"))
    pg.click("#rvGo")
    pg.wait_for_selector("#rvScan:not([disabled])", timeout=5000)
    expect("restore point, then its own uninstaller", ["begin", "program", "machine/Git", True] in calls(pg) and pg.locator(".step.done").count() == 2)
    expect("it says Windows no longer lists it", "no longer lists Git" in pg.inner_text("#rvDim"))
    expect("three scan modes, the last one used is picked", pg.locator('input[name="rvMode"]').count() == 3 and pg.is_checked('input[name="rvMode"][value="moderate"]'))
    pg.check('input[name="rvMode"][value="advanced"]')
    pg.screenshot(path=str(OUT / "pc_revo_steps.png"))
    pg.click("#rvScan")
    pg.wait_for_selector(".rtree", timeout=6000)
    expect("Scan runs the mode he picked", ["scan", "advanced"] in calls(pg))
    tree = pg.inner_text(".rtree")
    expect("the registry tree, Revo-style: hives and the path down to each leftover", "HKEY_CURRENT_USER" in tree and "HKEY_LOCAL_MACHINE" in tree and "Compatibility Assistant" in tree)
    expect("found items are bold, the rest only shows where they are", pg.locator(".tn.found").count() == 4 and pg.locator(".tn").count() > 8)
    expect("a found key shows its values", "CurrentVersion - 2.55.0" in tree)
    expect("in use: greyed, can't be ticked; Windows-area items are marked", pg.locator(".tn.used input[disabled]").count() == 1 and "Windows area" in tree)
    expect("Delete waits until something is ticked", pg.is_disabled("#rvDel"))
    pg.check('[data-tk="hkey_current_user"]')
    expect("ticking a parent ticks the free leftovers under it (not the one in use)", "Delete (2 · 2.1 KB)" in pg.inner_text("#rvDel"))
    pg.click("#rvAll")
    expect("Select all ticks every free leftover", "Delete (3 · 7.0 KB)" in pg.inner_text("#rvDel") and "7.0 KB" in pg.inner_text("#rvSum"))
    pg.screenshot(path=str(OUT / "pc_revo_tree.png"))
    pg.click("#rvDel")
    pg.wait_for_selector("#rvDelYes", timeout=2000)
    expect("the last question says how much: Yes, delete 3 (7.0 KB)", "(7.0 KB)" in pg.inner_text("#rvDelYes"))
    pg.click("#rvDelYes")
    pg.wait_for_selector("#rvAdmin", timeout=3000)
    expect("Delete asks once more, then removes the ticked ones", ["delete", ["r0", "r1", "r2"], False] in calls(pg))
    expect("what needs admin is offered as one admin step", "1 item needs admin" in pg.inner_text("#rvDim"))
    pg.click("#rvAdmin")
    pg.wait_for_timeout(300)
    expect("it says how much was freed", "Freed so far: 7.0 KB" in pg.inner_text("#rvSum"))
    expect("…which asks Windows once for just those", ["delete", ["r2"], True] in calls(pg) and pg.locator(".tn.gone").count() == 3)
    pg.click("#rvNext")
    pg.wait_for_selector("text=Found leftover files and folders", timeout=2000)
    expect("then the files tree, with sizes (bytes, KB, MB) and the total found", "git-setup.log" in pg.inner_text(".rtree") and "11.4 MB" in pg.inner_text(".rtree") and "300 bytes" in pg.inner_text(".rtree") and "(11.4 MB)" in pg.inner_text("#rvDim"))
    pg.click("#rvAll")
    expect("ticking shows the total to delete", "11.4 MB" in pg.inner_text("#rvDel"))
    pg.screenshot(path=str(OUT / "pc_revo_files.png"))
    pg.click("#rvBack")
    expect("Back goes to the registry tree", "found leftover registry items" in pg.inner_text("#rvDim").lower())
    pg.click("#rvNext")
    pg.click("#rvFin")
    pg.wait_for_timeout(200)
    expect("Finish closes the dialog and reads the list again", pg.locator("#rvDim").count() == 0 and ["close"] in calls(pg))
    pg.click('[data-utab="tools"]')
    pg.wait_for_selector('[data-tool="devmgmt"]', timeout=3000)
    pg.click('[data-tool="devmgmt"]')
    pg.click("#uRps")
    pg.wait_for_timeout(200)
    expect("Windows tools open through Python; restore points list", ["tool", "devmgmt"] in calls(pg) and "before a change" in pg.inner_text("main"))
    pg.click("#uBk")
    pg.wait_for_timeout(100)
    expect("the registry backups folder is one click away", ["backups"] in calls(pg))

    # ---------- Windows apps ----------
    pg.click('[data-utab="apps"]')
    pg.wait_for_selector('[data-app="appx/EarTrumpet"]', timeout=4000)
    expect("Windows apps are listed; hidden parts (codecs) only on request", pg.locator("[data-app]").count() == 2 and "HEVC" not in pg.inner_text(".utable"))
    pg.click("#uHidden")
    pg.wait_for_timeout(100)
    expect("Show hidden parts adds the codec", "HEVC Video Extension" in pg.inner_text(".utable"))
    pg.click('[data-app="appx/Python"]')
    pg.wait_for_selector("#uAppUn", timeout=3000)
    expect("the Python install manager carries its warning", "breaks Toolbelt" in pg.inner_text("#uSel") and "keep" in pg.inner_text(".utable"))
    pg.click("#uAppUn")
    pg.wait_for_selector("#rvDim", timeout=3000)
    expect("…also in the remove box, with 'Are you sure?'", "breaks Toolbelt" in pg.inner_text("#rvDim") and "Are you sure?" in pg.inner_text("#rvDim"))
    pg.press("#rvDim", "Escape")
    pg.wait_for_timeout(100)
    expect("Escape closes the box before anything happens", pg.locator("#rvDim").count() == 0 and not any(c[0] == "begin" and c[2] == "appx/Python" for c in calls(pg)))
    pg.click('[data-app="appx/EarTrumpet"]')
    pg.click("#uAppUn")
    pg.wait_for_selector("#rvGo", timeout=3000)
    pg.uncheck("#rvRp")
    pg.click("#rvGo")
    pg.wait_for_selector("#rvScan:not([disabled])", timeout=5000)
    expect("Remove goes through the same steps, here without a restore point", ["begin", "app", "appx/EarTrumpet", False] in calls(pg))
    pg.click("#rvCancel")

    # ---------- Leftover hunt: by name, for programs that are already gone ----------
    pg.click('[data-utab="hunt"]')
    pg.wait_for_selector("#uHq", timeout=3000)
    pg.fill("#uHq", "ro")
    pg.click("#uHunt")
    pg.wait_for_timeout(200)
    expect("too short a name is explained", "3 letters" in pg.inner_text("#app"))
    pg.fill("#uHq", "roblox")
    pg.check('input[name="uMode"][value="safe"]')
    pg.press("#uHq", "Enter")
    pg.wait_for_selector(".rtree", timeout=6000)
    expect("the hunt scans by name in the chosen mode", ["hunt", "roblox", "safe"] in calls(pg))
    expect("what's still used is greyed and can't be ticked", pg.locator(".tn.used input[disabled]").count() == 1 and "RobloxPlayerBeta" in pg.inner_text(".rtree"))
    pg.screenshot(path=str(OUT / "pc_hunt.png"))
    pg.click("#rvNext")
    pg.click("#rvAll")
    pg.click("#rvDel")
    pg.click("#rvDelYes")
    pg.wait_for_timeout(300)
    expect("only the free, ticked ones are sent to be removed", ["delete", ["f0"], False] in calls(pg))
    pg.click("#rvFin")

    # ---------- PC care: startup ----------
    pg.evaluate("window.toolbelt.go('pc')")
    pg.wait_for_selector('[data-st="HKCU/Run/Discord"]', timeout=4000)
    expect("an all-users entry can't be switched here", pg.is_disabled('[data-st="HKLM/Run/SecurityHealth"]'))
    pg.click('[data-st="HKCU/Run/Discord"]')
    pg.wait_for_timeout(300)
    expect("switching Discord off goes through Python", ["startup", "HKCU/Run/Discord", False] in calls(pg))

    # ---------- drivers ----------
    pg.click('[data-pct="drv"]')
    pg.wait_for_selector("#drvWu", timeout=5000)
    expect("drivers grouped, the board with its BIOS, old ones flagged", "EX-500 PRO" in pg.inner_text("main") and "BIOS 1234" in pg.inner_text("main") and "6 years old" in pg.inner_text("main") and "graphics" in pg.inner_text("main").lower())
    pg.click('[data-dfilter="attention"]')
    pg.wait_for_timeout(100)
    expect("Needs attention shows only the old LAN driver", "Realtek PCIe GbE" in pg.inner_text("main") and "AMD Radeon RX 9060 XT</b>" not in pg.inner_html("main").split("Updates")[-1])
    pg.click('[data-dfilter="hardware"]')
    pg.wait_for_timeout(100)
    expect("Real devices hides the virtual one", "Virtual Audio" not in pg.inner_text("main"))
    pg.click("#drvBoard")
    pg.click('[data-maker="https://www.amd.com/en/support/download/drivers.html"]')
    pg.click("#drvWu")
    pg.wait_for_function("document.querySelector('main').innerText.includes('32.0.31050.1')", timeout=6000)
    c = calls(pg)
    expect("board page, AMD page and Windows Update all go through Python; the WU result is listed", ["url", "board", ""] in c and ["url", "maker", "https://www.amd.com/en/support/download/drivers.html"] in c and ["wu"] in c)
    pg.screenshot(path=str(OUT / "pc_drivers.png"))

    # ---------- ping ----------
    pg.click('[data-pct="ping"]')
    pg.wait_for_function("document.querySelector('#pingVerdict') && document.querySelector('#pingVerdict').innerText.includes('fine')", timeout=8000)
    expect("opening the tab starts pinging; table and verdict fill in", ["ping_start", []] in calls(pg) and pg.locator("#pingTable tbody tr").count() == 3 and "192.168.1.1" in pg.inner_text("#pingTable"))
    drawn = pg.evaluate("(function(){var c=document.querySelector('#pingG');var d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;var n=0;for(var i=0;i<d.length;i+=4){if(d[i]>200&&d[i+1]<120)n++;}return n;})()")
    expect("the graph draws the lines", drawn > 20)
    pg.fill("#pingHost", "https://play.example.net/")
    pg.click("#pingAdd")
    pg.wait_for_timeout(200)
    expect("adding a host restarts with it (the address cleaned up)", ["ping_start", ["play.example.net"]] in calls(pg) and "play.example.net" in pg.inner_text("main"))
    pg.screenshot(path=str(OUT / "pc_ping.png"))
    pg.click('[data-pct="drv"]')
    pg.wait_for_timeout(200)
    expect("leaving the tab stops the pinging", ["ping_stop"] in calls(pg))
    expect("nothing sticks out sideways", pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"))
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_pc)")
