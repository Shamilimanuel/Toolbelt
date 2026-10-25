/* The calculator device: the natural display, the Casio / TI-style keys, memory and keyboard. Shared by the Calculator
   screen (app.js) and the floating mini window (calcpop.js). Needs calc.js first.
   window.calcDevice = { KEYS, fresh(), render(st, opts), wire(container, st, hooks), run(st) } */
(function () {
  'use strict';
  var C = function () { return window.calc; };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  // The keys, laid out like the Casio fx-82 / TI-30X: 5 across. `sh` is what SHIFT turns the key into (the small label above it).
  var KEYS = [
    { id: 'shift', label: 'SHIFT', cls: 'fn shiftkey' }, { id: 'left', label: '◀', do: 'left', cls: 'fn' }, { id: 'right', label: '▶', do: 'right', cls: 'fn' }, { id: 'del', label: 'DEL', do: 'del', cls: 'warn' }, { id: 'ac', label: 'AC', do: 'ac', cls: 'warn' },
    { id: 'sq', label: 'x²', ins: '^2', cls: 'fn', sh: { label: 'x³', ins: '^3' } }, { id: 'pow', label: 'x<sup>▢</sup>', ins: '^', cls: 'fn', sh: { label: 'ⁿ√', ins: 'root(', title: 'root(n, x)' } }, { id: 'sqrt', label: '√▢', ins: '√(', cls: 'fn', sh: { label: '∛', ins: '∛(' } }, { id: 'frac', label: '▢/▢', ins: '/', cls: 'fn', sh: { label: 'a b/c', do: 'format' } }, { id: 'neg', label: '(−)', ins: '-', cls: 'fn', sh: { label: '|x|', ins: 'abs(' } },
    { id: 'sin', label: 'sin', ins: 'sin(', cls: 'fn', sh: { label: 'sin⁻¹', ins: 'asin(' } }, { id: 'cos', label: 'cos', ins: 'cos(', cls: 'fn', sh: { label: 'cos⁻¹', ins: 'acos(' } }, { id: 'tan', label: 'tan', ins: 'tan(', cls: 'fn', sh: { label: 'tan⁻¹', ins: 'atan(' } }, { id: 'log', label: 'log', ins: 'log(', cls: 'fn', sh: { label: '10<sup>x</sup>', ins: '10^' } }, { id: 'ln', label: 'ln', ins: 'ln(', cls: 'fn', sh: { label: 'e<sup>x</sup>', ins: 'e^' } },
    { id: 'pi', label: 'π', ins: 'π', cls: 'fn', sh: { label: 'e', ins: 'e' } }, { id: 'ans', label: 'Ans', ins: 'ans', cls: 'fn' }, { id: 'inv', label: 'x⁻¹', ins: '^-1', cls: 'fn', sh: { label: 'x!', ins: '!' } }, { id: 'open', label: '(', ins: '(', cls: 'fn' }, { id: 'close', label: ')', ins: ')', cls: 'fn' },
    { id: 'mc', label: 'MC', do: 'mc', cls: 'fn mem' }, { id: 'mr', label: 'MR', do: 'mr', cls: 'fn mem' }, { id: 'mplus', label: 'M+', do: 'mplus', cls: 'fn mem' }, { id: 'mminus', label: 'M−', do: 'mminus', cls: 'fn mem' }, { id: 'copy', label: 'COPY', do: 'copy', cls: 'fn', title: 'Copy the answer (Ctrl+C with nothing selected does it too)' },
    { id: '7', label: '7', ins: '7' }, { id: '8', label: '8', ins: '8' }, { id: '9', label: '9', ins: '9' }, { id: 'mul', label: '×', ins: '×', cls: 'op' }, { id: 'div', label: '÷', ins: '÷', cls: 'op' },
    { id: '4', label: '4', ins: '4' }, { id: '5', label: '5', ins: '5' }, { id: '6', label: '6', ins: '6' }, { id: 'add', label: '+', ins: '+', cls: 'op' }, { id: 'sub', label: '−', ins: '-', cls: 'op' },
    { id: '1', label: '1', ins: '1' }, { id: '2', label: '2', ins: '2' }, { id: '3', label: '3', ins: '3' }, { id: 'format', label: 'FORMAT', do: 'format', cls: 'op small', sh: { label: 'table', do: 'table' } }, { id: 'sd', label: 'S⇔D', do: 'sd', cls: 'op small' },
    { id: '0', label: '0', ins: '0' }, { id: 'dot', label: '.', ins: '.', sh: { label: ',', ins: ',' } }, { id: 'exp', label: '×10<sup>n</sup>', ins: '×10^', cls: 'digit small', sh: { label: '%', ins: '%' } }, { id: 'eq', label: '=', do: 'eq', cls: 'eq' }, null];

  function fresh() { return { expr: '', out: null, err: '', hist: [], mode: 'exact', deg: true, ans: null, shift: false, mem: null }; }
  function load(st, key) {
    try { var cs = JSON.parse(localStorage.getItem(key || 'toolbelt-calc') || '{}'); if (Array.isArray(cs.hist)) st.hist = cs.hist.slice(0, 30); if (cs.mode) st.mode = cs.mode; if (typeof cs.deg === 'boolean') st.deg = cs.deg; if (cs.mem) st.mem = cs.mem; } catch (e) {}
    return st;
  }
  function save(st, key) { try { localStorage.setItem(key || 'toolbelt-calc', JSON.stringify({ hist: st.hist.slice(0, 30), mode: st.mode, deg: st.deg, mem: st.mem })); } catch (e) {} }
  function run(st) {
    var text = st.expr.trim();
    if (!text) { st.out = null; st.err = ''; return; }
    try {
      var env = {}; if (st.ans !== null) env.ans = st.ans; if (st.mem !== null) env.m = memValue(st);
      var v = C().evaluate(C().parse(text.replace(/\bans\b/gi, '(ans)')), env, { degrees: st.deg });
      st.out = v; st.err = ''; st.ans = v;
      var line = { e: text, r: C().format(v) };
      if (!st.hist.length || st.hist[0].e !== line.e) st.hist.unshift(line);
      st.hist = st.hist.slice(0, 30);
    } catch (e) { st.out = null; st.err = e.message; }
  }
  function memValue(st) { try { return C().calc(st.mem); } catch (e) { return null; } }
  function answerText(st) { return st.out === null ? '' : C().format(st.out, st.mode === 'decimal' ? 'decimal' : 'exact'); }

  function render(st, opts) {
    opts = opts || {};
    var shown = st.out !== null ? C().htmlValue(st.out, st.mode) : '';
    var dec = st.out !== null && st.mode !== 'decimal' ? C().decimalOf(st.out) : '';
    return '<div class="casio' + (opts.compact ? ' compact' : '') + '">' +
      '<div class="cdisp"><div class="cind"><span' + (st.shift ? ' class="on"' : '') + '>S</span><span class="on">' + (st.deg ? 'D' : 'R') + '</span><span' + (st.mem !== null ? ' class="on"' : '') + '>M</span><span class="on">' + (st.mode === 'decimal' ? 'Decimal' : st.mode === 'mixed' ? 'a b/c' : 'd/c') + '</span></div>' +
      '<div class="cnat medit dev" id="cNat" tabindex="0" role="textbox" aria-label="Sum" data-expr="' + esc(st.expr) + '"></div>' +
      '<div class="cout" id="cRes">' + (st.err ? '<span class="err">' + esc(st.err) + '</span>' : shown ? '<span class="big">' + shown + '</span>' + (dec && dec !== C().format(st.out) ? '<span class="dec">≈ ' + esc(dec) + '</span>' : '') : '') + '</div></div>' +
      '<div class="ckeys">' + KEYS.map(function (k, i) {
        // two zones like a real Casio: small function keys on top, big number keys below a divider
        var numZone = i >= KEYS.indexOf(KEYS.filter(function (x) { return x && x.id === '7'; })[0]);
        var cls = (k && k.cls) || (k ? 'digit' : '');
        var key = k ? '<button type="button" class="ckey ' + cls + (numZone ? ' num' : '') + (st.shift && k.sh ? ' shifted' : '') + '" data-ck="' + esc(k.id) + '"' + (k.title ? ' title="' + esc(k.title) + '"' : '') + '>' + (k.sh ? '<small class="sh">' + k.sh.label + '</small>' : '<small class="sh">&nbsp;</small>') + '<span>' + k.label + '</span></button>' : '<span></span>';
        return (k && k.id === '7' ? '<span class="ckdiv"></span>' : '') + key;
      }).join('') + '</div>' +
      (opts.noFooter ? '' : '<div class="row sb"><div class="row">' + [[true, 'Graden (D)'], [false, 'Radialen (R)']].map(function (m) { return '<button type="button" class="chip" data-cdeg="' + m[0] + '" aria-pressed="' + (st.deg === m[0]) + '">' + m[1] + '</button>'; }).join('') + '</div>' +
      '<span class="muted">SHIFT = the small labels · FORMAT = breuk / gemengd / decimaal · S⇔D = breuk ⇄ decimaal · M = geheugen</span></div>') + '</div>';
  }

  function wire(m, st, hooks) {
    // The display is a natural-input box (mathedit.js, 25 Oct: "really like" his fx-82): ▢/▢ makes a stacked fraction
    // to type into, √ and powers get their shapes. st.expr stays the sum as text (history, Ans, the Tabel tab).
    hooks = hooks || {};
    var nat = $('#cNat', m); if (!nat) return;
    var rerender = function () { if (hooks.rerender) hooks.rerender(); };
    var persist = function () { save(st, hooks.storeKey); if (hooks.save) hooks.save(); };
    st.edit = st.edit || {};
    var ed = window.mathEdit.create(st.edit, { letters: true });
    var sync = function () { st.expr = ed.text(); st.edit.text = st.expr; nat.setAttribute('data-expr', st.expr); };
    if (st.edit.text !== st.expr) ed.set(st.expr);              // the sum was changed from outside (a history line, AC)
    ed.mount(nat, sync);
    sync();
    nat.focus();
    nat.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); run(st); persist(); rerender(); }
      else if (e.key === 'Escape') { st.out = null; st.err = ''; rerender(); }            // the box itself has emptied already
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && window.getSelection().isCollapsed && st.out !== null) { e.preventDefault(); if (hooks.copy) hooks.copy(answerText(st)); }
    });
    function insert(ins) {                                      // what a key puts in, as shapes where the Casio has them
      if (ins === '/') ed.key('frac');
      else if (ins === '√(') ed.key('sqrt');
      else if (ins === '^') ed.key('pow');
      else if (ins.charAt(0) === '^') ed.pow(ins.slice(1));   // x², x³, x⁻¹
      else if (ins.length > 1 && ins.slice(-1) === '^') { ins.slice(0, -1).split('').forEach(function (c) { ed.key(c); }); ed.key('pow'); }   // 10^▢, e^▢, ×10^▢
      else ins.split('').forEach(function (c) { ed.key(c); });
    }
    $$('[data-ck]', m).forEach(function (b) {
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });   // the box keeps the focus (and its cursor)
      b.onclick = function () {
        var key = KEYS.filter(function (k) { return k && k.id === b.getAttribute('data-ck'); })[0]; if (!key) return;
        var k = st.shift && key.sh ? key.sh : key;
        if (key.id === 'shift') { st.shift = !st.shift; rerender(); return; }
        var wasShift = st.shift; st.shift = false;
        if (k.do === 'eq') { run(st); persist(); rerender(); return; }
        if (k.do === 'ac') { ed.clear(); st.out = null; st.err = ''; rerender(); return; }
        if (k.do === 'del' || k.do === 'left' || k.do === 'right') { ed.key(k.do); ed.focus(); return; }
        if (k.do === 'format') { st.mode = st.mode === 'exact' ? 'mixed' : st.mode === 'mixed' ? 'decimal' : 'exact'; persist(); rerender(); return; }
        if (k.do === 'sd') { st.mode = st.mode === 'decimal' ? 'exact' : 'decimal'; persist(); rerender(); return; }
        if (k.do === 'table') { if (hooks.table) hooks.table(st.expr.trim()); return; }
        if (k.do === 'copy') { if (hooks.copy && st.out !== null) hooks.copy(answerText(st)); return; }
        if (k.do === 'mc') { st.mem = null; persist(); rerender(); return; }
        if (k.do === 'mr') { if (st.mem !== null) { ed.insert(st.mem.indexOf('-') === 0 ? '(' + st.mem + ')' : st.mem); ed.focus(); } return; }
        if (k.do === 'mplus' || k.do === 'mminus') {
          if (st.expr.trim()) run(st);                            // what is typed now, not an older answer
          if (st.out === null) { rerender(); return; }
          try { var cur = st.mem === null ? C().R(0n) : C().calc(st.mem); var next = C().calc('(' + C().format(cur) + ')' + (k.do === 'mplus' ? '+' : '-') + '(' + C().format(st.out) + ')'); st.mem = C().format(next); } catch (e) { st.err = e.message; }
          persist(); rerender(); return;
        }
        insert(k.ins);
        if (key.sh && wasShift) rerender(); else ed.focus();
      };
    });
    $$('[data-cdeg]', m).forEach(function (b) { b.onclick = function () { st.deg = b.getAttribute('data-cdeg') === 'true'; persist(); if (st.expr) run(st); rerender(); }; });
  }

  window.calcDevice = { KEYS: KEYS, fresh: fresh, load: load, save: save, run: run, render: render, wire: wire, answerText: answerText, memValue: memValue };
})();
