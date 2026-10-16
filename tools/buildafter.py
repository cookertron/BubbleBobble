# -*- coding: utf-8 -*-
"""M7.85 follow-up -- AFTER THE ROUND BUILD'S ENTRY WINDOW: does a gate-open in-window ISR change anything later?

tools/buildentry.py found that an interrupt accepted between $97F8 and $9855's gate stores runs gate-open on
the machine (A) and gate-closed in the port (B), and that the two machines differ after the build in a few
bytes: even $B62D; odd $A3B2 $A990 $AA59 $AA65 $FEC6 (+ $8DB6/$8DBD on r60 / r81), and on r21 / r40 in
$7E0E and the $D380 bank at the loop top.  This tool traces A and B FORWARD from the same $97F8 machine, to
the first loop top $8D0C and then FRAMES frames on, the same key script on all (by frame), and a THIRD run B' = B with every `LD A,R` (ED 5F) answered by A's value at the same occurrence
(the port's declared RNG substitute stands in for R, so B' is "the port's model with R taken out").

  per frame  sampled at each video frame's interrupt acceptance from the first loop top on (absolute frames:
             the machines share T; keys by frame index): the frame and ISR count, the loop-top passes in the
             frame, the display $4000..$5AFF, the entity table $FD80..$FF5F, the beeper/MIC edges (OUT to an
             even port, bits 4/3: their count, and their levels with T from the frame start), and the RAM A
             and X differ in (the stack zone below SP excepted).  Reported: the FIRST frame (0 = the first
             after the loop top) each differs and what; whether the RAM converges.
  census     on A: every main-line / ISR read and write of the leftover bytes after the build ($9887 on),
             by PC -- who reads $B62D and who rewrites it; and each run's ISR count inside the build.
  rng        every LD A,R executed: site and whether A's and B's values differ (no value stored).
  check      A / B at $9887 and at the first $8D0C reproduce build/buildentry_fixture.json's diffs.

GUARDED: every run stops with an error if PC enters $D000..$D2FF.  NO VALUE read below $4000 is stored
(hashes, addresses, PCs and counts only).

Usage:  python tools/buildafter.py [--jobs N]          (-> build/pending/buildafter_fixture.json)
        python tools/buildafter.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import buildentry as BE                      # imports buildtime, which patches harness.Mem's reads / writes
import buildtime as BT
import rounddrain as RD
from harness import PC, T, SP, IFF, R
from harness import A as RA, F as RF

FIXTURE = 'build/buildafter_fixture.json'
ENTRY, END, TOP = 0x97F8, 0x9887, 0x8D0C
G4, G5 = 0xFEC4, 0xFEC5
GLO, GHI = 0xD000, 0xD300
STK = 128
FRAMES = 1500                                # frames past the first loop top
ACTIONS = ['B', '', 'B', '', 'RB', '', 'LB', '']   # chosen (scratch trial) because it reaches $B989 and $BA0F
KEY_FRAMES = 6                               # the script steps every 6 frames
WATCH = {0xB62D: 'B62D', 0xA3B2: 'A3B2', 0xA990: 'A990', 0xAA59: 'AA59', 0xAA65: 'AA65', 0xFEC6: 'FEC6',
         0x8DB6: '8DB6', 0x8DBD: '8DBD', 0x7E0E: '7E0E', 0xB54B: 'B54B', 0xFEC7: 'FEC7'}
DISP = (0x4000, 0x5B00)
ENT = (0xFD80, 0xFF60)
# the forced sample: (world, key, start, branch odd?, K) -- buildentry's FORCED worlds
FORCED = [('r2', '1', 1, 0, 47), ('r20', '1', 19, 0, 300), ('r21', '1', 20, 0, 47), ('r40', '2', 39, 0, 47),
          ('r60', '1', 59, 0, 47), ('r81', '1', 80, 0, 1),
          ('r2', '1', 1, 1, 47), ('r10_2p', '2', 9, 1, 47), ('r21', '1', 20, 1, 47), ('r40', '2', 39, 1, 47),
          ('r60', '1', 59, 1, 47), ('r81', '1', 80, 1, 1), ('r81', '1', 80, 1, 120)]


class Fail(Exception):
    pass


def sha(b):
    return hashlib.sha1(b).hexdigest()[:16]


class Census:
    """BT's read / write lists replaced by a filter on WATCH, tagged with the PC and main / ISR"""
    def __init__(self):
        self.pc, self.isr, self.on, self.ev, self.frame = 0, False, False, {}, -1
        self.first = {}

    def _hit(self, a, kind):
        if self.on and a in WATCH:
            k = '%s %s %04X %s' % (WATCH[a], kind, self.pc, 'isr' if self.isr else 'main')
            e = self.ev.setdefault(k, [0, self.frame])      # [count, first frame (-1: the banner)]
            e[0] += 1
            if WATCH[a] not in self.first:
                self.first[WATCH[a]] = [kind, '%04X' % self.pc, 'isr' if self.isr else 'main']


class RdList:
    def __init__(self, c):
        self.c = c

    def append(self, a):
        self.c._hit(a, 'r')


class WrList:
    def __init__(self, c):
        self.c = c

    def append(self, av):
        self.c._hit(av[0], 'w')


class Run:
    """one machine from a $97F8 snapshot.  mode A: as is; B: the first ISR after the entry runs with
    ($FEC4)/($FEC5) zeroed, restored at its return (buildentry's model of the port); B': B, and every LD A,R
    answered by A's value at the same occurrence."""
    def __init__(self, s, mode, census=None, ref=None):
        self.h = BE.from_snap(s)
        self.mode, self.census, self.ref = mode, census, ref
        self.cur, self.isrs, self.saved, self.n, self.tops, self.last = None, 0, None, 0, 0, None
        self.k = -1                          # the forward frame index (-1: the build / banner)
        self.ldar = []                       # (site, value) in order
        self.desync = None
        self.h.ports.record_writes = True
        if self.h.sim.registers[PC] != ENTRY:
            raise Fail('not at $97F8')

    def to(self, target, step=False, frame=None):
        """run until the MAIN LINE is at `target` (step: at least one instruction first), or, with `frame`,
        until an interrupt is accepted in video frame >= `frame` (absolute T // 69888)"""
        h = self.h
        sim = h.sim
        r, op, mem = sim.registers, sim.opcodes, sim.memory
        m = mem.m
        fd, ia = h.frame_duration, h.int_active
        c = self.census
        BT.RL = RdList(c) if c else None
        BT.WL = WrList(c) if c else None
        try:
            while True:
                p = r[PC]
                if GLO <= p < GHI:
                    raise Fail('PC entered the guard at $%04X' % p)
                if self.cur is not None and p == self.cur[0] and r[SP] == self.cur[1]:
                    if self.saved is not None:
                        m[G4], m[G5] = self.saved
                        self.saved = None
                    self.cur = None
                if self.cur is None and p == TOP:
                    self.tops += 1
                if self.cur is None and p == target and not step:
                    return
                step = False
                if c:
                    c.pc, c.isr = p, self.cur is not None
                acc = None
                if m[p] == 0x76:
                    t = r[T]
                    tt = t if t % fd < ia else (t // fd + 1) * fd
                    sp0 = r[SP]
                    h._fast_halt()
                    if r[PC] != (p + 1) & 0xFFFF:
                        acc = ((p + 1) & 0xFFFF, sp0, tt)
                else:
                    ldar = m[p] == 0xED and m[(p + 1) & 0xFFFF] == 0x5F
                    op[m[p]]()
                    if ldar:
                        self.on_ldar(p, r)
                    if r[IFF] and r[T] % fd < ia:
                        b, spb, tt = r[PC], r[SP], r[T]
                        if sim.accept_interrupt(r, mem, p):
                            acc = (b, spb, tt)
                if acc is not None:
                    self.cur = acc
                    self.isrs += 1
                    if self.isrs == 1 and self.mode != 'A':
                        self.saved = (m[G4], m[G5])
                        m[G4] = m[G5] = 0
                    self.last = acc[2] // fd
                    if frame is not None and self.last >= frame:
                        return
                self.n += 1
                if self.n > 400 * 10 ** 6:
                    raise Fail('runaway')
        finally:
            BT.RL = BT.WL = None

    def on_ldar(self, p, r):
        k = len(self.ldar)
        if self.mode == "B'" and self.desync is None:
            if k < len(self.ref.ldar) and self.ref.ldar[k][0] == p:
                v = self.ref.ldar[k][1]
                r[RA] = v
                r[RF] = (r[RF] & 0x3F) | (v & 0x80) | (0x40 if v == 0 else 0)
            else:
                self.desync = [k, '%04X' % p, self.k]
        self.ldar.append((p, r[RA]))

    def mem(self):
        return self.h.memobj.m

    def sound(self):
        w = self.h.ports.writes
        out = [(t, v & 0x18) for t, port, v in w if not port & 1]
        del w[:]
        return out


def ramdiff(x, y):
    mx, my = x.mem(), y.mem()
    sp = min(x.h.sim.registers[SP], y.h.sim.registers[SP])
    out = []
    for blk in range(0x4000, 0x10000, 256):
        if mx[blk:blk + 256] != my[blk:blk + 256]:
            out += [a for a in range(blk, blk + 256) if mx[a] != my[a] and not (sp - STK <= a < sp)]
    return out


def edges(snd, t0):
    """the beeper / MIC level changes: (T from the loop top, level)"""
    out, last = [], None
    for t, v in snd:
        if v != last:
            out.append((t - t0, v))
            last = v
    return out


def keys_for(runs, k):
    """ab38cost's play script through the game's own key tables ($B5FD P1, $B605 P2: L R J B as
    (half-row select, mask); select $1F = Kempston), both players, by frame"""
    act = ACTIONS[(k // KEY_FRAMES) % len(ACTIONS)]
    for x in runs:
        raw = x.mem()
        x.h.ports.release_all()
        for kt in (0xB5FD, 0xB605):
            for j, c in enumerate('LRJB'):
                sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                if c in act and mask:
                    if sel == 0x1F:
                        x.h.ports.kempston |= mask
                    else:
                        x.h.ports.press(sel, 0xFF & ~mask)


def trace(s):
    cen = Census()
    A = Run(s, 'A', census=cen)
    B = Run(s, 'B')
    Bp = Run(s, "B'", ref=A)
    runs = (A, B, Bp)
    out = {}
    # the build, to $9887 (the HALT not executed)
    for x in runs:
        x.to(END)
    out['isrs_in_build'] = [A.isrs, B.isrs, Bp.isrs]
    out['at_9887'] = {'B': BE.ranges(ramdiff(A, B)), "B'": BE.ranges(ramdiff(A, Bp))}
    out['t_9887'] = [A.h.sim.registers[T] % 69888, B.h.sim.registers[T] % 69888]
    cen.on = True
    for x in runs:
        x.to(TOP)
    out['at_8d0c'] = {'B': BE.ranges(ramdiff(A, B)), "B'": BE.ranges(ramdiff(A, Bp))}
    out['isrs_at_8d0c'] = [A.isrs, B.isrs, Bp.isrs]
    out['phase_8d0c'] = [x.h.sim.registers[T] % 69888 for x in runs]
    for x in runs:
        x.sound()
    # FORWARD, sampled at each frame's interrupt acceptance (absolute frames: the three machines share T)
    for x in runs:
        x.sound()
    fd = 69888
    F0 = A.h.sim.registers[T] // fd + 1
    res = {nm: dict(first={}, conv=None) for nm in ('B', "B'")}
    rd0 = {'B': ramdiff(A, B), "B'": ramdiff(A, Bp)}
    last = {}
    for k in range(FRAMES):
        F = F0 + k
        keys_for(runs, k)
        cen.frame = k
        rows = []
        for x in runs:
            x.tops, x.k = 0, k
            if x.last is None or x.last < F:
                x.to(None, frame=F)
            m = x.mem()
            rows.append(dict(f=x.last, isrs=x.isrs, tops=x.tops, d=bytes(m[DISP[0]:DISP[1]]),
                             e=bytes(m[ENT[0]:ENT[1]]), s=edges(x.sound(), (F - 1) * fd)))
        ra = rows[0]
        for nm, x, rx in (('B', B, rows[1]), ("B'", Bp, rows[2])):
            fr = res[nm]['first']
            rd = ramdiff(A, x)
            last[nm] = rd
            if rd and res[nm]['conv'] is not None:
                res[nm]['conv'] = None                     # diverged again
            if not rd and res[nm]['conv'] is None:
                res[nm]['conv'] = k
            if 'frame' not in fr and (ra['f'] != rx['f'] or ra['isrs'] != rx['isrs']):
                fr['frame'] = [k, ra['f'] - rx['f'], ra['isrs'] - rx['isrs']]
            if 'passes' not in fr and ra['tops'] != rx['tops']:
                fr['passes'] = [k, ra['tops'], rx['tops']]
            if 'display' not in fr and ra['d'] != rx['d']:
                da = [DISP[0] + i for i in range(len(ra['d'])) if ra['d'][i] != rx['d'][i]]
                fr['display'] = [k, len(da), BE.ranges(da)[:12]]
            if 'entity' not in fr and ra['e'] != rx['e']:
                ea = [ENT[0] + i for i in range(len(ra['e'])) if ra['e'][i] != rx['e'][i]]
                fr['entity'] = [k, BE.ranges(ea)[:24]]
            if 'sound_n' not in fr and len(ra['s']) != len(rx['s']):
                fr['sound_n'] = [k, len(ra['s']), len(rx['s'])]
            if 'sound' not in fr and ra['s'] != rx['s']:
                fr['sound'] = [k, len(ra['s']), len(rx['s'])]
            if 'ram' not in fr and rd != rd0[nm]:
                fr['ram'] = [k, BE.ranges(rd)[:24]]
    for nm in res:
        res[nm]['ram_end'] = BE.ranges(last[nm])[:40]
        res[nm]['ram_end_n'] = len(last[nm])
    out['frames'] = FRAMES
    out['res'] = res
    out['census'] = dict(sorted(cen.ev.items()))
    out['first_access'] = cen.first
    # LD A,R: sites and whether A and B read the same value (values NOT stored)
    la, lb = A.ldar, B.ldar
    sites = {}
    for i, (p, v) in enumerate(la):
        e = sites.setdefault('%04X' % p, [0, 0])
        e[0] += 1
        if i < len(lb) and lb[i][0] == p and lb[i][1] != v:
            e[1] += 1
    out['ldar'] = dict(n_A=len(la), n_B=len(lb), sites=sites,
                       same_sites=[p for p, v in la] == [p for p, v in lb],
                       desync=Bp.desync)
    return out


def natural(shift):
    """buildentry.chunk's drive (key 2, start 1): the advance whose first ISR lands open, as a snapshot"""
    h = BT.my_handoff('2')
    BE.build(h)
    r, m = h.sim.registers, h.memobj.m
    RD.ledger(h, lambda p, i: p == TOP)
    t_end = r[T] + RD.F_PLAY * h.frame_duration
    RD.ledger(h, lambda p, i: p == TOP and r[T] >= t_end)
    m[0x8609] = 1
    m[0xFDDA] |= 0x80
    m[0xFDE4] |= 0x80
    if shift:
        m[0x83EC] = (m[0x83EC] + shift) % 5
    m[0xFECD] = 10
    for k in range(10):
        RD.ledger(h, lambda p, i: p == ENTRY)
        s = (bytes(h.memobj.m), list(h.sim.registers))
        rec = BE.build(h)
        f, op = BE.first(rec)
        if op:
            return s, rec['round'], f
    raise Fail('no open advance')


def task(t):
    if t[0] == 'natural':
        s, rnd, f = natural(t[1])
        out = dict(kind='natural', key='2', shift=t[1], round=rnd, first=f)
    else:
        _, name, key, start, odd, K = t
        s0 = BT.world_at(key, start, [])
        b, regs = bytearray(s0[0]), list(s0[1])
        regs[T] = (regs[T] // 69888 + 1) * 69888 - K
        b[BE.CB] = (b[BE.CB] & 0xFE) if odd else (b[BE.CB] | 1)
        s = (bytes(b), regs)
        out = dict(kind='forced', world=name, branch='odd' if odd else 'even', K=K)
    out.update(trace(s))
    return out


def check(rows):
    """A / B at $9887 and $8D0C against buildentry's fixture"""
    F = json.load(open(BE.FIXTURE, encoding='utf-8'))
    bad = 0
    for r in rows:
        if r['kind'] == 'natural':
            ref = [x for x in F['ab_natural'] if x['shift'] == r['shift']][0]
        else:
            ref = [x for x in F['forced'] if x['world'] == r['world'] and x['K'] == r['K']
                   and x['branch'] == r['branch']][0]
        if ref['at_9887']['other'] != r['at_9887']['B'] or ref['at_8d0c']['other'] != r['at_8d0c']['B']:
            bad += 1
    return bad


def measure(jobs):
    jl = [('natural', 0), ('natural', 2)] + [('forced',) + f for f in FORCED]
    with Pool(jobs) as pool:
        rows = pool.map(task, jl, chunksize=1)
    return dict(note=__doc__.split('\n')[0], frames=FRAMES, check_vs_buildentry_bad=check(rows), rows=rows)


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 6
    if jobs > 6:
        raise SystemExit('at most 6 workers')
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in a:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = old == F
        if not ok:
            for i, (x, y) in enumerate(zip(old['rows'], F['rows'])):
                if x != y:
                    print('DIFF in row', i)
        print('MATCH' if ok else 'DIFFER')
        sys.exit(0 if ok else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as f:
        json.dump(F, f, separators=(',', ':'))
    print('check vs buildentry: %d bad' % F['check_vs_buildentry_bad'])
    for r in F['rows']:
        print(json.dumps(r))


if __name__ == '__main__':
    main()
