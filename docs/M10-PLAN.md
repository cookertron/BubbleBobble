# M10 -- the 128K branch's AY sound: what the machine does, and the plan

Written 2026-10-13 from the M10 recon: the owner's "ultracode: M10 recon", Workflow `m10-recon`, run
`wf_31c47c26-0ae`, 2026-10-12 23:57 .. 2026-10-13 01:30, four agents, 1.52M subagent tokens.  A read the engine
statically and wrote a Python model of it without ever running its code.  B built the project's first 128K harness
and captured the real engine.  C worked out what else the 128K branch changes.  D cross-checked all three against
the machine.  **Nothing in the port has changed.**  This is the plan for the owner to read before any code is written
(next.md's rule for M10).  The decisions that are the owner's are in section 3.

## 0. In one page

- **The engine is fully understood.**  It is small: a three-voice sequencer, 280 instructions plus 3,120 bytes of
  data, whose data are notes and raw AY register writes.  A's Python transliteration was written from the bytes
  alone.  It matches the real 128K machine **exactly**:
  - all eight sounds over 3,000 ticks from a fresh engine;
  - 511,270 ticks with real history: nine game scenes and five random request chains, 2,018 requests in all.
  
  There were 0 mismatches in any write, in its order, in the busy flag returned, or in the uncontended T.  The JS
  engine (M10.1) will be a transliteration of that model.
- **Eight sounds, and the engine plays only music.**
  - 1: the in-round theme.
  - 2: EXTEND.
  - 3: a short rising jingle (cold start, potion, boss defeat, after EXTEND).
  - 4: the HEART and the treasure room.
  - 5: the title, and game over.
  - 6: the boss theme.
  - 7: the game-start tune.
  - 0: the pause's mute.
  
  Every sound loops until the next request.  The engine plays NO effects, and every 48K beeper effect still sounds
  on a 128K, beside the AY.
- **The 128K version also plays differently, not just with music.**  At six places the game WAITS for the current
  tune to reach its end before it requests the next:
  - the cold start: 81 frames of black screen before the title;
  - round 1's start: 221 frames (4.4 s) in which the main loop, and so every enemy, stands still while the frame
    interrupt runs, so the player can already walk and the round's timers advance;
  - the treasure room: 81 frames;
  - EXTEND: 183 frames, so the cutscene runs about 3.7 s longer;
  - the boss defeat: 82 + 14 frames.
  
  The in-round theme runs at 2/3 speed (the engine skips one frame interrupt in three) and at full speed while
  HURRY UP is latched.  Every frame interrupt costs about 440..600 T more.
- **Recommendation: M10 is the game's own 128K branch, run on the port's 48K clock.**  The probe answers 128K, the
  three hooks stay live, and the engine runs from bank 1.  The 128K MACHINE's own clock and contention are DECLARED:
  each difference is within about 2%, and the net speed probably within about 1%.
  - Considered and rejected: "music only, over the 48K flow".  No machine plays that.  The game-start tune would be
    cut after about 68 frames and the cold-start jingle after one.
- **Three decisions are the owner's** (section 3): the page's default machine, how to switch machines, and the scope
  above.
- **Five increments, all solo** (section 4):
  - M10.0: the oracles;
  - M10.1: the engine;
  - M10.2: the branch;
  - M10.3: the page and the platform;
  - M10.4: the release docs.
  
  One Sonnet reviewer each for M10.2 (new blocking machinery in step()) and M10.3 (shared platform machinery), per
  the token-economy rule.

## 1. What the machine does -- MEASURED

The evidence is in the recon's scratch directories (gitignored, this machine only):

- `scratchpad/ay_static` (A: model.py, decode.txt, pred_0..7.json);
- `scratchpad/ay128` (B: h128.py, the 128K harness, its saved states and captures, direct_0..7.json);
- `scratchpad/branch128` (C: the pageshim among them);
- `scratchpad/ay_cross` (D: diff, lockstep, cadence, selfcheck_d).

The subagents could not write report files: the harness refuses them.  Their full structured reports, every claim
with its evidence and D's verdict on each, are in `scratchpad/m10_recon/` (A_static, B_ay128, C_branch128,
D_cross.json), with the workflow script.  M10.0 rebuilds every number below as a tracked tool and fixture.

### 1.1 The branch (C; confirmed by B and D)

- **The probe.**  On the 128K harness the probe $FAC3 counts BC = $0759 (the 48K counts $075E).  It answers A = $80,
  and the cold start keeps the three hooks ($8DC4 / $8E05 / $8E0A = $F3 / $0E / $21).
- **The 128K load differs from the 48K load in 14 bytes outside the display file:**
  - BANKM $5B5C = $10 (the 48K load has $00, image_tape.bin $1B);
  - $6000 = $10;
  - twelve system variables in $5C0A..$5CC8.
  
  $95F5 copies $5B5C into $9AE7, and the hooks page with ($9AE7)|1 = $11 and back with $10.  **Under M10 $9AE7 must
  be $10.**  The port's reset leaves 0 there, and with 0 a request returns A = 0, after which $8CD2's $9575 delay runs
  65,407 DJNZ.
- **$96B3..$96D8 (128K only):**
  - LDIR the engine, $E6A8..$F5BB on the tape, through the display file $4000..$4F13;
  - OUT ($7FFD),$11;
  - LDIR into bank 1 at $C350..$D263;
  - OUT ($7FFD),$10, then RET to $8CCA.
  
  The leg takes 203,984 T on the 128K (185,957 T on the 48K clock).  The copy through the display file is
  **invisible**: the bitmap there was zero and every affected attribute is $00, so 3,213 bytes change and none
  shows.  It stays until the CLS $97EB, 86 frames later.  There is no sprite rebuild (coldStart's comment at $96B0 says
  there is; it is wrong): bank 0's sprites are untouched and bank 1 holds only the engine.
- **The probe's 128K exit.**  $FAEF -> $FA3B is a trampoline to $FA67 LD A,$80 / RET (65 T against the 48K exit's
  17).  With the redefine cheat armed it falls into $FA40, the A+D+G spawn-record cheat, which is reachable ONLY on
  the 128K branch.  The port already models the trampoline's T and counts the cheat (probeEnd).
- **Nothing else in the game reads the branch.**  The three $C9 patches at $969A are the only differing bytes.

### 1.2 The engine (A; D found 0 mismatches)

- **Bank 1 layout:**
  - DATA $C350..$CF7F: 3,120 bytes, 7 sounds x 3 slot streams, each stream ending in $FF;
  - CODE $CF80..$D1E1: 280 instructions;
  - STATE words $D1E2..$D1ED;
  - the SOUND TABLE $D1EE..$D241: 7 x 12 bytes, the start and restart pointers of slots A, B and C;
  - $D242..$D263: unreachable.
  
  All the engine's state lives in 15 self-modified instruction operands and those six words, all zero at the copy.
- **Two entries, one caller each:** $CF80, the TICK (called from the ISR hook at $8DF4), and $D167, the REQUEST
  (called from $8E1D).  The code has no IN, DI, EI, HALT, CALL, RST, PUSH or POP, and never uses IX, IY or SP.  It
  has 26 OUT (C),A: 13 to $FFFD (register select) and 13 to $BFFD (data).  It never reads the AY and touches nothing
  outside its own bytes.
- **A tick runs three slots:** slot C first (the master, AY channel C, R4/R5), then A (R0/R1), then B (R2/R3).  A
  slot fetches only when its counter runs out:
  - `$03 (r v)+ $03`: raw AY writes (a write to R13 also sets the slot's envelope shape);
  - `$04`: toggles the slot's retrigger flag;
  - `$02 n` ... `$01`: one loop level;
  - `$FF`: END (acted on by the master only);
  - anything else: a NOTE [fine, coarse, d], where d = 0 means 256 ticks; with retrigger set, R13 := shape is written
    first.
  
  There is no software envelope, vibrato or arpeggio code: all of it is written out in the data.
- **Every sound loops.**  On the END tick all three slots reload from their restart pointers and the tick returns
  A = 1.  Every other tick returns A = 0.  Pass lengths in ticks:

  | Sound | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|
  | Ticks | 1,536 | 192 | 82 | 256 | 513 | 649 | 289 |
- **The request.**  For n = 1..7 it sets the pointers, clears the retrigger flags and sets the counters to 1.  It
  makes NO AY write and returns 1.  Request 0 writes R7 := $3F (every tone and noise off) and nothing else: the
  sequencer runs on, so outside the pause a 0 would mute until the current sound's pass restarts, up to a whole pass
  (D).  The game uses 0 only in the pause, whose unpause re-requests.
- **History matters in one byte.**  Slot B's shape operand $D13F becomes 1 forever once sound 1 or 6 has written
  R13 = 1.  Later retriggers then write R13 = 1 where a fresh engine writes 0.  Shapes 0 and 1 are the same AY
  envelope.
- **Registers.**  A sound's first tick writes R0..R5 and R7..R13 (13 to 16 writes).  R6 is written only by sound 6,
  its drums.  R14 and R15 are never written.
- **T, uncontended** (D: equal to the machine on 21,255 ticks):
  - idle tick 116;
  - a note 393 on slot A or B, 410 on the master; retrigger adds 58;
  - END tick 299, or 384;
  - the maximum, 2,853: sound 5's first tick (sound 6's worst is 2,781, at tick 137 of each pass);
  - request 428 (n = 1..7), 89 (n = 0).

### 1.3 The sound map (B and D measured)

A's table called sound 7 the title music; D refuted that: 7 is the game-start tune and the title is 5.

| Sound | What | Requested at |
|---|---|---|
| 0 | mute (R7 := $3F) | the pause $8FF3; the unpause $9006 re-requests the saved sound, which RESTARTS from its start |
| 1 | the in-round theme: 1,536 ticks, 46.1 s at the 2/3 cadence | round 1: $98F5 JP z,$8E05, after 7's pass.  Other rounds: $98FC JP nz,$8E0A, a 35-T no-op while 1 is current |
| 2 | EXTEND: 192 ticks | $94D5 (EXTEND complete); the boss defeat $8E95 (after 3) |
| 3 | a rising jingle: 82 ticks | the cold start $8CCD; the potion / level skip $891A; the boss defeat $8E77; $953C after EXTEND (after 2) |
| 4 | the HEART / treasure room: 256 ticks | the HEART $887D (power-up handler 10); the treasure room $8991 (after 3) |
| 5 | the title: 513 ticks | the cold start $8CD7 (after 3); GAME OVER $8CE4 (it plays on into the title) |
| 6 | the boss theme: 649 ticks, the only noise (drums) | round 80's banner tail $9901 |
| 7 | the game-start tune: 289 ticks | $97B4, when '1' or '2' is accepted |

No request is made at a death, at HURRY UP, or beside any beeper effect.

### 1.4 The waits: the 128K game blocks

$8E05 spins (LD C,($8E06) / DEC C / JR nz: 23 T a turn) until the busy byte, which holds the last tick's A, is 1.
That is, it waits until the CURRENT sound ends a pass, then falls into $8E0A to request its own A.  Every wait is
entered with interrupts on, so none hangs.  The main line is blocked while the ISRs and the engine run.  Measured on
the 128K harness; C's paging shim on the 48K clock gives the same frame counts:

| Site | Waits for | Frames |
|---|---|---|
| $8CD7, cold start | 3's pass | 81.  The title comes at $8CC3 + 85.0 frames (48K: + 1.12), and a '1' pressed at $8CC3 + 5 is lost |
| $98F5, round 1 only | 7's pass (289 ticks from $97B4) | 221.  The main loop starts at '1' + 294.1 frames (48K: + 68.2) |
| $8991, treasure room | 3's pass | 81 |
| $953C, after EXTEND | 2's pass | 183 |
| $8E8A, boss defeat | 3's pass (its own request is a no-op) | 82 |
| $8E95, boss defeat | 3's next pass end | 14 (depends on phase, 0..81) |

**Round 1's wait is gameplay.**  Both ISR gates are open, so for 4.4 s:
- the player walks (with RIGHT held, X goes 24 -> 124) and the bubble manager runs;
- the enemies, which belong to the main loop, stand still;
- the round timer $8DB6 and the hurry timer $8DBD advance 50 -> 271, so round 1's HURRY UP and item spawns come
  4.4 s sooner in play time.

**A wait counts TICKS, not frames.**  An interrupt lost to a DI window lengthens it (D: EXTEND lost 4, the potion 3).

### 1.5 The cadence

The hook runs at the end of EVERY frame interrupt ($8D8F CALL $8DC4), on both parities, whatever the gates.

- While ($FED4), the LAST REQUESTED sound, is 1, the engine ticks on two interrupts in three.  The counter $8DE0
  runs 2 -> 1 (tick), 1 -> 3 (skip), 3 -> 2 (tick).  It loads as 2, is global and is never reset.
- Even then it ticks every interrupt:
  - while the HURRY UP latch $904D is set (cleared at the round setup, at the respawn, and when Boris despawns); or
  - while the round's frame counter is >= 768 ($8DB7 >= 3) AND exactly seven enemies are alive ($FECA == 7, a
    literal CP 7 / JR z).
- Every other sound ticks on every interrupt.

D ran A's model of this gate against the machine over 14,149 ISRs: 0 mismatches.

### 1.6 What it costs

- **Per interrupt.**  The hook and tick together average 441..599 T on the 128K; on the 48K the RET costs the 27-T
  CALL / RET.  Ticked hooks run 291..4,289 T (p50 341, p90 978).
  - The hook's own part: 175 T (sound != 1); 199 (the hurry path); 253..289 (the theme's paths); 150 / 172 on a
    skipped frame.  Its two OUT ($7FFD) are I/O-contended.
  - On the 48K clock C measured +434 T per ISR (theme at 2/3) and +517 (full rate), with 0.82% / 0.98% fewer
    main-loop passes.  D did not re-measure these: M10.0 does.
- **A request.**
  - 35 T when the sound is already current (RET z).
  - 577 T when taken (805 contended); 263..299 T for request 0.
  - A taken request with interrupts on is a 512-T DI window ($8E10..$8E28), which loses the frame interrupt at 0.72%
    of phases.
- **Registers a taken request leaves:** A = $10, BC = $7FFD, DE and HL engine pointers, AF' = $11.  They are live at
  exactly two sites:
  - $8CD2's $9575 delay runs 3,967 DJNZ (48K: 768), 51,763 T against 10,033;
  - $8E98's $9573 delay runs about 44.9k T longer.
- **$8E0A ends EI / RET.**  The four requests made with interrupts off ($887D, $891A, $94D5, $9006) are each followed
  by their own EI, so only the acceptance point moves, by one instruction.  The pause still spins with interrupts
  off ($8FF6 DI follows its request), so nothing ticks while paused.
- **Where the AY writes fall in the frame:** 640..34,600 T after the frame starts on the 128K (in play the median is
  about 2,200 T; on the title about 660).  That is up to half a frame, 10 ms, after the frame's start.

### 1.7 The 128K machine itself (DECLARE)

| | 128K | 48K |
|---|---|---|
| Frame | 70,908 T, 50.02 Hz | 69,888 T, 50.08 Hz |
| CPU | 3.5469 MHz | 3.5 MHz |
| Interrupt length | 36 T | 32 T |
| Contention | from T 14,361, on 228-T lines | from T 14,335, on 224-T lines |

The faster CPU makes T-timed beeper loops about 1.34% sharper on the 128K.  Two more contention effects exist only
there:
- bank 1 is an odd bank, so it is contended during every tick and request;
- OUT to $FFFD / $BFFD is I/O-contended while bank 1 is paged.

Each difference is within about 2%; the net game speed is probably within about 1% (C, INFERRED).  ULA snow: with
I = $FC and contended bank 1 paged during ticks, 29% of ticks overlap the display; SkoolKit cannot show it.

### 1.8 Corrections to earlier docs

- SPEC "M6 sound", lines 5006-5008 (a pointer added on 2026-10-13; the full rewrite comes in M10.0):
  - 4 is also requested at $887D (the HEART);
  - sounds 1 and 6 are reached by tail jumps ($98F5 / $98FC / $9901), not CALLs;
  - $8CD7 is in the cold start, not a round start;
  - every $8E05 wait requests its A after it.
- TRAPS #150: play1p.pkl and play2p.pkl are not hung.  They are 128K-branch states inside round 1's wait for sound
  7, and with interrupts ON both reach $8E0A after 152 frames (a correction added on 2026-10-13).
- web/game.js coldStart's comment at $96B0: the 128K leg has no "sprite rebuild" (fixed when M10.2 replaces the throw).
- The orchestrator's scouting note "boot128's banks equal boot48's outside the display file" was wrong in 14 bytes
  (1.1).

## 2. What M10 is: the recommendation

**(A) RECOMMENDED: the 128K branch on the port's 48K clock.**  With M10 ON:
- the probe answers $80, and the 128K load's 14 bytes are laid down;
- the cold start takes its 128K leg, exactly, the invisible display writes included;
- the three hooks are live: the ISR's tick and cadence, every request site, every wait, the register effects and
  the DI windows;
- the engine is transliterated into JS and runs on its own bank-1 bytes;
- its AY writes are logged as [frame + t / 69,888, reg, val] and sounded beside the beeper.

This is EXACTLY a machine: the kit's 48K harness with a $7FFD paging port and an AY on $FFFD / $BFFD.  That is C's
paging shim, about 30 lines, which D re-ran.  So the layer can be gated frame for frame like everything else.  With
M10 OFF the page is today's page, byte for byte.  Declared: 1.7, the forced probe answer, and the AY's analogue
output (the platform's AyChip model).

**(B) Rejected: the tunes laid over the 48K flow, without the waits.**  No machine does this:
- sound 3 would be replaced by 5 one frame after the cold start;
- 7 would be replaced by 1 after about 68 frames;
- 2 would be replaced by 3 at once.

**(C) Rejected: the 128K machine's own clock.**  It means re-running the whole timing model (the owner stopped the
timing campaign on 2026-10-12) for differences of 1-2% that no player hears.

## 3. The owner's decisions

1. **Which machine does the page boot by default?**  Both are built and tested either way, and the flag's OFF is the
   48K, as rule 5 asks.
   - (a) The 128K: the music, with the 128K version's flow (round 1's frozen start, the longer cutscenes).
     Recommended, because the owner made the music part of done.
   - (b) The 48K: the faithful page as it is today, with the music one switch away.
2. **How to switch.**  The machine is chosen once per boot: the probe decides at the control select, and the cold
   start runs once.  So switching restarts the machine from its load.
   - Recommended: a key that reboots into the other machine.  Alt+M is suggested; the page already takes Alt+Enter.
     The choice is remembered the way the high score is, and the caption names the machine.
   - Or a setting only, such as a URL parameter.
3. **The scope.**  Option (A) above, the 128K branch as it is, waits and all, rather than the music alone.

M10.0 and M10.1 do not depend on these answers.  M10.2 needs answer 3, and M10.3 needs answers 1 and 2.

## 4. The increments

Each increment runs: oracle -> engine -> gates -> hand-tested mutants -> battery --affected -> docs -> commit.

### M10.0 -- the oracles (tools only, no engine change) [solo]

**DONE 2026-10-13** (M10.0a `dc20037` + kit `3e81ac1`, M10.0b `9b7945c`, M10.0c `8e491f2`, M10.0d the docs).  As built:
the paging shim is `Harness(paging=$10)`; the fixtures wait in `build/pending/` until their gates land (TRAPS #342); the
flow oracle's scenes are p1, p2, idle, skip, potion, heart, extend, boss, alive7 (SPEC "M10 -- the 128K branch" has the
results).  Its answers to section 5's questions are below.

- **tools/harness128.py.**  B's Harness128 promoted:
  - SkoolKit 10's CMIOSimulator / CCMIOSimulator over pagingtracer.Memory, built from build/boot128.z80;
  - key driving; logs of AY writes, $7FFD writes and speaker edges; an exact HALT skip; save / load.
  
  Its generic part goes upstream to the kit with selftest checks: frame length 70,908, the py and C engines
  identical, the HALT skip exact.  The game-specific logs (requests, ticks, waits) stay in the port's tools.
- **tools/harness.py.**  An opt-in paging shim, C's pageshim:
  - an OUT that decodes as $7FFD swaps $C000..$FFFF with the selected bank;
  - AY select and data writes are logged;
  - the tracer is re-bound after set_tracer (C24).
  
  It goes upstream too.
- **tools/ayengine.py -> build/ayengine_fixture.json.**  The DIRECT oracle, on a fresh bank 1:
  - each sound 0..7: the request's writes, then 3,000 ticks of [reg, val, pc, t], each tick's A and its
    uncontended T;
  - D's seeded random request chains: requests 0..7 at random ticks, mid-note and mid-loop.  These carry the history
    byte $D13F and request 0's long mute.
- **tools/ay128flow.py -> build/ay128flow_fixture.json.**  The FLOW oracle on the port's clock: the 48K harness plus
  the shim, contended.  Scenes:
  - the cold start;
  - the title: 3, the 81-frame wait, then 5;
  - the game start, 1P and 2P: 7, round 1's 221-frame wait with the ISR running, then 1;
  - play: the cadence (2 in 3, HURRY UP, the alive-7 rule);
  - the pause;
  - the potion: 3, the wait, 4;
  - the HEART: 4;
  - EXTEND: 2, the wait, 3;
  - round 80: 6; and the boss defeat: 3, the wait for 3, the wait for 2;
  - game over: 5;
  - a request landing in its own DI window.
  
  For every frame it records the AY rows [frame, t, reg, val], the requests, the waits, the busy byte, $8DE0, the
  hook's T, each ISR's T, and the pass marks the port's existing pass gates read.  It also answers D's top open
  question: the hook's cost per ISR on the 48K clock.
- **The port's own boot path.**  The flow oracle must start at the phase the PORT's skipProbe hand-over produces.  C
  found that at 5 of 16 phases on the 48K clock no interrupt lands in the $9575 delay.  The cold-start wait then
  never happens: sound 3 is never heard and the title comes 80 frames sooner.  On the 128K machine the phase is
  always one that waits (the probe's HALT pins it).  Find where the port's skip lands; if it lands in a no-wait phase,
  the skip must land where the probe would have.
- **docs:** SPEC's corrections (1.8) written out in full, a new SPEC section "M10 -- the 128K branch", port.json.

### M10.1 -- the engine in JS, not wired to anything [solo]

**DONE 2026-10-13.**  As built (SPEC "M10 -- the 128K branch", "The engine in JS"): `BB_AY`, `BB_Ay` and `bbAyBytes` in
web/game.js, a transliteration instruction by instruction, so each AY write's `dt` comes from the instructions' own T (the
model had only path sums); the fixture moved to build/ and registered as `ayengine`, the bytes shipped as `aybytes`
(build/ay_engine.json, tools/extract_ayengine.py); bb.test.js AE1..AE7.  All 13 streams exact on the first run.  The
ROM fetch is refused by undoing the whole tick (TRAPS #344), so the state matches the oracle's stop point.

- **web/game.js.**  The engine over its own 16K bank-1 array.  Its state lives in its own operand bytes, as on the
  machine: self-modified operands, not JS fields, so history carries over exactly as the bytes do.  It is a
  transliteration of A's model (the reference is scratchpad/ay_static/model.py):
  - request(n) and tick() return the writes in order, A and T;
  - the engine's 3,860 bytes ship as build/ay_engine.json (tape-derived JSON, like tape_bytes.json).
- **Gates:**
  - the fixture: every sound fresh for 3,000 ticks, and the chains; writes, their order, A and uncontended T;
  - the boundary: no write outside bank 1's state bytes;
  - a never-requested engine's ROM fetch at tick 256 is a counted refusal, not a throw (TRAPS #304).

### M10.2 -- the 128K branch on the 48K clock [solo; one Sonnet review: new blocking machinery in step()]

**M10.2a DONE 2026-10-13** (the cold start and the hand-over to `$970E`; SPEC "M10 -- the 128K branch", "The cold start and
the hand-over in the engine"): BB_Game's `m128` (default OFF), the 128K load's bytes and REPPER, the probe's `$80`, the
skip waiting for the probe's phase (`skipPhase`), `coldStart`'s 128K leg (no throw: the display writes, the engine over
bank 1), the cold start's T by phase (`tools/cold128.py` -> build/cold128_fixture.json, `bbColdT128`), and the hand-over
after `$8CCA` instruction by instruction with the game's interrupt and the sound hook (its non-theme path).  The flow
fixture moved to build/ and registered (`ay128flow`).  bb.test.js H1..H7: exact on the first run against p1, p2, idle and
the skip; the skip sweep (64 phases, its turns), the DI window (179 offsets) and the not-taken request.  The theme's cadence
and the hook in `isr()` are M10.2b's.

**M10.2b DONE 2026-10-14** (the sound hook in the game's interrupt; SPEC "M10 -- the 128K branch", "The sound hook in the
game's interrupt"): `isr()` under m128 runs `$8D8F CALL $8DC4` after its passes on its wall clock (`isrHook`: EPILOGUE's
first instruction, after the acceptance phase and the waits so far; the hook's T for the 48K's 27; its two `OUT ($7FFD)`s'
I/O cycles on the ISR's program), `soundHook` has the theme's cadence (`$8DE0`, the HURRY latch, the alive-7 rule; every
path's T from its instructions), the AY rows land in the frame the interrupt begins at the machine's T, `hand128Done`'s
late interrupt hooks in its own frame, and the front end's interrupts are accepted where its last instruction ends (it was
BB_ISR_ACCEPT's provisional 4: TRAPS #351).  The flow oracle gained `hooks` rows -- the hook's inputs where it reads them
(TRAPS #350) -- recaptured, every other record identical.  bb.test.js B1..B5: the title record for record from `$970E` to
request 7 (p1, the skip scene, the skip as it ships), soundHook over all 10,543 hooked interrupts of the nine scenes, the
hook inside play interrupts of the 48K's real load (odd, even, a skip: the split of `isrD` / `isrPlain`, TRAPS #352), OFF
never hooks, the late interrupt.  Exact on the first run but for a test's own arithmetic.  After '1' the title's 5 plays on
until M10.2c models the request sites.

**M10.2c DONE 2026-10-14** (the main line's requests and waits, part one; SPEC "M10 -- the 128K branch", "The requests and
waits on the main line"): `mwBegin` / `mwTail` / `mwRun` / `mwIns` / `mwRet` -- `$8E05` / `$8E0A` an instruction at a time on
step()'s ledger, the request's DI window on `diWindows` -- at `$97B4` (7), `$98F5` (round 1's wait, then 1), `$98FC` (1),
`$9901` (6) and `$8CE4` (5); the build replays plan each interrupt's hook (`hookPlan`).  bb.test.js C1..C8: p1 / p2 / skip /
idle free-running, every request, wait and mark the oracle's, every interrupt / hook / tick / OUT / AY write / pass to each
scene's pinned parting in play (the 48K port's own play timing past its verified window -- DECLARED, the M7 campaign
stopped); the DI window; every interrupts-on request of the oracle at its T; rounds 10 and 80.  Left for **M10.2c2**: the
sites with the interrupts off (`$887D`, `$891A`, `$94D5`, `$9006` -- the request's EI moves the acceptance), the waits
inside play blocks (`$8991` treasure room, `$953C` after EXTEND, `$8E8A` / `$8E95` boss defeat, the `$8E98` delay with the
request's registers).  Its gates can only be unit / structural (the request rows at the machine's T, the waits' tick counts):
the poked scenes' play before the sites is the 48K port's (C2's partings).

**M10.2c2 DONE 2026-10-14** (the sound calls in play; SPEC "M10 -- the 128K branch", "The sound calls in play"): the heart's
`$887D` request made at once inside the item pass (`heartReq`), the potion's and EXTEND's blocks held at each sound call on
their exact clock (`lzStopAt` / `lzHit` / `lzOn128`: `$891A`, `$8991`'s wait, `$94D5`, `$953C`'s wait), the interrupts-off
requests run whole with the caller's window carried to their RET (+ REM on RET z), and the boss defeat as a program on
step()'s ledger (`bossDeath128`: `$8E77`, `$8E8A`, the delays, `$8E95`, `$8E98`'s delay with A $10 / B $7F -- 45,069 T over
the 48K's).  The gates went further than "unit / structural": the potion is the machine's record for record (frames
838..929, every row), EXTEND the same but the lazy block's acceptance phases (the 48K's), the boss defeat's waits and
delays end in the machine's frames (its `$8E77` at the port's T, pinned).  The unpause's `$9006` moved to **M10.2d** with
the pause it pairs with.

**M10.2d DONE 2026-10-15** (the pause; SPEC "M10 -- the 128K branch", "The pause"): a new oracle, tools/pause128.py
(pausespin's runs on the M10 machine: 414 runs on six 128K worlds from the flow's p1 and boss scenes, natural and FORCED at
every edge of request 0's window and the unpause's request, and two whole-pause scenes on the real load) -- every edge the
machine's as the window rules predict.  In the engine the arm's 48K RET at `$8E0A` is, under m128, `$8FF3`'s request 0 on
the ledger (M10.2c's `mwEnter` / `mwRun`), the release is `spinRelease128` (`$9006`'s interrupts-off request carrying the
spin's window to its RET's end), the arm's interrupt keeps its acceptance phase under m128, a held frame re-bases the
windows, and the pause outside step() is refused.  bb.test.js Q1..Q6: all 414 runs replayed through spinStep exact; the
forced arm through step() at the machine's three phases; the scenes through step() the machine's to the arm and at the
release but pinned residuals of the 48K's pass clock -- one of them FOUND here: a pass with CAPS held runs 22 T more
(`$8D6A..$8D6F`), uncharged by the 48K's skeleton (TRAPS #357, DECLARED: the timing campaign is stopped).  M10.2 is done:
next **M10.3**, the page and the platform.

The branch sits behind an engine option: BB_Game's `m128`, default OFF, OFF in every test world.  It comes in parts,
each gated against ay128flow_fixture:

- **a. The cold start:**
  - the probe answers $80, with skipProbe or without;
  - the 128K load's bytes ($5B5C = $10 ...);
  - coldStart(M128): the leg $96B3..$96D8 (the display writes, the bank-1 copy, its T), and no $969A patch;
  - the hand-over's added work: request 3, the $9575 delay with A = $10 / B = $7F, the $8CD7 wait, request 5.
- **b. The ISR hook** at the end of every ISR, on the ISR's own program:
  - the cadence ($8DE0);
  - the two OUT ($7FFD) with their I/O contention;
  - the tick and its T, and the busy byte;
  - the AY rows, written to game.ay.log as [frame + t / 69,888, reg, val].
- **c. Every request site and every wait:**
  - requests: the $FED4 compare and store, RET z, the DI window that can lose an interrupt, the EI, and the register
    effects on the two delays;
  - waits: the 23-T spin on the frame clock, with the main line blocked while ISRs run (round 1's player walking);
    a wait counts ticks, so lost interrupts lengthen it.
- **d. The pause:** request 0's mute, the spin, the unpause's re-request and the restart.

**Gates:**
- the flow fixture, frame for frame: requests, waits, the busy byte, the cadence, the AY rows with their T, ISR T and
  pass marks;
- the boundary: OFF is byte-identical to the pre-M10 machine (the whole 64K and every log), and every existing gate
  runs OFF.

### M10.3 -- the page and the platform [solo; one Sonnet review: shared platform machinery]

**M10.3 DONE 2026-10-15** (the page and the platform; SPEC "M10 -- the 128K branch", "The page and the platform"): the page
boots the 128K (`BB_PAGE.m128`; OFF the 48K page as before) and Alt+M reboots into the other machine (`bbBoot()`, the page's
own boot, a new game from the tape's hand-over), the choice remembered like the high score (`saveMachine`, ADDED, default
ON) and named in the caption.  platform.js's new `'mix'` instrument renders the beeper and the AY into one stream on the
worklet and on the scheduled fallback, each AY write at its sample, the registers kept through every path that renders
nothing, `reset()` for a reboot, `info()` naming both chips.  The AY's level against the beeper's (`AY_MIX`) is PROVISIONAL:
the owner's listening test sets it.  Gated by kit.test.js "THE MIX" (11) and bb.test.js G0..G9 (the kit's suite against the page; fresh pages in
child processes for the default, the switch, a reload and a reboot after play; the 128K engine's logs through the mix
the one-shot render).  The Sonnet review's one finding fixed (a reboot left the speaker high: TRAPS #364).  Battery:
--affected 949 / 949, 8 MISSES closed by G9 (--match 12 / 12).  Next:
**the owner's listening test**, then **M10.4**, the release docs and the FULL battery.


- **web/platform.js** (game-agnostic; upstream to the kit with kit.test.js checks):
  - ONE output for both chips: the beeper and the AY mixed into the worklet stream.  Today the AY has only the
    scheduled path, the one that crackled on the owner-class laptop.
  - AY writes placed at their sub-frame sample, as fractional frames like the beeper's edges; otherwise they land up
    to 10 ms early or late (1.6).
  - `sound.info()` reports both chips.
- **web/template.html:**
  - the switch, per the decisions in section 3;
  - the AY log flushed to the bridge;
  - the caption names the machine;
  - `__PORT__` exports;
  - the remembered choice mutation-tested against the rig's real store (TRAPS #17).
- **The owner's listening test.**

### M10.4 -- the release docs [solo]

**M10.4 DONE 2026-10-15** (STATUS "M10.4"): the README's release pass -- both machines, a "Playing" section, the 128K
machine as a declared layer (1.7's clock against the 48K's, the forced probe answer, the AY model and `AY_MIX`, no ULA
snow), Alt+M, the scope rows the measurements corrected (81 round layouts and no ending sequence; no attract mode, one
high score), the slowdown departure rewritten as the timing model it became, the `LD A,R` substitute; STATUS's table and
"Left" refreshed; tools/mutants.py's subprocess output decoded as UTF-8.  The FULL battery 2026-10-15 13:54..14:33: LISTED 7,039 KILLED 7,035, **0 survivors, 0 dead anchors, 0 misses** (TIMEOUT 1 / BROKEN 3: the known M7.110 cursor guard, B9 x2, M7.69), 38.0 min on 20 workers.  M10 is
done but for `AY_MIX`, PROVISIONAL until the owner's listening test.

- README: the 128K machine as a declared layer (1.7, the forced probe answer, the AY output model) and its scope row.
- STATUS.
- The FULL battery, then commit.

Wrap-up item (d), the README pass, follows.

## 5. Risks and what is not yet measured

- **The skipProbe phase** (M10.0): does the port's skipped probe land where the cold-start wait happens?  ANSWERED
  (M10.0c `skip_sweep`): not always -- at 19 of 64 hand-over phases (27,300..46,956) the wait never happens.  The
  probe's own hand-over is pinned at phase 1,051, a waiting phase: under M10 the skip must hand over there.
- **The hook's cost on the 48K clock**: MEASURED (M10.0c): ~617 T a theme tick, 150..172 a skip, ~410..490 a
  full-rate tick -- ~464 T an ISR under the theme.
- **The 128K load's REPPER** (found in M10.0c): 2, not the 48K's 5 -- the front end's key repeat; M10.2a carries it.
- **The hook's T shifts every later pass of the ON path.**  So all of M10.2's gates come from the new fixture, none
  from the 48K ones; those stay for OFF.
- **Not exercised on the 128K yet** (D):
  - the storm and umbrella beepers;
  - a 2-player game, and the other control choices;
  - the A+D+G cheat;
  - rounds past 81, and the ending;
  - a request landing in its DI window.
  
  M10.0's flow oracle covers 2P and the DI window.  The rest is the same code on both branches: the hooks do not
  depend on the player.
- **The recon's HEART, potion, EXTEND and boss scenes were reached by declared pokes**, not by natural play.  The
  requests and waits they showed are the code's, but M10.0 should reach at least one of them naturally.
