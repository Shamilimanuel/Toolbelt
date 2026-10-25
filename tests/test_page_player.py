"""The video player inside Toolbelt (his asks, 15 Oct), in an invisible Chrome with real little videos (WebM, which
this Chrome plays): cutting while watching (handles on the timeline, the frame follows, keys, play the piece), the
full-window player, before / after with two videos in step and zoom, and the playable-copy fallback."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import engines                                                # noqa: E402
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


ffmpeg = engines.path_of("ffmpeg")
clips = {}
for name, size in (("before", "320x180"), ("after", "640x360")):
    path = OUT / ("player_%s.webm" % name)
    if not path.exists():
        subprocess.run([str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=%s:rate=30" % size, "-t", "4",
                        "-c:v", "libvpx-vp9", "-b:v", "200k", str(path)], check=True, creationflags=0x08000000)
    clips[name] = path.as_uri()

FAKE = r"""
(() => {
  const C = %s;
  const settings = {look: 'glassdark', accent: '', animations: false, save_to: 'C:/x', name_pattern: '{title}.{ext}', never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: false, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: ''};
  const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  const video = {token: 'v1', name: 'clutch.webm', kind: 'video', size: 148e6, duration: 4, width: 640, height: 360, fps: 30, vcodec: 'vp9', acodec: '', frames: 120, thumb: PNG};
  const bad = Object.assign({}, video, {token: 'bad', name: 'odd.mkv'});
  let jobs = [], nextId = 1;
  window.__calls = [];
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  window.pywebview = {api: new Proxy({
    settings: () => ok(settings), info: () => ok({version: '1', data: 'x', prototype: 'p', logos: {}}), gpus: () => ok([]), engines: () => ok({engines: [], total: 0, folder: ''}),
    jobs: () => { jobs.forEach(j => { if (j.state === 'waiting') j.state = 'running'; else if (j.state === 'running') { j.state = 'done'; j.progress = 100; j.extra.path = 'C:/out.webm'; j.extra.size = 9.6e6; if (j.kind === 'Preview') j.extra.url = C.before; } }); return ok(jobs); },
    mail: () => ok([]), clipboard_offer: () => ok(null), media_clips: () => ok([]),
    media_pick: () => ok({ok: true, file: window.__next || video}),
    media_info: () => ok({ok: true, file: video}),
    media_url: (t) => { window.__calls.push(['url', t]); return ok(t === 'bad' ? {ok: true, url: 'file:///C:/nope/odd.mkv'} : {ok: true, url: C.after}); },
    media_proxy: (t) => { window.__calls.push(['proxy', t]); jobs.unshift({id: nextId++, title: 'Playable copy', kind: 'Preview', progress: 0, state: 'waiting', message: '', result: null, extra: {token: t}}); return ok({ok: true, id: nextId - 1}); },
    media_job: (t, action, o) => { window.__calls.push(['job', action, o]); jobs.unshift({id: nextId++, title: action, kind: 'Media', progress: 0, state: 'waiting', message: '', result: null, extra: {action, token: t}}); return ok({ok: true, id: nextId - 1}); },
    media_compare: (id) => { window.__calls.push(['compare', id]); return ok({ok: true, kind: 'video', start: 0, action: 'upscale_video', before: {url: C.before, size: 2.1e6, width: 320, height: 180, name: 'b.webm'}, after: {url: C.after, size: 8.4e6, width: 640, height: 360, name: 'a.webm'}}); },
    media_estimate: () => ok({ok: true, plan: {mb: 10, fits: true, height: 360, percent: 50, audio_kbps: 0}}),
  }, {get: (t, k) => t[k] || (() => ok({ok: true, message: ''}))})};
  window.__setFile = (f) => { window.__next = f === 'bad' ? bad : video; };
  window.__addJob = (action) => { jobs.unshift({id: nextId++, title: action, kind: 'Media', progress: 100, state: 'done', message: '', result: null, extra: {action, token: 'v1', path: 'C:/out.webm', size: 8.4e6}}); };
})();
""" % json.dumps(clips)

page_file = OUT / "page_player.html"
page_file.write_text(build_page(), encoding="utf-8")


def calls(pg):
    return pg.evaluate("window.__calls")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
    pg = browser.new_page(viewport={"width": 1320, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(FAKE)
    pg.goto(page_file.as_uri())
    pg.wait_for_function("window.toolbelt && window.toolbelt.ready", timeout=10000)
    pg.evaluate("window.toolbelt.go('media')")
    pg.click("#mdPick")
    pg.wait_for_selector('[data-mtab="clip"]', timeout=4000)
    pg.click('[data-mtab="clip"]')
    pg.wait_for_function("document.querySelector('#mdPlayer video') && document.querySelector('#mdPlayer video').readyState >= 2", timeout=8000)
    expect("cutting a GIF shows the video itself, with From / To handles on its timeline", pg.locator("#mdPlayer .vp-h.vp-in").count() == 1 and pg.locator("#mdFrom").count() == 1)

    # drag the From handle to a quarter: the picture follows it, the slider and the times follow too
    track = pg.locator("#mdPlayer .vp-track").bounding_box()
    hin = pg.locator("#mdPlayer .vp-h.vp-in").bounding_box()
    pg.mouse.move(hin["x"] + hin["width"] / 2, hin["y"] + hin["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(track["x"] + track["width"] * 0.25, hin["y"] + hin["height"] / 2, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(300)
    t = pg.evaluate("document.querySelector('#mdPlayer video').currentTime")
    expect("dragging From shows that frame (%.2f s) and moves the From slider" % t, 0.8 < t < 1.2 and 8 <= int(pg.input_value("#mdFrom")) <= 12)
    pg.focus("#mdPlayer")
    pg.keyboard.press("Shift+ArrowRight")
    pg.keyboard.press("Shift+ArrowRight")
    pg.keyboard.press("ArrowRight")
    t2 = pg.evaluate("document.querySelector('#mdPlayer video').currentTime")
    expect("→ steps one frame, Shift+→ one second (%.2f s)" % t2, abs(t2 - (t + 2 + 1 / 30)) < 0.08)
    pg.keyboard.press("o")
    pg.wait_for_timeout(150)
    rng = pg.inner_text("#mdRangeText")
    expect("O sets To at the frame you're looking at: %s" % rng, "0:01 → 0:03" in rng)
    pg.click("#mdPlayer .vp-piece")
    pg.wait_for_timeout(2600)
    t3 = pg.evaluate("document.querySelector('#mdPlayer video').currentTime")
    expect("▶ Play the piece loops inside From / To (%.2f s)" % t3, 0.8 <= t3 <= 3.2)
    pg.click("#mdPlayer .vp-play")
    pg.screenshot(path=str(OUT / "player_cut.png"))
    pg.click("#mdClip")
    pg.wait_for_timeout(200)
    job = next((c for c in calls(pg) if c[0] == "job"), None)
    expect("Make it uses the piece picked while watching", job and 0.8 < job[2]["start"] < 1.2 and 2.8 < job[2]["end"] < 3.2)

    # watch it inside Toolbelt
    pg.click("#mdWatch")
    pg.wait_for_function("document.querySelector('#vpDim video') && document.querySelector('#vpDim video').currentTime > 0.3", timeout=6000)
    expect("▶ Watch plays the video full-window inside Toolbelt", pg.locator("#vpDim .vp").count() == 1)
    pg.screenshot(path=str(OUT / "player_watch.png"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    expect("Esc closes it", pg.locator("#vpDim").count() == 0)

    # before / after of a finished job
    pg.evaluate("window.__addJob('upscale_video')")
    pg.wait_for_selector("#mdDone [data-cmp]", timeout=6000)
    pg.click("#mdDone [data-cmp]")
    pg.wait_for_selector("#cmpBox video.cmp-a", timeout=4000)
    pg.wait_for_function("document.querySelector('.cmp-a').readyState >= 2 && document.querySelector('.cmp-b').readyState >= 2", timeout=6000)
    pg.click("#vpDim .vp-play")
    pg.wait_for_timeout(1500)
    ta, tb = pg.evaluate("[document.querySelector('.cmp-a').currentTime, document.querySelector('.cmp-b').currentTime]")
    expect("before / after: both videos play in step (%.2f / %.2f s)" % (ta, tb), ta > 0.5 and abs(ta - tb) < 0.2)
    pg.evaluate("(function(){var r=document.querySelector('#cmpBox .ba-range');r.value=30;r.dispatchEvent(new Event('input'));})()")
    pg.click("#cmpZoom")
    expect("the slider moves the cut, Zoom looks closer", pg.evaluate("getComputedStyle(document.querySelector('#cmpBox')).getPropertyValue('--cut').trim()") == "30%"
           and pg.evaluate("getComputedStyle(document.querySelector('#cmpBox')).getPropertyValue('--z').trim()") == "2")
    expect("the sizes are on the tags", "8.0 MB" in pg.inner_text("#cmpBox") and "640 × 360" in pg.inner_text("#cmpBox"))
    pg.screenshot(path=str(OUT / "player_compare.png"))
    pg.keyboard.press("Escape")

    # a video the engine can't play: a playable copy is made once, then it plays
    pg.evaluate("window.__setFile('bad')")
    pg.click("#mdPick")
    pg.wait_for_function("document.querySelector('#mdPlayer .vp-msg') && !document.querySelector('#mdPlayer .vp-msg').hidden", timeout=6000)
    expect("an unplayable video asks for a playable copy", ["proxy", "bad"] in calls(pg))
    pg.wait_for_function("document.querySelector('#mdPlayer video') && document.querySelector('#mdPlayer video').readyState >= 2", timeout=8000)
    expect("…and plays the copy when it's ready", True)
    expect("no script errors", errors == [])
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_player)")
