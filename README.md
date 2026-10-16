# Bubble Bobble (ZX Spectrum, 1987) — faithful JavaScript port

A single-file browser reproduction of the ZX Spectrum *Bubble Bobble* published by
Firebird Software in 1987 and written by Software Creations: code **Mike Follin**, graphics
**Andrew R. Threlfall**, music **Tim Follin**, under licence from Taito. The tape holds one game
with two branches, and both are reproduced: the 48K game with its beeper, and the 128K branch
with its AY music -- the 128K by default, Alt+M for the other. Built with the Spectrum Port Kit
(`docs/PORTING-ZX-TO-JS.txt` is the method; `docs/TRAPS.md` the lessons).

## The public repository

The published repository (github.com/cookertron/BubbleBobble) holds the port's source (`web/`), the tools that
measured the original (`tools/`), the tests (`test/`) and the findings (`docs/`). Nothing taken from the tape is in it:
not the tape image, not `build/` (the decoded assets and the oracle fixtures, which carry the machine's own states and
screens), not the snapshots and not the built pages -- so the page cannot be built from it alone (`tools/build.py`
reads `build/*.json`). The one exception is the debug page, published as a ZIP on the Releases page so that people can
test the port: unzip it and open `bubble_bobble_debug.html` in a browser.

## Playing

Build the page (below) and open `web/bubble_bobble.html`; a double-click is fine. It boots as
the machine does, through the load's control select: each player picks KEYBOARD (and redefines
the keys), SINCLAIR, KEMPSTON or CURSOR (KEMPSTON reads nothing on the faithful page: see the
declared departures), and '1' or '2' at the title starts a one- or two-player game. The caption
under the screen names each player's keys and the machine running. The page's own keys are all
Alt+ combinations, and the letter in a combination never reaches the game as a Spectrum key:

| Keys | |
|---|---|
| Alt+P | pause, and resume (the game's own pause) |
| Alt+Q | end the game (the game's own BREAK) |
| Alt+M | reboot into the other machine, 128K or 48K (remembered) |
| Alt+Enter | fullscreen; Escape, or Alt+Enter again, to leave it |

The sound starts at the first key or click (the browser's rule). `__PORT__.sound.info()` in the
browser's console reports the audio path the page took.

## The debug page

`python tools/build_debug.py` builds a second page, `web/bubble_bobble_debug.html`: the faithful page with a debug
layer (`web/debug.js`) and a panel down its right-hand side, for reaching any part of the game without playing to it.
It is not the faithful page, and the build proves it both ways: the faithful page carries no trace of the layer, and the
debug page is the faithful page plus the layer, byte for byte. Every control works through the game's own mechanism,
entered at a point real play reaches, between two frames and never inside one; an action asked for while the game is
busy (a round starting, a cutscene, the pause) waits for its moment, and the panel says what it is waiting for.

| Panel | What it does |
|---|---|
| Speed | freeze and run (Alt+X), one frame (Alt+C), ¼x to 8x. Every step is one machine frame; the sound is muted off 1x |
| Round 1..81 | jump to that round (80 is the boss, 81 the treasure room): the game's own round advance builds it, in the colours and platform tiles a straight run from round 1 gives it. Asked at the title, the next game starts there |
| clear round | kill everything and skip only the clear's wait (Alt+N): the game's own next round, its treasure-room warp included |
| kill all enemies | every free enemy dies as the lightning storm kills, every bubble holding one bursts (Alt+K); the fruit, the clear and its wait are the game's |
| burst bubbles | every bubble, as the storm's last ticks burst them |
| Power-ups 0..15 | that power-up at the round's own spawn point; take it to get its effect |
| Food items 0..15 | that food item at the round's own spawn point, its value paid when taken |
| EXTEND | give a player a letter, or all six: the "N I C E" cutscene, a life and the next round |
| Players | +1 life (Alt+L), infinite lives, invincible (Alt+I: the invulnerability after a respawn, held on -- the player flashes) |
| Timer and boss | HURRY UP now, Baron von Blubba now; on round 80, the boss's HP to 1 or 0 |

Two things the game itself does that can look like a debug fault: a jump lands exactly on the round asked, so it holds
off the warp to the treasure room that entering round 20, 40 or 60 without a death gives (clear the rounds instead to
see it); and the blue bottle (power-up 13) sets the game's collect lock -- nothing is picked up after it until a death.
The browser's console has the same hands (`__PORT__.debug.status()`, `.jump(n)`, `.powerUp(t)` ...), and
`node test/debug.test.js` checks the page (about 7 minutes: it jumps to every round).

## Legal position (stated once, here)

The game's code, data, graphics, level designs and music are copyrighted works. This port is
a reimplementation studied from the owner's own tape image for interoperability; it is not
the original binary and executes no Z80 code. Even so, the extracted assets (`build/*.json`), the
oracle fixtures beside them (which carry the machine's states and screens) and the generated pages
`web/bubble_bobble.html` and `web/bubble_bobble_debug.html` come from the tape: none of them is in the public
repository, and `tape/`, `build/*.bin`, `*.pkl` and every snapshot are git-ignored. The one exception is the debug
page, published as a release ZIP so that the port can be tested. No Spectrum ROM is
shipped or transcribed; the real 48K ROM is used locally in the analysis harness only.

**Declared departure -- the HUD digits.**  The original draws its score digits
straight out of the 48K ROM character set (`$8042` computes
`$3C00 + (digit + $30) * 8`).  Since no ROM is shipped or transcribed, the port
draws them from ten 8x8 digits made for this port by `tools/make_digits.py`,
which refuses to emit unless every glyph differs from the ROM's -- 62 of the 80
bytes do.  The face is deliberately distinct: no interior diagonal on the zero,
a two-pixel stroke where the ROM uses one.  Everything else about the score
renderer is faithful and gated against the machine -- which cells it addresses,
the order it walks them, the eight-bit `INC H` down each glyph, and the
self-modified leading-zero suppressor at `$81BB`.  CONSEQUENCE: the HUD is not
pixel-identical to the original, so the frame-level differential in M8 must
exempt the score cells.

**Declared departure -- the EXTEND letters.**  A SECOND, independent ROM
font dependency, found in M7.7-H6 and confirmed from a second direction in H9.  Forty-nine of the 81 rounds carry an element
class at `$7E0E`, and on fifteen of them it is redrawn each build into one of
eight values that select an EXTEND letter.  `$BF74` takes the glyph for that
letter from a pointer table at `$C068` and ORs it into the flashing-bubble sprite
bank -- and for those eight classes the pointers are **ROM character-set cells**
(`$3E28`, `$3EC0`, `$3EA0`, `$3E70`, `$3E20`: `e`, `x`, `t`, `n`, `d`).  The three
fixed classes are unaffected: water, lightning and fire come from icons in the
game's own RAM at `$B614`/`$B61C`/`$B624`.

The SAME SIX ROM ADDRESSES appear again in `$95D5`, the table the collected-EXTEND
HUD row draws from (`$957E`) -- two unrelated tables naming the same cells, so one
substitute serves both.  `tools/make_letters.py` draws six 8x8 glyphs for this port
and refuses to emit unless every one differs from the ROM's; 36 of the 48 bytes do.
**And one of those overlays is not a letter at all.**  On the 31 rounds with no
element class the pointer arithmetic (`SUB 2 / ADD A,A`, eight-bit) runs 252 bytes
past its twelve-entry table and fetches `$05E0` -- eight bytes of ROM *code*, not
a glyph -- which the original nibble-splits into the flashing-bubble sprite bank.
Measured, that changes 99 of the bank's 384 bytes, so it is visible.  The port
reproduces the arithmetic exactly, overrun and all, and overlays nothing there.
CONSEQUENCE: on those 31 rounds the flashing bubble differs from the original's,
and M8's frame differential must exempt it.

As with the HUD digits, everything except the glyph pixels is faithful and gated:
which class each round gets, the eight-into-six fold that makes E and D twice as
likely as X, T and N, the overlay's position and stride, and -- for the HUD row --
which cells it addresses, that the second player's pass is reached by falling
through, the self-modified column offset at `$95AE`, and the 8 display + 8 shadow +
1 attribute written per set bit.  CONSEQUENCE: the frame-level differential in M8
must exempt those six cells as well as the score cells.

The
method, the tools and the engine source minus assets are publishable.

## Scope of "faithful" (decided 2026-09-06; manual 0.4)

| Reproduced | Status |
|---|---|
| Two-player simultaneous play | in scope |
| Every round (the tape holds 81 layouts) and the boss | in scope. MEASURED: there is no ending sequence -- past the last round the game goes on at a random round between 30 and 61 (`docs/SPEC.md`, the round advance `$97F8`) |
| The title screen and the high score | in scope. MEASURED: there is no attract mode -- the title's wait has exactly two exits, '1' and '2', and 16,749 frames left alone never leave it -- and one high score, with no table and no name entry |
| The control-options screen and key redefinition | in scope |
| The 128K version: its AY music and its own flow | in scope (M10, 2026-10-13..15): the page's default machine |
| The Bleepload loading sequence and its "Loading xx" counter | out (the loader is not the game) |

## Declared departures from the original

- **The control select is the original's, all four options** (decided 2026-09-28, revising
  the first plan of keyboard and gamepad only). SINCLAIR and CURSOR are keyboard layouts on the
  real machine (keys 6-7-9-0 and 5-8-0-7), so they work as they are; KEMPSTON reads the Kempston
  port, and on the faithful path nothing drives it -- controllers are a later, declared layer
  (the owner, 2026-09-28). **Wired in M7.64:** the page boots through the load -- player 1's and
  player 2's passes, the redefine screen, the black screen and the hand-over into the title -- and is
  diffed frame for frame against the machine from the load to the title.  Where a screen is drawn, the port
  draws it at once as its time begins (the machine draws it over that time, up to 3.5 frames), the
  one departure inside it (`BB_REDEF.DEPARTS`).  The redefine screen's echo prints nine codes the
  substitute font did not have (`> ? @ J Q X Z ] _`), drawn to the same no-ROM rule.
- **No Kempston interface on the faithful page** (`padKempston`, ADDED, default OFF). The page's
  gamepad reading is not fed to the Kempston port, so a player who takes KEMPSTON reads nothing and
  cannot move -- a Spectrum with no interface fitted. Controllers are a later, declared layer; with
  the flag ON a pad drives the port. The key caption says so when a pad is connected.
- **The key caption during the load** (ADDED page furniture) says what the control select asks for;
  the game's key table is only copied into place at the hand-over, and from the title on the caption
  decodes it as before.
- **The 5-second black screen at load is skipped by default.** After the control select the
  original runs a ~5.1-second timing test (`$FAC3`, the 48K/128K probe) on a black screen; in a
  browser that reads as a hang, so the port skips it behind a named flag (`skipProbe`, default
  ON; built M7.63), answering as the machine does with the keys up. The faithful wait is kept in
  code and tested cycle by cycle against the machine. On the 128K the skip waits for the probe's
  own phase before it answers, so the cold start that follows is the machine's (M10.2a).
- **A key held ~23 frames of that black screen sends a real 48K down the 128K branch** (the
  probe miscounts; measured: 'A' held 22 frames is fine, 23 is not). On a 48K that branch copies
  the 128K sound engine over the sprites -- the port does not model it: on the 48K machine with
  the flag off, it counts the event (`probe128`) and continues as a 48K. The same goes for the
  undocumented cheat (player 2 redefines with 'R' and passes a checksum, then A+D+G held at the
  end of the black screen: it rewrites the enemies' types), reachable on a 48K only on that
  branch: counted, not modelled.
- **The black screen's clear is timed by a law of the frame phase**: where a
  frame interrupt lands inside the black screen's clear the port's timing can differ from the
  machine's by up to ~1,500 T-states (measured).
- **The timing is the machine's where it is measured, and the rest is declared.** The first plan
  (2026-09-06) declared the slowdown a gap: a fixed step where the original drops frames. Measured,
  the machine drops no video frame -- its slowdown is fewer main-loop passes in a busy frame, and
  an interrupt whose work overruns its frame loses the next one (0.55% of interrupts overrun, the
  worst by 10,088 T: `docs/TIMING.md`, item 9). So the port runs the 48K's frame clock -- 69,888 T
  a frame at 50.08 Hz -- and charges every main-loop pass and every frame interrupt its T-states,
  measured routine by routine and access by access; its slowdown is the machine's, a full pool's
  pop wave overrunning where the machine's does. Free-running from the load into play, the port's
  passes and interrupts are the machine's to the T over the windows the gates measure (the real
  load's 380 interrupts and 2,565 passes through round 1's start into its play; rounds 3, 17 and
  25 from frame 998 to frame 1,700, their `LD A,R` draws fed from the machine). The owner stopped
  the timing campaign on 2026-10-12, so the gaps left are DECLARED in `docs/TIMING.md` ("Still
  DECLARED"), among them: the lives panel and the corpse flight inside the odd interrupt and the
  boss's draws in an interrupt (off the interrupt's access program); the fitted contention of
  EXTEND's completion and the storm (within about 6,000 T of the machine's, under a tenth of a
  frame); the acceptance constant where a block has no instruction grid; and a pass with CAPS
  SHIFT held, 22 T short (`docs/TRAPS.md` #357).
- **Completed frames only.** Each frame's finished display file is shown; the original's
  mid-frame tearing is not reproduced.
- **The eleven `LD A,R` draws come from a declared substitute** (`docs/RNG.md`). The game's main
  generator at `$FE85` carries nearly all of its randomness and is reproduced byte for byte; the
  refresh register R, which a few sites read, cannot be reproduced exactly (measured infeasible),
  so those sites draw from per-site streams seeded from `$FE85` at the start press. The
  differences are quantified in `docs/RNG.md`, "Declared gaps".
- **The high score is kept between visits** (`BB_PAGE.saveHiScore`, ADDED, default ON; M9.1). The
  original has one high score and sets it to 20,000 at every load; the page saves a new high score in
  the browser (localStorage, key `bb-hiscores`) and lays it over that default at the next load's cold
  start. With the flag off the page is the machine; nothing else of the game reads or writes the store.
- **Alt+Enter fullscreen** (ADDED page furniture; M9.1): the Spectrum's border and screen on the whole
  screen at a whole-number pixel scale; Escape, or Alt+Enter again, brings the page back. The game
  never sees the key (ENTER is a Spectrum key: Alt+Enter is stopped before the keyboard reads it).
- **Alt+P pauses, Alt+Q quits** (`BB_PAGE.altKeys`, ADDED, default ON; M9.2 -- the owner's: the page's key combos
  are Alt+). The original pauses on SYMBOL SHIFT, resumes on CAPS SHIFT and ends a game on CAPS SHIFT + SPACE
  (BREAK) -- on a PC keyboard Ctrl, Shift and Shift+Space. With the flag on, Alt+P toggles the game's own pause
  and Alt+Q quits through the game's own BREAK (the page holds those Spectrum keys until the game has taken
  them), and the PC's own Shift and Ctrl no longer reach the game outside the control select, so nothing pauses,
  resumes or quits by accident. The control select's menus keep the original keys. Neither combo ever presses
  the Spectrum's P or Q. With the flag off the keys are the original's.
- **The 128K machine is the page's default** (`BB_PAGE.m128`, ON; M10 -- the owner's decision of
  2026-10-13). The probe at `$FAC3` decides which machine the game is on. On a 128K the cold start
  copies the AY music engine into memory bank 1 and the game drives it from every frame
  interrupt, and the 128K version plays differently as well: at six places it waits for the
  current tune to end before it asks for the next. The cold start waits 81 frames for its
  jingle before the title; round 1 starts with every enemy standing still for 4.4 seconds while
  the player can already move; EXTEND's cutscene runs about 3.7 seconds longer; the treasure room
  and the boss's defeat wait too. The page runs that branch as it is, waits and all
  (`docs/M10-PLAN.md`, option A), gated against the machine frame for frame; with the flag off it
  is the 48K page as before. Declared:
  - **The 48K's clock.** The branch runs on the 48K machine's clock -- a 69,888-T frame at 50.08 Hz
    on a 3.5 MHz CPU, the 48K's contention and its 32-T interrupt -- not the 128K's own (70,908 T
    at 50.02 Hz on 3.5469 MHz, contended on 228-T lines from T 14,361, a 36-T interrupt), nor the
    128K's contention of bank 1 itself and of the AY's port writes while it is paged in. Each
    difference is within about 2% and the net game speed is probably within about 1% (inferred,
    not measured); the tunes are in pitch and 0.12% fast. Re-timing the game on the 128K's clock
    was rejected (`docs/M10-PLAN.md` (C)): it would re-run the whole timing model for differences
    no player hears.
  - **The probe's answer is forced.** Run on the 48K clock, the probe would count a 48K; on the
    128K page its count is the 128K's (`$0759`, measured on the 128K machine), set where the probe
    reads it (`$FAE1`).
  - **The AY's sound.** Every AY write is the machine's, made at its own T-state; the sound the
    chip makes is the kit's AY model (16 levels at 2^(-1/4) a step, a 1.7734 MHz clock), played in
    one stream with the beeper. How loud the AY was against the beeper on a real 128K is analogue
    (the modulator, the TV), which no simulator measures: `AY_MIX` in `web/platform.js` sets it,
    PROVISIONAL at 1.0 until the owner's listening test (live: `__PORT__.sound.ayMix = x`).
  - **No ULA snow.** With the I register at `$FC` and the contended bank 1 paged in, 29% of the
    engine's ticks overlap the display, where a real 128K can show snow; the port shows none.
- **Alt+M switches the machine** (ADDED page furniture; M10.3). It reboots into the other machine
  at the control select -- the game in progress is gone, as when a real machine is switched off --
  and the caption names the machine running ("128K machine (Alt+M: the 48K)"). The choice is
  remembered in the browser (`BB_PAGE.saveMachine`, ADDED, default ON; key `bb-machine`); with the
  flag off, Alt+M still switches for the page's life.
- Anything else the port invents is named in `docs/NOTES.md` under "own inventions".

## Layout

See `CLAUDE.md` for the house rules and `tools/README.md` for the tool-to-phase map.
`docs/STATUS.md` is where the port stands, `docs/LOADER.md` the phase 1-2 record,
`docs/SPEC.md` the behavioural spec with addresses, `docs/TIMING.md` the frame-timing model and
its declared gaps, `docs/RNG.md` the generators, `docs/M10-PLAN.md` the 128K branch, and
`docs/NOTES.md` the provenance record (checklist, routine map, assumptions, open items).

## Build and test

```
python tools/selftest.py            # the kit's tools' own gate
python tools/build.py               # port.json -> web/bubble_bobble.html
node test/kit.test.js               # the platform runtime's checks, against the BUILT page
node test/bb.test.js                # the game's checks, against the BUILT page (~7 minutes)
python tools/build_debug.py         # the debug page: the built page + web/debug.js
node test/debug.test.js             # the debug page's checks (~7 minutes)
python tools/mutants.py --jobs 20   # the mutation battery (--affected after a change)
```

The analysis tools (`tools/*.py`) need the owner's tape in `tape/`, which is git-ignored.
