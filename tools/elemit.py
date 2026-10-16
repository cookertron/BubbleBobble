# -*- coding: utf-8 -*-
"""M7.22 -- $7E80, THE ELEMENT EMITTER: the chain entry that HALTS, and then
DOES NOT TRUST WHAT IT SAW BEFORE IT.

The eighth chain entry ($8D3A).  Once a round has an element, this is what drops
water, fire or lightning into the playfield.  Four things make it worth a tool:

  (a) *** IT HALTS AND THEN RE-TESTS. ***  $7EBA finds a free pool slot, and
      $7EC2's `EI / HALT` gives the frame away -- and $7EC4 asks `BIT 7,(HL)`
      AGAIN, because the ISR runs during that frame and may have taken the slot.
      A port that treats the HALT as a delay and keeps the slot it found is
      wrong exactly when the game is busiest.
  (b) TWO OPERANDS CARRY THE ELEMENT.  $7EFB is the operand of $7EF8's
      `LD (IY+9),n` -- the class travels into the slot inside an instruction --
      and $7EB2 is the operand of $7EB1's `CP n`, set to 4 or 1 by `CP 5`, so
      elements 5 and up are capped at ONE on screen and the rest at four.
  (c) THE RETURN ADDRESS IS PUSHED.  $7ECB `LD BC,$7F05 / PUSH BC` means the
      `RET nz` at $7EEB lands on $7F05, which puts the even ISR gate back -- a
      `finally` written in 1987.
  (d) IT FIRES ON ONE FRAME IN 256: $7E98 `CP $2A` on ($8DBD).

Usage:  python tools/elemit.py            (capture)
        python tools/elemit.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/elemit_fixture.json'
BRANCH_BYTE = 0x8DC4
EMIT = 0x7E80
HALT_AT = 0x7EC3
ELEM = 0x7E0E
CLEAR = 0x8E3B
CLOCK = 0x8DBD
OP_CLASS = 0x7EFB          # the operand of $7EF8 LD (IY+9),n
OP_CAP = 0x7EB2            # the operand of $7EB1 CP n
OP_SLOT = 0x7ED7           # the operand of $7ED6 LD A,n -- the 0..3 position cycle
TABLE = 0x7F0B
POOL = 0xFED8
GATE5 = 0xFEC5
STATE = 'round1_48'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


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


def emit(h, on_halt=None):
    """One $7E80, with $7EC3's HALT stepped over.

    The HALT is the machine waiting for the frame interrupt; with interrupts off
    it never leaves and with them on the whole ISR runs, which is $8D72's fixture
    and not this one's.  `on_halt` is called AT the halt, which is how the
    re-test at $7EC4 is driven: it is the only place the ISR's effect can be
    simulated honestly."""
    arm(h, EMIT)
    halts = 0
    n = 0
    r = h.sim.registers
    while n < 2 * 10 ** 6:
        if r[PC] == HALT_AT:
            halts += 1
            if on_halt is not None:
                on_halt(h.memobj.m)
            r[PC] = 0x7EC4              # the interrupt's own effect
            continue
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            return halts
        n += 1
    raise SystemExit('bad bracket -- PC $%04X' % r[PC])


def ready(m, elem=2, slot_busy=0):
    """A world $7E80 will emit in: an element, the clear latch down, the frame
       counter on $2A, and the pool empty."""
    m[ELEM] = elem
    m[CLEAR] = 0
    m[CLOCK] = 0x2A
    m[CLOCK + 1] = 0x00
    for k in range(12):
        p = POOL + 10 * k
        m[p + 7] = 0x80 if k < slot_busy else 0x00
        m[p + 9] = 0x00
    m[OP_SLOT] = 0
    m[GATE5] = 1
    #  the four emit points must not read as SOLID
    for i in range(4):
        ptr = m[TABLE + 4 * i] | (m[TABLE + 4 * i + 1] << 8)
        m[ptr] = m[ptr] & ~0x20


def slot_of(m):
    for k in range(12):
        if m[POOL + 10 * k + 7] == 0x84:
            return k
    return None


# ------------------------------------------------------------ (a) the gates
def phase_gates():
    rows = []

    def one(name, pokes):
        h, m = new()
        ready(m)
        for a, v in pokes.items():
            m[a] = v
        halts = emit(h)
        rows.append({'case': name, 'slot': slot_of(m), 'halts': halts,
                     'cap': m[OP_CAP], 'cls': m[OP_CLASS]})

    one('ready (element 2)', {})
    one('...no element ($7E0E = 0)', {ELEM: 0})
    one('...the round is CLEARING ($8E3B)', {CLEAR: 1})
    one('...the frame counter is $29', {CLOCK: 0x29})
    one('...the frame counter is $2B', {CLOCK: 0x2B})
    one('...the frame counter high byte is not zero', {CLOCK + 1: 0x01})
    print('(a) GATES')
    for r in rows:
        print('      %-42s slot %s, %d halt(s), cap $%02X, class $%02X'
              % (r['case'], r['slot'], r['halts'], r['cap'], r['cls']))
    return rows


# --------------------------------------------------------- (b) the operands
def phase_operands():
    rows = []
    for e in range(0, 16):
        h, m = new()
        ready(m, elem=e)
        emit(h)
        rows.append({'elem': e, 'cap': m[OP_CAP], 'cls': m[OP_CLASS],
                     'slot': slot_of(m),
                     'plus9': m[POOL + 9] if slot_of(m) == 0 else None})
    print('(b) OPERANDS: element -> $7EB2 (the CAP) and $7EFB (the CLASS)')
    print('      %s' % ' '.join('%d:cap%d/cls%d' % (r['elem'], r['cap'], r['cls'])
                                for r in rows))
    return rows


# ------------------------------------------------------------- (c) the cap
def phase_cap():
    """How many LIVE elements block a new one, and the cap is an operand."""
    rows = []
    for elem in (2, 5):
        for live in range(0, 7):
            h, m = new()
            ready(m, elem=elem)
            #  `live` slots with (IY+9) >= 2, which is what $7EA7 counts
            for k in range(live):
                m[POOL + 10 * k + 9] = 3
            emit(h)
            rows.append({'elem': elem, 'live': live, 'cap': m[OP_CAP],
                         'emitted': slot_of(m) is not None})
    print('(c) CAP: $7EA7 counts slots whose +9 is >= 2 and $7EB1 compares')
    for elem in (2, 5):
        rs = [r for r in rows if r['elem'] == elem]
        print('      element %d (cap %d): %s'
              % (elem, rs[0]['cap'],
                 ' '.join('%d:%s' % (r['live'], 'Y' if r['emitted'] else '-')
                          for r in rs)))
    return rows


# ------------------------------------------------------- (d) the free scan
def phase_free():
    """Which slot it takes, swept over which are busy."""
    rows = []
    for busy in range(0, 13):
        h, m = new()
        ready(m, slot_busy=busy)
        halts = emit(h)
        rows.append({'busy': busy, 'slot': slot_of(m), 'halts': halts})
    print('(d) FREE SCAN: 12 slots of stride 10 from $%04X, and $7EBA takes the '
          'FIRST with bit 7 clear' % POOL)
    print('      busy -> slot: %s'
          % ' '.join('%d:%s' % (r['busy'], r['slot']) for r in rows))
    print('      halts: %s' % ' '.join(str(r['halts']) for r in rows))
    return rows


# --------------------------------------------------------- (e) the re-test
def phase_retest():
    """*** THE POINT OF THE WHOLE ROUTINE. ***  $7EC4 asks BIT 7 AGAIN after the
       HALT, because the frame it gave away is one the ISR ran in."""
    rows = []
    for taken, name in ((False, 'the slot is still free'),
                        (True, 'the ISR took the slot during the HALT')):
        h, m = new()
        ready(m)

        def on_halt(mm, taken=taken):
            if taken:
                mm[POOL + 7] = 0x80          # slot 0's +7, the one it found
        emit(h, on_halt)
        rows.append({'case': name, 'slot': slot_of(m),
                     'slot0_plus7': m[POOL + 7], 'gate5': m[GATE5]})
    print('(e) THE RE-TEST at $7EC4')
    for r in rows:
        print('      %-40s -> emitted into %s, ($FEC5) = %d'
              % (r['case'], r['slot'], r['gate5']))
    return rows


# ------------------------------------------------------- (f) the ISR gate
def phase_gate():
    """($FEC5) off at $7EC7 and back on at $7F05 -- and $7F05 is reached through
       a PUSHED return address, so even the BIT 5 refusal restores it."""
    rows = []
    for solid, name in ((False, 'the emit point is open'),
                        (True, 'the emit point is SOLID (bit 5 set)')):
        h, m = new()
        ready(m)
        if solid:
            ptr = m[TABLE + 4] | (m[TABLE + 5] << 8)   # index 1, the first used
            m[ptr] = m[ptr] | 0x20
        h.memobj.watch(GATE5, GATE5 + 1)
        h.memobj.log.clear()
        emit(h)
        log = [[p, v] for (p, a, v) in h.memobj.log]
        h.memobj.unwatch()
        rows.append({'case': name, 'log': log, 'slot': slot_of(m),
                     'gate5': m[GATE5]})
    print('(f) THE ISR GATE')
    for r in rows:
        print('      %-40s writes %s, slot %s, ends %d'
              % (r['case'], ' '.join('$%04X:=%d' % (p, v) for p, v in r['log']),
                 r['slot'], r['gate5']))
    return rows


# -------------------------------------------------- (g) the position cycle
def phase_cycle():
    """$7ED7 is a 0..3 operand and $7F0B is four entries of [ptr, X, Y]."""
    h, m = new()
    table = [{'index': i,
              'ptr': m[TABLE + 4 * i] | (m[TABLE + 4 * i + 1] << 8),
              'x': m[TABLE + 4 * i + 2], 'y': m[TABLE + 4 * i + 3]}
             for i in range(4)]
    rows = []
    h, m = new()
    ready(m)
    for i in range(10):
        for k in range(12):
            m[POOL + 10 * k + 7] = 0x00
            m[POOL + 10 * k + 9] = 0x00
        emit(h)
        s = slot_of(m)
        rows.append({'call': i, 'op': m[OP_SLOT],
                     'x': m[POOL + 10 * s + 5] if s is not None else None,
                     'y': m[POOL + 10 * s + 6] if s is not None else None})
    print('(g) THE CYCLE: table %s'
          % ' '.join('[%d]=$%04X (%d,%d)' % (t['index'], t['ptr'], t['x'], t['y'])
                     for t in table))
    print('      ten calls -> operand %s'
          % ' '.join(str(r['op']) for r in rows))
    print('      ten calls -> (x,y) %s'
          % ' '.join('(%s,%s)' % (r['x'], r['y']) for r in rows))
    return {'table': table, 'rows': rows}


# --------------------------------------------------------- (h) the slot fields
def phase_fields():
    h, m = new()
    ready(m, elem=4)
    emit(h)
    s = slot_of(m)
    rec = [m[POOL + 10 * s + i] for i in range(10)] if s is not None else None
    print('(h) THE SLOT: %s -> %s'
          % (s, ' '.join('%02X' % v for v in rec) if rec else 'none'))
    return {'slot': s, 'record': rec}


def capture(jobs=15):
    out = {}
    out['gates'] = phase_gates()
    out['operands'] = phase_operands()
    out['cap'] = phase_cap()
    out['free'] = phase_free()
    out['retest'] = phase_retest()
    out['gate'] = phase_gate()
    out['cycle'] = phase_cycle()
    out['fields'] = phase_fields()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
