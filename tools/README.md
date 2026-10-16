# tools/ -- the game-agnostic analysis kit

Every tool here reads its game-specific facts from ONE manifest, `port.json` at
the repository root, through `tools/portconfig.py`: which tape, where the loader
leaves each block, the entry point, the PC of the game's own CALL into the ROM
loader, and where the 64K image and the saved machine states live.  A tool finds
the manifest by walking up from its own directory (or from
`PORT_JSON=/path/to/port.json`), fills in defaults for anything missing or
`null`, and never fails at import: `--help` works with no manifest at all, and a
tool only stops -- naming the key to fill in -- when it actually needs a value.
Numbers in the manifest may be JSON ints or hex strings (`"0x8400"`, `"$8400"`);
paths are relative to the manifest's directory.  The build script (`build.py`)
reads the same file (`name`, `template`, `out`, `includes`, `assets`); the
analysis tools read `tape` and `z80`.  Run `python tools/selftest.py` first: it
proves the whole kit against a synthetic tape and a ROM-only machine with
nothing filled in, so a missing SkoolKit ROM, z80dis or Pillow shows up before
phase 1, not in phase 8.

## Tools by phase

| tool | purpose | typical invocation | manual phase |
|---|---|---|---|
| `portconfig.py` | the manifest reader every tool uses; run it to print the merged config and which `port.json` was found | `python tools/portconfig.py` | all |
| `selftest.py` | self-test with NO tape: synthetic TZX, ROM-only harness, tiny images; exit status non-zero on failure | `python tools/selftest.py [-v]` | 7 the simulator harness (run before anything) |
| `tzx.py` | TZX parser: prints and STOPS on any unhandled block, verifies every ROM-format checksum, decodes headers, checks body length against header, dumps block bodies | `python tools/tzx.py tape/game.tzx --dump build/blocks` | 1 read the tape |
| `basic.py` | BASIC detokeniser; reports each USR target from the 5-byte binary form the ROM actually acts on, not the printed digits | `python tools/basic.py build/blocks/game.b01.body.bin` | 1 read the tape |
| `hexdump.py` | hex + ASCII dump with a base address | `python tools/hexdump.py build/image.bin --offset 0x8000 --len 64` | 2 the loader and the memory map |
| `mkloader.py` | scratch 64K with only the BASIC block at PROG ($5CCB) plus the stub's own relocation, so the stub disassembles at its running address | `python tools/mkloader.py [--copy 0x5CF1 0xFF00 0x100]` | 2 the loader and the memory map |
| `mkimage.py` | the post-loader 64K image, ASSERTED from the loader's postcondition (`tape.blocks`, `tape.copies`); `--upto N` for a transient stage | `python tools/mkimage.py [--upto 1]` | 2 the loader and the memory map |
| `adis.py` | annotated disassembler (z80dis): symbol substitution, region banners, DEFB rows for data regions, raw bytes beside each instruction | `python tools/adis.py 0x8400 40 [--image build/live.bin]`; `--sym NAME=ADDR` | 4 build an annotated disassembler |
| `walk.py` | recursive-descent code walker -- a LOWER BOUND on code -- plus the port / HALT / IM / below-$4000 inventory and the call graph | `python tools/walk.py [--entry ADDR] [--report calls]` | 4 build an annotated disassembler |
| `grepbytes.py` | byte-pattern search with instruction-boundary confirmation; unconfirmed hits are reported, not dropped | `python tools/grepbytes.py "CD 56 05"` | 4 build an annotated disassembler |
| `strings.py` | printable runs, and bit-7-terminated runs | `python tools/strings.py --min 4 [--hi]` | 5 static extraction of data |
| `speckle.py` | rank byte ranges as art vs noise -- the crude sweep before a disassembly says where the graphics are | `python tools/speckle.py build/image.bin --w 2 --h 16` | 5 static extraction of data |
| `contact.py` | contact sheet of a range rendered as sprites BOTH ways (row-major and cell-major); LOOK | `python tools/contact.py build/image.bin out.png --base 0x5F00 --len 0x1000 --w 2 --h 16` | 5 static extraction of data |
| `screen.py` | render the display file / 32x24 attribute sheet out of a memory image; `scr_addr(x,y)` and its inverse `bmp_coords(addr)` (ULA geometry) for turning write logs into footprints | `python tools/screen.py build/live.bin out.png [--attrs]` | 6 ground truth from a real frame |
| `harness.py` | the Z80 simulator harness: real 48K ROM (read locally from SkoolKit), tape deck at a PC breakpoint, keyboard/Kempston ports, memory write watch, step / run_until / run_frames / profile / call / save_state; ULA contention by default; `Harness(paging=0x10)` adds an opt-in 128K `$7FFD` paging port and AY (the 128K branch on the 48K clock, its differences declared) | `python tools/harness.py` (profile from the entry point); `from harness import Harness` | 7 the simulator harness (the pivot) |
| `harness128.py` | the 128K machine: SkoolKit's contended simulator over the paged memory (70,908-T frames), `$7FFD` paging, the AY's register writes and reads logged with their T and PC, speaker edges, an exact HALT skip, hooks (`add_hook`, `on_return`, `frame_hooks`), the C engine as a proven-identical accelerator; boots `z80.snapshot128` | `from harness128 import Harness128`; `python tools/harness128.py [snap.z80]` | 7 the simulator harness (a game with a 128K branch) |
| `boot.py` | boot (from `z80.snapshot` if set, else the tape), `--state NAME` to resume, `--arm-at ADDR` for the interrupt trap (6.3), optionally drive a key script, dump the LIVE image and save a state | `python tools/boot.py --state boot --arm-at 0x8000 --script "60:,60:SPACE" --save menu` | 7-8 boot / drive into live play |
| `simload.py` | the SNAPSHOT ROUTE: run the tape's own loader in SkoolKit's simulated LOAD (tap2sna) -> a .z80/.szx at hand-over; handles protected/custom loaders (bleepload, speedlock, alkatraz, ...) with no loader-specific code | `python tools/simload.py [--machine 48\|128] [--start ADDR] [--no-finish-tape]` | 1-2 tape + loader |
| `snapimport.py` | a .z80/.szx/.sna snapshot -> the harness image (`build/image.bin`) + a saved state (`--save NAME`); prints the loader's postcondition (PC/SP/IM/IFF/I/border) | `python tools/snapimport.py build/boot48.z80 --save boot` | 2 the loader and the memory map |
| `bleepload.py` | decode a Firebird Bleepload tape: block framing (block->dest map, groups), the driver's decryption of group 1 (applied), the later groups' XOR key read from the stage-2 loader, the driver's own copies and hand-over JP read from its code (printed; `--apply-copies`), and a diff against the snapshot with every mismatching page attributed -- to recover R3 (the tape-byte cross-check) the snapshot route loses; verified against thirteen titles on fourteen tapes (1986-89; a 128K side included) | `python tools/bleepload.py [--snapshot build/boot48.z80] [--apply-copies]` | 3/5 cross-check |
| `keyprobe.py` | which key does something: press each of the 40 from one state, diff PCs and memory; exports `KEYS` / `keymask` / `KEYMAP` / `press` / `parse_script` / `drive` | `python tools/keyprobe.py --state menu` | 8 drive into live play |
| `readwatch.py` | find buffers that are only ever READ (a level map) by watching memory reads per PC and page | `python tools/readwatch.py --state level --lo 0x5B00 --hi 0x8000` | 8 drive into live play |
| `fieldlog.py` | watch named RAM fields evolve over driven play, printing only the frames where something CHANGES (transition-diff over time; the complement to readwatch's reads-by-PC) -- fields from `--fields`, an entity table via `--slots/--off`, or the manifest varmap | `python tools/fieldlog.py --state round1 --frames 240 --slots 0xFD94:10:1 --off 0:2,4,5,6,7,9 --dec` | 8 working-RAM discovery / 10 behaviour |
| `bubdraw.py` | the bubble blitter `$B9E7` and the erase `$BF16`: decode, VERIFY a transliteration against the machine write for write (order included), and capture the oracle + the shipping sprite asset. `verify --sweep` runs every X sub-shift x Y residue x bubble kind; `erase --sweep` the same for the erase; `d380` checks the `$BF5B` element-sprite build against the live element states | `python tools/bubdraw.py erase --sweep` | 10 behaviour / 12 engine |
| `entdraw.py` | the ENTITY render pass `$A447` / `$A3AD`: decode, VERIFY a transliteration against the machine write for write (order, entity fields and the beam accumulator included), and capture the oracle. Carries SYNTHETIC scheduler scenes -- the natural ones never exercise the beam window | `python tools/entdraw.py verify --sweep` | 10 behaviour / 12 engine |
| `isrcost.py` | the ISR COST oracle: every sampled interrupt with BOTH halves bracketed by CONTROL FLOW inside it, so `total - skeleton - parts` must be 0. Branch-checks every state ($8DC4 == $C9) and REFUSES a 128K one | `python tools/isrcost.py capture` | 9 time / 12 engine |
| `spawn.py` | the ROUND SPAWNER `$727B`: capture what the machine leaves for every round (entity table, `$AA57`, the `$73A6` target rows, the `$A891` wake-up delays, the behaviour list) and re-verify it. `analyse` prints the measured (type, facing) -> sprite and handler tables | `python tools/spawn.py capture` | 5 data / 12 engine |
| `walker.py` | the `$AA60` update pass and the `$B028` walker, THREE oracles in one fixture: (a) the enemy table, the `$A891` wake-up delays and the pass globals frame by frame, over freshly spawned rounds as well as shipped states; (b) `$B028` called DIRECTLY, once per case, over the sampled world and over a BUILT one -- colour shadow and the `$712F` dummy page cleared and poked cell by cell, because the ledge -> hop launch and the above-the-HUD dummy reads are unreachable in every captured round; (c) each of the eight handlers called directly with the walk-gate bit both ways, which is the only way to tell type 0's unconditional `CALL $B028` from types 1 and 5; (d) the BALLISTIC HOP `$B0F7` entered through `$B028` with `(IY+9)` pre-set, over a built world whose wall cell and arc-displaced landing row are poked per case | `python tools/walker.py capture` | 10 behaviour / 12 engine |
| `battery.py` | the post-harness diagnostic battery over driven play: Q2 ports, Q3 self-modification, Q10 clock, Q13 coverage, Q15/Q16 render + colour, Q17 speaker, Q19 stack | `python tools/battery.py --state level --loop 0x8503 --script "60:D,60:Z"` | 8 drive into live play |
| `sfxcensus.py` | phase-11 census: WHICH beeper/AY sites fire and WHEN under a key script -- every `OUT` attributed to the executing PC, `$FE` writes grouped into bursts with their sites, other ports counted; raw edge log to `--out` JSON for modelling | `python tools/sfxcensus.py fruit --script "5:,30:P,60:" --out build/sfx/collect.json` | 11 sound |
| `sfx_trace.py` | phase-11.4 oracle: every beeper emitter CALLed in isolation with its live parameters across its range (and the per-tick ones DRIVEN by key), every `OUT ($FE)` edge stamped `[T-offset, value]` -> `build/sfx/<name>.json` + `index.json` (edge count, speaker transitions, span, half-period range) -- the fixtures the engine's generators are diffed against | `python tools/sfx_trace.py [collect]` | 11 sound |
| `filmstrip.py` | consecutive frames side by side, keys held -- LOOK at them | `python tools/filmstrip.py strip.png --state level --keys D --every 4` | 8 drive into live play |
| `clock.py` | the clock model by HISTOGRAM of T-states between visits to the loop top (never the mean) | `python tools/clock.py --pc 0x8503 --state level` | 9 measure time |
| `blitprobe.py` | where the draw routine actually WRITES: (writer PC -> region) histogram of every write above $4000, shadow screen labelled if you give it | `python tools/blitprobe.py --state level --keys D --shadow 0xC000` | 10 read the routines, write the behavioural spec |
| `blitforensics.py` | measure ONE sprite blit from ground truth: a TWO-BACKGROUND differential (run the call over all-$00 then all-$FF, diff the writes) recovers the sprite's WxH, MASKED/OPAQUE/XOR and the full data+mask bitmap WITHOUT reading the blitter or assuming size/order -- POP/LDI/AND-OR/OR-only/opaque alike, XOR detected+flagged, an empty result declared EMPTY; a THIRD run over the real background checks the model `(bg AND mask) OR data` byte for byte and disowns the grid on a mismatch.  One call is bounded by the return address at `--entry` (a CALL/RST must precede it, else refused; `--ret 0xADDR` or `--ret IX` for a blitter entered by JP that ends `JP (IX)`; a call that never returns exits 3); `--target LO HI` measures a same-layout back-buffer.  Synthetic gold gate in selftest; validated on Bubble Bobble, Chuckie Egg, Chuckie Egg 2 (draw AND erase pass) and Gauntlet (three shadow-screen blitters), model mismatch 0 on all | `python tools/blitforensics.py --state play --entry 0xA600 [--skip N] [--target 0xC000 0xDB00] [--ret IX] [--src HL]` | 5 static extraction / draw routines |
| `srctrace.py` | ring buffer of PCs (with SP) leading up to a target PC, optionally gated on SP -- "who set this up" | `python tools/srctrace.py --state level --pc 0x9DD2 --sp 0x5F00 0x6F80` | 10 read the routines, write the behavioural spec |
| `build.py` | assembles the shipped single HTML file from the template, the includes and the asset JSON | `python tools/build.py` | 12 write the engine |
| `build_debug.py` | the DEBUG page: runs `build.py`, then writes the built page plus a debug layer (`web/debug.js`, inlined at the end of the page's script) as `web/<name>_debug.html`; refuses a faithful page that carries the layer's marker, and proves the debug page is the faithful page plus the layer, byte for byte | `python tools/build_debug.py` | 14 test the built artifact |
| `debug_mutants.py` | the debug layer's mutation run: each mutant one exact replacement in `web/debug.js`, its page assembled as `build_debug.py` assembles one, through `test/debug.test.js` (`BB_DEBUG_PAGE`); a CONTROL must pass whole; pages and outputs in `scratch/debug_mutants/` (git-ignored) | `python tools/debug_mutants.py [--jobs 14] [NAME ...]` | 13-14 tests / mutation battery |
| `mutants.py` | the mutation battery's runner (manual 6.12): cases from `port.json` `mutants.cases` (read as data), each run in a private worker tree against only the suite blocks that execute its anchor (coverage pass via `mutants.js`, which builds a selectable copy of the suite with `vendor/acorn.js`), killing block first, stopping at the first FAIL; a survivor is re-run against the WHOLE suite before it is called one (MISS if only the whole suite kills it); state in `build/mutants/` | `python tools/mutants.py --affected --jobs 20`; full: `--background --jobs 20`; `--match TEXT`, `--sample N`, `--profile` | 13-14 tests / mutation battery |

Phases 3 (third-party disassembly), 11 (sound), 13-16 (differential tests,
headless tests, provenance, handover) have no generic tool here: theirs are
game-shaped and get written against the engine, as the manual says.  The
example addresses in the invocations above are the case study's.

## The manifest keys the tools read

```
"tape": {
  "path": "tape/game.tzx",   the tape the post-loader image is built from
  "deck": null,              the tape served at runtime loads (default: path)
  "blocks": [],              [] or "auto": follow the ROM headers (a stock tape:
                             BASIC to PROG, CODE to its header address); else
                             one entry per block for a custom loader --
                               {"dest": "0x8600", "len": "0x5210", "flag": "0x80"}
                               {"dest": "0x8400", "len": "0x7777", "block": 6}
  "copies": [],              the loader's own post-load moves, e.g. a stub
                             relocating itself:
                               {"src": "0x5CF1", "dst": "0xFF00", "len": "0x100"}
  "prog": "0x5CCB",          where a BASIC block is LOADed (stock 48K)
  "entry": null,             PC when the loader hands over -- REQUIRED to run
  "sp": "0xFFFF",            SP at that moment (the game usually sets its own)
  "tape_call_pc": null,      PC of the game's own CALL into LD-BYTES, if it
                             loads levels at runtime; this enables the deck
  "tape_ret_pc": null        where that CALL returns (default: call + 3)
},
"z80": {
  "contended": true,         CMIOSimulator (ULA contention) or plain Simulator;
                             PORT_CONTENDED=0/1 in the environment overrides
  "symbols": "tools/symbols.json",   {"0x8400": "main"}                    (adis)
  "regions": "tools/regions.json",   [{"start","end","desc","kind"}]      (adis)
  "states": "build",         directory for saved machine states (NAME.pkl)
  "image": "build/image.bin" the static post-loader image mkimage.py writes
  "snapshot": null,          a .z80/.szx to BOOT from (the snapshot route,
                             manual 6.1); when set, Harness() and the --state
                             tools use it instead of the tape block table
  "snapshot128": null,       the same tape on a 128K (for a 128K layer)
  "varmap": "tools/varmap.json"  {name:{addr,width,note}} a port fills in, so the
                             engine, the differential sampler and the tests all
                             share one variable-name table
}
```

A block matched by `flag` takes the first unused data block with that flag byte,
in tape order; `block` is the TZX block index as `tzx.py` prints it.  `len` is
the loader's own count and a payload of another size is an ERROR -- it means the
block table is wrong.  `tools/symbols.json` and `tools/regions.json` ship empty
(`{}` and `[]`); `adis.py --sym NAME=ADDR` grows the first.

## Typical flow

    python tools/selftest.py                          # prove the environment
    python tools/tzx.py tape/game.tzx --dump build/blocks
    python tools/basic.py build/blocks/game.b01.body.bin       # -> the USR target
    # read the loader; fill tape.blocks / tape.copies / tape.entry in port.json
    python tools/mkimage.py && python tools/walk.py && python tools/adis.py 0x8400 60
    python tools/harness.py                           # profile from the entry point
    python tools/boot.py --steps 400000 --save boot
    python tools/keyprobe.py --state boot             # -> which keys do what
    python tools/boot.py --script "60:,30:SPACE,300:1" --save level
    python tools/clock.py --pc 0x???? --state level   # the loop top from the profile
    python tools/battery.py --state level --loop 0x???? --script "60:D,60:Z"
    python tools/filmstrip.py strip.png --state level --keys D

Requirements: Python 3, SkoolKit 9 (its `resources/48.rom` is read locally and
never copied), z80dis, Pillow.  Everything the tools write under `build/` --
block bodies, images, states -- is tape-derived: keep it out of the repository.
