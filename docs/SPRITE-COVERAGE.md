# Bubble Bobble (Firebird 1987, ZX Spectrum) — Sprite Coverage Report

Synthesised from five concurrent class extractions, each graded by an adversarial
verifier. Every address is a Z80 code/data address in the loaded 64K image
(`build/image.bin`, offset == address). Format facts are backed by disassembly
(`tools/adis.py`) and/or a harness measurement (`tools/blitforensics.py` two-background
differential, or a live write-watch through the SkoolKit harness). This report
distinguishes **MEASURED** (observed on the running machine or format-agnostic
differential) from **INFERRED** (bank/offset from code, bytes from the static image,
frame never drawn live).

House rule: a bank is marked **verified** here ONLY if its class verdict was true or
the specific claim survived the verifier. Two class verdicts came back **false**
(bubbles, boss-census); the offending claims are called out in GAPS and are NOT
reported as verified.

---

## (a) Blitter census

Every draw routine that puts pixels (or attributes) on screen, its format, and the
sprite class it serves. All confirmed SPRITE writers blit **direct to the display file
($4000–$5AFF)** — the 28-state census found **zero** SPRITE writes to $E000–$F7FF.
**CORRECTION (2026-09-08, R12):** that does NOT mean there is no back-buffer. `$E000–$F7FF`
IS the clean-platform back-buffer/shadow (written by the round builder `$8260`, cleared
`$AA4A`, restored 22×8 to the display each frame by `$8216`; `$F800–$FAFF` = the attribute
shadow). The census surveyed only the per-frame SPRITE blitters, which composite straight
onto the display and never target the shadow — so "no sprite writes to $E000+" is right, but
"no back-buffer" was wrong. Sprite banks / object tables live at `$D000–$D7FF`, `$5B00`, and
the `$FD80+` structs, not in the platform shadow. (The one subtlety: the bubble blitter
*reads* a parallel copy at screen_high+$A0 as a second compositing source — see GAPS.)

| Routine | Format | Class served | Evidence |
|---|---|---|---|
| `$A447` (master) | 16×16 MASKED stack-blit master entry (CALLed, returns $A405). Builds shifted mask/data into $A000 staging, copies staging→screen. Dispatches straight path or the X-shifted $A53C path by X&6. | player / enemy | MEASURED (disasm + first-hit probe: IY=$FD80 ptr=$D7C0) |
| `$A53C` | X-SHIFTED variant of $A447 (X&6≠0); edge masks patched from table $AA4F into $A5A2/$A5B5/$A5CD. | player / enemy (shifted) | MEASURED (disasm) |
| `$A600` | 16×16 MASKED fast path. `LD SP,HL` parks SP at (IY+0/1); 64 bytes = 16 rows × [maskL,dataL,maskR,dataR]; screen=(screen AND mask) OR data @ $A652. 2 screen bytes/row. | player / enemy / Boris | MEASURED (`extract_sprites --verify`: 32 pops/32 writes/0 mismatch; blitforensics @$A600→$A405 = "16×16 MASKED") |
| `$A6F3` | X-SHIFTED variant of $A600 (from $A611 JP nz when X&6≠0). 24px/3-byte span: per row POP DE / AND E / OR D / LD (HL),A ×3. | player / enemy (shifted) | MEASURED (disasm). NB brief cited $A53C for this; $A53C is the *master-path* shift, $A6F3 the *$A600-path* shift. |

**Sprites are PRE-SHIFTED, 352 (`$160`) bytes each -- RESOLVED 2026-09-10 (M7.2).** The game does
NOT shift at draw time; each sprite stores FOUR pre-computed copies and `$A6F3` selects one by X's
even sub-position (`s = X & 6`): **s=0 at +0** (64 B, 4 B/row, 2 screen bytes), **s=2 at +$40**,
**s=4 at +$A0**, **s=6 at +$100** (each 96 B, 6 B/row, 3 screen bytes) -- block base = `2*(24s-16)`.
Total 64 + 96×3 = 352 = `$160`, which is exactly the enemy-bank stride (`$C260-$C100`). So the
"64-byte" figure in this table is only the s=0 block; the full sprite is `$160` bytes. The JS engine
blitter (`web/gfx.js bbBlit16`) reproduces this byte-identically at every shift (test/bb.test.js
M7.2). ACTION: `extract_sprites.py` grabs only the 64-byte s=0 block via the aligned-blit hook; to
ship shifted sprites it must grab all `$160` bytes per base.
| `$A2C2` (wrapper) | Wraps $A2D5: NOP-patches the two `OR (HL)` opcodes @ $A307/$A30C ($B6→$00) → **16×16 OPAQUE** copy, then restores. 2 bytes/row × 16, MSB-first, 32 bytes. Reached via `JP $8762` (opaque tile path); it has **no CALL callers**. | items / effects (opaque tiles) | MEASURED (blitforensics --entry 0xA2C2 = "16×16 OPAQUE") |
| `$A2D5` | Same routine entered directly = **16×16 OR/additive** (transparent, INK-only). IX=$FD00 row table, DE=(IY+0/1), self-mod col offset @ $A304, dest +$06. | effects (bolt, sparkle); entity mono | MEASURED (live source-capture in ellight; OR opcodes B6/B6 at draw) |
| `$A280` | Second copy of the $A2D5 OR-blit at dest col-offset +$1C. Used *with* $A2D5 to composite the 32×32 GIANT collectibles from 16×16 tiles. | items (giant composite) / effects | MEASURED (census writer-PCs $A2B6/$A2BB span $4844–$4F64 in candycane) |
| `$A314` | X-shifted OR variant of $A2D5 (self-mods shift @ $A349/$A33D/$A355). Same sources shifted; also the bolt background-erase pass. | effects (shifted); cross-cut Boris/water | MEASURED (disasm; bolt drawn $A314-shifted in ellight) |
| `$A076` | FIRE column copier (LDI-style): C=$FDF2 columns, 8 bytes down (INC H) from source self-modded @ $A074 ($A39D/$A3A5) to screen ptr $FDF0. OPAQUE, 8px/col. | effects (fire) | MEASURED (forced $9F64=$2A in elfire: $A077 wrote 5 cols × 8 rows) |
| `$A8C1` | **32×32 MONO OPAQUE.** LDI copier, 4 bytes/row × 32 = 128 bytes, MSB-first. Self-mod SOURCE @ $A8C2 ∈ {$5B00 C=0, $C080 C=2, $FE02 else}, self-mod X @ $A8DB, dest from $FD00[pose]. Paints 4×4 attr grid ($A8FC/$A925). Callers $A844, $AA29. | boss + giant items (shared) | MEASURED (blitforensics --state boss = "32×32 OPAQUE, 128 bitmap+16 attr"; direct drive: 128/128 bytes == source for all 3 sources) |
| `$B9E7` (bubble) | **Shifted MASKED stack-blit.** Entry $B9E7 (master call $B653; also $BE5B/$BEAF → JP $B9E7). Logical 16×16, rendered 24×16 = 3 bytes/row × 16. Saves SP in IX, parks SP = base + 48×(IY+5 & 7), POP data; edge mask from table $BFF8 = [00,80,C0,E0,F0,F8,FC,FE], not the buffer (buffer is DATA-ONLY). Ends RET $BBB0. Writers span $BA00–$BD22. | bubbles | MEASURED (blitforensics: MASKED, model_mismatch=0 all 6 variants) |
| `$BF5B` (builder) | Not a blitter: builds the flashing/element bubble $D380. LDIR the 384B $C780 in, overlay an 8-byte glyph from table $C068[(7E0E−2)] into the interior, regenerate 8 shifts via SRL/RR (48B/shift × 8). | bubbles (element/letter) | MEASURED (disasm + isolated run) |
| `$A929`/`$A9DA` | **NOT a draw** — 32×32 background SAVE/restore between display and $A000 staging (4 blocks of 32×8). The brief's "giants via $A929" is WRONG; this is the boss/giant ERASE pass. | (housekeeping) | MEASURED (disasm; writes to $A0xx) |
| `$8017`/`$876A`/`$9D56`/`$9780` | **NOT bitmap** — attribute painters ($5800–$5AFF only): HUD band; sprite recolour (AND $38 OR ink); boss flash colours; menu attr map. | (colour) | MEASURED (writes confined to attr file) |
| `$0BBC`/`$0C08`/`$FA88` | **NOT game sprites / OUT OF SCOPE** — Bleepload loading-screen (I-Ball) effect; loader animation. | (loader) | MEASURED |

---

## (b) Bank inventory

W×H, masked/opaque, format, the class JSON that holds the decoded bytes, and the
verified status per the class verdict. "MEASURED live" = bytes read from the running
machine or recovered by the format-agnostic differential; "INFERRED (image)" =
bank/offset from code, bytes from the static image, frame never drawn live.

### Players / enemies / Boris — 16×16 MASKED via `$A600` (`build/sprites_player_enemy.json`)

Class verdict: **VERIFIED = true.** Two sprites independently re-derived by the
format-agnostic differential; 8-entry enemy type-table pinned ($73B0..$73BF →
$73C0/$73D9/$73E1/$73EB/$73F8/$7400/$7408/$7410); 11/11 live pointers reproduced with
zero new.

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $D7C0 | 16×16 masked | 64B 4B/row | PLAYER faceL pose0 (base) | MEASURED live (16 states) |
| $DA80 | 16×16 masked | 64B | PLAYER faceL pose1 (run) = base+$2C0 | INFERRED (image) |
| $DD40 | 16×16 masked | 64B | PLAYER faceL pose2 = base+$580 | INFERRED (image) |
| $D920 | 16×16 masked | 64B | PLAYER faceR pose0 = base+$160 | MEASURED live (14 states) |
| $DBE0 | 16×16 masked | 64B | PLAYER faceR pose1 | INFERRED (image) |
| $DEA0 | 16×16 masked | 64B | PLAYER faceR pose2 | INFERRED (image) |
| $C6C0 | 16×16 masked | 64B | PLAYER special faceL (bubble-trapped/spin-death), set $AB44 | MEASURED live |
| $D300 | 16×16 masked | 64B | PLAYER special faceR, set $AB49 | MEASURED live |
| $C100 | 16×16 masked | 64B | ENEMY t0 primary (draw $AF31) | MEASURED live (4422 hits) |
| $5B80 | 16×16 masked | 64B | ENEMY t0 opposite facing — runtime MIRROR in low RAM, re-centred by 1px (NOT a bit-exact flip; use captured bytes). image.bin invalid here. | MEASURED live (3975 hits) |
| $D040 | 16×16 masked | 64B | ENEMY t1 primary (draw $AF47) | MEASURED live (ellight) |
| $D1A0 | 16×16 masked | 64B | ENEMY t1 facing B = $D040+$160 | MEASURED live (ellight) |
| $CD80 | 16×16 masked | 64B | ENEMY t2 primary (draw $AF95) | MEASURED live (elfire/umbrella) |
| $CEE0 | 16×16 masked | 64B | ENEMY t2 facing B = $CD80+$160 (verified flip) | MEASURED live |
| $C260 | 16×16 masked | 64B | ENEMY t3 (draw $AFAF; DE=0 → single frame, no +$160) | MEASURED live (r20_48/r30_48, 2026-09-09: the only t3 base blitted) |
| $C3C0 | 16×16 masked | 64B | ENEMY t4 primary (draw $AF77) | INFERRED (image) |
| $C520 | 16×16 masked | 64B | ENEMY t4 facing B = $C3C0+$160 | MEASURED live (r30_48, 2026-09-09) |
| $CAC0 | 16×16 masked | 64B | ENEMY t5 primary (draw $AF5F) | INFERRED (image) |
| $CC20 | 16×16 masked | 64B | ENEMY t5 facing B = $CAC0+$160 | MEASURED live (r50_48, 2026-09-09) |
| $C680 | 16×16 masked | 64B | ENEMY (draw $AFC4; DE=0 single frame, bilaterally symmetric). *By spawn-index this is type7, not t6 — see GAPS.* | INFERRED (image) |
| $D500 | 16×16 masked | 64B | ENEMY (draw $AFF6). *By spawn-index this is type6.* | INFERRED (image) |
| $D660 | 16×16 masked | 64B | ENEMY t6 facing B = $D500+$160 | MEASURED live (r40_48, 2026-09-09) |
| $FF50 | 16×16 masked | 64B | BORIS / Skel-Monsta chaser, set $9234 (NOT the 32×32 boss) | MEASURED live (boris, 475 hits) |

Corpse/death set — verifier's **missed-banks** find, same $A600 family (`build/sprites_player_enemy_extra.json`):

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $C700 | 16×16 mono | 32B, 2B/row | enemy CORPSE tumble frame 0; loader $8A9B/$8B53/$8BCA selects by (IY+4)=0/1/2. **RESOLVED**: drawn by the `$A280` mono OR-blit (read PCs $A2B4/$A2B9), span $C700..$C71F = 32 B -- NOT the $A600 masked path. | MEASURED live (read-watch, ellight) |
| $D340 | 16×16 mono | 32B, 2B/row | corpse frame 1 (same $A280 mono path) | MEASURED (format resolved via $C700 read-watch; 32B spacing to $D360) |
| $D360 | 16×16 mono | 32B, 2B/row | corpse frame 2 = $D340+$20 | MEASURED (format resolved) |

### Bubbles — runtime-built, `$B9E7` shifted-masked (`build/sprites_bubbles.json`, corrected in `build/sprites_bubbles_letters.json`)

Class verdict: **VERIFIED = false.** Bytes and blitter format are correct, but the
recovered *bitmaps* for several element/letter bubbles were contaminated (shadow
compositing not zeroed) and the EXTEND letter set was missed. Use the corrected file.

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $C780 | 16×16 masked | 8 shifts × 48B (data-only; mask from $BFF8) | empty travelling bubble (IY+9==0) | MEASURED live (patched IY+9=0; mm=0). Bitmap correct. |
| $C900 | 16×16 masked | 48B/shift | holding-an-enemy bubble (IY+9==1); enemy composited by $B121/$B147/$B1B4/$B3F5/$B460/$B574/$D701/$D78B — **cross-cut with enemy class** | MEASURED live (one instance). Bitmap correct. |
| $D380 | 16×16 masked | 48B/shift, built by $BF5B | elemental/flashing bubble (IY+9≥2); content = $7E0E element; ANIMATES | MEASURED live; **bitmaps re-derived shadow-zeroed** (see corrected file) |
| $B614 | 16×4 opaque | 2B/row | WATER symbol overlay (element 2) | MEASURED (image) |
| $B61C | 16×4 opaque | 2B/row | LIGHTNING symbol overlay (element 3) | MEASURED (image) |
| $B624 | 16×4 opaque | 2B/row | FIRE symbol overlay (element 4) | MEASURED (image) |
| $C068 table | — | 2B entries, idx=7E0E−2 | element-art pointer table, elements 2..12 (idx 0-10); idx 11 ($C07E=$3E3E) is dead padding, never indexed ($7E0E max = 12) | MEASURED (disasm) |
| $3E28/$3EC0/$3EA0/$3E70/$3E20 | 16×4 | 2B/row font glyphs | EXTEND letters E-X-T-E-N-D (elements 5–10 = E,X,T,E,N,D; 11=E,12=D) from game font $3E20–$3EC0 | MEASURED (corrected file; elem 9 'N' seen in extn, elem 12 'D' in extend/boris) |

### Items / fruit / collectibles / corpse / giants — mono via `$A2C2`/`$A2D5` and 32×32 via `$A8C1` (`build/sprites_items.json`, addendum `build/sprites_items_review.json`)

Class verdict: **VERIFIED = true.** Bytes/format correct throughout; two claims
corrected (evidence mis-attribution + incomplete index formula) — see GAPS. Both
sprite-index paths documented in the review file.

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $5D00 bank ($5D00–$603F) | 16×16 opaque | 32B, 2B/row MSB-first | unified item bank, 26 entries. Fruit: sprite=$5D00+((type&F)+10)×32. Power-up: sprite=$5D00+$8639[type]×32 (remap table [0,0,1,2,2,2,3,4,4,4,5,6,7,7,8,9]); path chosen by flag $872C | see rows below |
| $5D00 | 16×16 opaque | 32B | power-up idx0 = sweet | MEASURED live (sweet) |
| $5D20 | 16×16 opaque | 32B | power-up idx1 = red-lamp super | MEASURED live (powerup) |
| $5D40 | 16×16 opaque | 32B | power-up idx2 = candy-cane on-ground item | MEASURED live (candycane) |
| $5DE0 | 16×16 opaque | 32B | power-up idx7 = bottle | MEASURED live (bottle) |
| $5E40 | 16×16 opaque | 32B | collectible type0 (cherry/apple; brief said "banana") | MEASURED live (X64Y168; triple match) |
| $5E60 | 16×16 opaque | 32B | collectible type1 — *also the WATER SPLASH tile (effects class)* | MEASURED live |
| $5E80 | 16×16 opaque | 32B | collectible type2 = ice lolly | MEASURED live (X224Y136) |
| $5EA0 | 16×16 opaque | 32B | collectible type3 = grapes | MEASURED live (ellight) |
| $5EC0…$5F60 | 16×16 opaque | 32B | collectible types 4–9 | INFERRED (image) |
| $5F80 | 16×16 opaque | 32B | collectible type10 = '?' random box ($861D[10]=$FF) | MEASURED live (crown) |
| $5FA0 | 16×16 opaque | 32B | collectible type11 | MEASURED live (spawn) |
| $5FC0…$6020 | 16×16 opaque | 32B | collectible types 12–15 (14/15 = chili L/R) | INFERRED (image) |
| $C700 | 16×16 opaque | 32B mono | enemy CORPSE frame0 (STATIC; only ever an entity ptr at $8A9B/$8B53/$8BCA; '$CD33' is a data false-positive). Anim (IY+4) 0→1→2. | MEASURED (image). 32B spacing $D340→$D360 forces mono-16 (32B) not 64B masked. |
| $D340 | 16×16 opaque | 32B mono | corpse frame1 | MEASURED (image) |
| $D360 | 16×16 opaque | 32B mono | corpse frame2; on landing writes a $9607 fruit entry ($8B8B) | MEASURED (image) |
| $5B00 | 32×32 opaque | 128B mono | GIANT DIAMOND (candy-cane power-up); C=0 source; attr from $A890; spawn $88F9 | INFERRED (image); format via shared $A8C1 (boss path) |
| $C080 | 32×32 opaque | 128B mono | GIANT FRUIT / level-clear giant; C=2 source; attr $A8B0; spawn $88FD | INFERRED (image); format via shared $A8C1 |
| $FE02 | 32×32 opaque | 128B mono | CROSS-CUT: boss main frame (3rd source of $A8C1) | see boss class |

### Effects / elementals — `$A2D5`/`$A2C2`/`$A314`/`$A076` (`build/sprites_effects.json`, audit `build/sprites_effects_audit.json`)

Class verdict: **VERIFIED = true.** Core elemental sprites all re-derived exact;
verifier additionally found a whole 16×16 opaque tile sheet drawn by the same path
(cross-cut with items). Two semantic labels corrected.

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $6000-$6140 | 16×16 | 2B/row, 32B each | PROJECTILE sprites (2 slots $5B00/$5B0A, drawn via $A2D5 OR): $6000/$6020 BOULDER (kind 1, type-1 enemy); $6040/$6060 FIRE facing-left + $6080/$60A0 FIRE facing-right (kind 6 = type-6 enemy's breath AND the red-cross player fireball, +8=8); $60C0/$60E0/$6100 BOTTLE spin (kind 5, type-5 enemy, boomerangs); $6140 FALLING shot (kind 7, type-7 enemy). See SPEC "RED CROSS / projectile system". | MEASURED 2026-09-09 (code + live fireball) |
| $A37D | 16×16 | 2B/row, 32B | LIGHTNING BOLT (elemental type3). **TRANSPARENT / OR-composited** — see GAPS: boss-class report wrongly called it opaque. Drawn via object dispatch $9E85/$9E90 → $9F10 `JP $A2D5` (OR, opcodes B6 at draw); $A314 shifted; $A314 is the erase pass. | MEASURED live (ellight; 32 bytes match, masked differential) |
| $CA80 | 16×16 | 2B/row, 32B | POP/BURST sparkle frame0. $C006 engine, slot table $5CE0 → $C043 CALL $A2D5, OR/additive | MEASURED live (ellight, pixel-exact) |
| $CAA0 | 16×16 | 2B/row, 32B | sparkle frame1 (sibling; $C038, selected by JR c @ $C03B) | INFERRED (image) — never observed selected; see GAPS |
| $5E60 | 16×16 opaque | 32B | WATER SPLASH blob ($A2C2→$A2D5 opaque). *Also collectible type1.* | MEASURED live (blitforensics elwater) |
| $5D00 | 16×16 opaque | 32B | shared sheet tile (elwater water surface; also sweet room) | MEASURED live ($8903 tile ptr) |
| $5D80 | 16×16 opaque | 32B | generic bonus-room decoration tile (swirl/flower, water.pkl) — NOT "water splatter" | MEASURED live ($8903 tile ptr) |
| $A39D | 8×8 opaque | 1B/row, 8B | FIRE flame frame0 ($A076 column copier; bottom row $FF = burning floor) | MEASURED live (forced $9F64=$2A) |
| $A3A5 | 8×8 opaque | 1B/row, 8B | FIRE flame frame1 (counter bit3 @ $A055) | MEASURED live (same run) |
| $5D20,$5D40,$5D60,$5DE0,$5E00,$5E40,$5E80,$5EA0,$5EC0,$5F80,$5FA0,$6020 | 16×16 opaque | 32B | 12 more sheet tiles drawn by $A2C2→$A2D5 across saved states ($6020 only via $A314 shifted). CROSS-CUT with items collectibles. | MEASURED live (audit file) |

### Boss (Super Drunk) 32×32 — `$A8C1` (`build/sprites_boss.json`)

Class verdict: **VERIFIED = false** (the graded report blob). The three 32×32 frames
and $A8C1 are correct and complete, but two bank descriptions in the report were
materially wrong (bolt draw-mode; burst provenance). **The on-disk
`build/sprites_boss.json` is already corrected** — the artifact carries both fixes;
only the report text was wrong.

| Addr | W×H | Fmt | Note | Status |
|---|---|---|---|---|
| $FE02 | 32×32 opaque | 128B, 4B/row MSB-first | Boss main frame (C not 0/2). $A8C1. | MEASURED live (128/128 == source) |
| $C080 | 32×32 opaque | 128B | Boss alt pose (open-mouth/blob); C==2 ($A876) | MEASURED live (128/128) |
| $5B00 | 32×32 opaque | 128B | Boss burst/starburst; C==0 ($A86D). **STATIC/preloaded in image.bin** (85 nonzero bytes == live, byte-for-byte) — NOT runtime-built as the report claimed. | MEASURED live + image match |
| $A37D | 16×16 | 2B/row, 32B | Lightning bolt — **mask=TRUE, TRANSPARENT/OR-composited** (report wrongly said opaque). Bytes correct. See effects class + GAPS. | MEASURED live (draw mode corrected) |

---

## (c) Gaps, unverified banks, and outstanding corrections

> **RESOLVED after synthesis (main session, direct measurement):** the corpse-frame format dispute.
> A read-watch on `$C700..$C740` in `ellight` (corpses present from f37) showed the sprite bytes are
> read ONLY by PCs **`$A2B4` / `$A2B9`** -- inside the **`$A280` mono OR-blit** -- and the span touched
> is exactly **`$C700..$C71F` = 32 bytes**. So `$C700/$D340/$D360` are **16×16 MONO (2 B/row, 32 B)**
> drawn by the `$A2xx` family, NOT 64 B masked via `$A600`. (Consistent with `$A600` never having seen
> `$C700` across all 28 states, and with the 32-byte `$D340`->`$D360` spacing.) `$A280` therefore
> serves entity corpses as well as the giant-composite second tile.

### Class verdicts that came back FALSE (do not treat the original report claims as verified)

1. **Bubbles — element/letter bitmaps were shadow-contaminated.** Root cause: the
   `$B9E7` blit READS a parallel buffer at screen_high+$A0 (the $E000-region "shadow")
   at $BA7D and composites it as a *second* background, then writes only the real
   screen. blitforensics (which zeroes/watches only $4000–$5B00) left the shadow dirty
   and silently recovered contaminated sprites; model_mismatch=0 does NOT catch a
   constant hidden third source. Corrected sprites (shadow-zeroed) are in
   `build/sprites_bubbles_letters.json`:
   - `extend "D"` (elem 12) and elem 10 "D": true sprite is a clean bubble + small "D"
     glyph, NOT a filled bubble.
   - `elem_water` rows 0–3 and `elem_fire` rows 0–4 in the original were checkerboard
     contamination.
   - `empty` ($C780), `holding_enemy` ($C900), `elem_lightning` were unaffected (shadow
     clean at their Y) — those original renders are correct.
   - **Method fix (also affects `tools/blitforensics.py`):** to recover any
     $B9E7/$BE5B/$BEAF bubble sprite you must zero BOTH $4000–$5B00 AND the $E000
     shadow ($E000–$F800) before the differential. `--target` cannot express a second
     zeroed region, so the tool mis-recovers this blitter by default. **Not yet applied
     to the tool.**
   - **Missed set:** the entire EXTEND letter-bubble set (elements 5–10 = E,X,T,E,N,D;
     11/12 duplicate E/D) via the $C068 table. Original captured only elements 2/3/4
     plus one mislabelled "12". Now captured clean in `sprites_bubbles_letters.json`.
   - Note: `bytes_b64` in the bubble files is the raw POP-order buffer, NOT a linear
     row-major bitmap — it does not decode to the ASCII without the blitter.
   - Element 13 ($C068 ptr $3E3E, misaligned) renders garbage — **CONFIRMED unused (N25)**:
     $7E0E ∈ [2,12] (static class+2, or randomised (R&7)+5 = 5-12), so idx=7E0E−2 never reaches 11;
     $3E3E is 6 mod 8 = a misaligned mid-glyph read. idx 12-14 = $0000.
   - **RESOLVED 2026-09-10: idx 3-10 (elements/types 5-12, the RANDOMISED elemental) are ALL stale
     pointers into the Spectrum ROM font ($3D00+): type5→$3E28='E', 7→$3EA0='T', 12→$3E20='D', etc.
     Only idx 0/1/2 (water/lightning/fire = $B614/$B61C/$B624) are real. So a randomised-elemental
     bubble is drawn as a ROM-letter glyph, and popping it does NOTHING (effect dispatch $9E75
     handles only 2/3/4; SPEC "RANDOMISED / higher elementals"). The feature is unfinished/inert,
     not just idx 11.**

2. **Boss-census — two bank descriptions in the graded report were wrong** (the on-disk
   `build/sprites_boss.json` is already fixed, so no artifact edit is outstanding, but
   the report text must not be trusted):
   - **Bolt $A37D:** report said mask=false / OPAQUE via the $A2C2 NOP-patch wrapper.
     REFUTED live: the bolt draws via object dispatch $9E85 → $9E90 → $9F10 `JP $A2D5`
     (a JP, which is why a CALL-grep missed it), OR-composited (opcodes B6/B6 at draw),
     so it is **TRANSPARENT (mask=true)**, 16×16, 2B/row, 32B. The $A2C2 opaque wrapper
     has no CALL callers and (via `JP $8762`) draws a *different* sprite (a 16×16
     elemental ball). The effects-class report has this right.
   - **Burst $5B00:** report said "RUNTIME-BUILT, all-zero in image.bin". REFUTED:
     image.bin already holds the 85-nonzero-byte burst, byte-for-byte identical to the
     live states, and it is not written during the boss frames — it is STATIC/preloaded.

### Banks decoded from image only — INFERRED, never observed drawn live

- **Enemy banks t3–t7:** $C260, $C3C0/$C520, $CAC0/$CC20, $C680, $D500/$D660. No saved
  state advances far enough to draw them; bytes are valid loaded data + code-derived
  addresses, but not seen on-screen. A later-round state would confirm.
- **Player walk-cycle poses:** $DA80/$DD40 (faceL run) and $DBE0/$DEA0 (faceR run) —
  all supplied states have the player idle; code-derived + image-decoded only.
- **"Facing B" (+$160) frames** for t4/t5/t7 ($C520/$CC20/$D660) are inferred from the
  $AF2C mechanism (verified live only on t1 $D040/$D1A0 and t2 $CD80/$CEE0).
- **Giant items $5B00 (diamond) and $C080 (fruit) — RESOLVED 2026-09-09: BOTH now captured
  mid-draw live** (`$A8C1` fired with src `$5B00` in the candycane collect run and with src
  `$C080` in `peach_spawn-in.szx`, each on the last-corpse settle; both landed Xt14/Yt19 and
  were collected: +5600 / +2000 internal). Earlier note kept for the record: they were never captured mid-draw live
  (they spawn only in the level-clear sequence). Bytes read from image.bin; the 32×32
  format is verified only via the shared $A8C1 boss path, not a live giant draw.
  RESOLVED 2026-09-09: `$5B00` has a TRIPLE life -- the giant-diamond bitmap (static), the round-builder's tile scratch (`$8340-$83B5` write rows 5-7+ at build time), and at runtime the two PROJECTILE structs at `$5B00`/`$5B0A` (bytes 0-19, NOT cleared at level-clear: a planted struct survived to the giant's draw). So the DRAWN giant diamond's top rows carry residue: rows 5-7 show the build-scratch band (live `C00F/F03F/FCFF` vs the image's `CC33/F00F/FFFF`) -- the "strange artifact at the top" the player noticed -- and on a round where shots were fired rows 0-4 would show struct bytes. Original note: $5B00's low half is scribbled at runtime in non-boss states (overlaps the $5B80
  enemy-mirror region); image.bin holds the authentic diamond.
- **Sparkle frame1 $CAA0:** the $C03B carry branch never fired across 250+ frames of
  ellight, so frame1 was never observed selected — image-decoded only (format certain
  by sibling analogy to the live-verified $CA80).
- **Corpse frames $C700/$D340/$D360: RESOLVED (2026-09-08) — 16×16 MONO, 32 B, 2 B/row, drawn
  by the `$A280` mono OR-blit.** A read-watch on `$C700..$C740` in `ellight` (corpses present from
  f37) logged the read span as exactly `$C700..$C71F` = 32 bytes (PCs `$A2B4`/`$A2B9`) — a 64 B
  masked sprite could not sit 32 bytes from the next, and the frames re-decode as coherent
  tumble/dissolve mono. This matches the loader sites `$8A9B`/`$8B53`/`$8BCA`. The player_enemy
  extractor's earlier 16×16-*masked* filing was WRONG. Canonical reading = `sprites_items.json` /
  `sprites_player_enemy_extra.json` (both now mono 32B); a port carries the ONE mono reading.

### Unresolved mechanics (not sprite-byte gaps)

- **Enemy type t3 ($C260) opposite facing:** the type-table sets DE=0 (single frame,
  no +$160 flip), and $C260 is NOT bilaterally symmetric, so how its opposite facing is
  produced (a runtime low-RAM mirror like t0's $5B80, or it simply never flips) is
  UNRESOLVED. (t6/$C680 has DE=0 too but is symmetric, so no flip needed.)
- **t6/t7 name tags are swapped** in the player_enemy catalog vs the $73B0 dispatch
  order: table index 6 → $7408 → draw $AFF6 base $D500 (so $D500 is type6), index 7 →
  $7410 → draw $AFC4 base $C680 (so $C680 is type7). Banks/bytes are correct; only the
  labels are reversed. Cosmetic.
- **Fire spread cadence:** the elfire snapshot has fire idle; flame tiles/format were
  confirmed by forcing $9F64=$2A. The per-frame column-growth cadence and $FDF2/$FDF4
  extent are not fully characterised.
- **Water flow current** is NOT a bitmap sprite — it is attribute-only paint (ink $2D
  into attribute cells, algorithm $A1C6/$A1E6) with the splash tile $5E60/$5D00 drawn
  at the head.
- **Per-round fruit-type mapping and point values** ($811D score table, separate from
  the $861D colour table) were out of scope for sprites.

### Corrections not yet applied to code/tools

- `tools/blitforensics.py`: cannot zero a second region, so it silently mis-recovers
  the $B9E7 bubble blitter (shadow contamination). Needs a two-region zero option.
- The graded **boss-census report blob** still states the wrong bolt mode and burst
  provenance; the JSON artifact `build/sprites_boss.json` is already corrected.

---

## Class JSON files present in `build/`

| File | Class | Notes |
|---|---|---|
| `build/sprites_player_enemy.json` | players/enemies/Boris | 23 banks, $A600 masked |
| `build/sprites_player_enemy_extra.json` | corpse addendum | 3 banks ($C700/$D340/$D360), MONO 32B (resolved 2026-09-08; QA-updated) |
| `build/sprites_bubbles.json` | bubbles | 6 core variants + overlays; element/letter bitmaps SUPERSEDED |
| `build/sprites_bubbles_letters.json` | bubbles (corrected) | 12 shadow-zeroed entries incl. EXTEND letters — authoritative |
| `build/sprites_items.json` | items/fruit/corpse/giants | full $5D00 bank + corpse (opaque) + giants |
| `build/sprites_items_review.json` | items addendum | two-path index formula + power-up labels |
| `build/sprites_effects.json` | effects/elementals | bolt/sparkle/water/fire core |
| `build/sprites_effects_audit.json` | effects addendum | 20 entries incl. 12-tile opaque sheet |
| `build/sprites_boss.json` | boss 32×32 | 3 frames + bolt; already carries bolt/burst corrections |

All are decoded data (safe to commit); no tape-derived binaries.

## QA PASS (real-eyeball review, 2026-09-08) -- corrections applied

Rendered every sprite and eyeballed for garble. Findings + fixes:
- **FIXED -- enemy death-dissolve `$C700`/`$D340`/`$D360`**: were decoded 16x16 MASKED (64B) and rendered
  as noise; re-verified they are 16x16 **MONO** (32B, drawn via `$A280`; read-watch `$A2B4`/`$A2B9`
  span `$C700..$C71F` = 32B). Re-decoded mono -> coherent tumble/dissolve frames. `sprites_player_enemy_extra.json` updated.
- **FIXED -- phantom player run-poses `$DA80`/`$DD40`/`$DBE0`/`$DEA0`**: these were INFERRED at
  base+`$2C0`/+`$580` and rendered as noise. LIVE capture (round1, 90 frames of walk/jump/idle) shows
  the player uses ONLY `$D7C0` (faceR) and `$D920` (faceL) plus the specials `$C6C0`/`$D300` -- there is
  **NO separate walk-cycle sprite**. The four inferred banks were a bad offset; REMOVED from
  `sprites_player_enemy.json`.
- **CLEAN (confirmed by eye)**: the 4 player sprites; all enemy banks t0-t7 (incl. the image-derived
  t3-t7 -- recognisable creatures, just never drawn live); Boris; boss + the 2 giants; the bolt;
  bubbles incl. the EXTEND letters; the core `$5D00`/`$9605` item set (lamp/umbrella/cross/clock/
  shoe/banana/ice-lolly/burger/cake/crown/diamond...); the pop-sparks / water / fire effects.
- **LOW CONFIDENCE (flagged, not asserted)**: the TAIL of the `$5D00` sheet, roughly `$5FA0`-`$6020`,
  has a few noisy entries -- probably bonus-room decoration tiles or over-collection past the real item
  set. Treat those specific tiles as unverified until a state that draws them is captured.

### QA follow-up: giant diamond confirmed; `$5FC0`/`$5FE0` are NOT real (2026-09-08)

- **Giant diamond `$5B00` -- DATA confirmed, live draw NOT observed (correction).** `$5B00` DECODES to
  a clean 32x32 faceted cut diamond (rows 8-31) with a dithered "table" band on top (rows 5-7 =
  `CC33`/`F00F`/`FF`) -- that band is genuine sprite DATA, not a decode/sheet artifact. HOWEVER my
  earlier "confirmed live" was WRONG: in a no-input `candycane` run the giant does NOT spawn and the
  32x32 blitter `$A8C1` NEVER FIRES -- the `$A8C2`=`$5B00` I saw was just the operand's default, not an
  actual draw. OPEN: whether the on-screen giant diamond is this `$5B00` 32x32 (via `$A8C1`) OR is
  tile-composited from 16x16 tiles via `$A280` (the sprite-pass census claimed the latter for
  candycane) -- the two analyses disagree and I have NOT seen the giant drawn. Needs a giant-on-screen
  snapshot or a driven spawn to settle, and to confirm whether the player actually sees that top band.
  (`$FE02` is the boss's own frame; `$C080` the giant fruit.)
- **Collectible type is a 4-BIT field -> 16 types 0-15 (CORRECTED 2026-09-08, N19; supersedes the
  earlier "0-7").** The collect code does `AND $0F` (`$8728`/`$87EA`/`$8788`); the value table
  `$8649` has 16 entries; the old "0-7" conflated the TYPE with the 0-3 ANIMATION phase (byte0 low
  3 bits, cycled at `$86D9`). Sprite = `$5D00 + (type+10)*32`, so type0=`$5E40` .. type15=`$6020`
  (and `$5D00`-`$5E20`, formula indices 0-9, are the POWER-UP ICONS via the `$8639` remap, NOT
  collectibles). `$5EA0` = type 3.
- **Re-decoded the tail as 16×16 mono (the collectible `$A2C2`/`$A2D5` format), 2026-09-08 — mixed
  result, correcting the blanket "NOT real":**
  - types 0-3 (`$5E40`-`$5EA0`) AND **`$6000`/`$6020` decode to COHERENT round BOULDERS (projectile frames -- see the correction below)**
    -> CORRECTED 2026-09-09: they are real sprites but NOT collectibles -- `$6000`/`$6020` are the type-1 enemy's BOULDER projectile frames (projectile kind 1, `$9BE3`); the collectible formula would alias types 14/15 onto them, so 14/15 have no art of their own.
  - **types 12/13 (`$5FC0`/`$5FE0`): RESOLVED 2026-09-09 -- BLANK, INVISIBLE by design.** In the
    pristine boot image both 32-byte tiles are ALL ZERO (the "noise" came from the post-boot image,
    where that region is scribbled at runtime); their INK entries in `$862D` are 0 (black), and they
    do carry values (`$8649`: 12 = +300, 13 = +700). Spawned by poke next to types 11/14/15 on
    `round1_48`, they draw NOTHING (screenshot: 11 magenta, 14 blue ball, 15 red ball, 12/13 empty).
    No spawner produces them in observed play -> unused slots. (`$6000`/`$6020` coherent = boulder
    projectile frames.)

### Later-round enemy banks, LIVE (2026-09-09)

48K-branch harness states at the first round of each type (`r6_48` t1, `r10_48` t2, `r20_48` t1+t3,
`r30_48` t3+t4, `r40_48` t1+t6, `r50_48` t5, `r60_48` t7; recipe in docs/NOTES M6 outcomes + the
no-death-warp note in SPEC) ran through `extract_sprites.py`: every enemy base is now a LIVE entry in
build/sprites.json. Facing mirrors (+$160) blitted live: t1 `$D1A0`, t2 `$CEE0`, t4 `$C520`, t5 `$CC20`,
t6 `$D660`; t3 `$C260` and t7 `$C680` never flip (single bank, N16). The earlier "+$160 inferred for
t4/t5/t7" is superseded: t7 has no mirror (it walks at ±4 px/frame without flipping), t6 does.

