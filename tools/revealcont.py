# -*- coding: utf-8 -*-
"""THE REVEAL'S CONTENTION, ACCESS BY ACCESS (M7.99c).  $8C28 entered after a DI ($9031 / $A11B) runs with
interrupts OFF to its own $8C4C EI, so the frame interrupts it loses are decided by where that EI falls --
the reveal's CONTENDED T from the entry's frame phase.  M7.57's model stretched each routine's exact T by one
fitted K, which is the machine's on average and not at a phase: the machine's window is 248,010..258,242 T by
the phase (revealentry_fixture), the K model's 252,246 at every one, and on r50_48 / r10_48 at phase 26,208
and after round 1's odd ISR the machine loses a fourth interrupt the K model does not.

THE MEASUREMENT: SkoolKit's CMIOSimulator contends an instruction by its list of (address, T) accesses: an
access to $4000..$7FFF at frame T t waits DELAYS_48K[t % 69888] (6,5,4,3,2,1,0,0 over the first 128 T of each
of the 192 display lines from 14,335).  So the reveal's contended T is fixed by its CONTENDED ACCESSES -- each
one's exact (uncontended) T -- and the entry's phase:  t_i = phase + a_i + D_(i-1),  D_i = D_(i-1) + delay(t_i),
and a point at exact T e lands at e + D (the delays of the accesses before it).
  prog      a plain run (no delay, every access logged) from the entry's DI to the reveal's RET: the exact T
            of every access to $4000..$7FFF (data, the digits' own code at $7F80.., the OUT's ULA cycle), split
            by the routine it falls in (BB_RV_SCRIPT's hooks), each as offsets from its routine's hook --
            count and digest ('o;o;...' sha1[:16]); the reveal's hooks on the exact clock.
  machine   the CMIOSimulator, interrupts off (the entry DIs), from the entry at the phase to the RET: every
            hook's contended T, $8C4C's EI end and the RET's; and the write stream outside the stack, count
            and digest of 'address@T;' (T the writing instruction's start on the contended clock).  The replay of `prog` at the phase must give
            every one of them EXACTLY, or the tool stops (Fail).
  SOURCES   $9031 on r50_48 / r10_48 (revealentry.py's reach), at the free run's phase and the sixteen forced
            phases 4,368 apart; $A11B on the umbrella's five runs (umbrella.py's reach and free run), each of
            the five reveals at the machine's own phase (after the HALT's ISR) and the sixteen forced.
            VARIANTS of the r50_48 source ('pokes' at $9031, and 'extra': the bytes the variant reads that
            the base run does not, values at $9031, >= $4000 only) put the panel's letters and the lives rows
            where no world has them: the EXTEND masks, the lives counts and player 2 in play, and a lives
            row over a paper already its ink ($80E0's JR z taken: the derive's colours poked).
  digits    $7F80 alone (CALLed, a sentinel return) with ($8609) = 0..100: its points (its code is in
            contended memory: every fetch) by the round -- count, digest, exact T.
  panel     $957E alone with ($FDE3) = m, ($FDED) = 0 and the reverse, m = 0..63: count, digest, exact T.

  flash     (M7.99d) the umbrella's later flashes: $A121 DI / POP BC / DJNZ / PUSH BC / LD DE / CALL $A0E0, the
            flash, $A119 EI -- interrupts OFF from the DI to the HALT, so the same replay times them: each of
            the 20 turns (umbrella.py's five runs, turns 2..5) from its own phase (after the HALT's ISR) and the
            sixteen forced, its routines' programs (u_turn from the start, u_flash from $A0E0, u_ei from
            $A119) and every mark ($A0E0, $A119, the EI's end, the HALT) and write, EXACT, or the tool stops.

NO ROM BYTE IS STORED: T counts, offsets, addresses, digests; the variants' extra bytes are >= $4000.
GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/revealcont.py measure [--jobs N]  -> build/revealcont_fixture.json
        python tools/revealcont.py verify  [--jobs N]  re-run and diff against the fixture (MATCH)
"""
import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import Mem, PC, T, SP, IFF
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import revealentry as RE
import umbrella as UMB

FIXTURE = 'build/revealcont_fixture.json'
FRAME_T = 69888
PHASES = [k * (FRAME_T // 16) for k in range(16)]
GUARD = set(range(0xD000, 0xD300))
REVEAL = 0x8C28
HOOKS = {0x8216: 'repaint', 0x7F80: 'digits', 0x8C2B: 'derive', 0x957E: 'panel', 0x806C: 'lives', 0x8C4C: 'out'}
ROUTINES = ['release', 'repaint', 'digits', 'derive', 'panel', 'lives', 'out']
# the r50_48 $9031 source's variants: (name, pokes) -- the EXTEND letters ($FDE3 / $FDED), the lives counts
# ($FDDC / $FDE6) and the players' in-play flags ($FD87 / $FD91 bit 7)
VARIANTS = [
    ('p1_all', [(0xFDE3, 0x3F), (0xFDED, 0x00), (0xFDDC, 7), (0xFD91, 0x80), (0xFDE6, 1)]),
    ('mixed', [(0xFDE3, 0x15), (0xFDED, 0x2A), (0xFDDC, 0), (0xFD91, 0x80), (0xFDE6, 4)]),
    ('p2_all', [(0xFDE3, 0x00), (0xFDED, 0x3F), (0xFD87, 0x00), (0xFD91, 0x80), (0xFDE6, 5)]),
    # the derive's colours ($8309 / $830A) with paper 4, player 1's ink: every lives cell's $80E0 JR z taken
    ('same_ink', [(0x8309, 0x27), (0x830A, 0x27), (0xFD91, 0x80), (0xFDE6, 2)]),
]


class Fail(Exception):
    pass


def digest(pts):
    return hashlib.sha1(';'.join(str(o) for o in pts).encode('ascii')).hexdigest()[:16]


class ReadMem(Mem):
    """the bytes read before written (>= $4000 kept as an input set; not the instruction's own bytes)"""
    __slots__ = ('seen', 'rd', 'regs')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.seen, self.rd, self.regs = set(), set(), None

    def __getitem__(self, i):
        if self.regs is not None and type(i) is int and i not in self.seen:
            p = self.regs[PC]
            if not (p <= i < p + 4):
                self.seen.add(i)
                self.rd.add(i)
        return self.m[i]

    def __setitem__(self, i, v):
        if self.regs is not None:
            self.seen.add(i)
        Mem.__setitem__(self, i, v)


class WriteMem(Mem):
    """every write outside the stack with its instruction's start T (revealentry's rule: SP +- 64 is the stack)"""
    __slots__ = ('wr', 'regs', 'tins')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.wr, self.regs, self.tins = [], None, [0]

    def __setitem__(self, i, v):
        if self.regs is not None:
            sp = self.regs[SP]
            if not (sp - 64 <= i < sp + 64):
                self.wr.append((i, self.tins[0]))
        Mem.__setitem__(self, i, v)


def sim_of(h, log=None, mem=None):
    """a CMIOSimulator over the harness's registers; with `log`, no delay and every contended access logged"""
    regs = list(h.sim.registers)
    if mem is not None:
        h.memobj = mem
    sim = CMIOSimulator(h.memobj, config={})
    sim.registers[:] = regs
    if log is not None:
        sim.t0, sim.t1 = -1, FRAME_T + 1

        def contend(t, timings):
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    log.append(t)
                t += ts
            return 0
        sim.contend = contend
    h.sim = sim
    h.memobj.sim = sim
    return sim


def run_reveal(st, phase=None, log=None, pokes=(), rmem=False):
    """from the entry (the DI) to the reveal's RET: marks [(name, T from the entry)]; with a phase also the
    write stream outside the stack as (count, digest of 'address@T;' with T the writing instruction's start)"""
    h = RE.new('round1_48')
    h.load_state(st)
    for a, v in pokes:
        h.memobj.m[a] = v
    rm = ReadMem(h.memobj.m) if rmem else (WriteMem(h.memobj.m) if phase is not None else None)
    sim = sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    t0 = r[T]
    if rm is not None:
        rm.regs = r
    marks, sp0, ret, prev = [['release', 0]], None, None, None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if p == REVEAL and sp0 is None:
            sp0, ret = r[SP], mem[r[SP]] | (mem[r[SP] + 1] << 8)
        if sp0 is not None and p == ret and r[SP] == sp0 + 2:
            marks.append(['ret', r[T] - t0])
            break
        if p in HOOKS and prev != p and sp0 is not None:
            marks.append([HOOKS[p], r[T] - t0])
        iff = r[IFF]
        if rm is not None and not rmem:
            rm.tins[0] = r[T]
        sim.opcodes[mem[p]]()
        if not iff and r[IFF]:
            marks.append(['ei_end', r[T] - t0])
        prev = p
        if r[T] - t0 > 10 ** 6:
            raise Fail('no return from the reveal')
    if rm is not None:
        rm.regs = None
    if rm is not None and not rmem:
        s = ''.join('%d@%d;' % (a, t - t0) for a, t in rm.wr)
        return t0, marks, [len(rm.wr), hashlib.sha1(s.encode('ascii')).hexdigest()[:16]]
    return t0, marks, (rm.rd if rm is not None else None)


def replay(acc, marks, phase):
    """the contended T of every mark from the access program at the phase"""
    out, D, j = [], 0, 0
    for name, e in marks:
        while j < len(acc) and acc[j] < e:
            D += DELAYS_48K[(phase + acc[j] + D) % FRAME_T]
            j += 1
        out.append([name, e + D])
    return out


def program(st, pokes=()):
    log = []
    t0, marks, rd = run_reveal(st, None, log, pokes, rmem=True)
    acc = [t - t0 for t in log]
    hooks = dict(marks)
    prog = {}
    seq = [m for m in marks if m[0] in ROUTINES]
    for i, (name, e) in enumerate(seq):
        hi = seq[i + 1][1] if i + 1 < len(seq) else hooks['ret'] + 1
        pts = [a - e for a in acc if e <= a < hi]
        prog[name] = [len(pts), digest(pts)]
    return acc, marks, prog, rd


def source(args):
    """one source: its program, then the machine at every phase, each checked against the replay"""
    name, st, own, pokes, base_rd = args
    acc, marks, prog, rd = program(st, pokes)
    rows = []
    for ph in ([own] if own is not None else []) + PHASES:
        _, m, wd = run_reveal(st, ph, None, pokes)
        rp = replay(acc, marks, ph)
        if rp != m:
            raise Fail('%s phase %d: the replay %s, the machine %s' % (name, ph, rp, m))
        rows.append([ph, [x[1] for x in m]] + wd)
    out = {'name': name, 'exact': marks, 'prog': prog, 'n_acc': len(acc), 'own': own, 'machine': rows}
    if base_rd is not None:
        h = RE.new('round1_48')
        h.load_state(st)
        m0 = h.memobj.m
        extra = []
        for a in sorted(a for a in rd - base_rd if a >= 0x4000):
            if extra and extra[-1][0] + len(extra[-1][1]) // 2 == a:
                extra[-1][1] += '%02X' % m0[a]
            else:
                extra.append([a, '%02X' % m0[a]])
        out['pokes'] = [list(p) for p in pokes]
        out['extra'] = extra
    return out


def base_reads(st):
    return program(st)[3]


def call_alone(st, addr, pokes):
    """$7F80 / $957E CALLed alone with a sentinel return: (points from the entry, exact T)"""
    h = RE.new('round1_48')
    h.load_state(st)
    for a, v in pokes:
        h.memobj.m[a] = v
    RE.push_call(h, addr)
    log = []
    sim = sim_of(h, log)
    r, mem = sim.registers, sim.memory
    t0 = r[T]
    sents = set(h.SENTINELS)
    while r[PC] not in sents:
        if r[PC] in GUARD:
            raise Fail('guard at $%04X' % r[PC])
        sim.opcodes[mem[r[PC]]]()
        if r[T] - t0 > 10 ** 5:
            raise Fail('no return from $%04X' % addr)
    pts = [t - t0 for t in log]
    return [len(pts), digest(pts), r[T] - t0]


def alone(args):
    st, kind, v = args
    if kind == 'digits':
        return call_alone(st, 0x7F80, [(0x8609, v)])
    m1, m2 = v
    return call_alone(st, 0x957E, [(0xFDE3, m1), (0xFDED, m2)])


def umb_sources(run):
    x = UMB.reach(run)
    fr, aft, seg_states = UMB.free(x, run[0])
    out = []
    for (kind, k), st in seg_states:
        if kind == 'reveal':
            out.append(['%s:reveal%d' % (run[0], k), st, st[1][T] % FRAME_T])
    return out


FL_HOOKS = {0xA0E0: 'u_flash', 0xA119: 'u_ei'}


def run_flash(st, phase=None, log=None):
    """(M7.99d) a later flash, from $A121's DI to the HALT: marks [(name, T from the start)]; with a phase also
    the write stream as run_reveal's"""
    h = RE.new('round1_48')
    h.load_state(st)
    wm = WriteMem(h.memobj.m) if phase is not None else None
    sim = sim_of(h, log, wm)
    r, mem = sim.registers, sim.memory
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    t0 = r[T]
    if wm is not None:
        wm.regs = r
    if r[PC] != UMB.SEG_F:
        raise Fail('a flash source not at $A121')
    marks, prev = [['u_turn', 0]], None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if mem[p] == 0x76:
            marks.append(['halt', r[T] - t0])
            break
        if p in FL_HOOKS and prev != p:
            marks.append([FL_HOOKS[p], r[T] - t0])
        iff = r[IFF]
        if wm is not None:
            wm.tins[0] = r[T]
        sim.opcodes[mem[p]]()
        if not iff and r[IFF]:
            marks.append(['ei_end', r[T] - t0])
        prev = p
        if r[T] - t0 > 10 ** 5:
            raise Fail('no HALT after the flash')
    if wm is not None:
        wm.regs = None
        s = ''.join('%d@%d;' % (a, t - t0) for a, t in wm.wr)
        return t0, marks, [len(wm.wr), hashlib.sha1(s.encode('ascii')).hexdigest()[:16]]
    return t0, marks, None


def flash_source(args):
    name, st, own = args
    log = []
    t0, marks, _ = run_flash(st, None, log)
    acc = [t - t0 for t in log]
    seq = [m for m in marks if m[0] in ('u_turn', 'u_flash', 'u_ei')]
    prog = {}
    for i, (k, e) in enumerate(seq):
        hi = seq[i + 1][1] if i + 1 < len(seq) else dict(marks)['halt'] + 1
        pts = [a - e for a in acc if e <= a < hi]
        prog[k] = [len(pts), digest(pts)]
    rows = []
    for ph in [own] + PHASES:
        _, m, wd = run_flash(st, ph)
        rp = replay(acc, marks, ph)
        if rp != m:
            raise Fail('%s phase %d: the replay %s, the machine %s' % (name, ph, rp, m))
        rows.append([ph, [x[1] for x in m]] + wd)
    return {'name': name, 'exact': marks, 'prog': prog, 'n_acc': len(acc), 'own': own, 'machine': rows}


def flash_states(run):
    x = UMB.reach(run)
    fr, aft, seg_states = UMB.free(x, run[0])
    return [['%s:flash%d' % (run[0], k), st, st[1][T] % FRAME_T] for (kind, k), st in seg_states if kind == 'flash']


def measure(jobs=6):
    with ProcessPoolExecutor(jobs) as ex:
        rv = list(ex.map(RE.reach, [('9032', w) for w in ('r50_48', 'r10_48')]))
        um = list(ex.map(umb_sources, UMB.RUNS))
        fl = [s for l in ex.map(flash_states, UMB.RUNS) for s in l]
    srcs = [['9032:' + x['world'], x['state'], x['phase']] for x in rv]
    for u in um:
        srcs.extend(u)
    base = rv[0]['state']
    rd50 = base_reads(base)
    args = [(n, st, own, (), None) for n, st, own in srcs]
    args += [('9032:r50_48:' + v, base, None, pk, rd50) for v, pk in VARIANTS]
    al = [(base, 'digits', v) for v in range(101)]
    al += [(base, 'panel', (m, 0)) for m in range(64)] + [(base, 'panel', (0, m)) for m in range(1, 64)]
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(source, args))
        res_al = list(ex.map(alone, al))
        res_fl = list(ex.map(flash_source, [tuple(s) for s in fl]))
    out = {'meta': {'phases': PHASES, 'frame_t': FRAME_T, 'routines': ROUTINES,
                    'digest': "sha1(';'.join(offsets from the routine's hook))[:16]"},
           'sources': {r['name']: r for r in res},
           'digits': {str(a[2]): r for a, r in zip(al, res_al) if a[1] == 'digits'},
           'panel': {'%d,%d' % a[2]: r for a, r in zip(al, res_al) if a[1] == 'panel'},
           'flash': {r['name']: r for r in res_fl}}
    return out


def report(out):
    for n, s in out['sources'].items():
        ex = dict(s['exact'])
        wins = [r[1][[m[0] for m in s['exact']].index('ei_end')] + 4 for r in s['machine']]
        print('%-26s acc %6d  prog %s' % (n, s['n_acc'], ' '.join('%s:%d' % (k, v[0]) for k, v in s['prog'].items())))
        print('   exact ei_end %d ret %d; machine window %d..%d over %d phases (replay exact)' % (
            ex['ei_end'], ex['ret'], min(wins), max(wins), len(wins)))
    print('digits: %d rounds, points %s' % (len(out['digits']), sorted(set(v[0] for v in out['digits'].values()))))
    print('panel: %d masks, points %s' % (len(out['panel']), sorted(set(v[0] for v in out['panel'].values()))))
    fl = out['flash']
    halts = [r[1][-1] for s in fl.values() for r in s['machine']]
    print('flash: %d turns, %d runs (replay exact), progs %s, HALT %d..%d' % (
        len(fl), len(halts), sorted(set(json.dumps(s['prog']) for s in fl.values())), min(halts), max(halts)))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd not in ('measure', 'verify'):
        raise SystemExit(__doc__)
    jobs = 6
    if '--jobs' in sys.argv:
        jobs = min(6, int(sys.argv[sys.argv.index('--jobs') + 1]))
    t = time.time()
    out = measure(jobs)
    report(out)
    if cmd == 'measure':
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1)
        print('wrote %s (%.1f s)' % (FIXTURE, time.time() - t))
    else:
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        new_ = json.loads(json.dumps(out))
        if old == new_:
            print('MATCH (%.1f s)' % (time.time() - t))
        else:
            bad = [k for k in old if old[k] != new_.get(k)]
            print('DIFF in %s (%.1f s)' % (bad, time.time() - t))
            sys.exit(1)


if __name__ == '__main__':
    main()
