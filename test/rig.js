/* rig.js -- run the BUILT artifact under Node with a stubbed DOM.
 *
 * Manual phase 14: "Load THE BUILT ARTIFACT, not your source modules, so the
 * build step is under test."  And: "A CANVAS STUB THAT RECORDS DRAW CALLS WHEN
 * ARMED ... for anything conditional, RENDER TWICE with only the flag changed
 * and DIFF THE TWO DRAW LISTS."
 *
 *   const rig = require('./rig');
 *   const { S, P, sandbox } = rig.loadBuilt();     // S = __SPEC__, P = __PORT__
 *   rig.check(name, got, want); rig.checkTrue(name, cond, detail);
 *   rig.done();                                      // prints N/N, sets exit code
 *
 * What the stub deliberately does NOT provide: a real AudioContext (tests
 * install their own mocks on `sandbox` and remove them), Blob/URL/btoa (so the
 * worklet gate's absence path is what runs by default), a timer that fires
 * rAF (it is CAPTURED -- tests drive the loop by calling rig.raf()).
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);

let checks = 0, failures = 0;
function check(name, got, want) {
  checks++;
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { failures++; console.log(`  FAIL  ${name}\n        got  ${JSON.stringify(got)}\n        want ${JSON.stringify(want)}`); }
  else console.log(`  ok    ${name}`);
}
function checkTrue(name, cond, detail) {
  checks++;
  if (cond) console.log(`  ok    ${name}`);
  else { failures++; console.log(`  FAIL  ${name}${detail ? '  ' + detail : ''}`); }
}
function done() {
  console.log(`\n${checks - failures}/${checks} checks passed`);
  process.exit(failures ? 1 : 0);
}

/* ---------- the DOM stub ---------------------------------------------- */
const drawCalls = [];
let recording = false;
const ctxStub = {
  set fillStyle(v) { this._fill = v; },
  get fillStyle() { return this._fill; },
  fillRect(x, y, w, h) { if (recording) drawCalls.push(['fillRect', x, y, w, h, this._fill]); },
};
function makeEl(id) {
  const set = new Set();
  return {
    id, _text: '', innerHTML: '',
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    getContext() { return ctxStub; },
    style: {},
    classList: { add: c => set.add(c), remove: c => set.delete(c), contains: c => set.has(c) },
    blur() {}, focus() {},
    width: 256, height: 192,
  };
}
const els = new Map();
let rafCallback = null;
/* A real, if minimal, localStorage: settings code guards every call in
   try/catch, so WITHOUT this the round trip fails silently and every
   persistence check passes because there is nothing to fail on. */
const localStorageStore = new Map();
const localStorage = {
  getItem(k) { return localStorageStore.has(k) ? localStorageStore.get(k) : null; },
  setItem(k, v) { localStorageStore.set(k, String(v)); },
  removeItem(k) { localStorageStore.delete(k); },
  clear() { localStorageStore.clear(); },
};
const listeners = {};
const sandbox = {
  console,
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  document: {
    getElementById(id) {
      if (!els.has(id)) els.set(id, makeEl(id));
      return els.get(id);
    },
  },
  addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
  requestAnimationFrame(cb) { rafCallback = cb; return 1; },   // CAPTURE, don't fire
  localStorage,
  Math, JSON, Uint8Array, Float32Array, Buffer, String, Number, Array, Object, Error, Set, Map,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

/* ---------- load the built artifact ----------------------------------- */
function builtPath() {
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'port.json'), 'utf8'));
  return path.join(ROOT, cfg.out || ('web/' + (cfg.name || 'game') + '.html'));
}
function loadBuilt(file) {
  const BUILT = file || builtPath();
  const html = fs.readFileSync(BUILT, 'utf8');
  checkTrue('built file says it is generated', html.startsWith('<!-- GENERATED'));
  const jsonMatch = html.match(/<script type="application\/json" id="assets">([\s\S]*?)<\/script>/);
  checkTrue('asset payload present in the built file', !!jsonMatch);
  checkTrue('asset payload contains no unescaped "</"', !!jsonMatch && !jsonMatch[1].includes('</'));
  els.set('assets', Object.assign(makeEl('assets'), { _text: jsonMatch[1].replace(/<\\\//g, '</') }));
  const codeMatch = html.match(/<script>([\s\S]*?)<\/script>\s*$/);
  checkTrue('engine script present', !!codeMatch);
  vm.runInContext(codeMatch[1], sandbox, { filename: path.basename(BUILT) });
  const S = sandbox.globalThis.__SPEC__, P = sandbox.globalThis.__PORT__;
  checkTrue('platform hook exported (__SPEC__)', !!S);
  checkTrue('port hook exported (__PORT__)', !!P);
  /* ASSETS MARKED `ship: false` ARE NOT IN THE PAGE, so the rig loads them from
     disk and hands them to the suite.  Without this a held-back fixture would
     read as `undefined` and every gate block guarded by `if (A.thing)` would
     SILENTLY SKIP -- the page would shrink and the suite would go quiet, which
     is the worst possible trade.  Counted and reported, never silent. */
  if (P && P.assets) {
    const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'port.json'), 'utf8'));
    let merged = 0;
    for (const a of (cfg.assets || [])) {
      if (a.ship === false && !(a.key in P.assets)) {
        const f = path.join(ROOT, a.file);
        if (fs.existsSync(f)) { P.assets[a.key] = JSON.parse(fs.readFileSync(f, 'utf8')); merged++; }
      }
    }
    const want = (cfg.assets || []).filter(a => a.ship === false && fs.existsSync(path.join(ROOT, a.file))).length;
    checkTrue('test-only assets loaded from disk (' + merged + ' of ' + want + ')',
              merged === want);
  }
  checkTrue('rAF captured, not fired', rafCallback !== null);
  return { S, P, sandbox, html };
}

module.exports = {
  ROOT, sandbox, els, drawCalls, listeners, localStorageStore,
  check, checkTrue, done, loadBuilt, builtPath,
  record(on) { recording = on; if (on) drawCalls.length = 0; },
  raf() { return rafCallback; },
  /* an event's listeners in registration order, as a browser runs them on one target -- and, as a browser does,
     none after one that calls stopImmediatePropagation().  Without the stop every listener ran, so a page that
     must keep a key from a later listener (Alt+Enter from attachKeyboard's ENTER) passed with the stop missing. */
  fire(type, ev) {
    let stopped = false;
    if (ev && typeof ev === 'object') {
      const own = ev.stopImmediatePropagation;
      ev.stopImmediatePropagation = function () { stopped = true; if (typeof own === 'function') own.call(this); };
    }
    for (const fn of (listeners[type] || []).slice()) { fn(ev); if (stopped) break; }
  },
};
