# Task: rigorously validate three Z80 analysis probes across other games

You are Claude Fable 5.1 working on a ZX Spectrum reverse-engineering toolkit. Your job is to
find out whether three dynamic analysis tools generalise beyond the one game they were written
against, and to report the truth with evidence. Treat each tool as guilty until the evidence
acquits it. Do not tune a tool to make a game pass; when a tool and reality disagree, reality
(the disassembly, an independent measurement) wins until you prove otherwise.

## The tools under test (in `E:\Software\bubble_bobble\tools\`)

All three run against a LIVE, running Z80 state and share a boot layer, `probeutil.py`
(`--state NAME` a saved `.pkl`, or `--snapshot FILE` a `.z80`/`.szx`/`.sna` off `simload.py`;
plus `--arm` = set IFF=1, `--warm N` = run N frames armed, to reach running code). Read each
file and its `--help` first.

- **`stackscan.py`** — Q19 dynamic stack-imbalance scan. A shadow call stack classifies every
  RET as balanced, an IMBALANCE (a RET that discarded callers — the 8-bit "die / level
  complete / abandon update" idiom, manual family C1), or an unknown/computed return. It PRINTS
  a reconciliation `pushes == balanced + abandoned + imbalance-pops + open` and exits non-zero
  if it fails.
- **`chaincost.py`** — per-routine T-state cost of each CALL in a dispatch chain (`--range LO HI`),
  phase 9 / Q11. It prints the sum of per-routine medians against the MEASURED pass period and
  flags a `--range` that is not a clean chain.
- **`dataread.py`** — a read logger that filters out instruction fetches (address not in
  `[PC,PC+3]`), so a genuine data structure the code reads (a tile map, a table) stands out from
  code fetches. It prints a kept/total ratio and, with `--verify ADDR`, exits non-zero unless
  ADDR is among the hot data reads.

These are game-agnostic in mechanism but were exercised on ONE game (Bubble Bobble). The
**central question**: do they produce CORRECT, meaningful results on other games, and do the
built-in self-checks hold (and can you make them fail honestly)?

## The oracle for each (they have no single snapshot to diff, unlike a tape decoder)

| Tool | What proves it right, beyond "it ran" |
|---|---|
| `dataread` | A game with a **known data-structure address**. Run it on a live level with `--verify <that addr>` — it must PASS; `--verify <a wrong addr>` must FAIL. Cross-check: read the top reader PCs in the disassembly and confirm they are genuinely indexing that structure. |
| `stackscan` | A game with a **documented stack idiom** (a death / level-complete that POPs return addresses): script that event and confirm the imbalance appears at the right RET, then READ that routine to confirm it really unwinds. Plus: the reconciliation line must stay OK; try to find a state where it MISMATCHES (a decompressor using SP as a data pointer, self-modifying returns) — that is a real finding about the tool's limits. |
| `chaincost` | Independently measure the loop's pass period with `clock.py` (T between visits to the loop top); `chaincost`'s "measured pass period" must match it, and the per-routine medians must sum to just under it. Feed a deliberately BAD `--range` (overlapping or non-chain CALLs) and confirm it flags "sum EXCEEDS the pass". |

## The hard part, stated plainly

Unlike a tape decoder, these need a **live gameplay state per game**, which means driving each
game past its loader and menus. Budget for that. The path for a new tape:

1. `python tools/simload.py --tape "X.tzx" --out build/x.z80` (exploratory; stops at end of
   tape). Read the loader / trace for the hand-over `JP`, then re-run
   `simload.py --tape "X.tzx" --start <ENTRY> --out build/x.z80` for a clean hand-over snapshot.
2. `python tools/snapimport.py build/x.z80 --save x` → a `.pkl`, or point the probes at
   `--snapshot build/x.z80` directly.
3. Reach live play: `python tools/keyprobe.py --state x` to find menu keys, then
   `python tools/boot.py --state x --arm-at <ADDR> --script "60:...,60:..." --save x_play` to
   save a gameplay state (see how Bubble Bobble's states were made in `docs/NOTES.md`). For a
   quick robustness pass only, `--arm --warm 600` may reach an attract/demo without menus — but
   an end-of-tape snapshot often barely executes (measured: I,Ball, 65 stack pushes in 100
   frames), so a real measurement needs a driven state.

## Targets, in priority order

1. **Bubble Bobble itself — the known-answer regression.** States are already saved
   (`build/round1.pkl`, `play1p.pkl`, `play2p.pkl`). Reproduce these documented facts (in
   `docs/NOTES.md`) as a sanity gate before trusting the tools elsewhere:
   - `dataread --state round1 --lo 0x6000 --hi 0xFD00 --keys 8 --exclude 0xFD80 0xFDF8`: the hot
     data reads are `$96D1-$96DA` (per-entity scratch); there is NO tile-grid map. This is the
     negative control for `dataread` (a game where the answer is "no big buffer"). Confirm
     `--verify 0x96D9` PASSES and `--verify 0x9600` FAILS.
   - `chaincost --state round1 --range 0x8D25 0x8D61`: ~8.7 passes/frame, measured pass period
     ~5972 T, routines ~97% of the pass, self-check OK.
   - `stackscan --state round1`: reconciliation OK, 0 imbalances at idle (death not scripted).
2. **A game with DOCUMENTED ground truth — the gold target if you can obtain the tape.** The
   kit's own case study is Chuckie Egg (A&F, 1984): the field manual
   (`E:\Software\Spectrum-Port-Kit\docs\PORTING-ZX-TO-JS.txt`) states its **level buffer is at
   `$61A8`**, and documents stack-unwind idioms for death and level-complete, and per-path pass
   costs (grounded ~406 T, airborne ~560 T). If you have or can lawfully obtain that tape,
   `dataread --verify 0x61A8` on a live level is the definitive positive test for `dataread`,
   and its documented death routine is the definitive test for `stackscan`. If you cannot obtain
   it, say so and rely on targets 1 and 3.
3. **The seven Firebird Bleepload tapes** in `E:\Software\bleeploader-tapes\` (Hybrid, I Ball,
   Intensity, Ninja Scooter Simulator, Parabola, Samurai Warrior, The King's Keep) — for
   robustness and generality. You will not have documented ground truth for these, so for each:
   run the tools, confirm they do not crash and the self-checks hold, and VERIFY findings by
   reading the disassembly (e.g. confirm a `stackscan` imbalance is a real POP-unwind, confirm a
   `dataread` hot target is a real structure). A finding you cannot corroborate from the code is
   not a finding.

## Adversarial / negative tests

- `dataread --verify` a wrong address must exit non-zero; a right one exit zero. Confirm the gate
  discriminates rather than always passing.
- Give `chaincost` a `--range` over data or over a routine that is not a linear CALL chain; it
  should flag "sum EXCEEDS the pass" or report routines that "never returned", not a confident
  wrong table.
- Try to break `stackscan`'s reconciliation: a game with a heavy decompressor or a
  `JP (HL)`/`LD SP,table` dispatch. If reconciliation MISMATCHES, that is a correct signal of a
  stack idiom the tool does not model — document which, from the disassembly.
- Feed a probe a non-game state (a raw loader snapshot with `--arm`, no `--warm`) and confirm the
  output is obviously degenerate (a handful of pushes, near-empty data reads), not falsely rich.
- Confirm the port's own gate stays green after any change: `python tools/selftest.py` (32/32).

## If you change a tool

It is a git repo. You may fix bugs or add options, but:
- Keep the self-checks honest and keep `docstring` scope claims within the evidence — if you now
  trust a tool on N games, say which N and how you verified each.
- Do not commit tape-derived bytes (`.tzx/.z80/.szx/.sna/.pkl/.bin`, dumped blocks, screenshots
  of game frames): the `.gitignore` already excludes them; keep your snapshots in `build/`.
- Commit with a message that says what was measured, against which games, with the self-check
  numbers.
- These tools live in the PORT (`E:\Software\bubble_bobble\tools`), not the kit. A goal of this
  exercise is to decide whether they are ready to UPSTREAM to `E:\Software\Spectrum-Port-Kit`;
  if you conclude yes for any, note exactly what a kit port would need (they lean on this port's
  `harness.py`/`portconfig.py`, which the kit also has).

## Deliverable

Save `E:\Software\bubble_bobble\docs\probe-tools-test-report.md` with:
1. A per-tool, per-game results table: game → live-state reached (how) → the tool's key numbers →
   self-check OK/mismatch → whether the result was CORROBORATED from the disassembly.
2. The verdict on the central question per tool: does it generalise? What are its limits (states
   it needs, idioms it mismodels, games where it misleads)?
3. Every self-check MISMATCH or `--verify` FAIL, with the disassembly evidence explaining it.
4. Bugs found (crashes, false confidence, wrong parameter handling) with minimal repro.
5. Recommendation per tool: upstream to the kit as-is / after specific fixes / keep port-local,
   with reasons, and the `selftest` count before/after any change.

## Guardrails

- These are the owner's own tapes and states, used locally for interoperability study. Do not
  upload or commit tape-derived material. State this once in the report.
- Measure, don't assume. "Works" or "fails" must cite the self-check numbers AND a disassembly
  cross-check, not just that the tool ran.
- Reaching a live gameplay state is the costly part and is per-game reverse engineering; if a
  game defeats the menu-driving, say so and fall back to the targets you could drive. A precise
  "could not reach live play on game X, here is how far I got" is a good result, not a failure.
- If a self-check passes but you cannot corroborate the tool's actual output from the code, treat
  the tool as UNVALIDATED on that game and say so — a green self-check is necessary, not
  sufficient.
