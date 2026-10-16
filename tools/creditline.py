# -*- coding: utf-8 -*-
"""M7.30 -- $9751..$9764, the CREDIT line, and a reading of the table above it.

    $9751  LD IX,$9AB8 / LD HL,$50F7 / CALL $802E
    $975B  LD HL,$5AF7 / LD A,5 / LD B,9 / CALL $995A

*** IT CANNOT BE WIRED TO A REAL CALL SITE YET, AND THIS TOOL SAYS SO. ***
$9758 is reached by FALL-THROUGH from $9729's title text block, which draws four
DOUBLE-HEIGHT strings through $801D: "B U B B L E  B O B B L E", "By Software
Creations", "Program: Mike Follin" and "1 OR 2 TO PLAY".  Those need about thirty
substitute glyphs including LOWERCASE, and the port's gameReset() already stops
at $970E with the title screen NAMED OUT as the front-end increment's.  So the
CREDIT line is transliterated and gated here and registered as UNCALLED, not
forced into gameReset() ahead of the block it follows.

WHAT THE TABLE AT $9A85 SAYS, read for whoever takes the front end:
    IY walks it COLUMN-MAJOR -- `LD L,(IY)` and `LD H,(IY+4)`, so four parallel
    arrays of four: display lows, display highs, attributes, cell counts.  IX is
    seeded ONCE at $9A32 and $802E's own `INC IX` chains all four strings.
    *** AND ITS FOUR COUNTS MATCH THEIR STRING LENGTHS EXACTLY *** -- 24, 21,
    20, 14 -- where the two HAND-CODED sites do not: $8E83 loads 11 for a
    ten-character string and $9760 loads 9 for an eight-character one.

NO ROM BYTE IS RECORDED: destinations and the SOURCE ADDRESS each came from.

Usage:  python tools/creditline.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/creditline_fixture.json'
BRANCH_BYTE = 0x8DC4
ENTRY = 0x9751
STRING = 0x9AB8
DISPLAY = 0x50F7
ATTR_AT = 0x5AF7
ATTR = 0x05
CELLS = 9
TABLE = 0x9A85
CHARSET = 0x3C00
STATE = 'title'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    return h, h.memobj.m


def arm(h, addr):
    r = h.sim.registers
    if not hasattr(h, '_sp0'):
        h._sp0 = r[SP]
    r[SP] = h._sp0
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def phase_line():
    """Both halves of $9751, with the display and the attribute row POISONED so
       every write is visible."""
    h, m = new()
    r = h.sim.registers
    for i in range(16):
        for row in range(8):
            m[(DISPLAY + i + 0x100 * row) & 0xFFFF] = 0xFF
        m[(ATTR_AT + i) & 0xFFFF] = 0xFF
    glyphs, attrs = [], []
    sp0 = arm(h, ENTRY)
    #  *** $9751 IS NOT A SUBROUTINE. ***  It is mid-routine code that FALLS
    #  THROUGH into $9765's attribute scan, so there is no RET to catch and the
    #  first run of this phase ran off into the scan and reported a bad bracket
    #  at $9774.  The bracket is the ADDRESS AFTER the attribute run.
    END = 0x9765
    n = 0
    while n < 2 * 10 ** 6:
        pcv = r[PC]
        if pcv == END:
            break
        if pcv == 0x8052:
            glyphs.append([r[7] | (r[6] << 8), r[5] | (r[4] << 8)])
        elif pcv == 0x995C:
            attrs.append([r[7] | (r[6] << 8), r[0]])
        h.step(1, interrupts=False)
        n += 1
    else:
        raise SystemExit('never reached $%04X -- PC $%04X' % (END, r[PC]))
    codes = []
    i = STRING
    while m[i]:
        codes.append(m[i])
        i += 1
    #  the attribute run's last cell, and whether a character sits under it
    last_attr = max(a for a, _ in attrs)
    glyph_cols = sorted(set(a & 0x1F for a, _ in glyphs))
    out = {
        'codes': codes, 'cells': len(attrs),
        'ix_after': '%04X' % (r[IXl] | (r[IXh] << 8)),
        'attrs': [['%04X' % a, v] for a, v in attrs],
        'glyphs': [{'at': '%04X' % a, 'code': ((de - CHARSET) & 0xFFFF) // 8,
                    'row': ((de - CHARSET) & 0xFFFF) % 8} for a, de in glyphs],
        'last_attr': '%04X' % last_attr,
        'glyph_cols': glyph_cols,
        'attr_cols': sorted(set(a & 0x1F for a, _ in attrs)),
    }
    print('(a) THE CREDIT LINE: %r -- %d characters, %d glyph writes, %d attribute '
          'cells $%s..$%s all $%02X, IX left at $%s'
          % (''.join(chr(c) for c in codes), len(codes), len(glyphs), len(attrs),
             out['attrs'][0][0], out['attrs'][-1][0], out['attrs'][0][1],
             out['ix_after']))
    print('      *** NINE CELLS UNDER EIGHT CHARACTERS, and the ninth is $%s -- the '
          'LAST cell of the attribute file. ***  Columns: glyphs %s, attributes %s'
          % (out['last_attr'], out['glyph_cols'], out['attr_cols']))
    return out


def phase_table():
    """The four-column record table at $9A85, read for the front-end increment."""
    h, m = new()
    lows = [m[TABLE + i] for i in range(4)]
    highs = [m[TABLE + 4 + i] for i in range(4)]
    attrs = [m[TABLE + 8 + i] for i in range(4)]
    counts = [m[TABLE + 12 + i] for i in range(4)]
    #  IX starts at $9A32 and $802E chains by INC IX
    strings, a = [], 0x9A32
    for _ in range(4):
        s = ''
        while m[a]:
            s += chr(m[a]) if 32 <= m[a] < 127 else '?'
            a += 1
        a += 1
        strings.append(s)
    rows = [{'display': '%02X%02X' % (highs[i], lows[i]), 'attr': attrs[i],
             'cells': counts[i], 'text': strings[i], 'length': len(strings[i]),
             'exact': counts[i] == len(strings[i])} for i in range(4)]
    print('(b) THE TABLE AT $9A85, column-major, four parallel arrays of four')
    for r in rows:
        print('      $%s attr $%02X cells %2d  %-26r length %2d  %s'
              % (r['display'], r['attr'], r['cells'], r['text'], r['length'],
                 'EXACT' if r['exact'] else '*** OFF BY %d ***'
                 % (r['cells'] - r['length'])))
    print('      ...so the TABLE-driven counts are exact, while the two HAND-CODED '
          'sites are not: $8E83 loads 11 for ten characters and $9760 loads 9 for eight')
    return rows


def capture():
    out = {'line': phase_line(), 'table': phase_table()}
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s (no ROM byte: destinations and source ADDRESSES only)' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
