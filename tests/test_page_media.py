"""The Media screen in an invisible Chrome with a pretend Python side: game clips, a dropped video, every tab, the jobs list."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

from page import build_page                                   # noqa: E402
from playwright.sync_api import sync_playwright                # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")     # labels have arrows in them; the console may be cp1252


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


FAKE = r"""
(() => {
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\Users\\you\\Downloads\\Toolbelt', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: ''};
  const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  const video = {token: 'v1', name: 'clutch.mp4', kind: 'video', size: 148e6, duration: 42, width: 2560, height: 1440, fps: 60, vcodec: 'h264', acodec: 'aac', frames: 2520, thumb: PNG};
  const pic = {token: 'p1', name: 'logo.png', kind: 'picture', size: 4.1e6, duration: 0, width: 2048, height: 2048, fps: 0, vcodec: '', acodec: '', frames: 1, thumb: PNG};
  const gif = {token: 'g1', name: 'react.gif', kind: 'gif', size: 2.1e6, duration: 2, width: 320, height: 240, fps: 24, vcodec: 'gif', acodec: '', frames: 48, thumb: PNG};
  let jobs = [], nextId = 1, realesrgan = false;
  window.__calls = [];
  window.__drop = (file) => { window.__next = file; };
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.6', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]),
    set_setting: (k, v) => { settings[k] = v; return ok({ok: true, message: '', settings}); },
    engines: () => ok({engines: [{id: 'ffmpeg', name: 'ffmpeg', what: '', licence: '', approx: '', installed: true, size: 1, version: '9', step: 2}, {id: 'realesrgan', name: 'Real-ESRGAN', what: '', licence: '', approx: '~45 MB', installed: realesrgan, size: 0, version: '', step: 6}], total: 1, folder: 'C:\\e'}),
    jobs: () => { jobs.forEach(j => { if (j.state === 'waiting') j.state = 'running'; else if (j.state === 'running') { j.progress += 50; if (j.progress >= 100) { j.state = 'done'; j.extra.path = 'C:\\Users\\you\\Downloads\\Toolbelt\\out.mp4'; j.extra.size = 9.6e6; } } }); return ok(jobs); },
    cancel_job: (id) => ok({ok: true}), clear_jobs: () => ok({ok: true}), check_updates: () => ok({}), clipboard_offer: () => ok(null), mail: () => ok([]), games: () => ok([]),
    install_engines: (ids) => { window.__calls.push(['install', ids]); realesrgan = true; return ok({ok: true, message: 'Installing 1 engine'}); },
    media_pick: () => { window.__calls.push(['pick']); return ok({ok: true, file: window.__next || video}); },
    media_drop: (p) => { window.__calls.push(['drop', p]); return ok({ok: true, file: window.__next || video}); },
    media_info: (t) => ok({ok: true, file: video}),
    media_clips: () => ok([{token: 'c1', name: 'fight.mp4', game: 'GenshinImpact', source: 'ReLive', size: 212e6, when: '2026-10-13T20:00:00'}, {token: 'c2', name: 'mc.mp4', game: 'Minecraft', source: 'Game Bar', size: 388e6, when: '2026-10-12T20:00:00'}]),
    media_clip_thumb: (t) => ok({ok: true, thumb: PNG}),
    media_estimate: (t, mb, s, e) => { window.__calls.push(['estimate', mb, s, e]); return ok({ok: true, plan: {video_kbps: 1700, audio_kbps: 96, height: 720, scale: true, length: e > s ? e - s : 42, mb, fits: mb >= 10, percent: 94}}); },
    media_picture_preview: (t, fmt, q) => { window.__calls.push(['preview', fmt, q]); return ok({ok: true, size: 380000, preview: PNG, before: PNG, original: 4.1e6}); },
    media_video_plan: (t, s) => ok({ok: true, plan: {frames: 2520, width: 2560 * s, height: 1440 * s, minutes: 7, ok: s <= 1.5, why: 'That would be ' + 1440 * s + ' pixels tall; Toolbelt stops at 4K. Pick a smaller ×.'}}),
    upscale_models: () => ok({installed: realesrgan, models: [{id: 'realesrgan-x4plus', for: 'Photos', note: 'slow', scales: [4]}, {id: 'realesr-animevideov3', for: 'GIFs', note: 'fast', scales: [2, 3, 4]}]}),
    media_job: (t, action, o) => { window.__calls.push(['job', action, o]); jobs.unshift({id: nextId++, title: action + ' · x', kind: 'Media', progress: 0, state: 'waiting', message: '', result: null, extra: {action}}); return ok({ok: true, id: nextId - 1}); },
    show_file: (p) => { window.__calls.push(['show', p]); return ok({ok: true}); },
    cut_token: (t) => { window.__calls.push(['cut', t]); return ok({ok: false, message: 'no model in the test'}); },
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}),
  }};
  window.__setFile = (which) => { window.__next = {video, pic, gif}[which]; };
})();
"""

page_file = OUT / "page_media.html"
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
    pg.evaluate("window.toolbelt.go('media')")
    pg.wait_for_function("document.querySelectorAll('[data-clip]').length === 2", timeout=5000)
    expect("Game clips: two recordings with game, source and size", "GenshinImpact" in pg.inner_text(".mgrid") and "Game Bar" in pg.inner_text(".mgrid") and "202" in pg.inner_text(".mgrid"))
    pg.wait_for_function("document.querySelector('[data-clip=\"c1\"]').style.backgroundImage !== ''", timeout=4000)
    pg.click('[data-cfilter="ReLive"]')
    expect("the source filter narrows the grid", pg.locator("[data-clip]").count() == 1)
    pg.click('[data-cfilter="All"]')
    pg.click('[data-clip="c1"]')
    pg.wait_for_selector("#mdDiscord", timeout=4000)
    expect("picking a clip shows it with From/To and Send to Discord", pg.locator("#mdFrom").count() == 1 and "clutch.mp4" in pg.inner_text("main"))
    pg.evaluate("(function(){var f=document.querySelector('#mdFrom');f.value=170;f.dispatchEvent(new Event('input'));f.dispatchEvent(new Event('change'));var t=document.querySelector('#mdTo');t.value=220;t.dispatchEvent(new Event('input'));t.dispatchEvent(new Event('change'));})()")
    expect("the piece reads 0:17 → 0:22", "0:17 → 0:22 · 0:05" in pg.inner_text("#mdRangeText"))
    pg.click("#mdDiscord")
    pg.wait_for_timeout(300)
    calls = pg.evaluate("window.__calls")
    expect("Send to Discord starts the job with the piece", any(c[0] == "job" and c[1] == "discord" and abs(c[2]["start"] - 17) < 0.01 and abs(c[2]["end"] - 22) < 0.01 for c in calls))
    pg.screenshot(path=str(OUT / "media_clips.png"))

    # compress video
    pg.click('[data-mtab="vcomp"]')
    pg.wait_for_function("document.querySelector('#mdPlan') && document.querySelector('#mdPlan').innerText.includes('Result')", timeout=4000)
    expect("Compress video shows the plan: about 10 MB, 720p, smaller", "about 10 MB" in pg.inner_text("#mdPlan") and "720p" in pg.inner_text("#mdPlan") and "94% smaller" in pg.inner_text("#mdPlan"))
    pg.click('[data-target="25"]')
    pg.wait_for_function("document.querySelector('#mdPlan').innerText.includes('about 25 MB')", timeout=4000)
    pg.click("#mdCompress")
    pg.wait_for_timeout(200)
    expect("Compress starts with the target", any(c[0] == "job" and c[1] == "compress" and c[2]["target"] == 25 for c in pg.evaluate("window.__calls")))

    # convert
    pg.click('[data-mtab="convert"]')
    pg.click('[data-fmt="mp3"]')
    pg.click("#mdConvert")
    pg.wait_for_timeout(200)
    expect("Convert to MP3 starts", any(c[0] == "job" and c[1] == "convert" and c[2]["fmt"] == "mp3" for c in pg.evaluate("window.__calls")))

    # GIF / WebM
    pg.click('[data-mtab="clip"]')
    pg.click('[data-ckind="webm"]')
    pg.click('[data-cwidth="320"]')
    pg.click("#mdClip")
    pg.wait_for_timeout(200)
    expect("Make a WebM at 320 wide", any(c[0] == "job" and c[1] == "clip" and c[2]["kind"] == "webm" and c[2]["width"] == 320 for c in pg.evaluate("window.__calls")))

    # the jobs list on the screen
    pg.wait_for_function("document.querySelector('#mdDone') && document.querySelector('#mdDone').innerText.includes('done')", timeout=6000)
    expect("finished work is listed with Show in folder", pg.locator("#mdDone [data-show]").count() >= 1)

    # a picture: compress with the before/after slider, resize, format
    pg.evaluate("window.__setFile('pic')")
    pg.click("#mdPick")
    pg.wait_for_function("document.querySelector('#mdBa .ba-after')", timeout=5000)
    expect("a picture opens on Compress picture with a before/after preview", "WEBP" in pg.inner_text("#mdBa .ba-tag.r") and "Original" in pg.inner_text("#mdBa .ba-tag.l") and "91% smaller" in pg.inner_text("main"))
    expect("the preview was asked at WebP 78", ["preview", "webp", 78] in pg.evaluate("window.__calls"))
    pg.click('[data-ifmt="avif"]')
    pg.wait_for_timeout(300)
    expect("another format asks again", ["preview", "avif", 78] in pg.evaluate("window.__calls"))
    pg.click("#mdIcomp")
    pg.wait_for_timeout(200)
    expect("Save compresses as AVIF", any(c[0] == "job" and c[1] == "icomp" and c[2]["fmt"] == "avif" for c in pg.evaluate("window.__calls")))
    pg.screenshot(path=str(OUT / "media_icomp.png"))
    pg.click('[data-mtab="resize"]')
    pg.click('[data-preset="custom"]')
    pg.fill("#mdW", "500")
    pg.click("#mdPixel")
    pg.click("#mdResize")
    pg.wait_for_timeout(200)
    expect("custom resize sends width, keep shape and pixel art", any(c[0] == "job" and c[1] == "resize" and c[2]["preset"] == "custom" and c[2]["width"] == 500 and c[2]["pixel"] is True and c[2]["keep"] is True for c in pg.evaluate("window.__calls")))
    pg.click('[data-mtab="format"]')
    pg.click('[data-pfmt="ico"]')
    pg.click("#mdFormat")
    pg.wait_for_timeout(200)
    expect("picture format → .ico", any(c[0] == "job" and c[1] == "format" and c[2]["fmt"] == "ico" for c in pg.evaluate("window.__calls")))
    pg.click('[data-sugg="cut"]')
    pg.wait_for_timeout(200)
    expect("Cut out the background hands the picture to Cut out", ["cut", "p1"] in pg.evaluate("window.__calls") and pg.evaluate("window.toolbelt.state().screen") == "bg")

    # upscale: install first, then picture / gif / video
    pg.evaluate("window.toolbelt.go('media')")
    pg.click('[data-mtab="upscale"]')
    pg.wait_for_selector("#mdInstall", timeout=4000)
    expect("without Real-ESRGAN it offers to install it", "45 MB" in pg.inner_text("main"))
    pg.click("#mdInstall")
    pg.wait_for_timeout(1500)
    pg.click('[data-mtab="upscale"]')
    pg.wait_for_selector("#mdUp", timeout=4000)
    pg.click('[data-scale="4"]')
    pg.click("#mdUp")
    pg.wait_for_timeout(200)
    expect("picture upscale 4× with the chosen model", any(c[0] == "job" and c[1] == "upscale" and c[2]["scale"] == 4 for c in pg.evaluate("window.__calls")))
    pg.evaluate("window.__setFile('gif')")
    pg.click("#mdPick")
    pg.wait_for_selector("#mdSharpen", timeout=4000)
    expect("a GIF lands on Sharpen GIF with its 48 frames", "48 frames" in pg.inner_text("main"))
    pg.click('[data-gout="mp4"]')
    pg.click("#mdSharpen")
    pg.wait_for_timeout(200)
    expect("Sharpen GIF → looping MP4", any(c[0] == "job" and c[1] == "sharpen_gif" and c[2]["out"] == "mp4" for c in pg.evaluate("window.__calls")))
    pg.evaluate("window.__setFile('video')")
    pg.click("#mdPick")
    pg.click('[data-mtab="upscale"]')
    pg.wait_for_function("document.querySelector('#mdVplan') && !document.querySelector('#mdVplan').innerText.includes('Working')", timeout=5000)
    expect("video upscale: 1440p × 2 is past 4K, so it says so and the button is off", "stops at 4K" in pg.inner_text("#mdVplan") and pg.is_disabled("#mdUpVideo"))
    pg.screenshot(path=str(OUT / "media_upscale.png"))

    # dropping a file with a real path
    pg.evaluate("(function(){var dt=new DataTransfer();var f=new File(['x'],'clip.mp4',{type:'video/mp4'});Object.defineProperty(f,'pywebviewFullPath',{value:'C:\\\\Users\\\\you\\\\Videos\\\\clip.mp4'});dt.items.add(f);window.dispatchEvent(new DragEvent('drop',{dataTransfer:dt}));})()")
    pg.wait_for_timeout(300)
    expect("a dropped file goes to Python by its full path", any(c[0] == "drop" and c[1].endswith("clip.mp4") for c in pg.evaluate("window.__calls")))
    expect("nothing sticks out sideways", pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"))
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_media)")
