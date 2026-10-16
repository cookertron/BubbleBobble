"""M7.7-I7 -- the per-round SPAWN FLOW $89CB and the two TYPE decisions.

  $89CB  LD HL,$8CB0; round >= $50 forks to $8A09 (no timer gate at all);
         otherwise ($8DB7) == 4 goes to the POWER-UP and == 2 to the POINTS
         ITEM.  BOTH ARE EQUALITY TESTS, not thresholds, and each is guarded by
         its own one-shot bit in $8CB0 (bit 0 power-up, bit 1 points).
  $89E4  the points-item type: 12 - ($9AE9), with ($9AE9) >= 12 giving 0 and
         ($9AE9) == 0 giving 11.  Spawned into $9605 -- ENTRY 0 of the fruit
         table -- with its X from $8CAF.
  $8A0D  the power-up type: round 80 forces 13 and round 81 forces 12; a round
         found in the 16-byte list $8A62 takes the {3,3,4,5} draw at $8A2E;
         anything else takes the wide draw at $8A38, filtered through the
         6-byte EXCLUSION list $8A72 (found -> type 0, not found -> keep).
         Then CP 6 arms the UMBRELLA LOCK by writing 6 into $8A76, the fifth
         exclusion slot, and CP 7 with ($7E0E) == 2 doubles 7 into 14.
         Spawned into $9603 with its X from $8CAE.

THE TWO `LD A,R` SITES ARE REPLACED, NOT SAMPLED.  $8A2E and $8A38 are both
`ED 5F`, two bytes, and are patched in place to `3E nn` (LD A,n) -- the same
length, so nothing moves -- and nn swept.  That is a DECLARED SUBSTITUTE (see
docs/RNG.md), not a measurement of R: it makes the branch structure observable,
which is the thing under test.  The patch is recorded in the fixture and the
bytes are restored afterwards.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THE TIMER GATES ARE EQUALITIES.  In any captured round the timer is long
    past $0400 and $8CB0 is already latched, so $89CB is a no-op for a correct
    model AND a broken one.  $8CB0 is cleared and $8DB6 poked to each boundary,
    INCLUDING $0500 -- where a ">=" model would still spawn and the real one
    does not.
  * THE $8A38 POLARITY.  When the drawn value is 0, "not found, keep 0" and the
    inverted "found, so zero it" both return 0, so a sweep of multiples of 16
    passes with the polarity backwards.  The sweep covers every nn 0..255, so
    n&15 = 1 (must stay 1) and n&15 = 3 (must become 0) are both present.
  * THE UMBRELLA LOCK.  With $8A76 = $06 "the lock exists" and "6 is simply
    never drawn" are identical; with $8A76 = $2A "present but unfired" and "no
    lock at all" are identical.  Only the THREE-CALL TRANSITION separates them,
    so the lock is swept as a sequence: draw 6, then draw 6 again.
  * THE $9AE9 MAP.  "12 - L" and "12 - L with the L == 0 special case" agree for
    every L except 0, so L = 0 is swept explicitly.

AND IT SETTLES ROUND 77.  $8A28's CPIR runs with BC = 16 and decrements on the
MATCHING comparison too, so a match on the SIXTEENTH byte leaves C = 0 -- which
the INC C / DEC C / JR z test cannot tell from exhaustion.  The sixteenth byte
of $8A62 is 77.  The reading pass marked this LIKELY rather than SETTLED; one
call settles it, by forcing a draw whose two paths give different types.

Usage:  python tools/puspawn.py capture
        python tools/puspawn.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FLOW = 0x89CB
POWER = 0x8A0D
POINTS = 0x89E4
LATCH = 0x8CB0
ROUND = 0x8609
TIMER = 0x8DB6
LIST_AT, LIST_N = 0x8A62, 16
EXCL_AT, EXCL_N = 0x8A72, 6
LOCK = 0x8A76
WATER = 0x7E0E
DRAW_NARROW, DRAW_WIDE = 0x8A2E, 0x8A38
BLOCK = 0x9603
FIXTURE = 'build/puspawn_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

WATCH = {'8CAE': 0x8CAE, '8CAF': 0x8CAF, '8CB0': 0x8CB0, '8A76': 0x8A76,
         '9603': 0x9603, '9604': 0x9604, '9605': 0x9605, '9606': 0x9606}


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, hl=None):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    if hl is not None:
        r[6], r[7] = hl >> 8, hl & 0xFF
    r[PC] = addr
    return sp


def run(h, sp):
    """...recording WHICH draw site executed.

       Both sites are patched to LD A,n, so no value distinguishes them -- but
       the engine's feed queue matches on the SITE, so the fixture has to say
       which one fired.  A PC trap is the only thing that can.
    """
    site = None
    for _ in range(8):
        h.run_until((DRAW_NARROW, DRAW_WIDE) + tuple(h.SENTINELS),
                    limit=10 ** 6, stride=1, interrupts=False)
        r = h.regs
        if r[PC] in (DRAW_NARROW, DRAW_WIDE):
            site = r[PC]
            h.step(1)
            continue
        break
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))
    return site


def patch_draws(m, nn):
    """ED 5F -> 3E nn at BOTH draw sites.  Two bytes for two, nothing moves."""
    for a in (DRAW_NARROW, DRAW_WIDE):
        m[a], m[a + 1] = 0x3E, nn


def unpatch_draws(m):
    for a in (DRAW_NARROW, DRAW_WIDE):
        m[a], m[a + 1] = 0xED, 0x5F


def stage(m, rnd, latch=0x00, lock=0x2A, water=0x00):
    m[ROUND] = rnd
    m[LATCH] = latch
    m[LOCK] = lock
    m[WATER] = water
    m[0x8CAE], m[0x8CAF] = 0x30, 0xC0
    for i in range(8):
        m[BLOCK + i] = 0
    m[0x9604] = 0x41
    m[0x9606] = 0x41


# --------------------------------------------------- the power-up type decision
def power_rows(h, m):
    rows = []
    listed = [m[LIST_AT + i] for i in range(LIST_N)]
    # every round that matters: the whole $8A62 list, its neighbours, 80, 81
    rounds = sorted(set(listed + [r + 1 for r in listed] + [r - 1 for r in listed]
                        + [1, 2, 0x4F, 0x50, 0x51]))
    for rnd in rounds:
        if not (1 <= rnd <= 0x51):
            continue
        for nn in (0x01, 0x03, 0x06, 0x07, 0x0D, 0x00, 0x02, 0x05):
            stage(m, rnd)
            patch_draws(m, nn)
            sp = arm(h, POWER, hl=LATCH)
            site = run(h, sp)
            rows.append({'round': rnd, 'nn': nn, 'site': site,
                         'type': m[BLOCK] & 0x0F, 'b0': m[BLOCK],
                         'after': {k: m[a] for k, a in WATCH.items()}})
    unpatch_draws(m)
    return rows


def wide_rows(h, m):
    """Every nn 0..255 on an UNLISTED round, so the exclusion polarity is pinned
       at n&15 = 1 (must survive) and n&15 = 3 (must become 0)."""
    rows = []
    for nn in range(256):
        stage(m, 10)                       # 10 is not in $8A62
        patch_draws(m, nn)
        sp = arm(h, POWER, hl=LATCH)
        site = run(h, sp)
        rows.append({'nn': nn, 'site': site, 'type': m[BLOCK] & 0x0F})
    unpatch_draws(m)
    return rows


def water_rows(h, m):
    """THE TYPE-7 REWRITE.  $8A4C CP 7 then $8A50 LD A,($7E0E) / CP 2 doubles a
       drawn 7 into 14 -- but ONLY on a water round.  Every other row in this
       fixture leaves $7E0E at 0, so "CP 2" and "CP 1" and "no test at all" are
       the same function; the value has to be swept.
    """
    rows = []
    for water in (0, 1, 2, 3):
        for nn in (0x07, 0x06, 0x02):
            stage(m, 10, water=water)
            patch_draws(m, nn)
            sp = arm(h, POWER, hl=LATCH)
            site = run(h, sp)
            rows.append({'water': water, 'nn': nn, 'site': site,
                         'type': m[BLOCK] & 0x0F})
    unpatch_draws(m)
    return rows


def lock_rows(h, m):
    """THE UMBRELLA LOCK as a THREE-CALL TRANSITION -- the only thing that tells
       "present but unfired" from "no lock at all"."""
    seq = []
    stage(m, 10, lock=0x2A)
    patch_draws(m, 0x06)
    for call in range(3):
        m[LATCH] = 0x00                    # re-arm the one-shot each time
        for i in range(8):
            m[BLOCK + i] = 0
        sp = arm(h, POWER, hl=LATCH)
        site = run(h, sp)
        seq.append({'call': call, 'site': site, 'type': m[BLOCK] & 0x0F, 'lock': m[LOCK]})
    unpatch_draws(m)
    return seq


# ------------------------------------------------------------- the flow gates
def flow_rows(h, m):
    rows = []
    for rnd in (1, 10, 0x4F, 0x50, 0x51):
        for t in (0x01FF, 0x0200, 0x02FF, 0x0300, 0x03FF, 0x0400, 0x04FF, 0x0500):
            for latch in (0x00, 0x01, 0x02, 0x03):
                stage(m, rnd, latch=latch)
                m[TIMER], m[TIMER + 1] = t & 0xFF, t >> 8
                patch_draws(m, 0x01)
                sp = arm(h, FLOW)
                site = run(h, sp)
                rows.append({'round': rnd, 'timer': t, 'latch': latch, 'site': site,
                             'after': {k: m[a] for k, a in WATCH.items()}})
    unpatch_draws(m)
    return rows


def points_rows(h, m):
    rows = []
    for l in (0, 1, 2, 3, 10, 11, 12, 13, 127, 255):
        stage(m, 10)
        m[0x9AE9] = l
        sp = arm(h, POINTS, hl=LATCH)
        run(h, sp)
        rows.append({'l': l, 'type': m[0x9605] & 0x0F, 'b0': m[0x9605]})
    return rows


def capture():
    h, m = new()
    fx = {'note': __doc__.strip(),
          'flow_at': FLOW, 'power_at': POWER, 'points_at': POINTS,
          'latch_at': LATCH, 'list_at': LIST_AT, 'excl_at': EXCL_AT,
          'lock_at': LOCK, 'block_at': BLOCK, 'watch': WATCH,
          'draw_sites': [DRAW_NARROW, DRAW_WIDE],
          'draw_patch': 'ED 5F (LD A,R) -> 3E nn (LD A,n), a DECLARED SUBSTITUTE',
          'list': [m[LIST_AT + i] for i in range(LIST_N)],
          'excl': [m[EXCL_AT + i] for i in range(EXCL_N)],
          'power': power_rows(h, m), 'wide': wide_rows(h, m),
          'lock': lock_rows(h, m), 'flow': flow_rows(h, m),
          'water': water_rows(h, m),
          'points': points_rows(h, m)}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d power rows, %d wide rows, %d lock calls, %d flow rows, %d points'
          % (FIXTURE, len(fx['power']), len(fx['wide']), len(fx['lock']),
             len(fx['flow']), len(fx['points'])))


def verify():
    fx = json.load(open(FIXTURE))
    lst = fx['list']
    print('THE $8A62 LIST:', ' '.join(str(b) for b in lst))
    print()
    print('WHICH DRAW EACH ROUND TAKES, forced nn = 1 (narrow gives 3, wide keeps 1):')
    for rnd in lst + [lst[-1] + 1, 10]:
        r = [x for x in fx['power'] if x['round'] == rnd and x['nn'] == 0x01]
        if not r:
            continue
        t = r[0]['type']
        print('   round %3d  type %2d  -> %s%s' % (rnd, t,
              'NARROW {3,3,4,5}' if t == 3 else 'WIDE',
              '   <-- LAST LIST ENTRY' if rnd == lst[-1] else ''))
    print()
    print('THE UMBRELLA LOCK, three calls each forcing a draw of 6:')
    for s in fx['lock']:
        print('   call %d -> type %2d, $8A76 = $%02X' % (s['call'], s['type'], s['lock']))
    print()
    print('THE POINTS-ITEM TYPE MAP:')
    for r in fx['points']:
        print('   $9AE9 = %3d -> type %2d' % (r['l'], r['type']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
