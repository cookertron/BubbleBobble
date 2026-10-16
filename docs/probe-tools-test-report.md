# `stackscan.py`, `chaincost.py`, `dataread.py` across four games

Date: 2026-09-06.  Port repo: `E:\Software\bubble_bobble` (commit `b78e42f` before; one commit after).
Kit: `E:\Software\Spectrum-Port-Kit` at `9c63daf`, unchanged by this work.  Environment: Windows 11,
Python 3.12, SkoolKit 10.0 (the Python `CMIOSimulator`, which the probes need for their memory hooks),
z80dis.  The tapes, snapshots and saved states are the owner's own, used locally for interoperability
study; nothing tape-derived was committed (the port's `.gitignore` already excludes it) and the new
states live in the session scratch folder, not in either repository.

## 0. Verdict in one paragraph

`dataread` and `chaincost` generalise and their gates discriminate; both needed one semantic fix
each, found on other games (a buffer is read at player-relative cells, so an exact-address gate
cannot pass on the manual's own case study; a loop whose first CALL is conditional produced no
verdict at all).  `stackscan` as tested did **not** generalise: its "reconciliation" is an identity
that cannot fail, it did not track interrupts (one bogus "unknown return" per frame on every game),
and it was blind to the two death idioms the other games use, `LD SP,nn / JP` (Chuckie Egg 2) and a
`POP` that a later RET never lands behind.  It was rewritten around stack slots, the design Chuckie
Egg 2's own scanner used, and now names Chuckie Egg 2's death as exactly the two frames its notes
record, Chuckie Egg's death as the documented `LD B,6 / POP HL` loop, and Bubble Bobble's round 1
as 0 discards with the blitter's `LD SP,HL` recognised as a stack switch rather than a cut.  The
port's `selftest` went 32 → 33 with a synthetic check whose every stack event is known; 6/6
mutations of the scanner fail that check.  All three probes were then upstreamed: the kit's
`harness.py`, `portconfig.py`, `keyprobe.py` and `boot.py` were byte-identical to the port's, so the
kit port was four copied files plus the selftest check (kit selftest 32 -> 33, mutation battery 6/6
on the kit copy); the kit's `Harness(snapshot=False)` bug (section 5, item 10) was fixed in the same
commit and the fix synced back here.

## 1. Live states reached, and how

| Game | Source | How live play was reached | State |
|---|---|---|---|
| Bubble Bobble (BB) | `build/round1.pkl` (existing) | documented in `docs/NOTES.md` | settled round 1 |
| Chuckie Egg (CE, A&F 1984) — the manual's case study | `E:\Software\Chuckie\Chuckie Egg.tzx` | `simload.py` end-of-tape stopped at `$5FB8` inside the BASIC-block loader (`CALL LD-BYTES` for the 18,900-byte block to `$8214`, then `JP $A410`); harness-stepped 4 instructions to the JP; `simload.py --start 0xA410`; title code read: `$A4AB` `IN A,($FDFE) / BIT 1` = **S** starts, `$A5D3` `IN A,($F7FE) / AND 15` = **1-4** players; `boot.py --script "700:,30:S,150:,30:1,500:"` → LEVEL 01 (screen rendered and checked); keyprobe in play: **Z/M** left/right, **0** jump, **9** up | `ce_play2`, `ce_walked` |
| Chuckie Egg 2 (CE2, A&F 1985) — an extra target with documented ground truth in `E:\Software\Chuckie2\notes` | `Chuckie2/recon/image/ce2_realstart.z80` (`$60C2`, the loader's postcondition) | that repo's own recipe: SPACE → menu `$9BDC` → P → main loop `$786A`; IM 2, I=`$FE`, room 1, lives 5; keyprobe: **O/P** left/right, **SYM** jump, **0** ABORT, **S** SAVE; holding P falls into room 11 and dies at frame 611 (lives 5 → 4) | `ce2_play3` |
| 12 Firebird/Electric Dreams/Ariolasoft Bleepload titles | the hand-over `.z80`s from the Bleepload validation | `--arm --warm 300` only (title/attract; no menu driving attempted) | robustness only |

## 2. Results per tool and game

### 2.1 `stackscan`

| Game / state | Tool as tested (`b78e42f`) | Rewritten tool | Corroborated from the code |
|---|---|---|---|
| BB `round1`, 120 frames idle | 44,131 pushes, 44,130 balanced, **0 imbalances**, 1,857 "unknown returns" at 17 sites incl. `$8DA1` ×115 (the IM 2 ISR's RET), reconciliation OK | 44,262 frames (CALL/RST/**interrupt**), 44,261 balanced, **0 discards**, 1,731 fake returns at 9 game sites (`$93E8` ×1045, `$AAEA` ×240, `$AF46` ×180 …), ODD 0 | `$93DC LD HL,$93F4 / PUSH HL / … / $93E8 RET Z` and `$AAE5 PUSH HL / BIT 2,(IY+7) / RET Z / JP (HL)`: RET-as-jump dispatch.  The blitter `$A489 EXX / LD SP,HL / EXX` parks SP in sprite data and later restores it: a **switch**, not a cut — a first slot-based version counted it as 457 discards at 80 sites |
| CE `ce_walked` + 400 frames of Z (walks into a hen) | not run with the old tool on this event; on a forced timeout death the old tool reported 145 "imbalances" at 4 **ROM** sites (`$2DC0`, `$2D3A`, `$03F7`, `$AB66` "discarded 24") and 3,835 unknowns — calculator noise and stale entries; the game idiom did not fire on a timeout | 39,171 frames, **2 discards at `$92BE POP HL`** (victims `$929C→$91B8`, `$911E→$9949`), 260 rewritten at ROM `$369F`, 1,560 fake returns at 16 ROM sites, 2 at game sites, ODD 0 | `$92BC LD B,6 / $92BE POP HL / DJNZ / $92C1 RET` — the manual's C1 "dying draw routine" (`LD B,6 / POP HL six times / RET`); a PC watch shows `$92BC` executing exactly once during the run.  Six POPs, two frames: the other four words were the callers' own data pushes |
| CE2 `ce2_play3` + 620 frames of P (fall death in room 11) | 37,329 pushes, **6 imbalances** at `$A15B`/`$A37F`/`$79E4` (routine `$7E51`), **0 at `$8A84`**, unknown `$7F00` ×495 (ISR RET), reconciliation OK, "open at end 2" — the death was invisible | 37,824 frames, 20 discards at 7 sites: **`$8A84 LD SP,$FFF0` ×2** (victims `$937D→$9372`, `$936B→$78A5`), `$7E54 POP HL` ×2 for each of three callers, `$7EBD`/`$7ECC INC SP` ×6; fake returns `$7ECB`/`$7ED8`/`$7E64` ×6; ODD 0 | `$8A7D DEC (HL) / JP Z,$8A8A / CALL $7913 / $8A84 LD SP,$FFF0 / JP $77B9`.  The CE2 notes (`p6e-q19-stack-imbalance.md`) record this death as "55/55 deaths, 2 frames abandoned per death", the victims as `CALL $936F→$937D` and `CALL $78A2→$936B`, the `$7E54 POP HL` inline-parameter idiom and the `INC SP ×2 … DEC SP ×2` fetch — every line matches.  A PC watch shows `$8583` (fall damage) → `$8A29` → `$8A84` once |
| Hybrid end-of-tape snapshot, `--arm`, no warm (negative test: PC inside the Bleepload stage-2 loader) | 531 pushes, 4 imbalances, 9 unknowns | 490 frames, 4 discards at `$FBD1 POP HL` (the "Loading" text helper's inline-parameter idiom), 4 fake returns at `$FBDC`, ODD 0 | the loader's `CALL $FBD1` / text / `$FBDC RET` — small and correct, not falsely rich.  First version labelled `$FBD1` "JR" because the tail area is rewritten per block; names are now captured when the event happens |
| 12 Bleepload hand-over snapshots, `--arm --warm 300`, 120 frames | reconciliation OK on all (it always is); `$0052` ×85-120 "unknown" on five IM 1 titles (the ROM ISR's RET) | ODD 0 on all; 0 discards; frames from 29 (Intensity, idle) to 51,920 (Starfox attract); a single fake return ×1 at the start on most (a RET consuming a slot pushed before the scan began) | not corroborated beyond the ISR explanation: title screens waiting for a key — UNVALIDATED as gameplay measurements, as the prompt predicted |

### 2.2 `dataread`

| Game / state | Command | Result | Corroborated |
|---|---|---|---|
| BB `round1`, 30 frames, key 8 | documented args, `--verify 0x96D9` / `0x9600` | `$96D9` rank 1 PASS, exit 0; `$9600` FAIL, exit 1 (the gate discriminates) | **the `$96D1-$96DA` reads are `POP HL` (`$92FC`), `POP BC` (`$9302`), `EX (SP),HL / RET` (`$9F5A`/`$9F5B`) and `RET` (`$93C3`)** — the physics parks SP on the scratch block (manual 3.10).  NOTES.md calls them "five 16-bit scratch variables the physics copies per entity": right about the data, silent about the mechanism.  The tool now lists them as stack-class reads and the gate says so |
| CE `ce_play2`, 60 frames, key M (walking) | `--lo 0x5B00 --hi 0x8000 --verify 0x61A8` | **FAIL** (`$61A8` never read); top data `$72DC` ×10k, `$7325`, `$72A0-$72B1` (the entity table) | the level buffer **is** read: 1,945 reads at 38 addresses `$61D4-$61D6`, `$61F4-$61F6`, `$6214-$6216`, `$6234-$6236`, `$6372`, `$6392-$6393` — the cells around the player — by `$9555` (`CALL $9584 / CALL $95A6 / … / LD A,(HL)`), `$9E53` (`SRL C ×3 / ADD HL,BC / LD A,(HL)`: column = x>>3 into a row pointer), `$9ABE`, `$9386`/`$9391`, `$A356`.  Its first byte is the top-left cell, which nothing visits.  **The exact-address gate is the wrong shape for a buffer** |
| CE, same run | `--verify 0x61A8 0x6448` (range, new) / `0x6600 0x6900` | 2.17% of data reads, PASS / 0.00%, FAIL | as above |
| BB `round1` | `--verify 0x96D1 0x96DB` / `0x8000 0x8100` | 71.2% of stack-class reads, PASS (stack-class named) / FAIL | as above |
| CE2 `ce2_play3`, 150 frames, key P | `--verify 0x6000 0x6300` (tile plane) / `0x6300 0x6600` (property plane) / `0x4000 0x4100` | 1.49% PASS / **0.15% FAIL** (71 reads at 59 addresses) / FAIL | the property probe `$884B` (the CE2 notes' documented consumer) reads at cell transitions only; the tile plane is read every frame by `$93CB`/`$802D`.  Coverage is only as good as the play driven (manual Q13): an honest FAIL, not a tool fault |
| Starfox hand-over, `--arm --warm 300` (attract mode) | `--lo 0x5B00 --hi 0x10000` | as tested: top "data" `$FF76-$FF79` ×9,440 each; now: 44,840 stack-class reads listed apart, data top `$E7F5-$E7F8` ×1,180 by `$84A2` | `$8331 POP BC / $8332 RET` read the stack; `$849D LD B,8 / LD HL,$E7F8 / $84A2 LD A,(HL)` reads a real 8-byte table |
| BB raw hand-over snapshot `--arm`, no warm | documented window | 68.7% kept, `$6195-$619E` hot — the title screen running, not degenerate: `boot48.z80` is already at the game's entry | — |

The "kept" ratio self-check says nothing when the window holds no code (CE: 100% kept in
`$5B00-$8000` because the game runs above `$8000`); the tool now says so.

### 2.3 `chaincost`

| Game / state | Range | Result | Independent oracle |
|---|---|---|---|
| BB `round1`, 200 frames | `$8D25-$8D61` (documented) | 1,843 passes, 9.21/frame; sum of medians 5,800 T; measured period **5,959 T**; 97%; OK, exit 0 | `clock.py --pc 0x8D25`: modes 5,989 ×27, 5,957 ×9, 5,988 ×9, 5,980 ×8 T (0.086 frames) plus 7,511 and half-frame buckets (the alternate-frame ISR music) — agrees.  NOTES.md said ~8.7 passes/frame and ~5,972 T: same state, a different 200-frame window |
| BB raw hand-over (title), `--arm` | documented range | every site "never returned", 0 passes | correct: the chain is not running at the title |
| CE `ce_play2`, walking | `$9858-$98C0` (the real loop; the manual's example `$8503` is data in this build: `clock.py` "NO VISITS") | as tested: `$987B CALL $9CA4` never returned, `$9899 CALL $A21C` **14,285** calls in 120 frames (an inner loop), 0 passes, **no verdict line at all**; now: "only 0 passes through the first CALL site: not a running chain", exit 1 | `$985E JR NZ,$985E` is the frame wait the ISR breaks; the loop is a tight poll (`clock.py --pc 0x9863`: ~165 T between visits) with conditional and looped CALLs — not a linear chain, and the tool must say so |
| CE `ce_play2` | `$8400-$8480` (data) | "no CALL nn", exit 1 | — |
| CE2 `ce2_play3`, 300 frames idle | `$7871-$7895` (the first half-loop: 8 `CALL`s) | 100 passes (0.33/frame); period **209,664 T = 3.000 frames**; medians `$8EE8` 9,887, `$7F01` 6,028, `$8C0A` 511, `$9CC2` 94, `$90F0` 59, `$92E7` 45-60; sum 16,734 = 8%; OK | `clock.py --pc 0x786A`: 2.7 and 3.3 frames alternating (mean 3.000) — agrees.  `$8EE8` is the factory machine, `$8C0A` the sprite pass, `$90F0` the lift (none in room 1), `$92E7` sound: the CE2 README's slice map.  The "glue" figure is loose here: 92% is the `HALT` wait and the second half-loop outside the range |

## 3. The central question per tool

**`stackscan` (as tested): does not generalise.**  Three defects, each shown on a game other than
Bubble Bobble and then confirmed on Bubble Bobble itself:
1. The reconciliation `pushes == balanced + abandoned + imbalance-pops + open` is an identity.  Every
   removal path increments exactly one of the three counters and `open` is what remains, so it holds
   whatever the game does — including the Chuckie Egg 2 death it missed.  A check that cannot fail
   is not a check.
2. Accepted interrupts were never entered on the shadow stack (the test `pushed == pc` compares the
   pushed word with the PC *before* the instruction; the interrupt pushes the PC after it), so every
   ISR return was an "unknown": `$8DA1` ×115 on Bubble Bobble, `$7F00` ×495 on Chuckie Egg 2,
   `$0052` ×120 on the IM 1 Firebird titles.
3. Pairing by return address instead of by slot: a frame cut by `LD SP,nn` is never reported (the
   Chuckie Egg 2 death), a `POP` discard is reported only if a later RET happens to land on a deeper
   entry, and stale entries inflate later counts (Chuckie Egg timeout: "discarded 24").
The rewrite pairs by slot, treats interrupts as frames, names the killing instruction, holds
`LD SP` cuts pending until a new frame buries them (a reset) or SP comes back to them (a switch),
and reports fake returns and rewrites.  Its falsifiable check is ODD == 0 (an SP rise by an
instruction outside RET/POP/INC SP/LD SP); no Z80 instruction can trip it, so it is a
model-integrity canary, and the mutation battery exercises the behaviours instead.  Verified on
three games with documented idioms; the twelve Bleepload attract states ran clean (ODD 0) but are
not gameplay.

**`dataread`: generalises, with the gate reshaped.**  The read filter is sound on all four games.
The exact-address `--verify` is right for a scalar or a fixed slot (Bubble Bobble) and wrong for a
buffer (the manual's own `$61A8`, Chuckie Egg 2's planes): a `--verify LO HI` range form with a
share threshold was added and passes the gold target at 2.17% while failing cold ranges.  Two
classes of read are now told apart: data-class (LD, CP, ADD … from memory) and stack-class (the two
bytes at SP, read by POP/RET/EX (SP)); the latter is the call stack on Starfox and SP parked on data
on Bubble Bobble, so the gate accepts either and names the class.

**`chaincost`: generalises to what it models — a linear chain of `CALL nn` at one nesting level.**
Its period agrees with `clock.py` on both games where the range is a chain (Bubble Bobble 5,959 T,
Chuckie Egg 2 209,664 T).  Chuckie Egg's loop is not a chain (conditional first CALL, an inner loop
of 14,285 calls) and the tool as tested printed a table and no verdict; it now says so and exits 1.
Limits: conditional CALLs are not bracketed (by design), a CALL inside an inner loop overwrites its
own bracket, and "glue" is only meaningful when the range covers the whole pass.

## 4. Every self-check mismatch or gate failure, explained

- `stackscan` reconciliation: **never mismatched** on any game — because it cannot (section 3).
- `dataread --verify 0x61A8` on Chuckie Egg: **FAIL** on the gold target — the buffer is read at
  38 player-relative cells, never at its first byte (section 2.2); fixed by the range form.
- `dataread --verify 0x6300 0x6600` on Chuckie Egg 2 walking right: **FAIL** at 0.15% — the
  property probe fires at cell transitions; a coverage result, kept as is.
- `dataread --verify 0x745C` on Bubble Bobble: PASS with `--top 25` (rank 25), FAIL with
  `--top 10` — the gate depended on `--top`; it now prints the rank so the reader sees why.
- `chaincost` on Chuckie Egg `$9858-$98C0`: 0 passes and no verdict (as tested) — a conditional
  first CALL; now an explicit verdict and exit 1.
- The 128K/raw-snapshot negative tests: Bubble Bobble's `boot48.z80` is not a "raw loader"
  snapshot (it is at the entry, the title runs: 27,712 pushes in 100 frames); the true negative is
  a Bleepload end-of-tape snapshot with the PC inside stage 2 (490 frames, a correct small census).

## 5. Bugs found (with repro)

1. `stackscan`: interrupts untracked → one "unknown return" per frame on every game.  Repro: `python
   tools/stackscan.py --state round1` (old) shows `$8DA1 x115`.  Fixed (frames for accepted interrupts,
   detected after a RET or POP too).
2. `stackscan`: `LD SP,nn` discards invisible.  Repro: `--state ce2_play3 --script "620:P"` (old):
   0 imbalances at `$8A84`.  Fixed: `$8A84 LD SP,0xfff0` ×2 victims.
3. `stackscan`: reconciliation tautological (section 3).  Replaced.
4. `stackscan` (first rewrite): `LD SP,HL` blitter switch counted as 457 discards on Bubble Bobble.
   Fixed with pending frames; a second slip excluded the restoring `LD SP` from revival — caught by the
   Bubble Bobble regression before commit.
5. `stackscan` (first rewrite): instruction names decoded at report time mislabelled a self-modified
   loader byte (`$FBD1` "JR"); now captured at event time.
6. `dataread --verify ADDR` cannot pass on a buffer (section 4); range form added.
7. `dataread`: stack reads ranked as data (Starfox `$FF76-$FF79`).  Filter added; the first version
   used `[SP, SP+2)` and caught nothing because this simulator increments SP before the POP/RET read —
   measured (SP = `$FF78` while reading `$FF76`) and widened to `[SP-2, SP+2)`.
8. `dataread`: the kept-ratio self-check is meaningless when the window holds no code (Chuckie Egg
   100%); a note is printed.
9. `chaincost`: no verdict when the first CALL site never runs (Chuckie Egg); now explicit, exit 1;
   sites that never returned are named in the verdict.
10. Kit `harness.py`: `Harness(snapshot=False)` raises `AttributeError` in `Snapshot.get` although
    the docstring promises "False -> blank RAM"; use `image=False`.  Not fixed here (kit file).
11. Documentation: the kit's tool examples name `$8503` as the case study's loop top and `boot.py
    --arm-at 0x8000`; in this Chuckie Egg build `$8503` is data and the loop is at `$9858`.

## 6. Recommendation per tool

| Tool | Recommendation | What a kit port needs |
|---|---|---|
| `stackscan.py` (rewritten) | **upstream** | copy; the kit's `harness.py`/`keyprobe.py`/`portconfig.py` are byte-identical to the port's; add the `t_stackscan` check (it uses only `Harness(image=False)` and `poke`) → kit selftest 32 → 33; a README row |
| `dataread.py` | **upstream** as is | copy; a README row.  Note in its row that `--verify LO HI` is the buffer form |
| `chaincost.py` | **upstream** as is | copy; a README row.  State the model: a linear chain of `CALL nn`; it exits 1 otherwise |
| `probeutil.py` | **upstream** (the three depend on it) | copy |

Port `selftest`: **32/32 before, 33/33 after** ("stackscan: slot-based frames, discards, fake return,
LD SP reset vs switch, ISR": a program with two balanced CALLs, a POP discard, a fake return, an `LD
SP` reset buried by a new frame, an `LD SP` switch restored by `LD SP,(nn)`, an `EX (SP),HL` rewrite,
then the ROM ISR under a HALT loop).  Mutation battery, each failing that check by name: interrupts
untracked, `LD SP` as a plain discard, pending frames never buried, fake returns uncounted, landing
address ignored, POP discards unattributed — **6/6**.  Kit `selftest` unchanged at 32/32.

## 7. What was NOT done

- No Bleepload title was driven past its title screen; their `--arm --warm` states are robustness
  runs only (ODD 0, no crash), not measurements.  Starfox's attract mode is genuinely live and its
  one hot data table was corroborated; the rest were not.
- Chuckie Egg's level-complete and item-eating idioms (the manual's other C1 examples) were not
  exercised: 1,150 frames of walking and jumping produced 0 discards and a score of 50; the death
  needed a hen.
- Chuckie Egg 2's lethal-tile route (`$869E POP HL / JP $8A29`) was not reached; the fall route was.
