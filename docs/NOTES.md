# Provenance record — Bubble Bobble (ZX Spectrum) port

Kit: `E:\Software\Spectrum-Port-Kit` at commit `163cf61894a61688036589d4fa4cb1d7d3a2c967`
(2026-09-02, "The kit's briefing: README and CLAUDE.md"). Tool changes made here that are
game-agnostic are listed under "Upstream" below so they can be diffed back.

## 8.20 decision checklist (manual §8)

| Item | Answer | Settled by |
|---|---|---|
| Tape protected/packed? | Yes: Firebird Bleepload, custom loader with tail code in every block → snapshot route; R3 partly recovered by `tools/bleepload.py` | M1 |
| Ports touched? | reads: keyboard rows `$FE` only. writes: `$FE` x1356 (beeper+border) and low-byte `$FD` x1350 = `$7FFD` paging + `$FFFD`/`$BFFD` AY (the kit battery collapses the high byte). No `$1F` in 1P. | M2 Q2 DONE |
| Self-modifying/decrypting? | YES: 77 (writer,target) pairs patch executed operands per run ($A432->$A431 x3980, $9E58->$9E57, $A09F->$A09E, $8681->$8680, $925B/$9279->$92DE, ...). Per-transition differentials MUST treat patched bytes as state (G4). | M2 Q3 DONE |
| ROM called at runtime? | Yes in the FRONT END: `RST $38` (keyboard/FRAMES), `ROM_BEEPER $03B5` (key click, HL=$320 DE=2), `RST $10`/CHAN-OPEN (text), and the `$FAC3` machine probe runs under the ROM's IM 1 FRAMES counter. Gameplay: NONE (IM 2, 0.00% of play instructions in ROM); the ROM FONT bytes `$3D00+` are read for text (substitute-font departure). | M1; M2 Q4; M6 2026-09-09 |
| Loader-left state? | PC=$F5BC, SP=$61A7, IM 1, IFF 0 (DI), I=$3F, border 5, BANKM copy at $6000; full record in docs/LOADER.md | M1 done |
| Clock model? | IM2 ISR $8D72 locked to 50Hz (69888 T, exactly 1/frame, 0 missed even under load). Gameplay main loop FREE-RUNS (7 passes on draw frames / 11 on bubble frames in idle round 1, re-measured on the 48K branch 2026-09-09). The ISR is the RENDERER: odd frames = entity draw pass $A3AD (~27k T), even frames = bubble pass $B62C -- the "0.45-frame music" of the first reading was this draw pass (SPEC Clock). | M3 Q10 DONE; corrected 2026-09-09 |
| Frames dropped on overrun? | The ISR never overruns a frame (max 0.45) and 0 interrupts are missed, so NO video frames drop. Slowdown = fewer main-loop passes/frame when busy (free-running); a per-pass-T engine reproduces it, so decision 3's declared gap looks UNNECESSARY. OPEN: magnitude at true screen saturation (my bubble-spam did not saturate). | M3; confirm at saturation |
| Per-path pass costs? | Per-routine costs in the $8D25 chain measured (tools/chaincost.py): common pass sum-of-medians ~5800 T; the long pass is $931A ($9037? draw) and $925A spiking to ~28-42k T. The apparent bimodality is the alternate-frame ISR DRAW-pass cost ($A3AD, corrected 2026-09-09 -- not sound), not the main loop. Full per-path model needs M5 routine reading. | M3; M5 |
| Hot code below $8000? | No: 0.33% of play instructions (a 3-instruction loop at `$7E80-$7E84`), 0 in ROM; the round builder `$7F62/$8260`, enemy spawner `$72A5/$72F0` + type table `$73B0`, spawn table `$7491` and the elemental scan `$7E04-$7E4B` live in contended RAM but run only at round start. Per-frame hot code is `$80xx-$BFxx` + the ISR draw pass `$A3AD-$A7xx`. | M6 2026-09-09 (profile of round1_48) |
| Render model? | FRAMEBUFFER, MASKED blitter: the draw inner loop ($A651) is LD A,(HL)/AND E/OR D/LD (HL),A -> sprites are mask+data interleaved (Q15a). NO collision-by-screen: every display-file READER is in the $A5xx-$A7xx blitter cluster (read-modify-write), so the physics reads a SEPARATE map, not the screen (Q15b). | M4 Q15 DONE |
| Level format? | 81 rounds (round 81 = boss room) of packed per-row segment records at `$61A8`, 39 or 77 bytes each chosen by the size-flag bitmap `$8543`, walked sequentially by the round counter `$8609` (`$848C`); rendered by the builder `$7F62` into the shadow `$E000+` with the per-round platform tile `$856C` and the computed 15-round palette. Shipped as LIVE-extracted geometry + colour (tools/extract_rounds.py, build/rounds*.json), the packed segment scheme itself left undecoded (low). | M4/M5 DONE |
| Coordinate origins? | blitter draws via HL display-file addresses (AND/OR), 2 bytes wide x N rows ($A64F LD B,2 / DJNZ). Per-draw-routine origins to pin in M5. | M5 |
| Camera / scroll granularity? | No camera: one fixed 32x22 playfield per round. The round advance (`$97F8`, level-clear `$8ED4+` when the last corpse settles) rebuilds the next round through the builder + `$8216` full restore; corpse drops persist across it (SPEC "Round transition"). | M5 DONE |
| Random source? | **CORRECTED 2026-09-10 -- see docs/RNG.md (the E1 decision record).** PRIMARY = `$FE85`, a deterministic self-modifying PRNG (state `$FE86/$FE87`), seeded `$002A` FROM THE TAPE IMAGE and **never reseeded** (the sole writer over a full game start + 1.6M instructions is its own write-back). It is NOT seeded from R: `$FEBB`/`$FEC7` are not seeds (they are an instruction operand and the next-round lookahead). Per-session variety comes from the attract loop spinning the PRNG 185-304x/frame while the human waits to press start. Exactly **11** `LD A,R` sites, 0 `LD A,I`, 0 `LD R,A` (so R is 7-bit: 0..127, and both `CP $2A` checks are **1/128**, not 1/256): `$7E04 $873E $8A2E $8A38 $9715 $9811 $A15F $B008 $B0D5 $B88D $FEAC`. Engine: transliterate `$FE85` exactly; R-reads = declared per-site substitute with frame-keyed injection in tests (E1 DECIDED). | M2 Q18; M5 DONE; E1 2026-09-10 |
| Sound? | SETTLED 2026-09-09 (SPEC "M6 sound"): the machine is decided by a TIMING PROBE ($FAC3, accepted counts $075E/$0763 = 48K). 48K branch = NO music, no engine, 7 inline beeper SFX emitters (collect chirp $8CB1, jump tone $8FA5, blow clicks $ACAF, HURRY UP clicks $9062, letter click $B790, lightning flash $A0A3, pause $8FE7) + the front-end ROM-BEEPER click. 128K branch = the AY engine copied from $E6A8-$F5BB into bank 1 $C350 (M10). The M2 "beeper+AY together" measurement was of the 128K branch (key held during the probe). | M6 census DONE |
| Reference disassembly? | None found (Q6) | plan |
| BRIGHT / FLASH / attr owner? | round-1 census (768 cells): $47 bright-white-on-black x525 (sprites+round no.), $57 bright-white-on-RED x206 (the candy-stripe platforms: stripes are bitmap, paper is red), HUD dim $04/$02/$05 (1UP/HIGH-SCORE/2UP). BRIGHT heavy, FLASH never. Per-round platform colour varies (M4 to census more). | M4 Q16 DONE (round 1) |
| Paging / multi-load? | one load; 128K-aware via the $FAC3 timing probe (NOT BANKM -- $5B5C→$9AE7 via $95F5 is only the paging value OR'd with 1 for $7FFD); the 128K branch copies its AY engine into bank 1 at game start ($967E); no runtime tape loads (a developer extra-load path at $5BBE is unused) | M1 Q8; corrected 2026-09-09 |
| Hand-written Z80? | Yes | M1 |
| Scope of "faithful"? | Decided; see README | — |

## Routine map (address → behaviour → function)

_empty until M5_

## Assumption / reality / caught-by

| Assumption | Reality | Caught by |
|---|---|---|

## Open questions

- RESOLVED 2026-09-09: **which sound path a real 48K takes** -- decided by the `$FAC3` timing
  probe, not BANKM; the harness reproduces the 48K count (`$075E`) when no key is held through
  the probe (TRAPS #28; SPEC "M6 sound"). The pre-2026-09-09 harness play states are 128K-branch.
- RESOLVED: the loader's rolling-XOR decryption of `$6100-$70FF` and the driver tail is reproduced by the kit's validated `bleepload.py` (key page `$C900` XOR the stub pages); the tape-vs-snapshot diff is now unattributed 0 with only 8 non-display bytes differing, both named (docs/LOADER.md).

## M2 outcomes (reached live play)

- Front end mapped: control-select per player (1 KEYBOARD / 2 SINCLAIR / 3 KEMPSTON /
  4 CURSOR), then key-redefinition if keyboard, then the title "1 OR 2 TO PLAY" ($8CC3
  attract/starfield loop), then '1'/'2' starts a 1P/2P game. Uses IM1 + RST $38 keyboard.
- Saved states: title.pkl (P1 control menu), afterctrl.pkl (title), play1p.pkl, play2p.pkl
  (round 1, 1P and 2P). Entry gameplay via cursor(P1)+kempston(P2) to skip redefinition.
- Direction asserted: P1 cursor RIGHT($8) raises $FD83, LEFT($5) lowers it (G2).
- 2P battery (play2p, 400 frames): Q2 now reads `$1F1F` x800 -- the Kempston port IS polled
  for P2 (P2 chose KEMPSTON); Q10 mean 10,706 T/pass (0.153 frames, vs 8,225 in 1P: two
  players cost more per pass); Q16/Q17 as 1P.
- Q18 RNG (SUPERSEDED 2026-09-10 by docs/RNG.md -- the sweep below missed live firings; `$B0D5`
  fires 22x in 400 idle frames of round1_48, and `$FE85` draws 240x in the same window):
  the original note read: ZERO executions of any `LD A,R` site ($A15F/$B008/$B0D5/$B88D/$FEAC) in 1.2M
  in-game instructions. R is read only at game start ($9715: AND 7 -> $FEBB; $9811: AND $1F
  + $1E -> $FEC7). The play-time generator is RAM-based -- find it in M5 by tracing an enemy
  turn decision. Good case for the port: reproducible exactly; only the start seed is ours.
- Q19 (`tools/stackscan.py`, new, 300 idle frames): 59,458 calls, 59,456 balanced, **0
  imbalances** -- no caller-abandoning RET fires in idle round-1 play (death / round-clear
  must be scripted to expose theirs: run it again across those events in M4/M5). 18
  COMPUTED-RETURN sites (RET used as a jump via a pushed address: $93E8 x1299, $AAEA x432,
  $8DA1 x294 (in the ISR), $AF46, $AAB5, $B678, $AD50, $AB0B, $AAFB, $B25C ...) -- the
  dispatch idiom to read in M5.
- Still OPEN: complete varmap (score, lives, round address, P2 struct stride -- M5, and the
  round counter by reading the round loader in M4); Q14 which-way-up (M4); the round
  scroll-in mechanism (M4).

## M3 outcomes (timing)

- **Clock, settled**: gameplay is free-running (no HALT); the IM2 ISR at $8D72 is the only 50Hz
  tick, firing exactly once per frame (69888 T) with 0 misses in every test incl. a busy screen.
  The main-loop chain ($8D25-$8D61) runs ~6.2 passes/frame (M3, 128K-branch state); re-measured
  2026-09-09 on the 48K branch: 7 passes on entity-draw frames / 11 on bubble frames (idle round 1).
- ~~**Sound is ISR-driven** ... parity-1 branch runs the music every OTHER frame at ~0.45 frame~~
  WRONG (corrected 2026-09-09): the alternate-frame ISR cost is the ENTITY DRAW PASS `$A3AD`
  (odd frames, ~26.7k T), with the bubble pass `$B62C` on even frames -- identical on the 48K
  branch, which has no music. The sound hook `$8DC4` runs after both (a RET on 48K; the AY
  engine tick on 128K costs ~0.1-1.3k T). No jingle delays the round start on either branch
  (entities live +17 frames after '1' in both). See SPEC "Clock" and "M6 sound".
- **Walk speed**: P1 X advances +2px every 2 frames = ~0.98-1.00 px/frame = ~50 px/s; ~5.1 s to
  cross 256px (the human-scale cross-check; sane for Bubble Bobble). Q12 player divider = 2 frames.
- **Slowdown**: no dropped video frames (ISR always fits, 0 missed). The visible slowdown is fewer
  free-running passes per frame under load -- reproducible by charging per-pass T-states, so the
  fixed-step "declare it a gap" plan (decision 3) is probably unnecessary. NOT yet measured at true
  saturation (the bubble-spam test only put 3 enemies on screen); revisit with a saturated round.
- New tool `tools/chaincost.py`: brackets every CALL in a dispatch chain and reports per-routine
  T cost + modes over driven play (phase 9 / Q11), no variable map needed.

## M4 outcomes so far (data + ground truth)

- **Render model fully pinned (Q15)**: framebuffer; the sprite blitter at $A651 is
  `LD A,(HL) / AND E / OR D / LD (HL),A` -- MASKED, so sprite assets are two interleaved
  streams (mask, data). Gameplay never reads the display file for collision (all readers are
  the $A5xx-$A7xx blitters doing read-modify-write), so there IS a separate tile map / entity
  data -- extraction has something to decode (not a pure framebuffer game).
- **Colour (Q16)**: round-1 ink-to-meaning -- bright white sprites on black; platforms are
  bright white ink on RED paper (candy stripes live in the bitmap); HUD dim green/red/cyan.
  BRIGHT used throughout, FLASH never. The renderScreen BRIGHT palette swap is needed.
- **Ground truth**: round1.pkl (settled round 1) + shot_round1.png captured (harness route A).
- **Level map -- LOCATION STILL OPEN**: the map is a separate structure the physics reads, but
  I have NOT pinned its address. A readwatch pointed at $9600 was code-fetch noise ($9600-$97FF
  is the new-round init routine, not data) -- recorded so it is not repeated. Finding the map
  needs the collision routine read in M5 (which data address it indexes from the player's
  position); THEN static extraction + the live cross-check by poking the round counter (Q7).
  The round counter is also not yet located ($8609 is the title/demo cycle counter, not it).

## M5 start (routine reading) and a CORRECTED level-format hypothesis

- **Entity table**: base $FD80, **12 slots x 10-byte stride** ($FD80-$FDF7); iterated by
  `LD IX,$FD80 / LD DE,10 / LD B,12 / ADD IX,DE / DJNZ` ($8F00). Players are slots 0 and 1
  ($FD80, $FD8A); slots 2-11 are enemies/bubbles/items. 11 routines take `LD IX,$FD80` each
  with a `$FD8A` P2 twin ($925E/$926C, $9339/$934D, $949B/$94A2, $9826/$9836, $9B0E/$9B1A,
  $A979/$A971, $BD2C/$BD33, ...). A parallel per-slot field is addressed at `(IX+$5A)`.
- **CORRECTED (Q7)**: the level is **NOT a 32x24 tile grid**. With the player walking, the only
  hot data reads (instruction fetches filtered out, tools/dataread.py) are the 10 bytes
  **$96D1-$96DA** -- five 16-bit per-entity scratch words, loaded via the SP-parked fast-pointer
  idiom (POP / RET / EX (SP),HL with SP set to the block; manual 3.10; corrected below, and
  now shown as stack-class reads by dataread) at $92FC/$9302/$9F61/$93C3/$9319/... , plus
  $96BB-$96BE for the draw.
  There is NO tile-map lookup and NO display-file read-back, so collision is against a COMPACT
  per-round platform description, not a grid. The plan's "bit-packed 32x24 maps" assumption is
  downgraded. Candidate per-round reads to chase in M5: $8696 -> $9605/$9607/$9609 (once/frame),
  $9041 -> $745C/$745D.
- **M5 KEYSTONE FOUND (docs/SPEC.md)**: round counter `$8609`; level data base `$61A8`,
  variable-length records (39 = symmetric / 77 = full 28x22 grid) via the size-flag bitmap
  at `$8543`, selected by `$8609`; builder `$8260` draws the platform tile `$856C` into a
  clean platform-layer shadow buffer at `$E000-$F7FF` (=display+`$A000`; the playfield is black + striped platforms, no scenery), restored to the display
  each frame by `$8216` (row table `$FD04`) with sprites composited on top. Round 1 = 39
  bytes, decodes to a plausible symmetric map. OPEN: exact bit->cell order, round count,
  per-round colour, full 100-round extraction + closure/live cross-check.
- **Superseded**: the round-draw routine note (draws the platforms at round start -> the
  per-round source data + the round-counter index), and the collision routine (how player Y/X
  map to "on a platform"). Then extraction reads the per-round data out of live RAM by poking
  the round counter (Q7 live path).
- New tool `tools/dataread.py`: logs data reads with instruction fetches filtered
  (addr not in [PC,PC+3]), so a map/table read stands out from code fetches -- the instrument
  that settled "no tile grid".

## Correction (play-report): the platform palette is PER-LEVEL

A player who knows the original flagged that each level has a different palette. Confirmed
there is a per-round colour layer (shadow colour buffer `$F800-$FAFF` -> display attrs via
the builder LDIR `$8245`); round 1 = red `$57` is just one example. RESOLVED: the platform palette CYCLES every 15 rounds (16-19 = 1-4); the 15 BRIGHT attrs are
measured in docs/SPEC.md and build/round_palettes.json, captured live by driving the game round
by round (extract_round_colours.py). The colour is COMPUTED (no stored table found); engine uses
the 15 measured values by ((round-1) mod 15). The exact code formula stays OPEN. Do NOT render
levels as fixed red.

## Own inventions (things the port does that the original does not)

- The keyboard+gamepad control presentation (declared; see README).
- The fixed 50.08 Hz step (declared; see README).

## Upstream (game-agnostic changes contributed back to the kit)

**Done — kit commit `689dbef`** "tools: the snapshot route for protected/custom loaders"
(self-test 29 -> 31, platform suite still 115/115). The kit now ships `simload.py`,
`snapimport.py`, a generic `bleepload.py` block decoder, `Harness(snapshot=)`, `boot.py
--state/--arm-at`, the `z80.snapshot/snapshot128/varmap` manifest keys and the `run_frames`
fix. A separate session then generalised and validated the kit's `bleepload.py` against thirteen titles on fourteen tapes (kit commits 7a9fd0b, 9c63daf): it now reads the buffer, the stub's load page, the group-1 key and the later-group XOR key off the tape, walks the driver for its copies and hand-over JP, and attributes every mismatching page. That tool has been synced back into this port (with the newer simload.py, harness.py and selftest.py, 32/32), REPLACING the port's earlier game-specific version.

**Done -- kit commit `c32f351` (M9.1, 2026-10-12):** `test/rig.js` -- `fire()` stops at `stopImmediatePropagation()`
as a browser does (TRAPS #340), and `test/kit.test.js`'s event-order check that holds it (kit suite 115 -> 116; the
stop removed by hand, the check fails).

**Done -- kit commit `3e81ac1` (M10.0a, 2026-10-13):** `tools/harness.py` -- `Harness(paging=$10)` / `enable_paging()`,
the opt-in 128K `$7FFD` port and AY on the 48K machine (the M10 layer's machine: the 128K branch on the 48K clock);
`tools/harness128.py` -- the 128K machine itself (the M10 recon's agent-B harness, its game hooks left here); selftest
34 -> 38, hand-mutated (the shim 11/11, harness128 15/15 after three test gaps were closed).

Original list (now landed upstream):

- `.gitignore`: snapshot extensions and dump directories.
- `tools/harness.py`: `Harness(snapshot=...)` and the `z80.snapshot` manifest key (the snapshot
  route, manual 6.1); `run_frames` uses `self.frame_duration` not the hard-coded 69888.
- `tools/boot.py`: `--state NAME` (resume) and `--arm-at ADDR` (the interrupt trap, 6.3).
- `tools/portconfig.py`: `z80.snapshot`, `z80.snapshot128`, `z80.varmap` defaults.
- New game-agnostic tools worth upstreaming once generalised: `simload.py` (tap2sna wrapper),
  `snapimport.py` (snapshot → harness image/state).
- `stackscan.py`, `dataread.py`, `chaincost.py`, `probeutil.py`: validated across Chuckie Egg,
  Chuckie Egg 2 and this game (`docs/probe-tools-test-report.md`); stackscan rewritten around stack
  slots (the old reconciliation could not fail and it missed `LD SP` deaths), dataread's gate given a
  range form and a stack-class list, chaincost an explicit no-chain verdict.  Upstreamed to the kit the same day (kit selftest
  33/33, mutation battery 6/6 on the kit copy).  Correction to M5 above: the `$96D1-$96DA` reads are
  `POP`/`RET`/`EX (SP),HL` with SP parked on the block (manual 3.10), not `LD`-class data reads.
- `tools/blitforensics.py` + `screen.bmp_coords` (2026-09-07): validated for the kit by a tape-free synthetic gold
  gate (three poked blitters: masked AND-OR, opaque, XOR; recovered cell for cell; 4/4 gate mutations and 9/9 tool
  mutations caught), the $A600 anchor (16x16 MASKED, byte-identical to the pre-rewrite tool, deterministic), and
  Chuckie Egg ($929C skip 1: 16x16 OR-blit whose 32 recovered bytes equal the 32 source bytes read from $9070).
  Fixed on the way: the bound is now checked (a CALL/RST must precede the stack top; `--ret` overrides; a call that
  never returns exits 3 instead of reporting whatever ran), `--target LO HI` really measures a same-layout
  back-buffer (the bitmap filter was hard-wired to <$5800), attribute writes no longer crash the draw-order sort
  (every Chuckie Egg sprite routine hit it), EMPTY replaces a bogus XOR label for an all-transparent result, and
  `--out` creates its directory.  Second round the same day: Chuckie Egg 2 (`$8063` draw == source, `$7FC9`
  erase pass read as such) and Gauntlet (three `JP (IX)` shadow-screen blitters via `--ret IX --target 0xC000`;
  a `$0000` stack top crashed the draft) plus a THIRD run over the real background that checks
  `(bg AND mask) OR data` byte for byte -- mismatch 0 on all four games.  Report:
  `docs/blitforensics-test-report.md`.  Upstreamed the same day.

## M5 sprites (2026-09-07)

- Sprite blitter format VERIFIED, not assumed: instrumented one live blit (logged each POP
  source address vs each screen write) -> 16x16 = 64 bytes, 16 rows x [maskL,dataL,maskR,dataR],
  composite (screen AND mask) OR data. `tools/extract_sprites.py --verify` is a differential
  self-check against the live blitter (predicts each written byte from source mask/data +
  the prior screen byte; 32/32, 0 mismatches). Mutation-tested: swapping mask/data roles ->
  32 mismatches -> FAIL, restored -> PASS.
- Master entity draw $A447 (main loop $8C56/$91D6) -> 16-wide stack blitter $A600, SP parked
  at (IY+0/1). 8 per-type draw routines $AF31-$B021; facing = base+$160 where added; enemy A's
  flip is runtime-mirrored to low RAM $5B80 (=> read LIVE bytes, not image.bin, for low frames).
  $C260 = bubble (symmetric). $D7C0/$D920 = player two facings.
- CAUGHT: first pass decoded live frames from build/image.bin and $5B80 came out as garbage
  (low RAM is rebuilt at runtime); fixed to capture the 64 source bytes from the harness at
  blit time. Also dropped a naive +$160 auto-flip (it produced garbage for symmetric/runtime
  frames $C7E0,$5CE0) -- flips come from live capture instead.
- COVERAGE GAP (open): only round-1's enemy type + the static bank bases seen so far. The full
  roster/animation needs states from later rounds (each spawns different types). Front-end and
  HUD text draw via other blitters ($A824/$A84D/$A9ED) -- title/attract produce zero $A600 blits.

## M5 checkpoint (2026-09-07)

State of the port at this checkpoint (all committed; details in docs/SPEC.md):
- DONE: M0-M3; M4/M5 level system (round ctr $8609, data $61A8, 81 rounds, palette 15-cycle,
  shadow $E000); sprites (16x16 masked, format verified, extract_sprites.py); 8 enemy types
  ($73B0 dispatch) + spawn table ($7491, extract_enemies.py, 513 enemies); enemy AI (shared
  walker $B028, probe $B47B, ballistic tables $B59D/$B5BD); bubbles (pool $FED8 x12, lifecycle,
  blow=cursor 7) + capture manager ($B636/$BDFE/$BE5B, escape $B679).
- Assets shipped (build/*.json): sprites.json, enemies.json, round_palettes.json.
- Tools added this phase: extract_sprites.py, extract_enemies.py, fieldlog.py (game-agnostic;
  kit candidate). blitforensics.py generalised + validated in the parallel kit session.
- RESUME POINT: the POP -> FRUIT -> SCORE chain (player bursts a HOLDING bubble -> enemy death
  -> fruit on the $B59D/$B5BD arc -> collect -> score) and the exact capture-commit (set bubble
  (IY+9)=1 on a $BE5B hit). Then EXTEND/special bubbles, player physics ($A5xx), hurry-up/whale,
  boss ($79A2), front-end/HUD blitters + font, RNG. Then M6 sound (settle 48K-vs-128K first).
- To reach a HOLDING bubble live (needed for pop->fruit): from a play state, move the player
  adjacent to an enemy, blow (key 7), let the bubble envelop it (capture via $BE5B), then jump
  into the bubble to pop it -- or read the pop path (counterpart to the escape $B679).

## M6 outcomes (2026-09-09) -- the sound branch settled, the 48K beeper layer censused

- The 48K/128K decision is the front end's TIMING PROBE `$FAC3` (SPEC "M6 sound", TRAPS #28), not
  BANKM. The kit harness reproduces the 48K count `$075E` provided no key is held through the
  5-second credits/probe and contention is ON (`$075C` with a key held -> 128K; `$07AB` uncontended).
- **All pre-2026-09-09 harness play states are 128K-branch** (`$8DC4`=`$F3`, the AY engine sitting over
  `$C350-$D263`): afterctrl, play1p, play2p, round1, crowd and their derivatives. Kept for M10. All
  owner `.szx` snapshots are 48K-branch. Every M5 measurement made on the owner's snapshots stands;
  the M3 timing rows were re-measured on the 48K branch (ISR = renderer; see the checklist).
- 48K-branch harness states (build/*.pkl, regenerable): from `title` press '4' 3 frames, wait 30,
  '3' 3 frames, wait until PC hits `$8CC3` (+5 frames) -> `afterctrl48`; from it '1' held 6 frames
  (3 is too short) -> `play1p48` at +30, `round1_48` at +250; '2' -> `round1_2p48` at +250.
  Check `$8DC4`=`$C9` and `$C350` = sprite bytes in every new state.
- The 48K sound layer is seven inline beeper emitters + the ROM-BEEPER menu click; no music, no
  engine (SPEC table). `tools/sfxcensus.py` is the census tool; raw edge logs for the modelling
  step are reproducible from the states it names.
- Side facts from the same runs: the hurry-up timer `$8DBD` is reset to 0 by the player's death/
  respawn (`$ABB1` arms `$9160`=1 -> `$915F` resets it and removes Boris); the idle harness player
  is killed at ~f313 of round 1 by a wandering enemy, so an idle run never reaches HURRY UP (1500).

