# -*- coding: utf-8 -*-
"""M7.26 -- $801D and $8058: the DOUBLE-HEIGHT banner printer.

$802E is the string printer and $803C is its MODE: the operand of $803B's
`CALL nn`.  $804F writes a glyph at single height; $8058 writes it at DOUBLE,
four source rows doubled into one character cell and four more into the cell
below.  $801D swaps the operand to $8058, prints, and puts $804F back -- so the
mode is live state and the routine is its own bracket.

    $801D  LD DE,$8058 / LD ($803C),DE / CALL $802E / LD HL,$804F /
           LD ($803C),HL / RET
    $802E  LD A,(IX) / INC IX / OR A / RET z          -- NUL terminates
           EX DE,HL / CALL $8044 / EX DE,HL           -- DE := $3C00 + 8*code
           PUSH HL / CALL $804F-or-$8058 / POP HL / INC L / JR $802E
    $804F  LD B,8  / LD A,(DE) / LD (HL),A / INC DE / INC H / DJNZ
    $8058  PUSH HL / CALL $8061 / POP HL / LD BC,$20 / ADD HL,BC  -- and FALLS IN
    $8061  LD B,4  / LD A,(DE) / INC DE / LD (HL),A / INC H / LD (HL),A / INC H

*** NOT ONE ROM BYTE IS RECORDED HERE. ***  The glyphs live in the Spectrum ROM
and this project ships none, so every phase records WHERE a byte was written and
WHICH SOURCE ADDRESS it came from -- never the value.  The structure is fully
determined by those two, and the port's substitute font (tools/make_banner.py)
is what supplies the pixels.

Usage:  python tools/banner.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/banner_fixture.json'
BRANCH_BYTE = 0x8DC4
DOUBLE = 0x801D
PRINT = 0x802E
MODE_OP = 0x803C                # the operand of $803B CALL nn
SINGLE_BLIT = 0x804F
DOUBLE_BLIT = 0x8058
CHARSET = 0x3C00
STRINGS = {'hurry': (0x9A1C, 0x4000), 'perfect': (0x9A9F, 0x484B),
           'nice': (0x9AA9, 0x4869)}
STATE = 'extcomp'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, ix=None, hl=None):
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
    if ix is not None:
        r[IXh] = (ix >> 8) & 0xFF
        r[IXl] = ix & 0xFF
    if hl is not None:
        r[6] = (hl >> 8) & 0xFF      # H
        r[7] = hl & 0xFF             # L
    return sp


def trace(h, limit=2 * 10 ** 6):
    """Runs one call, returning the write trace as (dest, source) pairs.

       The SOURCE is DE at the moment of the store, which is an address in the
       ROM charset -- an address, not a byte.  Converting it to (code, row) is
       what makes the doubling provable without transcribing anything."""
    r = h.sim.registers
    m = h.memobj.m
    writes = []
    n = 0
    prev = None
    while n < limit:
        pcv = r[PC]
        # the two store sites: $8052 (single) and $8065/$8067 (double)
        if pcv in (0x8052, 0x8065, 0x8067):
            hl = r[7] | (r[6] << 8)
            de = r[5] | (r[4] << 8)
            #  *** $8064's `INC DE` HAPPENS BEFORE THE STORE. ***  $804F reads
            #  and stores and THEN increments ($8051/$8052/$8053), but $8061
            #  reads, increments, and then stores TWICE ($8063/$8064/$8065/
            #  $8067) -- so DE at the double-height sites is already one past
            #  the byte being written.  Recorded without this the trace reads
            #  "rows 1,1,2,2,...,7,7 and then row 0 of the NEXT character",
            #  which is an off-by-one dressed up as a finding.
            if pcv != 0x8052:
                de = (de - 1) & 0xFFFF
            writes.append([hl, de, '%04X' % pcv])
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            break
        n += 1
    else:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    return writes


def decode(writes):
    """(dest, source) -> (dest, code, row).  No ROM byte is involved."""
    out = []
    for hl, de, site in writes:
        rel = (de - CHARSET) & 0xFFFF
        out.append({'at': '%04X' % hl, 'code': rel // 8, 'row': rel % 8,
                    'site': site})
    return out


# ---------------------------------------------------- (a) the mode operand
def phase_mode():
    """$803C is the live operand of $803B's CALL, and $801D is its bracket."""
    rows = []
    for name, (ix, hl) in sorted(STRINGS.items()):
        h, m = new()
        before = m[MODE_OP] | (m[MODE_OP + 1] << 8)
        seen = []
        arm(h, DOUBLE, ix=ix, hl=hl)
        r = h.sim.registers
        n = 0
        while n < 2 * 10 ** 6:
            if r[PC] == 0x803B:
                seen.append(m[MODE_OP] | (m[MODE_OP + 1] << 8))
            h.step(1, interrupts=False)
            if r[PC] in h.SENTINELS:
                break
            n += 1
        rows.append({'string': name, 'before': before,
                     'during': sorted(set(seen)), 'calls': len(seen),
                     'after': m[MODE_OP] | (m[MODE_OP + 1] << 8)})
    print('(a) THE MODE OPERAND at $803C')
    for r in rows:
        print('      %-8s $%04X -> during %s (%d glyphs) -> $%04X'
              % (r['string'], r['before'],
                 ['$%04X' % v for v in r['during']], r['calls'], r['after']))
    return rows


# ------------------------------------------------- (b) the double-height blit
def phase_double():
    """Every write of a single glyph, as (dest, code, row).  FOUR source rows
       into the cell at HL and FOUR into the cell at HL+$20, each written
       TWICE -- sixteen display rows from eight source bytes."""
    h, m = new()
    #  a one-character string, so the trace is one glyph and nothing else
    m[0x9B80] = ord('N')
    m[0x9B81] = 0x00
    arm(h, DOUBLE, ix=0x9B80, hl=0x4869)
    w = decode(trace(h))
    print('(b) ONE GLYPH AT DOUBLE HEIGHT: %d writes from %d source rows'
          % (len(w), len(set(x['row'] for x in w))))
    for x in w:
        print('      $%s <- code %d row %d   (%s)'
              % (x['at'], x['code'], x['row'], x['site']))
    return w


def phase_single():
    """The same glyph through $804F, for the contrast: eight writes, one row
       each, one character cell."""
    h, m = new()
    m[0x9B80] = ord('N')
    m[0x9B81] = 0x00
    arm(h, PRINT, ix=0x9B80, hl=0x4869)
    w = decode(trace(h))
    print('(c) THE SAME GLYPH AT SINGLE HEIGHT: %d writes, rows %s'
          % (len(w), sorted(set(x['row'] for x in w))))
    return w


# ------------------------------------------------------ (d) the two strings
def phase_strings():
    rows = {}
    for name, (ix, hl) in sorted(STRINGS.items()):
        h, m = new()
        entry = DOUBLE if name != 'hurry' else PRINT
        arm(h, entry, ix=ix, hl=hl)
        w = decode(trace(h))
        codes = []
        i = ix
        while m[i]:
            codes.append(m[i])
            i += 1
        cols = sorted(set(int(x['at'], 16) & 0x1F for x in w))
        rows[name] = {'entry': '%04X' % entry, 'at': '%04X' % hl,
                      'codes': codes, 'writes': len(w),
                      'distinct': len(set(x['at'] for x in w)),
                      'columns': cols, 'trace': w}
    print('(d) THE THREE STRINGS')
    for name in sorted(rows):
        r = rows[name]
        print('      %-8s from $%s at $%s: %d chars, %d writes into %d cells, '
              'columns %s' % (name, r['entry'], r['at'], len(r['codes']),
                              r['writes'], r['distinct'] // 8, r['columns']))
    return rows


# ------------------------------------------------------- (e) the INC L wrap
def phase_wrap():
    """$803F is `INC L`, EIGHT BIT -- a string that runs off the right of a
       display third wraps to column 0 of the SAME third rather than moving on."""
    h, m = new()
    for i, c in enumerate(b'NICE'):
        m[0x9B80 + i] = c
    m[0x9B84] = 0x00
    arm(h, DOUBLE, ix=0x9B80, hl=0x487E)      # column 30 of third 1
    w = decode(trace(h))
    cols = [int(x['at'], 16) & 0x1F for x in w]
    pages = sorted(set(int(x['at'], 16) >> 8 for x in w))
    print('(e) THE EIGHT-BIT `INC L`: started at column 30, columns touched %s, '
          'pages %s -- %s'
          % (sorted(set(cols)), ['$%02X' % p for p in pages],
             'WRAPPED inside the third' if 0 in cols else 'did not wrap'))
    return {'columns': sorted(set(cols)), 'pages': ['%02X' % p for p in pages],
            'wrapped': 0 in cols, 'trace': w}


# --------------------------------------------- (f) the THREE arithmetics
def phase_arith():
    """*** THE EIGHT-BIT AND SIXTEEN-BIT ADDS, EACH DRIVEN WHERE IT BITES. ***

       $803F `INC L`, $8054/$8066/$8068 `INC H` and $805D `ADD HL,BC` are three
       different widths, and none of them shows at a comfortable address.  The
       first version of this tool's wrap phase started at column 30, where L
       runs $7E $7F $80 $81 and never wraps at all -- the columns it reported
       (30, 31, 0, 1) are the ROW field changing, not an eight-bit carry.  These
       three worlds put each add on its own boundary."""
    out = {}

    #  (i) INC L wraps: start one column from the end of the page
    h, m = new()
    for i, c in enumerate(b'NIC'):
        m[0x9B80 + i] = c
    m[0x9B83] = 0x00
    arm(h, PRINT, ix=0x9B80, hl=0x48FE)
    w = decode(trace(h))
    out['inc_l'] = {'from': '48FE', 'trace': w,
                    'lows': sorted(set(int(x['at'], 16) & 0xFF for x in w)),
                    'pages': sorted(set(int(x['at'], 16) >> 8 for x in w))}

    #  (ii) INC H wraps: start in the last page
    h, m = new()
    m[0x9B80] = ord('N')
    m[0x9B81] = 0x00
    arm(h, PRINT, ix=0x9B80, hl=0xFC40)
    w = decode(trace(h))
    out['inc_h_single'] = {'from': 'FC40', 'trace': w,
                           'pages': [int(x['at'], 16) >> 8 for x in w]}

    h, m = new()
    m[0x9B80] = ord('N')
    m[0x9B81] = 0x00
    arm(h, DOUBLE, ix=0x9B80, hl=0xFC40)
    w = decode(trace(h))
    out['inc_h_double'] = {'from': 'FC40', 'trace': w,
                           'pages': [int(x['at'], 16) >> 8 for x in w]}

    #  (iii) ADD HL,BC carries: the second cell is $20 past an L of $FE
    h, m = new()
    m[0x9B80] = ord('N')
    m[0x9B81] = 0x00
    arm(h, DOUBLE, ix=0x9B80, hl=0x48FE)
    w = decode(trace(h))
    out['add_hl_bc'] = {'from': '48FE', 'trace': w,
                        'cells': sorted(set(int(x['at'], 16) & 0xFF for x in w)),
                        'pages': sorted(set(int(x['at'], 16) >> 8 for x in w))}

    print('(f) THE THREE ARITHMETICS')
    print('      INC L from $48FE: lows %s, pages %s -- %s'
          % (['$%02X' % v for v in out['inc_l']['lows']],
             ['$%02X' % v for v in out['inc_l']['pages']],
             'WRAPPED' if 0x00 in out['inc_l']['lows'] else 'did not wrap'))
    print('      INC H from $FC40, single: pages %s'
          % ['$%02X' % p for p in out['inc_h_single']['pages']])
    print('      INC H from $FC40, double: pages %s'
          % ['$%02X' % p for p in out['inc_h_double']['pages']])
    print('      ADD HL,BC from $48FE: lows %s, pages %s -- the second cell %s'
          % (['$%02X' % v for v in out['add_hl_bc']['cells']],
             ['$%02X' % v for v in out['add_hl_bc']['pages']],
             'CARRIED into H' if len(out['add_hl_bc']['pages']) > 8
             else 'stayed in the page'))
    return out


def capture():
    out = {}
    out['mode'] = phase_mode()
    out['double'] = phase_double()
    out['single'] = phase_single()
    out['strings'] = phase_strings()
    out['wrap'] = phase_wrap()
    out['arith'] = phase_arith()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s (addresses and source ADDRESSES only -- no ROM byte)' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
