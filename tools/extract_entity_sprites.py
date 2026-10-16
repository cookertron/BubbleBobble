"""The ENTITY SPRITE BANKS -> build/entity_sprites.json.

The engine has carried the enemy ROSTER (which bank each type and facing uses)
since M7.6 and the entity BLITTER since M7.3b, but never the PIXELS.  So the
render pass ran, the beam test ran, bbBlit16 was called with the right sprite
pointer and the right coordinates -- and read 64 bytes of zero.  A masked blit
of an all-zero sprite writes zeros, and the background is black, so it was a
perfect no-op: three enemies alive, correctly positioned, correctly falling,
and not one pixel on screen.

THE BANKS ARE TAPE DATA.  Verified both ways before extracting (TRAPS #43):
  - build/image_tape.bin is NON-ZERO across the whole span, so the tape really
    did load these pages -- unlike $5C00-$6100, where it is empty and the item
    bank turned out to be runtime-built;
  - and every bank is BYTE-IDENTICAL between the tape image and the live
    round-80 dump, so nothing writes them during a game.
The one exception is $5B80, type 0's facing-1 bank, which the game BUILDS at
runtime as a mirror copy; it is deliberately NOT in this asset, and 208 of its
256 bytes differ between tape and dump, which is how you can tell.

THE PLAYER BANK RUNS TO $DFFF, NOT $D8FF (M7.42 fix).  Until then END was
$D900, which cut the player's FIRST frame in half and dropped the other five:
a player sprite is 352 bytes ($160, four pre-shifted copies -- web/gfx.js), and
the player bank is SIX of them, $D7C0 + k*$160 for k = 0..5, ending exactly at
$E000.  MEASURED (scratch probe_p2.py, round1_2p48, 3 x 4,000 frames, interrupts
on, random cursor-key P1 / Kempston P2 script with walking, jumping, firing and
deaths): the blitter $A600..$A7FF, attributed by IY, read EXACTLY $C6C0-$C6FF,
$D300-$D33F and $D7C0-$DFFF for BOTH players -- the same eight (IY+0/1) pointers
for P1 at $FD80 and P2 at $FD8A: $C6C0 $D300 $D7C0 $D920 $DA80 $DBE0 $DD40 $DEA0.
P2 was invisible because it stands on $D920 (facing left) where the port held
zeros; P1 lost every frame but $D7C0's aligned copy the same way.  $D900-$DFFF
is non-zero in the tape image, byte-identical to it in all 54 usable captures
and to the round-80 dump, never written during the drive, and never read by a
non-player slot.  The span stops at $E000: $E000 onward is the relocation
source / platform shadow, runtime-owned, and NOT sprite data.

Sprites here are the 64-byte MASKED format the entity blitter $A600 wants:
16 rows x [maskL, dataL, maskR, dataR], screen = (screen AND mask) OR data.
That is NOT the 32-byte unmasked format the item blitter $A2D5 uses.

    python tools/extract_entity_sprites.py
"""
import sys, json, base64

AT, END = 0xC100, 0xE000          # every roster bank, plus the six player frames to $DFFF
OUT = 'build/entity_sprites.json'

# the roster, purely so the asset can name what it covers and assert it is inside
ROSTER = {0: (0xC100, 0x5B80), 1: (0xD1A0, 0xD040), 2: (0xCEE0, 0xCD80),
          3: (0xC260, 0xC260), 4: (0xC520, 0xC3C0), 5: (0xCC20, 0xCAC0),
          6: (0xD660, 0xD500), 7: (0xC680, 0xC680)}
PLAYER = 0xD7C0
PLAYER_STRIDE = 0x160             # four pre-shifted copies (web/gfx.js bbBlit16)
# MEASURED (IY+0/1) at the $A603 draw for BOTH $FD80 and $FD8A -- one shared bank
PLAYER_FRAMES = [PLAYER + k * PLAYER_STRIDE for k in range(6)]   # $D7C0..$DEA0
PLAYER_EXTRA = [0xC6C0, 0xD300]   # also drawn for both players; 64 bytes read each
PLAYER2 = PLAYER_FRAMES + PLAYER_EXTRA     # P2 ($FD8A) uses exactly P1's set
RUNTIME_MIRROR = 0x5B80           # built by the game, NOT extracted


def main():
    tap = open('build/image_tape.bin', 'rb').read()
    img = open('build/image.bin', 'rb').read()
    n = END - AT
    blk = tap[AT:AT + n]

    if not any(blk):
        raise SystemExit('$%04X..$%04X is all zero in the tape image -- these pages '
                         'were never loaded, so this is not tape data (TRAPS #43)' % (AT, END - 1))
    diff = [AT + i for i in range(n) if tap[AT + i] != img[AT + i]]

    covered, outside = [], []
    for t, (f1, f0) in ROSTER.items():
        for a in (f1, f0):
            if a == RUNTIME_MIRROR:
                continue
            (covered if AT <= a < END else outside).append((t, a))
    if outside:
        raise SystemExit('roster banks outside the span: %s'
                         % ' '.join('type %d $%04X' % x for x in outside))
    if not (AT <= PLAYER < END):
        raise SystemExit('the player bank $%04X is outside the span' % PLAYER)
    for a in PLAYER_FRAMES:
        if not (AT <= a and a + PLAYER_STRIDE <= END):
            raise SystemExit('player frame $%04X..$%04X is outside the span'
                             % (a, a + PLAYER_STRIDE - 1))
    for a in PLAYER2:
        if not (AT <= a and a + 64 <= END):
            raise SystemExit('P2 sprite $%04X is outside the span' % a)
    if PLAYER_FRAMES[-1] + PLAYER_STRIDE != END:
        raise SystemExit('the span must end where the last player frame does ($%04X), '
                         'not at $%04X -- $E000 on is the runtime-owned shadow'
                         % (PLAYER_FRAMES[-1] + PLAYER_STRIDE, END))
    hi = tap[0xD900:END]
    if not all(any(hi[i:i + PLAYER_STRIDE]) for i in range(0, len(hi), PLAYER_STRIDE)):
        raise SystemExit('part of $D900..$%04X is all zero in the tape image' % (END - 1))
    if tap[0xD900:END] != img[0xD900:END]:
        raise SystemExit('$D900..$%04X differs between tape and dump -- not static tape data' % (END - 1))

    d = {'note': __doc__.strip(), 'at': AT, 'n': n, 'stride': 64,
         'rows': 16, 'masked': True,
         'roster': {str(k): list(v) for k, v in ROSTER.items()},
         'player_at': PLAYER, 'player_stride': PLAYER_STRIDE,
         'player_frames': PLAYER_FRAMES, 'player2_at': PLAYER2, 'end': END,
         'runtime_mirror': RUNTIME_MIRROR,
         'tape_vs_dump_diff': len(diff),
         'b64': base64.b64encode(blk).decode()}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: $%04X..$%04X, %d bytes' % (OUT, AT, END - 1, n))
    print('  tape image non-zero here: %d/%d bytes -- these pages DID load' %
          (sum(1 for b in blk if b), n))
    print('  vs the round-80 dump: %d bytes differ%s' %
          (len(diff), '' if not diff else ' -- ' + ' '.join('$%04X' % a for a in diff[:6])))
    print('  covers %d roster banks plus the player at $%04X' % (len(set(a for _, a in covered)), PLAYER))
    print('  player frames (both players, stride $%X): %s; also %s' % (
        PLAYER_STRIDE, ' '.join('$%04X' % a for a in PLAYER_FRAMES),
        ' '.join('$%04X' % a for a in PLAYER_EXTRA)))
    print('  NOT covered (runtime-built by the game): $%04X, type 0 facing 1' % RUNTIME_MIRROR)


if __name__ == '__main__':
    main()
