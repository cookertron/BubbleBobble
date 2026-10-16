# -*- coding: utf-8 -*-
"""M7.95 (measurement) -- THE TREASURE ROOM'S AWARD AND "PERFECT !" BLOCK IN TIME ($8F4C..$8F93).

$8E3A's treasure drain ($8F36) finds the item table empty and falls through $8F4A's JR nz into:

  $8F4C  DI / the tally compare / $8F66 LD ($FFEE),HL / LD A,1 / CALL $80FA / $8F6F LD ($FFEE),HL /
         LD A,2 / CALL $80FA / $8F77 EI           -- THE AWARD, interrupts OFF
  $8F78  LD B,0 / 256 x (PUSH BC / LD IX,$9A9F / LD HL,$484B / CALL $801D / LD HL,$594B / LD B,9 /
         LD A,$9E / CALL $994F / POP BC / DJNZ)  -- "PERFECT !", interrupts ON
  $8F92  XOR A / RET                              -- to $8D61 (JR z: the round advance)

tools/cost8e3a.py measured the block's total (natural 1,754,419 T from $8E3A's entry on lastdia81 /
lastdia82); this oracle measures it WRITE BY WRITE and IN TIME, from $8F4C's DI:

WORLDS, each reached as a saved state AT $8F4C (the DI not yet run):
  natural   lastdia81, lastdia82 -- ab38cost's key script, UNCONTENDED (cost8e3a's own runs), to the
            first $8F4C.
  forced    round1_48 / round1_2p48 run (contended, interrupts on) to $8D5E (the CALL $8E3A), then
            ($8E3B) = 0, ($FED1) = 1, the 31 item entries zero, plus the award's pokes (the tallies
            $FDE2 / $FDEC for the lead / tie / trail compare; the scores and the high score for the
            copy / abandon and the digit counts), then on to $8F4C -- declared in FORCED below.

RUNS from each world's $8F4C:
  exact     a plain Simulator, fast_djnz / fast_ldir OFF, no contention, interrupts OFF, to the
            return at $8D61: the T stamps (from $8F4C) of the DI's end, each $80FA call and return,
            the EI's end, $8F78, the first two iterations' $801D and $994F entries, the iteration
            period (ASSERTED the same for all 256), the RET's landing; every write OUTSIDE THE STACK
            with its instruction's start T: the award's (before $8F78) as [address, T] -- the
            digits' glyphs come from the ROM charset, so NO VALUE is kept, addresses only -- the
            first iteration's as [address, T from its PUSH BC], and the count and a digest
            ('address@T;') of the whole stream.  The SEED (revealentry's): every byte of $4000..
            read before written, as [start, hex] runs, and the ADDRESSES alone of the ROM reads
            (TRAPS #281).
  contended natural worlds at the reach phase and sixteen phases 4,368 apart, plus four that put a
            frame boundary inside the award's DI window; the forced 'r1_lead' at the reach phase:
            contended, interrupts ON, to the return.  Every accepted interrupt [T, its ISR's wall T,
            ($FEC4), ($FEC5), the branch it takes (odd/even: ($8DBD)+1's bit 0)], every DI window,
            every frame boundary and whether it was LOST (no interrupt accepted in [b, b+32)); the
            MAIN-LINE T (wall less the ISRs) at the EI's end, $8F78, every iteration's PUSH BC and
            the return; and THE PREMISE: what the ISRs inside wrote of the bytes the block writes,
            and read of them (counts by kind).

No ROM byte is stored: T counts, addresses and counts.  $D000..$D2FF is never executed (guarded).

Usage:  python tools/perfecttime.py capture [--jobs N]   (-> build/perfecttime_fixture.json, N <= 6)
        python tools/perfecttime.py verify  [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, Mem, PC, T, SP, IFF
import portconfig as pc
import revealentry as R
import ab38cost as B

FIXTURE = 'build/perfecttime_fixture.json'
FRAME_T = 69888
INT_T = 32
GUARD = set(range(0xD000, 0xD300))
DI_AT, AWARD, EI_AT, LOOP, ITER, DRAW, RUNS, BACK = 0x8F4C, 0x80FA, 0x8F77, 0x8F78, 0x8F7A, 0x801D, 0x994F, 0x8D61
PHASES = [k * (FRAME_T // 16) for k in range(16)]
# frame boundaries inside the award's DI window (~9,500 T on the natural worlds)
DI_PHASES = [FRAME_T - d for d in (40, 2000, 5000, 9000)]

ITEMS = [(0x9605 + 2 * i, 0) for i in range(31)]
BASE = [(0x8E3B, 0), (0xFED1, 1)] + ITEMS
FORCED = [
    # (name, state, pokes) -- the award's compare and paths
    ('r1_lead', 'round1_48', [(0xFDE2, 6), (0xFDEC, 2)]),
    ('r1_tie', 'round1_48', [(0xFDE2, 4), (0xFDEC, 4)]),
    ('r1_trail', 'round1_48', [(0xFDE2, 1), (0xFDEC, 7)]),
    ('p2_lead', 'round1_2p48', [(0xFDE2, 9), (0xFDEC, 3)]),
    ('p2_trail', 'round1_2p48', [(0xFDE2, 0), (0xFDEC, 5)]),
    ('p2_tie_high', 'round1_2p48', [(0xFDE2, 2), (0xFDEC, 2)] + [(0xFFE1 + i, 0) for i in range(4)]),
    # P1's new score EQUAL to the high score in all four bytes: the compare runs out and falls into the copy
    ('p2_equal', 'round1_2p48', [(0xFDE2, 7), (0xFDEC, 1), (0xFFE1, 0), (0xFFE2, 0), (0xFFE3, 0x01), (0xFFE4, 0),
                                 (0xFFE5, 0), (0xFFE6, 0), (0xFFE7, 0), (0xFFE8, 0),
                                 (0xFFE9, 0), (0xFFEA, 0), (0xFFEB, 0), (0xFFEC, 0)]),
    # eight-digit scores: no leading zero, the high score above both (abandoned at the first step)
    ('p2_full', 'round1_2p48', [(0xFDE2, 3), (0xFDEC, 8), (0xFFE1, 0x99), (0xFFE2, 0x99), (0xFFE3, 0x99),
                                (0xFFE4, 0x99), (0xFFE5, 0x34), (0xFFE6, 0x12), (0xFFE7, 0x56), (0xFFE8, 0x78),
                                (0xFFE9, 0x10), (0xFFEA, 0x32), (0xFFEB, 0x54), (0xFFEC, 0x76)]),
]
NATURAL = ['lastdia81', 'lastdia82']


class Fail(Exception):
    pass


def reach(job):
    """the world AT $8F4C as a saved state"""
    name = job
    if name in NATURAL:
        h = Harness(contended=False)
        h.load_state_file(pc.state_path(name))
        r, raw, sim = h.sim.registers, h.memobj.m, h.sim
        assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
        fd, ia = h.frame_duration, h.int_active
        t0 = r[T]
        ki, nextk = 0, r[T]
        while True:
            if r[T] >= nextk:
                h.ports.release_all()
                for kt in (0xB5FD, 0xB605):
                    for j, c in enumerate('LRJB'):
                        sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                        if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                            if sel == 0x1F:
                                h.ports.kempston |= mask
                            else:
                                h.ports.press(sel, 0xFF & ~mask)
                ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
            p = r[PC]
            if p in GUARD:
                raise Fail('guard')
            if p == DI_AT:
                break
            if raw[p] == 0x76 and r[IFF]:
                h._fast_halt()
                continue
            sim.opcodes[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                sim.accept_interrupt(r, sim.memory, p)
            if r[T] - t0 > 300 * fd:
                raise Fail(name + ': no $8F4C in 300 frames')
        h.ports.release_all()
        return {'name': name, 'state': h.save_state(), 'how': 'natural', 'frames': round((r[T] - t0) / fd, 3),
                'phase': r[T] % fd}
    f = [x for x in FORCED if x[0] == name][0]
    h = R.new(f[1])
    r, m = h.sim.registers, h.memobj.m
    t0 = r[T]
    R.go(h, {0x8D5E: lambda hh: True}, 4 * FRAME_T)
    for a, v in BASE + f[2]:
        m[a] = v
    R.go(h, {DI_AT: lambda hh: True}, 2 * FRAME_T)
    return {'name': name, 'state': h.save_state(), 'how': 'forced', 'frames': round((r[T] - t0) / FRAME_T, 3),
            'phase': r[T] % FRAME_T}


def exact(st):
    h = R.new('round1_48')
    h.load_state(st)
    rm = R.SeedMem(h.memobj.m)
    h.memobj = rm
    m0 = bytes(rm.m)
    R.plain(h)
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    if r[PC] != DI_AT:
        raise Fail('exact: at $%04X' % r[PC])
    t0 = r[T]
    sp0 = r[SP]
    if mem[sp0] | (mem[sp0 + 1] << 8) != BACK:
        raise Fail('exact: the return is not $8D61')
    rm.regs = r
    st_, its, draws, runs, aw = {}, [], [], [], []
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if p == BACK and r[SP] == sp0 + 2:
            st_['ret'] = r[T] - t0
            break
        if p == AWARD:
            aw.append([r[T] - t0, r[SP]])
        if aw and aw[-1][1] is not None and len(aw[-1]) == 2 and p in (0x8F6E, 0x8F77) and r[SP] == aw[-1][1] + 2:
            aw[-1].append(r[T] - t0)
        if p == LOOP:
            st_['loop'] = r[T] - t0
        if p == ITER:
            its.append(r[T] - t0)
        if p == DRAW:
            draws.append(r[T] - t0)
        if p == RUNS:
            runs.append(r[T] - t0)
        iff = r[IFF]
        rm.tins[0] = r[T]
        sim.opcodes[mem[p]]()
        if iff and not r[IFF]:
            st_['di_end'] = r[T] - t0
        if not iff and r[IFF]:
            st_['ei_end'] = r[T] - t0
        if r[T] - t0 > 3 * 10 ** 6:
            raise Fail('exact: no return')
    rm.regs = None
    if len(its) != 256 or len(draws) != 256 or len(runs) != 256:
        raise Fail('exact: %d / %d / %d iterations' % (len(its), len(draws), len(runs)))
    per = its[1] - its[0]
    if any(its[k + 1] - its[k] != per for k in range(255)) or \
       any(draws[k] - its[k] != draws[0] - its[0] or runs[k] - its[k] != runs[0] - its[0] for k in range(256)):
        raise Fail('exact: the iterations are not periodic')
    sd = R.seed_of(rm, m0, t0)
    wr = [(a, t - t0) for a, t in rm.wr]
    loop = st_['loop']
    aw_w = [[a, t] for a, t in wr if t < loop]
    it_w = [[a, t - its[0]] for a, t in wr if its[0] <= t < its[1]]
    for k in range(256):                       # every iteration writes the same addresses at the same offsets
        w = [[a, t - its[k]] for a, t in wr if its[k] <= t < (its[k + 1] if k < 255 else st_['ret'])]
        if w != it_w:
            raise Fail('exact: iteration %d writes differ' % k)
    stamps = dict(st_)
    stamps.update({'iter0': its[0], 'period': per, 'draw0': draws[0] - its[0], 'runs0': runs[0] - its[0],
                   'awards': [[a[0], a[2] if len(a) > 2 else None] for a in aw]})
    return {'stamps': stamps, 'award_writes': aw_w, 'iter_writes': it_w, 'n_writes': len(wr),
            'digest': hashlib.sha1(''.join('%d@%d;' % (a, t) for a, t in wr).encode('ascii')).hexdigest()[:16],
            'seed': sd}


class IsrMem(Mem):
    """the contended run's memory: the ISRs' reads and writes of the bytes the block writes"""
    __slots__ = ('inisr', 'blk', 'disp', 'n')

    def __init__(self, data, blk):
        Mem.__init__(self, data)
        self.inisr = False
        self.blk = blk
        self.n = {'isr_w_blk': 0, 'isr_r_blk': 0, 'isr_w_blk_disp': 0, 'isr_r_blk_disp': 0,
                  'isr_w_disp': 0, 'isr_r_803c': 0}
        self.disp = None

    def __getitem__(self, i):
        if self.inisr and type(i) is int:
            if i in self.blk:
                self.n['isr_r_blk'] += 1
                if i < 0x5B00:
                    self.n['isr_r_blk_disp'] += 1
            if i in (0x803C, 0x803D):
                self.n['isr_r_803c'] += 1
        return self.m[i]

    def __setitem__(self, i, v):
        if self.inisr:
            if 0x4000 <= i < 0x5B00:
                self.n['isr_w_disp'] += 1
            if i in self.blk:
                self.n['isr_w_blk'] += 1
                if i < 0x5B00:
                    self.n['isr_w_blk_disp'] += 1
        Mem.__setitem__(self, i, v)


def contended(args):
    st, phase, blk = args
    h = R.new('round1_48')
    h.load_state(st)
    rm = IsrMem(h.memobj.m, set(blk))
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports); rm.sim = h.sim
    r, sim, mem = h.sim.registers, h.sim, rm
    fd, ia = h.frame_duration, h.int_active
    if phase is not None:
        r[T] = (r[T] // fd) * fd + phase
    t0 = r[T]
    sp0 = r[SP]
    accepts, wins, its = [], [], []
    isr = []
    excl = 0
    di_t, ei_pending = None, False
    marks = {}
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        while isr and p == isr[-1][0] and r[SP] == isr[-1][1]:
            top = isr.pop()
            w = r[T] - top[2]
            accepts[top[3]][1] = w
            if not isr:
                excl += w
                rm.inisr = False
        if not isr:
            if p == BACK and r[SP] == sp0 + 2:
                marks['ret'] = r[T] - t0 - excl
                break
            if p == LOOP:
                marks['loop'] = r[T] - t0 - excl
            if p == ITER:
                its.append(r[T] - t0 - excl)
        if mem.m[p] == 0x76:
            raise Fail('a HALT inside the block')
        iff = r[IFF]
        sim.opcodes[mem.m[p]]()
        if not isr:
            if ei_pending and r[IFF]:
                wins.append([di_t, r[T] - t0])
                marks['ei_main'] = r[T] - t0 - excl
                ei_pending, di_t = False, None
            if iff and not r[IFF] and di_t is None:
                di_t = r[T] - t0
            if not iff and r[IFF] and di_t is not None:
                ei_pending = True
        if r[IFF] and r[T] % fd < ia:
            tb, spb = r[T], r[SP]
            g4, g5, odd = mem.m[0xFEC4], mem.m[0xFEC5], (mem.m[0x8DBD] + 1) & 1
            if sim.accept_interrupt(r, mem, p):
                # an ISR that re-enables and overruns the frame is interrupted itself: NESTED (its
                # wall T inside its parent's), flagged by a sixth field
                accepts.append([tb - t0, None, g4, g5, odd] + ([1] if isr else []))
                isr.append((mem.m[r[SP]] | (mem.m[(r[SP] + 1) & 0xFFFF] << 8), spb, tb, len(accepts) - 1))
                rm.inisr = True
        if r[T] - t0 > 40 * FRAME_T:
            raise Fail('contended: no end')
    tend = r[T] - t0
    first = fd - (t0 % fd)
    bounds = list(range(first, tend, fd))
    acc_t = [a[0] for a in accepts]
    lost = [b for b in bounds if not any(b <= a < b + INT_T for a in acc_t)]
    rule = [b for b in bounds if any(w[0] <= b and b + INT_T <= w[1] for w in wins)]
    return {'phase0': t0 % fd, 'forced': phase is not None, 'wall': tend, 'main': marks['ret'],
            'ei_main': marks.get('ei_main'), 'loop_main': marks['loop'], 'iters': its,
            'isrs': accepts, 'windows': wins, 'bounds': bounds, 'lost': lost, 'rule_lost': rule,
            'premise': dict(rm.n)}


def capture(jobs=6):
    names = NATURAL + [f[0] for f in FORCED]
    with ProcessPoolExecutor(jobs) as ex:
        reached = list(ex.map(reach, names))
    with ProcessPoolExecutor(jobs) as ex:
        exacts = list(ex.map(exact, [x['state'] for x in reached]))
    work, who = [], []
    for x, e in zip(reached, exacts):
        blk = sorted(set(a for a, t in e['award_writes']) | set(a for a, t in e['iter_writes']))
        phs = [None] + (PHASES + DI_PHASES if x['how'] == 'natural' else [])
        if x['how'] == 'forced' and x['name'] != 'r1_lead':
            continue
        for ph in phs:
            work.append((x['state'], ph, blk)); who.append(x['name'])
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(contended, work))
    out = {'meta': {'phases': PHASES, 'di_phases': DI_PHASES, 'int_t': INT_T,
                    'forced': [[f[0], f[1], f[2]] for f in FORCED]}, 'worlds': {}}
    for x, e in zip(reached, exacts):
        rows = [c for c, n in zip(res, who) if n == x['name']]
        out['worlds'][x['name']] = {'how': x['how'], 'frames_to_reach': x['frames'], 'reach_phase': x['phase'],
                                    'exact': e, 'contended': rows}
    return out


def report(out):
    for n, w in out['worlds'].items():
        e = w['exact']; s = e['stamps']
        print('%-12s %-7s reach %.2f fr ph %5d | exact ret %d di_end %s ei_end %s loop %d iter0 %d period %d '
              'draw0 %d runs0 %d awards %s | writes %d (award %d, iter %d)' % (
                  n, w['how'], w['frames_to_reach'], w['reach_phase'], s['ret'], s.get('di_end'), s.get('ei_end'),
                  s['loop'], s['iter0'], s['period'], s['draw0'], s['runs0'], s['awards'], e['n_writes'],
                  len(e['award_writes']), len(e['iter_writes'])))
        for c in w['contended']:
            K = (c['main'] - c['loop_main']) / (s['ret'] - s['loop'])
            print('   %s ph %5d wall %d main %d (K loop %.6f, award main %s) isrs %d lost %s rule %s wins %s gates %s prem %s' % (
                'F' if c['forced'] else 'N', c['phase0'], c['wall'], c['main'], K, c['ei_main'], len(c['isrs']),
                c['lost'], c['rule_lost'], c['windows'],
                sorted(set((a[2] > 0, a[3] > 0) for a in c['isrs'])), c['premise']))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    jobs = 6
    if '--jobs' in sys.argv:
        jobs = min(6, int(sys.argv[sys.argv.index('--jobs') + 1]))
    t = time.time()
    out = json.loads(json.dumps(capture(jobs)))
    report(out)
    if cmd == 'capture':
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(out, f, separators=(',', ':'))
        print('wrote %s (%.1f s)' % (FIXTURE, time.time() - t))
    elif cmd == 'verify':
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        if old == out:
            print('MATCH (%.1f s)' % (time.time() - t))
        else:
            bad = [k for k in old['worlds'] if old['worlds'][k] != out['worlds'].get(k)]
            print('DIFF in %s (%.1f s)' % (bad or 'meta', time.time() - t))
            sys.exit(1)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
