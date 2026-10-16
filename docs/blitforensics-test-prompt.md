# Test prompt: validate `blitforensics.py` for upstreaming to the Spectrum Port Kit

Copy everything below the line into a fresh Claude session (Fable 5.1 is fine) whose working
directory is a checkout of the **Spectrum-Port-Kit** (or the Bubble Bobble port, which has the
tool at `tools/blitforensics.py`). The goal is to rigorously validate the tool as a
game-agnostic kit tool, find its breaking points, and — only if it passes — upstream it.

The tool and its helper were drafted in the Bubble Bobble port:
- `tools/blitforensics.py` — the tool under test.
- `tools/screen.py` — gained `bmp_coords(addr)` (inverse of `scr_addr`); it must go up with it.

---

You are validating a new Spectrum Port Kit tool, `tools/blitforensics.py`, before it is added to
the kit. Work in the discipline of `docs/PORTING-ZX-TO-JS.txt` and `docs/TRAPS.md`: **measure,
don't assume**; a test that cannot fail is not a test (mutation-test each claim); the tool must be
**game-agnostic** (no per-game addresses baked in).

## What the tool claims to do

Given a saved harness state and the entry PC of a per-sprite draw routine, it recovers the sprite
that routine draws — its `W×H`, whether it is masked or opaque, and the full data+mask bitmap —
**without reading the blitter and without assuming size or byte order**, by a TWO-BACKGROUND
DIFFERENTIAL:

- run the same call from an identical saved state once over an all-`$00` display and once over
  all-`$FF`;
- classify each written byte: identical over both = **OPAQUE**; `over-$FF == over-$00 XOR $FF` =
  **XOR** (data recoverable, mask is not — it is flagged); otherwise **MASKED**
  (`screen = (screen AND mask) OR data`);
- `data = over-$00`; for a masked blit the bits that differ between the two runs are the
  transparent (background-showing) pixels.

It bounds one call by the return address found on the stack at entry, and runs with interrupts off.

## Your job

Build the evidence that the tool is correct where it claims to be, and that every documented
limitation either (a) is guarded (the tool warns/flags) or (b) is a clean, stated failure — not a
silent wrong answer. Produce a report `docs/blitforensics-test-report.md` with a PASS/FAIL verdict
per section and the exact commands and outputs.

### Section A — synthetic gold gate (tape-free; this is the strongest test and should become a
`selftest.py` case)

Construct three tiny blit routines in RAM with a KNOWN sprite, run the tool at each, and assert it
recovers exactly what you poked. This needs no game. Set up a harness (a ROM-only `Harness` as the
harness self-tests build one, or load any existing saved state and overwrite RAM), poke a caller
`CALL $8000` at the PC so the return address bounds the call, set `B`=row count, `HL`=source,
`DE`=a char-aligned mid-screen bitmap address (e.g. `0x4820`), `save_state_file` it, then run
`python tools/blitforensics.py --state <name> --entry 0x8000 --target 0x4000 0x5B00`.

Routine bytes (each draws an 8-wide × B-row sprite, advancing one pixel row per `INC D`):

1. **Masked-OR** at `$8000` — source is `mask,data` pairs (2 bytes/row):
   `1A A6 23 B6 23 12 14 10 F7 C9`
   (`LD A,(DE) / AND (HL) / INC HL / OR (HL) / INC HL / LD (DE),A / INC D / DJNZ $8000 / RET`).
   Expect: `MASKED`, `data == over-$00`, transparent pixels exactly where `mask=1 & data=0`.
2. **Opaque copy** at `$8000` — source is data only (1 byte/row):
   `7E 12 23 14 10 FA C9`
   (`LD A,(HL) / LD (DE),A / INC HL / INC D / DJNZ $8000 / RET`).
   Expect: `OPAQUE`, zero transparency, `data == over-$00 == over-$FF`.
3. **XOR** at `$8000` — source is data only:
   `1A AE 12 23 14 10 F9 C9`
   (`LD A,(DE) / XOR (HL) / LD (DE),A / INC HL / INC D / DJNZ $8000 / RET`).
   Expect: `XOR` detected and flagged; `data == over-$00`; the tool must NOT report a bogus mask.

For each: choose a data pattern with both set and clear bits (e.g. rows `3C 42 81 A5 A5 81 42 3C`)
and, for the masked case, a mask that is transparent in some clear-data pixels and opaque in
others — then assert the recovered grid equals the sprite you poked, cell for cell. **Mutation-test
the gate**: flip one source byte and confirm the assertion fails; flip the AND/OR to XOR and
confirm the classification flips. A gate that stays green under mutation is worthless.

### Section B — real blitter anchor (if a port with a known blitter is present)

In the Bubble Bobble port, `python tools/blitforensics.py --state round1 --entry 0xA600 --skip 1`
must report a `16×16 MASKED` sprite, row-major, whose ASCII is a rounded creature with two eyes and
a transparent left border (the enemy at `$C100`). This is the cross-check that the two-background
method agrees with hand instrumentation. If you have Chuckie Egg or Gauntlet states with a known
draw routine, repeat there and confirm the recovered sprite matches a `contact.py`/`screen.py`
render of the same graphic.

### Section C — adversarial / documented limits (each must be a guarded or clean failure)

1. **Fall-through vs CALL entry.** Hook an entry reached by fall-through and one reached by CALL;
   confirm the return-address bound is right or the result is obviously wrong (not subtly wrong).
   Propose a more robust bound if you can break it (e.g. an entry whose stack top is not its return).
2. **Background-restore routine.** Hook a full-frame routine that restores the background before
   drawing; confirm the tool prints the "fully solid … may be a background-restore" warning rather
   than silently reporting OPAQUE.
3. **Back-buffer / shadow.** Hook a blit that writes to an off-screen buffer; confirm `--target LO
   HI` at that buffer recovers it, and that the default (display) prints the "wrong entry / draws
   to a shadow" message, not a crash.
4. **Non-deterministic frame.** Confirm the two runs draw the SAME frame (they start from one saved
   state); construct a routine that advances an animation counter and confirm the restore prevents
   drift (or document that it doesn't).
5. **Clipping at screen edges;** **taller-than-one-cell sprites;** **attribute-only writes.**

### Section D — determinism

Run Section B twice; byte-identical JSON both times.

## Pass/fail

PASS only if: Section A recovers all three synthetic sprites exactly and its mutations fail as
expected; Section B matches the anchor; every Section C case is a guarded warning or a clean,
stated failure with no silent wrong answer; Section D is identical. Report any wrong-but-silent
result as a FAIL with a minimal repro.

## If it passes — upstream

Copy to `..\Spectrum-Port-Kit`: `tools/blitforensics.py`, the `bmp_coords` addition in
`tools/screen.py`, the `README.md` tool row, and add the Section A synthetic case to
`tools/selftest.py` (tape-free, so it runs in the kit gate). Record the kit HEAD sha you branch
from. Never commit tape-derived material (house rule 7): the synthetic gold gate uses only
poked bytes, so it is safe; do not add any game's sprite bytes to the kit.
