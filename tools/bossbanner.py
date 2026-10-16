# -*- coding: utf-8 -*-
"""M7.29 -- $8E9D/$8EA7, the boss banner: the LAST $802E call site.

    $8E7A  LD IX,$9A27 / LD HL,$484B / LD A,$85 / LD B,11 / CALL $8E9D
    $8E9D  PUSH HL / EX AF,AF' / CALL $A090 / EX AF,AF' / CALL $995A / POP HL
    $8EA7  JP $802E

*** ONE HL ADDRESSES BOTH, AND THE TWO RUNS ARE DIFFERENT LENGTHS. ***  $A090
turns the DISPLAY address into its attribute address, $995A paints B cells
there, and then the SAME HL -- popped back -- is where the glyphs go.  B is
ELEVEN and "WELL DONE!" is TEN characters, so the attribute run is one cell
wider than the text it colours.  The `EX AF,AF'` pair exists only because $A090
clobbers A, which is carrying the attribute.

$8EA7 is a JP, not a CALL: $802E's RET returns from $8E9D's caller.

TWO WORLDS, because the shipped call cannot reach either walk's wrap:
    $484B   the real one -- attributes $594B..$5955, glyphs $484B..$4854
    $48FA   where BOTH eight-bit walks bite -- the attributes run $59FA..$59FF
            and WRAP to $5900..$5904, and the glyphs wrap the same way

NO ROM BYTE IS RECORDED: destinations and the SOURCE ADDRESS each came from.

Usage:  python tools/bossbanner.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/bossbanner_fixture.json'
BRANCH_BYTE = 0x8DC4
ENTRY = 0x8E9D
STRING = 0x9A27
ATTR = 0x85
CELLS = 11
CHARSET = 0x3C00
STATE = 'boss'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, hl=None, ix=None, a=None, b=None):
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
    if hl is not None:
        r[6] = (hl >> 8) & 0xFF
        r[7] = hl & 0xFF
    if ix is not None:
        r[IXh] = (ix >> 8) & 0xFF
        r[IXl] = ix & 0xFF
    if a is not None:
        r[0] = a & 0xFF
    if b is not None:
        r[2] = b & 0xFF
    return sp


def drive(hl, cells=CELLS, attr=ATTR, string=STRING):
    """One call, returning the attribute writes and the glyph trace."""
    h, m = new()
    r = h.sim.registers
    glyphs, attrs = [], []
    sp0 = arm(h, ENTRY, hl=hl, ix=string, a=attr, b=cells)
    n = 0
    while n < 2 * 10 ** 6:
        pcv = r[PC]
        if pcv == 0x8052:                       # $804F's store -- a glyph byte
            glyphs.append([r[7] | (r[6] << 8), r[5] | (r[4] << 8)])
        elif pcv == 0x995C:                     # $995A's store -- an attribute
            attrs.append([r[7] | (r[6] << 8), r[0]])
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            break
        n += 1
    else:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    codes = []
    i = string
    while m[i]:
        codes.append(m[i])
        i += 1
    return {
        'from': '%04X' % hl, 'cells': cells, 'attr': attr, 'codes': codes,
        'ix_after': '%04X' % (r[IXl] | (r[IXh] << 8)),
        'attrs': [['%04X' % a, v] for a, v in attrs],
        'glyphs': [{'at': '%04X' % a, 'code': ((de - CHARSET) & 0xFFFF) // 8,
                    'row': ((de - CHARSET) & 0xFFFF) % 8} for a, de in glyphs],
    }


def phase_shipped():
    r = drive(0x484B)
    print('(a) THE SHIPPED CALL at $484B: %d attribute cells %s..%s all $%02X, '
          '%d glyph writes for %d characters, IX left at $%s'
          % (len(r['attrs']), r['attrs'][0][0], r['attrs'][-1][0], r['attrs'][0][1],
             len(r['glyphs']), len(r['codes']), r['ix_after']))
    print('      *** ELEVEN CELLS UNDER TEN CHARACTERS *** -- the attribute run is '
          'one wider than the text')
    return r


def phase_wrap():
    r = drive(0x48FA)
    acols = sorted(set(int(a, 16) & 0xFF for a, _ in r['attrs']))
    apages = sorted(set(int(a, 16) >> 8 for a, _ in r['attrs']))
    gcols = sorted(set(int(g['at'], 16) & 0xFF for g in r['glyphs']))
    gpages = sorted(set(int(g['at'], 16) >> 8 for g in r['glyphs']))
    print('(b) THE WRAP WORLD at $48FA')
    print('      attributes: lows %s over pages %s'
          % (['$%02X' % v for v in acols], ['$%02X' % p for p in apages]))
    print('      glyphs:     lows %s over pages %s'
          % (['$%02X' % v for v in gcols], ['$%02X' % p for p in gpages]))
    print('      BOTH eight-bit walks wrap: %s'
          % (0x00 in acols and 0x00 in gcols))
    r['attr_lows'] = acols
    r['attr_pages'] = ['%02X' % p for p in apages]
    r['glyph_lows'] = gcols
    r['glyph_pages'] = ['%02X' % p for p in gpages]
    return r


def phase_attr():
    """$995A ORs $40 into the value, and $85 is the one shipped attribute where
       that shows: $85 -> $C5.  Swept so the OR is a measurement, not a note."""
    rows = []
    for a in (0x85, 0x47, 0xC5, 0x00, 0xFF, 0x40, 0x3F):
        r = drive(0x484B, attr=a)
        rows.append({'given': a, 'written': r['attrs'][0][1],
                     'same': all(v == r['attrs'][0][1] for _, v in r['attrs'])})
    print('(c) $995A\'s `OR $40`: %s'
          % ' '.join('$%02X->$%02X' % (r['given'], r['written']) for r in rows))
    return rows


def capture():
    out = {'shipped': phase_shipped(), 'wrap': phase_wrap(), 'attr': phase_attr()}
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s (no ROM byte: destinations and source ADDRESSES only)' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
