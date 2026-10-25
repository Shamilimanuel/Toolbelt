"""The finishing tools on the page, in an invisible Chrome with a pretend Python side: Handy tools (QR code, colour
picker, rename files, checksum), the new Media tabs (crop, many pictures, sound), Fix all songs, the
Wallpaper Engine picker and the subtitles setting. Screenshots land in tests\\out."""
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\Users\\you\\Downloads\\Toolbelt', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: '', dl_subs: 'off'};
  const SVG = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21"><rect width="7" height="7" fill="#000"/></svg>');
  const c = document.createElement('canvas'); c.width = 400; c.height = 300; const x = c.getContext('2d'); x.fillStyle = '#3a6'; x.fillRect(0, 0, 400, 300);
  const PIC = c.toDataURL('image/png');
  const WAV = (() => { const n = 800, b = new DataView(new ArrayBuffer(44 + n)), w = (o, t) => [...t].forEach((ch, i) => b.setUint8(o + i, ch.charCodeAt(0)));
    w(0, 'RIFF'); b.setUint32(4, 36 + n, true); w(8, 'WAVEfmt '); b.setUint32(16, 16, true); b.setUint16(20, 1, true); b.setUint16(22, 1, true); b.setUint32(24, 8000, true); b.setUint32(28, 8000, true); b.setUint16(32, 1, true); b.setUint16(34, 8, true); w(36, 'data'); b.setUint32(40, n, true);
    for (let i = 0; i < n; i++) b.setUint8(44 + i, 128);
    return 'data:audio/wav;base64,' + btoa(String.fromCharCode(...new Uint8Array(b.buffer)));
  })();  // a tenth of a second of silence for the song player
  const pic = {token: 'p1', name: 'holiday.jpg', kind: 'picture', size: 4.1e6, duration: 0, width: 4000, height: 3000, fps: 0, vcodec: '', acodec: '', frames: 1, thumb: PIC};
  const song = {token: 's1', name: 'song.mp3', kind: 'audio', size: 7e6, duration: 207, width: 0, height: 0, fps: 0, vcodec: '', acodec: 'mp3', frames: 0, thumb: ''};
  const video = {token: 'v1', name: 'clip.mp4', kind: 'video', size: 48e6, duration: 60, width: 1920, height: 1080, fps: 60, vcodec: 'h264', acodec: 'aac', frames: 3600, thumb: PIC};
  let jobs = [], nextId = 1, whisper = false, renamePlan = null;
  window.__calls = [];
  const push = window.__calls.push.bind(window.__calls);
  window.__calls.push = (c) => push(JSON.parse(JSON.stringify(c)));     // what Python would get: a copy, like pywebview sends
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  const addJob = (title, kind, extra, result) => { jobs.unshift({id: nextId++, title, kind, progress: 0, state: 'waiting', message: '', result: null, extra: extra || {}, __result: result}); return nextId - 1; };
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '1.0', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]),
    set_setting: (k, v) => { settings[k] = v; window.__calls.push(['set', k, v]); return ok({ok: true, message: '', settings}); },
    engines: () => ok({engines: [{id: 'ffmpeg', name: 'ffmpeg', what: '', licence: '', approx: '', installed: true, size: 1, version: '9', step: 2},
      {id: 'whisper', name: 'whisper.cpp', what: 'speech to text', licence: 'MIT', approx: '~70 MB', installed: whisper, size: 0, version: '', step: 10},
      {id: 'whispermodel', name: 'Whisper model', what: '', licence: 'MIT', approx: '~575 MB', installed: whisper, size: 0, version: '', step: 10}], total: 1, folder: 'C:\\e'}),
    jobs: () => { jobs.forEach(j => { if (j.state === 'waiting') j.state = 'running'; else if (j.state === 'running') { j.progress += 50; j.message = 'working'; if (j.progress >= 100) { j.state = 'done'; j.result = j.__result || null; j.message = 'finished'; } } }); return ok(jobs.map(j => { const c = Object.assign({}, j); delete c.__result; return c; })); },
    cancel_job: (id) => { window.__calls.push(['cancel', id]); return ok({ok: true}); }, clear_jobs: () => ok({ok: true}), check_updates: () => ok({}), clipboard_offer: () => ok(null), mail: () => ok([]), games: () => ok([]),
    install_engines: (ids) => { window.__calls.push(['install', ids]); whisper = true; addJob('Install whisper.cpp', 'Engine', {engine: 'whisper'}); return ok({ok: true, message: 'Installing 2 engines'}); },
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}), show_file: (p) => ok({ok: true}), copy_text: (t) => { window.__calls.push(['copy', t]); return ok({ok: true}); },
    media_pick: () => ok({ok: true, file: window.__next || pic}), media_info: () => ok({ok: true, file: pic}),
    media_clips: () => ok([]), media_clip_thumb: () => ok({ok: true, thumb: ''}),
    media_picture_preview: () => ok({ok: true, size: 380000, preview: PIC, before: PIC, original: 4.1e6}),
    media_url: (t) => ok({ok: true, url: WAV}),
    media_job: (t, action, o) => { window.__calls.push(['job', action, o]); addJob(action, 'Media', {action, path: 'C:\\x\\out', size: 1e6}); return ok({ok: true, id: nextId - 1}); },
    media_pick_many: (what) => ok({ok: true, items: [{token: 'b1', name: 'a.jpg', size: 2e6}, {token: 'b2', name: 'b.heic', size: 3e6}, {token: 'b3', name: 'c.png', size: 1e6}].slice(0, what === 'folder' ? 3 : 2)}),
    media_batch_thumb: () => ok(PIC),
    media_batch: (tokens, action, o) => { window.__calls.push(['batch', tokens, action, o]); addJob('Converted · 3 pictures', 'Media', {action: 'batch', path: 'C:\\x\\a.webp', count: tokens.length, before: 6e6, size: 2e6, failed: []}); return ok({ok: true, id: nextId - 1}); },
    qr_preview: (kind, v, level, dark, light) => { window.__calls.push(['qr', kind, v, level, dark, light]); return ok({ok: true, svg: SVG, version: 2, modules: 25, size: 900, readable: dark !== '#FFFFFF'}); },
    qr_save: (...a) => { window.__calls.push(['qrsave', a[5]]); return ok({ok: true, path: 'C:\\x\\QR - code.png', message: 'Saved QR - code.png'}); },
    qr_copy: () => { window.__calls.push(['qrcopy']); return ok({ok: true, message: 'Copied'}); },
    rename_pick: (what) => ok({ok: true, count: 3}),
    rename_order: (how) => { window.__calls.push(['order', how]); return ok({ok: true}); },
    rename_plan: (rules) => { window.__calls.push(['plan', rules]); const names = ['IMG_1.JPG', 'IMG_2.JPG', 'IMG_3.JPG']; renamePlan = names.map((n, i) => ({old: n, new: rules.base ? rules.base + (rules.number !== 'off' ? ' ' + String(rules.start + i).padStart(rules.digits, '0') : '') + '.JPG' : n, problem: rules.base && rules.number === 'off' && i > 0 ? 'same name as IMG_1.JPG' : ''}));
      return ok({ok: true, items: renamePlan, count: 3, changes: renamePlan.filter(x => x.old !== x.new && !x.problem).length, problems: renamePlan.filter(x => x.problem).length, folder: 'E:\\Photos', undo: window.__undo || 0}); },
    rename_apply: (rules) => { window.__calls.push(['apply', rules]); window.__undo = 3; return ok({ok: true, message: 'Renamed 3 files.', renamed: []}); },
    rename_undo: () => { window.__calls.push(['undo']); window.__undo = 0; return ok({ok: true, message: 'Put 3 names back.'}); },
    songs: () => ok({folder: 'C:\\Music', songs: [{path: 'C:\\Music\\a.mp3', name: 'a.mp3', title: 'め組のひと / 宝鐘マリン cover', artist: 'Marine Ch.', album: '', cover: true, square: true, lyrics: false, seconds: 207}]}),
    songs_fix_all: () => { window.__calls.push(['fixall']); return ok({ok: true, job: addJob('Fix all songs for lyrics', 'Songs', {}, [
      {path: 'C:\\Music\\a.mp3', name: 'a.mp3', current: {title: 'め組のひと / 宝鐘マリン cover', artist: 'Marine Ch.', album: ''}, proposed: {title: 'め組のひと', artist: '宝鐘マリン', album: 'め組のひと'}, status: 'clean', synced: true},
      {path: 'C:\\Music\\b.mp3', name: 'b.mp3', current: {title: 'Known', artist: 'Someone', album: 'A'}, proposed: {title: 'Known', artist: 'Someone', album: 'A'}, status: 'already', synced: false},
      {path: 'C:\\Music\\c.mp3', name: 'c.mp3', current: {title: 'Weird [MV]', artist: 'X', album: ''}, proposed: {title: 'Weird', artist: 'X', album: 'Weird'}, status: 'none', synced: false}])}); },
    songs_fix_apply: (items, lyrics) => { window.__calls.push(['fixapply', items, lyrics]); return ok({ok: true, job: addJob('Save fixed song tags', 'Songs', {})}); },
    wallpapers: () => ok({ok: true, items: [{id: '111', title: 'Sakura video', type: 'video', kind: 'video', size: 140e6, tags: []}, {id: '222', title: 'Rain scene', type: 'scene', kind: 'gif', size: 2e6, tags: []}]}),
    wallpaper_thumb: () => ok(PIC),
    game_wallpaper: (key, which, id) => { window.__calls.push(['wallpaper', key, which, id]); return ok(id === '111' ? {ok: true, job: addJob('Background from Sakura', 'Wallpaper', {}), message: 'Making a background-sized copy'} : {ok: true, message: 'Saved the new background.'}); },
  }};
  window.__setFile = (w) => { window.__next = {pic, song, video}[w]; };
})();
"""

page_file = OUT / "page_finish.html"
page_file.write_text(build_page(), encoding="utf-8")


def calls(pg, name):
    return pg.evaluate("window.__calls.filter(c => c[0] === %r)" % name)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    pg = browser.new_page(viewport={"width": 1320, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)

    # ---------- Handy tools ----------
    pg.evaluate("window.toolbelt.go('tools')")
    expect("Handy tools is in the sidebar", "Handy tools" in pg.inner_text("#side"))
    expect("four tabs: QR code, Colour picker, Rename files, Checksum", pg.locator("[data-ttab]").count() == 4)
    pg.fill("#qrText", "https://example.com")
    pg.wait_for_selector("#qrPrev img", timeout=3000)
    expect("QR: typing a link shows the code", "25 × 25" in pg.inner_text("#qrInfo") and not pg.is_disabled("#qrPng"))
    pg.click('[data-qk="wifi"]')
    pg.fill("#qrSsid", "Home")
    pg.fill("#qrPass", "secret")
    pg.click('[data-qlevel="h"]')
    pg.wait_for_timeout(400)
    last = calls(pg, "qr")[-1]
    expect("QR: Wi-Fi with name, password and the 30% level", last[1] == "wifi" and last[2]["ssid"] == "Home" and last[2]["password"] == "secret" and last[3] == "h")
    pg.click("#qrClear")
    pg.wait_for_timeout(400)
    expect("QR: see-through sends no background colour", calls(pg, "qr")[-1][5] == "")
    pg.click("#qrSvg")
    pg.click("#qrCopy")
    pg.wait_for_timeout(200)
    expect("QR: Save SVG and Copy reach Python", calls(pg, "qrsave")[-1][1] == "svg" and len(calls(pg, "qrcopy")) == 1)
    pg.screenshot(path=str(OUT / "finish_qr.png"))
    pg.click('[data-ttab="pick"]')
    has = pg.evaluate("!!window.EyeDropper")
    expect("Colour picker: the screen picker button (EyeDropper %s here)" % ("exists" if has else "missing"), pg.locator("#pkGo").count() == 1)
    pg.evaluate("window.EyeDropper = function () { this.open = () => Promise.resolve({sRGBHex: '#ff5c8a'}); }; window.toolbelt.go('tools', true)")
    pg.click("#pkGo")
    pg.wait_for_selector(".pkswatch", timeout=3000)
    codes = pg.inner_text(".list")
    expect("Colour picker: a picked colour in every format", "#FF5C8A" in codes and "rgb(255, 92, 138)" in codes and "&#FF5C8A" in codes and "16735370" in codes)
    pg.click('[data-pkcopy="1"]')
    pg.wait_for_timeout(150)
    expect("Colour picker: Copy copies that code", calls(pg, "copy")[-1][1] == "rgb(255, 92, 138)")
    expect("Colour picker: remembered under Picked before", pg.locator('[data-pkold="#FF5C8A"]').count() == 1)
    pg.click("#pkCol")
    expect("Colour picker: Open in Colours goes to Colour codes with it", pg.evaluate("document.querySelector('#hxIn') && document.querySelector('#hxIn').value") == "#FF5C8A")
    pg.evaluate("window.toolbelt.go('tools')")
    pg.click('[data-ttab="rename"]')
    pg.click("#rnFolder")
    pg.wait_for_selector("#rnList .item", timeout=3000)
    expect("Rename: three files, before → after", pg.locator("#rnList .item").count() == 3 and "E:\\Photos" in pg.inner_text("main"))
    pg.fill('[data-rule="base"]', "Texel")
    pg.wait_for_timeout(500)
    expect("Rename: a name for all without numbers shows the problem", "problem" in pg.inner_text("#rnSum") and pg.is_disabled("#rnGo") is False)
    pg.click('[data-rnum="after"]')
    pg.wait_for_timeout(400)
    expect("Rename: with numbers the preview fits", "Texel 01.JPG" in pg.inner_text("#rnList") and "problem" not in pg.inner_text("#rnSum"))
    expect("Rename: typing keeps the focus in the box", pg.evaluate("document.activeElement && document.activeElement.getAttribute('data-rule')") in (None, "base"))
    pg.click('[data-rorder="date"]')
    pg.wait_for_timeout(300)
    expect("Rename: numbering order by date reaches Python", calls(pg, "order")[-1][1] == "date")
    pg.screenshot(path=str(OUT / "finish_rename.png"))
    pg.click("#rnGo")
    pg.wait_for_selector("#rnUndo", timeout=3000)
    expect("Rename: Rename sends the rules, then Undo appears", calls(pg, "apply")[-1][1]["base"] == "Texel")
    pg.click("#rnUndo")
    pg.wait_for_timeout(300)
    expect("Rename: Undo reaches Python", len(calls(pg, "undo")) == 1)
    pg.click('[data-ttab="sum"]')
    pg.click('[data-go="check"]')
    expect("Checksum: leads to Check a file", pg.evaluate("window.toolbelt.state().screen") == "check")

    # ---------- Media: crop ----------
    pg.evaluate("window.__setFile('pic'); window.toolbelt.go('media')")
    pg.click("#mdPick")
    pg.wait_for_selector('[data-mtab="crop"]', timeout=3000)
    pg.click('[data-mtab="crop"]')
    pg.wait_for_selector("#mdCropImg", timeout=3000)
    pg.wait_for_function("!document.querySelector('#mdCropRect').hidden", timeout=3000)
    expect("Crop: starts with the whole picture", "4000 × 3000" in pg.inner_text("#mdCropTxt"))
    pg.click('[data-ratio="1:1"]')
    pg.wait_for_function("!document.querySelector('#mdCropRect').hidden", timeout=3000)
    expect("Crop: Square gives the biggest square in the middle", "3000 × 3000 pixels kept" in pg.inner_text("#mdCropTxt"))
    box = pg.locator("#mdCropImg").bounding_box()
    pg.mouse.move(box["x"] + 10, box["y"] + 10)
    pg.mouse.down()
    pg.mouse.move(box["x"] + 60, box["y"] + 30, steps=4)
    pg.mouse.up()
    w = int(pg.inner_text("#mdCropTxt").split(" × ")[0])
    expect("Crop: drawing keeps the square shape", "%d × %d" % (w, w) in pg.inner_text("#mdCropTxt") and 400 < w < 600)
    rect = pg.locator("#mdCropRect").bounding_box()
    pg.mouse.move(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(rect["x"] + rect["width"] / 2 + 3000, rect["y"] + rect["height"] / 2, steps=3)
    pg.mouse.up()
    pg.click("#mdCropGo")
    pg.wait_for_timeout(200)
    b = calls(pg, "job")[-1][2]["box"]
    expect("Crop: moved to the right edge, the box goes to Python in the picture's own pixels", b["w"] == b["h"] and b["x"] + b["w"] == 4000)
    pg.screenshot(path=str(OUT / "finish_crop.png"))
    # ---------- Media: many pictures ----------
    pg.click('[data-mtab="batch"]')
    pg.click("#mbFolder")
    pg.wait_for_selector(".mbitem", timeout=3000)
    expect("Many pictures: a folder of 3 with thumbnails", pg.locator(".mbitem").count() == 3)
    pg.click('[data-mbx="1"]')
    pg.click("#mbFiles")
    pg.wait_for_timeout(200)
    expect("Many pictures: leave one out, add more without doubles", pg.locator(".mbitem").count() == 3)
    pg.click('[data-bact="format"]')
    pg.click('[data-pfmt="webp"]')
    pg.click("#mbGo")
    pg.wait_for_timeout(200)
    c = calls(pg, "batch")[-1]
    expect("Many pictures: Convert to WebP for all three", c[2] == "format" and c[3]["fmt"] == "webp" and len(c[1]) == 3)
    pg.click('[data-bact="crop"]')
    pg.click('[data-bratio="16:9"]')
    pg.click("#mbGo")
    pg.wait_for_timeout(200)
    expect("Many pictures: crop to 16:9", calls(pg, "batch")[-1][3] == {"ratio": "16:9"})
    pg.wait_for_function("document.querySelector('#mdDone') && document.querySelector('#mdDone').innerText.indexOf('3 pictures') !== -1", timeout=5000)
    expect("Many pictures: the result says how many and the sizes", "→" in pg.inner_text("#mdDone"))
    pg.screenshot(path=str(OUT / "finish_batch.png"))
    # ---------- Media: sound ----------
    pg.evaluate("window.__setFile('song')")
    pg.click("#mdPick")
    pg.wait_for_selector('[data-smode="cut"]', timeout=3000)
    expect("Sound: a song opens on the Sound tab with a player", pg.evaluate("window.toolbelt.state().screen") == "media" and pg.locator("#mdAudio").count() == 1)
    pg.evaluate("(function(){var f=document.querySelector('#mdFrom');f.value=100;f.dispatchEvent(new Event('input'));f.dispatchEvent(new Event('change'));var t=document.querySelector('#mdTo');t.value=400;t.dispatchEvent(new Event('input'));t.dispatchEvent(new Event('change'));})()")
    pg.click('[data-fout="3"]')
    pg.click("#mdCutSound")
    pg.wait_for_timeout(200)
    o = calls(pg, "job")[-1]
    expect("Sound: cut 10 s → 40 s with a 3 s fade-out", o[1] == "cutsound" and o[2]["start"] == 10 and o[2]["end"] == 40 and o[2]["fade_out"] == 3)
    pg.click('[data-smode="loud"]')
    pg.click('[data-loud="podcast"]')
    pg.click("#mdLoud")
    pg.wait_for_timeout(200)
    expect("Sound: even out to the podcast level", calls(pg, "job")[-1][1:] == ["normalise", {"target": "podcast"}])
    # ---------- Media: Subtitles is hidden (his wish, 15 Oct) ----------
    pg.evaluate("window.__setFile('video')")
    pg.click("#mdPick")
    pg.wait_for_selector('[data-mtab="sound"]', timeout=3000)
    expect("Subtitles is gone from Media's tabs and a video's suggestions", pg.locator('[data-mtab="subs"]').count() == 0 and pg.locator('[data-sugg="subs"]').count() == 0)

    # ---------- Fix all songs ----------
    pg.evaluate("window.toolbelt.go('video')")
    pg.evaluate("window.toolbelt.openFixAll()")
    pg.wait_for_selector(".fixlist", timeout=6000)
    rows = pg.locator(".fixlist .item")
    expect("Fix all: three songs, each with what it found", rows.count() == 3 and "found after a clean-up" in pg.inner_text(".fixlist") and "fix by hand" in pg.inner_text(".fixlist"))
    expect("Fix all: the found one is ticked, the unknown one isn't", pg.is_checked('[data-fx="0"]') and not pg.is_checked('[data-fx="2"]') and pg.locator('[data-fx="1"]').count() == 0)
    pg.screenshot(path=str(OUT / "finish_fixall.png"))
    pg.click("#fxSave")
    pg.wait_for_timeout(300)
    fa = calls(pg, "fixapply")[-1]
    expect("Fix all: Save sends only the ticked song with its new tags (and lyrics on)", len(fa[1]) == 1 and fa[1][0]["title"] == "め組のひと" and fa[2] is True)
    pg.wait_for_function("!document.querySelector('.fixlist')", timeout=5000)
    expect("Fix all: the dialog closes when saved", True)

    # ---------- Wallpaper Engine ----------
    pg.evaluate("window.toolbelt.openWallpapers({key: 'genshin', name: 'Genshin Impact'}, 'banner')")
    pg.wait_for_selector(".wpcard", timeout=4000)
    expect("Wallpaper Engine: the picker lists them with thumbnails", pg.locator(".wpcard").count() == 2 and "Sakura video" in pg.inner_text(".wpgrid"))
    pg.click('[data-wpk="video"]')
    expect("Wallpaper Engine: Videos filter", pg.locator(".wpcard").count() == 1)
    pg.click('[data-wpk="all"]')
    pg.fill("#wpQ", "rain")
    expect("Wallpaper Engine: search", pg.locator(".wpcard").count() == 1)
    pg.screenshot(path=str(OUT / "finish_wallpaper.png"))
    pg.fill("#wpQ", "")
    pg.click('[data-wp="111"]')
    pg.wait_for_timeout(300)
    expect("Wallpaper Engine: a big video starts a copy job for this game's backgrounds", calls(pg, "wallpaper")[-1][1:] == ["genshin", "banner", "111"] and pg.locator(".wpgrid").count() == 0)

    # ---------- the subtitles setting ----------
    pg.evaluate("window.toolbelt.go('settings')")
    pg.click("text=Downloads")
    pg.click('[data-dsubs="auto"]')
    pg.wait_for_timeout(200)
    expect("Settings: subtitles with videos", ["set", "dl_subs", "auto"] in pg.evaluate("window.__calls"))
    # every screen still opens, in the three looks
    for look in ("cartridge", "glass", "glassdark"):
        pg.evaluate("window.pywebview.api.set_setting('look', %r)" % look)
        r = pg.evaluate("window.toolbelt.walkScreens()")
        expect("every screen opens in %s (%d)" % (look, r["count"]), not r["failed"])
    pg.evaluate("window.pywebview.api.set_setting('look', 'cartridge')")
    expect("no errors in the page", not errors)
    for e in errors[:5]:
        print("      " + e)
    browser.close()

print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
