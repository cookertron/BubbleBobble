# -*- coding: utf-8 -*-
"""M7.84 -- THE ROUND BUILD'S ENTRY WINDOW, SURVEYED: can a frame interrupt land between $97F8 and $9855's gate stores?

$97F8 (the round advance) reaches the clear walk at $984B, whose first two $9855 LD (DE),A stores zero
($FEC4) (iteration 1, B = 19) and ($FEC5) (iteration 2) -- the table at $9AC1 starts $FEC4, $FEC5.  The ISR
($8D72) counts ($8DB6) and ($8DBD), then RR L on counter B's new low byte: ODD -> $8DA2 gated by ($FEC4)
($A3AD, then $AA60); EVEN -> $8DAD gated by ($FEC5) ($B62C).  An interrupt accepted after $97F8's entry
and before its branch's gate store runs GATE-OPEN; game.js (M7.59, BB_ROUND_BUILD comment) DECLARES that
window ("2 of 322") and the port runs that ISR gate-closed.

  natural   buildtime.py's own 322 natural advances (keys 1/2 x tile shifts 0/2 x $8609 chunks 1..71, ten
            each, plus the title's round 1 on key 1 and 2), contended, interrupts on, replayed the same way
            (asserted: the same (key, shift, round, entry phase) rows as build/buildtime_fixture.json).  Per
            advance: the main-line T from the entry to each gate store's completion (g4, g5), and the FIRST
            interrupt accepted after the entry: its T after the entry (the headroom), the branch it takes,
            the two gates at acceptance, whether its gate was open, its cost.
  ab        every in-window case, natural (the advance's own $97F8 machine) and FORCED (worlds from
            buildtime.world_at, the T moved so the frame boundary falls K T after the entry, and counter
            B's low bit poked to choose the branch): run A = the machine; run B = the port's model (that
            ISR runs with ($FEC4)/($FEC5) zeroed, restored at its return).  From each: the RAM the two
            differ in when the ISR is over (D; the stack zone excepted), every address of D the build's
            main line then reads before writing it (hits, with the PC of the read), the build's main-line
            T and its display writes (count, a hash of (main-line T, address) and of the addresses alone --
            NO VALUE), and the
            RAM A and B differ in at $9887 and at the loop top $8D0C (addresses only; display bytes counted).

GUARDED: every run stops with an error if PC enters $D000..$D2FF.  NO VALUE read below $4000 is stored.

Usage:  python tools/buildentry.py [--jobs N]          (-> build/buildentry_fixture.json)
        python tools/buildentry.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import buildtime as BT                       # patches harness.Mem with its read / write lists
import rounddrain as RD
from harness import Harness, PC, T, SP, IFF
from harness import A as RA
import portconfig as pc

FIXTURE = 'build/buildentry_fixture.json'
ENTRY, END, TOP = 0x97F8, 0x9887, 0x8D0C
G4, G5, CB = 0xFEC4, 0xFEC5, 0x8DBD
GLO, GHI = 0xD000, 0xD300
STK = 128                                    # the stack zone below SP left out of RAM diffs
OFFSETS = (1, 47, 120, 190, 215, 240, 260, 300, 340, 380)   # forced: the frame boundary K T after the entry
FORCED = [('r1_1p', '1', 0), ('r2', '1', 1), ('r10_2p', '2', 9), ('r11', '1', 10), ('r21', '1', 20),
          ('r81', '1', 80), ('r2_2p', '2', 1), ('r20', '1', 19), ('r40', '2', 39), ('r60', '1', 59)]


class Fail(Exception):
    pass


def sha(b):
    return hashlib.sha1(b).hexdigest()[:16]


def ranges(xs):
    out = []
    for a in sorted(xs):
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return ['%04X-%04X' % (a, b) if a != b else '%04X' % a for a, b in out]


def build(h, closed=False, track=False):
    """PC at $97F8 on the main line: run to $9887 (not executed), interrupts on.  closed: the FIRST
    interrupt accepted runs with ($FEC4)/($FEC5) zeroed and restored at its return.  track: keep the
    post-ISR RAM, the main line's reads-before-writes after it, and the display writes."""
    sim = h.sim
    r, op, mem = sim.registers, sim.opcodes, sim.memory
    m = mem.m
    fd, ia = h.frame_duration, h.int_active
    if r[PC] != ENTRY:
        raise Fail('not at $97F8 ($%04X)' % r[PC])
    t0, isr_t, cur = r[T], 0, None
    rec = dict(phase=r[T] % fd, round0=m[0x8609], g4=None, g5=None, isrs=[], ndisp=0, ldar=None)
    post, seen, hits, dh, da, saved = None, set(), {}, hashlib.sha1(), hashlib.sha1(), None
    BT.WL = []
    BT.RL = [] if track else None
    n = 0
    try:
        while True:
            p = r[PC]
            if GLO <= p < GHI:
                raise Fail('PC entered the guard at $%04X' % p)
            if cur is not None and p == cur[0] and r[SP] == cur[1]:
                d = r[T] - cur[2]
                rec['isrs'][-1].append(d)
                isr_t += d
                if len(rec['isrs']) == 1:
                    if saved is not None:
                        m[G4], m[G5] = saved
                    if track:
                        post = (bytes(m), r[SP])
                cur = None
            tm = r[T] - t0 - isr_t
            onmain = cur is None
            if onmain and p == 0x9813:
                rec['ldar'] = r[RA]                    # $9811 LD A,R: a register the ISR's length moves
            if onmain and p == END:
                rec['end'] = tm
                rec['round'] = m[0x8609]
                break
            if m[p] == 0x76:
                raise Fail('a HALT inside the build at $%04X' % p)
            del BT.WL[:]
            if track:
                del BT.RL[:]
            op[m[p]]()
            n += 1
            if onmain:
                for a, v in BT.WL:
                    if a == G4 and rec['g4'] is None:
                        rec['g4'] = r[T] - t0 - isr_t
                    elif a == G5 and rec['g5'] is None:
                        rec['g5'] = r[T] - t0 - isr_t
                if track:
                    if post is not None:
                        for a in BT.RL:
                            if a >= 0x4000 and a not in seen:
                                seen.add(a)
                                hits[a] = p
                    for a, v in BT.WL:
                        if post is not None:
                            seen.add(a)
                        if 0x4000 <= a < 0x5B00:
                            rec['ndisp'] += 1
                            dh.update(b'%d,%d;' % (tm, a))
                            da.update(b'%d;' % a)
            if r[IFF] and r[T] % fd < ia:
                b, spb, tt = r[PC], r[SP], r[T]
                g4v, g5v, odd = m[G4], m[G5], (m[CB] + 1) & 1
                if sim.accept_interrupt(r, mem, p):
                    cur = (b, spb, tt)
                    rec['isrs'].append([tt - t0, 'odd' if odd else 'even', g4v, g5v])
                    if len(rec['isrs']) == 1 and closed:
                        saved = (g4v, g5v)
                        m[G4] = m[G5] = 0
            if n > 3 * 10 ** 6:
                raise Fail('no $9887')
    finally:
        BT.WL = BT.RL = None
    rec['disp_hash'] = dh.hexdigest()[:16]
    rec['disp_addr'] = da.hexdigest()[:16]
    rec['post'], rec['reads'] = post, hits
    return rec


def first(rec):
    """the first interrupt after the entry: [headroom, branch, gate4, gate5, cost], and was its gate open"""
    if not rec['isrs']:
        return None, False
    f = rec['isrs'][0]
    return f, bool(f[2] if f[1] == 'odd' else f[3])


# ---------------------------------------------------------------- natural
def chunk(args):
    """buildtime.one_chunk's drive, with build() in place of its trace"""
    key, shift, start = args
    h = BT.my_handoff(key)
    rows, cases = [], []

    def one(keep):
        s = (bytes(h.memobj.m), list(h.sim.registers))
        rec = build(h)
        f, op = first(rec)
        row = dict(key=key, shift=shift, round=rec['round'], phase=rec['phase'], g4=rec['g4'], g5=rec['g5'],
                   first=f, open=op, end=rec['end'])
        if keep:
            rows.append(row)
            if op:
                cases.append((row, s, sha(bytes(h.memobj.m[0x4000:]))))
    one(start == 1 and shift == 0)
    r, m = h.sim.registers, h.memobj.m
    RD.ledger(h, lambda p, i: p == TOP)
    t_end = r[T] + RD.F_PLAY * h.frame_duration
    RD.ledger(h, lambda p, i: p == TOP and r[T] >= t_end)
    m[0x8609] = start
    m[0xFDDA] |= 0x80
    m[0xFDE4] |= 0x80
    if shift:
        m[0x83EC] = (m[0x83EC] + shift) % 5
    m[0xFECD] = 10
    for k in range(10):
        RD.ledger(h, lambda p, i: p == ENTRY)
        one(True)
    ab_rows = []
    for row, s, end_sha in cases:
        res = ab(s, check_sha=end_sha)
        res.update(kind='natural', key=row['key'], shift=row['shift'], round=row['round'])
        ab_rows.append(res)
    return rows, ab_rows


# ---------------------------------------------------------------- A / B
def from_snap(s):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path('round1_48'))
    h.load_state((s[0], s[1], 0))
    return h


def ab(s, check_sha=None):
    out, runs = {}, {}
    for mode in ('A', 'B'):
        h = from_snap(s)
        rec = build(h, closed=(mode == 'B'), track=True)
        m = h.memobj.m
        at_end = (bytes(m), h.sim.registers[SP])
        if mode == 'A' and check_sha is not None:
            out['replay'] = sha(bytes(m[0x4000:])) == check_sha
        RD.ledger(h, lambda p, i: p == TOP)
        rec['end_mem'], rec['top_mem'] = at_end, (bytes(m), h.sim.registers[SP])
        runs[mode] = rec
    A, B = runs['A'], runs['B']

    def diff(x, y):
        sp = min(x[1], y[1])
        return [a for a in range(0x4000, 0x10000) if x[0][a] != y[0][a] and not (sp - STK <= a < sp)]
    f, op = first(A)
    out.update(phase=A['phase'], g4=A['g4'], g5=A['g5'], first_A=f, open=op,
               first_B=first(B)[0], end_A=A['end'], end_B=B['end'],
               ndisp_A=A['ndisp'], ndisp_B=B['ndisp'], disp_same=A['disp_hash'] == B['disp_hash'],
               disp_addr_same=A['disp_addr'] == B['disp_addr'],
               round=A['round'], ldar_same=A['ldar'] == B['ldar'], ldar_run=A['ldar'] is not None)
    D = diff(A['post'], B['post']) if A['post'] and B['post'] else None
    out['post_diff'] = None if D is None else ranges(D)
    out['hits'] = None if D is None else [['%04X' % a, '%04X' % A['reads'][a]] for a in D if a in A['reads']]
    for nm, k in (('at_9887', 'end_mem'), ('at_8d0c', 'top_mem')):
        d = diff(A[k], B[k])
        out[nm] = dict(display=sum(1 for a in d if a < 0x5B00), other=ranges(a for a in d if a >= 0x5B00))
    return out


def forced(args):
    name, key, start, odd = args
    s = BT.world_at(key, start, [])
    rows = []
    for k in OFFSETS:
        b, regs = bytearray(s[0]), list(s[1])
        fd = 69888
        regs[T] = (regs[T] // fd + 1) * fd - k
        b[CB] = (b[CB] & 0xFE) if odd else (b[CB] | 1)
        res = ab((bytes(b), regs))
        res.update(kind='forced', world=name, K=k, branch='odd' if odd else 'even')
        rows.append(res)
    return rows


def task(t):
    return chunk(t[1:]) if t[0] == 'chunk' else forced(t[1:])


def measure(jobs):
    jl = [('chunk', k, s, c) for k in ('1', '2') for s in (0, 2) for c in BT.CHUNKS]
    jl += [('forced', nm, key, st, odd) for nm, key, st in FORCED for odd in (1, 0)]
    with Pool(jobs) as pool:
        res = pool.map(task, jl, chunksize=1)
    nat, ab_nat, forc = [], [], []
    for t, r in zip(jl, res):
        if t[0] == 'chunk':
            nat += r[0]
            ab_nat += r[1]
        else:
            forc += r
    # the same advances as buildtime's natural set
    bt = json.load(open('build/buildtime_fixture.json', encoding='utf-8'))['natural']['runs']
    same = [(r['key'], r['shift'], r['round'], r['phase']) for r in nat] == \
           [(r['key'], r['shift'], r['round'], r['phase']) for r in bt]
    heads = sorted((r['first'][0], r['key'], r['shift'], r['round']) for r in nat if r['first'])
    return dict(note=__doc__.split('\n')[0], same_as_buildtime=same, n_natural=len(nat),
                n_open=sum(1 for r in nat if r['open']),
                n_before_g5=sum(1 for r in nat if r['first'] and r['first'][0] < r['g5']),
                windows=sorted(set((r['g4'], r['g5']) for r in nat)),
                closest=heads[:12], natural=nat, ab_natural=ab_nat, forced=forc)


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 6
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in a:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = old == F
        if not ok:
            for k in old:
                if old.get(k) != F.get(k):
                    print('DIFF in', k)
        print('MATCH' if ok else 'DIFFER')
        sys.exit(0 if ok else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as f:
        json.dump(F, f, separators=(',', ':'))
    print('same as buildtime: %s; natural %d, open %d, first ISR before the $FEC5 store %d; windows (g4, g5) %s'
          % (F['same_as_buildtime'], F['n_natural'], F['n_open'], F['n_before_g5'], F['windows']))
    print('closest headrooms', F['closest'])
    for r in F['ab_natural'] + F['forced']:
        print(json.dumps({k: v for k, v in r.items()}))


if __name__ == '__main__':
    main()
