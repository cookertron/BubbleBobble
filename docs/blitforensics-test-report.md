# blitforensics.py -- validation for the Spectrum Port Kit (2026-09-07)

Prompt: `docs/blitforensics-test-prompt.md`.  Tool under test: `tools/blitforensics.py`
(with `screen.bmp_coords`).  Oracle discipline: measure, don't assume; every claim
mutation-tested; a wrong-but-silent answer is a FAIL.

**Verdict: PASS after seven fixes.  Upstreamed** (kit branched from `bca29d9`; second round,
Chuckie Egg 2 + Gauntlet + the model check, on top of `27c39c0`).

The tool as drafted (port `3e60057`) got the anchor right but had three silent-wrong /
crash paths that a second game hit on its first run; the rewrite keeps the method and
the output format, adds a `measure()` core the selftest calls in-process, and turns each
of them into a stated failure.  Scratch material (states, mutants, logs) stayed in the
session scratchpad; nothing tape-derived was added to either repository.

| Section | Result | Evidence |
|---|---|---|
| A synthetic gold gate | PASS | 3 poked blitters recovered cell for cell; 4/4 gate mutations fail as they must |
| B real-blitter anchors | PASS | Bubble Bobble `$A600` 16x16 MASKED, bytes identical before/after the rewrite; Chuckie Egg `$929C` 16x16 OR-blit == its 32 source bytes; Chuckie Egg 2 `$8063` draw == its 32 source bytes and `$7FC9` erase pass read correctly, both as the port's notes document them; Gauntlet's three `JP (IX)` shadow-screen blitters at the sizes `blittrace.py` documents |
| B model check | PASS | a third run over the real background: `(bg AND mask) OR data` reproduces every byte on all four games (mismatch 0 at 10 entries) |
| C adversarial limits | PASS after fixes | C1 bound, C3 back-buffer, C5 attr clip were silent/crash in the draft; now refused / measured / counted |
| D determinism | PASS | JSON and PNG byte-identical on two runs |
| Tool mutation battery | 12/12 caught by the selftest gate (port); 9/9 on the kit copy | |

## Defects found in the draft (all fixed)

1. **Silent wrong bound (C1).**  The word at (SP) was taken as the return address with no
   check, and the run's end reason (`limit`) was ignored.  A fall-through/JP entry, or a hook
   placed after a PUSH, ran the two "calls" for 200,000 steps into whatever followed and
   reported the result as one blit, exit 0.  Synthetic repro: `JP $8000` with `$1234` on the
   stack -> `blit @$8000 -> return $1234 ... MASKED 8x8`, rc 0.
   Fix: a CALL nn / CALL cc,nn / RST must precede the stack-top word (checked by opcode;
   the CALL's target need not be `--entry`, since Bubble Bobble reaches `$A600` by
   `CALL $A447 ... JR C,$A600`), else exit 3 naming the cause; `--ret 0xADDR` overrides;
   if either run does not reach the bound within `--steps` the tool says so and exits 3.
2. **`--target LO HI` at a back-buffer never recovered anything (C3).**  The bitmap filter
   was hard-wired to `a < $5800` and geometry to base `$4000`, so a buffer at `$C000`/`$D000`
   printed "no bitmap writes ... try --target at that buffer" even with `--target` at that
   buffer.  Fix: the first `$1800` bytes of the target are the bitmap (ULA layout, base LO),
   the next `$300` its attributes; the default region is unchanged.
3. **Crash on attribute writes inside the target (C5b, and every Chuckie Egg sprite routine).**
   The draw-order sort looked up attr addresses in the bitmap coordinate table:
   `KeyError: 22528`.  Fix: attrs are counted, not sorted.
4. **Bogus XOR label for an all-transparent result (C5e).**  data 0 / mask `$FF` satisfies
   the XOR test trivially.  Fix: a result that is background over both fills is `EMPTY`,
   with a note that masked-empty and XOR-of-nothing are indistinguishable.
5. `--out` into a directory that does not exist raised `FileNotFoundError`; now created.
6. **Crash on a `$0000` stack top (Gauntlet).**  Its blitters are entered by JP with `$0000`
   under SP and leave by `JP (IX)`; the bound check peeked at `ret - 3 = -3` and died with
   `IndexError`.  Fix: nothing can precede `$0000-$0002`, so it is refused like any other
   non-return; and `--ret` now accepts a register name (`--ret IX`) for exactly this shape.
7. **No falsifier for the mask model.**  Two backgrounds fit ANY routine of the form
   `f(bg, src)` to a mask+data pair; nothing said whether that pair was the routine.  Added a
   THIRD run over the real background: every written byte must equal
   `(bg AND over-$FF) OR over-$00` (or `bg XOR data` for XOR), else `MODEL MISMATCH` names the
   addresses and disowns the grid.  Witness in the selftest: `LD A,(DE) / CPL / AND (HL)`
   (`data AND NOT bg`) reads as MASKED and is flagged; the three family routines are not.

## Section A -- synthetic gold gate (tape-free)

State: `Harness(snapshot=False, deck=False)` (ROM + blank RAM), routine at `$8000`, caller
`CD 00 80 18 FE` at `$9000` (`CALL $8000 / JR $`), source at `$A000`, `B`=8, `HL`=`$A000`,
`DE`=`$4820` (x 0, y 72), `SP`=`$FF00`, IFF 0, saved with `save_state_file`.  Sprite:
`DATA = 3C 42 81 A5 A5 81 42 3C`; AND-mask (1 = transparent)
`MASK = C3 81 00 18 3C 00 81 C3` -- transparent in some clear-data pixels, opaque black in
others, and row 4 overlaps set data bits.  Command per case:

```
python tools/blitforensics.py --state <scratch>/a1_masked.pkl --entry 0x8000 --target 0x4000 0x5B00 --out <scratch>/out/a1_masked
```

| Case | Routine | Expect | Got |
|---|---|---|---|
| A1 masked-OR | `1A A6 23 B6 23 12 14 10 F7 C9` | MASKED, over-$00 == DATA, over-$FF == MASK OR DATA, transparent iff mask=1 & data=0 | all equal; return `$9003`, origin (0,72), 8x8 |
| A2 opaque | `7E 12 23 14 10 FA C9` | OPAQUE, both backgrounds == DATA, zero transparency | all equal |
| A3 XOR | `1A AE 12 23 14 10 F9 C9` | XOR flagged, over-$00 == DATA, over-$FF == ~DATA, no mask claimed | all equal; "(XOR blitter: ... a transparency mask is not observable by this method.)" printed |

A1 ASCII (`#` ink, `.` opaque black, space transparent):

```
  ####  
 #....# 
#......#
#.#  #.#
#.#  #.#
#......#
 #....# 
  ####  
```

Gate mutations (each must make the gate FAIL):

| Mutation | Gate result |
|---|---|
| data row 2 `$81` -> `$83` | FAIL on data, over-$FF and grid (row 2 `IKKKKKII`) |
| mask row 3 `$18` -> `$1A` (a clear-data bit) | FAIL on over-$FF and grid |
| opaque routine replaced by the XOR routine | FAIL: mode `XOR`, want `OPAQUE` |
| masked routine `OR (HL)` -> `XOR (HL)` | FAIL on over-$FF (row 4 `$99` not `$BD`); grid unchanged, so the gate must check over-$FF, which it does |

One mutation I first wrote (mask row 3 `$18` -> `$1C`) did **not** fail: bit 2 is a set data
bit, and the OR after the AND makes data win, so the change is unobservable by construction.
Replaced by a clear-data bit; recorded here because it is exactly the kind of mutation that
looks like a tool weakness and is not.

The gate is `t_blitforensics` in `tools/selftest.py` (port 34/34, kit 34/34).  It calls
`blitforensics.measure()` in-process on the three routines plus the guards below.

## Section B -- real blitter anchors

**Bubble Bobble** (`--state round1 --entry 0xA600 --skip 1`): `return $A405`, `16x16 px
(2x2 chars, 32 bitmap bytes)`, `MASKED`, row-major top-down, the rounded creature with two
eyes and a transparent left border.  `data_over_00` and `over_FF` from the rewritten tool are
equal to the draft tool's (compared JSON to JSON).  `steps [285, 285, 285]` (the third is the model-check run).

**Chuckie Egg** (scratch manifest, state `ce_play2`; writers found with `blitprobe.py`,
CALL entries by scanning for `CD lo hi` into each writer's routine):

| Entry | Result | Reading |
|---|---|---|
| `$929C` skip 1 | `return $9225`, 16x16, 32 bmp + 6 attr bytes, MASKED, custom order | the player; mask == ~data everywhere, i.e. an OR-only blit (`OR (HL)` at `$930D`) |
| `$929C` skip 0 / 2 | 16x24, 48 bmp + 6 attr, OPAQUE, "fully solid" warning | the same routine redrawing a ladder cell opaquely: the warning is right, this hit is not the sprite |
| `$9A4C` | `return $9DC1`, 24x16, OPAQUE, warning | the caged duck, opaque copy from `$72A0` |
| `$A1B8` | `return $98F9`, 24x8, OPAQUE, warning | three score digits `000` |

Cross-check for `$929C` skip 1: stepping the same call and recording every `LD A,(DE)` at
`$9308`/`$9310` gives 32 source reads from `$9070-$908F`; the multiset of recovered bytes
equals the multiset of source bytes, and the source rendered row-major (2 bytes x 16 rows,
also `contact.py --base 0x9070 --len 0x20 --w 2 --h 16`) is identical to the tool's grid,
row for row.

Before the fix every one of these Chuckie Egg entries crashed with `KeyError` (defect 3),
because each routine also writes the six attribute cells under the sprite.

**Chuckie Egg 2** (scratch manifest from the probe session, state `ce2_play3`; writers from
`blitprobe.py`, CALL entries by the same `CD lo hi` scan):

| Entry | Result | Reading |
|---|---|---|
| `$8063` | `return $7EF0`, 16x16, 32 bmp + 4 attr, MASKED, row-major | the farmer, OR-blit (`OR (HL)` at `$80A7`) |
| `$7FC9` skip 0/2 | `return $7EED`, 16x16, MASKED, custom order | the ERASE pass: `LD A,(DE) / CPL / AND (HL) / EXX / OR (HL)` = `(screen AND NOT sprite) OR background`; the grid's opaque-black cells are the farmer silhouette being cleared, its ink the floor tile restored |
| `$7FC9` skip 1 | 24x16, MASKED | the same pass on a 3-cell-wide object |
| `$7F4F` | `return $8FE2`, 8x56, OPAQUE, warning | an opaque column (the four lift rooms' path, per the port's audit) |
| `$7E91` | "entry $7E91 not reached (hit 0/0; limit)" | not hit in 4M steps without keys: a clean miss |

Cross-check: the 32 source reads at `$80A6` during the `$8063` call come from `$DFB6-$DFD5`;
their multiset equals the recovered bytes and, rendered row-major 2 bytes/row, equals the tool's
grid row for row.  The port's own notes (`notes/entity-record.md`, `phase10-audit-and-spec.md`)
name `$8063` "the ordinary OR-blitter" and `$7FC9` "erase, reading the previous screen address"
-- the tool reached both readings blind.

**Gauntlet** (port at `E:\software\Gauntlet`, state `_my_lvl8`, scratch manifest with
`states` at its build dir).  Its `blittrace.py` documents three blitters that compute the
attribute address as `$D8 | ...` and so can only target the shadow screen at `$C000/$D800`,
and end in `JP (IX)`:

| Entry | Command | Result | Documented |
|---|---|---|---|
| `$9DD2` | `--ret IX --target 0xC000 0xDB00` | 16x16, 32 bmp + 4 attr, OPAQUE, 106 steps | 16 px x 16 rows, 2x2 attribute cells |
| `$9E4B` | same | 8x16, 16 bmp + 2 attr, OPAQUE, row-major | 8 px x 16 rows, 2x1 cells |
| `$9EA0` | same | 16x8, 16 bmp + 2 attr, OPAQUE | 16 px x 8 rows, 1x2 cells |

Without `--ret`: "the word at (SP=$E295) is $0000, and no CALL/RST precedes it" (exit 3; the
draft crashed here).  With `--ret IX` but the default target: "no bitmap writes in
[4000,5B00) ... try --target at that buffer" (exit 2).  All three are OPAQUE, which is what a
tile-composed dungeon over black floors should be; the "fully solid" warning fires and is
advisory.  Model mismatch 0 on all three.

**Model check across the games** (`model_mismatch` in the JSON; 0 = every byte written over
the real background equals `(bg AND mask) OR data`): Bubble Bobble `$A600` 0/32; Chuckie Egg
`$929C` skip 0 0/48, skip 1 0/32, `$9A4C` 0/48; Chuckie Egg 2 `$8063` 0/32, `$7FC9` 0/32,
`$7F4F` 0/56; Gauntlet `$9DD2` 0/32, `$9E4B` 0/16, `$9EA0` 0/16.

## Section C -- adversarial / documented limits

| Case | Setup | Draft tool | Rewritten tool |
|---|---|---|---|
| C1a fall-through | `JP $8000`, stack top `$1234` | silent: `return $1234`, MASKED 8x8, rc 0 | exit 3: "the word at (SP=$FF00) is $1234, and no CALL/RST precedes it ... or pass --ret 0xADDR" |
| C1b hooked after PUSH | `PUSH HL` at `$8000`, `--entry 0x8001` | silent: `return $A000`, rc 0 | exit 3, same guard |
| C1c `--ret 0x9003` on C1b | | | MASKED 8x8, grid == poked sprite |
| C1d wrong `--ret 0x9010` | | | exit 3: "the call did not return to $9010 within 200000 steps (limit/limit); the writes are NOT one call" |
| C2 background restore | `LDIR $C000->$4000 x $1800` then the masked blit | warning printed | `256x192 ... OPAQUE` + "! fully solid with zero transparency -- may be a background-restore ..." |
| C3a back-buffer, default target | blit to `$D820` | "no bitmap writes ... try --target at that buffer", exit 2 | same |
| C3b `--target 0xD000 0xEB00` | | "no bitmap writes", exit 2 (defect 2) | MASKED 8x8, origin (0,72), grid == poked sprite |
| C4 animation counter | routine reads `($C000)` to pick the frame and increments it | both runs draw frame 0 | same (`h.load_state(saved)` between runs; mutant without it: over-$FF all `$FF`, gate FAIL) |
| C5a two cells tall | 16-row opaque with the ULA pixel-down carry at `$4820` | 8x16 row-major | same |
| C5b bottom clip | same at `$50E0` (y 184) | `KeyError: 22528` | `8x8 ... 3 attr bytes`, origin (0,184) |
| C5c right edge | at `$483F` | 8x8 origin (248,72) | same |
| C5d attribute-only | 4 bytes at `$5880` | "no bitmap writes ... attrs touched: 4", exit 2 | same, plus "other bytes in target: 0" |
| C5e all-transparent | data 0, mask `$FF` | `XOR` (defect 4) | `EMPTY` + "no mode is claimed -- try another --skip" |

A limit that remains a limit, now stated in the docstring: the target's bitmap is assumed to
be in ULA display layout with base LO.  A linear or otherwise laid-out back-buffer would get
wrong sizes and grids; the tool does not detect that.  The bound check is a plausibility test
(any CALL/RST opcode before the stack-top word), not proof; `--ret` is the override.

## Section D -- determinism

`--state round1 --entry 0xA600 --skip 1 --src IX --out bb_n1` then `... --out bb_n2`:
`cmp` on the two JSON files and on the two PNGs reports no difference (md5 of both JSONs
`bf377a2f...` before the rewrite; identical pairs again after it).

## Tool mutation battery

Mutants written beside the tool (so imports resolve -- the first battery run wrote them to
the scratch directory, every mutant died on `import portconfig`, every row failed, and it
read as "all caught"; invalidated and re-run) and driven through the same synthetic cases:

| Mutant | Caught by |
|---|---|
| no `load_state` between the two runs | A1-A3, C4 |
| bound check accepts any stack top | C1a, C1b |
| + never-returned guard removed (= the draft tool) | C1a, C1b, C1d |
| OPAQUE/MASKED labels swapped | A1, A2 |
| geometry base fixed at `$4000` | C3b (only once the buffer moved to `$D000`: at `$C000` the address bits the layout ignores made the mutation unobservable) |
| attr writes left in the draw order | C5b (KeyError) |
| XOR detection dropped | A3 |
| EMPTY detection dropped | C5e |
| transparent bits ignored in the grid | A1 grid |
| model check disabled | the `data AND NOT bg` witness no longer flagged |
| third run over the `$00` fill instead of the real background | "masked over a real background: model holds" |
| `ret < 3` guard removed | `IndexError` on the `$0000` stack top case |

The same twelve breakages against `tools/selftest.py` turn `t_blitforensics` red every time;
restored, 34/34.  On the kit copy, nine of them: 9/9 caught, 34/34 restored.

## Upstream

Kit HEAD before: `bca29d9` (first round), `27c39c0` (second).  Added `tools/blitforensics.py` (LF; identical to the port's
modulo line endings), `bmp_coords` in `tools/screen.py`, the README row (phase 5), and
`t_blitforensics` in `tools/selftest.py`.  Kit gate 34/34.  The synthetic case pokes its own
bytes; no game sprite data went into the kit.
