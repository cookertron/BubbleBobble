/* =====================================================================================================================
   THE DEBUG LAYER -- ADDED, and ONLY in the debug page (the owner, 2026-10-16: "a copy of the build but add debug
   features -- jump to level, trigger bonus item, kill all enemies, EXTEND, that sort of thing").

   tools/build_debug.py appends this file to the END of the built page's script -- after the page's own code and its
   __PORT__ hook, so it sees `game`, `sound`, `machine` and the engine's classes -- and writes the result as
   web/bubble_bobble_debug.html.  THE FAITHFUL PAGE NEVER CONTAINS IT: the build refuses a faithful page that carries
   BB_DBG, and proves the debug page is the faithful page plus this file (its title and banner aside), byte for byte.

   HOW IT ACTS -- through the game's own RAM and the game's own routines, BETWEEN two frames, never inside one, and
   only when no part of the engine is half-way through something (bbDbgBusy: a round start, a banner, a cutscene, a
   storm tick, the pause ...).  An action asked for at a busy moment is QUEUED and lands at the first quiet frame
   boundary; the panel says what it is waiting for.  Each action is the machine's own mechanism, entered at a point
   play can reach:
     - a JUMP arms the round the game's NEXT ADVANCE builds: $97F8 (roundAdvanceCore, hooked) finds ($8609) set one
       short of the target, so its own INC, lookahead, build, banner and settle run as they do between two rounds.
       The two BUILD COUNTERS ($82D7 the palette, mod 15; $83EC the platform tile, mod 5 -- SPEC: one step per build,
       not a function of the round) are stepped by the builds the jump skipped, so round N comes out in the colours and
       tiles a straight run from round 1 gives it.  Then the round is CLEARED the game's way (below) to make that
       advance happen.  Arming at the title (or the control select, or the game-over screen) starts the next game at
       the round armed.
     - a CLEAR / KILL turns every free enemy into a corpse through $8BC2 (corpseBirth -- the storm's, the fire's and
       the bolt's kill), and bursts every bubble that holds an enemy with the storm's own burst ($A0F5: +3 := 10,
       SET 3 / SET 1 of +7), so the game's pop kills what is inside.  The corpses fall and land as fruit, the game's
       clear ($8ECF) follows when the last has landed; a CLEAR then skips only the WAIT -- the countdown's window
       ($8F29: timer $0177..$01FF) is reached by setting the play timer to $0175 / $0176, the one of the two with the
       timer's own parity, so the interrupts keep their odd / even order.  On round 80 the boss's HP ($9F62) goes to
       0: his defeat is the game's own ($8E4E).
     - a POWER-UP or a FOOD ITEM is placed where the round's own spawn puts it: $89FB's tail into the slot ($9603, or
       entry 0 of $9605), X from $8CAE / $8CAF, the Y $8C98 laid at the round's build, a fresh item's phase, the
       spawn's one-shot latch ($8CB0) set as $8A10 / $89E2 set it -- an umbrella arms $8A45's lock too.  A slot
       already holding an item is emptied first the way the round clear empties it ($8ED7..$8EDF: phase 3, the phase
       clock wrapped), so the game's own expiry erases it -- which ages every other item on screen one phase too.
     - an EXTEND letter is what a letter pop leaves ($B7E5: the bit in $FDE3 / $FDED, the trigger $FED5 := 1): the
       game's $948F takes it on its next pass -- the wall panel, and with all six the "N I C E" cutscene, the life and
       the advance.
     - HURRY UP / BARON set the play timer past ($745C) or ($745C) + 500 (the same parity rule): $9037 and $917C fire
       on their own next pass.
     - INVINCIBLE holds the game's own RESPAWN invulnerability: +$5A bit 3 (the immunity $9289 / $9DC5 test) with the
       countdown +4 held at $50, so the player flashes as after a respawn; turned off, the countdown runs out by
       itself.  INFINITE LIVES keeps the spare lives from dropping under the count it was turned on with, and redraws
       the panel ($806C, livesIcons).
     - SPEED: freeze, one frame, slow motion and turbo -- the engine's frames themselves, so a turbo or slow frame is
       still exactly one machine frame; the sound is muted while the speed is not 1x (the bridge would pile up).
   What it cannot make faithful, it says: the state an action leaves was reached by an action, not by play -- the RNG
   in particular is where the shorter road left it.
   ===================================================================================================================== */
const BB_DBG = {
  MARK: 'BB_DBG',
  ROUND: 0x8609, PAL: 0x82D7, TILE: 0x83EC, UMB: 0xFECD, TENS: 0x9A0E,
  BOSS: 0x50, ROOM: 0x51, LAST: 81,
  PLAYER: [0xFD80, 0xFD8A],              // +4 count, +7 flags (bit 7 in play), +$5A status, +$5C lives, +$63 letters
  ENEMY: 0xFD94, ENEMIES: 7,             // the seven enemy slots ($92C0's walk)
  BUBBLE: 0xFED8, BUBBLES: 12,           // the twelve bubble slots: +7 flags, +8 the enemy held, +9 the class
  SETTLE: 0xB54B, LATCH: 0x8E3B, TIMER: 0x8DBD,
  HURRY_AT: 0x745C, HURRY_OFF: 0x9049, HURRY_ON: 0x904D, BARON: 0x01F4,
  PU: 0x9603, PU_X: 0x8CAE, FOOD: 0x9605, FOOD_X: 0x8CAF, LATCHES: 0x8CB0, CLOCK: 0x86CD, UMB_LOCK: 0x8A76,
  VALUES: 0x8649, HELD: 0xFDE1, TRIGGER: 0xFED5,
  BOSS_HP: 0x9F62, BORIS: 0x9250, ROOM_ON: 0xFED1, ROOM_CAP: 0x8F3A, RESET: 0x9160,
  FX: [[0xFECF, 'storm'], [0xFECE, 'flood'], [0xFED0, 'heart'], [0xFED2, 'no shots'], [0xFED1, 'potion']],
  SPEEDS: [0.25, 0.5, 1, 2, 4, 8], JUMP_TURBO: 4,
  WAIT: 3000,                            // frames an action waits for its moment before it is dropped, said so
  LETTERS: 'EXTEND',
};
/* the sixteen power-ups by their effect (SPEC "Power-ups -- the dispatch map", $8839); the item where SPEC confirms it */
const BB_DBG_PU = [
  ['rapid', 'rapid fire: a blow every 8 frames ($88EF)'],
  ['range', 'long range: bubbles travel 16 steps (the purple sweet, $88F4)'],
  ['range+rapid', 'long range and rapid fire (the red lamp, $88EC)'],
  ['giant \u25C6', 'a giant diamond falls at the round clear (the candy cane, $88F9)'],
  ['giant 50', 'a giant item falls at the round clear (the red cane, $88FD)'],
  ['giant 60', 'a giant item falls at the round clear ($88FD)'],
  ['umbrella', 'skips 3, 5 or 7 rounds (the umbrella, $88B1)'],
  ['flood', 'the water flood; corpses drop diamonds (the blue cross, $88C3)'],
  ['storm', 'the lightning storm; corpses drop diamonds (the yellow cross, $88D5)'],
  ['fire', 'fireballs instead of bubbles (the red cross, $88DC)'],
  ['heart', 'invincible for the round; touching an enemy kills it (the heart, $8859)'],
  ['no shots', 'the enemies cannot shoot for a while ($8883)'],
  ['potion', 'the room fills with items and the round advances by itself (the potion, $890D)'],
  ['bolt blow', 'lightning blow for both players (the blue bottle, $889C) -- and its bit is the COLLECT LOCK ($87E2): no item is taken after it until a death'],
  ['fast walk', 'fast walk, kept through deaths ($88A7)'],
  ['blow 500', 'every bubble blown scores 500 ($88B0)'],
];

const bbDebug = (() => {
  const D = BB_DBG;
  const st = {
    game: null, frozen: false, stepReq: 0, speed: 1, acc: 0, muted: false,
    target: null, fast: false, turbo: false, jumped: false,   // the jump armed, the clear's skip of the wait, the jump's turbo
    r1Mid: false,                                  // round 1 built from a round: the means' clock (advance)
    queue: [], log: [], error: null, jumps: 0, actions: 0, refused: 0, dropped: 0,
    god: [false, false], lives: [null, null], uiAt: 0, panel: null,
  };
  const hex = (v, n) => '$' + v.toString(16).toUpperCase().padStart(n || 4, '0');
  const say = (msg, kind) => {
    st.log.unshift({ f: st.game ? st.game.frame : 0, msg, kind: kind || 'ok' });
    if (st.log.length > 12) st.log.length = 12;
  };

  /* ---- the state ---- */
  const inPlay = g => !g.ctrl && !g.front && !g.overScreen;
  /* why an action may not land now -- null when it may (a frame boundary with nothing of the engine in flight) */
  function busy(g){
    if (g.ctrl) return 'the control select';
    if (g.front === 'title') return 'the title';
    if (g.front) return 'the title\u2019s release';
    if (g.overScreen) return 'the game-over screen';
    if (g.paused || g.spin) return 'the pause';
    if (g.roundSeq || g.advDefer || g.cdCut) return 'a round starting';
    if (g.extendPending) return 'the EXTEND cutscene';
    if (g.stormPending) return 'a storm tick';
    if (g.hurryPending) return 'the HURRY UP block';
    if (g.potionPending || g.perfectPending || g.revealPending || g.umb || g.umbHeld) return 'a power-up\u2019s sequence';
    if (g.joinPending) return 'the second player joining';
    if (g.mw || g.mwSeq || g.lz || g.lzRes) return 'a sound request\u2019s wait';
    /* NOT pTail (the cut pass's accesses past the interrupt, waited out next frame) nor skipIsr (an overrun's lost
       interrupt): timing only -- the pass's logic is done.  MEASURED: 328 of 600 frame boundaries of round 1's play
       carry a pTail, and no other flag here is ever set in plain play */
    if (g.heldWrites.length || g.emHalt || g.rvReads) return 'a block in flight';
    return null;
  }
  const playerOn = (g, p) => (g.ram[D.PLAYER[p] + 7] & 0x80) !== 0;
  function enemies(g){
    const ram = g.ram, n = { free: 0, held: 0, corpses: 0 };
    for (let i = 0; i < D.ENEMIES; i++){
      const s = D.ENEMY + 10 * i, f = ram[s + 7];
      if (!(f & 0x80)) continue;
      if (ram[s + 9] === 0xFF) n.corpses++;
      else if (f & 0x08) n.held++;
      else n.free++;
    }
    return n;
  }
  const timer = g => g.ram[D.TIMER] | (g.ram[D.TIMER + 1] << 8);
  const hurryAt = g => g.ram[D.HURRY_AT] | (g.ram[D.HURRY_AT + 1] << 8);
  /* the timer set to v or v + 1, whichever keeps its own parity: each interrupt's odd / even branch follows it */
  function setTimer(g, v){
    const t = timer(g), w = (v + ((v - t) & 1)) & 0xFFFF;
    g.ram[D.TIMER] = w & 0xFF; g.ram[D.TIMER + 1] = w >> 8;
    return w;
  }
  const bcd = (lo, hi) => { let v = 0; for (const b of [hi, lo]) v = v * 100 + (b >> 4) * 10 + (b & 15); return v; };
  const itemValue = (g, t) => 10 * bcd(g.ram[D.VALUES + 2 * t], g.ram[D.VALUES + 2 * t + 1]);   // on screen, x10

  /* the game's own routines, called between frames: their per-pass bookkeeping saved and put back */
  function corpse(g, slot){
    const eh = g.ehAt, bf = g.bfAt;
    g.ehAt = null; g.bfAt = null;
    try { g.corpseBirth(slot); } finally { g.ehAt = eh; g.bfAt = bf; }
  }
  function livesRedraw(g){
    const pT = g.pT;
    try { g.livesPanel(); } finally { g.pT = pT; }
  }

  /* ---- the actions: each returns 'done', 'wait' (try again next frame) or a refusal (a string) ---- */
  function killAll(g){
    const ram = g.ram;
    if (ram[D.SETTLE]) return 'wait';                  // the enemies are still dropping in ($AA72's settle window)
    let k = 0, b = 0, left = 0;
    for (let i = 0; i < D.ENEMIES; i++){
      const s = D.ENEMY + 10 * i, f = ram[s + 7];
      if (!(f & 0x80) || (f & 0x08)) continue;          // empty, or held in a bubble, or already a corpse
      if (ram[s + 6] < 0x10){ left++; continue; }       // above the playfield ($937F's gate): next frame
      corpse(g, s); k++;
    }
    for (let i = 0; i < D.BUBBLES; i++){
      const s = D.BUBBLE + 10 * i;
      if (!(ram[s + 7] & 0x80) || ram[s + 9] !== 1) continue;   // a bubble with an enemy inside: class 1
      ram[s + 3] = 10; ram[s + 7] |= 0x08; ram[s + 7] |= 0x02;  // $A0FF / $A102 / $A106 -- the storm's burst
      b++;
    }
    if (k || b) say('killed ' + k + ' enem' + (k === 1 ? 'y' : 'ies') + (b ? ', burst ' + b + ' bubble' + (b === 1 ? '' : 's') : ''));
    return left ? 'wait' : 'done';
  }
  function popAll(g){
    const ram = g.ram;
    for (let i = 0; i < D.BUBBLES; i++){                // $A0F5..$A10F, the storm's payload, all twelve
      const s = D.BUBBLE + 10 * i;
      ram[s + 3] = 10; ram[s + 7] |= 0x08; ram[s + 7] |= 0x02;
    }
    say('every bubble burst (the storm\u2019s payload)');
    return 'done';
  }
  function bossKill(g, hp){
    const ram = g.ram;
    if (ram[D.ROUND] !== D.BOSS) return 'only on round 80, the boss';
    if (ram[D.LATCH]) return 'the round is already cleared';
    ram[D.BOSS_HP] = hp;
    say(hp ? 'boss HP ' + hp + ' (one bolt hit kills)' : 'boss HP 0: his defeat follows');
    return 'done';
  }
  function clearRound(g){
    const ram = g.ram;
    if (ram[D.LATCH] || ram[D.ROOM_ON]) return 'done'; // cleared already, or the potion's room: skipWait does the rest
    if (ram[D.ROUND] === D.BOSS && ram[D.BOSS_HP]) bossKill(g, 0);
    return killAll(g);
  }
  /* the clear's skip of the wait: once the game has cleared ($8ECF's latch -- every corpse landed, the timer zeroed),
     the timer to the countdown's window */
  function skipWait(g){
    const ram = g.ram;
    if (!st.fast || busy(g)) return;
    if (ram[D.ROOM_ON]){
      /* the potion's room (and round 81's, whose potion is taken at once): its drain ($8F36) clears when the timer's
         high byte is EIGHT above the one captured at the take ($892C) -- "window reached, items left: cleared, no award" */
      const t = timer(g), w = setTimer(g, ((ram[D.ROOM_CAP] + 8) & 0xFF) << 8);
      say('the room\u2019s wait skipped (timer ' + hex(t) + ' -> ' + hex(w) + ', the drain\u2019s window)');
      st.fast = false;
      return;
    }
    if (!ram[D.LATCH]) return;
    if (timer(g) < 0x0175){
      const t = timer(g), w = setTimer(g, 0x0175);
      say('the clear\u2019s wait skipped (timer ' + hex(t) + ' -> ' + hex(w) + ')');
    }
    st.fast = false;
  }
  function slot(g, at, xat, latch, t, what){
    const ram = g.ram;
    if (ram[at] && ram[0xFED1]) return 'the slot holds an item and items do not age now ($FED1, the potion\u2019s room)';
    if (ram[at]){
      /* busy: emptied the round clear's way -- phase 3, the phase clock wrapped -- and the game's expiry erases it */
      if (!(ram[D.CLOCK] === 0xFF && (ram[at + 1] & 7) === 3)){
        ram[at + 1] = (ram[at + 1] & 0xF8) | 3; ram[D.CLOCK] = 0xFF;
      }
      return 'wait';
    }
    ram[D.LATCHES] |= latch;                            // $8A10 SET 0 / $89E2 SET 1: the round's own spawn spent
    ram[at] = (ram[xat] & 0xF0) | (t & 0x0F);           // $89FB LDI / $89FF AND 15 / OR C
    ram[at + 1] = (ram[at + 1] & 0xF8) | 1;             // a fresh item's phase (the build's $8C98)
    if (at === D.PU && t === 6) ram[D.UMB_LOCK] = 6;    // $8A45: an umbrella arms the lock
    say(what);
    return 'done';
  }
  function letter(g, p, i){
    if (!playerOn(g, p)) return 'player ' + (p + 1) + ' is not in play';
    const at = D.PLAYER[p] + 0x63;
    g.ram[at] |= 1 << i;                               // $B7FF OR C
    g.ram[D.TRIGGER] = 1;                              // $B808
    say('P' + (p + 1) + ' letter ' + D.LETTERS[i] + ' (mask ' + hex(g.ram[at], 2) + ')');
    return 'done';
  }
  function extend(g, p){
    if (!playerOn(g, p)) return 'player ' + (p + 1) + ' is not in play';
    g.ram[D.PLAYER[p] + 0x63] = 0x3F;
    g.ram[D.TRIGGER] = 1;
    say('P' + (p + 1) + ' EXTEND: all six letters');
    return 'done';
  }
  function addLife(g, p){
    if (!playerOn(g, p)) return 'player ' + (p + 1) + ' is not in play';
    const at = D.PLAYER[p] + 0x5C;
    if (g.ram[at] >= 99) return 'player ' + (p + 1) + ' has 99 spare lives';
    g.ram[at]++;
    if (st.lives[p] !== null) st.lives[p] = Math.max(st.lives[p], g.ram[at]);
    livesRedraw(g);
    say('P' + (p + 1) + ' +1 life (' + g.ram[at] + ' spare)');
    return 'done';
  }
  function hurry(g, baron){
    const ram = g.ram;
    if (ram[D.ROUND] === D.BOSS) return 'no HURRY UP on the boss round ($9037)';
    if (ram[D.RESET]) return 'wait';                   // a respawn's reset request ($9160): $915F zeroes the timer first
    if (ram[D.HURRY_OFF]) return 'the hurry is off this round ($9049: the round cleared, or a power-up)';
    if (!baron && ram[D.HURRY_ON]) return 'HURRY UP has been and gone this round';
    if (baron && (ram[D.BORIS + 7] & 0x80)) return 'Baron von Blubba is already out';
    const t = timer(g), w = setTimer(g, (hurryAt(g) + (baron ? D.BARON : 0) + 1) & 0xFFFF);
    say((baron ? 'Baron von Blubba' : 'HURRY UP') + ': timer ' + hex(t) + ' -> ' + hex(w) + ' (threshold ' + hex(hurryAt(g)) + ')');
    return 'done';
  }

  /* ---- the queue ---- */
  function ask(name, fn, opts){
    st.actions++;
    const a = { name, fn, at: st.game ? st.game.frame : 0, why: null, any: !!(opts && opts.any),
                advance: !!(opts && opts.advance) };       // an action whose end is an advance: spent by the next one
    st.queue.push(a);
    pump();
    return a.result || 'queued';
  }
  function pump(){
    const g = game;
    if (!g || st.error) return;
    const why = busy(g);
    for (let i = 0; i < st.queue.length; ){
      const a = st.queue[i];
      if (why && !a.any){ a.why = why; i++; continue; }
      if (g.frame - a.at > D.WAIT){ st.queue.splice(i, 1); st.dropped++; a.result = 'dropped'; say(a.name + ': dropped -- still waiting for ' + (a.why || '?') + ' after ' + D.WAIT + ' frames', 'bad'); continue; }
      let r;
      try { r = a.fn(g); } catch (e){ r = 'threw: ' + e.message; }
      if (r === 'wait'){ a.why = 'its moment'; i++; continue; }
      st.queue.splice(i, 1);
      a.result = r;
      if (r !== 'done'){ st.refused++; say(a.name + ': ' + r, 'bad'); }
    }
    skipWait(g);
  }

  /* ---- the holds, after each frame ---- */
  function holds(g){
    if (busy(g)) return;
    const ram = g.ram;
    for (let p = 0; p < 2; p++){
      if (!playerOn(g, p)) continue;
      const b = D.PLAYER[p];
      if (st.god[p] && !(ram[b + 0x5A] & 0x04)){ ram[b + 0x5A] |= 0x08; ram[b + 4] = 0x50; }
      if (st.lives[p] !== null && ram[b + 0x5C] < st.lives[p]){ ram[b + 0x5C] = st.lives[p]; livesRedraw(g); }
    }
  }

  /* ---- the jump: $97F8 with the round one short of the target ---- */
  function advance(g, core){
    st.fast = false;                                   // every advance ends a clear's skip of the wait
    for (let i = st.queue.length - 1; i >= 0; i--)    // ...and a clear or a jump still queued: this advance is the one asked
      if (st.queue[i].advance){ st.queue[i].result = 'done'; st.queue.splice(i, 1); }
    if (st.target === null) return core.call(g);
    const ram = g.ram, n = st.target, c = ram[D.ROUND];
    const d = n - c - 1;                               // the builds a straight run would have made in between
    ram[D.PAL] = (((ram[D.PAL] + d) % 15) + 15) % 15;
    ram[D.TILE] = (((ram[D.TILE] + d) % 5) + 5) % 5;
    ram[D.ROUND] = (n - 1) & 0xFF;
    ram[D.UMB] = 0;                                    // an umbrella's skip in progress ends here
    if (n < 10) ram[D.TENS] = 0x20;                    // $97C2's blank: rounds 1..9 never write the tens cell
    /* $9830's warp: advancing into 20, 40 or 60 with a player who has not died sends the game to 81.  A jump lands
       where it was asked: both players' bit 7 ("has died") held set across the advance, and put back after */
    /* ROUND 1 IS ONLY EVER BUILT FROM THE TITLE on the machine, and the engine's round-1 build clock (r1Clock) is a
       replay MEASURED on that path: the title's shut gates, a new game's HUD.  From a round it refuses -- a gate open
       at $97F8, or a score whose HUD awards run past its replay (MEASURED: from round 45, 'a stamp past the first
       award').  So a jump to round 1 from a round is built on the clock the engine keeps for a round with no measured
       program -- its means (buildClockFor's last arm): the same build, its writes landing on the means' frames */
    st.r1Mid = n === 1 && c !== 0;
    const warp = n === 20 || n === 40 || n === 60;
    const f = [ram[D.PLAYER[0] + 0x5A], ram[D.PLAYER[1] + 0x5A]];
    if (warp){ ram[D.PLAYER[0] + 0x5A] |= 0x80; ram[D.PLAYER[1] + 0x5A] |= 0x80; }
    st.target = null; st.jumps++; st.jumped = true;
    let r;
    try { r = core.call(g); }
    finally {
      if (warp) for (let p = 0; p < 2; p++){
        const a = D.PLAYER[p] + 0x5A;
        ram[a] = (ram[a] & 0x7F) | (f[p] & 0x80);
      }
    }
    say('round ' + (c || 'title') + ' \u2192 ' + ram[D.ROUND] + (n === ram[D.ROUND] ? '' : ' (asked ' + n + ')'));
    return r;
  }

  /* ---- the frame: the speed, the queue before each machine frame, the holds after ---- */
  const effSpeed = () => st.frozen ? 0 : (st.turbo && game && inPlay(game) ? Math.max(st.speed, D.JUMP_TURBO) : st.speed);
  function soundGate(){
    const want = effSpeed() !== 1 && !st.frozen;
    if (want && !st.muted && sound.ctx){ sound.on = false; st.muted = true; }
    else if (!want && st.muted){ sound.on = true; sound.next = null; st.muted = false; }
  }
  function frame(g, kb, step0){
    if (st.game !== g){                                // a new game (the page's boot, Alt+M): nothing carried over
      if (st.game) say('a new game (' + (g.m128 ? '128K' : '48K') + '): the queue and the jump cleared');
      st.game = g; st.queue.length = 0; st.target = null; st.fast = false; st.turbo = false; st.r1Mid = false;
      if (st.error){ st.error = null; st.frozen = false; }
    }
    if (st.error){ ui(); return; }
    let n;
    const s = effSpeed();
    if (st.frozen){ n = st.stepReq > 0 ? 1 : 0; if (n) st.stepReq--; }
    else if (s >= 1) n = s;
    else { st.acc += s; n = st.acc >= 1 ? 1 : 0; if (n) st.acc -= 1; }
    soundGate();
    if (!n) pump();
    for (let i = 0; i < n; i++){
      pump();
      try { step0.call(g, kb); }
      catch (e){
        st.error = e.message; st.frozen = true;
        say('THE ENGINE STOPPED: ' + e.message, 'bad');
        if (typeof console !== 'undefined') console.error(e);
        break;
      }
      holds(g);
    }
    if (st.turbo && st.jumped && !busy(g)){ st.turbo = false; st.jumped = false; }
    ui();
  }

  /* ---- the API: the panel's buttons and the console's hands ---- */
  const api = {
    MARK: D.MARK, state: st,
    busy: () => busy(game),
    enemies: () => enemies(game),
    jump(n){
      n = n | 0;
      if (n < 1 || n > D.LAST) return 'rounds are 1..' + D.LAST;
      st.target = n; st.fast = st.turbo = inPlay(game); st.jumped = false;
      say('jump to round ' + n + ' armed' + (st.fast ? '' : ': the next game starts there'));
      if (st.fast) return ask('jump to ' + n, clearRound, { advance: true });
      return 'armed';
    },
    cancel(){
      const q = st.queue.length, j = st.target;
      st.queue.length = 0; st.target = null; st.fast = false; st.turbo = false;
      say('cancelled' + (j !== null ? ' the jump to ' + j : '') + (q ? ' and ' + q + ' queued' : ''));
      return 'done';
    },
    clearRound(){ st.fast = true; return ask('clear the round', clearRound, { advance: true }); },
    killAll: () => ask('kill all enemies', killAll),
    popAll: () => ask('burst every bubble', popAll),
    bossHP: hp => ask('boss HP ' + hp, g => bossKill(g, hp | 0)),
    powerUp(t){
      t = t & 15;
      return ask('power-up ' + t, g => slot(g, D.PU, D.PU_X, 0x01, t, 'power-up ' + t + ': ' + BB_DBG_PU[t][0]));
    },
    food(t){
      t = t & 15;
      return ask('food ' + t, g => slot(g, D.FOOD, D.FOOD_X, 0x02, t, 'food item ' + t + ' (' + itemValue(g, t) + ')'));
    },
    letter: (i, p) => ask('letter ' + D.LETTERS[i & 7], g => letter(g, p | 0, i | 0)),
    extend: p => ask('EXTEND', g => extend(g, p | 0)),
    addLife: p => ask('+1 life', g => addLife(g, p | 0)),
    hurry: () => ask('HURRY UP', g => hurry(g, false)),
    baron: () => ask('Baron', g => hurry(g, true)),
    invincible(p, on){
      p = p | 0; st.god[p] = on === undefined ? !st.god[p] : !!on;
      if (st.god[p] && game && !busy(game)) holds(game);   // at once, not after the next frame
      say('P' + (p + 1) + ' invincible ' + (st.god[p] ? 'ON' : 'OFF (the respawn countdown runs out)'));
      return st.god[p];
    },
    infiniteLives(p, on){
      p = p | 0;
      const want = on === undefined ? st.lives[p] === null : !!on;
      st.lives[p] = want ? Math.max(1, game.ram[D.PLAYER[p] + 0x5C]) : null;
      say('P' + (p + 1) + ' infinite lives ' + (want ? 'ON (at ' + st.lives[p] + ')' : 'OFF'));
      return want;
    },
    freeze(on){ st.frozen = on === undefined ? !st.frozen : !!on; st.stepReq = 0; return st.frozen; },
    step(n){ st.frozen = true; st.stepReq += Math.max(1, n | 0); return st.stepReq; },
    speed(s){ if (D.SPEEDS.indexOf(+s) >= 0){ st.speed = +s; st.acc = 0; } return st.speed; },
    status(){
      const g = game, ram = g.ram, e = enemies(g), b = busy(g);
      const stage = g.ctrl ? 'control select' : g.front ? 'title' : g.overScreen ? 'game over' :
                    g.paused ? 'paused' : 'play';
      const pl = [0, 1].map(p => {
        const at = D.PLAYER[p];
        return { on: playerOn(g, p), lives: ram[at + 0x5C], letters: ram[at + 0x63], dying: !!(ram[at + 0x5A] & 0x04),
                 invulnerable: !!(ram[at + 0x5A] & 0x08), score: g.score(p ? BB_V.SCORE_P2 : BB_V.SCORE_P1) };
      });
      return {
        machine: g.m128 ? '128K' : '48K', stage, round: ram[D.ROUND], frame: g.frame, busy: b,
        players: pl, enemies: e, cleared: !!ram[D.LATCH], settle: ram[D.SETTLE],
        timer: timer(g), hurryAt: hurryAt(g), hurryOff: !!ram[D.HURRY_OFF], hurryFired: !!ram[D.HURRY_ON],
        baron: !!(ram[D.BORIS + 7] & 0x80),
        powerUp: ram[D.PU] ? ram[D.PU] & 15 : null, food: ram[D.FOOD] ? ram[D.FOOD] & 15 : null, held: ram[D.HELD],
        effects: D.FX.filter(([a]) => ram[a]).map(([, n]) => n)
                 .concat(ram[0xFDDA] & 0x20 ? ['fire'] : [], ram[0xFDDA] & 0x40 ? ['bolt'] : [],
                         ram[D.UMB] ? ['umbrella skip ' + ram[D.UMB]] : []),
        bossHP: ram[D.ROUND] === D.BOSS ? ram[D.BOSS_HP] : null,
        counters: { palette: ram[D.PAL], tile: ram[D.TILE] },
        debug: { frozen: st.frozen, speed: st.speed, target: st.target, fast: st.fast, queue: st.queue.map(a => a.name + (a.why ? ' (' + a.why + ')' : '')),
                 god: st.god.slice(), lives: st.lives.slice(), error: st.error },
      };
    },
    log: () => st.log.slice(),
    key(e){                                            // the debug page's own Alt keys
      if (!e.altKey) return false;
      const k = { KeyK: () => api.killAll(), KeyN: () => api.clearRound(), KeyX: () => api.freeze(),
                  KeyC: () => api.step(1), KeyI: () => api.invincible(0), KeyL: () => api.addLife(0) }[e.code];
      if (!k) return false;
      if (!e.repeat) k();
      return true;
    },
    frame, advance,
  };

  /* ---- the panel (a browser only: the headless rig has no createElement, and drives the API) ---- */
  function ui(){
    const P = st.panel;
    if (!P) return;
    const now = Date.now();
    if (now - st.uiAt < 120) return;
    st.uiAt = now;
    const s = api.status(), pr = (p, x) => s.players[p].on ? x : '\u2014';
    const lt = m => D.LETTERS.split('').map((c, i) => (m >> i) & 1 ? c : '\u00B7').join('');
    const L = [];
    L.push(s.machine + ' \u00B7 ' + s.stage + ' \u00B7 round ' + s.round + (s.round === D.BOSS ? ' (boss)' : s.round === D.ROOM ? ' (treasure room)' : '') + ' \u00B7 frame ' + s.frame);
    for (const p of [0, 1]){
      const q = s.players[p];
      L.push('P' + (p + 1) + ' ' + pr(p, 'lives ' + q.lives + ' \u00B7 score ' + q.score * 10 + ' \u00B7 ' + lt(q.letters) +
             (q.dying ? ' \u00B7 dying' : q.invulnerable ? ' \u00B7 invulnerable' : '')));
    }
    L.push('enemies ' + s.enemies.free + ' free, ' + s.enemies.held + ' in bubbles, ' + s.enemies.corpses + ' falling' +
           (s.cleared ? ' \u00B7 CLEARED' : '') + (s.settle ? ' \u00B7 settling ' + s.settle : ''));
    L.push('timer ' + s.timer + ' \u00B7 hurry at ' + s.hurryAt + (s.hurryOff ? ' (off)' : s.hurryFired ? ' (fired)' : '') +
           (s.baron ? ' \u00B7 BARON' : ''));
    L.push('power-up ' + (s.powerUp === null ? '\u2014' : s.powerUp + ' ' + BB_DBG_PU[s.powerUp][0]) + ' \u00B7 food ' +
           (s.food === null ? '\u2014' : s.food) + ' \u00B7 last taken ' + s.held + (s.effects.length ? ' \u00B7 ' + s.effects.join(', ') : ''));
    if (s.bossHP !== null) L.push('boss HP ' + s.bossHP);
    const d = s.debug;
    L.push((d.error ? 'ENGINE STOPPED' : d.frozen ? 'FROZEN' : 'running ' + d.speed + 'x') + (st.muted ? ' (muted)' : '') +
           (d.target !== null ? ' \u00B7 jump \u2192 ' + d.target : '') + (s.busy ? ' \u00B7 ' + s.busy : ''));
    if (d.queue.length) L.push('queued: ' + d.queue.join('; '));
    P.status.textContent = L.join('\n');
    P.log.textContent = st.log.map(x => x.f + '  ' + x.msg).join('\n');
    P.log.className = 'bbdbg-log' + (st.log.length && st.log[0].kind === 'bad' ? ' bbdbg-bad' : '');
    for (const b of P.toggles){
      const k = b.dataset.act, a = +b.dataset.arg;
      const on = k === 'freeze' ? d.frozen : k === 'speed' ? !d.frozen && d.speed === a : k === 'god' ? d.god[a] :
                 k === 'lives' ? d.lives[a] !== null : k === 'jump' ? d.target === a || (s.round === a && s.stage === 'play') :
                 k === 'letter' ? !!((s.players[+b.dataset.p].letters >> a) & 1) : false;
      b.classList.toggle('bbdbg-on', on);
    }
  }
  function build(){
    if (typeof document === 'undefined' || typeof document.createElement !== 'function' || !document.body) return;
    const css = document.createElement('style');
    css.textContent =
      '#bbdbg{position:fixed;top:48px;right:10px;width:330px;max-height:calc(100vh - 58px);overflow:auto;z-index:30;' +
      'background:var(--bg);color:var(--btn);border:1px solid var(--edge);border-radius:6px;' +
      'font:12px/1.35 system-ui,sans-serif;padding:8px 10px;box-shadow:0 2px 12px rgba(0,0,0,.35)}' +
      '#bbdbg.bbdbg-min .bbdbg-body{display:none}' +
      '#bbdbg h3{font:600 11px/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;margin:10px 0 5px;opacity:.8}' +
      '#bbdbg .bbdbg-top{display:flex;align-items:center;gap:8px}' +
      '#bbdbg .bbdbg-top b{font-size:13px;letter-spacing:.08em}' +
      '#bbdbg .bbdbg-top span{flex:1;opacity:.7;font-size:11px}' +
      '#bbdbg pre{margin:6px 0 0;white-space:pre-wrap;font:11px/1.4 ui-monospace,Consolas,monospace}' +
      '#bbdbg .bbdbg-row{display:flex;flex-wrap:wrap;gap:3px}' +
      '#bbdbg .bbdbg-grid{display:grid;grid-template-columns:repeat(9,1fr);gap:2px}' +
      '#bbdbg button{font:11px/1.2 system-ui,sans-serif;color:inherit;background:transparent;border:1px solid var(--edge);' +
      'border-radius:3px;padding:3px 5px;cursor:pointer;min-width:0}' +
      '#bbdbg button:hover{border-color:var(--btn)}' +
      '#bbdbg button.bbdbg-on{background:var(--btn);color:var(--bg);border-color:var(--btn)}' +
      '#bbdbg .bbdbg-grid button{padding:2px 0}' +
      '#bbdbg .bbdbg-log{opacity:.85;max-height:9em;overflow:auto}' +
      '#bbdbg .bbdbg-log.bbdbg-bad{color:#e5534b;opacity:1}' +
      '#bbdbg .bbdbg-note{opacity:.65;font-size:11px;margin-top:3px}';
    document.head.appendChild(css);
    const el = document.createElement('div');
    el.id = 'bbdbg';
    const btn = (act, arg, label, title, extra) =>
      '<button type="button" data-act="' + act + '" data-arg="' + arg + '"' + (extra || '') +
      (title ? ' title="' + title.replace(/"/g, '&quot;') + '"' : '') + '>' + label + '</button>';
    let rounds = '';
    for (let r = 1; r <= D.LAST; r++)
      rounds += btn('jump', r, r, r === D.BOSS ? 'round 80: the boss' : r === D.ROOM ? 'round 81: the treasure room' :
                    'jump to round ' + r);
    const letters = p => D.LETTERS.split('').map((c, i) => btn('letter', i, c, 'give P' + (p + 1) + ' the letter ' + c, ' data-p="' + p + '"')).join('') +
                         btn('extend', p, 'EXTEND!', 'all six letters: the NICE cutscene, a life and the next round');
    el.innerHTML =
      '<div class="bbdbg-top"><b>DEBUG</b><span>debug build \u2014 not the faithful page</span>' +
        btn('min', 0, '\u2013', 'hide / show the panel') + '</div>' +
      '<div class="bbdbg-body">' +
      '<pre class="bbdbg-status"></pre>' +
      '<h3>Speed</h3><div class="bbdbg-row">' + btn('freeze', 0, 'freeze', 'freeze / run (Alt+X)') +
        btn('step', 1, 'step', 'one frame (Alt+C)') +
        D.SPEEDS.map(s => btn('speed', s, s < 1 ? '\u00BC\u00BD'[s === 0.25 ? 0 : 1] + 'x' : s + 'x', 'speed ' + s + 'x')).join('') + '</div>' +
      '<h3>Round</h3><div class="bbdbg-grid">' + rounds + '</div>' +
      '<div class="bbdbg-row" style="margin-top:4px">' +
        btn('clear', 0, 'clear round', 'kill everything and skip the clear\u2019s wait: the game\u2019s own next round (Alt+N)') +
        btn('kill', 0, 'kill all enemies', 'corpses and fruit, the game\u2019s clear after (Alt+K)') +
        btn('pop', 0, 'burst bubbles', 'every bubble, as the storm\u2019s last ticks') +
        btn('cancel', 0, 'cancel', 'drop the jump and anything queued') + '</div>' +
      '<div class="bbdbg-note">A jump lands exactly on the round asked (the 20 / 40 / 60 treasure-room warp is held off); ' +
        'clear a round with \u201Cclear round\u201D to get the game\u2019s own next round, warp and all.</div>' +
      '<h3>Power-ups (the round\u2019s spawn point)</h3><div class="bbdbg-row">' +
        BB_DBG_PU.map((p, t) => btn('pu', t, t + ' ' + p[0], 'type ' + t + ': ' + p[1])).join('') + '</div>' +
      '<h3>Food items</h3><div class="bbdbg-row">' +
        Array.from({ length: 16 }, (_, t) => btn('food', t, String(t), 'food item ' + t)).join('') + '</div>' +
      '<h3>EXTEND</h3><div class="bbdbg-row">P1 ' + letters(0) + '</div>' +
        '<div class="bbdbg-row" style="margin-top:3px">P2 ' + letters(1) + '</div>' +
      '<h3>Players</h3><div class="bbdbg-row">' +
        btn('life', 0, 'P1 +1 life', 'Alt+L') + btn('lives', 0, 'P1 \u221E lives') + btn('god', 0, 'P1 invincible', 'Alt+I') + '</div>' +
        '<div class="bbdbg-row" style="margin-top:3px">' +
        btn('life', 1, 'P2 +1 life') + btn('lives', 1, 'P2 \u221E lives') + btn('god', 1, 'P2 invincible') + '</div>' +
      '<h3>Timer and boss</h3><div class="bbdbg-row">' + btn('hurry', 0, 'HURRY UP now') + btn('baron', 0, 'Baron now') +
        btn('boss', 1, 'boss HP 1', 'round 80: one bolt hit kills') + btn('boss', 0, 'kill boss', 'round 80: HP 0') + '</div>' +
      '<h3>Log</h3><pre class="bbdbg-log"></pre>' +
      '<div class="bbdbg-note">Alt+K kill all \u00B7 Alt+N clear round \u00B7 Alt+X freeze \u00B7 Alt+C step \u00B7 ' +
        'Alt+I invincible \u00B7 Alt+L +1 life.  Console: __PORT__.debug</div>' +
      '</div>';
    document.body.appendChild(el);
    /* the panel never takes the keyboard's focus: a focused button would swallow SPACE, a game key */
    el.addEventListener('mousedown', e => { if (e.target.closest('button')) e.preventDefault(); });
    el.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      const a = b.dataset.act, n = +b.dataset.arg;
      ({ min: () => el.classList.toggle('bbdbg-min'), freeze: () => api.freeze(), step: () => api.step(1),
         speed: () => { api.speed(n); api.freeze(false); }, jump: () => api.jump(n), clear: () => api.clearRound(),
         kill: () => api.killAll(), pop: () => api.popAll(), cancel: () => api.cancel(), pu: () => api.powerUp(n),
         food: () => api.food(n), letter: () => api.letter(n, +b.dataset.p), extend: () => api.extend(n),
         life: () => api.addLife(n), lives: () => api.infiniteLives(n), god: () => api.invincible(n),
         hurry: () => api.hurry(), baron: () => api.baron(), boss: () => api.bossHP(n) })[a]();
      b.blur(); st.uiAt = 0; ui();
    });
    if (window.innerWidth < 1200) el.classList.add('bbdbg-min');
    st.panel = { el, status: el.querySelector('.bbdbg-status'), log: el.querySelector('.bbdbg-log'),
                 toggles: Array.from(el.querySelectorAll('button[data-act="freeze"],button[data-act="speed"],' +
                   'button[data-act="god"],button[data-act="lives"],button[data-act="jump"],button[data-act="letter"]')) };
  }
  build();
  return api;
})();

/* the hooks: the page's game only (a test's own BB_Game is left alone) */
const bbDbgStep0 = BB_Game.prototype.step, bbDbgAdv0 = BB_Game.prototype.roundAdvanceCore,
      bbDbgClock0 = BB_Game.prototype.buildClockFor;
BB_Game.prototype.step = function (kb){
  if (this !== game) return bbDbgStep0.call(this, kb);
  bbDebug.frame(this, kb, bbDbgStep0);
};
BB_Game.prototype.roundAdvanceCore = function (){
  if (this !== game) return bbDbgAdv0.call(this);
  return bbDebug.advance(this, bbDbgAdv0);
};
/* a jump to round 1 from a round: the build's clock with no frame budget in sight -- buildClockFor's means */
BB_Game.prototype.buildClockFor = function (){
  if (this !== game || !bbDebug.state.r1Mid) return bbDbgClock0.call(this);
  bbDebug.state.r1Mid = false;
  const b = this.budget;
  this.budget = Infinity;
  try { return bbDbgClock0.call(this); } finally { this.budget = b; }
};
/* the debug page's Alt keys, ahead of the keyboard's listener (capture), so K, N, X, C, I and L are never pressed */
addEventListener('keydown', e => { if (bbDebug.key(e)){ e.preventDefault(); e.stopImmediatePropagation(); } }, true);
globalThis.__PORT__.debug = bbDebug;
