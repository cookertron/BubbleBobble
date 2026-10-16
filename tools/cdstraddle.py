# -*- coding: utf-8 -*-
"""M7.106 -- THE ROUND-CLEAR COUNTDOWN'S ADVANCE, AND THE INTERRUPT INSIDE ITS PASS.

$8E3A, latched ($8E3B non-zero) after a round's one-shot clear, ends every pass with the countdown
$8F29 LD A,($8DBE) / DEC A / RET nz / $8F2E LD A,($8DBD) / CP $77 / RET c / XOR A / RET -- the round
advances ($8D61 JR z,$8D09 -> CALL $97F8) on the first READ that finds the play timer at $0177.  The
timer is the ISR's ($8D72 INC ($8DBD)), so the advance comes in the pass whose $8F2E read is the first
after the interrupt that makes $0177 -- and a pass is ~6,000 T against a frame's 69,888, so that pass
usually STRADDLES the interrupt (started before it, reads after it).  M7.97 found it on the giant's
through-runs (giantspawn 'zero': $A824's last entry a frame before $9855's clear); the port's pass is
atomic, so its read saw the old timer and the advance came one pass later (TRAPS #90).

'runs': WORLDS x the clear made K = 0..KS-1 frames after the load, no keys, contended, interrupts on:
every walked enemy's +7 bit 7 cleared (the round cleared, as giantspawn's through-runs do), run to the
$97F8 entry.  Per run, on the machine's T clock:
  b        the frame boundary (a multiple of the frame) of the interrupt that made the timer $0177
  isr      [accept T, the ISR's T to its return] of that interrupt
  pass     T of the advancing pass's $8D0C (the last before $97F8)
  e3a      T of its $8E3A entry (the CALL done), hi / lo: T of its $8F29 / $8F2E (instruction starts)
  vals     [($8DBE), ($8DBD)] as $8F29 / $8F2E read them
  entry    T of $97F8
  isr_in   the T of ISRs between pass and lo (wall T the main line did not run)
  prev     [T of the previous pass's $8F2E, the value pair it read] -- the read that did NOT advance
Derived (asserted): the advancing read is the FIRST to find $0177, and the interrupt's boundary falls
before it: b <= lo.  'straddle' = pass < b (the pass began in the frame before).
The rule the port carries (M7.106): the countdown's read sees the interrupt iff its boundary is at or
before the read's instruction start (b <= lo: an instruction that ends past the boundary is finished
first -- the harness accepts at instruction ends, as M7.105 measured for a DI).

GUARDED: every run stops with an error if PC enters $D000..$D2FF.  Nothing below $4000 is stored.

Usage:  python tools/cdstraddle.py [measure] [--jobs N]   (-> build/cdstraddle_fixture.json)
        python tools/cdstraddle.py verify [--jobs N]      (re-measure, compare, say MATCH)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
from harness import Harness, PC, T, SP, IFF
from harness import A as RA
import portconfig as pc

FIXTURE = 'build/cdstraddle_fixture.json'
WORLDS = ['round1_48', 'r6_48', 'r10_48', 'r20_48', 'r30_48']
KS = 6
GLO, GHI = 0xD000, 0xD300
TOP, E3A, HI, LO, ENTRY = 0x8D0C, 0x8E3A, 0x8F29, 0x8F2E, 0x97F8
LIMIT = 520                                       # frames to the advance (375 from the clear)


def run(job):
    world, k = job
    h = Harness()
    h.load_state_file(pc.state_path(world))
    sim, r = h.sim, h.sim.registers
    mem, op = sim.memory, sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    h.ports.release_all()
    assert mem[0x8DC4] == 0xC9, world + ': not a 48K state'
    h.run_frames(k)
    n = (mem[0xAA57] - 2) & 0xFF or 256
    for i in range(n):
        a = (0xFD9B + 10 * i) & 0xFFFF
        mem[a] &= 0x7F
    t0 = r[T]
    isrs = []                                     # [boundary, accept T, duration or None, value after]
    in_isr = None                                 # (sp, return pc, index)
    reads = []                                    # [T, pc, value] of $8F29 / $8F2E (A after the load)
    pend = None
    tops, e3as = [], []
    while True:
        p = r[PC]
        assert not (GLO <= p < GHI), 'ENTERED THE GUARDED RANGE'
        assert r[T] - t0 < LIMIT * fd, world + ' k%d: no advance in %d frames' % (k, LIMIT)
        if in_isr and p == in_isr[1] and r[SP] == in_isr[0]:
            isrs[in_isr[2]][2] = r[T] - isrs[in_isr[2]][1]
            isrs[in_isr[2]][3] = mem[0x8DBD] | mem[0x8DBE] << 8
            in_isr = None
        if pend is not None:
            reads.append([pend[0], pend[1], r[RA]])  # A, after the load
            pend = None
        if in_isr is None:
            if p == ENTRY:
                break
            if p == TOP:
                tops.append(r[T])
            elif p == E3A:
                e3as.append(r[T])
            elif p in (HI, LO):
                pend = (r[T], p)
        if mem[p] == 0x76 and r[IFF]:
            sp0, ret = r[SP], (p + 1) & 0xFFFF
            h._fast_halt()                        # to the boundary, and the interrupt accepted there
            assert r[SP] != sp0 and in_isr is None
            isrs.append([(r[T] // fd) * fd, r[T], None, None])
            in_isr = (sp0, ret, len(isrs) - 1)
            continue
        op[mem[p]]()
        if r[IFF] and r[T] % fd < ia:
            sp0, ret = r[SP], r[PC]
            if sim.accept_interrupt(r, mem, p):
                assert in_isr is None, 'a nested interrupt'
                isrs.append([(r[T] // fd) * fd, r[T], None, None])
                in_isr = (sp0, ret, len(isrs) - 1)
    entry = r[T]
    lo = [x for x in reads if x[1] == LO]
    hi = [x for x in reads if x[1] == HI]
    first = next(i for i, x in enumerate(lo) if x[2] >= 0x77 and
                 [y for y in hi if y[0] < x[0]][-1][2] == 1)
    assert first == len(lo) - 1, 'the advance is not the first read to find $0177'
    a_lo, a_hi = lo[-1], hi[-1]
    pass_t = max(t for t in tops if t < a_lo[0])
    e3a = max(t for t in e3as if t < a_lo[0])
    assert a_hi[0] > pass_t and e3a > pass_t
    mk = [x for x in isrs if x[3] == 0x0177]
    assert len(mk) == 1, 'one interrupt makes $0177'
    b, acc, dur, _ = mk[0]
    isr_in = sum(x[2] for x in isrs if pass_t <= x[1] < a_lo[0])
    prev = lo[-2] if len(lo) > 1 else None
    prev_hi = [y for y in hi if prev and y[0] < prev[0]][-1] if prev else None
    assert b <= a_lo[0], 'the read before its interrupt'
    assert prev is None or prev[0] < acc, 'a read after the interrupt that did not advance'
    return {'world': world, 'k': k, 'b': b, 'isr': [acc, dur], 'pass': pass_t, 'e3a': e3a,
            'hi': a_hi[0], 'lo': a_lo[0], 'vals': [a_hi[2], a_lo[2]], 'entry': entry, 'isr_in': isr_in,
            'prev': [prev[0], [prev_hi[2], prev[2]]] if prev else None,
            'straddle': pass_t < b, 'torn': a_hi[0] < b}


def measure(jobs):
    jl = [(w, k) for w in WORLDS for k in range(KS)]
    with Pool(jobs) as pool:
        rows = pool.map(run, jl)
    return {'note': __doc__.split('\n')[0], 'worlds': WORLDS, 'ks': KS, 'runs': rows}


def report(F):
    rs = F['runs']
    print('runs %d, straddling %d, torn %d' % (len(rs), sum(x['straddle'] for x in rs), sum(x['torn'] for x in rs)))
    for x in rs:
        ml = x['lo'] - x['pass'] - x['isr_in']
        print('  %-10s k%d  b-pass %6d  lo-pass(main line) %5d  e3a->lo %3d  lo-b %6d  entry-lo %4d  %s'
              % (x['world'], x['k'], x['b'] - x['pass'], ml, x['lo'] - x['e3a'], x['lo'] - x['b'],
                 x['entry'] - x['lo'], 'STRADDLE' if x['straddle'] else ''))


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
