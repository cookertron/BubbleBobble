"""$B520 -- the ROUND-TRANSITION SETTLER, and the $AA6E divert that reaches it.

Every round opens with ($B54B) ticks in which $AA60 does NOT dispatch anything:
$AA6E reads the byte, $AA72 JP nz,$B520 leaps over $AA81 LD IY,$FD80, and slot 0
is P1 -- so the abandoned loop's first two entries are the PLAYERS.  Nobody moves
except by this ramp, which walks each enemy's (IY+6) DOWN toward the row the
spawner parked in $73A6, at up to two pixels a tick.

$9877 arms it: $58 = 88 ticks, or $14 = 20 on round 1.  It ticks on the ODD ISR
only, so 88 ticks is 176 VIDEO FRAMES.

WHY THE OBVIOUS WORLD CANNOT GATE THIS.  Three degeneracies stack on a captured
round, and any one of them alone would make a green gate meaningless:

  - an enemy's ordinary FALL is also (Y+2), at $B079, and also on the odd ISR.
    Sampling enemy Y on a mid-round capture is byte-identical with $B520 deleted.
  - the one steady mid-settle capture has every enemy already AT its target, so
    "ramp", "clamp" and "do nothing" are the same function there.
  - round 1's targets are all equal, so "stop at the first arrival" and "walk
    every slot" agree as well.

So the world is BUILT: spawn a round through $727B (which zeroes every +6 and
fills $73A6) and leave the enemies ASLEEP, so that with ($B54B) = 0 nothing moves
at all and the two models diverge on the very first tick.  Then add the rows no
round can produce -- an ODD Y against an ODD target, and a Y already BELOW its
target, which walks up through 255 because both INCs are eight-bit and there is
no clamp.

Usage:  python tools/settle.py capture
        python tools/settle.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IYh, IYl
import portconfig as pc

SETTLE = 0xB520
PASS = 0xAA60
SPAWN = 0x727B
TABLE, STRIDE = 0xFD80, 10
TARGETS = 0x73A6
COUNT_A = 0xAA57
B54B = 0xB54B
FIXTURE = 'build/settle_fixture.json'
BRANCH_BYTE = 0x8DC4
ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
SP0 = [0]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{state}: not the 48K branch (TRAPS #28/#36)')
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, iy, a=None):
    """point the machine at `addr` from a FIXED stack pointer (TRAPS #42).

       `a` matters here: $B520's FIRST instruction is DEC A, operating on the A
       that $AA6E's LD A,($B54B) left behind.  A direct call that forgets it
       writes garbage into $B54B and produces a whole sweep of plausible nonsense.
    """
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[IYh], r[IYl] = iy >> 8, iy & 0xFF
    if a is not None:
        r[0] = a & 0xFF
    r[PC] = addr


def run(h):
    h.run_until(tuple(h.SENTINELS), limit=10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('no sentinel -- PC $%04X' % h.regs[PC])
    return h.SENTINELS.index(h.regs[PC])


LOOP_TOP = 0x8D25          # the main-loop top, $8D25-$8D5E


def spawn_world(h, m, round_no, resume=False):
    """a freshly spawned round: every enemy at Y = 0, its real row in $73A6, and
       a wake-up delay so that with $B54B = 0 NOTHING moves on the first tick.

       `resume` puts the machine back on its feet afterwards.  A direct call
       leaves PC parked on a SENTINEL ($FE00..), which is game DATA -- free-run
       from there and the Z80 executes bytes that are not code until an interrupt
       happens to rescue it.  That is how a 200-frame window came back with
       $FEC6 frozen: the ISR never ran at all.
    """
    m[0x8609] = round_no
    m[0x73AF] = 0
    arm(h, SPAWN, TABLE)
    run(h)
    if resume:
        h.sim.registers[12] = SP0[0]
        h.sim.registers[PC] = LOOP_TOP


def cases():
    """(round, b54b, mutate) -- `mutate` pokes the rows no round can produce"""
    out = []
    for r in (1, 2, 4, 10, 20):
        for b in (0x58, 0x14, 2, 1):
            out.append((r, b, None))
    # an ODD Y against an ODD target: the only way to reach $B53F, the compare
    # BETWEEN the two INCs.  $7336 zeroes Y and every target is byte1 AND $F8,
    # so both are always even in play and "+2" is indistinguishable from
    # "+1 then check".
    for dy in (0, 1, 2, 3):
        for dt in (0, 1):
            out.append((4, 0x58, ('odd', dy, dt)))
    # ONE PIXEL SHORT, which is what makes the second INC conditional visible:
    # the routine compares AGAIN after the first, so an enemy at target - 1
    # finishes on ONE pixel, not two.  Reaching it needs the parity of Y and
    # target to differ, and in play both are always even.
    for d in (1, 3):
        for parity in (0, 1):
            out.append((4, 0x58, ('short', d, parity)))
    # a Y already BELOW its target: no clamp, both INCs eight-bit, so it walks
    # up through 255 and wraps rather than settling
    for y in (250, 254, 255, 0):
        out.append((4, 0x58, ('above', y, 0)))
    # one slot already AT its target in the MIDDLE of the list, so a model that
    # stopped at the first arrival differs from one that walks them all
    out.append((10, 0x58, ('mid', 0, 0)))
    # the slot geometry: $AA57 - 2, not 12
    for n in (2, 3, 4, 5, 8):
        out.append((10, 0x58, ('count', n, 0)))
    return out


def capture_calls():
    """table A: $B520 alone, one call per row, over the built world"""
    h, m = new()
    rows = []
    for (round_no, b54b, mut) in cases():
        spawn_world(h, m, round_no)
        m[B54B] = b54b
        if mut:
            kind, a, b = mut
            if kind == 'odd':
                m[TABLE + 2 * STRIDE + 6] = a
                m[TARGETS] = (m[TARGETS] + b) & 0xFF
            elif kind == 'above':
                m[TABLE + 2 * STRIDE + 6] = a
                m[TARGETS] = 8
            elif kind == 'short':
                # place slot 2 exactly `a` pixels above its target
                m[TABLE + 2 * STRIDE + 6] = (m[TARGETS] - a) & 0xFF
                if b:
                    m[TARGETS] = (m[TARGETS] + 1) & 0xFF
                    m[TABLE + 2 * STRIDE + 6] = (m[TARGETS] - a) & 0xFF
            elif kind == 'mid':
                m[TABLE + 3 * STRIDE + 6] = m[TARGETS + 1]
            elif kind == 'count':
                m[COUNT_A] = a
        before = [m[TABLE + i] for i in range(120)]
        tg = [m[TARGETS + i] for i in range(12)]
        arm(h, SETTLE, TABLE, a=m[B54B])       # A = ($B54B): $B520 opens with DEC A
        sent = run(h)
        rows.append({'round': round_no, 'b54b': b54b, 'mut': list(mut) if mut else None,
                     'count': m[COUNT_A], 'targets': tg, 'before': before,
                     'after': [m[TABLE + i] for i in range(120)],
                     'b54b_after': m[B54B],
                     'targets_after': [m[TARGETS + i] for i in range(12)],
                     'sentinel': sent})
    return rows


def capture_window():
    """table B: the WHOLE window, frame by frame, with a MOVEMENT KEY HELD.

       The freeze is the discriminator that enemy bytes cannot give -- the
       machine abandons the players with the enemies, and the port ran them
       anyway.  But a player that was never asked to move is frozen either way,
       so each armed window is paired with a CONTROL at $B54B = 0 and the same
       key.  If the control does not move the player, the armed window proves
       nothing and the capture says so.

       round1_48 was set up with the CURSOR keys, so P1's table at $B5FD is
       F7/10 ('5', left), EF/04 ('8', right), EF/01, EF/08 -- see the type-4
       work.  Holding EF/04 walks P1 right.
    """
    h, m = new()
    out = []
    # round_no None means "do not spawn at all": use round1_48 exactly as it is,
    # a real mid-round state where the port's own player physics works.  That is
    # the only world where the FREEZE is observable from the engine side -- on a
    # bare spawn P1 sits at (0,0) on a round whose platforms the port does not
    # carry, and it does not move whether it is frozen or not.
    for (round_no, armed) in ((1, True), (4, True), (10, True),
                              (1, False), (4, False), (10, False),
                              (None, True), (None, False)):
        if round_no is None:
            h2, m2 = new()
            h.sim.registers[:] = h2.sim.registers[:]
            m[:] = m2[:]
        else:
            spawn_world(h, m, round_no, resume=True)
        m[B54B] = 0 if not armed else (0x14 if round_no == 1 else 0x58)
        m[0xFEC4] = 0x14
        h.ports.pressed = {}
        h.ports.press(0xEF, 0xFF & ~0x04)          # hold '8' -- P1 right
        frames = []
        for f in range(200):
            h.run_until((ISR_IN,), limit=10 ** 7, stride=1)
            h.step(1)
            h.run_until((ISR_OUT,), limit=10 ** 7, stride=1)
            h.step(1)
            frames.append({'b54b': m[B54B], 'fec6': m[0xFEC6], 'aa65': m[0xAA65],
                           # the ISR's PARITY lives here, and it decides which
                           # frames tick the settler at all -- seed it or the
                           # engine's window is a tick out
                           'par': m[0x8DBD], 'par_hi': m[0x8DBE],
                           'slots': [m[TABLE + i] for i in range(120)]})
            if round_no is None and f >= 40:
                break
            if armed and m[B54B] == 0 and f > 8:
                break
            if not armed and f >= 40:
                break
        h.ports.pressed = {}
        out.append({'round': round_no if round_no is not None else 0,
                    'live': round_no is None,
                    'armed': armed, 'key': [0xEF, 0x04],
                    'b54b0': 0 if not armed else (0x14 if round_no == 1 else 0x58),
                    'targets': [m[TARGETS + i] for i in range(12)],
                    'count': m[COUNT_A], 'frames': frames})
    return out


def capture():
    h, m = new()
    calls = capture_calls()
    win = capture_window()
    fx = {'note': __doc__.strip(),
          'settle_at': SETTLE, 'pass_at': PASS, 'table_at': TABLE,
          'targets_at': TARGETS, 'count_at': COUNT_A, 'b54b_at': B54B,
          'stride': STRIDE, 'calls': calls, 'windows': win}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d direct calls, %d windows (%s frames)'
          % (FIXTURE, len(calls), len(win), '/'.join(str(len(w['frames'])) for w in win)))


def verify():
    fx = json.load(open(FIXTURE))
    moved = sum(1 for r in fx['calls']
                if any(r['before'][10 * k + 6] != r['after'][10 * k + 6] for k in range(12)))
    print('calls: %d, of which some enemy Y moved: %d' % (len(fx['calls']), moved))
    for w in fx['windows']:
        f0, f1 = w['frames'][0], w['frames'][-1]
        pmoved = any(f0['slots'][i] != f1['slots'][i] for k in (0, 1)
                     for i in (10 * k + 5, 10 * k + 6))
        print('  round %-2d %-7s %3d frames, $B54B %3d -> %3d, P1 moved: %s'
              % (w['round'], 'ARMED' if w['armed'] else 'control',
                 len(w['frames']), f0['b54b'], f1['b54b'], pmoved))
    ctl = [w for w in fx['windows'] if not w['armed']]
    ok = all(any(w['frames'][0]['slots'][i] != w['frames'][-1]['slots'][i]
                 for i in (5, 6)) for w in ctl)
    print('  the CONTROLS move P1 (so the freeze is a real observation):', ok)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
