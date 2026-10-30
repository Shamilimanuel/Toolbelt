/* Toolbelt's page. Talks to Python through window.pywebview.api (see main.py's Api class).
   Step 1 (the frame): sidebar, three looks, Settings, Engines and the job list are real; the tool screens
   show what each later step brings. window.toolbelt is for the tests (they never show a window). */
(function () {
  var T = window.toolbelt = { ready: false, errors: [] };
  window.addEventListener('error', function (e) { T.errors.push(String(e.message || e)); });
  window.addEventListener('unhandledrejection', function (e) { T.errors.push(String((e.reason && e.reason.message) || e.reason)); });

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function api(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    var bridge = window.pywebview && window.pywebview.api;
    if (!bridge || typeof bridge[name] !== 'function') return Promise.reject(new Error('Toolbelt\'s Python side isn\'t answering (' + name + ').'));
    return Promise.resolve(bridge[name].apply(bridge, args));
  }

  var ICON = {
    home: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    games: '<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 10.5v4M5 12.5h4M15.5 12h.01M18 14h.01"/>',
    video: '<path d="M12 3v12M6 10l6 6 6-6M4 21h16"/>',
    bg: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.6 7.6L20 18M8.6 16.4L20 6"/>',
    media: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>',
    color: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
    tools: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    calc: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h2M12 12h2M16 12h.01M8 16h2M12 16h2M16 16h.01"/>',
    unin: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    pc: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    guard: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M12 8v5M12 16h.01"/>',
    check: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    engines: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    settings: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>'
  };
  function svg(k) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[k] + '</svg>'; }

  // [id, name, the step that builds it (0 = this step)]
  var SCREENS = [['home', 'Home', 0], ['games', 'Games', 0], ['video', 'Download', 0], ['bg', 'Cut out', 0], ['media', 'Media', 0], ['color', 'Colours', 0], ['calc', 'Calculator', 0], ['tools', 'Handy tools', 0],
    ['unin', 'Uninstall', 0], ['pc', 'PC care', 0], ['guard', 'App guard', 0], ['sep'], ['check', 'Check a file', 0], ['engines', 'Engines', 0], ['settings', 'Settings', 0]];
  var NAMES = {}; SCREENS.forEach(function (s) { if (s[1]) NAMES[s[0]] = s[1]; });

  var STEPS = [
    [1, 'The frame', 'Window, three looks, sidebar, job list, engines, where files go'],
    [2, 'Downloader', 'Up to 4K, copied links, queue, Spotify, music tags. First test: your Marine cover'],
    [3, 'Cut out', 'Remove background, new background, paste in / copy out, sticker & emoji'],
    [4, 'Home', 'Your apps with progress and Next up, add any app, Settings / Folder / VS Code'],
    [5, 'Colours', 'Minecraft gradients with shadows, colour codes, palettes'],
    [6, 'Pictures & video', 'Convert, compress, resize, GIF / WebM, game clips, upscaling and GIF sharpening'],
    [7, 'Game library', 'Its own project in Widgets: your games, Playnite import, covers and banners'],
    [8, 'Waypoint door + checks', 'Toolbelt actions in Waypoint\'s right-click menu, check a file'],
    [9, 'PC care', 'Revo-style uninstaller, startup, drivers, ping'],
    [10, 'Finishing tools', 'QR codes, colour picker, rename files, crop, many pictures, HEIC, sound, subtitles, Fix all songs, Wallpaper Engine']
  ];
  var BUILT = 10;                                             // the last finished build step
  var PLAN = {
    home: ['<b>Your 10 apps</b> with their progress and first "Next up" line, read from each status.md', '<b>Add any Windows app</b>: from the Start menu, an .exe or a website', 'Labelled <b>Settings</b>, <b>Folder</b> and <b>VS Code</b> buttons on every app'],
    games: ['A <b>separate project</b> (Widgets\\GameLibrary) shown here as a tab, with Pop out', 'Finds your games in Steam, Epic, HoYoPlay, Minecraft and more; add one by its .exe', 'Playnite import, covers and banners from SteamGridDB, banner effects, GIF / video banners'],
    video: ['Paste a link: <b>video + sound, video only, or just the sound</b>, up to 4K', 'Steam-style page: downloading now, speed graph, up next, completed', '<b>Send to Spotify</b> (first test: め組のひと, your Marine cover) and a music tag editor', 'Needs yt-dlp, Deno and ffmpeg (about 80 MB): asks before installing'],
    bg: ['Drop or paste a picture: the background is cut out on your own PC', 'New background, touch-up brush, sticker & emoji sizes, crop, batch', 'Needs a cut-out model (BiRefNet, about 900 MB, or a small quick one): asks first'],
    media: ['Convert, compress video (fit under 10 MB for Discord), compress and resize pictures', 'GIF / WebM clips, game clips from ReLive / Steam / OBS', 'AI upscaling and <b>GIF sharpening</b> (Real-ESRGAN, about 50 MB)'],
    color: ['Minecraft gradient text in &#rrggbb, MiniMessage, Skript, &x and tellraw JSON', 'Bold / italic / underline / strike / obfuscated, <b>custom text shadow</b>', 'Colour codes, readability check, palettes, saved gradients'],
    unin: ['Revo-style: your program list with sizes, versions and companies; Icons / List / Details', 'Right-click menu, restore point first, leftover scan, Recycle Bin + registry backup', 'Tools: autorun, junk files, Windows tools, browser and Windows cleaners'],
    pc: ['Drivers: is each one the right one and up to date (AMD, Realtek, ASUS…), with Update', 'Startup: what starts with Windows and how much it slows you down', 'Connection: live ping and lag to game servers'],
    check: ['Fingerprints (MD5, SHA-1, SHA-256, SHA-512), who signed a file, compare two files', 'Whole-folder check, disguised files like invoice.pdf.exe', 'Plus the command door for Waypoint\'s right-click menu']
  };

  var st = { screen: 'home', set: 'look', settings: null, jobs: [], engines: null, gpus: null, info: null, bridge: false };
  try { var saved = localStorage.getItem('toolbelt-screen'); if (saved && NAMES[saved]) st.screen = saved; } catch (e) {}

  // ---------- small helpers ----------
  var toastTimer = null;
  function toast(text) {
    var old = $('#toast'); if (old) old.remove();
    clearTimeout(toastTimer);
    var t = document.createElement('div'); t.className = 'toast'; t.id = 'toast'; t.setAttribute('role', 'status');
    t.innerHTML = '<span class="badge" style="width:26px;height:26px;font-size:12px">T</span><span>' + esc(text) + '</span>';
    $('#app').appendChild(t);
    toastTimer = setTimeout(function () { t.remove(); }, 2800);
  }
  function fail(err) { toast(err && err.message ? err.message : String(err)); }
  function fmtBytes(n) {
    if (!n) return '0 MB';
    return n >= 1073741824 ? (n / 1073741824).toFixed(2) + ' GB' : (n / 1048576).toFixed(n >= 104857600 ? 0 : 1) + ' MB';
  }
  function fmtSize(n) {                                      // any size, from bytes up (the uninstaller's leftovers)
    n = +n || 0;
    if (n < 1024) return n + ' bytes';
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
    return fmtBytes(n);
  }
  function sw(id, on, label) { return '<button type="button" class="switch" role="switch" id="' + id + '" aria-checked="' + !!on + '" aria-label="' + esc(label) + '"></button>'; }
  function setrow(title, sub, ctl) { return '<div class="setrow"><div><b>' + title + '</b>' + (sub ? '<span class="muted">' + sub + '</span>' : '') + '</div><div class="ctl">' + ctl + '</div></div>'; }

  // ---------- looks ----------
  var ACCENTS = { cartridge: ['#FFCF3F', '#FF5C8A', '#5CE08A', '#5CC8FF', '#B98CFF'], glass: ['#0F6CBD', '#C239B3', '#0F7B3F', '#CA5010', '#5B5FC7'], glassdark: ['#60CDFF', '#FF8FD8', '#6CCB8A', '#FFB46B', '#A9A6FF'] };
  function lum(h) { var c = [1, 3, 5].map(function (i) { var v = parseInt(h.substr(i, 2), 16) / 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; }
  function applyLook() {
    var s = st.settings; if (!s) return;
    var r = $('#root');
    r.className = (s.look === 'cartridge' ? 'look-cartridge' : s.look === 'glass' ? 'look-glass' : 'look-glass glass-dark') + (s.animations ? '' : ' no-anim');
    if (s.accent) { r.style.setProperty('--accent', s.accent); r.style.setProperty('--on', lum(s.accent) > .45 ? '#1A1626' : '#FFFFFF'); }
    else { r.style.removeProperty('--accent'); r.style.removeProperty('--on'); }
    var mark = $('#mark');                     // the logo follows the look (his ask, 14 Oct); Python draws it, see brand.py
    if (mark && st.info && st.info.logos && st.info.logos[s.look]) mark.innerHTML = st.info.logos[s.look];
  }
  function change(key, value) {
    return api('set_setting', key, value).then(function (res) {
      st.settings = res.settings; applyLook();
      if (!res.ok && res.message) toast(res.message);
      return res;
    }).catch(fail);
  }

  // ---------- screens ----------
  var VIEWS = {}, WIRE = {};
  function placeholder(id) {
    var step = SCREENS.filter(function (s) { return s[0] === id; })[0][2];
    return '<h2 class="h">' + NAMES[id] + '</h2><div class="card stack"><div class="row sb"><span class="tag acc">Comes in step ' + step + '</span></div>' +
      '<ul class="points">' + PLAN[id].map(function (p) { return '<li>' + p + '</li>'; }).join('') + '</ul></div>';
  }


  // ---------- step 6: pictures & video ----------
  var MTABS = [['clips', 'Game clips'], ['convert', 'Convert'], ['vcomp', 'Compress video'], ['icomp', 'Compress picture'], ['resize', 'Resize'], ['format', 'Picture format'], ['clip', 'GIF / WebM'], ['upscale', 'Upscale (AI)'], ['crop', 'Crop'], ['batch', 'Many pictures'], ['sound', 'Sound']];   // Subtitles (whisper.cpp) hidden 15 Oct at his wish; its view below is kept but unreachable
  var MD = { tab: 'clips', file: null, clips: null, clipsBusy: false, filter: 'All', start: 0, end: 0, target: '10', plan: null, fmt: 'mp4',
    ifmt: 'webp', q: 78, lossless: false, prev: null, prevKey: '', preset: 'half', cw: '', ch: '', keep: true, pixel: false, pfmt: 'jpg', pq: 90,
    ckind: 'gif', cwidth: 480, cfps: 15, dither: 'bayer', what: 'picture', scale: 2, model: 'realesrgan-x4plus', gout: 'webp', vplan: null, models: null, thumbs: {},
    ratio: 'free', box: null, batch: [], bact: 'icomp', bthumbs: {}, bratio: '1:1', smode: 'cut', fin: 0, fout: 0, loud: 'spotify', slang: 'auto', str: false, sput: 'srt' };
  var CROP_RATIOS = [['free', 'Free'], ['1:1', 'Square'], ['16:9', '16:9'], ['9:16', '9:16', 'phone'], ['4:3', '4:3'], ['3:2', '3:2'], ['4:5', '4:5', 'Instagram'], ['3:1', '3:1', 'banner']];
  var LOUD = [['spotify', '−14 LUFS', 'Spotify, YouTube'], ['podcast', '−16', 'voice, podcasts'], ['loud', '−9', 'loud'], ['quiet', '−23', 'TV and film']];
  var SUB_LANGS = [['auto', 'Find out by itself'], ['en', 'English'], ['ja', 'Japanese'], ['nl', 'Dutch'], ['ko', 'Korean'], ['zh', 'Chinese'], ['es', 'Spanish'], ['de', 'German'], ['fr', 'French']];
  var CONVERT_OUT = [['mp4', 'MP4', 'plays everywhere'], ['webm', 'WebM', 'small, for the web'], ['mkv', 'MKV', 'keeps everything'], ['mov', 'MOV', 'Apple editors'],
    ['mp3', 'MP3', 'just the sound'], ['m4a', 'M4A', 'sound, smaller'], ['wav', 'WAV', 'sound, uncompressed'], ['opus', 'Opus', 'sound, smallest'], ['flac', 'FLAC', 'sound, lossless'], ['silent', 'No sound', 'sound taken out']];
  var RESIZE_OUT = [['half', '50%'], ['1920', '1920 wide'], ['1280', '1280 wide'], ['emoji', 'Discord emoji · 128'], ['sticker', 'Discord sticker · 320'], ['profile', 'Profile · 512'], ['mcskin', 'Minecraft skin · 64'], ['mcicon', 'Server icon · 64'], ['ico', 'Icon (.ico)'], ['custom', 'Custom…']];
  function mediaTake(promise, jump) {
    return promise.then(function (r) {
      if (!r.ok) { if (r.message) toast(r.message); return; }
      MD.file = r.file; MD.start = 0; MD.end = 0; MD.plan = null; MD.prev = null; MD.prevKey = ''; MD.vplan = null; MD.vt = 0;
      var k = r.file.kind;
      var fits = { video: ['convert', 'vcomp', 'clip', 'upscale', 'clips', 'sound'], gif: ['format', 'clip', 'upscale', 'convert'], picture: ['icomp', 'resize', 'format', 'upscale', 'crop', 'batch'], audio: ['convert', 'sound'] }[k] || [];
      if (jump || fits.indexOf(MD.tab) === -1) MD.tab = k === 'video' ? 'vcomp' : k === 'gif' ? 'upscale' : k === 'picture' ? 'icomp' : k === 'audio' ? 'sound' : MD.tab;
      MD.box = null;
      if (k === 'gif') MD.what = 'gif'; else if (k === 'video') { if (MD.tab === 'upscale') MD.what = 'video'; } else if (k === 'picture') MD.what = 'picture';
      go('media', true);
    }).catch(fail);
  }
  function mediaChips(list, key, attr) {
    return '<div class="row">' + list.map(function (x) { return '<button type="button" class="chip" data-' + attr + '="' + x[0] + '" aria-pressed="' + (MD[key] === x[0]) + '">' + x[1] + (x[2] ? ' <small>· ' + x[2] + '</small>' : '') + '</button>'; }).join('') + '</div>';
  }
  function fileCard() {
    var f = MD.file;
    if (!f) return '<div class="card drop stack" id="mdDrop" style="align-items:center;text-align:center;padding:22px"><b>Drop a video, a GIF, a song or a picture anywhere on Toolbelt</b><span class="muted">or</span><button type="button" class="btn" id="mdPick">Pick a file</button></div>';
    var facts = [fmtBytes(f.size)];
    if (f.duration) facts.push(fmtTime(f.duration));
    if (f.width) facts.push(f.width + ' × ' + f.height);
    if (f.fps) facts.push(f.fps + ' fps');
    if (f.vcodec) facts.push(f.vcodec.toUpperCase());
    var kinds = { video: 'video', gif: 'GIF', picture: 'picture', audio: 'sound', other: 'file' };
    var sugg = f.kind === 'video' ? [['vcomp', 'Shrink for Discord'], ['convert', 'Just the sound'], ['clip', 'Make a GIF'], ['upscale', 'Upscale it']] :
      f.kind === 'picture' ? [['icomp', 'Make it smaller'], ['resize', 'Resize'], ['crop', 'Crop'], ['upscale', 'Upscale it'], ['cut', 'Cut out the background']] :
      f.kind === 'gif' ? [['upscale', 'Sharpen it'], ['clip', 'Turn into WebM / MP4']] : f.kind === 'audio' ? [['sound', 'Cut or even out'], ['convert', 'Change the format']] : [];
    return '<div class="card row nw" style="align-items:center">' + (f.thumb ? '<img class="thumbimg sm" src="' + f.thumb + '" alt="">' : '<span class="badge">' + esc((f.name.split('.').pop() || '?').toUpperCase().slice(0, 4)) + '</span>') +
      '<div class="stack grow" style="gap:3px;min-width:0"><b class="ell">' + esc(f.name) + '</b><span class="muted">' + esc(kinds[f.kind] || f.kind) + ' · ' + facts.join(' · ') + '</span>' +
      (sugg.length ? '<div class="row">' + sugg.map(function (s) { return '<button type="button" class="chip" data-sugg="' + s[0] + '">' + s[1] + '</button>'; }).join('') + '</div>' : '') + '</div>' +
      (f.kind === 'video' || f.kind === 'gif' ? '<button type="button" class="btn sm" id="mdWatch" title="Watch it here, full window">▶ Watch</button>' : '') +
      '<button type="button" class="btn ghost sm" id="mdPick">Change</button></div>';
  }
  function needFile(kinds, what) {
    var f = MD.file;
    if (f && kinds.indexOf(f.kind) !== -1) return '';
    return '<div class="card"><span class="muted">' + (f ? 'That\'s a ' + f.kind + '. ' : '') + 'Pick ' + what + ' first (drop it anywhere, or use Pick a file above).</span></div>';
  }
  // ---------- videos inside Toolbelt (his asks, 15 Oct): a player that cuts while you watch, a full-window player, and
  // before / after. Python answers the video's address inside the window (viewer.py); nothing is served or uploaded. ----------
  var VPS = { urls: {}, proxyJob: {} };
  function mediaUrl(token) {                                   // the address to play a picked file from (asked once per file)
    if (VPS.urls[token]) return Promise.resolve(VPS.urls[token]);
    return api('media_url', token).then(function (r) { if (r && r.ok) { VPS.urls[token] = r.url; return r.url; } throw new Error((r && r.message) || 'No player address.'); });
  }
  function playerHtml(id, cut) {
    return '<div class="vp' + (cut ? ' cut' : '') + '" id="' + id + '" tabindex="0" aria-label="Video player">' +
      '<div class="vp-stage"><video playsinline preload="auto"></video><div class="vp-msg" hidden></div><button type="button" class="vp-big" aria-label="Play">▶</button></div>' +
      '<div class="vp-bar"><button type="button" class="vp-btn vp-play" aria-label="Play">▶</button><span class="vp-time">0:00 / 0:00</span>' +
      '<div class="vp-track" role="slider" aria-label="Position" tabindex="-1"><div class="vp-buf"></div>' + (cut ? '<div class="vp-sel"></div><span class="vp-h vp-in" title="From: drag me" aria-label="From"></span><span class="vp-h vp-out" title="To: drag me" aria-label="To"></span>' : '') + '<div class="vp-head"></div></div>' +
      '<button type="button" class="vp-btn vp-rate" title="Speed">1×</button><button type="button" class="vp-btn vp-mute" aria-label="Sound on or off">🔊</button><button type="button" class="vp-btn vp-full" aria-label="Full screen" title="Full screen">⛶</button></div>' +
      (cut ? '<div class="row vp-cut"><button type="button" class="btn ghost sm vp-in-btn" title="Key: I">[ From here</button><button type="button" class="btn ghost sm vp-out-btn" title="Key: O">To here ]</button>' +
        '<button type="button" class="btn ghost sm vp-piece" title="Key: P">▶ Play the piece</button><span class="muted vp-keys">Space play · ← → one frame · Shift + ← → one second · I / O set From / To</span></div>' : '') + '</div>';
  }
  // opts: {token, url, start, end, duration, fps, onRange(start, end, done), time (where to begin)}
  function playerAttach(root, opts) {
    if (!root) return null;
    var v = $('video', root), track = $('.vp-track', root), head = $('.vp-head', root), msg = $('.vp-msg', root);
    var cut = root.classList.contains('cut'), dur = opts.duration || 0, fps = opts.fps || 30, st0 = opts.start || 0, en0 = opts.end || 0;
    var pieceStop = null, rates = [1, 1.5, 2, 0.5, 0.25], ri = 0;
    function D() { return dur || v.duration || 0; }
    function E() { return en0 > st0 ? en0 : D(); }
    function pct(t) { return D() ? Math.max(0, Math.min(100, t / D() * 100)) : 0; }
    function paint() {
      head.style.left = pct(v.currentTime) + '%';
      $('.vp-time', root).textContent = fmtTime(v.currentTime) + ' / ' + fmtTime(D());
      var pl = v.paused ? '▶' : '❚❚'; $('.vp-play', root).textContent = pl; $('.vp-play', root).setAttribute('aria-label', v.paused ? 'Play' : 'Pause');
      $('.vp-big', root).hidden = !v.paused;
      if (v.buffered && v.buffered.length) $('.vp-buf', root).style.width = pct(v.buffered.end(v.buffered.length - 1)) + '%';
      if (cut) { $('.vp-sel', root).style.left = pct(st0) + '%'; $('.vp-sel', root).style.width = (pct(E()) - pct(st0)) + '%'; $('.vp-h.vp-in', root).style.left = pct(st0) + '%'; $('.vp-h.vp-out', root).style.left = pct(E()) + '%'; }
      if (opts.onTime) opts.onTime(v.currentTime);
    }
    function setRange(a, b, done) {
      a = Math.max(0, Math.min(a, D())); b = Math.max(0, Math.min(b, D()));
      if (b < a) { var t = a; a = b; b = t; }
      st0 = a; en0 = b >= D() - 0.05 ? 0 : b;
      paint();
      if (opts.onRange) opts.onRange(st0, en0, !!done);
    }
    function seek(t) { v.currentTime = Math.max(0, Math.min(t, D() || t)); paint(); }
    function toggle() { if (v.paused) { pieceStop = null; v.play().catch(function () {}); } else v.pause(); }
    function timeAt(e) { var r = track.getBoundingClientRect(); return D() * Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); }
    function drag(e, what) {
      e.preventDefault();
      var move = function (ev) {
        var t = timeAt(ev);
        if (what === 'in') { setRange(t, E(), false); seek(t); }             // the picture follows the handle: you SEE the cut
        else if (what === 'out') { setRange(st0, t, false); seek(t); }
        else seek(t);
      };
      var up = function (ev) { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); if (what !== 'seek') setRange(st0, E(), true); };
      document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
      move(e);
    }
    track.onpointerdown = function (e) { var h = e.target.classList && e.target.classList.contains('vp-h') ? (e.target.classList.contains('vp-in') ? 'in' : 'out') : 'seek'; drag(e, h); };
    $('.vp-play', root).onclick = toggle; $('.vp-big', root).onclick = toggle; v.onclick = toggle;
    $('.vp-rate', root).onclick = function () { ri = (ri + 1) % rates.length; v.playbackRate = rates[ri]; this.textContent = rates[ri] + '×'; };
    $('.vp-mute', root).onclick = function () { v.muted = !v.muted; this.textContent = v.muted ? '🔇' : '🔊'; };
    $('.vp-full', root).onclick = function () { if (document.fullscreenElement) document.exitFullscreen(); else if (root.requestFullscreen) root.requestFullscreen(); };
    if (cut) {
      $('.vp-in-btn', root).onclick = function () { setRange(v.currentTime, E(), true); };
      $('.vp-out-btn', root).onclick = function () { setRange(st0, v.currentTime, true); };
      $('.vp-piece', root).onclick = function () { seek(st0); pieceStop = E(); v.play().catch(function () {}); };
    }
    root.onkeydown = function (e) {
      if (e.target.tagName === 'INPUT') return;
      var step = e.shiftKey ? 1 : 1 / fps, k = e.key.toLowerCase();
      if (e.key === ' ') { e.preventDefault(); toggle(); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); v.pause(); seek(v.currentTime + step); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); v.pause(); seek(v.currentTime - step); }
      else if (cut && k === 'i') setRange(v.currentTime, E(), true);
      else if (cut && k === 'o') setRange(st0, v.currentTime, true);
      else if (cut && k === 'p') $('.vp-piece', root).click();
      else if (k === 'f') $('.vp-full', root).click();
    };
    v.ontimeupdate = function () { if (pieceStop !== null && v.currentTime >= pieceStop) { v.currentTime = st0; } paint(); };   // the piece loops
    v.onplay = v.onpause = v.onprogress = v.onseeked = paint;
    v.onloadedmetadata = function () { if (!dur) dur = v.duration; if (opts.time) v.currentTime = opts.time; else if (st0) v.currentTime = st0; paint(); };
    v.onerror = function () {                                // a codec this WebView2 can't play: make a light copy once
      if (!opts.token || VPS.proxyJob[opts.token] === 'done') { msg.hidden = false; msg.textContent = 'This video can\'t play inside Toolbelt.'; return; }
      msg.hidden = false; msg.textContent = 'This video uses a codec Toolbelt can\'t play directly: making a playable copy (once)…';
      api('media_proxy', opts.token).then(function (r) { if (r.ok) { VPS.proxyJob[opts.token] = r.id; pollJobs(); } }).catch(fail);
    };
    v.src = opts.url;
    return { video: v, seek: seek, setRange: setRange, paint: paint };
  }
  function playerProxyTick() {                               // called from pollJobs: a playable copy got ready
    Object.keys(VPS.proxyJob).forEach(function (token) {
      var id = VPS.proxyJob[token]; if (id === 'done') return;
      var j = st.jobs.filter(function (x) { return x.id === id; })[0];
      if (j && j.state === 'done' && j.extra.url) { VPS.proxyJob[token] = 'done'; VPS.urls[token] = j.extra.url; if (st.screen === 'media') go('media', true); }
    });
  }
  // the full-window player: "watch it inside Toolbelt"
  function openWatch(token, title) {
    mediaUrl(token).then(function (url) {
      var old = $('#vpDim'); if (old) old.remove();
      var dim = document.createElement('div'); dim.className = 'dim vpdim'; dim.id = 'vpDim';
      dim.innerHTML = '<div class="dialog watch" role="dialog" aria-modal="true" aria-label="' + esc(title) + '"><div class="row sb"><b class="ell">' + esc(title) + '</b><button type="button" class="ico" id="vpX" aria-label="Close">✕</button></div>' + playerHtml('vpWatch', false) + '</div>';
      $('#app').appendChild(dim);
      var p = playerAttach($('#vpWatch', dim), { url: url, token: token });
      var close = function () { if (p) p.video.pause(); dim.remove(); };
      $('#vpX', dim).onclick = close;
      dim.onclick = function (e) { if (e.target === dim) close(); };
      dim.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !document.fullscreenElement) close(); });
      $('#vpWatch', dim).focus();
      p.video.play().catch(function () {});
    }).catch(fail);
  }
  // before / after of a finished job: the slider over two synced videos (or two pictures), with zoom to look closely
  function openCompare(jobId) {
    api('media_compare', jobId).then(function (r) {
      if (!r.ok) { toast(r.message); return; }
      var b = r.before, a = r.after, vid = r.kind === 'video';
      var tag = function (x, word) { return word + ' · ' + (x.width ? x.width + ' × ' + x.height + ' · ' : '') + fmtSize(x.size); };
      var media1 = function (x, cls) { return vid ? '<video class="' + cls + '" src="' + x.url + '" muted playsinline preload="auto"></video>' : '<img class="' + cls + '" src="' + x.url + '" alt="">'; };
      var old = $('#vpDim'); if (old) old.remove();
      var dim = document.createElement('div'); dim.className = 'dim vpdim'; dim.id = 'vpDim';
      var ratio = a.width && a.height ? a.width + '/' + a.height : '16/9';
      dim.innerHTML = '<div class="dialog watch" role="dialog" aria-modal="true" aria-label="Before and after"><div class="row sb"><b>Before / after</b><div class="row"><button type="button" class="chip" id="cmpZoom" aria-pressed="false">Zoom 1×</button><button type="button" class="ico" id="vpX" aria-label="Close">✕</button></div></div>' +
        '<div class="ba cmp" id="cmpBox" style="aspect-ratio:' + ratio + '"><div class="ba-layer">' + media1(b, 'cmp-b') + '</div><div class="ba-layer ba-after">' + media1(a, 'cmp-a') + '</div><span class="ba-line"></span>' +
        '<input type="range" class="ba-range" min="0" max="100" value="50" aria-label="Slide between before and after"><span class="ba-tag l">' + esc(tag(b, 'Before')) + '</span><span class="ba-tag r">' + esc(tag(a, 'After')) + '</span></div>' +
        (vid ? '<div class="vp-bar cmpbar"><button type="button" class="vp-btn vp-play" aria-label="Play">▶</button><span class="vp-time">0:00</span><input type="range" class="grow" id="cmpSeek" min="0" max="1000" value="0" aria-label="Position"></div>' : '') +
        '<span class="muted">Drag across the picture to compare' + (vid ? '; both play in step' : '') + '. Zoom looks closer where your mouse is.</span></div>';
      $('#app').appendChild(dim);
      var box = $('#cmpBox', dim), range = $('.ba-range', box), zoom = 1;
      range.oninput = function () { box.style.setProperty('--cut', range.value + '%'); };
      box.onmousemove = function (e) { if (zoom === 1) return; var rc = box.getBoundingClientRect(); box.style.setProperty('--ox', ((e.clientX - rc.left) / rc.width * 100).toFixed(1) + '%'); box.style.setProperty('--oy', ((e.clientY - rc.top) / rc.height * 100).toFixed(1) + '%'); };
      $('#cmpZoom', dim).onclick = function () { zoom = zoom === 1 ? 2 : zoom === 2 ? 4 : 1; box.style.setProperty('--z', zoom); this.textContent = 'Zoom ' + zoom + '×'; this.setAttribute('aria-pressed', String(zoom > 1)); };
      var close = function () { $$('video', dim).forEach(function (x) { x.pause(); }); dim.remove(); };
      $('#vpX', dim).onclick = close;
      dim.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
      if (vid) {
        var va = $('.cmp-a', dim), vb = $('.cmp-b', dim), seekBar = $('#cmpSeek', dim), off = r.start || 0;
        var sync = function () { var want = va.currentTime + off; if (Math.abs(vb.currentTime - want) > 0.08) vb.currentTime = want; };
        var paintC = function () { $('.vp-time', dim).textContent = fmtTime(va.currentTime) + ' / ' + fmtTime(va.duration || 0); if (va.duration) seekBar.value = Math.round(va.currentTime / va.duration * 1000); $('.vp-play', dim).textContent = va.paused ? '▶' : '❚❚'; };
        $('.vp-play', dim).onclick = function () { if (va.paused) { sync(); va.play().catch(function () {}); vb.play().catch(function () {}); } else { va.pause(); vb.pause(); } paintC(); };
        seekBar.oninput = function () { if (va.duration) { va.currentTime = seekBar.value / 1000 * va.duration; sync(); } };
        va.ontimeupdate = function () { sync(); paintC(); };
        va.onloadedmetadata = function () { vb.currentTime = off; paintC(); };
        va.onended = function () { vb.pause(); paintC(); };
      }
      box.focus();
    }).catch(fail);
  }
  function rangeRow() {
    var f = MD.file, d = f && f.duration || 0;
    if (!d) return '';
    var end = MD.end || d;
    return '<div class="card stack"><div class="row sb"><b>Which piece</b><span class="muted" id="mdRangeText">' + fmtTime(MD.start) + ' → ' + fmtTime(end) + ' · ' + fmtTime(end - MD.start) + '</span></div>' +
      (f.kind === 'video' ? playerHtml('mdPlayer', true) : '') +
      '<div class="row nw"><label class="muted" for="mdFrom">From</label><input id="mdFrom" type="range" min="0" max="' + Math.floor(d * 10) + '" value="' + Math.floor(MD.start * 10) + '" class="grow" aria-label="From">' +
      '<label class="muted" for="mdTo">to</label><input id="mdTo" type="range" min="0" max="' + Math.floor(d * 10) + '" value="' + Math.floor(end * 10) + '" class="grow" aria-label="To"></div>' +
      '<div class="row"><button type="button" class="btn ghost sm" id="mdWhole">Whole video</button><button type="button" class="btn ghost sm" id="mdTrim">Save just this piece (no re-encoding, cuts snap to keyframes)</button></div></div>';
  }
  function mediaDone() {
    return '<div id="mdDone"></div>';
  }
  function renderMediaDone() {
    var box = $('#mdDone'); if (!box || st.screen !== 'media') return;
    var jobs = st.jobs.filter(function (j) { return j.kind === 'Media'; }).slice(0, 8);
    var sig = jobs.map(function (j) { return j.id + j.state + Math.round(j.progress) + (j.message || ''); }).join('|');
    if (box.getAttribute('data-sig') === sig) return;
    box.setAttribute('data-sig', sig);
    box.innerHTML = jobs.length ? '<span class="lbl">Work</span><div class="list">' + jobs.map(function (j) {
      var x = j.extra || {};
      var state = j.state === 'done' ? '<span class="okc">done</span>' + (x.count ? ' <span class="muted">· ' + x.count + ' picture' + (x.count === 1 ? '' : 's') + ' · ' + fmtBytes(x.before) + ' → ' + fmtBytes(x.size) + (x.failed && x.failed.length ? ' · ' + x.failed.length + ' skipped' : '') + '</span>' : x.after ? ' <span class="muted">· ' + x.before + ' → ' + x.after + ' LUFS</span>' : x.size ? ' <span class="muted">· ' + fmtBytes(x.size) + (x.width ? ' · ' + x.width + ' × ' + x.height : '') + (x.srt && x.srt !== x.path ? ' · plus an .srt' : '') + '</span>' : '') :
        j.state === 'failed' ? '<span class="badc">' + esc(j.message) + '</span>' : j.state === 'cancelled' ? '<span class="muted">cancelled</span>' : '<span class="warnc">' + Math.round(j.progress) + '%</span> <span class="muted">· ' + esc(j.message || 'waiting') + '</span>';
      return '<div class="item"><span class="badge" style="width:26px;height:26px;font-size:11px">' + (j.state === 'done' ? '✓' : j.state === 'failed' ? '!' : '…') + '</span><div class="stack" style="gap:2px;min-width:0"><b class="ell">' + esc(j.title) + '</b><span>' + state + '</span></div>' +
        (j.state === 'done' && x.path ? '<div class="row">' + (['upscale', 'upscale_video', 'sharpen_gif', 'compress', 'discord', 'icomp', 'resize', 'format'].indexOf(x.action) !== -1 ? '<button type="button" class="btn ghost sm" data-cmp="' + j.id + '">Before / after</button>' : '') +
          '<button type="button" class="btn ghost sm" data-show="' + esc(x.path) + '">Show in folder</button></div>' : j.state === 'running' || j.state === 'waiting' ? '<button type="button" class="btn ghost sm" data-cancel="' + j.id + '">Cancel</button>' : '<span></span>') + '</div>';
    }).join('') + '</div>' : '';
    $$('[data-show]', box).forEach(function (b) { b.onclick = function () { api('show_file', b.getAttribute('data-show')).then(function (r) { if (!r.ok) toast(r.message); }).catch(fail); }; });
    $$('[data-cancel]', box).forEach(function (b) { b.onclick = function () { api('cancel_job', +b.getAttribute('data-cancel')).catch(fail); }; });
    $$('[data-cmp]', box).forEach(function (b) { b.onclick = function () { openCompare(+b.getAttribute('data-cmp')); }; });
  }
  function mediaStart(action, options, title) {
    if (!MD.file) { toast('Pick a file first.'); return; }
    api('media_job', MD.file.token, action, options || {}).then(function (r) { toast(r.ok ? 'Started: ' + (title || action) : r.message); pollJobs(); }).catch(fail);
  }
  function rangeOpts(extra) { var o = extra || {}; if (MD.end > MD.start) { o.start = MD.start; o.end = MD.end; } else if (MD.start > 0) { o.start = MD.start; o.end = MD.file.duration; } return o; }
  VIEWS.media = function () {
    var f = MD.file, body = '';
    if (MD.tab === 'clips') {
      var c = MD.clips;
      var sources = ['All'].concat((c || []).map(function (x) { return x.source; }).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort());
      var shown = (c || []).filter(function (x) { return MD.filter === 'All' || x.source === MD.filter; });
      body = '<div class="row sb"><span class="muted">' + (c === null ? 'Looking for recordings…' : c.length + ' recording' + (c.length === 1 ? '' : 's') + ' in your Videos folders · newest first') + '</span>' +
        '<div class="row">' + sources.map(function (s) { return '<button type="button" class="chip" data-cfilter="' + esc(s) + '" aria-pressed="' + (MD.filter === s) + '">' + esc(s) + '</button>'; }).join('') + '<button type="button" class="btn ghost sm" id="mdClipsRefresh">Look again</button></div></div>' +
        (c && !c.length ? '<div class="card"><span class="muted">No recordings found. Toolbelt looks in Videos (Radeon ReLive, Captures) and OneDrive\\Video\'s.</span></div>' : '') +
        '<div class="mgrid">' + shown.map(function (x) {
          var th = MD.thumbs[x.token];
          return '<button type="button" class="mclip lift" data-clip="' + esc(x.token) + '"' + (th ? ' style="background-image:url(' + th + ')"' : '') + '><span class="tag" style="position:absolute;right:6px;top:6px">' + fmtBytes(x.size) + '</span><b class="ell">' + esc(x.game || x.name) + '</b><small>' + esc(x.source) + ' · ' + esc(x.when.slice(0, 10)) + '</small></button>';
        }).join('') + '</div>' +
        (f && f.kind === 'video' ? rangeRow() + '<div class="card stack"><b>' + esc(f.name) + '</b><div class="row"><button type="button" class="btn" id="mdDiscord">Send to Discord (10 MB)</button><button type="button" class="btn ghost" data-sugg="clip">Make a GIF</button><button type="button" class="btn ghost" data-sugg="upscale">Upscale</button></div></div>' : '');
    } else if (MD.tab === 'convert') {
      body = needFile(['video', 'audio', 'gif'], 'a video or a song') || ('<span class="lbl">Turn it into</span>' + mediaChips(CONVERT_OUT.filter(function (x) { return f.kind !== 'audio' || ['mp3', 'm4a', 'wav', 'opus', 'flac'].indexOf(x[0]) !== -1; }), 'fmt', 'fmt') +
        '<div class="row sb"><span class="muted">' + (['mkv', 'mp4', 'mov'].indexOf(MD.fmt) !== -1 ? 'Repacked without re-encoding when the codecs allow it: no quality lost, fast' : MD.fmt === 'silent' ? 'Same video, the sound track taken out' : 'Re-encoded; takes a while for long videos') + '</span><button type="button" class="btn" id="mdConvert">Convert</button></div>');
    } else if (MD.tab === 'vcomp') {
      var p = MD.plan;
      body = needFile(['video'], 'a video') || (rangeRow() + '<span class="lbl">Fit under</span>' + mediaChips([['10', '10 MB', 'Discord'], ['25', '25 MB'], ['50', '50 MB'], ['100', '100 MB'], ['500', '500 MB']], 'target', 'target') +
        '<div class="card" id="mdPlan">' + (p ? (p.fits ? '<b>Result: about ' + p.mb + ' MB</b> <span class="muted">· ' + p.height + 'p' + (p.scale ? ' (scaled down)' : '') + ' · ' + (p.audio_kbps ? 'sound kept' : 'no sound') + (p.percent > 0 ? ' · ' + p.percent + '% smaller' : '') + '</span>' : '<span class="badc">Too long for ' + p.mb + ' MB: trim it or pick a bigger size</span>') : '<span class="muted">Working it out…</span>') + '</div>' +
        '<div class="row"><button type="button" class="btn" id="mdCompress"' + (p && !p.fits ? ' disabled' : '') + '>Compress</button></div>');
    } else if (MD.tab === 'icomp') {
      var pv = MD.prev;
      body = needFile(['picture'], 'a picture') || ('<div class="ba" id="mdBa" style="max-width:640px;aspect-ratio:' + (f.width && f.height ? f.width + '/' + f.height : '4/3') + '">' + (pv ? '<div class="ba-layer"><img src="' + pv.before + '" alt="Original"></div><div class="ba-layer ba-after"><img src="' + pv.preview + '" alt="Compressed"></div><span class="ba-line"></span><input type="range" class="ba-range" min="0" max="100" value="50" aria-label="Slide between original and compressed"><span class="ba-tag l">Original ' + fmtBytes(pv.original) + '</span><span class="ba-tag r">' + MD.ifmt.toUpperCase() + ' ' + fmtBytes(pv.size) + '</span>' : '<span class="muted" style="position:absolute;inset:0;display:grid;place-items:center">Making a preview…</span>') + '</div>' +
        mediaChips([['webp', 'WebP'], ['jpg', 'JPG'], ['avif', 'AVIF', 'smallest, newer'], ['png', 'PNG', '256 colours']], 'ifmt', 'ifmt') +
        '<div class="row"><label class="muted" for="mdQ">Quality</label><input id="mdQ" type="range" min="30" max="100" value="' + MD.q + '" class="grow"><span class="muted" id="mdQv">' + MD.q + '</span><button type="button" class="btn" id="mdIcomp">Save</button></div>' +
        (pv ? '<span class="muted">' + (pv.size < pv.original ? Math.round(100 - 100 * pv.size / pv.original) + '% smaller' : 'Not smaller than the original: try another format or a lower quality') + '</span>' : ''));
    } else if (MD.tab === 'resize') {
      body = needFile(['picture'], 'a picture') || ('<span class="lbl">To</span>' + mediaChips(RESIZE_OUT, 'preset', 'preset') +
        (MD.preset === 'custom' ? '<div class="row"><input class="field" id="mdW" inputmode="numeric" placeholder="width" value="' + esc(MD.cw) + '" style="width:110px" aria-label="Width"><span class="muted">×</span><input class="field" id="mdH" inputmode="numeric" placeholder="height" value="' + esc(MD.ch) + '" style="width:110px" aria-label="Height"><span class="muted">pixels (leave one empty to keep the shape)</span></div>' : '') +
        '<div class="row nw">' + sw('mdKeep', MD.keep, 'Keep the shape (no stretching)') + '<span>Keep the shape (no stretching)</span></div><div class="row nw">' + sw('mdPixel', MD.pixel, 'Pixel art: keep it sharp') + '<span>Pixel art: keep it sharp</span></div>' +
        '<div class="row sb"><span class="muted">' + f.width + ' × ' + f.height + ' now' + (MD.preset === 'emoji' || MD.preset === 'sticker' || MD.preset === 'profile' || MD.preset === 'mcicon' ? ' · padded to a square, see-through edges' : '') + '</span><button type="button" class="btn" id="mdResize">Resize</button></div>');
    } else if (MD.tab === 'format') {
      body = needFile(['picture', 'gif'], 'a picture') || ('<span class="lbl">Make it a</span>' + mediaChips([['jpg', 'JPG'], ['png', 'PNG'], ['webp', 'WebP'], ['avif', 'AVIF'], ['gif', 'GIF'], ['bmp', 'BMP'], ['tiff', 'TIFF'], ['ico', 'Icon (.ico)']], 'pfmt', 'pfmt') +
        '<div class="row sb"><span class="muted">' + (MD.pfmt === 'jpg' || MD.pfmt === 'webp' || MD.pfmt === 'avif' ? 'Saved at quality 90' : MD.pfmt === 'ico' ? 'All sizes from 16 to 256 px in one file' : 'Lossless') + '</span><button type="button" class="btn" id="mdFormat">Convert</button></div>');
    } else if (MD.tab === 'clip') {
      body = needFile(['video', 'gif'], 'a video') || (rangeRow() + '<span class="lbl">As</span>' + mediaChips([['gif', 'GIF', 'works everywhere, big'], ['webp', 'Animated WebP', 'better colours, small'], ['webm', 'WebM', 'smallest'], ['mp4', 'Looping MP4', 'Discord plays it']], 'ckind', 'ckind') +
        '<span class="lbl">Width</span>' + mediaChips([[320, '320 px'], [480, '480 px'], [640, '640 px'], [720, '720 px']], 'cwidth', 'cwidth') + '<span class="lbl">Frames per second</span>' + mediaChips([[10, '10'], [15, '15'], [20, '20'], [30, '30']], 'cfps', 'cfps') +
        (MD.ckind === 'gif' ? mediaChips([['bayer', 'Crisp dots'], ['smooth', 'Smooth colours', 'bigger file']], 'dither', 'dither') : '') +
        '<div class="row sb"><span class="muted">' + (MD.ckind === 'gif' ? 'GIF holds 256 colours; under a minute' : 'No sound in clips') + '</span><button type="button" class="btn" id="mdClip">Make it</button></div>');
    } else if (MD.tab === 'crop') {
      body = needFile(['picture'], 'a picture') || ('<span class="lbl">Shape</span>' + mediaChips(CROP_RATIOS, 'ratio', 'ratio') +
        '<div><div class="cropbox" id="mdCrop"><img id="mdCropImg" src="' + f.thumb + '" alt="The picture to crop" draggable="false"><div class="croprect" id="mdCropRect" hidden></div></div></div>' +
        '<div class="row sb"><span class="muted" id="mdCropTxt">Drag on the picture to draw the part to keep; drag the box to move it</span><div class="row"><button type="button" class="btn ghost sm" id="mdCropAll">Whole picture</button><button type="button" class="btn" id="mdCropGo">Save the crop</button></div></div>');
    } else if (MD.tab === 'batch') {
      var bl = MD.batch, total = bl.reduce(function (a, x) { return a + x.size; }, 0), opts = '';
      if (MD.bact === 'icomp') opts = mediaChips([['webp', 'WebP'], ['jpg', 'JPG'], ['avif', 'AVIF', 'smallest'], ['png', 'PNG', '256 colours']], 'ifmt', 'ifmt') +
        '<div class="row"><label class="muted" for="mbQ">Quality</label><input id="mbQ" type="range" min="30" max="100" value="' + MD.q + '" class="grow"><span class="muted" id="mbQv">' + MD.q + '</span></div>';
      else if (MD.bact === 'resize') opts = mediaChips(RESIZE_OUT.filter(function (x) { return x[0] !== 'custom'; }), 'preset', 'preset') + '<div class="row nw">' + sw('mdPixel', MD.pixel, 'Pixel art: keep it sharp') + '<span>Pixel art: keep it sharp</span></div>';
      else if (MD.bact === 'format') opts = mediaChips([['jpg', 'JPG'], ['png', 'PNG'], ['webp', 'WebP'], ['avif', 'AVIF'], ['bmp', 'BMP'], ['tiff', 'TIFF'], ['ico', 'Icon (.ico)']], 'pfmt', 'pfmt');
      else opts = mediaChips(CROP_RATIOS.filter(function (x) { return x[0] !== 'free'; }), 'bratio', 'bratio') + '<span class="muted">The biggest part of that shape from the middle of each picture.</span>';
      body = '<div class="row"><button type="button" class="btn" id="mbFiles">Pick pictures</button><button type="button" class="btn ghost" id="mbFolder">Pick a folder</button>' + (bl.length ? '<button type="button" class="btn ghost sm" id="mbClear">Clear</button>' : '') +
        '<span class="muted">' + (bl.length ? bl.length + ' picture' + (bl.length === 1 ? '' : 's') + ' · ' + fmtBytes(total) : 'Ctrl or Shift picks several; a folder takes every picture in it, iPhone HEIC photos too') + '</span></div>' +
        (bl.length ? '<div class="mbgrid">' + bl.slice(0, 120).map(function (x, i) {
          var t = MD.bthumbs[x.token];
          return '<div class="mbitem" data-mbt="' + esc(x.token) + '" title="' + esc(x.name) + '"' + (t ? ' style="background-image:url(' + t + ')"' : '') + '><button type="button" class="ico" data-mbx="' + i + '" aria-label="Leave ' + esc(x.name) + ' out">✕</button></div>';
        }).join('') + (bl.length > 120 ? '<span class="muted">and ' + (bl.length - 120) + ' more</span>' : '') + '</div>' : '') +
        '<span class="lbl">Do this to all of them</span>' + mediaChips([['icomp', 'Compress'], ['resize', 'Resize'], ['format', 'Convert'], ['crop', 'Crop to a shape']], 'bact', 'bact') + opts +
        '<div class="row sb"><span class="muted">They go together in one new folder; the originals stay as they are.</span><button type="button" class="btn" id="mbGo"' + (bl.length ? '' : ' disabled') + '>Do it to ' + (bl.length || 'the') + ' picture' + (bl.length === 1 ? '' : 's') + '</button></div>';
    } else if (MD.tab === 'sound') {
      body = needFile(['audio', 'video'], 'a song or a video') || (mediaChips([['cut', 'Cut a piece'], ['loud', 'Even out the loudness']], 'smode', 'smode') + (MD.smode === 'cut' ?
        (f.kind === 'audio' ? '<audio id="mdAudio" controls preload="metadata" style="width:100%"></audio>' : '') + rangeRow() +
        '<span class="lbl">Fade in</span>' + mediaChips([[0, 'None'], [1, '1 s'], [3, '3 s']], 'fin', 'fin') + '<span class="lbl">Fade out</span>' + mediaChips([[0, 'None'], [1, '1 s'], [3, '3 s'], [5, '5 s']], 'fout', 'fout') +
        '<div class="row sb"><span class="muted">' + (f.kind === 'video' ? 'The picture comes along; the cut is exact (it\'s re-encoded)' : 'Saved in the same format, with its cover and tags') + '</span><button type="button" class="btn" id="mdCutSound">Cut</button></div>' :
        '<span class="lbl">Make it as loud as</span>' + mediaChips(LOUD, 'loud', 'loud') +
        '<div class="row sb"><span class="muted">Listens first, then evens it out in one go, so it never clips.' + (f.kind === 'video' ? ' The picture is copied untouched.' : '') + '</span><button type="button" class="btn" id="mdLoud">Even it out</button></div>'));
    } else if (MD.tab === 'subs') {
      var wh = st.engines ? st.engines.engines.filter(function (x) { return x.id === 'whisper' || x.id === 'whispermodel'; }) : [];
      if (wh.length && wh.some(function (x) { return !x.installed; })) body = '<div class="card stack"><b>Needs whisper.cpp and its model</b><span class="muted">The speech-to-text engine (about 70 MB) and the large-v3-turbo model (575 MB), both checked against their fingerprints. They run on your own PC; nothing is sent anywhere.</span><div class="row"><button type="button" class="btn" id="mdWhisper"' + (engineJobs().length ? ' disabled' : '') + '>' + (engineJobs().length ? 'Installing…' : 'Install them') + '</button></div></div>';
      else body = needFile(['video', 'audio'], 'a video or a song') || ('<span class="lbl">They speak</span>' + mediaChips(SUB_LANGS, 'slang', 'slang') +
        '<div class="row nw">' + sw('mdTr', MD.str, 'Translate to English') + '<span>Translate to English</span></div>' +
        (f.kind === 'video' ? '<span class="lbl">Put them</span>' + mediaChips([['srt', 'Only an .srt file', 'for players and editors'], ['track', 'As a subtitle track', 'switch on and off'], ['burn', 'In the picture', 'always visible, for Discord']], 'sput', 'sput') : '') +
        '<div class="row sb"><span class="muted">Runs on your own PC, no internet. Roughly ' + fmtTime(Math.max(20, (f.duration || 60) * 0.4 + 10)) + ' for this one; you can keep working meanwhile.</span><button type="button" class="btn" id="mdSubs">Make subtitles</button></div>');
    } else {
      var ms = MD.models, inst = ms && ms.installed, vp = MD.vplan;
      var what = mediaChips([['picture', 'Picture'], ['gif', 'GIF'], ['video', 'Video']], 'what', 'what');
      if (ms && !inst) body = what + '<div class="card stack"><b>Needs Real-ESRGAN</b><span class="muted">About 45 MB from its official GitHub release, checked against its fingerprint. It runs on your graphics card.</span><div class="row"><button type="button" class="btn" id="mdInstall"' + (engineJobs().length ? ' disabled' : '') + '>' + (engineJobs().length ? 'Installing…' : 'Install Real-ESRGAN') + '</button></div></div>';
      else if (MD.what === 'picture') body = what + (needFile(['picture'], 'a picture') || ('<span class="lbl">Model</span>' + mediaChips((ms ? ms.models : []).map(function (m) { return [m.id, m.for, m.note]; }), 'model', 'model') + '<span class="lbl">Make it</span>' + mediaChips([[2, '2×'], [3, '3×'], [4, '4×']], 'scale', 'scale') +
        '<div class="row sb"><span class="muted">' + f.width + ' × ' + f.height + ' → ' + (f.width * MD.scale) + ' × ' + (f.height * MD.scale) + ' · it guesses detail, it can\'t recover it</span><button type="button" class="btn" id="mdUp">Upscale</button></div>'));
      else if (MD.what === 'gif') body = what + (needFile(['gif'], 'a GIF') || ('<div class="list"><div class="item"><span class="okc">1</span><span>Take it apart into ' + (f.frames || '') + ' frames</span><span class="muted">ffmpeg</span></div><div class="item"><span class="okc">2</span><span>Sharpen and enlarge every frame (the anime video model)</span><span class="muted">Real-ESRGAN</span></div><div class="item"><span class="okc">3</span><span>Put it back together</span><span class="muted">ffmpeg</span></div></div>' +
        '<span class="lbl">Make it</span>' + mediaChips([[2, '2×'], [3, '3×'], [4, '4×']], 'scale', 'scale') + '<span class="lbl">Save as</span>' + mediaChips([['webp', 'Animated WebP', 'best colours'], ['gif', 'GIF', '256 colours'], ['mp4', 'Looping MP4', 'smallest']], 'gout', 'gout') + (MD.gout === 'gif' ? mediaChips([['bayer', 'Crisp dots'], ['smooth', 'Smooth colours']], 'dither', 'dither') : '') +
        '<div class="row sb"><span class="muted">' + f.width + ' × ' + f.height + ' → ' + (f.width * MD.scale) + ' × ' + (f.height * MD.scale) + '</span><button type="button" class="btn" id="mdSharpen">Sharpen GIF</button></div>'));
      else body = what + (needFile(['video'], 'a video') || (rangeRow() + '<span class="lbl">Model</span>' + mediaChips([['realesr-animevideov3', 'Games and anime', 'fast'], ['realesrgan-x4plus', 'Real footage', 'slow, 4× then shrunk']], 'model', 'model') + '<span class="lbl">Make it</span>' + mediaChips([[2, '2×'], [3, '3×'], [4, '4×']], 'scale', 'scale') +
        '<div class="card" id="mdVplan">' + (vp ? (vp.ok ? '<b>' + vp.width + ' × ' + vp.height + '</b> <span class="muted">· ' + vp.frames + ' frames · roughly ' + vp.minutes + ' min on your graphics card · done in batches, so it never fills the disk</span>' : '<span class="badc">' + esc(vp.why) + '</span>') : '<span class="muted">Working it out…</span>') + '</div>' +
        '<div class="row"><button type="button" class="btn" id="mdUpVideo"' + (vp && !vp.ok ? ' disabled' : '') + '>Upscale video</button></div>'));
    }
    return '<div class="row sb"><h2 class="h">Media</h2><span class="muted">Files are saved in ' + esc(st.settings.save_to) + '</span></div>' + fileCard() +
      '<div class="tabs" role="tablist">' + MTABS.map(function (t) { return '<button type="button" class="chip" role="tab" data-mtab="' + t[0] + '" aria-pressed="' + (MD.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' +
      '<div class="stack" style="max-width:720px">' + body + '</div>' + mediaDone();
  };
  function mediaPreview(m) {
    if (!MD.file || MD.file.kind !== 'picture' || MD.tab !== 'icomp') return;
    var key = MD.file.token + MD.ifmt + MD.q;
    if (MD.prevKey === key) return;
    MD.prevKey = key;
    api('media_picture_preview', MD.file.token, MD.ifmt, MD.q).then(function (r) {
      if (MD.prevKey !== key) return;
      if (!r.ok) { toast(r.message); return; }
      MD.prev = r; if (st.screen === 'media' && MD.tab === 'icomp') go('media', true);
    }).catch(fail);
  }
  function mediaPlan() {
    if (!MD.file || MD.file.kind !== 'video') return;
    if (MD.tab === 'vcomp') api('media_estimate', MD.file.token, +MD.target, MD.start, MD.end).then(function (r) { MD.plan = r.ok ? r.plan : null; var p = $('#mdPlan'); if (p && st.screen === 'media') go('media', true); }).catch(fail);
    if (MD.tab === 'upscale' && MD.what === 'video') api('media_video_plan', MD.file.token, MD.scale, MD.start, MD.end).then(function (r) { MD.vplan = r.ok ? r.plan : null; if ($('#mdVplan') && st.screen === 'media') go('media', true); }).catch(fail);
  }
  function loadClips(refresh) {
    MD.clipsBusy = true;
    api('media_clips', !!refresh).then(function (c) {
      MD.clips = c || []; MD.clipsBusy = false;
      if (st.screen === 'media' && MD.tab === 'clips') go('media', true);
      (function next(i) {                                      // thumbnails one by one, so the list shows at once
        if (i >= MD.clips.length || i >= 30) return;
        var t = MD.clips[i].token;
        if (MD.thumbs[t]) { next(i + 1); return; }
        api('media_clip_thumb', t).then(function (r) { MD.thumbs[t] = r.thumb || ''; var b = $('[data-clip="' + t + '"]'); if (b && r.thumb) b.style.backgroundImage = 'url(' + r.thumb + ')'; next(i + 1); }).catch(function () { next(i + 1); });
      })(0);
    }).catch(function (e) { MD.clipsBusy = false; MD.clips = []; fail(e); });
  }
  WIRE.media = function (m) {
    var pick = $('#mdPick', m); if (pick) pick.onclick = function () { mediaTake(api('media_pick'), false); };
    var watch = $('#mdWatch', m); if (watch) watch.onclick = function () { openWatch(MD.file.token, MD.file.name); };
    $$('[data-mtab]', m).forEach(function (b) { b.onclick = function () { MD.tab = b.getAttribute('data-mtab'); if (MD.tab === 'upscale' && MD.file) MD.what = MD.file.kind === 'gif' ? 'gif' : MD.file.kind === 'video' ? 'video' : 'picture'; go('media', true); }; });
    $$('[data-sugg]', m).forEach(function (b) { b.onclick = function () {
      var s = b.getAttribute('data-sugg');
      if (s === 'cut') { api('cut_token', MD.file.token).then(function (r) { go('bg'); cutStart(Promise.resolve(r)); }).catch(fail); return; }
      MD.tab = s; if (MD.tab === 'convert' && MD.file.kind === 'video') MD.fmt = 'mp3'; if (s === 'upscale') MD.what = MD.file.kind === 'gif' ? 'gif' : MD.file.kind === 'video' ? 'video' : 'picture'; if (s === 'clip' && MD.file.kind === 'gif') MD.ckind = 'webm';
      go('media', true);
    }; });
    [['fmt', 'fmt'], ['target', 'target'], ['ifmt', 'ifmt'], ['preset', 'preset'], ['pfmt', 'pfmt'], ['ckind', 'ckind'], ['cwidth', 'cwidth'], ['cfps', 'cfps'], ['dither', 'dither'], ['what', 'what'], ['scale', 'scale'], ['model', 'model'], ['gout', 'gout'], ['ratio', 'ratio'], ['bact', 'bact'], ['bratio', 'bratio'], ['smode', 'smode'], ['fin', 'fin'], ['fout', 'fout'], ['loud', 'loud'], ['slang', 'slang'], ['sput', 'sput']].forEach(function (pair) {
      $$('[data-' + pair[0] + ']', m).forEach(function (b) { b.onclick = function () {
        var v = b.getAttribute('data-' + pair[0]); MD[pair[1]] = /^\d+$/.test(v) ? +v : v;
        if (pair[0] === 'target' || pair[0] === 'scale') { MD.plan = null; MD.vplan = null; }
        go('media', true);
      }; });
    });
    $$('[data-cfilter]', m).forEach(function (b) { b.onclick = function () { MD.filter = b.getAttribute('data-cfilter'); go('media', true); }; });
    $$('[data-clip]', m).forEach(function (b) { b.onclick = function () {
      var t = b.getAttribute('data-clip'), c = MD.clips.filter(function (x) { return x.token === t; })[0];
      api('media_info', t).then(function (r) { if (!r.ok) { toast(r.message); return; } MD.file = r.file; MD.start = 0; MD.end = 0; MD.plan = null; MD.vplan = null; MD.vt = 0; go('media', true); }).catch(fail);
    };
    b.ondblclick = function () { var t = b.getAttribute('data-clip'), c = MD.clips.filter(function (x) { return x.token === t; })[0]; openWatch(t, c ? (c.game || c.name) : 'Video'); }; });
    var cr = $('#mdClipsRefresh', m); if (cr) cr.onclick = function () { MD.clips = null; go('media', true); loadClips(true); };
    if (MD.tab === 'clips' && MD.clips === null && !MD.clipsBusy) loadClips(false);
    var from = $('#mdFrom', m), to = $('#mdTo', m);
    if (from && to) {
      var upd = function () {
        var a = +from.value / 10, b = +to.value / 10; if (b < a) { b = a; to.value = from.value; }
        MD.start = a; MD.end = b >= MD.file.duration - 0.05 ? 0 : b;
        var end = MD.end || MD.file.duration;
        $('#mdRangeText', m).textContent = fmtTime(MD.start) + ' → ' + fmtTime(end) + ' · ' + fmtTime(end - MD.start);
      };
      from.oninput = function () { upd(); if (MD.player) { MD.player.setRange(MD.start, MD.end || MD.file.duration, false); MD.player.seek(MD.start); } };   // the frame at From shows
      to.oninput = function () { upd(); if (MD.player) { MD.player.setRange(MD.start, MD.end || MD.file.duration, false); MD.player.seek(MD.end || MD.file.duration); } };
      from.onchange = to.onchange = function () { upd(); MD.plan = null; MD.vplan = null; mediaPlan(); };
      var pl = $('#mdPlayer', m);
      MD.player = null;
      if (pl) mediaUrl(MD.file.token).then(function (url) {
        if (!document.body.contains(pl)) return;
        MD.player = playerAttach(pl, { url: url, token: MD.file.token, start: MD.start, end: MD.end, duration: MD.file.duration, fps: MD.file.fps || 30, time: MD.vt,
          onTime: function (t) { MD.vt = t; },
          onRange: function (a, b, done) {                      // the handles on the timeline move the same From / To
            MD.start = a; MD.end = b; from.value = Math.floor(a * 10); to.value = Math.floor((b || MD.file.duration) * 10);
            var e2 = MD.end || MD.file.duration; $('#mdRangeText', m).textContent = fmtTime(MD.start) + ' → ' + fmtTime(e2) + ' · ' + fmtTime(e2 - MD.start);
            if (done) { MD.plan = null; MD.vplan = null; mediaPlan(); }
          } });
      }).catch(function () { pl.remove(); });                   // no player here: the From / To sliders still work
      $('#mdWhole', m).onclick = function () { MD.start = 0; MD.end = 0; MD.plan = null; MD.vplan = null; go('media', true); };
      $('#mdTrim', m).onclick = function () { if (!(MD.end > MD.start) && MD.start <= 0) { toast('Move From or To first.'); return; } mediaStart('trim', rangeOpts(), 'trim'); };
    }
    var d = $('#mdDiscord', m); if (d) d.onclick = function () { mediaStart('discord', rangeOpts(), 'fit for Discord'); };
    var cv = $('#mdConvert', m); if (cv) cv.onclick = function () { mediaStart('convert', { fmt: MD.fmt }, 'convert to ' + MD.fmt.toUpperCase()); };
    var cp = $('#mdCompress', m); if (cp) cp.onclick = function () { mediaStart('compress', rangeOpts({ target: +MD.target }), 'compress to ' + MD.target + ' MB'); };
    var q = $('#mdQ', m); if (q) { q.oninput = function () { MD.q = +q.value; $('#mdQv', m).textContent = q.value; }; q.onchange = function () { MD.prevKey = ''; mediaPreview(m); }; }
    var ba = $('#mdBa .ba-range', m); if (ba) ba.oninput = function () { $('#mdBa', m).style.setProperty('--cut', ba.value + '%'); };
    var ic = $('#mdIcomp', m); if (ic) ic.onclick = function () { mediaStart('icomp', { fmt: MD.ifmt, quality: MD.q, lossless: MD.lossless }, 'compress picture'); };
    var rs = $('#mdResize', m); if (rs) rs.onclick = function () {
      var w = $('#mdW', m), h = $('#mdH', m); if (w) MD.cw = w.value.trim(); if (h) MD.ch = h.value.trim();
      mediaStart('resize', { preset: MD.preset, width: +MD.cw || 0, height: +MD.ch || 0, keep: MD.keep, pixel: MD.pixel }, 'resize');
    };
    ['mdKeep', 'mdPixel'].forEach(function (id) { var b = $('#' + id, m); if (b) b.onclick = function () { var on = b.getAttribute('aria-checked') !== 'true'; b.setAttribute('aria-checked', String(on)); MD[id === 'mdKeep' ? 'keep' : 'pixel'] = on; }; });
    var fm = $('#mdFormat', m); if (fm) fm.onclick = function () { mediaStart('format', { fmt: MD.pfmt, quality: MD.pq }, 'make a ' + MD.pfmt.toUpperCase()); };
    var cl = $('#mdClip', m); if (cl) cl.onclick = function () { mediaStart('clip', rangeOpts({ kind: MD.ckind, width: MD.cwidth, fps: MD.cfps, dither: MD.dither }), 'make a ' + MD.ckind.toUpperCase()); };
    var ins = $('#mdInstall', m); if (ins) ins.onclick = function () { ins.disabled = true; api('install_engines', ['realesrgan']).then(function (r) { toast(r.message); MD.models = null; pollJobs(); }).catch(fail); };
    var up = $('#mdUp', m); if (up) up.onclick = function () { mediaStart('upscale', { scale: MD.scale, model: MD.model }, 'upscale ' + MD.scale + '×'); };
    var sh = $('#mdSharpen', m); if (sh) sh.onclick = function () { mediaStart('sharpen_gif', { scale: MD.scale, out: MD.gout, dither: MD.dither }, 'sharpen GIF'); };
    var uv = $('#mdUpVideo', m); if (uv) uv.onclick = function () { mediaStart('upscale_video', rangeOpts({ scale: MD.scale, model: MD.model }), 'upscale video ' + MD.scale + '×'); };
    if (MD.tab === 'upscale' && MD.models === null) api('upscale_models').then(function (r) { MD.models = r; if (r.models && r.models.length && !r.models.some(function (x) { return x.id === MD.model; })) MD.model = r.models[0].id; if (st.screen === 'media') go('media', true); }).catch(fail);
    if (MD.tab === 'vcomp' && MD.plan === null) mediaPlan();
    if (MD.tab === 'upscale' && MD.what === 'video' && MD.vplan === null && MD.models && MD.models.installed) mediaPlan();
    // ---- crop (15 Oct): draw the part to keep on the picture ----
    var cimg = $('#mdCropImg', m);
    if (cimg) {
      var crect = $('#mdCropRect', m), cbox = $('#mdCrop', m), ctxt = $('#mdCropTxt', m), drag = null;
      var shape = function () { var r = MD.ratio.split(':'); return MD.ratio === 'free' ? 0 : +r[1] / +r[0]; };
      var draw = function () {
        if (!MD.box || !cimg.clientWidth) return;
        var k = cimg.clientWidth / MD.srcW, b = MD.box;
        crect.hidden = false;
        crect.style.left = b.x * k + 'px'; crect.style.top = b.y * k + 'px'; crect.style.width = b.w * k + 'px'; crect.style.height = b.h * k + 'px';
        ctxt.textContent = Math.round(b.w) + ' × ' + Math.round(b.h) + ' pixels kept of ' + MD.srcW + ' × ' + MD.srcH;
      };
      var centre = function () {
        var W = MD.srcW, H = MD.srcH, q = shape();
        if (!q) return { x: 0, y: 0, w: W, h: H };
        return W * q > H ? { x: (W - H / q) / 2, y: 0, w: H / q, h: H } : { x: 0, y: (H - W * q) / 2, w: W, h: W * q };
      };
      var setup = function () {
        var W = MD.file.width, H = MD.file.height;
        if (cimg.naturalWidth !== cimg.naturalHeight && (cimg.naturalWidth > cimg.naturalHeight) !== (W > H)) { var t = W; W = H; H = t; }   // a phone photo turned upright
        MD.srcW = W; MD.srcH = H;
        if (!MD.box || MD.boxFor !== MD.file.token + MD.ratio) { MD.box = centre(); MD.boxFor = MD.file.token + MD.ratio; }
        draw();
      };
      if (cimg.complete && cimg.naturalWidth) setup(); else cimg.onload = setup;
      var at = function (e) { var r = cimg.getBoundingClientRect(), k = cimg.clientWidth / MD.srcW; return { x: Math.max(0, Math.min(MD.srcW, (e.clientX - r.left) / k)), y: Math.max(0, Math.min(MD.srcH, (e.clientY - r.top) / k)) }; };
      cbox.onmousedown = function (e) {
        if (e.button !== 0 || !MD.box) return;
        e.preventDefault();
        var p = at(e), b = MD.box;
        drag = p.x > b.x && p.x < b.x + b.w && p.y > b.y && p.y < b.y + b.h ? { move: true, dx: p.x - b.x, dy: p.y - b.y } : { move: false, sx: p.x, sy: p.y, old: b };
      };
      var onMove = function (e) {
        if (!drag || !document.body.contains(cbox)) return;
        var p = at(e), b = MD.box, q = shape();
        if (drag.move) { b.x = Math.max(0, Math.min(MD.srcW - b.w, p.x - drag.dx)); b.y = Math.max(0, Math.min(MD.srcH - b.h, p.y - drag.dy)); }
        else {
          var dx = p.x - drag.sx, dy = p.y - drag.sy, maxW = dx < 0 ? drag.sx : MD.srcW - drag.sx, maxH = dy < 0 ? drag.sy : MD.srcH - drag.sy, w, h;
          if (q) { w = Math.min(Math.max(Math.abs(dx), Math.abs(dy) / q), maxW, maxH / q); h = w * q; }
          else { w = Math.min(Math.abs(dx), maxW); h = Math.min(Math.abs(dy), maxH); }
          MD.box = { x: dx < 0 ? drag.sx - w : drag.sx, y: dy < 0 ? drag.sy - h : drag.sy, w: w, h: h, old: drag.old };
        }
        draw();
      };
      var onUp = function () {
        if (!drag) return;
        if (!drag.move && (MD.box.w < 8 || MD.box.h < 8)) MD.box = drag.old;          // a click, not a drag: keep the old box
        drag = null; draw();
      };
      if (MD.cropOff) MD.cropOff();                          // one set of listeners, not one per redraw
      document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp); window.addEventListener('resize', draw);
      MD.cropOff = function () { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); window.removeEventListener('resize', draw); MD.cropOff = null; };
      $('#mdCropAll', m).onclick = function () { MD.ratio = 'free'; MD.box = null; go('media', true); };
      $('#mdCropGo', m).onclick = function () {
        var b = MD.box; if (!b) return;
        mediaStart('crop', { box: { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.w), h: Math.round(b.h) } }, 'crop ' + Math.round(b.w) + ' × ' + Math.round(b.h));
      };
    }
    // ---- many pictures at once ----
    var mbTake = function (p) { p.then(function (r) { if (!r.ok) { if (r.message) toast(r.message); return; } var have = {}; MD.batch.forEach(function (x) { have[x.token] = 1; }); r.items.forEach(function (x) { if (!have[x.token]) MD.batch.push(x); }); go('media', true); }).catch(fail); };
    var mbf = $('#mbFiles', m); if (mbf) mbf.onclick = function () { mbTake(api('media_pick_many', 'files')); };
    var mbd = $('#mbFolder', m); if (mbd) mbd.onclick = function () { mbTake(api('media_pick_many', 'folder')); };
    var mbc = $('#mbClear', m); if (mbc) mbc.onclick = function () { MD.batch = []; go('media', true); };
    $$('[data-mbx]', m).forEach(function (b) { b.onclick = function () { MD.batch.splice(+b.getAttribute('data-mbx'), 1); go('media', true); }; });
    var mq = $('#mbQ', m); if (mq) mq.oninput = function () { MD.q = +mq.value; $('#mbQv', m).textContent = mq.value; };
    if (MD.tab === 'batch') (function next() {                 // thumbnails one by one, only the ones shown
      var want = MD.batch.slice(0, 120).filter(function (x) { return MD.bthumbs[x.token] === undefined; })[0];
      if (!want || st.screen !== 'media' || MD.tab !== 'batch') return;
      MD.bthumbs[want.token] = '';
      api('media_batch_thumb', want.token).then(function (d) { MD.bthumbs[want.token] = d || ''; var el = $('[data-mbt="' + want.token + '"]'); if (el && d) el.style.backgroundImage = 'url(' + d + ')'; next(); }).catch(next);
    })();
    var mbg = $('#mbGo', m); if (mbg) mbg.onclick = function () {
      var o = MD.bact === 'icomp' ? { fmt: MD.ifmt, quality: MD.q } : MD.bact === 'resize' ? { preset: MD.preset === 'custom' ? 'half' : MD.preset, keep: true, pixel: MD.pixel } : MD.bact === 'format' ? { fmt: MD.pfmt, quality: 90 } : { ratio: MD.bratio };
      mbg.disabled = true;
      api('media_batch', MD.batch.map(function (x) { return x.token; }), MD.bact, o).then(function (r) { mbg.disabled = false; toast(r.ok ? 'Started on ' + MD.batch.length + ' pictures' : r.message); pollJobs(); }).catch(function (e) { mbg.disabled = false; fail(e); });
    };
    // ---- sound ----
    var au = $('#mdAudio', m); if (au) mediaUrl(MD.file.token).then(function (url) { if (document.body.contains(au)) au.src = url; }).catch(function () { au.remove(); });
    var csd = $('#mdCutSound', m); if (csd) csd.onclick = function () {
      var o = rangeOpts({ fade_in: MD.fin, fade_out: MD.fout });
      if (!(o.end > o.start) && !MD.fin && !MD.fout) { toast('Move From or To first (or pick a fade).'); return; }
      mediaStart('cutsound', o, 'cut the sound');
    };
    var ld = $('#mdLoud', m); if (ld) ld.onclick = function () { mediaStart('normalise', { target: MD.loud }, 'even out the loudness'); };
    // ---- subtitles ----
    var wi = $('#mdWhisper', m); if (wi) wi.onclick = function () { wi.disabled = true; api('install_engines', ['whisper', 'whispermodel']).then(function (r) { toast(r.message); pollJobs(); }).catch(fail); };
    var tr = $('#mdTr', m); if (tr) tr.onclick = function () { MD.str = tr.getAttribute('aria-checked') !== 'true'; tr.setAttribute('aria-checked', String(MD.str)); };
    var sb = $('#mdSubs', m); if (sb) sb.onclick = function () { mediaStart('subs', { lang: MD.slang, translate: MD.str, put: MD.file.kind === 'video' ? MD.sput : 'srt' }, 'subtitles'); };
    mediaPreview(m);
    renderMediaDone();
  };

  // ---------- Handy tools (15 Oct): QR codes, a colour picker for the whole screen, renaming many files, checksums ----------
  var HT = { tab: 'qr', qk: 'text', qv: { text: '', ssid: '', password: '', security: 'WPA', hidden: false, name: '', phone: '', email: '', url: '' }, level: 'm', dark: '#000000', light: '#FFFFFF', clear: false, prev: null,
    picked: null, picks: [], rn: null, rules: { base: '', find: '', replace: '', regex: false, prefix: '', suffix: '', number: 'off', start: 1, digits: 2, sep: ' - ', date: 'off', 'case': 'keep', ext_case: 'keep' }, order: 'name', plan: null };
  try { HT.picks = JSON.parse(localStorage.getItem('toolbelt-picks') || '[]').slice(0, 16); } catch (e) { HT.picks = []; }
  var TTABS = [['qr', 'QR code'], ['pick', 'Colour picker'], ['rename', 'Rename files'], ['sum', 'Checksum']];
  function htChips(list, key, attr, obj) {
    var o = obj || HT;
    return '<div class="row">' + list.map(function (x) { return '<button type="button" class="chip" data-' + attr + '="' + x[0] + '" aria-pressed="' + (String(o[key]) === String(x[0])) + '">' + x[1] + (x[2] ? ' <small>· ' + x[2] + '</small>' : '') + '</button>'; }).join('') + '</div>';
  }
  function qrFields() {
    var v = HT.qv, fld = function (id, key, ph, type) { return '<input class="field" id="' + id + '" data-qv="' + key + '" placeholder="' + ph + '" value="' + esc(v[key]) + '"' + (type ? ' type="' + type + '"' : '') + ' aria-label="' + ph + '">'; };
    if (HT.qk === 'wifi') return '<div class="stack">' + fld('qrSsid', 'ssid', 'Wi-Fi name') + fld('qrPass', 'password', 'Password') + htChips([['WPA', 'WPA / WPA2 / WPA3'], ['WEP', 'WEP'], ['none', 'No password']], 'security', 'qsec', v) + '</div>';
    if (HT.qk === 'contact') return '<div class="stack">' + fld('qrName', 'name', 'Name') + fld('qrPhone', 'phone', 'Phone number', 'tel') + fld('qrMail', 'email', 'Email', 'email') + fld('qrUrl', 'url', 'Website') + '</div>';
    return '<textarea class="field" id="qrText" data-qv="text" rows="3" placeholder="A link (https://…) or any text" aria-label="Link or text">' + esc(v.text) + '</textarea>';
  }
  function hexOf(c) { return c.toUpperCase(); }
  function pickCodes(hx) {
    var c = hexRgb(hx), hs = hex2hsl(hx);
    return [['HEX', hexOf(hx)], ['RGB', 'rgb(' + c.join(', ') + ')'], ['HSL', 'hsl(' + Math.round(hs[0]) + ', ' + Math.round(hs[1]) + '%, ' + Math.round(hs[2]) + '%)'],
      ['Minecraft', '&' + hexOf(hx)], ['Skript', '<#' + hexOf(hx) + '>'], ['Discord', String(parseInt(hx.slice(1), 16))]];
  }
  VIEWS.tools = function () {
    var body = '';
    if (HT.tab === 'qr') {
      var p = HT.prev;
      body = '<div class="cols"><div class="stack">' + htChips([['text', 'Link or text'], ['wifi', 'Wi-Fi'], ['contact', 'Contact']], 'qk', 'qk') + qrFields() +
        '<span class="lbl">Can still be read when damaged</span>' + htChips([['l', '7%'], ['m', '15%', 'normal'], ['q', '25%'], ['h', '30%', 'for stickers']], 'level', 'qlevel') +
        '<div class="row nw"><label class="muted" for="qrDark">Squares</label><input type="color" id="qrDark" value="' + HT.dark + '"><label class="muted" for="qrLight">Background</label><input type="color" id="qrLight" value="' + HT.light + '"' + (HT.clear ? ' disabled' : '') + '>' +
        sw('qrClear', HT.clear, 'See-through background') + '<span>See-through</span></div></div>' +
        '<div class="card stack qrcard" style="align-items:center"><div class="qrprev' + (HT.clear ? ' clear' : '') + '" id="qrPrev">' + (p && p.ok ? '<img src="' + p.svg + '" alt="QR code preview">' : '<span class="muted">' + esc(p && p.message || 'Type something and the code appears here') + '</span>') + '</div>' +
        '<span class="muted" id="qrInfo">' + (p && p.ok ? p.modules + ' × ' + p.modules + ' squares' + (p.readable ? '' : ' · <span class="warnc">too little contrast: phones may not read it</span>') : '') + '</span>' +
        '<div class="row"><button type="button" class="btn" id="qrPng"' + (p && p.ok ? '' : ' disabled') + '>Save PNG</button><button type="button" class="btn ghost" id="qrSvg"' + (p && p.ok ? '' : ' disabled') + '>Save SVG</button><button type="button" class="btn ghost" id="qrCopy"' + (p && p.ok ? '' : ' disabled') + '>Copy</button></div></div></div>' +
        '<span class="muted">Made on your PC; a link in a QR code works for whoever scans it, so only share what you\'d share anyway. Wi-Fi codes contain the password.</span>';
    } else if (HT.tab === 'pick') {
      var hx = HT.picked, has = !!window.EyeDropper;
      body = '<div class="card stack"><div class="row"><button type="button" class="btn" id="pkGo"' + (has ? '' : ' disabled') + '>🎯 Pick a colour from the screen</button><span class="muted">' + (has ? 'Then click anywhere: other windows, games, pictures. Esc stops.' : 'Picking needs a newer WebView2 (Windows updates it by itself).') + '</span></div>' +
        (hx ? '<div class="row nw" style="align-items:stretch"><span class="pkswatch" style="background:' + hx + '"></span><div class="list grow">' + pickCodes(hx).map(function (c, i) {
          return '<div class="item"><b>' + c[0] + '</b><code class="mono">' + esc(c[1]) + '</code><button type="button" class="btn ghost sm" data-pkcopy="' + i + '">Copy</button></div>'; }).join('') + '</div></div>' +
          '<div class="row"><button type="button" class="btn ghost sm" id="pkCol">Open in Colours (shades, palettes)</button></div>' : '') + '</div>' +
        (HT.picks.length ? '<span class="lbl">Picked before</span><div class="row">' + HT.picks.map(function (c) { return '<button type="button" class="pkold" data-pkold="' + c + '" style="background:' + c + '" title="' + c + '" aria-label="' + c + '"></button>'; }).join('') + '<button type="button" class="btn ghost sm" id="pkForget">Forget them</button></div>' : '');
    } else if (HT.tab === 'rename') {
      var r = HT.rules, pl = HT.plan, n = HT.rn;
      body = '<div class="row"><button type="button" class="btn" id="rnFiles">Pick files</button><button type="button" class="btn ghost" id="rnFolder">Pick a folder</button>' +
        '<span class="muted">' + (n ? n + ' file' + (n === 1 ? '' : 's') + (pl && pl.folder ? ' in ' + esc(pl.folder) : '') : 'Ctrl or Shift picks several; a folder takes every file in it (not its subfolders)') + '</span>' +
        (pl && pl.undo ? '<button type="button" class="btn ghost sm" id="rnUndo">↶ Undo the last rename (' + pl.undo + ')</button>' : '') + '</div>' +
        (n ? '<div class="cols"><div class="stack">' +
          '<label class="stack" style="gap:4px"><span class="lbl">A new name for all</span><input class="field" data-rule="base" value="' + esc(r.base) + '" placeholder="Leave empty to keep each name"></label>' +
          '<div class="row nw"><label class="stack grow" style="gap:4px"><span class="lbl">Find</span><input class="field" data-rule="find" value="' + esc(r.find) + '" placeholder="text in the names"></label><label class="stack grow" style="gap:4px"><span class="lbl">Replace with</span><input class="field" data-rule="replace" value="' + esc(r.replace) + '" placeholder="(nothing = remove it)"></label></div>' +
          '<div class="row nw">' + sw('rnRegex', r.regex, 'Find is a pattern (regex)') + '<span class="muted">Find is a pattern (regular expression, for experts)</span></div>' +
          '<div class="row nw"><label class="stack grow" style="gap:4px"><span class="lbl">Before</span><input class="field" data-rule="prefix" value="' + esc(r.prefix) + '"></label><label class="stack grow" style="gap:4px"><span class="lbl">After</span><input class="field" data-rule="suffix" value="' + esc(r.suffix) + '"></label></div>' +
          '<span class="lbl">Numbers</span>' + htChips([['off', 'None'], ['before', 'Before'], ['after', 'After'], ['only', 'Only numbers']], 'number', 'rnum', r) +
          (r.number !== 'off' ? '<div class="row nw"><label class="muted">from</label><input class="field" data-rule="start" inputmode="numeric" value="' + r.start + '" style="width:70px"><label class="muted">digits</label><input class="field" data-rule="digits" inputmode="numeric" value="' + r.digits + '" style="width:60px"></div><div class="row nw"><span class="muted">counting in the order of</span>' + htChips([['name', 'Name'], ['date', 'Date changed'], ['size', 'Size']], 'order', 'rorder') + '</div>' : '') +
          '<span class="lbl">Date in front</span>' + htChips([['off', 'None'], ['taken', 'Photo taken', 'from the photo itself'], ['changed', 'Last changed']], 'date', 'rdate', r) +
          '<span class="lbl">Letters</span>' + htChips([['keep', 'As they are'], ['lower', 'lower case'], ['upper', 'UPPER CASE'], ['title', 'Title Case']], 'case', 'rcase', r) +
          '<div class="row nw"><span class="lbl">Ending</span>' + htChips([['keep', 'As it is'], ['lower', '.jpg not .JPG']], 'ext_case', 'rext', r) + '<label class="muted">between parts</label><input class="field" data-rule="sep" value="' + esc(r.sep) + '" style="width:60px"></div>' +
          '</div><div class="stack"><div class="row sb"><b>Before → after</b><span class="muted" id="rnSum">' + (pl ? pl.changes + ' change' + (pl.changes === 1 ? '' : 's') + (pl.problems ? ' · <span class="badc">' + pl.problems + ' problem' + (pl.problems === 1 ? '' : 's') + '</span>' : '') : '…') + '</span></div>' +
          '<div class="list rnlist" id="rnList">' + (pl ? pl.items.map(function (it) { return '<div class="item' + (it.problem ? ' bad' : '') + '"><span class="ell muted">' + esc(it.old) + '</span><span class="ell' + (it.old !== it.new ? ' okc' : '') + '">→ ' + esc(it.new) + '</span>' + (it.problem ? '<span class="badc">' + esc(it.problem) + '</span>' : '<span></span>') + '</div>'; }).join('') + (pl.count > pl.items.length ? '<span class="muted">and ' + (pl.count - pl.items.length) + ' more</span>' : '') : '') + '</div>' +
          '<div class="row sb"><span class="muted">Files with a problem are left alone.</span><button type="button" class="btn" id="rnGo"' + (pl && pl.changes ? '' : ' disabled') + '>Rename ' + (pl ? pl.changes : '') + '</button></div></div></div>' : '');
    } else {
      body = '<div class="card stack"><b>Fingerprints live in Check a file</b><span class="muted">MD5, SHA-1, SHA-256 and SHA-512 of any file, pasting the fingerprint a website gives to see if it matches, who signed a program, comparing two files, and a whole folder at once.</span><div class="row"><button type="button" class="btn" data-go="check">Open Check a file</button></div></div>';
    }
    return '<h2 class="h">Handy tools</h2><div class="tabs" role="tablist">' + TTABS.map(function (t) { return '<button type="button" class="chip" role="tab" data-ttab="' + t[0] + '" aria-pressed="' + (HT.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' +
      '<div class="stack" style="max-width:900px">' + body + '</div>';
  };
  var qrTimer = null, rnTimer = null;
  function qrArgs() { return [HT.qk, HT.qv, HT.level, HT.dark, HT.clear ? '' : HT.light]; }
  function qrRefresh() {
    clearTimeout(qrTimer);
    qrTimer = setTimeout(function () {
      var v = HT.qv, empty = HT.qk === 'wifi' ? !v.ssid : HT.qk === 'contact' ? !v.name : !v.text.trim();
      if (empty) { HT.prev = null; paint(); return; }
      api.apply(null, ['qr_preview'].concat(qrArgs())).then(function (r) { HT.prev = r; paint(); }).catch(fail);
    }, 200);
    function paint() {
      var box = $('#qrPrev'), info = $('#qrInfo'), p = HT.prev; if (!box) return;
      box.className = 'qrprev' + (HT.clear ? ' clear' : '');
      box.innerHTML = p && p.ok ? '<img src="' + p.svg + '" alt="QR code preview">' : '<span class="muted">' + esc(p && p.message || 'Type something and the code appears here') + '</span>';
      info.innerHTML = p && p.ok ? p.modules + ' × ' + p.modules + ' squares' + (p.readable ? '' : ' · <span class="warnc">too little contrast: phones may not read it</span>') : '';
      ['#qrPng', '#qrSvg', '#qrCopy'].forEach(function (id) { var b = $(id); if (b) b.disabled = !(p && p.ok); });
    }
  }
  function rnRefresh(now) {
    clearTimeout(rnTimer);
    rnTimer = setTimeout(function () {
      api('rename_plan', HT.rules).then(function (r) { if (!r.ok) { toast(r.message); return; } HT.plan = r; if (st.screen === 'tools' && HT.tab === 'rename') { var keep = document.activeElement && document.activeElement.getAttribute('data-rule'), pos = keep ? document.activeElement.selectionStart : 0; go('tools', true); if (keep) { var el = $('[data-rule="' + keep + '"]'); if (el) { el.focus(); try { el.setSelectionRange(pos, pos); } catch (e) {} } } } }).catch(fail);
    }, now ? 0 : 250);
  }
  function setPicked(hx) {
    HT.picked = hx.toUpperCase();
    HT.picks = [HT.picked].concat(HT.picks.filter(function (c) { return c !== HT.picked; })).slice(0, 16);
    try { localStorage.setItem('toolbelt-picks', JSON.stringify(HT.picks)); } catch (e) {}
    go('tools', true);
  }
  WIRE.tools = function (m) {
    $$('[data-ttab]', m).forEach(function (b) { b.onclick = function () { HT.tab = b.getAttribute('data-ttab'); go('tools', true); }; });
    // QR
    $$('[data-qk]', m).forEach(function (b) { b.onclick = function () { HT.qk = b.getAttribute('data-qk'); HT.prev = null; go('tools', true); qrRefresh(); }; });
    $$('[data-qlevel]', m).forEach(function (b) { b.onclick = function () { HT.level = b.getAttribute('data-qlevel'); go('tools', true); qrRefresh(); }; });
    $$('[data-qsec]', m).forEach(function (b) { b.onclick = function () { HT.qv.security = b.getAttribute('data-qsec'); go('tools', true); qrRefresh(); }; });
    $$('[data-qv]', m).forEach(function (el) { el.oninput = function () { HT.qv[el.getAttribute('data-qv')] = el.value; qrRefresh(); }; });
    var dk = $('#qrDark', m), lt = $('#qrLight', m);
    if (dk) { dk.oninput = function () { HT.dark = dk.value.toUpperCase(); qrRefresh(); }; lt.oninput = function () { HT.light = lt.value.toUpperCase(); qrRefresh(); }; }
    var qc = $('#qrClear', m); if (qc) qc.onclick = function () { HT.clear = !HT.clear; go('tools', true); qrRefresh(); };
    var qs = function (fmt) { api.apply(null, ['qr_save'].concat(qrArgs(), [fmt])).then(function (r) { toast(r.message); if (r.ok && st.settings.open_when_done) api('show_file', r.path); }).catch(fail); };
    var qp = $('#qrPng', m); if (qp) qp.onclick = function () { qs('png'); };
    var qv = $('#qrSvg', m); if (qv) qv.onclick = function () { qs('svg'); };
    var qy = $('#qrCopy', m); if (qy) qy.onclick = function () { api.apply(null, ['qr_copy'].concat(qrArgs())).then(function (r) { toast(r.message); }).catch(fail); };
    if (HT.tab === 'qr' && !HT.prev) qrRefresh();
    // colour picker: Chromium's own EyeDropper reads any pixel on the screen (Windows asks nothing; Esc cancels)
    var pk = $('#pkGo', m); if (pk) pk.onclick = function () {
      new window.EyeDropper().open().then(function (r) { setPicked(r.sRGBHex.length === 7 ? r.sRGBHex : rgbHex((r.sRGBHex.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number))); }).catch(function () {});
    };
    $$('[data-pkcopy]', m).forEach(function (b) { b.onclick = function () { copyText(pickCodes(HT.picked)[+b.getAttribute('data-pkcopy')][1], b, 'Copy'); }; });
    $$('[data-pkold]', m).forEach(function (b) { b.onclick = function () { HT.picked = b.getAttribute('data-pkold'); go('tools', true); }; });
    var pf = $('#pkForget', m); if (pf) pf.onclick = function () { HT.picks = []; try { localStorage.removeItem('toolbelt-picks'); } catch (e) {} go('tools', true); };
    var pc = $('#pkCol', m); if (pc) pc.onclick = function () { if (window.toolbelt.openColour) window.toolbelt.openColour(HT.picked); else go('color'); };
    // rename
    var rnTake = function (p) { p.then(function (r) { if (!r.ok) { if (r.message) toast(r.message); return; } HT.rn = r.count; HT.plan = null; go('tools', true); rnRefresh(true); }).catch(fail); };
    var rf = $('#rnFiles', m); if (rf) rf.onclick = function () { rnTake(api('rename_pick', 'files')); };
    var rd = $('#rnFolder', m); if (rd) rd.onclick = function () { rnTake(api('rename_pick', 'folder')); };
    $$('[data-rule]', m).forEach(function (el) { el.oninput = function () { var k = el.getAttribute('data-rule'); HT.rules[k] = k === 'start' || k === 'digits' ? (parseInt(el.value, 10) || 0) : el.value; rnRefresh(); }; });
    var rx = $('#rnRegex', m); if (rx) rx.onclick = function () { HT.rules.regex = !HT.rules.regex; go('tools', true); rnRefresh(true); };
    [['rnum', 'number'], ['rdate', 'date'], ['rcase', 'case'], ['rext', 'ext_case']].forEach(function (pr) {
      $$('[data-' + pr[0] + ']', m).forEach(function (b) { b.onclick = function () { HT.rules[pr[1]] = b.getAttribute('data-' + pr[0]); go('tools', true); rnRefresh(true); }; });
    });
    $$('[data-rorder]', m).forEach(function (b) { b.onclick = function () { HT.order = b.getAttribute('data-rorder'); api('rename_order', HT.order).then(function () { go('tools', true); rnRefresh(true); }).catch(fail); }; });
    var rg = $('#rnGo', m); if (rg) rg.onclick = function () {
      rg.disabled = true;
      api('rename_apply', HT.rules).then(function (r) { toast(r.message); HT.rules.base = HT.rules.find = HT.rules.replace = HT.rules.prefix = HT.rules.suffix = ''; HT.rules.number = HT.rules.date = 'off'; HT.rules['case'] = HT.rules.ext_case = 'keep'; rnRefresh(true); }).catch(fail);
    };
    var ru = $('#rnUndo', m); if (ru) ru.onclick = function () { api('rename_undo').then(function (r) { toast(r.message); rnRefresh(true); }).catch(fail); };
    if (HT.tab === 'rename' && HT.rn && !HT.plan) rnRefresh(true);
  };
  T.ht = HT;

  // ---------- App guard (18 Oct): new programs are checked and he decides (appguard.py; the warning is web/guard.js) ----------
  var GD = { tab: 'trusted', st: null, busy: false, scan: '', jobSig: '' };
  // ---- App guard's scans and the Downloads check (18 Oct) ----
  var SCAN_KINDS = [['program', 'Program check', 'Downloads, Desktop, startup programs and Temp: every program that isn’t signed, is disguised or was downloaded. About a minute.'],
    ['quick', 'Defender quick scan', 'Microsoft Defender’s own scan of the usual hiding places. About 5 minutes; Defender handles what it finds.'],
    ['full', 'Defender full scan', 'Every file on every drive. Can take an hour or more; keep working meanwhile. It can’t be cancelled (Windows wants admin for that).'],
    ['folder', 'Scan a folder or drive', 'Pick a folder or a USB stick: Defender reports what it finds there (it removes nothing) and every program gets App guard’s checks.']];
  var SCAN_NAMES = { program: 'Program check', quick: 'Quick scan', full: 'Full scan', folder: 'Folder', usb: 'USB stick' };
  var VMARK = { danger: ['DANGER', 'tag bad'], unknown: ['UNKNOWN', 'tag warn'], safe: ['FINE', 'tag ok'] };
  function scanJob() { return st.jobs.filter(function (j) { return j.kind === 'Scan'; })[0]; }
  function findingHtml(f, actions) {
    var v = VMARK[f.verdict] || VMARK.unknown, notes = (f.checks || []).filter(function (c) { return c[0] !== 'ok'; }).map(function (c) { return c[1]; });
    return '<div class="item gfind"><span class="' + v[1] + '">' + v[0] + '</span><div style="min-width:0"><b class="ell">' + esc(f.name) + '</b><span class="muted ell">' + esc(f.place || f.site || '') + (f.when ? ' · ' + esc(f.when) : '') + ' · ' + esc(f.path) + '</span>' +
      (notes.length ? '<span class="gwhy">' + esc(notes.join(' · ')) + '</span>' : '') + '</div><div class="row nw">' +
      (actions.indexOf('trust') !== -1 ? '<button type="button" class="btn ghost sm" data-gfind="trust" data-path="' + esc(f.path) + '">Trust</button>' : '') +
      '<button type="button" class="btn ghost sm" data-gfind="show" data-path="' + esc(f.path) + '">Show</button>' +
      '<button type="button" class="btn danger sm" data-gfind="quarantine" data-path="' + esc(f.path) + '">Quarantine</button></div></div>';
  }
  function scanTab(g) {
    var job = scanJob(), running = job && (job.state === 'running' || job.state === 'waiting');
    var kinds = Object.keys(g.scans || {}).sort(function (a, b) { return (g.scans[b].when || '').localeCompare(g.scans[a].when || ''); });
    if (!GD.scan || !g.scans[GD.scan]) GD.scan = kinds[0] || '';
    var r = g.scans[GD.scan];
    var html = '<div class="gscans">' + SCAN_KINDS.map(function (k) {
      var last = g.scans[k[0]];
      return '<div class="card stack"><b>' + k[1] + '</b><span class="muted" style="font-size:12.5px">' + k[2] + '</span><span class="muted" style="font-size:12px">' + (last ? 'Last: ' + esc(last.when) : 'Not run yet') + '</span>' +
        '<button type="button" class="btn sm" data-gscan="' + k[0] + '"' + (running ? ' disabled' : '') + '>' + (k[0] === 'folder' ? 'Pick and scan' : 'Start') + '</button></div>';
    }).join('') + '</div>';
    if (running) html += '<div class="card stack" id="gScanRun"><div class="row sb"><b>' + esc(job.title) + '</b><span class="muted" id="gScanMsg">' + esc(job.message || 'starting') + '</span></div><div class="bar run"><i style="width:' + Math.round(job.progress) + '%"></i></div></div>';
    if (!r) return html + '<div class="card muted">No scans yet. A USB stick you plug in is checked by itself and shows up here too.</div>';
    var threats = r.threats || [], finds = r.findings || [];
    html += '<div class="row sb"><div class="tabs">' + kinds.map(function (k) { return '<button type="button" class="chip" data-gres="' + k + '" aria-pressed="' + (GD.scan === k) + '">' + esc(SCAN_NAMES[k] || k) + '</button>'; }).join('') + '</div></div>';
    html += '<div class="card stack"><div class="row sb"><b>' + esc(r.label || SCAN_NAMES[GD.scan]) + '</b><span class="muted">' + esc(r.when) + (r.seconds ? ' · took ' + fmtTime(r.seconds) : '') + '</span></div>' +
      '<span class="' + (finds.length || threats.length ? 'warnc' : 'okc') + '">' + (finds.length || threats.length ? (finds.length + threats.length) + ' to look at' : 'Nothing risky found') + '</span>' +
      (r.checked != null ? '<span class="muted">' + r.checked + ' program' + (r.checked === 1 ? '' : 's') + ' checked · ' + (r.fine || 0) + ' looked fine</span>' : '') +
      (threats.length && !finds.length ? '<div class="list">' + threats.map(function (t) { return '<div class="item"><span class="tag bad">DEFENDER</span><div style="min-width:0"><b>' + esc(t.name) + '</b><span class="muted ell">' + esc((t.files || []).join(' · ') || 'handled by Defender') + '</span></div><span></span></div>'; }).join('') + '</div>' : '') +
      '</div>';
    if (finds.length) html += '<div class="list">' + finds.map(function (f) { return findingHtml(f, ['trust']); }).join('') + '</div>';
    return html;
  }
  function downloadsTab(g) {
    var s = st.settings || {};
    if (s.guard_downloads === false) return '<div class="card muted">The Downloads check is off (App guard > Settings).</div>';
    var list = g.downloads || [];
    return '<span class="muted">Every new download is checked as soon as it’s complete (disguised? Defender? signed?). You only get a warning when something is wrong.</span>' +
      (list.length ? '<div class="list">' + list.map(function (d) { return d.verdict === 'safe' ? '<div class="item gfind"><span class="tag ok">FINE</span><div style="min-width:0"><b class="ell">' + esc(d.name) + '</b><span class="muted ell">' + esc(d.when) + (d.site ? ' · from ' + esc(d.site) : '') + '</span></div><button type="button" class="btn ghost sm" data-gfind="show" data-path="' + esc(d.path) + '">Show</button></div>' : findingHtml(d, d.verdict === 'unknown' ? ['trust'] : []); }).join('') + '</div>' : '<div class="card muted">No new downloads since App guard started.</div>');
  }
  function guardTick() {                                     // called from pollJobs: the scan's bar moves, the results come in when it ends
    if (st.screen !== 'guard') return;
    var job = scanJob(), sig = job ? job.id + job.state : '';
    if (job && (job.state === 'running' || job.state === 'waiting')) {
      var bar = $('#gScanRun .bar i'), msg = $('#gScanMsg');
      if (bar) { bar.style.width = Math.round(job.progress) + '%'; if (msg) msg.textContent = job.message || ''; }
      else if (GD.tab === 'scan' && GD.jobSig !== sig) go('guard', true);
    } else if (GD.jobSig && GD.jobSig !== sig) { if (job && job.state === 'done' && job.extra) GD.scan = job.extra.scan; loadGuard(); }
    GD.jobSig = sig;
  }


  function guardShield(col) {
    return '<svg viewBox="0 0 46 52" aria-hidden="true"><path d="M23 2 L43 9 V25 C43 38 34 46 23 50 C12 46 3 38 3 25 V9 Z" fill="' + col + '"/><path d="M14 26 l7 7 l12 -14" fill="none" stroke="var(--on)" stroke-width="4" stroke-linecap="square"/></svg>';
  }
  function loadGuard() { return api('guard_status').then(function (s) { GD.st = s; if (st.screen === 'guard') go('guard', true); }).catch(fail); }
  VIEWS.guard = function () {
    var g = GD.st, s = st.settings || {};
    if (!g) { loadGuard(); return '<h2 class="h">App guard</h2><span class="muted">Loading…</span>'; }
    var on = g.on, body;
    if (GD.tab === 'scan') body = scanTab(g);
    else if (GD.tab === 'downloads') body = downloadsTab(g);
    else if (GD.tab === 'settings') {
      body = setrow('Let signed programs through', 'Programs with a valid signature (Microsoft, Valve, Epic, Discord, Python…) start without a question; they still show under Activity.', sw('gSigned', s.guard_signed !== false, 'Let signed programs through')) +
        setrow('Defender scans each new program', 'A quick scan of just that file, before you’re asked.', sw('gScan', s.guard_scan !== false, 'Defender scans each new program')) +
        setrow('Check new downloads', 'Each new file in your Downloads folder is checked when it’s complete; a warning only when it’s risky.', sw('gDl', s.guard_downloads !== false, 'Check new downloads')) +
        setrow('Check USB sticks', 'A USB stick or memory card is checked when you plug it in, and you get a short note when it’s done.', sw('gUsb', s.guard_usb !== false, 'Check USB sticks')) +
        setrow('Quarantine folder', 'Stopped programs wait here with .blocked added, so they can’t start by accident', '<button type="button" class="btn ghost sm" data-open="quarantine">Open</button>');
    } else if (GD.tab === 'log') {
      body = g.log.length ? '<div class="list glog">' + g.log.map(function (l) { return '<div class="item"><span class="muted">' + esc(l.t) + '</span><span>' + esc(l.what) + '</span></div>'; }).join('') + '</div>' : '<div class="card muted">Nothing happened yet.</div>';
    } else if (GD.tab === 'stopped') {
      body = g.quarantine.length ? '<div class="list">' + g.quarantine.map(function (q) {
        return '<div class="item"><span class="badge" style="background:var(--bad);color:#fff;font-size:10px">EXE</span><div style="min-width:0"><b class="ell">' + esc(q.name) + '</b><span class="muted ell">' + esc(q.when) + ' · ' + esc(q.why) + ' · was in ' + esc(q.original.replace(/\\[^\\]*$/, '')) + '</span></div>' +
          '<div class="row nw"><button type="button" class="btn ghost sm" data-grestore="' + esc(q.id) + '">Restore</button><button type="button" class="btn danger sm" data-gdelete="' + esc(q.id) + '">Delete</button></div></div>';
      }).join('') + '</div>' : '<div class="card muted">Nothing stopped. Programs you stop wait here until you restore or delete them.</div>';
    } else {
      body = g.trusted.length ? '<div class="list">' + g.trusted.map(function (t) {
        return '<div class="item"><span class="badge" style="font-size:10px">' + esc((t.name.split('.').pop() || 'EXE').toUpperCase().slice(0, 4)) + '</span><div style="min-width:0"><b class="ell">' + esc(t.name) + '</b><span class="muted ell">' + (t.signed ? 'Signed' : 'Not signed') + ' · trusted ' + esc(t.when) + ' · ' + esc(t.path) + '</span></div>' +
          '<button type="button" class="btn ghost sm" data-gforget="' + esc(t.path) + '">Forget</button></div>';
      }).join('') + '</div>' : '<div class="card muted">Programs you trust appear here; they’re never asked about again.</div>';
    }
    return '<h2 class="h">App guard</h2>' +
      '<div class="card gstate">' + guardShield(on ? 'var(--accent)' : 'var(--ink2)') + '<div class="stack" style="gap:2px"><b>' + (on ? 'Watching for new programs' : 'App guard is off') + '</b><span class="muted">' +
        (on ? (g.running ? 'Defender is on too · ' + g.known + ' programs known · new ones are checked and you decide' : 'Starting…') : 'New programs start without a question. Defender still protects you.') + '</span></div>' +
        sw('gOn', on, 'App guard on') + '</div>' +
      '<div class="gcounts"><div><b>' + g.trusted.length + '</b><span>trusted</span></div><div><b>' + g.quarantine.length + '</b><span>in quarantine</span></div><div><b>' + g.log.length + '</b><span>in the activity list</span></div></div>' +
      '<div class="tabs" role="tablist">' + [['trusted', 'Trusted'], ['scan', 'Scan'], ['downloads', 'Downloads'], ['stopped', 'Quarantine'], ['log', 'Activity'], ['settings', 'Settings']].map(function (t) { return '<button type="button" class="chip" role="tab" data-gtab="' + t[0] + '" aria-pressed="' + (GD.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' +
      body +
      '<p class="muted" style="font-size:12.5px;max-width:80ch">App guard notices a new program within about a second and asks you while it runs; it can’t stop a program before it starts (Windows’ Smart App Control does that part). Microsoft Defender keeps protecting you either way. Nothing is uploaded.</p>';
  };
  WIRE.guard = function (m) {
    var on = $('#gOn', m); if (on) on.onclick = function () { var v = on.getAttribute('aria-checked') !== 'true'; api('guard_switch', v).then(function (r) { toast(r.message); return api('settings'); }).then(function (s) { st.settings = s; loadGuard(); }).catch(fail); };
    $$('[data-gtab]', m).forEach(function (b) { b.onclick = function () { GD.tab = b.getAttribute('data-gtab'); go('guard', true); loadGuard(); }; });
    [['gSigned', 'guard_signed'], ['gScan', 'guard_scan'], ['gDl', 'guard_downloads'], ['gUsb', 'guard_usb']].forEach(function (p) { var b = $('#' + p[0], m); if (b) b.onclick = function () { change(p[1], b.getAttribute('aria-checked') !== 'true').then(function () { go('guard', true); }); }; });
    var act = function (sel, name) { $$('[' + sel + ']', m).forEach(function (b) { b.onclick = function () { b.disabled = true; api(name, b.getAttribute(sel)).then(function (r) { toast(r.message); loadGuard(); }).catch(fail); }; }); };
    act('data-gforget', 'guard_forget'); act('data-grestore', 'guard_restore'); act('data-gdelete', 'guard_delete');
    $$('[data-gscan]', m).forEach(function (b) { b.onclick = function () { b.disabled = true; api('guard_scan', b.getAttribute('data-gscan')).then(function (r) { if (r.message) toast(r.message); b.disabled = false; if (r.ok) { GD.scan = b.getAttribute('data-gscan'); pollJobs(); } }).catch(fail); }; });
    $$('[data-gres]', m).forEach(function (b) { b.onclick = function () { GD.scan = b.getAttribute('data-gres'); go('guard', true); }; });
    $$('[data-gfind]', m).forEach(function (b) { b.onclick = function () { var a = b.getAttribute('data-gfind'); b.disabled = true; api('guard_finding', b.getAttribute('data-path'), a).then(function (r) { if (r.message) toast(r.message); b.disabled = false; if (a !== 'show') loadGuard(); }).catch(fail); }; });
  };
  T.loadGuard = loadGuard;

  // ---------- step 9: the Revo-style uninstaller (his flow, 15 Oct): right-click menu, a confirm box with the restore point,
  // the steps with Safe / Moderate / Advanced, then the leftover registry tree and the files tree with tick boxes ----------
  var UN = { tab: 'progs', view: 'details', q: '', progs: null, busy: false, sel: '', rps: null,
    apps: null, abusy: false, asel: '', aq: '', hidden: false, hq: '' };
  var UTABS = [['progs', 'Programs'], ['apps', 'Windows apps'], ['hunt', 'Leftover hunt'], ['tools', 'Windows tools']];
  var SCAN_MODES = [['safe', 'Safe', 'Its own folders and registry keys. Quick, nothing doubtful.'],
    ['moderate', 'Moderate', 'Also shortcuts, temporary files, file types and startup entries. The usual choice.'],
    ['advanced', 'Advanced', 'Also the whole registry and inside Windows\' own folders. Finds the most: look before you delete.']];
  var scanMode = 'moderate';
  try { var smo = localStorage.getItem('toolbelt-scan-mode'); if (smo === 'safe' || smo === 'moderate' || smo === 'advanced') scanMode = smo; } catch (e) {}
  function unShown() { var q = UN.q.toLowerCase(); return (UN.progs || []).filter(function (p) { return !q || p.name.toLowerCase().indexOf(q) !== -1 || p.publisher.toLowerCase().indexOf(q) !== -1; }); }
  function appsShown() { var q = UN.aq.toLowerCase(); return (UN.apps || []).filter(function (a) { return (UN.hidden || a.visible) && (!q || a.name.toLowerCase().indexOf(q) !== -1 || a.package.toLowerCase().indexOf(q) !== -1 || a.publisher.toLowerCase().indexOf(q) !== -1); }); }
  function pbadge(p, big) { var large = big || UN.view === 'icons'; return p.icon_data ? '<img class="appicon' + (large ? '' : ' sm') + '" src="' + p.icon_data + '" alt="">' : '<span class="badge" style="' + (large ? 'width:40px;height:40px' : 'width:26px;height:26px;font-size:11px') + '">' + esc(p.name.charAt(0)) + '</span>'; }
  function careTag(a) { return a.care ? '<span class="tag ' + (a.care === 'danger' ? 'warn" style="color:var(--bad)' : a.care === 'warn' ? 'warn' : '') + '">' + (a.care === 'danger' ? 'keep' : a.care === 'warn' ? 'careful' : 'note') + '</span>' : ''; }
  function loadProgs(refresh) {
    UN.busy = true;
    api('pc_programs', !!refresh).then(function (list) { UN.progs = list || []; UN.busy = false; if (st.screen === 'unin') go('unin', true); }).catch(function (e) { UN.busy = false; UN.progs = []; fail(e); });
  }
  function loadApps(refresh) {
    UN.abusy = true;
    api('pc_store_apps', !!refresh).then(function (list) { UN.apps = list || []; UN.abusy = false; if (st.screen === 'unin') go('unin', true); }).catch(function (e) { UN.abusy = false; UN.apps = []; fail(e); });
  }
  function modeRadios(name) {
    return '<fieldset class="smodes"><legend>Scanning mode</legend>' + SCAN_MODES.map(function (s) { return '<label><input type="radio" name="' + name + '" value="' + s[0] + '"' + (scanMode === s[0] ? ' checked' : '') + '><span><b>' + s[1] + '</b><span class="muted">' + s[2] + '</span></span></label>'; }).join('') + '</fieldset>';
  }
  VIEWS.unin = function () {
    var body = '';
    if (UN.tab === 'progs') {
      var list = UN.progs ? unShown() : [], sel = (UN.progs || []).filter(function (p) { return p.id === UN.sel; })[0];
      var head = '<div class="row sb"><input class="field" id="uQ" placeholder="Search programs or companies…" value="' + esc(UN.q) + '" aria-label="Search programs" style="max-width:340px"><div class="row"><span class="muted">' + (UN.progs ? list.length + ' programs' : 'Reading…') + '</span>' +
        [['icons', 'Icons'], ['list', 'List'], ['details', 'Details']].map(function (v) { return '<button type="button" class="chip" data-uview="' + v[0] + '" aria-pressed="' + (UN.view === v[0]) + '">' + v[1] + '</button>'; }).join('') + '</div></div>';
      var rows;
      if (UN.view === 'icons') rows = '<div class="mgrid" style="grid-template-columns:repeat(auto-fill,minmax(130px,1fr))">' + list.map(function (p) { return '<button type="button" class="card stack lift" data-prog="' + esc(p.id) + '" aria-pressed="' + (p.id === UN.sel) + '" style="align-items:center;text-align:center;gap:6px;cursor:pointer;border:0;color:inherit' + (p.id === UN.sel ? ';outline:3px solid var(--accent)' : '') + '">' + pbadge(p) + '<b class="ell" style="max-width:100%;font-size:12.5px">' + esc(p.name) + '</b><span class="muted" style="font-size:11px">' + (p.size ? fmtBytes(p.size) : '') + '</span></button>'; }).join('') + '</div>';
      else if (UN.view === 'list') rows = '<div class="list">' + list.map(function (p) { return '<button type="button" class="item hist" data-prog="' + esc(p.id) + '" aria-pressed="' + (p.id === UN.sel) + '" style="grid-template-columns:auto minmax(0,1fr)' + (p.id === UN.sel ? ';outline:3px solid var(--accent)' : '') + '">' + pbadge(p) + '<b class="ell">' + esc(p.name) + '</b></button>'; }).join('') + '</div>';
      else rows = '<table class="ctable utable"><thead><tr><th></th><th>Program</th><th>Company</th><th>Version</th><th>Size</th><th>Installed</th></tr></thead><tbody>' + list.map(function (p) { return '<tr data-prog="' + esc(p.id) + '"' + (p.id === UN.sel ? ' class="on"' : '') + ' tabindex="0"><td>' + pbadge(p) + '</td><td><b>' + esc(p.name) + '</b></td><td class="muted">' + esc(p.publisher) + '</td><td class="muted">' + esc(p.version) + '</td><td class="muted">' + (p.size ? fmtBytes(p.size) : '') + '</td><td class="muted">' + esc(p.date) + '</td></tr>'; }).join('') + '</tbody></table>';
      var detail = sel ? '<div class="card stack" id="uSel"><div class="row sb"><div class="filebox">' + pbadge(sel) + '<div class="stack" style="gap:2px;min-width:0"><b class="ell">' + esc(sel.name) + '</b><span class="muted">' + esc(sel.publisher || 'unknown company') + (sel.version ? ' · ' + esc(sel.version) : '') + (sel.size ? ' · ' + fmtBytes(sel.size) : '') + (sel.date ? ' · installed ' + esc(sel.date) : '') + '</span></div></div>' +
        '<div class="row"><button type="button" class="btn ghost sm" id="uRunIt">Run</button><button type="button" class="btn ghost sm" id="uWhere">Folder</button><button type="button" class="btn ghost sm" id="uMore" aria-label="More for this program">⋯ More</button><button type="button" class="btn" id="uUn">Uninstall…</button></div></div></div>' : '';
      body = head + (UN.progs === null ? '<div class="card"><span class="muted">Reading the installed programs from Windows…</span></div>' : rows) + detail +
        '<span class="muted">Right-click a program for more (search online, its links, install folder, registry key, export the list). Windows and Microsoft Store apps are in the Windows apps tab.</span>';
    } else if (UN.tab === 'apps') {
      var al = UN.apps ? appsShown() : [], asel = (UN.apps || []).filter(function (a) { return a.id === UN.asel; })[0];
      var hiddenCount = (UN.apps || []).filter(function (a) { return !a.visible; }).length;
      body = '<div class="row sb"><input class="field" id="uAq" placeholder="Search Windows apps…" value="' + esc(UN.aq) + '" aria-label="Search Windows apps" style="max-width:340px"><div class="row"><span class="muted">' + (UN.apps ? al.length + ' apps' : 'Reading…') + '</span>' +
        '<button type="button" class="chip" id="uHidden" aria-pressed="' + UN.hidden + '">Show hidden parts (' + hiddenCount + ')</button></div></div>' +
        (UN.apps === null ? '<div class="card"><span class="muted">Asking Windows for its apps…</span></div>' :
        '<table class="ctable utable"><thead><tr><th></th><th>App</th><th>Maker</th><th>Version</th><th></th></tr></thead><tbody>' + al.map(function (a) { return '<tr data-app="' + esc(a.id) + '"' + (a.id === UN.asel ? ' class="on"' : '') + ' tabindex="0"><td>' + pbadge(a) + '</td><td><b>' + esc(a.name) + '</b>' + (a.visible ? '' : ' <span class="muted" style="font-size:11px">' + esc(a.package) + '</span>') + '</td><td class="muted">' + esc(a.publisher) + '</td><td class="muted">' + esc(a.version) + '</td><td>' + careTag(a) + '</td></tr>'; }).join('') + '</tbody></table>') +
        (asel ? '<div class="card stack" id="uSel"><div class="row sb"><div class="filebox">' + pbadge(asel) + '<div class="stack" style="gap:2px;min-width:0"><b class="ell">' + esc(asel.name) + '</b><span class="muted">' + esc(asel.publisher) + ' · ' + esc(asel.version) + ' · ' + esc(asel.package) + '</span></div></div>' +
          '<div class="row"><button type="button" class="btn ghost sm" id="uAppMore" aria-label="More for this app">⋯ More</button><button type="button" class="btn" id="uAppUn">Remove…</button></div></div>' +
          (asel.careWhy ? '<span class="' + (asel.care === 'danger' ? 'badc' : asel.care === 'warn' ? 'warnc' : 'muted') + '">' + esc(asel.careWhy) + '</span>' : '') + '</div>' : '') +
        '<span class="muted">"Hidden parts" are codecs, runtimes and helpers without a Start-menu entry: most are needed by other apps.</span>';
    } else if (UN.tab === 'hunt') {
      body = '<div class="card stack"><b>Leftover hunt</b><span class="muted">For programs that are already gone (removed earlier, or an uninstaller that left things behind): Toolbelt scans like after an uninstall, by name. The results open in the same leftover trees. Anything still used by something installed is greyed out and can\'t be removed; Windows\' own folders and keys are never offered.</span>' +
        '<div class="row nw"><input class="field" id="uHq" value="' + esc(UN.hq) + '" placeholder="a program or company name, e.g. Roblox, Overwolf, Opera" aria-label="Name to look for" style="max-width:420px"><button type="button" class="btn" id="uHunt">Scan</button></div>' + modeRadios('uMode') + '</div>';
    } else {
      var tools = [['apps', 'Apps & features', 'Windows\' own list, also Microsoft Store apps'], ['startup', 'Startup apps', 'the same switches, in Settings'], ['update', 'Windows Update', 'also the drivers it offers'], ['storage', 'Storage sense', 'temporary files and what takes space'],
        ['cleanmgr', 'Disk Cleanup', 'the classic cleaner'], ['devmgmt', 'Device Manager', 'every device and its driver'], ['services', 'Services', 'what runs in the background'], ['msconfig', 'System Configuration', 'boot and services switches'], ['taskmgr', 'Task Manager', 'what runs now'], ['protection', 'System Protection', 'restore points on or off'], ['control', 'Control Panel', 'the old one']];
      body = '<div class="row sb"><span class="muted">Windows\' own tools, one click away.</span><div class="row"><button type="button" class="btn ghost sm" id="uBk">Registry backups</button><button type="button" class="btn ghost sm" id="uRp">Make a restore point now</button></div></div><div class="mgrid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr))">' + tools.map(function (t) { return '<button type="button" class="card stack lift" data-tool="' + t[0] + '" style="cursor:pointer;border:0;color:inherit;text-align:left;gap:3px"><b>' + t[1] + '</b><span class="muted">' + t[2] + '</span></button>'; }).join('') + '</div>' +
        '<div class="card stack"><div class="row sb"><b>Restore points</b><button type="button" class="btn ghost sm" id="uRps">Show</button></div>' + (UN.rps ? (UN.rps.length ? '<div class="list">' + UN.rps.map(function (r) { return '<div class="item"><span class="muted">' + esc(r.When || '') + '</span><span>' + esc(r.Description || '') + '</span><span></span></div>'; }).join('') + '</div>' : '<span class="muted">None. System Protection may be off: turn it on under System Protection above.</span>') : '') + '</div>';
    }
    return '<div class="row sb"><h2 class="h">Uninstall</h2><div class="row"><span class="tag ok">restore point before every uninstall</span><button type="button" class="btn ghost sm" id="uRef"' + (UN.busy || UN.abusy ? ' disabled' : '') + '>Refresh</button></div></div>' +
      '<div class="tabs" role="tablist">' + UTABS.map(function (t) { return '<button type="button" class="chip" role="tab" data-utab="' + t[0] + '" aria-pressed="' + (UN.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' + body;
  };
  WIRE.unin = function (m) {
    if (UN.tab === 'progs' && UN.progs === null && !UN.busy) loadProgs(false);
    if (UN.tab === 'apps' && UN.apps === null && !UN.abusy) loadApps(false);
    $$('[data-utab]', m).forEach(function (b) { b.onclick = function () { UN.tab = b.getAttribute('data-utab'); go('unin', true); }; });
    $$('[data-uview]', m).forEach(function (b) { b.onclick = function () { UN.view = b.getAttribute('data-uview'); go('unin', true); }; });
    var r = $('#uRef', m); if (r) r.onclick = function () { if (UN.tab === 'apps') { UN.apps = null; go('unin', true); loadApps(true); } else { UN.progs = null; go('unin', true); loadProgs(true); } };
    function keepTyping(id, key) { var el = $('#' + id, m); if (el) el.oninput = function () { UN[key] = el.value; var pos = el.selectionStart; go('unin', true); var again = $('#' + id); if (again) { again.focus(); try { again.setSelectionRange(pos, pos); } catch (e) {} } }; }
    keepTyping('uQ', 'q'); keepTyping('uAq', 'aq');
    $$('[data-prog]', m).forEach(function (b) {
      var id = b.getAttribute('data-prog');
      var pick = function () { if (UN.sel !== id) { UN.sel = id; go('unin', true); } };
      b.onclick = pick;
      b.onkeydown = function (e) { if (e.key === 'Enter') pick(); else if (e.key === 'Delete') { UN.sel = id; rvOpen('program', id); } };
      b.ondblclick = function () { UN.sel = id; rvOpen('program', id); };
      b.oncontextmenu = function (e) { e.preventDefault(); UN.sel = id; go('unin', true); progMenu('program', id, e.clientX, e.clientY); };
    });
    $$('[data-app]', m).forEach(function (b) {
      var id = b.getAttribute('data-app');
      var pick = function () { if (UN.asel !== id) { UN.asel = id; go('unin', true); } };
      b.onclick = pick;
      b.onkeydown = function (e) { if (e.key === 'Enter') pick(); };
      b.oncontextmenu = function (e) { e.preventDefault(); UN.asel = id; go('unin', true); progMenu('app', id, e.clientX, e.clientY); };
    });
    var hid = $('#uHidden', m); if (hid) hid.onclick = function () { UN.hidden = !UN.hidden; go('unin', true); };
    var un = $('#uUn', m); if (un) un.onclick = function () { rvOpen('program', UN.sel); };
    var aun = $('#uAppUn', m); if (aun) aun.onclick = function () { rvOpen('app', UN.asel); };
    var more = $('#uMore', m); if (more) more.onclick = function (e) { e.stopPropagation(); var b = more.getBoundingClientRect(); progMenu('program', UN.sel, b.left, b.bottom + 4); };
    var amore = $('#uAppMore', m); if (amore) amore.onclick = function (e) { e.stopPropagation(); var b = amore.getBoundingClientRect(); progMenu('app', UN.asel, b.left, b.bottom + 4); };
    var hq = $('#uHq', m); if (hq) { hq.oninput = function () { UN.hq = hq.value; }; hq.onkeydown = function (e) { if (e.key === 'Enter') $('#uHunt', m).click(); }; }
    $$('input[name="uMode"]', m).forEach(function (c) { c.onchange = function () { setScanMode(c.value); }; });
    var hb = $('#uHunt', m); if (hb) hb.onclick = function () { UN.hq = $('#uHq', m).value.trim(); rvHunt(UN.hq); };
    var ri = $('#uRunIt', m); if (ri) ri.onclick = function () { api('pc_run', UN.sel).then(function (res) { toast(res.message); }).catch(fail); };
    var wh = $('#uWhere', m); if (wh) wh.onclick = function () { api('pc_open_location', UN.sel).then(function (res) { toast(res.message); }).catch(fail); };
    $$('[data-tool]', m).forEach(function (b) { b.onclick = function () { api('pc_tool', b.getAttribute('data-tool')).then(function (res) { if (res.message) toast(res.message); }).catch(fail); }; });
    var rp = $('#uRp', m); if (rp) rp.onclick = function () { toast('Asking Windows (an admin question appears)…'); api('pc_restore_point').then(function (res) { toast(res.message); UN.rps = null; }).catch(fail); };
    var rps = $('#uRps', m); if (rps) rps.onclick = function () { api('pc_restore_points').then(function (list) { UN.rps = list || []; go('unin', true); }).catch(fail); };
    var bk = $('#uBk', m); if (bk) bk.onclick = function () { api('pc_open_backups').then(function (res) { toast(res.message); }).catch(fail); };
  };
  function setScanMode(v) { scanMode = v; try { localStorage.setItem('toolbelt-scan-mode', v); } catch (e) {} }

  // the right-click menu (Revo's): uninstall, search online, the program's own links, its folder, its registry key, export the list
  function progMenu(kind, id, x, y) {
    var old = $('#appMenu'); if (old) old.remove();
    var p = (kind === 'app' ? UN.apps : UN.progs || []).filter(function (q) { return q.id === id; })[0];
    if (!p) return;
    var items = kind === 'app'
      ? [['un', 'Remove…'], ['-'], ['google', 'Search online for "' + p.name + '"'], ['data', 'Open its data folder', !p.data]]
      : [['un', 'Uninstall…'], ['run', 'Run', !p.icon], ['-'], ['google', 'Search online for "' + p.name + '"'], ['about', 'Open About link', !p.about], ['help', 'Open Help link', !p.help], ['update', 'Open Update link', !p.update], ['-'],
        ['where', 'Install location', !p.location && !p.icon], ['regedit', 'Open registry key…', !p.key], ['-'], ['csv', 'Export list as CSV (Excel)'], ['html', 'Export list as web page']];
    var menu = document.createElement('div'); menu.className = 'cmenu'; menu.id = 'appMenu'; menu.setAttribute('role', 'menu');
    menu.innerHTML = items.map(function (i) { return i[0] === '-' ? '<hr>' : '<button type="button" role="menuitem" data-pm="' + i[0] + '"' + (i[2] ? ' disabled' : '') + '>' + esc(i[1]) + '</button>'; }).join('');
    var app = $('#app'), rect = app.getBoundingClientRect();
    app.appendChild(menu);
    menu.style.left = Math.max(4, Math.min(x - rect.left, rect.width - menu.offsetWidth - 8)) + 'px';
    menu.style.top = Math.max(4, Math.min(y - rect.top, rect.height - menu.offsetHeight - 8)) + 'px';
    $$('[data-pm]', menu).forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation(); menu.remove();
        var k = b.getAttribute('data-pm');
        var say = function (res) { if (res && res.message) toast(res.message); };
        if (k === 'un') rvOpen(kind, id);
        else if (k === 'run') api('pc_run', id).then(say).catch(fail);
        else if (k === 'where') api('pc_open_location', id).then(say).catch(fail);
        else if (k === 'csv' || k === 'html') api('pc_export_programs', k).then(say).catch(fail);
        else api('pc_program_action', id, k).then(say).catch(fail);
      };
    });
    var first = $('button:not([disabled])', menu); if (first) first.focus();
    menu.addEventListener('keydown', function (e) {
      var bs = $$('button:not([disabled])', menu), k = bs.indexOf(document.activeElement);
      if (e.key === 'Escape') menu.remove();
      else if (e.key === 'ArrowDown') { e.preventDefault(); bs[(k + 1) % bs.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); bs[(k - 1 + bs.length) % bs.length].focus(); }
    });
  }

  // ---------- the dialog: confirm → steps (restore point, its uninstaller, scan mode) → scanning → registry → files ----------
  var RV = null;
  var HIVE_NAME = { HKCU: 'HKEY_CURRENT_USER', HKLM: 'HKEY_LOCAL_MACHINE' };
  var STEP_ICON = { todo: '<span class="sti todo">○</span>', busy: '<span class="sti busy" aria-label="busy"></span>', done: '<span class="sti done">✓</span>', failed: '<span class="sti bad">✕</span>', skipped: '<span class="sti todo">–</span>' };
  function rvNew(kind, id, item) { return { kind: kind, id: id, item: item, page: 'confirm', rp: true, status: null, res: null, tick: {}, fold: {}, gone: {}, why: {}, admin: [], sure: false, busy: false, msg: '', backup: '', timer: null, last: '' }; }
  function rvOpen(kind, id) {
    var item = (kind === 'app' ? UN.apps : UN.progs || []).filter(function (q) { return q.id === id; })[0];
    if (!item) { toast('Pick a program first.'); return; }
    if (RV && RV.timer) clearInterval(RV.timer);
    RV = rvNew(kind, id, item);
    rvRender();
  }
  function rvHunt(name) {
    api('pc_revo_hunt', name, scanMode).then(function (res) {
      if (!res.ok) { toast(res.message); return; }
      if (RV && RV.timer) clearInterval(RV.timer);
      RV = rvNew('hunt', '', { name: name });
      RV.page = 'scanning';
      rvRender(); rvWatch();
    }).catch(fail);
  }
  function rvWatch() { if (RV.timer) clearInterval(RV.timer); RV.timer = setInterval(rvPoll, 600); rvPoll(); }
  function rvPoll() {
    if (!RV) return;
    api('pc_revo_status').then(function (s) {
      if (!RV) return;
      RV.status = s;
      if (s.phase === 'scanning' && RV.page !== 'scanning') RV.page = 'scanning';
      if (s.phase === 'scanned' && RV.page === 'scanning') {
        clearInterval(RV.timer); RV.timer = null;
        api('pc_revo_result').then(function (res) {
          if (!RV) return;
          RV.res = res; RV.tick = {}; RV.gone = {}; RV.why = {}; RV.admin = [];
          RV.page = res.registry.length ? 'reg' : res.files.length ? 'files' : 'none';
          rvRender();
        }).catch(fail);
        return;
      }
      if ((s.phase === 'uninstalled' || s.phase === 'idle') && RV.page === 'scanning') RV.page = RV.kind === 'hunt' ? 'none' : 'steps';
      var now = JSON.stringify([RV.page, s]);
      if (now !== RV.last) { RV.last = now; rvRender(); }
    }).catch(function () {});
  }
  function rvClose() {
    var s = RV.status;                                       // the restore point or the scan must finish first; an open uninstaller may stay
    if (s && (s.phase === 'scanning' || (s.phase === 'working' && !s.running))) { toast('Still busy: wait until this step is done.'); return; }
    if (RV.timer) clearInterval(RV.timer);
    var wasProg = RV.kind;
    RV = null;
    var dim = $('#rvDim'); if (dim) dim.remove();
    api('pc_revo_close').catch(function () {});
    if (wasProg === 'program') { UN.progs = null; UN.sel = ''; loadProgs(true); }
    else if (wasProg === 'app') { UN.apps = null; UN.asel = ''; loadApps(true); }
    if (st.screen === 'unin') go('unin', true);
  }
  function rvHead(title, sub) { return '<div class="row sb rvhead"><div class="stack" style="gap:2px"><h3 class="h" id="rvT">' + esc(title) + '</h3>' + (sub ? '<span class="muted">' + sub + '</span>' : '') + '</div><button type="button" class="ico" id="rvX" aria-label="Close">✕</button></div>'; }
  function rvConfirm() {
    var p = RV.item, app = RV.kind === 'app';
    var facts = app ? [p.publisher, p.version, p.package] : [p.size ? fmtBytes(p.size) : '', p.version, p.date, p.publisher];
    return rvHead(app ? 'Are you sure you want to remove the selected app?' : 'Are you sure you want to uninstall the selected program?') +
      '<div class="rvwho">' + pbadge(p, true) + '<div class="stack" style="gap:3px;min-width:0"><b style="font-size:16px">' + esc(p.name) + '</b>' +
      facts.filter(Boolean).map(function (f) { return '<span class="muted">' + esc(f) + '</span>'; }).join('') +
      (!app && (p.uninstall || p.quiet) ? '<span class="mono ell muted" style="font-size:11.5px" title="' + esc(p.uninstall || p.quiet) + '">' + esc(p.uninstall || p.quiet) + '</span>' : '') + '</div></div>' +
      (p.careWhy ? '<span class="' + (p.care === 'danger' ? 'badc' : 'warnc') + '">' + esc(p.careWhy) + (p.care === 'danger' ? ' Are you sure?' : '') + '</span>' : '') +
      '<label class="row nw" style="gap:8px;cursor:pointer"><input type="checkbox" id="rvRp"' + (RV.rp ? ' checked' : '') + '><span>Make a System Restore Point before ' + (app ? 'removing' : 'uninstall') + ' <span class="muted">(Windows asks for admin once)</span></span></label>' +
      '<div class="row" style="justify-content:flex-end"><button type="button" class="btn" id="rvGo">Continue</button><button type="button" class="btn ghost" id="rvCancel">Cancel</button></div>';
  }
  function rvSteps() {
    var s = RV.status || { phase: 'working', steps: [], scan: {} }, ready = s.phase === 'uninstalled', name = RV.item.name;
    var listed = s.listed === false ? '<span class="okc">✓ Windows no longer lists ' + esc(name) + '.</span>' : (s.listed === true && ready) ? '<span class="warnc">Windows still lists ' + esc(name) + '. If its uninstaller was cancelled, nothing was removed; if it\'s still working, wait.</span>' : '';
    return rvHead((RV.kind === 'app' ? 'Removing ' : 'Uninstalling ') + name, 'Performing the initial analysis and uninstall') +
      '<div class="rvsteps">' + (s.steps || []).map(function (x) { return '<div class="step ' + x.state + '">' + (STEP_ICON[x.state] || '') + '<div class="stack" style="gap:2px"><span>' + esc(x.text) + (x.state === 'done' && x.key !== 'scan' ? ' - done!' : '') + '</span>' + (x.note ? '<span class="muted">' + esc(x.note) + '</span>' : '') + '</div></div>'; }).join('') + '</div>' +
      (s.phase === 'rp-failed' ? '<div class="card stack"><b class="warnc">No restore point was made.</b><span class="muted">Turn System Protection on (Windows tools tab) to get restore points. Uninstall without one?</span><div class="row"><button type="button" class="btn" id="rvGoOn">Uninstall without it</button><button type="button" class="btn ghost" id="rvCancel">Cancel</button></div></div>' : '') +
      listed + (s.error ? '<span class="badc">' + esc(s.error) + '</span>' : '') + modeRadios('rvMode') +
      '<div class="row" style="justify-content:flex-end"><button type="button" class="btn" id="rvScan"' + (ready ? '' : ' disabled') + '>Scan</button><button type="button" class="btn ghost" id="rvCancel"' + (s.phase === 'working' && s.running ? ' disabled' : '') + '>Close</button></div>';
  }
  function rvScanning() {
    var sc = (RV.status && RV.status.scan) || { progress: 0, message: 'Starting…', mode: scanMode };
    return rvHead(RV.kind === 'hunt' ? 'Leftover hunt: ' + RV.item.name : 'Scanning for leftovers of ' + RV.item.name, (SCAN_MODES.filter(function (x) { return x[0] === sc.mode; })[0] || ['', ''])[1] + ' scan') +
      '<div class="stack" style="gap:6px;padding:18px 0"><div class="bar big run"><i style="width:' + Math.max(4, sc.progress || 0) + '%"></i></div><span class="muted">' + esc(sc.message || '') + '</span></div>' +
      '<div class="row" style="justify-content:flex-end"><button type="button" class="btn ghost" id="rvStop">Stop</button></div>';
  }
  function rvNone() {
    var mode = RV.res ? RV.res.mode : scanMode, err = RV.status && RV.status.error;
    return rvHead(err ? 'The scan stopped' : 'No leftovers found', esc((SCAN_MODES.filter(function (x) { return x[0] === mode; })[0] || ['', ''])[1]) + ' scan for ' + esc(RV.item.name)) +
      (err ? '<span class="badc">' + esc(err) + '</span>' : '<span class="okc">Nothing left behind. Clean.</span>') +
      '<div class="row" style="justify-content:flex-end">' + (mode !== 'advanced' && RV.kind !== 'hunt' ? '<button type="button" class="btn ghost" id="rvDeeper">Scan again, Advanced</button>' : '') + '<button type="button" class="btn" id="rvFin">Finish</button></div>';
  }
  // ----- the trees -----
  function rvNodes(list, kind) {
    var root = { kids: [], map: {} }, all = [];
    function child(parent, key, name) {
      if (!parent.map[key]) { var n = { key: key, name: name, kids: [], map: {}, items: [], depth: parent.depth === undefined ? 0 : parent.depth + 1 }; parent.map[key] = n; parent.kids.push(n); all.push(n); }
      return parent.map[key];
    }
    list.forEach(function (it) {
      var segs = kind === 'reg' ? [HIVE_NAME[it.hive] || it.hive].concat(it.path.split('\\')) : it.path.split('\\');
      var node = root, key = '';
      segs.forEach(function (s) { key += (key ? '\\' : '') + s.toLowerCase(); node = child(node, key, s); });
      if (it.kind === 'value') { var v = child(node, key + '::' + it.name, it.name + ' - ' + it.data); v.leaf = true; v.items.push(it); }
      else node.items.push(it);
    });
    return { root: root, all: all };
  }
  function freeUnder(n) {                                     // the tickable items of this node and everything below it
    var out = n.items.filter(function (it) { return !it.inUse && !RV.gone[it.id]; });
    n.kids.forEach(function (k) { out = out.concat(freeUnder(k)); });
    return out;
  }
  function rvTreeHtml(tree) {
    var html = '';
    function row(n) {
      var free = freeUnder(n), on = free.filter(function (it) { return RV.tick[it.id]; }).length, it = n.items[0];
      var found = n.items.length > 0, folded = RV.fold[n.key];
      var used = found && n.items.every(function (x) { return x.inUse; }), gone = found && n.items.every(function (x) { return RV.gone[x.id]; });
      var tags = '';
      if (found) {
        if (gone) tags += '<span class="tag ok">removed</span>';
        else if (used) tags += '<span class="tag">in use: ' + esc(it.inUse) + '</span>';
        if (it.area === 'windows' && !gone) tags += '<span class="tag warn">Windows area</span>';
        if (RV.why[it.id]) tags += '<span class="badc" style="font-size:12px">' + esc(RV.why[it.id]) + '</span>';
        if (it.size) tags += '<span class="tsize">' + fmtSize(it.size) + '</span>';
        tags += '<span class="muted" style="font-size:11.5px">' + esc(it.how) + '</span>';
      }
      html += '<div class="tn' + (found ? ' found' : '') + (used ? ' used' : '') + (gone ? ' gone' : '') + '" style="--d:' + n.depth + '">' +
        (n.kids.length || (it && it.values && it.values.length) ? '<button type="button" class="tog" data-fold="' + esc(n.key) + '" aria-label="' + (folded ? 'Open' : 'Fold') + '" aria-expanded="' + !folded + '">' + (folded ? '+' : '−') + '</button>' : '<span class="tog"></span>') +
        '<input type="checkbox" data-tk="' + esc(n.key) + '"' + (free.length && on === free.length ? ' checked' : '') + (free.length ? '' : ' disabled') + (on && on < free.length ? ' data-mixed="1"' : '') + ' aria-label="' + esc(n.name) + '">' +
        '<span class="tl' + (n.leaf ? ' mono' : '') + '">' + esc(n.name) + '</span>' + tags + '</div>';
      if (folded) return;
      if (it && it.kind === 'key' && it.values && it.values.length) {
        it.values.forEach(function (v) { html += '<div class="tn val" style="--d:' + (n.depth + 1) + '"><span class="tog"></span><span class="tl mono">' + esc(v[0]) + ' - ' + esc(v[1]) + '</span></div>'; });
        if (it.more) html += '<div class="tn val" style="--d:' + (n.depth + 1) + '"><span class="tog"></span><span class="tl muted">… and ' + it.more + ' more inside</span></div>';
      }
      n.kids.forEach(row);
    }
    tree.root.kids.forEach(row);
    return html;
  }
  function rvList() { return RV.page === 'reg' ? RV.res.registry : RV.res.files; }
  function rvTrees() {
    var list = rvList(), kind = RV.page, tree = rvNodes(list, kind);
    RV.tree = tree;
    var free = list.filter(function (it) { return !it.inUse && !RV.gone[it.id]; }), picked = free.filter(function (it) { return RV.tick[it.id]; });
    var usedN = list.filter(function (it) { return it.inUse && !RV.gone[it.id]; }).length, goneN = list.filter(function (it) { return RV.gone[it.id]; }).length;
    var sum = function (arr) { return arr.reduce(function (t, it) { return t + (+it.size || 0); }, 0); };
    var foundSize = sum(list.filter(function (it) { return !RV.gone[it.id]; })), pickedSize = sum(picked), freeSize = sum(free);
    var mode = (SCAN_MODES.filter(function (x) { return x[0] === RV.res.mode; })[0] || ['', ''])[1];
    var title = kind === 'reg' ? 'Found leftover Registry items' : 'Found leftover files and folders';
    var hint = kind === 'reg' ? 'Bold items are the leftovers; the rest shows where they are. Each one is saved to a .reg backup before it\'s deleted.' : 'Bold items are the leftovers. Deleted files and folders go to the Recycle Bin.';
    var hasFiles = RV.res.files.length > 0, hasReg = RV.res.registry.length > 0;
    return rvHead(title, esc(mode) + ' scan · ' + esc(RV.item.name) + ' · ' + list.length + ' found (' + fmtSize(foundSize) + ')' + (usedN ? ', ' + usedN + ' still in use (greyed)' : '') + (goneN ? ', ' + goneN + ' removed' : '')) +
      '<span class="muted" style="font-size:12.5px">' + hint + '</span>' +
      '<div class="rtree" role="tree">' + rvTreeHtml(tree) + '</div>' +
      (RV.admin.length ? '<div class="card row sb"><span class="warnc">' + RV.admin.length + ' item' + (RV.admin.length === 1 ? ' needs' : 's need') + ' admin rights (Program Files, all-users settings).</span><button type="button" class="btn" id="rvAdmin"' + (RV.busy ? ' disabled' : '') + '>Delete as admin</button></div>' : '') +
      (RV.msg ? '<span class="muted" role="status">' + esc(RV.msg) + (RV.backup ? ' <button type="button" class="btn ghost sm" id="rvBk">Open backups</button>' : '') + '</span>' : '') +
      '<div class="rvsum" id="rvSum"><span>Ticked: <b>' + picked.length + ' of ' + free.length + '</b></span><span>To delete: <b class="big">' + fmtSize(pickedSize) + '</b> <span class="muted">of ' + fmtSize(freeSize) + ' that can go</span></span>' +
      (RV.freed ? '<span class="okc">Freed so far: ' + fmtSize(RV.freed) + '</span>' : '') + '</div>' +
      '<div class="row sb rvfoot"><div class="row"><button type="button" class="btn ghost sm" id="rvAll"' + (free.length ? '' : ' disabled') + '>Select all</button><button type="button" class="btn ghost sm" id="rvNone"' + (picked.length ? '' : ' disabled') + '>Deselect all</button>' +
      (RV.sure ? '<button type="button" class="btn" id="rvDelYes" style="background:var(--bad);color:#fff">Yes, delete ' + picked.length + ' (' + fmtSize(pickedSize) + ')</button><button type="button" class="btn ghost sm" id="rvDelNo">No</button>'
        : '<button type="button" class="btn" id="rvDel"' + (picked.length && !RV.busy ? '' : ' disabled') + '>' + (RV.busy ? 'Deleting…' : 'Delete' + (picked.length ? ' (' + picked.length + ' · ' + fmtSize(pickedSize) + ')' : '')) + '</button>') + '</div>' +
      '<div class="row">' + (kind === 'files' && hasReg ? '<button type="button" class="btn ghost" id="rvBack">Back</button>' : '') + (kind === 'reg' && hasFiles ? '<button type="button" class="btn" id="rvNext">Next</button>' : '<button type="button" class="btn" id="rvFin">Finish</button>') + '</div></div>';
  }
  function rvRender() {
    if (!RV) return;
    var dim = $('#rvDim');
    if (!dim) { dim = document.createElement('div'); dim.className = 'dim'; dim.id = 'rvDim'; $('#app').appendChild(dim); }
    var keepScroll = $('.rtree', dim) ? $('.rtree', dim).scrollTop : 0;
    var body = RV.page === 'confirm' ? rvConfirm() : RV.page === 'steps' ? rvSteps() : RV.page === 'scanning' ? rvScanning() : RV.page === 'none' ? rvNone() : rvTrees();
    dim.innerHTML = '<div class="dialog revo" role="dialog" aria-modal="true" aria-labelledby="rvT">' + body + '</div>';
    var tr = $('.rtree', dim); if (tr) tr.scrollTop = keepScroll;
    $$('[data-mixed]', dim).forEach(function (c) { c.indeterminate = true; });
    var on = function (id, fn) { var el = $('#' + id, dim); if (el) el.onclick = fn; };
    on('rvX', rvClose); on('rvCancel', rvClose); on('rvFin', rvClose);
    var rpBox = $('#rvRp', dim); if (rpBox) rpBox.onchange = function () { RV.rp = rpBox.checked; };
    on('rvGo', function () {
      $('#rvGo', dim).disabled = true;
      api('pc_revo_begin', RV.kind, RV.id, RV.rp).then(function (res) {
        if (!res.ok) { toast(res.message); rvRender(); return; }
        RV.page = 'steps'; RV.status = null; rvRender(); rvWatch();
      }).catch(fail);
    });
    on('rvGoOn', function () { api('pc_revo_go_on').then(function () { rvPoll(); }).catch(fail); });
    $$('input[name="rvMode"]', dim).forEach(function (c) { c.onchange = function () { setScanMode(c.value); }; });
    var scanNow = function (mode) { api('pc_revo_scan', mode).then(function (res) { if (!res.ok) { toast(res.message); return; } RV.page = 'scanning'; rvRender(); rvWatch(); }).catch(fail); };
    on('rvScan', function () { scanNow(scanMode); });
    on('rvDeeper', function () { setScanMode('advanced'); scanNow('advanced'); });
    on('rvStop', function () { api('pc_revo_cancel').catch(fail); });
    on('rvNext', function () { RV.page = 'files'; RV.sure = false; RV.msg = ''; rvRender(); });
    on('rvBack', function () { RV.page = 'reg'; RV.sure = false; RV.msg = ''; rvRender(); });
    on('rvBk', function () { api('pc_open_backups').then(function (res) { toast(res.message); }).catch(fail); });
    $$('[data-fold]', dim).forEach(function (b) { b.onclick = function () { var k = b.getAttribute('data-fold'); RV.fold[k] = !RV.fold[k]; rvRender(); }; });
    $$('[data-tk]', dim).forEach(function (c) {
      c.onchange = function () {
        var n = RV.tree.all.filter(function (x) { return x.key === c.getAttribute('data-tk'); })[0];
        if (!n) return;
        freeUnder(n).forEach(function (it) { RV.tick[it.id] = c.checked; });
        RV.sure = false; rvRender();
      };
    });
    on('rvAll', function () { rvList().forEach(function (it) { if (!it.inUse && !RV.gone[it.id]) RV.tick[it.id] = true; }); RV.sure = false; rvRender(); });
    on('rvNone', function () { rvList().forEach(function (it) { RV.tick[it.id] = false; }); RV.sure = false; rvRender(); });
    on('rvDel', function () { RV.sure = true; rvRender(); });
    on('rvDelNo', function () { RV.sure = false; rvRender(); });
    var del = function (ids, admin) {
      RV.busy = true; RV.sure = false; rvRender();
      if (admin) toast('Windows asks for admin once…');
      api('pc_revo_delete', ids, !!admin).then(function (res) {
        if (!RV) return;
        RV.busy = false;
        (res.done || []).forEach(function (i) { RV.gone[i] = true; RV.tick[i] = false; delete RV.why[i]; });
        (res.failed || []).forEach(function (f) { RV.why[f[0]] = f[1]; RV.tick[f[0]] = false; });
        RV.admin = res.needAdmin || [];
        if (res.backup) RV.backup = res.backup;
        RV.freed = (RV.freed || 0) + (+res.freed || 0);
        RV.msg = (res.message || '') + (res.freed ? ' Freed ' + fmtSize(res.freed) + '.' : '');
        rvRender();
      }).catch(function (e) { if (RV) { RV.busy = false; rvRender(); } fail(e); });
    };
    on('rvDelYes', function () { del(rvList().filter(function (it) { return RV.tick[it.id] && !it.inUse && !RV.gone[it.id]; }).map(function (it) { return it.id; }), false); });
    on('rvAdmin', function () { del(RV.admin.slice(), true); });
    dim.onkeydown = function (e) { if (e.key === 'Escape') rvClose(); };
    var focus = $('#rvGo, #rvScan:not([disabled]), #rvNext, #rvFin', dim); if (focus && !dim.contains(document.activeElement)) focus.focus();
  }
  T.revo = function () { return RV; };

  var PC = { tab: 'start', startup: null, busy: false, drv: null, dbusy: false, wuJob: null, wu: null, filter: 'all', ping: null, pingOn: false, hosts: [], hostIn: '' };
  try { var ph = JSON.parse(localStorage.getItem('toolbelt-ping-hosts') || '[]'); if (Array.isArray(ph)) PC.hosts = ph.slice(0, 5); } catch (e) {}
  var PCT = [['start', 'Startup'], ['drv', 'Drivers'], ['ping', 'Ping & lag']];
  var PCOL = ['#FF5C8A', '#5CC8FF', '#5CE08A', '#FFCF3F', '#B98CFF', '#FFB13B', '#FF6B7A', '#7FE0D0'];
  function drvBadge(s) { return { problem: '<span class="tag warn" style="color:var(--bad)">problem</span>', generic: '<span class="tag warn">generic</span>', old: '<span class="tag warn">old</span>', ok: '' }[s] || ''; }
  VIEWS.pc = function () {
    var body = '';
    if (PC.tab === 'start') {
      var s = PC.startup;
      body = s === null ? '<div class="card"><span class="muted">Reading what starts with Windows…</span></div>' :
        '<div class="row sb"><span class="muted">' + s.length + ' things start with Windows · ' + s.filter(function (e) { return e.enabled; }).length + ' switched on</span><button type="button" class="btn ghost sm" id="pcStRef">Refresh</button></div><div class="list">' + s.map(function (e) {
          return '<div class="item" style="grid-template-columns:auto auto minmax(0,1fr) auto"><button type="button" class="switch" role="switch" data-st="' + esc(e.id) + '" aria-checked="' + e.enabled + '" aria-label="Start ' + esc(e.name) + ' with Windows"' + (e.canToggle ? '' : ' disabled title="All users: switch it in Task Manager"') + '></button>' + (e.icon_data ? '<img class="appicon sm" src="' + e.icon_data + '" alt="">' : '<span class="badge" style="width:24px;height:24px;font-size:11px">' + esc(e.name.charAt(0)) + '</span>') +
            '<div class="stack" style="gap:2px;min-width:0"><b class="ell">' + esc(e.name) + '</b><span class="muted ell">' + esc(e.where) + ' · ' + esc(e.command) + '</span></div><span class="tag' + (e.enabled ? ' ok' : '') + '">' + (e.enabled ? 'starts' : 'off') + '</span></div>';
        }).join('') + '</div><span class="muted">Switching off only stops it starting by itself; the program stays installed. Same switches as Task Manager > Startup.</span>';
    } else if (PC.tab === 'drv') {
      var d = PC.drv;
      if (!d) body = '<div class="card"><span class="muted">Reading every driver from Windows (a few seconds)…</span></div>';
      else {
        var list = d.drivers, cnt = { problem: 0, generic: 0, old: 0 };
        list.forEach(function (x) { if (cnt[x.state] !== undefined) cnt[x.state]++; });
        var shown = list.filter(function (x) { return PC.filter === 'all' ? true : PC.filter === 'attention' ? x.state !== 'ok' : x.hardware; });
        var groups = []; shown.forEach(function (x) { if (groups.indexOf(x.group) === -1) groups.push(x.group); });
        var makers = {}; list.forEach(function (x) { if (x.page && x.hardware) makers[x.maker] = x.page; });
        var wuJob = PC.wuJob !== null ? st.jobs.filter(function (j) { return j.id === PC.wuJob; })[0] : null;
        body = '<div class="row sb"><div class="row"><span class="tag">' + list.length + ' drivers</span><span class="tag ' + (cnt.problem ? 'warn' : 'ok') + '">' + cnt.problem + ' with a problem</span><span class="tag' + (cnt.generic ? ' warn' : '') + '">' + cnt.generic + ' generic</span><span class="tag' + (cnt.old ? ' warn' : '') + '">' + cnt.old + ' old</span></div>' +
          '<div class="row">' + [['all', 'All'], ['hardware', 'Real devices'], ['attention', 'Needs attention']].map(function (f) { return '<button type="button" class="chip" data-dfilter="' + f[0] + '" aria-pressed="' + (PC.filter === f[0]) + '">' + f[1] + '</button>'; }).join('') + '<button type="button" class="btn ghost sm" id="drvRef">Refresh</button></div></div>' +
          '<div class="card row nw"><span class="badge" style="width:44px;height:44px;font-size:18px">▦</span><div class="grow" style="min-width:0"><b>' + esc(d.board.maker) + ' ' + esc(d.board.model) + '</b><span class="muted" style="display:block">BIOS ' + esc(d.board.bios) + (d.board.biosDate ? ' from ' + esc(d.board.biosDate) : '') + '. Sound, network and chipset drivers for this board come from its own support page. The BIOS is link-only: updating it is done on that page, carefully.</span></div>' + (d.board.page ? '<button type="button" class="btn ghost sm" id="drvBoard">Board support page</button>' : '') + '</div>' +
          '<div class="card stack"><div class="row sb"><b>Updates</b><div class="row"><button type="button" class="btn" id="drvWu"' + (wuJob && (wuJob.state === 'running' || wuJob.state === 'waiting') ? ' disabled' : '') + '>Ask Windows Update</button><button type="button" class="btn ghost sm" id="drvOptional">Optional updates</button>' + Object.keys(makers).map(function (k) { return '<button type="button" class="btn ghost sm" data-maker="' + esc(makers[k]) + '">' + esc(k) + ' drivers</button>'; }).join('') + '</div></div>' +
          (wuJob && (wuJob.state === 'running' || wuJob.state === 'waiting') ? '<span class="muted">Windows Update is looking (this can take a minute)…</span>' : wuJob && wuJob.state === 'failed' ? '<span class="err">' + esc(wuJob.message) + '</span>' :
            PC.wu ? (PC.wu.length ? '<div class="list">' + PC.wu.map(function (u) { return '<div class="item"><span class="warnc">↑</span><div style="min-width:0"><b class="ell">' + esc(u.Title) + '</b><span class="muted" style="display:block">' + esc(u.Maker || '') + ' · ' + esc(u.Class || '') + ' · ' + esc(u.Date || '') + (u.Size ? ' · ' + fmtBytes(u.Size) : '') + '</span></div><span></span></div>'; }).join('') + '</div><span class="muted">Install them from Windows Update > Optional updates (the button above): Windows makes the change and can roll it back.</span>' : '<span class="okc">Windows Update has no driver updates for this PC right now.</span>') :
            '<span class="muted">Toolbelt never downloads drivers itself: only Windows Update and the makers\' own pages (decided 13 Oct). Make a restore point first (Uninstall > Windows tools).</span>') + '</div>' +
          groups.map(function (g) {
            return '<h3 class="h">' + esc(g) + '</h3><div class="list">' + shown.filter(function (x) { return x.group === g; }).map(function (x) {
              return '<div class="item"><span class="badge" style="width:28px;height:28px;font-size:12px">' + esc(x.name.charAt(0)) + '</span><div style="min-width:0"><b class="ell">' + esc(x.name) + '</b> ' + drvBadge(x.state) +
                '<span class="muted" style="display:block">' + esc(x.provider || 'unknown maker') + ' · ' + esc(x.version) + (x.date ? ' · ' + esc(x.date) : '') + (x.hardware ? '' : ' · software device') + '</span>' + (x.why ? '<span class="muted" style="display:block;font-size:11.5px">' + esc(x.why) + '</span>' : '') + '</div>' +
                (x.page && x.state !== 'ok' ? '<button type="button" class="btn ghost sm" data-maker="' + esc(x.page) + '">' + esc(x.maker) + ' page</button>' : '<span></span>') + '</div>';
            }).join('') + '</div>';
          }).join('');
      }
    } else {
      var p = PC.ping;
      var order = p ? p.order : [];
      body = '<div class="row sb"><div class="row">' + (PC.pingOn ? '<button type="button" class="btn ghost sm" id="pingStop">Pause</button>' : '<button type="button" class="btn sm" id="pingGo">Start</button>') + '<span class="muted">' + (PC.pingOn ? 'pings every second, only while this tab is open' : 'paused') + '</span></div>' +
        '<div class="row nw"><input class="field" id="pingHost" value="' + esc(PC.hostIn) + '" placeholder="add a game server, e.g. play.hypixel.net" style="width:260px" aria-label="Host to add"><button type="button" class="btn ghost sm" id="pingAdd">Add</button></div></div>' +
        (PC.hosts.length ? '<div class="row">' + PC.hosts.map(function (h, i) { return '<span class="tag">' + esc(h) + ' <button type="button" class="ico" data-hdel="' + i + '" aria-label="Remove ' + esc(h) + '" style="padding:0 2px">✕</button></span>'; }).join('') + '</div>' : '') +
        '<div class="graph" style="height:160px"><canvas id="pingG"></canvas><div class="gl" id="pingLegend">' + order.map(function (k, i) { return '<span><i style="background:' + PCOL[i % PCOL.length] + '"></i>' + esc(p.targets[k].name) + '</span>'; }).join('') + '</div></div>' +
        '<div class="card verdict" id="pingVerdict">' + (p ? '<span class="mark ' + ({ ok: 'okc', warn: 'warnc', bad: 'badc' }[p.verdict.level] || 'muted') + '">' + ({ ok: '✓', warn: '!', bad: '!' }[p.verdict.level] || '…') + '</span><div><b>' + esc(p.verdict.text) + '</b></div>' : '<span class="muted">Press Start.</span>') + '</div>' +
        '<table class="ctable" id="pingTable"><thead><tr><th>Target</th><th>Now</th><th>Average</th><th>Jitter</th><th>Lost</th></tr></thead><tbody>' + order.map(function (k, i) { var t = p.targets[k]; return '<tr><td><span class="gdot" style="display:inline-block;background:' + PCOL[i % PCOL.length] + '"></span> <b>' + esc(t.name) + '</b> <span class="muted">' + esc(t.ip || 'no address') + '</span></td><td>' + (t.now == null ? (t.count ? '<span class="badc">lost</span>' : '—') : t.now + ' ms') + '</td><td>' + (t.avg == null ? '—' : t.avg + ' ms') + '</td><td>' + (t.jitter == null ? '—' : t.jitter + ' ms') + '</td><td class="' + (t.lost >= 3 ? 'badc' : '') + '">' + t.lost + '%</td></tr>'; }).join('') + '</tbody></table>' +
        (p && p.events.length ? '<span class="lbl">What happened</span><div class="list">' + p.events.slice(0, 12).map(function (e) { return '<div class="item"><span class="muted">' + esc(e.at) + '</span><span>' + esc(e.target) + ': ' + esc(e.what) + '</span><span></span></div>'; }).join('') + '</div>' : '') +
        '<span class="muted">Your router, the internet and Discord / Hypixel are always measured; add the address of a game server to compare. Some servers don\'t answer pings (then they show as lost).</span>';
    }
    return '<div class="row sb"><h2 class="h">PC care</h2><span class="tag ok">restore point before any driver change</span></div>' +
      '<div class="tabs" role="tablist">' + PCT.map(function (t) { return '<button type="button" class="chip" role="tab" data-pct="' + t[0] + '" aria-pressed="' + (PC.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' + body;
  };
  function loadStartup() { PC.busy = true; api('pc_startup').then(function (s) { PC.startup = s || []; PC.busy = false; if (st.screen === 'pc') go('pc', true); }).catch(function (e) { PC.busy = false; PC.startup = []; fail(e); }); }
  function loadDrivers(refresh) { PC.dbusy = true; api('pc_drivers', !!refresh).then(function (d) { PC.drv = d; PC.dbusy = false; if (st.screen === 'pc') go('pc', true); }).catch(function (e) { PC.dbusy = false; fail(e); }); }
  var pingTimer = null;
  function drawPing() {
    var c = $('#pingG'), p = PC.ping; if (!c || !c.clientWidth || !p) return;
    var w = c.clientWidth, ht = c.clientHeight, dpr = window.devicePixelRatio || 1; c.width = w * dpr; c.height = ht * dpr;
    var ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
    var cs = getComputedStyle($('#root')), line = cs.getPropertyValue('--line').trim(), ink2 = cs.getPropertyValue('--ink2').trim();
    var max = 20; p.order.forEach(function (k) { p.targets[k].samples.forEach(function (s) { if (s != null) max = Math.max(max, s); }); }); max = Math.ceil(max * 1.2 / 10) * 10;
    ctx.strokeStyle = line; ctx.lineWidth = 1; [0.25, 0.5, 0.75].forEach(function (f) { ctx.beginPath(); ctx.moveTo(0, ht * f); ctx.lineTo(w, ht * f); ctx.stroke(); });
    var n = 120;
    p.order.forEach(function (k, i) {
      var s = p.targets[k].samples, col = PCOL[i % PCOL.length];
      ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); var pen = false;
      s.forEach(function (v, j) { var x = (n - s.length + j) / (n - 1) * w; if (v == null) { pen = false; ctx.fillStyle = col; ctx.fillRect(x - 1, ht - 4, 3, 4); return; } var y = ht - v / max * (ht - 18) - 3; if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } });
      ctx.stroke();
    });
    ctx.fillStyle = ink2; ctx.font = '11px ' + cs.getPropertyValue('--body'); ctx.fillText(max + ' ms', w - 46, 14);
  }
  function pollPing() {
    if (st.screen !== 'pc' || PC.tab !== 'ping' || !PC.pingOn) { clearInterval(pingTimer); pingTimer = null; return; }
    api('ping_snapshot').then(function (snap) {
      var had = PC.ping ? PC.ping.order.join() : '';
      PC.ping = snap;
      if (had !== snap.order.join() || !$('#pingTable')) { go('pc', true); return; }
      var m = $('#screen'), keep = $('#pingHost', m), pos = keep && document.activeElement === keep ? keep.selectionStart : null;
      var v = $('#pingVerdict', m), t = $('#pingTable', m);
      var tmp = document.createElement('div'); tmp.innerHTML = VIEWS.pc();
      if (v) v.innerHTML = $('#pingVerdict', tmp).innerHTML;
      if (t) t.innerHTML = $('#pingTable', tmp).innerHTML;
      drawPing();
      if (pos !== null) { keep.focus(); try { keep.setSelectionRange(pos, pos); } catch (e) {} }
    }).catch(function () {});
  }
  function pingStart() { PC.pingOn = true; api('ping_start', PC.hosts).then(function () { if (!pingTimer) pingTimer = setInterval(pollPing, 1000); go('pc', true); }).catch(fail); }
  function pingStop() { PC.pingOn = false; clearInterval(pingTimer); pingTimer = null; api('ping_stop').catch(function () {}); }
  function saveHosts() { try { localStorage.setItem('toolbelt-ping-hosts', JSON.stringify(PC.hosts)); } catch (e) {} }
  WIRE.pc = function (m) {
    $$('[data-pct]', m).forEach(function (b) { b.onclick = function () { var to = b.getAttribute('data-pct'); if (PC.tab === 'ping' && to !== 'ping') pingStop(); PC.tab = to; go('pc', true); if (to === 'ping') pingStart(); }; });
    if (PC.tab === 'start' && PC.startup === null && !PC.busy) loadStartup();
    if (PC.tab === 'drv' && !PC.drv && !PC.dbusy) loadDrivers(false);
    if (PC.tab === 'ping' && !PC.pingOn && PC.ping === null) pingStart();
    var r = $('#pcStRef', m); if (r) r.onclick = function () { PC.startup = null; go('pc', true); loadStartup(); };
    $$('[data-st]', m).forEach(function (b) { b.onclick = function () { var on = b.getAttribute('aria-checked') !== 'true'; api('pc_set_startup', b.getAttribute('data-st'), on).then(function (res) { toast(res.message); if (res.ok) { b.setAttribute('aria-checked', String(on)); PC.startup = null; loadStartup(); } }).catch(fail); }; });
    var dr = $('#drvRef', m); if (dr) dr.onclick = function () { PC.drv = null; go('pc', true); loadDrivers(true); };
    $$('[data-dfilter]', m).forEach(function (b) { b.onclick = function () { PC.filter = b.getAttribute('data-dfilter'); go('pc', true); }; });
    var bd = $('#drvBoard', m); if (bd) bd.onclick = function () { api('pc_open_url', 'board').then(function (res) { toast(res.message); }).catch(fail); };
    var op = $('#drvOptional', m); if (op) op.onclick = function () { api('pc_open_url', 'optional').then(function (res) { toast(res.message); }).catch(fail); };
    $$('[data-maker]', m).forEach(function (b) { b.onclick = function () { api('pc_open_url', 'maker', b.getAttribute('data-maker')).then(function (res) { toast(res.message); }).catch(fail); }; });
    var wu = $('#drvWu', m); if (wu) wu.onclick = function () { PC.wu = null; api('pc_wu_drivers').then(function (res) { PC.wuJob = res.id; pollJobs(); go('pc', true); }).catch(fail); };
    var pg = $('#pingGo', m); if (pg) pg.onclick = pingStart;
    var ps = $('#pingStop', m); if (ps) ps.onclick = function () { pingStop(); go('pc', true); };
    var hi = $('#pingHost', m); if (hi) { hi.oninput = function () { PC.hostIn = hi.value; }; hi.onkeydown = function (e) { if (e.key === 'Enter') $('#pingAdd', m).click(); }; }
    var pa = $('#pingAdd', m); if (pa) pa.onclick = function () { var h = (PC.hostIn || '').trim().replace(/^https?:\/\//, '').split('/')[0]; if (!h) { toast('Type a server address first.'); return; } if (PC.hosts.indexOf(h) === -1 && PC.hosts.length < 5) PC.hosts.push(h); PC.hostIn = ''; saveHosts(); pingStart(); };
    $$('[data-hdel]', m).forEach(function (b) { b.onclick = function () { PC.hosts.splice(+b.getAttribute('data-hdel'), 1); saveHosts(); pingStart(); }; });
    $$('[data-tool]', m).forEach(function (b) { b.onclick = function () { api('pc_tool', b.getAttribute('data-tool')).then(function (res) { if (res.message) toast(res.message); }).catch(fail); }; });
    drawPing();
  };
  function pcJobsTick() {                                  // called from pollJobs: the Windows Update question finishing
    if (PC.wuJob === null || PC.wu !== null) return;
    var j = st.jobs.filter(function (x) { return x.id === PC.wuJob; })[0];
    if (j && j.state === 'done') { PC.wu = j.extra.updates || []; if (st.screen === 'pc') go('pc', true); }
    else if (j && j.state === 'failed' && st.screen === 'pc' && PC.tab === 'drv' && $('#drvWu') && $('#drvWu').disabled) go('pc', true);
  }

  // ---------- step 8: check a file ----------
  var CHK = [['hash', 'Fingerprints'], ['sign', 'Signed by'], ['compare', 'Compare two'], ['folder', 'Whole folder'], ['what', 'What is it really']];
  var CK = { tab: 'hash', file: null, hashes: null, hashJob: null, pasted: '', verdict: null, sign: null, other: null, cmp: null, cmpJob: null, folder: null, fjob: null, fres: null, sniff: null };
  function ckFileBox(f, id, label) {
    if (!f) return '<div class="card drop stack" style="align-items:center;text-align:center;padding:18px"><b>' + esc(label || 'Drop a file here or anywhere on Toolbelt') + '</b><span class="muted">or</span><button type="button" class="btn" id="' + id + '">Pick a file</button></div>';
    return '<div class="card filebox"><span class="badge">' + esc((f.name.split('.').pop() || '?').toUpperCase().slice(0, 4)) + '</span><div class="stack grow" style="gap:2px;min-width:0"><b class="ell">' + esc(f.name) + '</b><span class="muted">' + fmtBytes(f.size) + '</span></div><button type="button" class="btn ghost sm" id="' + id + '">Change</button></div>';
  }
  function ckTake(promise, slot) {
    return promise.then(function (r) {
      if (!r.ok) { if (r.message) toast(r.message); return; }
      if (slot === 'other') CK.other = r.file; else { CK.file = r.file; CK.hashes = null; CK.hashJob = null; CK.verdict = null; CK.sign = null; CK.sniff = null; CK.cmp = null; }
      go('check', true);
    }).catch(fail);
  }
  VIEWS.check = function () {
    var f = CK.file, body = '';
    if (CK.tab === 'hash') {
      var job = CK.hashJob !== null ? st.jobs.filter(function (j) { return j.id === CK.hashJob; })[0] : null;
      body = ckFileBox(f, 'ckPick') + (f ? (CK.hashes ? '<div class="list">' + [['MD5', 'md5'], ['SHA-1', 'sha1'], ['SHA-256', 'sha256'], ['SHA-512', 'sha512']].map(function (a) {
          return '<div class="hashrow' + (CK.verdict && CK.verdict.ok && CK.verdict.algo === a[1] ? ' hit' : '') + '"><b>' + a[0] + '</b><code>' + esc(CK.hashes[a[1]]) + '</code><button type="button" class="btn ghost sm" data-ckcopy="' + esc(CK.hashes[a[1]]) + '">Copy</button></div>';
        }).join('') + '</div><label class="lbl" for="ckPaste">Paste the one from the website</label><input class="field mono" id="ckPaste" value="' + esc(CK.pasted) + '" placeholder="any of the four kinds; Toolbelt sees which one it is" autocomplete="off" spellcheck="false">' +
        '<div class="card verdict">' + (CK.verdict ? '<span class="mark ' + (CK.verdict.ok ? 'okc' : CK.verdict.algo ? 'badc' : 'warnc') + '">' + (CK.verdict.ok ? '✓' : '!') + '</span><div><b>' + (CK.verdict.ok ? 'Matches' : CK.verdict.algo ? 'Does NOT match' : 'Hmm') + '</b><span class="muted" style="display:block">' + esc(CK.verdict.message) + '</span></div>' : '<span class="muted">Paste a fingerprint above and Toolbelt compares it. Download sites usually show the SHA-256.</span>') + '</div>'
        : job && job.state === 'failed' ? '<span class="err">' + esc(job.message) + '</span>' : '<div class="card stack"><span class="muted">' + (job ? 'Reading the file… ' + Math.round(job.progress) + '%' : 'Working out the fingerprints…') + '</span></div>') : '');
    } else if (CK.tab === 'sign') {
      var s = CK.sign;
      body = ckFileBox(f, 'ckPick', 'Drop a program or installer (EXE, MSI, DLL)') + (f ? (s ? '<div class="card stack"><div class="verdict"><span class="mark ' + (s.level === 'ok' ? 'okc' : s.level === 'bad' ? 'badc' : s.level === 'warn' ? 'warnc' : 'muted') + '">' + (s.level === 'ok' ? '✓' : s.level === 'info' ? '·' : '!') + '</span><div><b>' + esc(s.title) + '</b><span class="muted" style="display:block">' + esc(s.why) + '</span></div></div>' +
        (s.signer ? '<div class="kv"><span>Signed by</span><span>' + esc(s.signer) + '</span><span>Certificate from</span><span>' + esc(s.issuer) + '</span><span>Valid</span><span>' + esc(s.from) + ' → ' + esc(s.until) + '</span>' + (s.timestamp ? '<span>Time-stamped by</span><span>' + esc(s.timestamp) + '</span>' : '') + '</div>' : '') + '</div>' : '<div class="card"><span class="muted">Asking Windows…</span></div>') : '');
    } else if (CK.tab === 'compare') {
      var cj = CK.cmpJob !== null ? st.jobs.filter(function (j) { return j.id === CK.cmpJob; })[0] : null, c = CK.cmp;
      body = '<div class="cols">' + ckFileBox(f, 'ckPick', 'The first file') + ckFileBox(CK.other, 'ckPickOther', 'The second file') + '</div>' +
        (f && CK.other ? (c ? '<div class="card verdict"><span class="mark ' + (c.same ? 'okc' : 'warnc') + '">' + (c.same ? '=' : '≠') + '</span><div><b>' + (c.same ? 'Identical' : 'Different') + '</b><span class="muted" style="display:block">' + esc(c.why) + '</span></div></div>' :
          cj && (cj.state === 'running' || cj.state === 'waiting') ? '<div class="card"><span class="muted">Comparing… ' + Math.round(cj.progress) + '%</span></div>' : '<div class="row"><button type="button" class="btn" id="ckCompare">Compare</button></div>') : '<span class="muted">Pick both files: Toolbelt checks size first, then the SHA-256 of each.</span>');
    } else if (CK.tab === 'folder') {
      var fo = CK.folder, fj = CK.fjob !== null ? st.jobs.filter(function (j) { return j.id === CK.fjob; })[0] : null, fr = CK.fres;
      body = '<div class="card stack">' + (fo ? '<div class="filebox"><span class="badge">DIR</span><div class="stack grow" style="gap:2px;min-width:0"><b class="ell">' + esc(fo.folder) + '</b><span class="muted">' + fo.files + ' files' + (fo.list ? ' · has a fingerprint list' : '') + '</span></div><button type="button" class="btn ghost sm" id="ckFolder">Change</button></div>' : '<div class="row sb"><span class="muted">A folder you want to be able to check later (a backup, a modpack, a world).</span><button type="button" class="btn" id="ckFolder">Pick a folder</button></div>') +
        (fo ? '<div class="row"><button type="button" class="btn ghost sm" id="ckMake"' + (fj && fj.state === 'running' ? ' disabled' : '') + '>Make a fingerprint list</button><button type="button" class="btn sm" id="ckVerify"' + (!fo.list || (fj && fj.state === 'running') ? ' disabled' : '') + '>Check against the list</button></div>' : '') +
        (fj && (fj.state === 'running' || fj.state === 'waiting') ? '<div class="bar"><i style="width:' + Math.round(fj.progress) + '%"></i></div><span class="muted">' + esc(fj.message || 'Working…') + '</span>' : fj && fj.state === 'failed' ? '<span class="err">' + esc(fj.message) + '</span>' : '') +
        (fr ? (fr.path ? '<div class="verdict"><span class="mark okc">✓</span><div><b>List saved: ' + esc(fr.path.split('\\').pop()) + '</b><span class="muted" style="display:block">' + fr.files + ' files, ' + fmtBytes(fr.bytes) + '. Later, "Check against the list" shows what changed, went missing or got corrupted.</span></div></div>' :
          '<div class="verdict"><span class="mark ' + (fr.ok ? 'okc' : 'badc') + '">' + (fr.ok ? '✓' : '!') + '</span><div><b>' + (fr.ok ? 'Everything matches the list' : (fr.changed.length + fr.missing.length) + ' problem' + (fr.changed.length + fr.missing.length === 1 ? '' : 's')) + '</b><span class="muted" style="display:block">' + fr.checked + ' files checked' + (fr.new.length ? ' · ' + fr.new.length + ' new since the list' : '') + '</span></div></div>' +
          (fr.changed.length ? '<span class="lbl">Changed</span><div class="list">' + fr.changed.slice(0, 50).map(function (n) { return '<div class="item"><span class="badc">!</span><span class="ell">' + esc(n) + '</span><span></span></div>'; }).join('') + '</div>' : '') +
          (fr.missing.length ? '<span class="lbl">Missing</span><div class="list">' + fr.missing.slice(0, 50).map(function (n) { return '<div class="item"><span class="badc">✕</span><span class="ell">' + esc(n) + '</span><span></span></div>'; }).join('') + '</div>' : '') +
          (fr.new.length ? '<span class="lbl">New</span><div class="list">' + fr.new.slice(0, 50).map(function (n) { return '<div class="item"><span class="muted">+</span><span class="ell">' + esc(n) + '</span><span></span></div>'; }).join('') + '</div>' : '')) : '') +
        '<span class="muted">The list is a plain text file next to the folder (name.sha256): one SHA-256 per file. Other tools (sha256sum) read it too.</span></div>';
    } else {
      var w = CK.sniff;
      body = ckFileBox(f, 'ckPick', 'Drop any file: Toolbelt reads its first bytes') + (f ? (w ? '<div class="card verdict"><span class="mark ' + (w.verdict === 'ok' ? 'okc' : w.verdict === 'danger' ? 'badc' : 'warnc') + '">' + (w.verdict === 'ok' ? '✓' : '!') + '</span><div><b>' + esc(w.verdict === 'ok' ? 'Really a ' + w.real.replace(/^Windows program.*/, 'Windows program') : w.advice) + '</b><span class="muted" style="display:block">The name says ' + (w.ext ? esc(w.ext) : 'nothing') + '; the first bytes say ' + esc(w.real) + '.</span></div></div>' : '<div class="card"><span class="muted">Looking…</span></div>') : '') +
        '<span class="muted">Every kind of file starts with its own few bytes (PNG, ZIP, EXE…), whatever the name claims. A program called invoice.pdf.exe is the classic trick.</span>';
    }
    return '<div class="row sb"><h2 class="h">Check a file</h2><span class="muted">fingerprints · signatures · compare · folders · disguises</span></div>' +
      '<div class="tabs" role="tablist">' + CHK.map(function (t) { return '<button type="button" class="chip" role="tab" data-chk="' + t[0] + '" aria-pressed="' + (CK.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' +
      '<div class="stack" style="max-width:820px">' + body + '</div>';
  };
  function ckJobsTick() {                                   // called from pollJobs: pick up finished check jobs
    if (st.screen !== 'check') return;
    var redo = false;
    if (CK.hashJob !== null && !CK.hashes) { var j = st.jobs.filter(function (x) { return x.id === CK.hashJob; })[0]; if (j && j.state === 'done') { CK.hashes = { md5: j.extra.md5, sha1: j.extra.sha1, sha256: j.extra.sha256, sha512: j.extra.sha512 }; redo = true; } else if (j && (j.state === 'running' || j.state === 'failed')) redo = true; }
    if (CK.cmpJob !== null && !CK.cmp) { var c = st.jobs.filter(function (x) { return x.id === CK.cmpJob; })[0]; if (c && c.state === 'done') { CK.cmp = { same: c.extra.same, why: c.extra.why }; redo = true; } else if (c && c.state === 'failed') { toast(c.message); CK.cmpJob = null; redo = true; } else if (c) redo = true; }
    if (CK.fjob !== null && !CK.fres) { var fj = st.jobs.filter(function (x) { return x.id === CK.fjob; })[0]; if (fj && fj.state === 'done') { CK.fres = fj.extra; if (fj.extra.path && CK.folder) CK.folder.list = true; redo = true; } else if (fj) redo = true; }
    if (redo) { var keep = $('#ckPaste'); var pos = keep ? keep.selectionStart : null; go('check', true); if (pos !== null) { var again = $('#ckPaste'); if (again) { again.focus(); try { again.setSelectionRange(pos, pos); } catch (e) {} } } }
  }
  WIRE.check = function (m) {
    $$('[data-chk]', m).forEach(function (b) { b.onclick = function () { CK.tab = b.getAttribute('data-chk'); go('check', true); }; });
    var pick = $('#ckPick', m); if (pick) pick.onclick = function () { ckTake(api('check_pick', 'file'), 'file'); };
    var po = $('#ckPickOther', m); if (po) po.onclick = function () { ckTake(api('check_pick', 'file'), 'other'); };
    if (CK.file && CK.tab === 'hash' && !CK.hashes && CK.hashJob === null) api('check_hash', CK.file.token).then(function (r) { if (!r.ok) { toast(r.message); return; } CK.hashJob = r.id; pollJobs(); }).catch(fail);
    var paste = $('#ckPaste', m);
    if (paste) paste.oninput = function () { CK.pasted = paste.value; api('check_match', CK.hashes, paste.value).then(function (v) { CK.verdict = paste.value.trim() ? v : null; var pos = paste.selectionStart; go('check', true); var again = $('#ckPaste'); if (again) { again.focus(); try { again.setSelectionRange(pos, pos); } catch (e) {} } }).catch(fail); };
    $$('[data-ckcopy]', m).forEach(function (b) { b.onclick = function () { api('copy_text', b.getAttribute('data-ckcopy')).then(function (r) { toast(r && r.message ? r.message : 'Copied'); }).catch(fail); }; });
    if (CK.file && CK.tab === 'sign' && !CK.sign) api('check_sign', CK.file.token).then(function (s) { CK.sign = s.ok ? s : { level: 'warn', title: "Couldn't check", why: s.message || '' }; go('check', true); }).catch(fail);
    if (CK.file && CK.tab === 'what' && !CK.sniff) api('check_sniff', CK.file.token).then(function (w) { if (!w.ok) { toast(w.message); return; } CK.sniff = w; go('check', true); }).catch(fail);
    var cmp = $('#ckCompare', m); if (cmp) cmp.onclick = function () { api('check_compare', CK.file.token, CK.other.token).then(function (r) { if (!r.ok) { toast(r.message); return; } CK.cmp = null; CK.cmpJob = r.id; pollJobs(); go('check', true); }).catch(fail); };
    var fo = $('#ckFolder', m); if (fo) fo.onclick = function () { api('check_pick', 'folder').then(function (r) { if (!r.ok) { if (r.message) toast(r.message); return; } CK.folder = r; CK.fres = null; CK.fjob = null; go('check', true); }).catch(fail); };
    var mk = $('#ckMake', m); if (mk) mk.onclick = function () { api('check_folder', CK.folder.folder, 'make').then(function (r) { if (!r.ok) { toast(r.message); return; } CK.fres = null; CK.fjob = r.id; pollJobs(); go('check', true); }).catch(fail); };
    var vf = $('#ckVerify', m); if (vf) vf.onclick = function () { api('check_folder', CK.folder.folder, 'verify').then(function (r) { if (!r.ok) { toast(r.message); return; } CK.fres = null; CK.fjob = r.id; pollJobs(); go('check', true); }).catch(fail); };
  }

  // ---------- step 10: the calculator (his school features: breuken, wortels, machten, tafels, tabel, vergelijkingen, grafiek) ----------
  var CTAB = [['calc', 'Rekenen'], ['frac', 'Breuken'], ['roots', 'Wortels & machten'], ['times', 'Tafels'], ['table', 'Tabel'], ['solve', 'Vergelijkingen'], ['graph', 'Grafiek'], ['prog', 'Programmer'], ['units', 'Eenheden'], ['date', 'Datum']];
  var CA = { tab: 'calc', expr: '', out: null, err: '', hist: [], mode: 'exact', deg: true, ans: null, shift: false, mem: null,
    pexpr: '', pbase: 16, pbits: 32, ukind: 'length', uval: '1', ufrom: 'km', d1: '2026-10-14', d2: '2027-01-01', dadd: '30', dunit: 'days',
    frac: '1/3 + 1/6', fr: null, frErr: '', fed: {},
    rootN: '2', rootX: '16', powX: '2', powY: '10', pctA: '20', pctB: '150',
    tafel: '7', upto: '12', quiz: null, quizIn: '', score: [0, 0], quizMsg: '',
    tf: 'y = 2x^2 + 3', tfrom: '-5', tstep: '1', tcount: '11',
    eq: '2x + 3 = 11', sol: null, solErr: '',
    gf: ['y = x^2', 'y = 2x + 1', ''], view: { x0: -10, x1: 10, y0: -10, y1: 10 }, hover: '' };
  window.calcDevice.load(CA);
  function calcSave() { window.calcDevice.save(CA); }
  function C() { return window.calc; }
  function fmtv(v) { var s = C().format(v, CA.mode === 'decimal' ? 'decimal' : 'exact'); var d = CA.mode === 'decimal' ? '' : C().decimalOf(v); return { main: s, dec: d && d !== s ? d : '' }; }
  function calcRun() {
    var text = CA.expr.trim();
    if (!text) { CA.out = null; CA.err = ''; return; }
    try {
      var env = {}; if (CA.ans !== null) env.ans = CA.ans;
      var v = C().evaluate(C().parse(text.replace(/\bans\b/gi, '(ans)')), env, { degrees: CA.deg });
      CA.out = v; CA.err = ''; CA.ans = v;
      var line = { e: text, r: C().format(v) };
      if (!CA.hist.length || CA.hist[0].e !== line.e) CA.hist.unshift(line);
      CA.hist = CA.hist.slice(0, 30); calcSave();
    } catch (e) { CA.out = null; CA.err = e.message; }
  }
  // the Breuken tab's keys: [key, label, class, title, small label above]
  var FKEYS = [['frac', '▢/▢', 'fn', 'Breuk (/)', 'breuk'], ['mixed', '▢<small>▢/▢</small>', 'fn', 'Gemengd getal (spatie)', 'gemengd'], ['sqrt', '√▢', 'fn', 'Wortel (w)', 'wortel'], ['sq', 'x²', 'fn', 'Kwadraat'], ['pow', 'x<sup>▢</sup>', 'fn', 'Macht (^)', 'macht'], ['del', 'DEL', 'warn', 'Wis één (Backspace)'],
    ['(', '(', 'fn'], [')', ')', 'fn'], ['left', '◀', 'fn', 'Naar links'], ['up', '▲', 'fn', 'Naar boven de streep'], ['down', '▼', 'fn', 'Naar onder de streep'], ['right', '▶', 'fn', 'Naar rechts / uit de breuk'],
    ['7', '7', 'digit num'], ['8', '8', 'digit num'], ['9', '9', 'digit num'], ['×', '×', 'op num'], ['÷', '÷', 'op num'], ['ac', 'AC', 'warn num', 'Alles wissen (Esc)'],
    ['4', '4', 'digit num'], ['5', '5', 'digit num'], ['6', '6', 'digit num'], ['+', '+', 'op num'], ['-', '−', 'op num'], ['eq', '=', 'eq num feq', 'Uitrekenen (Enter)'],
    ['1', '1', 'digit num'], ['2', '2', 'digit num'], ['3', '3', 'digit num'], ['0', '0', 'digit num'], ['.', ',', 'digit num']];
  function fracHtml(s) { return esc(s).replace(/(\d+)\/(\d+)/g, '<span class="fr"><span class="nu">$1</span><span class="de">$2</span></span>'); }
  function fracOutHtml() {
    var fr = CA.fr;
    if (CA.frErr) return '<span class="err">' + esc(CA.frErr) + '</span>';
    if (!fr) return '';
    return '<span class="big">= ' + C().htmlValue(fr.value, 'exact') + '</span>' + (fr.mixed !== fr.exact ? '<span class="big">= ' + C().htmlValue(fr.value, 'mixed') + '</span>' : '') +
      (fr.decimal !== fr.exact ? '<span class="dec">≈ ' + esc(fr.decimal) + '</span>' : '');
  }
  function fracStepsHtml() {
    var fr = CA.fr;
    if (!fr) return '<span class="lbl">Stappen</span><span class="muted">Type een som met breuken: de stappen komen hier.</span>';
    return '<span class="lbl">Stappen</span>' + (fr.steps.length ? '<ol class="steps fsteps">' + fr.steps.map(function (s) { return '<li>' + fracHtml(s) + '</li>'; }).join('') + '</ol>' : '<span class="muted">Geen aparte stappen voor deze; het antwoord is exact.</span>');
  }
  function pctRows() {
    var a = Number(String(CA.pctA).replace(',', '.')), b = Number(String(CA.pctB).replace(',', '.'));
    if (!isFinite(a) || !isFinite(b)) return '<span class="muted">Give two numbers.</span>';
    function n(x) { return String(Number(x.toPrecision(10))); }
    return '<div class="kv"><span>' + a + '% van ' + b + '</span><b>' + n(b * a / 100) + '</b>' +
      '<span>' + b + ' + ' + a + '%</span><b>' + n(b * (1 + a / 100)) + '</b><span>' + b + ' − ' + a + '%</span><b>' + n(b * (1 - a / 100)) + '</b>' +
      '<span>' + a + ' is hoeveel % van ' + b + '</span><b>' + (b ? n(a / b * 100) + '%' : '—') + '</b>' +
      '<span>van ' + a + ' naar ' + b + '</span><b>' + (a ? (b >= a ? '+' : '') + n((b - a) / a * 100) + '%' : '—') + '</b></div>';
  }
  VIEWS.calc = function () {
    var body = '';
    if (CA.tab === 'calc') {
      // The device (device.js): a ClassWiz / MultiView-style scientific calculator with a natural display, shared with the mini window
      body = '<div class="cols">' + window.calcDevice.render(CA) +
        '<div class="card stack"><div class="row sb"><b>Geschiedenis</b><div class="row"><button type="button" class="btn ghost sm" id="cMini">Floating mini ↗</button><button type="button" class="btn ghost sm" id="cClear">Wis</button></div></div><div class="list" id="cHist">' + (CA.hist.length ? CA.hist.map(function (h, i) { return '<button type="button" class="item hist" data-hist="' + i + '"><span class="cnat sm">' + C().html(h.e) + '</span><b class="ell">= ' + esc(h.r) + '</b></button>'; }).join('') : '<span class="muted">Nothing yet.</span>') + '</div>' +
        '<span class="muted">Typing works too, straight into the shapes like the Casio: <b>/</b> makes a fraction (the number before it goes on top), <b>▶</b> or <b>▼</b> moves on, <b>^</b> raises, <b>space</b> after a number = gemengd. Also sin(30), root(3, 27), 20%, 5!, π, Ans. Enter = uitrekenen, Esc = AC, Ctrl+C = kopieer het antwoord.</span></div></div>';
    } else if (CA.tab === 'prog') {
      var pr = null, perr = '';
      if (CA.pexpr.trim()) { try { pr = C().prog(CA.pexpr, CA.pbase, CA.pbits); } catch (e) { perr = e.message; } }
      var bases = [[16, 'HEX'], [10, 'DEC'], [8, 'OCT'], [2, 'BIN']];
      body = '<div class="card stack"><span class="lbl">Programmer</span><div class="row sb"><div class="row">' + bases.map(function (b) { return '<button type="button" class="chip" data-pbase="' + b[0] + '" aria-pressed="' + (CA.pbase === b[0]) + '">' + b[1] + '</button>'; }).join('') + '</div>' +
        '<div class="row">' + [8, 16, 32, 64].map(function (b) { return '<button type="button" class="chip" data-pbits="' + b + '" aria-pressed="' + (CA.pbits === b) + '">' + b + ' bit</button>'; }).join('') + '</div></div>' +
        '<input class="field cexpr" id="cPexpr" value="' + esc(CA.pexpr) + '" placeholder="' + esc({ 16: 'FF AND 0F, 1F << 4, NOT 0', 10: '255 AND 15, 1 << 4, 0xFF XOR 0b1010', 8: '377 OR 7', 2: '1010 XOR 0110' }[CA.pbase]) + '" aria-label="Sum" autocomplete="off" spellcheck="false">' +
        '<div class="row">' + ['AND', 'OR', 'XOR', 'NOT', '<<', '>>', 'MOD', '(', ')'].map(function (o) { return '<button type="button" class="chip" data-pop="' + esc(o) + '">' + esc(o) + '</button>'; }).join('') + (CA.pbase === 16 ? ['A', 'B', 'C', 'D', 'E', 'F'].map(function (h) { return '<button type="button" class="chip" data-pop="' + h + '">' + h + '</button>'; }).join('') : '') + '</div>' +
        (perr ? '<span class="err">' + esc(perr) + '</span>' : pr ? '<div class="bases">' + [['HEX', pr.hexGrouped, 16], ['DEC', pr.signed !== pr.unsigned ? pr.unsigned + ' <span class="muted">(signed ' + pr.signed + ')</span>' : pr.unsigned, 10], ['OCT', pr.oct, 8], ['BIN', pr.binGrouped, 2]].map(function (r) { return '<div class="brow' + (CA.pbase === r[2] ? ' on' : '') + '"><b>' + r[0] + '</b><span>' + r[1] + '</span><button type="button" class="btn ghost sm" data-pcopy="' + esc(String(r[1]).replace(/<[^>]+>/g, '').replace(/ /g, '')) + '">Copy</button></div>'; }).join('') + '</div>' +
        (pr.overflow ? '<span class="warnc">That number does not fit in ' + pr.bits + ' bits: only the lowest bits are shown.</span>' : '') +
        '<span class="lbl">Bits (click to flip)</span><div class="bits" style="grid-template-columns:repeat(' + Math.min(32, pr.bits) + ', ' + (pr.bits <= 16 ? 32 : 26) + 'px)">' + pr.bitArray.map(function (b, i) { var n = pr.bits - 1 - i; return '<button type="button" class="' + (b ? 'one' : '') + '" data-bit="' + n + '" title="bit ' + n + '">' + (b ? 1 : 0) + '</button>'; }).join('') + '</div>' : '<span class="muted">Type a number or a sum in the chosen base. Prefixes work anywhere: 0xFF, 0b1010, 0o17. AND OR XOR NOT, << >>, MOD, + − × ÷. The answer shows in all four bases at once, with the bits you can flip.</span>') + '</div>';
    } else if (CA.tab === 'units') {
      var kinds = Object.keys(C().UNITS), K = C().UNITS[CA.ukind] || C().UNITS.length;
      if (!K.units[CA.ufrom]) CA.ufrom = Object.keys(K.units)[0];
      var rows = null, uerr = '';
      try { rows = C().convert(CA.ukind, CA.uval, CA.ufrom); } catch (e) { uerr = e.message; }
      body = '<div class="card stack"><span class="lbl">Eenheden</span><div class="row">' + kinds.map(function (k) { return '<button type="button" class="chip" data-ukind="' + k + '" aria-pressed="' + (CA.ukind === k) + '">' + esc(C().UNITS[k].name) + '</button>'; }).join('') + '</div>' +
        '<div class="row nw"><input class="field" id="cUval" value="' + esc(CA.uval) + '" style="width:160px" aria-label="Value" inputmode="decimal"><select class="field" id="cUfrom" style="width:auto" aria-label="From unit">' + Object.keys(K.units).map(function (u) { return '<option value="' + esc(u) + '"' + (u === CA.ufrom ? ' selected' : '') + '>' + esc(u) + '</option>'; }).join('') + '</select></div>' +
        (uerr ? '<span class="err">' + esc(uerr) + '</span>' : '<div class="stack" style="gap:0">' + rows.map(function (r) { return '<div class="urow' + (r.unit === CA.ufrom ? ' on' : '') + '"><span class="muted">' + esc(r.unit) + '</span><b>' + esc(r.text) + '</b></div>'; }).join('') + '</div>') +
        '<span class="muted">Every unit of the kind at once. No currency: that would need the internet every time.</span></div>';
    } else if (CA.tab === 'date') {
      var dd = null, derr = '', da = null, aerr = '';
      try { dd = C().dateDiff(CA.d1, CA.d2); } catch (e) { derr = e.message; }
      try { da = C().dateAdd(CA.d1, CA.dadd, CA.dunit); } catch (e) { aerr = e.message; }
      body = '<div class="cols"><div class="card stack"><span class="lbl">Dagen tussen twee datums</span>' +
        '<div class="row nw"><input class="field" id="cD1" value="' + esc(CA.d1) + '" aria-label="From date" placeholder="2026-10-14"><span class="muted">→</span><input class="field" id="cD2" value="' + esc(CA.d2) + '" aria-label="To date" placeholder="2027-01-01"><button type="button" class="btn ghost sm" id="cToday">Vandaag</button></div>' +
        (derr ? '<span class="err">' + esc(derr) + '</span>' : '<div class="cres"><b>' + Math.abs(dd.days) + ' dagen</b>' + (dd.days < 0 ? '<span class="muted">(terug in de tijd)</span>' : '') + '</div><div class="kv"><span>Weken</span><span>' + Math.abs(dd.weeks) + ' weken en ' + dd.restDays + ' dagen</span><span>Jaren / maanden / dagen</span><span>' + dd.years + ' jaar, ' + dd.months + ' maanden, ' + dd.daysLeft + ' dagen</span><span>Van</span><span>' + esc(dd.weekdayFrom) + ' ' + dd.from + '</span><span>Tot</span><span>' + esc(dd.weekdayTo) + ' ' + dd.to + '</span></div>') + '</div>' +
        '<div class="card stack"><span class="lbl">Datum plus of min</span><div class="row nw"><input class="field" id="cDadd" value="' + esc(CA.dadd) + '" style="width:90px" aria-label="Amount" inputmode="numeric">' +
        '<div class="row">' + [['days', 'dagen'], ['weeks', 'weken'], ['months', 'maanden'], ['years', 'jaren']].map(function (u) { return '<button type="button" class="chip" data-dunit="' + u[0] + '" aria-pressed="' + (CA.dunit === u[0]) + '">' + u[1] + '</button>'; }).join('') + '</div></div>' +
        '<span class="muted">vanaf de eerste datum hierboven (' + esc(CA.d1) + ')</span>' + (aerr ? '<span class="err">' + esc(aerr) + '</span>' : '<div class="cres"><b>' + esc(da.date) + '</b><span class="muted">' + esc(da.weekday) + '</span></div>') +
        '<span class="muted">Negatief telt terug. Datums als 2026-10-14 of 14-10-2026.</span></div></div>';
    } else if (CA.tab === 'frac') {
      // typed straight into stacked boxes like his fx-82 (mathedit.js, 25 Oct); the answer and the steps stacked too
      body = '<div class="cols"><div class="casio fcasio"><div class="cdisp"><div class="cind"><span class="on">Breuken</span><span class="on">d/c</span></div>' +
        '<div class="cnat medit" id="cFracEd" tabindex="0" role="textbox" aria-label="Breuken som"></div><div class="cout" id="cFracOut">' + fracOutHtml() + '</div></div>' +
        '<div class="ckeys fkeys">' + FKEYS.map(function (k) { return (k[0] === '7' ? '<span class="ckdiv"></span>' : '') + '<button type="button" class="ckey ' + k[2] + '" data-fk="' + esc(k[0]) + '" title="' + esc(k[3] || '') + '"><small class="sh">' + (k[4] || '&nbsp;') + '</small><span>' + k[1] + '</span></button>'; }).join('') + '</div></div>' +
        '<div class="stack"><div class="card stack"><span class="lbl">Voorbeelden</span><div class="row">' + ['1/3 + 1/6', '3/4 − 1/8', '2/3 × 3/5', '2/3 ÷ 4/5', '1 1/2 + 2/3', '1851/250 × √36'].map(function (q) { return '<button type="button" class="chip" data-fq="' + esc(q) + '">' + esc(q) + '</button>'; }).join('') + '</div>' +
        '<span class="muted">Typen kan ook: <b>/</b> maakt een breuk (het getal ervoor gaat boven de streep), <b>▼ ▲</b> of <b>▶</b> wisselen tussen boven en onder, <b>▶</b> aan het eind gaat uit de breuk. <b>spatie</b> = gemengd getal, <b>w</b> = wortel, <b>^</b> = macht, <b>Enter</b> = uitrekenen.</span></div>' +
        '<div class="card stack" id="cFracSteps">' + fracStepsHtml() + '</div></div></div>';
    } else if (CA.tab === 'roots') {
      function tryc(expr) { try { var v = fmtv(C().calc(expr, {}, { degrees: CA.deg })); return '<b>' + esc(v.main) + '</b>' + (v.dec ? '<span class="muted"> ≈ ' + esc(v.dec) + '</span>' : ''); } catch (e) { return '<span class="err">' + esc(e.message) + '</span>'; } }
      body = '<div class="cols"><div class="stack"><div class="card stack"><span class="lbl">Wortel</span><div class="row nw"><input class="field" id="cRootN" value="' + esc(CA.rootN) + '" style="width:80px" aria-label="Which root"><span class="muted">√</span><input class="field" id="cRootX" value="' + esc(CA.rootX) + '" aria-label="Number"></div>' +
        '<div class="cres">' + tryc('root(' + CA.rootN + ', ' + CA.rootX + ')') + '</div><span class="muted">2 = vierkantswortel, 3 = derdemachtswortel, enz. Komt het niet mooi uit, dan zie je een decimaal.</span></div>' +
        '<div class="card stack"><span class="lbl">Macht</span><div class="row nw"><input class="field" id="cPowX" value="' + esc(CA.powX) + '" aria-label="Base"><span class="muted">tot de macht</span><input class="field" id="cPowY" value="' + esc(CA.powY) + '" aria-label="Exponent"></div>' +
        '<div class="cres">' + tryc('(' + CA.powX + ')^(' + CA.powY + ')') + '</div><span class="muted">Ook breuken en negatieve machten: 2^-3 = 1/8, 8^(1/3) = 2.</span></div></div>' +
        '<div class="card stack"><span class="lbl">Procenten</span><div class="row nw"><input class="field" id="cPctA" value="' + esc(CA.pctA) + '" aria-label="Percent"><span class="muted">%</span><input class="field" id="cPctB" value="' + esc(CA.pctB) + '" aria-label="Number"></div><div id="cPct">' + pctRows() + '</div></div></div>';
    } else if (CA.tab === 'times') {
      var n = parseInt(CA.tafel, 10) || 0, upto = Math.min(100, parseInt(CA.upto, 10) || 12);
      var q = CA.quiz;
      body = '<div class="cols"><div class="card stack"><span class="lbl">Tafel van</span><div class="row nw"><input class="field" id="cTafel" value="' + esc(CA.tafel) + '" style="width:90px" aria-label="Table of"><span class="muted">tot</span><input class="field" id="cUpto" value="' + esc(CA.upto) + '" style="width:90px" aria-label="Up to"></div>' +
        '<div class="row">' + [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(function (t) { return '<button type="button" class="chip" data-tafel="' + t + '" aria-pressed="' + (n === t) + '">' + t + '</button>'; }).join('') + '</div>' +
        '<table class="ctable"><tbody>' + C().times(n, upto).map(function (r) { return '<tr><td>' + r[0] + ' × ' + r[1] + '</td><td>= <b>' + r[2] + '</b></td></tr>'; }).join('') + '</tbody></table></div>' +
        '<div class="card stack"><div class="row sb"><b>Oefenen</b><span class="tag">' + CA.score[0] + ' goed van ' + CA.score[1] + '</span></div>' +
        (q ? '<div class="cres"><b>' + q[0] + ' × ' + q[1] + ' = ?</b></div><div class="row nw"><input class="field" id="cQuizIn" value="' + esc(CA.quizIn) + '" inputmode="numeric" aria-label="Your answer" autocomplete="off"><button type="button" class="btn" id="cQuizGo">Check</button></div>' : '<span class="muted">Random sommen uit de tafels 1 t/m 12 (of alleen de tafel hierboven).</span>') +
        (CA.quizMsg ? '<span class="' + (CA.quizMsg.indexOf('Goed') === 0 ? 'okc' : 'badc') + '">' + esc(CA.quizMsg) + '</span>' : '') +
        '<div class="row"><button type="button" class="btn ghost sm" id="cQuizAll">Nieuwe som (alle tafels)</button><button type="button" class="btn ghost sm" id="cQuizOne">Nieuwe som (tafel van ' + n + ')</button></div></div></div>';
    } else if (CA.tab === 'table') {
      var rows = null, terr = '';
      try { rows = C().table(CA.tf, Number(String(CA.tfrom).replace(',', '.')) || 0, Number(String(CA.tstep).replace(',', '.')) || 1, Math.min(200, Math.max(1, parseInt(CA.tcount, 10) || 11)), { degrees: CA.deg }); } catch (e) { terr = e.message; }
      body = '<div class="card stack"><span class="lbl">Tabel van een formule</span><input class="field cexpr" id="cTf" value="' + esc(CA.tf) + '" placeholder="y = 2x^2 + 3" aria-label="Formula">' +
        '<div class="row"><label class="muted" for="cTfrom">x van</label><input class="field" id="cTfrom" value="' + esc(CA.tfrom) + '" style="width:90px"><label class="muted" for="cTstep">stap</label><input class="field" id="cTstep" value="' + esc(CA.tstep) + '" style="width:90px"><label class="muted" for="cTcount">aantal</label><input class="field" id="cTcount" value="' + esc(CA.tcount) + '" style="width:90px"><button type="button" class="btn ghost sm" id="cTGraph">Teken deze</button></div>' +
        (terr ? '<span class="err">' + esc(terr) + '</span>' : '<table class="ctable"><thead><tr><th>x</th><th>y</th><th class="muted">decimaal</th></tr></thead><tbody>' + rows.map(function (r) { return '<tr><td>' + esc(r.x) + '</td><td><b>' + esc(r.y) + '</b>' + (r.err ? ' <span class="muted">(' + esc(r.err) + ')</span>' : '') + '</td><td class="muted">' + esc(r.yd) + '</td></tr>'; }).join('') + '</tbody></table>') + '</div>';
    } else if (CA.tab === 'solve') {
      var s = CA.sol;
      body = '<div class="card stack"><span class="lbl">Vergelijking oplossen</span><div class="row nw"><input class="field cexpr" id="cEq" value="' + esc(CA.eq) + '" placeholder="2x + 3 = 11   of   x^2 - 5x + 6 = 0" aria-label="Equation"><button type="button" class="btn" id="cEqGo">Los op</button></div>' +
        '<div class="row">' + ['2x + 3 = 11', 'x^2 - 5x + 6 = 0', '(x + 1)(x - 2) = 0', '3x - 7 = x + 5', 'x^2 = 2'].map(function (q) { return '<button type="button" class="chip" data-eq="' + esc(q) + '">' + esc(q) + '</button>'; }).join('') + '</div>' +
        (CA.solErr ? '<span class="err">' + esc(CA.solErr) + '</span>' : s ? '<div class="cres">' + (s.roots.length ? '<b>' + s.roots.map(function (r) { var v = fmtv(r); return 'x = ' + esc(v.main) + (v.dec ? ' ≈ ' + esc(v.dec) : ''); }).join('  of  ') + '</b>' : '<b>' + (s.kind === 'all' ? 'Elke x klopt' : 'Geen oplossing') + '</b>') + '<span class="tag">' + ({ linear: 'lineair', quadratic: 'kwadratisch · abc-formule', numeric: 'benaderd', none: 'geen', all: 'alles' }[s.kind] || s.kind) + '</span></div>' +
        '<span class="lbl">Stappen</span><ol class="steps">' + s.steps.map(function (st) { return '<li>' + esc(st) + '</li>'; }).join('') + '</ol>' : '') + '</div>';
    } else {
      body = '<div class="card stack"><span class="lbl">Grafiek</span>' + CA.gf.map(function (f, i) { return '<div class="row nw"><span class="gdot" style="background:' + ['#FF5C8A', '#5CC8FF', '#5CE08A'][i] + '"></span><input class="field cexpr" data-gf="' + i + '" value="' + esc(f) + '" placeholder="' + (i ? 'nog een formule…' : 'y = x^2') + '" aria-label="Formula ' + (i + 1) + '"></div>'; }).join('') +
        '<div class="cgraph"><canvas id="cCanvas" width="760" height="460"></canvas><span class="muted" id="cHover">' + esc(CA.hover || 'Beweeg over de grafiek om x en y af te lezen · scroll = zoom · sleep = verschuiven') + '</span></div>' +
        '<div class="row"><button type="button" class="btn ghost sm" id="cGReset">Terug naar −10…10</button><button type="button" class="btn ghost sm" id="cGZoomIn">Zoom in</button><button type="button" class="btn ghost sm" id="cGZoomOut">Zoom uit</button><span class="muted" id="cGErr"></span></div></div>';
    }
    return '<div class="row sb"><h2 class="h">Calculator</h2><span class="muted">breuken · wortels · machten · tafels · tabel · vergelijkingen · grafiek</span></div>' +
      '<div class="tabs" role="tablist">' + CTAB.map(function (t) { return '<button type="button" class="chip" role="tab" data-ctab2="' + t[0] + '" aria-pressed="' + (CA.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' + body;
  };
  function drawGraph(m) {
    var cv = $('#cCanvas', m); if (!cv) return;
    var ctx = cv.getContext('2d'), W = cv.width, H = cv.height, v = CA.view;
    var cs = getComputedStyle($('#root'));
    var ink = cs.getPropertyValue('--ink').trim() || '#fff', line = cs.getPropertyValue('--line').trim() || '#555', bg = cs.getPropertyValue('--field').trim() || '#000';
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
    function sx(x) { return (x - v.x0) / (v.x1 - v.x0) * W; }
    function sy(y) { return H - (y - v.y0) / (v.y1 - v.y0) * H; }
    function nice(span) { var raw = span / 10, p = Math.pow(10, Math.floor(Math.log10(raw))), r = raw / p; return (r < 1.5 ? 1 : r < 3.5 ? 2 : r < 7.5 ? 5 : 10) * p; }
    var gx = nice(v.x1 - v.x0), gy = nice(v.y1 - v.y0);
    ctx.lineWidth = 1; ctx.strokeStyle = line; ctx.fillStyle = ink; ctx.font = '11px ' + (cs.getPropertyValue('--mono') || 'monospace'); ctx.globalAlpha = .6;
    for (var x = Math.ceil(v.x0 / gx) * gx; x <= v.x1; x += gx) { ctx.beginPath(); ctx.moveTo(sx(x), 0); ctx.lineTo(sx(x), H); ctx.stroke(); if (Math.abs(x) > 1e-9) ctx.fillText(String(Number(x.toPrecision(6))), sx(x) + 3, sy(0) + 12 < H ? Math.min(H - 4, Math.max(12, sy(0) + 12)) : H - 4); }
    for (var y = Math.ceil(v.y0 / gy) * gy; y <= v.y1; y += gy) { ctx.beginPath(); ctx.moveTo(0, sy(y)); ctx.lineTo(W, sy(y)); ctx.stroke(); if (Math.abs(y) > 1e-9) ctx.fillText(String(Number(y.toPrecision(6))), Math.min(W - 30, Math.max(3, sx(0) + 4)), sy(y) - 3); }
    ctx.globalAlpha = 1; ctx.strokeStyle = ink; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0, sy(0)); ctx.lineTo(W, sy(0)); ctx.moveTo(sx(0), 0); ctx.lineTo(sx(0), H); ctx.stroke();
    var errs = [];
    CA.gf.forEach(function (f, i) {
      if (!f.trim()) return;
      var fn; try { fn = C().fn(f, { degrees: CA.deg }); } catch (e) { errs.push(e.message); return; }
      ctx.strokeStyle = ['#FF5C8A', '#5CC8FF', '#5CE08A'][i]; ctx.lineWidth = 2.2; ctx.beginPath();
      var pen = false, prevY = null;
      for (var px = 0; px <= W; px++) {
        var xv = v.x0 + px / W * (v.x1 - v.x0), yv = fn(xv);
        if (!isFinite(yv) || Math.abs(yv) > 1e6 || (prevY !== null && Math.abs(yv - prevY) > (v.y1 - v.y0) * 4)) { pen = false; prevY = isFinite(yv) ? yv : null; continue; }
        var py = sy(yv);
        if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
        prevY = yv;
      }
      ctx.stroke();
    });
    var ge = $('#cGErr', m); if (ge) ge.textContent = errs.join(' · ');
  }
  function newQuiz(only) {
    var a = only ? only : 1 + Math.floor(Math.random() * 12), b = 1 + Math.floor(Math.random() * 12);
    CA.quiz = Math.random() < .5 ? [a, b] : [b, a]; CA.quizIn = ''; CA.quizMsg = '';
  }
  WIRE.calc = function (m) {
    $$('[data-ctab2]', m).forEach(function (b) { b.onclick = function () { CA.tab = b.getAttribute('data-ctab2'); go('calc', true); }; });
    if ($('#cNat', m)) {
      window.calcDevice.wire(m, CA, {
        rerender: function () { go('calc', true); },
        copy: function (text) { api('copy_text', text).then(function (r) { toast(r && r.message ? r.message : 'Copied: ' + text); }).catch(fail); },
        table: function (expr) { CA.tf = expr ? 'y = ' + expr : CA.tf; CA.tab = 'table'; go('calc', true); }
      });
      $$('[data-hist]', m).forEach(function (b) { b.onclick = function () { CA.expr = CA.hist[+b.getAttribute('data-hist')].e; window.calcDevice.run(CA); calcSave(); go('calc', true); }; });
      var cl = $('#cClear', m); if (cl) cl.onclick = function () { CA.hist = []; calcSave(); go('calc', true); };
      var mini = $('#cMini', m); if (mini) mini.onclick = function () { api('calc_show').then(function (r) { if (r && !r.ok) toast(r.message); }).catch(fail); };
    }
    var px = $('#cPexpr', m);
    if (px) {
      px.focus();
      var pos0 = px.value.length; px.setSelectionRange(pos0, pos0);
      px.oninput = function () { CA.pexpr = px.value; };
      px.onkeydown = function (e) { if (e.key === 'Enter') go('calc', true); };
      $$('[data-pbase]', m).forEach(function (b) { b.onclick = function () {
        var nb = +b.getAttribute('data-pbase');
        try { if (CA.pexpr.trim()) { var r = C().prog(CA.pexpr, CA.pbase, CA.pbits); CA.pexpr = { 16: r.hex.replace(/^0+(?=.)/, ''), 10: r.unsigned, 8: r.oct, 2: r.bin.replace(/^0+(?=.)/, '') }[nb]; } } catch (e) {}
        CA.pbase = nb; go('calc', true);
      }; });
      $$('[data-pbits]', m).forEach(function (b) { b.onclick = function () { CA.pbits = +b.getAttribute('data-pbits'); go('calc', true); }; });
      $$('[data-pop]', m).forEach(function (b) { b.onclick = function () { var t = b.getAttribute('data-pop'); var s = px.selectionStart == null ? px.value.length : px.selectionStart; var ins = /^[A-F]$/.test(t) || t === '(' || t === ')' ? t : ' ' + t + ' '; px.value = px.value.slice(0, s) + ins + px.value.slice(px.selectionEnd == null ? s : px.selectionEnd); CA.pexpr = px.value; px.focus(); px.setSelectionRange(s + ins.length, s + ins.length); }; });
      $$('[data-pcopy]', m).forEach(function (b) { b.onclick = function () { api('copy_text', b.getAttribute('data-pcopy')).then(function (r) { toast(r && r.message ? r.message : 'Copied'); }).catch(fail); }; });
      $$('[data-bit]', m).forEach(function (b) { b.onclick = function () {
        try { var r = C().prog(CA.pexpr, CA.pbase, CA.pbits), n = +b.getAttribute('data-bit'); var arr = r.bitArray.slice(); arr[r.bits - 1 - n] = !arr[r.bits - 1 - n]; var f = C().progFromBits(arr, r.bits); CA.pexpr = { 16: f.hex.replace(/^0+(?=.)/, ''), 10: f.unsigned, 8: f.oct, 2: f.bin.replace(/^0+(?=.)/, '') }[CA.pbase]; go('calc', true); } catch (e) { toast(e.message); }
      }; });
    }
    var uv = $('#cUval', m);
    if (uv) {
      uv.oninput = function () { CA.uval = uv.value; var p = uv.selectionStart; go('calc', true); var again = $('#cUval'); if (again) { again.focus(); try { again.setSelectionRange(p, p); } catch (e) {} } };
      $('#cUfrom', m).onchange = function () { CA.ufrom = $('#cUfrom', m).value; go('calc', true); };
      $$('[data-ukind]', m).forEach(function (b) { b.onclick = function () { CA.ukind = b.getAttribute('data-ukind'); CA.ufrom = Object.keys(C().UNITS[CA.ukind].units)[0]; go('calc', true); }; });
    }
    var d1 = $('#cD1', m);
    if (d1) {
      [['cD1', 'd1'], ['cD2', 'd2'], ['cDadd', 'dadd']].forEach(function (pair) {
        var el = $('#' + pair[0], m); el.oninput = function () { CA[pair[1]] = el.value; var p = el.selectionStart; go('calc', true); var again = $('#' + pair[0]); if (again) { again.focus(); try { again.setSelectionRange(p, p); } catch (e) {} } };
      });
      $('#cToday', m).onclick = function () { var t = new Date(); CA.d1 = t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); go('calc', true); };
      $$('[data-dunit]', m).forEach(function (b) { b.onclick = function () { CA.dunit = b.getAttribute('data-dunit'); go('calc', true); }; });
    }
    var fe = $('#cFracEd', m);
    if (fe) {
      // the answer follows while typing (quietly: half-typed sums show nothing); = or Enter says what's wrong
      var firstTime = !CA.fed.root, ed = window.mathEdit.create(CA.fed);
      var runFrac = function (asked) {
        var t = ed.text();
        CA.fr = null; CA.frErr = '';
        if (t && ed.hasEmpty()) { if (asked) CA.frErr = 'Er is nog een leeg vakje.'; }
        else if (t) { try { CA.fr = C().fractionSteps(t); } catch (e) { if (asked) CA.frErr = e.message; } }
        $('#cFracOut').innerHTML = fracOutHtml(); $('#cFracSteps').innerHTML = fracStepsHtml();
      };
      ed.mount(fe, function () { runFrac(false); });
      if (firstTime) ed.set(CA.frac);
      runFrac(false);
      fe.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); runFrac(true); } });
      $$('[data-fk]', m).forEach(function (b) {
        b.addEventListener('mousedown', function (e) { e.preventDefault(); });   // the box keeps the focus (and its cursor)
        b.onclick = function () { var k = b.getAttribute('data-fk'); if (k === 'eq') runFrac(true); else ed.key(k); ed.focus(); };
      });
      $$('[data-fq]', m).forEach(function (b) { b.onclick = function () { ed.set(b.getAttribute('data-fq')); ed.focus(); }; });
    }
    [['cRootN', 'rootN'], ['cRootX', 'rootX'], ['cPowX', 'powX'], ['cPowY', 'powY'], ['cPctA', 'pctA'], ['cPctB', 'pctB'], ['cTafel', 'tafel'], ['cUpto', 'upto'], ['cTf', 'tf'], ['cTfrom', 'tfrom'], ['cTstep', 'tstep'], ['cTcount', 'tcount']].forEach(function (pair) {
      var el = $('#' + pair[0], m); if (!el) return;
      el.oninput = function () { CA[pair[1]] = el.value; var keep = el.id, pos = el.selectionStart; go('calc', true); var again = $('#' + keep); if (again) { again.focus(); try { again.setSelectionRange(pos, pos); } catch (e) {} } };
    });
    $$('[data-tafel]', m).forEach(function (b) { b.onclick = function () { CA.tafel = b.getAttribute('data-tafel'); go('calc', true); }; });
    var qa = $('#cQuizAll', m); if (qa) qa.onclick = function () { newQuiz(0); go('calc', true); var i = $('#cQuizIn'); if (i) i.focus(); };
    var qo = $('#cQuizOne', m); if (qo) qo.onclick = function () { newQuiz(parseInt(CA.tafel, 10) || 7); go('calc', true); var i = $('#cQuizIn'); if (i) i.focus(); };
    var qi = $('#cQuizIn', m), qg = $('#cQuizGo', m);
    if (qi && qg) {
      var check = function () {
        var want = CA.quiz[0] * CA.quiz[1], got = parseInt(qi.value, 10);
        CA.score[1]++;
        if (got === want) { CA.score[0]++; CA.quizMsg = 'Goed! ' + CA.quiz[0] + ' × ' + CA.quiz[1] + ' = ' + want; CA.quiz = null; }
        else { CA.quizMsg = 'Nee: ' + CA.quiz[0] + ' × ' + CA.quiz[1] + ' = ' + want; CA.quiz = null; }
        go('calc', true);
      };
      qg.onclick = check; qi.onkeydown = function (e) { if (e.key === 'Enter') check(); }; qi.oninput = function () { CA.quizIn = qi.value; };
    }
    var tg = $('#cTGraph', m); if (tg) tg.onclick = function () { CA.gf[0] = CA.tf; CA.tab = 'graph'; go('calc', true); };
    var eq = $('#cEq', m);
    if (eq) {
      var runEq = function () { CA.eq = eq.value; try { CA.sol = C().solve(CA.eq, { degrees: CA.deg }); CA.solErr = ''; } catch (e) { CA.sol = null; CA.solErr = e.message; } go('calc', true); };
      eq.onkeydown = function (e) { if (e.key === 'Enter') runEq(); };
      $('#cEqGo', m).onclick = runEq;
      $$('[data-eq]', m).forEach(function (b) { b.onclick = function () { eq.value = b.getAttribute('data-eq'); runEq(); }; });
      if (!CA.sol && !CA.solErr && CA.eq) { try { CA.sol = C().solve(CA.eq, { degrees: CA.deg }); } catch (e) { CA.solErr = e.message; } go('calc', true); }
    }
    var cv = $('#cCanvas', m);
    if (cv) {
      $$('[data-gf]', m).forEach(function (el) { el.oninput = function () { CA.gf[+el.getAttribute('data-gf')] = el.value; drawGraph(m); }; });
      drawGraph(m);
      var v = CA.view;
      function zoom(f, cx, cy) { var w = (v.x1 - v.x0) * f, h = (v.y1 - v.y0) * f; cx = cx === undefined ? (v.x0 + v.x1) / 2 : cx; cy = cy === undefined ? (v.y0 + v.y1) / 2 : cy; var fx = (cx - v.x0) / (v.x1 - v.x0), fy = (cy - v.y0) / (v.y1 - v.y0); v.x0 = cx - w * fx; v.x1 = v.x0 + w; v.y0 = cy - h * fy; v.y1 = v.y0 + h; drawGraph(m); }
      function toWorld(e) { var r = cv.getBoundingClientRect(); return [v.x0 + (e.clientX - r.left) / r.width * (v.x1 - v.x0), v.y1 - (e.clientY - r.top) / r.height * (v.y1 - v.y0)]; }
      cv.onwheel = function (e) { e.preventDefault(); var w = toWorld(e); zoom(e.deltaY > 0 ? 1.2 : 1 / 1.2, w[0], w[1]); };
      var drag = null;
      cv.onmousedown = function (e) { drag = [e.clientX, e.clientY, v.x0, v.x1, v.y0, v.y1]; };
      window.onmouseup = function () { drag = null; };
      cv.onmousemove = function (e) {
        var r = cv.getBoundingClientRect();
        if (drag) { var dx = (e.clientX - drag[0]) / r.width * (drag[3] - drag[2]), dy = (e.clientY - drag[1]) / r.height * (drag[5] - drag[4]); v.x0 = drag[2] - dx; v.x1 = drag[3] - dx; v.y0 = drag[4] + dy; v.y1 = drag[5] + dy; drawGraph(m); return; }
        var w = toWorld(e), parts = [];
        CA.gf.forEach(function (f, i) { if (!f.trim()) return; try { var y = C().fn(f, { degrees: CA.deg })(w[0]); if (isFinite(y)) parts.push((i + 1) + ': y = ' + Number(y.toPrecision(6))); } catch (err) {} });
        $('#cHover', m).textContent = 'x = ' + Number(w[0].toPrecision(6)) + (parts.length ? ' · ' + parts.join(' · ') : '');
      };
      $('#cGReset', m).onclick = function () { v.x0 = -10; v.x1 = 10; v.y0 = -10; v.y1 = 10; drawGraph(m); };
      $('#cGZoomIn', m).onclick = function () { zoom(1 / 1.5); };
      $('#cGZoomOut', m).onclick = function () { zoom(1.5); };
    }
  };
  window.toolbeltCalc = { state: function () { return CA; }, draw: function () { drawGraph($('#screen')); } };

  // ---------- step 7: the game library. Full-screen art (his pick, 15 Oct): the chosen game's banner fills the whole
  // screen, bright at the top and fading at the bottom; its cover, name and buttons float on glass; the covers sit in a
  // shelf along the bottom. Small covers and banners are upscaled to HD in the background (gameart.py). ----------
  var GM = { games: null, busy: false, sel: '', q: '', filter: 'all', sort: 'recent', banners: {}, bcache: {}, bidx: {}, bgOn: 'A', bgKey: '', bgHtml: { A: '', B: '' }, link: '', edit: false, shownKey: '' };
  function ago(iso) {
    if (!iso) return 'not played yet';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + ' min ago';
    if (s < 86400) return Math.round(s / 3600) + ' h ago';
    if (s < 86400 * 14) return Math.round(s / 86400) + ' days ago';
    return Math.round(s / 86400 / 7) + ' weeks ago';
  }
  function loadGames(refresh) {
    GM.busy = true;
    return api('games', !!refresh, true).then(function (g) {
      GM.games = g || []; GM.busy = false;
      if (!GM.sel || !GM.games.some(function (x) { return x.key === GM.sel; })) GM.sel = (shownGames()[0] || {}).key || '';
      if (st.screen === 'games') go('games', true);
    }).catch(function (e) { GM.busy = false; GM.games = []; fail(e); });
  }
  function shownGames() {
    var q = GM.q.toLowerCase();
    var list = (GM.games || []).filter(function (g) {
      if (GM.filter === 'hidden') return g.hidden;
      if (g.hidden) return false;
      if (GM.filter === 'fav') return g.favourite;
      if (GM.filter === 'installed') return g.installed;
      return true;
    }).filter(function (g) { return !q || g.name.toLowerCase().indexOf(q) !== -1 || (g.source || '').toLowerCase().indexOf(q) !== -1; });
    if (GM.sort === 'name') list.sort(function (a, b) { return a.name.localeCompare(b.name); });
    else if (GM.sort === 'time') list.sort(function (a, b) { return (b.playtime || 0) - (a.playtime || 0) || a.name.localeCompare(b.name); });
    return list;
  }
  function selGame() { return (GM.games || []).filter(function (g) { return g.key === GM.sel; })[0] || null; }
  // moving covers (GIF / video) follow Settings > Appearance > Moving game covers (his ask, 15 Oct):
  // still = never move; hover = the picked one and the one under the mouse move; always = they all move
  function coverMotion() { return (st.settings && st.settings.cover_motion) || 'hover'; }
  function tile(g) {
    var mode = coverMotion(), gif = g.cover_kind === 'gif' && g.cover_still, moving = mode === 'always' || (mode === 'hover' && g.key === GM.sel);
    var pic = gif && !moving ? g.cover_still : g.cover_data;
    var cover = pic ? ' style="background-image:url(' + pic + ')"' : '';
    return '<button type="button" class="gt lift' + (g.cover_data ? '' : ' nocover') + (g.cover_kind === 'gif' ? ' anim' : '') + '" data-game="' + esc(g.key) + '" aria-pressed="' + (g.key === GM.sel) + '"' + cover +
      (gif ? ' data-anim="' + esc(g.cover_data) + '" data-still="' + esc(g.cover_still) + '"' : '') + ' title="' + esc(g.name) + '">' +
      (g.cover_video ? '<video class="gtv" src="' + g.cover_video + '"' + (g.cover_data ? ' poster="' + g.cover_data + '"' : '') + ' muted loop playsinline preload="metadata"' + (moving ? ' autoplay' : '') + '></video>' : '') +
      (g.favourite ? '<span class="star">★</span>' : '') + (!g.cover_data && g.icon_data ? '<img class="gicon" src="' + g.icon_data + '" alt="">' : '') +
      '<b class="ell">' + esc(g.name) + '</b><small>' + esc(g.source) + (g.hidden ? ' · hidden' : '') + '</small></button>';
  }
  function coverMedia(g) {                                   // the big cover by the title: moves unless covers are set to Still
    var still = coverMotion() === 'still';
    if (g.cover_video) return '<video src="' + g.cover_video + '"' + (g.cover_data ? ' poster="' + g.cover_data + '"' : '') + ' muted loop playsinline' + (still ? '' : ' autoplay') + '></video>';
    if (g.cover_kind === 'gif' && still && g.cover_still) return '<img src="' + g.cover_still + '" alt="">';
    return g.cover_data ? '<img src="' + g.cover_data + '" alt="">' : '';
  }
  function shelfPlay(m) {                                    // which covers in the shelf move right now
    var mode = coverMotion();
    $$('[data-game]', m).forEach(function (tile) {
      var on = mode === 'always' || (mode === 'hover' && (tile.getAttribute('aria-pressed') === 'true' || tile.matches(':hover')));
      var v = $('video.gtv', tile);
      if (v) { if (on) v.play().catch(function () {}); else if (!v.paused) v.pause(); }
      var anim = tile.getAttribute('data-anim');
      if (anim) tile.style.backgroundImage = 'url(' + (on ? anim : tile.getAttribute('data-still')) + ')';
    });
  }
  function bannerBox(g) {                                    // the game's backgrounds in the order they fade through
    var list = g.banner_list || [], cur = (GM.bidx[g.key] || 0) % Math.max(1, list.length), dwell = (st.settings && st.settings.banner_dwell) || 20;
    var row = list.map(function (x, i) {
      return '<div class="bgthumb' + (i === cur ? ' on' : '') + '"><button type="button" class="bgpick" data-bgshow="' + i + '" title="Show this one now"' + (x.thumb ? ' style="background-image:url(' + x.thumb + ')"' : '') + '>' +
        '<span class="bgnum">' + (i + 1) + '</span>' + (x.kind !== 'pic' ? '<span class="tag acc">' + (x.kind === 'video' ? '▶ video' : 'GIF') + '</span>' : '') + (x.own ? '<span class="tag">' + esc(g.source) + '\'s</span>' : '') + (x.hd ? '<span class="tag hd">HD</span>' : '') + (x.width && x.width < 1280 && !x.own ? '<span class="tag warn" title="Only ' + x.width + ' px wide: it looks soft full screen. On SteamGridDB, paste its link again: Toolbelt now fetches the full size.">low-res</span>' : '') + '</button>' +
        '<div class="bgtools"><button type="button" class="ico" data-bgedit="left:' + i + '" aria-label="Earlier"' + (i ? '' : ' disabled') + '>◀</button><button type="button" class="ico" data-bgedit="right:' + i + '" aria-label="Later"' + (i < list.length - 1 ? '' : ' disabled') + '>▶</button>' +
        '<button type="button" class="ico" data-bgedit="remove:' + i + '" aria-label="Remove this background">✕</button></div></div>';
    }).join('');
    var ownMissing = g.own_banner && !list.some(function (x) { return x.own; });
    var small = list.filter(function (x) { return x.width && x.width < 1280 && !x.own; }).length;
    return '<div class="artbox"><div class="row sb"><span class="lbl">Backgrounds · ' + list.length + (list.length > 1 ? ' · each ' + dwell + ' s, then a slow fade to the next' : ' · add more and they take turns') + '</span>' +
      (g.custom_banner ? '<span class="tag">yours</span>' : '') + '</div>' +
      '<div class="bglist">' + (row || '<span class="muted">none yet</span>') + '</div>' +
      (small ? '<span class="muted">' + small + ' of these ' + (small === 1 ? 'is' : 'are') + ' small (marked low-res), so ' + (small === 1 ? 'it looks' : 'they look') + ' soft full screen. Links copied from SteamGridDB’s page are previews; paste one again and Toolbelt fetches the full size, then remove the old one with ✕.</span>' : '') +
      '<div class="row"><button type="button" class="btn ghost sm" data-art="pick:banner" title="A picture, GIF or short video from your PC">+ Add file</button><button type="button" class="btn ghost sm" data-art="link:banner" title="Paste a web address of a picture or video">🔗 Add link</button><button type="button" class="btn ghost sm" data-art="find:banner" title="Opens SteamGridDB in your browser">🌐 Find online</button><button type="button" class="btn ghost sm" data-art="we:banner" title="One of your Wallpaper Engine wallpapers">🖼 Wallpaper Engine</button>' +
      (ownMissing ? '<button type="button" class="btn ghost sm" data-bgedit="own:0">↺ ' + esc(g.source) + '\'s own</button>' : '') +
      (g.custom_banner ? '<button type="button" class="btn ghost sm" data-art="clear:banner" title="Remove yours, back to the launcher\'s own">🗑 All yours</button>' : '') + '</div>' +
      (GM.link === 'banner' ? '<div class="row nw"><input class="field grow" id="artUrl" data-which="banner" placeholder="https://… a picture, GIF or short video" aria-label="Link"><button type="button" class="btn sm" id="artUrlGo">Add</button></div>' : '') + '</div>';
  }
  // Wallpaper Engine's wallpapers as backgrounds (15 Oct): videos move, scenes give their preview (sharpened later)
  var WP = { items: null, q: '', kind: 'all', thumbs: {} };
  function openWallpapers(g, which) {
    var dim = document.createElement('div'); dim.className = 'dim';
    function shown() {
      var q = WP.q.toLowerCase();
      return (WP.items || []).filter(function (w) { return (WP.kind === 'all' || (WP.kind === 'video' ? w.kind === 'video' : w.kind !== 'video')) && (!q || w.title.toLowerCase().indexOf(q) !== -1); });
    }
    function grid() {
      var list = shown();
      if (!WP.items) return '<span class="muted">Looking in your Steam libraries…</span>';
      if (!WP.items.length) return '<span class="muted">' + esc(WP.message || 'No wallpapers found.') + '</span>';
      if (!list.length) return '<span class="muted">Nothing matches.</span>';
      return list.map(function (w) {
        var t = WP.thumbs[w.id];
        return '<button type="button" class="wpcard" data-wp="' + esc(w.id) + '" title="' + esc(w.title) + '"><span class="wpimg"' + (t && t !== 'none' ? ' style="background-image:url(' + t + ')"' : '') + '></span>' +
          '<span class="ell">' + esc(w.title) + '</span><span class="row nw"><span class="tag' + (w.kind === 'video' ? ' acc' : '') + '">' + (w.kind === 'video' ? '▶ video' : w.kind === 'gif' ? 'GIF preview' : 'picture') + '</span><span class="muted">' + fmtBytes(w.size) + '</span></span></button>';
      }).join('');
    }
    function render() {
      dim.innerHTML = '<div class="dialog stack" role="dialog" aria-label="Wallpaper Engine" style="width:min(860px,96vw)"><div class="row sb"><b>🖼 A background from Wallpaper Engine · ' + esc(g.name) + '</b><button type="button" class="btn ghost sm" data-x>Close</button></div>' +
        '<div class="row nw"><input class="field grow" id="wpQ" placeholder="Search your wallpapers" value="' + esc(WP.q) + '" aria-label="Search">' +
        [['all', 'All'], ['video', 'Videos'], ['still', 'Scenes & others']].map(function (k) { return '<button type="button" class="chip" data-wpk="' + k[0] + '" aria-pressed="' + (WP.kind === k[0]) + '">' + k[1] + '</button>'; }).join('') + '</div>' +
        '<span class="muted">Video wallpapers become moving backgrounds (big ones get a 1920-wide copy without sound first). Scene and web wallpapers only run inside Wallpaper Engine, so their preview is used and sharpened to HD afterwards.</span>' +
        '<div class="wpgrid" id="wpGrid">' + grid() + '</div></div>';
      wire();
    }
    function wireGrid() {
      $$('[data-wp]', dim).forEach(function (b) { b.onclick = function () { use(b.getAttribute('data-wp')); }; });
      thumbs();
    }
    function wire() {
      $$('[data-x]', dim).forEach(function (b) { b.onclick = function () { dim.remove(); }; });
      var q = $('#wpQ', dim); q.oninput = function () { WP.q = q.value; $('#wpGrid', dim).innerHTML = grid(); wireGrid(); };
      $$('[data-wpk]', dim).forEach(function (b) { b.onclick = function () { WP.kind = b.getAttribute('data-wpk'); render(); }; });
      wireGrid();
    }
    var asking = {};
    function thumbs() {                                         // a few at a time, only the ones shown
      shown().filter(function (w) { return !WP.thumbs[w.id] && !asking[w.id]; }).slice(0, 6).forEach(function (w) {
        asking[w.id] = true;
        api('wallpaper_thumb', w.id).then(function (d) {
          WP.thumbs[w.id] = d || 'none'; var el = $('[data-wp="' + w.id + '"] .wpimg', dim); if (el && d) el.style.backgroundImage = 'url(' + d + ')';
          delete asking[w.id]; if (dim.isConnected) thumbs();
        }).catch(function () { delete asking[w.id]; });
      });
    }
    function use(id) {
      forgetBanners(g.key);
      api('game_wallpaper', g.key, which, id).then(function (r) {
        toast(r.message);
        if (!r.ok) return;
        dim.remove();
        if (!r.job) { GM.games = null; loadGames(true); return; }
        pollJobs();
        var t = setInterval(function () {
          var j = st.jobs.filter(function (x) { return x.id === r.job; })[0];
          if (!j || j.state === 'running' || j.state === 'waiting') return;
          clearInterval(t);
          toast(j.state === 'done' ? 'The Wallpaper Engine background is ready.' : j.message || 'Stopped.');
          if (j.state === 'done') { forgetBanners(g.key); GM.games = null; loadGames(true); }
        }, 700);
      }).catch(fail);
    }
    render();
    $('#app').appendChild(dim);
    dim.addEventListener('keydown', function (e) { if (e.key === 'Escape') dim.remove(); });
    if (!WP.items) api('wallpapers').then(function (r) { WP.items = r.items || []; WP.message = r.message || ''; if (dim.isConnected) render(); }).catch(function (e) { WP.items = []; WP.message = e.message; render(); });
    else $('#wpQ', dim).focus();
  }
  T.openWallpapers = openWallpapers;
  function artBox(g, b, which, label, size) {
    var has = which === 'cover' ? !!g.cover_data : g.has_banner, custom = which === 'cover' ? g.custom_cover : g.custom_banner;
    var hd = which === 'cover' ? g.hd_cover : g.hd_banner;
    var prev = which === 'cover' ? (coverMedia(g) || '<span class="muted">none yet</span>') :
      (b && b.data ? (b.kind === 'video' ? '<video src="' + b.data + '" muted loop autoplay playsinline></video>' : '<img src="' + b.data + '" alt="">') : '<span class="muted">' + (g.has_banner ? 'loading…' : 'none yet') + '</span>');
    return '<div class="artbox"><div class="row sb"><span class="lbl">' + label + ' · ' + size + '</span><div class="row">' + (hd ? '<span class="tag hd">HD</span>' : '') + (custom ? '<span class="tag">yours</span>' : has ? '<span class="tag">from ' + esc(g.source) + '</span>' : '') + '</div></div>' +
      '<div class="artprev ' + which + '">' + prev + '</div>' +
      '<div class="row"><button type="button" class="btn ghost sm" data-art="pick:' + which + '" title="A file from your PC">+ File</button><button type="button" class="btn ghost sm" data-art="link:' + which + '" title="Paste a web address of a picture">🔗 Link</button><button type="button" class="btn ghost sm" data-art="find:' + which + '" title="Opens SteamGridDB in your browser">🌐 Find online</button>' +
      (custom ? '<button type="button" class="btn ghost sm" data-art="clear:' + which + '" title="Back to the launcher\'s own">🗑</button>' : '') + '</div>' +
      (GM.link === which ? '<div class="row nw"><input class="field grow" id="artUrl" data-which="' + which + '" placeholder="https://… a picture, GIF or short video" aria-label="Link"><button type="button" class="btn sm" id="artUrlGo">Save</button></div>' : '') + '</div>';
  }
  function spotlight(g) {
    if (!g) return '<div class="card spotinfo"><span class="muted">' + (GM.games && GM.games.length ? 'Pick a game below.' : 'No games found. Toolbelt looks in Playnite, Steam, Epic, HoYoPlay and Minecraft; or press + Add game.') + '</span></div>';
    var b = GM.banners[g.key];
    var played = (g.playtime >= 3600 ? Math.round(g.playtime / 3600) + ' h played · ' : g.playtime >= 60 ? Math.round(g.playtime / 60) + ' min played · ' : '') + ago(g.last_played);
    var fx = [['off', 'Off'], ['shine', 'Shine'], ['tilt', 'Parallax'], ['scan', 'Scanlines'], ['glow', 'Glow']];
    var newGame = GM.shownKey !== g.key;                    // a new game slides its details in (PlayStation-style)
    GM.shownKey = g.key;
    var hasArt = !!(b && b.data), loading = g.has_banner && !(b && b.loaded);
    var tags = (g.banner_kind === 'gif' ? '<span class="tag acc">GIF</span>' : g.banner_kind === 'video' ? '<span class="tag acc">▶ video loop</span>' : '') +
      (g.hd_banner || (b && b.hd) ? '<span class="tag hd" title="Upscaled to HD with Real-ESRGAN">HD</span>' : g.hd_wait ? '<span class="tag hdwait" id="hdTag" title="Real-ESRGAN is sharpening its art in the background"><span class="t">making HD…</span><span class="hdbar"><i></i></span></span>' : '');
    return '<div class="hero' + (g.fx === 'glow' ? ' fx-glow' : '') + (hasArt ? '' : loading ? ' loading' : ' nocover') + (newGame ? ' reveal' : '') + '" id="hero">' +
      '<div class="mini">' + (coverMedia(g) || (g.icon_data ? '<img class="gicon" src="' + g.icon_data + '" alt="">' : '')) + '</div>' +
      '<div class="stack heroright"><div class="row gmeta"><span>' + esc(g.source) + ' · ' + played + '</span>' + tags + '</div><div class="logo-t">' + esc(g.name) + '</div>' +
      '<div class="spotinfo' + (newGame ? ' reveal' : '') + '"><div class="row"><button type="button" class="btn play" data-play="' + esc(g.key) + '">▶ Play</button><button type="button" class="btn ghost sm" id="gmFolder">Folder</button>' +
      '<button type="button" class="btn ghost sm" id="gmFav" aria-pressed="' + !!g.favourite + '">' + (g.favourite ? '★ Favourite' : '☆ Favourite') + '</button><button type="button" class="btn ghost sm" id="gmHide">' + (g.hidden ? 'Show again' : 'Hide') + '</button>' +
      (g.key.indexOf('custom:') === 0 ? '<button type="button" class="btn ghost sm" id="gmRemove">Remove</button>' : '') +
      '<button type="button" class="btn ghost sm" id="gmEdit" aria-pressed="' + GM.edit + '">' + (GM.edit ? '✓ Done editing' : '✎ Edit artwork') + '</button></div>' +
      (g.description ? '<p class="gdesc">' + esc(g.description.length > 420 ? g.description.slice(0, 420) + '…' : g.description) + '</p>' : '') + '</div></div></div>' +
      (!GM.edit ? '' : '<div class="card stack artcard"><b>Artwork</b><div class="artgrid">' + artBox(g, b, 'cover', 'Cover', '600 × 900, GIF or video') + bannerBox(g) + '</div>' +
      '<div class="row sb"><span class="lbl">Background effect</span><div class="row">' + fx.map(function (f) { return '<button type="button" class="chip" data-fx="' + f[0] + '" aria-pressed="' + (g.fx === f[0]) + '">' + f[1] + '</button>'; }).join('') + '</div></div>' +
      '<span class="muted">Covers and backgrounds come from Playnite and Steam when they have them. Small pictures, GIFs and short videos (up to a minute) are sharpened to HD by themselves (Real-ESRGAN, on your graphics card; GIFs become animated WebP); the originals stay. Your own choices are copied to AppData\\Toolbelt\\art.</span></div>');
  }
  function bgFx(g) { return g && g.fx && g.fx !== 'off' && g.fx !== 'glow' ? ' fx-' + g.fx : ''; }
  VIEWS.games = function () {
    var list = GM.games ? shownGames() : [];
    var g = selGame();
    var filters = [['all', 'All'], ['installed', 'Installed'], ['fav', 'Favourites'], ['hidden', 'Hidden']];
    var sorts = [['recent', 'Recent'], ['name', 'A–Z'], ['time', 'Most played']];
    var layer = function (id) { return '<div class="layer' + (GM.bgOn === id && GM.bgHtml[id] ? ' on' : '') + '" id="bg' + id + '">' + GM.bgHtml[id] + '</div>'; };
    return '<div class="lib full" id="lib"><div class="libbg' + bgFx(g) + '" id="libbg" aria-hidden="true">' + layer('A') + layer('B') + '<div class="shade"></div></div>' +
      '<div class="row sb libtop"><h2 class="h">Games' + (GM.games ? ' · ' + list.length : '') + '</h2><div class="row">' +
      '<input class="field" id="gmQ" placeholder="Search" value="' + esc(GM.q) + '" style="width:150px" aria-label="Search games">' +
      filters.map(function (f) { return '<button type="button" class="chip" data-gfilter="' + f[0] + '" aria-pressed="' + (GM.filter === f[0]) + '">' + f[1] + '</button>'; }).join('') +
      '<span class="muted">·</span>' + sorts.map(function (f) { return '<button type="button" class="chip" data-gsort="' + f[0] + '" aria-pressed="' + (GM.sort === f[0]) + '">' + f[1] + '</button>'; }).join('') +
      '<span class="hdline" id="hdLine" hidden><span class="t"></span><span class="hdbar"><i></i></span></span>' +
      '<button type="button" class="btn sm" id="gmAdd">+ Add game</button><button type="button" class="btn ghost sm" id="gmRefresh"' + (GM.busy ? ' disabled' : '') + '>Look again</button><button type="button" class="btn ghost sm" id="gmJump">Update the taskbar menu</button></div></div>' +
      (GM.games === null ? '<div class="stage"><div class="card spotinfo"><span class="muted">Looking for your games…</span></div></div>' :
      '<div class="stage" id="spot">' + spotlight(g) + '</div>' +
      '<div class="shelf"><div class="games" id="gameGrid" role="listbox" aria-label="Your games">' + (list.length ? list.map(tile).join('') : '<span class="muted">Nothing here' + (GM.filter === 'hidden' ? ': nothing is hidden' : GM.q ? ' for "' + esc(GM.q) + '"' : '') + '.</span>') + '</div></div>') + '</div>';
  };
  function bgMarkup(b) {
    if (!b || !b.data) return '';
    if (b.kind === 'video') return '<video class="sharp" src="' + b.data + '" autoplay muted loop playsinline></video>';
    return '<img class="soft" src="' + b.data + '" alt=""><img class="sharp" src="' + b.data + '" alt="">';
  }
  // The background swap (his ask, 15 Oct: "it must be a smooth transition"): the next one is put in the free layer,
  // ON TOP and invisible; only when it is really ready (picture decoded, video playing) does it fade in, slowly, over the
  // one that is up, which stays fully visible underneath until the fade is done. No dark dip, no flash, no half-loaded frame.
  function layerReady(layer) {
    var img = $('img.sharp', layer) || $('img', layer), v = $('video', layer);
    var wait = v ? new Promise(function (ok) { if (v.readyState >= 3) ok(); else { v.addEventListener('canplay', ok, { once: true }); v.addEventListener('error', ok, { once: true }); } })
      .then(function () { return v.play().catch(function () {}); })
      : img && img.decode ? img.decode().catch(function () {}) : Promise.resolve();
    return Promise.race([wait, new Promise(function (ok) { setTimeout(ok, 5000); })]);   // never stuck on a slow file
  }
  function showBanner(key, force) {
    var b = GM.banners[key];
    var next = GM.bgOn === 'A' ? 'B' : 'A';
    var layer = $('#bg' + next), old = $('#bg' + GM.bgOn);
    if (!layer || !old) return;
    var src = b && b.data ? b.data : '';
    if (!force && GM.bgKey === key && GM.bgSrc === src && (old.classList.contains('on') || !src)) {   // the same picture is already up
      if (GM.slideKey !== key) slideNext(key);                     // …but its slideshow must still run (after a redraw too)
      return;
    }
    var token = GM.bgToken = (GM.bgToken || 0) + 1;
    clearTimeout(GM.slideT); GM.slideKey = null;
    GM.bgHtml[next] = bgMarkup(b);
    layer.classList.remove('on');
    layer.style.zIndex = 2; old.style.zIndex = 1;                // the new one comes in over the old one
    layer.innerHTML = GM.bgHtml[next];
    GM.bgOn = next; GM.bgKey = key; GM.bgSrc = src;
    var bg = $('#libbg'); if (bg) bg.className = 'libbg' + bgFx(selGame());
    if (!GM.bgHtml[next]) { old.classList.remove('on'); return; }     // nothing to show: the old one fades away
    layerReady(layer).then(function () {
      if (token !== GM.bgToken) return;                           // a newer swap started meanwhile
      requestAnimationFrame(function () {
        layer.classList.add('on');
        setTimeout(function () {                                  // the fade is done: now the old one can go
          if (token !== GM.bgToken) return;
          old.classList.remove('on'); old.innerHTML = ''; GM.bgHtml[old.id === 'bgA' ? 'A' : 'B'] = '';
          slideNext(key);
        }, reduce || !st.settings.animations ? 50 : 2600);
      });
    });
  }
  // several backgrounds per game: after a while (Settings: 10 / 20 / 45 / 90 s; a video always plays to its end first)
  // the next one fades in, round and round
  function slideNext(key) {
    clearTimeout(GM.slideT);
    GM.slideKey = null;
    var g = selGame();
    if (!g || g.key !== key || (g.banner_count || 0) < 2) return;
    var ms = ((st.settings && st.settings.banner_dwell) || 20) * 1000, v = $('#bg' + GM.bgOn + ' video');
    if (v && isFinite(v.duration) && v.duration > 0) ms = Math.max(ms, v.duration * 1000);
    GM.slideKey = key;
    GM.slideT = setTimeout(function () {
      GM.slideKey = null;
      if (st.screen !== 'games' || GM.sel !== key) return;
      GM.bidx[key] = ((GM.bidx[key] || 0) + 1) % g.banner_count;
      loadBanner(key, $('#screen'), true);
    }, ms);
  }
  function forgetBanners(key) {
    delete GM.banners[key];
    Object.keys(GM.bcache).forEach(function (k) { if (k.indexOf(key + '#') === 0) delete GM.bcache[k]; });
  }
  function loadBanner(key, m, force) {
    var g = (GM.games || []).filter(function (x) { return x.key === key; })[0];
    if (!g) return;
    var n = Math.max(1, g.banner_count || 1), i = (GM.bidx[key] || 0) % n, ck = key + '#' + i, first = !GM.banners[key];
    GM.bidx[key] = i;
    if (GM.bcache[ck]) { GM.banners[key] = GM.bcache[ck]; showBanner(key, force); return; }
    if (!g.has_banner) { GM.banners[key] = { kind: 'pic', data: '' }; showBanner(key, force); return; }
    api('game_banner', key, i).then(function (r) {
      GM.bcache[ck] = { kind: r.kind, data: r.ok ? r.data : '', loaded: true, hd: !!r.hd };
      if (st.screen === 'games' && GM.sel === key && GM.bidx[key] === i) {
        GM.banners[key] = GM.bcache[ck];
        if (first) { var sp = $('#spot'); if (sp) { sp.innerHTML = spotlight(g); wireSpot(m); } }
        showBanner(key, force);
      }
    }).catch(function () { GM.banners[key] = { kind: 'pic', data: '' }; });
  }
  function gamesHd(key) {                                    // Python finished an HD cover or background: swap it in quietly
    forgetBanners(key);
    api('games', false, true).then(function (list) {
      GM.games = list || GM.games;
      if (st.screen !== 'games') return;
      var m = $('#screen'), g = selGame();
      var grid = $('#gameGrid', m); if (grid) { var keep = grid.scrollLeft; grid.innerHTML = shownGames().map(tile).join(''); grid.scrollLeft = keep; wireTiles(m); }
      if (g) { var sp = $('#spot', m); if (sp && !GM.edit) { sp.innerHTML = spotlight(g); wireSpot(m); } if (g.key === key) loadBanner(key, m, true); }
    }).catch(function () {});
  }
  function gmChange(fn) { return fn.then(function (r) { if (r && r.message) toast(r.message); if (!r || r.ok !== false) { GM.games = null; loadGames(true); } }).catch(fail); }
  function wireSpot(m) {
    var g = selGame(); if (!g) return;
    hdPaint();
    var pl = $('[data-play]', m); if (pl) pl.onclick = function () { api('play_game', g.key).then(function (res) { toast(res.message); if (res.ok) { GM.games = null; loadGames(false); } }).catch(fail); };
    var ed = $('#gmEdit', m); if (ed) ed.onclick = function () { GM.edit = !GM.edit; GM.link = ''; var sp = $('#spot', m); if (sp) { sp.innerHTML = spotlight(g); wireSpot(m); } if (GM.edit) { var ac = $('.artcard', m); if (ac) ac.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } };
    var fo = $('#gmFolder', m); if (fo) fo.onclick = function () { api('game_folder', g.key).then(function (r) { toast(r.message); }).catch(fail); };
    var fv = $('#gmFav', m); if (fv) fv.onclick = function () { gmChange(api('game_set', g.key, 'favourite', !g.favourite)); };
    var hd = $('#gmHide', m); if (hd) hd.onclick = function () { gmChange(api('game_set', g.key, 'hidden', !g.hidden)); };
    var rm = $('#gmRemove', m); if (rm) rm.onclick = function () { gmChange(api('game_remove', g.key)); };
    $$('[data-fx]', m).forEach(function (b) { b.onclick = function () { gmChange(api('game_set', g.key, 'fx', b.getAttribute('data-fx'))); }; });
    $$('[data-bgshow]', m).forEach(function (b) { b.onclick = function () {      // show that background now (it fades in)
      GM.bidx[g.key] = +b.getAttribute('data-bgshow');
      $$('.bgthumb', m).forEach(function (t, i) { t.classList.toggle('on', i === GM.bidx[g.key]); });
      loadBanner(g.key, m, true);
    }; });
    $$('[data-bgedit]', m).forEach(function (b) { b.onclick = function () {      // ◀ ▶ ✕ and "the launcher's own back"
      var parts = b.getAttribute('data-bgedit').split(':'), what = parts[0], i = +parts[1];
      forgetBanners(g.key);
      if (what === 'left' || what === 'right') GM.bidx[g.key] = i + (what === 'left' ? -1 : 1);
      else if (what === 'remove' && (GM.bidx[g.key] || 0) >= i) GM.bidx[g.key] = Math.max(0, (GM.bidx[g.key] || 0) - 1);
      gmChange(api('game_banner_edit', g.key, what, i));
    }; });
    $$('[data-art]', m).forEach(function (b) { b.onclick = function () {
      var parts = b.getAttribute('data-art').split(':'), what = parts[0], which = parts[1];
      if (what === 'link') { GM.link = GM.link === which ? '' : which; $('#spot', m).innerHTML = spotlight(g); wireSpot(m); var u = $('#artUrl', m); if (u) u.focus(); return; }
      if (what === 'find') { api('game_art_search', g.key, which).then(function (r) { toast(r.message); }).catch(fail); return; }
      if (what === 'we') { openWallpapers(g, which); return; }
      if (what === 'clear') { forgetBanners(g.key); GM.bidx[g.key] = 0; gmChange(api('game_art_clear', g.key, which)); return; }
      forgetBanners(g.key); gmChange(api('game_art_pick', g.key, which));
    }; });
    var urlGo = $('#artUrlGo', m), urlIn = $('#artUrl', m);
    if (urlGo && urlIn) {
      urlGo.onclick = function () {
        var url = urlIn.value.trim(); if (!url) { toast('Paste a link first.'); return; }
        var which = urlIn.getAttribute('data-which');
        urlGo.disabled = true; urlGo.textContent = 'Fetching…';
        forgetBanners(g.key);
        api('game_art_url', g.key, which, url).then(function (r) {
          toast(r.message);
          if (r.ok) { GM.link = ''; GM.games = null; loadGames(true); } else { urlGo.disabled = false; urlGo.textContent = 'Save'; }
        }).catch(fail);
      };
      urlIn.addEventListener('keydown', function (e) { if (e.key === 'Enter') urlGo.click(); });
    }
  }
  // "making HD" with a bar (his ask, 15 Oct: it takes long): the game being sharpened, how far, how many wait
  function hdTick() {
    if (st.screen !== 'games') return;
    api('games_hd_status').then(function (s) { GM.hd = s; hdPaint(); }).catch(function () {});
  }
  function hdPaint() {
    var s = GM.hd || {}, now = s.now || {}, waiting = s.waiting || [], line = $('#hdLine'), tag = $('#hdTag');
    var pct = Math.round(now.progress || 0), what = now.which === 'cover' ? 'cover' : 'background';
    if (line) {
      line.hidden = !now.key && !waiting.length;
      $('.t', line).textContent = now.key ? 'HD: ' + (now.name || 'a game') + ' ' + what + ' ' + pct + '%' + (waiting.length ? ' · ' + waiting.length + ' more waiting' : '') : waiting.length ? 'HD: ' + waiting.length + ' waiting' : '';
      $('.hdbar i', line).style.width = (now.key ? pct : 0) + '%';
    }
    if (tag) {
      var mine = now.key && now.key === GM.sel, queued = waiting.indexOf(GM.sel);
      $('.t', tag).textContent = mine ? 'making HD… ' + pct + '%' + (now.seconds > 20 ? ' · ' + fmtTime(now.seconds) : '') : queued !== -1 ? 'HD next' + (queued ? ' (' + (queued + 1) + ' in line)' : '') : 'making HD…';
      $('.hdbar i', tag).style.width = (mine ? pct : 0) + '%';
      tag.title = mine && now.message ? now.message : 'Real-ESRGAN is sharpening its art in the background';
    }
  }
  WIRE.games = function (m) {
    if (GM.games === null && !GM.busy) loadGames(false);
    if (!GM.hdTimer) GM.hdTimer = setInterval(hdTick, 1000);
    hdPaint(); hdTick();
    var r = $('#gmRefresh', m); if (r) r.onclick = function () { GM.games = null; GM.banners = {}; GM.bcache = {}; go('games', true); loadGames(true); };
    var j = $('#gmJump', m); if (j) j.onclick = function () { api('refresh_jumplist').then(function (res) { toast(res.message); }).catch(fail); };
    var a = $('#gmAdd', m); if (a) a.onclick = function () { gmChange(api('game_add')); };
    var q = $('#gmQ', m); if (q) q.oninput = function () { GM.q = q.value; var grid = $('#gameGrid', m); if (grid) { var list = shownGames(); grid.innerHTML = list.length ? list.map(tile).join('') : '<span class="muted">Nothing here.</span>'; wireTiles(m); } };
    $$('[data-gfilter]', m).forEach(function (b) { b.onclick = function () { GM.filter = b.getAttribute('data-gfilter'); var list = shownGames(); if (list.length && !list.some(function (x) { return x.key === GM.sel; })) GM.sel = list[0].key; go('games', true); }; });
    $$('[data-gsort]', m).forEach(function (b) { b.onclick = function () { GM.sort = b.getAttribute('data-gsort'); go('games', true); }; });
    var grid = $('#gameGrid', m);
    if (grid) grid.onwheel = function (e) { if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && grid.scrollWidth > grid.clientWidth) { grid.scrollLeft += e.deltaY; e.preventDefault(); } };
    var lib = $('#lib', m);                                  // Parallax: the background drifts a little with the mouse
    if (lib) {
      lib.onmousemove = function (e) { var bg = $('#libbg', m); if (!bg || bg.className.indexOf('fx-tilt') === -1) return; var r = lib.getBoundingClientRect(); bg.style.setProperty('--px', ((e.clientX - r.left) / r.width - .5).toFixed(3)); bg.style.setProperty('--py', ((e.clientY - r.top) / r.height - .5).toFixed(3)); };
      lib.onmouseleave = function () { var bg = $('#libbg', m); if (bg) { bg.style.setProperty('--px', 0); bg.style.setProperty('--py', 0); } };
    }
    wireTiles(m);
    wireSpot(m);
    if (GM.sel) loadBanner(GM.sel, m);
  };
  function pickGame(key, m) {
    GM.sel = key; GM.link = ''; GM.edit = false;
    $$('[data-game]', m).forEach(function (x) { x.setAttribute('aria-pressed', String(x.getAttribute('data-game') === key)); });
    var t = $('[data-game="' + key.replace(/"/g, '\\"') + '"]', m); if (t && t.scrollIntoView) t.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'nearest', inline: 'nearest' });
    var sp = $('#spot', m); if (sp) { sp.innerHTML = spotlight(selGame()); wireSpot(m); }
    loadBanner(GM.sel, m);
    shelfPlay(m);
  }
  function wireTiles(m) {
    var tiles = $$('[data-game]', m);
    tiles.forEach(function (b, i) {
      b.onclick = function () { pickGame(b.getAttribute('data-game'), m); };
      if ($('video.gtv', b) || b.getAttribute('data-anim')) { b.onmouseenter = function () { shelfPlay(m); }; b.onmouseleave = function () { setTimeout(function () { shelfPlay(m); }, 0); }; }
      b.ondblclick = function () { api('play_game', b.getAttribute('data-game')).then(function (res) { toast(res.message); }).catch(fail); };
      b.onkeydown = function (e) {                            // ← → walk the shelf like a console
        var to = e.key === 'ArrowRight' ? tiles[i + 1] : e.key === 'ArrowLeft' ? tiles[i - 1] : null;
        if (to) { e.preventDefault(); to.focus(); pickGame(to.getAttribute('data-game'), m); }
      };
    });
  }

  function pollMail() {                                       // the taskbar menu and the tray say "open this screen" through Python
    api('mail').then(function (list) { (list || []).forEach(function (x) {
      if (x.games_hd) { gamesHd(x.games_hd); return; }
      if (x.toast) toast(x.toast);
      if (x.run) {                                          // the command door: Waypoint's right-click menu handed over a file
        if (x.run === 'cutout') { go('bg'); cutStart(api('cut_token', x.token)); }
        else if (x.run === 'check') { CK.file = x.file; CK.hashes = null; CK.hashJob = null; CK.verdict = null; CK.sign = null; CK.sniff = null; CK.tab = 'hash'; go('check'); }
        else { MD.file = x.file; MD.start = 0; MD.end = 0; MD.plan = null; MD.prev = null; MD.vplan = null; MD.tab = x.run === 'upscale' ? 'upscale' : x.file.kind === 'video' ? 'vcomp' : x.file.kind === 'gif' ? 'upscale' : 'icomp'; if (x.run === 'upscale') MD.what = x.file.kind === 'gif' ? 'gif' : x.file.kind === 'video' ? 'video' : 'picture'; go('media'); }
        return;
      }
      if (x.open === 'guard-scan') { GD.tab = 'scan'; loadGuard(); go('guard'); return; }
      if (x.open === 'calc-mini') api('calc_show').catch(function () {}); else if (x.open && VIEWS[x.open]) go(x.open);
    }); }).catch(function () {});
  }

  // ---------- step 2: the downloader ----------
  var DL = { video: null, busy: false, error: '', keep: null, height: null, audio: null, thumbs: {}, hist: {}, tagging: null, songs: null, updates: null, place: null, places: null };
  var PLACES = [['folder', 'Toolbelt folder'], ['desktop', 'Desktop'], ['library', 'Videos / Music'], ['spotify', 'Spotify'], ['custom', 'Pick a folder…']];
  function placeFolder(p) {
    var P = DL.places || {};
    if (p === 'spotify' && !(DL.keep === 'audio' && DL.audio === 'mp3')) p = 'folder';
    if (p === 'library') return DL.keep === 'audio' ? P.music : P.videos;
    if (p === 'custom' && !P.custom) p = 'folder';
    return P[p] || '';
  }
  var DL_ENGINES = ['yt-dlp', 'deno', 'ffmpeg'];
  var INSTALLABLE = ['yt-dlp', 'deno', 'ffmpeg', 'birefnet', 'realesrgan'];
  function fmtTime(s) { if (s == null) return '…'; s = Math.round(s); return s >= 3600 ? Math.floor(s / 3600) + ':' + ('0' + Math.floor(s / 60) % 60).slice(-2) + ':' + ('0' + s % 60).slice(-2) : Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }
  function fmtSpeed(b) { return !b ? '—' : b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB/s' : Math.round(b / 1024) + ' KB/s'; }
  function dlMissing() { return st.engines ? st.engines.engines.filter(function (x) { return DL_ENGINES.indexOf(x.id) !== -1 && !x.installed; }) : []; }
  function dlJobs(states) { return st.jobs.filter(function (j) { return j.kind === 'Download' && states.indexOf(j.state) !== -1; }); }
  function engineJobs() { return st.jobs.filter(function (j) { return j.kind === 'Engine' && (j.state === 'running' || j.state === 'waiting'); }); }

  VIEWS.video = function () {
    var s = st.settings || {}, miss = dlMissing(), installing = engineJobs();
    if (DL.keep === null) { DL.keep = s.keep || 'both'; DL.audio = s.audio_format || 'mp3'; }
    var head = '<div class="row sb"><h2 class="h">Downloads</h2><div class="row"><span class="tag">Speed <b id="dlSpeed">—</b></span>' +
      (DL.updates && DL.updates['yt-dlp'] && DL.updates['yt-dlp'].update ? '<span class="tag warn">yt-dlp has an update · <button type="button" class="btn sm" style="padding:3px 7px" id="dlUpd">Update</button></span>' : '') + '</div></div>';
    if (st.engines && (miss.length || installing.length)) {
      return head + '<div class="card stack"><b>The downloader needs three engines first</b>' +
        '<span class="muted">yt-dlp (downloads), Deno (needed for YouTube) and ffmpeg (joins 4K picture and sound, makes MP3s). About 160 MB downloaded from their official sites; every file is checked against the maker\'s fingerprint. They go in your AppData, never in OneDrive.</span>' +
        '<div class="list">' + st.engines.engines.filter(function (x) { return DL_ENGINES.indexOf(x.id) !== -1; }).map(function (x) {
          var j = st.jobs.filter(function (k) { return k.kind === 'Engine' && k.extra && k.extra.engine === x.id; })[0];
          var state = x.installed ? '<span class="okc">installed ' + esc(x.version) + '</span>' : j && (j.state === 'running' || j.state === 'waiting') ? '<span class="warnc">' + Math.round(j.progress) + '% · ' + esc(j.message || 'waiting') + '</span>' : j && j.state === 'failed' ? '<span class="badc">' + esc(j.message) + '</span>' : '<span class="muted">not installed · ' + esc(x.approx) + '</span>';
          return '<div class="item"><b>' + esc(x.name) + '</b><span class="muted">' + esc(x.what) + '</span><span>' + state + '</span></div>';
        }).join('') + '</div><div class="row"><button type="button" class="btn" id="dlInstall"' + (installing.length ? ' disabled' : '') + '>' + (installing.length ? 'Installing…' : 'Install them') + '</button></div></div>';
    }
    return head + '<div class="card stack"><div class="row nw"><input class="field" id="dlLink" placeholder="Paste a YouTube link (or copy one anywhere: Toolbelt notices)" value="' + esc(DL.link || '') + '" aria-label="Video link">' +
      '<button type="button" class="btn ghost" id="dlPaste">Paste</button><button type="button" class="btn" id="dlLook"' + (DL.busy ? ' disabled' : '') + '>' + (DL.busy ? 'Looking…' : 'Look up') + '</button></div>' +
      (DL.error ? '<span class="err">' + esc(DL.error) + '</span>' : '<span class="muted">For videos you\'re allowed to keep.</span>') + '</div>' +
      '<div id="dlChoice">' + choiceHtml() + '</div>' +
      '<div class="card dlhero" id="dlHero"></div>' +
      '<div class="graph"><canvas id="dlGraph"></canvas><div class="gl"><span><i style="background:var(--accent)"></i>Download speed</span></div></div>' +
      '<div class="row sb"><h3 class="h">Up next · <span id="dlQN">0</span></h3><span class="muted">two at a time</span></div><div class="list" id="dlQueue"></div>' +
      '<div class="row sb"><h3 class="h">Completed · <span id="dlDN">0</span></h3><button type="button" class="btn ghost sm" id="dlClear">Clear list</button></div><div class="list" id="dlDone"></div>' +
      '<div class="card stack" id="dlSpotify"></div>';
  };
  function choiceHtml() {
    var v = DL.video;
    if (!v) return '';
    if (DL.height === null && v.heights.length) DL.height = (v.heights.filter(function (h) { return h.height <= 2160; })[0] || v.heights[0]).height;
    var thumb = DL.thumbs[v.id] ? '<img class="thumbimg" src="' + DL.thumbs[v.id] + '" alt="">' : '<div class="thumbimg"></div>';
    var keep = [['both', 'Video + sound'], ['video', 'Video only'], ['audio', 'Just the sound']].map(function (k) { return '<button type="button" class="chip" data-keep="' + k[0] + '" aria-pressed="' + (DL.keep === k[0]) + '">' + k[1] + '</button>'; }).join('');
    var opts = DL.keep === 'audio' ? ['mp3', 'm4a', 'opus'].map(function (a) {
        return '<button type="button" class="chip" data-audio="' + a + '" aria-pressed="' + (DL.audio === a) + '">' + { mp3: 'MP3', m4a: 'M4A', opus: 'Opus' }[a] + ' <small>· ' + fmtBytes(v.sound[a]) + '</small></button>'; }).join('')
      : v.heights.map(function (h) { return '<button type="button" class="chip" data-height="' + h.height + '" aria-pressed="' + (DL.height === h.height) + '">' + esc(h.label) + ' <small>· ' + fmtBytes(DL.keep === 'video' ? h.video_only : h.size) + '</small></button>'; }).join('');
    var mp3 = DL.keep === 'audio' && DL.audio === 'mp3';
    if (DL.place === null) DL.place = st.settings.send_to || 'folder';
    if (DL.place === 'spotify' && !mp3) DL.place = 'folder';
    var send = PLACES.map(function (p) {
      var off = p[0] === 'spotify' && !mp3;
      var label = p[0] === 'custom' && DL.places && DL.places.custom ? esc(DL.places.custom.split('\\').pop() || DL.places.custom) + ' <small>· change</small>' : esc(p[1]);
      return '<button type="button" class="chip" data-place="' + p[0] + '" aria-pressed="' + (DL.place === p[0]) + '"' + (off ? ' disabled title="Spotify only plays MP3s: pick Just the sound + MP3"' : '') + '>' + label + '</button>';
    }).join('');
    var spot = mp3 && DL.place !== 'spotify' ? '<div class="row nw">' + sw('dlSpot', st.settings.auto_spotify, 'Also put it in Spotify') + '<span>Also put it in Spotify (Local Files)</span></div>' : '';
    return '<div class="card stack"><div class="row nw" style="align-items:flex-start">' + thumb + '<div class="stack" style="gap:4px"><b>' + esc(v.title) + '</b><span class="muted">' + esc(v.channel) + ' · ' + fmtTime(v.duration) + (v.is_live ? ' · live' : '') + '</span>' +
      '<div class="row" style="margin-top:4px"><button type="button" class="btn ghost sm" id="dlSpotSearch">Is it on Spotify already?</button></div></div></div>' +
      '<span class="lbl">Keep</span><div class="row">' + keep + '</div><span class="lbl">' + (DL.keep === 'audio' ? 'Format' : 'Quality') + '</span><div class="row">' + opts + '</div><span class="lbl">Send to</span><div class="row">' + send + '</div>' + spot +
      '<div class="row sb"><span class="muted" id="dlWhere">Saves to ' + esc(placeFolder(DL.place) || st.settings.save_to) + '</span><button type="button" class="btn" id="dlGo">Download</button></div></div>';
  }
  function wireChoice(m) {
    var box = $('#dlChoice', m); if (!box) return;
    $$('[data-keep]', box).forEach(function (b) { b.onclick = function () { DL.keep = b.getAttribute('data-keep'); box.innerHTML = choiceHtml(); wireChoice(m); }; });
    $$('[data-audio]', box).forEach(function (b) { b.onclick = function () { DL.audio = b.getAttribute('data-audio'); box.innerHTML = choiceHtml(); wireChoice(m); }; });
    $$('[data-height]', box).forEach(function (b) { b.onclick = function () { DL.height = +b.getAttribute('data-height'); box.innerHTML = choiceHtml(); wireChoice(m); }; });
    $$('[data-place]', box).forEach(function (b) { b.onclick = function () {
      var p = b.getAttribute('data-place');
      function redraw() { box.innerHTML = choiceHtml(); wireChoice(m); }
      if (p === 'custom' && (!DL.places || !DL.places.custom || DL.place === 'custom')) {
        api('choose_send_folder').then(function (r) {
          if (!r.ok) { if (r.message) toast(r.message); return; }
          st.settings = r.settings; DL.place = 'custom';
          return api('send_places').then(function (pl) { DL.places = pl; redraw(); });
        }).catch(fail);
        return;
      }
      DL.place = p; change('send_to', p); redraw();
    }; });
    var sp = $('#dlSpot', box); if (sp) sp.onclick = function () { var on = sp.getAttribute('aria-checked') !== 'true'; sp.setAttribute('aria-checked', String(on)); change('auto_spotify', on); };
    var ss = $('#dlSpotSearch', box); if (ss) ss.onclick = function () { api('spotify_search', DL.video.title).then(function (r) { toast(r.message); }).catch(fail); };
    var go = $('#dlGo', box);
    if (go) go.onclick = function () {
      var v = DL.video;
      api('start_download', v.id, DL.keep, DL.height, DL.audio, v.title, DL.place).then(function (r) {
        if (!r.ok) { toast(r.message); return; }
        toast('Added: ' + v.title); DL.video = null; DL.link = ''; DL.height = null;
        var l = $('#dlLink', m); if (l) l.value = '';
        box.innerHTML = ''; pollJobs();
      }).catch(fail);
    };
  }
  function lookUp(url) {
    url = (url || '').trim(); if (!url) { toast('Paste a link first.'); return; }
    DL.link = url; DL.busy = true; DL.error = ''; DL.video = null; DL.height = null;
    if (st.screen === 'video') go('video', true);
    api('look_up', url).then(function (r) {
      DL.busy = false;
      if (r.ok) { DL.video = r.video; if (r.video.thumb) DL.thumbs[r.video.id] = r.video.thumb; } else DL.error = r.message;
      if (st.screen === 'video') go('video', true);
    }).catch(function (e) { DL.busy = false; DL.error = e.message; if (st.screen === 'video') go('video', true); });
  }
  WIRE.video = function (m) {
    var inst = $('#dlInstall', m);
    if (inst) inst.onclick = function () { inst.disabled = true; api('install_engines').then(function (r) { toast(r.message); pollJobs(); }).catch(fail); };
    var upd = $('#dlUpd', m);
    if (upd) upd.onclick = function () { api('install_engines', ['yt-dlp']).then(function (r) { toast('Updating yt-dlp'); DL.updates = null; pollJobs(); }).catch(fail); };
    var link = $('#dlLink', m); if (!link) return;
    link.addEventListener('keydown', function (e) { if (e.key === 'Enter') lookUp(link.value); });
    link.addEventListener('input', function () { DL.link = link.value; });
    $('#dlLook', m).onclick = function () { lookUp(link.value); };
    $('#dlPaste', m).onclick = function () { api('paste').then(function (text) { link.value = (text || '').trim(); DL.link = link.value; if (link.value) lookUp(link.value); else toast('The clipboard has no text.'); }).catch(fail); };
    $('#dlClear', m).onclick = function () { api('clear_jobs').then(pollJobs).catch(fail); };
    wireChoice(m);
    api('send_places').then(function (pl) {
      DL.places = pl;
      var box = $('#dlChoice', m); if (box && DL.video) { box.innerHTML = choiceHtml(); wireChoice(m); }
    }).catch(function () {});
    renderDl(); loadSongs();
    if (!DL.updates && !DL.updateAsked) { DL.updateAsked = true; api('check_updates').then(function (u) { DL.updates = u; if (st.screen === 'video' && u['yt-dlp'] && u['yt-dlp'].update) go('video', true); }).catch(function () {}); }
  };
  function renderDl() {
    var m = $('#screen'); if (st.screen !== 'video' || !$('#dlHero', m)) return;
    var active = dlJobs(['running'])[0], queue = dlJobs(['waiting']).slice().reverse(), done = dlJobs(['done', 'failed', 'cancelled']);
    var hero = $('#dlHero', m);
    if (!active) {
      hero.innerHTML = '<div class="dlart idle"></div><div class="dlinfo"><span class="lbl">Downloading now</span><b>Nothing right now</b><span class="muted">Look a link up above, or copy one anywhere.</span></div>';
      hero.removeAttribute('data-job');
    } else {
      var x = active.extra || {}, th = DL.thumbs[x.video_id];
      if (hero.getAttribute('data-job') !== String(active.id)) {
        hero.setAttribute('data-job', active.id);
        hero.innerHTML = '<div class="dlart">' + (th ? '<img src="' + th + '" alt="">' : '') + '<span class="tag acc q">' + esc(x.quality || '') + '</span></div><div class="dlinfo"><span class="lbl" id="hStage"></span>' +
          '<b class="ell" style="font-size:17px">' + esc(active.title) + '</b><span class="muted ell">' + esc(x.channel || '') + '</span><div class="bar big run"><i id="hBar"></i></div>' +
          '<div class="dlstats"><span class="muted">Progress<b id="hP"></b></span><span class="muted">Downloaded<b id="hG"></b></span><span class="muted">Time left<b id="hL"></b></span><span class="muted">Speed<b id="hS"></b></span></div>' +
          '<div class="row"><button type="button" class="btn ghost sm" data-cancel="' + active.id + '">Cancel</button></div></div>';
        $('[data-cancel]', hero).onclick = function () { api('cancel_job', active.id).then(function (r) { toast(r.message); }).catch(fail); };
      }
      $('#hStage', hero).textContent = x.stage === 'Picture' || x.stage === 'Sound' ? 'Downloading now · ' + x.stage.toLowerCase() : (x.stage || 'Starting');
      $('#hBar', hero).style.width = active.progress + '%';
      $('#hP', hero).textContent = Math.round(active.progress) + '%';
      $('#hG', hero).textContent = x.total ? fmtBytes(x.got) + ' / ' + fmtBytes(x.total) : fmtBytes(x.got || 0);
      $('#hL', hero).textContent = x.eta != null ? fmtTime(x.eta) : '…';
      $('#hS', hero).textContent = fmtSpeed(x.speed);
    }
    var sp = $('#dlSpeed', m); if (sp) sp.textContent = fmtSpeed(active && active.extra ? active.extra.speed : 0);
    $('#dlQN', m).textContent = queue.length; $('#dlDN', m).textContent = done.length;
    $('#dlQueue', m).innerHTML = queue.length ? queue.map(function (j) {
      var x = j.extra || {};
      return '<div class="dlitem">' + (DL.thumbs[x.video_id] ? '<img class="thumbimg sm" src="' + DL.thumbs[x.video_id] + '" alt="">' : '<div class="thumbimg sm"></div>') + '<div style="min-width:0"><b class="ell">' + esc(j.title) + '</b><span class="muted">waiting</span></div><button type="button" class="btn ghost sm" data-cancel="' + j.id + '">Remove</button></div>';
    }).join('') : '<span class="muted">Nothing waiting.</span>';
    var doneBox = $('#dlDone', m), sig = done.map(function (j) { return j.id + j.state + (j.extra && j.extra.spotify || ''); }).join(',');
    if (doneBox.getAttribute('data-sig') !== sig) {
      if (doneBox.hasAttribute('data-sig')) loadSongs();        // something finished: the Spotify folder may have a new song
      doneBox.setAttribute('data-sig', sig);
      doneBox.innerHTML = done.length ? done.map(function (j) {
        var x = j.extra || {}, path = j.result || x.path || '', mp3 = /\.mp3$/i.test(path), tagable = /\.(mp3|m4a)$/i.test(path);
        var actions = j.state !== 'done' ? '<span class="' + (j.state === 'failed' ? 'badc' : 'muted') + '">' + esc(j.state === 'failed' ? j.message : 'cancelled') + '</span>' :
          (mp3 ? (x.spotify ? '<span class="tag ok">In Spotify ✓</span>' : '<button type="button" class="btn sm" data-spot="' + esc(path) + '">Send to Spotify</button>') : '') +
          (tagable ? '<button type="button" class="btn ghost sm" data-tags="' + esc(x.spotify || path) + '">Edit tags</button>' : '') +
          '<button type="button" class="btn ghost sm" data-show="' + esc(path) + '">Show in folder</button>';
        return '<div class="dlitem">' + (DL.thumbs[x.video_id] ? '<img class="thumbimg sm" src="' + DL.thumbs[x.video_id] + '" alt="">' : '<div class="thumbimg sm"></div>') +
          '<div style="min-width:0"><b class="ell">' + esc(j.title) + '</b><span class="muted ell">' + esc(x.quality || '') + (x.size ? ' · ' + fmtBytes(x.size) : '') + (path ? ' · ' + esc(path.split('\\').pop()) : '') + '</span></div><div class="row nw">' + actions + '</div></div>';
      }).join('') : '<span class="muted">Nothing finished yet.</span>';
      $$('[data-spot]', doneBox).forEach(function (b) { b.onclick = function () { api('send_to_spotify', b.getAttribute('data-spot')).then(function (r) { toast(r.message); if (r.ok) { b.outerHTML = '<span class="tag ok">In Spotify ✓</span>'; loadSongs(); } }).catch(fail); }; });
      $$('[data-show]', doneBox).forEach(function (b) { b.onclick = function () { api('show_file', b.getAttribute('data-show')).then(function (r) { if (!r.ok) toast(r.message); }).catch(fail); }; });
      $$('[data-tags]', doneBox).forEach(function (b) { b.onclick = function () { openTags(b.getAttribute('data-tags')); }; });
    }
    $$('#dlQueue [data-cancel]', m).forEach(function (b) { b.onclick = function () { api('cancel_job', +b.getAttribute('data-cancel')).then(pollJobs).catch(fail); }; });
    drawSpeed(active);
  }
  function drawSpeed(active) {
    var c = $('#dlGraph'); if (!c || !c.clientWidth) return;
    var key = active ? active.id : 'idle', h = DL.hist[key] || (DL.hist[key] = []);
    h.push(active && active.extra ? (active.extra.speed || 0) / 1048576 : 0); if (h.length > 90) h.shift();
    var w = c.clientWidth, ht = c.clientHeight, dpr = window.devicePixelRatio || 1; c.width = w * dpr; c.height = ht * dpr;
    var ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
    var cs = getComputedStyle($('#root')), acc = cs.getPropertyValue('--accent').trim(), line = cs.getPropertyValue('--line').trim();
    var max = Math.max(5, Math.max.apply(null, h) * 1.2), n = 90;
    ctx.strokeStyle = line; ctx.lineWidth = 1; [0.33, 0.66].forEach(function (f) { ctx.beginPath(); ctx.moveTo(0, ht * f); ctx.lineTo(w, ht * f); ctx.stroke(); });
    if (h.length < 2) return;
    function y(v) { return ht - v / max * (ht - 18) - 3; }
    ctx.beginPath(); h.forEach(function (v, i) { var x = (n - h.length + i) / (n - 1) * w; if (i) ctx.lineTo(x, y(v)); else ctx.moveTo(x, y(v)); });
    ctx.strokeStyle = acc; ctx.lineWidth = 2; ctx.stroke();
    ctx.lineTo(w, ht); ctx.lineTo((n - h.length) / (n - 1) * w, ht); ctx.closePath(); ctx.globalAlpha = .2; ctx.fillStyle = acc; ctx.fill(); ctx.globalAlpha = 1;
    ctx.fillStyle = cs.getPropertyValue('--ink2').trim(); ctx.font = '11px ' + cs.getPropertyValue('--body'); ctx.fillText(max.toFixed(0) + ' MB/s', w - 52, 14);
  }
  function loadSongs() {
    api('songs').then(function (r) { DL.songs = r; renderSongs(); }).catch(function () {});
  }
  function renderSongs() {
    var box = $('#dlSpotify'); if (!box || !DL.songs) return;
    var list = DL.songs.songs || [];
    box.innerHTML = '<div class="row sb"><b>Spotify · ' + list.length + ' song' + (list.length === 1 ? '' : 's') + ' in Music\\Toolbelt for Spotify</b><div class="row nw">' + (list.length ? '<button type="button" class="btn ghost sm" id="spFixAll" title="Ask LRCLIB about every song and propose tags lyrics-plus can find">✨ Fix all songs</button>' : '') + '<button type="button" class="btn ghost sm" id="spOpen">Open folder</button></div></div>' +
      '<span class="muted">One time only, in the Spotify app on your PC: <b>Settings → Your Library → Show Local Files</b> on, then <b>Add a source</b> and pick this folder. After that, new songs appear under <b>Local Files</b> by themselves. On your phone it needs Premium (download the playlist on the same Wi-Fi).</span>' +
      (list.length ? '<div class="list">' + list.map(function (sg) {
        var missing = [!sg.title && 'title', !sg.artist && 'artist', !sg.cover && 'cover', sg.cover && !sg.square && 'square cover', !sg.lyrics && 'lyrics'].filter(Boolean);
        return '<div class="item"><span class="' + (missing.length ? 'warnc' : 'okc') + '">' + (missing.length ? '!' : '✓') + '</span><div style="min-width:0"><b class="ell">' + esc(sg.title || sg.name) + '</b><span class="muted ell">' + esc(sg.artist || 'no artist') + (sg.album ? ' · ' + esc(sg.album) : '') + (missing.length ? ' · missing ' + missing.join(', ') : '') + '</span></div>' +
          '<div class="row nw"><button type="button" class="btn ghost sm" data-tags="' + esc(sg.path) + '">Tags</button><button type="button" class="btn ghost sm" data-cover="' + esc(sg.path) + '">Cover</button><button type="button" class="btn ghost sm" data-lyrics="' + esc(sg.path) + '">Lyrics</button></div></div>';
      }).join('') + '</div>' : '');
    $('#spOpen', box).onclick = function () { api('open_spotify_folder').then(function (r) { toast(r.message); }).catch(fail); };
    var fa = $('#spFixAll', box); if (fa) fa.onclick = function () { openFixAll(); };
    $$('[data-tags]', box).forEach(function (b) { b.onclick = function () { openTags(b.getAttribute('data-tags')); }; });
    $$('[data-cover]', box).forEach(function (b) { b.onclick = function () { openTags(b.getAttribute('data-cover'), 'cover'); }; });
    $$('[data-lyrics]', box).forEach(function (b) { b.onclick = function () { openTags(b.getAttribute('data-lyrics'), 'lyrics'); }; });
  }
  // Fix all songs (15 Oct): one job asks LRCLIB about every song; he sees current → proposed and saves the ticked ones
  var FIX_SAYS = { already: ['okc', 'already found'], clean: ['okc', 'found after a clean-up'], found: ['okc', 'found as LRCLIB names it'], none: ['warnc', 'not on LRCLIB: fix by hand'], error: ['badc', 'couldn\'t ask'] };
  function openFixAll() {
    var fx = { job: null, items: null, tick: {}, lyrics: true, saving: null, error: '' };
    var dim = document.createElement('div'); dim.className = 'dim';
    function job(id) { return st.jobs.filter(function (j) { return j.id === id; })[0]; }
    function changed(it) { return ['title', 'artist', 'album'].some(function (k) { return it.current[k] !== it.proposed[k]; }); }
    function render() {
      var body;
      if (fx.error) body = '<span class="err">' + esc(fx.error) + '</span>';
      else if (!fx.items) {
        var j = fx.job && job(fx.job);
        body = '<span class="muted">Asking LRCLIB about each song, a little slowly so it doesn\'t say "busy". Nothing is saved yet.</span>' +
          '<div class="bar"><i style="width:' + (j ? j.progress : 0) + '%"></i></div><span class="muted" id="fxMsg">' + esc(j ? j.message || 'waiting' : 'Starting…') + '</span>';
      } else {
        var todo = fx.items.filter(changed);
        body = '<span class="muted">' + fx.items.filter(function (x) { return x.status !== 'none' && x.status !== 'error'; }).length + ' of ' + fx.items.length + ' songs can be found by lyrics-plus. Ticked songs get the new tags when you press Save.</span>' +
          '<div class="list fixlist">' + fx.items.map(function (it, i) {
            var say = FIX_SAYS[it.status] || FIX_SAYS.none, ch = changed(it);
            var cur = esc(it.current.title || it.name) + ' · ' + esc(it.current.artist || 'no artist');
            var neu = esc(it.proposed.title) + ' · ' + esc(it.proposed.artist || 'no artist') + (it.proposed.album && it.proposed.album !== it.proposed.title ? ' · ' + esc(it.proposed.album) : '');
            return '<label class="item">' + (ch ? '<input type="checkbox" data-fx="' + i + '"' + (fx.tick[i] ? ' checked' : '') + '>' : '<span></span>') +
              '<div style="min-width:0"><b class="ell">' + (ch ? neu : cur) + '</b><span class="muted ell">' + (ch ? 'was: ' + cur : 'tags stay as they are') + '</span></div>' +
              '<span class="' + say[0] + '">' + say[1] + (it.synced ? ' · timed' : '') + '</span></label>';
          }).join('') + '</div>' +
          (todo.length ? '<label class="row nw"><input type="checkbox" id="fxLy"' + (fx.lyrics ? ' checked' : '') + '> <span>Also put the lyrics inside each saved song (for other players; lyrics-plus looks them up itself)</span></label>' : '') +
          '<div class="row"><button type="button" class="btn" id="fxSave"' + (todo.length && !fx.saving ? '' : ' disabled') + '>' + (fx.saving ? 'Saving…' : 'Save ticked (' + Object.keys(fx.tick).filter(function (k) { return fx.tick[k]; }).length + ')') + '</button>' +
          '<span class="muted" id="fxMsg"></span></div>';
      }
      dim.innerHTML = '<div class="dialog stack" role="dialog" aria-label="Fix all songs" style="width:min(720px,94vw)"><div class="row sb"><b>✨ Fix all songs for lyrics</b><button type="button" class="btn ghost sm" data-x>Close</button></div>' + body + '</div>';
      $$('[data-x]', dim).forEach(function (b) { b.onclick = close; });
      $$('[data-fx]', dim).forEach(function (b) { b.onchange = function () { fx.tick[b.getAttribute('data-fx')] = b.checked; var s = $('#fxSave', dim); if (s && !fx.saving) s.textContent = 'Save ticked (' + Object.keys(fx.tick).filter(function (k) { return fx.tick[k]; }).length + ')'; }; });
      var ly = $('#fxLy', dim); if (ly) ly.onchange = function () { fx.lyrics = ly.checked; };
      var sv = $('#fxSave', dim);
      if (sv) sv.onclick = function () {
        var pick = fx.items.filter(function (it, i) { return fx.tick[i] && changed(it); }).map(function (it) { return { path: it.path, title: it.proposed.title, artist: it.proposed.artist, album: it.proposed.album }; });
        if (!pick.length) { toast('Tick at least one song.'); return; }
        api('songs_fix_apply', pick, fx.lyrics).then(function (r) { if (!r.ok) { toast(r.message); return; } fx.saving = r.job; render(); }).catch(fail);
      };
    }
    var timer = setInterval(function () {
      if (fx.job && !fx.items) {
        var j = job(fx.job); if (!j) return;
        if (j.state === 'done') { fx.items = j.result || []; fx.items.forEach(function (it, i) { if (changed(it) && it.status !== 'none' && it.status !== 'error') fx.tick[i] = true; }); render(); }
        else if (j.state === 'failed' || j.state === 'cancelled') { fx.error = j.message || 'Stopped.'; render(); }
        else { var bar = $('.bar i', dim); if (bar) bar.style.width = j.progress + '%'; var msg = $('#fxMsg', dim); if (msg) msg.textContent = j.message || 'waiting'; }
      }
      if (fx.saving) {
        var k = job(fx.saving);
        if (k && k.state !== 'running' && k.state !== 'waiting') { toast(k.message); fx.saving = null; close(); loadSongs(); }
        else if (k) { var m2 = $('#fxMsg', dim); if (m2) m2.textContent = k.message || ''; }
      }
    }, 500);
    function close() {
      clearInterval(timer);
      if (fx.job && !fx.items) api('cancel_job', fx.job).catch(function () {});
      dim.remove();
    }
    render();
    $('#app').appendChild(dim);
    dim.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    api('songs_fix_all').then(function (r) { fx.job = r.job; pollJobs(); }).catch(function (e) { fx.error = e.message; render(); });
  }
  T.openFixAll = openFixAll;
  function openTags(path, startTab) {
    // The song dialog: Tags, the Cover editor (frame a square by moving and zooming), and Lyrics (14 Oct: his Spotify extras)
    var sg = (DL.songs && DL.songs.songs || []).filter(function (x) { return x.path === path; })[0] || { path: path, title: '', artist: '', album: '', name: path.split('\\').pop() };
    var tg = { title: sg.title, artist: sg.artist, album: sg.album, check: null, busy: false, seconds: sg.seconds || 0 };
    var tab = startTab || 'tags', cov = { token: '', data: '', W: 0, H: 0, s: 1, ox: 0, oy: 0, loaded: false, youtube: false }, ly = { plain: '', synced: '', has: false, lrc: false, status: '' };
    var dim = document.createElement('div'); dim.className = 'dim';
    var FRAME = 300;
    function paneTags() {
      var c = tg.check;
      return '<div class="row sb"><span class="muted">What Spotify shows, and what lyrics-plus searches lyrics by.</span><button type="button" class="btn ghost sm" id="tgFix">✨ Fix for lyrics</button></div>' +
        '<label class="lbl" for="tgTitle">Title</label><input class="field" id="tgTitle" value="' + esc(tg.title) + '">' +
        '<label class="lbl" for="tgArtist">Artist</label><input class="field" id="tgArtist" value="' + esc(tg.artist) + '">' +
        '<label class="lbl" for="tgAlbum">Album</label><input class="field" id="tgAlbum" value="' + esc(tg.album) + '">' +
        '<div class="card stack" style="gap:8px"><div class="row sb"><b>Will lyrics-plus find lyrics?</b><button type="button" class="btn ghost sm" id="tgCheck"' + (tg.busy ? ' disabled' : '') + '>' + (tg.busy ? 'Asking LRCLIB…' : 'Check with LRCLIB') + '</button></div>' +
        (c ? (c.ok === false ? '<span class="warnc">' + esc(c.message) + '</span>' : c.match ? '<span class="okc">✓ Yes: LRCLIB has lyrics for exactly these tags' + (c.synced ? ', with timing (they scroll along)' : '') + '. Romaji is a setting in lyrics-plus.</span>' :
          '<span class="warnc">✗ Not with these tags.</span>' + (c.candidates.length ? '<span class="muted">LRCLIB has these. Using one copies its title, artist and album into the fields above (Spotify then shows that artist). Lengths within 2 s of your song match.</span><div class="list">' + c.candidates.map(function (x, i) {
            return '<div class="item"><span class="' + (x.fits ? 'okc' : 'muted') + '">' + (x.fits ? '✓' : '·') + '</span><div style="min-width:0"><b class="ell">' + esc(x.title) + ' · ' + esc(x.artist) + '</b><span class="muted ell" style="display:block">' + esc(x.album) + ' · ' + fmtTime(x.duration) + (x.fits ? ' · same length' : ' · ' + x.diff + ' s off') + (x.synced ? ' · with timing' : '') + '</span></div><button type="button" class="btn ghost sm" data-cand="' + i + '">Use</button></div>';
          }).join('') + '</div>' : '<span class="muted">LRCLIB has no lyrics for this title at all. Musixmatch (the other source lyrics-plus asks) may still have them.</span>')) : '<span class="muted">Asks LRCLIB the same question lyrics-plus asks (title, artist, album, length).</span>') + '</div>' +
        '<span class="err" id="tgErr"></span>' +
        '<div class="row"><button type="button" class="btn" id="tgSave">Save</button><button type="button" class="btn ghost" data-x>Cancel</button></div>';
    }
    function paneCover() {
      return '<div class="row" style="align-items:flex-start"><div class="cov-frame" id="cvFrame" title="Drag to move, scroll to zoom">' + (cov.data ? '<img id="cvImg" src="' + cov.data + '" alt="" draggable="false">' : '<span class="muted">' + (cov.loaded ? 'No picture yet: pick one below.' : 'Loading…') + '</span>') + '</div>' +
        '<div class="stack grow" style="min-width:0"><span class="muted">Spotify shows a square. Move the picture inside the frame and zoom until it looks right.</span>' +
        '<div class="row nw"><label class="muted" for="cvZoom">Zoom</label><input id="cvZoom" type="range" min="100" max="400" value="100" class="grow" aria-label="Zoom"' + (cov.data ? '' : ' disabled') + '></div>' +
        '<span class="lbl">Picture from</span><div class="row"><button type="button" class="btn ghost sm" id="cvYt"' + (cov.youtube ? '' : ' disabled title="This song doesn\'t remember its video"') + '>YouTube</button><button type="button" class="btn ghost sm" id="cvFile">My own picture</button><button type="button" class="btn ghost sm" id="cvLinkBtn">A link</button></div>' +
        '<div class="row nw" id="cvLinkRow" hidden><input class="field grow" id="cvLink" placeholder="https://… a picture" aria-label="Picture link"><button type="button" class="btn sm" id="cvLinkGo">Fetch</button></div>' +
        '<span class="err" id="cvErr"></span><div class="row"><button type="button" class="btn" id="cvSave"' + (cov.data ? '' : ' disabled') + '>Save cover</button><button type="button" class="btn ghost" data-x>Close</button></div></div></div>';
    }
    function paneLyrics() {
      return '<div class="row sb"><span class="muted">' + (ly.has ? 'This song has lyrics inside it' + (ly.lrc ? ' and a .lrc with the timing' : '') + '.' : 'No lyrics in this song yet.') + '</span><button type="button" class="btn ghost sm" id="lyFind">Find lyrics (LRCLIB)</button></div>' +
        '<textarea class="field lyrics" id="lyText" placeholder="Paste or type the lyrics, or press Find" aria-label="Lyrics">' + esc(ly.plain) + '</textarea>' +
        '<span class="muted" id="lyStatus">' + esc(ly.status) + '</span>' +
        '<span class="muted">These are saved inside the song for players that read them (and a .lrc next to it' + (ly.synced ? ', with the timing' : ' when there is timing') + '). Spicetify\'s lyrics-plus does not read them: it looks lyrics up online by the song\'s tags. For Spotify, use Tags → ✨ Fix for lyrics.</span>' +
        (ly.ttml ? '<div class="card stack" id="lySpicy" style="gap:6px"><div class="row sb"><b>Spicy Lyrics</b><button type="button" class="btn ghost sm" id="lyTtml">Show the .ttml</button></div><span class="muted">Spicy Lyrics doesn’t look up local songs online; it takes this file once per song. In Spotify: play the song, open Spicy Lyrics, click <b>Lyrics Manager</b> (in its buttons), then <b>Upload</b>, choose <b>Save</b> and pick the .ttml. If you change the song’s tags later, import it again (Spotify then sees it as a new song).</span></div>' : '') +
        '<span class="err" id="lyErr"></span><div class="row"><button type="button" class="btn" id="lySave">Save lyrics</button><button type="button" class="btn ghost sm" id="lyClear">Remove</button><button type="button" class="btn ghost" data-x>Close</button></div>';
    }
    function render() {
      dim.innerHTML = '<div class="dialog wide" role="dialog" aria-modal="true" aria-labelledby="tagT"><div class="row sb"><h3 class="h" id="tagT">Song</h3><button type="button" class="ico" data-x aria-label="Close">✕</button></div>' +
        '<span class="muted ell">' + esc(sg.name || '') + '</span>' +
        '<div class="tabs" role="tablist">' + [['tags', 'Tags'], ['cover', 'Cover'], ['lyrics', 'Lyrics']].map(function (t) { return '<button type="button" class="chip" role="tab" data-stab="' + t[0] + '" aria-pressed="' + (tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>' +
        (tab === 'tags' ? paneTags() : tab === 'cover' ? paneCover() : paneLyrics()) + '</div>';
      wire();
    }
    function fit() {
      var img = $('#cvImg', dim); if (!img || !cov.W) return;
      var minS = FRAME / Math.min(cov.W, cov.H);
      cov.s = Math.max(cov.s, minS);
      cov.ox = Math.min(0, Math.max(FRAME - cov.W * cov.s, cov.ox));
      cov.oy = Math.min(0, Math.max(FRAME - cov.H * cov.s, cov.oy));
      img.style.width = (cov.W * cov.s) + 'px'; img.style.height = (cov.H * cov.s) + 'px';
      img.style.transform = 'translate(' + cov.ox + 'px,' + cov.oy + 'px)';
      var z = $('#cvZoom', dim); if (z) z.value = Math.round(cov.s / minS * 100);
    }
    function setPicture(r) {
      cov.token = r.token; cov.data = r.data; cov.W = r.width || cov.W; cov.H = r.height || cov.H;
      var probe = new Image();
      probe.onload = function () { cov.W = probe.naturalWidth; cov.H = probe.naturalHeight; cov.s = FRAME / Math.min(cov.W, cov.H); cov.ox = (FRAME - cov.W * cov.s) / 2; cov.oy = (FRAME - cov.H * cov.s) / 2; render(); fit(); };
      probe.src = r.data;
    }
    function crop() { return { x: Math.round(-cov.ox / cov.s), y: Math.round(-cov.oy / cov.s), w: Math.round(FRAME / cov.s) }; }
    function wire() {
      $$('[data-x]', dim).forEach(function (b) { b.onclick = function () { dim.remove(); }; });
      $$('[data-stab]', dim).forEach(function (b) { b.onclick = function () { tab = b.getAttribute('data-stab'); render(); }; });
      var ts = $('#tgSave', dim);
      if (ts) {
        [['tgTitle', 'title'], ['tgArtist', 'artist'], ['tgAlbum', 'album']].forEach(function (f) { var el = $('#' + f[0], dim); el.oninput = function () { tg[f[1]] = el.value; tg.check = null; }; });
        $('#tgFix', dim).onclick = function () {
          api('song_suggest_tags', path).then(function (r) { if (!r.ok) { $('#tgErr', dim).textContent = r.message; return; } tg.title = r.suggested.title; tg.artist = r.suggested.artist; tg.album = r.suggested.album; tg.seconds = r.seconds; tg.check = null; render(); toast('Cleaned up. Check with LRCLIB, then Save.'); }).catch(fail);
        };
        $('#tgCheck', dim).onclick = function () {
          tg.busy = true; render();
          api('song_lrclib_check', tg.title, tg.artist, tg.album, tg.seconds).then(function (r) { tg.busy = false; tg.check = r; render(); }).catch(function (e) { tg.busy = false; tg.check = { ok: false, message: e.message }; render(); });
        };
        $$('[data-cand]', dim).forEach(function (b) { b.onclick = function () { var x = tg.check.candidates[+b.getAttribute('data-cand')]; tg.title = x.title; tg.artist = x.artist; tg.album = x.album; tg.check = { ok: true, match: x.fits, synced: x.synced, candidates: [] }; render(); }; });
        $('#tgTitle', dim).focus();
        ts.onclick = function () {
          ts.disabled = true;
          api('write_tags', path, { title: tg.title, artist: tg.artist, album: tg.album }).then(function (r) {
            ts.disabled = false;
            if (!r.ok) { $('#tgErr', dim).textContent = r.message; return; }
            dim.remove(); toast(r.message); loadSongs();
          }).catch(function (e) { ts.disabled = false; $('#tgErr', dim).textContent = e.message; });
        };
      }
      var frame = $('#cvFrame', dim);
      if (frame) {
        if (!cov.loaded) { cov.loaded = true; api('song_cover', path).then(function (r) { if (!r.ok) { $('#cvErr', dim).textContent = r.message; return; } cov.youtube = r.youtube; ly.has = r.lyrics; ly.lrc = r.lrc; ly.ttml = r.ttml || ''; ly.plain = r.lyrics_text || ''; if (r.data) setPicture(r); else render(); }).catch(fail); }
        fit();
        var drag = null;
        frame.onmousedown = function (e) { if (!cov.data) return; drag = [e.clientX, e.clientY, cov.ox, cov.oy]; e.preventDefault(); };
        frame.onmousemove = function (e) { if (!drag) return; cov.ox = drag[2] + e.clientX - drag[0]; cov.oy = drag[3] + e.clientY - drag[1]; fit(); };
        frame.onmouseup = frame.onmouseleave = function () { drag = null; };
        frame.onwheel = function (e) { if (!cov.data) return; e.preventDefault(); zoomAt(e.deltaY < 0 ? 1.1 : 1 / 1.1, FRAME / 2, FRAME / 2); };
        function zoomAt(f, cx, cy) { var s2 = cov.s * f; cov.ox = cx - (cx - cov.ox) * (s2 / cov.s); cov.oy = cy - (cy - cov.oy) * (s2 / cov.s); cov.s = s2; fit(); }
        var z = $('#cvZoom', dim); if (z) z.oninput = function () { var minS = FRAME / Math.min(cov.W, cov.H), s2 = minS * (+z.value / 100); cov.ox = FRAME / 2 - (FRAME / 2 - cov.ox) * (s2 / cov.s); cov.oy = FRAME / 2 - (FRAME / 2 - cov.oy) * (s2 / cov.s); cov.s = s2; fit(); };
        function take(source, url) { $('#cvErr', dim).textContent = ''; api('song_cover_from', path, source, url || '').then(function (r) { if (!r.ok) { if (r.message) $('#cvErr', dim).textContent = r.message; return; } setPicture(r); }).catch(function (e) { $('#cvErr', dim).textContent = e.message; }); }
        var yt = $('#cvYt', dim); if (yt) yt.onclick = function () { take('youtube'); };
        $('#cvFile', dim).onclick = function () { take('file'); };
        $('#cvLinkBtn', dim).onclick = function () { var row = $('#cvLinkRow', dim); row.hidden = !row.hidden; if (!row.hidden) $('#cvLink', dim).focus(); };
        $('#cvLinkGo', dim).onclick = function () { take('link', $('#cvLink', dim).value.trim()); };
        $('#cvLink', dim).onkeydown = function (e) { if (e.key === 'Enter') $('#cvLinkGo', dim).click(); };
        var sv = $('#cvSave', dim);
        sv.onclick = function () {
          sv.disabled = true;
          api('song_cover_save', path, cov.token, crop()).then(function (r) { sv.disabled = false; if (!r.ok) { $('#cvErr', dim).textContent = r.message; return; } toast(r.message); loadSongs(); }).catch(function (e) { sv.disabled = false; $('#cvErr', dim).textContent = e.message; });
        };
      }
      var lt = $('#lyText', dim);
      if (lt) {
        if (!cov.loaded) { cov.loaded = true; api('song_cover', path).then(function (r) { if (!r.ok) return; cov.youtube = r.youtube; ly.has = r.lyrics; ly.lrc = r.lrc; ly.ttml = r.ttml || ''; ly.plain = r.lyrics_text || ''; if (r.data) { cov.token = r.token; cov.data = r.data; } render(); }).catch(fail); }
        lt.oninput = function () { ly.plain = lt.value; };
        $('#lyFind', dim).onclick = function () {
          var b = this; b.disabled = true; $('#lyStatus', dim).textContent = 'Asking LRCLIB…';
          api('song_lyrics_find', path).then(function (r) {
            b.disabled = false;
            if (!r.ok) { $('#lyStatus', dim).textContent = ''; $('#lyErr', dim).textContent = r.message; return; }
            $('#lyErr', dim).textContent = '';
            ly.plain = r.plain || (r.instrumental ? '' : lt.value); ly.synced = r.synced || ''; lt.value = ly.plain;
            ly.status = 'Found: ' + r.found + (r.synced ? ' · with timing' : ' · words only') + (r.instrumental ? ' · instrumental' : '') + (r.matches > 1 ? ' · ' + r.matches + ' matches, best picked' : '');
            $('#lyStatus', dim).textContent = ly.status;
          }).catch(function (e) { b.disabled = false; $('#lyErr', dim).textContent = e.message; });
        };
        $('#lySave', dim).onclick = function () {
          var b = this; b.disabled = true;
          api('song_lyrics_save', path, lt.value, ly.synced).then(function (r) { b.disabled = false; if (!r.ok) { $('#lyErr', dim).textContent = r.message; return; } ly.has = !!lt.value.trim(); ly.lrc = !!ly.synced; ly.ttml = ly.synced && ly.has ? path.replace(/\.mp3$/i, '.ttml') : ''; toast(r.message); loadSongs(); render(); }).catch(function (e) { b.disabled = false; $('#lyErr', dim).textContent = e.message; });
        };
        var tt = $('#lyTtml', dim); if (tt) tt.onclick = function () { api('show_file', ly.ttml).then(function (r) { if (!r.ok) toast(r.message); }).catch(fail); };
        $('#lyClear', dim).onclick = function () { lt.value = ''; ly.plain = ''; ly.synced = ''; $('#lySave', dim).click(); };
      }
    }
    render();
    $('#app').appendChild(dim);
    dim.addEventListener('keydown', function (e) { if (e.key === 'Escape') dim.remove(); });
  }

  // ---------- step 3: cut-outs ----------
  var CUT = { job: null, token: null, before: '', after: '', opts: null, info: null, error: '', recent: [] };
  var BGS = [['none', 'See-through'], ['white', 'White'], ['colour', 'Colour'], ['blur', 'Blur the background'], ['picture', 'Picture…']];
  function cutModel() { return st.engines ? st.engines.engines.filter(function (x) { return x.id === 'birefnet'; })[0] : null; }
  VIEWS.bg = function () {
    var model = cutModel(), installing = st.jobs.filter(function (j) { return j.kind === 'Engine' && j.extra && j.extra.engine === 'birefnet' && (j.state === 'running' || j.state === 'waiting'); })[0];
    var head = '<div class="row sb"><h2 class="h">Cut out</h2><div class="row"><span class="tag">pictures never leave this PC</span>' + (CUT.info ? '<span class="tag ok">' + CUT.info.seconds + ' s on the ' + esc(CUT.info.device) + '</span>' : '') + '</div></div>';
    if (model && (!model.installed || installing)) {
      return head + '<div class="card stack"><b>Cut-outs need the BiRefNet model first</b><span class="muted">928 MB, free for anything (MIT licence), from the official BiRefNet project, checked against the fingerprint rembg publishes. It runs on your graphics card and stays in your AppData.</span>' +
        (installing ? '<div class="bar run"><i style="width:' + installing.progress + '%"></i></div><span class="muted">' + Math.round(installing.progress) + '% · ' + esc(installing.message || 'waiting') + '</span>' : '<div class="row"><button type="button" class="btn" id="cutInstall">Install it</button></div>') + '</div>';
    }
    return head + '<div class="card drop stack" id="cutDrop"><b>Drop a picture here, or press Ctrl+V</b><span class="muted">A screenshot from Snipper works too. PNG, JPG, WebP, BMP, GIF or TIFF.</span>' +
      '<div class="row"><button type="button" class="btn" id="cutOpen">Open a picture…</button><button type="button" class="btn ghost" id="cutPaste">Paste (Ctrl+V)</button></div>' + (CUT.error ? '<span class="err">' + esc(CUT.error) + '</span>' : '') + '</div>' +
      '<div id="cutWork"></div><div id="cutResult"></div>' +
      (CUT.recent.length ? '<h3 class="h">Earlier this session</h3><div class="strip" id="cutRecent">' + CUT.recent.map(function (r) { return '<button type="button" class="checker" data-recent="' + r.token + '" title="' + esc(r.name) + '"><img src="' + r.after + '" alt="' + esc(r.name) + '"></button>'; }).join('') + '</div>' : '');
  };
  function cutStart(promise) {
    CUT.error = '';
    promise.then(function (r) {
      if (!r.ok) { if (r.message) { CUT.error = r.message; if (st.screen === 'bg') go('bg', true); } return; }
      CUT.job = r.id; CUT.token = r.token; CUT.before = r.before; CUT.after = ''; CUT.opts = null; CUT.info = null;
      if (st.screen === 'bg') go('bg', true);
      pollJobs();
    }).catch(fail);
  }
  function renderCut() {
    var m = $('#screen'); if (st.screen !== 'bg') return;
    var work = $('#cutWork', m), res = $('#cutResult', m); if (!work) return;
    var job = st.jobs.filter(function (j) { return j.id === CUT.job; })[0];
    if (job && (job.state === 'running' || job.state === 'waiting')) {
      work.innerHTML = '<div class="card row nw"><img class="thumbimg" src="' + CUT.before + '" alt=""><div class="stack grow"><b>' + esc(job.title) + '</b><div class="bar run"><i style="width:' + job.progress + '%"></i></div><span class="muted">' + esc(job.message || 'Waiting') + '</span></div></div>';
      res.innerHTML = '';
      return;
    }
    work.innerHTML = '';
    if (job && job.state === 'failed' && CUT.job) { CUT.error = job.message; CUT.job = null; go('bg', true); return; }
    if (job && job.state === 'done' && !CUT.after && !CUT.loading) {
      CUT.loading = true;
      api('cut_result', CUT.token).then(function (r) {
        CUT.loading = false;
        if (!r.ok) { CUT.error = r.message; go('bg', true); return; }
        CUT.after = r.after; CUT.opts = r.options; CUT.info = { seconds: r.seconds, device: r.device, size: r.width + ' × ' + r.height, name: r.name };
        CUT.recent = [{ token: r.token, name: r.name, after: r.after }].concat(CUT.recent.filter(function (x) { return x.token !== r.token; })).slice(0, 8);
        go('bg', true);
      }).catch(function (e) { CUT.loading = false; fail(e); });
    }
    if (CUT.after && !res.firstChild) res.innerHTML = resultHtml(), wireResult(m);
  }
  function resultHtml() {
    var o = CUT.opts || { bg: 'none', colour: '#FFFFFF', outline: 0, shadow: false };
    return '<div class="cols"><div class="stack"><div class="ba" id="cutBa" style="--cut:50%;aspect-ratio:' + CUT.info.size.replace(' × ', ' / ') + '">' +
      '<div class="ba-layer"><img src="' + CUT.before + '" alt="Before"></div><div class="ba-layer ba-after checker"><img id="cutAfter" src="' + CUT.after + '" alt="After"></div>' +
      '<span class="ba-line"></span><input type="range" class="ba-range" min="0" max="100" value="50" aria-label="Slide between before and after"><span class="ba-tag l">Before</span><span class="ba-tag r">After</span></div>' +
      '<span class="muted">' + esc(CUT.info.name) + ' · ' + CUT.info.size + ' · drag the line to compare</span></div>' +
      '<div class="stack"><div class="card stack"><b>Background</b><div class="row" id="cutBgs">' + BGS.map(function (b) { return '<button type="button" class="chip" data-bg="' + b[0] + '" aria-pressed="' + (o.bg === b[0]) + '">' + b[1] + '</button>'; }).join('') + '</div>' +
      (o.bg === 'colour' ? '<div class="row"><input type="color" id="cutColour" value="' + esc(o.colour.toLowerCase()) + '" aria-label="Background colour"><span class="muted">' + esc(o.colour) + '</span></div>' : '') +
      (o.bg === 'none' ? '<b>Sticker</b><div class="row nw"><label class="muted" for="cutOutline">White outline</label><input type="range" id="cutOutline" min="0" max="30" value="' + o.outline + '" class="grow"><span class="muted" id="cutOutlineV">' + (o.outline ? o.outline + ' px' : 'off') + '</span></div>' +
        '<div class="row nw">' + sw('cutShadow', o.shadow, 'Shadow') + '<span>Shadow</span></div>' : '') + '</div>' +
      '<div class="card stack"><b>Save it</b><div class="row"><button type="button" class="btn" id="cutSave">Save PNG</button><button type="button" class="btn ghost" id="cutCopy">Copy (Ctrl+C)</button></div>' +
      '<span class="muted">Copying keeps the see-through edges, so it pastes clean into Discord.</span></div>' +
      '<div class="card stack"><b>For Discord</b><div class="row"><button type="button" class="btn ghost sm" data-dc="emoji">Copy emoji 128</button><button type="button" class="btn ghost sm" data-dc="sticker">Copy sticker 320</button><button type="button" class="btn ghost sm" data-dc="icon">Copy server icon 512</button></div>' +
      '<div class="row"><button type="button" class="btn sm" id="cutDiscord">Save all three</button><span class="muted">kept under Discord\'s size limits</span></div></div></div></div>';
  }
  function cutApply(opts) {
    api('cut_set', CUT.token, opts).then(function (r) {
      if (!r.ok) { toast(r.message); return; }
      CUT.after = r.after; CUT.opts = r.options;
      var m = $('#screen'), res = $('#cutResult', m); if (res) { res.innerHTML = resultHtml(); wireResult(m); }
    }).catch(fail);
  }
  function wireResult(m) {
    var r = $('#cutBa', m); if (!r) return;
    $('.ba-range', r).addEventListener('input', function () { r.style.setProperty('--cut', this.value + '%'); });
    $$('[data-bg]', m).forEach(function (b) {
      b.onclick = function () {
        var bg = b.getAttribute('data-bg');
        if (bg === 'picture') { api('cut_background_picture', CUT.token).then(function (res) { if (res.ok) { CUT.after = res.after; CUT.opts = res.options; var box = $('#cutResult', m); box.innerHTML = resultHtml(); wireResult(m); } else if (res.message) toast(res.message); }).catch(fail); }
        else cutApply({ bg: bg });
      };
    });
    var col = $('#cutColour', m); if (col) col.addEventListener('change', function () { cutApply({ colour: col.value.toUpperCase() }); });
    var ol = $('#cutOutline', m);
    if (ol) {
      ol.addEventListener('input', function () { $('#cutOutlineV', m).textContent = +ol.value ? ol.value + ' px' : 'off'; });
      ol.addEventListener('change', function () { cutApply({ outline: +ol.value }); });
    }
    var sh = $('#cutShadow', m); if (sh) sh.onclick = function () { var on = sh.getAttribute('aria-checked') !== 'true'; sh.setAttribute('aria-checked', String(on)); cutApply({ shadow: on }); };
    $('#cutSave', m).onclick = function () { api('cut_save', CUT.token).then(function (res) { toast(res.message); }).catch(fail); };
    $('#cutCopy', m).onclick = function () { api('cut_copy', CUT.token).then(function (res) { toast(res.message); }).catch(fail); };
    $$('[data-dc]', m).forEach(function (b) { b.onclick = function () { api('cut_copy', CUT.token, b.getAttribute('data-dc')).then(function (res) { toast(res.message); }).catch(fail); }; });
    $('#cutDiscord', m).onclick = function () { api('cut_discord', CUT.token).then(function (res) { toast(res.message); }).catch(fail); };
  }
  WIRE.bg = function (m) {
    var inst = $('#cutInstall', m);
    if (inst) inst.onclick = function () { inst.disabled = true; api('install_engines', ['birefnet']).then(function (r) { toast(r.message); pollJobs(); }).catch(fail); };
    var open = $('#cutOpen', m); if (open) open.onclick = function () { cutStart(api('cut_pick')); };
    var paste = $('#cutPaste', m); if (paste) paste.onclick = function () { cutStart(api('cut_paste')); };
    $$('[data-recent]', m).forEach(function (b) {
      b.onclick = function () {
        var token = b.getAttribute('data-recent');
        api('cut_result', token).then(function (r) {
          if (!r.ok) { toast(r.message); return; }
          CUT.job = null; CUT.token = token; CUT.before = r.before; CUT.after = r.after; CUT.opts = r.options;
          CUT.info = { seconds: r.seconds, device: r.device, size: r.width + ' × ' + r.height, name: r.name };
          go('bg', true);
        }).catch(fail);
      };
    });
    renderCut();
  };
  function dropPicture(file) {
    if (!file || !/^image\//.test(file.type)) { toast('That isn\'t a picture.'); return; }
    if (file.size > 60 * 1024 * 1024) { toast('That picture is bigger than 60 MB.'); return; }
    var reader = new FileReader();
    reader.onload = function () { go('bg'); cutStart(api('cut_data', file.name, reader.result)); };
    reader.readAsDataURL(file);
  }
  // dropping a file anywhere must never make the window open the file itself
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) {
    e.preventDefault();
    var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (!f) return;
    var full = f.pywebviewFullPath;                            // pywebview adds the real path of a dropped file
    if (st.screen === 'bg' && /^image\//.test(f.type)) { dropPicture(f); return; }
    if (full && st.screen === 'check') { ckTake(api('media_drop', full), CK.tab === 'compare' && CK.file && !CK.other ? 'other' : 'file'); return; }
    if (full) { mediaTake(api('media_drop', full), true); return; }
    if (/^image\//.test(f.type)) dropPicture(f);
    else toast('Use "Pick a file" on Media for this one.');
  });
  document.addEventListener('keydown', function (e) {
    if (st.screen !== 'bg' || !(e.ctrlKey || e.metaKey) || e.altKey) return;
    var typing = /^(INPUT|TEXTAREA)$/.test((document.activeElement || {}).tagName || '');
    if (e.key.toLowerCase() === 'v' && !typing) { e.preventDefault(); cutStart(api('cut_paste')); }
    if (e.key.toLowerCase() === 'c' && !typing && CUT.after && !String(window.getSelection())) { e.preventDefault(); api('cut_copy', CUT.token).then(function (r) { toast(r.message); }).catch(fail); }
  });

  // the bar at the top: paste or type a link, and it opens Download with it looked up
  var omni = $('#omni');
  function omniGo() {
    var v = omni.value.trim(); if (!v) return;
    omni.value = ''; omni.blur(); go('video'); lookUp(v);
  }
  omni.addEventListener('keydown', function (e) { if (e.key === 'Enter') omniGo(); });
  omni.addEventListener('paste', function () { setTimeout(function () { if (/youtu\.?be/i.test(omni.value)) omniGo(); }, 0); });

  // copied links: offered once, on any screen
  function pollClipboard() {
    api('clipboard_offer').then(function (offer) {
      if (!offer || !offer.url) return;
      var old = $('#toast'); if (old) old.remove();
      clearTimeout(toastTimer);
      var t = document.createElement('div'); t.className = 'toast'; t.id = 'toast'; t.setAttribute('role', 'status');
      t.innerHTML = '<span class="badge" style="width:26px;height:26px;font-size:12px">↓</span><div class="stack" style="gap:6px;min-width:0"><b>You copied a video link</b><span class="muted ell">' + esc(offer.url) + '</span>' +
        '<div class="row"><button type="button" class="btn sm" data-o="look">Download it…</button><button type="button" class="btn ghost sm" data-o="no">Not now</button></div></div>';
      $('#app').appendChild(t);
      $('[data-o="look"]', t).onclick = function () { t.remove(); go('video'); lookUp(offer.url); };
      $('[data-o="no"]', t).onclick = function () { t.remove(); };
      toastTimer = setTimeout(function () { t.remove(); }, 12000);
    }).catch(function () {});
  }

  // ---------- step 5: Colours (carried over from the approved prototype) ----------
  var COL = { tab: 'grad', loaded: false, saved: [], pal: [], palBase: '#FF5C8A', palMode: 0, hex: '#FFCF3F', cA: '#FFF8E7', cB: '#3A3480',
    grad: { stops: ['#FF5F6D', '#FFC371'], fmt: 'sk', b: true, i: false, u: false, s: false, k: false, sh: false, shc: '#3A0A2A', sha: 60, text: 'Demo world' } };
  var CTABS = [['grad', 'Gradient text'], ['codes', 'Colour codes'], ['pal', 'Palettes'], ['saved', 'Saved']];
  var PRESETS = [['Sunset', ['#FF5F6D', '#FFC371']], ['Ocean', ['#2AF5FF', '#3D7BFF', '#7B3DFF']], ['Fire', ['#FFE53B', '#FF8C1A', '#FF2525']], ['Toxic', ['#B6FF3B', '#28D17C']],
    ['Rainbow', ['#FF3B3B', '#FFB13B', '#FFF03B', '#3BFF6B', '#3BB3FF', '#B53BFF']], ['Pastel', ['#FFB3C6', '#C3B3FF', '#B3F0FF']], ['Gold', ['#FFD86B', '#FF8A3D']]];
  T.openColour = function (hx) { COL.hex = hx; COL.tab = 'codes'; go('color'); };
  function hexRgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
  function rgbHex(c) { return '#' + c.map(function (v) { return ('0' + Math.max(0, Math.min(255, Math.round(v))).toString(16)).slice(-2); }).join('').toUpperCase(); }
  function hsl2hex(h, s, l) {
    s /= 100; l /= 100; var k = function (n) { return (n + h / 30) % 12; }, a = s * Math.min(l, 1 - l);
    var f = function (n) { return l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1))); };
    return rgbHex([f(0) * 255, f(8) * 255, f(4) * 255]);
  }
  function hex2hsl(hx) {
    var c = hexRgb(hx), r = c[0] / 255, g = c[1] / 255, b = c[2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, s = 0, h = 0, d = mx - mn;
    if (d) { s = d / (1 - Math.abs(2 * l - 1)); h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; if (h < 0) h += 360; }
    return [Math.round(h), Math.round(s * 100), Math.round(l * 100)];
  }
  function at(stops, t) {
    var cs = stops.map(hexRgb), seg = (cs.length - 1) * t, i = Math.min(Math.floor(seg), cs.length - 2), f = seg - i, a = cs[i], b = cs[i + 1];
    return rgbHex([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]).toLowerCase();
  }
  // Every format's code for a gradient; the rules are the prototype's, which he approved (13 Oct).
  function gradientCode(g) {
    var text = g.text || ' ', chars = Array.from(text), n = chars.length;
    var hexes = chars.map(function (c, i) { return at(g.stops, n > 1 ? i / (n - 1) : 0); });
    var shc = hexRgb(g.shc), sha = g.sha / 100, codes = (g.b ? '&l' : '') + (g.i ? '&o' : '') + (g.u ? '&n' : '') + (g.s ? '&m' : '') + (g.k ? '&k' : ''), out, note;
    if (g.fmt === 'mm') {
      var open = (g.b ? '<b>' : '') + (g.i ? '<i>' : '') + (g.u ? '<u>' : '') + (g.s ? '<st>' : '') + (g.k ? '<obf>' : '') + (g.sh ? '<shadow:' + g.shc + ':' + sha.toFixed(2) + '>' : '');
      var close = (g.sh ? '</shadow>' : '') + (g.k ? '</obf>' : '') + (g.s ? '</st>' : '') + (g.u ? '</u>' : '') + (g.i ? '</i>' : '') + (g.b ? '</b>' : '');
      out = open + '<gradient:' + g.stops.join(':') + '>' + text + '</gradient>' + close;
      note = 'MiniMessage: for Paper servers and plugins that use it.' + (g.sh ? ' Shadow needs Minecraft 1.21.4+.' : '');
    } else if (g.fmt === 'json') {
      var shInt = g.sh ? ((Math.round(sha * 255) << 24) | (shc[0] << 16) | (shc[1] << 8) | shc[2]) : null;
      out = JSON.stringify([''].concat(chars.map(function (c, i) {
        var o = { text: c }; if (c !== ' ') o.color = hexes[i];
        if (g.b) o.bold = true; if (g.i) o.italic = true; if (g.u) o.underlined = true; if (g.s) o.strikethrough = true; if (g.k) o.obfuscated = true;
        if (shInt !== null) o.shadow_color = shInt;
        return o;
      })));
      note = 'For /tellraw, signs and books.' + (g.sh ? ' shadow_color needs Minecraft 1.21.4+.' : '');
    } else {
      out = chars.map(function (c, i) {
        if (c === ' ') return ' ';
        var h = hexes[i], code = g.fmt === 'amp' ? '&' + h : g.fmt === 'sk' ? '<#' + h + '>' : '&x' + h.slice(1).split('').map(function (d) { return '&' + d; }).join('');
        return code + codes + c;
      }).join('');
      note = (g.fmt === 'amp' ? 'For EssentialsX and most plugins.' : g.fmt === 'sk' ? 'For Skript, used on Minecraft servers.' : 'For old Spigot plugins.') + (g.sh ? ' This format has no custom shadow: switch to MiniMessage or JSON for that.' : '');
    }
    return { out: out, note: note, hexes: hexes, chars: chars };
  }
  T.gradientCode = gradientCode;                                   // for the tests
  function copyText(text, el, label) {
    api('copy_text', text).then(function (r) {
      if (!r.ok) { toast(r.message); return; }
      if (el) { el.textContent = 'Copied ✓'; setTimeout(function () { el.textContent = label; }, 1200); } else toast('Copied ' + text);
    }).catch(fail);
  }
  function colTabs() { return '<div class="tabs" role="tablist">' + CTABS.map(function (t) { return '<button type="button" class="chip" role="tab" data-ctab="' + t[0] + '" aria-pressed="' + (COL.tab === t[0]) + '">' + t[1] + '</button>'; }).join('') + '</div>'; }
  VIEWS.color = function () {
    if (!COL.loaded) {
      COL.loaded = true;
      api('colours').then(function (d) {
        COL.saved = d.saved || [];
        if (d.last && Array.isArray(d.last.stops) && d.last.stops.length >= 2) Object.keys(d.last).forEach(function (k) { COL.grad[k] = d.last[k]; });
        if (st.screen === 'color') go('color', true);
      }).catch(function () {});
    }
    var g = COL.grad, body = '';
    if (COL.tab === 'grad') {
      body = '<div class="cols"><div class="card stack"><input class="field" id="grText" value="' + esc(g.text) + '" maxlength="80" aria-label="Text">' +
        '<div class="mc" id="grPrev"></div><div class="gbar" id="gbar"></div>' +
        '<div class="row" id="grFmt">' + [['&#rrggbb', 'amp'], ['MiniMessage', 'mm'], ['Skript', 'sk'], ['&x (old Spigot)', 'x'], ['tellraw JSON', 'json']].map(function (f) { return '<button type="button" class="chip" data-fmt="' + f[1] + '" aria-pressed="' + (g.fmt === f[1]) + '">' + esc(f[0]) + '</button>'; }).join('') + '</div>' +
        '<span class="muted" id="fmtNote"></span><textarea class="out" id="grOut" readonly aria-label="Code to copy"></textarea>' +
        '<div class="row sb"><span class="muted" id="grCount"></span><div class="row"><button type="button" class="btn ghost sm" id="grSave">☆ Save</button><button type="button" class="btn" id="grCopy">Copy code</button></div></div></div>' +
        '<div class="stack"><div class="card stack"><div class="row sb"><b>Colours</b><div class="row"><button type="button" class="btn ghost sm" id="grRev">⇄ Reverse</button><button type="button" class="btn ghost sm" id="grAdd">+ Add</button></div></div><div class="stops" id="stops"></div>' +
        '<span class="lbl">Presets</span><div class="row">' + PRESETS.map(function (p, i) { return '<button type="button" class="chip preset" data-preset="' + i + '" style="background-image:linear-gradient(90deg,' + p[1].join(',') + ')">' + p[0] + '</button>'; }).join('') + '</div></div>' +
        '<div class="card stack"><b>Style</b><div class="row" id="grStyle">' + [['b', '<b>B</b> Bold'], ['i', '<i>I</i> Italic'], ['u', '<u>U</u> Underline'], ['s', '<s>S</s> Strike'], ['k', '?! Obfuscated']].map(function (s) { return '<button type="button" class="chip" data-st="' + s[0] + '" aria-pressed="' + !!g[s[0]] + '">' + s[1] + '</button>'; }).join('') + '</div>' +
        '<b>Text shadow</b><div class="row nw">' + sw('shOn', g.sh, 'Custom shadow colour') + '<span>Custom shadow colour</span></div>' +
        '<div class="row"><input type="color" id="shC" value="' + esc(g.shc.toLowerCase()) + '" aria-label="Shadow colour"><label class="muted" for="shA">Strength</label><input id="shA" type="range" min="0" max="100" value="' + g.sha + '" class="grow"><span class="muted" id="shAv">' + g.sha + '%</span></div>' +
        '<span class="muted">Off = Minecraft\'s normal dark shadow. A custom colour works in MiniMessage and JSON on Minecraft 1.21.4+.</span></div></div></div>';
    } else if (COL.tab === 'codes') {
      body = '<div class="cols"><div class="card stack"><h3 class="h">One colour, every format</h3><div class="row nw"><input type="color" id="hxPick" value="' + COL.hex.toLowerCase() + '" aria-label="Pick a colour"><input class="field" id="hxIn" value="' + COL.hex + '" maxlength="7" aria-label="Hex code"></div>' +
        '<div class="list" id="hxRows"></div><span class="lbl">Shades (click to use)</span><div class="row" id="hxShades"></div></div>' +
        '<div class="card stack"><h3 class="h">Can you read it?</h3><div class="row"><span class="muted">Text</span><input type="color" id="cA" value="' + COL.cA.toLowerCase() + '" aria-label="Text colour"><span class="muted">on</span><input type="color" id="cB" value="' + COL.cB.toLowerCase() + '" aria-label="Background colour"></div>' +
        '<div class="contrast" id="cPrev">The quick brown fox · 123</div><b id="cRatio"></b><span class="muted" id="cVerdict"></span></div></div>';
    } else if (COL.tab === 'pal') {
      body = '<div class="card stack"><div class="row"><input type="color" id="pBase" value="' + COL.palBase.toLowerCase() + '" aria-label="Base colour"><div class="row" id="harm">' +
        ['Complementary', 'Analogous', 'Triadic', 'Shades', 'Tints'].map(function (n, i) { return '<button type="button" class="chip" data-harm="' + i + '" aria-pressed="' + (COL.palMode === i) + '">' + n + '</button>'; }).join('') + '</div></div>' +
        '<div class="palette" id="pal"></div><div class="row"><button type="button" class="btn" id="palGrad">Use as gradient</button><button type="button" class="btn ghost" id="palCopy">Copy all</button><button type="button" class="btn ghost" id="palPic">From a picture…</button></div></div>';
    } else {
      body = '<div class="list">' + (COL.saved.length ? COL.saved.map(function (s, i) {
        return '<div class="item"><span class="gbar" style="width:120px;background:linear-gradient(90deg,' + s.s.join(',') + ')"></span><div style="min-width:0"><b>' + esc(s.n) + '</b><span class="muted ell" style="font-family:var(--mono)">' + s.s.join(' → ') + '</span></div>' +
          '<div class="row nw"><button type="button" class="btn sm" data-use="' + i + '">Use</button><button type="button" class="ico" data-unsave="' + i + '" aria-label="Delete ' + esc(s.n) + '">✕</button></div></div>';
      }).join('') : '<span class="muted">Nothing saved yet. Press ☆ Save on a gradient.</span>') + '</div>';
    }
    return '<div class="row sb"><h2 class="h">Colours</h2><span class="muted">for Minecraft, Discord and themes</span></div>' + colTabs() + body;
  };
  var obfTimer = null, rememberTimer = null;
  WIRE.color = function (m) {
    clearInterval(obfTimer);
    $$('[data-ctab]', m).forEach(function (b) { b.onclick = function () { COL.tab = b.getAttribute('data-ctab'); go('color', true); }; });
    if (COL.tab === 'grad') wireGrad(m);
    else if (COL.tab === 'codes') wireCodes(m);
    else if (COL.tab === 'pal') wirePal(m);
    else {
      $$('[data-use]', m).forEach(function (b) { b.onclick = function () { COL.grad.stops = COL.saved[+b.getAttribute('data-use')].s.slice(); COL.tab = 'grad'; go('color', true); }; });
      $$('[data-unsave]', m).forEach(function (b) { b.onclick = function () { api('colours_delete', +b.getAttribute('data-unsave')).then(function (r) { COL.saved = r.saved; go('color', true); }).catch(fail); }; });
    }
  };
  function wireGrad(m) {
    var g = COL.grad, OBF = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&@';
    function renderStops() {
      var box = $('#stops', m); box.textContent = '';
      g.stops.forEach(function (h, i) {
        var row = document.createElement('div'); row.className = 'stop';
        row.innerHTML = '<input type="color" value="' + h.toLowerCase() + '" aria-label="Colour ' + (i + 1) + '"><input class="field mono" value="' + h + '" maxlength="7" aria-label="Hex ' + (i + 1) + '"><span class="muted grow">' + (i === 0 ? 'start' : i === g.stops.length - 1 ? 'end' : 'middle') + '</span>' +
          (g.stops.length > 2 ? '<button type="button" class="ico" aria-label="Remove colour ' + (i + 1) + '">✕</button>' : '');
        var ci = row.children[0], hi = row.children[1], x = row.querySelector('.ico');
        ci.addEventListener('input', function () { g.stops[i] = ci.value.toUpperCase(); hi.value = g.stops[i]; upd(); });
        hi.addEventListener('input', function () { var v = hi.value.trim(); if (v[0] !== '#') v = '#' + v; if (/^#[0-9a-fA-F]{6}$/.test(v)) { g.stops[i] = v.toUpperCase(); ci.value = v.toLowerCase(); upd(); } });
        if (x) x.onclick = function () { g.stops.splice(i, 1); renderStops(); upd(); };
        box.appendChild(row);
      });
      $('#grAdd', m).disabled = g.stops.length >= 6;
    }
    function upd() {
      var r = gradientCode(g), shc = hexRgb(g.shc), sha = g.sha / 100;
      $('#gbar', m).style.background = 'linear-gradient(90deg,' + g.stops.join(',') + ')';
      var prev = $('#grPrev', m); prev.textContent = '';
      r.chars.forEach(function (c, i) {
        var s = document.createElement('span'); s.textContent = c; s.style.color = r.hexes[i];
        if (g.b) s.style.fontWeight = '700'; if (g.i) s.style.fontStyle = 'italic';
        var dec = []; if (g.u) dec.push('underline'); if (g.s) dec.push('line-through'); s.style.textDecoration = dec.join(' ');
        var d = hexRgb(r.hexes[i]).map(function (v) { return Math.round(v * .25); });
        s.style.textShadow = g.sh ? '3px 3px 0 rgba(' + shc.join(',') + ',' + sha + ')' : '3px 3px 0 rgb(' + d.join(',') + ')';
        if (g.k && c !== ' ') s.className = 'obf';
        prev.appendChild(s);
      });
      clearInterval(obfTimer);
      if (g.k && !reduce) obfTimer = setInterval(function () { if (!document.body.contains(prev)) { clearInterval(obfTimer); return; } $$('.obf', prev).forEach(function (s) { s.textContent = OBF[Math.floor(Math.random() * OBF.length)]; }); }, 70);
      $('#grOut', m).value = r.out; $('#fmtNote', m).textContent = r.note;
      var cnt = $('#grCount', m), lim = g.fmt === 'json' ? 32500 : 256;
      cnt.textContent = r.out.length + ' characters' + (r.out.length > lim ? ' · too long for ' + (lim === 256 ? 'one chat message' : 'a command') : '');
      cnt.className = r.out.length > lim ? 'warnc' : 'muted';
      clearTimeout(rememberTimer);
      rememberTimer = setTimeout(function () { api('colours_remember', g).catch(function () {}); }, 1200);
    }
    renderStops(); upd();
    $('#grText', m).addEventListener('input', function () { g.text = this.value; upd(); });
    $$('#grFmt button', m).forEach(function (b) { b.onclick = function () { g.fmt = b.getAttribute('data-fmt'); $$('#grFmt button', m).forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); }); upd(); }; });
    $$('#grStyle button', m).forEach(function (b) { b.onclick = function () { var k = b.getAttribute('data-st'); g[k] = !g[k]; b.setAttribute('aria-pressed', String(g[k])); upd(); }; });
    $('#grAdd', m).onclick = function () { if (g.stops.length < 6) { g.stops.push(at(g.stops, .5).toUpperCase()); renderStops(); upd(); } };
    $('#grRev', m).onclick = function () { g.stops.reverse(); renderStops(); upd(); };
    $$('[data-preset]', m).forEach(function (b) { b.onclick = function () { g.stops = PRESETS[+b.getAttribute('data-preset')][1].slice(); renderStops(); upd(); }; });
    $('#shOn', m).onclick = function () { g.sh = !g.sh; this.setAttribute('aria-checked', String(g.sh)); upd(); };
    $('#shC', m).addEventListener('input', function () { g.shc = this.value.toUpperCase(); upd(); });
    $('#shA', m).addEventListener('input', function () { g.sha = +this.value; $('#shAv', m).textContent = this.value + '%'; upd(); });
    $('#grCopy', m).onclick = function () { copyText($('#grOut', m).value, this, 'Copy code'); };
    $('#grSave', m).onclick = function () { var btn = this; api('colours_save', (g.text || 'Gradient').slice(0, 40), g.stops).then(function (r) { if (r.ok) { COL.saved = r.saved; btn.textContent = '★ Saved'; } else toast(r.message); }).catch(fail); };
  }
  function lum(h) { var c = hexRgb(h).map(function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; }
  function wireCodes(m) {
    function show(h) {
      COL.hex = h;
      var c = hexRgb(h), hs = hex2hsl(h), box = $('#hxRows', m); box.textContent = '';
      [['HEX', h], ['RGB', 'rgb(' + c.join(', ') + ')'], ['HSL', 'hsl(' + hs[0] + ', ' + hs[1] + '%, ' + hs[2] + '%)'], ['Minecraft', '&' + h.toLowerCase()], ['Skript', '<#' + h.toLowerCase() + '>'], ['Discord / decimal', String(parseInt(h.slice(1), 16))]].forEach(function (r) {
        var it = document.createElement('button'); it.type = 'button'; it.className = 'item codeitem';
        it.innerHTML = '<span class="muted" style="min-width:110px">' + r[0] + '</span><b class="mono"></b><span class="muted">copy</span>';
        it.querySelector('b').textContent = r[1];
        it.onclick = function () { copyText(r[1], it.lastChild, 'copy'); };
        box.appendChild(it);
      });
      var sh = $('#hxShades', m); sh.textContent = '';
      [-0.6, -0.4, -0.2, 0, 0.25, 0.5, 0.75].forEach(function (k) {
        var hx = rgbHex(c.map(function (v) { return k < 0 ? v * (1 + k) : v + (255 - v) * k; }));
        var s = document.createElement('button'); s.type = 'button'; s.className = 'sw'; s.title = hx; s.setAttribute('aria-label', 'Use ' + hx);
        s.style.background = hx; if (k === 0) s.style.outline = '2px solid var(--ink)';
        s.onclick = function () { set(hx); };
        sh.appendChild(s);
      });
    }
    function set(h) { $('#hxIn', m).value = h; $('#hxPick', m).value = h.toLowerCase(); show(h); }
    $('#hxPick', m).addEventListener('input', function () { set(this.value.toUpperCase()); });
    $('#hxIn', m).addEventListener('input', function () { var v = this.value.trim(); if (v[0] !== '#') v = '#' + v; if (/^#[0-9a-fA-F]{6}$/.test(v)) { $('#hxPick', m).value = v.toLowerCase(); show(v.toUpperCase()); } });
    show(COL.hex);
    function contrast() {
      var a = $('#cA', m).value, b = $('#cB', m).value, la = lum(a), lb = lum(b), r = (Math.max(la, lb) + .05) / (Math.min(la, lb) + .05);
      COL.cA = a.toUpperCase(); COL.cB = b.toUpperCase();
      var p = $('#cPrev', m); p.style.color = a; p.style.background = b;
      $('#cRatio', m).textContent = 'Contrast ' + r.toFixed(1) + ' : 1';
      $('#cVerdict', m).innerHTML = r >= 7 ? '<span class="okc">Very easy to read</span> (passes AAA)' : r >= 4.5 ? '<span class="okc">Easy to read</span> (passes AA)' : r >= 3 ? '<span class="warnc">Only for big text</span>' : '<span class="badc">Hard to read</span>: pick colours further apart';
    }
    $('#cA', m).addEventListener('input', contrast); $('#cB', m).addEventListener('input', contrast); contrast();
  }
  function wirePal(m) {
    function build() {
      if (COL.palMode === 5) return paint();                       // colours taken from a picture
      var hs = hex2hsl(COL.palBase), h = hs[0], s = hs[1], l = hs[2];
      var sets = [
        [[h, s, l], [h, s, Math.max(15, l - 20)], [(h + 180) % 360, s, l], [(h + 180) % 360, s, Math.min(85, l + 15)]],
        [[(h + 330) % 360, s, l], [(h + 345) % 360, s, l], [h, s, l], [(h + 15) % 360, s, l], [(h + 30) % 360, s, l]],
        [[h, s, l], [(h + 120) % 360, s, l], [(h + 240) % 360, s, l]],
        [[h, s, l], [h, s, l * .8], [h, s, l * .6], [h, s, l * .4], [h, s, l * .25]],
        [[h, s, l], [h, s, l + (100 - l) * .25], [h, s, l + (100 - l) * .5], [h, s, l + (100 - l) * .7], [h, s, l + (100 - l) * .85]]
      ];
      COL.pal = sets[COL.palMode].map(function (x) { return hsl2hex(x[0], x[1], x[2]); });
      paint();
    }
    function paint() {
      var p = $('#pal', m); p.textContent = '';
      COL.pal.forEach(function (hx) {
        var b = document.createElement('button'); b.type = 'button'; b.className = 'pcol'; b.style.background = hx; b.style.color = lum(hx) > .4 ? '#111' : '#fff'; b.textContent = hx;
        b.title = 'Copy ' + hx; b.onclick = function () { copyText(hx, b, hx); };
        p.appendChild(b);
      });
    }
    $('#pBase', m).addEventListener('input', function () { COL.palBase = this.value.toUpperCase(); if (COL.palMode === 5) COL.palMode = 0; build(); });
    $$('[data-harm]', m).forEach(function (b) { b.onclick = function () { COL.palMode = +b.getAttribute('data-harm'); $$('[data-harm]', m).forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); }); build(); }; });
    $('#palGrad', m).onclick = function () { COL.grad.stops = COL.pal.slice(0, 6); COL.tab = 'grad'; go('color', true); };
    $('#palCopy', m).onclick = function () { copyText(COL.pal.join(' '), this, 'Copy all'); };
    $('#palPic', m).onclick = function () {
      api('colours_from_picture').then(function (r) {
        if (!r.ok) { if (r.message) toast(r.message); return; }
        COL.pal = r.colours; COL.palMode = 5;
        $$('[data-harm]', m).forEach(function (o) { o.setAttribute('aria-pressed', 'false'); });
        paint(); toast('The main colours of ' + r.name);
      }).catch(fail);
    };
    build();
  }

  // ---------- step 4: Home ----------
  var HOME = { data: null, filter: 'all', loading: false, menu: null, start: null, edit: false, pend: {}, seen: {} };
  var IC = {
    play: '<path d="M7 4l13 8-13 8z"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    code: '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>'
  };
  function ic(k) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + IC[k] + '</svg>'; }
  function loadHome(force) {
    if (HOME.loading) return;
    if (HOME.data && !force) return;
    HOME.loading = true;
    api('home').then(function (d) { HOME.loading = false; HOME.data = d; if (st.screen === 'home') go('home', true); }).catch(function (e) { HOME.loading = false; fail(e); });
  }
  var BADGES = ['#E8893A', '#5B6CFF', '#2BB3A4', '#E85D75', '#9AA7FF', '#F7A541', '#3FA796', '#B57EDC', '#6FA6D6', '#FF5C8A'];
  function appIcon(a, name) {
    if (a.icon) return '<img class="appicon" src="' + a.icon + '" alt="">';
    var h = 0, n = String(name || '?'); for (var i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) >>> 0;
    return '<span class="badge letter" style="background:' + BADGES[h % BADGES.length] + '">' + esc(n[0]) + '</span>';
  }
  // Edit mode (his ask 25 Oct, "like a phone home screen"): every card wiggles with a ✕; clicking marks it (your own
  // projects get hidden, added apps removed, hidden ones can come back), Done applies all of it, Cancel forgets it
  function homeMarked(id, kind) {
    var p = HOME.pend[id];
    return kind === 'hidden' ? p !== 'show' : !!p;
  }
  function editBits(id, kind) {
    if (!HOME.edit) return { cls: '', badge: '' };
    var gone = homeMarked(id, kind), i = Object.keys(HOME.seen).indexOf(id);
    if (i === -1) { HOME.seen[id] = 1; i = Object.keys(HOME.seen).length - 1; }
    var what = kind === 'added' ? 'Remove' : 'Hide', back = kind === 'hidden' ? 'Show on Home again' : 'Keep it';
    return { cls: ' wig' + (gone ? ' gone' : ''), style: ' style="--wd:' + (i % 5) * -0.11 + 's"',
      badge: '<button type="button" class="ex" data-ex="' + esc(id) + '" data-kind="' + kind + '" aria-pressed="' + gone + '" title="' + (gone ? back : what + ' from Home') + '" aria-label="' + (gone ? back : what + ' from Home') + '">' + (gone ? '↶' : ic('x')) + '</button>' +
        (gone ? '<span class="gonetag">' + (kind === 'added' ? 'Will be removed' : 'Hidden') + '</span>' : '') };
  }
  VIEWS.home = function () {
    var d = HOME.data;
    if (!d) { loadHome(); return '<h2 class="h">Your apps</h2><span class="muted">Reading your projects\' notes…</span>'; }
    var mine = d.projects.filter(function (p) { return HOME.edit || !p.hidden; }), hidden = d.projects.filter(function (p) { return p.hidden; }).length;
    var cards = [];
    if (HOME.filter !== 'added') mine.forEach(function (p) {
      var e = editBits(p.id, p.hidden ? 'hidden' : 'mine');
      cards.push('<div class="card appc lift' + e.cls + '"' + (e.style || '') + ' data-app="' + esc(p.id) + '" data-mine="1">' + e.badge + '<div class="top">' + appIcon(p, p.name) + '<div class="grow"><b class="ell">' + esc(p.name) + '</b><span class="muted ell">' + esc(p.what || p.id) + '</span></div>' +
        '<span class="tag">' + (p.progress == null ? 'no bar' : p.progress + '%') + '</span></div>' + (p.progress == null ? '' : '<div class="bar"><i style="width:' + p.progress + '%"></i></div>') +
        '<div class="next">' + (p.next ? '<b>Next:</b> ' + esc(p.next) : '<span class="muted">No open items in its notes.</span>') + '</div>' +
        '<div class="acts"><button type="button" class="btn sm' + (p.can_open ? '' : ' ghost') + '" data-a="open"' + (p.can_open ? '' : ' title="' + esc(p.note || 'Right-click → Change how it opens') + '"') + '>' + ic('play') + 'Open</button>' +
        '<button type="button" class="lb" data-a="settings"' + (p.has_settings ? '' : ' disabled title="It has no settings of its own"') + '>' + ic('gear') + 'Settings</button>' +
        '<button type="button" class="lb" data-a="folder">' + ic('folder') + 'Folder</button>' +
        '<button type="button" class="lb" data-a="code"' + (d.vscode ? '' : ' disabled title="VS Code wasn\'t found"') + '>' + ic('code') + 'VS Code</button></div></div>');
    });
    if (HOME.filter !== 'mine') d.added.forEach(function (a) {
      var e = editBits(a.id, 'added');
      cards.push('<div class="card appc lift' + e.cls + '"' + (e.style || '') + ' data-app="' + esc(a.id) + '">' + e.badge + '<div class="top">' + appIcon(a, a.name) + '<div class="grow"><b class="ell">' + esc(a.name) + '</b><span class="muted ell">' +
        (a.kind === 'url' ? esc(a.target) : 'added' + (a.group ? ' · ' + esc(a.group) : '')) + '</span></div>' + (a.missing ? '<span class="tag warn">moved?</span>' : '') + '</div>' +
        '<div class="next muted">' + (a.kind === 'url' ? 'A website, opens in your browser' : 'Added by you · ' + esc(a.target.split('\\').pop())) + '</div>' +
        '<div class="acts"><button type="button" class="btn sm" data-a="open">' + ic('play') + 'Open</button>' +
        (a.kind === 'url' ? '<span></span>' : '<button type="button" class="lb" data-a="folder">' + ic('folder') + 'Folder</button>') + '<span></span>' +
        '<button type="button" class="lb" data-a="remove">' + ic('x') + 'Remove</button></div></div>');
    });
    var changes = Object.keys(HOME.pend).length;
    return '<div class="row sb"><div><h2 class="h">Your apps</h2><span class="muted">' + (HOME.edit ? 'Click ✕ on what should go: your own projects are hidden (they can come back), added apps are removed from Home. Nothing gets uninstalled.' : (mine.length + ' of yours · ' + d.added.length + ' added · progress and Next up read from each project\'s notes · right-click an app for more')) + '</span>' +
      (HOME.edit ? '' : '<span class="muted" style="display:block;font-size:12px">Projects from <span title="' + esc(d.root || '') + '">' + esc((d.root || '').split('\\').pop() || 'nowhere yet') + '</span> · <button type="button" class="lb" id="homeRoot" style="display:inline;padding:0;text-decoration:underline">change</button></span>') + '</div>' +
      (HOME.edit ? '<div class="row"><button type="button" class="btn ghost sm" id="homeCancel">Cancel</button><button type="button" class="btn" id="homeDone">' + (changes ? 'Done · ' + changes + ' change' + (changes > 1 ? 's' : '') : 'Done') + '</button></div></div>'
        : '<div class="row"><div class="row" role="group" aria-label="Show">' + [['all', 'All'], ['mine', 'Mine'], ['added', 'Added']].map(function (f) { return '<button type="button" class="chip" data-f="' + f[0] + '" aria-pressed="' + (HOME.filter === f[0]) + '">' + f[1] + '</button>'; }).join('') + '</div>' +
      '<button type="button" class="btn ghost sm" id="homeRefresh">Refresh</button><button type="button" class="btn ghost sm" id="homeEdit"' + (d.projects.length + d.added.length ? '' : ' disabled') + '>Edit</button><button type="button" class="btn" id="homeAdd">+ Add app</button></div></div>') +
      (cards.length ? '<div class="apps' + (HOME.edit ? ' editing' : '') + '">' + cards.join('') + '</div>' : '<div class="card stack"><b>Nothing here yet</b><span class="muted">Press + Add app to put Discord, OBS, Steam or any other program here.</span></div>') +
      (hidden && !HOME.edit ? '<button type="button" class="btn ghost sm" id="homeUnhide" style="justify-self:start">Show ' + hidden + ' hidden app' + (hidden > 1 ? 's' : '') + '</button>' : '') +
      '<details class="card"><summary><b>Toolbelt\'s own build plan</b> <span class="muted">· steps 1–' + BUILT + ' done</span></summary><div class="steps" style="margin-top:12px">' + STEPS.map(function (s) {
        var done = s[0] <= BUILT;
        return '<div class="card step' + (s[0] === BUILT + 1 ? ' now' : '') + '"><span class="num">Step ' + s[0] + (done ? ' · <span class="okc">done ✓</span>' : s[0] === BUILT + 1 ? ' · <span class="warnc">next</span>' : '') + '</span><b>' + s[1] + '</b><span class="muted">' + esc(s[2]) + '</span></div>';
      }).join('') + '</div></details>';
  };
  function homeCall(name, id) {
    return api(name, id).then(function (r) { if (r && r.message) toast(r.message); return r; }).catch(fail);
  }
  WIRE.home = function (m) {
    $$('[data-f]', m).forEach(function (b) { b.onclick = function () { HOME.filter = b.getAttribute('data-f'); go('home', true); }; });
    $('#homeRefresh', m) && ($('#homeRefresh', m).onclick = function () { HOME.data = null; loadHome(true); toast('Read the notes again'); });
    $('#homeAdd', m) && ($('#homeAdd', m).onclick = openAddApps);
    var un = $('#homeUnhide', m);
    if (un) un.onclick = function () { Promise.all(HOME.data.projects.filter(function (p) { return p.hidden; }).map(function (p) { return api('home_hide', p.id, false); })).then(function () { loadHome(true); }); };
    var ed = $('#homeEdit', m); if (ed) ed.onclick = function () { HOME.edit = true; HOME.pend = {}; HOME.seen = {}; go('home', true); };
    var rootBtn = $('#homeRoot', m);
    if (rootBtn) rootBtn.onclick = function () { api('choose_projects_folder').then(function (r) { if (r.message) toast(r.message); if (r.ok) loadHome(true); }).catch(fail); };
    var cancel = $('#homeCancel', m); if (cancel) cancel.onclick = function () { HOME.edit = false; HOME.pend = {}; go('home', true); };
    var done = $('#homeDone', m);
    if (done) done.onclick = function () {
      var CALL = { hide: function (id) { return api('home_hide', id, true); }, show: function (id) { return api('home_hide', id, false); }, remove: function (id) { return api('home_remove', id); } };
      var ids = Object.keys(HOME.pend), n = { hide: 0, show: 0, remove: 0 };
      done.disabled = true;
      Promise.all(ids.map(function (id) { var what = HOME.pend[id]; n[what]++; return CALL[what](id); })).then(function () {
        HOME.edit = false; HOME.pend = {};
        var said = [n.hide && 'hid ' + n.hide, n.show && 'brought back ' + n.show, n.remove && 'removed ' + n.remove].filter(Boolean);
        if (said.length) toast(said.join(', ').replace(/^./, function (c) { return c.toUpperCase(); }) + ' (nothing was uninstalled)');
        if (ids.length) loadHome(true); else go('home', true);
      }).catch(function (e) { done.disabled = false; fail(e); });
    };
    if (HOME.edit) {                                         // in edit mode a click anywhere on a card flips its ✕; nothing opens
      $$('[data-app]', m).forEach(function (card) {
        var b = $('[data-ex]', card), id = card.getAttribute('data-app'), kind = b.getAttribute('data-kind');
        card.onclick = function (e) {
          e.preventDefault();
          var want = { mine: 'hide', hidden: 'show', added: 'remove' }[kind];
          if (HOME.pend[id]) delete HOME.pend[id]; else HOME.pend[id] = want;
          go('home', true);
        };
        card.oncontextmenu = function (e) { e.preventDefault(); };
      });
      return;
    }
    $$('[data-app]', m).forEach(function (card) {
      var id = card.getAttribute('data-app'), mineCard = card.hasAttribute('data-mine');
      $$('[data-a]', card).forEach(function (b) {
        b.onclick = function () {
          var a = b.getAttribute('data-a');
          if (a === 'open') homeCall('home_open', id);
          else if (a === 'settings') homeCall('home_settings', id).then(function (r) { if (r && r.go) go(r.go); });
          else if (a === 'folder') homeCall('home_folder', id);
          else if (a === 'code') homeCall('home_code', id);
          else if (a === 'remove') homeCall('home_remove', id).then(function () { loadHome(true); });
        };
      });
      card.oncontextmenu = function (e) { e.preventDefault(); appMenu(id, mineCard, e.clientX, e.clientY); };
    });
  };
  function appMenu(id, mineCard, x, y) {
    var old = $('#appMenu'); if (old) old.remove();
    var menu = document.createElement('div'); menu.className = 'cmenu'; menu.id = 'appMenu'; menu.setAttribute('role', 'menu');
    var items = mineCard ? [['open', 'Open'], ['notes', 'Read its notes'], ['code', 'Open in VS Code'], ['folder', 'Open its folder'], ['-'], ['change-open', 'Change how it opens…'], ['change-settings', 'Change where its settings are…'], ['reset', 'Back to the default'], ['-'], ['hide', 'Hide from Home']]
      : [['open', 'Open'], ['folder', 'Show the file'], ['-'], ['remove', 'Remove from Home']];
    menu.innerHTML = items.map(function (i) { return i[0] === '-' ? '<hr>' : '<button type="button" role="menuitem" data-m="' + i[0] + '">' + i[1] + '</button>'; }).join('');
    var app = $('#app'), r = app.getBoundingClientRect();
    app.appendChild(menu);
    menu.style.left = Math.max(4, Math.min(x - r.left, r.width - menu.offsetWidth - 8)) + 'px';
    menu.style.top = Math.max(4, Math.min(y - r.top, r.height - menu.offsetHeight - 8)) + 'px';
    var map = { open: 'home_open', notes: 'home_notes', code: 'home_code', folder: 'home_folder', reset: 'home_reset', remove: 'home_remove' };
    $$('[data-m]', menu).forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation(); menu.remove();
        var k = b.getAttribute('data-m');
        if (map[k]) homeCall(map[k], id).then(function () { if (k === 'reset' || k === 'remove') loadHome(true); });
        else if (k === 'change-open' || k === 'change-settings') api('home_change', id, k === 'change-open' ? 'open' : 'settings').then(function (res) { if (res.message) toast(res.message); if (res.ok) loadHome(true); }).catch(fail);
        else if (k === 'hide') api('home_hide', id, true).then(function (res) { toast(res.message); loadHome(true); }).catch(fail);
      };
    });
    var first = $('button', menu); if (first) first.focus();
    menu.addEventListener('keydown', function (e) {
      var bs = $$('button', menu), k = bs.indexOf(document.activeElement);
      if (e.key === 'Escape') menu.remove();
      else if (e.key === 'ArrowDown') { e.preventDefault(); bs[(k + 1) % bs.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); bs[(k - 1 + bs.length) % bs.length].focus(); }
    });
  }
  document.addEventListener('click', function (e) { var mnu = $('#appMenu'); if (mnu && !mnu.contains(e.target)) mnu.remove(); });

  function openAddApps() {
    var dim = document.createElement('div'); dim.className = 'dim';
    var picked = {};
    dim.innerHTML = '<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="addT" style="width:min(640px,100%)"><div class="row sb"><h3 class="h" id="addT">Add apps to Home</h3><button type="button" class="ico" data-x aria-label="Close">✕</button></div>' +
      '<input class="field" id="addQ" placeholder="Search your Start menu…" aria-label="Search your Start menu" autocomplete="off"><div class="list addlist" id="addList"><span class="muted">Reading your Start menu…</span></div>' +
      '<div class="row sb"><span class="muted" id="addN">0 picked</span><div class="row"><button type="button" class="btn ghost" id="addExe">Browse for a program…</button><button type="button" class="btn" id="addGo" disabled>Add to Home</button></div></div>' +
      '<div class="row nw"><input class="field" id="addUrl" placeholder="Or a website, like https://hoyolab.com" aria-label="Website address"><button type="button" class="btn ghost" id="addUrlGo">Add website</button></div></div>';
    $('#app').appendChild(dim);
    function close() { dim.remove(); }
    $$('[data-x]', dim).forEach(function (b) { b.onclick = close; });
    dim.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    $('#addQ', dim).focus();
    function render() {
      var q = $('#addQ', dim).value.trim().toLowerCase(), list = (HOME.start || []).filter(function (a) { return !q || (a.name + ' ' + a.group).toLowerCase().indexOf(q) !== -1; });
      $('#addList', dim).innerHTML = list.length ? list.slice(0, 200).map(function (a) {
        return '<button type="button" class="item additem" data-path="' + esc(a.path) + '" aria-pressed="' + !!picked[a.path] + '">' + (a.icon ? '<img class="appicon sm" src="' + a.icon + '" alt="">' : '<span class="badge" style="width:24px;height:24px;font-size:11px">' + esc(a.name[0]) + '</span>') +
          '<span class="ell" style="text-align:left"><b>' + esc(a.name) + '</b>' + (a.group ? ' <span class="muted">· ' + esc(a.group) + '</span>' : '') + '</span><span class="tick">' + (picked[a.path] ? '✓' : '') + '</span></button>';
      }).join('') : '<span class="muted">Nothing in your Start menu matches.</span>';
      $$('.additem', dim).forEach(function (b) {
        b.onclick = function () { var p = b.getAttribute('data-path'); if (picked[p]) delete picked[p]; else picked[p] = true; render(); };
      });
      var n = Object.keys(picked).length;
      $('#addN', dim).textContent = n + ' picked'; $('#addGo', dim).disabled = !n;
    }
    $('#addQ', dim).addEventListener('input', render);
    if (HOME.start) render(); else api('start_menu').then(function (l) { HOME.start = l; if (document.body.contains(dim)) render(); }).catch(fail);
    $('#addGo', dim).onclick = function () { api('home_add_many', Object.keys(picked)).then(function (r) { toast(r.message); close(); loadHome(true); }).catch(fail); };
    $('#addExe', dim).onclick = function () { api('home_add_exe').then(function (r) { if (r.message) toast(r.message); if (r.ok) { close(); loadHome(true); } }).catch(fail); };
    $('#addUrlGo', dim).onclick = function () { api('home_add', 'url', $('#addUrl', dim).value).then(function (r) { toast(r.message); if (r.ok) { close(); loadHome(true); } }).catch(fail); };
  }

  VIEWS.engines = function () {
    var e = st.engines, g = st.gpus;
    if (!e) return '<h2 class="h">Engines</h2><span class="muted">Looking…</span>';
    var colors = ['#E8893A', '#6F7BD6', '#3FA796', '#B57EDC', '#FF5C8A', '#4FB8E6', '#E6C84F'];
    var bar = e.total ? '<div class="storebar">' + e.engines.map(function (x, i) { return x.size ? '<i style="width:' + (x.size / e.total * 100) + '%;background:' + colors[i] + '" title="' + esc(x.name) + '"></i>' : ''; }).join('') + '</div>' : '';
    return '<div class="row sb"><h2 class="h">Engines</h2><span class="tag">' + fmtBytes(e.total) + ' in ' + esc(e.folder) + '</span></div>' +
      '<p class="muted">The outside programs and AI models Toolbelt uses. They all live in your AppData, never in OneDrive. Nothing installs without asking you first: each one arrives with the step that needs it.</p>' +
      '<div class="cols"><div class="card stack"><b>Space used</b>' + (bar || '<span class="muted">Nothing downloaded yet.</span>') +
      '<div class="row"><button type="button" class="btn ghost sm" data-open="engines">Open folder</button><button type="button" class="btn ghost sm" id="engRefresh">Look again</button><button type="button" class="btn ghost sm" id="engUpdates">Check for updates</button></div></div>' +
      '<div class="card stack"><b>Graphics card</b>' + (g === null ? '<span class="muted">Asking Windows…</span>' : g.length ? g.map(function (n) {
        var amd = /radeon|amd/i.test(n);
        return '<div class="item"><span class="okc">✓</span><span>' + esc(n) + '</span><span class="muted">' + (amd ? 'DirectML · Vulkan · AMF' : 'DirectML · Vulkan') + '</span></div>';
      }).join('') : '<span class="muted">Windows didn\'t report a graphics card.</span>') + '</div></div>' +
      '<div class="tbl"><div class="hd"><span>Engine</span><span>State</span><span>Licence</span><span></span></div>' + e.engines.map(function (x) {
        return '<div><span><b>' + esc(x.name) + '</b><span class="muted" style="display:block">' + esc(x.what) + '</span></span><span>' +
          (x.installed ? '<span class="okc">installed</span> <span class="muted">' + fmtBytes(x.size) + (x.version ? ' · ' + esc(x.version) : '') + '</span>' : '<span class="muted">not installed · ' + esc(x.approx) + '</span>') +
          '</span><span class="muted">' + esc(x.licence) + '</span><span>' + engineAction(x) + '</span></div>';
      }).join('') + '</div>';
  };
  function engineAction(x) {
    if (INSTALLABLE.indexOf(x.id) === -1) return '<span class="muted">with step ' + x.step + ', asks first</span>';
    var busy = st.jobs.filter(function (j) { return j.kind === 'Engine' && j.extra && j.extra.engine === x.id && (j.state === 'running' || j.state === 'waiting'); })[0];
    if (busy) return '<span class="warnc">' + Math.round(busy.progress) + '% · ' + esc(busy.message || 'waiting') + '</span>';
    if (!x.installed) return '<button type="button" class="btn sm" data-install="' + x.id + '">Install</button>';
    var u = DL.updates && DL.updates[x.id];
    if (u && u.update) return '<button type="button" class="btn sm" data-install="' + x.id + '">Update to ' + esc(u.newest) + '</button>';
    return u ? '<span class="okc">up to date ✓</span>' : '<span class="muted">installed</span>';
  }
  WIRE.engines = function (m) {
    var r = $('#engRefresh', m); if (r) r.onclick = function () { loadEngines(true); };
    $$('[data-install]', m).forEach(function (b) { b.onclick = function () { b.disabled = true; api('install_engines', [b.getAttribute('data-install')]).then(function (res) { toast(res.message); pollJobs(); }).catch(fail); }; });
    var cu = $('#engUpdates', m);
    if (cu) cu.onclick = function () { cu.disabled = true; cu.textContent = 'Asking…'; api('check_updates', true).then(function (u) { DL.updates = u; go('engines', true); var n = Object.keys(u).filter(function (k) { return u[k].update; }).length; toast(n ? n + ' update' + (n > 1 ? 's' : '') + ' available' : 'Everything is up to date'); }).catch(fail); };
  };

  var SETS = [['look', 'Appearance'], ['files', 'Files'], ['dl', 'Downloads'], ['about', 'About']];
  VIEWS.settings = function () {
    var s = st.settings;
    if (!s) return '<h2 class="h">Settings</h2><span class="muted">Loading…</span>';
    var body = '';
    if (st.set === 'look') {
      var acc = ACCENTS[s.look];
      body = setrow('Look', 'Cartridge, Glass or Glass Dark', [['cartridge', 'Cartridge'], ['glass', 'Glass'], ['glassdark', 'Glass Dark']].map(function (l) {
          return '<button type="button" class="chip" data-look="' + l[0] + '" aria-pressed="' + (s.look === l[0]) + '">' + l[1] + '</button>'; }).join('')) +
        setrow('Accent colour', 'Buttons, bars and highlights', '<div class="accents"><button type="button" class="own" data-acc="" aria-pressed="' + (!s.accent) + '">The look\'s own</button>' +
          acc.map(function (c) { return '<button type="button" style="background:' + c + '" data-acc="' + c + '" aria-pressed="' + (s.accent === c) + '" aria-label="Accent ' + c + '"></button>'; }).join('') + '</div>') +
        setrow('Animations', 'Screens sliding in, cards lifting, moving bars', sw('setAnim', s.animations, 'Animations')) +
        setrow('Background slideshow', 'A game with several backgrounds fades to the next one after', [[10, '10 s'], [20, '20 s'], [45, '45 s'], [90, '90 s']].map(function (k) { return '<button type="button" class="chip" data-bdwell="' + k[0] + '" aria-pressed="' + (((s.banner_dwell || 20)) === k[0]) + '">' + k[1] + '</button>'; }).join('')) +
        setrow('Moving game covers', 'GIF and video covers in the game library', [['still', 'Still'], ['hover', 'Move on hover'], ['always', 'Always move']].map(function (k) { return '<button type="button" class="chip" data-cmot="' + k[0] + '" aria-pressed="' + ((s.cover_motion || 'hover') === k[0]) + '">' + k[1] + '</button>'; }).join('')) +
        '<p class="muted" style="padding-top:8px">More sections (Startup & tray, Downloads, Notifications, Privacy, Integrations, Backup) arrive with the steps that need them.</p>';
    } else if (st.set === 'files') {
      body = setrow('Save to', 'Where finished files go', '<span class="tag" style="max-width:340px"><span class="ell">' + esc(s.save_to) + '</span></span><button type="button" class="btn ghost sm" id="pickFolder">Change…</button><button type="button" class="btn ghost sm" data-open="save">Open</button>') +
        '<div class="setrow"><div><b>Name files like</b><span class="muted">{title}, {quality} and {ext} are filled in for you</span><span class="err" id="patErr"></span></div><div class="ctl"><input class="field mono" id="pattern" value="' + esc(s.name_pattern) + '" aria-label="File name pattern" style="width:260px"><button type="button" class="btn sm" id="patSave">Save</button></div></div>' +
        setrow('Never overwrite', 'Adds (2), (3)… instead', sw('setOver', s.never_overwrite, 'Never overwrite')) +
        setrow('A folder per tool', 'Downloads, Cut-outs, Converted…', sw('setPer', s.folder_per_tool, 'A folder per tool')) +
        setrow('Open the folder when a job is done', '', sw('setOpen', s.open_when_done, 'Open the folder when done'));
    } else if (st.set === 'dl') {
      body = setrow('Notice copied links', 'Copy a YouTube link anywhere and Toolbelt offers to download it (only while it runs)', sw('setClip', s.watch_clipboard, 'Notice copied links')) +
        setrow('Keep, by default', '', [['both', 'Video + sound'], ['video', 'Video only'], ['audio', 'Just the sound']].map(function (k) { return '<button type="button" class="chip" data-dkeep="' + k[0] + '" aria-pressed="' + (s.keep === k[0]) + '">' + k[1] + '</button>'; }).join('')) +
        setrow('Sound format, by default', 'MP3 works everywhere, also in Spotify', [['mp3', 'MP3'], ['m4a', 'M4A'], ['opus', 'Opus']].map(function (k) { return '<button type="button" class="chip" data-dfmt="' + k[0] + '" aria-pressed="' + (s.audio_format === k[0]) + '">' + k[1] + '</button>'; }).join('')) +
        setrow('Subtitles with videos', 'English, Japanese and Dutch ones go inside the video (switch them on in any player). Automatic ones are YouTube’s own speech-to-text', [['off', 'Off'], ['made', 'Real ones only'], ['auto', 'Also automatic']].map(function (k) { return '<button type="button" class="chip" data-dsubs="' + k[0] + '" aria-pressed="' + ((s.dl_subs || 'off') === k[0]) + '">' + k[1] + '</button>'; }).join('')) +
        setrow('Put MP3s in Spotify too', 'Copies them to Music\\Toolbelt for Spotify', sw('setSpot', s.auto_spotify, 'Put MP3s in Spotify too') + '<button type="button" class="btn ghost sm" id="openSpot">Open folder</button>');
    } else {
      var i = st.info || {};
      body = setrow('Toolbelt', esc(i.version || ''), '<span class="tag">made with Claude</span>') +
        setrow('Settings and engines', esc(i.data || ''), '<button type="button" class="btn ghost sm" data-open="data">Open</button>') +
        setrow('Start menu and taskbar', 'Puts Toolbelt in your Start menu with its own icon; right-click it there to pin it to the taskbar', '<button type="button" class="btn ghost sm" id="startMenu">Add to Start menu</button>') +
        setrow('The keyboard\'s Calculator key', 'Opens Toolbelt\'s floating calculator instead of Windows\' (one entry in your own registry; off puts it back)', sw('setCalcKey', s.calc_key, 'Calculator key opens Toolbelt')) +
        setrow('Win+W', 'Opens Toolbelt, or hides it when it is in front. While on, Windows\' own Win+W (Widgets) is switched off in Windows itself; off gives it back.', sw('setWinT', s.win_t, 'Win+W opens Toolbelt')) +
        setrow('Windows\' Win+W', '<span id="wintInfo">Checking…</span>', '<button type="button" class="btn ghost sm" id="wintRestart" hidden>Restart Explorer</button>') +
        setrow('Own window bar', 'The top bar with the logo is the window\'s title bar: drag it to move, double-click to maximise. Off = Windows\' grey bar is back. Takes effect after a restart.', sw('setOwnBar', s.own_bar !== false, 'Own window bar')) +
        setrow('Internet switch', NET.installed ? 'The 🌐 button at the top switches your Ethernet off and on without a prompt (two tasks in Task Scheduler, folder Toolbelt). Works offline too.' : 'The 🌐 button at the top can switch your Ethernet off and on, like pulling the cable. Setting it up asks Windows for admin once; after that, no prompts.',
          NET.installed ? '<button type="button" class="btn ghost sm" id="netRemove">Remove</button>' : '<button type="button" class="btn sm" id="netSetup">Set up</button>');
    }
    return '<h2 class="h">Settings</h2><div class="setgrid"><nav class="setnav" aria-label="Settings sections">' + SETS.map(function (x) {
      return '<button type="button" data-set="' + x[0] + '" aria-pressed="' + (st.set === x[0]) + '">' + x[1] + '</button>'; }).join('') + '</nav><div class="card">' + body + '</div></div>';
  };
  WIRE.settings = function (m) {
    var ns = $('#netSetup', m), nr = $('#netRemove', m);
    if (ns) ns.onclick = function () { ns.disabled = true; ns.textContent = 'Waiting for Windows…'; api('net_setup').then(function (r) { toast(r.message); NET.installed = !!r.ok; go('settings', true); netPoll(); }).catch(fail); };
    if (nr) nr.onclick = function () { nr.disabled = true; api('net_remove').then(function (r) { toast(r.message); NET.installed = !r.ok; go('settings', true); netPoll(); }).catch(fail); };
    $$('[data-set]', m).forEach(function (b) { b.onclick = function () { st.set = b.getAttribute('data-set'); go('settings', true); }; });
    $$('[data-look]', m).forEach(function (b) { b.onclick = function () { change('look', b.getAttribute('data-look')).then(function () { return change('accent', ''); }).then(function () { go('settings', true); }); }; });
    $$('[data-acc]', m).forEach(function (b) { b.onclick = function () { change('accent', b.getAttribute('data-acc')).then(function () { go('settings', true); }); }; });
    var toggles = { setAnim: 'animations', setOver: 'never_overwrite', setPer: 'folder_per_tool', setOpen: 'open_when_done', setClip: 'watch_clipboard', setSpot: 'auto_spotify', setCalcKey: 'calc_key', setWinT: 'win_t', setOwnBar: 'own_bar' };
    $$('[data-dsubs]', m).forEach(function (b) { b.onclick = function () { change('dl_subs', b.getAttribute('data-dsubs')).then(function () { go('settings', true); }); }; });
    $$('[data-bdwell]', m).forEach(function (b) { b.onclick = function () { change('banner_dwell', +b.getAttribute('data-bdwell')).then(function () { go('settings', true); }); }; });
    $$('[data-cmot]', m).forEach(function (b) { b.onclick = function () { change('cover_motion', b.getAttribute('data-cmot')).then(function () { go('settings', true); }); }; });
    $$('[data-dkeep]', m).forEach(function (b) { b.onclick = function () { change('keep', b.getAttribute('data-dkeep')).then(function () { DL.keep = null; go('settings', true); }); }; });
    $$('[data-dfmt]', m).forEach(function (b) { b.onclick = function () { change('audio_format', b.getAttribute('data-dfmt')).then(function () { DL.keep = null; go('settings', true); }); }; });
    var os = $('#openSpot', m); if (os) os.onclick = function () { api('open_spotify_folder').then(function (r) { toast(r.message); }).catch(fail); };
    var sm = $('#startMenu', m); if (sm) sm.onclick = function () { api('add_to_start_menu').then(function (r) { toast(r.message); }).catch(fail); };
    Object.keys(toggles).forEach(function (id) {
      var b = $('#' + id, m); if (!b) return;
      b.onclick = function () { var on = b.getAttribute('aria-checked') !== 'true'; b.setAttribute('aria-checked', String(on)); var p = change(toggles[id], on); if (id === 'setWinT' && p && p.then) p.then(wintShow); };
    });
    // Windows' own Win+W (his wish, 15 Oct): switched off in Windows; Explorer has to restart before Windows lets go of it
    function wintShow() {
      var box = $('#wintInfo', m), btn = $('#wintRestart', m); if (!box) return;
      api('wint_info').then(function (w) {
        if (!w.on) { box.textContent = 'Windows\' own (Toolbelt\'s Win+W is off).'; btn.hidden = true; return; }
        // Windows 11 keeps Win+W for Widgets even when it's switched off in its settings (found 15 Oct, also with admin):
        // then Toolbelt's key watcher takes it first. Restarting Explorer only helps for keys Explorer itself gives up.
        box.textContent = w.mode === 'hotkey' ? 'Win+W is a normal shortcut of Toolbelt\'s.' : w.mode === 'hook' ? 'Toolbelt catches Win+W first with its key watcher, so Windows\' Widgets never opens.' :
          !w.windowsOff ? 'Still Windows\' own in its settings.' : 'Toolbelt isn\'t catching it right now: restart Toolbelt.';
        btn.hidden = true;
      }).catch(function () { box.textContent = ''; });
    }
    wintShow();
    var wr = $('#wintRestart', m); if (wr) wr.onclick = function () {
      wr.disabled = true; wr.textContent = 'Restarting…';
      api('wint_restart_explorer').then(function (r) { toast(r.message); wr.disabled = false; wr.textContent = 'Restart Explorer'; wintShow(); }).catch(fail);
    };
    var pf = $('#pickFolder', m);
    if (pf) pf.onclick = function () { api('choose_folder').then(function (res) { if (res.settings) st.settings = res.settings; if (!res.ok && res.message) toast(res.message); go('settings', true); }).catch(fail); };
    var ps = $('#patSave', m);
    if (ps) ps.onclick = function () {
      change('name_pattern', $('#pattern', m).value).then(function (res) { $('#patErr', m).textContent = res && !res.ok ? res.message : ''; if (res && res.ok) toast('Saved'); });
    };
  };

  // ---------- jobs ----------
  function renderJobs() {
    var running = st.jobs.filter(function (j) { return j.state === 'running' || j.state === 'waiting'; }).length;
    $('#jobsN').textContent = running;
    var d = $('#jobs'); if (d.hidden) return;
    var label = { waiting: 'waiting', running: '', done: 'done ✓', failed: 'failed', cancelled: 'cancelled' };
    d.innerHTML = '<div class="row sb"><h3 class="h">Jobs</h3><div class="row"><button type="button" class="btn ghost sm" id="jobsClear">Clear finished</button><button type="button" class="ico" id="jobsClose" aria-label="Close jobs">✕</button></div></div>' +
      (st.jobs.length ? st.jobs.map(function (j) {
        var live = j.state === 'running' || j.state === 'waiting';
        return '<div class="card job"><div class="row sb nw"><b class="ell">' + esc(j.title) + '</b>' + (live ? '<button type="button" class="btn ghost sm" data-cancel="' + j.id + '">Cancel</button>' : '') + '</div>' +
          '<span class="muted">' + esc(j.kind) + ' · ' + (j.state === 'running' ? Math.round(j.progress) + '%' : label[j.state]) + (j.message && j.state !== 'done' ? ' · ' + esc(j.message) : '') + '</span>' +
          '<div class="bar' + (j.state === 'running' ? ' run' : '') + '"><i style="width:' + j.progress + '%"></i></div></div>';
      }).join('') : '<span class="muted">Nothing running. Downloads, cut-outs and conversions show up here once those tools exist.</span>');
    $('#jobsClose').onclick = function () { toggleJobs(false); };
    $('#jobsClear').onclick = function () { api('clear_jobs').then(pollJobs).catch(fail); };
    $$('[data-cancel]', d).forEach(function (b) { b.onclick = function () { api('cancel_job', +b.getAttribute('data-cancel')).then(function (r) { if (r.message) toast(r.message); }).catch(fail); }; });
  }
  function toggleJobs(open) { $('#jobs').hidden = !open; $('#jobsBtn').setAttribute('aria-expanded', String(open)); renderJobs(); }
  $('#jobsBtn').onclick = function () { toggleJobs($('#jobs').hidden); };
  var engineBusy = false;
  function pollJobs() {
    return api('jobs').then(function (list) {
      st.jobs = list || []; renderJobs(); renderFoot();
      var busy = engineJobs().length > 0;
      if (busy || engineBusy !== busy) {                    // an install is running or just finished
        if (!busy) loadEngines();
        if (st.screen === 'video' && $('#dlInstall')) go('video', true);
        if (st.screen === 'bg' && ($('#cutInstall') || busy)) go('bg', true);
        if (st.screen === 'media' && MD.tab === 'subs' && ($('#mdWhisper') || busy)) go('media', true);
        if (st.screen === 'engines') go('engines', true);
      }
      engineBusy = busy;
      renderDl(); renderCut(); renderMediaDone(); ckJobsTick(); pcJobsTick(); playerProxyTick(); guardTick();
    }).catch(function () {});
  }

  // ---------- render ----------
  function renderSide() {
    var side = $('#side'); side.textContent = '';
    SCREENS.forEach(function (s) {
      if (s[0] === 'sep') { var d = document.createElement('span'); d.className = 'sep'; side.appendChild(d); return; }
      var b = document.createElement('button'); b.type = 'button';
      b.innerHTML = svg(s[0]) + '<span>' + s[1] + '</span>' + (s[2] ? '<span class="soon" title="Comes in step ' + s[2] + '">' + s[2] + '</span>' : '');
      if (s[0] === st.screen) b.setAttribute('aria-current', 'page');
      b.onclick = function () { go(s[0]); };
      side.appendChild(b);
    });
  }
  function renderFoot() {
    var running = st.jobs.filter(function (j) { return j.state === 'running'; }).length, e = st.engines;
    var have = e ? e.engines.filter(function (x) { return x.installed; }).map(function (x) { return x.name; }) : [];
    $('#foot').innerHTML = '<span>Engines: <b>' + (have.length ? esc(have.join(', ')) : 'none yet') + '</b></span>' +
      '<span>Saving to <b>' + esc(st.settings ? st.settings.save_to : '…') + '</b></span><span>' + running + ' job' + (running === 1 ? '' : 's') + ' running</span>' +
      (st.bridge ? '' : '<span class="badc">Python side not connected</span>');
  }
  function go(id, keep) {
    var changed = st.screen !== id;
    st.screen = id;
    try { localStorage.setItem('toolbelt-screen', id); } catch (e) {}
    renderSide();
    var m = $('#screen'), top = m.scrollTop;
    m.innerHTML = VIEWS[id]();
    m.classList.remove('enter');
    if (changed || !keep) { void m.offsetWidth; m.classList.add('enter'); m.scrollTop = 0; } else m.scrollTop = top;
    $$('[data-go]', m).forEach(function (b) { b.onclick = function () { go(b.getAttribute('data-go')); }; });
    $$('[data-open]', m).forEach(function (b) { b.onclick = function () { api('open_folder', b.getAttribute('data-open')).then(function (r) { if (!r.ok) toast(r.message); }).catch(fail); }; });
    if (WIRE[id]) WIRE[id](m);
  }

  function loadEngines(again) {
    return api('engines').then(function (e) {
      st.engines = e; renderFoot();
      if (st.screen === 'engines' || st.screen === 'video' || st.screen === 'bg' || (st.screen === 'media' && MD.tab === 'subs')) go(st.screen, true);     // the install card may now go away
      if (again) toast('Looked again: ' + e.engines.filter(function (x) { return x.installed; }).length + ' of ' + e.engines.length + ' installed');
    }).catch(fail);
  }

  // ---------- the own window bar (winbar.py): the page's bar is the title bar, these are its buttons ----------
  function winState() {
    api('win_state').then(function (s) {
      $('#root').classList.toggle('ownbar', !!(s && s.own));
      $('#root').classList.toggle('winmax', !!(s && s.max));
      $('#winMax').setAttribute('aria-label', s && s.max ? 'Restore' : 'Maximise'); $('#winMax').title = s && s.max ? 'Restore' : 'Maximise';
    }).catch(function () {});
  }
  // dragging: the mouse goes down on the bar (not on its box or buttons) → Windows moves the window from there
  // (Windows' move loop keeps the mouse-up to itself, so the page never sees a dblclick: two presses close together
  // in time and place count as one)
  var tbar = $('.tb'), lastDown = { t: 0, x: 0, y: 0 };
  tbar.addEventListener('mousedown', function (e) {
    if (e.button !== 0 || !$('#root').classList.contains('ownbar') || e.target.closest('input, button, label, a, .winbtns')) return;
    e.preventDefault();
    var now = Date.now(), twice = now - lastDown.t < 450 && Math.abs(e.screenX - lastDown.x) < 6 && Math.abs(e.screenY - lastDown.y) < 6;
    lastDown = twice ? { t: 0, x: 0, y: 0 } : { t: now, x: e.screenX, y: e.screenY };
    if (twice) api('win_max').then(winState).catch(fail);    // double-click the bar: maximise / back
    else api('win_drag').catch(function () {});
  });
  $('#winMin').onclick = function () { api('win_min').catch(fail); };
  $('#winMax').onclick = function () { api('win_max').then(winState).catch(fail); };
  $('#winClose').onclick = function () { api('win_close').catch(fail); };
  var winTimer = null;
  window.addEventListener('resize', function () { clearTimeout(winTimer); winTimer = setTimeout(winState, 120); });   // maximised by drag or double-click
  window.addEventListener('focus', winState);                // back from the tray / Win+W: the bar's buttons are always right

  // ---------- the internet switch (17 Oct): Ethernet off / on without pulling the cable (netswitch.py) ----------
  var NET = { state: 'on', installed: false, busy: false };
  // [button text, hover heading, hover text] (25 Oct, his ask: the hover should say this button switches the internet)
  var NET_SAYS = { on: ['Online', 'Your internet is on', 'Click to switch it off, like pulling the cable. Click again to turn it back on.'],
    off: ['Offline', 'Your internet is off', 'Toolbelt switched it off. Click to turn it back on.'],
    nocable: ['No connection', 'Switched on, but no connection', 'Is the cable in and the router on? Click to switch the internet off.'],
    busy: ['Switching…', 'Switching…', 'Windows is switching the network adapter; a few seconds.'] };
  function netPaint() {
    var b = $('#netBtn'), s = NET.busy ? 'busy' : NET.state, say = NET_SAYS[s];
    b.setAttribute('data-state', s); $('#netTxt').textContent = say[0];
    $('#netTipHead').textContent = say[1];
    $('#netTipText').textContent = NET.installed || s === 'busy' ? say[2] : 'Click to set up the internet switch: one Windows admin prompt, then it works with one click (also when you’re offline).';
    b.setAttribute('aria-pressed', String(NET.state === 'off'));
  }
  function netPoll() { if (NET.busy) return; api('net_state').then(function (r) { NET.state = r.state; NET.installed = r.installed; netPaint(); }).catch(function () {}); }
  function netFlip() {
    if (NET.busy) return;
    if (!NET.installed) { st.set = 'about'; go('settings'); toast('Set up the internet switch first (one Windows admin prompt, then never again).'); return; }
    NET.busy = true; netPaint();
    api('net_set', NET.state === 'off').then(function (r) { NET.busy = false; if (r.state) NET.state = r.state; netPaint(); toast(r.message); }).catch(function (e) { NET.busy = false; netPaint(); fail(e); });
  }
  $('#netBtn').onclick = netFlip;
  T.netFlip = netFlip;

  // ---------- start ----------
  function start() {
    if (st.bridge) return;
    st.bridge = true;
    Promise.all([api('settings'), api('info')]).then(function (r) {
      st.settings = r[0]; st.info = r[1];
      applyLook(); go(st.screen); renderFoot(); winState(); setTimeout(winState, 1500);
      T.ready = true;
      loadEngines();
      api('gpus').then(function (g) { st.gpus = g || []; if (st.screen === 'engines') go('engines', true); }).catch(function () { st.gpus = []; });
      setInterval(pollJobs, 500);
      setInterval(pollClipboard, 1000);
      setInterval(pollMail, 1000);
      netPoll(); setInterval(netPoll, 3000);
    }).catch(function (err) { T.errors.push(String(err.message || err)); fail(err); });
  }
  renderSide(); renderFoot();
  $('#screen').innerHTML = '<span class="muted">Starting…</span>';
  if (window.pywebview && window.pywebview.api) start();
  window.addEventListener('pywebviewready', start);

  // ---------- for the tests ----------
  T.walkScreens = function () {
    var failed = [], count = 0, here = st.screen;
    SCREENS.forEach(function (s) {
      if (!s[1]) return;
      try { go(s[0]); count++; if (!$('#screen').children.length) failed.push(s[0] + ': empty'); }
      catch (e) { failed.push(s[0] + ': ' + e.message); }
    });
    go(here);
    return { count: count, failed: failed };
  };
  T.state = function () {
    return { screen: st.screen, look: st.settings && st.settings.look, jobs: st.jobs.length, engines: st.engines && st.engines.engines.length, gpus: st.gpus, bridge: st.bridge };
  };
  T.go = go;
  T.winState = winState;
})();
