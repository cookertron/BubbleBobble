# Behavioural spec (M5) -- rules with addresses

Every rule cites the address it was read from (ORG is the game's own; the image is
`build/image.bin` from the snapshot). Provisional items are marked. Verified against
`build/round1.pkl` (settled round 1) unless noted.

## Clock and dispatch (M3)

- Gameplay is FREE-RUNNING: no HALT in the play path; the loop runs ~6-9 passes per video
  frame. The IM 2 interrupt `$8D72` is the only 50 Hz tick (exactly 1/frame, 69888 T).
- Main loop body: the CALL chain `$8D25-$8D61` (20 routines), reached from `$8D1E`; loops back
  after the game-over/pause checks at `$8D0D` (`$FEC9`), `$8D12` (`$FECD`), `$8D1E` (`$FEC8`).
- **The ISR `$8D72` is the RENDERER** (CORRECTED 2026-09-09, measured by exact stepping on the
  48K branch, `round1_48`): after the frame/hurry counters (`CALL $8DB5`) it takes the frame-parity
  branch `RR L`: ODD frames -> `$8DA2` (gate `$FEC4` non-zero): `CALL $A3AD` = the ENTITY DRAW
  PASS (players/enemies/Boris/boss: SP parked at `$AA59`, the draw-parity byte `$A3B2` toggled,
  bit 5 cleared on all 9 entity `+7`s, then per entity erase-from-shadow + masked blit `$A651`;
  **~26.7k T = 0.38 frame** in idle round 1) then `JP $AA60` (`$FEC6` 25 Hz counter, previous-pos
  bookkeeping). EVEN frames -> `$8DAD` (gate `$FEC5` non-zero): `JP $B62C` = the BUBBLE pass
  (~1.4k T with no bubbles). Both return to `$8D8F`, which then `CALL $8DC4` = the sound hook
  (see the M6 section). So **sprites are drawn at 25 Hz inside the ISR** and the main loop
  free-runs at **7 passes on draw frames / 11 on bubble frames** (idle round 1, both branches).
  The earlier reading "the parity-1 branch runs the MUSIC for ~0.45 frame" was WRONG: that cost is
  the draw pass, identical on the 48K branch, where no music exists at all. The ISR is accepted
  at T=41-48 of every frame (0 missed) and its odd-frame work spills ~0.4 frame into the frame.
- Round start is NOT delayed by a jingle on either branch: from the '1' press, the P1 record
  goes live at +5 frames, `$8609`=1 at +8, entities placed at (24,168) at +17, active at +19
  (measured `afterctrl48`+'1' vs `afterctrl`+'1', identical frames).
- 48K/128K: **NOT decided by BANKM.** The front end's `$FAC3` is a TIMING PROBE (see the M6
  section); the 48K branch has NO music and no sound engine, its SFX are inline `OUT ($FE)`
  sites in the game code. `$9AE7` (the BANKM copy made by `$95F5`) is only the paging VALUE the
  128K branch ORs with 1 for `$7FFD`.

## Render model (M4) -- framebuffer with a clean-background shadow

- There is NO background scenery: the playfield is BLACK except for the red/white striped
  platform ledges and border. The game keeps a clean copy of that PLATFORM LAYER in a shadow
  buffer at **`$E000-$F7FF`** (the byte behind display address D is at `D + $A000`), restores
  it under each sprite it moves (a per-entity erase inside the ISR draw pass `$A3AD` -- NOT a
  whole-screen copy per frame, see Clock), and composites the sprites on top -- the
  classic "restore the clean layer under the moving sprites" technique, NOT a decorative layer.
- `$8216` is the FULL restore -- called only by the round builder (`$7F4E`) and the playfield REPAINT
  routine `$8C28` (= `$8216` + attrs rows 2-23 from the colour shadow `$F840`, colours `$8309`/`$830A` by
  bit 5; used at the end of the yellow-cross storm and by the lightning code); 0 entries in 4 measured idle frames (2026-09-09): 22 char rows (rows 2-23; the HUD rows 0-1 are
  left alone), 8 pixel rows each, `LDIR` 32 bytes from `$A000+rowaddr` to `rowaddr`, the row
  start addresses taken from a pointer table at **`$FD04`** (`$4040,$4060,...,$4800,...`).
- Sprites: MASKED blitter `$A651` `LD A,(HL) / AND E / OR D / LD (HL),A` -> sprite assets are
  two interleaved streams (mask, data). No collision-by-(visible)screen.
- **The platform PALETTE changes EVERY level** (confirmed by a player who knows the original;
  round 1's red is only round 1). Colour is a per-round ATTRIBUTE layer: a shadow colour
  buffer at `$F800-$FAFF` copied to the display attrs `$5800-$5AFF` by the builder's LDIR at
  `$8245` (values seen: `$47` empty, `$57` red platforms, `$07`; round 1). The stripe PATTERN
  (not colour) is a per-VERTICAL-REGION patch of the tile bytes `$856D/$856F/$8571` -- `$824A` (top)
  / `$82C5` (bottom) at the `CP $16` row threshold -- IDENTICAL every round (N24: not per-round).
  Sprites are bright-white `$47`; HUD dim green/red/cyan; BRIGHT used, FLASH never.
- **The palette CYCLES with period 15** (rounds 16-19 repeat 1-4). 15 distinct platform
  attributes, all BRIGHT (measured live, `tools/extract_round_colours.py`):
  ```
  r : attr ink/paper        r : attr ink/paper
   1  $57 white/red          9  $56 yellow/red
   2  $55 cyan/red          10  $5C green/magenta
   3  $4C green/blue        11  $4F white/blue
   4  $4D cyan/blue         12  $5D cyan/magenta
   5  $66 yellow/green      13  $5F white/magenta
   6  $5E yellow/magenta    14  $4F white/blue
   7  $65 cyan/green        15  $54 green/red
   8  $4E yellow/blue      (16 = 1, cycle repeats)
  ```
  The colour is COMPUTED, NOT a stored attr sequence. **FORMULA (RESOLVED 2026-09-08, N24):**
  `attr = (table[idx] & $3F) | $40`, where `table` is the 15-byte `$858C` =
  `[17 95 8C 8D A6 9E A5 8E 96 9C 0F 9D 9F 8F 94]` and `idx` is a free-running BUILD counter (the
  self-mod operand `$82D7`, reset to 0 at new-game `$9701`, `+1` per platform build, wraps at 15) --
  which equals `(round-1) mod 15` in normal sequential play. Computed at `$82D6` (from `$7F62`
  @`$7F65`); the full attr is assembled at `$830A`, and the field cells get `attr & $47` at `$8309`
  written to `$F840-$FAFF`. VERIFIED: the formula reproduces all recorded round attrs
  (`build/round_palettes.json`, **0/19 mismatches**). Sprites remain bright-white; HUD dim; FLASH never.
- **Extraction (done)**: `tools/extract_round_colours.py` drives the game round by round
  (deactivating the enemy slots `$FD94-$FDD9` makes it clear and build the next round with
  its real colour), capturing each as the shadow bitmap + display attributes. build/rounds/
  colourNN.png + contact_colour.png + build/round_palettes.json.

## The round system (M5) -- THE KEYSTONE

- **Round counter: `$8609`** (1-based; = 1 in round 1). Incremented at new-round setup
  (`$97F8`/`$9800`: `LD A,($8609) / INC A / LD ($8609),A`). New-round setup `$97C7` also inits
  both players' extended fields (`(IY+$5B..$60)` at `$FD80`/`$FD8A`).
- **Round data base: `$61A8`** (the address the loader's unused developer-load path also named).
  Records are VARIABLE LENGTH, walked sequentially and selected by the round counter (`$848C`):
  ```
  $848C XOR A / LD ($8528),A        ; index = 0
  $8490 LD HL,$61A8                 ; base
  $8496 CALL $8529 -> carry         ; this round's size flag
  $849D LD DE,$27 (39) / JR c / LD DE,$4D (77) / ADD HL,DE   ; advance
  $84A9 LD A,($8609) / DEC A / CP ($8528)  ; reached target round?  else INC ($8528), loop
  ```
- **Record size = 39 or 77 bytes**, chosen by a 1-bit-per-round flag bitmap at **`$8543`**
  (`$8529`: bit `7-(round&7)` of `$8543 + (round>>3)`, MSB-first via `RL C`). Round 1 = 39
  bytes at `$61A8`: `fffc00..031ff0..031ff0..03ffff`. The 77-byte size equals 28x22 bits
  exactly, but that is a COINCIDENCE -- the record is NOT a raw bitmap (see the builder).
- **Builder `$824A`** (NOT `$8260`: `$825E` is `3A 09 83 LD A,($8309)` and `$8260` is that
  instruction's third byte -- there is no routine there, and this line said `$8260` until
  M7.8-A disassembled it) walks 22 rows (`$FD44` shadow row-pointer table: `$E040,$E060,...`) x 28
  columns (`LD C,$1C`), and PER ROW reads map bytes and does `LD A,(HL) / CP C` against the
  down-counting column index with `DJNZ`/`ADD HL,DE` skips -- a per-row SEGMENT / column-list
  encoding (fills platform runs), NOT one bit per cell. Where a segment is present it draws the
  8-byte platform tile at `$856C` (masked `LD A,(DE)/LD (HL),A/INC DE/LD A,(DE)/OR (HL)/LD (HL),A`)
  into the shadow at `$E000-$F7FF`; `$82C5` re-patches the tile bytes (`$856D/$856F/$8571`) at a
  row threshold (the platform look changes down the screen). `$AA4A` clears the shadow first.
  PROVISIONAL: the exact segment scheme is not fully decoded; do not trust a hand bitmap.
- **Extraction plan (Q7 live path, avoids decoding the pack)**: poke `$8609` to each round,
  run the round-build (walker `$848C` -> builder `$8260`), and dump the rendered shadow
  `$E000-$F7FF` = that round's platforms. Cross-check a few against a decode of `$61A8` once the
  segment scheme is read. The round COUNT comes from the game's `$8609` cap (near `$50`-`$52`).
- **ROUND COUNT = 81** (measured, `tools/extract_rounds.py`): rounds 1-81 render as clean,
  distinct levels (the real BB layouts: BUBBLE, POPCORN, SOS, the skull, ...); round 82+
  is garbage (the walker reads past the data; cell count jumps from ~2500-4000 to >4400).
  Round 81 is special-cased at `$7F83 CP $51 / RET z` (its number is not drawn) -- the boss.
  So the Spectrum port has 80 numbered rounds + a boss, NOT the arcade's 100.
- **EXTRACTION (done, live path)**: `tools/extract_rounds.py` reloads a live state, pokes
  `$8609`=round, CALLs the round-background builder **`$7F62`** (walker `$848C` -> tile
  drawer `$824A`/`$8260`), and dumps the rendered shadow `$E000-$F7FF` = that round's platforms (the constant outer border walls are drawn separately, so the extract is the
  per-round content in isolation). Contact sheet + per-round PNGs in build/rounds/.
- OPEN: the exact packed segment scheme at `$61A8` (only needed to ship the data as bytes rather
  than as rendered backgrounds); the boss round 81's own layout/behaviour. (Per-round platform
  COLOUR is now RESOLVED -- the `attr = (table[$858C+idx] & $3F) | $40` formula, see the render
  model, N24.)

## Entities (M5) -- struct, type dispatch, frame architecture

- **Entity table base `$FD80`, 12 slots x 10-byte stride** (`$8F00`: `LD IX,$FD80 / LD DE,10 /
  LD B,12`). Measured live (round1, 1P): slot 0 = P1 (Bub), slot 1 = P2 (Bob, inactive in 1P:
  flag bit 7 = 0), slots 2-8 = enemies (round 1 had 3, all type A). **Slots 9/10/11 (RESOLVED
  2026-09-08, N4):** slot 9 = `$FDDA` = P1's persistent state record (`IY+$5A`; confirmed by
  `$AD0C RES 4,(IY+$5A)` writing `$FDDA`), slot 10 = `$FDE4` = P2's (`IY+$5A`). Their `+0/+1` hold
  `[control byte, $02]`, NOT a sprite pointer (that is why the "ptr" looked like `$0200/$0201`), and
  `+7` bit7 is clear so they are not drawn. Slot 11 = `$FDEE` = the lightning-bolt / Boris object
  slot (zero in round1).
- **Struct fields (measured live + read from the update code `$B028`/`$B061`/`$B26F`)**:
  ```
  +0,+1  sprite pointer (LE) -- the blitter reads this (IY+0/1); the per-type routine sets it
  +2,+3  PREVIOUS-TICK draw position (+2 = prev Y, +3 = prev X) -- the erase position the $A600
         blitter WRITES ($A603,$A623) and re-reads next frame; +3/+2 copy +5/+6 one tick later
         (N5: walking right, +5 leads +3 by a tick; jumping, +2 trails +6)
  +4     animation counter (INC (IY+4) at $B061)
  +5     X pixel        (RIGHT raises; collision temp via $B26F -> $B579)
  +6     Y pixel        (ADD $11 for a below-point probe at $B064; clamp $C8/$DC/$BE at $B29F)
  +7     flags: bit7 active, bit0 facing (+$160 sprite / frame toggle via LD A,R $B008),
         bit4 (set when init index>=3, $7442), bit2 ($B030 doubles a step), bit1 (RES at init)
  +8     move/pause timer (DEC (IY+8) $B03A; at 0 -> movement/turn)
  +9     state (0 -> walk/move branch $B061; nonzero -> $B0F7 special/falling)
  ```
- **Type dispatch: jump table `$73B0` (8 entries), read by the spawner `$7325`.** Each type
  initialiser does `LD BC,<behaviour/draw routine> / LD HL,<sprite bank>` then the common tail
  `$741D`, which stores BC into a parallel BEHAVIOUR-POINTER list via `(IX+0/1)` + `INC IX x2`
  (seen live at `$B552`: 3x `$AF31` for round 1's three type-A enemies) and the sprite ptr into
  `(IY+0/1)`, baking the facing into +7 and adding `$160` to the bank if bit0 set (`$7447`).
  **The 8 entity types -> (behaviour routine, sprite bank):**
  ```
  type 0  $AF31  $C100 (+ runtime mirror $5B80)   basic walker (enemy A)   [3x in round 1]
  type 1  $AF47  $D040
  type 2  $AF95  $CD80          (init A=3)
  type 3  $AFAF  $C260          (init A=3, DE=0)   -- NEVER FLIPS: spawn $73EB sets DE=0 so the
                                                     facing-bake $744A is a no-op; draw $AFAF loads
                                                     $C260 unconditionally (no +$160, no $5B80
                                                     mirror). Uses the 2D mover $B26F, not $B028. (N16)
  type 4  $AF77  $C3C0
  type 5  $AF5F  $CAC0
  type 6  $AFF6  $D500
  type 7  $AFC4  $C680          (init DE=0)         -- NEVER FLIPS, same as type 3 (symmetric). (N16)
  ```
  The 8 behaviour routines are the per-frame UPDATE (`$AF31-$B021`, animate + move + set sprite
  ptr); a separate DRAW pass calls the master blitter `$A447`->`$A600` per active slot. So a
  frame is: update pass (call each entity's stored routine with IY=slot) then draw pass.
- **P1 fields (round1 diffs)**: X `$FD83`? -- NOTE the earlier provisional "X `$FD83`" was the
  +3 byte, now identified as an X/coordinate backup; the authoritative X is +5, Y is +6 (see the
  live slot dump and the update code). Per-entity 5-word scratch `$96D1-$96DA` via the SP-parked
  fast-pointer idiom (POP/RET/EX (SP),HL; manual 3.10).
- RNG (CORRECTED 2026-09-10, docs/RNG.md): `$FEBB`/`$FEC7` are NOT seeds -- see line 848. The
  PRNG is `$FE85` (state `$FE86/$FE87`, tape value `$002A`, never reseeded). Enemy facing
  uses `LD A,R` (`$B008`, the `CP $2A` at `$B00A`), so the visible waddle IS R-driven -- a declared substitute
  (consumption preserved) will be needed unless the port reproduces R.
- Dispatch idiom: RET-as-jump (`$93DC`, `$AAE5`) -- stackscan reports these as fake returns.
- Later-round live capture DONE 2026-09-09 (see the per-type movement census in the Enemy AI section);
  which types are which BB creatures is only naming (the sprite banks decide). Still OPEN (low): how
  `$7325` gets the type index (from the round record at `$61A8`?). (Slots 9-11 and the +2/+3-vs-+5/+6 relationship
  are now resolved -- see above, N4/N5.)

## Sprites (M5) -- 16x16 masked, stack-blitted (VERIFIED format)

- **Blitter family** in `$A400-$A9FF` (multiple sizes/clip variants; each parks SP at the
  sprite pointer with `LD SP,HL` and POPs the source). The MASTER entity draw is `$A447`,
  entered from FIVE sites (static grep, CORRECTED M7.49): the pass `$A402`; `$BF16`'s `$BF28`,
  the capture's `$BE92` and `$8C51`'s `$8C56`, all three with `$A5D9` patched to RET, so ERASE
  ONLY; and Boris's `$91D6`.  It falls through to the 16-wide stack
  blitter at **`$A600`**. That blitter: reads X=`(IY+5)`, Y=`(IY+6)`, flags=`(IY+7)`, the
  sprite pointer from **`(IY+0/1)`**, adds 8 to the beam accumulator (`$A616 CALL $A430`;
  `$A430` is `ADD A,n / LD ($A431),A / RET nc / RET`, the BEAM ADD of `$A3AD`, NOT an address
  computation -- the screen row comes from the `$FD00` table at `$A630`), then
  `$A61F LD SP,HL` parks the stack at the sprite and the inner loop `$A652` does
  `LD A,(HL) / AND E / OR D / LD (HL),A` -- E=mask, D=data, popped as pairs.
- **Sprite format (VERIFIED by instrumenting one blit -- logging each POP source address
  against each screen write, `tools/extract_sprites.py`)**: a frame is **64 contiguous
  bytes = 16 rows x 4 bytes**, each row `[mask_L, data_L, mask_R, data_R]` (mask before
  data, left byte-column before right). Composite is `screen = (screen AND mask) OR data`,
  so a pixel is **INK where data=1, BLACK where data=0 & mask=0, TRANSPARENT where
  data=0 & mask=1**. Width is 2 bytes (16px); an unaligned X is shifted IN CODE (the
  `$A60F AND 6 / JP nz,$A6F3` alignment branch), so a sprite pointer names ONE unshifted
  master, not a pre-shifted copy. Sprites are monochrome; colour is the per-round attribute
  layer (SPEC render model), so BRIGHT-white ink.
- **Per-type draw routines `$AF31-$B021`** (8 of them; the ~8 entity classes). Each sets its
  sprite bank base into `(IY+0/1)`; the opposite horizontal facing is at **base+`$160`** for
  routines that add it (`$AF2C LD DE,$160 / ADD HL,DE`, called `CALL z,$AF2C` on `(IY+7)`
  bit 0), but NOT universal -- some are symmetric or runtime-mirrored. Enemy A's left facing
  is GENERATED at runtime into low RAM **`$5B80`** (so `build/image.bin` holds stale bytes
  there; the live capture is the truth). Animation for the basic enemy is the two facings
  toggled (`$B008` uses `LD A,R` to flip `(IY+7)` bit 0).
- **Roster (verified frames, `tools/extract_sprites.py`; base addresses read from the draw
  routines, live frames captured from the harness)**:
  ```
  $C100 + $5B80(runtime mirror)   enemy A (basic walker; 2 facings)     [draw $AF31]
  $C260   enemy type 3 (symmetric, no facing branch; NOT the bubble -- see Bubbles)  [draw $AFBA]
  $C3C0 (+$160 $C520)             enemy (eyes+legs)                     [draw $AF7E]
  $C680                           enemy (symmetric/horned)              [draw $AFEC]
  $CAC0 (+$160 $CC20)             enemy                                 [draw $AF6A]
  $CD80 (+$160 $CEE0)             enemy                                 [draw $AF9E]
  $D040 (+$160 $D1A0)             enemy                                 [draw $AF52]
  $D500 (+$160 $D660)             enemy (legs)                          [draw $B018]
  $D7C0 + $D920(=+$160)           PLAYER (Bub/Bob; 2 facings)           [player draw]
  $C6C0, $D300                    round-1 live extras (items/effects?)  OPEN
  ```
- **Extraction (done)**: `tools/extract_sprites.py` unions the LIVE working set (hook `$A600`
  across every saved state, capture the distinct pointers the game draws, reading the 64
  source bytes from LIVE memory so low-RAM frames are correct) with the STATIC bases in the
  stable `$C000+` data region. Decodes with the verified format; writes build/sprites/
  spr_XXXX.png (x4) + contact.png + **build/sprites.json** (`{hexaddr:{addr,w,h,mask,bytes
  b64,source,seen,label}}`).
- Enemy roster: RESOLVED 2026-09-09 -- build/enemies.json holds every round's spawns and the banks of
  all 8 types were blitted live from harness-built rounds 6/10/20/30/40/50/60 (SPRITE-COVERAGE
  "Later-round enemy banks, LIVE"). OPEN: the other blitters ($A824 from `$8D46`, $A84D from `$8F26`, $A9ED from `$8D2E`, and
  the front-end text/HUD path -- title/attract draw NO $A600 blits) and their sizes; items,
  EXTEND letters, the boss, the whale; the exact per-frame animation index source.

## Enemy spawn table (M5) -- $7491, 16 bytes/round (VERIFIED + shipped as data)

- The spawner `$72A5` reads the round `($8609)`; **`CP $50`** -> rounds >= 80 (round 80, and
  the boss 81) branch to the boss setup `$79A2`; otherwise **`HL = $7491 + round*16`** (round
  1-based). It walks up to 7 enemies (`$72B3 LD B,7`), each **2 bytes**, stopping at X==0:
  ```
  byte0 = (X & $F8) | (type & 7)     ; type -> jump table $73B0 -> initialiser (SPEC Entities)
  byte1 = (Y & $F8) | (facing & 7)   ; low 3 bits seed the initial facing (correlates with X)
  ```
  Spawn loop `$72F0`: X -> (IY+5), Y -> (IY+6), sets (IY+7) bit7 active, `IX=$B552` builds the
  behaviour-pointer list, `JP (HL)` through `$73B0[type]` to the initialiser.
- **Decoded and validated (`tools/extract_enemies.py` -> build/enemies.json)**: 513 enemies
  across rounds 1-79; per-round count 3 (round 1) then mostly 7. All 8 types used, each
  introduced at a clean milestone round -- the staged roster BB is known for:
  ```
  type  bank   first round   (provisional BB identity)
   0   $C100        1         basic walker (Zen-Chan-like)   3x in round 1
   1   $D040        6
   2   $CD80       10
   3   $C260       20         (the symmetric $C260 frame)
   4   $C3C0       30
   6   $D500       40
   5   $CAC0       50
   7   $C680       60
  ```
  Self-check: round 1 = 3x type 0 (matches the live round-1 slots drawing $C100); every
  decoded type in 0-7. Mutation-tested (round*16 -> (round-1)*16 shifts to the $7491 dummy ->
  round-1 assert fails). BB creature NAMES are provisional (order/identity of the Spectrum
  roster not yet cross-referenced); the type/bank/first-round facts are measured.
- **RESOLVED 2026-09-08 (N14):** rounds >= 80 (`$72A0 CP $50 / JP nc,$79A2`) spawn NO regular
  enemies -- they divert to the boss setup `$79A2`, which seeds the boss HP (`LD A,$0A / RLCA` =
  `$14` = 20 -> `LD ($9F62),A`; later overwritten to 42 by `$98AD` -- 42-wins, per Boss (d)). The
  per-slot `(IX+$10)` (stored at `$730E LD (IX+$10),A`, `IX=$B552`) = `byte0 & 7` = the enemy TYPE
  0-7, also the `$73B0` dispatch index. Facing/behaviour wiring: `byte1 AND 3` (`$7432 E6 03`) then
  `OR $80` -> `(IY+7)` (`$7444 FD 77 07`): **bit0 = facing** (type0 -> `$C100`/`$5B80`), **bit1 =
  behaviour**, **bit7 = ACTIVE**. So the facing LOW BIT does determine initial direction (bit0
  alone; bit1 is a separate behaviour bit). (This is a stale duplicate of Boss (d)'s HP paragraph.)

## Enemy AI (M5) -- the shared walker (type 0 measured; all 8 types share it)

Each type's per-frame routine (`$AF31-$B021`, stored in the behaviour list and called in the
update pass) is thin: it conditionally calls the SHARED walker **`$B028`** (gated on an
`(IY+7)` bit, e.g. `$AF47 BIT 1,(IY+7) / CALL z,$B028`) then sets the sprite pointer. So the
enemy AI is one routine with per-type parameters -- the engine can be one walker + a param table.

**Walker `$B028` per frame** (measured live on round-1 type 0, `$FD94`, and read from code):
- `(IY+4)` anim counter `INC`'d every frame (`$B061`); free-running 0..255.
- **Movement divider** (`$B09B`/`$B0A5`): move only when `(IY+4)` vs `($B60F)` passes; `$B60F`=**22**
  (`$B028`: `LD A,$16`, doubled to `$2C` when `(IY+7)` bit 2 set -> faster/angry). Horizontal STEP
  = `($B610)` = **2** px. Net ~1 px/frame (measured: X 96->40 over 56 frames, then patrol).
- **Floor/wall probe `$B47B`/`$B47E`** (D=Y, E=X): `$AED1` makes the shadow-platform address from
  (X,Y); it ORs 2 or 3 bytes across the footprint (`(IY+5) AND 6` picks 2/3 by sub-char shift),
  tests bit **`$20`** at the foot row and one row up (`+$FFE0`), and returns `B` = 2 flags
  (bit0 floor-below, bit1 wall/head-ahead). It reads the clean PLATFORM LAYER in the shadow
  buffer `$E000+`, not the display.
- **`$B087` is `3E 00` -- `LD A,n` -- and `$B088` IS ITS IMMEDIATE OPERAND** (MEASURED 2026-09-16).
  The same byte is read a second time by `$B09B`'s `LD A,($B088)` and a third by `$B0ED`. One byte,
  three readers, and the first is invisible to any scan for absolute operands because it is not an
  `LD A,(nn)` at all. So patching it -- which type 7 does at `$AFD4` before every call -- does more
  than skip the movement divider: a FALLING enemy then runs `$B08B-$B09A` and **turns to face the
  player** (`LD A,($B612)` / `CP (IY+5)` / `SET 0,(IY+7)` / `RET nc` / `RES 0,(IY+7)`, so the
  facing bit is SET first and RESet only when the player is to the left -- the incoming facing is
  overridden either way). MEASURED with the enemy at X = `$60`: tracked player X `$20` leaves flags
  `$80`, `$F0` leaves `$81`, whichever way it was facing. The `$B0ED` read is provably dead
  (reached in 0 of 48 calls with the byte set, 12 of 48 with it clear).
- **Decision** (`$B070`): floor-below & no wall -> step horizontally in the facing direction
  (`(IY+7)` bit 0: 0=left,1=right); a wall ahead -> FLIP facing (`$B1DC LD A,(IY+7)/XOR 1/LD
  (IY+7),A`); no floor (platform edge) -> FALL `(IY+6) += 2` (`$B079`, `AND $FE`). This is
  deterministic edge-following: measured round-1 enemy walked left, fell off the ledge at X=40
  (Y 72->168 straight down), patrolled the bottom floor, and flipped E0->E1 at the left wall X=16.
- **RNG is minor**: `$B0D5 LD A,R / CP $2A` (**1/128** -- CORRECTED 2026-09-10: there is no `LD R,A`
  anywhere in the image or ROM, so R bit 7 is never set and `LD A,R` yields 0..127, not 0..255;
  measured 129 hits in 14,776 draws. docs/RNG.md) -> pause 12 frames (`(IY+8)=12` at `$B0F2`);
  `$B04A` flips facing at the pause-timer values 11 and 5. The core patrol needs NO RNG (good for
  the port: reproduce R only for the occasional hesitation, or a declared substitute).
- **THE ROUND ADVANCE `$97F8`** (TRANSLITERATED AND GATED 2026-09-16, head only: `$97F8..$9857`).
  - `$97F8` `($8609)++`, and if that reaches `$52` -- past round 81 -- the round becomes `($FEC7)`;
  - `$9809` the LOOKAHEAD is `($8609) + 1`, and if THAT would be `$52` it is drawn from
    `$9811 LD A,R / AND $1F / ADD $1E`, i.e. 30..61. That is the RETURN_ROUND RNG site, carried
    since M5 marked "never observed executing" -- it executes here;
  - `$9817` stores the lookahead at `$FEC7`, and `$981A`/`$981E`/`$9822` test THAT against 21, 41
    and 61. CORRECTION: SPEC said the milestone fires "advancing INTO round 21/41/61"; it fires
    when the LOOKAHEAD is 21/41/61, so `($8609)` is 20/40/60. One fact, two descriptions;
  - at a milestone BOTH players gain a life (`(IX+$5C)` and `(IX+$66)` from `$FD80`, i.e. `$FDDC`
    and `$FDE6`), and then **THE WARP**: `$9830` takes the first player whose `+$5A` bit 7 is
    CLEAR, P1 before P2; if BOTH are set nothing happens; otherwise, if that player is ALIVE
    (`+7` bit 7), `($8609)` becomes `$51` -- round 81, skipping the rest of the game. MEASURED as
    a sixteen-row truth table;
  - `$984B` walks the `$9AC1` table and zeroes all NINETEEN bytes it names, among them `$FEC4` and
    `$FEC5` -- BOTH ISR pass gates -- so the entire level build runs dark, plus `$8E3B` (the
    clear-pending latch), `$90AA` (the anger latch), `$FECA` (the alive count) and `$FED1` (the
    level-skip item).
- **THE LEVEL-CLEAR DECISION `$8E3A`** (TRANSLITERATED AND GATED 2026-09-16). The main loop asks
  `$8D5E CALL $8E3A / $8D61 JR z,$8D09`, so the answer is the **Z FLAG**. CORRECTION: SPEC said
  "`$FEC9` wrapping to 0 = level cleared"; `$FEC9` is the GAME-OVER latch (`$8D0D`/`$8D10`) and has
  nothing to do with this.
  - `$8E3A LD A,0 / OR A / JP nz,$8F29` -- `$8E3B` is that `LD`'s own OPERAND, the clear-pending
    LATCH, so once a round is cleared the tally is skipped ever after;
  - `$8E40` a non-zero `$FED1` hands the advance to `$8F36`, the level-skip item's own routine;
  - `$8E47` round `$50` replaces the tally with the boss's HP at `$9F62`;
  - `$8EAA` the TALLY: count `+7` **BIT 7** (via `RLCA / AND 1`) over `($AA57) - 2` slots from
    `$FD9B`, publish at `$FECA`. The loop is a `DJNZ`, so `($AA57) = 2` gives B = 0 and walks
    **256 slots**, 2,560 bytes past the table -- MEASURED `$FECA` = 86/87/88. Unreachable in play;
  - `$8EC5` zero alive -> `$8ECF`, the one-shot cleanup, which FALLS THROUGH into the countdown.
    `$8F00 LD IX,$FD80` is DEAD (overwritten by `$8F04`), so it wipes the twelve BUBBLE slots and
    not the entity table: `+9` to 0 and `+4` to `$7F`;
  - `$8EC7` two or more alive -> `RET NZ`;  `$8EC9` exactly one -> `CALL $90A9`, the ONE-LEFT
    ANGER (wired M7.50, `angerPass()` -- see the section below);
  - `$8F29` the COUNTDOWN is a **WINDOW**: `($8DBE)` must be EXACTLY 1 and `($8DBD)` at least
    `$77`, so a round advances between `$0177` and `$01FF` and never again. MEASURED at every
    edge: `$0176` no, `$0177` yes, `$01FF` yes, `$0277` no.
- **THE ROUND-TRANSITION SETTLER `$B520`** (TRANSLITERATED AND GATED 2026-09-16). `$9877` arms it:
  `LD A,($8609) / DEC A / LD A,$58 / JR nz / LD A,$14`, so `($B54B)` = 88 ticks, or 20 on round 1,
  and the SAME value goes to `$FEC4`. `$AA6E LD A,($B54B) / OR A / $AA72 JP nz,$B520` then diverts
  the whole entity pass -- and the jump lands PAST `$AA81 LD IY,$FD80`, so slot 0 is never reached
  and **both PLAYERS are abandoned with the enemies**. MEASURED: with a movement key held, P1
  walks in a control window at `$B54B` = 0 and does not move at all in the armed one.
  The prologue runs FIRST: `$FEC6` and the `$AA65` cadence are ticked before the divert.
  It ticks on the ODD ISR only (that is the branch `$AA60` lives on), so 88 ticks is **176 video
  frames** -- measured exactly. Per enemy, from slot 2 for `($AA57) - 2` slots: compare `(IY+6)`
  with `($73A6 + i)`, and if they differ `INC` and compare AGAIN, and only then `INC` a second
  time. So an enemy one pixel short moves ONE pixel. Both INCs are eight-bit and there is no
  clamp, so an enemy BELOW its target walks up through 255 rather than settling -- unreachable in
  play, because `$7336` zeroes every Y and every target is `byte1 AND $F8`.
- **`$AED1` ABOVE THE HUD is NOT "no cell"** (MEASURED 2026-09-15, `tools/walker.py` synth block).
  `$AED2 CP $18 / JP nc,$AEDC` -- below Y=`$18` it takes `$AED7 LD HL,$712F / XOR A / RET`. The
  `XOR A` is a Z flag meaning "not solid", and only the WALL test (`$B1D7`/`$B228`, which branches
  on Z) reads it. `$B47B` and the ledge look-ahead IGNORE Z and DEREFERENCE HL, so they read
  `$712E-$7131` (foot, after `INC L`/`INC L` or `DEC L`) and `$710F-$7111` one char row up
  (`LD HL,$FFE0 / ADD HL,DE`). Those bytes are STATIC DATA the game never writes -- byte-identical
  in `build/image.bin` and in the title, play1p, round1_48, hurryup, elwater and boss states --
  and they are NOT uniform: `$712F`/`$7130`/`$7131` are `$00` but **`$712E` is `$F0`, bit 5 SET**.
  So the foot probe above the HUD finds no floor and the enemy always FALLS, while a LEFTWARD
  look-ahead there would read a FLOOR -- unreachable, because the fall comes first.
  (CORRECTED 2026-09-15: this said the boot image held `$E4` at `$712F` and the answer was
  per-round. That came from indexing the 64K `build/image.bin` as if it began at `$4000` -- see
  TRAPS #41. The behaviour below was measured by POKING the bytes, so it is unchanged.)
  Poked both ways and confirmed: `$712F` bit 5 set -> the enemy does NOT fall and walks;
  `$710F` set -> it falls; `$7131`/`$712E` set -> the look-ahead sees a floor and it steps
  instead of hopping. The three-row search from there goes `$712F` -> `$710F` -> `$70EF`.
- **The eight handlers are FOUR shapes** (each called directly, 32 calls, 2026-09-15):
  - type 0 `$AF31` `CALL $B028` UNCONDITIONAL -- it walks even with bit 1 of `(IY+7)` set;
  - types 1 `$AF47` and 5 `$AF5F` `BIT 1,(IY+7) / CALL z,$B028` -- with the bit set they do
    nothing but re-set the sprite. The spawner clears the bit (`$7455 RES 1`), so NO capture of a
    running round distinguishes these two shapes; only a direct call with the bit set does;
  - types 2 `$AF95` and 3 `$AFAF` use the 2-D FLYER `$B26F`, not the walker at all. CORRECTED
    2026-09-15: they do NOT "clear bit 1" -- `$B2B0 LD A,($B57B) / AND 2 / JP nz,$B384` reads that
    bit as the **Y DIRECTION** (0 up, 1 down), silently repurposed from the walk gate types 1 and 5
    use. What looked like clearing was a flyer meeting a floor and turning upward. Details below.
  - type 4 `$AF77` `CALL $B3C5` -- a different routine entirely (TRANSLITERATED AND GATED
    2026-09-16, 1,168 cases over six built worlds). It is a HOPPER with its own probe, its own
    horizontal move `$B4AC`, and its own arc machinery:
      * the arc CURSOR is **`(IY+8)`** -- the byte every other type uses as a pause timer --
        and `(IY+9)` is only the state, its bit 7 choosing the table;
      * grounded, `$B3D9` probes at Y+`$11`: solid above -> FALL, else floor below -> LAUNCH,
        else FALL. The fall is `Y += 2` with **no** `AND $FE` (unlike the walker's `$B079`) and
        wraps at `$C0` -> 0;
      * `$B3F8` LAUNCH: cursor = 0, `(IY+9)` = `$81`. Then `$B40B` compares the enemy's row with
        the player's -- at or above it keeps bit 7 (the SMALL arc `$B5BD`, shared with the hop);
        below it clears bit 7 (the TALL arc `$B5DD`); LEVEL, and only then, it draws from the
        `$FE85` LFSR at `$B414` and compares against **`(IY+4)`**, so the anim counter is an
        aiming PROBABILITY, not an animation index. On a low draw it faces the player.
        This is the only enemy that draws from the LFSR rather than `LD A,R`;
      * airborne `$B42D`: `$B4AC` moves across (a wall turns it round; no ledge look-ahead) and
        returns in A the NEW X after a move or the NEW FLAGS after a turn -- and `$B445`'s
        `CP $10` compares THAT, so an X below `$10` skips the landing test and a turn never can;
      * the cursor runs 0..`$20` INCLUSIVE against a 32-byte table, so the last airborne frame
        reads **ONE BYTE PAST the end**: `$B5DD + $20` = `$B5FD`, the first byte of P1's KEY
        TABLE, taken as a signed Y delta. Those tables are LIVE STATE -- the tape holds sixteen
        ZEROS here (M7.44a); round1_48 holds `$F7` (the CURSOR keys) and the port's BB_KEYTAB `$DF`
        (key O) is a capture emulator's redefine -- so which controls the player chose changes how a type-4 enemy finishes its jump;
      * landing sets `(IY+9)` = 0 with no even-alignment and no move decision; the arc ends when
        the incremented cursor reaches `$21`.
    `$AF8A`, AFTER the sprite store, forces `(IY+6)` = 0 when `(IY+6) >= $BF` -- a THIRD bottom
    wrap, different from `$B3F0`'s `$C0` and `$AB0C`'s `$C8`/`$DC`, and it runs last. It MASKS
    `$B3F0`'s constant in every case reachable through the handler, so the oracle calls `$B3C5`
    directly for that one;
  - types 6 `$AFF6` and 7 `$AFC4` do not wrap the walker, they REWRITE it (TRANSLITERATED AND
    GATED 2026-09-16, 210 direct calls over four worlds). Both poke `$C9` (RET) over `$B20D` and
    `$B25D` and zero them afterwards, so the ledge decision becomes a STEP -- the RET lands on the
    address `$B1FF`/`$B24F` pushed. Type 7 also takes `$B088`, which skips the movement divider at
    `$B09B` AND, because that byte is `$B087`'s operand, homes a FALLING enemy's facing on the
    player. Type 7 `SLA`s the step before the call and `SRL`s it back, so it moves 4 px:
      * `$AFCA`'s SLA on `$B611` is DEAD -- `$B028`'s first instruction is `($B611) = ($B610)` --
        so `$B611` comes back equal to `$B610`'s ENTRY value, not to its own. MEASURED: entry
        `(3,7)` exits `(3,3)`.
      * the `SLA`/`SRL` round trip LOSES BIT 7: entry `$80` exits `$00` and `$C0` exits `$40`.
        Safe only because `$9874` is the sole writer of `$B610` and writes 2.
    Type 6 then has a SECOND `LD A,R` at `$B008` (`CP $2A`, 1/128) that FLIPS the facing, and the
    sprite two instructions later reads the FLIPPED value, so a flip shows the same frame. It is
    drawn on EVERY type-6 call, after the walk; `BB_RNG_SITES` lists it as `ENEMY_FACE`.
    NOTE the capture must trap `$B00A` as well as `$B0D7`, or every type-6 row records
    `draws: []` while the machine drew.
  - **(type, facing) sprite table, all 8 read back from the machine** (facing = `(IY+7)` bit 0;
    `$AF2C LD DE,$0160 / ADD HL,DE` is the mirror, applied when the bit is CLEAR):
    0 `$C100`/`$5B80` (the runtime mirror copy, NOT +`$160`), 1 `$D1A0`/`$D040`,
    2 `$CEE0`/`$CD80`, 3 `$C260`/`$C260` (one bank), 4 `$C520`/`$C3C0`, 5 `$CC20`/`$CAC0`,
    6 `$D660`/`$D500`, 7 `$C680`/`$C680` (one bank).
- **The 2-D FLYER `$B26F`** (TRANSLITERATED AND GATED 2026-09-15; 2,560 cases over five whole
  worlds, plus the 32 direct handler calls). No gravity, no floor-following, no player tracking,
  no hop, and it never touches `(IY+4)` or `(IY+8)`. One step on X and one on Y per call,
  REVERSING on either axis when the leading edge of the step would enter a solid cell.
  - `(IY+7)` bit 0 = X direction, bit 1 = **Y direction** (0 up, 1 down).
  - It works in the private scratch `$B579`/`$B57A`/`$B57B` and writes X/Y/flags back. The ORDER
    is the point: vertical, **re-store Y from the entity** (`$B284`), horizontal, vertical again.
    The first vertical call's MOVE is discarded and only its direction FLIP survives, so a
    vertical reversal costs no frame -- the enemy turns and steps away in the same call. The
    re-store also hands the horizontal probe the PRE-MOVE row.
  - HORIZONTAL uses step `$B610`; VERTICAL uses `$B611`. Type 2 copies one to the other (`$AF98`),
    type 3 halves it with a single `SRL` (`$AFB2`) -- so type 3 is **2 px across and 1 px down**.
  - The two probes are NOT the same shape and must not share a helper. Horizontal walks `+$20`
    (one CHARACTER ROW, 16-bit `ADD HL,DE`) and takes a third cell when the SCRATCH Y `AND 6` is
    non-zero; vertical walks `INC HL` (one CELL, 16-bit, so column 31 carries into column 0 of the
    next row) and takes its third from the SCRATCH X. Both count from the axis they are NOT moving
    along, unlike `$B47B` which always counts from `(IY+5)`.
  - Both call **`$AEDC`** -- `$AED1`'s body WITHOUT the `CP $18` guard -- so a flyer above the HUD
    computes a real, wrapped cell instead of taking the `$712F` dummy pointer.
  - The tail `$B29C` is `$AB0C`'s Y rule with ONE CONSTANT CHANGED: off the top wraps to **`$BE`**
    here and to `$C0` there. Because it runs first and always leaves Y below `$C8`, `$AB0C`'s Y
    rule is dead for these two types, while its X rule (force even, clamp `[$10,$E0]`) is still
    the only thing clamping X -- `$B26F` writes X raw.
  - `$FC00-$FCFF` is 256 bytes of **`$FF`** between the colour shadow and the `$FD00` row table:
    every byte has bit 5 set, so a probe running off the bottom of the shadow reads SOLID. That is
    what stops a flyer at the wrap edge, and the port carries it. MEASURED: identical in the image
    and in six states, never written in 300 frames.
- **The ledge look-ahead is EIGHT-BIT and ASYMMETRIC**: `$B1F5 INC L / INC L` rightward, `$B246
  DEC L` leftward, so a foot cell at low byte `$FE`/`$FF` (or `$00` leftward) wraps INSIDE the
  256-byte page -- eight character rows away, not the next column. The floor probe `$B47B`, by
  contrast, is SIXTEEN-bit (`$B48D INC HL`). Both pinned by poking the cell the other arithmetic
  would have read to the opposite value.
- **The probe row is Y+`$11`, not Y+`$10`** -- equivalent for every EVEN Y (both stay in one
  character row) and different only when Y is odd, which the per-slot tail `$AB0C` prevents but
  the ballistic hop does not. Pinned with synthetic odd-Y cases.
- **Shared AI params** (live round 1): `$B60F`=22 speed threshold, `$B610`/`$B611`=2/2 step.
  **`$B612`/`$B613` = the player-HOMING TARGET, not floor bounds (CORRECTED 2026-09-08, R10):**
  the sole writer is `$AACB`/`$AAD0` -- `$B612` = tracked-player X+8, `$B613` = tracked-player Y
  (from `$FD85/6` P1, or `$FD8F/90` P2 when `(IY+4)` bit4 selects P2). MEASURED: poke P1 X=100 ->
  `$B612`=108. Readers: face-X `$B08B`/`$B41B`; hop-toward-row `$B0DB`/`$B1FC`/`$B24C`/`$B400`.
  The old "32/168 = floor bounds" was just P1's round-1 start position. `$B60F`-`$B611` are globals
  reloaded per active enemy.
- **The BALLISTIC HOP `$B0F7`** (TRANSLITERATED AND GATED 2026-09-15, 1296 built-world cases;
  the earlier reading below was right in outline and wrong in three details, corrected here).
  `(IY+9)` is BOTH the state and the CURSOR: `$B158 DEC C / RES 7,C` makes the index, `$B15D`/
  `$B165` pick the table by BIT 7, and `$B16B CP $11` compares the WHOLE byte, bit 7 included.
  - the two arcs are `$B59D` (bit 7 CLEAR) and `$B5BD` (bit 7 SET), 32 SIGNED bytes each. BOTH
    GO UP THEN DOWN -- "downward/upward table" was wrong. `$B59D` is the BIG arc (-4..+4, peak
    40 px up at frame 14), taken by the HOMING hop the pause wind-up starts (`$B046` sets
    `(IY+9)` = 1); `$B5BD` is the SMALL arc (-2..+2, peak 14 px up), taken by the LEDGE hop
    (`$B20F`/`$B25E` set `$81`). Each sums to ZERO, so a hop that runs its course lands at the
    height it left. They are STATIC TAPE DATA at `$B59D`/`$B5BD`, byte-identical in
    `build/image.bin` and in every saved state. (CORRECTED 2026-09-15: briefly recorded as
    relocated from `$F59D`/`$F5BD` -- the same `$4000` indexing error, TRAPS #41. There is no
    such relocation: boot `$F000-$FFFF` matches boot `$B000-$BFFF` in 95 of 4096 bytes.)
    They are the third and fourth of a contiguous family -- the player's jump arc `$B57D` (24)
    and its spill `$B595` (8) run straight into them, with a fifth following at `$B5DD`.
  - `$B0F7 JP p,$B154` -- the HORIZONTAL move belongs to the BIT 7 arc ONLY, so a homing hop
    rises and falls on the spot while a ledge hop carries the enemy sideways.
  - that move is the walker's step MINUS the ledge look-ahead, and a WALL does not turn the
    enemy round: `$B11F`/`$B145` set `(IY+9)` = 0 and RET, CANCELLING the hop with nothing moved.
  - `$B16B CP $11` gates the landing test on the FULL byte, so the small arc (`$81`..`$A0`) looks
    for a landing from its FIRST frame while the big arc (1..`$20`) only does so from frame 17 --
    which is what stops a homing hop landing straight back on the ledge it left.
  - the landing test probes `$B47B` at row `(IX) + 15 + (IY+6)`, i.e. the ARC-DISPLACED foot row,
    and lands only on `bit1 clear AND bit0 set` (nothing solid above, floor below). Landing does
    `(IY+6) AND $FE`, `(IY+9)` = 0 and then **`$B192 JP $B09B`** -- into the top of the MOVE
    DECISION, not the step, so the enemy can land and wind up again in the same frame (measured:
    45 of 486 landings ended in a 12-frame pause, 192 carried a step of their own).
  - flying on: `(IY+6) += (IX)`, then `$B1A6 AND $7F / INC A / CP $21` -- the cursor is spent at
    33 and the hop ends; otherwise bit 7 is re-attached (`OR B`).
  - the ANIM COUNTER IS NOT TICKED: `$B061 INC (IY+4)` sits after the `$B05E` branch, so a
    hopping enemy does not animate. The arc is also the ONLY thing that gives an enemy an ODD Y
    (the fall `$B079` and the landing `$B189` both `AND $FE`), which is where Y+`$10` and
    Y+`$11` stop agreeing.
- **State `(IY+9)`** (the earlier reading, kept for provenance): 0 = walk/fall; nonzero = on a
  BALLISTIC TRAJECTORY (`$B0F7`->`$B154`). The state indexes a velocity table -- `$B59D` when
  positive or `$B5BD` when bit 7 set -- reading a per-frame Y-delta `(IX)` and
  adding it to `(IY+6)`; the state's low 7 bits step 1..`$21` (33 entries) per frame. Each frame it
  also floor-probes (`$B47B`) at the arc's foot and, on landing, `AND $FE` the Y, sets `(IY+9)=0`
  and `JP $B09B` (resumes walking). **CORRECTED 2026-09-08 (R9):** this is the enemy's own HOMING
  LOCOMOTION (a hop toward the player), NOT a passive knockout bounce. It is set by the enemy AI
  itself -- `$B046` (`LD (IY+9),1`, table `$B59D`) and `$B20F`/`$B25E`/`$B3FC` (`LD (IY+9),$81`,
  table `$B5BD`) -- with the hop DIRECTION chosen from the player row/column `$B612`/`$B613` (at
  `$B400`/`$B40F`, `$B1FC`/`$B24C`). A bubble CAPTURE flags the BUBBLE (`+7` bit2), not the enemy's
  `+9`; a pop (`$B6D8`) spawns a `$5CE0` corpse and an escape (`$B679`) re-walks. (4000 idle round-1
  frames wrote only `0` to an enemy's `+9`.) The two tables `$B59D`/`$B5BD` are shippable
  trajectory DATA (extract in the bubbles/items pass).
- Self-modified patch bytes `$B088`, `$B20D`, `$B25D` (set to `$C9`/`$00` by `$AFC4`/`$AFCx`)
  switch walker sub-behaviours per type/mode (e.g. a type that cannot fall, or the sped-up angry
  state).
- **ANGRY trigger (N15, 2026-09-08; CORRECTED M7.50):** the speed-doubler (`+7` bit2: `$B030`
  doubles the walker's threshold, `$AAE6` runs the enemy's handler a second time) is SET on an
  enemy at TWO sites.  `$B69A`, inside the bubble-timeout ESCAPE `$B679`, angers that one enemy.
  `$90CF` (`CB D6`, the `(HL)` form a scan for the indexed `(IX/IY+7)` forms misses), in the walk
  `$90C1`, angers EVERY enemy slot at once.  `$90C1` is reached through `$90A9` by the FIRST
  hurry-up (`$904D` = 0 falls through `$90A1` into it; only the second jumps to Boris at `$917C`,
  angering nothing) and by the one-left call `$8EC9`, and the latch `$90AA` lets only the first of
  the two walk (M7.50; the section `$8EC9 / $90A9` below).  The respawn runs the same walk as
  RES 2 (`$ABD5` flips the opcode byte `$90D0`), calming them all.  (Other `SET 2` sites: bubbles
  `$9CB4`/`$B9CF`/`$BEEF`, players `$8868`/`$8874`/`$88A7`, and the players' status bytes
  `$FDDA`/`$FDE4` at `$9DCE`.)  So "angry/fast" == escaped a bubble, OR the first hurry-up, OR one
  enemy left.
- RESOLVED too: what sets nonzero `(IY+9)` (R9, the homing setters `$B046`/`$B20F` -- capture flags
  the bubble, not `+9`); what `$B612`/`$B613` track (R10, the player-homing target).
- Per-type behaviour: a live movement census for all 8 types now follows (2026-09-09); the per-type
  AI patch internals (`$B088/$B20D/$B25D`) remain code-read, to be diffed by the M8 tracediff.

### Live movement census per enemy type (MEASURED 2026-09-09, 48K-branch states r6/r10/r20/r30/r40/r50/r60_48)

States built by poking `$8609` to N-1 and clearing the enemy slots until the level-clear advances
(the no-death warp needed `$FDDA`/`$FDE4` bit 7 set for rounds 20/40/60 -- see Round transition).
300 frames each, per active slot the per-frame (dx,dy) histogram, facing flips and `+9` states:

| type | first round | sprite bank(s) seen live | movement seen (dx,dy per frame, most common first) | notes |
|---|---|---|---|---|
| t0 | 1 | `$C100` + mirror `$5B80` | (0,0) (0,+2 fall) (±2,0) walk; `+9` 129-133 = homing hops (r10) | the measured walker |
| t1 | 6 | `$D040` + `$D1A0` (+$160) | (±2,0) walk, (0,+2) fall; few flips | walker, same speed as t0 |
| t2 | 10 | `$CD80` + `$CEE0` (+$160) | (±2,±2) DIAGONAL flight, (0,±2); wraps (one dy=190 = top->bottom) | a flying bouncer (2D mover) |
| t3 | 20 | `$C260` only (never flips) | (±2,±1) diagonals, (0,±1) drift; 807/897 frames stationary | slow flyer |
| t4 | 30 | `$C3C0` + `$C520` (+$160) | (±2,±1), (±2,0), (0,+2); `+9`=129 for 820/1495 frames = homing hop | hops at the player a lot; 45 flips/300 f |
| t5 | 50 | `$CAC0` + `$CC20` (+$160) | (±2,0) walk, (0,+2) fall | walker |
| t6 | 40 | `$D500` + `$D660` (+$160) | (±2,0) walk, (0,+2) fall | walker |
| t7 | 60 | `$C680` only (never flips) | **(±4,0)** walk = double speed, (0,+2) fall | the fast walker |

The `+$160` facing mirror is used by t1/t2/t4/t5/t6 (and t0 via the runtime `$5B80` copy); t3 and t7
draw one bank unconditionally (N16 confirmed live). Per-type AI internals (the `$B088/$B20D/$B25D`
patches) remain code-read; this census is the behavioural ground truth to diff the engine against.

### The springs' jerk: the odd interrupt overruns the frame (MEASURED 2026-10-16, the owner's playtest finding)

The owner (2026-10-16): "The spring enemies bouncing is jerky after the player moves.  If the player hasn't moved the
enemy motion is as it should be."  The spring is TYPE 4 (`$C3C0`: a head on a coil; round 30 has seven).  MEASURED on
the real machines (the harness: the 48K from the real load, round 30 entered at the end of ISR 1000 by `($8609)` = 29,
`($FECD)` = 1 -- the umbrella's skip, one build; tools/harness128.py: the 128K from the M10 recon's round-1 state;
scripts in scratchpad/spring/, NOT YET a tools/ oracle):
- **The mechanism.**  The ODD interrupt draws every sprite (`$A3AD`) and then moves them (`$AA60`); in round 30 it
  runs 57,000..78,000 T.  One that runs past the frame (69,888 T; 70,908 on the 128K) makes the machine MISS the next
  interrupt: the parity (`$8DBD` bit 0) then shifts by one, and every sprite's 25 Hz update comes 3 frames after the
  last instead of 2.  That hitch is the jerk.  (An interrupt that ends a few T past the frame, inside the next one's
  window, is followed at once by the next, and nothing is lost: the engine's span rule has it.)
- **Why "after the player moves".**  P1 starts at X = 24, a multiple of 8: its draw and erase take the blitter's
  unshifted path (`$A60F AND 6`).  At an X that is not -- three positions in four once it walks -- they take the
  shifted path: **+2,332 T** on the odd interrupt (one real-48K state, only P1's X ($FD85, and $FD83) changed: X 24 /
  25 / 32 / 40 -> 38,603 T, X 26..31 / 34 / 36 / 38 -> 40,935; +2,244 and +2,631 T at two more states).  Over 12
  random key probes per machine (seeded walks, jumps and waits after 400 untouched frames): **no interrupt lost while
  P1 has not moved** (~3,600 frames per machine), 233 (48K) and 138 (128K) after it first moves -- sporadic, 1..23 a
  run, before HURRY UP.
- **HURRY UP makes it heavy, whatever P1 does.**  ~1,610 frames into the round the first hurry-up angers every enemy
  (`$90C1`, +7 bit 2: `$AAE6` runs each handler TWICE), and from then on most odd interrupts overrun: an interrupt lost
  every 3..5 frames (50..60 in the next ~230 frames on both machines, P1 untouched or not), until a death's respawn
  calms them.  With P1 never moving: 0 lost before that point (2 runs per machine).
- **The port.**  The 48K page is the machine's: from the same drive (LD A,R fed) the engine loses the interrupts the
  machine loses (frames 1670, 2092, 2185, 2222 of the walk scenario; every enemy's X / Y / +7 / +8 / +9 equal at all
  1,236 interrupt ends after the build); on the 12 probes 5 identical lost frame for lost frame and the other 7 parting
  at declared fine-timing gaps (TIMING) -- 233 lost on the machine, 212 in the engine.  **The 128K page loses 2.8x as
  many as a real 128K** (380 in 23,237 frames, 1.64%, against 138 in 23,251, 0.59%, on the same probes): the odd
  interrupt's T is the real 128K's within ~1% (the AY hook's ~500 T on both), but the page runs the 128K branch on the
  48K's 69,888-T frame (README "The 48K's clock", M10-PLAN 1.7: "within about 1%" was INFERRED -- a threshold turns a
  1.5% longer frame into 2.8x fewer losses).  A scratch page with the 128K's frame (70,908 T), its contention geometry
  (from T 14,361 on 228-T lines) and its 36-T interrupt lost 128 (0.55%), probe for probe with the real 128K.  What to
  do about it is the owner's call (next.md, 2026-10-16b / c).
- **Confirmed in an emulator** (the owner, 2026-10-16, Spectaculator, the 48K: "the emulation replicates the bizarre
  jumping behaviour").  By phase (the same runs; a burst = >= 4 losses each <= 6 frames apart): BEFORE HURRY UP, all
  after P1's first move -- real 128K 36, the 128K page 135 (3.75x), the 128K-clock scratch page 32; real 48K 121, the
  engine 99 on the machine's drive (probe 8's 6 against 23 is that drive's key convention).  With P1 walking that is a
  hitch about every 7 s on a real 128K, every 2 s on the 128K page and on a 48K.

### Bubble-pop animation frame `$CAA0` -- NOT SELECTED by any pop measured (2026-09-09)

Every pop kind driven -- empty bubble by player contact, holding bubble (enemy->corpse) by contact,
natural timeout at ~445 f, and the yellow-cross storm's bulk burst -- reads ONLY `$CA80-$CA9F`
(frame 0) through the OR-blit `$A306`/`$A30B`; `$CAA0` (frame 1) was never touched. So the pop is a
single-frame flash in all observed cases; `$CAA0`/the `$C03B` carry branch is either unused on the
48K path or belongs to a pop kind not yet triggered. Left LOW-CONFIDENCE, not a blocking item.

## Bubbles (M5) -- object pool, lifecycle (measured); capture/item OPEN

- **In-play control (cursor scheme, P1)**: 5=left, 8=right, 0=JUMP, **7=BLOW**, 2=P2 join
  (measured live from round1: key 7 puts the player into the blow animation, computed poses
  ~`$DD40`/`$DA80`). The per-control-method readers are separate; the cursor default was measured,
  not the keyboard/redefine path.
- **Bubble object pool: base `$FED8`, stride 10** (measured: a 2nd concurrent bubble lands at
  `$FEE2`). Bubbles use the SAME 10-byte struct family as entities (`$FD80`), but in their own
  pool PAST the 12 entity slots ($FD80..$FDF7). +0/1 sprite base, +3 X (travel), +4 phase/timer,
  +5 X (float), +6 Y, +7 flags, +2 anim/attr.
- **Lifecycle (measured, one blown bubble frame-by-frame)**:
  1. BLOW / TRAVEL (~14 frames): X advances +8 per step in the facing direction, Y held at the
     player's Y, phase `+4` = 2..8, flags `+7` = `$C1`.
  2. FLOAT / RISE (from ~frame 16): horizontal motion stops, **Y decreases** (~0.5 px/frame, the
     bubble rises), phase `+4` = `$15`.., flags `+7` = `$85`.
  (Later drift, wobble and auto-pop timeout not yet traced.)

### BLOW -- the player action, the spawn and the empty-bubble schedule (M7.4d-ii, MEASURED 2026-09-10)

- **Input bit**: BLOW is **bit0** of the direction bitmask `$FD88` (this read; bit4 = the previous
  read's BLOW) -- the key table's 4th entry, NOT "down" (an earlier varmap guess).
- **Blow cadence `$ACA5-$ACE2`** (in the key reader `$ABF4..$ACEB`, on the ODD ISR from `$AA60`'s
  `$AB38`, before the physics dispatch): if `+$60` (`$FDE0`, P2 `$FDEA`) is nonzero -> beeper click `OUT ($FE), FDE0*8` (ported M7.44: `blowClick`; the M6
  BEEP_BLOW emitter) and `FDE0 := (FDE0+1) & +$5F` (the rapid-fire mask `$FDDF`=7 -> 1..7 then 0 =
  the 16-frame blow interval; rapid-fire sets the mask to 3 -- and the counter steps once per
  `$AB38` RUN, so the fast walk, which runs it twice, halves the interval: M7.48); else on the BLOW **rising edge**
  (bit0 set, bit4 clear) `FDE0 := 1`.  Holding never auto-repeats; a re-press spawns only once the
  counter is back at 0 (release >= 14 frames spawns, <= 12 does not).
- **Blow routine `$BD37`** -- called from the EVEN ISR: `$B62C -> $BD2C -> $BD37` per player
  (2 calls/even frame).  Blows when `+$60 == 1` (or 2 with the fast flag `+7` bit2), not dying
  (`+$5A` bit2), debounce `+$5A` bit1 clear (skipped when the mask `+$5F == 3`); `+$5A` bit5 (fire
  mode) -> the `$9DD4` fireball instead; `+$61 == 15` -> a +50 bonus via `$80FA` (both M7.x).
  Takes the FIRST FREE pool slot (`bit7` scan from `$FEDF`, stride 10); when none is free `$BD93`
  steals the oldest (pops it via `$B6D8`).  **Spawn `$BDC1`**: `+9` = 3 if the lightning ability
  `+$5A` bit6 else 0; `+8` = 0; `+7` = (player `+7` & `$81`) | `$40` [| `$10` for P2]; `+4` = 1;
  `+5`/`+3` = player X; `+6`/`+2` = player Y; then `SET 1,+$5A` (the debounce).
- **The manager is ONE unconditional twelve-slot pass, entirely inside the EVEN-parity ISR**
  (CORRECTED 2026-09-11; this paragraph previously claimed a split across parities BY SLOT, which
  was WRONG -- see the measurement trap below and docs/M7-PROGRESS M7.5-iv(b)).  The EVEN branch
  `$8DAD` (gated `$FEC5`) jumps to `$B62C`, which calls `$BD2C` (each player's blow check `$BD37`)
  and FALLS THROUGH into `$B636`: `LD IY,$FED8 / LD A,12 / LD ($BFF7),A`, then a loop that walks
  slots **0..11 ASCENDING**, decrementing `$BFF7` from 12 to 1, unconditionally, for any pool
  occupancy.  Per slot: bit7 clear -> skip; bit2 clear (travelling) -> `$BDFE` = the `$BE07` step
  (sprite `$C780`, cache Y/X in `+2/+3`, X +- 8 by `+7` bit0, capture check `$BE5B`, wall probe
  `$BEAF`, cap test -> `$BEE8`) then `+4++` at `$BE01`; bit3 set (burst) -> `$B6C3`; else (risen)
  -> `$B836` drift, `$B9E7` draw, then the shared `$B657` age toggle.  The ODD branch `$8DA2`
  (gated `$FEC4`) runs `$A3AD` then `$AA60` over the ENTITY table at `$FD80` and touches **no
  bubble byte at all** -- measured zero pool writes on odd parity across 470 frames of scripted
  play.  `$B836` has exactly ONE caller in the whole 64K (`$B650`, inside that loop), so there is
  no second path.  The main loop services no bubble on either parity.
  CONSEQUENCES: a bubble SPAWNED by the blow check is serviced by the SAME pass (spawn, then its
  first step, in one ISR -- the old "a 2nd bubble sits at the player's X until the next frame" was
  an artefact); step and tick are consecutive instructions, so the machine never shows "moved but
  not ticked" at a frame boundary; and ASCENDING order is load-bearing once the occupancy marker
  lands, because a lower slot's fresh marker is visible to a higher slot's probe in the same pass.  The cap test compares `+4` (before
  the tick) with the owner's range `+$5E` (`$FDDE`, P2 `$FDE8` via the `$BE37-$BE49` index) -- 8
  steps of 8 px; the **transition `$BEE8`**: `+4 := 20`, `SET 2 / RES 6`, `+3 := 2`, and the
  OWNER's debounce `+$5A` bit1 cleared (this is what re-arms the next blow).
- **Rise = the drift table `$B8DB`**: `$B836` reads the colour-shadow attribute at the bubble's
  cell (`$AEDC`), indexes `(attr & $C0) >> 5` -> `(dx, dy)` pairs `[0,-1] [1,0] [0,1] [-1,0]` -- open
  air rises straight up 1 px per move; the per-round WIND lives in the BRIGHT/FLASH bits of the
  colour shadow.  Risen ageing: `+4` advances via the global toggle `$B657`, flipped once per
  risen-bubble iteration (CORRECTED 2026-09-11: the old "two risen bubbles alternate" is WRONG --
  because the toggle is SHARED and flips once per risen body, an EVEN number of risen bubbles
  returns it to its entry value every pass, so the assignment is FIXED, not alternating.  Measured
  with two risen bubbles: one stays frozen at 21 while the other climbs 21,22,23,24; with three:
  21,21,21 -> 21,22,21 -> 22,22,22 -> 22,23,22.  The holding escape and the held-enemy release sit
  BEHIND the same toggle, so which slot gets them depends on its position in the risen set) -- M7.5,
  with the timeout pop, wall bounce (`$BEAF`), capture (`$BE5B`) and bubble-bubble contact (`$B8E5`:
  two bubbles overlapping at the same X freeze each other).
- **Measurement trap**: `run_frames(1)` overshoots by up to one instruction per call and the
  window drifts LATE (~5 T/call); after ~80 calls the next frame's early-ISR bubble tick leaks into
  the current window (the frame counters, incremented late in the ISR, do not) -- capture long
  fixtures against ABSOLUTE-T boundaries (`run_until(..., stride=1, predicate=T >= t0+k*FR)`).
- **Bubble sprite bases: two static, one BUILT** (measured 2026-09-12, `tools/bubdraw.py`).
  `$C780` (EMPTY) and `$C900` (HOLDING) are STATIC TAPE DATA: all 384 bytes of each are
  byte-identical across `build/image_tape.bin`, `build/image.bin` and every current in-play state,
  and they ship as `build/bubble_sprites.json`.  `$D380` is **RUNTIME-BUILT by `$BF5B`** (one
  caller, `$94B7`) and is deliberately NOT an asset -- that is why it differs from the tape image.
  The builder: `LDIR $C780 -> $D380` (384 B), then OR the element's glyph, read through the pointer
  table `$C068 + 2*(($7E0E) - 2)`, into **rows 4-11** of shift 0 -- one source byte per row, its
  high nibble into column 0 and its low nibble into the top half of column 1 (`$BFEE` swaps the
  nibbles) -- then generate shifts 1-7 by copying the previous block and shifting each 24-bit row
  right one bit (`$BFCC` SRL/RR/RR, walking backwards through the odd rows).  Hence `$D380` is an
  EXACT pre-shift table (block *s* == block 0 >> *s*, 16/16 rows) while `$C780`/`$C900`, which are
  hand-drawn, are not -- that difference is what identifies it.  MEASURED: the transliteration
  reproduces the live `$D380` of the `elfire`/`elwater`/`ellight` states 384/384 bytes each.
  The `$7E0E` element ids run 2 = water, 3 = lightning, 4 = fire, then the EXTEND letters
  (glyphs at `$3Exx`).  (An earlier note recorded the overlay as rows 4-7, 2 bytes per row; it is
  rows 4-11, 1 byte per row.)
  LAYOUT, measured from `$B9F4-$B9FC`: **8 pre-shifted X sub-positions of 48 bytes**, offset
  `(x & 7) * 48` -- note EIGHT sub-shifts, unlike the entity sprites' four at even sub-positions.
- **SPRITE SELECTION `$B9FE-$BA1D`.**  `(IY+9)` is the bubble's KIND, not a flag:
  **0 empty, 1 holding an enemy, 2 water, 3 lightning, 4 fire** (and the EXTEND letters above).
  `kind == 0` -> `$C780`; `kind >= 2` -> `$D380`; `kind == 1` -> `$C900`, EXCEPT that a holding
  bubble whose age `(IY+4)` has reached `$E6` **flashes by alternating with `$C780`** on the global
  `$B62D` toggle (`$BA0D JR c` / `$BA13 JR nz` both go to `$C900`; only age >= `$E6` AND `$B62D`
  clear falls through to the EMPTY path).  It does NOT switch to `$D380` -- that base belongs to
  the element bubbles.  (Corrected 2026-09-12; the M7.5-vii note had this garbled and its own
  "flashing" oracle case in fact drew HOLDING.  `build/sprites_bubbles.json`, written in M5, had
  it right.)
- **DRAW `$B9E7`** -- its own blitter, and the only routine in the game that reads the CLEAN
  PLATFORM LAYER.  Callers: `$B653` (the risen path, inside the twelve-slot manager) and the tail
  calls `$BE58`/`$BEAC`, each preceded by `CALL $BF16` (the erase).  It parks SP on the sprite and
  POPs it, keeps the display pointer in one register bank and the SHADOW pointer (`display +
  $A000`, `$BA6F ADD A,$A0`) in the other, and takes separate code paths for even and odd Y
  (`$BA37` vs `$BBC3`).  THE OPERATION, per pixel row, three columns from `X >> 3`, with
  `M = ($BFF8 + (X & 7))`:

  | column | value written |
  |---|---|
  | 0 | `(disp & M)  \| (shad & ~M) \| spr` |
  | 1 | `shad \| spr` |
  | 2 | `(disp & ~M) \| (shad & M) \| spr` |

  So the two edge columns keep the DISPLAY outside the bubble's 24-pixel window and take the CLEAN
  BACKGROUND inside it; the middle column is wholly inside.  Reading the shadow rather than the
  display is why a display-only oracle cannot show the operation (see TRAPS #37).
  FOOTPRINT: **16 pixel rows starting at Y, 3 columns wide**, 51 writes to 48 addresses.  There is
  no vertical sub-shift -- the display's own pixel-row addressing carries arbitrary Y, which is why
  48 bytes is exactly 16 rows by 3.  The sprite's 48 bytes are stored in **BOUSTROPHEDON order**:
  row 0 left to right, row 1 right to left, alternating, because the routine walks L forward
  through one row and back through the next instead of reloading it.  Two rows per DJNZ iteration,
  in three blocks so the pointer can be re-fetched from the `$FD00` row table at each character-row
  boundary: even Y `8-(Y&7)`, 8, `Y&7`; odd Y the same counts but the first block holds an ODD
  number of rows, so the second starts in the reversed phase and adds 2 to its column (`$BC71`).
  TWO ROWS CARRY NO SPRITE: the prologue `$BA78` is the loop body `$BA97` with its three `OR`
  instructions REMOVED, so row 0 is a pure background restore (its three sprite bytes are POPped
  and discarded), and the tail `$BB94` re-writes the last row background-only -- that is how the
  routine erases the one-pixel trail a rising bubble leaves.
  ROW ADDRESSES come from the game's own table at **`$FD00`** (24 words, indexed `y >> 3`, with
  `y & 7` added to the HIGH byte at `$BA67`), NOT from the ULA formula.  Its first two entries are
  the sentinel **`$01FF`**, not a screen address: a draw whose rows fall in character rows 0-1
  writes into ROM and is silently DROPPED, which is what keeps a bubble drifting off the top of the
  screen from scribbling on the HUD.  Measured: a draw at Y=8 makes 27 writes, at Y=0 none at all.
  NOTE: the bubble is `$C780`, NOT `$C260` (that is enemy type 3).
- **ERASE `$BF16`** -- and it is not a bubble routine at all.  It calls the ENTITY draw master
  `$A447` with two SELF-MODIFYING PATCHES and the flags forced to `$C0`: `$A5D9` (the junction
  where `$A447`'s erase half ends and its draw half begins) is set to `$C9` RET, and `$A480`'s
  `JP nz` is made unconditional `JP`.  The effect is "run only the ERASE half".  Three callers,
  all on the TRAVELLING path: `$BE55` (each tick, then `JP $B9E7` to draw), `$BEA9` (the capture
  tail, then draw) and `$BEE8` (the travel -> rise transition, before `+3` is repurposed as the
  marker pointer).  The RISEN path has NO erase -- a risen bubble moves one pixel per frame and
  the blitter's own two sprite-less rows clean up behind it.
  It repaints the 3x16 box at the **CACHED** position (`(IY+2)` = Y, `(IY+3)` = X -- note the
  order, Y first) from the shadow, with the same composite `$B9E7` uses for its sprite-less rows:
  col 0 `(disp & M) | (shad & ~M)`, col 1 `shad`, col 2 `(disp & ~M) | (shad & M)`.  48 writes.
  TWO differences from the draw, both MEASURED: the mask comes from the ENTITY table **`$AA4F`
  indexed by `X & 6`**, not `$BFF8` by `X & 7` -- the same eight bytes, but the erase snaps to the
  entity blitter's even sub-position, so for an odd X it uses a mask one step coarser than the
  draw just used; and the boustrophedon RESTARTS FORWARD at each of the three block boundaries
  (`8-(Y&7)`, 8, `Y&7` rows), because each block re-derives its address from the row table, where
  `$B9E7` runs one unbroken zig-zag.  A cached Y >= `$C0` returns without writing (`$A464`).  The
  DISPLAY cannot show that guard -- row-table entries 24-31 hold `$0000-$00E0`, so those rows
  address ROM and the writes would be dropped anyway -- but `$A431` can (CORRECTED M7.49): the
  forced `JP` sends every call that passes `$A464` down the SHIFTED erase, whose `$A56A CALL
  $A430` adds **20** to the beam accumulator, and a call at cached Y >= `$C0` adds NOTHING
  (PK9's CACHED-Y GATE row).
- **THE RENDER MODEL: the display is maintained PER ENTITY, never repainted.**  MEASURED
  2026-09-12 on round1_48: the whole-screen platform paint `$8216` executes **ZERO** times in 20
  frames of play, and the ATTRIBUTE file is never written by the render path at all (61 writes in
  40 frames, every one from `$8017`, the HUD).  What happens instead is 272-288 display writes on
  the ODD-parity ISR frame and NONE on the even one: each entity is ERASED at its cached position
  and REDRAWN at its current one, and the draw updates the cache.  So `$8216` + the colour copy are
  ROUND-START operations, and anything else drawn into the display -- a bubble -- persists.
- **`$A447`, one entity's erase-and-draw** (IY = an `$FD80` slot, stride 10):
  bit7 of `+7` clear, or bit3 set, goes to `$A437`, which marks it done and draws nothing.  bit6
  clear means there is no cached position yet, so the erase is skipped and bit6 is SET.  A cached
  Y `>= $C0` also skips the erase (`$A464`).  The erase runs at `(+3, +2)` and takes the ALIGNED
  path `$A483` when `(+3) & 6 == 0` -- TWO columns, a plain copy from the shadow, no mask -- and
  the SHIFTED path `$A53C` otherwise -- three columns masked from `$AA4F + ((+3) & 6)`, the same
  composite `$BF16` uses.  Then bit5 is SET and `($AA5F)` decremented, so the entity counts as done
  whether or not anything is drawn.  Then the draw: `+3 := +5`, `+2 := +6`, and the 16x16 masked
  blit at `(+5, +6)`.  Each path makes its OWN `$A430` beam add -- `$A485` +7 (aligned erase),
  `$A56A` +20 (shifted erase), `$A616` +8 (aligned draw), `$A708` +11 (shifted draw) -- WHEREVER
  `$A447` is entered, so a call from outside the pass (`$BF28`, `$BE92`, `$8C56`, `$91D6`) that
  reaches an erase or a draw adds to `$A431` too (CORRECTED M7.49; the next pass's `$A3D2`
  re-seeds it, so no band sees them).
- **The invulnerability FLASH is in the renderer, not the player code** (`$A5EA-$A5FF`).  On the
  `$A3B2` toggle phase 0, and for slots 0 and 1 ONLY, bit3 of `(IY+$5A)` -- `$FDDA` / `$FDE4`, the
  player state byte -- makes `$A447` RETURN before drawing.  Because it returns before `$A603`, the
  cache is NOT updated, so the next frame still erases the old position and the player reappears
  there.  That alternation IS the flash.
- **`$A3AD` is a BEAM-CHASING SCHEDULER, not a loop over the entity table.**  It toggles `$A3B2`,
  clears bit5 on the `+7` byte of NINE slots (`$FDE1`/`$FDEB`/`$FDF5`, the +7 bytes of slots 9-11,
  are deliberately left alone -- they are inside the players' parameter blocks), sets
  `($AA58) = ($AA5F) = ($AA57)` and seeds the beam accumulator `($A431) = $B9`.  Each visit adds 1
  (`$A3D9`) and forms the window `[acc, acc + $1E)`, and adds 1 MORE after stepping IY (`$A40C`)
  -- +1 TWICE per visit (CORRECTED M7.49); if any of `(+6)`, `(+6)+$10`, `(+2)`
  or `(+2)+$10` falls inside it the entity is SKIPPED this time round -- that is the raster about
  to display those rows.  `$A42B` uses plain 8-bit compares, so a window whose top has WRAPPED is
  EMPTY and skips nothing; transcribed as measured.  Drawing adds `$A447`'s OWN `$A430` calls
  (see `$A447`): MEASURED 7 (aligned erase) or 20 (shifted erase) plus 8 (aligned draw) or 11
  (shifted draw).  After `($AA57)` slots the list is
  rewound and swept AGAIN while `($AA5F) != 0`.
  MEASURED: on round 1 nothing is ever hidden and one sweep suffices; entities at Y 170-191 (round
  1's floor is Y=168, so this is reachable) are hidden by the first window and force a re-sweep.
- **The column walk is EIGHT-BIT in BOTH blitters.**  The column offset (`$BA61`/`$A593`
  `ADD A,(HL)`) and the walk along a row (`INC L`/`DEC L`, `INC E`) are 8-bit, so a row's three
  columns WRAP INSIDE the 256-byte page: at x = 248 on a row whose low byte is `$E0`, the third
  column lands at `$..00`, not on the next page.  MEASURED (the erase oracle's right-edge case).
  The row BASE add cannot carry for any byte X (`$E0` + 31 = `$FF`), so only the column walk is
  observable.
- **TRAVEL tick order `$BE07`** (the caller `$BDFE` is `CALL $BE07` then `INC (IY+4)` at `$BE01`):
  set the sprite base `$C780`; cache Y,X into `+2,+3`; stash X at `$C001`; step X by +-8 on `+7`
  bit 0; `CALL $BE5B` (capture); `CALL $BEAF` (wall probe); THEN the cap test -- `$BE4A` reloads
  `+4`, which the wall probe may just have set to `$14`, and `JP nc,$BEE8` on reaching the owner's
  range, which RETURNS, so a transition frame draws nothing beyond the erase inside `$BEE8`.
  Finally `$BE51`/`$BE53` `DEC A / RET z` twice: a bubble's FIRST TWO TICKS neither erase nor
  draw, so a freshly blown bubble is invisible for two frames.  Only then `$BE55` erase, `$BE58`
  draw.  The cap test belongs to `$BE07`, NOT to the `$BE01` tick.
- **OPEN (all dynamic; reach by scripted play -- player adjacent to an enemy, blow, jump -- or by
  reading the `$FED8` bubble-manager collision code)**: CAPTURE (a bubble overlapping an enemy
  traps it -> the enemy's state `(IY+9)` goes nonzero = the ballistic branch `$B0F7`/`$B154`);
  POP (player contact bursts the bubble -> the trapped enemy dies -> a fruit/item on the `$B59D`/
  `$B5BD` fall arc); ITEM spawn, collection and scoring; EXTEND-letter bubbles; the special
  fire/water/lightning bubbles. Idle-play blowing did NOT intersect a patrolling enemy (20 blow
  cycles), so capture needs positioning -- the next step.

### Blowing against a wall / obstacle -- MEASURED 2026-09-09 (owner's question)

The travel step probes the platform layer ahead of the bubble (`$BEC6`-`$BED4`, mask `C` over `B`
rows of the shadow); on a solid cell (`$BED5`): if the step counter `+4` is still below 2 (the bubble
has not completed its first 8-px step) it is BURST on the spot (`$BEDC SET 3`); either way the
bubble is snapped to the cell (`$BEE0`, X from the probe scratch `$C001 & $F8`), erased/redrawn
(`$BF16`), `+4 := 20`, `SET 2` (risen), `RES 6` (not travelling), `+3 := 2`. Sweep on `round1_48`
facing the right wall (X=224 is the last standing column, bubble X clamps to 224):

| player X | gap to wall | result |
|---|---|---|
| 224 (flush) | 0 | born already burst (`+7 $8D`), erased next frame, gone at f2, no score -- the `$BEDC` path |
| 212-220 | 4-12 px | the bubble stops against the wall inside the player's CONTACT box (dx 4-12 <= 13) and the contact rule bursts it: `$85 -> $8F` at f3, gone at f6-8 |
| 208 and further | >= 16 px | the bubble stops at the wall (X=224) and RISES normally |

Left wall (X=16, facing left): identical, born burst (`$8C`), gone at f2. So the answer to "does a
bubble pop immediately against a wall" is yes when flush (travel code) and within ~6 frames from
up to 12 px away (the spikes/contact rule); from 16 px it survives.

## Bubble capture & lifecycle (M5) -- the manager, read from code

- **Bubble manager `$B636`** iterates the **12-slot** pool (`LD IY,$FED8 / LD A,12`, stride 10,
  so `$FED8-$FF3F`). Per bubble it dispatches on the flags `(IY+7)`: bit 7 = active (else skip);
  bit 2 clear -> `$BDFE` (EMPTY bubble: travel + capture-check); bit 3 set -> `$B6C3`; the
  "holding an enemy" path keys off `(IY+9)`. Each active bubble runs `CALL $B836` (move) then
  `CALL $B9E7` (draw).
- **Empty-bubble travel `$BDFE`/`$BE07`**: sets sprite base `$C780`, caches Y/X in `(IY+2/3)`,
  advances `(IY+5)` X by +-8 in the facing direction (`BIT 0,(IY+7)`), and each frame
  `CALL $BE5B` (capture check). Travel distance is capped by a per-direction table at **`$FDDE`**
  indexed by `(IY+7)` bits 3-4 (`$BE46`): when `(IY+4)` reaches the cap the bubble stops
  travelling and rises (`$BEE8`) -- the measured TRAVEL->RISE transition.
- **Capture collision `$BE5B`**: `PUSH IY / POP IX` (IX = bubble), self-modifies `$92DE`->`$C9`
  (RET) to bound a call to the SHARED collision routine **`$92C0`**, restores it, and on an
  overlap returns the hit enemy's address; the enemy SLOT INDEX is `(HL-$FD9B)/10` (`$FD94`+7 is
  slot-0's flag byte). (`$92DE` is one of the M2 Q3 self-mod sites.)
- **Holding state**: a bubble that caught an enemy carries `(IY+9)=1` (holding), `(IY+8)` = the
  captured enemy's slot index, `(IY+4)` = age/timeout.
- **Draw `$B9E7`** (stack blitter, SP parked at the sprite): picks the sprite by KIND `(IY+9)` --
  `$C780` EMPTY, `$C900` HOLDING an enemy, `$D380` the ELEMENT bubbles (kind >= 2); a holding
  bubble past age `$E6` flashes by alternating `$C900` with `$C780` on `$B62D` (NOT `$D380`; about
  to burst/escape).
- **Drift `$B836`**: the floating bubble reads the platform layer (`$AEDC`) and drifts/bounces via
  the offset table **`$B8DB`**, with `LD A,R` (`$B88D`) choosing a direction when blocked -- so
  bubble drift IS mildly RNG-driven (unlike the deterministic enemy patrol).
- **Risen bubble vs PLAYER contact `$B8E5` (M7.5-iii, MEASURED 2026-09-10):** called from the drift
  step `$B836` before the wind move, once per active non-dying player (`$B901`).  Y overlap (`$B9D4`):
  the bubble Y in `(playerY-16, playerY+8]`.  X overlap (`$B9DE`): wide `(playerX-$10, playerX+15]`,
  then a facing-tight test -- facing right `(pX-$10, pX+13]`, facing left `(pX-11, pX+15]`.  Inside the
  tight band -> **TOUCH-POP** (`$B9B6`: `+7` bits 4/3/1 set, `+4:=$14`; the next pass bursts it).  At the
  far edge, if the player is PRESSING into the bubble (`$FD88`/`$FD92` dir bit2 right / bit3 left,
  `$B94D`) -> **PUSH**: `$B952 CALL $BF0A` first caches the current position into `+3/+2` and ERASES the
  bubble there (the risen path's only erase), then X += 2*drift[B] (+-2 px, B=2 right / 6 left) clamped
  `[$11,$E0]` (`$B977`), and `$B968` forces the wind index to 8 = `(0,0)` ONLY when it is 2 (right) or 4
  (down) -- an up or left wind survives (`$B971`) and moves the bubble as well (MEASURED, popkill N3
  ISRs 464/466/482; corrected by the drift fix -- it was written "always 8").  Touching WITHOUT pressing
  in is the BOUNCE `$B984`: nothing when the wind code equals B or `$B62D` is 0; otherwise, for wind 2/6
  (the one that is not B), `$B9A7` puts C = 4/8 in the player's `+8` and `$B9AA CALL $ADAA` moves him 2 px;
  and every bounce ends `$B9AF POP AF / $B9B0 LD (IY+8),A` with A = `$FD` (the high byte of the `$FD88`
  / `$FD92` pushed at `$B991`), so a LATER slot in the same pass sees both direction bits and is PUSHED
  (MEASURED, popkill B1/B2/B6; wind = B returns at once, B7).  `$B8EA/$B8ED` load the bubble X/Y into
  C/B ONCE for both players, and `$B932/$B943 LD B,n`, the push's `$B950 LD C,A` (C = the wind code,
  B9) and the bounce's `$ADAA` clobber them before P2's `$B901`.  **`$ADAA` hands back its own BC**:
  `$ADBB LD B,2` always; a step inside the cell leaves C = `(X+15)&$F8` going right (`$AE24`) or C
  unchanged going left; a step that CROSSES a cell probes through `$AED1` into `$AEDC` (`LD B,H` with
  H = 0 ... `$AEED LD BC,$F800`), so B = `$F8`, C = 0 whether or not it is blocked (Y+15 < `$18` takes
  `$AED7` instead and leaves B = 2, C = the jump phase if it is 0..15).  MEASURED: 16,720 direct calls
  of `$ADAA`, 0 mismatches; in play, popkill B10 (crossing: P2 at Y 16 does NOT pop), B11/B12 (inside
  the cell: P2 pops at C = `$40` / C = 8).  The port had B = 2, C = 4|8 after every bounce.
- **`$BF0A` DOES NOT RETURN** (MEASURED 2026-09-16): it sets the cached position from the current
  one (`+3 := +5`, `+2 := +6`) and FALLS THROUGH into `$BF16`, so every caller that "sets the
  cache" also ERASES at the position it has just cached. `$B6B9`'s `CALL $BF0A` in the escape is
  one such caller.
- **A CAPTURE ABANDONS ITS CALLER**: `$BEA8` POPs the return address before `$BEAC JP $B9E7`, so
  the remainder of `$BE07` -- the wall probe and the cap test after `$BE31` -- never runs and
  control resurfaces in the caller's caller. Modelled as a boolean the caller returns on.
- **Capture box** (`$92C0`, with `$92DE` patched to RET): the sprite INSET BY TWO on every side,
  `X+2..X+14` by `Y+2..Y+14`. The scan walks the enemies' `+7` bytes from `$FD9B` in steps of ten
  for `($AA57) - 2` slots -- a DO-WHILE, so a count of zero scans 256 -- skipping any that is not
  alive (bit 7) or is already FROZEN (bit 3), so one bubble cannot steal another's catch. The
  per-axis test is `v < hi AND (v + 15) >= lo`, both EIGHT-BIT.
- **Timeout ESCAPE `$B679`** (the manager's holding path): when a holding bubble's `(IY+4)` wraps,
  it RELEASES the enemy -- `IX = $FD94 + (IY+8)*10`, copy the bubble's X/Y to the enemy `(IX+5/6)`,
  reset `(IX+8/9)=0` (back to WALK state), and **`SET 2,(IX+7)`** = the walker's speed-doubler
  (`$B030`), i.e. the released enemy turns ANGRY/FAST -- BB's "pop it in time or it escapes angry".
- OPEN (the last capture specifics; localized): the exact commit that sets `(IY+9)=1`/`(IY+8)` on a
  successful `$BE5B` hit and hides the enemy; the `$92C0` collision internals; POP (player bursting
  a HOLDING bubble -> enemy DEATH -> a FRUIT/item on the `$B59D`/`$B5BD` fall arc); the fruit/item
  object + collection + SCORE; EXTEND letters; fire/water/lightning special bubbles.

## Items: pop -> fruit -> score (M5) -- READ FROM CODE (live capture NOT yet reproduced)

Confidence: the routines and their data flow are READ from the disassembly; the dynamic
capture->pop->fruit->collect sequence is NOT yet verified live (700 frames of scripted
steer+blow produced no capture; a poked `$5CE0` entry cleared after one frame). So the
per-slot field encoding and scoring below are PROVISIONAL until a live capture is scripted.

- **CAPTURE-COMMIT `$BE80`** (reached when the empty-bubble check `$BE5B` hits an enemy): sets the
  bubble `(IY+8)` = enemy slot index, `(IY+9)=1` (holding); on the ENEMY it does `SET 3,(IX+7)` (the
  "captured" marker, cleared by the escape path) and draws it once; the bubble's hold-timeout
  `(IY+4)` is loaded from data at **`$745A`**; then `$BEE8` transitions the bubble to floating.
- **HOLD / DRAW `$B9E7`**: a holding bubble draws sprite `$C900` (enemy visible inside); once
  `(IY+4) >= $E6` it FLASHES, alternating `$C900` with the EMPTY `$C780` on the `$B62D` toggle
  = about to burst/escape.  (`$D380` is the ELEMENT base, kind >= 2 -- corrected 2026-09-12.)
- **ESCAPE (timeout) `$B679`**: if not popped in time, the enemy is released -- copied back to
  `$FD94 + (IY+8)*10`, `(IX+8/9)=0` (WALK), **`SET 2,(IX+7)`** (the walker's speed-doubler) =
  ANGRY/FAST. Measured-consistent with BB's "pop it in time or it escapes angry".
- **BURST / POP `$B6D8`** (runs when the bubble's flag bit 2 is set): deactivates the bubble
  (`RES 7/3/2`), saves `(IY+9)` to `$B742` (the captured-enemy indicator -> fruit type), and
  creates a FRUIT in the table at **`$5CE0`**: scans 14 entries for a free one and writes
  `X|1` (bits7-3 = X, bit0 = active) then `Y` at the bubble's position. OPEN: the exact PLAYER
  action that sets bit 2 (the player bursting the bubble by contact).
- ~~FRUIT TABLE `$5CE0` / FRUIT MANAGER `$C006`~~ -- **WRONG AND WITHDRAWN (M7.7-I10).**  It is
  not a fruit table, the encoding is not `X<<3`, `$C006` is not an entry point, `$A314` is not a
  collect, and the clears are byte-fills, not an LDIR.  See the single entry below.
- **VERIFICATION OUTSTANDING**: reproduce a live capture (bubble overlapping an enemy during its
  travel) to confirm `$BE80`/`$5CE0` field encodings and read `$A314` scoring against a real
  fruit. Crude steer+blow did not align a bubble with an enemy; needs a scripted approach (drive
  the player onto an enemy and blow into it, or record a demo input) -- the next step here.

## Items: VERIFICATION UPDATE (M5) -- capture + pop->fruit CONFIRMED LIVE

Staged the capture instead of relying on luck (the earlier steer+blow missed because it
matched neither Y nor facing). Method: poke the player adjacent to an enemy at the SAME Y,
facing toward it, then blow (cursor key 7). Capture fires in ~2 frames. The blown bubble
inherits the player's Y and travels at it, so matching Y is the key; only the player/enemy
POSITIONS are poked -- the capture/burst/fruit CODE runs for real.

- **CAPTURE -- CONFIRMED LIVE**: bubble `$FED8` -> `(IY+9)=1` (holding), `(IY+8)=0` (enemy index,
  0-based from `$FD94`), and the captured enemy's `(IX+7)` bit 3 SET. Exactly the `$BE80` commit;
  the earlier-provisional field encodings are now measured.
- **POP -- the burst trigger is bubble flag BIT 3** (manager `$B636`: `$B64B BIT 3 -> $B6C3 ->
  $B6D8`), NOT bit 2 (bit 2 only distinguishes empty vs solid). CONFIRMED LIVE: setting bit 3 on
  the holding bubble -> `$B6D8` -> a FRUIT appears in `$5CE0` at the bubble's position
  (`byte0 = X<<3 | phase`, `byte1 = Y`; e.g. X=24 Y=168), the bubble deactivates, and `$B742` = 1
  (the captured-enemy -> fruit-type indicator).
- **CORRECTION**: `$A314` (called by the fruit manager `$C006` at phase 0/2) is the fruit
  DRAW/ERASE helper (copies the fruit cells to/from the shadow at `$A0xx`), **not** the collect/
  score routine.
- **STILL OPEN (collection & score not reproduced)**: the NATURAL player action that sets a
  holding bubble's bit 3 (the real "jump into the bubble to pop it" -- I used a bit-3 poke); the
  player-vs-fruit-table overlap check and the SCORE variable/points (holding the player on the
  fruit did NOT collect it, so the collision uses a representation the position-poke doesn't
  satisfy -- likely a check in the player update, to be found). EXTEND letters + special
  fire/water/lightning bubbles also remain.

## Score + item collection (M5) -- score VERIFIED; collection needs real play

- **SCORE (P1) = `$FFED`-`$FFEF`, 3-byte BCD (6 digits), little-endian** -- VERIFIED: reads
  `00 00 00` in round 1, matching the HUD "1UP 00". The add-score routine at **`$B7D1`**:
  `LD HL,$FFED / ADD A,C / DAA / INC HL / ADC A,B / DAA / INC HL / ADC A,0 / DAA` (three DAAs);
  the amount added is 10 or 100 (BCD) times a multiplier chosen just before (`$B7C6`). P2's
  score is a sibling (address TBD).
- **Scoring is on COLLECTION, not on the pop** (measured: a staged pop left `$FFED` unchanged).
- ~~Item/fruit table `$5CE0` ... `X<<3`~~ -- superseded by M7.7-I10 (a burst-sparkle particle
  engine; the X field is MASKED `& $F8`, not shifted).
- **HONEST LIMIT -- collection NOT reproduced**: a fruit created by a bit-3 POKE pop sits inert at
  phase 0 and is NOT collected even when the player walks onto it (score stays 0, entry persists
  60+ frames). Most likely the artificial pop creates a MALFORMED fruit -- a real player-pop sets
  fruit state (type via `$B742`, phase) that the poke does not -- so the collect path never fires.
  Faithful collection/scoring, and the power-up + level-clear items below, need a REAL capture->
  pop->collect sequence, which artificial position-pokes cannot stage cleanly (no self-playing
  demo state exists; the player is idle in every saved state).
- **POWER-UP + points-item spawn -- RESOLVED 2026-09-09 (code $8C5E/$89CB/$8A09 + an 8-round harness
  check).** Each round the init `$8C5E` clears the power-up slot `$9603` and decodes ONE per-round
  byte from the 81-entry table **`$FF90`** (indexed by round-1): X = `(byte>>1) & $70` for the
  power-up, its mirror `$100-(X+16)` for the points item, alternating which gets which by round
  parity; Y = `(byte<<4 & $F0)>>1`, bit 7 set if the round is in the 13-entry list `$860F`. The
  power-up TYPE for a normal round is the round number run through the type map `$8A62`(16 listed
  rounds)/`$8A72`; rounds that ARE listed take `$8A2E LD A,R AND 3 / SUB 1 / ADC A,3` = **{3,4,5}
  with P(3)=1/2** (CORRECTED 2026-09-10: not 'a random 0..3', and the branch sense is the reverse of
  what this line used to say; verified by executing the mask over R=0..127. docs/RNG.md);
  the unlisted branch is `$8A38`. The special rounds force type 6/7
  (umbrella/water). The POINTS-item type is a rotating counter **`$9AE9`** advanced by +? at each
  level clear (`$8EF2`), indexed into `$860F+...`. MEASURED: rounds 1/6/10/20/30/40/50/60 all
  spawned the power-up and points item at exactly the decoded X/Y; the power-up appears once the
  play timer `$8DBD` passes a threshold (idle: ~1024; blowing brings it forward). This CLOSES the
  "power-ups spawn ~1/level, storage/route OPEN" item. The candy-cane/giant-fruit chain (a
  level-clear GIANT once all enemies are dead) is the separate giant-item section.
  the special-item spawn are deterministic code (readable statically); the fruit TYPE is tagged by
  `$B742`; regular fruit sprites `$CA80`/`$CAA0`.

## Round transition / level-clear (M5) -- the advance machinery (static)

- The main loop top gates the round-advance on a clear-pending counter: `$8CFF INC ($FEC9) /
  JR nz` then `$8D06 CALL $96DF / $8D09 CALL $97F8`. `$FEC9` wrapping to 0 = "level cleared,
  advance now" (all-enemies-dead sets this up elsewhere; zeroing the enemy slots forces it, which
  is why `tools/extract_round_colours.py` advances by clearing slots).
- **Round-advance `$97F8`**: `INC ($8609)`; `CP $52` (82) -> wrap using `($FEC7)`. A next-round
  LOOKAHEAD is kept in **`$FEC7`** (`$9809`: inc, and at 82 reseed `LD A,R AND $1F ADD $1E`).
- **THE TWO CALLS THE ROUND-START SEQUENCE EXPOSED** (`$99A8`, `$A36C`) -- MEASURED AND GATED
  2026-09-22, M7.7-R4.  M7.7-R1 bracketed all nine calls in the sequence and found these two
  owned by no increment.
  - ***`$99A8` IS THE ROUND'S PLAYER INIT, AND IT IS A TWO-ENTRY SHARED BODY.***  `$99A8`
    CALLs `$99C3`, which sets P2 up and FALLS THROUGH into the tail at `$99D4`; the call
    returns, `$99A8` sets P1 up and JRs into the SAME tail.  The tail therefore runs twice,
    with `C = 1` then `C = 0`, and **C is both the player index and the source of the `(IY+7)`
    mask** -- one register doing two jobs, which is why passing "which player" as a boolean
    loses the mask.  (Not `playerInit()`, which is `$97D2`, the new-game start.)
  - **THE MASK IS THE PART A READING GETS WRONG.**  `$99EF` builds
    `C := (((IY+$5B) & 1) << 2) | $C0 | (index ^ 1)` and `$99FA` does
    `(IY+7) := ((IY+7) & C) | $40`.  Bits 6 and 7 always survive; bit 2 survives only if
    `(IY+$5B)` bit 0 is set; and **bit 0 -- THE FACING -- survives for P1 and is cleared for
    P2**, because the mask's bit 0 is the OTHER player's index.  MEASURED with every field
    poisoned: 19 writes, P1's `+7` `$5A -> $5B` (the `SET 0` at `$99B7`) `-> $41` and P2's
    `$5A -> $40`, and `(IY+$5B)` is READ and never written.
  - ***AND `$A36C` WAS ALREADY IN THE PORT -- INLINED INSIDE I6's ITEM HANDLER 12***, the
    level skip at `$8915`, so the round start could not reach it.  One routine, two call
    sites, transliterated at one of them (TRAPS #58's shape).  Twenty bytes at `$5B00` and
    twenty at `$FDEE`: 40 writes, ALL from `$AA4A`, and no player field touched.  It is one
    method now and both sites call it.
  - **AND THE `$5A` POISON HID TWO OF THE OPERATIONS IT WAS SUPPOSED TO EXPOSE.**  `$5A` is
    `0101 1010`: bit 6 is already SET, so `$99FE`'s `OR $40` writes nothing new, and bit 7 is
    CLEAR, so `$99D7`'s `AND $80` cannot be told from assigning the index.  Two mutations
    survived on exactly that.  `+7` is now driven with bit 6 clear and `+$5A` with bit 7 set.
  Oracle `tools/roundstart.py:phase_unowned`.
- **THE DRAINED DIFFERENTIAL** -- MEASURED AND GATED 2026-09-22, M7.7-R3.  The passdiff
  harness walked `BB_CHAIN` by hand and never called `step()`, so a routine that SPENT frames
  was never charged for them -- B2's 345-frame "WELL DONE" freeze and `$9887`'s HALT both
  passed without a single ISR running.  Draining `tframe` into `isr()` **at the point of each
  spend** takes `bosshit` and `r50_48` GREEN over all 60 rows with the drain active.
  - **THE DRAIN MUST HAPPEN WHERE THE SPEND HAPPENS.**  Draining once at the end of the pass
    applies frames spent BEFORE a write AFTER it: the freeze's 342 interrupts then ticked a
    settler byte that, on the machine, had not been written yet, and `($B54B)` came out 0
    against 87.
  - **`$9887`'s HALT SPENDS ONE FRAME**, and that is what closes `($B54B)` at the advance:
    un-charged it reads 88 against the machine's 87.  Gated on the routine itself as well as
    through the differential, because a two-frame charge drains an extra ISR whose settler
    tick lands on the wrong parity half the time and is invisible in `($B54B)` alone.
  - ***AND THE DIFFERENTIAL WAS ASSERTING A FIELD THE PORT CANNOT LEGITIMATELY REPRODUCE.***
    `($FEC7)`'s reseed is `$9811 LD A,R` -- the refresh register, which E1 replaced with a
    DECLARED SUBSTITUTE -- and the 80 -> 81 advance takes that arm because the lookahead would
    be 82.  It matched only because nothing had disturbed the substitute's state; charging the
    HALT adds one ISR, the ISR consumes a draw, and the value moves 40 -> 35.  A gate that
    asserts it is testing the substitute against the machine's R register, which is precisely
    what E1 says cannot be done.  EXCLUDED, by name.
  - ***AND WHAT STOPS IT NOW IS A NAMED, UNBUILT INCREMENT: THE ROUND BUILDER `$7F62`.***
    With `($B54B)` closed and `($FEC7)` excluded, the advance row diverges on `($830A)`, 94
    against 102: the SOLID palette is written by `$82F4`, and **`$82D6` has EXACTLY ONE CALLER
    IN 64K, `$7F65`**, inside the round builder.  The port loads a captured world instead of
    running the builder, so `paletteStep()` is wired nowhere and **a round advance never
    changes the palette** -- M7.3c's sibling, and the next increment.
  - **A CORRECTED PREDICTION, RECORDED WHERE IT WAS MADE.**  M7.7-R2 withdrew `arm; halt` vs
    `halt; arm` as a provable equivalent and said it would become real "the moment the halt
    spends its frame".  It spends now, and it is STILL equivalent, because `spend()` DEFERS:
    the frame is banked and the ISR runs at the drain, by which time the arm has happened
    either way.  The condition is not "the halt spends" but "the port models time INLINE".
- **THE ROUND BANNER `$98B5..$98EF`** -- MEASURED AND GATED 2026-09-22, M7.7-R2.  The
  ~1-second animation R1b found by measuring why the differential was off by one settler tick.
  - ***`B` IS ZERO AT `$98B5` ON EVERY STATE, SO `$98E2`'s `DJNZ` RUNS 256 TIMES.***  TRAPS
    #45 for the third time in this project.  Each iteration draws two text rows through
    `$802E` and writes ten attribute cells through `$995A` at `$594C` and `$598C` -- 5,140
    writes over only 20 cells.  Round 81 runs ZERO iterations: `$98B8 CP $51 / JR z,$98E4`
    sends it straight to the erase.
  - ***AND THE BANNER ERASES ITSELF: THE END STATE IS BYTE-IDENTICAL TO THE START.***
    `$98E4` calls `$9904` twice and the twenty cells go back to exactly what they held --
    measured on all five worlds -- so the ONLY observable is the TIME.  H2's lesson again, and
    it caught this increment's own gate: three mutations (one row instead of two, the second
    row at the first row's address, eleven cells instead of ten) all survived an end-state
    check.  The gate suppresses the erase and reads the rows MID-ANIMATION.
  - **WALL-CLOCK the cost splits by the round's digit count** -- one digit 3,524,147 and
    3,525,899 T, two digits 4,074,024 and 4,122,335, the classes 15% apart -- **but that is
    all ISR load** (M7.43, RA1).  Main-line, with every ISR inside it removed, the banner is
    FLAT: 2,830,310..2,837,539 T over 160 advances (median 2,832,314), and round 81 costs 7,110.
    step() charges the ISRs itself, so the engine spends the main-line constant; the digit
    classes charged them twice.
  - It is spent through **`spend()`, the port's only time API**, and the machinery already
    existed: a cost bigger than a frame drains through `step()`'s carry as zero-pass frames
    with one ISR each -- no main loop, interrupts firing, the settler ticking 25..29 times --
    which is exactly what the machine does, and what `$9573`'s busy wait already used.
  - The GLYPHS go through the ROM charset and are the same DECLARED DEPARTURE as the HUD font,
    the game-over banner and `$8E9D`'s: counted, not drawn.  The ATTRIBUTES are faithful, and
    `$995A`'s `OR $40` is a NO-OP at this call site because `$47` already has bit 6 -- only
    `$8E9D`'s `$85 -> $C5` ever shows it.  The eight-bit `INC L` cannot wrap at `$594C` or
    `$598C`, so it is EXERCISED from `$59FA` instead, where the run covers `$59FA..$59FF` and
    wraps to `$5900..$5903`.
  - `$9904` is H9's painter and stays a NAMED COUNTED STUB: the port RESTORES the twenty cells
    rather than repainting them, which models the OUTCOME and not the routine -- said out loud,
    because H9's increment will replace it.
  Oracle `tools/roundstart.py:phase_banner`.
- **THE ROUND-START SEQUENCE `$9858..$98B4`** -- MEASURED AND GATED 2026-09-22, M7.7-R1.
  This is the gap B11's differential stopped at: it reproduced the machine row for row for 59
  passes and halted exactly at the 80 -> 81 advance, naming twenty fields.
  - ***`$984B` HAS NO RET.***  `$9855 LD (DE),A / $9856 DJNZ $9851 / $9858 LD HL,$E000` -- the
    19-pointer clear walk falls STRAIGHT THROUGH into the sequence, which runs on past
    `$98B5` into the round banner before returning.  So `$8D09 CALL $97F8` runs ALL of it.
    The port keeps two methods and makes the call the machine gets for free (TRAPS #52's
    shape), and `roundAdvanceCore()` exists because `tools/roundadv.py` brackets the advance
    and STOPS at `$9858`: a gate must compare the span the fixture captured, not a longer one
    that then disagrees about `($FEC4)` (TRAPS #66).
  - ***THE SETTLE WINDOW IS 88 FRAMES ON EVERY ROUND AND 20 ON ROUND ONE.***
    `$9877 LD A,($8609) / DEC A / LD A,$58 / JR nz,$9881 / LD A,$14`, and **one load feeds
    both `($B54B)` and `($FEC4)`**.  `$B54B` is the byte `$AA72 JP nz,$B520` uses to abandon
    the ENTIRE entity pass, so round 1 freezes the entities for 20 frames and every other
    round for 88.  Enumerated over twelve round values with both bytes poisoned.
  - **AND `($FEC4)` IS THE UNDECAYED COPY**, which confirms it on four live captures with no
    poke at all: `$B54B` counts down and `$FEC4` keeps the round's original, so `play1p48`
    reads 14/20, `round1_48` 0/20, `r20_48` 10/88 and `bosshit` 0/88.  B11 recorded
    `play1p48` sitting inside a settle window as evidence that captures are suspect; it is a
    ROUND-1 SPECIAL CASE, and `$FEC4` is how you can tell after the fact.
  - **THE SEQUENCE CONTAINS A HALT.**  `$9887` waits for the ISR between arming the settler
    and zeroing the frame counter, so the two halves are on opposite sides of a frame
    boundary.  The port has no mid-routine HALT, so it is NAMED and counted.
  - `$988B` and `$988E` are **SIXTEEN-BIT STORES**: `LD HL,0 / LD ($8DBD),HL` zeroes `$8DBD`
    AND `$8DBE`, and `LD ($8DB6),HL` zeroes `$8DB6` AND `$8DB7`.  All four poisoned, because
    zero is the value the store writes.  `$9872` puts the enemy step `($B610)` back to 2.
  - `$9858` clears **6144 bytes, `$E000..$F7FF`** -- `LD C,$18` with `$AA49` entering at
    `B = 0`, so TRAPS #45's DJNZ runs 256 times and twenty-four passes cover the PLATFORM
    shadow and **not one byte of the colour shadow** at `$F800`, which is a different buffer
    with three lives (H3/H4/H5).
  - `$98AD`'s `LD A,$2A` **feeds two stores**: the ISR's even-branch gate `($FEC5)` and the
    boss's starting HP `($9F62)` share one literal.  `$79A2`'s self-doubling seeder wrote
    `$9F62` a moment earlier (20 on the 80 -> 81 build) and this supersedes it -- measured
    writers `$79A8` then `$98B2`, in that order.
  - **EVERY CALL IN THE SEQUENCE, BRACKETED SEPARATELY** (a first attempt measured two of the
    nine, because seven return addresses ARE the next call site and the bracket closed on an
    arm): `$7F1B` 211,251 writes -- the whole scroll-in [H11]; `$79AC` 2,028 with 1,634 into
    the colour shadow [H3/H8]; `$BF39` 1,696 [H10]; `$727B` 117 [M7.6's spawner]; `$957E` 123
    [H9]; `$8C5E` 73 [I6/I7]; `$A36C` 44 -- UNOWNED; `$99A8` 23 -- the round's player init,
    UNOWNED; `$AA49` 26 [I10].  The four the port owns are wired and the five it does not are
    NAMED COUNTED STUBS carrying those shapes.
  - ***AND B11'S TWENTY FIELDS PARTITION CLEANLY***: thirteen are written here and seven --
    `$8609`, `$A839`, `$AA00`, `$AA06`, `$FEC7`, `$FEC8`, `$A09E` -- are NEVER touched by the
    sequence; they move in the advance and the clear walk before it, or in the loop resuming
    after it.  Naming which is which is what turns "the round build is not transliterated"
    into a work order.
  - ***THE ROUND BANNER IS A ~1-SECOND ANIMATION AND ROUND 81 SKIPS IT ENTIRELY.***  With the
    sequence wired, B11's differential goes GREEN over all 60 rows of `bosshit` and `r50_48`
    and reaches `bosskilled`'s row 20 -- the 80 -> 81 advance -- differing on ONE field by
    ONE: `($B54B)` 87 against 88, because the engine arms the settler and stops while the
    machine then SPENDS FRAMES.  The first model was "one tick" and it is WRONG: measured on
    five worlds (`bosskilled` naturally, the rest by zeroing the enemy slots to force a
    clear), the count between arming and the first loop top is **1, 28 or 31**.  Splitting it
    at `$98B5` says why: the transliterated part costs **2..4 interrupts and 1..3 ticks**, and
    the BANNER after it costs **51..58 interrupts on an ordinary round and ONE on round 81**,
    which `$98B8 CP $51 / JR z,$98E4` sends straight past.  So `roundStart()` ends at `$98B4`
    BY MEASUREMENT, and the ticks it cannot reproduce are the banner's -- the work that
    increment inherits.  B11's fixture recorded the row-20 owner as `$8C5E the round build`;
    that is SUPERSEDED and the annotation now names the banner.
  - The ORDER of the settler arm and the HALT is unobservable in the port and only there:
    `roundHalt()` counts a frame the port does not spend, so `arm; halt` and `halt; arm` give
    identical state.  Withdrawn as a provable equivalent, and it becomes a real distinction
    the moment the banner makes the halt spend its frame.
  Oracle `tools/roundstart.py` -> `build/roundstart_fixture.json` (calls, settler, frames,
  zeroing, handover).
- **THE ROUND BUILDER `$7F62` AND ITS COMPOSITION `$7F1B`** -- MEASURED AND GATED 2026-09-23,
  M7.8-A.  The increment that stops the port's round advance painting an empty black screen.
  - **WHAT WAS WRONG.** `roundStart()` called `scrollIn()` alone -- `$7F30`'s scroll driver,
    the MIDDLE of `$7F1B` -- so the builder never ran and the repaint never ran.  Measured on
    the built page: after `reset()` the playfield had 0 of 704 invisible cells, 2,415 non-zero
    bitmap bytes, 2,247 platform-shadow bytes and 224 colour cells carrying the drift bits;
    after ONE `roundAdvance()`, **495 invisible, 0 bitmap, 0 shadow, 0 drift**.  M7.3c's
    visibility gate could not see it because that gate runs only after `reset()`.
  - **AND THE ANSWER IS NOT AN ASSET.  A ROUND'S PLATFORM SHADOW IS NOT A FUNCTION OF THE
    ROUND.**  The same round 20 built at different build-counter phases differs in up to 2,083
    of 6,144 shadow bytes.  `($83EC)` selects the tile -- five values in play, TEN distinct
    shadows when poked out of band, wrapping at 5 -- and BIT 7 of the palette byte `($82D7)`
    selects a wall arm (2 distinct shadows over a `$82D7` sweep, the odd one out being index 0,
    whose byte `$17` is the only one of the fifteen with bit 7 clear).  A faithful plate set is
    **81 x 5 x 2 = 810 shadows, about 5 MB**, against 768 bytes of Z80 over data already
    shipped.  That is why rounds 2-81 have no render asset and must not get one.
  - **THE COMPOSITION `$7F1B`**, in order: arm `$9603..$9643` as `LDI` x32 + `RET`;
    `$7F2A CALL $8207` (the filler pattern); `$7F2D CALL $7F62` (the builder); `$7F33` round 1
    SKIPS the scroll; `$7F36/$7F39` separator + cascade; 22 x (`$840A`, `$8447`);
    `$7F4E CALL $8216` (the repaint, which DISCARDS what the scroll drew); `$7F51 CALL $7F80`;
    `$7F58 CALL z,$7FC0` (round 1 only); `$7F5B CALL $806C`; `$7F5E CALL $854D`.
  - **`$7F62` HAS NO RET**: `$7F7D CALL $81C3` falls straight through into `$7F80`, so the
    round-number drawer is part of the builder's dynamic extent.  `$7F80` runs **three times**
    per build (the fall-through, `$7F51`, and `$8216`'s tail `JP $7F80`) and `$833A` runs
    **twice** (`$7F6E` and `$7F77`).  Only the execution COUNT separates that from a port that
    paints the same picture once.  Measured trace counts: round 2
    `{8207:1, 7F62:1, 7F80:3, 81E6:1, 8404:1, 840A:26, 8447:22, 8216:1, 806C:1, 854D:1}`;
    round 1 the same minus the scroll, plus `7FC0:1` and `806C:2`.
  - **`$81C3` IS TWO PASSES.**  `LD HL,$F800 / CALL $81C9`, then it FALLS THROUGH into `$81C9`
    again, so one pass writes 32 bytes and the routine writes 64 -- `$F800..$F83F`, the
    collision map's two HUD rows.  `$81E0` is `CPL / LD (HL),A / INC HL / DJNZ` aiming at
    `$81E1`, so the CPL fires ONCE PER GROUP; from A = 0 the groups alternate.  Measured with
    the range poisoned `$5A`: 64 writes, all from `$81E1`, zero outside the range, zero
    survivors, run lengths **9,4,6,4,18,4,6,4,9** -- and **the 18 IS THE JOIN**, pass one's
    trailing nine `$FF` abutting pass two's leading nine.  A one-pass port gives 9,4,6,4,9.
  - **`$854D` COPIES DISPLAY -> SHADOW**, rows 2 and 23.  `$8556` is
    `LD HL,$A000 / ADD HL,DE / EX DE,HL`, so DE ends holding the SHADOW address; the `LDIR`
    runs display into shadow, 8 sub-rows of 32, with `INC D` and `INC H` both EIGHT BIT.  It
    runs last because `$7F80` and `$806C` have just drawn into the DISPLAY.
  - **`$824A` IS AN EXX ROUTINE** and that is where a reading goes wrong: `$8273 CP C` compares
    against the ALTERNATE C, which holds `($8309)`, while `$827A SUB C` uses the MAIN C, the
    column counter.  `B = $1D` on the first map row and `$1C` after -- twenty-nine then
    twenty-eight -- so the `ADD HL,DE` row skip fires one cell into the next row.
  - **THE BUILDER'S INPUT SET IS `($8609)`, `($82D7)`, `($83EC)` AND THE PLATFORM SHADOW.**
    The fourth was found by a CLOSURE TEST: `$824A` merges with `OR (HL)`, so the same triple
    built from three different saved worlds gave THREE different shadows until `$9858`'s clear
    was modelled, after which it is distinct = 1 on every row.  The COLOUR shadow is **not**
    an input -- zeroing it as well changes nothing.
  - **`$9858`'s CLEAR LENGTH IS B FROM THE CALLER AND `$9858` NEVER SETS B.**  `$AA49` is
    `XOR A / LD (HL),A / INC HL / DJNZ`, so the clear is `B + 23*256`.  Armed from a mid-play
    save, B is 88 on round1_48 and 10 on r20_48 -- 5,976 and 5,898 bytes, residue left in the
    bottom sub-rows, predicted to the byte.  Through the REAL advance on a correctly seeded
    chain, **B is 0 on all 81 rounds**, the whole 6,144.  The short clears are an artefact of
    the entry point, not a behaviour (TRAPS #94).
  - **TWO PIECES OF LIVE STATE THE PORT HAD NEVER SEEDED**, both found only because the
    builder finally gave previously-uncalled methods a call site:
      * **`$833B`**, `$833A`'s self-modified operand and the wall column offset.  See the
        `$833A` entry above for the measured figures.
      * **`$856C..$8583`**, the tile buffer's static half.  A build writes only offsets +1, +3,
        +5 (odd, by `$824C/$824F/$8253` and again by `$82C5`) and +0..+14 (even, by `$8334`);
        **+7, +9, +11, +13, +15 and +16..+23 are never written by anything** and are pure tape
        data.  With them zero the `OR (HL)` contributed nothing, so the engine wrote 2,704
        bytes to the same 2,704 addresses in the same order and **455 platform bytes went
        missing** (TRAPS #96).  Carried as `BB_TILE_SEED`, from `build/image_tape.bin` and not
        `build/image.bin` -- the image is a round-80 dump whose even bytes hold that round's
        tile.
  - **THE ONE REMAINING DIVERGENCE IS THE DECLARED ROM-FONT DEPARTURE**, bounded to the glyph:
    `$7F80` draws the round number through `$8042`, which indexes the ROM charset at `$3C00`
    (7 reads below round 10, 14 from 10).  The machine changes 7 shadow bytes on round 1, 14 on
    round 11 and **0 on round 81** (`$7F83 CP $51 / RET z`); the engine differs on SIX, every
    one inside that set, and on no platform byte.
  - **NOT EVERY ROUTINE IN THE CLOSURE RUNS ON EVERY BUILD**: `$7FAF`, `$8042`, `$83D9` and
    `$850A` do not.  Recorded as false rather than rounded up to "all".
  - **`($83EC) == ($82D7) mod 5` IS AN INVARIANT OF THE MACHINE.**  Both advance by one per
    build, mod 5 and mod 15, and 5 divides 15.  It holds on all five shipped 48K states
    (round1_48 1/1, play1p48 1/1, r20_48 2/2, r50_48 2/2, bosshit 5/0) and on all 81 chained
    builds.  The port's `reset()` carried `($82D7)` from the render asset and left `($83EC)`
    on `build/image.bin`'s round-80 zero, i.e. **(1, 0), a pair the machine is never in** --
    so every round it built used the PREVIOUS round's platform tile, about 1,650 of 6,144
    shadow bytes per advance.  Inert until `$7F62` was wired; `tools/render_asset.py` captures
    `tile_counter` now and the port CARRIES it (deriving it would work here and is exactly the
    move this document warns against for `($82D7)`).
  - **THE FOUR DECLARED BOUNDARIES OF THIS INCREMENT**, each measured rather than waved at:
      * the ROUND-NUMBER GLYPH -- 6 bytes, the ROM-font departure (`$8042` indexes `$3C00`);
      * the LIVES ICONS -- row 23 columns 0..4, `livesPanel()` is a counted stub and `$806C`
        has SIX call sites in 64K, so it belongs to a HUD increment;
      * **`$7FC0`'s TAIL -- 1,191 writes** (488 display bitmap, 129 attributes, 32 shadow, 542
        score counters at `$96BB..$96CA`), which is why the machine's trace calls `$806C`
        TWICE on round 1 and the engine once.  The port models only the RRD loop
        `$7FC0..$7FD5`;
      * **THE ISR**, which fires inside `$7F1B` because the routine contains no `HALT`, draws
        entities into the display, and is then copied into the SHADOW by `$854D`'s row-2 pass.
        MEASURED both ways: it changes the built shadow on **3 of 23 covering rows**.  The
        compose oracle is captured interrupts-OFF, which is what the port models, with the
        interrupts-ON CRC carried beside it.
  - **`$854D` IS INVISIBLE IN THE COMPOSED PATH** and therefore needs a unit oracle: after
    `$8216` the display rows already equal the shadow, so it copies back identical bytes and
    changes nothing.  Five mutations of it -- including reversing the copy direction and
    replacing the whole body with a counter bump -- left the suite green.  Driven against a
    display poisoned `$5A` (and again `$A5`) it moves **512 bytes, `$E040`..`$F7FF`**, every
    one the poison.
  - **FOUR MUTANTS WITHDRAWN AS PROVABLE EQUIVALENTS**, enumerated rather than waved away:
    (1) repainting BEFORE the scroll -- after `scrollIn()` the display already equals the
    shadow on all 5,632 playfield bytes, so `$8216` changes 0 of 65,536 and the orders
    converge (M7.7-H2's discard finding from the other side; it becomes testable when the
    scroll increment gates MID-SCROLL snapshots);  (2) `$854D` before `$806C` -- equivalent
    ONLY because `livesPanel()` is a counted stub, a CONDITIONAL equivalent that becomes real
    the day `$806C` is built, which is the very reason `$854D` runs last;  (3) arming `$9603`
    after `$8207` -- `$8207` writes `$8584..$858B` and nothing else, disjoint;  (4) seeding
    `BB_TILE_SEED` from `build/image.bin` -- the tape and the image agree on ALL SIXTEEN bytes
    the constant still governs, differing only on the EVEN bytes, which `reset()` now carries
    from the render asset.
  - **THE WRITE EXTENT IS GATED AS AN ADDRESS SET OVER THE WHOLE 64K**, measured with a
    write-watch and not a before/after diff: `$7F62` writes 5,241 addresses and `$7F1B`
    10,414, unioned over rounds 2, 20 and 81, and the engine must write nothing outside them.
    A diff-based extent is wrong because `$860E` is written by `$8400` on every build and
    CHANGED on none (TRAPS #102).
  - Oracle `tools/roundbuild.py` -> `build/roundbuild_fixture.json`: 23 covering rows over
    (round, `$82D7`, `$83EC`) driving both record classes, both wall arms and all five tile
    indices -- **and "palette bit 7 is clear on index 0 alone" was FALSE**: `$858C` index 10
    is `$0F`, used on rounds 11, 26, 41, 56 and 71, and the first covering set never reached
    it -- compared per row by whole-shadow CRC, **22 per-row CRCs** so a failure names the
    row, all 768 colour bytes, the palette pair, the tile pointer and the 24-byte tile buffer,
    plus ONE full plate diffed literally with no checksum at all.
- **THE PLAYFIELD ATTRIBUTE PAINT** (`$82D6`, `$823C`, `$8C28`) -- MEASURED AND GATED
  2026-09-22, M7.3c.  ***THIS IS WHY THE PORT RENDERED A BLACK SCREEN.***
  - **NOTHING PAINTS ENTITY COLOUR.**  The open item read *"something paints entity colour and
    the engine does not model it"*.  60 frames of `round1_48` with `$5800..$5AFF` watched give
    **122 writes and every one from `$8017`, the HUD score** -- rows 0-1 only, the playfield
    never touched in play.  The enemies are visible because the WHOLE PLAYFIELD carries the
    round palette and the sprites inherit it: the cells under the three round-1 enemies read
    `$47`, `$47`, `$57`, the round's own OPEN and SOLID entries.
  - `$82D6` picks `BB_PALETTE[($82D7 - 1) mod 15]`, makes `solid = (p & $7F) | $40` into
    `($830A)` and `open = solid & $47` into `($8309)`, and fills the colour shadow from
    `$F840` with `open`.  PREDICTED EXACTLY on six states: `round1_48` 47/57, `r10`/`r20`/
    `r30`/`r50` 45/55, `bosshit` 46/66.  ***AND `$82D7` IS A BUILD COUNTER, NOT THE ROUND*** --
    `r10_48`, `r20_48`, `r30_48` and `r50_48` all read 2 -- so a port that derives the palette
    from `($8609)` is right on round 1 and wrong on four of the five others.
  - **THERE ARE TWO WAYS THE DISPLAY ATTRIBUTES GET WRITTEN AND THEY ARE NOT INTERCHANGEABLE.**
    `$823C`, the tail of `$8216`, is a plain `LDIR $F840 -> $5840`: correct AT BUILD TIME,
    when `$82FC` has just filled the shadow with `open`.  `$8C28` is the one that works on a
    LIVE shadow -- `$8C34 BIT 5,(HL)` picks `($830A)` or `($8309)` per cell -- because by then
    the shadow has been repurposed as H3's solidity, H4's drift and H5's occupancy bit fields.
    Run over `round1_48`'s live world `$8C28` changes **one cell of 704**, so the live
    attribute file IS that derivation.
  - **THE FOUR CELLS THE DERIVATION DOES NOT OWN ARE THE SAME EVERY ROUND** and belong to
    other painters: row 2 columns 0-1 (the ROUND NUMBER, `$7F80`) and row 23 columns 0-3.
    4 mismatches on round 1, 6 on round 20, 5 on round 50 -- named, not smoothed over.
  - ***THE ROUND ASSET'S ATTRIBUTE THIRD WAS THE COLOUR SHADOW, BYTE FOR BYTE.***
    `build/render_round1.json`'s `display` is a full 6912-byte display file whose attribute
    third for rows 2-23 equalled its own `colour` block: `$00`, `$20`, `$40`, `$A0`, `$C0`,
    `$E0` -- bit fields, not attributes.  **433 of the 704 playfield cells had ink equal to
    paper.**  The asset had NO PRODUCING TOOL, which is how it stayed wrong; it has one now
    (`tools/render_asset.py`), and it carries the palette pair and the build counter.
  - And `renderFrame()` copied the shadow over the attribute file at every reset, so even a
    corrected asset would have been destroyed.  It repaints the BITMAP only now; the
    derivation for a live shadow is `attrRestore()`, which B10 left a named stub and M7.3c
    wires.
  - **THE ROUND ASSET OVERRIDES `build/image.bin`'s defaults.**  The image is a ROUND-80 DUMP
    (TRAPS #43) and its `$82D7 = 5` is round 80's build counter; carried into a round-1 world
    it picks round 80's palette.  The seeding had to move AFTER that line, which the palette
    gate caught: the pair was right and the counter read 5.
  Oracle `tools/render_asset.py` -> `build/attrpaint_fixture.json` (palette, derive,
  no_entity_paint, asset).
- **THE BOSS ROUND END TO END -- THE DIFFERENTIAL, AND THE STATE SELECTION THAT INVALIDATES
  PART OF THE RANGE BEHIND IT** -- MEASURED AND GATED 2026-09-22, M7.7-H13-B11.
  - ***TWO OF THE FOUR BOSS CAPTURES ARE INSIDE A WINDOW THAT SWITCHES THE WHOLE ENTITY PASS
    OFF.***  `$AA6E` reads `($B54B)` and `$AA72 JP nz,$B520` ABANDONS the pass while it is
    non-zero.  `boss.pkl` holds `$35` and reaches zero at frame 107; `bossspawn.pkl` holds
    `$53` and is still at 24 after 120 frames.  And the claim that matters is not a counter:
    an INSTRUCTION census over `$AB00..$AC40` per 400k instructions gives **0 and 0** on those
    two, against **5928** on `bosshit` and **3519** on `r50_48`.  No player tick runs there at
    all, so every *"the player never did X on round 80"* negative measured on them is partly a
    statement about the settler.
  - **IT IS NOT A BOSS-STATE QUIRK.**  `play1p48` is inside one too (`$B54B = 14`, zero at
    frame 28) -- which is exactly the 28 frames that reconcile B8's `$A98F/$A990` decay:
    `28 + 201/0.5 = 430` against the measured 429.  Check the settler in any state before
    calling it "the round-N state".
  - **AND `bosskilled` IS UNUSABLE FOR A DIFFERENT REASON THAT NO ENTRY NAMED**: its settler
    is ZERO, so a gate that checks only `$B54B` passes it -- but it runs the entity pass
    **once in 120 frames**, because the boss dies at frame 3 and the "WELL DONE!" freeze owns
    the rest.
  - **THE DIFFERENTIAL IS OVER A SAMPLED STATE VECTOR, NOT THE WORLD, AND THE FIXTURE SAYS
    SO.**  A byte-for-byte world diff needs the engine seeded from a capture, which means
    shipping the 48K image, and house rule 7 forbids it.  So **36 fields** are sampled once
    per MAIN-LOOP PASS, each tagged with the increment that owns it, and **5 are tagged
    UNIMPLEMENTED** (`$A85C`, `$A8C2`, `$A8FD`, `$5B00`, `$5B0A`).  All five are STATIC across
    all 1,600 sampled passes on all three states, so the sampled differential is COMPLETE over
    everything that moves -- which is what makes an ownership column a measurement rather than
    an excuse.
  - ***A MAIN-LOOP PASS IS NOT ATOMIC WITH RESPECT TO THE FRAME COUNTER.***  The loop runs
    **8.571 times a frame** on `bosshit`, so **16 of its 600 passes STRADDLE an ISR** and the
    chain members see DIFFERENT values of `($8DBD)`: the boss tick at `$8D2E` reads one,
    `$A09A` at `$8D43` reads the next.  A replay that feeds one value per pass reproduces the
    boss exactly and is off by one on `$A09E`, which reads precisely like an engine bug in the
    effect manager.  The row carries BOTH samples and the gate walks `BB_CHAIN` itself,
    switching the counter where the machine did.
  - **AND A LOOP-TOP ROW IS THE RESULT OF THE PREVIOUS PASS.**  Row *r*'s other fields were
    produced by the chain of pass *r-1*; the input that drove them is the counter sampled
    DURING that pass, not the one sampled beside them.  Aligned the naive way, `$AA00`
    diverges at row 9 with a perfectly self-consistent engine.
  - ***THE ENGINE REPRODUCES THE MACHINE ROW FOR ROW.***  Seeded from row 0 and then fed
    nothing but the machine's own frame timeline, `mainLoop`'s chain walk produces every owned
    field of every later row -- the boss's whole trajectory, the tick divider, the bolt slots,
    the comparator pair and `$A09A`'s edge operand -- for **59 passes on `bosshit` and 59 on
    `r50_48` with ZERO divergence**.  On `bosskilled` it matches to row 19 and **stops by
    name at row 20, which IS the 80 -> 81 advance**: the frame counter restarts, the HP is
    re-armed to 42 and a FRESH SETTLE WINDOW opens at `$B54B = 87`.  `$97F8`'s counter
    arithmetic is transliterated; the round BUILD it leads to (`$8C5E`) is not, and the **20
    fields that move across that row are the work that increment inherits**.
  - The `r50_48` CONTROL says the sampler is not agreeing with itself: off the boss round only
    `$8DBD`, `$FEC8` and `$A09E` move at all, because every boss arm is gated off.
  - ***THE BOSS KILL PAYS +100 AND +100000 IN THE SAME FRAME, AND NOTHING IN THE PLAN OWNED
    THE SECOND ONE.***  `$8E55 DI / LD A,$10 / LD ($FFEF),A` -- the THIRD byte of the
    four-byte pending field, so `$10` in BCD lands on the 100000s -- beside B6's `$9F05`
    posting `$0100`.  MEASURED with the field SEEDED ZERO (`$80FA` clears it, so "paid a
    hundred thousand" and "paid nothing" are otherwise one row): both at frame 3, P1 goes
    `92 67 05 00` -> `92 68 15 00`.  A port that owns one of the two is wrong by a factor of
    a thousand.
  - ***`$927D` HAS TWO CALLERS AND A CALL SCAN FINDS EXACTLY ONE OF THEM.***  A 48K-wide
    census gives call site **`$9269`** (`CALL c,$927D`, inside `$9250` -- the chain's
    PLAYER-ENEMY pass at `$8D52`) and jump site **`$AA35`** (the boss arm's tail jump).  So
    *"a CALL scan of `$927D`'s callers misses it"* is true of `$AA35` and false of `$9269`,
    and *"entered only via `$AA35`"* is a ROUND-80-ONLY statement.  `$9269` runs 721 / 588 /
    1018 times in 120 frames on `hurryup` / `r50_48` / `bosshit` -- once a chain pass, on
    EVERY round -- but `$92BB` only returns carry on a real overlap, so in play `$927D` is
    entered ZERO times from it.  Park an ACTIVE enemy on P1 and it fires: `$927D` once,
    `$AA35` never, P1's state `$80` -> `$84`.
  - ***`$A824`'s NEGATIVE WAS WRONG, AND THE RIGHT ONE HAS THREE EXITS.***  *"The body never
    entered (`$A832 CP $50 / RET z`)"* conflates two gates.  `$A824` reads `($A839)` and RETs
    at `$A828` when there is no giant; then it is a **SECOND CP-FORM EDGE DETECTOR** --
    `$A82C CP $2A` against **`$A82D`, its own operand**, exactly `$A09A`'s idiom -- and only
    THEN does `$A835` send the boss round home.  MEASURED: `r50_48`/`hurryup` leave at
    `$A828`, `bosshit`/`bosskilled` reach `$A832` 149 times and leave at `$A837`, and
    `peachfall` gets PAST both 9 times.  The body IS entered, 1300 times in 150 frames.
  - **THE ZERO-NEGATIVES ARE PAIRED WITH POSITIVES**, because a zero is satisfied by a port
    that does less.  Poisoned `$5A` and driven 150 frames, `$8ECF`/`$8E3B`/`$FED4`/`$FECA` all
    survive on all five states -- and with the enemy slots zeroed to FORCE a round clear on
    `r50_48`, the round advances to 51 and **`$8E3B` and `$FECA` fire**.  The same recipe on
    `hurryup` clears nothing, recorded rather than hidden.
  - ***AND `($FED4)`'s NEGATIVE IS STRUCTURAL, NOT STATISTICAL.***  A 48K-wide census finds NO
    direct store to it at all and exactly ONE 16-bit pointer load, at **`$8E0A`** -- which is
    the MUSIC CALL `$9690` patches to `$C9` on the 48K branch.  There is nothing to make fire,
    which is a stronger statement than "it did not fire in N frames".
  - **RETRACTION -- the entry's own proposed trap is backwards.**  It offers *"A DECAY'S
    INVARIANT IS ITS COUNT, NOT ITS FRAME"* for `$A98F/$A990`.  B8 established the opposite
    and B10 confirmed it: the COUNT equals the start byte through `$AA9C`'s zero guard and is
    identical on every round, and the FRAMES carry the rate.  The entry's frame-numbered
    figures (138 and 430) differ from B8's (137 and 429) by the one frame the settle window
    explains.
  Oracle `tools/bossround.py` -> `build/bossround_fixture.json` (settle, passdiff, anchors,
  million, second_caller, paired_negatives).
- **THE ENDGAME, AND THE LAST DARK RANGE IN THE MAIN-LOOP CHAIN** (`$A09A`, `$A0E0`, `$A0F5`,
  `$A127`, `$8C28`, `$97F8`, `$984B`) -- MEASURED AND GATED 2026-09-22, M7.7-H13-B10.
  **`$A09A` IS NOT "LIGHTNING"**, which is what the port's chain stub called it from B0 until
  this increment read it.  It is a two-armed FULL-SCREEN EFFECT MANAGER, and it is now the
  eighth wired entry in `BB_CHAIN`, at slot 10.
  - **THE CP-FORM EDGE DETECTOR, AND A ROUND-1 WORLD CANNOT TEST IT.**  `$A09D CP $2A`
    compares against **`$A09E`, which is its own operand**, and `$A09F` writes the play timer
    straight back into it.  The tape holds `$2A` -- **and so does `play1p48`**, the state a
    lazy gate reaches for, so on a round-1 world "the constant `$2A`" and "live state" are the
    same row.  Censused over eight states, SEVEN differ: `boss $43`, `bosshit $58`,
    `bosskilled $DD`, `bossspawn $C9`, `r20_48 $9B`, `r50_48 $BD`, `round1_48 $E7`.  Same
    class as `$AA00`.
  - **AND "ONCE PER VIDEO FRAME, WHICH IS THE CP-FORM'S WHOLE PURPOSE" IS FALSE ON SIX OF
    EIGHT STATES.**  Measured edges per frame over 60 frames: 1.000 (`r20_48`, `round1_48`),
    0.983 (`boss`, `bosshit`), 0.967 (`r50_48`), 0.367 (`play1p48`), 0.350 (`bossspawn`),
    **0.050 (`bosskilled`)**.  The detector fires when `($8DBD)` CHANGES, and what drives
    `($8DBD)` is not the frame clock (TRAPS #48).
  - ***`$A0E0` MASKS 704 ATTRIBUTE BYTES, NOT 384.***  `$A0E7 CALL $A0ED` and
    `$A0EA CALL $A0ED` -- and **`$A0ED` IS THE NEXT INSTRUCTION**, so the second CALL returns
    INTO the loop and the routine falls through for a THIRD pass.  `B` is `$C0`, then 0, then
    0, and TRAPS #45's `DJNZ` with `B = 0` runs 256 times: **192 + 256 + 256 = 704**, and
    **`$5840 + 704 = $5B00` exactly**.  MEASURED: 704 writes over `$5840..$5AFF` from ONE
    writer PC (`$A0F0`).
  - ***AND THE REASON IT IS SAFE IS NOT "BITS 0-2 ARE UNTOUCHED" -- `AND $F8 / OR E` CLEARS
    AND REWRITES THEM.***  With the display seeded `$5A`, `D/E = $F8/$00` gives a uniform
    `$58` and `$F8/$03` gives `$5B`: the seed's low bits are gone both times.  It is safe
    because it writes the **DISPLAY attribute file and never the colour shadow** -- ZERO
    writes into `$F800..$FAFF` with the shadow seeded differently -- and because **`$8C28`
    re-derives all 704 from the shadow afterwards**.  H3/H4/H5's three lives of the colour
    shadow are untouched by construction, not by luck.
  - `$A0C5 LD DE,$0042 / JR $A0E0`, which no entry mentioned, makes **D zero**, so the
    thunder's last three steps paint all 704 cells FLAT `$42`.  The flood's `$002F` does the
    same with `$2F`, and the flood enters **the same body at `$A0ED`** with `B = $20` and its
    own HL -- 32 writes at `$5AE0..$5AFF`.  One routine, two doors (TRAPS #52's dual).
  - **THE THUNDER** (`$FECF`, armed by I6's item type 8 at `$88D5`) is a counter with four
    thresholds, stepped from 1 to the wrap in a BUILT world, 255 steps: it paints on steps
    30, 62, 94, 126, 158, 190, 222 -- every 32nd, from `$A0CA AND $1F / RET nz`, FOUR flashes
    each with a fresh RNG ink -- reaches `$A0F5` on steps 238..253 (`CP $F0`), goes FLAT `$42`
    on 251..253 (`CP $FD`), and **WRAPS at 254**, where the INC's Z flag tail-JPs to `$8C28`.
    The `CALL nc` at `$A0BA` reads the carry from `$A0B8`'s `CP $F0`, **not** from the INC --
    `INC A` does not touch carry -- and the `JP z` at `$A0BE` reads the INC's flags back off
    the stack, pushed at `$A0B7` BEFORE the CP.
  - **THE FLOOD** (`$FECE`, armed by I6's item type 7 at `$8843`) had to be driven on a CROSS
    round -- the boss round cannot serve, `$8A16` forces its power-up type to 13 so no water
    cross exists there.  On `redcross` (round 8), 139 steps from an arm of 1: `($FECE)` climbs
    by 3 until it passes `$AF` and then by a **net ONE** (`ADD 3 / SUB 2`), so it crawls the
    last stretch.  57 steps paint one 32-cell row each at **`$5AE0 - (A & $F8) * 4`**, walking
    UP the screen through 22 distinct rows; steps 84 and 85 are the `$C8..$C9` window and JP
    to the payload; **step 138 is the ADD's CARRY**, which disarms at `$A154`.  **WHEN BOTH
    ARMS ARE ARMED THE FLOOD WINS**: `$A0A7 JR nz,$A127` leaves before `$A0A9` ever reads
    `($FECF)`.
  - `$A0F5`, the payload both arms reach: DI, twelve slots at `$FED8` **stride TEN**,
    `(IX+3) := 10` and `SET 3` / `SET 1` on `(IX+7)`, EI.  36 writes from
    `$A0FF`/`$A102`/`$A106` over 24 addresses -- the two SETs are separate read-modify-writes
    -- and slots 12 and 13, past the twelve, are LEFT ALONE.
  - **`$A110` IS NOT PART OF `$A09A`.**  Its only 16-bit reference in 64K is `$88C1` -- item
    effect type 6, already recorded in `build/puhandlers_fixture.json` as `noret {"6": 41232}`.
    `$A127`, by contrast, has **ZERO** 16-bit references and is reached only by `$A0A7`'s
    relative JR, which is why no operand scan finds it.
  - **`$8C28` DOES NOT COPY THE SHADOW -- IT RE-DERIVES THE DISPLAY FROM IT.**  `CALL $8216`
    then 704 bytes from `$F840` to `$5840`, but `$8C34 BIT 5,(HL)` picks `($8309)` or
    `($830A)`, H3's open/solid palette pair.  MEASURED with the display trashed `$5A` and the
    shadow a uniform `$27`: 1412 attribute writes over `$5840..$5AFF`, 699 of the 704 cells on
    the SOLID entry `$55`, **not one keeps the `$5A`**, and the 64 HUD bytes below `$5840` are
    left alone.
  - ***"AT THE FAR END `$745C = $03E8`" IS SATISFIED BY A PORT THAT NEVER TOUCHES IT.***
    `bosskilled` already reads `$03E8` at frame 0, so the plan's anchor is a tautology of the
    capture.  Seeded to the poison `$BBAA` and driven 460 frames to round 81, **`($745C)` is
    never written**.  The advance itself is real: round `$50` -> `$51` at frame 348, the
    lookahead poison `$5A` -> `$28` (`$9817` stores the reseed UNCONDITIONALLY, so `$FEC7` can
    never hold a sentinel), and `($A839)`, entry 12 of the `$9AC1` clear table, 16 -> 0.
  - ***AND THE "UNACCOUNTED +300" IS ACCOUNTED FOR: IT IS AN ITEM.***  The award trail names
    every writer.  At frame 3 the boss dies -- `$9F56` DECs `($9F62)` to 0 [B6], `$9EF4` sets
    the owner operand `($9F09)`, `$9F05` posts `$0100`.  At 414/416 `($9F62)` is RE-ARMED by
    `$79A8` (B2's self-doubling seeder) and by `$98B2`, where **one `LD A,$2A` feeds BOTH
    `($FEC5)` and the boss HP**.  At 417 `$8809` posts `$0300` from HL loaded through
    `$8801 LD DE,$8649` -- **I6's item point-value table**.  A collected item on round 81, not
    an endgame award, which is why it appears in no entry.
  - **THE CLEAR WALK'S NEGATIVE HALF** (H1 owns the positive): with `$A8DB`, `$AA47`, `$AA48`,
    `$AA06`, `$A82D`, `$9F62`, `$A98F/$A990` and `$A891..$A898` all seeded `$5A` -- they read 0
    in the image, so a seed of zero checks nothing -- `$984B` stops at `$9858` after 19 writes
    from a single PC `$9855`, and **all sixteen survive** with zero overlap.  Two of the 19 it
    DOES clear are `$FECE` and `$FECF`, `$A09A`'s own two arms, which is why this range belongs
    to the endgame entry and not to B0's chain wiring.
  Oracle `tools/endgame.py` -> `build/endgame_fixture.json` (edge, paint, thunder, payload,
  flood, restore, advance, walk_negative).
- **THE DEATH SEQUENCE, AND THE ARROW FROM A DEATH TO A GAME OVER** (`$AB5E`, `$AB64`,
  `$AB68`, `$AB6D`, `$AB76`, `$BF0A`, `$806C`, `$8E2A`, `$927D`) -- MEASURED AND GATED
  2026-09-22, M7.7-H13-B9.  The death tick `$AB3F-$ABD4` has been shipped since M7.4d-iii;
  what it never had is the OUT-OF-LIVES BRANCH, and **no capture can reach it** -- every
  shipped `.pkl` has at least one player in play, so the whole arrow must be BUILT.
  - ***`$AB68 CALL $BF0A` WAS AN UNNAMED OMISSION: THE PORT'S FINAL DEATH LEFT THE PLAYER'S
    LAST FRAME ON SCREEN.***  `$AB5E DEC (IY+$5C) / $AB61 JP p,$AB6B / $AB64 RES 7,(IY+7) /
    $AB68 CALL $BF0A`.  A grep of `web/game.js` and every `docs/*.md` for `AB68` returned
    nothing.  `$BF0A` sets the erase cache from the LIVE position and, having no `RET`, falls
    through into `$BF16` and rubs the sprite out.
  - **AND THE DRAFTED ORACLE FOR IT COULD NOT FAIL.**  The plan said to poison the cache
    bytes `(IY+2)/(IY+3)` and diff the display file.  `$FD82`/`$FD83` have **two ordinary
    per-frame writers, `$A603` and `$A623`**, which wipe the poison at FRAME 1 -- and `$BF0A`
    then writes the live position those two have already put there.  Measured: the cache ends
    `[168, 24]` on the last life and the IDENTICAL `[168, 24]` on a respawn, both equal to the
    live position.  **A port that omits `$AB68` entirely passes that oracle**, and the display
    diff beside it is thousands of bytes of unrelated rendering.  TRAPS #44 in its purest
    form, and the refutation is a fixture row, not a comment.
  - **THE SEPARATOR IS A PC-ATTRIBUTED WRITE LOG.**  Cache writers on the last life are
    `{A603: 2, A623: 2, BF0D: 1, BF13: 1}`; on a respawn `{A603: 11, A623: 11}`, with
    `$AB68`/`$BF0A`/`$BF16` not entered at all.  **Bracketed `$AB5E` -> `$AB6B`** -- the
    instruction where both arms converge -- the last life writes **83 bytes, 48 of them
    DISPLAY** (from `$A5A8/$A5AC/$A5B7/$A5C4/$A5C8/$A5D3`) and the respawn writes **ONE**,
    `$AB5E`'s own `DEC`.
  - ***`$AB64` CLEARS BIT 7 BEFORE `$AB68` RUNS, SO "OUT OF PLAY, SKIP THE ERASE" IS EXACTLY
    THE WRONG OPTIMISATION.***  `(IY+7)` reads `$64` at the CALL.  `$A447` diverts a
    bit-7-CLEAR slot to `$A437`, the bookkeeping arm, which erases nothing -- `$BF16` gets the
    erase anyway by FORCING `(IY+7) := $C0` across the call and restoring it at `$BF35`.  The
    forced value satisfies `$A451` (bit 7 set), `$A456` (bit 3 clear) and `$A45E` (bit 6 set,
    tested before `$A45A` sets it); that is what the constant is FOR, and the port now models
    those three tests instead of transcribing their outcome.
  - `$BF16` is **`bbEraseSprite`, not `bbEraseEntity`**: `$BF23` writes `$C3` over `$A480`, so
    the THREE-column shifted path always runs.  At an even sub-position the two are
    BYTE-IDENTICAL -- `$AA4F[0]` is `$00`, so the third column computes
    `(disp & $FF) | (shad & $00)` and stores what was already there -- and they differ ONLY in
    the store count, 48 against 32.  No byte comparison anywhere can see that; the machine's
    write log can.  A behavioural no-op, corrected for faithfulness and recorded as one.
  - ***ON THE LAST LIFE THE DYING PLAYER'S OWN LIVES PANEL IS NOT REPAINTED.***  `$AB6D CALL
    $806C` runs on BOTH arms, and so does its shared tail `$8097` (twice each way) -- but
    `$8097` is `RET p` and refuses a player whose `+7` bit 7 is CLEAR, which `$AB64` cleared
    two instructions earlier.  Bracketed `$AB6D` -> `$AB70`: **12 writes and ZERO panel cells
    on the last life against 104 writes and 24 cells (`$50E0..$57E2`) on a respawn** -- and
    the eight icon bytes `$85B1..$85B8` are copied EITHER WAY, so a count of "did `$806C` run"
    sees nothing.  The pixels are HUD/M7.1; B9 leaves a NAMED COUNTED STUB and the measured
    shape, so the HUD increment inherits a test rather than a note.
  - **THE INVARIANT IS 76 FRAMES FROM THE ARM, NOT "FRAME 79".**  `$8E2A` ORs `($FD87)` with
    `($FD91)` and `RET m` leaves if either is in play; otherwise `$8E36` latches
    `($FEC9) := $B4` and `$8CFC` INCs it once a frame, so the span is `256 - $B4 = 76` BY
    ARITHMETIC.  Measured: `bosshit` arms at frame 4 and wraps at 80, `r50_48` arms at 6 and
    wraps at 82 -- **different frames, the same span**.  Assert the seed and the rate.
    `($FEC9)` must be seeded 0, not `$B4`, or the latch is invisible (TRAPS #44).
  - `$AB76 LD A,($8609) / SUB $50 / JR nz / LD ($8CB0),A` stores the SUB's OWN zero -- the
    comparison and the constant are one instruction.  Driven with `$8CB0` poisoned `$AA`:
    `$AB7D` fires once on `bosshit` (writers of `$8CB0` are `$8A0B`, `$8A10`, `$AB7D`) and
    NEVER on `r50_48`, where the byte keeps its poison.
  - **NEGATIVES, on BOTH rounds, each with its frame count (120) and its seed:** `$8E3B`
    never written, `$8ECF` never written, `($FED0)` never written (so `$927D`'s heart arm is
    unreachable without a poke), `($FED4)` never written during a 48K game over [B1], and
    **`$9573` entered ZERO times by a PLAYER death** -- the 6.9 s busy wait belongs to the
    BOSS death [B2], so a port sharing one "death delay" between them is wrong in both
    directions.  `($FECA)` is rewritten **35 times on round 50 by `$8EC1` and not once on
    round 80** (`$8EAA` is skipped when `($8609)` is `$50`): that row is what makes the
    boss-round negatives mean anything.
  - **MEASURED AGAINST THE PLAN:** the respawn raises the hurry-timer reset request
    (`$9160 := 1` at `$ABB1`) on both rounds, and **round 80 CONSUMES it** within 120 frames
    (`$9164` writes it back, ending 0) while **round 50 leaves it PENDING at 1**.  The plan
    expected the opposite.  Recorded as measured; the mechanism is not claimed.
  - **THE GUARD IS THE CALLER'S, NOT THE ROUTINE'S.**  With `(IX+$5A)` already `$84`, `$927D`
    STILL rewrites `(IX+4) := $50` -- two writes, from `$9290` and `$9293`.  A port that
    guards internally gives the player a rolling death timer under a resting boss.  And the
    respawn's invulnerability really does protect: the separating input is a respawn **parked
    on the boss's own tile**, which no capture contains -- same X, same Y, bit 3 set gives
    nothing at all and bit 3 clear gives `+$5A -> $84` and `+4 := $50`.  Without that input,
    "it protects" and "the boss simply missed" are the same green row.
  Oracle `tools/bossdeath2.py` -> `build/bossdeath2_fixture.json` (chain, ab68, panel,
  negatives, guard).
- **THE DAMAGE MODEL -- AND THE FIRST TIME EITHER ARM WAS SHOWN TO *REACH*** (`$9F29`,
  `$9D77`, `$9E71`/`$9E9E`, `$A98F`/`$A990`, `$9D83`) -- MEASURED AND GATED 2026-09-19,
  M7.7-H13-B8.  B5 transliterated boss -> player and B6 player -> boss; every measurement in
  both was an isolated `h.call`, so *"the rule is right"* and *"the rule never runs in play"*
  were the same green row.
  - **A BOLT DOES REACH THE ACCEPT SET IN FAIR PLAY, WITH NOTHING POKED.**  Eight independent
    key scripts on `build/bosshit.pkl` (round `$50`), pressing P1's own keys read from the
    live `$B5FD` table, 600 frames each: **18 bolts, 395 hit tests, 4 decrements of
    `($9F62)`**, with damage in ONE of the eight runs.  The cells are reported as a HISTOGRAM
    WITH ITS N -- `{(-3,-2): 3, (0,-3): 1}` -- because ONE KEY SCRIPT IS NOT A DISTRIBUTION
    (TRAPS #84): two independent measurement passes each ran one script family on this state
    and each declared the OPPOSITE cell "the case fair play produces".
  - **FOUR OF THE EIGHT SCRIPTS NEVER PRODUCED A BOLT AT ALL** -- their pops emitted class 0,
    so `($FFF9)` never became 3.  The bolt supply is intermittent in a way nothing in the
    port yet explains; what sets the pop class is carried as an OPEN item, not asserted.
  - **THE ACCEPT SET IS SIX CELLS OUT OF 768, AND ALL 768 ARE SWEPT.**  B6 swept 11x11; that
    cannot say what the other 647 tiles do, and "accepted" and "never reached" are the same
    row in a sweep that never visits the rejects.  6 accepted / 762 rejected at boss (20,9)
    and (26,19); **3 / 765 at (2,3)**, where the `bossX-3` column is off-screen.
  - **A BOLT SQUARELY ON THE BOSS DOES NOTHING.**  The bolt draws 16x16 over tiles
    `[tx, tx+1]` and the boss 32x32 over `[bx, bx+3]`, so **25 placements put visible pixels
    on the boss and exactly ONE of them, `(0,-1)`, is a hit**.  The other five accepted cells
    draw the bolt entirely clear of it, up to 24 px left and 24 px above.  The fixture carries
    the cross as a derived table, so a later "fix" into a bounding box fails a named row.
  - **THE STRIDE STEPS OVER ACCEPTED COLUMNS, BECAUSE THE BOSS MOVES TOO.**  `$9D77` adds
    exactly one tile per test, so a static reading says the bolt visits every column of its
    row -- and it does, 28 consecutive columns.  But `dx = boltTile - bossTile` jumps by 0, 1
    OR 2, and a measured flight goes `-4 -> -2` and `-1 -> +1`, **stepping over BOTH accepted
    columns in one flight** (28 tests, HP 42 -> 42).  The other flight dwells on `-3` instead
    and takes the boss 42 -> 37.
  - **THE DAMAGE PER ALIGNMENT IS NOT ONE.**  `$9F57` replaces the pushed `$9ED0` with the
    award tail, so the bolt does not move on a damaging frame and DWELLS: the fair-play dwell
    histogram is `{1: 1, 3: 1}` and one bolt scored FIVE.  A port that hard-codes "one hit,
    one HP" is wrong about the kill time, which is the only thing this behaviour is for.
  - The cadence is **two frames per test** -- 111 of the 118 gaps in one 600-frame run are
    exactly 2 -- from `$9E56`'s once-per-frame edge detector on `($8DBD)` and `$9E5C`'s
    every-other-frame toggle.  An engine that ticks the bolt every frame doubles the damage.
  - **THERE ARE TWO ROUND-80 GATES, NOT ONE, AND ONLY `ellight` SEPARATES THEM.**  `$9E71` in
    the TICK decides whether the bolt slots run at all; `$9E9E` inside the SLOT decides
    whether a running bolt tests the boss or scans for enemies.  Injected with the same
    class-3 request: `bosshit` (round 80, element 3) runs 118 slots and 17 hit tests;
    **`ellight` (round 17, element 3) runs 118 slots and ZERO hit tests**; `r20_48`
    (element 2) and `r50_48` (element 0) run 0 slots, because `$9E71`'s other arm dropped them
    before `$9E9E` was ever reached.  **A PASSIVE control round is an EMPTY ROW** and is
    recorded as one: `r50_48` driven by the same script blows 7 bubbles and its element is 0,
    so "no boss damage there" is the absence of a lightning bubble (TRAPS #50).
  - ***THE PORT SHIPPED EVERY BOLT AT HALF SPEED.***  Nothing ever seeded **`$9D83`**, the
    third `ADD A,A`, so it read as a NOP and the stride was FOUR pixels a tick instead of
    eight -- half the range before `$9ED3`'s despawn, half the columns tested.  B6 named the
    byte, measured that the tape and the round-80 dump both hold `$87`, and gated the READER
    -- but **the gate seeded the byte itself**, so it could not see that nothing wrote it
    (TRAPS #61).  Found by driving `boltSlot` without seeding anything.  Now seeded at reset
    beside `$A98F/$A990`.
  - **RETRACTION -- `$A98F/$A990`'s "55 and 201 decrements" IS NOT AN INVARIANT.**  `$AAA1`
    decrements to zero and `$AA9C`'s zero guard stops, so **the count EQUALS the start byte**:
    `play1p48` starts `[$37, $C9]` = `[55, 201]` and takes `[55, 201]`.  It is `$37` and `$C9`
    restated through a guard, and it is the same on every round.  **The FRAMES are the only
    rate-carrying observation** -- 137 and 429 on `play1p48` -- and every later capture
    (`r20_48`, `r50_48`) already holds `00 00`, which is why the port must SEED the tape value
    rather than read one.
  - The correction this increment owns: `web/game.js`'s `$AA60` comment used to read *"the two
    player slots read `$A98F`/`$A990` -- below the table, and harmlessly"*.  Both halves were
    wrong.  `$A891 + $FE` and `+ $FF` are 254 and 255 bytes **FORWARD** of the table, and they
    are not data -- they are the two instruction bytes `$A987`'s own `CALL $A98F` lands on.
    What IS harmless is the effect on the walk: `$AAA2..$AAB5` sends both player slots to
    `$AAB6` regardless, so the pair's sole consequence is through `$A969`.
  Oracle `tools/bossdamage.py` -> `build/bossdamage_fixture.json` (accept_map, overlap,
  fairplay, stride, offround, decay).
- **THE POP-EMIT TAIL AND THE AWARD FORK** (`$B6F2`, `$B75C`, `$B7E5`, `$B816`, `$A437`) --
  MEASURED AND GATED 2026-09-19, M7.7-H13-B7.  **This is where a popped bubble becomes a
  request, a corpse, a mask and a score.**
  - **THE CLASS TRAVELS THROUGH AN OPCODE.**  `$B6F5` writes `(IY+9)` into **`$B742`**, the
    operand of `$B741`'s own `LD A,3`, and then ZEROES `(IY+9)` -- so by the time the fork
    reads the class, the slot it came from no longer has it.  A PROVENANCE DIFF CANNOT FIND
    THIS: the tape holds `$03` there and the round-80 dump holds `$00`, neither of which is a
    class.  The pool census settles which classes are real: `elwater` carries 2s, `ellight` 3s,
    `elfire` 4s -- a static enumeration of the `(IY+9)` writers once concluded classes 2 and 4
    were unreachable and `$9460` was dead code.
  - **THE MAILBOX IS ARMED ONLY WHEN IT IS EMPTY.**  `$B73D` tests `($FFF9)` -- the request
    B6's `$93DC` consumes -- and a pop that finds one pending drops the class, the owner and
    the position on the floor and goes straight to the award.  Armed, it writes class into
    `($FFF9)`, owner into `($FFFA)`, `(IY+5)` into `($FFF7)` and `(IY+6)` into `($FFF8)`.
  - The OWNER is `(IY+7)` bit 4 folded to **1 or 2** by `RRA x3 / SUB 1 / ADC A,1` at `$B72E`,
    parked in `($B796)` -- which is `$B795 LD A,n`'s OWN OPERAND -- and the same bit is parked
    again at **`$B7C2`**, a second operand.  `$B738 BIT 1,(IY+7) / RET z` gates everything
    after the sparkle seed, so a bubble that merely expires seeds particles and stops.
  - **`$B816` RETURNS HL, AND `$B771` STORES WHATEVER IT LEFT.**  `$B761 LD HL,1`,
    `$B766 CALL z,$B816`, and `$8BC2` ends with **HL = `$0100`** -- so a class-1 pop pays ONE
    HUNDRED and class 0, which takes the same `JR c` arm, pays ONE.  MEASURED at the pay site
    with the field seeded zero (`$80FA` clears it at `$8164`, so an unseeded run cannot tell
    "paid ten" from "paid nothing"): `[01 00 00 00]` for class 0, `[00 01 00 00]` for class 1,
    `[10 00 00 00]` for class 2 and up, and 45584 -> 45684 / 45594 / 45585 through the HUD.
    A port that treats the corpse as a void call pays a class-1 pop a single point; one that
    fills the field big-endian pays 25,600.
  - `$B7E5` is the **EXTEND/power-up mask**, called from class 5 up (`CP 5 / CALL nc`), so
    class 4 -- the FIRE bubble -- leaves both player masks alone.  `SUB 5` indexes H6's
    EIGHT-byte table at **`$B80E`** and ORs the byte into `$FDE3 + 10p` with
    `p = (($B796) - 1) & 1`, then raises `($FED5)`.  **THERE IS NO BOUNDS CHECK**: class `$FF`
    indexes `$B80E + $FA = $B908`, which is code.  The OR matters -- a port that assigns loses
    every letter already collected.
  - **`$B816`'s index is the BUBBLE'S OWN `(IY+8)`**: `IY := $FD94 + 10*(IY+8)`, and there is
    no active check anywhere on the path -- on `build/boss.pkl` every entity slot reads
    `(IY+7) = $20` with bit 7 clear and the corpse is written anyway.  THE ENEMY ARRAY IS ONLY
    SEVEN SLOTS: MEASURED at k = 7 the corpse lands on `$FDDA`, P1's status record, and at
    k = 8 on `$FDE4`, P2's, with no complaint from anything.
  - **A KILL COSTS `($AA5F)` MINUS ONE FOR A LIVE ENEMY AND MINUS TWO FOR AN EMPTY SLOT.**
    `$8C51`'s final repaint reaches `$A437` -- `BIT 5,(IY+7) / RET nz / SET 5 / LD HL,$AA5F /
    DEC (HL)` -- THROUGH `$A447`, the entity master, which **diverts to `$A437` when bit 7 is
    CLEAR** (`$A451 JP p`) or bit 3 is set (`$A456`), and otherwise falls on to the erase/draw
    and never reaches `$A437` at all.  [CORRECTED 2026-09-22 in B9: this sentence used to read
    "returns early when bit 7 is SET", which is the mechanism inverted.  The measured table and
    the shipped code were right; only the explanation was wrong.]
    Modelling `$A437` alone charges a live enemy twice.  MEASURED over eight `(IY+7)` values
    with `($AA5F)` SEEDED `$77`: `$00` and `$40` give `$75`, everything with bit 7 or bit 5 set
    gives `$76`.  [M7.51: and a FROZEN enemy -- bit 3 set -- with bit 5 clear gives `$75` too, which
    the port charged `$76` until M7.51 (it tested bit 7 alone); `tools/corpserepaint.py`.]  The
    oracles' states read `$00` there -- taken between entity passes -- so an unseeded run wraps to
    `$FF` and reads as garbage.  NOT every shipped state reads `$00` (read directly from the 57
    `build/*.pkl`): four were captured MID-PASS inside `$A447` and read `$05..$09` (`r6_48`,
    `r30_48`, `r60_48`, `round1_2p48`), the Boris rounds read `$FE`/`$FF` (`boris`, `peachspawn`,
    `extcomp` -- his `$91D6 CALL $A447` counts it down OUTSIDE the pass), and the front end holds
    the tape's `$2A`.  `$8BF3` then overwrites
    `(IY+7)` with `$8C|dir`, clearing bit 5 again, so THE FLAG CANNOT TELL WHICH ARM RAN: only
    `($AA5F)` can.
  - `$B774`'s `LD HL,0` is a SELF-MODIFIED OPERAND written by `$B6E0 LD ($B775),HL` and holds
    a COLOUR SHADOW address (`$F8F5` on `build/boss.pkl`), so `$B774..$B78D` is a 4x4 cell
    window around the popped bubble and `$B7A1` is the CHAIN POP -- carried as a named counted
    stub until M7.45, which wired the real walk (`bubbleChainPop` / `bubbleChainMark`).
  Oracle `tools/popemit.py` -> `build/popemit_fixture.json` (fork, mailbox, corpse_index, rng,
  census, negatives, aa5f_arms).
- **THE ELEMENTAL BOLT** (`$93DC`, `$941B`, `$9E50`, `$9E90`, `$9D77`, `$9F29`, `$9EE7`) --
  MEASURED AND GATED 2026-09-19, M7.7-H13-B6.  **The only thing that damages the boss.**
  - **THE HIT WINDOW IS NOT A BOX.**  `$9F2D` accepts tile X in **{bossX - 3, bossX}** and tile
    Y in **{bossY - 3, bossY - 2, bossY - 1}** -- so `bossX+1`, `bossX+2` and **the boss's own
    row** all MISS.  Every AABB model disagrees, and the separating input is a bolt at
    **(bossX+1, bossY-2)**: inside the boss's own 4x4 sprite, and not a hit.  Swept 11x11 at
    (20,9), (2,3) and (26,19) -- at bossX = 2 the `bossX-3` column is off-screen and only three
    offsets survive, which is why one position cannot serve.
  - `$9F33` compares against **`$A8DB`, the draw instruction's own operand**; there is no
    separate boss-X variable.  `$9F53 LD HL,$9F62 / DEC (HL)` is the SOLE HP decrement.
  - **THE BOLT DOES NOT MOVE ON THE FRAME IT DAMAGES THE BOSS**: `$9F29` pushed `$9ED0` (the
    physics) and `$9F57 LD HL,$9EE7 / EX (SP),HL / RET` replaces it with the award tail.  The
    same bolt on round 20 moves 160 -> 152; on round 80 it stays at 160.  The draw runs either
    way, so an end-of-frame screen comparison sees nothing.
  - **THE BOSS HIT SUPPRESSES THE ENEMY KILL**: `$9F51 SCF / EX AF,AF'` stashes carry SET, so
    `$9EFE CALL nc,$8BC2` does not fire; the enemy path stashes CLEAR at `$9EE5`.  On round 80
    `$9E9E` jumps the ENTIRE enemy scan, so the suppression and the absence of an enemy are the
    same observation there -- the discriminator is the same bolt on round 20.
  - `$9E50` has **TWO SELF-MODIFIED GATES** before anything: `$9E56 CP n` (n IS `$9E57`), an
    edge detector on `($8DBD)` that makes the body run once per FRAME however many passes the
    loop makes, and `$9E5C LD A,n` (n IS `$9E5D`), an every-other-frame toggle.  Unseeded,
    driving `$9E50` measures nothing.
  - `$93DC` PUSHes `$93F4` as a fake return, and **`$93F4` does two jobs**: it clears the
    request AND sets `($FEC5)` -- the ISR's even-branch gate -- back to 1, which `$93E0`
    cleared on the way in.  523 writes of each in 60 frames and nothing else touches the byte.
  - `$941B` is a two-slot first-fit allocator writing EXACTLY three bytes: `+5`/`+6` are
    `($FFF7)`/`($FFF8)` masked to `$F8` and `+7` is `$80 | (p << 4) | (facing ^ 1)`, the facing
    read from **`$FD87 + 10p`**, so P2's is `$FD91`.  Both slots taken, the request is DROPPED.
  - `$9D77` scales `(IY+7)` bit 0 to +-8 with THREE `ADD A,A`, and the third -- **`$9D83`** --
    is an OPCODE BYTE THAT IS ALSO STATE, poked to `$00` by B8's kind-1 handler to halve the
    stride.  The tape and the round-80 dump BOTH read `$87`, so no image diff can find it.  The
    add to `(IY+5)` is eight-bit with no clamp; `$9ED3`'s bounds (X < 15, X >= `$E7`) despawn
    before the wrap can be reached.
  - `$9E90` refuses an inactive slot, CLEARS the sixteen-bit hit record at `$9EDF` (the operand
    of `$9EDE`'s own `LD DE,nn`) and ERASES -- in that order, before the round decides anything.
  - The award is **`$0100` into the pending field**, paid to `($9F09)` -- the operand of
    `$9F08`'s own `LD A,n`, rewritten by `$9EF4` and read as DATA by `$8E5F`: three consumers,
    one invisible to an operand scan.  A port that writes a literal 0 pays every bolt award into
    the HIGH SCORE slot `$FFE1`.  The field is CONSUMED by the award it feeds.
  - **The erase honours the sub-row and the draw does not**: at Y = `$54` the erase spans THREE
    character rows and the draw still spans two.  In play Y is always `$F8`-aligned, so a
    transliteration that "fixes" either breaks the pairing.  The `$FD00` ROM sinks are
    PERFORMED AND DISCARDED -- row 0 writes 0 display bytes, row 1 sixteen of 32 -- and only the
    COUNT can see it.
- **THE OVERLAP TEST AND THE DAMAGE TAIL** (`$A969`, `$A97D`, `$A98F/$A990`, `$A991`, `$9F5C`,
  `$927D`) -- MEASURED AND GATED 2026-09-19, M7.7-H13-B5.
  - **`$A98F/$A990` ARE TWO BYTES OF LIVE STATE THAT ARE ALSO TWO INSTRUCTIONS INSIDE
    `$A97D`'s OWN CONTROL FLOW.**  The tape holds `37 C9` -- `SCF / RET`, which makes **every
    position an overlap** -- and every boss capture holds `00 00`, `NOP / NOP`, which falls
    through into the real comparator at `$A991`.  There is exactly ONE reference to `$A98F` in
    64K: `$A987`'s own CALL operand.
  - **The decrementer is `$AAA1` in the `$AA60` slot walker**, whose index `($AA57) - 2 -
    ($B57C)` underflows in EIGHT BITS for the two player slots and lands 255 and 254 bytes
    FORWARD of `$A891`.  MEASURED from a cold round 1: **55 decrements of `$A98F` (zero at
    frame 137) and 201 of `$A990` (frame 429)** -- and the SAME 55 and 201 on round 20, so the
    pair's rate is not a function of the enemy count although the hold-off histogram beside it
    is.  `round1_48` is caught mid-decay at `00 69`.
  - **WITH THE PAIR ALIVE A PLAYER NOWHERE NEAR THE BOSS DIES**: boss at (2,3), P1 at pixel
    (200,150), and `(IX+$5A)` goes `$80` -> `$84` with `(IX+4) := $50`.  With `00 00` nothing
    happens at all.
  - **The four corners are four different functions**: `37 C9` hits everything, `37 00` and
    `00 00` are the comparator, and **`00 C9` is `NOP / RET` -- "always miss"**.  The
    intermediate opcode pairs are unreachable (see the decay order) and are a DECLARED gap.
  - `$A969` asks **P2 FIRST** and returns with IX holding whichever player matched, which is how
    `$AA35`'s tail jump into `$927D` knows who to kill.  BOTH axes must match; the Y is asked
    first and `$A98B` falls through for the X.
  - The accept set is **exactly the boss's own 4x4 tile box** -- swept over all 768 tiles at
    (20,9) and at (2,3), where the left wall would truncate a leftward set.  `$9F5C` is
    `RRA x3 / AND $1F`, and the carry the Y axis left is discarded by that mask.
  - **`$A9A3`'s `INC A` group is DEAD CODE**: after the four real compares A is the tile and D
    is boss+3, so it can only match a tile already accepted -- unless `INC A` wraps, and the
    tile is capped at 31.  Entered 72 times in 240 frames and matching none of them.
  - `$927D`: `($FED0)` diverts the whole routine to the weather path (one writer, `$885D`);
    bit 4 (carried) and bit 3 (dying) each refuse; otherwise `SET 2 / SET 7` and `(IX+4) := $50`.
    **It is NOT idempotent on bit 2** -- with `$84` already there it still rewrites `(IX+4)` --
    so bit 2 is `$AA30`'s guard and not this routine's.
  - The damage arm is **never taken in the fight**: over 240 frames `$AA2C` and `$A969` run 72
    times, `$A9AF` (the SCF exit) 6, and `$AA35` and `$927D` ZERO.
- **THE BOSS DRAW AND ERASE** (`$A8C1`, `$A8FC`, `$A9DA`, `$A929`, `$A951`, `$9D4C`) --
  MEASURED AND GATED 2026-09-19, M7.7-H13-B4.
  - **THE ERASE DOES NOT RESTORE THE ATTRIBUTES, IT RECONSTRUCTS THEM.**  The bitmap half is a
    straight copy from the shadow (display + `$A000`), but `$A951` falls out of it into `$9D4C`,
    which reads **BIT 5 of the COLOUR SHADOW** and writes `($8309)` or `($830A)` -- the round's
    open and solid attributes -- into the display.  A port that copies `$F8xx` back to `$58xx`
    paints `$00`/`$20`: black on black.
  - `$A9DA` erases FOUR character rows at the LIVE `$A839`, each 8 pixel rows of 4 bytes = 128
    display writes, then 16 attribute cells.  The draw is 128 + 16 = **144 writes, not 128**.
  - **The draw's attribute walk DESCENDS** (`LDD`, `$5997` down to `$5934`) while the erase's
    ASCENDS (`INC E`/`INC L`, eight-bit) -- the same four cells, the other way round, and at
    X = 29 they land on DIFFERENT cells (`$5A00..$59FD` against `$599D..$5900`).
  - `$A8C2/$A8C3` (the sprite) and `$A8FD/$A8FE` (the attribute block) are SELF-MODIFIED
    OPERANDS, both written by the spawn from the class index.  The blocks are `$A890 + 16C`:
    **C = 0, 2 and 3 are real tape data** (shipped as `BB_BOSS_ATTR`; C = 3 is the boss's own),
    **C = 1's block IS the enemy wake-up schedule** `$A891..$A8A0`, and C = 4, 5 and 6 point
    into the draw routine's own opcodes.  The TAPE leaves `$A8FD` holding `$A881`, which is not
    of that form at all: an `LDD` from there walks the spawn routine's source table.
  - `$A8DC` is the HIGH byte of the draw's sixteen-bit offset and has **no writer in 64K**:
    poked to 1 it moves all 144 writes by +`$100`.  `$A901`'s `RET z` is dead in play; built
    with `$A8FE = 0` the draw falls to 128 writes and no attributes.
  - **On `bossspawn` (`$A839 = 0`) rows 0 and 1 divert through the `$FD00` guard's `$01FF`**:
    their bitmap goes to ROM (the draw falls from 128 bytes to 64) and their attributes collide
    on the same four cells, so SIXTEEN writes show as TWELVE distinct.
  - **`$8309`/`$830A` have TWO writers each** (`$82F9`/`$88CD` and `$82F4`/`$88D0`) and neither
    fires during the fight (0 writes in 240 frames).  The effect-7 item sets BOTH to `$2F`, and
    in that world `$9D4C`'s two arms are the same function and the bit-5 test is unobservable.
  - **`$9D4C` has FIVE callers** -- `$9CFC`, `$9D01`, `$9D0B`, `$9D10` (a 2x2 entity painter)
    and `$A961` -- so a gate watching `$5800..$5AFF` globally captures their writes too.  On
    `build/boss.pkl` the other four are entered ZERO times in 120 frames.
  - `$A951` is **not an entry point**: zero `CD 51 A9` and zero `C3 51 A9` in 64K.
  - The eight-bit masks, all BUILT because nothing in play reaches them: the four `LDI`s are
    sixteen-bit while `INC H`/`INC D` are eight (X = 29 costs one extra page); the four `DEC E`
    after them cannot take back a carry (the draw drifts across 16 pages instead of 8); the four
    rows are added to `($A839)` as BYTES; `$A951`'s `AND 3` differs from `AND 7` only for a
    final D in `$21..$40`; and `$A90C`'s three `INC L` wrap inside their page.
- **THE BOSS TICK** (`$A9ED-$AA46`, `$A84D`) -- MEASURED AND GATED 2026-09-19, M7.7-H13-B3.
  - **FOUR GATES before anything moves**, in this order: `$A9F0 CP $50` (the round), `$A9F6 OR A`
    (is the boss present), `$AA04 RET z` (the involution) and `$AA0D RET nz` (the divider).  The
    ROUND gate is first, so a boss-less **round 81 does not spawn**; and a round the boss is not
    on leaves the divider UNTOUCHED, while round 80 ticks it whether or not the body runs.
  - **`$A839` is BOTH the boss's row AND its presence flag.**  `build/boss.pkl` holds 9 and can
    never take the spawn arm; `build/bossspawn.pkl` fires it at frame 38 with A = 4.
  - **The body, in order**: `$AA0E` ERASE (four rows, at the coordinates BEFORE either bounce),
    the X bounce, the Y bounce, the DRAW at the new position, then `$A969`'s overlap test with
    `$AA30 BIT 2,(IX+$5A)` between it and the kill at `$927D`.
  - **The box is TWO REGISTER PAIRS, not two constants**: `$AA11` passes (DE = `$AA47`,
    HL = `$A8DB`, C = 2, B = 27) and `$AA1D` passes (DE = `$AA48`, HL = `$A839`, C = 3, B = 20),
    so **X lands in [2,26] and Y in [3,19]** -- read off the machine by watching the boss move,
    with the velocity flipping at exactly those coordinates.
  - `$AA38` is `new = v + pos; if (new < C || new >= B) { v = -v; new = v + pos } ; pos = new`.
    Driven over all 256 positions for six velocities per axis, the KEPT set is exactly
    **[lo - v, hi - 1 - v] modulo 256** -- for X with v = 3 that is [0,23] **and {255}**, the
    eight-bit add showing through.
  - **THE BOSS IS NOT REPAINTED EVERY FRAME**: 266 bodies in 900 frames, 0.2956 per frame, with
    frame gaps of 3, 4 and 5.  A per-frame differential phases apart on the first move.
  - **NOTHING INITIALISES `$AA47`/`$AA48`.**  They are the two bytes in front of `$AA49`
    (disassembling from them invents `LD BC,$AF01`), each has exactly ONE reference -- the
    `LD DE` that points at it -- and neither the round build nor the spawn writes them.  An
    81-round chained build carrying poisoned `$03`/`$FD` reaches round 81 with them intact,
    survives the spawn and then steps THREE tiles a tick.  The magnitude is whatever the tape
    loaded and is a fixed point of `NEG`.
  - `$A84D` writes SEVEN bytes, and `$A85C` is `$A85B`'s OWN OPERAND -- the routine writes its
    own next argument.  `$A85C := A-1`, `$A8DB := 14`, `$A839 := 3`, `$A8FD/$A8FE :=
    $A890 + ((c*16) & $FF)` and `$A8C2/$A8C3 :=` **0 -> `$5B00`, 2 -> `$C080`, everything else
    (1 included) -> `$FE02`** -- `$A876 CP 2` is an EQUALITY, not a bound.  The table walk is
    eight-bit: index 16 lands back on the base.
  - **`$A8DC` has ZERO references in 64K** -- no store, no read, no pointer load -- and is still
    the high byte of the offset at `$A8DA LD BC,0`: poked to 1 it moves every one of the draw's
    144 writes by exactly +`$100`.
  - **`$A824`'s body is dead on round 80** (`$A832 CP $50 / RET z`): `$A838`, `$A83F`, `$A844`,
    `$A847` and `$A9B1` are entered ZERO times.
  - Across the 80 -> 81 advance `$AA06`, `$A82D`, `$A98F`, `$A990` and `$A8DB` are INHERITED --
    but **`$9F62` is NOT**: `$79A8` rewrites it with its own doubled operand (`$14` on round 81),
    and `$A839` is entry 12 of the `$9AC1` clear table, zeroed by `$9855`.
  - **"dy defaults to -1" and "dy defaults to +1" are behaviourally identical** -- the spawn puts
    Y at its low bound, so `$FF` bounces before the first store.  150 frames are byte-identical
    either way.  A documentation fact with no observable side; do not "fix" it.
- **THE BOSS HP BYTE AND THE DEATH TAIL** (`$8E47`/`$8E4E`, `$8E55-$8E9C`, `$8E9D`, `$9573`,
  `$79A2`/`$98B2`) -- MEASURED AND GATED 2026-09-19, M7.7-H13-B2.
  - **`$9F62` IS SIGNED AFTER THE DEC.**  `$8E4E LD A,($9F62) / DEC A / JP p,$8ECC`: values
    **1..128 are ALIVE** and **0 AND 129..255 are DEAD**.  "Zero means dead" is right on one
    value in 129, and no captured world can show it -- the byte is seeded 42 and only ever
    decremented, so every state on disk holds `$2A`.  Poked over all 256.
  - **The seeder DOUBLES ITSELF**: `$79A2` is `LD A,n` and **`$79A3` IS ITS OPERAND** -- tape
    `3E 05`, `$0A` on a round-80 state, `$14` on round 81.  `$98B2` writes `$2A` on every round
    build.  `$9F62` is `$2A` in every capture, so it cannot tell the two writers apart; `$79A3`
    can.  The byte has FOUR references: two stores, the read at `$8E4E`, and a POINTER LOAD at
    `$9F53` that no store census can see.
  - **The death is not a latch and not a wait**: it returns Z on the frame the HP test sees 0,
    and **23,967,550 T** are spent INSIDE the call -- 23,951,013 of them in three `$9573` busy
    waits with (A,B) = (3,0), (0,0), (2,0).  `$9573` is `LD C,10 / DJNZ / DEC A / JR nz /
    DEC C / JR nz`: **three counters**, only C its own, B whatever the caller left (0, so 256)
    and A what the PATCHED-OUT music call loaded.  Modelled by counting; exact on a seven-row
    (A,B) grid including (255,255).
  - **NOTHING ANIMATES**: 208 display WRITES over 138 CHANGED bytes, and eleven attribute cells
    `$594B..$5955` of `$C5`.  The boss still on screen is the last frame anything drew.
  - **NINE BYTES ARE NEVER WRITTEN** -- `$8E3B`, `$8609`, `$FEC7`, `$9F62`, `$86CD`, `$8CB0`,
    `$9604`, `$9606`, `$9160` -- asserted from a WRITE LOG, because three of them must hold the
    values that reach the branch and so cannot carry a marker.  `$8ECF` and `$D167` are entered
    ZERO times; the 128K music driver is never executed and must not be disassembled as code.
  - `$8E56 LD A,$10 / LD ($FFEF),A` lands in the PENDING field and `$80FA`'s cleanup at `$8161`
    zeroes `$FFED..$FFF0` immediately after: **the write exists only in the log**.
  - **The award goes to (`$9F09`)**, which is 1 in all four shipped boss states: poked 0/1/2/3
    it pays the HIGH SCORE slot / P1 / P2 / nobody (`$80FA CP 3 / RET nc`, the one path that
    leaves the pending field uncleared).  **Index 0's guard is `$FD7D`**, three bytes below the
    entity table -- `$A0` on every state, so index 0 always passes a guard belonging to no
    player.
  - `$8E9D` is PUSH HL / `$A090` / `$995A` / POP HL / **tail-JP** `$802E`: the same HL addresses
    the attributes and then the glyphs, and BOTH walks are EIGHT BIT (from `$48FA` the eleven
    cells run `$59FA..$59FF` then wrap to `$5900..$5904`).  `$995A` ORs `$40` in, so `$85` is
    written as `$C5` and the instruction's own byte is never the one that lands.
- **THE EXIT AND THE GAME LIFECYCLE** (`$8E2A`, `$8CDC`, `$96DF`, `$97D2`, `$9961`, `$9690`)
  -- MEASURED AND GATED 2026-09-19, M7.7-H13-B1.
  - **`$8E2A` is the only routine in the chain that can end a game**: `LD A,($FD87) / LD
    HL,$FD91 / OR (HL) / RET m`, so a game ends only when bit 7 is CLEAR in BOTH -- else
    `($FEC9) := $B4`.  FORTY-EIGHT of the forty-nine saved states have P1's bit 7 SET (the
    exception is `afterctrl48`, the front end), so this write is unreachable from every capture
    and the gate is BUILT.
  - The loop RETURNS **through the stack**: at `$8CDC` the SP is `$96DD` and the word below it
    is `$8CDC` itself, the literal `$8D05` pushed before the game began.  Armed, it arrives in
    0/0/37 frames on boss/round1_48/play1p48; the control takes 1576/1796 frames or never,
    and when it does arrive it is a natural death, not the trigger.
  - **The screen counts to the EIGHT-BIT WRAP, not to 76**: `$8CFB HALT / $8CFC INC ($FEC9) /
    $8D00 JR nz`.  MEASURED 76/1/128/255/192 frames from `$B4`/`$FF`/`$80`/`$01`/`$40`.  The
    banner is redrawn EVERY frame: nine attribute cells of **`$4E`** at `$594C..$5954` -- the
    instruction is `LD A,14` and the `$40` is added inside `$995A`, so the value read and the
    value written differ.  The GLYPHS go through the ROM charset (`$804A LD BC,$3C00`) and are
    a DECLARED DEPARTURE, like the HUD font.
  - When the counter wraps the machine **falls through into `$8D02`, which is the game's own
    entry point**: re-PUSH `$8CDC`, `CALL $96DF`, `CALL $97F8`.  "Game over" and "start a game"
    are 38 bytes apart.
  - `$96DF`'s reset half clears both EXTEND masks, `$FEC9`, the 16-bit timer, both ISR gates in
    one store, `$8609`, BOTH build counters, and sets `$8A76 := $2A`, `$FED3 := 6`.  **The
    twelve-byte clear starts at `$FFE5`, and that is the point: the HIGH SCORE at
    `$FFE1..$FFE4` is outside it and survives.**  `$FED4` is never written.
  - `$97D2` runs **TWICE** -- once by `CALL` with IY = `$FD80` and once by FALL-THROUGH with
    IY = `$FD8A`.  Fields: `+$5C` 3, `+$5F` 7, `+$60` 0, `+$5E` 8, `+$5D` 8, `+$5B` 2.
  - **`$9961` is the MID-GAME JOIN**, not hurry-up text: `($FED3)` is the credit count, half-row
    `$F7` is read ONCE and rotated TWICE ('1' to P1 at `$999B`, '2' falling on to P2 at
    `$9970`), and **both branches take ONE credit** at the shared `$9980 DEC (HL)`.  A joining
    player gets three lives, `(IY+4) = $50`, bit 7 in both `+$5A` and `+7`, and its OWN four
    score bytes cleared.  Its tail is `$9998 JP $7FC0`, the whole HUD repaint -- `$7FD7`'s 64-cell attribute
    clear (`$AA49`) and the lives panel `$806C` included, made by the port since M7.99b, every write at the
    machine's T from `$9961`'s entry (`tools/jointail.py`: `$7FC0` is entered 708 T in for P2, 753 for P1; the
    tail runs 41,857..58,721 T, so on the machine an interrupt usually lands inside it).
  - `$915F` with its request `($9160)` = 1 stores `$9160 / $9257 / $904D / $8DBD` and then, still inside its
    DI, erases Boris (`IY = $9250`, `CALL $A314`: 32 bytes restored from the shadow at his record's X / Y) --
    on every respawn, wherever the record points (`$88,$A8` when no Boris is out).  Made since M7.99b.
  - **BORIS'S SPRITE IS TAPE DATA, AND PLAY WRITES IT** (2026-10-10): `$FF50..$FF8F`, 64 bytes, masked 16x16, drawn
    by `$A447` from `$91D6` with IY = `$9250` (whose +0/+1 hold `$FF50`).  The port never laid it down until
    2026-10-10 (he drew blank -- the owner's report).  `$B7A1`, a popped bubble's chain mark, indexes the bubble flags
    at `$FEDF + 10 x (12 - marker)` in EIGHT bits, so markers 20..26 land on `$FF8F $FF85 $FF7B $FF71 $FF67 $FF5D
    $FF53`, and `$B7C3` stores (byte OR $0A) AND $EF into any whose bits 7 and 2 are set: `$FF67` `$E6` -> `$EE`
    (tools/tapereads.py: water, round 1; umbrella, round 28).
  - **`$7FC0` is NOT "round 1 only"**: a census of the ADDRESS finds `$7F58 CALL z` and
    `$9998 JP`, so the HUD is repainted whenever a second player joins, on any round.
  - `$FEC9` has **three** writers -- `$8E36`, `$96E9` and `$8CFC`, the last through HL.
  - `$9690`'s three RET patches (`$8DC4`, `$8E05`, `$8E0A`, tape `$F3`/`$0E`/`$21`) are LIVE
    STATE: on 48K all three are `$C9`, which is why `LD A,5 / CALL $8E0A` on the game-over
    screen does nothing on this branch.
- **THE GAME LOOP AND THE PASS CLOCK** (`$8D0C-$8D70`, `$7FFC`, `$8DB5`/`$8DBC`, `$A824`,
  `$A9FC`, `$AA05`) -- MEASURED AND GATED 2026-09-19, M7.7-H13-B0.
  - The loop has **no frame wait**: no `HALT` in its 101 bytes and nothing waits for the
    interrupt, so it FREE-RUNS and the pass rate is emergent.  MEASURED on `build/boss.pkl`:
    **8,548 passes in 900 frames contended (9.498/frame) and 8,674 uncontended (9.638)** from
    the SAME state.  That difference is the only thing that can tell a PASS divider from a
    FRAME divider, so every table is captured on both machines.
  - **The `$AA05` divider's interval is exactly 32 TICKS, not 32 passes.**  In PASSES the
    intervals are 32/35/36/38 contended and 32/38/47 uncontended; a tick is a pass on which
    `$A9FC`'s involution did not latch (13 and 21 latches in 900 frames).  "~3.33 frames per
    body move" is `32 / 9.5`, a DERIVED quantity that moves with the machine (mean 3.374
    contended, 3.331 uncontended, spread 3..5).
  - **`$A9FC` is an INVOLUTION, not a divider**: `op' = f - op`, a 2-cycle whose two operands
    SUM to `($8DBD)`.  From either shipped boss state it latches ZERO times in 300 frames, so a
    capture cannot tell it from a divider; seeded AT THE CALL with `$AA00 := ($8DBD)` the very
    next call latches and then every other one.  `$A824`'s `CP n / LD ($A82D),A` is the other
    idiom -- an EDGE DETECTOR on `($8DBD)`, 898 edges in 900 frames.
  - **`($FEC8)` counts PASSES** and `$8D22 CALL z,$7FFC` fires on its EIGHT-BIT wrap: 33 times
    in 900 frames, at passes 229, 485, 741, ... -- every 256 PASSES, ~27 frames.  `$8DB5` and
    `$8DBC` are each `LD HL,0` WHOSE OPERAND IS THE STORAGE and advance once per VIDEO FRAME.
  - `$7FFC` paints the HUD attributes in **four runs with `INC L`** -- 31 cells of `$47`, then
    10 of 4, 10 of 2, 10 of 5 -- and the `INC L` after each `DJNZ` SKIPS one cell, so `$581F`,
    `$582A` and `$5835` are never written and the walk cannot leave page `$5800`.
  - **`($FECD)` is a SECOND round-advance driver** (`$8D12`): each pass decrements it and jumps
    to `$8D09 CALL $97F8`, so the rounds are fully built and immediately discarded and the
    chain does not run on those passes.  MEASURED on r20_48: 0/1/3 -> 0/1/3 builds.
  - **THE LOOP HAS TWO EXITS.**  `$8D0D`'s game-over gate, and `$8D63-$8D6F` -- half-row `$FE`
    bit 0 (CAPS SHIFT) and half-row `$7F` bit 0 (SPACE), RET when BOTH are held: **BREAK**.
    Both return through the same literal `$8CDC` that `$8D05` pushed (197 and 196 steps against
    a control that does not reach it in 3,000,000).  The third branch is `$8D61 JR z,$8D09` on
    `$8E3A`'s Z flag.
  - **A CALLEE CAN BLOCK A WHOLE FRAME**: `$7E80`'s subtree reaches `$7EC2 EI / HALT`, three
    times in 900 frames on the boss round, and the frame it happens in runs ONE pass against a
    6..12 mode.
  - The twenty chain entries `$8D25..$8D5E` are each reached from THEIR OWN CALL and nothing
    else (1,198/1,198 over 120 frames, the H9 return-address method).
- **THE ENEMY DROP-IN** (`$7336`, `$B520`, `$A430`/`$A42B`) -- MEASURED AND GATED 2026-09-18,
  M7.7-H12.  The engine went in with M7.6/M7.7-a; this is its oracle, and it RETRACTS one of the
  reading pass's own low-confidence claims.
  - `$7336` walks `($AA57) - 2` slots at stride 10 -- **3 to 7**, matching F0's range -- moving
    each enemy's `(IY+6)` into `$73A6+i` as its TARGET and zeroing `(IY+6)`, so every enemy falls
    in from the top.  The count is also patched into `$7460`.
  - `$B520` ramps **+2 per tick on the ODD ISR = 1 px/frame**, each slot toward ITS OWN target and
    stopping there: round 14's seven different targets `[56,104,32,40,48,56,72]` are each hit
    exactly.  **The control matters**: an ordinary FALL is also `(Y+2)` on the odd ISR, so with
    `$B54B` = 0 the same enemies drift to `[58,58,68,66]` instead.
  - `Y <= target` is a property of the ARMING, not the settler: poked ABOVE its target the ramp
    climbs away and never returns.  Two eight-bit INCs, no clamp.
  - `$AA72 JP nz,$B520` abandons the whole entity pass INCLUDING BOTH PLAYERS: with a movement
    key held, P1's X is **constant for 176 frames** (88 ticks x 2) against 100 distinct X values
    in the control.
  - **THE "TOP-OF-PLAYFIELD CLIP" IS RETRACTED.**  `$A42B` is an EXCLUSION -- the entity is
    SKIPPED when its Y lies INSIDE `[base, base+$1E)`, so at low Y it is DRAWN.  `$A430` stores
    its own result back at `$A431`, so the band walks DOWN THROUGH A PASS (+1 twice per visit and
    the erase and draw adds of every entity drawn) -- BEAM AVOIDANCE, not clipping.  It does NOT
    persist across frames, as H12 read it from direct `$A430` calls: `$A3D2` re-seeds `$B9` before
    every pass's first add (CORRECTED M7.49: 2,453 of 2,453 passes in the pop-kill fixture's facts).  FOUR coordinates tested in order (`(IY+6)`,
    `(IY+6)+$10`, `(IY+2)`, `(IY+2)+$10`), any one inside skipping the entity ENTIRELY -- both
    erase and draw.  The tests are EIGHT-BIT, so `$F8`'s `+$10` wraps to `$08`; real play keeps
    both coordinates within 0..168, so nothing reaches it, and the wrap is gated at the method.
- **THE SCROLL-IN** (`$7F30`, `$81E6`, `$8404`/`$8407`/`$840A`, `$8447`, `$9603`) -- MEASURED AND
  GATED 2026-09-18, M7.7-H11.  **M7.1 binds here.**  H2 proved the end state is discarded, so
  every assertion is mid-scroll or a per-routine differential in a synthetic world.
  - `$7F34 JR z` -- **ROUND 1 SKIPS THE WHOLE SCROLL**: the copier is entered ZERO times there
    against **5,112** on every later round.
  - **`$9603` IS SELF-WRITTEN CODE.**  `$7F1B` lays 32 unrolled `LDI`s and a `RET` at `$9603`
    before the scroll -- and those 64 bytes, `$9603..$9642`, **are I1's item block**.  Code during
    the build, item data during play; the `RET` at `$9643` is one byte past the block.  It copies
    32 bytes **whatever BC holds** (nothing tests BC), leaving BC - 32 wrapping.
  - **`$8404`/`$8407`/`$840A` is a CASCADE USING RETURN ADDRESSES AS A LOOP** -- entering at
    `$8404` runs `$840A` FOUR times.  4 pre-roll + 22 content = **26 steps** over 176 pixels.
  - `$840A`: rows 2..22 := rows 3..23, bitmap AND attributes.  **21 table pairs** (`$840E` loads
    `$15`), and **`$843D INC IX / INC IX` advances ONE table entry, so the pairs OVERLAP** -- a
    sliding window.  **5,376 bitmap + 672 attribute writes, ZERO into the shadow.  T = 138,089.**
  - `$8447`: pushes row 23 from the SHADOW, index `$16` minus the step counter -- and **its
    ATTRIBUTE SOURCE IS THE COLOUR SHADOW** (`$8476 ADD A,$F8`, not `OR $58`).  288 screen writes.
  - `$81E6`: the separator row.  **Its fill calls `$AA4A`, NOT `$AA49`** -- one byte past the
    `XOR A` -- so the 32 attributes take `($5AC0)`, the OLD round's colour.  And **`$8203 DEC C`
    is an OUTER COLUMN LOOP**: the eight-row pattern walk runs 32 times, once per column.
  - **`$8584` IS DERIVED STATE WITH A ONE-ROUND LAG**: `$8207` LDIs `$856C`'s eight EVEN bytes
    into it BEFORE `$830B` refills `$856C`, so each round's band carries the PREVIOUS round's
    tile.  Invisible when consecutive rounds share a tile set (one pair in five, `$83EC` mod 5).
  - **The driver writes 163,872 screen bytes** -- exactly the discard H1 and H2 measured from
    outside.  And `$FD44[k] == $FD04[k] + $A000` on all 22 entries, so the two tables are
    indistinguishable until ONE entry is poked apart: `$8447` **follows the table**.
  - UNREACHABLE, asserted as negatives: `$840A`'s 22nd pair (`$FD30` = `$0000`, ROM) and `$8447`
    with k >= 22 (`$FD70` = `$A000`).  A port looping 22 times and a port adding a bounds check
    depart in OPPOSITE directions.
- **THE `$D380` ELEMENT SPRITE BANK** (`$BF39` -> `$BF53` -> `$BF5B`) -- MEASURED AND GATED
  2026-09-18, M7.7-H10.  **It cannot be shipped as an asset**: its content is a function of
  `($7E0E)`, which is redrawn from `LD A,R` on fifteen rounds (H6).
  - `$BF39`/`$BF53`/`$BF5B` are **three routines with ONE entry and no CALL between them**: a
    12-slot pool clear (`$FED8`, stride 10, +7/+8/+9 from **D**, which is zero only because
    `LD DE,10` set the stride, and +3 := 2), then a **28-byte** sparkle clear -- against `$989C`'s
    24 (H1), which is why `$5CFC..$5CFF` survives both -- then the bank.
  - **`$BF5B` zeroes 384 bytes, not 128**: `$AA49` exits with B = 0, so the second `CALL` runs 256
    times (TRAPS #45).  All 384 are overwritten by the `$BF6F` LDIR from `$C780`.  **1456 writes
    into `$D380` on every class**: `$AA4A` 384, `$BF6F` 384, four patch sites 4 each, `$BFC7` 336,
    six shift sites 56 each.
  - The patch: `$BF74 LD A,($7E0E) / SUB 2 / ADD A,A` indexes a twelve-word table at `$C068`.
    `$BFEE` is `LD A,(HL) / RRCA x4 / LD C,A / AND 15` -- **four rotates SWAP the nibbles**, so A
    returns the original HIGH nibble in the LOW position and `LD A,C / AND $F0` the LOW nibble in
    the HIGH.  Four groups of four writes at `$D38C`/`$D38D`/`$D391`/`$D390`, stepping SIX.
  - **THE SEVEN SHIFTS ARE TWO 24-BIT SHIFTS PER SIX-BYTE GROUP** -- bytes 0,1,2, then bytes
    **5,4,3 with byte 5 as the MSB**.  Reproduces all 384 bytes for all thirteen classes; a naive
    48-bit row shift gets 92-98 wrong.  `$C780`'s own blocks 1..7 are NOT the regenerated ones.
  - **DECLARED DEPARTURE.**  Classes 5..12 overlay ROM charset cells and take the substitute
    letters.  **Class 0 overlays `$05E0` -- eight bytes of ROM CODE** (its eight bytes -- not quoted: no ROM byte is written in this repository),
    reached by the 252-byte overrun, and worth **99 of the bank's 384 bytes**; the port overlays
    nothing.  The ARITHMETIC is still exact, and the cost is that the overrun becomes
    unobservable through the bank (a 16-bit index reaches `$C264`/`$02F0`, also a non-letter ROM
    pointer), so it is gated directly instead.
  - **Class 1 is UNREACHABLE** (`$7DD6` leaves C at 0/1/2/3/`$FE` -> classes 2/3/4/5/0).
  - H6's eight-into-six fold has a THIRD witness here: classes 5, 8 and 11 build an identical
    bank, as do 10 and 12.
- **THE POST-`$8216` HUD FURNITURE** (`$7FC0`, `$806C`, `$957E`, `$9904`) -- MEASURED AND GATED
  2026-09-18, M7.7-H9.  The four painters H1 found running AFTER the repaint.
  - **`$7FC0` HAS TWO REFERENCE SITES.**  `$7F58 CALL z` (round 1, gated on `$8609 DEC A`) and
    **`$9998 JP $7FC0`, a TAIL CALL** ending the PLAYER JOIN routine at `$9970` -- which zeroes
    that player's score record, SETs `(IY+$5A)` bit 7 (the died flag F0 uses to suppress the
    warp), SETs `(IY+7)` bit 7 IN PLAY and gives three lives.  **The HUD is repainted on every
    join**, not only on round 1.  There is no unconditional `CALL` to it anywhere.
  - `$7FC0`'s RRD loop makes eight ASCII digits at `$85E9` from the four BCD bytes at `$FFE1`, DE
    walking BACKWARDS, low digit of each byte FIRST -- and **three RRDs per byte RESTORE the
    record**.  1,227 writes, of which the nested `$7FDF CALL $806C` contributes 32 display, 32
    shadow and 4 attributes; `$7FC0`'s own display total is **456**.
  - `$806C`: min(lives,5)+1 cells on display row 23, into DISPLAY, SHADOW (+`$A000`) and
    ATTRIBUTES.  `$8097 RET p` is the IN-PLAY test on bit 7 of `$FD87`/`$FD91`, so **P2's whole
    half is dead in a one-player world**.  TWO SELF-MODS: `$8098` patches `$80F6` with `INC L`
    (`$2C`) or `DEC L` (`$2D`) so P2 walks LEFT, and `$80B9` patches `$80C0`'s operand.  **ONE
    REGISTER DOES TWO JOBS**: `$809D` puts that opcode in C and `$80C8 SUB $28` turns it into the
    attribute INK, 4 for P1 and 5 for P2.  `$80E0`'s `JR z` leaves the attribute alone when the
    PAPER already equals the ink.
  - `$8072 LD BC,$08FF` is ONE instruction and a TRAPS #45 site.  Shipped it writes 8 bytes and
    BC never borrows; poked to C = `$07` it writes **263 bytes over `$85B1..$86B7`**.
  - **`$957E` WRITES SIX BYTES AND NO PIXELS** unless a letter has been collected -- 8 display +
    8 shadow + 1 attribute PER SET BIT thereafter, six bits per player, P2's pass reached BY
    FALLING THROUGH with a self-modified column offset of `$1F` at `$95AE`.
  - **Its glyphs are the SAME SIX ROM CHARACTER-SET CELLS as `$C068`'s** (H6): `e x t e n d`.
    DECLARED DEPARTURE -- `tools/make_letters.py` draws substitutes and asserts every one differs
    from the ROM's.  M8's frame differential must exempt these six cells as it does the score.
  - `$9904` **takes the banner address in HL** (`$484C`, then `$488C`): eight rows of ten bytes
    SHADOW -> DISPLAY, then ten attributes chosen by **bit 5 of the COLOUR shadow**, `$8309` or
    `$830A`.  Twice a round, on every round including 81.
- **THE PLATFORM TILE AND THE WALLS** (`$824A`, `$830B`, `$833A`, `$8390`, `$837A`, `$83EB`) --
  MEASURED AND GATED 2026-09-18, M7.7-H8.  What turns H7's 616 collision cells into pixels.
  - `$83EB`: `$83EC` is an OPERAND and a **BUILD counter mod 5** (never recomputed from `$8609`);
    `($860D) := $6180 + 8 * idx`.  The five 8-byte patterns are TAPE DATA at `$E680..$E6A7`, put
    at `$6180` by H0's `$96AE` cold-start relocation -- **no asset, no departure**.
  - `$830B`: column 2 of all 22 shadow rows, `$A0`/`$50` alternating (**176 writes**,
    `$E042..$F7E2`), then an LDI loop into the buffer's **EVEN bytes only**.  `LD C,$FF` IS LOOP
    CONTROL: LDI does a sixteen-bit `DEC BC`, so a C that could wrap would borrow into B and cost
    the DJNZ a count (TRAPS #45).
  - `$824A`: 16x12 per SOLID cell, IX from the **SHADOW row table `$FD44`** (measured `$FD04` +
    `$A000` on all 22 entries; both start at char row TWO).  **TWO WRITE MODES**: main 8 rows
    STORE the left byte (`$8288`) and OR the right (`$828C`); the 4-row tail ORs BOTH.  The LAST
    map row SKIPS THE TAIL, writing 16 bytes not 24.  The column counter runs 28 per row while
    the map pointer's DJNZ counter starts at **29**, so the map row advance fires one cell into
    the next row.
  - **`$856C` IS TWENTY-FOUR BYTES**: DE runs continuously through both loops.  Three odd bytes
    are patched at `$824A`'s entry (`$A0/$50/$A0`) and REPATCHED by `$82C5` (`$80/$A0/$40`), which
    fires **exactly once**, after the first map row -- the top of a platform against its body.
  - `$8390`: two expansions on a ZERO/NON-ZERO test of `($860C)`.  Zero duplicates each tile byte;
    non-zero BIT-INTERLEAVES it, doubling each nibble into a whole byte (`$8` -> `$C0`) in a
    **linear 32-byte fill** of `hi, lo, hi, lo`.  Through a whole build the branches differ in
    **697 bytes, all in columns 0/1/30/31**.
  - `$833A`: ONE wall per call.  **`$833B` IS STATE AND ARGUMENT** -- `LD A,$1E / XOR $1E` toggles
    it and the value IS the column -- so the two calls in a build draw columns 0 then 30 or 30
    then 0 depending on the PREVIOUS build.  The orders differ **all in column 30**, and the
    COUNT IS PER ROUND, not 5: **42 bytes on round 1, 12 on round 2, 28 on round 20, 20 on
    round 50** (M7.8-A, `$833B` poked to `$1E` and `$00` around a cleared-shadow build; the
    earlier "5 bytes" was wrong).  The non-zero counts in columns 30/31 are IDENTICAL either
    way, so no count-based gate can see it -- and M7.8-A proved that the hard way: the port
    never seeded `$833B` at all, shipped the inverted parity, and no gate noticed until the
    builder was given a call site.  After the FIRST call alone the two arms differ in 704
    bytes across columns 0/1/30/31.
  - **`$833A`'s ROW CURSOR IS ADVANCED BY ITS CALLEE**: `$8375 INC IX / INC IX` is inside `$836A`,
    after the DJNZ.  `$833A`'s own loop has no IX advance, so reading it alone says the wall is
    redrawn over the same two char rows eleven times.  352 writes, columns 0/1, `$E040..$F7E1`.
  - `$837A`: columns 0, 1, 30 and 31 of rows 2..23 marked SOLID -- **88 cells**, H7's four unowned
    columns.
  - Both eight-bit adds (`$827B ADD A,(IX)`, `$835D ADD A,$20`) are TRANSCRIBED NOT EXERCISED:
    enumerated over every reachable input, **neither can wrap**.
- **THE ROUND-RECORD WALKER** (`$848C`, `$8529`, `$84D3`, `$850A`) -- MEASURED AND GATED
  2026-09-18, M7.7-H7.  **The asset-extraction binding**: 81 maps, one continuous bit stream each.
  - `$8529` probes **bit `7 - (i & 7)` of byte `$8543 + (i >> 3)`, MSB FIRST**.  `$9F5C` is
    `RRA/RRA/RRA/AND $1F` -- the carry-in reaches only bits 5-7 and the mask kills them, so it is
    `(i >> 3) & $1F` whatever the flags hold.  **SET = SHORT** (39 bytes, 14 wide, mirrored);
    **clear = LONG** (77 bytes, 28 wide).  **51 short, 30 long.**
  - **THE BIT BUDGET CLOSES EXACTLY, which is why those are the sizes**: 22 x 28 = 616 bits =
    77.0 bytes; 22 x 14 = 308 bits = 38.5 -> 39 with four spare.  51 x 39 + 30 x 77 = 4,299, so
    the table is `$61A8..$7272` with **8 bytes of slack** before `$727B`; round 81 is at `$7226`.
  - `$848C` steps a cursor from 0 adding each record's own size until it reaches `($8609) - 1`,
    so the ADDRESS costs one probe per preceding round and the SIZE is **probed again** at
    `$84BA` for the selected record.  (The two probes read the same bit and cannot disagree.)
  - `$84D3` paints 22 rows from **IX = `$F842` -- row TWO, column TWO** -- one cell per bit,
    `($8309)` for a 0 and `($830A)` for a 1.  **THE BIT CURSOR IS CONTINUOUS ACROSS ROWS**: E is
    PUSHed and POPped around the row advance at `$84FE`/`$8504` so it survives.  A port that
    re-aligns per row is right on row 1 and wrong from row 2 on -- and still produces a map.
  - The width `$84E5` (`$1C`/`$0E`) and row advance `$8500` (4/`$12`) are **SELF-MODIFIED
    OPERANDS**, and 28+4 = 14+18 = 32.  A build of one class never writes the other's pair:
    `image_tape.bin` holds `$1C`/`$0004`, the round-80 dump `$0E`/`$0012`.
  - `$850A` mirrors columns 2..15 onto **29..16, REVERSED**.  Observable only on a SHORT round
    with a non-palindromic row -- **49 of 51**, 3,352 cells.  "28 wide, no mirror" is refused by
    arithmetic on all 51.  The LONG class does not mirror: **all 30** long rounds are left-right
    asymmetric.
  - The record owns columns 2..29 of rows 2..23 ONLY.  Columns 0/1/30/31 are H8's walls and rows
    0/1 are `$81C3`'s ceiling (H3's); the walker writes **exactly 616 cells, `$F842..$FAFD`**, on
    both classes.
- **THE ELEMENT CLASS** (`$7DD6`, `$7E0E`, the lists at `$7E4B`) -- MEASURED AND GATED
  2026-09-18, M7.7-H6.  `$79AC`'s tail is the collision transform, the drift painter, and then --
  **by FALL-THROUGH, with no `CALL $7DD6` anywhere in 64K** -- a per-round element class.
  - `$7E4B..$7E7F` is FOUR `$00`-SEPARATED LISTS of round numbers, **11 / 10 / 13 / 15**.  The
    class is the list index **plus two**: **2 WATER, 3 LIGHTNING, 4 FIRE**; a round in no list
    gets `($FE + 2) & $FF` = **ZERO**; and the fourth list is REDRAWN at `$7E04 LD A,R / AND 7 /
    ADD A,5` into **5..12**, so those fifteen rounds differ BUILD TO BUILD.  The 53-byte table
    predicts F0's 81 chained builds exactly.
  - **`$7DE1 INC (HL) / DEC (HL)` IS A ZERO TEST THAT WRITES**, twice per entry examined and
    always restoring.  A write-watch over `$7E00-$7F00` therefore reports self-modifying code
    that is not there: **0 to 106 phantom writes**, a function of the round's position in its
    list (0 for round `$05`, 106 for every round in no list).
  - **`$7C89 CP $51 / RET z` MAKES ROUND 81's CLASS STALE** -- the treasure room inherits round
    80's.
  - Group 1 alone also stores `$A37D` into `($FDEE)` and `($FDF8)`, on exactly ten rounds.
  - THE FOUR READERS.  **`$9E75` dispatches THREE classes** -- 2 -> `$A159`, 3 -> `$9E85`,
    4 -> `$9F63` -- and 0, 1 and 5..12 fall through (an earlier reading said two).  `$7E80`
    patches `$7EFB`, the operand of `LD (IY+9),n`, with the CLASS ITSELF, and `$7EB2`, a `CP n`
    throttle, with **4 for classes 1..4 and 1 for 5..12**.  `$8A50` picks 7 or 14 over the item
    block.  `$BF74` selects the bubble glyph.
  - **THE EIGHT RANDOMISED CLASSES ARE THE EXTEND LETTERS.**  A popped bubble's `(IY+9)` rides
    `$B742` to `$FFF9`; `$B75C CP 5 / CALL nc,$B7E5` does `SUB 5` and indexes `$B80E` = bits
    `0,1,2,3,4,5,0,5`.  `$957E` draws **SIX** letters over a 6-bit field at `$FDE3`/`$FDED`, so
    **classes 11 and 12 ALIAS 5 and 10 and E and D are twice as likely (2/8) as X, T and N**.
  - **A SECOND ROM FONT DEPENDENCY -- DECLARED DEPARTURE.**  `$BF74` indexes a word table at
    `$C068` by `(class - 2)` and ORs the 8-byte glyph into the flashing-bubble bank at `$D38C`.
    Classes 2/3/4 take RAM icons at `$B614`/`$B61C`/`$B624` (a wave, a bolt, a flame); **classes
    5..12 take SPECTRUM ROM CHARACTER-SET CELLS -- `e x t e n d e d`**.  The aliased classes
    point at the same two ROM letters as the classes they alias, which is the fold confirmed by a
    second, unrelated table.  No ROM is shipped or transcribed; the port substitutes drawn
    letters as the HUD font does.
  - **CLASS 0 IS NOT INDEXED OUT**: `SUB 2` = `$FE`, `ADD A,A` = `$FC`, so the 31 rounds in no
    list read the word **252 bytes past** the eleven entries, at `$C164`.  Recorded, not repaired.
- **THE TRANSITION SPINE'S PIXELS AND ITS TAIL** (`$97F8`, `$9891`, `$9AC1`) -- MEASURED AND
  GATED 2026-09-18, M7.7-H1.  **RETRACTION: the transition is not pixel-free.**
  - THE CENSUS SPLITS AT THE FIRST `$8216`.  **Round 1 discards NOTHING** (0 display writes before
    the repaint -- `$7F34 JR z` skips the scroll); rounds 2, 5, 56, 72, 80 and 81 each discard
    **163,872, IDENTICALLY**.  What SURVIVES is round-dependent: round 81 keeps an order of
    magnitude fewer than the rest, having no banner.
  - FOUR PAINTERS run AFTER the discard.  `$7FC0` on ROUND 1 ONLY (488 display + 129 attribute --
    HUD text and both score panels); `$806C` EVERY round, sized by **LIVES** not by the round
    (32 bytes at 2 lives, 48 at 3); `$957E` CALLED every round and writing **nothing** in a fresh
    build (it walks collected EXTEND bits; a write census would call it dead code); and `$9904`
    **TWICE** per round (160 + 20, the banner restore) -- a painter in no earlier list.
  - **THE `$9AC1` WALK IS NINETEEN POINTERS.**  `$984F LD B,$13`; each `LD E,(HL) / LD D,(HL)`
    pair is read LOW BYTE FIRST and `$9855 LD (DE),A` writes ZERO to the TARGET.  Exactly 19
    writes, all from `$9855`, and **`$9AC1..$9AE6` itself is never written** -- a port that also
    zeroes the table is green on round 1 and writes into ROM on round 2.
  - **`$9891` UNDOES THE DIAMOND PIN, SO THE PIN LASTS EXACTLY ONE ROUND.**  `LD HL,$3CFF /
    LD ($8B9F),HL` restores the item generator's counter AND its `INC A` OPCODE at `$8BA0` in one
    sixteen-bit store; `$9897 LD A,7 / LD ($8BA2),A` puts the mask back.  `$88E0`'s pin
    (`$09/$00/$FF`) therefore survives one round and no more.
  - `$989C` clears **TWENTY-FOUR** sparkle bytes and `$BF53` twenty-eight; **`$5CFC..$5CFF`
    survives both** and holds live runtime-built data (`00 FC 3F C0`) that a 16-slot table would
    consume as a particle.
  - `$98A4 CALL $79AC` is H3's collision transform -- the tail re-runs it.  The tail's three steps
    write DISJOINT regions (`$8B9F..$8BA2`, `$5CE0..$5CF7`, `$F800..$FAFF`), so their ORDER is
    transcribed from the machine and is not observable; recorded as such rather than gated.
  - `$D380` is an OBSERVATION, never a frozen constant: on group-3 rounds `$7E0E` is redrawn from
    `LD A,R`, and two builds of the same round differ in up to 69 of its 384 bytes.
- **THE OCCUPANCY FIELD** (bits 0-4, `$B8C0`/`$B6D6`, `$AE81`) -- MEASURED AND GATED 2026-09-18,
  M7.7-H5.  The THIRD life of `$F800-$FAFF`: bits 0-4 carry the SLOT NUMBER of the bubble sitting
  in that cell, written by `$B8C0` and cleared by `$B6D6`, both PRESERVING bits 5, 6 and 7.
  - **`$BFF7` is the bubble manager's SLOT COUNTER** (writers `$B63C` and `$B674`, values 0..12),
    which is why its value "moves within a frame" -- it IS the loop index, so the marker stored in
    a cell is **`12 - slot`**, and `$AEAD` inverts exactly that.
  - **ONE PROBE, TWO MASKS**: `$AE7F` passes `$3F` (solid OR claimed) and `$AD35` passes `$20`
    (solid alone), both into `$AE81`.  The same cell reads BLOCKED to one caller and OPEN to the
    other.
  - **E IS NOT A BOOLEAN.**  0 = free; 1 = SOLID, which SHORT-CIRCUITS at `$AEA0`; and for a
    CLAIMED cell with `(IY+8)` bit 1 clear, **`10 * (12 - marker)`** -- the POOL OFFSET of the
    bubble holding it.  With that bit SET it writes `(IY+9) := 1` and `$AEAB POP HL / RET`
    **abandons its caller** (the fourth such routine, after `$B679`, `$88B1`, `$89B7`).
  - The walk is **EIGHT BIT** (`INC L`), so a probe at the end of a page finds its neighbours at
    the START of that page; the THIRD cell is gated on **X, not Y** (`$AE86 LD D,E` overwrites D
    before `$AE92 LD A,D / AND 6`); and the marker mask is **`$1F`**, not `$0F`.
  - **A CLAIMED CELL DIVERTS THE DRIFT INTO THE RNG**: `$B87D`/`$B888` test with `AND $1F` and
    `$B88D` draws `LD A,R / AND 6` -- the same 0/2/4/6 code space as the drift field.  So the
    drift map decides direction only when the target cell is FREE.
- **$7E80, THE ELEMENT EMITTER, WIRED -- THE CHAIN'S ONLY HALT** -- M7.22, 2026-09-24.
  `$8D3A CALL $7E80`, the eighth chain entry, and the one that gives a frame away mid-pass.
  - *** **$7EBA FINDS A FREE POOL SLOT, $7EC2 GIVES THE FRAME AWAY, AND $7EC4 ASKS AGAIN.** ***
    The frame it hands over is one the ISR runs in, and the ISR is what fills that pool -- so
    the slot may be gone.  MEASURED both ways by taking it DURING the halt: still free, it
    emits; taken, it emits NOTHING.  A port that treats the HALT as a delay and keeps the slot
    it found is wrong exactly when the game is busiest.  The port has carried `this.blocked`
    for this since B0 on the strength of three measured frames in build/boss.pkl; this is the
    routine that sets it.
  - **AND A FULL POOL DOES NOT HALT AT ALL** -- $7EC1's RET is before $7EC2's, MEASURED over
    every busy count 0..12.
  - **TWO OPERANDS CARRY THE ELEMENT.**  $7EFB is the operand of $7EF8's `LD (IY+9),n`, so the
    class travels into the slot INSIDE AN INSTRUCTION; $7EB2 is the operand of $7EB1's `CP n`,
    set by `CP 5` to 4 or 1.  MEASURED over all sixteen element values: 1..4 are capped at
    four on screen and 5 and up at ONE.  Both stores are AFTER the element's own `RET z`, so
    element 0 leaves both at whatever the last element put there -- live state with a tape
    value ($04 and $03), like every other operand in this port.
  - **THE RETURN ADDRESS IS PUSHED**: `$7ECB LD BC,$7F05 / PUSH BC` means $7EEB's `RET nz` --
    the refusal when the emit point reads SOLID -- lands on $7F05, which puts the even ISR
    gate back.  A `finally` written in 1987, and MEASURED: ($FEC5) goes 0 then 1 on BOTH arms.
  - **THE FRAME GATE READS ONLY THE LOW BYTE.**  `LD A,($8DBD) / CP $2A` is an eight-bit load
    of a sixteen-bit counter, so it fires once every 256 frames and a clock of $012A emits
    just the same.
  - The cap counts pool slots whose +9 is TWO OR MORE, twelve of stride ten from $FED8, with
    `LD C,D` starting the count at zero because D is the high half of the stride.  The spawn
    point is a 0..3 operand at $7ED7 over a four-entry table at **$7F0B** (TAPE DATA, now
    carried): $F84A (80,1), $F854 (160,1), $FAEA (80,191), $FAF4 (160,191) -- and $7EEB tests
    BIT 5 of the byte each pointer names, the colour shadow's SOLID bit, so an emit point with
    a platform on it is refused.
  - Oracle `tools/elemit.py` -> `build/elemit_fixture.json`, with ONE DECLARED SCAFFOLD: the
    HALT is stepped over, which is also where the re-test is driven from.
- **$917C, THE BORIS CHASE, WIRED** -- M7.21, 2026-09-24.  M7.19 left it a named counted
  stub; every pass after the banner has fired lands here through `$904F`'s `JP nz`.
  **SEVEN OPERANDS ARE ITS ENTIRE STATE** and not one of them is a variable: $918B the moving
  latch, $9194 a wrap counter, $919C a 0/1 toggle, $91BC the axis, $91DC the step countdown,
  $91E4 the 0..15 move length, and $91D0 the operand of $91CF's own CP.  Plus $91F8 and
  $921C, which $9037's tail wrote with the TARGET's +6 and +5.
  - **IT WAITS FIVE HUNDRED FRAMES PAST THE BANNER'S OWN THRESHOLD**, not past the banner:
    `LD HL,($745C) / LD DE,$01F4 / ADD HL,DE`.  MEASURED with the live 1500: 1999 and 2000
    decline, 2001 runs.  The add is sixteen bit and WRAPS -- unreachable with any ordinary
    threshold, so it is driven at $FF00 where the target becomes $00F4.
  - **A MOVE STARTS ONLY EVERY FIVE HUNDRED AND TWELVE TICKS.**  $9195's `INC A` on $9194 is
    NZ 255 times in 256 and $91A7's `JR nz` sends those to the HALT; only a WRAP lets $919B's
    `INC A / AND 1` on $919C run, and only when THAT lands on zero does $91A9 start one.
    MEASURED over 1,100 ticks: starts at 512 and 1025.  **Boris is ACTIVATED on tick ONE** --
    `$91A3 SET 7,(IY+7)` is on both arms -- so he is present from the first tick and merely
    still for the first five hundred.
  - **THERE ARE TWO ENTRIES TO THE TAIL, NOT ONE.**  $91CC stores ($8DBD) into $91D0 and then
    falls into the HALT; every `JP $91D4` -- the two `JP nc` in the axis arms and the
    arrival's own jump -- enters BELOW the store.  So a tick that MOVES Boris does not touch
    $91D0: at tick 513, the first step of the first move, the counter stays at 207 while the
    clock has gone on to 209.  **And $91CF's CP is DEAD**: the next instruction is the HALT,
    so nothing reads the flag -- the compare is a comment and the store is the point.
  - Almost every tick costs a frame: **1,098 HALTs in 1,100 ticks**, the two exceptions being
    the move starts, which RET at $91C6.  A move that ends on its COUNTER ($91ED) does not
    halt either.
  - A step is EIGHT PIXELS toward the target on ONE axis, and $9211's `NEG` is what makes the
    test a DISTANCE -- without it a target one pixel above Boris reads as 255 away.  The X arm
    additionally writes the sprite pointer $FF50 every step and the Y arm does not.
  - `$91AE RLC (IY+4)` with `$91B2 CALL c,$91C7` makes the step length climb 2, 4, 8 ... $80
    and then sit at $40.  (RLC against SLA is a PROVABLE EQUIVALENT here: they differ only in
    the bit that comes round when bit 7 was set, which is exactly the case $91C7 overwrites.)
  - **BORIS CHASES AN ADDRESS, NOT A PLAYER.**  Pointing the operands at P2 walks him to P2,
    and at the ROUND BYTE walks him to wherever that number is.
  - Oracle `tools/boris.py` -> `build/boris_fixture.json`, with TWO DECLARED SCAFFOLDS: the
    HALT and the $A447 draw behind it are stepped over (with interrupts off the machine sits
    at the HALT for ever; with them on the real ISR reaches the round advance and leaves the
    bracket at $9781), and the entry SP is pinned because the bracket leaks ten bytes a tick.
    **CORRECTED M7.49:** M7.21 also blamed `$A447` -- erasing at a cached position that is
    garbage on a poked world -- for Boris's record coming back `FE 02 FE 04 FE 06 FE A8 FE 0A`.
    That is the bracket's own sentinels, pushed over $9250 once the SP leak had walked the stack
    down to it (tick 116), with `$91A3`'s bit 7 and `$A447`'s bit 5 on +7; with SP pinned the
    draw runs clean for all 1,100 ticks, cache as poked or not, and phase (g) runs it.
- **THE SUBSTITUTE "HURRY UP !" FONT, AND $802E's BLIT FOR REAL** -- M7.20, 2026-09-24.
  M7.19 left one declared gap: `$802E` prints the string at $9A1C through `$8044`, which
  builds `$3C00 + c*8` -- a SPECTRUM ROM CHARACTER SET cell -- and this project ships no ROM
  transcription.  That gap is closed the way `tools/make_letters.py` closed the EXTEND row and
  `make_digits.py` the score digits.
  - **THE SHAPES ARE A DECLARED DEPARTURE AND THE ADDRESSES ARE NOT.**  `tools/make_hurry.py`
    draws ten 8x8 cells and refuses to emit in BOTH directions: a glyph that reproduces the
    ROM cell it replaces, and ink drawn where the ROM leaves a blank.  Eight of the ten carry
    ink and **43 of their 64 bytes differ**; the two SPACES are eight zero bytes in any font,
    which is named rather than worked around.  The first draft of the `!` was byte for byte
    the ROM's and the tool's own assert is what caught it.
  - The face is a five-wide slab on bits 6..2 against the ROM's six-wide on bits 6..1, so the
    banner is legible and visibly not the original.  **M8's frame differential must EXEMPT the
    ten cells it occupies, and they MOVE**, because the banner climbs the screen.
  - The blit is the machine's: eight rows with `INC H` between them and `INC L` to the next
    column, **both eight bit**, writing 1,680 display bytes over $404B..$57D4 in the machine's
    own order (MEASURED; the first sixteen are $50CB $51CB $52CB ... , the `INC H` walking
    down a column).  **It does not touch the shadow** -- `$804F` writes (HL) and nothing else,
    which is why `$9904`'s erase reads display + $A000 and the printer never does.
  - `INC H`'s mask and the `|`-versus-`+` spelling are both PROVABLE EQUIVALENTS here and are
    withdrawn with their reasons: the address is finished with `& 0xFFFF`, which keeps exactly
    the bits an inner mask would have kept, and both operands are already masked.  That is the
    opposite of `$995A`'s case (TRAPS #134), where the page byte carried bit 8 and an OR
    forgave a sixteen-bit L -- the two look identical and only one is load-bearing.
  - Font `tools/make_hurry.py` -> `build/hurryfont.json`.
- **$9037, HURRY UP!, WIRED** -- M7.19, 2026-09-24.  `$8D4F CALL $9037`, the seventeenth
  chain entry, tested every pass and doing its work exactly once.
  - **THE THRESHOLD IS LIVE STATE.**  `LD DE,($8DBD) / LD HL,($745C) / OR A / SBC HL,DE /
    RET nc` is a COMPARE, not a countdown -- and ($745C) reads **$03E8 (1000) on the tape and
    $05DC (1500) on round1_48**, so a port that hard-codes the tape value has measured the
    wrong machine.  MEASURED either side of the live one: 1499 and 1500 decline, 1501 fires.
  - **THE ONE-SHOT IS THREE OPERANDS, NOT A FLAG BYTE.**  $9049 is a permanent disable; $904D
    latches "already fired" and diverts every later pass to $917C; $90AA makes the enemies'
    temper a one-shot INSIDE the one-shot.  All three are the operands of `LD A,n`.
  - **IT TURNS BOTH ISR GATES OFF AND BACK ON, ASYMMETRICALLY.**  MEASURED in order: $9052
    ($FEC5):=0, $9055 ($FEC4):=0, $90A3 ($FEC4):=1, $90A6 ($FEC5):=1, $90B2 ($FEC4):=0, $90BA
    ($FEC4):=1, $90BD ($FEC5):=1 -- seven writes, four of them to $FEC4, ending (1, 1).
    $90B1 clears $FEC4 ALONE around the temper pass.
  - **`OUT ($FE),$10` IS BIT 4 -- THE SPEAKER -- NOT A BORDER COLOUR**, so the "border flash"
    is a PULSE TRAIN: 126 OUTs of $00 and $10 of which only **SEVEN are edges**, spanning
    1,622,170 T (23 frames).  The gaps run 45..13,626 T over twelve distinct values contended;
    uncontended they are instruction sums (13,620 a step; a flash step's LOW 45 T after the
    previous `$908F`, the next `$908F` 14,017 T after it).  [M7.52: M7.19 laid the edges on a
    flat 1,622,170/120 step with each LOW and its HIGH at ONE instant, which the bridge's box
    integral plays as silence (TRAPS #225).  Since M7.52 the port lays them at exactly those
    times from the contended first `$908F`, 615,340 T, through `mainOut`'s hold.]  **beepEdge's upper clamp had to go**: the jump tone
    is 1,436 T at most, so clamping into [0, 1) frames looked free, and this train would have
    stacked seven edges onto one.
  - **$995A IS NOT A TEXT PRINTER**: `OR $40 / LD (HL),A / INC L / DJNZ` -- ten ATTRIBUTE
    cells with BRIGHT forced on, `INC L` eight bit.  **The colour is an operand**: $9076's
    `LD A,6` has its 6 at $9077 and `XOR 5 / LD ($9077),A` alternates it, so the three flashes
    write 3/6/3 from a cold machine and 6/3/6 on round1_48 -- **$9077 is live state too**, and
    three of five censused states differ from the tape.
  - **$9102 IS A FOURTH OPCODE-AS-MODE-SWITCH**, after $92DE, $93C4 and $A82D.  `LD ($9102),A`
    puts a NOP or a RET BETWEEN THE TWO HALVES of $90DA's body, so a call with A = $C9 does
    the ERASE ONLY and returns before the redraw -- and before $911A's tail, where Boris is
    set up.  MEASURED over the three calls (B = 10, 11, 1): $9904 entered 22 times and $9940
    21.  $9A04 walks BACK from $FD2C to $FD00, 22 steps of two.
  - **BORIS IS PREPARED, NOT ACTIVATED** (+7 stays $00; only $91A3, inside the per-frame tick,
    sets bit 7) **AND HIS TARGET ALTERNATES BECAUSE THE SETUP RUNS TWICE**: $914B toggles the
    operand at $914C into $FD87 + 10n, so the first call asks about P2 and the second about
    P1, and with BOTH players in play the second run wins and Boris chases **P1**.
  - $90C1 is the enemies' temper: `SET 2,(HL)` at +7, two DECs to +5, `AND $F8`, `ADD HL,12`
    -- a stride of twelve from a pointer that moved back two, which is ten per slot.  Count is
    ($AA57) - 2, eight bit and a DO-WHILE.  The SET is STATE: `$90D0` is the opcode's second
    byte, and the respawn flips it to `$96` (RES 2) around its own CALL, so the same walk CALMS
    (M7.48; `hurryAnger()` reads the opcode).
  - **IT BLOCKS FOR FORTY-TWO FRAMES**: 2,963,896 T end to end, against 31 T for the round
    refusal, 91 for the clock and 205 for the latch.  [M7.54: the port ran it inside one frame and
    reopened the gates at once -- the banner never showed; now it runs in time, see "$9037's BLOCK
    IN TIME" below.]
  - **DECLARED DEPARTURE**: the banner's glyphs come from the SPECTRUM ROM CHARACTER SET
    ($8044 builds $3C00 + c*8) and this project ships no ROM transcription.  The string is
    "HURRY UP !" and the printer wrote **1,680 of the routine's 3,900** display bytes;
    everything else -- the erase, the recolour, the walk, the flash, the pulse train, the
    temper, Boris -- is pure data and is done for real.  A substitute font is M7.20's, exactly
    as `tools/make_letters.py` did for the EXTEND row.  `$917C`, the per-frame Boris chase, is
    a NAMED COUNTED STUB.
  - Oracle `tools/hurry.py` -> `build/hurry_fixture.json`.
- **$931A, THE ENVIRONMENT KILL, WIRED -- DEATH BY ATTRIBUTE COLOUR** -- M7.18, 2026-09-24.
  `$8D55 CALL $931A`, the sixteenth chain entry.  It walks the enemy table and then both
  players, and asks each the same question: what colour is the screen where you are standing?
  - **$93C4 IS AN OPCODE AND IT IS A MODE SWITCH -- the twin of $92DE one routine earlier.**
    `$931E XOR A / LD ($93C4),A` writes $00, a NOP, so a hazard FALLS THROUGH into $93C5 and
    the entity is CORPSED; `$9334 LD A,$C9` writes a RET, so a hazard returns the matched
    attribute and the caller decides.  The enemies get the NOP, the players the RET.  **AND IT
    IS LIVE STATE**: MEASURED $00 on round1_48, play1p48 and hurryup and $C9 on r20_48, boss
    and elwater -- which is which depends only on where in the pass the snapshot was taken.
  - **THREE CELLS, AND THEY ARE NOT TESTED ALIKE.**  MEASURED by read-watch: the entity's own
    attribute cell, cell + $21 and cell + $20.  Poking them one at a time shows the first two
    answer to PAPER 5 (`AND $38 / CP $28`) AND to BRIGHT INK 2 (`AND $47 / CP $42`), while the
    third answers **only to the ink**.
  - Over all 256 attribute values: **46 corpse an enemy, 32 by paper and 14 by ink**.  The two
    sets do not overlap because the paper test comes first -- $6A and $EA are bright ink 2 AND
    paper 5, and the paper arm takes them, which is why the ink set is 14 and not 16.
  - **THE PLAYER DOES NOT DIE THE WAY AN ENEMY DOES.**  $9349 and $935D are `SUB $28`, so of
    the two conditions only PAPER 5 reaches the player's tail -- and that tail is not a death:
    `$936A SET 4,(IX+$5A)` is the WATER-CARRY bit, the very bit `$9286` refuses a kill on one
    routine earlier.  MEASURED: bright ink under a player leaves +$5A at $80 and its jump
    phase untouched, while the same byte under an enemy corpses it.  The tail also zeroes the
    direction byte and the jump phase, and refuses on the FLOOD ($FECE) or a held jump.
  - **ONLY ONE PLAYER CAN BE SWEPT UP PER PASS**: $9349's `JR z,$9360` goes to a tail that
    ends in RET, so P1 being carried ends the routine and P2 is probed on the NEXT pass, when
    $9340 skips P1.
  - **`$93B9 DEC L` IS EIGHT BIT AND IT WRAPS SOMEWHERE REACHABLE.**  The third probe is
    `ADD HL,$21` then `DEC L` -- sixteen bits forward, eight back -- and they agree unless
    cell + $21 has a low byte of zero: row*32 + col = 223, 479 or 735, which is **column 31 of
    rows 6, 14 and 22**.  MEASURED at every column-31 row: those three read offsets
    [0, 33, 288] where the other nineteen read [0, 32, 33].  The three wrapped cells are
    **$59FF, $5AFF and $5BFF** -- the last is PAST the attribute file, so the machine asks a
    byte after the screen what colour it is.  Rows 0 and 1 read nothing at all: their Y is
    below `$937F CP $10`.
  - The cell is `(Y>>3)*32 + (X>>3)`, verified over 5,632 positions.  `$9F5C` is three RRAs --
    a ROTATE THROUGH CARRY, so bit 7 of the result is the incoming flag and only the `AND $1F`
    makes that not matter.
  - Oracle `tools/envkill.py` -> `build/envkill_fixture.json`.
- **$925A, THE PLAYER/ENEMY COLLISION PASS, WIRED -- AND $92DE IS AN OPCODE THAT IS A MODE
  SWITCH** -- M7.17, 2026-09-24.  `$8D52 CALL $925A`, the fifteenth chain entry.
  - **THE MODE SWITCH.**  `$925A XOR A / LD ($92DE),A` writes $00 -- a NOP -- so $92C0's scan
    FALLS THROUGH into a SECOND list at $92DF; `$9277 LD A,$C9` writes a RET and the same scan
    walks ONE.  **AND THE OTHER CALLER DOES THE OPPOSITE**: `$BE5B`, the bubble/enemy capture,
    writes $C9 before its `CALL $92C0` and $00 after.  MEASURED -- $92DE reads $C9 after $925A
    and $00 after $BE5B -- so the two writers DISAGREE about what to leave behind and neither
    depends on the resting value.  Each SETS BEFORE USE; "restore" is the wrong word.
    $92C0 has exactly two callers in 64K ($BE64 and, through `CALL nz,$92BB`, $925A itself).
  - **THE SECOND LIST IS BORIS.**  $9250 is one pseudo-entity whose +7 field is $9257, THREE
    BYTES BEFORE $925A's own first instruction.  `$9121`, inside the hurry-up code, fills him
    in (`(IY+9) := 8, (IY+8) := A, (IY+5) := $18, (IY+6) := $A8, (IY+4) := 2`), and the
    already-wired `$915F` hurryReset is what clears his +7.  He is not in the enemy table,
    which is the whole reason for a second list.  MEASURED: +7 is $00 in every captured state,
    and the hurryup state writes his fields ten times in 400 frames and never his +7.
  - **THE BOX, SWEPT OVER ALL 65,536 ENTITY POSITIONS AT FOUR PLAYER POSITIONS.**  `$9312` and
    `$930A` are the same six instructions twice -- `LD A,(HL) / CP B / RET nc / ADD A,15 /
    CP D / CCF / RET` -- so the two edges are not symmetric and `ADD A,15` is EIGHT BIT.
    (100,100) and (200,150) each accept 729, a 27x27 rectangle.  (250,250) accepts **ZERO**,
    because `player + 14` wraps to $08.  And (235,100) accepts **513**, x 222..**240** --
    nineteen columns, cut off by the wrap where sixteen-bit arithmetic gives 27.  That fourth
    anchor exists because a sixteen-bit mutation survived the first three (TRAPS #49).
  - **`$92BB`'s EARLY RET DOES NOT TOUCH THE CARRY.**  BIT and LD never do, so it hands the
    caller its own flag back.  All six arms were driven with the carry set BOTH ways and
    exactly one behaves differently: the dying player.
  - **`($AA57) - 2` IS EIGHT BIT AND THE WALK IS A DO-WHILE**, so a count of ZERO is TWO
    HUNDRED AND FIFTY-SIX passes, not none (`$9304 DEC A / JP nz` tests after the body).
    MEASURED: with ($AA57) = 2 the scan still finds a hit.
  - **`$9280 OR A` IS WHAT STOPS P2 BEING HIT TWICE.**  MEASURED AT THE FLAG, single-stepping
    the whole pass with P1 hit and P2 dying: carry is 1 entering $9280 and 0 leaving it, 0 at
    both $9277 and $927C, and $927D is entered ONCE with IX = $FD80.  A byte patch cannot
    isolate it -- the same `OR A` sets the Z flag $9281 reads, so NOPping it stops P1 being
    hit at all.
  - **$927D HAD THREE SPELLINGS IN THE PORT AND NOW HAS ONE.**  An uncalled half named
    `playerHit`, a second half inside `bossKillPlayer`, and the `$9298` arm that was in
    neither.  `$AA35` is a TAIL JUMP to the same handler, so the boss's kill and an enemy's
    kill are one rule.  ($FED0) != 0 diverts to $9298 -- the ENEMY dies, $8BC2 births a corpse
    over it and the player who touched it is paid $1000 -- and the heart is tested FIRST, so
    bit 4 and bit 3 do not protect an enemy from it.  The boss path's weather arm is a
    DECLARED boundary: on the $925A path HL is the hit entity's +7 pointer, on the boss path
    nothing has put an entity there.
  - The two refusals both write nothing, so the only world that can tell them apart is one
    with BOTH bits set -- and then `$9286 BIT 4` goes first.  Nothing in RAM records which RET
    was taken, so that ordering is carried by the port's own return label and gated as such.
  - Oracle `tools/playerenemy.py` -> `build/playerenemy_fixture.json`.
- **$A824, THE GIANT OBJECT, WIRED -- AND ITS ONCE-A-FRAME GATE IS AN OPERAND** -- M7.16,
  2026-09-24.  `$8D46 CALL $A824`, the twelfth chain entry.
  - **THE GATE.**  `$A829 LD A,($8DBD) / $A82C CP $43 / $A82E LD ($A82D),A / $A831 RET z` --
    the $43 is the operand of its OWN compare, and the store one instruction later replaces it
    with the frame counter just read.  The routine therefore works once per FRAME however many
    passes the loop makes, and the state that makes it so lives inside an instruction.
    MEASURED on fallcandy: four calls without moving ($8DBD) write ONE byte each -- the
    operand store, which happens on the declining path too -- and the row does not move;
    advance the clock and the next call writes 235.  Hard-coding the $43 runs the body once in
    256 frames.
  - **AND $A839 IS THE SAME TRICK**: `$A838 LD A,9` has its 9 AT $A839, the giant's ROW and
    its PRESENCE FLAG at once, and $A83F writes the incremented row back into it.  $A824's
    first test is `OR A / RET z` on that byte -- row 0 writes nothing at all, not even the
    frame operand.
  - **THE ROW WALK**, measured one starting row at a time from a fresh machine: 1..12 and
    17..18 advance by one; **19 does NOT** (`$A83B CP $14 / JR z` jumps the STORE, not the
    body -- the giant sits on row 19 and is redrawn and re-erased there every frame); 20..23
    advance and write progressively less as the draw clips off the bottom; **13..16 are the
    HIT rows**, and they are not a special case -- they fall out of P1's position on the two
    states that carry a giant.
  - **THE BODY DRAWS, COLLIDES, THEN ERASES**, which is not the order it reads in: the draw
    goes to the NEW row and `$A925` -- the boss's own per-row erase `$A929`, entered one row
    HIGHER -- cleans the old one.  MEASURED on fallcandy: 235 writes, 160 display over 160
    cells, 20 attribute, ZERO shadow; the erase's own footprint is 36 writes over 32 display
    cells, $406E..$4771 from row 3 and $484E..$4F51 from row 10.
  - **`$A9D5 POP HL` DISCARDS $A824's RETURN ADDRESS**, so a hit's `JP $8C28` returns to
    $A824's CALLER and `$A84A JP $A925` never runs: **a hit does not erase**.  ONLY A PC WATCH
    CAN SEE IT -- a write census cannot, because the reveal repaints over the evidence.
    MEASURED: a hit traces draw -> collide -> award -> reveal, a miss draw -> collide -> erase.
  - **THE AWARD** is a THREE-byte table at $A9EA ($40 $20 $10), indexed by the giant's TYPE
    minus one -- the type being itself the operand of $A85B -- dropped into ($FFEE), the second
    byte of $80FA's pending amount.  P1's record byte $FFE6 goes $42 -> $82 / $62 / $52 for
    types 1, 2 and 3.  **The table is three bytes because $A9ED is the boss tick**: it runs
    straight into executable code, so a port carrying "the table" without a length is carrying
    an opcode.
    **...and the type the game spawns for the giant DIAMOND is 0** (the candy cane's mailbox 1, `$A84D`'s DEC):
    index -1, `$A9EA + $FF = $AAE9`, the last byte of `$AAE6 BIT 2,(IY+7)` -- `$56`, the +56,000 measured live
    2026-09-09 (above).  So the port must carry that opcode byte too: until 2026-10-10 it did not, and the diamond
    paid nothing (build/tape_bytes.json; bb.test TR6 against the machine's own `$A9C1`).
  - Only TWO of the forty-nine saved states have a giant -- fallcandy and peachfall, both
    round 3 with the row at $13 -- so the gates run in FALLCANDY'S WORLD, including
    $A98F/$A990 = `00 00`.  reset() leaves the TAPE pair `37 C9` (SCF / RET), which makes
    EVERY POSITION AN OVERLAP, so a giant poked onto row 1 in the port's own world hits at
    once and the walk is invisible (B4, TRAPS #115).
  - Oracle `tools/giant.py` -> `build/giant_fixture.json`.
- **$8FA5, THE JUMP TONE, WIRED -- THE PORT'S FIRST SOUND** -- M7.15, 2026-09-24.
  `$8D25 CALL $8FA5`, the FIRST chain entry, and its whole output is four `OUT ($FE)` edges.
  - **IT IS TWO CALLS THAT ARE ONE.**  `$8FA5 LD HL,$FDDA / CALL $8FAE`, then `$8FAB LD
    HL,$FDE4` and a FALL-THROUGH into $8FAE -- so P2's tone has no call site of its own.
    DRIVEN both ways: P2 alone sounds, and both players jumping give EIGHT edges in one pass.
  - **THE DOMAIN IS DRIVEN, NOT ASSUMED.**  ($FD89) is the jump phase: 0 grounded, 1..32 the
    arc, $FF falling.  All forty keys were held in turn for 40 frames and EXACTLY ONE moves
    the byte off zero (the digit `0`); held for 200 frames it visits 26 distinct values, the
    arc 1..24 and both sentinels.  `$8FBB INC A / RET z` and `DEC A / RET z` reject exactly
    those two sentinels -- which is why there are two RETs and not one.
  - **THE PORT HAD THIRTY-TWO ZEROS WHERE $B57D LIVES.**  The player's jump arc is read
    TWICE: `$AD79` turns the phase into this frame's Y delta and `$8FC2` turns the SAME byte
    into the tone's pitch, so the sound of a jump IS its trajectory.  With zeros there every
    phase gave E = 17 and one flat note.  The 32 bytes are carried now; they agree with the
    neighbouring hop arc $B59D in THIRTY of thirty-two places (indices 5 and 26 differ), so a
    careless compare would have passed on the wrong table.
    The prior reading -- "$B57D (24) and its spill $B595 (8)" -- was a guess, and it is
    wrong: the arc is 32 bytes, phases 1..31 read $B57E..$B59C and **phase 32 reads $B59D**,
    the first byte of the hop arc below, $FC, still in range so nothing clamps.
  - **E = |($B57D + phase) - $10| + 1**, and **`$8FC9 JP p` IS DEAD over the real table**:
    every entry is $FC..$04, all below $10, so `SUB $10` always borrows and `$8FCC NEG`
    always runs.  E is therefore 13..21 and nothing else -- which is exactly the set
    `build/sfx/` holds, jump_E13..jump_E21, captured by a different tool with a different
    bracket.  The first edge is at **219 T** for every real pitch; the 211 the not-taken
    branch gives is reachable only by indexing OUT of the arc.
  - The two half-periods DIFFER: **16E+10 and 16E+30**, the second carrying the DJNZ (13 T)
    and the `LD A,$30` reload (7 T).  Every edge of every reachable pitch is reproduced T for
    T from $8FA5.
  - **AND IT COSTS THE PASS.**  MEASURED: both players out, 159 T; one tone, 64E + 360 (+8
    for the NEG); two tones, 159 + both deltas EXACTLY (3,265 T for two E=21 tones).  The
    engine charges the DELTA, because the 159 T floor is inside the flat BB_PASS_T -- as are
    the 121..196 T the four declining arms cost, which differ by at most 75 T and are
    declared rather than modelled.
  - The sound log is rows of [fractional simulated frame, level 0..1], which is what the
    platform's beeper bridge renders.  step()'s carry can begin a frame at a negative
    `tframe`, so the offset is clamped into [0, 1) and a push that would still go backwards
    is pinned AND COUNTED (`soundClamped` / `soundOutOfOrder`) -- house rule 6.
  - Oracle `tools/jumpsfx.py` -> `build/jumpsfx_fixture.json`.
- **$900B, THE WAKE GATE, WIRED -- AND $8C28, THE REVEAL, FINALLY WHOLE** -- M7.14,
  2026-09-24.  `$8D2B CALL $900B`, the THIRD chain entry, and TWO unrelated gates share it.
  - **(a) THE HEART PINS THE ROSTER ASLEEP.**  `($FED0) != 0` sets all EIGHT wake-up delays
    $A891..$A898 to $64, every pass.  MEASURED: $01, $80 and $FF each give eight writes and a
    table of $64s; $00 gives ZERO writes and leaves a poisoned table exactly as it found it.
  - **(b) THE CROSS NEEDS EXACTLY ONE.**  `$901E DEC A / RET nz` -- MEASURED, 0, 2 and $FF all
    decline.  Then `$9028 OR (HL) / INC HL / DJNZ` runs with **B = 7**: `$A898 IS NEVER READ`.
    Proved by poking one byte non-zero at a time across all eight -- with only index 7 set the
    reveal STILL FIRES, with any of 0..6 it does not.  A port that ORs the whole table is
    wrong in exactly one world, and the heart arm above is what writes that eighth byte.
    Then `($FED2) := 0` and $8C28 runs once, with interrupts off.
  - **$8C28 IS ASSEMBLED FROM FOUR ROUTINES THE PORT ALREADY HAD**, one of which ($957E,
    `extendRow`) had been written, gated in isolation and never called.  The CALL ORDER is
    measured by single-stepping with a PC watch, not read: **$8216 -> $7F80 -> $957E ->
    $806C**, and $7F80 is in that list because $8216 does not RET -- it ends `JP $7F80`.
  - MEASURED on round1_48: 7,550 writes -- 5,664 display over 5,632 distinct cells (22 rows x
    8 x 32; the HUD's two rows are NOT repainted) and 1,412 attribute over all 704 cells of
    $5840..$5AFF.  r20_48 gives 7,595.  Border 0 and the speaker LOW (`$8C4E OUT 0`, its last
    act, 213,291 T in); nothing else.  [M7.52: the port charges none of its 213,312 T -- declared,
    `docs/TIMING.md` item 10.]
  - Poisoning the display $5A and firing the gate restores 5,626 of the 5,632 playfield bytes;
    **the six that differ are named** -- $4141, $4241, $4341, $4441, $4541, $4641, row 2
    column 1, the round number's units digit that $7F80 draws after the repaint has gone past.
    Round 1 suppresses the tens digit (`$7F92 JR z,$7FA5`), which is why it is one column.
  - `$A0BE JP z,$8C28` in the flood effect is a jump to the WHOLE routine; the port had only
    its attribute half until now.
  - Oracle `tools/release.py` -> `build/release_fixture.json`.
- **$8FE7, THE PAUSE, WIRED** -- M7.13, 2026-09-24.  `$8D28 CALL $8FE7`, the SECOND chain
  entry and the only routine in the game that STOPS the machine.
  - **IT WRITES NOTHING ON THE 48K BRANCH.**  `$8FEE LD A,($FED4) / PUSH AF / XOR A /
    CALL $8E0A` ... `$9005 POP AF / CALL $8E0A` is the 128K driver's mute and unmute, and
    `($8E0A)` IS `$C9 RET` on 48K -- MEASURED $C9 on all four 48K states and $21 on both
    128K ones -- so the value is read and put straight back.  Over a complete arm-to-release
    the machine made 6 RAM writes and ALL SIX were its own stack frame: ZERO to the world.
  - **THE KEYS ARE SWEPT, NOT MAPPED.**  All forty keys pressed one at a time through the
    real routine: EXACTLY ONE arms it (SYM SHIFT, half-row $7F bit 1) and, with SYM held and
    the routine inside the spin, EXACTLY ONE frees it (CAPS SHIFT, half-row $FE bit 0).  With
    no key it returns in 4 steps.
  - **THE SPIN IS A BUSY WAIT WITH INTERRUPTS OFF.**  Four PCs, $8FFB..$9000, inside
    `$8FF6 DI` .. `$9009 EI`: 0 ISR entries in 200,000 steps with interrupts ENABLED in the
    simulator, and 0 of the 49,152 world bytes changed over 4,000.  A paused frame has no
    pass, no interrupt and no draw -- only the wall clock moves.
  - **AND THE PASS IS SUSPENDED, NOT RESTARTED.**  Entered at $8D25 with SYM down the machine
    settles in the spin; on release the next chain address it reaches is **$900B**, the entry
    AFTER the pause -- not $8D25 and not $8FA5.  `mainLoop()` therefore carries a resume index
    and `chainWalk(from)` is split out of it; a port that treats a pause as "skip this frame"
    re-runs $8FA5 on release.
  - Oracle `tools/pausegate.py` -> `build/pausegate_fixture.json`.
- **AND THE STRUCTURAL ROW THAT CAME WITH IT** -- M7.13.  Two rows already guarded the
  ship/test asset split (everything the engine source reads must be shipped; nothing it never
  reads may be).  A third asks whether every TEST-ONLY asset is read by any check at all, and
  found one of sixty-nine that was not: `build/livespanel_fixture.json`, captured by M7.10,
  registered, loaded from disk every run, compared against nothing -- **and wrong**.  Its
  read-watch excluded `a >= $E000` to drop the colour shadow, and $E000 is where the game's
  working RAM begins, so ($FD87), ($FD91), ($FDDC) and ($FDE6) -- the four addresses M7.10
  exists for -- were missing from its own "measured input set".  The exclusion is now the
  shadow WINDOW $E000..$FB00, the fixture is re-captured with 64 input addresses instead of
  60, and it is read by three gates (TRAPS #116).
- **$8E2A, THE GAME-OVER TRIGGER, WIRED** -- M7.12, 2026-09-24.  `$8D5B CALL $8E2A`, the
  nineteenth chain entry and the only one that can end a game.
  - `$8E2C LD A,($FD87) / LD HL,$FD91 / OR (HL) / RET m` -- it arms only when bit 7 is CLEAR
    in BOTH player slots; then `$8E34 LD A,$B4 / LD ($FEC9),A`.  `$8D0D` diverts the whole
    loop while `($FEC9)` is non-zero, `$8CFC INC (HL)` counts it UP to the eight-bit wrap
    (so `$B4` is 76 frames, not 180), and `$96E9` clears it at a new game.
    `$8E2A LD B,0` is DEAD -- B is never read -- and is a comment, not a store.
  - **IT WAS UNWIRED FOR A MEASURED REASON, AND M7.10 REMOVED IT.**  The port's `reset()`
    world had `($FD87) = ($FD91) = $00`, so wiring it would have ended every game on the
    first pass -- faithfully, for a world the machine is never in.  Seeding those flags for
    `$806C` put the port in the machine's world.
  - **AND WIRING IT PROVED SIX GATES WERE ISOLATING THE BUBBLE PATH WRONGLY.**  They zeroed
    `($FD87)` to remove the player -- the SAME BIT `bubbleTouchPlayer` tests -- so each one
    was also a game-over world.  Their captures are all round1_48, where the player is ACTIVE
    and merely elsewhere; they no longer deviate from the world they compare against
    (TRAPS #115).
  - The WRITE path is unreachable from every shipped capture (48 of 49 saved states have P1
    in play), so the gate DRIVES both arms: the machine's world must NOT arm over four
    passes, and both-players-out must arm to `$B4` and then divert.
- **$806C, THE LIVES ICONS** -- MEASURED AND GATED 2026-09-24, M7.10.  The SIXTH method
  written, gated in isolation and never called.  M7.8-A promoted it onto the round-advance
  path at `$7F5B` and found a counted stub; its live-sequence gate has been masking row 23
  columns 0..4 as a declared gap ever since.
  - **WHAT WAS MISSING WAS THE STATE, NOT THE CODE.**  `livesIcons()`, `livesRow()` and
    `livesCell()` were all transliterated.  `reset()` left `($FD87)`, `($FD91)`, `($FDDC)`
    and `($FDE6)` at ZERO -- and `$8097` is `RET p`, so a player whose +7 bit 7 is clear
    draws NOTHING.  Wiring the panel without the state would have drawn an empty row and
    looked like success.  MEASURED input set (a read-watch over `$806C`, minus its own code
    and the display it writes): the tile buffer's even bytes, the icon at `$85A1..$85C0`,
    and the four player bytes.  round1_48, play1p48 and r20_48 all carry `$E1`/`$60` --
    P1 in play, P2 NOT -- and lives 3/3 (r20_48 has 4, the `$982A` milestone award).
  - **THE SWEEP:** 9 writes and one attribute cell per life, clamped at 5 by `$809E` (6 cells
    at 5, 6 and 7 alike), and **ZERO writes for a player not in play**, both players driven.
  - **THE MASK IS NARROWED FROM 56 ADDRESSES TO 16.**  The live sequence now diverges from
    the machine on SIX bytes where it diverged on about twenty-five, round 1 on NONE, and
    **both round-81 compose rows match byte-for-byte with NOTHING masked** -- round 81 draws
    no round number, so the only remaining gap does not apply to it.
  - **AND IT REMOVED $8E2A's BLOCKER.**  That trigger was transliterated, gated and
    deliberately unwired because the port's world had no player in play, so wiring it would
    have ended every game on the first pass -- faithfully, for a world the machine is never
    in.  `$8E32`'s `OR (HL) / RET m` now declines on the first test, as it should.  The
    reason it is unwired has changed from "the world is wrong" to "the increment is next".
  - **AND THE PORT CAN NOW WARP.**  `$9840`'s `BIT 7,(IX+7)` always failed while `($FD87)`
    was 0, so the milestone warp could not fire and the sequence gates passed by accident.
    With the flags seeded the port warps 19 -> 81 correctly, so those gates now suppress the
    warp exactly as F0's chained-build recipe does -- driving both sides the same way.
  - Oracle `tools/livespanel.py` -> `build/livespanel_fixture.json`.
- **THE DRIFT PAINTER `$7C57..$7DD5`, TRANSLITERATED** -- MEASURED AND GATED 2026-09-23, M7.8-C.
  M7.7-H4 shipped this routine's OUTPUT and wrote "WHEN THE PAINTER LANDS THE ASSET GOES".
  It has landed: **15,552 bytes of captured field replaced by 675 bytes of static INPUT**
  (`$79AF..$7C22` the 628-byte rectangle stream, `$7C23`/`$7C33` two 16-byte stride tables,
  `$7E1A..$7E28` fifteen door-pattern bytes), and the engine COMPUTES all 81 rounds.
  - **THE STRUCTURE.**  Three head rectangles (left half only, identical every round, and
    rectangle 1 is a FIELD-LEVEL NO-OP because it writes code 0 over a field `$7C43` has just
    zeroed); `$7C84 CP $51 / RET z`; an entry walk over the stream following sixteen `$Fx`
    ALIASES, two of them CHAINED (60 -> 14 -> 13, 80 -> 77 -> 76); the per-round rectangle
    loop; the MIRROR; and four DOORS.
  - **LEN[n] = 4 + 2n + (n >> 1)** is the entry stride and **BODY[n] = 2 + (n >> 1)** the body
    offset.  Confusing the two is what made the walk loop for ever (TRAPS #106).
  - **THE MIRROR TRANSFORMS, IT DOES NOT COPY**: the left 16 columns onto the right 16
    REVERSED, swapping RIGHT(01) with LEFT(11) and leaving UP(00) and DOWN(10) alone.  384
    writes from `$7D73`, every round but 81.  It is the ONLY producer of code 3, which is why
    round 81's histogram is 680/42/46/**zero**.
  - **THE DOORS ARE PAINTED AFTER THE MIRROR** and are therefore NOT mirrored -- that
    asymmetry is the point, and it is why rounds 15, 21, 58, 64 and 73 are the only rounds
    1..80 whose field is not left/right symmetric.  Their call sites are `CALL nz`, opcode
    `$C4`, which a scan for `CD 2B 7E` misses: `$7E2B` has SEVEN call sites, not four.
  - **THE PATTERN TABLE IS LIVE DURING A PAINT**: `$7E0F`'s `RLC (HL)` rotates the byte IN
    PLACE, but four doors x two rotations is eight, and eight rotations of a byte is the
    IDENTITY, so it is restored by the end of every round (measured before and after, all 81).
    The shipped block is FIFTEEN bytes and stops at `$7E28`: `$7E29` is the painter's own
    entry counter, and pattern index 15 -- which would select it -- is NEVER used (measured,
    the index runs 0..12).
  - **ROUND 45 PAINTS OUTSIDE THE MAP AND THE ENGINE PRODUCES IT.**  Its rectangle starts at
    row 23 with C = 4 and `ADD IX,DE` has no map bound -- an UNCLAMPED ROW COUNTER, not an
    eight-bit wrap -- so rows 24..26 land at `$FB07..$FB0B`, `$FB27..$FB2B` and `$FB47..$FB4B`.
    15 cells, the only round of 81.  Clamping would be a departure; it is not one.
  - **THE DOMAIN IS 1..81** and off it the machine writes over live RAM: at `($8609)` = 0 --
    the byte `$96FB` writes at every new game -- 141 cells over `$FB02..$FFF0`, and at 255
    **10,545** over `$FB00..$FFF9`, across `$FD80` the player struct, `$FED8` the bubble pool
    and `$FFE1` the high score.  The port cannot reach it (`$97F8` increments the round BEFORE
    the round start and swaps 82 for the lookahead, so `($8609)` at every `$79AC` is 1..81),
    and it guards and COUNTS anyway (TRAPS #105).
  - **THE ALIAS WALK IS UNBOUNDED ON THE MACHINE AND BOUNDED IN THE PORT**, with the overrun
    counted: the Z80 terminates only because the data does (TRAPS #106).
  - **IT CARRIES NOTHING BETWEEN RUNS**, so the port may call it per round, out of order,
    repeatedly -- the question M7.8-A was burned by, asked here rather than assumed.
  - Oracle `tools/driftpainter.py` -> `build/driftpainter_fixture.json`; asset
    `build/drift_painter.json`.  `build/drift_field.json` is GONE.
- **THE DRIFT PAINTER'S WIRING AND ITS `$7DD6` TAIL** -- MEASURED AND GATED 2026-09-23, M7.8-B.
  M7.7-H4 measured the drift field and shipped it as `build/drift_field.json`; `driftApply()`
  was written for it and **had no call site**, so for three increments the port called only
  `$79AC`'s first instruction.
  - **`$79AC` DOES NOT STOP AT THE TRANSFORM.**  `$7C43` masks with `$38`, which WIPES bits 6
    and 7, and then falls onward through the painter `$7C57..$7E4A`, whose writers `$7E3E`
    and `$7D73` put them back.  MEASURED on the built page before the fix: **288 colour-shadow
    cells carry the drift bits after `reset()` and ZERO after every `roundAdvance()`** -- so
    `driftCode()` returned 0 for every cell, the open-air arm, and **every bubble on every
    round after the first rose straight up**.
  - Wired, the engine now reproduces the machine's WHOLE colour shadow byte for byte over the
    live sequence -- `reset()` and all 23 advances, by CRC -- with the drift-cell counts
    (288, 288, 408, 492, 528, 528 on rounds 1..6) agreeing row for row.
  - **`$7DD6` IS REACHED ONLY BY FALL-THROUGH** from the painter; there is no `CALL` to it in
    64K, which is why a caller scan finds nothing.  `elementClass()` was likewise written,
    gated in isolation and never called, so `($7E0E)` read 0 on all 80 advances while the
    machine carries a non-zero class on **50 of 81 rounds** -- the fire, water and lightning
    rounds never triggered.
  - **IT WRITES `($7E0E)` TWICE.**  MEASURED inside one `$79AC` bracket on round 3: `$7DF0`
    stores the raw class (5) and `$7E0A` the redraw (10).  `$7DF3 CP 5 / JR nc` sends a class
    of 5 or more to `$7E04 LD A,R / AND 7 / ADD 5`, so on the 13 rounds that take it the
    DECLARED RNG SUBSTITUTE gives its own answer and only the **5..12 range** is contracted --
    E1's rule, and F0's precedent for round 81's lookahead.  The other rounds are exact.
  - **ROUND 81 DOES NOT RUN THE TAIL, AND THE BRANCH IS IN THE PAINTER, NOT THE CLASS.**
    `$7C84` is `LD A,($8609) / CP $51 / RET z`, the same idiom as `$7F83`'s in the round-number
    drawer.  MEASURED two ways: an 81-round chained build writes `($7E0E)` on **80 of 81**
    rounds, round 81 the only exception; and a path trace of the round-80 and round-81 advances
    enters `$79AC`, `$7C43` and `$7C57` on BOTH and `$7DD6` on round 80 ALONE.  The FIELD still
    applies on round 81 -- `$7C57..$7C89` runs before the return -- so only the tail is skipped,
    and a port guarding the whole painter on the round would leave round 81 with no wind.
  - The painter ITSELF is still not transliterated; the field remains the declared asset, and
    M7.7-H4's "WHEN THE PAINTER LANDS THE ASSET GOES" still stands as the next increment.
- **THE BUBBLE DRIFT FIELD** (bits 6/7, `$B846`, `$B8DB`) -- MEASURED AND GATED 2026-09-18,
  M7.7-H4.  **The colour shadow has THREE lives**, not two: bits 0-4 a live per-cell bubble
  occupancy claim, bit 5 the static SOLID flag, and **bits 6-7 a static per-round DRIFT
  DIRECTION**.
  - `$B843 CALL $AEDC` builds the cell as `(Y & $F8) * 4 + (X >> 3)`; `$B846 LD A,(HL) /
    RLCA / RLCA / RLCA / AND 6` lifts bit 6 to bit 1 and bit 7 to bit 2, so the code comes out
    **already doubled** and indexes `$B8DB` directly.  0 -> (0,-1) UP, 2 -> (+1,0) RIGHT,
    4 -> (0,+1) DOWN, 6 -> (-1,0) LEFT.
  - **`$B8DB` IS THE TABLE M7.5 ALREADY EXTRACTED as the bubble WIND table** -- the same four
    deltas serve the wind push (indexed by the player's facing) and the map drift (indexed by the
    cell), plus the `(0,0)` pair at `$B8E3` that `$B968` uses to null a wind.
  - The field is SEED-INDEPENDENT; round 81 has ZERO cells of code 3 (`$7C89` skips the mirror);
    and **round 45 is the ONLY round that paints outside the map** (15 cells from `$7E3E` at
    `$FB07`-`$FB4B`), so bounds-checking is a declared departure with one round where it shows.
  - THE PAINTER `$7C57-$7E4A` IS NOT TRANSLITERATED.  The field is carried as a declared asset
    (`build/drift_field.json`, 81 rounds x 192 bytes) until it is.
  - **A PORT THAT OMITS IT LOOKS RIGHT FOR TWO SECONDS.**  Over 600 frames the field is read 362
    times in r6_48 and 361 in `water`, and ZERO times in round1_48 and boss.
- **THE COLLISION TRANSFORM** (`$82D6`, `$79AC` -> `$7C43`) -- MEASURED AND GATED 2026-09-18,
  M7.7-H3.  **This is where the render model binds.**
  - `$82D6` steps a palette index at `$82D7` -- a COUNT OF BUILDS wrapping 0..14, NOT the round
    (H0) -- picks a byte from the fifteen at `$858C`, strips its bit 7 into `$860C`, and derives
    **SOLID = (p & `$7F`) | `$40`** and **OPEN = SOLID & `$47`**.  Then it fills the colour shadow
    from `$F840` -- ROW TWO -- with OPEN, exactly 704 bytes, leaving rows 0 and 1 to `$81C3`.
  - **THE LOAD-BEARING FACT IS AN INEQUALITY**: for ALL FIFTEEN indices `OPEN & $38 == 0` and
    `SOLID & $38 != 0`.  Bit 5 in SOLID is set for exactly indices 4 (`$66`) and 6 (`$65`), an
    accident of two bytes -- so **"bit 5 means solid" is TRUE of the RAW build attributes on a
    minority of rounds and FALSE on the rest**, and universally true only after the transform.
  - `$79AC` = `JP $7C43`.  `$7C43 LD HL,$F800 / LD BC,3` -- a SIXTEEN-BIT load that sets B to
    ZERO itself, so the inner DJNZ runs 256 times and the outer three: **768 cells**.  The rule is
    `(v & $38) ? $20 : $00`, via TWO writers: `$7C4C` stores `(v & $38)` on every cell and `$7C4F`
    overwrites with `$20` where that was non-zero.  **A seed with no `$38` bits sends every cell
    down the `JR z` path and `$7C4F` never fires**, which is how a writer census can lose one.
  - A port converting THREE cells instead of 768 leaves 765 raw attributes in place -- and on the
    rounds whose palette already has bit 5 set in SOLID, a bit-5 gate cannot see that.  Gate the
    FULL 768-byte output, never a bitmask.
  - **`$81C3`/`$81E1` build the CEILING**: rows 0 and 1 come out solid except columns 9-12 and
    19-22, and poking `$81C3` to `$C9` makes the gaps vanish.  Visible only with those rows
    poisoned first, since `$82D6`'s fill never reaches them.
  - DURING PLAY the only writers are `$B8C0` and `$B6D6` (bubble occupancy) and **every write
    preserves bits 5, 6 and 7**.  `round1_48` and `water` are BOTH round `$01` and differ by 632
    writes to zero, so the writers are not a function of the round.
- **THE ROUND-TRANSITION DISCARD** (`$8216`) -- MEASURED AND GATED 2026-09-17, M7.7-H2.
  `$7F4E CALL $8216` runs three instructions after the scroll loop exits and repaints the WHOLE
  playfield out of the shadow: 22 rows of 8 x 32 bytes from the `$FD04` table (5,632 writes),
  then `$F840` -> `$5840`, `$02C0` (704), then `$8247 JP $7F80`.
  - **SO THE SCROLL'S OUTPUT IS DISCARDED.**  Patch `$7F34` from `28 18` to `18 18` so no round
    ever scrolls, build the SAME round twice from one saved machine, and the SHADOW and the
    COLOUR SHADOW come out BYTE-IDENTICAL -- 0 of 6,144 and 0 of 768 -- on rounds 2, 3, 21, 45,
    80 and 81, while the scrolled build costs 71% to 360% more T.
  - **AN END-STATE SCREEN GATE THEREFORE CANNOT FAIL.**  It passes a port with no scroll at all,
    a backwards scroll, a wrong-speed scroll, the wrong filler tile, the wrong attribute source
    or a pixel-smooth scroll.  Any scroll gate must compare MID-SCROLL snapshots.
  - The only display difference found (round 3, 53 bytes) is NOT the scroll: it is two settling
    enemies two pixels apart, because the longer build let the hurry timer tick once more.
  - It repaints 22 rows, not 24: the table starts at `$4040`, so the two HUD rows -- 576 display
    bytes -- are NOT repainted.  Entries 22 and 23 are `$0000`/`$0020`, which the Spectrum drops.
  - `$8216` has a SECOND caller at `$8C28`, so it is not round-build-only.
  - `$854D` copies **DISPLAY -> SHADOW**, the opposite direction, and that is measurable only
    with the two sides poked apart: after `$8216` the display equals the shadow at every address.
- **THE ROUND NUMBER** (`$7F80`) -- drawn into the **SHADOW** at `$E040`/`$E041`, never the
  display, which is why the FIRST of its three calls per build is the one that matters.  Round 81
  returns at once and draws nothing; a leading zero is SUPPRESSED, so rounds 1-9 draw seven shadow
  rows and rounds 10+ draw fourteen.  `$9A0E`/`$9A0F` hold ASCII (`$8042` does `ADD A,$30`).
  The glyph is SEVEN rows starting ONE ROW DOWN, and **that offset is `$7FAF INC HL`, not
  `$7FB1 INC H`** -- there are TWO independent `+1`s here.  `$8042` returns
  `$3C00 + 8*code`, which is glyph ROW 0 (measured: `(HL - $3C00) mod 8 == 0` at every
  `$7FAF` entry), and `$7FAF`'s `INC HL` steps the SOURCE past it -- that is why row 0 is
  never read and why the loop is `LD B,7`.  `$7FB1`'s `INC H` steps the DESTINATION page,
  `$E0` to `$E1`.  Both are `+1`, so the arithmetic lands either way; only one of them is
  the row, and this line credited the wrong one until M7.32.
  **`$7FBA` writes `$F841` inside the SHARED glyph routine**, so the tens call writes it too and
  `$7FA0` adds `$F840`: ONE colour write below round 10, THREE from round 10, ZERO on round 81.
- **PROVENANCE: `$5B00..$61A7` IS RELOCATED AT COLD START** -- MEASURED AND GATED 2026-09-17,
  M7.7-H0.  `$96A5 LD HL,$E000 / LD DE,$5B00 / LD BC,$06A8 / $96AE LDIR` copies 1,704 bytes once
  before the front end, so **THE LOAD IMAGE IS NOT THE RUN IMAGE THERE** and every static read of
  the range from `build/image_tape.bin` at its own address is wrong -- by 1,385 of 1,704 bytes.
  - **TRAPS #43's all-zero guard PASSES on it.**  `image_tape.bin[$6180..$61A7]` is **36 of 40
    NON-ZERO** -- it is STACK, because `$5BB0` does `LD SP,$61A7`; measured, 226,384 writes land
    in `$6100..$61A7` over 200 front-end frames, EVERY ONE from the ROM and none from the game.
    "The range is sourced" and "the range is correct" are different claims.  (TRAPS #47.)
  - The five platform tile patterns come from `$E680`, the `$5D00` item bank from `$E200`, and
    `$5CFC..$5CFF` from `$E1FC`.  `$5C00..$6100` IS all zero on tape, which made the item bank
    look unsourced when its source simply sits 32K away.
  - **The builder is INVISIBLE in the live dump**: `$8CC4 LD SP,$96DD` puts the stack over
    `$96A5..$96DC`, so disassembling `build/image.bin` there gives `POP HL / RST $38 / NOP`.
  - MEASURED from build/title.pkl with the destination POISONED and SP pinned outside the write
    range: 1,704 writes, all from PC `$96AE`, contiguous; and poking the source `$E680`/`$E681`
    makes `$6180`/`$6181` follow, so it is a COPY and not a coincidence.  The run image's
    `$6100..$61A7` occurs at EXACTLY ONE address in the 64K tape image, `$E600`.
  - The 35 bytes where the copy differs from the live dump are exactly the two LIVE CARVE-OUTS:
    **`$5B14-$5B1F`** -- the wall-texture scratch `$8390` writes that `$A36C`'s twenty-byte clear
    does NOT reach, which answers the old "writes 32 vs clears 20" question -- and **`$5CE0-$5CFB`**,
    the sparkle table.
  - **THE PLATFORM TILE IS BITMAP ONLY.**  Two builds of the same round, one with all forty tile
    bytes poked: the shadow BITMAPS differ by 1,279-2,752 bytes while the ATTRIBUTE file and the
    COLLISION shadow are IDENTICAL.  So the tile never reaches `$79AC`'s transform.  (The naive
    version of that experiment -- diffing the colour shadow against its pre-build state -- reports
    752 changed bytes on every round and proves the opposite, because `$7F62` rewrites it anyway.)
  - **`$82D7` and `$83EC` are BUILD COUNTERS, not the round.**  Each advances by ONE PER BUILD and
    `($860D)` = `$6180 + 8 * index` follows `$83EC` alone.  The index fits `(round + 1) mod 5` on
    ordinary rounds and BREAKS at a milestone warp, where `$8609` jumps **+62** while `$83EC`
    advances 1 -- a divergence EXACTLY ONE ROUND WIDE, so only a chained sweep across a warp can
    separate the two models.  Seven saved states here already violate the identity.
- **THE TREASURE ROOM** (`$890D`'s tail, `$8950`, `$899E`, `$8F36`) -- MEASURED AND GATED
  2026-09-17, M7.7-I11.  The level-skip power-up (type 12) empties the round and fills it with
  collectibles; the room then clears either when they have all been taken, or when the timer
  crosses a window.
  - **THE WINDOW IS AN EQUALITY, NOT A THRESHOLD.**  `$8F39 SUB n / $8F3B CP 8`, where `n` is
    `$8F3A` -- the timer's HIGH byte CAPTURED at `$892C` when the item was taken.  With items
    still live the room clears at a delta of EXACTLY 8 and at no other value: measured, 0 and 7
    do not clear, and neither do 9, `$10`, `$F8` or `$FF`.  The subtraction WRAPS in eight bits
    (capture `$FC` against high byte `$04` clears; a plain subtraction gives -248 and refuses).
  - Clearing ON the window gives **NO AWARD**; an EMPTY table awards whatever the delta.  The
    four outcomes are: window not reached + items left -> play on; window not reached + empty ->
    award; window reached + items left -> cleared, no award; window reached + empty -> award.
  - `$8F94` counts **31 entries from `$9605`, testing byte0 over a two-byte stride** -- ENTRY 0
    IS NOT COUNTED, so a room whose only remaining item is the round power-up counts as EMPTY.
    That is a THIRD base over the same 64 bytes, after I1's passes from `$9603` and I9's corpse
    scan from `$9607` (B = `$1E`).
  - **THE AWARD**: a ONE-BYTE UNSIGNED compare of `$FDE2` against `$FDEC` picks the leader, who
    gets `$0100` while the other gets `$0050` -- and **A TIE GIVES BOTH THE LARGER**.  Both go to
    **(`$FFEE`), the HIGH HALF** of the pending field, so they are worth a HUNDRED times the same
    number written low; only two of the four bytes are written, which is provable only in the
    score because `$80FA`'s cleanup zeroes all four afterwards.
  - **THE FILL** `$8950` runs on TWO REGISTER SETS: MAIN holds (entries left, item cursor, Y, X)
    and ALT holds (columns left, rows left, the colour-shadow cursor).  Six rows of seven, X from
    `$20` by `$20` and Y from `$20` by `$18`, writing byte0 = X | type and byte1 = Y **from
    `$9605`**.  The two DJNZs are on DIFFERENT Bs and `$8974` ends the WHOLE fill, not the row.
  - **THE PROBE** `$899E` tests NINE colour-shadow cells in three groups of three -- the row at
    the self-modified offset `$899F`, the row through the cursor, and the row below.  Its abort
    is CONTROL FLOW: `$89B7` finds a solid cell and does `POP HL / RET`, discarding `$899E`'s
    frame and returning past it with carry CLEAR, bypassing `$89B5 SCF`.  Third routine in the
    game to return past its caller, after `$B679` and `$88B1`.  And its third group is NOT at a
    negative offset: `$89AF LD E,$1D` leaves D at ZERO, because `$89B7`'s own `LD D,3` clobbered
    the `$FF`.
  - The type and the probe offset are self-modified TOGETHER: type 1 with offset -`$21`
    normally, type 9 with offset -`$01` on round 81 alone.  The two offsets AGREE on rounds 20
    and 80 and DIFFER on 1, 2, 5, 56 and 81.
  - `$8E3B` PREEMPTS the whole thing, and `$8F36` NEVER READS `$8609` -- rounds 2, 20 and 81 give
    identical answers.
  - DECLARED DEPARTURE: `$8F78` draws "PERFECT !" **256 times** (B starts at ZERO) with the main
    loop stopped -- ~1.8 million T, about 26 frames, ~41,600 screen writes.
- **THE `$8888` SHOOT GATE ZEROES THE HURRY TIMER** -- `$8895 LD HL,0 / LD ($8DBD),HL`, both
  bytes, mid-round, leaving the treasure room's capture `$8F3A` alone.  MEASURED: handlers **10
  AND 11** both reach it; the other fourteen do not.  So the room's window is not "elapsed since
  you took the skull" -- it is an equality on `$8DBE`, and a port modelling elapsed time diverges
  the moment either of those power-ups is collected.
- **THE ROUND-CLASS CENSUS** -- MEASURED AND GATED 2026-09-17, M7.7-F0, over 81 sequential
  `CALL $97F8` in ONE world (`build/roundclass_fixture.json`).  **Poking `$8609` is NOT a round
  sample**: `$8609 := 19` warps to 81 and gives round 81's signature to the T-state.
  - `$745C`, the per-round hurry threshold: **1500** for rounds 1-55 and 57-71, **350** on round
    56, **30000** on round 72, **1000** from round 73.  Rounds **80 and 81 INHERIT it** -- with a
    `$AABB` sentinel reseeded before every build it survives on exactly those two rounds and no
    others, because `$729D`/`$72A0`/`$72A2` diverts the spawner before both writers.  The sentinel
    is load-bearing: rounds 78 and 79 both give `$03E8` and both leave `$AA57` = 9, so "not
    written" and "written with the same value" are otherwise the same observation.
  - `$AA57` = (enemies in the round record) + 2, i.e. **TOTAL SLOTS INCLUDING THE TWO PLAYERS**.
    Over a real chained game it never leaves **5..9**, so at the four `SUB 2 / LD B,A` sites
    (`$90C1`, `$8EAA`, `$931A`, `$92E4`) B is 3..7 and never 0.  Rounds 80 and 81 inherit it too.
  - `$9811`, the return-round draw, is **exactly `(((R + 2) & $1F) + $1E)`** on all 256 values of
    R -- 32 distinct values over 30..61, both 41 and 61 reachable.  The `+2` is `LD A,R` (`ED 5F`)
    reading R after its own two M1 cycles.  **It cannot be measured by sampling** (TRAPS #46): R
    advances with the instruction count, so a periodic step schedule combs its residues (420
    samples missed the value 38) and driving whole frames phase-locks it to the frame parity
    (200 samples, TWO distinct values).
- **Rounds 21/41/61 (`CP $15/$29/$3D` on the LOOKAHEAD): +1 LIFE, and the NO-DEATH WARP** (CORRECTED
  2026-09-09, measured while building later-round states): `$982A/$982D INC (IX+$5C)/(IX+$66)` are the
  LIVES counters `$FDDC`/`$FDE6` (both players +1 life). Then the flag `(IX+$5A)` bit 7 (`$FDDA`/
  `$FDE4`), which is SET by `$9984` at a player's first respawn and is 0 in every fresh game: if P1
  has NOT died (bit 7 clear) and P1 is active (`+7` bit 7) -> `$8609 := $51` (round 81); else if P1
  has died, the same test on P2 (`$9836`); a player who has died gets no warp. MEASURED: a fresh
  harness game advancing 19->20 (lookahead 21) lands on round 81 every time; with `$FDDA`/`$FDE4`
  bit 7 poked on (as in every owner snapshot after a death) it lands on 20. So a no-death run is
  warped to the final round at 21, 41 or 61 -- the reading "if both hold bit 7 -> boss" was inverted.
- Next-round build then runs: clear the `$9AC1` pointer table (19 entries), clear the shadow
  `$E000` (`$18` rows), `CALL $7F1B / $727B (spawn enemies) / $99A8 / $A36C`.
- The FRUIT MANAGER `$C002`/`$C006` runs every main-loop pass (`$8D49`).
- OPEN (still): where the all-enemies-dead count is tallied and `$FEC9` armed; and whether the
  GIANT FRUIT / level-clear bonus is spawned in that path (the user's candy-cane hint) -- both are
  downstream of the item-collection path, which is not yet reproducible from a poked state.

## Items: CORRECTIONS from a real snapshot (M5) -- retractions + verified facts

A real in-game snapshot (player left of a landed fruit; keyboard controls) overturned two
earlier claims. Recording the corrections per house rule 1 (the machine is right):

- **RETRACT "$FFED = score"**: the HUD read "1UP 3200" while `$FFED-$FFEF` = `00 00 00`. So
  `$FFED` is NOT the P1 score (the `$B7D1` DAA routine adds to some other BCD counter). The real
  score location is OPEN (a candidate is near `$FFE4` = `00 20 03`, unconfirmed).
- **RETRACT "$5CE0 = collectible fruit"**: the collectibles are ENTITY-TABLE objects. In the
  snapshot, the popped enemies became fruits in slots 2-4 (`$FD80`+): ptr **`$C700`**, `(+9)=$FF`,
  flags `$3E/$3F`. (`$5CE0`'s role was left unconfirmed here; SETTLED by M7.7-I10 -- it is the
  BURST-SPARKLE particle engine, and the guess "transient burst effect" was right.)
- **Fruit/collectible object = an entity slot**: per-frame update at **`$8A80`**, which animates
  the sprite through **`$C700` / `$D340` / `$D360`** (a 3-frame shimmer, all runtime-built) and
  bobs it (Y +-8, wrap `$B8/$C0`). Both enemy-death fruit and (per the player) the spawned
  points-collectibles live here. Sprites confirmed visually: a banana and an ice lolly.
- **In-play controls (this real game) = KEYBOARD: O = left, P = right** (measured from the
  snapshot). (My earlier cursor mapping 5/8/0/7 was for the cursor-joystick option only.)
- The snapshot RESUMES correctly (main loop `$8D00-72` and the fruit manager run normally).
- **Collection NOT reproduced**: walking the player onto the banana (same floor, same cell) does
  not collect it or change any score in-harness, and reading the collection code cold produced
  repeated MIS-interpretations (bit1/bit4 of `(IY+7)` are the fruit's random-bob DIRECTION bits,
  not "touched/collected" as I first guessed). So the collection trigger + the score are UNSOLVED
  and need ground truth: a BEFORE/AFTER-collection snapshot pair to diff. `$A314`/`$A2D5` draw;
  `$8A80` updates; the collect path is not yet identified.

## Items: fruit collection + score -- VERIFIED LIVE via a before/after snapshot pair (M5)

> **CORRECTION (2026-09-08, bucket-A audit -- MEASURED; supersedes the score / value / ability claims in the "Items:" and first "Power-ups" sections below):**
> - **`$FFE4` is the HIGH-score MSB, NOT P1.** Score fields are HIGH `$FFE1-$FFE4`, P1 `$FFE5-$FFE8`, P2 `$FFE9-$FFEC` (8-digit BCD LE; base `$FFE1 + 4*player`, computed at `$8112 LD HL,$FFE1 / ADD HL,BC`). The high-score compare/copy is `$8141 LD DE,$FFE4` + `LDD`x4 (counts DOWN into `$FFE4..$FFE1`). The old "P1 score = `$FFE4`" readings conflated the high-score MSB `$FFE4` with P1's low bytes `$FFE5-$FFE7` (they move together because HIGH tracks the leading player). Live play1p: HIGH `$FFE1-4 = 00 00 02 00`, P1 `$FFE5-8 = 00`. See the HUD-layout section.
> - **Score-add routine ENTRY is `$80FA`** (`CP 3` player guard); BCD add loop `$811B-$8121` (**`DAA` at `$811D`** -- that address is an opcode, NOT a table); high-score compare/copy `$812E-$814C`. Pending add amount = `$FFED-$FFF0`.
> - **Per-item POINT VALUE is the 16-word table `$8649`** (indexed type*2; loaded to `$FFED` at `$8809`, added by `$80FA` at `$8817`): internal type0-8 = `$0010..$0090`, 9 = `$1000`, 10 = `$0400`, 11 = `$0800`, 12 = `$0300`, 13 = `$0700`, 14 = `$0200`, 15 = `$0500` (HUD = /10). `$8903` is only the draw-scratch sprite pointer, not a value table.
> - **CAUTION -- the +40000/+80000/+2000/+3000 figures below are PROVISIONAL / likely INFERRED-false.** No traced `$80FA` award path produces more than +1000 internal for one collect (type 9 = `$1000`); the large figures are probably the same `$FFE4`-vs-`$FFE5` byte-boundary misreads. Re-measure against a fresh snapshot before trusting them.

A before/after-collection snapshot pair (player left of a banana; after = banana taken) pinned
the whole chain by diff + a re-run, correcting all the earlier guesses:

- ~~**P1 SCORE = `$FFE4`-`$FFE7`, 4-byte BCD, little-endian**~~ **RETRACTED 2026-09-16, and
  now GATED AGAINST (M7.7-I4): every award row pins HIGH to 99999999 so the copy cannot fire,
  and asserts that only the collecting player's own four bytes move. The award is FOUR bytes
  with the carry reaching the top one, and the carry out of the fourth `DAA` is DISCARDED, so
  the score wraps mod 100,000,000. `$816B` returns `HL = base - 1` and the compare depends on
  it. Leading zeros are suppressed by a self-modified OPCODE at `$81BB`.**
  P1 is `$FFE5`-`$FFE8`; `$FFE4` is the HIGH score's MSB. `$80FA` computes `C = 4*player` and
  `$8112 LD HL,$FFE1 / ADD HL,BC` gives base `$FFE1 + 4p`, while `$880E BIT 0,(IX+$5A)` makes the
  player index **1 or 2, never 0** -- slot 0 is the high score, which `$8141 LD DE,$FFE4` + `LDD`x4
  copies into descending. The old reading was a four-byte window one byte early, straddling the
  high-score MSB, which is also where the phantom +40000/+80000 awards came from. The score-add + HIGH-SCORE compare/update is at **`$811D`-`$814C`** (`$812E` compares
  `$FFE4` to the high score, `$8144` LDDx4 copies it up if beaten); **`$8161` zeroes `$FFED`-`$FFF0`**
  -- so `$FFED` is a scratch, NOT the score (earlier claim retracted). Fruit-value table candidate
  at `$8903` (IY in the collect routine).
- **Collectible fruit table = `$9605`/`$9607`** (31 entries x 2 bytes: `byte0 = X & $F0 | flags`,
  `byte1 = Y & $F8 | flags`). In the snapshot: a banana `(X=64,Y=168)` and an ice lolly
  `(X=224,Y=136)`. Populated when a bubbled enemy is popped (the burst path `$8B4E`).
- **Collect routine = `$8669`** (main loop `$8D4C`): loads the player `$FD80`, scans the table
  (`$8691 LD HL,$9605 / B=$1F`), and `CALL $86A9` per non-empty entry -- the player-overlap check.
- **On collection (VERIFIED, walked P1 right onto the banana)**: at player X=50 the `$9607` entry
  cleared (X `$40 -> $00`), **P1 score `$FFE4` += 1000** (the banana's value), and a fruit-collected
  counter **`$FDE2`** (slot 9, `+8`) incremented `1 -> 2`. Collision has a few px of tolerance
  (fired at X=50 vs the fruit's X=64).
- **Fruit VISUAL is a SEPARATE entity object** (an `$FD80` slot: ptr `$C700`, `(+9)=$FF`, flags
  `$3E/$3F`), animated by `$8A80` (3-frame shimmer `$C700`/`$D340`/`$D360` + a bob). So a fruit
  = a visual entity + a collectible `$9607` entry.
- **In-play controls (real game) = keyboard O=left / P=right** (measured from the snapshot).
- OPEN (smaller now): the per-fruit VALUE table (`$8903`?) and whether value scales with a
  collection combo; `$86A9`'s exact overlap box; the giant fruit / power-ups (the user will
  supply a spawned-collectible and a power-up snapshot next).

## Items: spawned collectible + collect internals (M5) -- score DOUBLY confirmed

A second before/after pair (a SPAWNED collectible, not an enemy-death fruit) reconfirmed the score
address and added detail:

- **P1 SCORE `$FFE4` DOUBLY CONFIRMED**: this pair went `000000 -> 080000` (**+80000**), vs the
  banana pair's +1000. So different collectibles have very different values (banana = 1000; this
  spawned item = 80000), i.e. a per-type value.
- **The collect routine `$8669` checks BOTH players**: `$86A9 -> $86B1` calls the overlap test
  `$87B2` first with `IX=$FD8A` (P2) then `IX=$FD80` (P1), so either player can collect a fruit.
- The spawned collectible is NOT in the `$9607` enemy-fruit table (empty in both snapshots) and did
  not leave a cleanly-isolable removed screen cell (the scene's player+enemies all moved), so its
  exact storage/route is OPEN -- likely a single-instance special-item variable with its own
  **CORRECTED 2026-09-16 (M7.7-I2): `$8903` is NOT a code address.** It is a ten-byte DATA
  record -- a pseudo-entity -- lying in the hole between `$8902` (`C9 RET`) and `$890D`
  (`F3 DI`, a genuine `$8839[12]` dispatch target): `+0/+1` sprite pointer, `+5` X (`$8908`),
  `+6` Y (`$8909`). `$8779` and `$8728` address those bytes ABSOLUTELY, but the blitter `$A2D5`
  reads them THROUGH IY, which `$868D LD IY,$8903` sets inside the WALK. A port that relocates
  the record breaks the ink and the erase while the blit keeps working, and an oracle that calls
  `$8728` without setting IY blits every item to the same wrong address -- and still agrees with
  itself, which is how the first version of the I2 oracle passed while proving nothing.
- OPEN: the per-fruit VALUE table / how a fruit's type maps to its points (banana 1000 vs spawned
  80000); the spawned collectible's storage; the giant fruit (all-enemies-dead) and power-ups
  (a power-up snapshot to come).

## Items: two collectible kinds + score TRIPLY confirmed (M5, via 3 snapshot pairs)

Three before/after snapshot pairs (banana, a spawned item, a purple crown) nailed the score and
revealed two distinct collectible kinds:

- ~~**P1 SCORE = `$FFE4`-`$FFE7` (4-byte BCD) -- TRIPLY confirmed**~~ **RETRACTED -- see above.**
  Three readings of the same one-byte-early window agree with each other and with nothing else: banana `032000->033000` (+1000),
  spawned item `000000->080000` (+80000), crown `034000->074000` (+40000). The HUD shows
  `$FFE4`-as-decimal / 10 (e.g. 034000 -> "3400").
- **`$FDE2` = the collected-items counter** (slot 9, `+8`): increments on EVERY collect (1->2->3
  across the pairs) -- fruit and special items alike.
- **Kind 1 -- enemy-death FRUIT** (banana, ice lolly): stored in the table `$9607` (31 x 2 bytes),
  collect routine `$8669` (scans it, `$86A9` per fruit checks BOTH players `$FD8A`/`$FD80`). Low
  value (banana +1000 internal). Visual = a separate `$C700` entity (`$8A80` shimmer+bob).
- **Kind 2 -- SPAWNED special items** (the purple CROWN, +40000; an earlier item +80000): NOT in
  `$9607` and NOT a normal entity slot -- a SINGLE-INSTANCE special item. Collected by walking
  onto it (same as fruit); on collect the score jumps by a large per-type value, `$FDE2`
  increments, a presence flag **`$B62D`** clears (1->0), and its colour attribute leaves the
  shadow-colour buffer **`$F8xx`** (the crown is drawn PURPLE via its own attribute). Values are
  per-type and high (crown 40000, other 80000). Exact position/storage + draw routine OPEN (the
  diff is dominated by self-mod, and the draw uses scratch pointers `$C05E`/`$8903`).
- Collectible VALUES vary widely by type (fruit ~1000; specials 40000-80000 internally). A
  per-type value table exists but is not yet located.
- OPEN: the spawned/special item's exact storage + draw + value source; the giant fruit
  (all-enemies-dead) and power-ups (ability effects) -- future snapshots.

## Items: SOLVED -- one collectible table $9605 (RETRACTS "specials stored elsewhere")

The spawned/special items are NOT stored separately -- they are in the SAME table as enemy-death
fruit. Earlier I scanned the table from `$9607` and MISSED entry 0 at `$9605`, where the crown sat.
Found via a controlled collect-vs-idle differential + reading the collect routine.

- **ALL collectibles live in ONE 64-BYTE BLOCK, `$9603`-`$9642` = 32 slots x 2 bytes**
  (CORRECTED 2026-09-16 and GATED, M7.7-I1 -- the base is `$9603`, not `$9605`).
  `$8C5E LD HL,$9603 / LD B,$40 / CALL $AA49` clears the whole thing as one unit.
  - **slot 0** (`$9603`/`$9604`) is the SINGLE POWER-UP slot;
  - **slots 1..31** (`$9605`-`$9642`) are the FRUIT / points table.
  `$8689` walks it as TWO PASSES over the one allocation: the pass flag `$872C` is zeroed, the 31
  fruit entries run from `$9605` with `B=$1F`, then `$869F` INCrements the flag and the power-up
  slot is reached by FALLING THROUGH `$86A8`'s conditional RET -- not by a second loop.
  THIS RESOLVES the contradiction this document carried in two places: "all collectibles live in
  `$9605`" and "power-ups are NOT in the `$9605` table" were each half-right about one pass.
- **Entry layout** (verified against on-screen positions across 3 snapshots):
  ```
  byte0 = (X & $F0) | (type & $0F)     X = byte0 & $F0     THE TYPE IS FOUR BITS
  byte1 = (Y & $F8) | (phase & 7)      Y = byte1 & $F8
  byte0 === 0 means EMPTY; byte1 takes no part in that test
  ```
  **CORRECTED 2026-09-16 (M7.7-I1): the type is FOUR bits, not three, and X masks `$F0`, not `$F8`.**
  A three-bit type could never reach types 9..15, which have their own handlers (`$8839`), point
  values (`$8649`) and inks (`$861D`/`$862D`). Proved by every writer -- `$8B9B E6 F0` (the corpse
  landing) and `$8A02 E6 F0` (both spawns) -- and by the reader at `$8788 LD A,C / AND 15 / ADD A,10`.
  **AND THE MASKS GENUINELY DIFFER BETWEEN DRAW AND COLLISION.** `$877C E6 F0` takes the draw X, but
  `$87C9 E6 F8` writes `byte0 & $F8` back into the table for the duration of the `$930A`/`$9312`
  overlap test and then restores it. `$F8` keeps **bit 3 -- part of the type nibble** -- as an X bit,
  so every item of type 8..15 is collision-tested EIGHT PIXELS RIGHT of where it is drawn. A port
  needs both: `itemDrawX = byte0 & 0xF0` and `itemHitX = byte0 & 0xF8`.
  Examples: crown `9A 49` -> X=152,Y=72,type=2; banana `40 AA` -> X=64,Y=168,type=0; ice lolly
  `E2 8A` -> X=224,Y=136,type=2(b1); big item `5B 4B` -> X=88,Y=72,type=3.
- **Type -> three SEPARATE roles (CORRECTED 2026-09-08 -- `$861D` is NOT the value table):**
  - **INK/COLOUR** = **ONE 32-byte table at `$861D` indexed with an OFFSET, not two banks**
    (CORRECTED and GATED 2026-09-16, M7.7-I2). `$8728` does `LD H,($872C) / DEC H / JR z`, so a
    pass flag of exactly **1 -- the POWER-UP pass over `$9603`** -- indexes `$861D` directly, and
    everything else adds `$10` first. So the **FRUIT pass reads the HIGH half `$862D`**, which is
    the opposite way round to what this document said.
    THE POLARITY IS INVISIBLE FOR TYPES 0, 1 AND 8: the halves hold 06, 03 and 06 at exactly those
    three indices, so a test driven by an ordinary banana can have the selection completely
    backwards and pass. Types 5 (06 vs 07), 7 (05 vs 02) and 10 ($FF vs 03) are what make it
    observable, and the gate runs every type through BOTH passes as a control pair.
    `$FF` = random ink via `$873E LD A,R / AND 7`. Only `$861D[10]` is `$FF`, so **random ink
    reaches the screen only through the power-up slot holding type 10** -- it is not, as this
    document said elsewhere, "the '?' bonus item's RESULT"; it chooses an INK and nothing else,
    by patching the `OR n` operand at `$8769`.
  - **SPRITE** = the formula `$5D00 + (type+10)*32`, computed at `$8779` (draw scratch `$8903` / X
    `$8908` / Y `$8909`).
  - **POINT VALUE** = the 16-word table `$8649` (indexed type*2), loaded to `$FFED` at `$8809`,
    added by `$80FA` at `$8817` (see the CORRECTION banner above for the values).
- **The per-round SPAWN `$89CB`/`$8A0D`** -- MEASURED AND GATED 2026-09-16, M7.7-I7.
  - `$89CB`: round >= `$50` forks past the timer entirely; otherwise **`($8DB7) == 4` spawns the
    POWER-UP and `== 2` the POINTS ITEM. Both are EQUALITY tests, not thresholds** -- a `>=` model
    passes at `$0400` and fails at `$0500`. Each has its own one-shot bit in `$8CB0` (bit 0
    power-up, bit 1 points), and a round of EXACTLY 80 clears both before dispatching.
  - `$89E4` the points type: **12 - (`$9AE9`), with >= 12 giving 0 and 0 giving 11** -- so 0 AND 1
    both give 11, because 12 - 0 is 12 and the `CP H / DEC A` pair folds it down. Spawned into
    `$9605`, ENTRY 0 of the fruit table, with its X from `$8CAF`.
  - `$8A0D` the power-up type: round 80 forces 13, round 81 forces 12; a round found in the
    16-byte list `$8A62` takes the `{3,3,4,5}` draw at `$8A2E`; anything else takes the wide draw
    at `$8A38` filtered through the 6-byte exclusion list `$8A72`. Spawned into `$9603` with its X
    from `$8CAE`.
  - **ROUND 77 IS LISTED BUT CAN NEVER RECEIVE ITS LISTING.** `$8A28`'s CPIR runs with BC = 16 and
    decrements on the matching comparison too, so a match on the sixteenth byte -- which is 77 --
    leaves `C = 0`, indistinguishable from exhaustion. MEASURED: rounds 3..75 take the narrow
    draw, 77 takes the wide one. The sixteenth entry is functionally dead.
  - **THE UMBRELLA LOCK**: `$8A76` is the fifth exclusion slot. `$9707` puts the sentinel `$2A`
    there at new game (no 0..15 draw can match it) and `$8A49` writes 6 the instant a draw yields
    an umbrella, so **the umbrella spawns at most ONCE PER GAME and the lock arms at SPAWN**.
  - **A drawn 7 becomes type 14 only when `($7E0E) == 2`**, a water round.
- **The per-frame gate `$8669`** -- MEASURED AND GATED 2026-09-16, M7.7-I5. `$867F CP n` has
  `$8680` as its OWN OPERAND and `$8681` writes back what it just compared, so the test is
  **"has `$8DB6`'s low byte CHANGED since the previous call"** -- an EDGE DETECTOR, not a
  comparison against a constant (this document previously recorded it as `$8DB6 == $E1`, which
  was that capture's previous-frame value). The chain calls `$8669` several times a frame and
  only the first call after an interrupt gets past it. A WATER-CARRIED PLAYER (`+$5A` or `+$64`
  bit 4) jumps straight to the walk, BYPASSING both the gate and the `INC ($86CD)`, so the item
  lifetime clock FREEZES while anyone is carried.
- **The lifetime clock and the phase step `$86CC`** -- `$86CD` is the counter and `$86CF` the
  mask, both OPERAND bytes; `$86D0 INC HL` does not touch the flags, so `$86D1`'s `JR nz` is
  still reading the `AND`. The phase steps only when `(counter & mask) == 0`.
  **DELETION FIRES WHEN THE INCREMENTED PHASE IS 4, so ONLY FROM PHASE 3** -- measured
  `0->1 1->2 2->3 3->DEAD 4->5 5->6 6->7 7->0`. A phase-4 entry steps to 5 and SURVIVES, which
  matters because the round-transition row writer seeds phase 4 into 160 entries. The expiry
  clears byte0 and FALLS THROUGH into the erase.
- **The erase `$86E6`/`$876C`/`$A314`** -- `$876C` picks the round's open-cell colour `$8309` or
  its platform colour `$830A` PER CELL, from bit 5 of the COLOUR SHADOW, and writes the REAL
  attribute file. A non-zero `$FECE` jumps straight to `$A314`, skipping the attributes entirely.
  `$A314` restores 16 rows from the shadow at display + `$A000` in three bands of `(8 - Y&7)`,
  `8` and `Y&7`; items always have `Y&7 == 0`, so the third band is DEAD CODE for collectibles.
  An item on the BOTTOM ROW loses its lower half: the second band reads `$FD30`, past the
  24-entry table, which is `$0000`, so it addresses page 0 and the machine drops the writes.
- **Collect** (`$8669` -> `$86A9` -> `$86B1`, per entry) -- MEASURED AND GATED 2026-09-16, M7.7-I3:
  - **P2 (`$FD8A`) is tested BEFORE P1 (`$FD80`)**, and `$86BD`/`$86C9` re-read byte0 and `RET z`,
    so an entry one player takes is ABANDONED for the frame. With both players on one fruit,
    **P2 wins**. Invisible in 1P, where P2's `+7` bit 7 is clear and `$87B7` returns at once.
  - **the box is `px-15 .. px+14`** -- near edge inclusive, far edge EXCLUSIVE -- from
    `$930A`/`$9312`, which are ONE predicate on two register pairs. Both adds are EIGHT BIT, so
    the box shrinks at the low edge and **VANISHES ENTIRELY for a player coordinate >= 241**.
  - **the COLLIDE mask is `$F8`, not the draw's `$F0`.** `$87C9` writes `byte0 & $F8` back into
    the table for the duration of the call and restores it after. `$F8` keeps BIT 3 -- part of the
    type nibble -- as an X bit, so **every item of type 8..15 is collision-tested EIGHT PIXELS
    RIGHT of where it is drawn** (measured: type 1 collects for px 50..78, type 9 for 58..86, both
    drawn at X=64).
  - **`$87B2`'s first byte is LIVE STATE**: `$94DB` writes `$C9` to switch collection OFF and
    `$956D` writes `$00` to switch it on. This is why an earlier session could park a player on a
    fruit and see nothing happen.
  - **BIT 6 of `(IX+$5A)` locks collection out entirely** and there is NO `RES 6` anywhere in the
    image, so it clears only on a whole-byte write (respawn, or a new game).
  - on a collect it **clears byte0 ONLY -- byte1 SURVIVES** (which is what lets `$89FB` refill a
    slot by writing byte0 alone), increments the items counter `(IX+$62)`, and records the type in
    `$8828`, the OPERAND of `$8827 LD A,n`. Then the erase `$86E6` and the award `$80FA`.
  (The old per-collect figures +40000/+80000 are PROVISIONAL -- see the CORRECTION banner; the
  traced award caps at +1000 internal.)
- So the ENGINE model is simple: one 31-slot collectible table at `$9605` (pos+type per slot),
  a type->value/sprite table at `$861D`, and a walk-over collect. Enemy pops write a fruit entry
  here; the level's special items are pre-placed entries with high-value types.
- OPEN (small): the `$FF` random-ink roll observed live; power-up items (ability effects) -- a
  future snapshot. (The `$861D`/`$8649`/`$5D00`-formula chain is now resolved -- see above.)

## Power-ups (M5) -- effect + the player parameter struct (VERIFIED via a power-up snapshot)

The red LAMP power-up (power-up TYPE 2 = long range + fast bubbles; see the CORRECTION in this
section -- NOT a super-combo) was collected in a controlled collect-vs-idle differential. It
resolves the long-standing "slots 9/10 = $0200/$0201 control slots" mystery:

- **Slots 9 (`$FDDA`) and 10 (`$FDE4`) are the two players' BUBBLE / POWER-UP PARAMETER structs**
  (P1 = slot 9, P2 = slot 10) -- NOT drawable entities (that is why their "sprite ptr" was the
  odd `$0200`/`$0201`). Fields identified so far (P1, `$FDDA`+):
  ```
  +4  $FDDE  bubble travel-distance CAP   (the value the bubble-travel code reads at $FDDE/$BE46)
  +5  $FDDF  range-related
  +7  $FDE1  power-up flags
  +8  $FDE2  collected-items counter
  ```
- **Red LAMP = power-up TYPE 2 = long range + fast bubbles** (CORRECTED 2026-09-08 -- it is NOT a
  3-ability super-combo and NOT rapid fire; handler `$88EC` = `CALL $88F4` (range=`$10`) then falls
  into `(IX+$5F)=3`). The controlled differential showed THREE slot-9 fields move, but only TWO are
  abilities -- the third (`$FDE1`) is the last-collected-type recorder:
  ```
  $FDDE (+4)  8 -> 16   LONG RANGE   (bubble travel-cap doubled)
  $FDDF (+5)  7 -> 3    RAPID FIRE (blow-cadence mask; MEASURED 2026-09-09: blow interval 16 -> 8 frames, bubble speed unchanged)
  $FDE1 (+7)  0 -> 2    LAST POWER-UP TYPE (=2), written $8829 LD (IX+$61),A -- NOT an ability
  ```
  **ALL SIXTEEN HANDLERS MEASURED AND GATED 2026-09-16 (M7.7-I6)** -- each called directly with
  every write in `$4000`-`$FFFF` logged, so this list is what the machine does, not a reading:
  ```
   0 $88EF  (IX+$5F) := 3                     blow cadence
   1 $88F4  (IX+$5E) := $10                   bubble range
   2 $88EC  CALLs $88F4 then FALLS THROUGH into $88EF -- BOTH of the above
   3 $88F9  $FECC := 1
   4 $88FD  $FECC := 3      }  ONE handler, genuinely identical; 4 and 5 differ
   5 $88FD  $FECC := 3      }  ONLY in $8649 and $861D
   6 $88B1  LFSR -> {3,3,5,7} -> $FECD, then JP $A110 -- DOES NOT RETURN
   7 $88C3  $FECE := 1, $9049 := 1, $8309 := $2F, $830A := $2F, then $88E0
   8 $88D5  $FECF := 1, then $88E0
   9 $88DC  SET 5,(IX+$5A), FALLS THROUGH into $88E0
  10 $8859  $FED0 := 1; SET 3,(+$5A) and SET 2,(+7) on BOTH players; $8E0A(4); then $8888
  11 $8883  $FED2 := 1, then $8888
  12 $890D  the LEVEL SKIP: zeroes BOTH ISR gates $FEC4/$FEC5, then the round machinery -- (h)
  13 $889C  SET 6,($FDDA) and SET 6,($FDE4) -- ABSOLUTE, BOTH players: the COLLECT LOCK
  14 $88A7  SET 2,(IX+7) and (IX+$5B) := 3    fast walk
  15 $88B0  a bare RET -- its whole effect is $BD56's CP 15, downstream
  ```
  **`$88E0` THE DIAMOND PIN** (the tail of 7, 8 and 9): `LD HL,9 / LD ($8B9F),HL` writes 9 AND
  ZEROES `$8BA0`, which is the `INC A` OPCODE of the fruit-type generator, and `LD A,$FF /
  LD ($8BA2),A` widens its mask. The generator is pinned to a constant 9, so **every later corpse
  in the round drops a DIAMOND**. All thirteen in-game dumps hold `$8BA0 = $3C`, so this state has
  never been captured -- it exists only after one of these handlers runs.
  **`$8888` the shoot-gate refill** (the tail of 10 and 11): `$A891`-`$A898` := `$FF`, `$8DBD` := 0.
  **`$8829 LD (IX+$61),A`** records the collected type, read later by `$BD56 CP 15`.
  plus +3000 to the score `$FFE4` and `$FDE2` (counter) increments. (Earlier I mis-read this as a
  range-only "teapot"; it is the red lamp, and the multi-field change is the combo, not a bug.)
  The individual sweet power-ups will each set just ONE of these fields -- exact per-field->ability
  assignment (which of $FDDF/$FDE1 is speed vs fire-rate) confirmable with an individual-sweet snapshot.
- **Power-ups are drawn by `$A2C2`/`$A2D5`, NOT `$A824`** (CORRECTED and GATED 2026-09-16,
  M7.7-I2 -- `$A824` is a different subsystem, called three instructions earlier in the same
  main-loop chain). `$A2C2` NOPs the two `OR (HL)` at `$A307`/`$A30C`, calls the 16x16 UNMASKED
  blit `$A2D5` (two bands of 8 rows, 2 bytes a row, 32 bytes of sprite, row base from the `$FD00`
  table, column self-modded into `$A304`), then restores `$B6`. **So the item blit is OPAQUE
  while every other caller of `$A2D5` ORs** -- which is invisible over the empty sky an item
  normally sits on, so the gate runs every case twice, on a black destination and a white one.
  A blit that died between the NOP and the restore would leave every later OR-blit in the game
  silently opaque, so the oracle asserts `$A307 == $A30C == $B6` after every call.
- ~~**Power-ups are SPECIAL items** (single-instance, drawn by `$A824` via the self-modified draw
  scratch `$8903`(sprite)/`$8908`(X)/`$8909`(Y), sprite `$5D20` here) -- collected by walking onto
  them like fruit, but NOT stored in the `$9605` collectible table (the teapot was absent from it).
  Their exact object storage is a single-instance special-item var (partially open, same mechanism
  as the crown's `$A824` draw).
- **Engine model**: each power-up, on collect, writes one or more fields of the collecting player's
  slot-9/10 param struct + awards points, and records its own type into `$FDE1` (+7). The red lamp
  (type 2) sets the TWO ability fields (range + speed); other power-ups set their own field(s).
  Findable the same way (one controlled snapshot each).
- OPEN: the other power-up types' fields; the special-item object's exact storage/spawn; the
  candy-cane -> giant-fruit-on-clear mechanic.

## Power-ups: field mapping CONFIRMED via the purple sweet (long range) (M5)

The purple sweet (single "long range" sweet) collected in a controlled diff changed **only
`$FDDE` 8->16** (`$FDDF` stayed 7), plus `$FDE1` 0->1 and +2000 score. This isolates the fields:

- **`$FDDE` (slot9 +4) = BUBBLE RANGE cap** -- CONFIRMED (both the purple sweet and the super lamp
  set it 8 -> 16). This is the value the bubble-travel code reads (`$BE46`/`$FDDE`).
- **`$FDDF` (slot9 +5) = FAST BUBBLES** -- untouched by the range sweet; only the lamp set it
  7 -> 3. So it is a separate ability (the fast-bubble sweet's field).
- **`$FDE1` (slot9 +7) = LAST-COLLECTED POWER-UP TYPE** (CORRECTED) -- written by `$8829
  LD (IX+$61),A` on every collect, so purple sweet -> 1, red lamp -> 2. It is a type recorder, NOT
  a rapid-fire / tier flag (rapid fire = the separate type-14 power-up `$88A7`).
- Per-sweet POINT values differ: purple sweet +2000, super lamp +3000 (into `$FFE4`).
- **Engine model (firm now)**: a sweet writes its one field of the collecting player's slot-9/10
  struct (`$FDDE` range, `$FDDF` speed, `$FDE1` tier); the super lamp writes all three. Remaining
  individual sweets (the fast-bubble one, the rapid-fire one, speed shoes) each move one field --
  one controlled snapshot each to label them, but the field SET and the range mapping are proven.

## Power-up: BLUE CROSS = water special-effect -> diamonds (M5, VERIFIED)

Collected in the harness (from the correct snapshot) and observed frame by frame + on screen:

- **Blue cross = a SPECIAL-EFFECT power-up** (not a param-field one). On collect: **+8000** to the
  score, and it triggers the WATER effect via the self-modified special-effect engine at
  `$A824`/`$A84D` (which sets a mode `$A839` and a row count and reconfigures draw pointers into
  `$5B00`/`$C080`).
- **Water = a rising CYAN attribute fill of the whole playfield**, one char row at a time from the
  BOTTOM up (~100-200 frames to fill). Verified on screen: the entire play area turns cyan.
- **When the water fills, all enemies die** -> a big bonus (score jumped +30000 for the 3 enemies),
  their flags go to a death state (`$E8` -> `$BE` -> `$3E`).
- **The dead enemies become DIAMONDS**: entries appear in the `$9605` collectible table -- 3 x
  `29 A9` (X=40, Y=168, **type 9** -- the 4-bit type; my old "1" was a 3-bit `&7` decode) at the spots where the corpses landed. So diamonds are ordinary
  `$9605` collectibles (type 9, value `$8649[9]=$1000` = 10,000 on screen) and are collected for points like any fruit.
- This confirms the collectible/power-up TAXONOMY:
  1. **Points collectibles** (fruit, crown, DIAMONDS) -> `$9605` table (pos + type); collect adds
     the type's value.
  2. **Field-setting power-ups** (sweets: range `$FDDE` / speed `$FDDF` / fire `$FDE1`; super lamp =
     all three) -> write the collecting player's slot-9/10 param struct.
  3. **Special-effect power-ups** (blue cross water) -> run the `$A824`/`$A84D` effect engine
     (level-wide water -> mass kill -> diamond spawn).
- OPEN (small): the exact water-row counter / fill routine internals; the mass-kill->diamond
  conversion code; other special-effect power-ups (umbrella skip, etc.).

## RNG (M5) -- TIED DOWN: a deterministic PRNG + a little hardware R

Resolves the long-open Q18. The game uses TWO randomness sources:

- **PRIMARY: `$FE85` -- a deterministic self-modifying PRNG** (reproducible). Its state is the
  `LD HL,nn` operand at **`$FE86/$FE87`**, which it rewrites each call (`$FE91 LD ($FE86),HL`):
  ```
  FE85 LD HL,(state)          ; HL = state at $FE86/87
       LD A,H / RLCA / XOR L / ADD $FE / LD H,A
       RRCA / XOR L / LD L,A
       LD ($FE86),HL / RET     ; new state = returned HL
  ```
  VERIFIED deterministic: seed `$002A` -> the fixed sequence `283E 6C08 CE6F F017 F46D ...` every
  time. **11 call sites** drive item drops/spawns, the grid-fill, round setup and selections
  (`$88B1 $8AFD $8B11 $8BD7 $8BDF $950F $971D $9775 $9B28 $A0D0 $B414`). So it is fully
  portable -- reproduce the algorithm and the state and every PRNG-driven choice matches.
- **SECONDARY: `LD A,R`** (the Z80 refresh register, hardware/timing pseudo-random) at a FEW
  flavour sites only: enemy facing/waddle (`$B008`/`$B0D5`), bubble drift when blocked (`$B88D`),
  the "?" bonus-item result (`$873E`, `AND 7`), and a screen-splatter effect (`$FEAC`). These are
  NOT cleanly reproducible without cycle-exact R; the port models R or uses a declared substitute
  (manual E1) -- and they only affect cosmetic wobble, not scoring/structure.
- `$FEBB`/`$FEC7` are **NOT seeds at all** (CORRECTED 2026-09-10, causally proven by poking, docs/RNG.md):
  `$FEBB` is the operand of `LD (HL),n` at `$FEBA` (the front-end splatter's attribute byte, rewritten
  1024 times per wipe, with no reader anywhere in the image); `$FEC7` is the next-round LOOKAHEAD,
  R-injected only at the round-82 wrap. The ONLY PRNG seed is `$FE86/$FE87`. They are NOT rolling
  PRNG state.

**How the items are chosen:**
- **Power-ups & pre-placed collectibles** (crown, blue cross, sweets, lamp): set up at round start
  (the placement path calls the `$FE85` PRNG, `$971D`/`$9775`) -- deterministic given the PRNG state
  (and/or round data). Reproducible.
- **Spawned collectibles / enemy-pop fruit**: type/position via the deterministic PRNG `$FE85`
  (the `$88xx`/`$8Bxx` drop code calls it). Reproducible.
- **Corpse drops from the water kill**: FIXED -- `$88E0` pins the corpse-drop type generator (self-mod `$8B9F`/`$8BA0`/`$8BA2`) to type 9 = DIAMOND, so every drop is a diamond (there is no "$8940 routine"; the type is 9 in the 4-bit field, not 1)
  (all type 9), no PRNG roll. Normal corpse drops take the ROTATING type from that generator (`LD A,n / INC A / AND 7 / store` = 0..7 cycling).
- **The "?" bonus item**: the one genuinely hardware-random result (`$873E` `LD A,R`).

**Engine takeaway**: implement `$FE85` exactly (a tiny function + a 16-bit state) and nearly all
item/drop/spawn randomness is byte-exact; only the enemy waddle / bubble drift / "?" item use R
(model R or substitute, cosmetic).

## Items: corpse drops + type encoding REFINED (candy-cane snapshot, round 3)

The candy-cane "all enemies dead -> corpses drop fruit" snapshot (round 3: banana, magenta petal,
blue ice lolly + one corpse still falling) refined the collectible model:

- **Type = `byte0 & $0F`** (4 bits, up to 16 types), NOT `& 7` (the value logic at `$8728` does
  `AND 15`). Retract the earlier `type & 7`.
- **Fruit identity is PER-ROUND**: in round 3, type 0 = banana, type 1 = magenta petal, type 2 =
  blue ice lolly (verified on screen against the `$9605` entries `@9607 60 6A t0`, `@9609 D1 8A t1`,
  `@960B D2 AA t2`). The same type index maps to a different fruit sprite in another round (the
  `$861D` class + the round select the actual sprite/value).
- **My earlier "crown" was a type-10 "?" item**: its entry was `$9A` -> type `$0A`=10, and
  `$861D[10]=$FF` = the RANDOM path (`$873E LD A,R`). So the high-value crown was a "?" bonus roll,
  not a fixed type -- which is why its "storage" looked odd (it WAS `$9605` entry 0 all along, a ?
  item). The 80000 item was `$5B` -> type `$0B`=11 (`$861D[11]=05`).
- **Corpse-drop mechanic (verified)**: a killed enemy becomes a CORPSE entity (`$FD80` slot, ptr
  `$C700`, `+9=$FF`) that FALLS; on landing it converts to a `$9605` collectible entry with a fruit
  type. The candy cane triggers this for all enemies at once (three corpses -> types 0,1,2 here).
  Water-kill corpses instead all became diamonds (fixed) -- so the drop TYPE depends on the KILL
  method (candy cane -> the round's fruit set, cycling/varied; water -> diamonds).
- So the full type map (round-independent slots): 0-N = the round's fruit set; 10 = "?" random
  (R-rolled); 11 = a high-value special; (the DIAMOND is type 9 = 10,000 on screen -- what the water-fill and red-cross-fireball kills drop, via the `$88E0` pin; normal drops cycle 0..7 from the self-mod counter at `$8B9F`).

## Giant items: candy-cane -> GIANT DIAMOND (M5, VERIFIED LIVE 2026-09-09 via `candycane.pkl`)

The candy cane ARMS the giant; the giant DIAMOND drops when the **last corpse lands** (the
level-clear cleanup consumes the arm). Traced live by driving `candycane.pkl` (round 3: candy cane
present at (160,32), player at (144,32), one corpse still falling):

- **TRIGGER / TIMING (MEASURED in TWO separate runs -- the two halves are distinct observations):**
  the level-clear event is the **last corpse SETTLING** (its entity `+7` active bit clearing,
  `$BF -> $3F`; slot3 in `candycane.pkl`). At that exact frame the level-clear cleanup
  (`$8F00`/`$8F1A`) runs and does ONE of two things:
  - **(a) if the cane WAS collected** (arm `$FECC=1` via dispatch `$88F9`): the giant SPAWNS --
    MEASURED in a clean `run_frames(1)` replay: cane collected f1, armed f2; **f61** slot3 went
    `$BF->$3F` and on that same frame `$FECC` was consumed and `$A839` began dropping 4->...->19
    (src `$A8C2=$5B00`); landed Ytile 19 at f76; collected f77 = +5600. (The player's snapshot
    `falling_onto_candycane` shows this half: cane already collected, giant present.)
  - **(b) if the cane was NOT collected**: the uncollected cane is CLEARED -- MEASURED in a
    no-input run of `candycane.pkl`: `$9603` `$A3 -> 00` on the same slot3 `$BF->$3F` frame (f61),
    with NO giant (`$FECC`/`$A839` stayed 0). Only the cane was present to observe; the player's
    broader statement that ALL power-ups clear at this moment is consistent but only the cane was
    measured.
  CONSEQUENCE (user, now backed by (b)): the cane must be collected BEFORE the last corpse settles
  -- one enemy/corpse must still be in the air when you grab it. (My first no-input trace saw no
  giant only because the player never walked into the cane; it was in fact observing half (b).)
- **The candy cane is a collectible power-up** (in the level). Its OWN collect value is **+40
  internal = 400 on the HUD** (`$8649[3] = $0040`, the type-3 entry of the point-value table;
  MEASURED: score 4241 -> 4281 at f1 -- distinct from the giant's +5600 / 56,000, which comes later). Collecting it (player
  walked RIGHT onto it, key P) cleared `$9603` `$A3->0` and set `$FECC=1`.
- **The giant diamond is a 32x32 SPRITE** (4x a normal 16x16 collectible) -- a distinct SIZE CLASS.
  CORRECTED 2026-09-08 (retracts the `$5EA0` base and `$A929`-as-draw):
  - **DRAW = `$A8C1`** (the 32x32 blitter), whose SOURCE is a self-modified operand at `$A8C2`,
    set by `$A84D` to `$5B00` (mailbox 1 = giant diamond), `$C080` (mailbox 3 = giant fruit) or
    `$FE02` (the boss). **CONFIRMED LIVE 2026-09-09:** as the giant dropped, `$A8C1` FIRED with
    `$A8C2 = $5B00` -- so the diamond is drawn by the 32x32 `$A8C1` blit from `$5B00`, NOT the
    `$A280` tile route (settles the earlier `$A8C1`-vs-`$A280` open).
  - **ERASE/restore = `$A925`** (driver `$A9DA`), which copies the clean `$A000`/`$E000` shadow
    back to the display; **`$A929` is INSIDE that erase path, not a draw.**
  - `$5EA0` is NOT the giant -- it is the 16x16 type-3 collectible (`$5D00 + (3+10)*32`).
- **THE SPAWN, PORTED AND TIMED (M7.97, `tools/giantspawn.py` -> `build/giantspawn_fixture.json`).**  Until
  M7.97 the port did not make `$8F26 CALL $A84D` (a declared gap): a round cleared with the mailbox armed gave
  no giant.  Now `roundClearOnce` hands ($FECC) to `bossSpawn` and charges its T with `$8E3A`'s (rcSub).
  MEASURED: three natural `$A84D` runs over 48 states x 300 frames (candycane A = 1 and peachspawn A = 3 from
  `$8F26`, returning to `$8F29`; bossspawn A = 4 from `$A9F9`'s tail jump, returning to `$8D31`), ten forced
  (A = 0..5, $11, $13, $80, $FF): T = 150 + 38 (c = A - 1 = 0) / 62 (c = 2) / 67 (else) -- 188 / 212 / 217 --
  and SEVEN writes, no input read but A.  Only peachspawn holds ($FECC) at load (3).  Through-runs (round1_48
  cleared with ($FECC) = 1 / 3): the giant ticks in the clear's OWN frame (`$8EF9` zeroed ($8DBD), so `$A824`'s
  operand gate reopens -- row 4), reaches 19 sixteen frames on, sits there, and the round advance's `$9855`
  clears it 375 frames on.  FOUND: (1) `$A82D` (that gate's operand) loads as $2A (build/boot.pkl, every
  round-1 capture); the port's reset left 0, so its first giant would have skipped a tick -- seeded since M7.97.
  (2) round1_48 holds the overlap pair `$A98F/$A990` at `00 69`, mid-decay: a giant spawned there runs NOP /
  LD L,C, `$A969` returns into `$8A00` and the machine CRASHES 91 frames on (the through-runs poke the decayed
  `00 00`; the port models the endpoints only, bossAxis).  (3) the advancing pass straddles the interrupt (the
  last `$A824` entry a frame before `$9855`'s clear): the port's atomic pass ticks once more (TRAPS #90), DECLARED.
- **Giant spawn/store chain (MEASURED, N18)**: a special of dispatch-type 3/4 (`$8839` ->
  `$88F9`/`$88FD`) sets the mailbox `$FECC` = 1/3; `$8F1A` reads+clears `$FECC` and `CALL $A84D`,
  setting `$A839 = 3` (active/drop phase) and self-modding the `$A8C1` source. Per frame the giant
  DRIVER `$A824` (dispatched at `$8D46`) runs draw `$A8C1` / collect `$A9B1` / erase `$A925`.
  Collect `$A9B1 -> $A969` (overlap) awards a value from `$A9EA` (bytes `40 20 10`) indexed by
  `($A85C)-1`, via `$FFEE` -> `$80FA`, then clears `$FECC` and `$A839`.
- It **drops from the top and lands at (112, 152)** = bottom-centre, the SECOND-FROM-BOTTOM char row
  (row -1), matching the player's account.
- Per the player, this is the SAME mechanism as the giant FRUIT -- so a giant fruit is the same
  32x32 special object with a different sprite, under the analogous condition. (The candy cane -- power-up type 3, `$88F9`, mailbox 1 -- gives the giant DIAMOND; the RED candy
  cane -- type 4, `$88FD`, mailbox 3 -- gives the giant FRUIT/peach. MEASURED, not "other
  end-of-level conditions".)
- **GIANT FRUIT (peach) chain -- MEASURED LIVE 2026-09-09 from three snapshots
  (`peach_candy-cane` / `peach_spawn-in` / `falling_onto_peach`), the exact mirror of the diamond:**
  (1) the RED candy cane is power-up **type 4** (`$9603=$A4`, dispatch `$8839[4]=$88FD`); walking
  onto it scores its own `$8649[4]=$0050` = **+50 internal / 500 on screen** and two frames later
  ARMS **`$FECC=3`** (two enemies were still alive -- the arm happens before the level clears, per
  the cane rule). (2) On the frame the last corpse settles (f11, slot4 `$BF->$3F`) the arm is
  consumed, `$A839` 0->4, and **`$A8C1` fires with src `$A8C2=$C080`** -- the giant fruit's live
  draw path; it lands Xtile 14 / Ytile 19. (3) A natural fall onto it (no input): `$A85C=2` ->
  idx 1 -> `$A9EA[1]=$20`, `$A9C2 LD ($FFEE),$20`, internal `00003133 -> 00005133` = **+2000 =
  20,000 on screen** (HUD `31330 -> 51330`) -- the code-derived prediction confirmed exactly.
- So there are THREE collectible/draw classes now: (1) 16x16 collectibles in the `$9605` table
  (fruit/diamonds/etc.); (2) 16x16 single-instance specials via the `$A824` driver; (3) 32x32
  GIANT items via the `$A824` driver (blit `$A8C1`, erase `$A925`) (giant diamond/fruit).
- **VALUE (MEASURED LIVE 2026-09-09):** the giant DIAMOND awards **+5600 internal** -- and it comes
  from an OUT-OF-BOUNDS read (a double-decrement quirk). `$A84D` does `DEC A` on the mailbox (1 ->
  `$A85C = 0`); the collect `$A9B6` does `LD A,($A85C) / DEC A` AGAIN -> index `$FF`; `HL = $00FF +
  $A9EA = $AAE9`; `LD A,($AAE9) = $56`; `LD ($FFEE),A` -> `+5600` (byte1 of the BCD add) via `$80FA`.
  `$AAE9` is a stray byte inside an unrelated routine, so the diamond's value is unintended-but-stable.
  MEASURED twice (`$FFE6` `$42->$98` in a natural-ish collect; `00->$56` with items cleared; the
  write-watch logged `$A9C2 LD ($FFEE),$56`). The giant FRUIT (mailbox 3 -> `$A85C = 2` -> idx 1)
  reads `$A9EA[1] = $20` cleanly = **+2000 = 20,000 on screen, MEASURED LIVE** (`falling_onto_peach.szx`, natural fall: `$A9C2 LD ($FFEE),$20`, internal `00003133 -> 00005133`, HUD `31330 -> 51330`); the `[40,20,10]` table is correctly indexed only for
  mailbox >= 2. **RECONFIRMED via a fully NATURAL collect (`falling_onto_candycane.szx`): the player
  fell onto the landed diamond with zero input/poking; at the collect frame the write-watch logged
  `$A9C2 LD ($FFEE),$56` and P1 went `00004281 -> 00009881` = +5600, `$A85C=0`.** On the HUD that
  is **+56,000** (`42810 -> 98810`; the display is internal x 10 -- see the HUD-layout section), so
  the OOB `$56` quirk lands on a very plausible-looking big-bonus value. **PLAYER-CONFIRMED from real play: the score goes up by 56,000 on collecting the diamond** -- three independent confirmations (internal delta, decoded HUD digits, player observation).

## Item lifetime (phase clock) + level-clear cleanup -- MEASURED 2026-09-09

One mechanism explains item timeouts AND what vanishes when a level is cleared (both facts
supplied by the player, now measured from code + `candycane.pkl` / `crown.pkl`):

- **Every collectible carries a 3-bit PHASE** in byte1 bits 0-2 -- the power-up slot
  `$9603/$9604` and every `$9605` entry alike (the low bits I had loosely called "flags/state").
- **Phase stepper `$86D9-$8718`** (per item, after the collect check `$86C0 CALL $87B2`):
  `phase = (phase+1) & 7`; **if it reaches 4 the item is REMOVED** -- `$86E4 LD (HL),0` (byte0:=0)
  then erased from the shadow (`$AEDC`/`$876C`; `$A314` path if the water-fill flag `$FECE` is
  set); otherwise the new phase is stored at `$8718`. Its gate (`$86CC-$86D7`): `LD A,[$86CD] / AND [$86CF]=$FF / JR nz,skip` -- **`$86CD` is a live
  8-bit TICK COUNTER** (static `$93`, seen `$7E` live) and the stepper runs only when it reads 0,
  i.e. **once per 256 frames**; a second gate skips while `$FED1` (level-transition flag) is set.
  The level-clear writes **`$FF`** into `$86CD`, so the counter wraps to 0 on the very next tick =
  a forced immediate step (why the marked items vanish at once). The counter is incremented in place at `$8688` (`LD HL,$86CD / INC (HL)`, in the item-scan routine); the 256-frame period is MEASURED. MEASURED (crown idle, no clear): phase 1->2->3->removed at
  f130 / f386 / f642, `$8DBD` = 705 / 961 / 1217. **This is the item TIMEOUT.** A spawned special
  starts at phase 1 (~3 steps of life); a fresh corpse drop is written at phase ~2 (~2 steps).
- **Level-clear routine `$8ED4+`** -- fires when the LAST CORPSE SETTLES (its entity `+7` bit7
  clears, `$BF -> $3F`). In order: `$8CB0`/`$86CD` := `$FF` (self-mod gates); **`$9604 |= 3`**
  (the POWER-UP slot's phase) and **`$9606 |= 3`** (`$9605` ENTRY 0 = the spawned-in points
  item) -- and NOTHING to entries 1+; `$8DBD := 0` (play timer); `$9049 := 1`; then `$8F00`
  resets the 12 bubble slots (`+9=0`, `+4=$7F`) and consumes the giant mailbox (`$FECC` -> `$A84D`).
- **Consequences (all MEASURED):**
  - **The power-up AND the spawned-in points item clear on the last-corpse impact**: forced to
    phase >=3, the immediate step tips them to 4 -> `$86E4` within the same/next frame. Cane:
    `$8EE4` marks `$9604`, `$86E4` zeroes `$9603`, both at f61 (candycane, no collect). Crown
    (`$9605` entry 0, `crown.pkl` with its last enemy turned into a falling corpse): `$8EEC` marks
    `$9606` `$49->$4B` at the settle (f17), `$86E4` zeroes `$9605` at f18.
  - **Corpse drops REMAIN.** The landing corpse's own drop is written at the settle
    (`$8BA7` byte0 / `$8BB0` byte1) and is untouched by the marks; pre-existing drops keep their
    natural phase (2->3 at the clear, removed by the clock 256 frames later: entries 1-3 at
    f317 = f61+256). The freshest drop outlives the ROUND SCROLL: entry 4 was still present at the
    f436 advance to round 4; the new round's init then rebuilt the table (f438-504). So "corpse
    drops remain even while the level scrolls to the next" holds -- unless the 256-frame clock
    expires an older one first.

## Core loop: bubble collision -> capture -> burst -> corpse -> fruit (M5, VERIFIED live)

The three core mechanics, staged and verified in the harness (capture + pop), correcting the
earlier bit-3/`$5CE0` mis-trace:

- **Bubble<->enemy COLLISION**: a travelling/floating empty bubble runs the overlap check `$BE5B`
  each frame -- `PUSH IY/POP IX`, patches `$92DE`->RET around the SHARED collision `$92C0`, and on a
  hit returns the enemy's slot index `(HL-$FD9B)/10`. (Bubble travel distance is capped by `$FDDE`,
  the range param the teapot/lamp power-up doubles.)
- **CAPTURE** (`$BE80`, VERIFIED LIVE): on a hit the bubble becomes HOLDING -- `(IY+9)=1`,
  `(IY+8)`=captured enemy index, hold-timeout `(IY+4)` from `$745A` -- and the enemy gets `SET 3,
  (IY+7)` (captured/frozen). The held bubble draws the enemy inside (sprite `$C900`, flashing with `$C780` when
  flashing/about to escape). Staged by poking the player beside an enemy at the same Y facing it,
  then blowing; the bubble captured it in ~2 frames.
- **ESCAPE** (timeout, `$B679`): if not popped in time the enemy is released back to WALK with
  `SET 2,(IY+7)` = the speed-doubler (ANGRY/fast).
- **Corpse frames DRAWN LIVE -- CONFIRMED 2026-09-09 (`fbkill`):** the two flying corpses read
  `$C700-$C71F` and `$D340-$D37F` through the MONO blitter inner loop `$A2B4`/`$A2B9` (128/448
  reads over the flight) -- the mono 32B format and the `$A280` route confirmed in situ, not just
  from the read-watch span.
- **BURST by the player** (VERIFIED LIVE): when the PLAYER TOUCHES a holding bubble it pops
  (deactivates) and the trapped enemy immediately becomes a CORPSE -- ptr cycles
  `$C700`/`$D340`/`$D360` (the same frames the fruit update `$8A80` animates) with state `+9=$FF`,
  launched on a BALLISTIC BOUNCE (the `$B0F7`/`$B154` arc via tables `$B59D`/`$B5BD`; Y oscillates).
- **CORPSE -> FRUIT**: the bouncing corpse is the same `$8A80` fruit-entity in its falling state;
  when it lands it registers as a collectible entry (type per round). So enemy-pop fruit,
  water-kill diamonds and candy-cane corpse-drops all share ONE pipeline: enemy -> corpse entity
  (`$C700`, `+9=$FF`, bounce/fall) -> land -> an item entry.
- **The FALL `$8B4E`, the FLOOR PROBE `$8BB4` and the LANDING `$8B83`** -- MEASURED AND GATED
  2026-09-16, M7.7-I9.  Corrections to the above: the landing entry is written from **`$9607`,
  which is ENTRY 2**, not `$9605` -- entries 0 and 1 are reserved for the round's power-up and
  its spawned-in points item, so corpse fruit only ever takes 2..31.  An entry is FREE when
  **byte0** is zero; byte1 is not consulted (built: three entries carrying a type and X with
  byte1 = 0 are all walked past).
  - The fall is NOT parity-gated: every frame it advances `(IY+4)`, forces the sprite back to
    `$C700`, and steps Y by exactly two.  **`(IY+4)` does a different job here than in flight**:
    there it is a 0/1/2 shimmer cursor, here a full EIGHT-BIT TIMEOUT that lands the corpse when
    it **wraps to zero**.  Built and run 256 frames with the colour shadow clear everywhere:
    at frame 254 `(IY+4)` is 255 and the corpse is still falling; at frame 255 it wraps to 0 and
    lands.  A fall from the top of the playfield is about 96 frames, so this is unreachable in
    play and no capture could show it.
  - The probe reads the **colour shadow** (`$F800`, bit 5), not the display: a world with every
    display byte `$FF` and bit 5 clear does not land.
  - **EITHER floor cell lands it.**  `$8B65 CALL $AED1` returns with the flags already set from
    (X, Y+16), which `$8B69` reads; only then does `$8B6B` read the cell `$8B68`'s `INC HL`
    stepped to.  Built: floor_left alone lands, floor_right alone lands, neither falls.
  - **A solid cell in the corpse's OWN two rows means EMBEDDED, and it KEEPS FALLING** -- the
    opposite of "solid means stop".  `$8BB4` is called exactly twice, covering rows Y+8 and Y,
    both columns; a solid cell one cell row higher does not stop the landing.
  - **`$AED1` has an above-the-HUD guard**: for Y+16 < `$18` it returns the `$712F` dummy with
    A = 0, which reads as AIR.  Built with the floor row solid and the body rows clear:
    Y+16 = 16, 18 and 23 still fall; 24 and 32 land.
  - **THERE IS NO BOUNDS CHECK AFTER THE `DJNZ`.**  The scan runs `LD B,$1E` from `$9607`, so with
    all thirty-one fruit slots taken HL ends at `$9643` -- two bytes PAST the block, where the
    image holds a `$C9 RET` and the first byte of `LD IY,$FD00`.  MEASURED: the landing then
    writes `$36`/`$A1` over them.  **The original corrupts its own code.**
- CORRECTION: the earlier "set bubble bit 3 -> `$B6D8` -> `$5CE0`" is a burst VISUAL EFFECT, NOT
  the enemy death; the real death->corpse is triggered by the player-contact pop.

- **THE `$5CE0` BURST-SPARKLE ENGINE (`$C002`)** -- MEASURED AND GATED 2026-09-17, M7.7-I10.
  This one entry REPLACES the three overlapping accounts SPEC used to carry (a "fruit table"
  with a `X<<3` encoding, the retraction that left its role "unconfirmed", and the elemental-
  effect reading).  It is a fourteen-slot PARTICLE engine and nothing to do with collectibles.
  - `$C002` is the ONLY entry point; `$C006` has no reference anywhere in 64K, and the sole
    caller is `$8D49`.  Table `$5CE0..$5CFB`, 14 x 2 bytes.
  - **byte0 = (X & `$F8`) | phase(0..7) -- MASKED, not shifted.**  byte1 = RAW Y, masked to
    `& $F8` at use.  FREE means **`(byte0 & 7) == 0`, NOT `byte0 == 0`**: an expired particle
    KEEPS ITS X BITS, and the next burst reuses that very slot.  Gated by living a particle out
    and seeding again, because on a cleared table the two rules agree everywhere.
  - IY is pinned to `$C05E`, another ten-byte FAKE ENTITY RECORD (+0/+1 sprite, +5 X, +6 Y) --
    the same shape as the collectible's `$8903`.  `$A2D5` and `$A314` read their subject THROUGH
    IY, which is how one pair of blitters serves seven subsystems.  `$C002` calls `$A2D5`
    DIRECTLY, so it **ORs**; only the item path goes via `$A2C2`, which NOPs the two `OR (HL)`.
  - New phase 0 or 2 -> ERASE (`$A314`); 3..7 -> OR-draw `$CA80`.  Phase 0 also FREES.  **Phase 2
    does NOT expire** -- `$C055` rejoins at `$C047` and the slot is written back live.  Erase and
    draw each write **32 bytes**, so a write COUNT cannot tell them apart.
  - **Lifetime = exactly SEVEN passes** from the phase the pop seeds: erase, five draws,
    erase-and-free.  Phases 3..7 OR the SAME sprite into the SAME cells with no erase between, so
    the finished screen cannot count the draws -- the gate captures after every single pass.
  - **`$CAA0` AND THE `JR c` AT `$C03B` ARE DEAD BY CONSTRUCTION.**  ph = ((old & 7) + 1) & 7 and
    the free test has already rejected old & 7 == 0, so old & 7 is 1..7 and ph is one of
    {2,3,4,5,6,7,0} -- **never 1**; the carry needs ph < 2 and ph == 0 has already branched away.
    This upgrades the old "never observed" to SETTLED-DEAD.  A gate written to watch `$CAA0`
    drawn could only ever fail, so the negative is asserted instead.
  - **THE WALK IS NOT A CLEAN FOURTEEN ITERATIONS.**  `$C016`'s `LDI` decrements the SIXTEEN-bit
    BC, and C is a live register: entering with C == 0 borrows and costs B a count, so **slot 13
    is never serviced**.  MEASURED at the call site `$8D49`: C is 3 in `round1`, 1 in
    `candycane`/`crown`/`hurryup` and **ZERO in `fruit` and `boss`** -- ordinary play, not a
    curiosity.  C is whatever `$8D46`'s `CALL $A824` left, so its provenance is OPEN until
    `$A824` is transliterated.
  - Push it further and it RUNS AWAY: `$C023 LD C,A` sets C to the serviced slot's X & `$F8`, so
    when every serviced particle has X < 8 each LDI after the first sees C == 0, B passes zero and
    WRAPS, and the walk leaves the table.  MEASURED: 4,563 bytes written as far as `$5FFE`,
    straight through the `$5D00` item sprite bank.  Reachability in play is UNKNOWN (it needs a
    bubble popping at X < 8); it is reproduced because the walk is transliterated as a `DJNZ` over
    an eight-bit B rather than a for-loop.
  - **`$5CFC..$5CFF` = `00 FC 3F C0` is REAL AND READ.**  The runaway finds `$5CFE` = `$3F`, a
    non-zero phase, and services a particle there.  Those four bytes are runtime-built exactly
    like the `$5D00` bank (the tape image is zero across the whole span; in `boot`/`title` the
    region still holds the loader's own BASIC text -- `" v.9/87"` sits at `$5CE0` -- and in
    `iball` it holds credits text), and the round clears do not reach them: `$989C` fills 24
    bytes and `$BF53` 28, i.e. `$5CE0..$5CFB` only, both via the byte-fill `$AA49`, NOT an LDIR.
  - **THE SEED `$B6FC`**, inside the pop `$B6D8`: scan for `(byte0 & 7) == 0`; if the table is
    FULL the `DJNZ` falls through and `DEC DE` twice backs onto **slot 13**, which is overwritten
    rather than the burst being dropped.  byte0 := (X & `$F8`) | 1, byte1 := RAW Y, then
    CANCELLED unless `$10 <= Y < $AF` -- and the cancel writes a **bare `$00`**, not (X & `$F8`),
    so it is the one place a slot loses its X bits while byte1 keeps the rejected Y.


## Player: riding/bouncing on bubbles (M5, VERIFIED live)

Per the player, and confirmed in the harness: **the player can bounce off the TOP of a bubble if
JUMP is held on landing** -- the bubble-platforming used to climb the level.

- Staged: an empty floating bubble at (72,168); the player dropped onto its top with jump (`0`)
  held. Result: the player BOUNCED UP (Y 150 -> 113, rising) and the **bubble was NOT popped**
  (stayed active) -- it acts as a springboard/platform, not a target.
- The bounce is a RE-TRIGGERED JUMP: on contact the player's air fields set `(+8)=$22` (the jump
  velocity, identical to a normal jump) and `(+9)` runs up the jump-arc phase (1,2,3,... each
  frame). So "land on bubble top + jump held" simply re-arms the jump.
- **Player-vs-bubble CONTACT RULE -- MEASURED 2026-09-09 (code `$B8E5`-`$B9E6` + a poke sweep on
  `round1_48`; the "spikes on the back" behaviour).** Run per RISEN bubble only (`+7` bit 2 set --
  a travelling bubble passes through the player) for P1 then P2 (`$B901`, the player id parked in
  the burst routine's operand `$B9BC`), skipped while the player is dying (`$FDDA` bit 2):
  1. Contact box (`$B9D4`/`$B9DE`): bubble Y in `(pY-16, pY+8]` and bubble X in `(pX-16, pX+15]`
     (the bubble's top no lower than 8 px below the player's top; any horizontal overlap).
     Sweep: dy -14..+8 pops, -16 and +10 do not; a bubble arriving from above onto the head
     is inside this box, one directly below the feet is not.
  2. **Facing RIGHT** (`+7` bit 0 = 1): POP if bubble X <= pX+13; the FRONT-EDGE band
     X in {pX+14, pX+15} does not pop. **Facing LEFT**: POP if bubble X >= pX-10; the band
     X in [pX-15, pX-11] does not pop. Sweep (dy=0): R pops dx -14..+12, not +14; L pops dx
     -10..+14, not -12. So from the BACK the first pixel of overlap bursts the bubble (the spikes);
     from the FRONT there is a 2-px (right) / 5-px (left) band that does not.
  3. In that band, if the player is pressing TOWARD the bubble (`$FD88` bit 2 right / bit 3 left,
     tested `$B945`-`$B94D` with `B+2`), the bubble is PUSHED: erased (`$BF0A`), X += 2 x
     `$B8DB[B]` (B=2 -> +2 px, B=6 -> -2 px), clamped to 17..224 (`$B977`). MEASURED: walking into a
     bubble that starts 16-17 px ahead nudges it along at walk speed indefinitely (it stays 14-15 px
     ahead); one that starts 15 px ahead enters the pop window on the first step and bursts.
     Not pressing = nothing happens (the bubble rests against the player's front).
  4. The BURST (`$B9B6`): `+7 := (+7 & $EF) | player<<4`, `SET 3` (burst) and `SET 1` (popped-by-
     player = the elemental emit flag), `+4 := 20` (burst animation); if the bubble was somehow
     still travelling, `+3 := 2 / SET 2`. Observed `+7`: `$85 -> $8F -> $8F -> $C0` (erase) -> gone,
     +1 score for an empty bubble, a held enemy -> corpse.
  Bouncing (top + jump held, above) is the separate outcome; this rule is what "touching from the
  side" actually means. (One static-sweep row, dy=-4, did not pop within 12 frames -- the 1-px bob,
  not chased.)
- The player's JUMP model (useful for M7): `(+8)` = jump velocity/timer (`$22` at launch), `(+9)` =
  the ascent phase index (an arc, like the enemy ballistic `$B0F7`). To pin: the exact bubble-top
  detection (feet-vs-bubble-Y test) and the jump-arc table, in the player-physics pass.

## EXTEND letters (M5, mechanic recorded -- to pin via a snapshot)

Per the player (to be reverse-engineered/verified): the classic BB EXTEND bonus.

- Special **letter bubbles** float in containing the letters **E, X, T, E, N, D** (6). Popping one
  adds its letter to that player's WALL, drawn VERTICALLY: **left wall = P1, right wall = P2**.
- The mask is per-letter: a letter already held is DISCOUNTED (popping a duplicate does nothing).
- The collected letters PERSIST ACROSS LEVELS (carried with the player, not reset per round).
- Collecting all six -> (MEASURED 2026-09-09: the centre message is actually **"N I C E   1P"** /
  **"2P"** for the completing player -- double-height, flashing bright-white-on-blue, rows 11-12 --
  NOT the word EXTEND; and the platforms are wiped while ~160 food icons fill the screen; see the
  COMPLETION bullet in the next section) the player gets an **EXTRA LIFE**,
  the level **CLEARS**, and both players advance to the next level.
- WHAT THE PORT NEEDS (unknown, to find): (1) the per-player EXTEND **bitmask** variable (6 bits;
  persistent -- likely near the per-player score `$FFE4`/lives); (2) the letter-bubble TYPE and how a
  pop sets a bit (with the "already held -> discount" rule); (3) the wall letter-glyph display
  (drawn into the left/right border columns); (4) the "mask complete -> extra life + level clear"
  check.
- FAST PATH TO PIN IT (proven method): a snapshot with a **letter bubble present** (or a
  before/after around popping one) -> the controlled diff reveals the per-player mask + the
  letter-bubble type + the wall write. A state with a FEW letters already collected exposes the
  persistent mask directly.

## EXTEND letters: mask CONFIRMED ($FDE3/$FDED) (M5, via the EXTEND_D snapshot)

Snapshot: round 4, P1 has 'T' in the left wall, a letter-'D' bubble above the player. Collecting D
in a controlled diff pinned it (correcting my read -- round 4's platforms are bubble-LIKE TILES,
not bubbles; the D bubble was the only real bubble on screen; letter bubbles follow a set path from
the top to a resting place):

- **P1 EXTEND mask = `$FDE3`** (= slot 9 `$FDDA` +9); **P2 = `$FDED`** (slot 10 +9) -- i.e. the mask
  lives in the persistent per-player struct (so it CARRIES ACROSS LEVELS, as described).
- **6 bits = the E,X,T,E,N,D positions (bits 0-5)**. VERIFIED: idle mask `$04` = bit 2 = **T**
  (matches the 'T' in the wall); collecting **D** -> `$24` = bits 2+5, so **D = bit 5**. (E=0, X=1,
  T=2, E=3, N=4, D=5 -- the two E's are distinct bits, one per position.)
- **Wall display**: collecting a letter writes its glyph into the shadow bitmap at the wall column
  (the diff showed a vertical 'D' glyph appear at `$F020,$F120,...,$F720` -- one column, 8 rows).
  Left wall = P1, right wall = P2.
- **Completion**: all six bits set (`$3F`) -> EXTEND (word shown centre, EXTRA LIFE, level clears,
  advance). The check is ON-COLLECT (fires when a letter is added and the mask reaches `$3F`) --
  poking `$FDE3=$3F` alone does NOT trigger it. (Full extra-life/clear not yet cleanly captured --
  a real 6th-letter collect is needed.)
- **The mask PERSISTS ACROSS DEATHS as well as levels** (per the player): dying does NOT wipe the
  wall letters. (My earlier note that a "teleport-collect reset the mask" was a corrupted-player
  artifact -- an invalid poked state, NOT a genuine death -- so it does NOT indicate death behaviour.
  Retract the "letters lost on death" guess.)
- **Letter-collect routine = `$B7E5`** (RESOLVED 2026-09-08, N17): reached from bubble-pop `$B6D8`
  via `$B75C` (`CP 5` / `CALL nc`) when the popped kind >= 5 (kinds 5-10 = E,X,T,E,N,D); `SUB 5`
  -> idx; bit from the 8-entry table `$B80E` (`01 02 04 08 10 20 01 20`: kinds 5-10 = E,X,T,E,N,D; the duplicate-art kinds 11/12 = E/D again -> bit0/bit5 -- MEASURED: a kind-11 bubble completed the missing first-E bit); mask address = `$FDE3 + owner*10`
  (P1 `$FDE3` / P2 `$FDED`); `OR C` sets the bit (a duplicate is idempotent -- that IS the
  "discount"); sets `$FED5 = 1`; +10 internal (100 on screen) at the pop via `$B6D8 -> $80FA` (MEASURED at the completing pop; the earlier "+1000" was the `$FFE4` byte-boundary misread). The wall glyph is drawn
  per-frame by the display routine `$957E` from the glyph table `$95D5`.
- **COMPLETION -- MEASURED 2026-09-09 (`EXTEND_complete.szx`, round 9: player falling onto the final
  'E' bubble, mask `$3E` = only the first E missing).** The pop sets the bit via `$B7E5` and
  `$FED5 := 1`; the main loop's `$948F` sees `$FED5`, clears it, and runs **`$94C2`** for P1
  (`IX=$FD80`) then P2 (`IX=$FD8A`): `LD A,(IX+$63) / SUB $3F / RET nz` (a SUB -- there is no
  `CP $3F` in the image). On completion: **the mask is RESET to 0** (`$94C8`; MEASURED
  `$3E->(3F)->$00` at f5 -- the wall letters vanish and must be re-collected), hurry state
  `$FEC4/$FEC5` cleared, sound hook `$8E0A` (A=2), **item collection DISABLED** (`$87B2` patched
  to `RET`), the completing player's digit (`'1' + bit0` of `+$5A`) written into the message at
  **`$9AB3`**, the ENTIRE shadow `$E000-$FAFF` zeroed and the platform tile `$856C` cleared (the
  level's platforms are literally wiped), then **`$9500`**: `$8C14` deactivates all 7 enemy and 12
  bubble slots and restores the now-blank background + attrs (enemies simply REMOVED -- no corpses,
  no score; MEASURED f7); the screen fills with food -- `$9506-$9535`: 10 rows x 16 random items
  (types 0-3, X every 16 px, Y=176 down to 32, each row drawn via `$8689`; the `$9605` table keeps
  only the last row, so the ~160 icons are decoration, not collectables) (f10-12); lives icons
  redrawn; sound; the MESSAGE: `$9AA9` = `"N I C E      P"` printed by `$801D` -- which swaps the
  glyph copier to the **double-height** renderer `$8058` -- at `$4869` = **rows 11-12, cols 9-22**,
  attrs **`$CF` = bright white on blue, FLASH**, on both rows: on screen **"N I C E   1P"** (or 2P)
  (f18); delay `$9573`; **+1 LIFE** (`$9558`; MEASURED f139, 2->3) + icon redraw; delay; then the
  normal round advance (**f252, round 9->10**; the message stays until the transition repaint at
  f262). Timings from the completing pop: enemies gone +2, wipe +3, items +5..+7, message +13,
  extra life +134, advance +247. (Death does NOT clear the mask -- confirmed by the player.)

## EXTEND: "already-held -> discount" rule CONFIRMED (EXTEND_2nd_N snapshot)

Snapshot: P1 mask `$34` (T,N,D held), a 2nd 'N' bubble above the player. Popped it with a jump:

- **The mask `$FDE3` stayed `$34`** -- N (bit 4) was already set, so the duplicate did NOT change
  the mask and NO new wall glyph was drawn. The "already-held -> discount" rule is VERIFIED.
- **BUT points are still awarded**: score `045300 -> 046300` (read in the old, wrong `$FFE4` byte layout) = really **+10 internal = 100 on screen** for popping the letter -- the "+1000" was the byte-boundary misread, MEASURED correctly at the `EXTEND_complete` pop --
  bubble, even though it's a duplicate.
- So the letter-collect logic is: pop a letter bubble -> always +10 internal (100 on screen); if the letter's bit is NOT
  yet set, ALSO set it (bit = the letter's E,X,T,E,N,D position, 0-5) and draw its wall glyph;
  if already set, just the points (discounted for EXTEND).
- (Controls in this state: keyboard O=left / P=right / **Q=jump**.)

This completes the EXTEND mechanic: mask `$FDE3` (P1) / `$FDED` (P2), 6 position-bits; new letter =
set bit + wall glyph + 10 internal (100 on screen); duplicate = that +10 pop score only; all six (`$3F`) -> the completion sequence ("N I C E   nP" message, wipe, +1 life, advance -- MEASURED, see the COMPLETION bullet)
(checked on-collect). Open only: the completion code (extra life + clear). Death does NOT clear the mask (per the player).

## FIRE elemental -- floor-flame KILL MEASURED LIVE 2026-09-09 (`fire_kill.szx`)

The owner's `fire_kill.szx` (round 25, `$7E0E`=4, the player standing in the spread floor flames
with an enemy walking in on the bottom platform) pins the fire kill and unifies it with the other
elementals:

- **The flame is bright RED `$42`** (bright, paper 0, ink 2) painted on the FLOOR SURFACE row --
  here row 22 (Y 176-183), the row below the platform top the sprites stand on. Live extent = **9
  contiguous red cells** (row 22 cols 15-23), which is the `$9FC8` 9-flame cap CONFIRMED live; the
  fire object `$FDEE` carried `+4 = 9` (flame count) and `$FDF2 = $09` / `$FDF4 = $B0` (=176, the
  flame Y). The platform's own rows 20-21 stay green `$44` -- the flame colours only the floor.
- **The kill is the SHARED attribute probe** `$9377` -> `$93C4` -> `$8BC2` (return `$93D3`), the
  SAME routine water, the red cross and the yellow-cross storm use -- fire takes the RED
  `(attr & $47) == $42` branch, identical to a red-cross fireball. MEASURED: the enemy walking
  along the bottom platform (Y 164->168, `+7` E7) turned to a corpse at f15 (`+9 = $FF`, `$8BD3`
  wrote it) the frame its lower probe cell (the `$93A7` +$21-attr-cell offset = one row down) entered
  a red flame column; its own/upper cells were still green `$44`. Corpse flew (`+7` $AD) and settled
  to a `$9605` collectible (`+7` $3F) at f125. So FIRE = red floor flames = the red-attribute kill,
  one pipeline with everything else (water = cyan `$28`, fire/red-cross/storm = red `$42`).
- Spread CADENCE (column growth over time) is still not frame-sampled -- this capture is already
  fully spread -- but the extent cap (9), the colour, the row and the kill are now live-confirmed.

## Special elemental bubbles: WATER and FIRE (M5, mechanic recorded -- to pin via snapshots)

Per the player, THREE more bubble types exist beyond normal/enemy/letter bubbles -- the arcade's
elemental attack bubbles WATER / FIRE / LIGHTNING:

- **WATER bubble**: when popped it drops WATER that flows and **carries the player along** (a
  current that sweeps the player -- and presumably enemies -- down/across the platforms). Likely
  shares code with the blue-cross water fill and the special-effect engine `$A824`/`$A84D`, but as
  a localised flowing stream rather than a full-level rise.
- **FIRE bubble**: when it lands on the ground it creates **FLAMES on the floor** (that burn/kill
  enemies who touch them). Again likely via the `$A824` special-effect engine, with a flame sprite
  laid along the platform.
- **LIGHTNING bubble**: when popped it releases a **LIGHTNING BOLT that shoots horizontally** across
  the playfield (in the facing/fired direction), killing enemies in its path -- a fast straight
  beam (vs fire's floor flames and water's flowing current). Likely the same `$A824`/`$A84D` engine.
  So the elemental attack-bubble trio is WATER / FIRE / LIGHTNING, as in the arcade.
- WHAT THE PORT NEEDS (to find): each bubble's TYPE/flag (in the `$FED8` pool or as a special
  item), the pop/land trigger, the effect update (water current vector + player-carry physics; fire
  flame placement/spread + lifetime), and the enemy-kill (-> the corpse -> `$9605` fruit pipeline).
- FAST PATH: a MID-EFFECT snapshot of each (water actively flowing with the player being carried;
  fire flames burning on a platform), plus optionally a "bubble about to pop" before-shot. As with
  the blue-cross water, catching the effect IN PROGRESS reveals its state variables directly (a
  static "before" is not enough for an animated effect).

### Measured scaffolding (static, from code, 2026-09-08) -- element mapping still needs snapshots

RETRACTION: `$A824`/`$A84D` are NOT the special-effect engine (they are HUD/text blitters called
every frame from the main loop `$8D46`/`$8F26`); the "likely `$A824`" guesses above are withdrawn.

What IS measured -- the bit-3 bubble-pop -> effect-object pipeline (the elementals' strongest
candidate; NOT yet proven to be them vs a generic burst effect):
- Bubble TYPE lives in the `$FED8` pool entry `+7` flags. Manager `$B636` dispatches: bit7 = active;
  bit2 clear -> empty travelling bubble (`$BDFE`); **bit3 set -> pop-spawn path `$B6C3` -> `$B6D8`**.
  `SET 3,(IY+7)` at `$BE95`/`$BEDC` (capture region) marks a bubble for it.
- `$B6D8` (a bit-3 bubble popping): deactivates the bubble (RES 7/3/2 of `+7`) and writes an effect
  object into a **14-entry table at `$5CE0`** (2 bytes/entry: byte0 = (X&F8)|type3, byte1 = Y) at
  the bubble's position. (This `$5CE0` table is distinct from the `$9605` fruit table.)
- Effect engine ~~`$C006`~~ **`$C002`** walks `$5CE0` (14 entries).  CORRECTED by M7.7-I10: the
  low 3 bits are a PHASE, not a type -- phase 2 does NOT expire, only 0 does -- and `$CAA0` is
  never drawn at all.  See the single entry below.
- Pipeline: elemental bubble (bit3) -> pop `$B6D8` -> object in `$5CE0` -> engine `$C006`
  animates/draws it. WHICH low-3-bit type = water vs fire vs lightning, the current/flame/bolt
  physics, and the enemy-kill are exactly what a mid-effect snapshot of each must reveal.

### WATER elemental — FLOW ALGORITHM (deep multi-agent RE, harness-verified 2026-09-08)

*Reverse-engineered by a 13-agent workflow (analyze -> adversarial code+runtime verify -> synthesize) and then
INDEPENDENTLY RE-VERIFIED in the main session. My spot-checks: the carry snap `decode(word@$A25F) == player X,Y`
held on **34/36** active frames (the 2 misses are the 1-cell snap-in transient); activation is DETERMINISTIC
(propagation `$A15A`=1 at **f111**, capture `$FDDA` bit4 at **f114**, ≈2.2 s from t0 -- my earlier notes' f140/f206
were mislabeled loop counters, now corrected); the active band is **8 cells** (`$A25D..$A26B`, LDDR shifts 14 B
to `$A26C`); measured head path **LEFT -> DOWN -> RIGHT** exactly tracks the shadow platform geometry and the
player's sweep. NOTE: this SUPERSEDES the earlier "screen-space self-modifying" framing -- the FLOW is the
`$A25D` attribute-address queue; the self-modifying `$A5A2-$A5D1` blitter churn is the one-shot POP SPLASH, not
the flow (both verifiers independently confirmed the `$A5xx` shifted path fires 0x during pure flow).*

*Reverse-engineered from Bubble Bobble (Firebird 1987) Z80 machine code, verified against the SkoolKit harness on the `elwater` snapshot (`build/elwater.pkl`). Frames are 50 Hz from snapshot t0. Every address is a measured entry point unless marked INFERRED/OPEN. "Shadow" = display address + `$A000` (attributes: `$5800`+`$A000` = `$F800`; bit5/`$20` set = platform/wall).*

---

### (a) Water-bubble identity & burst trigger

The descending "water bubble" is an **ordinary bubble** in the `$FED8` pool (slot 5 = `$FF0A` in this capture). It carries **no static water flag** — at rest and all through its fall `+7 = $84` (bit7 active, bit2 set, bit3/bit1 clear), identical to every other pool bubble. The water-ness is produced **at the pop**, not stored on the bubble (`$B9B6`; proven generic — an ordinary bubble forced onto the player also stamps `$8E` at `$B9C1`).

- **Spawn** — ceiling emitter `$7EA0` spawns it (~f74) from the 4-byte/entry drop table `$7F0B` (`[ptr_lo,ptr_hi,X,Y]`, gap tested by `BIT 5,(HL)`): writes `+5=$50`(X), `+6=$BF`→snaps to `$01`(Y), `+9=2`, `+3=2`, `+7=$84` (`$7EF0/$7EF5/$7EF8/$7F00`). No water field.
- **Fall** — generic bubble mover `$B836` (Y `$01`→`$12`, X fixed `$50`), steered by the shadow cell it reads.
- **Overlap** — every frame `$B836` (at `$B850`) calls the player-overlap test `$B8E5` → `$B901` (vertical box `$B9D4`, horizontal box `$B9DE` with a facing-bit refinement `$B920`, D=`$0F`/`$0D`). The mask operand at `$B9BC` is self-modded per player (`0` P0 / `$10` P1).
- **Burst stamp** `$B9B6` (reached only via `JP c` at `$B92F`/`$B940`):
  ```
  B9B6 LD A,(IY+7) / AND $EF / OR $10(self-mod) / SET 3 / SET 1 / LD (IY+7),A  ; +7 = $8E   [MEASURED f109, PC $B9C1]
  B9C4 LD (IY+4),$14                                                          ; anim
  ```
  bit3 = pop-me, bit1 = produce-flow, bit4 = which player. **The trigger is generic** (not water-specific).
- **Pop + water seed** (next frame, f111) — manager `$B636` sees bit3 → `$B6C3`→`$B6D8`:
  - `$BF0A` stamps a one-shot splash (self-mods `$A480`/`$A5D9`, CALLs master draw `$A447`) — source of the `$A5A2–$A5D1` blitter-mask churn; **that shifted-blitter mask path is unrelated to the flow** (see (d)).
  - `$5CE0` entry0 seeded `[(X&$F8)|1, Y]` = `[$51,$12]` at `$B713`/`$B718`; effect engine `$C006` bumps its low-3-bit counter at **`$C02E`** (`$54`, then wraps) — a splash particle, distinct from the flow.
  - bit1 routes into the **water-seed branch `$B73D`**, seeding the flow globals (see (b)).

**Corrections applied:** `$FFF9` is *not* a constant — the operand byte at `$B742` (static image = `03`, i.e. the instruction reads `LD A,3` cold, not `LD A,1`) is self-modified by `$B6F5` (source `$B6F2 LD A,(IY+9)`), so `$FFF9` = popped bubble's `+9` state (`=$02` here), and it is a **transient** trigger (cleared to 0 every frame by the loop at `$93F5`), **not** a persistent "water on" flag. `$FFFA` = triggering-player index (P0=1 / P1=2), derived at `$B725–$B735` (from `+7` bit4), measured write `$B74C=$01`. `$5CE0` increment PC is `$C02E`, not `$C04C`. (M7.7-I10: both are real and they are different
writes -- `$C02E` updates the COPY at `$C048`, which is the operand of `$C047 LD A,n`, and `$C04C`
is what puts it back in the table through the operand at `$C04A`.)

---

### (b) Flow-state data structures

| Addr | Stride/size | Role |
|---|---|---|
| `$A25D` | 8 entries × 2 bytes LE (`$A25D..$A26B`) | **The water store.** Each entry = a display **attribute** address (`$58xx`–`$5Axx`). `$A25D` = head (newest); `$A25F` (entry 1) = the cell the player is snapped to. Advanced by LDDR shift + new head in `$A1C6`. Init-filled by `$A180`; each active tick the LDDR at `$A1D2` (BC=14) rolls the 8-word band up to `$A26C` and a new head is written at `$A25D`; the 9th word `$A26D` stays the untouched seed. Active band MEASURED = 8 cells. |
| `$A15A` | 1 byte (immediate operand of `LD A,n` at `$A159`) | Flow-active gate. Set once at seed (`$A166`), **reinforced each propagate** (`$A19B`), held 1 until in-code deactivation at `$A205`. **No per-frame main-loop reset** (`$9460` uses it to prevent re-seed). |
| `$A1AA` | 1 byte (operand of `LD C,n` at `$A1A9`) | Horizontal-direction toggle, seeded from `LD A,R` at `$A15F`. bit0: 0=LEFT(`$FFFF`), 1=RIGHT(`+1`). Flips **only on a blocked horizontal step** at `$A1B5` (see (c)). |
| `$A259`/`$A25A` | 2 bytes | Carry scratch: computed player X (`$A259`) / Y (`$A25A`), committed to the player at `$A252`/`$A257`. |
| `$7E0E` | 1 byte | Elemental TYPE. `==2` ⇒ WATER (`$9E78 SUB 2 / JP z,$A159`). 3,4 = other elementals; round-`$50` special case at `$9E71`. |
| `$9E5D` | 1 byte (operand at `$9E5C`) | 2-frame parity toggle: `XOR 1` each frame, `RET z` skips the whole effect tick on the off phase. |
| `$8DBD` | 1 byte | Global frame counter. Read by `$9E53` (end check `CP $E1`) and copied to vestigial self-mod `$A194` by `$A190`. |
| `$FFF7`/`$FFF8` | 2 bytes | Descending bubble/head X,Y — seeded by the pop (`$B752`/`$B758`), consumed by `$9460`→`$A15F` to build the source attribute address. Observed `[$50,$12]`→`[$3F,$17]`. |
| `$FFF9` | 1 byte | Transient burst trigger = popped bubble `+9` state (see (a)); cleared each frame by `$93F5`. |
| `$FFFA` | 1 byte | Triggering-player index (1/2). |
| `$FFFB` | 1 byte | Seeded `=$01` by `$946D` at the pop frame. Meaning **OPEN** (cross-cutting). |
| `$FDDA` (`$FD80+$5A`) | 1 byte | Player-1 extended state; **bit4 = captured-by-current** (the carry gate). Set by `$936A`, cleared by `$A212`. |
| `$FDE4` (`$FD80+$64`) | 1 byte | Player-2 equivalent; bit4 gates the P2 coord pair. |
| `$FD85`/`$FD86` | 2 bytes | Player-1 authoritative X/Y (what the carry snap overwrites). Backup pair `$FD82`/`$FD83`. |
| `$FD89` (`+9`) | 1 byte | Player "in-water"/descent flag: `$FF` falling with no floor (set `$AD51`), `0` on floor (`$AD4C`). |
| `$9603`/`$9605` | flag + 31×2-byte table | **Separate** render/collision object subsystem (see (d)/(f)). `$9603`=`$80` while live (~f40–f240). Not the `$A25D` flow. |
| `$8903` | 10 bytes | Synthetic draw entity for the water sprite (`+0/1` tile ptr, `+5` X, `+6` Y, `+7=$FF`). |
| `$FD00` | 32×2-byte LE | char-row→display base address table, indexed by `Y>>3`. |
| `$5E60`/`$5D00` | 16×16, 32 bytes, no mask | Static water tiles (splash / ripple). |

---

### (c) Per-frame propagation algorithm

**Dispatch chain (per 50 Hz frame):** `$8D40` main loop → `$9E50` effect update → parity gate `$9E5C` (`$9E5D XOR 1`; `RET z` on the off phase) → dispatch `$9E6E` (`LD A,($8609)` round; `CP $50`; `LD A,($7E0E)`; `SUB 2`; `JP z,$A159`) → tick gate `$A159` (`LD A,($A15A)`; `OR A`; `JR nz,$A190`).
**Init (once):** water-entity handler `$9460` (guarded `LD A,($A15A)/OR A/RET nz` and `LD A,($FECE)/OR A/RET nz`) builds the source attr address from `$FFF7`/`$FFF8` (`$946A–$948B`) → `$948C JP $A15F`.

> Note: `$A190` **is** statically reached — via the *relative* `JR nz,$A190` at `$A15C` (an absolute-address byte search misses it). The exact caller of `$9460` is not pinned (OPEN).

**Cadence/speed (MEASURED):** the tick runs every **other** frame (parity gate). The head advances exactly **one 8×8 attribute cell per active frame** = one cell / 2 frames ≈ **4 px/frame**, one axis at a time.

```
INIT  $A15F (runs once; $A15A guards re-entry):
    $A1AA = R                      ; random horizontal seed        [$A15F LD A,R / $A161]
    $A15A = 1                      ; active                        [$A164/$A166]
    HL = source_attr + $A000       ; shadow                        [$A169/$A16C]
    scan DOWN up to 22 cells (DE=$20), testing AND $20:            [$A16D..$A175]
        stop at first cell WITHOUT the platform bit (JR z at $A175)
    SBC HL,$A000 -> display addr; seed the band at $A25D ($A180); active band grows to 8 cells during propagation

ADVANCE  $A190 (one active frame):
    tmp = mem[$8DBD]               ; stored to self-mod $A194, flags unused (vestigial)  [$A190/$A195]
    $A15A = 1                                                       [$A19B]
    head = word[$A25D]
    if step(head, DOWN=+$20): return         ; DOWN has priority   [$A1A0/$A1A3]
    head = word[$A25D]
    dir = (mem[$A1AA] & 1) ? RIGHT(+1) : LEFT($FFFF)                [$A1AB BIT 0,C]
    if step(head, dir): return               ; success -> RET, $A1AA NOT toggled
    mem[$A1AA] ^= 1                           ; reached ONLY when the horizontal step is BLOCKED  [$A1B5-$A1BA]

step(head, dir):  # $A1C6
    cand = head + dir
    if shadow_attr[cand + $A000] & $20: return BLOCKED   ; RET nz   [$A1CC BIT 5,(HL) / $A1CF]
    POP AF                          ; drop caller return -> only ONE committed step/frame  [$A1D0]
    LDDR shift $A26A->$A26C (BC=14); word[$A25D] = cand ; queue grows a new head  [$A1D2-$A1DE]
    if cand <= $5AFF: attr[cand] = $2D        ; PAINT head CYAN (ink5)             [$A1E6/$A1EB]
    tail = word[$A26B]              ; post-shift oldest-in-band cell
    if tail > $5AFF: goto DEACTIVATE $A205    ; flow ran off the attribute file    [$A1F3-$A1F9]
    attr[tail] = (mem[$8309] & 7) | $40 = $46 ; ERASE trailing cyan -> background  [$A1FB-$A202]
    <fall through to player-carry $A21F>       ; carry runs iff a step succeeded

DEACTIVATE  $A205:
    $A15A = 0 ; $A259 = $A25A = 0
    RES 4,(IX+$5A)=$FDDA bit4 ; RES 4,(IX+$64)=$FDE4 bit4   ; drop both carry gates  [$A212/$A216]
```

**Direction/geometry rule (CORRECTED):** DOWN always has priority and never touches `$A1AA`. The horizontal direction is **held** across every successful step (and every DOWN step) and **reverses only when it is blocked** ("bounce off a wall"), *not* per-frame alternation. Passability is read-only from the shadow attribute buffer: open = `$40`, platform = `$20`/`$60` (bit5). **MEASURED** head path on this green-platform round: DOWN×2, LEFT×4, DOWN×4, blocked 1, then RIGHT — exactly tracking the platform geometry and matching the player sweep; `$A1AA` held `$50` through the LEFT run, `$51` through the RIGHT run, flipping only on the stuck frames (f132/f176/f220). Fixed-length band: each step paints one new cyan head and erases the post-shift oldest cell, so the visible current is a ~7-cell moving band. Termination is the in-code `$A205` (tail past `$5AFF`); the `$9603` subsystem's `$80`→`$00` at ~f250 is the separate object system finishing.

---

### (d) Rendering (blitter + water tile + cell→screen mapping)

The current is drawn by a **separate object subsystem**, distinct from the `$A25D` cellular flow. Driver `$8669` is called from the main chain at `$8D4C` (**4× per 69888-t frame** in this state — cadence is a main-loop concern, OPEN):

```
$8669: CALL $89CB (flow/spawn) ; early-outs on player bit4 / $8DB6==$E1 (else INC $86CD)
$8689: mem[$872C]=0 ; IY=$8903 (draw entity) ; HL=$9605 (31-entry cell table)
       for B in 31..1: if mem[HL]!=0 CALL $86A9 ; HL+=2
       INC mem[$872C] ; if mem[$9603]==0 RET
$86A9->$86B1 per cell: CALL $8779 (cell->addr/state) ; IX=$FD8A CALL $87B2 (RET z guard);
       IX=$FD80 CALL $87B2 (RET z guard) ; advance anim counter (mem[HL]&7)+1;
       gated by frame counter $86CC/$86D1 and $FED1 guard $86D3:
         if counter==4: erase 2x2 (JP $A314) ; else draw
```

**Draw mode (CORRECTED — always OPAQUE):** every draw exit of `$86B1` is `JP $A2C2`; there is **no reachable OR-draw path** for this water. Dispatch is `$871A LD A,($FECE)/OR A/JP nz,$A2C2`, `$8721 LD A,($FECF)/OR A/JP nz,$A2C2`, else `$8728–$8762` (shadow-mark, then `JP $A2C2`). `$FECE`/`$FECF` gate the shadow-marking step, **not** the blit mode (measured `$FECE=$FECF=0` at f200 yet 7 opaque draws). The shadow-mark `$8765` (`LD A,(HL)/AND $38/OR 3/LD (HL),A`) runs 4× per drawn cell, stamping a 2×2 collision marker into the shadow buffer (`$E000` region, `H-=$A0`).

**Core blit `$A2D5`** (16×16, char-aligned, self-modifying):
```
A2D5 A=(IY+6) Y ; CALL $9F5C (>>3) ; ADD A,A ; IX=$FD00+2*row
A2E5 DE=(IY+0/1) tile ptr
A2EB A=(IY+5) X ; CALL $9F5C (>>3) ; LD ($A304),A   ; self-mod the col offset in $A303
A2FB inner half (B=8):  A=(DE)|(HL);(HL)=A [PC $A308] ; L++ DE++ ;
                        A=(DE)|(HL);(HL)=A [PC $A30D] ; DE++ L-- H++ (INC H = down 1 pixel line)
     ; run twice (two 8-row halves) = 16 px tall
```
`$A2C2` NOP-patches the two `OR (HL)` opcodes (`$B6`→`$00`) at `$A307`/`$A30C` so the store is a plain overwrite, then restores them. `$9F5C` = `RRA`×3 `AND $1F` = `n>>3`. Cell→screen: `$FD00[2*(Y>>3)]` gives the row base; the column is added via the self-modded offset at `$A304`. Tiles `$5E60` (splash) / `$5D00` (ripple) are static (0 writes/frame). **MEASURED f200:** 7 draws, all IY=`$8903`, cells `[$71,$AB]`/`[$00,$22]`; write PCs `$A308`/`$A30D` (112+112 writes). Stubbing `$A2D5=$C9` collapses water pixel writes — proves it is the water writer.

**Erase `$A314`/`$A34D`:** same `$FD00` row table; copies the platform shadow (`H = disp_hi + $A0` = `$E000`) back into the display over the 16×16 cell (col self-modified at `$A355`).

**Not water:** the self-modifying shifted-sprite blitter `$A447`→`$A53C` (masks from `$AA4F`, patched into `$A5A2–$A5D1`, inner `$A5A0` = `(DE&$FC)|(HL&3)`) is the **generic** X-shifted path (`X&6 != 0`); it fires 0× during pure flow — the `$A5A2–$A5D1` churn seen at the burst is an unrelated shifted sprite, not the water. Player/enemy sprites use yet another blitter (`$BAxx`–`$BDxx`).

---

### (e) Player-carry physics

The player is **not** pushed by a velocity vector and does **not** read a water field at its own cell. Once captured, its authoritative position is **slaved each active tick to the flow's trailing cell** (`$A25F`, entry 1 — one cell behind the front), as a **fall-through tail** of `$A1C6` (so the carry runs only on frames where a step committed):

```
$A21F: HL = word[$A25F]                    ; trailing water-head attribute address
       H = (H - $58) & 3
       X = (L & $1F) * 8            (ADD A,A x3)     -> $A259     ; 8*column
       Y = (((addr-$5800) >> 2) & $F8) - 8           -> $A25A     ; 8*row - 8
$A23F: HL=$FDDA ; CALL $A248
$A245: HL=$FDE4 ; (fall-through)
$A248: BIT 4,(HL) ; RET z                   ; <-- CAPTURE GATE
       HL += $FFAC (-$54)                   ; flag addr -> player Y
       (HL)   = mem[$A25A]  (player Y)      [$A252]
       (HL-1) = mem[$A259]  (player X)      [$A257]
```

- **Carry gate = bit4** of `$FDDA` (P1) / `$FDE4` (P2). **Set** by attach detector `$9339`/`$936A` (`SET 4,(IX+$5A)`), re-evaluated every frame (`IX=$FD80` then `$FD8A`; guards: active, an attribute-cell probe `$9377` compared `==$28` at `$9349`, `$FECE==0`, not bit1 of `+8`). **Cleared** by the flow-termination path `$A212`/`$A216` (not by init). *Corrected:* `$FD85`/`$FD86` are gated by **`$FDDA` bit4** (P1); `$FDE4` bit4 gates the second pair `$FD8F`/`$FD90` (P2).
- **Commit order:** `$A252`/`$A257` execute **last** each active frame, overriding the normal fall (`$AD11`) / clamp (`$AB0C`) writes. **MEASURED:** the decoded `word[$A25F]` matched `$FD85`/`$FD86` on 241/245 frames; the 4 misses are +2 in Y (the `$AD5A` gravity nudge showing through on a frame where the head row had not yet advanced).
- **In-water flag `$FD89`** (`+9`) is the *descent* flag, not the carry gate: `$AD51` sets `$FF` while no floor is under the sprite (with `$AD5A` gravity `Y+=2`), `$AD4C` clears to 0 on landing. `$AD11` builds the floor probe (`DE=(X,Y+15)`, self-modded at `$AD41`, tested via `$AE81`/`$AE7F`).
- **Speed (MEASURED):** 8 px per active tick along whichever axis the head advanced (one axis at a time, 8-px cell granularity); ticks every other frame ⇒ **≈4 px/frame**. Trajectory matched the flow head exactly (serpentine: right, down with `$FD89=$FF`, left, down, right…).
- **Control override:** while bit4 is set, `$8670` branches past the spawn/level-progress check (`BIT 4,(IX+$5A)/JR nz $8689`; `BIT 4,(IX+$64)/JR nz $8689`). **Mutation test:** NOP the `SET 4` at `$936A` and clear bit4 → the player froze completely — confirming bit4(`$FDDA`) is the carry gate.

---

### (f) Enemy interaction

**The flow DOES kill free enemies -- MEASURED 2026-09-09 by planting (supersedes "none in this capture").**
The enemy pass `$931A` sets the shared probe's kill byte `$93C4` to NOP, walks entity slots 2 ..
`($AA57)-1` (`B = ($AA57) - 2`, `$AA57`=6 on this round), and calls `$9377` per slot: an enemy whose
OWN cell or BELOW-RIGHT cell has paper 5 (`(attr & $38) == $28`, the water tile `$2D`) goes to
`$93C4 -> $8BC2` = corpse. A live copy of an enemy planted on the water band (top row = the band)
inside that slot range died THE FRAME its cell turned cyan (`+7 $E0 -> $8D`, `+9 = $FF`, launched on
the usual corpse arc). Two reasons the original capture and the first plants saw nothing: enemies
held in bubbles carry `+7` bit 3, which the probe skips (`$937A`), and a slot beyond the `$AA57`
bound is never examined. The attach detector `$9339` iterates **only the two player slots** (`$FD80`,
`$FD8A`); the gated carry writer `$A248` targets **only** `$FDDA`/`$FDE4`. Enemies standing squarely in the current's path (slot 4 @ X112,Y96; slot 5 @ X96,Y128) were unchanged in position and state as the front swept over them. (Their `+7` flag toggles `$E8`/`$C8` = bit5 every frame, but that is the universal render clear/restore `$A3C0`/`$A43E`, unrelated to water.) The localised stream is a **player-only carry**; it does not drive the corpse (`$C700`)→`$9605`→diamond kill pipeline. Whether the round-`$50` blue-cross full-level water RISE (`$9E71 CP $50`→`$9E85`) kills enemies is a **different mechanic, not exercised here**.

---

### OPEN ITEMS

1. **Round/geometry ENABLE — RESOLVED 2026-09-08 (R14).** The arming caller is a plain relative
   `JR z,$9460` at `$93EB` inside the elemental dispatcher `$93DC`/`$93E4` (keyed on `$FFF9`=2/3/4,
   invoked from the main loop at `$8D3D`) — NOT a self-modified/indirect vector. It fires ONCE at
   the bubble pop (break at `$9460` first hit frame 110 = the pop). The guarded init `$9460`→`$948C`
   →`$A15F` is reached only via `$948C`; the per-frame water tick `$A159` RETs at `$A15E` until
   armed. (Which ROUND arms it is the `$7E4B` table — see the elemental-round-attached section.)
2. **Main-loop cadence.** Why the update chain (`$8D40`) and `$8669` run 4× per 50 Hz frame (fast-forward artifact? the declared slowdown?) — main-loop/timing facet.
3. **`$FFFB` = copy of the triggering-player index `$FFFA`** (1/2), written `$946D`
   (`LD A,($FFFA)/LD ($FFFB),A`); consumed as an IY base at `$9EF7`. RESOLVED (R14) — NOT the
   constant `$01` (it was 1 only because `$FFFA`=1 in that snapshot).
4. **`$FECE`/`$FECF`-nonzero branch of `$86B1` -- RESOLVED 2026-09-09.** `$FECE` = the blue-cross FLOOD
   (type 7) flag, `$FECF` = the yellow-cross STORM (type 8) tick. With either set the collectible draw
   jumps straight to `$A2C2` and SKIPS the `$8765` attribute stamp, so the item's cells keep the
   effect's colour instead of the item's ink. MEASURED (`$FECF` branch): a type-1 item poke-spawned at
   (120,168) has attrs `$03` (its ink) in a normal round and `$46` (the storm's colour) mid-storm.
   `$FECE` takes the identical jump (`$871A`, code-read).
5. **Natural detach -- MEASURED 2026-09-09 (`elwater`, the bubble popped on the player's head at f110).**
   Carry set at f113 (3 frames after the pop); the player rode the serpentine (rows 32 -> 64 -> 96 ->
   128 -> 168) and bit 4 CLEARED at f258 at (152,170) when the flow head ran off the BOTTOM of the
   playfield; the player then fell through the bottom edge, wrapped to the top and landed at (152,32)
   (f312). `$A15A` (armed) fell to 0 at f272 = flow terminated, 162 frames after the pop. A 1-frame
   re-attach blip at f263-264 (probe under the falling player) then clear again.
6. **Attach geometry -- RESOLVED 2026-09-09 (code + live).** `$9339` calls the SHARED attribute probe
   `$9377` for each player (`$9346`/`$935A`) with the kill branch byte **`$93C4` self-modified to RET**
   (the enemy loop `$931A` sets it to NOP before its own pass and back to `$C9` after, `$931F`/`$9336`),
   so for a player a hit merely returns `A = attr & $38`; `$9349 SUB $28 / JR Z` -> `$9360` (no flood
   `$FECE`, `+8` bit 1 clear) -> `SET 4`. The probe's cells are the entity's OWN cell (row Y>>3, col
   X>>3) and the two cells BELOW (row+1: col and col+1) -- i.e. the water band under the player's
   feet: the carried player rides at Y=64 while the cyan band (`$2D` = paper 5 ink 5) is drawn on row
   9 (Y 72-79). MEASURED: attr under the feet = `$2D` throughout the carry, `$46` (platform colour)
   at the head row.
7. **Two-player carry -- MEASURED 2026-09-09.** P2 joins mid-round with key **'2'** (`+7=$E0` at
   (216,168), `$FDE4=$89`). Placed on the path at (136,64), P2's bit 4 set the frame the head reached
   it (f152) and BOTH players then rode at IDENTICAL coordinates through the whole serpentine,
   detached together at (152,170) and fell/wrapped together. (P2's join spot on round 5 is over a
   floor gap: it fell through and wrapped to the top platform first.)
8. **Enemy kill by the FLOW -- RESOLVED 2026-09-09**, see (f): free enemies inside the `$AA57` slot bound die the frame a water tile reaches their cell; captured ones (`+7` bit 3) are immune.
9. Vestigial `$A194` self-mod (holds last frame's `$8DBD`); no read found.

---

### Confidence per section

- **(a) Identity & burst trigger** — MEASURED (dual-verified code+runtime); `$FFF9`/`$FFFA` semantics corrected and confirmed.
- **(b) Data structures** — MEASURED (addresses/strides/fields dumped and write-watched); `$FFFB` = copy of the triggering-player index `$FFFA` (R14, RESOLVED).
- **(c) Propagation** — MEASURED (queue, LDDR shift, shadow-bit probe, head path, cadence, mutation-tested type/direction gates); hdir "bounce-not-alternate" rule and `$A205` termination corrected; caller of `$9460` init = `JR z,$9460` at `$93EB` (R14, RESOLVED); the per-frame water tick `$A159` RETs at `$A15E` until armed.
- **(d) Rendering** — MEASURED (driver, core blit, write PCs, opaque-always dispatch, `$8765` shadow-mark, `$A5xx`-not-water, tiles static); 4×/frame cadence and `$FECE/$FECF`-nonzero path UNRESOLVED.
- **(e) Player-carry** — MEASURED (decode formula matched every frame, gate mutation-tested, commit ordering, px/frame); attach geometry INFERRED.
- **(f) Enemy interaction** — MEASURED 2026-09-09: the flow kills free enemies via the shared paper-5 probe (planted-enemy test); captured enemies immune; slot bound `$AA57`.

### Elemental type is ROUND-ATTACHED (`$7E4B` table) -- resolves the main OPEN item

USER-CONFIRMED + MEASURED: the elemental is NOT armed by gameplay chance; it is SELECTED PER LEVEL
at round setup. Routine `$7DD6` reads the level counter `$8609`, scans a table at **`$7E4B`**, and
writes the elemental type to **`$7E0E`**: `type = class + 2` -- `0`=none, `2`=WATER, `3`/`4`=the
other two fixed elementals (fire/lightning, order TBD), `>=5`=a RANDOMISED higher elemental (`LD A,R`
at `$7E04`; those levels vary per spawn). The effect dispatch `$9E75` then gates the water tick on
`$7E0E==2`; the `$8609 CP $50` at `$9E71` is ONLY the boss-round (80) special-case, unrelated.

**`$7E4B` scan/decode (MEASURED 2026-09-08, N20):** the table is **4 groups of 1-based
round-numbers, each terminated by a `00` byte**, in the fixed order WATER / LIGHTNING / FIRE /
RANDOMISED. `$7DD6` walks the groups with the class counter `C` (0,1,2,3); a round found in group
`C` gets `type = class + 2`; a round in NO group -> `type = 0` (none). Class 3 (the 4th group) is
the RANDOMISED elemental: `type = ($7E04 = R & 7) + 5` = 5-12, re-rolled per round BUILD (not per bubble). MEASURED 2026-09-09: six builds of round 3 armed `$7E0E` = 9, 7, 7, 6, 10, 9 (rounds 1/2 arm 0, rounds 5/6 arm 2). RESOLVED 2026-09-10 (see the subsection below): types 5-12 are INERT (no effect handler, ROM-font-letter bubble sprite). Original behaviour notes of types 5-12 themselves are still unmeasured.

FULL MAP rounds 1-81 (poke `$8609`=1..81 + `call $7DD6`, **0 mismatches**; byte-exact to `$7E4B`):
- **WATER (2):** 5, 6, 10, 11, 12, 13, 15, 18, 20, 64, 77
- **LIGHTNING (3):** 17, 19, 22, 30, 34, 43, 62, 66, 73, 80
- **FIRE (4):** 25, 26, 28, 29, 33, 37, 38, 39, 47, 67, 68, 70, 78
- **RANDOMISED (class 3 -> type 5-12):** 3, 4, 7, 8, 9, 14, 21, 23, 27, 35, 40, 49, 53, 55, 56
- **NONE (0):** all remaining rounds.

**RANDOMISED / "higher" elementals (types 5-12) = an UNFINISHED / INERT feature -- RESOLVED
2026-09-10.** On a class-3 round the setup rolls `$7E0E = (R & 7) + 5` = 5-12, but the game has
NO working elemental for those values:

- **No effect.** The per-frame effect dispatch `$9E75` (`SUB 2 / JP z WATER / DEC A / JR z LIGHTNING
  / DEC A / JP z FIRE / RET`) implements ONLY 2/3/4; types 5-12 fall straight through to `RET`.
  MEASURED by `h.call($9E75)` for every type 2-12: types 5-12 run 8 fixed steps and touch no
  elemental object. Popping a special bubble on rounds 3/4/7 (armed 5/12/7) produced an inert
  null-sprite object (the `+9=3` marker still routes through the lightning-pop path, but round
  setup `$7DFA` only seeds the bolt sprite `$A37D` for type 3, so `$FDEE`/`$FDF8` stay `$0000`),
  killed no enemy, and scored only the +10 bubble-pop points -- versus a real flying bolt on the
  lightning round 17.
- **No sprite -- the bubble shows a ROM FONT LETTER.** The elemental-bubble glyph table `$C068`
  (`idx = $7E0E-2`) has real bitmaps only for idx 0/1/2 (water `$B614` / lightning `$B61C` / fire
  `$B624`, in game RAM). idx 3-10 (types 5-12) hold STALE pointers into `$3Exx` = the Spectrum ROM
  character set (`$3D00+`): type 5 -> `$3E28` = 'E', type 7 -> `$3EA0` = 'T', type 12 -> `$3E20` =
  'D', etc. `$BF5B`/`$BF74` overlay those ROM font bytes onto the bubble, so a randomised elemental
  bubble is drawn as a letter-glyph bubble (see SPRITE-COVERAGE, `sprites_bubbles_letters.json`).
- **Net:** on these rounds the "special" bubbles are cosmetically odd (letter glyphs) and
  functionally INERT -- no current, no bolt, no flames. It is a class the level table addresses but
  the effect/sprite code never finished. (This EXTENDS N25, which flagged only idx 11 as dead: idx
  3-10 are equally ROM-font pointers, just reachable.) The rounds so tagged: 3, 4, 7, 8, 9, 14, 21,
  23, 27, 35, 40, 49, 53, 55, 56.

Type ordering CONFIRMED: LIGHTNING = 3, FIRE = 4 (matches the `elemental_lightening` level-17 and
`elemental_fire` level-25 snapshots). NOTE round 80 appears in the LIGHTNING group but is
boss-special-cased at `$9E71`/`$9EA1` (`CP $50`), so the boss round overrides it. Level 5 -> WATER
matches the `elwater` snapshot exactly. This SUPERSEDES OPEN item 1 above ("per-round ENABLE") --
the enable IS the `$7E4B` per-level table setting `$7E0E`. REMAINING (smaller): the spawn TIMING
within a water level (when the ceiling emitter `$7EA0` drops the bubble).

### LIGHTNING elemental (type 3) -- MEASURED (`elemental_lightening.szx`, level 17)

Confirms **LIGHTNING = elemental type 3** (level 17, a type-3 level per the `$7E4B` table) -> so
**type 4 = FIRE**. Far simpler than water: a single straight-flying bolt, not a cellular flow.

- **Bubble & pop**: an ordinary `$FED8` bubble (`+7=$84`), popped by PLAYER CONTACT (the player
  falls onto it). At the pop the position is left in `$FFF7`(X)/`$FFF8`(Y) and the triggering player
  in `$FFFA` -- the same seed globals as water.
- **Bolt objects** `$FDEE` / `$FDF8`, 10-byte entity structs; sprite ptr `+0/+1` = **`$A37D`** (set
  at round setup `$7DFA` for type 3). Fields: `+5` X, `+6` Y, `+7` flags (bit7 active, **bit0 =
  direction**, bit4 = player). Dispatch type3 -> `$9E85` -> `$9E90` (`BIT 7,(IY+7)` active gate).
  **Slot allocation is FIRST-FREE, not per player (MEASURED 2026-09-09 on `round1_2p48`, both players
  given bit 6 and made to pop their own bolt bubble by contact):** a P2-only pop landed in `$FDEE`
  (`+7=$91`: bit4 = player 2, bit0 = direction); with P1's bolt already flying in `$FDEE` (`+7=$80`),
  P2's pop 6 frames later took `$FDF8` (`+7=$91`) -- two bolts in flight at once, one per slot.
  Pop mechanics seen in the same runs: a rising bubble (`+7=$85`) touched by its player goes
  `$85 -> $8F -> $C0` over 3 frames and is gone on the 4th, scoring +1 (10 on screen); poking `+7`
  bit 1 alone does NOT pop it (the contact path sets more than that bit).
- **Spawn `$942E-$945C`** (at the pop): X = `($FFF7)&$F8` = pop X; Y = `($FFF8)&$F8` = **104** (the
  pop row); `+7 = (NOT player_facing_bit0) | (player_index<<4) | $80` -- bit0 is the **INVERSE** of
  the player's facing (`$9454 LD A,(player+7); AND 1; XOR 1` at `$9457`).
- **Direction rule (MUTATION-TESTED)** -- mover `$9D77`: `velocity = (bolt+7 bit0) ? +8 : -8` per
  tick. Because bolt bit0 = NOT player facing, **the bolt flies OPPOSITE to the player's facing**:
  face LEFT -> bolt RIGHT, face RIGHT -> bolt LEFT. Verified by flipping `$FD87` bit0 before the pop:
  facing left -> bolt X 48->96 (right); facing right -> bolt X 32->16 (left). (User-observed, now
  confirmed to the byte.)
- **Travel**: straight horizontal along the pop row (Y=104 fixed), **+8 px per 2-frame tick
  (~4 px/frame)** -- same parity cadence as water -- from the pop X to the screen edge (X~=224), then
  deactivates (`+7` -> `$01`). It passes straight through platform geometry (a beam, unlike water's
  geometry-following flow).
- **Kill**: any enemy on the bolt's row is killed as the bolt reaches its X -> corpse (`$C700`,
  `+9=$FF`) -> death shimmer (`$D340`/`$D360`) -> falls into the corpse->`$9605`->fruit/diamond
  pipeline (same as a bubble-pop kill). MEASURED: 2 enemies (slots 2/3, Y=104) killed at X~=64 (f37)
  and X~=160 (f61) -- matches the user's "kills two enemies".

2-player twin bolt: RESOLVED 2026-09-09 -- the two bolt slots are allocated first-free (`$FDEE` then `$FDF8`), see the LIGHTNING bolt-objects bullet. (STALE items removed: FIRE type 4
IS captured -- see below; the `$A37D` bolt bitmap IS decoded -- 16x16, mask=true, OR-composited /
transparent, in `build/boss_sprites.json` / SPRITE-COVERAGE.)

### FIRE elemental (type 4) -- MEASURED (`elemental_fire.szx`, level 25)

Confirms **FIRE = type 4** (level 25 per the `$7E4B` table). A falling drop that spreads into a row
of floor flames -- a third distinct shape (water = flowing queue, lightning = straight beam, fire =
drop + floor spread).

- **Bubble & pop**: an ordinary `$FED8` bubble popped by PLAYER CONTACT (here the player must JUMP up
  into it; jump key measured = keyboard **'Q'**). Pop position -> `$FFF7`/`$FFF8`, player -> `$FFFA`
  (same seed globals as water/lightning).
- **Object** `$FDEE` (the shared elemental-object slot, as lightning): `+5` X, `+6` Y, `+4`
  state/flame-count. Phase/lifetime counter is the self-mod operand at **`$9F64`** (top of handler
  `$9F63`): `<$20` = FALLING phase (`$9F6D-$A04D`), `>=$20` = BURNING phase (`$A04E`+).
- **Fall** (`$9F6D`..): the drop spawns at the pop X (grid-snapped, 184->192) and falls straight down
  ~4 px/frame (8 px per 2-frame tick), testing the shadow platform bit `$20` one row below (`$9F85`)
  until it lands on a floor. MEASURED: Y 152->160->168->176 (t0-t6), landed Y=176.
- **Spread** (at landing, t8): `+4` -> `$09`; flames spread from the landing cell via **`$9FC8`** --
  up to **4 tiles LEFT** (`DE=$FFFF`) + **4 RIGHT** (`DE=1`) + the centre = **9 flames maximum**.
  `$9FC8` steps tile-by-tile and STOPS EARLY when the next cell is NOT floor (`LD A,(HL); AND $20;
  RET z` -- a gap/edge) or when the cell ABOVE is floor (`RET nz` -- a wall). So **on a surface
  shorter than 9 tiles the fire spreads only as far as the floor continues (clipped at gaps and
  walls), giving fewer than 9 flames** -- 9 is the maximum.
- **Burn & end**: the flame row burns for **~267 frames from the pop ~= 5.3 s** (user: "~5 s"), then
  the effect ends (the `$9F64` counter resets to 0). MEASURED.
- **Enemy kill**: flames kill enemies that touch them -> corpse -> `$9605` fruit/diamond (as the
  other elementals; not separately frame-pinned in this busy capture).
- **Handler**: dispatch type4 -> `$9F63`; fall/land/spread `$9F6D-$A04D` (`$9FC8` spread, `$9FE0`
  address build); burn `$A04E`+.
- **TRANSLITERATED AND GATED (M7.67, `tools/fireman.py`, FM1..FM4).**  The routine, read whole:
  - **The arm `$93FD`**: `RET nz` while `($9F64)` is set; else `($9F64)` := 1, `($FDF3)` :=
    `(($FFF7)+8) AND $F8`, `($FDF4)` := `(($FFF8)+15) AND $F8` -- both adds EIGHT-BIT.
  - **The phase is `$9F63`'s own operand, and it is stepped TWICE a tick in the burn**: `$9E64`
    increments a non-zero `($9F64)` on every even tick whatever the class, then `$9F63` does `INC A` and
    tests `CP $20`.  The fall never stores the phase, so it falls with the phase counting up; at `$20`
    the burn takes over even mid-fall (the direct sweep's `$1F`).  The landing stores `$2A`; the burn
    stores `A`, so it runs `$2C`, `$2E` .. `$F8` -- 103 paints over 208 frames -- and `$FA` ends it.
  - **The drop**: erased each tick by `$9FF6` from the BACKING STORE (screen + `$A000`) at the cell
    `$9FE0` builds from the ROW TABLE at `$FD00` -- which is not the screen's: rows 0 and 1 hold `$01FF`
    and rows 24..31 `$0000..$00E0` on every state captured, so an erase there writes into the ROM.  Then
    `$AEDC`'s shadow cell: solid, or the cell below it open -> `$A00D` (Y + 8 eight-bit; `>= $BF` ->
    phase 0, nothing drawn; else the glyph `$B624` OVERWRITES the cell); else the landing.
  - **The landing `$9F8F`**: the flame row's screen address is built in the alternate HL from the floor's
    shadow cell (+`$5FE0`, then `H AND 3` -> the third's page); `(IX+4)` := 1; `$9FC8` left then right,
    four steps each, counting; the left steps `DEC L` the alternate address -- EIGHT-BIT, so past column
    0 it wraps inside its third's page (`$48FF` from row 8, `$40FF` from row 0) while the shadow walks
    back a row -- and `($FDF0)` takes the leftmost.
  - **The burn `$A04E`**: the frame `$A39D` (bit 3 clear) or `$A3A5` stored into `$A074`, the operand of
    `$A073 LD DE,nn`; the count clamped to at least 1 by `SUB 1 / ADC A,1` and WRITTEN BACK; the cells
    `INC L` eight-bit; the attributes `$42` through `$995A`.
  - **The end `$A030`**: phase 0, the cells restored from the backing store (a count of 0 is 256), the
    attributes `($8309) OR $40` -- the WHOLE byte, where the water's erase takes `AND 7`.

### All three elementals mapped

Selected per level by the `$7E4B` table (`$7DD6` -> `$7E0E`): **WATER** (type 2 -- flowing
attribute-address queue `$A25D`, geometry-following, carries the player), **LIGHTNING** (type 3 --
straight horizontal beam `$FDEE`, flies opposite the player's facing, kills its row), **FIRE**
(type 4 -- falling drop `$FDEE` -> up to 9-flame floor spread `$9FC8`, burns ~5 s). Types >=5 are
randomised higher elementals (`$7E04 LD A,R`), not yet examined.


## HURRY UP! + Boris / Baron von Blubba (M5, MEASURED)

CORRECTION of an earlier note in this file that said "Boris did NOT spawn in a 50 s forward-run":
that was a MEASUREMENT ERROR -- I watched the `$FD80` entity table, but **Boris lives in a
dedicated 10-byte struct at `$9250`**, outside that table. Re-run watching `$9250`, the harness
reproduces the whole sequence faithfully. Snapshots: `Hurry_Up.szx` (mid-HURRY UP!, player about to
die) and `boris_moves.szx` (Boris on screen, ~1 s before he moves), both round 4.

1. **Hurry-up trigger -- `$9037`.** `LD A,($8609); CP $50; RET z` -- no hurry-up on round 80 (`$50`,
   the boss). Then `LD DE,($8DBD); LD HL,($745C); OR A; SBC HL,DE; RET nc`: **`$8DBD`** is the
   play-timer (16-bit, `+1`/frame -- measured 1451->2002 over 551 frames), **`$745C`** the hurry-up
   threshold (16-bit; **PER-ROUND**, N21: set at round setup `$735A-$7373` -- `LD A,($8609)`;
   `CP $38`(r56)->350; `CP $48`(r72)->30000; `JR nc`(r73-81)->1000; else 1500; `LD ($745C),HL`.
   VERIFIED by disasm + poke `$8609`=r+`call $735A`. Round 80 hurry is suppressed by `$9037 CP $50
   RET z`). When `$8DBD`
   passes `$745C` the hurry-up starts; self-mod flag `$904D` latches it so later frames `JP $917C`.
   On trigger the text position `$9A04` is set to `$FD2C` and an `OUT ($FE)` klaxon plays
   (`$906F/$9081/$908F`).

2. **"HURRY UP!" text animation -- `$90DF-$9118`.** String at **`$9A1C`** (in the `$9A06` text
   table: ROUND/READY/HURRY UP/GAME OVER), printed by text routine **`$802E`** (IX = string). The
   position pointer `$9A04` is decremented by 2 each pass (`LD IX,($9A04); DEC IX; DEC IX; LD
   ($9A04),IX`), so the text travels UP the screen -- matching the observed bottom -> centre (hold
   ~1 s) -> top -> off.

3. **Boris activation -- `$917C`.** `LD HL,($745C); LD DE,$1F4; ADD HL,DE; LD DE,($8DBD); SBC HL,DE;
   RET nc` -- Boris waits until the timer reaches threshold **+ `$1F4` = 500 frames = 10.0 s**
   (matches the user's "~10 s after HURRY UP! disappears"). MEASURED: from `Hurry_Up.szx` (timer
   1451, threshold 1500) Boris's flags `+7` went `00 -> 80 -> E0` (activate) at frame 550, when the
   timer hit 2002 = 1500 + 500.

4. **Boris struct -- `$9250`** (dedicated, in the code region, NOT an `$FD80` slot):
   `+0/+1` sprite ptr (`$FF50`), `+2` draw-Y / `+3` draw-X, `+4` anim (`02` idle / `04` moving),
   `+5` X, `+6` Y, `+7` flags (`$E0` active), `+9` state (`08`). Spawn init (`$911A-$9134`) writes
   X=`$18` (24), Y=`$A8` (168), anim=2, state=8 -> **Boris spawns bottom-left (24,168)**.

5. **Boris sprite -- `$FF50`**, a 16x16 masked sprite in the standard format (rows of
   `maskL,dataL,maskR,dataR`; `screen=(screen AND mask) OR data`). Decoded to a rounded one-eyed
   creature; confirmed on screen (cyan, floating by the left wall). The pointer is (re)written to
   `$FF50` on each horizontal move (`$9234: LD HL,$FF50; LD (IY),L; LD (IY+1),H`). NOTE: `$FF50` is
   high RAM (just below the score at `$FFE4`); treat it as Boris's live sprite buffer.

6. **Boris AI -- homing, `$91F1-$9249`.** Axis toggle **`$91BC`** selects vertical (`$91F7`: step
   +-8 toward player Y `$FD86`) vs horizontal (`$921B`: step +-8 toward player X `$FD85`); 8 px per
   step. Drawn via the master sprite routine **`$A447`** (IY=`$9250`); movement gated by self-mod
   counters (the rotating `IY+4` copied to `$91DC`, and `$91E4` mod 16 / `$918B`). MEASURED
   (`boris_moves.szx`): idle ~1.5 s at spawn, then floats straight up 8 px/frame (Y 168->96 in 8
   frames), settles on the player's row (Y 104). He then CLOSES HORIZONTALLY on the player in
   periodic bursts of 8 px/frame steps -- measured with the killer enemy frozen so the player
   survives: X 24 -> 64 -> 168 toward the player at X=196, bursts separated by long (~500-1000
   frame) holds. Earlier no-input runs showed him "hold" at X=24 ONLY because a regular enemy
   jumps up and kills the player before Boris closes (user-confirmed) -- NOT a harness gap. He is
   invincible and kills on contact (design). **Contact-kill (RESOLVED 2026-09-08, N22):** a 16x16
   AABB overlap via the `$92DE` self-mod -- `$925A` NOPs `$92DE` before the player checks so `$92BB`
   falls into `$92DF LD HL,$9257` (Boris); the box test `$92E4`/`$930A`/`$9312` compares the player
   box (X+2..X+14, Y+2..Y+14) against Boris `$9255`/`$9256`; an overlap does `CALL c,$927D` = player
   death, setting `$FDDA`/`$FDE4` bit2+bit7 and death-anim `$50`. Mutation: NOP-ing the `$92DE` reset
   at `$925A` -> no kill.

7. **Boris despawn / hurry-up reset -- `$915F-$917B`.** `DI; clear latches ($9160/$9257/$904D);
   LD HL,0; LD ($8DBD),HL` (zero the timer); `IY=$9250; CALL $A314` (remove Boris); `EI`. Fires on
   round-clear / player-death, which is why hurry-up restarts cleanly next round.

**Boris approach + kill -- RESOLVED 2026-09-10 (`boris_kills_player.szx`, round 4, code `$918B-$924D`).**
Boris is a PHASE MACHINE that homes on the LIVE player over ~10 s stages:

- **Phase byte `(IY+4)` at `$9250+4`** doubles each stage via `RLC (IY+4)` at `$91AE`: `02`(appear)
  -> `04` -> `08` -> `10` -> `20` -> `40` -> `80`; at `80` the carry calls `$91C7` = reset to `$40`
  (so it cycles). Odd stages re-align Y, even stages step X (axis flag `$91BC`, toggled `$91BD`).
- **Each stage = a WAIT then a MOVE.** The wait is ~**512 frames** (~10.3 s) -- the counters `$9194`
  (256 calls) x `$919C` (x2) at `$9193-$91A2`; MEASURED gaps between phase changes: 532, 521, 516,
  513, 524, 513 frames. This is the "long dawdle".
- **Y-align (`$91F7`):** reads the LIVE player Y `$FD86`, steps `(IY+6)` by +-8 px/frame TOWARD it,
  ends the stage within 8 px of the player's Y. **X-approach (`$921B`):** reads the LIVE player X
  `$FD85`, steps `(IY+5)` by +-8 px/frame toward it (walk sprite `$FF50` set at `$9234`), a capped
  hop per stage. VERIFIED LIVE-TARGETING: poking the player to a new (X,Y) mid-wait makes the next
  Y-align track the new Y (168->144 toward player Y=136 instead of 96).
- **The lunge = the final X move overlapping the player -> the AABB contact kill** (`$92DE` box ->
  `$927D` death, point 6). MEASURED on the owner's capture (idle player frozen at (212,96)): appear
  at (24,168) f0; up to player Y (168->96) f532-540; X hops 24->64 (f1053), 64->168 (f2082, = the
  player's cell -5, the "waits near me" moment), a Y bob at f1569/2606 (the "little glitch"); final
  X lunge 168->216 into the player, **KILL at f3285**. One struct only, NO extra copies over 3285
  frames -- the arcade's "extra Boris per dawdle" does NOT happen here.


- **Boris movement, LIVE (2026-09-09, from the owner's `Boris_Moves.szx` = `boris.pkl`, round 4)**:
  Boris sits at (24,168) with `+7=$E0`, anim `+4`=2, for 79 frames, then DASHES straight UP at
  **8 px/frame for 9 frames** (Y 168 -> 96, anim 4), overshoots back to Y=104 in one +8 step and
  then does not move at all for the next ~390 frames (dx,dy)=(0,0) -- the "long dawdle" is real:
  bursts of 8-px steps separated by long pauses. Only ONE Boris struct (`$9250`) exists; no extra
  copies appeared in 600 frames. It was removed (`+7`=0, `$904D`=0) at f474 when the player died
  (the `$915F` reset). In a harness run on round 1 (death handler RET-patched) Boris activated
  exactly 500 frames after HURRY UP (timer = threshold + 500, `$917C`) at (24,168) and had not moved
  700 frames later. (Burst cadence + targeting rule now RESOLVED above via `boris_kills_player.szx`.)

## Umbrella (warp) power-up -- MEASURED (`powerup_umbrella.szx`, level 25)

The umbrella is a WARP power-up: collecting it skips several levels, each briefly drawn with its
enemies falling into position and the whole playfield flashing, before advancing to the next.

- **Collect**: a collectible picked up by touching it (here directly above the player, so a jump;
  jump key measured = keyboard 'Q'). Its on-collect handler is **`$88B1`**.
- **Skip count is RANDOM** -- `$88B1`: `CALL $FE85` (the deterministic PRNG); `AND 3` -> 0..3; then
  `SUB 1 / ADC A,0 / ADD A,A / ADD A,3` maps {0,1,2,3} -> **{3,3,5,7}**, stored in skip counter
  **`$FECD`**. So the umbrella skips **3, 5, or 7 levels** (3 ~=50%, 5 ~=25%, 7 ~=25%). MEASURED:
  this capture's PRNG state gave 5 (25->30); calling `$88B1` over 24 PRNG draws gave 3x11 / 5x6 / 7x6.
- **Skip counter `$FECD`** = levels remaining to skip, driven in the MAIN LOOP (`$8D0D-$8D1C`):
  ```
  8D06 CALL $96DF        ; draw the skip level + enemies fall into position (~128 frames)
  8D09 CALL $97F8        ; level advance: $8609++ (wraps at 82/$52 -> $FEC7)
  8D12 LD A,($FECD); OR A; JR z,$8D1E   ; counter 0 -> leave skip, resume normal play
  8D18 DEC A; LD ($FECD),A ; else decrement
  8D1C JR $8D09          ; and advance again
  ```
  `$97F8` is the SAME routine as a normal level-clear; the umbrella just fires it `$FECD` times.
- **Per-level pacing**: ~128 frames / ~2.5 s each (MEASURED: increments at f44/171/299/428/556) --
  the `$96DF` animation (level drawn, enemies falling into position); the playfield flashes throughout.
- **CAUSAL (mutation-tested)**: poking `$FECD`=1 mid-skip ended it after one more level (delta 2 not 5).

- **Collectible entry (RESOLVED 2026-09-08, N23):** the umbrella is power-up **type 6** (dispatch
  `$8839[6] = $88B1`); its sprite is `$5D60` (via `$8639[6] = 3` -> `$5D00 + 3*32`).
- **Pacing is FIXED, not enemy-gated (RESOLVED, N23):** MEASURED ~127-128 frames/level; perturbing
  or removing the enemies left the deltas unchanged.
- **`$FEC9` = the level-advance ABORT gate (RESOLVED, N23):** read at `$8D0D` (`RET nz`); set to
  `$B4` by `$8E2A` when both players' `+7` bit7 are clear (game-over), cleared by `$96DF`. Holding
  `$FEC9 = $B4` froze the skip.
- **The collect's own block, `$88C0 JP $A110` (MEASURED + PORTED, M7.98; `tools/umbrella.py` ->
  `build/umbrella_fixture.json`):** BEFORE the main loop skips anything, `$A110` runs FIVE turns of
  `CALL $A0E0` (the FLASH: `OUT ($FE),A`, then `$5840..$5AFF := (x AND $00) OR $10` -- 704 cells, red
  paper) / `EI / HALT` / `DI / CALL $8C28` (the REVEAL, interrupts off) / `EI / HALT` / `DI / POP BC /
  DJNZ`, then `EI / RET` into the item manager.  Five whatever (`$FECD`) is: the count shows in the block
  only as the FIRST flash's border (A = 3 / 5 / 7); after a reveal (`$8C4D XOR A`) every flash sends 0.
  Exact segments: head 29,000 T, flash 29,010, reveal 213,337 / 214,271 / 217,647 (round1_48 / r50_48 /
  the umbrella world), end 36.  Contended: 28.3..30.3 frames from `$88C0` to the RET, 10..11 ISRs, 3 or
  4 interrupts lost under each reveal (by the phase the HALT's ISR leaves).  The natural collect on the
  umbrella world drew 5 (25 -> 30), the main loop resuming 668.6 frames after `$88C0`.  The port did
  none of it until M7.98 (`puDispatch` returned at `$88C0`).

## Player physics -- MEASURED (round1, harness-driven)

Controls in this state = CURSOR keys (jump `0`, left `5`, right `8`); the `.szx` snapshots used
keyboard (jump `Q`, left `O`, right `P`). The port keeps both key paths (input decisions 2b).

Player = entity slot 0 (`$FD80`): `+5` X, `+6` Y, `+7` flags (bit0 = true facing), `+4` anim,
`+9` = jump-phase / air-state (`$FD89`). `$FD88` (`+8`) = **DIRECTION-INPUT bitmask** (CORRECTED
2026-09-08, R13 -- NOT a facing/sub-pixel code): low nibble = this frame's held directions, high
nibble = previous frame's (seeded by `$AC00 LD A,(IY+8)` + `ADD A,A`x4, merged with the control
table `$B5FD`/`$B605`). Bits: `bit0`=BLOW, `bit1`=jump, `bit2`=right, `bit3`=left (M7.44: `bit0`
was mis-read here as "down"); the high nibble is the PREVIOUS READ's, two frames earlier, since
the reader runs on odd ISRs only. So the
observed `$44`=right, `$88`=left, `$22`=up (both nibbles). Consumed at `$ADAA` (`LD A,(IY+8) /
AND $0C` -> L/R) and `$AEA1` (`BIT 1,(IY+8)` -> jump). No instruction ever loads `$22/$44/$88` as
an immediate. True facing is `(IY+7)` bit0.

- **Cadence**: the player updates every OTHER 50 Hz frame (2-frame tick ~= 25 Hz) -- X, Y and the
  jump phase all advance on alternate frames.  PINNED 2026-09-10 (M7.4a, scratchpad walkwrite): the
  move commits on the **EVEN frame (parity `$8DBD` bit0 == 0 = the entity-DRAW frame, M7.3b)** -- X
  (`$FD85`) is written on par=0 only, by `$AE6A` then `$AB11`; odd frames do not move the player.
  So player logic + entity draw share the one 25 Hz beat.
- **Walk**: a clean **+2 px per tick** (`$FD88` is the direction bitmask, NOT a sub-pixel
  accumulator -- it held `$44` throughout a right-walk), netting **~1 px/frame ~= 50 px/s**
  (MEASURED X 24->52 over 29 frames). Position clamped to X in [`$10`,`$E0`] (16..224) by `$AB0C`.
- **Jump trigger `$AD00`**: `BIT 1,C` (jump input) AND NOT `BIT 5,C` (already airborne) ->
  `LD (IY+9),1` (`$AD08`, start; also `RES 4,(IY+$5A)` clearing the water-carry bit). **Fixed height
  -- no variable-jump, no double-jump** (`$AD08` sets phase:=1 exactly once; `$AD65` auto-increments
  thereafter regardless of the button, so tap length is irrelevant). Apex Y=127 (a 41 px rise from
  168) is reached at phase 15 (~28 frames / ~14 ticks); the apex is held flat through phases 15-19
  (the four `0` arc entries); the full 24-phase arc spans ~48 frames at the 2-frame (25 Hz) cadence.
  (The old "20-frame hold" figure conflated 25 Hz ticks with 50 Hz frames -- ~19 ticks to end-of-apex.)
- **Jump arc `$AD65-$AD8F`**: phase `$FD89` (1->32) indexes arc table **`$B57D`** and
  `Y += table[phase-1]`; phase increments each tick (clamped 33 -> `$FF`). `$B57D` =
  `[-4,-4,-4,-4,-4,-4, -3,-3,-3, -2,-2,-2, -1,-1, 0,0,0,0, +1,+1, +2,+2,+2, +3]` -- decelerate-up /
  apex / accelerate-down; total rise = 41 px (MEASURED 168->127). **Same arc-table family as the
  enemies** (`$B59D` = enemy variant, `$B5BD` = a gentler arc e.g. bubble-bounce).
  - **Phases 25-32 / unbounded index (MEASURED, N2):** the phase counter runs 1->32 then is CLAMPED
    to `$FF` at `$AD6E` (`CP $21` -> `$AD72 LD A,$FF`). The index at `$AD84` (`ADD A,(HL)`) has NO
    bounds check: ascending phases 1-14 take the simple path `$AD81`; apex/descent phases >=15 take
    `$AD90`, which floor-probes and lands (`JP $AD51`, phase:=`$FF`). So a normal descent lands at
    phase ~24 -> `$FF` -> 0, and phases 25-32 are reached ONLY falling through open air, where the
    lookup SPILLS past the 24-entry table (ends `$B594`) into the 8-byte region **`$B595`**
    (`3 3 4 4 4 4 4 4`, before the enemy table `$B59D`) = an accelerating +3/+4-per-tick fall
    (MEASURED shown-phases 25-28 = +3,+3,+3,+4, i.e. `table[phase-2]` with the 1-tick display lag),
    until phase 32 wraps to `$FF` and flat +2/tick gravity takes over.
- **Fall (stepping off a platform)**: floor probe `$AD11` (reads the shadow platform bit `$20` below
  the sprite, self-modded at `$AD41`); no floor -> `$FD89`=`$FF`, gravity a CONSTANT **+2 px/tick**
  (`$AD5A`); on landing `$FD89` -> 0 (`$AD4C`). MEASURED: poked mid-air, Y fell +2/tick to the
  platform. (A jump's own descent uses the `$B57D` positive tail instead of this flat +2.)
  - **Free-fall HORIZONTAL cadence (M7.4d, MEASURED 2026-09-10):** while `$FD89`=`$FF` the tick
    goes through `$AD11`, which calls the horizontal move `$ADAA` ONLY when the self-modifying
    counter byte `$AA65` (the operand of `LD A,nn` at `$AA64`, decremented once per EVEN tick by
    `$AA60-$AA6B`, reloading to 4 at zero: 4,3,2,1) reads **1** -- i.e. a falling player steers
    only every 4th even tick (X advanced at f67/75/83/91 in the walk-off oracle).  The arc
    (`$AD65`) and grounded (`$ACFA`) ticks call `$ADAA` every tick.  Image value of `$AA65` = 3.
  - **The floor probe is FULL-WIDTH (`$AE81`/`$AE7F`, decoded `$AE89-$AE99`):** it tests the
    cells at `X>>3`, `+1`, and `+2` when `X&6 != 0` (the 16-px sprite spanning three cells), at
    row `(Y+16)>>3`.  Consequence: walking LEFT off a ledge the sprite OVERHANGS until no spanned
    cell has floor (off the row-19 ledge's col-7 end the drop is at x=40, not 54 as a left-edge
    probe would give -- MEASURED).  Landing is `$AD18`'s even-align (`$AD1E AND $FE`) plus
    "floor below -> phase 0, Y kept"; there is no separate row-snap.

- **Walk-step `$AE61`**: `X += 2` per tick (mirror `X -= 2` for left), gated by a wall/collision
  check `$AE75` (`RET nz` = blocked), clamped to X <= `$E0` (224); the even-align `$AB11` (`AND $FE`)
  holds X on the 2-px grid. `$FD88` is the direction-input bitmask (R13, above; `$44` right / `$88`
  left / `$22` jump held), NOT a sub-pixel accumulator -- the step is a clean +2.
- **In-air steering: YES** -- horizontal (walk-step) and vertical (arc) are DECOUPLED: holding a
  direction during a jump moves X at the full walk rate (MEASURED +36 px across one arc) while the
  `$FD89` arc independently drives Y.
- **Two players**: P1 = slot 0 (`$FD80`), P2 = slot 1 (`$FD8A`) -- identical mirrored struct
  (MEASURED play2p: P1 X=24 facing right, P2 X=216 facing left); both share the SAME physics
  routines (IY selects the slot). Persistent per-player state: P1 `$FDDA` / P2 `$FDE4`.
  - **Mid-game P2 JOIN (M7.4d-iv, MEASURED 2026-09-10 by write-watch on the '2' press frame):**
    `$99C9-$9994`, a player-START init and NOT the respawn `$AB6B`: `+5 := $D8` (216), `+0/1 :=
    $D920` (standing), `$FDE4 := 1` (the player-index bit), `+$60/+$61 := 0`, `+8 := 0`, `+6 := $A8`,
    `+7 := $40` then `SET 7` (-> `$C0`, active, facing LEFT), `$FDE4 |= $88` (active + bit3
    invulnerable), `+4 := $50` (the same 161-frame countdown as a respawn), lives `$FDE6 := 3`.  It
    runs from the main loop after the player ticks (P2's first tick, `+4 -> $4F`, is the next
    frame) and does NOT reset the hurry timer (`$9160` untouched).  Verified by the engine over
    180 frames with the join injected; two-player simultaneous physics (P1 keys / P2 Kempston,
    `round1_2p48`) verified over 120 frames with no player-side code beyond the slot
    parameterisation and the once-per-frame `$AA65` cadence.

- **Landing row-snap + walk wall-gate (RESOLVED 2026-09-08, N6):** X is even-aligned by `$AD1E`
  (`AND $FE`); the feet-probe reads cell `(X, Y+15)` via `$AE81` (mask `$20`, with `$AE9C`
  self-patched to `RET`) -- a hit sets phase:=0 at `$AD4C` (settles Y=136=17x8), a miss sets
  phase:=`$FF` (+2 gravity). The walk-step `$AE61` gates on `CALL $AE75` (`RET nz` = blocked);
  `$AE75` checks the foot cell `(X +- step, Y+15)` in the `$F800` attribute shadow at
  `$F800 + ((Y&$F8)<<2) + ((X>>3)&$1F)` bit 5; `X += 2` clamped to `[$10,$E0]` (right clamps X=224,
  left stops X=16 where `$FAC0/1 = $60`). ($FD88 low nibble resolved above -- R13.)

## Player death, respawn, LIVES and game over -- MEASURED 2026-09-09 (`death.szx`, round 3)

The player is killed by an enemy (slot 5) jumping up under it 12 frames after load; traced through
death, respawn, a second death, and (with lives poked to 0) the game-over exit.

- **Engine gate + refinements (M7.4d-iii, 2026-09-10, a natural enemy-contact death on
  `round1_48`, drift-free capture):** the death tick is the FIRST branch of the per-frame player
  tick (`$AB38 BIT 2,+$5A`), so a dying player runs neither the input stage nor the physics; the
  animation counter `+4` decrements once per `$AB38` run (`$AB5A`), exactly 80 times from `$50`
  (hit f7 -> respawn f169) -- 40 heavy frames with the fast walk, whose `$AAE6` runs it twice
  (M7.48, popkill I13: respawn at ISR 186); the respawn also sets `+8 := 1`, `+9 := 0`, `$904D := 0`, `Y := 168`,
  runs the CALM (`$ABB4/$ABB7/$ABBA`: `$90C1` with `$90D0` flipped to RES 2, M7.48),
  then P1 `X := 24` + `SET 0,+7` (facing right) / P2 `X := 216` + `RES 0,+7`, and requests the
  hurry reset by writing 1 into the OPERAND byte `$9160` of `$915F`'s `LD A,0`; `$915F` (a
  main-loop chain routine, every pass) consumes it on a LATER PASS OF THE SAME FRAME: `$9160 := 0`,
  `$9257 := 0`, `$904D := 0`, `$8DBD := 0` (16-bit, `$9170`), erase Boris (`IY=$9250`, `$A314`).
  The ISR that ends that frame then increments `$8DBD` to 1 -> the frame after a respawn is ODD
  again (two consecutive odd frames), the play timer restarts, and the frame-parity schedule shifts
  by one.  The invulnerability countdown `$ABDE` reuses `+4` from `$50`, decrementing once per
  heavy frame while bit3 is set and `$FED0 != 1`; `RES 3` fires when it goes negative -- 161 frames
  (f169 -> f330).  The engine reproduces all of this frame-for-frame over 372 frames with the hit
  INJECTED (the enemy collision is M7.6). (from the shared collision `$92BB-$92D4`: player box X+2..X+14 / Y+2..Y+14,
  skipped while `$FDDA` bit2 is already set). Gates, in order: **`$FED0` != 0 -> the ENEMY dies
  instead** (`$8BC2` turns it into a `$C700` corpse, `+9=$FF`, live-count `$AA5F` -1) **and the
  player scores +1000 internal (10,000 on screen)** -- an invincibility effect (`$FED0` is set by
  power-up type 10, see the dispatch map); `$FDDA` bit4 (water-carry) -> immune; bit3 (already
  dying/respawning) -> immune. Otherwise `SET 2` + `SET 7` on `$FDDA`/`$FDE4` and death anim
  `(IX+4) := $50`. MEASURED f12: `$FDDA 00->84`, anim `$50`.
- **Death animation** (`$AB48`): sprite -> `$D300`, X snapped to 8 px (`AND $F8`, 190->184), the
  anim counter `+4` counts down from `$50` (`$AB5A DEC / RET p`) -- about **204 frames** on round 3
  (f12->f216; not linear, a slow stretch mid-way; the boss-state probe took ~70 -- cadence not chased).
  The entity stays active (bit7) throughout; score untouched; enemies keep moving; no round restart,
  no READY text.
- **At the anim end `$AB5E DEC (IY+$5C)`: LIVES -= 1.** Lives = **SPARE lives**: P1 **`$FDDC`**
  (persistent struct +2), P2 **`$FDE6`**. Then `JP p`:
  - **result >= 0 -> RESPAWN (`$AB6B`)**: icons redrawn (`CALL $806C`), `+4 := $50` (the
    invulnerability countdown), `$FDDA := (bit0) | bit3 | bit7` -- bit2 (dying) cleared, **bit3 =
    respawn invulnerability** (cleared ~161 frames later: f216->f377), and **bit6 (blue-bottle
    lightning-blow) CLEARED**; `$FDE0 := 0`. MEASURED on the boss state: bit6 1->0, **speed `$FDDF`
    3->7 (default)**, `$FDE1` `$0D->0` -- **death strips the bubble power-ups** (range was already
    default 8). The player teleports to its START (P1 `(24,168)`, bottom-left) in place, mid-round.
    Round 80 special: `$8CB0 := 0`. **The EXTEND mask `$FDE3` is untouched -- persists across death**
    (`$08` throughout; user-confirmed). MEASURED: lives 3->2 at f216, 2->1 at the idle player's second
    death (f675).
  - **result < 0 (died with 0 spares) -> `$AB64 RES 7,(IY+7)`: the player is REMOVED.** Then `$8E2A`
    (both players' active bits clear) sets **`$FEC9`** (`$B4`/`$B5`), **"GAME OVER" is printed at row
    10, col 12** (`$8CE7` -> `$484C`), `$FEC9` counts up to `$FF` (~76 frames, ~1.5 s) and wraps, and
    the game exits to the front end (**round `$8609` 3->0**). MEASURED with `$FDDC` poked to 0.
- **LIVES ARE DISPLAYED (corrects bucket A's "no lives display"): `$806C`**, called at round start,
  at every respawn and at every extra-life grant. The 8x8 icon bitmap is assembled at **`$85B1`**
  (8 alternate bytes copied from `$856C` -- so it is derived from the round's platform tile) with a
  mask at `$85B9`; **P1's icons start at `$50E0` (row 23, col 0) and run RIGHT, P2's at `$50FF`
  (row 23, col 31) and run LEFT** -- the step is a self-modified `INC L` (`$2C`) / `DEC L` (`$2D`)
  at `$80F6`. One masked icon per spare life, **capped at 5 shown** (`CP 5 / LD A,5`), drawn only for
  an ACTIVE player (`RET p` on `$FD87`/`$FD91` bit7); lost-life slots are erased to the wall
  pattern. MEASURED: row 23 cols 0,1,2 held three icons at lives=3; after the respawn col 2 was
  background at lives=2. (The draw also writes `$FF` into the bitmap-shadow copy of each cell --
  purpose not chased.) Bucket A's pixel scan saw these as border graphics.
- **Extra lives**: (a) advancing INTO round **21, 41 or 61** gives **BOTH players +1**
  (`$9809-$982D`: next-round `$FEC7` compared to `$15/$29/$3D`, then `INC (IX+$5C)` and
  `INC (IX+$66)`); (b) **EXTEND completion +1** (`$9558 INC (IX+$5C)` after the centred EXTEND word
  is drawn at attr `$5969`, 14 cells, then `$806C`) -- this is the grant site for the still-open
  bucket-B "6th letter" capture. 3 spares at round 3 in this game (new-game init store not located --
  no direct write to `$FDDC` exists; likely a struct-template copy).

## Boss level (round 80) -- MEASURED (`boss_level_entry` / `blue_bottle` / `bolt_hits_boss` + deep RE)

The boss round is a DIFFERENT beast (user). Entry state MEASURED:
- **Level = 80** (`$8609`=`$50`) and **`$7E0E`=3** -- the level is armed for the LIGHTNING elemental,
  and the lightning-bolt object `$FDEE` is pre-seeded with its sprite (`$A37D`), inactive at entry.
- **Blue bottle** top-left. MEASURED (`blue_bottle.szx`, walk left off the platform to drop onto it):
  contact sets the player's power-up field **`$FDE1`** (= entity struct `+$61`, `IX=$FD80`) from `00`
  to **`$0D`** -- setter `$8829` (`LD (IX+$61),A`; value staged at `$8827`, gated on `$872C`, then a
  power-up dispatch through the jump table at `$8839`). The flag PERSISTS (held until the player dies
  ~1 s later by falling). The bottle is a fixed level object, NOT a `$9605` pickup, and is not removed
  by contact. The bottle sets the persistent **lightning-blow ability = `$FDDA` bit6 (P1) /
  `$FDE4` bit6 (P2)** (power-up handler 13 `$889C`; `$FDE1=$0D` only RECORDS the collected type).
  NOTE the static image has `$0E` at `$8828` but the runtime value written is `$0D` (self-mod
  operand, R7) -- `$0D` is the measured grant.
- **Damage model** (user, now CONFIRMED live -- `boss_blow_bolt.szx`): the ONLY way to hurt the boss
  is to blow a LIGHTNING bubble, pop it, and hit the boss with the released bolt. Full chain below.

### Blue-bottle lightning-blow -> bolt bubble -> boss damage (MEASURED, `boss_blow_bolt.szx`)

The blue bottle makes **every blown bubble a bolt bubble**; popping it releases the `$A37D` bolt
(the SAME object as the LIGHTNING elemental), which damages the boss if it sweeps the boss's row.
Traced end-to-end in the harness (blow key = SPACE, decoded from the P1 key table `$B5FD` = O/P/Q/SP):

1. **Blow marks the bubble (`$BDC1`).** At blow-create: `XOR A / BIT 6,(IX+$5A) / JR z / LD A,3 /
   LD (IY+9),A` -- if the player's `$FDDA` bit6 (lightning-blow) is set, the new bubble's **`+9`
   state = 3** (= lightning element); else 0 (normal). MEASURED: after SPACE, pool slot0 `+9=03`,
   `+7=$C1` (travels then rises exactly like a normal bubble; sprite `$C780` -- looks normal).
2. **The player must POP it (contact).** The bubble manager `$B636` routes a bubble by `+7`: bit2
   clear -> travel/rise handler `$BDFE`; bit2+bit3 set -> pop `$B6C3`->`$B6D8`. A PLAYER pop stamps
   the bubble `+7` **bit1** (the emit flag) via `$B9B6` (`SET 1`+bit3+bit2+bit4); a mere
   wall/ceiling hit (`$BEAF`) sets bit2+bit3 but NOT bit1, so it pops WITHOUT emitting. (MEASURED:
   forcing bit2+bit3 alone -> no bolt; adding bit1 -> bolt.)
3. **Pop emits the element (`$B6D8`->`$B725`).** `$B6D8` copies the bubble's `+9` (=3) to the
   self-mod operand `$B742`; the emit code `$B725` is gated by `BIT 1,(IY+7)/RET z` (the bit1 above),
   then writes **`$FFF9`=3** (lightning) + `$FFFA`=player + `$FFF7/8`=pop X/Y. So a popped bolt
   bubble drives the exact same `$FFF9`=3 lightning path as a popped lightning-ELEMENTAL bubble
   (R14) -- the two mechanics are unified.
4. **Bolt spawns + flies.** `$FFF9`=3 -> the lightning dispatch spawns the bolt object `$FDEE` (P1)
   / `$FDF8` (P2), sprite `$A37D`, at the pop position, `+7` bit7 active. It sweeps HORIZONTALLY
   along the pop ROW at +8px/2frame (~4px/f), direction OPPOSITE the player's facing (MEASURED:
   player faced right -> bolt flew LEFT, X 24->16->8, deactivating at the wall; active ~46 frames).
   Mover `$9D77`.
5. **Boss damage (CONFIRMED live).** When the bolt's tile matches the boss (`$9F29`: tileX ==
   `$A8DB` or `$A8DB+3`; `$A839` == boltTileY+1/+2/+3), boss HP `$9F62` -=1 (`$9F56`) and +100 score
   (`$9EE7`: `$FFED=$100`->`$80FA`). `$9EE7` does NOT stop the bolt (it advances on non-hit frames),
   but a hit frame skips the advance -- so a MOVING boss takes ~1-2 hits as it briefly aligns (the
   two-column box, bucket-A N13), while an immobilized boss is drained (MEASURED: pop at the boss's
   row, boss frozen -> HP 42->41->...; boss moving -> the bolt swept past and MISSED, HP unchanged).
6. **Geometry (the skill):** the bolt sweeps only the ROW it is popped on and flies AWAY from the
   player's facing. To hit the boss the player must pop the bolt bubble at the boss's height (jump /
   ride bubbles up), facing so the bolt flies toward the boss. Popping at the floor (Y=168) sends
   the bolt along the bottom, nowhere near the boss (MEASURED: HP unchanged).

### Boss internals -- deep multi-agent RE (13 agents), harness-verified + independently re-checked

INDEPENDENTLY RE-VERIFIED in the main session: velocity `$AA47`/`$AA48` = +-1; `$F800` shadow writes = 0
over 30 f (the boss blits to the DISPLAY file, NOT the shadow -- corrects my earlier "renders via shadow"
note); causal wall-bounce pokes reflect at X tiles **2 and 26**, Y tiles **3 and 19**, velocity flipping
each time; death-at-0 fires (poke `$9F62`=0 -> `$FFEF`=`$10` within 1 frame; HP=1 stays alive -- corrects
my earlier "death did not fire passively", which was a late poll after `$8167` consumed `$FFEF`). Key
corrections folded in below: **`$A969` is the boss<->PLAYER collision** (boss hurts the player on contact,
`$AA35`->`$927D`), NOT the bolt collision; **start HP = 42** (the `20`/`$79A3` seed is vestigial); **round
81 is a distinct final room, not a 2nd boss form**.

> **Corrected premise (MEASURED FALSE):** the boss does **not** render through the `$F800` attribute shadow. Its bitmap and attributes are blitted straight to the display file (`$4000–$5AFF`) by `$A8C1`. A `$F800` write-watch logs **zero** writes across boss frames. The `$E000`-region shadow and `$F800` clean-attr region are *read* only, to erase/restore the background under the old boss position.

---

### (a) Position, velocity, and the MOVEMENT / bounce algorithm  *(priority)*

**Storage.** Position is stored **only in tile units (8-pixel attribute cells)** — there is no sub-tile/pixel coordinate. On-screen pixel origin = `tile * 8`.

| Var | Meaning | Range (measured) | Writer |
|---|---|---|---|
| `$A8DB` | Boss X tile | `2 .. 26` | `$AA45` (`LD (HL),A`) |
| `$A839` | Boss Y tile | `3 .. 19` | `$AA45` |
| `$AA47` | dx velocity (signed byte) | `+1`/`-1` (image default `$01`) | `$AA43` (`LD (DE),A`, on bounce) |
| `$AA48` | dy velocity (signed byte) | `+1`/`-1` (image default `$FF` = −1) | `$AA43` (on bounce) |
| `$AA06` | phase counter (self-mod operand of `LD A,n` at `$AA05`) | mod-32 | `$AA0A` |
| `$AA00` | frame-gate scratch (`$8DBD − $37`) | — | `$AA01` |

Both `$A8DB` and `$A839` are written by the **single** store `$AA45`; both velocity bytes only by `$AA43`, and only on a bounce (MEASURED: write-watch showed each position byte written solely by PC `$AA45`, each velocity byte solely by PC `$AA43`).

**Per-frame gate + movement.** Entry `$A9ED`, body `$AA0E`:

```
boss_move_tick():                       # $A9ED, CALLed every main-loop iter from $8D2E
  if mem[$8609] != $50: return          # $A9ED  round-80 gate ($8609==$50); inert otherwise
  if mem[$A839] == 0:  A=4; goto $A84D   # $A9F3  Y-tile==0 -> SPAWN (see lifecycle)
  mem[$AA00] = mem[$8DBD] - $37          # $A9FC
  if that == 0: return                  # $AA04  skip the frame where global counter $8DBD==$37
  ph = (mem[$AA06] + 1) & $1F            # $AA05  self-modifying mod-32 phase counter
  mem[$AA06] = ph
  if ph != 0: return                    # $AA0D  fire body only when phase wraps -> ~every 3 frames

  # ---- movement body $AA0E ----
  call $A9DA                            # ERASE old boss footprint (restore clean bg), 4 tile-rows
  axis_update(pos=$A8DB, vel=$AA47, BC=$1B02)   # X: lo=C=2,  hi=B=27
  axis_update(pos=$A839, vel=$AA48, BC=$1403)   # Y: lo=C=3,  hi=B=20
  call $A8C1                            # DRAW boss at new position (display file + attrs)
  if call $A969 -> carry:               # boss<->PLAYER overlap (NOT bolt, NOT platform)
     if !(IX+$5A bit2): jp $927D        # $AA35  stun/kill the touched player
```

**The bounce core** (`$AA38`, shared by both axes — a pure DVD-logo reflection):

```
axis_update(pos, vel, lo=C, hi=B):      # $AA38
  cand = mem[vel] + mem[pos]            # LD A,(DE) / ADD A,(HL)
  if cand <  lo: goto bounce            # CP C / JR c
  if cand <  hi: mem[pos] = cand; return # CP B / JR c -> store cand  ($AA45)
  bounce:
     mem[vel] = -mem[vel]              # NEG / LD (DE),A  ($AA43)
     mem[pos] = mem[pos] + mem[vel]    # ADD A,(HL)
     store mem[pos]                     # LD (HL),A       ($AA45)
```

Disassembly (`$AA0E`, byte-verified):
```
AA0E CD DA A9   CALL $A9DA          ; erase old
AA11 11 47 AA   LD DE,$AA47         ; dx
AA14 21 DB A8   LD HL,$A8DB         ; X tile
AA17 01 02 1B   LD BC,$1B02         ; hi=27, lo=2   X limits
AA1A CD 38 AA   CALL $AA38
AA1D 11 48 AA   LD DE,$AA48         ; dy
AA20 21 39 A8   LD HL,$A839         ; Y tile
AA23 01 03 14   LD BC,$1403         ; hi=20, lo=3   Y limits
AA26 CD 38 AA   CALL $AA38
AA29 CD C1 A8   CALL $A8C1          ; draw
AA2C CD 69 A9   CALL $A969          ; boss<->player
AA2F D0         RET NC
AA30 DD CB 5A 56 BIT 2,(IX+$5A)
AA34 C0         RET NZ
AA35 C3 7D 92   JP $927D            ; hurt player
```
```
AA38 1A     LD A,(DE)   ; velocity
AA39 86     ADD A,(HL)  ; cand = vel + pos
AA3A B9     CP C        ; < lo ?
AA3B 38 03  JR C,$AA40
AA3D B8     CP B        ; < hi ?
AA3E 38 05  JR C,$AA45  ; in [lo,hi) -> store cand
AA40 1A     LD A,(DE)   ; bounce:
AA41 ED 44  NEG
AA43 12     LD (DE),A   ; store flipped velocity
AA44 86     ADD A,(HL)  ; reflect
AA45 77     LD (HL),A   ; store new tile  <-- BOTH axes
AA46 C9     RET
AA47 01 FF  (data) dx=$01  dy=$FF
```

**Key properties (all MEASURED):**
- **Limits are hard-coded screen edges** in the `BC` constants — NOT read from platform/shadow geometry. `hi` (B) is **exclusive**, `lo` (C) inclusive: valid tile range `[lo, hi)` → X turns at 26, Y at 19; low side turns at X=2, Y=3. It **reflects**, never storing the wall value.
- **Platform-ignorance CONFIRMED:** static scan of the whole boss region `$A800–$AA60` found **zero** `LD A,(F8xx)`, **zero** `AND $20`, **zero** `BIT 5,r`. The boss bounces off the screen sides/top/bottom only, ignoring all platform geometry (matches the user's report).
- **Strictly diagonal:** both axes always step together. Over 300 frames: 90 X-steps + 90 Y-steps, all on the same frames (0 X-only, 0 Y-only).
- **Cadence:** one tile-step per axis every **~3.33 frames** (phase counter advances ~10–12/frame mod 32; body fires on wrap). Screen speed ≈ 8 px / 3.33 f ≈ **2.4 px/frame per axis**, diagonal.
- **Causal bounce test** (poke onto each wall): right `(26,+1)→(25,−1)`; left `(2,−1)→(3,+1)`; bottom `(Y19,+1)→(18,−1)`; top `(Y3,−1)→(4,+1)`. All four walls reflect exactly as `$AA38` predicts.
- Velocity magnitude is `±1` in every observed state; no code was found that sets `|dx|/|dy| ≠ 1` (immutability not exhaustively proven — see OPEN).

---

### (b) Sprite / rendering

**Sprite** is **32×32 monochrome** (4 bytes wide × 8 pixel-rows × 4 tile-rows = 128 bytes). The `$A8C1` blitter's source operand `$A8C2` is SHARED between the boss and the 32×32 GIANT ITEMS; it is set only by `$A84D`, keyed off the giant-item mailbox `$FECC` (CORRECTED 2026-09-09 — these are NOT boss poses):

| Addr | Frame | Selected when |
|---|---|---|
| `$FE02` | **the boss** (green face) — the ONLY frame the boss ever uses | `$A84D` input A ∉ {1,3} (boss spawn calls it with A=4) |
| `$C080` | GIANT FRUIT / peach (a giant ITEM, not the boss) -- drawn live CONFIRMED 2026-09-09 (`$A8C1` fired with src `$C080`, `peach_spawn-in.szx`) | mailbox `$FECC`==3 |
| `$5B00` | GIANT DIAMOND (a giant ITEM, not the boss) | mailbox `$FECC`==1 |

**The boss is SINGLE-FRAME (MEASURED, corrects the earlier "alt-pose/burst" reading).** `$A84D` selects the source from `A` (via a self-modified `LD A,n` at `$A85B` whose operand byte IS `$A85C`, written to `A−1` at `$A84E`; the static image shows `LD A,3` but it is rewritten each call). h.call `$A84D` with A=1→`$5B00`, A=3→`$C080`, A=4→`$FE02`. The boss spawn (`$A9F3`) always passes **A=4 → `$FE02`**, and `$FECC` is set to 1/3 ONLY by the giant power-up handlers `$88F9`/`$88FD` (candy-cane→giant) on NORMAL levels — never during the boss fight (`$A9CF` only *clears* `$FECC` on giant-collect). So on round 80 the boss is `$FE02` throughout; the `$C080`/`$5B00` rows belong to the giant-item mechanic (see "Giant items").

**Draw routine `$A8C1`** blits to the **display file**, self-modifying its X:
```
A8C1 11 02 FE   LD DE,$FE02     ; source operand @A8C2 = current frame (default $FE02)
A8C4 3A 39 A8   LD A,($A839)    ; Y tile
A8C7 87 4F      ADD A,A / LD C,A
A8CB DD 21 00 FD LD IX,$FD00     ; IX = row-addr table + 2*Ytile
A8CF DD 09      ADD IX,BC
...
A8DA 01 18 00   LD BC,nn        ; operand byte @A8DB == boss X tile (self-modified)
A8DD 09         ADD HL,BC       ; dest = rowbase + Xtile
A8E1 ED A0      LDI x4 / DEC E x4 / INC D   ; copy 4 bytes (32px) per scanline, 8 rows
A8F3 DD 23 DD 23 INC IX x2       ; next char-row addr; loop 4 tile-rows
```
- Dest = `$FD00` row-address table `[2 * Ytile]` + Xtile. X **is** the `LD BC` operand at `$A8DB` (self-modified), so movement drives the blit column directly (MEASURED by single-stepping: 128 LDI, src `$FE02..$FE81`, dest cols = Xtile, row-hi `$48..$4F`).
- **The draw routine also paints the boss ATTRIBUTES.** It falls through past the bitmap loop into `$A902–$A924`: `H = ((D−1)>>3)&3 | $58` (attribute file `$5800–$5AFF`), `LDD x4` across 4 rows. The boss's green colour is painted by the draw routine itself, not only by the level map. *(Corrects the render facet's open question #3.)*

**Erase / restore.** `$A9DA` (driver: C=Ytile, B=4, loops 4 rows) → `$A929`: computes shadow source `$A000 + screenaddr` (= the `$E000`-region background shadow), copies 32×8 clean background back to the display, then attribute fixup at `$A951` reads `$A000+$58xx` (the `$F800` clean-attr region) and writes `$5800` via `$9D4C`. So `$F800`/`$E000` shadows are **read** to restore the background; the boss body itself is drawn to the display file.

**Animation.** None in normal play. MEASURED: watching `$FE02–$FE82` and the source operand `$A8C2` for 600–1200 frames in **both** states — zero bitmap writes, zero operand writes, `$A8C2` stayed `$FE02` throughout. The boss only *moves*; it does not animate per-pixel or swap frames during wandering or during a bolt hit. Forcing `$A8C2=$C080` did change the on-screen pose, confirming the selectable-source path is real.

**Frame-select `$A84D`** (called only from `$8F26`, the mailbox consumer `$8F1A` that reads/clears `$FECC`, OR directly from the boss spawn `$A9F9` with A=4): `A−1 → $A85C` (self-modifies the `LD A,n` at `$A85B`), then `C = A−1`; `C==0 → $5B00`, `C==2 → $C080`, else `→ $FE02`; writes the draw operand `$A8C2`; snaps X=14, Y=3. So input A: 1→diamond, 3→fruit, 4→boss (MEASURED via h.call). The GIANT mailbox `$FECC` is set to 1/3 only by the giant power-up handlers `$88F9`/`$88FD` (candy-cane→giant, normal levels); the boss spawn passes A=4. So `$A8C2`=`$FE02` throughout the boss fight — this routine is really the giant-item frame selector, not a boss animator.

> **Refuted render-facet claims (do NOT assert):** `$A969` is **not** bolt collision — it is boss↔**player** overlap (reads player slots `$FD80`/`$FD8A`, IX+5/+6/+7) and on carry drives `$927D` player-damage. `$A9B1` is a **second player-collision reaction**, not a bolt/death handler. The `$A9EA` table is **`[$40,$20,$10]`** (3 bytes; the following `$3A` is the `LD A,($8609)` opcode), indexed by **phase−2** via `$A85C`.

---

### (c) Lifecycle / state machine

Round 80 (`$8609 == $50`) is **the** boss fight. Round 81 (`$51`) is a **distinct final room, not a second boss form**.

**Dispatch.** The boss tick `$A9ED` is CALLed every main-loop iteration from **`$8D2E`** (MEASURED: at `$AA0E`, stack-top return = `$8D31`, SP=`$96D9`). The death check `$8E3A` is CALLed from `$8D5E`; its `A==0` return drives `$8D61 JR z,$8D09` (level complete).

**Spawn `$A84D`.** On the first boss-round frame `$A839` (Y tile) == 0, so `$A9F3..$A9F9 JP z,$A84D` places the boss at X=14 (`$A853`), Y=3 (`$A858`). Velocities default to dx=+1 (`$AA47`), dy=−1 (`$AA48`). Spawn does **not** write HP. *(Spawn confirmed by the tick-entry gate + disasm; not dynamically forced — both saved states already have the boss spawned.)*

**HP — 20 vs 42 (RESOLVED, MEASURED).** Boss HP lives at **`$9F62`**.
- Layout path `$79A2`: `LD A,10 / RLCA (=$14=20) / LD ($79A3),A / LD ($9F62),A` → seeds **20**.
- Arena setup `$98AD`: `LD A,$2A / LD ($FEC5),A / LD ($9F62),A` → sets **42**.
- MEASURED across the round-intro rebuild: writes occur in order — `$14` at PC `$79A8`, **then** `$2A` at PC `$98B2`. **Effective start HP = 42.** The `20` and `$79A3` are vestigial: `$79A3` has no reader anywhere in the 64K image (only the write `$79A6` and a false-positive at `$A32C`).
- HP is **never auto-restored** during play (0 writes to `$9F62` in a passive 120-frame run).

**Per-frame tick** (round-80 gated): spawn-if-Y0 → pause gate (`$8DBD − $37 == 0` skips) → frame divider (`$AA05`, one tile-step per 32 iters) → erase → bounce X → bounce Y → draw → player-collision. Inert on round 81 (`RET NZ` at `$A9F2`).

**Death check `$8E3A`** (three gates then the HP test):
```
8E3A LD A,0 / OR A / JP nz,$8F29     ; gate1: self-mod byte @$8E3B (0 => pass)
8E40 LD A,($FED1) / OR A / JP nz,$8F36 ; gate2: $FED1 must be 0
8E47 LD A,($8609) / CP $50 / JR nz,$8EAA ; gate3: boss round
8E4E LD A,($9F62) / DEC A / JP p,$8ECC  ; alive while HP>=1; HP==0 falls through to death
```
Upstream loop gates that must pass to even reach `$8E3A`: `$8D0D` (`$FEC9==0`) and `$8D12` (`$FECD==0`).

**Death sequence `$8E55`:** `DI; LD A,$10; LD ($FFEF),A` (death signal); `IX=$FD80`; `RES 7,(IX+$5A)/(IX+$64)`; `CALL $80FA` (explosion/sound, A from `$9F09`); clear `$FEC4/$FEC5`; `EI`; draw defeat graphic (`IX=$9A27 → screen $484B`, B=11, via `$8E9D`); three `CALL $9573` delays; `XOR A; RET`. The `A=0` return → `$8D61 JR z` → `$8D09 CALL $97F8` → round advances to 81.

**Round advance `$97F8`:** `INC ($8609)`. If the result would be `$52` (past round 81) it loads a random pending round instead: `LD A,R / AND $1F / ADD $1E` → rounds **30–61** (`$9809/$9811`). MEASURED: after a HP=0 death, `$8609` took a single write of `$51` at PC `$97FC`; there is **no ending sequence** — the game loops.

**Boss SPAWN -- MEASURED LIVE 2026-09-10 (`boss_spawn.szx`, captured at "ROUND 80 READY!").** The
boss is a DEDICATED struct (not an `$FD80` slot); it is absent through the READY hold (f0-40), then
**pops in whole at f41** -- the giant/boss blitter `$A8C1` reads the `$FE02` mailbox and draws it at
the TOP-CENTRE in a single frame (no fade/slide entrance), after which it descends into its patrol
(top at f42, lower-centre by f200). The round pre-places a BLUE BOTTLE (lightning-blow power-up) on a
left platform -- the only weapon that damages the boss. This confirms the predicted single-frame
pop-in and closes the "boss spawn transition" item.

**Boss DEATH + ENDING -- MEASURED LIVE 2026-09-10 (`boss_killed.szx`, HP=1 with a bolt in flight).**
- The bolt hits at f2: HP `1 -> 0`, score `56792 -> 156892` = **+100000** (`$8E6A CALL $80FA`).
- The **"WELL DONE!"** message draws immediately at **row 10, cols ~11-21**, attribute `$C5` =
  BRIGHT + FLASH, ink 5 (flashing cyan on black), alongside the defeat graphic `$8E9D` (the boss
  shown surrounded by lightning bolts). It holds on round 80 for ~345 frames.
- **Round advances 80 -> 81 (`$50 -> $51`) at f347.** Round 81 = the FINALE / TREASURE ROOM: **25
  collectibles, ALL type 9 = DIAMOND**, on magenta/yellow striped platforms. Each diamond collects
  for **+1000 internal = +10,000 on screen** (`$8649[9]=$1000`), so the room is worth up to ~250,000.
  MEASURED: teleporting the player onto a diamond scored +1000. (Same type-9 diamond the red-cross /
  water / fire kills drop -- the finale just pre-places 25 of them.)

**ENDGAME LOOP -- MEASURED LIVE 2026-09-10 (`last_diamond_81.szx` / `last_diamond_82.szx`).** The
treasure room REPEATS and then drops into a mid-game level -- an endless second quest, driven by the
return-round lookahead `$FEC7` and the round-advance `$97F8`:
- Beating the boss (round 80) runs `$97F8` with `$8609` passing through `$51`, which RESEEDS `$FEC7`
  randomly: `$9811 LD A,R / AND $1F / ADD $1E` = a level in **30-61**.
- Clearing a treasure room runs `$97F8` again: `$8609` `$51 -> $52`, `CP $52` hits -> `$9806
  $8609 = $FEC7` (the return level), then `$9817 $FEC7 += 1`. The 21/41/61 milestone check
  (`$981A CP $15/$29/$3D`) on the NEW `$FEC7`: if it lands on a milestone AND the player has not
  died, the no-death-warp code `$9846` forces `$8609 = $51` = ANOTHER treasure room; otherwise
  `$8609` stays = the return level and normal play resumes there.
- Each rebuild bumps the palette (build counter `$82D7`), so the repeated room is RECOLOURED
  (identical layout + 25 diamonds, different platform colours -- the player's "round 82").
- MEASURED (this seed): `$FEC7`=`$28`(40) room -> clear -> `$FEC7`->`$29`(41, a milestone) -> warp
  back to `$51` (2nd treasure room, palette `$82D7` 6->7, magenta->green); `$FEC7`=`$29`(41) room ->
  clear -> `$8609`=`$29`=41, `$FEC7`->`$2A`(42, not a milestone) -> play round 41. So the owner's
  "81 -> 82 -> 41" is exactly this run's `$FEC7` sequence; the number of treasure rooms and the
  return level are `LD A,R`-seeded (they vary with timing), but the loop mechanism is fixed.

**Round 81 is not a moving boss (MEASURED):** forcing `$8609=$51` produced 0 stores from `$AA45` (tick round-gated off); any position change came from the repurposed item logic (`$A824`, PC `$A83F`), not the boss writer. Rendered round 81 is a distinct striped room with no boss.

---

### (d) Damage model — CAUSAL results

The **only** weapon that damages the boss is the lightning bolt (round is armed `$7E0E=3`, lightning-only). Bolt objects: slot 0 `$FDEE`, slot 1 `$FDF8`; layout `+5` = X pixel, `+6` = Y pixel, `+7` bit7 = ACTIVE, sprite `$A37D`.

**Dispatch.** `$9E50` (CALLed from `$8D40`) does its preamble/cooldown, then on the boss round at **`$9E85`** loads `IY=$FDEE`, `CALL $9E90`, `IY=$FDF8`, and falls through into `$9E90` again (so slot 1 runs inline — *correction to the facet's "two CALLs"*). `$9E90`: `BIT 7,(IY+7) / RET z` (active gate) → physics `$A314` → on boss round `JP $9F29`.

**Collision + damage `$9F29`** (byte-verified):
```
9F2D FD 7E 05   LD A,(IY+5)     ; bolt X pixel
9F30 CD 5C 9F   CALL $9F5C      ; ->tileX  (RRA RRA RRA / AND $1F = (A>>3)&$1F)
9F33 21 DB A8   LD HL,$A8DB     ; boss X tile
9F36 BE         CP (HL)         ; bossX == boltTileX ?
9F37 28 04      JR z,$9F3D
9F39 C6 03      ADD A,3         ; boltTileX + 3
9F3B BE C0      CP (HL) / RET nz ; else NO HIT
9F3D FD 7E 06   LD A,(IY+6)     ; bolt Y pixel -> tileY
9F46 3C BE 28 07 INC A / CP(HL) / JR z   ; boltTileY+1
9F4A 3C BE 28 03 INC A / CP(HL) / JR z   ; +2
9F4E 3C BE      INC A / CP(HL)           ; +3
9F50 C0         RET nz          ; else NO HIT
9F51 37 08      SCF / EX AF,AF'
9F53 21 62 9F   LD HL,$9F62     ; boss HP
9F56 35         DEC (HL)        ; *** HP -= 1 *** (sole decrement)
9F57 21 E7 9E   LD HL,$9EE7 / EX (SP),HL / RET  ; route to on-hit handler
```

**Collision box (MEASURED, 13-case parametric map against the boss's collision-time tile (25,8)):**
- X hits at **exactly two discrete columns**: `boltTileX` and `boltTileX+3` — a 1-tile gap at +1/+2 **misses** (not a contiguous 0..3 box).
- Y hits the **contiguous three rows** `boltTileY+{1,2,3}`; `+0` and `+4` miss.
- HITs at bolt (25,7)(25,6)(25,5)(22,7)(22,5); MISSes at (25,8),(25,4),(24,7),(23,7),(21,7).

**Per-hit magnitude (CAUSAL):** every hit decrements exactly **−1** at `$9F56` (HP 42→41; broad write-watch logged the single write PC `$9F56`). **"Hits hard" is two bolts:** two active bolts overlapping the boss in one dispatch cycle = two independent `$9F56` decrements = **−2/cycle** (measured max). There is **no knockback and no stun** — a hit leaves `$A8DB/$A839` and the bolt flags unchanged.

**Sole-writer proof (MEASURED):** a byte-grep of the full 64K image for `$9F62` references returns exactly **four**: init write `$79A8`, death read `$8E4E`, set-42 write `$98B2`, and the `LD HL,$9F62` for the DEC at `$9F53`. No other writer, no decrement, no auto-restore path — no contact/bubble HP path exists.

**Death-at-0 (CAUSAL, RESOLVES the earlier OPEN):**
- `$8E4E`: `LD A,($9F62); DEC A; JP p,$8ECC`. HP=1 → DEC→0 (positive) → `$8ECC` **alive**; HP=0 → DEC→`$FF` (sign set) → falls to death `$8E55`.
- Poke `$9F62=1` → `$8E55` NOT reached (alive). Poke `$9F62=0` → `$8E55` reached; stepping past `$8E58` sets `$FFEF=$10`. **Death fires passively too:** poke 0 + `run_frames(6)` logged `$FFEF` 0→`$10` at PC `$8E58`, then consumed to 0 by `$8167` within ~1 frame. (The prior "death did not fire passively" note was a late poll seeing the consumed value; contradicted here.)
- Gates confirmed: poke HP=0 **and** `$FED1=1` → no death (diverts to `$8F36`); poke HP=0 **and** `[$8E3B]=1` → no death (diverts to `$8F29`).
- **Kill award (CAUSAL, N13):** death routes `$8E58 ($FFEF=$10)` → `$8E5F` (killer index `$9F09`) → `$8E6A CALL $80FA` = **+100000 to the killer** (MEASURED P1 `00045584`→`00145584`), then `$8E9D` draws the defeat graphic `$9A27`→`$484B`. (Each lightning HIT separately awards +100 via `$9EE7`→`$9F01`.)

---

### OPEN ITEMS

1. **Frame-switch (`$C080`/`$5B00`) — RESOLVED 2026-09-09: these are NOT boss frames.** `$A84D` maps the giant-item mailbox `$FECC` (1→`$5B00` giant DIAMOND, 3→`$C080` giant FRUIT, else `$FE02` boss); h.call `$A84D` with A=1/3/4 confirmed. `$FECC`=1/3 is set only by the giant power-up handlers `$88F9`/`$88FD` on NORMAL levels; the boss spawn passes A=4→`$FE02`, and `$A9CF` only *clears* `$FECC` on giant-collect. So the boss is single-frame `$FE02` and there is no boss alt-pose/burst. The remaining open item is the giant-item ON-SCREEN draw path (`$5B00`/`$C080` via `$A8C1` vs the `$A280` tile route) — tracked under the bucket-B "giant on-screen" capture, not here.
2. **Velocity immutability — RESOLVED (N9).** A full-image grep for references to `$AA47`/`$AA48`
   returns EXACTLY ONE each (operands at `$AA12`/`$AA1E`, instructions `$AA11`/`$AA1D`), both feeding
   the bounce `$AA38` whose sole writer `$AA43` NEGs; spawn `$A84D` leaves them untouched; live
   `$A8DB` steps only at `$AA45`. So `|dx|=|dy|=1` is IMMUTABLE — no HP-tied rage/speed-up exists.
3. **`$9840 BIT 7,(IX+7)` force-to-round-81 — RESOLVED (N10).** This is the tail of the
   round-advance `$97F8` (from `$8D09`, reached by fall-through). `$9811 LD A,R` picks a random
   30-61; the 21/41/61 milestones `$981A`/`$981E`/`$9822`; then `$9840 BIT 7,(IX+7)` on a LIVE
   player struct -> `LD A,$51 / LD ($8609),A` (byte-verified: `DD CB 07 7E / 3E 51 / 32 09 86`).
4. **Movement `$8DBD` pause gate — RESOLVED (N11).** `$8DBD` = the hurry-up play timer (+1/frame,
   zeroed `$916D`). The boss stall gate `$A9FC` (`LD A,($8DBD) / SUB $37`) is a 1-frame cosmetic
   stall, one frame per 256. The sibling bolt gate `$9E53` uses `CP $58`.
5. **`$AA05` phase multiplicity — RESOLVED (N12).** The boss phase advances ~10.3x/frame because the
   boss tick `$A9ED` is called once per pass of the main dispatch loop `$8D0C`->`$8D70` (from
   `$8D2E`), and there are ~10 passes per 50 Hz frame (31 phase writes over 3 frames, all at
   `$AA0A`); the mod-32 divider then yields the measured ~3.33-frame movement step.
6. **Death-sequence + kill score — RESOLVED (N13, CAUSAL).** On boss death `$8E58` writes
   `$FFEF=$10`; `$8E5F` reads the killer index from `$9F09`; `$8E6A CALL $80FA` consumes `$FFED-0`
   -> **+100000 into the killer's score** (MEASURED: poke `$9F62=0` -> P1 `00045584` -> `00145584`);
   `$8161`/`$8167` clears afterward; `$8E9D` blits the defeat graphic `$9A27`->`$484B`. (Separately,
   each lightning HIT awards +100 via `$9EE7`->`$9F01`.)
7. **HP-seed ordering under a fresh pre-boss load** re-derived from the round-intro rebuild (20 then 42), but not from a state earlier than boss-entry (none available); no reader of `$9F62` exists between the two writes, so 42-wins is robust.

### Confidence per section

- **(a) Movement/bounce — HIGH** (code + runtime both verified, zero refutations; causal wall-poke and 300-frame cadence).
- **(b) Sprite/rendering — HIGH** (32×32 blit, self-mod X, display-file + attr paint, `$F800`-shadow premise disproven; and the boss is now confirmed SINGLE-FRAME `$FE02` — the `$C080`/`$5B00` "poses" are the shared-blitter giant-item sprites, OPEN #1 resolved).
- **(c) Lifecycle — HIGH** (dispatch caller, HP 20-vs-42 ordering, death-at-0, round-80/81 divergence all measured; spawn confirmed by gate+disasm not live-forced).
- **(d) Damage — HIGH** (per-hit −1, collision box, two-bolt −2, death-at-0, sole-writer, and the +100000 kill-award all causally measured; boss OPEN items #1-#6 now resolved (incl. #1: the boss is single-frame `$FE02`), only #7 remains).

## Text & font system -- MEASURED (ROM font; DECLARED DEPARTURE for the port)

The game renders ALL text with the SPECTRUM ROM CHARACTER SET at `$3C00`; it has NO custom font.
- **Printer `$802E`**: IX = a 0-terminated string (one byte/char); per char it CALLs `$8044` to
  compute the glyph address = `$3C00 + char*8` (ROM font), then `$804F` copies the 8-byte glyph to the
  screen dest (HL). `$8042` is the PRINT-DIGIT entry: `ADD A,$30` (0-9 -> ASCII) then falls into
  `$8044` -- so the SCORE DIGITS use the same ROM glyphs.
- **8 call sites** of `$802E`: `$7FE9 $7FEF $8024 $8CEE $9114 $9758 $98C4 $98D4` (front-end, HUD,
  in-game messages, boss/arena). Flashing messages come from the `$9A06` string table (ROUND/READY,
  HURRY UP `$9A1C`, GAME OVER `$9A95`, CREDIT `$9AB8`).
- **HUD**: header strings "1UP" `$85C5`, "HIGH SCORE" `$85CC`, "2UP" `$85DA` printed via `$802E`;
  score digits via `$8042`. CORRECTED 2026-09-08 (R11): **all game text is PLAIN ASCII** (HUD
  `$85C1`; message table `$9A06-$9AB8`) -- the earlier "front-end strings are stored encoded" claim
  was WRONG (grep found no encoded/XOR/additive CHOOSE/CONTROL/KEYBOARD/JOYSTICK/KEMPSTON/SINCLAIR
  string, and the message table is all ASCII). The in-game "BUBBLE BOBBLE" appears as a letter-spaced
  ASCII string `$9A32` (`B U B B L E  B O B B L E`) printed through the ROM font. There is NO "CHOOSE
  A CONTROL"/keyboard string -- control-select is numeric/graphic. The big title-screen LOGO is a
  BITMAP, not ROM-font text (corrects the earlier "title is ROM-font" line). *(INFERRED, not proven:
  the one non-ASCII on-screen line "LICENSED BY FIREBIRD SOFTWARE" is taken to be part of a
  pre-rendered title/loading bitmap, since `$8044` is the only reference to the `$3C00` font.)*
- The ONLY game reference to the ROM font base `$3C00` is `$8044` (the `$121C` hit is inside the ROM).

**PORT IMPLICATION (DECLARED DEPARTURE):** the port must NOT ship or transcribe the Spectrum ROM font
(house rule 7 / legal position). Since the game has no custom font, the port renders text with a
SUBSTITUTE 8x8 font (a free / re-created ZX-style face), keeping the original's text CONTENT and
LAYOUT faithful; only the glyph bitmaps are substituted. => the planned `extract_font.py` is MOOT
(no game font exists to extract). The README must declare this.

## Power-ups -- the dispatch map (MEASURED from code; 6 of 16 confirmed against captured states)

The user is right that the remaining power-ups need mid-effect snapshots for their exact feel, but the
STRUCTURE is fully in the code. There is ONE special power-up slot at a time:
- **Slot `$9603`/`$9604`**: byte0 = `(X&$F8)|type` (same encoding as the `$9605` fruit table), byte1 =
  `(Y&$F8)|flags`; **`$872C`** = "power-up present" flag. Power-ups are NOT `$9605` fruit entries.
- **Collect -> dispatch** (`$87E7-$8838`): `$87EA LD A,(HL); AND 15` -> the low nibble IS the type ->
  `$87ED LD ($8828),A` (staged) -> `LD (HL),0` (slot consumed) -> `$8829 LD (IX+$61),A` records it in
  the player's `$FDE1` -> `$882C ADD A,A` indexes the 16-entry jump table **`$8839`** -> `JP (HL)`.
  - **`$8828` = a self-modified operand doing DOUBLE DUTY** (R7): it is BOTH the immediate of
    `$8827 LD A,n` (`3E 0D` in the bottle snapshot) AND the cell read by `$87FA LD A,($8828)`,
    rewritten each collect at `$87ED` with `(slot & 15)`. Its PRISTINE value is `$00` (boot / title /
    round1); the `$0E`/`$0D` seen earlier was the bottle snapshot's stale prior type, not a baked
    static. This is what caused the `$0E`-vs-`$0D` confusion.
  - **`$8639` is the power-up SPRITE-INDEX remap** (SETTLED, R6): sprite = `$5D00 + $8639[type]*32`;
    its sole consumer is the icon-draw address calc `$87A5-$87B0` (only image ref, `LD HL,$8639` at
    `$87AC`; type2->idx1->`$5D20`, type6->idx3->`$5D60`, type13->idx7->`$5DE0` all match live
    sprites). It is NOT a spawn/selection-progression table.

Player persistent struct offsets used below (entity-relative, `IX=$FD80`): `+$5A`=`$FDDA` (flags),
`+$5B`=`$FDDB` (2; type 14 sets 3, role unmeasured), `+$5E`=`$FDDE` (bubble RANGE in 8-px steps), `+$5F`=`$FDDF` (BLOW-CADENCE MASK: 7 normal = a blow every 16 frames, 3 = every 8; CORRECTED 2026-09-09 -- not a speed), `+$60`=`$FDE0` (the cadence counter), `+$61`=`$FDE1` (last pu type). Walk speed is `+7` bit 2 of the ENTITY (`$FD87`): set by types 10 and 14 = 2 px/frame instead of 1.

_**ALL 16 power-up types (0-15) MAPPED** on four axes: EFFECT (this dispatch table `$8839`, every
handler measured -- 9 via live owner snapshots, 7 via poke-collect), SPRITE (remap `$8639` -> 10
distinct glyphs `$5D00+idx*32`, all present LIVE -- idx 0/8 read blank ONLY in the post-boot
`image.bin`, the TRAPS #26 scribble), INK/colour (`$861D`, which distinguishes same-sprite types:
canes 3/4/5 = idx 2 inks 3/2/6; crosses 7/8/9 = idx 4 inks cyan/yellow/red; bottles 12/13 = idx 7),
and VALUE (`$8649`). Only two residuals: type 12's self-advance timer is PROVISIONAL, and the
poke-measured types (0/5/10/11/14/15) have their EFFECT measured but their physical in-game item is
inferred from sprite+ink rather than a dedicated snapshot._

| type | handler | effect (from code) | status |
|---|---|---|---|
| 0 | `$88EF` | `(IX+$5F)=3` -> **RAPID FIRE** (MEASURED 2026-09-09 by poke-collect on `round1_48`: the blow interval with the key pulsed drops from 16 to 8 frames; bubble speed unchanged at +8 px per 2 frames; range unchanged). `(IX+$5F)` is the blow-cadence counter MASK (7 normal, 3 rapid), NOT a speed. Value +30. | **MEASURED (poke)** |
| 1 | `$88F4` | `(IX+$5E)=$10` -> **bubble range = 16** (bubble travels 16 steps of 8 px instead of 8; MEASURED side effect: the blow interval stretches to 32 frames with the key pulsed) | **CONFIRMED** (purple sweet: `$9603=$A1`; poke 2026-09-09) |
| 2 | `$88EC` | range=$10 AND cadence mask=3 (calls 1 then 0's store) = long range + RAPID FIRE (MEASURED: 8-frame blow interval with 16-step range) | **CONFIRMED** (red lamp: `$9603=$A2`; poke 2026-09-09) -- `$FDE1=2` is only the last-type record |
| 3 | `$88F9` | `$FECC=1` -> spawn a GIANT item, source `$5B00` (via `$8F1A`->`$A84D`) | **CONFIRMED** (candy cane -> giant diamond: `$9603=$A3`) |
| 4, 5 | `$88FD` | `$FECC=3` -> spawn a GIANT item, source `$C080` (giant fruit); values +50 (type 4) / +60 (type 5) | **CONFIRMED** (type 4 red cane live; type 5 by poke 2026-09-09: `$FECC`=3, +60, nothing else) |
| 6 | `$88B1` | UMBRELLA: PRNG `AND 3` -> `$FECD` in {3,3,5,7} level warp | **CONFIRMED** (`$9603=$86`) |
| 7 | `$88C3` | `$FECE=1`, `$9049=1`, colour `$8309/$830A=$2F`, then `$88E0` (self-mods the corpse-drop type generator: `$8B9F=9`, `$8BA0`=NOP, `$8BA2`=AND $FF -> every corpse drop is type 9 = DIAMOND; shared by types 7/8/9) -> **WATER FILL** (rising flood) | **CONFIRMED** (blue cross / ice lolly: `$9603=$A7`) |
| 8 | `$88D5` | `$FECF=1` + `$88E0` (diamond-drop patch) -> **LIGHTNING STORM** (the YELLOW cross; MEASURED 2026-09-09 from `yellow_cross.szx`, round 8): `$FECF` counts +1/frame for 245 frames, driven by `$A0A3` each frame (`OUT 0` per tick); every 32 ticks (`AND $1F`=0) it paints 4 random inks (RNG `$FE85` & 3 -> black/blue/red/magenta, `(attr & $F8) | ink`) over rows 2-23 (`$A0E0`, border green) -- the last one sticks, so the platforms flicker blue/black/red/magenta; a RED ink kills every free enemy through the shared red-attribute kill check (corpse via `$8BC2`/`$8BD3`, measured: flash at tick `$A0` -> attr `$4A` -> enemy dead next frame); ticks `$F0-$FF` burst every bubble (`$A0F5`: bubble `+3`=10, `+7` bits 3\|1) so captured enemies die (+11 seen); ticks `$FD/$FE` paint the whole playfield `$42` red-on-black (border cyan/yellow, speaker on); at the wrap to 0 the playfield is repainted by `$8C28` (`$8216` + attrs from the colour shadow `$F840`). **The `$88E0` pin makes the storm-killed enemies' corpses drop type-9 DIAMONDS on landing** (CONFIRMED live 2026-09-10 via a fresh `yellow_cross.szx`: collect -> storm f1, both live enemies -> corpses by f33, 0 live by f140, corpses settle to purple diamonds f124-140; platform inks cycled black/blue/red/magenta/yellow). Collect value +90 (900 on screen). | **CONFIRMED** (`yellow_cross.szx`) |
| 9 | `$88DC` | `SET 5,($FDDA)` = FIRE MODE (blows fireballs instead of bubbles; kills via the red attr, corpses drop DIAMONDS) + `$88E0` diamond-drop pin | **CONFIRMED** (RED CROSS: `$9603=$49`; `red_cross.szx`) -- see "RED CROSS" |
| 10 | `$8859` | **HEART = round-long INVINCIBILITY** (the colour-cycling heart, sprite idx 5 `$5DA0`; CONFIRMED 2026-09-10 by the owner's description + measurement). `$FED0=1`; BOTH players `SET 3,($5A)` = INVULNERABLE. **The item COLOUR-CYCLES**: its ink `$861D[10]=$FF` -> a random ink every frame (`LD A,R` at `$873E`; measured cycle 1,3,4,7,7,2,2,7). **The player SPRITE FLASHES on/off**: while bit3 is set the player-draw returns without drawing on even draw-parity frames (`$A5E4` reads the draw-parity `$A3B2`; `$A5FB BIT 3,(IY+$5A) / RET nz`), so the sprite blinks at the ~25 Hz draw rate. **DURATION = until the round ends** (NOT a timer): the normal respawn-invuln countdown `$ABEA DEC (IY+4) -> RES 3` is SKIPPED while `$FED0=1` (`$ABE8`); `$FED0` is only cleared at the next round build. While active: CONTACT KILLS enemies (`$927D` reads `$FED0` -> corpse + 1000 on screen), the 8 shoot gates `$A891..` are refilled to `$64` every frame by `$900B` (enemies never shoot), and `SET 2,(+7)` gives temporary FAST WALK. `$8DBD=0` (hurry reset). +40 (400 on screen). | **CONFIRMED (heart)** |
| 11 | `$8883` | `$FED2=1`, the 8 per-enemy shoot-gate countdowns `$A891..` := `$FF`, hurry timer `$8DBD` := 0; +80 (800 on screen). MEASURED (poke): the gates count down (~0.5/frame) and `$901E` clears `$FED2` only when all are 0 -- the effect is "enemies cannot shoot until the countdowns expire" (nothing else moves: no walk/blow/flag change; enemies keep walking). | **MEASURED (poke)** |
| 12 | `$890D` | MEASURED 2026-09-09 by poke-collect (`round1_48`, +30): every enemy is REMOVED at once (`+7` bit 7 cleared, no corpse, no score), the ISR gates `$FEC4/$FEC5` and the elemental objects are cleared (`$A36C`), `$FED1`=1, `$9049`=1 (which DISABLES the hurry-up trigger `$9037`, so no HURRY UP/Boris follows), and a row of 4 collectibles appears at the top of the playfield (`$9605` entries: type 1 at X=32/64/96/128, Y=32; they stay put); the normal spawn-in item still arrives at entry 0 (f250). The round then ADVANCES by itself 2040 frames (~41 s) after the collect (timer-driven through the `$FED1` branch `$8E40 -> $8F36`, mechanism not decoded -- PROVISIONAL). A LEVEL SKIP / bonus item, not an effects reset. **M7.115d (2026-10-09, `tools/potion.py`, through play on the real load):** the gates are shut only for the arm: `$894B CALL $8C14` RES 7s the seven enemy and twelve bubble slots and repaints the playfield (DI `$8C14`..`$8C4C`: four ISRs lost), the fill `$8950` lays the room (six rows of seven, up to 31 entries), and its tail `$898F LD A,4 / CALL $8E05 / $8994 LD A,1 / LD ($FEC4),A / LD ($FEC5),A / EI / RET` OPENS BOTH -- the player walks and takes the items (the table-full exit `$8974 EI / RET` skips it: round 80's map). The dispatch comes one frame after the take: the award between `$87F0` and `$8822` runs past the interrupt. **M7.115e (`tools/isrcarry.py` potion sources, 125 runs):** `$890D` to its RET is ONE program, 237,047..244,659 T: `$890D DI` .. `$891D EI` (both gates shut at 8 / 21, `$A36C`'s forty stores -- the twenty into `$5B00` contended), the arm, `$8C14` at 1,404 (round 81: 1,416), the reveal with interrupts off to `$8C4C`, POP IX, the fill (its probe stores the cursor into `$89A9` every cell; 9,571..26,882 T over the treasure maps) and the tail.  A boundary 32 T before the end of the XOR A after `$891D EI` is lost, 31 T before it is taken there. | **MEASURED (poke; play M7.115d; T M7.115e)** |
| 13 | `$889C` | `SET 6,($FDDA)` and `SET 6,($FDE4)` -> **lightning-blow ability for BOTH players** | **CONFIRMED** (blue bottle: `$9603=$3D`) -- REFINES the boss note: the real ability flag is **`$FDDA` bit 6**, `$FDE1=$0D` merely records the type |
| 14 | `$88A7` | `SET 2,(IX+7)` + `(IX+$5B)=3` -> **FAST WALK** (MEASURED 2026-09-09 by poke: 20 frames of walking cover 40 px instead of 20; `+7` bit 2 = double walk speed, the same bit that makes an escaped enemy fast). Blow interval and bubble speed UNCHANGED (16 frames) -- NOT rapid fire (the fast bit only widens the blow window at `$BD3D` to counter values 1 and 2). `(IX+$5B)`=3: its bit 0 is folded into the player re-init at `$99EF` (`AND 1 / <<2 / OR $C0` -> the `+7` keep-mask), so the fast-walk bit SURVIVES the re-init at round start/respawn (default 2 clears it) = permanent shoes. +20. | **MEASURED (poke)** |
| 15 | `$88B0` | `RET` at collect (+50 = 500 on screen) -- its EFFECT lives in the blow routine: while `$FDE1==15` every bubble blown scores +50 internal = 500 on screen (`$BD56 CP 15` -> `$BD5D`); MEASURED by poke: 4 blows = +200 | **MEASURED (poke)** |

So: 6 types confirmed against captured states (1,2,3,6,7,13); types 0/4/5/14/15 are unambiguous from
the code; types 8,9,10,11,12 have their MECHANISM pinned (flags, timers, suppressions) but their item
IDENTITY and exact feel need a mid-effect snapshot each -- these are the precise targets for the
next snapshot session.

## RED CROSS (power-up type 9) = FIREBALL mode, and the PROJECTILE system -- MEASURED 2026-09-09

Snapshots `red_cross.szx` (collect by jumping) and `red_cross_fireball_kill.szx` (a fireball
mid-flight with two enemies in its row), plus an engineered hit and code reads.

- **Collect**: the red cross is power-up **type 9** (`$9603=$49`, dispatch `$8839[9]=$88DC`); its own
  value `$8649[9]=$1000` = **+1000 internal = 10,000 on screen**. The handler does **`SET 5,(IX+$5A)`**
  (`$FDDA`/`$FDE4` bit5 = FIRE MODE) then `$88E0`, which self-modifies the corpse-drop type generator
  (`$8B9F:=9`, `$8BA0` INC->NOP, `$8BA2` AND 7->AND $FF) so **every corpse drop becomes type 9 = a
  DIAMOND** (10,000). `$88E0` is shared by types 7 (water fill), 8 and 9. `$FDE1=9` records the type.
  Fire mode is lost on death (the respawn rebuilds the flag byte as bit0|bit3|bit7).
- **Blow in fire mode**: the blow routine's `$BD70 BIT 5,(IX+$5A) / JP nz,$9DD4` bypasses the bubble
  pool entirely. `$9DD4` only *requests* a fireball (`$9DDE:=1`, blowing player latched in `$9DDF`);
  the tick `$9DE1` (first call in the elemental/projectile dispatch `$9E50`, which runs every other
  frame via the `$9E5D` parity self-mod) consumes it and spawns into one of the **two PROJECTILE slots
  `$5B00` / `$5B0A`** (10-byte entity-style structs; slot 1 is recycled if both are busy unless it
  holds a player fireball) at the player's grid X/Y (Y must be in [16,178)), `+7` = active|facing
  (|bit4 for P2), **`+8 = 8` = the player-fireball KIND**, `$FEC5:=1`. The blow cadence is
  `$FDE0` (`(IX+$60)`, allowed at 1, or 2 with the type-14 rapid-fire bit).
- **Flight** (`$9BB4` kind dispatch -> `$9CF4`): the fireball erases and repaints its 2x2 attribute
  footprint with **`$42` (bright red ink)** -- that is the "red fireball" AND its hitbox -- disables
  the shot-vs-player check (`$9D8B:=RET`) and reuses the type-6 enemy's fire-breath handler `$9C4B`:
  `$9D77` steps X by **+-8 in the facing direction per 2-frame tick (4 px/frame)**, sprites
  `$6040/$6060` (facing left) or `$6080/$60A0` (facing right) alternating on `$A37C` bit1, **no
  platform stop for kind 8** (it passes through platforms), deactivates at X<16 or X>=224 (`$9D58`,
  with `$9D5C` patched to RET so a stale shooter flag is not cleared). Drawn by `$A2D5` (OR).
  MEASURED: X 64->72->80->...->224 over ~40 ticks; one run held at X=200 for ~44 frames (cause not
  chased). The fireball is NOT consumed by a kill -- it flies on and can kill several enemies.
- **Kill = attribute colour detection.** The environment-kill loop (`$9377-$93C4`, per active,
  uncaptured enemy with Y>=16) reads the enemy's attribute cells -- its own, the one below and the
  one below-right -- and a hit is `(attr & $47) == $42` (RED -- fire floor flames, red-cross fireballs, the yellow-cross
  storm flash) or `(attr & $38) == $28` (CYAN -- the blue-cross water flood); a hit CALLs the corpse spawn **`$8BC2`** from `$93D0` (MEASURED: the
  return address at both natural kills was `$93D3`). The enemy dies INSTANTLY -> corpse `$C700`,
  `+9=$FF`, launched on a random ballistic vector: it flies diagonally, **wraps off the top of the
  screen to the bottom** ("flies around"), then falls straight down and settles -> a `$9605` entry
  whose 4-bit type is **9 = DIAMOND** at the landing cell, worth 10,000 on screen if collected.
  MEASURED: engineered hit at f6 (fireball X=80 vs enemy at 88, cell-granular); natural double kill
  (slot 3 then slot 5 "straight after"), one diamond collected instantly (+1000 internal) and one
  left at (200,168), type 9. NB a type-9 entry's byte0 reads X+8 (bit3 of the type bleeds into X).
- **The ENEMY PROJECTILE system (same two slots).** Shooting enemy TYPES 1 and 5-7 use `$5B00/$5B0A`
  for their shots, `+8` = the shooter's type = the shot KIND: **1 = boulder** (`$9BE3`; sprites
  `$6000/$6020`, horizontal via `$9D77`, stops at platforms, a low-bits delay phase, releases the
  shooter's bit1 "shooting" flag on deactivation), **5 = bottle** (`$9C8C`; spinning frames
  `$60C0/$60E0/$6100` from `$A37C`; on hitting a platform it reverses ONCE (`SET 2` + flip facing) and
  vanishes when it returns to its launch X `(IY+9)` -- the Drunk's boomerang bottle), **6 = fire
  breath** (`$9C4B`; the `$6040-$60A0` fire art, stops at platforms), **7 = a falling shot** (`$9CDC`;
  `+8` px/tick straight down, sprite `$6140`, dies below Y=192). Spawner `$9AFC` (every other frame,
  `$9AF5` parity): for an inactive slot, `PRNG & 7` (skip on 0), a random enemy index checked against
  the live count `$AA57`, the enemy's TYPE must be 1 or >=5, and `$9B70` requires `$A891+index == 0`
  (**power-up type 10 fills `$A891..` with `$FF` = enemies stop shooting**), active and not
  captured; the shot spawns at the enemy with `+7 = $C0|facing`. Enemy shots hurt the player via
  `$9D8B/$9D8C` (grid-cell match against `$FD85/6` or `$FD8F/90`). Max two projectiles on screen.
- **Type 15 resolved on the side**: `$BD56 LD A,(IX+$61) / CP 15` -- while the last-collected
  power-up type is 15, **every bubble blown scores +50 internal = 500 on screen** (`$BD5D`).

## HUD layout -- MEASURED (round1 live + code)

All HUD text is ROM-font via `$802E` (strings) / `$8042` (digits) -- see the text/font section.
- **Round-start setup `$7FD8-$801C`**: prints the template block at **`$85C1`** -- row 0 (screen
  `$4000`): `"    1UP    HIGH SCORE    2UP"` (1UP cols 4-6, HIGH SCORE cols 11-20, 2UP cols 25-27);
  row 1 (`$4020`): `"      00   000200000       00"` (the initial digit placeholders). Then paints the
  attributes: **row 0 = 31 cells `$47`** (bright white); **row 1 = cols 0-9 `$04` GREEN (P1 score),
  col 10 gap, cols 11-20 `$02` RED (high score), col 21 gap, cols 22-31 `$05` CYAN (P2 score)**.
  CONFIRMED live in round1 byte-for-byte.
- **Scores = 8-digit BCD, 4 bytes little-endian each**: **HIGH `$FFE1-$FFE4`, P1 `$FFE5-$FFE8`, P2
  `$FFE9-$FFEC`** (base `$FFE1 + 4*player`). REFINES the earlier "P1 score = `$FFE4`" note (`$FFE4`
  is the high score's top byte, adjacent). `$80FA` (A = player 1/2) = the SCORE-ADD: adds the 4-byte
  BCD amount at `$FFED` with `DAA` (`$8110-$8121`), updates the high score by a top-down compare +
  `LDD` copy (`$812E-$814A`), then REDRAWS the digits via `$8178-$81AD` (`RLD` nibble extraction,
  two `$8042` digits per byte, consecutive columns from the pointer `$8605`). Called with `$FFED`=0 at
  round start for both players to draw the initial digits.
  - **DISPLAYED score = internal BCD x 10 (MEASURED 2026-09-09).** The HUD prints the 8 stored
    digits followed by a FIXED trailing "0" (leading zeros suppressed for P1/P2). Decoded from the
    display file against the ROM font around the giant-diamond collect: internal `00004281` shows
    as `42810`, `00009881` as `98810`; HIGH internal `00020000` shows as `000200000`. Every award is
    a multiple of 10, so the store drops that digit. This retires the old "HUD = /10" note (the
    factor was real; it had been pinned to the misread `$FFE4` byte). Consequence: every
    "internal" value in this spec is x10 on screen -- fruit types `$0010..$0090` = 100..900,
    candy cane +40 = 400, giant fruit +2000 = 20,000, giant diamond +5600 = 56,000.
- **Round number `$7F80-$7FB2`**: `$8609` / 10 -> tens (suppressed when 0) and units, each via `$8042`,
  written into the SHADOW at **`$E040`/`$E041`** (= screen row 2, cols 0-1; attr `$F840` = `$07`
  white) so the platform-restore keeps it; the two digits are also stored to **`$9A0E`/`$9A0F`** to
  fill the "ROUND xx" message. Skipped on round 81 (`CP $51`).
- **GAME OVER `$8CE7-$8CFB`**: prints `$9A95` "GAME OVER" at **`$484C`** (row 8, col 12); attrs at
  `$594C` x 9 cells = `$0E` (yellow on blue); then `HALT` and the `$FEC9` continue/game-over handling.
- **CREDIT print site (RESOLVED, N1)**: string `$9AB8` = `"CREDIT 6"\0`; printed by `$9751`
  (`LD IX,$9AB8 / LD HL,$50F7` = row 23 col 23 / `CALL $802E`) on the control-select screen (key
  poll + `DEC $FED3` follow).
- **LIVES -- RESOLVED 2026-09-09 (`death.szx`): they ARE drawn, as icons at row 23's corners by
  `$806C` (P1 from col 0 rightward, P2 from col 31 leftward), one per spare life, capped at 5 --
  see "Player death, respawn, LIVES and game over". The bucket-A note kept below was WRONG (its pixel
  scan mistook the icons for border graphics):** no dedicated life-icon HUD draw was found -- the live HUD is
  rows 0-1 (scores) only, and game-over is gated by the two player-active bits `$FD87`/`$FD91` bit7
  (`$8E2A -> $FEC9=$B4`), NOT an on-screen life counter (`$80FA` is score-add, not lives). A
  per-life icon display may not exist in this port. Needs a death/respawn snapshot to confirm
  whether/where any lives count is stored and drawn.

## M6 sound -- the 48K/128K decision, the 48K beeper layer (MEASURED 2026-09-09)

**The three "OPEN for M6" questions of the groundwork note are all settled** (TRAPS #28). The
groundwork's measurements were true but of the WRONG BRANCH: every harness play state made before
2026-09-09 (`afterctrl`, `play1p`, `play2p`, `round1`, `crowd` and everything derived from them) is on
the **128K branch**, because the M2 key script held a key during the 5-second front-end probe below.
All 32 of the owner's `.szx` snapshots are 48K-machine captures on the 48K branch (`$8DC4`=`$C9`).
New 48K-branch harness states: `afterctrl48`, `play1p48`, `round1_48`, `round1_2p48` (recipe in
docs/NOTES.md M6 outcomes). The old states stay for the M10 AY layer.

### The discriminator is a TIMING PROBE, `$FAC3` (front end, run after the control select)

```
FAC3  IM 1 / EI / HALT                 ; sync to an interrupt
FAC7  LD BC,0 / LD HL,0 / LD (FRAMES),HL / LD ($5C79),HL   ; ROM FRAMES := 0 (the IM 1 ROM ISR counts it)
FAD3  LD E,0 / LD A,$FF / LD HL,FRAMES
FADA  INC E / JR NZ,+1 / INC BC        ; BC counts blocks of 256 loop iterations
FADE  CP (HL) / JR NZ,$FADA            ; ... until FRAMES low byte == $FF (255 frames, 5.1 s)
FAE1  LD A,B / CP 7 / JR NZ,$FAEF      ; count must be $07xx
FAE6  LD A,C / CP $5E / JR Z,$FAF4 / CP $63 / JR Z,$FAF4   ; ... and exactly $075E or $0763 = 48K
FAEF  LD A,$80 / JP $FA3B              ; anything else = 128K  (A=$80)
FAF4  LD A,$30 / RET                   ; 48K  (A=$30)
```
The loop reads the contended sysvar `$5C78` every iteration, so the count depends on the ULA
contention pattern and on the ROM ISR's cost -- which is why the two accepted values exist and why
a **key held during the probe** (the ROM's KEY-SCAN/K-DECODE cost rises) or an **uncontended
simulation** breaks it. Measured in the kit harness (SkoolKit CMIOSimulator, contention ON):
`BC=$075E` (48K) with the control-select keys released before the probe starts (the front end
waits for release), `$075C` (-> 128K) with a key held through it, `$07AB` (-> 128K) uncontended.
The result A rides in A through `$F5CC JP $7274 -> JP $8CC3` (the title/attract entry, which
also prints the credit line `$F5D2` "MUSIC BY TIM FOLLIN") into `$8CC3: DI / LD SP,$96DD /
CALL $95F3`: `$95F4 EX AF,AF'` parks it, `$95F5` copies BANKM `$5B5C` -> `$9AE7`, the key tables
are copied, IM 2 is armed, and the routine falls into the decision at **`$967E`**:

```
9695  EX AF,AF' / CP $80 / JR Z,$96A5          ; A' == $80 -> 128K: keep the engine hooks
969A  LD A,$C9 / LD ($8DC4),A / LD ($8E05),A / LD ($8E0A),A   ; 48K: RET-patch the 3 sound entries
96A5  LDIR $E000..$E6A7 -> $5B00..$61A7        ; (both) front-end/work data out of the shadow area
96B0  CP $C9 / RET Z                           ; 48K: done
96B3  LDIR $E6A8..$F5BB (3860 B) -> $4000 ; OUT ($7FFD),($9AE7)|1 ; LDIR $4000 -> $C350..$D263
```
So the 128K branch copies the **AY engine** (stored on the tape at `$E6A8-$F5BB`, just below the
entry `$F5BC`; its AY-register player is the `$F3xx` code, delta `$2358`) through the screen into
**bank 1 at `$C350-$D263`** (`$CF80` = music tick, `$D167` = request; `$D1E6`/`$CFA9`/`$CFEF`
engine state) and leaves the three hooks live: ISR `$8DC4` (`DI` -> `$8DC5`: `$FED4`==1 ? music
cadence via `$8DE0` : engine tick `$8DEA`), `$8E0A` (the MUSIC request -- there are no AY effects: A = sound number
vs `$FED4`, page, `CALL $D167`, unpage), `$8E05` (wait for the engine's busy byte `$8E06` before the request).
On a flat 48K image that copy lands on the SPRITE region `$C350-$D263` (enemy banks t4/t7/t5/t2/t1,
corpse, bubble sprites) -- which is exactly what the pre-2026-09-09 harness states contain, and is
what a real 48K does if a key is held through the credits (a genuine original-game quirk: garbage
enemy sprites + silence). The sounds requested on the 128K branch -- CORRECTED 2026-10-13 by the M10 recon and
M10.0 (the first 128K harness; agent A's static model against it, 0 mismatches over 511,270 ticks; the flow on
the 48K clock, `tools/ay128flow.py`): 0 the pause's mute `$8FF3` (the unpause `$9006` re-requests the saved
sound, which restarts); 1 the in-round theme -- round 1 `$98F5 JP z,$8E05` (after 7's pass), every other round
`$98FC JP nz,$8E0A` (35 T while 1 is current); 2 EXTEND `$94D5`, the boss defeat's `$8E95` (after 3); 3 the cold
start `$8CCD`, the potion / level skip `$891A`, the boss defeat `$8E77`, `$953C` after EXTEND (after 2); 4 the
HEART `$887D`, the treasure room `$8991` (after 3); 5 the title `$8CD7` (after 3 -- the COLD START's wait, not a
round start) and GAME OVER `$8CE4`; 6 the boss theme, round 80's `$9901 JP $8E0A`; 7 the game-start tune `$97B4`.
A `$8E05` wait waits for the CURRENT sound to end a pass, then requests its own A.  Sounds 1 and 6 are reached by
TAIL JUMPS.  The engine plays music only: every beeper emitter below still sounds on a 128K.  The full record:
the section "M10 -- the 128K branch" below and docs/M10-PLAN.md section 1.

### The 48K branch: NO music, NO sound engine -- inline beeper SFX only (the faithful layer)

Census by `tools/sfxcensus.py` (every `OUT` attributed to the PC that executed it) over the owner's
48K states and the new 48K harness states; RE-MEASURED and corrected by M7.52 (`tools/beeper.py` ->
`build/beeper_fixture.json`, every emitter at its own entry and three natural runs through the
ISRs). Everything the 48K game ever puts on port `$FE`:

| Event | Site (entry) | Measured shape |
|---|---|---|
| **Item collect** (every item in the `$9603` block, both passes: the fruit/points slots 1..31 via `$8698`, the power-up slot 0 via `$86A3`, both into `$86B1` -> `$87B2`, which reaches `$881F` whenever the overlap passes) | `$881C EI` / `$881D LD C,$28` / `$881F CALL $8CB1` (the OUT is `$8CB4`; `$881F` is its only caller) | 40 OUTs `$30`/`$00` (border 0), first HIGH, last LOW; half-period `66C + 41` T for C = 40 down to 2 (2,681 -> 173 T); first OUT +35 T from `$881D`; first to last 55,653 T (0.80 frame); `$881D`..RET 55,793 T: a rising chirp.  `SLA B` is 8-bit (above C = `$80` the count wraps; B = 0 is 256 turns; the game passes only `$28`).  Interrupts ON (`$87F9 DI` .. `$881C EI`): on a natural collect ISR 452 lands between OUTs 23 and 24 and delays the rest by 1,892 T (its 1,851 T from entry to exit, plus 41).  Contended 0..26 T late over eight frame phases.  M7.115f: each edge at its OUT's place on the frame clock -- the item pass's contended waits before it, the earlier OUTs' among them -- the machine's on three takes of the real load (bb IA5); the award before it runs with interrupts OFF (`$87F9 DI` .. `$881C EI` and the `LD C,$28` after it): an interrupt whose pulse falls there is LOST (bb IA6) |
| **Jump** (every main-loop pass while the player `+9` = jump phase 1..32; skipped while the player flag byte `$FDDA`/`$FDE4` bit 2 = dying) | `$8FA5` (P1 then P2) -> `$8FAE` -> `$8FD6` | 2 cycles per pass, half-period `16E+10` T with `E = \|$B57D[phase] - 16\| + 1` = 21 (rise) .. 17 (apex) .. 13 (fall) => 346 T .. 218 T; repeats every pass (~5.9k T apart) for the whole ~48-frame arc |
| **Blow** | `$ACA5` -> `$ACAF` | one `OUT (IY+$60)*8` every 2 frames: values 8,16,24,32,40,48,56 -> speaker bit 4 = 0,1,1,0,0,1,1 (3 clicks over 14 frames); the counter is `BLOW_CADENCE` `$FDE0` itself, armed at the blow (`$ACE1`), masked by `(IY+$5F)`=7 |
| **HURRY UP!** | `$9037` -> `$9068..$9092` (`$906F`/`$9081`/`$908F`) | BLOCKING 2,963,896 T contended (42.4 frames; 2,951,094 uncontended) with both ISR gates closed (`$9052`/`$9055` .. `$90A3`/`$90A6`; the machine's ISRs inside run 447..452 T).  120 steps of `$908F OUT $10`, 13,620 T apart.  Every 32nd step (C = `$60`/`$40`/`$20`) flashes: `$906F OUT 0` 45 T after the previous `$908F`, `$995A` recolours the ten cells at `$59AB` (row 13, "HURRY UP !"), `$9081 OUT 0` 391 T later (not an edge), and the next `$908F` 14,017 T after the previous one: three LOW pulses of 13,972 T (0.2 frame) in a HIGH train.  126 OUTs, 7 edges.  First `$908F` 615,340 T after `$9037` contended (609,908 uncontended); first to last `$908F` 1,622,170 T (23.2 frames); the seven edges drift at most 152 T contended; ends HIGH |
| **EXTEND letter / bubble-score click** | `$B790` (`$B791`, `$B79E`) | `OUT 0` then `OUT $30` around the `+1` score add = one click per pop |
| **Yellow-cross storm (power-up type 8)** | `$A09A` (`$A0B0`; `$A0E0` via `$A0D8` and `$A0C8`) | one tick per change of (`$8DBD`) (`$A09D CP n`, whose operand `$A09F` rewrites): `$A0B0 OUT 0` at +92 (speaker LOW, border black).  Every 32nd tick (7 per storm) is a FLASH: four `$A0E0` OUTs at +337 + 29,088k, A = the PRNG ink 0..3 (speaker LOW, border = ink), 116,567 T.  THREE strike ticks (A = `$FD`/`$FE`/`$FF`): `$A0F5`, then `$A0E0 OUT A` at +1,375, speaker HIGH (border 5/6/7) until the next tick's `$A0B0` -- three long pulses, 95,508 and 43,435 T apart; 30,316 T; rows 2-23's attributes recoloured alongside (192 + 256 + 256 cells: `$A0ED`'s DJNZ runs from B = 0 twice).  The wrap (the count back to 0) is `$A0BE JP z,$8C28`.  255 ticks, 261.37 frames from arming to wrap in play |
| **Pause** | `$8FE7` (main loop) | SYMBOL SHIFT -> `DI`, border GREEN (`OUT 4`), spin until CAPS SHIFT, border black; the 128K branch also requests sound 0 around it.  `$8FF9 OUT 4` at +96 T from `$8FE7` and `$9003 OUT 0` at +33 T from the spin's head `$8FFB`, both speaker LOW (an edge only when the speaker was left HIGH) |
| The reveal's tail; the cold start | `$8C4E`, the end of `$8C28` (reached from `$A0BE`, `$9032` after `$9031 DI`, `$A9D7`, `$A11C`, and `$8C14` falling into it); `$960E` | `OUT 0`: speaker LOW, border black.  `$8C4E` is 213,291 T into `$8C28` (213,312 T in all; 215,514 / 215,535 on r20_48) |
| Front-end key click | `$F7D4 LD HL,$0320`, then forty `$F7DB CALL $03B5` (the ROM BEEPER) with DE = 2 and HL down 20 a call, then `$F7E7 OUT 0` | 241 OUTs (values 24/8/0), 366,456 T (5.24 frames): a rising sweep from ~527 Hz, ending LOW.  CORRECTED M7.53: the menu runs with IFF 1 -- `$F7B8`'s RST $38 enters the ROM's interrupt routine, which ends by re-enabling interrupts -- so a frame interrupt can land between BEEPER calls (at 2 of 8 frame phases every later edge is 1,205 T late); the fixture's shape is the uninterrupted one (TRAPS #228).  Front-end group 3 (a ROM dependency reproduced as a constraint, not a ROM copy) |
| Player death, enemy kill/pop, corpse landing, Boris, boss hit, walking, round clear | -- | **no sound on 48K** (0 `OUT ($FE)` over the death / fbkill / extcomp / fallcandy / peachfall / bosshit states).  CORRECTED M7.52: every `$9603`-block collect chirps (Item collect), the crown and the power-ups among them -- the old census's crown / bottle / powerup windows held no collect; the giant collect (`$A824`'s hit) ends `$A9D7 JP $8C28`, so in `$8C4E OUT 0`; the umbrella's `$A110` CALLs `$A0E0` five times (run by the port since M7.98: `umbFlash`), and the level-skip's `$894B CALL $8C14` falls into `$8C28` -- not run by the port |

The static census (M7.52, `tools/beeper.py` sites) finds 19 `OUT ($FE),A`: the fifteen of the rows
above (the jump tone's are `$8FD8`/`$8FDE`), the key click's `$F7E7` (A = 0), `$5BD1` (the loader),
`$F6B5` (A = 2) and `$F716` (A = 0); plus five hits that are operand bytes, not instructions: `$970C`
(in `$970B LD ($FED3),A`), `$9791`/`$979F`/`$9981` (`LD HL,$FED3`) and `$9962` (`LD A,($FED3)`).
`$8CB4` IS an instruction -- the chirp's OUT (the groundwork note had it as data).  The 32
`OUT (C),A` are all 128K ports: `$7FFD` paging (`$8DF2`/`$8DFE`/`$8E1A`/`$8E26`, `$96C3`/`$96D6`)
and the AY (26 in `$F318..$F4D1`, `$FFFD`/`$BFFD`).

**What the port models (decision 1, 48K-first):** the faithful sound layer is the table above, no
music engine -- every in-play emitter is built (M7.52; a main-loop OUT at or past the frame's
interrupt point is held by `mainOut` until the port's ISR has run), and the ROM-BEEPER click comes
with front-end group 3. The AY engine is the M10 layer (`$E6A8-$F5BB` on the tape; run it on `tools/harness128.py`, or on the 48K
harness with `Harness(paging=$10)` -- never on the flat image).

## M10 -- the 128K branch (MEASURED 2026-10-13: the M10 recon and M10.0)

docs/M10-PLAN.md section 1 holds the recon's full record (the engine's data grammar, the slot order, the costs on the
128K).  This section is what the M10 increments transliterate, and the oracles that hold them.  M10's machine is the
128K branch on the port's 48K clock (M10-PLAN option A): the 128K machine's own clock and contention are DECLARED.

### The machines (M10.0a)
- **The 128K**, `tools/harness128.py`: SkoolKit's contended 128K simulator (70,908-T frames, the 36-T interrupt) from
  `build/boot128.z80` (`z80.snapshot128`).  What a real 128K does: the reference for every declared difference.
- **M10's machine**, `Harness(paging=$10)` (tools/harness.py): the 48K harness plus the 128K's `$7FFD` decode (port &
  `$8002` == 0; bit 5 locks) and an AY on `$FFFD` / `$BFFD`.  The 48K frame, clock, contention and ROM stay: bank 1 and
  the AY ports are NOT contended here (both are on a 128K).
- **The 128K load's 14 bytes** (asserted from the two snapshots): `$5B5C` = `$10` (BANKM: `$95F5` copies it to `$9AE7`,
  and the hooks page with `($9AE7)|1` = `$11` and back with `$10`; the 48K load's 0 would page bank 1 / bank 0 wrong),
  `$6000` = `$10` (the loader's copy), and twelve system variables in `$5C0A..$5CC8` -- REPPER `$5C0A` = 2 (the 48K
  load's 5) is the one that shows: the front end's key repeat (the ROM's KEYBOARD reads it; the engine's
  `BB_MENU.REPPER` is the 48K's).  The 128K load's R (23, the 48K's 11) is a register, not laid.
- **The probe's answer**: forced to `$80` the way the machine reaches it -- BC := `$0759` (the 128K's count) at `$FAE1`,
  so the machine's own compare takes `$FAEF LD A,$80 / JP $FA3B` and the 128K exit's trampoline T.

### The engine in bank 1 (M10.0b: tools/ayengine.py -> build/pending/ayengine_fixture.json, M10.1's gate)
- The cold start's 128K leg (`$96B3..$96D8`) copies the tape's `$E6A8..$F5BB` through the display file into bank 1 at
  `$C350..$D263` (3,860 bytes; the rest of bank 1 zero) and leaves bank 0's sprites at `$C350..` alone.  Bank 1 is
  identical on both machines (all 16K, asserted).
- Two entries.  `$D167`, the REQUEST: A = the sound; 1..7 load the slots' pointers, write no AY register and return
  A = 1 in 428 T; 0 writes R7 := `$3F` (every tone and noise off) and nothing else, 89 T.  `$CF80`, the TICK: the idle
  tick (no slot's counter runs out) 116 T and no write; the largest 2,853 T (sound 5's first); A = 1 on the tick that
  ends a pass, else 0.  Both uncontended on M10's machine (asserted: the plain simulator at another phase identical).
- A fresh engine's pointers are all 0: ticked with no sound loaded (or after request 0 alone) its counters run out at
  tick 256 and slot C reads `$0000` -- the ROM (`$CF8C`).  The game never does it (a request always precedes a
  fetching tick); the port must refuse it, never read a ROM it does not ship.  The oracle stops a stream there and
  records the address only (TRAPS #341).

### Where the game calls it, and what it does around it (M10.0c: tools/ay128flow.py -> build/pending/ay128flow_fixture.json)
- **The hooks** (live on the 128K branch, `$C9` on the 48K):
  - `$8DC4`, at the end of EVERY frame interrupt (`$8D8F CALL $8DC4`), whatever the ISR's gates: when `$FED4` (the
    last sound REQUESTED) is not 1, or the HURRY UP latch `$904D` is set, or `($8DB7)` >= 3 with exactly seven enemies
    alive (`$FECA` == 7): tick; else the cadence counter `$8DE0` (2 -> 1 tick, 1 -> 3 skip, 3 -> 2 tick): 2 frames in 3.
    The tick's A goes to `$8E06`, the busy byte (`$8E05`'s operand).  Paged in and out by two OUT (`$7FFD`).
  - `$8E0A`, the request: `LD HL,$FED4 / CP (HL) / LD (HL),A / RET z` (35 T when the sound is current), then `$8E10 DI`,
    page bank 1, `CALL $D167`, unpage, `$8E28 EI / RET`.  It leaves A = `$10`, BC = `$7FFD` (live at `$8CD2`'s and
    `$8E98`'s delays: 3,967 DJNZ for the 48K's 768 at `$9575`).
  - `$8E05`, the wait: `LD C,(busy) / DEC C / JR nz,$8E05` (23 T a turn) until the busy byte is 1 -- the CURRENT sound
    ended a pass -- then it falls into `$8E0A` with its own A.  The main line is blocked; the ISRs run.  A wait counts
    TICKS: an interrupt lost to a DI window lengthens it.
- **The waits on the 48K clock**: the cold start's `$8CD7` 81 frames (348..429 on the real load); round 1's `$98F5`
  223 frames (1P; 221 2P) -- the player walks, the enemies (the main loop's) stand, the round's timers run; the
  treasure room's `$8991` 82; `$953C` after EXTEND 182; the boss defeat's `$8E8A` 82 (its own request a no-op) and
  `$8E95` 11.  After the defeat, round 81: `$98FC`'s 1, then `$891A`'s 3 and the treasure room's wait and 4.
- **The cadence**: the theme ticks exactly 2 in 3 (p1: 546 ticks, 273 skips); full rate under HURRY UP and the alive-7
  rule; every other sound ticks every interrupt.
- **The hook's T per ISR on the 48K clock**: a theme tick ~617 T (383..2,549), a theme skip 150..172, a full-rate tick
  ~410..490 (291..3,028; 3,028 = sound 5's first tick 2,853 + the hook's 175): ~464 T an ISR under the theme.  So every
  later pass of the ON path moves: M10's gates come from the M10 oracles, the 48K gates stay for OFF.
- **A taken request with the interrupts on is a DI window**: `$8E10 DI .. $8E29 RET`, 548 T on the 48K clock.  The
  frame's interrupt is taken when the boundary falls at or before the DI's first T, LOST 1..516 T in, and taken at the
  window's end from 517 (`di_window`: FORCED, only the clock moved, 1 T steps at both edges).
- **The cold start's wait depends on the hand-over's phase.**  Request 3 does not touch the busy byte, so `$8CD7` waits
  only if a tick fell between the request and the wait -- inside `$8CD2`'s `$9575` delay (51,763 T with the request's
  B = `$7F`).  The probe's own hand-over is pinned at phase 1,051 (its HALT and the FRAMES count) and waits.  The page's
  skipProbe hands over at the CLS's end, wherever the player's keys left it: at 19 of 64 phases (27,300..46,956) no
  tick falls in the delay, 3 is replaced by 5 at once and the title comes 4 frames on instead of 85 (`skip_sweep`).

### The engine in JS (M10.1: web/game.js `BB_AY`, `BB_Ay`, `bbAyBytes`; bb.test.js AE1..AE7) -- NOT WIRED until M10.2
- **Its bytes**: the shipped asset `aybytes` = build/ay_engine.json (`tools/extract_ayengine.py extract | verify`): the
  tape's `$E6A8..$F5BB`, 3,860 bytes, asserted equal to bank 1 after the game's own leg on M10's machine (at `$C350`, zero
  elsewhere, all 16K) and that bank's SHA-1 to the oracle fixture's (`0b045e9f...`).  `bbAyBytes(A)` decodes them;
  `BB_Ay.bank1(bytes)` builds the bank the leg leaves.  M10.2's leg will lay the same bytes through the display file.
- **The engine is `new BB_Ay(bank)` over a 16K `Uint8Array`, bank 1 itself** (`$C000..$FFFF`; M10.2's game owns it), and
  ALL its state is in that bank's bytes, as on the machine: per slot the counter, loop count, flag and shape (each the
  operand of an `LD A,n`) and the pointer (`LD HL,nn`), and the six words `$D1E2..$D1ED` -- `BB_AY.SLOTS` names them, in
  the tick's order C (the master), A, B.  No JS-side state but the counters `info()` reports.
- **`request(n)`** (`$D167`) and **`tick()`** (`$CF80`) return `{ writes: [[reg, val, dt], ...], a, t }`: the writes in
  order, `dt` the `OUT ($BFFD)`'s first T from the entry; `a` the A the routine returns (a tick's busy byte, 1 on the
  master's END); `t` uncontended, the RET counted.  Written instruction for instruction, each instruction's own T, so the
  path sums come out of them: idle 116; a lone note on A or B 393, on the master 410 (R4 at 210, R5 at 268), retriggered
  468 (R13 at 213); an END tick 299 or 384 (the counter's 34, LD HL's 10, the fetch's 30 and the restart's 225, and any
  commands before the `$FF`); the request 428, request 0 89 (R7 := `$3F` at 67, A = `$3F`).
- **A fetch below `$C000` is a COUNTED REFUSAL** (TRAPS #304, #341, #344): HL is sixteen bits, so a fetch past `$FFFF`
  reads `$0000`; anything below bank 1 -- the ROM, or banks 5 and 2, which the engine never reads -- refuses the TICK:
  every store the call made is put back from its undo record, last first, and the tick returns `{ writes: [], a: 0, t: 0,
  refused: { tick, slot, addr } }`, counted in `info()`.  Never a ROM read, never a throw.  Only a never-requested engine
  reaches it (tick 256, slot C, `$0000`), which the game never does.  A request cannot refuse: its table's twelve bytes
  are in bank 1 for any A (`$D1EE + 255 + 11 < $10000`; the offset is `12(A - 1) MOD 256`, the four ADD As eight bits).
- **Measured by its gate**: the 13 oracle streams event for event (47,338 events: 86,844 ticks, 248 requests, 101,905
  writes, every `dt`, A and T), every stream's 16K at its end, the refusal at tick 256 with the state the oracle stops at,
  and the boundary -- the calls write 29 bank bytes, all state; `$CFFF`, the master's shape, is never written (the
  master's data has no R13: its 4,880 retriggered notes write shape 0).  54 ms for all 13 streams.

### The cold start and the hand-over in the engine (M10.2a: web/game.js `BB_M128`, `bbColdT128`, `bbIo7ffd`, `m128`, `hand128*`, `soundHook`; bb.test.js H1..H7)
- **`m128`** (BB_Game's, default OFF, OFF in every other gate; the page's switch is M10.3's) makes the machine M10's.  Set
  before `ctrlBoot()` / `reset()`: `reset()` then lays the 128K load's 14 bytes (`BB_M128.LOAD`, the flow fixture's
  `bytes128`) and the hooks' operands at their tape values (`SEED`: the busy byte `$8E06` = 1, the cadence `$8DE0` = 2 --
  the 48K RET-patches the hooks and never reads them), and `coldStart()`'s default A is `$80`.  OFF is the 48K machine, byte
  for byte: the same real load answers `$30`, builds no engine, logs no AY row, RET-patches the three hooks (H7), and every
  other gate in the file runs OFF.
- **The front end's key repeat**: the ROM's KEYBOARD reads REPPER from `$5C0A`, which the 128K load leaves 2 (the 48K's 5).
  tools/cold128.py re-runs ctrlmenu's 24 key histories on the machine with `$5C0A` = 2 (a held key repeats at scans 0, 35,
  37, 39 ... against the 48K's 0, 35, 40, 45; 349 rows differ): the port's ROM-keyboard model under m128 is equal on all
  4,203 scans (H2).  Nothing else in the 14 bytes reaches the front end (FLAGS' bit 4 is the 128K BASIC's; FRAMES is
  zeroed by the probe; the rest is the printer's and the channels').
- **The probe** runs as on the 48K clock (the count is the 48K's `$075E`); under m128 `probeEnd` takes `BB_M128.BC` =
  `$0759`, the 128K's count, so the machine's own compare runs `$FAEF LD A,$80 / JP $FA3B` and the trampoline: the
  hand-over 115 T after `$FAE1` (the 48K's exit: 58), at the flow's `[344, 1051]` on the real load (H4).
- **The skip (ADDED)**, under m128, does not hand over where the CLS ends: at 19 of 64 hand-over phases (27,300..46,956) no
  tick falls in `$9575`'s delay, the `$8CD7` wait finds the busy byte still 1 (the tape's), and the cold start's jingle is
  never heard (the flow's skip_sweep; 20 had been written there: the rows hold 19).  It waits for `skipPhase` = the probe's
  own phase `BB_M128.HAND_PH` (1,051): in the CLS's frame if it ended before it, else in the next once that frame's
  interrupt (the front end's) has run -- or at once if that interrupt ran past it -- always on an integer T (the
  control select's path means leave a fraction: M7.115c).  From there it is the probe's hand-over frame for frame (H5).
- **The cold start with the leg**, `$F5CC -> $8CCA` (DI), is debt by the phase it begins at: `bbColdT128` replays the
  leg's access program (tools/cold128.py: 216,651 T plain, 48,391 contended accesses -- the cold start's own, the first
  LDIR's display writes with their internal cycles, the second's display reads, each `OUT ($7FFD)`'s four I/O cycles), the
  machine's T at 480 phases and on three worlds (H3).  Its products: `coldStart(M128)` skips the patches and runs the
  leg -- the 3,860 bytes over the display file (`legDisplay`, from the shipped asset) and the engine over the bank the
  leg leaves (`ayEngine = new BB_Ay(BB_Ay.bank1(...))`).  No sprite rebuild.  The interrupts that fall in it are lost.
- **The swap at `$8CCA`** (`hand128Swap`): handDone's -- the load's world with the 128K bytes and cold start, the black
  screen kept with the leg's display writes over it (AT ONCE: the machine's LDIR spreads them over frames 344..346 --
  invisible, their attributes 0, DECLARED), the page's clocks, the sound log and the front end's counters carried -- made
  at the cold start's end, not at `$970E`, because what follows reads and writes the world.  The control select's key
  table survives it (loadpath's cursor_kempston, H7).
- **After `$8CCA`**, instruction by instruction on the frame clock (`hand128Ins`): `$8CCA EI / LD A,3 / CALL $8E0A`
  (request 3), `LD C,1 / CALL $9575` -- the delay with the taken request's A = `$10` and B = `$7F`: 3,967 DJNZ, 51,763 T
  (the 48K's 768) -- `LD A,5 / CALL $8E05` (the wait: `LD C,(busy) / DEC C / JR nz`, 23 T a turn, the turns before the
  frame's last run at once), its fall into `$8E0A` (request 5), `JR $8D02 / LD HL / PUSH / CALL $96DF` and the reset half
  (`BB_SPINE.RESET_T`, DI) to `$970E`, where the title begins as handDone leaves it.  The frame's interrupt (asserted
  `BB_SPINE.INT_ACTIVE` T) is taken at the end of the instruction in progress with IFF 1, never right after an EI, and
  lost once it is no longer asserted: the cold start's end at T < 21 takes it after `LD A,3`, the reset half's at T < 11
  after `$970F`'s CALL (the title's first), as BB_SPINE has it (H7).
- **The request** (`$8E0A`): `LD HL,$FED4 / CP (HL) / LD (HL),A / RET z` -- 35 T when the sound is current (the flow's two
  such, the boss defeat's `$8E8A` and the alive-7 round's `$98FC`: H6) -- else `DI` ... `CALL $D167` (the engine's
  request) ... `EI / RET`, 577 T and the two `OUT ($7FFD)`s' I/O waits (`bbIo7ffd`: port `$7FFD` is C:1 four times from 8
  T in; the machine's OUT alone at 761 phases, the fourth wait non-zero at 54: H3).  A DI window: an interrupt asserted
  from 1 to 516 T after the DI is lost, from 517 taken after the RET (the flow's 179 forced offsets: H6).
- **The game's interrupt in the hand-over** (`hand128Isr`): both gates shut (`$9610`), so it counts `$8DB6` and `$8DBD` and
  calls the hook: `BB_ISR_ACK` + `PROLOGUE` + `COUNTERS` + the branch by the new parity + `GATE_CLOSED` to `$8D8F`'s CALL,
  then the hook (`soundHook`), then the pops, EI and RET (`EPILOGUE` less the 48K's CALL / RET, `HOOK48` = 27): 461 + the
  hook odd, 466 even.  **The hook** (any sound but the theme ticks every interrupt; the theme's cadence is M10.2b's):
  `DI / LD A,($FED4) / DEC A / JR nz,$8DEA / LD A,($9AE7) / OR 1 / LD BC,$7FFD / OUT (C),A / CALL $CF80 / EX AF,AF' /
  LD A,($9AE7) / LD BC,$7FFD / OUT (C),A / EX AF,AF' / LD ($8E06),A / RET` -- 175 T + the tick's + the OUTs' waits; the
  tick enters 109 T after the CALL (and the first OUT's waits).  Each AY write goes to `game.ay.log` as `[frame + t / 69,888, reg, val]`, t its
  `OUT ($BFFD)`'s first T.
- **Gated record for record** against the flow (H4: the real load's p1, p2 and idle; H5: the skip at the natural 52,024 and
  as it ships) through `game.ay.trace` (null; a gate sets one: the oracle's shapes): every mark, request, engine request,
  wait (its busy byte and turns), interrupt (acceptance, T, the hook's T), tick, `OUT ($7FFD)` and AY write to `$970E`,
  the interrupts lost, and the frames' sound state at every boundary from the swap (busy, the sound last requested, the
  cadence, the HURRY latch, `$8DB7`, the alive count).  The skip at 64 phases: the wait's frames, request 5's and
  `$970E`'s, the busy byte the wait found and its turns (241,8xx..243,0xx where it waits, 1 where it found 1).
- **Not yet** (M10.2b..d): the hook in `isr()` (the title and play: the theme's cadence, its T in the ISR's cost, the OUTs
  on the ISR's access program), every request site and wait in play, the pause.  Until M10.2b the title under m128 is
  silent (sound 5 is requested and never ticked), and a late interrupt at `$970E` runs the 48K's `isr()`.  (M10.2b: the
  hook in `isr()` and the late interrupt -- the next subsection.)

### The sound hook in the game's interrupt (M10.2b: web/game.js `isrHook`, `soundHook`'s cadence, `ayOut`'s I/O cycles, `frontFrame`'s acceptance phase; bb.test.js B1..B5)
- **The hook in `isr()`.**  Under m128 every interrupt the game runs -- step()'s at the frame's end, `isrHere`'s inside a
  callee, the reveal's, the game-over screen's, `hand128Done`'s late one -- ends with `$8D8F CALL $8DC4`.  Both parities and
  any gates reach it (`$8DA2`'s and `$8DAD`'s `RET z` and the passes' RETs all land on `$8D8F`), so it is EPILOGUE's first
  instruction: `isrPlain - EPILOGUE` plain T after the acceptance, and on the wall clock after the acceptance phase and
  the waits of every access before it (`isrD` so far).  The 48K's CALL to a RET (`HOOK48`, 27 T) gives way to the hook's
  T.  Its two `OUT ($7FFD)`s' four 1-T I/O cycles go on the ISR's program at their plain offsets (class 2, the port
  cycles'), so `isrD` replays them with the rest (soundHook waits them at their wall T: the same) and `isrPlain` keeps
  the rest.  The interrupt begins the NEXT frame -- step() runs it at the frame's end -- so its trace label and its AY
  rows' frame are `simFrame + 1`, their T the acceptance phase + the offsets: the machine's wall clock, not the main
  line's ledger (which the beeper's edges ride).  `hand128Done`'s late interrupt is in its own frame (`isrNow`), accepted
  after `$970E EI / $970F CALL` (`BB_SPINE.EI_NEXT[1]`), its T the ISR's own (461 / 466 + the hook's), no longer
  `GAME_ISR_T`; the interrupt after it is the next frame's again.  m128 with no engine (set after `reset()`) is refused
  by name.
- **The cadence** (`soundHook`, `$8DC4..$8E04` transliterated): `DI / LD A,($FED4) / DEC A / JR nz,$8DEA` -- every sound
  but the theme ticks every interrupt.  The theme: `LD A,($904D) / OR A / JR nz,$8DEA` (the HURRY UP latch: every
  interrupt); `LD A,($8DB7) / CP 3 / JR c,$8DDF / LD A,($FECA) / CP 7 / JR z,$8DEA` (past the round's 768th frame with
  exactly seven enemies alive: every interrupt); else `$8DDF LD A,n` (`$8DE0`) `/ DEC A / JR nz,$8DE6 / LD A,3 / $8DE6
  LD ($8DE0),A / RET z` -- 2 -> 1 tick, 1 -> 3 skip, 3 -> 2 tick, a skip leaving the busy byte as it was.  The hook's own
  T by path, from its CALL (the tick's T and the OUTs' waits on top): 175 not the theme, 199 HURRY, 253 seven alive, 267
  / 289 the cadence's tick (`$8DB7` below 3 / not), 150 / 172 its skip -- the instructions' sums, each the machine's on
  every hooked interrupt of the flow.  `hookIsrs` counts the hooks `isr()` ran, `hookSkips` the cadence's skips.
- **Where the front end's interrupts are accepted.**  The front end (the paint, the ring, the release) runs an
  instruction at a time on the frame clock, so the frame's interrupt is accepted where the instruction in progress at
  the boundary ends: `frontFrame` keeps `tframe - budget` as the acceptance phase (`gridPhV`) when the frame ends with the
  front end up.  It was `BB_ISR_ACCEPT`'s 4 (PROVISIONAL) until M10.2b -- invisible on the 48K, whose title interrupt has
  no contended access, and wrong at most title interrupts for the 128K hook's AY writes (TRAPS #351).  Both machines: the
  48K's isracc agrees on all ten title and release interrupts (frames 400..409).
- **The flow oracle's `hooks` rows** (tools/ay128flow.py, recaptured in M10.2b, every other record identical): at each
  `$8D8F CALL $8DC4` inside an ISR, `[label, frame, t, $FED4, $904D, $8DB7, $FECA, $8DE0, $8E06]` -- the hook's inputs as
  it reads them.  A boundary's frames row can be stale by then: the ISR's passes run first, and in p1's ISR 1697 the
  player's respawn at `$ABA8` (in `$AA60`'s pass) clears the HURRY latch before the hook, the main line's `$9059` setting
  it again before the next boundary (TRAPS #350).
- **Gated** (B1..B5): the title from `$970E` to request 7, record for record -- p1 (21 interrupts, 21 hooks, 21 ticks, 42
  `OUT ($7FFD)`s, 34 AY writes; sound 5's first tick 2,853 T, its interrupt 3,489), the skip scene (26 interrupts) and
  the skip as it ships -- and the sound state at every boundary; soundHook over all 10,543 hooked interrupts of the nine
  scenes from their recorded inputs (each T, ticked or skipped, the cadence and busy byte it leaves; one T per path);
  the hook inside play interrupts of the 48K's real load switched to m128 for one interrupt -- odd 465 (the draw: both
  OUTs wait 6 T), even 578, and a skip at 467 -- its CALL at the 48K's `$8D8F`, the cost the 48K's less `HOOK48` plus the
  hook's, `isrD` and `isrPlain` each (TRAPS #352), the program access for access; OFF never hooks; the late interrupt.
- **Not yet** (M10.2c, d): every request site and wait in play -- after '1' the title's 5 plays on (the machine's release
  requests 7 at `$97B4`, and round 1 waits for its end); the pause's mute and re-request.  (M10.2c: the title's, the round
  start's and game over's requests and round 1's wait -- the next subsection.)

### The requests and waits on the main line (M10.2c: web/game.js `mwBegin` / `mwTail` / `mwRun` / `mwIns` / `mwRet`, `BB_TEXIT.ARM128`, `hookPlan`; bb.test.js C1..C8)
- **The machine.**  Under m128 the main line calls the sound code the 48K patched to RETs: `$8E0A` the request (`LD HL,$FED4
  / CP (HL) / LD (HL),A / RET z` -- 35 T when the sound is already current -- else `DI`, bank 1 paged in, the engine's
  `$D167`, bank 0 back, `EI / RET`: 577..605 T with the two `OUT ($7FFD)`s' I/O waits; request 0 250) and `$8E05` the wait
  (`LD C,n / DEC C / JR nz`, 23 T a turn, the busy byte `$8E06` its operand) that spins until a tick has stored 1 there --
  the current sound has ended a pass -- then falls into `$8E0A`.  The interrupts run on inside the wait (both gates open on
  round 1: the player walks, the enemies -- the main loop's -- stand, the round's timers run 221 frames on).
- **In the engine** (`mw`): the main line is an instruction at a time in `$8E05..$8E29` on step()'s LEDGER, the way
  `hand128Ins` runs the hand-over's on the frame clock.  `mwWall(t) = t + isrCost - (span - 1) * FD` maps a ledger T to
  the frame clock (the ledger's 0 is where the frame's first interrupt ended), so every row the trace keeps (requests,
  engine requests, waits, OUTs, marks) and every `OUT ($7FFD)`'s I/O wait is at the machine's T.  The wait's whole turns
  that end before the frame's last run at once.  The interrupt is taken where the instruction in progress at the boundary
  ends (`mwRun` keeps that phase); the request's `DI .. EI / RET` is one step whose window `[DI + 1, the RET's end]` goes on
  `diWindows`, so a boundary 1..516 T into it LOSES the interrupt (`intLost`; `mwLost` counts them) and from 517 it is
  taken after the RET -- the flow's di_window.  A request cut before its DI ends after the interrupt, in the next frame.
- **The sites** (M10.2c): `$97B4` LD A,7 / CALL `$8E0A` when '1' or '2' is accepted (BB_TEXIT.ARM128: the arm's 48K RET is
  the request -- `'rq'` hands the main line over, the release's program resumes after it; `'m7'` marks the CALL); the round
  start's tail `$98F0..$9901` (`mwTail`): round 1's `JP z,$8E05` (the wait, then request 1), every other round's `JP
  nz,$8E0A` request 1 (a no-op while the theme is current), round 80's `$9901` request 6.  The tail's program (BB_R1T /
  bbLrTail) and the 'hp' path's banner constant now end where the 48K's RET at `$8E05` / `$8E0A` began (BB_M128.RET48, 10
  T; r1tBegin refuses a tail whose last instruction is not that RET).  Game over: `$8CDC LD HL,0 / LD ($FEC4),HL / LD A,5 /
  CALL $8E0A` -- the title's 5 -- inside step()'s exit (the screen's next frame finishes a request cut before its DI, from
  the ISR's end, its window dropped, no acceptance phase carried in).
- **The build replays** (r1Clock, lrClock): `$97F8..$9887` is replayed at `$97F8` with each interrupt's T dropped in at
  its boundary -- the 48K's gate-closed constant.  Under m128 each of those interrupts also runs the sound hook (+150..3,000
  T), so the replay's contention and its end were the 48K's: skip's HALT interrupt at 3 T for the machine's 0.  `hookPlan`
  gives the replay each interrupt's hook in order, stepped on a COPY of the engine and of the bytes the hook reads (its
  OUTs fall in the ISR's first few hundred T, where nothing waits); isrHook checks each planned T against the one it runs,
  up to the final replay's interrupt count (`hookPlanN`, `hookPlanBad`: 10 / 0 on round 1, 75 / 73 / 0 on rounds 10 / 80).
- **Gated** (C1..C8, against build/ay128flow_fixture.json, LD A,R fed the machine's draws -- the engine's R is a
  stand-in): p1, p2, skip and idle free-running from the load: every request, engine request, wait (its turns: 544,801 on
  p1's round-1 wait) and mark the oracle's; every interrupt, hook, tick, OUT, AY write and pass from `$970E` the oracle's
  to each scene's pinned parting -- but round 1's build's interrupts (eight, nine on skip), accepted at `BB_ISR_ACCEPT`'s
  4 (the build has no instruction grid, DECLARED) and differing by that alone; the DI window at the oracle's 163 offsets;
  all 18 requests the oracle made with the interrupts on (11 sites) re-made at their machine T; OFF unchanged and every
  refusal named; a request cut before its DI; the plan against soundHook on every path (288 hooks); rounds 10 and 80 (the
  `$9901` request exact to the T).
- **DECLARED / PINNED.**  The play after round 1's wait parts from the machine at p1 760, p2 / idle 1009, skip 761 (C2) --
  the 48K port's play in states its own gates never reached (the wait walked the player and ran the round's timers 221
  frames on); the M7 timing campaign stopped at M7.115m, so these are pinned, not chased.  Game over's request therefore
  lands at the port's T (idle: `[2272, 35549]` for the machine's `[2272, 35189]`), alive7's `$98FC` two frames late.
  The game-over screen's interrupts take `BB_ISR_ACCEPT` (the machine's HALT grid is 0..3), as on the 48K.
- **Not yet** (M10.2d): the pause -- `$8FF3`'s request 0 and the unpause's `$9006` request (made with the interrupts off),
  which pair.  (M10.2d: "The pause", two subsections on.)

### The sound calls in play (M10.2c2: web/game.js `lzStopAt` / `lzHit` / `lzOn128`, `lzSeg`'s stop, `heartReq`, `bossDeath128` / `mwSeqStep`, `BB_M128.STOP` / `HEART` / `BOSS`; bb.test.js D1..D6)
- **The machine.**  Four play blocks call the sound code too.  The HEART (power-up 10): `$887C DI / $887D CALL $8E0A` (A 4) `/
  $8880 EI`, inside the item pass.  The POTION (12): its block's head requests 3 at `$891A` (its own `$890D` DI still in
  force) and its fill's tail `$898F LD A,4 / CALL $8E05` WAITS for 3's pass to end -- 82 interrupts, both gates shut: the
  treasure room stands still -- then requests 4; the gates open after it (`$8996` / `$8999`).  EXTEND: the entry requests 2
  at `$94D5` (its `$94CB` DI in force) and `$953A LD A,3 / CALL $8E05` waits for 2's pass (182 interrupts) before the banner.
  The BOSS DEFEAT `$8E55..$8E9B`: `$8E77` request 3 (interrupts on), the banner, `$8E8A` the wait for 3's pass (82) and 3
  again (RET z, A stays 3), `$9573` twice ((3, 0), (0, 0)), `$8E95` the wait for 3's NEXT pass end (11 here; 0..81 by phase)
  and request 2 -- taken, it leaves A = $10, B = $7F -- and `$8E98 CALL $9573` with them: 7,744,925 T for the 48K's (2, 0)
  7,699,856, 45,069 longer.
  A request made with the interrupts OFF ($887D, $891A, $94D5): the window is the caller's from its DI; the request's own
  `EI / RET` ends it at the RET (the interrupt is then taken before the caller's EI); not taken, `RET z` leaves the
  interrupts off on to the instruction after the caller's EI (REM: 16 / 8 / 11 T past the 48K's RET).
- **In the engine.**  `mwBegin(pc, a, site, ret, iff)`: `iff` 0 runs the request WHOLE (`mwRun` -- no interrupt can be taken
  inside it) and `mwRet` carries the caller's window to the RET's end (+ REM on RET z): the window the block cut at the
  call (the last on the clock), else one from the call.  `mwRet` keeps the registers a taken request leaves (`mwA` / `mwB`).
  A WAIT entered with the interrupts off is refused by name (it could never end; the machine enters every one with them on).
  - A LAZY BLOCK'S STOP: under m128 `extRt` registers each sound call of EXTEND's and the potion's block at its CALL's end
    on the block's exact clock (`lzStopAt`, BB_M128.STOP: ENTRY 108, PT_HEAD 1,194, CALL_IN 24 after the routine before;
    the fill's tail from `ptFillModel`'s `tail`, none on the table-full exit).  `lzSeg` makes nothing of the block past the
    next stop -- writes, OUTs, windows -- and a window over it is CUT there (only over an interrupts-off call; its tail past
    the RET asserted equal to REM); reaching it before the frame's point it holds the block (`L.hit`) and `lzHit` enters
    the sound code there (`ret` 'lz').  The RET sets `lzRes`; `lzStep` (in step()'s loop the same frame, or at the next
    frame's start -- not while the sound code runs) resumes the block from after the 48K's RET (`lzOn128`).  `extEnd`
    handles a stop reached in the call's own frame (EXTEND's $94D5 is 108 T in): the pass held as for a block past the point.
  - THE HEART (`puRoundEffect` -> `heartReq`): made at once inside the item pass where the handler's CALL ends -- the
    pass's cursor at its `JP (HL)` (`itHandlerO`, the potion's) + HEART 197 -- its DI window from `$887C` (HEART_DI 21 T
    before, +1); its T charged to the item pass (`itSub`).  A cursor lost, or the call past the frame's point, counted
    (`mwLate`).
  - THE BOSS DEFEAT (`bossDeath128`): a program step() runs a step a turn (`mwSeq` / `mwSeqStep`), each wait and request on
    the ledger, each delay SPENT as the 48K's are, the instructions between them charged (BOSS: MID 79 + BANNER, CALL 17,
    LD_CALL 24).  It begins where `$8E77`'s CALL ends -- `$8E3A`'s entry on the frame clock (`calleeAt`) + its T to `$8E55`
    and the award's (rcT, rcSub) + HEAD 172 -- which is all of `$8E3A` the pass charges; the round advance the pass
    decided waits for the program (`advDefer`).
- **Gated** (D1..D6, against build/ay128flow_fixture.json, its scenes poked as it poked them): the POTION record for record
  -- both requests, the wait (243,034 turns), and every interrupt, tick, hook, OUT, engine request and AY write of frames
  838..929 the machine's (88 interrupts, 105 AY writes), the gates shut through the wait and open after; EXTEND the same
  over 838..1039 but for the acceptance phase of 14 interrupts that end a frame inside the lazy block (BB_ISR_ACCEPT's 4,
  the 48K's own) and their frames' rows shifted by it, and 1380..1394 exact (round 2's `$98FC`); the HEART's request to the
  T with its engine request and OUTs; the BOSS DEFEAT's requests at the machine's sites, sounds and frames, `$9901` and
  round 81's `$98FC` to the T, every wait's ticks (82, 11, 81) and end frame, its end within one 23-T turn, and every
  interrupt of 1698..1789, 2015..2211 (the delays to round 81's build: the delays end in the machine's frame) and
  2205..2299 the machine's but its acceptance phase; all four interrupts-off requests of the oracle re-made at their T,
  the stop unit by unit (held writes, an OUT, the cut window carried, the resume, both refusals), the heart's three paths;
  OFF unchanged and every new site refused by name outside step().
- **DECLARED / PINNED.**  The boss defeat's pass is the 48K port's play (C2's partings): `$8E77` at `[1700, 14820]` for the
  machine's `[1700, 13507]`, its OUTs' I/O waits from there (589 T for 577), the waits' rows at the port's T (pinned whole);
  their ends within one turn of the machine's.  The pass's skeleton after `$8E3A` is charged before the program, not
  after.  The heart's handler's own 197 T are not charged (as no handler's is, M7.92), and a heart past the frame's point
  is requested before that interrupt's hook all the same (`mwLate`).  The lazy blocks' acceptance phase is BB_ISR_ACCEPT's
  4, as on the 48K.

### The pause (M10.2d: web/game.js spinStep's `rq` / `spinRelease128`, `BB_PAUSE_SPIN.REQ` / `EI_RET`, pauseGate's refusal; tools/pause128.py -> build/pause128_fixture.json; bb.test.js Q1..Q5)
- **The machine.**  `$8FE7` arms on SYM SHIFT as on the 48K (M7.107), but its two `CALL $8E0A` are the sound code.  `$8FEE
  LD A,($FED4) / PUSH AF / XOR A / $8FF3 CALL $8E0A` is REQUEST 0, the mute -- the engine writes R7 := `$3F` 67 T into its
  89 T and nothing else -- made with the interrupts ON: a DI window `$8E10 .. $8E29` (238 T plus its OUTs' waits: 238..258
  measured) whose RET's end is the arm's last acceptance point; `$8FF6 DI` follows.  The spin polls with the interrupts
  off, so nothing ticks: the AY holds the mute.  CAPS releases it: `$9002 XOR A / $9003 OUT ($FE),A / $9005 POP AF / $9006
  CALL $8E0A` re-requests the sound `$8FEE` read with the interrupts OFF (`$FED4` is 0 by then: taken, 577 T plus waits),
  which restarts it from its start; its `$8E28 EI / $8E29 RET` end the spin's window one instruction before the 48K's
  `$9009 EI / $900A RET`, and `$8D2B` comes 14 T after that RET.
- **Measured** (tools/pause128.py: 414 runs on six worlds saved at the main loop's top from the flow's p1 (the theme) and
  boss (the boss theme) scenes -- 144 natural arms at 68 phases, 180 FORCED arms, 90 FORCED releases).  The arm's
  interrupt, `$8FE7` at boundary - L: taken where the instruction in progress ends, up to the request's DI (L <= 104);
  LOST from 1 T into the DI until 32 T before the RET's end (105..281); taken at the RET's end (282..313 -- the hook then
  ticks once after the mute: the engine's sequencer runs on); lost in `$8FF6`'s DI and the spin.  The release's (SYM and
  CAPS together, L from `$8FE7`): lost while the spin's window covers it (to 951 -- 350..406, between the releasing IN and
  the unpause's CALL's end, by the spin's own window alone), taken at the unpause's RET's end (952..983), and -- the
  point in `$9009 EI` -- after `$900A`'s RET (984..997).
- **In the engine.**  The arm's `rq` element (the 48K's RET at `$8E0A`) is, under m128, request 0 on step()'s ledger:
  `mwEnter` / `mwRun` (M10.2c's machinery, its window on `diWindows`).  The arm's interrupt is taken where `mwRun` stops
  before the DI (its acceptance phase), or -- not lost -- at the `$8FF6 DI` after the RET, by the arm's generic rule, which
  under m128 now keeps the phase (`gridPhV`, the end of the instruction in progress; OFF leaves the 48K's `BB_ISR_ACCEPT`).
  Lost in the window, the arm runs on (nothing after it waits for the interrupt).  A held frame re-bases the windows
  under m128 (`intLost`), as a frame's end does: a window over the point would otherwise stay on the old clock.  The
  release is `spinRelease128`: the spin's window `[DI + 1, ...]` pushed and carried to the request's RET's end (`cut`; REM
  `EI_RET` past RET z, which has no EI), the request run whole (iff 0); kept only when it holds the interrupt (the 48K's
  rule), else the acceptance phase at that RET's end or at `$900A`'s.  Only the window's end is ever read -- a release's
  poll starts 29 T or more after the spin's DI and before the point, or the DI is a frame behind (TRAPS #347).  pauseGate
  under m128 outside step() is refused by name before anything is stored.
- **Gated** (Q1..Q6, build/pause128_fixture.json): the machine's facts (the requests' T, the mute, the edges above, no tick
  in the spin); all 414 runs replayed through spinStep from the machine's `$8FE7` -- both requests' rows, the engine's
  requests, the OUT (`$7FFD`)s, the mute, the spin's DI, both OUT (`$FE`)s, every poll, `$8D2B`, the arm's interrupt and
  its acceptance phase (106), the release frame's interrupt lost or taken at the machine's phase (63 crossings); the two
  scenes through step() (pz: SYM at 741, CAPS at 749; pzb: SYM and CAPS at 741, six arms and releases in one frame) --
  frames 700..740 every record the machine's, the requests' site, A, sound and IFF the machine's, the unpause to the T,
  frames 742..748 quiet on both, the first interrupt after the release the machine's (the restarted theme's first tick,
  2,282 T) but its acceptance phase; the flow's own p1 pause requests at their machine T; OFF the 48K's pause, the refusal,
  and the edges (RET z at both sites, a lost window re-based by a held frame, a release well before the point, the arm's
  phase under m128 and OFF); and the arm meeting the interrupt THROUGH step() (PZ4's forced way: request 0 cut before its
  DI, lost in its window, taken at its RET's end -- the machine's phases 5, lost, 13), which Q2's replay cannot see (it
  derives each frame's origin from the spin's clock: TRAPS #360).
- **DECLARED / PINNED.**  `$8FE7`'s place in the pass is the 48K's pass clock (M7.107): in pz the arm is 1 T late, so
  request 0's OUTs wait 250 T for the machine's 244 (pinned).  FOUND, the 48K's: a pass with CAPS held and SPACE up runs
  `$8D6A..$8D6F` -- `$8D68 JR c` not taken, `LD A,$7F / IN A,($FE) / RRA / RET nc` -- 22 T more and a second contended IN,
  which the 48K's pass skeleton (the CAPS-up path) does not charge (TRAPS #357).  The release always holds CAPS, so pzb's
  six arms drift (24 T on the first) and both scenes' first interrupts after the release are accepted 2 and 4 T apart
  (pinned).  Not fixed: the timing campaign is stopped (owner, 2026-10-12).

### The page and the platform (M10.3: web/template.html `BB_PAGE.m128` / `saveMachine`, `BB_MACHINE`, `bbMachine`, `bbBoot`, `bbMachineKey`, the captions; web/platform.js SoundOut's `'mix'`; bb.test.js G1..G7, kit.test.js "THE MIX")
- **The machine the page boots** (the owner, 2026-10-13): the 128K -- `BB_PAGE.m128`, ON; OFF the 48K page as it was.  A
  machine is chosen once per boot (the probe answers it at the control select, the cold start runs once), so **Alt+M
  REBOOTS** into the other: `bbBoot()`, the page's own boot -- a new BB_Game, `m128` set before `ctrlBoot` (M10.2a), the
  load's control select at `BB_MENU.LOAD_PHASE` -- with the high score's and the Alt keys' objects made for the new game
  and the sound bridge reset.  In every state (the control select, the title, play, paused, the game over): the game in
  progress is gone, as when a real machine is switched off.  It is the page's key, like Alt+Enter: M (a Spectrum key) is
  never pressed by it, the event stops at the page's listener, a held combo's repeat does nothing; plain M is the game's.
- **Remembered** (`BB_PAGE.saveMachine`, ADDED, default ON, as the high score): `{ machine: '128K' | '48K' }` in the
  browser's store under `bb-machine`, saved at each switch, read at each boot.  Any other stored value is REFUSED by name
  (`machine.info().refused`) and the default booted, the store left as it was; an unparseable one reads as empty (the kit's
  `settingsStore` turns a parse error into null); a store that throws (file:// with site data blocked) reads as empty and
  its failed saves are counted.  OFF: the store is neither read nor written; Alt+M still switches, for the page's life.
- **The caption** names the machine RUNNING (`game.m128`, not the choice) and the key to the other, after the game's own
  keys and before the fullscreen hint, at the control select and in play: "128K machine (Alt+M: the 48K)".
- **The sound: ONE stream for both chips** (platform.js, game-agnostic: the instrument `'mix'`).  The beeper and the AY
  are rendered into the same chunks, on both transports: the worklet's one stream (the default -- the AY instrument had
  only the scheduled buffers, the path that crackled on the owner-class laptop: TRAPS #12) and the scheduled fallback.
  The page hands the bridge the engine's AY log beside the beeper's (`sound.flush(game.sound.log, game.simFrame,
  game.ay.log)`).  Its rows are `[frame + t / 69,888, reg, val]`, each at its OUT (`$BFFD`)'s T, so each write takes
  effect at the start of the output sample its time falls in -- floor on the stream map's absolute grid (an integer-frame
  log would land it up to a frame late) -- cut by the window as the beeper's edges are (a row past the window's last whole
  sample waits for the next).  MEASURED on the engine (scratchpad/m103/aylog_unsorted.js, every flow scene): the log is in
  time order and no row is ever logged behind the frame the step began in; an ISR's rows are labelled into the next frame
  (up to 0.57 of a frame ahead of `simFrame`) and wait in the log for the next flush.
- **The AY's state is never lost.**  Its registers are shadowed whatever becomes of the samples -- no context yet (before
  the first gesture), sound off, a backward clock (a restart), a dropped buffer (the voice cap) -- and the chip, made at
  its first rendered window, replays only the registers written since the last reset (a fresh AyChip IS power-on; a
  replayed R13 would restart the envelope).  A row that arrives behind its window is written at the window's start and
  counted (`aylate`).  An AY never written since its reset is not rendered at all: the 48K page costs nothing.  Its output
  is DC-blocked (the 20 Hz one pole, as the beeper's: the machine's output is AC coupled) and scaled by `ayMix`.
  `reset()` is a machine reboot: every chip at power-on -- the speaker LOW (EAR is 0 at power-on: a speaker the old
  machine left high steps down at the reboot, not at the new machine's first edge seconds later -- the Sonnet review's
  one finding), the AY silent, the AY instrument a fresh chip -- the map re-originated by the next flush, counted in
  `resets`, never as a resync, the lead untouched; and every origin, the first flush's too, adopts the driver's state
  from the log it drops (the speaker's level, the AY's registers).  `info()` names both chips:
  `... wk=on chips=beeper+ay ay=live ayw=152 aylate=0 aymix=1.00 resets=0`.
- **DECLARED / PROVISIONAL.**  The AY's level against the beeper's: `AY_MIX` 1.0 puts the three voices at full volume at
  the beeper's own swing (the skip scene's AY alone peaks at 0.88 of it) -- how loud the two were against each other on a
  real 128K is its analogue output (the TV, the modulator), which no simulator measures; the owner's listening test sets
  it (`sound.ayMix = x`, live).  The AY is the kit's AyChip model (16 levels at 2^(-1/4) a step, the mean of its internal
  steps per sample, AY_CLOCK 1,773,400 Hz).  The frame clock stays the 48K's 50.08 Hz (option A: the 128K branch on the
  48K clock), so the tunes are in pitch and 0.12% fast against a 128K's 50.02 Hz.  The beeper keeps the kit's speaker
  model on the 128K too.
- **Gated.**  kit.test.js "THE MIX" (11 checks, game-agnostic, upstream with the platform): the worklet's chunks and the scheduled
  buffers each the one-shot render of both chips -- built in the test from one BeeperChip and one AyChip written row by
  row -- at a mix of 0.6 and of 1, with writes in a window's last sample and in the sliver past it; a write's first
  sample on a map originated at frame 5, on both transports; never written = the beeper's stream, and a beeper ignores
  an AY log; no context, sound off (both transports), a restart (both), a dropped buffer and a late row keep the
  registers; only written registers replayed (an envelope never restarted, before a context and after a reset); reset()
  (the review's case: the speaker's step at the reboot, none at the new machine's first edge) and the first flush's
  adoption on all three instruments; info().  bb.test.js M10.3: G0 the kit's own suite run against the page in a child
  process (the battery runs only bb.test.js, and selects this block for every line of the mix G7 runs here: without G0,
  15 of the 30 platform cases lived through G5 / G7 alone -- TRAPS #363); G1 bbMachine (the default, the read, ten other values, the switch saved into the rig's REAL
  store and read back by a new boot -- TRAPS #17 --, OFF, a throwing store); G2 this suite's page the 48K by the store's
  choice (seeded before the load, so every page row before M10.3 reads the 48K page it was written for); G3 FRESH pages
  in child processes (empty store -> the 128K, '48K' -> the 48K, a refused value -> the 128K and the store untouched);
  G4 Alt+M twice on a fresh 128K page (a new game at the control select, the bound objects new, the loop stepping it, the
  choice saved, the bridge re-originated on the new clock, M never pressed, the repeat nothing, plain M the game's) and a
  RELOAD from the store the first switch left; G5 the 128K's AY reaching the bridge through the page's real loop by real
  key events (to the title at frame 174 and 50 frames of its tune: 152 rows, every one taken, none late, the log never
  above 16 rows, a mock context from the first key), the 48K page writing the AY nothing through its own drive into play;
  G6 the captions; G7 the 128K engine's two logs through the mix IN THIS PROCESS (the flow oracle's skip scene, 420
  frames to play: 1,687 beeper edges, 289 AY rows at 13 registers) the one-shot render on both transports (worst 7e-12 /
  1.5e-8); G8 a reboot IS a fresh boot -- a fresh 128K page driven by real keys into play (544 AY rows), Alt+M, Alt+M: each
  new game's whole state (its 64K hashed, the clocks, the stages, the logs, the engine) a fresh page's on that machine,
  loaded in ANOTHER process (so an asset the old game changed in place would show -- none does: 182 asset keys hashed
  across 1,300 frames of play on each machine, scratchpad/m103/assets_probe.js), the bridge silent and idle after each;
  G9 this suite's own page in this process -- its draw hands the bridge the game's three logs, a held Alt+M's repeat is
  stopped and switches nothing, plain M reaches the Spectrum's keyboard (the battery's selection sees only what runs in
  this process: run here, the Alt+M path and the draw's flush select this block, whose children kill their mutants --
  TRAPS #363).

## Player controls -- input reader & key tables (MEASURED)

- **Reader `$ABF4-$ACEB`** + the Kempston branch `$AEF5-$AF29` (IY = player entity; ported M7.44 as
  `playerRead`): walks a per-player KEY TABLE via HL. Each key = a
  2-byte pair **`[half-row-select, bit-mask]`**: `LD A,(HL)` (half-row) / `CP $1F` (Kempston sentinel
  -> `JP z,$AEF5`) / `INC HL` / `IN A,($FE)` (A = the half-row as the high address byte) / `AND (HL)`
  (mask) / `INC HL`; a clear masked bit = key pressed -> sets the direction/action bit. 4 keys per
  player (LEFT, RIGHT, JUMP, BLOW).
- **Active tables**: **P1 = `$B5FD`, P2 = `$B605`** (8 bytes each), selected at `$ABF4-$ABFD` by
  `(IY+$5A)` bit0. Populated at control-select time from a preset (keyboard / Sinclair / Kempston /
  cursor) or the KEYBOARD redefine flow. First byte `$1F` = the whole player is on the **Kempston**
  joystick (`IN ($1F)`, active-high).
- **PAUSE (MEASURED 2026-09-09, `$8FE7`, from the main loop `$8D28`)**: SYMBOL SHIFT (row `$7F`
  bit 1) pauses: `DI`, border GREEN (`OUT ($FE),4`), spin until CAPS SHIFT (row `$FE` bit 0),
  then border black and resume. Not redefinable; the 128K branch also silences the AY around it.
- **DECODED live** (round1 / play2p): P1 `$B5FD` = `[F7,10]`=**5** (LEFT), `[EF,04]`=**8** (RIGHT),
  `[EF,01]`=**0** (JUMP), `[EF,08]`=**7** (BLOW) -- i.e. the cursor-type binding, matching the measured
  in-play keys 5/8/0/7. P2 `$B605` first byte `$1F` = **Kempston** (as the M2 front-end drive set it).
- Half-row -> key legend used to decode: `$F7`={1,2,3,4,5}, `$EF`={0,9,8,7,6}, `$FB`={Q,W,E,R,T},
  `$FD`={A,S,D,F,G}, `$FE`={CS,Z,X,C,V}, `$DF`={P,O,I,U,Y}, `$BF`={EN,L,K,J,H}, `$7F`={SP,SS,M,N,B}
  (mask bit0..4 = the listed keys in order).
- PORT (decision 2b -- keyboard + controller only): implement this `[half-row,mask]` model (or an
  equivalent key-id per action) with the original's redefine; a gamepad synthesises the player's
  currently-defined keys before each step.
- **Key-table WRITER + redefine flow (RESOLVED 2026-09-08, N7 -- measured live via `title.pkl` +
  menu drive; the front end `$F5xx-$F9xx` and the pre-overwrite `$95F3` are ABSENT from
  `build/image.bin` because it is a post-boot image, which is why no literal writer is in the static
  image):** a one-shot copier `$95F3` (`LD DE,$B5FD` @`$95FB` / `LD BC,$10` @`$95FE` / `LDIR`
  @`$9601` from `HL=$F5D2`, then self-overwrites from `$7581` @`$9603`), called once from the attract
  entry `$8CC7`. Menu `$F607`/`$F664`, dispatch `$F680`; redefine `$F72F` reads 4 keys `$F983-$F986`
  via `$F7B3`; the builder `$F6DB` converts ASCII digits through table `$F988`. Presets:
  `$F9E8`="5807" / `$F9EC`="6790" / `$F9F0`="1245"; raw Kempston `$F9F4` = `1F 02 1F 01 1F 08 1F 10`.
- **2P key-clash: NONE at redefine time (RESOLVED, N8)** -- the builder converts `$F983-$F986`
  sequentially into `$F5D2` (P1) / `$F5DA` (P2) with no cross-player or per-key distinctness check.
  The only runtime handling is LEFT-priority at `$AC15-$AC22` (and `$AC54-$AC98` = a forced-direction
  override). So a port may let both players share a key; the original does not forbid it.

## High score / "scoreboard" -- MEASURED (single value, NO name-entry table)

The Firebird Spectrum port keeps **one high score, with no initials / name-entry / ranking table**.
Evidence: no high-score-table strings ("RANKING"/"NAME"/"ENTER"/initials defaults) in the image; no
name-entry key loop. `LAST-K` (`$5C08`) IS read, but ONLY by the front-end control/redefine menu at
`$F7B3` (CALLed from `$F664`/`$F748`/`$F75A`/`$F76C`/`$F77E`/`$F790`), never by any high-score
routine (R15). The lone `CP $41` at `$8CB5` is a DATA byte-pair inside the `$8CB0-$8CC2` blob (which
disassembles as junk; real code resumes at `$8CC3 DI`), NOT a name-entry compare. The `$85FC`
pointer table holds only the three on-screen SCORE positions (P1 `$402B`, HIGH `$401F`, P2 `$4034`).
- **High score = `$FFE1-$FFE4`, 8-digit BCD, 4 bytes LE.** Updated by `$8140` (LDD copy of a player's
  score into `$FFE1` when it exceeds the current high) -- see the HUD section; drawn as "HIGH SCORE".
- **PORT persistence (declared added layer, ON BY DEFAULT)**: serialise the 4 bytes `$FFE1-$FFE4`
  through `settingsStore('bb-hiscores')`; load at boot into that RAM mirror, save whenever it changes.
  Faithful path (the game's built-in default high score each cold boot) kept behind the flag; degrade
  silently on `file://`; mutation-tested against the rig's real store (TRAPS #17). Because there is no
  name table, the "scoreboard" is just this one number -- trivial to persist.

## $9AEB -- the enemy special-move spawner (chain entry $8D58)

MEASURED by `tools/enemyfire.py` into `build/enemyfire_fixture.json`; gated in
`test/bb.test.js`; engine `BB_Game.enemyFire` and its three helpers.

**What it is.**  Once per frame and then only every other one, the routine
drafts ONE eligible enemy into one of two pseudo-entity slots, `$5B00` and
`$5B0A`, setting the slot's `(IY+8)` to the enemy's type.  The slot then runs a
five-way special move at `$9BB4` -- which is NOT wired (a named counted stub,
`enemyFireUpdate`).

**Why it looked dead.**  The B-series differential tagged `$5B00` and `$5B0A`
UNIMPLEMENTED because both were static across all 1,600 sampled passes on all
three states.  The reason is the ROSTER, not the routine: `$9B41` accepts only
types 1, 5, 6 and 7, and the sampled states are on internal round 1, whose three
enemies are all type 0.  MEASURED over the spawn table at `$7491`: **45 of the
80 regular rounds carry a type this accepts**, and eleven (60-65, 67, 68, 76-78)
carry the type 7 that is exempt from the row match.

**The two gates.**
- `$9AEB` `LD A,($8DBD) / LD HL,$A37C / CP (HL) / LD (HL),A / RET z` -- the same
  frame detector `$A82D` uses, except the "operand" is an ordinary byte.  It is
  an EIGHT-BIT load of a sixteen-bit counter, so `$8DBE` is never read.
- `$9AF4` `LD A,n / XOR 1 / LD ($9AF5),A / RET z` -- an OPERAND that halves it
  again.  MEASURED: clock still -> reaches the slots once, `$9AF5` walks
  `1111111111`; clock advancing -> reaches them on 0, 2, 4, 6, 8 and `$9AF5`
  walks `1010101010`.

**The two slots.**  `$9AFC` CALLs `$9B07` for `$5B00` and then FALLS THROUGH
into it for `$5B0A`.  An active slot (bit 7 of `+7`) goes to `$9BB4` instead.
Within a slot, P1 is tried and then P2 by fall-through, and `$9B15`'s
`BIT 7,(IY+7) / RET nz` stops the slot once a spawn has taken -- which costs a
DRAW, and the draw moves the generator for everything after it.  MEASURED with
both players live: an all-type-1 roster fills both slots in TWO draws; one
acceptable enemy takes three; none takes four.

**The draw and the index.**  `$9B28` is a `$FE85` site (`BB_PRNG_SITES` calls it
"enemy AI cadence").  `AND 7`, and ZERO does nothing -- a one-in-eight pass.
That gate is load-bearing: without it `DEC A` gives $FF, the type is read at
`$B560` and the enemy pointer lands on `$FD91`, **which is player two**.

**The count gate WRAPS.**  `$9B31` `LD A,($AA57) / SUB 3 / CP C / RET c` in
eight bits.  At index 0 it refuses nothing.  MEASURED at index 6: counts 6, 7, 8
and 3 refuse; 9, 10, 12, **2 and 0** pass -- 2 and 0 through the wrap.

**The type.**  `$9B38 SLA C / LD HL,$B562 / ADD HL,BC` -- STRIDE TWO, which is
the pitch the round builder writes at (`$730E`, IX advancing by two), so the
types sit interleaved with their handler pointers at `$B552 + 2i`.

**Eligibility (`$9B70`).**  Wake delay (`$A891 + i`) zero; `+7` bit 7 SET and
bits 3 and 1 CLEAR; `+9` zero; `+6` character-aligned (`AND 7`, three bits); and
-- unless the type is 7 -- the same character row as the player (`AND $F8` on
BOTH sides).  `$9B87`'s `LD (IY+4),L` runs after the wake-delay test and before
every other one, so a late rejection leaves the enemy pointer in the slot and an
early one does not.

**The mark.**  `$9B52`'s `SET 1,(HL)` lands on the enemy's **+7** -- `$9B70`
returns with HL at the `+6`, so the `INC HL` reaches `+7` -- which is the same
bit `$9B91` refuses on.  One enemy cannot be drafted twice; the round builder's
`RES 1` at `$7455` is what unmarks them.

**The slot record.**  `(IY+4)` the low byte of the enemy pointer, `(IY+5)` the
enemy's `+5`, `(IY+6)` its `+6` aligned and `OR 1`, `(IY+7)` `$C0` with the
enemy's bit 0 (the facing, kept across the draft), `(IY+8)` the type, `(IY+9)`
its `+5` aligned.

## $948F -- the EXTEND trigger (chain entry $8D37)

MEASURED by `tools/extenddone.py` into `build/extenddone_fixture.json`; gated in
`test/bb.test.js`; engine `BB_Game.extendDone` and `extendComplete`.  **This was
the last unwired entry: the chain is now nineteen of nineteen.**

**The trigger.**  `LD A,($FED5) / OR A / RET z`, and `$9498` consumes it on the
way past.  MEASURED over `$00`, `$01`, `$80` and `$FF`: zero writes NOT ONE BYTE
and reaches neither `$94C2` nor `$957E`; every non-zero value behaves the same
and leaves `($FED5)` at `$00`.  Its only writer is `$B808`, inside the bubble-pop
class handler `$B7E5`, reached when a bubble of class 5 or more is popped -- and
that writer is already in the port (`bubbleClassMask`), so this wiring closes a
loop rather than adding a dead branch.

**The letters.**  `(IX+$63)` is `$FDE3` for P1 and `$FDED` for P2, one bit per
collected letter.  `$94C2` is `LD A,(IX+$63) / SUB $3F / RET nz` -- all six.
MEASURED by sweeping every one of the 256 values for BOTH players with the
accepted case ABORTED at `$94C8` and never executed.  The bit table at `$B80E` is
EIGHT bytes and classes 5..12 glyph to E, X, T, E, N, D, E, D, so 11 and 12 alias
5 and 10.

**`$94C2` DOES NOT RETURN WHEN IT ACCEPTS.**  Its tail is `POP HL / POP HL /
XOR A / LD ($87B2),A / JP $8D09` -- its own caller's return address and `$948F`'s
both discarded, then the chain's restart.  So once P1 completes, P2's call, the
counter, `$7E04`, `$BF5B` and the panel are ALL unreachable.  `$9558`'s
`INC (IX+$5C)` awards a life and `$8D09` is `CALL $97F8`, the round advance.

**The counter, and its equality.**  `$94A9` is `LD A,($FECB) / INC A / CP 4 /
JR z,$94BA`, and the jump skips the STORE as well as both calls.  MEASURED over
0..7: 0->1, 1->2, 2->3, **3->3 with both calls skipped**, then 4->5, 5->6, 6->7,
7->8 -- because `CP 4` is an equality, not a threshold.  In play it never exceeds
3: `($FECB)` is entry [16] of the `$9AC1` round-advance address table, zeroed
once per round, so the effect is **three element re-rolls per round and then the
class is frozen**.

**The two calls.**  `$7E04` is `LD A,R / AND 7 / ADD A,5` -- a DECLARED
SUBSTITUTE site, so the class is 5..12 by construction and the machine's sample
is noise, not a value to pin.  It is the TAIL of `$7DD6` and the port had it
inlined at that one site; `$94B4` calls it directly, so it is now a routine with
two callers.  `$94B7` is `CALL $BF5B`, the bank rebuild alone -- **not** `$BF39`,
which would also clear the entity pool and the 28-byte sparkle table.

**The tail is a `JP`.**  `$94BF JP $957E` means the EXTEND panel's RET is
`$948F`'s RET -- MEASURED: `$957E` entered once, SP there equal to SP at the arm.

**And two round-start call sites were stubs for routines the port already had.**
`$986F CALL $957E` is `extendRow()` (written for M7.7-H9, reached from `$8C28`)
and `$98A7 CALL $BF39` is `poolClearChain()` (written, reached from `reset()`).
TRAPS #58's shape twice more.  MEASURED with the targets POISONED, because on a
plain round1_48 each writes ZERO bytes -- `$957E` draws nothing while the masks
are `$00`, and `$BF39`'s stores all agree with what is already there.  Poisoned:
`$957E` writes 204 (96 display, 96 shadow, 12 attributes -- twelve letters times
8+8+1) and `$BF39` writes 411 (28 sparkle, 383 bank).

## $94C2 -- the EXTEND completion (reached from $948F)

MEASURED by `tools/extcomp.py` into `build/extcomp_fixture.json` on `extcomp`, a
real round-9 state already holding five of six letters; gated in
`test/bb.test.js`; engine `BB_Game.extendComplete` with `extendWipe`,
`extendReveal` and `extendBanner`.

**It is a 4.9-second cutscene that ends by advancing the round.**  MEASURED:
**17,162,734 T, 245.6 frames**, from `$94C2` to `$8D09`.

**The gate.**  `LD A,(IX+$63) / SUB $3F / RET nz` -- all six letters.  Swept over
all 256 values for BOTH players, with the accepted case ABORTED one byte past the
`RET nz` rather than executed 512 times.  `$94C8` then stores the A the SUB left,
which is zero, so the letters clear.

**Both ISR pass gates go down and neither comes back up.**  `$94CD`/`$94D0` zero
`($FEC4)` and `($FEC5)` inside a `DI .. EI`, and nothing in the routine restores
them -- MEASURED, both are still 0 at `$9553`.  That is safe only because the
exit is the round advance, whose `$9AC1` table zeroes them anyway.  The `A=2 /
CALL $8E0A` between them is a `$C9 RET` on the 48K branch and mutes nothing.

**`$87B2 := $C9` TURNS ITEM COLLECTION OFF** for the whole display, and `$956C`
restores the shipped `$00`.  `$87B2` is the FIRST BYTE of the player-vs-item
overlap routine and `$86B9`/`$86C5` CALL it -- a fifth opcode-as-mode-switch
after `$92DE`, `$93C4`, `$A82D` and `$9102`.  The patch exists so the player
cannot eat the decorative food the fanfare paints.

**The wipe is 6,912 bytes, `$E000..$FAFF`** -- the display window PLUS the colour
shadow.  `shadowClear()` (`$9858`) does 6,144 and stops at `$F7FF`, so **it
cannot be reused**.  MEASURED with the window poisoned as one contiguous run with
no gaps and both edges intact.  It misses live state by 641 bytes.

**`$856C`'s eight writes** are the EVEN half of eight of the twelve pairs, and
`$806C` de-interleaves them into `$85B1..$85B8` three instructions later, so this
blanks the lives icons' platform texture to match the wiped playfield.  The
result is byte-for-byte `BB_TILE_SEED`.

**`$8C14` is `$8C28` with a twenty-byte prefix**: `RES 7,(HL) / ADD HL,DE / DJNZ`
seven times from `$FD9B` and twelve times from `$FEDF`, both at stride ten --
nineteen slots -- and then it FALLS INTO the reveal.

**The shower is 320 writes into 32 bytes, ten times over.**  `$9509`'s
`LD IX,$9605` is INSIDE the outer loop, so every pass rewrites the same sixteen
records and only the last survives.  `byte0 = ((E-1) << 4) | (draw AND 3)` and
`byte1 = ((B+1) << 4) | 4`, E running 16..1 and B 10..1; **four `ADD A,A` in each
chain, not three**.  Exactly 160 PRNG draws at `$950F`, and ten item passes
through `$8689`.  The ageing those passes would do is gated on `($86CD) AND
($86CF)`, which is non-zero here, and `$8689` never INCs that tick -- so byte1
survives as `$24` and not `$25`.

**The two delays** go through `$9573`, whose cost the port already models by
counting.  The registers at each site were read out of the machine: `$9553` runs
with **A=207, B=0** (119.97 frames) and `$955E` with **A=45, B=4** (112.18).
**A at the first site is the banner's own attribute byte**, left in A by `$994F`,
so the first pause is that long because of the colour of the banner.  **(M7.57:
the second site's A and B are what `$806C` leaves -- (45, 4) is extcomp's, with
player two out of play; with player two in it they are `($5AC0)` and 5, and the
completion is 124K T shorter.  See "$94C2 IN TIME".)**

**`$9561` is three instructions, not the two calls above it.**  `$9568`'s `JR nz`
displacement is `$F7`, targeting `$9561`, past `$955B` and `$955E`.  **(M7.57: IX
there is NOT the player's -- `$955B`'s `$806C` leaves it at `$85B9` -- so the `DEC`
runs `$861C`, the byte before the ink table, until it is zero: 256 times from the
`$00` it holds.  The letters were already zeroed at `$94C8`; both readings end at
zero.)**  The `BIT`'s flags are discarded by the `DEC`, so it reads a byte and
changes nothing.  A reading that put the calls inside would make the routine
minutes long.

**The exit awards a life and advances the round.**  `$9558 INC (IX+$5C)`, then
`$956A POP HL / POP HL` discards its caller's return address AND `$948F`'s, and
`$9570 JP $8D09` is `CALL $97F8`.  The port models it with `extendAdvance`, the
same shape `paused` has for `$8FE7` -- and since M7.57 the advance WAITS for the
completion's 17.1M T to drain (`chainWalk`'s 'extend', `mainLoop`'s resume).

`$801D`, the double-height text printer, builds its glyph address as `$3C00 +
8*code` -- the Spectrum ROM character set -- so "N I C E      P" is drawn in the
port's substitute face (`BB_BANNER_FONT`, since M7.41; this paragraph once said
"counted and not drawn").  `$994F` itself IS
transliterated: two rows of fourteen attribute cells at `$5969` and `$5989`,
`$995A`'s `OR $40` turning `$8F` into `$CF`.  `$9AB3` is character 10 of the
string and carries `'1'` or `'2'` from bit 0 of `(IY+$5A)`.

## $801D / $802E / $8058 -- the banner printer and its double-height mode

MEASURED by `tools/banner.py` into `build/banner_fixture.json`; the substitute
font is `tools/make_banner.py` -> `build/bannerfont.json`; gated in
`test/bb.test.js`; engine `BB_Game.bannerDouble`, `bannerPrint`,
`bannerCellSingle` and `bannerCellDouble`.

**`$803C` is the printer's MODE** -- the operand of `$803B`'s `CALL nn`, holding
`$804F` (single height) or `$8058` (double).  `$801D` is its bracket: `$8020`
writes `$8058`, prints, and `$802A` puts `$804F` back.  MEASURED on all three
strings: the operand reads `$804F` before, `$8058` at EVERY glyph call, and
`$804F` after.  Its tape value is `$804F` on every state.

**`$802E` walks the string from IX** until a NUL, taking the glyph address from
`$8044` as `$3C00 + 8*code` and advancing the destination with `$803F`'s
**eight-bit `INC L`**.

**`$8058` IS TWO CHARACTER CELLS.**  `PUSH HL / CALL $8061 / POP HL /
LD BC,$20 / ADD HL,BC` and then it FALLS INTO `$8061` again: four source rows go
into the cell at HL and four into the cell below, each written TWICE.  MEASURED
as sixteen writes from eight source rows, `$4869..$4F69` then `$4889..$4F89`.

**THREE ADDS, THREE WIDTHS, and each measured on its own boundary:**
- `$803F INC L` is EIGHT BIT.  From `$48FE` the writes land at low bytes `$FE`,
  `$FF`, `$00` and never leave pages `$48..$4F`.
- `$8054`/`$8066`/`$8068` `INC H` is EIGHT BIT.  From `$FC40` the pages walk
  `$FC $FD $FE $FF $00 $01 $02 $03`.  (In the port this mask is absorbed by the
  address truncation -- TRAPS #156 -- but the wrap itself is real and gated.)
- `$805D ADD HL,BC` is SIXTEEN BIT.  From `$48FE` the second cell lands at low
  byte `$1E` of page `$50`, so the glyph touches NINE pages, one more than a
  single cell can.

**The three strings.**  `$9A1C` "HURRY UP !" at single height (`$9037`),
`$9A9F` "PERFECT !" at `$484B` double (`$8F78`, two hundred and fifty-six
times), and `$9AA9` "N I C E      P" at `$4869` double (`$94C2`), with `$9AB3`
-- character 10 -- overwritten by `'1'` or `'2'` at `$94E7`.  The port seeds all
three into the byte image at their machine addresses, so that overwrite works
the way the machine's does instead of being a special case.

**ONE PRINTER AND ONE FONT (M7.27).**  `hurryGlyphs` used to carry a
position-indexed font and its own eight-row blit -- a second transliteration of
`$802E` beside the general one.  It is `LD IX,$9A1C / CALL $802E` now and
nothing else.  `tools/make_hurry.py` is retired and `build/hurryfont.json` is
kept FROZEN as the record of what M7.20 drew, so the suite can assert the
unification was PIXEL-NEUTRAL: the surviving font must reproduce that record
cell for cell, including the repeats (R at positions 2 and 3, U at 1 and 6, the
space at 5 and 8) which are now one cell reached twice.

**THE FONT IS A DECLARED DEPARTURE, indexed by character code.**  Fifteen 8x8
cells drawn for this port; 67 of 112 bytes differ from the ROM's.  The assert is
a MINIMUM of three differing bytes per inked glyph, not merely inequality -- the
first drafts of T and F managed one and two (TRAPS #155).  The seven codes
"HURRY UP !" uses keep `make_hurry.py`'s exact bytes, so M7.20's banner does not
move a pixel.  The space is eight zero bytes in any font and is exempt in both
directions.  A character with no substitute glyph is COUNTED, never silently
blanked: the image's other strings ("ROUND", "READY", "CREDIT", "WELL DONE") go
through this same routine from call sites that are still stubs.

## $98C4 / $98D4 and $9904 -- the round banner's glyphs and its painter

MEASURED by `tools/roundbanner.py` into `build/roundbanner_fixture.json`; gated
in `test/bb.test.js`; engine `BB_Game.bannerRow` and `bannerErase`.

`$98B5`'s round banner is a ~1-second animation that ERASES ITSELF: 256 passes,
each drawing two text rows and twenty attribute cells, then `$98E4`/`$98EA` call
`$9904` twice to put everything back.  M7.7-R1b gated the COST and the iteration
count while the draw and the erase were counted stubs; M7.28 wires both.

**`$98C4` AND `$98D4` ARE TWO CALLS ON ONE POINTER.**  `$98BD` seeds IX at
`$9A06` and `$802E`'s own `INC IX` carries it past the NUL, so the second row
prints "READY    !" **without its address ever being named**.  MEASURED: IX is
left at `$9A11` after the first call and `$9A1C` after the second.  And `$98BD`
is INSIDE the DJNZ loop, so all 256 passes start the chain again -- a port that
seeded IX once would print "HURRY UP !" on the second pass.

**The round NUMBER is in the string, not beside it.**  `roundDigits()` writes
ASCII into `$9A0E`/`$9A0F` and the printer picks it up like any other character.
A leading zero is SUPPRESSED, so rounds 1..9 leave `$9A0E` at whatever it last
held -- which is why `$97C4` (fed by `$97C2 LD A,$20`) blanks it to a space at
new-game.  The tape's own copy reads "ROUND    0" (`$20 $30`); the port's "9" was
lifted from extcomp, the one shipped world holding it, and M7.41 corrected it.

**`$9904` RESTORES FROM THE SHADOW AND DERIVES THE ATTRIBUTES.**  Ten bytes by
eight rows LDIRed back from display + `$A000`, then ten attribute cells rebuilt
from bit 5 of the COLOUR shadow -- `($8309)` where clear, `($830A)` where set,
the same derive `$8C2B` does over the whole screen.  MEASURED with the display
poisoned and the shadow given a known pattern: **80 display writes and 10
attribute writes per call and nothing else.**

**THREE WALKS AT TWO WIDTHS, and the two real addresses show none of them.**
The LDIR is SIXTEEN BIT; `$9914`/`$9915`'s `INC H`/`INC D` are EIGHT;
`$9933`/`$9934`'s `INC E`/`INC L` are EIGHT; and `$9938`'s derive masks with
`AND 3`.  At `$484C` and `$488C` none of those can bite.  Driven from `$7AFA`
and `$60FA`, which between them carry the LDIR out of its low byte, wrap the
attribute run, and put the `AND 3` on a page where `OR $58` cannot absorb it.
(`$9925`'s `LD C,$40` is never read -- C is dead at this call site.)

**One mask IS unreachable**, established by enumeration rather than by sample:
`INC D`'s eight-bit wrap needs a start page above `$F8`, and every such wrap
lands in `$00xx`, where the machine writes nothing.

## $8E9D / $8EA7 -- the boss banner, and the last $802E call site

MEASURED by `tools/bossbanner.py` into `build/bossbanner_fixture.json`; gated in
`test/bb.test.js`; engine `BB_Game.bossBanner`, called from `bossDeath`.

    $8E7A  LD IX,$9A27 / LD HL,$484B / LD A,$85 / LD B,11 / CALL $8E9D
    $8E9D  PUSH HL / EX AF,AF' / CALL $A090 / EX AF,AF' / CALL $995A / POP HL
    $8EA7  JP $802E

**ONE HL ADDRESSES BOTH RUNS.**  `$A090` turns the display address into its
attribute address, `$995A` paints B cells there, and then the SAME HL -- popped
back at `$8EA6` -- is where the glyphs go.  The `EX AF,AF'` pair exists only
because `$A090` clobbers A, which is carrying the attribute.  `$8EA7` is a JP,
not a CALL, so `$802E`'s RET returns from `$8E9D`'s caller.

**AND THE TWO RUNS ARE DIFFERENT LENGTHS.**  `$8E83` loads B with **eleven** and
"WELL DONE!" is **ten** characters: `$995A` is bounded by B and `$802E` by the
NUL, so the attribute run is one cell wider than the text.  MEASURED at the
shipped `$484B`: 11 cells `$594B..$5955` all `$C5`, 80 glyph writes over eight
sub-rows, IX left at `$9A32` -- one past the NUL.

**BOTH EIGHT-BIT WALKS, driven where they wrap.**  The shipped call reaches
neither.  From `$48FA` the attributes run `$59FA..$59FF` and wrap to
`$5900..$5904`, all inside page `$59`, while the glyphs wrap the same way inside
pages `$48..$4F` -- two independent `INC L`s, neither leaving its page group.

**`$995A` ORs `$40` INTO THE VALUE**, so the byte the instruction loads is never
the byte that lands.  On the one attribute this site ships, "it ORs `$40`" and
"it writes `$C5`" are the same sentence, so it is SWEPT over seven values:
`$85 -> $C5`, `$47 -> $47`, `$00 -> $40`, `$3F -> $7F`.

**IT IS NOT THE LAST `$802E` CALL SITE, THOUGH M7.29 FIRST SAID IT WAS.**  A
byte grep for the address finds NINE references; I had counted the six strings
in `BB_BANNER_STR` instead.  Five are wired -- `$8024` (inside `$801D`),
`$8EA7`, `$9114`, `$98C4` and `$98D4` -- and **four are not**:

| site | what it prints | state |
|---|---|---|
| `$7FE9` | the HUD's top row, `IX = $85C1`, `HL = $4000` | counted |
| `$7FEF` | ...and its second row, IX carried | counted |
| `$8CEE` | "GAME OVER" at `$9A95` -> `$484C` | counted |
| `$9758` | "CREDIT n" at `$9AB8` -> `$50F7` | counted |

The six strings that ARE wired -- `$9A06`, `$9A11`, `$9A1C`, `$9A27`, `$9A9F`,
`$9AA9` -- draw their glyphs from the substitute font, and a CENSUS row in the
suite now holds both halves of that sentence so the next coverage claim has to
agree with the source.

## $9751..$9764 -- the CREDIT line, and the table above it

MEASURED by `tools/creditline.py` into `build/creditline_fixture.json`; gated in
`test/bb.test.js`; engine `BB_Game.creditLine`.  **Transliterated and gated but
NOT CALLED** -- see below.

    $9751  LD IX,$9AB8 / LD HL,$50F7 / CALL $802E
    $975B  LD HL,$5AF7 / LD A,5 / LD B,9 / CALL $995A

"CREDIT 6" from `$9AB8` at `$50F7`: eight characters, 64 display writes, then
NINE attribute cells at `$5AF7..$5AFF` written as `$45` -- `$975E` loads 5 and
`$995A` ORs `$40` in.  IX is left at `$9AC1`.

**THE NINTH ATTRIBUTE CELL IS `$5AFF`, THE LAST CELL OF THE ATTRIBUTE FILE.**
The glyphs cover columns 23..30 and the attribute run covers 23..31, so the run
fills the bottom row to the screen edge while the text stops one short.  Same
count-versus-terminator asymmetry as `$8EA7` (11 cells under 10 characters).

**~~AND THE OFF-BY-ONE BELONGS TO THE HAND-CODED CALL SITES.~~ WRONG -- SEE
M7.31 AND TRAPS #169.**  There are THREE hand-coded sites and this generalised
from two of them; `$8CF6` loads NINE cells for a nine-character string, in the
same row and the same columns.  What the measurement supports is the narrower
claim: **the table is exact where two of the three hand-coded sites are not.**
The four strings above this one are drawn from the COLUMN-MAJOR table at `$9A85`
-- `LD L,(IY)` and `LD H,(IY+4)`, four parallel arrays of four: display lows,
display highs, attributes, cell counts -- and its counts match their lengths
EXACTLY:

| display | attr | cells | string | length |
|---|---|---|---|---|
| `$4045` | `$07` | 24 | "B U B B L E  B O B B L E" | 24 |
| `$4806` | `$06` | 21 | "By Software Creations" | 21 |
| `$4867` | `$03` | 20 | "Program: Mike Follin" | 20 |
| `$502A` | `$8C` | 14 | "1 OR 2 TO PLAY" | 14 |

IX is seeded ONCE at `$9A32` and `$802E`'s own `INC IX` chains all four.  Four
out of four exact, against `$8E83`'s 11-for-10 and `$9760`'s 9-for-8 -- so the
printer is not the thing that is off.  `$8CF6`'s 9-for-9 says the CALL SITE is
not reliably the thing that is off either: it is two separate pieces of slack in
two separate routines.

**WHY IT WAS NOT CALLED (until M7.42).**  `$9758` is reached by FALL-THROUGH from
`$9729`'s title text block, whose four strings needed substitute glyphs INCLUDING
LOWERCASE, and `gameReset()` stopped at `$970B` with the title screen named out as the
front-end increment's.  So `creditLine` sat in the UNCALLED census until M7.41 gave it a
caller (`titlePaint()`) and M7.42 wired that into `gameReset()` through `titleEnter()`.

**The font needed nothing new**: C, R, E, D, I, T, space and 6 were all already
drawn for "PERFECT !", "READY    !" and the round number.

## $8CDC..$8D02 -- GAME OVER, and the glyphs B1 declared

MEASURED by `tools/gameover.py` (`phase_glyphs`, `phase_handcoded`,
`phase_802e_refs`) into `build/gameover_fixture.json`; gated in `test/bb.test.js`;
engine `BB_Game.gameOverBanner` / `gameOverFrame`.  The H13-B1 increment measured
this screen's countdown, its three `$FEC9` writers and its reset; **M7.31 closed
the one thing B1 declared, the glyphs.**

    $8CDC  LD HL,0 / LD ($FEC4),HL       both ISR gates down in ONE 16-bit store
    $8CE2  LD A,5 / CALL $8E0A           $C9 RET on the 48K branch -- does nothing
    $8CE7  LD IX,$9A95 / LD HL,$484C / CALL $802E
    $8CF1  LD HL,$594C / LD A,14 / LD B,9 / CALL $995A
    $8CFB  HALT                          one frame per pass
    $8CFC  LD HL,$FEC9 / INC (HL)
    $8D00  JR nz,$8CE7                   back to the DRAW, not to $8CDC

"GAME OVER" from `$9A95`: nine characters, **72 display writes** at `$484C`, IX
left at `$9A9F` -- which is `"PERFECT !"`, so the two strings are adjacent in the
block -- and nine attribute cells of `$4E` at `$594C..$5954` (`$8CF4` says
`LD A,14`; the `$40` is added INSIDE `$995A`, so the value read and the value
written differ).  Zero stray writes in the poisoned row.

**AND THIS SITE IS EXACT, WHICH FALSIFIED WHAT M7.30 WROTE ABOVE.**  Glyphs and
attributes both cover **columns 12..20 of character row 10** -- measured as rows
and columns, not inferred from `$484C` and `$594C` looking alike -- and nine
cells sit under nine characters.

**THE FULL COUNT IS FIVE OF SEVEN, AND IT TOOK FOUR TRIES TO GET THERE.**
`phase_handcoded` enumerates every entry to `$995A` -- `CALL` **and** `JP`, since
`$A04B` and `$A08D` reach it by jump and a `CD 5A 99` census cannot see them --
and asserts that every site with an immediate `B` is named.  That assert found
`$9074` on its first run:

| `LD B` at | string | text | length | cells | |
|---|---|---|---|---|---|
| `$98CA` | `$9A06` | "ROUND    1" | 10 | 10 | exact |
| `$98DA` | `$9A11` | "READY    !" | 10 | 10 | exact -- IX CHAINED, not named |
| `$9948` | `$9A1C` | "HURRY UP !" | 10 | 10 | exact -- COMPUTED address |
| `$9074` | `$9A1C` | "HURRY UP !" | 10 | 10 | exact -- the same ten cells, FLASHED |
| `$8CF6` | `$9A95` | "GAME OVER" | 9 | 9 | exact |
| `$8E83` | `$9A27` | "WELL DONE!" | 10 | **11** | slack +1 |
| `$9760` | `$9AB8` | "CREDIT 6" | 8 | **9** | slack +1 |

`$9074` is the hurry-up banner's SECOND run on one strip: `$9948`'s paints it from
a computed address (`$9103` builds L from `(IX+2)+11`, and `$9940` maps H through
`$9938`), and `$9074`'s flashes it from `$9068`'s border loop with the colour in
the operand at `$9077` (`XOR 5` alternating 6 and 3).

**And no story survives the count.**  "Ten-character strings are exact, odd
lengths carry a spare" is the obvious pattern and `$8E83` kills it.  Five of seven
are exact; nothing about the strings separates the two that are not (TRAPS #169).

**`$802E`'s reference census is DATA now, not a label constant.**  Nine
references: eight `CALL` (`$7FE9 $7FEF $8024 $8CEE $9114 $9758 $98C4 $98D4`) plus
ONE `JP` (`$8EA7`), so a `CD 2E 80` census alone finds eight of nine -- the same
shape as `phase_writers` finding two of `$FEC9`'s three writers.  **SIX draw on a
path the port runs** (`$8024` inside `$801D`, `$8CEE`, `$8EA7`, `$9114`, `$98C4`,
`$98D4`), ONE was transliterated but uncalled (`$9758`, wired M7.42), and **TWO were untouched:
`$7FE9` and `$7FEF`, the HUD's two rows from the buffer at `$85C1`.**

**The font needed G, M and V** -- drawn against the ROM's cells after reading
them, not drawn blind and checked afterwards: 5, 6 and 6 of eight bytes differ.
`make_banner.py` also gained an assert nothing had: **no two inked glyphs may be
the same eight bytes**, which the ROM-diff assert cannot see and which O/0 and
V/W are the pairs most at risk of.  31 codes now (49 since M7.41: `: B` and fifteen
lowercase for the title screen).

**`phase_screen`'s `bitmap_changed` is 51, not 72**, and NOT because its snapshot
is stale -- `frames()` stops AT `$8CDC` with `$484C` = `$7F`, nothing drawn.  Of
the 72 writes, **24 are `$00`** (every glyph's blank top and bottom row, plus the
space) and **21 of those land on a byte already holding `$00`**: 72 - 21 = 51.
**There is no CLS** -- the banner draws onto the live play field -- so 51 is a fact
about `round1_48`'s wallpaper, not about the banner.  Sound for a gate asserting
`> 0` against an engine drawing none; not a number to compare a drawing engine
against (TRAPS #172).  Both numbers are in the fixture and a row asserts the
inequality.

**TWO MUTATIONS SURVIVED UNTIL A SPY ROW EXISTED, AND WERE NOT WITHDRAWN.**
`attrRun(_, _, $4E)` is indistinguishable from `$0E` in the bytes, because `$995A`
ORs `$40` and `$4E` already carries bit 6; and painting the attributes before the
glyphs cannot change a byte, because the runs are disjoint.  Both are REAL
behaviour that leaves no trace in RAM -- the machine's instruction is `LD A,14`
and `$8CEE` precedes `$8CF8` -- so a spy on `attrRun`'s ARGUMENT and on the call
ORDER gates them, and the two dead B1 anchors they superseded are re-anchored
rather than retired.  Withdrawing a provable equivalent is the fallback, not the
first move.

**What is left of the departure is the FACE of the letters and nothing about
where they go.**

## $7F80/$7FAF -- the round number, and the bytes no check read

MEASURED by `tools/roundbuild.py`'s `phase_digits` into
`build/roundbuild_fixture.json`; gated in `test/bb.test.js`; engine
`BB_Game.roundDigits` / `digitGlyph`.  **M7.32 fixed a live bug here that had been
green for weeks, and the fix exposed a second one.**

    $7F83  CP $51 / RET z               round 81 draws nothing at all
    $7F86  LD E,$FF / the divide        tens and units by repeated subtraction
    $7F91  OR A / JR z                  the TENS branch is suppressed below 10
    $7F94  CALL $8042 / LD ($9A0E),A    ASCII into the banner string
    $7F9A  LD DE,$E040 / CALL $7FAF     the tens glyph
    $7FA0  LD ($F840),A                 colour, TENS BRANCH ONLY
    $7FA6  CALL $8042 / $7FA9           units ASCII into $9A0F
    $7FAC  LD DE,$E041                  falls through into $7FAF
    $7FAF  INC HL                       the SOURCE past glyph row 0 -- THIS is the +1
    $7FB0  EX DE,HL
    $7FB1  INC H / LD B,7               the DESTINATION page, $E0 -> $E1
    $7FBA  LD A,7 / LD ($F841),A        EVERY call, including the tens one

**FAULT ONE -- the font was indexed FLAT.**  `BB_DIGITS[digit * 8 + i + 1]` on a
table of ten eight-element arrays is an inner Array for 0..9 and `undefined` above;
a `Uint8Array` store coerces both to **0**.  Every digit drew seven zero bytes.
`scoreGlyph` indexes the same font correctly, so the two consumers disagreed about
its shape.  No check could see it: the fixtures record destinations and no VALUES,
and the nearest row requires a non-empty SUBSET of the machine's glyph addresses --
**all-zeros is a valid subset** (TRAPS #173).

**FAULT TWO -- the argument is a CODE, not a digit**, which the diagnostic added
with fault one's fix found on its first run.  `$8042` adds `$30` and `$8044` indexes
the charset with the result, so the machine draws whatever cell that lands on;
`$7F86`'s divide leaves `tens` as high as 25 for a byte round counter, so round 128
draws `'<'` and round 255 `'I'`.  `$9877`'s oracle sweeps a round in that range, so
the suite had been driving the broken domain all along -- invisibly, because a
lookup wrong for every input is equally wrong at 8 and at 12 (TRAPS #174).

**THE MODEL NOW**: `code = digit + $30`, cells for `'0'..'9'` only, and anything
else is a DECLARED GAP that is **counted** (`digitMissing`) rather than drawn as
zeros.  `$7FBA`'s colour write stays OUTSIDE that branch, because the machine runs
it on every call including one whose glyph this port cannot draw.  **In play there
is no gap**: rounds run 1..80, so tens is 0..8 and units 0..9 -- verified over all
eighty.

**MEASURED destinations** (`phase_digits`, by diff): `$E141..$E741` for the units
digit and `$E140..$E740` for the tens, seven shadow rows each on an eight-bit
`INC H` with L fixed -- 7 changed bytes on rounds 1 and 2, 14 on round 11, **0 on
round 81**.  The glyph's own row indices are 1..7; row 0 is never written.

**AND THE GATE IS VALUE-BASED NOW.**  Six rows: the bytes at every measured
address computed from the port's own `BB_DIGITS` with the shadow POISONED so a
matching write is still visible; the `+1`, stated against digits whose head and tail
differ so a missing offset cannot pass; the DOMAIN, with the declared gap counted
and `$7FBA` still running; the SHAPE, driving both consumers of `BB_DIGITS` so that
one font cannot have two dimensions again; the COLOUR writes, 0/1, 0/1, 1/2 and 0/0
for rounds 1, 2, 11 and 81 and scoped to `$7F80` alone because four other routines
write those two addresses over a whole `$7F1B`; and the premise that
`changed.length` is not a write count.

## The value-coverage sweep -- what else was never compared

A five-printer audit ran alongside the fix, classifying every check that observes a
printer's output as (A) exact values against the port's own font, (B) destinations
only, (C) a subset/count relation, (D) a spy, or (E) nothing.  What it found, and
what M7.32 closed:

**CLOSED HERE:**

* **`extendGlyph`'s SHADOW half was (B) -- the same fault one buffer over.**
  `$95A7` writes every byte TWICE, `ram[hl] = v; ram[sh] = v;`, and only the display
  copy was compared against `BB_LETTERS`; the shadow clause compared ADDRESSES.  A
  mutation putting the right byte on screen and `$00` in the shadow passed.  No live
  bug -- both writes take the same `v` -- but the gate could not have told.
* **`BB_DIGITS` had NO GATE AT ALL.**  `build/digits.json` existed since 16
  September, byte-identical to the engine's table, **unregistered in `port.json`**,
  read by nothing.  Registered now, with a row comparing the two cell for cell.
  `make_digits.py`'s assert was `rom[d] == DIGITS[d]` -- **whole-cell inequality**,
  which the ROM glyph with one byte changed satisfies (TRAPS #155, which
  `make_banner.py` was fixed for and this tool was not).  Now a MINIMUM of 3 with
  per-glyph counts recorded: 62 of 80 bytes differ, closest digits 6 and 8 at 5 of 8,
  so all ten already cleared it.  Plus a duplicate-cell assert.
* **The row that catches unread fixtures could not see an UNREGISTERED one**, because
  it iterates `port.json`.  A directory guard replaces the silence (TRAPS #175):
  eight intermediates and **fourteen orphans no tool writes and no check reads**.
* **`BB_LETTERS[0]` and `[3]` are the same eight bytes, and that is FAITHFUL** -- the
  machine's table at `$95D5` names the same charset cell twice.  Nothing asserted it,
  so the font's two consumers agreed by coincidence: `bankGlyph` finds its index with
  `indexOf`, which can therefore never return 3, while `extendGlyph` reaches `[3]` by
  position.  Both the duplicate and the count of five distinct cells are asserted now.

**STILL OPEN, and named rather than left to be rediscovered:**

* **`scoreHud` (`$816B`) is (B)/(D).**  Its only driver replaces the blitter with a
  stub whose body is `void digit` and whose comment says *the renderer's ADDRESSES --
  never its pixels*.  `scoreHud` appears nowhere else in the suite.
* **`treasurePerfect` is (C)** -- three counts and no byte, though the routine is (A)
  at the same address through another row.
* **`bannerRow` (`$98C4`/`$98D4`) is (D)** -- all three `roundBanner()` rows spy on
  destinations, and one says out loud that *the DISPLAY row goes somewhere this check
  does not look*.  Its glyphs are value-checked only by a row calling `bannerPrint`
  directly.
* **`extendBanner` is (C)**, partly (A) for the `$9AB3` digit cell alone.

Well covered (A), for contrast: `bannerPrint` at ten sites, `bannerCellSingle` and
`bannerCellDouble`, `bannerDouble` at five, `hurryGlyphs`, `gameOverBanner`,
`bossBanner`/`bossDeath`, `creditLine`, and `elementBank`/`bankGlyph` at 384 bytes
across thirteen classes.

**And one reason the whole-image differentials could not have caught `$7FAF`:**
`roundbuild`'s `sequence.mask` is exactly the sixteen glyph addresses `$E140..$E841`
and nothing else, so the whole-shadow and whole-64K diffs were structurally blind to
them, and the CRC anchor compares a capture taken at `$7F7D` -- upstream of the
fall-through into `$7F80`.

## $AD65 -- the player's jump arc, and the gate the port had backwards

MEASURED by `tools/jumparc.py` into `build/jumparc_fixture.json`; gated in
`test/bb.test.js`; engine `BB_Game.playerJumpFall`.  **NOT** `tools/jumpsfx.py`, which
is `$8FA5`'s TONE -- a different routine reading the same `$B57D` table with a
different index base.  Nothing drove the arc MOVER before M7.33.

    ACF0  LD A,(IY+9) / OR A
    ACF4  JP m,$AD11                   bit 7 set -> FREE-FALL
    ACF7  JP nz,$AD65                  non-zero  -> THE ARC   <-- the phase-0 guard
    ACFA  CALL $ADAA                   zero      -> GROUNDED
    AD65  CALL $ADAA                   the horizontal step
    AD68  LD A,(IY+9) / LD L,A / DEC L L = phase-1, EIGHT BIT, L ALONE
    AD6D  INC A / CP $21 / LD A,$FF    the NEW phase, clamped 33 -> $FF
    AD74  LD (IY+9),A                  STORED BEFORE THE PROBE DECIDES
    AD77  LD H,0                       THE INDEX IS UNSIGNED
    AD79  LD DE,$B57D / ADD HL,DE
    AD7D  CP $10 / JR nc,$AD90         THE NEW PHASE AGAINST 16
    AD81  LD A,(IY+6) / ADD A,(HL) / LD (IY+6),A
    AD88  CP $C0 / RET c / LD (IY+6),0 the plain step's wrap -> 0
    AD90  LD ($ADA1),HL / ...probe... / JR nz,$AD81 / JP $AD51
    AD51  LD (IY+9),$FF / ADD A,2 / CP $BF / LD (IY+6),2

**THE DESCENT PROBE IS GATED ON THE NEW PHASE, NOT ON THE SIGN OF THE DELTA.**  The
port tested `dy > 0`, first true at phase 19; `$AD7D` tests A, which is the new phase,
so the machine probes from **old phase >= 15**.  Phases **15, 16, 17, 18** are exactly
the table's zero-delta entries, and the port skipped the probe on all four.  MEASURED
with floor on the probe row against a cleared control on two 48K captures: on floor
those four divert to free-fall (`Y += 2`, phase `$FF`) where the port left them on the
arc with Y unchanged.  **REACHABLE** -- a short hop whose apex has floor 16 px below --
and the image's own residue `($ADA1) = $B58B` is index 14, phase 15 (TRAPS #178).

**TWO BOTTOM WRAPS, AND THEY ARE NOT THE SAME WRAP.**  `$AD88 CP $C0` on the plain step
lands on **0**; `$AD5D CP $BF` in the free-fall tail lands on **2**.  Measured first
wraps: plain from Y `$BE`, free-fall from Y `$BD`.  The port used `(y + dy) & 0xFF` for
both, and a single mask cannot express two wraps (TRAPS #179).  `playerFloorTick` shares
the second tail and now carries it too.

**PHASE 0 IS UNREACHABLE AND THE PORT REFUSES IT.**  `$ACF7 JP nz` is the guard,
`$AD65` has ONE reference in 64K, and a sweep of 3,055 breaks at the indexing
instruction across ten 48K captures saw every phase 1..32 and never 0.  The port used to
compute `BB_ARC[-1]` = `undefined` and move the player to **Y=0**; the machine has no
negative index -- `$AD6C DEC L` decrements L alone and `$AD77 LD H,0` forces the high
byte -- so phase 0 gives an **unsigned 255**, landing on **`$B67C`** (= `$FD` = **−3**),
**not** on `$B57C`, the byte before the table.  141 pixels apart.  `$B67C` is the `$FD`
prefix of `INC (IY+4)`, so the machine's phase-0 delta is determinate by accident of an
opcode.  The port throws.

**THE INDEX IS ONE FLAT UNSIGNED BYTE.**  Verified flat for every phase 1..32 and for
33 and 40, where the machine walks straight into the next arc tables.  The port's two
arrays and its `(idx - 24) & 7` became ONE 32-entry table: the mask was a no-op over
phases 25..32 (indices 24..31) and wrong above, and `$AD6E CP $21` clamps 33 to `$FF`
before the store so nothing above 32 is ever indexed -- the same dead guard M7.32
deleted (TRAPS #177).

**AND A PORT COMMENT WAS MIS-ATTRIBUTED** (fixed): the `BB_ARC` block described phases
1..31 reading `$B57E..$B59C`, which is the TONE read at `$8FC5` (indexed by PHASE), not
the ARC read at `$AD7C` (indexed by PHASE-1).  The code was right in both places; only
the comment named the wrong one.

## $AD18/$AE7F -- the floor tick does TWO probes, and the mask is a switch

MEASURED by `tools/jumparc.py`'s `phase_floortick` at `$AD18`'s OWN entry, not borrowed
from the arc path; engine `BB_Game.playerFloorTick` / `solidRow`.  **Three battery
survivors found this**, because `playerFloorTick` had no gate at all.

    AD18  LD E,(IY+5)                      X
    AD1B  LD A,(IY+6) / AND $FE / LD (IY+6),A   even-align, AND STORED
    AD23  ADD A,15 / LD D,A                D = the FEET row (Y+15)
    AD26  LD ($AD41),DE                    self-mod into $AD40's operand
    AD2A  LD A,($AE9C) / LD ($AD3B),A      save $AE9C
    AD30  LD A,$C9 / LD ($AE9C),A          PATCH $AE9C TO RET
    AD35  LD C,$20 / CALL $AE81            probe ONE: the feet row, mask $20
    AD3A  LD A,$E6 / LD ($AE9C),A          restore $AE9C
    AD3F  DEC E / JR z,$AD51               SOLID FEET -> FREE-FALL
    AD45  INC D / CALL $AE7F               probe TWO: the row below, mask $3F
    AD49  DEC E / JR nz,$AD51              CLEAR BELOW -> FREE-FALL
    AD4C  LD (IY+9),0 / RET                otherwise LAND

**LANDING NEEDS CLEAR FEET AND SOLID BELOW.**  The port modelled ONE probe and landed
wherever the row below was solid, regardless of the feet -- so it landed in worlds where
the machine falls.  Measured over three worlds (solid below, solid BOTH, neither) at nine
Y values: it lands only on clear-feet-and-solid-below, at Y `$60`, `$68`, `$B8`, `$C0`.

**And every one of those is a Y where `(Y & $FE) + 15` ENDS a character cell.**  The two
probes read different cells only then; anywhere else both read the same cell and landing
is impossible.  So **the machine lands only on an eight-pixel boundary, and nothing
checks for it** -- it falls out of the arithmetic.

**THE MASK IS NOT COSMETIC -- IT IS THE SWITCH ON A BOUNCE.**  After the probe decides a
cell is solid it runs `$AE9C AND $20`:

    AE9A  LD E,1
    AE9C  AND $20                  <- PATCHED TO RET around the FEET probe
    AE9E  JR z,$AEA1
    AEA0  RET                         solid under $20 -- an ordinary floor
    AEA1  BIT 1,(IY+8) / JR z,$AEAD
    AEA7  LD (IY+9),1 / POP HL / RET  sets the JUMP PHASE and UNWINDS past the caller

With `C = $20` that path is unreachable.  With `$3F` a cell solid only in bits 0..4 --
the walker's claim/release bits -- falls through, and with `(IY+8)` bit 1 set the probe
sets the jump phase to 1 and POPs the caller's return address.  **That is why the floor
tick patches `$AE9C` to `RET` for the feet probe and restores it for the row below**: to
choose which probe may bounce.

**THE BOUNCE IS NOT MODELLED**, and the three mask mutations are WITHDRAWN rather than
gated: re-measured over ten shipped 48K colour shadows, **zero** cells have any of bits
0..4 set, so `$3F` and `$20` select the same cells everywhere the suite can look -- and
the world that would distinguish them is exactly the world that reaches the bounce
(TRAPS #180).  Gating them against a half-modelled world would assert something false.

**Also still open:** `$AD90` self-modifies `$ADA1`/`$ADA2` with the arc pointer to
restore HL after `$AE7F` clobbers it, and `$AD26` self-modifies `$AD41`/`$AD42` with DE
-- four bytes of observable memory the port never writes, which any memory diff across a
jump or a fall will show.

## The three SILENT FALLBACKS, and why each is now counted

Gated in `test/bb.test.js`; engine `BB_Game.extendGlyph` / `scoreGlyph` / `driftDelta`.
TRAPS #174 (M7.32) says prefer a throw to a `|| FALLBACK[0]`, because a fallback is an
answer to a question you have then stopped asking.  Three were left standing in code
M7.32 and M7.33 touched.  **All three were UNREACHABLE, and each is now COUNTED or
REFUSED, with its unreachability driven rather than asserted.**

**1. `extendGlyph` -- the only division inside an index in the engine.**
`BB_LETTERS[(iy - $95D5) / 5]` is FRACTIONAL for any `iy` off the stride-5 grid: `$95F4`
gives `31 / 5 = 6.2`, and a fractional index is `undefined`, not an error.  `sub` was
then falsy and the loop fell through to `ram[de]` -- a ROM source this port leaves ZERO
-- writing **eight zeros to the display AND the shadow**, with no throw and no counter.
The `$7FAF` fault one buffer over (TRAPS #173).
Now `sub` has three distinct states: `null` (the source is not the charset -- read
`ram[de]` faithfully), an array (a substitute cell), and `undefined` (a charset source
with no substitute -- **counted as `extMissing`, nothing drawn**).  The loop still
ADVANCES on the gap path, because the attribute write takes its address from where `hl`
ended up.
UNREACHABLE and DRIVEN: `extendPass` walks `$95D5 + k*5` for k = 0..5, so every `iy` is
on the grid -- over all 256 masks and both column offsets, 512 passes and 1,536 glyph
calls, the counter stays at zero.

**2. `scoreGlyph` -- the `|| BB_DIGITS[0]` M7.32 half-closed.**  A BCD nibble of `$A..$F`
drew `'0'` silently; the machine draws `':'..'?'`, because `$8042` does `ADD A,$30` and
`$8044` indexes the charset with the result -- the same arithmetic `digitGlyph` models,
and M7.32 gave that one a counted gap.  **One font, two consumers, and until now two
different answers to "a cell I do not have."**  Now both count.
UNREACHABLE and PROVED over the whole input space, not sampled: `bcdAdd` matches a
reference `ADD`+`DAA` on all **131,072** `(x, y, carry)` triples, and BCD-in implies
BCD-out on every one -- so a score byte built by repeated award can never carry a nibble
above 9.  `BB_ITEM_VALUES` holds no non-BCD byte and `reset()` zeroes `$FFE1..$FFF0`.

**3. `driftDelta` -- a five-pair table read at an odd index.**  `BB_DRIFT` is ten entries
read as five pairs, so a pair starts at an EVEN index and `driftDelta(9)` ran off the
end, giving `[0, undefined]`.  An `undefined` delta propagates as `NaN` through arithmetic
and as **zero** through a typed-array store -- the `$7FAF` failure mode.  It throws now.
UNREACHABLE: the only caller passes `driftCode() & 6`, or the literal 8 that `$B968` uses
to null a RIGHT or DOWN wind (codes 2 and 4 only -- popkill N3/B3/B8).  Index 8 is `(0, 0)`,
which is that null.

**AND TWO OF THE ROWS WERE WRONG BEFORE THEY WERE RIGHT.**  The `extendGlyph` gap row
poisoned `$4000..$5800` and `$E000..$F800` and asserted nothing moved -- but the off-grid
`iy` it drove reads table bytes `00 00`, so `hl` is 0 and the writes land at
`$0000..$0700`, outside both regions.  Computing the sixteen addresses fixed that, and
the row STILL passed, because the ROM window is zero and "wrote zeros" is
indistinguishable from "wrote nothing" against a zeroed target.  The computed targets are
poisoned now (TRAPS #182).  And a range guard added with the `extendGlyph` fix was
provably dead -- `BB_LETTERS[k]` already returns `undefined` for every index the guard
rejected -- the second such guard in three increments (TRAPS #177).

## $AE9C..$AED0 -- the floor probe's ACTION tail, and the BUBBLE-JUMP

MEASURED by `tools/jumparc.py` (`phase_tail`, `phase_stamp`, `phase_attrib`) into
`build/jumparc_fixture.json`, from the read-first recon in
`scratchpad/recon/zzbounce.md`; gated in `test/bb.test.js`; engine
`BB_Game.floorProbe` / `probeCell` / `bubbleProbePop`.  **MODELLED IN M7.35.**  This section exists because M7.33 recorded the
`$3F`/`$20` mask difference as "observationally identical on shipped data" and withdrew
three mutations pending this measurement.  The measurement reverses the conclusion.

**THE BOUNCE IS REACHABLE: 21 hits at `$AEA7` over 67,540 measured video frames**, 48
captures by 7 key scripts, interrupts on, **nothing poked**.  The accounting closes
exactly:

    $AE7F   20635   the arc's probe entry (C = $3F)
    $AE81   37771   the floor tick's entries (C already loaded)
    $AE9A   12803   SOLID found -- the tail entered
    $AEA0   12512     ... bit 5 set: an ordinary floor
    $AEA1      50     ... bit 5 CLEAR: a BUBBLE under the probe
    $AEA7      21           ... jump HELD  -> THE BOUNCE
    $AEAD      29           ... jump clear -> pop the bubble

21 + 29 = 50, and 12803 - 12512 - 50 = 241 is the feet probe's patched-`RET` exits.  `IY`
at the probe is **only ever** `$FD80`/`$FD8A` -- a player record, never an enemy -- so
`(IY+8)` there is always the input mask.

**THE LOW FIVE BITS OF A COLOUR-SHADOW CELL ARE A BUBBLE INDEX.**  Claimed by `$B8C0`
(`AND $E0 / OR tag` -- the wall bit survives) and released by `$B6D6` (`AND $E0`), with
the claimed address cached in the bubble record at `+2/+3`.  The tag for slot *j* is
**`12 - j`**, range 1..12, from `$B63C LD ($BFF7),A` with `A = 12` counting down.
Verified over sixteen captures: **32 live bubbles, 32 matching cells, 0 misses.**  The
count of low-bit cells equals the number of live bubbles every time, which is why ten
captures with no bubbles gave zero (TRAPS #183).

**AND THE SAME BITS ARE PAINT DURING A REPAINT.**  `$8306`'s `LDIR` fill with
`$82F7 AND $47` keeps ink, so mid-repaint all 704 playfield cells carry low bits that are
colour.  In the steady state the map uses only the top three bits (TRAPS #184).

**`(IY+8)` BIT 1 IS "JUMP HELD THIS FRAME"**, written only by the input scan at `$ACEB`.
Bit 5 is the same key LAST frame, which is why `$AD00 BIT 1 / $AD04 BIT 5` is an edge
detector for starting a ground jump while `$AEA1 BIT 1` is a plain HELD test.  Set for
both players; the Kempston branch builds the same C at `$AF1D`.

**THE THREE BRANCHES:**

    $AEA0  RET                              bit 5 set -- an ordinary floor
    $AEA7  LD (IY+9),1 / POP HL / RET       bubble + jump HELD -> THE BOUNCE
    $AEAD  ...                              bubble + jump clear -> POP IT

**`$AEAD` is the exact inverse of the claim**: `12 - (cell & $1F)` recovers the slot,
`x10` the pool stride, `$FEDF` is slot 0's flags -- so HL lands on the flags of the
bubble that claimed the cell.  It sets bit 3 (burst) and bit 1 (emit element), and takes
attribution from `(IY+$5A)` bit 0 (`RES 4` for P1, `SET 4` for P2).  **And `$AEB9 LD E,A`
CLOBBERS the `E = 1` that `$AE9A` set**, so the caller sees "not solid" and the player
falls THROUGH the bubble it just popped.  That one instruction is the whole of "a bubble
is not floor".

**WHAT THE BOUNCE DOES**, driven from both entries with a wall control:

| phase in | cell | jump | phase out | Y | bubble flags | path |
|---|---|---|---|---|---|---|
| 0 | wall | clear | 0 | `$90` -> `$90` | `$84` | LAND |
| 0 | wall | HELD | 0 | `$90` -> `$90` | `$84` | LAND -- `$AE9C` found the wall |
| 0 | bubble | clear | **255** | `$90` -> `$92` | `$84` -> **`$8E`** | POP, then free-fall |
| 0 | bubble | **HELD** | **1** | `$90` -> `$90` | `$84` | **BOUNCE** |
| 20 | bubble | clear | 21 | `$90` -> `$91` | `$84` -> **`$8E`** | POP, arc continues |
| 20 | bubble | **HELD** | **1** | `$90` -> `$90` | `$84` | **BOUNCE** |

So: **Y does not move on the bounce frame**, the phase is re-armed to 1 from EITHER entry
(a jump off a bubble from the ground, a mid-air re-launch from the arc), and **the bubble
survives a bounce and is popped when jump is not held** -- bouncing rides it, falling
through pops it.

**The `POP HL` discards the INNER resume point**, `$AD49` (floor tick) or `$ADA0` (arc),
and SP moves by exactly one word, so the handler returns where a normal return lands:
`$AAEC`, the entity sweep's per-slot tail.  Model it as **"abort the rest of the mover
for this frame, set phase 1, leave Y alone"** -- not as an unwind past anything that
mattered.

**KEEP AN ASYMMETRY THE PORT WILL BE TEMPTED TO FIX.**  `$AEA7` checks NOTHING about the
bubble -- any cell with low bits 1..12 and bit 5 clear re-arms the jump, live bubble or
not.  Only `$AEAD` checks `BIT 7,(HL)`.  A port that validated on the bounce path would
be MORE correct than the machine and would diverge; the asymmetry is the behaviour, and
it should be asserted.

**LATENT, comment-worthy and not model-worthy:** a tag of 13 or more makes `12 - n` wrap
unsigned, `10 x $FF` truncate to `$F6`, and HL land at `$FFD5` -- above the pool, near the
score bytes.  Nothing writes a tag >= 13 today.

## $AE9C's tail in the port -- what M7.35 built

`solidRow` returned a boolean and is gone.  `probeCell` is the PREDICATE half and returns
WHICH CELL was solid, because the tail needs the cell's value to tell a wall from a
bubble; `floorProbe` is the routine, and it returns four outcomes:

| outcome | machine | the caller |
|---|---|---|
| `clear` | `E = 0`, nothing solid | carry on |
| `floor` | `E = 1`, bit 5 set, `$AEA0 RET` | the floor decision that site already made |
| `bounce` | `$AEA7`: phase := 1, `POP HL` | **RETURN AT ONCE**, Y unmoved |
| `popped` | `$AEAD`, then `$AEB9 LD E,A` | the same as `clear` -- fall THROUGH it |

`tail` is false for the FEET probe, whose caller patches `$AE9C` to `$C9` (`$AD30`)
precisely so a solid feet row cannot bounce.

**WIRED AT ALL THREE SITES**: `$AD37` (feet, mask `$20`, tail patched out), `$AD46` (the
row below, mask `$3F`) and `$AD9D` (the arc's descent probe, mask `$3F`).  The UNCALLED
census failed the moment the methods appeared with no call site, which is what that row
is for.

**`bubbleProbePop` is the exact inverse of `$B8C0`'s claim**: `12 - tag` recovers the
slot, `x10` the pool stride -- **EIGHT-BIT**, so a tag of 13 or more wraps to `$FF`,
truncates to `$F6` and lands at `$FFD5`, above the pool.  Driven for every tag 0..15 with
HL read from the register file, and the port is driven at the out-of-range tags too:
poison the address the eight-bit arithmetic reaches AND the one a sixteen-bit multiply
would, give both bit 7, and see which moves.  Nothing writes a tag >= 13 today, so it is
transliterated and counted rather than guarded -- a guard would be a departure, and
`$AEC0`'s `BIT 7` is what actually protects the pool.

**THE ASYMMETRY IS ASSERTED, NOT FIXED.**  `$AEA7` checks nothing about the bubble; only
`$AEAD` checks `BIT 7`.  A row drives a DEAD slot both ways: the bounce still fires, and
the pop refuses and counts it.

**AND THE `$3F`/`$20` MASKS ARE LIVE**, so M7.33's three withdrawn mask mutations are
restored, exactly as their withdrawal note said they would be.  A cell the port itself
creates separates them: `$3F` sees the bubble, `$20` does not.

**BIT 1, NOT BIT 5.**  `(IY+8)` bit 1 is the jump key held THIS frame and bit 5 the same
key LAST frame.  A captured "jump held" byte is `$22` and carries BOTH, so a gate built
from captures cannot tell the two tests apart -- a mutation testing bit 5 survived a full
battery.  The rows drive `$02` (the first frame of a press: bounces) and `$20` (the frame
after release: does not bounce, pops instead), which is where they part company
(TRAPS #188).

## $7FE2..$7FFB -- the HUD's two text rows, and $7FC0's FALL-THROUGH

MEASURED by `tools/hudfurniture.py`'s `text_rows`, driving `$7FE2` in the harness with
interrupts off, one instruction at a time.  Fixture: `build/hudfurniture_fixture.json`,
key `text`.  M7.36.

```
    $7FE2  LD IX,$85C1 / LD HL,$4000 / CALL $802E     row 0, 28 characters
    $7FEC  LD HL,$4020 / CALL $802E                   row 1, 29 -- IX CARRIED, not loaded
    $7FF2  LD A,1 / CALL $80FA                        P1's score panel
    $7FF7  LD A,2 / CALL $80FA                        P2's
    $7FFC  ...falls into the attribute repaint...
```

| | |
|---|---|
| row 0 | `'    1UP    HIGH SCORE    2UP'` -- 28 chars, NUL at `$85DD`, **224 writes**, columns 0..27 at `$4000` |
| row 1 | 29 chars, NUL at `$85FB`, **232 writes**, columns 0..28 at `$4020` |
| pages | `$40..$47` -- an EIGHT-BIT `INC H` with the low byte fixed |
| total | **456 glyph-row writes**, plus **64 panel bytes counted separately** |
| `IX` | `$85C1` at `$7FE9`, `$85DE` at `$7FEF` |
| `$80FA` | called with `A = 1` then `A = 2`, in that order |

### THE SECOND ROW'S POINTER IS NOT LOADED

`$7FEC` sets `HL` and nothing else.  `$802E`'s own `INC IX` has already carried `IX`
past the NUL at `$85DD`, so "row 1" is whatever follows row 0 in the template.  **A
caller scan therefore finds ONE string where there are two** -- the same chaining
`$98C4`/`$98D4` use for the round banner's two rows.

### $85C1..$85FB IS ONE 59-BYTE STATIC TEMPLATE FROM THE TAPE, NOT A BUFFER

Zero writes measured over 17,400 driven frames.  The only bytes ever written inside it
are `$85E9..$85F0`, by `$7FC0`'s own RRD conversion of the four BCD record bytes --
which `hudScoreDigits` already models.  A capture therefore shows row 1 carrying that
machine's converted high score (`785634120` in the fixture), not the seeded placeholder.

### *** AND $7FC0 FALLS INTO $7FFC, WHICH THE PORT SAID IT DID NOT ***

`$7FF9 CALL $80FA` **returns to `$7FFC`**, so every call to `$7FC0` repaints the HUD
attributes.  The comment on `hudAttrPaint` read "reached ONLY from `$8D22`'s `CALL z`",
and one of the port's two `$7FC0` sites was consequently missing the repaint.  `$8D22`
is the only site that **CALLS** `$7FFC` by address, which is a different claim.  Both
of `$7FC0`'s references run the whole routine: `CC C0 7F` at `$7F58` (the round-1
build) and `C3 C0 7F` at `$9998` (the mid-game join's tail jump).

### The two `$80FA` panels blit through the SAME `$804F`

`$81C0` is `JP $804F` -- the identical store site `$802E` uses.  So a write census over
`$4000..$47FF` conflates the panels with the strings, and the fixture counts them
separately for exactly that reason.  My first version of the phase watched the store
site alone and reported **232 writes for a 28-character row**: 224 string bytes plus one
panel digit that happened to land in the window.  `$7FF2` is the boundary.

### Coverage: `$802E` is now complete

Nine references in the image (8 `CALL`, 1 `JP` at `$8EA7`).  **Eight draw on a path the
port runs** -- `$7FE9`, `$7FEF`, `$8024` (inside `$801D`), `$8CEE`, `$8EA7`, `$9114`,
`$98C4`, `$98D4` -- and **one was transliterated but UNCALLED**: `$9758`, the CREDIT
line, which falls through from a title block the front end owns -- WIRED in M7.42, so all
nine now draw on a path the port runs.  **None are untouched.**
The census row in `test/bb.test.js` failed the moment `$7FE9`/`$7FEF` were wired, which
is what it was written for after I claimed a coverage number from the port's own string
table and was wrong by four (TRAPS #165).

---

## The three DIAGNOSTIC BOUNDS, and the measurement behind each

All three are diagnostics, not machine behaviour: each sits above what the MACHINE can
do, is counted and named, and throws rather than clamping (house rule 6).  Each exists
because a mutation used to cost the battery a 120-second blind TIMEOUT instead of naming
the invariant it broke.

### `BB_BANNER_MAX = 32` -- `$802E`'s walk

The machine walks until a NUL; the port modelled that literally, so a mutation deleting
the terminator test ran until the worker was killed.  MEASURED: the longest of the ten
declared strings walks **29** characters -- `$85DE`'s HUD row 1, which M7.36 itself
added, so the number is current and not inherited.  Bound 32.

### `BB_SPARK.MAX = 1024` -- `$C002`'s burst-sparkle walk

**The bound is above 709, not above fourteen.**  `B` is loaded 14 once, and `$C016`'s
`LDI` decrements the same `B` a second time, so a serviced slot with X bits `$00` makes
the DJNZ wrap and the total becomes `(wraps+1) x <=256`, decided by whatever RAM holds
above `$5CFC`.

| state | iterations | HL |
|---|---|---|
| every reachable state (48 captures, 12 passes each) | **14** | never leaves `$5CE0..$5CFA` |
| `caller C = 0, X >= 8` | 13 | `$5CF8` |
| `caller C = 1, every X < 8` (the fixture's `bc` row 3) | **431** | `$603C` -- 320 bytes past the table |
| worst of 1500 randomised tables | **709** | `$6268` |

Three regimes, exactly as the arithmetic predicts: 8..13 (no wrap), 216..269 (one), and
452/502/709 (two to three).  `tools/sparkle.py` now records `iters` and `ptr_out` per
row; the harness, an independent agent and the engine all three give 14 and 431.

**The 431 had been in the shipped fixture since M7.7** as `pix = 4256` against row 1's
`448` -- 32 pixel writes a draw, so 133 draws from fourteen seeded slots (TRAPS #193).

### `BB_SCROLL.MAX = 256` -- `scrollIn`'s step loop, and where the drift hang really was

The drift painter's stride mutation was blamed on the painter's walk for three
increments.  It is not: driven on the Z80 for all 81 rounds under both mutations, **162
runs, every one terminating** (`target`, never `limit`), with **no cycle** in the
256-state closure of the alias loop for either stride table.  The mutation makes the
paint take 54 frames instead of 2.  It is slower, not infinite.

MEASURED faithful maxima for the walk: **233** inner iterations (round 80, via the alias
chain `80 -> 77 -> 76`) against a hard eight-bit ceiling because `($7E29)` is one byte;
**2** alias hops taken against a shipped bound of 16; **1090** filler cells in the worst
round (58, mean 645).  The walk's two existing guards are dead code on every input the
machine can produce, including both mutants -- recorded rather than retuned.

**The hang is `$7F41`'s, and it is FAITHFUL.**  The corrupt fill walks `IX` out of
`$F800..$FAFF` over `$FB00..$FFFF`, which holds `BB_SCROLL.ROW_TAB = $FD04`;
`scrollStep`'s copier then takes its destinations from those wrecked pointers and copies
over `$8604` -- `scrollIn`'s OWN step counter -- caught going `0 -> 196 -> 128 -> 0 ->
255` over 14,969 steps.  On the machine that loop is `$7F4A DEC (HL) / $7F4B JP nz` with
`HL = $8604`: a counter in **writable memory**, decremented in place, with no register
copy and no second bound.  A Spectrum running these bytes spins exactly there.

So the faithful counter stays in `ram` and the **cap is the assertion**, the same shape
as `$7D49`'s eight-bit wrap.  **256 is provable, not chosen**: `($8604)` is one byte, so
no single seed can ask for more.  Measured faithful cost: **26 steps** (four pre-roll
plus `$7F3C`'s `$16`).

### `BB_PAINT.BUDGET = 2048` -- the filler's work, retuned from 200,000

`paintFill`'s work budget was **183x the measurement**.  The faithful maximum is 1090
cells in a round, and the port's own `want` accumulator equals the machine's logged write
count exactly on the faithful path, so it is the right meter.  Both stride mutants ask
for ~66,180, and the cheapest mutated round that exceeds 1090 asks for **4316** -- so a
budget in `1091..4315` kills the mutation **inside the painter, by name**, before the
corrupt fill can reach `$FD04`.  2048 is 1.9x the measurement and 2.1x under the mutant.

## $97EB -- the title screen's CLS, and the 185 bytes `gameReset()` skipped (closed M7.42)

MEASURED by `tools/gameover.py`'s `phase_title_cls` (the tool that already owns `$96DF`).
Fixture: `build/gameover_fixture.json`, key `title_cls`.  M7.38, front-end increment A.

```
    $970B  LD ($FED3),A      <- where the port's gameReset() stops
    $970E  EI
    $970F  CALL $97EB        <- a CALL, so $97EB RETURNS and $96DF continues
    $9712  LD BC,4           the starfield
    ...
    $97EB  LD HL,$4000
    $97EE  LD DE,$4001
    $97F1  LD BC,$1AFF
    $97F4  LD (HL),L         *** THE FILL VALUE IS L, NOT AN IMMEDIATE ***
    $97F5  LDIR
    $97F7  RET
```

### THE COUNT IS 6,912, NOT 6,911

`BC=$1AFF` is 6,911 LDIR copies **plus** the `LD (HL),L` that seeds the first byte, so the
range is `$4000..$5AFF` **inclusive**.  Measured over a world poisoned `$AA` **past the
end**: 6,912 bytes, contiguous, and `$5B00` came back `$AA`.

Two of M7.37's seven sub-blocks disagreed about exactly this, and it is not pedantry:
**`$5AFF` is the credit line's ninth attribute cell**, which `creditLine()`'s own gate
already asserts (`ram[0x5AFF] === (0x05 | 0x40)`).  A port clearing to `$5AFE` leaves the
brightest cell on the screen dirty and then tests over a dirty world.

### AND THE FILL VALUE COMES FROM L

`$97F4` is opcode `$75` — `LD (HL),L` — not `$36`, `LD (HL),n`.  L is `$00` only because HL
is `$4000`.  **Driven rather than read off the opcode**: patch `$97EC`, the operand of
`LD HL,$4000`, and the value follows — `L=$00 -> $00`, `L=$05 -> $05`, `L=$7E -> $7E`.

DE does **not** follow HL: the machine's `LD DE,$4001` is a separate immediate, so
patching `$97EC` alone moves HL and leaves DE.

**The seed cell is no use as a witness.**  DE trails HL by L, so L copies later the LDIR
writes over the byte the seed just placed; reading `$4000+L` shows the poison coming back
and looks like a refutation of a true claim.  The witness is the **first destination**,
`$4001` (TRAPS #197).

### THE GAP: `$970E..$97C6`, 185 BYTES

Until M7.42 `gameReset()` modelled `$96DF..$970B` and then called `playersInit()`
(`$97C7`/`$97D2`) — so the port **jumped from `$970B` to `$97C7`** and skipped the EI,
this CLS, the starfield, the four strings, the credit line, the sparkle ring and the key
wait.  M7.37 measured the whole gap; M7.38 closed the first of it, M7.41 the paint
(`titlePaint()`, which calls `titleClear()` and `creditLine()`), and M7.42 the rest: the
ring, the exits and the release wait, wired so `gameReset()` ends in `titleEnter()`.
The UNCALLED census went 19 -> 18 -> 17.

Two corrections to this file's own earlier text, both from this increment:

- **the credits store is at `$970B`, not `$9709`** — `$9709` is the `LD A,6` that feeds it,
  and the port's comment cited the load;
- **`creditLine()`'s "roughly thirty substitute glyphs including lowercase" is now
  measured**: the title screen's five strings need **36 distinct codes**, the font has 32,
  and **17 are missing** (`: B` plus the fifteen lowercase `a e f g i k l m n o r s t w
  y`).  For the whole front end it is 57 needed and 26 missing.

### A corroboration worth recording

`title.pkl` **fails** `tools/gameover.py`'s 48K-branch guard: `m[$8DC4]` reads `$F3`, not
`$C9`.  That is independent confirmation of M7.37's reading that the three RET patches at
`$8DC4`/`$8E05`/`$8E0A` are applied by `$95F3`, and that `title.pkl` is captured in the
control-select menu **before** `$95F3` runs.  `$97EB` reads no state, so the phase uses
`round1_48`.

## $970F..$9764 -- THE TITLE SCREEN'S PAINT (front-end GROUP 1, M7.41)

One straight line: `$970F CALL $97EB` (the CLS), `$9712..$9728` the starfield, `$9729..$974F`
the four title strings (fallen into from `$9727 JR nz`), `$9751..$9764` the credit line (fallen
into from `$974F DJNZ` exhausting).  **`$9729`, `$9751` and `$9765` have no CALL, JP,
conditional, JR or DJNZ anywhere in the image** -- measured, `title_paint.no_entry` -- so the
middle cannot be entered and the port's `titlePaint(phase)` is the block's only entry.  It
landed UNWIRED (M7.41, replacing `titleClear()` and `creditLine()` in the UNCALLED census,
19 -> 18) and M7.42 wired it: `gameReset()` -> `titleEnter()` -> `titlePaint()`, census 17.

**The starfield is EXACT.**  1,024 dots, each a pure function of the `$FE86/$FE87` PRNG state
and the 7-bit R phase.  Per dot: `$9715 LD A,R / AND 7 / LD ($FEBB),A` (the ink, into an
operand), `$971D CALL $FE85` (the PRNG), `$9720 CALL $FE82 -> JP $FE95` (the plotter):
`C = mask[$FEBD + (draw & 7)]`, `HL = $4000 + 3*(draw & $7FF)`, `L ^= R` (at `$FEAC`),
`LD (HL),C` -- a **store** -- then the attribute cell (`$A090`'s arithmetic inline) gets
`ram[$FEBB]`.  R steps +51 per dot and is read at +35 by `$FEAC`; `DEC C / JR nz` closing each
block of 256 is two more M1 fetches, `rng.stall(2)`, so the steps are +53 out of dots
255/511/767.  Driven from the machine's phase the port matches all 6,912 screen bytes, the
ordered 1,024 stores, the PRNG end `$2CCD` and the walk.  **The phase is a parameter**: with
none, `starfield()` arms a fresh one, as every title on the machine is a different starfield.

**Slot 7 of the mask table is `$FEC4`**, a live variable (twelve writing sites); `reset()`
seeds only `$FEBD..$FEC3` = `80 40 20 10 08 04 02`.  With `$FEC4 = $00` lit bytes equal set
pixels (820/820); with `$14` they part (940/1,060); with `$01`, 120 bytes carry bit 0.

**Interrupts are a DECLARED DEPARTURE here.**  `$970E` is EI; on the machine 5 or 6 ISRs land
inside the pass and move R (steps 103/104/106 where one splits a dot), at positions that need a
T-state clock.  The port's walk has none.  What the ISRs cannot touch -- each dot's display
page, mask and bit 7 of its low byte, and the PRNG end -- is one sequence over sixteen frame
phases on the real ISR, and the port matches it (`title_paint.ints_on`).

**The four strings are one IX chain** from `$9A32` to `$9A85` (one past the last NUL), placed
by the column-major table at `$9A85` (display low, display high, attribute, count: `45 06 67 2A
/ 40 48 48 50 / 07 06 03 8C / 18 15 14 0E`).  `$973F CALL $A090` DERIVES each attribute
address; `$994F` writes two rows, the second starting where `$995A`'s eight-bit `INC L` LEFT
HL, minus B, plus `$20` -- not `hl + $20` (they differ past the wrap: `$58F0 x32` -> `$5810`).
`DJNZ` with B = 0 is 256, so `attrRun` now treats a zero count as 256.  1,264 double-height
display writes, 167 attribute stores in nine runs (`$47 $47 $46 $46 $43 $43 $CC $CC $45`), all
BRIGHT from `$995A`'s `OR $40`.  The glyph shapes are the declared font departure; the cells
and the attributes are the machine's.

**The font grew by the title's seventeen** (`:`, `B`, and `a e f g i k l m n o r s t w y`) to
49 codes.  The other eleven the whole front end needs belong to the control-select and redefine
screens and are drawn with the strings that print them (group 3), so every glyph is read by a
gate.  The `T` was redrawn with a two-row bar: on the title screen its shoulder read as `I`.

## $9765..$97EA -- THE TITLE'S WAIT AND ITS EXIT, and THE WIRING (front-end GROUP 2, M7.42)

**The machine.**  `$9765 LD HL,$5800`, then forever: `$9768 INC HL` (at `$5B00` only H is
rewritten, to `$58`), skip the cell iff **bit 6** is set, else ONE `$FE85` draw whose new LOW
byte is the gate (`AND 7`, write iff zero) and whose new HIGH byte is the value (`AND 7`, a
store); then `$9781 IN` half-row `$F7`, `CPL`, `AND $1F`: `'1'` -> `$979E`, `'2'` -> `$9790`,
`'1'` beats `'2'`, 3/4/5 ignored.  Each arm DECs `$FED3` once (eight bit, no guard) and
ASSIGNS the in-play bytes -- 1P `$FD87 = $80` then `$FD91 = $00`, 2P `$FD91 = $80` then
`$FD87 = $80`.  `$97AB` zeroes `$FDDA`/`$FDE4`; `$97B7` runs the CLS and `$97BA` reads all
forty keys (`IN` with high byte 0) until every one is up; `$97C4` blanks `$9A0E`, `$97C7`/`$97D2`
stand both players up, and `$97EA` RETs twice, to `$8D09 CALL $97F8`.  The ISR is live
throughout ($970E EI) and, with both gates closed, only counts.

**The port.**  Iteration space is exact and row-for-row gated against `title_wait`:
`titleRingStep`, `titleKeyDecode`, `titleIter`, `titleArm`, `releaseEnter`, `releasePass`,
`keysDown`, `titleLeave`.  `gameReset()` now ends in `titleEnter()` (paint + ring), and
`gameStart()` no longer advances into round 1 -- `titleLeave()` makes the `$8D09` call when
`$96DF` finally returns.  **The page boots to the title** (`game.gameStart()` in the
template); a bare `new BB_Game(A)` stays the round-1 capture, in play: the declared test
boundary, and `mainLoop()` throws while the front end is up.

**The frame layer** (`frontFrame`, driven by `BB_TITLE`) is the added layer, and every term
is a measurement: each iteration charges its path's contended mean (skip 97.60, gate 208.19,
write 221.92 T), the paint is 634,920 T of debt (639,332 on arrival less its nine ISRs), a
release pass 184,631 T, the arm 142 T.  It gives 374.4 iterations a frame against the
machine's 374.08 (range 346..401 both), the machine's release-pass counts exactly at every
measured hold, and the first ring iteration after exactly nine ISRs.  `BB_TITLE.DEPARTS`
names what it is not: the key sampled once a frame, the paint and CLS instant, and the test
world being a capture (the ISR 41 T short was on it until M7.68 charged the acknowledge).  (The title's PARITY leak into the first in-play
ISR was on this list until M7.43's RA4 reproduced it.)

**The session seed.**  Every non-skipped iteration draws the PRNG, so how long the title was
up is the state the game starts on.  Driven with the machine's key script the port reaches
the machine's `$FE86/$FE87` at the first main-loop pass exactly.

**The round advance drains as the machine does (RA1..RA4, M7.43).**  61 ISRs (62/63 for 2P
on an even/odd HALT) from `$97F8` to the first `$8D0C`, counter B 50/51/52, and the parity
leak reproduced.  (M7.42 found it three frames long; the four causes and their fixes are in
`docs/M7-PROGRESS.md`.)

## $B6D8..$B797 -- THE POP KILL, and the fruit that stays (M7.45)

A touch-pop (`$B9B6` marks the bubble, `$B6D8` pops it on the even ISR) stores the bubble's cell
in the self-modified `$B775`, caches and erases it at `$BF0A`, and FALLS THROUGH into the emit
tail `$B6F2..$B797`: the class stash, the sparkle, the owner (`$B7C2`/`$B796`), the `$FFF9`
mailbox, the fork -- an enemy inside becomes a corpse (`$B816` -> `$8BC2`) -- the chain walk
(`$B774..$B78D` + `$B7A1`: a 4x4 cell window marking risen neighbours to pop next), the award
through `$80FA`, bracketed by a speaker click (`$B790`/`$B79C`).  The owner byte `$B9BC` is
written per player by `$B901` (`$00` P1, `$10` P2) -- the port had a constant `$10`, latent until
the award was wired.  A corpse (bits 7 and 3, `+9 = $FF`) is ticked by `$AAFC -> $8A78` on the
odd ISR, drawn by `$A26F` (an OR-draw through the `$FD00` row table in three blocks), flies,
falls, lands as a fruit in `$9607..`, and the round clears when `$FECA` runs out.
The fruit STAYS because `$86CE/$86CF` is the `AND $FF` operand of the item-age test: tape bytes
`$E6 $FF`, never written at runtime; the port's `reset()` held zeros, so every fruit vanished
three frames after landing (M7.45b).
Declared gaps: the ISR's T for a pop (median 8,472 T short) and a corpse tick (7,217 T) are not
charged (pinned by PK7); the click's LOW width is 3,924 T when paid and 296 T when the paid
player is out (PROVISIONAL, measured range 3,268..3,972), with a chain's pulse spacing not
modelled; a chain window that reaches ROM (a pop flagged between a capture and its first risen
move) marks from ROM bytes on the machine and is counted, not reproduced (`chainRomReads`).

## $97F8's ROUND BUILD IN TIME -- the new level scrolls in over ~53 frames (M7.59)

`tools/buildtime.py` -> `build/buildtime_fixture.json`.

- **The timeline** (main-line T from `$97F8`, contended, round 10 -> 11): the clear walk and
  `$9858`'s shadow clear to 161,799; the background builder `$7F62` (264K..371K T by round -- the
  round's own geometry, the tile moving it 0..8 T); `$7F30`; the separator row; four pre-roll steps
  (the `$8404` cascade) and 22 scroll steps with a push each, ~146K T a step; the repaint `$8216`
  (181K..190K); the digits, the lives, `$854D`, the spawn, the player init, the bolt slots, the letter
  panel; `$9887`.  EXACT the scroll is 3,164,692 T from `$7F30` to `$7F4E`; contended 1.1796..1.1811
  times that, the repaint 1.2273..1.2929.
- **Every step and push is the same** in every world: a step's byte i of pixel row r in pair p at
  147 + 5,547 p + 603 r + 16 i from its `$840A` entry, the pair's colours 4,861 after its first byte;
  a push from 162, its colours at 4,843.  The separator's colours at 92 + 26 i from `$7F30`, its
  pixels at 974 + 349 column + 37 row.
- **The premise** (322 advances): every interrupt inside the build is gate-closed (`$984B` zeroes
  both gates) and writes only the two frame counters, which the build never reads -- but for the
  entry window (an interrupt within ~1,035 T of `$97F8`, before the gate stores: 2 advances).
- **Only six routines touch the display**: the separator row, the steps and pushes, the repaint, the
  HUD (round 1), the lives, `$854D` (reads) and the letter panel.
- **FOUND:** the machine's round-1 HUD makes 617 (1P) / 653 (2P) display writes, the port's 517: it
  writes each HUD attribute row twice and row 23's first four cells.

## $A09A's FLASH AND STRIKE IN TIME -- four inks across 1.7 frames, the pass waiting (M7.58)

`tools/stormtime.py` -> `build/stormtime_fixture.json`.

- **The painter's clock (EXACT, a plain Simulator).**  A flash tick enters `$A0E0` at 337 + 29,088 k
  (k = 0..3) from `$A09A`, a strike at 1,375.  Each pass is three runs -- `$A0E7`'s CALL (B = `$C0`),
  `$A0EA`'s CALL (B = 0: 256) and the fall-through (256) -- and byte i of run r is stored by `$A0F0`
  at the entry + 60 / 7,954 / 18,455 + 41 i.  The tick ends at 116,567 / 30,316.  Every store of
  fifteen worlds (three flash counters under four generator words, the three strikes) sits on it.
- **Contended** the flash costs 122,289..123,796 T by frame phase, the strike 30,525..32,984.  One
  stretch per tick (`BB_STORM_K`, the sixteen forced natural runs' mean) puts every store within
  -1,638..+1,772 T of the machine's main-line T (flash, in sample; -1,449..+1,128 on seven free
  worlds) and -874..+1,483 / -810..+604 (strike).  DECLARED.
- **The premise (78 natural ticks, interrupts on).**  BOTH gates are open: 2..4 interrupts inside a
  flash, 0..2 inside a strike, each the whole bubble manager or entity pass (6..460 addresses
  written).  None writes an attribute byte, none reads one, none reads a byte before the tick's main
  line writes it, and the main line reads nothing one wrote.  The only tick-written bytes an
  interrupt reads are the strike payload's pool flags, read AFTER the payload's DI..EI stored them.
- **In the port** the stores are held to their frames (`stormBegin`/`stormHold`/`stormEnd`) and the
  pass parks at `$8D46` while the tick's T drains or a store is still held.  The payload `$A0F5`:
  see M7.60 below.

## $9DE1 THE FIREBALL'S SPAWN, AND $A0F5 THE STORM PAYLOAD IN TIME (M7.60)

- **`$9DD4`, the request** (`tools/projectile.py` 'fireball' -> `build/projectile_fixture.json`):
  `LD ($9DDF),IX / LD A,1 / LD ($9DDE),A / RET`, 50 T, reached only from the blow's `$BD74 JP nz` when
  +`$5A` bit 5 (fire mode, the power-up `$88DC`) is set.  No bubble is blown and the blow's debounce
  (+`$5A` bit 1) is NOT set -- the RET is the blow's.  The census: `$9DDF` is written only here, with
  the blow's IX, `$FD80` or `$FD8A`.
- **`$9DE1`, the spawn**, first call of the element tick `$9E50`, 17 direct worlds: `RET z` without a
  request; the request consumed and (`$FEC5`) -- the EVEN ISR GATE -- written 0, then 1 at `$9E4A` on
  every way out, even when it was 0 on entry.  Slot `$5B00` if +7 bit 7 is clear, else `$5B0A`, else
  (slot 1 holds an enemy shot) slot 1 is ALIGNED (+6 AND `$F8`, and left so), erased (`$A314`) and
  released (`$9D58`, the shooter unmarked by the fall-through) -- and nothing if slot 1 is a fireball
  (kind 8; slot 0's kind is never read).  Then the player's Y AND `$F8` must lie in `$10..$B1` --
  checked AFTER the recycle, so a refused request can still cost an enemy its shot.  +6/+5 aligned,
  +8 := 8, +7 := (IX+7) AND `$81`, bit 4 for P2 ((IX+`$5A`) bit 0); +0..+4 and +9 keep the last
  tenant's bytes.  Gated by PF0..PF2 (PJ8, the old boundary, is gone).
- **`$A0F5` in time** (`tools/stormtime.py` 'payload' -> `build/stormtime_fixture.json`): the same on
  all six ticks measured -- DI ends at +163 from `$A09A` (it starts at 159), 36 stores (slot k's
  `LD (IX+3),E` from 194 + 93k, its SETs on (IX+7) 19 and 42 later), EI at 1,309 and IFF back after
  its RET at 1,319.  Contended, the interrupt line raised at 200 offsets: none taken at 88 of them,
  exactly 160..1,287 -- the window [160, 1,319] under intLost's rule.  **In the port** the stores
  are held through `stormHold` (the SETs as read-modify-write OPERATIONS, so an ISR's change to the
  flag byte first survives), unstretched (no contended byte), the window is pushed onto `diWindows`,
  and the waiting ticks `$F0..$FC` run as a storm block of their own (the pass parks at `$8D46` when
  one runs past the interrupt point).  The flood's `$A151 JP $A0F5` is not on a tick clock and
  writes at the call, DECLARED.  Gated by PS0..PS3.

## $94C2 IN TIME -- the playfield empties, ten rows of fruit climb, the life lands 120 frames later (M7.57)

MEASURED by `tools/extendtime.py` -> `build/extendtime_fixture.json`: `$94C2` armed on extcomp and on
nineteen variants of it (P2 completing, rounds 23/45/67/81, letters held by the other player, two
players, lives 0/5/7, player one out, a paper equal to the lives ink, fifteen world items with an
RNG-ink power-up, the item tick on a mask that is not `$FF`, the tick under the heart, expiry under the
flood, the flood, the storm), interrupts off, EXACT (a plain Simulator, every LDIR iteration its own
step); the base world at sixteen frame phases, contended; and twenty natural completions (interrupts
ON), four from free entry phases and sixteen with the entry forced at `$948F`.
- **ON THE MACHINE** the completion is 17.1M main-line T (17,107,864 exact on extcomp; 16,964,300 ..
  17,529,030 across the twenty worlds).  Both gates are shut from +58 and +71 (`$94CD`/`$94D0`), and
  every interrupt inside it runs gate-closed, 488/493 T, writing the two counters and its stack --
  none of it read by the completion (0 of ~8,950 addresses, all twenty runs).  The frames: the wipe
  (145K T, the shadow only), the reveal from 145,651 T (the repaint from the wiped shadow row by row,
  the colours, the EXTEND panel, the lives), ten passes of sixteen fruit -- the records' Y climbs a
  row a pass, so ten rows fill the screen from the floor -- then "N I C E      P" ~13 frames in; the
  extra life 120 frames after it; the round advance ~112 frames after that.
- **TWO DIs.**  `$94CB`..`$94D8` (IFF clear 54..129 T from `$94C2`) and `$8C14`'s DI to `$8C4C`'s EI --
  the reveal runs with interrupts OFF for ~250,000 T.  The 48K ULA holds INT for 32 T and does not
  latch it, so an interrupt whose 32 T fall inside a window is LOST: 244 interrupts in 247.3 frames.
- **THE TWO BUSY WAITS count what the registers hold.**  `$9553`: A is `$995A`'s last store, the
  banner's `$8F` with `OR $40` = `$CF`, B zero -- 120 frames.  `$955E`: whatever `$806C` left -- the last
  lives cell leaves A = `($5AC0)` and B = the row's ink (4 or 5); a row out of play returns at `$8097
  RET p` with A = its walk opcode (`$2C`/`$2D`) and B untouched (zero from `$8078`'s DJNZ if no row
  ran).  (45, 4) with player two out of play, (`($5AC0)`, 5) with player two in it: a two-player
  completion is 124K T shorter.
- **THE SPIN DECREMENTS `$861C`, NOT THE LETTERS.**  `$955B CALL $806C` leaves IX at `$85B9` (its last
  cell's `LD IX,$85B1` stepped eight times) and nothing restores it, so `$9561 DEC (IX+$63)` is
  `$861C`, the byte before the ink table, run until it is zero: 256 stores from the `$00` all 57
  captured worlds hold there.  With no lives row in play IX is still the player's.  (M7.25 read it as
  the letters; both end at zero.)
- **`$8719`'s TWO WEATHER SKIPS.**  `DEC HL / LD A,($FECE) / OR A / JP nz,$A2C2 / LD A,($FECF) / OR A /
  JP nz,$A2C2`: under a flood or a storm an item goes straight to the blit, with no `$8769` and no four
  ink cells.  The port had neither (a note claimed them); M7.57 adds them to `itemEntry`, in play too.
- **THE PORT** runs the whole completion at once in the machine's order, under a Proxy that stamps
  every write with its machine T and HOLDS the ones past this frame's interrupt point (M7.54's held
  writes, a third block, `heldBy` 'extend').  The stamps come from a TIMING MIRROR: each routine names
  itself (`extRt`, in `BB_EXT_SCRIPT`'s order -- one out of order THROWS) and its model reads the RAM
  it is about to read -- the item pass its slots, the tick operands, the weather and the ink table;
  the lives their flags, counts and attributes; the panel its masks; the digits the round -- and
  returns every write's EXACT offset (`BB_EXT_W`, `BB_EXT_I`: the disassembly's instruction sums,
  matched write for write, T for T, on all twenty worlds) and its T to its return.  Each routine's
  exact T is stretched by `BB_EXT_K`, the natural runs' own contended totals; a write past its model
  is COUNTED (`extOff`), a stamp going backwards too (`extBack`).  `chainWalk` returns 'extend' and the
  round advance waits for `mainLoop`'s resume; step() drains the T and LOSES the interrupts whose 32 T
  fall inside either DI window (`intLost`: no ISR, no counters, the next frame's main line the whole
  frame).  The reveal's OUT goes to `mainOut` at its stamp.
- **DECLARED.**  (1) The contention is a fit: against twenty natural completions every hook is within
  -5,810..4,685 T of the machine's main-line T, the end within -5,172..4,564, every write of the run
  kept within 4,446 -- the machine's own phase moves the repaint 1.2197..1.2910 of its exact T.  (2)
  The DI windows' edges are the instructions' starts, to within an instruction.  (3) The machine patches
  `$A2C2`'s two NOPs and `$A304` into the item blit and `$A355`/`$A349`/`$A33D` into the erase; the port
  writes none of them (five stores an item entry, left out of the oracle's lists and counted).  (4)
  The power-up of type 10's ink is `$873E LD A,R`, a declared substitute site: its five stores are
  matched by address and T only.  (5) The pass that called `$948F` is charged nothing before the
  completion's entry (the frame ledger charges a pass at its end), as with the hurry.

## $98B5's ROUND BANNER IN TIME -- "ROUND n / READY !" is on the screen for the whole of it (M7.56)

MEASURED by `tools/bannertime.py` -> `build/bannertime_fixture.json`: the banner called directly from
the title hand-off's `$98B5` (exact -- a plain Simulator, every LDIR iteration its own step -- and
contended at eight frame phases, with the strings' characters moved, bit 5 flipped under its cells,
and round 81), and fourteen natural banners with the interrupts on (the hand-off, keys 1 and 2, and
rounds 2..7 of each after `$FECD`), every interrupt bracketed with a RAM diff across it.  (M7.28's
`roundbanner.py` measured WHAT it draws and erases; this is WHEN.)
- **ON THE MACHINE** the banner is up for the whole of its main-line T (2,830,310..2,837,539 over 160
  advances, `BB_BANNER_T.LOOP` the median): 256 iterations, each writing the same 180 bytes -- ten
  glyphs of eight rows and ten attribute cells per row -- at the same offsets from its `$98BC`, then
  the two erases.  48 or 49 interrupts land inside it on the hand-off (1P / 2P) and 51..58 in play,
  EVERY one with BOTH GATES OPEN: `($FEC4)` the settle window `$9884` armed (20 on round 1, 88 after)
  and `($FEC5)` `$98AF`'s `$2A`.  So the enemies settle in under the banner and, after round 1's
  twenty ticks, the players can move under it.
- **NOTHING THOSE INTERRUPTS DO TOUCHES IT.**  Across every interrupt inside all fourteen banners, not
  one of the 472..483 addresses the banner's main line reads changes, and not one banner cell is
  repainted -- while the interrupts repaint 16..580 screen bytes elsewhere (the diff could see one).
  That is what lets the port run it AHEAD.
- **EXACT** (uncontended): `$98BC` at 27 T and every 10,902; glyph stores at 232 + 500 c + 37 r (row 1)
  and 5,659 + 500 c + 37 r (row 2) from `$98BC`, attribute stores at 5,144 + 31 i and 10,571 + 31 i --
  `$802E`'s and `$995A`'s grid, the hurry's (`BB_HURRY_W` CHAR, GROW, RUN).  `$802E`'s path does not
  look at the character code: with every character of both strings moved, the same T.  The erases
  enter `$9904` at 2,790,961 and 2,794,038 (a 257th iteration's start + 22: the DJNZ falls through,
  `LD HL` 10, `CALL` 17); from each entry its LDIR stores come at 64 + 281 r + 21 i and its attributes
  at 2,414 + 67 i, **8 T more a cell whose colour-shadow bit 5 is set** (+160 over the twenty) --
  `$9904`'s grid, the hurry's (ROW, LDIR, CELL, BIT5).  `$98F0` at 2,797,088, `$8D0C` at 2,797,128.
  Round 81 (`$98B8 CP $51 / JR z`): the erases only, at 59 and 3,136 (6,250 T); contended the second
  comes at 3,136 or 3,941 -- the erase in the border or on the screen -- and the whole 6,250..7,869.
- **CONTENDED** an iteration costs 10,902..11,130 T by frame phase and 11,035.6..11,051.6 on average
  over the fourteen.  The natural tail (`$98F0` to `$8D0C`) averages 3,631 T and the gap between the
  erases 3,560.
- **THE PORT** (`roundBanner` -> `bannerBegin` / `bannerRt` / `bannerStamp` / `bannerHold` /
  `bannerEnd`): the call still runs the whole banner, but under a RAM Proxy that STAMPS each write with
  its main-line T from `$98B5` and HOLDS it in M7.54's `heldWrites` until the frame whose interrupt it
  precedes; `step()`'s `flushWrites` lands it.  The stamps are the exact offsets (`BB_BANNER_W`) on
  CONTENDED anchors (`BB_BANNER_AT`) fitted BACK from LOOP -- the port spends one constant for the
  whole banner, so the tail and the gap are the natural means and PERIOD (11,035) puts the first erase
  where they leave it (2,825,009; the second 2,828,569; round 81's 59 and 3,639, the mean of its two
  modes).  Against the fourteen: every iteration within 4,343 T, both erases within 4,112 -- the
  machine's own spread about LOOP.
- **THE REPEATS ARE HELD TOO** -- a repeat is what repairs a banner cell an interrupt has repainted --
  but not through the Proxy, whose trap per write made the block fifty times the transliteration's
  cost.  Iteration 0 runs under it and RECORDS its 180 writes; iterations 1..255 run the
  transliteration (every call, every counter) against a SCRATCH copy of the RAM, each holding iteration
  0's writes PERIOD k on; at the first erase the scratch must hold iteration 0's values in its cells and
  the real RAM's everywhere else, or the banner THROWS.  A routine whose writes are not the machine's
  count (80 / 10 / 90) is counted (`bannerOff`), a stamp going backwards is counted (`bannerBack`), a
  routine out of the machine's order throws.  Outside `step()` the budget is Infinity and all of it
  lands in the call.  `heldBy` says whose writes the queue holds, so the hurry's open-gate count
  (`hurryOpenIsrs`) is the hurry's alone; `bannerIsrs` counts the banner's; `frameLedger().banner`
  reports one while it is up.  `flushWrites` now re-bases IN PLACE (the same landing, order and
  resolution; 45 ms of allocation per banner gone).
- **THROUGH step()** on the port's own title hand-off (the HALT's interrupt even, as the machine's S0
  world's): 48 / 49 interrupts inside the banner, the machine's, with its gates and parity at every
  one; the whole banner up at every one on both; the erase after the last on both; on the engine's own
  ledger exactly the writes stamped before each interrupt's point have landed.  **DECLARED, the frame
  ledger's, not the banner's:** each even interrupt was charged 41 T short (the IM2 response, M7.54),
  each odd one 55..122 T short while `$AA60` is diverted, and after round 1's twenty ticks the
  undiverted `$AA60` pass 4,070..4,087 T LONG (1P) or 2,237..2,245 (2P) -- so the interrupt points trailed
  the machine's by up to 17,966 / 8,057 T at the banner's end, and the landed counts differed by up to
  225 / 97 writes, every one a repeat of a byte already there.  **Since M7.68**: even exact, odd -44..-15 /
  -82..-24 in the settle window and 22..39 / -26..-16 after, drift 605 / 1,421 T, up to 76 / 81 writes.
- **NOT MODELLED** -- a sprite crossing the banner: none did in the fourteen, and if one does, the
  held repeats repair the cell at the next frame's flush where the machine's next iteration repairs it
  before the beam reaches it, so the page would show the sprite on the banner for a frame (the port
  renders after the interrupt, the machine as the beam passes).

## $9BB4 -- THE PROJECTILES' UPDATE, ALL SIX ARMS (M7.55)

MEASURED by `tools/projectile.py` -> `build/projectile_fixture.json` (75 direct calls on built worlds,
a 33x33 hit sweep per player, and five natural scenes with interrupts on: rounds 6, 50 and 60, fbkill's
live fireball, and a staged round 40).  Every tick erases the slot at its 8-aligned Y, puts the full Y
back, and dispatches on (IY+8):
- **1 boulder** -- +-4 px (it zeroes `$9D83` for the move and restores it from `$9D82`, a byte only
  `$9C04` reads); a delay phase in Y's low bits: hidden on its first tick, five moves, one more hidden
  tick that frees the thrower (`$9C43`), then it rolls every tick; released when EITHER cell is solid or
  X leaves `$10..$DF`.  **6 breath** -- +-8 px, released only when BOTH cells are solid, or at the X
  bounds.  **5 bottle** -- +-8 px with NO X bound (X wraps); the first solid cell reverses it once and it
  is drawn inside the wall; released at a second solid cell or back at its launch column; FOUR frames
  `$60C0`..`$6120`.  **7 drop** -- +8 px down, an 8-bit add, released at Y >= `$C0`, no wall test.
  **8 player fireball** -- the breath body with `$9D5C`/`$9D8B` patched to RET: no wall test, no player
  hit, no unmark; it repaints its 2x2 attribute cells `$42` (the colour the environment kill `$931A`
  reads -- that is how it kills).  **any other kind** -- set to 0; the slot stays live, erased every tick,
  never drawn.
- **THE HIT** (`$9D8B`): the kill zone is exactly the projectile's own 8x8 cell (64 of 1,089 positions,
  swept per player); it sets dying (+`$5A` bit 2) and a 100-tick timer, skipping an invulnerable, carried
  or dying player -- and there is **no in-play test**: in natural one-player play 3 of 7 projectile kills
  landed on the ABSENT player 2, parked at (`$D8`,`$A8`).  Reproduced, as the machine does it.
- **DECLARED**: the update's T (1,784..4,619) is not charged to the frame, like the bolt's and the items'
  draws; the shared eraser/blitter operands (`$A355`/`$A349`/`$A33D`/`$A304`) are not written -- each is
  set before it is read in the same call; the through-step() row holds out frames the port's frame model
  cannot reproduce, counted by reason.  `$9DE1` (the fireball's SPAWN) and `$BD70`'s fire-mode blow
  arm were built in M7.60 (PF0..PF2).
- Corrections to the older notes above: the bottle has four frames, not three; the breath needs BOTH
  cells solid where the boulder needs EITHER; and there is no in-play test on the hit.
Gated by PJ0..PJ7 (PJ8, the boundary, became PF0..PF2); PJ6 checks every counter, the arms' included, against the machine's own events.

## $9037's BLOCK IN TIME -- the HURRY UP! banner climbs, the gates stay shut (M7.54)

MEASURED by `tools/hurryblock.py` -> `build/hurryblock_fixture.json`: the block called directly
(uncontended, contended, eight phases, the latched path, 3..8 and 256 temper slots), the natural run
(round1_48 + hurry.py's ready world, interrupts on, contended), a held-out two-player world, a
boundary entry phase, key scripts, and the tail with an interrupt placed D T after `$90A3`.
- **ON THE MACHINE** `$9037` enters 7,409 T into its frame; 42 interrupts land in the block (43 from
  an entry about 20,600 T or more into the frame -- 42.70 frames with the interrupts), EVERY one with
  both gates shut, 447/452 T, writing only `$8DB6`/`$8DBD` and its own stack; the banner climbs one
  character row a step (`$90E0`'s delay, B x 9,224 T, before each of its 22 steps); the reopen, the
  RET and the rest of the pass (`$925A`..`$8E3A`) come in the last frame.  No key is read while the
  gates are shut.  3,993 writes in a fixed order.
- **THE PORT** runs the block's routines at once in the machine's order, but for the length of the
  call `this.ram` is a Proxy that STAMPS each write with its machine T (`BB_HURRY_AT`: 22 contended step
  anchors; `BB_HURRY_W`: instruction sums inside a step; `hurryShift`: 101 T per short Boris setup) and
  HOLDS the ones past this frame's interrupt point until their frame (`heldWrites`, `flushWrites`).
  `chainWalk` parks the pass at `$8D52`; step() drains the block with gate-closed interrupts; the
  resumed pass charges one `BB_PASS_T`.  At 40 of the natural run's 42 interrupts the port equals the
  machine (gates, ISR cost, `$9A04`, `$9077`, `$904D`, write count, the 1,980-byte banner strip).
- **THE TAIL IS HELD AS OPERATIONS** (the review's MUST-FIX): `$90A3`/`$90A6` reopen the gates before
  the `$90C1` walk, and the 43rd interrupt -- EVEN at the natural fire, since every threshold is even
  and the fire comes at threshold + 1 -- runs the bubble manager, which can capture or release an enemy
  the walk then read-modify-writes.  So `$90CF`'s SET/RES and `$90D5`'s AND `$F8` are held as
  operations applied to the byte when they land, `$90D5` carrying `$90D3`'s read 11 T earlier: an
  interrupt between the two (D = 310..320 after `$90A3`, measured) stores the pre-interrupt X AND
  `$F8`, as the machine does.  Values computed ahead had re-frozen a released enemy with no bubble
  holding it, so the round could never clear (30 of 600 scene worlds).  `hurryOpenIsrs` and
  `hurryStale` count it (TRAPS #230).
- **DECLARED**: in-step contention (the port early by up to 956 T, 1,328 with Boris's record); the
  anchors are one world's -- against held-out natural worlds the stamps run -2.8K..+4.7K T and up to
  ~6 interrupt rows differ by a few writes (HB4 is in-sample; HB14 is the held-out two-player row);
  the 41 T interrupt response was not charged (~1.7K T over the block) until M7.68; near a frame boundary the
  block ends an interrupt sooner or later than the machine's (phase 22,909: 43 against 42); the
  ENTRY window -- a gate still open for the first 135 T -- was declared and unmeasured until M7.81.
- **THE ENTRY WINDOW, MEASURED (M7.81, `tools/hurryentry.py` -> `build/hurryentry_fixture.json`)**: every
  48K state played 300 frames, contended, under the key script, the trigger held off by its latch `$9049`.
  The fire comes on the first `$9037` after the interrupt that counts the clock past the threshold, so the
  candidates are the first entry after each interrupt: 12,660 of them, and THREE land inside the window --
  64 (`r50_48`), 84 (`r30_48`) and 111 T (`firekill`) before the next interrupt.  Fired there (the clock
  poked to the threshold at the interrupt before), the machine takes that interrupt with both gates OPEN,
  runs a whole pass, and shuts `$FEC5` 7,182 / 11,963 / 33,187 T after the entry.  What that pass changed
  and the block's main loop then read: nothing on two, four colour-shadow bytes on `firekill` (`$FA0D`
  `$FA2D` `$FA4D` `$FA4E`), every one read by `$9927 LD A,(HL) / AND $20`, bit 5 unchanged -- so the port's
  run-ahead, reading at the call, gets the machine's answer.  The port takes that interrupt gate-open
  (`hurryOpenIsrs`) and lands the block whole after it.  Still declared: a gate-open pass that flips a
  banner cell's colour-shadow bit 5 or a player's BIT 7 first -- not seen.  1,655 surveyed frames ran no
  `$9037` (a pass past a frame), so a fire can come at threshold + 2.
Gated by SFX10/SFX10b (flipped from the pins they were), HB1..HB23 and HE1 / HE2.

## $F5E7..$F663 -- THE CONTROL-SELECT SCREEN (front-end GROUP 3, H-a, M7.53)

MEASURED by `tools/ctrlselect.py` -> `build/ctrlselect_fixture.json`: player 1 driven from boot.pkl's
own entry `$F5BC`, player 2 after each of player 1's four choices (118, 107, 104 and 80 characters),
the Firebird line over all 256 old attribute values, fourteen printer probes, CHARS moved on both
printers, `$FAC3` on two paths and eight phases, and a read census from `$F664` to the relocation.
- **THE SCREEN IS FOUR RUNS BY PC** (TRAPS #153): the CLS `$F709` (6,912 display bytes, BORDCR ANDed
  with `$F8`, one `OUT ($FE)` of 0 that is not a sound edge); the rainbow `$F82A` (832 attribute stores
  over 704 cells, 128 of them twice, eleven row-runs); the Firebird line (256 display + 32 attribute
  stores, row 21); the printer `$F80B` (1,888 stores for seven strings, 118 glyphs).  So the reading's
  "one number" (M7.37 §11) splits, and GROUP 3's boundaries fall on its KEY READS: **H-a** the screen,
  complete before the first key read (`title.pkl` sits exactly there: 0 screen and 0 `$6200..$FFFF`
  differences from the driven `$F664`); **H-b** the key read `$F7B3`, the menu, the dispatch, the three
  presets and the key-table builder; **H-c** the redefine screen (its prints and reads interleave);
  **H-d** the load spine `$F5BC..$F5CF`, `$FAC3`, the `$9601` key copy and the wiring.
- **TIME**: `$F5E7 -> $F5F0` 182,450 T and `$F5F8 -> $F664` 194,099 T at boot.pkl's frame phase
  (179,000..189,617 and 190,914..194,159 over eight phases); player 1's paint runs with IFF 0.  Recorded
  as `BB_FE.OPEN_T`/`PAINT_T` and NOT charged -- H-b's frame layer charges them as debt, as
  `BB_TITLE.PAINT_T` was until M7.110 (the title's paint is now its instructions on the frame clock, BB_TPAINT).
- **THE FIREBIRD LINE** (`$FA71`, "LICENSED BY FIREBIRD SOFTWARE") goes through the ROM's channel-2
  printer, and the port reproduces its MEASURED effect, never ROM code: eight display rows and then the
  attribute per character, 32 characters from row 21 column 0; each attribute becomes old AND `$3F` for
  all 256 old values (with the hand-over's ATTR-P, MASK-P and P-FLAG); the glyphs come through CHARS
  (moved to `$3D00` and `$3C01` on the machine to prove it); the stream's seven control bytes are CHECKED,
  not interpreted, so any other stream is a named failure.
- **THE PRINTER `$F80B`**: `$F850` is a NOP or a RET -- code and state -- that switches printing; '@'
  ends a string; `$F829` (a data byte inside the code block) is the skip counter; the column add carries
  into the high byte (`$50E0` + `$28` = `$5108`); `BB_FE.PRINT_MAX` 64 is a diagnostic bound above the
  longest string's 27.
- **NOT MODELLED, AND WHY** (the review's F1, measured): the paint writes 16 ROM system-variable bytes (14
  system variables and 2 channel-table bytes) and 20 stack bytes.  13 of the 36 are READ before
  `$96A5`'s LDIR rewrites them at cold start -- FLAGS by the ROM keyboard scan (`$F7B8`'s RST `$38`),
  ten more by the ROM print of player 2's Firebird line, and `$61A5`/`$61A6` (the CALL `$F5E7` return
  address) by the game's RET at `$F708` -- but no GAME PC reads any of the 16, and their values are
  DEAD: restored to boot's at `$F664`, player 2's screen, `$4000..$FFFF` at `$96B0`, every register and
  T are unchanged, on two paths; a positive control (P-FLAG poisoned) changes 256 bytes of player 2's
  screen (TRAPS #227).
- **INTERRUPTS**: the menu runs with IFF 1.  `$F7B3` calls the ROM's interrupt routine itself, and that
  routine ends by re-enabling interrupts, so frame interrupts are accepted alongside the explicit calls
  -- the M7.37 reading said the opposite (TRAPS #228).
- **`$FAC3`** (H-d's): A = `$30` and BC = `$075E` on every path; `$F5CC` comes 994 T after the 256th frame
  boundary after `$F5C9` (T = 256 x 69,888 + 994 - the phase at `$F5C9`: 255.05..255.96 frames); it writes
  FRAMES, the +0/+1 bytes of the KSTATE set that holds the last key (`$5C04`/`$5C05`, or `$5C00`/`$5C01`
  after player 1 '3' and a player-2 redefine), and the stack.
- **FOR H-b**: the ROM's key decode is NOT a pure function of the keys down -- CAPS or SYM with A, then the
  shift released while A stays down, keeps returning the first decode for 20 frames and never accepts
  (menu and redefine, interrupts on and off); an interrupt can land inside the key click (2 of 8 phases,
  +1,205 T).  GATED in M7.61 (below).
- **H-b, BUILT (M7.61, `tools/ctrlmenu.py`, `BB_MENU`)**: the ROM scan behind `$F7B8` is held as its
  measured input/output -- FREEZE (two non-shift keys, or CAPS+SYM with one: nothing changes), NONE (the
  sets age), KEY; two sets [key, count 5, delay, code], aged BEFORE the match, the SECOND set taken first,
  REPDEL 35 / REPPER 5 scans, a repeat emitting the STORED code (the latch).  The filter `$F7BD`: SPACE ->
  `$5F`, ENTER -> `$5D`, `>= ':'` less `$20`, accept `'0'..'Z'`.  The test `$F667`: `'1'..'4'` and not
  `$F671`.  The dispatch `$F674`: `$F850` := 0, `$F671` := A unless `'2'`, `$F982` := A - `$31` (nothing reads
  it); KEMPSTON copies 8 raw bytes from `$F9F4` (no builder); SINCLAIR's `$F6B9` one-shot takes `6790` once,
  then `1245`; CURSOR `5807`.  The builder `$F6DB`: SUB `$30`, an EIGHT-bit SLA (measured with answers
  `$B0..$DF`: the offset wraps), [half-row, mask] from `$F988`, the cursor on by 8.  The click: 241 OUTs,
  366,849 T uncontended.  The frame layer charges every path's measured T (the open/paint contention law
  at 64 phases, interrupts OFF, so the interrupts player 2's pass takes are charged on top); an
  unmeasured `$F671` at the paint, or a scan path with no T, is a named failure.
- **THE MENU IS THE DEFAULT** (the owner, 2026-09-28, revising decision 2b's keyboard-and-gamepad-only
  plan): the page will present the full original control select -- SINCLAIR and CURSOR are keyboard
  layouts, KEMPSTON is served by a gamepad -- and skip `$FAC3`'s 5-second black screen behind a named
  flag.  Until H-d wires it, row (r) asserts the built page never runs `ctrlOpen`, `ctrlPaint` or
  `feSeed`.
- **THE SUBSTITUTE FONT** (the review's F7): the check now refuses a glyph equal to ANY 8-byte window of
  the ROM, and one within 3 bytes of its own ROM cell moved -2..+2 rows.  The old 'P' (since M7.20) was a
  ROM window -- the ROM's lowercase 'p' moved one row -- and the new 'K' and '.' were 2 bytes from their
  own cells moved a row; all three redrawn (bytes differing 245, window minimum 1, displaced minimum 3;
  `build/hurryfont.json` re-derived).  TRAPS #229.
Gated by the M7.53 block, rows (a)..(r), the reachability row and the font-distance row.

## $F723..$F7B0 -- THE REDEFINE SCREEN (front-end GROUP 3, H-c, M7.62)

MEASURED by `tools/redefine.py` -> `build/redefine_fixture.json`: eleven drives from `$F723` to the
builder's RET on four worlds (player 1 KEYBOARD; player 2 KEYBOARD after player 1 took 2, 3 or 4),
interrupts OFF, each answer held from its read's first scan to its accept; the T laws at 64 phases
with 16 held-out midpoints; five key scripts from boot.pkl's own `$F5BC`, a sample at every frame
boundary.
- **THE CODE.**  `$F723` CLS, rainbow, `CALL $F72F`, `JP $F6DB`.  `$F72F` (a NOP nothing writes)
  prints "CHOOSE KEYS FOR PLAYER n" (`$F8AD`, its digit `$F8C4`) at column 3 of row 1 and "LEFT :?"
  at column 9 of row 5; then five `CALL $F7B3` -- H-b's key read, whose echo now PRINTS, because
  `$F674` left `$F850` a NOP: the column stepped back over the '?' and the answer drawn there.  The
  answers go to `$F983`, `$F984`, `$F986`, `$F985` (THE THIRD AND FOURTH SWAPPED) and `$F987`, each
  followed by the next prompt (RIGHT, FIRE, JUMP, "ALL OK ?", rows 8/11/14/17).  `$F796 CP 'Y' / RET z`
  returns to `$F72C JP $F6DB`, the builder, whose RET goes into the spine.  Anything else comes round:
  `$F7AA` CLS, rainbow, `JP $F72F` -- the answers kept until overwritten.
- **THE CHEAT.**  `$F799 SUB 'R'`: player 2's 'R' (`$F8C4` = '2') stores A = 0 at `$F6A3`, turning its
  RET into a NOP; player 1's 'R' arms nothing.  `$F7A7 CALL $F6A3` then runs -- armed -- the checksum
  `$F6A4`: A plus `$F983..$F987`, less `$8F`; zero stores 0 over `$FA3F` (the RET of the 128K
  trampoline `$FA3B`'s `LD HL,$FA67 / PUSH HL / RET`) and sends `OUT ($FE),2` -- a RED border, EAR clear
  -- which lasts until the loop's CLS reaches `$F716`, 178,907..189,526 T later by phase (2.6 frames in
  the cheat script).  A is 0 after the 'R' that armed it and the fifth answer less 'R' on every round
  after, so an armed player 2 can pass the checksum with a later non-'R' answer ("SSSR" + 'K' does, on
  the second round).  What `$FA3F`'s NOP does afterwards is not H-c's: a byte grep of the title image
  finds one jump to `$FA3B`, `$FAF1` -- `$FAC3`'s non-48K branch (H-d's) -- so on the 48K path the
  store is measured and kept, and its effect never runs.
- **THE ECHO'S CODES**: the filter's own -- the capitals, the digits, SPACE as '_', ENTER as ']', and
  SYMBOL SHIFT's X, 0 and H as '@', '?' and '>'.  The substitute font gained nine cells for them
  (`> ? @ J Q X Z ] _`), each at least three bytes from its own ROM cell moved -2..+2 rows and at
  least one from any ROM window (`tools/make_banner.py`; 60 codes, 292 of 472 bytes differing).
- **TIME** (interrupts OFF, so the frame layer charges the interrupts that land in them on top): the
  screen `$F723 -> $F748` 234,604..244,496 T, the loop `$F7AA -> $F748` the same but at three phases
  (40..75 T apart), the prompt `$F801 ->` the next `CALL $F7B3` 9,020..9,940 -- ONE law for all four,
  contention being by time, not address -- each by phase, straight lines between (held-out within
  117, 117 and 23 T); the click with its printed echo 368,286.5 T, the mean of 64 phases and the same
  for all five reads (851 T over the menu's silent echo); the exits and the builder by path, each the
  mean of 64 phases, because every CALL, RET, PUSH and POP touches the contended stack at `$61xx`
  (spreads 16..25 T); player 2's paint after KEYBOARD (`$F671` = `$31`) its own law, 154,999..158,500 T
  -- the skip gate drops '1. KEYBOARD' AND the header, 80 characters (H-a's bug, kept).
- **THE FRAME LAYER** (`ctrlFrame`): the dispatch's KEYBOARD opens the screen at once and charges its
  law (stage 'redefine'); each read is H-b's ('menu', 'click', 'release', the click's debt the echo's);
  each release stores the answer, prints the next prompt and charges the prompt law ('prompt'); the
  fifth charges its exit and then the builder ('prompt' still, as the machine's clock has it) or the
  loop's law ('redefine').  The frame interrupt scans in all of them.
- **DECLARED** (`BB_REDEF.DEPARTS`): `drawnAtOnce` -- the screen, the loop and each prompt drawn as
  their T begins (H-a's rule); the means are H-b's `meanPathT` and `clickMeanContention`.
Gated by H-c(a)..(h): all 180,160 screen writes of the eleven drives in the machine's order, the state
and every game byte after, the T tied to the fixture, the five scripts frame for frame, each stage's
spend at its step, the red border's frames, player 2's 80-character paint, and the page never running it.

## $9EA6..$9ECE / $9F18 / $9EFE -- THE LIGHTNING BOLT'S ENEMY KILL (M7.65)

`$9E90` (one bolt slot) erases the bolt and, off the boss round (`$9E9E CP $50`), scans the enemy table:
`LD HL,$FD9B` (slot 2's +7), `($AA57) - 2` slots through a DJNZ, stride 10.  A slot is a target when
bit 7 of +7 is SET -- a live enemy, a frozen one AND A CORPSE (bit 7 stays set while it flies).  Its +6
is tested against the bolt's +6 and then its +5 against the bolt's +5 by `$9F18`, and a hit stores the
+5 pointer into `$9EDF/$9EE0` -- the operand of `$9EDE LD DE,nn`, cleared at `$9E95`.  **The scan does
not stop: the last hit slot wins.**

`$9F18` is `EX AF,AF' / LD A,(HL) / AND $F8 / LD C,A / EX AF,AF' / AND $F8 / SUB 15 / CP C / RET nc /
ADD A,$1E / CP C / CCF / RET`, carry = hit: with both bytes aligned, `c > a - 15` and `c <= a + 15`,
**all eight-bit** -- a bolt byte below 16 hits nothing (the SUB wraps), and at the top the ADD wraps (an
enemy at `$F8` is hit by a bolt at `$F0`, not by one at `$F8`).  5,568 hits in the 256 x 256 table; the
`AND $F8` on the enemy byte shows only there (an enemy at `$63` is missed by a bolt at `$70`, as one at `$60`
is).  So `-16` for `-15`, `$1D` for `$1E` and `>` for `>=` at either compare are EQUIVALENT: after the ANDs
`a - 15` is 1 mod 8 and `a + 15` is 7 mod 8, never equal to an aligned byte.

Then the physics (`$9ED0`) moves the bolt and the bounds (`$9ED6 CP 15`, `$9EDA CP $E7`) may `RES 7` it
**with the record set: a hit the move carries off the screen kills nothing**.  Otherwise a record with a
nonzero high byte takes `$9EE5 OR A / EX AF,AF'` into the shared award tail, where `$9EF7 LD IY,$FFFB /
ADD IY,DE` makes the +5 pointer the slot BASE and `$9EFE CALL nc,$8BC2` births the corpse (the boss
hit's `SCF` suppresses it -- B6).  **A bolt passing back through the corpse it made kills it again**:
ellight's idle play kills slot 2 at ISR 22 and again at 24, slot 3 at 46 and again at 48, `($AA5F)`
falling each time.

The port: `boltEnemyScan(iy)`, `boltNear(a, v)` and `boltCorpse()`, which hands `corpseBirth` the
record less 5.  UNMEASURED: a count of 2 would make the DJNZ walk 256 slots -- no scanned round was
seen with no enemy slot.  MEASURED by `tools/boltkill.py` -> `build/boltkill_fixture.json`: `$9E90`
called at its own entry (interrupts off, uncontended) on 155 built r20_48 worlds (X and Y sweeps of one
enemy's window, two enemies in it, dead / frozen / first-visit / corpse targets, counts 3, 7 and 8, the
wraps, three despawned hits, unaligned enemies, a P2 bolt, the halved stride, slot 1) and on the 24 live bolts of 120 idle
ISRs of ellight, re-run from their entries; per call the record at `$9ED0`, the slot `$8BC2` was handed
and every non-display, non-stack byte written (the erase's, blit's and `$A447`'s own operands apart).
Gated by BK1..BK3c.

## $AA60 SLOT BY SLOT, AND THE 41 T BEFORE $8D72 -- THE ISR'S T (M7.68, PK7)

- **The acknowledge.**  I = `$FC`, so the vector is read at `$FCFF`: `$FFFF`, a JR whose displacement
  is the ROM's first byte, onto `$FFF4 JP $8D72`.  19 + 12 + 10 = 41 T on every accepted interrupt,
  before the `$8D72` bracket.  `BB_ISR_ACK`; isr() charges it; the span test does not (BB_INT_PHASE
  is the `$8D72` entry).  `BB_TITLE.DEPARTS` loses `isrShort41T`.
- **`$AA60`, measured by `tools/aa60cost.py`** on every 48K saved state (300 frames, contended, a key
  script): the prologue `$AA60 -> $AA85`, each slot `$AA85 -> $AA85` (the last to `$8D8F`), each handler
  run (entered by `$AAEA RET z` or `$AAEB JP (HL)`, ended by the next entry one word up or by `$AAEC`), each
  corpse flight `$8A78 -> $AB03`.  The parts tile the bracket on all 5,974 passes.  The skeleton (slot
  less runs less flight) is a closed function of the slot (`BB_AA60`, the instruction sums; listed in
  `docs/TIMING.md`) and the engine charges it exactly on all 134 recorded passes (AC1: each seeded into a
  fresh engine, its handlers stubbed and every slot handed the machine's bytes at `$AB0C`).  The handler
  runs and the flights are charged their fixture MEDIANS -- `$AB38` 1,606, `$AF31` 1,360, `$AF47` 1,416,
  `$AF5F` 1,417, `$AF77` 1,216, `$AF95` 941, `$AFAF` 911, `$AFC4` 1,493, `$AFF6` 1,486, the flight 5,712
  -- PROVISIONAL (AC2), reported as `frameLedger().aa60`.  The diverted pass (`$AA72 JP nz,$B520`) is its
  instruction sums, exact on 504 uncontended passes (AC3).  FORCED rows (declared): an enemy tracking P2
  (`$AAC5`, +5), a corpse whose delay is still running (`$AAB3`, 98), a Y at or past `$DC` (`$AB32`, +21)
  -- no natural run reached them.
- **What it moved.**  BT3 (the round banner): even interrupts exact; odd late 22..39 / -26..-16 T (were
  4,070..4,087 / 2,237..2,245 long); drift 605 / 1,421 T (was 17,966 / 8,057); the 2P hand-off's ISR
  count 62, the machine's (one more while the ledger was exact on the 41 and the flat term still
  long).  HB4: the ledger's points within 12 T of the machine's; three rows' write counts differ by
  1..7, the anchors' own ~150 T lateness (TRAPS #270).  PK7: a corpse tick's ISR is now -252 T against
  the machine's (was 1,000+ short); a pop's is still 8,431 short, DECLARED.

## THE ENEMY HANDLERS' T (M7.70)

- **The oracle.**  `tools/enemycost.py`: every run of the eight enemy handlers on every 48K saved state, 300
  frames, UNCONTENDED, under ab38cost's key script.  A run starts at the handler's address when the
  instruction before was `$AAEA RET z`, `$AAEB JP (HL)` -- or a RET: an ANGRY slot's second run is entered
  by the first run's own RET into the handler (the doubling pushed it): 1,907 of the 11,191 natural runs.
  The rows keep 2 runs of each (handler, path, T): a conditional RET that falls through and then RETs to the
  same place leaves the same branch targets as one that is taken, so the path alone lost the type-4 arc's
  end and the left homing fall (the battery's survivors found it).  Per run:
  T, every byte read before written (plus `$FE86/$FE87` when `$FE85` runs: that LD HL,nn's operand IS the
  generator's state), every byte written (the stack excepted), each `LD A,R` (site, A), the branch targets.
  18 FORCED CALLS (the handler called once on the machine from a saved state with the slot, `$B612/$B613`
  and the shadow cells it reads poked): type 4's two bottom wraps (`$B3F3`, `$AF90`), its launch below the
  player (`$B40F`), its aim to the right (`$B423`), a grounded probe with the row above solid (`$B3DE`), the
  tall arc (`$B439`), the landing (`$B45E`) and its look with the row above solid (`$B459`), the low-X skip
  (`$B447`); the flyer's `$C8..$DB` wrap (`$B2A7`); and the patched RET at `$B20D` / `$B25D` (types 6 and 7
  at a ledge with the player above); at the HUD's edge, where `$AED1`'s D crosses `$18`, a big-arc hop landing
  from Y 6 (its move then searches from Y - 8 = -2, the eight-bit D), a walker and a grounded type 4 at Y 8,
  type 4's small-arc landing at Y 8; and a flyer whose last Y is `$C2`.
- **The cost.**  `BB_EN` (web/game.js), indexed by the engine's own decisions; EN1 seeds each kept run,
  feeds BB_Rng its LD A,R values, and requires the T and every byte written, and that the engine writes
  NOTHING the machine did not.  Every write agreed before any T was added: the behaviour gates
  (walker_fixture and its kin) had already pinned it.

## $AB38'S T, AND $AED1'S ARM ABOVE THE HUD (M7.69)

- **The oracle.**  `tools/ab38cost.py`: every `$AB38` run on every 48K saved state, 300 frames,
  UNCONTENDED, its own key script (left / right / jump / blow pressed through each player's table at
  `$B5FD` / `$B605`, the Kempston bits for a `$1F` entry), plus 17 FORCED runs (declared in the tool).
  Per run: T from entry to return, the slot, the keyboard rows and Kempston byte, every byte read before
  it is written (not the instruction's own bytes), every byte written (the stack excepted), the branch
  targets.  The rows keep 2 runs of each natural path and 4 of each forced one: 882 of 7,205.
- **The cost.**  `BB_AB38` (web/game.js) is the per-instruction T summed over named ranges; AB1 seeds each
  row and requires the T and the writes.  The writes differ only in 12 SELF-MODIFIED OPERANDS the engine
  does not keep: `$AD3B` (the saved `$AE9C`), `$AD41/2` (the feet DE), `$ADA1/2` (the arc's table
  pointer), the erase's `$A431`, `$A480`, `$A584`, `$A5A6`, `$A5B1`, `$A5BE`, `$A5D1`.
- **`$AED1`, D < `$18`.**  The cell-address routine compares the EIGHT-BIT D (the probe row) with `$18`;
  below it, `$AED7 LD HL,$712F / XOR A / RET`.  The floor probe's cell walk then reads `$712F`, `$7130`,
  `$7131` (zero in every saved state) and the move's foot is CLEAR whatever `$712F` holds (the XOR's Z),
  with its cell above at `$710F`.  The port read the shadow's top rows (solid in round 1), so a player at
  Y < 9 -- after a bottom wrap -- landed on the ceiling.  probeCell and hBlocked now take the arm (AB3).
  The walker's `$B47B` already knew the page (`tools/walker.py`, the dummy reads).
- **The final death's `$BF0A`** costs 182 (its head) + 118 (`$A447..$A460`: the IX frame and the three
  gates) + the erase class (`BB_A3AD.ERASE_SH[y3]`, forced shifted by `$BF23`; `ERASE_HIGH` at a cached Y
  >= `$C0`) + 10 (`$A5D9` patched to RET) + 76 (its tail) -- exact at all five forced classes.

## $9460 / $A15F / $A159..$A258 -- THE WATER STREAM (M7.66)

Supersedes the summary in the water section above where they differ.  **The arm** `$9460`: `($A15A)`
nonzero or `($FECE)` (the flood) nonzero -> RET; `($FFFB)` := `($FFFA)`; HL := `((($FFF8) + 9) AND $F8) * 4
+ (($FFF7) + 8) >> 3 + $5800`, both adds EIGHT-BIT (`$F8..$FF` seed column 0 of the same row, `($FFF8)` =
`$F7` seeds row 0); `JP $A15F`.  **The seed** `$A15F`: `($A1AA)` := R (the WATER_DIR draw; only bit 0 is
read), `($A15A)` := 1, then down the SHADOW (`+$A000`) up to 22 cells for the first with bit 5 clear;
none -> `LD HL,9`, so the band is `$6009` (MEASURED: 24 of elwater's arms).  SEVEN words `$A25D..$A26A` :=
the cell; `$A26B`, the tail slot, keeps its old value until the first step shifts into it.

**The tick** `$A159` (`LD A,n` with n at `$A15A`) -> `$A190`: `($A194)` := `($8DBD)` (a `CP` operand
nobody reads), `($A15A)` := 1, `step(+$20)`; if blocked, `step(($A1AA) bit 0 ? +1 : -1)`; if blocked,
`($A1AA)` ^= 1.  A committed step returns from the whole tick (`$A1D0 POP AF`), so the direction
reverses only on a wall.  **The step** `$A1C6`: shadow bit 5 of the candidate blocks.  LDDR 14 bytes
(`$A25D..$A26A` -> `$A25F..$A26C`), head := candidate, painted `$2D` if `<= $5AFF`.  Tail := `($A26B)`:
past `$5AFF` -> `$A205` (`($A15A)` := 0) then `$A208`; else erased to `($8309) AND 7 OR $40` and, IF THE
HEAD was past `$5AFF`, `$A208` (the carry flag crosses in AF', `$A1EE`/`$A21C`).  `$A208` zeroes `$A25A`,
`$A259` and bit 4 of `$FDDA` and `$FDE4` -- **the riders let go while the stream runs on**, and only the
tail stops it.  Then, on every committed step, **the ride** `$A21F`: X := column * 8, Y := `(((H - $58)
AND 3) : L) >> 2 AND $F8 - 8` of the band's SECOND word, into `+5`/`+6` of each player whose bit 4 is set.
A head stepping left from `$5800` goes to `$57FF`, in the bitmap, and is painted `$2D` there (MEASURED).

The port: `waterArm`, `waterSeed`, `waterStream`, `waterAdvance`, `waterStep`, `waterDrop`,
`waterRide`.  MEASURED by `tools/waterstream.py` -> `build/waterstream_fixture.json` (interrupts off,
uncontended; the oracle refuses any shadow read outside `$F7C0..$FC3F`, so no fixture reaches the ROM
shadow of the `$6009` band).  Gated by WS1..WS3.  Not modelled here (other routines): the attach
`$9339`/`$936A` and the enemy drowning `$931A` already run and now see real `$2D` cells.

## $F5C6..$F5CF, $FAC3 AND $F5CC..$970E -- THE LOAD SPINE, THE PROBE AND THE HAND-OVER (front-end GROUP 3, H-d, M7.63)

MEASURED by `tools/loadspine.py` -> `build/loadspine_fixture.json`: 56 key scripts from `$F5C6` (player 1
'4', player 2 '3', driven from title.pkl) with every interrupt in the CLS and the probe as (T past its
boundary, length), five entered at `$F5C9` 5..40 T before a boundary, the cheat armed; the ROM interrupt
from the idle probe loop over every key, shift, path and chord; the CLS and the cold start at 64 phases
with 16 held-out midpoints; the hand-over from `$F5CC` into the title at 8 phases, on a second path and at
every phase that puts a boundary within 30 T before `$8CCA`'s EI or `$970E`'s.
- **THE CODE.**  `$F5C6 CALL $F709` (the CLS: the black screen), `$F5C9 CALL $FAC3`, `$F5CC LD HL,$F5D2 /
  JP $7274 -> JP $8CC3`.  `$FAC3 IM 1 / EI / HALT`, FRAMES zeroed, then `INC E / JR nz / INC BC / CP (HL)
  / JR nz` until the ROM's interrupt has counted FRAMES to `$FF`: `B` = 7 and `C` = `$5E` or `$63` answer
  `$30`, anything else `$80` through the trampoline `$FA3B` (`LD HL,$FA67 / PUSH HL / RET`) -> `$FA67 LD
  A,$80 / RET` -- back to `$F5CC` either way.  With the cheat's NOP at `$FA3F`, `$FA40` reads half-row
  `$FD` and, with A+D+G all down, `$FA4A..$FA66` rewrites the low three bits of the spawn records from
  `($7277)` -- 223 bytes over `$74A1..$799D` in the armed script: the enemies' types.
- **THE ROM INTERRUPT'S T IS A LAW** (`BB_ROMISR`), exact over 23,529 measured interrupts: the SCAN (25
  a half-row holding a key + 27 a bit up to that row's highest), and by path -- idle 895 (+24 CAPS alone,
  +51 SYM alone), +30 per set held, +5 per set an idle scan frees; a key's NEW by class and shift (letter
  1,355 / 1,380 CAPS / 1,400 SYM, digit 1,296 / 1,391 / 1,425 with SYM+2 +4 and SYM+0 +11, SPACE and ENTER
  1,273 / 1,309 / 1,344, CAPS+SYM 1,317), HELD 1,099 / 1,135 / 1,170 (CAPS+SYM 1,143), REPEAT +85, FULL
  +27; set 0 -28 held, +46 new; the other set held +30; +35 per set a key's scan frees; SYM with M, N
  or B -23.  FREEZE: two keys 822 + the scan; three or more stop at the third in port order --
  392/394/367/369 by where the first two sit, + 59 a half-row + 27 a bit.  It reproduces H-b's ten
  `isr_class` measurements, and H-b's path averages are gone (they could not serve a count).
- **THE PROBE, CYCLE BY CYCLE.**  Each instruction's T; `CP (HL)`'s read of FRAMES (`$5C78`, contended)
  delayed by the harness's ULA table (the pattern 6,5,4,3,2,1,0,0 over 128 T of each of 192 lines from
  14,335, applied when the instruction starts inside 14,312..57,245); an interrupt accepted where an
  instruction ends past the boundary, costing the law's T.  Every script's HALT, every interrupt's offset
  and length, BC, E, A and the T to `$F5CC` are the machine's EXACTLY.  With the keys up: `BC = $075E`,
  E = 153 -- 153 iterations of slack.  **'A' held 22 frames of the black screen answers `$30`, 23 answers
  `$80`** (CAPS+A and CAPS+SYM: 22); a freezing chord is CHEAPER than an idle interrupt and RAISES the
  count -- A+D+G held 100..115 frames gives `$0763` (the second 48K answer), 130 gives `$0764` (128K).
- **ENTERING THE PROBE:** interrupts are on (the menu's).  A boundary crossed by `CALL $FAC3` or `IM 1`
  is the ROM's interrupt there, and the HALT waits a whole frame for the next; one crossed by `EI` waits
  one instruction and the HALT takes it at once.
- **THE HAND-OVER.**  `$F5CC -> $8CCA` (the JPs, `DI`, the cold start) 59,105..69,231 T by phase
  (`COLD_PH`), `$8CCA -> $96DF` 10,179 (`EI`, `$9575`'s wait), `$96DF -> $970E` 525 (`DI` .. `EI`).  A
  boundary in the wait takes the GAME's interrupt (`$8D72`, both gates shut by `$9610`: 488 T, and it
  only counts -- `$8DB6` stays, `$8DBD` is cleared by `$96DF`); in the cold start or the reset half it is
  LOST -- unless EI and the instruction after it end inside the interrupt's 32 asserted T (11 T at
  `$8CCA`, 21 at `$970E`), when it is taken late.  The spine ends ~994 T past a boundary, so the natural
  hand-over takes one interrupt in the wait.  The cold start's `$9601` copies the staging buffer to
  `$B5FD` (modelled: `reset(keys)` lays the buffer back first).
- **THE CLS** (`CLS_PH`, 178,976..189,580 T by phase, interrupts off) is charged as debt with its
  interrupts on top, as H-b's open: at the scripts' phase within 33 T, but where the interrupts land
  elsewhere in it its remaining stores meet another contention phase -- up to 1,448 T (DECLARED; the HALT
  re-syncs the count).
- **THE PORT.**  The frame layer's stages after player 2's pass: 'spine' (the CLS's debt), 'enter'
  (`CALL`/`IM 1`/`EI`, one at a time), 'halt', 'probe' (`probeRun`), 'hand' (the hand-over as debt,
  `handIsr` deciding each boundary).  At `$970E` `handDone()` rebuilds the game's world -- `reset(buf)`,
  the page's clocks and sound log kept, the front end's counters in `fePast` -- counts a taken interrupt,
  runs `gameStart()` and finishes the frame the game's way (the title's main line, then `isr()`).
- **DECLARED.**  `skipProbe` (ADDED, default ON: the owner, 2026-09-28) answers `$30` at `$F5C9` with no
  count.  An `$80` answer on a 48K is the 128K leg (`$96B3`: the AY engine through the screen into
  `$C350`, over the sprites), NOT modelled: `probe128` counts it and the port takes the 48K leg.  The
  armed cheat's `$FA4A..$FA66` is reached on a 48K only on that leg: counted (`probeCheats`), not modelled.
Gated by H-d(a)..(j).  WIRED in M7.64: the page boots through `ctrlBoot(BB_MENU.LOAD_PHASE)` (34,943, boot.pkl's
`$F5BC` phase) and `step()` delegates to `ctrlStep()` while `ctrl` is set; the whole load -- both passes, the
redefine screen, the probe run, the hand-over, forty frames of the title -- is diffed frame for frame against
`tools/loadpath.py` (M7.64(b), and the built page's own loop in (c)).  The faithful page has no Kempston
interface: `padKempston` (ADDED, default OFF) keeps a gamepad off port `$1F`.

## THE 48K BEEPER LAYER -- every in-play OUT ($FE), and the hold across the frame interrupt (M7.52)

MEASURED by `tools/beeper.py` -> `build/beeper_fixture.json`: every emitter at its own entry,
interrupts off, uncontended and at eight contended frame phases (the chirp `$8CB1` for nine values
of C, the site `$881D`, the storm's 256 ticks by class, `$8C28` on round1_48 and r20_48, the pause's
two OUTs, the HURRY UP! block, the front-end key click); three natural runs through the ISRs (a
collect in round1_48, a whole storm from arming to wrap, a HURRY UP! block); a census of every `OUT`
the code holds by site, and of the OUTs an in-play run executes.  The sound table above is the result.
What the port does with it:
- **The collect chirp** (`itemChirp`, `$881D..$8CC2`): forty OUTs at `66C + 41` from +35, and the
  55,793 T charged to the pass -- a collect holds the main loop four-fifths of a frame, as on the
  machine.  Where in the pass the chirp starts is still the flat `BB_PASS_T` clock (PROVISIONAL);
  the spacing is not.
- **The storm** (`effectThunder`, `$A09A`): the tick's `$A0B0 OUT 0`, the flash's four PRNG-ink OUTs
  (border = ink), the three strikes' `$FD`/`$FE`/`$FF` and the wrap into `$8C28`, at the measured
  offsets (`BB_STORM`).
- **The pause** (`$8FF9 OUT 4` at +96 T; `$9003 OUT 0` at +33 T from the spin's head) and **the
  reveal's tail** (`$8C4E OUT 0`).
- **HURRY UP!, RE-TIMED.**  M7.19's flat step put each flash's LOW and the HIGH after it at one
  instant -- a zero-width pulse, which the bridge's box integral plays as silence (TRAPS #225).  Now
  the first `$908F` at 615,340 T (contended) and the uncontended instruction sums after it
  (`BB_HURRY_PULSE`), every edge to the T against the fixture.
- **THE HOLD (`mainOut` / `flushHeld`).**  A main-loop OUT at or past the frame's interrupt point
  (`budget = span * FRAME_T - isrCost`) is held, re-based past the port's ISR and logged at the next
  `step()`; an edge exactly at the next budget is held again -- ONE boundary, `t < budget`, on both
  sides.  Every main-loop OUT goes through it but the pause gate's, which `$8FF6`'s DI lets log at
  once: the chirp, the storm, the reveal, the hurry, the pause release and the jump tone.  **DECLARED:
  the inserted gap is the port's own ISR window -- the interrupt that BEGAN the frame -- where the
  machine inserts the one that ENDS it, the opposite parity** (natural collects: the port inserts
  17..25k T, the machine 1,892); and for the same reason the storm's three strikes land one frame
  apart through `step()` where the machine's are 95,508 and 43,435 T apart.  Both are the frame
  ledger's layout (the ISR at the frame's end); fixing them means moving it, ledger-wide.
- **NOT BUILT, NAMED:** `$8C28`'s own 213,312 T is charged nowhere (`docs/TIMING.md` item 10); the
  HURRY UP! block's ISRs run with the gates OPEN in the port, 52..53 frames where the machine's block
  is 42.77 with both closed (older than M7.52, pinned in SFX10 -- the next increment); the umbrella's
  `$A110` and the level-skip's `$894B` reach `$A0E0` and `$8C4E` on paths the port does not run
  (SFX1's `NOT_PORTED_CALLERS`, TRAPS #226); the key click is front-end group 3's.
Gated by the M7.52 block, SFX1..SFX13 (with SFX10b..SFX10d).

## $8C51 -- THE DYING ENEMY'S FINAL REPAINT: $A447's ERASE-ONLY ENTRY, EVERY ARM (M7.51)

`$8BC2`, the corpse birth, is `DI / LD HL,$AA5F / DEC (HL) / CALL $8C51 / ...`, and `$8C51` is `LD
A,$C9 / LD ($A5D9),A / CALL $A447 / XOR A / LD ($A5D9),A / RET`: the entity master with its erase/draw
junction patched to RET -- the erase-only entry the capture's `$BE92` runs, with the dying enemy's
OWN flags and cache (before `$8BCA` changes the sprite).  So it takes `$A447`'s gates in order: bit 7
clear (`$A451 JP p`) or bit 3 set (`$A456`) -> `$A437`, `BIT 5 / RET nz / SET 5 / LD HL,$AA5F / DEC
(HL)` -- no erase, and a second `$AA5F` decrement only when bit 5 was clear; otherwise `SET 6`, and a
first visit (bit 6 was clear) or a cached Y of `$C0` or more goes to the patched RET; otherwise the
ERASE at the CACHED (+3, +2): aligned (`$A483`, two columns, a plain copy, +7 at `$A485`) or shifted
(`$A53C`, three masked columns, +20 at `$A56A`) by the CACHED X & 6, never the current one.  No
`$A5DC` DEC, no `$A5E0` SET 5, no draw.  The call's own T, uncontended: 1,448..1,540 with an aligned
erase, 3,065..3,145 with a shifted one, 167..235 without.
Until M7.51 the port ran `$A437`'s bookkeeping alone, and only for bit 7 clear: a live enemy's last
frame stayed on the display and `$A431` missed the add (DECLARED, COUNTED and PINNED by M7.49), and a
FROZEN enemy with bit 5 clear cost `$AA5F` one where the machine costs two.  `corpseFinalRepaint()`
now runs `entityEraseHalf()`, the ONE spelling of the erase-only entry for `$8C56` and `$BE92`, with
`$A437` whole.  The port does not model `$A447`'s self-modified operands (`$A50B`, `$A584`, the
eight mask bytes `$A5A2..$A5D1`, the junction `$A5D9`): each erase writes its own before its loop
reads them, and `$A5D9` is `$00` before and after every call.
In play: every live `$8C51` entry runs in the MAIN LOOP with interrupts off (`$8BC2` opens with DI;
`$93D3 EI` follows the environment kill's CALL), through `$93D0` (the environment kill: fbkill ISR
11, shifted; elwater ISR 576, aligned, its add carrying `$FC -> $03`), `$92A2` (the heart's touch
kill: `$927D`'s arm while `($FED0)` is set -- `$9298 EX DE,HL / LD IY,$FFF9 / ADD IY,DE / DI / PUSH
IX / CALL $8BC2`, from `$925A` at `$8D52`, `$92B9 EI` after the award -- wired, `playerHit` ->
`enemyDies` -> `corpseBirth`, but NOT in this oracle: `($FED0)` is `$00` in every 48K capture, so
its census never meets one) or `$9EFE` (the elemental bolt's enemy kill: ellight ISRs 22 and
46) -- wired since M7.65 (`boltCorpse`).  The pop's
births come through `$B82B` in the ISR and are frozen; and `$9EFE` also re-births the corpse it
made two ISRs earlier (ellight ISRs 24, 48, 50 and 52: +7 `$AD`, `$8BF3`'s `$8C|dir` with bit 5 set
by the entity pass's own `$A437`), so a bit-3 entry is a frozen enemy OR a corpse.  Every bit-3 or
empty slot the census met had bit 5 SET, so whether play ever reaches `$A437`'s SET 5 / DEC arm
through `$8C51` is PROVISIONAL (unseen: none in this oracle's census, none among the 355 bit-3
`$8C51` entries of the M7.49 review's scratch probe runs).
firekill's only idle kill (7,369 ISRs, the M7.51 review) comes in a `$931A` call an ISR entered
first (the ISR moves the enemy into the fire mid-walk).
MEASURED by `tools/corpserepaint.py` -> `build/corpserepaint_fixture.json`: `$8BC2` and `$8C51` called
at their own entries (interrupts off, uncontended) on 32 built worlds in slot 4 of r20_48 and of
firekill -- every arm, both erase boxes filled with synthetic display and shadow patterns -- and on
every enemy slot of r20_48, elfire and firekill as they stand (170 calls: r20_48's five live
enemies take `$A431` `$21 -> $28`, the review's number); fbkill's and elwater's first natural
environment kill re-run through `$931A` from its entry; a census of every `$8C56` entry on those runs
and on 600 idle ISRs of ellight; 17 claims (one of them: each of 3,992 operand fetches follows a
write to that byte in the same call).  Gated by the M7.51 block, CR1..CR7.

## $8EC9 / $90A9 -- THE ONE-LEFT ANGER (M7.50)

`$8E3A`, the main loop's level-clear decision, tallies bit 7 of +7 over `($AA57) - 2` slots; with
exactly one set, `$8EC9 CALL $90A9` runs on every main-loop pass outside the boss round (249 calls
in N1, 3,535 in L1), and
the decision still answers "not yet" (`$8ECC OR $2A` leaves NZ).  `$90A9` is `LD A,n / OR A / RET nz
/ INC A / LD ($90AA),A / XOR A / LD ($FEC4),A / CALL $90C1 / LD A,1 / LD ($FEC4),A / LD ($FEC5),A /
RET`: the operand `$90AA` is a LATCH, so only the FIRST call walks -- `$90C1` SETs bit 2 of +7 (the
ANGRY bit, which `$AAE6` doubles: the survivor runs its handler twice per tick, 2 px to 4 px per odd
ISR) and ANDs +5 with `$F8` on every enemy slot, dead ones and corpses included, with `$FEC4` shut
around it -- and both gates end at 1.  The hurry trigger `$9037` reaches the SAME body by falling
into `$90A9`, so the two share the latch: whichever comes first walks, the other returns at `$90AC`.
`$90AA` has two writers only -- `$90AE` (:= 1) and `$9855` (:= 0, the `$9AC1` round-reset table's
eighth entry, walked by `$984B` at every advance); the spawner, the hurry reset `$915F` and the
respawn calm never touch it, so after one anger and a death the enemies stay CALM for the rest of
the round, through any later HURRY UP -- unless one escapes a bubble ($B69A).  The "last enemy" is often a CORPSE (bit 7 stays set on a
flying one), so the call starts when the second-to-last corpse lands.  The port had `$8EC9` as a stub
`roundOneLeft(){ }` from M7.7-b to M7.50: `angerPass()` is now the one transliteration of `$90A9`,
called from `$8EC9` and fallen into by the hurry.  MEASURED by `tools/oneleft.py` (direct calls on 42
built worlds, six call sequences, two natural main-loop differentials of 6,811 and 5,594 rows, a
seven-run census; 6,782 and 5,544 rows compared, the rest cut by an ISR): a MAIN-LOOP differential, because `popkill.py`'s rows are ISRs re-seeded from
the machine and never run `$8E3A` -- which is why the stub was invisible to the whole suite.

## $A430 / $A431 -- THE BEAM ACCUMULATOR, IN THE PASS AND OUT OF IT (M7.49)

`$A430` is `ADD A,n / LD ($A431),A / RET nc / RET`, and `n` IS `$A431`: each call adds A to the byte
and leaves the sum as the next call's addend.  `$A3D2 LD A,$B9 / $A3D4 LD ($A431),A` seeds it at the
top of EVERY `$A3AD` pass (2,453 of 2,453 passes in the pop-kill scenes, every first `$A3D9` add
reading `$B9` -- the fixture's facts.a431), so no band -- `$A42B`'s exclusion `[acc, acc+$1E)` -- ever starts from what an
earlier pass or an out-of-pass call left: it does NOT persist across frames, as H12 read it from
direct calls.  Six sites call it: the pass's two +1s per visit (`$A3D9`, `$A40C`) and `$A447`'s
erase and draw (`$A485` +7 aligned, `$A56A` +20 shifted, `$A616` +8 aligned, `$A708` +11 shifted --
the return addresses give the sites).  And `$A447` is entered OUTSIDE the pass too, each entry
adding to whatever the last pass left:
- `$BF28` inside `$BF16` (`bubbleErase`, reached from `$BF0A`'s `cacheSetAndErase`): `$A480` forced
  to JP, so always the SHIFTED erase, +20 -- and nothing at all when the cached Y is `$C0` or more
  (`$A464`'s gate comes before the add; N1's falling corpse at cached Y `$C0..$C6`);
- `$BE92`, the capture's erase half (`entityEraseHalf`): +7 or +20 by the CACHED X, nothing on a
  first visit or at a cached Y of `$C0` (the capesc rows bracket it: `tools/walker.py`);
- `$91D6`, Boris's draw, in the MAIN LOOP with interrupts off: +8 on his first draw, then +7 +8
  (he steps eight pixels, so always aligned) -- `tools/boris.py` phase (g);
- `$8C56` (`$8C51`) on a LIVE enemy -- an environment kill (`$93D0`), the heart's touch kill
  (`$92A2`) or the elemental bolt's (`$9EFE`): +7 or +20, with a display erase (a frozen enemy takes
  `$A437` and adds nothing, which is all the pop-kill births are).  M7.49 declared, counted and
  pinned it; MODELLED since M7.51 (`corpseFinalRepaint` -> `entityEraseHalf`, above).  The M7.49
  review measured 110 such entries in long play, and a replay with only that erase undone still
  differed by 12 display bytes 400 ISRs later.
The port kept the accumulator in a JS local seeded `$B9` and stored it at the pass's end, so every
out-of-pass add was lost -- 2,233 of +20 and 19 of +7 in the pop-kill scenes: "differs by multiples
of `$14`".  Invisible on the display (no band reads the byte before the next re-seed), so `$A431` itself
is the only witness, and it joined the compared vector; the carry's +4 T of an out-of-pass add falls
inside PK7's declared ISR-cost gap (unmeasured there, not equivalent).  Inside `$A447` the carry
IS witnessed: `tools/entdraw.py` CALLs it on the uncontended harness with `$A431` seeded to carry
at each of its four sites (+4 T each).  `beamAdd(add, A)` is `$A430` on `ram[$A431]`.
Oracle `tools/popkill.py` (facts.a431 brackets every `$A430` call and every ISR edge: no writer but
`$A3D4` and `$A432`, no main-loop call in those scenes, the outside adds by entry) and `tools/boris.py`.

## $AA60 / $AB38 -- THE PLAYER INTERLEAVE, the respawn calm, $AD0C (M7.48)

`$AA60` dispatches EVERY slot through the handler list at `$B54E`: `$AAD3` takes the entry and bumps
the cursor, `$AAE5 PUSH HL`, `$AAE6 BIT 2,(IY+7)`, `$AAEA RET z` (run once) or `$AAEB JP (HL)`
(run twice: the pushed copy runs it again).  The list's first two words are `$AB38, $AB38` -- the
PLAYER routine, image values nothing rewrites (the spawner fills `$B552` on; measured by the M7.48
review's machine lens over 243 spawner runs, 55 states and 106k frames of play, with 40,050
dispatches in 19 states of rounds 4..81 never putting a player slot after an enemy) -- so slots 0
and 1 (`$FD80`, `$FD8A`) move the
players INSIDE the slot loop, in slot order, before any enemy's `$AAC1..$AAD0` copies the tracked
player's X+8/Y into `$B612/$B613`.  An enemy therefore reads its player's POST-move position.  The
port ran the players in a separate `updatePlayers()` AFTER the pass from M7.6-ii to M7.48, and:
- the enemies read the PRE-move X/Y (the INTERLEAVE row runs the old order on I1 and I2: 51 of
  160 rows and 34 of 114 differ from the machine);
- `$AAE6`'s doubling (+7 bit 2, the angry enemy's second run) applies to a PLAYER too -- it is the
  FAST WALK power-up (item 14, `$88A7 SET 2,(IX+7)`): he walks, reads his keys, ticks his
  invulnerability and his blow cadence twice per heavy frame, and DIES twice as fast (I5, I6, I10,
  I13: the natural death respawns at ISR 186); the port ran each player once;
- the per-slot tail `$AB0C` (X forced even and clamped to `$10..$E0`, Y wrapped) runs AFTER the
  player's move.  Before or after is invisible while X is even, but the right step's crossing test
  reads `(X+15) & $F8` against `(X+17) & $F8`, which is parity-sensitive: from X = `$DF` beside the
  right wall the step crosses into column 30 and is BLOCKED, and the tail evens it to `$DE`; a tail
  run first would make it `$DE`, which does not cross, and step to `$E0` (scene I8);
- `$AB38` has NO activity test (it opens `BIT 2,(IY+$5A)`): the pass's `$AAB6 BIT 7,B` is the only
  gate, and `$AAE6` decides the second run BEFORE the first.  So a fast-walking player's final death
  (`$AB64 RES 7`) is followed by a second run that ticks his invulnerability, reads his keys and
  walks him although he is out (I9: +4 `$50` -> `$4F`, X `$18` -> `$1A`; I12 the same for P2).  The
  port's `updatePlayer` had refused an inactive player -- harmless while the players ran outside
  the pass, a second gate inside it -- and the guard is gone;
- the blow click `$ACAF OUT ($FE),A` comes once per run, so a fast-walking blower OUTs twice per
  ISR (I14), 1,916..2,280 T apart on the machine.  DECLARED: the port runs the ISR at the frame's
  end and holds each click at the frame's last T (M7.44), so every OUT of one ISR -- the doubled
  pair, and P1's and P2's (2,312..2,591 T apart) -- lands at one instant; the count and the levels
  are gated on every row, the times are provisional (the ISR T gap, PK7).
The respawn (`playerDeathTick`, `$AB5E..`) CALMS the enemies: `$ABB4 CALL $ABD5` XORs `$90D0` with
`$40` (`$ABD5` does nothing else, and has only these two callers -- the review's census), turning `$90CF`'s `CB D6`
SET 2,(HL) into `CB 96` RES 2,(HL); `$ABB7 CALL $90C1` walks every enemy slot (clearing bit 2 and
still ANDing +5 with `$F8`); `$ABBA CALL $ABD5` flips it back -- for P1 (I3) and P2 (I10), and on
the last life too.  `$90D0` is state, not code: only `$D6` and `$96` were ever observed there;
`hurryAnger()` decodes it and throws on anything but SET/RES n,(HL), `reset()` seeds the image's
`$D6`, and the engine counts the SET walks (`hurryAngers`) and the RES walks (`hurryCalms`)
apart.  And the grounded jump edge is `$AD08 LD (IY+9),1` then `$AD0C RES 4,(IY+$5A)` -- the
jumper's own bit (I4 for P1; I11 stages it on both and P2 jumps) -- where the port had stopped at
the first.  The respawn's lives panel also repaints the lost life's cell in the SHADOW screen
(`$806C`'s `$80C0`): six bytes, the only shadow writes in the pop-kill scenes, and the engine's
`livesPanel()` writes the same.
Oracle `tools/popkill.py`, scenes I1..I14, 33 claims (per-ISR RAM-vector differentials, the
dispatch order kept as counts from `$AAE5`, events at `$AB38`, `$ABB7`, `$AD0C`, `$AB0C` and
`$ACAF`); `$90D0` and the flash toggle `$A3B2` joined the compared vector.

## $ABF4..$ACEB -- THE IN-PLAY KEY READER (M7.44)

On the ODD ISR, inside `$AA60`'s player handler `$AB38` (after the invulnerability tick, before
the physics), P1 at slot 0 then P2 at slot 1 -- TWICE for a player with +7 bit 2 (the fast walk,
`$AAE6`, M7.48); skipped while dying and under the `$B54B` settle divert, and for an inactive
player because the pass does not dispatch one -- except the doubled run after a fast walker's
final death, which `$AB38` (no activity test) runs on a player who is out (popkill I9/I12).  Table `$B605` if `+$5A` bit 0, else `$B5FD`: four `[half-row, mask]` pairs
LEFT, RIGHT, JUMP, BLOW, pressed when `IN & mask == 0`.  LEFT held skips RIGHT's pair with no IN
(LEFT priority).  A first byte of `$1F` switches to the Kempston branch `$AEF5`, active high,
with NO priority (L+R sets both and faces RIGHT).  `C` = previous low nibble << 4, then the
bits; the air rule at `$AC54` locks L/R through phase 1..`$0F` and drops the jump to `$FF` on a
change from `$10`; `$AC83` faces LEFT first; `$AC9B..$ACE5` writes the sprite pointer
(`$D7C0`, +`$160` facing left, +`$2C0`/`$580` blowing) and runs the blow cadence (`(cad+1) AND
+$5F`, the edge bit 0 with bit 4 clear, a speaker click `OUT ($FE),cad*8` per step); `$ACEB`
stores `C`.  A `($00,$00)` pair is permanently pressed.  Other writers of `+8`: the respawn's
`$ABA1` (1), `$99E8` at a join or round start (0), the bubble bounce `$B984` (4/8 then
`$FD`; implemented M7.47, popkill B1/B2/B6).  **The port's `BB_KEYTAB` is not the tape's** (the tape holds zeros): P1 plays O/P/Q/SPACE
and P2 6/7/9/0 until front-end group 3's control select seeds the table.  The page's arrows
(5..8) and a gamepad do NOT move P1 under it -- a declared, stated gap.

## $95F3 -- THE COLD START, whole (increment G, M7.40)

MEASURED by `tools/gameover.py`'s `phase_cold_start` (fixture `build/gameover_fixture.json`,
key `cold`), armed at `$8CC3` on `title.pkl` -- which holds the tape bytes naturally, since
it is captured before `$95F3` runs (it fails the `m[$8DC4] == $C9` 48K guard for exactly that
reason).  `$D167..$D18F` is never entered: a PC guard asserts it on every step.

```
  $95F4  EX AF,AF'              the machine flag ($30 = 48K / $80 = 128K) parked in A'
  $95F5  LD A,($5B5C)           BANKM -- read BEFORE $96A5 relocates over it
  $95F8  LD ($9AE7),A           read only by $8DEA/$8DF8/$8E12/$8E20, behind the 48K patches
  $95FB  LD DE,$B5FD / LD BC,$10 / $9601 LDIR    the KEY COPY -- HL is a live parameter
  $9603  LD HL,$7581 / LD DE,$95F3 / LD C,$10 / $960B LDIR    the SELF-OVERWRITE
  $960D  XOR A / OUT ($FE),A    border black
  $9610  LD HL,$FEC4 / $9613 LD B,$12 / $9615 CALL $AA49    eighteen bytes
  $9618  LD HL,$FC00 / LD DE,$FC01 / $961E LD BC,$0100 / $9621 LD (HL),$FF / $9623 LDIR
  $9625  $FFFF = $18 (JR) / $962A $FFF4 = $C3 / $962F $FFF5 = $8D72 / LD I,$FC / IM 2
  $963B  LD HL,$FD00 / $963E LD BC,$0080 / $9641 CALL $AA49    B = 0 -> TWO HUNDRED AND 56
  $9644  LD IY,$FD00 / four CALL $9662, HL = $4000 / $4800 / $5000 / $0000
  $967F  LD HL,$01FF / LD ($FD00),HL / LD ($FD02),HL    the LOW half only
  $9688  LD HL,$FFE1 / LD B,$10 / CALL $AA49 / $9690 LD A,2 / $9692 LD ($FFE3),A
  $9695  EX AF,AF' / $9696 CP $80 / $9698 JR z      -- 128K skips the patches
  $969A  LD A,$C9 / LD ($8DC4),A / LD ($8E05),A / LD ($8E0A),A
  $96A5  LD HL,$E000 / LD DE,$5B00 / LD BC,$06A8 / $96AE LDIR    the relocation
  $96B0  CP $C9 / $96B2 RET z   -- returns only because the 48K leg left $C9 in A
```

| | 48K leg | 128K leg |
|---|---|---|
| opcode dispatches (contended harness) | **3,322** | 3,318 |
| writes | **2,440** | 2,437 |
| the three patch bytes | `$C9 $C9 $C9` | untouched |
| display writes | 0 | 0 up to `$96B2`; the `$96B3` continuation then writes 3,860 |

The legs differ by exactly the patch: **4 dispatches, 3 writes.**  The dispatch count is the
contended harness's, which steps each LDIR per iteration -- it is not a Z80 instruction
count.  The **2,440 writes** are the contention-independent number.  T-states are a RANGE,
**59,053..69,182** over sixteen frame phases, because `$96AE` writes contended RAM.

### The numbers that are easy to get wrong

* **B = 0 MEANS 256** at `$963E` (`BC = $0080`): `$9641` clears `$FD00..$FDFF`, the table
  AND the player records' page.
* **The IM 2 fill is 257 bytes**, `$FC00..$FD00` -- 1 from `$9621` plus 256 from the LDIR.
  The 257th, `$FD00`, is the vector's high byte: cleared by `$9641`, rewritten by `$9662`,
  and finally `$FF` from `$967F`.  These 256 bytes of `$FF` are ALSO the band that stops a
  flyer at the wrap edge; the port used to write them in `reset()` for that reason alone.
* **`$9662` builds 64 words, both halves**, with an EIGHT-BIT `ADD A,L` at `$9673`.  On the
  machine's four calls (all `L = $00`) an eight- and a sixteen-bit add agree; `L = $20` is one
  of 224 starting low bytes that separate them.  `$967F` patches the LOW half only, so rows 0
  and 1 are `$01FF` while their shadows are `$E000`/`$E020`.  Entry 24 is `$0000`.
* **The self-overwrite target is `$95F3..$9602`**, not `$9603` (which is the LDIR's own
  `LD HL,$7581`).  The payload is round 15's spawn record, `48 21 60 21 88 20 A0 20 31 71 78 70
  C1 70 00 48`, and it lands on `$95F5..$95F8` -- so `$9AE7`'s writer destroys itself and no
  capture of play shows where `$9AE7` came from.
* **The high score**: sixteen bytes cleared from `$FFE1` (not `gameReset()`'s twelve from
  `$FFE5`, which leaves the record alone on purpose), then `$FFE3 = 2` -- 20,000 stored,
  rendered as 200,000 because `$7FC0` writes eight digits and never the ninth.
* **`$9575`**: 10,033 T of body (10,050 with the CALL), from one call site, `$8CD2`.
* **SP must move before `$96AE`**: the incoming SP is the relocation destination's last byte.
  Without `$8CC4 LD SP,$96DD` the routine does not reach `$8CCA`.

### A second entry

`$95F3` has one caller and the cold-start code is destroyed after it runs, so a second entry
never happens.  It was driven anyway, and **it is not the first entry replayed**: a real second entry skips $95F5/$95F8 and $9601 (so $9AE7 is NOT rewritten and no key copy happens), overwrites 26 bytes through $960C and eats its own LDIR (BC = hi(ret)*256 + $10), takes its CP $80 from the A' the first run left, and runs with interrupts live until $967E.
It does re-apply the patches, `$FFE3 = 2` and the relocation, and `POP BC` eats the return word
-- 3,322 dispatches and 2,431 writes, which reconcile as 2,440 − 2 (outer push) − 1 (`$9AE7`) −
16 (key copy) + 10 (the extra overwrite).

The port's `coldStart()` RE-APPLIES on every call, and that **replays the first entry** -- which
is right because every production call IS a first entry: `reset()` starts with `ram.fill(0)`
and is a fresh load, so it cold-starts exactly once.  The gate asserts the boundary that makes
this safe: the game lifecycle, including the game-over wrap into `$8D02`, never cold-starts.

### What the port does not model, and says so

* **`$9601`'s key copy is MODELLED since H-d (M7.63)** -- `reset(keys)` lays the control select's
  buffer back at `$F5D2` and the cold start copies it.  Before H-d it was DECLARED SKIPPED:
  HL arrives from `$F5CC` pointing at the
  staging buffer the control select builds (front-end group 3); no shipped asset reaches it,
  so an LDIR now would copy sixteen zeros over `$B5FD`, which type 4's tall arc reads as a
  signed Y delta.  `reset()` keeps seeding `BB_KEYTAB` -- a capture emulator's redefine, NOT the tape's
  bytes (the tape holds zeros; M7.44a).
* **`LD I,$FC` / `IM 2`** are CPU state; the port's frame driver is the interrupt.
* **The 128K continuation at `$96B3`**: `coldStart($80)` does everything up to `$96B2`
  faithfully and then throws, by name.
* **A key held through `$FAC3`'s 5.1-second probe sends a 48K machine down the 128K leg** -- the
  threshold MEASURED by H-d (M7.63): 'A' held 23 frames; the port counts the `$80` (`probe128`) and
  takes the 48K leg.  The M7.40 note:
  Measured by the M7.40 review: SPACE held gives `BC = $0757`, `A = $80`, and the cold start
  ends at `$96B3` with the patches left at their tape bytes.  The port always passes `$30`
  until `$FAC3` is modelled (front-end group 3), and must then decide what to do with `$80`,
  since `coldStart($80)` throws.

