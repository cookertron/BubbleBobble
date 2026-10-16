# -*- coding: utf-8 -*-
"""M7.21 -- $917C, THE BORIS CHASE: a state machine whose entire state lives
inside instructions.

Once $9037's banner has fired, every later pass lands here through $904F's
`JP nz`.  SEVEN OPERANDS drive it and not one of them is a variable:

    $918B   the MOVING latch      ($918A LD A,n)
    $9194   a counter that starts at $AA and counts UP to its wrap
    $919C   a 0/1 toggle advanced only when $9194 wraps
    $91BC   the AXIS toggle, flipped when a move STARTS
    $91DC   the step countdown, loaded from (IY+4)
    $91E4   a 0..15 counter that ends the move
    $91D0   the operand of $91CF's own CP, a frame-change detector

...and $91F8/$921C, which $9037's tail wrote with the TARGET's +6 and +5.

It also HALTs ($91D4) and then draws Boris through $A447, so every call that
gets past the wait costs a frame.

Usage:  python tools/boris.py            (capture)
        python tools/boris.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/boris_fixture.json'
BRANCH_BYTE = 0x8DC4
TICK = 0x917C
TRIG = 0x9037
BORIS = 0x9250
THRESH = 0x745C
CLOCK = 0x8DBD
OPS = [(0x918B, 'moving'), (0x9194, 'counter'), (0x919C, 'toggle'),
       (0x91BC, 'axis'), (0x91DC, 'countdown'), (0x91E4, 'steps'),
       (0x91D0, 'framecmp')]
TARGET_Y, TARGET_X = 0x91F8, 0x921C
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
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def tick(h, where='', advance=True):
    """ONE $917C, with $91D4's HALT AND THE DRAW BEHIND IT STEPPED OVER.

    *** THE HALT CANNOT BE DRIVEN WITHOUT A SCAFFOLD, AND THE SCAFFOLD IS
    NAMED. ***  $91D4..$91DA is `HALT / DI / CALL $A447 / EI / RET`.
    With interrupts OFF the machine sits at the HALT for ever.  With them ON the
    real ISR runs, and on a world poked into the middle of a hurry it reaches the
    round advance and walks out of the bracket (MEASURED: the PC left at $9781).
    (M7.21 also blamed $A447 -- erasing at a garbage cached position -- for
    Boris's record coming back `FE 02 FE 04 FE 06 FE A8 FE 0A`.  CORRECTED
    M7.49: that is arm()'s OWN sentinels, pushed over $9250 once the SP leak
    below had walked the stack down to it (tick 116, SP $9251), with $91A3's
    bit 7 and $A447's bit 5 on +7.  With SP pinned the draw runs clean for all
    1,100 ticks, cache as poked -- phase (g) runs it.)

    So the probe steps from $91D4 straight to $91DA, over the HALT, the draw and
    its DI/EI, and COUNTS how many it stepped over.  What $A447 does to an entity
    is $A447's own fixture (entdraw.py, M7.7-H9) and what the ISR does is
    $8D72's; what is measured here is $917C's STATE MACHINE.  The frame counter
    is advanced by one per tick, which is the ISR's one observable effect the
    routine actually reads ($91CC)."""
    #  *** SP LEAKS TEN BYTES A CALL IF THE BRACKET IS NOT RESET. ***  arm()
    #  pushes six sentinels and the routine pops one, so a hundred and twenty-odd
    #  ticks walk the stack down through whatever is under it -- MEASURED, the
    #  PC left at $FE88, inside the RNG, which the routine never calls.  The
    #  entry SP is pinned on the first tick and restored on every one after.
    if not hasattr(h, '_borisSP'):
        h._borisSP = h.sim.registers[SP]
    h.sim.registers[SP] = h._borisSP
    arm(h, TICK)
    halts = 0
    n = 0
    while n < 2 * 10 ** 6:
        if h.regs[PC] == 0x91D4:
            halts += 1
            h.sim.registers[PC] = 0x91DA        # over the HALT, the DI/EI and $A447
            continue
        h.step(1, interrupts=False)
        if h.regs[PC] in h.SENTINELS:
            if advance:
                m = h.memobj.m
                c = ((m[CLOCK] | (m[CLOCK + 1] << 8)) + 1) & 0xFFFF
                m[CLOCK] = c & 0xFF
                m[CLOCK + 1] = (c >> 8) & 0xFF
            return halts
        n += 1
    raise SystemExit('bad bracket%s -- PC $%04X'
                     % ((' at ' + where) if where else '', h.regs[PC]))


def run(h, limit=8 * 10 ** 6, interrupts=False, where=''):
    """*** $91D4 IS A HALT, so the tick has to be driven WITH INTERRUPTS. ***
       With them off the machine sits there for ever and the bracket reports a
       PC from wherever the step limit left it.  The machine's own answer to a
       HALT is the frame interrupt, so that is what the probe supplies."""
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=interrupts)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket%s -- PC $%04X'
                         % ((' at ' + where) if where else '', h.regs[PC]))


def fired(state=STATE, clock=None, run_banner=False):
    """A machine on which $9037 has already fired, so $917C is what runs.

    *** THE BANNER IS POKED, NOT RUN. ***  $9037 costs 2,963,896 T and the
    harness single-steps, so running it six times to set one latch is twenty
    minutes of nothing.  The state it leaves was MEASURED in M7.19 -- the fired
    latch at $904D, the temper latch at $90AA, Boris's record and the two target
    operands -- so it is written directly, and `run_banner=True` runs the real
    thing ONCE so the two can be compared."""
    h, m = new(state)
    th = m[THRESH] | (m[THRESH + 1] << 8)
    c = (th + 1) if clock is None else clock
    m[0x8609] = 0x03
    m[CLOCK] = c & 0xFF
    m[CLOCK + 1] = (c >> 8) & 0xFF
    m[0x9049] = 0
    if run_banner:
        m[0x904D] = 0
        m[0x90AA] = 0
        arm(h, TRIG)
        run(h, limit=40 * 10 ** 6)
        return h, m, th
    m[0x904D] = 1                  # $9058 -- the banner has fired
    m[0x90AA] = 1                  # $90AD -- and the temper is spent
    m[0x9194] = 0x00               # $911A XOR A / LD ($9194),A -- the banner
                                   #   ZEROES it; the tape's $AA is a cold value
    m[0x918B] = 0                  # not moving
    m[0x919C] = 0
    #  $91BC is NOT touched by the banner, so it keeps whatever the state has
    m[BORIS + 9] = 8               # $9125
    m[BORIS + 8] = 0               # $9129
    m[BORIS + 5] = 0x18            # $912C
    m[BORIS + 6] = 0xA8            # $9130
    m[BORIS + 4] = 0x02            # $9134
    m[BORIS + 7] = 0x00            # NOT activated -- $91A3 is what does that
    m[TARGET_Y] = 0x86; m[TARGET_Y + 1] = 0xFD
    m[TARGET_X] = 0x85; m[TARGET_X + 1] = 0xFD
    return h, m, th


def phase_poke_matches_banner():
    """...and the poke IS the banner's own postcondition, run once to say so."""
    h1, m1, _ = fired(run_banner=True)
    h2, m2, _ = fired()
    keys = [0x904D, 0x90AA, 0x9194, 0x918B, 0x919C, 0x91BC,
            TARGET_Y, TARGET_Y + 1, TARGET_X, TARGET_X + 1] + [
            BORIS + i for i in range(4, 10)]
    diff = {'%04X' % a: [m1[a], m2[a]] for a in keys if m1[a] != m2[a]}
    print('(f) THE POKE vs THE REAL BANNER: %d of %d bytes differ %s'
          % (len(diff), len(keys), diff or ''))
    return {'checked': len(keys), 'differ': diff}


def snap(m):
    d = {n: m[a] for a, n in OPS}
    d['boris'] = [m[BORIS + i] for i in range(10)]
    d['ty'] = m[TARGET_Y] | (m[TARGET_Y + 1] << 8)
    d['tx'] = m[TARGET_X] | (m[TARGET_X + 1] << 8)
    #  ...and the BYTES those operands point at.  The trajectory is a chase, so
    #  the thing chased is part of the state: round1_48 has P1 at (24, 168) and a
    #  freshly reset port has (0, 0), which is a different chase entirely.
    d['tyv'] = m[d['ty']]
    d['txv'] = m[d['tx']]
    return d


# ---------------------------------------------------------------- (a) the wait
def phase_wait():
    """`LD HL,($745C) / LD DE,$01F4 / ADD HL,DE / SBC HL,DE' / RET nc` -- FIVE
       HUNDRED frames past the banner's own threshold, not past the banner."""
    h, m, th = fired()
    rows = []
    for extra in (0, 499, 500, 501, 600):
        h2, m2, _ = fired()
        c = (th + extra) & 0xFFFF
        m2[CLOCK] = c & 0xFF
        m2[CLOCK + 1] = (c >> 8) & 0xFF
        before = snap(m2)
        tick(h2, 'wait +%d' % extra)
        after = snap(m2)
        rows.append({'extra': extra, 'clock': c,
                     'moved': after['counter'] != before['counter'],
                     'counter': [before['counter'], after['counter']]})
    print('(a) WAIT: the tick does nothing until the clock passes ($745C) + 500 '
          '= %d' % (th + 500))
    for r in rows:
        print('      +%3d (clock %5d) -> %s  counter %d -> %d'
              % (r['extra'], r['clock'], 'RUNS' if r['moved'] else '-',
                 r['counter'][0], r['counter'][1]))
    return {'threshold': th, 'rows': rows}


# ------------------------------------------------------------ (b) the cascade
def arm_move(m):
    """Put the machine ONE TICK away from a move starting.

    $9195's `INC A` on $9194 is NZ on 255 calls out of 256, and $91A7's `JR nz`
    then sends the tick to the HALT; only when $9194 WRAPS does $919B's
    `INC A / AND 1` on $919C get a look in, and only when THAT lands on zero does
    $91A9 start a move.  So a move begins every FIVE HUNDRED AND TWELVE ticks --
    MEASURED, and the reason a 400-call cascade saw none.  Setting $9194 to $FF
    and $919C to 1 makes the next tick the one."""
    m[0x9194] = 0xFF
    m[0x919C] = 1


def phase_cascade(n=1100):
    """N calls in a row, recording every operand.  The state machine IS the
       trajectory, so the trajectory is the fixture."""
    h, m, th = fired()
    c = (th + 501) & 0xFFFF
    m[CLOCK] = c & 0xFF
    m[CLOCK + 1] = (c >> 8) & 0xFF
    traj = [snap(m)]
    halts = 0
    for i in range(n):
        halts += tick(h, 'cascade call %d' % i)
        traj.append(snap(m))
    starts = [i for i in range(1, len(traj))
              if traj[i]['moving'] == 1 and traj[i - 1]['moving'] == 0]
    activ = [i for i in range(1, len(traj))
             if (traj[i]['boris'][7] & 0x80) and not (traj[i - 1]['boris'][7] & 0x80)]
    print('(b) CASCADE over %d calls: %d HALTs; $9194 %d -> %d; '
          'moves START at '
          'calls %s; bit 7 of +7 set at %s'
          % (n, halts, traj[0]['counter'], traj[-1]['counter'],
             starts[:6], activ[:4]))
    print('    axis toggles: %s ; countdown seen: %s'
          % (sorted(set(t['axis'] for t in traj)),
             sorted(set(t['countdown'] for t in traj))[:8]))
    return {'n': n, 'halts': halts,
            'traj': traj, 'starts': starts, 'activated': activ}


# ------------------------------------------------------------- (c) the step
def phase_step():
    """One MOVE, step by step: eight pixels an axis, and which axis."""
    h, m, th = fired()
    c = (th + 501) & 0xFFFF
    m[CLOCK] = c & 0xFF
    m[CLOCK + 1] = (c >> 8) & 0xFF
    #  put Boris a long way from his target so the move runs its full length
    m[BORIS + 5] = 0x18
    m[BORIS + 6] = 0xA8
    m[0xFD85] = 0xC0          # the target X
    m[0xFD86] = 0x40          # the target Y
    arm_move(m)
    rows = []
    for i in range(60):
        before = snap(m)
        tick(h, 'step call %d' % i)
        after = snap(m)
        rows.append({'call': i,
                     'x': [before['boris'][5], after['boris'][5]],
                     'y': [before['boris'][6], after['boris'][6]],
                     'moving': [before['moving'], after['moving']],
                     'axis': after['axis'],
                     'sprite': [after['boris'][0], after['boris'][1]]})
    moved = [r for r in rows if r['x'][0] != r['x'][1] or r['y'][0] != r['y'][1]]
    dx = sorted(set((r['x'][1] - r['x'][0]) & 0xFF for r in moved))
    dy = sorted(set((r['y'][1] - r['y'][0]) & 0xFF for r in moved))
    print('(c) STEP: %d of 60 calls move him; dx %s dy %s; sprite after an X '
          'step %s' % (len(moved), dx, dy,
                       ['$%02X%02X' % (r['sprite'][1], r['sprite'][0])
                        for r in moved[:3]]))
    return {'rows': rows, 'moved': len(moved), 'dx': dx, 'dy': dy}


# ------------------------------------------------------------ (d) the target
def phase_target():
    """$91F8 and $921C are OPERANDS, so Boris chases whatever address $9037's
       tail put there -- and poking them makes him chase something else."""
    rows = []
    for ty, tx, name in ((0xFD86, 0xFD85, 'P1 (what the banner set)'),
                         (0xFD90, 0xFD8F, 'P2'),
                         (0x8609, 0x8609, 'the ROUND BYTE, which is not a player')):
        h, m, th = fired()
        c = (th + 501) & 0xFFFF
        m[CLOCK] = c & 0xFF
        m[CLOCK + 1] = (c >> 8) & 0xFF
        m[TARGET_Y] = ty & 0xFF
        m[TARGET_Y + 1] = ty >> 8
        m[TARGET_X] = tx & 0xFF
        m[TARGET_X + 1] = tx >> 8
        m[0xFD85] = 0xC0
        m[0xFD86] = 0x40
        m[0xFD8F] = 0x20
        m[0xFD90] = 0xB0
        m[BORIS + 5] = 0x80
        m[BORIS + 6] = 0x80
        arm_move(m)
        for i in range(40):
            tick(h, 'target call %d' % i)
        rows.append({'case': name, 'ty': ty, 'tx': tx,
                     'x': m[BORIS + 5], 'y': m[BORIS + 6]})
    print('(d) TARGET: forty calls with the operands pointed at different bytes')
    for r in rows:
        print('      %-38s -> Boris at (%d, %d)' % (r['case'], r['x'], r['y']))
    return rows


# --------------------------------------------------------- (e) the frame CP
def phase_framecmp():
    """$91CC `LD A,($8DBD) / CP n / LD ($91D0),A` -- the SAME self-modified
       compare $A824 uses, and here the result is thrown away: the routine HALTs
       either way.  Measured by driving it with the clock still and moving."""
    rows = []
    for advance, name in ((False, 'clock still'), (True, 'clock advancing')):
        h, m, th = fired()
        c = (th + 501) & 0xFFFF
        m[CLOCK] = c & 0xFF
        m[CLOCK + 1] = (c >> 8) & 0xFF
        seen = []
        for i in range(12):
            if advance:
                c = (c + 1) & 0xFFFF
                m[CLOCK] = c & 0xFF
                m[CLOCK + 1] = (c >> 8) & 0xFF
            tick(h, 'framecmp')
            seen.append(m[0x91D0])
        rows.append({'case': name, 'framecmp': seen})
    print('(e) $91D0: %s' % '; '.join('%s -> %s' % (r['case'], r['framecmp'][:8])
                                      for r in rows))
    return rows


# ------------------------------------------------ (g) the draw, and $A431
def tick_draw(h, rec, where=''):
    """ONE $917C with ONLY the HALT stepped over: $91D5 DI / $91D6 CALL $A447 / $91D9 EI run
    for real, and $A431 -- the operand of $A430 ADD A,n, the beam accumulator -- is read at the
    CALL and after it, with Boris's X and cached X.  (M7.49: $A447 makes its own $A430 adds
    wherever it is entered, and Boris's entry is in the MAIN LOOP, so no per-ISR gate sees it.)
    The entry SP is pinned exactly as tick() pins it -- that, and not the cache, is what keeps
    arm()'s sentinels off $9250 (see tick())."""
    if not hasattr(h, '_borisSP'):
        h._borisSP = h.sim.registers[SP]
    h.sim.registers[SP] = h._borisSP
    arm(h, TICK)
    m = h.memobj.m
    n, cur = 0, None
    while n < 2 * 10 ** 6:
        pc_ = h.regs[PC]
        if pc_ == 0x91D4:
            h.sim.registers[PC] = 0x91D5            # over the HALT only
            continue
        if pc_ == 0x91D6:
            cur = [m[BORIS + 5], m[BORIS + 3], m[BORIS + 2], m[0xA431]]
        if pc_ == 0x91D9 and cur is not None:
            rec.append(cur + [m[0xA431]])
            cur = None
        h.step(1, interrupts=False)
        if h.regs[PC] in h.SENTINELS:
            c = ((m[CLOCK] | (m[CLOCK + 1] << 8)) + 1) & 0xFFFF
            m[CLOCK] = c & 0xFF
            m[CLOCK + 1] = (c >> 8) & 0xFF
            return
        n += 1
    raise SystemExit('bad bracket%s -- PC $%04X' % ((' at ' + where) if where else '', h.regs[PC]))


BEAM_ARM = (8, 30, 52)                  # the ticks before which arm_move() starts a move


def phase_beam(n=76):
    """The cascade's world with Boris's cache made sane (cosmetic: +7 bit 6 is clear, so the first
    draw erases nothing and writes the cache itself -- MEASURED, every add is the same without
    it), n ticks with the draw run and a move
    armed before each tick in BEAM_ARM (so he walks both axes; X stays byte-aligned, 24 and 32 --
    he steps eight pixels -- so only the aligned erase and draw occur): every
    [X, cached X, cached Y, $A431 before, $A431 after] of $91D6 CALL $A447."""
    h, m, th = fired()
    c = (th + 501) & 0xFFFF
    m[CLOCK] = c & 0xFF
    m[CLOCK + 1] = (c >> 8) & 0xFF
    m[BORIS + 2] = m[BORIS + 6]
    m[BORIS + 3] = m[BORIS + 5]
    rec, per_tick = [], []
    for i in range(n):
        if i in BEAM_ARM:
            arm_move(m)
        k = len(rec)
        tick_draw(h, rec, 'beam call %d' % i)
        per_tick.append(len(rec) - k)
    adds = sorted(set(r[4] - r[3] & 0xFF for r in rec))
    classes = sorted(set((r[0] & 6, r[1] & 6) for r in rec))
    print('(g) BEAM: %d draws over %d ticks; $A431 adds per draw %s; (X&6, cached X&6) %s'
          % (len(rec), n, adds, classes))
    return {'n': n, 'arm': list(BEAM_ARM), 'per_tick': per_tick, 'draws': rec, 'adds': adds}


def capture(jobs=15):
    out = {}
    out['poke'] = phase_poke_matches_banner()
    out['wait'] = phase_wait()
    out['cascade'] = phase_cascade()
    out['step'] = phase_step()
    out['target'] = phase_target()
    out['framecmp'] = phase_framecmp()
    out['beam'] = phase_beam()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
