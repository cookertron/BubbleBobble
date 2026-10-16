# -*- coding: utf-8 -*-
"""M7.14 -- $900B, THE WAKE GATE, and $8C28, THE REVEAL it fires once.

$900B is the THIRD chain entry ($8D2B) and it does two unrelated things:

  (a) WHILE THE HEART IS UP.  ($FED0) != 0 -> $A891..$A898 are all set to $64.
      Those are the enemies' WAKE-UP DELAYS, so the heart holds the roster
      asleep by rewriting the whole table every pass.
  (b) WHEN THE CROSS HAS WORN OFF.  ($FED2) must be EXACTLY 1 ($901E DEC A /
      RET nz), and then $9028's `OR (HL) / INC HL / DJNZ` with B = 7 ORs
      $A891..$A897 -- SEVEN bytes, not eight; $A898 is NOT in the loop.  Only
      when every one of those seven is zero does it clear ($FED2) and call
      $8C28 with interrupts off.

$8C28 is the REVEAL: `CALL $8216` (the playfield out of the shadow, which the
port has), then 704 attribute cells RE-DERIVED from bit 5 of the colour shadow
(which the port has), then `CALL $957E` (the extend row -- transliterated and
NEVER CALLED) and `CALL $806C` (the lives icons), then EI and border 0.

Everything here is measured because the reading above is a reading.

Usage:  python tools/release.py            (capture)
"""
import sys, json, zlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FIXTURE = 'build/release_fixture.json'
BRANCH_BYTE = 0x8DC4
GATE = 0x900B
REVEAL = 0x8C28
DELAYS, NDELAY = 0xA891, 8
HEART, CROSS = 0xFED0, 0xFED2
DISPLAY, DISPLAY_END = 0x4000, 0x5B00
CALLEES = {0x8216: '$8216 repaint', 0x957E: '$957E extend row',
           0x806C: '$806C lives icons', 0x7F80: '$7F80 round digits'}


def new(state='round1_48'):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = r[12]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def run(h, limit=40 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])


def call_gate(state='round1_48', heart=None, cross=None, delays=None,
              watch=None):
    """One $900B with the world poked, returning (writes, memory)."""
    h, m = new(state)
    if heart is not None:
        m[HEART] = heart
    if cross is not None:
        m[CROSS] = cross
    if delays is not None:
        for i, v in enumerate(delays):
            m[DELAYS + i] = v
    lo, hi = watch or (0x4000, 0x10000)
    h.memobj.watch(lo, hi)
    h.memobj.log.clear()
    arm(h, GATE)
    run(h)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    return log, m


# ------------------------------------------------------------- (a) the heart
def phase_heart():
    """($FED0) != 0 rewrites the WHOLE delay table.  How many bytes, and what
       value -- and does it do it EVERY time or only when they differ?"""
    rows = []
    for heart in (0, 1, 0x80, 0xFF):
        log, m = call_gate(heart=heart, cross=0,
                           delays=[0x11 + i for i in range(NDELAY)],
                           watch=(DELAYS, DELAYS + NDELAY))
        rows.append({'heart': heart, 'writes': len(log),
                     'table': [m[DELAYS + i] for i in range(NDELAY)]})
    print('(a) HEART: ($FED0) -> writes to $A891..$A898 and the table after')
    for r in rows:
        print('      $%02X -> %2d writes, table %s'
              % (r['heart'], r['writes'],
                 ' '.join('%02X' % v for v in r['table'])))
    return rows


# ------------------------------------------------------------- (b) the cross
def phase_cross():
    """($FED2) must be EXACTLY 1, and the OR loop covers SEVEN bytes."""
    rows = []
    for cross in (0, 1, 2, 0xFF):
        log, m = call_gate(heart=0, cross=cross, delays=[0] * NDELAY)
        rows.append({'cross': cross, 'writes': len(log),
                     'fired': m[CROSS] == 0 and len(log) > 8})
    print('(b) CROSS: ($FED2) -> did the reveal fire?')
    for r in rows:
        print('      $%02X -> %5d writes, %s'
              % (r['cross'], r['writes'], 'FIRED' if r['fired'] else '-'))

    #  THE SEVENTH BYTE.  $9028's DJNZ runs with B = 7, so $A898 is never read.
    #  Poke it non-zero with the other seven at zero: if the reveal still fires,
    #  the loop is seven bytes and a port that ORs eight is wrong.
    eighth = []
    for k in range(NDELAY):
        d = [0] * NDELAY
        d[k] = 0x5A
        log, m = call_gate(heart=0, cross=1, delays=d)
        eighth.append({'nonzero_index': k, 'writes': len(log),
                       'fired': m[CROSS] == 0 and len(log) > 8})
    fired = [e['nonzero_index'] for e in eighth if e['fired']]
    print('    ...and ONE byte non-zero at a time: the reveal still fires for '
          'index %s (the DJNZ covers the rest)' % (fired or 'NONE'))
    return {'cross': rows, 'one_nonzero': eighth}


# ------------------------------------------------------------ (c) the reveal
def phase_reveal(state='round1_48'):
    """$8C28 called directly: the ordered CALL trace and the write census."""
    h, m = new(state)
    seen = []
    sp = arm(h, REVEAL)
    h.memobj.watch(DISPLAY, 0x10000)
    h.memobj.log.clear()
    #  step with a PC watch so the callee ORDER is recorded, not inferred
    n = 0
    while n < 40 * 10 ** 6:
        h.step(1, interrupts=False)
        p = h.regs[PC]
        if p in CALLEES and (not seen or seen[-1][0] != p):
            seen.append((p, n))
        if p in h.SENTINELS:
            break
        n += 1
    log = list(h.memobj.log)
    h.memobj.unwatch()
    disp = [a for (_, a, _) in log if DISPLAY <= a < 0x5800]
    attr = [a for (_, a, _) in log if 0x5800 <= a < DISPLAY_END]
    pcs = {}
    for (p, a, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
    out = {'state': state, 'writes': len(log),
           'display': len(disp), 'display_cells': len(set(disp)),
           'attrs': len(attr), 'attr_cells': len(set(attr)),
           'attr_lo': '%04X' % min(attr), 'attr_hi': '%04X' % max(attr),
           'order': [CALLEES[p] for (p, _) in seen],
           'writer_pcs': dict(sorted(pcs.items(), key=lambda kv: -kv[1])[:14]),
           'display_crc': zlib.crc32(bytes(m[DISPLAY:DISPLAY_END])) & 0xFFFFFFFF,
           'steps': n}
    print('(c) REVEAL on %s: %d writes -- %d display (%d cells), %d attribute '
          '(%d cells, $%s..$%s)'
          % (state, out['writes'], out['display'], out['display_cells'],
             out['attrs'], out['attr_cells'], out['attr_lo'], out['attr_hi']))
    print('    CALL ORDER: %s' % ' -> '.join(out['order']))
    return out


def phase_reveal_states():
    out = {}
    for s in ('round1_48', 'r20_48', 'play1p48'):
        try:
            out[s] = phase_reveal(s)
        except SystemExit as e:
            print('    (%s skipped: %s)' % (s, e))
    return out


# --------------------------------------------------------- (d) the negatives
def phase_negatives():
    """ZERO writes when the gate declines, on every arm of it."""
    rows = []
    cases = [('heart 0, cross 0', dict(heart=0, cross=0, delays=[0] * NDELAY)),
             ('heart 0, cross 2', dict(heart=0, cross=2, delays=[0] * NDELAY)),
             ('cross 1, one delay left', dict(heart=0, cross=1,
                                              delays=[0, 0, 0, 1, 0, 0, 0, 0])),
             ('cross 1, all delays $FF', dict(heart=0, cross=1,
                                              delays=[0xFF] * NDELAY))]
    for name, kw in cases:
        log, m = call_gate(**kw)
        rows.append({'case': name, 'writes': len(log)})
    print('(d) NEGATIVES: writes when the gate declines')
    for r in rows:
        print('      %-26s %d' % (r['case'], r['writes']))
    return rows


# ------------------------------------------------------------- (e) the border
def phase_border():
    h, m = new()
    h.ports.record_writes = True
    h.ports.writes = []
    m[HEART] = 0
    m[CROSS] = 1
    for i in range(NDELAY):
        m[DELAYS + i] = 0
    arm(h, GATE)
    run(h)
    outs = [(o[1] & 0xFF, o[2] & 0x07) for o in h.ports.writes
            if (o[1] & 0xFF) == 0xFE]
    print('(e) BORDER: OUT ($FE) values during the reveal: %s'
          % (' '.join('%d' % v for _, v in outs) or 'NONE'))
    return [v for _, v in outs]


def capture():
    out = {}
    out['heart'] = phase_heart()
    out['cross'] = phase_cross()
    out['reveal'] = phase_reveal_states()
    out['negatives'] = phase_negatives()
    out['border'] = phase_border()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
