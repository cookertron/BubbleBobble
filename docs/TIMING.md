# The frame-timing model

Third version.  The first was wrong by a factor of 19 (TRAPS #35).  The second
replaced it with measured per-item costs but kept one deliberately inexact term,
`BB_ISR_UNMODELLED_ODD = 20900 T`.  This version retires that term, and the
reason it could be retired is the point of the record.

The measurement was a 16-agent pass (2026-09-12): five components measured
independently with control-flow brackets, each attacked on two adversarial
lenses -- bracket soundness and prediction on held-out scenes -- then a
synthesis that had to verify its own arithmetic by running it.  12,620
bracketed interrupts across 49 states.  The previous version of this document
is in git history; everything below supersedes it.

## The headline

**`BB_ISR_UNMODELLED_ODD` was never a measurement gap.  It was the cost of the
enemies the engine does not simulate.**

That distinction matters because the two have different futures.  A measurement
gap shrinks when you measure harder.  This term shrinks only when the ENGINE
grows, and it has a defined way to reach zero: when `$FD80` holds what the
machine's holds, it is zero by construction.  Measured directly, the absent
population costs 12,871-39,131 T per odd interrupt, or 3,138-8,467 T per absent
enemy (median 5,422).  20,900 sat in the middle of that band because that is
what it always was -- correctly sized, wrongly named, and with no way to know
when it should stop being needed.

## The parts tile the whole

Every claim here rests on one property, and it is a partition rather than a fit:

    TOTAL($8D72 .. the RET at $8DA1)
      = SKELETON(parity, gate) + A3AD($A3AD .. its RET) + AA60($AA60 .. its RET)      [odd]
      = SKELETON(parity, gate) + B62C($B62C .. its RET)                               [even]

`build/isrcost_fixture.json` holds 450 interrupts from five branch-checked 48K
states in which `TOTAL - SKELETON - parts` is **exactly 0 on 450 of 450**.  The
workflow's own battery got the same over 12,620.  Each bracket is control flow
only -- an entry address to the matching RET -- and the two halves are bracketed
to `$8D8F`, the address they both actually return to, rather than by subtracting
an epilogue constant, which is what a first attempt did and it was 6 T out.

## The skeleton, by segment

Three independent brackets, zero variance, one of which single-steps and
VALIDATES the `$8DA1` terminator rather than assuming it:

| segment | T | |
|---|---|---|
| PROLOGUE | 130 | `$8D72` DI + eleven pushes |
| COUNTERS | 91 | `CALL $8DB5`, the two 16-bit frame counters |
| BRANCH_ODD / BRANCH_EVEN | 41 / 46 | push the return address, `RR L`, branch |
| GATE_OPEN / GATE_CLOSED | 22 / 28 | the `$FEC4` / `$FEC5` test |
| EPILOGUE | 157 | `CALL $8DC4` (a bare RET on 48K), eleven pops, EI, RET |
| CALL_A3AD / JP_AA60 / JP_B62C | 17 / 10 / 10 | the handoffs |
| B62C_TOGGLE | 27 | belongs to the MANAGER, not the skeleton |

    GATE_CLOSED_ODD  = 130+91+41+28+157            = 447
    GATE_CLOSED_EVEN = 130+91+46+28+157            = 452
    ODD_OVERHEAD     = 130+91+41+22+157 + 17+10    = 468
    EVEN_OVERHEAD    = 130+91+46+22+157 + 10       = 456

**Two corrections to the numbers this replaces.**  `ODD_OVERHEAD` was 441, which
excluded its own 27 T handoff.  `EVEN_OVERHEAD` was 483, which SWALLOWED the 27 T
`$B62C` toggle that belongs to the manager; the committed `483 + 184 + 1184 =
1851` tiled only because `SLOT_SCAN 1184` excluded the same 27 T.  Using 483
alongside a structural manager model would double-count it on every even frame.

## `$A3AD`, and why the engine can now charge it itself

The render pass is a closed function of the entity table, `$AA57` and the `$FD00`
row table -- verified independent of sprite and display CONTENT by scrambling
`$4000-$5AFF` and getting a bit-identical cost.  Since M7.3b the engine runs the
real pass, so it can charge the real cost as it goes:

    523 + 61 x SWEEPS
      + per VISIT: 188 + TESTS + (0 if skipped else 20 + (17 if bit5 clear else 10)) + A447
      + 4 x BEAM_CARRIES

TESTS is the window test run in order on `(IY+6)`, `+$10`, `(IY+2)`, `+$10` with
loads 19/7/19/7 plus CALL 17, and a body of 22 (at or above the window top), 34
(below the top and below the base) or 39 (inside -- the visit stops here).  A447
is 151 (bit7 clear) or 171 (bit3 set), else ERASE + FLASH + DRAW, where ERASE is
0 (bit6 clear), 36 (cached Y >= `$C0`), 1256/1348/1346 aligned or 2873/2951/2953
shifted by the cached row's geometry, DRAW is 2016/2052 aligned or 2716/2752
shifted, and FLASH is 94/103/83 on toggle phase 0 -- or a return at 305/314 when
the player's invulnerability bit is set, in which case the erase has happened and
the draw has not.

MEASURED against the 450-interrupt fixture: **the engine never charges MORE than
the machine on any of the 205 odd interrupts**, is EXACT on 88 of them, and is
exact on 45 of 45 for one state.  The shortfall on the rest is ULA CONTENTION,
which the port does not model and never claimed to -- and contention can only
ADD, which is why the gate asserts the direction rather than a tolerance.

## What the engine computes now

    odd  = ACK + ODD_OVERHEAD + (what the passes charged themselves)
    even = ACK + EVEN_OVERHEAD + (what $B62C charged itself)          [M7.73]

**M7.68 retired `BB_ISR_ABSENT_AA60` and charged the acknowledge.**

- `BB_ISR_ACK = 41`: the IM2 response (19 T), the JR at `$FFFF` (12) and the JP at `$FFF4` (10)
  that come BEFORE `$8D72` on every accepted interrupt.  The bracket above starts at `$8D72`, so the
  ledger had been giving the main line 41 T a frame it never has.  Every oracle that derives main-line
  T already subtracted 488 / 493 per gate-closed interrupt; now the ledger spends the same.  Under the
  round banner every even interrupt was exactly 41 T short of the machine's (BT3) and is now exact;
  the hurry block's interrupt points are within 12 T of the machine's at all 42 (were walking 41 T a
  frame).  `BB_INT_PHASE` is the `$8D72` entry, so the span test takes the 41 back out.
- `$AA60` charges itself (`tools/aa60cost.py`, `build/aa60cost_fixture.json`): prologue + slots tile
  the bracket on all 5,974 passes of 48 states, and each slot is SKELETON + handler runs + corpse
  flight.  The skeleton is instruction sums -- `BB_AA60`: prologue 150 (+2 on the cadence wrap), slot
  top 130, a ticked delay 57 / 68 / 98 (slot 0 / slot 1 / `(IY+9)` = `$FF`) or 103 asleep, inactive
  74, frozen 122 (+7 when the corpse CALL is taken), live 253 (+5 tracking P2, -2 doubled), then 73 +
  the tail 150 (+14 an X clamp, +25 a Y in `$C8..$DB`, +21 a Y at or past `$DC`), and 10 for the last
  RET -- EXACT on every slot of 134 recorded passes, three of them FORCED (P2 tracking, a corpse with
  its delay running, a high Y).  The handlers (`$AB38` and the eight enemy types) and the corpse flight
  `$8A78` are charged their MEDIAN run T over the fixture (`BB_AA60_RUN`, `BB_AA60_CORPSE`), contended:
  PROVISIONAL, reported every frame as `frameLedger().aa60.prov`, and a handler with no median is
  charged the player's and counted (`aa60Unpriced`).  The diverted pass is its instruction sums too
  (`BB_AA60_DIVERT`: head 84 (+2), `$B520` 75, slots 72 / 109 / 127, the last DJNZ -5, RET 10), exact
  on all 504 uncontended diverted passes, where a fitted BASE of 165 stood.
- Result under the round banner (BT3): the late odd interrupts went from 4,070..4,087 T LONG (1P) and
  2,237..2,245 (2P) to 22..39 and -26..-16; the interrupt points' drift at the banner's end from
  17,966 / 8,057 T to 605 / 1,421.  What is left on the odd side is the handlers' provisional T and
  contention (the settle window's `$73A6` reads and `$A3AD`'s writes).

**M7.69: the player's runs charge their own T.**  `tools/ab38cost.py` records every `$AB38` run
UNCONTENDED (7,205 runs, 346 natural paths, 17 forced) and `BB_AB38` holds the instruction sums of
every arm -- the death tick and its respawn (the lives panel `$806C` per cell, the calm `$90C1` per slot,
the final death's forced erase `$BF0A` around `BB_A3AD`'s class), the invulnerability, the key reader
on keys and on Kempston, the air rule, the blow cadence, `$ADAA`'s move tree (`adaaT`), the floor probe
(`probeT`), the floor tick, the arc, the bubble-jump.  The engine adds them on its own branch decisions
and AB1 holds it to the machine's T, exact, on all 882 kept runs.  Instructions no run reaches -- `$ADA9`
(dead after a JP) and `$AF2C..$AF30` (an enemy helper) -- carry no term.  The machine runs `$AA60` in the
display period, so its contended runs exceed these sums (the round-1 path: 1,595 uncontended against
the 1,606 median): DECLARED, with the rest of the contention.  `frameLedger().aa60.player` reports the
part; `.prov` is now the enemies' medians alone.  Under the banner (BT3) the late odd interrupts moved
22..39 -> 11..28 T (1P) and -26..-16 -> -27..-17 (2P).

**M7.70: the enemy handlers' runs charge their own T.**  `tools/enemycost.py` records every run of the
eight handlers (`$AF31`, `$AF47`, `$AF5F`, `$AF77`, `$AF95`, `$AFAF`, `$AFC4`, `$AFF6`) UNCONTENDED --
11,209 runs (11,191 natural, 339 natural paths, 118..3,147 T, an angry slot's second run included) -- with 18
declared FORCED CALLS for the arms no natural run reaches.  `BB_EN` holds the instruction sums of every arm --
the eight heads and sprite tails, the walker `$B028` (pause, fall, homing fall), the move decision
`$B09B` (divider, three-row floor search, hesitation, wind-up), the step `$B1B7` (wall, ledge, hop, the
patched RET of types 6 and 7), the ballistic hop `$B0F7`, the flyer `$B26F` (three half-steps and the
`$AEDC` probe chain by stride), type 4's `$B3C5` (launch, `$FE85` aim, the two arcs, the landing, the
three bottom wraps), and the shared `$AED1` / `$B47B` probe.  The sums come from the measured
per-instruction T (`scratchpad/ensums.py`); every instruction the sums use was executed by a recorded
run -- the forced calls measured the 13 that only the Z80's table had covered, and five more put `$AED1`'s
D across `$18` (the HUD's edge) and a flyer's last Y in `$C0..$C7`.  EN1 holds the engine to the machine's
T, exact, on all 751 kept runs (2 per (handler, path, T)), and to its writes, adding none; EN2 shows the pass charging it (`frameLedger().aa60.enemy`).
`$B0F1`'s taken RET is dead (a non-zero `$B088` leaves at `$B09F` first) and carries the Z80's 11.
`.prov` is now the corpse flight `$8A78` alone (and an unpriced handler, none in any state).  BT3's
windows did not move: round 1's enemies are asleep through them.  Contention is DECLARED as before.

### M7.72: the corpse flight charges its own T

`tools/corpsecost.py` records every `$8A78` flight called from `$AB00 CALL z` on an UNCONTENDED machine
(48 states x 300 frames under ab38cost's key script: 274 runs, 46 natural paths, 3,787..5,934 T) plus 10
declared FORCED CALLS for the arms no flight reaches: the bob's wrap down (`$8ABF`), the fall's X clamp
(`$8AEA`), the fall's timeout (`$8B51` taken), the second `$8BB4` row solid on the right and on the left
(`$8B81` taken), a full fruit table (`$8B96` out), the fall above the HUD (`$AED1`'s `$AED7` arm) and the
erase at an odd, an even unaligned and a high cached Y (a flight's Y stays cell-aligned, a fall's moves by
2).  `BB_CO` is the sums (`scratchpad/cosums.py`, from the measured per-instruction T -- every instruction
the sums use was executed by a recorded run, so no Z80 table T); `$BF0A` is BB_AB38's `BF_*` with
BB_A3AD's erase class, `$AED1` is `BB_EN.AED`.  CO1 holds the engine to the machine's T, exact, on all
110 kept runs, and to every write but the erase's code scratch (`$A480`, `$A584`, `$A5A6`, `$A5B1`,
`$A5BE`, `$A5D1`), adding none; CO2 shows the pass charging it (`frameLedger().aa60.corpse`), CO3 that
the term does not outlive its pass.  FOUND by seeding `$A431` (the erase's accumulator): `$A430`'s add
CARRIES on 58 of the 274 flights, and `$A435 RET nc` falling through costs 4 T that `bubbleErase()` dropped
-- it now returns the carry's T, and `$BF0A` charges it (TRAPS #279).  `.prov` is now an unpriced handler
alone (none in any state); `BB_AA60_CORPSE` stays as the fixture's record (AC2).

### M7.73: the bubble manager charges itself

The even branch was `MGR_FRAME_FIXED + BLOW_CHECK + pool x PER_BUBBLE` -- a flat 5,300 T per live
bubble, PROVISIONAL since M7.3.  `tools/mgrcost.py` brackets every `$B62C` pass by control flow on an
UNCONTENDED machine (48 states x 300 frames under ab38cost's key script: 6,408 passes) and the parts
TILE the whole on every one: prologue + the blow arm + twelve slots + RET.  A slot is `$B62C`'s own
instructions (the SKELETON) plus the ARMS it enters -- travel `$BDFE`, held `$B6C3`, rise `$B836`, draw
`$B9E7`, agepop `$B6D8` (from `$B669`), escape `$B679` -- and the skeleton is a closed function of the
slot's path through its six branches (`$B644 $B648 $B64D $B65E $B664 $B669`), ONE T per path over every
recorded slot:

| path | T | |
|---|---|---|
| PRO / RET | 78 / 10 | the toggle, `CALL $BD2C`, the loop set-up; the last RET |
| EMPTY | 95 | bit 7 clear |
| TRAVEL / HELD | 108 / 126 | bit 2 clear / bits 2 and 3 set |
| ODD | 203 | risen, the `$B657` toggle skips the age |
| ESCAPE | 233 | risen, `(IY+9)` non-zero |
| AGE / AGE_POP | 261 / 268 | risen, `INC (IY+4)`, the `CALL m` not taken / taken |

They agree with the Z80's instruction sums (written out in `BB_B62C`'s comment).  An empty pool is
456 + 78 + 167 + 12 x 95 + 10 = 1,851, the figure the old model was fitted to.  The ARMS are charged their
MEDIAN run over the fixture, uncontended -- blow 167, travel 8,482 (exact since M7.79), held 8,263 (exact since M7.77), rise 1,241 (exact since M7.76), draw 3,718,
agepop 3,864 (exact since M7.77), escape 16 (exact since M7.78) (`BB_B62C_ARM`) -- PROVISIONAL, reported apart (`frameLedger().b62c.prov`, beside
`.skel` and each slot's `.path`).  Gates: MG1 sets each of the 257 kept slots into a fresh engine with the
bytes its skeleton read on the machine and requires the machine's path and T; MG2 the medians; MG3 the
ISR's charge and the split's clearing; MG4 the start-of-play budget.

What moved.  PK7's pop rows were 8,431 T short and are 2,352 short.  The IA2 drive (a full pool of
twelve risen bubbles) shows how far the flat slope was off when bubbles pop: the machine's even ISRs
run 64,463 / 68,474 / **78,570** T at ISRs 405 / 411 / 414, the new model charges 63,044 / 66,915 /
77,274, and at 414 BOTH overrun a frame and lose the next interrupt -- the flat slope, charging the pool
left AFTER the pops, never did (TRAPS #280; `build/itemage_fixture.json` now records each ISR's T).
BT3 / HB4 / HB14 did not move: the pool is empty through their windows.

### M7.74: the blow check charges itself

The first of `$B62C`'s arms, `$BD2C` (both players' blow checks, from `$B633`), was its fixture median, 167 T --
the idle figure, so every spawning blow was charged 167 where the machine spends 698 + 43 x the slot.
`tools/blowcost.py` records every run on an UNCONTENDED machine (48 states x 300 frames: 6,413 runs, 27
paths, 167..1,401 T) plus 17 declared FORCED CALLS (`$BD2C` called once with the player blocks and the pool
poked: the held-key request and its refusals, dying, the debounce, fire mode, the +$61 == 15 bonus alone /
with fire / for player 2, lightning, both players, the scan to slot 11, the full pool's steal over risen /
travelling / holding bubbles and for both players).  A run's T is its OWN instructions'; the two nested
callees are bracketed apart -- the steal's pop `$B6D8` (the manager's arm (d)) and the bonus's award
`$80FA` (the score's).  `BB_BL` is the instruction sums, added by `playerBlow` on its own branches (`bT`):

| term | T | |
|---|---|---|
| OUTER | 45 | `LD IX / CALL $BD37 / LD IX`; player 2 runs inline, its RET the arm's |
| REQ | 35 / 61 / 70 / 64 | +$60 == 1 / bit 2 clear (out) / +$60 not 2 (out) / the held key |
| DYING, DEB | 32 or 38 out; 38, or 58 / 64 out | +$5A bit 2; +$5F == 3, else bit 1 |
| BONUS | 38 / 135 | +$61 != 15 / the award's call (its T apart) |
| FIRE | 30, + 50 to `$9DD4`'s RET | |
| SCAN | 27 + 43 a live slot + 67 the free one; 521 none free | |
| STEAL | 45 + per slot 44 holding / 62 kept / 85 better + 34 (29 the last) + 85 | |
| SPAWN | 36 (38 lightning) + 289 (+3 player 2) | |

Idle is 45 + 61 + 61 = 167, the old median; a slot-0 spawn 698 (the fixture's 17 runs).  The callees: a pop
of a bubble that has not risen is `BIT 2 / RET z`, 31 T, exact (`.blow_sub`); a real pop is the agepop
median and the award one forced figure, 3,525 T, both PROVISIONAL (`.blow_prov`, inside `.prov`).  Gates:
BL1 (64 kept runs, T exact, every write, the callees apart), BL2 (the pass's ledger).  What moved: an even
ISR that spawns is 531..1,234 T longer than it was, so the main loop's pass count moves with it -- PK8's
fixed key script played a different game (TRAPS #282).  The bonus itself is now BEHAVIOUR (item 3 of
next.md, closed): +$0050 a blow through `$80FA`, before the fire test.

### M7.75: the bubble draw charges itself

The second arm, `$B9E7` (a risen bubble's draw, `CALL` at `$B653`), was its fixture median, 3,718 T -- an
element bubble at an odd Y.  `tools/drawcost.py` records every run on an UNCONTENDED machine (48 states x 300
frames: 12,307 runs, 24 paths, 3,651..3,801 T) plus 46 declared FORCED CALLS (`$B9E7` called once with slot 0
poked risen: every Y phase `$40..$47` for each of the five sprite choices, the edges Y 0 / 1 / `$B7` -- the
blocked drift's wrap `$B8AC` and the drift's `$B864` -- and X `$F0`, the age test's `$E5` / `$E6`).  The
routine borrows SP as its sprite pointer (`LD IX,0 / ADD IX,SP` ... `LD SP,IX / RET`), so a run ends on the
return PC AND the caller's SP.  Its T is a function of two things only, and a walk of the disassembly with the
Zilog table and only B tracked reproduces all 126 kept rows:

| term | T | |
|---|---|---|
| PRO | 111 | `$B9E7..$B9FD`: IX = SP, the sprite offset from X & 7, `LD SP,HL` |
| SEL | 64 / 69 / 81 / 105 / 126 | empty / element (`$D380`) / holding / holding past `$E6` with `$B62D` set / past `$E6` with it clear (the empty sprite) |
| MID | 121 | `ADD HL,SP / LD SP,HL`, the masks from `$BFF8`, `BIT 0,(IY+6)`, `JP nz` |
| EVEN | 3,355 | Y & 7 in {2,4,6}: eight row pairs at 339 T over three blocks, their set-ups and the background-only tail |
| TOP | 3,443 | Y & 7 = 0: the third block empty, `$BBB1`'s detour |
| ODD | 3,417 | `$BBC3`'s phase-shifted path |

`BB_DR` holds them; `bubbleSprite()` records the choice on the machine's own branches (`dSel`) and
`bubbleDraw()` adds the rest (`dT`); the pass charges it as `frameLedger().b62c.draw`, outside `.prov`.
Gates: DR1 (126 kept rows: T exact, every write but the routine's twelve self-modified operands, no other --
the three edge rows read the ROM and keep their bitmap writes as addresses), DR2 (the pass's ledger, nothing
stale).  What moved: PK7's pop rows went from 2,352 to 2,903 T short -- the median overcharged the empty
bubbles those rows draw (3,651 against 3,718) -- and nothing else in the suite.

### M7.76: the bubble rise charges itself

The third arm, `$B836` (a risen bubble's move, `CALL` at `$B650`), was its fixture median, 1,241 T -- one
player in the game, outside the bubble's Y band.  `tools/risecost.py` records every run on an UNCONTENDED
machine (48 states x 300 frames: 12,311 runs, 58 paths, 1,184..2,012 T) plus 30 declared FORCED CALLS (`$B836`
called once with slot 0 poked risen and the players poked: the drift's two Y wraps, the X clamp both ways, the
blocked re-roll and its own wrap -- Y `$BF` on `boris`, whose `LD A,R` draws direction 4 -- and its edge (Y `$BE`
re-rolled onto `$BF`, kept: the battery's one survivor, `>= $C0` -> `>= $BF`, until it was added), a ROM marker
pointer, and every exit of the player contact: inactive, dying, each of the four overlap tests failing, the
touch pop facing either way and for player 2, the push in each wind and against both clamps, the bounce's
six ends, both players on one bubble).  A run's T is its OWN instructions'; its two nested callees are
bracketed apart -- the push's erase `$BF0A` (`cacheSetAndErase`'s return) and the bounce's shove `$ADAA`
(`adaaT`, read on the player before the move) -- and both were exact already, so the gate checks them too.
`BB_RI` is the Zilog sums, added on the engine's own branches (`rT`, the callees `rSub`):

| term | T | |
|---|---|---|
| PRO | 377 | the marker clear `$B6C8` (111), the save, `CALL $AEDC` (148), the wind, `CALL $B8E5` |
| CONTACT | 143 | `$B8E5`'s own frame: two `$B901` set-ups and calls, the RET |
| `$B901` exits | 36 / 95 / 152 / 171 / 239 / 262 | inactive / dying / Y high / Y low / X low / X high |
| FACE, TIGHT | 337 right, 342 left; + 36 or 59 | to the tight test's call; its first `RET nc` or its CCF, + `JP c` |
| POP | 106 | `$B9B6` to its `RET nz` |
| B_SET, B945 | 17 right / 7 left; 39 | `LD B,n`; to `$B94D`'s `JR z` |
| PUSH | 135 + clamp 37 / 31 / 48 + 30 + 33 / 47 / 35 | the erase apart; `$B977` in range / low / high; wind 2 / 4 / other |
| BOUNCE | 20 + 26 eq; + 28 + 11 toggle 0; + 28 + 89 + 113 / 129 / 90 | wind 2 / 6 (the shove apart) / other |
| DRIFT | 117 + 31 / 33 / 24 | no wrap / Y past `$BF` to 1 / Y onto 0 to `$B7` |
| PROBE | 195 + 54 / 12 / 49 | free / the first cell blocked / the second |
| REROLL | 39 or 41 (flipped) + 113 + 12 or 33 (the wrap) + 148 | `LD A,R` .. the second `CALL $AEDC` |
| MARK | 106 + 30 / 36 / 53 | the marker and the cache; X in range / below `$10` / from `$E1` |

An idle risen bubble with no player in the game is 377 + 143 + 2 x 36 + 148 + 249 + 136 = 1,125 T.  Gates: RI1
(159 kept rows: T exact, the callees exact and apart, every LD A,R fed, every write but the erase's ten code
bytes, no other), RI2 (the pass's ledger: `frameLedger().b62c.rise` / `.rise_sub`, outside `.prov`, nothing
stale).  FOUND on the way: two of the first table's terms were wrong although the hand checks of the same
rows agreed -- the push's high clamp (41, the `CP $E1` dropped: 48) and the bounce (59, `$B945`'s 39 counted
twice: 20).  The check summed the derivation, the table encoded it again (TRAPS #283).  What moved: PK7's pop
rows went from 2,903 to 2,683 T short -- the median had undercharged those rows' rises -- and nothing else
in the suite.

### M7.77: the bubble pop charges itself

The fourth arm, `$B6D8` (the pop), was two medians: the HELD arm (`$B6C3`, 8,263 T) and the age pop (`$B669`,
3,864); the blow's steal (`$BDBC`) charged the age pop's.  `tools/popcost.py` records every run from those three
callers on an UNCONTENDED machine (48 states x 300 frames: 71 runs -- 65 held, 6 aged, no natural steal -- 33
paths, 525..1,909 T) plus 23 declared FORCED CALLS (`$B6D8` called once with the pool, the burst table and the
shadow window poked: not risen, unpaid, the burst table full, the Y cancel's four edges, classes 0 / 2 / 3 / 4 /
5 / 12, class 5 for player 2, the corpse on each `$A447` arm, the mailbox busy, player 2, the chain window's three
refusals and its mark, the window in ROM).  A run's T is its OWN instructions'; three nested callees are bracketed
apart -- the erase `$BF0A` (`cacheSetAndErase`, exact), the corpse birth `$8BC2` and the award `$80FA` -- and the
held arm is recorded whole (`$B6C3` to `$B66C`), which MEASURES its own CALL / JR at 29 T.  `BB_PO` is the Zilog
sums, added on the engine's own branches (`poT`, the exact callees `poSub`, the provisional `poProv`):

| term | T | |
|---|---|---|
| RETZ | 31 | not risen: `BIT 2 / RET z` |
| HEAD | 281 | the marker release `$B6CD`, `LD ($B775),HL`, `CALL $BF0A`, the three RES, the class into `$B742`, the seed's set-up |
| SEED | 46 a busy slot; + 26 free / 7 none | the burst table walk; none free backs onto slot 13 |
| Y | 105 / 114 / 123 | kept / below `$10` / `$AF` and up (the cancel) |
| FLAGS | 102 + 11 unpaid (RET z) / 5 paid | the owner into `$B7C2` and `$B796` |
| MAIL | 142 / 36 | the request armed / one already pending |
| MASK | 17 / 24 + 199 | class below 5 / `$B7E5`'s mask |
| FORK | 64 / 245 / 69 | class 0 / class 1 (`$B816`, the birth apart) / 2 and up |
| CHAIN | 860 | the 4 x 4 window, no marker |
| MARK | + 113 / 133 / 165 | a marker's `$B7A1`: the slot empty / not risen / marked |
| TAIL | 96 | the two click edges, `CALL $80FA` (the award apart) |
| HELD | 29 | `$B6C3 CALL / JR`, the arm's own |

The corpse birth is exact where a held enemy always is -- frozen, or an empty slot -- `$8BC2`'s own 628 + `$A447`'s
head 62 (+ 20 when bit 7 is set) + `$A437` 89 (bit 5 clear) or 41 (set): 751 / 779 / 799; a LIVE enemy's birth
(the erase inside it) stays PROVISIONAL at its one forced figure, 2,012 (`BB_B62C_ARM.birth`).  The award stays
PROVISIONAL at 3,525: it is the score's cost (3,197..9,356 natural, 225 for a player out of the game).  DECLARED:
a window centred in ROM (a pop before the first risen move, `$BEE8` parks `(IY+3)` at 2) marks from ROM bytes the
page does not hold; the machine spends 1,880 T there on the forced row, the page counts its 16 reads
(`chainRomReads`) and charges none.  Gates: PO1 (72 kept rows: T exact, the callees apart, every write but the
erase's ten code bytes, no other), PO2 (the pass: a held pop's `.pop` = the run + the measured 29, an age pop's
the run, `.pop_sub`, `.pop_prov` inside `.prov`, nothing stale), PO3 (the steal carries a PAID pop's award in
`.bProv` -- no recorded steal was paid).  FOUND: the pass stored `.prov` before adding the pops' provisional to
it, so the ledger hid it while `tcost` charged it (MG3 caught it; TRAPS #284).  What moved: PK7's pop rows went
from 2,683 to 1,421 T short; what is left there is the award, the travel and escape medians, and the rest of
the ISR.

### M7.78: the bubble escape charges itself

The fifth arm, `$B679` (the escape), was its median, 16 T -- an element bubble's.  It is JUMPED to from `$B664`
(`JR nz`: a risen, unheld bubble whose class is not 0, on the age toggle's even call) with the class in A, and
leaves by a jump to `$B66C` at the same SP.  `tools/escapecost.py` records every entry on an UNCONTENDED machine
(48 states x 300 frames: 2,784 runs -- 1,841 element, 938 ageing, 5 releases -- 4 paths, 16..478 T) plus 13
declared FORCED CALLS (`$B679` entered once with the pool and the enemy table poked, A = the class: an element
bubble, a holding one short of the wrap and at `$FE`, the wrap at each of the erase's Y phases -- even, aligned,
odd, past `$C0` -- enemy indexes 0, 7 and 30 (10 x 30 wraps in eight bits), the marker cell in ROM, bit 2 clear,
slot 5).  The nested erase `$BF0A` is bracketed apart (`cacheSetAndErase`, exact; the escape had inlined the
cache and called `bubbleErase` -- it now calls the one spelling).  `BB_ES` is the Zilog sums, which matched every
row first time:

| term | T | |
|---|---|---|
| ELEM | 16 | `DEC A / JR nz` taken: an element bubble does not even age |
| AGE | 46 | `DEC A`, `JR nz`, `INC (IY+4)`, `JR nz` taken: a holding bubble short of the wrap |
| WRAP | 384 | the release: the enemy's index x 10 in eight bits, its RES 3 / RES 6 / SET 2, the cell-aligned X / Y, +8 / +9 cleared, the two CALLs, `RES 7`, `JP` |
| MARK | 31 / 94 | `$B6C8` (`bubbleClearMarker` returns it): bit 2 clear, `RET z` / the cell released (a ROM cell's write discarded, the same T) |

So a release is 478 T + the erase (422 past `$C0`, 3,259..3,343 otherwise).  Gates: ES1 (22 kept rows: T exact,
the erase apart, every write but the erase's ten code bytes, no other), ES2 (the pass: `.escape` /
`.escape_sub` for a release, an ageing and an element bubble, nothing in `.prov`, nothing stale).  What moved:
nothing pinned -- PK7's pop rows stay 1,421 T short (no escape in them); the arm's median undercharged a holding
bubble by 30 T every fourth frame and a release by ~3,800.

### M7.79: the bubble travel charges itself -- the last arm

The sixth and last arm, `$BDFE` (the travel), was its median, 8,482 T.  It is JUMPED to from `$B648` (`JP z`: a
live bubble not yet risen) and leaves by `JP $B66C` at the same SP: `CALL $BE07` -- the step, the capture `$BE5B`
and its enemy scan `$92C0` (with `$92DE` patched to RET: one list), the wall probe `$BEAF` and `$AEDC`, the
range test, the rise transition `$BEE8` -- then the tick `INC (IY+4)`.  `tools/travelcost.py` records every entry
on an UNCONTENDED machine (48 states x 300 frames: 752 runs, 164 paths -- the scan's length and outcomes vary
with the enemy table -- 1,224..2,929 T own; 3 natural captures) plus 31 declared FORCED CALLS (each facing, X & 6 and X odd
at `$BEC4`, ages 0 / 1 / 2, the range reached for each owner, each of the probe's four cells, a bubble born
flush, the scan's refusals -- frozen, each axis at each edge -- a 256-slot walk, and the capture at each erase
class, enemy index and owner).  Nested apart: each `$BF16` (CALLed from `$BE55`, `$BEA9`, `$BEE8`), the captured
enemy's `$A447` (from `$BE92`), and the draw `$B9E7` (JUMPED to from `$BE58` / `$BEAC`, its RET landing on
`$BE01`).  `BB_TR` is the Zilog sums (written out in its comment); a forced open-air run traced instruction by
instruction sums to 1,457 T as they do:

| term | T | |
|---|---|---|
| ARM | 50 | `CALL $BE07`, the tick `INC (IY+4)`, `JP $B66C` |
| HEAD / FACE / STEP | 176 / 26 left, 19 right / 36 | `$BE07`..`$BE31` |
| CAP_IN / SCAN | 66 / 129 | `$BE5B` to the scan, the scan's head |
| a slot | 27 + 12 dead / 31 frozen / 26 live + an axis each (57 out at `CP`, 76 out at `CCF`, 71 in) + 70 tail | `$92E4`..`$9305` |
| HIT_END / MISS_END | 31 / 29 | `POP HL / RET / RET c`; `OR A / RET / RET c / $92DE RET` |
| CAP_NO / CAP_YES | 31 / 25 | `$BE67`..`$BE6C` |
| CAPTURE | 67 + 18 (k + 1) + 104 + 71 + 69 | the index by subtraction (k = the enemy's slot from 2), the freeze, `$BEE8`, the escape delay, `POP HL` |
| PROBE | 253 + 12 / 7 | `$BEAF` with `$AEDC` (131); `$BEC4 JR z,+0` -- taken when X & 6 is 0, to the same place |
| a column | 79 / 74 missed; 23 / 52 hit | this cell / the row below |
| PROBE_RET / WALL | 10 / 95 born flush, 77 | `$BED5`, into `$BEE8` |
| RISE | 168 / 173 | `$BEE8` for player 1 / 2 (`$BF02 JR z`) |
| CAP / AGE | 121 / 15, 24, 45 | `$BE37`; age 1 / 2 (invisible) / else |

Two callees became exact on the way.  `$BF16` on its own is `cacheSetAndErase` less `$BF0A`'s four cache stores
(`BB_AB38.BF_CACHE` 76): the engine's `forcedErase`, which `cacheSetAndErase` now falls into as the machine does.
And `$A447`'s LIVE arm, which `entityEraseHalf` returned as null, is priced: the head and gates through `$A45E`
(118, `BF_A447`), the patched RET (10), and between them, when bit 6 was set, `$A461`'s ceiling test (36) or the
erase at its class (`BB_A3AD.ERASE_AL` / `ERASE_SH` by the cached X, with the add's carry): 128 / 164 / 1,384 /
1,474 / 1,476 / 3,001 / 3,079 on the forced captures, every one.  That also prices a corpse birth on a live enemy:
popcost's `corpse_live` (628 + 1,384 = 2,012) is exact, and `BB_B62C_ARM.birth` is gone -- the award `$80FA` is
the one PROVISIONAL figure left in `$B62C`.  DECLARED: `($AA57)` = 2 makes the scan's do-while walk 256 slots,
wrapping through the ROM; the page holds no ROM, so it charges a ROM slot as dead and counts it
(`scanRomReads`), and the forced row's 3,407 T beyond that (194 slots) is the one figure it cannot compute.
Gates: TR1 (466 kept rows: T exact less that figure, the callees apart, every write but the code scratch -- the
erase's ten bytes, the aligned erase's `$A50B` (CR6's operand; a captured enemy's is the only bubble-arm erase on
that path) and the draw's twelve operands -- no other), TR2 (the pass: a capture, a step, an unseen tick; `.travel`
/ `.travel_sub`, nothing in `.prov`, nothing stale).  What moved: nothing pinned -- PK7's pop rows hold no
travelling bubble and stay 1,421 T short; what is left there is the award and the rest of the ISR.

### M7.80: the score award charges itself -- nothing provisional left in the even pass

The award `$80FA` was the one PROVISIONAL figure inside `$B62C`: 3,525 T, blowcost's one forced `bonus` run,
charged for every award in the blow's +$61 bonus and the pop's paid emit (`BB_B62C_ARM.award`, now gone, and with
it the ledger's `.prov`, `.blow_prov` and `.pop_prov` -- the award is a callee in `.blow_sub` / `.pop_sub`).
`tools/awardcost.py` records every `$80FA` run from all eleven `CALL $80FA` sites on an UNCONTENDED machine (48
states x 300 frames: 60 runs from seven sites, 10 paths, 225..9,356 T; no interrupt landed inside one) plus 25
declared FORCED CALLS (A >= 3, each player's guard out, the compare abandoned and copied at each of its four steps
and all four equal, every digit count 0..8, a wrap to zero, A = 0, a copy redrawing eight digits).  Nothing is
bracketed apart: `$816B`, `$8042`, `$81B9`, `$804F` are the award's own.  `BB_AW` is the Zilog sums (in its
comment), and it matched every forced row as written but for one slip in the hand addition (PASS 438 -> 431):

| term | T | |
|---|---|---|
| RANGE | 18 | `CP 3 / RET nc` taken |
| OUT | 225 | the player entity's bit 7 clear: `$815C` discards the pending |
| PASS | 431 | the head, the BCD add x4, `CALL $816B`, the compare's set-up |
| STEP | 51 | an equal compare byte (the fourth one 46) |
| ABANDON / COPY | 78 / 218 | + 51 a step; the copy + the HIGH redraw |
| EQUAL | 384 | 3 x 51 + 46 + the copy past its 33 of tests, + the HIGH redraw |
| HUD | 2,164 | `$816B` with its four bytes' RLDs and two `$8042`s each (82) |
| a digit | 18 / 347 / 346 | a leading zero (`RET z`); the first drawn (`RET z` not taken); the rest (`NOP`) |

The glyph rows come from the ROM charset on the machine (`$8042`: `$3C00 + 8 * (digit + $30)`) and from
`BB_DIGITS` on the page; `$804F` copies eight rows whatever they hold, so the T does not depend on a glyph byte --
AW1 matching on every row is the proof -- and no window is DECLARED.  The fixture keeps the ROM reads as a count
and the bitmap writes as addresses only (house rule 7).  Cross-checks for free: blowcost's three `bonus` awards
(3,525 each) and popcost's 41 award runs, measured by other oracles, are now BL1's and PO1's exact expectations,
and the engine's `scoreAward` meets every one.  Gates: AW1 (79 rows: T, every write, the bitmap by address); BL1 /
BL2 / PO1 / PO2 / PO3 / MG2..MG4 / DR2 / RI2 / ES2 / TR2 re-aimed (each asserts the ledger has no `.prov`).
MOVED: PK7's pop rows 1,421 -> 1,093 T short (the forced figure undercharged these pops' awards); what is left
there is the rest of the ISR (contention, the other passes).

### M7.83: the flood's tick charges itself and paints on its own clock

`$A09A`'s flood arm (`$A127`, the blue cross's ramp) charged NOTHING until M7.83 -- `BB_PASS_T` holds only the
idle path's 90 T -- and wrote its row (`$A13F LD B,$20 / JR $A0ED`, the painter's body entered at its loop) and its
payload (`$A151 JP $A0F5`) at the call.  `tools/floodtime.py` drives `$A09A` on round1_48 with ($FECE) = every v in
1..255 on an UNCONTENDED machine (the storm off, the edge detector primed), plus three row ticks and the payload at
sixteen contended phases, a contended sweep of the interrupt line over the payload tick (240 offsets), and 110
natural ticks with interrupts ON (seven free worlds; round1_48 and r50_48 at sixteen forced phases and at eight
phases 20..1,640 T before the interrupt, so the tick straddles it).  `BB_FLOOD` is the Zilog sums (in its comment):

| exit | ticks | T | |
|---|---|---|---|
| ROW | 171 | 1,523 | `$A127..$A144` 139; the body at 206, its first `$A0F0` store at 221, then 41 a cell |
| RAMP | 27 | 151 | `$A14D RET c` |
| PAST | 52 | 163 | `$A150 RET nc` |
| DISARM | 3 | 126 | the ADD's carry, `$A154` |
| PAYLOAD | 2 | 1,327 | the thunder's payload shifted by 8 T: every store, DI and the open point |

Each tick spends its cost less the idle path (the thunder's rule).  The row's stores touch the attribute file and
are held at round(K x T) with `BB_STORM_K.flood` = 1.048219, the sixteen forced natural runs' fit (1,523..1,650
measured); against the machine's main-line T they land -47..72 T (forced), -50..72 (free), -54..72 (edge),
DECLARED.  The payload touches no contended byte: EXACT on all 55 natural runs.  Its DI window is `BB_STORM_P` + 8:
the sweep loses the interrupt at exactly 168..1,295, and three straddling entries on each forced world lose it in
play.  THE PREMISE (0 of 110 break it): an interrupt inside a tick (0 or 1, both gates open) writes and reads no
attribute byte, reads nothing the tick wrote, and writes nothing it reads after -- so the storm's held-write block
(M7.58) serves the flood unchanged: `effectFlood` runs the row and the payload through `stormBegin` / `stormEnd`,
`attrFlash` stamps a whole play-area row (any other timed size or base still throws), and `effectPayload` takes the
door's shift.  Gates FL1 (all 255 ticks: exit, $FECE, spend, every store and stamp), FL2 (the 110 natural ticks),
FL3 (premise, sweep, window), FL4 (through `step()` on a real game: a row tick forced 300 T before the point holds
its last 30 stores and the pass waits; a payload tick forced 700 T before holds 19 and loses the interrupt).

### M7.95: the treasure room's award and "PERFECT !" in time

`$8E3A`'s treasure drain falls through `$8F4A JR nz` when the room is empty into `$8F4C DI` .. `$8F77 EI` (the
award: the tally compare, `$80FA` for each player) and `$8F78`'s 256 draws of "PERFECT !" (`$801D` + `$994F`,
interrupts ON), then `$8F92 XOR A / RET` to `$8D61 JR z` -- the round advance.  Until M7.95 the engine charged the
decision's 137 T and the two `$8F94` counts, and SPENT NOTHING of the block: 1,751,241 T, ~25 frames of the machine
missing (cost8e3a's natural block on lastdia81 / lastdia82 is 1,754,419 from `$8E3A`'s entry).

`tools/perfecttime.py` -> `build/perfecttime_fixture.json`: ten worlds AT `$8F4C` (lastdia81 / lastdia82 by
ab38cost's key script; eight forced on round1_48 / round1_2p48 -- lead / tie / trail, the HIGH copy, the four-equal
fall into it, eight-digit scores).  EXACT (plain Simulator, interrupts off) every write outside the stack by address
and instruction-start T (the award's listed -- no value: the digits are the ROM charset's; the first iteration's;
the whole stream's count and digest), the stamps, the SEED.  CONTENDED, interrupts on, 21 phases on each natural
world (four inside the award's DI window): every ISR, the window, the lost boundaries, the main-line T at the EI, at
every iteration and at the return, and what the ISRs touched of the block's bytes.  `verify --jobs 6`: MATCH (~11 s).

The engine (`BB_PF`, `BB_PF_SCRIPT`, `BB_AW_W`; `treasureBlock`) runs the block on the M7.57 mirror:

| routine | T | |
|---|---|---|
| `pf_award` | HEAD 54 + LEAD 19 / TIE 32 / TRAIL 30 + CALL 51, award 1, MID 50, award 2, EI 4 | 9,657 on lastdia; every write from the award's own clock |
| `pf_double` | 6,082 (BB_EXT_W's DOUBLE on `$9A9F`) | gap FIRST 59 / NEXT 75 |
| `pf_runs` | 629 (`$994F`, B = 9: rows from 28 and 352, 31 a cell) | gap 17 |
| `pf_end` | 0 | gap TAIL 32 (POP BC / DJNZ 8 / XOR A / RET) |

THE AWARD'S CLOCK: `scoreAward` / `scoreHud` / `scoreClear` / `scoreGlyph` mark each store's T (`awClk`, BB_AW_W --
the BB_AW sums cut at each store) when a block asks; the machine's three RLDs a byte also WRITE the score byte (two
intermediate values and back) -- logged by the model at their T, not made by the port (interrupts are off, the byte
reads the same after).  `scoreHud` now stores `$8605` where the machine does (`$817A`, then before every digit),
not once at the end.  EXACT on all ten worlds: the block's T, the 85..348 award writes by address and T, every
`$801D` / `$994F` hook, the whole 42,581..42,844-write stream (digest) -- PF1.

THE INTERRUPTS: the award's DI window [4, the end of `$8F78 LD B,0`] rides the frame clock (intLost): the machine
loses the boundary inside it on all 12 phases that put one there, the engine the same ones.  The draws run with
interrupts ON: 29..30 ISRs inside on the treasure worlds, 33 on round 1, EVERY ONE with both gates open -- the port's
`isr()` reads the same gates, and step() runs them between the held writes (M7.94's `rvIsr`).  THE STRETCH
(BB_EXT_K, the natural worlds' 42 runs): the award 1.007909 (0..151 T over 9,657), the draws 1.030295 (the loop's
mean main-line 1,793,632 less its 23,568 T of gaps over 1,718,016) -- the block's end -233..+62 T off the machine's
(round 1: +2,476), its iterations -785..+497 (PF1b, pinned, DECLARED).  THE PREMISE: no ISR inside writes or reads a
byte the block writes on the treasure worlds; on round 1 the sprites cross the PERFECT cells (816 writes / 616
reads) -- the held writes land before each interrupt point as the machine's do, to within the stretch's spread.
Through step() (PF2): the pass waits at `$8D61` (`perfectPending`, chainWalk's 'perfect'), 31 ISRs run inside,
frameLedger() names the block, and mainLoop's resume runs the round advance (charged as the clear pass).  `$8F4A`'s
fall-through 7 joins the decision's own (`BB_RC.TR_FALL`); RC3 (= PF3) now asserts the machine's 1,754,419.

### M7.97: the giant-item spawn is made and charged

`$8E3A`'s one-shot clear ends `$8F1A LD A,($FECC) / OR A / JR z` and, with the mailbox armed, `LD C,A / XOR A /
LD ($FECC),A / LD A,C / CALL $A84D` (the 49 of `BB_RC.HUD`, charged since M7.93).  The call itself was NOT made
and NOT charged until M7.97.  `tools/giantspawn.py` (verify MATCH, ~28 s): every `$A84D` run is
HEAD 150 + DIA 38 / FRUIT 62 / OTHER 67 (Zilog sums in `BB_GS`'s comment; 3 natural, 10 forced, 2 through-runs).
`bossSpawn` sets `gsT`; `roundClearOnce` returns it and the decision adds it to `rcSub`, so the clear pass's
`$8E3A` part is the machine's T with the spawn in it (RC1 now exact on its 3 spawn rows, writes compared; GS1 /
GS2).  The boss tick's tail-jump spawn (A = 4) stays in the flat rest with `$A9ED` (unmeasured).

### M7.98: the umbrella's `$A110` block

`$88B1` (the umbrella collected) stores ($FECD) and `$88C0 JP $A110`: five turns of the flash (`$A0E0`), `EI / HALT`,
`DI / CALL $8C28`, `EI / HALT`, `DI / POP BC / DJNZ`; `EI / RET`.  Until M7.98 the port returned at `$88C0` -- no flash,
no reveal, no HALT, ~28..30 frames of the machine missing (the rounds were still skipped by `$8D12` afterwards).

`tools/umbrella.py` -> `build/umbrella_fixture.json`: the natural collect (the umbrella world, the jump key held to
`$88B1`) and `$88BD` forced with A = 3 / 5 / 7 on round1_48, 5 on r50_48.  EXACT, each segment between two HALTs from its
own start: head 29,000 T (`BB_UMB.HEAD` 55 + the flash 28,941 + EI 4), flash turns 29,010 (`TURN` 65), reveals 213,337 /
214,271 / 217,647 (`$9032`'s script: DI 4 / CALL 17 / the reveal / RET to `$A11F` / EI 4), end 36 -- every hook, every
write (a flash's 704 cells run by run, `FL_PRE` 45, a cell 41 with its store 15 in, each run's last DJNZ 5 short, RET 10,
a CALL 17 after the first run only), every OUT.  CONTENDED, interrupts on: every ISR, HALT, DI window and lost boundary,
and on to the main loop's resume (3 / 5 / 7 `$97F8` entries, the round + ($FECD)).  `verify --jobs 6`: MATCH (~10 s).

The engine runs the block a SEGMENT at a time on the M7.57 mirror (`umbrellaBegin` / `umbSeg` / `umbStep`, blocks
`umb_head` / `umb_flash` / `umb_reveal`): the head inside the pass (interrupts on: an interrupt inside it runs between its
held writes, `rvIsr`), the pass then waiting at the chain entry after `$8669` ('umbrella'); every later segment from
mainLoop on the main line the HALT's interrupt left at the frame's start; a HALT spends the rest of its frame.  DI windows
on the frame clock: the reveal's (`$9032`'s) and a later flash's [DI, the HALT].  THE STRETCH: `BB_EXT_K.u_flash` 1.070734
(the twelve head / flash segments, ISRs out; 1.0529..1.0918 by phase, DECLARED); the reveal keeps BB_EXT_K -- the machine's
window is 1.155..1.194 of the exact by the phase the HALT's ISR leaves, so after round 1's ~27,000-T odd ISR the machine
loses four interrupts under the first two reveals and the K model three (UM2, 39 of 45 segments exact, the six pinned).
Gates M7.98 UM1 (every segment exact against the fixture, five runs), UM2 (the stretch, the lost interrupts, the spread
pinned: reveal -3,468..+4,197 T, flash -617..+512), UM3 (through step(): the umbrella collected on round 1, draws forced to
3 / 5 / 7: five flashes, five reveals, the OUTs `$FECD,0,...`, no pass while it runs, 11 ISRs, 3 lost a reveal here
(the port's own odd ISR ~21,000 T), 26 frames; then `$97F8` on the machine's rounds and play on round 4 / 6 / 8, the
machine's), UM4 (outside step() the whole block lands in the call; a HALT there throws).  DECLARED: `$88B1..$88BD`'s draw
charges nothing (every handler's own T, M7.92); the rest of `$8669`'s pass after the dispatch runs at the call, ~28
frames before the machine's (the other blocks' way).
### M7.96: the fourteen small callees charge themselves

The last fourteen main-loop callees inside the flat `BB_PASS_T` -- `$8E2A $9961 $900B $8FE7 $9AEB $93DC $9E50 $A9ED
$A824 $915F $948F $7E80 $9037 $A09A` -- now charge their own T through `passAdd`, as `$931A $C002 $925A $8FA5 $8E3A
$8669` have since M7.88..M7.93.  The oracle is `tools/costsmall.py` -> `build/costsmall_fixture.json` (every run of
each from its one call site, 48 states x 300 frames, uncontended, nested frames and HALT waits bracketed apart; 62
FORCED calls; the instruction-sum model exact on all 1,453,955 natural root and nested frames and the 1,024 forced;
'contended', 'window' -- round1_48's first 48 frames, the census -- and, new, 'window_world': round1_48's toggles,
edge operands and credits).  `verify --jobs 4`: MATCH (~4 min).

THE ENGINE: `BB_SM` is the fixture's own Zilog sums, one per straight line from an entry and per decision outcome
(538 keys, generated from the keys the code names); each routine's code calls `zs(key)` at the decisions it takes,
so a run's T is S(entry) + the sum of E(event), its nested frames the same from their entries; helpers already timed
supply their own (`restT`, `blitT`, `awT`, `corpseBirth`, `extModel('lives')`, `a314T`, `tcost` for `$A447`).
`smallRun(addr, fn)` (chainWalk) resets `smT`, runs, and passes round(K x smT) less what the run spent in time
(`smSpent`) to `passAdd`.  Thirteen outcomes the oracle never saw are listed (`BB_SM_UNMEASURED`) and COUNTED when
taken (`smMiss`); one Zilog T is written by hand (`A978t`, P2 hit by the boss test: RET c taken, 11).

| callee | share (`BB_PASS_PROV`) | K | |
|---|---|---|---|
| `$7E80` | 39 | 1.398753 | its code is in contended RAM: idle 28 -> 39 |
| `$8E2A` `$900B` `$915F` `$93DC` `$948F` `$A9ED` | 48 57 22 110 28 31 | 1 | |
| `$8FE7` | 37 | 1.039274 | the IN |
| `$9037` | 94 | 1.034097 | |
| `$9961` | 72 | 1.018937 | |
| `$9AEB` `$9E50` `$A09A` `$A824` | 51 102 48 28 | 1 | once a frame: the 11-pass frames' mean (M7.92's split) |

The rest left in `BB_PASS_T` is 78 T.  Blocks a callee starts on its own clock keep their T (the HURRY UP!
block from `$9037`'s entry: its run charges 0; the cross release's reveal from `$9031`: `$900B` charges the rest
less DI / CALL, 21).  FIXED (next.md 3k): (1) `$9037` with `$9049` set charged `spend(91)` on top of the flat rest
-- now the machine's 107, with the pass; (2) `$A824`'s draw (`$A8C1`, 4,196) and erase are its T, and on a hit
everything before `$A9B5`'s DI (4,888 on candycane's world) is SPENT IN TIME before the reveal block
(`smallSpend`); (3) `$A09A`'s share is 48 (the comments assumed the idle 90 every pass): a tick's spends keep the
thunder's rule (cost less the idle 90 in time) and the 90 come with the pass; (4) an EXTEND that completes spends
`$948F`'s 83 (P1) / 151 (P2) before `$94C2`'s block -- its pass is an advance, which charges the chain nothing.

THE CENSUS WORLD (TRAPS #286 again): charging themselves, the small callees showed two differences between the
engine's census world and round1_48 -- the credits (`$FED3` 0 against 5: `$9961` ran 28 T a pass, the machine 71)
and `$9E5D`'s toggle phase (the element tick fell in the engine's 7-pass frames, the machine's in its 11-pass ones).
The census row now seeds both, and the edge operands, from 'window_world'; odd frames run 11 again.

GATES: SM2 (fourteen rows) replays all 595 kept runs (the two boss kills through `$9298`, playerHit's boundary,
declared apart) from their own entry state -- exact, no key unmeasured; the forced runs' hooks re-made (the PRNG
draw at `$9B2B`, the overlap's carry at `$AA2F`, the slot filled during `$7EC2`'s HALT, the keys); `$A09A`'s ticks
by the storm's own K.  SM1: BB_SM = the fixture's sums key by key, every key the built code names summed or
declared, no seed below $4000.  SM3: the four fixes against the fixture's own instruction lists.  SM4: in a game,
every pass carries all fourteen parts, the call their sum, the every-pass routines at round(K x T) of the window's
T.  The pass identity rows (IM3, SC4, EP2, EK2, HB5) add the fourteen shares (`smShares`, from the fixture).

DECLARED: (until M7.99b, below: `$9961`'s join tail charged `$7FD7`'s 64-cell clear and the lives panel the port
did not make, and `$915F` Boris's `$A314` erase); the pause's spin polls (34 T each) are not charged (M7.107: charged, on the frame clock);
`$900B`'s and `$A09A`'s T before their reveal blocks stay with the pass (as before M7.96); the boss kill through
`$9298` is not charged (M7.99a: made and charged); K = 1 for the path-mixing once-a-frame routines.

### M7.99a: the boss tick's spawn and its kill through `$9298`

`tools/bosskillcost.py` -> `build/bosskillcost_fixture.json` (`verify --jobs 6`: MATCH, ~3 s), `$A9ED` from `$8D2E`,
uncontended, every self-modified byte an instruction is made of read as state (costsmall's `smc_set`):

- THE SPAWN (`$A9F9 JP z,$A84D`, A = 4) was ALREADY CHARGED: a tail jump keeps `$A84D` inside `$A9ED`'s own run, and
  M7.96 (merged after M7.97) prices it with BB_SM's `A9F9t` (JP 10 + `BB_GS.HEAD` 150) / `A871f` / `A878f` / `A880x` --
  217 + 10.  M7.97's note that it stayed in the flat rest was stale.  The natural run (bossspawn): 276 T, replayed
  through `smallRun` -> `passAdd` exactly, one spawn, its 7 writes (BK1).
- THE KILL THROUGH `$9298` (forced: ($FED0) poked on boss / bosshit / bosskilled, P1 or P2 glued into the box at
  `$AA2C`; nothing else).  HL at `$9298` is **$A9AF on every run** -- `$A994 LD HL,$A9AF / PUSH HL`, the comparator's
  SCF / RET it returns through -- so `$9299` makes IY = `$A9A8` and **`$8BC2` births a corpse over `$A969`'s own
  code** (`$A9A8..$A9B1`; `$A9AF` SCF becomes `$8C` ADC A,H), ($AA5F) counts it, the toucher is paid $1000.  Runs
  12,794..21,235 T: own = the carried refusal's own - 45 + 9281t 122 + 92ADt 59 / 92ADf 58 + 92BAx 10, `$8BC2` 731,
  `$80FA` 225 / 4,181 / 8,649.  The engine: `bossAxis` records HL (`bossHL`), `bossBody` folds `9281t` into its
  ($FED0) decision, `playerHit(fromBoss)` runs `bossHeart` (corpseBirth at HL - 7, the award, both T into `smT`) --
  EXACT on all 8 runs and their 8 controls, every write (BK2); costsmall's two forced runs (HL := $FD9B poked, a
  live slot) exact with the same declared input (BK3).
- 'after' (boss, the natural kill at frame 6): the machine EXECUTES a rewritten byte three frames on (PC `$A9A8`) and
  goes wrong (stopped there; not run on).  DECLARED: the port keeps its own comparator; the DI window
  `$929F..$92B9` is not on the frame clock (the `$925A` path's neither); with the overlap pair alive (SCF / RET) HL
  is not `$A969`'s -- nothing made, COUNTED (`bossHeartBlind`, BK4).

### M7.99b: the join's clear and lives panel, and Boris's erase, are made

`tools/jointail.py` -> `build/jointail_fixture.json` (`verify` MATCH, seconds): every main-line write of `$9961`'s
join and of `$915F`'s request, with the T of its instruction's start from the routine's entry, uncontended,
interrupts bracketed out.  Joins: 16 natural (eight 1P states, '2' held from frame 2 / 5; 7 with an interrupt
inside the tail) + 12 forced (P1 / P2 joining, the other's lives 0..7 and out, the panel's paper already its ink:
+1 T a cell).  `$915F`: 5 natural respawns (ab38cost's key script) + 8 forced over Boris's Y & 7.

THE ENGINE: `joinCommit` makes `$7FD7`'s clear and `$806C`'s panel between the RRD digits and the text, each write
stamped in `joinW` by round 1's own HUD model: `$7FC0`'s entry = the run's T so far less `BB_JOIN.HEAD` 120 (the
part of the path's straight line past the JP) plus `$997B`'s `$AA49` (B = 4); the clear's cell j at FILL0 + 26 j;
the panel from LIVES at `extModel('lives')`'s offsets (`joinStamp`, which COUNTS any write or offset it cannot
pair: `joinOff`).  `hurryReset` makes the erase (`itemErasePixels($9250)`, after the stores, as the machine) and
charges its own `restT` (`a314T` is gone).  Gates: JT1 (joinW = the machine's writes from `$7FD7` to `$7FE2`,
[T, address, value] exact, on all 28), JT2 (every display write of the tail in the machine's order, every non-ROM
value equal), JT3 (the fixture's panel structure), JT4 (through `step()`: P2 joins a round-1 game, the three
cells `$7FFC` skips are zeroed and P2's panel is the machine's), JT5 (the stamper's counts), BO1 (the 13 erases:
the machine's writes in its order, `$A314`'s operands `$A33D / $A349 / $A355` apart, T exact).

DECLARED: the tail's writes land AT THE CALL (the pass is atomic, as the tail's text and attributes always have);
on the machine an interrupt inside the 42..59K-T tail runs before its later writes (7 of the 16 natural joins).
M7.108: inside step() closed -- the join is a lazy block, every write in its frame; outside step() this path stays.

### M7.99c: the reveal timed by its accesses

The reveal entered after a DI (`$9031 DI / CALL $8C28`, the umbrella's `$A11B`) runs with interrupts off to its own
`$8C4C EI`, so the interrupts it loses are decided by where that EI falls.  The K model (one stretch a routine, M7.57)
is the machine's on average and not at a phase: the machine's window is 248,010..258,242 T by the entry's phase on
r50_48, the model's 252,246 at every one -- so at phase 26,208 on r50_48 / r10_48, and on the umbrella's first two
reveals after round 1's ~27,000-T odd ISR, the machine lost a fourth interrupt the engine did not (RV2 / UM2, DECLARED).

`tools/revealcont.py` -> `build/revealcont_fixture.json`.  SkoolKit's CMIOSimulator contends each ACCESS: one to
`$4000..$7FFF` at frame T t waits DELAYS_48K[t % 69888] (6,5,4,3,2,1,0,0 over the first 128 T of each of the 192 lines
from 14,335).  So with no ISR inside, the contended T is fixed by the exact T of each contended access and the entry's
phase: t_i = phase + a_i + D_(i-1).  MEASURED: a plain run logs every contended access of the reveal (49,803 for the
repaint's LDIRs, 6..316 for the digits by the round -- their code is at `$7F80`, every fetch contends -- 704 for the
derive's stores, 9 a panel letter, 18 a lives cell, 1 for the OUT's ULA cycle); the CMIOSimulator from the entry at
17 phases (the source's own and 16 forced) on 31 sources -- `$9031` on r50_48 / r10_48 and four variants of r50_48
(the EXTEND letters, the lives counts, player 2 in play, a lives row over a paper already its ink), the umbrella's 25
reveals -- gives every hook, the EI's end, the RET and every write's contended T, and the replay of the log gives
every hook EXACTLY on all 523 runs (the tool stops otherwise).  `$7F80` alone for ($8609) = 0..100 and `$957E` alone
for each player's 64 masks: count, digest, exact T.  `verify --jobs 6`: MATCH (~25 s).

The engine (`BB_ULA`, `bbUlaDelay`, `bbUlaDelays`, `BB_EXT_CP`, `bbDigitsCp`, `extCon`): each routine's model
(`extModel(kind, cp)`) also builds its ACCESS PROGRAM -- the repaint an LDIR's 11 and 14..20 (its last 11, 14, 15),
the derive's and the panel's stores at 4, the lives rows' `$80AF` read 51 before `$80B8`'s store, the attribute's
`$80D5` read and `$80E3` store, the last cell's `$5AC0` read, the OUT at 16, the digits instruction by instruction
(`bbDigitsCp`, checked against `extDigits`' T: a disagreement THROWS).  A block marked `ula` (`reveal`, `umb_reveal`:
interrupts off from their first instruction -- one with interrupts on THROWS) inside step() takes its entry's phase
from the interrupt point (`extPh` = extOrg - budget), and every contended offset -- hooks, held writes, the window's
EI, the block's end -- is `extCon`: the exact offset plus the delays of the accesses before it.  EXACT against the
machine: every hook, the EI's end, the RET and every write's T on the 523 runs (M7.99c C1), every routine's
program by count and digest on every source and alone (C2); the lost interrupts are the machine's on every one --
RV2 34 of 34 (was 32), UM2 45 of 45 (was 39); the contended `$8C28..RET` 0..0 T off the machine's main-line T on
both (was -6,008..+4,307 / -3,468..+4,197).

DECLARED (C3): outside step() (the budget Infinity, no interrupt point) the routines keep BB_EXT_K; the
interrupts-on blocks (`$94C2`'s, `$A09A`'s and `$A9B5`'s reveals, `$8F4C`, the umbrella's head) keep their K --
an ISR inside moves the frame phase by T the block cannot know when it stamps.

### M7.99d: the umbrella's later flashes timed by their accesses

The umbrella's turns 2..5 run `$A121 DI / POP BC / DJNZ / PUSH BC / LD DE / CALL $A0E0`, the flash, `$A119 EI` and
the HALT: interrupts OFF from the first instruction, so they are a block of the M7.99c kind (no ISR inside), and
M7.98 had left them on u_flash's one K (UM2: -617..+512 T off the machine's main-line T).  `tools/revealcont.py`
now also logs them ('flash': the 20 turns of umbrella.py's five runs, each at its own phase -- after the HALT's ISR
-- and the sixteen forced: 340 runs).  MEASURED: u_turn and u_ei touch no contended byte; u_flash's program is
`$A0E0 OUT ($FE),A`'s ULA cycle at 8 and each of the 704 cells' `$A0ED LD A,(HL)` read 11 before its store
instruction and the store at 4 -- 1,409 accesses; the replay gives every mark ($A0E0, $A119, the EI's end, the
HALT) and every write EXACTLY at every phase.  The HALT lands 29,197..31,676 T after the DI by the phase.

The engine (`BB_EXT_CP.FL_OUT` 8, `FL_RD` -11; `umb_flash` is `ula`, `diFrom: 'u_turn'`): C4 (every mark, write
and program, 340 runs, exact); UM2's flash 0..0 T through `umbSeg` at the machine's own phase.  The head
(`$88C0`, inside the pass, interrupts ON) keeps u_flash's K -- the C3 list.  A segment HALTs anyway, so the
frame's end does not move; what is exact now is where each flash write lands before the interrupt point.

### M7.99e: the interrupts-on blocks, measured before a design

The blocks with ISRs INSIDE (C3's list: `$94C2`, the storm wrap's `$A0BE` reveal, the giant's `$A9B5`, `$8F4C`, the
umbrella's head `$88C0`) stamp every write at the call on the main-line clock and spend their contended T at
`extEnd`; step() maps that onto frames with `budget = FRAME - isrCost`.  After each ISR the main line resumes at that
ISR's end, and its access delays depend on that phase.  Two questions, measured before any engine work.

`tools/isrcarry.py` -> `build/isrcarry_fixture.json`.  Sources: wrap (round1_48, r50_48, revealentry's reach), giant
(fallcandy, peachfall), perfect (lastdia81, lastdia82, r1_lead, perfecttime's reach), the umbrella's head (the natural
run, to its first HALT), extend (extcomp, all six letters, to `$8D09`: 1,345,409 instructions, 17,107,864 T exact);
each at its own phase and the sixteen forced (extend: own + 4) -- 141 runs.  `verify --jobs 6`: MATCH (~14 s).

(a) CARRY.  The plain run (CMIOSimulator, interrupts off, accesses logged) gives the block's instruction stream on
the exact clock; the replay walks it from the entry's phase, each access delayed by DELAYS_48K at its wall T, an
interrupt accepted after any instruction with IFF set (not after EI or a lone DD/FD prefix) whose wall end is < 32 T
into a frame, and the MACHINE's wall T of that ISR added there.  MEASURED: on all 141 runs the machine's main line is
the plain run's (instruction count and a PC hash -- no ISR moves the main line's flow), and the replay gives every
acceptance (instruction index and wall T) and the block's end EXACTLY.  So given each ISR's wall T, the main line is
the access model of M7.99c segment by segment, nothing more.

(b) THE ISR.  The RAM ($4000.. only) before each of the 356 ISRs inside the own-phase runs, fed to a fresh `BB_Game`
and its `isr()` (`scratchpad/isrcarry_eng/`: isrsnap.py, isreng.js -- probes, not gates): **the engine's `isrCost` is
the machine's UNCONTENDED ISR T (wall minus the ISR's own access delays) on 356 of 356.**  What it lacks is the ISR's
own contention: 0 on every ISR of giant, the two natural perfects and extend (extend's all gate-closed); 0..281 T an ISR on wrap round1_48 (sum 477..709 a run by phase), 0..883 on wrap r50_48 (2,609..2,624),
0..275 on perfect r1_lead (2,587..2,661 over 33 ISRs), 92..96 on the head's one ISR.

So the design next.md proposed holds: a block whose stamps are computed lazily, frame by frame, from the frame's
actual phase (each ISR's end = the frame's interrupt point + the engine's isrCost) would be exact wherever the ISR is
uncontended -- giant, extend, the natural perfects -- and off by the ISR's own contention (<= 2,661 T summed over a
block) elsewhere; that residue is the engine-wide ISR contention gap (STATUS), not this block's.

### M7.100: the giant's block timed a frame at a time

M7.99e's design, on the giant's `$A9B5` block first (short, its ISRs uncontended).  A block marked `lazy` inside step():
each routine builds its access program (M7.99c's `extModel(kind, cp)`) onto the block's EXACT clock (`lz.acc`, from the
entry); its writes are held UNSTAMPED (`lzHold`: Infinity in `heldWrites`, so flushWrites keeps them) and its OUT is
queued.  `lzSeg(s, budget)` times one frame: the main line from exact offset `lz.x` at frame time s, each access waiting
`bbUlaDelay(frame T - budget)` (the wall phase, as `extPh`), the interrupt point where the contended clock reaches the
budget.  Every write before it lands, every OUT before it is logged at its frame T; the end before it returns that T and
the pass resumes there (`lzStep`, less `paid`); otherwise the point is carried and the next frame starts at 0 -- after
the ISR, whose T is in that frame's budget.  The call's own frame runs at `extEnd` (s = the entry); every later one at
step()'s start, before flushWrites.  The DI windows go onto the frame clock on the contended clock (`lzWindows`; one
opening past the first interrupt point throws).  `rvIsr` weighs a lazy block's reads, kept on its exact clock, at
`lz.x`.  Outside step() the block keeps K.

The award's program: `giantCollide` runs `$80FA` on the award clock (`awClk`, base PRE 120 = `$80FA`'s entry) and
`scoreGlyph` logs each display store's access (`ck.cp`, the store + 4): the 32 `$8052 LD (HL),A` stores at 2017..4020 T
from `$A9B5` -- the plain run's (a probe: `scratchpad/lazy/gihead.py`), the only contended accesses before `$8C28`.

`tools/isrcarry.py` also runs the giant at revealentry's six phases with a boundary inside the award window
(`GIANT_WIN`): 153 runs, replay exact on all.  **LZ1**: each giant row (46: own phase, sixteen forced, the six) in the
engine, seeded as RX1's door, entered at the row's phase, its frames driven as step() drives them (intLost, lzStep,
flushWrites) with each ISR's T the machine's wall T: every ISR the machine takes is taken at its boundary (accepted
0..31 T on), the 12 it loses are lost, the end is the machine's wall T and the main line's delays its `main_delay` on
all 46; the program is the machine's 32 stores; the window's end 0..54 T past the exact by the phase; the OUT logged
once, in the last frame, at its instruction's contended T.  **LZ2** the boundary (K outside step(); four refusals).
RX2's giant spread is gone (no T at the call); RX3 runs the giant through step() with the lazy writes' order checked
at each ISR and an ISR flipping a byte read between the exact and the contended point (rvMoved 1).

Exact GIVEN the ISRs' T.  The engine's own isrCost is the machine's uncontended ISR T (M7.99e (b)), zero contention on
the giant's ISRs, so the giant is exact in play; on the wrap, `$8F4C` r1_lead and the umbrella's head the ISRs'
own contention (<= 2,661 T a block) would remain -- the engine-wide gap.  Still K: the wrap, `$8F4C`, the head, `$94C2`.

### M7.101: the storm wrap's block, and the instruction in progress at the point

The wrap (`$A09A`, BB_EXT_BLOCKS.wrap) is `lazy` too.  Its head `$A09A..$A0BE` is 172 T with ONE contended access: the
`$A0B0 OUT ($FE),A`'s I/O cycle, 100 T in (`BB_EXT_CP.WR_OUT`; a probe from `$A09A` on round1_48 and r50_48,
`scratchpad/lazy/wrhead2.py`); the reveal's routines carry the programs M7.99c gave them.  `paid` is 90 here (the idle
path BB_PASS_T holds) -- lzStep subtracts it.

**The instruction in progress at the point.**  The machine takes an interrupt at the END of an instruction, so the
accesses of the instruction straddling the boundary are made BEFORE the ISR, at phase 0.. (top border, no wait).
M7.100's lzSeg put every access past the point after the ISR; behind a ~53,500-T odd ISR that is the contended area
(r50_48 at phase 65520: 94 T too many).  Each program access now carries its T into its instruction (`bbAcc(cp, ins,
k)`, `cp.k`; `lz.ins`), and lzSeg breaks at the first access whose INSTRUCTION starts past the point.  The k values:
store 4, `LD A,(HL)` read 4 (`RD`), `LD A,(nn)` read 10 (`RD_NN`, `$80E7`), OUT cycle 8, an LDIR iteration's d, the
digits' from bbDigitsCp's own instruction list.  `tools/isrcarry.py` now records the machine's per-access k (`acc_k`:
a digest of `T:k;` over the plain run and the k histogram).

Gates: **LZ3** (34 wrap rows, machine ISR walls injected: acceptances, end wall T, main_delay -- all exact; the block
entered `HEAD` + the OUT's wait before the row's `$A0BE`, HEAD = the storm fixture's wrap tick less the reveal less the
JP's 10; 10 forced phases no head can reach -- after the OUT's wait `$A0BE` lands only 6..7 T into a contended cycle
-- run with the head's program out, counted), **LZ4** (the engine's `T:k` stream = the machine's on giant fallcandy /
peachfall and wrap round1_48 / r50_48, ~50,700 accesses each), LZ2 (+ an access with no instruction THROWS).  RX2's
wrap spread is retired (no T at the call).

Exact given the ISRs' T.  In play the engine's isrCost is the machine's UNCONTENDED ISR T; the wrap's ISRs have
contention of their own (M7.99e: <= 883 T an ISR, 477..2,624 T a block) -- the engine-wide gap, DECLARED.  Still K:
`$8F4C`, the umbrella's head, `$94C2`.

### M7.102: the treasure room's block, a clocked routine's program at its close

`$8F4C` (BB_EXT_BLOCKS.perfect) is `lazy`.  Its program, measured against isrcarry's plain runs (`acc_k`: every access
k = 4, 41,568 on lastdia81 / lastdia82, 41,512 on r1_lead): the award's HUD glyph stores (`$8052 LD (HL),A`; 96 / 40),
then per draw the nine "PERFECT !" characters' 16 row stores each (`extDouble`'s DOUBLE_ROWS, `LD (HL),A`) and `$994F`'s
18 attribute stores (pf_runs) -- 162 a draw x 256.  pf_end has none (the stack is above `$8000`).

THE AWARD IS CLOCKED: `pf_award`'s writes are stamped from the award's clock (`awClk`, M7.95), and its glyph stores are
only known once `treasureAward` has run -- AFTER its hook.  So `extRt` pushes a clocked routine's program at its CLOSE
(`lzPush`, at the next routine's hook; awClk.cp is the giant's log, each a store + ST); a clocked routine with no log
THROWS.  The award's DI window goes onto the frame clock from its EXACT offsets ([4, `$8F78 LD B,0`'s end]) for
`lzWindows` to put on the contended clock -- the K mirror kept its contended ones.

**LZ5**: isrcarry's 51 perfect rows (own phase and sixteen forced, three worlds) and perfecttime's eight with a boundary
inside the award's DI window, each from perfecttime's seed at `$8F4C`, frames driven as step() drives them with the
machine's ISR wall T: 1,819 acceptances at their boundary, the 13 lost interrupts, the DI window equal to perfecttime's
contended window on its 43 runs, the end's wall T and the main line's T (exact + delays) on all 59 -- first try.  PF1b
keeps measuring the K stretch (the model outside step()) with the flag down; PF2 logs the lazy writes (`lzHold`).

Exact given the ISRs' T.  The natural perfects' ISRs are uncontended (M7.99e), so lastdia is exact in play; r1_lead's
carry <= 275 T an ISR (2,587..2,661 T a block) that the engine's isrCost does not charge -- the engine-wide gap,
DECLARED.  Still K: the umbrella's head, `$94C2`.

### M7.103: the umbrella's head, to its HALT

The umbrella's head (`$88C0 JP $A110` .. `$A116 CALL $A0E0`, the first flash, `$A119 EI`; BB_EXT_BLOCKS.umb_head) is
`lazy`.  `u_head`'s 55 T touch no contended byte: isrcarry's `head:natural` plain run makes 1,409 contended accesses
(`acc_k` 1,408 x k4 + 1 x k8), exactly u_flash's program since M7.99d (the OUT's ULA cycle at 8, each cell's read and
store at 4).  The flash's OUT at `$A0E0` is queued for lzSeg (`lz.outs`, at its instruction's start) like the reveal's
`$8C4E`.  The block ends at the HALT (29,000 T exact); umbStep then spends the rest of that frame as before -- the
segment model of M7.98 is unchanged, only the head's own frames are now timed from their actual phase.

**LZ6**: isrcarry's 17 head rows (the natural collect's own phase 66,699 and sixteen forced), each from `$88C0` at the
row's phase, its frames driven as step() drives them with the machine's ISR wall T: the 8 acceptances at their boundary,
the HALT at the machine's wall T and the main line (exact + delays) on all 17 -- first try; 9 rows reach the HALT
before their first boundary.  The OUT is logged once at HEAD (phase 0, `$88C0` AT the point: HEAD into the next
frame, after the ISR).  LZ4 gains `head:natural` (8 sources).  UM3 (through step(), round 1) is unchanged: 26 frames,
15 lost, one ISR between the head's held writes.

Exact given the ISRs' T.  The head's one ISR carries 92..96 T of its own contention (M7.99e) that the engine's isrCost
does not charge -- the engine-wide gap, DECLARED.  Still K: `$94C2`.

### M7.104: `$94C2`, the EXTEND completion -- the last K block

`$94C2` (BB_EXT_BLOCKS.extend, 17,107,864 T exact on extcomp, 245 frames) is `lazy`.  Every routine carries an access
program.  A scratch probe of extcomp's plain run (`scratchpad/ext/probe.py`, every contended access with its PC) shows
where the 62,507 come from: the repaint's LDIRs, `$7F80`'s fetches, the derive's, the lives' and the banner's (`$8065` /
`$8067`) stores, the `$8C4E` OUT's cycle, `$995C`'s 28 runs, and each item draw's ink cells (`$8765 LD A,(HL)` 21 T
before `$876A`'s store, BB_EXT_CP.INK_RD) and blit rows (`$A306` / `$A30B LD A,(DE)`, the sprite at `$5D00..`, always
contended, 11 T before `$A308` / `$A30D`'s store, BB_EXT_CP.BL_RD; a row aimed into the ROM keeps its reads and loses its
stores).  The expiry's four cells (`$8777 LD (DE),A` into the attributes) and erase rows are stores at 4.  The entry, wipe
(the shadow's), stride2, res7, records, award, spin and gate_on touch no contended byte.  The engine's program matched
the machine's first time, access for access.

**The machinery change: DI windows a segment at a time.**  The reveal's window (`$8C14` DI .. `$8C4C` EI + 1) opens
145,000 T in, two frames past the first interrupt point.  lzWindows used to put every window on the first frame's clock
(and throw otherwise).  Now it only checks the windows (in order, each closing after it opens -- or THROW) and hands
them to `lz.wins` on the exact clock.  lzSeg puts each one on the frame clock in the frame it opens in (open <= that
frame's point, so intLost sees one opening AT the point), walking its close on past the point: no ISR is taken inside
a window, so its waits run on from the same phase.  A block that ends with a window not yet opened THROWS.  The
reveal's window is pushed on the exact clock when lazy (`wc`, extRt).

**Three new isrcarry sources** (`tools/isrcarry.py`, EXT_VARIANTS, own phase only): extendtime.py's tick (items that
expire, bands into the ROM), tickflood (the flood's erase and blit) and storm (`$8728`'s blit).  Their exact T is
extendtime's cost on the same world (17,268,572 / 17,147,865 / 17,352,451), so the two tools agree on the worlds.
`measure` 23 s; `verify --jobs 6` MATCH; the old sources' data unchanged.

**LZ7**: 8 runs (extcomp's own phase and four forced, the three variants at their own), each from `$94C2` on E1's world,
its frames driven as step() drives them with the machine's ISR wall T: 1,955 acceptances at their boundary with both
gates shut, the 3 or 4 lost interrupts lost (the reveal's window put on the clock in frame 2), `$8D09` at the machine's
wall T and the main line (exact + delays) on all 8.  The OUT is logged once, at the window's close.  Phase 0: isrcarry
arms `$94C2` with IFF 0, so the entry's own boundary passes untaken -- the row is entered a frame before its point.
LZ4 gains the four extend programs (12 sources); IC 156 runs / 12 sources / 3,900 ISRs, and the engine's isrCost is
the machine's wall T on all 1,955 extend ISRs.  E5 (through step()) now ends the first frame AT the point (lazy), E11's
windows are the lazy ones (one entered 50 T short gets its entry window in the next frame, 54 short AT the point), C3 /
LZ2 list all five interrupts-on blocks as lazy.

Exact given the ISRs' T (extend's are uncontended).  **No block keeps BB_EXT_K inside step() any more**; K is only the
model outside step() (unit calls, budget Infinity), as before.

### M7.105: a DI window opens 1 T into its DI, not at its end

M7.104's reviewer asked whether an interrupt whose line rises 1..3 T into a DI is lost on the machine and taken by the
engine: every window except the storm payload's opened at the DI's END (`DI_AT` 4 from the hook, `DI_ENTRY` 54), the
point where IFF reads clear.  MEASURED (scratch `scratchpad/distraddle/probe.py`, then `tools/isrcarry.py` STRADDLE):
the phase iterated to a fixed point that puts a frame boundary d T after a DI's START, the machine contended with
interrupts on.  `$A9B5` (giant, 2 worlds), `$8F4C` (PERFECT, 3 worlds), `$8C14` (inside `$94C2`): LOST at d = 1..6,
TAKEN at d = -2..0 (accepted at the DI's start, the end of the instruction before).  The line is sampled at an
instruction's end; at d = 1..3 the DI is the instruction in progress and its end has cleared IFF.  The storm payload's
measured window (BB_STORM_P.DI 160 = its DI at 159 + 1) was already so.

**Engine:** `BB_EXT_W.DI_OPEN = 1`, every window from the DI's start + 1: the giant's award, the PERFECT award, a later
umbrella flash (`$A121`), the reveal windows from `$8C14` / `$9031` / `$A11B` (extDiFrom), and `$94C2`'s prologue
(`DI_ENTRY` [51, 129], its DI at 50).  `DI_AT` stays 4 where it is the DI's T (the release's duration).  Reach in play:
~3 T in 69,888 a window -- a rare lost frame the engine used to run.

**Gates:** isrcarry gains 18 rows (three phases, d = 1..3, for each source with a DI: giant x2, perfect x3, extend), 174
runs / 4,929 ISRs, all exact on the machine-side replay; the old rows byte-identical (backup
`scratchpad/distraddle/isrcarry_fixture.m7104.json`).  LZ1 (52 runs, 18 lost), LZ5 (68, 22 lost) and LZ7 (11, lost
3/3/3/4/4/4/4/4/3/3/3) run the engine on them: with the old rule (`DI_OPEN` 4) each straddle row fails ("ISR 0 accepted
at 69896, the boundary at 1"), so the rows pin the edge.  The window-start expectations of PF1, PF1b, RX1, RV1, UM1,
LZ1, LZ5 and E11 move from the fixtures' DI end to `di_end - 3`; E11's "opens AT the point" probe is now 51 T short
(50 short is not lost).

### M7.106: the countdown's advance comes in the pass that straddles its interrupt

M7.97 declared one extra giant tick in the round advance's frame: the machine's advancing pass ran `$A824` in the frame
before the interrupt and `$8E3A`'s countdown after it, and the port's ATOMIC pass read the old timer and advanced one
pass later (TRAPS #90).  It is not the giant's: a latched `$8E3A` ends EVERY pass with `$8F29 LD A,($8DBE) / DEC A /
RET nz / $8F2E LD A,($8DBD) / CP $77 / RET c`, and the timer is the ISR's, so every countdown advance is decided by
where the interrupt making `$0177` falls inside a pass.

**Measured** (`tools/cdstraddle.py` -> `build/cdstraddle_fixture.json`, verify MATCH ~40 s): five worlds (round1_48,
r6_48, r10_48, r20_48, r30_48), the round cleared 0..5 frames after the load, no keys, contended, interrupts on, to
`$97F8`.  ALL 30 advances come in the pass that STRADDLES the interrupt: the pass began 14..4,600 T before the
boundary, its `$8F2E` read 4,237..7,694 main-line T in; the read in the pass before found `$0176`; `$8F2E` 22 T after
`$8F29`, `$97F8` 68 T after `$8F2E`; `$97F8` entered 471..7,015 main-line T after the boundary.  The port advanced
0 of 30 that way: always a whole pass (~6,000 T) late, after a full chain in the new frame.

**Engine:** `roundClearCountdown` places each read on the frame clock (`cdPos`: what the pass has spent, plus what it
will charge before the read -- `BB_CD.E3A` 426, the skeleton to the end of `CALL $8E3A`; the wrap's `$7FFC`;
`BB_PASS_REST`; the callees' charges so far; `$8E3A`'s own T -- and `BB_CD.LO` 22 to `$8F2E`).  A read whose
instruction starts at or after the interrupt point (`cdPast`: the M7.105 edge, the harness accepts at an instruction's
end) reads the timer the ISR will leave, the two bytes separately (a torn `$00FF` read is modelled).  An advance that
needs it CUTS the pass (`cdCut`, chainWalk returns 'cut'): step() charges the pass as a clear, spends it (it must end
the frame -- else THROW), counts it, and the ISR runs; the next step's `cdResume` checks the timer is the one read
(else THROW) and makes the advance before any pass, `$97F8`'s entry where the cut pass's charge ended.  A DI window
over the point is not guessed (`cdDiSkips`, counted).  Outside step() (budget Infinity) nothing is past.

**Gates:** CD1 (the fixture: 30 / 30 straddle, the reads' spacing = `BB_CD.LO`), CD2 (through step(), round 1 from the
title cleared: the read 926 T past the point, cut, `$97F8` in the next frame at 994 main-line T -- inside the machine's
471..7,015; the atomic pass enters it at 6,988, a pass later), CD3 (the edge: at the point seen, 1 T before not; the torn
pair; a DI window counted; outside step(); a resume on another timer throws).  GS2: the extra body is GONE -- 375 / 375
bodies, row for row the machine's.  DECLARED: the read's place is the port's pass clock (the skeleton exact, the
callees their charges, the 78-T rest unplaced, put before it); only the countdown's reads see the interrupt -- the rest
of the pass is still atomic (TRAPS #90's general case).

### M7.107: the pause's spin on the frame clock

`$8FE7` (chain entry `$8D28`) arms on SYM SHIFT: `$8FF6 DI`, `$8FF9 OUT ($FE),4`, then `$8FFB LD A,$FE / IN A,($FE) /
RRA / JR c` until CAPS SHIFT is down, then `$9003 OUT ($FE),0 / POP AF / CALL $8E0A (RET) / $9009 EI / $900A RET` and the
chain goes on at `$8D2B`.  Until M7.107 the polls were DECLARED uncharged, and the port resumed the suspended pass at
T 0 of the release frame with the last ISR's cost still in that frame's budget.  It also charged the suspended pass's
skeleton and its 78-T rest twice (once at the arm, once at the resume).

**Measured** (`tools/pausespin.py` -> `build/pausespin_fixture.json`, verify MATCH, ~15 s on 18 jobs): 249 runs.
108 are natural cuts on six worlds (round1_48, r6_48, r10_48, r20_48, r30_48, boss), with SYM from a boundary 1..6
frames after the load and CAPS from the first boundary after the spin + 0 / 1 / 3 frames.  69 hold SYM and CAPS
together, 33 of them FORCED 100..210 T before a boundary.  72 are FORCED cuts, with the arming `$8FE7` moved 40..110 T
before a boundary by moving the clock and nothing else.  All are contended, with interrupts on, and keys change at
boundaries after the instruction that crosses one.  The tool asserts the model on every poll of every run:
- a poll is 34 T, its IN's I/O cycle 8 T into it (A = `$FE`: N:1, C:3);
- the release poll is the FIRST whose IN starts at or after the boundary CAPS is down from;
- `$8D2B` comes 88 T after that IN, plus the IN's delay and the `$9003` OUT's (its I/O cycle 26 T after the IN, 8
  into the OUT).

The arm is exact instruction by instruction, with two contention points:
- the gate's `IN A,($FE)` runs with A = `$7F`, a contended high byte, so its I/O cycle is C:1, C:3 (7 and 8 into it);
- `$8FF9`'s OUT has its I/O cycle 8 into it.

Two edges, both the M7.105 rule:
- an arm instruction starting at or after the boundary waits for the ISR. With `$8FE7` 85 T before the boundary the
  DI starts on it and the ISR is taken; 86 T before, the DI starts 1 T before it and the interrupt is lost;
- the window `[DI + 1, $8D2B]` loses an interrupt whose 32 T it covers. The `$900A` RET ends 22 T in: taken; 32 T in:
  lost.

No interrupt is taken from the spin to `$8D2B`, and on every cut run the interrupt at the release boundary is lost and
the next one is taken.  The release always lands 4..31 T into the frame, and `$8D2B` 88..100 T after its IN.

**Engine:** `pauseGate` inside step() puts `$8FE7` on the pass clock with `pausePos`, cdPos's rule: what the pass has
spent, the callees' charges so far, `BB_PAUSE_SPIN.HEAD` 120 (the skeleton `$8D0C`..`CALL $8FE7`), the wrap's `$7FFC`,
and `BB_PASS_REST`.  `passCharge('paused')` ends the arming pass there.  `spinStep`, called once a frame, does this:
1. It walks the arm's instructions (`ARM`); one that starts at or after the point returns 'isr', the ISR runs, and
   the arm goes on next frame.
2. It polls on this frame's clock with `bbUlaDelay`; each poll whose IN starts before the point reads this frame's keys.
3. A frame that ends in the spin ('held', `spinHeld`) has no pass and no interrupt: the next frame's `isrCost` is 0
   and its budget is the whole frame.
4. A release logs the OUT and resumes the pass at `$8D2B`, in this frame. The DI window is pushed for `intLost` only
   when it covers the point.
5. The resumed pass is charged the skeleton after `$8FE7` (passcost's 479 less HEAD) and its callees: no second rest.

Outside step() the old untimed path stays.

**Gates:**
- PZ1: the fixture's facts.
- PZ2: all 249 runs replayed through `spinStep` from the machine's `$8FE7`. The DI, both OUTs, every poll, `$8D2B`, the
  ISR before the DI (24 runs) and the interrupt lost or taken (6 lost) are all exact.
- PZ3: through step(): the arming pass ends at `$8FE7`; three held frames with the timer standing; `isrCost` 0; the
  resume at 119 main-line T, charged 479 - 120 + callees.
- PZ4: `$8FE7`'s place (the machine's `$8D0C`..`$8D25` 86 + two CALLs), with the wrap; the poll edge, constructed (an
  IN starting AT the point is held, then released next frame; 1 T before, released now); an arm FORCED 40 T before
  the point runs the ISR in the arming frame and the DI in the next.

Two mutants were found to be equivalent and dropped:
- the 'isr' break in step()'s loop, because the loop's own condition stops on 'isr';
- the window opening at the DI rather than 1 T in, because a DI that ran always starts before the point.
- SFX11: its two edges now land at their frame-clock T.
- SFX11b: outside step() the untimed path keeps its edges (the caller's clock + 96, the release step + 33).

DECLARED: `$8FE7`'s place is the port's pass clock (the skeleton exact, the callees their charges, the 78-T rest put
before it), as the countdown's is.

### Before M7.68 (kept for the record)

    odd  = ODD_OVERHEAD + (what the passes charged themselves) + BB_ISR_ABSENT_ODD
    even = EVEN_OVERHEAD + MGR_FRAME_FIXED + BLOW_CHECK + pool x PER_BUBBLE

`BB_ISR_ABSENT_ODD = 24526` is the round-1 median of (measured odd ISR) minus
ODD_OVERHEAD minus the `$A3AD` cost the engine's own empty table produces.  It is
the `$AA60` pass -- which the engine does not run at all -- plus the three round-1
enemies it would update.  `frameLedger()` reports it every frame alongside
`tcost`, so the split between "measured" and "absent" is visible rather than
buried.

## Still not measured, and the scene each needs

0. (M7.68) the `$AA60` handlers' own T, path by path -- CLOSED: `$AB38` M7.69, the walker and the
   eight types M7.70, the corpse flight `$8A78` M7.72 (all uncontended instruction sums, exact).

1. `$B6D8` burst-with-contents (a bubble carrying an item or enemy): +5,893 to
   +18,582 T, the single largest residue.  `extcomp` and `ellight` already hold
   the scene -- decode, do not capture.
2. `$B977`/`$B9B6`/`$B984` player-bubble contact (push, touch-pop, ride): up to
   +10,386 T.  Reachable today from a key-driven blow.
3. `$BE80` capture commit: +4,707 T, seen once.  Needs an aimed blow into an enemy.
4. `$B88D` wind re-roll: the +298 T is exact but the new direction comes from
   `LD A,R`; needs the declared RNG substitution like the other sites.
5. The eight enemy-type handler costs are per-round, not per-behaviour (+-400 T
   per slot across states), and no state runs a type both singly and doubled.
6. The respawn frame (~5,950 T) and the invulnerability flash terms (305/314,
   94/103/83) have **no natural evidence in any 48K state** -- no state has
   `(IY+$5A)` bit 3 set on either player.  They are transcribed, not exercised.
7. (M7.73) `PER_BUBBLE` is retired: `$B62C`'s skeleton is exact, its ARMS are PROVISIONAL
   medians (`BB_B62C_ARM`).  (M7.74) The blow `$BD2C` is exact (`BB_BL`); its nested pop and award stay
   provisional.  (M7.75) The draw `$B9E7` is exact (`BB_DR`).  (M7.76) The rise `$B836` is exact (`BB_RI`):
   items 2 and 4 (the contact, the re-roll) are inside it and CLOSED as costs.  (M7.77) The pop `$B6D8`
   is exact (`BB_PO`) from all three callers -- held, agepop, the blow's steal -- its award and a live
   enemy's birth PROVISIONAL, a ROM-centred chain window DECLARED.  (M7.78) The escape `$B679` is exact
   (`BB_ES`).  (M7.79) The travel `$BDFE` is exact (`BB_TR`), with the capture, and a live enemy's birth with
   it: every arm of `$B62C` charges itself.  (M7.80) The award `$80FA` is exact (`BB_AW`): nothing PROVISIONAL
   is left inside the even pass, and its ledger has no `.prov`.  The
   arms were made exact as `$AA60`'s handlers were
   (M7.69..M7.72); items 1..4
   live inside them -- the pop `$B6D8` in held / agepop and in the blow's full-pool spawn, the contact
   and the wind re-roll in rise, the capture in travel.  Sizes (distinct instructions executed): blow
   60, rise ~460, escape ~200, the pop ~520, travel ~1,000 with the capture and the corpse birth.  The
   travel arm reaches the same draw (`$BEAC JP $B9E7`, `$BE58`): its T is `BB_DR`'s there too.
8. ULA contention: modelled nowhere, declared everywhere.  The overlay measured
   by the workflow is phase-dependent and PROVISIONAL.  (M7.99c: the reveal from
   `$9031` / `$A11B` is timed access by access from its entry's phase -- exact; every
   other block keeps a fitted K.  M7.99d: so are the umbrella's later flashes, `$A121`.)
9. A two-frame overrun is still unreached.  The worst interrupt seen is 79,976 T
   against a frame of 69,888; 0.55% of interrupts overrun one frame.
10. `$8C28`, the reveal, costs 213,312 T uncontended (215,535 on r20_48; 254,819 /
   258,160 contended) and the port charges it NOTHING at any entry (`$A0BE`, `$9032`,
   `$A9D7`, `$A11C`, `$8C14`'s fall-in) -- a gap since M7.14, first declared by M7.52
   (`build/beeper_fixture.json` 'reveal').  Entered after a DI (`$9031`, `$A11B`,
   `$8C14`) it runs with interrupts off to its own `$8C4C EI`, so the machine loses
   about three frame interrupts inside it; the port loses none.  **M7.57 closes the
   `$8C14` entry**: inside `$94C2` the reveal is charged its exact T stretched by the
   fitted contention, and step() LOSES the interrupts whose 32 T fall inside the
   DI window (`intLost`; MEASURED 244 interrupts in 247.3 frames).  **M7.86 closes the
   `$9032` entry** (`tools/revealentry.py` -> `build/revealentry_fixture.json`): `$9031 DI /
   CALL $8C28` runs the reveal through the same mirror on `BB_RV_SCRIPT` ('release' 21 T, the
   six hooks, the OUT's tail 29 to `$9035`), EXACT against the machine on r50_48 / r10_48 --
   the reveal 214,246 / 214,138 T, every hook, the 7,172 writes by address and T (RV1); the
   derive gains 8 T a SOLID colour-shadow cell (`DERIVE_SOLID`; always 0 inside `$94C2`,
   whose shadow is wiped).  The DI window [4, $8C4C EI + 8] on the contended clock: the
   machine loses 3 interrupts (phases 0..21,840) or 4 (26,208..65,520), the engine the same
   ones on 32 of 34 runs; phase 26,208 on both worlds loses a fourth on the machine (its
   window 254,012 T, the K model's 252,241) -- DECLARED, the contention spread, pinned
   (RV2); the contended $8C28..RET is -6,008..+4,307 T off the machine's.  The pass waits at
   `$8D2E` while step() drains it (RV3).  The release path's other instructions (`$902E`,
   `$9035 EI`, `$9036 RET`) stay in the flat BB_PASS_T.  **M7.94 closes `$A0BE` and `$A9D7`**
   (the fixture now carries a SEED for both, the write stream split at `$8C28` with T from it):
   both run on the same mirror with interrupts ON -- `BB_RW_SCRIPT` ('wrap' `$A09A..$8C28`,
   BB_STORM.WRAP 172, the block spending its T less the idle 90 BB_PASS_T holds; the wrap's own
   82 is no longer spent apart) and `BB_GR_SCRIPT` ('giant' `$A9B5 DI .. $A9D7 JP`: 120 + the
   award's exact T + 54 = 4,355 on both giant worlds).  EXACT against the machine (RX1): the
   reveal 213,312 / 214,246 (wrap) and 214,049 / 214,754 (giant), every hook, every write from
   `$8C28` by address and T.  FOUND: the giant's `$A9CB CALL $80FA` ran `addScore`, the arithmetic
   alone (no HUD digits, no player guard) -- now `scoreAward`; `addScore` folded into `award()`.
   The award window [4, the JP's end] rides the frame clock: the 12 forced boundaries inside it
   are lost on the machine and the engine alike (RX2); its writes land at the call (DECLARED,
   counted `gaEarly`).  No window from `$A0BE`.  THE ISRs INSIDE (4..6 on the machine) RUN in
   step() while the block's writes are held: each sees every write stamped before its interrupt
   point and none after, and a later held write lands over what it drew -- the machine's order
   (RX3).  What the port cannot give, COUNTED: the reveal reads its inputs at the call, so a byte
   an ISR changes before the machine's reveal reads it is stale (`rvMoved`, a read stamped with its
   routine's next write; 0 on round 1 through step()); and the K model's contended $8C28..RET is
   -10,619..+7,299 T (wrap) / -6,038..-3,926 (giant) off the machine's main-line T (pinned).
   **M7.98 closes `$A11C`** (the umbrella's `$A110` block, `tools/umbrella.py` -- below): every entry of
   the reveal is now in time.  **M7.99c** times the two DI entries (`$9031`, `$A11B`) by their contended
   accesses from the entry's phase: the lost interrupts are the machine's on every measured run (above).

## A harness trap found on the way

`rom_writes` never increments under `CMIOSimulator` -- SkoolKit's C simulator
enforces the ROM boundary itself without calling back into Python.  It cannot
distinguish "wrote into ROM and it was dropped" from "never went there".  The
write LOG is complete and correct for `>= $4000`, so the oracles are sound.
TRAPS #38.

### M7.108: the join timed a frame at a time

M7.99b made the join's tail (`$9998 JP $7FC0`: the RRDs, `$7FD7`'s clear, the lives panel, the two text rows, the two
awards, `$7FFC`'s attributes -- 42..59K T, interrupts on) and declared its writes AT THE CALL: the pass was atomic, so
an interrupt inside the tail ran after all of them, and the rest of the pass (`$915F` on) ran before that interrupt.

**Measured** (`tools/isrcarry.py`, three 'join' sources: round1_48 and r20_48 with '2' held, round1_48 with P1 out and
'1'; each reached by playing on, contended, to the first `$9961` that joins; own phase and sixteen forced): the plain
run's access program replayed from the entry's phase with the machine's ISR walls gives every acceptance and the RET,
51 of 51.  The program, PC by PC (scratch `scratchpad/join/trace.py`): `$9969 IN A,($FE)`'s I/O cycle (34 T in, 8 into
it; A = `$F7`), EVERY instruction of `$7FC0..$7FFF` -- the code lives in contended memory -- the clear's 64 stores
(`$AA4A`), the panel's reads and stores, 456 glyph stores (`$8052`), and `$8017`'s 61 attribute stores.  The awards
draw no glyph on these worlds.  The join's ISRs carry contention of their own (<= 285 T a run): the engine-wide gap.
The source rows store a seed (the bytes the plain run reads) for the engine's replay.

**Engine:** inside step() `joinCheck` hands a taken join to `joinBlock`: BB_EXT_BLOCKS.join (`lazy`), entered at
`joinPos` -- cdPos's rule, the skeleton to `$9961`'s entry `BB_JOIN.AT` 171 (86 + five CALLs) -- with what the pass
spent before it kept in `passPre`, which passCharge takes off the pass's charge.  The routines (`joinModel`):
- `j_head`: the spawn's and the commit's writes at `BB_JOIN.W2` (P2) / `W1` (P1) from the entry, the IN's cycle; to
  M7.99b's `$7FC0` entry;
- `j_hud`: `$7FC0`'s RRDs, every fetch, `HUD_T` 425;
- `j_clear`: the 64 stores and `$7FDF`'s CALL fetch;
- `lives`: extLives' model and program;
- `j_text`: BB_BUILD_HUD's text offsets and fetches;
- `j_aw` x2: the award on its clock (awClk, base 24), a CLOCKED routine pushed at its close (`hudAward`);
- `j_attr`: the runs to `$801C`'s RET -- `$9961`'s.

The run's T is the block's: smallRun charges `$9961` nothing.  A block past its interrupt parks the pass at `$8D34`
('join', chainWalk) while step() drains it; mainLoop resumes there.  Outside step() M7.99b's path stays (writes at the
call, joinW).

**Gates:**
- LZ8: the 51 rows, each from `$9961` seeded with the source's seed, frames as step() drives them with the machine's
  ISR walls -- every acceptance, the RET's wall T, the main line's delays exact; 33 runs past their first interrupt;
- LZ4: the three join programs access for access;
- JT6: the jointail fixture's 28 runs inside step(): every write [T from the entry, address, value] the machine's, in
  its order (762..1,075 a run).  The awards' RLDs (`$818A` / `$819E` / `$81B2`) are on the award's clock at the
  machine's T but their bytes are not rewritten -- DECLARED: each byte ends as it began and no ISR reads a score;
- JT4 (re-aimed): through step() the join is one block, its clear and panel at the machine's [T, address, value];
- JT7: through step(), a frame begun 30,000 T in: the block meets the interrupt with writes held, the pass waits at
  `$8D34` with `$915F` not run, the ISR runs, the next frame drains the block and the pass resumes at `$915F`,
  charged skeleton + rest + callees less passPre (the callees so far + AT + BB_PASS_REST).
- JT8: `$9961`'s place term by term -- the machine's `$8D0C..$8D25` 86 (pausespin's runs) + five CALLs + the rest,
  and a wrap pass's `$7FFC` (the match run's two survivors, AT 172 and the wrap left out, pinned here).

DECLARED: `$9961`'s place in the pass is the port's pass clock (cdPos's rule: BB_PASS_REST put before it); the join's
ISRs' own contention is not charged.

### M7.109: the title's ring on the frame clock

M7.42 ran the sparkle ring (`$9768..$978F`, interrupts on, ~374 iterations a frame) frame by frame with each
iteration charging its PATH's contended MEAN (title_wait's path_T: 97.60 / 208.19 / 221.92), so the iteration count a
frame was a band and WHERE a frame's interrupt fell inside an iteration was not modelled: the attribute file at a
boundary could not be the machine's (M7.64's load gate skipped the title's rows for that).

**Measured** (`tools/ringtime.py` -> `build/ringtime_fixture.json`): the real load -- loadpath's kbd_sinclair drive from
boot.pkl's `$F5BC` -- to its first `$9765` (phase 22,702; the cursor_kempston drive arrives at the same phase with the
same PRNG `$2CCD`, only R differs), and from that state its own phase, 21 forced and six presses, 30 boundaries each,
sampled as loadpath samples.  A replay of each iteration's instructions on the frame clock -- the contended accesses
BIT 6,(HL)'s read and internal cycle at 8 / 11, the store at 4, the IN's I/O cycle at 8 (port `$F7FE`: N:1, C:3), the
code, the PRNG at `$FE85` and the stack uncontended -- with the interrupt taken at the end of the instruction in progress
and the ISR's T (488 odd / 493 even: the engine's isrCost) gives every boundary's iteration count exactly, on all 22
runs.

**Engine:** `BB_RING` -- the six programs (skip / gate / write, plain and wrap), each instruction `[T, contended offsets,
effect, PC]`; the effects are the PRNG's store `'p'` (`$FE91`), the write `'w'` (`$9780`) and the key test `'k'`
(`$9783`).  frontFrame takes a new iteration's state at once (titleRingStep(hold): the path, the cursor, the draw) but
HOLDS the draw's store and the write (`ringP`, `ringW`) for their instructions, runs the instructions while the frame
lasts, and carries the rest (`ringCur`) past the ISR.  The arming key test swaps the spin's CPL / AND / JR z for the
arm's own tail (34 / 40 T to `$979E` / `$9790`), where ARM_T begins.  `BB_TITLE.COST` / `WRAP_T` are gone;
`titleIter` is gone (titleRingStep and titleKeyDecode are the spellings the scheduler and the gates share).

**Gates:** RT1 -- 22 runs, 660 boundaries: the iterations begun, the attributes' CRC, the PRNG, the instruction the
interrupt was taken after, the ISR T; 45 boundaries with a write still to come, 302 with the PRNG's store, 528 with the
key test.  RT2 -- the programs: their sums are path_T's 94 / 204 / 217 (+2 on the wrap), their PCs and effects, their
contended points.  RT3 -- six presses: the arm in the machine's frame, at its phase and iteration count, one with
`$9765`'s LD HL ending inside the interrupt's window.  M7.42's rate row now reads 374.05 a frame (the machine 374.075).

DECLARED, still: the paint (`$970F..$9764`) is drawn at once and charged as PAINT_T, so a page's ring starts at the
port's phase, not the machine's (the next increment: the paint in time); the starfield's inks are R's stand-in.
(M7.110 closed the first: below.)

### M7.110: the title's paint in time

Until M7.110 the paint `$970F..$9765` -- the CLS, the 1,024-dot starfield, the four double-height strings, the credit
line -- was drawn at once and its T charged as a debt (`BB_TITLE.PAINT_T` 634,920 = loadpath's 639,332 less nine ISRs),
so the ring began at the port's phase (DEPARTS `paintInstant`).

**Measured** (`tools/painttime.py` -> `build/painttime_fixture.json`, ~8 s): the real load (loadpath's kbd_sinclair drive)
to its first `$970F` (phase 9,678).  The plain run to `$9765`: 65,156 instructions, 589,318 T, 65,738 contended
accesses -- the CLS's 6,911 LDIRs (accesses at 8, 11, 14..20), each dot's two stores (`$FEB0` at 4, `$FEBA` at 7), the
strings' and credit line's stores and attribute runs (4); code, strings, PRNG, stack and the ROM's glyphs uncontended.
The stream is the SAME at every phase (17 checked), and isrcarry's carry test is EXACT on all 17: the main line replayed
with each ISR's T (488 odd / 493 even, uncontended, gates closed) gives every acceptance and the end
(`scratchpad/paint/probe.py`).  R: each ISR moves it 52 (odd) / 53 (even); given R at `$9712` (the first `$9715` read
is R + 3) all 2,048 R reads are reproduced on 5 phases (`rprobe.py`; the tool asserts every ISR's step).  From the
`$970F` state: its own phase and 18 forced, every boundary to four past `$9765` -- the paint's instructions done, the
ring's iterations begun, the attributes' CRC, the bitmap's CRC with the strings' 1,328 cells zeroed (the glyphs are the
ROM's, which the port does not ship: the cells, MASK, are where the machine's `$8052`/`$8065`/`$8067` store), the PRNG.

**Engine:** `bbTitlePaintProg(ram)` builds the program from the disassembly ([T, contended offsets, effect, PC], the
strings' lengths read from RAM); `titleEnter(phase)` puts a cursor up (`tpaint`) and frontFrame runs it an instruction
at a time on the frame clock, the ring's way, then the ring in the same frame.  Effects at their instructions: the
LDIR's byte, the walk armed at `$9712`, per dot the ink, its `$FEBB` store, the PRNG's store, the cell at `$FEAC`, the
two stores; the strings' writes recorded once at `$9729` (titleText / creditLine over a copy, `tpaintText`) and landed
at each store.  `isr()` stalls the walk by `BB_TPAINT.ISR_R` while a paint is up.  `starDot()` is gone (`starPos()` +
the two store effects); `titlePaint()` and `starfield()` are the same program's effects at once -- the gates' drivers,
back in both censuses.  `BB_TITLE.PAINT_T` and DEPARTS `paintInstant` are gone.

**Gates:** PT1 -- the program against the plain run (count, T, accesses, CRC of every PC:T:k), its effects' counts.
PT2 -- 19 runs, 249 boundaries (173 inside the paint): all of the above exact, `$9765` in the machine's frame at its
phase (natural [9, 22,702] -- ringtime's own arrival), the port's string stores on the machine's 1,328 cells, the ISR
T.  PT3 -- titlePaint() leaves the in-time paint's PRNG; a string write unmade at `$9765`, an unknown effect and a
cursor left up past `$9765` THROW (the last spun frontFrame forever: the battery's one TIMEOUT, now a named failure).

DECLARED, still: the glyphs (no ROM); the starfield's R at `$9712` is the stand-in (exact given the machine's).

### M7.111: the title's exit in time

Until M7.111 a release pass (`$97B7 CALL $97EB`, the CLS, then `$97BA`'s test of every key -- interrupts ON) was drawn
at once and charged as a debt at its contended MEAN with the interrupts off (`BB_TITLE.PASS_T` 184,631), the arm as
`ARM_T` 142, and `$97C7..$8D09` (~293 T) not at all; the post-cold-start probes (07n) put the engine's `$97F8` 2,154 T
late after two passes.

**Measured** (`tools/titleexit.py` -> `build/titleexit_fixture.json`, ~15 s): the real load (painttime's drive, then the
machine's own paint) to its first `$9765`.  The plain runs: the arm `$979E..$97B6` 12 instructions / 122 T (one player),
`$9790..$97B6` 12 / 130 (two; both through `$8E0A`, RET on 48K); a pass `$97B7..$97BF` 6,921 / 145,216 T with 62,196
contended accesses -- the CLS's (the paint's own program) and the IN's I/O cycle (port `$00FE`, at 8); `$97C0`'s JR
12 / 7; the leave `$97C2..$8D09`'s CALL 20 / 330 T.  16 runs from `$9765` -- '1' / '2' pressed at a boundary and held
1..11 frames, `$9765` at the machine's phase or forced -- every boundary to `$97F8`: ring iterations, passes begun, the
attributes' CRC, the bitmap's CRC less the strings' cells; marks at the arm, each `$97B7` / `$97C0`, `$97C2`, `$97F8`;
every ISR's T; the bytes the exit leaves.  1..5 passes; `$97F8` at phases 18,234..69,061.

**Engine:** `BB_TEXIT` (ARM[1] / ARM[2], PASS, AGAIN / OUT = `$97C0`'s JR then PASS / LEAVE) and `bbClsProg(call, fx)`,
the CLS's program shared with the paint.  At the arm frontFrame puts a cursor up (`texit`); the 'release' front runs it
an instruction at a time on the frame clock, the ring's way: 'rp' counts a pass at `$97B7`, the CLS's 'c0' / 'c' / 'cE'
wipe the screen as the LDIR goes, 'k' tests the keys at the IN's T; at a pass's end `$97C0` picks AGAIN or OUT, and at
OUT's end (`$8D09`'s CALL spent) titleLeave() makes the round advance.  The arm's and the leave's stores are made at
the arm / at `$97F8` (EQUIVALENT `exitStoresAtOnce`: RAM above `$8000` nothing reads in between).  PASS_T, ARM_T and
`frontDebt` are gone; releasePass() is the gates' spelling (UNCALLED 19, UNREACHABLE 15).

**Gates:** TX1 -- the four programs against the plain runs (count, T, accesses, CRC of every PC:T:k), the JR's two
costs, the effects.  TX2 -- 16 runs, 144 boundaries (87 inside the release wait): all of the above exact, the arm at its
phase, `$97F8` in the machine's frame at its phase, the exit's bytes, the ISR T.  TX3 -- no cursor, a pass ended
untested, an unknown effect THROW.  M7.42 (h) re-worded (the counts and frames still exact / within one).

DECLARED, still: the round-1 build from the title (`BB_BUILD_AT[1]` and the R1 stamps, measured as means / from
captures) -- the next increment re-measures it on this path.

### M7.112: the round-1 build from the title, exact

Round 1 is only ever built from the title (`$8D09 CALL $97F8` after the release wait).  Until M7.112 it was timed like
the scrolling rounds: `BB_BUILD_AT[1]` a contended MEAN to `$7F30`, the repaint stretched by `BB_BUILD_K`, the end
`BB_ROUND_BUILD_T[.][1]` -- the engine's build came out 0.8..3.3K T short and its draws a few hundred T off (07n).

**Measured** (`tools/r1build.py` -> `build/r1build_fixture.json`, ~1 min): titleexit's 16 runs on from `$97F8`, and two
with the high score poked at `$9765` (hi1 / hi2).  The plain run `$97F8..$9887`: one program per player count -- 54,150
contended accesses one player, 54,296 two; 49,803 are the repaint's LDIRs (`$8216`, exactly extModel('repaint')'s
program), the rest the code in contended RAM (`$7F1B..$7FFF`, `$727B..$74xx`) and the display stores.  Only the two
awards' T (`$7FF2` / `$7FF7 CALL $80FA`: the score against the high score; 2,868 vs 2,817 T with the poke) move with
the world, and they make no contended access.  The machine's main line is that program replayed from `$97F8`'s phase
with each ISR's T (gate-closed 488 odd / 493 even -- on the title path both gates are shut before `$97F8`, so M7.85's
entry window is gate-closed too; run 2_3_6_50000 puts an ISR 827 T in) dropped in at the first instruction past its
boundary: the tool asserts the end and the ISR count on all 18 (`$9887` at 679,994..700,130 main-line T, 10 or 11
ISRs).  After `$7FFC` the contended stretch re-locks to the ULA: hi1's 51 T shorter award still ends at the same T.

**Engine:** `BB_R1` (AT `$7F30`'s plain T, REP `$8216`'s, X the awards' normalized returns, END_N, DATA: the accesses
outside the repaint as k + LEB128 steps), `bbR1Prog` (the data with the repaint's generated accesses put in),
`bbR1Map` (the replay: `at`, the cumulative delays, the end) and `bbR1At` (plain -> main line).  Inside step()
`buildClockFor` gives round 1 `r1Clock()`: the stamps on plain T (stretches 1), each through `r1Stamp`; the replay is
made with no awards and made again at `$7FFC` (`r1Final`, once hudRows has run both: `hudAw`), and roundStart spends
its `endMain`.  `buildLog` (S.log) records every display store's address and stamp for the gates; `r1Last` is the
diagnostic.  Outside step() (no frame phase) round 1 keeps the means: DECLARED.

**Gates:** R1a -- the program, access for access (SHA-1 against the plain run).  R1b -- the replay's end, ISR count and
every mark on all 18 runs.  R1c -- through step() from titleexit's world after `gameReset()` (TRAPS #298): `$97F8` at
its phase, every boundary to `$9887` and the row after the ISR that ends its HALT -- attributes and bitmap CRC with
the 463 ROM-glyph bytes out (the HUD text and the round number) -- all 6,989 / 7,061 display writes at the machine's
address and main-line T (none counted late against the end made again at `$7FFC`), the ISR T, `$9887` in the machine's frame at its phase.  R1d -- a gate open at `$97F8`, an
early stamp past the first award, a scroll copy in round 1, a build with its awards unrun all THROW; outside step()
the means.

On the real load path (`scratchpad/world/engplay.js` + `cmp.py`) the build's frames 416..419 now match the machine.
Still declared: `$9888..$98B4` (BB_ROUND_TAIL_T, a mean) and the banner (`BB_BANNER_AT`, fitted): with the
machine's sample taken before each boundary's ISR, the banner's cells differ at 423 / 470 and player 1 is a frame off
from 469 -- the next increment.

### M7.113: the round-1 tail and banner from the title, exact

From `$9888` (the ISR that ends `$9887`'s HALT has run) to `$8D0C` (the RET of `$8D09`'s CALL `$97F8`): the resume's
stores, `$79AC` (the collision transform and the drift painter, code in contended RAM at `$7C43..$7E4A`), `$BF39`,
`$8C5E`, the gate stores at `$98AF` / `$98B2`, the banner's 256 iterations and its two erases.  Until M7.113 it was two
means: `BB_ROUND_TAIL_T[.][1]` and `BB_BANNER_T.LOOP` with the banner's writes on `BB_BANNER_AT`'s fitted anchors.

**Measured** (`tools/r1tail.py` -> `build/r1tail_fixture.json`, ~1 min): titleexit's 16 runs on through the build.
- The plain run is ONE access program in every run, one player or two: 81,852 contended accesses (34,499 in `$79AC`, 256
  identical banner iterations of 180 at 10,902 T, 1,220 in the erases), `$8D0C` at 2,951,701 plain T.  Packed (k + LEB128
  steps, a byte LZ77) it is 842 bytes.
- The machine's main line is that program replayed from `$9888`'s phase with each ISR's T at its boundary: exact on all
  16 (`$8D0C` at 3,013,702..3,020,491 main-line T, 50..52 ISRs, every mark).  Both gates are open in it (the settle
  window from `$9884`, the even gate from `$98AF`): the ISRs are 13.5K..26.4K T odd, 1,892 even.
- **The engine's isrCost is the machine's UNCONTENDED ISR T on every one of them** -- each ISR's T less its own contention
  delay (the tool splits the contended clock's delays inside the ISR from the main line's).  The summed contention is
  765 / 817 T a run for one player, 1,756 / 1,817 for two, at most 82 T an ISR (the odd ISR's `$A3AD` draw running past
  14,335 into the screen's lines).  That is the engine-wide ISR contention gap (M7.99e), here and nowhere else.
- **The HALT runs as 4-T steps.**  The interrupt that ends `$9887` is taken at the end of the first step at or past the
  boundary: (the HALT's phase) mod 4 T into the frame.  `$9888` at 493 / 496 / 13,515 where the HALT began 0 / 3 / 1 mod 4.

**Engine:** `BB_R1T` (B5 `$98B5`'s plain T, ST the gate stores', ERASE the `$9904` entries' from `$98B5`, END, DATA) and
`bbR1tProg` / `bbUnlz`.  `roundStart` remembers that round 1's build ran on the replay (`r1Seq`); at 'resume' inside
step() `r1tBegin` runs the resume's stores as before, HOLDS the gate stores and every banner write on the program's plain
clock from `$9888` (`r1tHold`: Infinity in heldWrites, lzHold's form; the banner's repeats at `BB_BANNER_W.PERIOD`, its
erases at ERASE), and the new phase 'r1t' runs `lzSeg(s, budget, L)` -- M7.100's, now given its block -- a frame at a
time: each frame's segment from the phase the main line resumes at (the first from the HALT's ISR's end, then 0), its
writes landed before the frame's point, `$8D0C`'s frame T where it ends.  `r1tLast` the diagnostic (rule 6).
`roundSeqStep('halt')` lands on the 4-T grid on every round.

**Gates:** R1Ta -- the program access for access and the constants against the plain run.  R1Tb -- the replay (the
test's own) with the fixture's ISR T gives every mark, the end and the ISR count on all 16.  R1Tc -- through step()
from titleexit's world with the machine's ISR T put on each ISR: `$9888` at the machine's phase, the attributes and the
bitmap (the ROM font's cells out) at every ISR's end, all 46,262 held writes at the plain run's address and T,
`$8D0C`'s main-line T, frame and phase.  R1Td -- free-running: every ISR's T is the machine's less its own contention,
`$8D0C` in the machine's frame, 813..1,792 T early (pinned: the ISRs shorter, and the main line's own waits at
the phases that puts it at -- R1Tc shows the replay exact given the ISRs' T, so the offset is wholly theirs).  R1Te -- the boundary (backwards,
over another block's writes, a packed copy before the start all THROW; outside step(), or a build not on the replay,
the means -- DECLARED).  BT3 / BT4 (M7.56) keep measuring the means every later round runs on: their hand-off takes
that path.

**The real load path** (`scratchpad/world/`: engplay.js drives the built page; machisr.py the machine, sampled at each
ISR's END -- the engine's step() ends with its ISR -- with the HALT stepped and the keys changed at the ISR's end, the
engine's convention: TRAPS #299; cmp5.py diffs engine frame N against machine frame N, the ROM font's cells out): the
display is IDENTICAL from frame 407 (the title's CLS) to 533 -- the build, the tail, the banner, `$8D0C` and player 1's
first 65 frames of play (the walk, the release, a jump, a bubble).  The first difference after it is at 534 (cells
(14..15, 2..3)), gone again 888..921: the next increment.  Frames 400..406 are the starfield (R, declared).  The tail of
every other round (`BB_ROUND_TAIL_T`, per round) and their banner (`BB_BANNER_AT`) are still means.

### M7.114a: the in-play pass on the frame clock

Until M7.114a a main-loop pass was ATOMIC and charged its plain T stretched by round1_48's contended means (`BB_PASS_K`,
per callee) plus a flat 78 T (`BB_PASS_REST`); the frame's ISR ran after the last whole pass.  On the real load the
engine ran 12 / 9 passes a frame where the machine ran 13 / 8, phases unrelated, so no window inside a pass (frame
534's 62-T `$FEC5` window, M7.114b) could be placed.

**Measured** (`tools/passacc.py` -> `build/passacc_fixture.json`, ~10 s, `verify` MATCH): the real load (boot.pkl's
`$F5BC`, the KEYBOARD drive, keys at each ISR's end), frames 470..759, 2,565 passes, the simulator's contention window
opened to the whole frame so every access is listed.
- **REST was a phantom.**  A plain pass is 4,933 T: the skeleton's 479 plus its twenty callees' own uncontended sums,
  nothing else.  Every callee's T equals the machine's uncontended T; the rest of the difference was contention.
- **A pass's contention is its ACCESS PROGRAM replayed from its phase.**  101,703 contended accesses at 30 sites: the
  skeleton's `$8D65` IN (8 T into it, 31 T before the pass's end), `$7FFC`'s code fetches and 61 HUD attribute stores
  (24 T apart; the fourth run FALLS into `$8015`, 17 T sooner), `$8FE7`'s IN (port `$7FFE`: two contended I/O cycles,
  7 and 8 in), `$9961`'s IN, `$8FA5`'s four OUTs a tone (192 T into the arm, 200 with the NEG; half-periods
  16E+10 / 16E+30), `$7E80`'s own code (`$7E80..$7E84` is contended RAM) and its `$7E0E` read, `$9037`'s `$745C` reads,
  `$9E50`'s `$7E0E` read, `$9AEB`'s `BIT 7,(IY+7)` on `$5B07` / `$5B11` (16 and 19 in), `$931A`'s five attribute reads
  a live probe makes, and `$C002`'s table reads (`$C00B` each iteration; `$C016` / `$C019` / `$C04C` on a live slot).
  (Corrected M7.115e: the fixture's 30 sites hold no `$8669` site -- no item is drawn in 470..759 -- and the engine's
  item pass puts no access on the program: its inks, blits, erases, award glyphs and chirp OUTs are the next gap.)  The replay: each access waits `bbUlaDelay` at its wall phase, and an ISR's T goes in
  before the first access whose INSTRUCTION starts at or past its point -- asserted on every pass by the tool.
- **The interrupt lands inside the pass, and what comes after it is the next frame's.**  The machine's straddling pass
  runs its later callees after the ISR: the edge detectors of `$9E50` / `$9AEB` / `$A09A` / `$A824` / `$8669` see the
  counter the ISR moved and fire in THAT pass, not the next (TRAPS #90's general case, #301).
- **52 bytes the engine reads keep their TAPE values to play** -- the edge detectors' operands (`$8680` `$9E57` `$A09E`
  `$AA00` = `$2A`, `$9AF5` = 1), `$917C`'s operands (`$9194` 4, `$91DC` 8, `$91D0` `$2A`, `$91E4` 0), `$9077` 3, `$7ED7`
  1 and the rest -- where reset() had 0 or build/image.bin's values (TRAPS #300).

**Engine:** `BB_PASS_K`, `BB_PASS_PROV` and `BB_PASS_REST` are gone; every callee charges its plain T.  `pa(o, k)` puts an
access on the pass's program at its plain offset from `$8D0C` (`passBegin`; each callee's entry `pbase`: the skeleton's
`AT0` 103, 17 a CALL, the callees before, kept in `pAt`): `BB_SM_ACC` per BB_SM key (zs), `paBit` for `$9AEB`, the
hooks in `$931A`'s tests (its T now summed in the machine's order), `$C002`'s iterations, `jumpTone`, the wrap's
`BB_PASS_ACC` table and the IN in `passCharge`.  `passWait` replays the program from the pass's phase on this frame's
clock; the accesses past the point go to `pTail`, waited out by `passTailWait` from the next frame's phase after the
ISR.  `chainWalk` CUTS the pass when a callee's entry is at or past the point (`passSplit`; `passSplitCharge` charges the
part so far and its waits; the pass resumes at that callee after the ISR, counted once, in the frame it began) -- or
when an edge read a fixed way in would be (`BB_EDGE_LOOK`: `$A824` 22, `$A9ED` 59, `$9037` 25; `$8669` 85 + `$89CB`'s
head, `itemSpawnT`), the head charged before the ISR.  `ctrRead` gives a counter read inside a callee the INC the ISR
made when the read starts at or past the point (`$9E50`'s, after its kid: its body then runs before the ISR, DECLARED).
`passSettle` spends a pass's prefix before a mid-pass block (the join) with its waits counted once.  `passLast.rest` is
now the pass's waits, `paid` what a cut charged before its ISR.  `BB_TAPE_OPS` seeds the 52 bytes in reset().

**Gates:** PA1 -- the fixture.  PA2 -- the load driven as the page does, the first pass of play put at the machine's
phase and every ISR from there given the machine's T: all 2,565 passes of 470..759 in the machine's frame, at its phase,
with its program (count and SHA-1).  PA3 -- the 52 bytes at the machine's play-start values.  PA4 -- free-running, the
first pass of play 1,036.782 T early (pinned: the ISRs' own contention, R1Td's gap, and the control select's scan means,
whose fraction rides on -- M7.114c).  PA5 -- the boundary (a backwards program and a non-counter read THROW; the cut and
its resume; a counter read at the point; outside step() no waits, no tail).

**Still DECLARED:** the census world's odd frames fit a twelfth pass twice in eleven (its ISRs lack their own contention,
M7.114c).  The hurry's, the storm's and `$94C2`'s blocks still start at their PASS's start (the atomic pass's placement:
the pass clock knows the entry, and moving them re-stages their gates -- tried, and the synthetic phases of HB10's
scenes have no exact natural pass: next).  `$9E50`'s tick body runs before the ISR when its read is past the point.
Sites off the real load's play not yet on the program (passcost's 48 states: `$7E80`'s long path -- contended code
throughout, counted `paMiss` --, the boss's blits in `$A824` / `$A9ED`, `$9037`'s banner, `$9AEB`'s fire updates,
`$C002`'s blits and erases, `$915F`'s Boris erase) wait nothing yet.  A pass resumed after a block or the pause waits
only for its program from there.

**The real load path** after M7.114a: the display is still identical 407..533; at 534 the bubble (cells (14..15, 2..3))
-- the even ISR inside `$93E1..$93F9`'s 62-T window, M7.114b.  Given the machine's ISR T the passes hold to 759; at 760
the sparkle table differs (534's world).

### M7.114b: the dark window

`$93DC` (elemArm, chain index 8, every pass) is `LD HL,$93F4 / PUSH HL / XOR A / $93E1 LD ($FEC5),A ...` and every
path returns through the pushed `$93F4`, whose `$93F9 LD ($FEC5),A` stores 1 again: the ISR's even-branch gate is
SHUT for 62 T a pass on the request-0 path (instructions starting 25 and 87 T in), and for the whole arm on the others.
An even ISR whose point falls between the two instructions' starts finds ($FEC5) = 0 and skips `$B62C` -- the machine's
at boundary 534 of the real load did (`$93E1` ran 3 T before it), and from there its bubbles ran one even pass behind
the engine's.

**Survey** (`scratchpad/m7114/isrbytes.py`, the real load's frames 470..759): the ISRs read 2,906 bytes `>= $4000`;
the main line writes 77 (61 HUD attributes, a few code-page operands, five in `$FExx`); the ONE byte in both is
`$FEC5`, and its only writers there are `$93E1` and `$93F9`, a pair in every pass.  (Not in that window, so not
surveyed: `$948F`'s `$9494` / `$94BA` pair and `$7E80`'s `$7EC7` / `$7F05`, both around a HALT or a block.)

**Measured:** `tools/passacc.py` now records each ISR's ($FEC5) at its acceptance (`gates`): 291 ISRs of 470..760,
0 at 534 only (470's `$2A` is the title's `$98AF`).

**Engine:** `elemArmDone` places `$93E1`'s start (`BB_DARK.E1` 25) and `$93F9`'s (the path's `smT` less
`BB_DARK.TAIL` 23 -- the store's 13 and `$93FC`'s RET: every path's `r93F4` key ends with the store) on the frame clock
(`passClock`: the pass's phase + the plain offset + the waits of the accesses before it).  A point between them sets
`isrDark`; the pass then cuts at the next callee's entry (past the point), and step() runs that ISR with ($FEC5) = 0
and puts `$93F9`'s 1 back after it.  **PA8**: given the machine's ISR T (PA2's drive), every ISR of 471..760 finds the
machine's ($FEC5) -- 0 at 534 alone, the engine dark exactly once there -- and the gate is 1 after every step.
PJ7 (projectiles through step() from machine states at a SYNTHETIC phase) gives each ISR the machine's own gate (its
target vector's `$FEC5`): its phase is not the machine's, so where it would put the window is not either.

**Still DECLARED:** free-running, the engine's pass is ~1,037 T off the machine's by play (PA4: the ISRs' own
contention, M7.114c), so the real load's frame 534 still differs (the window is placed from a clock that is not yet
the machine's; the engine went dark 8 times free-running over 1,045 frames, at its own phases).  The other gate pairs
above are not windowed.

**The battery after M7.114a, and what it found** (full run 02:14: 5,393 killed, 2 survivors, 8 timeouts).  The "timeouts"
were SURVIVORS whose whole-suite confirmation ran past the runner's per-case limit on a loaded machine (each passes the
suite alone in ~3 min): M7.114a re-phased the scenes that had driven those step() paths -- CD2 now takes the split route,
so no scene cuts at the countdown read; the hurry / PERFECT scenes no longer return a block with a HALT pending.  Gated now
as step()'s contract with a stub mainLoop (**PA11**: a block's return clears `blocked`; 'perfect' is never charged as a
pass; a cut on the clear is charged as the clear and ends the frame; the next step() resumes it) and **CD3**'s direct
resume ($97F8 entered where the cut pass ended).  **PA9**: step()'s pass loop THROWS past `BB_STEP_TURNS` (1024 -- a frame
holds at most 728; the suite's most is 18), so a mutant that stops the clock is a named failure, not a hang.  **PA10**:
the dark window's edges and the waits that move them.  The census world's element-tick seed became a no-op with M7.114a's
tape bytes; its mutant now flips the phase.

### M7.114c: the ISRs' own contention

Until M7.114c isrCost was the machine's UNCONTENDED ISR T (M7.99e, R1Td): the odd ISR's `$A3AD` draw runs past 14,335 T
into the screen's lines, and every display access it makes there waits for the ULA.  Free-running that put play's first
pass 1,036.782 T early (PA4) and `$8D0C` 813..1,792 T early on round 1's tail (R1Td).

**Measured** (`tools/isracc.py` -> `build/isracc_fixture.json`, ~12 s, `verify` MATCH): the real load (passacc's drive),
every interrupt of frames 400..760 -- 361 of them, 81,992 contended accesses, 16,839 T of delay (odd 16,811, even 28): its
acceptance phase, T, delay and ACCESS PROGRAM by class (`ent` $A447 from $A3AD's pass, `bent` $A447 from the bubble
manager, `in` the player handler's port cycles, `b5` the settler's `$73A6` reads, `bub` the bubble blitter `$B9E7`).
ASSERTED: each ISR's delay is its program replayed from its acceptance phase.  And a sweep from round1_48: `$A447`'s erase
and draw and `$B9E7`'s blit are ONE access template per (path,) Y & 7 -- X and the position beyond Y & 7 change nothing
(40 templates: offset, T into the instruction, row, column).
- The delay is very sensitive to the acceptance phase: the first contended access re-syncs to the ULA, so D falls
  about one T per T of phase, with 8-T jumps -- the ISR's END is nearly phase-independent, but not exactly.
- The acceptance phase is the end of the instruction in progress at the boundary: 0..15 T in play, mean 4.5.

**Engine:** isr() builds the ISR's program as it runs (`this.ip`: offset from the acceptance, k, class) and adds its replay
from the acceptance phase (`ipWait`): `isrCost = isrPlain + isrD`.  Every offset is the ISR's own ledger in machine order:
`BB_ISR_A3AD` / `BB_ISR_B62C` (the skeleton to the branch's routine), `$A447`'s entry from `$A3AD`'s ledger (less its
epilogue and the visit's tail, charged ahead: `BB_A3AD.EPI`, `V_POST`), the templates (`BB_BLIT_ACC`, base-36 packed; an
access on a ROM row of the `$FD00` table waits nothing) with the beam carries after them (`ipShift`), `$AA60`'s entry and
`$AB38`'s from the walk's sums, the INs / OUT of `playerRead` (`BB_ISR_IN`, the Zilog sums: 8 T in, and 7 T in as well when
the port's high byte is in `$40..$7F`), the settler's two `CP (HL)`s, the bubble slots' clock (`BB_B62C`'s skeleton and the
arms in order: a risen draw 87 T + the rise + 17 in, the travel's `$BF16` / `$B9E7`, the rise transition's and the capture's
erases from the arm's clock, `BB_ISR_TRAVEL` / `TR_BF` / `TR_POST` / `BF_A447`).  The acceptance phase is a HALT's where
the engine knows it (`haltPh`, the 4-T grid) and `BB_ISR_ACCEPT` (4, PROVISIONAL) elsewhere -- a pass's callees are not
timed instruction by instruction, so the instruction in progress at the boundary is unknown (M7.114d).  The blow click
is clamped inside ONE frame (after an overrun `span` is the last ISR's, and the lost frame was already stepped).

**Gates:** IC1 -- the fixture and the 40 templates the engine ships, access for access.  IC2 -- PA2's drive with each ISR
given the machine's acceptance phase: all 361 ISRs' programs class by class (count, SHA-1) and delays the machine's.  IC3
-- the boundary (a backwards program THROWS; the port rule; ROM rows; no program outside an ISR; the HALT's phase, else
BB_ISR_ACCEPT; the Kempston branch's `$1F` cycles COUNTED, `ipMiss`).  Re-pinned (each with an M7.114c note): PA4 1,036.782
-> -0.218 T; R1Td `$8D0C` 0..77 T early (473 of 828 ISRs exact, the rest -8..5 T); RA's counter B now a distribution
(1 / 1 off of 80 per key); BT3 (odd -8..5 / -6..4 in the settle window, the late ones 44..58 T long: a hand-off ~490 T
off the machine's phase); PK7 (pop rows 1,093 -> 49 T short); the census still two twelve-pass odd frames, elsewhere.

**Still DECLARED:** the acceptance phase (BB_ISR_ACCEPT) -- M7.114d, the instruction in progress at the boundary; the
Kempston branch's port cycles; corpse-flight / boss draws in an ISR (none on the real load).  **Found:** on the real load
given the machine's ISR T the PLAIN T differs at 691..741 by +1,510 / +1,357 / -1,357 / -1,510 (the access programs match
there) -- untouched by this increment.  (M7.114e: the ODD ISR's, not a bubble-manager arm -- a seed byte, below.)

### M7.114d: the acceptance phase from the instruction grid

M7.114c replayed each ISR's contention from its ACCEPTANCE PHASE -- the end of the instruction in progress at the
boundary -- and the engine knew it only at a HALT; elsewhere `BB_ISR_ACCEPT` (4 T).  Free-running, given the MACHINE's
acceptance phases (and nothing else), the real load's play already held pass for pass to frame 690
(`scratchpad/m7114d/payoff.js ph`); with 4 T it parted at frame 473.

**Measured** (`tools/insgrid.py` -> `build/insgrid_fixture.json`, ~18 s, `verify` MATCH): the real load's 2,565 passes of
470..759, every main-line instruction's plain offset from `$8D0C` and plain T (1,693,208; they tile each pass), and the 289
interrupts taken inside a pass: the instruction each was taken after and the phase.  Phases 0..15 T; one after `$8D0C`'s
EI (the Z80 takes none straight after EI: it waits for `LD A,($FEC9)`, 13 T).

**Engine:** every charge in a pass's models logs a GRID KEY (`pg(key, t, n)`, returning `t * n`) in the machine's order:
`BB_GRID_SM` -- all 527 BB_SM keys' instructions, generated from costsmall's blocks (`zs` logs them; `$93FC`'s RET, summed
early, is logged at elemArmDone) -- and `BB_GRID` for the other models: the skeleton (`SK.*`, `BB_PASS_GRID`: HEAD 76 with
its EI flagged, the CALL z not taken / taken, each chain CALL, TAIL 53), `$7FFC` on the wrap (`HUD.*`), `$8E3A`'s tally
(`RC.*`), `$C002`'s free slots (`SC.*`), `$8FA5`'s arms and tone loops (`JT.*`, `BB_JT_GRID`), `$925A` / `$92BB` / `$92E4`
(`PE.*`, `TR.*`), `$931A` / `$9377` / `$9360` (`EK.*`), `$8669`'s walk and `$89CB`'s ways out (`IT.*`), and the heads run
before the ISR at an edge-read cut (`LK.*`, `gridLook`).  A key's 'c' instruction (CALL) DEFERS the rest of the key until
the kid's closing RET ('x'); each callee's entry is a RESYNC (`pgSync`).  `gridWalk` lays out REGIONS between resyncs,
valid iff the keys tile them exactly (no unknown key, no rest left deferred, nothing marked out of order by `pgBad`); a key
whose grid does not sum to its charge THROWS.  `gridPh`: the last instruction begun before the point on the frame clock
(plain offset + the waits of the accesses before it), an EI's moved to the next, ended -- its end less the point is the
acceptance phase; in an invalid region or past the grid it is a MISS (`phMiss`, counted; `BB_ISR_ACCEPT` stands).
`gridResolve` runs it on the pass that straddles the point (a split's or a whole one's); isr() takes `isrPh` (a gate's),
`haltPh`, then the grid's.  The pieces not on a grid yet -- a live sparkle's blit / erase, a live item's entry, the
spawns, a corpse's `$8BC2`, `$90A9`, the countdown / treasure / boss arms of `$8E3A` -- leave their region a miss.

**And the edge-read cut became path-aware** (TRAPS #303): `edgeLook` is 0 when the callee's path does not reach its read
(`$A824` with `$A839` 0, `$A9ED` off round 80 or with no boss, `$9037` on round 80, `$8669` with a player carried) -- its
head then runs before the ISR, as the machine's does.

**Gates:** GR1 -- the fixture, and the BB_SM grid keys costsmall's blocks instruction for instruction.  GR2 -- PA2's drive:
all 2,565 passes' grids the machine's (count, SHA-1).  GR3 -- the same: all 289 in-pass ISRs taken after the machine's
instruction at its phase, nothing given.  GR4 -- FREE-RUNNING (the page's own load and ISR T): the real load's play the
machine's pass for pass (frame, phase to the T, access program) through frame 534's dark window to 690 -- pinned: the
first to part is frame 691's.  GR5 -- the boundary (sum and CALL-key refusals, invalid regions, misses, the EI rule, a
wait moving the instruction in progress, no key from an ISR, the look heads' sums, a stale phase).  GR6 -- fourteen paths
the real load does not take (items carried, the tone arms, the scans, the flood, the boss tally...) tile their charges.
Re-aimed: JT7's scene lets go of
the last cut (letGo) -- its pass resumed at `$9961` itself once the ISR phases moved; PA6 asserts both arms of each look.

**Still DECLARED:** the fraction PA4 pins (-0.218 T -- not the control select's scan means, as written here: the cold start's COLD_PH interpolation, closed by PA4c below) rides on, so GR4 compares phases to
the T; at frame 691 the ISR's plain T parted by +1,510 / +1,357 (found in M7.114c; fixed by M7.114e, below);
the round start's ISRs (the title's tail, the banner: R1Td's -8..5) still take BB_ISR_ACCEPT -- their blocks have no grid.

### M7.114e: the load's world is the tape's -- frame 691's +1,510 T was a seed byte

**Found** (`scratchpad/m7114e`): the parting at 691 was the ODD ISR (the labels there are odd; the even ISRs match the
machine all through 686..744: two rising bubbles, 12,012 / 12,074 / 12,100 T).  Inside it `$AA60`'s slot 3 (`$AF31`, the
walker `$B028`) cost 2,871 T on the engine from 691 and 1,361 on the machine until 733: `$B0A2`'s movement divider
(`(IY+4) >= ($B60F)`) let the floor probe `$B0AC..$B0D2` run 42 frames early.  Not a cost -- the arm's T is the machine's
(2,952 at 733 on both) -- a STATE: slot 3's `+4` counter ran 21 ahead, and so did slots 2 and 4.  They are seeded at the
spawn from `$73AF` (`$72F8`: += `$5D` per enemy), and on the page's load the spawn ran TWICE: `handDone`'s `reset()` ends with
`spawnRound()` (round 1, for every in-play test world), from reset's zero fill (-> `$17`), and the round start's `$9866 CALL
$727B` rolled again from there.  The machine's cold start (`$963B`) clears the table, `$73AF` holds the tape's `$02` and
`$727B` runs once (-> `$19`, +4 = `$5F $BC $19`, as round1_48 / play1p48 hold).  `reset()`'s own world was off too
(`$17` against round1_48's `$19`).

**Why BB_TAPE_OPS missed it:** its rule takes each byte's value at the first pass of PLAY (passacc) -- by then the spawn
has rolled `$73AF`; a read-modify-write before play is invisible to it.  So the whole load was swept for the class
(`firstread.py`: every byte >= `$5B00` the machine reads before writing it, `$F5BC` to frame 760, 2,854 live bytes;
`handcmp.js`: against the engine's RAM right after `handDone`, leaving out the ROM's variables, the relocated code and the
front end's code).  Two remained: `$73AF`, and `$856C`'s eight even bytes -- reset() carries round 1's tile there (right for
an in-play world) while the load holds the tape's zeros, and `$8207` lifts them into the separator pattern `$8584` at the
round start before `$830B` refills them (the machine's `$8584..$858B` is `$00` x 8 from 412 to 760; invisible on round 1's
screen, but RAM).

**Engine:** `BB_TAPE_RMW = { $73AF: $02 }` (passacc `boot_rmw`, boot.pkl at `$F5BC`, asserted = build/image_tape.bin), seeded
in reset() before the spawn; `reset(keys, load)` -- `handDone` passes `load`: no spawn (the round start's does it) and no
tile evens carried.  After it the sweep finds nothing but the hand-over's own counter tick.

**Result:** given the machine's ISR T all 361 ISRs of 400..760 exact (drive.js: none differs); FREE-RUNNING the real load is
the machine's pass for pass through the window's end, 2,565 passes of 470..759 (GR4 re-pinned); the ISR T left differs only
at 421..469 by -6..+8 T -- the round start's acceptance (R1Td), next.

**Gates:** GR4 (no part to 759), ME1 (BB_TAPE_RMW = boot_rmw; reset()'s round rolls `$73AF` once to `$19`, roster +4
`[95,188,25]`; the page's load spawns once and its `$8584` is the tape's).  6 battery cases (`scratchpad/battery/add_m7114e.py`).

### R1Tf: round 1's tail takes its ISRs at the machine's acceptance phase

After M7.114e the only ISR T left off the machine on the real load was 421..469 (-6..+8 T): the ISRs inside round 1's tail
and banner (`$9888..$8D0C`, M7.113's lazy replay), which took `BB_ISR_ACCEPT` (4 T) -- R1Td pinned 473 of 828 exact over
titleexit's 16 runs, -8..5 T, `$8D0C` 0..77 T early.  The replay already paused the main line at the point itself (`lzSeg`'s
`L.x`, the point's plain T) and resumed it after the ISR, so the main line's T was right; only each ISR's own contention,
replayed from the acceptance phase, was not.

**Measured** (`tools/r1tail.py`, now also): the plain run's every instruction's T, 362,817 of them (no EI, no HALT --
asserted; ONE sequence on all 16 runs, one player or two -- asserted by digest), summing to `BB_R1T.END`; shipped as
`BB_R1T.INS` (one byte per instruction, the same LZ77: 1,084 characters); and each machine ISR's acceptance phase (0..16 T,
the runs' `isrs[i][3]`).  Fixture regenerated: only those keys added, `verify` MATCH.

**Engine:** `bbR1tIns()` (each instruction's plain start, its T; refuses a grid that does not sum to `$8D0C`); `r1tPh(x)`:
the last instruction begun before plain T x ends at start + T, less x -- the acceptance phase (the ULA never waits that close
to the boundary, so `L.x` is the clock's point); `r1tStep` sets `gridPhV` from it whenever the point falls inside the tail.

**Result:** R1Td free-running: 828 of 828 ISRs the machine's T, `$8D0C` exact on all 16 runs; R1Tf: all 812 in-tail ISRs at the
machine's phase, given the machine's ISR T and free-running.  The real load free-running (`scratchpad/m7114d/payoff.js`):
all 380 ISRs of 380..760 and all 2,565 passes the machine's.  `BB_ISR_ACCEPT` is left only to grid misses and the blocks with
no grid (the lazy blocks, a later round's start).  Still DECLARED: PA4's -0.218 T (the cold start's COLD_PH
interpolation, not the scan means as written then -- closed by PA4c, below).

### PA4c: the cold start's access program -- PA4's -0.218 T was COLD_PH's straight lines

**Found** (`scratchpad/pa4/debt.js`, the real load frame by frame): the control select's fractions (BB_FE.SCAN_T's path
means) all die at frame 88's HALT -- the probe's `$FAC5 EI / HALT` resyncs to the boundary, and the probe is cycle-exact.
The fraction was born at frame 344 in `handOpen()`: `phaseT(BB_SPINE.COLD_PH, tframe)`, 64 samples every 1,092 T with
straight lines between (17/78 = 0.21795 at the real load's phase 994).  Exact at the samples, up to ~150 T off between.

**Measured** (`tools/coldstart.py` -> `build/coldstart_fixture.json`, `verify` / `emit`): `$F5CC -> $8CCA` (interrupts off)
is ONE program on p4p3, p2p2 and the real load: plain **54,451 T**, **13,648 contended accesses** (digest
`9cc3d833156fddf7`); replayed from the phase (each access waits DELAYS_48K at its wall phase) it is the machine's T at the
64 phases, 16 midpoints, 400 random phases, and the real load's (frame 344, phase 994: **67,376 T**).  Shipped as LEB128
steps through r1tail's byte LZ77: 27 bytes (`BB_SPINE.COLD`).

**Engine:** `bbColdProg()` (refuses a count that is not N), `bbColdT(phase)` = PLAIN + the program's bbUlaDelay waits;
`handOpen()` charges it.  COLD_PH stays (H-d(c): the fixture's table, and handOpen = it at the 64 samples).

**Result:** H-d(c)'s cold-start midpoint band 0 (was <= 150; the gate now demands exact); PA4c CS1..CS3 (the program,
every phase, the real load's hand-over: phase 994, 67,376 T, an integer total); PA4 re-pinned **0.000** -- free-running,
the first pass of play is the machine's T.  Nothing of PA4 is DECLARED now.

### M7.115: a later round's start on its program -- rounds 2..81 off the means

**Found:** rounds 2..81 (and the wrap past 81) started on contended MEANS taken at one phase -- `BB_BUILD_AT` (the scroll
mark), `BB_BUILD_K` (1.18 / 1.26 stretches), `BB_ROUND_BUILD_T`, `BB_BANNER_AT` -- as round 1 did before M7.112 / M7.113:
the build's stamps K T off the machine's (BD2: -4.7K..+4.8K), the tail's acceptance phase the declared 4 T.

**Measured** (`tools/lrstart.py` -> `build/lrstart_fixture.json`, 336 natural advances: rounddrain's hand-off, ($FECD)
chunks of ten from every tenth round, keys 1 and 2, the tile counter moved, the wrap, lives / letters / palette x tile
pokes): `$97F8..$9887` and `$9888..$8D0C`'s plain access programs, split at the routine marks (23 + 9 segments), are a
function of the ROUND and the PLAYER COUNT (the spawn `$727B` is 10..19 T longer with two) but for five pieces:
- `w` `$97F8..$9858`: no contended access; `BB_BUILD_WIN`'s w4 (to `$9855`'s first store) + 836 (18 STEPs, the DJNZ's 8);
- `j` `$83F1 JR nz` in the tile index `$83EB`: 11 T when the index wraps from 4, else 12 (the tile counter moves the
  background by that 1 T and nothing else);
- `k` wallPattern `$8390`: two programs by `$860C` (paletteStep's bit 7: the expand path), whatever the tile;
- `l` the lives panel `$806C`: `extModel('lives', cp)` + 17, after `$7F5B CALL`'s own four code fetches (contended RAM);
  it reads the bottom row's attributes, which the build rewrites first -- the engine remakes it at the CALL;
- `p` the letter panel `$957E`: `extModel('panel', cp)` + 17.
Replayed from the advance's phase with the machine's ISR T, both halves give every mark, the end and the ISR count on all
336; every gate-closed ISR in the builds is `BB_ISR_ACK + GATE_CLOSED` by parity; 2 advances take a gate-OPEN ISR in the
entry window.  491 distinct segments, 10.8 MB -> 65 KB (r1tail's byte LZ77) -- `BB_LR`.

**Engine:** `lrClock()` (buildClockFor, inside step()): the round's segments with `lrHoles()`, replayed by `bbR1Map` from
`$97F8`'s phase -- `C.r1` with `lr`, so every stamp goes through `r1Stamp` and the scroll's copier (`bbBuildCopy32`)
through the same map; `lrCheck` remakes the replay when a panel at its CALL is not the clock's.  The tail: `r1tBegin` takes
the round's program (`bbLrTail`: acc / ins, the instruction grid, END, B5 = gate + 33, ST, ERASE) -- round 1's is the same
shape (`bbR1tTail`), so lzSeg, r1tPh's acceptance phase and the banner's stamps are R1Tf's.

**Result:** LR1 (the stream = the fixture), LRq (nine chosen advances) and LRt (rounds 2 / 81's tails on a fresh engine: every
held write at the machine's plain T) -- the quick block the battery's constant cases die in --, LR2 (every advance's build: the engine's own pieces on the machine's RAM, the
replay = the machine's marks / `$9887` / ISR count), LR2b (every tail), LR2c (the wall), LR3 (through step(): rounds 2..4,
81 and the wrap; the tail's 46,262 held writes at the machine's plain T), LR4 (unit builds at the machine's phase: every
display write at the machine's main-line T).  RA's in-play counter-B distribution moved to 0 on two more advances.
**Still DECLARED:** an ISR inside the entry window (gate-OPEN, M7.85b) is replayed at the gate-closed T (counted
`lrWinIsrs`); outside step() and for a round / player count never measured, the means.  NOT YET gated: a later round's
start free-running against the machine (the engine's own ISRs in the tail -- R1Td's check for later rounds).

### M7.115c: a later round's start free-running -- three things the replay with the machine's ISR T could not see

**Measured** (`tools/lrfree.py` -> `build/lrfree_fixture.json`, ~1.5 min on 11 workers, `verify` MATCH): the real load
(passacc's drive and keys) with ($FECD) poked at the same point in engine and machine -- the END of an ISR (round 2 from
frames 480 / 560 / 640 / 700 / 745 of round 1's play; rounds 10 / 41 / 81 by ($8609) with the warp refused; three
advances back to back, 2-3-4; 81 and the wrap, which drew round 34) or the `$8D0C` of a pass that begins within 96 T of
the boundary (frames 546 / 744: the interrupt falls inside the `$FECD` pass) -- recorded to 60 frames into the new round:
every ISR [label, T, own delay, acceptance phase], each advance's `$97F8` / `$9887` / `$9888` / `$8D0C` [frame, phase],
($8609) at `$9888`, the wrap's `LD A,R` at `$9811`, the first frame of `$7E80`'s long path (`$7E85`), and the attributes'
and bitmap's CRC at the end (r1build's ROM-font mask, plus the round number's tens digit, cell (2, 0) rows 1..7).

**Found**, free-running, nothing given (scratch: `scratchpad/m7115c/cmp.js`, `split.js`, `prog.py`'s dumps):
1. **Every odd ISR from the tail on 89..162 T short** (round 2: the build exact, then `$A3AD`'s draws).  The PLAIN T was
   exact; the delay was not.  The draw blits from type 0's facing-1 sprite bank at `$5B80` -- the runtime mirror,
   CONTENDED -- and its POPs wait; isracc's templates were swept on `$C100` (uncontended) and held only the display's
   accesses.  Measured: `tools/isracc.py` now also sweeps the draw from `$5B80`: **16 S templates** (by the draw's key),
   the source reads (offset, k), the shift's copy read byte after byte from its start (64 aligned, 96 shifted at +64 /
   +160 / +256: bbBlit16's copy) -- asserted, and the display's accesses asserted the D template's.  Engine: `ipSrc`
   merges the reads whose address is in `$4000..$7FFF` into the draw's program (`entityDrawOne`).
2. **The third advance's `$9888` 8 T late** (n3).  The build's replay began at the advance PASS's `$8D0C`, not `$97F8`:
   mainLoop called `roundAdvance()` (buildBegin, lrClock's phase, the stamps' origin) before step() spent the pass's
   charge -- the `$FECD` pass's 96 T.  On every other world the HALT's 4-T grid swallowed it (96 is a multiple of 4);
   on n3 the second advance began in the frame the first's tail ended, the build came 69 T short, and 69 is not.  The
   engine's own program replayed from the machine's `$97F8` phase gives the machine's `$9887` exactly (4,388,342).
   Engine: **`loopAdvance()`** -- inside step() mainLoop marks the advance (`advDefer`) and step() makes it after
   spending the charge; when the charge ran past the frame's interrupt, at the top of the next frame after the ISR
   (cdResume's rule, counted `advNext`).  Outside step() (no frame clock) at once, as before.  This also moves the
   natural clear's and the PERFECT / EXTEND resumes' `$97F8` to their pass's end -- the clear's chain, which the
   machine ran before `$8E3A` (and before the PERFECT block); no machine world reaches those yet (PF2 restated).
3. **The ISR inside the advance pass at `BB_ISR_ACCEPT`** (late744: 4 T, the machine's 8).  The `$FECD` pass is eleven
   fixed instructions (`$8D0C EI` 4, `LD A,($FEC9)` 13, `OR A` 4, `RET nz` 5, `LD A,($FECD)` 13, `OR A` 4, `JR z` 7,
   `DEC A` 4, `LD ($FECD),A` 13, `JR $8D09` 12, `CALL $97F8` 17 = BB_FECD_PASS_T): **`SK.FECD`**, laid by mainLoop's
   `$FECD` branch and handed to gridResolve (gridPh's EI rule included).

**Result:** all 11 worlds the machine's: every ISR's T from the poke through the build, the HALT's, the tail and the
banner (and on round 2 / 41 / the late worlds the 60 frames of play), every `$9888` and `$8D0C` at its frame and phase,
the rounds, the wrap (BB_Rng's substitute fed the machine's draw), the screen at the end.  RA's in-play counter B: key
2's far -1 went to 0 too (`far 0:67 | near 0:13`).  isracc `verify` MATCH (only `tmpl` gained the S keys).

**Gates:** LRF1 (round 2, five phases), LRF2 (10 / 41 / 2-3-4 / 81-34), LRF3 (the advance pass that meets the
interrupt: SK.FECD's phase, advNext 1), LRF4 (the boundary: loopAdvance outside step(), SK.FECD's sum and EI); IC1 (56
templates, the S ones (offset, k)); RA re-pinned; PF2 restated.  11 battery cases (`scratchpad/battery/add_m7115c.py`).

**The owner's round 2 (2026-10-09, found in the page, not by a gate):** the level drawn, then no sprite and nothing
moving -- no console error.  The page boots with `skipProbe` ON (the added layer, default): the control select's path
means (`BB_FE.SCAN_T`) leave a FRACTION on the clock, which the probe's `$FAC5 EI / HALT` clears on the faithful path
(PA4c) -- so every gate, run with skipProbe off (or from `gameStart`), had an integer clock at a later round's start.
`bbLrMap` (M7.115b) indexed its delay table at `(phase + t + D + I) % FD`: at a fractional phase that is undefined, the
build's end NaN, `spend(NaN)` -- the pass loop never ran again, `$9887` was never reached, both gates stayed shut.  Round
1's `bbR1Map` calls `bbUlaDelay`, whose `& 7` truncates (the delay at n + e is the delay at n), so round 1 never showed
it.  Fix: the table indexed at the phase's floor (`| 0`), bbUlaDelay's rule.  **LRF5**: the page's own boot, ($FECD) in
play, round 2's start completes on a fractional clock, its map = the map from the phase's floor, delay for delay.  A
soak on that path (`scratchpad/m7115c/soak.js`): rounds 2..16 advanced with play between, clean.

**Still DECLARED:** the play after a later round's start where the machine runs `$7E80`'s long path (`$7E85..`,
contended code: rounds 10 / 4 / 34 from their first frames -- the pass's plain T exact, its delay not; the engine counts
`paMiss`); the wrap's `LD A,R` (BB_Rng); 2P later-round starts free-running (the real load is 1P; LR2 holds their
programs); the natural clear's / PERFECT's / EXTEND's `$97F8` at the pass's end (unmeasured free-running).

### M7.115d: the potion (type 12) opens the treasure room -- the owner's "fills the level, then crashes"

**Found** (the owner, 2026-10-09; reproduced headless, `scratchpad/m7115c/pu12.js`): after the type-12 item the room
filled and then nothing moved but the round's bubbles, which flowed until they popped -- about forty seconds later the
timer advanced the round.  `$890D` shuts both ISR gates; the engine's fill stopped at its last row's `DEC C`, and the
machine goes on: `$898F LD A,4 / CALL $8E05` (a RET on 48K) / `$8994 LD A,1 / LD ($FEC4),A / LD ($FEC5),A / EI / RET`
-- both gates OPEN (`$93DC` reopened the even one every pass, so the bubble manager ran; the odd gate stayed 0, so
`$A3AD` / `$AA60` never drew or moved anyone).  And `$894B CALL $8C14` was a named stub ("render work"), so the
round's bubbles lived on where the machine's are gone at the collect.

**Measured** (`tools/potion.py` -> `build/potion_fixture.json`, ~2.5 min, `verify` MATCH): the real load, a type-12
item laid under P1 at the end of ISR 600 / 700 and taken by the game's own item pass, then right / left alternately;
per ISR the gates, P1's X / Y, `($FED1)`, the round and the live bubbles; the take (`$87F0`, frame F), the dispatch
(`$890D`, frame F + 1: the award runs past the interrupt), the gate writes (`$890F` / `$8912` 0, `$8996` / `$8999` 1 in
frame F + 5), the ISRs lost under `$8C14`'s DI (F + 2..F + 5), and the room's advance (frames 2,473 / 2,728).

**Engine:** `treasureFill` ends at the machine's tail (both gates 1; the table-full exit `$8974` leaves them);
`treasureArm` calls `$8C14` (`extendReveal`, `$9500`'s own spelling: the 19 RES 7s and the reveal).

**Result:** PT1 -- through play, every ISR from F + 6 to the room's timer window holds the machine's `($FEC4)`, P1's X
and Y, `($FED1)`, the round and the live bubbles (1,862 / 2,017 rows), `($FEC5)` open but for `$93DC`'s dark-window hits.
The treasure block's two-exit row: the normal exit opens both gates, the table-full one leaves them.  The handler oracle
(puhandlers, bracketed at `$8949`) stubs what lies past its bracket.

**Still DECLARED (PT2, pinned):** the potion's T -- the dispatch one ISR early (the engine makes the collect whole in
its pass), the four ISRs the machine loses under `$8C14`'s ~250,000-T DI window run in the engine, so its passes sit at
other phases through the room (`$FEC5`'s dark-window ISRs differ on 4 / 1 rows) and the room advances 5 / 4 frames
early.  Timing it is a block (BB_EXT_BLOCKS, as EXTEND's `$9500` reveal is) -- a later increment.  (M7.115e: timed as a block -- below.)

### M7.115e: the potion's T, a block

**Measured** (`tools/isrcarry.py`'s potion sources -> `build/isrcarry_fixture.json`; `tools/potion.py` 'fill' ->
`build/potion_fixture.json`; both `verify` MATCH): a type-12 laid under P1 and played on to the game's own `$890D` on
round1_48, r50_48, round1_2p48, lastdia81 (round 81: type 9, offset -1) and the real load (potion.py's f600), each at its
own phase, sixteen forced, three a DI that put a boundary 1..3 T into it (`$890D`'s and `$8C14`'s) and two at the head
window's close (125 runs).  `$890D` to its RET is ONE program: 237,047..244,659 T exact (239,368 on round1_48 and the
real load).  From `$890D` (each write at its instruction's start): `DI / XOR A`, `$890F` / `$8912` both gates shut at 8 /
21, `$A36C` -- twenty `LD (HL),A` from 89 into `$5B00..` (CONTENDED, 4 T in), twenty from 645 into `$FDEE..` -- `$891D EI`
at 1,204 (the head's window [1, 1,212]: the end of the XOR A after it), the arm's stores 1,212..1,356, `PUSH IX / CALL
$8C14`: `$8C14` at 1,404 (round 81 +12).  Then `$94C2`'s `res7` and the reveal's six routines (their RET at `$894E`), POP
IX, the fill to `$899D`'s RET.  The fill's probe self-modifies `$89A9` every cell (`$89A1 LD ($89A9),HL`).  The replay with
the machine's ISR T gives every acceptance and the end on all 125; the ISRs inside are gate-closed and uncontended (493 /
488 T).  The closing edge: a boundary 32 T before 1,212 is LOST, 31 T before is TAKEN AT 1,212 (all five worlds).  The
reveal's close cannot be reached so: its contended stores re-sync the main line to the ULA (TRAPS #309).  The fill alone,
plain, on every map `treasure.py` holds (seven rounds x both offsets, three built shadows): 9,571..26,882 T, the
table-full exit on four.  The item pass on the real load: `$8669`'s entry to `$890D` 64,750 T plain (the chirp 55,793 of
it), 62 T after the handler's RET; contended, its main line waits 147 T (the erase 83, the award's glyphs 31, the chirp's
OUTs 33).

**Engine:** `BB_EXT_BLOCKS.potion` (lazy; `BB_PT`, `BB_PT_SCRIPT`): `potionBlock` -- `pt_head` (`extModel`: the gates, `$A36C`
in the machine's order, the arm, its twenty contended stores on the program), `res7` and the reveal, `pt_fill`
(`ptFillModel`: the probe's groups out at the first SOLID cell, the cursor store, the placements, the table-full exit
or the gates).  Inside a pass it begins at `potionPos` -- `$8669`'s entry (calleeAt) + the item pass's charge so far
less `BB_PT.AFTER` + its chirp spent in time (`itChirpT`) -- the pass to there spent now (passSettle, the join's way); the
chain waits after `$8669` ('potion') while step() drains it; the windows ride the frame clock.  `treasureProbe` writes the
operand; `boltSlotsClear` writes in the machine's order.

**Gates:** LZ9 -- each potion row from `$890D` seeded with what the machine's run reads, its frames driven as step() drives
them with the machine's ISR T: every acceptance, all 469 interrupts the two windows lose, the RET's wall T, the main
line's delays, all 7,351..7,493 writes by address and T and those outside the reveal by value too; LZ4 + its five
programs; IC 350 runs.  PT3 -- `ptFillModel` = the machine's fill on the 17 maps, T and every write.  PT2 restated: the
engine's `$890D` after ISR F + 1, its block resumed once, the four ISRs LOST, five ISRs under it.  PT4 -- the same world on the
page's own path (skipProbe on, a fractional clock): the block runs and drains, the room advances.

**Still DECLARED (PT2, pinned):** the item pass's own contended accesses are not on the pass's program, so `$890D` comes
142 / 139 T early free-running (601:31,248 / 701:39,987, the machine's 31,390 / 40,126), the block ends 90 T early, and
the room's passes -- each draws its items, off the program too -- sit at other phases: `$93DC`'s dark window holds other
ISRs (4 / 3 rows) and the room advances -1 / 0 frames (until M7.115e -5 / -4).  Next: the item pass on the pass's program.  (M7.115f: on it, and on the grid -- below.)

### M7.115f: the item pass on the pass's program and its grid

**Measured** (`tools/itemacc.py` -> `build/itemacc_fixture.json`, ~1 min on 20 workers, `verify` MATCH): the real load
(passacc's drive; P / O after) with a potion laid at the end of ISR 600 / 700 (potion.py's worlds, to the room's advance)
and eight items laid at ISR 600 (`fruit:f600`: under P1, in his walk, far, Y 8 -- rows into the ROM --, phases that expire
at the first tick, the power-up slot; to frame 1,300); seventeen saved states holding items and round1_2p48 with items under
both players, 600 frames of random keys.  Per pass passacc's row from F - 2; per `$8669` call its access program (offset
from the entry, T into the instruction) and its instruction grid, the ISRs inside, the handler's window, each chirp's 40
OUT starts.  The first call of each distinct (program, grid) and every take / expiry / erase / dispatch REPLAYED plain from
its entry -- its seed, program, grid, T, its `LD A,R` draws, the take's DI offsets -- and 45 FORCED (the flood, the storm, P1
carried poked at a walk's entry).  82,709 calls; 277 replays; 16 takes (one by P2), 33 expiries, 49 erases (14 solid cells),
16 awards (two copying the high score), both spawns.
- **The accesses.**  An ink cell (`$8765`): its read 4 T in and `$876A LD (HL),A` 21 T on (4 in) -- the attributes.  A blit row
  (`$A2C2`'s, the NOPs in): `$A306` / `$A30B LD A,(DE)` (the sprite at `$5D00..`, always contended) at 0 / 28, `$A308` /
  `$A30D`'s stores at 11 / 39 (4 in), a row aimed into the ROM keeping its reads.  The erase's four cells (`$8777`, 39 T into
  an open `$876C` cell, 47 into a solid one) and the restore's rows (`$A360` / `$A364` at 7 / 29).  The award's glyph rows
  (`$8052`, 7 T into each).  The chirp's 40 OUTs (`$8CB4`: the ULA's port, 8 T in).
- **The instructions** are the BB_IT / BB_SC / BB_AW sums' own lists, term for term: on every replay the grid laid out
  from the entry to the RET or the handler's `JP (HL)` and the program are the machine's (277 / 277).
- **The take's award runs with interrupts off** -- `$87F9 DI` .. `$881C EI` and the `LD C,$28` after it: an interrupt whose
  pulse falls there is LOST on the machine.  No natural take in the twenty worlds put one there: the walk runs in the
  frame's first pass, its takes early (the room's 21-entry walk takes nothing; P1 never reaches its rows).
- **Free-running** the passes are the machine's from F - 2 through the take, the potion's block and the room: 224 / 166
  passes to frame 840 / 878 -- where the machine's walk reads P1 AFTER an ISR inside it (the room's walk spans the frame;
  its later entries' box tests see P1 where the odd ISR moved him -- an X test's way out flips, ~141 T; the call's plain
  replay takes the other path, `same` false) -- and the fruit world 232 to frame 644, where `$931A` makes one probe more
  after the ISR inside its pass.  The same class both times: a callee the point falls inside reads what its ISR writes.

**Engine:** the item pass's instructions on the pass's grid in the machine's order (BB_GRID's `IT.` / `AW.` / `CH.`
keys -- the spawns, the entry, the unpack, the collect and its take, the age and its expiry, the weather, the ink, the
erase and the restore, the blit, the award (`ik`: logged inside the item pass only), the chirp); a CURSOR through them
(`pgc` / `pgO`, gridWalk's deferral: a CALL key's rest at the kid's closing RET) from the callee's entry; each contended
access on the program at the cursor (`itemAcc`); the handler's `JP (HL)` a CUT (`pgCut`: the region ends laid out with its
CALLs' rests to come; the handler not laid out) and its entry kept (`itHandlerO`).  The take's DI window on the frame clock
(`itDiLast`, `itDi`; M7.105's +1).  The chirp inside a pass (`itemChirpPass`): each edge at its OUT's place (`passClock`),
those past the point held MARKED and given the waits of the accesses between the point and them when logged
(`passTailWait`'s `pTailCum`, `flushHeld`) -- PROVISIONAL since M7.84 until now.  The potion: `potionPos` = the cursor's
`$890D` on the frame clock (M7.115e's charge-so-far formula gone with `itChirpT` -- dead inside step(), the full battery's four
survivors; a lost cursor is COUNTED, `ptPosMiss`); past the point its settle hands the pass's tail to `pTail` (the chirp's last OUTs wait from the
next frame's phase before the block's first segment: `lzStep(budget, s)` from step()'s clock) and resolves the ISR's
acceptance from the grid (the chirp's instruction in progress); the resumed pass's program starts after `$8669`'s rest and
the chain's CALL (`IT.AFTER`, `BB_PT.AFTER` + 17) and takes no prefix waits off (`passPreD` 0 -- the prefix's were spent
at the settle).

**Gates:** IA1 the fixture; **IA2** the 277 replays seeded into a fresh engine (their draws fed): program and grid =
the machine's, count and SHA-1; **IA3** free-running, every machine pass from F - 2 at its frame, phase and program to the
pinned divergences, each with its cause; **IA4** the potion's `$890D` = the machine's (601:31,390 / 701:40,126; until
M7.115f 142 / 139 T early); **IA5** the chirp's 40 edges at the machine's frame and phase on the three takes inside IA3's
windows; **IA6** the award's DI window: its edges the machine's on 14 takes, on the frame clock, an interrupt inside lost.
PT1 / PT2 restated (the dispatch exact; the room's `$FEC5` rows that differ all from 840 / 878 on), SFX5 restated (the
edges at their OUTs' places, one gap of the ISR window).

**Still DECLARED:** the callee an interrupt falls inside runs whole before its ISR -- the item walk's box tests and
`$931A`'s probes read what the ISR writes on the machine (IA3's pins; the room's dark-window rows 4 / 5 and its advance
-1 / 0, PT2).  Next: the walk cut at its interrupt.  (M7.115g: the ISR runs inside the callee at its read -- below.)  A small handler's own T (types 0..5, after `$8838 JP (HL)`) is not
charged (M7.92).  An edge-look cut at `$8669` on a spawn path leaves the spawn's own T out of the look (itemSpawnT).

### M7.115g: the callee an interrupt falls inside

M7.114a cut a pass only at a callee's ENTRY: a callee the point fell inside ran whole before the ISR, so its reads after
the point saw the world as it was before the interrupt, and the ISR (run after the whole callee) saw the callee's later
writes.  M7.115f's IA3 pinned two places it bites.

**Measured** (`tools/straddle.py` -> `build/straddle_fixture.json`, ~3 min on 20 workers): a census of the class.  itemacc's
three real-load worlds and every 48K saved state, 600 frames of random keys each (52 worlds): every chain CALL with exactly
one ISR accepted inside it -- 27,087 STRADDLES.  Each replayed from the callee's entry, plain and atomic: *before* (the
counters' INC at the point, as ctrRead gives it -- the engine's rule when the point falls inside), *after* (the ISR's
changes laid over the entry -- its cut at the entry and at an edge read), and the *exact cut* (the ISR's changes, and its R
delta, at the machine's instruction) -- ASSERTED to be the natural call on all 27,087, so the method is the machine's.  And
the ISR re-run *late*: from the point's state with the callee's post-point writes laid over it (the engine's order until
now), against the natural ISR's writes, each read of the callee's writes named.  Two traps on the way (TRAPS #313): the
keys an ISR reads are the ones at its FIRST instruction (a driver may change them at the frame boundary, between the
acceptance and that read), and a plain replay sees the R register move by the ISR's own instructions.
- On the engine's rule 141 calls took another path or wrote other bytes: `$8669` 79 (77 the treasure room's 21-entry walk,
  the collide's `$87B8` X / `$87B3` flags read after the odd ISR moved P1 -- IA3's pin), `$8FA5` 18 (P1's jump byte `$FD89`
  at `$8FBA`), `$925A` 15 (the enemies' Y in its box tests, `$9312`), `$931A` 12 (its probes' Y / X / flags), `$C002` 12 (the
  sparkle blit's OR merge, `$A307` / `$A30C`, reading screen bytes the ISR's sprites drew), `$A9ED` 4 (P1's Y / X), `$8E3A` 1.
  The other fourteen callees: never.
- Run late, the ISR wrote otherwise on 19 more (the dark window's 105 excepted -- M7.114b models them): 15 the screen bytes
  a main-line blit (`$A9ED`'s boss, `$C002`'s sparkles) and the ISR's sprites share, 2 the potion's (its block begins after
  the ISR already, M7.115e), `$925A`'s and an item handler's one each.

**Engine:** `isrSite(o, cut)` -- a model calls it before a read of what the ISR writes: `o` the reading instruction's plain
offset (the cursor, `pgO`, plus its place in the key), `cut` where the keys logged so far end.  The first at or past the
point runs this frame's ISR THERE (`isrHere`): its acceptance phase from the grid so far (gridPh on the keys, cut at
`cut`; a MISS counted), the ISR with the pass's program, grid and cursor flag set aside and the budget Infinity (its edges
no main-line OUTs), its start the point (`isrStart`, which the clicks now read: `tframe - carry` was it only at the frame's
end).  Then `isrDone`: step()'s frame end runs no second ISR (it re-bases the DI windows first, either way), gridResolve takes no second
phase, ctrRead gives the RAM's counter (the INC is there).  Refused, each site COUNTED (`isrInRefused`), where the frame's
ISR is not a plain one -- a block's held writes, the dark window, a build's window, a reveal's re-based reads, the
umbrella, a lazy block, the potion pending; a DI window over the point loses it (`intLostAt`, the pure test).  The cursor
walks every pass's grid now, not the item pass's alone.  The sites: the collide's `$87B3` (P's +7), `$87B8` (X), `$87BF`
(Y), `$87E2` (the lock) -- its T summed as its tests run (`itemCollideT` gone: it summed ahead from the bytes before the
ISR); `$931A`'s probe's `$9377` / `$937A` (+7), `$937E` (Y), `$938D` (X).

**Gates:** SG1 the census (per callee, pinned); SG2 each of the 315 gate rows (`$8669` 157 with the 79 of the class,
`$931A` 158 with 12) seeded into a fresh engine with the machine's ISR -- its changes -- taken where the engine takes it:
the grid the machine's natural grid on all 315, the ISR inside the callee on 90 of the 91 (the other's read is the
handler's: `$889C SET 6,(HL)` after the `JP (HL)` -- the small handlers run unclocked, M7.92); without the nested ISR 89 of
the 91 differ (the two that do not: a row that writes other bytes on the same path, one whose counterfactual reads a cell
the machine's run never did).  SG3 the boundary (the site before / at / after the point; nothing of the ISR on the program
or grid; each refusal alone; the DI window; a lost cursor; the cursor across a resync -- the deferred rests dropped -- a
mark and a cut; ctrRead; gridResolve; the phase from the grid, and its MISS; both clicks at isrStart).  SG4 each site at its reading instruction's FIRST T -- the ISR flips the byte, the point at the
read's start (the decision the ISR's) and one T later (the read's) -- the places from the instruction lists, not the
engine's constants (TRAPS #314).  **IA3 re-pinned:** free-running 746 / 656 / 1,065 passes the machine's (until M7.115g
224 / 166 / 232), 1,583 / 1,742 / 276 ISRs run inside a callee and no step running two -- to the power-up spawned in the
room at frame 1448 in both potion worlds (its `$8A38 LD A,R`: the machine drew 26 / 29, the engine's stand-in 59) and the
fruit world's first sparkle at 806 (the engine blits it; its accesses are not on the program, M7.114a's declared list).
PT1 / PT2: the room the machine's to 1448 -- f700's to its advance (0 dark-window rows, 0 frames), f600's one row and -1
frame after its 1448 draw (until M7.115g 4 / 5 rows from 840 / 878).

**Still DECLARED:** the census's other callees -- `$8FA5`'s P1 jump read, `$925A`'s box tests, `$C002`'s blit merge,
`$A9ED`'s P1 reads, `$8E3A`'s tally (50 rows: the same mechanism, each callee's reads on the cursor; M7.115h: the first
three's 34 -- below) -- and the late ISR's 17 (the screen bytes the main line's blits and the ISR's sprites share: the ISR
must come before those WRITES too); a power-up handler's read (`$889C`; the small handlers' own T, M7.92); the R
register's stand-in (the potion pins); `$C002`'s blits and erases off the program (the fruit pin).

### M7.115h: the census's next three callees -- the jump tone, the contact pass, the clear decision

**Measured** (`tools/straddle.py`, re-captured; its 27,087 rows unchanged): gate rows for `$8FA5`, `$925A` and `$8E3A` --
every row the old rule got wrong (34: 18 / 15 / 1) and every 40th of the rest (`$8E3A`'s every 10th: its countdown, drain
and anger are a few of a world's straddles), 277 rows (43 / 96 / 138), each with the natural grid, the seed and the ISR's
changes.  `$8E3A`'s seed gains the operands it reads as INSTRUCTION BYTES -- the clear latch `$8E3B`, the drain's base
`$8F3A`, the one-left latch `$90AA` and the walk's SET / RES `$90D0`: the seed's rule (read before written, an
instruction's own bytes out) left them out, and replayed without them 32 of the 138 take another path -- the latched
countdown's and the latched anger's (TRAPS #315).  And FORCED (`FORCED_8E3A`): `$8E3A`'s paths no natural straddle walks,
from round1_48's first `$8E3A` entry with pokes, replayed plain and atomic to the RET -- the one-left anger's first walk
over one slot and four (479 / 836 T), the countdown's advance (82 T), the drain's band with an item left (1,654 T): each
grid, T and seed (the battery's one survivor asked for them: the first walk's head had no machine grid).
The first capture's fifteen `$8E3A` rows found the paths the engine did not lay out (the drain, the anger: twelve).  The class rows' reads of ISR-changed bytes, by
the machine: `$9312` 44 (an enemy's Y in the box test), `$8FBA` 17 (P1's jump byte), `$930A` 8, `$92CC` 2, `$92E6` 2,
`$92EA` 1, `$8EB7` 1 (the tally), `$8FAE` 1 (P2's +$5A after an ISR inside P1's tone).  `$8E3A`'s 138 rows walk 13 of its
paths: the tally's (the many, the one left), the drain's (items left), the latched anger's, the boss round's, the
countdown's (`RET nz`, `RET c`).  One `$925A` class row (elfire, frame 292) is the census's late `$925A` row: the ISR run
after the kill's stores read P1's +4 and +$5A (`$AB5A` / `$AB38`) -- inside the callee it finds them as they entered.

**Engine:** each read of what the ISR writes, and each store it reads, a site at its instruction (isrSite); the read's
key logged before the decision it feeds -- the keys split at the reads (BB_GRID's `JT.B2` / `JT.B7` / `JT.PH`, `PE.B2` /
`PE.K_F`, `TR.E_B3` / `TR.AX`), the places from the instruction lists (BB_JT_GRID `R_B7` 26 / `R_PH` 17; BB_PE `R_P1` 31,
`R_P2` 14, `R_KF` 7, `W_5A` 42, `W_4` 61; BB_TR `R_PX` 10, `R_PY` 51, `R_E7` 15, `R_E3` 7, `R_AX` 23; BB_RC `W_FECA` 4,
`W_ANG0..2` 37 / 7 / 20, `WK_RX` 27, `WK_WX` 38):
- `$8FA5`'s arms: `$8FAE BIT 2,(HL)` (+$5A), `$8FB5 BIT 7,(HL)` (+7), `$8FBA LD A,(HL)` (the jump phase).
- `$925A`: `$9262` / `$9270 BIT 7,(IX+7)` (each player's +7), `$92BB BIT 2,(IX+$5A)`, `$92C3` / `$92CC` (the player's X /
  Y), the walk's `$92E6 BIT 7` and `$92EA BIT 3` (+7 READ TWICE, as the machine reads it: an ISR between them seen by the
  second), `$9312` / `$930A` (Y / X); the kill's `$927D LD A,($FED0)` and `$9283 LD A,(IX+$5A)`, and its two stores
  `$9290` / `$9293` -- the ISR's P1 handler reads them (the late row).  Not on the boss's `$AA35 JP $927D` (its keys are
  logged ahead, BB_SM: no cursor there).
- `$8E3A`: the tally's slots (`$8EB7`) and its count's store (`$8EC1` `($FECA)`, which the ISR reads at `$8DD8`); the
  drain's counter read (`$8F36`: ctrRead's INC when its site is refused; until M7.115h it read the counter raw); the
  one-left anger's gate stores (`$90B2` `($FEC4)` := 0, `$90BA` / `$90BD` := 1: an interrupt inside the walk finds the odd
  gate SHUT) and its walk's read-modify-writes (`$90CF SET 2,(HL)`; `$90D3` / `$90D5`, the X read and its store apart: an
  ISR between them is overwritten, as on the machine) -- on `$8E3A`'s path only (`g`): the hurry's fall-in and the
  respawn's calm run the walk as before.
- `$8E3A`'s paths on the pass's grid: the drain (`$8F36..`, `$8F94`'s count entry by entry), the countdown
  (`$8F29..$8F35`), the anger latched and first (`$90A9..$90C0`, the walk `$90C1..$90D9`).  The clear (`$8ECF..$8F28`, with
  its DI window `$8EF5..$8F19 EI`) is a mark (pgBad: the cursor lost after it) -- DECLARED.
- **`$8E3A`'s entry.**  `pbase` -- every in-pass clock's origin for the running callee (calleeAt, ctrRead) -- is set at
  the top of chainWalk's loop, and `$8E3A` is called after the loop: inside a pass its base stayed `$8E2A`'s, and the
  countdown's cdPos put `$8F29` 65 T early on round 1's latched passes (`$8E2A`'s run and the CALL; the cursor at `$8F29`
  against cdPos).  M7.106's gates could not see it: CD3 tests cdPos outside a pass (calleeAt's other branch) and CD2's
  world takes the split route.  It is `$8E3A`'s own entry now (TRAPS #316).
- **The countdown after a nested ISR:** cdPast gives the RAM's timer -- the INC is there already: no second INC, no cut.

**Gates (bb.test.js, the last block "M7.115h SH"):** SH1 the census's gate rows for the three, pinned (the class rows'
reads by PC, `$8E3A`'s 13 paths); **SH2** all 277 rows seeded into a fresh engine with the machine's ISR at its acceptance
offset: the grid the machine's on all 277, the ISR inside the callee on all 34 class rows; without the nested ISR 33 of the
33 class rows that part paths take another, and the tally's `wr` row writes the old count (`$FECA` 3 for the machine's 2);
the late row's nested ISR sees P1's +4 / +$5A as they entered (`[0, $80]`; the kill's `[$50, $84]` after it); and the four
forced paths' grids the machine's (no interrupt); SH3 the
countdown placed from `$8E3A`'s entry (cdPos = the cursor's place = the pass's phase + the entry + RC.PRE), after a
nested ISR the RAM's (`$0176`: none, no cut; without one the ISR's INC: advance, cut at `$0177`), the clear's mark, and the
paths that are not these callees' (the boss's `$927D`, the hurry's fall-in, the respawn's calm) run no site and lay out
nothing; SH4 each of the 28 sites at its instruction's first T and one T later -- the places from the instruction lists
(TRAPS #314), a refused site leaving the drain's read to ctrRead's INC.  The free-running gates (IA3, PT1 / PT2, CD1..3)
unchanged.  Suites bb 1,859 / kit 120 / selftest 34.

**Still DECLARED:** `$C002`'s blit merge (12 rows) and `$A9ED`'s P1 reads (4) -- M7.115i / M7.115j; the late ISR's 15
screen bytes (`$A9ED`'s boss and `$C002`'s sparkles); `$8E3A`'s clear on the grid and its DI window; the boss's `$927D`
reads; a power-up handler's read (`$889C`).

### M7.115i: `$7E80` on the pass's program -- every element round's pass, and its HALT a block

**Found** (2026-10-11, measuring the owner's boss fix: tools/bossfree.py's bodies ran up to 4 frames ahead by frame 1400):
`$7E80` -- the element emitter, chain entry 8 -- lives at `$7E80..$7F0A`, CONTENDED RAM: every opcode fetch, operand read and
internal cycle on its pc waits in the screen fetch.  The engine put only `$7E80 LD A,($7E0E) / OR A / RET z` on the pass's
program (M7.114a; the rest counted `paMiss`), but on a round with an element -- 49 of the 81, the boss's among them -- EVERY
pass runs on through `$7E85..$7E9D` (`LD ($7EFB),A / CP 5 / LD A,4 / JR c / LD A,1 / LD ($7EB2),A / LD A,($8E3B) / OR A /
RET nz / LD A,($8DBD) / CP $2A / RET nz`): each such pass came out 0..87 T short by its phase.  And in the frame ($8DBD) =
$2A (42 frames into a round, then every 256) it scans the twelve bubble slots, finds a free one and `$7EC2 EI / HALT`s --
the engine gave the frame away from wherever the HALT began (`spend(BB_FRAME_T)`, `blocked`) and ran `$7EC4`'s re-test, the
emit and the rest of the chain BEFORE the ISR that may take the slot.

**Measured** (new tool `tools/emitacc.py` -> `build/emitacc_fixture.json`, ~1.5 min on 20 workers, `verify` MATCH): the real
load poked to rounds 80 / 10 / 25 / 3 / 17 at ISR 1000 (bossfree's way), free-running to frame 1700 -- every pass's [frame,
phase, plain length, program], every ISR's [label, T, acceptance phase], every `LD A,R`'s draw -- and eighteen saved states
with an element, 600 frames of random keys: 109,806 calls, 85,881 on the long path, 79 scans, 37 HALTs, 20 emits, 17 refused
at a solid emit point.  The first call of each distinct program and every scan replayed plain from its entry ('a', to the
HALT) and from `$7EC4` after its ISR ('b'), 80 forced (no free slot, the clear's RET, the slot filled during the HALT, the
emit point flipped), and 40 PHASED: a scanning call's entry moved to `shift` T before a frame boundary -- the bottom border,
nothing waits there -- so the point lands to the T: 10 / 70 T in, AT and 1 T into `$7E98`'s read, AT and 2 T into the EI,
AT and 1 T into the HALT's first step (TRAPS #320).
- **The accesses**, per instruction, keyed by pc and T (taken and not are two keys; scratch derive over saved states with
  the paths forced), assembled per BB_SM key from costsmall's blocks: `BB_SM_ACC` now holds all 26 of `$7E80`'s keys.  A
  taken JR / DJNZ waits five more times on its operand's address (7..11 / 8..12 in); an `(IY+d)` store four or two times
  (11..15 / 14..15); `$7E0E`, `$7EFB`, `$7EB2`, `$7ED7` and the emit table `$7F0B..` are contended, the slots, `$8E3B`,
  `$8DBD`, `$FEC5` and the collision map the table points into (`$F84A..`) are not.
- **The HALT** runs 4-T steps, an M1 at `$7EC3` then `$7EC4` -- contended: in the screen fetch the steps lock to the ULA's
  cycle and all 37 natural HALTs were taken at phase 1 (one phased HALT that began past the screen's last line, at 3).  The
  interrupt is taken at the end of the first step that ends at or past the point; an EI in progress at the point holds it
  to the end of the HALT's first step (phase 6 / 4 / 3 on the phased edges); an interrupt taken before the HALT -- inside
  the call before its EI, or AT the EI's start -- leaves the HALT to wait for the NEXT one, a whole frame (TRAPS #318).

**Engine (web/game.js):** `BB_SM_ACC` for every key; the count loop in the machine's order (each slot's test, then the DJNZ
and the next slot's read -- the DJNZs were summed first); the counter read `$7E98` by ctrRead (the INC when the read starts
at or past the point); a site (isrSite) at each read of what the ISR writes -- each slot's `$7EA7 LD A,(HL)` (+9) and
`$7EBA BIT 7,(HL)` (+7), BB_EM's `R_*` places.  **The HALT a block on the frame clock** (`emHaltBegin`): '7EBCt' split where
the machine splits it -- BB_EM.HEAD (`$7EBC JR z` taken, `$7EC2 EI`) and BB_EM.BIT (`$7EC4 BIT 7,(HL)`), their grid keys
`EM.HEAD` / `EM.BIT` --, the pass to the HALT spent (passSettle: the potion's way, `$7E80` charged to the HALT), the HALT's
steps walked to the point (`emHaltWalk`: the ISR at `haltPh`, exact), and the pass waits there ('halt', chainWalk): step()
ends the frame, and mainLoop resumes the pass at `$7EC4` (`elemEmitB`, charged as `$7E80`'s) and the chain after `$7E80`.
LATE (the EI begins at or past the point): this frame's ISR at the grid's phase from the region the HALT cut, the next frame
the HALT's -- walked from its start, no pass (`emHalt.wait`) -- COUNTED (`emHaltLate`).  Outside step() (no frame clock, or a
pass driven alone) the old path: the frame given away whole, `blocked`, the re-test at once (DECLARED, as since B0).  The
walk refuses a point with no frame clock, or more than a frame away (no HALT waits longer), by name.
`paMiss` is gone.  Two pieces the hand battery proved EQUIVALENT went: a site at `$7E98` (nothing between it and the
scan's first read is what the ISR writes: the ISR there, at that read or at the next callee's cut is the same machine) and
an `isrDone ||` in the late test (every site's read comes before the EI).

**Gates (bb.test.js, the last block "M7.115i EA"):** EA1 the fixture; **EA2** every replay's parts and every forced run
seeded into a fresh engine -- the program, the grid and the T the machine's, count and SHA-1, all 226; **EA3** free-running,
the real load poked to rounds 25 / 17 / 3 (its class's `LD A,R` fed: BB_Rng is a declared substitute): every pass from frame
998 to 1700 at the machine's frame and phase with its program (reassembled across a cut and across the HALT), every ISR's T
-- r25 2,911 passes, r17 2,713, r3 4,373, each with its two (one) scans and HALTs; r17's program parts once by an access that
waits nothing (`$9B87`'s read of the fire slot `$5B0E`: `$9AEB`'s fire updates, off the program since M7.114a); **EA3b** the
two that part at gaps outside `$7E80`: r80 at frame 1113 -- the boss's first draw, 891 contended accesses in the machine's
pass, the engine's 59 (its erase and draw blits: M7.115j) -- and r10 at the odd ISR 1472, 24 T short: an enemy above the
HUD probes the dummy page (`$B47B`'s `OR (HL)`s through `$AED7`'s `$712F` pointer read `$712F..` / `$710F..`, contended,
8 accesses off the ISR's program; the state the game reads the machine's); **EA4** the walk from each of the 72 HALTs'
starts their steps and phase, the free-running worlds' HALT ISRs at phase 1; **EA4b** the 40 phased runs (the ISR inside
`$7E80` at the machine's acceptance phase and the HALT late; the EI and the first step's edges one step); **EA4c** the late
branch's parts (a refused site: ctrRead, the grid's phase from the cut; the tail; the sites' places in costsmall's keys);
**EA4d** the scan's 24 sites at their reads' first T and one T later (the count, the found slot, the acceptance phase);
**EA5** the boundary (the late HALT's frame, the resume, the no-clock path, the walk's refusals -- no clock, more than a
frame --, a step ending AT the point, reset()).  **HB20** counts the HALT's resume (its `stale` clause could no longer fail:
nothing sets `blocked` inside step() now; PA11 / PA6 keep step()'s side of it, through a stubbed mainLoop).  **LRF2** now holds every ISR to its worlds' ends (it stopped at the first `$7E85`: r10 188,
n3 419, r81w 255); **TB3** re-pinned -- the boss's bodies' frames the machine's to body 10, then at most 2 ahead (was 6 / 4),
DECLARED on the boss's draws (M7.115j); PA2's `paMiss` clause gone.  Suites bb 1,875 / kit 120 / selftest 34.

**Still DECLARED:** the boss tick's draws (`$A9ED`'s erase and draw blits: M7.115j -- below, done); the floor probe's dummy-page reads in
the odd ISR (`$B47B` above the HUD: next); `$9AEB`'s fire updates (`$9B87` ..); the late HALT's natural case is phased only
(about one emit in fifty); outside step() the HALT is the old frame-whole spend.

### M7.115j: the boss tick on the pass's program and its grid

**Found** (EA3b's r80 pin, M7.115i): the boss tick `$A9ED`'s code is not contended (`$A84D..$AA4E`), but a BODY (`$AA0E`,
every 32nd tick) blits.  The erase `$A9DA` runs four `$A929` rows, each eight pixel rows of four `LDI`s from the shadow
(`$A000` + the screen address) to the screen and four `$9D4C` attribute cells (`BIT 5,(HL)` on the colour shadow, `LD
A,($8309)` or `($830A)`, `LD (DE),A`). The draw `$A8C1` runs four character rows of eight pixel rows of four `LDI`s from the
sprite at (`$A8C2`) and the attribute walk's sixteen `LDD`s from (`$A8FD`) down.  Every block move writes the screen: SkoolKit's ldi
puts `(DE)` on the program three times -- the store 11 T in and two internal cycles at 14 and 15 -- and `(HL)` at 8 when
the source is contended (the class-0 sprite at `$5B00`, never in play); every `$9D4C` store once, 4 T in.  **832
contended accesses a body**, where the engine put none: frame 1113's pass held the machine's 891 against the engine's 59,
and r80 parted there.  And the engine summed the blits' keys out of the machine's order -- `zs('A929', 4)`,
`zs('A9E7t', 3)`, `zs('A966t', 3)`: CALL keys n times, so the cursor was lost in every body and the region not laid out
-- and logged the bounce's RET before its arms.  So an interrupt inside a body ran after the whole tick: the census
(tools/straddle.py) had 4 straddles reading P1's Y / X before the ISR moved him and 10 whose ISR, run late, read the
screen bytes the blits only write after it (its sprites drawn on the boss).

**Measured** (new tool `tools/bossacc.py` -> `build/bossacc_fixture.json`, ~35 s on 20 workers, `verify` MATCH): the real
load poked to the boss round at ISR 1000 (emitacc's r80), free-running to frame 1700. It holds every ISR's [label, T,
acceptance phase] and, at its end, digests of the bitmap with every ROM-glyph cell zeroed (the cell's pixel rows 1..7 a
glyph's: the HUD's text, the banners, the round number -- the port draws its own) and of the attributes.  Six boss-round
saved states run 600 frames of random keys.  That is 35,969 calls and 962 bodies, every body's program 832 accesses.  The first call of each
distinct (program, grid) was replayed plain from its entry (247: seed, program, grid, T, the final byte at each address
written).  Forty-eight runs were FORCED from each world's first body: P2 over the boss, P1 over it, dying over it, beside
it, the tape's SCF / RET pair, the sprite at `$5B00`, the box's corners. Four of them keep the machine's instruction list
[pc, offset].  And 84 were PHASED (TRAPS #320's way): the body's entry moved into the bottom border so that the point
lands AT and 1 T into eleven of its instructions, with P1 beside the boss and over it, at BOTH parities of the ISR
(`$8DBD`'s bit 0 flipped, `$AA00` re-aimed so the tick still reaches its body -- the even ISR draws the sprites).  Each
records the ISR's offset, T and phase, the call's grid, program and seed, its stores before the ISR, the ISR's changes,
its reads of the bytes the call writes (with the entry's byte), and the final bytes.  `tools/straddle.py`: GATE +=
`$A9ED` -- every class row, every row whose ISR run late writes otherwise, every 10th of the rest (31). Each carries the
final bytes and, on a late row, what the ISR read as it read it.

**Engine (web/game.js):** `BB_BT` holds the places in BB_SM's keys: MV is each blit key's first block move (`A929` 137,
`A94Et` 32, `A8C1` 148, `A8EFt` 10, `A8F9t` 84, `A901f` 66, `A921t` 10). ST is the stores: `$9D4C`'s 12 / 20, `$AA01` 30,
`$AA0A` 23. R is the reads of what the ISR writes: P2's and P1's +7, P1's Y and X, the matched player's +$5A. BN is the
bounce's stores by arm, and J927D is `$AA34` / `$AA35`'s head (`BT.J927D`).  `btAt` logs a blit key at the cursor
(btMiss counted if the cursor is lost).  `btMove` puts a block move's accesses on the program, then a site, then the
store.  `btAttr` logs `$9D4C` in order, with A loaded before its store's site.  The erase, the rows, the draw and its
attribute walk now run in the machine's key order (`bt`); so do the bounce (its RET after the arms, each store a site)
and the overlap (each read a site).  `$AA30` reads the MATCHED player's +$5A: until M7.115j it read P1's whoever matched.
The boss's path into `$927D` runs playerHit's PE keys and sites, the T in its own run; until M7.115j BB_SM's
`9281f` / `9288` / `928B` / `9297x` were logged ahead of it, with no site.  BB_GRID_SM gains `A978t` (`11x`: P2's RET c on a hit,
the one sum written by hand, which had no grid, so its region was never laid out).  The giant's path (`$A842`, `$A925`,
`$A9B1`: bt off) is as before.

**Gates (bb.test.js, the last block "M7.115j BA"):** BA1 the fixture; **BA2** every replay and forced run seeded into a
fresh engine -- program, grid, T, the boss after a body and every byte written the machine's, 289 / 289 (the SCF / RET
pair, unreached in play, DECLARED: counted on its 6); **BA3** r80 free-running: all 6,702 passes from 998 to 1700 at the
machine's frame, phase and program, all 703 ISRs' T, and the masked bitmap and the attributes at every ISR's end the
machine's -- 38 ISRs taken inside a body, each where the engine must take it (after `$A9FC`'s edge read and by the body's
last site); **BA4** the 84 phased runs: the ISR nested at the machine's acceptance phase after the machine's count of the
call's stores, what it reads the machine's, every byte the machine's -- the old rule (the ISR after the call) reads other
bytes on exactly the 28 late-class runs; **BA5** the 31 census rows -- the old rule wrong on all 4 class and all 10 late
rows, the engine right on 31; **BA6** the boundary (no program or site outside a pass, a lost cursor counted, the giant's
path untouched, `$AA30`'s matched player, the dead `$A901 RET z`); **BA7** every site at its instruction's first T and one
T later, the places from the MACHINE's instruction list (TRAPS #314): 302 stores of 19 kinds both ways, and five reads
with the ISR flipping what they read.  TB3's drift is 0 (every body's frame the machine's); EA3b's r80 exact to 1114;
SH3, SM1 and GR1 re-pinned.  Suites bb 1,882 / kit 120 / selftest 34.

**Still DECLARED:** the giant's blits (off the program, its region not laid out); the tape's SCF / RET comparator pair
(unreached in play: decayed to NOP / NOP before the boss round); the heart arm's grid on the boss's path (`9281t` in T,
`$FED0` is 0 in every captured state); `$C002`'s blits (M7.115k); the odd ISR's dummy-page probe (r10, EA3b).

### M7.115k: the sparkle walk on the pass's program and its grid

**Found** (M7.114a's DECLARED list; IA3's fruit pin, frame 806's pass 32 accesses short): `$C002`, the burst-sparkle walk
(`$8D49`'s CALL, the thirteenth chain entry), walks the fourteen two-byte particles at `$5CE0` -- contended: its `$C00B` /
`$C016` / `$C019` reads and its `$C04C` write-back have been on the program since M7.114a.  A LIVE slot (byte 0 & 7 not 0)
advances its phase and either restores the pixels under it -- phase 2, and phase 0, which frees the slot -- through `$C057
CALL $A314` (sixteen rows, each two stores into the screen from the shadow at `$A000` + the address), or ORs its sprite in
through `$C043 CALL $A2D5` (sixteen rows, each `$A307` / `$A30C OR (HL)` reading the screen and `$A308` / `$A30D LD (HL),A`
storing it; the sprite at `$CA80` is not contended).  The engine logged none of a live slot's keys on the grid, so its region
was a MISS and an ISR inside it was given BB_ISR_ACCEPT.  It put none of the kids' 32 / 64 contended accesses on the pass's
program.  And it ran the walk whole before the ISR.  The census (tools/straddle.py) had 11 straddles whose OR read screen
bytes the ISR had drawn its sprites on after the point.  One more had its ISR seed slot 0 before the walk read it, so the walk
took another path.  And 5 had an ISR that, run late, read screen bytes the walk wrote after the point.

**Measured** (new tool `tools/sparkacc.py` -> `build/sparkacc_fixture.json`, ~45 s on 20 workers, `verify` MATCH):
- The real load (passacc's drive and keys, potion.py's P / O walk after them), with the table LAID (declared) at the end of
  every 4th ISR from 600 to frame 1300: six particles, three on P1's cells (the odd ISR draws him over them) and three
  fixed, at six phases.  Free-running, it records every pass from 598 [frame, phase, plain length, program], every ISR
  [label, T, acceptance phase, the masked bitmap and the attributes at its end], and every LD A,R.
- 48 saved states, 600 frames of random keys with SPACE (natural pops, natural sparkles): 194,440 calls, 2,321 live (3,990
  draws, 1,561 erases; 227 with C = 0 at the entry -- the LDI's borrow, thirteen slots).
- 236 replays (the first call of each distinct program and grid, plain from its entry: C, seed, program, grid, T, the final
  byte at every address written).
- 6 forced runs (every path in one walk, the borrow, rows the `$FD00` table aims at the ROM, the screen's edges, fourteen
  drawing, fourteen freeing); three of them keep the machine's instruction list.
- 76 PHASED runs.  The walk's entry is moved into the bottom border so the point lands AT and 1 T into 18 targets -- the
  slots' reads, the LDI, the Y read, the write-backs, the blit's OR reads and stores, the restore's stores -- in three
  scenes:
  - 'over': P1 on three particles, the odd ISR next;
  - 'pop': a HELD bubble on them, the even ISR next.  It pops the bubble: its erase lands on their bytes, and its seed goes
    into the first free slot, which the third particle's write-back frees;
  - 'pop0': every slot free, so the seed goes into slot 0.
- The kids' own operands (`$A304`, `$A33D`, `$A349`, `$A355`: rewritten before every read) are left out of the write
  digests, as in the earlier gates' OPS.
- `tools/straddle.py`: GATE += `$C002`, LATE_KEEP too.  Its 12 class rows, its 5 late rows and every 40th of the rest make 83
  rows, each with C at the entry (`X.c`); `fin` leaves the four operands out.

**Engine (web/game.js):** BB_GRID gains the live slot's keys in the machine's order:
- `SC.LIVE` (`$C00B..$C02F`); `SC.ERASE_Z` / `SC.ERASE_E` and `SC.ERASE_TAIL` (PUSH / PUSH / CALL, with POP / POP / JR at
  its RET); `SC.DRAW` (to the CALL, EXX at its RET; `SC.DRAW_C` for the dead `$CAA0` arm); `SC.WB`;
- `SC.BL_ROW` / `_LAST`, the OR rows.  The item's `IT.BL_HEAD` / `BAND` / `END`, `IT.DIV` and `IT.RS_*` are reused.

BB_SC holds the sites' places: `LDI_AT` 47, `Y_AT` 69, `WB_AT` 17, `OR_RD0` 7, `OR_ST0` 14, `OR_RD1` 38, `OR_ST1` 45; the
restore's `RS_ST0` / `RS_ST1` are the item's.  In a pass (`sc`), sparkleFrame runs a site (isrSite):
- before each slot's `$C00B` read (a pop's seed fills the first free slot);
- before a live slot's LDI and `$C019` reads (the seed overwrites slot 13 when none is free);
- before its write-back (the seed's search reads the slot it frees).

Its kids run in sparkle mode (`scK`, which sets `scBl` / `scRs`): their keys, their screen accesses at the cursor, and a site
before each OR read, each OR store and each restore store.  The OR row's read and store are split around those sites, so an
ISR between them is overwritten, as on the machine.  A row the `$FD00` table aims at the ROM gets no access and no site.

Outside a pass nothing changes.  The item's blit and restore are unchanged (their band modes are separate).  The other
callers -- `$915F`'s Boris, the projectiles, the bolt -- are as before: off the program (DECLARED).  `BB_Game.SC` is exported;
the dead `paMark` is gone.

**Gates (bb.test.js, the last block "M7.115k SK"):**
- **SK1** the fixture, and the live slot's 24 grid keys against costc002's instruction lists, T for T, CALL for CALL.
- **SK2** 242 / 242 replays and forced runs exact (program, grid, T, writes; with the machine's C).
- **SK3** the spark world free-running, the engine laying the table as its ISR returns (inside a callee or at the frame's
  end; TRAPS #327):
  - 2,524 passes from 598 to frame 971 at the machine's frame, phase and program; past it every pass found at its frame and
    phase has the machine's program, and 51 are not found (frames 971..980);
  - every ISR's T is the machine's but seven, and the masked bitmap and the attributes at all 703 ISR ends are the
    machine's;
  - 83 ISRs are taken inside a live walk, exactly the machine's that fall at or before the walk's last site;
  - PINNED (MEASURED on the machine, TRAPS #329): ISR 804 is 5 T short -- a bubble the even ISR pops, and the pop's accesses
    (its erase's 80, its seed's 3) are not on the ISR's program; the seed's store waits 5 T in the screen fetch.  ISR 971
    is 10 T short -- the lives panel (`$80A8`'s masked rows) drawn inside the odd ISR, 54 accesses not on it; 972..980
    follow.
- **SK4** the 76 phased runs exact: the ISR nested once, at the machine's acceptance phase, after the machine's count of the
  stores it can see (TRAPS #328); what it reads, the grid, program, T and final bytes the machine's.  The old rule is wrong on
  50 (33 reads, 50 bytes, 34 paths).
- **SK5** the 83 census rows exact; the old rule is wrong on all 12 class and all 5 late rows.
- **SK6** the boundary: outside a pass; a lost cursor; the item's blit and restore after the sparkle's; Boris's `$9250`.
- **SK7** each site at its instruction's first T and one T later, the places from the machine's instruction list: 297 stores
  of 5 kinds both ways, and six reads with the ISR writing what they read.

IA3 is re-pinned: the fruit world is exact past its first sparkle (806) to 970 -- 2,287 passes, where it was 1,065.  The pin
is now Boris's erase: `$915F`'s `$A314` after ISR 971 cut the pass, its 32 screen stores not on the pass's program.  Suites
bb 1,889 / kit 120 / selftest 34.

**Still DECLARED:**
- the pop's accesses in the even ISR (its erase's, its seed's: SK3's ISR 804) and the lives panel's inside the odd ISR (ISR
  971) -- off the ISR's access program;
- Boris's erase off the pass's program (IA3's fruit pin);
- the projectiles' and the bolt's blits;
- the walk's C taken from (`$FECA`) (M7.90);
- the dead `$CAA0` arm;
- the odd ISR's dummy-page probe (r10, EA3b).

### M7.115l: Boris's erase on the pass's program, and its DI window on the frame clock

**Found** (M7.115k's pin, IA3's fruit world: frame 970's pass, the machine's 423 accesses, the engine's 391): `$915F`
(`$8D34`, the sixth chain entry) reads its request -- the operand of its own `LD A,n` at `$9160`, which the respawn (inside
the odd ISR) and the round's clear (`$8ECF`) set to 1.  With it up, `$9163 DI` clears the request, `$9257`, `$904D` and the
hurry timer `$8DBD`, and `$9173 LD IY,$9250 / CALL $A314` restores the pixels under Boris's record: sixteen rows of two
stores into the screen from the shadow, then `$917A EI / $917B RET`.
- The 32 stores (`$A360` / `$A364`, 4 T into each) were not on the pass's program.
- The engine logged the request path as one BB_SM key whose CALL defers its EI, and none of the restore's keys after it, so
  the region was a MISS.
- The whole erase runs with interrupts OFF, and the engine had no window there.  It ran an interrupt that fell inside at
  the next callee's entry, every time.

**Measured** (new tool `tools/borisacc.py` -> `build/borisacc_fixture.json`, ~40 s on 20 workers, `verify` MATCH):
- 48 saved states, 600 frames of random keys each: 186,576 calls, 23 with the request up (none with an ISR inside, none
  losing one -- the window is ~1,700 T of a 69,888-T frame, met once per respawn).  Each replayed plain from its entry: the
  seed (`$9160`, read as an operand, among it), the program, the grid, T, the final bytes.
- 15 forced runs from the death world's first request: every Y & 7 (the third band), the screen's left and right edges,
  rows the `$FD00` table aims at the ROM (their stores dropped: 4 runs with fewer than 32), the bottom; three keep the
  machine's instruction list.
- 84 PHASED runs.  The call's entry is moved into the bottom border so the point lands AT and 1 T into each instruction
  to the restore's last row, the EI and the RET, and 33 / 32 / 31 / 30 / 1 T before the RET's end, in three scenes:
  'odd' (Boris's cells under P1, the odd ISR next: it draws him there), 'odd3' (the same with Y & 7 = 3: the window ends
  later), 'even' (the even ISR next).  The entry AT itself is left out: a run begun at the entry samples the line first at
  its first instruction's end (TRAPS #330).
- What the machine does:
  - the point at or before the DI's first T (18 runs) -- the ISR is taken there, after the instruction in progress, before
    the stores.  It INCs the hurry timer the call then clears, so the next ISR's parity is not the old rule's;
  - from 1 T into the DI to 32 T before the RET's end (45 runs) -- the interrupt is LOST;
  - 31..1 T before the RET's end (21 runs) -- the pulse outlasts the window and the RET's end takes it, at the acceptance
    phase "the end less the point" (1 .. 31), whatever instruction was in progress at the point.

**Engine (web/game.js):** `BB_BORIS` = { REC `$9250`, DI 5 } (the DI 5 T into 'SM.9162f', after the RET nz).  In a pass,
`hurryReset`:
- logs 'SM.9162f' to its CALL (the EI deferred), then runs a site at the DI (`isrSite`: the ISR the point falls before it
  runs there, before the stores);
- raises `bkK` around `$A314`: the restore runs in Boris's mode (`bk` / `bkRs`), its keys on the grid at the cursor (the
  sparkle's `IT.RS_*`, M7.115k) and each row's two screen stores on the program -- and no site, since interrupts are off;
- after `$917B`'s key pushes the window [the DI's place + 1 (BB_EXT_W.DI_OPEN), the RET's end] onto the frame clock
  (`diWindows`, as the award's): a pulse wholly inside it is LOST (`intLost`, step()'s frame end; `isrHere` refuses it).
  A cursor lost cannot place it: COUNTED (`bkWinMiss`).  Outside step() (no frame clock) nothing is pushed.

`gridPh` gains the window rule: a point inside a DI window whose pulse outlasts it is taken at the window's end (the
acceptance phase `w[1] - b`), for every window -- the award's (M7.115f) too.  In the spark world it never fires.
`BB_Game.BORIS` is exported.

**Gates (bb.test.js, the last block "M7.115l BK"):**
- **BK1** the fixture: 48 worlds, 186,576 calls, 23 requests, 23 replays (all with the natural call's program and grid), 15
  forced, 84 phased (18 before the DI, 45 LOST, 21 at the RET's end); the DI 16 T from the entry = BB_SM's '915F' + DI.
- **BK2** 38 / 38 replays and forced runs exact: program (1,140 accesses), grid, T, final bytes.
- **BK3** the 84 phased runs exact: the ISR at the DI's site (once, at the machine's acceptance phase, after none of the
  stores it can see), LOST (a window over the point, no ISR), or after the call at the window's end (phases 1 .. 31); what
  the ISR reads of the call's bytes, the grid, program, T, every byte.  The old rule (no site, no window) takes the 45 the
  machine loses and reads the cleared timer on all 18 before the DI.
- **BK4** the boundary: outside a pass the erase is made and nothing pushed, its site refused; in a pass outside step()
  no window and no ISR, Boris's modes down after it; a lost cursor places no window (counted) and no store; the request
  down: '9162t' alone.
- **BK5** the window's edges and the site from the machine's instruction list (Y & 7 = 0, 5, the ROM's rows): [the DI + 1,
  the RET's end]; the point AT the DI takes the ISR at the site, 1 T later and 32 T before the end it is LOST, 31 T before
  not.
- **BK6** through `step()`, on a real game (round 1 in play): the request raised in the first pass whose DI lands 200 ..
  1,200 T before the point -- that frame has no ISR (`extLost` +1, the branch 'lost', the timer the call cleared not
  INCed), the next frame's ISR runs (odd, the timer INCed from 0), no other frame in 40 loses one.

**Re-pinned:**
- **IA3**: the fruit world is exact through Boris's erase (970's pass: 423 accesses, the machine's) to frame 1128 -- 3,343
  passes, where it was 2,287.  The new pin is the R stand-in: ISR 1128's walker `$B0D5 LD A,R` (CP `$2A`, the 1/128
  hesitation) draws the stand-in's first `$2A` of 37 in the window; the machine's R there is 39.  The ISR's 613 accesses
  and their waits are the machine's, its T 452 short (33,761 / 34,213).  MEASURED (scratchpad/m7115l): with the machine's
  draws fed, the engine's ISR 1128 is 34,213 T (TRAPS #332).
- **IA5**: the fruit window now holds its take at 980 too -- four takes, all 40 edges exact.
- **SK3**: ISRs 972 .. 976 (past ISR 971's 10-T gap, the lives panel) moved: the respawn in ISR 971 raises Boris's request,
  and his erase, now on the program, waits in one of those shifted passes.  The window rule's hits in that world: 0
  (TRAPS #334).
- **SK6**: its Boris clause is a call with `bkK` down (only `hurryReset` raises it).

Suites bb 1,895 / kit 120 / selftest 34.

**Still DECLARED:**
- the pop's accesses in the even ISR (SK3's ISR 804) and the lives panel's inside the odd ISR (ISR 971) -- off the ISR's
  access program;
- the R register's stand-in (BB_Rng): the potion worlds' `$8A38` (IA3, 1448) and now the fruit world's `$B0D5` (1128);
- the projectiles' and the bolt's blits;
- the walk's C taken from (`$FECA`) (M7.90);
- the dead `$CAA0` arm;
- the odd ISR's dummy-page probe (r10, EA3b).

### M7.115m: the even ISR's last accesses on its program -- the pop, the escape's and the push's erases, the steal, the bonus

**Found** (M7.115k's pin, SK3's ISR 804: the machine's 253 accesses, the engine's 170, its T 5 short): M7.114c put each ISR's
own contention on its access program, but the even ISR's bubble manager `$B62C` makes more contended accesses than it
carried there.  A census of 48 saved states (600 frames of random keys each) found, inside the even ISR:
- the POP `$B6D8` -- 167 from the held arm (`$B6C3`), 26 from the age's `CALL m` (`$B669`), none from the blow's steal
  (`$BDBC`).  Each makes:
  - its erase: `$B6E3 CALL $BF0A` -> `$BF16` -> `$A447`'s shifted erase, 80 screen accesses at a Y the ROM's rows do not cut;
  - its seed of the sparkle table at `$5CE0`: `$B701`'s read of each slot it walks, `$B713` / `$B718`'s stores, `$B723`'s
    cancel;
  - for a paid pop (74), the award `$B797 CALL $80FA` -- each drawn digit's eight glyph stores into the HUD (`$8052`) --
    between the two OUT (`$FE`)s at `$B791` / `$B79E` (the ULA's I/O cycle);
  - for a class-1 pop, the corpse birth `$8BC2` -> `$8C51` -> `$A447` on the enemy: an erase on its live arm, none on its
    `$A437` arms (all 8 natural births);
- the ESCAPE's erase (`$B6B9 CALL $BF0A`: a holding bubble whose age wraps, 4) and the PUSH's (`$B952 CALL $BF0A`, inside
  the rise `$B836`: a player pressing into a risen bubble, 105);
- the blow's BONUS award (`$BD6B CALL $80FA`: the player whose last power-up was type 15, paid on every blow) -- none
  natural.
None of these accesses was on the ISR's program.  In ISR 804 the erase falls in the top border; the seed's `$B713` store
is the ISR's only wait (5 T).

**Measured** (new tool `tools/popacc.py` -> `build/popacc_fixture.json`, ~40 s on 20 workers, `verify` MATCH):
- 48 saved states, 600 frames of random keys with SPACE: 13,296 even ISRs' `$B62C` (its entry 340 T after the acceptance on
  every one, its RET to `$8D8F`).  The 279 that pop, erase an escape or a push, steal or pay a bonus are kept with their
  program (plain offsets from `$B62C`'s entry), their marks, the ISR's acceptance phase and `$B62C`'s waits.  Those waits
  are the even ISR's whole contention: nothing before or after `$B62C` touches contended memory.
- Each replayed plain from its entry, recording:
  - the seed: every byte read before written, with the self-modified operands it fetches first among it (`$B62D`, `$B657`,
    `$A431`, the corpse birth's generator operand `$FE86` / `$FE87`);
  - its LD A,R draws, the program, T and the writes;
  - the glyph rows' addresses, and the chain walk's ROM reads with the marks it makes from them.
  ASSERTED: every instruction byte a run fetches before writing, that any run writes, is in SMC.  Every code byte a run
  rewrites before it runs is in OPS (the blitters' own operands, not state) or SMC (state the engine models).
- 54 FORCED calls on round1_48 / round1_2p48, each reaching its proof marks.  They were built on the even ISR's real stack
  (`$96C1`), not the saved state's SP (TRAPS #335).  They cover:
  - the pop at every Y & 7, the ROM's rows, the cancel's four edges, and a Y the erase skips;
  - the seed's busy walk and the full table (slot 13);
  - every class, and the corpse birth's arms (frozen, dead, live aligned, live shifted, live unvisited);
  - the digits drawn (0..8), the HIGH copy, the award's guard, the mailbox busy, and player 2;
  - a chain of two pops in one pass, the age pop, the escape, and the push both ways and player 2's;
  - the steal (unpaid, paid), and the bonus for both players;
  - two events in one pass, each clock carrying the first's callee T (TRAPS #339): a push then the age pop, a push then
    the escape, two pushes of one bubble (player 2's tests read the registers player 1's push left), both players'
    bonuses, a bonus then the steal.

**Engine (web/game.js):** `BB_ISR_PO` holds each entry on its caller's clock (the Zilog sums; EV3 holds every one against the
machine's marks):
- the held arm's pop is 87 T into its slot; the age's arms count from `$B656`, the draw's return: the escape 73 T, the pop
  108 T;
- the escape's `$BF0A` is 351 T past its entry, plus its `$B6C8`'s body;
- the pop's `$BF0A` is 144 T in.  Its seed's reads and stores are placed from the walk's start and from `$B70C` (`Y_ST`
  37 / 69, `CANCEL` 105 / 114);
- the pop's `$B790` is its charge less the TAIL charged ahead.  The OUTs come 4 T and award + 21 T past it, the award 54 T;
- a class-1 birth is 185 T past `$B75C`, its `$A447` 79 T past the birth;
- the push's `$BF0A` is 43 T past its JR z, less what the contact charges ahead of the player's `$B901` (49 T for player 1,
  10 T for player 2);
- the blow's clock is `$BD2C`'s entry (44 T into `$B62C`) plus its T so far.  During player 1's walk it is less player 2's
  LD IX (14 T).  The steal's pop and the bonus's award are 14 T (the POP IX) before it.

Who sets the clocks:
- bubbleManagerPass sets `blAt` (the blow), `poAt` (the held arm), `riAt` (the rise: the push) and `agAt` (`$B656`: the
  age's arms);
- bubbleAge sets `esAt` / `poAt`; playerBlow sets `poAt` for the steal (`blowClock`).

What each piece puts on the program:
- bubblePop gives its erase `bfAt` (the template, class 1, as the travel's).  sparkSeed pushes its reads and stores (class
  5, `BB_ISR_PO_C`);
- bubbleAwardFork puts the birth's `ehAt` and the first OUT (ipPort, A = 0).  It runs the award through `awardIsr` (its
  glyph stores from awClk's cp, M7.100's clock, class 5), then the second OUT (A = `$30`);
- the bonus's award is `awardIsr` too.
Outside an ISR (no program) every clock is null and nothing changes.  `BB_Game.ISR_PO`, `ISR_PO_C` and `AB38` are exported.

**Gates (bb.test.js, the last block "M7.115m EV"):**
- **EV1** the fixture: 48 worlds, 13,296 calls, 279 kept, every replay the natural call's program; 54 forced (3 steals, 5
  bonus awards, five with two events in one pass); `$B62C` at 340 T on all 279.  The 279 hold:
  - 167 held pops and 26 age pops -- 74 paid, 153 chain marks, 8 corpse births, 11 cancels;
  - 105 pushes and 4 escapes.
  3 replays' chain window lies in the ROM and marks from its bytes: DECLARED.
- **EV2** 330 / 330 calls exact through a fresh engine's bubbleManagerPass (100,374 accesses).  Each matches the machine on:
  - the program, in time order, and T;
  - the final byte at every address written (the blitters' own operands and the digits' pixels left out: the port draws
    its own);
  - the glyph rows' addresses, every R draw consumed, and the chain's marks and ROM reads.
  The old rule differs on all 330.
- **EV3** every entry on the clock -- 230 pops, 349 `$BF0A`s, 91 awards, 11 corpse births -- at the machine's offset from
  `$B62C`'s entry, in order.
- **EV4** each of the 276 natural calls' program, replayed from its ISR's acceptance phase, waits the machine's D (199
  non-zero, up to 1,207 T); the old rule's program waits otherwise on 129.
- **EV5** the boundary: outside an ISR the paid steal's pass runs to the same RAM and builds nothing; the award with no
  clock pushes nothing; no clock is left set after the pass; the class is its own; the ROM window's reads are counted and
  no mark is made from them.

**Re-pinned:**
- **SK3**: ISR 804 is the machine's -- its pin is gone; ISR 971 (the lives panel) and 972..980 remain.
- **PK7**: the pop rows' median gap moves from 49 to -40 T.  Their contention is replayed from BB_ISR_ACCEPT, not the
  machine's phase, which popkill's rows do not carry -- the declared gap the row names.

Suites bb 1,900 / kit 120 / selftest 34.

**Still DECLARED:**
- the lives panel inside the odd ISR (ISR 971) -- off the ISR's access program;
- the corpse flight's erase and draw (`$8A78`'s `$BF0A` and `$A26F`, inside the odd ISR: 1,205 natural `$BF0A`s in this
  census) and the boss's draws in an ISR -- off its program (M7.114c's list);
- the chain walk's window parked in the ROM (`$02xx`): its marks from the ROM's bytes (chainRomReads; 3 natural calls);
- the R register's stand-in (BB_Rng): the potion worlds' `$8A38` (IA3, 1448), the fruit world's `$B0D5` (1128);
- the projectiles' and the bolt's blits; the walk's C taken from (`$FECA`) (M7.90); the dead `$CAA0` arm;
- the odd ISR's dummy-page probe (r10, EA3b).
