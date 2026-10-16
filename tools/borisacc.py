"""M7.115l (measurement) -- $915F's BORIS ERASE ON THE PASS'S ACCESS PROGRAM AND ITS GRID, AND ITS DI WINDOW ON THE CLOCK.

M7.114a put every main-line pass on the frame clock by its ACCESS PROGRAM (passacc), M7.114d placed each interrupt by the
pass's INSTRUCTION GRID (insgrid), M7.115f..k did it for the item pass, the callee an interrupt falls inside, $7E80, the
boss tick and the sparkle walk.  $915F ($8D34, the sixth chain entry) reads its request -- the operand of its own
`LD A,n` at $9160, which the respawn (inside the odd ISR) and the round's clear ($8ECF) set to 1 -- and with it up runs
`$9163 DI`, clears the request, $9257, $904D and the hurry timer $8DBD, and `$9173 LD IY,$9250 / CALL $A314`: Boris's
pixel restore, sixteen rows of two stores into the SCREEN from the shadow at display + $A000 -- contended, 32 accesses the
engine put nowhere (IA3's fruit pin: frame 970's pass 32 short) -- then `$917A EI / $917B RET`.  The engine logged the
request path as one BB_SM key whose CALL defers its EI, with none of the restore's keys after it (its region a MISS), and
the whole erase runs with interrupts OFF: an interrupt whose pulse falls inside the window is LOST on the machine (M7.57's
rule, M7.105's edge) -- the engine had no window there and ran it.

This oracle measures it:

  SAVED STATES (sparkacc's 48), FRAMES frames each of random keys (seeded): natural deaths and clears, natural requests.
  calls   every $915F CALL from the chain is counted; the REQUEST ones (the operand $9160 = 1 at the entry) are kept:
          [frame, the wall phase at its entry, its plain T, the accesses (count, digest of 'o:k;' -- o the plain offset from
          the entry, k the T into the instruction), the instructions (count, digest of 'o:t;'), the ISRs inside [o, T, label,
          acceptance phase], the frames whose interrupt the call LOST (a boundary inside it, no ISR for it), Boris's X / Y]
  replays every request call run again PLAIN (no contention, interrupts off) from its entry to the RET: the SEED (every byte
          >= $4000 read before written, as [start, hex] runs, and $9160 -- the request, read as an operand), the accesses
          and the instructions (count + digest), T, the marks [name, plain offset], the writes (count; the final value of
          each byte written: count + digest of 'a:v;'; the addresses as [start, length] runs -- $A314's own operands OPS
          left out: rewritten before every read, not state); `same` = the replay's digests are the natural call's
  forced  FORCED replays (declared), from the first request call of BASE_WORLD: Boris over every Y & 7 (the third band),
          at the screen's left and right edges, rows the $FD00 table aims at the ROM (their stores dropped), the bottom;
          ILIST's keep the machine's instruction list [pc, plain offset]
  phased  PHASED runs (declared): that call's entry with the CPU's T set so that the entry lies `shift` T before a frame
          boundary -- the bottom border, where nothing waits: plain offsets are wall offsets and the point lands to the T --
          run with interrupts and contention to the RET (and an ISR the RET's end takes): the point AT and 1 T into
          TARGETS (the request's read, the DEC, the RET nz, the DI, the stores, the CALL, the restore's entry, its first and
          last rows, the EI, the RET) and at END_AT T before the call's end (the window's last 32 T: the pulse outlasts it),
          in three scenes: 'odd' -- Boris's cells under P1's, the ODD ISR next (it draws him: his sprite on the erase's
          bytes; it INCs the hurry timer the call clears); 'odd3' -- the same with Boris's Y & 7 = 3 (the third band: the
          window ends later); 'even' -- the EVEN ISR next.  Each: the ISR [plain offset, T, acceptance phase, parity] or
          none (LOST: no ISR in the run, the boundary inside it), the call's instructions and accesses (count + digest, the
          ISR out), its seed, its stores before the ISR that the ISR can see (obs: the screen, the request, $9257, $904D,
          the timer), the ISR's changes AS IT LEFT THEM, what the ISR read of the bytes the call writes [address, value it
          saw, the entry's value], the final value of every byte the call wrote or the ISR changed [address, value]

ASSERTED: each natural request call's instructions tile its plain T; a replay's run ends at the RET; a phased run has at
most one ISR.  No ROM byte: offsets, T, phases, digests and game-RAM bytes (the seeds, the writes) only.

Usage:  python tools/borisacc.py [capture|verify] [--jobs N]   -> build/borisacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from ctrlmenu import GUARD, Fail
from harness import PC, T, IFF, SP
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import revealentry as RE
import revealcont as RC
from sparkacc import drive, STMem, STATES, FRAMES

FIXTURE = 'build/borisacc_fixture.json'
FD = 69888
IA = 32
ENTRY = 0x915F
REQ = 0x9160                    # $915F's LD A,n operand: the request
REC = 0x9250                    # Boris's record: +5 X, +6 Y
P1 = 0xFD80
MARKS = {0x9163: 'di', 0xA314: 'rs', 0xA34D: 'band', 0x917A: 'ei', 0x917B: 'ret'}
# the bytes read as instruction bytes that are state: the request (the respawn and the clear write it)
SMC = [REQ]
# $A314's own operands, rewritten at its entry before the code that reads them (band 1's count $A33D, band 3's $A349, the
# column $A355): not live state (bb.test's earlier gates' OPS) -- the writes' digests and the stores' counts leave them out
OPS = (0xA33D, 0xA349, 0xA355)
BASE_WORLD = 'death'


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


def obs(a):
    """the bytes the call writes that the ISR reads: the screen (its sprites), the request, $9257, $904D, the hurry timer"""
    return 0x4000 <= a < 0x5800 or a in (REQ, 0x9257, 0x904D, 0x8DBD, 0x8DBE)


class Rec:
    """the natural run's recorder: its $915F calls with the request up (sparkacc.drive's interface)"""

    def __init__(self, h):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.C = None
        self.calls, self.kept, self.ldar = [], [], []
        self.n_calls = 0
        self.pf = None
        self.armed = True
        self.tb = 0
        self.d_ins = 0
        self.frame = 0
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend

        def cont(t, timings):
            C = self.C
            if self.st_isr is None and C is not None:
                tt, k = t, 0
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        C['acc'].append('%d:%d;' % (tt - C['t0'] - C['D'] - C['I'], k))
                        C['D'] += d
                        self.d_ins += d
                        tt += d
                    tt += ts
                    k += ts
            return oc(t, timings)
        sim.contend = cont

    def before(self, frame):
        h, r, mem = self.h, self.h.sim.registers, self.h.sim.memory
        pc = r[PC]
        self.frame = frame
        if self.st_isr is not None:
            return False
        C = self.C
        if pc == ENTRY and C is None:
            self.n_calls += 1
            if mem[REQ] == 1:
                sp = r[SP]
                self.C = C = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'ins': [], 'isr': [],
                              'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'state': h.save_state(),
                              'x': mem[REC + 5], 'y': mem[REC + 6]}
        elif C is not None and pc == C['ret'] and r[SP] == C['sp'] + 2:
            self.end_call(frame)
        self.tb = r[T]
        self.d_ins = 0
        return True

    def after(self):
        C = self.C
        if C is None:
            return
        r = self.h.sim.registers
        o = self.tb - C['t0'] - (C['D'] - self.d_ins) - C['I']
        C['ins'].append('%d:%d;' % (o, r[T] - self.tb - self.d_ins))

    def end_call(self, frame):
        C = self.C
        self.C = None
        r = self.h.sim.registers
        Tp = r[T] - C['t0'] - C['D'] - C['I']
        o_prev = 0
        for s in C['ins']:
            o, t = map(int, s[:-1].split(':'))
            if o != o_prev:
                raise Fail('frame %d: $915F\'s instructions do not tile at %d (expected %d)' % (C['f'], o, o_prev))
            o_prev = o + t
        if o_prev != Tp:
            raise Fail('frame %d: $915F\'s instructions end at %d, its T %d' % (C['f'], o_prev, Tp))
        labels = set(x[2] for x in C['isr'])
        lost = [f for f in range(C['f'] + 1, frame + 1) if f not in labels]
        key = (dig(C['acc']), dig(C['ins']))
        self.calls.append([C['f'], C['ph'], Tp, len(C['acc']), key[0], len(C['ins']), key[1], C['isr'], lost,
                           C['x'], C['y']])
        self.kept.append((C['state'], C['sp'], C['ret'], C['f'], key, len(C['isr']), lost))

    def isr_begin(self, t_, label):
        self.isr_t0 = t_

    def isr_end(self, label):
        r = self.h.sim.registers
        T_ = r[T] - self.isr_t0
        C = self.C
        if C is not None:
            C['isr'].append([self.isr_t0 - C['t0'] - C['D'] - C['I'], T_, label, self.isr_t0 % FD])
            C['I'] += T_


def run_state(st):
    h = RE.new(st)
    rec = Rec(h)
    drive(h, rec, FRAMES, rng=random.Random('borisacc:' + st), pool=('O', 'P', 'Q', 'SPACE'))
    return st, rec


def seed_runs(m0, rd):
    runs = []
    for a in sorted(set(a for a in rd if a >= 0x4000) | set(SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return runs


def replay(state, sp_ret, pokes=()):
    """PLAIN (no contention, interrupts off) from the saved state to the RET: the seed, the accesses, the instructions, T,
       the marks, the writes (the final value of each byte written outside the stack)"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    m0 = bytes(h.memobj.m)
    rm = RE.SeedMem(h.memobj.m)
    log = []
    sim = RC.sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    if r[PC] != ENTRY:
        raise Fail('a replay not at $915F')
    rm.regs = r
    t0 = r[T]
    acc, ins, pcs, marks = [], [], [], []
    nlog = 0
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p in GUARD:
            raise Fail('replay: guard at $%04X' % p)
        tb = r[T]
        if p in MARKS:
            marks.append([MARKS[p], tb - t0])
        rm.tins[0] = tb
        sim.opcodes[mem[p]]()
        for t in log[nlog:]:
            acc.append('%d:%d;' % (t - t0, t - tb))
        nlog = len(log)
        ins.append('%d:%d;' % (tb - t0, r[T] - tb))
        pcs.append((p, tb - t0))
        if r[T] - t0 > 10 ** 6:
            raise Fail('replay: no RET')
    rm.regs = None
    wa = sorted(set(a for a, t in rm.wr if a not in OPS))
    fin = ['%d:%d;' % (a, m[a]) for a in wa]
    runs = []
    for a in wa:
        if runs and runs[-1][0] + runs[-1][1] == a:
            runs[-1][1] += 1
        else:
            runs.append([a, 1])
    return {'seed': seed_runs(m0, rm.rd), 'acc': [len(acc), dig(acc)], 'ins': [len(ins), dig(ins)], 'T': r[T] - t0,
            'marks': marks, 'wr': [sum(1 for a, t in rm.wr if a not in OPS), len(fin), dig(fin)], 'wa': runs}, pcs


def phased(state, sp_ret, shift, pokes=()):
    """FORCED (declared): a request call's entry state with `pokes`, moved to `shift` T before a frame boundary (the bottom
       border: nothing waits there), run with interrupts and contention to its RET -- and through an ISR its RET's end
       takes (the window's last 32 T: the pulse outlasts the DI)"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    for a, v in pokes:
        h.memobj.m[a] = v
    m0 = bytes(h.memobj.m)
    tm = STMem(h.memobj.m)
    regs = list(h.sim.registers)
    sim = CMIOSimulator(tm, config={})
    sim.registers[:] = regs
    h.sim, h.memobj = sim, tm
    tm.sim = sim
    sim.set_tracer(h.ports)
    r, ops = sim.registers, sim.opcodes
    if r[PC] != ENTRY:
        raise Fail('a phased run not at $915F')
    sim.t0, sim.t1 = -1, 1 << 40
    fd = FD
    r[T] = (r[T] // fd + 1) * fd - shift
    t0 = r[T]
    st = {'D': 0, 'I': 0, 'acc': [], 'in_isr': False, 'd_ins': 0}
    oc = sim.contend

    def cont(t, timings):
        if not st['in_isr']:
            tt, k = t, 0
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    d = DELAYS_48K[tt % FD]
                    st['acc'].append('%d:%d;' % (tt - t0 - st['D'] - st['I'], k))
                    st['D'] += d
                    st['d_ins'] += d
                    tt += d
                tt += ts
                k += ts
        return oc(t, timings)
    sim.contend = cont
    tm.regs = r
    tm.mode = 1
    ins, isr, wr_i, isr_info, t_end, chg = [], None, None, [], t0 + 4 * FD, None
    done = False
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            T_ = r[T] - isr[2]
            isr_info.append([isr[2] - t0 - st['D'] - st['I'], T_, isr[3]])
            st['I'] += T_
            st['in_isr'] = False
            tm.mode = 1
            isr = None
            chg = sorted([a, tm.m[a]] for a, old in tm.iold.items() if tm.m[a] != old)
        if isr is None and pc == ret and r[SP] == sp0 + 2:
            break
        if pc in GUARD or r[T] > t_end:
            raise Fail('phased run: guard at $%04X / no RET' % pc)
        tb = r[T]
        st['d_ins'] = 0
        ops[tm.m[pc]]()
        if isr is None:
            ins.append('%d:%d;' % (tb - t0 - (st['D'] - st['d_ins']) - st['I'], r[T] - tb - st['d_ins']))
        if r[IFF] and r[T] % fd < IA and isr is None:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, tm, pc):
                isr = (b0, s0, t_, t_ % fd)
                wr_i = len(tm.wr)
                st['in_isr'] = True
                tm.mode = 2
    tm.mode = 0
    tm.regs = None
    if len(isr_info) > 1:
        raise Fail('phased run: %d ISRs inside' % len(isr_info))
    # the call ends past the boundary by construction (the gates' shifts are inside it)
    Tp = r[T] - t0 - st['D'] - st['I']
    if not (0 <= shift < Tp + 1):
        raise Fail('phased run: the boundary at %d outside the call (T %d)' % (shift, Tp))
    m = tm.m
    chg = chg or []
    wa = sorted(set(a for a, v in tm.wr if a not in OPS) | set(a for a, v in chg))
    fin = [[a, m[a]] for a in wa]
    seen = sorted([a, v, m0[a]] for a, v in tm.irs.items() if a in tm.cw)
    after = {}
    for a, v in (tm.wr[wr_i:] if wr_i is not None else []):
        after[a] = v
    n_all = sum(1 for a, v in tm.wr if obs(a))
    n_before = sum(1 for a, v in tm.wr[:wr_i] if obs(a)) if wr_i is not None else n_all
    if isr_info:
        o, T_, ph = isr_info[0]
        isr_row = [o, T_, ph, m[0x8DBD] & 1]
    else:
        isr_row = None
    return {'isr': isr_row, 'lost': not isr_info, 'ins': [len(ins), dig(ins)], 'acc': [len(st['acc']), dig(st['acc'])],
            'T': Tp, 'seed': seed_runs(m0, tm.rd), 'wr_i': n_before, 'n_wr': n_all, 'chg': chg, 'seen': seen,
            'fin': fin, 'late': sum(1 for a, v, v0 in seen if a in after and after[a] != v)}


# the forced runs that keep the machine's instruction list ([pc, plain offset] of each): every place, to the T, for the
# gates (the window's edges, the stores)
ILIST = {'y0', 'y5', 'rom'}
# the phased targets: [name, pc, its visit (0 = the first)]; shifts after its start: 0 = AT (the point at its first T), 1 =
# 1 T in.  Rows: $A360 / $A364 are each row's two stores (visit 15 of $A364: the last row's second).  The entry AT is left
# out: a run begun at the entry samples the line first at its first instruction's end -- on the machine a point at the
# entry's first T is the CALL's end, and the ISR comes before $915F (the chain's split at the callee's entry)
TARGETS = [('entry', 0x915F, 0), ('dec', 0x9161, 0), ('retnz', 0x9162, 0), ('di', 0x9163, 0), ('st9160', 0x9164, 0),
           ('st8dbd', 0x9170, 0), ('call', 0x9177, 0), ('rs', 0xA314, 0), ('row0', 0xA360, 0), ('row15', 0xA364, 15),
           ('ei', 0x917A, 0), ('ret', 0x917B, 0)]
# ...and the window's last T, by their distance before the call's end (the RET's): the pulse is 32 T -- at 32 it falls
# wholly inside the window, at 31 it outlasts it (the RET's end takes it)
END_AT = (33, 32, 31, 30, 1)


def scenes(m):
    """the phased scenes' pokes from the base call's RAM: 'odd' -- Boris's record on P1's cells, the ODD ISR next ($8DBD
       even: the ISR INCs it first); 'odd3' -- the same, Boris's Y & 7 = 3; 'even' -- the EVEN ISR next"""
    px, py = m[P1 + 5], m[P1 + 6]
    odd = [(REQ, 1), (REC + 5, px & 0xF8), (REC + 6, py), (0x8DBD, m[0x8DBD] & 0xFE)]
    odd3 = [(REQ, 1), (REC + 5, px & 0xF8), (REC + 6, (py & 0xF8) | 3), (0x8DBD, m[0x8DBD] & 0xFE)]
    even = [(REQ, 1), (0x8DBD, m[0x8DBD] | 1)]
    return [('odd', odd), ('odd3', odd3), ('even', even)]


def forced_list():
    """the forced pokes (declared): every Y & 7, the screen's edges, rows aimed at the ROM, the bottom"""
    pos = lambda x, y: [(REQ, 1), (REC + 5, x), (REC + 6, y)]
    out = [('y%d' % k, pos(0x60 + 8 * k, 0x50 + k), None) for k in range(8)]
    out += [('left', pos(0x00, 0x60), None), ('right', pos(0xF8, 0x63), None), ('right2', pos(0xF0, 0x66), None),
            ('rom', pos(0x80, 0x04), None), ('top', pos(0x40, 0x0C), None), ('bottom', pos(0x90, 0xB7), None),
            ('low', pos(0x30, 0xBF), None)]
    return out


def world_job(st):
    tag, rec = run_state(st)
    reps = []
    for state, sp, ret, f, key, nisr, lost in rec.kept:
        x, _ = replay(state, (sp, ret))
        x['f'] = f
        x['same'] = nisr == 0 and not lost and x['acc'][1] == key[0] and x['ins'][1] == key[1]
        reps.append(x)
    forced, phase = [], []
    if st == BASE_WORLD:
        base = next((k for k in rec.kept if k[5] == 0 and not k[6]), None)
        if base is None:
            raise Fail('%s: no request call to base the forced and phased runs on' % st)
        state, sp, ret = base[0], base[1], base[2]
        m = state[0]
        for name, pk, _ in forced_list():
            x, xp = replay(state, (sp, ret), pk)
            fx = {'forced': name, 'pokes': pk, 'a': x}
            if name in ILIST:
                fx['ilist'] = [[p, o] for p, o in xp]
            forced.append(fx)
        for sname, pk in scenes(m):
            x, pcs = replay(state, (sp, ret), pk)
            shifts = []
            for name, tpc, nth in TARGETS:
                hits = [o for p, o in pcs if p == tpc]
                if len(hits) <= nth:
                    raise Fail('scene %s: no visit %d of $%04X' % (sname, nth, tpc))
                for d in ((1,) if tpc == ENTRY else (0, 1)):
                    shifts.append((name, tpc, nth, d, hits[nth] + d))
            for e in END_AT:
                shifts.append(('end-%d' % e, None, None, 0, x['T'] - e))
            for name, tpc, nth, d, shift in shifts:
                y = phased(state, (sp, ret), shift, pk)
                y.update({'scene': sname, 'target': name, 'pc': tpc, 'nth': nth, 'd': d, 'shift': shift, 'pokes': pk})
                phase.append(y)
    return {'tag': tag, 'n_calls': rec.n_calls, 'calls': rec.calls, 'replays': reps, 'forced': forced, 'phased': phase}


def capture(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, STATES))
    tot = {'calls': 0, 'requests': 0, 'replays': 0, 'lost': 0, 'isr_in': 0}
    for x in res:
        tot['calls'] += x['n_calls']
        tot['requests'] += len(x['calls'])
        tot['replays'] += len(x['replays'])
        tot['lost'] += sum(1 for c in x['calls'] if c[8])
        tot['isr_in'] += sum(1 for c in x['calls'] if c[7])
        ns = sum(1 for y in x['replays'] if y['same'])
        if x['calls'] or x['forced']:
            print('%-12s %6d calls, %3d requests, %3d replays (%d plain-comparable), %d forced, %d phased' % (
                x['tag'], x['n_calls'], len(x['calls']), len(x['replays']), ns, len(x['forced']), len(x['phased'])),
                flush=True)
    print('total:', tot)
    return {'meta': {'tool': 'tools/borisacc.py', 'no_rom_bytes': True,
                     'note': "$915F's Boris erase: access programs, instruction grids and its DI window, natural, replayed "
                             'and phased; seeds are game-RAM bytes read before written'},
            'frames': FRAMES, 'smc': SMC, 'ops': list(OPS), 'base_world': BASE_WORLD,
            'targets': [[n, '%04X' % p, k] for n, p, k in TARGETS], 'end_at': list(END_AT),
            'worlds': {x['tag']: x for x in res}, 'total': tot}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 20
    if cmd == 'capture':
        out = capture(jobs)
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture(jobs)))
        print('verify:', 'MATCH' if old == new else 'DIFFER')
        return 0 if old == new else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
