"""M7.89 (measurement) -- THE JUMP TONE'S T ($8FA5, and its own tail $8FAE), RUN BY RUN, UNCONTENDED.

passcost (M7.86) ranked $8FA5 at 6.9% of the main loop's T: 83..3,265 T, median 196, 36 paths, its
only child $8FAE.  This oracle records every run of $8FA5 from its one caller ($8D25 CALL $8FA5) on an
UNCONTENDED machine, so a run's T is the sum of its instructions' own T, and brackets every nested
CALL apart by entry PC + return SP (cost931a's way):

  $8FA5    LD HL,$FDDA / CALL $8FAE (P1) / LD HL,$FDE4 and FALL THROUGH into $8FAE (P2): P2's arm is
           $8FA5's OWN T, P1's is the child's
  $8FAE    one player's arm: (pb) bit 2 -> RET (dying); (pb-$53) bit 7 clear -> RET (not in play);
           phase (pb-$51) $FF -> RET (falling), 0 -> RET (grounded); else the tone: A = ($B57D+phase)
           - $10, NEG if negative, E = A + 1, B = 2 square cycles through OUT ($FE)

Every interrupt accepted inside a run is BRACKETED OUT (acceptance to the return to the interrupted PC
at the interrupted SP); such a run keeps its T and path, its seed/post are not kept ('irq').  A HALT
inside a run is an error (asserted: none).

  T        the run, entry to RET, the ISRs out (its child IN)
  own      T less the child's
  sig      the path of each level: every conditional pc with its taken / fell counts, 'pc:tNfM'
  kids     [entry, T, own, sig, kids] of each nested call
  E        per player (P1, P2) the arm the STATE names ('D' dying, 'O' out, 'F' falling, 'G' grounded,
           or the tone's E, '-' marking the NEG), computed from the bytes the run READ (its seed) --
           not from the path -- as game.js's jumpTone computes it
  seed     every byte the run READS before it writes it (not its own instruction bytes), the ROM's
           VALUES never (TRAPS #281: their count in 'rom'); post: every byte written, final value

THE MODEL (Zilog T, asserted against EVERY run, natural and forced, FROM THE STATE -- 'model'):
  $8FA5 own = HEAD 37 + ARM(P2);  $8FAE (the child) = ARM(P1);  ARM below (W)

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table.  FORCED CALLS (declared, CALLS below): every arm for each player with the other
out, the tone at every phase 1..32 for each player (the whole $B57D table: E 13..21, every one NEG --
the table holds $FC..$04, below $10), and one poked table byte for the JP p taken arm (no NEG).
$8FA5 called from a saved state with pokes, interrupts off at entry, returning to $8D28.
'contended': {state: [[runs, T] contention off, [runs, T] on]}, the runs an interrupt landed in out.
'window' (M7.93): round1_48's first WINDOW frames, contention off and on -- [runs, total T, {arms: n}] -- the
frames BB_PASS_T was CALIBRATED on (the timing census, build/timing_fixture.json 'seq': 48 frames); the share
the main loop's flat rest gives up is this window's (TRAPS #286: the share AS CALIBRATED).
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/cost8fa5.py [--jobs N]          (-> build/cost8fa5_fixture.json, N <= 6)
        python tools/cost8fa5.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections, time
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/cost8fa5_fixture.json'
FRAMES = 300
WINDOW = 48       # M7.93: the timing census's frames (BB_PASS_T's calibration), round1_48 from its start
KEEP = 2
BLOCK = 69888
ENTRY, CALLER, BACK = 0x8FA5, 0x8D25, 0x8D28
ARM = 0x8FAE
STATE_OPS = {}
CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RST_OPS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1
ED_REP = {0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}

# ---------------------------------------------------------------- the model (Zilog T)
W = dict(
    # $8FA5 LD HL,nn 10 / CALL $8FAE 17 / LD HL,nn 10 (the fall-through into $8FAE then is P2's arm)
    HEAD=37,
    # $8FAE BIT 2,(HL) 12 / RET nz taken 11
    DYING=23,
    # BIT 12 / RET nz 5 / LD DE,nn 10 / ADD HL,DE 11 / BIT 7,(HL) 12 / RET z taken 11
    OUT=61,
    # ... RET z 5 (55) / INC HL 6 / INC HL 6 / LD A,(HL) 7 / INC A 4 / RET z taken 11
    FALL=89,
    # ... RET z 5 (83) / DEC A 4 / RET z taken 11
    GROUND=98,
    # ... RET z 5 (92) / LD L,A 4 / LD H,n 7 / LD DE,nn 10 / ADD HL,DE 11 / LD A,(HL) 7 / SUB n 7 /
    # JP p 10 / [NEG 8] / LD L,A 4 / LD H,n 7 / ADD A,n 7 / LD E,A 4 / LD B,n 7  (177, +8 NEG)
    # then B = 2 cycles of: LD A,n 7 / OUT (n),A 11 / LD A,E 4 / (DEC A 4 / JR nz 12) x E, the last
    # JR 7 / OUT 11 / LD A,E 4 / the same delay / DJNZ 13 = 32E + 40, the last DJNZ 8 (-5); RET 10
    #   = 177 + 64E + 80 - 5 + 10 = 64E + 262
    TONE=262, TONE_E=64, NEG=8,
)


def arm_state(sd, pb):
    """the arm the STATE names for player base pb, from the bytes the run read ({addr: value})"""
    if sd[pb] & 0x04:
        return 'D'
    b7 = (pb + 0xFFAD) & 0xFFFF
    if not sd[b7] & 0x80:
        return 'O'
    ph = sd[(b7 + 2) & 0xFFFF]
    if ph == 0xFF:
        return 'F'
    if ph == 0:
        return 'G'
    a = (sd[(0xB57D + ph) & 0xFFFF] - 0x10) & 0xFF
    neg = bool(a & 0x80)
    if neg:
        a = (-a) & 0xFF
    return ('-' if neg else '') + str((a + 1) & 0xFF)


def MARM(s):
    """an arm's T from arm_state's name"""
    if s in ('D', 'O', 'F', 'G'):
        return W[{'D': 'DYING', 'O': 'OUT', 'F': 'FALL', 'G': 'GROUND'}[s]]
    neg = s.startswith('-')
    return W['TONE'] + W['TONE_E'] * int(s.lstrip('-')) + (W['NEG'] if neg else 0)


# ---------------------------------------------------------------- forced calls (declared)
P1B, P2B = 0xFDDA, 0xFDE4


def _player(pb, arm, ph=1):
    b7 = (pb + 0xFFAD) & 0xFFFF
    if arm == 'D':
        return [(pb, 0x04), (b7, 0x80), (b7 + 2, 1)]
    if arm == 'O':
        return [(pb, 0), (b7, 0)]
    return [(pb, 0), (b7, 0x80), (b7 + 2, {'F': 0xFF, 'G': 0}.get(arm, ph))]


CALLS = []
for _who, _pb, _ob in (('p1', P1B, P2B), ('p2', P2B, P1B)):
    for _a in 'DOFG':
        CALLS.append(('%s_%s' % (_who, _a), 'round1_48', _player(_pb, _a) + _player(_ob, 'O')))
    for _ph in range(1, 33):
        CALLS.append(('%s_ph%02d' % (_who, _ph), 'round1_48', _player(_pb, 'T', _ph) + _player(_ob, 'O')))
# the $B57D table holds $FC..$04 only, so every natural tone takes the NEG: one poked table byte ($B57E =
# $20, phase 1) for the JP p taken arm (E 17, no NEG) -- declared, a state no natural run holds
CALLS.append(('p1_pos', 'round1_48', _player(P1B, 'T', 1) + _player(P2B, 'O') + [(0xB57E, 0x20)]))
CALLS.append(('both_ph01_ph32', 'round1_48', _player(P1B, 'T', 1) + _player(P2B, 'T', 32)))
CALLS_BY = {c[0]: c for c in CALLS}


# ---------------------------------------------------------------- the machinery (generic)
class RecMem(B.RecMem):
    """ab38cost's recorder, plus the operands read as STATE (STATE_OPS: {pc: addrs}), set per tool"""
    __slots__ = ('ops',)

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = self.ops.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def machine(state, ops, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    rm.ops = ops
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


class Tracker:
    """the open run: a stack of frames [entry, sp0, t0, x0, kidT, cnt {pc: [t, f]}, kids, ret]"""

    def __init__(self, entry, keep_tree=True):
        self.entry = entry; self.keep = keep_tree
        self.cur = None; self.stack = []; self.excl = 0; self.isr = None; self.done = []

    def open(self, r, rm, ret):
        sp0 = (r[SP] + 2) & 0xFFFF
        self.cur = {'seed': [], 'irq': 0, 'halt': 0}
        rm.seen = set(); rm.rec = self.cur['seed']; rm.wr = self.cur['post'] = {}; rm.stk = sp0 - 2
        self.stack = [[self.entry, sp0, r[T], self.excl, 0, {}, [], ret]]

    def close_frames(self, r, rm):
        sp, t = r[SP], r[T]
        while self.stack and sp >= self.stack[-1][1] and sp - self.stack[-1][1] < 0x100:
            f = self.stack.pop()
            T_ = (t - f[2]) - (self.excl - f[3])
            node = ['%04X' % f[0], T_, T_ - f[4], sig(f[5]), f[6]]
            if self.stack:
                par = self.stack[-1]
                par[4] += T_
                par[6].append(node)
            else:
                assert r[PC] == f[7], 'returned to $%04X' % r[PC]
                x = self.cur
                x['T'] = T_; x['own'] = T_ - f[4]; x['sig'] = node[3]; x['cnt'] = f[5]; x['kids'] = f[6]
                rm.rec = None
                self.done.append(x)
                self.cur = None

    def step(self, r, op, raw, rm, h):
        p, sp = r[PC], r[SP]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if self.isr is not None and p == self.isr[0] and sp == self.isr[1]:
            self.excl += r[T] - self.isr[2]
            self.isr = None
            if self.cur is not None:
                rm.rec = self.cur['seed']
        if self.isr is None and self.cur is not None:
            self.close_frames(r, rm)
        o = raw[p]
        if o == 0x76:
            if self.cur is not None and self.isr is None:
                raise AssertionError('HALT inside a run at $%04X' % p)
            h._fast_halt()
            return
        top = self.stack[-1] if (self.cur is not None and self.isr is None) else None
        op[o]()
        if top is not None:
            np_, nsp = r[PC], r[SP]
            if COND[o] or (o == 0xED and raw[(p + 1) & 0xFFFF] in ED_REP):
                c = top[5].get(p)
                if c is None:
                    c = top[5][p] = [0, 0]
                c[1 if np_ == B._fall(raw, p) else 0] += 1
            if nsp == (sp - 2) & 0xFFFF and ((o in CALL_OPS and np_ != (p + 3) & 0xFFFF) or o in RST_OPS):
                ret = (p + (1 if o in RST_OPS else 3)) & 0xFFFF
                if raw[nsp] | raw[(nsp + 1) & 0xFFFF] << 8 == ret:
                    self.stack.append([np_, sp, r[T], self.excl, 0, {}, [], ret])
        if r[IFF] and r[T] % h.frame_duration < h.int_active:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                assert self.isr is None, 'an interrupt inside the ISR'
                self.isr = (b, spb, tt)
                if self.cur is not None:
                    self.cur['irq'] += 1
                    rm.rec = None


def sig(cnt):
    """a level's path: each conditional pc in address order with its taken / fell counts"""
    return ' '.join('%04x:t%df%d' % (q, c[0], c[1]) for q, c in sorted(cnt.items()))


def run(name, entry, back, ops, frames=FRAMES, contended=False):
    h, rm = machine(name, ops, contended)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    tr = Tracker(entry)
    while r[T] < t_end or tr.cur is not None:
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
        if tr.cur is None and tr.isr is None and p == entry:
            sp = r[SP]
            assert raw[sp] | raw[(sp + 1) & 0xFFFF] << 8 == back, '$%04X entered not from its caller' % entry
            tr.open(r, rm, back)
        tr.step(r, op, raw, rm, h)
    return tr.done


def call_run(state, pokes, entry, back, ops, limit=400000):
    h, rm = machine(state, ops)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for ad, v in pokes:
        raw[ad] = v
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = back & 0xFF, back >> 8
    r[SP] = sp; r[PC] = entry
    tr = Tracker(entry)
    tr.open(r, rm, back)
    for _ in range(limit):
        tr.step(r, op, raw, rm, h)
        if tr.isr is None and tr.cur is not None:
            tr.close_frames(r, rm)
        if tr.cur is None:
            break
    else:
        raise AssertionError('$%04X: no return' % entry)
    return tr.done[0]


def row_base(name, x):
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if a < 0x5800] if rom else []
    if rom:
        post = [(a, v) for a, v in post if a >= 0x5800]
    out = {'state': name, 'T': x['T'], 'own': x['own'], 'sig': x['sig'], 'irq': x['irq'], 'kids': x['kids']}
    if not x['irq']:
        out.update({'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
                    'post': ''.join('%04x%02x' % (a, v) for a, v in post),
                    'rom': len(rom), 'blind': ' '.join('%04x' % a for a in blind)})
    return out


def contended_pair(st, entry, back, ops, keep=lambda x: True):
    """one state's natural runs with contention OFF and ON -- [runs, total T] each, the runs an
    interrupt landed in (and those `keep` refuses) left out"""
    out = []
    for c in (False, True):
        rs = [x for x in run(st, entry, back, ops, FRAMES, c) if not x['irq'] and keep(x)]
        out.append([len(rs), sum(x['T'] for x in rs)])
    return out


def jobs_arg(args):
    j = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    return min(j, 6)


# ---------------------------------------------------------------- $8FA5
def check(x):
    """the model, FROM THE STATE, against one run: (ok, E-names (P1, P2), predicted (own, kid))"""
    sd = {}
    for a, v in x['seed']:
        sd.setdefault(a, v)
    e1, e2 = arm_state(sd, P1B), arm_state(sd, P2B)
    po, pk = W['HEAD'] + MARM(e2), MARM(e1)
    kids = x['kids']
    ok = (x['own'] == po and len(kids) == 1 and kids[0][0] == '%04X' % ARM and kids[0][1] == pk
          and kids[0][2] == pk and x['T'] == po + pk)
    return ok, (e1, e2)


def one(job):
    name, tag = job
    if tag:
        c = CALLS_BY[tag]
        runs = [call_run(c[1], c[2], ENTRY, BACK, STATE_OPS)]
    else:
        runs = run(name, ENTRY, BACK, STATE_OPS)
    out = []
    for x in runs:
        ok, es = check(x)
        rw = row_base(tag or name, x)
        rw['E'] = list(es)
        out.append((ok, rw))
    return out


def contended_one(st):
    return contended_pair(st, ENTRY, BACK, STATE_OPS)


def window_one(c):
    """M7.93: round1_48's first WINDOW frames, contention off / on: [runs, total T, {'P1,P2' arms: n}], the
    runs an interrupt landed in left out"""
    rs = [x for x in run('round1_48', ENTRY, BACK, STATE_OPS, WINDOW, c) if not x['irq']]
    return [len(rs), sum(x['T'] for x in rs), dict(collections.Counter(','.join(check(x)[1]) for x in rs))]


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, A.STATES)
        wres = pool.map(window_one, (False, True))
    contended = {s: cres[i] for i, s in enumerate(A.STATES)}
    rows, per = [], collections.Counter()
    n_runs = n_irq = 0
    ts, owns, sigs, arms = [], collections.Counter(), set(), collections.Counter()
    bad, sigs_forced, arms_forced = [], set(), set()
    for (s, tag), rs in zip(work, res):
        for ok, x in rs:
            if not ok:
                bad.append([x['state'], x['T'], x['own'], x['sig'], x['E']])
            path = x['sig'] + ' | ' + x['kids'][0][3]
            if tag:
                sigs_forced.add(path); arms_forced.update(x['E'])
                rows.append(x)
                continue
            n_runs += 1; n_irq += 1 if x['irq'] else 0
            ts.append(x['T']); owns[x['own']] += 1; sigs.add(path); arms.update(x['E'])
            key = path + ' ' + ','.join(x['E'])
            if per[key] < KEEP and not x['irq']:
                per[key] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS], 'W': W,
            'runs': n_runs, 'irq_runs': n_irq, 'paths': len(sigs), 'T': [min(ts), max(ts)],
            'T_median': sorted(ts)[len(ts) // 2],
            'own': [min(owns), max(owns)], 'own_distinct': len(owns),
            'arms_natural': dict(sorted(arms.items())), 'arms_forced_new': sorted(arms_forced - set(arms)),
            'paths_list': sorted(sigs), 'forced_paths_new': sorted(sigs_forced - sigs),
            'contended': contended,
            'window': {'frames': WINDOW, 'state': 'round1_48', 'off': wres[0], 'on': wres[1]},
            'model': {'bad': bad, 'checked': n_runs + len(CALLS)},
            'rows': rows}


def finish(F, fixture, args, report):
    if 'verify' in args:
        old = json.load(open(fixture, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); return 0 if ok else 1
    json.dump(F, open(fixture, 'w', encoding='utf-8'), separators=(',', ':'))
    report(F)
    return 0


def report(F):
    print('runs %d (irq %d) paths %d T %s median %d own %s/%d | rows %d' % (
        F['runs'], F['irq_runs'], F['paths'], F['T'], F['T_median'], F['own'], F['own_distinct'], len(F['rows'])))
    print('model: bad %d of %d' % (len(F['model']['bad']), F['model']['checked']))
    for b in F['model']['bad'][:10]: print('  BAD', b)
    print('arms natural:', F['arms_natural']); print('arms forced new:', F['arms_forced_new'])
    print('forced new paths: %d' % len(F['forced_paths_new']))
    n0, t0 = F['contended']['round1_48'][0]; n1, t1 = F['contended']['round1_48'][1]
    print('round1_48 uncontended %d runs mean %.3f | contended %d runs mean %.3f' % (n0, t0 / n0, n1, t1 / n1))
    w0, w1 = F['window']['off'], F['window']['on']
    print('window %d frames: contended %d runs %d T mean %.3f ; uncontended %d runs %d T mean %.3f ; K %.6f ; arms %s %s' % (
        WINDOW, w1[0], w1[1], w1[1] / w1[0], w0[0], w0[1], w0[1] / w0[0], (w1[1] / w1[0]) / (w0[1] / w0[0]), w0[2], w1[2]))


def main():
    args = sys.argv[1:]
    t0 = time.time()
    F = json.loads(json.dumps(measure(jobs_arg(args))))
    rc = finish(F, FIXTURE, args, report)
    print('%.0f s' % (time.time() - t0))
    sys.exit(rc)


if __name__ == '__main__':
    main()
