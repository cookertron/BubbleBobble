/* kit.test.js -- the platform runtime's own suite, run against the BUILT
 * starter page through the rig (manual phase 14).  A port keeps this file
 * and appends its game's checks after it; nothing here knows about any game.
 *
 *   node test/kit.test.js
 */
'use strict';
const { execFileSync } = require('child_process');
const path = require('path');
const rig = require('./rig');
const { check, checkTrue } = rig;

/* ---- the build is under test ------------------------------------------ */
let built = true;
try { execFileSync('python', [path.join(rig.ROOT, 'tools', 'build.py')],
                   { cwd: rig.ROOT, stdio: 'pipe' }); }
catch (e) { built = false; console.log(String(e.stdout || '') + String(e.stderr || '')); }
checkTrue('tools/build.py builds the page from port.json', built);

const { S, P, sandbox, html } = rig.loadBuilt();
const FRAME_HZ = S.FRAME_HZ;
check('the frame clock defaults to the 48K ULA', FRAME_HZ, 50.08);

/* =======================================================================
   THE DISPLAY FILE
   ======================================================================= */
{
  const SS = S.SpecScreen;
  check('pixelAddr: the ULA bit layout 010TTLLLRRRCCCCC',
        [SS.pixelAddr(0, 0), SS.pixelAddr(8, 0), SS.pixelAddr(0, 1),
         SS.pixelAddr(0, 8), SS.pixelAddr(0, 64), SS.pixelAddr(255, 191)],
        [0x4000, 0x4001, 0x4100, 0x4020, 0x4800, 0x57FF]);
  check('attrAddr: the third from bits 12:11, L carried through',
        [SS.attrAddr(0x4000), SS.attrAddr(0x4800), SS.attrAddr(0x50E5)],
        [0x5800, 0x5900, 0x5AE5]);
  check('attrAt: 32 a row', SS.attrAt(31, 23), 0x5AFF);
  check('nextRow: INC H within a character row, then L += $20 / H -= 8',
        [SS.nextRow(0x4000), SS.nextRow(0x4700), SS.nextRow(0x47E0)],
        [0x4100, 0x4020, 0x4800]);
  check('nextCol: INC L, and H += 8 when L wraps into the next third',
        [SS.nextCol(0x4000), SS.nextCol(0x40FF)], [0x4001, 0x4800]);
  const scr = new SS();
  scr.plot(3, 5, true);
  check('plot sets the right bit of the right byte', scr.get(SS.pixelAddr(3, 5)), 0x10);
  scr.plot(3, 5, false);
  check('...and clears it', scr.get(SS.pixelAddr(3, 5)), 0);
  const font = new Uint8Array([1,2,3,4,5,6,7,8, 9,10,11,12,13,14,15,16]);
  const p = scr.putGlyph(0x4000, font, 0);
  check('putGlyph writes eight rows down the pixel-row chain and steps right',
        [scr.get(0x4000), scr.get(0x4100), scr.get(0x4700), p], [1, 2, 8, 0x4001]);
  scr.clear();
  scr.print(0x4020, 'AB', font, 65);
  check('print indexes the font from its first code',
        [scr.get(0x4020), scr.get(0x4021), scr.get(0x4721)], [1, 9, 16]);
  scr.fillAttr(0x38);
  check('fillAttr touches attributes only',
        [scr.get(0x5800), scr.get(0x5AFF), scr.get(0x4020)], [0x38, 0x38, 1]);
}

/* ---- the renderer, at the draw-list level -------------------------- */
{
  const ctx = sandbox.document.getElementById('scr').getContext('2d');
  const scr = new S.SpecScreen();
  scr.put(0x4000, 0x80); scr.put(0x5800, 0x07);      // one ink pixel, white on black
  rig.record(true); S.renderScreen(ctx, scr, 0); rig.record(false);
  const has = (x, y, w, c) => rig.drawCalls.some(d => d[1] === x && d[2] === y && d[3] === w && d[5] === c);
  checkTrue('an ink pixel is one dim-white run of 1', has(0, 0, 1, '#d7d7d7'));
  checkTrue('...followed by a paper run of 7', has(1, 0, 7, '#000000'));
  checkTrue('an all-paper row is ONE call, not eight', has(8, 0, 8, '#000000'));
  scr.put(0x5800, 0x47);
  rig.record(true); S.renderScreen(ctx, scr, 0); rig.record(false);
  checkTrue('BRIGHT selects the second palette', has(0, 0, 1, '#ffffff'));
  scr.put(0x5800, 0x87);                              // FLASH
  rig.record(true); S.renderScreen(ctx, scr, 16); rig.record(false);
  checkTrue('FLASH swaps ink and paper when bit 4 of the frame counter is set',
            has(0, 0, 1, '#000000') && has(1, 0, 7, '#d7d7d7'));
  rig.record(true); S.renderScreen(ctx, scr, 15); rig.record(false);
  checkTrue('...and not otherwise', has(0, 0, 1, '#d7d7d7'));
  rig.record(true); S.renderScreen(ctx, scr, 0, 1); rig.record(false);
  checkTrue('`rows` clips the render', rig.drawCalls.every(d => d[2] < 8));
  S.paintBorder(2);
  check('the border paints the overscan element from the dim palette',
        sandbox.document.getElementById('overscan').style.background, '#d70000');
}

/* =======================================================================
   THE KEYBOARD MATRIX AND THE KEMPSTON PORT
   ======================================================================= */
{
  const kb = new S.Keyboard();
  kb.press('A');
  check('a key down is a ZERO bit in its half-row', [kb.halfrow(1), kb.bit(1, 0), kb.bit(1, 1)], [0xFE, 0, 1]);
  check('IN A,(C): a LOW select bit reads that half-row', kb.port(0xFD), 0xFE);
  check('...a HIGH one does not', kb.port(0xFE), 0xFF);
  kb.press('SPACE');
  check('...and several low bits AND their rows together, as the ULA does',
        [kb.port(0x7F), kb.port(0x00)], [0xFE, 0xFE]);
  kb.releaseAll();
  check('releaseAll clears keys and both Kempston bytes',
        [kb.port(0x00), kb.kempston, kb.kempston2], [0xFF, 0, 0]);
  const km = S.buildKeymap({ KeyZ: 'SYM' });
  check('the arrows ARE 5/6/7/8, the cursor keys', [km.ArrowLeft, km.ArrowDown, km.ArrowUp, km.ArrowRight], ['5', '6', '7', '8']);
  check('letters, digits, the shifts and the overrides', [km.KeyQ, km.Digit3, km.ShiftLeft, km.KeyZ], ['Q', '3', 'CAPS', 'SYM']);
  /* the page's own listeners, through the rig's event bus */
  const noop = { preventDefault(){} };
  rig.fire('keydown', Object.assign({ code: 'KeyQ', target: null }, noop));
  checkTrue('a keydown on the page presses the mapped key', P.keyboard.down('Q'));
  rig.fire('keyup', Object.assign({ code: 'KeyQ', target: null }, noop));
  checkTrue('...and keyup releases it', !P.keyboard.down('Q'));
  rig.fire('keydown', Object.assign({ code: 'KeyW', target: { tagName: 'INPUT' } }, noop));
  checkTrue('a keystroke aimed at a form field is NOT a game key', !P.keyboard.down('W'));
  rig.fire('keydown', Object.assign({ code: 'KeyE', target: null }, noop));
  rig.fire('blur', {});
  checkTrue('losing focus releases everything', !P.keyboard.down('E'));

  sandbox.navigator = { getGamepads(){ return [null, { connected: true, id: 'Test Pad One',
    axes: [0.9, -0.9], buttons: [{ pressed: true }] }]; } };
  const st = S.pollGamepads(kb);
  check('a gamepad feeds the Kempston byte: right, up, fire',
        [st.count, kb.kempston, st.names[0]], [1, S.KEMPSTON_RIGHT | S.KEMPSTON_UP | S.KEMPSTON_FIRE, 'TEST PAD ON']);
  check('padBits: B / the shoulders carry the ADDED $20 bit',
        S.padBits({ axes: [0, 0], buttons: [{ pressed: false }, { pressed: true }] }), S.KEMPSTON_POTION);
  check('padBits: the d-pad', S.padBits({ axes: [0, 0], buttons: Array.from({ length: 16 }, (_, i) => ({ pressed: i === 14 })) }), S.KEMPSTON_LEFT);
  delete sandbox.navigator;
  S.pollGamepads(kb);
  check('no navigator: the port byte is clear', kb.kempston, 0);
}

/* =======================================================================
   THE AY CHIP against the datasheet formula, measured out of its own
   samples by counting zero crossings -- an independent re-derivation of
   f = clock / (16 * TP), not a read-back of the constant.
   ======================================================================= */
{
  const sr = 44100;
  const measure = (tp) => {
    const c = new S.AyChip(sr, S.AY_CLOCK);
    c.write(0, tp & 0xFF); c.write(1, tp >> 8);
    c.write(7, 0x38); c.write(8, 15); c.write(9, 0); c.write(10, 0);
    const n = sr * 0.4, buf = new Float32Array(n);
    c.render(buf, 0, n);
    let mean = 0; for (let i = 0; i < n; i++) mean += buf[i];
    mean /= n;
    let cross = 0;
    for (let i = 1; i < n; i++) if ((buf[i - 1] - mean) <= 0 && (buf[i] - mean) > 0) cross++;
    return cross / 0.4;
  };
  for (const tp of [1625, 812, 404, 121]) {
    const want = S.AY_CLOCK / (16 * tp), got = measure(tp);
    checkTrue(`AyChip tone period ${tp} -> ${want.toFixed(1)} Hz`,
              Math.abs(got - want) / want < 0.02, `measured ${got.toFixed(1)} Hz`);
  }
  const wiggle = (r7) => {
    const c = new S.AyChip(sr, S.AY_CLOCK);
    c.write(0, 100); c.write(1, 0); c.write(7, r7); c.write(8, 15);
    const n = 4000, buf = new Float32Array(n);
    c.render(buf, 0, n);
    let lo = 1e9, hi = -1e9;
    for (let i = 200; i < n; i++) { lo = Math.min(lo, buf[i]); hi = Math.max(hi, buf[i]); }
    return hi - lo;
  };
  checkTrue('R7 bit 0 CLEAR = tone A ENABLED: the output swings', wiggle(0x38) > 0.1);
  checkTrue('R7 bit 0 SET = tone A disabled: a constant, not silence (the chip\'s AND gate)', wiggle(0x39) < 1e-6);
}

/* =======================================================================
   THE BEEPER CHIP: the box integral, the DC blocker, the speaker model
   ======================================================================= */
{
  const sr = 44100;
  const square = (hz, secs) => { const ed = []; let lv = 1;
    for (let t = 0; t < secs; t += 1 / (2 * hz)) { ed.push([t, lv]); lv ^= 1; } return ed; };
  /* measurement of the integral and the blocker runs with the ADDED
     speaker model OFF -- the at-unity bound is the blocker's passband */
  S.speakerFilter.set(false);
  for (const hz of [1000, 2500, 4000]) {
    const c = new S.BeeperChip(sr), n = Math.round(sr * 0.3), buf = new Float32Array(n);
    c.render(buf, 0, n, 0, square(hz, 0.3), 0);
    let cross = 0;
    for (let i = 1; i < n; i++) if (buf[i - 1] <= 0 && buf[i] > 0) cross++;
    checkTrue(`BeeperChip renders a ${hz} Hz square at ${hz} Hz`, Math.abs(cross / 0.3 - hz) / hz < 0.03, `measured ${(cross / 0.3).toFixed(1)}`);
  }
  {
    const c = new S.BeeperChip(sr, false), buf = new Float32Array(4);
    c.render(buf, 0, 4, 0, [[0.25 / sr, 1]], 0);
    checkTrue('the box integral is EXACT: an edge a quarter into a sample gives 0.75 high',
              Math.abs(buf[0] - 0.25) < 1e-6 && Math.abs(buf[1] - 0.5) < 1e-6, JSON.stringify([...buf]));
    const d = new S.BeeperChip(sr), b2 = new Float32Array(sr);
    d.render(b2, 0, sr, 0, [[0, 0]], 0);
    checkTrue('a constant level renders as SILENCE, not as a DC step', Math.abs(b2[sr - 1]) < 1e-6);
    const e2 = new S.BeeperChip(sr), b3 = new Float32Array(sr);
    e2.render(b3, 0, sr, 0, square(1588, 1), 0);
    let pk = 0; for (let i = sr / 2; i < sr; i++) pk = Math.max(pk, Math.abs(b3[i]));
    checkTrue('and a 1,588 Hz square passes the blocker at ~unity', pk > 0.48 && pk < 0.52, String(pk));
  }
  {
    const edges = square(100000, 0.05), n = Math.round(sr * 0.05);
    const raw = new S.BeeperChip(sr, false), b1 = new Float32Array(n);
    raw.render(b1, 0, n, 0, edges, 0);
    let pkRaw = 0; for (let i = 0; i < n; i++) pkRaw = Math.max(pkRaw, Math.abs(b1[i]));
    checkTrue('a 100 kHz square averages down instead of aliasing (bound 0.11, derived)', pkRaw < 0.12, String(pkRaw));
    const c = new S.BeeperChip(sr), b2 = new Float32Array(n);
    c.render(b2, 0, n, 0, edges, 0);
    const tau = sr / (2 * Math.PI * 20), settle = Math.ceil(5 * tau);
    let pk = 0; for (let i = settle; i < n; i++) pk = Math.max(pk, Math.abs(b2[i]));
    checkTrue('...and the DC-blocked path rejects it too, once settled (5 tau)', pk < 0.12, String(pk));
    const R = 1 - 2 * Math.PI * 20 / sr, h = b2[0];
    let worst = -Infinity;
    for (let i = 1; i < settle; i++) worst = Math.max(worst, Math.abs(b2[i]) - (Math.abs(h) * Math.pow(R, i) + 0.12));
    checkTrue('the startup transient decays as h*R^i, not as a whine', worst < 0, String(worst));
  }
  S.speakerFilter.set(true);
  /* the speaker model: shades the top octaves, passes the band, and its
     state carries across render() calls -- the anti-click property */
  const rms = (b, from) => { let s = 0; for (let i = from; i < b.length; i++) s += b[i] * b[i]; return Math.sqrt(s / (b.length - from)); };
  const render = (hz) => { const n = Math.round(sr * 0.2), b = new Float32Array(n);
    new S.BeeperChip(sr).render(b, 0, n, 0, square(hz, 0.2), 0); return rms(b, Math.round(sr * 0.1)); };
  S.speakerFilter.set(false); const hiRaw = render(8000), loRaw = render(500);
  S.speakerFilter.set(true);  const hiMod = render(8000), loMod = render(500);
  checkTrue('the speaker model shades an 8 kHz square well below the raw render', hiMod < hiRaw * 0.5, (hiMod / hiRaw).toFixed(3));
  checkTrue('...and passes a 500 Hz square nearly whole', loMod > loRaw * 0.85, (loMod / loRaw).toFixed(3));
  const n = Math.round(sr * 0.1), ed = square(2000, 0.1);
  const whole = new Float32Array(n), split = new Float32Array(n);
  new S.BeeperChip(sr).render(whole, 0, n, 0, ed, 0);
  const c2 = new S.BeeperChip(sr), h = n >> 1;
  const ei = c2.render(split, 0, h, 0, ed, 0);
  c2.render(split, h, n - h, h / sr, ed, ei);
  let same = true; for (let i = 0; i < n; i++) if (whole[i] !== split[i]) { same = false; break; }
  checkTrue('the model state carries across render calls: split === whole', same);
  check('speakerFilter is live-toggleable and reports its state', [S.speakerFilter.set(false), S.speakerFilter.set(true)], [false, true]);
}

/* =======================================================================
   THE BRIDGE, scheduled path: the voice cap, the whole-sample tiling, the
   adaptive lead, the latency class, the worklet init chain
   ======================================================================= */
const mockCtx = (state) => ({
  sampleRate: 44100, get currentTime() { return state.now; }, destination: {},
  createBuffer: (c, n) => { const d = new Float32Array(n); return { length: n, getChannelData: () => d }; },
  createBufferSource() { return { buffer: null, connect() {}, start(when) { state.started++;
    if (state.bufs) state.bufs.push({ when, data: this.buffer.getChannelData() }); } }; },
});
{
  const st = { now: 10, started: 0 };
  const bo = new S.SoundOut();
  bo.ctx = mockCtx(st); bo.gain = { connect() {} }; bo.chip = new S.BeeperChip(44100);
  bo.next = 0; bo.base = 0; bo.t0 = st.now + 0.05; bo.live = [];
  for (let i = 0; i < 60; i++) bo.live.push(st.now + 5);
  bo.flushBeeper([[0.2, 1], [0.4, 0], [0.6, 1]], 4);
  check('a full voice list drops instead of scheduling', st.started, 0);
  check('...and the dropped edges still leave the speaker at the right level', bo.chip.lvl, 1);
  check('...and the drop is counted', bo.dropped, 1);
  st.now = 20;
  bo.flushBeeper([[4.5, 0]], 8);
  check('voices expire by their scheduled END TIME, not by a callback', st.started, 1);
}
{
  /* THE TILING: buffers abut on the sample grid, and the whole schedule
     reconstructs ONE continuous render of the same edges.  The frame counts
     mix 1 (a per-frame front end) with 4..7 (a variable pass clock). */
  const SR = 44100, st = { now: 10, started: 0, bufs: [] };
  const out = new S.SoundOut();
  out.ctx = mockCtx(st); out.gain = { connect() {} }; out.chip = new S.BeeperChip(SR);
  const NF = [1, 4, 5, 4, 7, 1, 1, 6, 4, 5, 5, 4, 6, 1, 4, 5, 7, 4, 4, 5];
  const log = [], all = []; let f = 0, lv = 0;
  out.flushBeeper(log, 0);                          // originate the map
  for (const nf of NF) {
    for (let t = f + 0.0125; t < f + nf; t += 0.025) { lv ^= 1; log.push([t, lv]); all.push([t, lv]); }
    f += nf; out.flushBeeper(log, f);
  }
  check('every closed frame was scheduled', [out.resyncs, out.dropped, st.bufs.length], [0, 0, NF.length]);
  const s00 = Math.floor(st.bufs[0].when * SR);
  const total = Math.floor((out.t0 + f / FRAME_HZ) * SR) - s00;
  let abut = true, offset = 0;
  for (const b of st.bufs) { if (Math.round(b.when * SR) - s00 !== offset) abut = false; offset += b.data.length; }
  checkTrue('consecutive buffers abut on the sample grid, for every frame count', abut && offset === total, `${offset} vs ${total}`);
  const cat = new Float32Array(total);
  for (const b of st.bufs) cat.set(b.data, Math.round(b.when * SR) - s00);
  const ref = new Float32Array(total);
  new S.BeeperChip(SR).render(ref, 0, total, 0, all.map(e => [out.t0 + e[0] / FRAME_HZ - s00 / SR, e[1]]), 0);
  let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
  checkTrue('the scheduled buffers reconstruct ONE continuous render, sample for sample', worst < 1e-6, 'worst ' + worst.toExponential(2));
}
{
  const st = { now: 0, started: 0 };
  const So = new S.SoundOut();
  So.ctx = mockCtx(st); So.gain = { connect() {} }; So.chip = new S.BeeperChip(44100);
  So.flushBeeper([], 10);
  check('the first flush originates at now + the DEFAULT lead', [So.lead, So.t0], [0.08, 0.08]);
  st.now = 0.02; So.flushBeeper([[12, 1]], 15);
  checkTrue('a healthy flush schedules and never ratchets', So.live.length === 1 && So.underruns === 0 && So.lead === 0.08);
  const cursor = 0.08 + 5 / FRAME_HZ;
  st.now = 0.30; So.flushBeeper([], 20);
  const expect = (0.30 - cursor) + 0.08;
  checkTrue('an underrun ratchets the lead by the MEASURED deficit + margin', So.underruns === 1 && Math.abs(So.lead - expect) < 1e-9, So.lead.toFixed(5));
  checkTrue('...and the re-origin schedules with the NEW lead', Math.abs(So.t0 - (0.30 + expect)) < 1e-9);
  st.now = 5; So.flushBeeper([], 25);
  checkTrue('a huge stall caps the lead at SND_LEAD_MAX', So.underruns === 2 && So.lead === S.SND_LEAD_MAX);
  const led = So.lead, und = So.underruns, rs = So.resyncs;
  So.flushBeeper([], 2);
  checkTrue('a clock restart re-origins but does NOT ratchet -- it is not a tear', So.resyncs === rs + 1 && So.underruns === und && So.lead === led);
  checkTrue('info() is one pasteable line naming the transport', /^mode=sched sr=44100 lead=/.test(So.info()) && So.info().includes('wk=off'));
}
{
  let captured = null;
  sandbox.AudioContext = class { constructor(opts) { captured = opts; this.sampleRate = 48000; this.destination = {}; }
    createGain() { return { gain: { value: 0 }, connect() {} }; } };
  const S2 = new S.SoundOut();
  checkTrue('start() brings the context up under the mock', S2.start() === true);
  checkTrue('...asks for the playback latency class, not the default', !!captured && captured.latencyHint === 'playback');
  checkTrue('...and with no audioWorklet on the context, stays on the scheduler', S2.mode === 'sched' && S2.initPending === false);
  checkTrue('...with a beeper chip for the default instrument', S2.chip instanceof S.BeeperChip);
  const S2a = new S.SoundOut({ instrument: 'ay', gain: 0.5 });
  S2a.start();
  checkTrue('instrument "ay" builds an AyChip and honours the gain option', S2a.chip instanceof S.AyChip && S2a.gain.gain.value === 0.5);
  delete sandbox.AudioContext;
}
{
  /* the worklet module's TWO URLs: blob first (http), data: as the file://
     fallback, MEASURED in headless Chrome; the mocks' addModule returns a
     SYNCHRONOUS thenable, which the init chain supports on purpose */
  const mkCtx = (verdict) => class {
    constructor() { this.sampleRate = 48000; this.destination = {}; this.tried = []; const tried = this.tried;
      this.audioWorklet = { addModule: (url) => ({ then(ok, err) { tried.push(url.slice(0, 5)); verdict(url) ? ok() : err({ name: 'AbortError' }); } }) }; }
    createGain() { return { gain: { value: 0 }, connect() {} }; }
  };
  sandbox.Blob = Blob; sandbox.URL = URL; sandbox.btoa = btoa;
  sandbox.AudioWorkletNode = class { constructor(ctx, name, opts) { this.name = name; this.opts = opts;
    this.port = { posted: [], onmessage: null, postMessage(m) { this.posted.push(m); } }; } connect() {} };
  sandbox.AudioContext = mkCtx(url => !url.startsWith('blob:'));
  const S3 = new S.SoundOut(); S3.start();
  checkTrue('a blob-refusing platform (file://) falls back to the data: module',
            S3.mode === 'worklet' && S3.initPending === false && S3.ctx.tried.join() === 'blob:,data:');
  checkTrue('...recording WHY blob was refused for info()', S3.workletErr.indexOf('blob:AbortError') === 0 && S3.info().includes('wk=on'));
  checkTrue('...the node is registered under the kit\'s processor name', S3.node.name === 'spec-beeper' && S.WORKLET_SRC.includes("registerProcessor('spec-beeper'"));
  checkTrue('...and got its refill gate on arrival', S3.node.port.posted.length === 1 && S3.node.port.posted[0].min === Math.floor(0.08 * 48000));
  sandbox.AudioContext = mkCtx(() => false);
  const S4 = new S.SoundOut(); S4.start();
  checkTrue('both URLs refused: the scheduler keeps the game audible', S4.mode === 'sched' && S4.initPending === false);
  checkTrue('...and info() names both failures instead of staying silent', S4.info().includes('wk=blob:AbortError data:AbortError'));
  sandbox.AudioContext = mkCtx(() => true);
  const S5 = new S.SoundOut({ instrument: 'ay' }); S5.start();
  checkTrue('the AY instrument never asks for the worklet (declared: scheduler only)', S5.mode === 'sched' && S5.ctx.tried.length === 0);
  const S6 = new S.SoundOut({ instrument: 'mix' }); S6.start();
  checkTrue('the MIX takes the worklet stream, with a beeper chip and its AY not made until it sounds',
            S6.mode === 'worklet' && S6.ctx.tried.join() === 'blob:' && S6.chip instanceof S.BeeperChip && S6.aym === null);
  delete sandbox.AudioContext; delete sandbox.AudioWorkletNode; delete sandbox.Blob; delete sandbox.URL; delete sandbox.btoa;
}

/* =======================================================================
   THE WORKLET PATH: one continuous pull-model stream
   ======================================================================= */
{
  const sr = 44100;
  {
    const So = new S.SoundOut(); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    const edges = []; { let lv = 1; for (let f = 0.2; f < 60; f += 0.37) { edges.push([f, lv]); lv ^= 1; } }
    const log = []; let fed = 0;
    const feed = (upto) => { while (fed < edges.length && edges[fed][0] < upto) log.push(edges[fed++]); So.flushWorklet(log, upto); };
    So.flushWorklet([], 0);
    for (const u of [3, 8, 9, 15, 26, 41, 60]) feed(u);
    const total = Math.floor(60 / FRAME_HZ * sr);
    check('the stream sent exactly the whole-sample window of 60 frames', So.vsent, total);
    const cat = new Float32Array(total); { let o = 0; for (const c of chunks) { cat.set(c, o); o += c.length; } }
    const ref = new Float32Array(total);
    new S.BeeperChip(sr).render(ref, 0, total, 0, edges.map(e => [e[0] / FRAME_HZ, e[1]]), 0);
    let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
    checkTrue('the chunk concatenation IS the one-shot render, sample for sample', worst < 1e-7, 'worst ' + worst.toExponential(2));
    const rs = So.resyncs, n0 = chunks.length;
    So.flushWorklet([[1, 1]], 2);
    checkTrue('a clock restart re-origins the stream map without emitting',
              So.resyncs === rs + 1 && chunks.length === n0 && So.vbase === 2 && So.vsent === 0 && So.chip.lvl === 1);
    /* flush() dispatches on mode, and a custom frame clock is honoured */
    const S128 = new S.SoundOut({ frameHz: S.FRAME_HZ_128K }); const c2 = [];
    S128.ctx = { sampleRate: sr }; S128.chip = new S.BeeperChip(sr);
    S128.node = { port: { postMessage(m) { if (m.chunk) c2.push(m.chunk); } } }; S128.mode = 'worklet';
    S128.flush([], 0); S128.flush([], 50);
    check('a 128K frame clock tiles the stream at its own rate', S128.vsent, Math.floor(50 / S.FRAME_HZ_128K * sr));
  }
  {
    const So = new S.SoundOut(); const posted = [];
    So.ctx = { sampleRate: sr }; So.node = { port: { postMessage(m) { posted.push(m); } } };
    So.ratchetSamples(Math.round(0.05 * sr));
    checkTrue('an underrun report ratchets lead to episode + margin', So.underruns === 1 && Math.abs(So.lead - 0.13) < 1e-3);
    checkTrue('...and posts the worklet its new refill gate', posted.length === 1 && posted[0].min === Math.floor(So.lead * sr));
    So.ratchetSamples(sr * 2);
    checkTrue('...and a huge episode caps at SND_LEAD_MAX', So.lead === S.SND_LEAD_MAX);
  }
  {
    /* the processor itself, eval'd from the SAME source string the page
       ships, with the worklet globals stubbed */
    let ProcCls = null; const reports = [];
    const AudioWorkletProcessor = class { constructor() { this.port = { onmessage: null, postMessage: m => reports.push(m) }; } };
    const registerProcessor = (name, cls) => { ProcCls = cls; };
    void AudioWorkletProcessor; void registerProcessor;
    eval(S.WORKLET_SRC);
    const p = new ProcCls();
    const msg = d => p.port.onmessage({ data: d });
    const spin = () => { const o = new Float32Array(128); p.process([], [[o]]); return o; };
    msg({ min: 100 });
    let o = spin();
    checkTrue('before anything arrives: silence, and NO underrun report', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(60).fill(0.5) }); o = spin();
    checkTrue('below the refill gate the stream does not start yet', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(80).fill(0.25) }); o = spin();
    checkTrue('at the gate it starts -- and boot silence was NOT an underrun', reports.length === 0 && o[0] === 0.5 && o[127] === 0.25);
    o = spin();
    checkTrue('a dry queue emits zeros mid-episode without reporting yet', reports.length === 0 && o[11] === 0.25 && o[12] === 0);
    msg({ chunk: new Float32Array(50).fill(0.75) }); o = spin();
    checkTrue('recovery ALSO waits for the refill gate -- no fragile resume', reports.length === 0 && o.every(v => v === 0));
    msg({ chunk: new Float32Array(80).fill(0.75) }); o = spin();
    checkTrue('resuming reports the episode length, once', reports.length === 1 && reports[0].underrun === 244 && o[0] === 0.75);
  }
}

/* =======================================================================
   THE MIX: a 128K's beeper AND its AY on ONE stream (instrument 'mix')
   The reference is built here, independently of SoundOut: one BeeperChip
   over every edge, one AyChip driven write by write at the sample its
   fractional frame falls in -- floor((f - origin) / frameHz * sr), silent
   (not stepped) before its first write -- DC-blocked by the 20 Hz one pole
   and scaled by ayMix, the two summed.  Each transport must reproduce it.
   ======================================================================= */
{
  const sr = 44100, FHZ = FRAME_HZ;
  /* sec(f): a frame's time from the render's first sample; smp(f): the sample a write falls in -- the map's own
     floor, the specification of "its sample" */
  const refMix = (edges, rows, total, sec, smp, mix) => {
    const ref = new Float32Array(total);
    new S.BeeperChip(sr).render(ref, 0, total, 0, edges.map(e => [sec(e[0]), e[1]]), 0);
    const ay = new S.AyChip(sr, S.AY_CLOCK), raw = new Float32Array(total);
    let at = 0, live = false;
    for (const [f, r, v] of rows) {
      const k = smp(f);
      if (k > at) { if (live) ay.render(raw, at, k - at); at = k; }
      ay.write(r, v); live = true;
    }
    if (live && at < total) ay.render(raw, at, total - at);
    const R = 1 - 2 * Math.PI * 20 / sr; let px = 0, py = 0;
    for (let i = 0; i < total; i++) { const y = raw[i] - px + R * py; px = raw[i]; py = y; ref[i] += mix * y; }
    return ref;
  };
  /* a tune: tone A, then B over A, a volume change, noise on C under an envelope, the mixer last -- writes at
     fractional frames; two in the SLIVER past a flush's last whole sample (frame < upto, its sample the next
     window's), two in a window's last sample */
  const edges = []; { let lv = 1; for (let f = 0.3; f < 60; f += 0.41) { edges.push([f, lv]); lv ^= 1; } }
  const sliver = u => { const x = u / FHZ * sr, s = Math.floor(x); return (s + (x - s) / 2) / sr * FHZ; };
  const lastSmp = u => { const s = Math.floor(u / FHZ * sr); return (s - 0.5) / sr * FHZ; };
  const rows = [[1.25, 0, 0x7D], [1.25, 1, 0], [1.2502, 7, 0x3E], [1.75, 8, 15], [4.5, 2, 0xFA], [4.5, 3, 1],
                [4.6, 7, 0x3C], [4.6, 9, 12], [lastSmp(8), 8, 11], [sliver(8), 8, 9], [10.333, 6, 7], [10.333, 11, 0x40],
                [10.333, 12, 0], [10.4, 13, 0x0E], [10.4, 10, 0x10], [10.41, 7, 0x1C], [lastSmp(26), 9, 13],
                [sliver(26), 9, 15], [33.7, 8, 0], [47.9, 7, 0x3F]]
    .sort((x, y) => x[0] - y[0]);
  const UPTO = [3, 8, 9, 15, 26, 41, 60];
  const feedAll = (flush) => {
    const log = [], alog = []; let fe = 0, fa = 0;
    flush(log, 0, alog);
    for (const u of UPTO) {
      while (fe < edges.length && edges[fe][0] < u) log.push(edges[fe++]);
      while (fa < rows.length && rows[fa][0] < u) alog.push(rows[fa++]);
      flush(log, u, alog);
    }
    return { log, alog };
  };
  /* (1) the worklet: chunk for chunk, the one-shot render -- at a mix of 0.6, so the level is in the sum */
  {
    const So = new S.SoundOut({ instrument: 'mix', ayMix: 0.6 }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    const left = feedAll((l, u, a) => So.flush(l, u, a));
    const total = Math.floor(60 / FHZ * sr);
    const cat = new Float32Array(total); { let o = 0; for (const c of chunks) { cat.set(c, o); o += c.length; } }
    const ref = refMix(edges, rows, total, f => f / FHZ, f => Math.floor(f / FHZ * sr), So.ayMix);
    let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
    let peak = 0; for (let i = 0; i < total; i++) peak = Math.max(peak, Math.abs(ref[i]));
    checkTrue('MIX, worklet: the chunks ARE one render of both chips -- every AY write at the sample its fractional ' +
              'frame falls in (two in the sliver past a window’s last sample, two in its last sample), at the mix’s own ' +
              'level, sample for sample', worst < 1e-6 && peak > 0.3 && So.ayMix === 0.6 && So.info().includes(' aymix=0.60 ') &&
              left.alog.length === 0 && left.log.length === 0 && So.ayWrites === rows.length && So.ayLate === 0,
              'worst ' + worst.toExponential(2) + ' peak ' + peak.toFixed(3) + ' writes ' + So.ayWrites);
  }
  /* (2) the scheduled path (the fallback), its buffers laid end to end */
  {
    const st = { now: 10, started: 0, bufs: [] };
    const So = new S.SoundOut({ instrument: 'mix' });
    So.ctx = mockCtx(st); So.gain = { connect() {} }; So.chip = new S.BeeperChip(sr);
    feedAll((l, u, a) => So.flush(l, u, a));
    const s00 = Math.floor(st.bufs[0].when * sr), total = Math.floor((So.t0 + 60 / FHZ) * sr) - s00;
    const cat = new Float32Array(total); for (const b of st.bufs) cat.set(b.data, Math.round(b.when * sr) - s00);
    /* the map's origin is t0 (frame 0): the reference's sample 0 is the first buffer's, s00 on the context's grid */
    const ref = refMix(edges, rows, total, f => So.t0 + f / FHZ - s00 / sr, f => Math.floor((So.t0 + f / FHZ) * sr) - s00,
                       So.ayMix);
    let worst = 0; for (let i = 0; i < total; i++) worst = Math.max(worst, Math.abs(cat[i] - ref[i]));
    checkTrue('MIX, scheduled: the buffers ARE the same one render, on the context’s sample grid',
              worst < 1e-6 && st.bufs.length === UPTO.length && So.resyncs === 0, 'worst ' + worst.toExponential(2));
  }
  /* (3) a write lands ON its sample: R8 = 15 under R7 = $3F (every generator off: the level itself) at frame 10.5 on
     a map originated at frame 5 -- the first non-zero sample is floor((10.5 - 5) / frameHz * sr) from the origin's,
     not the frame's start, nor the next; on the worklet's stream and on the scheduled buffers' context grid */
  {
    const So = new S.SoundOut({ instrument: 'mix' }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    So.flush([], 5, []); So.flush([], 10, [[6, 7, 0x3F]]); So.flush([], 12, [[10.5, 8, 15]]);
    const cat = [].concat(...chunks.map(c => Array.from(c)));
    const first = cat.findIndex(v => Math.abs(v) > 1e-9);
    const st = { now: 10, started: 0, bufs: [] };
    const Sc = new S.SoundOut({ instrument: 'mix' });
    Sc.ctx = mockCtx(st); Sc.gain = { connect() {} }; Sc.chip = new S.BeeperChip(sr);
    Sc.flush([], 5, []); Sc.flush([], 10, [[6, 7, 0x3F]]); Sc.flush([], 12, [[10.5, 8, 15]]);
    const s00 = Math.floor(st.bufs[0].when * sr), cs = new Float32Array(Math.floor((Sc.t0 + 7 / FHZ) * sr) - s00);
    for (const b of st.bufs) cs.set(b.data, Math.round(b.when * sr) - s00);
    const fs = cs.findIndex(v => Math.abs(v) > 1e-9);
    check('MIX: an AY write sounds from the sample its fractional frame falls in (worklet, scheduled)',
          /* a write that never sounds is a FAILED row (null), never a throw that ends the file */
          [first, first >= 0 ? +cat[first].toFixed(6) : null, fs >= 0 ? fs + s00 : null, fs >= 0 ? +cs[fs].toFixed(6) : null],
          [Math.floor((10.5 - 5) / FHZ * sr), +(So.ayMix / 3).toFixed(6), Math.floor((Sc.t0 + 5.5 / FHZ) * sr),
           +(So.ayMix / 3).toFixed(6)]);
  }
  /* (4) never written: the AY is not made and not rendered -- the stream IS the beeper's alone */
  {
    const mk = (inst) => { const So = new S.SoundOut({ instrument: inst }); const ch = [];
      So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
      So.node = { port: { postMessage(m) { if (m.chunk) ch.push(m.chunk); } } }; So.mode = 'worklet'; return [So, ch]; };
    const [Sm, cm] = mk('mix'), [Sb, cb] = mk('beeper');
    const lm = [], lb = [], am = [];
    Sm.flush(lm, 0, am); Sb.flush(lb, 0);
    let prev = 0;
    for (const u of UPTO) {
      const ne = edges.filter(e => e[0] >= prev && e[0] < u); prev = u;
      lm.push(...ne); lb.push(...ne); Sm.flush(lm, u, am); Sb.flush(lb, u);
    }
    const a = [].concat(...cm.map(c => Array.from(c))), b = [].concat(...cb.map(c => Array.from(c)));
    const ab = [[1, 8, 15]]; Sb.flush([], UPTO[UPTO.length - 1] + 1, ab);
    checkTrue('MIX: an AY never written is never made nor rendered -- the stream is the beeper’s, sample for sample (a ' +
              '48K machine on a mix page costs nothing); and a BEEPER ignores an AY log handed to it (' + ab.length + ' left)',
              Sm.aym === null && !Sm.ayLive && a.length === b.length && ab.length === 1 && Sb.aym === null && Sb.ayWrites === 0 &&
              a.every((v, i) => v === b[i]) && /chips=beeper\+ay ay=idle ayw=0 aylate=0 aymix=1\.00 resets=0$/.test(Sm.info()),
              Sm.info());
  }
  /* (5) no context yet, and sound off: the logs are emptied, the AY's registers SHADOWED -- the chip, made when the
     context comes up, sounds what the driver left (a level of 15 under R7 = $3F: the first sample is ayMix / 3) */
  {
    const st = { now: 10, started: 0, bufs: [] };
    const So = new S.SoundOut({ instrument: 'mix' });
    const log = [[0.5, 1]], alog = [[0.25, 7, 0x3F], [0.5, 8, 15], [0.75, 13, 0x0A]];
    So.flush(log, 1, alog);                                   // no context: before the page's first gesture
    const shadow = [So.ayReg[7], So.ayReg[8], So.ayReg[13], log.length, alog.length, So.ayLive];
    So.ctx = mockCtx(st); So.gain = { connect() {} }; So.chip = new S.BeeperChip(sr);
    So.flush([], 2, []); So.flush([], 3, []);
    const b0 = st.bufs[0] && st.bufs[0].data[0];
    const So2 = new S.SoundOut({ instrument: 'mix' }); So2.on = false;
    const l2 = [[0.5, 1]], a2 = [[0.5, 9, 7]];
    So2.ctx = mockCtx({ now: 0, started: 0 }); So2.flush(l2, 1, a2);
    const So3 = new S.SoundOut({ instrument: 'mix' }); So3.on = false; So3.mode = 'worklet'; So3.ctx = { sampleRate: sr };
    const l3 = [[0.5, 1]], a3 = [[0.5, 10, 9]]; So3.flush(l3, 1, a3);
    /* ONLY THE REGISTERS WRITTEN are replayed into the new chip: R13 never written, its envelope is power-on's (level
       0 until its first step -- R11/R12 $FFFF: 0.59 s), so A in envelope mode is SILENT; a replayed R13 = 0 would
       restart it at 15 */
    const st4 = { now: 10, started: 0, bufs: [] };
    const So4 = new S.SoundOut({ instrument: 'mix' });
    So4.flush([], 1, [[0.2, 7, 0x3F], [0.3, 11, 0xFF], [0.3, 12, 0xFF], [0.4, 8, 0x10]]);
    So4.ctx = mockCtx(st4); So4.gain = { connect() {} }; So4.chip = new S.BeeperChip(sr);
    So4.flush([], 2, []); So4.flush([], 6, []);
    const env = st4.bufs[0] ? Math.max(...st4.bufs[0].data.map(Math.abs)) : -1;
    checkTrue('MIX: with no context the logs are emptied and the AY’s registers kept (' + JSON.stringify(shadow) +
              '); when it comes up the chip is made from them -- the first sample ' + (b0 && b0.toFixed(6)) +
              ' -- and sound OFF keeps them too', JSON.stringify(shadow) === JSON.stringify([0x3F, 15, 0x0A, 0, 0, true]) &&
              Math.abs(b0 - So.ayMix / 3) < 1e-6 && So.aym !== null && So.aym.reg[8] === 15 && So.aym.reg[13] === 0x0A &&
              l2.length === 0 && a2.length === 0 && So2.ayReg[9] === 7 && l3.length === 0 && a3.length === 0 &&
              So3.ayReg[10] === 9 && So4.aySeen === 0x1980 && env === 0,
              'worklet off ' + JSON.stringify([l3.length, a3.length, So3.ayReg[10]]) + ', the envelope peak ' + env);
  }
  /* (6) a clock RESTART and a DROPPED buffer still leave the registers where the driver left them */
  {
    const So = new S.SoundOut({ instrument: 'mix' }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    So.flush([], 0, []); So.flush([], 20, [[3, 8, 5]]);
    const rs = So.resyncs, n0 = chunks.length;
    const al = [[18.5, 8, 11], [19.5, 7, 0x3E]];
    So.flush([], 4, al);                                       // the simulated clock went BACK: a restart
    const st = { now: 10, started: 0 };
    const Sd = new S.SoundOut({ instrument: 'mix' });
    Sd.ctx = mockCtx(st); Sd.gain = { connect() {} }; Sd.chip = new S.BeeperChip(sr);
    Sd.next = 0; Sd.base = 0; Sd.t0 = st.now + 0.05; Sd.live = [];
    for (let i = 0; i < 60; i++) Sd.live.push(st.now + 5);    // the voice cap is full
    const ad = [[1.5, 8, 13], [3.5, 9, 4], [6, 10, 2]];
    Sd.flush([], 4, ad);
    const sr0 = { now: 10, started: 0 }, Sr = new S.SoundOut({ instrument: 'mix' });
    Sr.ctx = mockCtx(sr0); Sr.gain = { connect() {} }; Sr.chip = new S.BeeperChip(sr);
    Sr.flush([], 0, []); Sr.flush([], 8, [[2, 8, 3]]);
    const ar = [[7.5, 8, 12], [7.75, 9, 6]], n1 = sr0.started; Sr.flush([], 3, ar);
    checkTrue('MIX: a restart writes the AY log into the registers without emitting (R8 ' + So.ayReg[8] + ', R7 ' +
              So.ayReg[7] + '), and a dropped buffer writes those below its frame (R8 ' + Sd.ayReg[8] + ', R9 ' + Sd.ayReg[9] +
              ', R10 ' + Sd.ayReg[10] + ' -- the frame-6 write left for the next)',
              So.resyncs === rs + 1 && chunks.length === n0 && al.length === 0 && So.ayReg[8] === 11 && So.ayReg[7] === 0x3E &&
              Sd.dropped === 1 && st.started === 0 && Sd.ayReg[8] === 13 && Sd.ayReg[9] === 4 && Sd.ayReg[10] === 0 && ad.length === 1 &&
              Sr.resyncs === 1 && sr0.started === n1 && ar.length === 0 && Sr.ayReg[8] === 12 && Sr.ayReg[9] === 6,
              'scheduled restart ' + JSON.stringify([Sr.resyncs, sr0.started - n1, ar.length, Sr.ayReg[8], Sr.ayReg[9]]));
  }
  /* (7) reset(): a NEW machine -- the AY back to power-on silence (a droning tone stops), the map re-originated,
     counted as a reset and never as a resync, the lead untouched */
  {
    const So = new S.SoundOut({ instrument: 'mix' }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    So.flush([], 0, []); So.flush([], 10, [[1, 0, 0x7D], [1, 7, 0x3E], [1, 8, 15], [1, 13, 0x0E]]);
    const before = chunks.length, rs = So.resyncs, lead = So.lead;
    const drone = chunks[chunks.length - 1].some(v => Math.abs(v) > 0.05);
    So.reset();
    const st = [So.resets, So.ayLive, So.aym, Array.from(So.ayReg).every(v => v === 0), So.next];
    So.flush([], 1, []);                                      // the new machine's first flush: the origin, no chunk
    So.flush([], 30, []);
    /* the new machine's first writes, A in envelope mode: R13 was written BEFORE the reset -- it is not replayed */
    So.flush([], 32, [[30.5, 7, 0x3F], [30.5, 11, 0xFF], [30.5, 12, 0xFF], [30.5, 8, 0x10]]);
    const after = chunks.slice(before);
    checkTrue('MIX: reset() silences the AY (a droning tone: ' + drone + ' -> ' + after.length + ' chunk, peak ' +
              (after[0] ? Math.max(...after[0].map(Math.abs)).toExponential(1) : '?') + '), re-origins the map (' +
              So.vbase + ', ' + So.vsent + ') and counts a reset, not a resync (' + So.resets + ', ' + (So.resyncs - rs) + ')',
              drone && JSON.stringify(st) === JSON.stringify([1, false, null, true, null]) && after.length === 2 &&
              after[0].every(v => v === 0) && after[1].every(v => v === 0) && So.ayLive && So.aySeen === 0x1980 &&
              So.vbase === 1 && So.resyncs === rs && So.lead === lead &&
              /aymix=1\.00 resets=1$/.test(So.info()));
  }
  /* (7b) THE REVIEW'S CASE: the old machine left the speaker HIGH; reset() puts it LOW at the reboot (EAR is 0 at
     power-on), so the step is heard THERE and not at the new machine's first edge to 0, thirty frames on; the first
     flush adopts the driver's state (a level, the AY instrument's registers); reset() on the AY instrument is a fresh
     chip */
  {
    const So = new S.SoundOut({ instrument: 'mix' }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    So.flush([], 0, []); So.flush([[2.5, 1]], 10, []);
    const high = So.chip.lvl;
    So.reset();
    const low = So.chip.lvl, n0 = chunks.length;
    So.flush([], 1, []); So.flush([], 30, []); So.flush([[30.5, 0]], 40, []);
    const pk = c => c ? Math.max(...Array.from(c, Math.abs)) : -1;
    const atBoot = pk(chunks[n0]), atEdge = pk(chunks[n0 + 1]);
    const F = new S.SoundOut({ instrument: 'mix' }); F.ctx = { sampleRate: sr }; F.chip = new S.BeeperChip(sr);
    F.node = { port: { postMessage() {} } }; F.mode = 'worklet';
    F.flush([[0.5, 1]], 1, []);                               // the first flush: the origin, with an edge logged
    const st = { now: 10, started: 0 }, Fs = new S.SoundOut({ instrument: 'mix' });
    Fs.ctx = mockCtx(st); Fs.gain = { connect() {} }; Fs.chip = new S.BeeperChip(sr);
    Fs.flush([[0.5, 1]], 1, []);
    const Fa = new S.SoundOut({ instrument: 'ay' }); Fa.ctx = mockCtx({ now: 10, started: 0 }); Fa.gain = { connect() {} };
    Fa.chip = new S.AyChip(sr, S.AY_CLOCK);
    Fa.flush([[0.5, 8, 15], [0.75, 7, 0x3E]], 1);             // the AY instrument's first flush
    const firstAy = [Fa.chip.reg[8], Fa.chip.reg[7]];
    const old = Fa.chip; Fa.reset();
    checkTrue('MIX: reset() puts the speaker LOW (' + high + ' -> ' + low + '): its step at the reboot (peak ' + atBoot.toFixed(3) +
              ') and none at the new machine’s first edge to 0 (' + atEdge.toExponential(1) + '); the first flush adopts the ' +
              'driver’s level (worklet ' + F.chip.lvl + ', scheduled ' + Fs.chip.lvl + ') and the AY instrument’s registers (' +
              JSON.stringify(firstAy) + '); reset() makes the AY instrument a fresh chip',
              high === 1 && low === 0 && atBoot > 0.5 && atEdge < 1e-3 && F.chip.lvl === 1 && Fs.chip.lvl === 1 &&
              JSON.stringify(firstAy) === JSON.stringify([15, 0x3E]) && Fa.chip !== old && Fa.chip instanceof S.AyChip &&
              Array.from(Fa.chip.reg).every(v => v === 0) && Fa.chip.sr === sr && Fa.next === null && Fa.resets === 1);
  }
  /* (8) a row that arrives BEHIND its window (a driver's late log) is written at the window's start and COUNTED */
  {
    const So = new S.SoundOut({ instrument: 'mix' }); const chunks = [];
    So.ctx = { sampleRate: sr }; So.chip = new S.BeeperChip(sr);
    So.node = { port: { postMessage(m) { if (m.chunk) chunks.push(m.chunk); } } }; So.mode = 'worklet';
    So.flush([], 0, []); So.flush([], 10, [[2, 7, 0x3F]]);
    So.flush([], 12, [[5, 8, 15]]);                           // frame 5: already rendered at frame 10
    const c = chunks[chunks.length - 1];
    checkTrue('MIX: a late AY row is written at the start of the window it arrives in, and counted (aylate ' +
              So.ayLate + ', first sample ' + c[0].toFixed(6) + ')', So.ayLate === 1 && Math.abs(c[0] - So.ayMix / 3) < 1e-6 &&
              So.info().includes(' aylate=1 '));
  }
  check('the beeper and the AY alone name their one chip in info()', [new S.SoundOut().info().split(' wk=off')[1],
        new S.SoundOut({ instrument: 'ay' }).info().split(' wk=off')[1]], [' chips=beeper resets=0', ' chips=ay resets=0']);
}

/* =======================================================================
   THE LOOP, THE SETTINGS, AND THE STARTER DEMO END TO END
   ======================================================================= */
{
  const st = S.settingsStore('kit-test');
  checkTrue('settingsStore.save reports that the write LANDED', st.save({ a: 1 }) === true && rig.localStorageStore.has('kit-test'));
  check('...and load reads it back', st.load(), { a: 1 });
  st.clear();
  check('...and clear removes it', st.load(), null);
}
{
  const d = new P.Demo(); const kb = new S.Keyboard();
  check('the demo starts with its block at the centre', [d.x, d.y], [15, 11]);
  kb.press('P'); d.step(kb);
  check('P moves the block right on a movement frame', d.x, 16);
  d.step(kb); d.step(kb); d.step(kb);
  check('...and holds for the next three frames', d.x, 16);
  kb.releaseAll(); kb.kempston = S.KEMPSTON_UP; d.step(kb);
  check('the Kempston byte moves it too', d.y, 10);
  kb.releaseAll();
  const f0 = d.simFrame;
  kb.press('SPACE'); d.step(kb);
  const half = FRAME_HZ / (2 * 440), want = Math.ceil(1 / half);
  checkTrue('SPACE logs a 440 Hz edge stream on the SIMULATED clock, inside the frame',
            (d.sound.log.length === want || d.sound.log.length === want - 1) &&
            d.sound.log.every(e => e[0] >= f0 && e[0] < f0 + 1) && d.sound.log[0][1] === 1,
            `${d.sound.log.length} edges`);
  const n1 = d.sound.log.length; d.step(kb);
  checkTrue('...phase-continuous into the next frame (no edge repeats, no gap)',
            d.sound.log.length > n1 && d.sound.log[n1][0] - d.sound.log[n1 - 1][0] > half * 0.999 &&
            d.sound.log[n1][0] - d.sound.log[n1 - 1][0] < half * 1.001);
  check('...and reddens the border while firing', d.border, 2);
  kb.releaseAll(); d.step(kb);
  check('releasing leaves the speaker LOW with one closing edge', [d.sound.log[d.sound.log.length - 1][1], d.border], [0, 0]);
}
{
  /* the page's own loop, driven through the captured rAF: three and a half
     frames of wall time is three simulation steps, and the bridge is fed
     from draw with the simulated frame count */
  const st = { now: 10, started: 0 };
  /* the keydown tests above already gestured start() in a sandbox with no
     AudioContext, which correctly switched audio OFF; hand it a mock now.
     This drives the PORT ENGINE (P.game) through the page's real loop -- the
     game-specific replacement of the kit starter block (manual phase 14). */
  P.sound.on = true; P.sound.ctx = mockCtx(st); P.sound.gain = { connect() {} }; P.sound.chip = new S.BeeperChip(44100);
  const cb = rig.raf();
  const before = P.game.frame;
  cb(0);
  check('the first rAF only sets the clock', P.game.frame - before, 0);
  cb(3.5 / FRAME_HZ * 1000);
  check('3.5 frames of wall time step the engine exactly 3 frames', P.game.frame - before, 3);
  checkTrue('the sound bridge tracks the engine simFrame from draw', P.sound.next === P.game.simFrame);
  cb(4000);
  checkTrue('a long stall is capped at maxDt, not replayed', P.game.frame - before <= 6 + Math.ceil(0.25 * FRAME_HZ));
}

/* ---- the ship/test asset split (kit-generic) -------------------------- */
{
  const fs2 = require('fs'), path2 = require('path');
  const cfg = JSON.parse(fs2.readFileSync(path2.join(rig.ROOT, 'port.json'), 'utf8'));
  const m = html.match(/id="assets">([\s\S]*?)<\/script>/);
  const payload = JSON.parse(m[1].split('<\/').join('</'));
  const onDisk = a => fs2.existsSync(path2.join(rig.ROOT, a.file));
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const ship = (cfg.assets || []).filter(a => a.ship !== false && onDisk(a));
  const held = (cfg.assets || []).filter(a => a.ship === false && onDisk(a));
  /* *** THE SPLIT IS ONLY SAFE IF IT IS ASSERTED IN BOTH DIRECTIONS. ***  An
     asset held back by mistake makes the PAGE quietly wrong; one shipped by
     mistake makes it quietly fat.  `ship` defaults to TRUE, so the dangerous
     direction takes a deliberate `ship: false`. */
  check('every shipped asset is in the page payload', ship.filter(a => !has(payload, a.key)).length, 0);
  check('no ship:false asset is in the page payload', held.filter(a => has(payload, a.key)).length, 0);
  checkTrue('...and the suite still sees every held-back one, loaded from disk by the rig: ' +
            held.length + ' held back, ' + Object.keys(P.assets).length + ' visible to the test',
            held.every(a => has(P.assets, a.key)));
  check('the payload is the shipped assets and nothing else',
        Object.keys(payload).length, ship.length);
}

/* ---- the rig's event bus runs listeners as a browser does (kit-generic) --
   In registration order, and none after one that calls
   stopImmediatePropagation(): a page that keeps a key from a later listener
   (a fullscreen key ahead of attachKeyboard's) is only testable if the rig
   stops where a browser stops. */
{
  const seen = [];
  rig.sandbox.addEventListener('x-rig-order', () => seen.push('a'));
  rig.sandbox.addEventListener('x-rig-order', e => { seen.push('b'); if (e.stop) e.stopImmediatePropagation(); });
  rig.sandbox.addEventListener('x-rig-order', () => seen.push('c'));
  rig.fire('x-rig-order', {});
  rig.fire('x-rig-order', { stop: true });
  check('the rig runs an event’s listeners in order, and none after stopImmediatePropagation()', seen.join(''), 'abcab');
}

rig.done();
