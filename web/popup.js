/* The tray pop-up's script: asks Python for the games, filters them, starts one on a click. */
(function () {
  'use strict';
  var st = { games: [], src: 'All', q: '', look: 'cartridge', logos: {} };
  var $ = function (s) { return document.querySelector(s); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function api(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[name]) return Promise.reject(new Error('not connected'));
    return window.pywebview.api[name].apply(null, args);
  }
  function ago(iso) {
    if (!iso) return 'not played yet';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + ' min ago';
    if (s < 86400) return Math.round(s / 3600) + ' h ago';
    if (s < 86400 * 14) return Math.round(s / 86400) + ' days ago';
    return Math.round(s / 86400 / 7) + ' weeks ago';
  }
  function applyLook(settings) {
    st.look = settings.look || 'cartridge';
    $('#root').className = st.look === 'cartridge' ? 'look-cartridge' : st.look === 'glass' ? 'look-glass' : 'look-glass glass-dark';
    if (settings.accent) $('#root').style.setProperty('--accent', settings.accent); else $('#root').style.removeProperty('--accent');
    if (st.logos[st.look]) $('#mark').innerHTML = st.logos[st.look];
  }
  function render() {
    var sources = ['All'].concat(st.games.map(function (g) { return g.source; }).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort());
    $('#filt').innerHTML = sources.map(function (s) { return '<button type="button" class="chip" data-src="' + esc(s) + '" aria-pressed="' + (st.src === s) + '">' + esc(s) + '</button>'; }).join('');
    Array.prototype.forEach.call(document.querySelectorAll('[data-src]'), function (b) { b.onclick = function () { st.src = b.getAttribute('data-src'); render(); }; });
    var q = st.q.toLowerCase();
    var shown = st.games.filter(function (g) { return (st.src === 'All' || g.source === st.src) && (!q || g.name.toLowerCase().indexOf(q) !== -1); });
    $('#list').innerHTML = shown.length ? shown.map(function (g) {
      var pic = g.icon_data ? '<img src="' + g.icon_data + '" alt="">' : '<span class="tile">' + esc(g.name.charAt(0)) + '</span>';
      return '<button type="button" class="g" data-key="' + esc(g.key) + '">' + pic + '<span class="w"><b>' + esc(g.name) + '</b><small>' + esc(g.source) + ' · ' + ago(g.last_played) + '</small></span><span class="play">PLAY</span></button>';
    }).join('') : '<div class="empty">' + (st.games.length ? 'Nothing matches.' : 'No games found. Toolbelt looks in Playnite, Steam and HoYoPlay.') + '</div>';
    Array.prototype.forEach.call(document.querySelectorAll('[data-key]'), function (b) {
      b.onclick = function () { api('play_game', b.getAttribute('data-key')).then(function (r) { if (r.ok) api('popup_hide'); else b.querySelector('small').textContent = r.message; }).catch(function () {}); };
    });
  }
  function load() {
    return Promise.all([api('settings'), api('info'), api('games')]).then(function (r) {
      st.logos = (r[1] && r[1].logos) || {};
      applyLook(r[0] || {});
      st.games = r[2] || [];
      render();
    });
  }
  $('#q').addEventListener('input', function () { st.q = $('#q').value; render(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') api('popup_hide').catch(function () {}); });
  $('#lib').onclick = function () { api('show_main', 'games').catch(function () {}); };
  $('#main').onclick = function () { api('show_main', '').catch(function () {}); };
  // the internet switch (17 Oct), the same one as in the main window's top bar
  var net = { state: 'on', installed: false, busy: false };
  function netPaint() {
    var s = net.busy ? 'busy' : net.state;
    $('#net').setAttribute('data-state', s);
    $('#netTxt').textContent = { on: 'Online', off: 'Offline', nocable: 'No connection', busy: 'Switching…' }[s];
  }
  function netPoll() { if (net.busy) return; api('net_state').then(function (r) { net.state = r.state; net.installed = r.installed; netPaint(); }).catch(function () {}); }
  $('#net').onclick = function () {
    if (net.busy) return;
    if (!net.installed) { api('show_main', 'settings').catch(function () {}); return; }
    net.busy = true; netPaint();
    api('net_set', net.state === 'off').then(function (r) { net.busy = false; if (r.state) net.state = r.state; netPaint(); }).catch(function () { net.busy = false; netPaint(); });
  };
  setInterval(netPoll, 3000);
  window.toolbeltPopup = { reload: function () { $('#q').value = ''; st.q = ''; netPoll(); return load().then(function () { $('#q').focus(); }); }, state: function () { return { games: st.games.length, look: st.look, net: net.state }; } };
  function start() { load().catch(function () { setTimeout(start, 400); }); }
  if (window.pywebview && window.pywebview.api) start(); else window.addEventListener('pywebviewready', start);
})();
