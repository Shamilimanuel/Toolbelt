"""Tests the Download screen in an invisible Chrome, with a pretend Python side that behaves like the real one.

Walks his real use: install the engines, look up a link, pick "Just the sound" as MP3, download, see it finish,
send it to Spotify, fix its tags, and the "you copied a video link" offer. No window appears, nothing downloads.
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
  const settings = {look: 'cartridge', accent: '', animations: false, save_to: 'C:\\Users\\you\\Downloads\\Toolbelt', name_pattern: '{title} - {quality}.{ext}',
    never_overwrite: true, folder_per_tool: false, open_when_done: false, watch_clipboard: true, keep: 'both', audio_format: 'mp3', auto_spotify: true, send_to: 'folder', custom_folder: ''};
  const eng = {'yt-dlp': false, deno: false, ffmpeg: false};
  let jobs = [], nextId = 1, offer = null, tags = {title: '', artist: 'Marine Ch.', album: ''};
  const songs = [];
  window.__calls = [];
  window.__offer = (url) => { offer = {url, at: Date.now() / 1000}; };
  const ok = (v) => Promise.resolve(JSON.parse(JSON.stringify(v)));
  // a 640×360 picture, drawn on the spot: a wide YouTube thumbnail to frame into a square
  const WIDE = (function () { const c = document.createElement('canvas'); c.width = 640; c.height = 360; const x = c.getContext('2d'); x.fillStyle = '#c83c3c'; x.fillRect(0, 0, 640, 360); x.fillStyle = '#3c64c8'; x.fillRect(200, 60, 240, 240); return c.toDataURL('image/jpeg'); })();
  function engineList() {
    const meta = {'yt-dlp': ['yt-dlp', 'downloads videos'], deno: ['Deno', 'needed for YouTube'], ffmpeg: ['ffmpeg', 'joins, converts, compresses']};
    return {engines: Object.keys(meta).map(id => ({id, name: meta[id][0], what: meta[id][1], licence: 'x', approx: '~ MB', installed: eng[id], size: eng[id] ? 1048576 : 0, version: eng[id] ? '1.0' : '', step: 2}))
      .concat([{id: 'birefnet', name: 'BiRefNet', what: 'cut-outs', licence: 'MIT', approx: '~900 MB', installed: false, size: 0, version: '', step: 3}]), total: 0, folder: 'C:\\e'};
  }
  function tick() {                       // pretend time passes: running jobs move on
    jobs.forEach(j => {
      if (j.state === 'waiting') j.state = 'running';
      else if (j.state === 'running') {
        j.progress = Math.min(100, j.progress + 34);
        Object.assign(j.extra, {speed: 3 * 1048576, got: j.progress * 90000, total: 9000000, eta: 3, stage: 'Sound'});
        if (j.progress >= 100) {
          j.state = 'done';
          if (j.kind === 'Engine') eng[j.extra.engine] = true;
          if (j.kind === 'Download') { j.result = 'C:\\Users\\you\\Downloads\\Toolbelt\\Song - MP3.mp3'; j.extra.path = j.result; j.extra.size = 9000000; j.extra.spotify = j.extra.mode === 'audio' ? 'C:\\Users\\you\\Music\\Toolbelt for Spotify\\Song - MP3.mp3' : ''; if (j.extra.spotify) songs.push({path: j.extra.spotify, name: 'Song - MP3.mp3', title: '', artist: 'Marine Ch.', album: '', cover: true}); }
        }
      }
    });
  }
  window.pywebview = {api: {
    settings: () => ok(settings), info: () => ok({version: '0.2', data: 'C:\\x', prototype: 'p'}), gpus: () => ok(['AMD Radeon RX 9060 XT']),
    set_setting: (k, v) => { settings[k] = v; window.__calls.push(['set', k, v]); return ok({ok: true, message: '', settings}); },
    engines: () => ok(engineList()),
    jobs: () => { tick(); return ok(jobs); },
    cancel_job: (id) => { const j = jobs.find(x => x.id === id); if (j) j.state = 'cancelled'; return ok({ok: true, message: 'Cancelling…'}); },
    clear_jobs: () => { jobs = jobs.filter(j => ['running', 'waiting'].includes(j.state)); return ok({ok: true}); },
    install_engines: (ids) => { const want = ids || Object.keys(eng).filter(k => !eng[k]); want.forEach(e => jobs.unshift({id: nextId++, title: 'Install ' + e, kind: 'Engine', progress: 0, state: 'waiting', message: '', result: null, extra: {engine: e}})); window.__calls.push(['install', want]); return ok({ok: true, message: 'Installing ' + want.length + ' engines'}); },
    check_updates: () => ok({'yt-dlp': {installed: '1.0', newest: '1.1', update: true}}),
    look_up: (url) => { window.__calls.push(['look_up', url]);
      if (!/youtu/.test(url)) return ok({ok: false, message: "That doesn't look like a YouTube video link."});
      return ok({ok: true, video: {id: 'JGgnJ0XKGN4', title: 'め組のひと / 宝鐘マリン cover', channel: 'Marine Ch. 宝鐘マリン', duration: 242, url, is_live: false, thumb: '',
        heights: [{height: 2160, label: '4K', size: 400000000, video_only: 396000000}, {height: 1080, label: '1080p', size: 84000000, video_only: 80000000}], sound: {mp3: 7400000, m4a: 3900000, opus: 3700000}}}); },
    start_download: (id, mode, height, audio, title, place) => { window.__calls.push(['download', id, mode, height, audio, place]); jobs.unshift({id: nextId++, title, kind: 'Download', progress: 0, state: 'waiting', message: '', result: null, extra: {video_id: id, mode, quality: mode === 'audio' ? audio.toUpperCase() : height + 'p'}}); return ok({ok: true, id: nextId - 1}); },
    send_places: () => ok({folder: settings.save_to, desktop: 'C:\\Users\\you\\Bureaublad', videos: 'C:\\V', music: 'C:\\M', spotify: 'C:\\S', custom: settings.custom_folder, chosen: settings.send_to}),
    choose_send_folder: () => { settings.custom_folder = 'D:\\Clips'; settings.send_to = 'custom'; return ok({ok: true, message: '', settings}); },
    clipboard_offer: () => { const o = offer; offer = null; return ok(o); },
    paste: () => ok('https://youtu.be/JGgnJ0XKGN4'),
    show_file: (p) => { window.__calls.push(['show', p]); return ok({ok: true}); },
    send_to_spotify: (p) => ok({ok: true, message: 'Copied to Music\\Toolbelt for Spotify.', path: p}),
    spotify_search: (q) => { window.__calls.push(['spotify_search', q]); return ok({ok: true, message: 'Searching Spotify for: ' + q}); },
    songs: () => ok({folder: 'C:\\Users\\you\\Music\\Toolbelt for Spotify', songs}),
    write_tags: (p, v) => { window.__calls.push(['tags', p, v]); songs.forEach(s => { if (s.path === p) Object.assign(s, v); }); return ok({ok: true, message: 'Saved.'}); },
    song_cover: (p) => { window.__calls.push(['cover', p]); return ok({ok: true, token: 'k1', data: WIDE, square: false, youtube: true, lyrics: false, lrc: false, lyrics_text: ''}); },
    song_cover_from: (p, source, url) => { window.__calls.push(['cover_from', source, url]); if (source === 'link' && !/^https:/.test(url)) return ok({ok: false, message: "That isn't a web link (it should start with https://)."}); return ok({ok: true, token: 'k2', data: WIDE, width: 640, height: 360}); },
    song_cover_save: (p, token, crop) => { window.__calls.push(['cover_save', token, crop]); songs.forEach(s => { if (s.path === p) s.square = true; }); return ok({ok: true, message: 'Cover saved.', data: WIDE}); },
    song_suggest_tags: (p) => { window.__calls.push(['suggest', p]); return ok({ok: true, current: {title: 'め組のひと / 宝鐘マリン cover', artist: 'Marine Ch.', album: ''}, suggested: {title: 'め組のひと', artist: '宝鐘マリン', album: 'め組のひと'}, seconds: 207.5}); },
    song_lrclib_check: (title, artist, album, s) => { window.__calls.push(['lrclib', title, artist, album, s]); if (artist === 'ラッツ & スター') return ok({ok: true, match: true, synced: true, candidates: []}); return ok({ok: true, match: false, synced: false, candidates: [{title: 'め組のひと', artist: 'ラッツ & スター', album: "青春歌年鑑 BEST30 ('83)", duration: 207.47, diff: 0.0, synced: true, fits: true}, {title: 'め組のひと', artist: 'Koda Kumi', album: 'Live', duration: 218, diff: 10.5, synced: false, fits: false}]}); },
    song_lyrics_find: (p) => { window.__calls.push(['lyrics_find', p]); return ok({ok: true, plain: 'la la la\nlo lo lo', synced: '[00:01.00] la la la', instrumental: false, found: 'Megumi no hito · Houshou Marine', matches: 2}); },
    song_lyrics_save: (p, plain, synced) => { window.__calls.push(['lyrics_save', plain, synced]); songs.forEach(s => { if (s.path === p) s.lyrics = !!plain; }); return ok({ok: true, message: plain ? 'Lyrics saved.' : 'Lyrics removed.'}); },
    open_spotify_folder: () => ok({ok: true, message: 'Opened'}),
    open_folder: () => ok({ok: true}), open_prototype: () => ok({ok: true, message: ''}), choose_folder: () => ok({ok: false}),
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
    pg.evaluate("window.toolbelt.go('video')")
    pg.wait_for_timeout(300)

    # 1. engines missing -> install card
    expect("without engines it offers to install them", pg.locator("#dlInstall").count() == 1 and "fingerprint" in pg.inner_text("main"))
    pg.click("#dlInstall")
    pg.wait_for_function("!document.querySelector('#dlInstall')", timeout=15000)
    expect("after installing, the link box appears", pg.locator("#dlLink").count() == 1)
    expect("all three were asked for", any(c[0] == "install" and len(c[1]) == 3 for c in pg.evaluate("window.__calls")))

    # 2. a bad link is explained; a good one is looked up
    pg.fill("#dlLink", "https://example.com/video")
    pg.click("#dlLook")
    pg.wait_for_timeout(300)
    expect("a non-YouTube link is explained", "doesn't look like a YouTube" in pg.inner_text("main"))
    pg.click("#dlPaste")
    pg.wait_for_selector("[data-keep]", timeout=5000)
    expect("Paste fills in the link and looks it up", "め組のひと" in pg.inner_text("#dlChoice"))
    expect("4K is picked by default with its size", pg.get_attribute('[data-height="2160"]', "aria-pressed") == "true" and "381" in pg.inner_text('[data-height="2160"]'))
    expect("Send to offers five places, Toolbelt folder picked, Spotify off for video", pg.locator("[data-place]").count() == 5 and pg.get_attribute('[data-place="folder"]', "aria-pressed") == "true" and pg.is_disabled('[data-place="spotify"]'))
    pg.click('[data-place="desktop"]')
    expect("Desktop shows the real Desktop folder and is remembered", "Bureaublad" in pg.inner_text("#dlWhere") and ["set", "send_to", "desktop"] in pg.evaluate("window.__calls"))
    pg.click('[data-place="library"]')
    expect("Videos / Music puts a video in Videos", pg.inner_text("#dlWhere").endswith(r"C:\V"))
    pg.click('[data-place="custom"]')
    pg.wait_for_function("document.querySelector('[data-place=custom]').innerText.includes('Clips')", timeout=3000)
    expect("Pick a folder asks Windows once, then shows the folder's name", pg.get_attribute('[data-place="custom"]', "aria-pressed") == "true" and r"D:\Clips" in pg.inner_text("#dlWhere"))
    pg.click('[data-place="folder"]')
    pg.click('[data-keep="video"]')
    expect("video only shows sizes without the sound", "378" in pg.inner_text('[data-height="2160"]'))
    pg.click('[data-keep="audio"]')
    expect("just the sound offers MP3 / M4A / Opus and the Spotify switch", pg.locator("[data-audio]").count() == 3 and pg.locator("#dlSpot").count() == 1)
    pg.click('[data-place="spotify"]')
    expect("MP3 can go straight to Spotify, then the extra Spotify switch hides", pg.get_attribute('[data-place="spotify"]', "aria-pressed") == "true" and pg.locator("#dlSpot").count() == 0 and r"C:\S" in pg.inner_text("#dlWhere"))
    pg.click('[data-keep="both"]')
    expect("switching back to video moves Spotify back to the Toolbelt folder", pg.get_attribute('[data-place="folder"]', "aria-pressed") == "true")
    pg.click('[data-keep="audio"]')
    pg.click("#dlSpotSearch")
    pg.screenshot(path=str(OUT / "download_choice.png"))

    # 3. download it
    pg.click("#dlGo")
    pg.wait_for_timeout(700)
    calls = pg.evaluate("window.__calls")
    expect("the download asks Python for MP3, sound only", ["download", "JGgnJ0XKGN4", "audio", 2160, "mp3", "folder"] in calls)
    expect("Spotify search used the title", any(c[0] == "spotify_search" and "め組" in c[1] for c in calls))
    pg.wait_for_selector("#hBar", timeout=5000)
    pg.screenshot(path=str(OUT / "download_running.png"))
    expect("the banner shows it downloading with speed", "3.0 MB/s" in pg.inner_text("#dlHero"))
    pg.wait_for_function("document.querySelector('#dlDone') && document.querySelector('#dlDone').innerText.includes('In Spotify')", timeout=8000)
    expect("finished: listed as completed and already in Spotify", "Song - MP3.mp3" in pg.inner_text("#dlDone"))
    pg.wait_for_timeout(600)
    expect("the Spotify box lists the song and how to set Spotify up", "Show Local Files" in pg.inner_text("#dlSpotify") and pg.locator("#dlSpotify [data-tags]").count() == 1)

    # 4. fix the tags
    pg.click("#dlSpotify [data-tags]")
    pg.fill("#tgTitle", "め組のひと")
    pg.fill("#tgArtist", "宝鐘マリン")
    pg.click("#tgSave")
    pg.wait_for_timeout(600)
    expect("tags are written through Python", any(c[0] == "tags" and c[2]["artist"] == "宝鐘マリン" for c in pg.evaluate("window.__calls")))
    expect("the song shows its new title", "め組のひと" in pg.inner_text("#dlSpotify"))

    # Fix for lyrics (15 Oct): clean tags, the same LRCLIB question lyrics-plus asks, and entries that would match
    pg.click("#dlSpotify [data-tags]")
    pg.wait_for_selector("#tgFix", timeout=3000)
    pg.click("#tgFix")
    pg.wait_for_function("document.querySelector('#tgArtist') && document.querySelector('#tgArtist').value === '宝鐘マリン'", timeout=3000)
    expect("Fix for lyrics fills the cleaned title, artist and album", pg.input_value("#tgTitle") == "め組のひと" and pg.input_value("#tgAlbum") == "め組のひと")
    pg.click("#tgCheck")
    pg.wait_for_selector("[data-cand]", timeout=3000)
    expect("the check says no, and lists entries that would match (same length marked)", "Not with these tags" in pg.inner_text(".dialog") and "same length" in pg.inner_text(".dialog") and ["lrclib", "め組のひと", "宝鐘マリン", "め組のひと", 207.5] in pg.evaluate("window.__calls"))
    pg.click('[data-cand="0"]')
    pg.wait_for_timeout(100)
    expect("Use copies that entry's tags into the fields", pg.input_value("#tgArtist") == "ラッツ & スター" and "青春歌年鑑" in pg.input_value("#tgAlbum") and "Yes" in pg.inner_text(".dialog"))
    pg.click("#tgSave")
    pg.wait_for_timeout(300)
    expect("Save writes the matching tags", any(c[0] == "tags" and c[2]["artist"] == "ラッツ & スター" and "青春歌年鑑" in c[2]["album"] for c in pg.evaluate("window.__calls")))

    # the cover editor: the wide picture, framed square by zoom and drag, saved with the crop
    pg.click("#dlSpotify [data-cover]")
    pg.wait_for_selector("#cvImg", timeout=5000)
    pg.wait_for_timeout(200)
    expect("Cover opens the editor with the song's picture, YouTube offered", pg.locator("#cvYt").is_enabled() and pg.get_attribute('[data-stab="cover"]', "aria-pressed") == "true")
    pg.evaluate("(function(){var z=document.querySelector('#cvZoom');z.value=150;z.dispatchEvent(new Event('input'));})()")
    frame = pg.locator("#cvFrame")
    box = frame.bounding_box()
    pg.mouse.move(box["x"] + 150, box["y"] + 150)
    pg.mouse.down()
    pg.mouse.move(box["x"] + 60, box["y"] + 120, steps=5)
    pg.mouse.up()
    pg.click("#cvSave")
    pg.wait_for_timeout(300)
    saved = [c for c in pg.evaluate("window.__calls") if c[0] == "cover_save"]
    expect("Save sends the framed square (x, y, w in picture pixels) for the picture it was given", saved and saved[0][1] == "k1" and saved[0][2]["w"] < 360 and saved[0][2]["x"] > 0 and 0 <= saved[0][2]["y"] <= 360 - saved[0][2]["w"])
    pg.click("#cvYt")
    pg.wait_for_timeout(200)
    pg.click("#cvLinkBtn")
    pg.fill("#cvLink", "ftp://nope")
    pg.click("#cvLinkGo")
    pg.wait_for_timeout(200)
    expect("YouTube asks Python; a bad link is explained", ["cover_from", "youtube", ""] in pg.evaluate("window.__calls") and "web link" in pg.inner_text("#cvErr"))
    pg.fill("#cvLink", "https://example.com/pic.jpg")
    pg.press("#cvLink", "Enter")
    pg.wait_for_timeout(200)
    expect("a good link is fetched", any(c[0] == "cover_from" and c[1] == "link" and c[2] == "https://example.com/pic.jpg" for c in pg.evaluate("window.__calls")))
    pg.screenshot(path=str(OUT / "song_cover.png"))

    # lyrics: find, edit, save, remove
    pg.click('[data-stab="lyrics"]')
    pg.wait_for_selector("#lyText", timeout=3000)
    pg.click("#lyFind")
    pg.wait_for_function("document.querySelector('#lyText').value.includes('la la la')", timeout=4000)
    expect("Find fills the lyrics and says what it found", "Megumi no hito" in pg.inner_text("#lyStatus") and "with timing" in pg.inner_text("#lyStatus"))
    pg.fill("#lyText", "la la la\nlo lo lo\n(outro)")
    pg.click("#lySave")
    pg.wait_for_timeout(300)
    calls = pg.evaluate("window.__calls")
    expect("Save writes the edited words and the timing", any(c[0] == "lyrics_save" and "(outro)" in c[1] and c[2].startswith("[00:01") for c in calls))
    pg.click("#lyClear")
    pg.wait_for_timeout(300)
    expect("Remove saves empty lyrics", any(c[0] == "lyrics_save" and c[1] == "" for c in pg.evaluate("window.__calls")))
    pg.click(".dialog [data-x]")
    pg.wait_for_timeout(200)
    expect("the song list shows what is still missing", pg.locator(".dim").count() == 0 and "lyrics" in pg.inner_text("#dlSpotify"))
    pg.screenshot(path=str(OUT / "download_done.png"), full_page=True)

    # 5. copied link offer, from another screen
    pg.evaluate("window.toolbelt.go('home')")
    pg.evaluate("window.__offer('https://youtu.be/dQw4w9WgXcQ')")
    pg.wait_for_selector("#toast [data-o='look']", timeout=4000)
    expect("copying a link shows the offer", "You copied a video link" in pg.inner_text("#toast"))
    pg.click("#toast [data-o='look']")
    pg.wait_for_timeout(500)
    expect("…which opens Download and looks it up", pg.evaluate("window.toolbelt.state().screen") == "video" and any(c == ["look_up", "https://youtu.be/dQw4w9WgXcQ"] for c in pg.evaluate("window.__calls")))

    # 5b. the bar at the top takes a link too
    pg.evaluate("window.toolbelt.go('settings')")
    pg.fill("#omni", "https://youtu.be/JGgnJ0XKGN4")
    pg.press("#omni", "Enter")
    pg.wait_for_timeout(500)
    expect("a link typed in the top bar opens Download and looks it up", pg.evaluate("window.toolbelt.state().screen") == "video" and pg.input_value("#omni") == "" and pg.locator("[data-keep]").count() == 3)

    # 6. settings: the Downloads section
    pg.evaluate("window.toolbelt.go('settings')")
    pg.click('[data-set="dl"]')
    pg.click('[data-dkeep="audio"]')
    pg.wait_for_timeout(200)
    pg.click("#setClip")
    pg.wait_for_timeout(200)
    calls = pg.evaluate("window.__calls")
    expect("Downloads settings save", ["set", "keep", "audio"] in calls and ["set", "watch_clipboard", False] in calls)

    # 7. engines screen shows the update
    pg.evaluate("window.toolbelt.go('engines')")
    pg.click("#engUpdates")
    pg.wait_for_timeout(400)
    expect("Engines offers the yt-dlp update", "Update to 1.1" in pg.inner_text("main"))
    over = pg.evaluate("(() => { const m = document.querySelector('main'); return m.scrollWidth > m.clientWidth + 2; })()")
    expect("nothing sticks out sideways", not over)
    expect("no script errors", errors == [])
    if errors:
        print("    " + "\n    ".join(errors[:10]))
    browser.close()

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_page_download)")
