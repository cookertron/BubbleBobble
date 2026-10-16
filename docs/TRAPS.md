# Traps — what two ports paid to learn

Each entry is a measurement, not an opinion.  The manual (`PORTING-ZX-TO-
JS.txt`) says what to do in each phase; this file is the list of places a
careful engineer still fell in, with the number that proved it.  Read it
once before starting and again whenever something is "nearly right".

## Simulation and the oracle

1. **Contended timing changes the game's speed.**  The plain simulator and
   the contended (CMIOSimulator) one disagreed by 7,400 T a main-loop pass
   in the case study: 11.3 Hz uncontended against 10.0 Hz contended, and
   real hardware is the contended figure.  The harness defaults to
   contended; every pass-rate, clock and sound-cadence measurement is wrong
   on the other setting.

2. **Boot the real loader, in order, unpatched.**  Loading blocks "by fiat"
   (copying them into memory and jumping to the entry) skipped a paging
   probe the loader itself ran, left a mode byte at a stale value, and put
   EVERY sound measurement for weeks on the wrong (128K/AY) branch of a
   game that was actually a 48K beeper game on the owner's machine.  The
   fix was a boot that ran the loader's own code between blocks.  If the
   loader does anything but LOAD, let it do it.

3. **An emulation bug can look exactly like a tape fault.**  A corrupt glyph
   was reproduced in a third-party emulator too and blamed on tape
   mastering.  It was the simulator's own interrupt landing while the game
   ran with SP pointed at sprite data; the ISR's pushes scribbled return
   addresses over the tail bytes.  Under contended timing it never
   happened.  Verify every extracted asset against the tape bytes, and
   refuse to ship one that is not genuinely there.

4. **Asset extraction reads the live buffer, not the screen.**  A sprite
   captured off the display is one frame of one draw under one palette;
   the sprite RECORD the game decodes is the asset.  Capture at the instant
   the blitter finishes, or decode the record format outright.

## The audio bridge

5. **Tile buffers on the sample grid — floor BOTH ends, never round a
   length.**  A 50.08 Hz frame is 880.591 samples at 44.1 kHz; rounding
   the length while placing the start exactly made every buffer a fraction
   of a sample too wide or narrow.  Measured: 426 of 1,042 joins collided,
   mixed peak 1.2169 against a largest single sample of 0.9996.  Taking
   both ends onto the grid makes buffers abut by construction for any
   frame count; floor keeps an edge's time inside its own buffer
   non-negative (round put 0.495 of full scale on one sample, −44 dB).

6. **Cut the event log by the WINDOW, not by the frame.**  The buffer ends
   on a sample boundary, up to one sample short of the frame's exact time;
   an edge in that sliver must stay in the log for the next buffer.
   Splicing it with only its level applied cost −54 dB on a two-voice tune
   whose edges are 0.6 of a sample apart.

7. **A backward jump of the simulated clock is a RESTART, not drift.**
   Without a re-origin branch the game played SILENT for as long as the
   menu before it had lasted — 19.3 s after a 930-frame menu.

8. **Count voices against the clock, never in `onended`.**  That callback
   may never fire on a suspended context, and then the cap never releases.

9. **The jitter budget must adapt.**  A fixed 80 ms head start tore the
   schedule on a gaming laptop whose main thread stalls longer than that,
   twice per stall (the gap, then another lead of silence from the
   resync).  Ratchet the lead by the MEASURED deficit on genuine underruns
   only; never on restarts; never decay it.

10. **Ask for the stability buffer.**  `latencyHint: 'playback'`, not the
    default 'interactive' (the smallest hardware buffer the OS will serve).
    A game's sound is quantised to its own frame or pass anyway.

11. **The speaker is a cone, not a voltmeter.**  A bit-exact square wave is
    faithful to the ULA's output pin, not to what anyone heard; the game's
    own chirps reach 7.4 kHz and small laptop drivers buzz on raw edges.
    The 4.2 kHz second-order model stays on by default; the raw voltage is
    one console toggle away for A/B.  (It was NOT the crackle — see 12 —
    but it stays on its merits.)

12. **One continuous stream beats many scheduled buffers.**  A laptop
    crackled on the joins between per-frame buffer sources while a native
    emulator played the same game clean on the same machine — the
    emulator's audio is a pull-model stream.  The worklet FIFO transport is
    that; the crackle lived exactly where joins were densest (the title
    tune, 50 buffers a second) and vanished with it.

13. **Blob worklet modules fail on `file://`.**  Measured in headless
    Chrome: `audioWorklet.addModule(blobUrl)` → `AbortError: Unable to load
    a worklet's module`; a `data:` URL loads, constructs and messages.  A
    double-clicked download IS `file://`.  Try blob, fall back to data.

14. **Never let a fallback engage silently.**  The first worklet build fell
    back to the scheduler without a word, and it took a full remote
    debugging round trip to learn that the fix had never run.  `info()`
    names the transport and the reason it is not the preferred one.

15. **Above-Nyquist content must average, not fold.**  Game data routinely
    holds pitches at 15–21 kHz; a point-sampled square folds them into the
    audible band as a whine that is not in the original.  The beeper's box
    integral and the AY's stepped mean both exist for this (a 100 kHz
    square renders below 0.12 peak, derived bound 0.11).

## The page and the rig

16. **Render with primitives only.**  `fillRect` and `fillStyle`, nothing
    else — so the headless rig can record the draw list and DIFF two
    renders that differ by one flag.  Everything visual then has a test.

17. **A test that cannot fail is not a test.**  Persistence checks passed
    for weeks because the rig had no localStorage and the code guards every
    call in try/catch: save wrote nowhere, load read nothing, nothing
    failed.  The rig now has a real store, and `settingsStore.save` reports
    whether the write landed.

18. **The arrow keys ARE the Spectrum's cursor keys.**  On a 48K, cursor
    left/down/up/right are 5/6/7/8; mapping the arrows onto them is the
    machine, not a convenience.

19. **Keystrokes aimed at a form field are not game keys**, and a button
    left holding focus swallows SPACE.  Guard the first; blur the second.

20. **Losing window focus loses the keyup.**  Release everything on `blur`
    or the player walks into a wall until they press the key again.

## Method

21. **The differential gate is the whole method in one shape.**  One
    sampler at the main-loop top; the same key script through the harness
    and through the built engine; two tables diffed row for row.  The
    first differing row names the bug.  Every other tool exists to feed it.

22. **Freeze the oracle's answer as a fixture.**  When a gate needs the
    tape and the tape is not always available, the real Z80's own output
    lives in `build/*.json` and the headless suite runs against it.

23. **Mutation-test, then trust.**  Break the behaviour on purpose and
    watch the NAMED test fail.  A mutation that nothing catches is either a
    missing test or proof that the line is not load-bearing — both are
    worth knowing, and only the first is a bug.

24. **The added layer is a boundary only if a test says so.**  Run the
    simulation with the enhancement on and off and require the state to be
    byte-identical.  Intent is not a boundary.

25. **On a machine you cannot touch, shipped diagnostics are the
    debugger.**  Every decisive measurement in the audio saga came from the
    player's side: a control experiment (the emulator), one pasted `info()`
    line, and a localisation ("only the title tune").  Build for that.

26. **The static image is POST-BOOT — the front end is not in it.**
    `build/image.bin` is the game after the loader handed over, so the
    control-select / key-redefine front end (`$F5xx-$F9xx`) and the
    one-shot key-table copier `$95F3` (which self-overwrites after its
    `LDIR`) are gone — grepping the image for "the writer of `$B5FD`" finds
    nothing.  Study those in a LIVE title state (`title.pkl`) or by driving
    the menu, not the image.  (M5 bucket-A cost a "no literal writer exists"
    dead-end before this was noticed.)

27. **`Mem.watch(lo,hi)` is HALF-OPEN `[lo,hi)`.**  `watch(a,a)` logs
    nothing; use `watch(a,a+1)` to watch one byte.  An earlier "the boss
    death award never fires" and a "0 writes to enemy `+9`" reading were
    both this off-by-one, not a real absence.  When a write-watch comes
    back empty, first check the range is not degenerate before concluding
    the code path is dead.

28. **The machine detect can be a TIMING PROBE -- and your key script can
    flip it.**  Bubble Bobble decides 48K-vs-128K by counting loop
    iterations across 255 ROM-FRAMES ticks (`$FAC3`) and accepting exactly
    two counts; the count moves with ULA contention and with the ROM ISR's
    keyboard work.  The M2 script held a key through that 5-second credits
    screen, the count came out two blocks low, the game took the 128K branch,
    copied its AY engine over the sprite region, and every harness play
    state for three milestones was on the wrong branch (M3 then read the
    ISR's draw pass as "the music").  Uncontended simulation misdetects too.
    Rules: (a) after the loader, find the branch decision by WATCHING what
    patches the sound hooks, not by reading BANKM; (b) keep contention ON;
    (c) release keys before any long front-end wait and check the decision
    byte (`$8DC4` here) in every saved state; (d) attribute `OUT`s by the
    executing PC (`tools/sfxcensus.py`) -- a static `D3 FE` scan matched
    data bytes.

29. **`run_frames(1)` overshoots, and the overshoot ACCUMULATES.**  Each
    call targets `T + FRAME_T` from wherever the previous call stopped and
    stops up to one instruction late, so over N calls the capture window
    drifts late (~5 T/call measured).  After ~80 calls the NEXT frame's
    early-ISR work leaked into the current window -- here the bubble pool's
    `+4` tick, ~400 T into the frame -- while the frame counters, which the
    same ISR increments LATE, did not: parity looked right and one field was
    one frame early.  Two identical scenarios captured with different call
    granularity then DISAGREED, which is the tell.  Rules: (a) capture long
    fixtures against ABSOLUTE boundaries `t0 + k*FRAME_T`
    (`run_until((), stride=1, predicate=T >= target)`); (b) when a fixture
    and a write-watch differ by exactly one frame, suspect the window, not
    the game -- re-run with a different call granularity before touching
    the engine; (c) long captures are safe for observables written late in
    the frame (main-loop physics); re-check anything the ISR writes early.
    (Kit candidate: give `run_frames` an absolute-target mode.)

30. **A self-modifying PRNG's cycle length is SEED-dependent -- never reuse the map
    as a general stream** (Bubble Bobble, 2026-09-10, docs/RNG.md).  `$FE85` is the
    game's real generator: a 16-bit hash whose state IS its own `LD HL,nn` operand.
    It is a bijection, so every seed lies on a cycle -- but the cycles differ wildly.
    From the tape seed `$002A` the orbit is 54,919 long; from `$BB02` it is 7,503,
    which at the blocked-bubble draw rate repeats inside 3-4 minutes of play, and
    short-orbit seeds score chi2 636-852 on 127 df.  So: transliterate it for its own
    consumers, seed it only the way the machine does, and NEVER borrow it as the
    substitute stream for other sites "because it is already there".

31. **A forced scenario manufactures the statistics you then measure**
    (Bubble Bobble, 2026-09-10).  Chasing a rare RNG path, one census built a
    6-bubble cluster and re-poked it every 40 frames.  That scenario produced chi2
    221.7 on 127 df at a site where NATURAL play measures 123.8 -- an apparently
    damning non-uniformity that was entirely an artefact of the harness driving the
    same code path in lockstep.  Distribution claims must come from natural play;
    forced scenarios are for REACHING a path, not for characterising it.

32. **"No RNG here" from a fixture that logged only ONE site is a false invariant**
    (Bubble Bobble, 2026-09-10, caught by a completeness critic before it shipped).
    Two bubble fixtures record zero random draws, and a proposed gate turned that
    into "this replay consumes no RNG at all".  But the captures logged the bubble
    site alone: on the same idle round-1 scenario the ENEMY hesitation site fires 22
    times in 400 frames.  The assertion was true only because that site was not yet
    wired, and would have gone red the day the enemy work landed correctly.  Scope a
    zero-consumption assertion to the SITE the fixture actually measured, and re-check
    it when a new consumer is wired.  General form: a fixture's silence about X is not
    evidence that X did not happen.

33. **A gate that RE-IMPLEMENTS the logic it tests cannot fail** (Bubble Bobble,
    2026-09-10, caught by my own mutation battery one increment after a critic
    flagged the same class).  The RNG gate checked that a draw is seven bits --
    the single most consequential property, since believing otherwise is the
    1/256 bug the SPEC taught for months.  It built its sample with a local
    helper that did the shift ITSELF rather than calling the engine's.  Every
    frozen constant matched, the gate went green, and mutating the engine's
    extraction to eight bits changed nothing: the test was testing the test.
    Rule: a gate must reach the property through the SAME function the shipped
    path uses -- one source of truth for the computation, exercised by name --
    and where a property is load-bearing, assert it a SECOND way through the
    real call path (here: draw 50,000 values through `rng.draw()` and check the
    maximum), so a mutation that bypasses the shared helper still fails.
    House rule 3 is not satisfied by running the battery; it is satisfied by
    watching each mutation fail a NAMED check, and by treating a mutation that
    does NOT fail as a finding about the gate rather than a pass.

34. **A fixture captured at a fixed T-offset inside a long ISR does not record
    the machine's per-frame state -- it records a CUT THROUGH ONE PASS, and a
    model fitted to it will be confidently wrong** (Bubble Bobble, 2026-09-11;
    the most expensive error on this project so far, shipped and gated for a
    day before a 10-agent measurement workflow caught it).
    The bubble manager was recorded as "split by slot across frame parities":
    pool slot 0 serviced on one parity, slots 1-11 on the other.  That model
    was derived from per-frame PC counts and per-slot write-watches, it was
    written into the SPEC, transliterated into the engine, and three fixture
    scenarios passed against it FRAME FOR FRAME.  It was false.  The machine
    runs ONE unconditional twelve-slot loop, entirely inside one parity's ISR.
    WHAT ACTUALLY HAPPENED: the captures sampled at a fixed `t0 + k*FRAME_T`
    offset, and that offset lands INSIDE the even ISR -- after slot 0's X write
    (+808 T) but before slot 0's `+4` write (+2255 T).  So one manager pass was
    sliced in half: slot 0's pre-sample work appeared on one row, and slot 0's
    tick plus ALL of slots 1-11 appeared on the next.  Two half-passes read
    exactly like two alternating half-schedules.  The reconstruction is
    constructive, not a story: the fixture reproduces with ZERO differing rows
    for sampling phases +1650..+2250 T and for no other phase.
    WHY THE GATES DID NOT CATCH IT: they compared X, and X advances on the same
    row under both models.  The column that separates them is the AGE, because
    it advances in the SAME pass as the move.  The gate was blind BY COLUMN as
    well as by boundary -- so "it passes frame-for-frame" meant only "it agrees
    on the columns I happened to compare, at the phase I happened to capture".
    RULES: (a) sample a fixture at a STRUCTURAL boundary -- run to the ISR
    entry, step in, run to its RET -- never at a fixed `T mod FRAME_T`, because
    the ISR's length is state-dependent (measured 1841 T empty to over 112000 T
    with a full pool, i.e. more than a whole frame); (b) record the sample PC on
    every row, which would have shown these rows landing mid-routine and caught
    it at capture time; (c) assert the boundary as a field in the fixture and
    check it in the gate; (d) when a model says two things happen on different
    frames, gate a column that MUST move with each of them, not one they share;
    (e) a schedule claim needs a scenario that DISCRIMINATES it -- here, a
    bubble in slot 1 with slot 0 deliberately EMPTY, which the two models
    predict as exact mirror images.

35. **Never bracket a routine's cost by watching the STACK POINTER return --
    one such bracket produced TWO wrong conclusions and both shipped**
    (Bubble Bobble, 2026-09-11, docs/TIMING.md).  The IM2 handler's cost was
    measured from its entry until SP rose back above its entry value.  But the
    sprite blitter parks the stack on the sprite and switches it repeatedly
    ($A437 `LD SP,IX`, $A489 `LD SP,HL`, 14 switches per odd interrupt), so the
    bracket stopped at $A48A after 1481 T inside a routine that really costs
    ~27000 T -- a factor of 19.  That alone would have been bad enough.  The
    compounding failure: the first display write happens 139 T AFTER the bracket
    gives up, so all ~288 writes fell OUTSIDE the measured "interrupt" and were
    attributed to the main loop.  The project then recorded, in the SPEC, in a
    fixture and in three comments that ship inside the built artifact, that the
    heavy composite is a main-loop event -- and "corrected" an earlier draft that
    had been right.  RULES: (a) bracket by CONTROL FLOW (entry address to the
    RET), never by a register a stack-blitter will move; (b) a cost measurement
    and a location measurement taken through the same bracket are NOT
    independent evidence -- if the bracket is wrong they fail together and
    corroborate each other; (c) when a new measurement overturns an older one,
    check whether the new METHOD is sound before believing it, because the older
    draft here was correct and was discarded; (d) do NOT validate such a capture
    by checking that the routine's cost plus the remaining time sums to one
    frame -- that is a partition identity, satisfied by ANY cut of the window,
    and the faulty bracket passes it by 0 T.

36. **A hazard you have already written down will still fool you, if it reaches
    you disguised as a different subsystem** (Bubble Bobble, 2026-09-12; this is
    #28 coming back, and the record is that it worked).  #28 says the 128K
    branch copies its AY engine over the sprite region and that every play state
    made before 2026-09-09 is on it; the project memory even names the range,
    `$C350-$D263`.  Yet when three of those old states (`play1p`, `round1`,
    `crowd`) disagreed with the tape over 336 of the 384 bytes of the bubble
    sprite at `$C780`, that read as evidence about GRAPHICS -- "this sprite must
    be built at runtime" -- and a session went and wrote it into the SPEC.  The
    branch never came to mind because nothing in the question mentioned sound.
    What settled it was measuring the EXTENT before theorising: 3,617 of the
    3,860 bytes inside the `$96B3` LDIR window differ and 0 outside it, which is
    an LDIR's signature and not a builder's.  The real discriminator is `$8DC4`
    (`$F3` = 128K, `$C9` = 48K), NOT `$9AE7`, which reads 0 on both.  RULES:
    (a) when a region disagrees between two states of the same game, get the
    extent first -- an LDIR leaves a window with hard edges, a builder leaves a
    pattern; (b) check the machine branch of every state a claim rests on, and
    say which states those were; (c) a paging-less harness turns a bank write
    into silent corruption, so any claim about memory above the paging boundary
    is suspect until the branch is pinned; (d) note the branch discriminator in
    the fixture metadata, not only in the state's filename.

37. **A resting scene where two of a routine's inputs are EQUAL cannot show you
    which one it reads -- six mutations survived a green byte-exact oracle**
    (Bubble Bobble, 2026-09-12).  The bubble blitter composites the display with
    the SHADOW buffer (the clean platform layer).  The oracle was captured on a
    settled scene, where the platform layer had just been restored -- so at
    every address a draw touches, display == shadow.  With d == s, reading the
    shadow and reading the display give the same answer, and the two edge masks
    are interchangeable: `(d&M)|(s&~M)` == `(d&~M)|(s&M)`.  A second accident
    compounded it: rows 0 and 15 of the real sprite are BLANK, so "row 0's
    sprite bytes are discarded" and "the last row is re-written background-only"
    -- two genuine features of the routine -- were also invisible.  The gate was
    byte-exact over 21 cases and 1,008 bytes and still passed a blitter with the
    wrong background source, the wrong mask polarity, no trailing restore, and
    only 15 rows.  RULES: (a) for any routine with two data inputs, one case
    must make them DIFFER; (b) for any routine driven by asset data, one case
    must use a SYNTHETIC asset with no zero bytes, so every structural position
    is observable -- the machine runs it just the same; (c) gate the addresses a
    routine did NOT write as well as those it did, or a wrong address simply
    goes unexamined; (d) when a mutation survives, the fault is in the SCENARIO
    before it is in the gate -- ask what the scene makes equal.

38. **`rom_writes` is a DEAD COUNTER under the C simulator -- a zero that looks
    like evidence** (Bubble Bobble, 2026-09-12).  The kit's `Mem.__setitem__`
    counts writes below `$4000` so you can tell "the routine attempted a write
    into ROM and it was dropped" from "the routine never went there".  Under
    `CMIOSimulator` -- the default -- it never increments: SkoolKit's C
    simulator enforces the ROM boundary itself and does not call back into
    Python for those writes.  Verified directly: a RAM stub doing
    `LD A,$FF / LD ($0000),A / LD ($8000),A` logs only the `$8000` write, leaves
    `mem[$0000]` untouched, and moves `rom_writes` by 0.  The write LOG is
    complete and correct for `>= $4000`, so oracles built on it are sound; it is
    only the sub-`$4000` counter that silently reads zero.  RULES: (a) never
    take `rom_writes == 0` as evidence a routine avoided ROM -- it cannot
    distinguish that from a dropped write; (b) to tell the two apart, compute
    the address in a model and check the DISPLAY outcome, which is identical
    either way, or single-step; (c) a counter that can only ever read zero is
    worse than no counter, so check a metric can move before reasoning from it.

39. **`run_until` defaults to `interrupts=True`; `Harness.call` defaults to
    `False` -- a hand-rolled call bracket runs the whole ISR inside the routine
    it was meant to isolate** (Bubble Bobble, 2026-09-14).  `harness.py:487`
    signs `run_until(targets, limit, stride, predicate, interrupts=True)`,
    because its usual job is driving frames; `Harness.call` passes
    `interrupts=False` when it brackets a routine between pushed sentinels.  A
    bracket written by hand -- push sentinels, set PC, `run_until(sentinels)` --
    inherits the *free-running* default, so an IM2 interrupt fires mid-routine
    and the whole per-frame ISR executes inside the "isolated" call.  It showed
    up here as 3 divergences in a 618-case walker differential whose fingerprints
    belonged to a DIFFERENT routine: the cached-position bytes `(+2)`/`(+3)`
    written and flag bits 5-6 set, which is the render master `$A447`, not the
    walker.  With `interrupts=False` the same 618 cases diverge 0 times.
    RULES: (a) any hand-rolled `call` bracket passes `interrupts=False`
    explicitly -- do not inherit; (b) when a differential fails, ask FIRST
    whether the changed bytes are the ones the routine under test can even
    write: bytes only another routine touches mean the harness, not the model;
    (c) a "0 divergences" result from a bracket that never re-ran with
    interrupts off has not been shown to test anything.

40. **A model can agree with the machine because the SAMPLED world makes the
    right and wrong answers equal** (Bubble Bobble, 2026-09-15).  `$AED1` above
    the HUD returns the fixed pointer `$712F` rather than a cell, and the floor
    probe dereferences it; the engine modelled that as "no cell -> no floor".
    Those disagree only when `$712E-$7131` or `$710F-$7111` have bit 5 set, and
    in `round1_48` -- the state every capture was taken from -- they are all
    `$00`.  So 618 direct calls agreed perfectly while the model was wrong, and
    every state they are all `$00`.  So 618 direct calls agreed perfectly
    while the model was wrong, and a mutation replacing the pointer with a
    sentinel survived.  What settles it is the byte NEXT DOOR: `$712E` is
    `$F0`, bit 5 SET, so a LEFTWARD look-ahead above the HUD reads a FLOOR
    where the sentinel says nothing -- unreachable only because the foot probe
    falls first.  (Written on the day, this entry cited `$712F` = `$E4` in the
    boot image; that was TRAPS #41's indexing error.  The finding itself was
    proved by POKING the bytes on the machine, so it is unaffected.)  The
    same shape hid the ledge -> hop launch (`$B20F`/`$B25E`): reaching it needs
    an enemy on a platform EDGE with the player at or below its row, and the
    sampled sweep launched 0 hops in 618 cases.  FIX: BUILD the world -- clear
    the colour shadow and the dummy page and poke them cell by cell, with the
    cell the WRONG arithmetic would have read set to the OPPOSITE value so the
    two answers cannot coincide.  128 built cases launch 61 hops and killed all
    five surviving mutations.  RULES: (a) a differential inherits the sampled
    world's coincidences -- ask what the capture state makes EQUAL, and poke it
    apart; (b) when an early-out returns a POINTER rather than a flag, find out
    which callers read the flag and which dereference the pointer, because they
    are not the same test; (c) count the DECISIONS a sweep reaches, not the
    cases it runs -- "0 of 618" hops is the number that matters.

41. **`build/image.bin` is a FULL 64K dump indexed from ZERO -- indexing it as
    `[addr - 0x4000]` silently reads a different address and manufactures
    "runtime-built" and "relocated" conclusions** (Bubble Bobble, 2026-09-15).
    The file is 65,536 bytes and `tools/adis.py` indexes it `mem[addr]`, which
    is why disassembly was always right.  A hand-rolled probe that wrote
    `img[a - 0x4000]` -- reasoning from the fact that RAM starts at `$4000` --
    reads the byte `$4000` BELOW the one it names, and gets plausible-looking
    data rather than an error, because every address in range holds something.
    It produced two confident, wrong facts in one session: that the ballistic
    arc tables at `$B59D` were absent from the image and therefore
    runtime-built, and -- following that thread -- that the whole `$F000-$FFFF`
    page was RELOCATED to `$B000-$BFFF` at init, "confirmed" by finding the
    arcs at `$F59D` (which is `$B59D` read through the same `$4000` shift) and
    by a 4045/4096 match of live `$Bxxx` against `img[a - 0x4000]` for
    `a` in `$F000-$FFFF` (which is live `$Bxxx` against image `$Bxxx` -- a
    tautology dressed as evidence).  Both tables are simply static at
    `$B59D`/`$B5BD`.  RULES: (a) read a memory image through ONE accessor that
    takes an absolute address, defined once, never an inline subtraction;
    (b) a claim that a region is "runtime-built" or "relocated" must be checked
    against the LIVE image at the SAME address before it is written down --
    `img[a] != live[a]` is the whole test; (c) when a probe and an existing tool
    disagree about the same bytes, the tool has been right for longer;
    (d) evidence that a region was copied must compare the two regions IN THE
    SAME image (here boot `$F000` vs boot `$B000`: 95 of 4096, i.e. no copy).

42. **`Harness.call` never restores SP, so a long sweep silently walks the stack
    into ROM and every later row reads "nothing happened"** (Bubble Bobble,
    2026-09-15).  `harness.py:638` pushes the six `SENTINELS` and sets SP; the
    routine RETs to the first, popping one.  Net: **10 bytes lower per call**,
    never restored.  A 2,560-case sweep therefore walks SP down 25,600 bytes.
    MEASURED on round1_48, whose SP rests at `$96D7`: it crosses `$4000` at call
    **2223** -- and call 2223 is exactly where a flyer sweep went dead.  Below
    `$4000` the sentinel writes land in ROM and are dropped, so `run_until`
    never sees one, the call burns its whole instruction limit, and the row is
    captured as before == after.  It does not throw; it produces PLAUSIBLE rows
    that say the routine did nothing.  Worse, before that it writes 12 bytes of
    sentinel into whatever live data SP happens to be passing through.
    RULES: (a) any sweep that calls more than a few hundred times must PIN SP to
    a fixed value per call, not inherit it; (b) assert the call ended on a
    SENTINEL -- `if regs[PC] not in SENTINELS: raise` -- because a limit-exhausted
    call is otherwise indistinguishable from a quiet one; (c) when a capture
    shows a run of identical "nothing changed" rows, check the STACK before the
    routine; (d) earlier fixtures in this project were not corrupted, but only
    because SP happened not to pass through anything they read -- that is luck,
    not correctness, so they were all re-captured with SP pinned.

43. **`build/image.bin` is a LIVE ROUND-80 DUMP, not the tape image, so seeding
    "tape data" from it silently ships bytes the game wrote at runtime**
    (Bubble Bobble, 2026-09-16).  Every disassembly in this project reads
    `build/image.bin`, which is right for reading CODE -- code is not
    self-modified often enough to matter, and where it is, the patch byte IS the
    thing being read.  It is WRONG for extracting a static table into the engine.
    CAUGHT BY a gate, not by inspection: the round build `$8C5E` disagreed with
    the machine on exactly one of 81 rounds.  Round 20's item byte at `$FFA3` is
    `$8F` in `image.bin` and `$95` on the tape, which sends the staged Y byte to
    `$29` instead of `$79`.  Two clusters across the 58 saved states: the early
    ones (including `boot.pkl`, taken at loader hand-over, before a single
    instruction of the game has run) hold `$95`; the boss-round ones hold `$8F`,
    and `image.bin` groups with them.
    **`build/image_tape.bin` -- the R3 rebuild from the actual tape block bytes
    -- is the authority for static data.**  An audit of every table this engine
    carries found exactly two that differ:
      - `$FFA3` above, and
      - `$8A76`, the UMBRELLA LOCK: tape `$2A` (a sentinel no 0..15 draw can
        match), dump `$06`.  `$9707` writes the sentinel at new game and `$8A49`
        writes 6 the instant a draw produces an umbrella -- so the umbrella
        spawns at most ONCE PER GAME, and by round 80 it had already gone.
        Seeding `$06` from the dump would start every new game with the umbrella
        already spent.
    The arcs `$B59D`/`$B5BD`/`$B5DD`, the `$9AC1` reset table, `$8649`, `$861D`,
    `$8839`, `$860F` and `$8A62` are byte-identical in both, so the gates built
    on them stand.  `$B5FD` differs in all 16 bytes and SHOULD: it is P1's key
    table, live state by design (TRAPS #41's companion -- type 4's arc reads one
    byte past its table into it).
    **AMENDED THE SAME DAY, and the amendment matters more than the rule.**
    `image_tape.bin` is authoritative ONLY WHERE THE TAPE ACTUALLY LOADED.  M1
    recorded its coverage as 191 of 192 pages, but that is pages, not bytes: the
    rebuild is **ALL ZEROS from `$5C00` to `$6100`** -- the Spectrum's
    system-variable area and the game's own working RAM, which no tape block
    covers.  Taking "static data" from there returns a block of nothing.
    CAUGHT ON THE FIRST USE OF THE NEW RULE: extracting the item sprite bank at
    `$5D00` from the tape image produced 832 zero bytes, and the only reason it
    did not ship was that the extractor compared against the live dump and
    reported 711 of 832 bytes differing.  A silent extractor would have shipped
    an invisible item.
    So the range was not tape data at all -- it is RUNTIME-BUILT, like `$D380`
    (built by `$BF5B`, deliberately not an asset).  PROVED three ways: the tape
    image is empty there; the bank is byte-identical in 54 of 57 saved states
    and differs only in `boot` and `title`, so it is built during the front end;
    and zeroing it in a live round-1 state produces ZERO writes back over 200
    frames, so nothing rebuilds it in play.
    RULES: (a) extract static tables from `image_tape.bin`, disassemble from
    `image.bin`; (a2) **BEFORE trusting `image_tape.bin` for a range, assert it
    is not all zero there** -- an unloaded page is indistinguishable from real
    data that happens to be zero, and an extractor that does not check will hand
    you silence; (a3) when the tape image is empty and the live states agree,
    the range is RUNTIME-BUILT: find the builder, and carry the bytes as a
    declared asset only until you do; (b) when the two disagree on a byte you
    are about to ship,
    that disagreement is a FINDING -- something writes it, and the engine
    probably has to model the write; (c) `boot.pkl` settles which value is the
    tape's, because nothing has run yet; (d) a one-row-in-81 gate failure is
    worth chasing to the byte -- this one was three layers from where it looked.

44. **A BUILT world is not immune: seeding a field with the value the routine
    WRITES there makes the write a no-op, and no amount of byte-for-byte
    comparison can see it** (Bubble Bobble, 2026-09-16).  The corpse landing
    `$8B83` does `LD (IY+8),0` and the fall `$8B4E` forces the sprite pointer
    back to `$C700` every frame.  The I9 oracle built its worlds from scratch --
    exactly what TRAPS #37 and #40 ask for -- but it built them by zeroing the
    ten-byte slot and then setting the fields it cared about, and it seeded the
    sprite as `$C700` because that is what a corpse holds.  So `(IY+8)` was
    already 0 and the sprite was already `$C700`: deleting either write changed
    nothing on the machine OR in the engine, and both mutations survived a gate
    that compared **all ten slot bytes on every row**.  Widening the comparison
    was the right fix for three other survivors and did nothing for these two.
    The cure is in the SEED, not the comparison: start `(IY+8)` at `$5A` and the
    sprite at the `$D360` FLIGHT frame, and watch the machine put both back.
    RULES: (a) for every field a routine ASSIGNS a constant to, seed that field
    to something else -- ideally the value it would hold one state earlier, so
    the world stays legal; (b) "I built the world" is not the same as "the world
    can distinguish the answers": a zeroed struct is a world in which every
    `:= 0` is invisible; (c) when a survivor names a WRITE rather than a branch,
    look at what the field held BEFORE the call, not at what the gate compares.

    (d) AND THE POISON MUST BE CHOSEN AGAINST THE OPERATION, not merely be a
    value the routine never writes.  $5A is 0101 1010, so it hides an
    `OR $40` (bit 6 already set) and an `AND $80` (bit 7 already clear);
    it hid a `SET 3`/`SET 1` pair in B10 for the same reason.  Pick the
    seed by looking at the INSTRUCTION: for an OR, clear those bits; for
    an AND, set them; for a SET, clear them.  [added by M7.7-R4, after two
    mutations survived on exactly this]

45. **A loop counter you transliterate as a `for` is a loop counter you have
    decided cannot misbehave** (Bubble Bobble, 2026-09-17).  `$C002` walks
    fourteen sparkle slots with `LD B,14` / `DJNZ`, and every instinct says
    `for (s = 0; s < 14; s++)`.  But `$C016`'s `LDI` decrements the SIXTEEN-bit
    BC, and C is a live register the caller sets: entering with C == 0 borrows
    and takes a count off B, so the walk ends one slot short and SLOT 13 IS
    NEVER SERVICED.  That is not a curiosity -- C measured at the call site
    `$8D49` is 3 in `round1`, 1 in `candycane`/`crown`/`hurryup` and ZERO in
    `fruit` and `boss`.  Worse, `$C023 LD C,A` reloads C from the serviced
    slot's X & $F8, so a run of particles at X < 8 zeroes C every time, B passes
    zero, WRAPS, and the walk leaves the table -- measured at 4,563 bytes
    written as far as $5FFE, straight through the $5D00 sprite bank.  A `for`
    loop is green through all of it.  RULES: (a) transliterate `DJNZ` as an
    EIGHT-BIT decrement with the loop's own exit test, and let the wrap emerge;
    (b) any instruction that touches the counter -- `LDI`, `LDD`, `CPIR`, a
    16-bit `DEC` -- is part of the loop control, not a memory move, so find
    every writer of B and C between the `LD B,n` and the `DJNZ`; (c) when a
    register is live INPUT from a caller you have not transliterated, MEASURE it
    across several states before calling it a constant -- one state said 3 and
    would have hidden the whole thing; (d) a runaway walk is a coverage
    instrument: this one read four bytes the engine had never loaded, and that
    is how `$5CFC..$5CFF` was found.

46. **A DETERMINISTIC REGISTER CANNOT BE SAMPLED -- any periodic schedule is a
    comb through its residues** (Bubble Bobble, 2026-09-17).  `$9811` is
    `LD A,R / AND $1F / ADD $1E`, so it should yield all 32 values 30..61.  An
    agent pass sampled it, got eight consecutive EVEN draws, and nearly concluded
    that the milestone values 41 and 61 are unreachable in simulation.  Writing
    the oracle meant to settle that, I stepped `1 + (i % 17)` instructions
    between samples and got 31 of 32 over 420 samples -- the value 38
    (`R AND $1F` == 8) missing entirely, counts running from 1 to 32.  THE
    READING PASS'S PREDICTION WAS RIGHT AND MY MEASUREMENT WAS WRONG.  R advances
    once per opcode fetch, so ANY deterministic step schedule is periodic in R --
    and so is the alternative that looks safest: driving whole frames gave
    exactly TWO distinct values over 200 samples, because `run_frames` is
    deterministic and R phase-locks to the frame parity.
    THE FIX IS NOT A BETTER SAMPLER.  Stop sampling: SET the register to all 256
    values and assert the FUNCTION, which no phase artefact can fake.  That also
    catches what sampling hides -- the answer is `(((R + 2) AND $1F) + $1E)`, not
    `((R AND $1F) + $1E)`, because `LD A,R` is `ED 5F` and reads R after its own
    TWO M1 cycles.  A sampler could never have found the +2; it shows up only
    when you control the input.
    RULES: (a) if a quantity is a pure function of machine state you can write,
    ENUMERATE the input and assert the function -- never sample it; (b) KEEP the
    degenerate sample in the fixture as evidence that the harness cannot answer
    the distribution question, so nobody re-derives a histogram from it later;
    (c) `LD A,R` and `LD A,I` read AFTER their own fetch -- count the M1 cycles
    of the reading instruction itself; (d) this is the third confident wrong
    answer this project has taken from a fixed or periodic phase, after TRAPS
    #34's scheduler and the eight all-even draws.  Where a phase is involved,
    assume the artefact until it is proved otherwise.

47. **THE LOAD IMAGE IS NOT THE RUN IMAGE, and the all-zero guard does not catch
    it** (Bubble Bobble, 2026-09-17).  TRAPS #43 said: before trusting
    `image_tape.bin` for a range, assert it is not all zero, because an unloaded
    page is indistinguishable from real data that happens to be zero.  That rule
    has a HOLE, and $5B00..$61A7 is in it.  1,704 bytes are relocated there from
    $E000 at cold start ($96A5 LDIR), so the tape image's own copy of the range
    is wrong -- by 1,385 of 1,704 bytes -- and its $6180..$61A7 is 36 of 40
    NON-ZERO, so the guard answers YES, THIS RANGE IS SOURCED and hands you
    rubbish.  The rubbish is STACK: $5BB0 does LD SP,$61A7, and 226,384 writes
    land there in 200 front-end frames, every one a ROM push.
    THE GUARD ONLY EVER ANSWERED "IS THIS SOURCED?", NEVER "IS THIS CORRECT?".
    Those are different claims and only the second one matters.
    AND THE BUILDER IS INVISIBLE WHERE YOU WOULD LOOK FOR IT: $8CC4 LD SP,$96DD
    parks the stack over $96A5..$96DC, so disassembling the LIVE dump there gives
    POP HL / RST $38 / NOP, and an analyst concludes the routine does not exist.
    Read it from the TAPE image.  TRAPS #41 was about the right INDEX; this is
    about the right FILE, and the two together mean neither image is authoritative
    on its own.
    RULES: (a) for any range you intend to ship, find its SOURCE, not just its
    bytes -- search the whole 64K tape image for the run image's content and
    require exactly ONE hit, because a match at two addresses proves nothing
    about which was copied; (b) then prove it is a COPY by poking the source and
    watching the destination follow -- a matching range and a shared origin are
    otherwise the same observation; (c) a relocation is CODE, so find it and run
    it on the machine with the destination POISONED, rather than shipping the
    destination; (d) disassemble cold-start code from the tape image and running
    code from the live dump, and expect neither to be readable in the other.

48. **AN "UNREAD" CLAIM MUST CARRY THE FRAME COUNT THAT MADE IT TRUE -- and the
    frame count is not sufficient either** (Bubble Bobble, 2026-09-18).  A
    reading pass grepped for `AND $40` and `AND $80`, found almost nothing, and
    concluded that bits 6 and 7 of the colour shadow were never read.  The grep
    was ACCURATE.  The inference was wrong: the read is `RLCA / RLCA / RLCA /
    AND 6`, a rotate that lifts those two bits into an already-doubled index --
    invisible to any search for a mask.
    A DIFFERENTIAL AGREED WITH THE GREP, AND WAS ALSO WRONG.  Flip bits 6/7
    across the whole map and run 80 frames: the game is IDENTICAL in every state
    tried, which reads as "nothing reads them".  Run 600 and it diverges at
    frame 108 -- the frame the first bubble reaches the drift stage.
    AND LENGTHENING THE RUN IS NOT THE FIX.  `round1_48` still says "unread" at
    600 frames, because no bubble ever reaches that stage there -- while
    `water`, WHICH IS THE SAME ROUND $01, diverges at frame 1.  What decides it
    is whether the WORLD EXERCISES THE PATH, not how long you run and not which
    round you picked.
    RULES: (a) a negative is a measurement and carries its conditions -- "bits
    6/7 are unread" is not a fact, "bits 6/7 are unread over 80 frames of
    round1_48" is; (b) a GREP CANNOT PROVE A NEGATIVE about a value that can be
    rotated, shifted, added or compared into use -- only a differential can, and
    only with a control; (c) ALWAYS RUN THE CONTROL: the same rig mutating bit 5
    diverges at frame 0 or 1 everywhere, which is the only thing that makes the
    bits-6/7 result mean anything; (d) when a differential says "no difference",
    ask what event would have to happen for a difference to appear, and then
    check that the run is long enough AND the world arranged for it to happen.

49. **ONE CELL POSITION IS NOT A TEST OF A CELL WALK -- and the alignment you
    happened to pick decides which register you think it reads** (Bubble Bobble,
    2026-09-18).  `$AE81` probes up to three consecutive colour-shadow cells.
    Six mutations survived a battery over a case list that varied the cell's
    VALUE thoroughly and its POSITION not at all, and between them they covered
    every structural property of the walk: the `INC L` being EIGHT BIT, the
    second and third cells being tested with the caller's mask, the marker's
    mask being `$1F` rather than `$0F`, and -- the one that was an ENGINE
    DEFECT rather than a gate gap -- WHICH REGISTER GATES THE THIRD CELL.
    `$AE86 LD D,E` overwrites D with the incoming X three instructions before
    `$AE92 LD A,D / AND 6`, so the gate is on X.  I transliterated it as Y, and
    it passed everything, because every case I drove had X and Y BOTH 8-ALIGNED
    and `x & 6` and `y & 6` were both zero.
    AND THE WRAP TOOK THREE TRIES.  The end of a ROW is not a page boundary:
    `x=$F8, y=$60` gives base `$F99F`, and an eight-bit and a sixteen-bit INC
    agree there.  `y=$38` gives `$F8FF`, where they differ.  Then the DECOY
    proving it was folded onto the wrap target BY MY OWN SEEDING FORMULA, which
    deliberately addressed cells the way the machine does -- it only works as an
    ABSOLUTE poke, claim at `$F900` with `$F800` empty.
    RULES: (a) for any routine that WALKS, vary the starting POSITION as hard as
    the contents -- page boundaries, both alignments, and each visited cell
    filled alone; (b) when two registers could be the source of a test, find a
    case where they DIFFER before believing either -- coordinate pairs are the
    classic trap because play tends to align both; (c) a helper that seeds a
    world "the way the machine addresses it" CANNOT seed the case that proves
    the addressing -- that one needs an absolute poke; (d) a marker or index
    whose live range is narrower than its field (here 1..12 in five bits) hides
    the mask: drive a value that uses the top bit.

50. **A CALL WHOSE EFFECT IS IDEMPOTENT OVER THE DEFAULT WORLD CANNOT BE SEEN
    TO HAVE RUN -- and a WALK IS NOT PROVED BY ITS TARGETS** (Bubble Bobble,
    M7.7-H1, 2026-09-18).  Two mutations survived a gate that looked complete.
    (a) DELETING a `CALL` survived: the tail's `$98A4 CALL $79AC` maps colour
    cells whose `$38` bits are set to `$20`, and over a fresh world every cell
    was ALREADY `$20`, so "it ran" and "it did not" were the same end state.
    The fix is to seed the input with a value the callee CHANGES (`$57`), which
    costs one line and turns an invisible call into a one-byte assertion.
    (b) Walking TWENTY pointers instead of nineteen survived a gate that
    asserted all NINETEEN NAMED TARGETS end zero -- because the twentieth write
    lands on a byte NOBODY NAMED, and no check over the named set can see it.
    The fix is to COUNT: a recording Proxy over the RAM image makes the write
    count itself the assertion, which is the only thing that bounds a loop from
    above.
    RULES: (a) before asserting that a routine ran, ask what the world would
    look like if it had NOT -- if the answer is "the same", the seed is wrong,
    not the routine; (b) for any loop, gate the COUNT as well as the effects,
    because effect checks are existential and only a count is universal;
    (c) this is the mirror of #44 -- there the SEED made a write invisible, here
    the DEFAULT made a whole call invisible.

51. **A SELF-MODIFICATION'S LIFETIME IS A SEPARATE FACT FROM ITS EFFECT, AND
    NEITHER INCREMENT THAT TOUCHES IT CAN SEE IT** (Bubble Bobble, M7.7-H1,
    2026-09-18).  `$88E0` pins the item generator by zeroing an `INC A` OPCODE
    at `$8BA0`; a later increment measured the generator reading that opcode.
    Both were right and neither could observe that `$9891 LD HL,$3CFF /
    LD ($8B9F),HL` puts the counter AND the opcode back at every round
    transition -- so the pin lasts EXACTLY ONE ROUND.  It took a third
    increment, spanning both, driving the pin in and the transition after it.
    RULE: when a routine writes into code, do not stop at "who reads it".  Ask
    WHO RESTORES IT and WHEN, and gate the expiry as its own negative -- a port
    that never restores looks identical for one round and diverges forever
    after.  Watch for a SIXTEEN-BIT store spanning an operand and the opcode
    next to it: it restores two facts in one instruction and reads as one.

52. **A ROUTINE WITH NO CALLER IS NOT DEAD -- IT IS FALLEN INTO; AND A COUNT
    QUOTED FROM ONE ROUND IS A SAMPLE** (Bubble Bobble, M7.7-H6, 2026-09-18).
    `$7DD6` computes a per-round value that 49 of 81 rounds depend on, and there
    is no `CALL` or `JP` to it anywhere in 64K -- the routine above it simply
    runs off its end.  A caller scan found nothing and the reading pass filed the
    whole subsystem under the previous routine's name for two increments.
    The same increment then caught its own version of the second half: the plan
    carried "70 phantom self-modifications" as a fact, and 70 turned out to be
    the MAXIMUM FOR ONE GROUP.  The real count runs 0 to 106 and is a function of
    where the round sits in its list.
    RULES: (a) when a scan for callers comes back empty, disassemble BACKWARDS
    from the entry before concluding anything -- fall-through is invisible to
    every reference search; (b) a count measured on one round, one slot or one
    frame is a sample until something shows it is constant, so gate the RANGE and
    name the variable it depends on; (c) a subsystem inherits the name of
    whatever routine precedes it, which is exactly how it stays unmodelled.

53. **WHEN TWO UNRELATED TABLES ENCODE THE SAME MAPPING, THAT AGREEMENT IS THE
    PROOF -- AND AN INDEX CAN RUN OFF ITS TABLE ON PURPOSE** (Bubble Bobble,
    M7.7-H6, 2026-09-18).  Eight randomised element classes fold onto six EXTEND
    letters.  Read one way, `$B80E`'s bit masks say classes 11 and 12 alias 5 and
    10.  Read another way -- a sprite-pointer table at `$C068` that nothing
    connects to `$B80E` -- classes 11 and 12 point at the SAME TWO GLYPHS as 5
    and 10.  Either reading alone is an inference; together they are a
    measurement, because a coincidence would have to hold in two encodings at
    once.
    And in the same table: class 0 does `SUB 2 / ADD A,A` and indexes **252 bytes
    past** an eleven-entry table, on 31 of 81 rounds.  A port that "fixes" that by
    clamping the index is not more correct, it is different.
    RULES: (a) look for a SECOND encoding of any mapping before believing the
    first, and prefer a pair of tables that do not know about each other;
    (b) compute what every reachable input does to an index, including the ones
    below the table's base -- an out-of-range index is behaviour until measured
    otherwise; (c) never repair an original's overrun inside a faithful port
    without a declared flag and a test on both sides.

54. **A GATE THAT COMPARES THE CELLS IT EXPECTS TO BE WRITTEN IS EXISTENTIAL --
    ADD THE COUNT** (Bubble Bobble, M7.7-H1/H6/H7, 2026-09-18).  The same gap
    three increments running, in three disguises.  H1: a pointer walk of TWENTY
    instead of nineteen -- every named target still ends correct, and the
    twentieth write lands on a byte nobody named.  H6: a list walk that scans a
    FIFTH list -- every phantom write inside the table still matches, and the
    extra ones fall outside the range the log was FILTERED to.  H7: a map painter
    running 24 rows instead of 22 -- all 616 cells are painted correctly and two
    more rows go past the end of the buffer into a page another subsystem uses.
    Each survived a battery, and each was invisible for the same reason: the
    assertion quantified over the writes I predicted, so it could not see a write
    I had not.
    RULES: (a) for anything that WALKS or PAINTS, count the writes and assert the
    total, not just the values at the addresses you expect; (b) never filter a
    recording log to the region under test -- log everything and make the region
    an ASSERTION on the addresses; (c) the machine-side oracle usually catches
    this for free, because a write-watch has no expectations -- so mirror the
    same count on the ENGINE side, which is where the mutation actually lands.

55. **"CAN THIS GATE SEE THE THING IT IS NAMED AFTER?" IS ITS OWN MEASUREMENT --
    AND SYMMETRY CAN MAKE THE ANSWER NO** (Bubble Bobble, M7.7-H7, 2026-09-18).
    A map record is painted half-width and MIRRORED, and I set out to count the
    rounds on which the mirror is observable.  My first metric counted rounds
    whose finished map is left-right ASYMMETRIC.  It returned 30 -- which is
    exactly "the 30 rounds that are not mirrored at all", because a mirrored
    round is symmetric BY CONSTRUCTION.  The number was real, the question it
    answered was not the one asked, and it would have been quoted as evidence for
    the mirror while being evidence only against the other class.
    The right question was narrower: the mirror's REVERSAL is separable only on a
    mirrored round with a NON-PALINDROMIC row.  That count is 49 of 51 and 3,352
    cells -- and a THIRD competing model turned out to be refused by arithmetic
    rather than by data at all.
    RULES: (a) before quoting a separability count, name the two models it
    separates and check the count is not a tautology about one of them; (b) when
    a transform imposes a symmetry, that symmetry destroys the evidence for the
    transform -- look for the cases that escape it; (c) enumerate every competing
    model explicitly, because one of them may be excluded by a size or a bound
    instead of by a measurement, and that is a stronger result worth stating.

56. **A LOOP'S CURSOR ADVANCE CAN LIVE IN THE CALLEE** (Bubble Bobble, M7.7-H8,
    2026-09-18).  `$833A` is an eleven-iteration loop over a row-address table,
    and its body contains NO `INC IX` anywhere: the advance is `$8375 INC IX /
    INC IX`, sitting inside the subroutine it CALLs, after that subroutine's own
    DJNZ and before its RET.  Read the loop on its own -- which is how anyone
    reads a loop -- and it says the wall is redrawn over the same two char rows
    eleven times.  I had transliterated exactly that before a register trace
    showed IX running `$FD44`, `$FD48`, `$FD4C`: four bytes an iteration, because
    each of the two CALLs moves it twice.
    RULES: (a) when a loop's induction variable never changes in its body, the
    callee is mutating it -- read every CALL to the end of its RET, not to its
    apparent purpose; (b) a subroutine that advances its caller's cursor is a
    second return value with no name, so gate it by TRACING THE REGISTER across
    iterations rather than by reading; (c) this is the dual of #52 -- there a
    routine was entered by fall-through, here it exits having changed state the
    caller owns.  Control flow and data flow both leak across boundaries that
    look closed.

57. **AN IDEMPOTENT SIDE EFFECT NEEDS A WRITE COUNT; AND "CANNOT WRAP" IS A
    THEOREM YOU MUST ACTUALLY PROVE** (Bubble Bobble, M7.7-H8, 2026-09-18).  Two
    kinds of survivor from one battery, both about what a state comparison cannot
    express.
    (a) `$82C5` patches three bytes to fixed values.  It fires ONCE, after the
    first row of a 22-row scan.  A mutation making it fire on EVERY row survives
    any check on those three bytes, because the second write puts back what the
    first did -- only counting the writes (6, not 66) separates them.
    (b) Three other survivors were PROVABLE EQUIVALENTS, and proving it took
    enumeration rather than intuition: two eight-bit adds cannot wrap because the
    row-table low bytes top out at `$E0` against a column of 29, and the second
    site reads every OTHER table entry, whose low bytes are `$40/$80/$C0/$00`.
    Worth the enumeration in both directions: a comment in my own code claimed
    the second add "can wrap", and it cannot.
    RULES: (a) for any effect that is idempotent -- a patch to a constant, a
    clear, a flag set -- gate the COUNT, because the end state is the same under
    once, twice and never-again; (b) before withdrawing a mutation as equivalent,
    ENUMERATE the reachable inputs and show the branch is unreachable, then write
    the proof next to the code as TRANSCRIBED-NOT-EXERCISED; (c) enumeration also
    catches the opposite error, a comment asserting a wrap that cannot happen.

58. **AN OPCODE SCAN FOR `CALL` IS NOT A SCAN FOR REACHABILITY** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  A reading pass established that the HUD painter
    `$7FC0` had exactly one reference -- a `CALL z` gated on the round number --
    and concluded the HUD is painted on round 1 and never again.  It scanned for
    `CD` and `CC`.  There is also a `C3`: `$9998 JP $7FC0`, a TAIL CALL, ending
    the player-join routine.  The HUD is repainted on every join, and a port
    built to the original claim shows a stale HUD for the whole of a two-player
    game.
    RULES: (a) scan for the whole family -- `CALL`, every conditional `CALL`, `JP`
    and every conditional `JP`, `RST`, and the bare ADDRESS as a word (for jump
    tables and pushed return addresses); (b) a tail call is invisible to anyone
    looking for a call, and it is the normal way a routine ends when its last act
    is to delegate; (c) this is the third member of a family: #52 (entered by
    fall-through, no reference at all), #56 (leaves having moved its caller's
    cursor), and now this -- reached by a JP that a call scan never sees.

59. **A DESTRUCTIVE EXPERIMENT MUST RESTORE WHAT IT DESTROYS** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  One measurement in this increment exists to prove a
    loop guard is load-bearing: poke the counter and watch the copy run away over
    263 bytes.  It restored the poked operand and not the 263 bytes -- which
    happen to be the very record the NEXT measurements read.  Every controlled
    measurement afterwards was taken in the wreckage, and reported a mask of
    non-zero bytes where the machine has zeros.
    It was caught by an ENGINE DIFFERENTIAL and could not have been caught by a
    census: the write COUNTS matched exactly, 109 against 109, while the values
    from the fourth cell onward were fiction.
    RULES: (a) snapshot and restore any region a destructive experiment can
    reach, and size the snapshot from the WORST case, not the shipped one;
    (b) order matters -- put destructive probes last, or rebuild between them;
    (c) when an oracle and an engine disagree, single-step the real machine
    before assuming the engine is wrong: here the trace showed the engine right
    and the oracle contaminated; (d) a matching write count is not agreement.

60. **A CONTROLLED WORLD IS ONLY CONTROLLED WHERE YOU SEEDED IT -- AND THE
    MODELS YOU WANT TO SEPARATE DECIDE WHICH WORLDS TO BUILD** (Bubble Bobble,
    M7.7-H9, 2026-09-18).  Two lessons from one battery.
    (a) A Spectrum character row is EIGHT PAGES: a row at `$50E0` walks H from
    `$50` to `$57`.  Seeding `$5000..$50FF` controls one row in eight and leaves
    seven reading whatever the previous world left, on both sides of the
    differential.
    (b) Six mutations survived not because the gate was weak but because the
    WORLD was tame.  Lives of 3 cannot separate "clamp at 5" from "clamp at 4"
    from "no clamp" -- all three agree below the threshold.  An attribute whose
    paper is 3 never reaches the branch that fires when paper equals ink.  A
    six-bit mask cannot show that a loop runs six times rather than eight.
    RULES: (a) seed every page a walk can reach, and derive the extent from the
    addressing, not from where you expect writes to land; (b) for each competing
    model, name the input that separates it and BUILD THAT WORLD -- a gate over a
    typical world tests typical behaviour only; (c) a clamp, a threshold and a
    loop bound are all invisible from inside their normal range, so drive them
    from outside it.

61. **A DECLARED DEPARTURE CAN HIDE THE BUG IT SITS ON TOP OF** (Bubble Bobble,
    M7.7-H10, 2026-09-18).  A sprite generator indexes a pointer table with an
    EIGHT-BIT offset, so one input runs 252 bytes past the table and fetches a
    pointer nobody chose.  That overrun is real behaviour on 31 of 81 rounds and
    was gated two increments earlier.  But the pointer lands in the machine ROM,
    which the port does not ship, so the port substitutes nothing there -- and a
    mutation making the index SIXTEEN-BIT survived a battery, because the
    sixteen-bit index lands on a DIFFERENT ROM pointer that the port also
    substitutes nothing for.  Two different wrong answers, one identical output.
    RULES: (a) wherever a departure replaces a computed value with a constant,
    the computation upstream of it becomes unobservable -- gate that computation
    DIRECTLY, by exposing it, rather than through its effect; (b) audit every
    declared departure for what it stops you from being able to see, and write
    that down beside the departure; (c) a test that recomputes the quantity it is
    checking is testing itself -- ask the engine for the value.

62. **DEAD WORK IS STILL BEHAVIOUR, AND ONLY A COUNT CAN SEE IT** (Bubble
    Bobble, M7.7-H10, 2026-09-18).  A routine clears 384 bytes and then
    immediately overwrites all 384 from a table.  The clear cannot be observed in
    the final state by any comparison, at any address, ever.  It is nevertheless
    the machine's behaviour, it costs real time, and it exists for a reason worth
    recording: the clear is 384 rather than the 128 the source asks for, because
    the subroutine it calls twice is a DJNZ loop that exits with B = 0.
    RULES: (a) transliterate dead work and gate it by WRITE COUNT, which is the
    only instrument that can see it; (b) a `LD B,n / CALL / CALL` pair where the
    callee decrements B to zero is a doubling, not a repetition -- this is the
    third TRAPS #45 site in this port and they have all been counted wrong at
    first reading; (c) when a routine's effect is invisible, ask what it costs in
    time before deleting it, because a timing model will notice later.

63. **A GATE WHOSE CALL PATH DOES NOT INCLUDE THE CODE UNDER TEST** (Bubble
    Bobble, M7.7-H11, 2026-09-18).  A driver runs a preparatory step and then a
    four-iteration loop before its main work.  The state after those is
    observable only at that moment, because the main loop scrolls it off the
    screen, so the gate brackets it there -- and to build the expected state it
    calls the preparatory routine and the loop body DIRECTLY.  A mutation to the
    driver's own loop then survives: the routine it corrupts is correct on both
    sides and nothing the gate calls goes through it.
    The remedy is structural, not additional: EXTRACT the loop into a method that
    the driver calls and the gate calls, so there is one path and both ends use
    it.  That also makes the machine's own grouping explicit in the port.
    RULES: (a) after writing a gate, trace the call path from the assertion to
    the mutated line -- if the mutated line is not on it, the gate cannot fail;
    (b) prefer extracting a named step over reassembling it in the test, because
    a reassembly is a second implementation that can agree with the machine while
    the first one does not; (c) this is distinct from every other gap in this
    chain -- not an unobservable effect, not a tame world, not a filtered log,
    but a test that never reaches the code.

64. **"LATER OVERWRITTEN" IS RECURSIVE: CHOOSE THE BRACKET PER CLAIM** (Bubble
    Bobble, M7.7-H11, 2026-09-18).  H2 established that a scroll's finished
    screen is repainted from a shadow immediately afterwards, so the gate must
    compare MID-SCROLL.  Built that way, two mutations still survived -- deleting
    the separator row the scroll begins with, and making its four-step pre-roll
    push rows it should not.  Both are invisible at the END of the scroll for the
    same reason the whole scroll is invisible after the repaint: the band they
    write is scrolled off the top before the animation finishes.
    The bracket had to move inward a second time, to the instant after the
    pre-roll.  There is no "the" mid-point: each claim has its own last moment of
    visibility, and a single sampling point chosen once per increment will be
    wrong for some of them.
    RULES: (a) for every claim, ask when its evidence is destroyed and bracket
    just before THAT, not before some other claim's destruction; (b) a routine
    whose output is consumed by a later stage of the same routine needs its own
    bracket, not its caller's; (c) if two claims have different last-visible
    moments they need two brackets, and saying so costs less than a battery.

65. **WHEN A PLAN NAMES A TOOL TO EXTEND, THAT TOOL'S DOCSTRING IS A LIST OF
    TRAPS ALREADY PAID FOR** (Bubble Bobble, M7.7-H12, 2026-09-18).  The
    increment plan said "extending tools/settle.py".  I wrote a fresh driver
    instead, and paid for two faults that settle.py documents in its own opening
    comment: a direct call leaves PC parked on a SENTINEL, which is game DATA, so
    free-running frames from there executes bytes that are not code until an
    interrupt rescues the machine (every enemy coordinate came back as 2, a
    counter never armed, a player drifted); and an armed window MUST be paired
    with a control that holds the same key with the mechanism disabled, because a
    player never asked to move is frozen either way.
    RULES: (a) before writing a new oracle, read the docstring of any tool the
    plan names -- it is a record of the specific ways this machine has already
    fooled someone; (b) prefer extending to rewriting even when the rewrite looks
    smaller, because the cost of a rewrite is invisible until it reproduces a
    solved bug; (c) an oracle's docstring is a deliverable, not decoration: write
    down what made the obvious world useless, because the next increment will
    face the same world.

66. **AN ORACLE TABLE AND AN ENGINE METHOD CAN BE DIFFERENT FUNCTIONS**
    (Bubble Bobble, M7.7-H12, 2026-09-18).  A machine routine takes ONE
    coordinate and answers "is it in the band?".  The engine method that calls it
    takes an ENTITY and answers "is any of its FOUR coordinates in the band?".
    Comparing the method against the routine's table row for row fails on every
    row where the entity's Y is outside but its Y+16 is inside -- and the failure
    looks exactly like an engine bug.
    RULES: (a) when a gate compares an engine method to a machine measurement,
    state what each one's INPUT is and check they are the same thing; (b) if they
    are not, either restrict the comparison to inputs on which the two agree AND
    say why, or gate the wider behaviour separately -- H12 does both; (c) a
    failing gate is not evidence of an engine fault until the comparison itself
    has been audited.


67. **A SHIPPED STATE CAN RESUME MID-ROUTINE** (Bubble Bobble, M7.7-H13
    constructive pass, 2026-09-19).  `build/bottle.pkl` was captured with
    A = `$0D`, DE = `$9603` and a stack top of `$8A5D`: resuming it COMPLETES a
    bottle spawn that was already half done, with the type the machine had
    before any poke.  Every `$8609` control in that cluster showed a spurious
    frame-0 spawn for exactly this reason, and it looks like the poke causing it.
    RULES: (a) before attributing anything to a poked input, print the saved PC
    and the top of the stack -- a state is a MOMENT, not a scene; (b) a state
    captured inside a CALL owes its caller a return, so the first frames after a
    resume run code the experiment did not choose; (c) if a control and its
    experiment share a captured mid-routine state, they share its tail too, and
    the difference between them is not what the poke did.

68. **A DISASSEMBLY THAT STARTS ONE BYTE LATE INSIDE AN `FD` PREFIX INVENTS A
    PLAUSIBLE INSTRUCTION** (Bubble Bobble, M7.7-H13 constructive pass,
    2026-09-19).  `$9AFD`, `$9DF2` and `$9DFC` were quoted in three separate
    documents as `LD HL,$5B00`.  No such instruction exists: the real ones are
    `$9AFC`/`$9DF1 LD IY,$5B00` and `$9DFB LD IY,$5B0A`, and the phantom is the
    `21 00 5B` that follows the `FD` prefix byte.  The wrong reading is not
    nonsense -- it is a register the routine plausibly uses, which is why it
    survived three readings.
    RULES: (a) disassemble from a known entry, never from an address a grep
    landed on; (b) if a quoted instruction's address is one past an `DD`/`FD`/
    `ED`/`CB` byte, it is the prefix's operand and the instruction is fiction;
    (c) a byte-pair census over 64K finds operands as readily as opcodes -- see
    #58 and the `$8309` miscount in the same pass.

69. **`Harness.call`'s SENTINEL LIST INCLUDES `$FE02`, WHICH IS THE BOSS
    SPRITE'S OWN BYTES** (Bubble Bobble, M7.7-H13 constructive pass,
    2026-09-19).  A sentinel return parks PC on data in this area, so
    single-stepping on from a `call()` return executes pixels.  The same shape
    as #42's SP fault and as `settle.py`'s docstring warning, in a new place.
    RULES: (a) after `call()`, PC is a SENTINEL and nothing may be stepped from
    there -- restore PC (and SP) explicitly before free-running; (b) when a tool
    parks PC on a sentinel inside game memory, say so where the tool is used,
    not only where it is defined.

70. **A MASK MUTATION ON A TYPED-ARRAY STORE CANNOT FAIL** (Bubble Bobble,
    M7.7-H13-B0, 2026-09-19).  `ram[$FEC8] = (ram[$FEC8] + 1) & 0xFF` into a
    `Uint8Array` -- mutating the `& 0xFF` to `& 0xFFFF` changes NOTHING, because
    the container already truncates.  The battery reported it as a SURVIVOR, and
    a survivor reads as a hole in the gate rather than as a mutation that cannot
    express the bug.  The same is true of every `& 0xFF` on a store into `ram`,
    and this port has hundreds.
    RULES: (a) a mutation must be able to CHANGE THE VALUE THAT LANDS -- on a
    `ram[]` store the mask is enforced by the array, so mutate the SEMANTICS
    instead (B0 replaced it with "the counter is driven by the frame, not by the
    pass", which dies immediately); (b) when a mask mutant survives, check the
    CONTAINER before you go looking for the missing assertion; (c) masks on
    LOCALS and on 16-bit pairs are real and must still be mutated -- it is the
    8-bit store into the byte image that is free.

71. **AN INTERVAL CLAIM MUST NAME THE WINDOW, AND A SHORT WINDOW HIDES THE RARE
    STATE** (Bubble Bobble, M7.7-H13-B0, 2026-09-19).  The plan's headline --
    "the PASS interval is exactly 32 in every interval of both runs" -- is true
    over 300 frames and FALSE over 900: the intervals are 32, 35, 36, 38
    contended and 32, 38, 47 uncontended, because `$A9FC`'s involution LATCHES
    13 and 21 times in 900 frames and a latched pass does not tick the divider.
    What is exactly 32, in both runs, is the interval in TICKS.
    RULES: (a) an interval or period claim carries the window it was measured
    over, and "every interval" means every interval IN THAT WINDOW; (b) if any
    state in the loop is rare, the window must be long enough to contain several
    of them -- count the rare state and say how many the window held; (c) when a
    count and a derived count disagree (passes vs ticks), the ONE that is exact
    names the real unit.

72. **WIRING A ROUTINE IS HOW A MISSING RESET GETS FOUND** (Bubble Bobble,
    M7.7-H13-B0, 2026-09-19).  `$C002` had been transliterated and gated in
    isolation for a whole increment (I10) and was correct.  The moment B0 wired
    it into the main-loop chain it wrote 642 display bytes on a still round --
    because `$5CE0`, its table, is INSIDE the relocated block `$5B00..$61A7`, and
    the port's `reset()` had never run the round build's own `$BF39` clear.  The
    machine has the table ZERO on `round1_48`, `r20_48` and `boss` alike, and
    carries `(IY+3) = 2` in every bubble slot -- which is `$BF4B`, one
    instruction inside the very chain that clears it.
    RULES: (a) a routine gated in isolation is gated over the world the GATE
    built, not over the world the engine has -- wiring is a separate act with its
    own findings; (b) when a newly wired routine misbehaves, compare the engine's
    world against a captured machine world at the same moment BEFORE touching the
    routine; (c) fix it with the machine's own routine, not with a fill: the
    clear belongs to the build, and calling `poolClearChain()` also restored
    `(IY+3) = 2`, which a fill would have missed.

73. **A MUTATION WHOSE ANCHOR DRIFTS IS SILENTLY DEAD, AND THE BATTERY'S HEADLINE
    COUNTS THE LIST RATHER THAN THE LIVE ONES** (Bubble Bobble, M7.7-H13-B1,
    2026-09-19).  I10 gave `itemBlit` a `rec` and an `or_` parameter.  SEVEN I2
    mutations anchored on the old call shape stopped matching that day and were
    reported as `!! ANCHOR 0x` -- and the increments after it went on quoting
    "1038/1038 killed, ZERO survivors", which is the length of the LIST.  Seven
    behaviours had no mutation coverage for eleven increments.
    RULES: (a) report three numbers -- LISTED, LIVE (anchor found), KILLED -- and
    never let LISTED stand in for LIVE; (b) an anchor failure is a RED result,
    not a warning: it means a behaviour that used to be gated no longer is;
    (c) when a routine's SIGNATURE changes, grep the battery for its name in the
    same edit -- the anchors are source text and they rot exactly like a comment.

74. **CENSUSING ONE OPCODE FORM UNDERCOUNTS REFERENCES** (Bubble Bobble,
    M7.7-H13-B1, 2026-09-19).  `web/game.js` said of `$7FC0`: "its sole reference
    in both images is `CC C0 7F` (CALL z), so A PORT THAT NEVER BUILDS ROUND 1
    HAS NO HUD AT ALL".  A census of the ADDRESS -- the two bytes `C0 7F`, with
    the preceding byte classified -- finds `$7F58 CALL z` AND `$9998 JP`, the
    mid-game join's tail jump, so the HUD is repainted whenever a second player
    joins on ANY round.  The same shape one level down: a `32 C9 FE` census of
    `$FEC9`'s writers finds two and there are three, because `$8CFC` loads the
    address into HL and INCs through it.
    RULES: (a) census the ADDRESS and classify the byte in front of it; never
    census opcode-plus-address as one pattern; (b) the forms that hide are the
    conditional calls, the tail JPs and the pointer loads (`LD HL,nn` then an
    indirect write) -- all three are in this game; (c) a sentence of the form
    "its sole reference is X" is a claim about a SEARCH, and the search must be
    stated with it.

75. **AN `OR` AGAINST A PAGE BASE ABSORBS THE CARRY A MASK IS THERE TO CATCH**
    (Bubble Bobble, M7.7-H13-B2, 2026-09-19).  The machine walks an attribute
    row with `INC L`, so the address is `(H << 8) | L` with L EIGHT BIT.
    Transliterated as `ram[page | l]` with `l = (l + 1) & 0xFF`, the mask looks
    load-bearing and is not: every attribute page has bit 8 set, so
    `$5900 | $100` is `$5900` and a sixteen-bit L wraps anyway.  The mutation
    that removed the mask wrote all eleven cells in exactly the right places and
    SURVIVED.  Written as `ram[(page + l) & 0xFFFF]` the same mutation dies at
    once.
    RULES: (a) address arithmetic that models an eight-bit walk must ADD, not
    OR -- the OR silently forgives the carry; (b) this is TRAPS #70 one level
    up: there the CONTAINER masked, here the OPERATOR does, and in both cases
    the surviving mutation is evidence about the TRANSLITERATION, not about the
    gate; (c) when a mask mutation survives, write the same expression two ways
    and see whether they can ever differ before looking for a missing assertion.

76. **A GUARD CAN READ A BYTE THAT BELONGS TO NOBODY** (Bubble Bobble,
    M7.7-H13-B2, 2026-09-19).  `$80FA`'s award computes `HL = 10*A` and adds
    `$FD7D`, so the `BIT 7` guard lands on `$FD87` for player 1 and `$FD91` for
    player 2 -- and on **`$FD7D`** for index 0, three bytes BELOW the entity
    table.  It reads `$A0` on every state on disk, so index 0 always passes a
    guard that is not a player's flag at all.  The port carries zeros there, so
    the award silently did nothing for index 0 and the gate comparing it to the
    machine failed on a byte nobody had ever named.
    RULES: (a) when an index scales a base, ENUMERATE the addresses it produces
    for every index the code accepts, not just the ones play uses; (b) a guard
    outside the structure it appears to guard is a fact about the DATA, not
    about the player -- record the value and where it comes from; (c) an index
    unreachable in play still needs its row, and the world for it is SEEDED from
    the machine rather than invented in the reset.

77. **A UNIFORM SOURCE CANNOT TEST AN ADDRESS COMPUTATION** (Bubble Bobble,
    M7.7-H13-B4, 2026-09-19).  `$9D4C` reads BIT 5 of the colour shadow and
    writes one of two attributes.  Every natural boss row is UNIFORM -- all
    sixteen cells clear on `boss`, `bosskilled` and `bossspawn` -- so a port
    reading that bit from the WRONG ADDRESS (wrong stride, wrong page wrap, the
    display attributes instead of `$F8xx`) produces byte-identical output on all
    of them AND on both uniform controls.  Only one captured state discriminates
    at all, and only in two cells of sixteen.  The H13 falsification pass caught
    this before the oracle existed.
    RULES: (a) when a routine READS a table and the table is uniform, the read's
    ADDRESS is untested no matter how many states are driven -- make the source
    POSITION-DEPENDENT: a checkerboard `bit = (row + col) & 1` for a flag, a
    `(addr * k) & $FF` fill for a byte copy, a distinct value per row for a blit;
    (b) the test to apply to a drafted world is "which cells would differ if the
    address were wrong?" -- if the answer is "none", the world is decoration;
    (c) this is why B4 ships checkerboards and multiplied fills rather than the
    states the game produces.

78. **A POINTER SWEEP FINDS DATA THE PORT NEVER SHIPPED** (Bubble Bobble,
    M7.7-H13-B4, 2026-09-19).  The boss's colours come from a seven-slot array
    of sixteen-byte blocks at `$A890 + 16C`, read by an `LDD` walk through a
    self-modified pointer.  Poking that pointer over every C the routine accepts
    found the engine writing SIXTEEN ZEROS where the machine writes the boss's
    attributes: `$A881..$A8C0` is tape data nobody had extracted, and no gate
    that compared only the write ADDRESSES could ever have noticed.
    RULES: (a) a blit gate must compare VALUES as well as addresses, and the
    source must be non-uniform (see #77); (b) when a routine reads through a
    self-modified pointer, sweep the pointer over every value its writers can
    produce -- and over the TAPE RESIDUE, which here is not of the array's form
    at all and makes the walk read the spawn routine's own source table;
    (c) three of the seven slots are real data, one IS a live array the spawner
    writes, and three point into the draw routine's own opcodes: a sweep says
    which is which, a single captured value says nothing.

79. **A SELF-MODIFIED INSTRUCTION PAIR HAS MORE STATES THAN ITS TWO ENDPOINTS,
    AND THE ONES BETWEEN ARE ARBITRARY OPCODES** (Bubble Bobble, M7.7-H13-B5,
    2026-09-19).  `$A98F/$A990` live inside `$A97D`'s control flow and decay from
    `37 C9` (SCF / RET -- every position is an overlap) to `00 00` (NOP / NOP --
    fall through to the real comparator).  They are decremented ONE AT A TIME by
    `$AAA1 DEC (HL)`, so the pair walks through two hundred-odd intermediate
    OPCODE pairs, and they are not all the same function: `37 00` falls through
    and behaves as the comparator, but **`00 C9` is NOP / RET and returns with
    the caller's carry -- "always miss", a third answer neither endpoint gives**.
    Measured: 5, 2, 2 and 0 hits out of five probes for `37 C9`, `37 00`,
    `00 00` and `00 C9`.
    RULES: (a) drive all four CORNERS of a self-modified pair, not the two the
    images happen to hold -- "non-zero" is not a state; (b) a port that ships no
    Z80 cannot execute the intermediates, so PROVE they are unreachable (here:
    the first byte reaches zero at frame 137 while the second is still near
    `$89`, and the only other consumer needs a round build that cannot happen
    inside the 429 frames the decay takes) and DECLARE the gap in the gate;
    (c) the proof is about the DECAY ORDER and the CONSUMER's reachability, and
    both have to be measured -- neither follows from reading the code.

80. **A PUSHED RETURN ADDRESS IS PART OF THE ROUTINE, AND IT CAN DO A SECOND JOB
    THE BODY DOES NOT HINT AT** (Bubble Bobble, M7.7-H13-B6, 2026-09-19).
    `$93DC` opens by PUSHing `$93F4` and then clears the ISR's even-branch gate
    (`$93E0 XOR A / LD ($FEC5),A`).  `$93F4` is `XOR A / LD ($FFF9),A / INC A /
    LD ($FEC5),A / RET`: it clears the request AND **sets the gate back to 1**.
    Transliterating the body without the pushed return leaves the gate dark
    for ever, the bubble manager never runs again, and the failure surfaces four
    subsystems away -- in this case in M7.5's blow gates, which is how it was
    caught.  MEASURED over 60 frames: `$93E1` writes 0 and `$93F9` writes 1, 523
    times each, and nothing else touches the byte.
    RULES: (a) when a routine PUSHes a literal before doing anything, read that
    address as part of the routine -- it is the epilogue, and no CALL-graph scan
    associates it with the caller; (b) a byte cleared at the top of a routine and
    restored at the bottom is a HAND-OFF, not a reset: transliterate both halves
    or neither; (c) if a new increment breaks a gate in an unrelated subsystem,
    suspect exactly this before suspecting the gate.

81. **AN INSTRUMENT MUST COVER EVERY WRITE PATH OF THE THING IT MEASURES**
    (Bubble Bobble, M7.7-H13-B6, 2026-09-19).  The bolt's draw goes through
    `itemPoke()` and its erase wrote `ram[dst] = ...` directly, so a gate that
    monkey-patched `itemPoke` to count writes measured the draw exactly and
    reported the erase as ZERO WRITES -- a confident, precise, wrong number that
    looked like an engine fault.  The two halves of one blit pair had two write
    paths and the same below-$4000 guard duplicated in both.
    RULES: (a) before trusting an instrumented count, check that EVERY store in
    the routine goes through the instrumented door -- grep the method for a bare
    `ram[` ; (b) unify the paths rather than instrumenting two (the erase now
    calls `itemPoke` too, which also removes the duplicated ROM guard);
    (c) a count of ZERO from an instrument is the most suspicious result it can
    produce: something ran, or nothing did, and only the other half of the pair
    says which.

82. **A CALL IS AN EXPRESSION: ITS RETURN VALUE CAN BE THE DATUM, AND A "VOID"
    TRANSLITERATION SILENTLY SUBSTITUTES THE CALLER'S OWN PRELOADED REGISTER**
    (Bubble Bobble, M7.7-H13-B7, 2026-09-19).  `$B761 LD HL,1 / $B764 CP L /
    $B766 CALL z,$B816 / ... / $B771 LD ($FFED),HL`.  Read as control flow this
    is "if the class is 1, make a corpse, then store the award" -- and the award
    looks like the `LD HL,1` two instructions above.  It is not: `$B816` ends in
    `$8BC2`, which leaves **HL = $0100**, so the CORPSE'S OWN RETURN VALUE is the
    award and a class-1 pop pays ONE HUNDRED.  The engine paid ONE, and the
    difference is invisible in any test that only asks "was a corpse created?".
    RULES: (a) for every `CALL` whose caller stores a register pair afterwards
    WITHOUT reloading it, find what the callee leaves there -- follow the callee
    to its own last write of that pair, through its tail calls; (b) a JS method
    transliterated as a void statement is an ASSERTION that the callee returns
    nothing; write that assertion down or return the value; (c) gate the PAID
    AMOUNT, not the fact of payment -- and seed the destination field, because a
    routine that clears it before adding (here `$80FA` at `$8164`) makes "paid
    ten" and "paid nothing" the same observation.

83. **A BIT TEST IS NOT A GATE UNTIL YOU KNOW WHO CALLS IT**
    (Bubble Bobble, M7.7-H13-B7, 2026-09-19).  `$A437` reads
    `BIT 5,(IY+7) / RET nz / SET 5,(IY+7) / LD HL,$AA5F / DEC (HL)` and is,
    locally, a bit-5 test.  Modelled that way it charges a LIVE enemy twice,
    because the only path that reaches it is `$A447`, the entity master, which
    **diverts to `$A437` when bit 7 is CLEAR** (`$A451 JP p`) or bit 3 is set
    -- otherwise it falls on to the erase/draw and never reaches `$A437` at
    all.  The real rule is (bit 7 CLEAR **or** bit 3 SET) **and** bit 5 clear.
    [The mechanism sentence here first read "returns early when bit 7 is SET",
    inverted; corrected in B9 from the disassembly.  The rule and the code were
    right for the eight values measured, which is exactly why nothing caught it
    -- see rule (d).  M7.51: none of the eight had bit 3 set, and rule and code
    both lacked that half -- a FROZEN enemy with bit 5 clear cost one where the
    machine costs two; `tools/corpserepaint.py`, CR3.]  Worse, `$8BF3` overwrites `(IY+7)` immediately afterwards and clears
    bit 5 again, so THE FLAG CANNOT SAY WHICH ARM RAN -- only the counter can.
    RULES: (a) before transliterating a routine's entry condition, list its
    callers and fold in every test they made on the same byte; (b) when the
    observable is overwritten downstream, gate the SIDE EFFECT (here `($AA5F)`)
    and not the flag; (c) seed that counter to a value the code never writes --
    every shipped capture reads `$00` there, so an unseeded run wraps to `$FF`
    and both arms look like garbage.  (d) WRITE THE MECHANISM DOWN FROM THE
    DISASSEMBLY, NOT FROM THE TABLE.  A measured input/output table pins the
    RULE and says nothing about WHY, so an inverted explanation beside correct
    code passes every gate and every battery -- and the next increment reasons
    from the prose, not the bytes.  This entry shipped that way for three
    increments.

84. **ONE KEY SCRIPT IS NOT A DISTRIBUTION, AND "NEVER IN N" MUST CARRY ITS N**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  Two independent agents measured
    which of the boss's six accepted cells fair play actually produces.  Each
    ran ONE key-script family on the same state; one reported "four of five hits
    were at dx = -3, the visually-absurd cell", the other "every one of six
    decrements landed at (-3,-1); in 22 bolts the overlapping cell (0,-1) NEVER
    fired".  A twelfth script produced (0,-1).  Each had read a property of its
    own script as a property of the game.
    RULES: (a) any claim about "what the game actually does in play" needs a
    SWEEP of scripts and a histogram REPORTED WITH ITS N, never a single run;
    (b) "never observed" is a statement about the sample -- write the sample
    size into the sentence, and into the fixture, so the next reader can see how
    thin it is; (c) when two measurements of the same thing disagree about the
    COMMON CASE while agreeing on the SET, suspect the sampling, not the code.

85. **A CROSS-PRODUCT OF TWO MEASURED SUPPORTS IS NOT A PROBABILITY**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  An enumeration pass measured the
    reachable bubble rows (23 of them) and the reachable boss rows (17), crossed
    them, found 51 of 391 pairs accepted and reported "13.0%" -- then quoted an
    observed 13.6% as corroboration.  Neither axis was uniform (only 7 of the 23
    rows ever reached the allocator) nor independent (the boss's x and y are
    correlated, and only 89 of 425 pairs occur at all), and the pairing was not
    even well defined, because the bolt's row is frozen at allocation while the
    boss's moves through the whole flight.
    RULES: (a) enumerating a SUPPORT is a closure argument -- "these values are
    reachable" -- and says nothing about rates; do not divide it; (b) if a rate
    is wanted, measure the rate, and say over how many trials; (c) a computed
    number that lands near an observed one is a coincidence until the sampling
    model is written down, and quoting it as agreement hides both.

86. **A GAME'S KEY TABLE HOLDS ITS OWN AND-MASK, NOT THE VALUE THE PORT RETURNS**
    (Bubble Bobble, M7.7-H13-B8, 2026-09-19).  `$B5FD` holds four
    (half-row select, BIT MASK) pairs and the game tests `IN A,(sel) / AND mask
    / JR z`, so the mask has the key's bit SET.  `Ports.press` wants the value
    the port RETURNS, where a pressed key is a ZERO.  Handing the table value
    over verbatim pressed the SEVEN OTHER KEYS of that half-row -- and on `$7F`
    one of them is the PAUSE key, so the machine sat in `$8FFB`'s
    `IN A,($FE) / RRA / JR c` loop with interrupts OFF.  The phase ran, produced
    zero bolts, zero hit tests and zero damage, and read exactly like a correct
    negative.
    RULES: (a) convert a game's mask with `0xFF ^ mask` and say so at the
    conversion site; (b) before believing a keyboard-driven negative, assert a
    POSITIVE control from the same script -- here "the player blew at least one
    bubble" -- because a wedged machine and a correct rule give the same zeros;
    (c) if a free-running measurement stops advancing frames, disassemble the PC
    it stopped at before touching anything else: `$8FFF` named the bug in one
    line.

87. **A BRACKET'S END POINT MUST BE AN INSTRUCTION *BOTH* ARMS EXECUTE, AND THE
    TELL IS THAT BOTH ARMS READ ZERO** (Bubble Bobble, M7.7-H13-B9,
    2026-09-22).  To isolate the death tick's out-of-lives branch I armed a
    write watch at `$AB5E` and harvested it at `$ABD4`, "the tick's RET".
    `$ABD4` is P2's RET: P1 leaves at `$ABCB`, four bytes earlier, because
    `$ABBD BIT 0,(IY+$5A) / JR nz` splits the respawn into a P1 arm and a P2
    arm with a `RET` at the end of each.  The harvest point was never reached,
    the log was never read, and the phase reported **0 writes on the last life
    and 0 on the respawn** -- which is exactly the shape a correct negative
    has.  The real numbers were 83 and 1.
    RULES: (a) pick the bracket's end at the instruction where the arms
    CONVERGE -- here `$AB6B`, the target of the `JP p` that skipped the branch
    -- not at "the end of the routine", which may be several addresses;
    (b) ZERO ON BOTH SIDES OF A COMPARISON IS NOT A RESULT, it is a broken
    instrument: a differential whose two halves agree at zero has measured
    nothing, and the control that was supposed to save you agrees with you for
    the wrong reason (the dual of #50 and #81(c));
    (c) count the END POINT's executions alongside the writes -- a bracket that
    closed zero times should fail loudly, not return an empty list.

88. **A COVERAGE COUNT IS AN UPPER-BOUND TEST, NOT AN EQUALITY: "WERE THESE N
    PLACES WRITTEN?" IS SATISFIED BY A ROUTINE THAT WRITES EVERYWHERE**
    (Bubble Bobble, M7.7-H13-B10, 2026-09-22).  The flood arm paints ONE
    32-cell row per step at `$5AE0 - (A & $F8) * 4`, walking up the screen
    through 22 distinct rows.  My gate collected the set of 32-aligned rows
    that had been painted and asserted `size === 22`.  Three different
    mutations passed it: painting the WHOLE 704-cell screen every step (all 22
    rows are in the set), computing the base WITHOUT the `AND $F8` (the set is
    still 22 rows because the gate only sampled 32-byte boundaries), and
    walking the rows DOWN instead of up (a set has no order).
    RULES: (a) a set of touched positions is an EXISTENTIAL -- pair it with the
    changed-cell COUNT per step, which makes over-painting fail immediately;
    (b) assert the ADDRESS against the formula that produced it, not against
    membership of a bucket, or every address inside the bucket passes;
    (c) if the thing walks, assert the ORDER: keep the sequence and check it is
    monotonic, because a set discards exactly the property "walks up".
    And the sibling that showed up four more times in the same run: a THRESHOLD
    probed at a value both models agree on tests nothing -- `AND $1F` and
    `AND $0F` both say "wait" at `$11`, and only `$10` separates them.  That is
    TRAPS #60 re-paid; pick the value ONE STEP from the boundary, on each side.

89. **A CAPTURE CAN SIT INSIDE A WINDOW THAT SWITCHES A WHOLE PASS OFF, AND THE
    COUNTER THAT SAYS SO IS NOT THE EVIDENCE** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  `$AA6E LD A,($B54B) / $AA72 JP nz,$B520` abandons the entire
    entity update while the settler byte is non-zero.  `build/boss.pkl` holds
    `$35` and `build/bossspawn.pkl` `$53`, so they sit 107 and ~166 frames
    inside that window -- and four increments measured player-related negatives
    on them.  `build/play1p48.pkl` is inside one too (`$B54B = 14`), which is
    the 28 frames that reconcile two different measurements of the same decay.
    RULES: (a) before recording that a routine did not run, PROFILE IT -- an
    instruction census over its address range (0 against 5928 here) is the
    evidence; a counter reading zero is not; (b) check the gating byte of every
    state you are about to call "the round-N state", and put its value in the
    fixture beside the numbers; (c) a state can be unusable for a SECOND
    reason that the first check passes -- `bosskilled`'s settler is zero and it
    still runs the entity pass once in 120 frames, because a 345-frame freeze
    owns the rest of the run.

90. **A SAMPLER'S ROW IS THE RESULT OF THE PREVIOUS PASS, AND A PASS IS NOT
    ATOMIC WITH RESPECT TO THE CLOCK IT SAMPLES** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  Two alignment faults, both of which look exactly like engine
    bugs.  First: a row taken at the loop top holds the frame counter as it was
    at the END of the pass, while the chain that produced the row's other
    fields ran with the PREVIOUS value -- replayed the naive way, the boss's
    tick divider diverged at row 9 against an engine that was self-consistent
    throughout.  Second: the loop runs 8.571 times a frame, so 16 of 600 passes
    STRADDLE an interrupt and the chain members see DIFFERENT counter values --
    the boss tick at `$8D2E` reads one, `$A09A` at `$8D43` reads the next.  One
    replayed value per pass reproduces the boss exactly and is off by one on
    `$A09E`, and the obvious conclusion is that the effect manager is wrong.
    RULES: (a) sample the driving clock AT each consumer, not once per row, and
    record how many rows straddle -- if the number is zero the extra samples
    cost nothing and the claim is now measured; (b) state explicitly which pass
    a row describes; "the row after" and "the pass that produced it" are off by
    one and the difference is invisible while nothing moves; (c) when a replay
    diverges on ONE field while everything around it matches, suspect the
    replay's alignment before the code -- a real defect rarely spares its
    neighbours.

91. **THE SEED LIST IS THE TEST'S WORLD: ANYTHING NOT IN IT IS SUPPLIED,
    SILENTLY, BY THE ENGINE'S OWN DEFAULTS** (Bubble Bobble, M7.7-H13-B11,
    2026-09-22).  The differential seeded 30 fields and compared them.
    `$A98F/$A990` were not among them, so the engine ran on what `reset()` puts
    there -- the tape's `37 C9`, `SCF / RET`, which makes EVERY POSITION AN
    OVERLAP (TRAPS #79) -- while the machine's capture held `00 00`.  The
    engine's boss killed P1 on pass 10 and the first differing row said
    `FDDA 192 vs 196`: a true report of a divergence with an entirely false
    implication.
    RULES: (a) a field that the code under test READS belongs in the seed list
    even when you are not comparing it -- the comparison set and the seed set
    are different lists and only the second one has to be complete;
    (b) when a differential's first divergence is in a field whose INPUTS are
    not seeded, fix the seed before touching the engine; (c) the port's own
    `reset()` defaults are the most dangerous unseeded values there are,
    because they are plausible: a zero would have been obvious.

92. **A SUITE THAT ONLY COMPARES RAM NEVER ASKS WHETHER ANYTHING IS VISIBLE,
    AND IT WILL PASS OVER A BLACK SCREEN** (Bubble Bobble, M7.3c, 2026-09-22).
    The round render asset's attribute third for rows 2-23 was the COLOUR
    SHADOW, byte for byte -- solidity, drift and occupancy bit fields written
    into the attribute file.  433 of the 704 playfield cells had ink equal to
    paper.  The sprites blitted perfectly, byte-exact against the machine, and
    nothing could be seen.  **915 checks passed over it**, and when the fix
    turned the screen from black to the round's colours, NOT ONE of them moved.
    The owner found it by looking at a filmstrip.
    RULES: (a) a differential against a captured world is a test of AGREEMENT,
    not of OUTPUT -- add at least one assertion about the rendered result
    itself, and the cheapest useful one is "no playfield cell has ink equal to
    paper"; (b) every shipped asset needs a PRODUCING TOOL in the repository --
    this one was made ad hoc, had no tool, and so nothing ever re-derived it or
    checked it against the machine; (c) when an asset contains two blocks of
    the same size, check they are not accidentally the same block: `display`'s
    attribute third and `colour` were identical and no gate compared them;
    (d) LOOK AT IT.  The manual says so for a reason, and the one measurement
    that found this was a write-watch run because a human said the screen was
    wrong.

93. **A SEED THAT IS WRONG BY ONE STEP IS NOT VISIBLY WRONG IN ANY SINGLE ROW**
    (Bubble Bobble, M7.8-0a, 2026-09-23).  `roundclass.py`'s chained build
    seeded `($8609) := 0` and called it "the NEW-GAME value $96FB writes".
    `$96FA` is `XOR A / LD ($8609),A / LD ($83EC),A / LD ($82D7),A` -- ALL
    THREE.  The chain inherited round1_48's `($82D7) = ($83EC) = 1`, so every
    build counter in the census, and every palette byte and tile index derived
    from one, came out ONE BUILD AHEAD of a real new game.  Nothing looked
    wrong: each row was internally consistent, the round-keyed findings were
    all correct, and no gate read the counter columns.  It surfaced only when
    the platform shadow was measured and the same round 1 built at the two
    phases differed in 1,661 of 6,144 bytes.  By then TWO independent
    measurement passes had taken 81-round sweeps off it and published tables
    shifted by exactly one round -- an 84-tile reconstruction table missing six
    tiles, and two "sixteen exact rounds" lists each +1.
    (a) When a tool claims to reproduce a machine state, DISASSEMBLE the
    routine it is imitating and seed every byte it writes, not the one you
    remembered.  (b) A comment naming a single address is a claim about a
    whole routine; check it.  (c) Derived columns nobody gates are where this
    hides -- so gate the SEED, not just the output.

94. **THE ENTRY POINT YOU ARM AT IS PART OF THE MEASUREMENT, AND IT CAN INVENT
    A DEFECT THAT IS NOT THERE** (Bubble Bobble, M7.8-A, 2026-09-23).
    `$9858`'s shadow clear is `LD HL,$E000 / LD C,$18 / CALL $AA49 / DEC C /
    JR nz`, and `$AA49` is `XOR A / LD (HL),A / INC HL / DJNZ` -- a fill whose
    length is **B from the caller**.  `$9858` never sets B.  Armed at `$9858`
    from a mid-play save, B held whatever the interrupted main loop left: 88 on
    round1_48 and 10 on r20_48, clearing 5,976 and 5,898 of 6,144 bytes and
    leaving residue in the shadow's bottom sub-rows, predicted to the byte on
    four states.  That looked exactly like a defect in the port's
    `shadowClear()`, which clears all 6,144.  Driven through the REAL advance
    on a correctly seeded chain, **B is 0 on all 81 rounds** -- the whole
    6,144, every time.  The port was right and the harness was lying.
    Before "fixing" a method to match a harness measurement, drive the machine
    the way the GAME drives it and measure again.  An arm point is a poke.

95. **A METHOD WITH NO CALL SITE HAS NEVER HAD ITS PARITY EXERCISED, AND A
    SELF-MODIFIED OPERAND IS EXACTLY WHERE THAT BITES** (Bubble Bobble, M7.8-A,
    2026-09-23).  `$833A` is `LD A,$1E / XOR $1E / LD ($833B),A / LD C,A`: the
    literal IS the state, flipping `$1E -> $00 -> $1E` across the two calls a
    build makes, and C is the COLUMN OFFSET for the wall draw.  `reset()` never
    seeded `$833B`, so it started at `$00`, the parity inverted, and the FIRST
    call drew the RIGHT wall and the second the LEFT.  The method had been
    written, reviewed and gated -- but it had NO CALL SITE, so nothing had ever
    run it twice in sequence, which is the only way the flip is observable.
    Thirteen such methods existed in this engine at once.
    (a) Count call sites, not methods: an uncalled method is untested however
    many rows name it.  (b) For a self-modified operand, gate the RESTING
    VALUE at reset, from the tape image, not just the transition.

96. **THE WRITE COUNT CAN MATCH THE MACHINE EXACTLY WHILE EVERY VALUE IS
    WRONG** (Bubble Bobble, M7.8-A, 2026-09-23).  `$824A`'s inner loop is
    `LD (HL),A` on the even byte and `OR (HL)` on the odd one, and the odd
    bytes come from the platform tile buffer `$856C`.  A build writes only
    offsets +1, +3 and +5 there; +7, +9, +11, +13, +15 and all of +16..+23 are
    **never written by anything** -- pure tape data the port had never shipped.
    With them zero the `OR` contributed nothing, so the engine wrote 2,704
    bytes to the same 2,704 addresses as the machine, in the same order, and
    455 platform bytes went missing.  A gate counting writes, or diffing which
    addresses were touched, passes this perfectly.
    (a) Compare VALUES, not extents.  (b) When a routine merges rather than
    stores, its source buffer is an input -- find the bytes nothing writes and
    ship them.  (c) "Engine-only 0, machine-only 455" is the signature of a
    missing input, not a wrong algorithm; the asymmetry names the bug.

97. **AN ANNOTATION THAT LIVES ONLY IN THE ARTIFACT DIES AT THE NEXT
    RECAPTURE** (Bubble Bobble, M7.8-A, 2026-09-23).  M7.7-R1 recorded why a
    differential row was superseded by editing `build/bossround_fixture.json`
    directly.  Regenerating that fixture for an unrelated reason reverted the
    note to the producing tool's 2026-09-17 text and took a gate red.  This is
    TRAPS #92 rule (b) from the other direction: an asset is its tool's output
    and nothing else, so anything worth keeping belongs in the tool.  If you
    find yourself editing a `build/*.json` by hand, you are editing a build
    product.

98. **A DIFFERENTIAL THAT SEEDS ITS OWN INPUTS TESTS THE ROUTINE AND NEVER THE
    SEQUENCE** (Bubble Bobble, M7.8-A, 2026-09-23).  The round-builder gate
    compared the engine against the machine on 18 covering rows, byte for byte,
    over the whole shadow -- and every row began by seeding `($8609)`,
    `($82D7)` and `($83EC)` from the fixture.  So it proved the builder correct
    *for inputs it supplied itself*.  Meanwhile `reset()` left `($83EC)` one
    build behind `($82D7)`, a pair the machine is never in, and **every round
    the port actually built used the previous round's platform tile** -- about
    1,650 of 6,144 shadow bytes wrong on every advance, with all 18 rows green.
    The fix is a second gate that pokes NOTHING: drive the port's own
    `roundAdvance()` N times from `reset()` and compare against N chained
    `CALL $97F8` from a new game.  A sampled input space and a generated
    sequence are different tests and a suite needs both.

99. **WHEN A CONSTANT HAS NO MEASUREMENT NAMED BESIDE IT, TRY CORRECTING IT AND
    SEE IF THE SUITE GOES RED** (Bubble Bobble, M7.8-A, 2026-09-23).  The
    `($83EC)` defect above was pinned by an assertion -- `pg.ram[V.build_b_at]
    === 0` -- sitting in the same expression as a properly sourced one
    (`=== A.render.build_counter`).  The 0 was `build/image.bin`'s round-80
    residue frozen into a gate with no machine value named for it.  An
    adversarial pass found it not by breaking the code but by **fixing** it and
    watching the suite fail.  The INVERSE MUTATION is the cheap test for a
    constant nobody sourced: if making it right turns the suite red, the suite
    is pinning a bug.  Corollary: in any assertion that ANDs several equalities,
    check that each side has a provenance, because one borrows credibility from
    the others.

100. **AN ASSERTION CAN BE TRUE OF EVERYTHING** (Bubble Bobble, M7.8-A,
    2026-09-23).  A gate meant to bound a declared departure read
    `for (const ad of glyph) if (g.ram[ad] !== undefined) inside++;` and then
    `inside === glyph.size`.  `g.ram` is a `Uint8Array(65536)`, so that is true
    for every in-range index -- including `$0000` and `$FFFF`, addresses the
    glyph never touches.  Directly above it sat `for (let row = 0; row < 22;
    row++){ /* comment */ }`, a loop with an empty body.  The row's prose
    claimed the engine differed from the machine on exactly six bytes and
    asserted nothing of the kind.  Neither survives a moment's reading, and
    both shipped green.  (a) A predicate over a typed array that tests
    `!== undefined` tests nothing.  (b) Mutation-test the GATE, not only the
    code: feed it a value you know is wrong and require it to fail.  (c) An
    empty loop body is a review failure, not a style one.

101. **THE ISR REACHES INTO CODE THAT HAS NO HALT IN IT** (Bubble Bobble,
    M7.8-A, 2026-09-23).  `$7F1B`, the round-start composition, contains no
    `HALT` anywhere, so the 50 Hz interrupt fires *during* the scroll and
    composites entities into the display -- and `$854D` then copies display rows
    2 and 23 back into the SHADOW, so a sprite that lands in row 2 becomes part
    of the built background.  MEASURED by capturing every covering row twice:
    the ISR changes the built shadow on 3 of 23 rows, and on one of them it is
    two bytes that no amount of staring at the builder would explain.  An
    oracle taken with interrupts on, compared against a port that runs no ISR
    inside its own composition, asserts a behaviour the port does not model --
    so capture BOTH, compare against the one the port models, and carry the
    other as the named boundary with its rate.

102. **A BOUNDARY CHECK THAT NAMES RANGES LEAVES EVERYTHING BETWEEN THEM
    UNGUARDED -- AND AN EXTENT MUST BE MEASURED AS WRITES, NOT AS CHANGES**
    (Bubble Bobble, M7.8-A, 2026-09-23).  The builder's "what it must not
    touch" check guarded four named ranges.  A mutation adding
    `ram[0x9000] = 0xFF` to the ceiling routine -- the builder scribbling
    outside its own extent on every build -- survived a battery; the identical
    scribble at `$7000` was caught only because `$7000` happens to fall inside
    the round records.  The fix is to measure the machine's extent as an
    ADDRESS SET over the whole 64K and require the engine's changed set to be a
    subset of it.
    AND THE FIRST ATTEMPT AT THAT WAS WRONG IN AN INSTRUCTIVE WAY: measuring
    the extent by diffing the world before and after gives CHANGED addresses,
    not written ones.  `$860E` is written by `$8400` on every build and changed
    on none of them, so a port writing a different value there looked like it
    had scribbled outside the extent, and three display cells the machine
    rewrites with their own values did too.  A store of the value already there
    is still a store.  Measure the extent with a write-watch, union it with the
    diff, and only then compare.

103. **A ROUTINE REACHED ONLY BY FALL-THROUGH HAS NO CALLERS TO FIND, AND A
    METHOD WRITTEN FOR IT WILL SIT UNCALLED** (Bubble Bobble, M7.8-B,
    2026-09-23).  `$79AC` is `JP $7C43`; `$7C43` masks the colour shadow with
    `$38` and then falls onward through the drift painter, which falls into
    `$7DD6`, the element class.  There is no `CALL` to either tail anywhere in
    64K.  The port had `driftApply()` and `elementClass()` both written, both
    gated in isolation, and both with **zero call sites** -- so every round
    advance wiped the per-round wind (every bubble after round 1 rose straight
    up) and left the element class at 0 (the fire, water and lightning rounds
    never fired).  This is the same shape M7.8-A found three times in one
    increment and it is now five.
    (a) A caller scan proves nothing about a fall-through; walk the code
    FORWARD from the jump target and see where it stops.  (b) Audit for methods
    with no call site as a standing check -- the count is a number the suite can
    assert.  (c) A routine gated in isolation is not wired; "tested" and
    "reached" are different claims.

104. **A GATE WHOSE TWO SIDES ARE THE SAME CAPTURE CANNOT FAIL, AND SHIPPING A
    ROUTINE'S OUTPUT IS HOW YOU GET ONE** (Bubble Bobble, M7.8-C, 2026-09-23).
    The drift field was shipped as an asset -- 81 rounds x 192 bytes of captured
    output -- and the suite's "the drift field matches the machine on all 81
    rounds" row drove the engine, which read `build/drift_field.json`, against
    `build/drift_fixture.json`.  An adversarial pass found those two hold
    **byte-identical base64 for all 81 rounds**: one capture compared with a
    copy of itself, per cell, with a seeded map and a careful commentary about
    permutations -- and no possible failure.
    The cure is not a better comparison, it is a different engine: ship the
    routine's INPUT and compute.  675 bytes of stream and tables replaced 15,552
    bytes of field, and the identical comparison became a test of the algorithm.
    (a) When an asset is a routine's OUTPUT, any gate over it is at risk of
    this; ask what the engine would have to get wrong for the row to go red.
    (b) Two assets derived from one measurement are ONE source -- diff them
    before using one to check the other.  (c) "WHEN THE X LANDS THE ASSET GOES"
    is worth writing into the spec at the moment the asset is created, because
    it is the thing that later makes the gate real.

105. **A TRANSLITERATION CAN INHERIT A DOMAIN IT NEVER HAD** (Bubble Bobble,
    M7.8-C, 2026-09-23).  The port's drift field was a lookup: an unknown round
    found no entry and the routine silently did nothing.  The transliterated
    painter walks a stream through LIVE memory, and off its domain it does not
    do nothing -- at `($8609)` = 0, the byte `$96FB` writes at every new game, it
    writes 141 cells over `$FB02..$FFF0`, and at 255 it writes **10,545** over
    `$FB00..$FFF9`: the player struct at `$FD80`, the bubble pool at `$FED8`, the
    high score at `$FFE1`.  The silent no-op became memory corruption.
    Measuring that the port cannot reach it (`$97F8` increments the round before
    the round start, so the painter only ever sees 1..81) is necessary and not
    sufficient: the guard goes in anyway, and it is COUNTED rather than silent,
    because the next caller will not know.

106. **A TRANSLITERATED LOOP CAN BE UNBOUNDED WHERE THE MACHINE'S WAS BOUNDED
    BY ITS DATA -- AND A MUTATION BATTERY WITH NO PER-CASE TIMEOUT TURNS THAT
    INTO A WEDGED RUN** (Bubble Bobble, M7.8-C, 2026-09-23).  The drift
    painter's alias walk re-enters at `$7C8A` with a new round and nothing in
    the routine limits how often: the Z80 terminates only because the stream
    data terminates.  Transliterated faithfully, that is an unbounded
    `for (;;)` in the browser.  A mutation reading the entry stride from
    `BODY[]` instead of `LEN[]` made the walk under-advance, land on an `$Fx`
    byte and cycle -- and `node test/bb.test.js` then burned a full core for
    **five hours**, while the runner, which had no timeout, sat blocked behind
    it with that mutation STILL APPLIED to `web/game.js`.
    Two defects, one incident, and both needed fixing:
    (a) BOUND the loop and COUNT the overrun.  The bound is a measurement --
    sixteen aliases exist and the deepest real chain is two hops -- not a
    guess, and it is a declared departure because the machine would spin.
    (b) EVERY subprocess in a battery gets a timeout.  *** CORRECTION, and it
    matters because the first version of this entry blamed the wrong tool: the
    PROJECT'S battery `mutate7.py` ALREADY had a 180-second timeout and crash
    detection, with a comment explaining that a hang counts as a kill because
    the suite did not pass.  The runner with no timeout was a HELPER I wrote
    myself that afternoon and then reported results from. ***  Do not write a
    lesson blaming shared tooling until you have read it.
    (c) When a battery is interrupted, VERIFY THE FILE IS RESTORED before
    trusting anything -- checking the first case's anchor is not enough, it was
    the third that was stuck, and a report of "the file is clean" was wrong.
    (d) Silence from a long-running job is not progress.  The output file had
    not grown in five hours; the check that settled it was whether the BUILD
    ARTIFACT's mtime was still moving.

107. **THE FIX FOR A HANG REPORTED THE HANG AS A PASS** (Bubble Bobble, M7.8-C,
    2026-09-23).  After a mutation hung the suite for five hours, a HELPER
    RUNNER I had written -- not the project's `mutate7.py`, which already had
    both guards -- was given a per-case timeout.  It did this:

        except subprocess.TimeoutExpired:
            return ['TIMEOUT'], '...'

    and its caller reads the returned list as the FAILURE LIST:
    `if not fails: SURVIVED else: print('killed by %d' % len(fails))`.  So a
    timeout printed **"killed by 1"** -- indistinguishable from a real kill.
    The next run reported "all 25 mutations killed, zero survivors" and TWO of
    them had hung for 180 seconds each.  That went into a message to the user as
    a clean result.
    It was caught only because a PARALLEL runner, written independently, used a
    distinct TIMEOUT verdict and disagreed -- two implementations of the same
    measurement, which is the only thing that finds this class.
    AND THE SAME DISAGREEMENT THEN CORRECTED THE OPPOSITE ERROR.  The parallel
    runner called a crashing case SURVIVED, which is the same lie inverted: a
    page that will not parse, or an engine that throws, has not been measured
    either.  The project's own battery had this right all along -- it turns an
    empty summary into a named `<crash>` failure -- and the split that survives
    is three-way: an ENGINE DIAGNOSTIC firing (this engine throws on an
    unexpected RNG draw, by design) is a KILL; a SyntaxError is a BROKEN MUTANT
    that tested nothing and must be repaired; only a clean green run is a
    SURVIVOR.
    (a) A timeout is not a kill and not a pass: give it its OWN verdict and
    count it as bad.  An engine that hangs has not been shown to be correct.
    (b) Never encode a new outcome in an existing channel -- a sentinel in the
    failure list is a lie the caller cannot detect.
    (c) When a fix and a report disagree with a second implementation, believe
    the disagreement and go and measure.

108. **A GUARD THAT BOUNDS THE WRONG QUANTITY BOUNDS NOTHING** (Bubble Bobble,
    M7.8-C, 2026-09-23).  The drift painter's fill was given a budget to stop a
    corrupted stream hanging the engine.  The first version counted CALLS and
    capped them at 4,096 -- but one call can ask for 256 rows x 256 cells, so
    the cap permitted 268 million writes and the engine still hung.  Counting
    the CELLS is the only cap that bounds the work.  Measured afterwards: a real
    round asks for at most 1,090 cells, so a 200,000 budget is 183x headroom and
    the 81 real rounds trip it zero times.
    Bound the thing that actually grows, and then measure the real maximum so
    the headroom is a number rather than a hope.

109. **AN ASSET IS SHIPPED BECAUSE NOBODY ASKED WHO READS IT, AND A PAGE GETS TO
    8.8 MB ONE FIXTURE AT A TIME** (Bubble Bobble, M7.9, 2026-09-24).  The built
    page was 8,829,094 bytes.  **97.7% of it was oracle fixtures written for the
    test suite**: 68 of 76 assets, 17.6 MB, one of them -- a per-frame entity
    oracle -- 13.3 MB on its own.  The engine reads EIGHT assets, 207 KB.
    Nothing was wrong with any individual decision; each fixture was inlined
    because the build inlines assets, and nobody asked which of them the engine
    reads.  Holding the test-only ones back and letting the rig load them from
    disk took the page to 621 KB with the suite running every check.
    (a) THE FLAG THAT LOOKS LIKE THE ANSWER IS NOT THE ANSWER: splitting on
    `required` would have BROKEN the page, because two assets the engine reads
    at reset() were marked `required: false`.  Derive the split from the ENGINE
    SOURCE, not from anyone's classification, and gate it that way.
    (b) GATE BOTH DIRECTIONS.  An asset held back by mistake makes the page
    quietly wrong; one shipped by mistake makes it quietly fat -- and only the
    second is how it grew.  Default the flag to SHIP, so an unclassified asset
    costs bytes rather than correctness.
    (c) THE SILENT-SKIP IS THE REAL DANGER.  Every gate block here is guarded by
    `if (A.thing)`, so an unmerged fixture would skip its whole block and the
    suite would go quiet: measured, disabling the rig's merge drops the suite
    from 1,001 checks to 67.  The rig COUNTS what it merged and asserts the
    number, so the collapse is loud.

110. **A PREDICATE BUILT BY STRING CONCATENATION LOSES ITS ESCAPES, AND THE ROW
    PASSES** (Bubble Bobble, M7.9, 2026-09-24).  The gate above was first
    written as `new RegExp('(?:this\.)?A\.' + key + '\b')`, generated through
    a Python heredoc.  The escapes collapsed on the way in, so the JavaScript
    string `'\b'` was a BACKSPACE character rather than a word boundary, the
    pattern matched nothing, and the check reported **"0 referenced"** and
    PASSED -- a guard over an empty set.
    It was caught only because the row printed its own count and the count was
    zero.  (a) Make a check STATE THE SIZE OF WHAT IT MEASURED, so measuring
    nothing is visible.  (b) Assert that size is non-zero as its own row.
    (c) Prefer a literal scan to a dynamically built regex when the pattern
    crosses a code generator; escaping survives one layer, rarely two.

111. **A ROUTINE CAN BE FULLY TRANSLITERATED AND STILL DRAW NOTHING, BECAUSE THE
    STATE IT READS WAS NEVER SEEDED** (Bubble Bobble, M7.10, 2026-09-24).
    `$806C`'s three methods were all written and gated in isolation.  What was
    missing was `reset()`: `($FD87)`, `($FD91)`, `($FDDC)` and `($FDE6)` were
    ZERO, and `$8097` is `RET p` -- a player whose +7 bit 7 is clear draws
    nothing at all.  **Wiring the call without the state would have produced an
    empty row and a green suite**, because the gate that would have caught it
    was masking those very cells as a declared gap.
    (a) Before wiring a routine, take a READ-WATCH over it and diff its input
    set against what `reset()` actually holds.  The code being right is half
    the job.  (b) A declared gap in a gate is a place where wiring something
    badly cannot be seen -- so NARROW THE MASK in the same increment that
    closes the gap, or the next change inherits a blind spot.

112. **SEEDING STATE CORRECTLY CAN BREAK GATES THAT WERE PASSING BY ACCIDENT,
    AND THAT IS THE ENGINE GETTING MORE FAITHFUL** (Bubble Bobble, M7.10,
    2026-09-24).  Setting `($FD87)` for the lives panel also fed `$9840`'s
    `BIT 7,(IX+7)`, the milestone warp's in-play test.  While the byte was 0 the
    port COULD NOT WARP, so eight sequence gates walked rounds 1..23 in order
    and passed; with it seeded the port warps 19 -> 81, correctly, and they went
    red.  The gates were comparing two different journeys and had never said so:
    the oracle's chain suppresses the warp deliberately (F0's recipe) and the
    port had been unable to warp for an unrelated reason.
    When a faithfulness fix turns gates red, check whether they were passing
    because of the very defect you removed -- and then drive BOTH SIDES under
    the oracle's conditions, rather than relaxing the assertion.

113. **A DUPLICATE CONSTANT IS A MUTATION THAT CANNOT FAIL** (Bubble Bobble,
    M7.10, 2026-09-24).  I added a 32-byte `BB_LIVES_ICON` and seeded it at
    `$85A1` -- which `BB_HUDF_ICON` had already seeded, from an earlier HUD
    increment.  The battery then reported the new mutation "the life icon glyph
    is not seeded" as a SURVIVOR, and it was right to: the line it removed was
    dead, the other seed still ran, and nothing changed.  A survivor pointing at
    code that does nothing is the cheapest possible signal that the code should
    not exist.  The real seeding IS tested -- zeroing `$85A1` breaks 23 of 23
    sequence rows -- so the coverage was there all along.
    Grep for the ADDRESS, not the constant name, before adding a seed.

114. **TWO SPELLINGS OF ONE RULE ARE A DUPLICATE WAITING TO DRIFT APART, AND THE
    UNCALLED-METHOD CENSUS IS WHERE THEY SURFACE** (Bubble Bobble, M7.11,
    2026-09-24).  `driftCode()`/`driftDelta()` and the `$B836` bubble move both
    computed the per-round wind -- the helper by name, the move inline -- and
    they were proved equivalent over 3,072 sampled cells.  Equivalent today;
    two things to keep in step for ever.  The helper had no engine caller at
    all, which is why it showed up in the census (TRAPS #103's gate) as a DEAD
    DUPLICATE rather than as a bug.
    The fix is not to delete the helper -- the gates drive it by name -- but to
    make the ENGINE call it, so there is one spelling and the existing coverage
    now covers the live path.  The census then shrinks by two, which is the
    signal that the collapse actually happened.
    A census of unreached methods is not only a list of unfinished work; it is
    a list of places where the same rule may already be written twice.

115. **AN "ISOLATED" TEST WORLD CAN BE A WORLD THE MACHINE IS NEVER IN, AND THE
    ROUTINE YOU WIRE NEXT IS WHAT TELLS YOU** (Bubble Bobble, M7.12,
    2026-09-24).  Six bubble gates zeroed `($FD87)` "to isolate the
    bubble-bubble path", removing the player so it could not touch the bubbles.
    Their fixtures were all captured on round1_48, where the machine has `$E1`
    -- the player is ACTIVE and simply sits somewhere else.  The zeroing was
    belt-and-braces that happened to change nothing.
    Then `$8E2A` was wired, and its test is THE SAME BIT: on this machine "no
    active player" and "game over" are one condition.  Every one of those
    isolated worlds armed the game-over timer, `$8D0D` short-circuited the rest
    of the pass, and six long-standing gates went red at once.
    (a) A test world that DEVIATES from the capture it is compared against is a
    liability even while it passes; prefer to isolate by POSITION or by the
    data under test, not by clearing a flag whose other meanings you have not
    enumerated.  (b) When wiring a routine turns old gates red, check whether
    those gates were relying on the world being impossible before you touch the
    routine.  (c) The fix here made the gates STRICTER, not looser: they now use
    the machine's own world.

116. **A FIXTURE NOBODY READS IS A FIXTURE NOBODY CHECKS -- AND ONE OF THEM WAS
    WRONG** (Bubble Bobble, M7.13, 2026-09-24).  Two structural rows already
    guarded the ship/test asset split: everything the ENGINE source reads must
    be shipped, and nothing it never reads may be.  Neither asked the next
    question.  A third row -- *is every test-only asset read by any check at
    all?* -- found exactly one of sixty-nine that was not:
    `build/livespanel_fixture.json`, captured by M7.10, registered in
    `port.json`, loaded from disk by the rig every single run, and compared
    against nothing.  M7.10 had written its gates from the numbers the tool
    PRINTED, which is not the same as reading the file it wrote.
    AND THE FILE WAS WRONG.  Its read-watch subtracted the colour shadow with
    `not (SHADOW <= a)` and `SHADOW = 0xE000` -- and $E000 is where the game's
    working RAM begins, so the filter swallowed $FD80..$FFFF whole.  The four
    addresses the increment EXISTS for -- ($FD87), ($FD91), ($FDDC), ($FDE6),
    the ones `reset()` had left at zero -- were missing from its own "measured
    input set", and the note in `port.json` advertised that set as complete.
    (a) An exclusion written as a half-open comparison with ONE end is a
    half-open exclusion: the shadow $806C writes is a WINDOW, $E000..$FB00, and
    naming both ends would have been the same amount of typing.  (b) For every
    artefact a tool produces, ask what READS it -- and make that a check, not a
    habit.  (c) The third direction of a structural gate is usually the one
    that finds something; two directions feel complete and are not.

117. **"THE NINE WIRED ROUTINES" WHILE DRIVING EIGHT** (Bubble Bobble, M7.13,
    2026-09-24).  The chain-ORDER gate installs a recorder on each wired method
    and asserts the sequence mainLoop() produces.  Its message said "the NINE
    wired routines record their own entry" and it listed -- and installed --
    eight.  M7.12 wired `gameOverTimer` and never added its recorder, so the
    order check could not have seen `$8E2A` wired at the FRONT of the chain
    instead of the end.  The fix is not the message: it is the tenth recorder.
    A gate whose text counts higher than its body is a gate that is a
    measurement of nothing in the gap, and the gap is exactly where the newest
    increment lives.

118. **THE RUNNER APPLIED NO MUTATION AND CALLED ALL 29 OF THEM SURVIVORS**
    (Bubble Bobble, M7.13, 2026-09-24).  Adding a path resolver to the parallel
    battery -- so that a case naming `bb.test.js` would land in `test/` rather
    than `web/` -- collapsed the two-line write into one and, doing so, moved it
    one indent level in, leaving it INSIDE the dead-anchor branch, after
    `continue`.  Every case then built and tested the PRISTINE tree, passed, and
    was recorded as SURVIVED.
    THE TELL WAS THE SHAPE, not any one row: 29 survivors out of 29.  No real
    increment has ever had a survival rate anywhere near that, and the right
    reading of "everything survived" is *suspect the runner*, not *the suite is
    weak*.  This is the same family as #107 (a hang reported as a kill) and #110
    (a regex that matched nothing reporting "0 referenced" and passing): a run
    that states a verdict for a measurement that did not happen.
    (a) The runner now RE-READS the file after writing and, if the text did not
    change, records NOT-APPLIED -- its own verdict, and one that fails the run.
    (b) It also says so out loud when every case survives.  (c) An edit that
    re-indents a line inside a loop with a `continue` in it deserves the diff
    read back, because Python will not complain.

119. **BOTH BATTERY RUNNERS HARDCODED `web/<fn>` FOR 1,502 CASES** (Bubble
    Bobble, M7.13, 2026-09-24).  The case list has named a FILE since it was
    written -- `('game.js', label, old, new)` -- and both runners resolved it as
    `'web/' + fn`.  Nothing noticed, because all 1,502 cases were `web/game.js`.
    The first case that mutates `test/bb.test.js` crashed with
    FileNotFoundError.
    That is worth more than a path fix: MUTATING THE SUITE IS HOW A GATE IS
    SHOWN TO BE ABLE TO FAIL, and the battery could not do it at all.  The first
    two suite mutations it ran found a row that could be neutered to `a => false`
    and still pass, because its answer is "nothing is wrong" and an empty list
    is a pass.  Such a row needs a CONTROL -- the same predicate run over a list
    with a phantom entry, which must come back naming exactly the phantom.

120. **`DJNZ` WITH B = 7 OVER AN EIGHT-ENTRY TABLE, AND THE EIGHTH ENTRY IS
    WRITTEN BY THE SAME ROUTINE** (Bubble Bobble, M7.14, 2026-09-24).  $900B's
    second gate ORs the enemy wake-up delays and fires the reveal when they are
    all zero.  The table is eight bytes, $A891..$A898, and its own first gate
    writes all EIGHT of them.  The OR loop reads SEVEN: `LD B,7` at $9026, so
    $A898 is never in it.
    Transcribing "all the delays" would have been wrong in exactly one world --
    seven zero and the eighth not -- and that world is REACHABLE, because the
    heart arm three instructions earlier is what puts a non-zero value in the
    eighth.  The proof is not the listing: one byte poked non-zero at a time
    across all eight, and only index 7 still lets the reveal fire.
    A loop counter that does not match the table it walks is a MEASUREMENT, not
    a typo, until the machine says otherwise -- and the cheap way to ask is to
    sweep the table one entry at a time rather than to read the DJNZ twice.

121. **A `JP` INTO A ROUTINE IS A CALL OF THE WHOLE ROUTINE, AND A STUB NAMED
    AFTER HALF OF IT HIDES THAT** (Bubble Bobble, M7.14, 2026-09-24).  $8C28 is
    `CALL $8216` then an attribute derive then `CALL $957E` then `CALL $806C`.
    The port had the derive, under the name `attrRestore()`, and the flood
    effect's `$A0BE JP z,$8C28` called it -- so a jump to a four-part routine
    ran one part, and the name made that look deliberate.  The comment even
    said "the $8216 half is still a stub", which is true and was read for three
    increments as "this is finished".
    The call ORDER, incidentally, is not readable either: $8216 does not RET, it
    ends `JP $7F80`, so a PC watch over the real routine reports FOUR callees
    where the source of $8C28 shows three.

122. **A TABLE OF ZEROS IS A TABLE THAT WORKS** (Bubble Bobble, M7.15,
    2026-09-24).  $8FA5's pitch is `|($B57D + phase) - $10| + 1`, and the port
    had thirty-two zeros at $B57D -- so every jump phase gave |0 - $10| + 1 =
    17, one flat note, and the routine ran, returned and produced a perfectly
    plausible square wave.  Nothing was undefined, nothing threw, and a gate
    that compared "the engine makes four edges" would have passed.
    The tell was not the sound: it was that EVERY animation byte gave the SAME
    answer.  A lookup whose output does not vary with its index is not a
    lookup, and the cheap check is to sweep the index and count the distinct
    results BEFORE comparing any of them to the machine.
    The table also agrees with its neighbour $B59D in 30 of 32 bytes, so a gate
    that seeded the wrong one and compared casually would also have passed; the
    two differing indices are named in the gate.

123. **"24 AND AN 8-BYTE SPILL" WAS A GUESS THAT HAD BEEN IN A COMMENT FOR
    THREE INCREMENTS** (Bubble Bobble, M7.15, 2026-09-24).  The arc-table
    comment described $B57D as "(24) and its spill $B595 (8)".  Driving the
    machine says otherwise: the jump phase runs 1..32, `$AD6E CP $21` is what
    turns 33 into $FF, and phase 32 reads $B59D -- the first byte of the NEXT
    table.  There is no spill; there is a 32-byte table whose last index is one
    off the end and lands on a byte that happens to be in range.
    A structural claim in a comment ("this table is 24 long") is a measurement
    like any other and wants the same treatment: drive the index to its extreme
    and see where it reads.

124. **A CLAMP THAT NEVER TRIPS IS NOT A TESTED CLAMP** (Bubble Bobble, M7.15,
    2026-09-24).  The sound log must stay sorted, so `beepEdge` pins a
    backwards push to the previous time and counts it.  The gate drove it with
    a NEGATIVE frame offset -- which clamps every edge to 0, so they all land on
    the same time and the ORDER guard never fires.  The battery found it: the
    guard could be deleted and the suite stayed green.
    Two different guards on the same line need two different worlds.  The one
    that exercises the order guard is an edge already in the log LATE in the
    frame and a tone emitted EARLY in it.

125. **AN ERASE THAT RESTORES FROM A SHADOW WRITES NOTHING IN A CLEAN WORLD**
    (Bubble Bobble, M7.16, 2026-09-24).  The giant's erase copies the backing
    store back over the display.  In a freshly reset port the display ALREADY
    equals the shadow, so a before/after diff of the screen finds zero changed
    cells -- and a gate that compares "the addresses the erase touched" gets an
    empty list, which compares equal to nothing and passes.
    POISON FIRST.  The same shape as TRAPS #100 (a tautological assertion) and
    #44 (a diff that cannot see an idempotent write): when a routine's job is to
    make memory match something, the test world has to start NOT matching.

126. **A MUTATION THAT REORDERS TWO LINES MAY REORDER NOTHING** (Bubble Bobble,
    M7.16, 2026-09-24).  A case meant to move the presence test AFTER the frame
    store moved it only past the `const clock = ...` line above the store, which
    changes nothing -- and the battery duly reported it as a survivor, which
    read as "the gate is weak" rather than "the case is wrong".
    A survivor is a claim about a PAIR (mutation, suite).  Before strengthening
    the suite, read the mutation and ask what it actually does; two of the six
    survivors in this increment were the case's fault, and one of those two was
    a genuine PROVABLE EQUIVALENT -- an idempotent store, visible in the
    machine's write log and not in the port's memory, which is withdrawn with
    its reason rather than chased.

127. **A GATE THAT DRIVES THE HELPER INSTEAD OF THE ROUTINE TESTS THE TEST'S
    ARITHMETIC** (Bubble Bobble, M7.17, 2026-09-24).  $925A's box test was
    gated by computing B, C, D and E in the test and calling the engine's
    `boxAxis` with them.  It matched the machine's 65,536-position sweep
    exactly -- and FIVE mutations survived it: the `+2`, the `+14`, their eight
    bits, which axis is asked first, and the sixteen-bit form.  None of those
    live in `boxAxis`; they live in the CALLER, and the gate had replaced the
    caller with itself.
    Fourteen of forty-one M7.17 cases survived the first pass for this one
    reason.  When a routine computes its own inputs, the gate must place the
    WORLD and let the routine compute them -- the helper's signature is exactly
    the boundary a test must not step over.

128. **THREE ANCHORS WERE NOT ENOUGH FOR AN EIGHT-BIT WRAP** (Bubble Bobble,
    M7.17, 2026-09-24).  TRAPS #49 says sweep at more than one anchor.  Three
    were swept -- (100,100), (200,150), (250,250) -- and a mutation replacing
    `(v + 15) & 0xFF` with `v + 15` still survived.  `ADD A,15` can only wrap
    for an entity at 241 or above, and the `CP B` above it only lets such an
    entity through when `player + 14` is bigger still: the two arithmetics
    agree everywhere except a player in [228, 241], and none of the three
    anchors was in it.
    An anchor set for a wrap is not "a few spread out": it is derived from
    WHERE THE WRAP CAN HAPPEN.  The fourth anchor, (235,100), accepts 513 and
    is cut off at x = 240 exactly where the wrap bites.

129. **A FLAG CLEAR ON THE COMMON PATH IS INVISIBLE UNTIL THE UNCOMMON PATH IS
    DRIVEN** (Bubble Bobble, M7.17, 2026-09-24).  $925A opens with `XOR A`,
    which clears the carry before the first scan.  Deleting the port's
    equivalent survived, because with the player ALIVE the scan runs on to
    $9308's own `OR A` and clears the flag anyway.  Only a DYING player -- whose
    scan RETs at $92BB without touching the carry -- lets a stale flag reach
    $9269's `CALL c,$927D`.
    Two instructions that clear the same flag need two worlds: one where only
    the first runs.  The same shape as #124's clamp-versus-order guard, one
    increment later.

130. **COLLAPSING TWO SPELLINGS INTO ONE KILLS THE MUTATIONS THAT ANCHORED ON
    THE COPY** (Bubble Bobble, M7.17, 2026-09-24).  $927D had THREE spellings in
    the port -- an uncalled `playerHit`, a second half inside `bossKillPlayer`,
    and the `$9298` arm that was in neither.  Collapsing them (the right move,
    and what M7.11 did for the wind read) left six of B5's mutation cases with
    dead anchors, because every one of them had anchored on the copy.
    Their BEHAVIOUR is unchanged, so they are RE-ANCHORED on the single body,
    not withdrawn -- except one, which became the same (old, new) pair as an
    M7.17 case on the same line and is MERGED with a note saying so.  A dead
    anchor after a deliberate collapse is bookkeeping; a withdrawn case is a
    lost measurement.
    And one of the re-anchored six then SURVIVED: swapping the order of two
    refusals that both write nothing is invisible unless BOTH their bits are
    set, and no row drove that.  The machine cannot tell them apart either --
    nothing in RAM records which RET was taken -- so the port's own label
    carries the claim, and a row with both bits set is what pins it.

131. **A STORE OF THE VALUE ALREADY THERE IS A STORE YOU CAN DELETE** (Bubble
    Bobble, M7.18, 2026-09-24).  `$931E XOR A / LD ($93C4),A` puts a NOP in the
    routine's own code so the enemy sweep corpses what it finds.  Deleting the
    port's equivalent SURVIVED -- because `reset()` already leaves $00 at
    $93C4, so the write was setting the byte to what it held.  The same shape
    as M7.16's idempotent-store equivalent, except this one is NOT an
    equivalent: the byte is live state that the routine's own second write
    ($C9) changes, so between passes it really does need putting back.
    A gate for a store must POISON THE TARGET first, and the poison has to be a
    value the routine can actually meet -- here the $C9 the same routine writes
    forty instructions later.  Three of this increment's five survivors were
    this: $93C4's NOP, and the direction byte the water carry zeroes (already
    zero in the test world).

132. **THE SECOND PLAYER IS HALF THE ROUTINE AND NONE OF THE GATE** (Bubble
    Bobble, M7.18, 2026-09-24).  $931A probes P1, and if P1 is swept up the
    routine RETURNS; otherwise it probes P2 at ITS OWN +7.  Three mutations
    survived the first gate pass -- "P2 is never probed", "P2 is probed at P1's
    +7", and "P1 falls through to P2 after being carried" -- because every
    world the gates built had P2 out of play.
    The same hole M7.17 had one increment earlier (TRAPS #127's P2 half), which
    means naming it once was not enough.  A routine that names two structs
    needs a world with both of them live, and a routine whose two halves are
    mutually exclusive needs the PAIR driven: both players in the same hazard,
    two passes, and the second pass is where the exclusivity shows.

133. **A COUNT IS NOT A FOOTPRINT** (Bubble Bobble, M7.19, 2026-09-24).  The
    banner's erase was gated by COUNTING its calls -- 22 erases, 220 attribute
    restores, 24 attribute runs -- and every count matched the machine.  SEVEN
    mutations survived it: seven rows instead of eight, the display read instead
    of the shadow, the `+11` on the low byte dropped, the erase aimed at the
    position the banner is moving TO rather than the one it is leaving, and the
    recolour's ink changed.  None of those changes a count.
    The fix is three measurements, not one: the ADDRESSES (an ordered list and a
    span), the VALUES (by count per value, because the SET of values is the same
    whichever way round the recolour and the flash are), and a POISONED source
    (the display filled with $5A so "copied from the shadow" is distinguishable
    from "copied from itself").  This is TRAPS #127 one increment on, in its
    other form: there the gate replaced the routine's arithmetic, here it
    replaced the routine's output with a tally of it.

134. **`|` FORGIVES A SIXTEEN-BIT LOW BYTE WHEN THE PAGE ALREADY HAS THAT BIT**
    (Bubble Bobble, M7.19, 2026-09-24).  TRAPS #75 said this about the boss
    erase's attribute walk and it happened again: `ram[(hl & 0xFF00) | l]` with
    `l` allowed past 255 lands on the SAME cell, because every attribute page
    ($58, $59, $5A) already has bit 8 set.  A mutation making `INC L` sixteen
    bits survived a whole battery.
    Written as `+` the mask becomes load-bearing and the mutation dies.  The
    rule: when an address is assembled from a page and an offset, use `+` and
    let the mask carry the eight-bit claim -- an OR hides exactly the bug the
    mask exists to prevent.

135. **A FIXTURE AND AN ENGINE CAN DESCRIBE DIFFERENT MACHINES AND BOTH BE
    RIGHT** (Bubble Bobble, M7.19, 2026-09-24).  $9077 is the operand of the
    flash's `LD A,6` and it ALTERNATES, so it is live state with no
    initialiser: the tape holds 6 and round1_48 holds 3.  reset() seeds the tape
    value, which is what a cold machine has; the oracle captured the other.  The
    flash therefore comes out 3/6/3 in the port and 6/3/6 in the fixture, and a
    gate comparing them directly is comparing two different moments.
    Three of the five censused states differ from the tape in this byte, and a
    fourth (hurryup) has the temper latch already set.  The gate now asserts
    reset()'s value against the TAPE and the behaviour against the FIXTURE'S
    OWN operand -- and the same rule caught ($745C), the threshold, which reads
    1000 on the tape and 1500 in play.

136. **THE FIRST DRAFT OF A SUBSTITUTE GLYPH WAS THE ROM'S** (Bubble Bobble,
    M7.20, 2026-09-24).  `tools/make_hurry.py` draws ten cells to replace the
    Spectrum ROM character set the HURRY UP banner reads, and asserts every one
    that carries ink differs from the cell it replaces.  The '!' I drew -- its
    eight bytes not quoted here: no ROM byte is written in this repository --
    was byte for byte the ROM's, because there is only one obvious way to draw
    an exclamation mark on an 8x8 grid.
    The assert is what said so, which is the whole reason `make_letters.py`
    established it.  A substitute font needs the guard in BOTH directions,
    too: a blank in the ROM must stay blank here, or the assert can be
    satisfied by drawing something visible in a gap.  Two of the ten ARE
    spaces, eight zero bytes in any font, and that is named in the tool rather
    than special-cased around.

137. **TWO IDENTICAL-LOOKING MUTATIONS, ONE LOAD-BEARING AND ONE NOT** (Bubble
    Bobble, M7.20, 2026-09-24).  `ram[(hl & 0xFF00) | l]` in $995A hid a
    sixteen-bit L, because every attribute page already carries bit 8 (TRAPS
    #134).  `ram[((h << 8) | l) & 0xFFFF]` in $802E's blit does NOT, because
    both operands are masked one line earlier and the address is finished with
    `& 0xFFFF` -- which keeps exactly the bits an inner mask would have kept.
    The same is true of `INC H`'s own mask there.
    Both are written the honest way and both mutations are WITHDRAWN as provable
    equivalents WITH THEIR REASONS, because the next reader will see two lines
    that look the same and need to know why only one has a live case behind it.

138. **A 1,100-TICK TRAJECTORY IS A LONG TEST AND STILL A NARROW ONE** (Bubble
    Bobble, M7.21, 2026-09-24).  $917C is a state machine in seven operands, so
    the fixture is its PATH -- 1,100 ticks, every operand, Boris's ten bytes.
    The engine walked it exactly, and NINE mutations survived.
    The path sees two move starts, both on the Y axis, both ARRIVING rather than
    running out of steps, with the step length only ever 2 or 4 and the target
    exactly level with Boris.  So: the X arm's sprite write, the counter-ending
    move, the `NEG` that makes the arrival test a distance, the carry reset on
    the step length, the sixteen-bit wrap in the wait, and reset()'s own seeding
    all had no world at all.
    LENGTH IS NOT COVERAGE.  A trajectory proves the port walks the same path;
    it says nothing about the branches the path did not take, and each of those
    needs a world built for it.

139. **A PROBE THAT LEAKS TEN BYTES OF STACK A CALL LOOKS LIKE A GAME BUG**
    (Bubble Bobble, M7.21, 2026-09-24).  The tick bracket pushes six sentinels
    and the routine pops one, so a hundred and twenty ticks walked SP down
    through whatever was under it and the PC came out at $FE88, inside the RNG,
    which $917C never calls.  Before that, two other probe artefacts wore the
    same disguise: with interrupts on, the real ISR reached the round advance
    and left the bracket at $9781, and Boris's record came back
    `FE 02 FE 04 ...` after 128 ticks -- blamed at the time on $A447 erasing at
    a garbage cached position.  CORRECTED M7.49: it was THIS leak as well, the
    sentinels themselves (#146's signature), pushed over $9250 when the draw
    was run; with SP pinned the draw runs clean.
    Three "the game does something strange after N calls" reports, all three the
    probe's -- and two of them the same leak.  When a driven measurement
    degrades WITH ITERATION COUNT rather than with the input, suspect the
    scaffold: the machine has no idea how many times
    you have called it.

140. **A RESET WORLD ALREADY HELD THE VALUE THE ROUTINE WRITES** (Bubble Bobble,
    M7.22, 2026-09-24).  $7F00 sets (IY+3) := 2 on the slot it fills, and the
    port's bubble pool already reads 2 there after `reset()` -- so deleting the
    write changed nothing and the mutation survived a row that compared all ten
    bytes of the record.
    Poison the whole record first, and then assert BOTH halves: the five bytes
    the routine writes must match the machine, and the five it does not must
    still be the poison.  That second half is what turns "it wrote the right
    values" into "it wrote exactly these and nothing else".  Third time this
    session (TRAPS #131, #125): a store is only tested against a target that
    did not already agree.

141. **A TIDY WORLD HIDES THE LAST SLOT AND THE EXACT THRESHOLD** (Bubble
    Bobble, M7.22, 2026-09-24).  $7EA7 counts twelve pool slots whose +9 is TWO
    OR MORE.  The gate drove the count 0..6 by filling slots from the FRONT with
    the value 3 -- so slot 11 was never the one that mattered and `>= 1` was
    never distinguishable from `>= 2`.  Both mutations lived.
    A loop bound wants its LAST iteration to be the load-bearing one, and a
    comparison wants a value ON the boundary.  One live element in slot 11, and
    one slot holding exactly 1, killed both.

142. **SOME WRITES ARE UNOBSERVABLE FROM INSIDE THE PORT BECAUSE THE OBSERVER IS
    THE INTERRUPT** (Bubble Bobble, M7.22, 2026-09-24).  $7EC7 clears the even
    ISR gate and $7F05 puts it back, bracketing the slot write so a mid-write
    interrupt cannot see a half-built element.  In the port nothing runs between
    those two lines -- the ISR is called at frame boundaries -- so deleting the
    clear changes no byte any check can read, and the mutation survived.
    The claim is real and the port keeps it, so the row is made about the
    SOURCE: both writes present, in order, inside the routine.  That is the
    honest shape for a guard whose only observer is a thing the port models
    elsewhere -- neither a survivor to shrug at nor a behaviour to invent.

143. **A GATE THAT CAN NEVER BITE AT THE VALUE YOU DRIVE IT AT** (Bubble Bobble,
    M7.23, 2026-09-24).  $9B31 is `LD A,($AA57) / SUB 3 / CP C / RET c`, the
    spawner's check that the drawn enemy index exists.  The oracle drove it at
    index 0 with counts 12 and 3 and both passed, so the phase was written down
    as "($AA57) is too small for the index -> still spawns" and proved nothing.
    At index 0 the comparison is (count - 3) against 0, and `SUB 3` is EIGHT-BIT:
    a count of 2 wraps to $FF and passes harder than 12 does.  The gate can only
    refuse high in the roster.  Re-driven at index 6 -- the largest a draw of 7
    can make -- it refuses 6, 7, 8 and 3, and passes 9, 10, 12, 2 and 0.  The
    wrap is a real 1987 behaviour and the port now reproduces it.
    Before sweeping a comparison, work out the input at which its two sides can
    actually straddle.  A sweep taken where every value lands on the same side
    of the branch is a table of one answer.

144. **A SWEEP THAT FINDS NOTHING MUST SAY SO OUT LOUD** (Bubble Bobble, M7.23,
    2026-09-24).  $5B0A is reached by FALL-THROUGH from $5B00's handler, and to
    see it filled at all the first PRNG draw must spawn nothing and the second
    must spawn something -- because a successful first draw MARKS the enemy and
    the second draw then finds nobody.  The phase swept 4,096 seeds for the pair
    (0, 1), found none, and silently wrote a fixture whose "second slot" rows
    never once filled the second slot.  Two of the three arms passed on a port
    with one slot.
    The fix was both halves: print the census of what WAS reachable (`(g0) 4096
    seeds swept ... second draws reachable: 2 3 6 7`), take any of them instead
    of insisting on one, and `assert` in the tool that at least one arm really
    filled $5B0A.  A sweep with no hit is not a null result; it is a sweep that
    has not run.

145. **THE MUTATION THAT RE-TESTS A CHECK THREE LINES ABOVE IT** (Bubble Bobble,
    M7.23, 2026-09-24).  One M7.23 case meant to stop the generator advancing on
    a refused draw.  What it actually inserted was a copy of $9B1E's
    `BIT 7,(IX+7)` -- a test that had already passed on every path that reaches
    the draw.  It changed no behaviour, survived, and sat in the survivor list
    looking like a hole in the gates.
    A survivor is a claim about the SUITE; a mutation that mutates nothing is a
    claim about nothing.  Read every survivor's diff before writing the gate it
    seems to ask for, or you will write a check for a bug that cannot exist.
    (The real case -- snapshot $FE86/$FE87 and restore them when the draw is
    refused -- dies on the row that says the generator advances twice.)

146. **A SNAPSHOT TAKEN BEFORE THE PROBE ARMS REPORTS THE PROBE'S OWN STACK**
    (Bubble Bobble, M7.24, 2026-09-24).  `tools/extenddone.py`'s first run said
    `$948F` writes 128 bytes.  It writes 112.  The sixteen extra were the
    harness's own sentinel return addresses, pushed by `arm()` AFTER the "before"
    snapshot was taken -- and they were obvious in hindsight, because the diff
    read `FE 02 FE 04 FE 06 FE 08`, which is the sentinel list counting up.
    Snapshot AFTER arming, and drop only a named window below the armed SP for
    the routine's own CALL/RET traffic.  A probe's scaffolding is not a finding.

147. **A FILTER WIDE ENOUGH TO HIDE THE MEASUREMENT IS WORSE THAN THE ARTEFACT**
    (Bubble Bobble, M7.24, 2026-09-24).  The fix for #146 was `if (ad < floor):
    continue`, with `floor` the armed SP.  The stack on this state sits at
    `$96CB` -- so that one line silently dropped the entire display file, every
    game variable below `$96CB`, and `$7E0E`, which is the ONE byte `$7E04`
    writes and the whole point of that branch.  The count went down and looked
    tidier.
    Exclude a NAMED WINDOW, never a half-line.  And report what was dropped
    beside what was kept, so the next reader can see the size of the hole.

148. **A GATE THAT MEASURES THE STEP BEFORE THE ONE IT NAMES** (Bubble Bobble,
    M7.24, 2026-09-24).  The round-start row poisoned the twelve EXTEND letter
    cells with `$5A`, ran `roundStart()`, and asserted they were no longer
    poison -- claiming that `$986F`'s `CALL $957E` had drawn them.  But
    `roundBuild()` repaints the whole playfield earlier in the same sequence, so
    "no longer `$5A`" was true whether or not `$957E` ran at all.  The battery
    made `$986F` a no-op and the row lived.
    When a routine runs late in a long sequence, poisoning at the top measures
    whatever runs FIRST.  The fix is a DIFFERENCE: the same sequence with the
    masks at `$00` against the same sequence with them at `$3F`, and the twelve
    cells must disagree.

149. **SIX THINGS LOST TO ESCAPE HANDLING** (Bubble Bobble, M7.24, 2026-09-24).
    The running tally: four heredocs that ate `\n` and produced
    `SyntaxError: unterminated string literal`; a check row whose regex was
    built by concatenation and lost its `\b`; and now a row whose regex was
    written `/this\\.elemRedraw\\(\\)/` -- matching a literal backslash,
    matching nothing, and failing a check EVERY OTHER PART OF WHICH PASSED.
    The same run left `\u2019` sitting raw in sixty-two labels.
    The standing rule, now earned six times: build source with the Write/Edit
    tools or `repr()`, never a shell heredoc; and prefer a plain-string
    `split(...).length - 1` to a regex when all you are doing is counting
    occurrences.

150. **TWO STATES IN THE ROSTER ARE HUNG 128K CAPTURES** (Bubble Bobble, M7.24,
    2026-09-24).  Reconnaissance over all 57 `build/*.pkl` found `play1p.pkl`
    (PC `$8E07`) and `play2p.pkl` (PC `$8E08`) sitting INSIDE `$8E05`'s delay
    loop with its operand `$8E06` at `$00` -- 300,000 steps from each visits
    only `{$8E05, $8E07, $8E08}`.  They are 48K images captured before `$9690`
    patched the branch, and they never leave.  `iball.pkl` is not a state of
    this build at all: 4,036 bytes differ from `image_tape.bin` in `$8000-$8FFF`
    alone, against 55 for `round1_48.pkl`.
    Any sweep that says "measured on all states" must say WHICH, and the 48K
    branch check (`$8DC4 == $C9`, TRAPS #28/#36) is what separates them.  Note
    the three patch bytes are INTERLOCKED: `$9690` writes `$C9` to `$8DC4`,
    `$8E05` and `$8E0A` together, and patching `$8DC4` while leaving `$8E05`
    alive hangs the machine, because `$8E05`'s `JR nz` returns to its own
    `LD C,n` and only `$8DC4`'s tail refreshes the operand.
    **CORRECTED 2026-10-13 by the M10 recon** (C22, confirmed by D: docs/M10-PLAN.md 1.8).  The two states
    are NOT hung.  They sit in round 1's `$98F5` wait for sound 7's pass end (`$FED4` = 7, `$8E06` = 0).
    With interrupts ON the ISR's hook ticks the engine, which the flat image holds over its sprites, and both
    states fall into `$8E0A` after 152 frames.  The 300,000-step trace above holds only with interrupts OFF.

151. **A PROBE THAT CANNOT AIM IS NOT A MEASUREMENT** (Bubble Bobble, M7.25,
    2026-09-24).  `tools/extcomp.py`'s first run reported that PLAYER TWO CANNOT
    COMPLETE EXTEND -- 256 values swept, none accepted.  The routine was fine.
    The tool set IX by writing registers 13 and 14, and in this simulator IXh
    and IXl are 8 and 9; 13 and 14 are SP-adjacent and I.  IX never moved off
    whatever the state happened to hold, which was P1's address, so every P2
    sweep was a P1 sweep with P2's letters poked.
    A sweep that finds a whole arm dead is reporting on the probe until proved
    otherwise.  Read the harness's own register table rather than guessing a
    conventional layout.

152. **A POISON WIDER THAN THE ROUTINE MEASURES ITS NEIGHBOURS** (Bubble Bobble,
    M7.25, 2026-09-24).  The wipe phase filled `$DF00..$FFFF` with `$5A` and
    then reported `$94EA`'s LDIR as "6,915 bytes, `$E000..$FEC5`, 963 gaps
    inside".  The LDIR does exactly 6,912 contiguous bytes; the extra three were
    `($FEC4)` and `($FEC5)`, which `$94CD`/`$94D0` zero TWENTY-NINE BYTES EARLIER
    in the same routine, and the 963 "gaps" were simply the poison between the
    two regions.
    Poison as wide as the question and no wider, and report a CONTIGUOUS RUN
    rather than a set -- a set cannot tell "it cleared this range" from "it
    cleared this range and something else cleared two more bytes".

153. **ATTRIBUTE THE WRITES BY PC BEFORE EXPLAINING THEM** (Bubble Bobble,
    M7.25, 2026-09-24).  The item-shower phase counted 283 changes from a loop
    that makes 320 writes, and the obvious story was a second writer -- `$8689`
    ageing the records it had just been handed.  Splitting the changes by the PC
    that made them killed that story in one line: `$951C` 123 and `$9527` 160,
    both inside the loop, and `$8689` writes NONE of these bytes.  The 37
    "missing" are stores whose value already agreed, because byte0 carries a
    two-bit PRNG draw that repeats over ten passes.
    The attribution costs one variable and it is the difference between a
    measurement and a plausible story.

154. **A CENSUS IS ONLY COMPARABLE TO ONE TAKEN OVER THE SAME WINDOW** (Bubble
    Bobble, M7.25, 2026-09-24).  The oracle's call census stops at `$9553`,
    because everything past it is two multi-million-T delays.  The gate compared
    the PORT's whole run against it and failed on `$806C`: two on the machine,
    three in the port.  Both are right.  `$955B` is past the abort line.
    A window is part of a measurement.  Either compare like with like, or
    capture the full-run figure as well and say which is which -- and when a
    count disagrees by exactly the number of calls past the boundary, suspect
    the boundary before the port.

155. **"NOT IDENTICAL" IS NOT "A DIFFERENT FACE"** (Bubble Bobble, M7.26,
    2026-09-25).  Every substitute font in this port is policed by an assert that
    the glyph is not byte-for-byte the ROM's cell.  The first drafts of the new
    T and F passed it while differing in ONE and TWO bytes of eight -- a T whose
    only change was a narrower crossbar, and an F whose only change was a
    narrower top bar.  They are the ROM's letters with a haircut.
    The assert is a MINIMUM now: an inked glyph must differ in at least three of
    its eight bytes, and the per-glyph count is printed as evidence.  A rule that
    a lazy draft can satisfy is a rule that will be satisfied lazily.

156. **THE OUTER MASK CAN ABSORB THE INNER ONE** (Bubble Bobble, M7.26,
    2026-09-25).  Two mutations made `INC H` sixteen-bit instead of eight in the
    banner blits, and both survived.  They are provable equivalents: the address
    is built as `((h << 8) + l) & $FFFF`, h rises by at most seven inside one
    glyph, so it can never reach $200 and the outer truncation does the inner
    mask's job.  Verified rather than argued -- the two spellings were run side
    by side over all 256 start pages times four columns, and not one world
    differs.  The same reasoning retires `(h << 8) | l` versus `+ l` HERE while
    leaving TRAPS #134 intact THERE, because #134 is about a left operand whose
    low byte is not zero.
    When a mutation to an arithmetic width survives, look for a wider mask
    downstream before writing a gate for it -- and check by running both, not by
    reasoning about both.

157. **A GATE NAMED FOR A WRAP THAT DRIVES NO WRAP** (Bubble Bobble, M7.26,
    2026-09-25).  The row for $803F's eight-bit `INC L` started a string at
    column 30 and reported "columns 30, 31, 0, 1 -- WRAPPED inside the third".
    From $487E the low byte runs $7E $7F $80 $81 and never carries; the "column
    0" is the ROW field of the display address changing, which every walk does.
    Three separate mutations to the three adds lived behind that sentence.
    Each of $803F's `INC L`, $8054's `INC H` and $805D's `ADD HL,BC` is now
    driven from an address where THAT add is on its boundary -- $48FE, $FC40 and
    $48FE respectively.  A wrap has an address; find it before claiming it.  This
    is TRAPS #143's rule for comparisons applied to arithmetic.

158. **A MUTATION CAN BE SUPERSEDED BY CONSTRUCTION, AND THAT IS THE POINT**
    (Bubble Bobble, M7.27, 2026-09-25).  Folding the two substitute fonts into
    one code-indexed table killed three mutation cases outright -- "the two R
    glyphs are different shapes", "the two SPACES are drawn with ink", and a
    duplicate `INC L` -- not because the gates got weaker but because the bugs
    stopped being expressible.  There is ONE R now and the string reaches it
    twice; there is no second space to make differ; there is one walk, so there
    is one place to break it.
    A withdrawal like this is evidence that a refactor removed a CLASS of bug,
    and it is only honest if it says which row carries the claim afterwards --
    here the pixel-neutrality row, which asserts that positions 2 and 3, 1 and 6,
    and 5 and 8 resolve to the same cell.  "Superseded by construction" is a
    reason; "it stopped applying" is not.

159. **A GATE THAT WIPES ALL 64K REMOVES THE THING UNDER TEST** (Bubble Bobble,
    M7.27, 2026-09-25).  M7.20's `INC H` row zeroes the whole world image and
    then prints the HURRY banner at $FCFB to watch the rows wrap $FF -> $00.
    That worked while the glyphs came from a JS constant and the string was
    implicit.  M7.27 moved the string into the byte image at $9A1C, where the
    machine keeps it -- so the wipe deleted the string, the printer hit a NUL
    immediately, and the row failed.
    The row was right and the wipe was too wide.  When DATA migrates into the
    world image -- which is the direction this port keeps moving -- every
    wholesale `for (a = 0; a < 0x10000) ram[a] = 0` in the suite becomes
    destructive, and the fix is to put back what the routine reads and say why.

160. **"UNREACHABLE" IS A CLAIM AND IT NEEDS ENUMERATING, NOT SAMPLING** (Bubble
    Bobble, M7.28, 2026-09-25).  A mutation removing the `AND 3` from $9904's
    attribute-page derive survived.  I drove it at $7AFA, saw the masked and
    unmasked answers agree, and was one keystroke from withdrawing it as
    unreachable.  They agree there because `OR $58` already has bits 3 and 4
    set, so the mask only changes an answer when the shifted page has BIT 2 set
    -- and enumerating all 256 start pages gives $19..$38, $59..$78, $99..$B8
    and $D9..$F8, of which $60 is ordinary RAM.  The world existed; my sample
    was in the wrong place.
    The sibling case in the same routine -- the eight-bit `INC D` -- really is
    unreachable, and the way that was established is the same enumeration, not
    the same hunch.  When withdrawing anything as "cannot happen", enumerate the
    input space; a single disagreeing sample is not evidence of a rule.

161. **A STUB THAT MODELS THE OUTCOME STOPS BEING HONEST WHEN ITS NEIGHBOUR IS
    WIRED** (Bubble Bobble, M7.28, 2026-09-25).  $9904 was a NAMED COUNTED STUB
    that RESTORED the twenty attribute cells to whatever they held before the
    round banner ran.  That was a fair model of the OUTCOME while the banner's
    glyphs were not being drawn -- the end state really was byte-identical, and
    the port reached it by a different route.  Wiring the glyphs made it wrong
    at once: a restore cannot put back eighty display bytes it never saved, and
    the real routine does not remember anything, it rebuilds from the SHADOW and
    re-derives the attributes from bit 5 of the COLOUR shadow.
    Outcome-modelling stubs are fine and should say so -- this one did -- but
    they are coupled to what is stubbed AROUND them.  When wiring X, check every
    stub whose correctness rested on X staying stubbed, and expect them to come
    as a pair.

162. **NEW CODE CAN KILL AN OLD ANCHOR WITHOUT MOVING IT** (Bubble Bobble,
    M7.28, 2026-09-25).  The battery's DEAD ANCHOR verdict has always meant "the
    increment moved the code this case pointed at".  This one meant something
    else: H11's mutation anchored on a one-line copy loop, and $9904's LDIR is
    spelled identically, so the anchor started matching TWICE and the runner
    could not place it.  Nothing H11 cares about changed at all.
    Both failures look the same in the report, and the fix is different: a moved
    anchor is RE-ANCHORED to where the code went, an ambiguous one is given the
    CONTEXT that distinguishes the two sites -- here the enclosing method.  When
    a dead anchor points at code that is still exactly where it was, count the
    matches before rewriting anything.

163. **ADDING A PARAMETER DEGRADES EVERY EXISTING CALLER SILENTLY** (Bubble
    Bobble, M7.29, 2026-09-25).  `bossBanner` gained a fourth argument -- the
    string to print -- and the two older rows that drive it kept passing three.
    JavaScript gave them `undefined`, `undefined & 0xFFFF` is 0, `ram[0]` is the
    zero the ROM window holds, and the printer stopped at once.  Both rows WENT
    ON PASSING while the thing they now covered drew nothing at all.  The suite
    was green and one of its newest paths was dead.
    The fix is a DIAGNOSTIC, not a default: `bannerPrint` throws on a
    non-integer address, the way `prngNext` throws on an unlisted site.  House
    rule 6 is usually read as being about runtime fallbacks; it applies just as
    hard to an argument that silently arrives as `undefined`.  When a method
    gains a parameter, grep every call site -- the compiler will not.

164. **A COUNT AND A TERMINATOR ARE TWO DIFFERENT BOUNDS IN ONE CALL** (Bubble
    Bobble, M7.29, 2026-09-25).  `$8E83` loads B with ELEVEN and `$8E7A` points
    IX at "WELL DONE!", which is TEN characters.  `$995A` is bounded by B and
    `$802E` is bounded by the NUL, so the attribute run is one cell WIDER than
    the text it colours -- and the eleventh cell is coloured while the eleventh
    character cell is never drawn.
    That asymmetry is invisible while the glyphs are COUNTED rather than DRAWN:
    a stub that added `n` to a glyph tally agrees with the machine on every
    number except the one that matters.  Gate the two bounds separately, and in
    one world -- `ram[$5955] === $C5 && ram[$4855] === $5A` says it in a line.

165. **I COUNTED MY OWN TABLE AND CALLED IT A CENSUS** (Bubble Bobble, M7.29,
    2026-09-25).  "$8EA7 was the last $802E call site" went into a check label,
    the SPEC, the progress log and very nearly a commit message.  It is false:
    the image holds NINE references to $802E and four are still counted rather
    than drawn -- the HUD's two rows at $7FE9/$7FEF, "GAME OVER" at $8CEE and
    "CREDIT n" at $9758.  What I had actually counted was the six strings in
    BB_BANNER_STR, which is the port's own list of what it already does.
    `python tools/grepbytes.py "2E 80"` takes ten seconds and would have said so
    at any point.  A claim about COVERAGE has to be measured against the IMAGE,
    never against the port's own table of what it has done -- that table cannot
    know what is missing from it.  The row is a census now and asserts both
    halves: the six that draw, and the four that do not.
    The same sweep found a comment on treasurePerfect that had said "$801D and
    $994F, neither of which is transliterated yet" for three increments after
    M7.26 transliterated both.

166. **TWO BATTERIES AT ONCE PRODUCE NOISE, AND THE NOISE LOOKS LIKE FINDINGS**
    (Bubble Bobble, M7.29, 2026-09-25).  I started a second full run while the
    first was still going.  `scratchpad/battery/parallel.py` gives each worker a
    FIXED directory -- `workers/w0..wN` -- so the two runs handed each other
    half-mutated trees.  The report came back with SIXTEEN survivors scattered
    across ARC, PATCH, M7.16, M7.20, M7.21 and the walker: milestones untouched
    in weeks, every one of them plausible enough to spend an hour on.  The same
    tree, run alone, gives ZERO.
    The tell was one line I nearly scrolled past: `WORKER 2 FATAL: baseline RED`.
    A worker whose baseline is red is not testing anything, and the runner
    already knows to shout when EVERY case survives (TRAPS #118) -- it did not
    know to shout when its own tree was being edited underneath it.
    The runner takes a LOCK now and refuses a second run by name and pid.  The
    working tree was never touched, which is the one promise that held.  Related:
    do not edit `web/game.js` or `test/bb.test.js` mid-run either -- I did that
    in the same session and threw away a seventeen-minute result.

167. **THE BASELINE ASKED WHETHER ANYTHING FAILED, NOT WHETHER THE SUITE PASSED**
    (Bubble Bobble, M7.30, 2026-09-25).  A heredoc turned an escaped newline into
    a real line break inside a JS string, so `test/bb.test.js` stopped parsing.
    `baseline()` collected lines beginning with `FAIL`, found none -- a crash
    produces none -- and declared the worker healthy.  Every case then died on
    the same crash.
    The per-case logic already knew better: no summary plus `SyntaxError` is
    BROKEN-MUTANT, not a kill (TRAPS #107's rule).  The BASELINE had no business
    being laxer than the cases it guards.  It now requires the POSITIVE signal --
    the `N/N checks passed` line -- and a plausible check count, so a suite that
    parses but exits after two checks is not a baseline either.  Verified by
    breaking the suite on purpose: the workers report `baseline DID NOT RUN` and
    the run lists ZERO cases instead of claiming kills.
    The general rule: a health check must look for the evidence of health, never
    for the absence of evidence of illness.

168. **NINE THINGS NOW LOST TO SHELL HEREDOCS** (Bubble Bobble, M7.30,
    2026-09-25).  The tally: four Python files whose `\n` collapsed, one regex
    built by concatenation that lost its `\b`, one written with doubled
    backslashes that matched a literal one, sixty-two labels left carrying a raw
    `\u2019`, a lock block in the battery runner, and now a check row whose
    `src.indexOf('\n  }')` became a line break -- which took the whole suite
    down and hid it behind a green battery (TRAPS #167).
    Twice now the script has WRITTEN the broken file and compiled it afterwards,
    so the repo carried a syntax error for as long as it took to notice.  The
    rule is not just "use the Write tool": it is **round-trip through a temp file
    and parse it BEFORE writing the real one**.  Both repair scripts in this
    increment do that (`node --check` for JS, `py_compile` for Python), and that
    is the pattern to copy.

169. **I GENERALISED FROM THE MEMBERS I HAD MEASURED -- FOUR TIMES, GETTING A
    DIFFERENT ANSWER EACH TIME** (Bubble Bobble, M7.31, 2026-09-25).  One
    property, four claims:

    | claim | source | verdict |
    |---|---|---|
    | "the off-by-one BELONGS to the hand-coded sites" | M7.30, from 2 of 3 | wrong |
    | "1 of 3 exact" | M7.31 first pass, from a list I typed | wrong |
    | "4 of 6 exact" | a verification pass, from a wider read | wrong |
    | **"5 of 7 exact"** | the phase's own ENUMERATION + assert | right |

    `$8E83` loads 11 attribute cells for a ten-character string and `$9760` loads
    9 for eight, while the `$9A85` table gets it right four times out of four.
    From those two I wrote, in SPEC.md and in a check label and in the progress
    log, that the off-by-one BELONGED to the hand-coded sites.  M7.31 measured a
    third, `$8CF6`, found it exact, and wrote "1 of 3" -- **inside the same
    increment as this entry warning against exactly that move.**  A verification
    pass then found `$98CA`, `$98DA` and `$9948`, all exact.  And the assert I
    finally added -- *every `$995A` site with an immediate `B` must be named* --
    found `$9074` on its first run: a SEVENTH site, which colours the same ten
    cells as `$9948` and flashes them from `$9068`'s border loop, with the colour
    living in the operand at `$9077`.
    Every wrong number came from a list I typed.  The right one came from a scan.
    And note what the scan had to cover: `CALL` **and** `JP`, because `$A04B` and
    `$A08D` reach `$995A` by jump and a `CD 5A 99` census cannot see them -- the
    same shape as `phase_writers` finding two of `$FEC9`'s three.
    **And no story survived the count either.**  "Ten-character strings are exact,
    odd lengths carry a spare" is the obvious pattern and `$8E83` kills it: eleven
    cells for the ten characters of "WELL DONE!".  Five of seven are exact and
    nothing about the strings separates the two that are not.  The finding is a
    bare count, and it is written as one on purpose.
    The rule: **a claim about a CATEGORY is not earned by the members you have
    measured -- enumerate the category IN CODE, and make the enumeration assert
    that nothing is unnamed.**  TRAPS #160 is the same shape from the other end
    (do not call a mutation unreachable without enumerating the 256 cases) and
    #165 is it again (do not count coverage from your own table).  What this one
    adds: writing the lesson down does not protect you from it.  Only the assert
    does.  *When a sentence says "always", "belongs to" or "never", the next
    commit contains a loop.*

170. **THE ORACLE ALREADY EXISTED AND I NEARLY WROTE OVER IT** (Bubble Bobble,
    M7.31, 2026-09-25).  I composed a new `tools/gameover.py` -- eighteen
    hundred bytes of phases for the GAME OVER screen -- and a shell heredoc
    failed on a quote before it could be written.  `ls` then showed
    `tools/gameover.py` already present at 18,744 bytes: the H13-B1 increment's
    oracle for the SAME routine, which already measured the 256-frame countdown
    (`phase_countdown`), the three writers of `$FEC9` including the one that INCs
    through HL (`phase_writers`), the `$96DF` reset and the screen's changed
    cells.  A broken heredoc is what saved it.
    Worse, I had spent three subagents' time on questions that file answers, and
    had to send one of them a correction mid-flight.
    The rule: **before writing `tools/X.py`, list `tools/`.**  This repo has
    ninety-odd tools and an eight-month memory; "is there already one for this?"
    costs one command and the alternative is silent destruction of measured work.
    The same applies to a phase name inside an existing tool -- `phase_glyphs`
    went in beside `phase_screen` rather than replacing it, because the old
    measurement was right for the gate it served.

171. **ONE COUNTER, TWO MEANINGS, AND NOTHING SAID SO** (Bubble Bobble, M7.31,
    2026-09-25).  `bannerGlyphs` counts GLYPHS DRAWN at `$8EA7` and at `$98C4`
    -- `+10` each, the NUL deliberately not counted.  At `$8CF6` it counted
    FRAMES OWED, `+1` per redraw, because the glyphs were a declared departure
    and there was nothing else to count.  Same name, two units, and a gate
    asserting `bannerGlyphs === 2` after two calls looked exactly like the gates
    asserting `+10` after one.
    A declared departure needs a counter, and the cheap move is to reuse the
    counter the real behaviour uses.  That is precisely when the name must
    change: the departure counter and the behaviour counter are not the same
    quantity, and once the departure closes the two silently merge into a number
    that means neither.  Drawing the nine made it uniform (`+9`, the NUL still
    not counted) and the row that says so is the only record that it ever was
    not.
    The rule: **a counter's name states its unit; a declared departure counts in
    its own name.**

172. **A DIFF CANNOT SEE A WRITE THAT CHANGES NOTHING, AND MY FIRST EXPLANATION
    OF WHY WAS ALSO WRONG** (Bubble Bobble, M7.31, 2026-09-25).  `phase_screen`
    measures the game-over banner by snapshotting `$4000..$5B00`, running the loop,
    and diffing.  It reports **51** changed bitmap cells.  The banner writes
    **72**.
    I wrote that the snapshot must be taken after the loop had already drawn once.
    **It is not**: `frames()` evaluates `watch(p, f)` on the PC about to execute,
    so it stops AT `$8CDC` with `$484C` = `$7F` -- play-field bytes, nothing drawn.
    The real reason is better and it is measured: of the 72 writes, **24 are `$00`**
    (the blank top and bottom row of every glyph, plus the space character) and
    **21 of those land on a byte that already holds `$00`**.  72 - 21 = 51, exactly.
    **There is no CLS**: the banner draws straight onto the live play field, so 51
    is a fact about `round1_48`'s wallpaper and not about the banner.
    That was SOUND for the gate it served, which asserted `> 0` against an engine
    drawing none: the number did not matter and the row only had to prove the
    machine drew something there.  It stops being sound the moment a DRAWING engine
    is compared against it, and 51 is exactly the kind of plausible wrong target
    that gets adopted without question.
    The rule: **to count what a routine WRITES, watch the write; to count what it
    CHANGES, diff.**  Those differ by however much of the output already happened
    to be there, which is a property of the WORLD and not of the routine.
    `phase_glyphs` watches `$8052` and gets 72; both numbers are in the fixture and
    a row asserts the inequality, so neither can be mistaken for the other again.
    And the smaller lesson: when a measurement disagrees with the code, find the
    mechanism before naming it.  I had a plausible story (stale snapshot) and it
    cost nothing to check -- `stopped at PC = $8CDC` and one dump of the row.

173. **"NO ROM BYTE IS RECORDED" QUIETLY BECAME "NO VALUE IS CHECKED", AND A
    ROUTINE WROTE ZEROS FOR WEEKS** (Bubble Bobble, M7.32, 2026-09-25).
    `digitGlyph`, the `$7FAF` transliteration, fetched its glyph byte like this:

        ram[((d << 8) | l) & 0xFFFF] = BB_DIGITS[digit * 8 + i + 1];

    `BB_DIGITS` is TEN EIGHT-ELEMENT ARRAYS.  A flat index yields an inner **Array**
    for 0..9 and **undefined** above, and a `Uint8Array` element store coerces both
    to **0** without throwing -- `Number([..])` is `NaN`, and `NaN` truncates to
    zero.  So every round-number digit drew seven zero bytes, while `roundDigits`
    reported a faithful call count, faithful `$9A0E`/`$9A0F` ASCII and faithful
    `$F840`/`$F841` colour writes.  The other consumer of the same font,
    `scoreGlyph`, indexes it correctly -- **one font, two consumers, two beliefs
    about its dimensions.**
    **WHY NOTHING CAUGHT IT IS THE LESSON.**  This project ships no Spectrum ROM and
    its fixtures deliberately record destinations and source ADDRESSES and no ROM
    bytes.  That is right.  What it became is "no value is ever compared", including
    the bytes of the port's OWN substitute fonts -- which are the port's data, are
    in the built page, and could have been compared from the first day.  The nearest
    row diffs the engine WITH digits drawn against the same engine WITHOUT and
    requires the changed set to be a non-empty SUBSET of the machine's glyph
    addresses.  **All-zeros is a valid subset.**  Its label even states "the engine
    differs from the machine on SIX bytes" -- a number its predicate never reads.
    The rule: **a declared departure still has bytes, and they are YOUR bytes.**
    Refusing to record the original's data in a fixture does not excuse never
    checking the substitute's.  Concretely: for every glyph a port draws from a
    substitute table, one row must compute the expected byte FROM THAT TABLE and
    compare it at an address the oracle measured.  A destination-only row cannot
    tell drawing from erasing.
    And the smaller tell, worth grepping for on its own: **a number stated in a
    check's LABEL that the predicate never reads.**  That is a claim with no test
    behind it, sitting inside something that looks tested.

174. **A LOOKUP THAT IS WRONG FOR EVERY INPUT CANNOT SHOW YOU THAT ITS DOMAIN IS
    WRONG TOO** (Bubble Bobble, M7.32, 2026-09-25).  Fixing #173 I added a
    diagnostic throw beside it -- house rule 6, never let a fallback engage
    silently, since falling back on zero and reporting success is exactly what the
    bug did.  **It fired on the first run**: `no cell for digit 12`.
    A SECOND, independent fault had been sitting underneath.  The port's signature
    took a DECIMAL DIGIT; the machine takes a code.  `$8042` does `ADD A,$30` and
    `$8044` builds `$3C00 + 8*code`, so it draws whatever cell that lands on -- and
    `$7F86`'s divide-by-ten leaves `tens` as high as 25 for a byte round counter, so
    round 128 draws `'<'` and round 255 draws `'I'`.  `$9877`'s settle-window oracle
    sweeps twelve round values and one of them is in that range, so the suite had
    been *driving* the broken domain all along.
    It was invisible because the value fetch was wrong for EVERY input: a lookup
    that always returns the same wrong thing is equally wrong at 8 and at 12, so the
    domain error had no signature of its own.  Two faults stacked in six lines, and
    the first one masked the second.
    The rule: **after fixing a fault that affected every input, re-ask the questions
    the fault could have hidden** -- the domain, the range, the arity.  And prefer a
    THROW to a `|| FALLBACK[0]`: `scoreGlyph` has exactly that fallback and so
    cannot answer whether it is ever asked for a cell it does not have.  A fallback
    is an answer to a question you have then stopped asking.

175. **A GUARD OVER THE REGISTER CANNOT FIND WHAT IS ABSENT FROM THE REGISTER**
    (Bubble Bobble, M7.32, 2026-09-25).  The suite has a row built for exactly this
    job -- *every test-only asset is READ by a check* -- and it had been green for
    weeks while `build/digits.json` sat unread since 16 September.  It iterates
    `port.json`'s asset list.  A fixture that was never REGISTERED is invisible to
    it by construction.
    That mattered: `digits.json` records `BB_DIGITS`, the font whose consumer was
    writing seven zeros per digit (TRAPS #173).  The fixture is byte-identical to
    the engine's table, so a row comparing them would have existed all along -- and
    the tool that writes it already asserts a difference from the ROM, so the whole
    apparatus was there and simply unplugged.
    The fix is to enumerate **the directory**, subtract the register, and require the
    remainder to equal a PINNED list.  A new unregistered fixture then fails, and has
    to be either registered or named with a reason.  The pinned list here came out at
    eight extraction intermediates (each with a producing tool or a suite reference)
    and **fourteen orphans that no tool writes and no check reads** -- itself a
    finding, recorded rather than tidied away, and derived by scanning `tools/` for
    each filename rather than by my judging which looked disposable.
    And the guard is shown to WORK, not merely to be quiet: the same set-difference
    re-run over the listing PLUS a phantom must come back naming exactly the phantom.
    Verified with a real file on disk as well -- it fired and named it.
    The general rule: **a completeness check must enumerate the territory, not the
    map.**  TRAPS #165 is the same lesson about coverage (never count call sites from
    the port's own table) and #169 about categories (enumerate in code, and assert
    nothing is unnamed).  Three shapes of one mistake: asking the record what the
    record contains.

176. **THE PORT AND THE MACHINE CAN AGREE BY ACCIDENT, AND THAT IS NOT A REASON TO
    LEAVE IT** (Bubble Bobble, M7.32, 2026-09-25).  A coercion hunt over the whole
    engine found **213 store sites in 70 methods** that index `ram[var + n]` with no
    `& 0xFFFF`.  All are unreachable from the real slot bases.  Where a fuzz did reach
    one -- `corpseBirth` with the hit pointer at 0, giving `$FFF9` -- the wrapped
    addresses are `$0000..$0002`: ROM, which the machine also ignores.  **So the port
    and the machine produce the same visible result for opposite reasons** -- the
    machine because a store to ROM does nothing, the port because a JS index past the
    end of a typed array is dropped.
    Not reported as a defect, and deliberately not fixed en masse: 213 edits with no
    behavioural difference is churn, and the analysis that says "unreachable" is worth
    more written down than acted on.  But the agreement is a coincidence of two
    different mechanisms, and if either base ever moves into RAM the port stops
    tracking the machine with nothing to say so.
    The rule: **when a port and the original agree, know WHICH mechanism is producing
    the agreement.**  "The output matches" is not the same as "the model is right",
    and the difference only shows up later, when an input moves.
    The same hunt's useful negatives, worth keeping because a clean negative with its
    method stated is a result: all 64 `BB_*` tables deep-proxied for fractional,
    negative, past-end and absent reads; every `Uint8Array` proxied for non-number
    stores; 1,500 frames, rounds 1..81 through the build routines, `roundDigits` over
    all 256 values of `($8609)`, eight banner strings by five destinations,
    `extendPass` over 256 masks, `elementBank` over 256 classes, and all 311 prototype
    methods over ~100 tuples -- 22,557 calls.  No reachable instance of the `$7FAF`
    class survives.  Three latent ones and one wart remain, each guarded by exactly one
    caller and each named in M7-PROGRESS rather than left to be rediscovered.

177. **THE GUARD I ADDED WHILE FIXING SOMETHING WAS DEAD ON ARRIVAL, AND ONLY THE
    BATTERY SAID SO** (Bubble Bobble, M7.32, 2026-09-25).  Fixing `digitGlyph` I wrote

        const g = code >= 0x30 && code <= 0x39 ? BB_DIGITS[code - 0x30] : undefined;

    and the battery's one survivor was the mutation that dropped the guard:

        const g = BB_DIGITS[code - 0x30];

    It survived because it is the same function.  `BB_DIGITS[code - 0x30]` is a cell
    IFF `code - 0x30` is 0..9, which is exactly `0x30 <= code <= 0x39` -- enumerated
    over every digit 0..255, the two forms never differ.  The guard tested a condition
    the array lookup had already decided, and the `g === undefined` branch below was
    carrying the whole domain by itself.
    So the code went, not the mutation.  A survivor pointing at code that does nothing
    means the code should not exist; the domain it was documenting now lives in a
    comment, which is the honest place for a statement that is not a test.
    **The specific trap is that this was code added IN THE ACT OF FIXING A BUG**, when
    the instinct to be careful is strongest and the scrutiny is lowest -- the fix gets
    tested, the belt-and-braces around it does not.  The diagnostic throw added at the
    same moment earned its place immediately (it found a second fault, TRAPS #174); the
    range guard beside it was decoration.  Both felt equally prudent when written.
    The rule: **mutate the defensive code you add during a fix, not just the fix.**
    And note what made this cheap to settle: the mutation already existed because I
    write a case for every line I touch, so the battery answered a question I had not
    thought to ask.
    **SECOND INSTANCE, two increments later** (M7.34): fixing `extendGlyph`'s silent
    fallback I wrote
    `Number.isInteger(k) && k >= 0 && k < BB_LETTERS.length ? BB_LETTERS[k] : undefined`,
    and the mutation deleting it survived -- because `BB_LETTERS[k]` is ALREADY
    `undefined` for `6.2`, `-1`, `6`, `7` and `2.5`, enumerated.  Same shape, same
    circumstance: a guard added in the act of fixing something else, testing a condition
    the lookup had already decided.  Twice is a habit, so the habit is what to watch:
    **when a fix adds a guard, ask what the operation returns WITHOUT it before writing
    it.**

178. **THE GATE WAS ON THE SIGN OF THE DELTA AND THE MACHINE'S IS ON THE PHASE
    COUNTER** (Bubble Bobble, M7.33, 2026-09-25).  `playerJumpFall` decided whether to
    probe the floor with `if (dy > 0)`.  The machine decides with `$AD7D CP $10 /
    JR nc`, and A at that point is the NEW phase -- `$AD6D INC A` has already run and
    `$AD74` has already STORED it -- so the machine probes from OLD PHASE >= 15.
    `dy > 0` first holds at phase 19.  The four phases in between, 15..18, are exactly
    the arc table's ZERO-DELTA entries, so the port skipped the probe on four phases the
    machine takes it on.  **REACHABLE**: any short hop whose apex has floor 16 px below.
    Both rules agree on 13 of the 17 phases either could see, which is why it survived.
    **What made it invisible is that the divergence needs TWO conditions at once** -- a
    phase in 15..18 AND floor on the probe row -- and no shipped world and no existing
    gate happened to place both.  The suite was green because untested, not because
    right, exactly as in TRAPS #173.
    The rule: **a predicate derived from a value is not the predicate the machine
    evaluates, even when it agrees.**  `dy > 0` and `newphase >= 16` are both true
    statements about a descending jump; only one of them is the instruction.  When a
    port's condition is a paraphrase rather than a transliteration, write down the
    instruction it replaces and check the paraphrase over the WHOLE domain -- here, the
    two rules differ on precisely the phases where the delta is zero, which is the one
    place "descending" is ambiguous.
    And the corroboration was sitting in the image: `($ADA1) = $B58B` is the
    self-modified arc pointer left by the last descent probe the real machine ran, index
    14, **phase 15** -- one of the four.

179. **ONE ROUTINE, TWO BOTTOM WRAPS, AND THEY ARE NOT THE SAME WRAP** (Bubble Bobble,
    M7.33, 2026-09-25).  The jump arc has two exits and each clamps Y differently:

        $AD88  CP $C0 / RET c / LD (IY+6),0      the PLAIN arc step  -> Y := 0
        $AD5D  CP $BF / RET c / LD (IY+6),2      the FREE-FALL tail  -> Y := 2

    Different thresholds AND different landing values, one instruction apart in intent
    and 63 bytes apart in the image.  The port modelled neither, using `(y + dy) & 0xFF`
    for both -- and a single mask cannot express two wraps, so no amount of tuning one
    number would have covered it.  `playerFloorTick` shares the second tail and its own
    comment had flagged it as unmodelled since it was written.
    The rule: **when a routine has more than one exit, ask each exit what it clamps.**
    A wrap discovered on one path is not the routine's wrap, it is that path's wrap, and
    the giveaway is a comment saying "the bottom wrap" in the singular.
    Measured: the plain step first wraps from Y `$BE` (result `$C0`) and the free-fall
    tail from Y `$BD` (result `$BF`), so there is a one-pixel band where the two rules
    disagree about whether to wrap at all, on top of disagreeing where to land.

180. **A MASK THAT LOOKS COSMETIC WAS THE SWITCH ON A WHOLE BEHAVIOUR** (Bubble
    Bobble, M7.33, 2026-09-25).  The floor probe has two entry points one instruction
    apart -- `$AE7F LD C,$3F` and `$AE81`, which the floor tick enters with `C := $20`
    already loaded.  I had a port helper with `$20` hard-coded and a note that the
    difference was "measured as 0 differing cells over shipped data", i.e. cosmetic.
    It is not.  After the probe decides a cell is solid it runs `$AE9C AND $20`:

        AE9A  LD E,1
        AE9C  AND $20              <- PATCHED TO $C9 (RET) around the FEET probe
        AE9E  JR z,$AEA1
        AEA0  RET                     solid under $20 -- an ordinary floor
        AEA1  BIT 1,(IY+8) / JR z,$AEAD
        AEA7  LD (IY+9),1 / POP HL / RET    *** sets the JUMP PHASE and UNWINDS ***

    With `C = $20` the `AND` is always non-zero and `$AEA0` returns.  With `C = $3F` a
    cell solid only in bits 0..4 -- the walker's claim and release bits -- falls through,
    and with `(IY+8)` bit 1 set the probe **sets the jump phase to 1 and POPs the
    caller's return address**: a bounce that returns past its caller.  The mask is the
    switch.  And that is why the floor tick patches `$AE9C` to `RET` for its feet probe
    and restores it for the row below: to choose which probe may bounce.
    **The equivalence measurement was true and the conclusion drawn from it was wrong.**
    Zero shipped cells have a low bit set -- I re-measured it, ten shadows, zero -- so
    the two masks select the same cells today.  That makes the mutations unkillable, and
    it says nothing about whether the masks mean the same thing.
    The rule: **"observationally equivalent on the data I have" is not "the same
    operation."**  When a constant differs between two call sites of one routine, find
    what reads it downstream before concluding the difference does not matter; the
    distinguishing input may be one the shipped captures never contain because it is
    written at RUNTIME.
    Consequence recorded rather than papered over: the three mask mutations are
    WITHDRAWN, with the note that the world distinguishing them is exactly the world
    that reaches the unmodelled bounce -- so they cannot be gated until it is modelled,
    and gating them against a half-modelled world would assert something false.
    **RESOLVED (M7.34): the bounce is REACHABLE and the masks are genuinely different.**
    A measurement pass counted **21 hits at `$AEA7` over 67,540 measured video frames
    from key scripts alone, nothing poked** -- it is the BUBBLE-JUMP.  The low five bits
    of a colour-shadow cell are a BUBBLE INDEX, claimed by `$B8C0` (`AND $E0 / OR tag`)
    and released by `$B6D6` (`AND $E0`), the tag for slot *j* being `12 - j`.  So the
    suspicion in this entry was right, the withdrawal was the right call, and the three
    mutations come back when M7.35 models the tail.

181. **WHEN NO CALLER CAN EXPRESS A DIFFERENCE, GATE THE ROUTINE AT ITS OWN ENTRY**
    (Bubble Bobble, M7.33, 2026-09-25).  A mutation turning the floor probe's
    `$AE92 AND 6` into `AND 7` survived a full battery.  The two differ only at X = 1
    mod 8, and no mover produces an odd X: driving `$ADAA` over all 256 X by four
    direction bytes -- 1,024 runs -- **X parity is preserved**, 512 even-to-even and
    zero even-to-odd, and the player starts at 24.  So every gate that reaches the probe
    through `playerJumpFall` or `playerFloorTick` is structurally unable to kill it.
    The reflex here is to withdraw it as a provable equivalent, and that would have been
    wrong.  `$AE7F` is a ROUTINE, not a helper: it has its own entry, its own register
    contract (D = pixel row, E = X) and a second entry one byte later at `$AE81` that
    differs only in which mask C holds.  Driven directly over all 256 X with floor in
    the THIRD CELL ONLY, it is solid for 192 of them and follows `AND 6` at every one --
    so the case is gated, not withdrawn.
    This does not contradict *drive the routine, never the helper*.  That rule is about
    not substituting a convenient inner function for the behaviour under test.  Here the
    inner function IS a routine of the original with its own address, and the claim being
    gated is its arithmetic.  **The test is whether the thing you are driving has a
    contract in the MACHINE, not whether it is at the bottom of the call stack.**
    The order that got there: withdraw only after establishing that no entry point can
    express the difference -- and check the routine's own entry before concluding that.

182. **A POISON-AND-SWEEP ROW MUST SWEEP WHERE THE ROUTINE WRITES, AND A COMPUTED
    ADDRESS IS NOT A FIXED REGION** (Bubble Bobble, M7.34, 2026-09-25).  A new row
    proved that `extendGlyph`'s declared gap writes NOTHING -- not zeros, which is what
    the old silent fallback wrote.  It poisoned `$4000..$5800` and `$E000..$F800` with
    `$5A`, drove an off-grid index, and asserted nothing moved.  It passed, and a
    mutation that wrote ZEROS passed with it.
    The off-grid index I chose reads table bytes `00 00`, so `hl` is **0** and the eight
    writes would land at `$0000..$0700` -- outside both poisoned regions.  The sweep was
    looking somewhere the routine never wrote.
    Fixed by COMPUTING the sixteen addresses from the same table bytes the routine reads
    and asserting those.  **And it still passed**, because `$0000..$0700` is the ROM
    window, which the byte image leaves ZERO -- so writing zeros changed nothing and the
    before/after comparison was satisfied.  That is *zero writes is a measurement of the
    world, not of the routine*, a rule already in this file, applied to my own gate:
    the sixteen computed targets are now POISONED before the call.
    Two lessons, and the second is the sharper one:
    **(a)** when a routine's destination is computed from data, a fixed-region sweep can
    miss it entirely -- derive the addresses the way the routine does.
    **(b)** "nothing was written" needs the target to hold something that is NOT what a
    faulty write would put there.  Against a zeroed region, "wrote zeros" and "wrote
    nothing" are the same observation, and the gate proving the difference was the one
    thing that had to tell them apart.

183. **A CENSUS RETURNED ZERO BECAUSE I SAMPLED THE CAPTURES WITHOUT THE THING**
    (Bubble Bobble, M7.34, 2026-09-25).  I measured whether any colour-shadow cell can
    hold a low bit with bit 5 clear -- the state that makes the floor probe's wider mask
    behave differently -- and got **zero**, over ten shipped 48K captures, twice,
    independently.  I wrote it into TRAPS #180 and into a mutation withdrawal.
    The ten captures had **no live bubbles**.  The low five bits ARE a bubble index, and
    the count of low-bit cells equals the number of live bubbles, every time: `elwater`
    five bubbles five cells, `sweet` three and three, `water` three and three,
    `round1_48` zero and zero.  Driven for 300 frames, **46 of 48 in-play captures
    produce one** -- and the three that start with none produce one the frame after BLOW
    works.
    So the measurement was correct and the population was wrong.  I had asked "does this
    ever happen?" of a sample selected for not containing it, and nothing in the
    arithmetic of the answer could tell me that.
    The rule: **when a census returns zero, state what the sample was selected FOR
    before concluding the thing cannot happen.**  Concretely: name the property, then
    check whether any member of the sample exhibits its PRECONDITION -- here, a live
    bubble.  A zero over a sample that cannot contain the event is not evidence, and it
    reads exactly like evidence.
    Related but distinct: TRAPS #144 says a sweep that finds nothing must print the
    census of what WAS reachable.  This one is worse, because the census of what was
    reachable would also have been zero -- the missing step is upstream of the sweep, in
    choosing the worlds.  And #180 is the consequence: a correct measurement supporting
    a wrong conclusion about what an operation MEANS.

184. **THE SAME BITS MEAN TWO THINGS AT TWO TIMES, AND ONE OF THEM IS PAINT** (Bubble
    Bobble, M7.34, 2026-09-25).  Chasing the bubble index above, seven captures reported
    **704 low-bit cells at once** -- every cell of the 22x32 playfield, which twelve
    bubbles cannot do.  Attributed: `$8306` is the round painter's `LDIR` fill, and
    `$82F7 AND $47` keeps flash, bright and **ink**, so during a repaint every playfield
    cell carries low bits that are colour, not a bubble tag.
    In the steady state the map uses only the top three bits -- `round1_48` shows eight
    distinct values, `$00 $20 $40 $A0 $C0 $E0` and two more -- so bits 0..4 are reserved
    for the tag while a round RUNS, and only the painter puts anything else there.
    The rule: **a field can be reserved without being exclusive.**  Before reading a bit
    range as one thing, find every writer and ask when each one runs; a port that models
    the reader and runs it against a half-painted map will decode paint as data.  The
    tell here was a count that was physically impossible for the meaning I had assumed --
    704 cells for a twelve-slot pool -- which is worth watching for on its own.

185. **THE BATTERY DECODED THE SUITE WITH THE CONSOLE'S CODEPAGE, AND HAD BEEN DOING
    SO ALL ALONG** (Bubble Bobble, M7.35, 2026-09-25).  `subprocess.run(..., text=True)`
    with no `encoding` decodes with the LOCALE DEFAULT -- cp1252 on this machine -- while
    `test/bb.test.js` prints UTF-8.  The project's non-ASCII had survived by luck:
    `U+2019` is `E2 80 99` and cp1252 happens to have a character at `0x99`.  A check
    label I added contained `U+201D`, which is `E2 80 9D`, and **`0x9D` is undefined in
    cp1252** -- so every worker died in its subprocess reader thread and **"finished" in
    0.2 minutes having run nothing.**
    **The tell was the CLOCK, not the traceback.**  2,170 cases cannot be decided in
    twelve seconds.  The traceback only said where; what said *something is wrong* was a
    run that could not possibly have done the work.  And the baseline's positive-signal
    check (TRAPS #167) never got a chance, because the failure was in READING the output
    rather than in the output -- a health check can only inspect what it can decode.
    Fixed twice over: `encoding='utf-8', errors='replace'` at both call sites, so a
    stray byte degrades one character instead of killing a worker; and a WALL-CLOCK
    FLOOR on the run, which says outright that a thousand-case run finishing in seconds
    did not run.
    The general rule: **a test harness must pin its own encodings**, because the default
    is a property of the machine and not of the project -- and *fast* is a failure
    signal in anything whose job takes minutes.
    Two of my own scratch mutation harnesses had the identical bug, with the identical
    consequence: nine cases reported as SURVIVORS when the harness could not read the
    output. They now require `N/N checks passed` and raise if it is absent.

186. **A FIND-BY-LABEL EDIT MUST CONFIRM ITS MATCH IS LIVE CODE, NOT A COMMENT**
    (Bubble Bobble, M7.35, 2026-09-25).  My re-anchor helpers locate a mutation case by
    `m.find(label)` and replace the span `rindex('    (', 0, i)` .. `index('),\n', i)`.
    For a WITHDRAWN case -- commented out with `#  (` -- the label is still found, but
    `rindex('    (')` walks BACK PAST the comment into the preceding LIVE case, so the
    replacement swallows it.  **Two cases were deleted this way and the anchor checker
    could not see it: a deleted case has no anchor to be dead.**
    Caught by arithmetic: 2,149 at the previous battery, +3 restored, -2 eaten = 2,150,
    and the +1 did not match the +3 I had made.  Both were restored and identified by
    name (`M7.33: probe ONE uses $3F` and `M7.33: the probe row is not masked to a
    character row`).
    Two rules: **an edit located by text must verify the match is in the construct it
    means to edit** -- here, that the span actually starts at a live tuple; and **a
    completeness check needs a COUNT INVARIANT as well as a validity check**, because
    every per-item check in the world passes over an item that is gone.  The checker
    prints the live-case count, the distinct-label count and a per-milestone census now.

187. **THE CHEAP CHECK EXISTED ALL ALONG AND I HAD NEVER WRITTEN IT** (Bubble Bobble,
    M7.35, 2026-09-25).  The mutation battery reports dead anchors after eighteen
    minutes.  Walking the case list with `ast` and counting each anchor's occurrences in
    the engine takes **under a second**, and it reports AMBIGUOUS anchors too -- which
    the battery cannot, since it applies the first match and never knows there was a
    second.
    Written in M7.35 after the fourth increment in a row that produced dead anchors, it
    found ten candidates on its first run.  Four were its own blind spot: it did not know
    `bb.test.js` is a legitimate mutation target (cases that break the SUITE to prove a
    row can fail), and it called them dead.  **A checker that does not know its own
    domain reports its blind spot as a defect**, so it now lists the targets it knows and
    names an unrecognised one instead of failing it.
    The rule: **when a slow process reports a class of error, ask what the fast version
    of that check would cost.**  Eighteen minutes against one second, for four
    increments, is the price of not asking.

188. **TWO BITS THAT ARE SET TOGETHER IN EVERY WORLD I BUILT** (Bubble Bobble, M7.35,
    2026-09-25).  `$AEA1 BIT 1,(IY+8)` tests the jump key HELD THIS FRAME.  My gate used
    `$22` for "jump" and `$44` for "no jump", taken straight from a measured capture --
    and `$22` carries bit 1 AND bit 5.  So a mutation testing **bit 5** instead passed
    every row, and the battery found it.
    Bit 5 is the same key LAST frame.  That is why `$AD00 BIT 1 / $AD04 BIT 5` is an
    EDGE detector for starting a ground jump while `$AEA1` is a plain HELD test -- and
    the two bits only part company on the FIRST frame of a press (`$02`) and the frame
    after release (`$20`), neither of which a steady-state capture contains.
    The rule: **when two inputs are correlated in the worlds you sampled, the gate tests
    their conjunction and not either one.**  Before trusting a bit test, construct the
    world where that bit disagrees with its neighbours -- and note that a captured value
    is exactly the wrong place to look for one, because a capture is a steady state and
    the interesting frames are transitions.
    Same family as #183 (a census over a population selected for not containing the
    event) and #180 (observationally equivalent on the data I have).  Three shapes of
    one thing: the sample decided the answer and did not say so.

189. **A POISON-AND-SWEEP OVER A NUL-TERMINATED REGION CANNOT INCLUDE THE NUL** (Bubble
    Bobble, M7.36, 2026-09-25).  I added a diagnostic bound to `$802E`'s walk -- it reads
    until a NUL, so a mutation deleting the terminator test used to hang a battery worker
    for 120 seconds.  The bound sits above the measurement (32 against the longest
    string's 29) and cannot fire on the faithful path.  It fired immediately, **on the
    faithful path, in a gate of my own**: row (b) of the same increment poisons
    `$85C1..$85FB` with `$5A` to prove nothing but the RRD conversion writes inside the
    template, and two of those 59 bytes are the terminators at `$85DD` and `$85FB`.
    The rule: **a sweep that overwrites a terminator is not testing the region, it is
    constructing the failure the bound exists to name.**  Hold the terminators back and
    assert they came back zero; the claim ("nothing writes here") is about the content
    bytes, so nothing is lost.  And the general form: a new invariant can invalidate an
    OLD gate's method, not just an old behaviour -- so after adding a bound, look at
    every gate that deliberately builds illegal states.

190. **A KEYBOARD-GATED ROUTINE DRIVEN WITH NO KEYBOARD RETURNS BEFORE THE THING YOU ARE
    MEASURING** (Bubble Bobble, M7.36, 2026-09-25).  Row (c) had to show that `$7FC0`
    falls into `$7FFC` at BOTH of its call sites, and the second site is the mid-game
    join's tail jump.  The clause seeded the credit count and called `joinCheck()` -- and
    measured nothing, because `$9967` reads half-row `$F7` and **the Spectrum's keys are
    ACTIVE LOW**.  With no Keyboard attached `port($F7)` is `$FF`, so the routine returns
    at `$996F RET c`, long before `joinCommit` where `$9998 JP $7FC0` actually lives.
    The gate failed rather than passing vacuously, which is the only reason it was found.
    The rule: **for a routine gated on input, the absence of input is not a neutral
    default -- it is one specific branch, usually the early return.**  Drive it, and put
    a refusal control beside it so the positive case cannot pass for the wrong reason.

191. **AN EQUIVALENT MUTANT BY CONSTRUCTION MAKES THE HEADLINE CLAIM UNTESTABLE, AND
    MOVING ONE BYTE OF DATA FIXES IT** (Bubble Bobble, M7.36, 2026-09-25).  The
    increment's second row is titled "the second row's pointer is NOT LOADED": `$7FEC`
    sets `HL` alone and `$802E`'s own `INC IX` has carried `IX` past the NUL at `$85DD`.
    Every clause in that row -- `next === $85DE`, the template's bytes, the poison sweep
    -- passes identically whether the port writes `bannerPrint(next, $4020)` or
    `bannerPrint($85DE, $4020)`, **because `next` IS `$85DE` on the faithful path.**  The
    obvious mutation was therefore an equivalent mutant, and the row's own headline was
    the one thing it did not test.
    The fix is not a cleverer assertion, it is a different WORLD: move the terminator to
    `$85CB` and row 0 is ten characters, so `IX` lands on the `'H'` of HIGH.  A chained
    printer draws HIGH SCORE at `$4020`; one that names `$85DE` draws the score row
    whatever the template says.  Hand-mutated both ways to confirm: one named kill.
    The rule: **when two implementations agree on every world you have, the gate is
    testing their agreement, not your claim.**  Ask what data would separate them and
    seed it -- a NUL, a length, a count.  This is TRAPS #44's shape (a world that already
    holds the answer cannot show the write) applied to control flow instead of data.

192. **A BOUND TAKEN FROM THE REACHABLE MEASUREMENT WOULD HAVE FIRED ON A REAL HAZARD**
    (Bubble Bobble, M7.36, 2026-09-25).  `$C002`'s burst-sparkle walk takes **14**
    iterations on every reachable state -- 48 captures, 12 consecutive passes each, HL
    never leaving `$5CE0..$5CFA`.  A ceiling of 32, or even 256, looks generous against
    14 and is wrong, because `$C016`'s `LDI` is a **second decrementer of the same B**: a
    serviced slot with X bits `$00` makes the DJNZ wrap and the total becomes
    `(wraps+1) x <=256`, decided by whatever RAM holds above `$5CFC`.  Over 1500
    randomised tables the count came out in three regimes -- 8..13, 216..269, and
    452/502/709 -- the largest walking HL to `$6268`.  **The machine really does that.**
    A ceiling of 256 would have named a faithful hazard as a bug.
    The rule: **a diagnostic ceiling is bounded below by the worst the MACHINE can do,
    not by the best you have observed.**  The reachable number tells you the bound cannot
    fire in play; the unreachable-but-real number tells you where to put it.

193. **THE RUNAWAY WAS IN THE SHIPPED FIXTURE ALL ALONG, AS A PIXEL COUNT NOBODY DIVIDED**
    (Bubble Bobble, M7.36, 2026-09-25).  `build/sparkle_fixture.json`'s `bc` row 3 has
    reported `pix = 4256` since M7.7, against row 1's `448`, and `ptr = $603C` against
    row 1's `$5CFA`.  448 over 14 slots is 32 pixel writes a draw, so 4256 is **133 draws
    from fourteen seeded slots**, and the pointer ended 320 bytes past the end of the
    table.  Two numbers, both present, both correct, and the fact they encode -- a
    431-iteration runaway -- went unread for twenty-eight increments.
    The rule: **a fixture that records a CONSEQUENCE instead of the QUANTITY hides the
    quantity in plain sight.**  If a claim is about how many times something ran, count
    the loop top; do not infer it from a write total that needs dividing.  `tools/
    sparkle.py` now records `iters` and `ptr_out` per row, and the harness, an
    independent agent and the engine all three say 431.

194. **A MALFORMED MUTATION'S TIMEOUT WAS THE MALFORMATION** (Bubble Bobble, M7.36,
    2026-09-25).  One of the five long-standing battery TIMEOUTs was R2's "the loop runs
    255 times".  It replaced the `do {` line of `$98E2`'s banner loop with
    `while (b !== 1) {` and **left the `} while (b !== 0);` behind** -- so the mutant
    carried an ORPHANED, EMPTY-BODIED `while` that spun on `1 !== 0` for ever.  A worker
    died at 120 seconds for a parsing accident, and the behaviour the case named (255
    iterations) is exactly what the first loop already did.
    `$98E2` needs no bound at all: `B` is an eight-bit sole counter bracketed by
    `$98BC PUSH BC` / `$98E1 POP BC`, so from zero it is 256 and can be nothing else --
    confirmed on four independent captures, and 0 on round `$51`.
    The rule: **before bounding the engine, check that the mutation is well-formed.** A
    hang can be the case's own syntax.  Prefer a single-line replacement with no
    dangling tail, and prefer one whose effect is visible through a counter the gate
    already reads.

195. **A MUTATION ANCHOR THAT MATCHES NINE LINES APPLIES TO WHICHEVER ONE THE REPLACER
    FINDS FIRST** (Bubble Bobble, M7.36, 2026-09-25).  Rewriting R2 well-formed, I
    anchored on `} while (b !== 0);` and `b = (b - 1) & 0xFF;` -- which match **five** and
    **nine** do/while tails in `game.js` respectively, one of them `$C002`'s.  The cases
    would have applied, gone red, and reported a kill for a routine they never touched.
    `scratchpad/m735_anchors.py` said so in under a second.
    The rule: **"it applied" is not "it applied where I meant".**  Anchor uniqueness is a
    property to be checked, not assumed, and a one-line anchor in a file with a house
    idiom (`do {` ... `} while (b !== 0);` appears once per transliterated DJNZ) is
    almost never unique.  Carry the line above it.

196. **A TIMEOUT DISCARDS THE FAIL LINES ALREADY ON THE PIPE** (Bubble Bobble, M7.36,
    2026-09-25).  The drift painter's stride mutation prints **five FAILs** -- one of them
    the drift-field row itself -- and only then hangs, in `scrollIn`, thousands of calls
    later.  `subprocess.TimeoutExpired` carries whatever was captured before the kill and
    `parallel.py` threw it away, recording `TIMEOUT, n=0`.  So a mutation the suite HAD
    named was filed as an unnamed hang, for three increments.
    The rule: **a hang is not an absence of evidence; it is evidence plus an interruption.**
    Read the partial output.  FAILs before the hang make it a named kill
    (`TIMEOUT-KILLED`); none, and it stays a TIMEOUT, because then nothing was shown and
    saying otherwise is the crash-as-pass lie in another costume (TRAPS #107).
    A separate lesson from the same work: a diagnostic counter named `scrollSteps`
    **clobbered** the existing `$840A` execution counter of the same name, which the
    composition-trace gate caught on the first build.  New observability can collide with
    old observability; grep the name before adding it.

197. **AN LDIR FILL OVERWRITES ITS OWN SEED CELL, SO THE SEED'S VALUE MUST BE WITNESSED AT
    THE FIRST DESTINATION** (Bubble Bobble, M7.38, 2026-09-26).  `$97EB` is
    `LD HL,$4000 / LD DE,$4001 / LD BC,$1AFF / LD (HL),L / LDIR`.  To show the fill value
    comes from **L** and not from an immediate, I patched `$97EC` -- the operand of
    `LD HL,$4000` -- so HL became `$4005`, L became `$05`, and then read `$4005`.  It came
    back as my `$AA` poison, which looked like a clean refutation of a claim that is
    **true**.
    DE trails HL by L.  So after L copies the LDIR's destination *reaches the seed cell*
    and writes whatever the source now holds over it.  The seed happened, and then was
    erased, by the very loop it seeded.
    The rule: **in a copy-forward fill whose destination trails its source, the seeded byte
    is transient.**  Witness it at the FIRST DESTINATION -- `$4001`, which receives the
    seed's value on the first copy -- not at the seed.  More generally: when a probe of a
    true claim returns the poison, suspect the probe ADDRESS before the claim, and ask what
    else wrote there.  (Same family as TRAPS #182, where a poison-and-sweep swept a fixed
    region for an address computed from data.)

198. **TRAPS #191 AGAIN, ON MY OWN GATE, IN THE SESSION THAT WROTE IT** (Bubble Bobble,
    M7.38, 2026-09-26).  `titleClear()` was `ram[hl] = hl & 0xFF` with `hl` nailed to
    `$4000`.  That is byte-for-byte identical to `ram[hl] = 0` on every world a caller can
    build, so the row titled "the fill value is L, not an immediate" could not fail for the
    mutation it was written to catch, and I wrote a comment in the gate ADMITTING the
    clause only held the engine to the faithful case.  An honest admission is not a test.
    The fix is #191's: **make the data that separates them reachable.**  `$97EB`'s three
    registers became parameters with its own operands as defaults -- HL, DE and BC are
    registers the machine loads, so modelling them as inputs is *more* faithful, not less
    -- and the gate now reproduces the oracle's three PATCHED machine runs
    (`L=$00/$05/$7E`) and diffs them row for row.  `ram[hl] = 0` is now a named kill,
    confirmed by hand before the battery.
    The rule, restated because it recurred within one session: **a constant folded into a
    method makes its own transliteration untestable.**  When the machine's value comes from
    a register, let the port's value come from a parameter, and default it to the
    instruction's operand.  And when a gate comment starts explaining why a clause cannot
    discriminate, that is the moment to change the design, not to document the gap.

199. **AND #194 RECURRED TOO, IN A MUTATION I WROTE TWO INCREMENTS AFTER RECORDING IT**
    (Bubble Bobble, M7.38, 2026-09-26).  M7.38's case "the LDIR counts down by two" was
    `bc -= 2` against `titleClear`'s `while (bc)`.  **`BC` starts at `$1AFF` = 6,911, which
    is ODD**, so the sequence runs 5, 3, 1, -1, -3 and never equals zero -- and in JS a
    negative number is truthy, so the loop spins for ever.  The battery reported it as the
    run's single TIMEOUT.
    TRAPS #194's own closing note says exactly this: *"do not drop the mask -- `b` goes
    negative and never equals 0, which is a second, plausible-looking hang."*  I wrote that
    note about somebody else's loop and then made the same mutation against my own two
    increments later.
    The rule: **check the PARITY of a counter before mutating its step.**  A down-counter
    whose start is odd cannot be stepped by two, and `while (x)` in JS does not stop at
    zero-crossing the way a Z80 `DJNZ` does.  Prefer a mutation that TERMINATES and whose
    effect shows up in a number the gate already reads -- the replacement here stops DE
    advancing, which writes one cell 6,911 times and dies on the byte count in seconds.
    The general form, now three-for-three this session: **a trap recorded is not a trap
    avoided.**  #191 recurred within the session that wrote it (#198), #194 recurred two
    increments later (this one), and #192's heredoc-backslash collapse bit three times
    after being written down.  Re-reading the file is not the countermeasure; the
    countermeasure is the harness that catches it -- the anchor checker, the wall-clock
    floor, the verdict taxonomy -- and each of those earned its place the same way.

200. **A BROKEN PROBE LOOKS EXACTLY LIKE A REFUTATION, AND IT HAPPENED THREE TIMES IN TWO
    INCREMENTS** (Bubble Bobble, M7.39, 2026-09-26).  Verifying two agents' measurements I
    reported MISMATCH three times, and **all three times the claim was true and my probe
    was broken**:
    * I tested `'CP 0x5b' in dis.lower()` — the haystack lowercased, the needle not — so a
      filter instruction that is plainly there (`$F7CB  FE 5B  CP 0x5b`) read as absent.
      `CP 0x30` and `SUB 0x20` in the same check matched only by luck, having no letters in
      the operand.
    * I read `$FEC4` from `title.pkl` and expected `$00`; it is `$01` there, because
      `title.pkl` is captured *before* `$96DF` runs and it is `$96EF` that zeroes the byte,
      thirty-five bytes (fifteen instructions) before the code that reads it.  **The right question was not
      "what does the capture hold" but "what does it hold AT THE INSTRUCTION THAT READS
      IT".**
    * I counted screen bytes with more than one bit set, to show a mask slot's value
      reaching the display.  **Two dots can land in the same cell and OR together**, so
      471 multi-bit cells appear even with the slot at `$00` — the metric was confounded
      and could not distinguish any hypothesis.  The fix was to find a signal UNIQUE to the
      thing measured: slots 0..6 cover bits 7..1, so **bit 0** is producible only by slot 7
      — 0 cells with the slot `$00`, 92 with it `$01`.
    The rule, in three parts because each failure was a different mistake: **case-fold both
    sides**; **read a byte at the instruction that consumes it, not at the capture
    boundary**; and **choose a metric only the hypothesis can produce**, then show it goes
    to zero when the hypothesis is removed.
    And the meta-rule, which is why this is worth an entry rather than three silent fixes:
    **when a probe refutes a claim you have reason to believe, the probe is the more likely
    suspect.**  TRAPS #197 is the same lesson from the other side (a probe at the wrong
    address returning the poison).  Three of these in two increments means the reflex has
    to be: reproduce the claim's OWN measurement first, then diverge — if you cannot
    reproduce it, you do not yet have a refutation, you have a disagreement.

201. **"1,020 OF 1,023 STEPS AGREE" AND "256 OF 1,024 DOTS AGREE" WERE THE SAME
    MEASUREMENT, AND ONE OF THEM HID THREE QUARTERS OF A BUG** (Bubble Bobble, M7.39b,
    2026-09-26).  The starfield's ink and position come from a walk the project measured in
    M7.8 and recorded as "+51 mod 128".  It is `+51` **except after dots 255, 511 and 767,
    where it is `+53`** — `DJNZ`-not-taken plus `DEC C` plus `JR nz` is two extra M1
    fetches, so the walk advances by the iteration's M1 count and each rollover costs `+2`.
    The census comment described that as "confirmed for 1,020 of the 1,023 steps", which
    sounds like a rounding error.  Diffed **row for row against the output** instead, the
    same fact reads: **the port's model is right for 256 of 1,024 dots and wrong for the
    other 768.**
    The rule: **for an ACCUMULATOR, never report agreement per step — report it per
    output.**  A phase error never heals; three wrong increments out of a thousand corrupt
    everything after the first one.  "1,020 of 1,023" and "256 of 1,024" differ by the
    whole result, and only the second is the number a port cares about.
    Two more things from the same increment, both mine, both of the same family — **an
    inference from a correct measurement, not stated as an inference:**
    * I wrote "one eighth of 1,024, so **128** dots draw nothing", which assumes the slot
      index is uniform.  It is `prng & 7` over a *specific* sequence: measured **125** with
      the port's own seed.  A ratio is not a count.
    * I wrote "draw nothing", having measured only that the mask is `$00`.  `$FE95` ends in
      `LD (HL),C` — a **STORE**, not an OR — so such a dot *clears the byte it lands on*.
      What a zero mask does depends on the instruction that applies it.
    And the discriminator I built on it was invalid anyway: `reset()` puts `$14` in
    `$FEC4`, which has **no bit 0**, so the bit-0 count is zero for both `$00` and `$14`.
    The pair that discriminates is **lit bytes, 820 vs 940**.  Check that a discriminator
    separates the two worlds you will actually build, not the two you happened to test.

202. **A HAND-COPIED DUPLICATE OF A GENERATED TABLE, WHOSE OWN HEADER IS ALREADY STALE**
    (Bubble Bobble, M7.39b, 2026-09-26).  `BB_BANNER_FONT` in `web/game.js` is a hand
    transcription of `tools/make_banner.py`'s `GLYPHS`.  Its header comment says "these
    **fifteen** cells" and "**67 of 112** bytes" — against the fixture's **32** rows and
    **160 of 248**.  It went stale silently, some increments ago, while every gate stayed
    green: the gates compare `game.js`'s literal against `build/bannerfont.json`, so the
    two *data* copies are checked against each other and **the prose describing them is
    checked by nothing**.
    This is the project's own "two spellings of one rule" trap (the M7.11 drift duplicates,
    M7.17's three spellings of `$927D`) in its cheapest disguise — the duplication is not
    of code but of a COUNT, in a comment.
    The rule: **a number in a comment that describes generated data must either be
    interpolated from that data or asserted against it.**  If a count appears in prose and
    nothing reads it, it is not documentation, it is a claim with no test — and extending
    the font is now a four-file change (`make_banner.py`'s `GLYPHS` *and* its
    `STRINGS`/`EXTRA` together, or its `not spare` assert fires; `build/bannerfont.json`;
    `web/game.js`'s literal; and the header prose) precisely because that number was never
    wired to anything.

203. **A MUTATION THAT DOES NOT EXPRESS THE BUG IT NAMES IS AN EQUIVALENT MUTANT WITH A
    MISLEADING LABEL** (Bubble Bobble, M7.40, 2026-09-26).  `rowTableBlock` models `$9673`'s
    eight-bit `ADD A,L`, and I wrote a case labelled "the add carries into H -- sixteen-bit":
    `l = (l + 0x20) & 0xFF` -> `l = l + 0x20`.  It carries into NOTHING.  `ram` is a
    `Uint8Array`, so storing `$100` silently keeps `$00`, and `h` is a separate variable the
    add never touches -- so in JS, dropping the mask is *itself* an equivalent mutant.  Hand-
    testing it before the battery gave **0 FAILs**; the battery would have reported a
    SURVIVOR and blamed the row, which is correct.
    The real porting mistake is a sixteen-bit HL add whose carry reaches H.  Written that way
    the case dies on row (f) alone -- the one row that drives `L = $20` -- because on the
    machine's own four inputs (all `L = $00`) the two adds agree.
    The rule: **model the MISTAKE, not a syntactic perturbation of the line.**  Ask what a
    porter would actually get wrong, and check the mutation reaches the observable output
    through the language's own semantics -- typed arrays mask, `const` hides, a separate
    variable does not carry.  And **hand-test the sharpest cases before the battery**: five
    minutes found this; the battery would have spent seventeen to report it as the wrong kind
    of failure.

204. **A PROBE THAT BORROWS ITS PRECONDITION FROM MEMORY THE PORT HAS NOT MODELLED YET WILL
    SILENTLY CHANGE BRANCH WHEN IT IS** (Bubble Bobble, M7.40, 2026-09-26).  The extendGlyph
    gap-path row probes an off-grid `iy = $95F4` to exercise the counted fallback, which fires
    only for a ROM glyph source -- `ram[iy+2..iy+3] < $4000`.  Those two bytes sit inside
    `$95F3..$9602`, the cold start's SELF-OVERWRITE target.  The port had left them zero, a
    ROM address, so the probe hit the gap path **by accident**.  Increment G modelled `$9603`'s
    LDIR, the bytes became round 15's spawn record -- `$21 $88`, a RAM source -- and
    extendGlyph correctly took the faithful `ram[de]` path instead.  The row went red only
    because it asserted `extMissing + 1` specifically; a looser row would have gone on passing
    while testing a different branch.
    The rule: **a row that depends on a memory precondition must CONSTRUCT it and ASSERT it**,
    not inherit it.  Every byte the port does not yet model is a byte some later increment
    will change, and a probe resting on one is testing the port's ignorance.

205. **A RUNTIME PRODUCT SHIPPED AS DATA -- TWICE MORE, AND ONE OF THEM HID ITS OWN WRITER**
    (Bubble Bobble, M7.40, 2026-09-26).  Two port tables turned out to be values the machine
    COMPUTES, measured from captures taken after the computation and shipped as constants:
    * `BB_ROWTAB`, commented "static tape data ... rather than recomputing the ULA formula",
      was measured from `build/image.bin`, a POST-BOOT image.  `$9662` BUILDS it at every cold
      start -- 64 words, of which the port held 24 and derived another 22 by a second spelling
      of `$9662`'s own `ADD A,$A0`.
    * HUD row 1, `'      00   000200000       00'`, was measured from `round1_48` AFTER `$7FC0`
      had converted the 20,000 record.  The tape, boot, title and afterctrl48 all hold
      `'      00     1000000       00'`.  Seeded post-conversion, every digit row passed with
      `hudScoreDigits` DELETED, because the template already held the answer (TRAPS #44).
    And a third case shows why a writer census cannot settle "is this static?": `$9AE7` is
    written by `$95F8` -- and `$95F8` lies inside `$95F3..$9602`, which `$9603` overwrites a
    few instructions later.  **The writer destroys itself**, so a byte-grep of any in-play
    capture finds no writer at all.
    The rule: **before calling a table static, find what writes it -- and if nothing does,
    ask whether the writer overwrote itself or ran before the capture.**  "The load image is
    not the run image" (TRAPS #43/#47) is the same trap entered from the data side.

206. **A CORRECT MEASUREMENT AND THE DESIGN IT SEEMED TO DEMAND ARE DIFFERENT CLAIMS, AND I
    MERGED THEM IN A DOC** (Bubble Bobble, M7.40, 2026-09-26).  An agent measured that a
    second entry to `$95F3` re-runs the whole init and eats a stack word.  True.  I wrote into
    `docs/M7.37-FRONTEND-READING.md`: *"So `coldStart()` must refuse a second call"* -- and a
    pre-mortem agent showed that the suite calls `reset()` **77 times on one object**, so a
    throwing guard would fire at line 36, before ~1,243 checks ran, and turn the whole file
    into a stack trace.  ~~Worse, refusing is LESS faithful than the alternative: re-running
    everything IS what the measurement says a second entry does.~~  *(Struck: that sentence
    is itself an instance of this entry's trap -- see #207.)*
    The rule: **a measurement tells you what the machine does; it does not tell you what the
    port must forbid.**  Before adding a runtime guard, count the legitimate callers, and ask
    whether the faithful response to the measured behaviour is to reproduce it rather than
    prevent it.  The boundary that matters -- production never cold-starts twice per load --
    became a gate, which is where a boundary belongs (house rule 5).

207. **I REPEATED #206'S TRAP INSIDE #206'S OWN CORRECTION** (Bubble Bobble, M7.40,
    2026-09-26).  #206 records that I merged a measurement ("a second entry re-runs the whole
    init") with a design it seemed to demand ("so `coldStart()` must refuse a second call").
    In correcting that, I wrote "re-applying on every call IS the faithful behaviour -- it is
    precisely what the measurement shows a second entry does" -- into the engine, the gate, the
    SPEC and #206 itself.  The pre-commit critic DROVE a real second entry: it skips
    `$95F5`/`$95F8` and `$9601`, so `$9AE7` is not rewritten and no key copy happens; its
    self-overwrite becomes 26 bytes through `$960C` and destroys its own LDIR, because
    `BC = hi(ret)*256 + $10`; its `CP $80` reads the `A'` the first run left; and interrupts
    stay live until `$967E`.  It re-applies the patches, `$FFE3` and the relocation -- which is
    why "re-runs the whole init" FELT true -- and nothing else about it matches.
    The design survived; the justification did not.  Re-applying is right because **every
    production call is a first entry**, not because it models a second one.
    The rule: **a correction is a new claim and needs the same evidence as the one it
    replaces.**  I corrected #206 by argument, from the same partial measurement that had
    misled me the first time, and the only thing that settled it was driving the case.  When
    a claim of the form "X IS what the machine does" appears, it is a measurement claim, and it
    is either driven or it is struck.

208. **A GATE ON THE STAGES CANNOT SEE THE ORDER OF THE WHOLE** (Bubble Bobble, M7.41,
    2026-09-27).  `titlePaint()` is four stages; the row asserting the machine's ordered
    attribute stores drove them ONE BY ONE, in the right order, from the test.  So "the credit
    line prints before the title text" survived the hand-test: the two touch disjoint cells,
    the end state is identical, and the only witness -- the order of the stores -- was
    supplied by the row itself.  **Log through the composite, not around it.**  The fix
    wraps `titlePaint()` in the write proxy and drops the CLS and starfield prefix by count.

209. **A STATE THAT IS "ARMED ONCE" BECOMES A CONSTANT OVER A SESSION** (M7.41).  The class-B
    walk armed only when `!walkArmed`, which only `reset()` clears.  With the new stalls a whole
    starfield advances the walk by exactly +8 (1,024 x 51 + 8 = 0 + 8 mod 128), so every title
    screen after the first in one session would have drawn the SAME ink sequence -- on a
    machine where every title is a different starfield.  The pre-mortem found it by asking
    what the SECOND call sees.  And the first gate row for the fix only excluded "+8"; a reuse
    with any other drift passed until the row pinned the fresh arm's own value (snapshot,
    arm, restore, compare).  **Assert the value the right mechanism produces, not the absence
    of one wrong one.**

210. **AN ORACLE WITH INTERRUPTS OFF SILENTLY DECLARES NOTHING** (M7.41).  The title paint
    runs after `$970E EI`.  Every leg of the first oracle ran interrupts off -- correct for
    exactness, and the rows were right -- but the port's missing in-loop ISR bumps were then
    a departure nobody had declared, because nothing measured the path the machine takes.
    The review drove it: 5-6 ISRs, R steps of 103/104/106, every dot moved, and the PRNG-only
    projection identical over sixteen frame phases.  **When the oracle turns interrupts off,
    it must also drive them on and say what survives** -- that is where the departure's
    boundary is.

211. **A FAKED PRECONDITION HIDES AN ORDERING** (Bubble Bobble, M7.42, 2026-09-27).  Every row
    that drove a game over did it by clearing bit 7 of the two in-play bytes -- lives stayed at
    three.  So `titleLeave()` running the round advance BEFORE `playersInit()` passed the whole
    suite: the fields the players are stood up with already held the values.  A real game over
    leaves them ZERO, and then the first pass differs in 39 bytes.  **When a row builds a
    precondition by shortcut, ask which state the shortcut leaves that the real path does not**
    -- the review's row zeroes the twelve fields and spies the order.

212. **A PROBE THAT READS AFTER THE FRAME SEES THE FRAME'S WRITES** (M7.42).  The state "at the
    first main-loop pass" was read after the step that ran it: `$FEC5` came back 1 against the
    machine's `$2A`, and it looked like a divergence in the round advance.  `elemArm` had written
    it DURING that pass.  Snapshotting at the ENTRY of the first `mainLoop()` gives `$2A`, as on
    the machine.  TRAPS #200 again, in a new shape: **name the instant a measurement is taken
    and take the port's at the same instant.**

213. **WIRING A ROUTINE EXPOSES WHAT IT READS** (M7.42).  Two bugs older than the front end
    became reachable the moment the page could start a game: player 2 was INVISIBLE (the
    entity-sprite asset stopped at `$D8FF` and the player bank runs to `$DFFF`), and the round
    advance's T accounting drains three frames long (RA1..RA4, closed M7.43).  Neither was new; the old
    `gameStart()` path discarded the spends and no page could reach two players.  **A new
    path through old code is a measurement of the old code** -- review it as one.

214. **I CALLED AN AGENT'S RESULT VOID WITHOUT CHECKING, AND I WAS WRONG** (Bubble Bobble, M7.43,
    2026-09-27).  The design agent's mutation runner wrote each mutant into `web/game.js` and ran
    `node test/bb.test.js` with no build step, and I concluded its "17 of 17 killed" had tested the
    pristine page -- and wrote that into the battery file and a reviewer's brief.  The suite
    rebuilds the page ITSELF (`execFileSync('python', [.. 'tools/build.py' ..])`, line 19); a
    reviewer said so, and a one-line grep confirmed it.  The result was valid.  TRAPS #200 from
    the other side: **a claim that a measurement is broken is itself a measurement claim** -- it
    needs the same one-line check before it is written down, and "the runner does not do X" is
    checked by reading what the runner calls, not by reading the runner alone.

215. **A TABLE MEASURED FROM A SWEEP CANNOT BE GATED BY THE SAME SWEEP** (M7.43).  RA3's
    per-(players, round) build and tail costs are the means of the $FECD sweep's own advances,
    so the in-play row that replays that sweep is exact by construction on the table -- it tests
    the phases and the charges, not the fit.  The review drove fourteen HELD-OUT advances on
    other worlds: twelve exact, two one ISR short.  **Say which rows are in-sample, and keep a
    held-out number somewhere a reader will find it**, even when it cannot be a row.

216. **TWO OF MY OWN NEW ROWS FAILED ON THE CORRECT ENGINE -- AND IT WAS THE ROWS** (Bubble Bobble,
    M7.44, 2026-09-27).  "An inactive player is not read" compared P2's whole slot and found X
    changed -- by the per-slot tail that clamps every slot's X to `$10`, key or no key.  "The
    settle probe" required two live armed windows; there is one.  Both were written from the
    reviewer's description, not from the world.  TRAPS #200 again: **a new row that fails on an
    engine the machine already agrees with is a claim about the row first** -- narrow it to
    what the mechanism under test writes, and count from the fixture, not from the prose.

217. **A LATENT BUG IN A ROUTINE NOBODY REACHES IS STILL A BUG -- AND ITS COMMENT MUST SAY SO**
    (Bubble Bobble, M7.45, 2026-09-27).  `bubbleTouchPop` ORed a constant `$10` where the machine
    reads the operand `$B9BC` that `$B901` writes per player.  While the award tail was unwired no
    pop paid anyone, so no row could see it; the moment the pop was wired, every one-player kill
    would have paid player 2.  The builder's comment first described it as a bug players had
    seen ("every touch-pop paid P2"); the review corrected it to LATENT.  **Wiring a routine turns
    its latent constants into live ones** (TRAPS #213) -- and a claim about what players saw is a
    measurement claim like any other.

218. **TWO CALLS SHARE THE REGISTERS, AND A TRANSLITERATION THAT GIVES EACH ITS OWN LOCALS IS A
    SECOND MACHINE** (Bubble Bobble, M7.47, 2026-09-27).  `$B8EA/$B8ED` load the bubble's X/Y into
    C/B ONCE and then call the touch test for P1 and for P2.  P1's call overwrites them (the push's
    `LD C,A`, `$ADAA`'s exit BC -- `$F800` when a step crosses a cell), so P2's test sees what P1
    left.  The port passed each call the bubble's X/Y afresh; the difference is P2 popping a bubble
    the machine does not, at Y 16..17.  And the bounce ends `POP AF / LD (IY+8),A` where the POP
    pops a PUSH HL, so A is `$FD`, not a restored flag -- a later bubble in the same pass reads it
    as "pressing".  **When one routine is called twice from one site, trace what the FIRST call
    leaves in every register the second call reads** -- a JS parameter list is a claim that it
    leaves nothing.

219. **"SURVIVED EVERY SCENE" IS NOT "EQUIVALENT" -- #191 AGAIN, AND THE DECLARATION WAS ALREADY
    WRITTEN** (Bubble Bobble, M7.48, 2026-09-27).  The interleave's mutant "the player's `$AB0C`
    tail runs BEFORE his move" survived all fourteen differential scenes and the whole suite, and
    the handoff note said "EQUIVALENT -- declare it".  The tail only evens and clamps X, and in
    play X is always even, so the claim looked safe.  It is false: the right step's crossing test
    reads `(X+15) & $F8` against `(X+17) & $F8`, so from an ODD X one step from the wall the step
    crosses and is blocked, and from the evened X it does not.  One staged scene (I8, X = `$DF`)
    kills it on its first row.  **An equivalence is a claim about every input the code can see,
    and "the scenes we have agree" is a claim about the scenes.**  Before declaring one, read the
    code the two orders feed and find the branch that could tell them apart -- #191's rule, and it
    was written down seven increments ago.

220. **A ROUTINE TRANSLITERATED BEFORE ITS CALLER GETS CALLED FROM THE WRONG PLACE, AND THEN THE
    CALLER IS BUILT AROUND IT** (Bubble Bobble, M7.48).  The player physics was ported in M7.4 as
    `updatePlayers()`, long before the entity pass `$AA60` existed in the port; when the pass came
    (M7.6-ii) it was built for the enemies and the players stayed a separate call after it.  On the
    machine they are two entries of the pass's own handler list (`$AB38, $AB38`), so the pass's
    order (enemies read the post-move X), its doubling (the fast walk) and its per-slot tail all
    applied to them -- and none did in the port, from M7.6-ii to M7.48, while every gate on each
    half passed.  **When the machine reaches a routine through a table, the port must reach it
    through the same table**; a hard-wired call beside the dispatcher is a second dispatcher with
    its own order.  And moving the call is not the end of it: the routine still carries its OLD
    caller's assumptions.  `updatePlayer` had an activity guard written for `updatePlayers()`, which
    called it for both slots blindly; `$AB38` has none, and inside the pass the guard became a
    second gate that the doubled run after a fast-walker's final death reaches (I9 -- the first
    battery's one survivor).  And a byte in the code can be state: `$90D0` is an OPCODE the
    respawn flips between SET and RES, so the same walk angers or calms.

221. **A PIN ON A VALUE THAT A CLAMP ALREADY FORCES CANNOT FAIL** (Bubble Bobble, M7.48).  The
    review found a fast walker's two blow clicks stamped at one instant where the machine spaces
    them ~2,000 T, and I declared it -- "nothing is charged inside the `$AA60` walk" -- and pinned
    it as a boundary: the engine's pair must be coincident.  The mutant that SPACES them survived.
    The pin was true for a different reason: the port runs the ISR at the frame's end, so every
    click is past the frame and M7.44's clamp holds it at the frame's last T -- 105 of 105 clicks
    measured -- and any spacing below the clamp vanishes.  The clause was dropped, the mutant
    listed as equivalent, and the comment now names the clamp.  **Before pinning a declared value,
    mutate the value and watch the pin fail** -- a boundary asserted downstream of a saturating
    operation asserts the saturation.

222. **A SELF-MODIFIED OPERAND THAT SEVERAL CALLERS SHARE IS STATE, NOT A LOCAL -- AND A BYTE LEFT OUT OF
    THE VECTOR BECAUSE IT "DIFFERS EVERYWHERE" IS A GATE SWITCHED OFF** (Bubble Bobble, M7.49,
    2026-09-27).  The port held `$A431`, `$A430`'s own addend, in a JS local seeded `$B9` and stored it
    at the end of the draw pass -- a faithful model of the PASS.  But `$A447` makes its own `$A430`
    calls wherever it is entered, and it is entered from `$BF16`, `$BE92`, `$91D6` and `$8C51` too: 2,252
    adds over the pop-kill scenes landed on a byte the port had already finished with.  Nothing
    on the display changed (every pass re-seeds before any band reads it), so no display differential
    could fail; the byte was the only witness -- and in M7.48 it was LEFT OUT of the compared vector
    because it "differed on every scene, unexplained".  It stayed an open item, which is the only thing
    that made it a finding rather than a blind spot.  **An operand is shared state the moment a second
    caller reaches it; model it where it lives.  And a byte excluded from a differential because it
    disagrees is the one byte that differential most needs.**  H12's "the band persists across frames"
    was the same shape in a measurement: read from direct `$A430` calls, it described the calls.

223. **A STUB IN THE MAIN LOOP IS INVISIBLE TO EVERY PER-ISR GATE -- AND THE NATURAL SCENE THAT
    "COVERS" IT CAN BE A NO-OP** (Bubble Bobble, M7.50, 2026-09-28).  `$8EC9 CALL $90A9`, the
    one-left anger, was `roundOneLeft(){ }` from M7.7-b to M7.50, and wiring it changed NOTHING in
    the 1,420-check suite: the pop-kill gate replays ISRs from the machine's own pre-state and never
    runs the main loop, and the level-clear gate held the one-left rows out and counted them.  The
    recon then found the natural scene that reaches it, N1, is a no-op too -- its "last enemy" is a
    flying CORPSE, so the walk changes no table byte (TRAPS #183's shape).  **Know which loop a gate
    runs and what it samples.  A routine called from the main loop needs a main-loop differential,
    and the scene that
    drives it has to be one where the call DOES something** -- here a live survivor (L1), whose X
    steps double.

224. **THE HARNESS NEVER SEES A ROM WRITE, SO A COUNT OF THEM IS ALWAYS ZERO** (Bubble Bobble, M7.51,
    2026-09-28).  `$A447`'s erase walks sixteen rows through the `$FD00` table, and a cached Y near the
    top or bottom sends some rows to addresses below `$4000` -- ROM, where the write is dropped.  The
    M7.51 oracle counted them with the harness's write watch and got ZERO on every row: SkoolKit's
    simulator discards a ROM write before the memory object is asked, so the watch never fires.  The
    right count came from the row table itself (a cached Y of `$BF` lands one row in RAM, three
    writes; `$08` sixteen; `$0B` thirty-three).  **A probe can only count what its hook is shown: before
    trusting a zero, make the event happen on purpose and watch the probe see it** (TRAPS #200's rule,
    applied to the harness itself).

225. **TWO EDGES AT ONE INSTANT ARE A PULSE NOBODY HEARS -- AND A GATE THAT ONLY FORBIDS TIME GOING
    BACKWARDS PASSES IT** (Bubble Bobble, M7.52, 2026-09-28).  M7.19 laid the HURRY UP! train's seven
    edges on a flat step and put each flash's LOW (`$906F`) and the HIGH after it (`$908F`) at the
    SAME T.  Its gate checked seven edges, alternating levels and `t[i] >= t[i-1]` -- all true -- and
    the train was silent: the bridge renders each sample as the exact mean of the square over the
    sample's interval (a box integral), so a zero-width LOW contributes nothing.  The machine's LOWs
    are 13,972 T wide (0.2 frame).  **Gate an edge train's WIDTHS against the machine's, not only its
    count, order and levels -- a `>=` where the machine has a gap is the bug's own shape.**

226. **A CENSUS BY SITE SAYS EVERY EMITTER IS BUILT; ONLY A CENSUS BY CALLER SAYS EVERY PATH TO IT
    RUNS** (Bubble Bobble, M7.52, 2026-09-28).  SFX1 named every `OUT ($FE)` in the game's code and
    mapped each to the port method that makes it -- nineteen of nineteen, "every in-play OUT
    accounted for".  The review walked the CALLERS: `$A116 CALL $A0E0` (the umbrella's five flashes)
    and `$894B CALL $8C14` (the level-skip's treasure arm, which falls into `$8C28` and its `$8C4E
    OUT 0`) reach two of those sites on paths the port never runs.  The site is built; the sound is
    not made.  **When a census claims completeness, say what it enumerated -- sites, callers or
    paths -- and list the callers of every shared site before claiming the paths** (SFX1 now names
    both, `NOT_PORTED_CALLERS`).

227. **"OVERWRITTEN BEFORE ANYTHING READS IT" IS A CLAIM ABOUT READS -- A WRITE CENSUS CANNOT MAKE IT,
    AND "DEAD" IS A DIFFERENTIAL** (Bubble Bobble, M7.53, 2026-09-28).  The control-select screen writes
    16 ROM system-variable bytes and 20 stack bytes the port does not model, and the gate said why:
    `$96A5`'s relocation "overwrites them before anything reads them".  The oracle had a WRITE census
    and nothing else.  A read watch from `$F664` to the relocation found 13 of the 36 READ first --
    FLAGS by the ROM's keyboard scan, ten more by player 2's ROM print, and a return address by the
    game's own RET.  The decision survived on a different measurement: no GAME PC reads any of the 16,
    and putting boot's values back at `$F664` changes nothing through `$96B0` -- with a positive control
    (P-FLAG poisoned changes 256 bytes of player 2's screen), so the differential can fail.  The same
    "before anything reads them" had been retracted once already, in the M7.7 FGH reading.  **A claim
    that nothing reads a byte needs a read watch; a claim that its value does not matter needs an
    un-write differential and a control that proves the differential can see a change.**

228. **AN EXPLICIT `RST $38` RUNS THE ROM'S WHOLE INTERRUPT ROUTINE -- ITS EI INCLUDED** (Bubble Bobble,
    M7.53, 2026-09-28).  The front-end reading reasoned that because `$F7B3` calls the ROM's interrupt
    body itself to scan the keyboard, "the whole menu runs with the ISR suppressed and IFF=0" -- and
    M7.52's sound table repeated it for the key click.  A routine called for its side effect carries all
    of its effects: this one ends by re-enabling interrupts, so from the first key read the menu runs
    with IFF 1 (98.7% of 377,800 steps; 50 frame interrupts accepted in 50 frames alongside 3,550
    explicit calls), player 2's paint takes 5-6 interrupts, and an interrupt can land inside the key
    click (2 of 8 phases, +1,205 T).  **Measure IFF across the loop; never infer it from which routine
    is called.**

229. **A GLYPH CHECKED AGAINST ITS OWN ROM CELL CAN STILL BE A ROM CELL -- MOVED ONE ROW; AND A PATCH
    CANNOT DELETE A QUOTE WITHOUT CARRYING IT** (Bubble Bobble, M7.53, 2026-09-28).  The substitute
    font's rule -- every inked glyph differs from the ROM cell it replaces in at least 3 of 8 bytes --
    passed a 'P' that was, byte for byte, an eight-byte window of the ROM (the ROM's lowercase 'p'
    moved one row), from M7.20 until the M7.53 review; the new 'K' and '.' sat 2 bytes from their own
    cells moved a row.  make_banner.py now refuses a glyph equal to ANY eight-byte ROM window, and one
    within 3 bytes of its own cell moved -2..+2 rows.  The same sweep found twelve more quotes of ROM
    bytes in comments, docs and a fixture, and a fixture holding nine ROM glyph cells because its oracle
    recorded eight bytes at every pointer, ROM or not.  (a) Scan the whole tree against every ROM
    window, not each glyph against its own cell; (b) an oracle that records the bytes at a pointer must
    refuse a pointer below `$4000`; (c) a forbidden quote is removed by PATTERN in place -- a patch that
    deletes it carries it on its `-` side -- and the history still holds what the tree no longer does.

230. **A RUN-AHEAD IS SAFE ONLY WHILE ITS INPUTS ARE FROZEN -- AND THE LAST INTERRUPT OF THE BLOCK
    WAS NOT** (Bubble Bobble, M7.54, 2026-09-28).  The HURRY UP! block runs ahead of the machine's
    frames and holds each write until its frame, on a measured premise: the interrupts inside it
    write two counters and their stack, which the block never reads.  True for the 42 with both
    gates shut -- and false for the 43rd, which lands after `$90A3`/`$90A6` reopen them and runs the
    bubble manager between the temper walk's read and its write.  Values computed ahead undid its
    captures and releases.  The fix holds a read-modify-write as the OPERATION, applied to the byte
    when it lands, with its read stamp.  **A premise measured over the block's middle has to be
    re-measured at both ends, where the state that made it true is being set up and torn down.**

231. **A FILE NAMED BY ITS CONTENT CAN STILL BE ONE THAT EXISTS -- AND THE TOOL THAT WROTE IT SAID SO**
    (Bubble Bobble, M7.56, 2026-09-28).  The round banner's timing oracle was written as
    `tools/roundbanner.py` -- a good name by the rule that agents' scratch dirs are named by content --
    and it replaced M7.28's committed `roundbanner.py`, the oracle of what the banner draws; its first
    capture then overwrote `build/roundbanner_fixture.json`, which the suite reads.  The Write tool had
    reported "updated", not "created".  Both came back from git (the tree was clean), and the new oracle
    is `tools/bannertime.py`.  **Before creating a tool or a fixture, list the directory for the name --
    and read the verb the tool reports.**  A content name is chosen to be unique among the new; it is
    not checked against the old.

232. **A SCRIPT WITHOUT AN ARGUMENT PARSER DOES NOT ANSWER `--help`: IT RUNS** (Bubble Bobble, M7.56,
    2026-09-28).  `scratchpad/battery/parallel.py --help` fell through to a FULL battery at the default
    eight jobs; it took the lock and ran ten minutes before it was seen and killed, and its stale lock
    had to be removed by hand (the lock did its job: the next run refused to start).  **Read a script's
    argument handling before calling it with a flag it may not have.**

233. **`sed -i` IN GIT BASH REWRITES A CRLF FILE AS LF -- ALL OF IT** (Bubble Bobble, M7.57,
    2026-09-29).  A one-line quote fix with `sed -i` on `test/bb.test.js` turned every one of its
    29,669 CRLF line endings into LF; the suite still passed.  Caught only by counting `\r\n` against
    `\n` after the edit.  **Edit a CRLF file with a script that reads bytes and writes `\r\n` back, and
    count the endings after any shell edit.**  (The same session hit TRAPS #192 twice more: a heredoc ate
    the backslashes of `\'extend\'` and of a Python path.)

234. **A REGISTER READ AT ONE WORLD IS NOT A CONSTANT** (Bubble Bobble, M7.25 -> M7.57, 2026-09-29).
    M7.25 read `$955E`'s busy-wait counts "out of the REGISTERS, not guessed" -- (45, 4) on extcomp -- and
    shipped them as `BB_EXTCOMP.DELAY2_A/B`.  They are what `$806C` leaves behind: `$8095`'s walk opcode
    and player one's ink with player two out of play, `($5AC0)` and 5 with player two in it.  A
    two-player EXTEND ran 124,000 T long in the port.  **A value read out of the machine's registers is
    a measurement of that world; the code that left it there is the model.**

235. **(IX+d) IS WHATEVER THE LAST CALLEE LEFT IN IX** (Bubble Bobble, M7.25 -> M7.57, 2026-09-29).
    `$9561`'s spin `DEC (IX+$63)` was transliterated as the player's letters byte because `$9556 POP IX`
    restores the player -- but `$955B CALL $806C` runs between them and leaves IX at `$85B9`, so the
    machine decrements `$861C`, the byte before the ink table, 256 times.  Both readings start and end
    at zero, so every end-state gate agreed for thirty-two increments; only the per-write T stream of
    M7.57's oracle told them apart.  **After a CALL an index register is the callee's until proven
    otherwise, and a gate on the end state cannot see a byte that ends where it began.**

236. **"ALREADY MODELLED" IS A CLAIM, NOT A MEASUREMENT** (Bubble Bobble, M7.57, 2026-09-29).
    `itemEntry`'s note said `$8719`'s two weather skips were "already modelled in itemInkDraw"; nothing
    there read `$FECE` or `$FECF`, so under a flood or a storm every item got an ink the machine never
    gives it.  Found only because the timing mirror had to account for the flood's 574 T.  **A comment
    that says something is handled elsewhere is a pointer to go and check.**

237. **TWO NATURAL RUNS 11,000 T APART MAY BE TWO WORLDS, NOT TWO PHASES** (Bubble Bobble, M7.57,
    2026-09-29).  Free natural completions at one entry phase ran 11K T shorter than the forced run at
    the same phase: the lead frames had moved the PRNG, and four more empty records shortened the item
    passes.  Seeded from each run's own entry state, the model took both exactly.  And sixteen free
    leads gave only FOUR entry phases -- a pass reaches `$948F` at much the same point of every frame --
    so the phase sweep had to be forced at the entry.  **Before blaming timing, seed the port from each
    run's own state; and a lead in frames samples the pass, not the phase.**

238. **MISSING INTERRUPTS ARE A DI WINDOW BEFORE THEY ARE A SIMULATOR FAULT** (Bubble Bobble, M7.57,
    2026-09-29).  The natural completions took 244 interrupts in 247.3 frames of wall time, and my first
    reading was the harness: a fast LDIR swallowing the interrupt windows.  SkoolKit's CMIOSimulator
    forces fast_ldir and fast_djnz OFF; the gap sat exactly over `$8C14`'s DI and `$8C4C`'s EI -- which
    TIMING.md item 10 had DECLARED since M7.52 ("the machine loses about three frame interrupts inside
    it; the port loses none").  **Count the interrupts against the wall time, and look for a DI before
    suspecting the tool; a declared gap is where to look first.**  (The port now loses them: `intLost`.)

239. **THE MACHINE'S SIDE OF A COMPARISON MUST NOT BE THE CONSTANT UNDER TEST** (Bubble Bobble, M7.57,
    2026-09-29).  Five of the eleven battery survivors: E10 compared the OUT's T with `hook + W.OUT` on
    both sides, and E11 built the DI edges from `W.INT_T` and `W.DI_ENTRY` -- so mutating a constant
    moved the expectation with it.  The rows now take the machine's side from the fixture (the
    prologue's stores at 31 and 129) or from the Z80 (DI 4 T, EI + XOR A 8, INT 32).  **A row that reads
    the engine's constant to build its expectation tests nothing about that constant.**

240. **`>= 1` ON A COUNTER TWO MECHANISMS FEED LETS EITHER ONE BE DELETED** (Bubble Bobble, M7.57,
    2026-09-29).  A write past its routine's model is counted twice -- by the write and by the
    routine's close -- and E12 asserted `extOff >= 1`, so the battery deleted each count in turn and
    the row stayed green.  **Assert the exact count, and give each mechanism a case only it can see**
    (a routine SHORT of its model is counted by the close alone).

241. **"THE INTERRUPT READS A BYTE THE BLOCK WRITES" IS NOT THE HAZARD -- THE ORDER IS** (Bubble
    Bobble, M7.58, 2026-09-29).  The storm oracle's first premise clause flagged four strike runs: the
    bubble manager reads the payload's twelve pool flags.  But the payload stores them inside its own
    DI..EI, BEFORE every interrupt of the tick, and the port's call lands them first too -- the same
    order.  The hazard for a write the port lands at the call is an interrupt that reads the byte
    BEFORE the machine's main line writes it.  **State a premise as an order of events (first read
    against last write), not as a set intersection** -- the intersection fails runs that are right,
    and a clause that cries wolf gets loosened until it hides the run that is wrong.

242. **A PART-PAINTED SCREEN IS NOT A LANDING TIME** (Bubble Bobble, M7.58, 2026-09-29).  ST4 first
    checked that a frame boundary inside the flash showed a part-painted attribute file and that the
    tick ended fully painted.  The battery moved the stamps' origin to the frame's start -- every store
    ~50K T early -- and the screen was still part-painted at a boundary, so the row stayed green; so did
    a resume that skipped the entry after `$A09A`, and a parked pass charged `BB_PASS_T`.  The row now
    counts the stores landed at each frame's end against the fixture's own stamps and each frame's
    interrupt point, names the entry that comes next, and checks the carry.  **A qualitative "it is
    visible" check cannot see a mis-timing that is still visible; pin the count per boundary.**

243. **AN EQUIVALENT MUTANT PROVED BY ALGEBRA IS STILL CODE THAT CAN BE WRONG** (Bubble Bobble, M7.58,
    2026-09-29).  The painter's timed read goes through the held values (the next pass reads this
    one's), and deleting that survived: every timed pass after the first is `AND $F8 / OR ink` with
    ink <= 3, and `(x & $F8 | e1) & $F8 = x & $F8`, so no machine path can see the held value.  That is
    a proof, not "every scene agrees" (#219) -- but the code still claims to read what the machine
    reads.  Kept, and CONSTRUCTED a case that can see it (a `D = $00` pass, then `D = $FF`, all held).
    **When algebra makes a path unobservable, either delete the path or build the input that observes
    it -- never leave it both present and untestable.**

244. **A PROXY OVER A WHOLE ROUTINE PAYS FOR EVERY READ IN IT, NOT FOR THE BYTES IT GUARDS** (Bubble
    Bobble, M7.59, 2026-09-29).  The round build's held display writes first ran under one Proxy for
    the whole of `$97F8`: 108 ms a build against 1.9 without, nearly all of it `get` traps in the
    background builder and the spawn, which never touch the display.  The suite went from 13 s to 81.
    MEASURED which routines read or write the display (the direct worlds, every main-line read), and
    put the Proxy on only there, with the quiet routines checked against a copy of the display file.
    **Scope an interception to where the guarded memory is touched, and measure where that is.**

245. **THE TEST RIG'S vm CONTEXT MAKES A GLOBAL IN A HOT LOOP SEVEN TIMES DEARER** (Bubble Bobble,
    M7.59, 2026-09-29).  The scroll's copier ran 2.4 ms a build in plain node and 16.8 inside the rig:
    under `vm.runInContext` every global lookup goes through the context's interceptor, and the loop
    called a global function per write.  Before that V8 had been discarding the optimized method over
    and over ("wrong map" on `this` -- BB_Game keeps gaining fields).  The loop now runs at module
    level over a small fixed-shape object with no global named inside it: the suite 32 s -> 18.
    **Profile inside the rig, not beside it; keep hot loops off `this` and free of global names.**

246. **AN END STATE AFTER A REPAINT CANNOT SEE WHAT THE STAGES BEFORE IT GOT WRONG** (Bubble Bobble,
    M7.59, 2026-09-29).  BD5b compared a build held whole, once landed, with a build holding nothing:
    0 bytes of 48K differ.  The battery then made the scroll's copier read the screen instead of the
    held values, and BD5b stayed green -- `$8216` repaints the whole playfield from the shadow after
    the scroll, so the scroll's values never reach the end state (H2 said this of the scroll itself).
    BD5c now compares the display MID-SCROLL: the held build landed to a point against a build whose
    interrupt point is that point.  **A differential over the end of a pipeline tests only the last
    stage that writes everything.**

247. **A TABLE BUILT WITH PYTHON'S round() IS NOT THE ONE JS'S Math.round() BUILDS** (Bubble Bobble,
    M7.59, 2026-09-29).  BB_BUILD_AT, the mean of two or four samples a round, was generated with
    `round()`, which rounds halves to EVEN; the row recomputing it with `Math.round` (halves UP)
    disagreed on 23 of 81 rounds.  **Generate a JS table with JS's own rounding (floor(x + 0.5)), or
    the row that recomputes it fails on every tie.**

248. **A HAND-ROLLED INTERRUPT CHECK THAT FORGETS THE EI RULE TAKES AN INTERRUPT THE Z80 REFUSES**
    (Bubble Bobble, M7.60, 2026-09-29).  The payload sweep stepped the simulator itself and called an
    interrupt taken at the first instruction end with IFF set and the line up -- and so took one at
    1,309, the EI, where SkoolKit's `accept_interrupt` (like the Z80) refuses one straight after EI.
    The window came out 22 T short.  **A loop that decides acceptance itself must copy the
    simulator's refusal (`opcode == 0xFB`), or call `accept_interrupt` and read its result.**

249. **AN ANCHOR IS A PREFIX: A NEW LINE COPIED FROM ANOTHER ROUTINE MAKES ITS MUTANTS AMBIGUOUS**
    (Bubble Bobble, M7.60).  `stormHold`'s new store line was character for character the hurry's;
    three M7.54 cases, whose anchors stop before the line's end, then matched twice.
    `m735_anchors.py` caught it.  **Give a new line a shape of its own (reorder the test, add a
    comment) rather than widening the old anchors.**

250. **A GATE THAT REPLAYS THE ENGINE'S OWN LOG CHECKS THE LOG, NOT THE STATE** (Bubble Bobble,
    M7.60).  PS0 wrapped `stormHold`, logged each store with its operation, and replayed the log to
    compare with the machine's values -- so a mutant that wrote the placeholder value to RAM instead
    of applying the operation survived: the log was right and the RAM was wrong.  **Compare the RAM
    the engine leaves, not a reconstruction from what it said it did.**

251. **A CONSTANT TIED TO ITS MEASUREMENT IS NOT A CONSTANT SPENT AT THE RIGHT STEP** (Bubble Bobble,
    M7.61).  Row (k) proved every `BB_MENU` T equal to the fixture's, and row (j) diffed the frame layer
    against the machine frame by frame -- in BANDS (edges within 1,200 T, scans within 8).  So charging
    SPACE's 38 T accept as the plain 75, skipping the menu test's exit or `$F5F0`'s 33, or costing a digit
    as a letter all survived: the values were right and the bands too wide to see where they went.  The
    fix logs every spend with markers at the step and compares the spend next to each marker with the
    machine's number for that KEY.  **When a differential uses bands, pin each small term's USE with a
    row of its own -- a band hides any term smaller than itself.**

252. **A SCRATCH FILE READ WITHOUT AN ENCODING PUTS MOJIBAKE IN THE SUITE, AND IT STAYS GREEN**
    (Bubble Bobble, M7.62, 2026-09-30).  The H-c gate block, written as UTF-8, was spliced into
    `test/bb.test.js` by a script that read it with a bare `open(path).read()` -- cp1252 on this
    machine -- so its 38 curly apostrophes landed as three-character mojibake in the check titles.  Nothing
    failed: titles are text.  It was seen in the output by eye.  **Every script that reads or writes a
    repo or scratch text file passes `encoding='utf-8'`; after a splice, grep the file for the mojibake.**

253. **A FIRST-MISMATCH SEARCH THAT BEGINS AT A LENGTH MISMATCH NAMES THE END, NOT THE FAULT**
    (Bubble Bobble, M7.62).  H-c(a)'s first draft set the failing index to the shorter length whenever
    the lengths differed and skipped the element loop -- so it named store 8,896, where the port ran out,
    while the real divergence was store 8,272 (6,912 + 832 + 24 and 9 characters of 16): the first '?', a code the substitute font had no cell for
    (counted and never drawn, as designed).  **Search the common prefix first; fall back to the length only
    when the prefix agrees.**

254. **THE MACHINE'S DRIVE STOPS PART-WAY INTO A FRAME; THE PORT'S LAST STEP ENDS ON A BOUNDARY**
    (Bubble Bobble, M7.62).  Each redefine script stops at `$F5C6` after its last sampled boundary, with
    every OUT of the last click made; the port's last `ctrlStep` leaves that click's tail in `heldEdges`
    for the frame after, so every script came up 47 edges short.  H-b(j) never met it only because its
    scripts' last click ended sooner.  **Against a drive that stops mid-frame, count the held edges at
    their times (the next frame's start plus the offset), and step once more for the stop itself.**

255. **A SPAN THAT CROSSES A CLS IS A LAW OF THE PHASE, NOT A NUMBER** (Bubble Bobble, M7.62).  The
    loop's `$F7AA -> $F716` (when the cheat's red border goes) was first taken from one drive: 179,000 T.
    At the cheat script's phase it is 189,467 -- the CLS's 6,912 contended stores move it by 10,600 T --
    and the port's border went black a frame early.  **Before using any span that contains contended
    bulk writes, measure it at 64 phases.**

256. **A PATH AVERAGE CANNOT SERVE A COUNT THAT INTEGRATES IT** (Bubble Bobble, M7.63, 2026-09-30).  H-b
    held the ROM's frame interrupt as eight path averages -- fine for a menu diffed in bands.  `$FAC3` counts
    loop iterations across 255 of those interrupts, so every interrupt's T error is summed: 'held' is 1,124 T
    in set 1 but 1,096 in set 0, and freezing chords run 482..1,007 T against the one 980.  With 153
    iterations of slack, the averages would have misplaced the 48K/128K threshold.  Measured every interrupt
    (23,529) and fitted an exact additive law.  **Before a routine integrates a measured cost, compare the
    cost's resolution with the integrand's tolerance -- an average that passes one gate can fail the next.**

257. **A GUARDED TEST BLOCK THAT SKIPS SILENTLY LOOKS GREEN** (Bubble Bobble, M7.63).  The H-d block was
    guarded on `P.BB_SPINE && P.BB_ROMISR`; the template did not export them, so the block never ran and
    the suite said 1,591/1,591.  The only sign was the count not moving.  **Give every guarded block an
    `else` row that fails, and check the suite's count moved by the rows you added.**

258. **AN INTERRUPT THAT FALLS INSIDE A DI IS NOT NECESSARILY LOST** (Bubble Bobble, M7.63).  The frame
    interrupt is asserted for 32 T; if EI and the instruction after it end inside that window, it is
    taken late.  The hand-over's first model lost every boundary in the cold start's DI; the machine took
    one 15 T before `$8CCA` (EI + `LD A,3` = 11 T) and one 9 T before `$970E` (EI + `CALL` = 21 T).  **A DI
    window's edge is the assertion length less the T of EI and the next instruction -- measure both.**

259. **A SEEDED WORLD CARRIES WHAT ITS SEEDER LEFT** (Bubble Bobble, M7.63).  Tests entering the probe at
    `$F5C9` seeded on top of `ctrlBoot()`, whose open pass had left `ctrlDebt`; the frame layer paid that
    debt first, the probe began a frame late, and every edge script failed -- on the port's side of the
    diff, not the machine's.  **When a test enters a stage mid-flow, clear every piece of stage state the
    real flow would have consumed getting there.**

260. **A SAMPLER'S CURSOR MUST START AT THE EVENT IT SAMPLES AFTER** (Bubble Bobble, M7.63).  The tool's
    "counters at each boundary after `$970E`" kept the boundary cursor it set at `$F5CC`; at `$970E` the
    cursor was already in the past, so the first two samples were both taken there and the port looked a
    frame ahead.  **Re-anchor a sampling cursor when the sampled phase begins, and check a sample series'
    first two entries differ in T.**

261. **SOME MACHINE EDGES DO NOT EXIST** (Bubble Bobble, M7.63).  A scan for a phase putting a boundary
    exactly 21 T before `$8CCA` found none: the cold start's T moves several T per phase step, so near
    `$8CCA` only offsets -15 and -13 occur, near `$970E` -30, -28, -9 and -7.  **Before building a gate on
    an exact machine edge, enumerate the offsets that occur; where the edge itself cannot be reached, pin
    its constants from a direct measurement and test the behaviour on the offsets that do occur.**

262. **A STOP THAT A FEATURE REMOVES TAKES ITS KILLS WITH IT** (Bubble Bobble, M7.63).  While the frame layer
    STOPPED at the spine, the exact moment it stopped caught a lost `ENTRY_T` or `DISPATCH_T`, and the frame-for-
    frame rows never needed to.  H-d made the spine a live stage, the stop disappeared, and the full battery
    found both mutants surviving -- along with a path label the new interrupt law no longer read.  **When a
    change removes a boundary or makes a value unread, re-run the subsets of every earlier increment that
    touches it, not only the new cases -- and pin each spend at its step with its own row.**

263. **A FLOAT CLOCK DRIVEN BY 1000/HZ STEPS LOSES A FRAME** (Bubble Bobble, M7.64).  The page-level load
    drive fed the page's loop `tw += 1000 / HZ` from 1e5 ms; one sum rounded under a whole frame, that call
    stepped nothing, a later call stepped two, and the page ran a frame behind the machine from frame 1 --
    while the same drive from 2e6 ms passed.  The row's own one-step-per-call check was what caught it.
    **When a test drives a wall-clock loop frame by frame, add an epsilon to each step and assert exactly
    one engine frame per call.**

264. **THE PAGE'S LOOP CLOCK ONLY RUNS FORWARD, AND EVERY PAGE ROW SHARES IT** (Bubble Bobble, M7.64).  A new
    block driving the page at 2e6..3e6 ms ran before KR-page, which starts its clock at 1e6: time went
    backwards, the loop stepped nothing, and KR-page said "never left the title".  **A row that drives the
    page's rAF must start its clock above every earlier row's and below every later one's -- list them
    (`let tw =`) before choosing.**

265. **A "NEVER RAN" ROW ON COUNTERS THAT A RESET ZEROES PASSES VACUOUSLY** (Bubble Bobble, M7.64).  H-c(h)
    asserted the page's `redefOpens === 0`; once the page ran the redefine screen, the hand-over's `reset()`
    zeroed the counter and the row stayed green although the claim had become false -- only reading it
    showed it.  **When wiring flips a "never runs" row, check every such row by hand, and assert the new
    positive count from where the counters survive (`fePast`) as well as the zero where they do not.**

266. **A TABLE BUILT ON THE INPUTS A ROUTINE NORMALISES CANNOT SEE THE NORMALISATION** (Bubble Bobble, M7.65).
    `$9F18` ANDs both bytes with `$F8` before it compares.  The first oracle swept every bolt byte against
    the 32 ALIGNED enemy bytes -- the only values the author thought mattered -- so a port that dropped the
    enemy's AND passed all 8,192 answers and the battery found it.  The same subset showed four more
    survivors that were provably EQUIVALENT (after the ANDs `a - 15` is 1 mod 8, so `>` and `>=` never
    differ), which is the other half of the lesson: **sweep a comparator over the full domain of each input,
    not the domain after its own masking -- and when a mutant survives, first ask whether the arithmetic
    lets it differ at all; prove it equivalent and replace it, or find the input that separates it.**
267. **A WORLD'S OWN WALLS CAN HIDE THE ARITHMETIC** (Bubble Bobble, M7.66).  The water arm's column
    add is eight-bit, so `($FFF7)` = `$F8` seeds column 0 of the same row; a sixteen-bit add would seed
    column 0 of the NEXT row.  The oracle swept all 256 bytes -- on elwater, whose column 0 is a WALL, and
    the seed scans DOWN for the first open cell: both versions walked the same wall to the same cell, and
    768 arms could not tell them apart.  The same increment's row-23 corridor opened the margin below the
    file, so the head fell off before it ever stood on `$5AFF` or `$5B00` -- the two limits' exact cells.
    **A full-domain sweep is only as good as the world it runs in: when the routine searches, clamps or
    falls from where the input puts it, run the sweep where that search is the identity (an open shadow),
    and check that a limit's own cell is actually visited.**
268. **AN ORACLE'S CALL HELPER CAN LEAK ITS OWN STACK INTO A LONG RUN** (Bubble Bobble, M7.67).  The water
    oracle's `run_call` pushes six sentinel returns below SP and stops when the routine returns into the
    first -- which leaves SP TEN BYTES LOWER.  Nothing restored it.  The water runs were short (at most
    121 calls, 1,210 bytes, over nothing the tick reads), so their fixture never showed it; the fire runs
    are 230 calls long, and at call 232 the sentinels `$FE02` landed on `$8DBD`, the frame counter: the
    machine's element tick saw frame 2, the engine's frame 88, and the gate failed on `$9E57` -- an oracle
    fault that looked like an engine one.  The stack filter hid the writes from the fixture itself.
    **A helper that calls a routine many times in one world must put SP back after each call; check a long
    run's last calls for a byte that changed with no write logged.**
269. **WHEN A COST BECOMES STRUCTURAL, EVERY STAND-IN WORLD MUST CARRY WHAT THE COST READS** (Bubble Bobble,
    M7.68).  Two gates stand the machine's round1_48 up in a fresh engine by copying its entity TABLE --
    and nothing else.  While `$AA60` cost a flat 8,381 T that was enough.  Once it charged itself, the
    engine's world (spawned from the capture, its wake-up delays still at `+$1E`) had all three enemies
    ASLEEP (456 T a slot) where round1_48's are awake (606 + a handler run), and the odd ISR came out 5.2K
    short of the machine's median: the pass-count gate saw 12 passes where the machine runs 11.  Nothing in
    the engine was wrong.  **When a term changes from a constant to a function of state, list what the
    function reads (here the delay bytes `$A891..` and `$A98F/$A990`, the handler list) and seed it in
    every test world that claims to be the machine's -- from the fixture, never invented.**
270. **TWO ERRORS THAT CANCEL LOOK LIKE A DECLARED TOLERANCE** (Bubble Bobble, M7.68).  The ledger left out
    the 41 T before `$8D72`, so its interrupt points walked 41 T a frame from the machine's; the hurry
    block's write stamps run ~150 T late against the machine's writes.  Over the first few interrupts the
    two cancelled, and HB4 pinned "at most two rows differ, each by one write" -- on the cancellation.
    Charging the 41 T made the ledger exact to 12 T and three rows now differ by 1..7 writes: the stamps'
    own error, hidden until then.  The same thing happened under the banner, where the missing 41 T a frame
    had been offsetting the flat `$AA60` term's 2,240 T in 2P until only one of the two was fixed.  **A
    pin on a drift is a pin on the SUM of every error under it: when one term is corrected, expect the
    others to show, and re-derive the bound from what is left rather than widening it to fit.**
271. **A SCENE WHOSE PHASE COMES FROM THE LEDGER TESTS THE LEDGER** (Bubble Bobble, M7.69).  SFX5 (a chirp
    crossing the frame interrupt) and HB10's play scene (the 43rd interrupt inside the hurry's tail) both
    ran with carry 0 and let the engine's own ledger decide where the interrupt fell.  They passed because
    the ledger's T happened to put it there.  M7.69 made the player's runs exact -- 11 T a run -- and the
    chirp missed its interrupt by 244 T and the tail's by 2,189: two rows about HOLDING failed on TIMING.
    A play-length search cannot rescue them (a 150 T window in a 69,888 T frame).  **A row about a
    mechanism that needs an event at a phase must SEED the phase from the machine's measurement (and say
    how near it can get), never inherit it from the ledger: the ledger will change, and the row should not.**
272. **A VALUE THAT STOPS FEEDING A COST NEEDS A ROW THAT READS IT WHERE IT IS REPORTED** (Bubble Bobble,
    M7.68).  `aa60Diverted` once decided whether the flat `$AA60` term was charged, so a stale flag moved the
    ISR's T and a dozen rows killed "the flag never reset".  M7.68 made the diverted pass charge itself and
    left the flag only in `frameLedger()` -- and no row read it there.  The full battery's one survivor.
    **When a refactor turns a load-bearing value into a reported one, move its test to the report: read it
    on the interrupt after the one that set it.**
273. **A CONDENSED MODEL HIDES THE ARMS IT FOLDED** (Bubble Bobble, M7.69).  `hBlocked` and `probeCell` turned
    `$AED1`'s address arithmetic into one shadow-cell formula and dropped its `D < $18` arm (`$AED7`, the
    `$712F` page); every behavioural gate passed, because no gate put a player above the HUD.  The cost gate
    found it: once each run's T was the sum of the machine's own instructions, 22 rows came out 66..364 T
    off and every one was a player at Y < 9.  **When a routine is modelled by its outcome rather than its
    instructions, enumerate its branches against the disassembly and name each one the model drops --
    a T differential over natural runs is a cheap way to make the machine do it.**
274. **A SEGMENT CUT AT A BRANCH LOSES THE INSTRUCTION THAT SET ITS FLAG** (Bubble Bobble, M7.70).  The enemy
    handlers' T was summed segment by segment from the measured table, each branch's taken / not-taken T a
    term of its own -- and every `BIT n,B / JR` after a probe lost its `BIT` (8 T): the segment before ended
    at the CALL, the branch term began at the JR.  Separately `$AF8F RET c` sat in two terms.  EN1 found
    both on its first run (every walker row -8, every type-4 row +3 = +11 - 8).  **Cut segments so that
    each one starts where the last one ended: a term that begins at a branch must begin at the
    instruction that set its flag, and a terminator belongs to exactly one term.**
275. **"NOT THE INSTRUCTION'S OWN BYTES" DROPS A SELF-MODIFIED STATE** (Bubble Bobble, M7.70).  The run
    recorder skips the bytes of the instruction being executed, so an opcode fetch is not an input.  But
    `$FE85 LD HL,nn` keeps the generator's STATE in its operand: three type-4 rows drew from it and the seed
    did not carry it, so the gate's engine drew from the image's value.  **When a recorder excludes code
    bytes, list the self-modified operands that are DATA and record their reads.**
276. **AN ENTRY TEST BY CALLER MISSES THE RE-ENTRY** (Bubble Bobble, M7.70).  The oracle started a run when
    the handler was reached from `$AAEA` / `$AAEB`.  An angry slot runs its handler twice -- the second time
    entered by the FIRST run's RET into the pushed handler address -- so 1,907 of 11,191 runs (17%) were not
    recorded, and the listing showed `RET -> $AF31` as a clue.  **When a routine can be entered by a
    return, an entry test that names its callers is incomplete; read the listing's targets for every way
    in.**
277. **A PATH OF BRANCH TARGETS CANNOT SEE A RET THAT FELL THROUGH** (Bubble Bobble, M7.70).  The oracle kept
    two runs of each distinct path, the path being the PCs where control did not fall through.  A
    conditional RET that is NOT taken falls into a few instructions and an unconditional RET to the same
    caller: both runs list the same target, so type 4's arc end (`$B476`) and type 7's left homing fall
    (`$B095`) were measured and never kept -- three battery survivors, not the gate, said so.  **A dedup key
    must separate every outcome the gate prices: key on the T as well, or on the full trace.**
278. **AN OPCODE READ AS STATE BYPASSES THE READ RECORDER** (Bubble Bobble, M7.72).  The corpse landing's type
    generator is three self-modified bytes, and one is an OPCODE: `$8BA0` is `INC A` until `$88E0` writes a
    NOP there.  TRAPS #275's fix recorded the operands read as data, but the harness FETCHES an opcode from
    raw memory, never through the recorder's `__getitem__`, so `$8BA0` never entered the seed -- the gate's
    fresh engine held 0 there (a NOP) and wrote type 2 where the machine wrote 3.  **A seed recorder that
    hooks memory reads sees operand fetches, not opcode fetches: record a self-modified OPCODE explicitly
    at its own PC.**
279. **A COST TERM MEASURED ON UNSEEDED STATE HIDES THE BRANCH THAT STATE DRIVES** (Bubble Bobble, M7.72).
    `$BF0A`'s erase charged `BB_A3AD.ERASE_SH` since M7.69, exact on every final-death run of AB1 -- because
    AB1 never seeded `$A431`, the erase's accumulator, so the engine's add never carried.  The corpse oracle
    seeded it (TRAPS #275) and 58 of 274 flights came out 4 T long: `$A430 ADD A,n / LD ($A431),A / RET nc`
    falls through to its `RET` when the add carries, and `bubbleErase()` passed no cost table, so the carry
    was dropped.  **When a gate's seed omits an input, its exactness says nothing about the branches that
    input steers: seed every byte the run reads, then look for the T the new seed moves.**
280. **A DRIVE INDEXED BY THE MACHINE'S ISRS IS INDEXED BY FRAMES ONLY UNTIL AN ISR OVERRUNS** (Bubble
    Bobble, M7.73).  IA2 stepped the engine once per recorded machine ISR.  When `$B62C` began charging
    itself, IA2 failed at ISR 415 -- P1's X one step behind -- because a wave of five age pops in a full
    pool made the even ISR 77,274 T and the engine lost the next interrupt.  So did the machine (78,570
    T at ISR 414): the old flat slope charged the pool left AFTER the pops, never overran, and made the
    two indexings agree by accident.  **A cost model that cannot overrun hides every drive that confuses
    an interrupt with a frame: record the machine's ISR T beside the rows, and step over a frame the
    engine reports lost exactly where the machine's ISR ran past one.**
281. **A SEED RECORDER WRITES THE ROM DOWN, AND ROMSCAN CANNOT SEE IT** (Bubble Bobble, M7.74).  A cost
    oracle's seed is every byte the run read, as `(address, value)` hex.  The blow's bonus pays through
    `$80FA`, whose digits come from the ROM charset (`$8042 -> $3D80..`), so the first blowcost fixture
    carried 48 ROM bytes in its seeds and the glyph pixels in its writes -- and M7.72's corpse fixture,
    already committed, carried 201 (`$0000..$08FF`, a draw reading low memory).  `tools/romscan.py` passed
    both: six hex digits per byte break up every run it looks for.  **A recorder that keeps what it reads
    must refuse what it may not keep: drop the VALUE of any read below `$4000` (keep the address), keep a
    ROM-reading run's bitmap writes as addresses only, and gate the fixtures for it.**
282. **A SCRIPTED PLAY-THROUGH IS CHAOTIC IN THE MAIN LOOP'S PASS COUNT** (Bubble Bobble, M7.74).  PK8
    ("the page clears round 1 by play", SPACE two frames in sixteen) went from 3 kills to 0 when the blow
    began charging its exact T: a spawning ISR 551 T longer moved one main-loop pass, `$FEC8` differed at
    frame 68, and every bubble after it flew a different course.  Over ten phases and periods the page
    still captured in all and cleared in two.  **A fixed key script proves the page CAN do a thing, not
    that it does it on that script: when an exact cost moves it, check the claim across phases before
    calling it a regression, and re-aim the script saying why.**
283. **A HAND CHECK SUMS THE DERIVATION; THE TABLE ENCODES IT AGAIN** (Bubble Bobble, M7.76).  The rise's
    terms were hand-summed and checked by hand against the forced rows -- bounce_t0, bounce_w6, the pushes
    -- and every check agreed.  The gate then failed 16 rows: `BB_RI.BOUNCE` was 59 because it folded in
    `$B945`'s 39, which the table also charged as its own term (the hand check had added the two pieces
    once), and the push's high clamp was 41 because the sum dropped `$B97E CP $E1` (the hand check never
    reached a high-clamp row).  **The figure that is checked has to be the one the engine adds: check
    the table through the engine on every row, not the arithmetic beside it, and give every term a row
    that reaches it.**
284. **A LEDGER FIELD STORED BEFORE ITS LAST TERM IS ADDED** (Bubble Bobble, M7.77).  The manager pass
    adds every slot's provisional T into `prov`, stores it as `this.mgrProv`, then sums `tcost`.  The pop's
    provisional share (`popProv`, the award) was added to `prov` on the line before `tcost` -- AFTER the
    store -- so `tcost` charged it and `frameLedger().b62c.prov` did not show it: the ISR's T was right
    and the report of where it went was wrong.  Every per-row gate passed; MG3 (the ISR's T against the
    ledger's parts, with the pop stubbed to charge 1000 / 200 / 30) and PO2 (`.prov` against `.pop_prov`)
    caught it.  **Add every term before any field is stored, and gate the ledger's parts against the
    total the ISR charged, with a stub that charges a distinct figure in each part.**
285. **MAKING ONE TERM EXACT CAN REMOVE THE LAST ROW THAT DROVE ANOTHER FIELD** (Bubble Bobble, M7.79).  The
    travel increment priced `$A447`'s live arm, so a live enemy's corpse birth -- nested in the blow's steal
    -- stopped being PROVISIONAL.  The M7.79 subset was clean; the FULL battery after it found three M7.74
    survivors (`.blow_prov` dropped from `.prov`, hidden from the ledger, not cleared by the next ISR): the
    only pass-level row whose blow carried a provisional T had been that birth, and now carried 0, so every
    gate on `.blow_prov` compared 0 with 0.  PO3 now runs a paid steal (the award, the one provisional T a
    blow can still carry) through the pass and a gate-shut ISR.  **When a term turns exact, look for the
    gates that were exercising a SIBLING field through it -- and run the full battery, not just the
    increment's subset: a subset only mutates the new code.**
286. **A FLAT COST MAKES DIFFERENT WORLDS AGREE BY ACCIDENT; AN EXACT ONE SPLITS THEM** (Bubble Bobble, M7.88).
    The main loop charged every pass a flat 6,186 T -- round1_48's CONTENDED pass.  M7.88 made `$931A` charge
    its own exact T, and three things moved at once.  (1) Taking passcost's ALL-STATE UNCONTENDED median
    (1,286) out of the flat rest made round 1's pass 234 T short: the share removed must be the callee's
    share OF THE CALIBRATION (round1_48, contended: 2,023).  (2) Even then the census world -- the machine's
    own round1_48 entity table, `$931A` exactly 2,006 -- ran 17 T a pass short of the machine and fit a
    twelfth odd-frame pass across 11 passes of carry: the exact T needs the CALIBRATION STATE's contention
    stretch (1.008319), or the calibrated world stops being calibrated.  (3) Two rows pinned the port's
    freshly-built world (enemies asleep, each probe 23 T) to counts the machine measured on its BOSS round
    (7 `$FEC8` wraps in 200 frames; 3..5 frames a cadence): with a flat cost those agreed, with an exact one
    the port's world runs ~10.7 passes a frame -- as the machine would THERE.  They now assert the
    structure.  **When a flat calibrated cost is split into exact parts, remove each part's share AS
    CALIBRATED (same state, same contention), stretch the exact part by the calibration's contention, and
    re-read every row that compared rates across two worlds: it was passing on the flat cost, not on the
    machine.**
    **M7.90's refinement: "as calibrated" means the same FRAMES too.**  BB_PASS_T was fit on the timing census --
    round1_48's first 48 frames, where every `$C002` run is idle; round1_48's 300-frame contended mean (913) also
    holds seven live-sparkle runs the calibration never saw, and taking it out left the census pass at 6,181 T,
    where only 6,182..6,211 gives the machine's 11 odd passes.  The census window's own mean (907, K 1.019451)
    keeps it.  Every callee's tool now carries a `window` survey for this.

287. **A TERM THE GEOMETRY ZEROES ON EVERY ROW THAT CAN SEE IT** (Bubble Bobble, M7.100).  The giant's lazy block
    puts its award's DI window on the CONTENDED clock, and the mutant that left it on the exact clock survived
    every gate: the lost-interrupt rows (RX2, LZ1's six) all put a frame boundary at the window's end, and a window
    of 4,355 T ending at a boundary lies wholly in the bottom border (contention stops at 57,343 of 69,888), so its
    contended end IS its exact end on exactly the rows that test lost-ness.  The term only moves on rows where no
    boundary is near.  **When a term matters only away from the rows that test the behaviour, pin the term
    itself on the rows where it moves** (LZ1 now asserts the window's contended end, 0..54 T past the exact by
    the phase).  The same run's other survivor was a true equivalent -- a stamp on the queue's clock that
    flushWrites consumed in the same step, so its offset could not matter: the code was simplified to land the
    write directly, not tested harder.

288. **AN ACCESS PROGRAM WITH NO INSTRUCTIONS IN IT** (Bubble Bobble, M7.101).  M7.100's lazy blocks carried each
    contended access's T and nothing else, and lzSeg put every access past the interrupt point after the ISR.
    The machine takes the interrupt at the END of the instruction in progress, so that instruction's later
    accesses are made at phase 0.. (top border, no wait), before the ISR.  The giant's 46 rows were all exact by
    luck: no contended access straddled a boundary followed by a long odd ISR.  The wrap's 34th row did (r50_48,
    phase 65520: one access put after a 53,539-T ISR waited 94 T).  The fix gave every access its T into its
    instruction (`bbAcc`), and the gate written to pin those numbers (LZ4: the engine's `T:k` stream against
    the machine's plain run, access for access) found the next assumption at once: `$80E7 LD A,($5AC0)` reads 10 T
    in, not 4, as an `LD A,(HL)` would.  **A timing model that splits a run at an interrupt must split it where the
    machine does -- at an instruction's end -- and the instruction structure is a measurement like any other:
    gate it against the machine, don't type it from the opcode you think is there.**

289. **A TEST THAT PUTS BACK THE VALUE IT EXPECTS, NOT THE ONE IT FOUND** (Bubble Bobble, M7.102).  PF1b measures the
    K model of the treasure room's block, so it takes the block's `lazy` flag down for its runs and puts it back
    in a `finally`: `PFB.lazy = true`.  The mutant that took `lazy: true` out of the block's declaration SURVIVED
    the whole suite -- PF1b, early in the file, set the flag to true for every gate after it (LZ5, C3, LZ2), so
    the mutated engine ran lazily anyway.  A test that toggles shared state must restore what it FOUND
    (`const was = PFB.lazy; ... finally { PFB.lazy = was; }`); restoring the value the test believes is right
    repairs exactly the bug the declaration's mutant plants.  **Save and restore; never restore a constant.**

290. **A WINDOW EDGE READ OFF A FLAG, NOT OFF THE THING IT GATES** (Bubble Bobble, M7.105).  Every DI window the
    engine kept opened where IFF reads clear -- the DI's end -- because that is what the fixtures recorded ("IFF clear
    from the DI's end").  But the window's job is to say which interrupts are LOST, and the machine samples the line
    at an instruction's end: one rising 1..3 T into a DI meets the DI's end with IFF already clear, so it is lost
    too.  Three T in 69,888 a window -- no grid of forced phases (4,368 apart) ever landed there, and every gate
    compared the window to the same flag-derived number, so all agreed.  The storm payload's window, measured by
    sweeping the interrupt's offset, had been right all along (its DI + 1).  **Measure an edge with the event it
    decides -- sweep the boundary across it and record taken or lost -- never with a state flag that changes near it.**

291. **A DECLARED DEVIATION NAMED AFTER THE FEATURE THAT SHOWED IT** (Bubble Bobble, M7.106).  M7.97 found the giant
    ticking once more in the round advance's frame and declared "one extra giant tick".  The cause was the countdown:
    a latched `$8E3A` reads the ISR's timer at the END of every pass, and the interrupt that makes `$0177` lands inside
    a pass ~99% of the time -- so EVERY countdown advance on the machine comes in the straddling pass, and the port's
    atomic pass made every one of them a pass late (30 of 30 measured).  The giant was only the one thing in the frame
    that drew.  **When a declared gap is phrased by its symptom, measure its mechanism across worlds where the symptom
    is absent; the reach is usually the mechanism's, not the symptom's.**

292. **ONE INSTRUCTION, TWO CONTENTION PATTERNS: THE PORT IS (A << 8) | n** (Bubble Bobble, M7.107).  `IN A,($FE)`
    puts A on the address bus's high byte.  The pause's poll loads A = `$FE` first: high byte uncontended, I/O
    pattern N:1, C:3, one delay 8 T into the IN.  The gate 22 T earlier loads A = `$7F`: high byte in `$40..$7F`,
    pattern C:1, C:3, two delays (7 and 8 in).  A model fitted on the poll train alone was exact on 621,676
    polls, and 26 of 249 arm runs came out 1..6 T short.  **For every I/O instruction, read the high byte the code
    actually loads (A for `IN A,(n)` / `OUT (n),A`, B for `(C)` forms) before you pick its contention pattern.**

293. **A TIMEOUT IS NOT A CRASH** (Bubble Bobble, M7.108).  A `--match` battery run launched in the foreground with a
    590-s timeout died with `BrokenProcessPool` -- the same words as the known `--background` failure on this
    machine, so it read as "the pool breaks here too".  It was the timeout: the runner's coverage preparation alone
    took 4 minutes, and killing the parent killed the workers mid-task.  **Before reading a failure as the known one,
    check what ended the process -- your own timeout is the first suspect.**  Long jobs go through Start-Process.

294. **LINE ENDINGS ARE PART OF A HASH** (Bubble Bobble, M7.108).  `core.autocrlf` is true, so the working copy of
    `test/bb.test.js` is CRLF, and the battery runner keys each case's killing block by the sha of the block's source
    text.  An editor that saved the file as LF changed every block's sha at once: `--affected` re-selected 5,227
    cases on "killing block changed", ran each one's whole coverage selection instead of its killer first, and had
    not finished one worker in 35 minutes (a full run is 13).  `git diff` showed nothing odd -- git normalises the
    endings.  **After editing a hashed file, check its line endings match the checkout (CRLF here) before a battery;
    a selection count near the whole battery after a small change is the tell.**

295. **A STATE MADE AT ONCE IS SEEN BY EVERY BOUNDARY THAT CUTS ITS INSTRUCTIONS** (Bubble Bobble, M7.109).  The ring's
    iteration was timed instruction by instruction and its WRITE held for its own instruction, and the iteration counts
    and the attribute file came out exact at every boundary -- and 27 of 28 runs still failed, on the PRNG: the port
    drew it when the iteration began, the machine stores it at `$FE91`, 140 T in.  Nothing at the title reads the PRNG
    between the two, so it looked like an equivalence to declare -- but a boundary that cuts the iteration is a sample,
    and the sample saw the difference (196 of 660 boundaries).  **When an action is moved onto a clock, move every
    store it makes, not only the one you were looking at; then a gate can compare the whole state at every boundary
    instead of declaring the parts it cannot.**

296. **A HELPER THAT RETURNS A SIMULATOR MAY ALSO HAVE TAKEN YOURS** (Bubble Bobble, M7.110).  `revealcont.sim_of(h, log)`
    builds a logging CMIOSimulator -- no contention, every contended access appended to `log` -- and also puts it in
    `h.sim`.  painttime.py measured the plain stream with it and then ran its contended runs on the same harness: they
    ran on the logger, uncontended, appending to a list that never stopped, and the capture reached 12.8 GB before it
    was killed (the probe that worked had used a fresh harness per call without knowing why).  **Give a measurement
    that swaps the machine its own harness, and when a capture slows from seconds to minutes, look at its memory before
    its logic.**

297. **A FIELD YOU REMOVE TAKES ITS MUTANTS' TEETH WITH IT** (Bubble Bobble, M7.111).  The release passes stopped being
    a debt, so `frontDebt` went -- and an old case, "ctrlPaint charges the paint as the front end's debt already",
    whose mutation was `this.frontDebt = BB_FE.PAINT_T`, SURVIVED the affected run: it now wrote a property nothing
    reads, and the row that killed it had compared `g.frontDebt` before and after (undefined === undefined).  The
    case was re-aimed to what the row means -- the paint charged through `spend()` -- and killed.  **When a field
    dies, grep the battery for every case that writes it: each is now an equivalent mutant, and its row a check of
    nothing.**

298. **A GATE'S WORLD THAT PASSED A SHORT BLOCK CAN BE WRONG FOR THE NEXT ONE** (Bubble Bobble, M7.112).  TX2's world at
    `$9765` is a fresh `BB_Game` with the title's display, PRNG, counters and gates seeded -- right for the exit, which
    reads almost nothing.  Carried on through `$97F8`, the same world built ROUND TWO: a fresh game is the capture's
    in-play world, `$8609 = 1`, and the machine's `$96DF` had set it to 0.  The first symptom was 329 display writes
    missing and every stamp in the wrong place -- read as a timing bug for a while.  The world needs `gameReset()`
    (`$96DF`'s reset half) first, as the page's load path has it.  Two smaller lies on the way: the round number is a
    ROM glyph drawn into the SHADOW and copied up by the repaint (mask the display cells under `$7F80`'s stores, not
    only `$8052`'s), and the engine's step ends WITH the next boundary's ISR -- so a row after `$9887` must be the
    machine's state after that ISR (the first gate-open one draws the players), not at its boundary.  **When a gate
    drive runs past the block its world was built for, list what the new block reads and check the world holds the
    machine's value for each.**
299. **THE HARNESS'S HALT SHORTCUT LANDS ON THE BOUNDARY; THE MACHINE LANDS ON THE HALT'S 4-T GRID** (Bubble Bobble,
    M7.113).  `Harness._fast_halt()` jumps T straight to the frame boundary and takes the interrupt there; the Z80 runs a
    HALT as 4-T steps and takes it at the end of the first step at or past the boundary -- (the HALT's phase) mod 4 T
    late.  r1tail.py steps the opcode and saw `$9888` at 496 / 13,515 where `$9887` began 3 / 1 mod 4; every tool that
    used `run_until` / `step` / `loadpath.drive` across a HALT measured its exit up to 3 T early.  The engine's
    `roundSeqStep('halt')` now lands on the grid; its other HALTs (`$7EC2`, the game-over screen) still land on the
    boundary, as the fixtures measured them.  **When a tool's exactness matters across a HALT, step the opcode -- and
    check which convention the fixture you compare against was made with.**  A second convention found on the way:
    loadpath changes keys AT the boundary, before that boundary's ISR, while the engine's step() keeps one keyboard for its
    main line and the ISR that ends it -- so an ISR-time key read (the players' `$AB38`) differs by a frame between the two
    drives on a key change; compare like with like (scratchpad/world/machisr.py changes keys at the ISR's end).
300. **TWO "TAPE" IMAGES, AND ONLY ONE IS THE LOADED GAME** (Bubble Bobble, M7.114a).  `build/image.bin` is mkimage.py's
    ASSERTED postcondition (each block where the loader would put it, the loader's moves by hand) and adis.py's default;
    for this Bleepload tape it is NOT what the loader leaves.  `build/image_tape.bin` (bleepload.py's rebuild, checked
    byte for byte against boot.pkl, tap2sna's snapshot of the REAL loader) is.  They differ at 8,253 bytes, among them
    operands the port reads: `$9077` 6 / 3, `$9194` `$AA` / 4, `$91DC` `$F6` / 8, `$91D0` `$D2` / `$2A`, `$91E4` `$0E` /
    0.  reset() and hurry.py's "tape" operands came from image.bin since M7.7, three gates asserted them, and the cold
    machine they claimed to describe never existed: the real load carries image_tape.bin's values to the first pass of
    play (passacc's `tape_ops`), and with them the edge detectors' operands (`$2A`, the developer's own last frame) that
    decide which pass the first once-a-frame tick lands in.  **A value "from the tape" names its image; for a protected
    loader only the simulated load's (or a rebuild checked against it) is the game.**
301. **AN ATOMIC PASS MOVES EVERY EDGE DETECTOR A PASS LATE** (Bubble Bobble, M7.114a; TRAPS #90's general case).  The
    machine's pass that straddles the interrupt runs its later callees AFTER the ISR -- `$9E50`, `$9AEB`, `$A09A`,
    `$A824`, `$A9ED`, `$8669` compare `$8DBD` / `$8DB6` with an operand of their own and fire in that pass, not the next.
    A port that runs whole passes and then the ISR fires each of them one pass late -- once a frame, every frame -- and a
    gate that counts passes or reads the world at frame boundaries cannot see it.  It showed only when the pass's T was
    made exact and the passes still parted at the first straddle.  The fix is the interrupt INSIDE the pass (at a
    callee's entry, or at an edge read a fixed way in); a read that comes after a callee's own kid needs the read's
    place (`ctrRead`).  **When the main line is put on the frame clock, the ISR's writes have to land where the clock
    says.**

302. **A CONTENDED ISR'S T DEPENDS ON THE INSTRUCTION THE INTERRUPT WAS TAKEN AFTER** (Bubble Bobble, M7.114c).  The
    interrupt is accepted at the END of the instruction in progress at the boundary -- 0..15 T in on the real load -- and
    an ISR whose accesses reach the screen's lines waits the ULA from THAT phase: D falls about one T per T of phase with
    8-T jumps, so a constant estimate is a few T off on most contended ISRs, and the engine's own `carry` (the overshoot to
    the next callee's entry, up to ~1,000 T) is no estimate at all -- with it a synthetic-phase scene's age column and a
    fruit test's overrun row moved.  Gate the program and the delay GIVEN the machine's acceptance phase (IC2), and say
    where the phase comes from.  **An ISR's cost has an input outside the ISR: where the main line was.**

303. **"THE INSTRUCTION IN PROGRESS" HAS TWO TRAPS: EI, AND A CUT THAT ASSUMES THE PATH** (Bubble Bobble, M7.114d).  The
    Z80 accepts no interrupt straight after EI, so a point that falls at the end of `$8D0C`'s EI is taken after the NEXT
    instruction (13 T on, frame 474 of the real load) -- a grid that only knows lengths gets it 13 T wrong.  And M7.114a's
    edge-read cut (`BB_EDGE_LOOK`: cut the pass at a callee's entry when its counter read would be past the point) cut
    there even when the callee RETURNED before its read (`$A9ED` off round 80, `$A824` with no giant, `$9037` on round 80,
    `$8669` with a player carried): the state was the same either way, so no gate saw it -- only the grid did, when the
    head's 59 T were laid out where the machine ran 31.  **A cut rule written for one path is a timing claim about every
    path: make it read the bytes that choose the path.**

304. **A REFUSAL THAT THROWS FROM A PATH THE PAGE RUNS IS A CRASH, AND A HEADLESS RUN WILL NOT FIND IT** (Bubble Bobble,
    2026-10-08, found by the owner in the browser).  M7.114d's `gridWalk` THREW on a grid key with a CALL summed n times
    -- "refuse by name" -- and the giant item's row erase (`$A929`, `zs('A966t', 3)`) is such a key.  It fires only when
    the pass holding the giant's tick is the one that straddles the interrupt point, so the page froze "at a random
    interval" after a giant appeared, while 18 headless giant scenes of 3,000 frames each ran clean (the straddle never
    landed there).  A throw is right for a broken TABLE (a key that does not sum to its charge: no input can make it
    happen); for an INPUT the model does not cover it is a counted miss (`gridCallN`), with a gate that walks the pass
    directly rather than hoping the frame clock puts the point in it.  **Ask which refusals the page can reach, and
    gate those with the scene forced, not sampled.**  (Same day: `handDone`'s `reset()` laid the load image's display
    file -- round 1's screen -- over the machine's black one for two frames; a state transplant must say which RAM is
    the machine's at that moment, the screen included.)

305. **A "TAPE VALUE" LIST TAKEN AT PLAY MISSES EVERY BYTE THE SETUP READS BEFORE IT WRITES** (Bubble Bobble, M7.114e).
    BB_TAPE_OPS took each byte's value at the first pass of play and kept those nothing had written; `$73AF`, the spawn's
    rolling seed, is read-modify-written by the round start, so it was neither.  Separately the hand-over's `reset()`
    stood round 1 up (for the test worlds) and the round start spawned again, so the seed rolled twice; enemies' movement
    dividers ran 21 frames off and the ISR T parted 350 frames later as "a bubble-manager arm's +1,510 T".  The cure was a
    class sweep, not the byte: every RAM byte the machine reads before writing, load to the window's end, against the
    engine's RAM right after the transplant -- two bytes, both fixed.  **When a transplant (reset, a state load) stands in
    for the machine's own setup, sweep read-before-write against it once; and a T difference whose access program
    matches is a decision, so look for the state that made it before pricing an arm.**

306. **A HALT HIDES A CLOCK THAT IS OFF BY A MULTIPLE OF 4; A TEMPLATE SWEPT ON ONE BANK HIDES THE OTHER BANKS' WAITS**
    (Bubble Bobble, M7.115c).  Every later-round gate passed "given the machine's ISR T", and free-running found two
    errors those gates could not see.  The build's clock began at the advance pass's `$8D0C`, 96 T before `$97F8` -- and
    the `$9887` HALT that follows resumes on the 4-T grid at the next interrupt, so a 96-T error vanished at `$9888` on
    every world but the one where the gap before it was not a multiple of 4 (an advance begun in the frame the last
    tail ended).  And the ISR's draw templates were swept with the sprite at `$C100`, uncontended; type 0's facing-1
    copy lives at `$5B80`, and its reads wait.  **A wait-for-the-boundary instruction (HALT, a sync loop) is a low-pass
    filter on timing errors: check the T BEFORE it, not just the frame and phase after.  And a sweep's fixed inputs are
    part of its result -- vary the one that decides whether an access is contended (the source address), not only the
    ones that move the destination.**

307. **THE PAGE'S DEFAULT PATH IS A WORLD OF ITS OWN** (Bubble Bobble, M7.115c, the owner's round 2).  Every later-round
    gate ran the FAITHFUL path (`skipProbe` off) or `gameStart`; the page ships with `skipProbe` ON, an added layer that
    skips the probe whose HALT clears the control select's fractional T.  On the page's own path the clock reaches play
    with a fraction, and an integer-indexed table (`bbLrMap`'s) turned it into NaN: the game froze after round 2's level
    was drawn, with nothing in the console.  An added-layer flag changes the world the faithful code runs in, not just
    what the player sees.  **Run each new mechanism on the page's default flags too (the boot the page itself makes);
    and an engine clock that may hold a fraction must never index an array with it -- use the scalar function, or floor.**
    (TRAPS #304's giant crash was the same shape: page only, found by the owner.)

308. **A LOOP MODELLED TO ITS LAST ITERATION IS NOT THE ROUTINE; A STUB NAMED "RENDER WORK" CAN HOLD STATE** (Bubble
    Bobble, M7.115d, the owner's potion freeze).  The treasure room's fill was transliterated loop for loop and gated byte
    for byte over 81 maps -- and stopped at the outer loop's `DEC C`, dropping the five instructions after it that open
    both ISR gates.  Every unit row passed (they check the item block); in play the player never moved again.  And
    `$894B CALL $8C14` was left out as "render work", but its first twenty bytes RES 7 every enemy and bubble slot.
    **Model a routine to its RET (or its JP), and give a stub's callee a state census before calling it render.**

309. **A NEW BLOCK CAN STRADDLE A TEST'S RE-PHASE; A LONG CONTENDED WINDOW'S CLOSE HAS NO PHASE THAT REACHES IT** (Bubble
    Bobble, M7.115e, the potion as a block).  (a) The in-play `$FECD` sweep re-phases the clock between its 80 rows
    (`letGo`, `carry = ...`), written when every block ended inside the pass that began it.  Round 81 spawns its power-up
    at once -- a potion, under P1 with no keys held -- so the potion's ~240,000-T block was still in flight when the row
    ended; `letGo` zeroed the pass's callee charges but not the prefix the block had spent (`passPre`), and the resumed
    pass charged a negative T (`passWait`: "the access program goes backwards").  The engine was right; the harness cut
    the machine in half.  (b) M7.105-style straddles for the WINDOW'S CLOSE (a boundary 32 / 31 T before the end of the
    instruction after the EI: lost / taken AT the close) work on the potion's head window, whose only contended stores
    are twenty bytes; on the reveal's window they cannot -- ~37,000 T of contended stores re-sync its main line to the
    ULA, so its close lands at frame phase ~188 or ~-2 whatever the entry, and the fixed point cycles.  (c) "Exact given
    the machine's ISR T" (LZ9, 125 / 125) left 142 T free-running: the block's entry inside `$8669` waits for the item
    pass's own accesses (the take's erase, the award's glyphs, the chirp's OUTs), which no pass program holds.
    **When a block is added, grep the suite for helpers that re-phase or transplant state between rows and run each over
    the worlds that can trigger it -- drain (or refuse) a block in flight; measure a window's close only where its
    main line is not re-synced by contention, and let the blocks that can reach a shared constant pin it; and check the
    ENTRY of a mid-callee block free-running, not just the block given its entry.**

310. **A GATE THAT SEEDS ITS WORLD FROM THE MACHINE SUPPLIES THE BYTES THE PORT NEVER LOADS; A WATCH'S SILENCE IS THE SIZE
    OF ITS WORLDS** (Bubble Bobble, 2026-10-10, the owner's "Boris doesn't appear after the hurry up").  (a) Boris was
    implemented, switched on as the machine does and gated -- and drew blank: his 64-byte sprite `$FF50..$FF8F` is tape
    data the port never laid down, the giant banks' twin of two days before.  A sweep for the class (tools/tapereads.py:
    every byte the machine reads in play that no run writes, against the page's own RAM) found four more in one pass:
    the lightning bolt and the fire's two frames (the bolts -- the boss fight's too -- and the flames drew blank), the
    giant diamond's award byte `$AAE9` (SPEC had recorded its +56,000 since 2026-09-09; the port paid nothing), and
    round 45's cells below the map.  Each routine was gated byte for byte -- in worlds seeded from the machine
    (entdraw's sprites, fireman's read seeds, the award gate's types 1..3 but not the 0 the game spawns), so the seed
    was the missing byte.  (b) A 115,069-frame write-watch on Boris's bank over 21 worlds saw no write, and the sweep's
    wider worlds found one: `$B7A1`'s chain mark indexes the bubble flags in eight bits and markers 20..26 land on the
    bank -- `$FF67` goes `$E6` -> `$EE` in round 1.  The boss captures' `$EE` was image.bin's (TRAPS #300) AND a real
    write.  (c) "Read before this run's first write" is not static data: the map, the entity and bubble slots and the
    self-modified operands hold the tape's value by coincidence often enough to bury the class; the class is the bytes
    NO run writes, plus live cells named one by one.
    **When one routine is found reading bytes the port never loaded, sweep for the class: every byte the machine reads
    in play that nothing writes, against the page's own RAM, nothing seeded.  A world seeded from the machine tests the
    routine, never the RAM it starts from.  And a watch that saw nothing has measured its worlds, not the game.**

311. **A BLOCK THAT ENDS INSIDE A CALLEE LEAVES THAT CALLEE'S REST BEFORE THE NEXT CALL; A PASS RESUMED WITH A FRESH PROGRAM
    OWES NOTHING TO ITS PREFIX** (Bubble Bobble, 2026-10-10, M7.115f).  With the item pass on the program the potion's `$890D`
    was exact free-running and the treasure room's passes were the machine's -- all but the first, 2 T late.  (a) The block
    ends at the potion handler's RET, INSIDE `$8669`: the item pass's rest (POP HL .. RET z, POP BC / POP HL / RET, 62 T) and
    the chain's CALL come before the next callee, and the resumed pass's program began at 0 -- its callees' accesses 79 T
    early, their contention 2 T off.  (b) Found reading the code for (a): `passSettle` spends the prefix's waits, and
    `passCharge` took them off AGAIN from the resumed pass's fresh program (`passPreD`), under-charging it whenever a
    mid-pass block ended past the point -- the potion always, the join sometimes.  (c) Making `lzStep` start a segment at
    step()'s clock (so the potion's tail could wait first) broke six LZ gates that drive `lzStep` directly with a stale clock:
    the new start went in as a parameter step() passes, the old default kept.
    **When a block ends, ask where the machine is then -- inside which callee, how far from the next CALL -- and what the
    resumed pass's program and charge still hold of the part before; and when a shared method gains an input, give its
    direct callers the old one.**

312. **AN ATOMIC CALLEE IS THE MACHINE'S ONLY WHERE NOTHING IT READS AFTER ITS INTERRUPT HAS MOVED** (Bubble Bobble,
    2026-10-10, M7.115f).  The treasure room's item walk (21 entries, ~64,000 T) spans its frame: the odd ISR inside it moves
    P1, and the machine's later entries test their boxes against the moved P1 -- an X test's way out flips (~141 T) and the
    free-running passes part from the machine's at frame 840 / 878, exact until then.  The same in `$931A`'s probes (frame
    644 of a fruit world: one probe more after its ISR).  M7.114a declared it ("the callee the point falls inside runs whole
    before the ISR"); no gate had ever shown where it bites.  tools/itemacc.py found it by replaying each natural call PLAIN
    from its entry state and comparing paths: `same` false names exactly the calls an ISR changed (10 of the room's 28
    distinct walks).
    **When a callee spans its interrupt, replay it atomically from its entry and compare paths with the natural run: a
    difference is a read of what the ISR wrote, which an atomic model cannot make -- count where, and cut the callee there
    when it matters.**

313. **A CALLEE RUN WHOLE BEFORE ITS INTERRUPT IS WRONG IN TWO DIRECTIONS, AND A REPLAY OF THE ISR MUST SEE THE KEYS AND THE R IT
    SAW** (Bubble Bobble, 2026-10-10, M7.115g).  (a) The census of the class (tools/straddle.py: 27,087 calls with one ISR
    inside) measured the callee's side -- its reads after the point see the ISR's writes: 141 calls on the engine's rule --
    and then, asked separately, the ISR's side -- run after the callee's later writes, the ISR wrote otherwise on 19 more,
    mostly screen bytes a main-line blit and the ISR's sprites share.  A census of one direction would have called the
    class done.  (b) The method was checked by its own extreme: the ISR's changes laid on at the machine's instruction must
    give the natural call back exactly, every row -- and that check found the R register (the ISR's instructions move it;
    an LD A,R after the point reads it) before any verdict was trusted.  (c) The first late-ISR census blamed 220 calls,
    most with no read of the callee's writes at all: the saved-state driver changes the keys at the frame boundary, AFTER
    the acceptance and before the ISR's first read, and the replay took the keys at the acceptance.  The keys an ISR reads
    are the ones at its first instruction.
    **When a model reorders a callee and its interrupt, measure both directions; validate the replay by its exact case
    first; and give a replayed ISR the inputs it actually read -- the keys at its first instruction, the R its own
    instructions moved -- or the census measures the replay.**

314. **A SITE IS RIGHT ONLY TO THE T IT IS TESTED TO, AND A CENSUS TESTS ONLY THE READS THAT CHANGED** (Bubble Bobble,
    2026-10-10, M7.115g).  The census's 91 class rows exercised the collide's X and flags reads and three of `$931A`'s probe
    reads -- never the collide's Y, its lock or the probe's second flag test, whose bytes no natural ISR moved there.  Those
    sites passed every row because no row reached them; a site missing or a T off would have passed too.  SG4 drives each
    site directly: the ISR flips the byte the read sees, the point at the reading instruction's first T (the ISR first:
    the decision follows it) and one T later (the read first) -- and takes the places from the instruction lists
    (BB_GRID), not from the engine's own offsets, so a wrong constant cannot agree with itself.
    **Test every site at its instruction's first T and the T after, from the measured instruction list; a census that
    passes says nothing about the reads it never saw change.**

315. **A READ-BEFORE-WRITE SEED LEAVES OUT THE BYTES AN INSTRUCTION RUNS -- AND A SELF-MODIFIED OPERAND IS ONE** (Bubble
    Bobble, 2026-10-11, M7.115h).  tools/straddle.py seeds each gate row's replay with the bytes the machine's call read
    before writing them, and (revealentry's SeedMem rule) not the bytes of the instruction being run -- an opcode fetch is
    not data.  But `$8E3A`'s clear latch `$8E3B`, its drain's base `$8F3A` and the one-left latch `$90AA` are the operands
    of `LD A,n` / `SUB n`, and the walk's `$90D0` the second byte of `SET 2,(HL)` (the respawn's calm XORs it to RES),
    written by other code: STATE read as CODE.  A fresh engine seeded without them reads the
    image's values (0, 42, 0) where the machine's were the round's: replayed so, 32 of `$8E3A`'s 138 gate rows take
    another path -- the latched countdown's run as a tally, the latched anger's as a first walk -- and look like engine
    bugs.  M7.115f had met it for the item pass and listed that routine's operands by hand (IA.SMC); the next routine with
    self-modified state needed its own list.
    **A replay seeded from read-before-write must add the self-modified operands its routine reads as instruction bytes,
    routine by routine; when a replay parts from the machine at a branch on such a byte, suspect the seed before the
    engine.**

316. **A BASE A LOOP MAINTAINS IS STALE FOR THE CALL AFTER THE LOOP** (Bubble Bobble, 2026-10-11, M7.115h).  chainWalk sets
    `pbase` -- the running callee's entry, every in-pass clock's origin (calleeAt, ctrRead) -- at the top of its loop over
    the chain; `$8D5E CALL $8E3A` runs after the loop, so inside a pass `$8E3A`'s base was still `$8E2A`'s, and the
    countdown's reads (cdPos, M7.106) were placed 65 T early on round 1's latched passes.  No gate saw it: M7.106's CD3
    tests cdPos outside a pass (calleeAt's other branch) and CD2's world reaches its advance by the split route.  It
    surfaced when the cursor walked through `$8E3A` and the two clocks were compared for the same instruction (SH3).
    **When two mechanisms place the same instruction, assert they agree -- in a pass, not only outside one; and check every
    call a loop's bookkeeping does not reach.**

317. **LIVE STATE THAT ONLY THE TAPE INITIALISES IS INVISIBLE TO A "NO RUN WRITES IT" RULE -- COMPARE THE PAGE'S RAM WITH
    THE MACHINE'S AT A POINT THEY SHARE** (Bubble Bobble, 2026-10-11, the owner's "the boss doesn't move and hitting it
    once with a lightning bolt kills it straight away").  The boss's velocities `$AA47` / `$AA48` are tape bytes ($01 / $01)
    nothing in the game sets -- bosstick.py had said so since B3 -- and the bounce WRITES them (`$AA43`, the NEG), so #310's
    sweep, which kept only the bytes no run writes, dropped them as live state: #310 (c) named that risk and took it.  The
    port never laid them down.  Its boss stood at the spawn; and a bolt that hits skips its own physics (`$9F57` returns to
    `$9EE7`, past `$9ED0`), so it dwelt in the accept set and took all 42 HP -- one bolt, one kill.  On the machine the boss
    moves on after a hit or two.  Every boss gate seeded its world from a capture holding $01 / $01: #310 (a), again.  The
    rule that sees the class: run the machine and the page on one path to a point they share (the real load's frame 600,
    the drive exact pass for pass) and compare the RAM at EVERY address any run reads before its first write, whatever its
    value (tapereads' census: 18,369 addresses; bb.test TB2).  What differs is the class plus a short declared list -- the
    stack, the 128K path, a jump table the engine dispatches in code, the R stand-in, the element bubble built on demand,
    the bubble pool's tape junk -- each with its reason, each required still to differ, and each "read only after a write"
    claim checked against the reads that saw the tape's value.  It also found `$79A3`, the seed of the boss setup `$79A2`
    the port had never modelled.
    **When a sweep's rule must leave a class out, give the class its own rule -- the strongest is a whole-RAM differential at
    a point the page and the machine share -- and gate the behaviour on the page's OWN path (tools/bossfree.py: the boss's
    bodies from the real load), because a world seeded from a capture holds every byte the page forgot to load.**

318. **A HALT IN CONTENDED RAM IS NOT A 4-T GRID FROM ITS START: ITS FETCHES WAIT, AND IN THE SCREEN FETCH THEY LOCK TO THE
    ULA** (Bubble Bobble, 2026-10-11, M7.115i).  `$7E80`'s `$7EC2 EI / HALT` sits at `$7EC3`, below $8000.  A halted Z80 goes
    on fetching -- SkoolKit: an M1 at the HALT, then at `$7EC4` -- 4 T a step, and each fetch waits in the screen fetch like
    any other, so the steps lock to the ULA's 8-T cycle: all 37 natural HALTs were taken at phase 1, wherever they began.
    M7.113's rule for the round start's HALT at `$9887` -- taken (its start mod 4) T into the frame -- holds only where the
    fetches never wait: a phased HALT that began past the screen's last line (after a 60,967-T ISR) was taken at 3.  And an
    interrupt taken BEFORE the HALT -- the point inside the call before its EI, or AT the EI's start, where the instruction
    before it ends -- leaves the HALT to wait for the NEXT one: a whole frame (an EI in progress at the point holds the
    interrupt only to the end of the HALT's first step).  The engine walks the steps (emHaltWalk: 4 T and the ULA's delay at
    each start, the first always run, the interrupt at the end of the first that ends at or past the point); tools/emitacc.py
    asserts that walk on every HALT it sees (72).
    **A HALT's acceptance is its steps' walk from where it began, through its own contention -- not its start's alignment.**

319. **A SITE DRIVEN OUTSIDE step() NEEDS step()'S FRAME-START STATE** (Bubble Bobble, 2026-10-11, M7.115i).  isrHere works
    out the ISR's acceptance phase only when `gridPhV` is null, which step() sets at each frame's start; undefined means a
    MISS (counted, BB_ISR_ACCEPT).  A fresh engine's is undefined, so EA4b's first scene -- the machine's call with the
    boundary moved onto it, driven through smallRun -- ran the ISR inside `$7E80` at no phase, and the gate read the engine
    as wrong.  It was the scene.
    **A scene that drives a frame-clock mechanism outside step() must set what step() sets at a frame's start (`gridPhV`
    null, `isrDone` false), or it reads the mechanism's MISS as the engine's answer.**

320. **TO PUT THE INTERRUPT ON A RULE'S EDGE, MOVE THE CALL: SET ITS ENTRY'S T IN THE BOTTOM BORDER** (Bubble Bobble,
    2026-10-11, M7.115i).  No natural run put an interrupt inside `$7E80` before its HALT (about one emit in fifty would),
    and the mutants on the late test (`>=` / `>`, the EI's start / the HALT's) and on the counter read's offset survived
    every natural world.  emitacc's PHASED runs take a natural call's entry state and set the CPU's T so that the entry lies
    `shift` T before a frame boundary -- in the bottom border, where nothing waits, so plain offsets are wall offsets and the
    point lands on the T wanted: 10 / 70 T in; AT and 1 T into `$7E98`'s read; AT and 2 T into the EI; AT and 1 T into the
    HALT's first step.  Each edge is a PAIR -- at an instruction's start and one T in -- and each pair kills the mutant that
    moves its edge by one.
    **Give each edge of a timing rule a machine run on both sides of it, placed to the T; when nature does not place them,
    place them yourself in the border.**

321. **A PROBE THAT REASSEMBLES A PASS MUST USE THE GATE'S OWN HOOKS -- ALL OF THEM** (Bubble Bobble, 2026-10-12, M7.115j).
    The first free-running probe of r80 after the boss's blits went on the program reported pass 2900 (frame 1361) parting by
    276 accesses -- 154 against the machine's 430.  It was the probe.  That pass holds `$7E80`'s HALT, and the gate (EA3)
    reassembles a pass across the HALT with two more hooks (emHaltBegin takes the program to the HALT, emKey('BIT') moves the
    base past its steps); the probe had copied the cut's and the charge's hooks only.  With them: exact.
    **A scratch probe of a gated quantity starts as a copy of the gate's harness, every hook of it; a "part" the probe finds
    is the probe's until the gate's harness agrees.**

322. **A SUM WRITTEN BY HAND NEEDS ITS GRID WRITTEN TOO -- AND ONLY A FORCED PATH SHOWS IT** (Bubble Bobble, 2026-10-12,
    M7.115j).  `A978t` (the RET c that closes `$A969` on a P2 hit) is BB_SM's one sum costsmall never measured (no natural run
    has P2 over the boss); it was written in M7.96, its grid never.  gridWalk takes a key with no grid as "not laid out" --
    the region invalid, counted, nothing thrown -- so the P2-hit region was never on the grid, and no gate drove it: every
    boss world is 1P.  BA2's forced 'p2 over' replay found it as one instruction missing (1,239 / 1,240) and an invalid grid.
    **Every hand-written sum gets its hand-written grid in the same edit, and a forced run through it: the path no world
    takes is the one no gate has seen.**

323. **PHASE IS NOT ENOUGH: THE INTERRUPT YOU PLACE HAS A PARITY** (Bubble Bobble, 2026-10-12, M7.115j).  bossacc's phased
    runs moved the frame boundary onto 21 places in a body; all 42 runs then took the SAME ISR -- the frame counter's parity
    is the entry state's -- and that one was odd (the player's, 1,892 T), which draws no sprite.  So none of them reached the
    late class (the ISR's sprites on the boss's screen bytes), and the old rule's control could not fail.  Flipping `$8DBD`'s
    bit 0 (and re-aiming `$AA00` so the tick's SUB still reaches the body) put the even ISR there: 28 late-class runs.
    **When you place an interrupt, place both of its kinds: the boundary's phase AND the ISR's parity (or whatever selects
    its work), each a run.**

324. **A "WHAT DID THE ISR SEE" CHECK NEEDS THE BYTES THE SEED NEVER HELD** (Bubble Bobble, 2026-10-12, M7.115j).  A replay's seed is
    every byte the CALL read before writing it.  The boss's blits write the screen and read none of it, so a seeded engine
    holds zeros where the machine's screen was -- and the ISR nested in the blit reads exactly those bytes (its sprites).
    BA5's first run compared the engine's view with the machine's and failed on every late row for want of the entry's
    screen, not for the nesting.  The census now carries, for each byte the late ISR read, [address, the value it read, the
    entry's value]; the gate lays the entry's down first.  The same for a CONTROL: an ISR whose reads were recorded only
    for bytes the call had already written (bossacc's first TMem) can never show the late class, which is the bytes the
    call writes AFTER it -- by construction its control cannot fail.
    **Compare only what the run reads or writes, and carry the entry value of every byte a nested reader looks at that
    the seed does not hold; record a reader's view of bytes written before AND after it.**

325. **AN ISR'S CHANGES ARE WHAT IT LEFT WHEN IT RETURNED, NOT WHAT THE RUN LEFT** (Bubble Bobble, 2026-10-12, M7.115k).
    sparkacc's first phased runs took the ISR's changes the way bossacc does: every byte the ISR wrote, valued at the END of
    the run.  In the 'pop' scene the ISR seeds a slot at phase 1 and the walk, after it, advances the slot and writes it back
    at phase 2.  So the "change" the gate laid down at the ISR was the walk's phase 2, and the engine's walk then drew where
    the machine erased.  The changes are now taken when the ISR returns.  bossacc's phased runs have the same shape, latent:
    nothing there writes again after the ISR what the ISR wrote.
    **Snapshot a nested reader's effects at its own end; a value read later is someone else's.**

326. **WHAT THE ISR "READ OF THE CALL'S BYTES" EXCLUDES WHAT IT HAD WRITTEN ITSELF** (Bubble Bobble, 2026-10-12, M7.115k).
    The ISR's sprite routines erase a sprite's cells from the shadow and then draw it, reading the cells back, so its first
    read of such a byte returns its own write.  sparkacc's first 'seen' (bossacc's TMem) kept every first read.  70 of 76
    phased runs disagreed with an engine stub that reports the bytes as the ISR found them on entry -- the record was wrong,
    not the engine.  The phased memory now keeps a read only when the ISR has not written that byte before it.
    **A "what the reader saw" record is the bytes it read before writing them; the rest is its own.**

327. **A DECLARED POKE "AT THE END OF ISR L" GOES WHERE THE ENGINE'S ISR RETURNS** (Bubble Bobble, 2026-10-12, M7.115k).  The
    spark world lays the table at the end of every 4th ISR.  The first free-running probe laid it before the next step --
    where an ISR at the frame's end returns -- and parted at frame 723: ISR 724 was taken inside a walk (isrHere), and on the
    machine that walk's later slots read the lay at once.  The gate now lays it from inside the engine's isr(), wherever that
    runs.  BA3's and IA3's single pokes are read only at a later pass's start, so the step boundary served them.
    **A drive's poke at an ISR's end hooks the ISR, not the frame loop; once ISRs nest inside callees, the two differ.**

328. **COUNT ONLY THE STORES THE NESTED READER CAN SEE** (Bubble Bobble, 2026-10-12, M7.115k).  BA4 compares the machine's
    count of the call's stores before the ISR with the engine's.  That is exact for the boss, where every store between two
    sites is itself a site.  The sparkle walk stores bytes no ISR reads (`$C04A`, `$C048`, its record) between its sites, and
    the engine takes the ISR at the next site, after them.  That is the same machine with a different count.  The count is
    now taken over the bytes the ISR reads (the screen, the table) on both sides.
    **When a check counts effects before an interleaving point, count those the other side can observe; the rest may move
    freely, and a site among them would be an equivalent mutant.**

329. **A FIX THAT MOVES A FREE-RUNNING PIN OWES THE NEW PIN ITS MEASURED CAUSE** (Bubble Bobble, 2026-10-12, M7.115k).  With
    the sparkle's accesses on the program, IA3's fruit world ran past its pin (806) to 970, and the spark world showed seven
    ISRs' T off.  Each looked like the sparkle's; on the machine none was:
    - pass 970 holds Boris's erase (`$915F`'s `$A314`, 32 stores the program lacks);
    - ISR 804 holds a pop whose seed's store waits 5 T (the pop's 83 accesses are not on the ISR's program);
    - ISR 971 holds the lives panel drawn inside the ISR (54 accesses).
    Each was found by dumping the machine's accesses with their PCs and diffing them against the engine's program, access
    by access.
    **When a pin moves, dump the machine's accesses (with PCs) at the new one and diff them against the engine's before
    naming the cause; the new gap is usually someone else's.**

330. **A PHASED RUN BEGUN AT THE CALLEE'S ENTRY CANNOT PUT THE INTERRUPT BEFORE ITS FIRST INSTRUCTION** (Bubble Bobble,
    2026-10-12, M7.115l).  borisacc's first capture placed the point AT `$915F`'s entry (shift 0).  The harness samples the
    INT line at an instruction's END, and the run starts at the entry, so the first sample came after `LD A,n`: an ISR at
    offset 7, phase 7.  On the machine a point at the entry's first T is the CALL's end, and the ISR comes before the callee
    (the chain's split at its entry).  That row is dropped; the entry is placed 1 T in only.  sparkacc's and bossacc's AT
    targets were all past a first instruction, whose end sampled the line.
    **A run that starts at a callee's entry has no instruction before it: the point AT the entry belongs to the caller.**

331. **A SEEDED ENGINE'S FAR-AWAY POINT PUTS EVERY ACCESS IN THE SCREEN** (Bubble Bobble, 2026-10-12, M7.115l).  BK5's first
    window check ran with seeded()'s budget 1e9 and found Boris's window ending 58 T past the machine's RET.  passClock
    counts the waits of the accesses before the point, and with the point 1e9 T away every store sits at the wall phase
    (o - 1e9) mod 69,888 -- in the screen fetch.  The phased checks, the point inside the call, were right.  The window
    check now puts the point 1,000 T past the call, its stores in the bottom border.
    **A clock-derived value in a unit gate depends on where the gate puts the point: put it where the machine's run had it,
    or where nothing waits.**

332. **WHEN AN ISR'S T DIFFERS BUT ITS ACCESS PROGRAM DOES NOT, LOOK AT THE R STAND-IN FIRST** (Bubble Bobble, 2026-10-12,
    M7.115l).  Boris's erase moved IA3's fruit pin from 970 to 1128.  ISR 1128 was 452 T short, yet its 613 accesses and
    their waits were the machine's: the difference was a path, not a wait.  The machine's PCs at the ISR's end ran the
    walker's `$B0D5` (LD A,R / CP `$2A`, the 1/128 hesitation); the engine's stand-in drew `$2A`, the machine's R 39.  Fed
    the machine's draws, the engine's ISR 1128 is the machine's 34,213 T.  The stand-in had drawn 36 values in the window
    before it, none `$2A`, so the worlds agreed until the 1-in-128 came up.
    **A stand-in for a random source agrees with the machine only until its first decisive value: when a free-running ISR
    keeps its access program but not its T, feed the machine's draws before naming another cause.**

333. **A DI WINDOW HAS TWO EDGES AND THREE OUTCOMES** (Bubble Bobble, 2026-10-12, M7.115l).  `$915F`'s erase runs between
    `$9163 DI` and `$917A EI`.  borisacc's 84 phased runs, in three scenes:
    - a point at or before the DI's first T is taken there, before the stores -- the ISR INCs the hurry timer they then
      clear, so the next ISR's parity changes;
    - from 1 T into the DI to 32 T before the end of the instruction after the EI, it is LOST;
    - 31 .. 1 T before that end, the pulse outlasts the window and the end takes it, at the phase "end less point" --
      whatever instruction the grid held at the point.
    The engine had no window there; it ran every such interrupt at the next callee's entry.  It now has a site at the DI,
    pushes the window (intLost), and gridPh returns a window's end for a point inside one -- every window's, the award's
    too.
    **Model a DI window with all three outcomes -- taken before (a site at the DI), lost (the window), late (its end as the
    acceptance phase) -- and place each edge with a phased run.**

334. **A PIN DOWNSTREAM OF A KNOWN GAP MOVES WITH ANY FIX IN THE SHIFTED REGION** (Bubble Bobble, 2026-10-12, M7.115l).  SK3's
    ISRs 972 .. 976 sit after ISR 971's 10-T gap (the lives panel), so their T were already wrong and pinned.  With Boris's
    erase on the program they moved again (+7 / +4 / +7 to +3 / -3 / -2).  Before re-pinning, the new gridPh rule's hits in
    that world were counted (0) and its lost interrupts (0): the movement was the erase's waits in a shifted pass, the
    respawn in ISR 971 having raised his request.
    **When a fix moves values a known gap already makes wrong, show which part of the fix moved them before re-pinning --
    count the new rule's firings.**

335. **A SAVED STATE'S SP MAY NOT BE A STACK** (Bubble Bobble, 2026-10-12, M7.115m).  popacc's forced calls first pushed
    `$B62C`'s return address below each saved state's own SP.  round1_2p48 was captured inside `$A447`, whose blit borrows
    SP as its data pointer, so its SP was `$FD2E`.  The forced push scene's pass then ran its stack over the `$FDxx` tables
    and its IY wandered to `$FCEC`: a pop no scene asked for, with a cancel.  The even ISR's real SP at `$B62C`'s entry
    (`$96BB..$96C3` on every world, a probe) is now every forced call's stack.
    **Before you push onto a saved state's SP, check that it is a stack: a state captured inside a blitter may hold a data
    pointer there.  Build forced calls on the stack the caller really runs on.**

336. **A FORCED SCENE CAN WALK INTO A DECLARED GAP BY ITS DEFAULTS** (Bubble Bobble, 2026-10-12, M7.115m).  The forced paid
    pops first used a held bubble whose marker pointer was the rise's ROM park (`$02xx`).  The paid path's chain walk
    reads that 4x4 window -- ROM bytes, which mark slots on the machine.  The port ships no ROM (chainRomReads, declared),
    so every paid scene's T was 1,972 T short and its writes wrong (a mark at `$FFA3`), and the first diff looked like a
    clock error.  The paid scenes now use the bubble's own cell; the 3 natural calls whose window lies in the ROM are named,
    and EV5 holds that the engine counts their reads and makes no mark from them.
    **Give a forced scene the state the path is meant to test, not a default that reaches a declared gap; when a forced
    run fails, check its path against the declared list before the model.**

337. **EXCLUDE THE CODE A RUN REWRITES FROM A WRITES DIGEST BY RULE, AND ASSERT THE RULE** (Bubble Bobble, 2026-10-12,
    M7.115m).  The first EV2 run failed the writes on every call.  The machine rewrites the `$A447` erase's operands and
    the `$B9E7` draw's before they run (and patches `$A480` / `$A5D9` and restores them); the engine stores none of them.
    The earlier gates listed such bytes by hand (OPS).  popacc now detects them -- code bytes fetched after this run wrote
    them -- and its capture FAILS on one in neither OPS (not state) nor SMC (state the engine models: the capture's `$92DE`
    patch, the class `$B742`, the chain centre `$B775`...).  A new self-modified byte cannot hide in the exclusion.
    **When a check leaves bytes out, derive the list from the run and fail on anything undeclared; a hand-kept list
    silently excludes the next byte that should have been compared.**

338. **AN INPUT CAN BE AN OPERAND THE RUN FETCHES FIRST** (Bubble Bobble, 2026-10-12, M7.115m).  The replays' seed is every
    byte read before written -- but SeedMem leaves out the running instruction's own bytes, so a self-modified operand
    fetched before any write is not in it.  The flash toggle `$B62D` (`$B62C LD A,n`), the age toggle `$B657`, the beam
    addend `$A431` and the corpse birth's generator `$FE86` / `$FE87` (`$FE85 LD HL,nn`) are all inputs that way.  popacc
    records the instruction bytes fetched before any access.  Its capture fails on one that a run also writes and SMC does
    not list -- it found `$FE86` / `$FE87`, which the first list missed.
    **A seed built from data reads misses inputs that live in operands: record the instruction bytes fetched first, and
    fail when one that any run writes is undeclared.**

339. **A CLOCK TERM THAT ONLY TWO EVENTS IN ONE PASS CAN SEE SURVIVES EVERY ONE-EVENT SCENE** (Bubble Bobble, 2026-10-12,
    M7.115m).  The hand battery killed 75 of popacc's 78 cases.  The three survivors were each a callee's T inside a clock:
    - `$B656`'s clock carries the rise's callee T (a push's erase) before the age's arms;
    - the push's clock carries what player 1's walk added before player 2's push;
    - the blow's clock carries player 1's bonus award before player 2's.
    Every natural and forced call had at most one such event, so each term was zero wherever it was read.  Each is a real
    machine path, and five forced scenes now stack two events: a push then the age pop, a push then the escape, both
    bonuses, a bonus then the steal, and two pushes of one bubble.  The double push needs player 2 at (`$10`, `$10`):
    `$B901` tests the registers player 1's push left (B = 2, C = the wind code 2).
    **For every sum in a clock, find the scene where that term is non-zero when it is read: a callee's T matters only when
    a later event in the same pass reads the clock.**

340. **A RIG THAT RUNS EVERY LISTENER CANNOT TEST A STOP** (Bubble Bobble, 2026-10-12, M9.1).  Alt+Enter toggles
    fullscreen, and ENTER is a Spectrum key (buildKeymap): the page's key listener runs before attachKeyboard's and calls
    `stopImmediatePropagation()`, so the game never sees that ENTER.  The rig's `fire()` ran every listener whatever an
    earlier one did -- a page that forgot the stop and a page that made it gave the same rows, so the row could not
    fail.  `fire()` now stops where a browser stops, and kit.test.js holds it (upstreamed: kit `c32f351`).
    **When a row depends on something the browser does -- propagation, default actions, focus, storage -- check that the
    rig does it too before trusting the row: TRAPS #17 again, one layer down.**

341. **AN ORACLE THAT RUNS A ROUTINE PAST ITS FIRST READ OF THE ROM RECORDS ROM BYTES** (Bubble Bobble, 2026-10-13,
    M10.0b).  The direct engine oracle called the music engine's request with 0 and then ticked it 3,000 times.  Request
    0 only mutes: it loads no sound, so the fresh engine's pointers were still 0, and at tick 256 the slots read $0000
    -- the ROM -- and wrote what they found there to the AY.  The capture was written, verified and cross-checked
    against the 128K machine, both of which agreed, because both run the same ROM.  Only the summary gave it away: 152
    "pass ends" in a stream with no sound loaded.  Every engine stream now runs under a read watch that stops the stream
    at the engine's first read below $4000 and records the address, never the bytes; the end state is taken before that
    tick.
    **When an oracle runs code the port will transliterate, watch its reads: a stream that touches the ROM must stop
    there.  Two machines agreeing proves nothing about where the bytes came from.**

342. **AN ORACLE'S FIXTURE WITHOUT ITS GATE FAILS THE SUITE'S FIXTURE GUARDS, BOTH WAYS** (Bubble Bobble, 2026-10-13,
    M10.0b).  The suite holds two guards: every test-only asset in port.json is READ by a check, and every build/*.json
    on disk is registered or named in a pinned list.  M10.0's oracles land before the increments whose gates read them.
    Registered, the engine fixture failed the first guard; unregistered, the second (1920/1922 both ways).  Such a
    fixture now waits in build/pending/, which the directory guard does not list, and the increment that adds its gate
    moves it to build/ and registers it (the tool's FIXTURE constant says so).
    **Land an oracle's fixture with its reader, or park it where the guards are not looking, by name, and move it when the
    reader lands.  Do not weaken the guard to fit the schedule.**

343. **A DRIVE RULE SCOPED BY A CONDITION, NOT A PLACE, FIRES WHERE NO ONE LOOKED** (Bubble Bobble, 2026-10-13,
    M10.0c).  The flow oracle's pause scene needed keys at frame boundaries: the pause spins with the interrupts off, and
    the drive applies keys at ISR ends.  The first rule applied them at any boundary where IFF was 0.  The front end has
    DI stretches of its own, and there the rule changed when keys arrived: the probe's start moved from phase 52,024
    to 2,240, and the whole real load shifted.  The rule now fires only inside the pause's spin ($8FF6..$9009), which is
    pausespin's convention, and the probe's phase is back.
    **Scope a drive rule by WHERE it is needed, not by a condition that happens to hold there, and re-check a known
    landmark (here the probe's phase) after changing one.**

344. **A REFUSAL HALFWAY THROUGH A ROUTINE LEAVES HALF ITS STORES** (Bubble Bobble, 2026-10-13, M10.1).  The JS music
    engine must refuse the fetch a never-requested engine makes at tick 256 ($0000, the ROM).  By the time slot C reads
    there, the tick has already stored its counter, and in general an earlier slot may have stored a note and made AY
    writes.  The oracle stops BEFORE that tick, so a refusal that just stops leaves a state no machine had.  The tick now
    keeps an undo record of its own stores and puts them back, LAST FIRST, before it returns the refusal.  Replayed
    first to last, the record restores the wrong value whenever a call stores one byte twice -- the counter is
    decremented to 0 and then reloaded by the note -- and a gate row (AE6: slot A's refusal after slot C's note) fails
    on exactly that.
    **Make a refusal atomic: undo every store the refused call made, newest first, and gate the state it leaves against
    the oracle's stop point.**

345. **"THE ENGINE" IS A SLICE OF THE PAGE'S TEXT, AND THREE CENSUSES READ IT** (Bubble Bobble, 2026-10-13, M10.1).  The
    ship / test split and the UNCALLED-method census both cut the built page from the first `class BB_Game` to
    `globalThis.__PORT__`.  An asset read outside that slice is "shipped but unread".  A class placed inside it has its
    two-space-indented methods counted as the game's uncalled methods.  The slice starts at the first occurrence of the
    TEXT, so a comment that names the class earlier would move it.  The reachability census reads every `game.X(` outside
    the class body.  So the engine class sits BEFORE the slice, beside BB_Rng, and its one asset read (`bbAyBytes`) is a
    column-0 function AFTER the class, which no census counts.
    **Before adding code to the engine file, know which census reads which slice, and place the code by that, not by
    taste.  M10.2 wires the engine into the class: its new methods join the censuses on purpose.**

346. **A COUNT IN A DOC IS A MEASUREMENT ONLY UNTIL SOMEONE COUNTS IT** (Bubble Bobble, 2026-10-13, M10.2a).  M10.0c's flow
    oracle measured the page's skip at 64 hand-over phases, and its docstring, SPEC, M10-PLAN, STATUS and next.md all said
    "20 of 64 (27,300..46,956) do not wait".  The fixture's own rows hold 19: 27,300 to 46,956 in steps of 1,092 is
    nineteen phases.  The error lived in five documents for a day because no gate read the number; the first gate that
    counted the rows (M10.2a's H5) found it.
    **When a doc states a count, have the gate that reads the fixture assert that count from the rows -- a prose number no
    check reads is a guess with a provenance.**

347. **A CHECK WHOSE OTHER VALUE NO PATH CAN REACH IS AN EQUIVALENT MUTANT -- FIND IT BEFORE THE BATTERY DOES**
    (Bubble Bobble, 2026-10-13, M10.2a).  The 128K hand-over takes the frame's interrupt only with IFF 1 and not right
    after an EI (`H.iff && !H.ei`), and pays its two debts (the cold start, the reset half) in chunks that stop at the
    frame's end.  The hand battery left both standing: on the hand-over's path IFF is 1 at every check -- its IFF-0
    stretches are debts, whose checks only ever lose an interrupt -- and the frame's carry takes a debt past the boundary
    exactly as the chunks do, each boundary's interrupt lost either way.  Two more lines (the request's and the reset
    half's `DI` stores) could not be read by any check at all and were removed before the battery.
    **For every guard or term, name the path that reaches it with the other value.  If none does, it is either dead code
    or a later increment's (here M10.2c's requests made with interrupts off): say which, and leave its mutation out with
    the reason.**

348. **A SAMPLER THAT RECORDS AFTER THE EVENT IT DESCRIBES** (Bubble Bobble, 2026-10-13, M10.2a).  The flow oracle's
    `frames` rows carry IFF "at each boundary BEFORE that frame's interrupt (IFF 0 = the interrupt is lost)".  But the
    drive records a boundary at the first loop turn past it, and the previous turn has already run the instruction that
    crossed it AND accepted the interrupt -- so a frame whose interrupt was TAKEN at once reads IFF 0 too (the hand-over's
    frame 348).  Counting lost interrupts from that column would have been wrong.  M10.2a counts them from the ISR rows
    instead: the boundaries between the hand-over and `$970E` less the interrupts taken.
    **Know where a sampler stands relative to the event its column names; when it can stand on either side, derive the
    fact from the records that cannot (here the ISR rows), and say so in the gate.**

349. **A GATE WHOSE INPUT PRODUCES THE DEFAULT CANNOT SEE THE INPUT LOST** (Bubble Bobble, 2026-10-13, M10.2a).  The
    swap at `$8CCA` must carry the control select's key buffer into the new world.  The flow's real load picks P1
    KEYBOARD (O, P, SPACE, Q) and P2 SINCLAIR -- which is exactly BB_KEYTAB, the table reset() seeds when no buffer
    arrives.  A swap that dropped the buffer gave the same bytes, and the battery case for it could not die.  The gate now
    drives loadpath's cursor_kempston (P1 CURSOR, P2 KEMPSTON) under m128 and compares the machine's table.
    **Drive a carry-over gate with an input whose result differs from every default the code falls back to -- and check
    the default is not the answer first.**

350. **A BOUNDARY ROW IS NOT WHAT A LATE READER SAW** (Bubble Bobble, 2026-10-14, M10.2b).  The flow oracle samples the
    sound state at each frame boundary, before the frame's interrupt; the 128K sound hook reads it at the END of that
    interrupt, after the passes.  A unit drive of the hook from the boundary rows matched 10,542 of the oracle's 10,543
    hooks.  The other, p1's ISR 1697, read the HURRY latch as 0 though the boundaries on both sides of it say 1: the
    player's respawn at `$ABA8`, inside `$AA60`'s pass, cleared it before the hook, and the main line's `$9059` set it
    again before the next boundary (a write watch on the harness: scratchpad/m102b/latch1697.py).  No boundary sample
    could show it.  The oracle now records the hook's inputs where the hook reads them (the `hooks` rows), and the
    unit drive (B2) uses those: 10,543 of 10,543.
    **Sample a routine's inputs at the routine, not at the nearest convenient boundary -- a byte can change and change
    back between two samples.**

351. **A PROVISIONAL CONSTANT IS SAFE ONLY WHILE NOTHING READS ITS ERROR** (Bubble Bobble, 2026-10-14, M10.2b).  The
    title's interrupts took `BB_ISR_ACCEPT` (4 T, "PROVISIONAL where none is known") as their acceptance phase.  On the
    48K nothing could see it: the title's interrupt has both gates shut and no contended access, so its T does not
    depend on the phase.  The 128K hook places its AY writes and OUTs from the acceptance phase, and the first comparison
    with the flow oracle put 19 of p1's 21 title interrupts 1..6 T off.  The phase had been available all along -- the front end
    runs an instruction at a time, so it is where the instruction in progress at the boundary ends (frontFrame keeps it
    now) -- and the 48K's isracc confirms it on all ten title and release interrupts.
    **When a new consumer reads a value that was provisional because nothing read it, re-derive the value first: "it
    does not matter" was a statement about the old consumers only.**

352. **A SUM-ONLY GATE CANNOT SEE A SPLIT** (Bubble Bobble, 2026-10-14, M10.2b).  The hook's two `OUT ($7FFD)`s put their
    I/O cycles on the ISR's access program, so that `isrD` (the ISR's contention) carries their waits and `isrPlain` the
    rest.  The arithmetic makes `isrCost = isrPlain + isrD` the same whatever offsets those cycles are given -- a wrong
    offset only moves T from one term to the other -- so every gate that compares the ISR's T (B1, H4's interrupt rows)
    passes a mutant there.  B3 gates each term: `isrD` the 48K's plus the waits `bbIo7ffd` gives at the OUTs' T,
    `isrPlain` the rest, and the program access for access.
    **When code moves an amount between two terms whose sum is what the gates read, gate each term.**

353. **A REPLAY THAT ASSUMES THE INTERRUPT'S T INHERITS EVERY CHANGE TO IT** (Bubble Bobble, 2026-10-14, M10.2c).  Round 1's
    build is replayed at `$97F8` with each interrupt's T dropped in at its boundary: a constant, the 48K's gate-closed
    ISR, exact on 18 runs.  M10.2b made every interrupt under m128 longer by the sound hook, and the engine's own ISRs
    charged it -- but the replay, made before they run, still placed the 48K's constant, so its contention and its end
    were the 48K's.  p1, p2 and idle showed nothing (their HALT phase happened to agree); only the skip scene's HALT
    interrupt, accepted at 3 T for the machine's 0, gave it away.  The replay now takes each interrupt's hook from a plan
    stepped on a copy of the engine, and isrHook checks every planned T against the one it runs.
    **When you change what an interrupt costs, find every place that predicted that cost before it ran -- a replay, a
    mirror, a fitted constant -- and make it ask, or check it against what then happens.**

354. **AN ORACLE THAT FORCES ITS CLOCK HAS EDGES THAT ARE NOT THE CODE'S** (Bubble Bobble, 2026-10-14, M10.2c).  The flow
    oracle's di_window places the frame boundary o T after a request's DI by moving the clock at `$8E0A`'s entry.  For
    o < -29 the boundary is "before" the entry, so the simulator sees an interrupt already pending there and takes it one
    instruction in -- no real run does that (a boundary inside the CALL is taken at the CALL's end).  For o > 548 the
    instruction in progress is the caller's, not the request's.  Gating the request on all 179 rows failed 13 of them for
    reasons that had nothing to do with the request; on the 163 inside `[$8E0A, its RET's end]` it is exact.
    **Before gating against a forced oracle, mark which of its rows the forcing itself decided, and gate the rest.**

355. **A STAND-IN IS FREE-RUNNING EXACT ONLY WHERE NOTHING READS IT** (Bubble Bobble, 2026-10-14, M10.2c).  The engine's R
    register is a stand-in seeded per session; the 48K's free-running gate (GR4) is exact because its window reads no
    `LD A,R` that matters.  Under m128 the first comparison of p1 parted at frame 740, one frame into play: 4,229 passes
    for the machine's 3,814, and a cascade after.  It was not the new code -- with the machine's 2,126 `LD A,R` draws fed
    (the oracle records them), the passes agree to the T for twenty frames more and the remaining partings are the
    48K port's own play timing.
    **Feed every stand-in the machine's values before reading a free-running divergence as a bug in the code under
    test.**

356. **A STEP PLACED AFTER A PASS INHERITS WHATEVER THE PASS ALREADY CHARGED OF IT** (Bubble Bobble, 2026-10-14, M10.2c2).
    The boss defeat under m128 became a program step() runs after the pass that found the boss dead -- its waits cannot
    end inside a pass.  The first cut started it at the pass's end and charged the banner and the instructions between
    the sound calls in it, reasoning from the 48K's comment that an advance pass charges 96 T.  It was a CLEAR pass: it
    charges the whole chain, `$8E3A`'s own T with it -- the banner's 5,507 T and the defeat's tail included -- so the
    request landed ~7,000 T late and the banner was spent twice.  Only printing which pass path ran (`passLast.path`
    'clear') showed it.  The pass now charges `$8E3A` to `$8E77` alone and the program starts there.
    **When a step moves out of a pass, find which path charged the pass and what of the step it already holds; read
    the path from the run, not from the comment that describes the usual one.**

357. **A KEY THAT IS NOT A GAME KEY STILL CHOOSES THE PASS'S PATH** (Bubble Bobble, 2026-10-15, M10.2d).  The 128K pause's
    scenes left the machine right after the release, by 2 T at the first interrupt: every pass of the release frame ran
    22 T longer on the machine.  CAPS SHIFT, which releases the pause, is half of BREAK: with CAPS up `$8D68 JR c` jumps
    to `$8D70`; with CAPS down and SPACE up the pass runs `$8D6A LD A,$7F / IN A,($FE) / RRA / RET nc` -- 22 T and a second
    contended IN.  The 48K's pass skeleton was measured with no key down, so the port never charged it, and no gate held
    CAPS through a pass until the 128K pause's release had to.  Not fixed (the timing campaign is stopped, owner
    2026-10-12): DECLARED in SPEC "The pause", the scenes pinned after the release.
    **A skeleton measured on one path is that path's.  List what chooses its branches -- a release key, a held direction,
    a flag -- and drive each before calling it a constant.**

358. **A FORCED RUN CAN BE PRE-EMPTED BY THE NATURAL ONE, AND THEN IT IS THE NATURAL ONE** (Bubble Bobble, 2026-10-15,
    M10.2d).  pause128's forced runs pressed SYM at a boundary b0 and moved the clock at the first `$8FE7` at or after b0.
    On one world the pass reached `$8FE7` 1 T BEFORE b0 and its IN read SYM 6 T later: the arm was natural, the forcing
    never happened, and 50 "forced" runs repeated the natural one -- seen only because a summary grouped the outcomes by
    world.  The keys now go down at the forced instruction itself, and the tool asserts that each forced run's arm is the
    forced one.
    **Assert that a forced run was forced.  A condition the natural path can satisfy first fails silently.**

359. **AN OFFSET BETWEEN TWO EVENTS HOLDS ONLY WHERE NO INTERRUPT FALLS BETWEEN THEM** (Bubble Bobble, 2026-10-15, M10.2d).
    Q2's first draft took the `$8FF3` arrival as the request's entry less the CALL's 17 T, and expected the engine's
    `$8D2B` at the machine's.  Both failed exactly on the forced runs that took an interrupt in between -- at the CALL's
    end, at the unpause's RET -- because there the machine runs the ISR between the two events, and the engine runs it at
    the frame's end.  The oracle now records the arrival itself; the gate takes the machine's interrupt out of its `$8D2B`.
    **Record each event a gate compares.  Derive an offset only across a span the oracle asserts is uninterrupted.**

360. **A REPLAY THAT TAKES EACH FRAME'S ORIGIN FROM THE ENGINE'S CLOCK CANNOT SEE THAT CLOCK WRONG** (Bubble Bobble,
    2026-10-15, M10.2d).  Q2 replays every machine run through spinStep a frame at a time, and after an interrupt in the
    arm it sets the next frame's origin so that the main line resumes at the machine's ISR end: `off = ISR end - spin.t`.
    The hand battery's one survivor left request 0's cut clock un-re-based (`sp.t = t` for `t - budget`) -- and the replay
    absorbed it, since it computes the origin from the very value that was wrong; step() takes its origin from the
    interrupt's cost and resumed the arm a frame late.  Q6 now forces the arm into the interrupt THROUGH step() (PZ4's
    way) at the machine's three cases.
    **A replay harness that reads the engine's state to place the next step tests the steps, not the hand-over between
    them: drive the hand-over through the real loop too.**
361. **A CONSTANT OF 1 HIDES ITS OWN MULTIPLICATION, AND AN ORIGIN OF 0 ITS OWN SUBTRACTION** (Bubble Bobble, 2026-10-15,
    M10.3).  The mix's exactness checks compared the chunked stream with a one-shot render built in the test -- and ran at
    the default AY level, `AY_MIX` = 1.0, on maps whose origin was frame 0.  Listing the mutants before any ran showed two
    that could not fail: `out[i] += g*y` as `out[i] += y` (the level dropped) and `(f - this.vbase)` as `f` (the origin
    dropped) -- with g = 1 and vbase = 0 they ARE the code.  The checks now run at a mix of 0.6 and place a write on maps
    originated at frame 5, on both transports.
    **A differential check run only at an identity value (a gain of 1, an origin or offset of 0, a scale of 1) cannot see
    the term that applies it: run it at least once off the identity.**
362. **A SUITE THAT LOADS THE PAGE ONCE CAN TEST ONE BOOT** (Bubble Bobble, 2026-10-15, M10.3).  The page's default became
    the 128K, and Alt+M reboots it -- a new game object.  The suite's page is shared state: PAGE_RUN drives it once and
    keeps `P.game`, and every page row after reads what that drive left.  A block that rebooted it (to test the default, a
    remembered choice, the switch) would swap `P.game` under every block that runs after it -- in any order the mutation
    runner picks.  So the suite seeds the rig's store with the 48K BEFORE the load (the page every row before M10.3 was
    written for), and every other boot runs in a CHILD PROCESS: a fresh rig, a store as a browser holds it, the built page
    loaded, its result back as JSON (~0.7 s a load) -- which also tests what nothing in-process can: a RELOAD reading what
    the previous page saved.  (And the store's reader decides what a refusal can see: the kit's settingsStore turns an
    unparseable value into null, so it reads as empty, not refused.)
    **Never re-boot the suite's shared page in a block: test other boots in fresh processes, and pin the shared one's
    boot by its inputs before it loads.**
363. **A SUITE'S CHILD PROCESS IS INVISIBLE TO THE BATTERY'S SELECTION, AND A SECOND SUITE IS INVISIBLE TO THE BATTERY**
    (Bubble Bobble, 2026-10-15, M10.3).  platform.js's mix is gated by the kit's suite (test/kit.test.js, "THE MIX"), but
    the battery runs only bb.test.js and selects, per case, the blocks that ran the case's line IN ITS OWN PROCESS.  The
    hand battery had run the kit first, so all 30 platform cases died; run the battery's way (the M10.3 block alone) 15
    of them LIVED -- the AY level dropped, the replay of written registers, the window's cut a sample short, the late row
    uncounted, both maps' origins dropped: G5 / G7's end-to-end views cannot see them.  Now the block that runs the mix's
    lines here (G7) also runs the kit's suite in a child (G0), so the selection that picks the block for those lines
    brings the kit's checks with it; the lines only children run (reset(), start(): no AudioContext in the rig's process)
    stay hand-battery-only, out of the list, where they would be MISSES.
    The --affected run then said it a second way: 8 MISSES (killed only by the whole suite) -- the page's Alt+M path and
    the draw's flush line, whose kills are in G4 / G5's CHILD pages while the lines run in this process only under the
    48K page's drives in other blocks, which cannot see them.  G9 runs them in the M10.3 block, in this process, without
    rebooting the shared page (an Alt+M REPEAT, a plain M, one page frame).
    **Hand-test each case the battery's way (its suite, its selection) before the list goes in: a kill by another suite
    -- or by a child process -- is not a kill the battery will see.**
364. **A REBOOT IS NOT A RESTART, AND THE FIRST FLUSH IS NOT ALWAYS EMPTY** (Bubble Bobble, 2026-10-15, M10.3; the Sonnet
    review's finding).  SoundOut.reset() re-originated the stream and silenced the AY but left the beeper's level where
    the OLD machine left it, and the origin branch adopted a dropped log's level only on a restart (`next !== null`) --
    "the first flush has nothing logged yet" was true at page load, false after a reboot.  A speaker left high stayed
    high (silent, DC-blocked) until the new machine's first edge to 0 -- a full-scale click (1.04 before the gain)
    seconds after the switch, where a switched-off machine clicks at once.  Now reset() puts every chip at power-on (the
    speaker LOW, the AY instrument a fresh chip) and every origin adopts the dropped log's state.
    **When an API gains a "start again" path, re-read every branch that assumed it runs once.**
