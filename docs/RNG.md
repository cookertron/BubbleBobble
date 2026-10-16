# RNG — the E1 decision record

**Status: DECIDED 2026-09-10.** Supersedes the plan's open item E1 ("declared statistical
substitute if the game reads R / the floating bus"). Everything here is MEASURED unless marked
INFERRED. Produced by a 13-agent measurement workflow (5 independent censuses, 3 design
proposals, 3 judging lenses, a synthesis and a completeness critic); the critic's findings and
two of my own re-verifications are folded in below.

---

## The decision in one paragraph

The port ships **two generators, kept strictly apart**. `$FE85` is a real state-based
generator, so the plan's *first* branch applies: **transliterate it byte-exactly**, no
substitute. It carries essentially all of the game's structural randomness. The eleven
`LD A,R` sites get a **declared substitute**, because exact reproduction is measured-infeasible
and — the decisive point — *meaningless*. Per-session variety comes from the machine's own
mechanism (the attract loop spinning the PRNG while a human waits), never from a wall clock.

---

## What the measurement found

### 1. The primary generator is not R

`$FE85` is a deterministic, self-modifying 16-bit hash whose state **is its own `LD HL,nn`
immediate operand** at `$FE86/$FE87`. Three independent agents re-derived the algorithm and
matched the machine byte for byte for eight draws from the tape-image seed `$002A`; a fourth
matched 60 live draws over 60 frames. The map is a **bijection** on 16 bits; the orbit through
`$002A` is a pure cycle of length **54,919**.

Nothing ever reseeds it. Over a full game start plus 1.6M play instructions the only writer of
`$FE86/$FE87` is the routine's own write-back.

| | draws/frame |
|---|---|
| `$FE85` PRNG, in play | 0.46 – 2.0 |
| `$FE85` PRNG, attract screen | 185 – 304 |
| all eleven `LD A,R` sites combined, in play | 0.06 – 0.23 |

Re-verified independently for this record: over 400 idle frames of `round1_48`, `$FE85` drew
**240** times (0.60/frame) while the R sites fired **22** times in total.

### 2. R is 7-bit for the life of the machine

There is **no `LD R,A` (`ED 4F`) anywhere** in the 64K image or the 48K ROM, so R's bit 7 stays
at its power-on 0. Every `LD A,R` returns **0..127, never 0..255** — bit 7 clear in ~25,000
observed firings across five censuses.

**Consequence: both `CP $2A` checks are 1/128, not 1/256.** Pooled 129 hits in 14,776 draws =
1/114.5 (115.4 expected at 1/128; 57.7 at 1/256; z = +9.4 against 1/256). Believing the old
figure would halve the enemy waddle and hesitation rates. The 7-bit extraction is therefore
baked into the generator and mutation-tested.

Opcode census, re-confirmed for this record against `build/image.bin` (65,536 bytes):

| opcode | meaning | count |
|---|---|---|
| `ED 5F` | `LD A,R` | 11 |
| `ED 4F` | `LD R,A` | 0 |
| `ED 57` | `LD A,I` | 0 |
| `DB FF` | `IN A,($FF)` floating bus | 0 |

### 3. Exact reproduction of R is infeasible *and* meaningless

The law is exact and simple: R at a site = (R at ISR entry + a constant for that code path) mod
128, verified with zero mismatches over 987,750 instructions. But R at ISR entry is uniform over
0..127, because the machine executes 8,246–9,304 instruction fetches per frame — about 8.3 wraps
of the modulus — driven by a main-loop pass count that varies 4..14.

All three "simple models" were refuted by direct measurement. R is not constant at a site (121
of 128 distinct values at `$B88D`). R is not a function of position within the frame (one
T-offset yielded seven different values). R is not a function of instructions since the ISR (an
identical code path at identical T yielded 35 different values). The decisive experiment: the
same snapshot and pokes run under the contended versus plain simulator, where only interrupt
placement differs, produced **0 of 22 matching draws** and a *different number* of draws.

And the loss is quantified:

| comparison | agreement on blocked-bubble redirects |
|---|---|
| two REAL runs, 64 T-states apart | 25.5% |
| a uniform substitute vs a real run | 37.3% |
| theoretical ceiling for the outcome distribution | 37.5% |

**The substitute is a closer match to any given real run than two real runs are to each other.**

### 4. Everything else was ruled out with evidence

No floating-bus read exists in the 64K. The ROM frame counter is never read (0 reads across 160
watched frames; the game is IM 2 and executes 0.00% of instructions in ROM). An exhaustive
self-modification census (3,211 executed addresses against 209,992 logged writes) found 60
writer/target pairs, of which exactly one is generator state. No uninitialised-RAM or
display-file entropy. Every keyboard and Kempston read masks to bits 0–4, discarding the
undefined ULA bits.

### 5. Two sites are not random at all

`$9715` and `$FEAC`, the front-end wipe, are **one `+51 mod 128` walk read twice at a fixed +35
offset** — 803/810 and 804/811 steps confirm the stride, 807/811 the offset. The loop body is a
fixed-length instruction sequence, so its masked output is a perfect eight-step cycle. An
independent generator there would visibly change the effect's texture. They get an exact walk,
not a substitute.

---

## The specification

### Generator A — faithful, exact

`prngNext(site)` transliterates `$FE85`, about ten lines. State lives **in the byte image** at
`$FE86/$FE87`, never in a JS field, because fixtures poke it and M8 RAM diffs read it.

Golden vector from `$002A`: `283E 6C08 CE6F F017 F46D 822C 27BF EF48`.

> **Trap (also logged in TRAPS):** the cycle length is seed-dependent — 54,919 from `$002A` but
> 7,503 from `$BB02`. Never reuse this map as the substitute stream, and never reseed it for
> variety.

Per the critic's finding C, this side gets the **same discipline as the substitute**: a frozen
call-site table, throw-on-unlisted, per-site counters and the per-frame balance assertion. Its
eleven `CALL $FE85` sites are `$88B1 $8AFD $8B11 $8BD7 $8BDF $950F $971D $9775 $9B28 $A0D0
$B414`.

### Generator B — the declared substitute

A 32-bit LCG per site; a draw is the **top 7 bits** (`s >>> 25`), giving 0..127. That shift is
the 1/128 correction made executable. Full period; the LCG's weak low bits are discarded by
construction. State is JS-side only, never in the byte image, so a RAM diff can never see added
state.

Per-site seeding derives each stream's identity from **its Z80 address**, so the site table
doubles as the census in code. Per-site streams (rather than one shared stream) exist for one
reason: wiring M7.6 can never shift M7.5's values, so no earlier fixture is invalidated as the
port grows. Measured cross-site correlation is 0.2506 against 0.25 for independent.

**Every mask stays transliterated at the call site.** The generator returns seven bits and knows
nothing about bubbles. This reproduces for free the `{3,4,5}` law with P(3)=1/2, the live table
lookup at `$8A38`, the never-C / mirror-half / perpendicular-quarter drift law, and the 1/128
equality rate. **Hand-written probability tables are forbidden** — the spec already carried two
bugs of exactly that kind.

### Seeding

The machine chain, measured: the tape image hands over with `$FE86/$FE87 = $002A`; nothing
reseeds it; the post-control-select menu loop spins the PRNG while waiting for the start key, at
185–304 draws per frame. **The state at the instant the human presses is the run's identity** —
16 consecutive press frames gave 16 distinct states.

The port reproduces that mechanism, not a clock. A session is a pure function of (wait frames,
key trace), enforced by a test. **No wall-clock seed, and no flag for one**: it is not what the
machine does, and it would silently delete replay and bug-report reproducibility.

**The `LD A,R` stand-in takes the same identity (M7.71).**  It used to be seeded with `BB_RNG_SEED` at
`reset()` and never again, so every page load drew the same sequence at every site: the element class
(`$7E04`) ran `6 12 9 10 9 10 5 5 11 ...` and class 8 -- EXTEND's second E, `$B80E` bit 3 -- first came
at the 35th pick, so the owner could never collect two E's.  Now `rngSession()` re-derives the
stand-in's per-site streams from `$FE86/$FE87` at the title's start press (`$979E` / `$9790`), the
state the `$9775` ring spin leaves there -- one more reader of the run's identity, not a new source.
Only the streams change: the counters, the starfield walk and a test's feed queue are kept.  Gated
(M7.71): 16 press frames give 16 distinct class sequences, one press frame always the same.

Until M7.8 the attract spin is a stand-in at a measured-but-provisional rate, behind a named
flag. At M7.8 the transliterated menu cycler replaces it and the gap closes to zero **with no
added entropy source**, because the loop's draw count is a function of the attribute file.

### The call sites

Eleven, each keyed by its measured Z80 address, with milestone:

| site | subsystem | milestone |
|---|---|---|
| `$B88D` | blocked-bubble drift redirect | **now (M7.5)** |
| `$B008` | enemy facing / waddle flip | M7.6 |
| `$B0D5` | enemy hesitation | M7.6 |
| `$873E` | the "?" bonus item's ink | M7.7 |
| `$8A2E` | power-up type, listed rounds | M7.7 — *transcribed, never observed executing* |
| `$8A38` | power-up type, unlisted rounds | M7.7 |
| `$7E04` | randomised elemental type | M7.7 |
| `$9811` | return-round lookahead | M7.7 — *transcribed, never observed executing* |
| `$A15F` | water direction seed | M7.7 |
| `$9715` | front-end wipe ink | M7.8 (owns the shared walk) |
| `$FEAC` | front-end wipe position | M7.8 (reads the walk at +35) |

### Injection for the differential gates

Frame-keyed (`expect` / `draw` / `endFrame`), **not a cursor**. Draw counts are
outcome-dependent — the same 400 frames produced 22 versus 26 draws from a timing change alone —
so a cursor silently reindexes the whole remaining stream after one missed decision, and the
gate then dies far downstream with a meaningless message or passes by luck. Frame-keying makes
house rule 2 ("the first differing row names the bug") mechanical, with three distinct named
failures: unexpected draw, unconsumed draw, wrong site/tag.

No silent fallback (house rule 6): a starved feed throws by default.

---

## Corrections folded in from the completeness critic

The critic found eleven substantive issues. The load-bearing ones, with the two I re-verified
myself marked:

1. **The zero-draw tripwire was a false invariant** *(re-verified: `$B0D5` fires 22 times in 400
   frames of plain idle `round1_48`)*. The fixtures show zero draws only because they logged
   `$B88D` alone. A total-count assertion would go red the day M7.6 lands correctly. **Scoped to
   the per-site count for `$B88D`.**
2. **A mutation that cannot fail** — "feed masked values instead of raw bytes" is a no-op,
   because the drift mask is idempotent, and its stated justification used wrong arithmetic.
   House rule 3 forbids exactly this. **Deleted and re-homed** to the sites where the mask is
   not idempotent.
3. **A twelfth PRNG consumer nobody had named**: `$B414`, a probabilistic turn-toward-the-player
   for an enemy sharing the player's row. Reached by fall-through only, which is why every
   census missed it. **Added to the PRNG table, flagged transcribed-not-exercised**, to be
   staged before M7.6.
4. **The hard-coded `$8A76 = $2A`** *(re-verified: `build/image.bin` already carries `$06`, the
   post-umbrella state)*. **Read it from the world image at draw time.**
5. **The PRNG cadence "law" was a 60-frame artefact** — a longer capture shows a 162-frame
   dropout and frames with one draw rather than two, and 2P is not a clean doubling. **The
   fixture must span ≥400 frames and include a dropout.**
6. **The purity stub missed its own mutation** (a clock seed taken in the constructor, before
   stepping). **The stubbed window now wraps construction.**
7. **`arm(WIPE)` contradicted the frozen eleven-key table.** `$9715` owns the walk; the table
   stays eleven.
8. **The primary gate dropped the field that gates the draw** — the occupancy word the redirect
   test reads. **Added to the diff.**
9. Doc-correction targets were slightly off; corrected below.

---

## Declared gaps (for README)

- **Mechanism.** On the machine R free-runs with the instruction stream and a read never
  advances it; the substitute advances only when drawn. No observable consequence at any
  uniform site.
- **Value departure, quantified.** The 37.3% / 25.5% figures above.
- **Within-frame correlation** at the drift site is real and not modelled: two bubbles blocked
  in the same frame take the same direction 19.2% of the time on the machine versus 21.7% under
  the substitute. **2.5 percentage points on a one-in-five event.** Declared rather than
  modelled, because modelling it would bake one code path's timing into the RNG.
- **Per-site streams** are an engineering choice, not the machine's shape (it has one shared
  counter). The only observable difference is the correlation above.
- **The "?" item's ink order** walks quasi-periodically on the machine; the marginal is
  unchanged but the frame-by-frame order differs.
- **The wipe's interrupt hiccups** are not modelled: about 7 of 811 steps slip the phase on the
  machine, giving 2 adjacent-ink repeats per wipe against 0 in the port.
- **Seeding** is a stand-in until M7.8, with the closure named.  Since M7.71 the `LD A,R` stand-in's
  streams are re-derived from the `$FE85` state at the start press, so a game's draws depend on the
  press timing as the machine's do (not on R's exact value, which is still not modelled).
- **Two sites are transcribed, not exercised** (`$8A2E`, `$9811`) across ~57 saved states and
  thousands of driven frames. Their masks are proven by direct execution on the Z80; their
  end-to-end reachability is INFERRED.
- **A front-end table overrun** is real and state-dependent (a 7-byte mask table indexed by
  `AND 7`, so one index reads a live variable — `$58` in the shipped image). Behaviour to be
  picked at M7.8.

## Rejected alternatives

Emulating R exactly (needs a fetch-exact Z80, buys nothing observable). Deriving R from the
port's `spend(T)` cost model (0/22 matching draws under a timing change; would chain every RNG
outcome to placeholder constants). A positional generator keyed by (site, index) — measured
badly anti-correlated in the exact dimension it existed to fix, and structurally blind to a
spurious draw. Replaying captured draws as the shipping strategy (the draw count itself
desynchronises). Reusing the PRNG map as the substitute stream (short orbits from some seeds).
`Math.random`, or any wall-clock seed. One shared substitute stream. A bare cursor feed.
Modelling the within-frame stride. Deferring seeding entirely.
