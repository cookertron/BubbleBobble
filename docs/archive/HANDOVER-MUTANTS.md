# HANDOVER: the kit's mutation runner, for Bubble Bobble

Written 2026-10-06 for the Claude Code session porting Bubble Bobble.  Read it
once, do the steps in order, and stop to report if any check fails.  Step 6
folds what matters into `CLAUDE.md` and `next.md`; after that this file can go
to `docs/archive/`.

## What changes, and why

A full battery run takes about 4.4 hours (5,003 cases, 20 workers) because
every case runs the whole of `test/bb.test.js` -- about 35 s idle, 79 s under
load -- although most of its checks never touch the mutated line.  The rebuild
costs 0.2 s; the suite is the whole cost.

`tools/mutants.py`, the Spectrum Port Kit's runner (its manual, section 6.12),
runs each case against only the suite blocks that can kill it:

- One coverage pass per run maps each case's anchor to the top-level blocks of
  `bb.test.js` that execute it.  `tools/mutants.js` builds a "selectable" copy
  of the suite for this; `bb.test.js` itself is never modified.
- The block that killed a case last time runs first, and the run stops at the
  first FAIL.
- A case that survives its selected blocks is run against the WHOLE suite
  before it is called a survivor, so selection costs time, never a verdict.  A
  case that only the whole suite kills is reported as a MISS.

Measured on this repo, on a seeded sample of 24 cases checked against the M7.98
full run: every verdict agreed; 9.2 s a case while the killing blocks were
unknown and 1.3 s once known, against 54 s for the whole suite on the same
core.  Expect the first full run to be several times faster than 4.4 hours and
later ones well under that again; the first real run gives the true figures.

Everything `parallel.py` guarded against still holds: private worker trees
(`scratch/mutants/w*`), one run at a time (a lock), proof that each mutation
landed, CRLF kept byte for byte, timeouts that keep their FAIL lines, crashes
told apart (DIAGNOSTIC for a `BB_...Error`, BROKEN-MUTANT, CRASH), the
wall-clock floor, the all-survived alarm, UTF-8 output.  The real tree is
never written.

## Step 1 -- install (nothing changes behaviour yet)

Unzipped into the repo root, this handover adds `tools/mutants.py`,
`tools/mutants.js`, `tools/vendor/acorn.js` with `acorn.LICENSE` (MIT),
`scratchpad/compare_mutants.py`, and `scratchpad/battery/full_m798_cases.json`
(the M7.98 full run's per-case verdicts, for the comparisons below).  Then:

1. `port.json`: add
   `"mutants": {"cases": "scratchpad/battery/mutate7.py", "suite": "test/bb.test.js", "diagnostic": "BB_"}`.
   `mutate7.py` is read as data and never executed, so `MUTS` must stay a
   literal list with unique labels -- it is today: 5,003 cases, no repeats.
2. `.gitignore`: add `scratch/` and `build/mutants/` (the worker trees, and the
   runner's local state).
3. `tools/README.md`: a row for `mutants.py`.
4. Commit: `battery: the kit's mutation runner (tools/mutants.py)`.

Nothing is written into `build/` itself: the runner's temporary files live at
each worker tree's root, and `build/mutants/` is a directory, which the fixture
guard (it lists `build/*.json`) does not see.

## Step 2 -- profile it (about 3 minutes)

    python tools/mutants.py --profile --jobs 20

Expect `baseline: 1735/1735 checks passed` (or today's count), a coverage line,
and the slowest blocks.  If it says the selectable copy ran different checks
from the suite, STOP and report it: the runner refuses to continue rather than
test a different suite.

## Step 3 -- check it against M7.98 (a few minutes)

    python tools/mutants.py --sample 40 --jobs 20
    python scratchpad/compare_mutants.py

The first run also does the one-off preparation: every block run alone at
baseline, and learning what each block that fails alone depends on (see the
optional section below).  The baseline, the coverage and both of those are
cached in `build/mutants/prep.json` and reused while the suite, the page, the
rig, the fixtures and `mutants.js` are unchanged.

Expect `MISSES 0` in the summary line, and the compare script to report no
kills lost.  It counts KILLED, DIAGNOSTIC and TIMEOUT-KILLED all as kills: with
the run stopping at the first FAIL, a case M7.98 called DIAGNOSTIC may now be
KILLED by a row that fails before the throw.

## Step 4 -- the first full run, in the background

    python tools/mutants.py --background --jobs 20

It returns at once.  The one-line summary appears in
`build/mutants/summary.txt` and the log in `build/mutants/run.log`.  Do not
wait on it or poll it: write the PID and those two paths into `next.md` and end
the stage, as the owner's rule says.  `--background` detaches with
`DETACHED_PROCESS`, which has not been tested on Windows yet: if the command
does not return at once, or the log stops growing when the shell closes, start
it the way `watch.ps1` runs things today instead.

This run records every case's killing row and block in
`build/mutants/last.json`; that is what makes later runs fast.  When it ends,
run `python scratchpad/compare_mutants.py` again, now over all 5,003 cases.

## Step 5 -- the new routine

- After an increment: `python tools/mutants.py --affected --jobs 20`.  It runs
  the new cases, older cases whose anchor lines changed, cases whose killing
  block changed, and every dead anchor, which stays red until fixed.
- A full run (`--background`) at each milestone, after any change to
  `test/rig.js`, `tools/build.py` or the runner, and before a release.
- `--match TEXT` still picks cases by label (`||` separates alternatives), for
  one increment's cases while you write them.
- Say in each commit which kind of run it was, with its summary line.
- If a run dies, delete `scratch/mutants/.running` by hand.  That is
  deliberate: on Windows, probing whether the old process is alive would kill
  it.
- `scratchpad/battery/parallel.py` is retired; keep it for reference.

## Step 6 -- make it survive context clears

`CLAUDE.md` is re-read after every `/clear` and compaction, and `next.md` is
the bridge, so the change must be written into both.  In `CLAUDE.md`, append
to house rule 3:

       **The battery runs with `tools/mutants.py`** (the kit's runner): after
       an increment, `--affected --jobs 20`; a full run with `--background
       --jobs 20` at each milestone, after any change to test/rig.js,
       tools/build.py or the runner, and before a release.  Its one-line
       result lands in build/mutants/summary.txt -- never wait on it or poll
       it.  Every gate block must pass on its own: a case runs only the blocks
       its anchor reaches.  scratchpad/battery/parallel.py is retired.

In "Commit style", after "what the mutation battery covered", add "(affected
or full, with the summary line)".  In `next.md`, replace the battery parts of
both RESTART HERE sections -- the PID 29844 run and `watch.ps1` on
`full_m798.log` -- with where step 4 stands.

## Optional, recommended -- six blocks that cannot run alone

At baseline these blocks fail when run on their own, because each drives the
page's single built-in game object and expects the blocks before it to have
used it already ("booted it once"):

| block | lines | opens with | needs first |
|---|---|---|---|
| 87 | 24586-24873 | `if (A.keyreader) {` | 83-86 |
| 90 | 25872-25913 | `{` | 83-87 |
| 94 | 27149-27823 | `if (A.ctrlselect) {` | 83-87, 90 |
| 112 | 32607-33290 | `if (A.ctrlmenu && P.BB_MENU) {` | 83-87, 90, 94 |
| 113 | 33301-33649 | `if (A.redefine && A.ctrlmenu && P.BB_REDEF) {` | ... 112 |
| 114 | 33658-33998 | `if (A.loadspine && P.BB_SPINE && P.BB_ROMISR) {` | ... 113 |

Blocks 83-86 (lines 23562-24575: the load path, the game-over title wait, the
round drain) set the page's game object up.  The runner copes: it learned
these dependencies and runs them first whenever one of these blocks runs.  But
that costs time on every case that needs the chain, and on every case whose
anchor runs at load time, which can reach every block (27% of the battery).
The real fix is for each of the six to start from a known state: reset the
page's game object, or load a fresh page, at its top, so that it passes alone.
Afterwards a run prints no "depends on earlier blocks" lines; editing
`bb.test.js` invalidates the cached preparation by itself.

## Optional -- next.md's size

`next.md` is 58 KB, about 14,600 tokens, read at the start of every session.
Keeping it to where things stand and what comes next, with the history
sections moved to `docs/archive/next-2026-10-06.md` (searched, never read
whole), saves most of that on every session.  The owner's rule still holds:
`next.md` stays the only bridge.
