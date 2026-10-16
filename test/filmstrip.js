/* filmstrip.js -- drive the BUILT page headlessly and dump display files.
 *
 * Not a gate.  This exists so a human can LOOK at the port (manual phase 16 --
 * the things a test cannot tell you: does it move right, does it read as Bubble
 * Bobble, is the HUD in the right place).
 *
 * The engine's player takes its direction from the entity's +8 byte; the key
 * DECODE is part of a pass the engine does not model yet, so the script pokes
 * +8 directly -- which is exactly what the machine's reader would have written.
 *
 *   node test/filmstrip.js [frames] [every]
 *
 * writes build/frames/f####.bin, each a full 64K image; render with
 *   python tools/strip.py
 */
const fs = require('fs');
const path = require('path');
const R = require('./rig.js');

const FRAMES = +(process.argv[2] || 600);
const EVERY = +(process.argv[3] || 40);
const OUT = path.join(R.ROOT, 'build', 'frames');

const { P } = R.loadBuilt();
const g = new P.BB_Game(P.assets);
g.reset();

const P1 = 0xFD80;
/* +8, the decoded direction the machine's key reader leaves for $A5xx:
   bit 2 = face/move right, bit 3 = face/move left, bit 0 = fire (blow),
   bit 4 = suppress.  Kept as a little script so the strip shows motion in
   both directions and some bubbles. */
function dirAt(f) {
  const t = f % 320;
  if (t < 110) return 0x04;                 // walk right
  if (t < 130) return 0x04 | 0x01;          // ...and blow
  if (t < 240) return 0x08;                 // walk left
  if (t < 260) return 0x08 | 0x01;          // ...and blow
  return 0x00;                              // stand
}

/* Put items on the board.  $8C5E clears the block and stages the round's two
 * spawn positions; the fruit entries here stand in for the corpse landings that
 * I9 will produce, written in the machine's own format:
 *     byte0 = (X & $F0) | (type & $0F)      byte1 = (Y & $F8) | phase
 * The per-frame walk $8689 is driven explicitly because the gated wrapper $8669
 * -- the edge detector and the lifetime clock -- is I5, not yet modelled.  So
 * these items draw and stay put: nothing ages them and nothing collects them.
 */
g.ram[0x8609] = 1;
g.itemRoundBuild();
const PLACED = [[1, 0x40, 0xA8, 0], [3, 0x70, 0x88, 1], [5, 0xB0, 0xA8, 2],
                [7, 0x90, 0x68, 3], [9, 0x50, 0x68, 4], [11, 0xC0, 0x48, 5]];
for (const [slot, x, y, type] of PLACED) {
  g.ram[0x9603 + 2 * slot] = (x & 0xF0) | (type & 0x0F);
  g.ram[0x9603 + 2 * slot + 1] = (y & 0xF8) | 1;
}
g.ram[0x9603] = (0x30 & 0xF0) | 10;        // the power-up slot: type 10, random ink
g.ram[0x9604] = (0xC8 & 0xF8) | 1;

fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (f.endsWith('.bin')) fs.unlinkSync(path.join(OUT, f));

let wrote = 0;
for (let f = 0; f < FRAMES; f++) {
  g.ram[P1 + 8] = dirAt(f);
  g.step(null);
  g.itemPass();                 // $8689 -- driven here; its $8669 wrapper is I5
  if (f % EVERY === 0) {
    fs.writeFileSync(path.join(OUT, 'f' + String(f).padStart(4, '0') + '.bin'),
                     Buffer.from(g.ram));
    wrote++;
  }
}
/* a census, so the strip comes with numbers rather than only vibes */
let enemies = 0, bubbles = 0, items = 0;
for (let k = 2; k < 12; k++) if (g.ram[0xFD80 + 10 * k + 7] & 0x80) enemies++;
for (let k = 0; k < 12; k++) if (g.ram[0xFED8 + 10 * k + 7] & 0x80) bubbles++;
for (let k = 0; k < 32; k++) if (g.ram[0x9603 + 2 * k]) items++;
let inks = new Set();
for (let a = 0x5800; a < 0x5B00; a++) if (g.ram[a] & 7) inks.add(g.ram[a] & 7);
console.log('frames ' + FRAMES + ', dumped ' + wrote + ' to build/frames/');
console.log('  at the end: P1 at (' + g.ram[P1 + 5] + ',' + g.ram[P1 + 6] + ')' +
            ', enemies alive ' + enemies + ', bubbles ' + bubbles +
            ', item slots occupied ' + items +
            ', distinct inks on screen ' + JSON.stringify([...inks].sort()));
