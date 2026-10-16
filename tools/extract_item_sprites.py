"""The ITEM SPRITE BANK at $5D00 -> build/item_sprites.json.

The draw computes its sprite pointer as `$5D00 + index * 32` with the index
coming from one of two places ($8779/$87A5):

    fruit pass     index = type + 10          type 0..15  ->  10..25
    power-up pass  index = $8639[type]        type 0..15  ->   0..9

So the reachable addresses run from $5D00 (power-up index 0) to $6020+31
(fruit type 15, index 25) -- 832 bytes.  The top of that is NOT sprite data:
the drop generator only makes fruit types 0..7, so the bank proper stops well
short and types 12..15 blit whatever follows.  This tool carries the WHOLE
range verbatim, garbage included, because a faithful port has to draw the same
garbage the machine draws.

*** THIS BANK IS RUNTIME-BUILT, NOT TAPE DATA. ***  MEASURED three ways:
  - build/image_tape.bin -- the R3 rebuild from the actual tape blocks -- is
    ALL ZEROS from $5C00 to $6100.  Those pages are simply not on the tape
    (they are the Spectrum's system-variable area and the game's working RAM),
    so the tape image is NOT authoritative here.  It is authoritative only
    where the tape actually loaded, which is why this tool asserts the range is
    non-zero in a live state and REFUSES to take it from the tape image.
    (TRAPS #43, amended.)
  - the bank is byte-identical in 54 of the 57 saved states -- everything from
    `afterctrl` onward.  Only `boot`, `title` and `iball` differ, and all three
    are FRONT-END states (round counter 0); in `boot` and `title` this span
    still holds the loader's own BASIC text (" v.9/87" sits at $5CE0) and in
    `iball` it holds credits text.  So the span is working RAM that the game
    takes over, and it is built during the front end, after the title screen
    and before play.
  - zeroing $5D00..$603F in a live round-1 state and running 200 frames
    produces ZERO writes back into the range, so nothing rebuilds it in play.

OPEN ITEM: find the builder.  The project's precedent is to BUILD such a bank
rather than ship it -- $D380, the flashing-bubble sprite, is runtime-built by
$BF5B and is deliberately not an asset.  The builder here runs in the front end
(M7.8), so until that is reached the bank is carried as a declared asset and
the draw is gated against the same bytes on both sides.  When the builder is
found, this asset should be DELETED, not kept as a cross-check.

Sprites here are UNMASKED and character-aligned: 16 rows x 2 bytes, written by
$A2D5 as two bands of 8.  NOT the 64-byte masked format the entity blitter uses.

    python tools/extract_item_sprites.py [state]
"""
import sys, json, base64, glob, os, hashlib
sys.path.insert(0, 'tools')
from harness import Harness
import portconfig as pc

# FOUR BYTES LOWER THAN THE BANK ITSELF.  $5CFC..$5CFF sit between the $5CE0
# sparkle table and $5D00, and the reading pass called them junk -- but $C002's
# walk READS THEM: when its DJNZ counter wraps (every serviced particle with
# X < 8 costs a count, TRAPS-worthy on its own) the walk leaves the table, and
# $5CFE = $3F is the first thing it finds with a non-zero phase, so the machine
# services a particle THERE.  They are runtime-built exactly like the bank --
# the tape image is zero across the whole span -- and the clears do not reach
# them ($989C fills 24 bytes and $BF53 28, i.e. $5CE0..$5CFB).  Carried here so
# the port reproduces the runaway; they go when the builder is found.
AT, N = 0x5CFC, 836
OUT = 'build/item_sprites.json'
REMAP_AT, REMAP_N = 0x8639, 16


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else 'round1_48'
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    blk = bytes(m[AT:AT + N])
    if not any(blk):
        raise SystemExit('%s: $%04X..$%04X is all zeros -- wrong source' % (state, AT, AT + N - 1))

    tap = open('build/image_tape.bin', 'rb').read()
    if any(tap[AT:AT + N]):
        raise SystemExit('the tape image is NON-ZERO here -- re-read the docstring, '
                         'this bank may be tape data after all')

    # how many saved states agree, so the "constant once built" claim carries a number
    ref = hashlib.md5(blk).hexdigest()
    agree, differ = [], []
    for f in sorted(glob.glob('build/*.pkl')):
        try:
            g = Harness(); g.load_state_file(f)
            same = hashlib.md5(bytes(g.memobj.m[AT:AT + N])).hexdigest() == ref
            (agree if same else differ).append(os.path.basename(f)[:-4])
        except Exception:
            pass

    remap = list(m[REMAP_AT:REMAP_AT + REMAP_N])
    # the INDEX FORMULA is still based at $5D00 -- the four bytes below it are
    # carried in the same block but are not part of the bank's indexing.
    BANK = 0x5D00
    fruit = {t: BANK + (((t + 10) * 8 & 0xFF) * 4) for t in range(16)}
    power = {t: BANK + ((remap[t] * 8 & 0xFF) * 4) for t in range(16)}

    d = {'note': __doc__.strip(), 'at': AT, 'n': N, 'stride': 32,
         'bank_at': 0x5D00, 'pre': list(m[AT:0x5D00]),
         'rows': 16, 'cols': 2, 'masked': False, 'runtime_built': True,
         'source_state': state, 'md5': ref,
         'states_agreeing': agree, 'states_differing': differ,
         'remap_at': REMAP_AT, 'remap': remap,
         'fruit_addr': {str(k): v for k, v in fruit.items()},
         'power_addr': {str(k): v for k, v in power.items()},
         'b64': base64.b64encode(blk).decode()}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: $%04X..$%04X, %d bytes, from the LIVE state %s'
          % (OUT, AT, AT + N - 1, N, state))
    print('  RUNTIME-BUILT: the tape image is all zeros here ($5C00-$6100 never loaded)')
    print('  %d saved states agree byte-for-byte; %d differ (%s)'
          % (len(agree), len(differ), ', '.join(differ) or 'none'))
    print('  fruit    type 0 -> $%04X ... type 15 -> $%04X' % (fruit[0], fruit[15]))
    print('  power-up type 0 -> $%04X ... type 15 -> $%04X' % (power[0], power[15]))


if __name__ == '__main__':
    main()
