# -*- coding: utf-8 -*-
"""THE PAUSE'S SPIN ON THE FRAME CLOCK -- where the pass that $8FE7 suspended resumes.

$8FE7 (chain entry $8D28) arms on SYM SHIFT: $8FF6 DI, $8FF9 OUT ($FE),4, then the spin
$8FFB LD A,$FE / IN A,($FE) / RRA / JR c,$8FFB until CAPS SHIFT is down, then $9002 XOR A / OUT /
POP AF / CALL $8E0A (RET on 48K) / $9009 EI / RET -- and the chain goes on at $8D2B (CALL $900B).
M7.13 measured what it does (tools/pausegate.py); the port charged its polls nothing and resumed the
pass at T 0 of the release frame (DECLARED in TIMING.md).  This measures WHERE, on the frame clock:

'runs': WORLDS x the arm K = 0..KS-1 frames after the load x N paused frames, contended, interrupts
on; and 'late' runs (FORCED: the arming $8FE7 put LATE T before a boundary by moving the clock,
nothing else -- no natural run's DI falls past its interrupt).  Keys change at frame boundaries (multiples of the frame on the T clock) after the instruction
that crosses one, as run_frames leaves them: SYM from boundary b0 (with CAPS too in mode 'both');
from the first boundary after the spin is reached nothing (N > 0) or CAPS (N = 0); CAPS from the
boundary bc = that one + N frames; nothing a frame after.  Per run, T on the machine's clock:
  top    the last $8D0C before the spin (the arming pass)    c25    its $8D25 (CALL $8FA5)
  e7     its $8FE7 (the CALL done)                          di     its $8FF6 DI
  h      the spin's head $8FFB, first reached               rin    the releasing poll's IN ($8FFD)
  res    $8D2B (the $900A RET's end), the chain                 isrs   [boundary, accept T, T to RET] top..
  outs   [$8FF9 OUT ($FE),4, $9003 OUT ($FE),0] -- instruction starts
  next   the boundary of the first interrupt taken after res (a lost one is a frame later)
  polls  polls run (the $8FFB visits)                       e7h    h - e7 (wall T: an ISR may fall in it)
The poll train is checked in the tool against the model the port carries (pred()): a poll is 34 T,
the IN's I/O cycle 15 T in (8 into the IN) contended by the ULA (BB_ULA's rule); the release poll is the first whose
IN starts at or after bc.  ASSERTED per run: no ISR is accepted between the spin and $8D2B (the INT at
bc is lost -- EI comes 70+ T past it), and pred() gives every poll start, rin and res exactly.

GUARDED: every run stops with an error if PC enters $D000..$D2FF.  Nothing below $4000 is stored.

Usage:  python tools/pausespin.py [measure] [--jobs N]   (-> build/pausespin_fixture.json)
        python tools/pausespin.py verify [--jobs N]      (re-measure, compare, say MATCH)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
from harness import Harness, PC, T, SP, IFF
import portconfig as pc

FIXTURE = 'build/pausespin_fixture.json'
WORLDS = ['round1_48', 'r6_48', 'r10_48', 'r20_48', 'r30_48', 'boss']
KS = 6
NS = [0, 1, 3]
GLO, GHI = 0xD000, 0xD300
TOP, C25, GATE, DI, HEAD, IN_PC, RESUME = 0x8D0C, 0x8D25, 0x8FE7, 0x8FF6, 0x8FFB, 0x8FFD, 0x8D2B
SYM, CAPS = (0x7F, 0xFD), (0xFE, 0xFE)
ULA_FROM, ULA_LINE, ULA_LINES, ULA_OPEN = 14335, 224, 192, 128
POLL, IN_OFF, IN_IO = 34, 7, 15
LATE = [40, 70, 84, 85, 86, 87, 88, 89, 90, 95, 100, 110]
LATE_BOTH = [100, 150, 170, 180, 181, 182, 183, 184, 190, 200, 210]


def ula(t, fd):
    """BB_ULA's delay at frame phase t (web/game.js bbUlaDelay)"""
    t %= fd
    t -= ULA_FROM
    if t < 0 or t >= ULA_LINE * ULA_LINES:
        return 0
    x = t % ULA_LINE
    if x >= ULA_OPEN:
        return 0
    p = x & 7
    return 6 - p if p < 6 else 0


def pred(h, bc, fd, upto=None):
    """the poll starts from the head h to the release poll (its IN at or after bc)"""
    s, starts = h, []
    while True:
        starts.append(s)
        if s + IN_OFF >= bc:
            return starts
        s += POLL + ula(s + IN_IO, fd)


def keys(hh, ks):
    hh.ports.release_all()
    for sel, v in ks:
        hh.ports.press(sel, v)


def run(job):
    world, k, n, mode = job[:4]
    late = job[4] if len(job) > 4 else None
    h = Harness()
    h.load_state_file(pc.state_path(world))
    sim, r = h.sim, h.sim.registers
    mem, op = sim.memory, sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    assert mem[0x8DC4] == 0xC9, world + ': not a 48K state'
    keys(h, [])
    b0 = (r[T] // fd + 1 + k) * fd
    sched = [(b0, [SYM, CAPS] if mode == 'both' else [SYM])]
    isrs, in_isr = [], None
    tops, c25s, e7s, dis, polls, ins, outs = [], [], [], [], [], [], {}
    hd = bc = res = None
    forced = False
    t_start = r[T]
    while True:
        p = r[PC]
        assert not (GLO <= p < GHI), 'ENTERED THE GUARDED RANGE'
        assert r[T] - t_start < (k + n + 14) * fd, '%s k%d n%d: no resume' % (world, k, n)
        if in_isr and p == in_isr[1] and r[SP] == in_isr[0]:
            isrs[in_isr[2]][2] = r[T] - isrs[in_isr[2]][1]
            in_isr = None
        if in_isr is None:
            if p == TOP and hd is None:
                tops.append(r[T])
            elif p == C25 and hd is None:
                c25s.append(r[T])
            elif p == GATE and hd is None:
                if late is not None and r[T] >= b0 and not forced:
                    r[T] = (r[T] // fd + 1) * fd - late     # FORCED: $8FE7 'late' T before a boundary
                    forced = True
                e7s.append(r[T])
            elif p == DI and hd is None:
                dis.append(r[T])
            elif p == HEAD:
                if hd is None:
                    hd = r[T]
                    b1 = (hd // fd + 1) * fd
                    bc = b1 + n * fd
                    if mode == 'both':
                        bc = b0                    # CAPS is down from the arm's own boundary
                    else:
                        sched = [x for x in sched if x[0] > hd]
                        if n:
                            sched.append((b1, []))
                        sched.append((bc, [CAPS]))
                        sched.append((bc + fd, []))
                    sched.sort()
                polls.append(r[T])
            elif p == IN_PC:
                ins.append(r[T])
            elif p in (0x8FF9, 0x9003) and (hd is None) == (p == 0x8FF9):
                outs[p] = r[T]                     # the arm's OUT ($FE),4 and the release's OUT ($FE),0 (starts)
        if mem[p] == 0x76 and r[IFF]:
            sp0, ret = r[SP], (p + 1) & 0xFFFF
            h._fast_halt()
            isrs.append([(r[T] // fd) * fd, r[T], None])
            in_isr = (sp0, ret, len(isrs) - 1)
            if res is not None:
                break
        else:
            op[mem[p]]()
            if p == 0x900A and hd is not None and res is None:
                res = r[T]                         # $900A RET done: $8D2B on the main line
                keys(h, [])                        # nothing re-arms: the next interrupt is this pause's
                sched = []
            if r[IFF] and r[T] % fd < ia:
                sp0, ret = r[SP], r[PC]
                if sim.accept_interrupt(r, mem, p):
                    assert in_isr is None, 'a nested interrupt'
                    isrs.append([(r[T] // fd) * fd, r[T], None])
                    in_isr = (sp0, ret, len(isrs) - 1)
                    if res is not None:
                        break
        while sched and r[T] >= sched[0][0]:
            keys(h, sched.pop(0)[1])
    top, c25, e7, di = tops[-1], c25s[-1], e7s[-1], dis[-1]
    assert top < c25 < e7 < di < hd
    rin = ins[-1]
    nb, nacc, _ = isrs.pop()
    nxt = nb                               # the boundary of the first interrupt taken after $8D2B
    isr_in = [x for x in isrs if x[1] >= top]
    assert not [x for x in isr_in if x[1] > hd], 'an ISR between the spin and $8D2B'
    assert nacc >= res
    if mode != 'both':
        assert bc > hd
    want = pred(hd, bc, fd)
    assert polls == want, '%s k%d n%d: the poll train is not the model (first off at %d)' % (
        world, k, n, next(i for i, (a, b) in enumerate(zip(polls, want)) if a != b) if len(polls) == len(want) else -1)
    assert rin == want[-1] + IN_OFF
    return {'world': world, 'k': k, 'n': n, 'mode': mode, 'late': late, 'b0': b0, 'top': top, 'c25': c25, 'e7': e7, 'di': di, 'h': hd,
            'bc': bc, 'rin': rin, 'res': res, 'polls': len(polls), 'isrs': isr_in, 'next': nxt, 'outs': [outs[0x8FF9], outs[0x9003]], 'e7h': hd - e7}


def measure(jobs):
    jl = [(w, k, n, 'cut') for w in WORLDS for k in range(KS) for n in NS] + \
         [(w, k, 0, 'both') for w in WORLDS for k in range(KS)] +          [(w, 0, n, 'late', d) for w in WORLDS[:3] for n in (0, 1) for d in LATE] +          [(w, 0, 0, 'both', d) for w in WORLDS[:3] for d in LATE_BOTH]
    with Pool(jobs) as pool:
        rows = pool.map(run, jl)
    return {'note': __doc__.split('\n')[0], 'worlds': WORLDS, 'ks': KS, 'ns': NS,
            'model': {'poll': POLL, 'in_off': IN_OFF, 'in_io': IN_IO}, 'runs': rows}


def report(F):
    rs = F['runs']
    print('runs %d' % len(rs))
    for x in rs:
        fd = 69888
        print('  %-10s k%d n%d %-4s  e7 ph %5d  h-e7 %3d  h ph %5d  isr(top..) %d  rin-bc %3d  res-rin %3d  polls %6d'
              % (x['world'], x['k'], x['n'], x['mode'], x['e7'] % fd, x['e7h'], x['h'] % fd, len(x['isrs']),
                 x['rin'] - x['bc'], x['res'] - x['rin'], x['polls']))


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 6
    cmd = a[0] if a and not a[0].startswith('--') else 'measure'
    F = measure(jobs)
    report(F)
    if cmd == 'verify':
        old = json.load(open(FIXTURE))
        print('MATCH' if old == json.loads(json.dumps(F)) else 'DIFFER')
    else:
        json.dump(F, open(FIXTURE, 'w'), indent=1)
        print('->', FIXTURE)


if __name__ == '__main__':
    main()
