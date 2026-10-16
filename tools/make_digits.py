"""The SUBSTITUTE DIGIT FONT -> build/digits.json.  A DECLARED DEPARTURE.

The game draws its score digits through $8042, which computes
`$3C00 + (digit + $30) * 8` -- the SPECTRUM ROM CHARACTER SET.  This project
ships no ROM transcription (README), so the port cannot use those glyphs.

These ten 8x8 digits are DRAWN FOR THIS PORT, not extracted from anything.
They are the banner font's digits (make_banner.py) -- one face for the whole
HUD, as the machine has -- a different design from the ROM's, which the tool
asserts.  The tool ASSERTS that every glyph differs from the ROM's, so
an accidental reproduction cannot slip through unnoticed -- and it reports how
many of the 80 bytes differ, as evidence rather than as a promise.

The ROM is read from the analysis harness for that comparison ONLY.  No ROM
byte is written to build/digits.json or to any other artifact.

CONSEQUENCE, to be carried in the README and in M8: the HUD will not be
pixel-identical to the original, so a frame-level differential must EXEMPT the
score cells.  Everything else about the renderer -- which cells it addresses,
the order it walks them, the self-modified leading-zero suppressor at $81BB --
is faithful and gated (M7.7-I4).

    python tools/make_digits.py
"""
import sys, json, base64
sys.path.insert(0, 'tools')

# Drawn by hand.  Bit 7 is the leftmost pixel; row 8 is blank so digits sit on
# a baseline with the descender space the renderer's 8-row copy expects.
#  ONE FACE WITH THE HUD'S TEXT (2026-10-08).  These were a separate design -- a two-pixel stroke, seven rows from
#  the TOP row -- while the HUD's strings ($802E: "00" under 1UP / HIGH SCORE / 2UP) draw their digits from
#  make_banner.py's font, one-pixel, in the ROM's rows 1..6.  So an unchanged score cell and a redrawn one were
#  two faces side by side, and that font's zero was a square box a player read as an empty cell.  The machine
#  draws both from ONE font, the ROM's, in ITS layout (row 0 and row 7 blank -- $7FAF's seven rows from row 1
#  rely on it).  So the ten digits are now the banner font's, read from make_banner.py, not copied.
from make_banner import GLYPHS as _BANNER
DIGITS = [list(_BANNER[str(d)]) for d in range(10)]
OUT = 'build/digits.json'


def rom_digits():
    """The ROM's own ten glyphs, for COMPARISON ONLY -- never stored."""
    from harness import Harness
    h = Harness()
    m = h.memobj.m
    return [[m[0x3C00 + (d + 0x30) * 8 + r] for r in range(8)] for d in range(10)]


def show(g):
    return '\n'.join(''.join('#' if (b >> (7 - i)) & 1 else '.' for i in range(8)) for b in g)


MIN_DIFF = 3                      # of eight bytes, for any glyph carrying ink


def main():
    rom = rom_digits()
    #  *** THE ASSERT IS A MINIMUM, NOT A WHOLE-CELL INEQUALITY. ***  It used to be
    #  `rom[d] == DIGITS[d]`, which a digit differing from the ROM's in ONE byte of
    #  eight satisfies -- the ROM's letter with a haircut.  That is TRAPS #155,
    #  which make_banner.py was fixed for and this tool was not.  The per-glyph
    #  count is reported as EVIDENCE rather than as a promise.
    per = {}
    for d in range(10):
        per[d] = sum(1 for r in range(8) if rom[d][r] != DIGITS[d][r])
    thin = sorted(d for d in range(10) if per[d] < MIN_DIFF)
    if thin:
        raise SystemExit('digits %s differ from the ROM in fewer than %d bytes of '
                         'eight (%s) -- that is the ROM glyph with a haircut, not a '
                         'substitute face (TRAPS #155)'
                         % (thin, MIN_DIFF, {d: per[d] for d in thin}))
    #  ...and no two digits may be the SAME cell, which the ROM comparison cannot
    #  see: a font whose 6 and 8 are one glyph passes every difference test and is
    #  unreadable.  (make_banner.py gained the same assert in M7.31.)
    byrow = {}
    for d in range(10):
        byrow.setdefault(tuple(DIGITS[d]), []).append(d)
    dup = sorted(v for v in byrow.values() if len(v) > 1)
    assert not dup, 'two digits are the same cell: %r' % dup

    diff = sum(per.values())
    flat = bytes(b for g in DIGITS for b in g)

    d = {'note': __doc__.strip(), 'substitute': True, 'rows': 8, 'width': 8,
         'count': 10, 'departure': 'the original draws these from the 48K ROM charset',
         'bytes_differing_from_rom': diff,
         'min_diff': MIN_DIFF,
         'per_glyph_differing': [per[i] for i in range(10)],
         'closest': {'digit': min(per, key=lambda k: per[k]),
                     'bytes': min(per.values())},
         'b64': base64.b64encode(flat).decode()}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: ten 8x8 digits, drawn for this port' % OUT)
    print('  every glyph differs from the ROM by at least %d of 8: %d of 80 bytes '
          'total, closest digit %d at %d'
          % (MIN_DIFF, diff, d['closest']['digit'], d['closest']['bytes']))
    print('  per glyph: %s' % ' '.join('%d:%d' % (i, per[i]) for i in range(10)))
    print()
    for d0 in (0, 1, 8):
        print('  digit %d      port            ROM' % d0)
        for a, b in zip(show(DIGITS[d0]).split('\n'), show(rom[d0]).split('\n')):
            print('              %s      %s' % (a, b))


if __name__ == '__main__':
    main()
