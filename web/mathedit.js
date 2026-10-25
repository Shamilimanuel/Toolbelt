/* A Casio-style "natural input" box (his ask 25 Oct, the Breuken tab: "put it like breuken, really like", with a photo of
   his fx-82 showing 1851/250 × √36 stacked). You type straight into the shapes: the fraction key makes a stacked
   fraction with a box above and below the bar, √ gets its bar, a power is raised, a mixed number has its whole part.
   The model is a tree of rows; the cursor is a row and a place in it. text() turns it into a sum calc.js can read.
   window.mathEdit = { create(state, { letters }) } ; an editor: { mount(el, onChange), key(name), text(), set(text), insert(text), pow(text), clear(), focus() } */
(function () {
  'use strict';
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // the slots of each shape, in reading order
  var SLOTS = { frac: ['n', 'd'], mixed: ['w', 'n', 'd'], sqrt: ['b'], pow: ['e'] };
  function row(parent, key) { return { items: [], parent: parent || null, key: key || '' }; }
  function shape(t, into) { var it = { t: t, parent: into }; SLOTS[t].forEach(function (k) { it[k] = row(it, k); }); return it; }
  function isShape(it) { return it && it.t !== 'c'; }
  function empty(it) { return SLOTS[it.t].every(function (k) { return !it[k].items.length; }); }

  function create(state, opts) {
    var letters = !!(opts && opts.letters);
    // state keeps the tree between redraws of the screen (CA.fed in app.js)
    var root = state && state.root ? state.root : row(null, ''), cur = state && state.cur ? state.cur : { r: root, i: 0 };
    var el = null, onChange = null, rowsSeen = [];
    function keep() { if (state) { state.root = root; state.cur = cur; } }

    // ---------- typing ----------
    function put(it) { it.parent = cur.r; cur.r.items.splice(cur.i, 0, it); cur.i++; }
    function char(c) { put({ t: 'c', c: c }); }
    function enter(it, k, atEnd) { cur = { r: it[k], i: atEnd ? it[k].items.length : 0 }; }
    function operandLeft() {                                    // the number just left of the cursor (Casio takes it into the numerator)
      var j = cur.i, its = cur.r.items;
      if (j > 0 && its[j - 1].t === 'c' && its[j - 1].c === ')') {    // a whole (…) goes up, like the Casio
        for (var depth = 0; j > 0; j--) { var c = its[j - 1].t === 'c' ? its[j - 1].c : ''; if (c === ')') depth++; else if (c === '(' && --depth === 0) { j--; break; } }
        if (depth !== 0) j = cur.i;
      }
      while (j > 0 && ((its[j - 1].t === 'c' && /[0-9.a-zA-Zπ]/.test(its[j - 1].c)) || its[j - 1].t === 'sqrt' || its[j - 1].t === 'pow')) j--;   // 1851, ans, √36, sin(30) or 2² goes up too
      var took = its.splice(j, cur.i - j);
      cur.i = j;
      return took;
    }
    function wrapLeft(t, into, next) {                          // the shape takes the number left of the cursor into its first box
      var took = operandLeft(), it = shape(t, cur.r);
      took.forEach(function (x) { x.parent = it[into]; it[into].items.push(x); });
      put(it);
      enter(it, took.length ? next : into, false);
    }
    function frac() { wrapLeft('frac', 'n', 'd'); }
    function mixed() { wrapLeft('mixed', 'w', 'n'); }
    function slash() {                                          // the / key on the keyboard: in a top box it goes under the bar (2 1/4), else a new fraction
      var it = cur.r.parent;
      if (it && cur.r.key === 'n' && (it.t === 'frac' || it.t === 'mixed')) enter(it, 'd', false); else frac();
    }
    function sqrt() { var it = shape('sqrt', cur.r); put(it); enter(it, 'b', false); }
    function pow(text) {
      var it = shape('pow', cur.r); put(it);
      if (text) { text.split('').forEach(function (c) { it.e.items.push({ t: 'c', c: c, parent: it.e }); }); return; }   // x² : the 2 goes in and the cursor stays after
      enter(it, 'e', false);
    }

    // ---------- moving ----------
    function slotAfter(it, k, step) { var s = SLOTS[it.t], j = s.indexOf(k) + step; return j >= 0 && j < s.length ? s[j] : null; }
    function out(after) { var it = cur.r.parent, r = it.parent; cur = { r: r, i: r.items.indexOf(it) + (after ? 1 : 0) }; }
    function left() {
      if (cur.i > 0) {
        var it = cur.r.items[cur.i - 1];
        if (isShape(it)) { var s = SLOTS[it.t]; enter(it, s[s.length - 1], true); } else cur.i--;
        return;
      }
      if (!cur.r.parent) return;
      var prev = slotAfter(cur.r.parent, cur.r.key, -1);
      if (prev) enter(cur.r.parent, prev, true); else out(false);
    }
    function right() {
      if (cur.i < cur.r.items.length) {
        var it = cur.r.items[cur.i];
        if (isShape(it)) enter(it, SLOTS[it.t][0], false); else cur.i++;
        return;
      }
      if (!cur.r.parent) return;
      var next = slotAfter(cur.r.parent, cur.r.key, 1);
      if (next) enter(cur.r.parent, next, false); else out(true);
    }
    function upDown(down) {                                     // ▲ ▼ : between the top and the bottom of the nearest fraction
      var r = cur.r;
      while (r.parent) {
        var it = r.parent;
        if ((it.t === 'frac' || it.t === 'mixed') && (down ? r.key !== 'd' : r.key === 'd')) {
          var to = down ? 'd' : 'n';
          cur = { r: it[to], i: Math.min(cur.r === r ? cur.i : it[to].items.length, it[to].items.length) };
          return;
        }
        r = it.parent;
      }
    }
    function del() {
      if (cur.i > 0) {
        var it = cur.r.items[cur.i - 1];
        if (isShape(it) && !empty(it)) { left(); return; }      // a filled shape: step inside first (like the Casio)
        cur.r.items.splice(cur.i - 1, 1); cur.i--; return;
      }
      if (!cur.r.parent) return;
      var shp = cur.r.parent;
      if (empty(shp)) { out(false); cur.r.items.splice(cur.i, 1); return; }
      left();
    }
    function clear() { root.items = []; cur = { r: root, i: 0 }; }

    // ---------- the sum for calc.js ----------
    function closed(s) {                                        // "(1+2)" is one bracket from start to end; "(1)+(2)" isn't
      if (s.charAt(0) !== '(' || s.slice(-1) !== ')') return false;
      for (var i = 0, depth = 0; i < s.length; i++) { if (s[i] === '(') depth++; else if (s[i] === ')' && --depth === 0 && i < s.length - 1) return false; }
      return true;
    }
    // as few brackets as calc.js needs, so it reads well in the history: 3/4+1/8, (3/4)^2, 2^(1/2), (1+1/2)
    function text(r) {
      r = r || root;
      var simple = function (s) { return /^[0-9.]+$|^[a-zA-Zπ]+$/.test(s) || closed(s) ? s : '(' + s + ')'; };
      return r.items.map(function (it, i) {
        if (it.t === 'c') return it.c === '−' ? '-' : it.c;
        var n, d;
        if (it.t === 'frac' || it.t === 'mixed') {
          n = simple(text(it.n) || '0'); d = simple(text(it.d) || '0');
          if (it.t === 'mixed') return '(' + (text(it.w) || '0') + '+' + n + '/' + d + ')';
          var prev = r.items[i - 1], next = r.items[i + 1];
          var alone = (!prev || (prev.t === 'c' && /[+\-×÷(,]/.test(prev.c))) && (!next || (next.t !== 'pow' && !(next.t === 'c' && /[!%]/.test(next.c))));
          return alone ? n + '/' + d : '(' + n + '/' + d + ')';
        }
        if (it.t === 'sqrt') return '√(' + (text(it.b) || '0') + ')';
        var e = text(it.e) || '0';
        return '^' + (/^[0-9]+$|^[a-zπ]$/.test(e) ? e : '(' + e + ')');
      }).join('');
    }
    function hasEmpty(r) { r = r || root; return r.items.some(function (it) { return isShape(it) && SLOTS[it.t].some(function (k) { return !it[k].items.length || hasEmpty(it[k]); }); }); }

    // ---------- drawing ----------
    var CARET = '<i class="mcar"></i>';
    function draw(r) {
      var id = rowsSeen.push(r) - 1, html = '', here = cur.r === r;
      if (!r.items.length) return '<span class="mslot' + (here ? ' on' : '') + '" data-mr="' + id + '" data-mi="0">' + (here ? CARET : '') + '</span>';
      r.items.forEach(function (it, i) {
        if (here && cur.i === i) html += CARET;
        if (it.t === 'c') { html += '<span class="mch" data-mr="' + id + '" data-mi="' + (i + 1) + '">' + esc({ '*': '×', '/': '÷', '-': '−' }[it.c] || it.c) + '</span>'; return; }
        if (it.t === 'frac') html += '<span class="fr"><span class="nu">' + draw(it.n) + '</span><span class="de">' + draw(it.d) + '</span></span>';
        else if (it.t === 'mixed') html += '<span class="mmix">' + draw(it.w) + '<span class="fr"><span class="nu">' + draw(it.n) + '</span><span class="de">' + draw(it.d) + '</span></span></span>';
        else if (it.t === 'sqrt') html += '<span class="sq">√<span class="rad">' + draw(it.b) + '</span></span>';
        else html += '<sup class="mpow">' + draw(it.e) + '</sup>';
      });
      if (here && cur.i === r.items.length) html += CARET;
      return '<span class="mrow" data-mr="' + id + '" data-mi="' + r.items.length + '">' + html + '</span>';
    }
    function paint() {
      if (!el) return;
      rowsSeen = [];
      el.innerHTML = draw(root);
      keep();
    }
    function changed() { paint(); if (onChange) onChange(); }

    var KEYS = {
      frac: frac, mixed: mixed, slash: slash, sqrt: sqrt, pow: function () { pow(''); }, sq: function () { pow('2'); },
      left: left, right: right, up: function () { upDown(false); }, down: function () { upDown(true); }, del: del, ac: clear
    };
    function key(name) {
      if (KEYS[name]) KEYS[name]();
      else if (name.length === 1) char(name);
      changed();
    }
    function numberLeft() { var it = cur.r.items[cur.i - 1]; return it && it.t === 'c' && /[0-9]/.test(it.c); }
    function onKey(e) {
      // Breuken: x is ×, w / r a root, g a mixed number. With letters on (Rekenen, the mini): letters are letters (2x, sin, ans)
      var k = e.key, map = { '/': 'slash', ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Backspace: 'del', Escape: 'ac', '^': 'pow', '*': '×', ':': '÷', '√': 'sqrt' };
      if (e.ctrlKey || e.metaKey || e.altKey || k === 'Enter' || k === 'Tab') return;
      if (map[k]) { e.preventDefault(); key(map[k]); return; }
      if (k === ' ') { e.preventDefault(); if (numberLeft()) key('mixed'); return; }   // 2 1/4: a space after a number starts a mixed number
      if (letters) { if (/^[a-zA-Zπ!%]$/.test(k)) { e.preventDefault(); key(k); return; } }
      else if (k === 'x') { e.preventDefault(); key('×'); return; }
      else if (k === 'r' || k === 'w') { e.preventDefault(); key('sqrt'); return; }   // r for root, w for wortel
      else if (k === 'g') { e.preventDefault(); key('mixed'); return; }               // g for gemengd
      if (/^[0-9.,+\-()÷×]$/.test(k)) { e.preventDefault(); key(k === ',' && !letters ? '.' : k); }
    }
    function onPaste(e) {
      var t = e.clipboardData && e.clipboardData.getData('text');
      if (!t) return;
      e.preventDefault(); insert(t.trim()); changed();
    }

    // ---------- text in: a sum calc.js can read becomes shapes (the history, Ans, MR, pasting) ----------
    var PREC = { '+': 1, '-': 1, '*': 2, '/': 2, 'neg': 3, '^': 4, '!': 5, '%': 5 };
    function prec(n) { return n.op === '/' && !n.school ? 4.5 : n.op ? PREC[n.op] : 6; }   // a stacked fraction needs brackets only as a power's base
    function chars(r, s) { String(s).split('').forEach(function (c) { r.items.push({ t: 'c', c: c, parent: r }); }); }
    function build(n, r) {
      function wrap(x, need) { if (prec(x) < need) { chars(r, '('); build(x, r); chars(r, ')'); } else build(x, r); }
      var it;
      if (n.num !== undefined) return chars(r, n.num);
      if (n.konst) return chars(r, n.konst === 'e' ? 'e' : 'π');
      if (n.v !== undefined) return chars(r, n.v);
      if (n.fn === 'sqrt') { it = shape('sqrt', r); build(n.args[0], it.b); r.items.push(it); return; }
      if (n.fn) {
        chars(r, { cbrt: '∛' }[n.fn] || n.fn); chars(r, '(');
        n.args.forEach(function (a, i) { if (i) chars(r, ','); build(a, r); });
        return chars(r, ')');
      }
      if (n.op === 'neg') { chars(r, '-'); return wrap(n.a, 3); }
      if (n.op === '!' || n.op === '%') { wrap(n.a, 5); return chars(r, n.op); }
      if (n.op === '/' && !n.school) { it = shape('frac', r); build(n.a, it.n); build(n.b, it.d); r.items.push(it); return; }
      if (n.op === '^') { wrap(n.a, 5); it = shape('pow', r); build(n.b, it.e); r.items.push(it); return; }
      if (n.op === '*' || n.op === '/') { wrap(n.a, 2); if (!n.implicit) chars(r, n.op === '/' ? '÷' : '×'); return wrap(n.b, n.implicit && n.b.op === '/' ? 6 : 3); }
      build(n.a, r); chars(r, n.op); wrap(n.b, 2);
    }
    function insert(t) {                                        // at the cursor; half a sum like sin( goes in as plain characters
      var tmp = row(null, ''), tree = null;
      try { tree = window.calc.parse(t); } catch (e) {}
      if (tree) build(tree, tmp); else chars(tmp, t);
      tmp.items.forEach(function (x) { put(x); });
    }
    function set(textIn) {                                      // replaces everything: 1 1/2 + 2/3 (mixed), (1/2)^3, √36, 2×(3/4)
      clear();
      if (/\d \d+\/\d/.test(textIn)) {                          // calc.js can't read a mixed number, so these go by hand
        var re = /(\d+) (\d+)\/(\d+)|(\d+(?:[.,]\d+)?)\/(\d+(?:[.,]\d+)?)|(\s)|(.)/g, m;
        while ((m = re.exec(textIn))) {
          var it;
          if (m[1]) { it = shape('mixed', cur.r); chars(it.w, m[1]); chars(it.n, m[2]); chars(it.d, m[3]); put(it); }
          else if (m[4]) { it = shape('frac', cur.r); chars(it.n, m[4]); chars(it.d, m[5]); put(it); }
          else if (m[7]) char(m[7] === '−' ? '-' : m[7]);
        }
      } else if (String(textIn).trim()) insert(String(textIn).replace(/−/g, '-').trim());
      changed();
    }
    function onClick(e) {
      var t = e.target.closest('[data-mr]');
      el.focus();
      if (!t || !rowsSeen[+t.getAttribute('data-mr')]) return;
      cur = { r: rowsSeen[+t.getAttribute('data-mr')], i: +t.getAttribute('data-mi') };
      paint(); el.focus();
    }
    function mount(node, cb) {
      el = node; onChange = cb;
      el.addEventListener('keydown', onKey);
      el.addEventListener('paste', onPaste);
      el.addEventListener('mousedown', function (e) { e.preventDefault(); onClick(e); });
      paint();
    }
    keep();
    return { mount: mount, key: key, text: function () { return text(); }, hasEmpty: function () { return hasEmpty(); }, clear: function () { clear(); changed(); }, set: set,
      insert: function (t) { insert(t); changed(); }, pow: function (t) { pow(t); changed(); }, focus: function () { if (el) el.focus(); } };
  }

  window.mathEdit = { create: create };
})();
