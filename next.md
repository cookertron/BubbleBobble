# next.md — where the Bubble Bobble port stands, and what to do next

Written 2026-10-08 (updated 2026-10-16c: THE SPRING JERK CONFIRMED IN AN EMULATOR by the owner (the 48K); the 128K page's excess is before HURRY UP, 135 lost against a real 128K's 36; the owner's decision pending), so a fresh session can continue without the old conversation.  CLAUDE.md and the memory index load automatically; this file is the
bridge.  Read it, then `docs/STATUS.md` (the short read) and **docs/M10-PLAN.md** (the M10 findings and plan).
Don't re-read old transcripts.

## RESTART HERE (2026-10-16c, THE SPRING JERK CONFIRMED IN AN EMULATOR (the 48K); THE ONE REASON TO GO ON: THE 128K PAGE HITCHES ~4x AS OFTEN AS A REAL 128K BEFORE HURRY UP; THE OWNER'S DECISION PENDING)

- **The owner's emulator check (2026-10-16):** "Yes the emulation replicates the bizarre jumping behaviour. I've
  created two snapshots to capture so I don't have to poke it each time. spring_enemy_128K.szx and
  spring_enemy_48K.szx. You don't need to do anything further on this as the build replicates the game logic exactly,
  unless there's some reason you can think of to examine this more closely?"  Nothing running; no cron.  Commits this
  stage: this next.md + one SPEC bullet (docs only; suites as at 30be3e0: bb 1,980, kit 132, debug 40; no battery due).
- **The snapshots** (`snapshots/`, git-ignored with every `*.szx` -- never commit them): `spring_enemy_128K.szx` and
  `spring_enemy_48K.szx` are THE SAME FILE (25,945 bytes, SHA-1 7b69009b9743..., Spectaculator, SZX 1.4, machine id 1
  = 48K, RAM pages 0 / 2 / 5 only): round 30 (`$8609` 30, `$FECD` 0), P1 untouched at X 24 / Y 168, `$8DBD` $45 (odd),
  PC $FFFF at T 26 (an interrupt just accepted), seven springs.  The owner's 39 older snapshots are all 48K too.  So
  the emulator confirmed the 48K; the real 128K's rate rests on tools/harness128.py alone.  **BUT while this was being
  written the owner saved two REAL 128K ones** (14:16:52 and 14:17:02): `snapshots/Bubble Bobble#10320478124.szx`
  and the one the owner then renamed **`snapshots/spring_enemy_128K_REAL.szx`** (SHA-1 ae3a62f13908; the owner: "a
  real 128K snapshot of round 29" -- it is ROUND 30: the HUD reads 30 and `$8609` = 30; the poke was 29 and the
  umbrella's skip adds one).  Both: machine id 2, all 8 RAM pages, an AY chunk, `$7FFD` $10; P1 untouched at X 24 /
  Y 168; the first with every enemy at Y 52 (just arrived), the REAL one ~10 s later with them bouncing (`$8DBD` $33
  then $92).  Screen render: scratchpad/spring/szxscreen.py IN.szx OUT.png.  If both come from one untouched run, they are an
  independent check of tools/harness128.py against Spectaculator's 128K: load the first into harness128 (needs an SZX
  loader: the 8 banks, the registers with R / I / IM / IFF, the T in the frame, `$7FFD`, the AY registers), run it
  hands-off, and look for the second's RAM at a frame end (LD A,R makes that a T-exact test).  Do that FIRST if the
  owner picks (b) or (c), before calibrating anything on harness128.  Reader:
  `python -I scratchpad/spring/szxinfo.py FILE...` (machine, chunks, registers, `$7FFD`, a few game bytes).
- **The split by phase, from the stored runs (no new runs; a burst = >= 4 losses each <= 6 frames apart = HURRY UP):**

  | 12 probes (probes.json 0..11) | before HURRY UP (all after P1's first move) | in HURRY-UP bursts | total |
  |---|---|---|---|
  | real 128K (batch128.py) | 36 | 102 (probes 0, 7) | 138 |
  | the 128K page (batchport.js 128K) | **135 (3.75x)** | 245 (0, 7, and 8, which the real one lacks) | 380 |
  | the 128K-clock scratch page (scratch/spring/clock128.html) | 32 | 96 | 128 |
  | real 48K (mach.py) | 121 | 112 | 233 |
  | the engine on mach.py's drive (eng.js) | 99 (probe 8: 6 vs 23 = the drive's key convention; without it 93 vs 98) | 113 | 212 |
  | the 48K page on the page's drive (batchport.js 48K) | 89 | 177 | 266 |

  In the owner's terms, before HURRY UP with P1 walking (P1's first move at probe frame 400..643, HURRY UP at ~1,610:
  ~22 s a probe): a hitch about every 7 s on a real 128K; about every 2 s on the port's 128K page -- and on a real 48K
  and the 48K page.
- **The answer given:** the logic is exact on both pages and the 48K page's timing is the 48K's, but the 128K page (the
  default) is the one place the build does not replicate the original here: it runs the 128K's code on the 48K's
  frame (declared; its "within about 1%" is wrong for this threshold effect).  If the owner's playtest was on the
  default page, the jerk came ~4x as often as on a real 128K.  The 128K snapshot is the 48K one: to see a real 128K,
  pick the 128K model BEFORE loading the tape (a 128K SZX: machine id 2, 8 RAM pages, a larger file), then A/B it
  against the port's 128K page at round 30 (the debug page's round jump) with P1 walking.  RECOMMENDED (b); at the
  least (a), since README "The 48K's clock" / M10-PLAN 1.7's "1%" is now measured wrong.
- **THE DECISION IS THE OWNER'S (a scope change):** (a) declare only; (b) RECOMMENDED: the 128K's clock as a declared
  layer on the 128K page; (c) the full 128K re-timing; or leave it.  Each is detailed in the 2026-10-16b section below.
  Read the answer in the conversation; if the context was cleared before it, ASK AGAIN.
- **If (b): SOLO + ONE Sonnet reviewer on the final diff** (the M10.2c / M10.3 pattern: it changes the default page's
  clock).  Not a multi-agent pass: the machine question is answered (clock128.html already gives the real 128K's
  rates probe for probe); what remains is applying it.  Order: (1) the module constants per machine -- `BB_FRAME_T`,
  `BB_ULA` (FROM / LINE), the span rule's 32-T interrupt, `bbUlaTab`'s cache, the page's frame rate -- the 128K's
  values as clock128.html has them, behind ONE named flag, ON on the 128K page; OFF = the 48K clock with its exact M10
  gates kept; audit every table derived from them; (2) the gate: batch128.py vs batchport.js over probes.json, the
  rates within noise of each other; (3) re-pin the page-level 128K tests that assume the 48K frame (run the suites to
  find them; G8 and debug.test.js are the likely ones); (4) README / M10-PLAN 1.7 / SPEC; (5) the --affected battery,
  then a FULL one (the default page changes).

## RESTART HERE (2026-10-16b, THE OWNER'S SPRING-ENEMY FINDING -- MEASURED: the jerk is THE ORIGINAL'S on both real machines; the 128K page (the 48K clock) has it 2.8x as often as a real 128K; THE OWNER IS CHECKING IT IN AN EMULATOR -- the decision waits for that)

- **The finding (owner, 2026-10-16):** "The spring enemies bouncing is jerky after the player moves. If the player
  hasn't moved the enemy motion is as it should be."  Nothing committed for it yet; nothing running; no cron.
- **The mechanism (measured on the real machines; scripts in scratchpad/spring/, git-ignored):** the spring is TYPE 4
  (sprite `$C3C0`, a head on a coil; round 30 has seven).  The ODD interrupt draws every sprite (`$A3AD`) and then moves
  them (`$AA60`); in round 30 it runs 57,000..77,000 T.  When it runs past the frame (69,888 T on the 48K) the machine
  MISSES the next interrupt, the parity (`$8DBD` bit 0) shifts by one, and every sprite's 25 Hz update comes 3 frames
  after the last instead of 2: the visible jerk.  **"After the player moves":** P1 starts at X = 24, a multiple of 8 --
  the blitter's unshifted path (`$A60F AND 6`); at an X that is not (3 positions in 4 once it walks) its draw and erase
  take the shifted path: **+2,332 T** on the odd interrupt (align.py: ONE real-48K state, only P1's X changed: X 24 /
  25 / 32 / 40 -> 38,603 T, X 26..31 / 34..38 -> 40,935; +2,244 and +2,631 at two more states).  Over 12 random probes
  per machine: **0 interrupts lost while P1 stands untouched** (~3,600 frames each machine), **233 (real 48K) and 138
  (real 128K) after P1 first moves.**  So the owner's observation is the original game's behaviour, on both machines.
- **HURRY UP makes it heavy, whatever P1 does** (found after the question below was asked): ~1,610 frames into the
  round the first hurry-up angers every enemy (`$90C1`; +7 bit 2: `$AAE6` runs each handler TWICE) and from then on most
  odd interrupts overrun -- one lost every 3..5 frames, 50..60 in the next ~230 frames on BOTH real machines, P1
  untouched or not, until a death's respawn calms them.  With P1 never moving (probes.json 12 / 13: mach.py 30 0 12|13,
  batch128.py 30 12 13): 0 lost before that point, on both machines.  Before HURRY UP the losses are sporadic (1..23
  a run) and all after P1 has moved.  (probes 0 and 7's big counts were all after HURRY UP.)
- **The port's 48K page IS the machine.**  mach.py (the real load, passacc's keys, round 30 poked in at the end of ISR
  1000, a walk probe; ISRs closed at their RET) against eng.js (the engine EA3's way: skipProbe off, ctrlBoot, LD A,R
  fed): lost interrupts **[1670, 2092, 2185, 2222] on both**; every enemy's X / Y / +7 / +8 / +9 equal at all 1,236
  ISR ends after the build (2 differ in `$FEC5` only: `$93DC`'s dark window).  On the 12 random probes 5 are identical
  lost frame for lost frame; the other 7 part at a declared fine-timing gap (an odd ISR at the threshold a few T off:
  69,934 vs 69,883, 69,926 vs 69,916; the dark window; a respawn's `$8DBC` reset a frame apart; a respawn DI window) or
  at mach.py's key convention (keys at ISR ends: a key change on a LOST interrupt reaches the machine a frame late --
  probe 8); totals 233 machine / 212 engine.
- **The port's 128K page (the default) has it 2.8x as often as a real 128K:** 380 lost in 23,237 frames (1.64%)
  against 138 in 23,251 (0.59%) on the same 12 probes (batch128.py: tools/harness128.py from the recon's real-128K
  state scratchpad/ay128/main128_late.pkl; batchport.js: the built page).  The odd interrupt's T is the real 128K's
  within ~1% (medians 63,1xx..64,5xx both; the AY hook ~500 T on both); the FRAME is not: the page runs the 128K branch
  on the 48K's 69,888-T frame (README "The 48K's clock" / M10-PLAN 1.7, DECLARED as "within about 2% ... probably
  within about 1% (inferred, not measured)" -- wrong for this threshold effect).  **EXPERIMENT** (scratch/spring/
  clock128.html = the built page with `BB_FRAME_T` 70,908, `BB_ULA` FROM 14,361 / LINE 228 and the span rule's 32-T
  interrupt as 36): **128 lost (0.55%)**, probe for probe with the real 128K (51/50, 1/0, 2/3, 2/3, 4/9, 2/3, 2/1,
  45/56, 7/4, 6/5, 1/1, 5/3).  The real 128K still stutters in bursts (probe 1: 50 losses, every third frame for ~250
  frames) -- the original's, as on the 48K.
- **THE OWNER'S ANSWER (2026-10-16):** "Can you make a note of this please? I'll test it in emulation to see if it is
  true. I don't remember them doing this so would like to check. Can you tell me what I need to poke in order to go
  straight to the level with the spring enemies please?"  NOTED: this section + SPEC "The springs' jerk: the odd
  interrupt overruns the frame" (after the movement census).  THE POKES GIVEN (a fresh load, in round 1 once P1 can
  move; `$FECD` LAST -- it is the umbrella's skip counter, so the game's own advance builds the round):
  `POKE 33495,14` ($82D7 the palette build counter) and `POKE 33772,4` ($83EC the tile counter) -- round 30's own
  colours (a fresh load's round 1 has 1 / 1; a straight run leaves round 30 at 0 / 0; the warp's one build steps
  them; cosmetic) -- then `POKE 34313,29` ($8609, one short) and `POKE 65229,1` ($FECD).  On a 128K `$FECD` is in the
  paged slot (bank 1 is in only during the AY tick, <1% of the time): if no warp happens, poke it again.
  **THE DECISION WAITS FOR THE OWNER'S EMULATOR CHECK.**  Options as put: (a) declare only (README / SPEC / M10-PLAN:
  the measured consequence in place of the "1%"); (b) RECOMMENDED: the 128K's clock as a declared layer on the 128K
  page (frame 70,908 T, the contention geometry 14,361 / 228, the 36-T interrupt, the page at 50.02 Hz; behind a flag,
  ON on the 128K page; the 48K-clock path and its exact M10 gates kept; gated statistically against
  tools/harness128.py like batch128.py vs batchport.js; ~1 session + a battery -- the module constants BB_FRAME_T /
  BB_ULA / the 32-T interrupt and bbUlaTab's cache made per machine, every derived table audited); (c) the full
  re-timing on the 128K, exact against harness128 (several sessions; the timing campaign reopened).  If the owner
  reports the emulator does NOT stutter: check the emulator's contention / model / speed first (the effect is a
  T-state threshold), then compare its round 30 against mach.py's frames.
- **Scripts** (scratchpad/spring/): perf.js (the debug page, per-frame ISR branch / cost), look.py, mach.py (the real
  48K; `python scratchpad/spring/mach.py 30 2300`, or `30 0 <i>` = probe i of probes.json -> batch48_<i>.json), eng.js
  (`node scratchpad/spring/eng.js 30 [mach file]`), mach128.py / eng128.js (the walk probe on the real / port 128K),
  batch128.py (12 probes, real 128K, ~80 s), batchport.js (`node ... <i> 128K|48K 30`; `BB_PAGE_FILE` = another page),
  probes.json (12 seeded probes), align.py (the odd ISR's T by P1's X).
- **Lessons:** (1) a recorder that closes an ISR at the loop's top MERGES a back-to-back ISR (one that returns inside
  the next interrupt's window is followed at once by the next) into the next one -- close it right after its RET,
  before the acceptance check (mach.py's first "machine lost 2207" was that; the engine was right: span 1); (2) keys
  applied at ISR ends lag a frame when that ISR is lost, keys applied per frame do not -- a differential across lost
  interrupts needs the two drivers on one convention; (3) "within about 1%" was an average; a threshold (the frame's
  end) turns a 1.5% longer frame into 2.8x fewer events -- measure threshold effects as rates, never infer them from
  averages.

## RESTART HERE (2026-10-16, THE DEBUG PAGE -- COMMITTED 30be3e0; next: THE OWNER'S SPRING-ENEMY FINDING, tested with it; the listening test still open)

- **The owner's request (2026-10-16):** "create a copy of the build but add debug features - jump to level, trigger bonus
  item, kill all enemies, EXTEND, that sort of thing" -- to test every aspect of the port.
- **Committed 30be3e0** (web/debug.js, tools/build_debug.py, tools/debug_mutants.py, test/debug.test.js, README.md,
  tools/README.md, .gitignore, docs/STATUS.md, next.md).  Nothing running; no cron; the local http.server stopped.
  - **`python tools/build_debug.py`** -> **web/bubble_bobble_debug.html** (git-ignored, tape-derived): runs build.py, then
    `assemble()`: the built page + web/debug.js at the end of the page's script; refuses a faithful page carrying `BB_DBG`;
    reads the faithful page back off the debug page byte for byte.
  - **web/debug.js** (pure ASCII -- non-ASCII as `\uXXXX`, the page declares no charset): a panel and `__PORT__.debug`.
    Hooks, the page's game only: `BB_Game.prototype.step` (speed: freeze / one frame / 1/4x..8x, muted off 1x; the queue
    before each frame; the holds after; an engine throw caught, shown, frozen -- a reboot clears it), `roundAdvanceCore`
    (a jump: `$8609` one short; `$82D7` mod 15 / `$83EC` mod 5 stepped by the builds skipped; the 20/40/60 warp held off;
    `$FECD` ended; `$9A0E` blanked below 10; queued clears spent), `buildClockFor` (round 1 from a round: the means'
    clock -- r1Clock is the title path's replay).  Actions land between frames, queued while a block is in flight
    (`busy`: NOT pTail / skipIsr, timing only).  Kill = `$8BC2` + the storm's burst for class-1 bubbles; items at the
    round's spawn point (`$89FB`; a busy slot emptied by the clear's expiry); letters = `$B7E5`'s leavings; invincible =
    the respawn's invulnerability held (at once); clear = the wait skipped, the timer's parity kept (the potion's room:
    the drain's window).  Alt+K N X C I L.
  - **test/debug.test.js 40/40** (~7 min): B1..B4 the boundary (B4: with no action, the same 64K as the faithful page
    after the real load's 700-frame drive -- the faithful page in a child process), A1..A19 + A6b / A8b every action,
    T1 a jump to EVERY round (81, scrambled, each in play with a straight run's counters), T2..T5, E1.
    `BB_DEBUG_PAGE=<file>` tests a given page, no build.
  - **tools/debug_mutants.py** (pages in scratch/debug_mutants/, git-ignored; `--jobs 14`, ~30 min): **29 of 29 killed**,
    the control 40/40.  The final run with the tool: 28 + `god-at-once` SURVIVED (A10 read the hold a frame late; the
    first run's kill had been an enemy's luck) -> A10 reads it before any frame -> killed.  Earlier: `spent` -> A8b;
    `boss` hung the 40-min timeout -> the waits cut to 3,000 callbacks, the tour stops at its first failure.
  - Suites: bb **1,980/1,980**, kit 132/132, debug 40/40; romscan CELLS 0, STRONG 1 (allowed), 476 files.  No battery
    file changed -- no battery due.  Browser (Chrome on 127.0.0.1): the panel renders, a click jumps 1 -> 12, spawns the
    storm cross at the spawn point, kills all six; focus never leaves the page; no console error.
- **Found in the game (faithful, in the panel and README):** the blue bottle's bit is the COLLECT LOCK (`$87E2`: nothing
  taken after it until a death); on round 81 the player stands on the potion and takes it at once, so the room's drain
  (`$8F36`, 8 x 256 frames) ends it.
- **NEXT 1 -- THE OWNER'S PLAYTEST FINDING (2026-10-16), with the debug page (solo):** "The spring enemies bouncing is
  jerky after the player moves. If the player hasn't moved the enemy motion is as it should be."
  - Which enemy: most likely TYPE 4 (SPEC "Live movement census": first in round 30, sprite `$C3C0` / `$C520`, `+9` =
    129 the homing hop -- "hops at the player a lot"; the hop is `$B0F7` through `$B028`, the arcs BB_HOP_BIG `$B59D` /
    BB_HOP_SMALL `$B5BD`); possibly type 2 (round 10, the flying bouncer).  Confirm by eye on the debug page first.
  - The test: jump to the round, freeze / step, record the enemy's (X, Y, +9) every frame from the round's start with
    the player NEVER moved, and again with a short walk first -- the same frames.  Then the differential (house rule 2):
    the same key script through the harness (the machine) and through the built page, sampled at the main loop's top,
    diffed row for row -- the first differing row names it.  If the machine jerks the same way it is the machine's (the
    homing hop re-aiming at the player, or the slowdown the timing model gives -- TIMING item 9: 0.55% of interrupts
    overrun, more with the player moving?); if not, the port's.  Solo unless the differential points into unmeasured
    timing.
- **NEXT 2 -- the owner's listening test** (2026-10-15b's NEXT 1 below: the caption, the tunes, crackle, the balance via
  `__PORT__.sound.ayMix = x`, Alt+P, Alt+M, `sound.info()`), then the owner's calls (CAPS-held pass #357, controllers,
  the pre-publication history scrub).
- **Pre-existing, found (the owner's call):** the built page declares no charset and no doctype.  Served over http,
  Chrome takes it as windows-1252 in quirks mode -- the caption's "·" shows as "Â·"; opened from disk Chrome usually
  detects UTF-8.  A `<meta charset="utf-8">` in the template would settle it: a page change, so a battery.
- **Lessons this session:** a check that kills a mutant by LUCK is not a kill -- A10 read a hold one frame late and the
  first run's kill came from an enemy's touch; read the effect at the moment it is promised.  A mutant that HANGS the
  suite is not a kill by name: bound every wait, stop a tour at its first failure.  And `busy` must separate logic in
  flight from timing only (pTail): measure which flags are set at frame boundaries before treating one as a block.

## RESTART HERE (2026-10-15c, M10.4 THE RELEASE DOCS -- COMMITTED 3d9ef82, the FULL battery CLEAN; M10 IS DONE but for AY_MIX; next: THE OWNER'S LISTENING TEST, then only the owner's calls)

- **Committed 3d9ef82** (README.md, docs/STATUS.md, docs/M10-PLAN.md, tools/mutants.py).  Suites: bb **1,980**, kit
  **132**, selftest **38**.  Nothing running; no cron.
  - **README.md**, the release pass: the intro names both machines (the 128K by default); a new "Playing" section (the
    control select, '1' / '2', the caption, the page's Alt keys, `__PORT__.sound.info()`); the scope rows the
    measurements corrected (81 round layouts and NO ending sequence -- past the last round a random round 30..61, SPEC
    `$97F8`; NO attract mode -- the title's wait has two exits --; one high score, no table / name entry; a 128K row);
    the first plan's "No dropped frames ... _pending (milestone M3)_" rewritten as the timing model it became (the
    machine drops no video frame; 0.55% of interrupts overrun, TIMING item 9; the port's slowdown is the machine's;
    GR4 / EA3's windows; the gaps DECLARED in TIMING, the CAPS-held pass #357 among them); the `LD A,R` substitute
    (RNG.md "Declared gaps"); the 128K machine as a declared layer (the 48K's clock against M10-PLAN 1.7, the probe's
    count forced to the 128K's `$0759` at `$FAE1`, the AY model + AY_MIX PROVISIONAL, no ULA snow) and Alt+M
    (saveMachine, `bb-machine`); Layout, Build and test.
  - **docs/STATUS.md**: the M10.4 paragraph; the table "Where it stands" (stale since 2026-10-08) and "Left" (2 sound,
    3 the timing campaign STOPPED = declared, 7 128K DONE) refreshed; the page paragraph brought to M9.2 / M10.3.
    **docs/M10-PLAN.md**: "M10.4 DONE".
  - **tools/mutants.py**: `prepare` / `cover` and the `git` helper decode their output as UTF-8, `errors='replace'`.
    Measured (a direct check): the OLD `text=True` (cp1252 here) on output holding U+2550 kills subprocess's reader
    thread -- a traceback on stderr, NOT an exception in the caller -- and leaves `r.stdout` None, so cover's
    `print(r.stdout.strip())` would crash; the NEW call returns the text; the git helper decodes the README's diff.
- **The FULL battery** (the runner changed; build/mutants/m104_full.log): `2026-10-15 14:33 full run: LISTED 7039
  KILLED 7035  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 3  CRASHES 0  MISSES 0  -- 38.0 min on 20 workers` -- the
  four known (M7.110's cursor guard; B9 x2, M7.69).  It REUSED its cached preparation ("preparation reused (nothing it
  depends on has changed)": by design the cache key leaves mutants.py out), so it never ran the new decoding -- the
  direct check above is the proof.
- **NEXT 1: THE OWNER'S LISTENING TEST** (the owner's ears; the checklist is 2026-10-15b's NEXT 1 below: the caption,
  the tunes, crackle, the balance via `__PORT__.sound.ayMix = x` live, Alt+P, Alt+M, `sound.info()`).  The page is built
  (web/bubble_bobble.html, 13:45, from 1f61a2e's sources -- 3d9ef82 changed none of them).  What it finds is fixed
  first.  An AY_MIX change: the value is the 128K machine's own balance, not this game's, so it is `AY_MIX` in
  web/platform.js -- shared: upstream to E:/Software/Spectrum-Port-Kit with its kit.test.js expectations -- plus every
  expectation of the mix level (grep `aymix=1`: kit.test.js's two regexes, bb.test.js's three strings in G3 / G8), the
  README / STATUS / SPEC sentences
  calling it PROVISIONAL at 1.0, and an `--affected` battery (`$env:ZX_CASE_TIMEOUT='900'`, Start-Process, watch.ps1,
  a CronCreate poll -- the 2026-10-15b launch line below, `--affected` for the full run's arguments).
- **After that, nothing of the plan is left.**  The port is done but for the owner's calls: any playtest findings; the
  CAPS-held pass gap (TRAPS #357 -- the timing campaign is stopped, the owner's word reopens it); controllers (a later
  declared layer, when the owner asks); the PRE-PUBLICATION history scrub (STATUS "Left" 9: git filter-repo over the
  old ROM quotes, or one squashed commit -- before any push anywhere).
- **Solo or agents:** solo.  Nothing left is unknown machine behaviour: the listening test is the owner's ears, and an
  AY_MIX change is one constant.
- **Lesson this session:** a battery that reuses its cached preparation never runs `prepare` / `cover`, so it cannot
  prove a change to them -- check the changed call directly (or delete build/mutants/prep.json to force a fresh
  preparation, ~25 min).  I first wrote "proven by the run" into this file and had to take it back.

## RESTART HERE (2026-10-15b, M10.3 THE PAGE AND THE PLATFORM -- COMMITTED 0f27a31, its batteries CLEAN; kit upstreamed 7abb3b7 + 6260b4c; next: THE OWNER'S LISTENING TEST, then M10.4 the release docs + the FULL battery, SOLO)

- **Committed 0f27a31** (web/platform.js, web/template.html, test/kit.test.js, test/bb.test.js, SPEC "The page and the
  platform", STATUS, M10-PLAN "M10.3 DONE", TRAPS #361..#364).  Suites: bb **1,980**, kit **132**, selftest 38; romscan
  CELLS 0, STRONG 1 (allowed), 472 files.  The kit repo (E:/Software/Spectrum-Port-Kit): **7abb3b7** (platform.js + its
  kit.test.js checks, 127/127 there) and **6260b4c** (its starter.html rebuilt).  Nothing running; no cron.
- **What M10.3 is**: the page boots the **128K** (`BB_PAGE.m128`, ON; OFF the 48K page as before); **Alt+M reboots into
  the other machine** in any state (`bbBoot()`: a new BB_Game from the load's control select, `m128` set before
  `ctrlBoot`, hiscore / altkeys made for it, `sound.reset()`); remembered (`BB_PAGE.saveMachine`, ADDED, default ON; store
  key `bb-machine`, `{ machine: '128K' | '48K' }`, any other value refused by name, an unparseable one read as empty by
  the kit's settingsStore); the caption names the machine RUNNING before the fullscreen hint ("128K machine (Alt+M: the
  48K)").  web/platform.js (game-agnostic): SoundOut's instrument **`'mix'`** -- the beeper and the AY in the SAME chunks
  on the worklet (default) and the scheduled fallback; `flush(beeperLog, upto, ayLog)`; each AY write at
  floor((frame - origin) / frameHz * sr); registers shadowed (`ayReg` / `aySeen`) through no context / sound off /
  restart / drop; the chip (`aym`) made at the first rendered window, replaying only registers written since reset;
  never written = never rendered; DC-blocked, scaled by `ayMix` (**`AY_MIX` 1.0, PROVISIONAL**); `reset()` = every chip
  at power-on (the speaker LOW -- the Sonnet review's one finding, TRAPS #364); every origin adopts the dropped log's
  state; `info()` ends `chips=beeper+ay ay=live ayw=N aylate=0 aymix=1.00 resets=0`.
- **Tests.**  kit.test.js +11 ("THE MIX", the S6 worklet line, the one-chip info line).  bb.test.js: the prelude SEEDS
  the rig's store with `{ machine: '48K' }` before loadBuilt, so the shared page stays the 48K page every older page row
  reads (TRAPS #362); block "M10.3" G0..G9 (source scratchpad/m103/g_block.js; `python scratchpad/m103/sync.py` copies it
  in -- run it AFTER m102d's / m102c2's sync.py, which replace from their headers to rig.done() and would drop it;
  `node scratchpad/m103/g_only.js` runs it alone the runner's way, ~12 s, FAILFAST=1): G0 the kit's suite in a child;
  G1 bbMachine; G2 the seeded page; G3 / G4 / G8 FRESH pages in child processes (`child(raw, fn)`: a rig + store seeded
  with `raw`, `fn.toString()` run there, JSON back; ~0.7 s a load); G5 the 128K's AY through the page's real loop; G6 the
  captions; G7 the 128K engine's logs through the mix in-process, exact; G9 this page in-process (the draw's three logs,
  Alt+M's REPEAT -- never a real Alt+M on the shared page --, plain M).  M7.64(c2) and FS12 compare against
  `bbCtrlCaption()` (BB_PAGE_CTRL_CAPTION is the bare text now).
- **Battery.**  mutate7.py **7,039** cases (6,840 game.js, 152 template.html, 28 platform.js, 19 bb.test.js -- the
  "6,840" of notes since M10.2b was game.js's count only; `python scratchpad/m103/deadcheck_all.py` checks every case
  against its own file: dead 0).  scratchpad/battery/add_m103.py APPLIED (60 new, 11 page cases re-aimed onto the lines
  M10.3 rewrote; its docstring lists the EQUIVALENT left out and the 21 KIT_ONLY cases kept out of the list).  Hand
  battery (scratchpad/m103/handmut.py; `--bb` runs a case the battery's way, the M10.3 block alone): 82 cases, all
  killed but one EQUIVALENT (game.m128 set after ctrlBoot).  `--affected` (build/mutants/m103_aff.log): `LISTED 949
  KILLED 949 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 8 -- 72.0 min` -- the 8 MISSES were the
  Alt+M path and the draw's flush, killed only in child pages (the selection sees only this process: TRAPS #363) --
  closed by G9; `--match` on the twelve cases on those lines (build/mutants/m103_miss.log): `LISTED 12 KILLED 12 ...
  MISSES 0 -- 41.4 min`.
- **NEXT 1: THE OWNER'S LISTENING TEST** (the owner's; nothing to build first).  `python tools/build.py`, then open
  web/bubble_bobble.html (double-click is fine: file:// takes the worklet by its data: URL).  Listen for, and report:
  1. a fresh page names the **128K** in the caption; after the control select the cold start's short rising jingle,
     then the title tune; '1': the game-start tune, round 1 standing still ~4.4 s (the 128K's own wait), then the
     in-round theme -- slower until HURRY UP;
  2. **crackle or clicks** (there should be none: one stream for both chips);
  3. **the balance**: the AY music against the beeper's effects (jump, blow, pop, collect).  Live in the console:
     `__PORT__.sound.ayMix = 0.6` (or 1.5, ...) -- the number that sounds right becomes AY_MIX (PROVISIONAL 1.0 now;
     the AY alone peaks at 0.88 of the beeper's swing in the skip scene);
  4. Alt+P mutes the music; Alt+P again resumes it -- the tune restarts from its start (the 128K's own behaviour);
  5. **Alt+M**: the 48K at its control select, the caption "48K machine (Alt+M: the 128K)", no music, the effects as
     before; reload: still the 48K (remembered); Alt+M: the 128K again;
  6. paste `__PORT__.sound.info()` (expect `mode=worklet ... chips=beeper+ay ay=live ...`).
  What it finds is fixed first (an AY_MIX change is one constant + its kit / G3 / G8 expectations that read
  `aymix=1.00` -- grep `aymix=1.00`).
- **NEXT 2: M10.4 -- the release docs + the FULL battery (SOLO; no multi-agent pass: nothing about the machine is
  unknown -- it writes up what M10.0..M10.3 measured)**: README (the 128K machine as a declared layer: M10-PLAN 1.7, the
  forced probe answer, the AY output model and AY_MIX, the 50.08 Hz clock; the machine switch; scope row), STATUS
  (the table "Where it stands" is stale since 2026-10-08: suites, battery, the 128K), then the FULL battery -- FIRST
  give tools/mutants.py's `prepare` / `cover` `encoding='utf-8', errors='replace'` (their `subprocess.run(... text=True
  ...)`, ~lines 465 / 480; a runner change makes the full run due anyway).  A full run's baseline + coverage takes ~25
  min before any case runs -- never wrap it in a `timeout`.  Launch: `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process
  python -ArgumentList 'tools/mutants.py','--jobs','20' -RedirectStandardOutput build/mutants/m104_full.log
  -RedirectStandardError build/mutants/m104_full.log.err -WindowStyle Hidden -PassThru` + `Start-Process pwsh
  -ArgumentList '-NoProfile','-File','scratchpad/battery/watch.ps1',"$($p.Id)",'build/mutants/m104_full.log'
  -WindowStyle Hidden` + a CronCreate poll (:07 / :27 / :47) of the .done file.  Expect LISTED 7,039 (+ M10.4's).
- **Still the owner's call** (reported 2026-10-15, unchanged): the CAPS-held pass gap (TRAPS #357, the 48K's: +22 T and a
  second contended IN on a pass with CAPS held) -- one session if wanted; its best slot is BEFORE M10.4's full battery.
  The owner stopped the timing campaign on 2026-10-12, so it waits for the owner's word.
- **Lessons this session**: hand-test a case the battery's way before the list goes in (`--bb`), and remember the
  selection sees only what runs in the suite's process (#363); run a differential check off its identity values (#361);
  never reboot the shared page in a block (#362); `sed -i` in Git Bash turned docs/STATUS.md's CRLF into LF (restored;
  use Python for in-place edits); Git Bash heredocs still break on some quoting -- patch scripts via the Write tool.

## RESTART HERE (2026-10-15a, M10.2d THE PAUSE -- COMMITTED d56fd4c, its --affected battery CLEAN (863/863); M10.2 IS DONE; next: M10.3 the page and the platform, SOLO + ONE Sonnet reviewer)

- **Committed d56fd4c** (NEW tools/pause128.py + build/pause128_fixture.json, registered `pause128`; web/game.js;
  test/bb.test.js block "M10.2d" Q1..Q6; port.json; SPEC "The pause"; M10-PLAN "M10.2d DONE"; STATUS; TRAPS #357..#360).
  Suites: bb **1,970**, kit 121, selftest 38; romscan CELLS 0, STRONG 1 (allowed), 472 files.  mutate7.py **6,840** cases
  (scratchpad/battery/add_m102d.py applied: 49 new, 0 re-aimed; deadcheck clean; backup mutate7.m102d.bak).  Hand
  battery (scratchpad/m102d/handmut.log): 49 cases, 48 killed first; the one survivor ("request 0 cut: the spin's clock
  not re-based") was a gate gap -- Q2's replay takes each frame's origin from spin.t, so it cannot see that clock wrong
  (TRAPS #360) -- closed by Q6 (the arm meeting the interrupt THROUGH step()), its re-run killed.  --affected
  (build/mutants/m102d_aff.log): `LISTED 863  KILLED 863  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0
  MISSES 0 -- 41.0 min on 20 workers`.  Nothing running; no cron.
- **What M10.2d is** (SPEC "M10 -- the 128K branch", "The pause"): under m128 `$8FE7`'s arm makes `$8FF3`'s request 0 (the
  mute, R7 := $3F; interrupts ON: a DI window whose RET's end is the arm's last acceptance point) and the release makes
  `$9006`'s re-request of the saved sound with the interrupts OFF (it restarts the sound; its EI / RET end the spin's
  window an instruction before the 48K's `$9009 EI / $900A RET`).  Engine: BB_PAUSE_SPIN's `rq` (ARM[8], the 48K's RET at
  `$8E0A`) runs request 0 through M10.2c's `mwEnter` / `mwRun`; `spinRelease128` runs the unpause (iff 0, the spin's
  window carried by mwRet's `cut`, REM `EI_RET` 14 on RET z); the arm's interrupt keeps its acceptance phase under m128
  (`gridPhV`; OFF unchanged); a held frame re-bases `diWindows` under m128; `pauseGate` under m128 outside step() is
  refused by name.  BB_PAUSE_SPIN gained `REQ` 64 (the releasing IN to `$9006`'s CALL's end) and `EI_RET` 14.
- **The oracle** `python tools/pause128.py measure | verify --jobs 12` (~1 min, MATCH): six 128K worlds saved at `$8D0C`
  from ay128flow's p1 (790/870/960/1050/1140, the theme) and boss (1400, the boss theme) drives; 414 runs (144 natural,
  180 FORCED arms with `$8FE7` 40..400 T before a boundary, 90 FORCED releases 100..1,000 T); two scenes on the real load
  (pz: SYM 741, CAPS 749; pzb: SYM+CAPS 741, CAPS 742..744).  The machine's edges: the arm's interrupt taken at the end of
  the instruction in progress up to request 0's DI (L <= 104 from `$8FE7`), LOST 105..281, taken at its RET's end
  282..313, lost from `$8FF6 DI`; the release's lost to 951 (350..406 by the spin's own window alone), taken at the
  unpause's RET 952..983, after `$900A`'s RET 984..997.  The tool asserts every forced run was forced (TRAPS #358).
- **Gates** (`node scratchpad/m102d/q_only.js`, ~3 s, FAILFAST=1, SCRATCH=1 reads q_block.js instead of the suite's copy;
  `python scratchpad/m102d/sync.py` copies scratchpad/m102d/q_block.js into bb.test.js -- run it AFTER m102c2's sync.py,
  which would drop it): Q1 the machine's facts; Q2 all 414 runs through spinStep from the machine's `$8FE7`, exact; Q3 the
  scenes through step() (PINNED: the arm 1 T late in pz -- `$8FE7`'s place, the 48K's pass clock -- and the CAPS-held
  passes after the release, see FOUND); Q4 the flow's own p1 pause requests at their T; Q5 OFF, the refusal, the edges;
  Q6 the arm meeting the interrupt through step() (FORCED pausePos: request 0 cut / lost / taken at its RET's end -- the
  machine's phases 5 / lost / 13).
- **FOUND (the 48K's, DECLARED -- NOT fixed: the owner stopped the timing campaign on 2026-10-12):** a pass with CAPS
  held and SPACE up runs `$8D6A..$8D6F` (`$8D68 JR c` not taken; `LD A,$7F / IN A,($FE) / RRA / RET nc`): +22 T and a
  second contended IN per pass, which the pass skeleton (the CAPS-up path) never charged (TRAPS #357).  Every pause's
  release frame holds CAPS, on both machines; measured 22 T a pass in pz's frame 749.  A small, contained fix if the
  owner reopens timing (passCharge's skeleton + BB_PASS_ACC's second IN, then re-pin Q3 and whatever 48K gate holds
  CAPS through a pass) -- **the owner's call; it was reported at the end of the 2026-10-15 session.**
  **PROBED 2026-10-15 (the owner asked what the fix would cost; probe reverted, nothing committed):**
  scratchpad/caps357/probe.py, a rough charge in passCharge (+22 T when CAPS is down and SPACE up on 'pass' / 'wrap';
  the first IN at end-53, the second IN's I/O as C:1 / C:3 at end-25 / end-24 -- port $7FFE's high byte is contended,
  GUESSED, not measured; a 75-T grid tail 'SK.TAILC' '7 7 11 4 7 7 11 4 5 12').  bb 1,968/1,970: only TWO checks moved,
  both the pause release (scratchpad/caps357/probe_result.txt): M7.107 PZ3 (its expectation is passcost's CAPS-up 479:
  4,590 -> 4,612; it needs a MEASURED CAPS-down skeleton) and M10.2d Q3 (the first interrupt after the release: pz's
  pinned -2 T became EXACT; pzb's +4 became -3 -- the one unexplained residue).  Estimate given to the owner: ONE
  session, ~5..7 h of work + an --affected battery (~1 h, unattended): measure CAPS-held play passes on the 48K (and the
  M10 machine) incl. the second IN's contention, an interrupt inside the 75-T tail and a key change at a frame boundary
  (the straddling pass's tail reads the NEXT frame's keys); the engine; a differential gate + PZ3 from the measured
  skeleton + Q3 un-pinned; hand battery; docs.  TIME-BOX: anything past the CAPS tail (pzb's residue if it is not
  this, `$8FE7`'s 1-T place) is declared and pinned, not chased.  Best slot if wanted: after M10.3, before M10.4's FULL
  battery (which then covers it).  Solo; no multi-agent pass (the branch is four instructions, already read).
- **Next: M10.3 -- the page and the platform (SOLO; ONE Sonnet reviewer, narrow brief: shared platform machinery)**, per
  docs/M10-PLAN.md section 4 "M10.3" and the owner's decisions (memory: 128K the default machine, Alt+M reboots into the
  other one, the choice remembered like the high score, the caption names the machine):
  - web/platform.js (game-agnostic, upstream to the kit with kit.test.js checks): ONE output for both chips -- the AY
    into the worklet stream beside the beeper (today the AY has only the scheduled path, the one that crackled); AY writes
    placed at their sub-frame sample as fractional frames like the beeper's edges (game.ay.log rows are already
    `[frame + t / 69,888, reg, val]`); `sound.info()` reporting both chips.
  - web/template.html: the switch (Alt+M, beside M9.2's Alt+P / Alt+Q in bbAltKeys), the AY log flushed to the bridge,
    the caption, `__PORT__` exports, the remembered choice mutation-tested against the rig's real store (TRAPS #17).
  - Read first: platform.js `AyChip` (~line 287), `SoundOut` and the worklet transport (~455..600); template.html's sound
    bridge and `bbHiScore` (the settingsStore pattern); bb.test.js's AK (M9.2) and HS (M9.1) blocks for the page-level
    test style.  Then the owner's listening test.
  - Same rhythm: engine/platform -> gates -> hand battery -> add list -> --affected (detached + watch.ps1 + cron) -> the
    Sonnet review -> docs -> commit -> next.md.  platform.js changes also need kit.test.js checks (CLAUDE.md rule 8).
  - Multi-agent pass: NOT needed -- the machine side is measured (M10.0..M10.2); M10.3 applies it to the page and the
    audio runtime, where the rig and the owner's listening test are the checks.
- **Before M10.4's FULL battery** (unchanged): tools/mutants.py's `prepare` / `cover` need `encoding='utf-8',
  errors='replace'`.  A full / --match run's baseline + coverage takes ~25 min before any case runs -- never wrap it in a
  `timeout`.

## RESTART HERE (2026-10-14c, M10.2c2 THE SOUND CALLS IN PLAY -- COMMITTED 45ced8f, its --affected battery CLEAN (802/803 + the timeout closed, 9/9); next: M10.2d the pause, SOLO)

- **Committed 45ced8f** (game.js, bb.test.js, SPEC "The sound calls in play", STATUS, TRAPS #356, M10-PLAN "M10.2c2 DONE").
  Suites: bb **1,964**, kit 121, selftest 38; romscan CELLS 0, STRONG 1 (allowed), 470 files.  mutate7.py **6,791** cases
  (add_m102c2.py applied + one hand-appended case for the wait refusal; deadcheck clean).  --affected (build/mutants/
  m102c2_aff.log): `LISTED 803 KILLED 802 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 1` -- the timeout ("EXTEND's entry calls
  $8E05": a wait with the interrupts off spun for ever) closed by mwEnter's refusal (D6); its --match re-run
  (build/mutants/m102c2_fix.log) `LISTED 9 KILLED 9 SURVIVORS 0`.  Nothing running; no cron.
- **Next: M10.2d -- the pause (SOLO)**: `$8FF3`'s request 0 (interrupts on: the mute, request 0 = 250 T, its mixer write),
  the spin with interrupts off (nothing ticks: the AY holds the mute), and the unpause's `$9006` request (made with the
  interrupts OFF -- mwBegin(.., 0): the machinery is M10.2c2's) then `$9009 EI`.  The p1 scene has it: pause [1193, 27201],
  request 0 at [1193, 27218] (250 T), unpause [1256, 78], request 1 at [1256, 95] (iff 0, 577) -- but p1's play parts at
  760 (C2), so gate as M10.2c2 did: the requests at the machine's T (unit, like D5(a)), and the pause path driven in a
  scene (spinStep / spinHeld, step()'s `paused && !spin` path at ~line 22460 -- read both first).  Same rhythm:
  engine -> gates (scratchpad/m102d/, an e_block + sync AFTER m102c2's) -> hand battery (copy m102c2/handmut.py) -> add
  list -> --affected (detached + watch.ps1 + cron) -> docs -> commit -> next.md.
- **Before M10.4's FULL battery** (unchanged): tools/mutants.py's `prepare` / `cover` need `encoding='utf-8',
  errors='replace'`.  Note: a full / --match run's baseline + coverage takes ~25 min before any case runs -- never wrap
  it in a `timeout`.

### M10.2c2's working notes (kept for reference)

- **M10.2c2 WRITTEN** (SPEC "The sound calls in play", M10-PLAN "M10.2c2 DONE", TRAPS #356 -- written; STATUS's paragraph and
  the commit's numbers still to fill):
  - web/game.js: BB_M128.STOP / HEART / BOSS; mwBegin(.., iff) -> mwEnter (no budget check: lzHit calls it before step()
    sets budget); mwRun runs an iff-0 request whole; mwIns marks `taken`, pushes its window only with iff 1; mwRet carries
    the caller's window (M.cut -> the last on diWindows) to the RET's end (+ M.rem on RET z), sets mwA / mwB (A $10 / B $7F
    when taken), 'lz' -> lzRes.  Lazy blocks: extBegin refuses m128 extend/potion outside step(), lz.stops; extRt ->
    lzStopAt (EXTEND entry $94D5 iff 0, 'double' $953C wait, potion pt_head $891A iff 0, pt_fill tail $8991 wait --
    ptFillModel returns `tail`); lzSeg stops at the next stop (held writes / outs / windows capped, a window over an iff-0
    call cut, REM asserted, L.hit); lzHit / lzOn128; lzStep resumes (lzRes) and hits; extEnd hits in the call's frame.
    step(): `if (this.lz && !this.mw) lzStep`, loop turns `lzRes && lz` -> lzStep, `mwSeq` -> mwSeqStep, advDefer guarded by
    !mwSeq.  puRoundEffect -> heartReq (the heart).  bossDeath -> bossDeath128 under m128 (program in mwSeq from
    calleeAt(BB_CD.E3A) + rcT + rcSub + BOSS.HEAD).  reset(): mwSeq, lzRes, mwStops, mwLate, mwA, mwB, bossSeqs, bossAt.
    The unpause's $9006 MOVED to M10.2d (pairs with $8FF3's request 0).
  - test/bb.test.js: block "M10.2c2" D1..D6 (source scratchpad/m102c2/d_block.js; `python scratchpad/m102c2/sync.py` copies
    it in -- run it AFTER scratchpad/m102c/sync.py if that is ever re-run, which would drop it; `node
    scratchpad/m102c2/d_only.js` runs it alone ~10 s, FAILFAST=1).  14/14 with the kit's 8.  The whole suite passed
    1,958/1,958 with the engine change before D went in (scratchpad/m102c2/bb_run1.log); expect 1,964 now -- RE-RUN after
    the hand battery restores game.js.
  - Battery list: `scratchpad/battery/add_m102c2.py` (109 new + 7 re-aimed; `--dry` checks anchors; NOT yet applied to
    mutate7.py; its docstring lists 9 predicted EQUIVALENT).  `python scratchpad/m102c/deadcheck.py` must print only
    `cases N` after applying it.
- **Hand battery DONE** (scratchpad/m102c2/handmut.log): 113 cases, 110 killed; the 3 survivors were gate gaps, closed and
  re-run killed: the boss program's start when the pass charged LESS than $8E77 (D6's unit: moved there from 1,100, kept
  from 3,000 -- the gated scene's clear pass charges past it, so the move never bound) and the delays' (A, B) (D4 records
  [[3,0],[0,0],[$10,$7F]]).  add_m102c2.py APPLIED: 109 new + 7 re-aimed, mutate7.py 6,790 cases, deadcheck clean (backup
  mutate7.m102c2.bak).  kit 121, selftest 38, romscan CELLS 0 / STRONG 1 (allowed) / 470 files.
- **RUNNING (detached, both with watch.ps1):** the full bb suite (PID 23288 -> scratchpad/m102c2/bb_run2.log(.done); expect
  1,964) and the --affected battery (PID 13728 -> build/mutants/m102c2_aff.log(.done)).  A CronCreate poll :07/:27/:47 in
  the session (gone after a clear: then just `cat` both .done files).
- **Then:** survivors -> gate gaps or EQUIVALENT (add_m102c2.py's docstring); STATUS's M10.2c2 paragraph (above M10.2c's;
  its line 684-ish "next M10.2c2" -> M10.2d) and the "As of" line; commit (game.js, bb.test.js, SPEC, STATUS, TRAPS #356,
  M10-PLAN, next.md) -> next.md.  Next increment: M10.2d the pause ($8FF3 request 0, the spin, $9006's interrupts-off
  request 1 -- moved here from M10.2c2), solo.

## RESTART HERE (2026-10-14b, M10.2c THE MAIN LINE'S REQUESTS AND WAITS -- COMMITTED fa8e0df, its --affected battery CLEAN (689/689); next: M10.2c2 the interrupts-off sites and the in-play waits, SOLO)

- **M10.2c WRITTEN** (SPEC "The requests and waits on the main line", M10-PLAN "M10.2c DONE", STATUS's M10.2c paragraph,
  TRAPS #353..#355 -- all written; the commit's numbers still to fill):
  - web/game.js: `mwBegin / mwTail / mwWall / mwMark / mwRun / mwIns / mwRet` (beside hand128*): `$8E05` / `$8E0A` an
    instruction at a time on step()'s ledger, `mwWall(t) = t + isrCost - (span-1)*FD`; the request's DI window
    `[DI+1, RET end]` on diWindows (`mwLost`).  Sites: BB_TEXIT.ARM128 ('m7' mark, 'rq' -> mwBegin(7, $97B4)), frontFrame
    and step()'s pass loop run `mwRun` while `this.mw`; r1tBegin's END less BB_M128.RET48 (10) + refusal; r1tStep and the
    'hp' case call `mwTail` ($98F5 wait+1 / $98FC 1 / $9901 6); roundBanner's constant less RET48; step()'s game over
    $8CDC..$8CE4 request 5 + the overScreen carry branch (gridPhV nulled, windows dropped).  `hookPlan()` (a copy of the
    engine) feeds bbR1Map / bbLrMap each gate-closed ISR's hook (wall(o, isrs); wall.hook), isrHook checks it
    (`hookPlanN`, `hookPlanBad`, `lim` = the final replay's isrs from r1Final / lrClock).  reset(): mw, mwCalls, mwLost,
    hookPlanned, hookPlanBad, hookPlanN.
  - test/bb.test.js: block "M10.2c" C1..C8 (source scratchpad/m102c/c_block.js; `python scratchpad/m102c/sync.py`
    copies it in; `node scratchpad/m102c/c_only.js` runs it alone ~18 s, FAILFAST=1).  All 8 pass; the whole suite
    passed 1,950/1,950 BEFORE the block went in (scratchpad/m102c/bb_run1.log) -- RE-RUN it (expect 1,958) after the
    hand battery restores game.js.
  - The Sonnet review (done): no ledger / DI / r1t / OFF bug; three hygiene defects fixed + gated (C6 stale phase and
    window, C7 the plan's limit).
  - Battery list: `scratchpad/battery/add_m102c.py` (147 new + 17 re-aims; `--dry` checks anchors; NOT yet applied to
    mutate7.py).  `python scratchpad/m102c/deadcheck.py` lists cases whose anchors are not once in game.js -- after
    applying add_m102c.py it must print only `cases N`.
- **Hand battery DONE** (08:19..08:54, scratchpad/m102c/handmut.log): 151 cases, 145 killed; survivors: five
  EQUIVALENT (moved to add_m102c.py's docstring with the reasons) and "the tail less the RET OFF too" (the older R1T
  gates' -- the --affected battery runs them).  add_m102c.py APPLIED: 142 new + 17 re-aimed, mutate7.py 6,681 cases,
  deadcheck clean (backup mutate7.m102c.bak).  Suites after: bb **1,958**, kit 121, selftest 38; romscan CELLS 0,
  STRONG 1 (allowed), 470 files.
- **The --affected battery (09:19..10:00): `LISTED 689  KILLED 689  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0
  CRASHES 0  MISSES 0 -- 41.4 min on 20 workers`** (build/mutants/m102c_aff.log).  COMMITTED fa8e0df (game.js, bb.test.js,
  SPEC, STATUS, TRAPS #353..#355, M10-PLAN).  Nothing running; no cron.
- **Next: M10.2c2 (SOLO; no reviewer -- the blocking machinery is M10.2c's, reviewed)**: the request sites in play made
  with the interrupts OFF -- `$887D` (HEART, 4), `$891A` (potion / level skip, 3), `$94D5` (EXTEND, 2), the unpause `$9006`
  (M10.2d's pause pairs with it) -- mwBegin with iff 0 (the row's IFF column; no DI window to lose, the request's EI
  moves the acceptance one instruction on: M10-PLAN 1.6); and the waits inside play blocks -- `$8991` (treasure room:
  3's pass then 4), `$953C` (after EXTEND: 2's pass then 3), `$8E77` / `$8E8A` / `$8E95` (boss defeat: 3, wait, 2) and
  `$8E98`'s `$9573` delay that the request's A = $10 / B = $7F lengthen (~44.9k T).  Each lives inside an existing block
  model (the potion's, EXTEND's lazy block, the boss death $8E3A..) -- read how each block runs on the frame clock first.
  GATES can only be unit / structural there: C4 already re-makes these sites' interrupts-on requests at their machine T;
  add the iff-0 rows ([840,69413,$891A,3,1,0,577], [840,68416,$887D,4,1,0,577], [840,2217,$94D5,2,1,0,577],
  [1256,95,$9006,1,0,0,577]) and the waits' TICK counts (a wait counts ticks: the potion scene's 243,034 turns / 82
  frames etc.) -- the poked scenes' play before the sites is the 48K port's (C2's partings), so not record for record.
  Same rhythm: engine -> gates (scratchpad/m102c2/, a c2_block like c_block + sync) -> hand battery -> add list ->
  --affected -> docs -> commit -> next.md.
- **Before M10.4's FULL battery** (unchanged): tools/mutants.py's `prepare` / `cover` (`subprocess.run(... text=True ...)`,
  ~lines 465 / 480) need `encoding='utf-8', errors='replace'`.

## RESTART HERE (2026-10-14a, M10.2b THE SOUND HOOK IN THE GAME'S INTERRUPT -- COMMITTED 7625bc5, its --affected battery CLEAN (533/533); next: M10.2c the request sites and waits in play, SOLO + ONE Sonnet reviewer)

- **M10.2b DONE** (the plan's "b. the ISR hook"; SPEC "M10 -- the 128K branch", the new subsection "The sound hook in the
  game's interrupt"; M10-PLAN "M10.2b DONE"; STATUS's M10.2b paragraph and item 7):
  - web/game.js: `isr()` under m128 calls `isrHook()` after `isrD` (the 48K's program replayed): `$8D8F CALL $8DC4` at
    plain `isrPlain - BB_SEG.EPILOGUE`, on the wall clock at the acceptance phase + that + the waits so far (D0); the
    hook's T replaces HOOK48 in `isrPlain` (`isrPlain += hk - (isrD - D0) - HOOK48`), `isrD` re-replayed with the hook's
    OUT I/O cycles; label `simFrame + 1` (the interrupt begins the NEXT frame) unless `isrNow` (hand128Done's late one,
    its own frame); the trace's isrs row [label, acceptance, T, hook T, ticked]; `hookIsrs` counted; m128 with no engine
    refused by name.  `soundHook(at, o, label)`: the full `$8DC4..$8E04` (the theme's HURRY / alive-7 / cadence `$8DE0`
    paths, a skip leaving the busy byte, `hookSkips`), the trace's `hooks` rows; `o` = its plain offset on the ISR's
    program (null in the hand-over).  `ayOut(v, pc, t, o)`: with `o`, the OUT's four 1-T I/O cycles (8..11 T in, class 2)
    go on `this.ip`.  `frontFrame` keeps `gridPhV = tframe - budget` when the frame ends with the front end up (the
    title's and release's acceptance phase; was BB_ISR_ACCEPT's 4).  `hand128Done`'s late interrupt: `isrNow`,
    `gridPhV = t + EI_NEXT[1]`, spends `isrCost` (was GAME_ISR_T).  reset(): `isrNow`, `hookIsrs`, `hookSkips`.
  - tools/ay128flow.py: the `hooks` record ([label, frame, t, $FED4, $904D, $8DB7, $FECA, $8DE0, $8E06] at each $8D8F
    inside an ISR) -- recaptured (~4.5 min): every other record identical (checked against the old file).  WHY (TRAPS #350):
    p1's ISR 1697 -- `$ABA8` (the player's respawn, in `$AA60`'s pass) clears the HURRY latch before the hook and `$9059`
    sets it again before the next boundary (scratchpad/m102b/latch1697.py, a write watch).
  - test/bb.test.js: the M10.2a block's helpers (M102A) gained `init` and `hooks`; H4 / H5 now compare the hooks rows and
    run THROUGH the title's first interrupt (span's window ends at its end; H4's counts 83 interrupts, 104 AY writes; the
    busy byte after it 0).  NEW block "M10.2b" B1..B5 (source scratchpad/m102b/b_block.js; scratchpad/m102b/sync.py copies
    h_block.js + b_block.js over bb.test.js's section; `node scratchpad/m102b/b_only.js` runs B1..B5 alone ~3 s,
    `node scratchpad/m102b/hb_only.js` B then H ~10 s, FAILFAST=1): B1 the title record for record $970E -> request 7
    (p1 21 interrupts / 21 hooks / 21 ticks / 42 OUTs / 34 AY; the skip scene 26; the skip as it ships, df -255) and the
    boundary states; B2 soundHook over all 10,543 hooked interrupts (stubbed tick) + edge rows; B3 the hook in play ISRs of
    the 48K's real load flipped to m128 (465 odd, 578 even: OUT waits 6/6 and 0/10; 467 a skip) -- cost, isrD, isrPlain,
    program, OUT rows, tick, the whole hooks row; B4 OFF never hooks + isracc 400..409's phases; B5 the late interrupt.
  - Suites: bb **1,950**, kit **121**, selftest **38**; romscan CELLS 0, STRONG 1 (allowed), 470 files.
  - Battery: +78 cases (`scratchpad/battery/add_m102b.py`, backup mutate7.m102b.bak; its docstring lists the two predicted
    EQUIVALENT left out) and the TEN M10.2a cases whose lines M10.2b rewrote RE-AIMED onto the new lines, labels kept:
    **6,678 cases, 0 dead**.  Hand battery FIRST (`scratchpad/m102b/handmut.py`: each case against the B blocks, then
    the H blocks -- `hb_only.js`, FAILFAST; `--only` / `--from N`): 85 of 88 on the first pass, the three survivors gate
    gaps, closed (B3 compares the whole hooks row -- 578 has three alive; B2's alive edge rows 6 / 8 / 86, CP 7 / JR z
    being equality and the tally's 86 reachable; B4: every interrupt accepted inside the INT window, the drain's carry
    632,647 kills frontFrame's phase kept past the front end) -> 88 of 88.  WINDOWS REFUSED ONE WRITE of web/game.js
    mid-run (Errno 22) and the runner's restore with it: game.js was left mutated and was restored from
    scratchpad/m102b/game.js.pre_hand (checked byte for byte); handmut.py now retries every write.  **The --affected
    battery, 00:26..01:05: `LISTED 533  KILLED 533  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0  MISSES 0
    -- 39.5 min on 20 workers`** (build/mutants/m102b_aff.log: 78 new, 350 on anchor lines, 105 by killing block).  Its
    .err holds the known cp1252 reader-thread error.  Nothing running; the poll cron deleted.
  - Docs: SPEC subsection; M10-PLAN; STATUS; TRAPS #350 (a boundary row is not what a late reader saw), #351 (a
    provisional constant is safe only while nothing reads its error), #352 (a sum-only gate cannot see a split).
- **Declared / not yet (M10.2c..d)**: under m128 after '1' the title's 5 plays on (no request site: the release's $97B4
  request 7, round 1's $98F5 wait, every other site); play under m128 is the 48K's flow plus the hook; the pause.
  The release's leave frame and the round advance's drain under m128 take BB_ISR_ACCEPT's 4 (as OFF does).
- **M9.2 closed:** the owner checked Alt+P / Alt+Q in the browser (2026-10-14): both work, nothing found.
- **Next: M10.2c -- every request site and wait in play (SOLO + the ONE Sonnet reviewer: new blocking machinery in
  step())** -- the plan's c.: `$8E0A`'s compare / store / RET z (35 T) at every site ($97B4 7, $98F5 / $98FC 1, $9901 6,
  $887D 4, $891A 3, $8991 3+wait+4, $94D5 2, $953C wait+3, $8E77 / $8E8A / $8E95, $8CE4 5, the unpause $9006), the DI
  window $8E10..$8E29 (lost 1..516 T in: di_window), the EI, the registers left (A $10, BC $7FFD: $8E98's delay);
  `$8E05`'s 23-T spin with the main line blocked while ISRs run (round 1's 223-frame wait: the player walks, the
  enemies stand, the timers run); a wait counts TICKS.  Gates from the flow's p1 / p2 / idle / potion / heart / extend /
  boss / alive7 scenes record for record (marks, reqs, ereqs, waits, isrs, hooks, ticks, p7ffd, ay, passes).  The hook
  in isr() is now exact wherever the port's play is the machine's, so M10.2c's gates can run whole scenes.  The
  increment's rhythm as M10.2a / M10.2b: oracle -> engine -> gates -> hand battery (a handmut.py like m102b's, writes
  retried) -> the list (an add_m102c.py like add_m102b.py) -> --affected battery (the PowerShell command and the
  watch.ps1 + cron poll in the M10.2a section below) -> docs -> commit -> next.md.
- **Before M10.4's FULL battery** (unchanged): tools/mutants.py's `prepare` / `cover` (`subprocess.run(... text=True ...)`,
  ~lines 465 / 480) need `encoding='utf-8', errors='replace'`; a runner change makes the full run due anyway.

## RESTART HERE (2026-10-13f, M10.2a THE 128K COLD START AND HAND-OVER -- COMMITTED cc245b6, its --affected battery CLEAN (521/521); next: M10.2b the sound hook in isr(), solo)

- **M10.2a DONE** (the plan's "a. the cold start"; SPEC "M10 -- the 128K branch", the new subsection "The cold start and
  the hand-over in the engine"; M10-PLAN "M10.2a DONE"):
  - web/game.js, before the class beside BB_SPINE: `BB_M128` (LOAD = the 128K load's 14 bytes, REPPER 2, BC $0759,
    HAND_PH 1051, COLD = the 128K cold start's access program, LEG = its marks' plain offsets, SEED = the busy byte $8E06
    = 1 and the cadence $8DE0 = 2, HOOK48 27), `bbCold128Prog`, `bbColdT128(phase, upto)`, `bbIo7ffd(t)` (OUT ($7FFD)'s
    four 1-T I/O waits).  In BB_Game: `m128` (default false; set before ctrlBoot / reset), `skipPhase` (= HAND_PH),
    `this.ay = { log, trace }` (log rows [frame + t / 69,888, reg, val]; trace null, a gate sets one), `ayEngine`;
    reset() lays LOAD + SEED under m128, coldStart()'s default A is $80 under m128; coldStart(M128) runs the leg
    (legDisplay + `ayEngine = new BB_Ay(BB_Ay.bank1(legBytes()))`) where it threw; feScanPath's REPPER override;
    probeOpen -> 'skip128' (skip128(): to skipPhase, on an integer T, the next frame's after its interrupt if past it);
    probeEnd's forced BC; handOpen -> hand128Open; handIsr -> hand128Int; ctrlFrame's two branches; hand128Open / Int /
    Chk / Run / Ins / Ret / Isr / Swap / Done, soundHook (its NON-THEME path only), ayOut / ayTick / ayAt / ayMark.
    Exports BB_Game.M128 / coldProg128 / coldT128 / io7ffd.
  - THE SWAP IS AT $8CCA (hand128Swap), not $970E as the 48K's handDone: what follows reads and writes the world.  It
    carries the frame clocks, the sound log, fePast (incl. probeAt / probeEndAt), spineA / probeBC / probeE, handLost,
    tframe, ctrl / hand; the black screen with the leg's display bytes over it (AT ONCE, declared).
  - tools/cold128.py (NEW; capture | verify | emit, ~30 s) -> build/cold128_fixture.json (registered `cold128`, ship
    false): the 128K cold start's program (216,651 T plain, 48,391 accesses; the replay exact at 480 phases + the real
    load, the skip and p4p3), 'repper' (ctrlmenu's 24 histories with $5C0A = 2), 'io7ffd' (OUT ($7FFD) at 761 phases;
    the 4th wait non-zero at 54).  verify MATCH.
  - tools/ay128flow.py: FIXTURE -> build/ay128flow_fixture.json (`git mv` from build/pending/, registered `ay128flow`,
    ship false); skip_sweep rows gained [busy byte at the wait, its turns]; recaptured (4.3 min: scenes, hook, di_window
    unchanged).
  - test/bb.test.js: FIVE top-level blocks "M10.2a H1..H3" (the load, REPPER, the cold T + bbIo7ffd), "H4" (p1 / p2 /
    idle record for record + the frames' sound state), "H5" (the skip: natural phase, as shipped, 64 phases, the clock's
    edges), "H6" (the DI window at 179 offsets + the not-taken request), "H7" (the boundary OFF, the late / early
    interrupt rules, ON-vs-OFF sound, cursor_kempston's key table) -- source scratchpad/hand128/h_block.js
    (scratchpad/hand128/sync_block.py copies it in), `node scratchpad/hand128/h_only.js` runs them alone (~6.6 s;
    FAILFAST=1 stops at the first FAIL).  M7.40's (h) and (h2) re-aimed: the leg modelled (legOk), no throw.
  - Suites: bb **1,945** (1,938 + H1..H7), kit **121**, selftest **38**; romscan CELLS 0, STRONG 1 (allowed), 470 files.
  - Battery: +168 cases (`scratchpad/battery/add_m102a.py`, backup mutate7.m102a.bak; its docstring lists the predicted
    EQUIVALENT left out) + M7.40's dead case on the old throw RE-AIMED ("the 128K leg not run"): **6,600 cases, 0 dead,
    0 ambiguous**.  Hand battery FIRST (scratchpad/hand128/handmut.py, FAILFAST): 167 of 169 killed by the M10.2a
    blocks alone; "the leg writes no display" and "the 128K hand-over on a 48K's $80 too" are for M7.40 (h) and H-d(f)
    (the battery: both killed there).  It found two equivalents (TRAPS #347: IFF is 1 at every check on the hand-over's path; the frame's carry
    takes a debt past the boundary as the chunks do) and one gate gap (the wait's busy byte: the flow's sweep now
    records it and the turns).  **The --affected battery, 20:08..20:42: `LISTED 521  KILLED 521  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0  MISSES 0  -- 34.5 min on 20 workers`** (build/mutants/m102a_aff.log: 169 new, 281 on anchor lines, 71 by killing block).
    Nothing running; the poll cron deleted.  The command (PowerShell): `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process
    python -ArgumentList 'tools/mutants.py','--affected','--jobs','20' -RedirectStandardOutput build/mutants/<name>.log
    -RedirectStandardError build/mutants/<name>.log.err -WindowStyle Hidden -PassThru` + `Start-Process pwsh -ArgumentList
    '-NoProfile','-File','scratchpad/battery/watch.ps1',"$($p.Id)",'build/mutants/<name>.log' -WindowStyle Hidden`, then
    a CronCreate poll (:07 / :27 / :47) of `<name>.log.done`.  (watch.ps1's summary check now matches the runner's dated
    summary line -- it read `summary_line False` on tonight's clean run.)
  - Docs: SPEC subsection; M10-PLAN; STATUS; TRAPS #346 (a count in a doc: 20 of 64 was 19), #347 (equivalents found
    before the battery), #348 (the flow's frames IFF column is sampled after the acceptance), #349 (a carry-over gate
    whose input is the default); "20 of 64" corrected to 19 in SPEC, M10-PLAN, STATUS, the tool's docstring and the
    M10.0c section below.
- **Declared / not yet (M10.2b..d)**: under m128 the TITLE IS SILENT (sound 5 requested at $970E, never ticked: isr() has
  no hook yet); a late interrupt at $970E (the reset half's end at T < 11) runs the 48K's isr(); the leg's display
  writes land at $8CCA at once; play under m128 is the 48K's flow (no request site, no wait, no round-1 freeze yet).
- **Still open from M9.2:** the owner's in-browser check of Alt+P / Alt+Q (the owner, 2026-10-13: tonight) -- anything it
  finds goes first.
- **Next: M10.2b -- the sound hook in isr(): the title and play under m128 (SOLO: the flow oracle measured every ISR, its
  hook's T by path and every AY row; the work is applying it.  The ONE Sonnet reviewer is kept for M10.2c, the blocking
  waits in step() -- the plan's "new blocking machinery").**
  1. isr() under m128: after the parity branch, `$8D8F CALL $8DC4` -> soundHook at the CALL's wall T: the ISR's
     acceptance phase (isrAt) + its T to $8D8F with its contention so far; the ISR's cost = isrPlain - HOOK48 + the
     hook's T, its two OUT ($7FFD)s' I/O checks on the ISR's access program (this.ip: four 1-T accesses each at their
     plain offsets -- as the cold start's program records them), so isrD replays them with the rest.
  2. The theme's cadence in soundHook: $FED4 == 1 -> $904D (HURRY latch) set -> tick; else $8DB7 >= 3 and $FECA == 7 ->
     tick; else the counter $8DE0 (2 -> 1 tick, 1 -> 3 skip, 3 -> 2 tick), stored either way, a skip returning (RET z)
     with the busy byte untouched.  The hook's own T by path from the fixture: 175 (not the theme), 199 (the HURRY
     path), 253..289 (the theme's), 150 / 172 (a skip) -- derive each from the instructions (the transliteration) and
     gate them against the flow's isrs rows (hook T - the tick's T).
  3. THE AY ROWS' FRAME: step() runs the ISR that begins frame k at the END of step k (its ledger: isrStart = budget);
     the rows belong to frame k (simFrame + 1 then) at the machine's acceptance phase + the offsets -- not at the
     ledger's budget.  Decide and gate against the flow's ay rows.
  4. The title: sound 5 at full rate from $970E; the title's paint has ISRs inside it (frontFrame / tpaint "land where
     the machine's do") -- each needs the hook; hand128Done's late interrupt too (GAME_ISR_T is the 48K's 488).
  5. Gates from the flow: p1 from $970E to request 7 ([429, 2120] .. [450, 957]) record for record (every ISR's
     acceptance, T and hook T, every tick, AY row and OUT ($7FFD)); the cadence by a unit drive of soundHook over p1's
     play frames rows (cur, cadence, hurry, $8DB7, alive; the hook's own T per path).  OFF byte-identical.
  Then M10.2c (every request site and wait in play -- the round-1 freeze; ONE Sonnet reviewer), M10.2d (the pause),
  M10.3 (the page: the switch Alt+M, the mixed output), M10.4 (README, the FULL battery after the runner's cp1252 fix).
- **Before M10.4's FULL battery** (unchanged): tools/mutants.py's `prepare` / `cover` (`subprocess.run(... text=True ...)`,
  ~lines 465 / 480) need `encoding='utf-8', errors='replace'`; a runner change makes the full run due anyway.

## RESTART HERE (2026-10-13e, M10.1 THE AY ENGINE IN JS -- COMMITTED 2b5ecdb, its --affected battery CLEAN (283/283); next: M10.2 the 128K branch on the 48K clock, solo + ONE Sonnet reviewer)

- **M10.1 DONE** (the plan's "the engine in JS, not wired to anything"; SPEC "M10 -- the 128K branch", the new subsection
  "The engine in JS"):
  - web/game.js: `BB_AY` (the layout, the sound table, the request's six LDI destinations, `SLOTS` C / A / B with every
    state operand's address) and `class BB_Ay` BESIDE BB_Rng, BEFORE the game's class (TRAPS #345: the censuses' text
    slice); `bbAyBytes(A)` a column-0 function AFTER the class (the asset read must be inside the slice); exports
    `BB_Game.AY / Ay / ayBytes`.  `new BB_Ay(bank)` over a 16K Uint8Array that IS bank 1 ($C000..$FFFF; M10.2's game
    will own it); `BB_Ay.bank1(bytes)` = the leg's bank (the bytes at $C350, zero elsewhere).  `request(n)` / `tick()`
    -> `{ writes: [[reg, val, dt], ...], a, t }`, dt = the OUT ($BFFD)'s first T from the entry; written instruction for
    instruction (each `t += n` names its instructions), so the per-write dt came out of the instructions' own T.
    `info()` = { ticks, requests, refusals, refusal }.
  - THE REFUSAL (TRAPS #344): a fetch below $C000 (HL 16-bit: past $FFFF reads $0000) throws an internal sentinel that
    tick() catches: every store of the call put back from `undo` ([index, old] pairs, LAST FIRST), result `{ writes: [],
    a: 0, t: 0, refused: { tick, slot, addr } }`, counted.  The brief said "outside $C350..$D263"; bank 1's other bytes
    are the machine's zeros, so the boundary is bank 1's ($BFFF refused, $C000 read: AE6 drives both edges).
  - The bytes: `tools/extract_ayengine.py extract | verify` (~3 s) -> build/ay_engine.json, port.json `aybytes`
    (required, shipped): the tape's $E6A8..$F5BB, asserted equal to bank 1 after the game's own leg (ayengine.fresh48)
    and to the fixture's bank1.sha1 `0b045e9f...`.  build/pending/ayengine_fixture.json MOVED to build/ (`git mv`),
    registered `ayengine` (ship: false); tools/ayengine.py's FIXTURE follows (`verify` MATCH).
  - test/bb.test.js: the last block "M10.1" AE1..AE7 (scratchpad/m101/ae_block.js its source; `node
    scratchpad/m101/ae_only.js` runs it alone against the built page in 0.7 s): the asset = the machine's bank; all 13
    streams event for event (47,338 events: 86,844 ticks, 248 requests, 101,905 writes); every end SHA-1; the refusal at
    tick 256 (slot C, $0000; the bank = the oracle's stop state; the next tick refused again); the boundary (29 bank bytes
    written, all state; $CFFF the master's shape never: its 4,880 retriggers write 0); bank 1's edges driven ($BFFF,
    $C000, the $FFFF wrap, slot A's refusal undoing slot C's note); the request's A eight bits (1..255 against the table
    walk 12(A-1) MOD 256) and each call's undo record its own.  EXACT ON THE FIRST RUN.
  - Suites: bb **1,938** (1,931 + AE1..AE7), kit **121**, selftest **38**.  romscan CELLS 0, STRONG 1 (allowed), the
    new JSON's base64 among the 468 files.
  - Battery: +143 cases (`scratchpad/battery/add_m101.py`, backup mutate7.m101.bak; its docstring lists the predicted
    EQUIVALENT left out: wr()'s `& 0xFF` (a Uint8Array keeps the low byte), the counter's and loop count's `& 0xFF` (a
    truth test and a Uint8Array store), the catch's re-throw guard, the END's / restart()'s store order): **6,432
    cases, 0 dead, 0 ambiguous**.  Hand battery FIRST (scratchpad/m101/handmut.py: each case against the AE block
    alone): **143/143 killed** (1 m 52 s).  **The --affected battery, 16:27..17:02: `LISTED 283  KILLED 283  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0
    CRASHES 0  MISSES 0  -- 34.6 min on 20 workers`** (build/mutants/m101_aff.log: 143 new, 140 on anchor lines).  Its
    .err holds the known cp1252 reader-thread error (M9.2's ” in the baseline's output; the verdicts come from JSON).
    Nothing running; the poll cron deleted.
  - Docs: SPEC "The engine in JS"; M10-PLAN M10.1 DONE (+ the stale "game.js line 5079" refs now name coldStart's
    $96B0 comment); TRAPS #344 (a refusal halfway through a routine leaves half its stores) and #345 ("the engine" is a
    slice of the page's text: three censuses read it); STATUS's M10.1 paragraph, item 7.
- **Still open from M9.2:** the owner's in-browser check of Alt+P / Alt+Q (the rig has no real keyboard) -- anything it
  finds goes first.
- **Next: M10.2 -- the 128K branch on the 48K clock (SOLO, ONE Sonnet reviewer: new blocking machinery in step(); the
  machine's behaviour is MEASURED -- the flow oracle answers every question, agents add nothing else).**  Split it, a
  commit and an --affected battery each (the owner's decisions: 128K default, Alt+M, scope (A) -- M10.3 wires the page):
  1. **M10.2a the cold start** behind BB_Game's `m128` (default OFF, OFF in every test world): the probe's answer $80
     (skipProbe or not; the skip must hand over at the probe's own phase 1,051 -- skip_sweep), the 128K load's 14 bytes
     (BANKM $5B5C = $10, $6000 = $10, twelve sysvars $5C0A..$5CC8, REPPER 2 -> the front end's key repeat), coldStart's
     128K leg replacing the throw (the display writes from `bbAyBytes`, invisible; the bank-1 copy into the game's
     `bank1`; the leg's T 185,957 on the 48K clock; no $969A patch), the hand-over: request 3, the $9575 delay with A =
     $10 / B = $7F (3,967 DJNZ), the $8CD7 wait, request 5.  MOVE build/pending/ay128flow_fixture.json to build/ and
     register it (`ay128flow`, ship: false) with the first gate that reads it (TRAPS #342).
  2. **M10.2b the ISR hook** at the end of every ISR ($8D8F CALL $8DC4) on the ISR's program: the cadence $8DE0 (2 in 3
     under the theme; full rate under HURRY UP $904D or ($8DB7) >= 3 with $FECA == 7), the two OUT ($7FFD), the tick and
     its T, the busy byte $8E06, the AY rows -> `game.ay.log` [frame + t / 69,888, reg, val] (t = the hook's place + the
     tick's entry + dt).
  3. **M10.2c every request site and wait**: $8E0A's compare / store / RET z (35 T), the DI window $8E10..$8E29 (548 T:
     lost 1..516 T in, di_window), the EI, the registers left (A $10, BC $7FFD: $8CD2's and $8E98's delays); $8E05's
     23-T spin on the frame clock with the main line blocked while ISRs run (round 1's 223-frame wait: the player walks,
     the enemies stand, the timers run); a wait counts TICKS.
  4. **M10.2d the pause**: request 0's mute, the spin, the unpause's re-request (the sound restarts).
  Gates per part from the flow fixture (its scenes p1, p2, idle, skip, potion, heart, extend, boss, alive7), and the
  boundary: OFF byte-identical to today (the whole 64K and every log), every existing gate runs OFF.  Wiring the engine
  INTO the class makes its new methods join the UNCALLED / reachability censuses -- on purpose, listed (TRAPS #345).
- **Before M10.4's FULL battery** (unchanged from M9.2): tools/mutants.py's `prepare` / `cover` (`subprocess.run(...
  text=True ...)`, ~lines 465 / 480) need `encoding='utf-8', errors='replace'` (node's ” decoded as cp1252 killed a
  reader thread in M9.2's run); a runner change makes the full run due anyway.

## RESTART HERE (2026-10-13d, M9.2 THE PAGE'S ALT KEYS -- COMMITTED 5a77f0c, its --affected battery CLEAN; the owner's M10 decisions RECORDED; next: the owner's browser check, then M10.1, solo)

- **THE OWNER ANSWERED (2026-10-13), all three M10 decisions as recommended** (recorded in memory:
  bubble-bobble-port-decisions): (1) the page boots the **128K** by default (OFF = the faithful 48K page); (2) the switch is
  **Alt+M**, rebooting into the other machine, remembered like the high score (a function key was considered; browsers bind
  them); (3) the scope is **(A)**: the 128K branch as it is, waits and all.  And: **the page's key combos are Alt+**.
- **M9.2 (the owner's request, ahead of M10.1): Alt+Q quits (was Shift+Space), Alt+P toggles the pause (was Ctrl to pause,
  Shift to resume).**  WRITTEN, suites green (bb **1,931** = 1,922 + AK1..AK9, kit 121, selftest 38), NOT COMMITTED:
  - FOUND first: the quit and the pause are the GAME'S OWN keys -- BREAK = CAPS SHIFT + SPACE read by the main loop each
    pass ($8D63 / $8D6F, the engine's breakHeld()), the pause SYMBOL SHIFT ($8FE7) and its release CAPS SHIFT (the spin
    $8FFB) -- and the kit's keymap makes them PC Shift+Space, Ctrl, Shift.  So M9.2 is a page INPUT layer, ADDED, the
    faithful mapping its OFF (house rule 5); the engine is untouched.
  - web/template.html: `BB_PAGE.altKeys` (default true); `BB_ALT = { HOLD: 300 }`; `bbAltKeys(game, on)` -> {key(e),
    kb(keyboard), tick(), info()}; `const altkeys` after `fullscreen`; the keydown listener `fullscreen.key(e) ||
    altkeys.key(e)`; the loop `step(){ game.step(altkeys.kb(keyboard)); altkeys.tick(); hiscore.tick(); }`; the caption
    'pause Alt+P (again resumes), quit Alt+Q' (OFF: the old); `__PORT__` exports BB_ALT, bbAltKeys, altkeys.
    The view (kb() in the game's world, ON): port() = the Keyboard's half-rows with CAPS (row 0 bit 0) and SYM (row 7
    bit 1) UP; hold 'pause' -> SYM down; 'resume' -> CAPS down, SPACE up (no BREAK in the pass it resumes); 'quit' ->
    CAPS and SPACE down.  key(): Alt+P / Alt+Q only (a repeat swallowed, uncounted); outside play (ctrl, front, overScreen)
    counted `ignored`; Alt+Q -> 'quit'; Alt+P -> 'resume' if game.paused else 'pause'.  tick() after each step: taken
    when the game paused / resumed / reached overScreen, else let go at HOLD frames (`expired`).
  - test/bb.test.js: the last block "M9.2" AK1..AK9 (scratchpad/m92/ak_block.js is its source; `node
    scratchpad/m92/ak_only.js` runs it alone against the built page in ~3 s, PAGE_RUN extracted from the suite).
  - Battery list (scratchpad/battery/mutate7.py, gitignored): +45 (`scratchpad/battery/add_m92.py`, backup
    mutate7.m92.bak) and 6 RE-AIMED (their anchor lines rewritten: the BB_PAGE line, step(), the keydown listener --
    "M7.44 review: the page steps the engine WITHOUT its keyboard", "M7.64: padKempston defaults ON", "M9.1:
    saveHiScore OFF by default", "M9.1: the page's loop never ticks the high score", "M9.1: Alt+Enter not stopped...",
    "M9.1: Alt+Enter's default not prevented"): **6,289 cases, 0 dead, 0 ambiguous**.  Hand battery FIRST
    (scratchpad/m92/handmut.py: each new case against the AK block alone): **45/45 killed**.
  - Docs written (uncommitted): README's declared departures (the Alt+P / Alt+Q bullet), STATUS's M9.2 paragraph.
  - **COMMITTED `5a77f0c`.  The --affected battery, 10:26..11:10: `LISTED 140  KILLED 140  SURVIVORS 0  DEAD ANCHORS 0
    TIMEOUTS 0  BROKEN 0  CRASHES 0  MISSES 0  -- 44.3 min on 20 workers`** (build/mutants/m92_aff.log: 45 new, 95
    on anchor lines).  Nothing running.
  - Noted, not fixed (a runner change makes a full run due -- do it before M10.4's FULL battery): tools/mutants.py's
    `prepare` / `cover` calls (`subprocess.run(... text=True ...)`, ~lines 465 and 480) decode node's UTF-8 as
    cp1252, and AK9's closing curly quote (byte $9D) killed a reader thread (m92_aff.log.err).  Their results come
    from JSON files -- no verdict touched -- but add `encoding='utf-8', errors='replace'` to both.
  - The runner's "A FULL RUN IS DUE: changed since the last full run: test/rig.js" is bookkeeping: M9.1's full run
    ran with the rig change uncommitted and recorded the HEAD before it.  The next full run (M10.4) clears it.
- **Next, in order:**
  1. The owner's in-browser check of Alt+P / Alt+Q (the rig has no real keyboard): anything it finds first.
  2. **M10.1, the engine in JS (solo)** -- the brief in the section below.  M10.3 will put Alt+M in the same listener
     family (BB_PAGE / bbAltKeys' neighbour), and its caption beside Alt+P / Alt+Q.

## RESTART HERE (2026-10-13c, M10.0 DONE -- THE ORACLES; next: M10.1 THE ENGINE IN JS, solo; the owner's three decisions before M10.2)

- **M10.0 is DONE** (the plan's "the oracles", docs/M10-PLAN.md section 4), five commits this session:
  - `dc20037` (kit `3e81ac1`) M10.0a the two machines: `Harness(paging=0x10)` and `tools/harness128.py`; selftest 38.
  - `9b7945c` M10.0b `tools/ayengine.py` -> build/pending/ayengine_fixture.json (the engine, direct).
  - `8e491f2` M10.0c `tools/ay128flow.py` -> build/pending/ay128flow_fixture.json (the flow on the port's clock).
  - `90d638d` M10.0d the docs: SPEC "M6 sound" corrected + the new SPEC section **"M10 -- the 128K branch"** (the
    reference for M10.1/M10.2: read it first), TRAPS #341..#343, STATUS, M10-PLAN's M10.0 answers.
  - next.md commits between.  The section below this one has every detail (formats, measurements, why build/pending/).
- Suites: bb **1,922**, kit **121**, selftest **38**.  Battery: none this session (no game.js / bb.test.js change).
  **Nothing running.**
- **The owner's three decisions (M10-PLAN section 3) are STILL PENDING** -- not asked as a blocking question this session
  (M10.1 does not need them); put to the owner in the end-of-session report.  M10.2 needs decision 3 (the scope:
  recommended (A), the 128K branch as it is, waits and all); M10.3 needs 1 (the default machine: recommended the 128K)
  and 2 (the switch: recommended a key, Alt+M, rebooting into the other machine, remembered like the high score).
  If the owner has answered in chat, record the answers here and in memory (bubble-bobble-port-decisions) first.
- **Next: M10.1 -- the engine in JS, not wired to anything (SOLO: a transliteration whose oracle is exact and complete;
  agents add nothing).**  Read first: SPEC "M10 -- the 128K branch", M10-PLAN 1.2, scratchpad/ay_static/model.py (agent
  A's Python model: matches the machine exactly; the JS is a transliteration of it), tools/ayengine.py's docstring.
  1. `web/game.js`: the engine over its OWN 16K bank-1 array (`Uint8Array(0x4000)`, addresses $C000..$FFFF), its state in
     its own self-modified operand bytes and the words $D1E2..$D1ED exactly as the machine keeps them (model.py's SLOTS
     table: counter / pointer / loop count / loop start / retrigger flag / shape / restart pointer per slot C, A, B), so
     history (the $D13F shape byte) carries over as the bytes do.  `request(n)` -> {writes [[reg, val, dt], ...], a, t}
     and `tick()` -> the same.  **dt per write is new work**: model.py has only per-path T SUMS; the JS needs each OUT
     ($BFFD)'s first T from the call's entry -- derive the per-instruction T along each path (the engine's code is in
     scratchpad/ay_static/engine_code.dis; the fixture's dt values are the gate).  A fetch outside $C350..$D263 (a fresh
     engine's tick 256 reads $0000) is a COUNTED REFUSAL (TRAPS #304, #341), never a ROM read, never a throw.
  2. The engine's bytes: a NEW shipped asset (tape-derived JSON like tape_bytes.json): the 3,860 bytes the cold start's
     leg copies (build/image_tape.bin $E6A8..$F5BB -> bank 1 $C350..$D263; the rest of bank 1 zero).  A tool (e.g.
     tools/extract_ayengine.py) writes build/ay_engine.json and ASSERTS it equal to bank 1 after the game's own leg (as
     ayengine.py's fresh48 does) and to the fixture's bank1.sha1 (`0b045e9f44e55e0d5691dfd7eff2efe29eaacc11`, the fresh
     16K).  Register it in port.json (required, shipped -- the suite checks every asset the engine source reads is
     shipped).
  3. MOVE build/pending/ayengine_fixture.json to build/ and register `ayengine` (ship: false) in port.json -- AND the gate
     block that reads it in the same increment (the fixture guards, TRAPS #342).
  4. Gates (test/bb.test.js, CRLF -- edit with a Python script that keeps the endings): every stream of the fixture
     event for event (requests ['R', n, A, T, w], ticks [A, T, w], idle runs k), the end SHA-1 of the engine's 16K, the
     'none' and '0' streams' refusal at tick 256 (counted, the state before it equal); the boundary (no write outside
     bank 1's operand / word bytes).  Mutation cases (scratchpad/battery/mutate7.py, `scratchpad/m735_anchors.py` after
     every case edit) -> the battery `--affected --jobs 20` (Start-Process line in the M9.1 section below), then commit.
- **Then:** the owner's decisions -> M10.2 (the branch on the 48K clock; one Sonnet reviewer; its gates from
  build/pending/ay128flow_fixture.json, moved and registered then; carry REPPER 2, the skip at the probe's phase 1,051,
  the DI window) -> M10.3 (the page and platform.js; one Sonnet reviewer) -> M10.4 (the release docs, the FULL battery)
  -> (d) the README -> (e) the scrub (the owner's call).

## RESTART HERE (2026-10-13b, M10.0a..c -- THE MACHINES, THE DIRECT AND THE FLOW ORACLES -- COMMITTED dc20037 (kit 3e81ac1), 9b7945c, 8e491f2; next: M10.0d the docs, then M10.1, solo)

- **The owner's three decisions (M10-PLAN section 3) are STILL PENDING** -- not asked this session: M10.0 and M10.1 do
  not depend on them (M10.2 needs answer 3, M10.3 answers 1 and 2).  Put them to the owner when M10.1 is done, or
  sooner if the owner is around; the recommendations stand (default the 128K; Alt+M reboots into the other machine,
  remembered; the 128K branch as it is, waits and all).
- **M10.0a COMMITTED, port `dc20037`, kit `3e81ac1`** (tools only, no engine or test change):
  - `tools/harness.py`: `Harness(paging=0x10)` / `h.enable_paging(out7ffd)` -> `h.paging` (class `Paging`): an OUT
    decoding as $7FFD (port & $8002 == 0) swaps $C000..$FFFF with bank (value & 7) unless bit 5 locked it; an AY on
    $FFFD (latch; IN reads the register masked by `AY_MASK`) / $BFFD (data).  Logs `h.paging.p7ffd` [T, pc, value,
    applied], `.ay_log` [T, pc, reg, value], `.ay_reads`; `.unsupported` counts 'rom0' / 'shadow' / 'reg>15' (never
    modelled: the 48K ROM, frame, clock and contention stay).  `.bank(b)` reads any bank; `.page(b)`.  `save_state()`
    gains a 4th member when paging is on; `load_state` of a 3-tuple on a paging harness RESETS the banks.  T in a row =
    the OUT/IN instruction's first T (SkoolKit calls the tracer first); pc = the OUT's own address.
  - `tools/harness128.py`: `Harness128(snapshot=None|path|False, engine='py'|'c', state=None, out7ffd=None)` -- the
    recon's B harness made generic (B's game hooks NOT carried: $8D8F hook, $8E0A request, $8E05 wait, $CF80 tick,
    $D167 engine request, the frame_log of game bytes, gpeek via $9AE7 -- rebuild what you need with `add_hook` /
    `on_return` / `frame_hooks`; B's original is still scratchpad/ay128/h128.py).  snapshot None = port.json
    `z80.snapshot128` (build/boot128.z80).  Logs ay_log [frame, t, pc, reg, val, T, ctx] (ctx = `h.ctx`), ay_reads,
    ay_ignored, p7ffd_log [frame, t, pc, val, T, applied], spk_log, fe_count; `bank_peek/bank_poke`; `watch_bank(b)`.
  - selftest 34 -> **38** (t_harness_paging, t_harness128_machine, t_harness128_engines, t_harness128_hooks).
    Hand-mutated with scratchpad mut_shim.py (re-create: apply one replacement, run selftest, restore): shim 11/11,
    harness128 15/15 after three gaps closed.  `python tools/passacc.py verify` MATCH (the 48K tools unchanged).
  - docs: NOTES "Upstream", tools/README.md rows, CLAUDE.md's tools line (port and kit).
- **Line endings (measured with Python this session -- a Git Bash `grep $'\r'` check LIED):** CRLF in the working tree:
  web/game.js, test/bb.test.js, docs/SPEC.md, docs/NOTES.md, port.json, tools/README.md; LF: tools/*.py, next.md.
  Edit CRLF files with a Python script that converts and restores the endings (as this session did).
- Suites: selftest **38/38**; bb 1,922 / kit 121 not re-run (no page or test change).  Battery: none (no game.js /
  bb.test.js change).  **Nothing running.**
- **Next, in order (M10.0 continues, SOLO -- the machine answers each question directly; no agents):**
  1. ~~M10.0b~~ -- **COMMITTED 9b7945c**: `tools/ayengine.py [capture|verify]` -> **build/pending/ayengine_fixture.json**
     (1.2 MB, verify MATCH ~15 s).  13 streams: sounds '0'..'7' (request, then 3,000 ticks), 'none', 'chain1'..'chain4'
     (D's generator, 60 requests each).  Events: ['R', n, A, T, w] / [A, T, w] / an int k = k idle ticks (A 0, T 116, no
     write); w = [reg, val, dt, ...], dt = the OUT ($BFFD)'s first T from the call's entry.  'end_sha1' = bank 1's
     SHA-1 at the stream's end.  '0' and 'none' STOP at tick 256 (`rom_fetch` [256, $CF8C, $0000]: a fresh engine's
     pointers are 0; that tick's writes are ROM bytes, never recorded; end_sha1 is the state BEFORE that tick).
     Asserted: the plain simulator identical; harness128 from boot128 identical (bank 1, writes, A).  Measured: request
     428 T / 89 (n = 0); idle 116; largest tick 2,853 (sound 5's first).
     - **WHY build/pending/:** bb.test.js has two fixture guards (~line 14884: every build/*.json on disk registered in
       port.json or named in a PINNED list; ~line 1258's "EVERY test-only asset is READ by a check").  An oracle
       fixture without its gate fails one or the other (this session: 1920/1922 both ways).  So M10.0's fixtures wait
       in build/pending/ (the guard lists build/*.json only), and the increment whose gate reads one MOVES it to
       build/ and registers it in port.json (ship: false).  The tool's FIXTURE constant says so.
  2. ~~M10.0c~~ -- **COMMITTED 8e491f2**: `tools/ay128flow.py capture|verify` -> **build/pending/ay128flow_fixture.json**
     (1.9 MB, verify MATCH ~5 min).  The machine: `machine()` = world('boot') + paging + `load128_bytes()` (the 14,
     asserted); the probe's BC forced to $0759 at $FAE1 (or `skip`: at $F5C9 A := $80, PC := $F5CC).  The drive
     (`Flow`): every instruction, keys at ISR ends (front-end scan hold), keys ALSO at boundaries only inside the
     pause's spin $8FF6..$9009 (applied wherever IFF = 0 it MOVED the front end -- the probe 52,024 -> 2,240), pokes
     at ISR ends (values recorded in `applied`).  Records per scene (the docstring): frames (change rows), isrs [label,
     t, T, hook T, ticked], ticks, ereqs, reqs [frame, t, site, A, cur, iff, T], waits, ay [frame, t, reg, val],
     p7ffd, passes [frame, t], ldar, spk, marks, applied.  SCENES: p1 (1P: cold start, title, 7, the round-1 wait with
     RIGHT held, 1, cadence, pause/unpause, HURRY poked at 1400), p2, idle (game over 2272), skip, potion, heart,
     extend (pokes at 840), boss (round 80 by bossfree's route at 1240, HP 0 at 1700), alive7 (round 10 at 1240).
     MEASURED (the M10.2 design inputs):
     - the no-skip timeline: probe $F5C9 at 88, hand-over 344:1051, request 3 at 347, the cold-start wait 348..429,
       5 at 429, the title ring 438; '1' at 450 -> 7 at 450, the round-1 wait 516..739 (223 frames; 2P 221), 1 and
       the main loop at 739.  The theme ticks exactly 2 in 3.
     - **skip_sweep**: the page's skip lands at 64 phases -> 19 of 64 (27,300..46,956; '20' was written: TRAPS #346) NEVER WAIT (3 replaced by 5 at
       once; the title +4 frames, not +85).  The probe's own hand-over is pinned at phase 1,051 (waits).  So under
       M10, skipProbe must hand over at the probe's phase (1,051 into a frame), not at the CLS's end -- M10.2's design.
     - **di_window**: a taken request with IFF 1: the frame's interrupt taken at boundary <= the DI's first T, LOST at
       1..516 T into the window, taken at its end from 517 (DI .. RET = 548 T on the 48K clock).
     - **hook** per ISR on the 48K clock: theme tick ~617 T (383..2,549), skip 150..172, full-rate tick ~410..490
       (291..3,028); ~464 T an ISR under the theme.
     - REPPER: the 128K load's $5C0A = 2 (48K: 5) -- the engine's BB_MENU.REPPER = 5 is the 48K's; under M10 the
       front end's key repeat must use 2 (M10.2a).
  3. M10.0d -- SPEC: the corrections (M10-PLAN 1.8) in full and a new section "M10 -- the 128K branch".
  4. Then M10.1 (the engine in JS, solo: move build/pending/ayengine_fixture.json to build/, register it `ayengine`,
     ship: false, and its gate reads it), the owner's decisions, M10.2 (one Sonnet review; moves the flow fixture the
     same way), M10.3 (one Sonnet review), M10.4; then (d) the README, (e) the scrub.
  5. TRAPS to write at M10.0d: (a) an oracle stream that runs a routine past its first read of the ROM records
     ROM-derived values -- '0' ran 3,000 ticks through the ROM until its summary showed 152 "ends"; every engine
     stream now runs under a read watch that stops it; (b) a fixture without its gate fails the suite's fixture
     guards -- build/pending/.

## RESTART HERE (2026-10-13, THE M10 RECON DONE -- docs/M10-PLAN.md WRITTEN FOR THE OWNER; next: the owner's three decisions, and M10.0 the oracles, solo)

- **The recon** (the owner's "ultracode: M10 recon"): Workflow `m10-recon`, run `wf_31c47c26-0ae`,
  2026-10-12 23:57 .. 2026-10-13 01:30: 4 agents, 1.52M subagent tokens, 93 min.
  - A: the static engine reading and a Python model (scratchpad/ay_static/model.py, pred_0..7.json).
  - B: the project's FIRST 128K harness (scratchpad/ay128/h128.py), with its saved states (menu128 / cold128 /
    fresh128 / title1500 / main128_late / boss80_128_c ... .pkl) and captures (direct_0..7.json, scene_*.json).
  - C: the branch's other changes (scratchpad/branch128/, including pageshim.py: a $7FFD paging shim on the kit's 48K
    harness).
  - D: the cross-check (scratchpad/ay_cross/: diff, lockstep chains, cadence, selfcheck_d).
  - The full reports are in **scratchpad/m10_recon/** (A_static.json, B_ay128.json, C_branch128.json, D_cross.json),
    with the workflow script.  Subagents cannot write report files (the harness refuses them), so put the whole
    report into the schema.
- **RESULT:** A's model matches the machine EXACTLY, with 0 mismatches in writes, their order, A or uncontended T:
  - all 8 sounds x 3,000 fresh ticks;
  - 511,270 ticks in situ (2,018 requests, 9 scenes plus 5 random chains).
  
  D refuted six claims:
  - A12: 7 is the game-start tune and 5 the title;
  - A19: what HL holds after a taken request;
  - A22: on a 128K the cold-start wait ALWAYS happens;
  - B5: request 0 mutes until the sound's pass restarts;
  - C18: the largest tick is 2,853 T;
  - my scouting note: boot128 and boot48 differ in 14 bytes outside the display.
  
  Findings: docs/M10-PLAN.md section 1 (the engine, the sound map, the six waits, the cadence, the costs, the 128K
  machine's declared differences, the doc corrections).  The six waits include round 1's 221-frame frozen start.  The
  cadence is 2 frames in 3, at full rate under HURRY UP and in the alive-7 case.
- **Docs this session, commit `07725cf`:** docs/M10-PLAN.md (new); a correction pointer in SPEC "M6 sound" (after line 5008); TRAPS
  #150's correction; STATUS item 7.  No code.  Suites unchanged (bb 1,922 / kit 121 / selftest 34; docs only, not
  re-run); no battery.  **Nothing running.**
- **The owner's three decisions** (M10-PLAN section 3):
  1. the page's default machine (recommended: the 128K);
  2. how to switch (recommended: a key, Alt+M?, that reboots into the other machine, remembered like the high
     score);
  3. the scope (recommended: the 128K branch as it is, waits and all; music-only matches no machine).
  
  M10.0 and M10.1 do not depend on them.  M10.2 needs answer 3; M10.3 needs answers 1 and 2.
- **Next, in order:**
  1. The owner's answers (anything else the owner reports still goes first).
  2. **M10.0, the oracles (tools only):**
     - tools/harness128.py: B's h128 promoted, its generic part upstream to the kit;
     - the paging shim in tools/harness.py: C's pageshim, upstream;
     - tools/ayengine.py -> build/ayengine_fixture.json: direct, each sound 0..7 fresh for 3,000 ticks, plus D's
       random chains;
     - tools/ay128flow.py -> build/ay128flow_fixture.json: the flow on the port's 48K clock, for the scenes in
       M10-PLAN section 4, plus the hook's cost per ISR on the 48K clock and the skipProbe phase question;
     - SPEC's full M10 section.
     
     Read first: scratchpad/ay128/h128.py, scratchpad/branch128/pageshim.py, scratchpad/ay_cross/lockstep*.py (D's
     chains), scratchpad/ay_static/model.py.
  3. M10.1, the engine in JS.  M10.2, the branch on the 48K clock (parts a..d).  M10.3, the page and the platform.
     M10.4, the release docs.
  4. Then (d) the README, and (e) the scrub (the owner's call).
- **Solo or agents:** M10.0..M10.4 are SOLO.  The recon settled what the machine does, independently cross-checked
  with 0 mismatches, and the oracles are cheap and complete: the direct oracle diffs every write, the flow oracle
  every frame.  One Sonnet reviewer each for M10.2 (new blocking machinery in step()) and M10.3 (shared platform
  machinery), per the token-economy rule.

## RESTART HERE (2026-10-12b, M9.1 THE SAVED HIGH SCORE + ALT+ENTER FULLSCREEN -- COMMITTED e640bc7, its FULL BATTERY CLEAN; next: the owner's playtest findings, then M10 (128K/AY music) PLANNING)

- **M9.1 COMMITTED, commit `e640bc7`** -- wrap-up item (b): the two ADDED layers the owner decided on 2026-09-08 (memory:
  bubble-bobble-port-decisions).  All suites green: bb **1,922** / kit **121** / selftest 34; romscan CELLS 0, STRONG 1
  allowed.  Files:
  - web/game.js: `BB_HI` / `bbHiDigits` / `bbHiValid` (after `BB_SCORE`); `BB_Game.hiSeed` (constructor; `null` = the
    machine, every test world); `hiRestore()` (just above `reset()`), called right after `this.coldStart()` in `reset()`;
  - web/template.html: `BB_PAGE.saveHiScore` (default `true`); `bbHiScore(game, store, on)` and the page's `hiscore` (the
    store read ONCE at boot; `tick()` in the loop's `step()` after `game.step`); `BB_FULL` / `bbFullFit` / `bbFullscreen`
    and the page's `fullscreen` (its keydown listener registered BEFORE `attachKeyboard`'s: `preventDefault` +
    `stopImmediatePropagation`; `sync()` first in `draw()`); the `.bb-full` CSS; both key captions end "fullscreen
    Alt+Enter (Esc leaves)"; `__PORT__` exports them all;
  - test/rig.js: `fire()` stops at `stopImmediatePropagation()` (TRAPS #340) -- UPSTREAMED to the kit
    (`../Spectrum-Port-Kit` commit `c32f351`: kit suite 115 -> 116, its README / CLAUDE counts updated);
    test/kit.test.js +1 (the event order);
  - test/bb.test.js: the last block "M9.1" (HS1..HS10, FS1..FS12);
  - docs: STATUS (paragraph, table, the page paragraph), TRAPS #340, README (two declared departures), NOTES (Upstream).
  - WHAT: the machine has ONE high score, `$FFE1..$FFE4` (BCD, LSB first), set only by the cold start (`$9688` / `$9692`:
    20,000) and `$80FA`'s copy.  ON (the page's default): a stored `{"high":"dddddddd"}` (eight decimal digits, MSB first)
    is laid over `$9692`'s at the hand-over; after it the page saves a change that beats the store (re-read each time).
    Anything else stored is refused and said so (`P.hiscore.info()`).  OFF, or ON with nothing stored: the machine (HS6:
    the whole 64K at the title is the bare game's).  Fullscreen: Alt+Enter / Escape; the Fullscreen API (WebKit's too) or,
    refused / absent, the frame over the window; the screen at the largest whole DEVICE-pixel scale that leaves the page's
    border (`bbFullFit`: 5x at 1920x1080).
- **Battery:** the list `scratchpad/battery/mutate7.py` (gitignored): +67 (`add_m91.py` 65 + `scratchpad/m91/caption.py`
  2; backups mutate7.m91.bak / mutate7.m91cap.bak), 8 re-aimed (`reaim_m91.py`, backup mutate7.reaim91.bak), 1 re-aimed
  after the run (backup mutate7.m91grant.bak): **6,244 cases, 0 dead**.  FULL (the rig changed) 2026-10-12 19:36..20:36:
  `LISTED 6244  KILLED 6239  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 4  CRASHES 0  MISSES 0  -- 60.0 min on 20
  workers` (build/mutants/m91_full.log; coverage re-learned).  The four known (M7.110's guard TIMEOUT, B9 x2, M7.69) plus
  M9.1's own "the grant never ends pending" -- a SyntaxError (the deleted line left a dangling `else`) -- re-aimed to
  `if (false)`: `--match` 20:50 `LISTED 1  KILLED 1` (build/mutants/m91_grant.log).  Predicted EQUIVALENT, left out (see
  add_m91.py's docstring): the baseline's `return`; `b !== null &&`; leave()'s `was === 'screen'`; fit()'s size cache.
  **Nothing running.**
- **A `--match` / `--affected` run (Git Bash breaks the pool, even foreground):** `$env:ZX_CASE_TIMEOUT='900'; $p =
  Start-Process python -ArgumentList 'tools/mutants.py --match "LABEL TEXT" --jobs 20' -RedirectStandardOutput
  build/mutants/<name>.log -RedirectStandardError build/mutants/<name>.log.err -WindowStyle Hidden -PassThru -Wait` (ONE
  string for -ArgumentList keeps a label with spaces whole; `-Wait` is fine for a handful of cases).  A full run: the line
  in the M7.115m section below (Start-Process + watch.ps1 + a CronCreate poll at :07 / :27 / :47).
- **Found on the way:**
  - README's scope table still says "Title screen, attract mode, high-score table and name entry | in scope" -- MEASURED
    long ago: no attract mode (16,749 frames), ONE high score, no table, no name entry.  Item (d) rewrites it.
  - The fullscreen CSS is not gated (the rig has no layout): the owner's playtest checks it in a browser.
- **Next, in order:**
  1. ~~The owner's playtest of M9.1~~ -- PASSED (the owner, 2026-10-12: "score saves, fullscreen and exit fullscreen
     work flawlessly").  Anything else the owner reports still goes first.
  2. **M10 -- 128K/AY music, PLAN FIRST** (wrap-up item (c), PART OF DONE).  HOW (asked by the owner 2026-10-12; the
     recommendation given): the RECON as ONE multi-agent pass (ultracode / a Workflow -- only when the owner triggers it in
     their own words) of four agents: A the static reading, B the 128K harness and the AY capture (never run in this
     project: the old 128K-branch states were a 48K machine, no paging), C what else the 128K branch changes (the `$8E05`
     waits, `$96B3`'s screen writes and sprite rebuild, the frame length), D a cross-check (the opening AY writes of two
     sounds predicted from A's reading against B's capture); then the plan written for the owner before code; the
     implementation SOLO, increment by increment, as always.  If the owner prefers, the same A / B / C one at a time
     (Sonnet), D done by hand.  Known already -- read these, nothing more:
     docs/SPEC.md "M6 sound" (lines ~4956..5045): the decision is the timing probe `$FAC3`; the 128K leg `$96B3` copies
     the engine (`$E6A8..$F5BB` on the tape, 3,860 B) through the screen into bank 1 `$C350..$D263` (`$CF80` the music
     tick, `$D167` the request; engine state `$D1E6` / `$CFA9` / `$CFEF`) and keeps three hooks live: `$8DC4` (in the ISR:
     `$FED4` == 1 ? the music cadence `$8DE0` : the engine tick `$8DEA`), `$8E0A` (a request, A = the sound number: page,
     `CALL $D167`, unpage), `$8E05` (waits on the busy byte `$8E06`); sounds 0..7 and their request sites are listed
     there; the AY writer is `$F318..$F4D1` (26 `OUT (C)` to `$FFFD` / `$BFFD`).  docs/NOTES.md "M6 outcomes" (~lines
     240..256: the old harness play states are 128K-branch, `$8DC4` = `$F3`).  `build/boot128.z80` exists (simload).  The
     port's `coldStart(BB_COLD.M128)` THROWS at `$96B3` (not modelled).
     The plan must settle, with agents ONE AT A TIME (Sonnet, narrow briefs, ~600-word reports -- token-economy):
     - A (static): the engine as it lands in bank 1 -- entry points, the request's sound table, the music / SFX data
       format, the tick's AY write order, the busy byte; whether the 128K branch plays AY effects where the 48K plays its
       beeper ones (which beeper emitters stay on 128K);
     - B (dynamic): a 128K harness run (SkoolKit's 128K simulator from boot128.z80, the probe answering 128K) recording
       every AY register write [frame, T, reg, val] and every `$8E0A` request over the title, a round start, play, the
       pause, a death, EXTEND and the boss -- the oracle's format; and what the `$8E05` waits do to the game's flow on a
       128K (does the round start wait for sound 5?);
     - then the plan, written down before any code: the scope (music only, or music + AY effects), the switch (an ADDED
       flag: OFF = the 48K faithful page; ON = the 48K game with the 128K engine's sound -- the waits modelled or
       declared), the transliteration, the fixture, the gates (the AY stream frame for frame against the harness),
       platform.js's `AyChip` / `SoundOut` (already there: [frame, reg, val] rows).
  3. (d) the README: the slowdown figure (MEASURED; "pending (milestone M3)" in it today), every declared departure and
     DECLARED timing gap in one list, the scope table corrected.
  4. (e) the pre-publication history scrub -- the owner's call, only if publishing.
- **Solo or agents:** the playtest's fixes -- solo (applying behaviour already measured).  **M10's planning needs agents**
  (one at a time, Sonnet): it is "what does the machine actually do?", there are independent ways to find out (a static
  reading of the engine, the 128K harness's AY stream), and a wrong reading would be baked into the layer's code and
  fixtures.

## RESTART HERE (2026-10-12, M7.115m THE EVEN ISR'S LAST ACCESSES ON ITS PROGRAM -- COMMITTED 99eab2b; its FULL BATTERY CLEAN; next: THE WRAP-UP (the owner's decision: the timing campaign stops; 128K/AY music part of done))

- **M7.115m COMMITTED, commit `99eab2b`** (all suites green: bb **1,900** / kit 120 / selftest 34; romscan CELLS 0, STRONG 1 allowed;
  `python tools/popacc.py verify` MATCH (~40 s)).  Files:
  - web/game.js: BB_ISR_PO / BB_ISR_PO_C (each entry on its caller's clock); bubbleManagerPass's `blAt` / `poAt` / `riAt` /
    `agAt`; bubbleAge's `esAt` / `poAt`; the escape's, the pop's and the push's `bfAt`; sparkSeed's reads and stores;
    bubbleAwardFork's `ehAt`, its two OUTs (ipPort) and `awardIsr` (new: $80FA with awClk, its glyph stores onto `this.ip`);
    playerBlow's `blowClock` (the steal's pop, the bonus's award); BB_Game.ISR_PO / ISR_PO_C / AB38 exported;
  - web/template.html (BB_ISR_PO exported);
  - test/bb.test.js: the last block "M7.115m EV" (EV1..EV5); SK3 re-pinned (ISR 804 exact -- its pin gone); PK7 re-pinned
    (the pop rows' synthetic-phase median 49 -> -40);
  - tools/popacc.py (new), build/popacc_fixture.json (new, 1.3 MB), port.json (`popacc`);
  - docs: TIMING "M7.115m", STATUS paragraph + table, TRAPS #335..#339.
  The battery list (scratchpad/battery/mutate7.py, gitignored): +78 (`add_m7115m.py`, backup mutate7.m7115m.bak) and 15
  re-aimed (`reaim115m.py`, backup mutate7.reaim115m.bak): **6,177 cases, 0 dead**.  Hand-tested before the battery
  (scratchpad/m7115m/handmut.py: each new case against the EV block alone -- ev_only.js runs ev_block.js, the block
  extracted from bb.test.js): 75 / 78 killed first; the 3 survivors were clock terms only two events in one pass can read
  (TRAPS #339) -- five forced scenes added (push_age, push_esc, push2, bonus_both, bonus_steal), then 78 / 78.
  - WHAT: the even ISR's bubble manager `$B62C` made contended accesses that were not on the ISR's program:
    - the pop `$B6D8` (held arm 167, age pop 26, steal 0 in the census): its erase (`$BF0A` -> `$BF16` -> `$A447`, 80
      accesses), its seed (`$B701` reads, `$B713` / `$B718` stores, `$B723` cancel), a paid pop's award (8 glyph stores a
      digit, `$8052`) between OUT `$B791` / `$B79E`, a class-1 pop's corpse birth on a live enemy;
    - the escape's erase (`$B6B9`), the push's (`$B952`, inside the rise);
    - the blow's bonus award (`$BD6B`).
    SK3's ISR 804: 83 accesses, 5 T short.
  - MEASURED (popacc): 48 states x 600 frames, 13,296 even ISRs, 279 kept (each replayed plain from `$B62C`'s entry with
    its seed, R draws, the ISR's acceptance phase and D); 54 forced on round1_48 / round1_2p48 (built on the even ISR's
    real stack `$96C1`, TRAPS #335) with proof marks -- 54 with the five two-event scenes.  Declared: OPS (the blitters' own operands), the digits' pixels, 3
    calls whose chain window is parked in the ROM (marks from ROM bytes).
  - ENGINE: BB_ISR_PO = { HELD 87, AGE 108, ESC 73, ES_BF0A 351, BF0A 144, SEED_RD 4, Y_ST [37, 69], CANCEL [105, 114],
    OUT 4, AWARD 54, OUT2 21, BIRTH 185, BIRTH_A447 79, PUSH_BF0A 43, PUSH_P [49, 10], BLOW 44, BLOW_P1 14, POP_IX 14 }
    (the Zilog sums; TIMING "M7.115m" spells each one).  Every clock is null outside an ISR and after the pass (EV5).
  - GATES: EV1 the fixture; EV2 330 / 330 calls exact through bubbleManagerPass (program, T, writes, glyph addresses, R
    draws, chain marks and ROM reads; the old rule wrong on all 330); EV3 every entry (230 pops, 349 `$BF0A`s, 91 awards,
    11 births) at the machine's offset; EV4 the 276 natural calls' D from the machine's acceptance phase (199 non-zero, up
    to 1,207 T; the old rule wrong on 129); EV5 the boundary (no program outside an ISR, the same RAM; no clock left set).
- **The `--affected` battery:** 2026-10-12 16:54..17:44: `LISTED 194  KILLED 194  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0
  BROKEN 0  CRASHES 0  MISSES 0  -- 50.7 min on 20 workers` (build/mutants/m7115m_aff.log; 93 new or re-aimed, 1 anchor
  line, 100 killing blocks).  Clean.  In STATUS's battery cell.
- **The FULL battery DONE, 2026-10-12 17:56..18:26:** `LISTED 6177  KILLED 6173  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0  -- 29.7 min on 20 workers` (build/mutants/m7115m_full.log).  The four are the known noise:
  TIMEOUT M7.110's cursor guard, BROKEN B9 x2 / M7.69.  In STATUS's battery cell.  Nothing running.  The command, for the
  next one: `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20'
  -RedirectStandardOutput build/mutants/<name>.log -RedirectStandardError build/mutants/<name>.log.err -WindowStyle Hidden
  -PassThru` + `Start-Process pwsh -ArgumentList '-NoProfile','-File','scratchpad/battery/watch.ps1',"$($p.Id)",
  'build/mutants/<name>.log' -WindowStyle Hidden` (add `'--affected'` after an increment); result `cat
  build/mutants/<name>.log.done`; poll it with a CronCreate job (:07 / :27 / :47), delete the job when the file appears.
- **Found on the way (not this increment's):**
  - the pop click's edges (`popClick`) still start at M7.84's PROVISIONAL place (the ISR's start + tcost); the OUTs' exact
    places on the ISR's clock are now known (bubbleAwardFork's `tail` + OUT / + AWARD + aw + OUT2) -- a candidate to make
    the click exact (its gates: PK's click rows; the contention before it from the program).
  - inside the ODD ISR the corpse flight `$8A78` erases (`$8A7D CALL $BF0A`) and draws (`$A26F`) every corpse frame -- 1,205
    `$BF0A`s in popacc's census, none on the odd ISR's program (M7.114c's declared "corpse-flight / boss draws in an ISR").
- **Next, in order:**
  1. ~~The `--affected` line~~, ~~commit~~ -- DONE (99eab2b).
  2. ~~The FULL battery's line~~ -- DONE (clean: 0 survivors, the four known; docs-only commit).
  3. **THE OWNER'S DECISION (2026-10-12): the timing campaign STOPS here.**  The remaining timing gaps -- the lives panel
     and the corpse flight inside the odd ISR, the boss draws in an ISR, EXTEND's / the storm's fitted contention,
     BB_ISR_ACCEPT where no grid, the R stand-in, the ROM chain window, the rest of TIMING's "Still DECLARED" -- stay
     DECLARED.  Do not pick them up.
  4. THE WRAP-UP, in this order (each a scoped increment with its gates and battery, as before):
     a. the owner's playtest pass -- anything it finds first (the owner reports in chat or docs/);
     b. the decided added layers not built yet (memory: bubble-bobble-port-decisions):
        - high-score saving: ON by default, platform.js `settingsStore('bb-hiscores')`, the single high score
          `$FFE1..$FFE4` (BCD LE), the faithful path (the default each boot) behind the flag, silent on file://,
          mutation-tested against the rig's REAL store (TRAPS #17);
        - Alt+Enter fullscreen, Escape back to the page layout (page furniture, ADDED);
     c. **128K/AY music -- PART OF DONE (owner, 2026-10-12)**: the planned M10 layer, a declared switchable layer over the
        48K faithful path.  The music driver at `$D167` has never been disassembled (the 48K branch skips it; `$FAC3` is
        the 48K/128K probe).  Scope it with a plan first: the 128K branch of the tape (tools/bleepload.py, M1's 128K
        discriminator), a 128K harness (SkoolKit's 128K simulator, its AY register writes as the oracle), platform.js's
        AY chip and the Web Audio bridge, [frame, reg, val] events.  Unknown machine behaviour: plan with agents (one
        at a time, Sonnet, per the token-economy rule) before code;
     d. the README: the slowdown figure (measured), every declared departure and DECLARED timing gap in one list;
     e. the pre-publication history scrub (filter-repo or one squashed commit) -- only if the owner publishes.

## RESTART HERE (2026-10-12, M7.115l BORIS'S ERASE `$915F` ON THE PROGRAM, ITS DI WINDOW ON THE FRAME CLOCK -- COMMITTED c133e8c; ITS FULL BATTERY CLEAN; next: the pop's ISR accesses)

- **M7.115l COMMITTED, commit `c133e8c`** (all suites green: bb **1,895** / kit 120 / selftest 34; romscan CELLS 0, STRONG 1
  allowed; `python tools/borisacc.py verify` MATCH (~35 s)).  Files: web/game.js (BB_BORIS; hurryReset; itemErasePixels /
  itemEraseBand's Boris mode bk / bkRs; gridPh's window rule; reset() bkK / bkRs / bkWinMiss; BB_Game.BORIS),
  web/template.html (BB_BORIS exported), test/bb.test.js (the last block "M7.115l BK" BK1..BK6; IA3 re-pinned and its drive
  records the `$B0D5` draws (hes); IA5 4 takes; SK3's ISRs 972..976 re-pinned; SK6's Boris text), tools/borisacc.py (new),
  build/borisacc_fixture.json (new, 218 KB), port.json (`borisacc`), docs (TIMING "M7.115l", STATUS paragraph + table,
  TRAPS #330..#334).  The battery list (scratchpad/battery/mutate7.py, gitignored): +27 (`add_m7115l.py`, backup
  mutate7.m7115l.bak), 9 re-aimed (`reaim115l.py`, backup mutate7.reaim115l.bak): **6,099 cases, 0 dead, 0 ambiguous**.
  Hand-tested before the battery (scratchpad/m7115l/handmut.py, run_bk.js -- the BK block extracted from bb.test.js; `--sk`
  adds the SK block): 17 / 17 killed.
  - WHAT: `$915F` with its request up (`$9160` = 1: the respawn inside the odd ISR, the clear `$8ECF`) runs `$9163 DI`, the
    stores (`$9160`, `$9257`, `$904D`, the hurry timer `$8DBD`), `$A314` on Boris's record `$9250` (16 rows x 2 screen
    stores), `$917A EI / $917B RET`.  MEASURED (84 phased runs): a point at or before the DI's first T is taken there
    (before the stores: the ISR INCs the timer they clear -- the next ISR's parity); 1 T into the DI .. 32 T before the
    RET's end: LOST; the last 31 T: taken at the RET's end (acceptance phase = end - point).
  - ENGINE: 'SM.9162f' to its CALL, a site at the DI (`isrSite(o0 + BB_BORIS.DI, pgO)`), the stores, `bkK` raised around
    `$A314` (its keys on the grid at the cursor, its rows' stores on the program, no site), '917Bx', then the window [DI's
    place + 1, the RET's end] pushed onto `diWindows` (a pass with a frame clock; a lost cursor COUNTED in bkWinMiss).
    gridPh: a point inside ANY DI window is taken at the window's end (`w[1] - b`) -- the award's too; in the spark world
    it never fires.
  - GATES: BK1 the fixture (23 natural requests, 15 forced, 84 phased: 18 before / 45 LOST / 21 at the end); BK2 38/38
    replays + forced exact (program 1,140 accesses, grid, T, bytes); BK3 84/84 phased exact (old rule: takes the 45 lost,
    misreads the timer on all 18 before); BK4 the boundary; BK5 the window edges + site from the machine's instruction
    list; BK6 THROUGH step(): a real round-1 game, the request raised in a pass whose DI is 830 T before the point -- that
    frame's ISR is LOST, the next frame's ISR runs (odd, timer 1).
  - FOUND: IA3's fruit world now exact through Boris's erase to frame 1128 (3,343 passes, was 2,287): the new pin is the R
    stand-in -- ISR 1128's walker `$B0D5 LD A,R` (1/128 hesitation, CP `$2A`) draws the stand-in's first `$2A` of 37 in the
    window; the machine's R there = 39.  ISR 1128's 613 accesses and waits are the machine's, its T 452 short
    (33,761 / 34,213).  MEASURED with scratchpad/m7115l/isrdump_fruit.py (the machine's ISR + its LD A,R log) and
    probe_isr_fruit.js (`FEED=<.ldar>`: fed the machine's draws, the engine's ISR 1128 = 34,213 T exactly).
- **The `--affected` battery, 2026-10-12 12:12..13:01:** `LISTED 115  KILLED 115  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0
  BROKEN 0  CRASHES 0  MISSES 0  -- 48.4 min on 20 workers` (build/mutants/m7115l_aff.log; 36 new or re-aimed, 0 anchor
  lines, 79 killing blocks).  Clean.  In STATUS's battery cell.
- **The FULL battery DONE, 2026-10-12 13:20..14:19:** `LISTED 6099  KILLED 6095  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0  -- 59.0 min on 20 workers` (build/mutants/m7115l_full.log).  The four are the known noise:
  TIMEOUT M7.110's cursor guard, BROKEN B9 x2 / M7.69.  In STATUS's battery cell.  Nothing running.  The command, for the
  next one: `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20'
  -RedirectStandardOutput build/mutants/<name>.log -RedirectStandardError build/mutants/<name>.log.err -WindowStyle Hidden
  -PassThru` + `Start-Process pwsh -ArgumentList '-NoProfile','-File','scratchpad/battery/watch.ps1',"$($p.Id)",
  'build/mutants/<name>.log' -WindowStyle Hidden` (add `'--affected'` after an increment); result `cat
  build/mutants/<name>.log.done`; poll it with a CronCreate job (:07 / :27 / :47), delete the job when the file appears.
- **Next, in order:**
  1. ~~The `--affected` line~~, ~~commit~~ -- DONE (c133e8c).
  2. ~~The FULL battery's line~~ -- DONE (clean; docs-only commit).
  3. Then (b) the pop's accesses in the even ISR (M7.115m: bubbleManagerPass's slot clock `at` is there -- give the
     HELD arm's `$B6D8` and bubbleAge's AGE_POP a clock like the travel arm's `trAt` / `bfAt`, put the erase
     `$BF0A` -> `$BF16` -> `$A5A0..$A5D3` (80 accesses) on `this.ip` with ipTmpl as the travel's erase does, and the
     seed's `$B701` read / `$B713` / `$B718` stores; SK3's ISR 804 is the free-running gate), then (c) the lives panel
     in the odd ISR (ISR 971: 54 accesses, 10 T) -- expect SK3 exact to 1300 after both; then the odd ISR's
     dummy-page probe (r10, EA3b), then the item-5 list (the R register first: it now pins all three of IA3's worlds --
     `$8A38` in the potion worlds, `$B0D5` in the fruit world).  All solo: the machine answers each directly (the probes
     in scratchpad/m7115k and m7115l: isrdump_fruit.py / probe_isr_fruit.js dump an ISR on both sides, FEED= feeds the
     machine's LD A,R draws).

## RESTART HERE (2026-10-12, M7.115k THE SPARKLE WALK `$C002` ON THE PROGRAM AND THE GRID -- COMMITTED 12fee6b; ITS FULL BATTERY CLEAN; next: Boris's erase)

- **M7.115k COMMITTED, commit `12fee6b`** (all suites green: bb **1,889** / kit 120 / selftest 34; romscan CELLS 0, STRONG 1
  allowed; `python tools/sparkacc.py verify` MATCH (~45 s), `python tools/straddle.py verify` MATCH (~3 min)).  Files: web/game.js,
  web/template.html (BB_SC exported), test/bb.test.js (the last block "M7.115k SK"; IA3 re-pinned), tools/sparkacc.py (new),
  tools/straddle.py (GATE += $C002), build/sparkacc_fixture.json (new, 1.0 MB), build/straddle_fixture.json (re-captured:
  every other callee's rows byte-identical, +83 $C002 gate rows), port.json (`sparkacc`), docs (TIMING "M7.115k", STATUS
  paragraph + table, TRAPS #325..#329).  The battery list (scratchpad/battery/mutate7.py, gitignored): +60
  (`add_m7115k.py`, backup mutate7.m7115k.bak), 6 re-aimed (`reaim115k.py`, backup mutate7.reaim115k.bak): **6,072 cases, 0
  dead, 0 ambiguous**.  Hand-tested before the battery (scratchpad/m7115k/handmut.py): 4 / 4 killed.
  - WHAT: a live particle's keys on the grid in the machine's order (SC.LIVE / ERASE_* / DRAW / WB / BL_ROW*, the item's
    IT.BL_* / IT.RS_* reused); its kids' screen accesses at the cursor (scK -> scBl / scRs: 64 a draw, 32 an erase); a site
    before each slot's `$C00B` read, the LDI, `$C019`, the write-back, each OR read, each OR store, each restore store (the
    OR row's read and store split around them).  BB_SC: LDI_AT 47, Y_AT 69, WB_AT 17, OR_RD0 7 / OR_ST0 14 / OR_RD1 38 /
    OR_ST1 45.
  - GATES SK1..SK7 (all green; details in TIMING "M7.115k"): SK2 242/242 replays + forced exact; SK3 the spark world
    free-running exact to frame 971 (2,524 passes), all 703 ISR-end screens exact, PINNED ISR 804 (-5) / ISR 971 (-10) +
    972..980; SK4 76/76 phased exact; SK5 83/83 census rows; SK7 297 stores + 6 reads at first T / +1.  IA3: the fruit
    world exact past 806 to 970 (2,287 passes), pinned on Boris's erase.
- **The `--affected` battery, 2026-10-12 08:56..09:41:** `LISTED 106  KILLED 106  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0
  BROKEN 0  CRASHES 0  MISSES 0  -- 45.0 min on 20 workers` (build/mutants/m7115k_aff.log; 66 new or re-aimed, 4 anchor
  lines, 36 killing blocks).  Clean.  In STATUS's battery cell.
- **The FULL battery DONE, 2026-10-12 10:05..10:33:** `LISTED 6072  KILLED 6068  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0  -- 28.3 min on 20 workers` (build/mutants/m7115k_full.log).  The four are the known noise:
  TIMEOUT M7.110's cursor guard, BROKEN B9 x2 / M7.69.  In STATUS's battery cell.  Nothing running.  The command, for the
  next one: `$env:ZX_CASE_TIMEOUT='900'; $p =
  Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20' -RedirectStandardOutput build/mutants/m7115k_full.log
  -RedirectStandardError build/mutants/m7115k_full.log.err -WindowStyle Hidden -PassThru` + `Start-Process pwsh
  -ArgumentList '-NoProfile','-File','scratchpad/battery/watch.ps1',"$($p.Id)",'build/mutants/m7115k_full.log' -WindowStyle
  Hidden`.  ~30 min (6,072 cases).  Result: `cat build/mutants/m7115k_full.log.done`.  Known noise: TIMEOUT M7.110's cursor
  guard, BROKEN B9 x2 / M7.69.  Don't edit game.js / bb.test.js / port.json / tools while it runs.
- **FOUND (MEASURED on the machine, pinned in SK3 / IA3; each its own next increment, solo):**
  - (a) **Boris's erase off the pass's program** -- `$915F` (hurryReset) restores the pixels under Boris's record `$9250`
    through `$A314` (`itemErasePixels(0x9250)`, game.js) and its 32 screen stores are not on the pass's program: IA3's fruit
    pin (pass 970:69416, the machine 423 accesses, the engine 391; the erase runs in step 971 after ISR 971 cut the pass).
    The sparkle's mode (scRs) is the pattern: keys + accesses at the cursor + sites (does an ISR read / write Boris's cells?
    measure first).  Smallest of the three.
  - (b) **the pop's accesses in the even ISR** -- a bubble the bubble manager pops (`$B6D8`: HELD or AGE_POP) erases its
    cells (`$BF0A` -> `$BF16` -> `$A5A0..$A5D3`: 80 screen accesses) and seeds the sparkle table (`$B701` read, `$B713` /
    `$B718` stores, `$B723` the cancel): none on the ISR's access program (`this.ip`; the travel arm's erase has `bfAt`, the
    pop none).  SK3's ISR 804: the seed's store waits 5 T (the machine's only wait in that ISR).  Needs the pop's entry on
    the ISR's clock (the slot clock `at` in bubbleManagerPass + the HELD / AGE_POP arms' offsets; BB_PO's sums).
  - (c) **the lives panel inside the odd ISR** -- `$8091..` / `$80A8` (LD IX,$85B1 / ... `$80AF LD A,(HL) / AND (IX+8) /
    OR (IX)` .. `$80B8 LD (HL),A`): 54 screen accesses at ISR 971 (both the spark and the fruit world) not on the ISR's
    program, 10 T.
  - Probes for all three (gitignored, scratchpad/m7115k/): `python -I scratchpad/m7115k/isrdump.py WANT OUT` (the spark
    world's ISR WANT: every contended access [plain offset, k, address, pc]); `node scratchpad/m7115k/probe_isrprog.js WANT
    OUT` (the engine's ISR program there); `python -I scratchpad/m7115k/fruitpass.py FRAME PHASE OUT` (the fruit world's pass:
    accesses with PCs, marks); `node scratchpad/m7115k/run_sk.js` (the SK block alone, ~70 s).
- **Next, in order:**
  1. ~~The `--affected` line~~, ~~commit~~ -- DONE (12fee6b).
  2. ~~The FULL battery's line~~ -- DONE (clean; docs-only commit).
  3. (none -- the FULL battery is step 2.)
  4. Then (a) Boris's erase, (b) the pop's ISR accesses, (c) the lives panel in the ISR -- each moves SK3's / IA3's pins
     (expect SK3 exact to 1300 after (b)+(c), IA3's fruit world past 970 after (a)); then the odd ISR's dummy-page probe (r10,
     EA3b), then the item-5 list below.  All solo: the machine answers each directly (the probes above).

## RESTART HERE (2026-10-12, M7.115j THE BOSS TICK ON THE PROGRAM AND THE GRID -- COMMITTED d04a4e8; ITS FULL BATTERY CLEAN; next: M7.115k `$C002`)

- **M7.115j COMMITTED, commit `d04a4e8`** (all suites green: bb **1,882** / kit 120 / selftest 34; romscan CELLS 0, STRONG 1 allowed;
  `python tools/bossacc.py verify` MATCH, `python tools/straddle.py verify` MATCH).  Files: web/game.js, web/template.html
  (BB_BT exported), test/bb.test.js, tools/bossacc.py (new), tools/straddle.py, build/bossacc_fixture.json (new),
  build/straddle_fixture.json, port.json, docs (TIMING "M7.115j", STATUS, TRAPS #321..#324).  The battery's list
  (scratchpad/battery/mutate7.py, gitignored): +59 new, 22 re-aimed (`add_m7115j.py`, `reaim115j.py`, `fix115j.py`;
  backups mutate7.m7115j.bak / .reaim115j.bak / .fix115j.bak).
  - FOUND / FIXED: a boss BODY ($AA0E, every 32nd tick) blits 832 contended accesses (each LDI / LDD's (DE) at 11 / 14 / 15
    T in, each $9D4C store's at 4) that were not on the pass's program, and its keys were summed out of order (CALL keys n
    times: the cursor lost) -- so r80 parted at frame 1113 and the screen at 1122.  Now r80 is EXACT to frame 1700: all
    6,702 passes (frame, phase, program), all 703 ISRs' T, and the screen at every ISR's end (bitmap with ROM-glyph cells
    masked, attributes).  Also found: `A978t` (P2's RET c on a boss hit, hand-written in BB_SM) had no grid entry -- the
    P2-hit region was never laid out; `$AA30` read P1's +$5A whoever matched (now the matched player's).
  - ENGINE: BB_BT (the places: MV each blit key's first block move, ST the stores, R the reads, BN the bounce's stores,
    J927D); btAt / btMove / btAttr; bossErase / bossEraseRow(row, bt) / bossDraw(bt) / bossDrawAttrs(dst, bt) /
    bossOverlap(bt) / bossTouches(.., bt) in the machine's key order with a SITE (isrSite) before every store and every read
    of what the ISR writes; the tick's two stores ($AA01, $AA0A) and the bounce's stores sites too; the boss's path into
    $927D on PE's keys and sites (playerHit: one rule; 'BT.J927D' = RET nz not taken / JP).  The giant's path (bt off) as
    before: summed keys, no access, no site (DECLARED).  `attrValue(src)` split out of attrReconstruct.
  - MEASURED: new `tools/bossacc.py` (`capture | verify --jobs 20`, ~35 s) -> `build/bossacc_fixture.json` (1.5 MB, port.json
    `bossacc`, test-only): r80 (emitacc's drive) + 6 boss-round states; every $A9ED call; 247 replays; 48 forced (4 with the
    machine's instruction list); 84 PHASED (the body's entry in the bottom border, the point AT / 1 T into 11 instructions,
    P1 beside / over the boss, BOTH parities of the ISR -- the even ISR draws sprites: the late class).
    `tools/straddle.py`: GATE += $A9ED (every class row, every late-diff row, every 10th): 31 rows with 'fin' / 'wr_i' and,
    on late rows, 'seen' [addr, value the ISR read, entry value].
  - GATES (bb.test.js, the last block "M7.115j BA"): BA1 the fixture; BA2 289 replays + forced exact (program, grid, T,
    writes; the SCF / RET pair DECLARED, counted); BA3 r80 free-running exact to 1700 incl. the masked screen; BA4 the 84
    phased runs (the ISR nested at the machine's phase after the machine's count of stores; the 28 late-class runs the old
    rule gets wrong); BA5 the 31 census rows (4 class + 10 late: old rule wrong on all 14); BA6 the boundary; BA7 every
    site at its instruction's first T and one T later from the machine's instruction list (604 store placements, 5 read
    flips).  Re-pinned: TB3 (drift 0), EA3b (r80 exact to 1114), SH3 (the boss's $927D now logs PE's 3 keys, 1 ISR), SM1
    (448 names; BB_BT.MV's 7 keys summed), GR1 (A978t the one hand-written grid key).
- **The `--affected` battery, 2026-10-12 03:55..04:51:** `LISTED 428  KILLED 426  SURVIVORS 2  DEAD ANCHORS 0  TIMEOUTS 0
  BROKEN 0  CRASHES 0  MISSES 0  -- 55.7 min on 20 workers` (build/mutants/m7115j_aff.log).  The two survivors were the two
  cases predicted EQUIVALENT before the run -- a RET's grid key ('AA46x', '9D57x') moved past a store: the store's site
  fires before both either way (the same cut, the same acceptance phase), the key logs no RAM, the store no key.
  Replaced (`fix115j.py`) by "the RET not logged" (the T 10 short: BA2), `--match` 04:55: `LISTED 2  KILLED 2  SURVIVORS 0`.
  **0 survivors.**
- **Next, in order:**
  1. ~~The battery's line~~, ~~docs~~, ~~straddle verify~~, ~~commit~~ -- DONE.
  2. ~~The FULL battery~~ DONE, 2026-10-12 04:57..05:25: `LISTED 6012  KILLED 6008  SURVIVORS 0  DEAD ANCHORS 0
     TIMEOUTS 1  BROKEN 3  CRASHES 0  MISSES 0  -- 28.0 min on 20 workers` (build/mutants/m7115j_full.log).  The four are
     the known noise: TIMEOUT M7.110's cursor guard, BROKEN B9 x2 / M7.69.  In STATUS's battery cell.  The command, for the
     next one: `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20'
     -RedirectStandardOutput build/mutants/<name>.log -RedirectStandardError build/mutants/<name>.log.err
     -WindowStyle Hidden -PassThru` + `Start-Process pwsh -ArgumentList '-NoProfile','-File','scratchpad/battery/watch.ps1',
     "$($p.Id)",'build/mutants/<name>.log' -WindowStyle Hidden`; result `cat build/mutants/<name>.log.done`.
  3. Then **M7.115k: `$C002`** (the live slot on the grid, its blits' accesses -- the same mechanism: BB_BT's way; its census
     rows: straddle's 12 class rows), then the odd ISR's dummy-page probe (r10's ISR 1472: EA3b's pin), then the item-5
     list below.  Solo (the mechanism is settled; the machine answers each question directly).

## RESTART HERE (2026-10-12, M7.115i $7E80 ON THE PASS'S PROGRAM, ITS HALT A BLOCK -- COMMITTED; ITS FULL BATTERY CLEAN; next: M7.115j the boss tick)

- **M7.115i COMMITTED (all suites green: bb 1,875 / kit 120 / selftest 34; romscan CELLS 0, STRONG 1 allowed; `python
  tools/emitacc.py verify` MATCH): `$7E80`, the element emitter, on the pass's access program, and its `$7EC2 EI / HALT` a
  block.**  Commit `03c76fb`.
  - FOUND: `$7E80..$7F0A` is contended RAM and on every element round (49 of 81, the boss's too) EVERY pass runs its long
    path `$7E85..$7E9D`, which the engine put nothing of on the program (counted `paMiss`): each pass 0..87 T short, the boss
    4 frames ahead by 1400.  Its HALT gave the frame away from wherever it began (`spend(BB_FRAME_T)`) and ran the re-test
    `$7EC4` + the rest of the chain BEFORE the ISR that may take the slot.
  - MEASURED: new **`tools/emitacc.py`** (`capture | verify [--jobs N]`, ~1.5 min on 20) -> **`build/emitacc_fixture.json`**
    (1.05 MB, port.json `emitacc`, test-only): the real load poked ($8609 = round - 1, $FECD = 1 at the end of ISR 1000) to
    rounds 80 / 10 / 25 / 3 / 17, free-running to frame 1700 (passes [frame, phase, len, program digest, ISRs, HALT], ISRs
    [label, T, acceptance phase], every LD A,R [frame, pc, A]); 18 saved states with an element (600 frames of random keys);
    replays 'a' (entry -> HALT/RET) and 'b' ($7EC4 after the ISR -> RET), 80 forced, **40 PHASED** (a scanning call's entry
    moved `shift` T before a boundary in the bottom border: 10 / 70 T in, AT / 1 T into $7E98's read, AT / 2 T into the EI,
    AT / 1 T into the HALT's first step -- TRAPS #320), 72 HALTs each asserted = the step walk.
  - ENGINE (web/game.js): `BB_SM_ACC` for all 26 of `$7E80`'s keys (scratch derive: per instruction by (pc, T), assembled
    from costsmall's blocks); the count loop in the machine's order; `$7E98`'s counter by ctrRead; sites at each slot's
    `$7EA7` (+9) and `$7EBA` (+7) reads (BB_EM.R_*); **the HALT a block**: `emHaltBegin` (BB_EM.HEAD = JR z + EI; the pass to
    the HALT spent via passSettle; `emHaltWalk` -- 4 T + the ULA's delay a step, the first always run, the ISR at haltPh; it
    refuses a point with no clock or more than a frame away; LATE when the EI begins at or past the point: the frame's ISR at
    the grid's phase (pgCut + gridResolve), the next frame the HALT's, `emHalt.wait`, counted `emHaltLate`); chainWalk
    returns 'halt'; step() treats it as a block; mainLoop walks a late HALT's frame and resumes at `$7EC4` (`emKey('BIT')` +
    `elemEmitB`, charged as $7E80's; `emResumes`).  Outside step() the old path (frame whole, `blocked`).  `paMiss` gone.
    `BB_Game.SM_ACC` / `BB_Game.EM` exported.  step()'s `blocked` handling KEPT: PA11 / PA6 test it through a stubbed
    mainLoop (nothing sets `blocked` inside step() now).
  - GATES (bb.test.js, the last block "M7.115i EA"): EA1 the fixture; EA2 226 replay parts (program, grid, T, SHA-1); EA3
    free-running r25 / r17 / r3 exact pass for pass + programs + ISRs to 1700 (R draws fed; r17's program pinned at pass
    1195: `$9B87`'s fire-slot read, $9AEB, off the program since M7.114a, waits nothing); **EA3b the two that part**: r80 at
    frame 1113 (the boss's first draw: 891 accesses, the engine's 59 -> M7.115j), r10 at the odd ISR 1472 (24 T: an enemy
    above the HUD -- `$B47B`'s OR (HL)s through `$AED7`'s dummy pointer read `$712F..` / `$710F..`, contended, 8 accesses off
    the ISR's program -> item 4 below); EA4 the walk on all 72 HALTs; EA4b the 40 phased runs; EA4c the late branch's parts;
    EA4d the scan's 24 sites at first T / +1 (count, found slot, acceptance phase); EA5 the boundary.  **LRF2** now checks to
    its worlds' ends (was: to the first $7E85); **TB3** re-pinned (late 10, drift 2: the boss's draws, M7.115j); PA2's
    `F.miss` clause removed; **HB20** counts the HALT's resume (its `stale` clause could no longer fail); the B7 "RETURN
    ADDRESS IS PUSHED" source check reads `elemEmitB`.
  - Hand battery (scratch handmut.py, 22 mutants): all killed but two EQUIVALENT, removed from the code: a site at `$7E98`
    and `isrDone ||` in the late test.
  - Docs: TIMING "M7.115i", STATUS paragraph + table (1,875 / 5,953 cases / 21,621 lines / 173 assets / 320 traps), TRAPS
    #318 (a contended HALT locks to the ULA), #319 (a site driven outside step() needs gridPhV null), #320 (phased runs).
- Battery: `scratchpad/battery/reaim115i.py` (14 re-aimed, "(re-aimed M7.115i)"; backup mutate7.reaim115i.bak),
  `scratchpad/battery/add_m7115i.py` (+56; backup mutate7.m7115i.bak), +1 inline (the walk's distance guard; backup
  mutate7.m7115i_b.bak): **5,953 cases, 0 dead, 0 ambiguous**.  (`scratchpad/battery/fix115i.py` was written for a
  `blocked` clean-up that was NOT applied -- don't run it.)
  - **`--affected` 2026-10-11 23:24..00:18:** `LISTED 448  KILLED 447  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 0
    CRASHES 0  MISSES 0  -- 54.1 min on 20 workers`.  The TIMEOUT ("the walk with no frame clock not refused": the walk hung)
    fixed by the second guard (removing either guard now fails EA5 fast).
  - **`--affected` 2026-10-12 00:37..01:17:** `LISTED 387  KILLED 387  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0
    CRASHES 0  MISSES 0  -- 40.5 min on 20 workers`.  Clean.
- **The FULL battery (M7.115i's end) DONE, 2026-10-12 01:38..02:05:** `LISTED 5953  KILLED 5949  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 1  BROKEN 3  CRASHES 0  MISSES 0  -- 26.7 min on 20 workers` (build/mutants/m7115i_full.log).  The four are the
  known noise: TIMEOUT M7.110's cursor guard, BROKEN B9 x2 / M7.69.  In STATUS's battery cell.  Nothing running.
- **Next, in order:**
  1. ~~The FULL battery's line~~ DONE (above; committed docs-only).
  2. **M7.115j: the boss tick `$A9ED` on the program and the grid** -- its erase (`$A9DA`: four `$A929` rows, each with its
     `$9D4C` CALLs) and draw (`$A8C1`) accesses on the pass's program (EA3b's r80 pin: frame 1113's pass, the machine's 891
     contended accesses, the engine's 59 -- emitacc's r80 world is the free-running gate: expect r80 exact to 1700, and EA3b's
     r80 pin then moves) and laid out on the grid in the machine's order (today `zs('A929', 4)` / `zs('A966t', 3)`: CALL keys
     summed n times, the cursor NaN), sites at its P1 reads (`$A983` Y, `$A98B` X, `$A97E`) and the late ISR's 10 rows
     (straddle.py GATE += $A9ED).  TB3's drift -> 0.  Measure first (passacc / itemacc / emitacc style on bossfree's quiet
     world).  Solo.
  3. Then `$C002` (the live slot on the grid, its blits' accesses) -- M7.115k.
  4. **NEW (found by EA3b): the odd ISR's dummy-page probe** -- an enemy above the HUD (Y < $18): `$B47B`'s floor probe ORs the
     cells through `$AED7`'s dummy pointer `$712F` and one row up `$710F` -- contended RAM, 8 accesses (4 a probe: `$B48C` /
     `$B497` OR (HL), 26 T apart) off the ISR's access program (`this.ip`; enemyProbeAt reads RAM but pushes nothing; the
     enemy handlers get no `enAt` today -- the player has `abAt`).  r10's ISR 1472 is the free-running gate (expect r10 exact
     to 1700; EA3b's r10 pin then moves).  Small; solo.
  5. Then: the R register (BB_Rng: the class draw `$7E04`, `$B0D5`'s, the power-up's), `$9AEB`'s fire updates (`$9B87` ..),
     the small handlers' own T (M7.92), the clear's grid and DI window, the natural clear / PERFECT / EXTEND free-running,
     2P later rounds; the `$D380` element-bubble reads.

## RESTART HERE (2026-10-11b, THE OWNER'S BOSS BUG FIXED -- COMMITTED 51c517a; NOTHING RUNNING; next: M7.115i, `$7E80`'s long path on the pass's program)

- **The owner's report: "the boss doesn't move and hitting it once with a lightning bolt kills it straight away."  FIXED
  and committed `51c517a` (all suites green: bb 1,866 / kit 120 / selftest 34; romscan CELLS 0, STRONG 1 allowed).**
  - CAUSE (MEASURED, tools/bossfree.py + scratch probes): the boss's velocities `$AA47` / `$AA48` are tape bytes ($01 / $01)
    that NOTHING in the game initialises (bosstick.py said so since B3) and the page never laid them down -- at 0 the boss
    stood at its spawn (14, 3) forever.  A bolt that hits skips its own physics (`$9F57` returns to `$9EE7`, past `$9ED0`),
    so it DWELLS while aligned: on the machine the boss moves on after one hit (42 -> 41); on the page the bolt took all 42
    (every other frame, ~1.7 s).  Symptom 2 is symptom 1's consequence.  Every boss gate had seeded its world from a capture
    holding $01 / $01 (TRAPS #310's shape).  tools/tapereads.py missed it because the bounce's `$AA43` NEG WRITES the pair:
    its rule kept only bytes no run writes (TRAPS #317).
  - FIX: tools/tapereads.py BLOCKS += `$AA47+2`, `$79A3+1` (WRITERS `$AA43` / `$79A5`) -> build/tape_bytes.json (extract);
    reset() already lays every block down.  `$79A3` is `$79A2`'s seed: THE BOSS SETUP (`$72A2 JP nc,$79A2` on rounds 80/81)
    `LD A,n / RLCA / LD ($79A3),A / LD ($9F62),A / RET` -- now modelled in spawnRound (it was `return 0`): HP 10 on the first
    boss build, 20 on round 81's, superseded by `$98B2`'s 42 at the start.  The build's state stores land as the build runs
    (only display bytes are held) -- the machine's land at the build's end: DECLARED in TB5.
  - THE CLASS: tapereads' CENSUS (new, in build/tapereads_fixture.json 'census'): every address any run reads before its
    first write (18,369), with the machine's RAM at the end of ISR 600 of the real load (passacc's drive) and 'tape_read'
    (where some run read the tape's value).  TB2 compares the page's RAM (skipProbe off) there: 178 differ, all in 11
    DECLARED groups (the per-type jump table `$73B0`, `$9561`'s discarded BIT `$892D`, the 128K path `$8DE0` / `$8E06`, the
    stack `$96B7..$96DC`, the saved SP `$AA59`, the probe's patched opcode `$AE9C`, the handler list's tail `$B558..`,
    the element bubble `$D380..$D4FF` (built on demand), the title ink `$FEBB` (R stand-in), the bubble pool's tape font
    junk `$FED8..$FF4F` ($B6CD reads +2 under +3 = $02: a ROM pointer)).  OPEN, not checked here: whether every bubble
    blit of `$D380..` reads what bbBuildElementBubble builds (the census saw tape-valued reads there in boris / blowbolt).
  - NEW ORACLE tools/bossfree.py (`capture | verify`, ~20 s; verify MATCH) -> build/bossfree_fixture.json (port.json
    'bossfree', test-only): the real load poked ($8609) = $4F, ($FECD) = 1 at ISR 1000 (not 600: the comparator pair
    $A98F/$A990 must have decayed -- poked at 600 the MACHINE crashes 271 frames after the spawn executing the pair).
    Runs: quiet (103 bodies to 1400: [entry frame, Y, X, dx, dy]), bolt (a bolt at the boss's (X, Y-2) at ISR 1117: one
    hit at 1118, 42 -> 41), kill (HP 1: the death, round 81 at 1464, its start at 1532), seed ($79A3 = $85: RLCA's carry
    -> $0B).
  - GATES (bb.test.js, the last block "2026-10-11 TB"): TB1 the pair and seed are the tape's and reset() lays them; TB2
    the census; TB3 every body's position the machine's (103/103), the spawn at 1111, frames exact to body 6 then ahead by
    <= 4 (DECLARED: $7E80's long path, below); TB3b the same positions as the page SHIPS (skipProbe on); TB4 the bolt: HP /
    bolt X / flags the machine's at every ISR end to 1161, and with the pair zeroed the same bolt hits 42 times (the
    owner's report, reproduced); TB5 the kill and $79A2's seed (rows by LABEL: DI windows skip ISRs); TB5b the RLCA carry.
    TR2 now expects the eight blocks and the new writers.  Hand mutants: all 7 killed (the carry one by TB5b only).
  - Docs: TRAPS #317, STATUS paragraph + table (1,866 / 5,896 cases / 21,461 lines / 317 traps), port.json notes.
    TIMING unchanged (no T change); M7-PROGRESS not written (as for the Boris fix).
- **FOUND (MEASURED, scratch passm.py / passe.js): the boss runs ~0.75% FAST on the page.**  On the boss round EVERY
  main-loop pass runs `$7E80`'s long path (`$7E85..$7E9D`: ($7E0E) = the element, non-zero there) -- code in CONTENDED
  memory, which the engine does not put on the pass's access program (paMiss, DECLARED since M7.115c).  Each pass comes
  out 0..87 T short by its phase (0 in the border, up to 87 in the screen fetch); fresh passes run 13,150 T ahead after
  290 passes, the bodies up to 4 frames ahead by frame 1400.  Every element round has the same gap.
- Battery: `scratchpad/battery/add_bossbug.py` (+9 cases; backup mutate7.bossbug.bak): 5,896 cases, 0 dead.
  **`--affected` 18:29..18:55: `LISTED 249  KILLED 249  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0
  MISSES 0  -- 26.5 min on 20 workers`.  Clean.  Nothing running.**  A FULL battery is not due (runner, rig and build
  unchanged): run one at M7.115i's end (the pass program changes) or the next change to the runner / rig / build.
- **Next, in order:**
  1. (done) The battery clean; committed web/game.js, test/bb.test.js, tools/tapereads.py, tools/bossfree.py,
     build/tapereads_fixture.json, build/tape_bytes.json, build/bossfree_fixture.json, port.json, docs/TRAPS.md,
     docs/STATUS.md, next.md.  (The owner's untracked files stay: Bubble_Bobble.7z, bubble-bobble-mutants-handover.zip,
     run_claude.ps1, docs/chrome_console_giant_item_crash_report.txt.)
  2. **NEW M7.115i: `$7E80`'s long path on the pass's access program** (the boss's speed; every element round): the
     instructions `$7E80..$7E9D` (and the emitter past `$7E9E` when ($8DBD) = $2A) as grid keys with their contended
     accesses (opcode fetches and operands in $7Exx, the stores to $7EFB / $7EB2), measured like itemacc / M7.115f.
     Gate: TB3's body frames exact (drift 0), LRF2's r81w to its end.  Solo: the machine answers every row.
  3. M7.115j (was M7.115i): the boss tick `$A9ED` on the grid (its erase / draw keys in the machine's order, sites at
     `$A983` / `$A98B` / `$A97E`, the late ISR's 10 rows; straddle.py GATE += $A9ED).  Then M7.115k (was j): `$C002`.
  4. Then: the R register, the small handlers' own T (M7.92), the clear's grid and DI window, the natural clear /
     PERFECT / EXTEND free-running, 2P later rounds; the `$D380` element-bubble reads (above).

## RESTART HERE (2026-10-11, M7.115h THE CENSUS'S NEXT THREE CALLEES -- COMMITTED f76e8e3; NOTHING RUNNING; next: M7.115i, the boss tick $A9ED)

- **`f76e8e3` M7.115h (all suites green): the census's next three callees on M7.115g's mechanism -- the jump tone `$8FA5`, the
  contact pass `$925A`, the level-clear decision `$8E3A`.**  (M7.115g's "M7.115h" list is split: `$A9ED` and `$C002` are
  M7.115i / M7.115j -- `$A9ED`'s erase logs CALL keys summed x3 (the cursor is NaN at its overlap reads), and `$C002`'s live
  slot is not on the grid at all.)
  - MEASURED: `tools/straddle.py` (its 27,087 rows unchanged; `verify` MATCH) -- GATE now {$8669, $931A, $8FA5, $925A,
    $8E3A}: 277 new gate rows (43 / 96 / 138, the 34 the old rule got wrong among them: P1's jump byte at `$8FBA`, an
    enemy's Y in `$9312`'s box test, an enemy the ISR inside the tally killed); `SAMPLE_AT` ($8E3A every 10th);
    `SMC_SEED` ($8E3A's operands read as instruction bytes: `$8E3B`, `$8F3A`, `$90AA`, `$90D0` -- without them 32 of its
    rows replay another path, TRAPS #315); `FORCED_8E3A` (round1_48's first `$8E3A` entry, poked: the one-left anger's
    first walk over one / four slots, the countdown's advance, the drain's band with an item left -- each grid, T, seed;
    `world['forced']`).
  - ENGINE (web/game.js): sites (isrSite) at every read of what the ISR writes and every store it reads -- `$8FA5`'s arms
    (`$8FAE` / `$8FB5` / `$8FBA`), `$925A` (`$9262` / `$9270` +7, `$92BB` +$5A, `$92C3` / `$92CC` X / Y, the walk's `$92E6`
    / `$92EA` (+7 read twice), `$9312` / `$930A`, the kill's `$927D` / `$9283` reads and `$9290` / `$9293` stores -- not on
    the boss's `$AA35 JP $927D`), `$8E3A` (the tally's `$8EB7` slots and `$8EC1` ($FECA) store, the drain's `$8F36`
    (ctrRead's INC when refused), the anger's gate stores `$90B2` / `$90BA` / `$90BD` and its walk's `$90CF` / `$90D3` /
    `$90D5` -- `angerPass(g)` / `hurryAnger(g)`: only from `$8EC9`).  The keys split at the reads (BB_GRID `JT.B2/B7/PH`,
    `PE.B2/K_F`, `TR.E_B3/AX`); the places BB_JT_GRID `R_B7/R_PH`, BB_PE `R_P1/R_P2/R_KF/W_5A/W_4`, BB_TR
    `R_PX/R_PY/R_E7/R_E3/R_AX`, BB_RC `W_FECA/W_ANG0..2/WK_RX/WK_WX`.  `$8E3A`'s paths on the grid (the drain + `$8F94`'s
    count `RC.CNT_*`, the countdown `RC.CD*`, the anger `RC.ANG_*` / walk `RC.WK_*`); the clear a `pgBad` mark (DECLARED,
    with its DI window `$8EF5..$8F19`).  **FOUND: `pbase` stayed `$8E2A`'s inside `$8E3A` (it is set in chainWalk's loop)
    -- the countdown's cdPos 65 T early in a pass (TRAPS #316); chainWalk sets it before `roundClearCheck` now.**
    `cdPast` false after a nested ISR (isrDone: the RAM's timer).  `enemiesAlive()` walks the tally on the grid.
  - GATES (bb.test.js, the last block "M7.115h SH"): SH1 the census's rows for the three (pinned; the class rows' reads
    by PC; $8E3A's 13 paths); SH2 all 277 rows exact (grid count + SHA-1), the ISR inside on all 34 class rows, inert 33/33
    path rows differ + the tally's `wr` row writes the old count, the late `$925A` row's nested ISR sees P1's +4/+$5A as
    they entered, the 4 forced paths' grids the machine's; SH3 cdPos = the cursor's place at `$8F29` (pbase), the
    countdown after a nested ISR the RAM's, the clear's mark, the boss's `$927D` / the hurry's fall-in / the respawn's
    calm run no site and log no key; SH4 the 28 sites at their first T and one T later (places from BB_GRID).  SG2 now
    filters its rows to `$8669` / `$931A`; SG1's DECLARED text updated.  **Suites: bb 1,859 / kit 120 / selftest 34;
    romscan CELLS 0, STRONG 1 (allowed).**
  - Docs: TIMING "M7.115h" (+ M7.115g's DECLARED note), STATUS paragraph + table (1,859 / 21,443 lines / 316 traps),
    TRAPS #315 (a read-before-write seed leaves out self-modified operands) / #316 (a base a loop maintains is stale for
    the call after it), port.json's straddle note.
- Battery: `scratchpad/battery/reaim115h.py` (50 re-aimed, labels suffixed "(re-aimed M7.115h)"; backup
  mutate7.reaim115h.bak), `scratchpad/battery/add_m7115h.py` (+71; backup mutate7.m7115h.bak),
  `scratchpad/battery/add_m7115h_b.py` (+3 on the forced paths; backup mutate7.m7115h_b.bak): 5,887 cases, 0 dead.
- **`--affected` 12:22..12:57:** `LISTED 241  KILLED 240  SURVIVORS 1  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0
  MISSES 0  -- 34.3 min on 20 workers`.  The survivor "M7.115h: the anger's head's stores swapped" -- the one-left
  anger's first walk had no machine grid (no natural straddle walks it, SH4 used a sum the swap keeps): FIXED by the
  census's FORCED_8E3A replays (SH2 checks their grids); the survivor and three neighbours (walk slot / countdown advance /
  drain advance reordered) killed by hand before the re-run.
- **`--affected` (second) 13:23..13:49:** `LISTED 236  KILLED 236  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0
  CRASHES 0  MISSES 0  -- 25.2 min on 20 workers`.  Clean.  Nothing running.**
- **Next, in order:**
  1. (done) Both --affected lines clean; committed M7.115h (web/game.js, test/bb.test.js, tools/straddle.py,
     build/straddle_fixture.json, port.json, docs/, next.md).  (The owner's untracked files stay: Bubble_Bobble.7z,
     bubble-bobble-mutants-handover.zip, run_claude.ps1, docs/chrome_console_giant_item_crash_report.txt.)  A FULL
     battery is not due (the runner, test/rig.js and tools/build.py did not change); run one at M7.115j's end (the
     census's mechanism complete) or at the next change to the runner / rig / build.
  2. **M7.115i: the boss tick `$A9ED`** -- its erase (`$A9DA`: four `$A929` rows, each with its `$9D4C` CALLs) and draw
     (`$A8C1`) laid out on the grid in the machine's order (today `zs('A929', 4)` / `zs('A966t', 3)` -- a CALL key summed
     n times: the cursor NaN, gridCallN), so the cursor is valid at `$A969`'s overlap: sites at its P1 reads (`$A983` Y,
     `$A98B` X, `$A97E` -- the census's reads after an ISR) and the boss path's `$927D` reads; and the late ISR's 10 rows
     there (the boss draw's screen writes vs the ISR's sprites: sites at the WRITES -- a write the ISR reads after the
     point must wait for the ISR).  Add `$A9ED` to straddle.py's GATE (its 279 'b' rows: 4 class + 10 late) and gate as
     SH (SI block).  Solo: the census answers every row from the machine.
  3. M7.115j: `$C002` -- the live slot on the grid (the blit / restore keys IT.BL_* / IT.RS_* through ik()), its accesses
     on the program (IA3's fruit pin at 806 moves), the OR merge's reads `$A307` / `$A30C` sites, the late ISR's 5 rows;
     the census rows need the C register (the walk's borrow).
  4. Then: the R register (the power-up's LD A,R -- IA3's potion pins), the small handlers' own T (M7.92), `$7E80`'s long
     path, the clear's grid and DI window, the natural clear / PERFECT / EXTEND free-running, 2P later rounds.

## RESTART HERE (2026-10-10d, M7.115g THE ISR INSIDE A CALLEE -- COMMITTED ef12f96; NOTHING RUNNING; next: M7.115h, the census's other callees)

- **`ef12f96` M7.115g (all suites green): the callee an interrupt falls inside -- the ISR runs THERE.**
  - MEASURED: new tool **`tools/straddle.py`** (`capture | verify --jobs N`, ~3 min on 20 workers) ->
    **`build/straddle_fixture.json`** (2.7 MB, test-only, port.json `straddle`).  itemacc's 3 real-load worlds + every 48K
    saved state (600 frames of random keys; 52 worlds): every chain CALL with exactly one ISR inside -- 27,087 straddles --
    replayed from the callee's entry plain and atomic: `before` (the engine's rule: the counters' INC at the point),
    `after` (the ISR's changes over the entry: the cut at the entry / edge read), the EXACT CUT (asserted = the natural call
    on every row: the method is the machine's), and the ISR re-run `late` (after the callee's later writes).  Result: on the
    engine's old rule 141 differ -- $8669 79 (77 the treasure room's walk), $8FA5 18, $925A 15, $931A 12, $C002 12, $A9ED 4,
    $8E3A 1; late, 19 more (15 screen bytes main-line blits and the ISR's sprites share, 2 the potion's -- handled by its
    block --, 2 single).  Gate rows ($8669 157 incl. the 79, $931A 158 incl. 12) carry the natural grid, the seed, the
    ISR's changes, the draws.  Two traps found (TRAPS #313): the ISR's keys are the ones at its FIRST instruction (the
    saved-state driver changes them at the frame boundary, after the acceptance), and the exact cut needs the ISR's R delta.
  - ENGINE (web/game.js): `isrSite(o, cut)` / `isrHere(cut)` -- the first read past the point runs the frame's ISR there
    (the phase from the grid so far; nothing of the ISR on the pass's program / grid; budget Infinity; `isrStart` = the
    point, which blowClick / popClick now read instead of `tframe - carry`); `isrDone` -> step()'s frame end runs no second
    ISR (re-bases the DI windows), gridResolve skips, ctrRead gives the RAM's counter; refusals counted (`isrInRefused`:
    heldWrites, isrDark, buildWin, rvReads, umb, lz, potionPending); a DI window over the point loses it (`intLostAt`, the
    pure test; intLost uses it).  The CURSOR (pgO) walks every pass's grid now (pg / pgSync / pgBad / pgCut), not the item
    pass's alone.  Sites: the collide $87B3 / $87B8 / $87BF / $87E2 (BB_IT R_FLAGS 4 / R_X 5 / R_Y 39 / R_LOCK 5; its T now
    summed as the tests run -- `itemCollideT` removed) and $931A's probe $9377 / $937A / $937E / $938D (BB_EK R_Y 23 / R_X 61).
    The other isr() callers set isrStart = tframe - carry (the old value).
  - GATES (bb.test.js, the last block "M7.115g SG"): **SG1** the census pinned per callee; **SG2** 315 gate rows in a fresh
    engine with the machine's ISR changes at its acceptance offset: all grids the machine's, the ISR inside on 90 of 91
    (the other: a handler's read, $889C, after the JP (HL) -- DECLARED), and without the nested ISR 89 of 91 differ; **SG3**
    the boundary (each refusal alone, the DI window, a lost cursor, ctrRead, gridResolve, the grid's phase and its MISS,
    both clicks); **SG4** each of the 8 sites at its reading instruction's first T and one T later (places from BB_GRID).
    **IA3 re-pinned**: 746 / 656 / 1,065 passes (was 224 / 166 / 232) to 1448 / 1448 (the power-up's $8A38 LD A,R: the R
    stand-in, machine 26 / 29 vs engine 59) and 806 (the fruit world's first sparkle: its blit's accesses off the program,
    M7.114a's declared list); 1,583 / 1,742 / 276 nested ISRs, no step with two.  PT1 / PT2 re-pinned to 1448: f700's room
    exact to its advance (0 rows, 0 frames), f600 1 row / -1 frame after its draw.  Pop-click / blow-click unit rows give
    isrStart.  **Suites: bb 1,855 / kit 120 / selftest 34; romscan CELLS 0, STRONG 1 (allowed).**
  - Docs written: TIMING "M7.115g", STATUS paragraph + table (1,855 / 5,813 cases / 21,299 lines / 171 assets / 314
    traps), TRAPS #313 / #314.  passSplitCharge's comment reworded (done).  `python tools/straddle.py verify --jobs 12`:
    MATCH (19:10).
- **The subset 17:59..18:47:** `LISTED 94  KILLED 89  SURVIVORS 5  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0  CRASHES 0  MISSES 0
  -- 47.8 min on 20 workers`.  Fixed (all suites green after, bb 1,855): (1) "outside step() a site runs the ISR" was
  EQUIVALENT (passClock is finite: bbUlaDelay(-Infinity) = 6, so a point at Infinity is never reached) -- the guard
  removed from isrSite, the case gone; (2) "the DI windows not re-based after a nested ISR" -- no scene had a DI window
  after a nested ISR in one frame: the frame end now computes `const lost = ... intLost(budget)` ONCE before its branch
  (the same calls as before), the case gone, two new on that line ("the frame end never loses its ISR", "the DI windows not
  re-based at the frame end"); (3..5) the cursor's resync / mark / cut survivors -- SG3 now drives them (a resync drops
  C_X's deferred 15 T: pgO 122 not 137; after pgBad / pgCut the cursor is NaN and a site is a counted miss).  Re-aimed:
  "a second site runs a second ISR", "step() runs the frame's ISR again after a nested one", and the older "M7.57 ext: a
  lost interrupt runs after all" (labels suffixed).  `scratchpad/battery/fix115g.py` (backup mutate7.fix115g.bak); 5,813
  cases, 0 dead.
- Battery: `scratchpad/battery/reaim115g.py` (28 re-aimed, labels suffixed "(re-aimed M7.115g)"; backup
  mutate7.reaim115g.bak) and `scratchpad/battery/add_m7115g.py` (+66; backup mutate7.m7115g.bak): 5,813 cases, 0 dead.
- **The follow-up subset 19:06..19:31** (the 8 cases above): `LISTED 8  KILLED 8  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0
  BROKEN 0  CRASHES 0  MISSES 0  -- 25.1 min on 8 workers`.  STATUS's battery line carries both subset lines.
- **FULL battery 19:43..20:19:** `LISTED 5813  KILLED 5809  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 3  CRASHES 0
  MISSES 0  -- 35.7 min on 20 workers` (ZX_CASE_TIMEOUT=900).  The 1 + 3 are the known noise: TIMEOUT M7.110's cursor
  guard, BROKEN B9 x2 / M7.69.  ROM scan (`python tools/romscan.py`): CELLS 0, STRONG 1 (allowed).  Nothing running.
- **Next, in order:**
  0. (done) The follow-up's line: 8 / 8; the passSplitCharge comment; straddle.py verify MATCH; the FULL battery
     clean; committed.  (Kept below for the record: the full battery's launch line.)
  3. (done) The FULL battery (due: game.js's pass loop, the cursor in every pass, bb.test.js's IA / PT / SG blocks):
     `$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20'
     -RedirectStandardOutput build/mutants/m7115g_full.log -RedirectStandardError build/mutants/m7115g_full.log.err
     -WindowStyle Hidden -PassThru` + watch.ps1 on $p.Id + a cron poll.  Fix its survivors, `--affected` if code moved.
  4. (done) Commit M7.115g: web/game.js, test/bb.test.js, tools/straddle.py, build/straddle_fixture.json, port.json, docs/
     (TIMING, STATUS, TRAPS), next.md -- the message with both battery lines and the suite counts.  (The owner's untracked
     files stay: Bubble_Bobble.7z, bubble-bobble-mutants-handover.zip, run_claude.ps1,
     docs/chrome_console_giant_item_crash_report.txt.)
  5. **M7.115h: the census's other callees, on the same mechanism** -- sites for $8FA5 (P1's $FD89 at $8FBA: its arm),
     $925A (the enemies' Y in $9312's box test, P1's Y at $92CC), $A9ED (P1's Y / X at $A983 / $A98B), $8E3A ($8EB7), $C002
     (the blit's OR merge: the screen bytes at $A307 / $A30C -- with it the blit's accesses on the program, IA3's fruit pin)
     -- each callee's reads on the cursor (its keys must walk); the gate rows for them from straddle.py (add each callee to
     GATE); and the late ISR's 17 (the ISR before the main line's screen WRITES: sites at the writes).  Solo: the census
     answers every row from the machine.
  6. Then: the R register (the power-up's LD A,R pins IA3's potion worlds: an R model from the grid's instructions would
     need M1 counts per instruction -- measure first), the small handlers' own T (M7.92), $7E80's long path, the natural
     clear / PERFECT / EXTEND free-running, 2P later rounds.

## RESTART HERE (2026-10-10c, M7.115f THE ITEM PASS ON THE PASS'S PROGRAM AND GRID -- COMMITTED 5f4f9fb; NOTHING RUNNING; next: M7.115g, the callee an interrupt falls inside, cut there)

- **`5f4f9fb` M7.115f (all suites green): the item pass (`$8669`) on the pass's access program AND its instruction grid.**
  - MEASURED: new oracle **`tools/itemacc.py`** (`capture | verify --jobs N`, ~1 min on 20 workers, verify MATCH) ->
    **`build/itemacc_fixture.json`** (1.8 MB, test-only, port.json `itemacc`).  Worlds: the real load with a potion laid at
    the end of ISR 600 / 700 (potion.py's, to the room's advance) and `fruit:f600` (eight items laid at ISR 600: under P1, in
    his walk, far, Y 8 = rows into the ROM, phase-3 expiries, the power-up slot; to frame 1,300); 17 saved states with items
    + round1_2p48 with items under both players, 600 frames of random keys.  Per pass passacc's row (from F - 2); per
    `$8669` call its program ('o:k;' from the entry), grid ('o:t;'), ISRs inside, handler window, chirp OUT starts
    [frame, phase].  REPLAYS (the first call of each distinct program + grid, every take / expiry / erase / dispatch) plain
    from the entry: seed, program, grid, T, `LD A,R` draws, the take's DI offsets; `same` = the natural call took that path.
    45 FORCED (flood $FECE, storm $FECF, P1 carried).  82,709 calls, 277 replays; 16 takes (1 by P2), 33 expiries, 49 erases.
  - ENGINE (web/game.js): BB_GRID's `IT.` / `AW.` / `CH.` keys (every instruction of the item pass, the BB_IT / BB_SC /
    BB_AW sums' own lists); a CURSOR (`pgc`, `pgO`, `pgStk`: `pgCur` / `pgEmit`, gridWalk's deferral) from the callee's entry
    in `itemFrame`; `itemAcc(d, k)` puts each access at the cursor (ink cells, blit rows incl. the reads of ROM-aimed rows,
    erase cells, restore rows, award glyph rows, chirp OUTs); `ik()` logs the shared routines' keys only inside the item
    pass; the handler's `JP (HL)` a CUT (`pgCut`; gridWalk's `close(to, cut)`), its entry `itHandlerO`.  The take's award
    DI window ($87F9 DI .. the LD C,$28 after $881C EI) pushed on the frame clock (`itDiLast`, `itDi`).  `itemChirpPass`:
    the edges at their OUTs' places (`passClock`), those past the point held MARKED (`mainOut(a, t, tw)`) and given the
    tail's waits when logged (`passTailWait` keeps `pTailCum`, `flushHeld` adds them).  The potion: `potionPos` =
    passClock(itHandlerO); past the point `potionBlock` hands the tail to pTail (`passWait`) and resolves the ISR's grid
    phase (`gridResolve`); `lzStep(budget, s = 0)` (step() passes its clock); the resumed pass after the potion starts after
    `IT.AFTER` + the CALL (`pAt` 79) with `passPreD = 0` (TRAPS #311).  New constants: BB_IT `L_ST_O / L_ST_S / N_ST / C_DI /
    LDC / OUT_IO`, BB_SC `RS_ST0 / RS_ST1 / BL_ST0 / BL_RD1 / BL_ST1`.
  - GATES (bb.test.js, the last block "M7.115f IA"): IA1 the fixture; **IA2** the 277 replays seeded (draws fed): program
    and grid = the machine's (275 / 277 exact at the first try -- the two were R draws); **IA3** free-running pass for pass,
    pinned: potion 224 / 166 passes to frame 840 / 878, fruit 232 to 644 (causes asserted: the walk reads P1 after the ISR
    inside it -- the replay's `same` false; `$931A` one probe more); **IA4** `$890D` = the machine's 601:31390 / 701:40126
    (the tail 17 / 20 T); **IA5** the chirp's 40 edges exact on 3 takes; **IA6** the DI window's edges = the machine's on 14
    takes, on the frame clock, an interrupt inside lost.  PT1 / PT2 restated (dd 0 / 0; the room's $FEC5 rows that differ,
    4 / 5, all from 840 / 878; the advance -1 / 0 pinned), SFX5 restated (the edges at the OUTs' places, one ISR-window gap).
  - Docs: TIMING.md "M7.115f", STATUS paragraph + table, TRAPS #311 / #312, SPEC (the collect chirp's row), port.json.
  - **Suites: bb 1,851 / kit 120 / selftest 34.**
- Battery: `scratchpad/battery/reaim115f.py` (63 re-aimed -- the item code's lines rewritten; backup mutate7.reaim115f.bak)
  and `scratchpad/battery/add_m7115f.py` (+48; backup mutate7.m7115f.bak); 5,751 cases, 0 dead.  The 48 new as a subset
  09:18..09:44: `LISTED 48 KILLED 47 SURVIVORS 1` -- "a block's segment from 0, not step()'s clock": IA4 / PT2 recorded the
  start step() HANDED lzStep, not the one lzSeg USED; both now hook lzSeg from inside lzStep and the mutant is killed by
  hand (PT2 and IA4 fail).  (After the block its effect is absorbed: the reveal's contention re-syncs the end, TRAPS #309.)
  Then `const live = h >= 0x40 && h < 0x80` (was `((h + 0) & 0xFF) >= 0x40 ...`) and its case re-aimed.
- **FULL battery 10:00..11:07:** `LISTED 5751  KILLED 5743  SURVIVORS 4  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 3  CRASHES 0
  MISSES 0  -- 67.3 min on 20 workers` (ZX_CASE_TIMEOUT=900).  Known noise: BROKEN B9 x2 / M7.69, TIMEOUT M7.110's cursor
  guard.  The 4 SURVIVORS were M7.115e's potionPos formula (charge so far - AFTER + itChirpT): inside step() the cursor now
  always gives $890D, so the formula was DEAD behind a silent fallback (house rule 6).  Removed with `itChirpT` (nothing
  else read it); a lost cursor is now COUNTED (`ptPosMiss`; IA4 holds it at 0 on both worlds and shows one counted); PT2's
  itChirpT check gone.  Battery: the 5 cases on the removed lines out, `M7.115f: a lost cursor in potionPos not counted`
  in -- 5,747 cases, 0 dead.  Suites still bb 1,851 / kit 120 / selftest 34.
- **`--affected` 11:25..12:04 (after the fix):** `LISTED 150  KILLED 150  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 0
  CRASHES 0  MISSES 0  -- 39.5 min on 20 workers`.  A full battery is NOT due (the runner, test/rig.js and tools/build.py
  did not change; --affected re-ran every case whose anchor or killing block moved since 10:00's full run).  ROM scan
  (`python tools/romscan.py`): CELLS 0, STRONG 1 (allowed) -- the new fixture and tool included.  Nothing running.
- **Next, in order:**
  0. (done) M7.115f committed 5f4f9fb with both battery lines.  (Untracked and the owner's, leave them: Bubble_Bobble.7z,
     bubble-bobble-mutants-handover.zip, run_claude.ps1, docs/chrome_console_giant_item_crash_report.txt.  scratchpad/ is
     ignored by git: the battery's case list and its add / re-aim scripts live there.)
  1. **M7.115g: THE CALLEE AN INTERRUPT FALLS INSIDE, CUT THERE.**  The engine runs a callee whole before its ISR (M7.114a);
     the machine's later reads see what the ISR wrote.  IA3 shows where it bites: the treasure room's walk (21 entries,
     ~64,000 T, spans the frame: its later box tests see P1 where the odd ISR moved him -- 10 of the room's 28 distinct walks;
     the room's dark-window rows and its advance, PT2) and `$931A`'s probes (fruit:f600 frame 644, 46 frames into ordinary
     play -- likely the commoner one).  MEASURE FIRST (solo; tools/itemacc.py's method generalised): for every pass a natural
     run straddles, replay the callee the point falls inside atomically from its entry state and compare paths -- count by
     callee and by the reads that changed (the class's census).  Then cut where it matters: the item walk at a live
     entry's collide (its first read of P1 / P2 at or past the point -- the pass split at a callee's entry generalised to a
     point inside one: a resumable walk, the cursor and the program carried across the ISR), and `$931A` the same way.
     Gates: IA3's pins move out (the room exact to its advance: PT2's dark-window rows and advance -> 0) and each census
     row the machine's.
  2. The other DECLARED items: a small handler's own T (types 0..5 after `$8838 JP (HL)`, not charged since M7.92); the
     edge-look cut at `$8669` on a spawn path (itemSpawnT leaves the spawn's own T out); $7E80's long path in play (rounds
     4 / 10 / 34); the natural clear / PERFECT / EXTEND $97F8 free-running; 2P later rounds free-running.
  Solo: each answer comes from the machine directly (replay the callee atomically, compare with the natural run) --
  nothing for a second reader to attack.

## RESTART HERE (2026-10-10b, THE OWNER'S BORIS BUG FIXED + ITS CLASS SWEPT -- COMMITTED 2c28e79; NOTHING RUNNING; next: M7.115f)

- **2c28e79 -- Boris has a sprite, and so do the bolts and the flames.**  The owner's "Boris doesn't appear after the
  hurry up": his 64-byte masked 16x16 `$FF50..$FF8F` is tape data the port never laid down (the giant banks' twin,
  2026-10-08).  New oracle **`tools/tapereads.py`** (capture | verify ~6 min on 20 workers, MATCH; extract):
  every saved state but boot / title / iball twice for 4,000 frames (random P1 keys; none) + r60_48 warped to rounds
  1..81 for 1,500 -- 189 runs; every read of a byte >= $5B00 outside the shadow screen made before the run's first write,
  kept when NO run writes the address (static) and it holds build/image_tape.bin's value (the 11 image.bin-built states
  only where the images agree) -> **build/tapereads_fixture.json** (test-only, 15,370 reads, every block write, and the
  machine's own calls).  Against the page's RAM in play it found FOUR more blocks; **build/tape_bytes.json** (shipped,
  reset() lays it down, game.js ~5126):
    `$A37D..$A3AC` the lightning bolt ($A2D5 from ($FDEE)) + the fire's two frames ($A04E) -- blank in the port, the
                   boss fight's bolts too;
    `$AAE9`        `$56`: the giant DIAMOND (the candy cane's giant) is type 0 and `$A9C1` reads the award table at index
                   -1 -- the +56,000 SPEC measured live 2026-09-09; the port paid 0 (the award gate tried types 1..3 only);
    `$FB07..$FB0B` / `$FB27..` / `$FB47..` `$40`: round 45's paint spill below the map, ON THE TAPE, read by the map
                   probes in every round before 45 (engine: enemyProbeAt, bubbleRiseStep, bubbleChainPop);
    `$FF50..$FF8F` Boris.
  **And play WRITES Boris's bank:** `$B7A1`'s chain mark indexes the bubble flags at `$FEDF + 10 x (12 - marker)` in 8
  bits, markers 20..26 land on the bank, `$B7C3` turns `$FF67` `$E6` -> `$EE` (water round 1, umbrella round 28).  That
  answers the morning's wrinkle twice: the four boss captures' `$EE` is image.bin's (they were built from it: boss.pkl =
  image.bin at all 8,253 bytes the images disagree on) AND a real in-play write.  The engine's bubbleChainMark already did
  it -- it read 0 there before.
  Gates **TR1..TR7** (bb.test.js, the last block): TR1 the class (all 15,370 reads vs the page's RAM at round 1 frame 600;
  two named exceptions, each must still differ: `$73B0..$73BF` the initialisers' code-pointer table, `$892D` a discarded
  BIT); TR2 the six blocks (laid by reset(), each non-zero byte read on the machine, every write a named writer's);
  TR3 Boris's 8 machine `$A447` calls replayed on the page's RAM (512 display bytes, nothing seeded from his bank); TR4
  the bolt's 4 blits (128); TR5 the fire's 4 burns (324); TR6 the diamond's `$56`; TR7 the chain mark `$E6` -> `$EE`.
  Hand-mutated: no blocks / only Boris / all but Boris -- each TR fails where it should.  TRAPS #310, STATUS, SPEC
  (Boris's bank written by `$B7A1`; the diamond's type 0), port.json (tapebytes, tapereads).
  **Suites: bb 1,845 / kit 120 / selftest 34.**
- Battery: `scratchpad/battery/add_bug1010.py` (+6 cases: no blocks, first only, no Boris, no `$FB` cells, no `$AAE9`, one
  byte late) + `M7.19: Boris's sprite pointer is not seeded` re-aimed (its anchor's comment changed).  5,703 cases, every
  anchor exactly once (backup `mutate7.bug1010.bak`).
  `--affected` 06:45: `LISTED 104 KILLED 104 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 23.5 min
  on 20 workers`; after the "giant diamond" wording (TR2 / TR6 text) `--affected` 07:16: `LISTED 104 KILLED 104 SURVIVORS 0
  DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 28.5 min on 20 workers`.  A FULL battery is NOT due (the runner,
  test/rig.js and tools/build.py did not change; every case whose anchor or killing block moved re-ran).
- Scratch: `scratchpad/tapereads/` (README.txt lists every probe; `tr_run.js` runs one bb block standalone in 0.7 s).
- OPEN, not investigated (noted for later, NOT a blocker): the write-watch's warps from round1_48 and round1_2p48 to round
  80 CRASHED the machine (ROM `$2FAF` at frame 330 / ROM `$0E5C`'s LDIR at 600, random keys) -- `python
  scratchpad/tapereads/boris_crash.py round1_48 80 2 6000`.  Warps from r60_48 / boris / hurryup to 80, and all 81 warps
  from r60_48, run clean, so it may be the warp from round 1's state rather than the game.  If a natural boss-round crash
  is ever reported, start there.
- **Next, in order (solo):**
  1. **M7.115f: the item pass ($8669) on the pass's access program** -- unchanged from below (2026-10-10's item 1):
     PT2's residual (`$890D` 142 / 139 T early), measure first with a passacc-style tool over the potion world.
  2. The FULL battery after M7.115f (it should close PT2) -- launch directly (Start-Process + watch.ps1,
     ZX_CASE_TIMEOUT=900).
  3. The other DECLARED items: $7E80's long path in play (rounds 4 / 10 / 34), the natural clear / PERFECT / EXTEND
     $97F8 free-running, 2P later rounds free-running.
  Solo (M7.115f's method is M7.114a's: the machine answers directly, nothing to attack by a second reader).

## RESTART HERE (2026-10-10, M7.115e COMMITTED 462cffd -- NOTHING RUNNING; next: THE OWNER'S BORIS BUG (sprite not loaded), then M7.115f)

- **`462cffd` M7.115e** -- the potion's T is a block (see 09g below for what it holds).  Battery `--affected` 20:36..21:35:
  `LISTED 527 KILLED 527 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 58.8 min on 20 workers`
  (75 new, 12 anchor lines, 440 killing blocks; 5,697 cases).  **Suites: bb 1,838 / kit 120 / selftest 34.**
- A FULL battery is NOT due: no change to the runner, test/rig.js or tools/build.py, and `--affected` re-ran every case
  whose anchor or killing block moved (as M7.115d's).  Run the next one after M7.115f (it should close PT2) -- launch it
  directly (Start-Process + watch.ps1, ZX_CASE_TIMEOUT=900; don't wait for the Fist project's 4-worker battery).
- Docs fix (this commit): TIMING.md M7.114a's site list named "`$8669`'s item inks and blits" -- passacc's 30 sites hold no
  `$8669` site (no item is drawn on the real load's 470..759), and the engine's item pass pushes NO access at all.
- **Next, in order (solo):**
  0. **THE OWNER'S BUG (2026-10-10): "Boris doesn't appear after the hurry up" -- DIAGNOSED, NOT FIXED.**  Boris IS
     implemented (M7.19..M7.21: $9037's banner, $911A's setup, $917C's chase) and switches on as the machine's does --
     reproduced (session scratch `boris/poke.js`, the page's path, the round clock poked to 1,495 then threshold+500-2):
     $9257 (his +7) = $E0 from clock 2,001, borisHalts counting, $A447 called every tick -- but the display under him
     does not change (`boris/draw.js`): HIS SPRITE IS NOT IN THE PORT'S RAM.  The X arm points (IY) at $FF50, and the
     machine holds his 64-byte masked 16x16 there ($FF50..$FF8F, TAPE DATA: build/image_tape.bin, equal in boris /
     hurryup / round1_48 / r50_48 / peachfall); the engine's RAM there is all zeros, so he draws blank.  The 2026-10-08
     giant peach / boss bug's twin (build/giant_sprites.json, tools/extract_giant_sprites.py, loaded at reset game.js
     ~5120, gate bb.test.js ~40387 "THE GIANT PEACH AND THE BOSS HAVE SPRITES").
     FIX PLAN: add ($FF50, 64) to that tool's BANKS (its note: Boris's record $9250 -> $FF50), regenerate, extend the
     gate (Boris's bytes = the tape's; Boris activated -> his pixels on the display, against the machine's boris.pkl
     display or a harness run), mutation cases, battery --affected, commit.  MEASURE FIRST the one wrinkle: in all four
     boss-round captures (boss / bosshit / bosskilled / bossspawn, round 80) $FF67 holds $EE where the tape has $E6 --
     find whether play writes it (a write-watch on $FF50..$FF8F over a long run incl. round 80) or those captures came
     from another image; the tool asserts equality in its states, so this decides what it may ship.
     (Machine behaviour, not the bug: Boris comes 500 frames after the hurry's threshold -- ~10 s after HURRY UP -- and a
     lost life resets the round clock and re-arms the hurry, so dying in that window means no Boris.)
  1. **M7.115f: the item pass ($8669) on the pass's access program.**  PT2 pins what it costs now: the potion's $890D 142 /
     139 T early (the machine waits 147 T between $8669's entry and $890D: the take's erase 83, the award's glyphs 31, the
     chirp's 40 OUTs 33 -- session scratch `itempos.py` had the measurement), the room's passes (21 items drawn a pass, none
     on the program) drifting: $FEC5's dark-window rows 4 / 3, the advance -1 / 0.
     Measure first: a passacc-style tool over the potion world (potion.py's drive: frames F-2 .. the room's end) and a
     world with live fruit -- every contended access of each pass with its PC and k, by site; then the engine: each item
     entry's accesses at its offset in $8669's run (the ink cells: $8765 LD A,(HL) read 21 T before $876A's store; the blit
     rows: $A306 / $A30B LD A,(DE) at $5D00.. 11 T before $A308 / $A30D's stores; M7.104's extEntry / extBands carry these
     offsets inside $94C2 -- reuse), the take's erase ($86E6 cells / rows), the award's glyph stores (awClk's cp) and the
     chirp's OUT cycles (8 T in) -- and itemChirp's edges at the chirp's pass-clock place (they start at tframe now,
     PROVISIONAL since M7.84).  Gates: the program by site = the machine's on those worlds; PT2's dd / f5 / advance -> 0.
  2. The other DECLARED items: $7E80's long path in play (rounds 4 / 10 / 34), the natural clear / PERFECT / EXTEND $97F8
     free-running, 2P later rounds free-running.

## RESTART HERE (2026-10-09g, M7.115e THE POTION AS A BLOCK -- DONE, NOT COMMITTED; BATTERY `--affected` QUEUED/RUNNING; next: its result, then commit)

- **M7.115e (uncommitted, all suites green): the potion's T is a block** (`BB_EXT_BLOCKS.potion`, lazy; `BB_PT`,
  `BB_PT_SCRIPT`, `potionBlock`, `potionPos`, `ptFillModel`; extModel 'pt_head' / 'pt_fill'; chainWalk 'potion' after
  `$8669`, mainLoop's resume, step()'s list, extEnd's branch, counters ptBlocks / ptPast / ptResumes / ptIsrs, diagnostics
  `potion:`; `itChirpT` (the chirp spent in time, reset in itemHead); `treasureProbe` writes `$89A9`/`$89AA` (the machine's
  self-modified operand); `boltSlotsClear` in the machine's order ($5B00's twenty, then $FDEE's)).
  - MEASURED: `tools/isrcarry.py` + 5 potion sources (round1_48, r50_48, 2p = round1_2p48, lastdia81 = round 81's type 9 /
    offset -1, real = potion.py's f600 via new `potion.reach()`), own phase + 16 forced + 3 straddles per DI ($890D's,
    $8C14's) + 2 at the HEAD window's close (32 / 31 T before 1,212: lost / taken AT the close).  350 runs, all exact; old
    sources byte-identical (backup `<session scratchpad>/m7115e/isrcarry_fixture.m7115d.json`).  The reveal window's close
    has NO reachable phase (contention re-syncs it to the ULA: frame phase ~188 / ~-2) -- TRAPS #309.  `tools/potion.py`
    gains 'fill' (17 maps: treasure.py's 7 rounds x 2 offsets + 3 built; `verify` MATCH, runs unchanged).
  - Gates: **LZ9** (125 rows exact: acceptances, 469 lost, the RET, main delays, all writes by addr@T, ext writes by value),
    LZ4 now 20 programs, LZ2's lazy list + potion, IC 350 runs / 20 sources / 4977+54 ISRs (potion ISRs gate-closed, in
    the isrCost check), **PT3** (ptFillModel = the machine's fill on 17 maps, T and every write; table-full on 4), **PT2
    restated** (the engine's $890D after ISR F+1, the four lost, 5 ISRs under the block, itemHead zeroes itChirpT; PINNED
    residual dd -142 / -139 T, f5 4 / 3, advance -1 / 0 -- was -5 / -4), PT1's dark-window bound ez <= 3.  puhandlers'
    type-12 stub now names the block's routines; the in-play $FECD sweep (RA-h) drains a block in flight before its
    re-phase (round 81 spawns a potion under P1 -- TRAPS #309).  **PT4** (TRAPS #307: the page's own path, skipProbe on,
    the clock's 0.198-T fraction: the block past the point / resumed once, 5 ISRs, 4 lost, round 2 at frame 2472).
  - **Suites: bb 1,838 / kit 120 / selftest 34.**  `python tools/isrcarry.py verify --jobs 6` MATCH (44 s);
    `python tools/potion.py verify --jobs 2` MATCH (~45 s).
  - Docs: TIMING.md "M7.115e" (+ pointer in M7.115d), STATUS paragraph + table + Left 3(d), TRAPS #309, SPEC type-12 row,
    port.json notes (isrcarry, potion).
  - Battery: `scratchpad/battery/add_m7115e.py` -- 17 re-aimed (the type-12 dispatch, $A36C, step()'s block list x8, the
    reveal script's CALL, the potion's reveal count) + 75 new; 5,697 cases, every anchor exactly once (backup
    `mutate7.m7115e.bak`).
  - Scratch (session scratchpad `m7115e/`): trial.py (isrcarry potion sources alone), lz.js (LZ9 by hand), pt.js / pt2.js
    (the free-running drive, the engine's phases), itempos.py (the machine's item pass: 64,750 T to $890D plain, waits 147
    T = erase 83 + award 31 + chirp 33), inplay.js (the sweep's crash), fill.js.
- **RUNNING: `--affected --jobs 20` with ZX_CASE_TIMEOUT=900** -- launched DIRECTLY 20:36 (the owner, 2026-10-09: "start
  it regardless; the other project, The Way of the Exploding Fist, is limited to 4 workers"): battery python PID 30172
  (build/mutants/m7115e.log, .log.err, .log.pid); watcher `scratchpad/battery/watch.ps1` pwsh PID 36032 writes
  `build/mutants/m7115e.log.done` at the end (the LISTED line also in build/mutants/summary.txt).  The two
  wait_then_run.ps1 waiters (22428, 29164) were stopped before they launched anything.  Cron 7e17d483 polls at
  :07/:27/:47 (session-only).  Don't edit game.js / bb.test.js / tools until it ends.  If the session died:
  `cat build/mutants/m7115e.log.done`.
- **Next, in order (solo):**
  1. The battery's line; fix any survivor / dead anchor (re-aim in a new script, `--match` them); re-run any TIMEOUT alone
     with `--match` and ZX_CASE_TIMEOUT=900.
  2. Commit M7.115e (web/game.js, test/bb.test.js, tools/isrcarry.py, tools/potion.py, build/isrcarry_fixture.json,
     build/potion_fixture.json, port.json, docs) with the battery line and bb 1,838.  A FULL battery is due after it
     (the runner did not change, but bb.test.js's LZ / PT blocks did and 92 cases are new or re-aimed): launch it
     directly (`$env:ZX_CASE_TIMEOUT='900'; $p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20'
     -RedirectStandardOutput build/mutants/run.log -RedirectStandardError build/mutants/run.err -WindowStyle Hidden
     -PassThru` + watch.ps1 on $p.Id) -- don't wait for the Fist project's 4-worker battery.
  3. Then the DECLARED residual PT2 pins: **the item pass ($8669) on the pass's access program** -- each pass's item inks
     ($8765 read 21 T before $876A's store) and blits ($A306/$A30B reads at $5D00.., stores), the take's erase ($86E6),
     the award's glyph stores (awClk's cp), the chirp's 40 OUTs (the ULA I/O cycle) -- M7.104's extEntry / extBands have
     the offsets inside $94C2.  Measure first (passacc-style on the potion world: the machine's program by site through
     the take and the room), then expect PT2's dd / f5 / advance -> 0.  Solo (the method is M7.114a's).  The other
     DECLARED items stay: $7E80's long path in play (rounds 4 / 10 / 34), the natural clear / PERFECT / EXTEND $97F8
     free-running, 2P later rounds.

## RESTART HERE (2026-10-09f, M7.115d THE POTION FREEZE FIXED, COMMITTED 054a153 -- NOTHING RUNNING; next: the potion's T as a block)

- **FULL battery after M7.115c (8a51d68), 17:22..17:48:** `LISTED 5616 KILLED 5612 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 1
  BROKEN 3 CRASHES 0 MISSES 0 -- 26.4 min on 20 workers` (ZX_CASE_TIMEOUT=900).  The known noise only: BROKEN B9 x2 /
  M7.69, TIMEOUT M7.110's cursor guard.
- **M7.115d (uncommitted, suites green): the owner's second bug -- the potion (type 12, $890D, the treasure room) "fills
  the level with the items but then crashes; the bubbles still flow until they pop".**  Measured on the machine
  (`tools/potion.py` -> `build/potion_fixture.json`, port.json `potion` ship false, ~2.5 min, verify by re-capture):
  the fill's tail `$898F..$899D` OPENS both ISR gates ($8994 LD A,1 / LD ($FEC4),A / LD ($FEC5),A); the engine stopped
  at the last row's DEC C, so the odd gate stayed 0 (nobody moved or was drawn) and only the bubble manager ran.  And
  `$894B CALL $8C14` (RES 7 on every enemy / bubble slot + the reveal) was a named stub -> now `extendReveal()`.
  Gates: PT1 (through play, two worlds: every ISR's odd gate, P1 X/Y, $FED1, round, bubbles = the machine's; $FEC5 but
  for dark-window hits), PT2 (DECLARED, pinned: the potion's T -- dispatch 1 ISR early, the 4 ISRs the machine loses
  under $8C14's DI run, the room advances -5 / -4 frames, $FEC5 rows differ 4 / 1), the treasure block's two-exit row,
  puhandlers' type 12 stubbed past its $8949 bracket.  Hand-mutated: no gate stores / the $8C14 stub both killed.
  +6 battery cases (`scratchpad/battery/add_m7115d.py`).  Docs: SPEC type-12 row, TIMING "M7.115d", STATUS, TRAPS #308.
  **Suites: bb 1,835 / kit 120 / selftest 34.**
- `--affected` 18:37: `LISTED 382 KILLED 382 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 38.8
  min on 20 workers` (the 6 potion cases and 376 whose killing block changed: the treasure and puhandlers blocks).
- **Next, in order (solo):**
  1. (done) M7.115d committed (054a153) with the lines above.  A FULL battery is not due (the runner did not change since 17:22's).
  2. Timing gaps now declared, in order: the potion as a block (BB_EXT_BLOCKS like EXTEND's $9500 reveal: its DI window,
     the award past the interrupt -- PT2 moves to 0); $7E80's long path in play (rounds 4 / 10 / 34); the natural clear /
     PERFECT / EXTEND $97F8 free-running; 2P later rounds free-running.  Solo.

## RESTART HERE (2026-10-09e, M7.115c COMMITTED 8a51d68 -- FULL BATTERY RUNNING; next: its result)

- **`8a51d68` M7.115c** (with the owner's round-2 freeze fix): see 09d below for what it holds.  Suites: bb 1,832 / kit
  120 / selftest 34.
- **RUNNING: the FULL battery** (due: game.js, bb.test.js and the runner changed) with `ZX_CASE_TIMEOUT=900` -- python
  PID 31016 (build/mutants/run.log, run.err, run.log.pid), started 17:22; watcher pwsh PID 6056 writes
  `build/mutants/run.log.done`; the one-line result also lands in `build/mutants/summary.txt`.  Expect longer than
  16.5 min once (killers re-learnt after the block renumbering).  Don't edit game.js / bb.test.js / tools while it runs.
- **Next, in order (solo):**
  1. The full battery's line into next.md (commit); fix any survivor / dead anchor (re-aim pattern
     `scratchpad/battery/reaim115c2.py`); re-run any timeout alone with `--match` (and ZX_CASE_TIMEOUT).
  2. The DECLARED list: $7E80's long path in play (rounds 4 / 10 / 34 run it from their first frame: the pass's plain
     T exact, its contended code fetches not on the program -- paMiss) is the next obvious one; then the natural
     clear's / PERFECT / EXTEND $97F8 free-running (needs a natural round-clear world), 2P later rounds free-running.
  Solo; agents only if $7E80's measurement turns up unknown machine behaviour.

## RESTART HERE (2026-10-09d, M7.115c + THE OWNER'S ROUND-2 FREEZE FIXED -- battery for its cases clean; committing, then a FULL battery)

- **The owner's bug (2026-10-09): round 2 froze after its level was drawn -- no sprites, nothing moving, no console
  error.**  Reproduced in Chrome (the page served by `python -m http.server 8765 --directory web`): `tframe` NaN,
  roundSeq stuck at 'halt', both gates 0.  Cause (committed in M7.115b, 983de2e): the page boots with `skipProbe` ON (the
  added layer), so the control select's path means leave a FRACTION on the clock (the probe's HALT clears it on the
  faithful path every gate runs); `bbLrMap` indexed its delay table at the fractional phase -> undefined -> the build's
  end NaN.  Fix: `D += tab[((phase + t + D + I) % FD) | 0]` (bbUlaDelay's rule; bbR1Map was always safe).  Gate
  **LRF5** (the page's own boot, skipProbe on, round 2 on a fractional clock; mutation-tested by hand: fails on the old
  line).  Soak `node scratchpad/m7115c/soak.js "" 15`: rounds 2..16 clean.  Repros: `scratchpad/m7115c/frac3.js`
  (headless, the page's path; `old.html` = the old line), `r2bug*.js`.  TRAPS #307, TIMING M7.115c, STATUS.
- **Battery since 09c:** `--affected` 15:19 `LISTED 5611 KILLED 5478 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 133 BROKEN 0
  CRASHES 0 MISSES 2 -- 137.4 min`; timeouts re-run 15:48 `LISTED 133 KILLED 62 ... TIMEOUTS 71 -- 18.9 min` (68 were
  load-time anchors whose killing block was lost: a TIMEOUT overwrites last.json's killer_sha); `tools/mutants.py` now
  takes **`ZX_CASE_TIMEOUT`** (env, default 180) and re-run 2 with 1500 s 16:23 `LISTED 71 KILLED 70 SURVIVORS 1 ...
  TIMEOUTS 0 -- 15.9 min`: the survivor (the shift's copy offset in ipSrc) was EQUIVALENT -- a bank is wholly in or out
  of contended RAM -- so `ipSrc` now decides per BANK and the term went (`reaim115c2.py`: 3 re-aimed, 1 dropped, +1 the
  merge's sort; +1 the round-2 stall case).  5,616 cases, every anchor once.
- **Suites: bb 1,832 / kit 120 / selftest 34.**  All 11 lrfree worlds still exact (`node scratchpad/m7115c/cmp.js`).
- `--match M7.115c` 17:16: `LISTED 19 KILLED 19 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 27.6
  min on 19 workers` (the 13 new / changed cases and the 6 re-aimed by M7.115c).
- **Next, in order (solo):**
  1. (done) m115c.log: 19 / 19 killed.
  2. Commit M7.115c (web/game.js, test/bb.test.js, tools/lrfree.py, tools/isracc.py, tools/mutants.py,
     build/lrfree_fixture.json, build/isracc_fixture.json, port.json, docs) -- the battery lines above, bb 1,832.
  3. A FULL battery (due: game.js, bb.test.js and the runner changed): `$p = Start-Process python -ArgumentList
     'tools/mutants.py','--jobs','20' -RedirectStandardOutput build/mutants/run.log -RedirectStandardError
     build/mutants/run.err -WindowStyle Hidden -PassThru` + watch.ps1 on $p.Id.  Expect it slow (~2 h) once: the
     killers the timeouts lost are re-learnt; add `$env:ZX_CASE_TIMEOUT='1500'` before it if the 180-s limit bites.
  4. Then the DECLARED list: $7E80's long path in play (rounds 4/10/34 from their first frame) is the next obvious one.

## RESTART HERE (2026-10-09c, M7.115c DONE, NOT COMMITTED -- affected 0 survivors / 133 timeouts; TIMEOUT RE-RUN RUNNING; next: its result, then commit)

- **M7.115c (uncommitted, all suites green): a later round's start FREE-RUNNING is the machine's.**  New oracle
  `tools/lrfree.py` -> `build/lrfree_fixture.json` (port.json `lrfree`, ship false; `python tools/lrfree.py capture|verify
  --jobs 11`, ~1.5 min, verify MATCH): the real load + ($FECD) poked in engine and machine, 11 worlds (round 2 from
  frames 480/560/640/700/745; r10, r41, n3 = 2-3-4, r81w = 81 then the wrap to 34; late546 / late744 poked at a pass
  $8D0C within 96 T of the boundary).  Dev aids (env LRFREE_PROG / SCR / PASSES / PDUMP / STOP) in its docstring;
  scratch drivers in `scratchpad/m7115c/` (cmp.js = the whole comparison).
- **Found and fixed (web/game.js):** (1) the odd ISR's draw from type 0's facing-1 bank $5B80 is CONTENDED: isracc.py now
  sweeps 16 `S` templates (source reads), BB_BLIT_ACC S00..S17, `ipSrc()` in entityDrawOne (isracc fixture regenerated,
  verify MATCH, only `tmpl` gained keys); (2) the build's clock began at the advance pass's $8D0C, 96 T before $97F8
  (hidden by the HALT's 4-T grid): `loopAdvance()` -- mainLoop sets `advDefer`, step() makes the advance after spending
  the pass's charge, or at the next frame's top when it ran past the interrupt (`advNext` counter); (3) `SK.FECD` grid
  key for the advance pass (+ pgSync(96)), handed to gridResolve via `fecdGrid`.
- **Gates:** LRF1..LRF4 (bb.test.js after the LR full block, ~line 406); IC1 now 56 templates; RA_DIST key 2 re-pinned
  `far 0:67 | near 0:13` (improved); PF2 restated (the PERFECT resume's $97F8 may be the next frame: `late` / advNext).
  **Suites: bb 1,831 / kit 120 / selftest 34.**  Docs: TIMING.md "M7.115c" section, STATUS paragraph + Left 3(a),
  TRAPS #306.
- Battery: +11 cases (`scratchpad/battery/add_m7115c.py`, backup mutate7.m7115c.bak), 7 re-aimed
  (`reaim115c.py`, backup mutate7.reaim115c.bak); every anchor exactly once (5,615 cases).
- `--affected` DONE 15:19: `LISTED 5611 KILLED 5478 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 133 BROKEN 0 CRASHES 0 MISSES 2
  -- 137.4 min on 20 workers` (nearly every case "affected": the new LRF block renumbered the blocks after it, so every
  killing block looked changed; MISSES are the two known M7.11 / M7.24 "whole suite only" cases).
- Timeout re-run 1 (15:48): `LISTED 133 KILLED 62 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 71 ... MISSES 0 -- 18.9 min`.  68 of
  the 71 are load-time anchors ("all" blocks) whose killing block was lost (last.json keeps killer_sha; a TIMEOUT
  overwrites it with None), so the cheapest-first sweep (886 s of blocks) cannot reach it in 180 s.  Fix:
  `tools/mutants.py` takes `ZX_CASE_TIMEOUT` (env, default 180) -- a runner file, so a FULL run is due anyway.
- **RUNNING: re-run 2 of the 71 with ZX_CASE_TIMEOUT=1500** (`scratchpad/m7115c/rerun.py` over `timeouts2.txt`) --
  python PID 33880 (build/mutants/to115c2.log / .err / .log.pid), started 16:07; watcher pwsh PID 23712 writes
  `build/mutants/to115c2.log.done`.  It records each case's killing block, so later runs are fast again.
  Don't edit game.js / bb.test.js / tools while it runs.
- **Next, in order (solo):**
  1. to115c2.log's LISTED line; fix any survivor.
  2. Commit M7.115c (web/game.js, test/bb.test.js, tools/lrfree.py, tools/isracc.py, build/lrfree_fixture.json,
     build/isracc_fixture.json, port.json, docs) with the battery line and bb 1,831; then a FULL battery (milestone).
  3. Still DECLARED after this: $7E80's long path in play (paMiss -- the next obvious one: rounds 4/10/34 run it from
     their first frame; pass plain T exact, its contended code fetches missing); the natural clear's / PERFECT / EXTEND
     $97F8 at the pass end unmeasured free-running (needs a natural round clear world); 2P later rounds free-running.

## RESTART HERE (2026-10-09b, FULL BATTERY AFTER M7.115 CLEAN -- NOTHING RUNNING; next: M7.115c)

- **FULL battery (milestone, after 983de2e) 01:08..01:25:** `LISTED 5604 KILLED 5598 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 3
  BROKEN 3 CRASHES 0 MISSES 0 -- 16.5 min on 20 workers`.  BROKEN B9 x2 / M7.69 and TIMEOUT M7.110's cursor guard: the
  known ones.  TIMEOUT M7.49 M14 and M7.99c "no access program": load artifacts -- `--match` alone on 2 workers 07:20:
  `LISTED 2 KILLED 2 ... TIMEOUTS 0 -- 3.1 min` (M7.99c still takes ~3 min alone: close to the 180-s limit under load).
- Suites unchanged: bb 1,827 / kit 120 / selftest 34.  **Next: M7.115c** (09a's item 2 below).  Solo.

## RESTART HERE (2026-10-09a, M7.115b COMMITTED 983de2e -- FULL BATTERY RUNNING; next: its result, then M7.115c)

- **`983de2e` M7.115b** -- rounds 2..81 (and the wrap) build and run their tail on their own measured program inside
  step(): `lrClock` (buildClockFor) + `lrHoles` / `lrModel` / `lrCheck`, `bbLrMap` (5 ms a build), `bbLrBuild`,
  `bbLrTail` (cached), `BB_LR` (491 segments, 65 KB); the tail through `r1tBegin` with `this.lrT` (round 1's own object is
  `bbR1tTail()`; every `BB_R1T.x` use in the tail is now `this.r1t.T.x`).  docs/TIMING.md "M7.115", STATUS paragraph.
  tools/lrstart.py's fixture also keeps the RAM at $97F8 (`snap_win`: player blocks, bottom attributes, $FEC7, $82D7,
  $83EC) and at each panel's CALL.
- **Suites: bb 1,827 / kit 120 / selftest 34.**  The LR gates are TWO blocks at the top of bb.test.js (line ~178):
  the quick one (LR1, LRq nine advances, LRt unit tails of rounds 2 / 81, ~2 s) -- the battery orders a case's blocks
  CHEAPEST first, and BB_LR's constant cases timed out (180 s) while the gates were one 146-s block -- and the full one
  (LR2/2b/2c all 336, LR3 through step(), LR4 14 unit builds).  Helpers `lrReplay`, `lrSnapIn`, `lrRuns` are prelude.
  The BD block's `playing(key, exact = false)` turns lrClock OFF (those rows pin the means); BD4 passes `true`.
- Battery: +20 cases (`scratchpad/battery/add_m7115.py`, `reaim115b.py`), 16 re-aimed (`reaim115.py`, `reaim115b.py`),
  backups `mutate7.m7115.bak` / `.reaim115.bak` / `.reaim115b.bak`.  `--affected` 01:08: `LISTED 32 KILLED 32 SURVIVORS 0
  DEAD ANCHORS 0 TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 17.1 min on 20 workers`.
- **RUNNING: the FULL battery (milestone)** -- python PID 31248 (build/mutants/run.log, .err, run.log.pid), started 01:08;
  watcher `scratchpad/battery/watch.ps1` (pwsh PID 21784) writes `build/mutants/run.log.done` at the end.  Result line:
  `build/mutants/summary.txt`.  The suite is now ~3 min alone (it was 3m17 at HEAD before M7.115), so expect ~60..90 min.
  Expected noise: BROKEN B9 x2 / M7.69, TIMEOUT M7.110's guard; LOAD artifacts re-run alone with `--match`.
  Don't edit game.js / bb.test.js / tools while it runs.
- **Next, in order (solo):**
  1. The battery's line into next.md (commit); fix any survivor / dead anchor (re-aim pattern `scratchpad/battery/reaim115.py`).
  2. **M7.115c: a later round's start FREE-RUNNING against the machine** (R1Td's check for rounds >= 2: the engine's
     own ISRs in the tail -- enemy draws of other rounds -- and the entry-window ISR, DECLARED now).  World: the real load
     (passacc's key script, payoff.js's engine side) with ($FECD) = 1 poked at the same frame in the engine and in the
     machine (a new tool, r1tail / passacc style: machine ISR T + acceptance phase + $8D0C frame/phase per ISR from the
     advance to some frames into round 2's play), then compare free-running.  Measure first; solo unless the ISR
     differences turn out to be unknown machine behaviour.

## RESTART HERE (2026-10-08u, M7.115a ORACLE COMMITTED (12a77ea) -- NOTHING RUNNING; next: M7.115b the engine)

- **`12a77ea` tools/lrstart.py + build/lrstart_fixture.json** (port.json `lrstart`, ship false).  `python tools/lrstart.py
  capture --jobs 20` (~5 min; `LRSTART_CACHE=scratchpad/lrs/advs.pkl` pickles the advances for re-runs), `verify`, `emit`
  (prints the engine's `BB_LR` body: N, SEGS, WPAT, R, LZ -- 103 KB, `scratchpad/lrs/emit.js`).
- MEASURED, 336 advances: every advance's two plain programs replay to the machine (marks, ends, ISR counts).  Program =
  per `round_players` segment list (`R`: build `|` tail; ids into the stream) with holes the engine fills:
  `w` win $97F8..$9858 = 1,035..1,163 T, no access (expect BB_BUILD_WIN's w4 + 836); `j` $83F1 JR = 12, or 11 when
  tileIndex's idx is 4; `l` lives = extModel('lives', cp) (+17 CALL? check against fixture holes.lives b64);
  `p` panel = extModel('panel', cp); `k` wallPattern = WPAT['sel_ptr'] (sel = BB_PALETTE_AT[$82D7] bit 7 BEFORE
  paletteStep, ptr = $6180 + 8 * $83EC before tileIndex -- only sel matters: ids 71 / 5).  The 2P spawn differs (2_1 vs 2_2).
  Segment bytes: LEB L, LEB n_acc, LEB n_ins, then n_acc x (k byte, LEB step; first step from the segment start), then
  n_ins grid bytes (tail only).  Tail derived constants: G = start of 'gate' seg; ST = G+7 / G+20; B5 = G+33; $9904 entries
  e2start+17, e3start+27 (checked on round 1's BB_R1T); END = sum.
  Two advances (2_1_*_8) take a gate-OPEN ISR in the entry window: DECLARE in the engine (count it, rule 6).
- **Next (M7.115b, solo):** web/game.js: `BB_LR` (emit), a Uint8Array LZ decoder (bbUnlz builds a JS array -- too big for
  10.8 MB), `bbLrSegs()` cached; buildClockFor -> `lrClock()` for rounds >= 2 inside step() (generalise r1Clock /
  bbR1Map: P.x = [Inf, Inf], holes filled at clock time, regenerated + compared at buildRt('lives'/'panel'), THROW if
  different); C = {at: plain $7F30, ks 1, kr 1, end}; roundStart spends M.endMain and sets r1Seq; the tail: generalise
  BB_R1T uses (r1tBegin, r1tPh, roundBanner_hp, bannerRt ERASE, bannerHold B5, bannerBegin ST length, line ~5822) to a
  per-start object.  Gates LR1.. (decode, programs = fixture per world, holes = engine models), then a free-running gate:
  the real load + $FECD poked in engine and machine (payoff.js style) -- the strongest check.

## RESTART HERE (2026-10-08t, STATUS REFRESHED (6197884) + LATER ROUND START SURVEYED -- NOTHING RUNNING; next: the oracle tools/lrstart.py)

- **`6197884` STATUS**: table (bb 1,819 / kit 120 / selftest 34, 5,584 cases, the 08s full battery) and "Left" item 3 now opens
  with TIMING.md's current Still DECLARED list.  Docs only.  (`docs/chrome_console_giant_item_crash_report.txt`, untracked: the
  `SM.A966t` grid crash -- already fixed in bd0efb9; leave it or delete it, it is the owner's file.)
- **The next DECLARED item: a LATER round's start (rounds 2..81, `$97F8..$8D0C` in play).**  The engine times it by
  contended means at one phase (`BB_ROUND_BUILD_T`, `BB_BUILD_K` 1.18 / 1.26, `BB_BANNER_AT`, BB_ISR_ACCEPT in the tail):
  K-T off, as round 1 was before M7.112 / M7.113 / R1Tf.  **MEASURED (scratch, `scratchpad/lrs/`):**
  - `survey.py` (17 s, 20 workers; `survey.json`): the plain run `$97F8 -> $9887` then `$9888 -> $8D0C` on 91 worlds
    (rounds 1..81 key 1, 2P rounds 2/6/41/81, lives 0/7 and `$83EC` shifted on rounds 2/41), split at the routine marks.
    FIXED in every round (one program): build 418, fpat 4, filler 293, preroll 96,772, loop 551,567 (the 26 scroll
    steps), rows 517, bolt 20, `$AA49` 24, `$BF39` 29, the banner loop 46,080 (round 81: skipped), e1 0.
    ROUND-ONLY (no 2P / lives / tile-shift dependence): bg `$7F2D` (~900..1,077 acc), spawn `$727B` (~1.3..2.3K),
    `$79AC` (34.5..37.2K acc, plain 112..123K T: the transform + drift painter), the erases e2 / e3 (610 acc, k pattern by
    round); plain T only: adv `$97F8..$9863` (161,799 / 20,40,60 / 81 differ), `$8C5E` (2,018..2,312).
    BY GENERATOR already in the engine: repaint (by round decade), digits (decade), lives (count / players).
  - `size2.py`: one byte-LZ stream over all 80 rounds' variable segments (r1tail's encode + lz): 6.7 MB -> **40,429 bytes**
    (`$79AC` 27.5K, bg 6.2K, spawn 2.8K, erases 0.8K); the fixed segments 1.4 MB -> 340 bytes.  Shippable as data.
- **Plan (M7.115, solo -- the method is R1Tf's, no unknown machine behaviour):**
  1. `tools/lrstart.py` (capture / verify / emit) -> `build/lrstart_fixture.json`: worlds = buildtime's natural chunks
     (back-to-back advances, `$FECD`) plus the pokes above; per round the plain programs per segment (assert fixed / round-only
     as surveyed), plain T per mark, the tail's instruction grid (needed: the tail's ISRs have both gates open); machine runs
     (contended, interrupts on): every ISR [main-line T, T, own delay, acceptance phase], marks, `$9887` and `$8D0C` frame+phase;
     assert the replay (program + machine ISR T) gives every mark.  Register in port.json (ship false).
  2. Engine: rounds >= 2 build + tail on the program (as BB_R1 / BB_R1T for round 1), the tail's grid for the acceptance
     phase; the fits (BB_BUILD_K, BB_BANNER_AT, BB_ROUND_BUILD_T) kept only where a gate pins them, or retired.
  3. Gates (LR1..: program, replay, through step() given ISR T, free-running), mutation cases, `--affected`, commit.

## RESTART HERE (2026-10-08s, FULL BATTERY DONE + ITS ONE REAL FINDING FIXED -- NOTHING RUNNING; next: STATUS refresh)

- **FULL battery (milestone, after PA4c) 17:10..18:31, shared the machine with the Fist battery:** `LISTED 5584 KILLED 5578
  SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 3 BROKEN 3 CRASHES 0 MISSES 2 -- 81.0 min on 20 workers`.
  - BROKEN B9 x2 / M7.69 and TIMEOUT M7.110's cursor guard: the known, expected ones.
  - TIMEOUT M7.49 M14 and MISSES M7.11 / M7.24: LOAD artifacts -- re-run alone on a quiet machine (`--match`, 4 workers)
    all three KILLED inside the selection, no miss.
  - TIMEOUT M7.99c "a routine with no access program is not refused": REAL (reproduced alone).  C3's `noProg` let the
    whole reveal run before it could say "not refused" (> 180 s).  Fixed in test/bb.test.js (C3's `bent`: a model asked
    for after the bent one throws 'bent: ... let through' -- the refusal throws first).  `--match M7.99c --jobs 20`:
    `LISTED 47 KILLED 47 ... TIMEOUTS 0 MISSES 0 -- 13.8 min` (that case now killed by C3 in 160 s).
- **Suites: bb 1,819 / kit 120 / selftest 34.**  Next: as 08r's "Next, in order" items 2 and 3 (STATUS refresh, then the
  later round start's ISR acceptance).  Solo.

## RESTART HERE (2026-10-08r, PA4c COMMITTED 1d4e93f -- FULL BATTERY QUEUED; next: refresh STATUS's "Left", then pick the next DECLARED item)

- **`1d4e93f` PA4c** -- handOpen() charges `bbColdT(phase)` (BB_SPINE.COLD: plain 54,451 T + the 13,648-access program
  replayed by bbUlaDelay) instead of COLD_PH's straight lines.  tools/coldstart.py + build/coldstart_fixture.json
  committed (verify MATCH), port.json registers `coldstart` (ship false).  Gates: H-d(c) cold midpoint band now must be 0;
  new PA4c CS1..CS3; **PA4 re-pinned 0.000 and rb === null: every pass of the 2,565 is the machine's, free-running**.
  `node scratchpad/m7114d/payoff.js`: first bad null, ISR T 380 same / 0 differ.  docs/TIMING.md "PA4c" section + the two
  "Still DECLARED" lines corrected; STATUS has a PA4c paragraph.
- **Suites: bb 1,819 / kit 120 / selftest 34.**
- Battery: +6 cases (`scratchpad/battery/add_pa4c.py`, backup `mutate7.pa4c.bak`) -> ~5,584.  `--match PA4c --jobs 6`:
  `LISTED 6 KILLED 6 SURVIVORS 0 ... MISSES 0 -- 14.4 min`.
- **UPDATE 18:20: the full run IS RUNNING -- python PID 34660, launched 17:10 by the waiter (alongside the Fist battery,
  so slower than 37 min).**  A mistaken second launch at 18:14 was refused by the runner's lock (scratch/mutants/.running)
  but TRUNCATED build/mutants/run.log (the run keeps writing at its own offset: expect NULs before its tail) and
  run.log.err; run.log.pid rewritten.  Watcher `scratchpad/battery/watch.ps1 34660 build/mutants/run.log` (pwsh PID 33088)
  writes `build/mutants/run.log.done` when 34660 exits.  The authoritative line is build/mutants/summary.txt (plus last.json).
- (was) **RUNNING: the FULL battery (milestone)** -- waiter `scratchpad/battery/wait_then_run.ps1 build/mutants/run.log --jobs 20`
  (pwsh PID 8724, launched ~16:20) is WAITING for the Exploding Fist project's battery to end, then runs; it writes
  `build/mutants/run.log.pid` at launch and `build/mutants/run.log.done` at the end (summary also in build/mutants/summary.txt).
  Don't edit game.js / bb.test.js / tools until it LAUNCHES (the .pid file exists).  If the session died: `cat build/mutants/run.log.done`.
  Expected noise (as 08n): BROKEN B9 x2 / M7.69, TIMEOUT M7.110's guard.  Any survivor / dead anchor: fix (re-aim pattern
  `scratchpad/battery/reaim114e.py`), `--match` them, commit with the line.
- **Next, in order (solo):**
  1. When the battery's done: record its line in next.md (commit), fix anything it found.
  2. docs/STATUS.md is stale above its new paragraphs ("Where it stands" table says bb 1,775 / 5,120 cases, "Left" is as
     of M7.83): refresh the table and the "Left" list from TIMING.md's "Still DECLARED" lines (cheap, do it first).
  3. Then the next DECLARED item with the most machine behaviour in it.  Candidates (TIMING.md): BB_ISR_ACCEPT on the
     blocks with no instruction grid (a LATER round's start -- round 2+'s tail/banner, the lazy blocks) -- measure first,
     insgrid/r1tail-style, on a round-2 start; the fitted contentions of EXTEND (-5.8K..4.7K T), the storm ticks, the round
     build and the flood row (DECLARED stretches); sound's declared gaps (STATUS Left #2).  The later round start is the
     natural continuation of R1Tf (same tool pattern).  Solo; agents only if the machine behaviour is unknown.

## RESTART HERE (2026-10-08q, PA4 DIAGNOSED + ORACLE WRITTEN (uncommitted) -- NOTHING RUNNING; next: wire it into the engine)

- **PA4's -0.218 T is NOT the control select's scan means.**  `node scratchpad/pa4/debt.js` (the real load, frame by frame:
  ctrl state, ctrlDebt, tframe, carry): the menu's fractions (SCAN_T 970.23 etc.) all die at frame 88's HALT (the probe's
  `$FAC5 EI / HALT` resyncs to the boundary; the probe is cycle-exact).  The fraction is born at frame 344 in `handOpen()`
  (web/game.js ~17074): `cold = this.phaseT(L.COLD_PH, this.tframe)` -- BB_SPINE.COLD_PH is 64 samples every 1,092 T with
  straight lines between (17/78 = 0.21795 at the real load's phase 994).  Exact at the samples, up to ~150 T off between.
- **New oracle `tools/coldstart.py` -> `build/coldstart_fixture.json`** (UNCOMMITTED, ~14 s, `verify` / `emit` modes):
  `$F5CC -> $8CCA` (interrupts off) is ONE program: plain **54,451 T**, **13,648 contended accesses** (digest
  `9cc3d833156fddf7`), its replay from the phase (each access waits DELAYS_48K at its wall phase) = the machine's T at
  64 phases + 16 midpoints + 400 random, on p2p2, and on the REAL LOAD (frame 344, phase 994: **67,376 T**).  Packed: LEB128
  steps + r1tail's byte LZ77 = 27 bytes (`python tools/coldstart.py emit` prints the JS line).  Scratch probe:
  `scratchpad/pa4/coldprog.py`.
- **Next, in order (solo):**
  1. port.json: register `coldstart` (ship false, test-only; note like isracc's).
  2. web/game.js: `BB_SPINE.COLD = { PLAIN: 54451, LZ: '<emit>' }`, a decoder (bbUnlz + LEB128 steps, cached), and in
     handOpen `cold = PLAIN + replay(prog, phase)` via bbUlaDelay (start phase = `this.tframe` mod frame, as phaseT gets).
     Keep COLD_PH (H-d(c) asserts it = loadspine's table and handOpen = it at the 64 samples -- still true; its midpoint
     band becomes 0: tighten that gate to exact).
  3. bb.test.js: new gate block (PA4c?): fixture registered; decoded program count/digest = fixture; handOpen's cold =
     the fixture's `samples` (40 random phases) and `real.t` at `real.phase`; re-pin PA4 (`PA4_EARLY` at bb.test.js:39141)
     -- expect '0.000' -- and update its text + TIMING.md "Still DECLARED" lines (M7.114d / R1Tf sections say the
     fraction is the scan means: correct that) and STATUS.
  4. Build, `node test/kit.test.js` + bb suite, `node scratchpad/m7114d/payoff.js` (expect all exact), mutation cases
     (`scratchpad/battery/add_*.py` pattern), then the FULL battery (due at this milestone) via
     `scratchpad/battery/wait_then_run.ps1 build/mutants/run.log --jobs 20`; commit tool + fixture + engine + tests.
- Suites unchanged: bb 1,816 / kit 120 / selftest 34 (HEAD cfd8490).

## RESTART HERE (2026-10-08p, R1Tf COMMITTED -- NOTHING RUNNING; next: PA4's -0.218 T)

- **R1Tf committed** (`git log -1 -- tools/r1tail.py`).  `--affected` 15:16..15:28: `LISTED 28 KILLED 28 SURVIVORS 0 DEAD ANCHORS 0
  TIMEOUTS 0 BROKEN 0 CRASHES 0 MISSES 0 -- 12.7 min`.  5,578 cases.  bb 1,816 / kit 120 / selftest 34.
- **Next: PA4's -0.218 T** (08o's last bullet).  Solo.  A FULL battery is due at the next milestone (after PA4, or before a
  release) -- use `scratchpad/battery/wait_then_run.ps1 build/mutants/run.log --jobs 20` when another project is busy.

## RESTART HERE (2026-10-08o, R1Tf WRITTEN -- since committed, see 08p)

- **R1Tf = round 1's tail takes its ISRs at the machine's acceptance phase** (docs/TIMING.md "R1Tf", STATUS).  tools/r1tail.py
  now records the plain run's instruction T sequence (362,817, no EI / HALT, one sequence on all 16 runs: `n_ins`,
  `ins_digest`, `ins_lz`) and each machine ISR's acceptance phase (`isrs[i][3]`); fixture regenerated (only those added,
  verify MATCH).  Engine: `BB_R1T.INS`, `bbR1tIns()`, `r1tPh(x)`, r1tStep sets `gridPhV`.  R1Td re-pinned EXACT (828/828,
  `$8D0C` 0..0); R1Tf new.  payoff.js: all 380 ISRs + 2,565 passes of the real load free-running = the machine's.
  **Suites: bb 1,816 / kit 120 / selftest 34**; r1tail / passacc / isracc verify MATCH.
- Battery: 8 new cases (`scratchpad/battery/add_r1tf.py`, backup `mutate7.r1tf.bak`) -> 5,578.  **QUEUED: `--affected --jobs 20`
  via `scratchpad/battery/wait_then_run.ps1` (new, generic: `<log> <mutants.py args...>`; pwsh PID 34104) -> build/mutants/
  r1tf.log, `.pid` at launch, `.done` at the end** (another project's battery was running at 14:40).  Cron a7085d4b polls.
  Don't edit game.js / bb.test.js / tools until it LAUNCHES.  If the session died: `cat build/mutants/r1tf.log.done`.
- When clean: commit R1Tf (web/game.js, test/bb.test.js, tools/r1tail.py, build/r1tail_fixture.json, docs) with the line and
  bb 1,816; then next.md.
- **Then: PA4's -0.218 T** -- the control select's scan means (BB_FE.SCAN_T are path means over 64 phases; the real load's
  control select runs before play, so its T fraction rides on into $F5BC..play).  Measure first: which of the menu's scans the
  real load takes and their exact T at their phases (the 64-phase tables exist: `timing.pass`).  Solo.

## RESTART HERE (2026-10-08n, M7.114e COMMITTED 827bc90 -- NOTHING RUNNING; next: the round start's ISR acceptance)

- **`827bc90` M7.114e** (08m below has the detail).  FULL battery 13:19..13:55: `LISTED 5571 KILLED 5563 SURVIVORS 0
  DEAD ANCHORS 4 TIMEOUTS 1 BROKEN 3 CRASHES 0 MISSES 0 -- 36.8 min` (BROKEN B9 x2 / M7.69, TIMEOUT M7.110's guard:
  expected).  Dead anchors fixed (`scratchpad/battery/reaim114e.py`, backup `mutate7.m7114e.bak`): H-d hand -> reset(buf,
  true); M7.28 '0'/'O' and M7.32 BB_DIGITS -> bd0efb9's digit face; M7.114d's refusal DROPPED (now a counted miss, BUG1008
  covers it).  `--match` on them: LISTED 5 KILLED 5, clean.  **5,570 cases.  Suites: bb 1,815 / kit 120 / selftest 34.**
  This full run also closes the post-bd0efb9 milestone.
- **Next: the round start's ISR acceptance (R1Td)** -- free-running the ISR T now differs only at 421..469 by -6..+8 T
  (`node scratchpad/m7114d/payoff.js`; `node scratchpad/m7114c/drive.js` is exact): the title's tail / banner blocks have
  no instruction grid, so their in-block ISRs take BB_ISR_ACCEPT (4).  Measure first: which instruction each of those ISRs
  is taken after on the machine (insgrid-style over the round start, frames 400..470).  Then PA4's -0.218 T fraction (the
  control select's scan means).  Solo.
- Helper kept: `scratchpad/battery/wait_then_full.ps1 <log>` -- detached, waits until no other project's battery runs,
  then launches the full battery and writes `<log>.pid` / `<log>.done` (use it when another project is busy).

## RESTART HERE (2026-10-08m, M7.114e WRITTEN -- since committed 827bc90, see 08n)

- **M7.114e = the load's world is the tape's** (docs/TIMING.md "M7.114e", STATUS, TRAPS #305).  Frame 691's +1,510 T was
  the ODD ISR (not the even one): slot 3's `$B0A2` divider passing 21 frames early, because the hand-over's `reset()` spawned
  round 1 itself and the round start spawned again, rolling `$73AF` (the +4 seed) twice.  A class sweep
  (`scratchpad/m7114e/firstread.py` + `handcmp.js`: every byte the machine reads before writing, load to 760, against the
  engine after handDone) found `$73AF` and `$856C`'s even bytes.  Fix: `BB_TAPE_RMW = { $73AF: $02 }` (tools/passacc.py
  BOOT_RMW -> fixture `boot_rmw`, regenerated: only that key added, verify MATCH), seeded in reset() before the spawn;
  `reset(keys, load)` -- handDone passes `true`: no spawnRound, no tile-even carry.
  Result: drive.js all 361 ISRs exact; free-running all 2,565 passes the machine's to 759 (GR4 re-pinned: no part);
  ISR T left only 421..469 (-6..+8, the round start's acceptance R1Td).
- Gates: GR4 re-pinned, ME1 new.  **Suites: bb 1,815 / kit 120 / selftest 34**; passacc + isracc verify MATCH.
- Battery: 6 new cases (`scratchpad/battery/add_m7114e.py`, backup `mutate7.bug1008.bak`) -> 5,566 cases.  No separate
  --affected: ONE FULL run covers the post-bd0efb9 milestone and M7.114e.  **QUEUED: `scratchpad/battery/wait_then_full.ps1`
  (pwsh PID 25684, detached) waits until no other project's battery runs (the_way_of_the_exploding_fist's was running at
  13:07), then launches `tools/mutants.py --jobs 20` -> build/mutants/run.log; it writes `run.log.pid` at launch and
  `run.log.done` at the end.**  Cron 82da335c polls (session-only).  If the session died: `cat build/mutants/run.log.done`
  (or the LISTED line in run.log / build/mutants/summary.txt); if neither .pid nor .done exists and PID 25684 is gone,
  relaunch the waiter: `Start-Process pwsh -ArgumentList '-NoProfile','-File','scratchpad/battery/wait_then_full.ps1',
  'build/mutants/run.log' -WindowStyle Hidden`.  DON'T edit game.js / bb.test.js / tools until it has LAUNCHED (worker trees
  copy at launch).
  Expect BROKEN 3 (B9 x2, M7.69), TIMEOUT 1 (M7.110's guard); M7.98's two / UM3 timeouts were gated as slow survivors in
  7324372.  Any other TIMEOUT: `python scratchpad/bugs/try_mut_long.py "<label part>"` (passes alone = slow survivor: gate).
- **When clean: commit M7.114e** (web/game.js, test/bb.test.js, tools/passacc.py, build/passacc_fixture.json, docs) with the
  battery line, bb 1,815; then next.md.
- **Then: the round start's ISR acceptance (R1Td; its blocks have no grid -- 421..469 free-running) and PA4's -0.218 T
  fraction (the control select's scan means).**  Solo.

## RESTART HERE (2026-10-08l, everything COMMITTED (7324372) -- NOTHING RUNNING; next: a FULL battery, then M7.114e)

- **`7324372`**: the three slow survivors of the post-M7.114d full battery gated (UM3's beside count, UM3b new, the
  blow click's clamp driven directly); try_mut kills all three.  **Suites: bb 1,814 / kit 120 / selftest 34.**
  Battery list 5,560 (BUG1008's 14 less the 4 equivalent pgBad cases).
- **`bd0efb9`**: the owner's four bugs (08k below).
- **First thing: a FULL battery** (milestone: game.js changed for the bugs) -- but ONLY when no other project's battery
  is running (12:40 today `the_way_of_the_exploding_fist` had 20 workers up; two batteries at once time each other
  out -- check `Get-CimInstance Win32_Process -Filter "Name='node.exe'"` for `.mutants_suite.js`).  Then:
  `$p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20' -RedirectStandardOutput build/mutants/run.log
  -RedirectStandardError build/mutants/run.err -WindowStyle Hidden -PassThru` and watch.ps1 on $p.Id / build/mutants/run.log.
  Expect BROKEN 3 (B9 x2, M7.69), TIMEOUT 1 (M7.110's guard).  Any other TIMEOUT: `python scratchpad/bugs/try_mut_long.py
  "<label part>"` (an 1,800 s limit; passes alone = slow survivor: gate it).
- **Then M7.114e** -- frame 691's even ISR plain T (08j below).  Solo.

## RESTART HERE (2026-10-08k, the owner's four bugs FIXED bd0efb9; try_mut RUNNING; next M7.114e)

- **FULL battery after 9373e4e (10:20..10:55): `LISTED 5555 KILLED 5548 SURVIVORS 0 DEAD ANCHORS 0 TIMEOUTS 4 BROKEN 3
  CRASHES 0 MISSES 0 -- 35.2 min`.**  BROKEN = B9 x2, M7.69 (expected).  TIMEOUTS: M7.110's guard (expected) and three
  NOT seen before: "M7.114c: the blow click clamped to span frames", "M7.98: mainLoop runs a pass beside the block",
  "M7.98: the pass does not wait for the block" -- being checked (below).
- **`bd0efb9` -- the owner's four bugs** (commit message has the detail; TRAPS #304):
  (1) the giant item crash = M7.114d's gridWalk THROWING on a CALL key summed n times ($A929's 'A966t' x3) -> a counted
  miss (gridCallN); (2) the peach / boss sprite banks $C080 / $FE02 were never loaded -> build/giant_sprites.json
  (tools/extract_giant_sprites.py, port.json 'giantspr'); (3) round 1 flashed at the hand-over -> handDone keeps the
  display; (4) HUD squares = the banner font's square zero beside a second digit face -> one face (make_digits.py takes
  the banner font's digits, zero slashed).  Gates "2026-10-08 (1)..(4)" at the end of bb.test.js.
  Battery: `--match BUG1008` LISTED 14 KILLED 9 TIMEOUTS 5 -> four pgBad marks EQUIVALENT (removed with their cases),
  the hand-over-bitmap case gated by the attribute check.  **Suites: bb 1,812 / kit 120 / selftest 34.**  5,565 cases.
- **RUNNING: `scratchpad/bugs/tries2.py` (PID 8016, watcher 33524, log scratchpad/bugs/tries2.log, `.done` beside it)** --
  try_mut over the hand-over case and the three timeouts; it EDITS web/game.js in place, don't touch game.js until it
  ends.  A case that passes the suite alone is a slow survivor: gate it.  Then a FULL battery (milestone), next.md.
- **Next: M7.114e** (unchanged -- 08j below).  Solo.

## RESTART HERE (2026-10-08j, M7.114d COMMITTED 9373e4e -- FULL battery RUNNING; next M7.114e)

- **`9373e4e` M7.114d = the acceptance phase from the instruction grid** (08i below; docs/TIMING.md "M7.114d", TRAPS #303).
  Battery: `--match M7.114d` (10:14) `LISTED 133 KILLED 133 SURVIVORS 0 ... MISSES 0 -- 19.4 min`.  Battery list 5,555.
  **Suites: bb 1,808 / kit 120 / selftest 34**; insgrid verify MATCH.
- **RUNNING: the FULL run (milestone), PID 15424, watcher 10556, log build/mutants/run.log, `run.log.done` beside it;
  result line in build/mutants/summary.txt.**  Expect BROKEN 3 (B9 x2, M7.69), TIMEOUT 1 (M7.110's guard).  Any other
  TIMEOUT: `python scratchpad/m7114/try_mut.py "<label part>"` (passes alone = slow survivor: gate it).  Record the line here.
- **Next: M7.114e -- frame 691's even ISR plain T** (+1,510 / +1,357 at 691..741: a bubble-manager arm's T; programs
  match).  `node scratchpad/m7114c/drive.js` prints it (given the machine's ISR T), `node scratchpad/m7114d/payoff.js`
  shows free-running parting at 691 (GR4 pins it -- re-pin when fixed: the next part, or none to 759).  Measure the arm on
  the machine first (isracc-style probe of 691's even ISR, which slot / arm and its T).  Then: PA4's 0.218-T fraction
  (the control select's scan means) and the round start's ISR acceptance (R1Td; blocks with no grid).  Solo.

## RESTART HERE (2026-10-08i, M7.114d WRITTEN, NOT committed -- an --affected battery RUNNING)

- **M7.114d = the acceptance phase from the instruction grid** (docs/TIMING.md "M7.114d", TRAPS #303, STATUS).
  tools/insgrid.py (new) -> build/insgrid_fixture.json (port.json `insgrid`), `verify` MATCH.  Engine: pg / pgSync / pgBad,
  gridWalk, gridPh, gridResolve, BB_GRID_SM (generated by scratchpad/m7114d/gen_sm.py from costsmall), BB_GRID (SK / HUD /
  RC / SC / JT / PE / TR / EK / IT / LK keys), BB_PASS_GRID, BB_JT_GRID; edgeLook path-aware.  Gates GR1..GR5 (block at the
  end of bb.test.js); JT7 got letGo, PA6 both arms of each look.  **Suites: bb 1,807 / kit 120 / selftest 34.**
  Result: given the machine's ISR T all 2,565 pass grids and all 289 in-pass acceptance phases exact; FREE-RUNNING the real
  load holds pass for pass to frame 690 (GR4 pins the part at 691).
- Battery: 74 new cases (`scratchpad/battery/add_m7114d.py`, backup `mutate7.m7114c.bak`).  **RUNNING: `--affected --jobs 20`
  (PID 3252, watcher 3828, log build/mutants/m114d.log, `.done` beside it; cron eabae327 polls -- session-only).**
  RESULT (09:04): `LISTED 338 KILLED 269 SURVIVORS 1 DEAD ANCHORS 60 TIMEOUTS 8 BROKEN 0 CRASHES 0 MISSES 1 -- 36.5 min`.
  Done since: the 60 dead anchors re-aimed (`scratchpad/battery/reaim114d.py`, 5,556 cases); gates added for the survivor
  ($A9ED's look on round 80 with no boss -> PA6 lk80n), the MISS (zs's unsummed key -> GR5 qZ) and phMiss (GR5 qR).
  bb still 1,807, green.  **RUNNING: `scratchpad/m7114d/tries.py` (PID 10208, watcher 2120, log
  scratchpad/m7114d/tries.log, `.done` beside it; cron 0c05a8de)** -- try_mut over the 8 timeouts + 2: it EDITS
  web/game.js in place.  DONE 09:45: gated the real ones (GR1 the LK heads vs costsmall, GR4 a stale phase, GR5 a
  deferred rest / an invalid region's instructions, GR6 14 off-play paths tile their charges -- the carried-P2 case);
  the $925A / $92C0 CALL-flag cases were EQUIVALENT (a CALL whose rest is empty): one dropped, one re-aimed to $9377's
  cell.  **bb 1,808.**  **RUNNING: `--match M7.114d --jobs 20` (PID 10656, watcher 16100, log build/mutants/m114d2.log,
  cron polls).**  When clean: commit M7.114d (game.js, bb.test.js,
  port.json, tools/insgrid.py, build/insgrid_fixture.json, docs) with the battery line and bb 1,807; then a FULL run.
- Also to do at commit: game.js line ~546's BB_ISR_ACCEPT comment still says "DECLARED until ... M7.114d" -- reword
  (now: only where no grid: the round start's blocks, misses).
- **Next after: M7.114e -- frame 691's even ISR plain T (+1,510 / +1,357 at 691..741, a bubble-manager arm;
  `node scratchpad/m7114c/drive.js` prints it; `node scratchpad/m7114d/payoff.js` shows free-running parting there).**
  Then the PA4 fraction (the control select's scan means) and the round start's ISR acceptance (R1Td).  Solo.

## RESTART HERE (2026-10-08h, FULL battery after M7.114c CLEAN; M7.114d IN PROGRESS)

- **FULL RUN after 1684655 (07:15..07:36): `LISTED 5482  KILLED 5478  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1  BROKEN 3
  CRASHES 0  MISSES 0 -- 21.1 min on 20 workers`** (BROKEN = B9 x2, M7.69; TIMEOUT = M7.110's guard: expected).
  NOTHING RUNNING.
- **Next: M7.114d -- the acceptance phase** (08f's last bullet).  Solo.

## RESTART HERE (2026-10-08g, M7.114c COMMITTED 1684655 -- FULL battery RUNNING; next M7.114d)

- **`1684655` M7.114c = the ISRs' own contention** (08f below has the detail).  Second `--affected` after the fixes:
  `LISTED 119 KILLED 119 SURVIVORS 0 TIMEOUTS 0 MISSES 0 -- 15.6 min`.  Suites bb 1,802 / kit 120 / selftest 34.
- **RUNNING: the FULL run (milestone), PID 3340, watcher 19840, log build/mutants/run.log, `run.log.done` beside it;
  result line in build/mutants/summary.txt.**  Expect BROKEN 3 (B9 x2, M7.69), TIMEOUT 1 (M7.110's guard).  Any other
  TIMEOUT: `python scratchpad/m7114/try_mut.py "<label part>"` (passes alone = slow survivor: gate it).
- **Next: M7.114d -- the acceptance phase** (08f's last bullet).  Solo.

## RESTART HERE (2026-10-08f, M7.114c WRITTEN, NOT committed -- an --affected battery RUNNING)

- **M7.114c = the ISRs' own contention** (docs/TIMING.md "M7.114c", TRAPS #302).  tools/isracc.py (new) ->
  build/isracc_fixture.json (port.json `isracc`), ~12 s, `verify` MATCH: the real load's 361 ISRs of frames 400..760,
  each one's access program by class (ent / bent / in / b5 / bub) and delay, replay asserted; and 40 blitter templates
  ($A447 erase E / draw D by path and Y&7, $B9E7 B by Y&7).  Engine: `this.ip` built during isr() (`ipTmpl`, `ipPort`,
  `ipShift`, the settler's reads), `ipWait` from the acceptance phase, `isrCost = isrPlain + isrD`; `BB_BLIT_ACC`
  (packed templates), `BB_ISR_A3AD / B62C / RISE / CALL / TRAVEL / TR_BF / TR_POST / BF_A447 / JP`, `BB_ISR_IN`;
  acceptance phase = `haltPh` (round HALT's 4-T grid) else `BB_ISR_ACCEPT` 4 (PROVISIONAL); the blow click clamped to ONE
  frame (overrun fix).  Gates IC1..IC3 (block at the end of bb.test.js); re-pinned PA4 (-0.218), R1Td (0..77, 473/828
  -8..5), RA (distribution), BT3, PK7 (49 / 115), census ODD_PIN.  **Suites: bb 1,801 / kit 120 / selftest 34**, romscan 0,
  passacc + isracc verify MATCH.  Docs (TIMING, STATUS, TRAPS #302) written.
- Battery: 5,479 cases (`scratchpad/battery/add_m7114c.py` 65 new, `reaim114c.py` 29 re-aimed; backup
  `mutate7.m7114b.bak`).  First `--affected` (06:05..06:31): `LISTED 434 KILLED 426 SURVIVORS 7 TIMEOUTS 1 MISSES 1` --
  the capture / rise / holding-bubble paths the real load never reaches -> IC4 (isracc 'even': five machine scenes of
  $B62C on round1_48, all exact; it found the capture's contended `LD A,($745A)` read, now on the program); two
  EQUIVALENT cases re-aimed (template k, column 0); the cadence OUT -> IC3 (cadence 9); the MISS -> IC1 calls the
  uncached `bbBlitUnpack` (`scratchpad/battery/fix_m7114c.py`; 5,482 cases).  bb now **1,802**.
  **RUNNING: second `--affected --jobs 20` (PID 21756, watcher 21844, log build/mutants/m114c2.log, `.done` beside it;
  cron c7569ccd polls it -- session-only).**  If the session died: read the log's LISTED line.
  Survivors -> gate them (a TIMEOUT that passes alone: `python scratchpad/m7114/try_mut.py "<label part>"` = slow survivor).
- When clean: commit M7.114c (game.js, bb.test.js, port.json, tools/isracc.py, build/isracc_fixture.json, docs) with the
  battery line and bb 1,801; then a FULL run (milestone) via the Start-Process line.
- **Found, not fixed:** given the machine's ISR T the real load's even ISR PLAIN T differs at 691..741 by +1,510 / +1,357 /
  -1,357 / -1,510 (programs match) -- a bubble-manager arm's T.  `node scratchpad/m7114c/drive.js` prints it.
- **Next after the commit: M7.114d -- the acceptance phase** (the instruction in progress at the boundary; the residue of
  R1Td / PA4 / BT3 and the real load's frame 534 free-running).  Ideas: the pass access program already knows the
  instruction starts of contended accesses; per-callee instruction-start programs; or measure whether a coarser rule
  (callee entry vs mid-callee) gets most ISRs exact.  Measure first (scratchpad/m7114c/isracc.py has the phases).  Solo.

## RESTART HERE (2026-10-08e, M7.114b COMMITTED deb1287 -- full battery CLEAN; next M7.114c)

- **`deb1287` M7.114b = the dark window** (the 08d section below has the detail).  Suites bb 1,798 / kit 120 / selftest 34.
  Its battery: --match of the last 9 `LISTED 9 KILLED 9 ... MISSES 0 -- 12.1 min`.
- **FULL RUN after deb1287 CLEAN (04:34..04:51): `LISTED 5414  KILLED 5410  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0 -- 16.9 min on 20 workers`** (BROKEN = B9 x2, M7.69; TIMEOUT = M7.110's guard, expected).
  NOTHING RUNNING.  (A TIMEOUT that passes the suite alone -- `python scratchpad/m7114/try_mut.py "<label part>"` -- is a
  SLOW SURVIVOR, not a hang: gate it.)
- **Next: M7.114c -- the ISRs' own contention** ($A3AD's draw, $AA60's $73A6 reads): the free-running clock is ~1,037 T
  off by play (PA4) and the census pin (ODD_PIN) waits on it; with it, the real load's frame 534 should hold
  free-running (engplay + cmp5 400).  Solo -- the method is M7.113's / M7.114a's (access programs replayed on the clock).

## RESTART HERE (2026-10-08d, M7.114b written, NOT committed -- a --match battery RUNNING)

- **FULL battery after M7.114a (01:44..02:14): `LISTED 5406  KILLED 5393  SURVIVORS 2  DEAD ANCHORS 0  TIMEOUTS 8
  BROKEN 3  CRASHES 0  MISSES 0 -- 29.9 min`.**  The 7 new "TIMEOUTs" were NOT hangs: survivors whose whole-suite
  confirmation ran past the runner's per-case limit on the loaded machine (each passes the suite alone in ~3 min --
  checked by hand with `python scratchpad/m7114/try_mut.py "<label part>"`, which applies one case, runs the suite, restores).
  M7.114a re-phased the scenes that drove those step() paths.  Fixed in the uncommitted M7.114b:
  - PA11 (stub mainLoop): a block's return clears `blocked` (H23); 'perfect' never charged as a pass (M7.95); a cut on
    the clear charged as the clear and spent (M7.106 x2); the next step() resumes the cut (M7.106 "never resumed").
  - CD3: a direct cdResume -- $97F8's entry where the cut pass ended (M7.106 "$97F8's entry where the build ended").
  - PA9: step()'s pass loop THROWS past BB_STEP_TURNS 1024 (the two M7.98 cases, which DID spin: killed now).
  - The census mutant was equivalent (the tape seed); re-aimed to flip the phase -- killed.
- **M7.114b = the dark window** (see docs/TIMING.md "M7.114b"): survey `scratchpad/m7114/isrbytes.py` -- $FEC5 is the
  only byte the ISRs read that the main line writes in the real load's play; passacc.py records each ISR's $FEC5
  (`gates`, 0 at 534 only); `elemArmDone` places the window (`passClock`, `BB_DARK`) -> `isrDark`; step() runs that ISR
  with $FEC5 = 0.  Rows PA8 (gates, given the machine's ISR T), PA9, PA10 (the window's edges and waits), PA11; PJ7 gives
  each ISR the machine's own gate.  **Suites: bb 1,798 / kit 120 / selftest 34**; passacc verify MATCH; romscan 0.
  Free-running real load still differs at 534 (clock ~1,037 T off: M7.114c).
- Battery list 5,414.  `--affected --jobs 20` (03:02..03:22): `LISTED 143 KILLED 140 SURVIVORS 2 TIMEOUTS 1` -> PA10,
  PA9's stub made finite.  `--match` 11 (03:31..03:57): 6 killed, 1 survivor, 4 timeouts -> the survivors above, PA11.
- **RUNNING: `--match` of the 9 left (PID 25364, watcher 14020, log `build/mutants/m114b2.log`, `.done` beside it).**
  When LISTED 9 KILLED 9: commit M7.114b (all of game.js, bb.test.js, tools/passacc.py, build/passacc_fixture.json,
  docs/TIMING.md, docs/STATUS.md) with the battery lines above and bb 1,798; then a FULL run (milestone) and M7.114c.
- Python heredocs in the Bash tool turned a doubled backslash-n into a real newline in mutate7.py twice -- build
  backslashes with chr(92) in such scripts.

## RESTART HERE (2026-10-08a, M7.114a COMMITTED -- the in-play pass on the frame clock; FULL battery NOT yet run)

- **M7.114a = the in-play pass on the frame clock** (commit `744544f`).  Read docs/TIMING.md "M7.114a", TRAPS #300 / #301.
  - Measured: `tools/passacc.py` (new) -> `build/passacc_fixture.json` (port.json `passacc`), ~10 s, `verify` MATCH.  The
    real load (boot.pkl, the KEYBOARD drive embedded), frames 470..759, 2,565 passes: each pass's contention is its ACCESS
    PROGRAM (every contended access's plain offset + T into its instruction) replayed from its phase with the ISRs' T at
    their points.  BB_PASS_REST (78 T) was a phantom; a plain pass is the skeleton 479 + its callees' own T.
  - Engine: BB_PASS_K / BB_PASS_PROV / BB_PASS_REST GONE.  `pa` / `passBegin` / `pbase` / `pAt` (the program), `passWait`
    + `pTail` / `passTailWait` (the waits; the tail after the ISR), `passSplit` / `passSplitCharge` (the interrupt INSIDE
    the pass at a callee's entry, or at an edge read a fixed way in: `BB_EDGE_LOOK`, `edgeLook` -- $8669 from
    itemSpawnT), `ctrRead` (a counter read past the point sees the ISR's INC; $9E50 after its kid -- body before the
    ISR, DECLARED), `passSettle` (a mid-pass block's prefix: the join), `calleeAt` (cdPos / pausePos / joinPos),
    `BB_SM_ACC` (small callees' accesses by BB_SM key), `paBit`, hooks in $931A (T now in code order) / $C002 /
    jumpTone / the wrap / the skeleton IN.  `passLast.rest` = the pass's waits, `paid` = a cut's charge before its ISR.
    `BB_TAPE_OPS`: reset() seeds the 52 bytes the tape leaves to play (TRAPS #300: build/image.bin is NOT the loaded game;
    $9077 / $9194 / $91DC / $91D0 / $91E4 / $7ED7 were wrong since M7.7; tools/hurry.py now reads build/image_tape.bin,
    `--operands` re-measured into the hurry fixture).
  - Gates: PA1 (fixture), PA2 (given the machine's ISR T: all 2,565 passes of 470..759 at the machine's frame, phase and
    program), PA3 (the 52 bytes), PA4 (free-running: play's first pass 1,036.782 T early, pinned -- the ISRs' own
    contention + the menu's means, M7.114c), PA5 (boundary), PA6 / PA7 (unit: edge reads' places, $C002 live slot,
    waits of a cut / a settle counted once, resumed program, HALT's `blocked`, passD, the corpse's T).
  - Re-aimed (each with an M7.114a note): MP1 / IM3 / EP2 / $931A / SC4 / SM3 / SM4 (K and the calibration identity
    retired), JT7 / LZ8 / JT8 / CD3 / PZ4 (REST gone), CD2 / GS2 (advance via a cut pass OR M7.106's cut), HB20 (the
    fire in the frame after the HALT -- one pass, two frames), PF2 (last waiting frame may hold no write), the census row
    (pinned 12,11,...,12,11 -- two odd frames fit a 12th pass, M7.114c), the tape-value rows (TRAPS #300).  Test helper
    `letGo(g)` (top of bb.test.js) for scenes re-phased by carry; HE2 starts its fire pass AT $9037 (chainResume).
  - Bug found by PA6 and fixed: passSettle took a block prefix's waits off twice.
  - Battery: 5,406 cases (`scratchpad/battery/reaim114.py`: 34 re-aimed, 21 dropped -- the K/PROV/REST constants --, 78
    new + 1; backup `mutate7.m7113.bak`).  `--match M7.114a` 112: 92 killed, 14 survivors + 6 timeouts -> PA6 / PA7 and
    the settle fix; re-run 23: 20 killed, 3 survived -> PA7; last 3: LISTED 3 KILLED 3 SURVIVORS 0.
- **Suites: bb 1,794 / kit 120 / selftest 34.**
- **Real load path** (`scratchpad/world/engplay.js`, `cmp5.py 400`; stext.json masks only to 535 -- frames from 536 show
  the HUD's ROM-font cells, an artifact): identical 407..533; 534 the bubble (M7.114b).  scratchpad/m7114/ has the probes
  (machacc.py, engacc.js <last> <seed>, cmpf.py lo hi, census.py over the 48 states).
- **Next (Claude's order):**
  1. **A FULL battery** (milestone: game.js and bb.test.js changed a lot): the Start-Process line with `--jobs 20`
     (`$p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20' -RedirectStandardOutput build/mutants/run.log
     -RedirectStandardError build/mutants/run.err -WindowStyle Hidden -PassThru`, then watch.ps1 on $p.Id), ~30 min now
     (the suite is ~2.5 min).  Expect BROKEN 3 (B9 x2, M7.69), TIMEOUT 1 (M7.110's guard).
  2. **M7.114b: the dark window** -- $93DC (elemArm, chain index 8) stores ($FEC5) 0 at $93E1 and 1 at $93F9, 62 T later;
     an even ISR in between skips $B62C (frame 534).  With the pass on the clock: when the point falls inside elemArm
     between those stores, the ISR must see ($FEC5) = 0 (a mid-callee split: ctrRead's pattern but for an ISR READ of a
     main-line write -- e.g. elemArm records the window and step() runs the ISR with $FEC5 = 0 if the point is in it).
     Survey first: every main-line store to bytes the ISR reads ($FEC4 / $FEC5 / $B54B / $FD80.. / $FED8..) and its
     offset.  Gate: cmp5 400 identical past 534 on the real load.
  3. M7.114c: the ISRs' own contention ($A3AD's draw, $AA60's $73A6 reads) -- PA4's 1,037 T and the census pin.
  4. Then: the hurry / storm / $94C2 blocks from their callee's entry (calleeAt + passSettle; HB10's synthetic phases
     need the fire pass at $9037 -- try chainResume and find why HB10's capture / escape outcomes moved: the skipped
     pre-block callees feed the ISRs' cost); the census sites not on the program ($7E80's long path -- paMiss --, the
     boss blits, $9AEB's fire updates, $C002's blits); $9E50's tick body after the ISR.
  Agents: no -- the method is known; solo.

## RESTART HERE (2026-10-07r, M7.114 MEASURED -- the frame-534 cause found; nothing in game.js yet; nothing running)

- **What frame 534 is** (scratchpad/world, all gitignored; tools named below).  The differing cells (14..15, 2..3) are a
  BUBBLE in the pool (slot at $FED8: Y at $FEDE) rising 1 px per even ISR ($B62C; $B657 toggles each even pass).  On
  the machine the even ISR taken at boundary 534 found **($FEC5) = 0** and skipped $B62C, so the machine's bubbles (and
  $B657's parity) run one even pass behind the engine's from there on.  Engine and machine RAM agree on every modelled
  byte through 533 (`re<N>.bin` / `rs<N>.bin`, 500..600).
- **Why ($FEC5) was 0:** every main-loop pass calls $93DC (elemArm) at $8D3D; `$93E1` stores 0 and `$93F9` (the pushed
  $93F4) stores 1 **62 T later** -- a dark window once a pass (~1.2% of the frame).  The machine's `$93E1` ran 3 T
  before boundary 534 and the ISR was accepted 29 T in, interrupted PC $93E7 (`scratchpad/world/machgate.py <last>`
  prints every $FEC5 store and acceptance).  The engine runs a pass ATOMICALLY (step(): whole mainLoop() passes, the
  ISR after), so an ISR can never see the window: **TRAPS #90's general case**, here with an ISR gate.
- **Why the engine cannot place that window yet -- its in-play pass clock is not the machine's** (measured, frames
  500..600, `machphase2.py 600` -> mphase2.json, `node engphase2.js` -> ephase2.json, `ph.py lo hi`):
  - ISR T: engine = machine to within tens of T (even 6,979 vs 6,960 -- the 19-T IM2 response counted differently;
    odd engine 30..70 T SHORT = the odd ISR's own contention, `$A3AD`'s screen accesses: the "engine-wide ISR
    contention gap").  Label: machine ISR at frame variable f <-> engine step f+1.
  - Pass T: machine plain passes 4,933 (min) .. 5,000 T; engine 5,053 on the same path.  Per callee
    (`machcalls.py` -> mcalls.json, compared with the engine's passLast.parts) every callee's T EQUALS the machine's
    UNCONTENDED T except the contended ones, which carry BB_PASS_K means: $7E80 39 vs 28..50, $8FE7 37 vs 36..42,
    $9037 94 vs 91..102, $931A 1061 vs 1052..1062, $9961 72 vs 71..77, $C002 907 vs 890..912.
  - **BB_PASS_REST (78 T) is a phantom**: skeleton 479 + the twenty callees' uncontended sums = 4,933 = the machine's
    uncontended plain pass EXACTLY (28+211+48+316+187+36+57+91+22+1067+1052+110+28+71+48+89+44+28+31+890 = 4,454).
    REST is the leftover of the old flat BB_PASS_T mean, nothing the machine runs.
  - Contended accesses per call (`machcalls2.py` -> mcalls2.json, the simulator's contend() hooked; 0 when the call ran
    in the border): $7E80 6 (its own CODE at $7E0E..$7E84 is contended memory), $8FE7 2 ($4000), $9037 2 ($745C..D),
    $931A 5 (attributes $5A04..$5A45), $9961 1 ($4000), $9AEB 8 ($5B07..$5B11, some passes), $C002 8..14
    ($5CE0..$5CFA); all others 0.  Plus the skeleton's IN ($FE) (I/O contention -- not yet checked).
  - Consequence: engine 12 / 9 passes per frame where the machine has 13 / 8 at the same frames, phases unrelated --
    the 62-T window cannot be placed from the engine's clock until the pass is exact on the frame clock.
- **Suites unchanged: bb 1,787 / kit 120 / selftest 34.  Full battery after M7.113 CLEAN (below).  Nothing running.**
- **Next (Claude's order) -- M7.114 is now "the in-play pass on the frame clock", in this order, solo:**
  1. **M7.114a: the pass's T exact given the ISRs' T.**  Drop BB_PASS_REST (re-pin what moves: BT3 drift etc.) and the
     K means for in-play passes; instead each contended callee logs its contended accesses as plain-T offsets
     (code fetches of $7E80 static per instruction; data reads by address) and the skeleton's IN, and the pass is
     replayed on the frame clock from its phase with the engine's DELAYS (lzSeg's way, M7.110..113).  Measure first:
     a tool (tools/passclock.py) that records, on the real-load run AND passcost's states, per callee per path the
     access offsets, and asserts the replay gives every machine pass's contended T.  Gate: the engine's per-frame pass
     count and each pass's start phase = the machine's, given the machine's ISR T (as R1Tc does).
  2. **M7.114b: the dark window.**  With the pass on the clock, an ISR whose point falls between $93E1's end and
     $93F9's end (elemArm's place in the pass: skeleton to $8D3D's CALL + the callees before it + $93DC's head) runs
     with ($FEC5) = 0 (GATE_CLOSED_EVEN, 452 T): the pass must be split at the interrupt point there (TRAPS #90 rule a).
     Check whether any other byte an ISR reads is written mid-pass (survey: every store to $FEC4/$FEC5/$B54B/$FD80../
     $FED8.. by the main line, which pass offset).  Gate: frame 534 on the real load path (cmp5.py).
  3. **M7.114c: the odd ISR's own contention** ($A3AD's screen accesses, $AA60's $73A6 reads) -- without it the phase
     drifts 30..70 T per odd ISR and frame 534's window (62 T) will not hold over 60 frames free-running.
  Then the other HALTs on the 4-T grid; DEPARTS 'bootFromCapture'.
  Agents: no -- the method is known and the measurements are cheap (each machine probe ~2..4 min, run detached).

## RESTART HERE (2026-10-07q, M7.113 in; full battery after it CLEAN; nothing running)

- **`c97b956` M7.113 = the round-1 tail and banner from the title, exact.**  Read docs/TIMING.md "M7.113", TRAPS #299.
  - Measured: `tools/r1tail.py` (new) -> `build/r1tail_fixture.json` (port.json `r1tail`), ~1 min, `verify` MATCH.
    $9888..$8D0C is ONE plain access program in every run (81,852 accesses); replayed with each ISR's T it is the
    machine's main line exactly.  The engine's isrCost = the machine's UNCONTENDED ISR T on every ISR there; the residue
    free-running is the ISRs' own contention ($8D0C 813..1,792 T early, same frame -- R1Td pins it).  The HALT at $9887
    ends on its 4-T grid ((phase) mod 4 T late); the harness's `_fast_halt` lands on the boundary (TRAPS #299).
  - Engine: `BB_R1T` (LZ-packed program), `bbUnlz`, `bbR1tProg`, `r1tBegin` / `r1tStep` / `r1tHold`, `roundBanner_hp`;
    `lzSeg(s, budget, L)` takes its block; roundSeq phase 'r1t'; `r1Seq` set by roundStart when round 1's build ran on
    the replay.  'halt' lands on the 4-T grid on EVERY round.  Gates R1Ta..R1Te; BT3/BT4 force the means path
    (`r1Seq = false`), BT3 drift re-pinned 602 / 1424; RA-g HALT gate on the grid.
  - Battery 5,348 (`scratchpad/battery/add_m7113.py` 26 new, `reaim113.py` 17 re-aimed + 2 new; backup
    `mutate7.m7112.bak`).  --affected 148: 3 survivors -> 2 gates added (roundStarts in R1Tc; $8D0C with a write held
    in R1Te), the arm re-aim corrected ('M7.113b'); `--match M7.113` 45/45 killed.
- **Suites: bb 1,787 / kit 120 / selftest 34.**
- **Full battery after M7.112 was CLEAN** (5320/5316, BROKEN 3, TIMEOUT 1 expected; commit e812bd1).
- **Full battery after M7.113: CLEAN.**  19:43..19:57, `LISTED 5348  KILLED 5344  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0 -- 14.5 min on 20 workers` (BROKEN = B9 x2, M7.69; TIMEOUT = M7.110's guard case,
  EXPECTED).  compare_mutants: 5,078 agree, 0 gained, 1 'lost' = the same STALE M7.53 H-a label as before.  Nothing
  to fix.  NOTHING RUNNING.
- **Real load path after M7.113** (`scratchpad/world/`): `node scratchpad/world/engplay.js` (engine e<N>.bin),
  `python scratchpad/world/machisr.py 1045` (machine s<N>.bin at each ISR's END, HALT stepped, keys changed at the
  ISR's end = the engine's convention; ~3 min), then `cd scratchpad/world && python cmp5.py 400` (e<N> vs s<N>, ROM
  font cells masked).  RESULT: identical 407..533 (build, tail, banner, play); differs 534..887 (first cells (14..15,
  2..3)), identical 888..921, differs from 922.  400..406 = the title starfield (declared).  The OLD probes
  (machdump m<N> before the ISR, keys at the boundary) do NOT line up with the engine -- don't use cmp.py/cmp2/cmp3.
- **Next (Claude's order):**
  1. **M7.114 = the first in-play divergence on the real load path, frame 534** (cells (14..15, 2..3)).  Measure first:
     what object it is (machine RAM at 533/534 vs the engine's -- extend machisr.py to dump $FD80.. entity table and
     $FED8.. pool at ISR ends), then the routine responsible.  Keys in machplay_s.PLAY around 496..534: SPACE 496..499,
     P 510..539.  Solo.
  2. Then TRAPS #90's general case; the other HALTs ($7EC2, game over) on the 4-T grid (fixtures were made with
     _fast_halt -- re-measure before changing); the engine-wide ISR contention gap.

## RESTART HERE (2026-10-07p, M7.112 in; full battery after it CLEAN; M7.113 under way -- see 07q above if present)

- **`0514331` M7.112 = the round-1 build from the title, exact.**  Read docs/TIMING.md "M7.112", TRAPS #298.
  - Measured: `tools/r1build.py` (new) -> `build/r1build_fixture.json` (port.json `r1build`), ~1 min,
    `python tools/r1build.py verify` MATCH.  titleexit's 16 runs on from $97F8 + hi1 / hi2 (high score poked at $9765).
    The plain $97F8..$9887 is ONE access program per player count (54,150 / 54,296; 49,803 = the repaint's LDIRs, the
    same as extModel('repaint')'s); only the two awards' T move with the world (no contended access inside them).
    Replaying it from $97F8's phase with the ISRs' 488 / 493 gives the machine's main line EXACTLY on all 18 (the tool
    asserts it).  On the title path both gates are shut before $97F8, so M7.85's entry window is gate-closed.
  - Engine: `BB_R1` (AT, REP, X, END_N, DATA = the non-repaint accesses as k + LEB128), `bbR1Prog` / `bbR1Map` /
    `bbR1At`; `buildClockFor` -> `r1Clock()` inside step() (round 1 only), stamps through `r1Stamp`, replay made again
    at $7FFC (`r1Final`, from hudRows' `hudAw`), roundStart spends `R1.M.endMain`.  `buildLog` / S.log records display
    stores for gates; `r1Last` the diagnostic.  Outside step(): the old means (DECLARED).
  - Gates R1a / R1b / R1c / R1d all pass.  R1c's world = TX2's after `g.gameReset()` (a fresh BB_Game has $8609 = 1
    and built ROUND TWO -- TRAPS #298); mask = the HUD text's 456 + the round number's 7 bytes (ROM glyphs, the latter
    via the shadow and the repaint); last row = after the ISR that ends $9887's HALT (step() ends with it).
  - Battery 5,320 (`scratchpad/battery/add_m7112.py`: 6 re-aimed, 24 new; backup `mutate7.m7111.bak`).  `--affected` 31:
    29 killed, 2 survived -> 'the replay's ISR before the access' EQUIVALENT (accesses within ~23 T of a boundary are in
    the top border: no contention) DROPPED; 'the late count against the first end' killed after R1c checks the end
    r1Final sets (`--match M7.112` 23/23).  NOTE: `--match` / `--affected` must also go through PowerShell Start-Process
    (Git Bash -> BrokenProcessPool, even foreground).
- **Suites: bb 1,782 / kit 120 / selftest 34.**
- **Full battery after M7.112: CLEAN.**  18:40..18:54, `LISTED 5320  KILLED 5316  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 1
  BROKEN 3  CRASHES 0  MISSES 0 -- 14.2 min on 20 workers` (BROKEN = B9 x2, M7.69; TIMEOUT = M7.110's guard case,
  EXPECTED, a kill).  compare_mutants: 5,078 agree, 0 gained, 1 'lost' = the same STALE M7.53 H-a label as after M7.111
  (its re-aimed case is killed).  Nothing to fix.
- **Real load path after M7.112** (`scratchpad/world/engplay.js` then `cd scratchpad/world && python cmp.py 400`):
  the build's frames 416..419 now MATCH the machine (07n had 416 / 417 / 418 off).  Remaining: 420 and 421..427
  are machdump's sampling convention (m<N> is before boundary N's ISR, e<N> after it -- compare e(N) with m(N+1));
  in THAT comparison 420..468 agree except the banner's row-12 cells at 423 and 470, and player 1 differs from 469.
  So the round tail ($9888..$98B4, BB_ROUND_TAIL_T a mean) and/or the banner ($98B5.., BB_BANNER_AT fitted) still
  put play a frame off.
- **Next (Claude's order):**
  1. The full battery's result (above).
  2. **M7.113 = the round-1 tail and banner from the title, exact** -- the same method: extend r1build (or a new tool)
     from $9888 (after the HALT's ISR) to $8D0C: the plain program(s) of $9888..$98B4 and the banner, check whether one
     program + replay with the ISR walls (gate-OPEN now: the settle window -- take the machine's walls first, then see
     whether the engine's isrCost matches) gives the machine's end; then the engine on the frame clock; gate with the
     page drive (engplay shape) showing player 1's first move on the machine's frame; then DEPARTS 'bootFromCapture'
     re-worded.  Solo.
  3. Then TRAPS #90's general case.

## RESTART HERE (2026-10-07o, M7.111 in, full battery CLEAN; M7.112 measuring -- nothing running)

- **`9454b7c` M7.111 = the title's exit on the frame clock** (step 1+2a of 07n's M7.111 list; the round-1 build is
  split off as M7.112).  Read docs/TIMING.md "M7.111", TRAPS #297.
  - Measured: `tools/titleexit.py` (new) -> `build/titleexit_fixture.json` (port.json `titleexit`), ~15 s,
    `python tools/titleexit.py verify` MATCH.  World: painttime's $970F drive + the machine's paint to $9765 (bitmap
    stored with the strings' 1,328 cells zeroed; the cells' addresses in `mask_b64`).  Programs (plain runs): arm1
    $979E 12 / 122 T, arm2 $9790 12 / 130, pass $97B7..$97BF 6,921 / 145,216 T / 62,196 accesses, leave
    $97C2..$8D09's CALL 20 / 330 T.  16 runs (key, press boundary, held, phase), 1..5 passes, every boundary to $97F8.
  - Engine: `BB_TEXIT` (ARM / PASS / AGAIN / OUT / LEAVE; exported BB_Game.TEXIT), `bbClsProg(call, fx)` shared with the
    paint; `texit` cursor put up at the arm, the 'release' front runs it (texitFx: 'rp', 'c0', 'c', 'cE', 'k'); at OUT's
    end titleLeave().  PASS_T / ARM_T / frontDebt GONE; EQUIVALENT + 'exitStoresAtOnce'; releasePass() a gate driver
    (UNCALLED 19, UNREACHABLE 15).
  - Gates TX1 / TX2 / TX3 all pass; M7.42 (h) re-worded.
  - Battery 5,297 cases (`scratchpad/battery/reaim111.py`: 6 re-aimed, 17 new; backup `mutate7.m7110.bak`;
    `scratchpad/battery/deadcheck.py` lists dead anchors in 1 s).  `--match M7.111` 23/23; `--affected` 197: 196 killed,
    1 survivor (M7.53 H-a frontDebt case -- equivalent once the field went; re-aimed to spend(), killed), 1 MISS (M7.11
    wind read, as at M7.110; whole suite kills it).
- **Suites: bb 1,778 / kit 120 / selftest 34.**
- **Full battery after M7.111: CLEAN.**  16:48..17:03, `LISTED 5297  KILLED 5293  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 1  BROKEN 3  CRASHES 0  MISSES 0 -- 14.7 min on 20 workers` (BROKEN = B9 x2, M7.69; TIMEOUT = M7.110's
  guard case, EXPECTED, a kill).  compare_mutants: 5,078 agree, 0 gained, 1 'lost' = a STALE label in last.json (the
  M7.53 H-a case's pre-M7.111 label, SURVIVED in the --affected run; its re-aimed case '(re-aimed M7.111)' is KILLED
  in this run and the old label is not listed).  Nothing to fix.  Nothing running.
- **M7.112 measurement STARTED (scratchpad/r1build/, gitignored; nothing in game.js yet):**
  - `probe.py [n]` (titleexit's RUNS -> $8D0C; marks, ISRs, PC-stream CRC -> probe.json; ~1 min a run).  On 3 runs
    (1_3_1_n p97F8 48,740; 2_3_1_n 48,772; 1_2_3_n 20,474 = engplay's drive): the MAIN-LINE T (ISRs taken out) is
      $97F8..$7F30  426,897 / 426,929 / 428,470   (engine BB_BUILD_AT[1] 427,569: a mean, inside the spread)
      $7F30..$7FC0  182,891 / 183,051 / 184,501
      $7FC0..$9887   71,487 /  84,479 /  69,090   (2P's HUD + lives longer)
      $97F8..$9887  681,275 / 694,459 / 682,061   (engine BB_ROUND_BUILD_T[0][1] 678,792 1P / [1][1] 693,616 2P:
                                                  1P SHORT 2.5..3.3K T, 2P 0.8K -- the frame-early player)
    ISRs in the build: 10, all gate-closed 488/493 (6 before $7F30, 3 to $7FC0, 1 after).  $9887 is the HALT; then
    gate-open ISRs (13.5K..26K T) and $98B5 (the banner) at +14 frames, $8D0C at +61 (1P) / +63 (2P) frames.
    The PC stream's length differs run to run only by the HALT spins (not yet split by segment).
  - `stream.py i ...` (TE.stream per segment: count / T / contended accesses / CRC) was STARTED as a Claude background
    shell at 16:5x on runs 0 2 1 4 and had printed nothing after 10 min (RC.sim_of's per-access log over ~680K T is
    slow, and the battery shared the CPU) -- it dies with the session; re-run it DETACHED (Start-Process, log to
    scratchpad/r1build/stream.log) with ONE run first to time it.
  - Engine now (engplay.js + cmp.py 400 after M7.111, built page): unchanged from 07n -- 416/417 build draws, 418 the
    row-12 band a frame apart, 420 player 1 a frame early, (2,15)/(2,16) on alternate frames 421..427, and from 461
    player 1 moves ONE FRAME EARLY for the rest.  hand2.js: the engine's titleLeave at 409:19,981 (machine $97F8
    409:20,474; the 493 is an even ISR wall -- check against TX2 before reading anything into it).
- **Next (Claude's order):**
  1. **M7.112 = the round-1 build from the title, exact.**  Decide from stream.py: if the $97F8..$9887 stream is the
     SAME instructions in every run (only contention differs) and its contended accesses are few, ship it as a
     program (M7.110's way: [T, contended offsets] generated, replayed on the frame clock from the $97F8 phase) and
     derive BB_BUILD_AT[1] / R1_REPAINT / R1_HUD / the round-1 end from it per run (gate-closed ISRs 488/493 on the
     walls; M7.85's entry window kept).  Then a tool `tools/r1build.py` (port.json key + fixture: the marks and the
     per-boundary display CRC with mtext's mask, titleexit's 16 runs to $8D0C), gates, and the M7.64 page drive with
     skipProbe off showing player 1's first move on the machine's frame.  Then DEPARTS 'bootFromCapture' re-worded.
  2. Then TRAPS #90's general case (other chain readers of the timer after the interrupt point).
  Solo -- the method is known (M7.109..M7.111).


## RESTART HERE (2026-10-07n, the post-cold-start world MEASURED; nothing running, nothing uncommitted but next.md)

- **Full battery after M7.110: clean** (`2de2ee3`).  15:45..16:01, `LISTED 5280  KILLED 5276  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 1  BROKEN 3  CRASHES 0  MISSES 0 -- 16.0 min on 20 workers`; the TIMEOUT is M7.110's guard case (EXPECTED,
  a kill -- see 07l); compare_mutants 5,079 agree, 0 lost, 0 gained.  Suites unchanged: bb 1,775 / kit 120 / selftest 34.
- **Item 4's last part (bootFromCapture) MEASURED -- probes in `scratchpad/world/` (gitignored; tape-derived .bin there,
  never commit):**
  - `machplay.py 700` -> machplay.json: loadpath's drive (kbd_sinclair) + PLAY (310 idle frames, '1' x3, then P / Q / O /
    SPACE moves) to 1,045 boundaries; `engplay.js` drives the BUILT page with the same keys and **skipProbe = false**
    (frames line up with the machine only then) and diffs.  `machdump.py <last> <frames,...>` saves m<N>.bin displays +
    mtext.json (cells whose machine bitmap is a ROM glyph -- the no-ROM text, masked; coords only); `cmp.py [from]` diffs
    them against engplay's e<N>.bin.  `marks.py <last>`: the machine's (frame, T) at $97B7 / $97C0 / $97C7 / $8D09 / $97F8 /
    $7F30 / $7FC0 / $98B5; `hand2.js`: the engine's method entries (tframe).
  - RESULT: load + hand-over exact; $970F at phase 9,678 machine / 9,690 engine; the frame counters agree (the engine
    runs boundary N+1's ISR at the end of step N -- a sampling convention, not a bug).  The title's attributes differ
    (the starfield's R, known).  **Frames 407..415 identical; play agrees except TIMING:** the build's draw a few
    hundred T apart inside frames 416/417, a white band (row 12 attrs) one frame apart at 418, player 1 drawn a frame
    EARLY at 420, the (2,15)/(2,16) cells on alternate frames 421..427, and from 461 player 1 moves ONE FRAME EARLY for
    the rest of the run (same path, shifted).  No non-timing world difference seen to frame 1,045.  The capture world
    (reset()'s render asset) is invisible on the load path: the CLS and the build overwrite it.
  - WHERE THE TIME GOES (machine vs engine, frame:T): first release pass $97B7 404:824 vs 404:356 (-468); second
    406:48,576 vs 406:46,192 (-2,384: PASS_T 184,631 is a contended MEAN, interrupts off); $97F8 409:20,474 vs
    409:22,628 (+2,154; $97C7..$8D09 ~293 T is uncharged).  The machine then: $7F30 415:32,559, $7FC0 (HUD) 418:8,865,
    banner $98B5 423:23,219.  The engine reaches $97F8 LATE yet shows the player a frame EARLY, so the round-1 build
    from the title (BB_BUILD_AT[1] 427,569 mean / R1_REPAINT / R1_HUD / BB_ROUND_BUILD_T[0][1] 678,792) is short too.
  - Known on the way (already declared, BB_SPINE comment): a key held ~23 frames of the black screen sends a 48K down
    the 128K leg (the machine then CALLs $D167) -- my first script pressed '1' inside the probe and hit the guard.
- **Next: M7.111 = THE TITLE'S EXIT IN TIME** (the item 4 work's last piece; the M7.109/M7.110 method).  Solo.
  1. A tool `tools/titleexit.py` (port.json key + fixture): from the ring's real $9765 state (ringtime's world) with
     a '1' press at natural + forced phases, to K boundaries past the first main-loop pass of round 1: the
     release passes' instruction program (the $97EB CLS with interrupts ON -- BB_SPINE.CLS_PH is the hand-over CLS by
     phase, a precedent), the arm ($9790/$979E..$97B7), $97C2..$8D09, and per boundary the display CRC (text masked as
     mtext does), the frame counters, the marks above.
  2. Engine: the release passes as a program on the frame clock (PASS_T / ARM_T GONE, as M7.109 removed COST),
     $97C7..$8D09 charged; then re-measure the round-1 build from the title against the machine on THIS path and fix
     what is short (BB_BUILD_AT[1] and the R1 stamps were measured as means / from captures).
  3. Gates: the new fixture exact; the page drive of M7.64 extended into play with skipProbe off (engplay.js's shape),
     player 1's first move on the machine's frame.  Then DEPARTS 'bootFromCapture' can be re-worded (the world is
     the capture's only where nothing can see it) and removed if a gate shows that.
  4. Then TRAPS #90's general case (other chain readers of the timer after the interrupt point).


## RESTART HERE (2026-10-07l, M7.110 in -- the title's paint in time; nothing running)

- **M7.110 = item 4, second half: the paint ($970F..$9765) is its instructions on the frame clock.**  Read docs/TIMING.md
  "M7.110", TRAPS #296.
  - Measured: `tools/painttime.py` (new) -> `build/painttime_fixture.json` (port.json `painttime`), ~8 s,
    `python tools/painttime.py verify`.  The real load to its first $970F (phase 9,678); the plain program (65,156
    instructions, 589,318 T, 65,738 accesses, CRC of PC:T:k); natural + 18 forced, every boundary to 4 past $9765:
    instructions done, ring iterations, attr CRC, bitmap CRC with the strings' 1,328 cells zeroed (ROM glyphs), PRNG;
    R at $9712, arrival [k, phase], ISR T; each ISR's R step asserted (52 odd / 53 even).
  - Engine: `BB_TPAINT` (ISR_R, END) + `bbTitlePaintProg(ram)` (exported BB_Game.TPAINT / titlePaintProg);
    `titleEnter(phase)` puts up `tpaint` (tpaintNew), frontFrame runs it (front stays 'title'), `tpaintFx` the effects,
    `tpaintText` records the strings' writes once (Proxy over a copy), `isr()` stalls the walk while a paint is up.
    `starDot` GONE (`starPos`); `titlePaint` / `starfield` = the program's effects at once (gate drivers, back in both
    censuses: UNCALLED 18, UNREACHABLE 14).  BB_TITLE.PAINT_T and DEPARTS paintInstant GONE.  A cursor left up past
    $9765 THROWS (it hung frontFrame: the battery's TIMEOUT).
  - Gates PT1 (program), PT2 (19 runs / 249 boundaries exact), PT3 (instant spelling, three throws); M7.42 / M7.41
    rows re-worded for the paint in time (page drive's `at.painting`).
  - Battery 5,280 cases (30 re-aimed by `scratchpad/paint/reaim110.py`, backup `scratchpad/battery/mutate7.m7109.bak`;
    20 new, 1 equivalent dropped -- the CLS seed 0 vs L, HL fixed at $4000).  `--match M7.110` 48/49 (that one);
    `--affected` 219: 218 killed, 0 survivors, 1 TIMEOUT (bannerDouble's IX -> the hang, fixed), 1 MISS (M7.11's
    wind read: its killer, the census row, was edited); `--match` of the three (m110b.log): both KILLED, and the
    guard's own case is an EXPECTED TIMEOUT (without the guard step() spins -- a hang no test can bound; a kill).
- **Suites: bb 1,775 / kit 120 / selftest 34.**
- **Next (Claude's order):**
  1. a FULL battery (Start-Process line, `--jobs 20`, watch.ps1 + cron poll) -- a milestone, ~13 min;
  2. the post-cold-start world (bootFromCapture), then TRAPS #90's general case (other chain readers of the timer
     after the interrupt point).  Solo.

## (2026-10-07k, full battery after M7.109 CLEAN)

- **Full battery after M7.109: clean.**  14:13..14:26, `LISTED 5261  KILLED 5258  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 0  BROKEN 3  CRASHES 0  MISSES 0 -- 12.6 min on 20 workers` (BROKEN = the known B9 x2, M7.69);
  compare_mutants: 5,079 agree, 0 kills lost, 0 gained, 186 only in the new run.
- **Next: item 4, second half -- THE PAINT IN TIME** (step 2 of 07j's list below).  Probes already run
  (`scratchpad/paint/probe.py`, `rprobe.py`, `dump.py` -> `stream.json`): from loadpath kbd_sinclair's first $970F
  (phase 9,678) the paint's main line is 65,156 instructions / 65,738 contended accesses, IDENTICAL at all 17 phases,
  and isrcarry's replay with the ISRs' walls (488 odd / 493 even, uncontended, gates closed) is EXACT on all 17 (every
  acceptance, the end, the delays).  R: given R at $9712 (first $9715 read = R9712 + 3), each ISR adds 52 (odd) / 53
  (even) -- all 2,048 R reads exact on 5 phases.  Segments: CLS 145,190 T, starfield 1,024 x 49 instructions
  (2 contended stores, $FEB0 k4 / $FEBA k7), text + credit ~63K T (straight-line: $801D/$802E/$8044/$804F/$8058/
  $8061, $A090, $994F/$995A; ROM glyphs uncontended).  Plan: a generated program [T, ks, fx, PC] run by frontFrame
  ('paint' before 'title', the ring's way), the starfield's effects per instruction, the text's writes recorded once
  and landed at their stores, an R stall per ISR inside the paint; tools/painttime.py fixture + gates.  Solo.

## RESTART HERE (2026-10-07j, M7.109 in -- the title's ring on the frame clock; FULL BATTERY RUNNING)

- **`4a44eee` M7.109 = item 4, first half: the sparkle ring ($9768..$978F) timed an instruction at a time.**  Read
  docs/TIMING.md "M7.109", TRAPS #295.
  - Measured: `tools/ringtime.py` (new) -> `build/ringtime_fixture.json` (port.json `ringtime`).  The real load
    (loadpath kbd_sinclair) to its first $9765 (phase 22,702; both load scripts arrive with the SAME phase and PRNG
    $2CCD -- only R differs, so the title's attribute difference between them is the starfield's R).  Natural + 21
    forced phases + 6 presses, 30 boundaries each.  ~10 s.  `python tools/ringtime.py verify` MATCH.
  - Engine: `BB_RING` (six programs, [T, contended offsets, effect, PC]; exported `BB_Game.RING`); frontFrame runs
    them on the frame clock, `ringCur` carries a cut iteration past the ISR, `titleRingStep(hold)` holds the PRNG's
    store (`ringP`, $FE91) and the write (`ringW`, $9780); key test at the IN; arm tails 34/40 T; `titleArmPh`.
    BB_TITLE.COST / WRAP_T and `titleIter` REMOVED.
  - Gates RT1 (22 runs / 660 boundaries exact), RT2 (programs vs path_T), RT3 (6 arms); M7.42 (f) re-worded.
  - Battery 5,261 (9 M7.42 cases re-aimed by `scratchpad/title/reaim109.py`, backup
    `scratchpad/battery/mutate7.m7108.bak`; 17 new).  `--match` 69/69, `--affected` 143/143, compare 5,079 agree.
- **Suites: bb 1,772 / kit 120 / selftest 34.**
- **RUNNING: FULL battery** launched 14:13 via Start-Process (`--jobs 20`): **PID 42452**, watcher **45192**
  (watch.ps1).  Log `build/mutants/run.log`, done file `build/mutants/run.log.done`, result `build/mutants/summary.txt`.
  Expect LISTED 5,261, BROKEN 3 (B9 x2, M7.69), ~13 min.  Don't edit game.js / bb.test.js until it ends.  If it died,
  delete `scratch/mutants/.running` by hand.  Then `python scratchpad/compare_mutants.py`.
- **Next (Claude's order):**
  1. read the full battery's result; fix any survivor first; record it in next.md (commit);
  2. item 4, second half -- THE PAINT IN TIME ($970F..$9764, interrupts on, ~640K T over 9 frames): today
     PAINT_T is a debt charged at once (paintInstant), so the ring starts ~16 iterations off the machine's phase
     (machine 250 in the first ring frame, port 266).  Measured on the way: the paint's main-line T depends on the
     $970F phase (loadpath's 637,604 vs title_wait's 634,920).  The paint's access program is data-independent (the
     CLS LDIR, 1,024 dots each with 2 contended stores, the double-height text -- BB_EXT_W DOUBLE has a program --,
     the credit line), so it can be timed like a lazy block; its writes held to their frames make the 9 paint frames
     comparable, and the 5..6 ISRs inside the starfield move R (steps 103/104/106, M7.41) -- with the ISRs placed,
     the starfield is exact GIVEN R at $9712, and M7.64(b)'s title rows can be compared with the machine's R passed in;
  3. then the post-cold-start world (bootFromCapture), then TRAPS #90's general case.
  Solo -- no unknown machine behaviour needing agents (the paint is the known access-program method).

## (2026-10-07i, full battery after M7.108 CLEAN -- superseded by 07j)

- **Full battery after M7.108: clean.**  13:22..13:35, `LISTED 5244  KILLED 5241  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 0  BROKEN 3  CRASHES 0  MISSES 0 -- 12.5 min on 20 workers` (BROKEN = the known B9 x2, M7.69);
  compare_mutants: 5,079 agree, 0 kills lost, 0 gained, 169 only in the new run.  (watch.ps1's "summary_line False"
  is only its 6-line tail missing the LISTED line; summary.txt has it.)
- **Next (Claude's order):** 1. item 4 (title attributes frame for frame; the tape's post-cold-start world);
  2. other chain readers of the timer after the interrupt point (TRAPS #90's general case).  All solo.

## (2026-10-07h, FULL BATTERY RUNNING after M7.108 -- superseded by 07i above)

- Launched 13:22 via the Start-Process line (`--jobs 20`): **PID 43556**, watcher **11032**
  (`scratchpad/battery/watch.ps1`).  Log `build/mutants/run.log`, done file `build/mutants/run.log.done`, result line
  `build/mutants/summary.txt`.  Expect ~5,244 listed, ~13 min, the known BROKEN 3 (B9 x2, M7.69).  Don't edit
  game.js / bb.test.js until it ends.
- **Next session:** read summary.txt (or run.log.done); if it died, delete `scratch/mutants/.running` by hand.  Then
  `python scratchpad/compare_mutants.py` (expect 5,079 agree, 0 kills lost).  Fix any survivor/miss first.  Then
  item 4 (title attributes frame for frame), then TRAPS #90's general case.  All solo.

## RESTART HERE (2026-10-07g, M7.108 in -- the join timed a frame at a time; nothing running)

- **`9f27304` M7.108 = NEXT item 2, the join tail's writes in time.**  Read docs/TIMING.md "M7.108", TRAPS #293 / #294.
  - Measured: `tools/isrcarry.py` 'join' sources (JOIN_SRC: round1_48 '2', r20_48 '2', round1_48 P1-out '1'; own +
    16 forced; each row's source stores `seed` + `key`).  Replay exact 51/51; fixture 225 runs / 15 sources / 4,977
    ISRs, old sources byte-identical (backup `scratchpad/join/isrcarry_fixture.m7107.json`).  `measure --jobs 6` 33 s.
  - Engine: BB_EXT_BLOCKS.join (lazy), `joinBlock` / `joinPos` (BB_JOIN.AT 171) / `joinRt` / `hudAward` /
    `joinModel`, `joinStores` split out of joinCommit; `passPre` in passCharge; chainWalk 'join' at $8D34;
    BB_Game.JOIN / PASS_REST exported.  Outside step() M7.99b's joinW path stays.
  - Gates: LZ8, LZ4 (15 programs), JT6, JT4 (re-aimed), JT7, JT8; IC counts updated.
  - DECLARED: the awards' RLD intermediates not written (each byte ends as it began; no ISR reads a score).
  - Battery 5,244 cases (+33, 16 re-aimed via `scratchpad/join/reaim108.py`, backup `mutate7.m7107.bak`; anchors 0
    bad).  match 31/33 -> JT8 -> `--affected` 226/226 -> match 33/33; compare_mutants 5,079 agree, 0 lost.
- **Suites: bb 1,769 / kit 120 / selftest 34.**
- **TRAP to remember (#294):** the working copy is CRLF (`core.autocrlf` true) and the battery hashes blocks by source
  text.  The Edit tool / some writes leave `test/bb.test.js` or `web/game.js` LF -- convert back to CRLF before any
  battery (`python -c` replace `
` -> `

`), or `--affected` re-selects ~everything and crawls.
- **Next (Claude's order):**
  1. a FULL battery (Start-Process line, `--jobs 20`, watch.ps1 + cron poll): the suite grew by 4 checks and 33 cases;
     runner / rig / build unchanged, so not strictly required -- do it at this milestone anyway (~13 min);
  2. item 4 (title attributes frame for frame; the tape's post-cold-start world);
  3. possible follow-on: other chain readers of the timer after the interrupt point (TRAPS #90's general case).
  All solo.

## RESTART HERE (2026-10-07e, M7.107 in -- the pause's spin on the frame clock; nothing running)

- **Full battery after M7.106: clean.**  10:22, LISTED 5,181 KILLED 5,178, 0 survivors / misses / crashes, BROKEN 3
  (the known B9 x2, M7.69), 12.5 min; compare_mutants 5,079 agree, 0 kills lost.
- **M7.107 = NEXT item 1, the pause's spin polls.**  Read docs/TIMING.md "M7.107" and TRAPS #292.
  - Measured: NEW `tools/pausespin.py` -> `build/pausespin_fixture.json` (registered in port.json; verify MATCH,
    ~15 s, `--jobs 18`).  249 runs:
    - 108 natural cuts on 6 worlds x 6 arm phases x 0 / 1 / 3 paused frames;
    - 69 SYM+CAPS held together, 33 of them FORCED 100..210 T before a boundary;
    - 72 FORCED cuts with `$8FE7` moved 40..110 T before a boundary.

    The tool asserts every poll (621,676) against the model: a poll is 34 T, its IN's I/O cycle 8 T into it; the
    release is the first poll whose IN starts at or after the boundary; `$8D2B` comes 88 T after that IN, plus its
    delays.  The arm is exact; the gate's IN has A = `$7F`, so its I/O is C:1, C:3 (TRAPS #292).  Two edges:
    - `$8FE7` at boundary - 85 puts the DI on the boundary (ISR taken first); at - 86 the interrupt is lost;
    - the DI window `[DI+1, $8D2B]`: the RET ending 22 T in is taken, 32 T in is lost.
  - Engine:
    - `BB_PAUSE_SPIN` (ARM / POLL / IN / IO / REL_OUT / RES / HEAD 120), exported as `BB_Game.PAUSE_SPIN`, plus
      `BB_Game.ULA_DELAY` and `BB_Game.EXT_INT_T`.
    - `pausePos` (cdPos's rule) and `passCharge('paused')`: the arming pass ends at `$8FE7`.
    - `spinStep(kb, budget)` returns 'isr' (ISR before the DI), 'held' (`spinHeld`: no pass, no interrupt, next
      frame's isrCost 0) or 'released' (OUT logged, `tframe` = `$8D2B`, DI window pushed only if it covers the point).
    - The resumed pass is charged 479 - HEAD + its callees (`pauseResumed`).
    - Outside step() the old untimed path stays (`paused && !spin`).
    - Counters: spinPolls / spinIsrs / spinLost / spinDi.
  - Gates:
    - **PZ1**: the fixture.
    - **PZ2**: all 249 runs replayed through spinStep: DI, both OUTs, every poll, `$8D2B`, ISR-before-DI (24),
      interrupt lost (6) -- exact.
    - **PZ3**: through step(): arm charge = `$8FE7`'s place; 3 held frames with the timer standing; isrCost 0;
      resume at 119 T; charged 479 - 120 + callees.
    - **PZ4**: the place term by term, with the machine's 86 + two CALLs, and the wrap; the poll edge constructed;
      a FORCED arm 40 T before the point runs the ISR first.
    - **SFX11**: its two edges at their frame-clock T.
  - DECLARED: `$8FE7`'s place is the port's pass clock (78-T rest put before it), as the countdown's is.
  - Battery cases: +30 M7.107 (+2 for SFX11b's timed release); 3 re-aimed; 2 equivalent dropped. Scripts:
    `scratchpad/distraddle/reaim107.py`, backup `mutate7.m7106.bak`; anchors.py 0 bad.
  - `--match "M7.107:"` 26/30.  Four survivors:
    - HEAD 121 (PZ4 now pins the place to the machine's 86);
    - an IN AT the point (PZ4's constructed edge row added);
    - two equivalent mutants (step()'s 'isr' break, which the while condition already covers; the window opening
      at the DI, since `di + 1 <= budget` always holds), both dropped.
- **Batteries:**
  - `--affected` 1 (a107.log): 117/122, five old SFX pause cases SURVIVED. Their code (the untimed path, armed
    outside step()) was no longer reached by any row. SFX11b now drives it.
  - Two cases were added for the timed release edge.
  - `--affected` 2 (a107b.log): LISTED 120 KILLED 120.
  - `--affected` does NOT re-select an old survivor whose anchor is unchanged, so the four remaining SFX cases were
    run with `--match` (m107c.log): LISTED 4 KILLED 4.
  - compare_mutants: 5,079 agree, 0 kills lost.
- **Suites: bb 1,765 / kit 120.  Battery 5,211 cases.**  M7.107 COMMITTED (see git log).
- **Next (Claude's order):**
  1. a FULL battery: the suite grew, and runner / rig / build are unchanged. Use the Start-Process line, then
     watch.ps1 and a cron poll;
  2. the join tail's writes in time (M7.99b's declared atomic-at-the-call writes; reuse M7.106's cut machinery);
  3. item 4 (title attributes frame for frame; the tape's post-cold-start world).

  All solo.

## RESTART HERE (2026-10-07d, FULL BATTERY RUNNING after M7.106 -- no code change since 028d4eb)

- **The owner picked "full battery first".**  Launched 10:09 via the Start-Process line (`--jobs 20`): **PID 3224**,
  watcher **22756** (`scratchpad/battery/watch.ps1`).  Log `build/mutants/run.log`, done file
  `build/mutants/run.log.done`, result line `build/mutants/summary.txt`.  Expect ~5,181 listed, ~13 min, the known
  BROKEN 3 (B9 x2, M7.69).  Do NOT edit game.js / bb.test.js until it ends (workers copy at start, but don't risk it).
- **Next session:** read summary.txt (or run.log.done); if it died, delete `scratch/mutants/.running` by hand.  Then
  `python scratchpad/compare_mutants.py` (expect 5,079 agree, 0 kills lost).  Fix any survivor/miss first.
- **Then, in this order (Claude decides the order now -- owner's rule 2026-10-07: don't stop to ask, pick and go):**
  1. the pause's spin polls (34 T each, declared uncharged in TIMING.md -- smallest, clears a declared gap);
  2. the join tail's writes in time (M7.99b's declared atomic-at-the-call writes; reuse M7.106's cut machinery);
  3. item 4 (title attributes frame for frame; the tape's post-cold-start world).  All solo.

## RESTART HERE (2026-10-07c, M7.106 in -- the countdown's advance in the straddling pass; nothing running)

- **The owner picked "M7.97's extra giant tick".  M7.106 commits it.**  Read docs/TIMING.md "M7.106" and TRAPS #291.
  - The cause was not the giant: a latched `$8E3A` reads the ISR's timer at `$8F29` / `$8F2E` at the END of every
    pass; the interrupt making `$0177` lands inside a pass, so the machine advances in that STRADDLING pass.  The
    port's atomic pass made EVERY countdown advance a whole pass (~6,000 T) late; the giant's extra tick was the
    visible symptom.
  - Measured: NEW `tools/cdstraddle.py` -> `build/cdstraddle_fixture.json` (registered in port.json; verify MATCH,
    ~40 s, `--jobs 6`): 5 worlds x clear 0..5 frames on, contended: 30 / 30 advances in the straddling pass (began
    14..4,600 T before the boundary, `$8F2E` 4,237..7,694 main-line T in), `$8F2E` 22 T after `$8F29`, `$97F8` 68 T
    after `$8F2E`, entered 471..7,015 main-line T after the boundary.  giantspawn verify still MATCH.
  - Engine: `BB_CD { E3A: 426, LO: 22 }` (`BB_Game.CD`); `roundClearCountdown` places each read on the pass clock
    (`cdPos`), `cdPast` (read start >= the interrupt point; a DI window -> counted `cdDiSkips`, not guessed); an
    advance needing the ISR sets `cdCut`, chainWalk returns 'cut', step() charges it as a clear, spends it (must end
    the frame or THROW), counts it; next step `cdResume` checks the timer (else THROW) and runs roundAdvance before
    any pass, `buildWin.entry` = the frame's start T.  Counters cdCuts / cdResumes / cdDiSkips.
  - Gates: **CD1** (fixture), **CD2** (through step(): round 1 cleared, read 926 T past the point, `$97F8` next frame
    at 994 T -- inside the machine's range; atomic variant a pass later; the cut charged as passcost's clear 455;
    a forced early cut THROWS), **CD3** (edges: at the point / 1 T before, torn `$00FF`, DI window, outside step(),
    resume mismatch throws, the read's place term by term from passcost's skeleton).  **GS2: the extra body is gone**
    (375 / 375, row for row the machine's).  DECLARED: the read's place uses the port's pass clock (78-T rest put
    before it); only the countdown's reads see the interrupt -- the rest of a pass is still atomic (TRAPS #90).
  - Suites: **bb 1,760 / kit 120 / selftest 34**; romscan 0.  Battery **5,181** (+20 M7.106, 4 re-aimed: scratch
    `scratchpad/distraddle/reaim106.py`, backup `mutate7.m7105.bak`; anchors.py 0 bad).  `--match "M7.106:"` 15/20 ->
    5 survivors (cut frame end guard, cut charged as plain pass, `$8E3A`'s own T / E3A 0 / wrap's `$7FFC` out of the
    read's place) -> CD2/CD3 rows added -> `--affected --jobs 20` LISTED 49 KILLED 49, 0 misses/crashes (6.6 min);
    compare_mutants 5,079 agree, 0 kills lost.  No Sonnet review (one routine, test-pinned).
- **Next (owner's call -- the NEXT list):** the join tail's writes in time; the pause's spin polls; item 4.  All solo
  (no unknown machine behaviour).  A possible follow-on, NOT on the list: other chain readers of the timer after the
  interrupt point (TRAPS #90's general non-atomic pass) -- only the countdown is cut.  A full battery is due at the
  next milestone (runner/rig/build unchanged since the last full run after M7.104).

## RESTART HERE (2026-10-07b, M7.105 in -- DI windows open 1 T into the DI; nothing running)

- **The full battery after M7.104 is DONE** (01:09..01:21, 12.4 min): `LISTED 5153  KILLED 5150  SURVIVORS 0  DEAD
  ANCHORS 0  TIMEOUTS 0  BROKEN 3 (the known B9 x2, M7.69)  CRASHES 0  MISSES 0`; `python scratchpad/compare_mutants.py`:
  5,079 agree, 0 kills lost, 76 new.
- **`1a14b46` M7.105: a DI window opens 1 T into its DI, not at its end** (the reviewer's item (a) from M7.104).  Read
  docs/TIMING.md "M7.105" and TRAPS #290.
  - Measured: scratch `scratchpad/distraddle/probe.py` (phase iterated to a fixed point, boundary d T after a DI's
    start): `$A9B5`, `$8F4C`, `$8C14` all LOST at d = 1..6, TAKEN at d = -2..0.  The engine took d = 1..3.
  - `tools/isrcarry.py`: + `STRADDLE` (first_di / di_start / straddle): 18 new rows (d = 1..3 for giant x2, perfect x3,
    extend:extcomp; wrap and head have no DI), 174 runs, old rows byte-identical (backup
    `scratchpad/distraddle/isrcarry_fixture.m7104.json`).  measure 63 s.
  - Engine: `BB_EXT_W.DI_OPEN: 1` at the giant / PERFECT award windows, the later umbrella flash, extDiFrom ($8C14,
    $9031, $A11B), `DI_ENTRY` [51, 129].  DI_AT stays 4 (the release's duration).
  - Gates: LZ1 52 runs (18 lost), LZ5 68 (22 lost), LZ7 11 (lost 3/3/3/4/4/4/4/4/3/3/3), IC 174 / 4,929 / 2,687;
    PF1, PF1b, RX1, RV1, UM1, LZ1, LZ5, E11 window starts = di_end - 3; E11's AT-the-point probe 51 short.  Hand
    mutation DI_OPEN 4: every straddle row fails in LZ1/LZ5/LZ7.
  - Suites: **bb 1,757 / kit 120 / selftest 34**.  Battery **5,161** (+8 M7.105, 9 re-aimed: scratch
    `scratchpad/distraddle/reaim105.py`; `scratchpad/lazy/anchors.py` 0 bad).  `--affected --jobs 20` (Start-Process +
    watch.ps1): LISTED 368 KILLED 368, 0 survivors/misses/crashes, 12.6 min.  No Sonnet review (small, test-pinned).
- **Next (owner's call -- the NEXT list):** M7.97's extra giant tick; the join tail's writes in time; the pause's spin
  polls; item 4.  All solo -- no unknown machine behaviour needing agents.  A full battery is not required yet
  (runner/rig/build unchanged); do one at the next milestone.

## RESTART HERE (2026-10-07a, M7.104 in -- `$94C2` is lazy and exact; the LAZY-STAMP ITEM IS DONE; full battery running)

- **`1827fc8` M7.104: `$94C2`, the EXTEND completion, timed a frame at a time (lazy) -- the last K block.**  Read
  docs/TIMING.md "M7.104".  No interrupts-on block keeps BB_EXT_K inside step() any more (K is only the model outside
  step(), unit calls).
  - Measured (scratch `scratchpad/ext/probe.py` -> mach*.json: every contended access with its PC): the only contended
    routines are repaint, digits, derive, lives, double ($8065/$8067), out, runs ($995C) and the item draws -- the ink
    cells ($8765 read 21 T before $876A's store: `BB_EXT_CP.INK_RD`), blit rows ($A306/$A30B sprite reads at $5D00..,
    always contended, 11 T before the stores: `BL_RD`; a ROM row keeps its reads), the expiry's cells and erase rows.
    entry/wipe/stride2/res7/records/award/spin/gate_on: empty programs.  extPass/extEntry/extBands take `cp`.
  - Machinery (shared): DI windows a segment at a time -- `lzWindows` validates (in order, or THROW) into `lz.wins` on
    the exact clock; `lzSeg` pushes each in the frame it opens in (open <= point) with its close walked past the point;
    a block that ends with an unopened window THROWS.  extRt pushes the reveal window on the exact clock when lazy (`wc`).
  - `tools/isrcarry.py`: + `EXT_VARIANTS` (tick, tickflood, storm from extendtime.VARIANTS, own phase only).  measure
    23 s; verify MATCH; old sources byte-identical.  Fixture backup of the old one: `scratchpad/ext/isrcarry_fixture.m7103.json`.
  - Gates: **LZ7** (new, before LZ4): 8 runs all EXACT (1,955 acceptances, lost 3/3/3/4/4/3/3/3, $8D09 wall T, main
    line, OUT at the window's close); phase 0 entered a frame early (isrcarry arms $94C2 with IFF 0).  LZ4 12 programs;
    IC 156/12/3,900; E5 (first frame ends AT the point), E11 (lazy windows; + a window opening AT the point), E12 (+
    extHold's `<` on the K path, flag saved/restored), C3 / LZ2 (all five lazy; + windows-backwards / unopened refusals).
  - Suites: **bb 1,757 / kit 120 / selftest 34**; romscan 0.  Battery **5,153** (+13 M7.104, 9 re-aimed; scratch
    `scratchpad/ext/reaim104.py`, anchors.py 0 bad): `--match "M7.104:"` 12/13 -> E11 row -> 1/1; `--affected --jobs 20`
    LISTED 271 KILLED 270, survivor "M7.57 ext: a write AT the interrupt point lands in this frame" (extHold's cut,
    unpinned once extend went lazy) -> E12 row -> rerun 203/203; compare_mutants 5,079 agree, 0 kills lost.
  - **Sonnet review (the item's ONE): no confirmed bug.**  Kept for later: (a) PRE-EXISTING edge, all blocks: DI windows
    open at the DI's END (`DI_AT` 4, DI_ENTRY 54), so an interrupt whose line rises 1..3 T into a DI is taken by the
    engine but lost on the machine (the storm payload's measured window starts at DI start + 1, BB_STORM_P.DI 160).
    ~3 T in 69,888 a window; worth one measurement (isrcarry/revealentry forced phases at DI start + 1..3) before
    touching `intLost`'s rule.  (b) extBands counts any row >= $40 as contended; the $FD00 table only aims at the
    screen or ROM -- unreachable.
- **FULL BATTERY RUNNING** (launched 01:09, PID 42524, watcher 12084, `--jobs 20` via Start-Process; required at the
  item's end -- none since c2f6a19).  Result -> `build/mutants/summary.txt`, log `build/mutants/run.log`, done file
  `build/mutants/run.log.done`.  Expect ~5,153 listed, the known BROKEN 3 (B9 x2, M7.69).  Don't wait on it; next
  session: read summary.txt, then `python scratchpad/compare_mutants.py`; fix any survivor first.
- **Next (owner's call -- the NEXT list):** the DI-straddle measurement above (small, solo); M7.97's extra giant tick;
  the join tail's writes in time; the pause's spin polls; item 4.  All solo -- no unknown machine behaviour needing agents.

## RESTART HERE (2026-10-06l, M7.103 in -- the umbrella's head is lazy and exact; `$94C2` extend next, the LAST)

- **`d3811ef` M7.103: the umbrella's head (`$88C0`, BB_EXT_BLOCKS.umb_head) on the lazy machinery.**  Read docs/TIMING.md
  "M7.103".
  - Measured: isrcarry's `head:natural` acc_k (1,408 x k4 + 1 x k8 = 1,409 = n_acc) is exactly u_flash's program, so
    `u_head` returns an EMPTY cp.  `umb_head` has `lazy: true`; `umbFlash`'s `$A0E0` OUT goes to `lz.outs` ([w.t0, a])
    when `lzOn`, else mainOut as before.  No other machinery change: the head ends at the HALT, lzStep/extEnd leave
    tframe there, umbStep spends the rest of the frame (M7.98's segments untouched).
  - Gates: **LZ6** (new, before LZ4 in bb.test.js): 17 rows, all exact first try (8 acceptances, HALT wall T, main
    line); phase 0 enters AT the point, so the OUT is logged HEAD into the next frame (the gate expects that).  LZ4 now
    8 sources; C3 / LZ2 lists `["wrap","giant","perfect","umb_head"]`.  UM3 unchanged (26 frames, 15 lost).
  - Suites: **bb 1,756 / kit 120 / selftest 34**; romscan 0.  Battery **5,140** (+6 M7.103 cases; the 2 M7.98 flash-OUT
    cases re-aimed to the `else this.mainOut(...)` line; scratch `scratchpad/lazy/addmuts103.py`, `anchors.py` 0 bad):
    `--affected --jobs 20` LISTED 97 KILLED 97, 0 misses/crashes (2.3 min); compare_mutants 0 kills lost.
  - **Launch note:** mutants.py launched from the Git Bash tool (even foreground) dies with BrokenProcessPool -- use
    the PowerShell tool's Start-Process line (06b) + `scratchpad/battery/watch.ps1 <PID> <LOG>` + a cron poll.
- **Next step (solo): `$94C2` extend onto `lazy` -- the last K block.**  Its reveal's DI window opens far past the first
  interrupt point: `lzWindows` currently THROWS on that (LZ2 'late'), so it must time windows segment by segment (each
  window put on the frame clock in the frame where it opens, from that frame's phase -- likely inside lzSeg).  Many of
  its routines have no cp yet (entry, wipe, stride2, res7, records, items, double, runs, award, spin, gate_on ...):
  probe each against isrcarry's `extend:extcomp` acc_k (one source, own + 4 forced; 1,345,409 instructions) the way
  `scratchpad/lazy/gihead.py` / `wrhead2.py` do.  extend's ISRs are all gate-closed and uncontended (M7.99e), so it
  should be exact in play.  Add `extend:extcomp` to LZ4, an LZ7 row set, drop `extend` from C3's K list.
  Then, item END: ONE Sonnet reviewer (brief: lzSeg's instruction rule, bbAcc, lzPush, the windows-by-segment change),
  then a FULL battery run (Start-Process line in 06b; none since c2f6a19 -- runner/rig/build unchanged).
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the pause's
  spin polls; item 4.

## RESTART HERE (2026-10-06k, M7.102 in -- `$8F4C` perfect is lazy and exact; the umbrella's head next)

- **`3794ef0` M7.102: the treasure room's `$8F4C` block on the lazy machinery.**  Read docs/TIMING.md "M7.102" and
  TRAPS #289.
  - Program (matches isrcarry's `acc_k` digest on lastdia81 / lastdia82 / r1_lead, all k = 4): the award's HUD glyph
    stores, then per draw 9 x 16 "PERFECT !" row stores (`extDouble(off, str, cp)`) + `$994F`'s 18 attribute stores
    (pf_runs); pf_end empty.  `perfect` has `lazy: true`.
  - **Shared machinery change:** `extRt` now pushes programs via `lzPush(w)`; a CLOCKED routine (`m.clk`, i.e.
    pf_award) is pushed at its CLOSE (the next routine's hook) from `awClk.cp` (treasureBlock gives ck `cp: []` when
    lzOn); no clock log THROWS.  No lazy block may END on a clocked routine (none does; noted in lzPush's comment).
    The award's DI window is pushed with EXACT offsets when lazy (`this.extT + LD_B`) for lzWindows.
  - Gates: **LZ5** (new: 51 isrcarry rows + perfecttime's 8 DI-window rows = 59, all exact: 1,819 acceptances, 13
    lost, the window = perfecttime's on 43 runs, end wall T, main line); LZ4 now 7 sources; PF1b measures the K model
    with the flag DOWN (save/restore -- TRAPS #289, the battery caught the restore-a-constant bug); PF2 hooks lzHold;
    C3 / LZ2 lists `["wrap","giant","perfect"]`; LZ2 + the clockless-award refusal.
  - Suites: **bb 1,755 / kit 120 / selftest 34**; romscan 0.  Battery **5,134** (+14, 2 re-aimed; scratch
    `scratchpad/lazy/addmuts102.py`, `anchors.py` checks every case's anchor is unique): `--match "M7.102:"` 13/14 ->
    the survivor was the PF1b test bug, fixed, 1/1; `--affected --jobs 20` (detached, Start-Process + watch.ps1)
    LISTED 110 KILLED 110, 0 misses/crashes (2.1 min); compare_mutants 0 kills lost.  Probe: `scratchpad/lazy/pf1.js`.
- **Next step (solo): the umbrella's head (`$88C0`, BB_EXT_BLOCKS.umb_head) onto `lazy`.**  `u_head` needs an access
  program (probe it from isrcarry's `head:natural` source as `scratchpad/lazy/gihead.py` / `wrhead2.py` do; its one ISR
  has 92..96 T of contention, M7.99e); umb_head interacts with umbSeg / umbHeld (M7.98's segment-between-HALTs model) --
  read those first.  LZ4 must add `head:natural` (its acc_k: 1,408 x k4 + 1 x k8).  Then `$94C2` extend last (its
  reveal's DI window opens far past the first point -- lzWindows must time windows segment by segment; many routines
  with no cp).  Remove each from C3's K list.  ONE Sonnet reviewer at the END of the item (lzSeg's instruction rule,
  bbAcc and now lzPush are new shared machinery -- include them in its brief), then a FULL battery run (Start-Process
  line in 06b; none since c2f6a19 -- runner/rig/build unchanged, so not yet required).
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the pause's
  spin polls; item 4.

## RESTART HERE (2026-10-06j, M7.101 in -- the wrap is lazy and exact; `$8F4C` perfect next)

- **`d289310` M7.101: the storm wrap (`$A09A`) on the lazy machinery, and lzSeg fixed at the interrupt point.**  Read
  docs/TIMING.md "M7.101" and TRAPS #288.
  - The head `$A09A..$8C28`: 172 T, one contended access = the `$A0B0` OUT's I/O cycle at 100 (`BB_EXT_CP.WR_OUT`;
    probe `scratchpad/lazy/wrhead2.py`).  `wrap` has `lazy: true`; `paid` 90 works through lzStep.
  - **lzSeg change (shared machinery):** the machine takes an interrupt at an instruction's END, so the accesses of
    the instruction in progress at the point run BEFORE the ISR.  Every program access now goes through
    `bbAcc(cp, insStart, k)` (k = T into its instruction, kept in `cp.k`; `lz.ins`); lzSeg breaks at the first access
    whose instruction starts past the point.  extRt THROWS on a lazy program access with no k.  Every producer
    (repaint, digits, derive, panel, lives, out, wrap, giant, u_flash) was converted; `RD` 4 (`LD A,(HL)`), `RD_NN` 10
    (`$80E7 LD A,(nn)`), ST 4, OUT cycles 8.
  - `tools/isrcarry.py` records each source's machine `acc_k` (digest of `T:k;` + the k histogram); re-measured,
    `verify --jobs 6` MATCH.  perfect's: k = 4 only (41,568 / 41,512 accesses); head:natural: 1,408 x 4 + 1 x 8.
  - Gates: **LZ3** (34 wrap rows, all exact; 10 forced phases no head reaches run with the head's program out),
    **LZ4** (engine `T:k` stream == machine's on giant x2, wrap x2), LZ2 (+ no-instruction throw), RX2's wrap spread
    retired, C3 / LZ2 lists `["wrap","giant"]`.
  - Suites: **bb 1,754 / kit 120 / selftest 34**; romscan 0.  Battery **5,120** (+17, 12 re-aimed):
    `--match "M7.101:"` 17/17; `--affected --jobs 20` LISTED 80 KILLED 80, 0 misses/crashes (1.4 min);
    compare_mutants 0 kills lost.  Scratch: `scratchpad/lazy/` (spec7..13, addmuts.py, reaim.py, k10.py).
  - Note: u_flash's k values are not gated (the umbrella's blocks are not lazy); LZ4 must add `head:natural` when the
    head goes lazy.
- **Next step (solo): `$8F4C` perfect onto `lazy`.**  pf_award is a CLOCKED routine (stamps from awClk; its cp from
  ck.cp like the giant's -- push via the same glyph-store path); pf_double / pf_runs need access programs (extDouble's
  glyph stores, the attribute runs) -- measure first against isrcarry's perfect sources (`acc_k` is all k = 4: stores
  or `LD A,(HL)` reads).  Then LZ1-style rows for lastdia81/82 and r1_lead (17 rows each; seeds as perfecttime's), an
  LZ4 entry per source, and remove `perfect` from C3's K list.  Then the umbrella's head (`u_head` needs a cp;
  umb_head interacts with umbSeg/umbHeld), and `$94C2` extend last (its reveal's DI window opens far past the first
  point -- lzWindows must time windows segment by segment).  ONE Sonnet reviewer at the END of the item (lzSeg's
  instruction rule and bbAcc are new shared machinery -- include them in its brief), then a FULL battery run
  (Start-Process line in 06b; none since c2f6a19 -- the runner/rig/build are unchanged, so not yet required).
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the pause's
  spin polls; item 4.

## RESTART HERE (2026-10-06i, M7.100 in -- the giant's block is lazy and exact; the wrap next)

- **`954aaa4` M7.100: the LAZY-STAMP machinery, proved on the giant (`$A9B5`).**  Read docs/TIMING.md "M7.100" and
  game.js's BB_ULA comment (the M7.100 paragraph).  A block with `lazy: true` in BB_EXT_BLOCKS, inside step():
  `extRt` pushes each routine's access program onto `lz.acc` (block-exact clock); `extPut` -> `lzHold` holds the write
  UNSTAMPED (`[Infinity, a, v, , , , exact]` in heldWrites); `extOut(a)` queues the OUT (returns false); `extEnd` runs
  `lzWindows` (DI windows -> frame clock, contended; one opening past the first point THROWS) and `lzSeg` for the call's
  frame; step() calls `lzStep(budget)` before flushWrites for every later frame.  `lzSeg(s, budget)` lands the writes /
  logs the OUTs before the point, returns the end's frame T or carries the point (`lz.x`, `lz.i`).  `rvIsr` uses `lz.x`.
  extBegin refuses a block while `this.lz` drains.  Outside step() lazy blocks keep K.
  - The giant's award program: giantCollide runs `$80FA` on an award clock (`awClk` with `cp: []`, base PRE 120);
    `scoreGlyph` pushes each display store + 4 into `ck.cp` -> `this.gaCp` -> extModel('giant').  32 stores, 2017..4020 T.
  - `tools/isrcarry.py` gained `GIANT_WIN` (revealentry's six in-window phases): 153 runs, `verify --jobs 6` MATCH.
  - Gates: **LZ1** (46 giant rows, machine ISR walls injected: acceptances, 12 lost, end wall T, main_delay -- all exact;
    window's contended end; the OUT), **LZ2** (boundary + 4 refusals); RX2's giant dmain retired (null); RX3 adapted
    (lazy write order at each ISR; an ISR flip between exact and contended point -> rvMoved 1); C3 lists `lazy`; IC 153.
  - `__PORT__` (web/template.html) now exports `BB_EXT_CP`, `bbUlaDelay`.  TRAPS #287 (a term the geometry zeroes).
  - Suites: **bb 1,752 / kit 120 / selftest 34**; romscan 0.  Battery **5,103** (+17 M7.100 cases, 9 re-aimed):
    `--match "M7.100:"` 17/17; `--affected --jobs 20` LISTED 45 KILLED 45, 0 misses/crashes; compare_mutants 0 kills lost.
  - Scratch: `scratchpad/lazy/` (specs, `gihead.py` -- the award-access probe, logs; backups game.js.bak, mutate7.bak).
- **Next step (solo): the storm WRAP (`$A0BE`, BB_EXT_BLOCKS.wrap) onto `lazy`.**  What it needs:
  1. the 'wrap' routine's access program ($A09A..$A0BE, BB_STORM.WRAP 172 T): probe it as `scratchpad/lazy/gihead.py`
     does (isrcarry's `start` + `RC.sim_of(h, log)`, log the accesses before PC = $8C28) -- likely none (code above $8000);
     then `case 'wrap': return { off, dur: BB_STORM.WRAP, cp }`.
  2. `lazy: true` on wrap; `paid` is 90 here (lzStep / extEnd subtract it -- the first block where that matters).
  3. LZ1-style rows from isrcarry's wrap sources (round1_48, r50_48; 17 rows each; seeds = revealentry A0BE, the door
     arms ($FECE)=0, ($FECF)=$FF, ($A09E) = ($8DBD)^1 and calls effectManager()).  With the machine's ISR walls it should
     be exact; the engine's own isrCost differs by the ISR's contention (477..709 / 2,609..2,624 T a run, DECLARED).
  4. RX2's wrap dmain spread ('-10619..7299') and RX3's A0BE run will move like the giant's did; rx3m (the colour-shadow
     flip) must still count 1 with reads on the exact clock.
  Then `$8F4C` perfect (pf_award is a CLOCKED routine -- its writes stamp from awClk, its cp from ck.cp like the giant's;
  pf_double / pf_runs need access programs: extDouble's glyph stores and the attribute runs -- measure first), the
  umbrella's head (`u_head` needs a cp; `umb_head` interacts with umbSeg/umbHeld), and `$94C2` extend last (many routines
  with no cp; its reveal's DI window opens far past the first point -- lzWindows must time windows segment by segment).
  Remove each from C3's K list as it lands.  ONE Sonnet reviewer at the END of the item (shared machinery: memory
  `token-economy`), then a FULL battery run (Start-Process line in 06b; none since c2f6a19).
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the pause's
  spin polls; item 4.

## RESTART HERE (2026-10-06h, M7.99e in -- the measurement says the lazy-stamp design holds; OWNER'S GO NEXT)

- **`30320bc` + `0735053` M7.99e (measurement only, no engine change): `tools/isrcarry.py` -> `build/isrcarry_fixture.json`**
  (registered in port.json, read by the new gate row **IC** at the end of bb.test.js).  Read docs/TIMING.md "M7.99e".
  Sources: wrap `$A0BE` (round1_48, r50_48), giant `$A9B5` (fallcandy, peachfall), perfect `$8F4C` (lastdia81/82, r1_lead),
  the umbrella's head `$88C0`, extend `$94C2` (extcomp) -- own phase + 16 forced (extend own + 4): 141 runs, ~14 s
  (`verify --jobs 6` MATCH).
  - **(a) EXACT on 141/141:** the machine's main line is the plain run's (no ISR changes its flow), and replaying the
    uncontended access program from the entry's phase, with the machine's ISR wall T at each predicted acceptance,
    gives every acceptance (instruction index + wall T) and the block's end to the T.
  - **(b) CLOSE:** RAM before each of the 356 own-phase ISRs fed to the built engine's `isr()` (probes, not gates:
    `scratchpad/isrcarry_eng/isrsnap.py` then `node scratchpad/isrcarry_eng/isreng.js`; the .bin dumps are $4000+ only
    and live beside the scripts, not committed): **isrCost == the machine's UNCONTENDED ISR T on 356/356.**  The gap is
    only each ISR's own contention: 0 on giant, the natural perfects, extend; <= 883 T an ISR and <= 2,661 T summed
    over a block on wrap r50_48 / perfect r1_lead (wrap round1_48 477..709, head 0..96).
  - Suites: **bb 1,750 / kit 120 / selftest 34**.  Battery `--affected --jobs 20`: LISTED 7 KILLED 7, 0 misses/crashes,
    5.3 min; compare_mutants 0 kills lost.  IC mutation by hand: GATE_CLOSED_EVEN + 1 -> IC + 9 rows FAIL.
    Still no full run since c2f6a19 (no rig/build/runner change) -- do one at the end of this item.
- **Next step (owner's go -- engine work, shared machinery):** the LAZY-STAMP design.  An interrupts-on block's routines
  carry access programs as the `ula` blocks do (M7.99c's `extModel(kind, cp)` / `extCon`), but the block's stamps are
  NOT fixed at the call: flushWrites()/step() resolve them frame by frame, each frame's segment timed from that frame's
  actual phase (the resume point = the interrupt point + the engine's isrCost, which (b) shows is the machine's
  uncontended ISR T).  Exact where the ISR is uncontended (giant, extend, natural perfects); off by the ISR's own
  contention elsewhere (DECLARED -- the engine-wide ISR-contention gap, STATUS "Left: contention").  Start with the
  giant ($A9B5, short, ISR exact) as the proving block, gate it against isrcarry's rows (accepts + end per phase),
  then wrap / perfect / head / extend.  Remove each from C3's K list and its extBegin throw as it lands.
  Solo, with ONE Sonnet reviewer at the end (shared machinery: memory `token-economy`).  Then a FULL battery run.
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the pause's
  spin polls; item 4.

## RESTART HERE (2026-10-06g, M7.99d in -- the owner chose "the interrupts-on blocks' K")

- **The owner picked item 1 of the NEXT list:** the interrupts-on blocks' K -> the access-by-access model (M7.99c's
  C3).  Read docs/TIMING.md's "M7.99c" and "M7.99d" sections first.
- **`42a2292` M7.99d: the umbrella's LATER flashes** (`$A121 DI .. the HALT`, turns 2..5) turned out to have
  interrupts OFF from their first instruction -- no ISR inside -- so they are now timed by their accesses
  (`umb_flash` is `ula`, `diFrom: 'u_turn'`; `BB_EXT_CP.FL_OUT` 8 / `FL_RD` -11).  `tools/revealcont.py` gained the
  'flash' sources (20 turns x 17 phases = 340 runs, replay exact; `verify --jobs 6` MATCH ~26 s).  New row
  **M7.99d C4**; UM2's flash spread 0..0 (was -617..+512); C3's boundary list updated.
  Suites: **bb 1,749 / kit 120 / selftest 34**; romscan 0.  Battery 5,086 cases (+7):
  `--affected --jobs 20`: LISTED 63 KILLED 63, 0 misses/crashes, 6.5 min; compare_mutants 0 kills lost.
  No full run since c2f6a19 (not required: no rig/build/runner change) -- do one at the end of this item.
- **What is LEFT of the item -- the blocks with ISRs INSIDE** (`$94C2` extend, `$A09A` wrap, `$A9B5` giant, `$8F4C`
  perfect, the umbrella's head `$88C0`).  The problem, read off the code (game.js `extBegin`/`extRt`/`extHold`/
  `extEnd` ~9100..9330, step() ~18190): a block stamps ALL its writes at the call on the main-line clock
  (`heldWrites` [T past the budget, addr, value]) and `spend()`s its whole contended T at `extEnd`; step() then
  maps main-line T onto frames with each frame's `budget = FRAME - isrCost`, where `isrCost` is the ISR the
  PREVIOUS step() ran -- so the phase where the main line resumes after each ISR inside the block (= that ISR's
  end) is not known when the block stamps.  The access delays after an ISR depend on that phase.
- **Next step (solo -- the measurement is cheap and complete):** MEASURE before designing.  A tool (extend
  revealcont.py or a new `tools/isrcarry.py`; list `tools/` first, TRAPS #231): for each interrupts-on block on
  its existing worlds (revealentry's wrap/giant seeds, perfecttime's worlds, umbrella's head, extcomp's
  completion), run the CMIOSimulator WITH interrupts and record each ISR's start/end T inside the block; then
  (a) replay the block's logged access program segment by segment, each from the machine's own ISR end -- is the
  main line exact? (watch the interrupt's acceptance at an instruction's end); (b) put the ENGINE's isrCost for
  the same frames beside the machine's ISR T -- how far apart?  If (a) is exact and (b) is close, the design is
  a block whose stamps are computed lazily, frame by frame in flushWrites/step() from the frame's actual
  isrCost (shared machinery: one Sonnet reviewer, memory `token-economy`).  If (b) is far, the gain is bounded
  by the ISR model and the owner should hear that before any engine work.
- Then the rest of the NEXT list (owner's call): M7.97's extra giant tick; the join tail's writes in time; the
  pause's spin polls; item 4.

## RESTART HERE (2026-10-06f, the battery is clean -- OWNER'S CALL NEXT)

- **FULL RUN after `c2f6a19` (Start-Process, 15:40..16:00): `LISTED 5079  KILLED 5076  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 0  BROKEN 3  CRASHES 0  MISSES 0  -- 19.9 min on 20 workers`** (incl. the fresh ~4 min prep).  BROKEN = the
  known three (B9 x2, M7.69).  The log has NO "depends on earlier blocks" lines: every gate block passes alone.
  `compare_mutants.py`: 5,079 agree, 0 kills lost, 0 gained.  Nothing running; `scratch/mutants/.running` is gone.
- **Master all green: bb 1,748 / kit 120 / selftest 34.**  The battery work is finished.
- **Next: the owner picks from the NEXT list** (the 06 section below: the interrupts-on blocks' K via the
  access-by-access model; M7.97's extra giant tick; the join tail's writes in time; the pause's spin polls; item 4 --
  title attributes, post-cold-start world).  The first is unknown machine behaviour across several ISR-shifted
  blocks -- agents worth considering (memory `multi-agent-pass-decision`), within the token-economy rule (one Sonnet
  agent at a time).  The rest are solo-sized.
- Housekeeping: `bubble-bobble-mutants-handover.zip` is still untracked in the repo root (the owner's file; its
  HANDOVER is archived at `docs/archive/HANDOVER-MUTANTS.md`) -- the owner may delete or keep it; never commit it.

## RESTART HERE (2026-10-06e, the page blocks self-contained -- full run DONE, see 06f)

- **`c2f6a19` (test-only): blocks 87, 90, 94, 112, 113, 114 now pass ALONE.**  A prelude helper `PAGE_RUN`
  (top of M7.64 in `test/bb.test.js`) holds the page drives, each run once by whichever block asks first:
  `loaded()` (M7.64(a)'s boot recorded before any drive, M7.64(c)'s key-event drive to the title, and `at` -- a COPY
  of the page as that drive left it, read by M7.64(c)/(c2) and M7.42's boundary row), `played()` (adds KR-page's
  '1'-into-play + KeyP drive), and `clock()` -- ONE forward-only page clock (the loop starves on a dt below its last,
  so the old per-row `let tw = 1e5/3e5/1e6/5e6/9e6` would stall out of file order).  `PAGE_BOOT` (a block-written
  top-level let) is gone.  Checked: 83, 84, 87, 90, 94, 112, 113, 114 each alone, reversed (114..83) and two mixed
  orders -- all pass.  Suites: bb 1,748 / kit 120 (selftest 34 unchanged).
- **FULL RUN LAUNCHED 15:40, PID 19476** (Start-Process, `--jobs 20`).  Result -> `build/mutants/summary.txt`, log
  `build/mutants/run.log`.  Don't poll it.  Expect ~15 min plus a fresh prep (bb.test.js changed: coverage pass
  ~3 min), and NO "depends on earlier blocks" lines in the log (the prep's learned chain is gone).  Expect KILLED
  5,076 + BROKEN 3 (B9 x2, M7.69), CRASHES 0, MISSES 0.  Then `python scratchpad/compare_mutants.py` (0 kills lost
  expected), record the line here + a commit.  If it died: delete `scratch/mutants/.running` by hand.
- **Next after that:** the owner's NEXT list (the 06 section below) -- owner's call which item.

## RESTART HERE (2026-10-06d, full run after the runner fix IN; 2 CRASHES fixed in a row)

- **FULL RUN after `9d6681b` (Start-Process, 13:55..14:10): `LISTED 5079  KILLED 5074  SURVIVORS 0  DEAD ANCHORS 0
  TIMEOUTS 0  BROKEN 3  CRASHES 2  MISSES 0  -- 15.2 min on 20 workers`** (was 58.3 min: the killers recorded in
  last.json now run first).  MISSES 0, as expected.  BROKEN = the known three (B9 x2, M7.69).
- **The 2 CRASHES were a fragile TEST ROW, not a gate gap:** "M7.58 tick: the flash / strike paints in one call".
  The mutants leave the painter's log short; M7.58 ST1's per-store loop ran to the MACHINE's length and read
  `u.log[j][0]` past the end -> TypeError, no `BB_` diagnostic -> CRASH.  (parallel.py had called these DIAGNOSTIC:
  in the whole suite an engine diagnostic fired first; the selection now runs ST1's block first.)  Fix: the loop
  is bounded by `u.log.length` too (the length mismatch is already a `bad` entry the line above).  Checked by hand:
  flash mutant -> 5 FAILs (ST1, ST2, ST4, PS2...), strike -> 4 FAILs; clean tree bb 1,748 / kit 120.
- **`--affected --jobs 20` after the fix: `LISTED 85  KILLED 85  ... CRASHES 0  MISSES 0 -- 7.1 min`**;
  `compare_mutants.py`: 5,079 agree, 0 kills lost, 0 gained.  So the battery stands at 5,076 killed + 3 known BROKEN.
- **Next (solo, test-only):** make blocks 87, 90, 94, 112, 113, 114 self-contained (the "Open" item in 06b
  below), then a FULL run (~15 min now; Start-Process line in 06b).  Then the owner's NEXT list (06 section).

## RESTART HERE (2026-10-06c, the 3 MISSES fixed in the runner -- FULL RUN IN PROGRESS)

- **`9d6681b` (runner only; suites unchanged: bb 1,748 / kit 120 / selftest 34).**  The first full run's 3 MISSES:
  - **Optimised code does not count its calls.**  Block 51 calls `smallRun` 145,768 times; block 134's 1,383 calls
    then record 0 in V8 precise coverage (TurboFan; not inlining, not bytecode flushing, not Maglev -- each tried).
    `tools/mutants.js cover` now runs `node --no-opt` (coverage pass 101 s -> 175 s, cached by prep key).
    Re-mapped: 90 of 5,079 cases had been under-selected (1,584 block slots); only M7.96's became a MISS.
  - **Source-text kills** (M7.11, M7.24: behaviour-equivalent refactors caught only by rows that grep BUILT_SRC --
    blocks 53 and 67): coverage can never map them.  The survivor confirmation now runs the SELECTABLE copy with
    every block (so a MISS records its killing block), and a recorded killer outside a case's coverage joins its
    selection and runs first.  So a source-text hole is a MISS once, then a cheap kill.
  - Checked: `--match "inlined again||smallRun charges again"` twice: MISSES 2 then 0 (0.1 min).
  - Kit fixes to report upstream (with `--background`'s pool failure): these two.
- **FULL RUN LAUNCHED 13:54, PID 21680** (Start-Process, `--jobs 20`), required by the runner change.  Result ->
  `build/mutants/summary.txt`; log `build/mutants/run.log`.  Don't poll it.  Expect ~60 min, KILLED 5,076 + BROKEN 3,
  MISSES 0 or 2 (the two source-text cases learned their killers in the --match runs, so 0 expected).  Then
  `python scratchpad/compare_mutants.py` (0 kills lost expected), and record the line in next.md + a commit.
  If it died: delete `scratch/mutants/.running` by hand.
- **Next after that (solo, test-only):** make blocks 87, 90, 94, 112, 113, 114 self-contained (the "Open" item below),
  then a full run.  Then the owner's NEXT list.

## RESTART HERE (2026-10-06b, the kit's runner installed -- FULL RUN IN PROGRESS)

- **The battery now runs with `tools/mutants.py`** (the kit's runner, from the owner's
  `bubble-bobble-mutants-handover.zip`; its HANDOVER is at `docs/archive/HANDOVER-MUTANTS.md`).
  How to use it: "How to work -> Battery" below; CLAUDE.md house rule 3 says the same.
  - `3ffcc6c` installed it (tools/mutants.py, tools/mutants.js, tools/vendor/acorn.js + MIT licence;
    port.json "mutants"; .gitignore `scratch/`, `build/mutants/`; tools/README.md row).
  - `--profile --jobs 20`: baseline 1,748 / 1,748; the selectable copy ran the same checks; a case
    under coverage 99.4 s, "about 0.9 s" with the killing block first (x110).
  - `--sample 40 --jobs 20`: 40 / 40 KILLED, MISSES 0, 2.3 min; `compare_mutants.py` against
    `full_m799_cases.json`: 40 agree, 0 kills lost.
- **`--background` FAILS ON THIS MACHINE** (the handover warned it was untested on Windows): launched
  10:57 (PID 26200), it died 20 s later as its 20-process pool started -- `BrokenProcessPool: A process
  in the process pool was terminated abruptly` (log kept: `build/mutants/run_detached_failed.log`).
  Use Start-Process instead (proven):
  `$p = Start-Process python -ArgumentList 'tools/mutants.py','--jobs','20' -RedirectStandardOutput
  build/mutants/run.log -RedirectStandardError build/mutants/run.err -WindowStyle Hidden -PassThru`.
  (A kit fix to report upstream: DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP breaks the pool.)
- **FIRST FULL RUN WITH tools/mutants.py DONE (2026-10-06 10:59..11:57, Start-Process, 20 workers):
  `LISTED 5079  KILLED 5076  SURVIVORS 0  DEAD ANCHORS 0  TIMEOUTS 0  BROKEN 3  CRASHES 0  MISSES 3  --
  58.3 min`** (parallel.py: 350.9 min).  `compare_mutants.py` against M7.99's parallel.py run: 5,079
  agree, 0 kills lost, 0 gained.  BROKEN = the known three (B9 x2, M7.69).  `build/mutants/last.json`
  now holds every case's killing block, so `--affected` runs are fast from here.
  **The 3 MISSES** (killed only by the whole suite; the coverage selection did not pick the killing
  block -- costs time, not a verdict, but each is a selection hole): "M7.24: the element redraw is
  inlined again, so $7E04 has two spellings", "M7.11: the wind read is inlined again, duplicating
  driftCode()", "M7.96: smallRun charges again what the run already spent in time".  The first two
  look like source-text checks (a row that greps BUILT_SRC never executes the anchor, so coverage
  cannot map it); worth a look -- the runner may need a "source rows" rule, or those rows a home in a
  block the anchor reaches.  Solo, small.
- **Open (recommended by the handover, not done):** make blocks 87, 90, 94, 112, 113, 114 of
  `test/bb.test.js` self-contained (each drives `P.game`, the page's one game object, and needs
  83..86 -- the load path, the title wait, the round drain -- to have driven it first).  Careful:
  M7.64(a) records the page's boot BEFORE any row drives it, so a reset must not disturb 83's
  premise.  A test-only increment, solo; a full run after it.  The runner prints
  "depends on earlier blocks" lines until it is done.
- Then the NEXT list of the section below is unchanged (owner's call).

## RESTART HERE (2026-10-06, battery IN -- the owner pauses here)

- **FULL BATTERY DONE (2026-10-06 01:48..07:39, 350.9 min, 20 workers): 5,079 / 5,079 KILLED, 0 survivors, 0 dead
  anchors, 0 timeouts.**  Only the known cases: B9 x2 + M7.69 BROKEN-MUTANT, M7.13 three FAILs then a hang.  Per-case
  results in `scratchpad/battery/full_m799_cases.json`.  A full run is now ~5.9 h.  Nothing to fix.
- Waiting on long jobs: the battery runner detaches itself (`--background`) and is not waited on;
  for any other long job: launch detached, `scratchpad/battery/watch.ps1 <PID> <LOG>` (writes
  `<LOG>.done`), then a CronCreate poll -- never a Claude background shell / Monitor (memory
  `detached-monitors`).
- **Master `1e7b62d`, all green: bb 1,748 / kit 120 / selftest 34; romscan 0.  No worktrees.**  This session:
  - Owner's report (a jump up through a platform pauses the horizontal travel) MEASURED FAITHFUL: the machine holds X
    for 6 frames rising through round 1's first platform ($ADAA's wall probe); the engine matches (0 / 90 frames
    differ, two scripts: `scratchpad/platjump_mach.py`, `scratchpad/platjump_eng.js`).  No change.
  - `a9242a0` M7.99a (`tools/bosskillcost.py`): the boss tick's A=4 spawn was ALREADY charged by M7.96's BB_SM (M7.97's
    note corrected); the heart kill through $9298 is made + charged (forced: HL = $A9AF always -- `$8BC2` makes the
    corpse over $A969's own code, the toucher paid $1000).  Declared (BK4): the machine executes a corrupted byte 3
    frames on; the arm's DI window off the frame clock; HL unknown on the tape's live SCF/RET pair.  Subset 29/29.
  - `29278b3` M7.99b (`tools/jointail.py`): a P2/P1 join's tail MAKES `$7FD7`'s 64-cell clear + the `$806C` lives
    panel at machine T (BB_JOIN.HEAD 120); `$915F` makes Boris's `$A314` erase.  Declared: the tail's writes land at
    the call (atomic pass -- 7 of 16 natural joins have an interrupt inside); Boris's erase offsets not compared.
    Subset 22/22.
  - `1e7b62d` M7.99c (`tools/revealcont.py`): the DI reveal ($9031 / $A11B) is timed ACCESS BY ACCESS from the entry's
    frame phase (contention depends only on each $4000..$7FFF access's position): 523 runs exact; RV2 and UM2's
    declared misses are GONE (spreads 0..0).  Still K (declared, C3): outside step(), and the interrupts-on blocks
    ($94C2, $A09A, $A9B5, $8F4C, the umbrella's flashes).  No subset (the full battery covers its 47).
- **NEXT after the battery (owner's call):** the interrupts-on blocks' K -> the same access-by-access model where an
  ISR's phase shift can be carried (M7.99c's C3); M7.97's extra giant tick in the advancing frame; the join tail's
  writes in time (not at the call); the pause's spin polls; item 4 below (title attributes, post-cold-start world).

## Standing instructions from the owner

- **Faithful first, then modern (restated 2026-09-28).**  Finish the FAITHFUL port, commit it,
  and only THEN adapt it for controllers and other modern goodies, as a declared, flagged layer.
- **Do NOT integrate controllers** (no gamepad or Kempston mapping, no changes to
  `web/platform.js`'s gamepad handling) until the owner asks.  The owner's words: "If a player
  selects option 2-4 for any of the players then that player's character is unable to be
  controlled."  What that means on the faithful path, told to the owner:
  - SINCLAIR (2) and CURSOR TYPE (4) are KEY PRESETS on the machine (`"6790"` then `"1245"`,
    `"5807"`), so faithfully the number keys drive that player -- no controller code involved.
  - KEMPSTON (3) reads port `$1F`; with no controller it reads nothing, so that player cannot move.
  - DONE in M7.64: the template's `poll()` zeroes both Kempston ports unless `BB_PAGE.padKempston`
    (ADDED, default OFF) is set, so option 3 is dead until the owner asks for controllers.
- **Token economy** (memory: `token-economy`).  No multi-agent review workflows.  At most
  ONE reviewer agent, on Sonnet (`model: 'sonnet'`), with a narrow brief and a short report,
  and only for increments that add shared machinery.  One agent at a time, never in parallel.
  Small increments done inline.  The free local checks carry the verification.  Keep tool
  output short.
- **Decisions of 2026-09-28** (memory: `bubble-bobble-port-decisions`; README's declared
  departures): the page presents the FULL original control-select menu (all four options);
  `$FAC3`'s 5-second black screen is skipped by default behind a named flag, the faithful wait
  kept and tested; the substitute font keeps its current no-ROM rule; the git history's old ROM
  quotes stay local -- there is no remote; scrub or squash the history BEFORE any publication
  (this now includes the ROM bytes M7.72's corpse fixture carried until M7.74b -- TRAPS #281).

## Where it stands

- **Commits.**  `git log` is the record; the per-increment notes up to M7.83 are in
  `docs/archive/next-2026-10-06.md`.
- **Suites.**  `node test/bb.test.js` 1,772 (~45 s); `node test/kit.test.js` 120;
  `python tools/selftest.py` 34.
- **Battery.**  5,079 cases (`scratchpad/battery/mutate7.py`).  Last parallel.py FULL run after
  M7.99a/b/c: 5,079 / 5,079 KILLED (350.9 min).  Known cases: B9 x2 + M7.69 BROKEN-MUTANT, M7.13
  three FAILs then a hang.  The first tools/mutants.py full run: see RESTART HERE.  Older run
  history: `docs/archive/next-2026-10-06.md`.
- **TRAPS.**  #288 is the last (#288: an access program with no instructions in it -- split where the machine does; #285: making a term exact removed the last row that drove a sibling ledger field -- run the full battery; #284: a ledger field stored before its last term is added; #283: a hand check sums the derivation, the table encodes it again; #281: a seed recorder writes the ROM down and romscan cannot see it;
  #282: a scripted play-through is chaotic in the main loop's pass count; #280: a drive indexed by ISRs is
  indexed by frames only until an ISR overruns; #278: an opcode read as state bypasses the read recorder;
  #279: a cost term measured on unseeded state hides the branch that state drives).

## Next, in order

(Items 0..3b are DONE; their notes are in `docs/archive/next-2026-10-06.md`.)
4. **Found in M7.64 (the RING part DONE in M7.109 -- see RESTART HERE; the paint and the world remain):** the title's attributes after the LOAD are not compared frame
   for frame (the ring's stars at a contended mean of iterations a frame -- BB_TITLE's declared layer);
   and the game world after the hand-over is still the round-1 capture's (`bootFromCapture`), with the
   chosen key table laid in -- the tape's own post-cold-start world is not modelled.
5. **Only when the owner asks:** controllers (`padKempston` ON, a gamepad layer) -- the modern layer.

## How to work (the checks cost no tokens)

- **Build and test:** `python tools/build.py`, then the three suites above.  The built page
  is what's tested.
- **Oracles:** `python tools/<name>.py verify` must say MATCH -- for example `beeper`,
  `ctrlselect`, `hurryblock --jobs 12`, `projectile`, `bannertime --jobs 12`, `blowcost --jobs 20`
  (~10 s), `corpsecost --jobs 8`, `mgrcost --jobs 20`.
- **ROM rule:** `python tools/romscan.py` must exit 0, AND it cannot see ROM bytes hex-encoded in a
  fixture's seed (TRAPS #281) -- RF1 in bb.test.js is that gate.  Never write ROM bytes anywhere.
  Remove any quote by pattern, in place (TRAPS #229).  Never execute or disassemble
  `$D000..$D2FF` (the 128K music driver).
- **Disassembly:** `python tools/adis.py 0xADDR COUNT` (from the image); `python tools/grepbytes.py
  "A2 A5"` finds byte patterns (a hit inside an instruction is UNCONFIRMED -- disassemble around it).
- **Battery:**
  - The case list is `scratchpad/battery/mutate7.py` (gitignored).  Append each increment's
    mutants as literal tuples `(file, label, old, new)` before the list's closing `]`; `\n` in an
    anchor matches a CRLF line.  Write the appending script with the Write tool (TRAPS #192 -- a bash
    heredoc mangled `\n` again in M7.74).
  - Then run `python scratchpad/m735_anchors.py`.  It must report 0 dead and 0 ambiguous;
    re-aim any dead cases on the new code (every engine edit that rewrites a line kills old anchors).
  - **OWNER'S RULE (2026-10-02): the battery ALWAYS runs on `--jobs 20` -- subsets and full runs alike,
    never 30 or 32.**
  - **The runner is `tools/mutants.py`** (the kit's; manual 6.12; config in `port.json` "mutants").
    It reads `mutate7.py`'s `MUTS` as DATA (never executed): keep it a literal list, labels unique.
    Each case runs in a private worker tree (`scratch/mutants/w*`) against only the `bb.test.js`
    blocks its anchor reaches, killing block first, stopping at the first FAIL; a survivor is re-run
    against the WHOLE suite (a MISS if only that kills it).  State: `build/mutants/` (prep.json,
    last.json, run.log, summary.txt), gitignored.  **Always `--jobs 20`** (owner's rule).
  - After an increment: `python tools/mutants.py --affected --jobs 20` (new cases, changed anchors,
    changed killing blocks, every dead anchor).  One increment's cases while writing them:
    `--match "TEXT"` (`||` = or).
  - A FULL run (`python tools/mutants.py --jobs 20` via the Start-Process line in RESTART HERE --
    `--background` breaks the pool on this machine) at each
    milestone, after any change to `test/rig.js`, `tools/build.py` or the runner, and before a
    release.  Its one-line result lands in `build/mutants/summary.txt`, the log in
    `build/mutants/run.log` -- do not wait on it or poll it; write the PID into next.md and end the
    stage.  Afterwards `python scratchpad/compare_mutants.py [REF.json]` diffs last.json against a
    reference run (default `scratchpad/battery/full_m799_cases.json`, the last parallel.py run).
  - Say in each commit which kind of run it was, with its summary line.
  - If a run dies, delete `scratch/mutants/.running` by hand (probing the old PID on Windows would
    kill it).  NEVER edit game.js or bb.test.js while a run is preparing (workers copy at start).
  - Every gate block must pass on its own (all do since `c2f6a19`).  A block that drives the page's one game
    object calls `PAGE_RUN.loaded()` / `.played()` first and takes its frames from `PAGE_RUN.clock()`.
  - `scratchpad/battery/parallel.py` is RETIRED (kept for reference; its old instructions are in
    `docs/archive/next-2026-10-06.md`).
  - A SURVIVOR is a gap in a gate, not in the mutant: M7.74's three were an expectation taken from the
    engine's own constant (TRAPS #239), a ledger field hidden in a sum, and a branch no gate row reached.
- **Gotchas:**
  - **Python on this machine defaults to cp1252**: every `open()` of a text file passes
    `encoding='utf-8'` (TRAPS #252).
  - Edits to CRLF files: write a spec `PAIRS = [(old, new), ...]` with the Write tool, then
    `python scratchpad/crlf_apply.py TARGET SPEC.py` (reads bytes, normalises to `\n`, asserts each old
    occurs once, writes the file's endings back, prints the counts).  Copy `old` text from a fresh
    `sed -n` of the file -- comment line breaks are rarely where you remember them.
  - **Before creating a tool or a fixture, list the directory for its name** (TRAPS #231).
  - Repo text files are CRLF (template.html and port.json are LF).  The Write tool writes LF.
  - **Never `sed -i` a CRLF file** (TRAPS #233).
  - A row's EXPECTATION must come from the fixture or the Z80, never from the engine constant it
    tests (TRAPS #239); assert exact counts, not `>= 1` (#240).
  - Comparing natural runs: seed the port from each run's own entry state (TRAPS #237).
  - A new failing row: check the row first (TRAPS #216).  A scripted play-through that changes outcome
    after an exact cost change: check across script phases before calling it a regression (#282).
  - To bisect a behaviour change: `git show HEAD:web/game.js > web/game.js`, build, run a scratch
    probe, then restore the saved copy and rebuild -- a per-frame dump of `$FD80..$FF5F` plus
    `tcost` / `isr_t` names the first differing frame (M7.74's PK8 diagnosis took three runs).
  - Name agents' scratch dirs by content, never by increment number.
- **Commits:** scoped.  The message says what was measured and gives the battery result
  and the suite count.  It ends with the attribution lines the session's system reminder
  gives.
