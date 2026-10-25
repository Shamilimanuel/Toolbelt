/* The floating mini calculator's script: the shared device (device.js) in a small always-on-top window. */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  function api(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[name]) return Promise.reject(new Error('not connected'));
    return window.pywebview.api[name].apply(null, args);
  }
  var st = window.calcDevice.load(window.calcDevice.fresh());
  function applyLook(settings, logos) {
    var look = settings.look || 'cartridge';
    $('#root').className = look === 'cartridge' ? 'look-cartridge' : look === 'glass' ? 'look-glass' : 'look-glass glass-dark';
    if (settings.accent) $('#root').style.setProperty('--accent', settings.accent); else $('#root').style.removeProperty('--accent');
    if (logos && logos[look]) $('#mark').innerHTML = logos[look];
  }
  function render() {
    $('#body').innerHTML = window.calcDevice.render(st, { compact: true, noFooter: true });
    window.calcDevice.wire($('#body'), st, {
      rerender: render,
      copy: function (text) { api('copy_text', text).catch(function () {}); },
      table: function (expr) { api('show_main', 'calc').catch(function () {}); }
    });
  }
  $('#close').onclick = function () { api('calc_hide').catch(function () {}); };
  $('#full').onclick = function () { api('show_main', 'calc').catch(function () {}); };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !st.expr) api('calc_hide').catch(function () {}); });
  window.calcPop = {
    state: function () { return { expr: st.expr, mode: st.mode, keys: document.querySelectorAll('[data-ck]').length }; },
    reload: function () { st = window.calcDevice.load(window.calcDevice.fresh()); return Promise.all([api('settings'), api('info')]).then(function (r) { applyLook(r[0] || {}, (r[1] || {}).logos); render(); var ex = $('#cNat'); if (ex) ex.focus(); }); }
  };
  function start() { window.calcPop.reload().catch(function () { render(); setTimeout(start, 500); }); }
  render();
  if (window.pywebview && window.pywebview.api) start(); else window.addEventListener('pywebviewready', start);
})();
