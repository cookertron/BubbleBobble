# -*- coding: utf-8 -*-
"""M10.2d -- THE 128K BRANCH'S PAUSE ON THE FRAME CLOCK: request 0 before the spin, the saved sound re-requested after it.

$8FE7 (the chain's $8D28) arms on SYM SHIFT and spins until CAPS SHIFT as on the 48K (tools/pausespin.py), but on the
128K branch $8E0A is the sound code, not a RET:
  $8FEE LD A,($FED4) / PUSH AF / XOR A / $8FF3 CALL $8E0A    REQUEST 0, the mute (R7 := $3F), made with the interrupts
        ON: a DI window $8E10 DI .. $8E28 EI / $8E29 RET, whose RET's end is the arm's last acceptance point
  $8FF6 DI / LD A,4 / $8FF9 OUT ($FE),A / $8FFB the spin            interrupts off: nothing ticks
  $9002 XOR A / $9003 OUT ($FE),A / $9005 POP AF / $9006 CALL $8E0A    the saved sound RE-REQUESTED with the interrupts
        OFF (it restarts from its start): its $8E28 EI / $8E29 RET ends the spin's window, one instruction before the
        48K's $9009 EI / $900A RET, and the chain goes on at $8D2B
This measures both on the M10 machine (tools/ay128flow.py's: the 48K harness, contended, with the paging port and AY).

'runs'   pausespin's runs: WORLDS -- the M10 machine at the main loop's top ($8D0C, outside an interrupt), saved from the
         flow's p1 (round 1, the theme 1 current) and boss (round 80, the boss theme 6) scenes in play -- x the arm
         K = 0..KS-1 frames on x N paused frames ('cut'), SYM+CAPS together ('both'), and FORCED runs ('late': $8FE7 put
         LATE T before a boundary, only the clock moved -- the arm's instructions, request 0's four before its DI, the DI,
         its window, its RET's end and the spin's DI; 'late' 'both': LATE_BOTH, the unpause's request across a boundary --
         SYM, and CAPS with it, pressed at that $8FE7: the first at or after b0, wherever the world's pass puts it).
         Keys change at frame boundaries, after the instruction that crosses one (pausespin's convention); 'both' lets go
         at $8D2B (nothing re-arms).  Per run, T on the machine's clock (absolute):
           top c25 e7 di h bc rin res polls outs next e7h   pausespin's (di: $8FF6's DI)
           isrs   [boundary, T after the acknowledge, T to the RET, the acceptance T]  pausespin's rows + the T the
                  interrupt is accepted at (the end of the instruction in progress, before the acknowledge)
           nacc   the acceptance T of the interrupt at `next` (before the acknowledge)
           cur    ($FED4) at $8FEE: the sound the unpause re-requests
           marks  [$8FF3, $9006]: the first arrival at each CALL (the flow's 'pause' / 'unpause' marks)
           reqs   [T, site, A, cur, IFF, DI, end]   each $8E0A entry on the main line: the CALL's site, A, ($FED4) then,
                  IFF, its $8E10 DI's first T (None when RET z returns), the T its RET ends ($8E29's, or $8E0F's RET z) --
                  before any interrupt taken there
           ereqs  [T, A, T to the return, A returned]   each $D167 (the engine's request)
           ay     [T, reg, val]   every AY data write ($BFFD; the OUT's first T)      p7ffd [T, pc, val]
           ticks  [T]   each $CF80 (the engine's tick, in an interrupt's hook)
         ASSERTED per run: a FORCED run's arming $8FE7 is the forced one (a world whose pass reaches $8FE7 just before b0
         would arm unforced and quietly repeat the natural run -- p1@960 did, until the keys went down at the forced
         $8FE7 itself), exactly two requests ($8FF3: A 0, IFF 1; $9006: A = cur, IFF 0), the poll train pred()'s from
         the head to the release, and no interrupt accepted from the spin's head to the unpause's RET's end.
'scenes' the real load's p1 with a pause inside the window where the port is the machine record for record (C2: to frame
         760): SYM at 741..743, CAPS at 749..751 ('pz'); SYM and CAPS together at 741, CAPS alone 742..744 ('pzb') --
         ay128flow's Flow and records (its module docstring is the format).

GUARDED: PC in $D000..$D2FF stops a run unless bank 1 is paged (the engine's code is there).
No ROM byte: T, phases, game-RAM bytes and the engine's AY writes only.
Usage:  python tools/pause128.py [measure] [--jobs N]     (-> build/pause128_fixture.json)
        python tools/pause128.py verify [--jobs N]        (re-measure, compare, say MATCH)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
from harness import Harness, PC, T, SP, IFF, A as RA
import ay128flow as af
from pausespin import pred, keys, SYM, CAPS, TOP, C25, GATE, DI, HEAD, IN_PC, IN_OFF

FIXTURE = 'build/pause128_fixture.json'
WORLDS = [('p1', 790), ('p1', 960), ('boss', 1400), ('p1', 870), ('p1', 1050), ('p1', 1140)]   # 'late': the first three
KS = 6
NS = [0, 1, 3]
GLO, GHI = 0xD000, 0xD300
REQ, REQ_RETZ, REQ_DI, REQ_RET, EREQ, EREQ_BACK, TICK = 0x8E0A, 0x8E0F, 0x8E10, 0x8E29, 0xD167, 0x8E20, 0xCF80
ARM_GATE, PAUSE, UNPAUSE = 0x8FEE, 0x8FF3, 0x9006
# $8FE7 put L T before a boundary (uncontended there): the boundary falls L T after $8FE7 -- in the arm (to the CALL's end
# 75), request 0's LD HL / CP / LD / RET z (75..103), at its DI (104), inside its window (105..), within 32 T of its RET's
# end (282..313), in the spin's DI (314..316), the spin
LATE = [40, 70, 74, 75, 76, 80, 98, 99, 103, 104, 105, 106, 107, 108, 150, 200, 250, 280, 281, 282, 283, 300, 312, 313,
        314, 315, 316, 317, 320, 400]
# SYM and CAPS together: the first poll releases (its IN at $8FE7 + 342); the unpause's request from 406 to its RET's end
# at 983, $9009 EI 983..987, $900A RET to 997 ($8D2B) -- 350..405: the point between the releasing IN and the unpause's
# CALL's end, where only the spin's own window (from its DI) can hold it
LATE_BOTH = [100, 104, 105, 200, 282, 313, 314, 350, 360, 380, 405, 406, 500, 800, 950, 951, 952, 953, 980, 982, 983, 984,
             985, 986, 987, 990, 996, 997, 998, 1000]
SCENES = {
    'pz': dict(script=af.CTRL + [(368, []), (3, ['1']), (107, []), (40, ['P']), (141, []), (3, ['SYM']), (5, []),
                                 (3, ['CAPS']), (100, [])], frames=840, window=700),
    'pzb': dict(script=af.CTRL + [(368, []), (3, ['1']), (107, []), (40, ['P']), (141, []), (1, ['SYM', 'CAPS']),
                                  (3, ['CAPS']), (100, [])], frames=840, window=700),
}


class _At(af.Flow):
    """the flow's drive, saving the machine at the main loop's top ($8D0C, outside an interrupt) at each frame in `at`"""

    def __init__(self, h, at, **kw):
        super().__init__(h, **kw)
        self.at, self.states = sorted(at), {}

    def on_pc(self, pc):
        if self.at and pc == TOP and self.isr is None and self.frame >= self.at[0]:
            self.states[self.at.pop(0)] = self.h.save_state()
        return super().on_pc(pc)


def worlds():
    """{'scene@frame': the machine's state}: each scene driven once from the load, as the flow drives it"""
    out = {}
    for scene in sorted({w[0] for w in WORLDS}):
        sc = af.SCENES[scene]
        at = [f for s, f in WORLDS if s == scene]
        h, m, r = af.machine()
        fl = _At(h, at, keyf=af.script_keyf(sc['script']), skip=sc.get('skip', False), pokes=sc.get('pokes'))
        fl.run(max(at) + 2)
        if fl.at:
            raise af.Fail('%s: no $8D0C at frames %s' % (scene, fl.at))
        for f, st in fl.states.items():
            out['%s@%d' % (scene, f)] = st
    return out


_WS = {}


def _init(ws):
    _WS.update(ws)


def run(job):
    wname, k, n, mode = job[:4]
    late = job[4] if len(job) > 4 else None
    h = Harness(contended=True)
    h.load_state(_WS[wname])
    pg = h.paging
    pg.clear_logs()
    sim, r = h.sim, h.sim.registers
    m, op = h.memobj.m, sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    assert pg is not None and m[0x8DC4] != 0xC9 and r[PC] == TOP, wname + ': not the 128K branch at $8D0C'
    keys(h, [])
    b0 = (r[T] // fd + 1 + k) * fd
    arm = [SYM, CAPS] if mode == 'both' else [SYM]
    sched = [] if late is not None else [(b0, arm)]     # FORCED: the keys go down at the forced $8FE7 itself
    isrs, in_isr = [], None
    tops, c25s, e7s, dis, polls, ins, outs = [], [], [], [], [], [], {}
    reqs, ereqs, ticks = [], [], []
    rq = eq = None
    hd = bc = res = cur = None
    mk = {}
    forced = False
    t_start = r[T]
    while True:
        p = r[PC]
        assert not (GLO <= p < GHI) or pg.cur == 1, 'ENTERED THE GUARDED RANGE'
        assert r[T] - t_start < (k + n + 14) * fd, '%s k%d n%d %s %s: no resume' % (wname, k, n, mode, late)
        if in_isr and p == in_isr[1] and r[SP] == in_isr[0]:
            isrs[in_isr[2]][2] = r[T] - isrs[in_isr[2]][1]
            in_isr = None
        if p == TICK:
            ticks.append(r[T])
        elif p == EREQ:
            eq = [r[T], r[RA], None, None]
            ereqs.append(eq)
        elif p == EREQ_BACK and eq is not None and eq[2] is None:
            eq[2], eq[3] = r[T] - eq[0], r[RA]
        if in_isr is None:
            if p == TOP and hd is None:
                tops.append(r[T])
            elif p == C25 and hd is None:
                c25s.append(r[T])
            elif p == GATE and hd is None:
                if late is not None and r[T] >= b0 and not forced:
                    r[T] = (r[T] // fd + 1) * fd - late     # FORCED: $8FE7 'late' T before a boundary
                    keys(h, arm)
                    forced = True
                e7s.append(r[T])
            elif p == ARM_GATE and hd is None:
                cur = m[0xFED4]                        # $8FEE LD A,($FED4): what $9005's POP AF gives back
            elif p in (PAUSE, UNPAUSE) and p not in mk and (p == PAUSE) == (hd is None):
                mk[p] = r[T]
            elif p == REQ:
                ret = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
                rq = [r[T], (ret - 3) & 0xFFFF, r[RA], m[0xFED4], r[IFF], None, None]
                reqs.append(rq)
            elif p == REQ_DI and rq is not None and rq[5] is None:
                rq[5] = r[T]
            elif p == DI and hd is None:
                dis.append(r[T])
            elif p == HEAD:
                if hd is None:
                    hd = r[T]
                    b1 = (hd // fd + 1) * fd
                    bc = b1 + n * fd
                    if mode == 'both':
                        bc = b0                        # CAPS is down from the arm's own boundary
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
                outs[p] = r[T]                         # the arm's OUT ($FE),4 and the release's OUT ($FE),0 (starts)
        if m[p] == 0x76 and r[IFF]:
            sp0, ret = r[SP], (p + 1) & 0xFFFF
            h._fast_halt()
            isrs.append([(r[T] // fd) * fd, r[T], None, None])
            in_isr = (sp0, ret, len(isrs) - 1)
            if res is not None:
                break
        else:
            op[m[p]]()
            if rq is not None and rq[6] is None and in_isr is None and \
                    (p == REQ_RET or (p == REQ_RETZ and r[PC] != REQ_DI)):
                rq[6] = r[T]                           # the request's RET ends (before an interrupt taken there)
            if p == 0x900A and hd is not None and res is None:
                res = r[T]                             # $900A RET done: $8D2B on the main line
                keys(h, [])                            # nothing re-arms: the next interrupt is this pause's
                sched = []
            if r[IFF] and r[T] % fd < ia:
                sp0, ret, t_ = r[SP], r[PC], r[T]
                if sim.accept_interrupt(r, m, p):
                    assert in_isr is None, 'a nested interrupt'
                    isrs.append([(r[T] // fd) * fd, r[T], None, t_])
                    in_isr = (sp0, ret, len(isrs) - 1)
                    if res is not None:
                        break
        while sched and r[T] >= sched[0][0]:
            keys(h, sched.pop(0)[1])
    top, c25, e7, di = tops[-1], c25s[-1], e7s[-1], dis[-1]
    assert top < c25 < e7 < di < hd
    assert late is None or (forced and e7 == (e7 // fd + 1) * fd - late), '%s %s: not forced' % (wname, late)
    rin = ins[-1]
    nb, _, _, nacc = isrs.pop()
    isr_in = [x for x in isrs if x[1] >= top]
    q = [x for x in reqs if x[0] >= top]
    assert len(q) == 2 and q[0][1] == PAUSE and q[0][2] == 0 and q[0][3] == cur and q[0][4] == 1 and \
        q[1][1] == UNPAUSE and q[1][2] == cur and q[1][3] == 0 and q[1][4] == 0, '%s: the requests %s' % (wname, q)
    assert not [x for x in isr_in if hd < x[1] < q[1][6]], 'an interrupt between the spin and the unpause\'s RET'
    assert nacc is None or nacc >= res
    if mode != 'both':
        assert bc > hd
    want = pred(hd, bc, fd)
    assert polls == want, '%s k%d n%d: the poll train is not the model' % (wname, k, n)
    assert rin == want[-1] + IN_OFF
    return {'world': wname, 'k': k, 'n': n, 'mode': mode, 'late': late, 'b0': b0, 'top': top, 'c25': c25, 'e7': e7,
            'di': di, 'h': hd, 'bc': bc, 'rin': rin, 'res': res, 'polls': len(polls), 'isrs': isr_in, 'next': nb, 'nacc': nacc,
            'outs': [outs[0x8FF9], outs[0x9003]], 'e7h': hd - e7, 'cur': cur, 'marks': [mk[PAUSE], mk[UNPAUSE]], 'reqs': q,
            'ereqs': [x for x in ereqs if x[0] >= top],
            'ay': [[t, rg, v] for t, pc_, rg, v in pg.ay_log if t >= top],
            'p7ffd': [[t, pc_, v] for t, pc_, v, ap in pg.p7ffd if t >= top],
            'ticks': [t for t in ticks if t >= top]}


def scene(name):
    sc = SCENES[name]
    h, m, r = af.machine()
    f = af.Flow(h, keyf=af.script_keyf(sc['script']))
    f.run(sc['frames'])
    rec = af.records(f, sc['window'])
    rec['script'] = [[n, k] for n, k in sc['script']]
    rec['skip'] = False
    rec['frames_to'] = sc['frames']
    return rec


def _job(j):
    return scene(j[1]) if j[0] == 'scene' else run(j)


def measure(jobs):
    ws = worlds()
    names = ['%s@%d' % w for w in WORLDS]
    jl = [(w, k, n, 'cut') for w in names for k in range(KS) for n in NS] + \
         [(w, k, 0, 'both') for w in names for k in range(KS)] + \
         [(w, 0, n, 'late', d) for w in names[:3] for n in (0, 1) for d in LATE] + \
         [(w, 0, 0, 'both', d) for w in names[:3] for d in LATE_BOTH]
    sj = [('scene', s) for s in SCENES]
    with Pool(jobs, initializer=_init, initargs=(ws,)) as pool:
        out = pool.map(_job, sj + jl)
    return {'note': __doc__.split('\n')[0], 'worlds': names, 'ks': KS, 'ns': NS, 'late': LATE, 'late_both': LATE_BOTH,
            'runs': out[len(sj):], 'scenes': dict(zip(SCENES, out[:len(sj)]))}


def report(F):
    rs = F['runs']
    print('runs %d' % len(rs))
    fd = 69888
    for x in rs:
        q0, q1 = x['reqs']
        print('  %-10s k%d n%d %-4s %4s  e7 ph %5d  q0 %3d+%3d  q1 %3d  h-e7 %3d  isr %d  rin-bc %3d  res-rin %4d  polls %6d'
              % (x['world'], x['k'], x['n'], x['mode'], x['late'] if x['late'] is not None else '', x['e7'] % fd,
                 q0[0] - x['e7'], q0[6] - q0[0], q1[6] - q1[0], x['e7h'], len(x['isrs']), x['rin'] - x['bc'],
                 x['res'] - x['rin'], x['polls']))
    for name, sc in F['scenes'].items():
        print('  scene %-4s reqs %s  marks %s' % (name, sc['reqs'][-4:], {k: v for k, v in sc['marks'].items()
                                                                          if k in ('pause', 'unpause', 'main_loop')}))


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 6
    cmd = a[0] if a and not a[0].startswith('--') else 'measure'
    F = measure(jobs)
    report(F)
    if cmd == 'verify':
        old = json.load(open(FIXTURE))
        same = old == json.loads(json.dumps(F))
        print('MATCH' if same else 'DIFFER')
        sys.exit(0 if same else 1)
    with open(FIXTURE, 'w') as fh:
        json.dump(F, fh, separators=(',', ':'))
    print('->', FIXTURE, os.path.getsize(FIXTURE), 'bytes')


if __name__ == '__main__':
    main()
