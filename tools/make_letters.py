"""The SUBSTITUTE EXTEND-LETTER FONT -> build/letters.json.  A DECLARED DEPARTURE.

The game draws its collected-EXTEND row through $957E, whose glyph table at
$95D5 points at SPECTRUM ROM CHARACTER-SET CELLS: $3E28, $3EC0, $3EA0, $3E28,
$3E70, $3E20 -- 'e', 'x', 't', 'e', 'n', 'd'.  H6 found the SAME SIX ADDRESSES
in $C068's bubble-glyph table, so two unrelated tables name them and one
substitute font serves both.  This project ships no ROM transcription (README),
so the port cannot use those glyphs.

These six 8x8 letters are DRAWN FOR THIS PORT, not extracted from anything, and
deliberately a different face from the ROM's: a squarer, heavier design on a
different bearing.  The tool ASSERTS that every glyph differs from the ROM's, so
an accidental reproduction cannot slip through, and reports how many of the 48
bytes differ as evidence rather than as a promise.

The ROM is read from the analysis harness for that comparison ONLY.  No ROM byte
is written to build/letters.json or to any other artifact.

CONSEQUENCE, carried in the README and in M8: the EXTEND row will not be
pixel-identical to the original, so a frame-level differential must EXEMPT those
six cells.  Everything else about the renderer is faithful and gated (M7.7-H9):
which cells it addresses, that the second player's pass is reached BY FALLING
THROUGH, the self-modified column offset at $95AE, and the 8 display + 8 shadow
+ 1 attribute it writes PER SET BIT.

    python tools/make_letters.py
"""
import sys, json, base64
sys.path.insert(0, 'tools')

ROM_AT = (0x3E28, 0x3EC0, 0x3EA0, 0x3E28, 0x3E70, 0x3E20)   # e x t e n d

# Drawn by hand.  Bit 7 is the leftmost pixel.
LETTERS = [
    [0x00, 0x00, 0x7C, 0x6C, 0x7C, 0x60, 0x7C, 0x00],   # 0  e -- squared bowl
    [0x00, 0x00, 0x6C, 0x38, 0x10, 0x38, 0x6C, 0x00],   # 1  x -- full-height cross
    [0x00, 0x30, 0x7C, 0x30, 0x30, 0x30, 0x1C, 0x00],   # 2  t -- flat crossbar
    [0x00, 0x00, 0x7C, 0x6C, 0x7C, 0x60, 0x7C, 0x00],   # 3  e -- same as 0
    [0x00, 0x00, 0x78, 0x6C, 0x6C, 0x6C, 0x6C, 0x00],   # 4  n -- square shoulder
    [0x00, 0x0C, 0x3C, 0x6C, 0x6C, 0x6C, 0x3C, 0x00],   # 5  d -- flat-sided bowl
]
OUT = 'build/letters.json'


def main():
    rom = open(_rom_path(), 'rb').read()
    diff, total = 0, 0
    for k, a in enumerate(ROM_AT):
        theirs = rom[a:a + 8]
        mine = LETTERS[k]
        if bytes(mine) == theirs:
            raise SystemExit('letter %d REPRODUCES the ROM glyph at $%04X' % (k, a))
        for i in range(8):
            total += 1
            diff += 1 if mine[i] != theirs[i] else 0
    json.dump({
        'note': ('SUBSTITUTE EXTEND letters, DRAWN FOR THIS PORT -- a DECLARED '
                 'DEPARTURE.  The original reads the Spectrum ROM character set at '
                 '$3E28/$3EC0/$3EA0/$3E28/$3E70/$3E20 through $95D5, and H6 found '
                 'the same six addresses in $C068.  No ROM byte appears here.'),
        'rom_at': ['0x%04X' % a for a in ROM_AT],
        'letters': LETTERS,
        'bytes_differing_from_rom': diff, 'bytes_total': total,
        'b64': base64.b64encode(bytes(b for g in LETTERS for b in g)).decode(),
    }, open(OUT, 'w'), indent=1)
    print('wrote %s: six 8x8 letters, %d of %d bytes differ from the ROM\'s'
          % (OUT, diff, total))


def _rom_path():
    import skoolkit, os
    return os.path.join(os.path.dirname(skoolkit.__file__), 'resources', '48.rom')


if __name__ == '__main__':
    main()
