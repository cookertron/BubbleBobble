"""$97F8 -- the ROUND ADVANCE, and the $9AC1 nineteen-address reset.

Reached from the main loop at $8D09 once $8E3A has answered Z.  This oracle
covers the ARITHMETIC HEAD only, $97F8..$9857: everything from there on builds
the new level and scrolls it in, which is increment (h).

    $97F8  ($8609)++            ; and if that reaches $52 -- past round 81 --
    $97FF                        ; the round becomes ($FEC7), the LOOKAHEAD
    $9809  look = ($8609) + 1   ; and if THAT would be $52, look is drawn from
    $9811                        ; LD A,R / AND $1F / ADD $1E, i.e. 30..61
    $9817  ($FEC7) = look
    $981A  look == $15, $29 or $3D -- 21, 41, 61 -- is the MILESTONE:
    $982A    both players gain a life, (IX+$5C) and (IX+$66) from $FD80
    $9830    then pick the first player whose +$5A bit 7 is CLEAR, P1 before P2;
    $983E    if BOTH are set, nothing more happens
    $9840    and if that player is ALIVE (+7 bit 7), ($8609) := $51 -- the WARP
    $984B  then walk the $9AC1 table and zero all NINETEEN bytes it names

SPEC SAID the milestone fires "advancing INTO round 21/41/61".  It fires when
the LOOKAHEAD is 21/41/61, and $9817 stores the lookahead before $981A tests it
-- so ($8609) is 20/40/60 at that moment.  Both descriptions are of one fact;
this one names the register.

WHAT THIS ORACLE MUST NOT ASSUME.  The nineteen bytes are seeded to $FF, not 0,
or "zero them" and "leave them alone" are the same function.  And the table is
walked out of the image rather than hard-coded, so a wrong address is visible.

$9811 is BB_RNG_SITES' RETURN_ROUND, marked "TRANSCRIBED, never observed
executing".  It executes here, so the draws are trapped and recorded.

Usage:  python tools/advance.py capture
        python tools/advance.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

ADVANCE = 0x97F8
STOP = 0x9858                 # after the nineteen-byte clear, before the build
RNG_CP = 0x9813               # the AND $1F right after $9811's LD A,R
TABLE = 0xFD80
RESET_TAB = 0x9AC1
FIXTURE = 'build/advance_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

# the bytes the head reads or writes, beyond the nineteen the table names
WATCH = {'8609': 0x8609, 'FEC7': 0xFEC7, 'FDDC': 0xFDDC, 'FDE6': 0xFDE6,
         'FDDA': 0xFDDA, 'FDE4': 0xFDE4, 'FD87': 0xFD87, 'FD91': 0xFD91}


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{state}: not the 48K branch (TRAPS #28/#36)')
    SP0[0] = h.sim.registers[12]
    return h, m


def reset_addrs(m):
    return [m[RESET_TAB + 2 * i] | (m[RESET_TAB + 2 * i + 1] << 8) for i in range(19)]


def run_head(h):
    """$97F8 to $9858, trapping the RETURN_ROUND draw on the way.

       There are no CALLs and no HALT before $9858 -- the HALT is at $9887, well
       past the stop -- so this runs with interrupts off and needs no sentinels:
       the ADDRESS reached is the bracket.
    """
    r = h.sim.registers
    r[12] = SP0[0]
    r[PC] = ADVANCE
    draws = []
    for _ in range(8):
        h.run_until((RNG_CP, STOP), limit=10 ** 6, stride=1, interrupts=False)
        if h.regs[PC] != RNG_CP:
            break
        draws.append({'site': 0x9811, 'tag': 0, 'A': h.regs[0] & 0x7F})
        h.step(1)
    if h.regs[PC] != STOP:
        raise SystemExit('did not reach $%04X -- PC $%04X' % (STOP, h.regs[PC]))
    return draws


def cases():
    """(round, fec7, p1state, p2state, p1flags, p2flags, lives1, lives2)

       The warp truth table is the point of the state/flags sweep: $9830 picks
       the first player whose +$5A bit 7 is CLEAR, P1 before P2, and warps only
       if THAT player is alive.  All four combinations, both alive and dead.
    """
    out = []
    # the milestones, and the rounds either side of each
    for r in (1, 2, 18, 19, 20, 21, 38, 39, 40, 41, 58, 59, 60, 61, 0x4F, 0x50):
        out.append((r, 0x20, 0x00, 0x00, 0xC0, 0xC0, 3, 3))
    # the WRAP: round $51 advances to $52, which becomes ($FEC7)
    for fec7 in (0x1E, 0x20, 0x3D, 0x51):
        out.append((0x51, fec7, 0x00, 0x00, 0xC0, 0xC0, 3, 3))
    # ...and the round whose LOOKAHEAD would be $52, which draws from LD A,R
    for fec7 in (0x20, 0x3D):
        out.append((0x50, fec7, 0x00, 0x00, 0xC0, 0xC0, 3, 3))
    # THE WARP TRUTH TABLE.  The milestone tests the LOOKAHEAD, and the lookahead
    # is ($8609) + 1 AFTER the advance -- so a lookahead of 21 means entering
    # with 19, not 20.  (Getting that wrong gives sixteen rows that all answer
    # "no warp" and look like a settled truth table.)
    for p1s in (0x00, 0x80):
        for p2s in (0x00, 0x80):
            for p1f in (0x40, 0xC0):
                for p2f in (0x40, 0xC0):
                    out.append((19, 0x20, p1s, p2s, p1f, p2f, 3, 3))
    # the lives INC, including its eight-bit wrap
    for lv in (0, 1, 5, 0xFE, 0xFF):
        out.append((19, 0x20, 0x00, 0x00, 0xC0, 0xC0, lv, lv))
    # the other two milestones, so 41 and 61 are not taken on trust from 21
    for r in (39, 59):
        for p1s in (0x00, 0x80):
            for p2s in (0x00, 0x80):
                out.append((r, 0x20, p1s, p2s, 0xC0, 0xC0, 3, 3))
    # a non-milestone round with the same player states, so the warp cannot fire
    for p1s in (0x00, 0x80):
        out.append((10, 0x20, p1s, 0x00, 0xC0, 0xC0, 3, 3))
    return out


def capture():
    h, m = new()
    addrs = reset_addrs(m)
    rows = []
    for (rnd, fec7, p1s, p2s, p1f, p2f, lv1, lv2) in cases():
        m[0x8609] = rnd
        m[0xFEC7] = fec7
        m[0xFDDA] = p1s
        m[0xFDE4] = p2s
        m[TABLE + 7] = p1f
        m[TABLE + 10 + 7] = p2f
        m[0xFDDC] = lv1
        m[0xFDE6] = lv2
        # $FF, not 0: with the targets already zero, "zero them" and "leave them
        # alone" would be the same function
        for a in addrs:
            m[a] = 0xFF
        before = {k: m[a] for k, a in WATCH.items()}
        draws = run_head(h)
        rows.append({'round': rnd, 'fec7': fec7, 'p1s': p1s, 'p2s': p2s,
                     'p1f': p1f, 'p2f': p2f, 'lv1': lv1, 'lv2': lv2,
                     'before': before, 'draws': draws,
                     'after': {k: m[a] for k, a in WATCH.items()},
                     'reset': [m[a] for a in addrs]})
    fx = {'note': __doc__.strip(), 'advance_at': ADVANCE, 'stop_at': STOP,
          'reset_tab': RESET_TAB, 'reset_addrs': addrs,
          'reset_bytes': [m[RESET_TAB + i] for i in range(38)],
          'watch': WATCH, 'table_at': TABLE, 'rows': rows}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d calls, %d that warped, %d that drew RETURN_ROUND'
          % (FIXTURE, len(rows),
             sum(1 for r in rows if r['after']['8609'] == 0x51
                 and ((r['round'] + 1) & 0xFF) != 0x51),
             sum(1 for r in rows if r['draws'])))


def verify():
    fx = json.load(open(FIXTURE))
    R = fx['rows']
    print('rows %d' % len(R))
    print('  the nineteen reset targets, all zero on every row:',
          all(all(v == 0 for v in r['reset']) for r in R))
    print('  the milestone (lookahead 21/41/61) and the life it grants:')
    for r in R[:16]:
        gave = r['after']['FDDC'] != r['before']['FDDC']
        print('    $8609 %3d -> %3d   $FEC7 -> %3d   life %s   warp %s'
              % (r['round'], r['after']['8609'], r['after']['FEC7'],
                 'YES' if gave else '-', 'YES' if r['after']['8609'] == 0x51 else '-'))
    print('  the warp truth table at round 19 (lookahead 21):')
    for r in R:
        if r['round'] == 19 and r['lv1'] == 3:
            print('    P1 $5A=%02X +7=%02X  P2 $5A=%02X +7=%02X  ->  $8609 %02X %s'
                  % (r['p1s'], r['p1f'], r['p2s'], r['p2f'], r['after']['8609'],
                     'WARP' if r['after']['8609'] == 0x51 else ''))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
