# M7 -- the engine build (progress log)

The behavioural spec (M4/M5) and sound (M6) are done; M7 writes the actual JS
engine, faithfully, one gated increment at a time.  Rules (CLAUDE.md): the
built artifact is what is tested (`python tools/build.py` then
`node test/bb.test.js` + `node test/kit.test.js`); never import source into a
test; every rule transliterated from a MEASURED SPEC address; every behaviour
mutation-tested (break it, watch the named check fail, restore).

## Architecture (as built)

- **The world is a byte image.**  `web/game.js` `BB_Game.ram` is a 64K
  `Uint8Array`; variables, the entity table, the clean-platform shadow and the
  display file all live at the ORIGINAL machine addresses (docs/SPEC.md,
  tools/varmap.json).  `this.scr` is a `SpecScreen` whose `.m` is a **subarray
  view** of `ram[$4000..$5AFF]`, so the kit's `renderScreen` paints the world
  image with zero copies.
- **Assets** load into the mirror at their real addresses from `port.json`.
  Round geometry is shipped as decoded data (the clean shadow layer + colour),
  not rebuilt from the packed `$61A8` records (that format is undecoded and
  low-priority -- a declared simplification, SPEC "round system").
- **Render path** (measured at `$8216`): each frame the clean platform layer
  (rows 2-23) is restored from the shadow (`display = shadow + $A000`) and the
  attrs from the colour shadow; the HUD (rows 0-1) is left to its own writer;
  sprites are composited on top (later increment).
- **Wiring**: `web/template.html` instantiates `BB_Game`, the loop steps/draws
  it, `__PORT__ = { BB_Game, game, Demo, ... }`.  The kit `Demo` class stays
  defined so the platform self-test keeps running.

## Increments

- [x] **M7.0 -- FOUNDATION (2026-09-10).**  The byte image, the display-as-view,
  asset loading, the measured render path (shadow restore + colour attrs), and
  the `__PORT__` hook.  `test/bb.test.js` (19 checks) is the frame gate: the
  engine's rendered display is byte-identical to a harness-captured CLEAN
  round-1 frame (`build/render_round1.json`, extracted live from `round1_48`
  with entities zeroed).  Mutation-tested (break the shadow offset -> the gate
  fails at `$4040`, restore -> green).  kit.test 115/115, bb.test 19/19.
  NO game logic yet -- `step()` holds the static round.

- [x] **M7.2 -- the sprite blitter + entity draw pass, ALL sub-shifts (2026-09-10).**
  `web/gfx.js` `bbBlit16` composites a 16x16 masked sprite (`screen = (screen
  AND mask) OR data`, the exact `$A651` POP-blit); `drawEntities` (in
  `renderFrame`) composites each active `$FD80` slot after the clean-layer
  restore.  KEY FINDING: the game does NOT shift at draw time -- each sprite is
  **352 bytes = four PRE-SHIFTED copies** (`$A6F3` picks the block by X's even
  sub-position: s=0 @+0 [4 B/row], s=2 @+64, s=4 @+160, s=6 @+256 [6 B/row];
  sprite stride is `$160`, confirmed `$C260-$C100`).  This resolved the
  earlier "cross-row state" mystery -- identical-looking rows drew differently
  because their pre-shifted bytes differ.  Gate (`build/blit_fixture.json`, 4
  sprites at s=0/2/4/6, draw-only via `h.call($A3AD)`, full 352-byte sprites):
  byte-identical to the harness at every shift; mutation-tested (block-offset
  +1 fails, restore passes).  bb.test 20/20, kit.test 115/115.  NOTE for M7.1:
  `extract_sprites.py` currently grabs only the 64-byte s=0 block -- it must
  grab all `$160` bytes so shifted draws work in the shipped engine.

- [x] **M7.7a -- the SCORE subsystem (2026-09-10, out of plan order -- it is
  self-contained and gateable now).**  `web/game.js` `addScore(player)` /
  `award(player, amount)` transliterate `$80FA`: BCD `ADC`+`DAA` add of the
  pending amount (`$FFED`) to `score[player]` (`$FFE1 + 4*player`; player 1 =
  P1, 2 = P2), then the MSB-first high-score compare/copy and the amount
  clear.  Gate: a POINT TABLE FROM BOTH SIDES (`build/score_fixture.json`, 62
  rows: real round awards + arbitrary amounts to exercise every BCD nibble
  carry) -- the engine's result BYTES match the harness `$80FA` exactly.
  Byte-exact (a lenient decode hid bad nibbles at first -- fixed), and
  mutation-tested (both nibble carries + the high-score compare fail when
  broken).  bb.test 21/21.  TODO: the HUD DIGIT DRAW (`$816B`) is deferred to
  the HUD renderer (needs the substitute font, an M9 decision).

- [x] **M7.3 -- the per-frame dispatch skeleton (2026-09-10).**  `web/game.js`
  `isr()` transliterates the IM2 ISR `$8D72`: the two self-modifying 16-bit
  frame counters `$8DB5` (`$8DB6/7` master, `$8DBD/E` hurry timer, +1/frame),
  the frame-PARITY branch (parity = bit0 of `$8DBD`; odd -> entity DRAW pass
  gated on `$FEC4`, even -> BUBBLE pass gated on `$FEC5`), and the sound hook
  (`$8DC4` = RET on 48K).  `mainLoop()` carries the 21-routine chain
  `$8D25-$8D5E` (game-over gate `$FEC9`, pass counter `$FEC8`, then the CALL
  chain) as the transliteration MAP -- routines are STUBS except the ones
  already done; `step()` = `isr()` once + `BB_PASSES` chain passes.  The pass
  COUNT is spend(T)-driven (M3 costs) and NOT yet wired -- a placeholder runs,
  which affects logic RATE only, not the frame structure.  Gate
  (`build/isr_fixture.json`): the ISR reproduces the harness `$8DB6/7`/`$8DBD/E`
  + parity sequence over 30 frames AND runs the DRAW pass exactly on the odd
  frames (detected by a shadow-restore probe, so the ENGINE's branch is tested,
  not the test's own parity); step() advances the ISR once/frame.
  Mutation-tested (counter +2, parity `&2` both fail; restore -> green).
  bb.test 24/24, kit.test 115/115.

- [x] **M7.3b -- wire spend(T), the frame-timing model (2026-09-10).**
  `step()` now runs the main loop as a spend(T) BUDGET LOOP: after the ISR it
  spends `BB_PASS_T` per main-loop pass until `FRAME_T` (69888) is reached, so
  the per-frame pass COUNT emerges from the timing rather than a `BB_PASSES`
  placeholder.  Gate `build/timing_fixture.json` (MEASURED on `round1_48` via
  the game's own `$FEC8` pass counter + a `$8D72`->SP-return ISR bracket):
    * ODD frames run an INVARIANT **11** passes (harness 24/24);
    * EVEN frames run a state-dependent **5-7** (mode **7**);
    * the ISR is CHEAP on both parities (**1481 T** odd / **1851 T** even -- it
      only advances the counters); the expensive entity draw (~24500 T) is a
      MAIN-LOOP event on EVEN frames, which is why even frames complete fewer
      passes.
  The engine reproduces the odd invariant (11) exactly and the even MODE (7);
  the render (clean-layer restore) runs on the harness-measured draw parity
  (EVEN), verified by a scribble-restore probe -- not by the test's assumption.
  Constants `PASS_T=6219 = (FRAME_T-ISR_ODD)/11` and `DRAW_T=24504 =
  (FRAME_T-ISR_EVEN)-7*PASS_T` are DERIVED from the measured budgets and are
  PLACEHOLDERS: as each chain routine is transliterated it will `spend()` its
  own measured cost and the even-frame variance (5-7) will emerge faithfully.
  Mutation-tested (PASS_T, DRAW_T, and the draw parity each fail their named
  checks; restore -> green).  bb.test 30/30, kit.test 115/115, selftest 34/34.

  **CORRECTION logged.**  The M7.3 draft assumed (from an early SPEC note) that
  the ISR `$8D72` was the renderer and drew entities on ODD frames, with
  `BB_ISR_DRAW=27490`.  Direct measurement refuted all three: the ISR is
  ~1500-1850 T (149/163 instrs, pure counter bookkeeping), the entity draw is a
  MAIN-LOOP event, and it runs on EVEN frames.  The old M7.3 "draw pass runs on
  odd frames" check tested the engine against its OWN assumption (circular); it
  is replaced by (a) an ISR-does-not-render check and (b) the M7.3b draw-parity
  check keyed to the measured fixture.  (House rule 1: the simulator is right.)

  **AUDIT 2026-09-10 (re-verification pass after a model switch) -- one
  attribution error in the paragraph above, corrected; no engine-behaviour
  bug.**  The M7.3b write-up said the ISR is "pure counter bookkeeping" and
  named the ~24500 T even-frame work "the entity draw `$A3AD`".  Direct
  measurement (PC hits on `$A3AD`, display-file writes per parity, `$A3AD`
  disassembly) shows: `$A3AD` runs on ODD frames, INSIDE the ISR, costing 1180
  of its 1481 T -- it saves SP, does `RES 5` on nine entity `+7` flag bytes
  (the `$FD87` C1/E1 toggle) and a light ~19-byte draw; `$B62C` is the even
  ISR's idle bubble pass.  The HEAVY composite is a DIFFERENT routine: ~250-270
  display writes per EVEN frame via the `$A651`/`$A655` masked blitter, a
  main-loop event.  So the original SPEC's "odd -> `$A3AD` in the ISR" was
  right and its "~27k T" cost was wrong; my correction got the cost, the
  parity of the heavy render and the main-loop location right but hung the
  wrong name on it.  What this changes: labels in `game.js`, this log and the
  memory; `draw_parity=0` in `build/timing_fixture.json` is now DIRECTLY
  measured (it had been inferred from pass counts and marked MEASURED
  prematurely).  What it does not change: the engine's timing (11/7) and its
  render-on-even are measured-correct.  UNMODELLED (logged): the odd ISR's
  `RES 5` flag clears and light draw, and whatever SETS bit5 on even frames
  -- untested by any current gate; they land with the per-entity erase.
  The same audit also confirmed the M7.4b jump-trigger assumption: at `$AD00`
  register `C == $FD88` exactly (`$00`/`$00` idle, `$02`/`$02` on the jump
  edge), and `$AD00` runs every even tick while grounded and is skipped
  while airborne -- the transliteration is exact.

- [x] **M7.4a -- the player, flat-ground WALK (2026-09-10).**  `playerWalk()`
  transliterates the walk-move `$AE40-$AE74`: read the direction bitmask's LOW
  nibble (`$FD88 & $0C` -- the `$ADAA AND $0C` test, bit2 RIGHT / bit3 LEFT),
  move the active player +-2 px (`$AE68 ADD A,2`), clamp X to `<= $E0` (224,
  the right edge, `$AE6D CP $E0`), and set the erase-backup `$FD83` to the
  pre-move X.  MEASURED STRUCTURE (scratchpad walk/walkwrite/walkcap): the move
  is committed ONCE PER EVEN FRAME -- X (`$FD85`) is written on par=0 only, by
  `$AE6A`+`$AB11`; odd frames do not move the player -- so `updatePlayers()`
  runs from the even-frame work in `step()` (the same 25 Hz beat as the draw),
  NOT per main-loop pass.  Normal walk = 2 px / 2 frames = 1 px/frame = 50 px/s
  (confirms the M3 figure); fast-walk (`$FD87` bit2) would move every frame.
  Gate (`build/walk_fixture.json`): fed the harness's OWN per-frame direction
  from a hold-RIGHT script on `round1_48`, the engine's player X/Y and frame
  parity match the harness FRAME FOR FRAME over 216 frames (open ground: 24 ->
  224, the `$E0` clamp reached at frame 205; no platform probe fires, so the
  move + clamp are isolated).  The input DECODE (keys -> `$FD88`) is the
  separate M7.8 layer.  Mutation-tested (move +3, clamp `$FF`, and moving every
  pass instead of once/even-frame each fail their named check; restore green).
  bb.test 33/33, kit.test 115/115, selftest 34/34.

  DECODED, DECLARED for M7.4b (next): the platform-collision FOOT PROBE `$AED1`
  -- read the COLOUR shadow at `$F800 + (Y+15 >> 3)*32 + (X >> 3)`, bit5 (`$20`)
  = solid; `$AE40` probes the foot cell ahead (and one char-row up) and blocks
  the move if solid.  Also the LEFT lower clamp and JUMP/FALL/LAND (the `$B57D`
  24-byte arc table indexed by the jump-phase `$FD89`, phases spilling into
  `$B595`; gravity +2/tick `$AD5A`; jump start `$AD08`).

- [x] **M7.4b -- the player, JUMP / FALL / LAND (2026-09-10).**  `playerJumpFall()`
  + `updatePlayer()` transliterate the jump machine (`$AD00` trigger, `$AD65`
  arc, `$AD51` free-fall/land).  On the EVEN tick: a grounded player jumps on
  the RISING EDGE (`$FD88` bit1 set AND bit5 clear -> phase 1, no move that
  tick; held does NOT re-trigger); an airborne player advances the arc
  `Y += $B57D[phase-1]` then `phase++` (move-then-increment, clamp 33 -> `$FF`),
  and on the descent (dy>0) if the projected feet (`Y+dy+15`) enter a solid
  cell it switches to FREE-FALL (`phase=$FF`, gravity +2), then snaps
  `Y = (feet & $F8) - 16` onto the platform and lands (`phase=0`).  Solidity is
  the `$AED1` foot probe reading the COLOUR shadow `$F800` bit5 -- the engine's
  `$F800` == the harness's (VERIFIED equal), so landings reproduce.  Arc table
  + the `$B595` spill are shipped as MEASURED constants (`BB_ARC`/`BB_ARC_SPILL`).
  Gate (`build/jump_fixture.json`, hold-JUMP on `round1_48`): the engine's Y AND
  the jump-phase byte match the harness FRAME FOR FRAME over 64 frames -- rise
  168->127 (apex, phase 15), flat apex (phases 16-19), descent, and the
  free-fall landing onto the col-3 row-19 ledge at y=136 (round 1 col 3 has
  solid rows 15/19/23, so a jump-in-place lands on a HIGHER ledge -- MEASURED,
  not a bug).  Mutation-tested (arc value, floor-probe bit, landing snap, and
  the trigger edge guard each fail their named check; restore -> green).
  bb.test 36/36, kit.test 115/115, selftest 34/34.

- [x] **M7.4c -- the horizontal-collision path `$ADAA` (walk both ways +
  collision + in-air steering) (2026-09-10).**  `playerMoveH()` + `hBlocked()`
  transliterate the FULLY DECODED `$ADAA`: read the dir low nibble (bit2 RIGHT
  / bit3 LEFT; neither or both -> no move), step 2, and probe the platform
  layer ONLY when the step crosses a char-cell boundary (RIGHT `(X+15)&$F8 !=
  (X+17)&$F8`; LEFT `X&7 < 2`); within a cell the move is free.  On a crossing
  the target-edge foot cell is probed in the `$F800` colour shadow (bit5), with
  a one-cell vs two-cell (foot +- one char-row) choice by the jump phase and
  `Y&7` (`$ADCB-$AE02`).  Commit: RIGHT `X+=2` clamp `<= $E0`, LEFT `X-=2` clamp
  `>= $10`.  `playerMoveH` now runs on BOTH grounded and airborne ticks (the
  jump arc and the horizontal move are separate routines driven together), so
  IN-AIR STEERING works.  Gates: `leftwall` (LEFT clamps at the `$10` border,
  30f), `airsteer` (JUMP+RIGHT: X's phase-gated probe pause at phases 9-10 +
  the Y arc, 60f) -- both frame-for-frame vs the harness, and the M7.4a/b walk
  + jump gates still pass.  Mutation-tested: turning the probe off (`$20` ->
  `$00`) breaks `airsteer` (the pause vanishes) -- the CORE collision probe is
  gated.  bb.test 40/40, kit.test 115/115, selftest 34/34.

  TWO FINDINGS logged this increment:
  * The NAIVE in-air model ("X +2 every airborne tick") is WRONG -- X pauses at
    jump phases 9-10 because the `$ADAA` probe blocks the boundary-crossing
    step against a side platform; the faithful `$ADAA` reproduces it exactly.
  * "walk into a wall at x=64" was a MISREAD -- driving LEFT ~217 frames the
    player DIES (`$FDDA` bit2 set, sprite -> `$C6C0`, anim `$50` countdown) and
    the death routine `$AB57` snaps `X &= $F8` (-> 64).  Round 1's bottom is
    OPEN (only the `$10`/`$E0` borders block horizontally).  The differential
    caught it (engine 66 vs harness 64).  (Death-snap `$AB57` + the dying flag
    are noted for the death/respawn increment.)

  COVERAGE NOTE (honest): `airsteer` gates the probe's `f||u` (two-cell) path;
  the LEFT `$10` clamp and the ascending-`Y&7==0` `f&&u` sub-branch are faithful
  transliterations of measured instructions but are NOT independently reachable
  in round 1 (the border wall blocks before the clamp; the `f&&u` branch needs
  a boundary cross while ascending at `Y&7==0` against a wall) -- so mutating
  them alone does not fail a round-1 gate.  Left for a round with interior
  bottom walls / a targeted scenario.

  STILL OUT (M7.4d): fall-off-edge when walking off a ledge (the grounded floor
  probe -> `$FF`), blow, death/respawn, 2P.

- [x] **M7.4d-i -- FALL-OFF-EDGE: the floor tick, the physics dispatch, and the
  free-fall cadence (2026-09-10).**  Decoding the physics DISPATCH `$ACEB-$AD11`
  restructured the player tick to the machine's own shape (`updatePlayer`):
    * phase `$FF` FREE-FALL -> `$AD11`: the horizontal move ONLY when the
      cadence counter `$AA65` reads 1, then the `$AD18` floor tick;
    * phase 1-32 ARC -> `$AD65`: horizontal every tick, then the arc;
    * phase 0 GROUNDED -> `$ACFA`: horizontal every tick, THEN the `$AD00` jump
      edge (RET), else the `$AD18` floor tick.
  `playerFloorTick` = `$AD18-$AD51`, ONE routine for the grounded check and
  free-fall landing: even-align Y (`$AD1E`), probe the floor under the sprite's
  FULL WIDTH at row `(Y+16)>>3` (`solidBelow`: cells `X>>3`, `+1`, and `+2`
  when `X&6 != 0` -- `$AE89-$AE99`), solid -> phase 0 with Y kept, else phase
  `$FF` and `Y += 2` the same tick.  The arc's descent test (`$AD90`) uses the
  same full-width probe under the projected feet (`Y+16+dy`).  `tickCadence`
  = `$AA60-$AA6B`: `INC ($FEC6)` then the SELF-MODIFYING operand of `LD A,nn`
  at `$AA64` (the byte `$AA65`) decrements, reloading to 4 at zero -- it
  cycles 4,3,2,1 once per EVEN tick BEFORE the physics, and the free-fall
  horizontal move fires only on the tick it reads 1 (every 4th tick; MEASURED
  f67/75/83/91).  Image value 3, seeded in `reset()`.
  Gates (frame-for-frame vs the harness): `fall` (jump onto the row-19
  ledge, walk RIGHT off its end at x=32, throttled free-fall with steering,
  land on row 23 at y=168, keep walking -- 130f) and `fallleft` (jump onto
  the ledge's right half, walk LEFT: the sprite OVERHANGS and drops only when
  no spanned cell has floor, at x=40 -- 170f).  All earlier player gates still
  pass.  Mutation-tested: cadence phase (`==2`) breaks fall AND airsteer;
  period (reload 3) and a late landing break fall; the LEFT-EDGE-ONLY probe
  (the M7.4c coverage gap) now breaks `fallleft` (engine drops at x=48, the
  harness stays up).  bb.test 45/45, kit.test 115/115, selftest 34/34.

  THREE CORRECTIONS to earlier understanding, all forced by the differential:
    1. The M7.4b landing "snap" `Y=(feet&$F8)-16` was a COINCIDENCE: the real
       landing is `$AD18`'s even-align + "floor below -> phase 0, Y kept";
       both give 136 there, they differ elsewhere.  Replaced.
    2. The grounded order was move-THEN-trigger (`$ACFA` -> `$AD00`), not
       trigger-then-move; the old order passed only because the probe cell
       happened to be empty.  Fixed.
    3. A free-fall is NOT a clean +2/tick horizontally: the `$AA65` cadence
       throttles it to every 4th tick (the first divergence, f65).
  Also learned: round-1 enemies roam onto the ledges within ~100-170 frames
  and KILL the player (`$FDDA` bit2, sprite `$C6C0`/`$D300`), which
  contaminated two attempted oracles; `fallleft` is captured with the heart
  flag `$FED0=1` poked (contact then kills the enemy) -- verified it leaves
  the walk rate (2 px/even-tick) and fast-walk (bit2=0) untouched, recorded
  in the fixture.  UNMODELLED: the `$AD5D CP $BF` bottom-of-screen wrap on the
  +2 step, and `$FEC6`'s readers.

  STILL OUT (M7.4d): blow, death/respawn, 2P.

- [x] **M7.4d-ii -- BLOW: the player action, the spawn, and the empty bubble's
  travel/rise schedule (2026-09-10).**  `playerInput` now carries FACING (`+7`
  bit0 from the L/R bits, LEFT first -- `$AC0E-$AC34`) and the BLOW CADENCE
  (`$ACA5-$ACE2`: `+$60` running -> `(+1) & +$5F`, the 16-frame interval; else
  the rising edge of dir **bit0** -> 1.  BLOW is bit0, not "down" -- varmap
  corrected).  `playerBlow` = `$BD37` (cadence == 1, not dying, debounce
  clear; first free pool slot; the `$BDC1` spawn fields; SET the debounce),
  called from `bubbleEvenPass` because the machine calls it from the even
  ISR (`$B62C -> $BD2C -> $BD37`, 2/even frame, T%FR ~420, ret `$8D8F`).
  THE MANAGER IS SPLIT BY SLOT ACROSS PARITIES [**WRONG -- see M7.5-iv(b) above:
  a fixed-phase sampling artefact, TRAPS #34**] (exact per-frame PC counts +
  per-slot write-watches with 1, 2 and 3 bubbles): `bubbleEvenPass` = the
  blow checks then SLOT 0 only (travelling: the `$BE07` step; risen: the
  `$B836` drift move); `bubbleOddPass` (in `isr()`, the `$A3AD` pass, gated
  `$FEC4`) = slot 0's TICK only (cap test -> `$BEE8` transition, then `+4++`)
  and SLOTS 1-11's full body (step, cap test, tick / drift move).  The rise
  is the `$B8DB` drift table indexed by the colour-shadow attribute's
  BRIGHT/FLASH bits at the bubble's cell (open air = (0,-1); the per-round
  wind lives in those bits).  Seeds in `reset()`: `$FDDE/$FDDF` (P2
  `$FDE8/9`) = 8/7, `$FEC5` = 1, `$FEC4` = `$14`.
  Gates (`build/blow_fixture.json`, three scenarios, frame-for-frame:
  `$FDE0`, the debounce bit, facing, player X/Y, and slots 0-1's flags, X/Y
  and travelling phase): `blow` (hold: spawn, 8 steps of +8, rise, 60f),
  `blow2` (re-blow after the interval -> slot 1, its odd-frame schedule,
  transition and first rise steps; compared to f41, where the two bubbles
  overlap at x=88 and bubble-bubble contact `$B8E5` freezes both -- M7.5,
  declared in the fixture), `blowleft` (walk right, face left, blow: -8
  steps into open air, 129f).  Mutation-tested: cadence mask, edge guard,
  facing, cap-before-tick order, debounce clear at the transition, the
  slot-0/1-11 split (even pass servicing all slots breaks blow2), the
  slot-0 tick, and the drift table each fail a named check.
  bb.test 50/50, kit.test 115/115, selftest 34/34.

  FINDINGS: (1) a naive "manager runs every frame on parity" model was wrong
  twice over -- the first bubble happened to land on the phase that made it
  look right; the 2nd bubble exposed it.  (2) TRAPS #29: `run_frames(1)`
  overshoot ACCUMULATES; after ~85 calls the next frame's early-ISR bubble
  tick leaked into the window (parity did not, since the counters are
  incremented late in the ISR) -- a fixture and a write-watch disagreed by
  one frame; the game is deterministic (two runs identical); fixed by
  capturing against absolute-T boundaries.  (3) The intra-frame ordering:
  the `$FDE0` edge is main-loop (T%FR ~20356), the spawn is the NEXT even
  ISR; the capture window straddles them so per-window observables put
  them in the same frame -- the engine runs the even pass after the player
  update to match; a blow-while-walking gate would pin whether the spawn
  reads the pre- or post-move X.
  UNMODELLED (M7.5): the risen ageing (+4/+2 via the `$B657` global toggle)
  and timeout pop, wall bounce `$BEAF`, capture `$BE5B`, bubble-bubble
  contact `$B8E5`, steal-oldest when the pool is full, fire-mode fireball,
  bubble DRAWING (`$C780` is runtime-built), the blow click (M7.9), the +50
  bonus; also the even ISR's extra T with bubbles active (timing is idle).

  STILL OUT (M7.4d): death/respawn, 2P.

- [x] **FRAME-MODEL CORRECTION -- step() is now [main loop][ISR] (2026-09-10,
  found by the death/respawn work).**  Three direct measurements: (1) the ISR
  `$8D72` CALLs `$8DB5` (both counter increments) FIRST, then `$8D88 RR L`
  branches on the NEW parity; (2) the respawn's hurry reset (`$915F` ->
  `$9170: $8DBD := 0`) is a MAIN-LOOP chain routine and in the capture window
  it precedes the ISR's increment (the window ends with `$8DBD = 1`, two
  consecutive odd frames); (3) the capture windows from `round1_48` start at
  `T%FR ~2249` -- just AFTER the ISR -- so every fixture window is [the main
  loop of frame k, whose parity the ISR that began it set][the ISR that
  begins frame k+1].  CONSEQUENCE: a fixture row's `par` is the END-of-window
  parity = the NEXT frame's.  The heavy work (player update + entity
  composite, 7 passes) belongs to the machine's ODD frames and merely
  appears on `par=0` rows -- the original SPEC's "odd -> draw" was right in
  frame terms; the M7.3b relabel matched the windows through a consistent
  inversion.  That inversion is harmless for end-of-window observables
  (every gate passed) but breaks main-loop -> ISR causality inside a frame
  (the engine would end the respawn step with `$8DBD = 0`, not 1, and run a
  frame late thereafter).  FIX: `step()` runs the main loop first (parity =
  the current `$8DBD`; ODD = heavy) and `isr()` at the END; the bubble passes
  now live in `isr()` on the new parity (the "even pass after the player
  update" workaround is gone -- it was the machine's structure all along);
  `PASS_T`/`DRAW_T` re-derived (6185 / 25112: the 11-pass frame is the EVEN
  one whose ISR cost 1851, the 7-pass frame the ODD one at 1481) -- the same
  7/11 emerges.  NO end-of-step observable changed: bb.test 50/50 unchanged.
  READING NOTE for M7.3b/M7.4a-d-ii above: where they say the player/draw/
  blow-check run on "EVEN (par=0)" frames, read "on par=0 FIXTURE ROWS = the
  machine's odd frames"; the mechanisms are unaffected.

  STILL OUT (M7.4d): death/respawn, 2P.

- [x] **M7.4d-iii -- DEATH, the animation, LIVES, the RESPAWN and its
  invulnerability, the hurry reset (2026-09-10).**  `playerHit` = `$927D`
  (heart flag `$FED0` -> the enemy dies instead [M7.6/7]; `+$5A` bit4/bit3 ->
  immune; else `+$5A |= $84`, `+4 := $50`).  The player tick now branches
  first on DYING (`$AB38`): `playerDeathTick` = `$AB3F-$ABD4` -- sprite
  `$D300`/`$C6C0` by `$8DBD & 8`, `X &= $F8`, `+4--` per heavy frame (80 of
  them); on going negative `+$5C` (lives) `-= 1`, RES 7 on `+7` if THAT goes
  negative (the player is out), then the respawn: `+4 := $50` (reused as the
  invulnerability countdown), `+$5A := (+$5A & 1) | $88`, RES 2 `+7`, the
  bubble power-ups stripped (`+$60/$5E/$5F/$61 := 0/8/7/0`), `+8 := 1`, `+9 :=
  0`, `$904D := 0`, `Y := 168`, `$9160 := 1`, then P1 `X := 24` facing right /
  P2 `X := 216` facing left.  `playerInvulnTick` = `$ABDE` (bit3 set and
  `$FED0 != 1`: `+4--`, RES 3 when negative -- 161 frames).  `hurryReset` =
  `$915F`, run every chain pass from `mainLoop()`: when the self-modifying
  request byte `$9160` reads 1, clear it, `$9257`/`$904D := 0`, `$8DBD := 0`
  -- and the ISR that ends the frame increments it to 1 (the measured two
  consecutive odd frames; this is what forced the frame-model correction).
  Gate (`build/death_fixture.json`, a NATURAL enemy-contact death on
  `round1_48` captured drift-free with a full engine seed): the test replays
  the direction byte and INJECTS `playerHit(0)` after the recorded death
  frame's step (the enemy collision itself is M7.6); 372 frames (to the
  recorded second death) track the harness frame-for-frame on X/Y, `+4`,
  `+7` (minus the draw toggle bit5), the death sprites, `$FDDA`, lives, the
  jump phase, BOTH frame counters, `$AA65`, the blow parameters and `$9160`.
  Mutation-tested: the X snap, the sprite bit, the lives decrement, the reset
  request, the invulnerability clear, and consuming the reset in the ISR
  instead of a chain pass each fail a named check.  bb.test 54/54, kit.test
  115/115, selftest 34/34.
  UNMODELLED: the lives-icon redraw `$806C` (HUD, M7.1), `$BF0A` (the erase
  backup on going out), `$8CB0` beyond the round-80 clear, the `$90D0` bit6
  toggle (`$ABD5`/`$90C1`), Boris's erase in the reset, the `$8E2A` game-over
  watch, and the walking sprite selection (`$D920`) -- the gate compares the
  sprite only while dying.

  STILL OUT (M7.4d): 2P.

- [x] **M7.4d-iv -- TWO PLAYERS and the P2 JOIN (2026-09-10).**  Two-player
  simultaneous play needed NO engine change: everything player-side is
  addressed from the slot base (`+$5A..` persistent struct, `+$60` cadence,
  the `+7` bit4 spawn/cap index), and the shared cadence `$AA65` ticks once
  per frame before both players.  Gate `twop` (`build/twop_fixture.json`,
  `round1_2p48`: P1 on keys walks RIGHT while P2 on KEMPSTON walks LEFT then
  jumps and lands on the row-19 ledge; 120f drift-free): both players' X, Y,
  jump phase, `+7` (minus the draw toggle), `+4`, both persistent bytes and
  `$AA65` track the harness frame for frame, each player fed its own
  direction byte (`$FD88` / `$FD92`).  The mid-game P2 JOIN ('2' held in a 1P
  game) is `playerJoin(1)` = `$99C9-$9994` (MEASURED by write-watch on the
  press frame) -- a player-START init, NOT the respawn: X := 216, sprite
  `$D920`, `$FDE4 := 1` then `|= $88`, `+$60/+$61 := 0`, `+8 := 0`, Y := 168,
  `+7 := $40` then SET 7 (facing left), `+4 := $50` (the 161-frame
  invulnerability), lives := 3; it runs from a light frame's main loop after
  the player ticks and does NOT reset the hurry timer.  Gate `join`
  (`build/join_fixture.json`, 180f from `round1_48` with the join INJECTED
  after the recorded press frame -- the '2' decode is the M7.8 input layer):
  P2's slot, `$FDE4`, lives, sprite, the hurry value, `$9160` and `$AA65`
  track for all 180 frames; the idle P1 is compared until a roaming enemy
  kills it at f151 (recorded as `events.p1_death`; no enemies in the engine).
  Mutation-tested: the join's facing and countdown, the input stage reading
  P1's direction byte for every slot, and the cadence ticking per player
  instead of per frame (that one breaks every free-fall gate at once) each
  fail named checks.  bb.test 59/59, kit.test 115/115, selftest 34/34.
  UNMEASURED: the P1 new-game start (`$97D2`) and the '2'/key decode (M7.8).

  **M7.4 -- THE PLAYER SUBSYSTEM -- IS COMPLETE**: walk, jump, fall, land,
  wall collision, in-air steering, walk-off, blow (+ the bubble's travel and
  rise), death, lives, respawn + invulnerability, the hurry reset, two
  players, the P2 join -- every piece transliterated from a measured routine
  and gated frame-for-frame against the Z80.

- [x] **M7.5-i -- the risen bubble AGE + timeout POP (2026-09-10).**  A risen
  empty bubble ages via the manager's global self-modifying toggle `$B657`
  (`$B656`, seed 0): it flips each time a risen bubble is serviced and gates
  `INC (IY+4)` (`$B666`) to every OTHER service, so a lone bubble ages +1 every
  4 frames.  When the age carries `+4` into `$80` (128) the bubble POPs
  (`$B6D8`): erase + clear `+7` bits 7/3/2 -> the slot goes inactive (measured
  `$85` -> `$01`).  `bubbleAge`/`bubblePop` in `web/game.js`; wired into the odd
  pass for risen slot 0 and slots 1-11; `$B657` seeded in `reset()`.  The
  `$5CE0` burst-effect object the pop also spawns is a DRAW effect (deferred to
  the bubble-draw increment); the holding-bubble ESCAPE path (`$B679`, +9 != 0)
  lands with capture (M7.6).  Gate (`build/bubage_fixture.json`, one blown
  bubble): the age tracks the harness FRAME-FOR-FRAME through the clean early
  window (120 frames: travel count 1..8, the rise transition, ~25 ages), and a
  SEEDED open-air lone bubble ages to 127 then pops at `+4 -> $80` clearing the
  right bits.  Mutation-tested (toggle removed -> age check fails; pop threshold
  and pop-bits -> pop checks fail).  bb.test 63/63, kit.test 115/115, selftest
  34/34.

  TWO FINDINGS (both bound the gate honestly, and shape later increments):
    * The age is NOT clean every-4 over the full 8-second life: the real
      machine's VARIABLE main-loop pass count (the M7.3b flat-timing
      simplification) occasionally skips a manager pass (measured age gaps of 6
      at idx ~120 and 5 at ~310), which the fixed 7/11 model can't reproduce --
      so the strict window is bounded and the pop is gated in isolation.
    * With TWO risen bubbles the global toggle flips once PER BUBBLE per pass,
      so the age interleaves between them -- my current odd-pass order
      (slot 0 then 1..11) makes the LATER bubble monopolise the age.  The
      460-frame idle fixture exposed this because the idle player is killed by a
      roaming enemy ~idx 300 (M7.6) and the harness recorded a stray BLOW at idx
      313; a headless engine (no enemies, player not dying) blows a 2nd bubble
      there.  The exact two-bubble toggle interleaving is MEASURED-and-gated in
      the bubble-contact increment (M7.5-iii).
    * Also confirmed for M7.5-ii: my naive attribute-only drift sends a risen
      bubble into a 127<->128 oscillation at the ceiling (no wall/bounce yet).

- [x] **M7.5-ii -- the travel-step WALL probe (2026-09-10).**  `bubbleWallProbe`
  transliterates `$BEAF`: after each travel step, read the platform layer at the
  bubble's cell (`$AEDC`: `$F800 + (Y>>3)*32 + (X>>3)`) and test the solid bit
  `$20` over 2 columns (`INC L`) x this row + one row DOWN (`+32`); on a hit,
  snap X back to the pre-step cell (`$C001 & $F8`, cached at `$BE1F`) and run the
  shared `$BEE8` rise transition (via `bubbleRise`), plus `SET 3` (bit3, burst)
  if the bubble is still on its first step (`+4 < 2`, born flush).  The manager
  passes now also dispatch bit3 -> `bubblePop` (`$B6C3` -> `$B6D8`).  Gate
  (`build/bubwall_fixture.json`, a bubble blown into the right wall): the
  bubble's X tracks the harness FRAME-FOR-FRAME -- it stops at x=224 and rises,
  where WITHOUT the probe it would overshoot (keep stepping +8).  Mutation-tested
  (probe disabled -> overshoot, X mismatch).  bb.test 65/65, kit.test 115/115,
  selftest 34/34.
  COVERAGE NOTES: the row-DOWN probe cell and the `+4<2` born-flush `SET 3` are
  faithful `$BEAF`/`$BED5` transliterations but are not exercised by the right-
  wall scenario (the border is caught by the same-row cell; the wall hit lands
  at `+4>=2`).  DEFERRED: the born-flush BURST I measured on round1 (player
  x=216) is actually a RISEN-at-wall drift effect (SET 3 at `+4=20`, not the
  born path) -- it lands with the risen wall/ceiling drift (M7.5, needs the
  `$B88D` RNG); and the pop's `$5CE0` burst-effect + `$BF16` erase are draw
  effects (bubble-draw increment).

- [x] **M7.5-iii -- the risen bubble vs PLAYER contact $B8E5 (2026-09-10).**
  `bubblePlayerContact` (called from `bubbleRiseStep` before the wind move,
  $B850) tests a risen bubble against each active, non-dying player
  (`bubbleTouchPlayer` = $B901): the $B9D4 Y-overlap (`by` in `(py-16, py+8]`)
  and $B9DE X-overlap (wide E=$10/D=15, then a facing-tight test) exactly as
  the operands read.  Facing the bubble at close overlap -> TOUCH-POP
  (`bubbleTouchPop` = $B9B6: clear/set +7 bits 4/3/1, `+4:=$14`; the next pass
  bursts it via the bit3 path).  Otherwise, pressing INTO it (dir bit2 right /
  bit3 left, $B94D) -> PUSH: X += 2*drift[B] (+-2 in the pressed direction),
  clamped ($B977), and the wind index is overridden to 8 = (0,0) so the push's
  +-2 stands ($B968).  BB_DRIFT extended to index 8.  Gate
  (`build/bubpush_fixture.json`, a poked risen bubble): PUSH -- the player
  holds RIGHT into it and the bubble's X tracks the harness FRAME-FOR-FRAME
  (shoved, not sailed through); TOUCH-POP -- a close idle overlap bursts it
  within ~2 frames of the harness.  Mutation-tested: contact disabled, push
  direction inverted, and the pop branch removed each fail named checks.
  bb.test 68/68, kit.test 115/115, selftest 34/34.
  COVERAGE / DEFERRED: the $B984 player-BOUNCE/ride path (touching WITHOUT
  pressing in) is a no-op stub -- so the $B94D "pressing-in" guard's false
  branch and the Y-overlap UPPER bound (`by <= py-16`, only at the ceiling)
  are transcribed-not-exercised by this 40-frame geometry (they cannot fail
  this fixture; noted like the wall probe's row-down cell).  Still deferred to
  later M7.5 increments: the two-bubble OCCUPANCY MARKER + RNG redirect
  ($B8C0 writes the manager-id into the colour-shadow low bits, $B6D6 clears,
  $B88D `LD A,R` redirect -- needs the RNG substitute E1; oracles captured in
  build/bubblock_fixture.json + bubceil_fixture.json, regenerable), the risen
  ceiling drift Y-wrap ($B864-$B875), the capture of ENEMIES ($BE5B, needs
  M7.6), and bubble DRAWING ($C780).

- [x] **E1 -- the RNG DECISION (2026-09-10).  Decision record: `docs/RNG.md`.**
  Measured by a 13-agent workflow (5 independent censuses, 3 design proposals, 3
  judging lenses, a synthesis, a completeness critic), with the two design-changing
  claims re-verified by hand before adoption.  THE PREMISE WAS WRONG: the plan
  assumed the game's randomness came from the Z80 R register, so E1 would be a
  substitute.  In fact `$FE85` is a real deterministic self-modifying PRNG (16-bit
  state at `$FE86/$FE87`, a bijection, orbit 54,919 from the tape seed `$002A`,
  never reseeded) and it carries essentially ALL structural randomness -- 0.46-2.0
  draws/frame in play against 0.06-0.23 for all eleven `LD A,R` sites combined.  So
  the plan's FIRST branch applies to it: transliterate exactly, no substitute.  Only
  the thin R layer gets a declared substitute.
  KEY MEASURED FACTS: exactly 11 `LD A,R`, 0 `LD A,I`, 0 `LD R,A` -> R is 7-BIT for
  the life of the machine (0..127), so both `CP $2A` checks are **1/128, not the
  1/256 in SPEC** (129 hits in 14,776 draws).  Exact R reproduction is infeasible
  (contended-vs-plain timing on the same snapshot: 0/22 matching draws AND a
  different draw count) and MEANINGLESS: two real runs 64 T apart agree on 25.5% of
  blocked-bubble redirects while a uniform substitute agrees 37.3% against a 37.5%
  ceiling -- the substitute is closer to any real run than two real runs are to each
  other.  No floating bus (0 `DB FF` in 64K), no ROM frame counter, no other LFSR.
  Two sites (`$9715`/`$FEAC`) are NOT random: one `+51 mod 128` walk read twice at
  +35, so they get an exact walk.
  SPEC/NOTES CORRECTED: the 1/256 rate; the enemy-facing address (`$B00C` -> `$B008`);
  `$FEBB`/`$FEC7` are not seeds (an instruction operand and the next-round lookahead,
  proven causally); the power-up draw is `{3,4,5}` with P(3)=1/2, not "a random 0..3",
  with the branch sense reversed.  TRAPS #30/#31/#32 added.
  NOT YET IMPLEMENTED -- this increment is the DECISION and the doc corrections only;
  no engine change, suite unmoved at 68/68.  Implementation is M7.5-iv, whose step 1
  lands the module with ZERO call sites and proves the suite still 68/68.

- [x] **M7.5-iv(a) -- the RNG MODULE, landed INERT (2026-09-10).**  Implements the
  E1 decision (`docs/RNG.md`).  Before writing a line I re-verified the spec I was
  about to bake in: the `$FE85` disassembly instruction-for-instruction, its golden
  vector reproduced three ways (my transliteration, the record, and the machine via
  `h.call` -- 8/8 on both the state sequence and the returned `A`), the substitute's
  frozen constants in node, and the site lists by scanning the image (11 `ED 5F`,
  11 `CD 85 FE`, 0 `C3 85 FE`).  One correction fell out: the PRNG seed is `$002A`
  in `build/image_tape.bin` (the loader hand-over), while `build/image.bin` already
  holds `$D8F3` because the front end has spun it -- the port seeds the former.
  SHIPPED: `BB_RNG_SITES` (the frozen eleven-entry census-in-code), `BB_PRNG_SITES`
  (the eleven `CALL $FE85` sites, which get the same throw-on-unlisted discipline),
  `class BB_Rng` (per-site LCG streams, the seven-bit extraction in ONE function,
  the class-B `+51` walk, frame-keyed feed with three named failures, snapshot/
  restore, `info()`), `prngNext(site)`, and the `reset()` wiring.  No change to
  `web/platform.js` or `web/template.html`; the class and both tables are reachable
  as `BB_Game` statics.  **CHECK ZERO: with ZERO call sites the suite was UNMOVED at
  68/68, 115/115, 34/34** -- the evidence the module changed nothing.
  GATES (none need a fixture or harness time): the PRNG golden vector and its
  byte-image residency; the substitute's frozen constants and BOTH width checks;
  per-site stream independence including the property that motivates it (interleaved
  M7.6 draws leave the M7.5 stream untouched); the front-end walk's exact +51/+35
  structure; determinism, snapshot/restore and a PURITY trap that stubs the clock
  and `Math.random` around CONSTRUCTION as well as stepping; the faithful/added
  boundary; and the feed's three distinct failures.  bb.test 68 -> 99, kit.test
  115/115, selftest 34/34.
  MUTATION BATTERY (11 mutations, each fails a NAMED check): the extraction widened
  to eight bits, both through the shared function and bypassing it; three ways of
  breaking `$FE85`; a shadow copy of the PRNG state; one seed for all streams; the
  wipe sites given an iid generator; the wipe armed as two independent walks; an
  unlisted site drawing silently; and a wall-clock seed.
  A FINDING ABOUT MY OWN GATE, logged as TRAPS #33: the first battery had TWO
  mutations that did not bite, and the important one was a real defect -- the width
  gate re-implemented the seven-bit shift inside the test instead of calling the
  engine's, so it was testing the test.  Fixed by making the extraction a single
  named function the gate exercises, plus a second assertion through the real
  `rng.draw()` path.  (The other was a badly-built mutation, not a gate weakness.)
  STILL NO CALL SITES: nothing draws yet.  Wiring `$B88D` is M7.5-iv(b).

- [x] **M7.5-iv(b) -- the manager schedule and the player phase CORRECTED, and the
  WHOLE behavioural suite re-baselined onto the ISR-exit boundary (2026-09-11).**
  WHAT LANDED: `bubbleEvenPass`/`bubbleOddPass` are replaced by one
  `bubbleManagerPass` (twelve slots, ascending, `$BFF7` written as the counter);
  the PLAYER update moved out of the main loop into the ISR's odd branch, which
  is where the machine does it, so the player and the manager are now one frame
  APART as they are on the hardware; and ALL THIRTEEN fixtures were re-captured
  with the new `tools/capture.py` at the ISR-exit boundary.  Key scripts were
  recovered from the OLD fixtures' own recorded `$FD88` bytes rather than from
  their prose notes, so the scenarios are reproduced exactly rather than guessed.
  2421 rows; every row carries its sample PC and none landed inside a routine
  the ISR calls.  Suite 99 -> 100, kit.test 115/115, selftest 34/34.
  THE GATE THAT PROVES IT: the `bubpush` AGE column.  X alone cannot see the
  schedule (it advances on the same row under either model); the age advances in
  the SAME pass as the move, so it separates them.  MUTATION BATTERY: the
  ORIGINAL BUG (player update back in the main loop) now fails **26** checks,
  where before the re-baseline it failed none; manager on the wrong parity fails
  13; step-and-tick split across passes fails 6; the old slot-split fails 1.
  HONEST GAPS in that battery: reversing the slot order and dropping the `$BFF7`
  write BOTH still fail 0 checks, because nothing consumes the occupancy marker
  yet -- they become live in the next increment, and are listed as its required
  mutations rather than claimed as covered now.
  THREE DECLARED RACES, each derived from the FIXTURE rather than hard-coded: the
  machine drops a whole manager pass when the main loop has `$FEC5` clear as the
  ISR samples it (~1% of even frames), which the flat-timing model cannot place.
  It shows up as an age gap of 6 where every other is 4 (so the `bubage` window
  now ends at the first such gap, computed from the data) and as a missed travel
  step (so `blowleft` carries a measured `compare_until`).  Also corrected: the
  hurry reset is consumed by the main-loop chain on the frame AFTER the respawn,
  because the respawn now requests it from inside the ISR; and the death sprite
  is comparable only once the death ANIMATION owns it, since on the hit frame
  the machine still shows a walking sprite, which is unmodelled.

  THE FINDING THAT PROMPTED ALL OF THIS (kept for the record):
  Settled by a 10-agent measurement + adversarial workflow, then re-verified by hand.
  THE ERROR: since the BLOW increment the engine has modelled the manager as SPLIT
  BY SLOT across frame parities (slot 0 on one, slots 1-11 on the other).  The
  machine instead runs `$B636` as ONE unconditional twelve-slot loop, slots 0..11
  ascending, ENTIRELY inside the EVEN-parity ISR; the odd ISR touches no bubble byte
  (zero pool writes on odd parity in 470 frames of scripted play), and `$B836` has
  exactly one caller in the whole 64K, so there is no second path.
  ROOT CAUSE (now TRAPS #34): the blow/bubage fixtures were captured at a fixed
  `t0 + k*FRAME_T` offset that lands INSIDE the even ISR, between slot 0 X write and
  slot 0 `+4` write -- so ONE manager pass was cut in half and recorded as two
  half-passes on consecutive rows, which reads exactly like two alternating
  half-schedules.  Constructive proof: the committed fixture reproduces with ZERO
  differing rows for sampling phases +1650..+2250 T and for no other phase.
  WHY THE GATES PASSED: they compared X, which advances on the same row under BOTH
  models.  The discriminating column is the AGE, which advances in the same pass as
  the move.  The gate was blind by COLUMN as well as by boundary.
  VERIFIED BY HAND THIS SESSION: adding the age column (rows 0-10) to the already
  wired `bubpush` gate makes the CURRENT engine fail at row 2 with `+4 22!=21`,
  exactly as predicted -- the TRAPS #33 proof that a gate rejects a named wrong
  variant.  Correcting the manager to a single twelve-slot even pass turns that
  column green and takes exactly the four predicted checks red (blow, blow2,
  blowleft, bubage), which are the FIXTURE BOUNDARY DEFECT, not a regression.
  A SECOND, LARGER PROBLEM SURFACED (now also fixed above).  Re-capturing those four
  at the ISR-exit boundary still does not make them pass, because the PLAYER UPDATE
  is also mis-phased: the machine does it in the ISR that makes parity ODD and the
  manager in the NEXT ISR, which makes it EVEN -- ADJACENT frames -- whereas the
  engine does the player update in the MAIN LOOP gated on the CURRENT parity, so it
  performs both in ONE step and nothing in the next.  The old fixed-phase captures
  hid this too.  MEASURED BLAST RADIUS of the full correction (player update moved
  into the odd ISR branch): 14 checks across 11 fixtures go red -- walk, jump,
  leftwall, airsteer, fall, fallleft, death, twop, join, bubwall, bubage -- i.e. a
  RE-BASELINE of essentially the whole behavioural suite onto the ISR-exit boundary.
  Encouraging: under the full correction two of the three blow scenarios PASS against
  ISR-exit captures; bubage still fails, so at least one subtlety is unidentified.
  (That plan was carried out in full; see WHAT LANDED at the top of this entry.)
  STILL TO DO, the increment this whole detour was in service of: wire the occupancy
  marker (`$B8C0` write / `$B6C8` clear, value = `$BFF7` = 12 - slot) and the `$B88D`
  blocked-drift redirect, gated by the phase-invariant subset of
  `build/bubblock_fixture.json`, and reconcile that `LD A,R` site against
  `docs/RNG.md` and `BB_RNG_SITES`.  Its REQUIRED mutations are the two that cannot
  bite yet: reversing the slot iteration order, and dropping the `$BFF7` write.
  ALSO CORRECTED HERE (measured, adversarially confirmed): the SPEC manager-schedule
  paragraph, and the SPEC claim that two risen bubbles age ALTERNATELY -- the `$B657`
  toggle is SHARED and flips once per risen body, so an EVEN number of risen bubbles
  returns it to its entry value every pass and the assignment is FIXED (measured: one
  bubble frozen at 21 while another climbs 21,22,23,24).
  DECLARED, NOT MODELLED (for later increments): `$FEC5` is briefly cleared by the
  main loop, dropping a whole manager pass on ~1% of even frames, which the flat
  timing model cannot reproduce and which is why the bubage gate has a bounded window;
  the even ISR is not flat-cost and can exceed a whole frame with a full pool; the
  lightning storm can leave permanent ghost markers, so "zero means unoccupied" is not
  an invariant after it; and `BB_ISR_ODD` is far below the measured odd-ISR cost --
  its own increment, not to be folded in here.

- [x] **M7.5-v -- the OCCUPANCY MARKER and the `$B88D` blocked-drift redirect
  (2026-09-11).**  The increment the schedule detour was in service of.
  `bubbleRiseStep` is now the full `$B836`: clear this bubble's previous marker
  (`$B6C8`, one byte, `AND $E0`, gated on bit 2 because a TRAVELLING bubble
  caches Y/X in `+2/+3` instead and must never clear); save the PRE-CONTACT
  position (the machine self-modifies the operand of the `LD DE,nn` at `$B87F`);
  read the wind index; player contact; the wind move; then probe the POST-DRIFT
  cell AND the cell one row down and one column right.  FREE only if BOTH read
  zero in the low five bits -> mark at `cell + $21`, position kept.  BLOCKED ->
  one random delta applied to the PRE-CONTACT position (so the wind move AND any
  player push are BOTH discarded), Y >= `$C0` wrapped to 0, marked at the new
  cell with no `+$21` and no re-probe.  The marker is OR-ed into the LOW FIVE
  BITS, preserving bit 5 (platform-solid) and bits 7-6 (wind); its VALUE is
  `$BFF7` = 12 - slot.  The X clamp runs AFTER the write, so the two can
  disagree.  `bubblePop` now clears the marker too (`$B6DD`).
  CLEAR-BEFORE-PROBE IS LOAD-BEARING: a stationary riser clears and rewrites the
  same cell and stays free; probing first would block it on its own marker every
  pass and burn a random draw each time.
  THE RNG: `$B88D` is the `BUB_DRIFT` site from `docs/RNG.md`, drawn through
  `rng.draw(0xB88D, slot)` -- the first live consumer of the E1 substitute.
  GATE (`build/bubblock_fixture.json`, re-captured at the ISR-exit boundary):
  two risen bubbles whose cells collide, so the HIGHER slot finds the LOWER
  slot's marker written earlier in the SAME ascending pass.  Every one of the
  machine's draws is fed back frame-by-frame through `rng.expect`/`endFrame`, so
  the comparison is fully deterministic and the substitute's own values never
  enter.  120 rows of positions, flags, ages and MARKER CELLS.  bb.test 104/104,
  kit.test 115/115, selftest 34/34.
  MUTATIONS -- including the two that were INERT until the marker had a consumer,
  which was the whole reason they were carried forward as required: reversing the
  slot order now fails (the feed's own tag assertion catches the wrong slot
  drawing); dropping the `$BFF7` write fails; the XOR-6 remap inverted, the mask
  widened to `AND 7`, the blocked base taken POST-drift instead of PRE-contact,
  the free path marking at the cell instead of `cell + $21`, and clearing AFTER
  the probe all fail named checks.
  TWO GATE DEFECTS FOUND AND FIXED WHILE DOING THIS.  (1) Three mutations were
  CRASHING the suite instead of failing a check, because a feed violation threw
  out of the gate -- they are by-design named failures and are now reported as
  such.  (2) Clobbering the solid/wind bits on the marker write failed NOTHING:
  the two-bubble scenario runs in open air where those bits are zero, so the
  distinction was invisible.  Closed by MEASURING a case that does exercise it --
  a risen bubble whose marker cell lies on a solid platform row reads `$2C`, the
  solid bit plus slot 0's marker -- rather than declaring the gap.
  STILL OUT of M7.5: steal-oldest (`$BD93` -> `$BDBC`, which clears a marker
  AHEAD of the loop), the free-path Y-wrap at `$B864-$B875`, holding/escape
  (`$B679`), capture (`$BE5B`, needs M7.6 enemies) and bubble DRAWING (`$C780`).
  DECLARED: the lightning storm can leave permanent ghost markers, so "zero means
  unoccupied" is not an invariant after it; and `$B6D8`'s 4x4 scan underflows
  below `$F800` for a marker in the top map rows.

- [x] **M7.5-vi -- STEAL-OLDEST and the free-path vertical WRAP (2026-09-11).**
  STEAL-OLDEST (`$BD93-$BDC0`): when the blow finds no free slot it reuses the
  bubble with the LARGEST `+4` among those NOT holding an enemy, pops it (which
  RELEASES its occupancy marker, ahead of the manager loop) and spawns there.
  The machine's scan starts with its running best at 0 and its candidate pointer
  parked on slot 0, so an all-holding pool falls back to slot 0 -- reproduced.
  The VERTICAL WRAP (`$B864-$B875`) on the free path: a Y landing exactly on 0
  reappears at `$B7`, and `$C0` or beyond reappears at 1.
  GATE (`build/bubsteal_fixture.json`): all twelve slots seeded active and risen
  at ages 10,20,...,120 with the OLDEST (slot 11) HOLDING an enemy, so the rule
  must SKIP it and take slot 10 -- which separates the real rule from "take the
  largest age".  Filling the pool by play is impractical and that was MEASURED,
  not assumed: the blow debounce only re-arms when a bubble rises, so holding the
  key never gets the pool above ONE bubble in 400 frames.  All twelve slots are
  compared after the pass, plus the colour-shadow bytes.  bb.test 108/108,
  kit.test 115/115, selftest 34/34.
  MUTATIONS: ignoring the holding check, stealing the youngest, always stealing
  slot 0, and skipping the pop all fail named checks.
  A THIRD GATE DEFECT OF THE SAME FAMILY, found and fixed here.  Skipping the pop
  initially failed NOTHING, twice over.  First the seeded bubbles carried the
  `$02xx` placeholder pointer, so they had no marker to release; fixed by letting
  the pool run two passes before arming the blow.  Then it STILL passed, because
  the gate seeded the bubbles but not the COLOUR SHADOW, so the engine began with
  no markers at all and the release was invisible either way.  Only once the
  fixture recorded and the gate seeded the shadow did the mutation bite.  The
  recurring lesson: a gate must start from the same WORLD the harness had, not
  just the same entity bytes.
  TRANSCRIBED, NOT EXERCISED: the vertical wrap.  MEASURED as unreachable on
  round 1 -- the ceiling wind holds a bubble at y=55, so neither branch occurs in
  any committed fixture.  Flagged in code.
  ALSO FIXED: a stale comment in `playerBlow` still asserting the old slot-split
  model (a spawned bubble waiting a pass before moving).  It does not: the blow
  check runs at the TOP of the manager pass, so the bubble it spawns is serviced
  by that same pass -- visible in this fixture, where the stolen slot's `+4` is
  spawned at 1 and ticked to 2 before the frame ends.

- [x] **M7.3c -- the frame-timing model REBUILT (2026-09-12).**  The retraction
  below is now acted on; the engine no longer ships the wrong model.
  SHIPPED: `BB_ISR_ODD`/`BB_ISR_EVEN`/`BB_DRAW_T` are GONE, replaced by a frozen
  `BB_COST` table of MEASURED per-item costs plus `BB_INT_PHASE` and one named
  `BB_ISR_UNMODELLED_ODD`.  `isrCostFor(odd)` computes the branch cost from the
  POPULATION -- entities for the odd branch, live pool slots for the even one --
  so the even branch reproduces the machine's EXACT empty-pool 1851 T
  (483+184+1184) and scales ~5300 T per bubble.  `step()` is now a ledger: the
  main loop is budgeted by what the PREVIOUS ISR left, the phase of the pass the
  interrupt CUT is carried rather than discarded, ZERO passes is expressible, and
  an ISR longer than a frame is expressed as the next interrupt being LOST (the
  ISR skipped) while `frame` still advances exactly 1 -- the runtime's wall-clock
  contract depends on that.  `drawPass` is renamed `entityComposite` and called
  ONLY from `isr()`, on the ODD branch, BEFORE the entity update.  `timing()`
  becomes `frameLedger()`, which REPORTS the one inexact term every frame.
  THE FIXTURES DID NOT MOVE, as predicted: the sample point is unchanged, so all
  20 behavioural fixtures were untouched.  Only `build/timing_fixture.json` was
  corrected (`draw_parity` 0 -> 1, the retracted fields kept as provenance).
  GATES: the render check is now TWO-SIDED (renders on the odd branch, does NOT
  on the even) because a never-render engine satisfies a one-sided check
  vacuously; the two transcription tautologies are DELETED (they compared the
  engine constant against the fixture field it was derived from -- TRAPS #33);
  the pass-count checks no longer assert a false invariant (the census showed
  "invariant 11 / mode 7" was a scope error) but a measured RANGE plus the
  structural fact that the heavy branch affords strictly fewer passes.
  bb.test 108 -> 114, kit.test 115/115, selftest 34/34.
  MUTATIONS, six, each failing a named check: the retracted model (composite back
  in the main loop); never render; the odd cost reverted to the old 1481; the
  even branch as a constant; an overrun advancing `frame` by 2; and the cut-pass
  phase discarded.
  THREE COVERAGE GAPS FOUND AND CLOSED in the first battery -- the last three
  mutations all failed NOTHING at first, because no gate exercised a non-empty
  pool, nothing reached the overrun path, and nothing observed the carry.  Closed
  with a pool-occupancy slope check, an INJECTED overrun (the rate is chaotic and
  declared; the mechanism is gatable), and a check that the heavy-branch pass
  count varies over a run.
  STILL DECLARED, not modelled (docs/TIMING.md): the drop RATE and which frame
  drops; the `$FEC5` race; the partial final pass; and `BB_PASS_T` as a round-1
  fit, so the main-loop logic rate is off by up to ~50% away from round 1.

- [!] **M7.3b RETRACTED -- the frame-timing model was WRONG.
  Decision record: `docs/TIMING.md` (2026-09-11).  ACTED ON above.**  Settled by a
  13-agent measurement + adversarial workflow; the two central claims were
  re-verified by hand before adoption.  Docs and comments corrected here; the
  ENGINE RESTRUCTURE is its own increment.
  ONE MEASUREMENT BUG, TWO WRONG CONCLUSIONS.  The interrupt's cost was
  bracketed from entry until the STACK POINTER returned -- but the sprite
  blitter switches the stack itself (14 times per odd interrupt), so the bracket
  stops after 1481 T inside the draw.  That gave the cost as 1481 T instead of
  ~27000 T (19x out); and because the FIRST display write lands 139 T AFTER the
  bracket gives up, all ~288 writes fell outside the measured "interrupt" and
  were attributed to the main loop -- which is how the SPEC came to say the
  heavy composite is a main-loop event on even frames.  RE-VERIFIED BY HAND:
  the stack bracket reproduces 1481 T terminating at `$A48A`; the structural
  bracket gives 27151/27490 T on odd frames with 288 display writes inside the
  interrupt from blitter pages `$A4-$A7`, and ZERO display writes in the main
  loop.  **The draft that the 2026-09-10 "correction" overturned was RIGHT; that
  correction is the regression.**  Logged as TRAPS #35.
  ALSO REFUTED: the pass count is not invariant 11/7 (that was a scope error --
  a small sample of one idle state); it is (budget - interrupt cost) / pass cost
  with both terms state-dependent, and it reaches ZERO passes in 11.7% of
  windows in one measured state, losing a chain tick.  And the interrupt DOES
  overrun a whole frame naturally, losing an interrupt outright (disabled on
  entry, re-enabled only at the end), so the game clock runs at 39.6-50.08 Hz
  under load -- refuting the committed note that it never overruns.
  THE GOOD NEWS, measured not assumed: **the fixtures do NOT need re-capturing.**
  The sample point does not move, and the restructure was measured to score
  106/108 with ZERO fixture edits; only the stale timing fixture is replaced.
  Inverting `step()` is REFUTED -- it produces the wrong parity on a specific
  recorded row (the frame after a respawn, where a main-loop routine zeroes the
  byte that IS the parity) and would force a second full re-baseline.
  LANDED IN THIS COMMIT (docs and comments only, suite unmoved at 108/108):
  `docs/TIMING.md`; TRAPS #35; and the three refuted claims in `web/game.js`
  that were shipping INSIDE the built artifact are now marked refuted in place.
  THE RESTRUCTURE, next: cost the interrupt from measured per-item costs taken
  as ARGUMENTS (not from the engine's own scene -- it is empty, and an emergent
  cost computes 2253 T against a measured 25692-39900 T, an error the same order
  as the bug being fixed) plus one named, reported, shrinking term for the enemy
  population; carry the cut pass's phase; express a lost interrupt as the
  interrupt being SKIPPED, never as advancing the frame counter by more than 1;
  delete `BB_DRAW_T`; invert the render check and rewrite the three pass-count
  checks, which currently stay green only inside a window ONE PASS WIDE.

- [~] **M7.5-vii -- the bubble SPRITES and the draw ORACLE (2026-09-12).
  MEASUREMENT ONLY: the blit operation is not decoded, so nothing draws yet.**
  A PROVENANCE CORRECTION first: `docs/SPEC` claimed the bubble sprite base
  `$C780` was RUNTIME-BUILT ("live vs image.bin differ 60/64 bytes").  That does
  not reproduce.  All 384 bytes of `$C780` (EMPTY) and `$C900` (HOLDING) are
  byte-identical across `build/image_tape.bin`, `build/image.bin` AND a live
  in-play state -- they are STATIC TAPE DATA and are extracted directly.
  `$D380` (FLASHING) genuinely does differ, 105 of 384 bytes, and is still
  unexplained.
  MEASURED LAYOUT: EIGHT pre-shifted X sub-positions of 48 bytes, offset
  `(x & 7) * 48` -- note eight, where the entity sprites have four at even
  sub-positions.  `$B9E7` is its OWN blitter, not the 16x16 entity one: it picks
  the sprite by state (HOLDING when `+9` = 1; FLASHING when `+4` >= `$E6` or
  `$B62D` set; else EMPTY), parks SP on the sprite and POPs it, and has SEPARATE
  code paths for even and odd Y.
  MEASURED FOOTPRINT, from the oracle rather than from reading: exactly 16 pixel
  rows starting at Y, 3 columns wide from `X >> 3`, 51 writes per draw (15 rows
  of 3 plus one row written twice).  There is NO vertical sub-shift -- the
  display's own pixel-row addressing carries arbitrary Y, which is why the 48
  bytes are exactly 16 rows x 3.
  THE ORACLE (`build/bubdraw_fixture.json`): 20 cases covering all eight X
  sub-shifts x both Y parities, plus a draw over a platform row (non-zero
  background) and one of each sprite variant.  Each records every display write
  as address + value AND the byte that was there BEFORE, which specifies the blit
  as a function of (sprite, position, background) -- a far tighter target than a
  whole-screen diff, and the thing the transliteration will be gated on.
  GATED NOW: the asset shape, the provenance correction, and the GEOMETRY --
  every write lands inside a 3-column by 16-row box at the bubble position, all
  cases write 51 bytes, and the oracle covers all eight shifts and both parities.
  bb.test 114 -> 120, kit.test 115/115, selftest 34/34.
  WHAT IS NOT DONE, stated plainly: the blit OPERATION.  It is neither a plain
  store nor a pure OR -- some sprite bits are cleared -- and the mask table at
  `$BFF8` is indexed by `(x & 7)`.  Deciding it needs a READ-ORDER trace of the
  stack blitter, which is the next increment.  Nothing draws bubbles until then.

- [x] **M7.5-viii -- the BLIT OPERATION, and two provenance corrections.**
  DECODED from the disassembly and proved against the machine.  `$B9E7` keeps the
  DISPLAY pointer in one register bank and the SHADOW pointer (`display + $A000`,
  from `$BA6F ADD A,$A0`) in the other: it is the only routine in the game that
  reads the CLEAN PLATFORM LAYER, and compositing against the shadow rather than
  the display is exactly what a display-only oracle cannot show.  Per pixel row,
  three columns from `X >> 3`, `M = ($BFF8 + (X & 7))`:
  col 0 `(disp & M) | (shad & ~M) | spr`, col 1 `shad | spr`,
  col 2 `(disp & ~M) | (shad & M) | spr`.  Sixteen rows from Y; the 48 sprite
  bytes run in BOUSTROPHEDON order (row 0 left to right, row 1 right to left)
  because the routine walks L forward through one row and back through the next.
  TWO ROWS CARRY NO SPRITE: the prologue `$BA78` is the loop body `$BA97` with its
  three `OR`s removed, so row 0 is a pure background restore, and the tail `$BB94`
  re-writes the last row background-only -- how the routine erases a rising
  bubble's one-pixel trail, and why 51 writes land on 48 addresses.  Row addresses
  come from the game's `$FD00` table, NOT the ULA formula: rows 0-1 hold the
  sentinel `$01FF`, so a draw that reaches the HUD rows writes into ROM and is
  DROPPED (measured: Y=8 makes 27 writes, Y=0 none).
  PROVED BEFORE PORTING: a Python transliteration reproduced every write, in
  order, for all 32 oracle cases and for a 1,536-case sweep of every X sub-shift
  x every Y residue x every bubble kind (`tools/bubdraw.py verify --sweep`).
  CORRECTION 1, the sprite bases.  `(IY+9)` is the bubble's KIND -- 0 empty,
  1 holding, 2 water, 3 lightning, 4 fire -- not a flag.  kind 0 -> `$C780`,
  kind >= 2 -> `$D380`, kind 1 -> `$C900` except that a holding bubble past age
  `$E6` FLASHES by alternating with the EMPTY sprite on the `$B62D` toggle; it
  does NOT switch to `$D380`.  The M7.5-vii note had this garbled, and its own
  "flashing" oracle case in fact drew HOLDING -- the rule was never exercised.
  `build/sprites_bubbles.json`, written back in M5, had it right.
  CORRECTION 2, `$D380`.  M7.5-vii recorded its 105/384 difference from the tape
  as unexplained; it is RUNTIME-BUILT by `$BF5B` (one caller, `$94B7`): `LDIR
  $C780 -> $D380`, OR the element glyph from `$C068 + 2*(($7E0E) - 2)` into rows
  4-11 of shift 0, then generate shifts 1-7 by shifting each 24-bit row right one
  bit.  That is why `$D380` is an EXACT pre-shift table (block s == block 0 >> s)
  while the hand-drawn `$C780`/`$C900` are not -- the signature that identifies
  it.  The transliteration reproduces the live `$D380` of `elfire`, `elwater` and
  `ellight`, 384/384 bytes each.  `$D380` is therefore NOT shipped as an asset.
  And the `$C780`/`$C900` anomaly in the OLD states (`play1p`, `round1`, `crowd`,
  336/384 different) is not a build at all: those were captured on the 128K
  branch, which `LDIR`s its AY engine over `$C350-$D263` (`$96B3`) -- 3,617 of
  the 3,860 bytes in that window differ and 0 outside it.  That branch hazard was
  ALREADY recorded (TRAPS #28, and the state list in the project memory); it
  still misled a session because it arrived as a question about graphics, with
  nothing about sound in it.  TRAPS #36 records how it got through.  The real
  discriminator is `$8DC4` (`$F3` 128K / `$C9` 48K), not `$9AE7`.
  SHIPPED: `web/gfx.js` `bbBlitBubble` + `bbBuildElementBubble`; `bubbleSprite`
  and `bubbleDraw` in `game.js`, wired at the `$B653` position between the drift
  move and the age tick; the `$FD00` row table and `$BFF8` mask table seeded into
  the world image; `build/bubble_sprites.json` as a required asset.
  GATED byte-exact against 32 oracle cases (1,464 display bytes plus 48 dropped
  ROM-window addresses), each recording the display AND shadow byte before every
  address in the box, so the gate is a closed function of
  (sprite, position, display, shadow) and needs no harness.
  THE FIRST MUTATION BATTERY HAD SIX SURVIVORS and that is the real lesson of
  this increment (TRAPS #37): on a settled scene the display EQUALS the shadow at
  every touched address, so the background source and the mask polarity are
  unobservable, and rows 0 and 15 of the real sprite are BLANK, so the two
  no-sprite rows are unobservable too.  The oracle was re-captured with cases
  that DIRTY the display away from the shadow, cases that draw a SYNTHETIC
  all-non-zero sprite table, and cases on the sentinel rows -- and with the box's
  untouched addresses recorded so a write to the wrong place is examined rather
  than ignored.  All 18 mutations then died: shadow source, mask polarity, middle
  column, boustrophedon, row 0's discard, the tail restore, 15 rows, `X&6`
  pre-shift, ULA-formula addressing, the ROM-write drop, both `$D380` build
  details, both variant rules, the call site on the wrong path, the missing call,
  and both seeded tables.
  bb.test 120 -> 135, kit.test 115/115, selftest 34/34.
  NOT DONE, and named: the ERASE `$BF16` and the travelling-bubble draw path
  (`$BE58`/`$BEAC`) -- the manager draws risen bubbles only; the `$D380` builder
  ships and is gated but has no caller yet (nothing creates element bubbles until
  M7.6); `$C700`/`$D340`/`$D360`, the burst shimmer, are untouched.

- [x] **M7.5-ix -- the ERASE `$BF16` and the travelling draw path.**  `$BF16` turns out not to be
  a bubble routine: it calls the ENTITY draw master `$A447` with two self-modifying patches --
  `$A5D9`, the junction where `$A447`'s erase half ends and its draw half begins, set to RET, and
  `$A480`'s `JP nz` made unconditional -- plus the flags forced to `$C0`.  "Run only the erase
  half."  It repaints the 3x16 box at the CACHED position (`+2` = Y, `+3` = X) from the shadow
  with the same composite `$B9E7` uses for its two sprite-less rows, 48 writes.
  TWO measured differences from the draw: the mask is the ENTITY table `$AA4F` indexed by
  **`X & 6`** (not `$BFF8` by `X & 7`), so for an odd X the erase uses a mask one step coarser
  than the draw just used; and the boustrophedon RESTARTS FORWARD at each of the three block
  boundaries, where the draw runs one unbroken zig-zag.
  A BUG THE EDGE CASE CAUGHT, in code committed the same day: the column walk is `INC L`/`DEC L`,
  EIGHT-BIT, so a row's three columns wrap inside the 256-byte page.  `bbBlitBubble` shipped with
  16-bit arithmetic and was wrong for x >= 248 on a row whose low byte is `$E0`.  The draw oracle
  had no case there; the erase oracle's right-edge case did, and failed.  Both blitters now share
  `bbRowBase`/`bbColAddr`, and the draw oracle gained three page-wrap cases.
  WIRED at all three real call sites: `$BEE8` (the rise transition, before `+3` is repurposed),
  and `$BE55`/`$BE58` on the travelling tick.  That also moved the CAP TEST out of the `$BE01`
  tick and back into `$BE07` where the machine has it, and added `$BE51`/`$BE53`: a bubble's
  first two ticks neither erase nor draw, so a freshly blown bubble is invisible for two frames.
  The risen path still has no erase -- correctly: it moves one pixel a frame and the blitter's own
  sprite-less rows clean up behind it.
  ORACLE: 17 erase cases (both mask rules separated by an odd X, the page wrap, the sentinel rows,
  and three cached-Y >= `$C0` cases that write nothing) plus a 256-case sweep, all matching the
  machine write for write.
  A NEW GATE, and the interesting part: the erase writes no sprite data, so its boustrophedon is
  INVISIBLE in the finished display -- three distinct addresses per row, so the order cannot change
  the result.  Two ordering mutations survived the byte-exact gate.  Both blitters are now checked
  through a recording proxy against the oracle's ORDERED write list (2,358 writes), which is a
  stronger claim than the final bytes: it is "we reproduced the routine", not "we reproduced its
  effect".
  17 of 19 mutations killed.  The two survivors are proved unobservable rather than untested, and
  are labelled TRANSCRIBED-NOT-EXERCISED in the code: the cached-Y >= `$C0` early-out (row-table
  entries 24-31 hold `$0000-$00E0`, so those rows address ROM and the writes are dropped anyway --
  two guards masking each other), and the 8-bit row-BASE add (the table's low bytes top out at
  `$E0` and a byte X gives at most column 31, so `$E0 + 31 = $FF` never carries).
  bb.test 135 -> 143, kit.test 115/115, selftest 34/34.
  NOT DONE: the capture tail `$BEA9` is wired only as far as the shared erase/draw -- `$BE5B`
  itself is M7.6.  The engine still restores the whole clean layer each frame instead of relying
  on these per-entity erases; replacing that is the M7.3b follow-up, and until it lands the erase
  is faithful but largely redundant.

### Next increments (order from the plan, each its own gate)

- [ ] **M7.1 -- HUD + all-81-rounds geometry.**  (`extract_sprites.py` must
  also grab all `$160` bytes per sprite -- see M7.2 -- before sprites ship.)
  Extract every round's clean shadow+colour (poke `$8609`, call `$7F62`) into
  the asset; write the HUD renderer (score BCD -> font digits at rows 0-1; the
  substitute-font departure declared).  Gate: each round's clean frame == harness.
- [x] **M7.3b DONE -- the per-entity render pass replaces the full-frame restore.**
  MEASURED FIRST, and it overturned the engine's render model: the whole-screen
  platform paint `$8216` runs ZERO times in 20 frames of play, and the attribute
  file is never written by the render path (61 writes in 40 frames, all from
  `$8017`, the HUD).  What happens instead is 272-288 display writes on the ODD
  ISR frame and none on the even one -- each entity ERASED at its cached position
  and REDRAWN at its current one, the draw updating the cache.  `renderFrame()` is
  now what it always should have been: the ROUND-START paint, called once.
  `$A447` transliterated whole -- both erase paths (ALIGNED `$A483`, two columns
  copied straight from the shadow; SHIFTED `$A53C`, three columns masked from
  `$AA4F + (X & 6)`), the entry gates, the cache update, and the INVULNERABILITY
  FLASH, which turns out to live in the RENDERER: on toggle phase 0, slots 0 and 1
  only, bit3 of the player state byte returns before the draw, and because that is
  before `$A603` the cache is not updated either.
  `$A3AD` transliterated whole, and it is a BEAM-CHASING SCHEDULER: an entity whose
  sprite rows fall in a 30-line window that advances with the work done is SKIPPED
  and the list swept again, until every entity has been drawn.  The window test
  uses plain 8-bit compares, so a wrapped window is empty and skips nothing --
  transcribed as measured.
  A M7.2 CORRECTION fell out of it.  `bbBlit16` had shipped since M7.2 with two
  edge faults, because its fixture put four sprites in the middle of the screen:
  it used the ULA formula instead of the `$FD00` row table (so character rows 0-1,
  the `$01FF` sentinel, would have scribbled the HUD instead of addressing ROM),
  and it CLIPPED at `col + i < 32` where the machine's 8-bit `INC L` WRAPS inside
  the page.  Both corrected; both blitters now share `bbRowBase`/`bbColAddr`.
  ORACLE `build/entdraw_fixture.json`: 21 `$A447` calls and 16 whole `$A3AD`
  passes, every write in ORDER with the display and shadow byte before each, plus
  the entity fields, the beam accumulator and both counters the machine leaves.
  A 288-case sweep as well.  Everything matched the machine on the first run.
  THE MUTATION BATTERY IS THE STORY AGAIN (TRAPS #37).  The first pass had TEN
  survivors, and the reason was that the eight NATURAL passes captured from round 1
  hide NOTHING and sweep ONCE -- so the whole scheduler was inert in the oracle,
  and a version that ignored the window entirely reproduced every write.  Worse,
  a gate asserted "the oracle caught the scheduler re-sweeping (write counts
  vary)"; instrumenting showed the variation came from erase-path changes, not
  re-sweeping, so that check was claiming something the data did not show.  Fixed
  by EIGHT synthetic scenes with entities at Y 170-191 (round 1's floor is Y=168,
  so this is reachable, not contrived) which produce up to 3 sweeps and 8 hidden
  visits, and by gating the BEAM ACCUMULATOR the machine leaves behind -- a number
  that depends on every visit, every skip and every path cost, and is the machine's
  rather than the model's.  Two more survivors needed an odd cached X (so `X & 6`
  and `X & 7` disagree) and a non-player slot with the flash bit set.  One survivor
  was my own seeding bug: I set bit5 on `$FDD9`/`$FDE3`/`$FDED` to test "clear NINE
  slots, not twelve", but the bytes `$A3C0` touches are `$FDE1`/`$FDEB`/`$FDF5`.
  23 of 24 now die.  The last is a proved ARITHMETIC EQUIVALENCE, labelled in the
  code: the aligned erase only runs when `X & 6 == 0`, so its mask is always `$00`
  and masking reduces to copying the shadow.
  bb.test 143 -> 155, kit.test 115/115, selftest 34/34.
  DECLARED: `$AA57` (how many slots a sweep visits) is seeded with the MEASURED
  round-1 value 5 -- on the machine the SPAWN code maintains it, which is M7.6.
- [x] **M7.6-0 DONE -- the ISR cost model, measured; BB_ISR_UNMODELLED_ODD retired.**
  A 16-agent measurement pass: five ISR components bracketed independently by
  CONTROL FLOW, each attacked on two adversarial lenses (bracket soundness,
  held-out prediction), then a synthesis that verified its own arithmetic by
  running it.  12,620 bracketed interrupts across 49 states.  docs/TIMING.md is
  rewritten as the record.
  THE HEADLINE: the 20900 T term was never a measurement gap -- it is the cost of
  the ENEMIES THE ENGINE DOES NOT SIMULATE.  Measured: 12,871-39,131 T per odd
  interrupt of absent population, 3,138-8,467 T per absent enemy (median 5,422).
  20,900 sat mid-band because that is what it always was: correctly sized,
  wrongly named, and with no way to know when it should stop being needed.  It is
  now `BB_ISR_ABSENT_ODD`, sized from the fixture, reported every frame by
  frameLedger(), and zero by construction once $FD80 matches the machine.
  THE PARTS TILE THE WHOLE: total - skeleton - (the bracketed halves) is EXACTLY
  0 on 450 of 450 interrupts in build/isrcost_fixture.json (and 12,620 of 12,620
  in the workflow's own battery).  A partition, not a fit.
  SKELETON, by segment, three independent brackets, zero variance: 130 prologue,
  91 counters, 41/46 branch, 22/28 gate, 157 epilogue, 17/10/10 handoffs.  TWO
  CORRECTIONS: ODD_OVERHEAD was 441, excluding its own 27 T handoff; EVEN_OVERHEAD
  was 483, SWALLOWING the 27 T $B62C toggle that belongs to the manager (the
  committed 483 + 184 + 1184 = 1851 tiled only because SLOT_SCAN excluded the same
  27 T, so the two errors cancelled).
  $A3AD NOW CHARGES ITSELF.  Since M7.3b the engine runs the real pass, so it
  accumulates the real cost as it goes -- per visit, per window-test outcome, per
  erase and draw class, per beam carry, per sweep.  MEASURED against the fixture:
  the engine NEVER charges more than the machine on any of 205 odd interrupts,
  is EXACT on 88, and exact on 45 of 45 for one state.  The shortfall on the rest
  is ULA CONTENTION, which the port does not model and never claimed to -- and
  contention can only ADD, so the gate asserts the DIRECTION rather than a
  tolerance.  That is a stronger claim than a tolerance and it cannot be met by
  accident.
  22 of 22 mutations killed, including every skeleton segment, every $A3AD cost
  class, the beam carry, the toggle-phase flash check, and the accumulator reset.
  bb.test 155 -> 165, kit.test 115/115, selftest 34/34.
  ALSO FOUND: `$AA57` is DERIVED, not a constant -- $72B3-$72CA walks the round's
  spawn table, counts the enemies and stores count + 2 (the two player slots).
  Round 1 = 3 + 2 = 5, exactly the value M7.3b had to seed by hand.  The `CP 9`
  clamp at $72C6 is DISABLED (the JR displacement is 0), and since max enemies is
  7 the maximum is 9 -- which is precisely why $A3AD clears bit 5 on NINE slots.
  AND: TRAPS #38, `rom_writes` is a dead counter under the C simulator.
  NOT DONE, named in docs/TIMING.md with the scene each needs: $B6D8
  burst-with-contents (the largest residue, +5.9-18.6 kT), player-bubble contact,
  the capture commit, the manager's structural per-slot cost (PER_BUBBLE 5300 is
  still a flat slope), the enemy-type handler costs per behaviour rather than per
  round, and the respawn/invulnerability terms -- which have NO natural evidence
  in any 48K state, so they are transcribed and not exercised.
- [x] **M7.6-i DONE -- the ROUND SPAWNER, byte-exact over all 79 rounds.**
  `$727B` transliterated whole and gated against the machine for every round: the
  90-byte entity table it owns, `$AA57`, the `$73A6` target-Y table, the rolling
  anim seed, the `$B552` behaviour list, the player-threshold byte and the tail --
  513 enemies, byte for byte.
  `$AA57` IS DERIVED NOW: `$72B3-$72CA` counts the round's enemies and stores
  count + 2 for the two player slots.  Max 9, which is exactly why `$A3AD` clears
  bit 5 on NINE slots.  The `CP 9` clamp at `$72C6` is DISABLED (JR displacement
  0) and transcribed that way.
  TWO THINGS I HAD NOT SCOPED: enemies do NOT start at their table row -- `$7336`
  parks each Y in `$73A6[i]` and zeroes it, so they drop in from the top; and the
  tail `$7356-$73A5` builds the enemy WAKE-UP DELAYS at `$A891` from one of eight
  patterns at `$7461` selected by byte 14, each biased `$1E`.  That is the table
  `$AA60` reads for which slots are asleep.
  THE BYTE-FOR-BYTE GATE CAUGHT THREE THINGS: a 16-BIT STORE SPLASHING onto its
  neighbour (`LD ($FD91),HL` puts the old `$FD87` into `$FD92`); the type byte's
  STRIDE TWO, invisible on round 1 because its three enemies share a type; and
  the boss divert coming AFTER the table clear, not before.
  24 of 25 mutations killed; the survivor is a labelled equivalence (every
  terminator in the table is exactly `$00`, so the `AND $F8` cannot be seen).
  bb.test 165 -> 177, kit.test 115/115, selftest 34/34.
- [x] **M7.6-ii -- the entity UPDATE pass `$AA60`** (the walker's movement is next).
  The second half of the odd ISR branch, and the last thing on the frame path the
  engine was not doing at all.  It walks `($AA57)` slots and for each decides
  whether the slot is AWAKE and which routine gets to move it.
  THE WAKE-UP SCHEDULE, which pairs with M7.6-i: the spawner leaves a delay byte
  per enemy at `$A891`, and while it is non-zero the pass ticks it and skips the
  slot -- so a round's enemies come alive in a staggered order.  The index is
  `($AA57) - 2 - ($B57C)` in EIGHT BITS, so the two player slots read `$A98F`/
  `$A990`, below the table and harmlessly, because they are exempt anyway along
  with any slot whose `(IY+9)` is `$FF`.
  THE DISPATCH: `$B612`/`$B613` take the tracked player's X+8 and Y (P2 when bit
  4 is set, which the spawner assigns by enemy index), the handler comes from the
  `$B54E` list, and it runs ONCE -- or TWICE when bit 2 is set, because `$AAE6`
  chooses `JP (HL)` over `RET` and the pushed copy of the address runs it again.
  That doubling IS the "angry" speed-up an escaped enemy gets.
  ALSO: `tickCadence()` is gone.  It was `$AA60`'s own prologue, extracted before
  `$AA60` existed in the engine; keeping both would have ticked the free-fall
  cadence twice a frame, and wiring the pass in without noticing broke five
  player-physics gates immediately.
  GATED frame for frame over 5 scenes, 235 passes, as a ONE-STEP differential
  (re-seeded from the previous frame, so the players' own movement cannot drift
  into it).  TWO OF THE SCENES ARE FRESHLY SPAWNED ROUNDS, because every shipped
  state is far enough into its round that all its enemies are awake and the
  delays never move -- on round1_48 the asleep path is simply unreachable
  (TRAPS #37).  118 frames where a delay actually ticks.
  17 of 17 mutations killed.  Five of them survived the first run, all because
  the CHECKS could not see them rather than because the model was loose: the
  settler divert, both wake-up exemptions, and the handler cursor were only
  observable once the test rig recorded WHICH handler ran for WHICH slot.
  bb.test 177 -> 195, kit.test 115/115, selftest 34/34.
  NOT DONE: the handlers themselves.  All eight are thin wrappers around the
  shared walker `$B028`, so enemies hold position for now; `enemyHandler()` is a
  declared no-op.  Its oracle is already captured -- build/walker_fixture.json,
  five scenes, 485 frames of the enemy table.
- [x] **M7.6-iii -- the SHARED WALKER `$B028`; enemies move.**  Gated frame for
  frame over 223 passes, 373 enemy moves, 6 turns.  The pause timer short-circuits
  everything and is a HOP WIND-UP, not hesitation; the move has a divider, a
  three-row floor search, the 1/128 `LD A,R` and a comparison with the player's
  row; the step is stopped by a WALL (turn round) or a LEDGE (hop), with an
  ASYMMETRIC look-ahead -- two cells right, one left.
  FOUR CORRECTIONS/ADDITIONS: `$AED1` returns Z for NOT-solid and early-outs above
  the HUD; `$AB0C` is a per-slot TAIL run for every visited slot (X forced even
  and clamped, Y wrapped) which I had not scoped; the handler CURSOR advances on
  the skip paths but not when asleep; and the eight handlers are FOUR SHAPES, not
  one -- type 7 doubles the step (the measured fast walker), type 6 patches the
  ledge test away, type 4 calls another routine.  Two shapes transliterated; the
  other five are held out of the gate and counted.
  THE SCENES WERE THE WORK: the first battery had 17 survivors because nothing
  reachable from a shipped state exercises the walker -- on round1_48 the divider
  always passes, so `$B0D5` is not reached ONCE in 30 frames.  Two synthetic
  scenes (a wall turn, and a states scene seeding a running pause, an angry enemy
  with its counter between the two thresholds, an odd in-range X, and enemies
  outside the bounds) took it to 23 of 28 killed.
  ALSO FIXED: the capture read IY with its bytes swapped (harness.py:95 makes 10
  the HIGH byte), so hesitation draws were tagged slot -2420.
  bb.test 195 -> 199, kit.test 115/115, selftest 34/34.
- [x] **M7.6-iii AUDIT -- the sampled world was hiding two decisions and one bug.**
  Re-examined at the user's request.  The frame differential was replaced as the
  primary gate by a PER-CALL one: `$B028` called directly, 618 cases over the
  sampled world (odd and page-edge X, the bottom-wrap Y band, both facings,
  angry, the pause timer around its two flip points, the anim counter either
  side of the divider) and then 152 more over a BUILT one -- the colour shadow
  and the `$712F` dummy page cleared and poked cell by cell.
  ONE REAL BUG, and the sampled world could not see it: `$AED1` above the HUD
  does not return "no cell", it returns the fixed POINTER `$712F`, and the floor
  probe and the ledge look-ahead DEREFERENCE it while only the wall test reads
  its Z flag.  The engine modelled it as a sentinel meaning "nothing there".
  Those agree only while `$712E-$7131` and `$710F-$7111` have bit 5 clear, which
  is true in round1_48 and FALSE in the boot image (`$712F` = `$E4`) -- the bytes
  are live, so the answer is per-round.  Fixed and gated both ways.
  TWO DECISIONS NEVER REACHED: the ledge -> hop launch (`$B20F`/`$B25E`) fired 0
  times in 618 sampled cases and 61 times in the built world; and the eight-bit
  `INC L`/`DEC L` look-ahead needed a foot cell at low byte `$00`/`$FF` with the
  cell a SIXTEEN-bit walk would read poked to the opposite value.  Also pinned:
  the probe row is Y+`$11` not Y+`$10` (they differ only at ODD Y, which the
  per-slot tail prevents but the hop will not).
  THE HANDLERS ARE NOW MEASURED, NOT READ: each of the eight called directly, 32
  calls, with BIT 1 of the flags both ways -- which is the only way to see that
  type 0 walks unconditionally while types 1 and 5 do not, since the spawner
  clears that bit and no capture of a running round can show it.  The same calls
  read back the whole (type, facing) sprite table, and the five untransliterated
  types are now asserted to be declined OUTRIGHT (write nothing) rather than
  quietly half-run.  NEW FACTS: types 2/3 clear bit 1 on the way through; type 6
  has a SECOND `LD A,R` at `$B008` that flips the facing, not yet modelled;
  types 6/7 patch `$B20D`/`$B25D` (and 7 also `$B088`) and restore them, and 7
  doubles `$B610`/`$B611` with `SLA` and halves them back with `SRL`.
  MUTATION BATTERY 35/35 killed, from 22 of 27 before the audit -- all five
  previous survivors dead.  Two new TRAPS (#39 the `run_until` interrupt
  default, #40 a sampled world that makes right and wrong answers equal).
  bb.test 199 -> 209, kit.test 115/115, selftest 34/34.
- [x] **M7.6-iv DONE -- the BALLISTIC HOP `$B0F7`; the hop hold-out is gone.**
  1296 built-world cases, matched call for call on the first run: 601 still
  flying, 486 landings, 209 hops a wall cancelled, 248 arcs run out, 90 fed
  hesitation draws.  Removing the walker gate's hop hold-out took it from 223
  passes to 250 and 373 enemy moves to 447 -- the 27 held-out slot-frames are
  now covered by the real scenes as well.
  THE READING IN SPEC WAS WRONG IN THREE PLACES, all corrected: both arcs go UP
  then down (not "`$B59D` downward, `$B5BD` upward"); which one is flown is BIT
  7 of `(IY+9)`, and `$B16B CP $11` compares the WHOLE byte, so the small arc
  looks for a landing from its first frame while the big one waits 17; and a
  WALL does not turn the enemy round the way the walker's step does -- it
  CANCELS the hop outright with nothing moved.
  ALSO: `$B192` is a `JP $B09B`, the TOP of the move decision, so an enemy can
  land and wind up again in the same frame (45 of 486 landings did); the anim
  counter is never ticked by a hop; and the arc is the only thing that gives an
  enemy an ODD Y, which is exactly where Y+`$10` and Y+`$11` stop agreeing.
  THE ARCS ARE STATIC TAPE DATA at `$B59D`/`$B5BD`, byte-identical in
  `build/image.bin` and in every saved state.  Shipped as constants and gated
  byte-for-byte against the machine's own 64.
  CORRECTED SAME DAY: this first said they were RELOCATED from `$F59D`/`$F5BD`.
  There is no relocation -- that came from indexing the 64K `build/image.bin` as
  if it began at `$4000`, which reads the byte `$4000` below the one it names
  and returns plausible data instead of an error (TRAPS #41).  The same error
  put `$712F` = `$E4` into TRAPS #40 and SPEC; the truth is the opposite way
  round and more useful: `$712F` is `$00` (so an enemy above the HUD always
  falls) while **`$712E` is `$F0`, bit 5 SET**, so a leftward look-ahead there
  would read a FLOOR.  The engine now CARRIES those 128 bytes at `$70C0` instead
  of leaving the page zeroed and agreeing by luck, gated against the machine.
  Mutation battery 55/55 killed, 0 survivors.  bb.test 209 -> 217.
- [x] **M7.6-vi DONE -- TYPES 2 AND 3: the 2-D flyer `$B26F`.**  2,560 cases
  over FIVE WHOLE WORLDS (empty, solid, and three deterministic sparse patterns)
  plus the 32 direct handler calls, matched call for call.  The walker frame
  gate now holds out ZERO passes -- it was holding out 60 for untransliterated
  types.  `BB_ENEMY_WALK` became `BB_ENEMY_MOVE`, a shape per type, because
  "walk / gate on bit 1 / null" no longer describes what the handlers do.
  A FACT I HAD RECORDED WRONGLY: types 2 and 3 do not "clear bit 1" of the
  flags.  `$B2B0` reads that bit as the **Y DIRECTION**; what I measured was a
  flyer meeting a floor and turning upward.  The multi-agent pass caught it.
  TWO THINGS THE SPARSE WORLDS FOUND that hand-built cells would not:
  (a) the vertical probe's `INC HL` runs off the END of the colour shadow --
  `$FBFF` + 1 = `$FC00` -- and `$FC00-$FCFF` is 256 bytes of `$FF`, every byte
  bit-5 set, so it reads SOLID.  That guard band is what stops a flyer at the
  wrap edge, and the engine had ZEROS there; it is carried now.
  (b) HARNESS TRAP #42: `Harness.call` never restores SP, so each call leaves it
  10 bytes lower.  A 2,560-case sweep walks SP 25,600 bytes down and crosses
  `$4000` at call 2223 -- exactly where the capture went dead, because below
  `$4000` the sentinel writes land in ROM and every later row records
  "nothing happened".  All captures now PIN SP and assert the call ended on a
  sentinel.  Earlier fixtures were re-captured; none had been corrupted, but
  only because SP happened not to pass through anything they read.
  Mutation battery 81/81 killed, plus one EQUIVALENT MUTANT documented rather
  than gated ($B290 writes the whole flags byte; masking to bits 0-1 cannot
  differ, since nothing can change (IY+7) between $B27B and $B290).
  bb.test 220 -> 225.
- [x] **M7.6-vii DONE -- the review pass: one real bug and three unfalsifiable
  boundaries.**  Six adversarial lenses over M7.6-v/vi, each wrong-behaviour
  finding put to two refuters.  It found a REAL BUG I had mis-addressed by one:
  `$B087` is `3E 00` (`LD A,n`) and **`$B088` is its immediate operand** -- the
  same byte `$B09B` reads.  One byte, THREE readers, and the first is invisible
  to a scan for absolute operands.  So a patched FALLER turns to face the player
  (`$B08B-$B09A`), which my comment had described and then attributed to a
  separate "`$B087` patch byte" that does not exist.  Latent only because type 7
  is not wired yet, and type 7 patches it before every call.  Measured, fixed,
  gated.
  THREE BOUNDARIES THE GATE COULD NOT FALSIFY, each the TRAPS #37/#40 shape:
  (a) the flyer tail's MIDDLE band (`$C8..$DB` -> 0) was reached by 0 of 2,560
  rows, so all three of its constants were free -- the sweep's Y topped out
  below it;  (b) the borrow gate offered sub-cell offsets `{0,4,6,7}` only, one
  firing value and three far-away non-firing ones, so `<= 0` and `AND 6` both
  survived;  (c) the `$B088` dimension never met the FALL path -- 0 of 72
  patched rows fell -- which is exactly why the real bug went unnoticed.
  Closed by widening to every offset, adding Y values inside the band, adding a
  `patchfall` group with the player level with the enemy, and -- for the
  horizontal mask, which an EVEN step cannot distinguish and the game only ever
  produces 2 (measured over 600 frames) -- an ODD-step group the game never
  produces but the capture can place.
  Fly cases 2,560 -> 19,360; synth 328 -> 368.  Mutation battery 92/92 killed.
  bb.test 225 -> 226.
- [x] **M7.6-viii DONE -- TYPES 6 AND 7; seven of the eight handlers are done.**
  210 direct calls over FOUR worlds, plus two freshly spawned rounds that
  actually contain these types.  The review pass proved the previous single
  world could not see a single patch install: deleting all five from types 6 and
  7 on the machine gave BYTE-IDENTICAL results there, because the floor ahead
  skipped the ledge block, anim $40 cleared the divider, and the floor underfoot
  meant no fall.  So the capture now builds `floor`, `ledge`, `divider` and
  `fall`, and each one discriminates: on the ledge type 0 hops while 6 and 7
  step; below the divider only 7 skips the wind-up; falling, only 7 re-aims its
  facing at the player.
  THREE THINGS THE ORACLE HAD TO LEARN FIRST:
  (a) trap `$B00A` as well as `$B0D7` -- type 6 draws at `$B008` on every call,
  and every committed type-6 row said `draws: []` while the machine had drawn;
  (b) FORCE the 1-in-128.  Across the whole fixture exactly ONE natural draw was
  `$2A`, and it would vanish if any earlier case moved R.  The capture now pokes
  A at the CP and runs the rest on the machine, so the taken side of BOTH
  hesitations is deliberate;
  (c) capture rounds 40 and 60.  Rounds 4 and 10 contain no type 6 or 7 at all,
  so the frame gate's held-out count would have dropped to zero while the number
  of type-6/7 slot-frames actually diffed stayed there.
  ALSO: the gate now compares the RESTORE half -- the patch bytes and
  `$B610`/`$B611` after the call -- which the slot bytes cannot see, and a STEPS
  pass enters with values the game never produces, which is the only way to show
  that `$AFCA`'s SLA on `$B611` is DEAD (`$B028` overwrites it, so `$B611` exits
  equal to `$B610`'s ENTRY value) and that the SLA/SRL round trip LOSES BIT 7.
  The `$AA60` gate now holds out and counts the 144 frames where the player
  moved, because `$B612`/`$B613` are copied from a player slot this gate does
  not update.
  Mutation battery 104/104 killed, plus two EQUIVALENT MUTANTS documented.
  bb.test 226 -> 234.  ONLY TYPE 4 REMAINS.
- [x] **M7.6-ix DONE -- TYPE 4, and with it ALL EIGHT enemy handlers.**
  1,168 cases over six built worlds, and the handler gate now diffs all 240 of
  its calls with NONE declined -- every type is transliterated.
  Type 4 shares nothing: its own probe, its own horizontal move `$B4AC`, its own
  arcs.  Three things are unlike anything else in the engine:
  (a) the arc CURSOR is `(IY+8)`, the byte every other type uses as a pause
  timer, and `(IY+9)` only picks the table with its bit 7;
  (b) `$B445`'s `CP $10` compares whatever `$B4AC` left in A -- the NEW X after
  a move, the NEW FLAGS after a turn -- so an X below `$10` skips the landing
  test and a turn never can.  Transcribed, not tidied;
  (c) the cursor runs 0..`$20` INCLUSIVE against a 32-byte table, so the last
  airborne frame reads ONE BYTE PAST the end, into `$B5FD` -- P1's KEY TABLE.
  A keyboard byte as a signed Y delta.
  AND THOSE TABLES ARE LIVE STATE.  The tape default is `$DF` (key O); round1_48
  holds `$F7`, the CURSOR keys, because the control-select screen had run; at the
  title they are all zero.  So which controls the player chose changes how a
  type-4 enemy finishes its jump.  The gate seeds the machine's values and
  asserts they DIFFER from the engine's boot defaults, so the coupling is
  recorded rather than accidentally satisfied.  M7.8 will own that table.
  Type 4 is also the ONLY enemy that draws from the `$FE85` LFSR -- the site
  `BB_PRNG_SITES` had listed as "never observed executing" -- and it compares the
  draw against `(IY+4)`, making the anim counter an aiming PROBABILITY.  The gate
  seeds and diffs the LFSR state either side of every handler call, so a model
  that skipped a draw is caught even where the branch did not depend on it.
  FOUR THINGS THE BATTERY FOUND: the wrapper's `$BF` clamp MASKS `$B3F0`'s `$C0`
  wrap in every case reachable through `$AF77` (so the oracle calls `$B3C5`
  directly for it); the launch's cursor reset was invisible while every case
  started at 0; the landing's head-solid arm needed a world poking the
  ARC-DISPLACED row rather than the one under the feet; and two mutation anchors
  had gone ambiguous now that two routines share a probe expression.
  Mutation battery 133/133 killed, no survivors.  bb.test 236 -> 244.
- [x] **M7.6-x DONE -- CAPTURE `$BE5B` and ESCAPE `$B679`; M7.6 is complete.**
  The last of the M7.5 bubble work that needed enemies before it could be
  gated.  278 direct calls: 60 captures, 145 misses, 27 releases, and 32 whole
  `$BE07` travel steps.
  TWO PIECES OF CONTROL FLOW ARE THEMSELVES THE BEHAVIOUR:
  (a) a capture ABANDONS its caller -- `$BEA8` POPs the return address before
  the final `JP`, so the rest of the bubble's update never runs and control
  resurfaces one level out.  With sentinels pushed that is visible as the call
  returning on sentinel INDEX 1, which is how the fixture records whether a
  capture happened at all;
  (b) `$B679` never returns: both its exits `JP` back to `$B66C`, the manager's
  slot-advance.  The oracle brackets it by setting the slot counter to 1 so that
  advance RETs -- otherwise a direct call walks IY on through whatever follows
  the pool.  The first attempt ran 10^6 instructions and died inside `$A447`.
  A THIRD, found by transliterating: **`$BF0A` does not RET** -- it sets the
  cache from the current position and FALLS THROUGH into `$BF16`, so the bubble
  is erased at the position it has just cached.  Two routines that look separate
  in a symbol list are one.
  THE GATE HAD TO LEARN TO SEE PAINT.  Both routines draw, and an escape also
  releases an occupancy marker, and a comparison of the twenty entity bytes can
  see neither -- so every row now carries a checksum of the display and of the
  colour shadow.  That alone was not enough: on a settled screen the erase
  repaints exactly what is already there and the marker's low bits are already
  clear, so both checksums sat still (TRAPS #37 again).  The rows now arrive
  with the display filled with a pattern nothing could repaint to, and with live
  bits in the marker byte -- which is at `$F9F8`, not `$F8F9`, because the
  pointer is little-endian out of +2/+3 and I had it backwards for an hour.
  FOUR MORE GAPS THE BATTERY NAMED: the two axes were never held APART (every
  case had bx == by and ex == ey, so a test comparing Y against the X box was
  indistinguishable); the eight-bit wrap in `v + 15` only shows where the far
  edge wraps too, which needs a bubble at X >= 240; the enemy was always in slot
  2, so the `($AA57) - 2` count was free; and the released enemy's timer and
  state were always already zero, so the clears were invisible.
  Mutation battery 162/162 killed.  bb.test 244 -> 251.
- [x] **M7.7-a DONE -- the ROUND-TRANSITION SETTLER `$B520`, and a shipped bug.**
  A nine-agent pass read the eight M7.7 subsystems; this is the first increment
  its synthesis recommended, and it found the port doing something the machine
  does not.
  THE BUG: `$AA72 JP nz,$B520` leaps over `$AA81 LD IY,$FD80`, and slot 0 is P1
  -- so the divert abandons the PLAYERS along with the enemies.  `web/game.js`
  returned early from `entityUpdatePass()` and then called `updatePlayers()`
  anyway, so for the 88 ticks that open every round the port let the players
  walk while the machine froze them.  MEASURED both ways: with a movement key
  held, P1 walks in a control window at `$B54B` = 0 and does not move one pixel
  in the armed one.
  THE SETTLER itself: `($B54B)` ticks on the ODD ISR only, so `$58` is 88 ticks
  = **176 VIDEO FRAMES** (measured exactly), and round 1 gets `$14`.  Each enemy
  walks up to +2 toward its `$73A6` target, with the second step CONDITIONAL --
  it compares again after the first INC, so an enemy one pixel short moves one.
  Both INCs are eight-bit with no clamp, so an enemy BELOW its target walks up
  through 255.
  THE WORLD HAD TO BE BUILT, three degeneracies deep: an ordinary FALL is also
  `(Y+2)` on the same branch, so a mid-round capture is byte-identical with
  `$B520` deleted; the one steady mid-settle state has every enemy already AT
  its target, where ramp, clamp and do-nothing are the same function; and round
  1's targets are all equal, so stop-at-first-arrival agrees with walk-them-all.
  MY OWN GATE WENT GREEN FOR THE WRONG REASON TWICE, both TRAPS #37:
  (1) a fresh engine has P1 at X = 0, so what the first freeze check detected
  was the per-slot TAIL clamping X up to `$10` -- the player physics never moved
  anybody and the freeze mutation walked straight through;
  (2) an armed window cannot supply a DIRECTION, because the input reader is
  part of the abandoned pass, so replaying its `$FD88` asks the engine's player
  to stand still -- which it would do frozen or not.  The armed replays now take
  the CONTROL's decoded directions, and the pair runs on a LIVE `round1_48`
  state because a bare spawn leaves P1 on a round whose platforms the port does
  not carry.
  New tool `tools/settle.py`, new fixture `build/settle_fixture.json` (42 direct
  calls, 8 windows).  Mutation battery 178/178 killed.  bb.test 251 -> 259.
  KNOWN GAP, counted not hidden: the machine interleaves the players INTO the
  slot loop at 0 and 1, copying `$B612`/`$B613` from the player slot BEFORE each
  slot's handler, so an enemy sees the player's POST-move position.  The port
  runs the players after the pass.  The `$AA60` gate holds out the 144 frames
  where that shows.  Also: the engine's player does not fall on a freshly
  spawned world -- the M7.1 per-round render dependency.
- [x] **M7.7-b DONE -- the LEVEL-CLEAR decision `$8E3A` and the tally `$8EAA`.**
  61 direct calls.  The first oracle in this project that captures a REGISTER:
  the main loop asks `$8D5E CALL $8E3A / $8D61 JR z,$8D09`, so the answer is the
  **Z FLAG**, not a memory cell.  (SPEC had the door as "`$FEC9` wrapping to 0";
  `$FEC9` is the GAME-OVER latch and a different thing, which two agents caught
  independently.)
  THE TALLY counts BIT 7 of `+7` through `RLCA / AND 1`, over `($AA57) - 2`
  slots from `$FD9B`, and publishes the total at `$FECA`.  The sweep uses flag
  values where bit 0 and bit 7 DIFFER (`$C1`, `$80`, `$41`) because the ordinary
  live `$C0` has both clear -- with only `$C0`, "count bit 7" and "count bit 0"
  are the same function.
  THE ADVANCE IS A WINDOW, not a threshold: `$8F29` needs the play timer's high
  byte EXACTLY 1 and its low byte at least `$77`, so a round advances between
  `$0177` and `$01FF` and never again.  MEASURED at every edge: `$0176` no,
  `$0177` yes, `$01FF` yes, `$0277` no.
  THE DJNZ OVERRUNS.  `($AA57) = 2` gives B = 0 and the loop walks 256 slots --
  2,560 bytes past the entity table, counting bit 7 of game code and ROM.
  MEASURED `$FECA` = 86/87/88.  Transcribed (the model is a do-while), but those
  rows are HELD OUT of the differential and counted: the port does not reproduce
  that memory and never will.  Unreachable in play -- `($AA57)` is enemies + 2.
  THE ONE-SHOT CLEANUP `$8ECF` is transliterated whole, including that
  `$8F00 LD IX,$FD80` is DEAD (overwritten by `$8F04` before use), so the ENTITY
  table is untouched and only the twelve BUBBLE slots are wiped.
  HELD OUT AND COUNTED: the exactly-one-alive path calls `$90A9`, the anger pass
  (increment f, and it walks with a stride of TWELVE); a non-zero `$FED1` hands
  the answer to `$8F36`, the level-skip item's own routine (increment d).
  New tool `tools/clear.py`, new fixture `build/clear_fixture.json`.
  Mutation battery 196/196 killed, plus two EQUIVALENT MUTANTS documented: the
  `DEC A / RET nz` at `$8EC7` cannot be told from `n > 1` because n = 0 has
  already returned, and `$8ECF`'s fall-through into the countdown cannot be told
  from a plain return because `$8ECF` zeroes the timer first -- true of the
  machine, not just of the model.  bb.test 259 -> 264.
- [x] **M7.7-c DONE -- the ROUND ADVANCE `$97F8` and the `$9AC1` reset.**
  53 direct calls, bracketed by the ADDRESS reached rather than by sentinels:
  there are no CALLs and no HALT before `$9858`, so the stop IS the bracket.
  `($FEC7)` is the LOOKAHEAD -- the round AFTER the one just entered -- and it is
  what the milestone tests.  SPEC said the extra life arrives "advancing INTO
  round 21/41/61"; `$9817` stores the lookahead and `$981A` tests it, so
  `($8609)` is 20/40/60 at that moment.  Both describe one fact, and the pass
  had already settled it.
  THE WARP, measured as a truth table rather than described: at a milestone both
  players gain a life, and then `$9830` takes the FIRST player whose `+$5A`
  bit 7 is CLEAR -- P1 before P2 -- and sets `($8609)` = `$51`, round 81, if
  THAT player is alive.  With both bits set it never fires.  All four state
  combinations, each with the chosen player alive and dead.
  PAST ROUND 81 the round becomes the lookahead, and a lookahead that would
  itself be 82 is DRAWN: `$9811 LD A,R / AND $1F / ADD $1E`, giving 30..61.
  That is `BB_RNG_SITES`' RETURN_ROUND, which had been carried since M7.5 marked
  "TRANSCRIBED, never observed executing".  It executes here, and the draws are
  trapped, recorded and fed.
  THE NINETEEN bytes the `$9AC1` table names are zeroed -- seeded to `$FF` in the
  fixture, because with them already zero "zero them" and "leave them alone"
  are the same function.  The table is walked out of the byte image at its real
  address rather than hard-coded, so a wrong entry fails a gate.  Two of the
  nineteen are `$FEC4` and `$FEC5`, BOTH ISR pass gates, so the whole level
  build runs with both halves of the interrupt dark.
  MY FIRST SWEEP GOT THE MILESTONE ROUND WRONG -- it entered at 20 rather than
  19, so the lookahead was 22 and all sixteen truth-table rows answered "no
  warp".  A perfectly settled-looking table testing nothing.
  New tool `tools/advance.py`, new fixture `build/advance_fixture.json`.
  Mutation battery 219/219 killed.  bb.test 264 -> 270.
- [x] **M7.7-I1 DONE -- the ITEM BLOCK, the round build `$8C5E`, and the two-pass walk `$8689`.**
  First increment off the (d)/(e) reading pass (docs/M7.7-ITEMS-READING.md).
  THE BLOCK IS ONE 64-BYTE ALLOCATION, `$9603`-`$9642` = 32 slots x 2 bytes.
  Slot 0 is the SINGLE power-up slot; slots 1..31 are the fruit / points table.
  Reading the base as `$9605` is what made this document assert, in two separate
  sections, both "all collectibles live in `$9605`" and "power-ups are NOT in
  `$9605`" -- one allocation, two passes, and each half-right.
    byte0 = (X & $F0) | (type & $0F)   -- FOUR bits of type, reaching all 16
    byte1 = (Y & $F8) | (phase & 7)    -- byte0 === 0 is the emptiness test
  The oracle is `tools/itemscan.py`: `$8C5E` over all 81 rounds, and `$8689`
  captured as a VISIT ORDER by trapping `$86A9` with `$86B1` poked to RET, so the
  traversal runs pure -- no unpack, no collision, no erase.
  THREE THINGS HERE ARE INVISIBLE UNLESS THE WORLD IS BUILT FOR THEM, and each
  got its own named check: the clear is 64 bytes and not 62 (identical unless the
  block is dirty, so every byte is seeded to `$FF`); the walk is 31 entries and
  not 32 (identical over a zeroed table, so `$9643`/`$9644` are seeded `$FF` and
  must stay untouched); and THE ODD-ROUND SWAP is invisible on every even round
  with the one live dump being round 80, so all 81 rounds are swept with round 81
  -- odd, but exempted by `$8CA5 CP $51 / RET z` BEFORE the swap -- as the control.
  TWO DEPENDENCIES WORTH NAMING. `$8C61 LD B,$40` is consumed by `$AA49`'s DJNZ,
  so B is ZERO at `$8C77` and the CPIR scans `$860F` with BC = 14 exactly; drop
  the clear's counter and it scans `$4000` bytes. And `$8CAA LD ($8CAE),HL` with
  H = the power-up X and L = the points X: the swap is just the little-endian
  store landing L first.
  A GATE CAUGHT SOMETHING NOBODY WAS LOOKING FOR -- see TRAPS #43. The build
  disagreed with the machine on exactly ONE of 81 rounds, and the cause was that
  `build/image.bin` is a LIVE ROUND-80 DUMP, not the tape image: round 20's item
  byte at `$FFA3` is `$8F` there and `$95` on the tape. An audit of every table
  this engine carries found exactly two runtime-mutated bytes -- that one, and
  `$8A76`, the UMBRELLA LOCK (tape `$2A`, dump `$06`), which independently
  confirms the reading pass's claim that the umbrella spawns at most once per
  game. Static tables now come from `build/image_tape.bin`, the R3 tape rebuild.
  The `$872C` row started out comparing carried-over state, since the build never
  writes it; it is now seeded to `$FF` and asserts the build LEAVES IT ALONE.
  ONE MUTATION SURVIVED the first battery -- "the power-up slot uses the same
  emptiness test as byte1" -- and the SCENARIO was at fault, not the gate: in
  every walk case slot 0's byte0 and byte1 were zero or non-zero together, so
  "empty means byte0 == 0" and "empty means byte1 == 0" agreed everywhere. The
  case that separates them is not contrived, it is what `$8C5E` leaves after
  EVERY round build -- byte0 cleared, the staged Y sitting in `$9604` -- and what
  a collected item leaves behind. Three such blocks added; the mutation dies.
  New tool `tools/itemscan.py`, new fixture `build/itemscan_fixture.json`.
  Mutation battery 254/254 killed. bb.test 270 -> 281.
- [x] **M7.7-I2 DONE -- the item UNPACK `$8779`, the INK `$8728`, the DRAW `$A2C2`/`$A2D5`.**
  ONE 32-BYTE INK TABLE WITH AN OFFSET, NOT TWO BANKS. `$8728` does
  `LD H,($872C) / DEC H / JR z`, so a pass flag of exactly 1 -- the POWER-UP
  pass -- indexes `$861D` directly and everything else adds `$10` first. The
  FRUIT pass therefore reads the HIGH half, which is the opposite way round to
  what SPEC said. THE POLARITY IS INVISIBLE FOR TYPES 0, 1 AND 8, where the two
  halves hold the same value: a gate driven by an ordinary banana can have the
  selection completely backwards and pass. Types 5, 7 and 10 are what make it
  observable, and every type is run through BOTH passes as a control pair.
  TWO SPRITE FORMULAS, ONE TAIL: `$87A5` looks the type up in `$8639` and JUMPS
  INTO the fruit path at `$878C`, so the passes share the `*32` and differ only
  in the index -- `type + 10` against `$8639[type]`. The three `ADD A,A` happen
  in EIGHT-BIT A before the last two doublings move into HL.
  THE BLIT IS OPAQUE. `$A2C2` NOPs the two `OR (HL)` at `$A307`/`$A30C`, calls
  the 16x16 unmasked `$A2D5`, and restores `$B6`. Over the empty sky an item
  normally sits on, opaque and OR are the SAME FUNCTION -- so every case is
  captured twice, on a black destination and a white one, and the two must be
  byte-identical. The oracle also asserts both patch bytes come back as `$B6`:
  a blit that died in between would leave every later OR-blit in the whole game
  silently opaque, and that would surface three increments away, not here.
  THE INK GOES TO THE REAL ATTRIBUTE FILE. `$8749 CALL $AEDC` returns a
  COLOUR-SHADOW address and `$874D SUB $A0` turns `$F8xx` into `$58xx`. The draw
  never touches the shadow at all, which corrects SPEC's "stamps a 2x2 collision
  marker into the shadow buffer". Cells are seeded `$FF`, so the result
  `$38 | ink` proves in ONE byte that the paper survived, that BRIGHT and FLASH
  were cleared, and that a write happened.
  AND THE STAMP SPILLS. An item on the bottom row (Y=`$B8`) puts two of its four
  cells at `$5B1C`/`$5B1D` -- PAST `$5AFF`, outside the attribute file, in the
  page the game uses as data. Found because the gate failed there.
  THREE MISTAKES OF MY OWN, all in the ORACLE rather than the engine, and all of
  the same family -- being wrong in the same way twice reads as agreement:
    (a) I seeded the destination at `0x4000 + (y&$F8)*4 + (y&7)<<8`, which is the
        Spectrum's address only for the TOP THIRD. For Y=`$48` and Y=`$B8` it
        seeded bytes the blit never touches, so the black/white control compared
        two identical UNSEEDED screens and agreed 96 times out of 96 while
        proving nothing. Fixed by filling the whole display, which cannot miss.
    (b) I armed `$8728` without setting IY. The blitter reads the draw record
        THROUGH IY -- `LD A,(IY+6)` for the row -- and IY is loaded by `$868D`
        inside the WALK, not by `$8728`. So every case blitted to `$4041`
        regardless of Y, and the two runs still agreed with each other.
    (c) the attribute seeding stopped at `$5B00`, so for the bottom row the
        engine and the machine disagreed about bytes NEITHER of them wrote.
  AND THE BATTERY FOUND MORE. Six mutations survived the first full run.
  THREE WERE REAL COVERAGE GAPS:
    - "a blit into ROM is stored rather than dropped" and "the shadow cell keeps
      the $AED1 dummy guard the item path does NOT have" both survived because
      every draw case sat at Y >= $18, and both behaviours live only ABOVE that.
      I had listed Y < 16 in this increment's own unreachable list and then not
      written the case -- the list is worth only what you act on. Positions
      Y=$00 and Y=$10 added. The Y=$00 row earns its place twice over: the
      machine drops all 32 blit bytes into ROM, so the sprite VANISHES while its
      four attribute cells are still stamped. The ROM one ALSO needed a new
      assertion, because the fixture records only writes inside $4000-$6000 --
      the engine could store below $4000 and no check would ever look.
      AND THE FIRST VERSION OF THAT ASSERTION WAS ITSELF WRONG: it snapshotted
      the sub-$4000 region AFTER the call and compared the result with itself,
      so the mutation survived a SECOND battery. The working form asserts the
      region is still all zero, which it must be -- reset() zeroes the world and
      nothing in the engine legitimately writes into ROM.
    - "the pass test is non-zero rather than exactly 1": $8728 reads the flag
      with DEC H / JR z (exactly 1) while $8779 reads it with OR A / JR nz
      (anything non-zero). Only a flag of 2 separates them -- POWER-UP sprite
      with FRUIT ink -- and the walk never produces one, so it had to be built.
  FOUR WERE TRUE EQUIVALENT MUTANTS, each provable from the data rather than
  argued, documented and removed from the battery:
    - `(b >> 1) & $70` vs `& $F0`: a byte shifted right is at most $7F, so bit 7
      is always clear and the masks agree on every input.
    - bit 6 vs bit 7 for the random-ink test: index 10 is the ONLY entry with
      either bit set, and it is $FF, which has both.
    - the blit's column add 8-bit vs 16-bit: the row table's widest low byte is
      $E0 and the column is even and at most 30, so 224+30 = 254 never carries.
    - the blit's INC H 8-bit vs 16-bit: the row table's high bytes top out at
      $50 and the band is 8 rows, so $57 is the worst case.
    - and `(v >> 3) & $1F` vs `& $3F` in the cell divide: a byte shifted right by
      three never exceeds 31.
  New tools `tools/itemdraw.py` and `tools/extract_item_sprites.py`, new fixture
  `build/itemdraw_fixture.json`, new asset `build/item_sprites.json`.
  Mutation battery 287/287 killed. bb.test 281 -> 293.
- [x] **M7.7-I3 DONE -- the OVERLAP BOX `$930A`/`$9312` and the COLLECT `$87B2`.**
  THE PRIMARY ORACLE IS EXHAUSTIVE. `$930A` and `$9312` are pure predicates of
  three bytes, so instead of sampling them through gameplay they are called
  directly over ALL 256x256 item-versus-player coordinate pairs per axis --
  131,072 rows -- and the CARRY FLAG is captured. That matters: an item's X is
  always a multiple of 16 and the player moves in coarse steps, so a +-15 box
  and a +-16 box, and `<` against `<=` on the far edge, agree at nearly every
  position the game can produce. SPEC's one recorded datum (player X=50 taking
  a fruit at X=64) passes under all four readings.
  THE BOX IS `px-15 .. px+14` -- near edge INCLUSIVE, far edge EXCLUSIVE -- and
  BOTH ADDS ARE EIGHT BIT, so it SHRINKS at the low edge (px=1 gives 16 hits,
  not 30) and VANISHES ENTIRELY for px >= 241: a player that far right can
  collect nothing at all. No sampled position would have found that.
  The two axes produce BYTE-IDENTICAL bitmaps, so they are one routine on two
  register pairs -- and the engine already carried it as `boxOverlap()`, written
  for the bubble capture, which shares the very same `$930A` on the machine.
  THE MASK SPLIT, NOW QUANTIFIED: `$877C` takes the draw X with `AND $F0`, but
  `$87C9` writes `byte0 & $F8` back into the table for the duration of the call
  and restores it after (the original rides in A' across the CALL on the
  `EX AF,AF'` pair). `$F8` keeps BIT 3, part of the type nibble, as an X bit.
  MEASURED: type 1 and type 9 DRAW at the same X=64, but type 1 collects for
  player X 50..78 and type 9 for 58..86 -- EIGHT PIXELS RIGHT.
  TWO STATES UNREACHABLE IN PLAY, BOTH BUILT: `$87B2`'s first byte is LIVE STATE
  (`$00` a NOP collects, `$C9` collects nothing; written by `$956D` and `$94DB`)
  -- which is the answer to the old note about a player standing on a fruit
  while nothing happened. And BIT 6 of `(IX+$5A)` locks collection out entirely,
  with no `RES 6` anywhere in the image.
  A COLLECT CLEARS byte0 ONLY: byte1 survives, which is what lets `$89FB` refill
  a slot by writing byte0 alone. Measured across all 93 collects.
  THE ORDERING HAD TO BE BUILT TWICE OVER. `$86B5` tests P2 before P1, but in a
  one-player game P2's +7 bit 7 is clear and `$87B7` returns before anything
  happens, so the ordering is invisible. Built with both players live over one
  fruit: P2 WINS, counter 1 to 0. Then the battery showed that `$86BD`'s
  "abandon the entry once taken" guard was STILL ungated, because an emptied
  slot has byte0 = 0 and byte0 = 0 only falls inside the box when the player is
  near X=0 -- at mid-screen the guard is free. Rebuilt at the left edge, where
  without it P1 would collect the same slot a second time.
  New tool `tools/itembox.py`, new fixture `build/itembox_fixture.json`.
  Mutation battery 315/315 killed. bb.test 293 -> 305.
- [x] **M7.7-I4 DONE -- the SCORE AWARD `$80FA`, the clear `$8161`, the HUD `$816B`.**
  THREE four-byte packed-BCD fields, MSB at the high address: HIGH `$FFE1-4`,
  P1 `$FFE5-8`, P2 `$FFE9-C`, base = `$FFE1 + 4*player`, and the index is 1 or 2
  -- NEVER 0, because slot 0 IS the high score. Every award row pins HIGH to
  99999999 so the copy cannot fire and asserts that only the collecting player's
  own four bytes move: that is precisely the check that would have caught the
  "P1 = `$FFE4`-`$FFE7`, TRIPLY confirmed" claim this document carried for three
  sessions -- a four-byte window one byte early, straddling the high-score MSB,
  which is also where the phantom +40000/+80000 awards came from.
  MEASURED: the add is FOUR bytes with the carry reaching the top one
  (12999999 + 1 -> 13000000); the carry OUT of the fourth DAA is DISCARDED, so
  the score wraps mod 100,000,000 (99999999 + 1 -> 00000000); the MSB-first
  compare has three outcomes (copy, abandon, and all-four-equal falling through
  into a copy that changes nothing); an INACTIVE player has its pending
  DISCARDED; and `A >= 3` returns WITHOUT clearing, so the pending survives.
  `$816B` IS NOT COSMETIC, and finding that out cost a rebuild. Its loop ends
  four bytes below where it started, so it RETURNS `HL = base - 1`, and `$8129`'s
  `ADD HL,DE` relies on exactly that to aim the compare at the player's MSB.
  The first version of the oracle poked `$816B` to RET to "isolate the
  arithmetic"; that left HL four bytes high, the compare read the PENDING FIELD,
  and the copy silently stopped firing. The award and the renderer are one
  mechanism and are captured together.
  LEADING-ZERO SUPPRESSION is a self-modified OPCODE at `$81BB`: `$C8` (RET Z)
  while armed, rewritten to `$00` (NOP) by the first non-zero digit. Visible in
  the cell count -- a score of 10 draws 16 cells, 1000 draws 32.
  THE HUD FONT IS A DECLARED DEPARTURE. `$8042` sources its glyphs from the 48K
  ROM charset at `$3C00`, which this project does not ship or transcribe, so the
  port draws ten digits made by `tools/make_digits.py` -- which REFUSES to emit
  unless every glyph differs from the ROM's (62 of 80 bytes do). M8's frame
  differential must exempt the score cells. The fixture records the renderer's
  screen ADDRESSES and a checksum, never pixel values, so no ROM byte enters the
  repository.
  THE BATTERY FOUND WHAT THE SUITE COULD NOT. Four mutations of `itemAward`
  survived because NOTHING IN THE SUITE EVER CALLED IT: I3 gated `itemCollide`'s
  table effects and stopped; I4 gated `scoreAward` directly. The seam between
  them was untested. Adding `$87F9` rows (all 16 types through both players)
  closed it -- and the first thing they exposed was that THE ENGINE NEVER SEEDED
  `$8649` AT ALL. The ink and remap tables went in during I2 and the point values
  simply did not. The port would have awarded nothing for every item.
  A THIRD INSTANCE OF I3's PATTERN: "the copy is three bytes" survived because in
  every row built, the player's low byte and HIGH's low byte happened to match,
  so copying three and copying four were the same function. A row where all four
  differ kills it.
  TWO EQUIVALENT MUTANTS, documented and removed: the copy written ascending from
  `$FFE1` addresses the identical byte pairs as descending from `$FFE4`; and the
  screen pointer's eight-bit `INC L` never wraps, because all three HUD addresses
  (`$402B`, `$401F`, `$4034`) stay clear of a page boundary across eight digits.
  PROVED EQUIVALENT RATHER THAN TESTED: the carry into the FIRST ADC. `$8115`
  sums `$FFE1 + 4*A` with A <= 2, so it maxes at `$FFE9` and cannot carry out of
  sixteen bits -- no measurement can distinguish ADD from ADC there.
  TWO MISTAKES OF MINE WORTH RECORDING: I named the fixture
  `build/score_fixture.json`, which was an EXISTING committed M7 point-table
  gate, and clobbered it (restored from git; mine is now `scoreaward_fixture`).
  And I edited `web/game.js` while the mutation battery was running, which is why
  the suite returned 313, then 312, then 311 on the SAME artifact and why a font
  edit vanished -- the battery restores its own snapshot after every mutation.
  New tools `tools/scoreaward.py` and `tools/make_digits.py`, new fixture
  `build/scoreaward_fixture.json`, new asset `build/digits.json`.
  Mutation battery 351/351 killed. bb.test 305 -> 315.
- [x] **M7.7-I5 DONE -- the LIFETIME CLOCK `$8669`/`$86CC`, the EXPIRY, the ERASE `$86E6`/`$A314`.**
  THE DELETE CONDITION, measured over all eight phases:
    `0->1  1->2  2->3  3->DEAD  4->5  5->6  6->7  7->0`
  Deletion fires when the INCREMENTED phase is 4, so ONLY FROM PHASE 3. A
  phase-4 entry steps to 5 and SURVIVES. That is load-bearing: the
  round-transition row writer seeds phase 4 into 160 entries, and a model that
  deleted on a STORED 4 would wipe every one of them on the first tick. The two
  models agree on a phase-3 entry and differ only on a phase-4 one, which is why
  phase 4 had to be swept explicitly.
  `$8669` IS AN EDGE DETECTOR, not a comparison. `$867F CP n` has `$8680` as its
  OWN OPERAND and `$8681` writes back the byte it just compared. With `$8DB6`
  FROZEN and three back-to-back calls the counter ticks on the first and not the
  second or third; in a live frame the timer always moves, so the early-out is
  never taken and the mechanism cannot be seen at all.
  A WATER-CARRIED PLAYER FREEZES THE ITEM CLOCK ENTIRELY -- `$8670`/`$8676` jump
  past both the gate AND the INC. Both bytes matter (`+$5A` for P1, `+$64` for
  P2) and the bypass still RUNS THE WALK.
  THE ERASE REPAINTS WHAT IS USUALLY ALREADY THERE (TRAPS #40): with the four
  attributes seeded `$FF`, the two round colours set DIFFERENT, and shadow bit 5
  set in exactly two of four cells, one call returns `$46 $66 $66 $46` and both
  branches of `$876C` run at once. A non-zero `$FECE` jumps STRAIGHT to the pixel
  restore, leaving the attributes untouched.
  `$A314` is three bands of `(8 - Y&7)`, `8` and `Y&7` rows. Items always have
  `Y&7 == 0`, so BAND 3 IS DEAD CODE for collectibles.
  AN ITEM ON THE BOTTOM ROW loses its lower half: the second band reads `$FD30`,
  the entry PAST the 24-entry table, which is `$0000`, so it addresses page 0 and
  the machine drops the writes -- 20 bytes against a mid-screen item's 36.
  ELEVEN MUTATIONS SURVIVED THE FIRST BATTERY. Seven were coverage gaps, and
  every one was a case I had HALF built: P1's carry byte set but never P2's; an
  EMPTY table, so "bypass to the walk" and "bypass and return" agreed; counter
  values `$00`/`$01`/`$FF`, all of which agree between the real `$86CF` mask and
  a hard-coded `$07` (only `$10` separates them); no check that the expiry FALLS
  THROUGH into the erase; no assertion that nothing is written below `$4000`; and
  nothing exercising `$86B1`'s ORDER, since "age then draw" and "draw without
  ageing" leave an identical table and only the SCREEN separates them.
  FOUR WERE GENUINELY EQUIVALENT, all dead because items always have `Y&7 == 0`
  or because the operands are bounded short of a wrap: band 3 runs zero rows
  either way, the first band's `8 - shift` is just 8, and neither the row step
  nor the column add can carry.
  THE LAST ONE NEEDED THE ENGINE AND THE MACHINE TREATED DIFFERENTLY, and I got
  it wrong twice first. "A restore into ROM is stored rather than dropped"
  survived because the bottom band's SOURCE is `$A0xx` -- on the machine that is
  the game's own CODE and so naturally non-zero, which makes dropping the write
  observable; the engine ships no code there, reads zero, and "drop the write"
  and "write a zero" collapse into one function. My first fix seeded that shadow
  IN THE ORACLE, which CORRUPTED THE MACHINE'S CODE and moved the write count
  from 20 to 36 -- altering the thing being measured. The fix belongs on the
  engine side only.
  New tool `tools/itemlife.py`, new fixture `build/itemlife_fixture.json`.
  Mutation battery 390/390 killed. bb.test 315 -> 330.
- [x] **M7.7-I6 DONE -- the POWER-UP DISPATCH `$8839` and all SIXTEEN handlers.**
  THE ORACLE LET THE MACHINE ENUMERATE THE EFFECTS rather than my reading
  sixteen routines and hoping: each handler called directly, the jump table read
  OUT OF THE IMAGE, and every write in `$4000`-`$FFFF` logged. That is why this
  increment was called SOLO -- the measurement is cheap and complete, so there
  was no belief of mine left for an independent reader to attack. The engine
  matched all 64 rows first time.
  TWO REFINEMENTS THE CAPTURE ITSELF FORCED. The `$96Cx` writes were STACK
  TRAFFIC -- a handler's own PUSHes recorded as if they were power-up behaviour
  -- so the stack window is excluded. And neither seed alone makes every write
  visible: a `SET n,(HL)` over `$FF` changes nothing and type 12's
  `(IX+$62) := 0` over `$00` changes nothing, so every handler is captured at
  BOTH `$FF` and `$00`, the same device as I2's black-and-white destination.
  WHAT THE MACHINE CONFIRMED:
  - TYPE 2 IS A GENUINE FALL-THROUGH: `$88EC` CALLs `$88F4` and then runs into
    `$88EF`, so it does BOTH of what types 1 and 0 do -- exactly two writes,
    where type 0 moves only `+$5F` and type 1 only `+$5E`.
  - THE DIAMOND PIN `$88E0`, shared by 7, 8 and 9, writes 9 to `$8B9F` AND
    ZEROES `$8BA0` -- which is the `INC A` OPCODE of the fruit-type generator --
    and widens the mask at `$8BA2` to `$FF`. The generator is pinned to a
    constant 9, so EVERY LATER CORPSE IN THE ROUND DROPS A DIAMOND. All thirteen
    in-game dumps hold `$8BA0 = $3C`, so this patched state has never been
    captured; it exists only after one of these handlers runs.
  - TYPES 10 AND 13 WRITE BOTH PLAYERS -- `$8859` by reloading IX, `$889C` by
    absolute address -- while the IX-relative handlers (0, 1, 2, 9, 14) all
    differ between P1 and P2. Invisible in a one-player game, where only P1 ever
    collects, so every handler is run with IX = P1 AND IX = P2.
  - TYPE 13 IS I3's COLLECT LOCK, arriving by absolute address at `$FDDA` and
    `$FDE4`; there is no `RES 6` anywhere in the image.
  - TYPE 15 WRITES NOTHING, so "correct" and "not implemented" are
    indistinguishable at collect; its whole effect is downstream in `$BD56`'s
    `CP 15`.
  - TYPES 4 AND 5 SHARE ONE HANDLER and are genuinely identical here. No gate
    can separate them at this level -- recorded as a fact rather than papered
    over; they differ only in `$8649` and `$861D`, which I2 and I4 cover.
  - TYPE 6 DOES NOT RETURN (`$88C0 JP $A110`) and is the only handler drawing
    from the `$FE85` LFSR, folding {0,1,2,3} onto {3,3,5,7} because the SUB's
    borrow collapses draw 0 onto draw 1.
  TWO OF MY OWN ERRORS, both caught rather than shipped: the fixture first
  recorded the LFSR state as a mismatch because the engine's generator starts
  from its own seed -- the oracle now records `$FE86`/`$FE87` BEFORE the call so
  the draw is reproducible. And a named check asserted the gated struct stayed
  all-`$FF` when `$FDE2` is `$5A` from my own seed list; it now compares the two
  flag states against each other rather than against a literal.
  OUT OF SCOPE AND NAMED: type 12's body past the two ISR gates (it calls `$A36C`
  and `$8E0A` and self-modifies `$896D`) belongs with the round build, (h).
  TWO MUTATIONS SURVIVED, and both exposed a structural weakness rather than a
  detail. "Type 15 is not a bare RET" survived because the gate compared ONLY
  the addresses the machine WROTE -- type 15's write list is empty, so the loop
  ran zero times and a handler that does nothing was indistinguishable from one
  doing anything at all. The fix rebuilds the machine's expected post-state
  (seed plus writes) and compares EVERY SEEDED BYTE, so a write the engine
  invents is caught as surely as one it omits. That is the "compare the
  addresses a routine did NOT write" countermeasure established several
  increments ago and then not applied here.
  "The recorder always writes P1" survived because the oracle calls `$8839[t]`
  DIRECTLY, so `$8829 LD (IX+$61),A` never runs in a handler row, and the only
  rows going through `$8822` used P1 alone -- with P1 the sole collector,
  "write (IX+$61)" and "always write $FDE1" are the same function. Now gated
  with both players.
  Fixing those surfaced two more of mine: the gate entered through
  `itemPowerUp()` where the oracle enters at the handler, adding a recorder
  write the machine never made; and the flag comparison tripped over `$FDE2`,
  which the oracle's own SEED list sets to `$5A` -- the SECOND time in this
  increment that same seeded byte was misread as a handler effect.
  New tool `tools/puhandlers.py`, new fixture `build/puhandlers_fixture.json`.
  Mutation battery 429/429 killed. bb.test 330 -> 341.
- [x] **M7.7-I7 DONE -- the per-round SPAWN FLOW `$89CB` and both TYPE decisions.**
  **ROUND 77 IS SETTLED, not LIKELY.** The reading pass flagged a plausible CPIR
  off-by-one and could not resolve it; one forced draw does. `$8A28` runs with
  BC = 16 and decrements on the MATCHING comparison too, so a match on the
  SIXTEENTH byte leaves `C = 0` -- which the `INC C / DEC C / JR z` test cannot
  tell from exhaustion. The sixteenth byte of `$8A62` is 77. MEASURED: the other
  fifteen listed rounds take the narrow {3,3,4,5} draw and ROUND 77 TAKES THE
  WIDE ONE. It is listed and can never receive its listing.
  THE TECHNIQUE THAT MADE IT TESTABLE: the two `LD A,R` sites were REPLACED, not
  sampled. `$8A2E` and `$8A38` are both `ED 5F`, so they are patched in place to
  `3E nn` -- two bytes for two, nothing moves -- and nn swept over all 256, then
  restored. That is a DECLARED SUBSTITUTE recorded in the fixture, not a
  measurement of R, and it is what turned `$8A2E` from docs/RNG.md's
  "TRANSCRIBED, never observed executing" into a branch with 360 rows through it.
  Because no value distinguishes the two patched sites, the fixture also records
  WHICH site fired, by PC trap -- the engine's feed queue matches on site.
  THE TIMER TESTS ARE EQUALITIES, NOT THRESHOLDS: `$8DB7 == 4` spawns the
  power-up and `== 2` the points item. A ">=" model passes at `$0400` and fails
  at `$0500`, and in any captured round the timer is long past both with the
  latches already set, so the routine is a no-op for a correct model and a
  broken one alike. Each spawn has its own one-shot bit in `$8CB0`, and a round
  of EXACTLY 80 clears both before dispatching -- which is why a round-80
  capture can never show the gate working.
  THE UMBRELLA LOCK NEEDED A THREE-CALL TRANSITION. With `$8A76` already `$06`,
  "the lock exists" and "6 is simply never drawn" are identical; with it at
  `$2A`, "present but unfired" and "no lock at all" are identical. Measured: the
  first forced draw of 6 yields an umbrella and writes 6 into the fifth
  exclusion slot; every later one is filtered to type 0. ONE UMBRELLA PER GAME,
  armed at SPAWN.
  THE POINTS MAP is 12 - (`$9AE9`), with >= 12 giving 0 and 0 giving 11 -- so
  **0 AND 1 both give 11**, because 12 - 0 is 12 and the `CP H / DEC A` pair
  folds it down.
  THREE MUTATIONS SURVIVED. Two were EQUIVALENT for instructive reasons:
  "the listed-round scan covers 15 entries" is equivalent BECAUSE OF THIS
  INCREMENT'S OWN FINDING -- entry 15 is round 77, which the `C = 0` off-by-one
  makes unreachable, so fifteen and sixteen entries give identical results for
  every round and the sixteenth entry is functionally dead. And "the `>= 12` test
  is `> 12`" is equivalent because the branches agree at the boundary: `l = 12`
  gives 0 either way, since 12 - 12 = 0 is exactly what the `>=` branch produces.
  The third was a real gap -- every row left `$7E0E` at 0, where "CP 2", "CP 1"
  and no test at all are the same function. Swept: a drawn 7 becomes type 14
  ONLY when `$7E0E` is exactly 2, one row in twelve.
  New tool `tools/puspawn.py`, new fixture `build/puspawn_fixture.json`.
  Mutation battery 465/465 killed. bb.test 341 -> 355.
- [x] **M7.7-I8 DONE -- the CORPSE BIRTH `$8BC2` and FLIGHT `$8A78`-`$8B4D`.**
  THREE RNG USES FROM TWO DRAWS, confirmed on all sixteen seeds. `$8BD7` and
  `$8BDF` give the low and high nibbles of the packed `(+8)` -- but the X
  DIRECTION is bit 0 of the GENERATOR'S OWN H after the second draw, taken by
  `RR H`. That is not a draw at all. The oracle recomputes `$FE85` twice in
  Python and it agrees with the machine on every seed, with both directions
  occurring, so a model that draws a third time or hard-codes the bit fails
  about half of them.
  THE MACHINE CORRECTED MY TEST SETUP. `$8B2A ADD A,(IY+5)` is EIGHT BIT, so a
  leftward step that would pass zero WRAPS HIGH and takes the RIGHT clamp: X=20
  stepping 24 left gives **224, not 16** -- a corpse walking off the left edge
  reappears clamped at the right. Reaching the genuine left clamp needs a step
  that lands in range (X=30 -> 16). Both are cases now, and every clamp calls
  `$8B45`, which XORs bit 0 of `(+7)`: the corpse BOUNCES rather than sticking.
  AND MY ODD-FRAME ASSERTION WAS OVERSTATED -- the engine was right. Odd frames
  DO change the cache, because `$8A7D CALL $BF0A` sets `(+2)`/`(+3)` on EVERY
  frame, before the parity test. "Changes nothing" was false; "changes nothing
  except the cache, and the cache always equals the current position" is both
  true and a stronger claim.
  `$BF0A` HAS NO RET: it sets the cache and FALLS THROUGH into `$BF16`, which
  saves `(+7)`, forces it to `$C0` so the master's own gates cannot refuse a
  bit-3 slot, erases, and restores. Every corpse frame begins by rubbing itself
  out where it stands.
  THE BOB WRAPS ASYMMETRICALLY: rising past `$C0` gives ZERO (not `$C0`, and not
  `$B8`); falling past 0 gives `$B8`. Neither is reachable unless a corpse
  happens to cross, so both are forced.
  AND THE DESCEND->FALL FRAME RETURNS AT `$8AF7` WITHOUT DRAWING -- one frame per
  corpse, invisible unless the display writes are counted. Gated by requiring it
  to write strictly fewer bytes than the frame before, and to zero `(+4)` and
  align X to `$F0`.
  The flight matches FRAME FOR FRAME over 245 frames of 8 runs, and every
  divergence beyond that begins exactly one frame after each run enters the
  fall -- which is I9.
  FIVE MUTATIONS SURVIVED, and the split matters.
  ONE WAS UNREACHABLE: the right clamp at `$DF` against `$E0`. X starts aligned
  to `$F8`, every step is `hi * 8`, and both clamps are multiples of 8, so X is
  ALWAYS a multiple of 8 and `$DF` is odd. Removed as equivalent.
  ONE WAS A COVERAGE GAP: the birth coordinates were `$55`/`$66`, where
  `AND $F8` and `AND $F0` give the SAME answer, so the mask was untestable.
  Bit 3 is now set in both (`$5C`/`$6E`).
  **THE OTHER THREE EXPOSED A MODELLING GAP AND ARE DEFERRED, NOT DELETED.**
  They are all display-only effects, so I added a play-area checksum -- and it
  disagreed with the machine on the FIRST flight frame. MEASURED: the machine
  changes 48 display bytes starting at `$488E` (the erase at Y=96); this engine
  changes 56 starting at `$486E` (Y=88). The cause is that **the corpse draws
  itself through `$A26F`, which is NOT the entity master's draw half that M7.3b
  gated** -- it is a separate entry point, not yet transliterated -- and
  `$BF16`'s erase patches TWO bytes (`$A5D9` AND `$A480`) where the engine's
  `entityEraseHalf` models only one.
  So the display comparison was WITHDRAWN rather than left passing without being
  understood, the measurement is recorded in test/bb.test.js at the point where
  it would go, and the three mutations wait on the render work:
    - "$BF0A returns instead of falling through into the erase"
    - "the erase does not force the flags, so a bit-3 corpse is never erased"
    - "the fall transition DRAWS instead of returning at $8AF7"
  THE STATE MACHINE IS EXACT -- 245 frames across 8 runs, every slot field --
  and THE DRAWING IS A NAMED GAP. Making the checksum pass by seeding around the
  difference would have been a lie about what is verified.
  New tool `tools/corpse.py`, new fixture `build/corpse_fixture.json`.
  Mutation battery 509/509 killed. bb.test 355 -> 365.
- [x] **M7.7-I9 DONE -- the FALL `$8B4E`, the FLOOR PROBE `$8BB4`, the LANDING `$8B83`.**
  THE MACHINE CORRECTED ME AGAIN, and the reading pass was right. I read `$8B6B`
  as testing only (X+8, Y+16); the built world says **floor_left ALONE lands the
  corpse**, because `$AED1` returns with the flags already set from (X, Y+16) and
  `$8B69`'s `JR nz` reads THOSE, before `$8B6B` reads the cell the `INC HL`
  stepped to. Two cells, one of them tested by a routine that had already tested
  it on the caller's behalf.
  AND THE POLARITY IS COUNTER-INTUITIVE: a solid cell UNDER the corpse lands it,
  but a solid cell in its OWN two rows means it is EMBEDDED and it KEEPS FALLING.
  All four body cells behave that way even with the floor solid.
  `(IY+4)` DOES A DIFFERENT JOB HERE than in flight -- there a 0/1/2 shimmer
  cursor, here a full EIGHT-BIT TIMEOUT that lands the corpse when it WRAPS TO
  ZERO. Unreachable in play (a fall from the top of the playfield is ~96 frames
  at two pixels), so it is BUILT: shadow bit 5 clear everywhere, 256 frames. At
  frame 254 `(IY+4)` is 255 and it is still falling; at frame 255 it wraps to 0
  and lands.
  THE GENERATOR CYCLES 0..7 IN LANDING ORDER and is PINNED TO 9 after `$88E0`.
  Seeded MID-CYCLE at `$05`, so "resets at round init" and "never resets" cannot
  both give type 0 first: the machine gives 6, 7, 0, 1, ... The pinned run is a
  CROSS-INCREMENT case -- I6 proved `$88E0` writes those three bytes, I9 is where
  they are read, and neither gate alone would catch the pair.
  THE SCAN STARTS AT `$9607` = **ENTRY 2**, not entry 1: entries 0 and 1 are the
  round's power-up and its spawned-in points item. An entry is free when
  **byte0** is zero -- built with three entries carrying a type and X but byte1 =
  0, and the scan walks past all three.
  AND THERE IS NO BOUNDS CHECK AFTER THE `DJNZ`. With all thirty-one fruit slots
  taken the pointer ends at `$9643`, TWO BYTES PAST THE BLOCK, and the landing
  writes `$36`/`$A1` over a `$C9 RET` and the first byte of `LD IY,$FD00`.
  **The original corrupts its own CODE.** Gated.
  EIGHT MUTATIONS SURVIVED THE FIRST BATTERY, and none of them was in the
  transliteration. FOUR were GATE gaps of one shape: the gate compared `landed`
  and Y, so the sprite force, the timeout counter and the packed byte were never
  looked at. It now compares **all ten slot bytes** on every probe, dummy and
  timeout row -- and that alone was not enough, because of a SECOND shape that
  took two further rounds to see. TWO OF THE WORLDS SEEDED THE VERY VALUE THE
  CODE WRITES: the slot was zeroed and `(IY+8)` never set, so the landing's own
  `LD (IY+8),0` was a no-op; and the sprite was seeded AS `$C700`, so forcing it
  back to `$C700` every frame changed nothing. The worlds now start from
  `(IY+8) = $5A` and the `$D360` FLIGHT frame, and the machine is watched
  putting both back. **Comparing every byte does not help if the byte already
  holds the answer.**
  FOUR were COVERAGE gaps, all of one kind -- a world in which two different
  rules give the same answer:
    - no run long enough to reach the wrap (added: 256 frames, `(IY+4)` driven
      to 255, which also kills the mod-3 model);
    - a solid cell one cell row ABOVE the corpse, clear in every earlier world,
      so "two body rows" and "three" were the same function;
    - the above-the-HUD heights had a CLEAR shadow, so the guard and a missing
      guard both read air. Now the FLOOR ROW ONLY is seeded solid -- seeding the
      body rows too is no good either, because then every height is embedded and
      falls whatever the guard does. With it: Y+16 = 16/18/23 fall, 24/32 land,
      and a `$10` threshold would land all five;
    - every occupied entry had BOTH bytes set, so "free means byte0 == 0" and
      "free means byte1 == 0" agreed everywhere.
  AND THE WIDENED GATE IMMEDIATELY CAUGHT MY OWN FIXTURE: the pixels-only probe
  case was the one world that never seeded `(IY+4)`, so the machine ran it from 0
  and the engine from `$10`. Eleven other cases had hidden it.
  New tool `tools/corpseland.py`, new fixture `build/corpseland_fixture.json`.
  Mutation battery 551/551 killed, ZERO survivors (+42 for I9).
  bb.test 377 -> 382.
- [x] **M7.7-I10 DONE -- the `$5CE0` BURST-SPARKLE engine `$C002` and its seed `$B6FC`.**
  **M7.7 (d)/(e) IS COMPLETE.**  This was the optional one, and it paid for
  itself twice over.
  THE WALK IS NOT A FOURTEEN-ITERATION LOOP. `$C016`'s `LDI` decrements the
  SIXTEEN-bit BC, and C is a live register, so entering with C == 0 borrows and
  costs B a count -- **slot 13 is then never serviced**. I measured C at the
  call site `$8D49` rather than assuming: 3 in `round1`, 1 in
  `candycane`/`crown`/`hurryup`, and **ZERO in `fruit` and `boss`**. So this is
  ordinary play. C comes from `$8D46`'s `CALL $A824`, which is not
  transliterated, so its provenance is a NAMED OPEN DEPENDENCY, not a constant
  I pretended to know.
  AND IT CAN RUN AWAY. `$C023 LD C,A` reloads C from the serviced slot's
  X & `$F8`, so when every serviced particle has X < 8 each later LDI sees
  C == 0, B passes zero and WRAPS, and the walk leaves the table: 4,563 bytes
  written as far as `$5FFE`, through the `$5D00` item sprite bank. The engine
  reproduces it ONLY because the walk is transliterated as a `DJNZ` over an
  eight-bit B. A `for (s = 0; s < 14; s++)` would have been green all day.
  THE RUNAWAY FOUND A REAL ASSET GAP. The machine services a particle at
  `$5CFE`; the engine had nothing there. `$5CFC..$5CFF` = `00 FC 3F C0` is
  runtime-built exactly like the `$5D00` bank -- the tape image is zero across
  the span, and in `boot`/`title` the region still holds the LOADER'S OWN BASIC
  TEXT (`" v.9/87"` sits at `$5CE0`) -- and the round clears do not reach it
  (`$989C` fills 24 bytes, `$BF53` 28, i.e. `$5CE0..$5CFB`). The item-bank asset
  now starts at `$5CFC`. Checking that also corrected the extractor's claim
  "only boot and title differ": `iball` differs too, and it is a front-end state
  (round 0, credits text in the bank), which is the same story, not a new one.
  `$CAA0` IS SETTLED-DEAD, WITH A PROOF, NOT AN OBSERVATION. ph = ((old & 7)
  + 1) & 7 and the free test has already rejected old & 7 == 0, so old & 7 is
  1..7 and ph is one of {2,3,4,5,6,7,0} -- NEVER 1; the carry needs ph < 2 and
  ph == 0 has already branched away. SPEC's "never observed" is upgraded.
  TWO MUTATIONS SURVIVED THE FIRST BATTERY AND BOTH WERE EQUIVALENT -- each made
  that impossible phase do something. They were WITHDRAWN and replaced with the
  live neighbour of each boundary (phase 3 instead of 1, `ph < 4` instead of
  `ph < 3`), which are observable and die; the code carries the proof as a
  TRANSCRIBED-NOT-EXERCISED label and the gate asserts the NEGATIVE -- over every
  pass captured, the new phase is never 1.
  THE GATE'S HARD PART WAS THE WORLD, NOT THE CODE. Phases 3..7 OR the SAME
  sprite into the SAME cells with no erase between, so one draw, three and five
  give a byte-identical screen; and erase and draw each write exactly 32 bytes,
  so a write COUNT cannot tell them apart either. Every pass is therefore
  captured separately and the ORDERED write list is compared. The screen is
  seeded never-zero and the shadow to that pattern XOR `$5A`, so "leave it
  alone", "write zero" and "copy the shadow" are three different answers -- over
  the black sky a sparkle actually sits on, they are one.
  AND TRAPS #44 BIT AGAIN IMMEDIATELY: the first run failed on the phase-0 case,
  which writes nothing, because the record and both self-modified operands held
  whatever the previous case left. They are now seeded to values the pass does
  not write.
  ONE REFACTOR FELL OUT, and it is the point of the whole subsystem: `$A2D5` and
  `$A314` read their subject THROUGH IY, so `itemBlit`/`itemErasePixels` now take
  the RECORD ADDRESS -- `$8903` for a collectible, `$C05E` for a sparkle -- plus
  the OR flag that `$A2C2` patches out for items and leaves alone for everyone
  else. One pair of blitters, seven subsystems.
  SPEC's THREE overlapping accounts of `$5CE0` are replaced by ONE. The old
  "fruit table" entry (wrong encoding `X<<3`, wrong entry point `$C006`, `$A314`
  called a collect, the clears called an LDIR) is struck through; the retraction
  that left its role "unconfirmed" is closed; the elemental-effect reading is
  corrected.
  New tool `tools/sparkle.py`, new fixture `build/sparkle_fixture.json`.
  Mutation battery 593/593 killed, ZERO survivors (+42 for I10, two of
  them replaced after surviving as provable equivalents).
  bb.test 382 -> 401.
- [x] **M7.11 DONE -- the wind read collapsed into `driftCode()`/`driftDelta()`.**
  The uncalled-method census had them as DEAD DUPLICATES: the helpers computed
  the per-round wind by name, `bubbleRiseStep()` computed it inline, and the two
  were proved equivalent over 3,072 sampled cells. Equivalent today; two things
  to keep in step for ever.
  The engine CALLS them now, so there is one spelling of the rule and the gates
  that already drove the helpers by name now cover the live path too. The census
  drops 22 -> 20, which is the signal the collapse really happened.
  Four mutations, all killed -- including "the wind read is inlined again",
  which the census gate catches because `driftCode` would return to the list.
  TRAPS #114. bb.test 1001/1001.
- [x] **M7.10 DONE -- $806C, THE LIVES ICONS, and the mask narrowed from 56
  addresses to 16.** The SIXTH method written, gated in isolation and never
  called.
  **WHAT WAS MISSING WAS THE STATE, NOT THE CODE.** `livesIcons()`, `livesRow()`
  and `livesCell()` were all transliterated; `reset()` left ($FD87), ($FD91),
  ($FDDC) and ($FDE6) at ZERO, and `$8097` is `RET p`, so wiring the call alone
  would have drawn an EMPTY ROW and passed -- the gate that should have caught it
  was masking those cells as a declared gap (TRAPS #111).
  Input set measured by read-watch; round1_48, play1p48 and r20_48 all carry
  $E1/$60 (P1 in play, P2 not) and lives 3/3.
  **THE GATE IS STRICTLY STRONGER NOW:** the mask drops its 40 lives addresses,
  the live sequence diverges on SIX bytes instead of ~25, round 1 on NONE, and
  BOTH ROUND-81 COMPOSE ROWS MATCH WITH NOTHING MASKED -- round 81 draws no round
  number, so the last remaining gap does not apply there.
  **AND IT UNBLOCKED $8E2A.** That trigger was deliberately unwired because the
  port's world had no player in play; `$8E32`'s `OR (HL) / RET m` now declines on
  the first test as it should, so the reason has changed from "the world is
  wrong" to "the increment is next".
  **AND THE PORT CAN NOW WARP.** `$9840`'s BIT 7 test always failed while ($FD87)
  was 0, so eight sequence gates had been passing BY ACCIDENT -- comparing two
  different journeys, since the oracle suppresses the warp and the port simply
  could not. They drive both sides the same way now (TRAPS #112).
  AND I ADDED A DUPLICATE CONSTANT: `BB_LIVES_ICON` seeded $85A1, which
  `BB_HUDF_ICON` already seeded. The battery reported its mutation as a SURVIVOR
  and was right -- the line was dead. Removed (TRAPS #113).
  New tool `tools/livespanel.py`. The uncalled-method census 23 -> 22.
  bb.test 1001 (one row replaced, one strengthened). TRAPS #111-#113.
- [x] **M7.9 DONE -- THE SHIP/TEST ASSET SPLIT: the page is 621 KB, was 8,829,094
  bytes.** The user asked in September why the HTML was 8.3 MB when three other
  ports from the same kit are under 1 MB. This is the answer, and it was never
  the rounds.
  **97.7% OF THE PAGE WAS ORACLE FIXTURES.** 68 of 76 assets, 17.6 MB, written
  for the SUITE and inlined into the artifact a player downloads; `walker` alone
  was 13.3 MB. The engine reads EIGHT assets, 207 KB.
  `port.json` gains `ship`, DEFAULTING TO TRUE so an unclassified asset costs
  bytes rather than correctness; `tools/build.py` holds back `ship:false`;
  `test/rig.js` loads them from disk and MERGES them into `P.assets`, counting
  what it merged. Both are kit files, so both changes are game-agnostic and
  `test/kit.test.js` carries the generic checks (house rule 8).
  **THE FLAG THAT LOOKED LIKE THE ANSWER WAS NOT**: splitting on `required`
  would have BROKEN the page -- `records` and `reloc` are read by reset() and
  were marked `required: false`. The gate derives the split from the ENGINE
  SOURCE instead, so mismarking an asset turns it red.
  **GATED BOTH WAYS AND MUTATION-TESTED BY HAND**, since the battery only
  mutates web/*.js: marking an engine asset `ship:false` FAILS; shipping a
  test-only asset FAILS (and the page jumps to 5,587 KB); and disabling the
  rig's merge drops the suite from **1,001 checks to 67** -- the silent-skip
  failure mode, caught loudly by the rig's own counted assertion.
  AND THE FIRST VERSION OF THE ENGINE-SIDE GATE MEASURED NOTHING: built as a
  dynamic RegExp through a code generator, its escapes collapsed, `''` became
  a BACKSPACE, and the row reported "0 referenced" and PASSED. Replaced with a
  literal scan, plus a row asserting the count is non-zero (TRAPS #110).
  kit.test 115 -> 120, bb.test 996 -> 1001.
- [x] **M7.8-C DONE -- THE DRIFT PAINTER `$7C57..$7DD5`, TRANSLITERATED, AND THE
  ASSET RETIRED.** The first increment here driven by a full agentic pass: four
  mapping agents, a synthesis, and two adversarial reviewers, against a target
  that was FALSIFIABLE BEFORE ANYONE STARTED -- `build/drift_field.json` already
  held the machine's answer for all 81 rounds, so a model either reproduced them
  from `build/image.bin` alone or it did not.
  **81 OF 81, and both reviewers reproduced it with INDEPENDENT implementations**
  written from their own disassembly rather than from the synthesis code.
  **THE ASSET IS THE PAINTER'S INPUT NOW**: 675 bytes (628-byte rectangle stream,
  two 16-byte stride tables, fifteen door-pattern bytes) against 15,552 bytes of
  captured output. `build/drift_field.json` is gone.
  **AND THAT MADE A TAUTOLOGICAL GATE REAL.** The suite's "the drift field matches
  the machine on all 81 rounds" row drove the engine -- which READ
  `drift_field.json` -- against `drift_fixture.json`, and a reviewer found the two
  hold BYTE-IDENTICAL base64 for all 81 rounds. One capture compared with a copy
  of itself, per cell, with careful commentary about permutations, and no possible
  failure. The engine now computes, so the identical comparison tests the
  algorithm (TRAPS #104).
  **THE DOMAIN FINDING WAS THE ONE A SOLO PASS WOULD HAVE MISSED.** The old lookup
  silently no-opped on an unknown round; a real painter does not. At `($8609)` = 0
  -- the byte `$96FB` writes at EVERY NEW GAME -- the machine writes 141 cells over
  `$FB02..$FFF0`, and at 255 it writes **10,545** across the player struct, the
  bubble pool and the high score. Measured that the port cannot reach it (`$97F8`
  increments the round before the round start); guarded and COUNTED anyway
  (TRAPS #105).
  FINDINGS WORTH KEEPING: `$7E2B` has SEVEN call sites, not four -- the four doors
  are `CALL nz`, opcode `$C4`, which a `CD 2B 7E` scan misses. Head rectangle 1 is
  a field-level NO-OP. The mirror TRANSFORMS rather than copies (RIGHT <-> LEFT,
  UP/DOWN untouched) and is the only producer of code 3. The pattern table is LIVE
  during a paint and restored by the identity of eight rotations. The shipped
  pattern block is FIFTEEN bytes because `$7E29` is the painter's own counter and
  index 15 is never selected. Round 45's 15 off-map cells are PRODUCED, not
  clamped. And the painter carries NOTHING between runs -- the question M7.8-A was
  burned by, asked rather than assumed.
  **AND IT COST FIVE HOURS OF A SPINNING CORE, FROM TWO DEFECTS OF MINE.** The
  alias walk is unbounded on the machine -- the Z80 terminates only because the
  data does -- so a mutation reading the stride from `BODY[]` instead of `LEN[]`
  made it cycle, and `node test/bb.test.js` never returned. The runner had NO
  per-case timeout, so it sat blocked with that mutation STILL APPLIED to
  `web/game.js`, and my report that the file was clean was wrong: I checked the
  first case's anchor and it was the third that was stuck. The walk is bounded and
  counted now, both runners time out per case, a timed-out case is a SURVIVOR, and
  the battery lives in `scratchpad/battery/` instead of a session temp directory
  that has since disappeared (TRAPS #106).
  The bounds gate then caught me again: my first two corruptions to exercise it
  did not actually loop, so the row FAILED rather than passing vacuously.
  Replaced with two that do.
  **AND THE FIX FOR THE HANG REPORTED THE NEXT HANG AS A PASS.** The serial
  runner's timeout returned `['TIMEOUT']` as the FAILURE LIST, and its caller
  prints `killed by len(fails)` -- so a hang printed "killed by 1". The next run
  reported "all 25 killed, zero survivors" with TWO cases having hung for 180s
  each, and that went to the user as a clean result. It was caught only because
  a PARALLEL runner, written independently, gave TIMEOUT its own verdict and
  DISAGREED -- two implementations of one measurement, which is the only thing
  that finds this (TRAPS #107).
  **SO THE BATTERY NOW RUNS ON EIGHT CORES**, `scratchpad/battery/parallel.py`:
  each worker gets its own 31 MB tree (web/, test/, tools/, port.json,
  build/*.json), so the cases are genuinely independent -- and **the real working
  tree is never written**, which removes the serial runner's worst property, that
  an interrupted run leaves a mutation APPLIED to web/game.js. Validated against
  the serial result on a slice whose answer was known before trusting it.
  TWO MORE UNBOUNDED PATHS were found by it and fixed: the rectangle counter is
  a BYTE on the machine (`$7E29`, `DEC / JP nz`), so modelling it as a JS number
  let a mutation loop to -1, -2, ... -- eight bits is both more faithful and
  bounded; and `paintFill` got a work budget whose FIRST version counted CALLS
  and capped them at 4,096, which permits 268 million writes and still hung.
  Counting CELLS bounds it: a real round asks for at most 1,090, so 200,000 is
  183x headroom and the 81 real rounds trip it zero times (TRAPS #108).
  **OPEN ITEM, recorded rather than swept away:** one mutation -- the entry
  stride read from `BODY[]` instead of `LEN[]` -- HANGS the suite, and the hang
  is NOT in the painter. `driftPainter()` completes all 81 rounds with it
  applied, and none of 21 instrumented engine loops fires; something downstream
  loops on the corrupted field, in a `for` with a computed bound, and I did not
  locate it. The mutant is WITHDRAWN with its enumeration because its property is
  already covered by the mirror-image case ("the body offset comes from LEN[],
  not BODY[]", killed by 11) and the only thing it adds is the hang. A corrupted
  drift field can hang the engine somewhere not yet found, and the painter's
  three guards do not cover it.
  **THE BATTERY NOW RUNS ON EIGHT CORES** -- `scratchpad/battery/parallel.py`,
  16 minutes against 65 serial, each worker in its own 31 MB tree so the REAL
  working tree is never written. Writing a second implementation of the same
  measurement is what found the reporting bugs in the first.
  **AND IT CORRECTED MY OWN RECORD TWICE.** (1) I wrote that the battery had no
  per-case timeout; `mutate7.py` ALWAYS had one, plus crash detection, with a
  comment saying a hang counts as a kill because the suite did not pass. The
  runner that lacked both was a HELPER I wrote that afternoon and then reported
  results from. TRAPS #106/#107 are corrected. (2) My parallel runner then made
  the inverse error, calling a crashing case SURVIVED. Nineteen "survivors" were
  not survivors: eighteen were the engine's own `BB_Rng: UNEXPECTED DRAW` guard
  firing -- a real detection, by a named diagnostic -- and two were BROKEN
  MUTANTS whose `old` stopped mid-line and left a dangling `-- "I am a corpse"`,
  so they produced invalid JavaScript and had been testing NOTHING. Both
  repaired.
  **M7.8-C's OWN DEBT, REPAID:** deleting `driftApply()` killed the anchors of
  14 older mutations (seven H4, seven M7.8-B) -- TRAPS #73's shape. The seven H4
  rows tested the ASSET'S UNPACKING, which no longer exists, and are retired
  with their enumeration; four M7.8-B rows have exact M7.8-C successors already
  killed; three are re-pointed at the live code.
  **OPEN: THREE NAMED HANGS**, each an unbounded loop a single mutation reaches
  -- `I10` and `R2` are pre-existing and unrelated; the third is M7.8-C's entry
  stride, whose runaway is NOT in the painter (it completes all 81 rounds with
  the mutation applied and none of 21 instrumented loops fires).
  New tool `tools/driftpainter.py`; assets `build/drift_painter.json` (shipped)
  and `build/driftpainter_fixture.json` (oracle). TRAPS #104-#108.
  bb.test 988 -> 996.  Mutation battery LISTED 1459 / KILLED 1456 / SURVIVORS 0
  / DEAD ANCHORS 0 / TIMEOUTS 3 (named).
- [x] **M7.8-B DONE -- THE DRIFT PAINTER'S WIRING, `$7DD6`, AND A STANDING CENSUS.**
  Two gameplay-visible defects the M7.8-A adversarial pass named, both PRE-EXISTING
  and both the same shape: a routine reached on the machine only by FALL-THROUGH,
  with a JS method written for it, gated in isolation, and never called.
  **`$79AC` DOES NOT STOP AT THE COLLISION TRANSFORM.** `$7C43` masks with `$38`,
  which WIPES bits 6 and 7, and then falls onward through the painter
  `$7C57..$7E4A`, whose writers `$7E3E` and `$7D73` put them back.  MEASURED on
  the built page: 288 colour-shadow cells carry the drift bits after `reset()` and
  **ZERO after every `roundAdvance()`**.  Those bits are the per-round WIND, so
  `driftCode()` read 0 for every cell -- the open-air arm -- and **every bubble on
  every round after the first rose straight up**.  Wired, the engine reproduces the
  machine's WHOLE colour shadow byte for byte over `reset()` and all 23 advances.
  **`$7DD6`, THE ELEMENT CLASS, likewise.** `($7E0E)` read 0 on all 80 advances
  while the machine carries a non-zero class on 50 of 81 rounds, so the fire, water
  and lightning rounds never triggered.  It writes TWICE -- `$7DF0` the raw class,
  `$7E0A` the redraw -- and the port models both; on the 13 rounds that take
  `$7DF3 CP 5 / JR nc` -> `$7E04 LD A,R` the DECLARED RNG SUBSTITUTE gives its own
  answer and only the **5..12 range** is contracted.  66 rounds exact.
  **ROUND 81'S SKIP IS A BRANCH IN THE PAINTER, DISASSEMBLED NOT INFERRED**:
  `$7C84 LD A,($8609) / CP $51 / $7C89 RET z`, the same idiom as `$7F83`'s.  The
  census says `($7E0E)` is written on 80 of 81 rounds, and a path trace enters
  `$79AC`/`$7C43`/`$7C57` on rounds 80 AND 81 and `$7DD6` on 80 alone.  The FIELD
  still applies on round 81 -- only the tail is skipped -- so the guard sits in
  `driftPainter()` where the machine puts it, and both arms are driven.
  **AND THEN TRAPS #103'S OWN RULE (b) WAS MADE INTO A GATE.**  This pattern has
  now bitten FIVE times in two increments, so the suite counts it: the engine
  methods with no `this.X(` site and not dispatched by name through `BB_CHAIN`.
  **23**, frozen -- six the driver interface, **two DEAD DUPLICATES**
  (`driftCode()`/`driftDelta()` restate the inline wind read of the `$B836` move,
  proved equivalent over 3,072 sampled cells), and **fifteen unbuilt increments**,
  which is the honest size of what is left.  The gate is mutation-tested in BOTH
  directions: a new uncalled method appearing, and an existing one being wired.
  A first hand-rolled version of that scan reported 24 and wrongly included
  `entitySlotTail`, which IS called -- two scans of the same thing disagreeing by
  one is why the list is frozen rather than recomputed and trusted.
  The painter ITSELF is still not transliterated; M7.7-H4's "WHEN THE PAINTER
  LANDS THE ASSET GOES" stands as the next increment.
  bb.test 981 -> 988.  TRAPS #103.
- [x] **M7.8-A DONE -- THE ROUND BUILDER `$7F62` AND ITS COMPOSITION `$7F1B`.**
  The user asked for "the render assets for rounds 2-81, which don't exist and
  would every one have had M7.3c's black-screen defect".  The measurement pass
  answered the question and then moved the ground under it.
  **THE PREMISE HELD, AND HARDER THAN IT WAS PUT.** Over all 81 rounds a plate
  whose attribute third came from the colour shadow has 322..578 of 704 playfield
  cells black-on-black (median 456, never zero), while the correct source gives
  ZERO on every round. No palette entry is dark, so the visibility gate cannot
  false-fail.
  **BUT ROUNDS 2-81 MUST NOT GET PLATES AT ALL.** A round's platform shadow IS
  NOT A FUNCTION OF THE ROUND: the same round 20 at different build-counter
  phases differs in up to 2,083 of 6,144 bytes; `($83EC)` picks the tile (five
  values in play) and BIT 7 of the palette byte picks a wall arm. A faithful
  plate set is **81 x 5 x 2 = 810 shadows, about 5 MB**, against 768 bytes of Z80
  over data the port already ships.
  **AND THE DEFECT WAS ALREADY SHIPPED, ONE LEVEL ABOVE THE ASSETS.** `roundStart()`
  called `scrollIn()` -- the MIDDLE of `$7F1B` -- so the builder never ran.
  Measured on the built page: after `reset()`, 0 of 704 invisible cells, 2,415
  bitmap bytes, 2,247 shadow bytes, 224 drift cells; after ONE `roundAdvance()`,
  **495 invisible, 0 bitmap, 0 shadow, 0 drift**. M7.3c's visibility gate could
  not see it because it runs only after `reset()`.
  NEW: `ceiling()` (`$81C3`, TWO passes -- it falls through into `$81C9` a second
  time, so the run lengths are 9,4,6,4,**18**,4,6,4,9 and the 18 is the JOIN),
  `rowsToShadow()`/`rowToShadow()` (`$854D`, display -> shadow), `roundBackground()`
  (`$7F62`, ten calls and NO RET), `roundBuild()` (`$7F1B`).
  **TWO PIECES OF UNSEEDED LIVE STATE, found only because the builder finally gave
  thirteen uncalled methods a call site.** `$833B`, `$833A`'s self-modified operand
  and the wall column offset -- the parity inverted and the walls drew on the
  wrong sides; SPEC had already warned "no count-based gate can see it" and was
  right. And `$856C..$8583`, the tile buffer's static half: a build writes only
  +1/+3/+5 and the evens, so +7..+15 and +16..+23 are pure tape data the port had
  never shipped, and with them zero `$824A`'s `OR (HL)` contributed nothing --
  **2,704 writes to the same 2,704 addresses in the same order, 455 platform bytes
  missing** (TRAPS #96).
  **THEN AN ADVERSARIAL PASS FOUND A THIRD, AND IT WAS THE REAL ONE.** `reset()`
  carried `($82D7)` from the render asset and left `($83EC)` on `build/image.bin`'s
  round-80 zero, so the port sat at (1, 0) -- a pair the machine is never in,
  since `$83EC == $82D7 mod 5` on all five shipped states and all 81 chained
  builds. **Every round the port built used the PREVIOUS round's platform tile**,
  about 1,650 of 6,144 bytes per advance, with all 18 differential rows green --
  because the differential SEEDS its own inputs and so tested the builder against
  poked triples and never against the sequence the port generates (TRAPS #98).
  A gate ASSERTED the wrong value, so the pass found it by *correcting* the seed
  and watching the suite go red (TRAPS #99). `($83EC)` is carried from the render
  asset now, and `tools/render_asset.py` captures it.
  **WHAT THE PASS ALSO PROVED ABOUT THE GATE:** fifteen mutations left it at
  969/969. `$854D` had no byte oracle at all and is INVISIBLE in the composed path
  (after `$8216` the display already equals the shadow), so its whole body could be
  replaced by a counter bump; the composition's counts were compared to JS
  literals, which regression-tests the oracle and not the port; the `$7F1B`-exit
  snapshot the fixture already carried was never read by any check; one assertion
  was a TAUTOLOGY over a `Uint8Array` sitting above a loop with an empty body
  (TRAPS #100). All fixed: a live-sequence gate that pokes nothing, a poisoned-
  display unit oracle for `$854D`, the engine's own trace against the machine's
  measured one, the compose rows compared, and the covering set extended 18 -> 23
  to drive palette index 10 -- because **"bit 7 is clear on index 0 alone" was
  false**: `$858C` index 10 is `$0F`, used on rounds 11, 26, 41, 56 and 71.
  **FOUR DECLARED BOUNDARIES, each with a magnitude rather than a shrug:** the
  ROM-font round-number glyph (6 bytes, `$8042` indexes the charset at `$3C00`);
  the lives icons (`$806C` is a counted stub, row 23 columns 0-4); `$7FC0`'s tail
  (**1,191 writes measured** -- 488 bitmap, 129 attributes, 32 shadow, 542 score
  counters -- which is why the machine calls `$806C` twice on round 1 and the
  engine once); and the ISR, which fires inside `$7F1B` because it has no HALT and
  changes the built shadow on 3 of 23 rows (TRAPS #101).
  ALSO CORRECTED: `$8260` is not an instruction (`$825E` is `LD A,($8309)`; the
  drawer is `$824A`); the wall orders differ by 42/12/28/20 bytes per round, not
  "5"; `tools/render_asset.py` hardcoded a palette wrong at six of fifteen indices
  and now reads `$858C` from the image; M7.3c's "433 invisible cells" measures 495
  on the pre-fix blob and is frozen with its git provenance (TRAPS #97).
  **AND A SECOND ROUND OF THE SAME ATTACK FOUND TWO MORE.** The tile buffer is
  TWO HALVES with different provenance and the constant carried no marker: the
  odd bytes are static tape data, but the EVEN bytes are PER-ROUND STATE, so
  seeding all 24 from the tape left `$8207`'s filler at `$00 x 8` where the
  machine leaves round 1's tile -- the ONE-ROUND LAG, invisible until the filler
  was compared after `roundBuild()` instead of after `roundBackground()`, since
  `$8207` is called at `$7F2A`, UPSTREAM of the builder. And the "must not touch"
  check named four ranges and left everything between them open: a mutation
  adding `ram[0x9000] = 0xFF` to `ceiling()` survived, so the extent is now an
  ADDRESS SET over the whole 64K -- and the first attempt at THAT was wrong too,
  because a before/after diff gives CHANGED addresses and `$860E` is written on
  every build and changed on none (TRAPS #102).
  **AND THE `($83EC)` FIX SILENTLY DISARMED TWO OLDER MUTATIONS** -- TRAPS #73's
  shape with a LIVE anchor instead of a dead one. Both H0 rows aimed at the image
  FALLBACK line, which now has both counters overwritten by the asset two lines
  later, so both became equivalents and survived a battery that had killed them
  for months. Re-aimed at the carry. One of the re-aimed pair then survived
  again, for a real reason: round 1's asset has `build_counter == tile_counter ==
  1`, so a port routing one to the other's address is byte-identical on every
  shipped world (TRAPS #37's shape). Fixed without a second asset, by handing the
  engine a SYNTHETIC render asset with 7 and 2 and requiring each to land at its
  own address.
  FOUR MUTANTS WITHDRAWN AS PROVABLE EQUIVALENTS, each with its enumeration in
  the battery: repaint-before-scroll (after `scrollIn()` the display already
  equals the shadow on all 5,632 playfield bytes); `$854D` before `$806C`
  (CONDITIONAL -- equivalent only while `livesPanel()` is a stub, and real the
  day `$806C` is built); arming `$9603` after `$8207` (disjoint, measured); and
  `BB_TILE_SEED` from `image.bin` (tape and image agree on all sixteen bytes the
  constant still governs).
  New tool `tools/roundbuild.py` -> `build/roundbuild_fixture.json` (closure,
  ceiling, compose, alias, clear, closed, oracle 23 rows, anchor, digits, sequence,
  rowsto, hud, extent, negatives).
- [x] **M7.7-F0 DONE -- the ROUND-CLASS CENSUS and the CHAINED-BUILD RECIPE.**
  The first increment out of the (f)/(g)/(h) reading pass, and deliberately built
  SOLO: the pass had already measured all of it twice, so it was a transcription
  sitting, not a discovery one.
  THE RECIPE IS THE DELIVERABLE, and it exists because **POKING `$8609` IS NOT A
  ROUND SAMPLE.** `$8609 := 19` warps to 81 and produces round 81's signature to
  the T-state; round 1 needs `$8609 := 0`, which no shipped state carries; and
  `$745C`/`$AA57` are INHERITED on 80/81, so a fresh poke hands you whatever the
  source state held. So: 81 sequential `CALL $97F8` in ONE world, the warp
  suppressed, SP pinned per build, and the sentinels reseeded BEFORE EVERY BUILD.
  THE SENTINEL IS THE WHOLE POINT. Rounds 78 and 79 both give `$03E8` and both
  leave `$AA57` = 9, so on a chained sweep "not written" and "written with the
  same value" are the same observation. With `$745C := $AABB` before every build,
  the negative is proved on ALL 81 ROWS: it survives on EXACTLY rounds 80 and 81.
  MEASURED: the threshold table is 1500 for rounds 1-55 and 57-71, **350 on round
  56**, **30000 on round 72** and 1000 from 73 -- the hurry-up is shortest on 56
  and effectively absent on 72. `$AA57` = enemies + 2 (the two PLAYER slots are
  in it) and over a real chained game it never leaves **5..9**, which is what
  makes the four `SUB 2 / LD B,A` sites safe: B is 3..7, never 0, so none of them
  runs 256 iterations into the score bytes and ROM. **That settles a disagreement
  the reading pass could not**: its completeness critic called `$AA57` = 14 "the
  REACHABLE half" of that overrun; the F0 investigation said 5..9 and proved it
  four ways; this chained sweep confirms the investigation. The 14 case is a
  POKED characterisation and the plan now says so.
  THE WARP HAS THREE INPUTS, and the port already had it right. Six of sixteen
  rows fire; the rule is `(NOT P1died AND P1inplay) OR (P1died AND NOT P2died AND
  P2inplay)`, because `$9830` picks the first player whose died-flag is CLEAR and
  `$9840 BIT 7,(IX+7)` then tests THAT player through whichever IX the first test
  left. With both flagged dead there is no warp at all -- the row a two-input
  model gets wrong. And **the two extra lives do not ride on the warp**: (3,3)
  becomes (4,4) in all sixteen rows, granted at `$982A`/`$982D` before the warp
  is considered.
  AND I MADE THE EXACT MISTAKE THE PLAN WARNED ABOUT, in the file whose docstring
  warns about it. The plan asserts `$9811` gives 32 distinct values; my first
  measurement gave **31**, with 38 (`R & $1F` == 8) missing over 420 samples and
  counts running 1 to 32. **The plan was right and my measurement was wrong**:
  R advances with the INSTRUCTION COUNT, so stepping `1 + (i % 17)` between
  samples is a comb through its residues. Driving whole frames is no better --
  200 samples give exactly TWO values, because `run_frames` is deterministic and
  R phase-locks to the frame parity. So the oracle stopped sampling: it SETS R to
  all 256 values and asserts the FUNCTION, `(((R + 2) & $1F) + $1E)`, 256 of 256,
  the +2 being `LD A,R` (`ED 5F`) reading R after its own two M1 cycles. The
  two-value frame run is KEPT in the fixture as the demonstration that an idle
  harness cannot sample `$9811` at all. (This is the same shape as the earlier
  pass's eight all-even draws -- the third time a fixed or periodic phase has
  produced a confident wrong answer here. TRAPS #34's family keeps growing.)
  THE ONE PLACE THE TWO SIDES MAY DIFFER is gated as such: round 81's lookahead
  is DRAWN, so the E1 substitute gives its own value and only the 30..61 RANGE is
  contracted -- 1 row of 81, and the other 80 are compared exactly.
  New tool `tools/roundclass.py`, new fixture `build/roundclass_fixture.json`.
  Mutation battery 618/618 killed, ZERO SURVIVORS FIRST TIME (+25 for F0) -- the
  first increment here to manage that, because the gate drives 96 warp rows and
  81 chained builds through one small routine.
  bb.test 401 -> 421.
- [x] **M7.7-I11 DONE -- the TREASURE ROOM (`$890D`'s tail, `$8950`, `$899E`, `$8F36`).**
  Numbered into the ITEMS series on purpose: `$8F36` never reads `$8609` and
  gives identical answers on rounds 2, 20 and 81, its trigger is an ordinary
  1-in-16 power-up, and every byte it touches was already built by I1-I10.
  IT HAD TO MOVE BOTH HALVES AT ONCE. Before it, handler 12 did not set `$FED1`
  and `roundClearCheck` had no caller. Wiring either alone gives **a round that
  can never be cleared** -- a hang, not a cosmetic gap, on any round.
  **THE WINDOW IS AN EQUALITY, NOT A THRESHOLD.** With items still live the room
  clears at a delta of EXACTLY 8 between the timer's high byte and the one
  captured when the skull was taken -- and at no other value. Measured: 0 and 7
  do not clear, and neither do 9, `$10`, `$F8` or `$FF`. A port that writes `>=`
  is right on every row below 8 and on every empty-table row, and wrong from the
  ninth tick onward. The `$F8`/`$FF` rows are in the sweep because the
  subtraction WRAPS in eight bits -- deltas a sixteen-bit model never produces.
  Clearing ON the window gives NO AWARD (Z set, scores unmoved, zero screen
  writes); an EMPTY table awards whatever the delta.
  THE LEADER COMPARE IS ONE UNSIGNED BYTE. `$7F` against `$80` gives the award to
  P2 and `$80` against `$7F` to P1; a signed compare reverses both and no
  ordinary pair of tallies could tell. **A TIE GIVES BOTH PLAYERS THE LARGER
  AMOUNT** (`$8F61` copies HL into DE), so the rule is not "the leader gets more"
  but "nobody behind gets less".
  THE AWARD GOES TO THE HIGH HALF of the pending field (`$8F66 LD ($FFEE),HL`),
  so it is worth a HUNDRED times the same number written low -- and only TWO of
  the four bytes are written. That is provable only in the SCORE: seeded `$99`
  throughout, P1 comes back `99 00 01 99`. The FIELD cannot show it, because
  `$80FA`'s own cleanup zeroes all four afterwards.
  THE FILL RUNS ON TWO REGISTER SETS and the split is load-bearing: MAIN holds
  (entries left, item cursor, Y, X) and ALT holds (columns left, rows left, the
  colour-shadow cursor). The two DJNZs are on DIFFERENT Bs, and the entry
  counter's exit ends the whole fill MID-ROW -- which a one-register-set model
  gets wrong only on a map open enough to fill the table. Round 80 is that map.
  THE PROBE ABANDONS ITS CALLER. `$89B7` finds a solid cell and does POP HL /
  RET, discarding `$899E`'s frame and returning past it with carry CLEAR,
  bypassing the `$89B5 SCF`. Third routine here to do that, after `$B679` and
  `$88B1`. And its third cell group is NOT at a negative offset: `$89AF LD E,$1D`
  leaves D at ZERO, because `$89B7`'s own `LD D,3` clobbered the `$FF` and its
  loop counted it down -- a model that keeps D lands 227 bytes away.
  ENTRY 0 IS NEVER TOUCHED BY EITHER. The fill starts at `$9605` and the count
  walks 31 entries from `$9605`, so a room whose only remaining item is the round
  power-up counts as EMPTY. That is a THIRD base over the same 64 bytes, after
  I1's passes from `$9603` and I9's corpse scan from `$9607`, and every row seeds
  entry 0 LIVE so the three cannot agree by accident.
  THE PROBE OFFSET IS AN EQUAL-ANSWER TRAP, and the audit predicted it. The
  `$899F` offset is -`$21` for type 1 and -`$01` for type 9, and the two AGREE on
  rounds 20 and 80 (14/14 and 32/32) while DIFFERING on 1, 2, 5, 56 and 81. A
  gate driven only on r20 or boss cannot tell them apart; the sweep spans both.
  **IT FORCED I6's BOUNDARY FORWARD, AND THAT GATE IS NOW STRONGER.** I6 had
  handler 12 bracketed at `$8915`, a documented partial contract, so extending
  the port past it broke that gate. The boundary moved to `$8949` -- one
  instruction short of `CALL $8C14`, which RES 7s seven entity slots and twelve
  bubble slots and then repaints the whole playfield through `$8216` (7,076
  display writes, measured, and (h)'s work). The row now covers `$A36C`'s forty
  bytes, `$8E0A` writing NOTHING (so its absence is an assertion), both tallies,
  BOTH latches, the `$8F3A` capture and both self-modified operands.
  AND THAT EXPOSED TRAPS #44 AGAIN: `$8DBE` and `$8F3A` were BOTH seeded `$5A`,
  so the capture wrote the value already there and "captured" was
  indistinguishable from "never written". Seeded apart.
  ALSO CONFIRMED, a defect the reading pass predicted in SHIPPED work:
  `tools/clear.py`'s clean slate writes `$40` into twelve slots' +7 from `$FD80`,
  which lands on `$FD87` and `$FD91` -- BOTH PLAYERS' ACTIVE FLAGS -- so `$810C
  BIT 7,(IX+7)` discarded every award, and not one of its nineteen watched
  addresses was >= `$FFE0`. The drain rows here seed the players ACTIVE, which is
  the only reason they can observe an award at all.
  DECLARED DEPARTURE: `$8F78` draws "PERFECT !" **256 times** (B starts at ZERO)
  with the main loop stopped -- about 1.8 million T, roughly 26 frames, ~41,600
  screen writes. The port counts the iterations faithfully so the timing is
  gated; the glyph draw goes through `$801D`/`$994F`, neither transliterated yet
  -- the same named gap as `$A26F` in I8.
  AND ONE FACT FOR THE TIMER MODEL: **power-up 11 ZEROES `$8DBD` (both bytes)**
  mid-round while leaving `$8F3A` alone, so the room's window is NOT
  "elapsed since you took the skull" -- it is an equality on `$8DBE`, and a port
  modelling elapsed time diverges the moment a second power-up is collected.
  New tool `tools/treasure.py`, new fixture `build/treasure_fixture.json`.
  FOURTEEN MUTATIONS SURVIVED THE FIRST BATTERY, and THREE of them were my own
  fault rather than the gate's.
  ONE WAS A PROVABLE EQUIVALENT: "the type is ADDED to X rather than ORed".  X is
  always a multiple of `$20` and the type is 1 or 9, so their bits are DISJOINT
  and OR, ADD and XOR give the same byte on every cell of every map.  Withdrawn
  and replaced with a three-bit type field, which differs only on round 81.
  TWO MORE WERE EQUIVALENTS I CREATED.  `puShootGate()` ALREADY zeroed the hurry
  timer -- `$8895` sits in the SHARED `$8888` tail -- so the line I added to
  handler 11 was a duplicate and deleting it changed nothing.  Removing it also
  CORRECTED THE READING PASS: **handlers 10 AND 11 both zero the timer**, not 11
  alone, and the gate now asserts that plus the negative for the eight handlers
  that do not.
  THE OTHER ELEVEN WERE REAL GAPS, of two familiar shapes.  THREE were asserted
  off the FIXTURE instead of driven through the engine -- the type and probe
  offset checks read captured rows and never called `treasureArm()`, which is
  now driven over seven real rounds.  The other eight were worlds where two
  rules agree: the live entries sat at the BOTTOM of the table, so a 30-entry
  walk and a 31-entry walk found the same items; the fill comparison stopped at
  64 bytes, so an over-long fill wrote past it unseen; and EVERY wrap row had
  the masked and unmasked subtraction AGREEING.  Fixed by putting the live
  entries at the top, adding one entry with byte0 ZERO and byte1 `$7E`, guarding
  the six bytes past the block, and adding a capture of `$FC` against a high byte
  of `$04` -- a delta of 8 masked, MINUS 248 unmasked.
  AND THE LAST ONE NEEDED A BUILT WORLD.  `break` instead of `return` on a full
  table differs only when the table fills with passing cells STILL TO COME IN A
  LATER ROW.  I measured all 81 rounds: only round 80 fills at all, at 32 of its
  42 cells, and its ONE spare cell falls in the same row as the last placement --
  so on every map the game ships, "end the fill" and "end the row" are the same
  function.  With the colour shadow clear everywhere all 42 pass, the table fills
  on cell 31 with eleven to come across two later rows, and the wrong model
  carries the entry counter past zero to `$FF` and writes onto the image's own
  `$C9` RET -- the byte I9 measured the corpse landing scribbling on.
  Mutation battery 682/682 killed, ZERO survivors (+64 for I11).
  bb.test 421 -> 444.
- [x] **M7.7-H0 DONE -- PROVENANCE: the `$96AE` cold-start relocation.**
  FIRST IN H because H4, H5, H7 and H8 all assert cell values painted from bytes
  that, until now, the project would have read from the wrong place.
  **THE LOAD IMAGE IS NOT THE RUN IMAGE OVER `$5B00..$61A7`.** 1,704 bytes arrive
  there from `$E000` once at cold start (`$96A5 LD HL,$E000 / LD DE,$5B00 /
  LD BC,$06A8 / LDIR`), so every static read of the range out of the tape image
  AT ITS OWN ADDRESS is wrong -- by 1,385 of 1,704 bytes.
  **AND TRAPS #43's ALL-ZERO GUARD PASSES ON IT.** `image_tape.bin[$6180..$61A7]`
  is **36 of 40 NON-ZERO**, so "is this range sourced?" answers YES and hands you
  the wrong forty bytes. They are STACK: `$5BB0` does `LD SP,$61A7`, and MEASURED
  from build/boot.pkl, 226,384 writes land in `$6100..$61A7` over 200 front-end
  frames -- EVERY ONE from the ROM, ZERO from the game's own code. The item bank
  two pages down is the mirror image of the same trap: `$5C00..$6100` IS all
  zero, which made it look unsourced when its source simply sits 32K away at
  `$E200`. **"The range is sourced" and "the range is correct" are different
  claims, and the guard only ever answered the first.**
  THE BUILDER IS ALSO INVISIBLE IN THE LIVE DUMP. `$8CC4 LD SP,$96DD` puts the
  stack over `$96A5..$96DC`, so disassembling `build/image.bin` there yields
  `POP HL / RST $38 / NOP` and an analyst concludes the routine does not exist.
  It has to be read from `build/image_tape.bin` -- TRAPS #41's cousin: the right
  FILE matters as much as the right index.
  MEASURED ON THE MACHINE, from build/title.pkl with the whole destination
  POISONED and SP pinned OUTSIDE the write range: **1,704 writes, EVERY ONE from
  PC `$96AE`, contiguous**, and nothing left poisoned but the five bytes that are
  `$5A` IN THE SOURCE. **And it is a COPY, not a coincidence**: poke the source
  `$E680`/`$E681` to `00 99` and `$6180`/`$6181` read back `00 99`.
  THE INFERENCE RESTS ON UNIQUENESS: the run image's `$6100..$61A7` occurs at
  EXACTLY ONE address in the whole 64K tape image, and it is `$E600`. A match at
  two addresses would prove nothing about which was copied.
  AND THE 35 BYTES WHERE THE COPY DIFFERS FROM THE LIVE DUMP ARE EXACTLY THE TWO
  LIVE CARVE-OUTS -- `$5B14-$5B1F` and `$5CE0-$5CFB` -- which **closes a reading-
  pass open question**: those twelve bytes are precisely what `$8390` writes and
  `$A36C`'s twenty-byte clear does not reach, and the rest is I10's sparkle
  table.
  **THE TILE IS BITMAP ONLY -- AND MY FIRST EXPERIMENT SAID THE OPPOSITE.**
  Poking the forty tile bytes, rebuilding, and diffing the colour shadow against
  its PRE-BUILD state reports 752 changed bytes on every round, because `$7F62`
  rewrites it whether the tiles were touched or not. That number says nothing
  about the tile and would have "proved" it reaches collision. WITH A CONTROL --
  build the same round TWICE from the same world, once with the tiles poked --
  the shadow BITMAPS differ by 1,279 to 2,752 bytes while the ATTRIBUTE file and
  the COLLISION shadow are IDENTICAL on all four rounds. So the tile never
  reaches `$79AC`'s transform and H3's bit-5 rule does not depend on it.
  THE BUILD COUNTERS ARE NOT THE ROUND. `$82D7` and `$83EC` each advance by ONE
  PER BUILD, and `($860D)` = `$6180 + 8 * index` follows `$83EC` alone. On rounds
  15..19 the index fits `(round + 1) mod 5` exactly -- and BREAKS at the warp
  round, where `$8609` jumps by **+62** while `$83EC` advances by 1. The
  divergence is EXACTLY ONE ROUND WIDE, which is why only a CHAINED sweep across
  a milestone warp can separate the two models. Seven of this repository's own
  saved states already violate the identity (r6_48..r60_48 all carry
  `$83EC` = 2), so a port recomputing the tile from the round is wrong in worlds
  already on disk.
  TWO MUTATIONS SURVIVED THE FIRST BATTERY AND BOTH WERE MY OWN ERRORS. One was
  BADLY TARGETED -- it moved the relocation past `const r = this.A.render`, which
  only READS the asset, while the shadow load is further down inside `if (r)`.
  The other was EQUIVALENT UNDER MY OWN STRUCTURE: the engine loaded the asset AT
  `BB_RELOC.SRC` and copied FROM `BB_RELOC.SRC`, so changing the constant moved
  both together and a wrong source address still produced a right answer. The
  asset now declares its OWN address, which is what made "the source is `$E100`"
  observable at all; the inverse edit is withdrawn as equivalent while the two
  agree, and the gate asserts the AGREEMENT instead.
  New tools `tools/provenance.py` and `tools/extract_reloc.py`, new asset
  `build/reloc.json`, new fixture `build/provenance_fixture.json`.
  Mutation battery 695/695 killed, ZERO survivors (+12 for H0, one
  withdrawn as equivalent and one re-targeted). bb.test 444 -> 462.
- [x] **M7.7-H2 DONE -- THE DISCARD: `$8216`, and why no scroll gate may check the end state.**
  This increment exists so the ones after it cannot lie.  `$7F4E` CALLs `$8216`
  three instructions after the scroll loop exits, and `$8216` repaints the whole
  playfield out of the shadow -- so **whatever the scroll drew is thrown away**.
  **THE RESULT IS STRONGER THAN THE READING PASS'S.**  Its anchor was "0
  differing display bytes on rounds 2, 3, 21, 45", which was true only of the
  rounds it sampled and silent about why.  With the pair properly isolated --
  chain to N-1, SAVE THE WHOLE MACHINE, build once unpatched, restore, build
  again with `$7F34` patched `28 18` -> `18 18` so no round ever scrolls -- the
  **SHADOW and the COLOUR SHADOW come out BYTE-IDENTICAL on all six rounds**, 0
  of 6,144 and 0 of 768.  The scroll's output is discarded COMPLETELY from both
  buffers the port models, while the scrolled build costs 71% to 360% more T.
  AND ROUND 3's 53 DISPLAY BYTES ARE NOT THE SCROLL.  They are two SETTLING
  ENEMIES two pixels apart: the longer build let the hurry timer tick once more
  (54 against 53), so the ISR ran the settler one extra time.  Slots 4 and 5 at
  Y=56 against Y=54, at X=48 and X=192 -- exactly the columns the differing
  bytes fall in.
  SO AN END-STATE SCREEN GATE PASSES A PORT WITH: no scroll at all, a backwards
  scroll, a wrong-speed scroll, the wrong filler tile, the wrong attribute source
  in `$8447`, the wrong pre-roll count, or a pixel-smooth scroll.  **The scroll
  increment must gate MID-SCROLL snapshots.**
  THREE OF MY OWN ERRORS SURFACED ON THE WAY.  (1) My first pair ran TWO WHOLE
  CHAINED GAMES, one patched throughout, which I called a stronger claim -- it is
  a CONFOUNDED one, because suppressing the scroll changes every later build's
  timing and the games DRIFT; rounds 3 and 45 came back with 53 and 236 bytes
  differing for reasons unrelated to the discard.  (2) Measuring `$8216` with
  INTERRUPTS ON gave 6,208 bitmap writes instead of 5,632 -- 576 of the
  "repaint" was the interrupt handler running the entity render.  (3) My
  `roundDigits` missed that **`$7FBA` writes `$F841` inside the SHARED glyph
  routine**, so the tens call writes it too and `$7FA0` adds `$F840` on top:
  that is why a suppressed round makes ONE colour write and round 10 makes
  THREE, and a model with the write in the tens branch alone gives a suppressed
  round none.
  TWELVE MUTATIONS SURVIVED THE FIRST BATTERY, in three groups.  EIGHT were one
  gap: the gate compared only `$9A0E`/`$9A0F`, the two ASCII cells, because the
  glyph pixels are the declared font departure -- but the ADDRESSES can be
  compared and so can the colour bytes, and without them the whole draw side was
  ungated (eight rows instead of seven, a row too high, the wrong buffer, either
  colour write missing).  TWO were negatives nobody checked: a 24-row repaint
  lands on table entries `$0000`/`$0020`, **dropped on the Spectrum but stored
  happily by a `Uint8Array`**, and a 768-byte attribute copy runs PAST the
  attribute file into `$5B00`, the wall-texture scratch.  The engine now has the
  ROM guard the machine gets for free.
  AND THREE WERE PROVABLE EQUIVALENTS, withdrawn and labelled: **22 rows against
  24 is unobservable in RAM** (both do 5,632 writes; it differs only in time),
  and BOTH eight-bit walks can never wrap for any row this table holds -- the
  high byte tops at `$57` and the low byte at exactly `$FF`.
  ONE LAST TRAP, FROM THE OTHER SIDE: proving the digits are drawn AFTER the copy
  cannot use a glyph byte, because **the substitute font has ZERO ROWS** and
  "drawn" and "not drawn" are the same byte at some cells.  The COLOUR byte
  works: `$F841` reads 7 while its display counterpart `$5841` still holds the
  pre-copy `$47`.
  New tool `tools/discard.py`, new fixture `build/discard_fixture.json`.
  Mutation battery 720/720 killed, ZERO survivors (+25 for H2, three withdrawn
  as provable equivalents).  bb.test 462 -> 484.
- [x] **M7.7-H3 DONE -- THE COLLISION TRANSFORM: the palette `$82D6` and `$79AC` -> `$7C43`.
  THIS IS WHERE M7.1 BINDS.**
  **THE LOAD-BEARING FACT IS AN INEQUALITY, NOT A BIT.**  For ALL FIFTEEN palette
  indices `OPEN & $38 == 0` and `SOLID & $38 != 0` -- that is what makes
  `$7C43`'s test a collision map at all.  Bit 5 being set in SOLID is true for
  exactly indices 4 (`$66`) and 6 (`$65`) and is an accident of two bytes, so
  **"bit 5 means solid" is TRUE of the RAW build attributes on a minority of
  rounds and FALSE on the rest**, and becomes universally true only AFTER the
  transform.  A bit-5 gate therefore passes whether `$79AC` ran or not, on
  whichever class of round it happens to use.
  **`$7C46` IS `LD BC,3`, A SIXTEEN-BIT LOAD THAT SETS B TO ZERO ITSELF** -- so
  the inner DJNZ runs 256 times and the outer three: 768 cells.  A port reading
  it as "three" converts three and leaves 765 raw attributes behind, and on those
  same eleven rounds a bit-5 gate cannot see that either.  The gate therefore
  asserts the FULL 768-BYTE OUTPUT and drives both a bit-5-clear palette and a
  bit-5-set one.  (TRAPS #45, and the interesting half is that it is NOT
  caller-dependent -- the instruction sets B itself.)
  **TWO WRITERS, AND A SEED OF `$47` HIDES ONE.**  `$7C4C` stores `(v & $38)` on
  every cell; `$7C4F` overwrites it with `$20` only where that was non-zero.
  `$47 & $38 == 0`, so with that seed every cell takes the `JR z` path and
  `$7C4F` NEVER FIRES -- which is exactly how an earlier pass censused three
  writers and lost one entirely.  Driven on BOTH sides: 768 + 768 for
  `$57`/`$66`/`$65`/`$FF`, 768 alone for `$47`/`$46`/`$45`/`$00`.
  A REAL BUILD REPRODUCES EVERY SHIPPED STATE'S MAP 768 OF 768 -- round 1
  included, which needs `$8609` := 0 and no shipped state carries, so F0's
  chained recipe supplies it.
  **`$81C3` IS THE CEILING AND IT IS LOAD-BEARING.**  Row 0 comes out solid
  except columns 9-12 and 19-22, and poking `$81C3` to `$C9` makes the gaps
  VANISH.  The reading pass originally told the gate to prove the port need NOT
  implement it.  AND THAT MUTATION ONLY SHOWS WITH THE CEILING ROWS POISONED
  FIRST: `$82D6`'s fill starts at `$F840`, ROW TWO, so rows 0 and 1 are written
  by `$81C3`/`$81E1` ALONE, and left as the previous build made them "drew the
  ceiling" and "did nothing" are the same picture -- which is what my first
  attempt measured, with the patch changing nothing.
  **THE PLAY ROW DID WHAT IT WAS REWRITTEN TO DO.**  `round1_48` and `water` are
  BOTH ROUND `$01` and differ by 632 writes to ZERO; `r50_48` and `boss` are late
  rounds with none.  The only writers are `$B8C0` and `$B6D6`, the bubble-
  occupancy pair, and EVERY ONE of their writes preserves bits 5, 6 and 7 across
  all eight worlds and 240 frames each.  So **"rounds >= 2" is itself a false
  model** -- the writers fire whenever a BUBBLE HOLDS A CELL, which is not a
  function of the round -- and a round-1-only version of this row is the exact
  disease the revision existed to catch.
  TWO MUTATIONS SURVIVED THE FIRST BATTERY, both the same gap: the palette gate
  poisoned and checked only the 704 bytes the fill writes, so a fill starting a
  row EARLY (over the ceiling) or running a row LONG (past the map) looked
  identical.  Now MEASURED rather than assumed: exactly 704 writes, `$F840` to
  `$FAFF`, with both neighbourhoods asserted untouched.
  AND THE GATE CAUGHT ONE OF MINE: the fifteen palette bytes were declared as a
  constant and never LOADED, so the engine read zeros from `$858C`.
  New tool `tools/collmap.py`, new fixture `build/collmap_fixture.json`.
  Mutation battery 746/746 killed, ZERO survivors (+26 for H3).
  bb.test 484 -> 499.
- [x] **M7.7-H4 DONE -- THE BUBBLE DRIFT FIELD: bits 6/7 and `$B8DB`.**
  **THE READING PASS NEARLY LOST THIS SUBSYSTEM TO A GREP.**  It searched for
  `AND $40` and `AND $80`, found almost nothing, and inferred bits 6-7 were
  unread.  The grep was accurate and the inference was wrong: the read is
  `$B847 RLCA / RLCA / RLCA / $B84A AND 6`, a TRIPLE ROTATE that lifts bit 6 to
  bit 1 and bit 7 to bit 2 -- so the code comes out ALREADY DOUBLED and indexes
  the byte-pair table at `$B8DB` directly.  Codes 0/2/4/6 give UP, RIGHT, DOWN,
  LEFT.
  SO THE COLOUR SHADOW HAS **THREE** LIVES: bits 0-4 a live per-cell bubble
  occupancy claim, bit 5 the static SOLID flag (H3), bits 6-7 a STATIC PER-ROUND
  DRIFT DIRECTION.
  **THE TABLE WAS ALREADY IN THE PORT.**  `BB_DRIFT`, extracted in M7.5 as the
  bubble WIND table, is byte for byte `$B8DB` -- the same four deltas serve the
  wind push (indexed 2 or 6 by the player's facing) and the map drift (indexed by
  the cell), plus the `(0,0)` pair at `$B8E3` that `$B968` uses to null a wind.
  I had written a duplicate before noticing, and removed it.
  **THE PAINTER IS DEFERRED AND NAMED.**  `$7C57-$7E4A` -- three fixed
  rectangles, a per-round compressed stream at `$79AF` with sixteen `$Fx`
  redirects, a mirror, four doors and a rotating pattern table -- is not
  transliterated.  The FIELD is captured per round instead and carried as a
  declared asset (81 rounds x 192 bytes, two bits a cell), exactly as `$5D00`'s
  item bank is carried until its builder is found.  WHEN THE PAINTER LANDS THE
  ASSET GOES, rather than staying as a cross-check.
  MEASURED: the field is SEED-INDEPENDENT (the same round with the map pre-seeded
  eight ways gives the same 768 codes, so the painter reads nothing from the map
  it writes); round 81 has ZERO cells of code 3, the mirror being skipped at
  `$7C89`; and **ROUND 45 IS THE ONLY ROUND that paints outside the map** -- 15
  cells from PC `$7E3E` -- so the port's choice to bounds-check is a DECLARED
  DEPARTURE with exactly one round where it shows.
  **AND THE RULE THIS INCREMENT EXISTS TO WRITE DOWN.**  Flip bits 6/7 across the
  whole map in r6_48 and run **80 frames: IDENTICAL**, which reads as "nothing
  reads them".  Run **600 and it diverges at frame 108** -- the frame the first
  bubble reaches the drift stage (r10_48 109, hurryup 128).  **ANY "UNREAD" CLAIM
  IN THIS PORT MUST CARRY THE FRAME COUNT THAT MADE IT TRUE.**
  AND THE FRAME COUNT IS NOT SUFFICIENT EITHER: round1_48 says "unread" at 600
  frames as well, because no bubble ever reaches the drift stage there (0 reads
  in 600 frames) -- while **`water`, WHICH IS THE SAME ROUND `$01`, diverges at
  frame 1** (361 reads).  What decides it is whether the WORLD exercises the
  path, not how long the run is and not which round it is.  The CONTROL mutation
  on bit 5 diverges at frame 0 or 1 in every world, which is what makes the
  negative worth anything.
  THREE MUTATIONS SURVIVED THE FIRST BATTERY, all mine and all familiar shapes.
  EVERY `y` I drove was a MULTIPLE OF 8, so `y & $F8` and `y` were the same
  number and the mask was invisible.  I ZEROED THE MAP before applying the field,
  which makes "OR in" and "write over" the same operation (TRAPS #44) -- it is
  now seeded with bit 5 set and a low-bit pattern, and the gate asserts the low
  six bits SURVIVE.  And I compared a CODE CENSUS rather than the cells: reversing
  the four cells packed into each byte permutes placement while leaving every
  count identical, so the census could not see it.  Now compared CELL BY CELL.
  New tools `tools/drift.py` and `tools/extract_drift.py`, new asset
  `build/drift_field.json`, new fixture `build/drift_fixture.json`.
  Mutation battery 766/766 killed, ZERO survivors (+20 for H4).
  bb.test 499 -> 512.
- [x] **M7.7-H5 DONE -- THE OCCUPANCY FIELD: bits 0-4, and the shared probe `$AE81`.**
  The THIRD life of `$F800-$FAFF`.  H3 settled bit 5 (SOLID), H4 bits 6-7 (the
  per-round DRIFT); bits 0-4 carry the SLOT NUMBER of the bubble sitting there.
  **IT CORRECTED THE READING PASS TWICE.**  `$BFF7` is not the mystery the plan
  calls it ("writer UNIDENTIFIED", "value MOVES WITHIN A FRAME"): its writers are
  `$B63C` and `$B674` and its values run 0..12, because it is the bubble
  manager's own SLOT COUNTER.  It moves within a frame because it IS the loop
  index, which is why the marker stored in a cell is `12 - slot` and why `$AEAD`
  inverts exactly that to find the bubble.  And the CHANGED-BIT MASK SET the plan
  first predicted, `{$01,$06,$0A,$0B,$0C}`, is not the machine's: `$01` NEVER
  occurs in over a thousand writes while `$00` (a same-value write-back) and
  `$07` do.
  **ONE PROBE, TWO MASKS, TWO MEANINGS.**  `$AE7F` passes `C = $3F` (solid OR
  claimed -- "can a bubble go here?") and `$AD35` passes `C = $20` (solid alone
  -- "is there a floor here?"), and both fall into the same body at `$AE81`.  A
  port with a single "is this cell solid?" helper answers one of the two wrongly
  everywhere a bubble is sitting.
  **AND E IS NOT A BOOLEAN.**  It comes back as one of three things: 0 for free,
  1 for SOLID (which SHORT-CIRCUITS at `$AEA0` before the IY test happens), and
  for a CLAIMED cell with `(IY+8)` bit 1 clear, **`10 * (12 - marker)` -- the
  POOL OFFSET of the bubble holding it**, which is how one bubble finds another.
  With that bit SET it instead marks the ASKING bubble, `(IY+9) := 1`, and
  `$AEAB POP HL / RET` **ABANDONS ITS CALLER** -- the fourth routine in this game
  to return past its own frame, after `$B679`, `$88B1` and `$89B7`.
  **AND A CLAIMED CELL DIVERTS THE DRIFT INTO THE RNG**: `$B87D`/`$B888` test
  with `AND $1F` and, if either is claimed, `$B88D` draws `LD A,R / AND 6` -- the
  same 0/2/4/6 code space H4's field uses, from the refresh register instead of
  the map.  So H4's answer is the direction a bubble takes ONLY when the cell it
  wants is free.  Asserted as a FUNCTION over all 256 values of R (TRAPS #46).
  **THE FIRST SURVIVOR IN THIS STRETCH THAT WAS AN ENGINE DEFECT, NOT A GATE
  GAP.**  `$AE86 LD D,E` overwrites D with the incoming X three instructions
  before `$AE92 LD A,D / AND 6`, so the THIRD CELL IS GATED ON X, NOT Y.  I wrote
  `y & 6` and it survived a battery because every case I drove had X and Y BOTH
  8-ALIGNED, which makes the two expressions agree.  The separating pair is now
  in the fixture: "Y unaligned but X aligned" is NOT reached, "Y aligned but X
  unaligned" IS.
  THE OTHER FIVE SURVIVORS HAD ONE ROOT CAUSE -- **one cell position for every
  case** -- which made three properties structurally invisible: the EIGHT-BIT
  `INC L`, the second and third cells being tested with the caller's mask (I only
  ever filled the first), and the marker's FIVE-BIT mask (markers 7 and 12 both
  fit in four bits; `$15` and `$1F` separate `$0F` from `$1F`, giving 166 and 66).
  AND THE WRAP TOOK THREE ATTEMPTS.  The end of a ROW is not enough -- `x=$F8,
  y=$60` gives base `$F99F`, low byte `$9F`, and both models agree.  A PAGE
  boundary is needed (`y=$38` -> base `$F8FF`).  And the decoy proving it was
  FOLDED ONTO THE WRAP TARGET by my own seeding formula, which deliberately
  addresses cells the way the machine does; it only works as an ABSOLUTE poke --
  claim at `$F900`, `$F800` empty, and the machine returns 0 because it wrapped
  and never looked.
  Two traps while measuring, both recorded: I drove the probe WITHOUT AN IY,
  which read every case as free and made the two masks look identical; and my
  first claimed-cell case used MARKER 12, which resolves to slot 0 and therefore
  offset ZERO -- indistinguishable from a free cell.
  New tool `tools/occupancy.py`, new fixture `build/occupancy_fixture.json`.
  Mutation battery 787/787 killed, ZERO survivors (+21 for H5).
  bb.test 512 -> 529.
- [x] **M7.7-H1 DONE -- THE TRANSITION SPINE `$97F8`: the pixel census, the four
  painters, the `$9AC1` walk and the EXPIRY of the diamond pin.**
  F0 had already taken the round-class census, the warp table and the `$8609`
  sweep, so what was left here was the part the reading pass got WRONG.
  **IT SAID "NO PIXELS AT ALL" AND THAT IS RETRACTED.**  The transition paints
  the display in FOUR places the spine never names, and all four run AFTER
  `$8216` -- which matters precisely because H2 proved `$8216` DISCARDS the
  scroll.  Without counting them, H2's patch pair would be asserting over a
  display that three routines repaint after the discard.
  **THE CENSUS SPLITS AT THE FIRST `$8216`.**  Round 1 discards NOTHING -- zero
  display writes before the repaint -- because `$7F34 JR z` sends it straight
  past the scroll.  Rounds 2, 5, 56, 72, 80 and 81 each discard **163,872**,
  IDENTICALLY: the scroll costs the same whatever it is drawing over.  What
  SURVIVES is not round-independent -- round 81 keeps an order of magnitude
  fewer than the rest, because it has no banner.
  **THE FOUR PAINTERS**, each bracketed by its own stack frame: `$7FC0` runs on
  ROUND 1 ONLY (488 display + 129 attribute -- the HUD text and both score
  panels); `$806C` runs EVERY round and scales with LIVES, not with the round or
  with P2 (32 bytes on rounds 1/2/5, 48 on 56/72/80/81); `$957E` is CALLED every
  round and writes NOTHING in a fresh build, because it walks the collected
  EXTEND bits and none are set -- **a gate that only counted writes would
  conclude it is never called**; and `$9904`, IN NO LIST IN THE READING PASS,
  runs TWICE per round (160 display + 20 attribute each time, the banner
  restore).
  **THE `$9AC1` WALK IS NINETEEN POINTERS, AND THE TABLE IS NOT ONE OF THEM.**
  Exactly 19 writes, every one from PC `$9855`, every target ending zero -- and
  `$9AC1..$9AE6` itself untouched.  Seeded to `$FF` first, because most of those
  targets are ALREADY ZERO when a round ends and "written" and "already 0" would
  otherwise be the same observation.  A port that also zeroes the table is green
  on round 1 and writes nineteen bytes into ROM on round 2.
  **AND `$9891` UNDOES `$88E0`'s DIAMOND PIN EVERY SINGLE ROUND.**  The pin was
  set before every build (I6's `$09/$00/$FF`, which zeroes the generator's INC A
  OPCODE at `$8BA0` and widens the mask) and every round handed back
  `$FF/$3C/$07`: `LD HL,$3CFF / LD ($8B9F),HL` restores the counter AND the
  opcode in ONE sixteen-bit store, then the mask goes back.  **The diamond pin
  lasts exactly one round.**  I6 measured the pin and I9 measured the generator;
  NEITHER COULD SEE THAT IT EXPIRES -- it took a third increment spanning both.
  A second negative with it: the sparkle table is cleared TWICE, 24 bytes by
  `$989C` and 28 by `$BF53`, and `$5CFC..$5CFF` comes back UNTOUCHED by either --
  those four bytes hold live runtime-built data (`00 FC 3F C0`) that a 16-slot
  table picks up as a particle, which is exactly the runaway walk I10 measured.
  `$D380` is recorded as an OBSERVATION and deliberately NOT frozen: on the
  group-3 rounds `$7E0E` is redrawn from `LD A,R`, so two builds of the SAME
  round differ in up to 69 of 384 bytes.  An md5 in the fixture would turn this
  gate red on a coin toss.
  TWO HARNESS ERRORS, both mine: I keyed the painter census by WRITING PC and
  looked the rows up by ENTRY address (found nothing), and I armed `$984B` as a
  routine when it FALLS THROUGH into the whole build (75,708 writes for a step
  that makes 19).
  FOUR SURVIVORS.  Two real gaps: a walk of TWENTY pointers, invisible to any
  check on the nineteen named targets -- closed by COUNTING the writes through a
  recording Proxy; and a tail that never calls the collision transform, closed by
  seeding the colour shadow with a value the transform CHANGES (`$57` -> `$20`),
  since over an unseeded shadow "it ran" and "it did not" are the same end state.
  **The other two are PROVABLE EQUIVALENTS and are withdrawn**, not papered over:
  the tail's three steps write `$8B9F..$8BA2`, `$5CE0..$5CF7` and `$F800..$FAFF`
  -- measured DISJOINT, not one byte shared -- so no permutation of them is
  observable.  The order is kept because it is the machine's, and the code is
  labelled TRANSCRIBED-NOT-EXERCISED.
  New tool `tools/roundadv.py`, new fixture `build/roundadv_fixture.json`.
  Mutation battery 804/804 killed, ZERO survivors (+17 for H1, 2 withdrawn).
  bb.test 529 -> 546.
- [x] **M7.7-H6 DONE -- THE ELEMENT CLASS `$7E0E`: `$7DD6`'s four lists, and
  where the eight randomised classes actually go.**
  `$79AC`'s tail is the collision transform (H3), the drift painter (H4), and
  then -- **BY FALL-THROUGH, with no `CALL $7DD6` anywhere in 64K** -- a
  per-round ELEMENT CLASS that **49 of 81 rounds have and the port modelled none
  of**.  That missing caller is why a caller scan finds nothing and why the
  reading pass filed the whole thing under "`$79AC`'s map pass".
  **IT IS A WALK, NOT A LOOKUP.**  `$7E4B` holds four `$00`-separated lists of
  round numbers, **11 / 10 / 13 / 15** long, and the class is the list's index
  PLUS TWO: 2 WATER, 3 LIGHTNING, 4 FIRE.  A round in no list gets
  `($FE + 2) & $FF` = **ZERO, not 4**.  The fourth list does not give 5 either:
  `$7DF3 CP 5 / JR nc` sends it to `$7E04 LD A,R / AND 7 / ADD A,5`, so those
  fifteen rounds draw one of **EIGHT** values 5..12 that differs BUILD TO BUILD.
  The 53-byte table PREDICTS F0's chained-build measurement on all 81 rounds with
  zero mismatches, which is two independent routes to the same answer.
  **THE NAMED NEGATIVE PAID OFF AND THEN CORRECTED ITSELF.**  `$7DE1 INC (HL) /
  DEC (HL)` is a ZERO TEST THAT STORES -- twice for every entry examined, always
  from PCs `$7DE1`/`$7DE2`, always restoring -- so a write-watch over
  `$7E00-$7F00` reports self-modifying code that is not there.  The plan named
  "70 phantom self-modifications"; **70 is the MAXIMUM FOR GROUP 2, not the
  number.**  The count is a function of the round's POSITION IN ITS LIST and runs
  **0 to 106** -- 0 for round `$05`, the first entry of the first list, and 106
  for every round in no list.  A single figure would have been a sample, so the
  gate asserts the whole range and the table's byte-identity afterwards.
  **ROUND 81 NEVER REACHES ANY OF IT.**  `$7C89 CP $51 / RET z` returns out of
  the entire tail, so the treasure room inherits round 80's class.  Asserted with
  a poison value no code path writes, against rounds 80 and 5 through the SAME
  driver -- "stale" is only a fact if a neighbour is seen being written.
  **A CORRECTION TO THE READING PASS: `$9E75` DISPATCHES THREE CLASSES, NOT
  TWO.**  The pass read `SUB 2 / JP z,$A159 / DEC A / JR z,$9E85` and stopped
  there; the next two instructions are `DEC A / JP z,$9F63`.  Driven per class:
  2 -> `$A159`, 3 -> `$9E85`, 4 -> `$9F63`, and 0, 1 and every randomised class
  fall through to RET.
  **AND THE PLAN'S OPEN QUESTION IS CLOSED: THE EIGHT RANDOMISED CLASSES ARE THE
  EXTEND LETTERS.**  It asked this increment to find where 5..12 go or say it did
  not.  They go two places, and the two agree:
  - `$7E80` patches TWO IMMEDIATES before either of its gates -- `$7EFB`, the
    operand of `LD (IY+9),n`, takes the CLASS ITSELF, so an elemental bubble is
    spawned CARRYING its class as its state byte; and `$7EB2`, the operand of a
    `CP n` bubble-count throttle, takes **4 for classes 1..4 and 1 for classes
    5..12** -- the randomised classes spawn under a four times tighter throttle.
  - A popped bubble's `(IY+9)` rides out through `$B742` to `$FFF9`, and
    `$B75C CP 5 / CALL nc,$B7E5` sends everything from 5 up to the EXTEND award,
    which does `SUB 5` and indexes a bit-mask table at **`$B80E`**: bits
    `0,1,2,3,4,5,0,5`.  `$957E` draws **SIX** letters (its `LD A,6` over a 6-bit
    field at `$FDE3`/`$FDED`), so eight classes fold onto six bits -- **classes
    11 and 12 ALIAS 5 and 10, which makes E and D twice as likely (2/8) as X, T
    and N (1/8)** under a uniform `AND 7`.
  **AND A SECOND, INDEPENDENT ROM FONT DEPENDENCY -- a new DECLARED DEPARTURE.**
  `$BF74` indexes a word table at `$C068` by `(class - 2)` and ORs the 8-byte
  glyph it points at into the flashing-bubble bank at `$D38C`.  Classes 2/3/4
  take RAM icons at `$B614`/`$B61C`/`$B624` -- a wave, a bolt and a flame, which
  is where the M5 captures' "elwater 2, ellight 3, elfire 4" comes from.
  **CLASSES 5..12 TAKE SPECTRUM ROM CHARACTER-SET CELLS**: `'e','x','t','e','n',
  'd','e','d'`.  The port substitutes drawn letters exactly as the HUD font does.
  That the two aliased classes point at the SAME TWO ROM LETTERS as the classes
  they alias is what makes the 8->6 fold a fact rather than a reading -- two
  unrelated tables agreeing.
  **AND CLASS 0 IS NOT INDEXED OUT.**  `SUB 2` gives `$FE`, `ADD A,A` gives
  `$FC`, so the 31 rounds in no list read the word **252 BYTES PAST** the eleven
  entries, at `$C164`, and overlay whatever it points at.  Measured and recorded,
  not repaired: a port that clamps the index draws a different bubble on 31
  rounds.
  SEVEN SURVIVORS, all gate gaps of mine, three root causes and no engine
  defect.  (i) THE WRITE LOG WAS FILTERED TO THE TABLE, so a walk that scans a
  fifth list runs off the end of `$7E4B..$7E7F` and writes where the filter was
  not looking -- the same mistake as checking a pointer walk's named targets in
  H1.  The range is now an ASSERTION on the addresses, not a filter on the log.
  (ii) MEMBERSHIP IS NOT A TEST OF A DRAW: "between 5 and 12" is satisfied by a
  constant 5, by a six-bit mask giving only the odd values, and by no redraw at
  all, and all three survived.  The gate now drives 400 builds of a group-3 round
  and demands ALL EIGHT values.  (iii) THE TWO CLASS TABLES WERE COMPARED FIXTURE
  TO FIXTURE -- nothing ever read what the ENGINE had put in its world, so three
  mutations to its own constants survived, including deleting the seeding loop.
  New tool `tools/elemclass.py`, new fixture `build/elemclass_fixture.json`.
  Mutation battery 829/829 killed, ZERO survivors (+25 for H6).
  bb.test 546 -> 567.
- [x] **M7.7-H7 DONE -- THE ROUND-RECORD WALKER `$848C`: 81 maps, one
  continuous bit stream each, and the mirror that only 49 rounds can prove.**
  **THE ASSET-EXTRACTION BINDING.**  If this decode is wrong the port ships 81
  wrong maps, and because they are PLAUSIBLE-LOOKING maps nobody notices until an
  enemy walks through a floor.  So nothing here is compared by count: every
  measured round is rebuilt CELL BY CELL against a Python walk, and the cells the
  walker was not supposed to touch are counted separately.
  **THE STRUCTURE.**  `$8529` probes bit `7 - (i & 7)` of byte `$8543 + (i >> 3)`
  -- MSB FIRST -- and `$9F5C` is `RRA/RRA/RRA/AND $1F`, where the carry-in can
  only reach bits 5-7 and the mask kills them, so it is `(i >> 3) & $1F` whatever
  the flags hold.  A SET carry means a **39-byte SHORT** record painted 14 wide
  and MIRRORED; a clear one a **77-byte LONG** record painted 28 wide.
  **AND THE BIT BUDGET CLOSES ON THE NOSE, which is WHY those are the sizes:**
  LONG is 22 x 28 = 616 bits = **77.0 bytes exactly**; SHORT is 22 x 14 = 308
  bits = 38.5 -> **39 bytes with four bits spare**.  51 short + 30 long = 4,299,
  so the table runs `$61A8..$7272` with **eight bytes of slack** before `$727B`
  and round 81's record sits at `$7226` -- every number the plan predicted.
  **THE BIT CURSOR DOES NOT RESTART EACH ROW.**  E (bits left in C) is PUSHed and
  POPped around the row advance at `$84FE`/`$8504` precisely so that it SURVIVES.
  A short record's 14 bits a row means row 1 starts at bit 14 and only every
  fourth row lands on a byte boundary, so **a port that re-aligns per row is
  right on row 1 and wrong from row 2 onward** -- and it still produces a map.
  **THE TWO LOOP CONSTANTS ARE SELF-MODIFIED OPERANDS**, `$84E5` (28 or 14) and
  `$8500` (4 or 18), and 28+4 = 14+18 = 32, a whole attribute row either way.
  A build of one class NEVER writes the other's pair -- which is visible in the
  shipped images themselves: `image_tape.bin` holds `$1C`/`$0004` and the
  round-80 dump holds `$0E`/`$0012`, caught on opposite branches.  Round 1 is
  SHORT and round 81 is LONG, so both are built and both pairs gated AS STATE.
  **THE MIRROR IS REVERSED** -- columns 2..15 onto 29..16 -- **and I first
  measured its observability wrong.**  My initial metric counted rounds with a
  left-right asymmetric finished map, got 30, and that number is simply "the 30
  LONG rounds": a short round is symmetric BY CONSTRUCTION, because the mirror is
  what makes it so.  It proves LONG does not mirror and says NOTHING about the
  reversal.  The reversal is separable only on a SHORT round with a
  NON-PALINDROMIC row -- **49 of the 51**, disagreeing with a straight mirror in
  **3,352 cells**.  The third model, "28 wide with no mirror", is refused by
  arithmetic on all 51: 22 x 28 needs 77 bytes and the record has 39.
  And the mirror falls out of the POKE too, through a byte nobody chose for the
  purpose: the same record byte set to `$00` moves **16 cells on round 1 and 8 on
  round 81**.  The poke is to `$00` and not `$FF` because round 1's first record
  byte IS `$FF` (TRAPS #44), and the expected changed set is COMPUTED from the
  original byte rather than asserted as a magic 16.
  **ONE SURVIVOR, AND IT WAS THE SAME GAP A THIRD TIME.**  A painter running 24
  rows instead of 22 paints all 616 cells correctly and then writes two more rows
  PAST `$FAFF` -- into the `$FB00` page H4 measured round 45's drift field
  spilling into -- and no check on the cells it was SUPPOSED to write can see
  that.  After H1's twentieth pointer and H6's fifth list, the rule is now
  unconditional: **an engine-side gate needs the write COUNT, because comparing
  the cells you expect is existential.**
  New tools `tools/roundgeom.py` and `tools/extract_records.py`, new asset
  `build/round_records.json` (4,299 bytes + the 11-byte bitmap), new fixture
  `build/roundgeom_fixture.json`.
  Mutation battery 861/861 killed, ZERO survivors (+32 for H7).
  bb.test 567 -> 583.
- [x] **M7.7-H8 DONE -- THE PLATFORM TILE AND THE WALLS: two write modes in one
  routine, and a loop cursor that lives in the callee.**
  H7 turned 81 records into 616 COLLISION cells; this turns those cells into
  PIXELS.  `$824A` blits 16x12 per solid cell over the shadow, and **it does not
  use one write mode**: the main eight rows STORE the left byte (`$8288`) and OR
  the right (`$828C`), while the four-row tail ORs BOTH (`$82A6`/`$82AB`).  The
  LAST map row SKIPS THE TAIL (`$8296 DEC L / JR z`), so a cell there writes
  SIXTEEN bytes and not 24 -- which is also why `(IX+2)` is never read past the
  end of the 22-entry row table.
  **`$856C` IS TWENTY-FOUR BYTES**, not eight and not sixteen -- it had been read
  all three ways.  DE runs CONTINUOUSLY through both loops, so ONE solid cell
  over a zeroed shadow makes 24 ordered writes and 24 DISTINCT seeds come back in
  order.  The `$A0/$50/$A0` at positions 1, 3 and 5 are `$824A`'s own entry
  patch, so the same measurement pins the buffer's SHAPE, its ORDER and the patch
  at once.  `$82C5` then fires EXACTLY ONCE, after the first map row, and moves
  three of those bytes to `$80/$A0/$40` -- which is why a platform's top row is
  drawn differently from its body.
  **THE ORDER DEPENDENCY IS REAL AND INVISIBLE TO EVERY COUNT.**  `$833B` is
  STATE *and* ARGUMENT: `LD A,$1E / XOR $1E` toggles it and the value IS the
  column, so the two `$833A` calls in a build draw columns 0 then 30 or 30 then
  0 depending on what the PREVIOUS build left.  The two orders differ in FIVE
  bytes, all in column 30, while leaving the non-zero counts in columns 30 and 31
  IDENTICAL.
  **AND $833A's ROW CURSOR IS ADVANCED BY ITS CALLEE.**  `$833A`'s own loop
  contains NO `INC IX` at all -- `$8375 INC IX / INC IX` sits inside `$836A`,
  after its DJNZ and before its RET.  Reading the loop alone says the wall is
  redrawn over the same two char rows eleven times, and I nearly transliterated
  exactly that; a register trace says IX runs `$FD44`, `$FD48`, `$FD4C` -- four
  bytes an iteration, because each of the two CALLs moves it twice.
  **TWO MEASUREMENT ERRORS OF MY OWN, BOTH CAUGHT BY CONTROLS.**  (i) The wall
  ORDER experiment first reported **1,556 differing bytes across all 32 columns**
  -- because the two builds ran SEQUENTIALLY and `$83EC` (the tile index) and
  `$82D7` (the palette index) are BUILD counters, not round numbers (H0), so the
  second build drew a different tile in a different colour.  Pinning every
  carried counter collapses it to the 5 bytes above.  (ii) `$8390`'s interleave I
  first read as two 16-byte halves; it is a LINEAR 32-byte fill of `hi, lo, hi,
  lo` per tile byte, because `$83D9` is CALLED TWICE and `$83C5..$83D3` then copy
  the pair forward with `LD A,(IX-2)`.  That produces the right 32 bytes in the
  wrong ORDER, and the gate caught it before the battery did.
  TEN SURVIVORS.  **Three are PROVABLE EQUIVALENTS, withdrawn with the proof**:
  `$827B ADD A,(IX)` and `$835D ADD A,$20` are eight-bit adds that CANNOT WRAP
  over any reachable input (row-table low bytes top out at `$E0` with a column of
  29, and `$833A` reads every OTHER entry, whose low bytes are `$40/$80/$C0/$00`
  with c in {0, `$1E`}), and my tail-cursor mutation set DE to where it already
  was.  Both adds are now labelled TRANSCRIBED-NOT-EXERCISED -- and a comment
  claiming the second "can wrap" was corrected.
  THE OTHER SEVEN WERE GATE GAPS: `$830B` had **no gate at all**; the wall was
  checked by COUNT and COLUMN but not by VALUE, so a uniform `$C7` buffer could
  not separate a STORE from an OR nor "reads `$5B00..$5B1F` once per ROW PAIR"
  from "restarts for each call"; `$82C5` is IDEMPOTENT, so "fires once" and
  "fires every row" leave the same three bytes and only a WRITE COUNT separates
  them; and -- **in the very increment that wrote TRAPS #54** -- I filtered the
  write log to the shadow again, so a tail drawn on the last map row, whose
  target comes from row-table entry 22 and therefore reads as ZERO, put eight
  writes near `$0000` where nothing was looking.
  New tool `tools/roundtile.py`, new fixture `build/roundtile_fixture.json`.  The
  tile's forty bytes need no asset: H0's `$96AE` relocation already carries them.
  Mutation battery 905/905 killed, ZERO survivors (+44 for H8, 3 withdrawn).
  bb.test 583 -> 604.
- [x] **M7.7-H9 DONE -- THE POST-`$8216` HUD FURNITURE: `$7FC0`, `$806C`,
  `$957E`, `$9904`.**  H1 retracted "NO PIXELS AT ALL"; these are the four
  painters it found, and every one needed something done to the world before it
  could be observed at all.
  **A CORRECTION TO THE PLAN: `$7FC0` HAS TWO REFERENCE SITES, NOT ONE.**  The
  plan scanned for `CALL` and `CALL z` and concluded `$7F58` was the only one.
  `$9998` is a **`JP $7FC0`** -- a TAIL CALL -- ending the PLAYER JOIN routine at
  `$9970`, which zeroes that player's four-byte score record, SETs the died flag
  at `(IY+$5A)` bit 7 (F0's warp suppressor), SETs `(IY+7)` bit 7 IN PLAY and
  gives three lives.  **So the HUD is repainted on EVERY JOIN as well as on round
  1**, and a port that paints it only on round 1 shows a stale HUD for the whole
  of a two-player game.  An opcode scan for `CALL` is not a scan for reachability.
  **THE MEASUREMENTS.**  `$7FC0` writes 1,227 bytes (488 display + 129 attribute
  + 32 shadow + 578 RAM) -- but it CALLs `$806C` at `$7FDF`, so 32 display, 32
  shadow and 4 attributes belong to the nested frame and its OWN display total is
  456.  `$806C` writes min(lives,5)+1 cells into display, shadow AND attributes,
  32 display bytes at 3 lives and 48 at 6, and **exactly doubles** with P2 in
  play.  `$9904` writes 80 display + 10 attributes per call, twice a round.  And
  **`$957E` writes SIX BYTES AND NO PIXELS AT ALL** in a fresh build -- rising to
  8 + 8 + 1 per set bit once `$FDE3`/`$FDED` carry the six bits H6 settled.
  **THE RRD LOOP RESTORES WHAT IT READS**: three RRDs per byte are a full turn,
  so "converts the score" and "consumes the score" are one observation unless the
  records are POKED APART.  HIGH := 12 34 56 78 gives `'78563412'` and all three
  records come back untouched.  And `$8072 LD BC,$08FF` is ONE instruction and a
  TRAPS #45 site: as shipped it writes eight bytes and BC never borrows, but
  poked to C = `$07` the same loop writes **263 bytes over `$85B1..$86B7`** --
  measured, not asserted.
  **FOUR MEASUREMENT ERRORS, ALL MINE, ALL IN THE RIG AND NOT THE
  TRANSLITERATION.**  (i) `$9904` TAKES ITS ADDRESS IN HL (`$484C`/`$488C`) and I
  drove it cold -- 0 display writes, 21 attributes, 103 scattered RAM writes, a
  census of nothing.  (ii) The censuses ran with INTERRUPTS ON: on round 5 the
  ISR fired mid-call and added twelve writes from `$B674`, H5's bubble-manager
  slot counter, so the same call measured 120 writes on round 2 and 170 on round
  5 with identical inputs.  H2 paid for this once already.  (iii) The
  "CONTROLLED" world seeded `$5000..$50FF` when a char row walks H from `$50` to
  `$57` -- **seven rows in eight were reading whatever the built world held**.
  (iv) **A DESTRUCTIVE EXPERIMENT DID NOT RESTORE THE WORLD IT WRECKED**: the
  `C = $07` runaway writes 263 bytes over the very record the other measurements
  read, and I restored the poked operand but not the damage, so everything after
  it was measured in the wreckage.
  (iii) and (iv) were caught by the ENGINE DIFFERENTIAL and nothing else -- the
  write COUNTS matched exactly (109 against 109) while the values from one cell
  on were fiction.  A census-only gate passes both.
  **AND THE EXTEND ROW IS THE SAME SIX ROM GLYPHS H6 FOUND.**  `$95D5`'s table
  points at `$3E28, $3EC0, $3EA0, $3E28, $3E70, $3E20` -- `e x t e n d` -- which
  are the SAME SIX ADDRESSES as `$C068`'s bubble table.  Two unrelated tables
  naming them, so one substitute font serves both: `tools/make_letters.py` draws
  six 8x8 glyphs and refuses to emit unless every one differs from the ROM's (36
  of 48 bytes do).  The gate compares ADDRESSES, never pixels, exactly as the
  score digits already do.
  ELEVEN SURVIVORS.  **Four are PROVABLE EQUIVALENTS, withdrawn with enumerated
  proofs**: `$80F6`'s row step (lives clamp to 5, so P1 walks `$50E0..$50E5` and
  P2 `$50FF..$50FA` -- no page crossing), `$80BC ADD A,$A0` (H runs `$50..$57`),
  `$9933 INC E` (both callers land at `$594C`/`$598C`), and `$80C0`'s patched
  operand against a fresh read of `(HL)` -- equal BY CONSTRUCTION, because the
  same byte was written to both one instruction apart.  *The related mutation
  "the operand is never patched" WAS killed, so the self-modification itself is
  gated.*  One more was a NO-OP of my own making and was rewritten.
  THE OTHER SIX WERE GATE GAPS, and all of one kind: **my controlled world was
  too tame to separate the models.**  Three needed worlds it did not build --
  SEVEN lives (clamp-at-5 gives six cells, clamp-at-4 five, no clamp eight), an
  attribute PAPER EQUAL TO THE INK (the only case that reaches `$80E0`'s `JR z`),
  and an EXTEND mask with bits 6 and 7 SET (a six-letter loop must ignore them).
  Two more: the font check asserted only that *something* non-background was
  drawn, so a port reading the absent ROM (zeros) and a port drawing one glyph
  six times both passed.  And the last was the familiar shape a fourth time -- an
  eight-letter loop reads a ZERO table entry and writes near `$0000`, outside the
  region the check filtered to.
  New tools `tools/hudfurniture.py` and `tools/make_letters.py`, new fixture
  `build/hudfurniture_fixture.json`, new asset `build/letters.json`.
  Mutation battery 946/946 killed, ZERO survivors (+41 for H9, 4 withdrawn).
  bb.test 604 -> 623.
- [x] **M7.7-H10 DONE -- THE `$D380` ELEMENT SPRITE BANK (`$BF39` -> `$BF5B`).**
  BLOCKING for anything that draws an element or EXTEND bubble, and it KILLS the
  idea of shipping `$D380` as an asset: the bank's content is a function of
  `($7E0E)`, which H6 showed is redrawn from the refresh register on fifteen
  rounds, so two builds of the SAME ROUND can differ.  Nothing here is keyed on
  the round.
  **`$BF5B` ZEROES 384 BYTES, NOT 128.**  `$AA49` is `XOR A / LD (HL),A / INC HL /
  DJNZ` and exits with B = 0, so `LD B,$80 / CALL / CALL` clears 128 and then TWO
  HUNDRED AND FIFTY-SIX (TRAPS #45).  All 384 are immediately overwritten by the
  LDIR from `$C780`, so it is DEAD WORK -- a port writing 128 is byte-identical
  afterwards and wrong in the trace, which is why the gate counts.
  **THE SHIFT RULE IS TWO 24-BIT SHIFTS PER SIX-BYTE GROUP**, bytes 0,1,2 as one
  MSB-first value and then bytes **5,4,3** as a second WITH BYTE 5 AS THE MSB --
  the triple is stored REVERSED.  A Python model of that reproduces all 384 bytes
  for all THIRTEEN classes; the obvious implementation, one 48-bit shift of each
  six-byte row, gets **92 to 98 of them wrong**.
  **AND THE PORT CANNOT BUILD NINE OF THE THIRTEEN BANKS FAITHFULLY.**  The patch
  fetches eight bytes through `$C068`.  Classes 2/3/4 take RAM icons at
  `$B614`/`$B61C`/`$B624` and are exact.  Classes 5..12 take SPECTRUM ROM CHARSET
  cells -- the six H6 and H9 already declared.  **And class 0 is not a glyph at
  all**: `SUB 2 / ADD A,A` gives `$FC`, so the 31 rounds in no list read 252 bytes
  PAST the twelve-entry table, at `$C164`, which holds `$05E0` -- **EIGHT BYTES OF
  ROM *CODE*** (its eight bytes -- not quoted: no ROM byte is written in this repository).  Measured, that overlay changes **99
  of the bank's 384 bytes**, so it is not invisible and cannot be waved away.
  The resolution keeps the faithful part exact: the pointer ARITHMETIC is
  reproduced overrun and all, and only the eight glyph bytes are substituted
  (the drawn letters for 5..12, nothing for class 0).  To give the engine an
  exact target for everything else, **the oracle makes the MACHINE build each
  bank from the port's own substitute**, by repointing the table entry at a RAM
  scratch block -- the harness drops writes below `$4000`, so the substitute
  cannot simply be poked over the ROM.  The gate then compares all 384 bytes per
  class with the departure confined to eight.
  **AND H6's EIGHT-INTO-SIX FOLD HAS A THIRD INDEPENDENT WITNESS.**  After
  `$B80E`'s bit masks and `$C068`'s pointers, the SPRITE DATA agrees: classes 5,
  8 and 11 build an IDENTICAL bank, and so do 10 and 12.
  **CLASS 1 IS UNREACHABLE** -- `$7DD6` leaves C at 0, 1, 2, 3 or `$FE`, so the
  class is 2, 3, 4, 5 or 0, never 1 -- so its pointer's eight bytes at `$BE00`
  are deliberately not shipped, and the gate asserts the unreachability rather
  than the data.
  FOUR SURVIVORS.  **One is a COST OF THE DEPARTURE, not a gate gap**: class 0's
  eight-bit index reaches `$C164`/`$05E0` and a sixteen-bit one reaches
  `$C264`/`$02F0` -- genuinely different pointers, but BOTH are non-letter ROM
  addresses and the port overlays nothing for either, so **they are
  indistinguishable through the finished bank**.  Not shipping the ROM costs the
  ability to gate that overrun by its effect, so `bankSlot()` was exposed and the
  arithmetic gated directly -- and the old check was recomputing the slot in the
  test, i.e. testing the test.  Two more were the familiar shape: the pool clear
  was gated by COUNT (48 writes) and not by address or value, so a stride of nine
  and a `+3` of zero both survived.  The fourth was a badly-constructed mutation
  of mine that left half the original code running.
  New tool `tools/elembank.py`, new fixture `build/elembank_fixture.json`.
  Mutation battery 983/983 killed, ZERO survivors (+37 for H10).
  bb.test 623 -> 638.
- [x] **M7.7-H11 DONE -- THE SCROLL-IN, GATED AS AN ANIMATION.  This is where
  M7.1 binds.**
  H2 proved the END STATE TESTS NOTHING -- `$7F4E CALL $8216` repaints from the
  shadow three instructions after the loop exits -- so not one assertion here
  looks at the finished screen.
  **THE COPIER IS SELF-WRITTEN CODE, AND IT LIVES IN I1's ITEM BLOCK.**  `$7F1B`
  lays THIRTY-TWO unrolled LDIs (`ED A0`) and a `RET` at `$9603` immediately
  before the scroll.  Those 64 bytes, `$9603..$9642`, are EXACTLY the item block
  I1 measured -- the same memory is executable code during the round build and
  live item data during play, and the chain's `RET` at `$9643` is the byte one
  past the block's end.  Neither image shows it: the tape has cold-start code
  there and the round-80 dump has item data, so only breaking at `$8421`
  mid-transition sees it.  It IGNORES BC because nothing tests BC -- driven at
  `$0000`, `$001F`, `$0020` and `$1234`, it copies 32 every time and leaves
  BC - 32 wrapping.
  **`$8404`/`$8407`/`$840A` IS A CASCADE THAT USES RETURN ADDRESSES AS A LOOP.**
  `$8404` CALLs `$8407`, whose return address is `$840A`; `$8407` CALLs `$840A`,
  whose return address is ALSO `$840A`.  Entering at `$8404` runs `$840A` FOUR
  TIMES -- four pre-roll steps, then 22 content steps, 26 over a 176-pixel
  playfield.
  Other structure: **`$8447`'s ATTRIBUTE SOURCE IS THE COLOUR SHADOW**
  (`$8476 ADD A,$F8`, not `OR $58`) -- a port taking the new row's colour from
  the attribute plane is reading what it just scrolled; **`$81EF` calls `$AA4A`,
  NOT `$AA49`**, one byte past the `XOR A`, so the separator row's 32 attributes
  take `($5AC0)`, the OLD round's colour, instead of black; and **`$8584` is
  DERIVED STATE WITH A ONE-ROUND LAG** -- `$8207` LDIs `$856C`'s eight EVEN bytes
  into it and runs BEFORE `$830B` refills `$856C`, so every round's band is drawn
  in the PREVIOUS round's tile.  I had shipped `$8584` as a table lifted from the
  tape (all zeros, the cold-start value) and it is now derived.  The lag is
  invisible when consecutive rounds share a tile set -- one pair in five, because
  `$83EC` cycles mod 5 -- so it must be driven across a build boundary.
  **AND THE DRIVER WRITES 163,872 SCREEN BYTES**, which is EXACTLY the figure H1
  and H2 measured being discarded on rounds 2, 5, 56, 72, 80 and 81.  The
  scroll's entire output is what `$8216` throws away, now measured from the
  inside and the outside and agreeing to the byte.
  **TWO REAL TRANSLITERATION ERRORS, BOTH CAUGHT BY GATES.**  (i) `$843D INC IX /
  INC IX` advances TWO BYTES -- ONE table entry -- so the pairs OVERLAP: it is a
  SLIDING WINDOW over `$FD04`, not disjoint pairs.  My `+4` walked off the
  display table into the shadow table (2,816 bitmap writes instead of 5,376 plus
  1,280 spurious shadow writes).  The synthetic world made it legible in one
  probe because every row names itself.  (ii) **`$81E6` HAS AN OUTER COLUMN
  LOOP** -- `$8203 DEC C / JR nz,$81F5` runs the eight-row pattern walk THIRTY-
  TWO TIMES, once per column, so the row walk is the INNER one.  My version wrote
  a single column, and that was invisible to every check until the pre-roll
  bracket existed.
  **H2's LESSON HAS AN INNER ANALOGUE, and it cost two survivors.**  The
  separator band is SCROLLED OFF THE TOP before the animation ends, so removing
  the filler entirely and making the pre-roll push rows BOTH leave the final
  screen untouched.  The bracket had to move inward again, to `$7F3C` -- after
  the filler and the cascade, before the counter is set.  A thing that is later
  overwritten can only be seen before it is overwritten, and "before" has to be
  chosen per claim, not once per increment.
  EIGHT SURVIVORS, all gate gaps.  Four because **the separator row had no oracle
  at all**; three because **the driver was gated only by its return value** and a
  step COUNT cannot see an ordering (a pre-roll that pushes, a counter
  decremented early and a push before the step all give 26); and one because **my
  pre-roll gate called `scrollFiller()` and `scrollStep()` DIRECTLY, so a
  mutation to the driver's pre-roll LOOP was never on the gate's call path at
  all** -- a failure mode distinct from every other in this chain, fixed by
  extracting `scrollPreRoll()`.
  Two oracle faults of my own: the driver run inherited `$8584` from whichever
  measurement ran before it (`$7F30` does not lay the pattern -- `$8207` runs at
  `$7F2A`), making the fixture order-dependent; and the first write census lumped
  the routine's own stack PUSHes in with the shadow writes the plan says must be
  zero.
  New tool `tools/scroll.py`, new fixture `build/scroll_fixture.json`.
  Mutation battery 1016/1016 killed, ZERO survivors (+33 for H11, 1 obsolete
  mutation retired when `$8584` became derived).
  bb.test 638 -> 656.
- [x] **M7.7-H12 DONE -- THE ENEMY DROP-IN: a GATING increment, and a
  RETRACTION.**
  **THE ENGINE FOR THIS WAS ALREADY WRITTEN.**  `$7336`'s arming, `$B520`'s
  settler and `$A430`/`$A42B`'s band all went in with M7.6 and M7.7-a and had
  never had an oracle of their own.  H12 builds one, and settles the three
  numbers the reading pass moved OUT of its settled model into LOW CONFIDENCE
  with an explicit instruction not to quote them until this increment took them.
  **TWO CONFIRMED, ONE RETRACTED.**
  - "2 px per tick on the ODD ISR = 1 px/frame" -- **CONFIRMED.**  The ramp runs
    `0,0,2,2,4,4`: the counter ticks every OTHER frame.
  - "targets 0..168, window 88 x 2 = 176 px" -- **CONFIRMED.**  Measured targets
    span 8..168 over rounds 1/2/10/14/17, and the freeze holds for exactly 176
    frames, which is 88 ticks on the odd ISR.
  - "the top-of-playfield CLIP -- invisible until Y ~ 4, slides out from under
    the HUD at pixel row 16" -- **RETRACTED.  THERE IS NO SUCH CLIP.**  `$A42B`
    is `CP C / RET nc / CP B / CCF / RET`: an EXCLUSION, skipping the entity when
    its Y lies INSIDE a 30-pixel band, so at LOW Y it is DRAWN.  And `$A430
    ADD A,$2A / LD ($A431),A` stores its own result back as its addend, so the
    band walks ONE PIXEL PER ENTITY and persists across frames [CORRECTED M7.49:
    it walks down through a PASS, and $A3D2 re-seeds it $B9 before every pass --
    it does not persist].  It is BEAM
    AVOIDANCE, not a clip -- which sits beside H11's finding that there is no
    `HALT` anywhere in the scroll loop.  FOUR coordinates are tested in order --
    `(IY+6)`, `(IY+6)+$10`, `(IY+2)`, `(IY+2)+$10` -- and any ONE inside the band
    skips the entity ENTIRELY, both erase and draw, so a port testing only the
    current Y leaves a half-erased sprite whenever the CACHED Y is in the band.
  **THE CONTROL IS WHAT MAKES THE RAMP MEAN ANYTHING.**  An enemy's ordinary FALL
  is also `(Y+2)` on the odd ISR, so with `$B54B` = 0 the same enemies drift to
  `[58,58,68,66]` -- NOT the targets and not equal to each other.  Armed, round
  14's SEVEN DIFFERENT targets `[56,104,32,40,48,56,72]` are each hit exactly.
  Without the control, "the settler ran" and "gravity ran" are one observation --
  `settle.py` had written that down and I had to be reminded of it.
  **THE FREEZE, WITH ITS OWN CONTROL:** 176 frames with P1's X CONSTANT at 24
  while a movement key is held, against 100 distinct X values when the counter is
  zero and the same key is held.  The assertion is "constant WHILE the counter is
  non-zero", not "never moves": a 200-frame window runs 24 frames past the thaw,
  in which P1 legitimately walks 12 steps, and reporting the whole-window spread
  made the armed case look unfrozen.
  **AND THE OVERSHOOT NEGATIVE IS CHARACTERISED, NOT ASSUMED:** poked ABOVE its
  target the ramp CLIMBS AWAY to 100 and never returns, so `Y <= target` is a
  property of THE ARMING (`$7336` zeroes every Y) and not of the settler, which
  has no clamp and two eight-bit INCs.
  **TWO RIG FAULTS, BOTH MINE, BOTH ALREADY DOCUMENTED IN THE TOOL I WAS TOLD TO
  EXTEND.**  The plan said "extending `tools/settle.py`" and I wrote a fresh
  driver instead.  It cost: (i) a direct call leaves PC parked on a SENTINEL,
  which is game DATA, so free-running frames executes bytes that are not code --
  every enemy Y came back as 2, the freeze never armed and P1 drifted; and (ii)
  no paired CONTROL, which `settle.py` insists on because a player never asked to
  move is frozen either way.  Both are in `settle.py`'s docstring.  **When a plan
  names a tool to extend, that tool's docstring is a list of traps already paid
  for.**  A third fault was an SP imbalance from one phase inheriting another's
  machine; every phase now gets a fresh harness.
  ONE SURVIVOR, and it is the good kind: the four tests done SIXTEEN-BIT rather
  than eight.  That differs only for a coordinate >= `$F0`, and 600 frames of
  real play across all twelve slots keep `(IY+6)` and `(IY+2)` within **0..168**.
  But a sample is not a proof and `$A42B` is a Z80 `CP`, so rather than withdraw
  it the WRAP IS GATED AT THE METHOD -- `$F8` has its `+$10` wrap to `$08` and be
  caught by a band down there.
  Two structural fixes from H11's lesson: the arming check now drives
  `spawnRound()` instead of reimplementing its loop, and the clip decision is
  extracted as `entityHidden()` so the gate drives it rather than reassembling
  it.  And one comparison had to be corrected -- the machine's `$A42B` table is a
  SINGLE-coordinate test while `entityHidden()` is the FOUR-coordinate decision,
  so comparing them directly asserts that one function equals a different one.
  New tool `tools/dropin.py` (extending `tools/settle.py`), new fixture
  `build/dropin_fixture.json`.
  Mutation battery 1038/1038 killed, ZERO survivors (+22 for H12).
  bb.test 656 -> 674.
- [x] **M7.7-R4 DONE -- THE TWO CALLS NO INCREMENT OWNED: $99A8 and $A36C.**
  ***$99A8 IS THE ROUND'S PLAYER INIT AND A TWO-ENTRY SHARED BODY***: $99A8
  CALLs $99C3, which does P2 and FALLS THROUGH into the tail; the call returns,
  $99A8 does P1 and JRs into the SAME tail.  C is BOTH the player index AND the
  source of the (IY+7) mask -- one register, two jobs -- so a transliteration
  passing "which player" as a boolean loses the mask.
  THE MASK: `C := (((IY+$5B) & 1) << 2) | $C0 | (index ^ 1)` then
  `(IY+7) := ((IY+7) & C) | $40`.  Bits 6/7 always survive, bit 2 only if
  (IY+$5B) bit 0 is set, and **BIT 0 -- THE FACING -- SURVIVES FOR P1 AND IS
  CLEARED FOR P2**, because the mask's bit 0 is the OTHER player's index.
  Byte-exact against the machine on both players.
  ***AND $A36C WAS ALREADY IN THE PORT, INLINED INSIDE I6's ITEM HANDLER 12***
  (the level skip at $8915), so the round start could not reach it.  One
  routine, two call sites, transliterated at one -- TRAPS #58's shape.  It is
  one method now and both sites call it.
  **AND THE $5A POISON HID TWO OPERATIONS IT WAS SUPPOSED TO EXPOSE**: $5A is
  0101 1010, so bit 6 is ALREADY SET (the `OR $40` writes nothing new) and bit
  7 is CLEAR (the `AND $80` cannot be told from an assignment).  Two mutations
  survived on exactly that.  A poison must be chosen AGAINST THE OPERATION, not
  merely be a value the routine never writes -- TRAPS #44 gains rule (d).
  New phase `tools/roundstart.py:phase_unowned`.
  Mutation battery LISTED 1398 / LIVE 1398 / DEAD ANCHORS 0 / SURVIVORS 0
  (+16 for R4).
  bb.test 950 -> 955.
- [x] **M7.7-R3 DONE -- THE DRAINED PASSDIFF HARNESS.  It walked the
  differential forward through TWO OF MY OWN DEFECTS to a real boundary.**
  The harness walked BB_CHAIN by hand and never called step(), so a routine
  that SPENT frames was never charged: B2's 345-frame freeze and $9887's HALT
  both passed without one ISR running.  Draining tframe into isr() AT THE POINT
  OF EACH SPEND takes bosshit and r50_48 GREEN over all 60 rows with the drain
  active.
  **THE DRAIN MUST HAPPEN WHERE THE SPEND HAPPENS** -- draining at the end of
  the pass applies frames spent BEFORE a write AFTER it, and the freeze's 342
  interrupts ticked a settler byte the machine had not written yet (0 vs 87).
  **$9887's HALT SPENDS ONE FRAME** and that closes ($B54B): 88 vs 87
  un-charged.  Gated on the routine too, because a two-frame charge is
  invisible in ($B54B) alone (parity).
  ***THE DIFFERENTIAL WAS ASSERTING A FIELD THE PORT CANNOT REPRODUCE***:
  ($FEC7)'s reseed is $9811 `LD A,R`, which E1 replaced with a DECLARED
  SUBSTITUTE.  It matched by luck; one extra ISR consumes a draw and it moves
  40 -> 35.  EXCLUDED by name.
  ***AND WHAT STOPS IT NOW IS A NAMED, UNBUILT INCREMENT***: ($830A) 94 vs 102,
  because $82D6 has EXACTLY ONE CALLER IN 64K -- $7F65, inside the round
  builder $7F62 -- which the port does not run.  **paletteStep() is wired
  nowhere, so a round advance never changes the palette.**  M7.3c's sibling.
  A CORRECTED PREDICTION, recorded where it was made: R2 said the arm/halt
  order would become observable "the moment the halt spends its frame".  It
  spends now and is STILL equivalent, because spend() DEFERS -- the condition
  is "the port models time INLINE", which it does not.  Withdrawn again, with
  the better reason.
  Mutation battery LISTED 1382 / LIVE 1382 / DEAD ANCHORS 0 / SURVIVORS 0
  (+3 for R3, -1 withdrawn).
  bb.test 945 -> 950.
- [x] **M7.7-R2 DONE -- THE ROUND BANNER $98B5..$98EF: a ~1-second animation
  that erases itself.**
  ***B IS ZERO AT $98B5 ON EVERY STATE, SO $98E2'S DJNZ RUNS 256 TIMES*** --
  TRAPS #45 for the THIRD time in this project.  Each iteration draws two text
  rows and twenty attribute cells: 5,140 writes over only 20 cells, $594C and
  $598C.  Round 81 runs ZERO iterations ($98B8 `CP $51 / JR z,$98E4`).
  ***AND THE END STATE IS BYTE-IDENTICAL TO THE START.***  $98E4 calls $9904
  twice and the cells go back to exactly what they held, on all five worlds, so
  the ONLY observable is the TIME.  H2's lesson again -- AND IT CAUGHT THIS
  INCREMENT'S OWN GATE: three mutations (one row instead of two, the second row
  at the first row's address, eleven cells instead of ten) all survived an
  end-state check.  The gate SUPPRESSES THE ERASE and reads mid-animation.
  **THE COST IS A FUNCTION OF THE ROUND'S DIGIT COUNT**: one digit 3,524,147
  and 3,525,899 T (0.05% apart), two digits 4,074,024 and 4,122,335 (1.2%),
  the classes 15% apart, round 81 just 8,134.  A single constant would be 15%
  wrong on half the rounds -- about four settler ticks.  *(SUPERSEDED M7.43:
  those were wall-clock figures; main-line the banner is flat, and the 15% was
  ISR load that step() then charged a second time -- RA1.)*
  AND THE MECHANISM ALREADY EXISTED: spend() is the port's only time API, and a
  cost bigger than a frame drains through step()'s carry as zero-pass frames
  with one ISR each, which is exactly what the machine does.  No new machinery
  was needed -- the $9573 busy wait had already solved this.
  SIX OF FOURTEEN MUTATIONS SURVIVED THE FIRST RUN, every one a gate hole:
  three to the self-erasing end state, one to an eight-bit walk that cannot
  wrap at the shipped addresses (now driven from $59FA, where it does), one to
  a digit-count threshold tested only on one side (TRAPS #60), and one because
  nothing asserted roundStart() REACHED the banner.
  New phase `tools/roundstart.py:phase_banner`.
  Mutation battery LISTED 1380 / LIVE 1380 / DEAD ANCHORS 0 / SURVIVORS 0
  (+14 for R2).
  bb.test 936 -> 945.
- [x] **M7.7-R1 DONE -- THE ROUND-START SEQUENCE $9858..$98B4, the gap B11
  stopped at.**
  The port had roundAdvance() -> roundReset() (the 19-pointer clear walk) and a
  transitionTail() covering $9891..$98A4 **THAT NOTHING CALLED**.  Between them
  lay $9858..$988E and $98A7..$98B4, unread.
  ***$984B HAS NO RET***: $9856's DJNZ falls STRAIGHT THROUGH into $9858, and
  the sequence runs on past $98B5 into the round banner before returning, so
  $8D09 `CALL $97F8` runs all of it.  The port keeps two methods and makes the
  call the machine gets for free -- and roundAdvanceCore() exists because
  tools/roundadv.py BRACKETS the advance at $9858, so the advance gate must
  compare that span and not a longer one (it failed on ($FEC4) first, which is
  TRAPS #66 exactly).
  ***THE SETTLE WINDOW IS 88 FRAMES ON EVERY ROUND AND 20 ON ROUND ONE***, from
  ONE load feeding BOTH $B54B and $FEC4.  $B54B is what $AA72 uses to abandon
  the entire entity pass, so round 1 freezes the entities for 20 frames and
  every other round for 88.  **AND ($FEC4) IS THE UNDECAYED COPY** -- $B54B
  counts down, $FEC4 keeps the round's original -- so four live captures
  confirm it with NO POKE AT ALL: play1p48 14/20, round1_48 0/20, r20_48 10/88,
  bosshit 0/88.  B11 recorded play1p48 inside a settle window as evidence that
  captures are suspect; it is a ROUND-1 SPECIAL CASE and $FEC4 says so
  afterwards.
  ALSO: the sequence CONTAINS A HALT ($9887, between arming the settler and
  zeroing the frame counter, so the halves sit on opposite sides of a frame);
  $988B and $988E are SIXTEEN-BIT STORES (four bytes, all poisoned); $9858
  clears 6144 bytes $E000..$F7FF and NOT ONE byte of the colour shadow; and
  $98AD's `LD A,$2A` feeds BOTH the ISR gate and the boss HP, superseding
  $79A2's seeder two frames later.
  EVERY CALL BRACKETED SEPARATELY -- and the first attempt measured TWO OF NINE,
  because seven return addresses ARE the next call site and the bracket closed
  on an arm.  $7F1B 211,251 writes, $79AC 2,028, $BF39 1,696, $727B 117, $957E
  123, $8C5E 73, $A36C 44 (UNOWNED), $99A8 23 (UNOWNED), $AA49 26.
  ***AND B11'S TWENTY FIELDS PARTITION***: thirteen written here, seven
  ($8609, $A839, $AA00, $AA06, $FEC7, $FEC8, $A09E) never touched.
  TWO OF MY OWN MUTATIONS SURVIVED the first run, both real holes: nothing
  asserted transitionTail() was REACHED (which is what makes I6's diamond pin
  last exactly one round), and nothing BOUNDED the shadow clear -- so the clear
  is its own method now and both are gated.
  ***AND THE FOLLOW-UP MEASUREMENT FOUND THE NEXT INCREMENT.***  Re-running
  B11's differential with the sequence wired takes bosshit and r50_48 GREEN
  over all 60 rows and reaches bosskilled's row 20, differing on ONE field by
  ONE: ($B54B) 87 against 88.  The obvious model -- "the halt costs one settler
  tick" -- IS WRONG: across five worlds the count between arming and the first
  loop top is 1, 28 or 31.  Split at $98B5 it resolves: the transliterated part
  costs 2..4 interrupts, and THE ROUND BANNER AFTER IT COSTS 51..58 INTERRUPTS
  ON AN ORDINARY ROUND AND ONE ON ROUND 81, because $98B8 `CP $51 / JR z,$98E4`
  skips it.  A ~1-second animation nobody had costed, and it is why bosskilled
  was off by exactly one.  B11's row-20 owner annotation ($8C5E, the round
  build) is SUPERSEDED and now names the banner.
  ONE MORE MUTATION WITHDRAWN: swapping the settler arm and the HALT survives
  because roundHalt() counts a frame the port does not spend, so both orders
  give identical state -- a provable equivalent that becomes a real distinction
  the moment the banner increment makes the halt real.
  New tool `tools/roundstart.py`, new fixture `build/roundstart_fixture.json`.
  Mutation battery LISTED 1366 / LIVE 1366 / DEAD ANCHORS 0 / SURVIVORS 0
  (+15 for R1, -1 withdrawn).
  bb.test 922 -> 936.
- [x] **M7.3c DONE -- THE PLAYFIELD ATTRIBUTE PAINT.  *** 915 CHECKS PASSED
  OVER A BLACK SCREEN. ***  CLOSES the "enemies are drawn but invisible" item,
  whose framing was wrong.**
  **NOTHING PAINTS ENTITY COLOUR.**  60 frames of round1_48 with the attribute
  file watched: 122 writes, EVERY ONE from $8017, the HUD score, rows 0-1 only.
  The playfield is never touched in play.  The enemies are visible because the
  WHOLE PLAYFIELD carries the round palette and the sprites inherit it.
  ***THE ROUND ASSET'S ATTRIBUTE THIRD WAS THE COLOUR SHADOW, BYTE FOR BYTE.***
  build/render_round1.json's `display` is a full 6912-byte display file whose
  attribute third for rows 2-23 equalled its own `colour` block -- $00, $20,
  $40, $A0, $C0, $E0, which are H3's solidity, H4's drift and H5's occupancy
  BIT FIELDS, not attributes.  433 of the 704 playfield cells had INK EQUAL TO
  PAPER.  The asset had NO PRODUCING TOOL, which is how it stayed wrong for
  nineteen increments; it has one now.
  AND renderFrame() copied the shadow over the attribute file at every reset,
  so even a corrected asset would have been destroyed on load.  $823C really is
  a plain LDIR $F840 -> $5840 -- correct AT BUILD TIME, when $82FC has just
  filled the shadow with the OPEN palette byte, and wrong over the mid-play
  capture reset() loads.  $8C28 is the one that works on a live shadow
  ($8C34 `BIT 5,(HL)` picks $830A or $8309), it changes ONE CELL OF 704 when
  run over round1_48's live world, and B10 had left it a named stub.
  **THE PALETTE CANNOT BE DERIVED FROM THE ROUND.**  $82D6 picks
  BB_PALETTE[($82D7 - 1) mod 15]; predicted exactly on six states -- and $82D7
  is a BUILD COUNTER, so r10_48, r20_48, r30_48 and r50_48 all read 2.  It is
  carried, and the ROUND ASSET OVERRIDES build/image.bin's $82D7 = 5, which is
  ROUND 80's (TRAPS #43).  Getting that precedence wrong is what the palette
  gate caught first: the pair was right and the counter read 5.
  ***AND THE STRUCTURAL POINT IS NOW A TEST.***  The fix turned the screen from
  black-on-black to the round's colours and NOT ONE of the 915 existing checks
  moved.  Every gate in this repository drives the engine from a captured world
  and compares RAM; not one ever asked whether anything could be SEEN.  The
  suite now has a VISIBILITY gate: after reset() every one of the 704 playfield
  cells must have ink different from paper, and the cells the enemies stand on
  are checked by name.  NEW TRAPS #92.
  New tool `tools/render_asset.py`, new fixture `build/attrpaint_fixture.json`,
  and `build/render_round1.json`'s attribute third CORRECTED.
  ONE OLDER MUTATION WITHDRAWN WITH ITS ENUMERATION: "H0: the build counters
  are not carried as state" removed `$82D7 := 5; $83EC := 0`, and the round
  asset now supplies $82D7 regardless -- while $83EC reads 0 in BOTH images and
  reset() zero-fills, so that half was a no-op all along and the $82D7 half was
  masking it.  Replaced by one that still bites: the round-80 image default
  winning over the asset, which is EXACTLY the defect I wrote first and the
  palette gate caught.
  Mutation battery LISTED 1351 / LIVE 1351 / DEAD ANCHORS 0 / SURVIVORS 0
  (+9 for M7.3c, -1 withdrawn).
  bb.test 915 -> 922.
- [x] **M7.7-H13-B11 DONE -- THE BOSS ROUND END TO END.  The differential
  runs, and the state-selection correction it exists to carry is measured.**
  ***TWO OF THE FOUR BOSS CAPTURES ARE INSIDE A WINDOW THAT SWITCHES THE WHOLE
  ENTITY PASS OFF.***  An INSTRUCTION census over $AB00..$AC40 per 400k gives
  ZERO on boss.pkl and bossspawn.pkl against 5928 on bosshit and 3519 on
  r50_48 -- no player tick runs there at all.  And it is not a boss-state
  quirk: play1p48 is inside one too ($B54B = 14, zero at frame 28), which is
  exactly the 28 frames that reconcile B8's decay (28 + 201/0.5 = 430 vs 429).
  NEW TRAPS #89.  bosskilled is unusable for a DIFFERENT reason no entry
  named: its settler is zero, so a $B54B check passes it, but it runs the
  entity pass ONCE in 120 frames because the WELL DONE freeze owns the rest.
  **THE DIFFERENTIAL IS OVER A SAMPLED STATE VECTOR AND THE FIXTURE SAYS SO** --
  a byte-for-byte world diff would need the engine seeded from a capture, i.e.
  shipping the 48K image, which house rule 7 forbids.  36 fields per MAIN-LOOP
  PASS, each tagged with its owning increment, 5 tagged UNIMPLEMENTED -- and
  all five are STATIC across all 1,600 sampled passes, so the sampled
  differential is COMPLETE over everything that moves.
  ***AND THE ENGINE REPRODUCES THE MACHINE ROW FOR ROW***: seeded from row 0
  and fed nothing but the machine's own frame timeline, mainLoop's chain walk
  produces every owned field of every later row for 59 passes on bosshit and
  59 on r50_48, ZERO divergence.  On bosskilled it matches to row 19 and STOPS
  BY NAME at row 20 -- that row IS the 80 -> 81 advance, and the 20 fields that
  move across it are the work $8C5E, the round build, inherits.
  **GETTING THERE COST TWO TRAPS.**  $AA00 diverged at row 9 against a
  perfectly self-consistent engine, because A LOOP-TOP ROW IS THE RESULT OF THE
  PREVIOUS PASS; and then $A09E diverged because A MAIN-LOOP PASS IS NOT ATOMIC
  WITH RESPECT TO THE FRAME COUNTER -- the loop runs 8.571 times a frame, 16 of
  600 passes STRADDLE an ISR, and the boss tick at $8D2E and $A09A at $8D43 see
  DIFFERENT values of ($8DBD).  NEW TRAPS #90.  And $A98F/$A990 were missing
  from the vector, so the engine ran on reset()'s tape value `37 C9` -- every
  position an overlap -- killed P1 on pass 10 and the differential called it a
  boss bug.  NEW TRAPS #91: THE SEED LIST IS THE TEST'S WORLD.
  **THE TWO ADDRESSES THE WHOLE PLAN LEFT UNOWNED ARE TAKEN.**  $8E58 is the
  +100000 boss-kill bonus (`DI / LD A,$10 / LD ($FFEF),A`, the THIRD byte of
  the pending field) paid in the SAME FRAME as B6's +100 -- a port that owns
  one is wrong by a factor of a thousand.  And $927D has TWO callers: a 48K
  census gives call site $9269 and jump site $AA35, so "a CALL scan misses it"
  is true of $AA35 and FALSE of $9269, and "entered only via $AA35" is a
  round-80-only statement.  $9269 runs once a chain pass on EVERY round; park
  an active enemy on P1 and it fires with $AA35 at zero.
  **AND $A824'S NEGATIVE WAS WRONG**: "the body never entered" conflates two
  gates.  $A824 RETs at $A828 for want of a giant, is then a SECOND CP-FORM
  EDGE DETECTOR ($A82C `CP $2A` against $A82D, its own operand -- $A09A's idiom
  again), and only then does $A835 send the boss round home.  Three exits,
  three states: r50_48 at $A828, bosshit at $A837, peachfall PAST both.
  EVERY ZERO-NEGATIVE IS NOW PAIRED WITH A POSITIVE -- force a round clear on
  r50_48 and $8E3B and $FECA fire -- and ($FED4)'s is STRUCTURAL: no direct
  store anywhere in 48K and ONE pointer load, at $8E0A, which is the music call
  $9690 patches to $C9 on this branch.
  RETRACTED: the entry's own proposed trap, "a decay's invariant is its COUNT,
  not its frame", is backwards -- B8 and B10 have it the other way round.
  New tool `tools/bossround.py`, new fixture `build/bossround_fixture.json`.
  Mutation battery LISTED 1343 / LIVE 1343 / DEAD ANCHORS 0 / SURVIVORS 0
  (+7 for B11).
  bb.test 898 -> 915.
  ***M7.7-H13 IS COMPLETE: B0 THROUGH B11.***
- [x] **M7.7-H13-B10 DONE -- THE ENDGAME AND $A09A: the last dark range in
  the main-loop chain, and it was never "lightning".**
  The port carried $A09A as a chain stub with that label from B0.  It is a
  two-armed FULL-SCREEN EFFECT MANAGER -- the blue-cross FLOOD ($FECE) and the
  THUNDER ($FECF), both armed by I6 item types -- behind a CP-form edge
  detector whose compare operand $A09E IS ITS OWN BYTE.  It is the EIGHTH
  wired chain entry now.
  ***$A0E0 MASKS 704 ATTRIBUTE BYTES, NOT THE 384 THE PLAN SAID.***  $A0E7
  CALLs $A0ED and $A0EA CALLs it again -- and $A0ED IS THE NEXT INSTRUCTION,
  so the second CALL returns INTO the loop and the routine falls through for a
  THIRD pass: $C0, then 0, then 0, and DJNZ with B = 0 is 256 (TRAPS #45).
  192 + 256 + 256 = 704, and $5840 + 704 = $5B00 EXACTLY.  $8C28 copies 704
  the other way; the number closes from both ends.
  ***AND THE PLAN'S REASON FOR SAFETY WAS BACKWARDS***: `AND $F8 / OR E` CLEARS
  AND REWRITES bits 0-2, it does not leave them alone.  What makes it safe is
  that it writes the DISPLAY attribute file and NEVER the colour shadow (zero
  writes into $F800..$FAFF with the shadow seeded differently), and that $8C28
  RE-DERIVES all 704 from the shadow through H3's open/solid palette pair --
  not a copy: $8C34 `BIT 5,(HL)` picks ($8309) or ($830A).
  **A ROUND-1 WORLD CANNOT TEST $A09E.**  The tape holds $2A and so does
  play1p48; seven of eight censused states differ (boss $43, bosskilled $DD,
  ...).  And "54 edges, once per video frame, which is the CP-form's whole
  purpose" is FALSE ON SIX OF EIGHT: measured 1.000, 1.000, 0.983, 0.983,
  0.967, 0.367, 0.350 and 0.050.  The detector fires when ($8DBD) changes and
  ($8DBD) is not the frame clock.
  **$A110 IS NOT PART OF $A09A** -- its only reference is $88C1, item effect
  type 6, already in build/puhandlers_fixture.json.  $A127 has ZERO 16-bit
  references and is reached only by a relative JR.
  ***"AT THE FAR END $745C = $03E8" IS SATISFIED BY A PORT THAT NEVER TOUCHES
  IT*** -- bosskilled already reads $03E8 at frame 0.  Seeded to the poison
  $BBAA and driven 460 frames to round 81, it is NEVER WRITTEN.
  ***AND THE UNACCOUNTED +300 IS ACCOUNTED FOR: IT IS AN ITEM.***  At f417
  $8809 posts $0300 from HL loaded through $8801 `LD DE,$8649` -- I6's item
  point-value table.  The same trail also shows the boss HP re-armed at
  f414/f416 by $79A8 (B2's self-doubling seeder) and by $98B2, where ONE
  `LD A,$2A` feeds BOTH ($FEC5) and the boss HP.
  **SEVEN OF MY OWN MUTATIONS SURVIVED THE FIRST RUN, AND EVERY ONE WAS A GATE
  HOLE OF THE SAME TWO SHAPES.**  Four were thresholds probed at a value both
  models agree on ($10 under `AND $1F` and `AND $0F` alike; $F0 for the
  payload-versus-flat split) -- TRAPS #60 re-paid, a threshold is invisible
  from inside its range.  Three were a COVERAGE count: "were these 22 rows
  painted?" is satisfied by a routine that paints all 704 cells, by a
  misaligned base and by a walk in the wrong direction.  NEW TRAPS #88.  The
  rows now gate the changed-cell COUNT, the base ADDRESS against the formula,
  and the DIRECTION of the walk.
  ALSO: the flood wins when both arms are armed ($A0A7 leaves before $A0A9
  reads ($FECF)); the flood crawls by a NET ONE past $AF (`ADD 3 / SUB 2`) and
  disarms on the ADD's CARRY at step 138; and the clear walk's NEGATIVE half --
  16 poisoned survivors, all surviving, with $FECE and $FECF among the 19 it
  DOES clear.
  New tool `tools/endgame.py`, new fixture `build/endgame_fixture.json`.
  Mutation battery LISTED 1336 / LIVE 1336 / DEAD ANCHORS 0 / SURVIVORS 0
  (+28 for B10).
  bb.test 878 -> 898.
- [x] **M7.7-H13-B9 DONE -- THE DEATH SEQUENCE, AND THE ARROW INTO THE EXIT.
  It found an omission the port never knew it had.**
  ***$AB68 CALL $BF0A WAS UNNAMED: THE PORT'S FINAL DEATH LEFT THE PLAYER'S
  LAST FRAME ON SCREEN.***  On the out-of-lives branch only, $BF0A sets the
  erase cache from the live position and, having no RET, falls through into
  $BF16 and rubs the sprite out.  A grep of game.js and every docs/*.md for
  AB68 returned nothing.
  **AND THE PLAN'S OWN DRAFTED ORACLE FOR IT COULD NOT FAIL** -- the critic
  section said so and the fixture now proves it as a ROW: $FD82/$FD83 have TWO
  ORDINARY PER-FRAME WRITERS ($A603, $A623) that wipe the $5A poison at FRAME
  1, and $BF0A writes the live position they already put there, so the cache
  ends [168,24] on the last life and the IDENTICAL [168,24] on a respawn.  A
  port that omits $AB68 entirely passes a display diff.  The separator is the
  PC-ATTRIBUTED WRITE LOG: cache writers {A603:2, A623:2, BF0D:1, BF13:1}
  against {A603:11, A623:11}, and bracketed $AB5E -> $AB6B the last life writes
  83 bytes (48 DISPLAY) where a respawn writes ONE.
  **AND THE BRACKET ITSELF PAID FOR A TRAP.**  My first harvest point was
  $ABD4 and it measured ZERO ON BOTH ARMS: $ABD4 is P2's RET -- P1 leaves the
  tick at $ABCB -- so the end of the bracket was never executed.  Two zeros
  read exactly like a correct negative.  NEW TRAPS #87.
  ***$AB64 CLEARS BIT 7 BEFORE $AB68 RUNS***, and $A447 diverts a bit-7-CLEAR
  slot to $A437, which erases nothing -- $BF16 gets the erase anyway by FORCING
  (IY+7) := $C0 and restoring it at $BF35.  So "the player is out of play, skip
  the erase" is exactly the wrong optimisation.  The port now MODELS $A451/
  $A456/$A45E against the forced value instead of transcribing their outcome,
  which is what makes a mutation of the constant able to fail at all.
  ***AND ON THE LAST LIFE THE DYING PLAYER'S OWN LIVES PANEL IS NOT
  REPAINTED*** -- $AB6D CALL $806C runs on both arms, but $8097 is `RET p` and
  refuses a player whose bit 7 is clear.  12 writes and ZERO panel cells
  against 104 writes and 24 cells, with the eight icon bytes copied EITHER WAY
  so that a call count sees nothing.  $806C stays a NAMED COUNTED STUB and the
  HUD increment inherits the measurement.
  **CONFIRMED THE CRITIC'S CORRECTION**: the invariant is 76 FRAMES FROM THE
  ARM, not "frame 79" -- bosshit arms at 4 and wraps at 80, r50_48 arms at 6
  and wraps at 82; 76 = 256 - $B4 by arithmetic, so assert the SEED and the
  RATE.  B11's anchor list still quotes only 79 and needs fixing.
  **A SECOND DOCUMENTATION CORRECTION, FOUND BY DISASSEMBLING $A447**: B7 wrote
  that $A447 "returns early when bit 7 is SET".  It is the other way round --
  $A451 `JP p` DIVERTS TO $A437 WHEN BIT 7 IS CLEAR, and a bit-7-set slot never
  reaches $A437 at all.  The measured table and the shipped code were right;
  only the prose was inverted, which is why nothing caught it for three
  increments.  Corrected in game.js, SPEC and TRAPS #83 (new rule (d)).
  ALSO: $BF16 is bbEraseSprite, not bbEraseEntity ($BF23 writes $C3 over $A480
  so the three-column path always runs) -- byte-identical at an even
  sub-position because $AA4F[0] is $00, differing only in the store count, 48
  against 32.  A behavioural no-op, fixed for faithfulness and recorded as one.
  NEGATIVES on BOTH rounds with their frame count: $8E3B, $8ECF, $FED0, $FED4
  never written, $9573 entered ZERO times by a player death (it is the BOSS
  death's busy wait), and ($FECA) rewritten 35 times on round 50 by $8EC1 and
  NOT ONCE on round 80 -- the row that makes the rest mean something.
  MEASURED AGAINST THE PLAN: round 80 CONSUMES the hurry-timer reset request
  ($9164) while round 50 leaves it PENDING.  The plan expected the opposite.
  THE TWO EQUAL ANSWERS, each driven to its separating input: $927D rewrites
  (IX+4) := $50 over an ALREADY-$84 state, so the guard is $AA30's and a port
  guarding internally gives a rolling death timer; and a respawn PARKED ON THE
  BOSS'S OWN TILE separates "the invulnerability protects" from "the boss
  missed" -- bit 3 set, nothing; bit 3 clear, killed.
  ONE MUTATION WITHDRAWN with its reason: the cached-Y ceiling in the caller
  duplicated the one bbEraseSprite already carries ($A464 lives in the callee),
  so neither copy could fail alone.  The duplicate is REMOVED, not excused.
  New tool `tools/bossdeath2.py`, new fixture `build/bossdeath2_fixture.json`.
  Mutation battery LISTED 1308 / LIVE 1308 / DEAD ANCHORS 0 / SURVIVORS 0
  (+16 for B9).
  bb.test 860 -> 878.
- [x] **M7.7-H13-B8 DONE -- THE DAMAGE MODEL: the first time either arm was
  shown to REACH.**
  B5 transliterated boss -> player and B6 player -> boss, and EVERY measurement
  in both was an isolated `h.call`, so "the rule is right" and "the rule never
  runs in play" were the same green row.  This increment opened with a
  three-agent pass on that one question and then built the increment on the
  answer.
  **A BOLT DOES REACH THE ACCEPT SET IN FAIR PLAY, WITH NOTHING POKED.**  Eight
  key scripts on bosshit, pressing P1's own keys from the live $B5FD table, 600
  frames each: 18 bolts, 395 hit tests, 4 decrements, damage in ONE of eight.
  The cells go in as a HISTOGRAM WITH ITS N, because the two measurement agents
  each ran one script family and each declared the OPPOSITE cell "the case fair
  play produces" -- NEW TRAPS #84.  Four of the eight scripts emitted class 0
  and produced no bolt at all; what sets the pop class stays OPEN.
  ***AND IT FOUND A SHIPPED DEFECT: EVERY BOLT IN THE GAME FLEW AT HALF
  SPEED.***  Nothing ever seeded $9D83, the third `ADD A,A`, so it read as a NOP
  and the stride was four pixels a tick instead of eight.  B6 named the byte and
  gated the READER -- but the gate seeded the byte itself, so it could not see
  that nothing wrote it.  Only a run that drove the physics WITHOUT seeding it
  could find it, which is what B8's dwell row does.
  **THE STRIDE STEPS OVER ACCEPTED COLUMNS.**  $9D77 moves one tile per test, so
  a static reading says the bolt visits every column -- and it does.  But the
  BOSS MOVES, so dx jumps by 0, 1 or 2, and a measured flight goes -4 -> -2 and
  -1 -> +1, stepping over BOTH accepted columns in one flight (28 tests, HP
  unchanged) while another dwells on -3 and takes 42 -> 37.
  **TWO ROUND-80 GATES, NOT ONE, AND ONLY `ellight` SEPARATES THEM**: $9E71 in
  the tick decides whether the slots run, $9E9E inside the slot decides boss
  test versus enemy scan.  r20_48 and r50_48 separate neither ($9E71's other arm
  drops them on the ELEMENT), and a passive control round is an EMPTY ROW --
  recorded as one, with its blow count and its element, so nobody quotes it.
  **RETRACTION**: B5's "55 and 201 decrements of $A98F/$A990" is not an
  invariant, it is the START BYTE restated through $AA9C's zero guard -- the
  count EQUALS the byte, identically on every round, and the FRAMES (137/429)
  are the only rate-carrying observation.  The port's $AA60 comment ("below the
  table, and harmlessly") is corrected in the same sitting: 254 and 255 bytes
  FORWARD, and they are instruction bytes, not data.
  ALSO: all 768 tiles swept at three boss positions (6/762, 6/762, 3/765) rather
  than B6's 11x11, and the overlap x accept cross -- 25 placements put pixels on
  the boss and exactly ONE is a hit.
  NEW TRAPS #84 (one key script is not a distribution), #85 (a cross-product of
  two measured supports is not a probability) and #86 (a key table's mask is the
  game's AND-mask, not the harness's port value -- handing it over verbatim
  pressed the seven OTHER keys of the half-row, one of which was PAUSE, and
  parked the machine in a DI loop so an entire phase measured nothing).
  New tool `tools/bossdamage.py`, new fixture `build/bossdamage_fixture.json`.
  Mutation battery LISTED 1292 / LIVE 1292 / DEAD ANCHORS 0 / SURVIVORS 0
  (+7 for B8).
  bb.test 843 -> 860.
- [x] **M7.7-H13-B7 DONE -- THE POP-EMIT TAIL AND THE AWARD FORK: where a popped
  bubble becomes a request, a corpse, a mask and a score.**
  **THE CLASS TRAVELS THROUGH AN OPCODE.**  $B6F5 writes (IY+9) into $B742 --
  the operand of $B741's own `LD A,3` -- and then ZEROES (IY+9), so the fork
  reads the class out of an instruction and the slot it came from no longer has
  it.  A PROVENANCE DIFF CANNOT FIND THIS: the tape holds $03 there, the
  round-80 dump $00, and neither is a class.  A static enumeration of the (IY+9)
  writers once concluded classes 2 and 4 were unreachable and $9460 was dead
  code; ONE POOL CENSUS refutes it (elwater carries 2s, ellight 3s, elfire 4s).
  **$B816 RETURNS HL, AND $B771 STORES WHATEVER IT LEFT.**  The engine paid a
  class-1 pop +1 and the machine paid +100.  $B761 loads HL = 1, $B766 CALLs the
  corpse, and $8BC2 ends with HL = $0100 -- so the CORPSE'S OWN RETURN VALUE is
  the award, and class 0, which takes the same `JR c` arm, pays 1.  Measured at
  the pay site with the field SEEDED ZERO, because $80FA clears it at $8164 and
  an unseeded run cannot tell "paid ten" from "paid nothing".
  **A KILL COSTS ($AA5F) MINUS ONE FOR A LIVE ENEMY AND MINUS TWO FOR AN EMPTY
  SLOT.**  I modelled $A437's `BIT 5,(IY+7)` alone and M7.6's corpse gate failed
  immediately: $A437 is reached THROUGH $A447, which returns early when bit 7 is
  SET, so the second decrement needs bit 7 CLEAR **and** bit 5 clear.  Measured
  over eight (IY+7) values with ($AA5F) seeded $77 -- every shipped state reads
  $00 there, so an unseeded run wraps to $FF and reads as garbage -- and $8BF3
  then overwrites (IY+7), clearing bit 5 again, so THE FLAG CANNOT TELL WHICH
  ARM RAN.  Only ($AA5F) can.
  ALSO MEASURED: the mailbox is armed ONLY WHEN ($FFF9) IS EMPTY, and a pop that
  finds one pending drops class, owner and position on the floor; the owner is
  bit 4 folded to 1-or-2 and parked in TWO operands ($B796 and $B7C2); $B7E5
  fires from class FIVE, not four, so the FIRE bubble leaves both masks alone,
  and it ORs into $FDE3 + 10p with NO BOUNDS CHECK (class $FF reaches $B908,
  which is code); and $B816's index is the bubble's own (IY+8) over a SEVEN-slot
  array, so k = 7 writes a corpse over P1's status record at $FDDA and k = 8
  over P2's at $FDE4, with no complaint from anything.
  TWO SELF-INFLICTED ERRORS WORTH RECORDING: I added a second constant for the
  $B80E table when H6 already ships BB_EXTEND_BIT_AT -- one table, two names, the
  exact drift a duplicated constant causes -- and the (IY+7) low bit comes from
  $8BC2's THIRD RNG use, so the gate had to seed $FE86/$FE87 from the fixture's
  own rng_before or it compared two different worlds.
  New tool `tools/popemit.py`, new fixture `build/popemit_fixture.json`.
  Mutation battery LISTED 1285 / LIVE 1285 / DEAD ANCHORS 0 / SURVIVORS 0
  (+30 for B7; two of the first draft's mutations were WITHDRAWN with reasons --
  a duplicated table, and a `SET 5` that $8BF3 overwrites before anything reads
  it).
  bb.test 828 -> 843.
- [x] **M7.7-H13-B6 DONE -- THE ELEMENTAL BOLT: the only thing that damages the
  boss.**
  **THE HIT WINDOW IS NOT A BOX, AND IT HAD NEVER BEEN MEASURED.**  Tile X in
  {bossX-3, bossX} and tile Y in {bossY-3, bossY-2, bossY-1}, so bossX+1,
  bossX+2 and THE BOSS'S OWN ROW all miss.  The separating input against every
  AABB model is a bolt at (bossX+1, bossY-2) -- inside the boss's own sprite and
  not a hit.  Swept 11x11 at THREE positions, because at bossX = 2 the bossX-3
  column is off-screen and a sweep taken there alone passes a port implementing
  offset 0 only (TRAPS #49, twice now in this range).
  **TWO NEGATIVES THAT NEEDED TWO ROUNDS.**  The same bolt over the same enemy on
  round 20 and round 80: the bolt DOES NOT MOVE on the frame it damages the boss
  (X stays 160 against 152, and $9D77 is absent from the round-80 trace), and the
  boss hit SUPPRESSES the enemy kill ($9F51's SCF means $9EFE's CALL nc does not
  fire).  On round 80 the enemy scan is jumped entirely, so "the SCF suppressed
  it" and "there was no enemy" are the same observation there -- which is the
  whole reason both rounds are driven.
  **$93F4, THE ADDRESS $93DC PUSHES, DOES A SECOND JOB**: it clears the request
  AND sets ($FEC5) -- the ISR's even-branch gate -- back to 1, which $93E0
  cleared on the way in.  Transliterating the body without it left the gate dark,
  the bubble manager never ran again, and the failure surfaced four subsystems
  away in M7.5's blow gates.  NEW TRAPS #80.
  **AND AN INSTRUMENT THAT COVERED HALF A ROUTINE REPORTED ZERO.**  The bolt's
  draw goes through itemPoke() and its erase wrote `ram[dst]` directly, so a gate
  counting through itemPoke measured the draw exactly and reported the erase as
  ZERO WRITES -- a confident, precise, wrong number that read like an engine
  fault.  The paths are unified now (which also removes a duplicated ROM guard).
  NEW TRAPS #81.
  ALSO MEASURED: $9E50's TWO self-modified gates, without which driving it
  measures nothing at all -- the first run of this oracle produced an empty
  table; $9D83, the third `ADD A,A`, an OPCODE BYTE THAT IS ALSO STATE which
  reads $87 in BOTH images so no diff can find it; $941B's three bytes with P2's
  facing at $FD87 + 10p and the seeds carrying BIT 3 SET so $F8 and $F0 can be
  told apart; the award of $0100 CONSUMED by the award it feeds; and the sub-row
  pairing -- at Y = $54 the erase spans THREE character rows and the draw two.
  ELEVEN SURVIVORS, every one a gate hole: seeds that could not separate two
  masks, an "at least 32" write count that a missing erase also satisfies, an
  edge detector re-seeded between calls so its write-back was invisible, and an
  award whose pending field is cleared by the very call that reads it.  ONE
  WITHDRAWN: $93E0's clear is restored by $93F4 before anything can read it, and
  the port has no mid-routine interrupt to see the gap.
  New tool `tools/bolt.py`, new fixture `build/bolt_fixture.json`.
  Mutation battery LISTED 1255 / LIVE 1255 / KILLED 1255, zero survivors.
  (1,255 in the full run plus one dead anchor the counting caught again in the
  same session: unifying the erase onto itemPoke merged two ROM guards into
  one, so I5's guard mutation became a DUPLICATE of I2's and is WITHDRAWN as
  subsumed -- verified by re-running both, which still kill.)
  bb.test 806 -> 828.
- [x] **M7.7-H13-B5 DONE -- THE OVERLAP TEST, $A98F/$A990, AND THE DAMAGE TAIL.
  The one place where a faithful port and a naive one differ by a DEATH.**
  **THE PLAN SAID AGENTS; IT IS SOLO NOW, AND B0 IS WHY.**  Both of its STILL
  OPENs are closed: "why the pair decrements at 0.5 per frame while the loop runs
  9.5x" was answered by B0's correction ($AA60 runs on the ODD ISR BRANCH, so
  0.5/frame is exact), and "can $A891..$A897 be non-zero in play" is a cheap
  complete measurement, which this oracle makes.  The criterion held: what was
  unknown machine behaviour in the plan had become a settled answer.
  **$A98F/$A990 ARE LIVE STATE THAT ARE ALSO TWO INSTRUCTIONS INSIDE THEIR OWN
  CALLER.**  `37 C9` (SCF/RET) on the tape makes EVERY POSITION AN OVERLAP;
  `00 00` (NOP/NOP) falls through to the real comparator.  ONE reference exists
  in 64K -- $A987's own CALL operand -- so no census finds it.
  **THE PORT HAD NEVER PUT THE TAPE VALUE THERE TO DECAY FROM.**
  entityUpdatePass() has been decrementing the pair since M7.6 with nothing
  reading it, and reset() left it $00 $00, so every game started 429 frames old.
  Seeded now, and the engine's own walker takes it down.
  **THE CAUSAL ROW**: boss at (2,3), P1 at pixel (200,150) -- nowhere near it --
  and with the pair alive the player DIES ($5A $80 -> $84, +4 := $50).
  **THE DECAY MEASURED ON TWO ROUNDS**, per the standing rule: 55 decrements of
  $A98F (zero at frame 137) and 201 of $A990 (frame 429) on round 1, and the SAME
  55 and 201 on round 20, where $AA57 is 7 rather than 5.  The pair's rate is NOT
  a function of the enemy count, although the hold-off histogram beside it is --
  which is exactly what the plan asked to be checked rather than assumed.
  **AND THE PAIR HAS FOUR CORNERS, NOT TWO.**  `37 00` falls through and behaves
  as the comparator, but `00 C9` is NOP/RET and returns with the caller's carry:
  ALWAYS MISS, a third answer neither endpoint gives.  Measured 5 / 2 / 2 / 0
  hits out of five probes.  The port models the two ENDPOINTS and DECLARES the
  rest, with a proof that they are unreachable: $A98F reaches zero at frame 137
  while $A990 is still near $89, and the only other consumer ($A9B1, the giant
  object) needs a round build, which cannot happen inside the 429 frames the
  decay takes.  NEW TRAPS #79.
  FIVE SURVIVORS, all of them gate holes rather than engine faults: the pair
  tested on one byte or for "non-zero" (the corner table), the $3F tile mask
  (WITHDRAWN -- px >> 3 is at most 31 for any byte), the carried and dying bits
  swapped (both end in "nothing written", so the gate had to assert WHICH GUARD
  refused), and `SET 7` invisible because every kill row already had bit 7 set
  (a bit-7-clear row added).
  New tool `tools/bossoverlap.py`, new fixture `build/bossoverlap_fixture.json`.
  Mutation battery LISTED 1212 / LIVE 1212 / KILLED 1212 in one clean run, zero
  survivors and zero dead anchors.
  bb.test 790 -> 806.
- [x] **M7.7-H13-B4 DONE -- THE BOSS DRAW AND ERASE, AND $9D4C's
  RECONSTRUCTION.**
  **THE ERASE RECONSTRUCTS THE ATTRIBUTES, IT DOES NOT RESTORE THEM** -- $9D4C
  reads BIT 5 of the COLOUR shadow and writes the round's open or solid
  attribute.  On every captured world the cells already hold what it writes, so
  the separator is a POISONED PAIR ($5A/$A5, values no palette produces).
  **AND THE PLAN'S OWN CONTROLS COULD NOT FAIL**, which the H13 falsification
  pass caught before the oracle existed: every natural row is UNIFORM, so a port
  reading bit 5 from the WRONG ADDRESS is byte-identical on boss, bosskilled,
  bossspawn and both uniform controls.  Only bosshit discriminates, in TWO cells
  of sixteen.  The world that replaced them is a CHECKERBOARD -- bit 5 =
  (row + col) & 1 -- which makes all sixteen discriminating.  NEW TRAPS #77, and
  the same shape is used twice more: the shadow seeded (addr * 7) & $FF for the
  128-byte copy, and the sprite seeded (addr * 11) & $FF for the 128-byte blit.
  **A POINTER SWEEP FOUND DATA THE PORT HAD NEVER SHIPPED.**  Poking $A8FD over
  every C the routine accepts showed the engine writing SIXTEEN ZEROS where the
  machine writes the boss's colours: $A881..$A8C0 is tape data nobody had
  extracted, and no gate comparing only ADDRESSES could have seen it.  Shipped as
  BB_BOSS_ATTR.  Three of the seven slots are real data, C=1's block IS the enemy
  WAKE-UP SCHEDULE the spawner writes, and C=4/5/6 point into the draw routine's
  own opcodes -- as does the TAPE RESIDUE $A881, which is not of the array's form
  at all.  NEW TRAPS #78.
  **TRAPS #44 DEMONSTRATED RATHER THAN CITED**: seeded with the value $9D4C
  writes, sixteen writes report ZERO changed bytes.  And on bossspawn rows 0 and
  1 both divert through the $FD00 guard's $01FF, so sixteen writes show as twelve
  distinct and the DRAW falls from 128 bitmap bytes to 64.
  **TRAPS #75 RE-PAID, IN MY OWN NEW CODE**: the erase's attribute walk was
  written `(ad & 0xFF00) | el`, and every attribute page has bit 8 set, so the OR
  forgave a sixteen-bit E and the eight-bit mask was decorative.  Written with
  `+` the mutation dies.  Two days, two increments, the same operator.
  ONE MUTATION WITHDRAWN as a provable equivalent: `INC H` and `ADD HL,$100` are
  the same operation on the high byte -- both wrap $FF to $00 -- so a
  "sixteen-bit pixel-row step" cannot differ from the eight-bit one anywhere.
  New tool `tools/bossdraw.py`, new fixture `build/bossdraw_fixture.json`, new
  constant `BB_BOSS_ATTR` (48 bytes of tape data).
  Mutation battery LISTED 1187 / LIVE 1187 / KILLED 1187 in one clean run, zero
  survivors and zero dead anchors.
  bb.test 764 -> 790.
- [x] **M7.7-H13-B3 DONE -- THE BOSS TICK: gates, divider, move frame, bounce,
  spawn.**
  **THE BOX IS TWO REGISTER PAIRS, NOT TWO CONSTANTS**, so it is read off the
  machine by WATCHING THE BOSS MOVE: X walks [2,26] and Y [3,19] over 266 bodies
  in 900 frames, with the velocity flipping at exactly those coordinates.  A port
  with the right numbers in the wrong pair still fails.
  **THE FOUR GATES ARE DRIVEN AS A TABLE, BOTH SIDES OF EACH.**  A gate that is
  merely "usually taken" is indistinguishable from one always taken until the row
  that separates them exists -- and the row that matters here is a BOSS-LESS
  ROUND 81, which does NOT spawn, because the round gate comes first.  Round 80
  ticks the divider whether or not the body runs; a round the boss is not on
  leaves it untouched.
  **$AA38 DRIVEN OVER EVERY INPUT IT HAS**: 256 positions x 6 velocities x 2
  axes.  The KEPT set is exactly [lo - v, hi - 1 - v] MODULO 256 -- for X with
  v = 3 that is [0,23] AND {255}, the eight-bit add showing through.
  **NOTHING INITIALISES THE VELOCITIES**, and only a CHAINED BUILD can say so:
  81 sequential builds carrying poisoned $03/$FD reach round 81 with them intact,
  survive the SPAWN, and then step three tiles a tick.  Poking a fresh state
  could never prove a negative about every round before 80.
  **$A8DC HAS ZERO REFERENCES IN 64K** -- not a store, not a read, not a pointer
  load -- and is still the high byte of the draw's offset: BUILT, it moves all
  144 writes by +$100.
  **AND THE PLAN'S "INHERITED" LIST IS WRONG ABOUT ONE BYTE.**  $AA06, $A82D,
  $A98F, $A990 and $A8DB do survive the 80 -> 81 advance; $9F62 does not, and the
  WRITE LOG names the writer -- $79A8, the self-doubling seeder, with $14.
  $A839 is entry 12 of the $9AC1 clear table and $9855 zeroes it.  Neither was
  inferred from the value.
  **THREE SURVIVORS, AND TWO OF THEM WERE TRAPS #63 AGAIN**: the "share one
  velocity byte" and "lend Y the X bounds" mutations live in `bossBody`, and the
  gate was calling `bossBounce` itself -- a call path that does not include the
  code under test.  Driven through `bossBody` they die at once.  The third was a
  gate that counted the spawn without checking WHAT it spawned (A = 3 puts the
  same boss in the same place with a different sprite).
  ALSO WORTH RECORDING, because it is TRAPS #60 in a new shape: all 266 sampled
  bodies carry dx == dy == 1 with both coordinates mid-range, so NOT ONE OF THEM
  can tell the two axes apart.  The rows that can are the ~30 where a velocity
  REVERSED, plus one BUILT row with X and Y both at 19 -- where Y must reverse
  and X must not.  **No new traps this increment**; it re-paid #60 and #63.
  The erase, the draw, the overlap test and the kill are NAMED COUNTED STUBS
  (B4 and B5), counted so that "the body ran" and "the body ran and drew" are
  different observations.
  New tool `tools/bosstick.py`, new fixture `build/bosstick_fixture.json`.
  Mutation battery LISTED 1156 / LIVE 1156 / KILLED 1156, zero survivors.
  (1,155 in the full run plus ONE dead anchor the new counting caught IN THE
  SAME SESSION IT WAS CREATED: wiring $A9ED disarmed a B0 mutation anchored on
  its `null` chain entry.  Repaired and re-killed -- which is exactly what
  TRAPS #73 exists for, working this time.)
  bb.test 744 -> 764.
- [x] **M7.7-H13-B2 DONE -- THE BOSS HP BYTE, THE DEATH TAIL AND "WELL DONE!".**
  **THE BRANCH HAD BEEN MEASURED ON ONE INPUT.**  `$9F62` is seeded 42 and only
  ever decremented, so every state on disk holds `$2A` and `$8E51 DEC A /
  $8E52 JP p` had never been asked anything else.  All 256 poked: **1..128 are
  ALIVE and 0 AND 129..255 are DEAD** -- the byte is SIGNED after the DEC, so
  "zero means dead" is right on one value in 129.  The sweep drives
  `roundClearCheck`, the WIRED predicate, which is what closes the H13 critic's
  C3: `$9F62` was not among `clear_fixture`'s watch keys, so the wired boss arm
  was ungated and a constant-answer mutation survived it.  **`$9F62` is now in
  that fixture too**, seeded before the call and asserted after.
  **THE SEEDER DOUBLES ITSELF.**  `$79A2` is `LD A,n` and `$79A3` IS ITS OPERAND:
  tape `3E 05`, `$0A` on a round-80 state, `$14` on 81.  "`$79A2` seeds the HP"
  and "`$98B2` seeds it" agree on every captured world -- `$9F62` is `$2A`
  everywhere -- and only this byte separates them.
  **THE DEATH IS NOT A LATCH AND NOT A WAIT**: it returns Z on the frame the test
  sees 0, and 23,967,550 T are spent INSIDE the call, 23,951,013 of them in three
  `$9573` busy waits.  `$9573` has THREE counters and they are not
  interchangeable; the engine COUNTS the loop and lands on the machine's T
  exactly for all seven rows of an (A,B) grid including (255,255) and (1,1).
  **NOTHING ANIMATES**: 208 display WRITES over 138 CHANGED bytes and eleven
  attribute cells of `$C5`.  And **nine bytes are never written, asserted from a
  WRITE LOG and not from a diff** -- three of them (`$8E3B`, `$8609`, `$9F62`)
  have to hold the values that reach the branch, so no marker can be seeded into
  them and only a log can speak for them.  `$8ECF` and `$D167` are entered zero
  times.
  **`$8E56`'s OWN WRITE IS ONE A DIFF CANNOT SEE**: `LD A,$10 / LD ($FFEF),A`
  lands in the pending field and `$80FA`'s cleanup zeroes it two instructions
  later.  Gated with the TAIL CUT -- the award stubbed out -- which is the same
  method the mid-game join needed in B1.
  **TWO SURVIVORS TAUGHT SOMETHING, AND NEITHER WAS A GATE HOLE.**  "the banner
  walk is SIXTEEN bit" survived because the transliteration wrote
  `ram[page | l]`, and every attribute page has bit 8 set, so `$5900 | $100` is
  `$5900` and the OR forgives the carry the mask exists to catch.  Rewritten as
  `ram[(page + l) & 0xFFFF]` it dies at once -- NEW TRAPS #75, which is #70 one
  level up (the CONTAINER masked there, the OPERATOR here).  And "the award goes
  to P1" survived until the index was swept: `$9F09` is 1 in all four boss
  states, and poked 0/1/2/3 the award pays the HIGH SCORE slot / P1 / P2 /
  nobody.  **Index 0's guard is `$FD7D`, three bytes BELOW the entity table** --
  `$A0` on every state, so index 0 always passes a guard belonging to no player,
  and the port carries zeros there.  NEW TRAPS #76.
  New tool `tools/bossdeath.py`, new fixture `build/bossdeath_fixture.json`,
  `build/clear_fixture.json` re-captured with `$9F62`.
  Mutation battery LISTED 1123 / LIVE 1123 / KILLED 1123 in ONE clean run --
  zero survivors and zero dead anchors, the first run since the counting was
  fixed in which all three numbers agree.
  bb.test 726 -> 743.
- [x] **M7.7-H13-B1 DONE -- THE EXIT AND THE GAME LIFECYCLE.**
  **THE TRIGGER IS UNREACHABLE FROM EVERY WORLD THIS PROJECT OWNS.**  `$8E2A`
  ends a game by finding bit 7 CLEAR in BOTH `$FD87` and `$FD91`, and 48 of the
  49 saved states have P1's bit 7 SET -- the exception is `afterctrl48`, which is
  the front end.  So the world is BUILT and PAIRED: armed it reaches `$8CDC` in
  0/0/37 frames on boss/round1_48/play1p48, and the control takes 1576/1796
  frames or never -- and when the control DOES arrive it is a natural death, not
  the trigger, which is why the control is reported with its frame count rather
  than as a bare "no".  `$FEC9` is seeded ZERO, never `$B4`: seeding it with the
  value the routine writes is TRAPS #44 exactly.
  **THE SCREEN COUNTS TO THE EIGHT-BIT WRAP, NOT TO 76**: measured 76/1/128/255/
  192 frames from `$B4`/`$FF`/`$80`/`$01`/`$40`, and seeding only `$B4` cannot
  tell "counts to the wrap" from "waits 76".  Its attributes are `$4E` and the
  instruction says `LD A,14` -- the `$40` is added INSIDE `$995A`, so the value
  read and the value written differ and only the measurement has it right.
  **"GAME OVER" AND "START A GAME" ARE 38 BYTES APART**: when the counter wraps
  the machine falls through into `$8D02`, which re-PUSHes `$8CDC`, calls `$96DF`
  and calls `$97F8`.  The end-to-end gate drives it: from a world with both
  players out, one step ends the game, 76 run the screen WITH ZERO PASSES, and
  the next is round 1 with six credits and three lives each.
  **TWO CENSUS ERRORS FOUND, ONE OF THEM IN THIS REPOSITORY'S OWN COMMENTS.**
  `$FEC9` has THREE writers and a `32 C9 FE` scan finds two, because `$8CFC`
  loads the address into HL and INCs through it.  And `web/game.js` said `$7FC0`'s
  "sole reference in both images is `CC C0 7F` (CALL z), so A PORT THAT NEVER
  BUILDS ROUND 1 HAS NO HUD AT ALL" -- a census of the ADDRESS finds `$7F58
  CALL z` AND `$9998 JP`, the mid-game join's tail jump, so the HUD is repainted
  whenever a second player joins, on ANY round.  NEW TRAPS #74.
  **`$9961` IS THE MID-GAME JOIN, not "hurryText"** as the chain comment had it:
  half-row `$F7` is read ONCE and rotated TWICE, and BOTH branches take ONE credit
  at the shared `$9980 DEC (HL)` -- "a two-player start costs two credits" is the
  natural reading and it is wrong.  **Every join row is measured TWICE**, once
  with its tail jump cut to a RET, because `$7FC0` RRD-converts both score records
  on its way past and a gate reading them afterwards is measuring the HUD.
  **AND SEVEN MUTATIONS HAD BEEN DEAD FOR ELEVEN INCREMENTS.**  I10 gave
  `itemBlit` a `rec` and an `or_` parameter; seven I2 mutations anchored on the
  old call shape stopped matching that day, and every increment since has quoted
  "1038/1038 killed", which is the length of the LIST.  All seven are repaired and
  re-killed.  NEW TRAPS #73: report LISTED, LIVE and KILLED as three numbers, and
  the battery now prints them -- **and the first run that printed them found
  FOURTEEN MORE**, from I10, I11, H0, H2, H3, H10 and from B0 itself (B1's own
  edit to `step()` disarmed a B0 mutation four hours after it was written).
  Thirteen were comment, whitespace and refactor drift and are repaired and
  killed; the fourteenth was REMOVED, because H2 had already withdrawn it as a
  provable equivalent and left it in the list, where the drifting anchor then hid
  it -- repairing it had re-armed an answered question.
  **AND A MUTATION HUNG THE BATTERY INSTEAD OF FAILING IT.**  One unbounded
  `while (!(g.ram[0x8DBD] & 1)) g.step(...)` in the ISR-cost gate waited for a
  counter that a mutation had stopped; node span for 203 CPU-seconds and the run
  neither killed the mutation nor reported a survivor -- and when it was
  interrupted the restore failed with `OSError: [Errno 22]`, leaving a LIVE
  MUTATION in `web/game.js` (`$C019`'s Y mask as `$F0` instead of `$F8`).  It was
  found by the suite going red on two I10 rows, restored, and re-verified.  The
  wait is now bounded to four steps with its own assertion, and `run()` carries a
  180-second timeout that reports a hang as `<hung>` rather than as silence.
  The GLYPHS of "GAME OVER" are a DECLARED DEPARTURE -- `$802E` draws through the
  ROM charset at `$3C00` and this port ships no ROM -- named and counted
  (`bannerGlyphs`), and belonging with the rest of the text system in the front
  end.  `$96DF`'s title-screen half (`$97EB`'s pattern fill, the RNG warm-up, the
  record table at `$9A85`) is NAMED OUT of this increment, not absorbed.
  New tool `tools/gameover.py`, new fixture `build/gameover_fixture.json`.
  Mutation battery LISTED 1100 / LIVE 1100 / KILLED 1100 -- zero survivors and
  zero dead anchors.  (1,087 of them in the full run; the fourteen anchors that
  run exposed were repaired and re-killed in a targeted re-run immediately after,
  and the fourteenth was WITHDRAWN again -- H2 had already answered it as a
  provable equivalent and left it in the list, where a drifting anchor hid it.)
  bb.test 698 -> 726.
- [x] **M7.7-H13-B0 DONE -- THE PASS CLOCK AND THE CHAIN SPINE.  The main-loop
  chain is no longer a stub list.**
  **THE WORLD IS NOT A STATE, IT IS TWO MACHINES.**  Every divider downstream of
  `$8D0C` counts PASSES, and on one capture "the divider counts frames" and "the
  divider counts passes" are the same function -- they agree at `32/9.5`.  The
  oracle runs `build/boss.pkl` with `contended=True` and `=False`: 8,548 passes
  in 900 frames against 8,674, and every table is asserted across both.
  **IT REFUTED THE PLAN'S OWN HEADLINE.**  "the PASS interval is exactly 32 in
  every interval of both runs" is true over 300 frames and FALSE over 900 --
  32/35/36/38 and 32/38/47.  What IS exactly 32 in both is the interval in
  **TICKS**, and a tick is a pass on which `$A9FC`'s involution did not latch (13
  and 21 latches in 900 frames).  NEW TRAPS #71: an interval claim carries its
  window, and a short window hides the rare state.
  **AND IT REFUTED "ONE EXIT".**  `$8D63-$8D6F` reads half-row `$FE` bit 0 (CAPS
  SHIFT) and half-row `$7F` bit 0 (SPACE) and RETs when both are held -- **BREAK**
  -- through the same `$8CDC` that `$8D05` pushed.  Measured: 197 steps from the
  game-over poke, 196 from the keys, and a CONTROL that reaches `$8CDC` in no
  number of steps at all (3,000,000 tried).
  **AND "NO HALT IN THE LOOP" IS TRUE OF THE 101 BYTES AND FALSE OF THE LOOP**:
  `$7E80`'s subtree reaches `$7EC2 EI / HALT` three times in 900 frames, and the
  frame it happens in runs ONE pass against a 6..12 mode.  `step()` now honours
  a blocking callee.
  **`$A9FC` IS AN INVOLUTION** (`op' = f - op`, a 2-cycle whose operands sum to
  `($8DBD)`), not the divider it looks like.  From either shipped boss state it
  latches ZERO times in 300 frames -- so the orbit is BUILT, seeded AT THE CALL
  rather than one ISR earlier, and then it latches immediately and at stride 2.
  **WIRING `$C002` FOUND A MISSING RESET.**  It had been gated in isolation since
  I10 and was correct; wired, it wrote 642 display bytes on a still round, because
  `$5CE0` is INSIDE the relocated block `$5B00..$61A7` and `reset()` had never run
  the round build's own `$BF39` clear.  The machine has the table ZERO on
  `round1_48`, `r20_48` and `boss`, and `(IY+3) = 2` in every bubble slot -- which
  is `$BF4B`, one instruction inside the same chain.  Fixed with the machine's own
  routine, not a fill.  NEW TRAPS #72.
  **FOUR MUTATIONS WITHDRAWN AS EQUIVALENTS, each with its reason**: swapping the
  two BREAK half-rows (both tested at bit 0 under an AND -- no input separates
  them); `$7FFC`'s `LD HL,$5820` reload (31 writes plus the `INC L` land exactly
  on `$5820`, so the machine's own reload is redundant); `$7FFC`'s 8-bit walk (it
  starts at `$00` and writes 64 cells, so L cannot wrap and the routine takes no
  argument that could reach it); and `($FEC8) & 0xFFFF` -- **which is TRAPS #70:
  the store is into a `Uint8Array`, so the container already masks and the
  mutation cannot express the bug.**  It was replaced by "the counter is driven by
  the frame, not by the pass", which dies at once.
  The chain is now a LIST with a method name or null per entry, so
  "transliterated" and "wired" cannot drift apart silently: three are wired
  (`$915F`, `$C002`, `$8669`), sixteen are named stubs, and `$8E3A` is the loop's
  own branch.  All twenty are reached from their own CALL, 1,198/1,198.
  **DECLARED**: the port's pass rate is 9.365/frame on its round-1 world against
  the machine's 9.498/9.638 on the boss round -- different worlds, and the ISR
  cost model underneath is the one docs/TIMING.md refuted.  32 ticks is 3.42
  frames, inside the machine's own 3..5 spread, and what is asserted faithfully is
  the STRUCTURE (per pass vs per frame), not the rate.
  New tool `tools/passclock.py`, new fixture `build/passclock_fixture.json`.
  Mutation battery: 27 new mutations, all killed, zero survivors.
  bb.test 674 -> 698.
- [x] **2026-09-24, M7.23 -- `$9AEB` WIRED, and $5B00/$5B0A WERE NEVER
  UNIMPLEMENTED.**  EIGHTEEN of the nineteen chain calls now run in the built
  page; `$948F` extendDone is the only one left.  `$9AEB` is the ENEMY
  SPECIAL-MOVE SPAWNER: it drafts one eligible enemy into one of two
  pseudo-entity slots, `$5B00` and `$5B0A`, whose per-frame update at `$9BB4`
  is a NAMED COUNTED STUB (`enemyFireUpdate`) for a later increment.
  The B-series differential tagged both slots UNIMPLEMENTED because they were
  static across all 1,600 sampled passes -- and the reason is the ROSTER, not
  the routine.  `$9B41` accepts only types 1, 5, 6 and 7, and every sampled
  state is on internal round 1, whose three enemies are all type 0.  MEASURED
  over the spawn table at `$7491`: **45 of the 80 regular rounds carry a type
  it accepts**, eleven of them the type 7 that skips the row match.
  What the increment paid for: `$9B31`'s `SUB 3 / CP C / RET c` is EIGHT-BIT
  and cannot refuse a low index at all, so a count of 2 passes where 3 refuses
  (TRAPS #143); `$5B0A` is reached by FALL-THROUGH and the first sweep for a
  seed that fills it found none and said nothing (TRAPS #144); and one mutation
  re-tested a check three lines above itself and "survived" (TRAPS #145).
  `$9B52`'s `SET 1,(HL)` marks the enemy's **+7**, not its +8, which is the bit
  `$9B91` refuses on -- so one enemy cannot be drafted twice.
  New tool `tools/enemyfire.py`, new fixture `build/enemyfire_fixture.json`.
  Mutation battery: 66 new cases, all killed, zero survivors (three withdrawn
  as provable equivalents with their reasons, one replaced for mutating
  nothing).  bb.test 1,124 -> 1,145.
- [x] **2026-09-24, M7.24 -- `$948F` WIRED.  THE CHAIN IS NINETEEN OF
  NINETEEN.**  Every entry of `$8D25-$8D5E` now carries a method name and none
  is null.  `$948F` is the EXTEND trigger: `($FED5)` set and consumed, both
  players offered to `$94C2`, a counter bumped unless it would reach 4, and then
  `JP $957E` so the letter panel's RET is the routine's RET.
  **THIS IS NOT A DEAD BRANCH**: `($FED5)`'s only writer is `$B808` inside the
  bubble-pop class handler, which the port has had since B-series as
  `bubbleClassMask` -- it was write-only, and nothing read or lowered it.
  What the increment paid for:
  * `$94C2` **does not return when it accepts** -- `POP HL / POP HL / JP $8D09`
    discards its caller's return address AND `$948F`'s, so once P1 completes,
    P2's call, the counter, `$7E04`, `$BF5B` and the panel are all unreachable.
    The port models the not-returning; the life award at `$9558` and the round
    advance are DECLARED GAPS, and so is the resulting wedge (the stub does not
    clear `(IX+$63)`, so a completed player stops the panel redraw for good).
  * `$94AD` is `CP 4`, an **equality** -- 3 stays 3 with both calls skipped, and
    4 goes to 5.  In play it never exceeds 3 because `($FECB)` is entry [16] of
    the `$9AC1` round-advance table, so the effect is three element re-rolls per
    round and then a frozen class.
  * **Two round-start call sites were stubs for routines the port already had**
    -- `$986F CALL $957E` is `extendRow()` and `$98A7 CALL $BF39` is
    `poolClearChain()`.  TRAPS #58's shape, seventh and eighth instances.  Both
    measured with the targets POISONED, because unpoisoned each writes ZERO.
  * `$7E04` had one site inlined and a second that could not reach it; it is a
    routine now (`elemRedraw`), and it is a DECLARED `LD A,R` SUBSTITUTE, so its
    value is 5..12 by construction and the machine's sample is noise.
  New tool `tools/extenddone.py`, new fixture `build/extenddone_fixture.json`.
  Mutation battery: 40 cases written, 38 kept and all killed (two withdrawn as
  provable equivalents with their reasons).  bb.test 1,145 -> 1,153.
  TRAPS #146-#150: a snapshot taken before the arm reports the probe's own
  stack; a filter wide enough to hide the measurement; a gate that measures the
  step BEFORE the one it names; six things now lost to escape handling; and two
  states in the roster that are HUNG 128K captures.

- [x] **2026-09-24, M7.25 -- `$94C2` WIRED: the EXTEND completion, a 4.9-second
  cutscene that awards a life and advances the round.**  MEASURED end to end at
  **17,162,734 T, 245.6 frames**, from `$94C2` to `$8D09`.  M7.24's declared
  wedge is lifted: the completion clears `(IX+$63)`.
  What the increment paid for:
  * **`$87B2 := $C9` turns ITEM COLLECTION OFF** for the whole display -- a
    fifth opcode-as-mode-switch, and the port already honoured it, so only a
    world with a player standing on a shower item could show it.
  * **The wipe is 6,912 bytes, `$E000..$FAFF`** -- display window plus colour
    shadow -- so `shadowClear()`'s 6,144 could not be reused.
  * **The shower is 320 writes into 32 bytes, ten times over**, and the item
    ageing that would spoil it is gated on `($86CD) AND ($86CF)`, which `$8689`
    never advances.  A port whose `reset()` leaves that at zero ages every
    record and looks like a transliteration bug.
  * **`$9561` is three instructions, not the two calls above it** -- `$9568`'s
    displacement targets `$9561`.  The other reading makes the routine minutes
    long, and it was in the reconnaissance I was handed.
  * **A ninth missing `reset()` seed**: bit 0 of `(IY+$5A)` is the PLAYER
    NUMBER, `$00`/`$01` measured on four states, and the port had both at zero,
    so the EXTEND banner named player one twice.
  New tool `tools/extcomp.py`, new fixture `build/extcomp_fixture.json`.
  Mutation battery: 62 cases written, 58 kept and all killed (two provable
  equivalents and two unobservable orderings withdrawn with their reasons).
  bb.test 1,154 -> 1,166.
  TRAPS #151-#154: a probe that cannot aim (IXh/IXl are 8/9, not 13/14, and the
  tool reported that player two can never complete EXTEND); a poison wider than
  the routine; attributing writes by PC before explaining them; and a census
  compared against one taken over a different window.

- [x] **2026-09-25, M7.26 -- `$801D` WIRED: the double-height banner printer,
  and TWO declared glyph gaps closed at once.**  `$94C2`'s "N I C E   n  P" and
  `$8F78`'s "PERFECT !" now draw, through ONE transliteration of `$802E` with
  `$803C` carried as the live mode operand it is.
  * **The font is INDEXED BY CHARACTER CODE**, fifteen cells covering all three
    strings that go through `$802E` on wired paths, so the port no longer holds
    a second position-indexed printer beside the general one.  The seven codes
    "HURRY UP !" uses keep `make_hurry.py`'s exact bytes and M7.20's 1,100-odd
    checks are what prove the repointed blit moved nothing.
  * **`$8058` is TWO character cells** -- four source rows doubled into each --
    and the routine has THREE adds at TWO widths: `INC L` and `INC H` eight-bit,
    `ADD HL,BC` sixteen.  All three are now driven from an address where that
    add is on its boundary.
  * The strings are seeded into the byte image at their machine addresses, so
    `$94E7`'s store at `$9AB3` overwrites the banner's tenth character the way
    the machine does rather than through a special case in the port.
  New tools `tools/make_banner.py` and `tools/banner.py`, new fixtures
  `build/bannerfont.json` and `build/banner_fixture.json`.
  Mutation battery: 40 cases written, 36 kept and all killed (four withdrawn as
  provable equivalents, two of them VERIFIED over 1,024 worlds rather than
  argued).  bb.test 1,166 -> 1,178.
  TRAPS #155-#157: "not identical" is not "a different face" (the first T and F
  differed from the ROM in ONE and TWO bytes of eight, so the assert is a
  minimum now); the outer mask can absorb the inner one; and a gate named for a
  wrap that drives no wrap -- three mutations to three adds lived behind one
  sentence about column 30.

- [x] **2026-09-25, M7.27 -- ONE FONT AND ONE PRINTER.**  A pure refactor, and
  the suite is what made it safe.  `hurryGlyphs` carried a position-indexed font
  and its own eight-row blit -- a second transliteration of `$802E` beside the
  general one, with two places for the same behaviour to drift.  It is
  `LD IX,$9A1C / CALL $802E` now and nothing else.
  * `BB_HURRY_FONT` and `tools/make_hurry.py` are retired.  `make_banner.py`
    covers those seven codes with the SAME BYTES plus eight more, under a
    stricter assert, and reproduces M7.20's per-string aggregate exactly -- 8
    inked cells, 43 of 64 bytes differing, two blanks -- so nothing is lost.
  * **`build/hurryfont.json` is kept FROZEN** as the record of what M7.20 drew,
    and the suite asserts the surviving font reproduces it CELL FOR CELL.  That
    row is the proof the change was pixel-neutral, and it is what will say so if
    the banner ever moves.
  * M7.26 had also split the HURRY comment block from the constant it described;
    that is tidied here.
  Mutation battery: 4 new cases, all killed.  Seven older cases went dead:
  three RE-ANCHORED, one RE-AIMED, and **three withdrawn as SUPERSEDED BY
  CONSTRUCTION** -- a code-indexed font cannot hold two different R glyphs or
  two different spaces, so those bugs stopped being expressible.  bb.test stays
  at 1,178: no behaviour changed, which is the whole claim.
  TRAPS #158-#159: a mutation superseded by construction is evidence a refactor
  removed a class of bug (and must name the row that carries the claim now); and
  a gate that wipes all 64K removes the thing under test once data moves into
  the world image.

- [x] **2026-09-25, M7.28 -- the ROUND BANNER DRAWS, and $9904 erases it for
  real.**  Two of the three remaining `$802E` call sites are wired; `$8EA7`'s
  boss banner is the one left.
  * **`$98C4` and `$98D4` are TWO CALLS ON ONE POINTER** -- `$802E`'s own
    `INC IX` carries it from "ROUND    n" into "READY    !", so the second row's
    address is never named, and `$98BD` is INSIDE the loop so all 256 passes
    start the chain again.  The port carries the pointer now instead of naming
    `$9A11`.
  * **`$9904` restores from the SHADOW and DERIVES the attributes** -- 80
    display bytes and 10 attribute cells per call, measured.  It had been a
    stub that RESTORED the twenty cells, which modelled the outcome honestly
    while the glyphs were not drawn and became wrong the moment they were.
  * The font grew to 26 codes (O, A, D and the digits); "HURRY UP !" still
    matches the frozen M7.20 record, so that banner has not moved.
  Mutation battery: 29 cases written, 28 kept and all killed.  bb.test
  1,178 -> 1,185.
  SIX older cases went dead and all six are re-anchored -- one of them for a
  reason this project had not hit before: H11's anchor did not MOVE, $9904's
  LDIR is spelled identically to scrollCopy32's and made it AMBIGUOUS.
  TRAPS #160-#162: "unreachable" needs ENUMERATING, not sampling -- I nearly
  withdrew a live mutation because the one world I tried happened to agree; a
  stub that models the OUTCOME stops being honest when its neighbour is wired;
  and new code can kill an old anchor without moving it.

- [x] **2026-09-25, M7.29 -- `$8EA7` WIRED, and a COVERAGE CLAIM CORRECTED.**
  Six strings -- `$9A06`, `$9A11`, `$9A1C`, `$9A27`, `$9A9F`, `$9AA9` -- take
  their glyphs from the substitute font instead of being counted.
  **This increment first claimed `$8EA7` was the LAST `$802E` call site.  It is
  not.**  A byte grep finds NINE references and four are still counted: the
  HUD's two rows at `$7FE9`/`$7FEF`, "GAME OVER" at `$8CEE` and "CREDIT n" at
  `$9758`.  I had counted the six strings in the port's own table.  The suite
  row is a CENSUS now and asserts both halves (TRAPS #165).
  * **One HL addresses both runs and they are DIFFERENT LENGTHS**: `$8E83` loads
    B with ELEVEN, "WELL DONE!" is TEN characters, so the attribute run is one
    cell wider than the text -- an asymmetry that is invisible while the glyphs
    are counted rather than drawn.
  * Both eight-bit `INC L` walks driven from `$48FA`, where each wraps inside
    its own page group; the shipped `$484B` reaches neither.
  * `$995A`'s `OR $40` SWEPT over seven values, because on the one attribute
    this site ships "it ORs $40" and "it writes $C5" are the same sentence.
  * The font is at 28 codes (W and L added, both at least three bytes from the
    ROM's -- L's first draft was ONE, the same trap T, F and D fell into).
  Mutation battery: 14 cases written, 13 kept and all killed; one withdrawn as a
  duplicate of B2's, which already owned the claim.  bb.test 1,185 -> 1,191.
  **AND THE RUNNER TAKES A LOCK NOW.**  Two concurrent batteries share
  `workers/w0..wN`, so they hand each other half-mutated trees: a run overlapping
  another reported SIXTEEN survivors across milestones untouched in weeks, where
  the same tree alone gives zero.  `parallel.py` refuses a second run by name and
  pid (TRAPS #166).
  TRAPS #163-#164: adding a parameter degrades every existing caller SILENTLY
  -- two older rows kept passing three arguments and went on PASSING while
  drawing nothing, so `bannerPrint` throws on a bad address now; and a COUNT and
  a TERMINATOR are two different bounds in one call.

- [x] **2026-09-25, M7.30 -- `$9758`, the CREDIT line: transliterated, gated, and
  registered as UNCALLED.**  "CREDIT 6" at `$50F7`, eight characters and 64
  display writes, then NINE attribute cells at `$5AF7..$5AFF` as `$45`.
  **The font needed NOTHING NEW** -- C, R, E, D, I, T, space and 6 were already
  drawn for PERFECT, READY and the round number, which is what made this the
  right one to take first.
  * **The ninth attribute cell is `$5AFF`, the last cell of the attribute file**:
    the run fills the bottom row to the screen edge while the text stops one
    short.  Same asymmetry as `$8EA7`.
  * **And the off-by-one belongs to the HAND-CODED sites, not the printer.**  The
    four title strings above it come from the column-major table at `$9A85` and
    its counts match their lengths exactly, 24/21/20/14 -- four out of four --
    against `$8E83`'s 11-for-10 and `$9760`'s 9-for-8.
  * **It is NOT CALLED and that is recorded.**  `$9758` is reached by fall-through
    from the title text block, whose four strings need ~30 glyphs including
    LOWERCASE, and `gameReset()` stops at `$970E` with the title screen named out.
    Wiring it early would draw a credit line onto a titleless screen, so it joins
    the UNCALLED census -- eighteenth entry -- with a gate proving it is unreached
    today and works when called.
  Mutation battery: 14 cases written, 12 kept and all killed (two withdrawn:
  `$995A`'s OR absorbs the attribute value, and the draw/paint order is
  unobservable and gated against the source).  bb.test 1,191 -> 1,195.
  **AND THE BATTERY'S BASELINE CHECK WAS WRONG.**  It asked whether anything
  FAILED; a syntax error in `bb.test.js` produces no FAIL lines, so a broken
  suite read as a healthy baseline while every case died on the same crash.  It
  requires the `N/N checks passed` line and a plausible count now, verified by
  breaking the suite on purpose (TRAPS #167).

- [x] **2026-09-25, M7.31 -- `$8CEE`: the GAME OVER glyphs, and one property I
  got wrong four times.**  H13-B1 measured this screen's countdown, its three
  `$FEC9` writers and its reset, and DECLARED the glyphs: the engine wrote the
  nine attribute cells and COUNTED the glyphs it owed.  M7.31 draws them.
  "GAME OVER" from `$9A95`, **72 display writes** at `$484C`, IX left at `$9A9F`
  -- which is `"PERFECT !"`, so the two strings are adjacent -- nine cells of
  `$4E` at `$594C..$5954`, **zero stray writes** in a poisoned row.  Glyphs and
  attributes both cover **columns 12..20 of character row 10**, measured as rows
  and columns rather than inferred from `$484C` and `$594C` looking alike.
  * **THE OFF-BY-ONE: FOUR CLAIMS, ONE PROPERTY, AND ONLY THE LAST IS RIGHT.**
    M7.30 wrote that it "belongs to the hand-coded sites" (from 2 of 3); M7.31's
    first pass said "1 of 3"; a verification pass said "4 of 6"; the phase's own
    enumeration says **5 of 7**.  Every wrong number came from a list I typed; the
    right one came from a scan over `CALL` **and** `JP` (`$A04B`/`$A08D` reach
    `$995A` by jump, which a `CD 5A 99` census cannot see).  And the assert I
    added -- *every site with an immediate `B` must be named* -- found `$9074` on
    its first run: the hurry-up banner's SECOND run on one strip, flashing the
    same ten cells from `$9068`'s border loop with the colour in the operand at
    `$9077`.  I wrote the TRAPS entry warning against this generalisation and then
    made it again inside the same increment; writing the lesson down did not
    protect me, the assert did (TRAPS #169).
  * **And no story survives the count.**  "Ten-character strings are exact, odd
    lengths carry a spare" dies on `$8E83`: eleven cells for the ten characters of
    "WELL DONE!".  Five of seven exact, nothing separating the two that are not.
  * **The `$802E` census is DATA now.**  "Nine references" was a constant in a
    check label, typed by the hand that got the count wrong in M7.29.
    `phase_802e_refs` measures it: eight `CALL` plus ONE `JP` (`$8EA7`), so a
    `CD 2E 80` scan alone finds eight of nine.  SIX draw on a path the port runs,
    ONE is transliterated but uncalled (`$9758`), TWO are untouched.
  * **THE ORACLE ALREADY EXISTED AND I NEARLY WROTE OVER IT.**  I had composed a
    new `tools/gameover.py` when a shell heredoc failed on a quote; `ls` then
    showed B1's 18 KB oracle for the same routine already there, already measuring
    the countdown, the writers and the reset -- and I had spent three subagents on
    questions it answers.  A broken heredoc is what saved it.  The three new
    phases went in BESIDE `phase_screen` (TRAPS #170).
  * **`phase_screen`'s 51 is not 72, and my first explanation was also wrong.**
    Not a stale snapshot -- `frames()` stops AT `$8CDC` with nothing drawn.  Of the
    72 writes, 24 are `$00` and **21 land on a byte already `$00`**: there is no
    CLS, the banner draws onto the live play field, and 51 is a fact about
    `round1_48`'s wallpaper.  Both numbers are in the fixture and a row asserts the
    inequality (TRAPS #172).
  * **TWO SURVIVORS WERE GATED, NOT WITHDRAWN.**  `attrRun(_, _, $4E)` is
    indistinguishable from `$0E` in the bytes (`$995A` ORs `$40`; `$4E` already has
    bit 6) and the paint order is unobservable (the runs are disjoint).  Both are
    real behaviour -- the instruction is `LD A,14`, and `$8CEE` precedes `$8CF8` --
    so a spy on the ARGUMENT and the ORDER kills them, verified by hand before the
    battery saw it.  That let the three dead B1 anchors be superseded with named
    live replacements instead of retired for convenience.
  * **`bannerGlyphs` meant two things.**  GLYPHS DRAWN at `$8EA7`/`$98C4` (+10),
    FRAMES OWED here (+1).  One name, two units.  Nine drawn, nine counted
    (TRAPS #171).
  * **Font: G, M, V**, drawn against the ROM's cells after READING them -- 5, 6
    and 6 of eight bytes differ -- and `make_banner.py` gained an assert nothing
    had: **no two inked glyphs may be the same eight bytes**, which the ROM-diff
    assert cannot see and which O/0 and V/W are most at risk of.  31 codes, and
    the string renders legibly.
  * Three docstring claims in `gameover.py` corrected: "48 of 48" against its own
    fixture's 48-of-49 with `afterctrl48` as the counter-example; `title` called a
    128K capture when it is **pre-`$9690`** (unpatched, `($FFE3)` = `$38`); and
    `$8CE2`'s `CALL $8E0A` called "nothing" when it is 27 T and two stack writes.
    `$969A`'s three straight-line `LD ($8DC4)/($8E05)/($8E0A),$C9` stores past one
    `JR z` are a better proof than any census that **the 48K game-over screen is
    silent**.  A dead write log in `phase_screen` removed (`harness.Mem` has `log`,
    not `writes`, so it collected `[]` for ever).
  Mutation battery: 25 M7.31 cases, all killed. The TWO that survived the first run were GATED rather than withdrawn -- a spy on `attrRun`'s ARGUMENT and on the call ORDER, mutation-tested by hand before the battery saw it -- and the THREE dead B1 anchors were retired with their live replacements named and verified. Full run **2,065 cases, 2,060 killed, ZERO survivors, ZERO dead anchors**, 5 named TIMEOUTs (the three long-standing ones plus M7.26's two unbounded printer loops), 17.1 minutes on 30 workers.  bb.test 1,195 -> 1,199.

- [ ] **NEXT: `$7FE9`/`$7FEF`, the HUD's two rows -- AND THE READ-FIRST PASS
  ALREADY LANDED, AGAINST MY HYPOTHESIS.**  I expected `$85C1` to be a buffer the
  HUD fills.  It is a **59-byte STATIC TEMPLATE carried in the tape image**
  (`$85C1..$85FB`: `'    1UP    HIGH SCORE    2UP'` + NUL, then
  `'      00   000200000       00'` + NUL), and **only `$85E9..$85F0` is ever
  written** -- by `$7FC0`'s RRD/RLD conversion of the four BCD record bytes, which
  the port already implements as `BB_HUDF`.  Measured: zero writes to
  `$85C1..$85FB` over 17,400 driven frames, and the one natural path that reaches
  `$7FC0` (holding `2` to join) writes eight bytes at `$7FCC`/`$7FD0` and nothing
  else.  So this is a SETTLED-ANSWER increment, not an unknown-behaviour one:
  * the enclosing routine is `$7FC0..$801C`; the port already does the RRD half
    and `$7FFC`, so **the missing middle is `$7FE2..$7FFB`**;
  * destinations `$4000` (28 cells, cols 0..27) and `$4020` (29 cells, cols
    0..28), IX carried past the first NUL to `$85DE` -- 224 + 232 = **456**
    glyph-row writes;
  * **ONE new glyph: `'S'` (`$53`).**  The font jumps `0x52 'R'` -> `0x54 'T'`;
    every other code the two strings need is already drawn;
  * the SCORE DIGITS bypass the buffer entirely -- `$816B` takes its destination
    from the table at `$85FC` (`$402B` HIGH / `$401F` P1 / `$4034` P2) and blits
    straight to screen, with leading-zero suppression by the self-modified byte
    `$81BB` (`$C8` RET Z -> `$00` NOP on the first non-zero digit).  P1's most
    significant digit is at `$401F`, **row 0 column 31**, outside the 28 cells the
    row-0 string covers, so nothing in `$7FC0` erases it;
  * TWO things the read did NOT settle, carried forward rather than assumed:
    whether the trailing literal `'0'` at cols 7/19/28 means the record is
    score/10, and whether `$401F` is reachable in real play (it needs a record
    >= `10 00 00 00` BCD and no driven run produced one).

- [x] **2026-09-25, M7.32 -- `$7FAF`: the round number was drawing SEVEN ZEROS PER
  DIGIT, and the fix uncovered a second fault underneath it.**
  * **FAULT ONE, the one the census found.**  `BB_DIGITS[digit * 8 + i + 1]` on a
    table of ten EIGHT-ELEMENT ARRAYS is an inner Array for 0..9 and `undefined`
    above; a `Uint8Array` store coerces both to **0** without throwing.  Every
    round-number digit drew seven zero bytes while `roundDigits` reported a faithful
    call count, faithful `$9A0E`/`$9A0F` ASCII and faithful `$F840`/`$F841` colour
    writes.  `scoreGlyph` indexes the same font correctly -- **one font, two
    consumers, two beliefs about its dimensions**, and the disagreement was
    invisible because the wrong one was wrong for every input.
  * **WHY NOTHING SAW IT, which is the real content of this increment.**  The
    fixtures record destinations and source ADDRESSES and no ROM bytes -- correct,
    since no ROM is shipped -- and that became **"no value is ever compared"**,
    including the bytes of the port's OWN substitute font, which are the port's data
    and were in the built page all along.  The nearest row diffs the engine with
    digits against the same engine without and requires the changed set to be a
    non-empty SUBSET of the machine's glyph addresses: **all-zeros is a valid
    subset.**  Its label even states "the engine differs from the machine on SIX
    bytes", a number its predicate never reads (TRAPS #173).
  * **FAULT TWO, found by the diagnostic I added with the fix, on its first run.**
    `digitGlyph: no cell for digit 12`.  The port's signature took a DECIMAL DIGIT;
    the machine takes a CODE -- `$8042` does `ADD A,$30` and `$8044` indexes the
    charset with the result, and `$7F86`'s divide leaves `tens` as high as 25 for a
    byte round counter, so round 128 draws `'<'` and round 255 `'I'`.  `$9877`'s
    settle-window oracle sweeps twelve round values and one is in that range, so the
    suite had been DRIVING the broken domain all along.  A lookup that is wrong for
    every input cannot show you its DOMAIN is wrong too (TRAPS #174).  The model now
    computes the code, keeps cells for `'0'..'9'`, and COUNTS anything else as a
    declared gap -- never a silent zero.  `$7FBA`'s colour write stays outside that
    branch because the machine runs it on every call.  **No gap in play**: rounds
    1..80 give tens 0..8, verified over all eighty.
  * **AND THE MEASUREMENT PASS CORRECTED MY OWN COMMENT: there are TWO independent
    `+1`s and I credited the wrong one.**  `$7FAF INC HL` steps the SOURCE past
    glyph row 0 -- measured as `(HL - $3C00) mod 8 == 0` at every entry -- and that
    is the `i + 1` and the reason the loop is `LD B,7`.  `$7FB1 INC H` steps the
    DESTINATION page.  Both are `+1`, so the arithmetic lands either way and a later
    fix reasoning from my comment would have put the offset on the wrong operand.
  * **The colour claim was missing a case**: 0/1, 0/1, 1/2 and **0/0** for rounds 1,
    2, 11 and 81 -- round 81 returns in three instructions and writes nothing
    anywhere, not even a stack push.  And over a whole `$7F1B` those two addresses
    have FOUR other writers (`$8302`, `$8306`, `$8385`, `$8387`), one each on every
    round including 81, so the gate is scoped to `$7F80` alone.
  * **`changed.length` IS NOT A WRITE COUNT**, and a row now says so rather than
    leaving the coincidence to luck.  Measured: a SECOND call changes ZERO of its
    seven bytes; over a whole `$7F1B`, where `$7F80` runs three times, round 1 makes
    21 writes and ends with 6 changed; over a ZEROED shadow it is 7 writes and 6
    changed, because **row 7 is the only value-preserving store** -- the union of
    no-op row indices over all ten codes is exactly `{7}`, every cell's row 7 being
    blank.  The value row may compare against `changed` only because it drives ONE
    call over a POISONED shadow, which is the one setup where they coincide.
  * **SIX new rows, all value-based**: the bytes at every measured address computed
    from the port's own `BB_DIGITS`; the `+1` stated against digits whose head and
    tail differ, so a missing offset cannot pass; the DOMAIN with its counted gap;
    the SHAPE, driving both consumers so one font cannot have two dimensions again;
    the colour writes; and the diff-versus-write-count premise.
  * **AND THE SWEEP RAN, WHICH WAS THE OTHER HALF OF THIS INCREMENT.**  A
    five-printer audit classified every check observing a printer's output as (A)
    exact values against the port's own font, (B) destinations only, (C) a
    subset/count relation, (D) a spy, or (E) nothing.  It found a LIVE INSTANCE OF
    THE SAME FAULT ONE BUFFER OVER, and three more holes, all closed here:
    * **`extendGlyph`'s SHADOW half was (B).**  `$95A7` writes every byte twice --
      `ram[hl] = v; ram[sh] = v;` -- and only the display copy was compared against
      `BB_LETTERS`.  A mutation putting the right byte on screen and `$00` in the
      shadow passed.  No live bug (both take the same `v`) but the gate could not
      have told.
    * **`BB_DIGITS` HAD NO GATE AT ALL.**  `build/digits.json` had existed since 16
      September, byte-identical to the engine's table, **unregistered in
      `port.json`**, read by nothing.  And `make_digits.py`'s assert was
      `rom[d] == DIGITS[d]` -- whole-cell inequality, which the ROM glyph with one
      byte changed satisfies (TRAPS #155, which `make_banner.py` was fixed for and
      this tool was not).  Now registered, compared cell for cell, and a MINIMUM of
      3 with per-glyph counts: 62 of 80 differ, closest digits 6 and 8 at 5 of 8, so
      all ten already cleared it.  Plus a duplicate-cell assert.
    * **The row built to catch unread fixtures could not see an UNREGISTERED one**,
      because it iterates `port.json`.  A guard over the register cannot find what is
      absent from the register (TRAPS #175).  Replaced with a DIRECTORY guard --
      eight intermediates, each with a producing tool or a suite reference, and
      **fourteen orphans that no tool writes and no check reads**, derived by
      scanning `tools/` for each filename rather than by my judging which looked
      disposable.  Shown to WORK with a phantom, in-suite and on disk.
    * **`BB_LETTERS[0]` and `[3]` are the same eight bytes, and that is FAITHFUL** --
      `$95D5` names the same charset cell twice.  Nothing asserted it, so the font's
      two consumers agreed by coincidence: `bankGlyph` indexes with `indexOf`, which
      can therefore never return 3, while `extendGlyph` reaches `[3]` by position.
    * **And one reason the whole-image differentials could not have caught `$7FAF`:**
      `roundbuild`'s `sequence.mask` is exactly the sixteen glyph addresses and
      nothing else, so the whole-shadow and whole-64K diffs were structurally blind,
      and the CRC anchor compares a capture taken at `$7F7D` -- upstream of the
      fall-through into `$7F80`.
  * **FOUR HOLES LEFT OPEN AND NAMED** rather than left to be rediscovered:
    `scoreHud` (`$816B`) is (B)/(D) -- its only driver stubs the blitter with a body
    of `void digit` and a comment saying *the renderer's ADDRESSES -- never its
    pixels*; `treasurePerfect` is (C); `bannerRow` (`$98C4`/`$98D4`) is (D), one of
    its rows admitting *the DISPLAY row goes somewhere this check does not look*; and
    `extendBanner` is (C) except for the `$9AB3` digit cell.  Each needs a row that
    computes the expected byte from the font and compares it at a measured address.
  * Well covered (A), for contrast: `bannerPrint` at ten sites, `bannerCellSingle`
    and `bannerCellDouble`, `bannerDouble` at five, `hurryGlyphs`, `gameOverBanner`,
    `bossBanner`/`bossDeath`, `creditLine`, `elementBank`/`bankGlyph`.
  * **AND AN ADVERSARIAL HUNT FOR MORE OF THE SAME COERCION CLASS CAME BACK CLEAN ON
    REACHABILITY**, which is the result I wanted and the one I would not have trusted
    from reading.  Method: all 64 `BB_*` tables deep-proxied for fractional, negative,
    past-end and absent reads; every `Uint8Array` proxied for non-number stores; driven
    through 1,500 frames, rounds 1..81 through the build routines, `roundDigits` over
    all 256 values of `($8609)`, eight banner strings by five destinations,
    `extendPass` over 256 masks, `elementBank` over 256 classes, `enemyHandler` over
    all eight types, and all 311 prototype methods over ~100 real-vocabulary tuples --
    22,557 calls.  **No reachable instance of the `$7FAF` fault survives.**  Also clean:
    all eight banner strings fully covered by the 31-cell font with zero
    `bannerMissing`; every `reset()` seeding bound matches its table length; no dangling
    `this.` field of 122 read; the T-state cost model cannot go `NaN` over 3,000 frames
    (which would freeze the frame budget silently); AY and beeper fuzz produced no
    non-finite sample.
  * **AND IT CORRECTED A DOC I HAD NOT FIXED.**  I corrected the two-`+1` attribution in
    `web/game.js` and **`docs/SPEC.md` still credited only `$7FB1` in two places -- one
    of them the entry I wrote earlier in this same increment.**  SPEC.md is what someone
    reads before deleting a `+1`, so a wrong attribution there is worse than in a
    comment.  Both fixed, with `$7FAF INC HL` and `$7FB0 EX DE,HL` written into the
    listing so the two operands cannot be confused again.

- [x] **2026-09-25, M7.33 -- `$AD65`, the jump arc: a REACHABLE divergence on four
  phases, and two bottom wraps that are not the same wraps.**  The read-first pass was
  aimed at `playerJumpFall`'s `BB_ARC[-1]` at phase 0 -- a latent fault -- and found
  something better on the way: a condition the port had **paraphrased** rather than
  transliterated.
  * **THE DESCENT PROBE IS GATED ON THE NEW PHASE, NOT ON THE SIGN OF THE DELTA.**  The
    port tested `dy > 0`, first true at phase 19.  `$AD7D CP $10 / JR nc` tests A, and
    `$AD6D INC A` has already made A the NEW phase and `$AD74` has already STORED it --
    so the machine probes from **old phase >= 15**.  Phases **15, 16, 17, 18** are
    exactly the arc table's ZERO-DELTA entries, so the port skipped the probe on four
    phases the machine takes it on.  **REACHABLE**: any short hop whose apex has floor
    16 px below.  MEASURED with floor on the probe row against a cleared control on two
    48K captures -- `newphase>=16` predicts every row and `dy>0` gets four wrong
    (TRAPS #178).
  * **What made it invisible**: the divergence needs TWO conditions at once, a phase in
    15..18 AND floor on the probe row, and no shipped world or existing gate placed
    both.  Green because untested, not because right -- the same shape as M7.32.  And
    the corroboration was in the image all along: `($ADA1) = $B58B` is the
    self-modified arc pointer left by the last descent probe the real machine ran,
    index 14, **phase 15**.
  * **TWO BOTTOM WRAPS, AND THEY ARE NOT THE SAME WRAP.**  `$AD88 CP $C0` on the plain
    step lands on **0**; `$AD5D CP $BF` in the free-fall tail lands on **2**.  Measured
    first wraps: plain from Y `$BE`, free-fall from Y `$BD` -- different thresholds AND
    different landings, so there is even a one-pixel band where they disagree about
    whether to wrap at all.  The port used `(y + dy) & 0xFF` for both, and one mask
    cannot express two wraps (TRAPS #179).  `playerFloorTick` shares the second tail,
    whose own comment had flagged it as unmodelled since it was written, and carries it
    now.
  * **PHASE 0: unreachable, and the port refuses it instead of teleporting.**  `$ACF7
    JP nz,$AD65` IS `playerPhysics`'s `if (phase !== 0)`; `$AD65` has ONE reference in
    64K; a sweep of 3,055 breaks at the indexing instruction across ten 48K captures saw
    every phase 1..32 and never 0.  But the port computed `BB_ARC[-1]` = `undefined` and
    `(y + undefined) & 0xFF` = 0, moving the player to Y=0 silently.  **The machine has
    no negative index**: `$AD6C DEC L` decrements L alone and `$AD77 LD H,0` forces the
    high byte, so phase 0 is an UNSIGNED 255 landing on **`$B67C`** = `$FD` = **-3** --
    not `$B57C`, the byte before the table, which was my premise and was wrong.  141
    pixels apart, and `$B67C` is the `$FD` prefix of `INC (IY+4)`, so the machine's
    phase-0 delta is determinate by accident of an opcode.
  * **The index is ONE FLAT UNSIGNED BYTE**, verified flat for phases 1..32 and for 33
    and 40.  The port's two arrays and `(idx - 24) & 7` became one 32-entry table: the
    mask was a no-op over the reachable domain and wrong above it, and `$AD6E CP $21`
    clamps 33 to `$FF` before the store -- the same dead guard M7.32 deleted
    (TRAPS #177).
  * **And a port comment was mis-attributed**: the `BB_ARC` block described the TONE
    read at `$8FC5` (indexed by PHASE) and called it the ARC read at `$AD7C` (indexed
    by PHASE-1).  The code was right in both places.
  * **A new oracle, `tools/jumparc.py`** -- and `ls tools/` first, per TRAPS #170:
    `tools/jumpsfx.py` is `$8FA5`'s TONE, `tools/walker.py` is the ENEMY arcs, and
    `build/jump_fixture.json` has no producing tool and records no phase.  Nothing drove
    the mover.  Its own first draft read **DE where it meant HL** (H is 6, L is 7) and
    reported the table base for every phase; the measurement's own inconsistency caught
    it -- a -3 delta against a base holding -4 (TRAPS #151).
  * **And the gate block was INERT on its first run**: appended after `rig.done()`, so
    four checks were added and the count did not move.  The count is the tell, and the
    standing rule is that everything-green on a first run is a warning.
  * **THEN THE BATTERY FOUND FOUR SURVIVORS AND EVERY ONE WAS A REAL HOLE.**  Chasing
    the three that were `playerFloorTick`'s uncovered something larger than the wrap I
    had gone in for: **`$AD18` does TWO probes, not one.**  `$AD35` probes the FEET row
    (Y+15) with `C := $20` and `$AE9C` PATCHED TO RET -- a solid result means the sprite
    is inside the floor and goes to FREE-FALL -- and only then does `$AD45 INC D` probe
    the row BELOW with `$AE7F`'s `$3F`, where solid LANDS.  The port modelled one probe
    and landed wherever the row below was solid regardless of the feet.
    MEASURED at `$AD18`'s own entry over three worlds (solid below, solid BOTH, neither):
    it lands only on clear-feet-and-solid-below, at Y `$60`, `$68`, `$B8`, `$C0` -- and
    every one of those is a Y where `(Y & $FE) + 15` ENDS a character cell.  The two
    probes read different cells only then, so **the machine lands only on an eight-pixel
    boundary and nothing checks for it**; it falls out of the arithmetic.
  * **AND THE MASK I HAD WRITTEN OFF AS COSMETIC IS THE SWITCH ON A BOUNCE.**  After the
    probe decides a cell is solid it runs `$AE9C AND $20`: solid under `$20` returns at
    `$AEA0`, but a cell solid ONLY in bits 0..4 -- the walker's claim/release bits --
    falls through to `$AEA1 BIT 1,(IY+8)`, and `$AEA7 LD (IY+9),1 / POP HL / RET` **sets
    the jump phase and unwinds past the caller**.  With `C = $20` that is unreachable;
    with `$3F` it is not.  That is why the floor tick patches `$AE9C` for the feet probe
    and restores it for the row below: to choose which probe may bounce.  The
    equivalence measurement I had relied on was TRUE -- re-measured, ten shadows, zero
    cells with a low bit set -- and the conclusion drawn from it was wrong (TRAPS #180).
  * **THREE MASK MUTATIONS ARE WITHDRAWN, NOT GATED**, because the world that
    distinguishes `$3F` from `$20` is exactly the world that reaches the unmodelled
    bounce; gating them against a half-modelled world would assert something false.  The
    bounce is M7.34's.
  * **AND THE LAST SURVIVOR WAS GATED AT THE ROUTINE'S OWN ENTRY RATHER THAN WITHDRAWN.**
    `$AE92`'s `AND 6` versus `AND 7` differ only at X = 1 mod 8, and the movers cannot
    produce an odd X -- `$ADAA` driven over all 256 X by four direction bytes, 1,024
    runs, parity PRESERVED, zero even-to-odd, and the player starts at 24.  No caller can
    express it.  But `$AE7F` has its own entry and its own register contract, so it is
    driven directly over all 256 X with floor in the third cell only: solid for 192, and
    the measured result follows `AND 6` at every one (TRAPS #181).
  Mutation battery: 28 M7.33 cases across two batches, every one hand-verified before the battery saw it -- including the original `dy > 0` gate, the only case that means anything since the suite was green WITH it. THREE MASK CASES WITHDRAWN with a re-measured reason (ten shadows, ZERO cells with a low bit set, and the distinguishing world is the unmodelled bounce). The FIVE survivors across three runs were ALL REAL HOLES, not equivalents: four closed with new rows and the fifth gated at \'s own entry. Final run **2,114 cases, 2,109 KILLED, ZERO survivors, ZERO dead anchors**, 5 named TIMEOUTs, 17.5 minutes on 30 workers.  bb.test 1,208 -> 1,216.

- [x] **2026-09-25, M7.34 -- the three SILENT FALLBACKS, and the printer whose values
  nothing read.**  All three fallbacks were instances of a rule M7.32 itself wrote
  (TRAPS #174: a fallback is an answer to a question you have then stopped asking), and
  all three were unreachable -- so each is now COUNTED or REFUSED with its
  unreachability DRIVEN rather than asserted.
  * **`extendGlyph`'s was the worst**, and it is the only division inside an index in the
    engine: `BB_LETTERS[(iy - $95D5) / 5]` is FRACTIONAL for any `iy` off the stride-5
    grid, and a fractional index is `undefined`, so the loop fell through to `ram[de]` --
    a charset source this port leaves ZERO -- writing **eight zeros to the display AND
    the shadow** with nothing recording it.  `sub` has three distinct states now and the
    gap is counted.  Unreachability driven over all 256 masks and both offsets, 1,536
    glyph calls, counter at zero.
  * **`scoreGlyph`'s `|| BB_DIGITS[0]`** made one font answer "a cell I do not have" two
    different ways, since M7.32 gave `digitGlyph` a counted gap and left this one.  Both
    count now.  Unreachability proved over the WHOLE input space: `bcdAdd` matches a
    reference `ADD`+`DAA` on all 131,072 triples with BCD-in implying BCD-out.
  * **`driftDelta`** read a five-pair table at an odd index and returned `[0, undefined]`
    -- the `$7FAF` failure mode.  It throws.
  * **AND THE PRINTER AUDIT CORRECTED THE PLAN, which is why it ran.**  Three of the four
    value-blind printers were already PARTLY value-checked, so new gates would have
    duplicated; what was wrong was the LEVEL.  `treasurePerfect`, `bannerRow` and
    `extendBanner` each had a row computing the expected byte from the port's own font --
    driving `bannerPrint` or `bannerDouble` DIRECTLY, with the routine under test tied to
    those addresses only by a SPY on its argument.  Traces compared write for write and
    were identical, so they are re-driven from the real entry points and **no new fixture
    was needed**.
  * **`scoreHud` (`$816B`) WAS the real hole.**  Its fixture recorded
    `sorted(set(addresses))` plus a ROM-derived checksum no check reads -- order,
    repeats and which digit all discarded -- and the gate replaced the blitter with a
    body of `void digit`.  A CHARACTER CODE and a ROW INDEX are not ROM bytes, so
    `tools/scoreaward.py` records them in order now and the row drives `scoreHud`
    UNSTUBBED over eleven records, all three fields, both suppressor states, comparing
    every byte against the port's own `BB_DIGITS`.
  * **`$81BB` IS AN OPCODE BYTE and the port carried it as a JS boolean** --
    behaviourally equivalent, since `$8183` re-arms unconditionally, and inconsistent
    with every other self-modified operand here.  What a local hid is the WRITE CENSUS:
    `$81BD`'s store is unconditional past the `RET z`, so the machine disarms ONCE PER
    DRAWN DIGIT -- eight times for an eight-digit score -- where a boolean writes it
    never.  It lives in the byte image now.
  * **`bannerRow` HAS NO BRACKET ON `($803C)`**, which nothing asserted.  With `$8058` in
    it the same pass makes **320** glyph writes instead of 160 and LEAVES the operand
    behind -- so the round banner is single-height only because whatever ran before it put
    `$804F` back.  Asserted now.
  * **`extendBanner`'s digit is BIT 0 of `(IX+$5A)`**, not which entity `IX` points at:
    P1's slot with bit 0 set draws '2'.  A gate that varies `IX` proves nothing.
  * **`extendGlyph`'s SUBSTITUTION BOUNDARY is an assertion now**, which house rule 5
    requires and it was not: two battery survivors showed that moving the threshold to
    `$8000` and deleting the test both passed, because all six table sources are charset
    addresses.  The table is DATA, so the row pokes a source into the display file and
    requires the FAITHFUL path.
  * **SEVEN DEAD ANCHORS re-anchored** (four M7.32's, three H9's) after the `extendGlyph`
    restructure -- never withdrawn for an anchor moving.
  * And two of my own errors worth the record: a range guard added with the fix was
    provably dead -- `BB_LETTERS[k]` already returns `undefined` for every index it
    rejected -- **the second such guard in three increments**, so TRAPS #177 gained a
    second instance rather than a new entry.  And the gap row was wrong TWICE: it swept a
    fixed region when the write address is computed from data, and then compared against a
    zeroed target where "wrote zeros" and "wrote nothing" are the same observation
    (TRAPS #182).  One mutation of mine also **mutated nothing** -- an unused variable
    that left the IX chain intact -- which is the third kind of survivor and the easiest
    to mistake for a gap.
  Mutation battery: 35 M7.34 cases across two batches, every one hand-verified before the battery saw it. ONE withdrawn because it MUTATED NOTHING (an unused variable that left the IX chain intact -- the third kind of survivor). ELEVEN dead anchors re-anchored across three runs, never withdrawn: seven from the `extendGlyph` restructure and four from `$81BB` leaving the boolean. Final run **2,149 cases, 2,144 KILLED, ZERO survivors, ZERO dead anchors**, 5 named TIMEOUTs, 17.8 minutes on 30 workers.  bb.test 1,216 -> 1,228.

- [x] **2026-09-25, M7.35 -- THE BUBBLE-JUMP: the floor probe stops being a
  predicate.**  M7.33 found `$AEA7`, measured `$3F` and `$20` as identical over ten
  shipped colour shadows, withdrew three mask mutations and said to restore them when
  the bounce landed.  M7.34's recon landed it -- **21 hits over 67,540 measured video
  frames from key scripts alone, nothing poked** -- and this models it.
  * **FOUR OUTCOMES WHERE THERE WAS A BOOLEAN.**  `solidRow` is gone; `probeCell`
    returns WHICH CELL was solid (the tail needs the value to tell a wall from a
    bubble) and `floorProbe` returns `clear` / `floor` / `bounce` / `popped`.  Wired at
    all three sites -- `$AD37` (feet, mask `$20`, tail PATCHED OUT by `$AD30`), `$AD46`
    (the row below, `$3F`) and `$AD9D` (the arc's descent probe, `$3F`).
  * **`$AEB9 LD E,A` is one instruction and it is the whole of "a bubble is not
    floor"**: it clobbers the solid result, so a player who pops a bubble falls THROUGH
    what it just stamped.  The bounce instead sets phase 1 and aborts the mover with Y
    UNMOVED -- `$AEAB`'s `POP HL` discards the inner resume point, and phase 1's delta
    arrives next frame.  Measured from BOTH entries with one input changing per row.
  * **`bubbleProbePop` is the exact inverse of `$B8C0`'s claim**: `12 - tag`, `x10`
    **EIGHT-BIT**, from `$FEDF`.  Driven for every tag 0..15 with HL read from the
    register file -- and the port is driven at the out-of-range tags too, poisoning both
    the address the eight-bit arithmetic reaches and the one a sixteen-bit multiply
    would.  Nothing writes a tag >= 13 today, so it is transliterated and COUNTED rather
    than guarded: a guard would be a departure, and `$AEC0`'s `BIT 7` is what protects
    the pool.
  * **THE ASYMMETRY IS ASSERTED, NOT FIXED.**  `$AEA7` checks nothing about the bubble;
    only `$AEAD` checks `BIT 7`.  A row drives a DEAD slot both ways -- the bounce fires
    anyway, the pop refuses and counts it -- because a port that validated on the bounce
    path would be MORE correct than the machine and would diverge.
  * **M7.33's THREE MASK MUTATIONS ARE RESTORED**, exactly as their withdrawal note
    said, and all three are killed by the new rows.
  * **AND THE BATTERY FOUND A BIT I COULD NOT HAVE DISTINGUISHED.**  `(IY+8)` bit 1 is
    the jump key held THIS frame, bit 5 the same key LAST frame.  A captured "jump held"
    byte is `$22` and carries BOTH, so my gate -- built from captures -- could not tell
    a bit-1 test from a bit-5 one, and a mutation testing bit 5 survived a full run.
    The rows drive `$02` (the first frame of a press: bounces) and `$20` (the frame
    after release: pops instead), which is where the two part company.  A capture is a
    steady state; the interesting frames are transitions (TRAPS #188).
  * **THREE FAILURES IN MY OWN TOOLING, all found here:**
    * **the battery has been decoding the suite with the console's codepage all along.**
      A label containing `U+201D` -- whose UTF-8 third byte is undefined in cp1252 --
      killed every worker in its reader thread, and thirty of them "finished in 0.2
      minutes" having run nothing.  **The tell was the CLOCK, not the traceback.**  Both
      call sites pin UTF-8 now, and the run has a WALL-CLOCK FLOOR.  Two scratch
      harnesses had the identical bug and reported nine cases as SURVIVORS when they
      could not read the output (TRAPS #185).
    * **my re-anchor helper silently DELETED two mutation cases.**  Locating a case by
      label and replacing `rindex('    (')` .. `index('),')` walks back past a
      COMMENTED-OUT case into the live one in front of it.  The anchor checker could not
      see it -- a deleted case has no anchor to be dead -- and the arithmetic caught it:
      2,149 + 3 restored - 2 eaten = 2,150, where I had made +3.  Both restored by name
      (TRAPS #186).
    * **the cheap check existed all along and I had never written it.**  Walking the
      case list with `ast` and counting each anchor takes under a SECOND where the
      battery takes eighteen minutes -- and it catches AMBIGUOUS anchors, which the
      battery structurally cannot.  Written after the fourth increment in a row that
      produced dead anchors; it found ten candidates on its first run, four of them its
      own blind spot because it did not know `bb.test.js` is a valid target
      (TRAPS #187).
  Mutation battery: 18 M7.35 cases plus M7.33's THREE mask cases restored, all hand-verified. TWO cases my own re-anchor script had DELETED were found by arithmetic and restored. A new anchor checker (under a second against the battery's eighteen minutes) reports DEAD and AMBIGUOUS anchors and a COUNT INVARIANT. Final run **2,170 cases, 2,165 KILLED, ZERO survivors, ZERO dead anchors**, 5 named TIMEOUTs, 17.7 minutes on 30 workers.  bb.test 1,228 -> 1,234.

- [x] **M7.36 -- `$7FE2..$7FFB`, the HUD's two text rows; `$7FC0`'s FALL-THROUGH; and
  FOUR DIAGNOSTIC BOUNDS, each from a measurement that was not the obvious one
  (2026-09-25).**
  `$7FE2` is the missing middle of `$7FC0`: the port had the RRD score conversion and had
  named this half as the front end's work.  MEASURED by `tools/hudfurniture.py`'s new
  `text_rows` phase -- 28 characters at `$4000` in 224 writes over columns 0..27, and 29
  at `$4020` in 232 over 0..28, **456 glyph bytes across pages `$40..$47`** on an
  eight-bit `INC H`, plus **64 panel bytes counted separately** because `$81C0` is
  `JP $804F` and blits through the same store site.  `$80FA` is called with `A = 1` then
  `A = 2`.
  **THE SECOND ROW'S POINTER IS NOT LOADED** -- `$7FEC` sets `HL` alone and `$802E`'s own
  `INC IX` has carried `IX` past the NUL at `$85DD`, so a caller scan finds one string
  where there are two.  **`$85C1..$85FB` is ONE 59-BYTE STATIC TEMPLATE from the tape,
  not a buffer**: zero writes over 17,400 driven frames, and the only bytes ever written
  inside it are `$85E9..$85F0`, by `$7FC0`'s own RRD conversion.  One new glyph, `'S'`
  (5 of 8 bytes differ from the ROM cell it replaces); `BB_BANNER_FONT` is now 32 codes.
  **AND `$7FC0` FALLS INTO `$7FFC`, WHICH THE PORT SAID IT DID NOT.**  `$7FF9 CALL $80FA`
  returns to `$7FFC`, so both of `$7FC0`'s references repaint the attributes -- `CC C0 7F`
  at `$7F58` and `C3 C0 7F` at `$9998` -- and one of the two sites in the port was
  missing it.  The comment claimed `$7FFC` was "reached ONLY from `$8D22`'s `CALL z`";
  `$8D22` is the only site that CALLS it *by address*, which is a different claim.
  **`$802E` IS NOW COMPLETE**: all nine references transliterated -- eight drawing, one
  uncalled (`$9758`, the credit line the front end owns), **none untouched**.  The census
  row failed the moment `$7FE9`/`$7FEF` were wired, which is what it was written for.

  **The four bounds, and why each number is not the obvious one.**  All four are
  diagnostics: counted, named, thrown, above what the MACHINE can do.  Two agents
  measured them, neither reading the other's work.
  * `BB_BANNER_MAX = 32` -- `$802E`'s walk.  Longest of the ten declared strings is **29**
    (`$85DE`'s HUD row 1, which this increment added, so the number is current).
  * `BB_SPARK.MAX = 1024` -- `$C002`.  **Above 709, not above fourteen.**  Reachable
    states all take 14 (48 captures, 12 passes each), but `$C016`'s `LDI` is a second
    decrementer of the same `B`, so a slot with X bits `$00` wraps the DJNZ and the total
    becomes `(wraps+1) x <=256`: three regimes over 1500 randomised tables, 8..13 then
    216..269 then 452/502/709, the largest walking HL to `$6268`.  **A ceiling of 256
    would have named a faithful hazard as a bug.**  `tools/sparkle.py` now counts the
    loop top; harness, agent and engine all three say 14 and 431.
  * `BB_SCROLL.MAX = 256` -- `scrollIn`.  **The drift hang was never in the painter's
    walk.**  162 mutated machine runs all terminate (`target`, never `limit`), no cycle in
    the 256-state closure.  The hang is `$7F41`'s and it is FAITHFUL: the corrupt fill
    walks `IX` over `$FB00..$FFFF`, which holds `BB_SCROLL.ROW_TAB`, and the copier then
    writes over `$8604` -- `scrollIn`'s own counter -- caught going `0 -> 196 -> 128 -> 0
    -> 255` over 14,969 steps.  256 is **provable**: `($8604)` is one byte.  Measured
    faithful cost 26 steps.
  * `BB_PAINT.BUDGET = 2048` -- was **200,000, which is 183x the measurement** of 1090
    cells.  Both stride mutants ask ~66,180 and the cheapest mutated round over 1090 asks
    4316, so 2048 kills them inside the painter before `$FD04` is wrecked.
  The walk's own two guards are **dead code on every input the machine can produce**,
  including both mutants -- recorded rather than retuned.  `parallel.py` now reads the
  FAIL lines already on the pipe when a case times out (`TIMEOUT-KILLED`), because the
  drift mutant prints five FAILs before it hangs.

  **What this cost, and what caught it.**  Eight new TRAPS, #189..#196.  A poison sweep
  that overwrote its own terminators made the new bound fire on the faithful path, in a
  gate of mine (#189).  A join clause driven with no keyboard measured a routine that had
  already returned, because the keys are active low (#190).  The row titled "the pointer
  is NOT LOADED" could not tell loading from carrying, because `next` IS `$85DE` on the
  faithful path -- fixed by MOVING THE NUL to `$85CB`, which leaves `IX` on the `'H'` of
  HIGH (#191).  A malformed mutation left an orphaned `} while` and its 120-second
  TIMEOUT was the malformation, not a behaviour (#194); rewriting it produced two anchors
  matching five and nine lines apiece (#195).  A diagnostic counter named `scrollSteps`
  clobbered the existing `$840A` execution counter and the composition-trace row caught it
  on the first build.  And the fixture had carried `$C002`'s 431-iteration runaway since
  M7.7 as a pixel count nobody divided (#193).
  **One SURVIVOR, and it took two attempts.**  "The strings are seeded without their NUL"
  survived because `ram` is a zero-filled `Uint8Array`; the first fix poisoned the region
  and called `reset()`, which begins with `ram.fill(0)`, so the poison was gone before the
  seeding ran and it survived that too.  TRAPS #44 at two levels.  The seeding is now
  `seedBannerStrings()` and the gate drives it on a dirty world: both cases kill (1 and
  23 named failures), and the seed is testable on its own instead of only as a side
  effect of a sixty-line reset.

  Mutation battery: 42 new M7.36 cases plus R2's malformed case remade well-formed.
  Two full runs: the first **2,211 killed of 2,212 with one survivor**, then after the
  refactor that made that write observable, **2,213 cases and ALL 2,213 KILLED -- zero
  survivors, zero dead anchors, zero ambiguous anchors, and ZERO TIMEOUTS**, 16.3 minutes
  on 30 workers.  The five long-standing named timeouts (I10, R2, M7.8-C and M7.26's two
  printer loops) are all gone, each converted into a named kill by a measured bound rather
  than excused.  bb.test 1,234 -> **1,244**; kit 120/120.

- [x] **M7.37 -- THE FRONT END, READ FIRST (2026-09-26).**  A reading pass, no engine
  code.  Seven sub-blocks measured on the live Z80 by seven agents; each read
  adversarially verified by an eighth required to reach the same fact by a DIFFERENT
  ROUTE; then a completeness critic.  **155 findings, 137 load-bearing; 100 claims
  verified, 87 CONFIRMED and 13 REFUTED; 47 corrections to this repo's own docs.**
  Consolidated in `docs/M7.37-FRONTEND-READING.md`; detail in
  `scratchpad/recon/zzfe_*_report.md` (190 KB) and `zzfe_critic_report.md` (39 KB).
  * **THERE IS NO ATTRACT MODE AND NO DEMO.**  "$8CC7 the attract entry" is `CALL $95F3`,
    the cold-start setup.  Driven 16,749 frames (335 s) with no keys and 24 exits watched:
    not one fires, `$8D25` never entered, `$FD80..$FDF7` never changes a byte, no PC in
    `$4000..$7FFF` at all.  A whole sub-system the plan budgeted for does not exist.
  * **THERE ARE TWO FRONT ENDS.**  The cold-start one (`$F5BC..$8CD9`) runs ONCE and is
    then PHYSICALLY DESTROYED -- `$F5BC..$F9FF` sits inside the game's own shadows, 1,050
    of 1,092 bytes gone after 120 frames of play.  The per-game one is the TAIL OF `$96DF`,
    the routine the port ALREADY models as `gameReset()`, and `$96DF` is a clean CALL/RET
    pair so it can be a function call.
  * **THE `$F5D2` CONTRADICTION IS SETTLED AND SPEC WAS RIGHT.**  It is a 16-byte
    key-table staging buffer written through a cursor at `$F5E5`; its tape content is the
    easter egg "MUSIC BY TIM FOLLIN", which nothing ever prints (`LD IX,$F5D2` occurs zero
    times in 64K; not NUL-terminated).  Three states across 14 captures.  The missing word
    was REUSE, and SPEC never said HL is a LIVE PARAMETER.
  * **MY OWN BRIEFING WAS WRONG TWICE**, recorded rather than quietly fixed:
    `build/image_tape.bin` DOES hold the front end (1,195/1,280 non-zero, byte-identical to
    `title.pkl` at eight checked addresses) -- only `image.bin` is unusable (373/1,280); and
    `title.pkl` is NOT mid-redefine but parked in player 1's control-select menu read.
  * **FOUR BLOCKERS THE CRITIC CAUGHT IN THE READS** -- "the agents agreed" is not "the
    agents were right": the starfield attribute is `$00..$07` 128 each, not `$05`; the glyph
    requirement had five answers and none was the number (57 for the front end, 36 for the
    title, 26/17 missing); `$97EB` clears 6,912 to `$5AFF` not 6,911 to `$5AFE`; and the
    high score is BOTH 20,000 (stored) AND 200,000 (rendered, because `$85F1` is a fixed
    template `'0'`).
  * **THE DECLARED DEPARTURES ARE NOW ONE DESIGN, NOT SEVEN**, including the fact nobody
    had written down: **there are THREE printers** -- `$802E` (NUL-terminated),
    `$F863`/`$F887` (`$40`-terminated, CHARS-resolved, self-patched enable byte, own
    cursors) and the Firebird line (ROM channel 2 + `RST $10`, INK 8 / PAPER 8).  And
    `$F7B3` does NOT wait for an interrupt -- `$F7B8` is `RST $38` -- so LAST-K is a
    FUNCTION the port can write and test, not a background service.
  * I reproduced the five most load-bearing claims myself before committing
    (`scratchpad/recon/zzfe_my_check.py`): **5 of 5.**
  * Work order A..H, **the CLS first and the font FIFTH**: 89.6% of the title paint is
    glyph-free, and doing the font first makes the first increment the one that trips three
    polarity-flip assertions.  A..G need no new measurement.  **And the critic's "G-half"
    is already done**: `$97F8..$9861` -- the round advance, `$984B`'s nineteen-byte clear
    and `$9858..$9861`'s shadow wipe -- is already in the port as `roundAdvanceCore` /
    `shadowClear`.

- [x] **M7.38 -- `$97EB`, the title screen's CLS: 6,912 bytes, and the fill value comes
  from L (2026-09-26).**  Front-end increment A.
  MEASURED by `tools/gameover.py`'s new `phase_title_cls` (the tool that already owns
  `$96DF` -- TRAPS #170).  `BC=$1AFF` is 6,911 LDIR copies **plus** the `LD (HL),L` that
  seeds the first byte, so the range is `$4000..$5AFF` inclusive -- 6,912 bytes, contiguous,
  with `$5B00` left at the `$AA` poison.  Two of M7.37's sub-blocks disagreed about exactly
  this, and `$5AFF` is the credit line's ninth attribute cell, which `creditLine()`'s own
  gate asserts.
  **THE FILL VALUE IS L, NOT AN IMMEDIATE**, and it is DRIVEN rather than read off the
  opcode: patch `$97EC` and the value follows -- `L=$00 -> $00`, `$05 -> $05`, `$7E -> $7E`.
  **`$970F` IS A CALL**, so `$97EB` returns and `$96DF` continues -- which is why this is
  the first of a list.  `gameReset()` models `$96DF..$970B` then calls `playersInit()`
  (`$97C7`/`$97D2`), so the port **jumps from `$970B` to `$97C7` and skips 185 bytes**.
  `titleClear()` joins the frozen UNCALLED census as its NINETEENTH entry, for
  `creditLine()`'s exact reason one increment later in the same routine -- and the census
  failed the moment the method appeared, which is what it is for.
  **TWO TRAPS, both mine, both caught by driving:** #197, an LDIR fill overwrites its own
  seed cell (DE trails HL by L), so my probe of a TRUE claim returned the poison and looked
  like a refutation -- the witness is the first DESTINATION; and #198, TRAPS #191 recurring
  **in the session that wrote it**: with HL nailed to `$4000`, `ram[hl] = hl & 0xFF` and
  `ram[hl] = 0` are identical, so the row's headline could not fail and I had written a
  comment ADMITTING it.  Fixed #191's way -- `$97EB`'s three registers became parameters
  with its own operands as defaults, the gate reproduces the oracle's three patched runs,
  and `ram[hl] = 0` is a named kill.
  Corrections shipped with it: the credits store is `$970B` not `$9709` (three battery
  anchors re-anchored, count held), and `creditLine()`'s "roughly thirty glyphs" is now
  measured at 36 needed / 17 missing.
  Mutation battery: 12 new cases.  Two runs: the first had ONE TIMEOUT, my own malformed case (see TRAPS #199), and after replacing it **2,225 cases and ALL 2,225 KILLED -- zero survivors, zero dead anchors, zero ambiguous anchors, zero timeouts**, 16.3 min on 30 workers.  bb.test 1,244 -> **1,247**; kit 120/120.

- [x] **M7.40 -- INCREMENT G: `$8CC3` / `$95F3`, THE COLD START, WHOLE -- and a live bug in
  the shipped page (2026-09-26).**
  **THE PAGE SHOWED A HIGH SCORE OF ZERO.**  `BB_BANNER_STR` seeded HUD row 1 with the
  RENDERED default, but nothing wrote the record at `$FFE1..$FFE4`, so the first
  `hudScoreDigits()` converted zero and overwrote the template.  `$9690`/`$9692` seed
  `$FFE3 = 2`: 20,000 stored, 200,000 displayed -- the factor of ten is the ninth digit,
  `$85F1`, which `$7FC0` never writes.
  **`coldStart()` IS NOW THE WHOLE OF `$95F3..$96B2`, IN MACHINE ORDER**: BANKM to `$9AE7`; the
  `$9601` key copy DECLARED SKIPPED (HL is a live parameter and the control select that fills
  `$F5D2` is group 3 -- modelling it now would copy sixteen zeros over `$B5FD`, which type 4's
  arc reads as a signed Y delta); the SELF-OVERWRITE of `$95F3..$9602` as state; border black;
  the 18-byte and 256-byte (`B = 0`) clears; the 257-byte IM 2 fill and vector; four
  `rowTableBlock` calls building 64 words; `$967F`'s low-half `$01FF`; the record; the three
  RET patches unless `$80`; and `relocate()` at `$96A5`.  On `$80` it does all of that and then
  THROWS by name, because the `$96B3` 128K continuation is not modelled.
  **THREE SECOND SPELLINGS LEFT `reset()`**: the `$FC00` fill (it is the IM 2 vector table as
  well as the flyer's wrap-edge band), the 24-entry `BB_ROWTAB` seed, and the shadow half it
  DERIVED as `$FD04 + $A000` -- a second spelling of `$9662`'s own `ADD A,$A0`.  `relocate()`
  moved INSIDE the cold start, because `$95F5` reads BANKM before `$96A5` relocates over it and
  the port had them the other way round.
  **TWO TABLES THE PORT SHIPPED AS DATA ARE VALUES THE MACHINE COMPUTES** (TRAPS #205):
  `BB_ROWTAB` ("static tape data", measured from post-boot `image.bin`) and the HUD row-1
  template (measured from `round1_48` after `$7FC0` ran -- so every digit row passed with
  `hudScoreDigits` deleted).  Both now come from the machine's own arithmetic or the tape.
  **THE WORK, and what caught each mistake:**
  * Part 1's battery had ONE survivor -- a 12-vs-16 clear that `ram.fill(0)` hid.  The pre-
    mortem's `driven()` harness closed it by poisoning past the end (TRAPS #44).
  * The pre-mortem showed the suite calls `reset()` **77 times on one object**, so the
    "mandatory guard" I had written into the docs would have killed the file (TRAPS #206).
  * An existing `extendGlyph` row had BORROWED its precondition from bytes the cold start now
    writes, and silently switched branch (TRAPS #204).  It now constructs the case.
  * One of my own mutations did not express its bug: dropping a mask is equivalent in JS,
    because `Uint8Array` masks the store (TRAPS #203).  Hand-testing caught it pre-battery.
  * Part 2's battery had ONE survivor: the IM 2 fill's 257th write is DEAD in the end state
    (`$9641`, `$9662` and `$967F` all rewrite `$FD00`).
  * **A four-agent pre-commit review** found the ENGINE right -- the port's ordered write log
    equals the machine's at every index, 2,408 stores on the 48K leg and 2,405 on the 128K, and
    all 256 entry values of A partition identically -- and the GATE short three ways.  Its
    fixes shipped: a WRITE CENSUS row (the port's stores must be the machine's log minus the
    32 declared writes, which kills the dead-write survivor and five more); a row driving the
    GAME-OVER WRAP (a mutant cold-starting there erased the session high score and passed the
    whole suite); and a row reading the PRODUCTION call's products on a fresh load (every
    driven row saw only the second call).  Every number those rows need is measured into the
    fixture, and four values the phase had TYPED now come from its log.
  * And it DROVE a real second entry: it is not the first entry replayed.  `coldStart()`
    re-applying is still right -- every production call is a first entry -- but my text said
    it "is" the second entry, in six places including #206's own correction.  Struck and
    corrected; TRAPS #207.
  Mutation battery: 51 new cases, 13 re-anchored.  Three runs: part 1's had ONE survivor (the 12-vs-16 clear), part 2's had ONE (the IM 2 fill's dead 257th write); after the review's rows, **2,267 cases and ALL 2,267 KILLED -- zero survivors, zero dead anchors, zero ambiguous anchors, zero timeouts**, 16.9 min on 30 workers.  bb.test 1,244 -> **1,268**;
  kit 120/120.  TRAPS #203..#207.

- [x] **M7.41 -- FRONT-END GROUP 1: `$970F..$9764`, THE TITLE SCREEN'S PAINT, as one drive
  (2026-09-27).**
  **`titlePaint(phase)`** = `titleClear()` + `starfield()` + `titleText()` + `creditLine()`,
  UNWIRED until group 2.  The oracle is ONE drive (`phase_title_paint`, fixture key
  `title_paint`): `$970F -> $9729 -> $9765` on `title` with the RET patches, `$FEC4 = 0`, the
  PRNG at `$002A`, R pinned, the screen poisoned past `$5AFF`.
  **THE STARFIELD IS EXACT**: all 6,912 bytes at `$9729` and the 1,024 ordered stores, from the
  machine's phase.  `BB_Rng.stall(2)` models DEC C / JR nz's two M1s, so the walk is +53 out of
  dots 255/511/767 -- the port's flat +51 was wrong for 768 of 1,024 dots.  The mask constants
  at `$FEBD` were never seeded (a starfield would have been 1,024 black dots); slot 7 is read
  live from `$FEC4`.  **The phase is a parameter** and the default ARMS afresh: the pre-mortem
  found the walk was armed once per `reset()`, so every later title in a session would have
  drawn the same ink sequence (TRAPS #209).
  **THE FOUR TITLE STRINGS**: one IX chain, the `$9A85` column-major table, `$A090`-derived
  attribute addresses, and `attrRunDouble` for `$994F`, whose second row is NOT `hl + $20`.
  The attribute file at `$9765` is the machine's, all 768 cells, and the text's 1,328 display
  cells are exactly the machine's.  17 glyphs drawn (`: B` + fifteen lowercase), the `T`
  redrawn because it read as `I`.  `'ROUND    9'` -> the tape's `'ROUND    0'` (the seed came
  from extcomp).  `attrRun` treats B = 0 as 256, as DJNZ does.
  **WHAT CAUGHT WHAT.**  The pre-mortem prototyped the design against the oracle before it was
  built (1,024/1,024) and found the re-arm and the ungated `ROUND` fix.  Hand-testing found
  "credit line before text" surviving -- the order row drove the stages itself (TRAPS #208).
  The first battery had one equivalent case and one of my own broken mutants.  **A four-agent
  pre-commit review** re-derived every instruction and drove 14 more machine cases, write for
  write equal; found two gate holes (the re-arm row excluded only "+8", and the end-state row
  never read the walk back), the undeclared interrupts-ON departure (TRAPS #210 -- now a leg of
  the oracle over sixteen frame phases, and a row), wrong counts in my own comments ("nine
  writers" is twelve; "thirty-five instructions" is bytes), `make_banner.py` still holding
  `'ROUND    9'` with no row tying it to the port, and the legibility of `T`.
  Mutation battery: 65 new cases, 10 re-anchored.  Final battery **2,331 of 2,331 killed** -- zero survivors, dead anchors or timeouts, 17.5 min on 30 workers.  bb.test 1,268 -> **1,288**;
  kit 120/120; selftest 34/34.  TRAPS #208..#210.

- [x] **M7.42 -- FRONT-END GROUP 2: `$9765..$97EA`, THE TITLE'S WAIT AND ITS EXIT, AND THE
  WIRING (2026-09-27).**  **The page now boots to the title and every game over returns to
  it.**  The sparkle ring and key wait, the two arms, the release wait and the hand-off, as
  eight methods gated ROW FOR ROW in iteration space against `title_wait` (one capture on a
  cold-started world, since title.pkl has no IM 2 ISR); and `frontFrame()`, the frame layer,
  whose every cost is a measured contended mean -- 374.4 iterations a frame against 374.08,
  the machine's release counts exactly, nine ISRs before the first key read.
  `gameReset()` ends in `titleEnter()`; `gameStart()` no longer calls `roundAdvance()`; the
  UNCALLED census 18 -> 17; `$9758` draws on a live path, so all nine `$802E` sites do.
  **The design was JUDGED**: three independent lifecycle designs (minimal churn, maximal
  faithfulness, testability first) and a judge that grafted the best of each and caught two
  measurement contradictions in them (the round build must drain through `carry`; the paint
  cost was a guess in one design, measured here).
  **Two old bugs the wiring exposed** (TRAPS #213): player 2 invisible (fixed in M7.42b) and
  the round advance's drain, recorded here as RA1..RA4 and NOT fixed in this increment:
  * **RA1** -- `BB_BANNER_T.ONE` (the banner `$98B5..$8D0C`) was measured WALL-CLOCK with the
    ISRs inside it (`run_until` takes interrupts) and is spent as main-line T, so the drain
    charges those ISRs twice: 3,525,023 against 2,835,397 main-line (+689,626 T).  The
    "15% digit-count class" is entirely ISR load; the main-line cost is flat to 0.06%.
  * **RA2** -- `isrCostFor(odd)` always adds `BB_ISR_ABSENT_AA60`; on the machine `$AA81` is
    absent while `$B54B` is non-zero (20 settle-window ISRs), present after (+157,925 T).
  * **RA3** -- the build `$97F8..$9887` and `$9888..$98B4` are charged 0 T (machine 678,792 /
    178,675, per round and key), and the `$9887` HALT a flat frame (machine: until the
    interrupt).
  * **RA4** -- `roundStart()` runs as one block, so the machine's first eleven ISRs (gate-
    closed, before `$9888` zeroes the counters) run in the port AFTER it, at full cost.  The
    same split is what the title's parity leak needs.
  With all four emulated the port gives exactly 61/62 ISRs and counter B 50/51.  RA1 and RA3
  must land together.
  **What caught what.**  The oracle agent found title.pkl's ISR is not the game's, and that
  the recon's `$5044` was round1_48's own seed.  An ISR audit measured the title ISR (488/493 T,
  counters only) and the parity leak.  Hand-testing found a no-exit off-by-one in my own row
  (the machine's bound stops at the 2,305th `$9770`).  The battery's first M7.42 pass left
  five survivors: three real gaps closed by rows (a stale carry, the PRNG site, the release
  reading only `$F7`), two declared equivalent under per-frame key sampling.  The four-lens
  pre-commit review drove 192 machine cases outside the fixture (0 differences), found the
  hand-off order ungated (TRAPS #211), `ARM_T` untied, the first-pass row able to pin the
  session seed exactly, and nine stale comments; and, playing the built page, player 2
  invisible.  The `$FEC5` "divergence" was my probe reading after the frame (TRAPS #212).
  Mutation battery: 50 new cases, 3 re-aimed.  Full battery **2,374 of 2,374 killed** (zero survivors, dead anchors or timeouts); after the review's fixes the M7.42 set re-ran **50 of 50 killed**, and the full battery re-runs with M7.42b.  bb.test 1,288 -> **1,302**; kit
  120/120; selftest 34/34.  TRAPS #211..#213.

- [x] **M7.42b -- PLAYER 2 WAS INVISIBLE, AND MOST OF PLAYER 1 WAS BLANK: the player sprite bank
  is `$D7C0..$DFFF` (2026-09-27).**  Found by the M7.42 review playing the built page: a
  two-player start drew nothing where player 2 stood.  MEASURED on round1_2p48 (3 x 4,000
  driven frames, interrupts on, walking, jumping, firing, deaths): the entity blitter reads
  exactly `$C6C0-$C6FF`, `$D300-$D33F` and `$D7C0-$DFFF` for BOTH players -- the same eight
  sprite pointers for `$FD80` and `$FD8A`.  A player sprite is 352 bytes (four pre-shifted
  copies) and the bank is SIX of them, ending exactly at `$E000`.  `tools/extract_entity_sprites.py`
  stopped at `$D8FF`, so the port held zeros from `$D900`: player 2 (on `$D920`) blitted a zero
  mask and zero data, and player 1 lost every frame but the first's aligned copy.  `$D900..$DFFF`
  is tape data -- byte-identical in all 54 usable captures and the round-80 dump, never written
  at runtime, never read by a non-player slot.  The asset now spans `$C100..$DFFF` (7,936
  bytes), the extractor asserts every measured frame lies inside and that the span ends where
  the last frame does, and three rows gate it: the asset's range, the engine's RAM over all six
  frames (and the tape image where present), and player 2's box holding pixels on every frame
  it is drawn through the two-player scene.  Against the OLD asset all three fail.
  No existing row moved -- which is how it survived: nothing had ever looked at a player sprite
  past the first frame, or at player 2 at all (TRAPS #213).
  Mutation battery: 2 new cases.  Full battery over M7.42 and M7.42b together: **2,380 of 2,380 killed**, zero survivors, dead anchors or timeouts, 23.5 min on 30 workers.  bb.test 1,302 -> **1,305**.

- [x] **M7.43 -- RA1..RA4: THE ROUND ADVANCE DRAINS AS THE MACHINE DOES (2026-09-27).**  M7.42's
  capture found every round advance three frames long; the four measured causes are fixed
  together, because none turns the count green alone:
  * **RA1** -- the banner is charged its MAIN-LINE T, one constant (2,832,314; round 81 7,110),
    not the wall-clock digit classes that step() then charged the ISRs of a second time.
  * **RA2** -- the diverted `$AA60` (the settle window) charges its own bracket, 381..557 T,
    instead of the undiverted absent term.  The BASE/per-slot split is PROVISIONAL (instruction
    sums, 381 exact and 546 inside the measured 545..557).
  * **RA3** -- the build `$97F8..$9887` and the tail `$9888..$98B4` are charged from per-(players,
    round) tables measured by the new `tools/rounddrain.py`, and the `$9887` HALT waits to the
    interrupt instead of a flat frame.
  * **RA4** -- `roundStart()` is split at the HALT: the build is spent, then `step()` runs the
    'halt', 'resume' and 'hp' phases, so the build's ISRs run gate-closed before `$9888` zeroes
    the counters and the HALT's ISR sees the arm.  **The title's PARITY LEAK is reproduced** and
    left `BB_TITLE.DEPARTS`.
  Result: the title hand-off drains 61 ISRs for '1' and 62/63 for '2' on an even/odd HALT,
  counter B 50/51/52 -- all four machine rows exact.  In play, 80 advances per key: round
  exact, pre-reset ISRs and HALT parity exact outside a near-boundary window, counter B the
  machine's or one short (IN-SAMPLE for the tables, TRAPS #215); on fourteen HELD-OUT natural
  advances the review found twelve exact and two one ISR short.  The residual is outside
  RA1..RA4: the in-play odd ISR ($A3AD's draw) is charged 12.4k..21.3k T less than the machine,
  and the even ISR the declared 41 T.
  **Also fixed from the review:** `$8D12`'s advance pass was charged a whole `BB_PASS_T` (6,186
  T) against a measured 96 (rounddrain `fecd_pass`, nine entries) -- the in-play row had
  compensated for it INSIDE the test; `mainLoop()` now throws mid round start; the round tables
  throw on a round they do not hold; `finishRound` is bounded; the title loops in the new rows
  are bounded; one old row that built rounds on half-finished sequences finishes them.
  **The design agent prototyped all of it**, oracle included, in a scratch copy; both fixtures
  reproduced bit for bit here.  I wrongly called its mutation result void (TRAPS #214).
  Mutation battery: 17 new cases, 16 re-aimed.  Full battery **2,402 of 2,402 killed**, zero survivors, dead anchors or timeouts, 29.3 min on 30 workers; its one hang-after-failures (an unbounded title loop in a M7.42 row) is now bounded and the case re-ran as a clean kill.  bb.test 1,305 -> **1,319**.
  TRAPS #214..#215.

- [x] **M7.44a -- KR1 + KR2: THE IN-PLAY KEY READER, MEASURED; the legacy fixtures RE-KEYED (2026-09-27).**
  The page starts a game whose player ignores the keys: nothing in the port writes the direction
  byte `(IY+8)` from input.  The machine's reader is `$ABF4..$ACEB` plus a Kempston branch
  `$AEF5..$AF29`, run once per ODD ISR inside `$AA60`'s player handler, P1 then P2.  Bits: 3 LEFT,
  2 RIGHT, 1 JUMP, 0 BLOW, 4..7 the previous read.  LEFT has priority on the keyboard (RIGHT's pair
  is skipped, no IN) and none on Kempston; a `($00,$00)` pair is permanently pressed; `$1F` means
  Kempston only in the first pair; the air rule locks L/R through phase 1..$0F and DROPS the jump
  to $FF on a change from $10 on (settled from the code -- one report said $10 locks); the reader is
  skipped while dying and under `$B54B`.  **`BB_KEYTAB` is not the tape's** -- the tape holds
  sixteen zeros; the port's O/P/Q/SPACE + 6/7/9/0 is a capture emulator's redefine, and the real
  keys come from group 3's control select.
  **KR1** `tools/keyreader.py` -> `build/keyreader_fixture.json`: twelve scenarios, a transliteration
  of the disassembly matching all 1,219 reads, deterministic, independently replayed row for row.
  **KR2** `tools/rekey.py`: the fourteen legacy movement fixtures had lost their key scripts; each was
  recovered from its own direction bytes under the capture's table (`F7 10 EF 04 EF 01 EF 08 1F 02
  1F 01 1F 08 1F 10`: P1 on 5/8/0/7, P2 on Kempston), re-driven row for row, and written back with
  `keys`/`kemp` per row and `seed.keytab` ADDED -- every existing field byte-identical, verified
  against git HEAD independently.  One suite row reads the new fixture and PINS THE GAP (the
  player ignores 'P').  No engine change.  bb.test 1,319 -> 1,320.  Next: KR3 + KR4 together.

- [x] **M7.44 -- KR3 + KR4: THE KEY READER IS WIRED -- the player answers the keys (2026-09-27).**
  `playerRead(slot)` is `$ABF4..$ACEB` and the Kempston branch `$AEF5..$AF29`, transliterated
  instruction by instruction, replacing `playerInput`; wired where the machine calls it (the odd
  ISR's `$AA60` player handler).  The fifteen movement gates that poked `$FD88` now drive KEYS
  from the re-keyed fixtures and add the reader's own byte as a differential; the KR-gate replays
  all 23 oracle scenario runs row for row, both players.  **Found on the way:** the players were
  gated on `$B54B` instead of the divert, so they ran one tick early at the end of every settle
  window (S13 -- row 39 against the machine's 41); the blow click `$ACAF OUT ($FE)` the spec
  omitted is ported (`blowClick`), held inside its own frame (the review drove blow+jump and
  found 54 out-of-order speaker edges without that).  The prototype's one survivor (a RIGHT-first
  `$AC83`) needed a scenario no one had: S7b, Kempston L+R held through a jump.  The review added
  S14 (rapid fire, `+$5F = 3`), a seeded probe for the settle freeze, an inactive-player row, the
  page's own rAF loop in KR-page (a template stepping with no keyboard passed before), and found
  the "one other writer of +8" claim true only inside the oracle (three more writers beyond it).
  **The page now plays**: walk, jump, blow, trap, die, respawn, two players.  **Not yet**: a
  popped enemy is never killed (`bubblePopEmit`/`corpseTick` unwired), so no round clears by
  play; the arrows and a gamepad do not move P1 under `BB_KEYTAB`, and nothing on the page names
  the keys.  Mutation battery: 35 new cases, 3 re-aimed.  Full battery **2,437 of 2,437 killed**, zero survivors, dead anchors or timeouts, 31.8 min on 30 workers.  bb.test 1,320 -> **1,373**;
  kit 120/120; selftest 34/34.  TRAPS #216.

- [x] **M7.45 -- THE POP KILL, and M7.45b THE FRUIT THAT STAYS: rounds clear by play (2026-09-27).**
  A trapped enemy's bubble popped but the enemy was never killed: `bubblePop` stopped at the head
  of `$B6D8` and never fell into the emit tail, and nothing called `corpseTick`.  Now the pop
  stores `$B775`, erases at `$BF0A` and falls into `bubblePopEmit`; the chain walk is real; the
  owner byte `$B9BC` is per player (a LATENT constant `$10` would have paid P2 for every kill --
  TRAPS #217); `$AAFC` dispatches corpses to `corpseTick`; `corpseDraw` is `$A26F` (it had used
  the masked sprite blitter); the pop click is ported; and three older gaps the wider vector
  exposed are closed (`$B62D`'s flash toggle, `$BE5B`'s `$92DE` writes, the `$B880/$B881` and
  `$B892` operands).  **M7.45b**: `$86CE/$86CF`, the item-age `AND $FF`, were zeros in the port,
  so every fruit vanished three frames after landing; `reset()` now seeds the tape's bytes.
  Oracle `tools/popkill.py` (scenes N1..N3, C1..C4; per-ISR RAM vectors as diffs, the HUD band
  masked and every stored cell scanned against the ROM charset; 14 claims) and `tools/itemage.py`.
  Gate PK0..PK8 + IA1/IA2: every ISR of every scene loads the machine's pre state, runs the
  engine's `isr()` and compares the whole post vector, display included outside the HUD band --
  exact on every row but the one declared ROM-window chain.  PK8: the built page clears round 1
  by play.  Built by an agent in a scratch copy from a recon agent's prototype; both fixtures
  reproduced bit for bit here; a three-lens review drove 18 more scenes (0 differences in the
  changed code) and found `$B892`, a silent click and four gate gaps -- all fixed.
  Declared: the pop and corpse-tick ISR T (pinned, PK7); the click's width is PROVISIONAL by
  range and a chain's pulse spacing is not modelled; ROM-window chains are counted.
  Open, found by the reviews: a risen bubble drifts one pixel off the machine in some scenes and
  can leave a dotted mark.  Mutation battery: 72 new cases, 5 re-aimed, 2 retired.  Full battery **2,505 of 2,505 killed** (the one survivor of the 2,506 run was the case already declared EQUIVALENT -- corpseDraw clipping below $4040 -- and it is retired), zero dead anchors or timeouts, 35.2 min on 30 workers.
  bb.test 1,373 -> **1,393**; kit 120/120; selftest 34/34.  TRAPS #217.

- [x] **M7.46 -- THE KEY CAPTION: ADDED page furniture, read from the key table in RAM (2026-09-27).**
  The page gave a player no way to learn the controls: the machine names its keys only on the
  control-select screen (front-end group 3), and the port's table is a capture emulator's redefine
  (O/P/Q/SPACE, 6/7/9/0).  A faint line under the screen, declared ADDED like the theme button,
  now DECODES the four `[half-row, mask]` pairs at `$B5FD`/`$B605` -- the bytes `playerRead` walks
  -- into key names every drawn frame, so it cannot disagree with what the game reads and stays
  right when group 3 writes the table: `$1F` reads "joystick", a `($00,$00)` pair "always held",
  plus pause/resume/quit.  A connected gamepad that no table reads is SAID (house rule 6), not
  ignored.  The page title is "Bubble Bobble" (it was the kit's "starter").  Two rows drive the
  page's own rAF loop with the table poked; 7 mutation cases, all killed.  bb.test 1,393 ->
  **1,395**; kit 120/120.  Engine unchanged, so the full battery was not re-run (8f9f299's 2,505
  of 2,505 stands); the 7 page cases were run and killed.

- [x] **M7.47 -- THE PUSH AND THE BOUNCE: the risen-bubble drift and the dotted trail (2026-09-27).**
  The M7.45 reviews saw a risen bubble one pixel off the machine and a dotted trail on the page.
  The cause was the player PUSH `$B94F..$B976`: the port never erased the bubble before moving it
  (`$B952 CALL $BF0A` -- the trail) and nulled the wind on EVERY push, where `$B968` nulls only a
  right or down wind and an up or left wind survives (the pixel).  And the deferred bounce
  `$B984` is now built: it ends `POP AF / LD (IY+8),A` with A = `$FD`, which a later bubble in the
  same pass reads as "pressing" -- the "crowded rising bubbles out of step" the reviews blamed on
  the R substitute.  The two players' touch tests share the B/C registers `$B8EA/$B8ED` loaded
  once, and `$ADAA`'s exit BC is `$F800` after a cell crossing (TRAPS #218, measured over 16,720
  direct calls).  Per-ISR differentials on seven scenes went from 3..76 bad rows to 0 (the one
  scene with a residual is the declared player-interleave gap).  The pop click's start is now
  held after any edge already logged in its frame, bounded to the frame and COUNTED.
  Oracle: `tools/popkill.py` N3 extended to 1,200 rows, scenes B1..B14, 22 claims.  A review found
  the `$ADAA` registers, the silent hold and five surviving mutants; all fixed and gated.
  Mutation battery: 34 new cases, 4 re-aimed.  Full battery **2,546 of 2,546 killed**, zero survivors, dead anchors or timeouts, 37.1 min on 30 workers.  bb.test 1,395 -> **1,405**;
  kit 120/120; selftest 34/34.  TRAPS #218.

- [x] **M7.48 -- THE PLAYER INTERLEAVE: $AA60 moves the players, the respawn calms, the fast walk works (2026-09-27).**
  The machine's entity pass dispatches every slot through its handler list, and the list opens
  `$AB38, $AB38` -- the player routine -- so slots 0 and 1 move the players INSIDE the loop: every
  enemy's `$AAC9/$AACF` copy of the tracked player reads the POST-move X+8/Y, `$AAE6`'s doubling
  runs a player with +7 bit 2 twice (the FAST WALK, which never doubled in the port -- nor did the
  death, the reader or the blow cadence), and the per-slot tail `$AB0C` evens a player's X AFTER he
  moves.  The port had run the players in a separate `updatePlayers()` AFTER the pass since M7.6-ii
  (TRAPS #220); `entityUpdatePass()` now routes `BB_PLAYER_HANDLER` to `updatePlayer(slot)`.  Two
  more gaps the differentials exposed: the respawn's CALM (`$ABB4/$ABBA` flip the opcode byte
  `$90D0` between SET 2 and RES 2 around `$ABB7 CALL $90C1`, so the walk clears every enemy's
  anger and 8-aligns its X), and the jump edge's `$AD0C RES 4,(IY+$5A)`.  Differentials over 29
  recon scenes went from 637 bad rows to 0.
  The first full battery's ONE survivor was a finding: `updatePlayer`'s activity guard is not on
  the machine (`$AB38` opens `BIT 2,(IY+$5A)`), and inside the pass the doubled run after a fast
  walker's final death reaches it (I9).  The guard went.  A four-lens review (27 agents: the Z80
  itself over 55 states and 106k frames of play, the gate, the page as a player, every claim)
  confirmed the three engine changes on the machine and found the gate short: P1-only scenes
  (the P2 calm, the P2 jump edge, P2's last death), no dying fast walker, a walker-gate row that
  could not fail, fixture facts no row read, and a declared-but-ungated blow click.  Now:
  `tools/popkill.py` scenes I1..I14, 33 claims (I8 separates "tail after the move" from "tail
  before" -- a mutant the handoff had proposed to declare equivalent, TRAPS #219); the blow click
  `$ACAF` gated for count and level on every row (the times declared: TRAPS #221); the shadow
  screen gated scene by scene; PK0 pins the claim count; the INTERLEAVE row runs the old order and
  counts its failures (51 of I1's rows, 34 of I2's) instead of quoting a scratch number; the
  `$AA60` walker gate counts the 5 frames where the order SHOWS rather than the 144 where a
  player moved.  `$90D0` and `$A3B2` joined the compared vector; `hurryAngers`/`hurryCalms`.
  Mutation battery: 35 new cases, 7 re-aimed.  Full battery: 2,581 cases, ALL 2,581 KILLED (0 survivors, 0 dead anchors, 0 timeouts; 21.9 min on 30 workers).  bb.test 1,405 -> **1,414**; kit
  120/120; selftest 34/34.  TRAPS #219..#221.

- [x] **M7.49 -- $A431, THE BEAM ACCUMULATOR: $A447's own adds, in the pass and out of it (2026-09-27).**
  `$A431` -- `$A430`'s self-modified addend, the base of `$A42B`'s beam-avoidance band -- differed from
  the machine by multiples of `$14` on every pop-kill scene, and M7.48 left it out of the vector.  A
  recon agent measured why: `$A447` (the entity erase/draw) makes its OWN `$A430` calls wherever it is
  entered, and it is entered outside the pass from `$BF16` (+20, the forced-shifted erase, none at a
  cached Y of `$C0` or more), `$BE92` (the capture's erase half), `$91D6` (Boris, main loop) and `$8C51`
  (a live enemy's final repaint); the port kept the accumulator in a JS local and stored it at the
  pass's end (TRAPS #222).  Invisible -- every pass re-seeds `$B9` before any band reads it (2,453 of
  2,453), which also REFUTES H12's "the band persists across frames" (corrected in SPEC, M7-PROGRESS,
  M7.7-H13-MODEL, tools/dropin.py and its fixture note).  Now `beamAdd()` is `$A430` on `ram[$A431]`;
  `a447Erase()` is the one spelling of `$A447`'s erase for the pass and the capture; `bubbleErase()` holds
  `$A464`'s gate before the add; `$A431` is in the popkill vector (PK9 and the cached-Y gate row), and
  `tools/boris.py` phase (g) runs Boris's draw for real with `$A431` bracketed (the main-loop entry no
  per-ISR gate sees).  A three-lens review (the machine lens re-measured the model independently
  over 983k ISRs in 49 states: six `$A430` sites, five `$A447` entries, no band ever reading a
  carried value) found the gate short: the capture's +20 and first-visit arms and the carry T of
  `$A447`'s own adds were unwitnessed (the capesc rows now bracket `$BE92` with 14 new cases; a
  `carry` phase in `tools/entdraw.py`), the Boris texts blamed the M7.21 runaway on a stale cache (it
  was `arm()`'s SP leak -- TRAPS #139 corrected), and `$8C51` on a live enemy was declared only in a
  comment (now counted and pinned).  Oracle claims 34/34.  Mutation battery: 23 new cases (the
  recon's M13, the carry T of an outside add, is UNMEASURED inside PK7's gap), 3 re-aimed.
  Full battery: 2,604 cases, ALL 2,604 KILLED (0 survivors, 0 dead anchors, 0 timeouts; 22.5 min on 30 workers).  bb.test 1,414 -> **1,420**; kit 120/120; selftest 34/34.  TRAPS #222.

- [x] **M7.50 -- THE ONE-LEFT ANGER: $8EC9 CALL $90A9 wired (2026-09-28).**
  With exactly one enemy left, the level-clear decision `$8E3A` calls `$90A9` on every main-loop
  pass; the latch `$90AA` lets only the first walk: `$90C1` angers every enemy slot (bit 2 of +7,
  which `$AAE6` doubles -- the survivor moves 2 px to 4 px per odd ISR) with `$FEC4` shut around it.
  The hurry falls into the same body and shares the latch; only the round reset `$9855` clears it,
  so after one anger and a death the enemies stay calm for the rest of the round.  The port had a
  stub `roundOneLeft(){ }` since M7.7-b; `angerPass()` is now the one transliteration of `$90A9`,
  called from `$8EC9` and fallen into by the hurry, with the diagnostics `oneLeftCalls` and
  `angerWalks`.  The stub was invisible to the whole suite (TRAPS #223): per-ISR gates never run the
  main loop.  Oracle `tools/oneleft.py` (new; 13 claims): direct `$8E3A` calls on 42 built worlds,
  six call sequences, two natural MAIN-LOOP differentials (N1 and L1), a census; `build/clear_fixture.json`
  re-captured (its note only).  Gate OL0..OL7 and the level-clear gate no longer holds the one-left
  rows out.  Built by a recon agent in a scratch copy; both fixtures reproduced byte for byte here.
  Mutation battery: 19 new cases.  Full battery: 2,623 cases, ALL 2,623 KILLED (0 survivors, 0 dead anchors, 0 timeouts; 23.1 min on 30 workers).  bb.test 1,420 -> **1,431**; kit 120/120;
  selftest 34/34.  TRAPS #223.

- [x] **M7.51 -- $8C51 ON A LIVE ENEMY: the dying enemy's final repaint erases it (2026-09-28).**
  `$8BC2`'s `$8C51` patches `$A5D9` to RET and CALLs `$A447` -- the erase-only entry the capture's
  `$BE92` runs -- with the dying enemy's own flags: a live, drawn enemy is ERASED at its cached
  position with the `$A430` add (+7/+20 by the cached X); a first visit or a cached Y of `$C0` only
  sets bit 6; a frozen or empty slot takes `$A437` (SET 5 and a second `$AA5F` DEC when bit 5 was
  clear).  The port ran only `$A437`'s bookkeeping, for bit 7 clear: a live enemy killed by an
  element or fire kept its last frame on the display (the M7.49 review: 12 bytes still wrong 400
  ISRs later) and `$A431` missed the add -- declared, counted and pinned by M7.49 -- and a frozen
  enemy cost `$AA5F` one where the machine costs two.  `entityEraseHalf()` is now the ONE spelling of
  the erase-only entry for `$8C56` and `$BE92`, `$A437` whole; `corpseLiveRepaints` is retired.
  Oracle `tools/corpserepaint.py` (new; 178 direct calls on built and real worlds of r20_48, firekill
  and elfire, natural kills in fbkill and elwater re-run through `$931A`, a census; 17 claims) ->
  `build/corpserepaint_fixture.json`; gate CR1..CR8 (CR8: the heart's touch kill `$92A2` reaches the
  same repaint -- no 48K capture sets `($FED0)`, so the built record stands in).  Built by an agent in
  a scratch copy; the fixture reproduced byte for byte here.  A two-lens review re-measured the
  machine on 346 direct calls in states the oracle never used (exact on the whole of RAM) and found
  the gate short on SET 6's order before `$A464`, the `$AA5F` wrap and the heart's route (worlds and
  a row added) and several over-stated counts (110 live `$8C51` entries are 99 environment kills and
  11 bolt kills; TRAPS #83 and `tools/popemit.py` carried the old `$A437` rule).  Found on the way:
  the lightning bolt's enemy kill `$9EFE` is still a counted stub, so bolt kills never happen in the
  port (next); and the harness never sees a ROM write (TRAPS #224).  Mutation battery: 21 new cases,
  2 re-aimed, 4 retired.  Full battery: 2,640 cases, ALL 2,640 KILLED (0 survivors, 0 dead anchors, 0 timeouts; 23.2 min on 30 workers).
  bb.test 1,431 -> **1,438**; kit 120/120; selftest 34/34.  TRAPS #224.

- [x] **M7.52 -- THE 48K BEEPER LAYER: every in-play OUT ($FE), and the hold across the frame
  interrupt (2026-09-28).**  `tools/beeper.py` (new) measured every emitter at its own entry -- the
  collect chirp `$8CB1` for nine values of C, the site `$881D` uncontended and at eight contended
  phases, the storm's 256 ticks by class, the reveal `$8C28` on two states, the pause's two OUTs, the
  HURRY UP! block, the front-end key click -- plus three natural runs through the ISRs (a collect, a
  whole storm, a HURRY UP!) and a census of every `OUT` the code holds -> `build/beeper_fixture.json`.
  Built: the collect chirp (`itemChirp`: forty OUTs at 66C+41, and its 55,793 T charged to the
  pass), the storm's ticks, flashes, strikes and wrap (`BB_STORM`), the pause gate and release, the
  reveal's `$8C4E OUT 0`, and the HURRY UP! train re-timed to the T (M7.19's flat step put each LOW
  and its HIGH at one instant -- silent, TRAPS #225).  And the hold: `mainOut()` holds a main-loop
  OUT at or past the frame's interrupt point and `flushHeld()` logs it after the port's ISR; every
  main-loop OUT but the pause gate's goes through it, the jump tone's included.  Built by an agent
  in a scratch copy; the fixture reproduced here (`beeper.py verify: MATCH`).  A three-lens review
  (machine, design, claims) found: the hold inserts the ISR that BEGAN the frame where the machine
  inserts the one that ENDS it (17..25k T against 1,892 -- declared), the storm's strikes a frame
  apart against the machine's long-short (declared, SFX8), three wrong releases that passed SFX10
  (SFX10b/c/d: the hold's placement predicted independently, the blow cadence through the train,
  one boundary), the jump tone bypassing the hold and the border (now through `mainOut`), two
  unported callers the site census missed (TRAPS #226), `$8C28`'s uncharged cost undeclared
  (`docs/TIMING.md` item 10), and a stale SPEC sound table (rewritten, every number re-checked
  against the fixture and the disassembly).  Its verify stage died on a session limit; every finding
  was re-checked by hand.  Older than M7.52 and pinned in SFX10 for the next increment: the HURRY UP!
  block runs with the ISR gates OPEN in the port (52..53 frames against the machine's 42.77).
  Mutation battery: 48 new cases (43, and 5 from the review), 14 re-anchored, 1 re-aimed.
  Battery: 2,688 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 24.3 min on 30 workers.  bb.test 1,438 -> **1,455**; kit 120/120; selftest 34/34.  TRAPS #225, #226.

- [x] **M7.53 -- FRONT-END GROUP 3, H-a: THE CONTROL-SELECT SCREEN `$F5E7..$F663` -- AND THE TREE MADE
  ROM-FREE (2026-09-28).**  `tools/ctrlselect.py` (new) drives player 1 from boot.pkl's own `$F5BC` and
  player 2 after each of player 1's four choices, the Firebird line over all 256 old attribute values,
  fourteen printer probes, CHARS moved on both printers, `$FAC3` on two paths and eight phases, and a
  read census from `$F664` to the relocation -> `build/ctrlselect_fixture.json`.  The screen splits by PC
  into four runs (CLS 6,912, rainbow 832, Firebird line 288, printer 1,888), refuting the reading's "one
  number" (TRAPS #153 again), and GROUP 3 splits on its key reads: H-a the screen (built here, UNWIRED),
  H-b the key read and the menu, H-c the redefine, H-d the spine, `$FAC3` and the wiring.  New:
  `ctrlOpen`/`ctrlPaint`, the front-end CLS, rainbow, printer and Firebird line, `feSeed` (the load's
  front-end bytes); the ROM's channel-2 print reproduced as a MEASURED constraint (old AND `$3F`, glyphs
  through CHARS, the stream checked and not interpreted).  Built by an agent in a scratch copy; the
  fixture and the font reproduced here byte for byte.  A four-lens review (machine, gates, claims,
  rules; 7 of its 27 verifications ran before a session limit, and the agent that built H-a reproduced
  every finding before fixing it, refuting none) found: row (j)'s "overwritten before anything reads
  them" false -- 13 of the 36 bytes are read first, the values are DEAD, and that is now measured (a
  read census, an un-write differential, a positive control; TRAPS #227); the menu runs with IFF 1, not
  0 (TRAPS #228 -- the M7.37 reading and M7.52's key-click row both said IFF 0); `$FAC3`'s footprint and
  duration were one path's (now a law over two paths and eight phases); decision 2b -- keyboard and
  gamepad only, the original menu behind `flags.originalMenu`, default OFF -- makes this screen the
  flag-ON path, and a page-level row asserts the page never runs it; the site census blind to 8
  unreachable methods (a reachability row now freezes 23); 22 surviving mutants (rows strengthened:
  every control byte, every bad `$F850` value, the 64-byte bound, player 2's CLS, rainbow and Firebird
  line store for store, the counters' meanings, the default A, no T charged); and the substitute 'P'
  equal to an eight-byte ROM window -- make_banner.py now refuses any ROM window and any glyph within 3
  bytes of its own cell moved two rows; P, K and '.' redrawn (TRAPS #229).  **THE TREE IS NOW ROM-FREE:**
  twelve quotes of ROM bytes in comments, docs and a fixture removed by pattern (a diff would have
  carried them), and the element-class fixture's nine ROM glyph cells (the EXTEND letters point into the
  ROM charset) nulled, with its oracle fixed; an independent scan finds no ROM character cell and no
  strong ROM window in any tracked file (the one strong hit is the game's own "Program:" at `$9A61`,
  which the ROM's tape messages share).  The git history still holds the removed quotes.  Mutation
  battery: 75 new cases (40, and 35 from the review), 6 re-anchored (the M7.38 LDIR pair, the four
  M7.39b census values), and the M7.31 "G is the ROM's G" case rewritten ROM-free.  Battery: 2,763 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 27.0 min on 30 workers.
  bb.test 1,455 -> **1,477**; kit 120/120; selftest 34/34.  TRAPS #227, #228, #229.

- [x] **M7.54 -- $9037's BLOCK IN TIME: the HURRY UP! banner climbs, the gates stay shut (2026-09-28).**
  `tools/hurryblock.py` (new) -> `build/hurryblock_fixture.json`.  The port had run the whole block in
  one frame (the banner never showed), reopened the gates at once (52..53 open-gate frames, the world
  moving under the banner) and run the rest of the pass at once.  Now the block's routines run ahead
  in the machine's order with every write STAMPED with its machine T and HELD until its frame (a RAM
  Proxy for the length of the call), the pass parks at `$8D52`, and step() drains the block with
  gate-closed interrupts: 40 of the natural run's 42 interrupts equal the machine's exactly.  Built by
  an agent in scratch; a three-lens review found a MUST-FIX -- the tail's temper walk, run ahead,
  overwrote what the 43rd (open-gate) interrupt did to enemies, re-freezing a released enemy with no
  bubble (TRAPS #230) -- now held as read-modify-write operations with their read stamps, measured
  against a new machine phase; and ~20 SHOULD-FIXes (held-out worlds, the Boris branch modelled, the
  diagnostics gated, the resumed pass's entries pinned).  Mutation battery: 78 new cases, 16 older
  ones re-aimed on the new code.  Battery: 2,841 cases, all killed, 0 dead or ambiguous anchors, 0
  timeouts, 32 min on 30 workers.  bb.test 1,477 -> **1,504**; kit 120/120; selftest 34/34;
  hurryblock.py verify MATCH.  TRAPS #230.

- [x] **M7.55 -- $9BB4, THE ENEMY PROJECTILES: all six arms, the release, the hit (2026-09-28).**
  `tools/projectile.py` (new) -> `build/projectile_fixture.json`.  The counted stub `enemyFireUpdate` --
  reachable since the game advances rounds, so every projectile the port spawned froze -- now runs the
  boulder, the breath, the bottle, the drop, the player fireball's update and the default arm, the
  release `$9D58` and the hit `$9D8B`, with `reset()` seeding `$9D82`.  75 direct calls and 1,345 natural
  `$9AEB` calls equal the machine's whole vector; 2,368 frames through step() match on the projectile
  state.  Built by an agent in scratch (rebuilt once after a scratch-directory collision wiped its first
  delivery); a single Sonnet review (the new economy) found no divergence from the machine and one gap --
  six arm counters never read -- now checked in PJ6 against the machine's events (the first draft of
  that check failed on the pristine engine: the fireball runs the breath body, TRAPS #216 again).
  Mutation battery: 40 new cases + 7 for the counters (run as a subset after the full battery: the fix
  only adds clauses, which cannot revive a killed mutant), 1 retired (the stub's own).  Battery: 2,880
  cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 37.2 min on 30 workers.  bb.test 1,504 ->
  **1,522**; kit 120/120; selftest 34/34; projectile.py verify MATCH.

- [x] **M7.56 -- $98B5's ROUND BANNER IN TIME: "ROUND n / READY !" is on the screen (2026-09-28).**
  `tools/bannertime.py` (new) -> `build/bannertime_fixture.json`.  The port drew the banner 256 times
  and erased it inside ONE call, so the page never showed it.  MEASURED: on the machine it is up for
  the whole of its ~2.83M main-line T with BOTH gates open (the settle window and `$98AF`'s `$2A`) --
  48..58 interrupts inside it -- and across fourteen natural banners (the title hand-off, 1P and 2P, and
  rounds 2..7 of each) no interrupt changes a byte the banner reads or repaints a banner cell, while
  they repaint up to 580 screen bytes elsewhere.  So the call runs the whole banner AHEAD and every
  write is stamped with its machine T and HELD until its frame -- M7.54's held writes, a second block:
  exact offsets (`BB_BANNER_W`: 256 iterations 10,902 T apart uncontended, the same 180 writes at the
  same offsets, `$802E`/`$995A`/`$9904` on the hurry's grid) on contended anchors fitted back from LOOP
  (`BB_BANNER_AT`: 11,035 an iteration; within 4,343 T of every natural iteration).  The 255 repeats
  are held too (a repeat is what repairs a cell an interrupt repaints), but a Proxy trap per write
  made the block fifty times the transliteration: iteration 0 records its writes under the Proxy and
  the repeats run the transliteration against a SCRATCH copy that is checked byte for byte at the
  erase.  `flushWrites` re-bases in place (the same semantics; 45 ms of allocation a banner gone), and
  `heldBy` keeps the hurry's open-gate count the hurry's.  Through step() on the port's own hand-off:
  48 / 49 interrupts inside it, the machine's, the whole banner up at every one and the erase after the
  last, as on the machine.  DECLARED: the frame ledger's ISR costs under the banner (41 T short on every
  even interrupt, 55..122 short on the diverted odd ones, and after round 1's twenty ticks the
  undiverted `$AA60` 4,070..4,087 T long in 1P, 2,237..2,245 in 2P -- PK7) move the interrupt points up
  to 17,966 T from the machine's, which changes only which repeat of an unchanged byte lands when.
  Built inline (no agent, no review, as planned); the oracle's first name overwrote M7.28's committed
  `roundbanner.py` and its fixture, both restored from git (TRAPS #231), and a `--help` started a real
  battery (TRAPS #232).  Mutation battery: 41 new cases, 6 re-aimed (the in-place `flushWrites`, the
  owner test, an anchor the banner's Proxy made ambiguous).  Battery: 2,928 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts (M7.13's resumed-pass case is killed by name before a hang, as in M7.54 and M7.55), 63.2 min on 30 workers.  bb.test 1,522 ->
  **1,530**; kit 120/120; selftest 34/34; bannertime.py verify MATCH; romscan clean.  TRAPS #231, #232.

- [x] **M7.57 -- $94C2's EXTEND COMPLETION IN TIME: the playfield empties, the fruit climbs, the
  life lands two seconds later (2026-09-29).**  `tools/extendtime.py` (new) ->
  `build/extendtime_fixture.json`.  The port ran the whole 17.1M T completion -- and the round advance
  after it, the next round's build included -- inside ONE call, so the page never showed any of it.
  MEASURED: `$94C2` exact on extcomp and nineteen variants (every path of the item pass, the lives
  rows, the letter panel and the digits), contended at sixteen phases, and twenty natural completions
  with interrupts on: both gates shut from +58/+71, every interrupt inside it gate-closed and touching
  nothing the completion reads.  So the call runs the whole completion AHEAD and holds every write
  until its frame -- M7.54's held writes, a third block -- stamped by a TIMING MIRROR: each routine
  names itself (`extRt`) and its model reads the RAM the routine is about to read and gives every
  write's exact offset (`BB_EXT_W`/`BB_EXT_I`, the disassembly's instruction sums, write for write and
  T for T on all twenty worlds), stretched by each routine's contention (`BB_EXT_K`, fitted on the
  natural runs: every hook within -5,810..4,685 T of the machine, DECLARED).  The round advance waits
  (`chainWalk`'s 'extend', `mainLoop`'s resume).  Through step() on a real game: the banner 13 frames
  in, the life 121 after it, the advance 247 frames in.
  **FOUND, all by the oracle's per-write stream:** (a) `$8C14` DIs and `$8C4C` EIs, so the machine
  LOSES the ~3.5 frames of interrupts under the reveal (244 in 247.3 frames) -- `intLost` now loses
  them in step() (and the prologue's `$94CB` window); (b) `$955E`'s wait counts what `$806C` left in A
  and B, not M7.25's constant (45, 4): a two-player completion is 124K T shorter; (c) the spin at `$9561`
  decrements `$861C` -- `$806C` leaves IX at `$85B9` -- not the letters (both end at zero); (d)
  `$8719`'s flood/storm skip was MISSING from `itemEntry` (a note said it was "already modelled"), so in
  play an item under a flood or a storm got an ink the machine never gives it; (e) the reveal's OUT
  went out 350,000 T early.  DECLARED: the fitted contention; the DI edges to within an instruction;
  the item blit's and erase's operand patches the port does not write; the RNG-ink power-up's values
  (`$873E LD A,R`); the calling pass charged nothing before the entry (as the hurry's).  Also found: the
  ROUND BUILD's scroll-in lands inside one call too (roundAdvance -> roundStartBuild) -- never visible
  -- queued.  Built inline; one Sonnet review (its SHOULD-FIX: `extBegin` refuses an open DI window, symmetric with the held writes; its NIT: `extBlocks` counts only a completion past the point, as `hurryBlocks`).  The battery's first pass on the new rows
  left eleven survivors, all test gaps: rows that built the machine's side from the engine's own
  constant (TRAPS #239), a `>= 1` on a counter two mechanisms feed (#240), a backward-stamp case with no
  budget, and `K.out`'s sub-T stretch (now 1).  The full battery's three survivors were M7.25's cases
  on `BB_EXTCOMP`, which the mirror had left dead: it is removed (its numbers kept as history) and the
  three re-aimed on the live code.  Mutation battery: 203 new cases, 48 re-aimed (M7.25's on the
  rewritten completion, M7.14's and the SFX's on the reveal's OUT, M7.54's on step()'s 'extend',
  M7.19's ambiguous anchor).  Battery: 3,131 cases, all killed (3,128 in the full run and the three
  re-aimed in the M7.25 subset, 59 of 59), 0 dead or ambiguous anchors, 0 timeouts (M7.13's
  resumed-pass case killed by name before a hang, as in M7.54..M7.56), 67.1 min on 32 workers.  bb.test 1,530 -> **1,542**; kit 120/120; selftest
  34/34; extendtime.py verify MATCH; romscan clean.  TRAPS #233..#240.

- [x] **M7.58 -- $A09A's STORM FLASH AND STRIKE TICKS IN TIME: the four inks are seen (2026-09-29).**
  `tools/stormtime.py` (new) -> `build/stormtime_fixture.json`.  The port painted a flash tick's four
  704-byte passes inside ONE call, so only the fourth ink was ever seen, and the rest of the pass ran
  at once.  MEASURED: `$A09A` exact on round1_48 (flash at `$1F`/`$3F`/`$DF` under four generator
  words, the three strikes): every `$A0F0` store at the `$A0E0` entry (337 + 29,088 k; 1,375) + 60 /
  7,954 / 18,455 + 41 i over runs of 192/256/256; contended at sixteen phases; and 78 NATURAL ticks
  with interrupts on (seven free worlds, round1_48 and r50_48 forced at sixteen phases, flash and
  strike).  Unlike the hurry's and EXTEND's blocks BOTH GATES ARE OPEN: 2..4 interrupts inside a
  flash, 0..2 inside a strike, each running the whole bubble manager and entity pass -- and none
  writes or reads an attribute byte, none reads a byte before the tick's main line writes it, and the
  main line reads nothing one wrote.  So the painter's stores are stamped and HELD to their frames
  (`stormBegin`/`stormHold`/`stormEnd`, M7.54's held writes, a fourth block, no Proxy -- the painter is
  the only writer and reads through its own held values), stretched by a fitted contention
  (`BB_STORM_K` 1.056080 / 1.059269, the forced runs' mean: stores within -1,638..+1,772 T of the
  machine in sample, -1,449..+1,128 out; strike -874..+1,483 / -810..+604, DECLARED), the OUTs after
  `$A0B0` and the cost stretched with them, and the pass parks at `$8D46` (`chainWalk`'s 'storm').
  Through step() on a real game: the inks land pass by pass, the stores landed at each frame's end
  exactly those the stamps put before its interrupt point, `$A824` resumes after two interrupts.
  DECLARED, not modelled: the strike payload `$A0F5` lands at the call and its DI window loses no
  interrupt.  One Sonnet review: its SHOULD-FIX was real -- the last store comes 31 T (flash) / 57 T (strike) after the T the tick leaves (the idle path's 90 T are charged later, in `BB_PASS_T`), so a point in that gap left one store held with the pass running on, and `$9037` in the same pass would have thrown over it; the pass now also waits while a store is held (ST5 constructs the gap).  Its NIT: the flood's door checked inside a tick too, and a timed pass with no tick up.  Battery: the M7.58 subset left four survivors -- three
  test gaps in ST4 (TRAPS #242: it now pins the landing count per boundary, the entry after the tick
  and the carry) and one mutant equivalent by algebra (#243: a constructed case now sees it).
  Mutation battery: 38 new cases, 14 re-aimed (B10's, the SFX's and M7.54's/M7.13's on the rewritten
  tick and step()).  Battery: 3,169 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 70.2 min on 32 workers.  bb.test 1,542 -> **1,548**; kit 120/120; selftest 34/34;
  stormtime.py verify MATCH; romscan clean.  TRAPS #241..#243.

- [x] **M7.59 -- $97F8's ROUND BUILD IN TIME: the new level scrolls in (2026-09-29).**
  `tools/buildtime.py` (new) -> `build/buildtime_fixture.json`.  The port ran the whole build inside
  one call, so every round change showed the new level at once.  MEASURED: 322 natural advances
  (rounds 1..81, 1P and 2P, two tile phases, sixteen chunks of ten on 32 workers) -- the separator
  band, 4 pre-roll and 22 scroll steps of ~146K T (not the ~10 frames next.md guessed: ~53), the
  repaint, the lives; every interrupt gate-closed (488/493 T) writing only the frame counters but for
  the ENTRY WINDOW (2 advances at phase 69,841 run one gate-open, touching nothing the build reads,
  DECLARED); and twelve worlds EXACT, where every step and push writes the same bytes at the same
  offsets.  THE PORT: every display write of the build stamped and held to its frame -- a fifth
  block -- from a per-round anchor (BB_BUILD_AT, the scroll mark's mean: the tile moves it 0..8 T)
  and exact sums (BB_BUILD_W; the M7.57 mirror's models for the repaint, the lives and the letter
  panel), stretched by BB_BUILD_K (1.180387 / 1.255556, fitted).  BD1: every display write at the
  machine's exact T on all twelve worlds with the machine's own clock; BD2: within -4.7K..+4.8K T of
  two natural advances write by write, every step entry within 3,131 T; BD4 through step(): round 2's
  170,244 writes land over 64 frames, each in the frame its stamp puts it.  The Proxy is on only
  where the display is touched (TRAPS #244) and the copier runs at module level (#245); the
  held-write queue keeps its entries' times and moves its own clock (heldShift) instead of re-basing
  every kept entry every frame -- shared machinery, the suite 13 -> 19 s with the new rows.
  FOUND: the machine's round-1 HUD makes 100 (1P) / 136 (2P) display writes more than the port's
  `$7FC0..$7FFC` (each HUD attribute row twice, row 23's first four cells) -- queued with the HUD's
  model; round 1's HUD lands at its hook, DECLARED.  One Sonnet review (its SHOULD-FIXes:
  `hurryBegin` now refuses another block's writes as every other Begin does; `buildBegin`'s guard
  states why it is unreachable).  Battery: the M7.59 subset first left eleven survivors -- two
  dead code (the holders' queue clock is always 0: deleted, #243), one masked by a negative count
  (`heldOps > 0`), the rest test gaps: the copier's counters and overtaking guard (constructed), the
  store path's point, the absolute write count, the stretched stamps' rounding (BD1b) and the scroll's
  values, which the repaint hides from any end state (#246: BD5c).  59 new cases, 20 re-aimed.
  Battery: 3,228 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 106.4 min on 32 workers.  bb.test 1,548 -> **1,557**; kit 120/120; selftest 34/34; buildtime.py verify MATCH;
  romscan clean.  TRAPS #244..#247.

- [x] **M7.60 -- $9DE1 THE FIREBALL'S SPAWN, AND $A0F5 THE STORM PAYLOAD IN TIME (2026-09-29).**
  THE FIREBALL: the blow's `$BD70` in fire mode is `JP nz,$9DD4` -- the request, and no bubble -- and
  the element tick's first call `$9DE1` spawns it (the M7.55 measurement, 15 direct worlds, plus two
  new ones: an UNALIGNED enemy shot recycled, +6 `$43` left `$40`).  PF0 replays all 17 through
  `elemPreTick()` under a write log -- the slots, the request, (`$FEC5`)'s 0-then-1, the shooter's
  unmark, the display writes of the recycle's erase; PF1 the request from a fire-mode blow (P2's IX is
  the machine's `$FD8A`), PF2 the chain.  Fire mode was already reachable in the port (the power-up
  `$88DC` sets +`$5A` bit 5), so until now a fire-mode player blew nothing at all.  THE PAYLOAD:
  `tools/stormtime.py` gains a 'payload' phase -- the exact stores (identical on six ticks, waiting
  and strike) and a contended sweep of the interrupt line over 200 offsets: lost at exactly
  160..1,287.  The port holds the 36 stores through `stormHold` (the SETs as operations, M7.54's
  shape), pushes the DI window onto `diWindows` for intLost, and gives the thirteen waiting ticks a
  storm block of their own.  PS0 stores/stamps/RAM against the six exact ticks, PS1 the window
  against all 200 sweep offsets, PS2 the holding (an ISR's change to a flag survives the held SETs),
  PS3 through step() with the phase forced: the frame's interrupt LOST, $8DBD unmoved, the stores
  landed next step.  Battery: the M7.60 subsets left seven survivors -- five test gaps, closed (the
  fireball's ($FEC5) 0 needed a write log and its recycle an unaligned shot; the payload's flash-tick
  window, an op resolved early, and PS0 replaying its own log instead of reading RAM -- TRAPS #250)
  and two EQUIVALENT, dropped: `$9DE0` read as `$FD`
  (the census: only `$9DD4` writes `$9DDF`, with IX = `$FD80`/`$FD8A`) and a held op's view value
  (nothing reads it).  58 new cases, 9 re-aimed (B10's payload, the SFX idle rule, M7.58's hold and throw).
  Battery: 3,286 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 109.2 min on 32 workers.  bb.test 1,557 -> **1,564**; kit 120/120; selftest 34/34; projectile.py and stormtime.py verify MATCH; romscan clean.  TRAPS #248..#250.

- [x] **M7.61 -- FRONT-END GROUP 3, H-b: THE KEY READ `$F7B3`, THE MENU, THE DISPATCH, THE PRESETS AND THE
  KEY-TABLE BUILDER `$F6DB`, AND THE FRAME LAYER THAT RUNS THE CONTROL SELECT (2026-09-29).**  Landed from
  the recon (based on M7.53) onto M7.60: the recon's game.js and template hunks applied cleanly, port.json's
  entry and the gate block were placed by hand, `tools/ctrlmenu.py` copied in and RE-CAPTURED here --
  byte-identical to the recon's fixture.  THE ROM'S KEYBOARD ROUTINE (behind `$F7B8`'s RST `$38`) is a
  MEASURED CONSTRAINT, never a transcription: 160 decode rows (118 emit, 56 accepted), all 780 pairs and 238
  wider chords (FREEZE vs KEY), 23 named histories and a 3,000-scan random walk -- two sets, aged before the
  match, the second taken first, a repeat emitting the STORED code; the fixture keeps the game filter's
  verdicts, key names, counts, T and port bytes, no ROM byte.  The filter, the menu test, the dispatch, the
  three presets (SINCLAIR's self-patching one-shot) and the builder are transliterations; the click is its
  measured 241 OUTs; `ctrlBoot()`/`ctrlStep()` run it frame by frame on step()'s ledger, 12 key scripts
  diffed against the machine at every frame boundary.  UNWIRED: nothing on the page calls ctrlBoot or
  ctrlStep (row (q)); H-d wires it.  THE BATTERY'S FIRST SUBSET left six survivors: one equivalent mutant of
  mine (replaced), FOUR small T terms -- the accept exit by key, the menu test's exit, `$F5F0`'s exit, a
  digit's cheaper decode -- which (k) tied to the fixture as CONSTANTS while (j)'s bands could not see them
  SPENT at the wrong step (new row **(j2)**: every spend logged with markers, compared with the machine's
  number for that key -- TRAPS #251), and the builder's EIGHT-bit SLA, reachable only with answers the
  filter never passes: the oracle now drives `$B0/$B5/$C9/$DF`, whose doubled offset wraps back into the
  `$F988` map (MEASURED, not argued -- 52 drives).  THE REVIEW (one Sonnet reader, the frame layer): no
  high-confidence bug.  Its main query -- player 2's open and paint charged an interrupt on top of a debt
  that might already hold one -- is refuted by the oracle: the contention tables are measured with
  interrupts OFF.  Two silent holes it named are now named failures (row **(j3)**): `$F671` other than
  `$2A`/`$33`/`$34` at the paint THROWS (it used to paint as if no line were dropped -- H-c's `$31` has no
  measurement yet), and a scan path with no measured T throws instead of leaving NaN to end the frame loop.
  107 new cases, 3 re-aimed (the SFX / M7.52 flushHeld anchors, which ctrlStep's copied line made
  ambiguous).  Battery: SCOPED to what M7.61 touched: 191 of 3,392 cases (H-b's 107, M7.53's H-a cases, the census cases and the three re-aimed), all killed, 0 dead or ambiguous anchors, 0 timeouts, 8.5 min on 32 workers -- the FULL run is owed at H-c (two attempts at M7.61 were killed by the harness for low memory, near 95 min).  bb.test 1,564 -> **1,583**; kit 120/120; selftest 34/34;
  romscan clean.

- [x] **M7.62 -- FRONT-END GROUP 3, H-c: THE REDEFINE SCREEN `$F723..$F7B0`, AND PLAYER 2'S PAINT AFTER
  KEYBOARD (2026-09-30).**  `tools/redefine.py` (new) -> `build/redefine_fixture.json`: eleven drives from
  `$F723` to the builder's RET on four worlds, interrupts OFF, each answer fed from its read's first scan to its
  accept -- every screen write in order (the CLS and rainbow as values, the printer as address/code/row), the
  prompts' calls, the marks' T, the non-click OUTs, the state before and after; the T laws at 64 phases with
  16 held-out midpoints; five key scripts from boot.pkl's `$F5BC`, frame for frame.  THE CODE: CLS, rainbow,
  header, LEFT; five reads (H-b's, the echo now PRINTED -- `$F850` is the NOP `$F674` left); the answers to
  `$F983 $F984 $F986 $F985 $F987` (the third and fourth SWAPPED); 'Y' to the builder, anything else round
  again.  THE CHEAT: player 2's 'R' turns `$F6A3`'s RET into a NOP; armed, every answer but 'Y' runs the
  checksum `$F6A4` (A + the five answers - `$8F`), whose zero stores 0 over `$FA3F` (the 128K trampoline's
  RET -- reached only from `$FAC3`'s non-48K branch) and sends OUT 2: a red border until the loop's CLS reaches
  `$F716`, 178,907..189,526 T later by phase.  THE T: the screen, the loop (three phases apart from it) and
  ONE prompt law (contention is by time, not address) by phase; the click with its printed echo 368,286.5
  (851 T over the menu's); the exits and the builder the means of 64 phases (the stack at `$61xx` is
  contended); player 2's paint after KEYBOARD (`$F671` = `$31`, 80 characters) its own law -- where H-b's
  `ctrlPaintPass` threw.  THE PORT: `redefOpen/Head/Answer/Check/Call/Loop` transliterated; the frame layer's
  KEYBOARD no longer stops -- stages 'redefine' and 'prompt' run on `step()`'s ledger with the interrupts on
  top, and `ctrlPassEnd` takes the pass to player 2 or the spine.  THE FONT: the echo prints any code the filter
  passes, so nine cells were drawn (`> ? @ J Q X Z ] _`) to the no-ROM rule (the first 'X' sat one byte from a
  ROM window: redrawn); 60 codes.  H-c(a): 180,160 screen writes of the eleven drives in the machine's order;
  (b) the state and every game byte after; (c) the T tied to the fixture; (d) the five scripts through
  `ctrlStep()` frame for frame; (e) each stage's spend at its step (the laws named by the fixture table they
  equal, every click's debt, the exits by path, the reads' entries); (f) the red border at the machine's frames;
  (g) the 80-character paint and the seeds; (h) the page never runs it.  H-b's (e), (j3) and (o) follow the
  change; the census grows by nine.  FOUND on the way: the screen census stopped at the first '?' -- a code the
  font had no cell for, counted and never drawn, as designed; the border's CLS span first taken at one phase was
  10,467 T short at the script's (TRAPS #255).  Hand-tested: the H-c subset (73 cases) left ONE survivor, the
  reads' 37 T entry -- a term the bands hide (#251): (e) now pins it.  66 new cases, 6 re-aimed (H-b's KEYBOARD
  stop, player 2 never asked and player 2's '1'; the font census's three counts).  Battery: 3,458 cases, all killed, 0 dead or ambiguous anchors, 0 timeouts, 128.2 min on 20 workers (the FULL run M7.61 owed; one M7.13 case killed by three failures and then a hang).  bb.test 1,583 ->
  **1,591**; kit 120/120; selftest 34/34; redefine.py verify MATCH; romscan clean.  TRAPS #252..#255.

- [x] **M7.63 -- FRONT-END GROUP 3, H-d: THE LOAD SPINE `$F5C6..$F5CF`, THE 48K/128K PROBE `$FAC3`, THE ROM
  INTERRUPT'S T AS A LAW, AND THE HAND-OVER `$F5CC..$970E` (2026-09-30).**  `tools/loadspine.py` (new) ->
  `build/loadspine_fixture.json`: 56 key scripts from `$F5C6` (player 1 '4', player 2 '3', driven from title.pkl)
  with every interrupt in the CLS and the probe as (T past its boundary, length), five of them entered at `$F5C9`
  5..40 T before a boundary, the cheat armed with and without A+D+G; the ROM interrupt from the idle probe loop
  over 117 single keys and shifts, set 0, the full path, 703 pairs and 338 wider chords; the CLS and the cold
  start at 64 phases + 16 midpoints; the hand-over into the title at 8 phases, a second path and the six
  phases that put a boundary within 30 T before `$8CCA` or `$970E`; the interrupt window's own terms.  THE
  CODE: `$F5C6 CALL $F709` (the black screen), `$F5C9 CALL $FAC3`, `$F5CC LD HL,$F5D2 / JP $7274`.  THE ROM
  INTERRUPT: H-b's eight path averages could not serve a count that sums 255 of them ('held' is 1,124 in set
  1, 1,096 in set 0; freezing chords 482..1,007) -- `BB_ROMISR`, an additive law (a scan term by half-row and
  highest bit, a base by path/class/shift, the sets' terms, the third-key exit for chords), exact on all
  23,529 measured interrupts and on H-b's own ten (TRAPS #256).  THE PROBE: modelled instruction by instruction
  with the harness's ULA table on `CP (HL)`'s read of FRAMES; every script's HALT, all its interrupts' offsets
  and lengths, BC, E, A and the T to `$F5CC` EXACT.  'A' held 22 frames answers `$30`, 23 `$80`; a freezing
  chord RAISES the count (A+D+G 100..115 frames: `$0763`, 130: `$0764`).  Entering it: a boundary crossed by the
  CALL or `IM 1` is the ROM's interrupt and the HALT waits a frame; one crossed by `EI` the HALT takes at once.
  THE HAND-OVER: the cold start by phase (DI), `$9575`'s wait (EI: the game's own interrupt, 488 T, counting
  only), the reset half (DI); an interrupt inside a DI still TAKEN when EI and the next instruction end inside
  its 32 asserted T (TRAPS #258); `$9601`'s key copy MODELLED -- `reset(keys)` lays the control select's buffer
  back and the cold start copies it.  THE PORT: stages 'spine', 'enter', 'halt', 'probe', 'hand'; at `$970E`
  `handDone()` rebuilds the world (the page's clocks, the sound log and -- in `fePast` -- the front end's counters
  kept), counts the taken interrupt, runs `gameStart()` and finishes the frame the game's way.  `skipProbe`
  (ADDED, default ON: the owner's decision) answers `$30` at `$F5C9`.  DECLARED: an `$80` on a 48K is the 128K
  leg (`$96B3`, the AY engine over the sprites) -- counted (`probe128`), the 48K leg taken; the armed cheat's
  `$FA4A..$FA66` (223 spawn-record bytes' enemy types) reached only there -- counted; the CLS charged as an
  interrupts-off law with its interrupts on top (33 T at the scripts' phase, up to 1,448 where they land
  elsewhere; the HALT re-syncs).  H-d(a) the law over every interrupt; (b) the probe against 56 scripts; (c) the
  laws, their USE at all 64 phases, the window's measured terms, the screen `spineOpen()` leaves; (d) the
  hand-over against 14 natural runs into the title (the interrupts taken/lost/late, `$970E`, the key table,
  `$8DB6/$8DBD` at `$970E` and the next two boundaries, the title's first ring iteration within 12,000 T);
  (e) the flag; (f) the 128K answer counted; (g) the copy; (j) H-b's entry and dispatch spends at their step; (h) the whole load end to end through `ctrlStep()`
  into `step()` and a game started; (i) the page does not run it yet; an `else` row fails if the block cannot
  run (TRAPS #257).  H-b(k) and H-b(o), two cold-start rows (the copy no longer skipped) and the census (+10,
  -`ctrlStopped`) follow.  FOUND on the way: TRAPS #256..#261 -- and #192 (a heredoc ate a backslash) and #251
  (a band hid the CLS law's use; pinned by an exact row) recurred.  Hand-tested: the H-d subset (96 cases) left
  five survivors -- the window's three constants (no natural run reaches the edge: pinned to the measurement,
  #261), the CLS left undrawn (row (c) now reads the port's own screen) and the title's partial frame after
  `$970E`, an EQUIVALENT mutant (the carry moves the remainder; the nine-frame paint debt outlasts it; not
  listed) -- then 95/95.  One Sonnet review (shared machinery: the hand-off into `step()`): the ledger
  sound; `reset()` left `kb` null and `budget` Infinity for the rest of the handed frame -- unobservable
  today (the title's paint debt reads no key and makes no OUT), fixed to `step()`'s contract; `probeAt` and
  `probeEndAt` kept in `fePast`.  95 new cases, 8 re-aimed.  Battery: FULL: 3,552 cases, all killed -- 3,549 in the full run on the final engine (140.2 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before), and its three H-b survivors killed by two new rows (H-d(a) now checks each interrupt's class; H-d(j) pins the entry and dispatch spends the spine's old stop used to catch -- TRAPS #262).  bb.test 1,591 -> **1,601**; kit
  120/120; selftest 34/34; romscan clean.  TRAPS #256..#262.

- [x] **M7.64 -- THE LOAD, WIRED: THE PAGE BOOTS THROUGH THE CONTROL SELECT (2026-09-30).**  The page's boot
  line is `game.ctrlBoot(BB_MENU.LOAD_PHASE)` -- `LOAD_PHASE` 34,943, boot.pkl's own `$F5BC` phase, tied to the
  fixtures -- and `step()` delegates to `ctrlStep()` while `ctrl` is set, tested every frame (the hand-over's
  `reset()` nulls it inside the frame `$970E` falls in).  `tools/loadpath.py` (new) -> `build/loadpath_fixture.json`:
  THE WHOLE LOAD AS ONE DRIVE from boot.pkl's `$F5BC` -- both passes, the redefine screen, the black screen, the
  probe RUN, the hand-over and forty frames of the title -- on two scripts (KEYBOARD redefined O/P/SPACE/Q then
  SINCLAIR, whose table IS `BB_KEYTAB`; CURSOR then KEMPSTON), a sample at every boundary: stage, pass, border,
  the bitmap's and the attributes' CRC-32.  M7.64(a) the page's boot; (b) the engine through `step()`, the probe
  run (skipProbe OFF), against both, FRAME FOR FRAME: every frame's stage, pass and border; the attributes on
  every frame but the declared drawn-at-once ones (three from a stage's start) and the title's (its ring draws
  its stars at a contended MEAN of iterations a frame -- BB_TITLE's own departure); the black screen's bitmap
  and attributes on all 257 of each; the key table the cold start copied; (c) THE BUILT PAGE, its own loop and
  real key events, the default flags: the machine's rows to the black screen and, skipProbe ON, its rows with
  the 256 probe frames removed after -- the title in 90 frames, one engine frame per display frame; (c2) the
  caption; (d) `padKempston` (ADDED, default OFF): the template's `poll()` zeroes both Kempston ports after
  `pollGamepads` unless it is set, so a player who takes KEMPSTON cannot move (the owner's words), and the
  caption says why.  MEASURED ON THE WAY: the text screens' bitmaps can never agree (the substitute font, the
  no-ROM rule), so only attributes are compared where there is text.  FLIPPED: M7.42's boundary row (the page
  boots through the load; a fresh `gameStart()` still opens `$96DF` with the paint owed), M7.53(r), H-b(q),
  H-c(h) (it had gone VACUOUS -- TRAPS #265), H-d(i), M7.46's gamepad note; the UNCALLED census 17 -> 16
  (ctrlStep left, ctrlBoot a driver name), the reachability census 63 -> 12 (roots constructor, ctrlBoot,
  step).  FOUND: TRAPS #263 (a float rAF clock lost a frame), #264 (the page's loop clock only runs forward),
  #265.  One Sonnet review (the page's entry point): none found on all four items.  17 new cases (one survivor,
  poll() clearing only the first pad, killed by a two-pad row); 4 re-aimed (two anchors on the old boot line,
  one mutant left syntactically broken by the new `else if`, and a census case whose unreachable host --
  ctrlPaint -- became reachable).  Battery: FULL: 3,569 cases, all killed (136.7 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before) (M7.64).  bb.test 1,601 -> **1,606**; kit 120/120; selftest
  34/34; romscan clean; `loadpath.py verify` MATCH.  TRAPS #263..#265.

- [x] **M7.71 -- THE EXTEND SEED: THE `LD A,R` STAND-IN TAKES THE RUN'S IDENTITY AT THE START PRESS
  (2026-10-02, owner-reported).**  The owner could never collect a second E.  Not the award: `$B7E5`
  indexes `$B80E` (the machine's bytes) and class 8 sets bit 3, the second E.  The class comes from `$7E04
  LD A,R / AND 7 / ADD A,5`, and BB_Rng (the declared R stand-in) was seeded with `BB_RNG_SEED` at
  `reset()` and never again: every page load drew `6 12 9 10 9 10 5 5 11 ...`, class 8 first at the 35th
  pick.  `rngSession()` (new) re-derives the stand-in's per-site streams from `$FE86/$FE87` at the title's
  start press -- the `$9775` spin's state, RNG.md's "the run's identity" -- keeping its counters, the
  starfield walk and a feed queue (`BB_Rng.reseedStreams`, new).  No clock: a session is still a pure
  function of (wait frames, key trace).  Gate (title block (l2)): 16 press frames give 16 distinct class
  sequences and seeds, 10 with a class 8 in their first twelve; the same press frame gives the same one.
  Battery: 6 new cases, 5 killed, 1 EQUIVALENT dropped and named (reading the state before or after
  `titleArm`, which never writes `$FE86/7`); subset: every RNG-related case re-run against the new seeding, 249 cases (labels naming RNG / seed / draw / LD A,R / hesitation / element class, plus M7.71), all killed (12.9 min, 20 workers, 0 dead anchors); the full battery last ran at M7.70.  bb.test 1,636 -> **1,637**.

- [x] **M7.70 -- THE EIGHT ENEMY HANDLERS CHARGE THEIR OWN T (2026-10-01, PK7).**  M7.69 left the enemy runs
  at their fixture medians (`BB_AA60_RUN`, 911..1,493 T contended, whatever the path; a run is 118..3,147 T).
  `tools/enemycost.py` (new) records every run of `$AF31`, `$AF47`, `$AF5F`, `$AF77`, `$AF95`, `$AFAF`,
  `$AFC4`, `$AFF6` on an UNCONTENDED machine -- 48 states x 300 frames under ab38cost's key script -- 11,191
  runs, 339 natural paths, per run the T, every byte read before written, every byte written, each LD A,R;
  plus 18 declared FORCED CALLS (one call of the handler on the machine from a poked saved state) for the
  arms no natural run reaches and `$AED1`'s D at the HUD's edge.  Two oracle faults found on the way and fixed (TRAPS #275, #276): `$FE85`'s
  operand is the PRNG state and was not seeded; an angry slot's SECOND run, entered by the first run's RET,
  was not recorded (17% of runs).  Before any T was added every kept run's writes and draws matched the
  engine already.  `BB_EN` is sums over named ranges of the measured per-instruction T
  (`scratchpad/ensums.py`, no hand sums; the forced calls measured every instruction the Z80's table had
  stood in for), added on the engine's own branch decisions (`this.eT`) in enemyHandler, the walker, the
  move decision, the step, the hop, the flyer and its probe chain, type 4 and its horizontal move, and
  the shared `$AED1` / `$B47E` probe.  The first gate run found two cut errors in the sums (TRAPS #274).
  EN1: all 751 kept runs exact in T, in every byte written, and writing nothing more.  The first battery
  subset left 14 of 321 alive (TRAPS #277): 3 EQUIVALENT (equal constants: M_FOUND / M_NF, PB_UP / PB_FT, S1 / S5 --
  dropped, named), `FLIP` never read (removed), and 10 that the rows did not reach -- the dedup by path
  alone (now path and T) and `$AED1`'s D at the HUD's edge (5 more forced calls); all 10 then killed.  EN2: the pass
  charges them (`frameLedger().aa60.enemy`); `.prov` is the corpse flight alone.  AC1, AC4, AB2 and the
  round-1 ISR row now read the enemy term as exact; BT3's windows did not move (round 1's enemies sleep
  through them).  Battery: 296 new cases (each BB_EN value +1 element by element, 62 wiring cases including EN1's
  no-extra-write rule; `M_DEAD` dropped as dead) and 22 re-aimed.  FULL: 4,175 cases, 4,173 killed (182.3 min on 20 workers, 0 dead anchors, 0 timeouts; the M7.13 case three failures then a hang, as before); the 2 survivors -- M7.68's doubled-run and ledger-report cases, toothless once the enemy runs left .prov -- killed by AC4 on an angry unpriced slot.
  bb.test 1,634 -> **1,636**; kit 120/120; selftest 34/34; romscan clean; `enemycost.py verify` MATCH.

- [x] **M7.69 -- THE PLAYER HANDLER $AB38 CHARGES ITS OWN T, AND THE PROBE ABOVE THE HUD (2026-10-01, PK7).**
  M7.68 left every `$AA60` handler run at its fixture median; the player's (`$AB38`, 189..8,229 T contended)
  was 1,606 whatever the path.  `tools/ab38cost.py` (new) records every `$AB38` run on an UNCONTENDED machine
  -- 48 states x 300 frames under its own key script, pressed through each player's OWN table at `$B5FD` /
  `$B605` (aa60cost's O/P/Q/SPACE never reached any state's jump entry: the arc's air rule `$AC5D..$AC98` had
  never run), plus 17 declared FORCED runs (the final death at five erase classes, P2's respawn, round 80,
  six lives, a Kempston table, the bubble-jump, the fall wrap, phase 33, the left ascent with and without a
  gap above, the heart freeze, a pop on a dead bubble, the probe above the HUD with `$712F..` solid) --
  7,205 runs, 346 distinct natural paths, 189..10,471 T; per run the T, every byte read before written,
  every byte written.  An uncontended run's T is its instructions' own, so `BB_AB38` is sums over named
  ranges of the per-instruction T the oracle measured, added on the engine's own branch decisions
  (`this.pT`); `adaaT()` walks `$ADAA`'s tree because `playerMoveH` is condensed; `probeT()` the probe's;
  the final death's `$BF0A` is its own sums around `BB_A3AD`'s erase class (the 128 T between them is
  `$A447`'s head and `$A5D9`'s patched RET).  AB1: all 882 kept runs seeded into a fresh engine give the
  machine's T EXACTLY and write the machine's bytes (all but 12 self-modified operands, named and required
  to differ).  AB2: the pass charges the player as that T (`frameLedger().aa60.player`), the enemies still
  at their medians.  FOUND BY AB1 (AB3): `$AED1` with the eight-bit D = Y+15 below `$18` is `$AED7` --
  `LD HL,$712F / XOR A / RET` -- and the port read the colour shadow's top rows, so a player wrapped to Y < 9
  LANDED on the ceiling where the machine lets it fall on through; probeCell and hBlocked now follow the
  arm (22 rows had shown it as T).  MOVED: BT3's late odd windows 22..39 -> 11..28 (1P) and -26..-16 ->
  -27..-17 (2P), the player's 11 T of contention now outside the median; SFX5 and HB10's play scene had
  their phase from the ledger and lost it -- both now SEED it from the machine (TRAPS #271; SFX5 as near the
  machine's crossing as one main-loop pass allows).  The M7.68 battery's one survivor (the divert flag,
  report-only) killed by AC4b (TRAPS #272).  One Sonnet review: every BB_AB38 constant it recomputed (~80) matched the disassembly, adaaT's tree and the $AED7 fix confirmed; noted: AB1 checks the bytes the machine wrote, so an EXTRA engine write is not caught (DECLARED); the BB_AB38 comment's counts were stale (fixed); HB10 is weaker than its 'nothing chosen' form (declared, TRAPS #271).  127 new cases (three dropped
  as equivalent or unreachable, named in the list), 29 re-aimed.  Battery: FULL: 3,879 cases, 3,878 killed (169.0 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; the M7.13 case three failures then a hang, as before); the one survivor, "M7.47fix a blocked crossing returns the in-cell BC", had been killed only by the shadow misread M7.69 fixed -- three cases of the $AED7 arm BLOCKED ($710F solid), their BC measured by calling the machine's $ADAA, now kill it (re-run alone).
  bb.test 1,631 -> **1,634**; kit 120/120; selftest 34/34; romscan clean; `ab38cost.py verify` MATCH.

- [x] **M7.68 -- THE ISR'S T: THE 41 T ACKNOWLEDGE, AND $AA60 SLOT BY SLOT (2026-10-01, PK7).**  The ledger
  charged each interrupt its `$8D72` bracket and left out the 41 T before it (the IM2 response 19, `$FFFF`'s
  JR 12, `$FFF4`'s JP 10), and charged `$AA60` a flat 8,381 T (`BB_ISR_ABSENT_AA60`, round1_48's median)
  whatever the population.  Now `BB_ISR_ACK` is charged on every interrupt (the span test takes it back out:
  `BB_INT_PHASE` is the `$8D72` entry), and `$AA60` charges itself: `tools/aa60cost.py` (new) brackets it
  slot by slot on all 48 48K saved states (300 frames, contended, a key script; 5,974 passes tile), and
  the skeleton -- `BB_AA60`, the instruction sums -- is EXACT on every slot of 134 recorded passes (AC1,
  29 classes; three FORCED rows for paths no natural run reached: P2 tracking, a corpse whose delay still
  runs, a Y at or past `$DC`).  The handler runs and corpse flights are charged their fixture MEDIANS
  (`BB_AA60_RUN`, `BB_AA60_CORPSE`: PROVISIONAL, AC2, reported as `frameLedger().aa60`, an unpriced handler
  counted -- AC4).  The diverted pass is its instruction sums (`BB_AA60_DIVERT`), exact on 504 uncontended
  passes where a fitted BASE 165 stood (AC3).  AC5: the span law at the frame edge.  MOVED: BT3's even
  interrupts exact (were -41), late odd 22..39 / -26..-16 T (were +4,070 / +2,237), drift 605 / 1,421 T (was
  17,966 / 8,057), the 2P hand-off's ISR count the machine's again; HB4's ledger within 12 T at all 42
  interrupts (HB14 14 T; its bound 2,000 -> 20), its drift rows now the stamps' own (TRAPS #270); RA's
  costs exact (were "41 T short"); PK7's corpse tick -252 T (pop still 8,431 short, pinned).  FOUND: two
  gates stood round1_48 up without its wake-up delays (TRAPS #269).  One Sonnet review (the ledger is shared
  machinery): every `BB_AA60` / `BB_AA60_DIVERT` constant recomputed from the disassembly and confirmed, the
  span law confirmed, no vacuous row; ONE finding, fixed -- isr() did not clear the `$AA60` split, so an even
  frame's `frameLedger().aa60` reported the last odd pass (AC4 now reads the even interrupt after it).  41 new
  cases (four survivors in the first subset -- the P2 track, the corpse-awake path, the high Y, the span --
  killed by the forced rows and AC5), 17 re-aimed.  Battery: FULL: 3,771 cases, 3,770 killed (160.2 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before); the ONE survivor, "M7.43: RA2 divert flag never reset", lived because the flag no longer moves the cost -- it is only reported -- and no row read the report: AC4b (new) reads it on the even interrupt after a diverted one, and kills it (the case re-run alone).
  bb.test 1,625 -> **1,631**; kit 120/120; selftest 34/34; romscan clean; `aa60cost.py verify` MATCH.

- [x] **M7.67 -- THE FIRE ELEMENTAL (2026-10-01).**  `fireArm` and `fireManager` were counted stubs: a fire
  bubble popped and nothing fell -- the last two elemental stubs.  Now `$93FD` (the arm: refused while
  `($9F64)` is set, else the phase := 1 and the drop at `(($FFF7)+8) AND $F8`, `(($FFF8)+15) AND $F8`, both
  EIGHT-BIT adds) and `$9F63` (`fireManager`: its phase is its own operand `$9F64`, which `$9E64` has
  already stepped this tick): the drop erased from the backing store (`fireScreen` `$9FE0` through the row
  table at `$FD00`, `fireRestore` `$9FF6`), then `fireFall` (`$A00D`: Y + 8 eight-bit, gone at `$BF`, the
  glyph `$B624`) or `fireLand` (`$9F8F`: four steps each way through `$9FC8` -- the next cell floor, the
  one above it open -- counted in `($FDF2)`, the left limit's screen address walked by an eight-bit DEC L in
  the alternate set and stored in `($FDF0)`; phase `$2A`), `fireBurn` (`$A04E`: the phase stored, the frame
  `$A39D` / `$A3A5` by bit 3 written into `$A074` -- the operand of `$A073 LD DE,nn` -- the count clamped
  to at least 1 and written back, the flames, the `$42` attributes) and `fireEnd` (`$A030` at `$FA`: the
  cells restored, the attributes `($8309) OR $40`, the whole byte).  The burn steps the phase by TWO a
  tick, `$2C` to `$F8`: 103 paints, 208 frames.  MEASURED by `tools/fireman.py`: 1,539 arms at their own
  entry on elfire, 1,366 manager calls at their own entry (every phase byte, every count 0..12 in both
  frames and at the end, the drop at every X and every Y on elfire and on a built floor), 59 CONTINUOUS
  runs (the arm, then `$9E50` every frame until the fire is gone: a 4 x 4 grid of pops on elfire; built
  floors -- a full one, where the spread's search is the identity; a gap and a wall at distance 1..5 each
  side; both edge columns; the left spread past column 0 on rows 0, 8 and 12; an open field; a solid
  spawn cell; the Y wrap; an immediate landing; the X wrap; the bottom row) and every natural `$93FD` /
  `$9F63` entry of 300 idle ISRs of elfire, 300 of firekill (a fire alive) and 400 of elfire with a fire
  request poked in (453 calls).  Gated FM1..FM4 (the water block's judge: every display write in order,
  every other byte's final value, no extra write, no MISSING write, no read the fixture did not seed).
  Found on the way: the row table at `$FD00` is not the screen's -- rows 0 and 1 hold `$01FF` and rows
  24..31 `$0000..$00E0`, so a drop erased there writes into the ROM and the port must drop those writes;
  past column 0 the flame row's screen address wraps inside its own third's page (`$48FF` from row 8,
  `$40FF` from row 0) while the shadow walks back a row; and the ORACLE's own fault -- `run_call` left SP
  ten bytes lower per call, so after 230 calls of a continuous run its sentinels landed on `$8DBD` (TRAPS
  #268; `tools/waterstream.py` fixed too, `verify` still MATCH).  63 mutants, all killed in the subset.
  Battery: FULL: 3,730 cases, all killed (161.8 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before).
  bb.test 1,617 -> **1,625**; kit 120/120; selftest 34/34; romscan clean; `fireman.py verify` MATCH.

- [x] **M7.66 -- THE WATER STREAM (2026-09-30).**  `waterArm` and `waterStream` were counted stubs: a water
  bubble popped and nothing flowed.  Now `$9460` (the arm: two refusals, then the pop's `($FFF7)+8` and
  `($FFF8)+9` -- EIGHT-BIT adds -- as an attribute address) -> `$A15F` (`waterSeed`: `($A1AA)` := the
  WATER_DIR draw, `($A15A)` := 1, a 22-cell scan down the shadow, `LD HL,9` when none is open, SEVEN band
  words), and `$A159` -> `$A190` (`waterAdvance`: down first, then sideways, the direction reversed only by
  a blocked sideways step), `$A1C6` (`waterStep`), `$A208` (`waterDrop`) and `$A21F` (`waterRide`).
  MEASURED by `tools/waterstream.py`: 2,051 arms at their own entry on elwater (every `($FFF7)` and
  `($FFF8)` byte, on elwater's shadow and on an open one), 40 continuous runs (one arm then the tick until
  the stream stops: a 6 x 6 grid of pops, an open field, a row-0 corridor into the bitmap, a row-23
  corridor through `$5AFF` to `$5B00`, a one-cell pocket; carry gates and `($8309)` varied) and all 348
  natural `$9460` / `$A159` entries of 700 idle ISRs of elwater.  Gated WS1..WS3 (every display write in
  order, every other byte's final value, no extra write, no MISSING write, no read the fixture did not
  seed; the R byte fed).  Found on the way: SPEC's summary missed the HEAD-past-`$5AFF` path -- it lets the
  riders go (`$A208`) but the stream runs on; only the tail stops it.  70 mutants (one old B6 case
  re-aimed); the first subset left nine survivors -- three EQUIVALENT (an LDDR of 16 bytes lands its extra
  two under the head store; `$A21F` rewrites `$A259`/`$A25A` after every `$A208`; only H's low two bits
  survive the SRLs, so AND 7 = AND 3) and six real gaps: elwater's column 0 is a WALL, so a column add
  that ran on to 32 scanned the same wall to the same cell (open-shadow arms added, TRAPS #267); `($8309)`
  never had high bits; and the row-23 world opened the margin below the file, so the head fell off
  instead of walking through the two limits' exact cells.  Battery: FULL: 3,667 cases, all killed (146.5 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before).
  bb.test 1,611 -> **1,617**; kit 120/120; selftest 34/34; romscan clean; `waterstream.py verify` MATCH.

- [x] **M7.65 -- THE LIGHTNING BOLT'S ENEMY KILL (2026-09-30).**  `boltEnemyScan` and `boltCorpse` were counted
  stubs: a bolt never killed an enemy.  Now `$9EA6..$9ECE` (the scan: `($AA57) - 2` slots from slot 2, any
  bit-7 slot a target -- a corpse too -- the last hit wins), `$9F18` (`boltNear`, the eight-bit window) and
  `$9EFE` (`corpseBirth` of the record less 5).  MEASURED by `tools/boltkill.py`: `$9E90` at its own entry on
  155 built r20_48 worlds and the 24 live bolts of 120 idle ISRs of ellight (4 kills: ISRs 22 and 46, and
  the re-kills of the same corpses at 24 and 48), and `$9F18` for every bolt byte against every aligned
  enemy byte, aligned or not.  Gated BK1 (the comparator's 65,536 answers), BK2 (all 179 calls: the record at `$9ED0`, the
  slot handed to `$8BC2`, every non-display byte written, and no other), BK3/BK3b/BK3c (the last hit wins;
  frozen and corpse targets, the count, the despawned hits, the wraps; the re-kill).  One row claimed a
  kill at the top wrap where the fixture showed a hit the move carries past `$E7` -- the row was wrong
  (TRAPS #216), fixed to say so.  30 mutants (one old B6 case re-aimed); the first subset left five comparator
  survivors -- four PROVABLY EQUIVALENT (after the ANDs, `a - 15` is 1 mod 8 and `a + 15` 7 mod 8, so `-16`,
  `$1D` and `>` for `>=` cannot differ; replaced by `-23`, `$16` and inverted compares), and one real gap: the
  table held aligned enemy bytes only, so dropping `$9F1A`'s AND survived -- widened to 256 x 256, with two
  unaligned-enemy scan worlds (TRAPS #266).  Battery: FULL: 3,599 cases, all killed (143.5 min on 20 workers, 0 dead or ambiguous anchors, 0 timeouts; one M7.13 case killed by three failures and then a hang, as before).
  bb.test 1,606 -> **1,611**; kit 120/120; selftest 34/34; romscan clean; `boltkill.py verify` MATCH.

- [ ] **NEXT.**  The front end is READ (M7.37), and **A**, **G**, **GROUP 1** and **GROUP 2**
  (M7.38..M7.42) are built; the page boots to the title.  In order:
  * ~~The round advance's drain, RA1..RA4~~ -- CLOSED by M7.43.  Left from it: the in-play odd
    ISR's $A3AD draw is charged 12.4k..21.3k T short, and the ISR is 41 T short everywhere.
  * ~~GROUP 3~~ -- WIRED by M7.64: the page loads through the full menu.  (History:) H-a, the control-select screen, was BUILT (M7.53) and UNWIRED: it was
    decision 2b's flag-ON path (`flags.originalMenu`, default OFF).  **H-b** -- the key read
    `$F7B3`, the menu, the dispatch, the presets and the key-table builder -- is BUILT (M7.61) and
    unwired too, **H-c** -- the redefine screen -- is BUILT (M7.62) and unwired, and **H-d** -- the load
    spine, `$FAC3`, the hand-over and the `$9601` key copy -- is BUILT (M7.63) and unwired.  Next the
    WIRING (M7.64): the page loads through the full menu (the owner's decision), `step()` delegates to
    `ctrlStep()`, and a named Kempston flag keeps a gamepad off the faithful path.  With it, the input layer -- and a DECLARED flag for starting from a joystick, which the
    machine's title cannot do (it reads only half-row `$F7`).
  * ~~THE POP KILL~~ (M7.45), the key caption (M7.46), the risen-bubble drift (M7.47), the player
    interleave (M7.48), `$A431` (M7.49), the one-left anger (M7.50), `$8C51` on a live enemy (M7.51),
    the 48K beeper layer (M7.52), the HURRY UP! block in time (M7.54), the enemy projectiles (M7.55)
    the round banner in time (M7.56), EXTEND's completion in time (M7.57) and the storm's flash tick
    in time (M7.58), the round build's scroll-in (M7.59) and the fireball's spawn with the storm
    payload in time (M7.60) -- CLOSED.  Next: (was the ROUND BUILD's scroll-in) which lands inside one call too and so is never seen; the lightning bolt's
    enemy kill `$9EFE` (its scan `$9EA6..$9ECE` and corpse call are counted stubs, so bolt kills never
    happen -- unread code: a recon agent); and the ISR T for a pop, a corpse tick and the in-play
    `$A3AD` draw.
  Still outstanding from earlier: `$8306`'s half-painted map (not yet asserted); the four
  self-modified bytes `$ADA1`/`$ADA2`/`$AD41`/`$AD42`.  (The beeper emitters are CLOSED by M7.52
  but for the key click, which is group 3's.)  (BB_CHAIN has no null entries: all nineteen run.)

- [~] **PARTLY CLOSED by H13-B0..B11 -- the main-loop chain `$8D25-$8D5E` IS
  WIRED, and EIGHT of its twenty calls run in the built page**: `$A9ED` (the
  boss tick), `$9961` (the mid-game join), `$915F`, `$93DC` (the element arm),
  `$9E50` (the element tick), **`$A09A` (the effect manager -- B10 read the
  last genuinely dark range and it was never "lightning")**, `$C002` (the
  sparkle) and `$8669` (the collect).  The remaining ELEVEN carry a method name
  of `null` in `BB_CHAIN`, so "transliterated" and "wired" cannot drift apart
  silently: `$8FA5` jumpSFX, `$8FE7` pause, `$900B` shootGate, `$948F`
  extendDone, `$7E80` elemEmit, `$A824` giant (B11 corrected its negative and
  found a SECOND CP-form edge detector in it, `$A82D`), `$9037` hurryTrig,
  `$925A` player+enemy (B11 took its `$9269`, the second caller of `$927D`),
  `$931A` envKill, `$9AEB` and `$8E2A` (B1, transliterated and gated but
  deliberately unwired until the front end puts a player in play).
  `$8E3A` is the loop's own branch and is not in the list.
  **AND B11 NAMED THE NEXT OWNER**: the 80 -> 81 differential stops exactly at
  the round advance, because `$97F8`'s counter arithmetic is transliterated and
  the round BUILD it leads to, **`$8C5E`**, is not.  The twenty fields that move
  across that row are recorded in `build/bossround_fixture.json` as the work
  that increment inherits.
- [x] **CLOSED by M7.3c (2026-09-22) -- and THE FRAMING BELOW WAS WRONG:
  there is no entity colour pass, because NOTHING paints entity colour.
  The round asset's attribute third held the COLOUR SHADOW and
  renderFrame() copied it over the attribute file at every reset.  The
  enemies inherit the playfield palette.  Kept verbatim below because the
  structural point at the end of it is the one that mattered, and it is
  now TRAPS #92 and a gate.**
- [x] **WAS OPEN -- ENEMIES ARE DRAWN BUT INVISIBLE: no entity COLOUR pass.**
  Found by the owner looking at a filmstrip, not by a test. The entity sprite
  banks were missing entirely (fixed, `build/entity_sprites.json`), and the
  enemies now blit -- measured, 27 bytes at x=120 across y=72..87 where it was
  zero before -- but the attribute cells under them hold `$00`: ink 0 on paper
  0, black on black. The machine's own round-1 plate holds `$47` there, BRIGHT
  WHITE on black, and the round render asset is the clean platforms-and-HUD
  frame, which does not carry it. So something paints entity colour and the
  engine does not model it. Small and well-defined; it is the last thing
  between the port and looking like Bubble Bobble.
  AND THE STRUCTURAL POINT: 293 checks passed over a screen with nothing on it.
  Every gate here drives the engine from a captured world and compares RAM;
  not one of them ever asks whether anything is VISIBLE. That is a blind spot
  in the approach, not a missing test.
- [ ] **OPEN -- the ITEM SPRITE BANK `$5D00` is RUNTIME-BUILT and its builder is unfound.**
  `build/image_tape.bin` is ALL ZEROS from `$5C00` to `$6100`: no tape block
  covers those pages, so the bank is not tape data. It is byte-identical in 54
  of 57 saved states, differing only in `boot` and `title`, so it is built during
  the FRONT END; and zeroing it in a live round-1 state produces zero writes back
  over 200 frames, so nothing rebuilds it in play. Carried as a declared asset
  meanwhile. The project's precedent says BUILD it -- `$D380` is runtime-built by
  `$BF5B` and deliberately not an asset -- so when M7.8 reaches the front end,
  find the builder and DELETE `build/item_sprites.json` rather than keeping it as
  a cross-check. (TRAPS #43.)
- [ ] **M7.3b follow-up -- per-entity draw-pass erase.**  Once entities MOVE,
  replace the full row 2-23 restore with the original's per-entity erase from
  the shadow at the previous `+2/+3` position, then blit at `+5/+6` (the
  harness does a DIRTY-CELL restore, measured 2026-09-10: cells no sprite
  touched are never rewritten).  Gate: a moved-entity frame == harness, and the
  even-frame pass VARIANCE (5-7) emerges from the real per-entity draw cost.
- [~] **M7.4 -- player** (walk/jump/fall/land/blow, the input reader `$AC0E`
  + the key tables; SPEC "Player physics/controls").  Differential sampler.
  M7.4a (WALK) + M7.4b (JUMP/FALL/LAND) + M7.4c ($ADAA horizontal collision +
  in-air steering) + M7.4d-i (fall-off-edge, physics dispatch, free-fall
  cadence) + M7.4d-ii (BLOW: cadence, spawn, the slot-split bubble schedule,
  travel, rise) + M7.4d-iii (death, lives, respawn, invulnerability, the hurry
  reset) + M7.4d-iv (two players, the P2 join) DONE above -- M7.4 COMPLETE;
  the '2'/key decode and the P1 new-game start are M7.8 input/front-end items.
- [ ] **M7.5 -- bubbles** (pool `$FED8`, blow/travel/drift/pop, the contact
  rule `$B8E5`, capture `$BE5B`).
- [x] **M7.6 -- enemies COMPLETE**: spawner, the `$AA60` pass, the shared
  walker, the ballistic hop, all EIGHT handlers, and capture/escape.
- [ ] **M7.7 -- items/score, round transition + the endgame loop, hurry-up +
  Boris, boss + WELL DONE ending + round-81 treasure room.**
- [ ] **M7.8 -- front end** (title/attract/options/redefine/high-score) +
  the input layer (keyboard faithful path + the declared controller layer).
- [ ] **M7.9 -- sound emitters** (the 7 beeper emitters from `build/sfx/*.json`
  via `cmp_sfx`/`sfxgate`) + RNG (`$FE85` exact; `LD A,R` substitute flagged).
- [ ] **M8 differential proof** runs alongside from M7.2 (per-frame RAM diffs
  from fixtures, per-routine trace diffs, framediff).

## Gotchas already paid for

- The clean frame must come from the SHADOW, not a raw display capture: a
  display grabbed after zeroing entities still holds residual sprite pixels
  (148 stray bytes, row 10 worst) until the shadow is restored over them.
- `SpecScreen.m` must be re-pointed to the ram view AFTER construction
  (`this.scr.m = this.ram.subarray(0x4000, 0x4000+0x1B00)`).
- The kit's last self-test block (loop/sound-bridge) drives the page engine,
  so it now drives `P.game`; it was rewritten as the M7.0 game-integration
  check (frame stepping + the bridge tracking `simFrame`).
