/* Toolbelt's maths engine (step 10, 14 Oct 2026). Plain JavaScript, no library.
   - Numbers are kept EXACT as fractions (BigInt numerator / denominator) as long as the maths allows it:
     1/3 + 1/6 stays 1/2, √9 stays 3, 2^10 stays 1024. Anything else (√2, sin 30°, 2^0.5) becomes a decimal.
   - It reads what you type the way a school calculator would: 2x, 3(4+5), 2², √16, 20%, 5!, π, root(3, 27).
   - Used by the Calculator screen in app.js for sums, fractions with steps, tables, equations and graphs.
   window.calc = { parse, evaluate, format, Rational, fractionSteps, solve, table, times } */
(function () {
  'use strict';

  // ---------- exact fractions ----------
  function bgcd(a, b) { a = a < 0n ? -a : a; b = b < 0n ? -b : b; while (b) { var t = a % b; a = b; b = t; } return a; }
  function R(n, d) {                                             // a fraction n/d, always reduced, d > 0
    d = d === undefined ? 1n : d;
    if (d === 0n) throw new Error('Delen door nul kan niet (division by zero).');
    if (d < 0n) { n = -n; d = -d; }
    var g = bgcd(n, d) || 1n;
    return { n: n / g, d: d / g, exact: true };
  }
  function isR(v) { return v && v.exact === true; }
  function toNum(v) { return isR(v) ? Number(v.n) / Number(v.d) : v; }
  function fromNumber(x) {                                       // a typed decimal like 0.25 becomes 1/4 exactly
    if (!isFinite(x)) throw new Error('That number is too big.');
    if (Math.floor(x) === x && Math.abs(x) < 1e15) return R(BigInt(x));
    var s = String(x);
    if (/e/i.test(s)) return x;
    var parts = s.split('.'), digits = parts[1].length;
    if (digits > 12) return x;
    return R(BigInt(parts[0] + parts[1]) * (x < 0 && parts[0] === '-0' ? -1n : 1n), 10n ** BigInt(digits));
  }
  function add(a, b) { return isR(a) && isR(b) ? R(a.n * b.d + b.n * a.d, a.d * b.d) : toNum(a) + toNum(b); }
  function sub(a, b) { return isR(a) && isR(b) ? R(a.n * b.d - b.n * a.d, a.d * b.d) : toNum(a) - toNum(b); }
  function mul(a, b) { return isR(a) && isR(b) ? R(a.n * b.n, a.d * b.d) : toNum(a) * toNum(b); }
  function div(a, b) {
    if (isR(a) && isR(b)) return R(a.n * b.d, a.d * b.n);
    if (toNum(b) === 0) throw new Error('Delen door nul kan niet (division by zero).');
    return toNum(a) / toNum(b);
  }
  function neg(a) { return isR(a) ? R(-a.n, a.d) : -a; }
  function isInt(v) { return isR(v) ? v.d === 1n : Number.isInteger(v); }
  function bigRoot(n, k) {                                       // exact k-th root of a BigInt, or null
    if (n < 0n) return null;
    if (n < 2n) return n;
    var x = BigInt(Math.round(Math.pow(Number(n), 1 / k)));
    for (var c = x - 1n; c <= x + 1n; c++) if (c >= 0n && c ** BigInt(k) === n) return c;
    return null;
  }
  function root(v, k) {                                          // k-th root, exact when it comes out whole (√(4/9) = 2/3)
    k = toNum(k);
    if (!Number.isInteger(k) || k < 1) throw new Error('A root needs a whole number like 2 or 3.');
    var x = toNum(v);
    if (x < 0 && k % 2 === 0) throw new Error('De wortel van een negatief getal bestaat niet (no real root of a negative number).');
    if (isR(v)) {
      var sign = v.n < 0n ? -1n : 1n, rn = bigRoot(sign * v.n, k), rd = bigRoot(v.d, k);
      if (rn !== null && rd !== null) return R(sign * rn, rd);
    }
    return x < 0 ? -Math.pow(-x, 1 / k) : Math.pow(x, 1 / k);
  }
  function pow(a, b) {
    if (isR(a) && isR(b) && b.d === 1n) {                        // whole exponent: stays exact
      var e = b.n < 0n ? -b.n : b.n;
      if (e > 4000n) throw new Error('That power is too big to write out.');
      var n = a.n ** e, d = a.d ** e;
      return b.n < 0n ? R(d, n) : R(n, d);
    }
    if (isR(a) && isR(b) && b.d <= 12n) {                        // a^(p/q) = (q-th root of a)^p, exact if it can be
      var r = root(a, Number(b.d));
      if (isR(r)) return pow(r, R(b.n));
    }
    var x = toNum(a), y = toNum(b);
    if (x < 0 && !Number.isInteger(y)) throw new Error('A negative number to a broken power has no real answer.');
    var out = Math.pow(x, y);
    if (!isFinite(out)) throw new Error('That power is too big.');
    return out;
  }
  function fact(v) {
    var x = toNum(v);
    if (!Number.isInteger(x) || x < 0) throw new Error('Faculteit (!) works on whole numbers from 0 up.');
    if (x > 400) throw new Error('That factorial is too big to write out.');
    var out = 1n; for (var i = 2n; i <= BigInt(x); i++) out *= i;
    return R(out);
  }

  // ---------- reading what was typed ----------
  var FUNCS = {
    sqrt: function (a) { return root(a[0], 2); }, cbrt: function (a) { return root(a[0], 3); }, root: function (a) { if (a.length < 2) throw new Error('root needs two numbers: root(3, 27).'); return root(a[1], a[0]); },
    abs: function (a) { var v = a[0]; return isR(v) ? R(v.n < 0n ? -v.n : v.n, v.d) : Math.abs(v); },
    floor: function (a) { return fromNumber(Math.floor(toNum(a[0]))); }, ceil: function (a) { return fromNumber(Math.ceil(toNum(a[0]))); }, round: function (a) { return fromNumber(Math.round(toNum(a[0]))); },
    min: function (a) { return a.reduce(function (m, v) { return toNum(v) < toNum(m) ? v : m; }); }, max: function (a) { return a.reduce(function (m, v) { return toNum(v) > toNum(m) ? v : m; }); },
    ln: function (a) { return Math.log(toNum(a[0])); }, log: function (a) { return a.length > 1 ? Math.log(toNum(a[1])) / Math.log(toNum(a[0])) : Math.log10(toNum(a[0])); },
    exp: function (a) { return Math.exp(toNum(a[0])); }, fact: function (a) { return fact(a[0]); },
    sin: function (a, deg) { return trig(Math.sin, a[0], deg); }, cos: function (a, deg) { return trig(Math.cos, a[0], deg); }, tan: function (a, deg) { return trig(Math.tan, a[0], deg); },
    asin: function (a, deg) { return atrig(Math.asin, a[0], deg); }, acos: function (a, deg) { return atrig(Math.acos, a[0], deg); }, atan: function (a, deg) { return atrig(Math.atan, a[0], deg); }
  };
  function trig(fn, v, deg) { var x = toNum(v); var out = fn(deg ? x * Math.PI / 180 : x); return Math.abs(out) < 1e-12 ? 0 : Math.abs(Math.round(out) - out) < 1e-12 ? Math.round(out) : out; }
  function atrig(fn, v, deg) { var out = fn(toNum(v)); if (isNaN(out)) throw new Error('That is outside what this function can take (between -1 and 1).'); return deg ? out * 180 / Math.PI : out; }
  var CONSTS = { pi: Math.PI, 'π': Math.PI, e: Math.E };

  function tokenize(text) {
    var s = String(text).replace(/(\d),(\d)/g, '$1.$2').replace(/[−–]/g, '-').replace(/:/g, '÷').replace(/\s+/g, '');   // 1,5 is a decimal; root(3, 27) keeps its comma
    s = s.replace(/²/g, '^2').replace(/³/g, '^3');
    var out = [], i = 0;
    while (i < s.length) {
      var c = s[i];
      if (/[0-9.]/.test(c)) { var m = s.slice(i).match(/^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i); out.push({ t: 'num', v: m[0] }); i += m[0].length; continue; }
      if (c === '√') { out.push({ t: 'id', v: 'sqrt' }); i++; continue; }
      if (c === '∛') { out.push({ t: 'id', v: 'cbrt' }); i++; continue; }
      if (c === 'π') { out.push({ t: 'id', v: 'π' }); i++; continue; }
      if (/[a-zA-Z_]/.test(c)) {                                 // a word; "cos60" is cos followed by 60, "x2" is x·2
        var w = s.slice(i).match(/^[a-zA-Z_]+/)[0];
        var known = Object.keys(FUNCS).concat(Object.keys(CONSTS)).filter(function (k) { return w.toLowerCase().indexOf(k) === 0; }).sort(function (a, b) { return b.length - a.length; })[0];
        if (known && w.length > known.length && !FUNCS[w.toLowerCase()] && !CONSTS.hasOwnProperty(w.toLowerCase())) w = w.slice(0, known.length);
        out.push({ t: 'id', v: w }); i += w.length; continue;
      }
      if (c === '×' || c === '÷') { out.push({ t: c }); i++; continue; }       // the school signs bind looser than the fraction bar: 2/3 ÷ 4/5
      if ('+-*/^(),!%'.indexOf(c) !== -1) { out.push({ t: c }); i++; continue; }
      throw new Error('Unknown symbol: ' + c);
    }
    return out;
  }
  function parse(text) {                                         // returns a small tree; evaluate() walks it
    var toks = tokenize(text), p = 0;
    if (!toks.length) throw new Error('Type a sum first.');
    function peek() { return toks[p]; }
    function take(t) { var k = toks[p]; if (!k || (t && k.t !== t)) throw new Error(t ? 'Expected ' + t + (k ? ' but found ' + (k.v || k.t) : ' at the end') : 'Unexpected end'); p++; return k; }
    function expr() { var a = school(); while (peek() && (peek().t === '+' || peek().t === '-')) { var op = take().t; a = { op: op, a: a, b: school() }; } return a; }
    function school() {                                          // × and ÷ between whole fractions: 2/3 ÷ 4/5 = (2/3) ÷ (4/5)
      var a = term();
      while (peek() && (peek().t === '×' || peek().t === '÷')) { var op = take().t === '×' ? '*' : '/'; a = { op: op, a: a, b: term(), school: true }; }   // school: drawn as × ÷, not stacked
      return a;
    }
    function startsValue(k) { return k && (k.t === 'num' || k.t === 'id' || k.t === '('); }
    function term() {
      var a = unary();
      while (peek() && (peek().t === '*' || peek().t === '/' || startsValue(peek()))) {
        if (peek().t === '*' || peek().t === '/') { var op = take().t; a = { op: op, a: a, b: unary() }; }
        else a = { op: '*', a: a, b: unary(), implicit: true };   // 2x, 3(4+5), (1+2)(3+4)
      }
      return a;
    }
    function unary() { if (peek() && peek().t === '-') { take(); return { op: 'neg', a: unary() }; } if (peek() && peek().t === '+') { take(); return unary(); } return power(); }
    function power() { var a = postfix(); if (peek() && peek().t === '^') { take(); return { op: '^', a: a, b: unary() }; } return a; }
    function postfix() {
      var a = primary();
      while (peek() && (peek().t === '!' || peek().t === '%')) { var op = take().t; a = { op: op, a: a }; }
      return a;
    }
    function primary() {
      var k = take();
      if (k.t === 'num') return { num: k.v };
      if (k.t === '(') { var e = expr(); take(')'); return e; }
      if (k.t === 'id') {
        var name = k.v.toLowerCase();
        if (peek() && peek().t === '(' && FUNCS[name]) {
          take('('); var args = [];
          if (!(peek() && peek().t === ')')) { args.push(expr()); while (peek() && peek().t === ',') { take(); args.push(expr()); } }
          take(')'); return { fn: name, args: args };
        }
        if (FUNCS[name]) { return { fn: name, args: [unary()] }; }       // sqrt 16, sin 30
        if (CONSTS.hasOwnProperty(name)) return { konst: name };
        if (/^[a-z]$/.test(name) || name === 'ans') return { v: name };      // a variable (x), or the previous answer
        if (/^[a-z]+$/.test(name) && name.length > 1) {                  // "xy" means x·y, "2ab" means 2·a·b
          var node = { v: name[0] };
          for (var i = 1; i < name.length; i++) node = { op: '*', a: node, b: { v: name[i] }, implicit: true };
          return node;
        }
        throw new Error('Unknown word: ' + k.v);
      }
      throw new Error('Unexpected ' + (k.v || k.t));
    }
    var tree = expr();
    if (p < toks.length) throw new Error('Unexpected ' + (toks[p].v || toks[p].t));
    return tree;
  }
  function evaluate(node, env, opts) {
    env = env || {}; opts = opts || {};
    function ev(n) {
      if (n.num !== undefined) return fromNumber(Number(n.num));
      if (n.konst) return CONSTS[n.konst];
      if (n.v !== undefined) { if (env[n.v] === undefined) throw new Error('What is ' + n.v + '? Give it a value.'); return env[n.v]; }
      if (n.fn) return FUNCS[n.fn](n.args.map(ev), opts.degrees !== false);
      var a = ev(n.a);
      if (n.op === 'neg') return neg(a);
      if (n.op === '!') return fact(a);
      if (n.op === '%') return div(a, R(100n));
      var b = ev(n.b);
      if (n.op === '+') return add(a, b);
      if (n.op === '-') return sub(a, b);
      if (n.op === '*') return mul(a, b);
      if (n.op === '/') return div(a, b);
      if (n.op === '^') return pow(a, b);
      throw new Error('Unknown operation');
    }
    return ev(node);
  }
  function calc(text, env, opts) { return evaluate(parse(text), env, opts); }

  // ---------- showing numbers ----------
  function fmtNumber(x, digits) {
    if (!isFinite(x)) return String(x);
    if (x === 0) return '0';
    var s = Number(x.toPrecision(digits || 10));
    return String(s);
  }
  function fmtBig(n) { var s = String(n); return s.length > 60 ? s.slice(0, 20) + '…' + s.slice(-20) + ' (' + s.replace('-', '').length + ' digits)' : s; }
  function format(v, mode) {                                     // mode: 'exact' (3/4), 'mixed' (1 3/4) or 'decimal'
    if (!isR(v)) return fmtNumber(v);
    if (v.d === 1n) return fmtBig(v.n);
    if (mode === 'decimal') return fmtNumber(toNum(v));
    if (mode === 'mixed') {
      var whole = v.n / v.d, rest = (v.n < 0n ? -v.n : v.n) % v.d;
      if (whole !== 0n) return fmtBig(whole) + ' ' + rest + '/' + v.d;
    }
    return fmtBig(v.n) + '/' + v.d;
  }
  function decimalOf(v) { return isR(v) ? (v.d === 1n ? '' : fmtNumber(toNum(v), 10)) : ''; }

  // ---------- fractions with steps (a/b ± c/d, ×, ÷ and chains of them) ----------
  function fractionSteps(text) {
    var tree = parse(text), steps = [];
    function leaf(n) { if (n.num !== undefined) return fromNumber(Number(n.num)); if (n.op === 'neg' && leaf(n.a) !== null) { var l = leaf(n.a); return l === null ? null : neg(l); } if (n.op === '/' && n.a.num !== undefined && n.b.num !== undefined) return R(BigInt(n.a.num), BigInt(n.b.num)); return null; }
    function run(n) {
      var l = leaf(n);
      if (l !== null) return l;
      if (!n.op || n.op === 'neg' || n.op === '!' || n.op === '%') return evaluate(n);
      var a = run(n.a), b = run(n.b);
      if (!isR(a) || !isR(b)) return evaluate(n);
      var out;
      if (n.op === '+' || n.op === '-') {
        if (a.d === b.d) { out = n.op === '+' ? add(a, b) : sub(a, b); steps.push(format(a) + ' ' + n.op + ' ' + format(b) + ' = ' + (n.op === '+' ? a.n + b.n : a.n - b.n) + '/' + a.d + (format(out) !== (n.op === '+' ? a.n + b.n : a.n - b.n) + '/' + a.d ? ' = ' + format(out) + ' (vereenvoudigd)' : '')); }
        else {
          var lcm = a.d * b.d / bgcd(a.d, b.d), an = a.n * (lcm / a.d), bn = b.n * (lcm / b.d);
          out = n.op === '+' ? add(a, b) : sub(a, b);
          var raw = (n.op === '+' ? an + bn : an - bn) + '/' + lcm;
          steps.push(format(a) + ' ' + n.op + ' ' + format(b) + ' → gelijknamig maken (noemer ' + lcm + '): ' + an + '/' + lcm + ' ' + n.op + ' ' + bn + '/' + lcm + ' = ' + raw + (format(out) !== raw ? ' = ' + format(out) + ' (vereenvoudigd)' : ''));
        }
      } else if (n.op === '*') { out = mul(a, b); var r1 = (a.n * b.n) + '/' + (a.d * b.d); steps.push(format(a) + ' × ' + format(b) + ' = teller × teller / noemer × noemer = ' + r1 + (format(out) !== r1 ? ' = ' + format(out) + ' (vereenvoudigd)' : '')); }
      else if (n.op === '/') { out = div(a, b); var r2 = (a.n * b.d) + '/' + (a.d * b.n); steps.push(format(a) + ' ÷ ' + format(b) + ' = ' + format(a) + ' × ' + format(R(b.d, b.n)) + ' (omkeren en vermenigvuldigen) = ' + r2 + (format(out) !== r2 ? ' = ' + format(out) + ' (vereenvoudigd)' : '')); }
      else if (n.op === '^') { out = pow(a, b); steps.push('(' + format(a) + ')^' + format(b) + ' = ' + format(out)); }
      else out = evaluate(n);
      return out;
    }
    var result = run(tree);
    return { value: result, steps: steps, exact: format(result), mixed: format(result, 'mixed'), decimal: isR(result) ? fmtNumber(toNum(result)) : fmtNumber(result) };
  }

  // ---------- tables ----------
  function times(n, upto) {
    var rows = [];
    for (var i = 1; i <= (upto || 12); i++) rows.push([i, n, i * n]);
    return rows;
  }
  function table(formula, from, step, count, opts) {
    var tree = parse(formula.replace(/^\s*y\s*=\s*/i, '')), rows = [];
    var x = fromNumber(from), st = fromNumber(step);
    for (var i = 0; i < count; i++) {
      var y, err = '';
      try { y = evaluate(tree, { x: x }, opts); } catch (e) { y = null; err = e.message; }
      rows.push({ x: format(x), y: y === null ? '—' : format(y), yd: y === null ? '' : decimalOf(y), err: err });
      x = add(x, st);
    }
    return rows;
  }
  function fn(formula, opts) {                                   // a fast y(x) for drawing
    var tree = parse(formula.replace(/^\s*y\s*=\s*/i, ''));
    return function (x) { try { return toNum(evaluate(tree, { x: x }, opts)); } catch (e) { return NaN; } };
  }

  // ---------- equations: ax + b = c and ax² + bx + c = 0 (abc-formule), with steps ----------
  function solve(text, opts) {
    var sides = String(text).split('=');
    if (sides.length !== 2) throw new Error('Write an equation with one = in it, like 2x + 3 = 11.');
    var L = parse(sides[0]), Rt = parse(sides[1]);
    function g(x) { return sub(evaluate(L, { x: x }, opts), evaluate(Rt, { x: x }, opts)); }
    var g0 = g(R(0n)), g1 = g(R(1n)), g2 = g(R(2n)), g3 = g(R(3n));
    var a = div(sub(add(g2, g0), mul(R(2n), g1)), R(2n)), b = sub(sub(g1, g0), a), c = g0;
    var check = add(add(mul(a, R(9n)), mul(b, R(3n))), c);
    var steps = [], f = function (v) { return format(v); };
    if (Math.abs(toNum(sub(check, g3))) > 1e-9) return numericSolve(g, steps);
    var isZero = function (v) { return Math.abs(toNum(v)) < 1e-12; };
    if (isZero(a)) {
      if (isZero(b)) return { kind: isZero(c) ? 'all' : 'none', steps: [isZero(c) ? 'Links en rechts zijn altijd gelijk: elke x klopt.' : 'Links en rechts zijn nooit gelijk: geen oplossing.'], roots: [] };
      steps.push('Alles naar één kant: ' + f(b) + 'x ' + (toNum(c) < 0 ? '− ' + f(neg(c)) : '+ ' + f(c)) + ' = 0');
      steps.push(f(b) + 'x = ' + f(neg(c)));
      var x1 = div(neg(c), b);
      steps.push('x = ' + f(neg(c)) + ' / ' + f(b) + ' = ' + f(x1) + (decimalOf(x1) ? ' ≈ ' + decimalOf(x1) : ''));
      return { kind: 'linear', steps: steps, roots: [x1] };
    }
    steps.push('Alles naar één kant: ' + f(a) + 'x² ' + (toNum(b) < 0 ? '− ' + f(neg(b)) : '+ ' + f(b)) + 'x ' + (toNum(c) < 0 ? '− ' + f(neg(c)) : '+ ' + f(c)) + ' = 0');
    steps.push('a = ' + f(a) + ', b = ' + f(b) + ', c = ' + f(c));
    var D = sub(mul(b, b), mul(R(4n), mul(a, c)));
    steps.push('D = b² − 4ac = ' + f(mul(b, b)) + ' − ' + f(mul(R(4n), mul(a, c))) + ' = ' + f(D));
    if (toNum(D) < 0) { steps.push('D < 0, dus geen oplossing.'); return { kind: 'none', steps: steps, roots: [] }; }
    var sq = root(D, 2);
    steps.push('√D = ' + f(sq) + (isR(sq) ? '' : ' (geen mooi getal)'));
    var two_a = mul(R(2n), a);
    if (toNum(D) === 0) { var x0 = div(neg(b), two_a); steps.push('D = 0, dus één oplossing: x = −b / 2a = ' + f(neg(b)) + ' / ' + f(two_a) + ' = ' + f(x0)); return { kind: 'quadratic', steps: steps, roots: [x0] }; }
    var xa = div(add(neg(b), sq), two_a), xb = div(sub(neg(b), sq), two_a);
    steps.push('x = (−b ± √D) / 2a = (' + f(neg(b)) + ' ± ' + f(sq) + ') / ' + f(two_a));
    steps.push('x = ' + f(xa) + (decimalOf(xa) ? ' ≈ ' + decimalOf(xa) : '') + '  of  x = ' + f(xb) + (decimalOf(xb) ? ' ≈ ' + decimalOf(xb) : ''));
    return { kind: 'quadratic', steps: steps, roots: [xa, xb] };
  }
  function numericSolve(g, steps) {                              // not a line or a parabola: look for sign changes and close in
    var roots = [], prev = null, px = 0;
    function keep(r) { r = Number(r.toPrecision(8)); if (!roots.some(function (q) { return Math.abs(q - r) < 1e-6; })) roots.push(r); }
    for (var x = -100; x <= 100; x += 0.25) {
      var y; try { y = toNum(g(fromNumber(x))); } catch (e) { y = NaN; }
      if (y === 0) keep(x);
      else if (prev !== null && isFinite(y) && isFinite(prev) && prev !== 0 && prev * y < 0) {
        var lo = px, hi = x, flo = prev;
        for (var i = 0; i < 60; i++) { var mid = (lo + hi) / 2, fm = toNum(g(fromNumber(mid))); if (flo * fm <= 0) hi = mid; else { lo = mid; flo = fm; } }
        keep((lo + hi) / 2);
      }
      prev = y; px = x;
    }
    steps.push('Dit is geen lijn of parabool, dus Toolbelt zoekt de oplossingen tussen −100 en 100 door in te klemmen (bisectie).');
    steps.push(roots.length ? 'Gevonden: ' + roots.map(function (r) { return 'x ≈ ' + r; }).join(', ') : 'Geen oplossing gevonden tussen −100 en 100.');
    return { kind: 'numeric', steps: steps, roots: roots };
  }

  // ---------- the natural display: what was typed, drawn like a textbook (fractions stacked, √ with its bar, powers raised) ----------
  function hesc(s) { return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  var PREC = { '+': 1, '-': 1, '*': 2, '/': 2, 'neg': 3, '^': 4, '!': 5, '%': 5 };
  function html(text) {
    function prec(n) { return n.op === '/' && !n.school ? 4.5 : n.op ? PREC[n.op] : 6; }   // a stacked fraction needs brackets only as a power's base
    function wrap(n, need) { var s = r(n); return prec(n) < need ? '(' + s + ')' : s; }
    function r(n) {
      if (n.num !== undefined) return hesc(n.num);
      if (n.konst) return n.konst === 'e' ? 'e' : 'π';
      if (n.v !== undefined) return n.v === 'ans' ? 'Ans' : hesc(n.v);
      if (n.fn) {
        var a = n.args;
        if (n.fn === 'sqrt') return '<span class="sq">√<span class="rad">' + r(a[0]) + '</span></span>';
        if (n.fn === 'cbrt') return '<span class="sq">∛<span class="rad">' + r(a[0]) + '</span></span>';
        if (n.fn === 'root' && a.length > 1) return '<span class="sq"><sup class="idx">' + r(a[0]) + '</sup>√<span class="rad">' + r(a[1]) + '</span></span>';
        if (n.fn === 'fact') return wrap(a[0], 5) + '!';
        if (n.fn === 'abs') return '|' + r(a[0]) + '|';
        return hesc(n.fn) + '(' + a.map(r).join(', ') + ')';
      }
      if (n.op === 'neg') return '−' + wrap(n.a, 3);
      if (n.op === '!') return wrap(n.a, 5) + '!';
      if (n.op === '%') return wrap(n.a, 5) + '%';
      if (n.op === '/' && n.school) return wrap(n.a, 2) + '÷' + wrap(n.b, 3);
      if (n.op === '/') return '<span class="fr"><span class="nu">' + r(n.a) + '</span><span class="de">' + r(n.b) + '</span></span>';
      if (n.op === '^') return wrap(n.a, 5) + '<sup>' + r(n.b) + '</sup>';
      if (n.op === '*') return wrap(n.a, 2) + (n.implicit ? '' : '×') + wrap(n.b, n.implicit && n.b.op === '/' ? 6 : 3);
      if (n.op === '+') return r(n.a) + ' + ' + wrap(n.b, 2);
      if (n.op === '-') return r(n.a) + ' − ' + wrap(n.b, 2);
      return '?';
    }
    if (!String(text).trim()) return '';
    try { return r(parse(text)); } catch (e) {                   // half-typed: show the text as it is, a little prettier
      return hesc(String(text)).replace(/\*/g, '×').replace(/sqrt\(?/g, '√(').replace(/cbrt\(?/g, '∛(').replace(/pi/g, 'π').replace(/-/g, '−');
    }
  }
  function htmlValue(v, mode) {                                  // a result drawn the same way: 7/4, 1 3/4 or 1.75
    if (!isR(v) || v.d === 1n || mode === 'decimal') return hesc(format(v, mode));
    var sign = v.n < 0n ? '−' : '', n = v.n < 0n ? -v.n : v.n;
    if (mode === 'mixed' && n > v.d) return sign + fmtBig(n / v.d) + '<span class="fr"><span class="nu">' + (n % v.d) + '</span><span class="de">' + v.d + '</span></span>';
    return sign + '<span class="fr"><span class="nu">' + fmtBig(n) + '</span><span class="de">' + fmtBig(v.d) + '</span></span>';
  }

  // ---------- programmer mode: whole numbers in hex / dec / oct / bin, bit operations, a word size ----------
  function prog(text, base, bits) {                              // base: 16 / 10 / 8 / 2 for plain numbers; bits: 8 / 16 / 32 / 64
    base = base || 10; bits = bits || 64;
    var s = String(text).replace(/\s+/g, ' ').trim();
    if (!s) throw new Error('Type a number or a sum first.');
    var toks = [], i = 0;
    var WORDS = { and: '&', or: '|', xor: '^', not: '~', mod: '%', shl: '<<', shr: '>>' };
    while (i < s.length) {
      var c = s[i];
      if (c === ' ') { i++; continue; }
      var m;
      if ((m = s.slice(i).match(/^0x[0-9a-f]+/i))) { toks.push({ n: BigInt(m[0]) }); i += m[0].length; continue; }
      if ((m = s.slice(i).match(/^0b[01]+/i))) { toks.push({ n: BigInt(m[0]) }); i += m[0].length; continue; }
      if ((m = s.slice(i).match(/^0o[0-7]+/i))) { toks.push({ n: BigInt(m[0]) }); i += m[0].length; continue; }
      if ((m = s.slice(i).match(/^[a-z]+/i)) && WORDS[m[0].toLowerCase()]) { toks.push({ t: WORDS[m[0].toLowerCase()] }); i += m[0].length; continue; }   // AND before A-F hex digits
      if ((m = s.slice(i).match(/^[0-9a-f]+/i)) && (base === 16 || /^[0-9]+$/.test(m[0]))) {
        var digits = m[0], ok = { 16: /^[0-9a-f]+$/i, 10: /^[0-9]+$/, 8: /^[0-7]+$/, 2: /^[01]+$/ }[base];
        if (!ok.test(digits)) throw new Error('"' + digits + '" is not a number in base ' + base + '.');
        toks.push({ n: BigInt({ 16: '0x', 10: '', 8: '0o', 2: '0b' }[base] + digits) }); i += digits.length; continue;
      }
      if ((m = s.slice(i).match(/^[a-z]+/i)) && WORDS[m[0].toLowerCase()]) { toks.push({ t: WORDS[m[0].toLowerCase()] }); i += m[0].length; continue; }
      if (s.startsWith('<<', i) || s.startsWith('>>', i)) { toks.push({ t: s.substr(i, 2) }); i += 2; continue; }
      if ('+-*/%&|^~()'.indexOf(c) !== -1) { toks.push({ t: c }); i++; continue; }
      if (c === '×') { toks.push({ t: '*' }); i++; continue; }
      if (c === '÷') { toks.push({ t: '/' }); i++; continue; }
      throw new Error('Unknown symbol: ' + c);
    }
    var p = 0;
    function peek() { return toks[p]; }
    function take() { return toks[p++]; }
    var LEVELS = [['|'], ['^'], ['&'], ['<<', '>>'], ['+', '-'], ['*', '/', '%']];
    function level(k) {
      if (k === LEVELS.length) return unary();
      var a = level(k + 1);
      while (peek() && LEVELS[k].indexOf(peek().t) !== -1) { var op = take().t, b = level(k + 1); a = apply(op, a, b); }
      return a;
    }
    function unary() {
      if (peek() && peek().t === '-') { take(); return -unary(); }
      if (peek() && peek().t === '~') { take(); return ~unary(); }
      var k = take();
      if (!k) throw new Error('The sum ends too soon.');
      if (k.n !== undefined) return k.n;
      if (k.t === '(') { var v = level(0); if (!peek() || take().t !== ')') throw new Error('A ) is missing.'); return v; }
      throw new Error('Unexpected ' + k.t);
    }
    function apply(op, a, b) {
      if (op === '+') return a + b; if (op === '-') return a - b; if (op === '*') return a * b;
      if (op === '/') { if (b === 0n) throw new Error('Delen door nul kan niet (division by zero).'); return a / b; }
      if (op === '%') { if (b === 0n) throw new Error('Delen door nul kan niet (division by zero).'); return a % b; }
      if (op === '&') return a & b; if (op === '|') return a | b; if (op === '^') return a ^ b;
      if (op === '<<') return a << b; if (op === '>>') return a >> b;
      throw new Error('Unknown operation ' + op);
    }
    var value = level(0);
    if (p < toks.length) throw new Error('Unexpected ' + (toks[p].t || toks[p].n));
    return progShow(value, bits);
  }
  function progShow(value, bits) {
    bits = bits || 64;
    var mask = (1n << BigInt(bits)) - 1n, raw = value & mask, overflow = value > mask || value < -(1n << BigInt(bits - 1));
    var signed = raw >= (1n << BigInt(bits - 1)) ? raw - (1n << BigInt(bits)) : raw;   // two's complement reading of the same bits
    var bin = raw.toString(2).padStart(bits, '0');
    return { value: value.toString(), signed: signed.toString(), unsigned: raw.toString(), hex: raw.toString(16).toUpperCase().padStart(bits / 4, '0'), oct: raw.toString(8), bin: bin,
      binGrouped: bin.replace(/(.{4})(?=.)/g, '$1 '), hexGrouped: raw.toString(16).toUpperCase().padStart(bits / 4, '0').replace(/(.{4})(?=.)/g, '$1 '), bits: bits, overflow: overflow,
      bitArray: bin.split('').map(function (b) { return b === '1'; }) };
  }
  function progFromBits(bitArray, bits) {
    var raw = BigInt('0b' + (bitArray.map(function (b) { return b ? '1' : '0'; }).join('') || '0'));
    return progShow(raw, bits);
  }

  // ---------- units: everything of one kind at once (Windows shows one; this shows the whole list) ----------
  var UNITS = {
    length: { name: 'Lengte', base: 'm', units: { mm: 0.001, cm: 0.01, m: 1, km: 1000, inch: 0.0254, foot: 0.3048, yard: 0.9144, mile: 1609.344 } },
    weight: { name: 'Gewicht', base: 'kg', units: { mg: 1e-6, g: 0.001, kg: 1, ton: 1000, ounce: 0.028349523125, pound: 0.45359237 } },
    temperature: { name: 'Temperatuur', base: '°C', units: { '°C': 1, '°F': 1, K: 1 } },
    speed: { name: 'Snelheid', base: 'm/s', units: { 'm/s': 1, 'km/h': 1 / 3.6, mph: 0.44704, knot: 0.514444 } },
    data: { name: 'Data', base: 'byte', units: { bit: 0.125, byte: 1, KB: 1000, MB: 1e6, GB: 1e9, TB: 1e12, KiB: 1024, MiB: 1048576, GiB: 1073741824, TiB: 1099511627776 } },
    time: { name: 'Tijd', base: 's', units: { ms: 0.001, s: 1, min: 60, hour: 3600, day: 86400, week: 604800, year: 31557600 } },
    area: { name: 'Oppervlakte', base: 'm²', units: { 'cm²': 0.0001, 'm²': 1, hectare: 10000, 'km²': 1e6, 'ft²': 0.09290304, acre: 4046.8564224 } },
    volume: { name: 'Volume', base: 'L', units: { ml: 0.001, L: 1, 'm³': 1000, 'US gallon': 3.785411784, 'US cup': 0.2365882365, 'fl oz': 0.0295735295625 } },
    angle: { name: 'Hoek', base: '°', units: { '°': 1, rad: 180 / Math.PI, grad: 0.9, turn: 360 } },
    energy: { name: 'Energie', base: 'J', units: { J: 1, kJ: 1000, cal: 4.184, kcal: 4184, Wh: 3600, kWh: 3600000 } },
    pressure: { name: 'Druk', base: 'Pa', units: { Pa: 1, kPa: 1000, bar: 100000, atm: 101325, psi: 6894.757293168, mmHg: 133.322387415 } }
  };
  function convert(kind, value, from) {
    var k = UNITS[kind]; if (!k) throw new Error('Unknown kind.');
    var x = Number(String(value).replace(',', '.'));
    if (!isFinite(x)) throw new Error('Give a number.');
    var out = {};
    if (kind === 'temperature') {
      var c = from === '°C' ? x : from === '°F' ? (x - 32) * 5 / 9 : x - 273.15;
      out['°C'] = c; out['°F'] = c * 9 / 5 + 32; out.K = c + 273.15;
    } else {
      if (!k.units[from]) throw new Error('Unknown unit.');
      var baseValue = x * k.units[from];
      Object.keys(k.units).forEach(function (u) { out[u] = baseValue / k.units[u]; });
    }
    return Object.keys(out).map(function (u) { return { unit: u, value: out[u], text: fmtNumber(out[u], 10) }; });
  }

  // ---------- dates ----------
  function parseDate(s) {
    s = String(s).trim();
    var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/) || s.match(/^(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})$/);
    if (!m) throw new Error('Write a date as 2026-10-14 or 14-10-2026.');
    var y = m[1].length === 4 ? +m[1] : +m[3], mo = +m[2], d = m[1].length === 4 ? +m[3] : +m[1];
    var dt = new Date(Date.UTC(y, mo - 1, d));
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) throw new Error('That date does not exist.');
    return dt;
  }
  function dateText(dt) { return dt.getUTCFullYear() + '-' + String(dt.getUTCMonth() + 1).padStart(2, '0') + '-' + String(dt.getUTCDate()).padStart(2, '0'); }
  var DAYS = ['zondag', 'maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag'];
  function dateDiff(a, b) {
    var A = parseDate(a), B = parseDate(b), sign = B < A ? -1 : 1;
    if (sign < 0) { var t = A; A = B; B = t; }
    var days = Math.round((B - A) / 86400000);
    var y = B.getUTCFullYear() - A.getUTCFullYear(), mo = B.getUTCMonth() - A.getUTCMonth(), d = B.getUTCDate() - A.getUTCDate();
    if (d < 0) { mo--; d += new Date(Date.UTC(B.getUTCFullYear(), B.getUTCMonth(), 0)).getUTCDate(); }
    if (mo < 0) { y--; mo += 12; }
    return { days: days * sign, weeks: Math.floor(days / 7) * sign, restDays: days % 7, years: y, months: mo, daysLeft: d, from: dateText(A), to: dateText(B), weekdayFrom: DAYS[A.getUTCDay()], weekdayTo: DAYS[B.getUTCDay()] };
  }
  function dateAdd(a, amount, unit) {
    var A = parseDate(a), n = parseInt(amount, 10) || 0, out = new Date(A.getTime());
    if (unit === 'days') out.setUTCDate(out.getUTCDate() + n);
    else if (unit === 'weeks') out.setUTCDate(out.getUTCDate() + 7 * n);
    else if (unit === 'months') out.setUTCMonth(out.getUTCMonth() + n);
    else out.setUTCFullYear(out.getUTCFullYear() + n);
    return { date: dateText(out), weekday: DAYS[out.getUTCDay()] };
  }

  window.calc = { parse: parse, evaluate: evaluate, calc: calc, format: format, decimalOf: decimalOf, R: R, isR: isR, toNum: toNum, fromNumber: fromNumber,
    fractionSteps: fractionSteps, times: times, table: table, fn: fn, solve: solve, root: root, pow: pow, html: html, htmlValue: htmlValue,
    prog: prog, progShow: progShow, progFromBits: progFromBits, UNITS: UNITS, convert: convert, parseDate: parseDate, dateText: dateText, dateDiff: dateDiff, dateAdd: dateAdd, DAYS: DAYS };
})();
