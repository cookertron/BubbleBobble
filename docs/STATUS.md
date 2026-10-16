# Bubble Bobble (ZX Spectrum, Firebird 1987) — port status

**As of 2026-10-16, after the debug page.**  This is the short read (the table and "Left" below
were refreshed 2026-10-15 at M10.4; the dated paragraphs are newest first).  The long
read is `docs/M7-PROGRESS.md` (5,890 lines, one entry per increment),
`docs/SPEC.md` (the measured behaviour of every routine transliterated so far)
and `docs/TRAPS.md` (364 entries — every way a gate or a measurement has lied to
me, and what stopped it).

**The debug page (2026-10-16)** -- the owner: "a copy of the build but add debug features -- jump to level, trigger bonus
item, kill all enemies, EXTEND, that sort of thing", to test every aspect of the port.  `python tools/build_debug.py`
writes `web/bubble_bobble_debug.html` (git-ignored: tape-derived): the built faithful page plus `web/debug.js`, a panel
(speed: freeze / one frame / 1/4x..8x; rounds 1..81; clear round, kill all, burst bubbles; power-ups 0..15; food 0..15;
EXTEND letters; +1 life, infinite lives, invincible; HURRY UP, Baron, the boss's HP) and `__PORT__.debug`.  Every action
is the game's own mechanism entered where play reaches it, between two frames, queued while anything of the engine is in
flight: a jump arms the round `$97F8` builds (`$8609` one short; the build counters `$82D7` / `$83EC` stepped by the
builds skipped, so round N has a straight run's colours and tiles; the 20/40/60 warp held off; round 1 from a round on the
means' clock, r1Clock being the title path's replay), a kill is `$8BC2` (the storm's) and the storm's burst, an item is
`$89FB`'s placement at the round's own spawn point, a letter is `$B7E5`'s leavings, invincible is the respawn's
invulnerability held, a clear skips only the wait (the timer's parity kept).  THE BOUNDARY: the faithful page never
carries the layer (the build reads the faithful page back off the debug page byte for byte), and with no action the debug
page's game IS the faithful page's (the same 64K after the real load's 700-frame drive).  FOUND, the game's own: the blue
bottle's bit is the collect lock (`$87E2`); on round 81 the potion is taken at once and its drain ends the room.  FOUND,
pre-existing (the owner's call): the built page declares no charset and no doctype (over http, windows-1252 in quirks
mode).  test/debug.test.js **40/40** (~7 min; T1 jumps to every round); tools/debug_mutants.py: **29 of 29
mutants killed**, the control whole.  No file the battery covers changed: no battery due.  bb 1,980/1,980, kit 132, romscan clean.

**M10.4 (2026-10-15): the release docs and the FULL battery** (M10-PLAN "M10.4").  README: the 128K machine as a
declared layer -- the 48K's clock against the 128K's own (M10-PLAN 1.7), the probe's forced answer, the AY's output model
and `AY_MIX`, no ULA snow -- and Alt+M; a "Playing" section (the control select, the page's Alt keys, `sound.info()`);
the scope rows the measurements corrected (81 round layouts and no ending sequence; no attract mode, one high score with
no table); the first plan's "no dropped frames" departure rewritten as the timing model it became (the machine drops no
video frame, the port's slowdown is the machine's, the gaps left DECLARED in TIMING); the `LD A,R` substitute (RNG);
build and test.  This file's table and "Left" refreshed (stale since 2026-10-08).  tools/mutants.py: `prepare`,
`cover` and its `git` helper decode their output as UTF-8 (`errors='replace'`) -- Python's default here is cp1252,
which fails on bytes the suite's UTF-8 output can hold, and a `git diff` it could not decode fell back to selecting
every case of that file.  The FULL battery (the runner changed) 2026-10-15 13:54..14:33: LISTED 7,039 KILLED 7,035, **0 survivors, 0 dead anchors, 0 misses** (TIMEOUT 1 / BROKEN 3: the known M7.110 cursor guard, B9 x2, M7.69), 38.0 min on 20 workers.  It reused its cached
preparation -- by design the cache leaves the runner out -- so the new decoding was proven by a direct check: the old
call on output holding U+2550 kills subprocess's reader thread and leaves the output None (cover's `print(r.stdout.strip())`
would crash); the new call returns the text.  Still PROVISIONAL: `AY_MIX` 1.0 -- the owner's listening test sets it.
bb 1,980, kit 132, selftest 38.

**M10.3 (2026-10-15): the page and the platform** (SPEC "M10 -- the 128K branch", "The page and the platform").  The page
now boots the **128K** (the owner's decision: the AY music, with the 128K version's own flow; `BB_PAGE.m128`, OFF the 48K page
as before) and **Alt+M reboots into the other machine** -- `bbBoot()`, the page's own boot, a new game from the tape's
hand-over, in any state -- the choice remembered in the browser like the high score (`saveMachine`, ADDED, default ON; any
other stored value refused by name) and the caption naming the machine running.  The sound is ONE stream for both chips:
platform.js's new `'mix'` instrument renders the beeper and the AY into the same chunks on the worklet (the default -- the AY
used to have only the scheduled buffers, the path that crackled) and on the scheduled fallback, each AY write at the sample
its fractional frame falls in, the AY's registers kept through every path that renders nothing, an AY never written not
rendered at all (the 48K page costs nothing), `reset()` for a reboot, `info()` naming both chips.  DECLARED / PROVISIONAL:
the AY's level against the beeper's (`AY_MIX` 1.0) is analogue -- the owner's listening test sets it (`sound.ayMix = x`
live).  GATES: kit.test.js "THE MIX" (11, game-agnostic: each transport the one-shot render of both chips, built in the test;
placement on a non-zero origin; every state-keeping path; reset(); info()); bb.test.js G1..G7 (bbMachine against the rig's
real store; this suite's page pinned to the 48K by seeding the store before the load, so every page row reads the page it
was written for; FRESH pages in child processes for the 128K default, a remembered 48K, a refused value, Alt+M twice and a
reload; the 128K's AY through the page's real loop by real keys; and the 128K engine's two logs through the mix in-process,
the one-shot render on both transports; a reboot after play the fresh page's boot, compared across processes; G0, the kit's own suite run against the page, so the battery's cases on the mix meet the kit's checks).  FOUND while listing the mutants, before any ran: the exactness checks ran at the
default mix of 1 and on maps originated at frame 0, so a dropped gain or a dropped origin was invisible to them -- they now
run at 0.6 and from frame 5 (TRAPS #361); a suite with one page can test one boot -- the in-process page is shared state, so
other boots run in child processes (TRAPS #362); run the battery's way, 15 of the 30 platform cases lived through this suite -- the kit's suite killed them, which the battery never runs (TRAPS #363: G0).  The Sonnet review's one finding, fixed: a reboot left the speaker high, so its step came at the new machine's first edge, seconds later (TRAPS #364).  bb 1,980, kit 132, selftest 38.  Battery: +60 cases, 11 page cases re-aimed onto the lines M10.3 rewrote -- 7,039 cases (6,840 game.js, 152 page, 28 platform, 19 suite: the "6,840" of the notes since M10.2b counted game.js only); hand battery 82 cases all killed but one EQUIVALENT (game.m128 set after ctrlBoot), 21 of them kit-only (kept out of the list: no block runs their lines in the suite's process); the --affected run 949 / 949 killed, 0 survivors, 0 dead anchors, 0 timeouts, 8 MISSES (72.0 min on 20 workers) -- the selection's holes, closed by G9 (their `--match` run on the twelve cases on those lines: LISTED 12 KILLED 12, 0 survivors, 0 misses, 41.4 min).

**M10.2d (2026-10-15): the 128K branch's pause** (SPEC "M10 -- the 128K branch", "The pause").  Under `m128` the pause
now requests 0 in its arm -- `$8FF3`'s mute, with the interrupts on: a DI window whose RET's end is the arm's last
acceptance point -- and its release re-requests the saved sound with the interrupts off (`$9006`), restarting it, its
EI / RET ending the spin's window an instruction before the 48K's.  MEASURED first: a new oracle, tools/pause128.py --
pausespin's runs on the M10 machine, 414 runs (natural arms at 68 phases, FORCED arms and releases at every edge), and two
whole-pause scenes on the real load.  GATES: Q1..Q6 -- the machine's edges; all 414 runs replayed through spinStep from the
machine's `$8FE7`, exact (both requests, the mute, the windows, every poll, every acceptance phase); the scenes through
step() the machine's to the arm, quiet while held, the unpause to the T, the restarted theme's first tick; the flow's own
pause requests at their T; OFF unchanged, the refusal, the edges; the arm meeting the interrupt through step() at the
machine's three phases.  FOUND: a pass with CAPS held and SPACE up runs `$8D6A..$8D6F`, 22 T more, which the 48K's pass
skeleton never charged -- the release always holds CAPS, so the scenes are pinned after it (TRAPS #357, DECLARED: the
timing campaign is stopped); a forced run whose natural instruction pre-empts
the forcing repeats the natural run silently -- the oracle now asserts it (#358); a gate's offset between two events holds
only where no interrupt falls between (#359); the hand battery's one survivor showed the replay gate blind to its own clock
-- Q6 drives the arm through step() (#360).  bb 1,970, kit 121, selftest 38.  Battery: +49 cases (6,840); hand battery 49 / 49 after one gate gap closed (Q6); the --affected run 863 / 863 killed, 0 survivors, 0 timeouts (41.0 min on 20 workers).

**M10.2c2 (2026-10-14): the 128K branch's sound calls in play** (SPEC "M10 -- the 128K branch", "The sound calls in
play").  Under `m128` the heart now requests 4 inside the item pass (`heartReq`); the potion's and EXTEND's blocks stop at
each sound call on their exact clock and the main line runs the sound code there (`lzStopAt` / `lzHit` / `lzOn128`): the
potion's `$891A` request 3 and its fill's `$8991` wait for 3's pass (82 interrupts, the treasure room standing still) and
request 4, EXTEND's `$94D5` request 2 and `$953C` wait for 2's pass (182) and request 3; requests made with the interrupts
off run whole and carry the caller's DI window to their RET.  The boss defeat is a program on step()'s ledger
(`bossDeath128`): `$8E77`, the banner, the `$8E8A` wait, two delays, the `$8E95` wait and request 2, whose A $10 / B $7F make
`$8E98`'s delay 45,069 T longer than the 48K's.  GATES: D1..D6 -- the potion the machine's record for record (frames
838..929, every interrupt, tick, hook, OUT and AY write), EXTEND the same but 14 acceptance phases (the lazy block's 4,
the 48K's own), the heart's request to the T, the boss defeat's waits and delays ending in the machine's frames (`$8E77`
at the port's T, pinned), the interrupts-off requests at their machine T, the stop unit by unit, OFF unchanged and every
new site refused by name.  FOUND: the boss's first cut double-charged its banner -- the pass was a clear pass charging
`$8E3A` whole (TRAPS #356); the battery's one timeout, a wait entered with the interrupts off, now refused.  The unpause's
`$9006` moved to M10.2d with the pause.  bb 1,964, kit 121, selftest 38.  Battery: +110 cases, 7 re-aimed (6,791); hand
battery 113 / 113 after three gate gaps closed; the --affected run 802 / 803 killed, 0 survivors, 1 timeout (closed, its
its re-run with the new refusal's case: 9 / 9 killed, 39.7 min).

**M10.2c (2026-10-14): the 128K branch's requests and waits on the main line** (SPEC "M10 -- the 128K branch", "The
requests and waits on the main line").  Under `m128` the main line now calls the sound code the 48K patched to RETs, an
instruction at a time on step()'s ledger (`mwIns`): the release's `$97B4` request 7, round 1's `$98F5` wait for the
game-start tune's pass (221 frames of interrupts -- the player walks, the enemies stand, the round's timers run) and its
request 1, every later round's `$98FC` request 1 and round 80's `$9901` 6, game over's `$8CE4` 5.  A request's DI window
loses the interrupt at a boundary 1..516 T inside it.  FOUND on the way: round 1's build was replayed with the 48K's
interrupt T although every interrupt under m128 carries the hook (TRAPS #353) -- the replay now plans each hook on a
copy of the engine; the oracle's forced DI-window rows outside the request are its own (#354); a free-running comparison
needs the R stand-in fed (#355).  GATES: C1..C8 -- p1, p2, skip and idle free-running: every request, wait (its turns)
and mark the machine's, and every interrupt, hook, tick, OUT, AY write and pass from `$970E` to each scene's pinned
parting in play (the 48K port's play timing past its own verified window; round 1's build's acceptance phases DECLARED);
the DI window at 163 offsets; all 18 interrupts-on requests of the oracle re-made at their T; rounds 10 and 80.  The one
Sonnet review found three hygiene defects in the game-over and plan paths, fixed and gated.  Next M10.2c2: the in-play
sites with the interrupts off and the waits inside play blocks.  bb 1,958, kit 121, selftest 38.  Battery: +142 cases, 17
re-aimed (6,681); the --affected run 689 / 689 killed, 0 survivors (41.4 min on 20 workers).

**M10.2b (2026-10-14): the 128K branch's sound hook in the game's interrupt** (SPEC "M10 -- the 128K branch", "The sound
hook in the game's interrupt").  Under `m128` every frame interrupt now ends as the machine's does, with `$8D8F CALL $8DC4`
after its passes, on its own wall clock (`isrHook`: after the acceptance phase and the waits so far): the theme's cadence
(`$8DE0`, two interrupts in three; every one under the HURRY UP latch or past the round's 768th frame with seven
enemies alive), the engine's tick between two `OUT ($7FFD)`s whose I/O cycles join the ISR's access program, the busy
byte -- every path's T from its instructions.  The AY writes land in the frame the interrupt begins, at the machine's
T; the late interrupt at `$970E` hooks in its own frame.  The title is no longer silent: sound 5 plays from `$970E`.
FOUND on the way: the front end's interrupts were accepted at a provisional 4 T -- invisible on the 48K, wrong at 19 of
the title's 21 interrupts for the hook's AY writes; frontFrame now keeps the end of its last instruction (the 48K's
isracc agrees on all ten title and release interrupts; TRAPS #351).  The flow oracle gained `hooks` rows, the hook's
inputs where it reads them -- a boundary sample missed one ISR whose passes clear the HURRY latch before the hook
(TRAPS #350).  GATES: B1..B5 -- the title record for record from `$970E` to request 7 (p1: 21 interrupts, 34 AY
writes; the skip scene; the skip as it ships); soundHook over all 10,543 hooked interrupts of the oracle's nine scenes;
the hook inside play interrupts of the 48K's real load switched to m128 for one interrupt (odd, even, a skip -- the
cost, `isrD` and `isrPlain` each, the program: TRAPS #352); OFF never hooks; the late interrupt.  H4 / H5 now compare
the hooks' inputs and run through the title's first interrupt.  After '1' the title's 5 plays on until M10.2c (the
request sites and waits in play).  bb 1,950, kit 121, selftest 38.

**M10.2a (2026-10-13): the 128K branch's cold start and hand-over, modelled** (SPEC "M10 -- the 128K branch", "The cold
start and the hand-over in the engine").  BB_Game's `m128` (default OFF in the engine; the page boots the 128K since M10.3) makes the machine
M10's -- the 128K branch on the 48K clock: `reset()` lays the 128K load's 14 bytes and the hooks' operands, the front end
repeats keys at the 128K load's REPPER (2), the probe's count is forced to the 128K's (`$80`), the skip (ADDED) waits for
the probe's own hand-over phase (at 19 of 64 others the cold start's jingle is never heard), and `coldStart`'s 128K leg is
modelled at last (it threw, by name): the display writes, the engine over bank 1, its T by phase from a new access
program (`tools/cold128.py`, the machine's T at 480 phases).  At `$8CCA` the world swaps and the rest runs instruction by
instruction -- request 3, the `$9575` delay with the request's registers (3,967 DJNZ), the `$8CD7` wait for the jingle's
end (81 frames), request 5, the reset half -- with the game's interrupt and its sound hook ticking the engine, every AY
write logged at its OUT's T.  GATES: H1..H7 -- exact on the first run against the flow oracle: p1, p2 and idle record for
record (82 interrupts, 82 ticks, 88 AY writes, 170 OUT ($7FFD)s, the wait's 241,825 turns, the frames' sound state);
the skip at its natural phase and as it ships; the skip at 64 phases (the wait's busy byte and turns); a taken request's
DI window at 179 offsets; the not-taken request; REPPER over 4,203 scans; the boundary (OFF is the 48K machine).  Hand
battery, 169 cases (168 new, M7.40's case on the old throw re-aimed): 167 killed by the M10.2a blocks alone, the other two
left for M7.40 (h) and H-d(f); two more found equivalent and left out (TRAPS #347), one gate gap fixed (the wait's busy
byte: the flow's skip sweep now records it and the turns).  bb 1,945, kit 121, selftest 38.

**M10.1 (2026-10-13): the AY engine in JS, not wired yet** (SPEC "M10 -- the 128K branch", "The engine in JS").  The
128K branch's music engine -- bank 1's `$CF80..$D1E1` -- transliterated instruction for instruction as `BB_Ay` over its
own 16K, its state in its own operand bytes, so its history carries over as the machine's does.  `request(n)` and
`tick()` return each AY write with the T of its `OUT ($BFFD)` from the entry, the returned A and the uncontended T.  Its
3,860 bytes ship as `aybytes` (build/ay_engine.json, `tools/extract_ayengine.py`, asserted equal to the bank the game's
own leg lays).  A never-requested engine's ROM fetch (tick 256) is a COUNTED REFUSAL, undone store by store (TRAPS #344).
GATES: AE1..AE7 -- the bytes are the machine's bank; all 13 oracle streams event for event (47,338 events, 101,905
writes); every stream's end state; the refusal; the boundary (29 state bytes written, nothing else); bank 1's edges
driven; the request's eight-bit A.  Exact on the first run.  Hand battery 143/143 before the battery; the --affected
battery (143 new, 140 on the anchor lines around them): LISTED 283 KILLED 283, 0 survivors, 0 dead anchors (34.6 min on
20 workers).  bb 1,938, kit 121, selftest 38.

**M9.2 (2026-10-13): the page's Alt keys -- Alt+P toggles the pause, Alt+Q quits** (the owner, 2026-10-13: the page's
key combos are Alt+, as Alt+Enter is; ADDED, `BB_PAGE.altKeys`, default ON).  The game's own keys are SYMBOL SHIFT (the
pause, `$8FE7`), CAPS SHIFT (the resume, the spin `$8FFB`) and CAPS SHIFT + SPACE (BREAK, the main loop's second exit
`$8D63` / `$8D6F`) -- PC Ctrl, Shift and Shift+Space through the kit's keymap.  ON, in the game's world the page hands
the engine a VIEW of its Keyboard (`bbAltKeys`' kb(): port() and both Kempston bytes) in which CAPS and SYMBOL SHIFT
read up; Alt+P holds SYMBOL SHIFT (playing) or CAPS SHIFT with SPACE up (paused) until the game has paused or resumed
itself, Alt+Q holds CAPS SHIFT and SPACE until the game has BREAKed -- only in play (the title and the game-over
screen count and ignore them), each hold let go after `BB_ALT.HOLD` = 300 frames if the game cannot take it (past
round 1's 221-frame wait on M10).  The control select keeps the Keyboard (its menus read SYMBOL SHIFT codes); the
combos never press P or Q (the listener runs before attachKeyboard's, with fullscreen's).  OFF is the machine's keymap.
GATES: AK1..AK9 (the boundary; the view equal to the Keyboard less CAPS / SYM over 10,240 reads; on a real load: Ctrl
and Shift+Space do nothing, Alt+P pauses through `$8FE7` and resumes through the spin in one frame, Alt+Q BREAKs from
play and from the pause, OFF Ctrl / Shift / Shift+Space as on the machine; the title and the game-over screen; the
hold's rules; the page's own listener, loop and caption).  Hand battery 45/45 before the battery; the --affected
battery (45 new, 6 re-aimed onto the rewritten lines, 89 more on the lines around them): LISTED 140 KILLED 140, 0
survivors, 0 dead anchors (44.3 min on 20 workers).  bb 1,931, kit 121.

**M10.0 (2026-10-13): the 128K branch's oracles** (the plan: docs/M10-PLAN.md; the reference: SPEC "M10 -- the 128K
branch").  Tools only, no engine change:
- THE TWO MACHINES (M10.0a; upstreamed, kit commit `3e81ac1`, kit selftest 38): `Harness(paging=$10)`, the 48K harness
  with the 128K's `$7FFD` port and an AY -- M10's machine, the 128K branch on the 48K clock -- and `tools/harness128.py`,
  the 128K itself (SkoolKit's contended 128K simulator, the C engine proven identical, an exact HALT skip, hooks).
- THE ENGINE, DIRECT (M10.0b, `tools/ayengine.py`): `$D167` and `$CF80` called from a fresh bank 1 that the game's own
  cold-start leg laid -- sounds 0..7 for 3,000 ticks each, the no-request case, agent D's seeded chains -- every AY write
  with its T, each call's A and uncontended T; identical on the 128K machine (bank 1, writes, A).  A stream stops at the
  engine's first read of the ROM (TRAPS #341).
- THE FLOW, ON THE PORT'S CLOCK (M10.0c, `tools/ay128flow.py`): the real load on M10's machine (the 128K load's 14 bytes
  laid, the probe's count forced to the 128K's), nine scenes from the cold start to round 81 -- every request, wait,
  tick and AY write, every ISR with its hook's T, every pass, LD A,R draw and speaker edge.  MEASURED there: the waits
  (the cold start 81 frames, round 1 223), the 2-in-3 theme, the hook's ~464 T an ISR; a taken request's DI window
  (lost 1..516 T in); and the page's skipProbe, which at 19 of 64 hand-over phases skips the cold start's wait -- the
  probe's own phase (1,051) waits, so M10.2's skip must hand over there.  REPPER is 2 on the 128K load (the 48K's 5):
  the front end's key repeat.
- The fixtures wait in `build/pending/` until the gates that read them (M10.1, M10.2) land (TRAPS #342).  Suites: bb
  1,922, kit 121, selftest 38.  No battery (nothing in the page or its tests changed).

**M9.1 (2026-10-12): the saved high score and fullscreen -- the wrap-up's first two ADDED layers** (the owner's decisions
of 2026-09-08, built after the timing campaign stopped):
- THE SAVED HIGH SCORE (`BB_PAGE.saveHiScore`, ADDED, default ON).  The machine has ONE high score, `$FFE1..$FFE4` (BCD, LSB
  first), set only by the cold start (`$9688`'s clear, `$9692`: 20,000) and raised only by `$80FA`'s copy.  The page reads
  `settingsStore('bb-hiscores')` once at boot; a value of exactly eight decimal digits goes to the engine (`hiSeed`), which
  lays it over `$9692`'s at the hand-over (`BB_Game.hiRestore`, right after `coldStart()` in `reset()`) -- so the title and
  every HUD read it as they read the default.  Any other value is REFUSED and said so (`hiscore.info().refused`).  After the
  hand-over the page's loop reads the four bytes each step: the first read is the baseline, and a later change that beats
  the store (re-read each time, so another tab's better score stands) is saved.  OFF -- and ON with nothing stored -- is the
  machine: the store untouched, the whole 64K the bare game's at the title on the same script (HS6, HS7).  A store that
  throws (file:// with site data blocked) reads as empty and its failed saves are counted, never raised.
- FULLSCREEN (ADDED page furniture).  Alt+Enter puts `#overscan` -- the border and the screen -- on the whole screen (the
  Fullscreen API, WebKit's prefixed one too), or over the window where the browser has none or refuses (counted); Escape,
  or Alt+Enter again, brings the page back, and a fullscreen the browser ends itself is followed at the next draw.  The
  screen is the largest whole number of DEVICE pixels a Spectrum pixel that leaves the page's own border round it
  (`bbFullFit`: 5x at 1920x1080, 5x in device pixels at 1536x864 x1.25).  Its key listener runs before attachKeyboard's
  and stops Alt+Enter there: the Spectrum's ENTER is never pressed by it.  Both key captions name it.
- The rig's `fire()` now stops at `stopImmediatePropagation()` as a browser does: before, a page that forgot the stop
  passed the same rows (TRAPS #340; upstreamed, kit commit `c32f351` -- kit.test.js +1).
- GATES: HS1..HS10 (the engine's boundary, the refusals, the real load restoring it and round 1's HUD showing it, saves
  read back from the rig's REAL localStorage -- TRAPS #17 --, the baseline, OFF, a throwing store, the page's own loop
  saving), FS1..FS12 (the fit, the page's own listeners, the API's paths, the captions).  Not gated: the fullscreen CSS
  (the rig has no layout) -- for the owner's playtest to check in a browser.  bb 1,922, kit 121.

**M7.115m (2026-10-12):** the even ISR's last accesses on its program.  M7.114c put each ISR's own contention on its access
program, but the bubble manager `$B62C` made more contended accesses there than it carried:
- the pop `$B6D8` (the held arm, the age's `CALL m`, the blow's steal): its erase (80 screen accesses), its seed of the
  sparkle table at `$5CE0`, a paid pop's award (each drawn digit's eight glyph stores into the HUD) between its two
  OUT (`$FE`)s, a class-1 pop's corpse birth on a live enemy;
- the escape's and the push's erases;
- the blow's bonus award.
None of them was on the ISR's program: SK3's ISR 804 was 83 accesses and 5 T short.
MEASURED with tools/popacc.py:
- 48 saved states, 600 frames of random keys: 13,296 even ISRs, 279 kept (167 held pops, 26 age pops -- 74 paid --, 105
  pushes, 4 escapes), each replayed plain from `$B62C`'s entry with its seed, its R draws and the ISR's acceptance phase;
- 54 forced calls for the paths play did not reach (the steal, the bonus, every class and the corpse birth's arms, the
  cancel's edges, the full table, the digits drawn, player 2, two events in one pass...), built on the even ISR's real
  stack (TRAPS #335).
Now each entry sits on the slot clock (BB_ISR_PO: the Zilog sums), and every access is on the program where the machine
makes it.  All 330 calls are the machine's through the engine -- program, T, writes, every entry's offset.  Replayed from
the machine's acceptance phase, every natural call waits the machine's D (EV4: 276, the old rule wrong on 129).  SK3's
ISR 804 is exact; PK7's synthetic-phase median moves 49 -> -40.  DECLARED: a chain window parked in the ROM (3 natural
calls: the port ships no ROM).  TRAPS #335..#339.  bb 1,900.

**M7.115l (2026-10-12):** Boris's erase (`$915F`) on the pass's program, and its DI window on the frame clock.  With its
request up (the respawn, the clear) `$915F` restores the pixels under Boris's record through `$A314` -- 32 screen stores --
between `$9163 DI` and `$917A EI`.  The stores were not on the program, the restore's keys were not on the grid, and the
engine had no window: it ran an interrupt that fell inside at the next callee's entry.
MEASURED with tools/borisacc.py:
- 48 states with random keys: 23 natural requests, replayed;
- 15 forced runs (every Y & 7, the screen's edges, rows aimed at the ROM);
- 84 phased runs (Boris under P1 with the odd ISR next, Y & 7 = 3, the even ISR next).
On the machine a point at or before the DI's first T is taken there (the ISR then INCs the hurry timer the call clears); from
1 T into the DI to 32 T before the RET's end it is LOST; in the last 31 T it is taken at the RET's end.
Now the request path's keys are in the machine's order, the erase's stores are at the cursor, there is a site at the DI,
the window rides the frame clock (intLost), and gridPh takes a pulse that outlasts any DI window at its end.  Through
step(), a frame whose point falls inside the erase loses its ISR (BK6).  IA3's fruit world now runs past the erase to frame
1128 (3,343 passes): there the R stand-in draws the walker's 1/128 hesitation (`$B0D5`, `$2A`) and the machine's R does not
(MEASURED: fed the machine's draws, ISR 1128 is the machine's).  TRAPS #330..#334.  bb 1,895.

**M7.115k (2026-10-12):** `$C002`, the burst-sparkle walk, on the pass's program and its grid.  A live particle restores
the pixels under it (`$A314`: 32 screen stores) or ORs its sprite in (`$A2D5`: 32 OR reads of the screen and 32 stores).
None of those accesses were on the program, the live slot's keys were not on the grid, and the walk ran whole before the
ISR.  The census had 12 straddles that read the screen the ISR had drawn on, or the slot its pop had seeded, and 5 whose
ISR, run late, read the walk's later bytes.
MEASURED with tools/sparkacc.py:
- the real load with the table laid every 4th ISR, free-running to frame 1300 with the screen at every ISR's end;
- 48 states with random keys;
- 236 replays, 6 forced runs, and 76 phased runs (P1 over the particles, and a held bubble popping over them);
- straddle.py's 83 `$C002` rows.
Now the live slot's keys are in the machine's order, its kids' accesses are at the cursor, and there is a site before each
read of what the ISR writes (the table, the screen it ORs) and each store it reads (the screen, the write-back).
Free-running, the sparkle world is the machine's pass for pass to frame 971, and its screen at all 703 ISR ends (SK3).  IA3's
fruit world now runs past its first sparkle to 970.
Found on the way, each its own next increment (MEASURED, pinned):
- the pop's accesses in the even ISR;
- the lives panel drawn inside the odd ISR;
- Boris's erase (`$915F`) off the pass's program.
TRAPS #325..#329.  bb 1,889.

**M7.115j (2026-10-12):** the boss tick `$A9ED` on the pass's program and its grid.  A body (every 32nd tick) blits --
the erase's 128 LDIs and 16 attribute stores, the draw's 128 LDIs and 16 LDDs -- 832 contended accesses that were not on the
program, and its keys were summed out of the machine's order, so the cursor was lost and an interrupt inside a body ran
after the whole tick (the census: 4 straddles read P1's Y / X before the ISR moved him, 10 ISRs drew their sprites on screen
bytes the blits write after them).  MEASURED (tools/bossacc.py: the real load to the boss round free-running to frame 1700
with the screen at every ISR's end, six boss-round states, 247 replays, 48 forced, 84 phased runs at both ISR parities;
straddle.py's $A9ED rows): every block move's and attribute store's accesses, the keys in the machine's order, a site before
every store and every read of what the ISR writes.  Free-running, the boss round is the machine's to frame 1700 -- all 6,702
passes, all 703 ISRs, and the screen at every ISR's end (BA3); the boss's frames drift 0 (TB3).  Found on the way: `$AA30` read
P1's flags whoever the boss matched (now the matched player's), and P2's hit had no grid (`A978t`).  TRAPS #321..#324.
bb 1,882.

**M7.115i (2026-10-11):** `$7E80`, the element emitter, on the pass's program.  Its code is contended RAM, and on a round
with an element (49 of the 81, the boss's among them) every pass runs its long path `$7E85..$7E9D` -- of which the engine put
nothing on the program: each such pass ran 0..87 T short, the boss 4 frames ahead by frame 1400.  And its HALT (`$7EC2 EI /
HALT`, in the frame ($8DBD) = $2A) gave the frame away from wherever it began, the re-test that asks whether the ISR took the
slot running BEFORE that ISR.  MEASURED (tools/emitacc.py: five rounds of the real load free-running to frame 1700, eighteen
saved states, and 40 phased runs that put the interrupt on each edge to the T): every key's accesses (BB_SM_ACC), the HALT's
contended steps (locked to the ULA in the screen fetch: taken at phase 1), and the late case (an interrupt before the HALT:
it waits a whole frame).  The HALT is a block now -- the pass to it spent, its steps walked to the interrupt, the re-test and
the chain after the ISR.  Free-running, rounds 25 / 17 / 3 are the machine's pass for pass to frame 1700 (EA3); LRF2 holds to
its worlds' ends; the boss's bodies drift 2 frames, not 4 (TB3: its own draws, M7.115j).  Found on the way: an enemy above
the HUD probes the dummy page `$712F` in contended RAM -- 8 accesses off the odd ISR's program (r10's 24 T at frame 1472:
next).  TRAPS #318..#320.  bb 1,875.

**2026-10-11, the owner's boss bug and its class:** "the boss doesn't move and hitting it once with a lightning bolt kills
it straight away".  The boss's velocities `$AA47` / `$AA48` are tape bytes ($01 / $01) that nothing in the game sets, and
the page never laid them down: at zero the boss stood at its spawn, and a bolt that hits skips its own physics (`$9F57`
returns past `$9ED0`) -- it dwelt in the accept set and took all 42 HP.  On the machine the boss moves on after a hit.
tools/tapereads.py missed them because the bounce writes them (its rule kept only bytes no run writes); its CENSUS now
compares the page's RAM with the machine's at frame 600 of the real load at all 18,369 addresses any run reads before
writing (TB2: 178 differ, all in 11 declared groups, each with its reason).  It found `$79A2`'s seed `$79A3` too: the boss
setup, now modelled (`LD A,n / RLCA / LD ($79A3),A / LD ($9F62),A`: the HP 10, then 20 on round 81's build, before the
start's 42).  tools/bossfree.py measures the boss on the real load's path: every body's position the machine's (103 of
103; their frames drift up to 4 ahead -- DECLARED, `$7E80`'s long path is not timed), one bolt one hit (42 -> 41), the
kill, round 81 and its seed.  TB1..TB5b; TRAPS #317.  bb 1,866.

**M7.115h (2026-10-11):** the census's next three callees on M7.115g's mechanism -- the jump tone `$8FA5`, the contact
pass `$925A` and the level-clear decision `$8E3A`.  MEASURED (tools/straddle.py's gate rows for them: 277, the 34 the old
rule got wrong among them -- P1's jump byte read after the odd ISR inside the tone stepped it, an enemy's Y in `$9312`'s box
test after the ISR moved it, an enemy the ISR inside the tally killed): each read of what the ISR writes, and each store it
reads (the kill's, which the ISR's P1 handler reads; the gates the one-left anger closes and reopens), is a site at its
instruction, and `$8E3A`'s paths are on the pass's grid (its drain, its countdown, its anger and walk; the clear a mark).
All 277 rows the machine's (SH2), each of the 28 sites exact to the T (SH4).  Found on the way: inside a pass `$8E3A`'s
clock origin was `$8E2A`'s, so the countdown's reads were placed 65 T early (TRAPS #316); and the census's seed left out the
operands `$8E3A` reads as instruction bytes -- without them 32 of its rows replay another path (TRAPS #315).  DECLARED, the
next increments: `$A9ED`'s P1 reads and `$C002`'s blit merge (16 rows), the late ISR's screen bytes (15).  bb 1,859.

**M7.115g (2026-10-10):** the callee an interrupt falls inside.  MEASURED (tools/straddle.py: 52 worlds, every chain call
with one ISR inside it -- 27,087 -- replayed from its entry atomic, the exact cut asserted equal to the machine's call on
every one): where the engine's rule (the callee whole before its ISR) parts from the machine -- 141 calls in 7 callees, 77
of them the treasure room's walk -- and where the ISR, run after the callee's later writes, does (19).  The engine now runs
the frame's ISR INSIDE the callee, at its first read past the point (isrSite / isrHere: the acceptance phase from the grid
so far, nothing of the ISR on the pass's program or grid, no second ISR at the frame's end), with the cursor walking every
pass: the item collide's four player reads and `$931A`'s probe's four.  All 315 gate rows the machine's (SG2), each site
exact to the T (SG4); free-running the potion worlds are the machine's to frame 1448 and the fruit world to 806 (until now
840 / 878 / 644) -- pinned there on the R register's stand-in (the power-up's draw) and the sparkles' blits off the program;
the potion's room to its advance on f700.  DECLARED: the census's other five callees (50 rows), the late ISR's screen
bytes (17).  bb 1,855.

**M7.115f (2026-10-10):** the item pass (`$8669`) on the pass's access program and its instruction grid.  MEASURED
(tools/itemacc.py: the real load with a potion laid at ISR 600 / 700 and eight items laid at ISR 600, seventeen saved states
with items and a two-player world; 82,709 calls, 277 replayed plain from their entry, 45 forced): every contended access of
the item pass -- the ink cells, the blit rows (the sprite's reads; a row into the ROM keeps them), the erase's cells and the
restore's rows, the award's glyph rows, the chirp's OUTs -- and every instruction, in the machine's order.  The engine now
lays the item pass's instructions on the grid with a cursor through them, each access on the program at its place (277 /
277 replays exact, IA2), the handler's `JP (HL)` a cut; the take's award window (`$87F9 DI` .. `$881C EI`) on the frame
clock -- an interrupt there is lost on the machine, and the engine ran it; the chirp's 40 edges at their OUTs' places
(PROVISIONAL since M7.84; now the machine's, IA5); the potion's `$890D` at the machine's frame and phase (until now 142 /
139 T early, IA4) and every pass of the treasure room the machine's from there (IA3).  Two fixes on the way: the resumed
pass after a block that ends inside `$8669` starts after its rest and the CALL, and takes no prefix waits off (TRAPS #311).
DECLARED, pinned (IA3, PT2): from frame 840 / 878 the room's walk reads P1 after the ISR inside it on the machine -- an
atomic callee cannot -- so the dark-window rows differ (4 / 5) and the room advances -1 / 0; the same class in `$931A`'s
probes (TRAPS #312).  bb 1,851.

**2026-10-10, the owner's Boris bug and its class:** Boris was implemented and switched on as the machine's is, but
drew blank -- his 64-byte sprite `$FF50..$FF8F` is tape data the port never laid down (the giant banks' twin, 2026-10-08).
tools/tapereads.py sweeps for the class: 189 runs (every saved state twice for 4,000 frames; r60_48 warped to rounds
1..81), 15,370 bytes the machine reads that no run writes and that hold the tape's value, held against the page's own RAM
in play.  It found four more: the lightning bolt and the fire's two frames (`$A37D..$A3AC` -- the bolts, the boss fight's
too, and the flames drew blank), the giant diamond's award byte `$AAE9` (the +56,000 SPEC recorded in 2026-09: type 0
reads the award table at index -1; the port paid nothing), and round 45's cells below the map (`$FB07..`, `$40` on the
tape, read by the map probes in every round before 45).  build/tape_bytes.json lays the six blocks down at reset().  And
play writes Boris on the machine: `$B7A1`'s chain mark with marker 24 wraps onto `$FF67`, `$E6` -> `$EE`; the engine
does too now.  TR1..TR7: the class against the page's RAM; the blocks; the machine's own Boris draws, bolt blits, fire
burns, diamond award and chain mark, replayed with nothing seeded from the blocks.  TRAPS #310.  bb 1,845.

**M7.115e (2026-10-09):** the potion's T is a block (`BB_EXT_BLOCKS.potion`).  MEASURED (tools/isrcarry.py's potion
sources -- round1_48, r50_48, two-player, round 81 and the real load, 125 runs; tools/potion.py 'fill' -- 17 maps):
`$890D` to its RET is one program, 237,047..244,659 T, with two DI windows (`$890D`..`$891D` EI and `$8C14`'s reveal) and
twenty contended stores (`$A36C` into `$5B00`); the replay with the machine's ISR T exact on all 125, the head window's
close measured both ways (32 T before: lost; 31 T before: taken AT the close).  The engine's block is exact on all 125
(LZ9: acceptances, the 469 lost, the RET, every write) and its fill on all 17 maps (PT3); inside a pass it begins where
the pass clock puts `$890D` (potionPos), the chain waiting after `$8669`.  Free-running (PT2) the dispatch now comes after
ISR F + 1 and the four ISRs are lost as on the machine; DECLARED: `$890D` 142 / 139 T early -- the item pass's own
accesses (the take's erase, award glyphs, chirp OUTs; each pass's item draws) are not on the pass's program -- so the
room advances -1 / 0 frames (was -5 / -4).  PT4: the same on the page's own path (skipProbe on).  bb 1,838.

**M7.115d (2026-10-09):** the potion (type 12, the treasure room) no longer freezes the game -- the owner's bug.  The
engine's fill stopped at its last row and never ran the machine's tail, which opens both ISR gates `$890D` shuts, so
nothing moved but the bubbles; and `$894B CALL $8C14` (RES 7 on every enemy and bubble slot, the repaint) was a named
stub.  MEASURED through play (tools/potion.py): PT1 -- every ISR of the room holds the machine's odd gate, P1's position,
the latch, the round and the bubbles.  DECLARED (PT2): the potion's T (its `$8C14` DI window loses four ISRs on the
machine; the room advances 4..5 frames early).  bb 1,835.

**M7.115c (2026-10-09):** a later round's start FREE-RUNNING is the machine's.  tools/lrfree.py: the real load with
($FECD) poked at the same point in engine and machine (round 2 from five phases of play, rounds 10 / 41 / 2-3-4 / 81 and
the wrap, and two pokes at a pass that meets the interrupt before `$97F8`), nothing given.  It found three things the
replay with the machine's ISR T could not: the odd ISR's draw reads type 0's facing-1 sprite from `$5B80`, contended (16
S templates from isracc, `ipSrc`) -- every odd ISR from the tail on had been 89..162 T short; the build's clock began at
the advance pass's `$8D0C`, 96 T before `$97F8` -- hidden by the HALT's 4-T grid except where the gap was not a multiple
of 4 (`loopAdvance`: the advance made after the pass's charge, the next frame if it ran past the interrupt); and the
advance pass had no instruction grid (`SK.FECD`).  LRF1..LRF4: all 11 worlds, every ISR from the poke through the tail
and banner (and 60 frames of play where the machine does not run `$7E80`'s long path, DECLARED), every `$9888` / `$8D0C`,
the screen.  And the owner's round-2 freeze (the page only: skipProbe's fractional clock made the later-round map NaN
since M7.115b -- floored now, LRF5 on the page's own boot).  bb 1,832.

**M7.115 (2026-10-08):** a later round's start is on its own program.  Rounds 2..81 and the wrap were built and bannered on
contended means at one phase (BB_BUILD_AT / BB_BUILD_K / BB_ROUND_BUILD_T / BB_BANNER_AT).  MEASURED (tools/lrstart.py, 336
natural advances): `$97F8..$9887` and `$9888..$8D0C` are a program per round and player count, but for five pieces the
engine makes (the entry walk, `$83EB`'s JR, wallPattern by `$860C`, the lives and letter panels) -- 491 segments, 65 KB
(`BB_LR`).  Inside step() `lrClock` replays the build from `$97F8`'s phase (every stamp, the scroll's copier too) and the
tail runs on R1Tf's clock with the round's program and grid.  LR1..LR4: every advance's replay is the machine's, every
display write of a build at the machine's T, the tail's 46,262 writes at its plain T.  Not yet gated: free-running against
the machine (the engine's own ISRs in a later round's tail).  bb 1,827.

**PA4c (2026-10-08):** the cold start ($F5CC -> $8CCA) is charged by its own access program (tools/coldstart.py: plain
54,451 T, 13,648 contended accesses, one program on every world; `BB_SPINE.COLD`) replayed from its phase, not COLD_PH's
straight lines -- exact at every phase.  PA4's -0.218 T was that interpolation (not the scan means): free-running, the first
pass of play is now the machine's, 0.000 T.  bb 1,819.

**R1Tf (2026-10-08):** round 1's tail and banner take their ISRs at the machine's acceptance phase, from the tail's own
instruction grid (tools/r1tail.py: 362,817 instructions, one sequence on all 16 runs; `BB_R1T.INS`).  R1Td free-running is
now exact: 828 / 828 ISRs and `$8D0C` on all 16 runs (was 473, -8..5, 0..77 T early).  The real load free-running: all 380
ISRs of 380..760 and all 2,565 passes the machine's.  bb 1,816.

**M7.114e (2026-10-08):** the load's world is the tape's.  Frame 691's +1,510 T was the ODD ISR's slot 3 passing its
movement divider 21 frames early: its +4 seed came from `$73AF`, which the hand-over's `reset()` had rolled by spawning
round 1 itself before the round start spawned again.  A sweep of every byte the machine reads before writing it (load to
760) against the engine after the hand-over found that and `$856C`'s even bytes; `BB_TAPE_RMW` ($73AF = $02) and
`reset(keys, load)` (no spawn, no tile carry on the load) close both.  Given the machine's ISR T all 361 ISRs exact;
FREE-RUNNING the real load is the machine's pass for pass through the window's end (GR4, 2,565 passes); ISR T left: the
round start's acceptance (421..469, -6..+8 T).  bb 1,815.

**M7.114d (2026-10-08):** the acceptance phase from the instruction grid.  Every charge a pass's models make logs a grid
key (its instructions' T in the machine's order; a CALL defers what follows it to the kid's closing RET), resynced at each
callee's entry; the pass that straddles the interrupt point gives the instruction in progress, and the ISR's contention is
replayed from its end.  Against the machine (tools/insgrid.py, the real load's 2,565 passes, 1,693,208 instructions):
given the machine's ISR T every pass's grid is the machine's (GR2) and all 289 in-pass ISRs' acceptance phases (GR3).
FREE-RUNNING the real load is now the machine's pass for pass through frame 534's dark window to frame 690 (GR4); at 691
the even ISR's plain T parts (+1,510, a bubble-manager arm -- M7.114e).  The edge-read cuts became path-aware (a callee
that returns before its read runs its head before the ISR).  bb 1,808.

**M7.114c (2026-10-08):** the ISRs carry their own contention.  Each interrupt's display accesses (`$A447`'s erase and draw,
`$B9E7`'s blit -- swept templates, one per path and Y & 7), its port cycles and the settler's reads are laid on its own
ledger and replayed from the acceptance phase.  Against the machine (tools/isracc.py, the real load's 361 ISRs of frames
400..760): given the acceptance phase every ISR's program and delay is the machine's (IC2).  Free-running, play's first
pass is now 0.2 T off (was 1,036.8) and round 1's `$8D0C` 0..77 T early (was 813..1,792); what is left is the acceptance
phase (a declared constant, 4 T, where the engine does not know the instruction in progress -- M7.114d).  bb 1,801.

**M7.114b (2026-10-08):** the dark window.  `$93DC` shuts the ISR's even gate (`$FEC5`) for 62 T a pass (`$93E1` 0,
`$93F9` 1); an interrupt point between them is an even ISR that skips `$B62C`, as the machine's at frame 534 of the real
load did.  The engine places the window on the pass's frame clock and runs that ISR dark (PA8: given the machine's ISR
T, all 290 ISRs of 471..760 find the machine's gate).  The survey of the real load's play found no other byte the ISRs
read that the main line writes.  Free-running the clock was still ~1,037 T off by play (M7.114c).  The battery after M7.114a found five step() paths its
scenes no longer drove; they are gated as step()'s contract (PA9..PA11, CD3).  bb 1,798.

**M7.114a (2026-10-07):** the in-play pass is on the frame clock.  A pass is its plain T (the skeleton and its callees'
own sums -- the 78-T `BB_PASS_REST` was a phantom, the per-callee contended stretches `BB_PASS_K` are gone) and its ACCESS
PROGRAM: every contended access at its plain offset from `$8D0C`, replayed from the pass's phase, the ones past the
interrupt point after the ISR.  The interrupt is taken INSIDE the pass -- at a callee's entry, or at an edge detector's
counter read a fixed way in -- so the once-a-frame routines fire in the pass that straddles it, as the machine's do
(TRAPS #301).  And reset() seeds the 52 bytes the port reads that the tape leaves to play (TRAPS #300: build/image.bin
is not the loaded game).  Against the machine on the real load (tools/passacc.py): given the ISRs' T, all 2,565 passes
of frames 470..759 at the machine's phase with its program (PA2).  Free-running, play's first pass is 1,037 T early: the
ISRs' own contention (M7.114c).  Still declared: the hurry / storm / extend blocks start at their pass's start; sites off
the real load's play.  bb 1,792 / kit 120 / selftest 34.

**M7.113 (2026-10-07):** round 1's tail and banner from the title (`$9888..$8D0C`) are EXACT inside step() given the
ISRs' T: one plain access program in every run (81,852 accesses, shipped LZ-packed, 842 bytes) replayed lazily a frame
at a time (lzSeg, now given its block) behind the engine's own ISRs, the gate stores and the banner's 46,260 writes held
on its plain clock (BB_R1T); and the HALT at `$9887` lands on its 4-T grid (TRAPS #299: the harness's `_fast_halt`
does not).  Against the machine (tools/r1tail.py, 16 runs): the program (R1Ta), the replay (R1Tb), and through step()
with the machine's ISR T every ISR's screen, every write and `$8D0C`'s frame and phase (R1Tc); free-running the engine's
ISR T is the machine's UNCONTENDED T on every ISR, `$8D0C` in the machine's frame 813..1,792 T early (R1Td: the
engine-wide ISR contention gap).  The real load path is now identical to the machine from frame 407 to 533, into play.
bb 1,787 / kit 120 / selftest 34.

**M7.112 (2026-10-07):** the round-1 build from the title (`$97F8..$9887`) is EXACT inside step(): its plain access
program (54,150 / 54,296 contended accesses, one per player count -- the repaint's LDIRs from extModel's generator, the
rest shipped as data, the awards' T put back from the world) replayed from `$97F8`'s phase with the ISRs' 488 / 493
gives every stamp's main-line T (BB_R1).  Against the machine (tools/r1build.py, 18 runs incl. a poked high score):
the program access for access (R1a), the replay's end and marks (R1b), and through step() every boundary's display,
all 6,989 / 7,061 writes at the machine's T, the ISR T and `$9887`'s frame and phase (R1c).  On the real load path the
build's frames now match; the round tail and the banner (means) still move play by a frame.  bb 1,782 / kit 120 /
selftest 34.

**M7.111 (2026-10-07):** the title's exit -- the arm, the release passes (`$97B7`: the CLS, then the test of every
key, interrupts on) and the leave to `$8D09`'s CALL -- is its instructions on the frame clock (BB_TEXIT), not a pass at a
contended mean charged as a debt (PASS_T / ARM_T gone; `$97C7..$8D09` charged at last): the CLS wipes the title as the
machine's LDIR does and `$97F8` comes in the machine's frame at its phase.  EXACT against the machine from the real
load's `$9765` (tools/titleexit.py): the programs instruction for instruction (TX1); 16 runs, 144 boundaries, 1..5
passes (TX2).  Next: the round-1 build from the title on this path.  bb 1,778 / kit 120 / selftest 34.

**M7.110 (2026-10-07):** the title's paint (`$970F..$9765`: the CLS, 1,024 stars, the strings, the credit line;
interrupts on) is its 65,156 instructions on the frame clock (BB_TPAINT), not a debt drawn at once: the screen fills as
the machine's does, each ISR lands where the machine takes it and steps R (52 / 53), and the ring starts at the machine's
phase.  EXACT against the machine from the real load's `$970F` (tools/painttime.py): the program instruction for
instruction (PT1); 19 runs, 249 boundaries -- instructions done, ring iterations, attributes, bitmap less the ROM glyphs'
cells, PRNG, the arrival's frame and phase (PT2).  Still declared: the glyphs, the starfield's R at `$9712`.
bb 1,775 / kit 120 / selftest 34.

**M7.109 (2026-10-07):** the title's sparkle ring (`$9768..$978F`, interrupts on) is timed on the frame clock an
instruction at a time (BB_RING), not at a contended mean a path: the interrupt cuts an iteration where the machine's
does, and the write, the PRNG's store and the key test past the cut are the next frame's.  EXACT against the machine
from the real load's `$9765` (tools/ringtime.py): 22 runs, 660 boundaries -- iterations, attribute file, PRNG, the
cut instruction (RT1); the programs (RT2); six arms at the machine's frame and phase (RT3).  Still declared: the paint
drawn at once (the ring's start phase is the port's), the starfield's R.  bb 1,772 / kit 120 / selftest 34.

**M7.108 (2026-10-07):** the join (`$9961` and its 42..59K-T tail, interrupts on) is `lazy` inside step() -- placed
on the pass clock, every write held to its frame, the pass parked at `$8D34` while it drains.  EXACT against the
machine on 51 runs (LZ8, isrcarry's three join sources), its program access for access (LZ4), every write of the
jointail fixture's 28 runs at the machine's T (JT6), the parked pass through step() (JT7).  The awards' RLD
intermediates are not made (DECLARED).

**M7.105 (2026-10-07):** a DI window opens 1 T into its DI, not at its end -- MEASURED: an interrupt whose line rises
1..3 T into a DI is lost on the machine (the DI is the instruction in progress), and the engine used to take it.
`BB_EXT_W.DI_OPEN` 1 for every block's windows; isrcarry's 18 STRADDLE rows (giant, PERFECT, `$8C14`) pin it through
LZ1 / LZ5 / LZ7.  bb 1,757 / kit 120 / selftest 34.

**M7.104 (2026-10-07):** `$94C2`, the EXTEND completion, is `lazy` -- the LAST interrupts-on block on K.  It is EXACT
against the machine on 8 runs (LZ7: extcomp at five phases plus the tick, tickflood and storm worlds -- 1,955
acceptances, the lost interrupts, `$8D09`'s wall T and the main line), given the ISRs' T.  Its program is the machine's
access for access (LZ4, 4 worlds).  DI windows are now put on the frame clock in the frame they open in.  bb 1,757 /
kit 120 / selftest 34.

**M7.103 (2026-10-06):** the umbrella's head (`$88C0`, the first flash to its HALT, interrupts ON) is `lazy` too, EXACT
against the machine on 17 runs (LZ6: every acceptance, the HALT's wall T, the main line), given the ISRs' T; its program
is the machine's access for access (LZ4).  Its one ISR carries 92..96 T of its own (DECLARED).  `$94C2` the last on K.
bb 1,756 / kit 120 / selftest 34.

**M7.102 (2026-10-06):** the treasure room's `$8F4C` block (the award, then 256 "PERFECT !" draws with interrupts ON,
29..33 ISRs inside) is `lazy` too, EXACT against the machine on 59 runs (LZ5: every acceptance, the 13 interrupts its DI
window loses, the window, the end's wall T, the main line), given the ISRs' T; its program is the machine's access for
access on all three worlds (LZ4).  The award is a CLOCKED routine: its glyph stores are logged on the award's clock and
pushed at its close (`lzPush`).  r1_lead's ISRs carry contention of their own (<= 275 T an ISR, DECLARED).  The
umbrella's head and `$94C2` still K.  bb 1,755 / kit 120 / selftest 34.

**M7.101 (2026-10-06):** the storm wrap's `$A09A` block is `lazy` too, EXACT against the machine on 34 runs (LZ3), given
the ISRs' T -- the wrap's ISRs carry contention of their own (<= 883 T an ISR) that isrCost does not charge (DECLARED).
And lzSeg now makes the accesses of the instruction in progress at the interrupt point BEFORE the ISR, as the machine
does: every program access carries its T into its instruction (`bbAcc`), gated against the machine's plain run access
for access (LZ4).  `$8F4C`, the umbrella's head and `$94C2` still K.  bb 1,754 / kit 120 / selftest 34.

**M7.100 (2026-10-06):** the giant's `$A9B5` block -- interrupts ON, 3..5 ISRs inside -- is timed a frame at a time
(`lazy`: its writes and OUT held unstamped, `lzSeg` timing each frame by the access program from the phase the main line
actually resumes at).  EXACT against the machine on 46 runs (LZ1: every acceptance, every interrupt the award's DI window
loses, the end's wall T, the main line's delays), given the ISRs' T -- the engine's own isrCost is the machine's on the
giant's ISRs (M7.99e).  The wrap, `$8F4C`, the umbrella's head and `$94C2` still K.  bb 1,752 / kit 120 / selftest 34.

**M7.99b (branch `m799b-join`):** M7.96's two declared fidelity gaps closed -- `$9961`'s join tail now MAKES
`$7FD7`'s 64-cell attribute clear and the lives panel `$806C`, every write at the machine's T from `$9961`'s entry
(`joinW`), and `$915F` makes Boris's `$A314` erase (`tools/jointail.py`, JT1..JT5 / BO1).  bb 1,741 / kit 120 /
selftest 34.

**M7.97 (branch `giant-spawn`):** the level clear's giant-item spawn (`$8F26 CALL $A84D`) is made and its
188 / 212 T charged with `$8E3A` (`tools/giantspawn.py`, GS1 / GS2; RC1 re-aimed); `$A82D` seeded at its load
value $2A.  bb 1,708 / kit 120 / selftest 34.

**M7.99a (branch `m799a-boss`):** the boss tick's spawn (`$A9F9`, A = 4) was already charged by M7.96 (gated now, BK1);
the boss's kill through `$9298` is MADE and charged -- HL is `$A969`'s pushed `$A9AF`, so the corpse is born over
code (`tools/bosskillcost.py`, BK1..BK4).  bb 1,739 / kit 120 / selftest 34.

---

## Where it stands

| | |
|---|---|
| Target | The 48K game and its 128K branch (the 128K the page's default since M10.3, Alt+M the other), one self-contained HTML file, the keyboard through the original's control select (no Kempston interface on the faithful page: controllers are a later, declared layer) |
| Built artifact | `web/bubble_bobble.html` — regenerated by `tools/build.py` from `web/game.js` + `web/platform.js` + `web/template.html` + `build/*.json` |
| Game suite | **1,980 checks**, all green (`node test/bb.test.js`, ~7 min) -- latest: M10.3 (the page and the platform: G0..G9), M10.2d (the 128K branch's pause: Q1..Q6), M10.2c2 (its sound calls in play: D1..D6), M10.2c (its requests and waits on the main line: C1..C8), M10.2b (its sound hook in the game's interrupt: B1..B5), M10.2a (its cold start and hand-over: H1..H7), M10.1 (the AY engine: AE1..AE7), M9.2 (Alt+P / Alt+Q: AK1..AK9), M9.1 (the saved high score and fullscreen: HS1..HS10, FS1..FS12); before them the M7 timing campaign, stopped by the owner on 2026-10-12 after M7.115m (EV1..EV5).  Per-increment history: the dated paragraphs above and `docs/M7-PROGRESS.md` |
| Runtime suite | **132 checks**, all green (`node test/kit.test.js`; M10.3: "THE MIX", the beeper and the AY on one stream); tool selftest **38** (`python tools/selftest.py`; M10.0a: the 128K machine and the paging port) |
| Mutation battery | **7,039 cases** (`tools/mutants.py`, 20 workers: 6,840 on web/game.js, 152 on the page, 28 on web/platform.js, 19 on the suite).  The FULL battery of M10.4 (the runner changed) 2026-10-15 13:54..14:33: LISTED 7,039 KILLED 7,035, **0 survivors, 0 dead anchors, 0 misses** (TIMEOUT 1 / BROKEN 3: the known M7.110 cursor guard, B9 x2, M7.69), 38.0 min on 20 workers.  Each M9 / M10 increment's `--affected` run, all 0 survivors: M10.3 949 / 949 (8 MISSES, the selection's holes, closed by G9: `--match` 12 / 12), M10.2d 863 / 863, M10.2c2 802 / 803 (1 timeout, closed), M10.2c 689 / 689, M10.2b 533 / 533, M10.2a 521 / 521, M10.1 283 / 283, M9.2 140 / 140.  The FULL run before: 2026-10-12 (M9.1), LISTED 6,244 KILLED 6,239, 0 survivors, 0 dead anchors (the four known + one malformed case, re-aimed and killed), 60.0 min.  Every earlier run is in this file's history (`git log -p docs/STATUS.md`).  Result line: `build/mutants/summary.txt` |
| Engine size | `web/game.js` 23,061 lines; `web/template.html` 537; `web/platform.js` 1,030 |
| Frozen fixtures | 182 asset entries in `port.json`, 171 of them test-only (latest: `pause128`, M10.2d; `ay128flow` and `cold128`, M10.2a; `ayengine` and the shipped `aybytes`, M10.1; `popacc`, M7.115m), all measured from the owner's own tape via the SkoolKit-wrapped Z80 harness (the 128K's on `tools/harness128.py` and the paging port) |
| Traps recorded | 364 |

Everything above is measured against the real machine code running in the
harness.  Where a number appears in a comment it either names its source or is
marked PROVISIONAL.

### What the built page actually does right now

It boots, paints a round, scrolls it in, runs the HUD, and runs the main-loop
chain with the entity, bubble, item, enemy and effect passes wired, and plays
from the load to game over.  Since M7.42 the page BOOTS TO THE TITLE (starfield,
sparkle, '1' or '2' to start) and every game over returns to it; since M7.44 the player
reads the keys -- P1 on O/P/Q/SPACE and P2 on 6/7/9/0 (`BB_KEYTAB`, a stated gap until
the control select) -- and walks, jumps, blows, traps and POPS enemies; since M7.45 a
popped enemy dies, flies, lands as a fruit that can be collected, and the round clears to
the next -- the game plays round after round to game over.  Since M7.48 the players move inside
the entity pass as on the machine, so the fast-walk power-up works and a respawn calms the
enemies; since M7.50 the last enemy left turns angry and runs at double speed.  A caption under the screen
names the keys, read from the table in RAM (M7.46, ADDED page furniture).  Since M7.52 the
game sounds as the 48K machine does in play -- the collect chirp, the storm, the pause, the
reveal, the jump tone and the HURRY UP! train at the machine's times, with a main-loop sound
that an interrupt lands inside held until the port's ISR has run.  Since M7.54 the HURRY UP!
banner climbs a step at a time, and since M7.56 "ROUND n / READY !" is on the screen for the
whole of each round's start, as on the machine.  Since M7.57 an EXTEND completion runs in time
too: the playfield empties, ten rows of fruit climb the screen, "N I C E   n P" goes up, the extra
life lands 120 frames later and the round advances ~112 frames after that -- where the page used to
jump straight to the next round.  Since M7.59 every round change scrolls the new level in, as on
the machine: the separator band rises and the new playfield climbs the screen over ~53 frames, is
repainted and the lives go up -- where the page used to show the new level at once.  Since M7.58 the storm's flash is seen pass by pass -- four inks
29,088 T apart across 1.7 frames, the pass waiting for them -- where only the last used to show.
Since M7.64 THE PAGE BOOTS THROUGH THE LOAD, as the machine does: the original control select -- each
player picks KEYBOARD (and redefines on the redefine screen), SINCLAIR, KEMPSTON or CURSOR -- then the
black screen (the 48K/128K probe `$FAC3`, modelled cycle by cycle, skipped by default behind `skipProbe`)
and the hand-over into the title, whose key table is the one the players chose.  The whole load is diffed
frame for frame against the machine from the load to forty frames into the title (`tools/loadpath.py`),
through the page's own loop with real key events.  The faithful page has no Kempston interface
(`padKempston`, ADDED, default OFF): a player who takes KEMPSTON cannot move.  Since M9.1 the page keeps the high
score between visits (`saveHiScore`, ADDED, default ON; off, the machine's 20,000 every load) and Alt+Enter puts the
Spectrum on the whole screen (ADDED page furniture; Escape brings the page back).  Since M9.2 Alt+P pauses and resumes
and Alt+Q ends a game, through the game's own keys (`altKeys`, ADDED, default ON).  Since M10.3 THE PAGE BOOTS THE
128K: the game's own 128K branch on the port's clock -- the AY music in every frame interrupt, the title's and the
game start's tunes, the in-round theme at two ticks in three (full speed under HURRY UP), the six waits for a tune's end
(round 1's frozen start, the longer cutscenes) and the pause's mute -- with the beeper's effects beside it in one sound
stream; Alt+M reboots into the 48K, remembered in the browser (`saveMachine`, ADDED, default ON), and the caption names
the machine running.

---

## Done

- **The harness and the method.**  TZX parse, loader/boot, a SkoolKit-wrapped Z80
  with contended timing, a config-driven disassembler, code walker, byte grep,
  read-watch, clock histogram, screen forensics.  `python tools/selftest.py`
  gates them.
- **The platform runtime** (`web/platform.js`): display file + renderer, keyboard
  matrix + Kempston + gamepads, AY and beeper, the Web Audio bridge, the loop,
  settings.  Shared with other ports, so game changes stay out of it.
- **Render path** — byte-identical to a harness-captured clean round-1 frame.
- **The sprite blitter**, all four pre-shifted sub-positions (the game does not
  shift at draw time; each sprite is 352 bytes = four copies).
- **All 81 rounds' geometry**, the drift field and its painter, the collision
  transform, the mirror, the door patterns.
- **The scroll-in**, the round build, the HUD (score panels, lives icons, the
  RRD score conversion, and as of M7.36 the two text rows).
- **Bubbles** — blow, travel, drift, pop, the contact test, the pool at `$FED8`,
  the colour-shadow bubble tag (`$B8C0` claims, `$B6D6` releases).
- **Players** — walk, jump arc, fall, the floor probe, the bubble-jump, death,
  respawn, the mid-game join.
- **Enemies** — the handler/move/sprite tables, all types, the giant, the boss, and their
  projectiles (M7.55).
- **Items and score**, the EXTEND letters, hurry-up (its trigger, temper, Boris and sound,
  and its banner in time, M7.54), the round banner (in time since M7.56: on the screen for
  the whole of it), GAME OVER, the endgame loop.
- **The burst-sparkle engine** `$C002`, including the wrap the machine really has.
- **The main loop's pass in T** -- the skeleton by path (M7.87) and all twenty callees charging their own
  runs (M7.88..M7.93, M7.96): only 78 T of `BB_PASS_T` stay flat.
- **`$802E`, the string printer — all nine references in the image are now
  transliterated** and all nine draw on a path the port runs (`$9758`, the title's
  credit line, was the last, wired in M7.42).

## Left

In rough order of how much unknown machine behaviour is in each:

1. **The front end** — READ in full (`docs/M7.37-FRONTEND-READING.md`), then
   measured and adversarially verified increment by increment.  Increment A
   (`$97EB`, the CLS), increment **G** (`$95F3`, the whole cold start), **GROUP 1**
   (`$970F..$9764`, the title paint) and **GROUP 2** (`$9765..$97EA`, the sparkle ring,
   the two exits and the release wait -- WIRED: the page now boots to the title and every
   game over returns to it) are built.  ~~Nothing left in it needs another
   measurement~~ (M7.53 found that H-b's key model does, below) — the build plan with
   its measured grouping is §11 of that document:
   **G → GROUP 1 (A-wire + B + E + F) → GROUP 2 (C + D) → GROUP 3 (H + `$FAC3`)**.
   Each boundary was measured, not argued: E and F cannot be split because a glyph
   no string uses is forbidden by the tool that draws it, and C and D cannot be
   split because the release-wait census differs by exactly C's three writes
   depending on where you enter.
   **There is no attract mode** — measured over 16,749 frames — so that sub-system
   is off the list.  `$FAC3` (the 5.1-second 48K/128K timing probe) was in no
   increment's scope and now belongs to group 3.
   **GROUP 3 -- the control select, the redefine screen, the load spine -- is BUILT (M7.53, M7.61..M7.63)
   and WIRED (M7.64): the page boots through it.**  **DECIDED
   2026-09-28: the page presents the FULL original menu** (revising decision 2b's keyboard-and-
   gamepad-only plan; SINCLAIR and CURSOR are keyboard layouts; KEMPSTON reads nothing until the
   owner asks for controllers -- `padKempston`, ADDED, default OFF),
   **and skips `$FAC3`'s 5-second black screen by default** behind a named flag, the faithful
   wait kept and tested.  The split is measured: **H-b** (the key read `$F7B3`, the menu, the dispatch,
   the presets, the key-table builder, and the frame layer `ctrlBoot`/`ctrlStep`) is BUILT (M7.61) and
   unwired -- the ROM's stateful key decode held as a measured constraint; **H-c** (the redefine
   screen `$F723..$F7B0`, and player 2's paint after KEYBOARD) is BUILT (M7.62) and unwired; **H-d**
   (the load spine `$F5C6..$F5CF`, `$FAC3` cycle by cycle with the ROM interrupt's T as an exact law, the
   hand-over `$F5CC..$970E`, the `$9601` key copy and `skipProbe`) is BUILT (M7.63); and M7.64 WIRED
   them: the page boots through `ctrlBoot()`, `step()` delegates to `ctrlStep()`, the whole load is diffed
   frame for frame against the machine (`tools/loadpath.py`), and `padKempston` keeps a gamepad off the
   faithful path.
2. **Sound** — the 48K in-play beeper layer is BUILT (M7.52, `tools/beeper.py`), and the 128K's AY music with
   it (M10.1..M10.3: the engine transliterated, every request, wait and tick the machine's, the two chips on one
   stream).  Left: `AY_MIX`, the AY's level against the beeper's, PROVISIONAL until the owner's listening test.
   Left in the 48K layer, all declared: the key click (front-end group 3, `beeper_fixture.menuclick`);
   the hold's gap is the ISR that BEGAN the frame, not the one that ends it (17..25k T
   against the machine's 1,892 on a natural collect), and the storm's strikes land a
   frame apart where the machine's run 95,508 and 43,435 T -- both the frame ledger's
   layout; the umbrella's `$A110` and the level-skip's `$894B` paths are unported.  The
   reveal's OUT inside EXTEND goes out at its machine T (M7.57); elsewhere at the port's clock.
   The AY path exists in the runtime.
3. **The other blocking sequences, and the ISR T gaps.**  **STOPPED by the owner on 2026-10-12, after M7.115m: what is
   left here stays DECLARED** (the README names it; the newest list is `docs/TIMING.md`'s last "Still DECLARED", M7.115m's,
   plus the CAPS-held pass, TRAPS #357, found in M10.2d -- reopening either is the owner's call).
   **Where it stood (2026-10-08, from `docs/TIMING.md`'s "Still DECLARED" lines):** the real load free-running is the machine's from the load through play's window
   (GR4: all 380 ISRs of 380..760, all 2,565 passes; PA4 0.000).  Still DECLARED, most machine behaviour first:
   (a) `BB_ISR_ACCEPT` (the 4-T acceptance constant) wherever a pass or block has no instruction grid -- the lazy
   blocks (a later round's start has its grid since M7.115, free-running exact since M7.115c; the natural clear's and
   the PERFECT / EXTEND resumes' `$97F8` now at their pass's end, not yet measured free-running); (b) the fitted contentions -- EXTEND's completion (-5.8K..+4.7K T a hook), the storm ticks (-1.6K..+1.8K), the
   flood row (the round build's left with M7.115, but outside step() and for a round never measured); (c) the
   hurry's, storm's and `$94C2`'s blocks start at their pass's start; `$9E50`'s tick body before the ISR when its
   read is past the point; (d) sites off the real load's play not on the access program yet (`$7E80`'s long path,
   the boss's blits in `$A824` / `$A9ED`, `$9037`'s banner, `$9AEB`'s fire updates, `$C002`'s blits, `$915F`'s Boris
   erase, and `$8669`'s own -- each pass's item inks and blits, the take's erase, award glyphs and chirp OUTs: the
   potion's `$890D` 142 / 139 T early, M7.115e PT2); (e) the census world's odd frames (a twelfth pass twice in eleven), the Kempston branch's port cycles,
   corpse-flight / boss draws inside an ISR (none on the real load); (f) `$8C28`'s own 213,312 T outside `$94C2`.
   The history of how the blocks got here follows.  The HURRY UP! block runs in time
   since M7.54 (its writes held to their frames, the gates shut, the pass resumed after it; the
   ENTRY window -- a gate open for the block's first 135 T -- MEASURED in M7.81: play reaches it in 3 of
   12,660 candidate entries, the gate-open pass changes nothing the block reads differently, HE1 / HE2), and so does
   the ROUND BANNER since M7.56 (its writes held to their frames under both open gates; the 255
   repeats held from a checked scratch), and so does EXTEND's completion since M7.57 (every write
   stamped by a timing mirror exact to the machine's instruction sums on twenty worlds, stretched by
   a fitted contention -- every hook within -5,810..4,685 T of the machine's, DECLARED -- the round
   advance waiting for the T, and the interrupts under its two DIs LOST as on the machine), and so does
   the cross release's reveal from `$9032` since M7.86 (the same mirror on its own script, EXACT to the
   machine's 214,246 / 214,138 T and its 7,172 writes on r50_48 / r10_48; its DI loses 3 or 4
   interrupts, the engine the same at all 34 measured phases since M7.99c -- the reveal timed by its
   contended accesses from the entry's phase, exact; the pass parked at `$8D2E`) -- and the giant hit's (`$A9B5`, interrupts
   ON) since M7.100, the storm wrap's (`$A09A`) since M7.101, the treasure room's (`$8F4C`) since M7.102 and the umbrella's head
   (`$88C0`) since M7.103, `$94C2` itself since M7.104 and the potion's (`$890D`) since M7.115e, timed a
   frame at a time from each frame's actual phase, exact given the ISRs' T (LZ1, LZ3, LZ5, LZ6, LZ7) -- and so do
   the storm's flash and strike ticks since M7.58 (the painter's stores held to their frames under
   both OPEN gates -- 78 natural ticks show the interrupts touch no attribute byte and nothing the
   tick reads -- stretched by a fitted contention, -1,638..+1,772 T, DECLARED; the pass parked at
   `$8D46`), and so does the ROUND BUILD since M7.59 (its 170,244 display writes held to their frames
   -- 26 scroll steps over ~53 frames, the repaint, the lives -- stamped from a per-round anchor and
   exact sums stretched by a fitted contention, -4.7K..+4.8K T against the machine, DECLARED; round
   1's HUD, the title's transition only, in time since M7.82 -- 617 / 653 writes, each at its exact T,
   `$7FD7`'s `$AA49` and `$7FDF`'s lives panel added; BD1).  Since M7.60 the storm's payload `$A0F5`
   is timed on all sixteen ticks that call it (the thirteen waiting ticks `$F0..$FC` and the three
   strikes): its 36 stores held to their frames, the SETs as operations, and its DI window LOSES an
   interrupt whose line rises 160..1287 T into the tick, as the machine does (200 offsets, contended).
   Since M7.83 the FLOOD's tick (`$A127`) is timed too: every exit charges its exact cost (BB_FLOOD), the row's
   32 stores are held on the tick's clock (stretched, DECLARED) and its door into the payload (`$A151`) runs the
   thunder's held stores and DI window 8 T later (lost 168..1295, measured).  **M7.68 closed most of the ISR T
   gap (PK7):** the 41 T acknowledge before `$8D72` is charged on every interrupt, and `$AA60` charges itself --
   its skeleton exact (instruction sums, every slot of 134 recorded passes), its handler runs and corpse
   flights at their measured MEDIANS (PROVISIONAL, reported as `frameLedger().aa60`), the diverted pass
   exact.  Under the banner: even interrupts exact, the late odd ones 22..39 / -26..-16 T (were 4,070 /
   2,237 LONG).  M7.69 made the player's runs exact and M7.70 the eight enemy handlers' (`BB_EN`,
   uncontended instruction sums on the engine's own branches, EN1 exact on 751 kept runs), and M7.72 the corpse
   flight's (`BB_CO`, CO1 exact on 110 kept runs; it found `$BF0A`'s dropped carry T).  M7.73 made the even pass
   `$B62C` charge itself: its skeleton exact (`BB_B62C`, MG1 on 257 kept slots of 6,408 tiled passes), its arms
   at PROVISIONAL medians (`BB_B62C_ARM`, `frameLedger().b62c.prov`) where a flat 5,300 T a bubble stood; a pop's
   ISR T went from ~8.4K short to 2,352 (pinned, PK7), and a full pool's pop wave now overruns a frame where the
   machine's does (IA2).  M7.74 made the first arm, the blow check `$BD2C`, exact (`BB_BL`, BL1 on 64 kept
   runs of 6,413 plus 17 forced calls; its nested pop and award apart, PROVISIONAL) and modelled its +$61
   bonus; M7.75 the draw `$B9E7` (`BB_DR`, DR1 on 126 kept runs of 12,307 plus 46 forced calls: five sprite
   choices x three Y phases, Zilog sums; PK7's pop gap moved to 2,903, the median had overcharged); M7.76 the rise `$B836` (`BB_RI`, RI1 on 159 kept
   runs of 12,311 plus 30 forced calls, the push's erase and the bounce's shove apart; PK7 2,903 -> 2,683); M7.77
   the pop `$B6D8` from all three callers (`BB_PO`, PO1 on 72 kept runs of 71 plus 23 forced calls; the erase and a
   frozen enemy's birth exact, the award and a live birth PROVISIONAL, a ROM-centred chain window DECLARED; PK7
   2,683 -> 1,421); M7.78 the escape `$B679` (`BB_ES`, ES1 on 22 kept runs of 2,784 plus 13 forced calls: element
   16, ageing 46, a release 478 + its erase apart; PK7 did not move); M7.79 the travel `$BDFE` with the capture
   (`BB_TR`, TR1 on 466 kept runs of 752 plus 31 forced calls; `$BF16` and `$A447`'s live arm priced on the way, so
   a live enemy's corpse birth is exact too; a 256-slot scan through the ROM DECLARED) -- every arm of `$B62C` is
   exact; M7.80 the award `$80FA` (`BB_AW`, AW1 on 79 kept runs of 60 from seven call sites plus 25 forced calls;
   PK7 1,421 -> 1,093): nothing PROVISIONAL is left inside the even pass.  Left (the hurry's ENTRY window MEASURED in M7.81):
   contention.  `$8C28`'s own 213,312 T is charged nowhere but inside `$94C2` (`docs/TIMING.md` item 10).  (CLOSED lately: the player
   interleave M7.48, `$A431` M7.49, the one-left anger M7.50, and `$8C51` on a live enemy -- a
   killed enemy is now erased -- M7.51.)
4. **The elementals -- CLOSED by M7.67.**  The enemies' projectiles (`$9BB4`) run since M7.55, the
   fire-mode fireball (`$9DD4` / `$9DE1`) since M7.60, the lightning bolt's enemy kill since M7.65, the
   water stream since M7.66, and the fire elemental -- the arm `$93FD` and the manager `$9F63`: the
   drop, the landing's spread, the burn and the end -- since M7.67.  No elemental stub is left.
5. **`$8306`'s half-painted map hazard** — the round painter's `LDIR` with
   `$82F7 AND $47` keeps ink, so mid-repaint all 704 playfield cells carry low
   bits that are COLOUR, not a bubble tag.  The port must not run the bubble
   probe against one (TRAPS #184).  Known, not yet asserted.
6. **Bytes of observable memory the port never writes** — `$AD90`'s
   self-modified `$ADA1`/`$ADA2` and `$AD26`'s `$AD41`/`$AD42`.  Any memory diff
   across a jump or a fall will show them.  And the item blit's and erase's operand
   patches (M7.57): `$A2C2` NOPs `$A307`/`$A30C` and puts them back, `$A304` takes the
   column, `$A314` patches `$A355`/`$A349`/`$A33D` -- five stores an item entry the
   port does not make (the blit is a store, not a patched OR).
7. **128K -- DONE (M10.0..M10.4, 2026-10-13..15)**, but for `AY_MIX` (item 2).  The record: the music driver at
   `$D167` was untouched on the 48K branch the port first modelled.  The M10 recon (2026-10-13) read it, modelled it in
   Python and ran it on the project's first 128K harness: the model matches the
   machine exactly.  It also measured what else the 128K branch changes (six waits,
   round 1's frozen start, the in-round theme's cadence).  The findings and the
   plan, with the owner's three decisions, are in docs/M10-PLAN.md (M10 is part of
   done).  M10.0 (the oracles: the two machines, the engine direct, the flow on the
   port's clock), M10.1 (the engine in JS, gated write for write), M10.2a (the cold
   start and the hand-over) M10.2b (the sound hook in every interrupt: the title
   plays) and M10.2c (the title's, round start's and game over's requests, round 1's
   wait) and M10.2c2 (the in-play sites and waits) and M10.2d (the pause) are DONE: M10.2 is done;
   and M10.3 (the page and the platform: the 128K the page's default, Alt+M, the beeper and the AY on one sound
   stream) is DONE, and M10.4 (the release docs, the FULL battery).
8. **Declared departures still to be re-examined**: the substitute fonts (no ROM
   is shipped or transcribed, so `$3C00 + 8*code` is replaced by code-indexed
   substitute cells — 51 codes in `BB_BANNER_FONT`, none equal to any eight-byte
   window of the ROM and none within 3 bytes of its own ROM cell moved two rows
   (M7.53; the owner KEPT this rule on 2026-09-28 -- '9', 'O' and 'U' come within one
   byte of some other ROM window, simple shapes, not copies), plus `BB_LETTERS`,
   `BB_DIGITS`, `BB_HURRY_FONT`), and the declared slowdown flag.
9. **ROM bytes in the git HISTORY.**  Since M7.53 the tree is ROM-free (an
   independent scan of every tracked file finds no ROM character cell and no strong
   ROM window), but twelve earlier quotes -- the old substitute 'P', eight bytes of
   ROM code at `$05E0`, the ROM's 'W', '!', S and G rows -- and nine ROM glyph cells
   in the element-class fixture are still in the commits that added them.  **DECIDED
   2026-09-28: a PRE-PUBLICATION STEP -- before this repository is pushed anywhere, publish a
   scrubbed history (git filter-repo over those quotes) or a single squashed commit, never the
   history as it stands.**  **DONE 2026-10-16** (the owner asked for a public repository): the
   tree went out as ONE parentless commit, without `build/` (the decoded assets and the
   fixtures, which carry the machine's states and screens), to github.com/cookertron/BubbleBobble;
   this repository still has no remote, and must never get that one -- its history is not
   for publication.  Updates go out the same way (next.md says how).

---

## How each increment is built

Six steps, in this order, every time:

1. **An oracle** — a `tools/*.py` script that drives the real routine in the Z80
   harness with interrupts OFF, at its own entry point, and records what it did.
2. **A fixture** — `build/*_fixture.json`, frozen, registered in `port.json` as
   `ship:false` so it is test-only and never reaches the page.
3. **The engine method** in `web/game.js`, transliterated instruction by
   instruction, with the machine address in a comment on each line.
4. **A gate block** appended to `test/bb.test.js`, comparing the engine's
   behaviour to the fixture row for row, with the negative controls that stop the
   row passing for the wrong reason.
5. **Mutation cases** appended to `scratchpad/battery/mutate7.py`, then the full
   battery: break each behaviour on purpose, watch the named test fail, restore.
6. **Docs** (SPEC / TRAPS / M7-PROGRESS) and a scoped commit naming what was
   measured and what the battery covered.

The built artifact is what is tested — `tools/build.py` first, then the suites.
No test ever imports a source module.

### The rules that keep it honest

- Measure, don't assume.  When the JS disagrees with the simulator, the
  simulator is right until proven otherwise.
- A test that cannot fail is not a test.  Every behaviour is mutation-tested.
- Faithful first; every departure from the original is a named flag, off on the
  faithful path, with the faithful behaviour kept in code and tested.
- Diagnostics ship.  A fallback never engages silently.
- Never commit tape-derived material — no `.tzx`, no `.pkl`, no `build/*.bin`,
  no extracted binaries.  Decoded data and frozen fixtures (`build/*.json`) are
  fine, and are what the suites read.

### What keeps going wrong, and what now catches it

Two failure modes dominate, and both are about *verification*, not about code:

- **Gates that pass while testing less than they claim.**  Countermeasures now
  routine: enumerate the category in code and assert nothing is unnamed; drive
  the routine at its own entry when no caller can express a difference; poison
  the exact computed addresses, not a fixed region; require the positive signal
  (`N/N checks passed`) in every harness; treat "fast" as a failure signal.
- **Correct measurements supporting wrong conclusions.**  A measurement of ten
  captures that contained no live bubbles was correct and the conclusion drawn
  from it was not (TRAPS #183).  The fix is always to name what the sample did
  *not* contain.

`scratchpad/m735_anchors.py` checks every mutation case's anchor for being dead
or ambiguous, plus a count invariant, in under a second — after a re-anchoring
script silently deleted two cases and arithmetic was the only thing that noticed
(TRAPS #186).
