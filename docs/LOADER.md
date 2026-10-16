# Phase 1-2 record: the tape, the loader and the memory map

Tape: `tape/Bubble Bobble.tzx`, 55,769 bytes, TZX 1.10 ("Created with Ramsoft MakeTZX").
`python tools/tzx.py "tape/Bubble Bobble.tzx"`: **214 blocks, 195 carrying data, no checksum
or length problems.** Block census: 4 × `0x10` standard, 191 × `0x11` turbo (pilot 2165 T,
sync 667/735, zero 856, one 1712, 249-250 pilot pulses, 267-275 bytes each), 6 × `0x12` pure
tone, 6 × `0x20` pause, 3 × `0x21`/`0x22` groups ("Bleepload Group 1/2/3"), 1 × `0x30` text.
Turbo body bytes 50,855; payload 191 × 256 = 48,896 bytes.

## BASIC (block #2, 181 bytes; `tools/basic.py`)

```
10 REM  BUBBLE BOBBLE - v.9/87
20 CLEAR 50000
30 BORDER 0:PAPER 0:INK 0:CLS
40 PRINT AT 1,9;PAPER 1;INK 7;" BUBBLE BOBBLE "
50 LOAD "Bobble"CODE 52480
60 RANDOMIZE USR 52480          ; binary form $CD00 -- the stage-1 stub
```

## Stage 1: the Bleepload stub at $CD00 (block #4, 512 bytes)

Disassembled in memory with z80dis (`tools/adis.py 0xCD00 200 --image build/image.bin`
reproduces it). Flow:

1. `LD A,($5B5C) / LD ($6000),A` — saves the 128K **BANKM** system variable (the last
   `$7FFD` value; `$00` on a 48K, `$10` on a 128K in 48 BASIC mode) into `$6000`.
2. `LD A,2 / CALL $1601` (ROM CHAN-OPEN, screen) and `LD ($5C6B),0` (DF_SZ) — it prints
   "Loading xx" (block number in hex) with `RST $10` through the ROM.
3. The block loop at `$CD21`: `CALL $CD74` reads one block into the buffer at `$FE00` with
   its own edge-detection loop (`$CE06`: `LD A,$16 / DEC A / JR NZ` delay, `INC B / RET Z /
   LD A,$7F / IN A,($FE) / RRA / NOP / XOR C / AND $20 / JR Z` — the ROM LD-EDGE core with
   the BREAK test replaced by `NOP`; border toggles `AND 7 / OR 8 / OUT ($FE)`). Block
   length = `$109 + ($FF15)` where `($FF15)` = `(previous block's tail byte AND 7) + 1`
   (`$CD4A-$CD5A`).
4. Buffer layout: `$FE00` group id (`$64` 'd' for group 1; the stub checks `CP $64`),
   `$FE01-$FF00` 256 data bytes, `$FF01` block number (compared with D, incremented per
   block), `$FF02-$FF03` destination address, `$FF04...` tail.
5. `$CE30` XOR-folds the block and compares with the byte after it; a failure prints
   "Block ?" / "Rewind to" / "Searching" (text at `$CE5D-$CEC9`).
6. `$CD5F` copies the 256 bytes verbatim (`LDIR`) to the destination, then `$CD47-$CD5E`
   skips `($FF04)` bytes into the tail, takes the next block's length byte, and **`JP (HL)`
   executes code carried in the block's tail** — the loader is distributed across the tape.

## The group-1 driver at $5B00 (arrived in a group-1 block; self-decrypting)

Read from the snapshot (`tools/adis.py 0x5B00 120 --image build/snap48.bin`, the snapshot
taken at the end of the tape). After group 1 the tail code lands here and:

- `$5B12-$5B50`: XOR-decrypts a page at `($FEE7)` with a two-byte key stream, decrypts its
  own continuation at `$5B40+`, clears `($5CB0)`, sets DF_SZ, decrypts `($FEE9)..($FEEC)`
  page-wise. (The decrypted form is what the snapshot holds; nothing here is reproduced.)
- `$5B51`: `LD SP,$60FF`; **`LDIR $CF00 → $4000, $1B00 bytes`** — the loading screen was
  loaded at `$CF00-$E9FF` and is copied to the display file here; **`LDIR $EA00 → $6100,
  $1000 bytes`** — 4K relocated.
- `$5B6A-$5B7B`: group id `$65`, "Loading" position, `CALL $FA00` — **stage 2** loads group
  2. Then the screen is cleared (`$5B7E`), group id `$66`, `CALL $FA00` loads group 3.
- `$5B9F`: **`LDIR $4000 → $FA00, $600 bytes`** — group 3's six blocks were staged in the
  display file (`$4000-$45FF`) and are moved over the top of stage 2 and its buffer
  (`$FA00-$FFFF`), so the final image has game bytes there.
- `$5BAA`: **`LD A,($6000) / LD ($5B5C),A`** — BANKM restored from the copy: the game
  reads the system variable `$5B5C` (Q8; `$00` on 48K, `$10` on 128K in the two
  snapshots).
- `$5BB0`: `LD SP,$61A7`; `CALL $028E` (ROM KEY-SCAN): if a key pair with `D-E = $21` is
  held, `LD IX,$61A8 / LD DE,$9E58 / LD A,$FF / SCF / CALL $0556` loads a hidden 40,536-byte
  headerless file from tape into `$61A8` (a border-flash loop on error) — a developer/extra
  path that is not on this tape; otherwise **`JP $F5BC` — the hand-over.**

## Stage 2 at $FA00 (overwritten by group 3 afterwards; read from the end-of-tape snapshot)

Same loading core as stage 1 (`$FA90`/`$FB1D`), group id from `($FBFE)` ← `($5B00)`,
"Loading" text positions from `$5B01-$5B04`. Differences that matter for `bleepload.py`:

- **`$FA77`: every data byte is XORed with the destination's high byte** (`LD A,($FF03) /
  XOR (HL) / LD (HL),A / LDI`) before the copy — groups 2 and 3 are stored scrambled.
- `$FA3C-$FA45`: the last block of a group is the one whose destination high byte equals
  `($FF05) - 1`; then `$FA6A`: `LD HL,($FF06)` and `PUSH HL / RET` jumps there if non-zero,
  else `RET` to the driver.

## Loader postcondition (the state the game starts from; `tools/simload.py --start 0xF5BC`)

```
tap2sna.py -c machine=48 -c accelerator=list -c finish-tape=1 --start 62908 ... build/boot48.z80
Simulation stopped (PC at start address): PC=62908
Accelerators: bleepload: 892782; misses: 0
```
`PC=$F5BC  SP=$61A7  IM=1  IFF=0 (DI)  I=$3F  border=5 (cyan)  BANKM ($5B5C)=$00 (48K) / $10 (128K)`
`($6000)` keeps the BANKM copy; `$5CB0` = 0. The 128K snapshot is identical at hand-over apart
from BANKM and the paging state (`out7ffd=$10`).

## Memory map

_Filled in by `tools/bleepload.py` (block → destination) and `tools/walk.py` (code/data)._

## Memory map (from `tools/bleepload.py` block→dest and `tools/walk.py` from $F5BC)

| Region | Contents |
|---|---|
| `$0000-$3FFF` | ROM (SkoolKit 48.rom, local only) |
| `$4000-$5AFF` | display file + attributes (loading screen at load time; gameplay screen after) |
| `$5B00-$5BFF` | the group-1 driver page (self-decrypted; runs once at load) |
| `$5C00-$5CBF` | ROM system variables |
| `$5CC0-$5FFF` | (never loaded from tape; work RAM) |
| `$6000` | the BANKM copy the stub saved; `$6100-$70FF` the decrypted relocated 4K |
| `$61A8` | IX base used by the developer extra-load path (`$5BBE`) |
| game code/data | `$5D01-$CBxx` and up; ~478 call targets, hot loop at `$8D09` |
| `$CD00-$CEFF` | Bleepload stage-1 stub (spent after load) |
| `$D000-$D1FF` | AY music engine + note tables (mixed code/data) |
| `$F3xx-$F4xx` | AY player: writes registers via `LD BC,$FFFD/$BFFD; OUT (C),A` |
| `$F5BC` | **entry** (the loader's `JP`); font/screen init then `JP $7274 → JP $8CC3` |
| `$F7B3` | menu key reader: `LD (LAST_K),0 / RST $38 / LD A,(LAST_K)` + `ROM_BEEPER` click |
| `$FA00-$FFFF` | stage-2 loader at load time; game bytes (group 3) after |

Reconstruction gate (`tools/bleepload.py`, the kit's generalised tool, validated against 13 titles and synced into this port): 191 turbo blocks in 3 groups (48/137/6); 187/192 pages loaded (the 5 missing are `$5C00-$60FF`, never on tape). The tool READS the loader's transforms off the tape rather than taking them from this document: first group `$64` from the stub's `CP` immediate; stub 512 bytes at `$CD00`, buffer `$FE00`; the group-1 key page `$C900` (block #8) XORed with the stub's two pages -> K, which decrypts `$CF00-$FBFF` and the driver page's own `$5B40+` (applied); stage 2 at `$FA00`, whose `LD A,($FF03)` at `$FA83` makes the later-group XOR key the destination high byte; the driver's copies `LDIR $CF00->$4000 $1B00` and `$EA00->$6100 $1000` after group 1, the screen-clear fill after group 2, `LDIR $4000->$FA00 $600` after group 3; and the hand-over `JP $F5BC` with `LD SP,$61A7`. With `--apply-copies`, vs the snapshot: **bytes compared 47,872 / mismatching 2,766 in 23 pages / unattributed 0.** Twenty-one of those pages are the transient display file (loading text and group-3 staging, not game data); the remaining 8 bytes are 6 in `$5B00` (the driver rewrites its own first bytes with the next group id and text position at run time) and 2 in `$6100` (the stack below SP=`$61A7` at hand-over). The decrypted 4K and the driver page now match byte-for-byte, so **R3 is complete for the game area**: every game byte in the snapshot is accounted for from the tape bytes plus named loader transforms.

## Clock and interrupts (early observations, to be measured in M2/M3)

- Front end: **IM 1** (`$FAC3`, `$122E`, `$40C3`); the menu polls the keyboard with `RST $38`
  and waits on `LAST_K` ($5C08). It also HALTs (`$FAC6`), so the harness must run it with
  interrupts armed (the snapshot hands over in IM 1, IFF=0; arm immediately — manual 6.3).
- Gameplay: **IM 2** (`$9639`; `I=$FC`, a 257-byte `$FF` table at `$FC00`, ISR reached via the
  `$FFF4: JP $8D72` trampoline). The main loop is at `$8D09` with `HALT` at `$8CFB`/`$8D..`;
  it looks **frame-synced** (Q10 to confirm by histogram in M3).
- Ports read during the menu: `$FE` half-rows only (keyboard). AY port loads (`$FFFD`/`$BFFD`)
  and `$7FFD` paging appear in the AY player and the sound dispatch at `$8E12`.

## Q8 — 48K vs 128K, and an OPEN sound question

The discriminator is **BANKM**: the stub saves `($5B5C)` to `$6000` before any paging; the
driver restores it (`$5BAA`); the game reads it once at `$95F5` (`LD A,($5B5C) / LD ($9AE7),A`)
and the sound dispatch at `$8E12` does `LD A,($9AE7) / OR 1 / LD BC,$7FFD / OUT (C),A` around
`CALL <AY engine>` — i.e. `$9AE7` is the value written to the 128K paging port to bank in the
AY.  **Open, and it gates all sound measurement (TRAPS #2):** the SkoolKit 48K snapshot leaves
`$9AE7`=$10 at the title screen, so in the harness the game takes the AY path and the AY writes
fall on the dead 48K ports.  Whether a real 48K takes a beeper branch (and how it decides — a
`$7FFD` read-back probe, or BANKM being 0) is to be settled in M6 before any sound is modelled;
until then, poking `$9AE7`=0 is the provisional 48K setting.  The in-game SFX use the beeper
(`OUT ($FE)` at `$8Fxx`); the music engine is AY.
