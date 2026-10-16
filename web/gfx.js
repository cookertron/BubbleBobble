/* =======================================================================
   web/gfx.js -- the display-file blitters (M7.2), transliterated from the
   measured 16x16 masked stack-blitter ($A600/$A651).

   The composite rule is `screen = (screen AND mask) OR data` (MEASURED,
   blitforensics).  A sprite is 64 bytes = 16 rows of [maskL, dataL, maskR,
   dataR] -- two screen bytes wide (16 px).  Positions are EVEN-aligned
   (X & $FE) with a sub-byte shift s = X & 6 (measured: the blitter's
   `AND 6`; odd X snaps down), so a shifted sprite spans three screen bytes.
   Sprites live in the world image at their real addresses; the blitter reads
   them from `ram`.
   ======================================================================= */

/* the ULA byte address of pixel (x,y) in world-image coordinates ($4000) */
function bbPixelAddr(x, y){
  return 0x4000 + ((y & 0xC0) << 5) + ((y & 0x38) << 2) + ((y & 7) << 8) + (x >> 3);
}

/* blit one 16x16 masked sprite at pixel (X,Y) -- the DRAW half of the entity
   master $A447 ($A614 aligned / $A6F3 shifted).  The sprite is 352 bytes = FOUR
   PRE-SHIFTED copies (MEASURED at $A6F3: the blitter picks the copy by X's
   even sub-position, it does NOT shift at draw time -- sprite stride is $160):
     s = X & 6 == 0 -> block +0,   4 bytes/row [mL,dL,mR,dR]     (2 screen bytes)
     s == 2         -> block +64,  6 bytes/row [m,d,m,d,m,d]      (3 screen bytes)
     s == 4         -> block +160, 6 bytes/row
     s == 6         -> block +256, 6 bytes/row
   The composite is `screen = (screen AND mask) OR data` per byte, the exact
   $A651 POP-blit (E=mask, D=data).  X is snapped even; rows run in order and
   columns left to right.

   TWO EDGE FAULTS CORRECTED in M7.3b, both shipped since M7.2 because the
   fixture put its four sprites in the middle of the screen:
     * the row address comes from the game's $FD00 TABLE ($A630), not the ULA
       formula, so character rows 0-1 -- the sentinel $01FF -- address ROM and
       are DROPPED instead of scribbling on the HUD;
     * the column walk is `ADD A,L` / `INC L`, EIGHT-BIT ($A64D/$A656), so a
       row's columns WRAP inside the 256-byte page.  The old `col + i < 32`
       clip silently dropped the second column at X = 248, where the machine
       writes $..FF then $..00. */
function bbBlit16(ram, sprAddr, X, Y){
  const x = X & 0xFE, s = x & 6;
  const nb = s ? 3 : 2;                                 // screen bytes per row
  let o = sprAddr + (s ? 2 * (24 * s - 16) : 0);        // pre-shifted block base
  for (let r = 0; r < 16; r++){
    const base = bbRowBase(ram, (Y + r) & 0xFF, x);
    for (let i = 0; i < nb; i++){
      const a = bbColAddr(base, i);
      const mask = ram[o + 2 * i], data = ram[o + 2 * i + 1];
      if (a >= 0x4000) ram[a] = (ram[a] & mask) | data;
    }
    o += nb * 2;
  }
}

/* the ERASE half of $A447, at the entity's CACHED position (+3 = X, +2 = Y).
   Two paths, and which one runs is decided by the cached X's sub-position:
     X & 6 == 0  ($A483, ALIGNED)  two columns, a PLAIN COPY from the shadow
     otherwise   ($A53C, SHIFTED)  three columns, masked from $AA4F + (X & 6),
                                   the same composite $BF16 and $B9E7 use
   Sixteen rows either way, in three blocks (8-(Y&7), 8, Y&7) that each restart
   their zig-zag FORWARD.  A cached Y of $C0 or more erases nothing ($A464).
   NOTE this is NOT bbEraseSprite: that one is $BF16, which patches $A480 so the
   SHIFTED path always runs.  Same routine, two different entry conditions.
   MEASURED against build/entdraw_fixture.json (17 cases + a 288-case sweep). */
function bbEraseEntity(ram, X, Y){
  if (Y >= 0xC0) return;                                // $A464 CP $C0 / JP nc
  const shifted = (X & 6) !== 0;                        // $A47E AND 6 / $A480 JP nz
  const mask = ram[0xAA4F + (X & 6)], nmask = mask ^ 0xFF;
  const ncol = shifted ? 3 : 2;
  const n1 = 8 - (Y & 7);
  for (let r = 0; r < 16; r++){
    const i = r < n1 ? r : (r < n1 + 8 ? r - n1 : r - n1 - 8);
    const base = bbRowBase(ram, (Y + r) & 0xFF, X);
    for (let k = 0; k < ncol; k++){
      const c = (i & 1) === 0 ? k : ncol - 1 - k;
      const a = bbColAddr(base, c);
      const s = ram[(a + 0xA000) & 0xFFFF];
      // the ALIGNED path only runs when X & 6 == 0, so its mask is always
      // $AA4F[0] = $00 and `(disp & M) | (shad & ~M)` reduces to `shad`.  A
      // mutation that masks here instead of copying is therefore EQUIVALENT,
      // not a defect, and survives the battery by arithmetic.
      const v = !shifted ? s                            // $A4A5: a plain copy
              : c === 0 ? ((ram[a] & mask) | (s & nmask))
              : c === 1 ? s
              :           ((ram[a] & nmask) | (s & mask));
      if (a >= 0x4000) ram[a] = v;
    }
  }
}

/* ---------------------------------------------------------------------
   THE BUBBLE BLITTER ($B9E7).  A different routine from $A651 above, with a
   different composite, and the only one in the game that reads the CLEAN
   PLATFORM LAYER: it takes the background from the shadow buffer (display +
   $A000) rather than from the display, so a draw is a function of the shadow
   AND the display.  MEASURED against build/bubdraw_fixture.json -- 21 cases,
   every write in order -- and against a 1536-case sweep of every X sub-shift
   by every Y residue by every bubble kind (tools/bubdraw.py).

   Per pixel row, three columns from X >> 3, with M = ram[$BFF8 + (X & 7)]:

       col 0   disp = (disp & M)  | (shad & ~M) | spr      $BA97-$BAA2
       col 1   disp =  shad                     | spr      $BAA5-$BAA9
       col 2   disp = (disp & ~M) | (shad &  M) | spr      $BAAB-$BAB6

   The edge columns keep the display outside the bubble's 24-pixel window and
   take the clean background inside it.  Sixteen rows from Y; the sprite's 48
   bytes run in BOUSTROPHEDON order (row 0 left to right, row 1 right to left)
   because the routine walks L forward through one row and back through the
   next rather than reloading it.

   TWO ROWS CARRY NO SPRITE.  The prologue at $BA78 is the loop body with its
   three OR instructions removed, so row 0 is a pure background restore (its
   sprite bytes are POPped and discarded), and the tail at $BB94 re-writes the
   last row background-only.  Hence 51 writes to 48 addresses -- the last row
   twice.  Both are faithful: they are how the routine erases the one-pixel
   trail a rising bubble leaves.

   The row address comes from the game's own $FD00 table, not from a formula:
   its first two entries are the sentinel $01FF that keeps the HUD rows out of
   reach, and (y & 7) is added to the HIGH byte ($BA67).  --------------- */
/* The column offset ($BA61 ADD A,(HL)) and the walk along a row ($BAA3 INC L,
   $BAC3 DEC L) are EIGHT-BIT, so a row's three columns WRAP INSIDE the 256-byte
   page: at the right edge of a row whose low byte is $FE the third column lands
   at $..00, not on the next page.  MEASURED -- the erase oracle's right-edge
   case is what caught a 16-bit version of this, in bbColAddr.
   The 8-bit add HERE is TRANSCRIBED, NOT EXERCISED: the row table's low bytes
   top out at $E0 and a byte X gives a column of at most 31, so $E0 + 31 = $FF
   and this add can never carry.  A mutation to 16-bit arithmetic survives the
   whole battery, and that is correct rather than a gap. */
function bbRowBase(ram, y, x){
  const sa = bbBubbleAddr(ram, y);
  return (sa & 0xFF00) | ((sa + (x >> 3)) & 0xFF);
}

function bbColAddr(base, c){ return (base & 0xFF00) | ((base + c) & 0xFF); }

function bbBubbleAddr(ram, y){
  const e = 0xFD00 + 2 * ((y >> 3) & 0x1F);
  return (ram[e] | ((ram[e + 1] + (y & 7)) << 8)) & 0xFFFF;
}

function bbBlitBubble(ram, sprAddr, X, Y){
  const mask = ram[0xBFF8 + (X & 7)], nmask = mask ^ 0xFF;
  const spr = sprAddr + 48 * (X & 7);                  // $B9F1-$BA1F: 8 pre-shifts of 48
  let a = 0;
  for (let r = 0; r < 16; r++){
    const base = bbRowBase(ram, (Y + r) & 0xFF, X);
    const rev = (r & 1) !== 0;                         // odd rows run right to left
    for (let i = 0; i < 3; i++){
      const c = rev ? 2 - i : i;
      a = bbColAddr(base, c);
      const s = ram[(a + 0xA000) & 0xFFFF];
      const p = r === 0 ? 0 : ram[spr + 3 * r + i];     // $BA78: row 0 has no OR
      const v = c === 0 ? ((ram[a] & mask) | (s & nmask) | p)
              : c === 1 ? (s | p)
              :           ((ram[a] & nmask) | (s & mask) | p);
      if (a >= 0x4000) ram[a] = v;                      // $FD00 rows 0-1 point at ROM
    }
  }
  const base = bbRowBase(ram, (Y + 15) & 0xFF, X);
  for (let c = 0; c < 3; c++){                          // $BB94: the trailing restore
    a = bbColAddr(base, c);
    const s = ram[(a + 0xA000) & 0xFFFF];
    const v = c === 0 ? ((ram[a] & mask) | (s & nmask))
            : c === 1 ? s
            :           ((ram[a] & nmask) | (s & mask));
    if (a >= 0x4000) ram[a] = v;
  }
}

/* ---------------------------------------------------------------------
   THE ERASE ($BF16).  Not a bubble routine at all: it calls the ENTITY draw
   master $A447 with two self-modifying patches -- $A5D9, the junction where
   the erase half ends and the draw half begins, set to RET, and $A480's
   `JP nz` made unconditional -- plus the flags forced to $C0.  The effect is
   "run only the ERASE half", repainting the 3x16 box at the CACHED position
   (IY+2 = Y, IY+3 = X) from the shadow with the same composite the bubble
   blitter uses for its two sprite-less rows:

       col 0   disp = (disp & M)  | (shad & ~M)
       col 1   disp =  shad
       col 2   disp = (disp & ~M) | (shad &  M)

   TWO differences from $B9E7, both MEASURED (17 oracle cases + a 256-case
   sweep, tools/bubdraw.py erase --sweep).  The mask comes from the ENTITY
   table $AA4F indexed by X & 6, NOT $BFF8 by X & 7 -- the same eight bytes,
   but the erase snaps to the entity blitter's even sub-position, so for an odd
   X it uses a mask one step coarser than the draw did.  And the boustrophedon
   restarts FORWARD at each of the three block boundaries (8-(Y&7), 8, then
   Y&7 rows), because each block re-derives its address from the row table,
   where $B9E7 runs one unbroken zig-zag across all sixteen.

   A cached Y of $C0 or more writes nothing at all ($A464 CP $C0 / JP nc into
   the patched RET).  HERE that guard is TRANSCRIBED, NOT EXERCISED: entries 24-31
   of the $FD00 row table hold $0000-$00E0, so every row a cached Y of $C0..$FF
   can reach -- the wrap back to rows $00-$07 included -- addresses ROM, where the
   write is dropped anyway, and removing it changes no display byte.  The SAME
   gate stands first in the caller, bubbleErase() (M7.49), where it also skips
   $A447's $A430 add -- and there $A431 witnesses it: N1's falling corpse enters
   $BF16 at cached Y $C0..$C6 and the machine adds nothing (popkill PK9). */
function bbEraseSprite(ram, X, Y){
  if (Y >= 0xC0) return;                               // $A464 CP $C0 / JP nc
  const mask = ram[0xAA4F + (X & 6)], nmask = mask ^ 0xFF;
  const n1 = 8 - (Y & 7);                              // block 1, then 8, then Y&7
  for (let r = 0; r < 16; r++){
    const i = r < n1 ? r : (r < n1 + 8 ? r - n1 : r - n1 - 8);
    const base = bbRowBase(ram, (Y + r) & 0xFF, X);
    for (let k = 0; k < 3; k++){
      const c = (i & 1) === 0 ? k : 2 - k;
      const a = bbColAddr(base, c);
      const s = ram[(a + 0xA000) & 0xFFFF];
      const v = c === 0 ? ((ram[a] & mask) | (s & nmask))
              : c === 1 ? s
              :           ((ram[a] & nmask) | (s & mask));
      if (a >= 0x4000) ram[a] = v;                     // $FD00 rows 0-1 point at ROM
    }
  }
}

/* $BF5B, the ELEMENT bubble sprite BUILD.  $D380 is NOT tape data: it is a
   384-byte buffer rebuilt whenever the element changes (one caller, $94B7).
   Copy the EMPTY table, OR the element's 8x8 glyph into rows 4-11 of shift 0,
   then generate shifts 1-7 by shifting each 24-bit row right one bit.  That is
   why $D380 is an EXACT pre-shift table while $C780/$C900, which are hand-drawn
   tape data, are not -- the measurement that identifies it.  Element id is
   ram[$7E0E]: 2 water, 3 lightning, 4 fire; the glyph pointer table is $C068.
   MEASURED: reproduces the live $D380 of the elfire/elwater/ellight states
   byte for byte, 384/384 each. */
function bbBuildElementBubble(ram, elem){
  const D = 0xD380;
  for (let i = 0; i < 384; i++) ram[D + i] = ram[0xC780 + i];      // $BF66 LDIR
  const t = 0xC068 + 2 * (elem - 2);                               // $BF71-$BF7D
  let g = ram[t] | (ram[t + 1] << 8), ix = D + 12;                 // $BF82 -> row 4
  for (let n = 0; n < 4; n++){                                     // $BF89 LD B,4
    let v = ram[g++];
    ram[ix]     |= v >> 4;  ram[ix + 1] |= (v << 4) & 0xF0;        // even row: cols 0,1
    v = ram[g++];
    ram[ix + 5] |= v >> 4;  ram[ix + 4] |= (v << 4) & 0xF0;        // odd row, reversed
    ix += 6;                                                       // $BFB1 ADD IX,6
  }
  for (let s = 0; s < 7; s++){                                     // $BFB9 LD A,7
    const src = D + 48 * s, dst = D + 48 * (s + 1);
    for (let i = 0; i < 48; i++) ram[dst + i] = ram[src + i];      // $BFC4 LDIR
    let i = dst;
    for (let n = 0; n < 8; n++){                                   // $BFCA LD B,8
      let c = 0;
      for (const k of [0, 1, 2]){                                  // even row: +0,+1,+2
        const nc = ram[i + k] & 1; ram[i + k] = (ram[i + k] >> 1) | (c << 7); c = nc;
      }
      i += 5;                                                      // $BFD4 ADD HL,3
      c = 0;
      for (const k of [0, -1, -2]){                                // odd row: +5,+4,+3
        const nc = ram[i + k] & 1; ram[i + k] = (ram[i + k] >> 1) | (c << 7); c = nc;
      }
      i += 1;                                                      // $BFE2 INC HL
    }
  }
}

globalThis.bbPixelAddr = bbPixelAddr;
globalThis.bbBlit16 = bbBlit16;
globalThis.bbBubbleAddr = bbBubbleAddr;
globalThis.bbRowBase = bbRowBase;
globalThis.bbColAddr = bbColAddr;
globalThis.bbBlitBubble = bbBlitBubble;
globalThis.bbEraseSprite = bbEraseSprite;
globalThis.bbEraseEntity = bbEraseEntity;
globalThis.bbBuildElementBubble = bbBuildElementBubble;
