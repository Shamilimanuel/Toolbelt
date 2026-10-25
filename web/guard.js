/* App guard's warning window (18 Oct): shows the oldest waiting question; Trust it / Just this time / Stop it. */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var busy = false, current = null;
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function api(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[name]) return Promise.reject(new Error('not connected'));
    return window.pywebview.api[name].apply(null, args);
  }
  var VERDICT = { safe: ['LOOKS SAFE', 'var(--ok)', 'var(--on)'], unknown: ['UNKNOWN: YOUR CALL', 'var(--warn)', '#1A1626'], danger: ['DANGER', 'var(--bad)', '#fff'] };
  var MARK = { ok: ['✓', 'var(--ok)'], warn: ['!', 'var(--warn)'], bad: ['✕', 'var(--bad)'] };
  function applyLook(s) {
    var look = s.look || 'cartridge';
    $('#root').className = look === 'cartridge' ? 'look-cartridge' : look === 'glass' ? 'look-glass' : 'look-glass glass-dark';
    if (s.accent) $('#root').style.setProperty('--accent', s.accent);
  }
  function render(list) {
    current = list[0] || null;
    if (!current) { $('#bar').style.background = 'transparent'; $('#card').innerHTML = '<span class="gnote">Nothing to decide.</span>'; return; }
    var v = VERDICT[current.verdict] || VERDICT.unknown, ext = (current.name.split('.').pop() || 'EXE').toUpperCase().slice(0, 4);
    $('#bar').style.background = v[1];
    if (current.kind === 'notice') {                         // a note (a USB stick was checked, a risky download): its own buttons
      var LABEL = { show: ['Show in Toolbelt', 'btn'], ok: ['OK', 'btn ghost'], quarantine: ['Quarantine', 'btn danger'], keep: ['Keep it', 'btn ghost'] };
      $('#card').innerHTML = '<div class="ghead"><span class="tag acc">APP GUARD</span><span>' + esc(current.when.slice(11)) + '</span></div>' +
        '<b style="font-size:15px;overflow-wrap:anywhere">' + esc(current.name) + '</b>' +
        (current.verdict === 'danger' ? '<div class="verdict" style="background:' + v[1] + ';color:' + v[2] + '">' + v[0] + '</div>' : '') +
        '<ul class="checks">' + current.checks.map(function (c) { var m = MARK[c[0]] || MARK.warn; return '<li><i style="color:' + m[1] + '">' + m[0] + '</i><span>' + esc(c[1]) + '</span></li>'; }).join('') + '</ul>' +
        '<div class="acts" style="grid-template-columns:repeat(' + current.actions.length + ',minmax(0,1fr))">' + current.actions.map(function (a) { return '<button type="button" class="' + LABEL[a][1] + '" data-act="' + a + '">' + LABEL[a][0] + '</button>'; }).join('') + '</div>' +
        (list.length > 1 ? '<span class="gmore">' + (list.length - 1) + ' more waiting</span>' : '');
      Array.prototype.forEach.call(document.querySelectorAll('[data-act]'), function (b) { b.onclick = function () { decide(b.getAttribute('data-act')); }; });
      return;
    }
    $('#card').innerHTML = '<div class="ghead"><span class="tag acc">APP GUARD</span><span>' + esc(current.when.slice(11)) + ' · it’s running</span></div>' +
      '<div class="gwho"><span class="ico">' + esc(ext) + '</span><div style="min-width:0"><b>' + esc(current.name) + '</b><small>' + esc(current.path) + '</small></div></div>' +
      '<div class="verdict" style="background:' + v[1] + ';color:' + v[2] + '">' + v[0] + '</div>' +
      '<ul class="checks">' + current.checks.map(function (c) { var m = MARK[c[0]] || MARK.warn; return '<li><i style="color:' + m[1] + '">' + m[0] + '</i><span>' + esc(c[1]) + '</span></li>'; }).join('') + '</ul>' +
      '<div class="acts"><button type="button" class="btn" id="aTrust">Trust it</button><button type="button" class="btn ghost" id="aOnce">Just this time</button><button type="button" class="btn danger" id="aStop">Stop it</button></div>' +
      '<span class="gnote">Stop it ends the program and puts its file in quarantine (Toolbelt > App guard can restore it).</span>' +
      (list.length > 1 ? '<span class="gmore">' + (list.length - 1) + ' more waiting</span>' : '');
    $('#aTrust').onclick = function () { decide('trust'); };
    $('#aOnce').onclick = function () { decide('once'); };
    $('#aStop').onclick = function () { decide('stop'); };
  }
  function decide(action) {
    if (busy || !current) return;
    busy = true;
    Array.prototype.forEach.call(document.querySelectorAll('.acts .btn'), function (b) { b.disabled = true; });
    api('guard_decide', current.id, action).then(function () { busy = false; return reload(); }).catch(function () { busy = false; reload(); });
  }
  function reload() {
    return Promise.all([api('settings'), api('guard_pending')]).then(function (r) { applyLook(r[0] || {}); render((r[1] && r[1].pending) || []); });
  }
  window.toolbeltGuard = { reload: reload, state: function () { return { showing: current ? current.name : '' }; } };
  setInterval(function () { if (!busy) reload().catch(function () {}); }, 1500);
  function start() { reload().catch(function () { setTimeout(start, 400); }); }
  if (window.pywebview && window.pywebview.api) start(); else window.addEventListener('pywebviewready', start);
})();
