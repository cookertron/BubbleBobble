# -*- coding: utf-8 -*-
"""M7.28 -- $98C4/$98D4's glyphs and $9904, the painter that erases them.

$98B5's round banner is a ~1-second animation that ERASES ITSELF: 256 passes,
each drawing two text rows through $802E and ten attribute cells through $995A,
and then $98E4/$98EA call $9904 twice to put everything back.  M7.7-R1b gated
the COST and the iteration count; the DRAW and the ERASE were counted stubs.

  $98BC  PUSH BC / LD IX,$9A06 / LD HL,$484C / CALL $802E
  $98C7  LD HL,$594C / LD B,10 / LD A,$47 / CALL $995A
  $98D1  LD HL,$488C / CALL $802E        -- IX is now at $9A11, "READY    !"
  $98D7  LD HL,$598C / LD B,10 / LD A,$47 / CALL $995A
  $98E1  POP BC / DJNZ $98BC

  $9904  LD A,8 / EX DE,HL / LD HL,$A000 / ADD HL,DE
  $990B  PUSH HL / PUSH DE / LD BC,10 / LDIR / POP DE / POP HL
  $9914  INC H / INC D / DEC A / JR nz     -- TEN BYTES x EIGHT ROWS from the
                                              SHADOW, both page steps EIGHT BIT
  $9919  LD A,D / DEC A / CALL $9938       -- the attribute page, $A091's rule
  $991F  LD HL,$A000 / ADD HL,DE           -- ...and the COLOUR shadow
  $9923  LD B,10 / LD C,$40                -- *** C IS NEVER READ ***
  $9927  LD A,(HL) / AND $20 / LD A,($8309) / JR z / LD A,($830A)
  $9932  LD (DE),A / INC E / INC L / DJNZ  -- both walks EIGHT BIT

*** IX IS RE-SEEDED EVERY PASS. ***  $98BD is INSIDE the DJNZ loop, so each of
the 256 iterations starts again at $9A06; $802E's own `INC IX` is what carries
it from "ROUND    n" to "READY    !" between the two calls.

NO ROM BYTE IS RECORDED: the draw phases store destination addresses and the
SOURCE ADDRESS each came from, as tools/banner.py does.

Usage:  python tools/roundbanner.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/roundbanner_fixture.json'
BRANCH_BYTE = 0x8DC4
PAINT = 0x9904
PRINT = 0x802E
ROWS = ((0x484C, 0x594C, 0x9A06), (0x488C, 0x598C, 0x9A11))
CHARSET = 0x3C00
STATE = 'round1_48'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, hl=None, ix=None):
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
    return sp


def snap(m):
    return bytes(m[0x4000:0x10000])


def diff(a, b, floor=None, lo=0x4000):
    out = []
    for i in range(len(a)):
        if a[i] != b[i]:
            ad = lo + i
            if floor is not None and floor - 64 <= ad < floor:
                continue
            out.append([ad, a[i], b[i]])
    return out


def run(h, limit=4 * 10 ** 6):
    r = h.sim.registers
    n = 0
    while n < limit:
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            return n
        n += 1
    raise SystemExit('bad bracket -- PC $%04X' % r[PC])


# ------------------------------------------------------- (a) $9904's writes
def phase_paint():
    """Driven with the display POISONED and the shadow given a known pattern,
       so what lands is visibly the SHADOW and not 'whatever was there'."""
    rows = []
    for disp, attr, _ in ROWS:
        h, m = new()
        #  a recognisable shadow under the ten cells, eight rows deep
        for r8 in range(8):
            for i in range(10):
                #  $FF, not $5A: the shadow pattern below runs $00..$80, and a
                #  poison inside that range collides with one of the 80 cells --
                #  the first run of this phase reported SEVENTY-NINE writes and
                #  the missing one was a byte that already agreed.
                m[(disp + 0x100 * r8 + i) & 0xFFFF] = 0xFF              # the poison
                m[(disp + 0xA000 + 0x100 * r8 + i) & 0xFFFF] = (0x11 * r8 + i) & 0xFF
        #  and a colour shadow that is SOLID on half the cells
        for i in range(10):
            m[(attr + 0xA000 + i) & 0xFFFF] = 0x20 if i % 2 else 0x00
            m[(attr + i) & 0xFFFF] = 0xFF
        sp0 = arm(h, PAINT, hl=disp)
        before = snap(m)
        run(h)
        after = snap(m)
        d = diff(before, after, floor=sp0)
        disp_w = [x for x in d if x[0] < 0x5800]
        attr_w = [x for x in d if 0x5800 <= x[0] < 0x5B00]
        other = [x for x in d if x[0] >= 0x5B00]
        rows.append({
            'display_at': '%04X' % disp, 'attr_at': '%04X' % attr,
            'display_writes': len(disp_w), 'attr_writes': len(attr_w),
            'other_writes': len(other),
            'display': [['%04X' % a, v] for a, _, v in disp_w],
            'attrs': [['%04X' % a, v] for a, _, v in attr_w],
            'open': m[0x8309], 'solid': m[0x830A],
        })
    print('(a) $9904 THE PAINTER')
    for r in rows:
        print('      from $%s: %d display bytes from the SHADOW, %d attribute cells '
              'derived from bit 5 of the COLOUR shadow, %d elsewhere '
              '(open $%02X / solid $%02X)'
              % (r['display_at'], r['display_writes'], r['attr_writes'],
                 r['other_writes'], r['open'], r['solid']))
        print('        attrs: %s' % ' '.join('$%s:$%02X' % (a, v) for a, v in r['attrs']))
    return rows


# --------------------------------------------------- (b) one banner iteration
def phase_draw():
    """$802E driven at each of the two rows, recording (destination, source
       address) pairs -- never a ROM byte."""
    out = {}
    for disp, attr, strat in ROWS:
        h, m = new()
        r = h.sim.registers
        writes = []
        arm(h, PRINT, hl=disp, ix=strat)
        n = 0
        while n < 2 * 10 ** 6:
            if r[PC] == 0x8052:
                hl = r[7] | (r[6] << 8)
                de = r[5] | (r[4] << 8)
                writes.append([hl, de])
            h.step(1, interrupts=False)
            if r[PC] in h.SENTINELS:
                break
            n += 1
        codes = []
        i = strat
        while m[i]:
            codes.append(m[i])
            i += 1
        out['%04X' % strat] = {
            'at': '%04X' % disp, 'attr_at': '%04X' % attr, 'codes': codes,
            'ix_after': '%04X' % (r[IXl] | (r[IXh] << 8)),
            'trace': [{'at': '%04X' % hl, 'code': ((de - CHARSET) & 0xFFFF) // 8,
                       'row': ((de - CHARSET) & 0xFFFF) % 8} for hl, de in writes],
        }
    print('(b) THE TWO ROWS')
    for k in sorted(out):
        r = out[k]
        print('      $%s -> $%s: %d chars, %d writes, IX left at $%s'
              % (k, r['at'], len(r['codes']), len(r['trace']), r['ix_after']))
    return out


# ------------------------------------------- (c) IX is re-seeded every pass
def phase_ix():
    """$98BD `LD IX,$9A06` is INSIDE the DJNZ loop.  Driven by running the
       banner's body twice and watching where IX starts each time."""
    h, m = new()
    r = h.sim.registers
    seen = []
    arm(h, 0x98BC)
    #  B is zero at entry on every state, so the DJNZ runs 256 times; stop
    #  after the second pass rather than execute a full second of animation
    n = 0
    passes = 0
    while n < 4 * 10 ** 6:
        if r[PC] == 0x802E and (r[IXl] | (r[IXh] << 8)) in (0x9A06, 0x9A11):
            seen.append('%04X' % (r[IXl] | (r[IXh] << 8)))
        if r[PC] == 0x98BC:
            passes += 1
            if passes > 2:
                break
        h.step(1, interrupts=False)
        n += 1
    print('(c) IX AT EACH $802E CALL over two passes: %s -- %s'
          % (seen[:6], 're-seeded every pass' if seen[:4] == ['9A06', '9A11', '9A06', '9A11']
             else 'NOT re-seeded'))
    return {'seen': seen[:8], 'reseeded': seen[:4] == ['9A06', '9A11', '9A06', '9A11']}


# --------------------------------------- (d) the painter's THREE arithmetics
def phase_arith():
    """*** $9904 HAS THREE WALKS AT TWO WIDTHS AND ITS TWO REAL ADDRESSES SHOW
       NONE OF THEM. ***  At $484C and $488C the LDIR's ten bytes never cross a
       page, the eight page steps never reach $FF, the attribute run's ten cells
       never cross $FF, and the derive's `AND 3` is absorbed by the `OR $58`.
       Four mutations lived behind that.  Two worlds put each on its boundary:

         $7AFA  the LDIR's ten bytes carry out of the low byte, the attribute
                run wraps its own, and the page derive reaches a value whose
                bit 4 the AND has to clear ($81 >> 3 = 16)
         $FC40  the eight `INC D`/`INC H` steps run $FC..$FF and WRAP to $00
    """
    #  *** $7AFA DOES NOT SHOW THE `AND 3`. ***  $58 already has bits 3 and 4
    #  set, so `OR $58` absorbs them and the mask only changes an answer when
    #  the shifted page has BIT 2 set.  Enumerated over all 256 start pages,
    #  that is pages $19..$38, $59..$78, $99..$B8 and $D9..$F8 -- and $60 is in
    #  RAM, so that is the world to drive it from.  Concluding "unreachable"
    #  from one sample was wrong and the enumeration is what said so.
    rows = []
    for disp in (0x7AFA, 0x60FA, 0xFC40):
        h, m = new()
        for r8 in range(8):
            for i in range(10):
                a = (disp + 0x100 * r8 + i) & 0xFFFF
                m[a] = 0xFF
                m[(a + 0xA000) & 0xFFFF] = (0x11 * r8 + i) & 0xFF
        sp0 = arm(h, PAINT, hl=disp)
        before = snap(m)
        run(h)
        after = snap(m)
        d = diff(before, after, floor=sp0)
        pages = sorted(set(a >> 8 for a, _, _ in d))
        rows.append({'from': '%04X' % disp, 'writes': len(d),
                     'pages': ['%02X' % p for p in pages],
                     'all': [['%04X' % a, v] for a, _, v in d]})
    print("(d) THE PAINTER'S THREE ARITHMETICS")
    for r in rows:
        print('      from $%s: %d writes over pages %s'
              % (r['from'], r['writes'], r['pages']))
    return rows


def capture():
    out = {'paint': phase_paint(), 'draw': phase_draw(), 'ix': phase_ix(),
           'arith': phase_arith()}
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s (no ROM byte: destinations and source ADDRESSES only)' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
