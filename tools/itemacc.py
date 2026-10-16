"""M7.115f (measurement) -- THE ITEM PASS ($8669) ON THE PASS'S ACCESS PROGRAM AND ITS INSTRUCTION GRID.

M7.114a put every main-loop pass on the frame clock by its ACCESS PROGRAM (passacc: each contended access's plain offset
from $8D0C and its T into its instruction) and M7.114d placed each interrupt by the pass's INSTRUCTION GRID (insgrid).
The item pass $8669 had neither: its ink cells, blit rows, the take's erase, the award's glyphs and the chirp's OUTs
waited nothing in the engine, and an interrupt inside a walk with a live entry was a grid MISS.  PT2 (M7.115e) pinned
what that costs: the potion's $890D 142 / 139 T early, the treasure room's passes (21 items drawn a frame) at other phases.

This oracle measures the item pass where it does its work:

  THE REAL LOAD (passacc's drive and keys, then P / O alternately -- potion.py's), free-running, contended:
    potion:f600 / potion:f700   a type-12 laid under P1 at the end of ISR F (potion.py's worlds), to the room's advance
    fruit:f600                  eight items laid at the end of ISR 600 (FRUIT_LAY: under P1, in his walk, far, Y 8 --
                                its blit rows aimed into the ROM --, phases 3 that expire at the first tick, the power-up
                                slot), to frame 1,300
    for each: every main-line pass from frame F - 2 [frame, wall phase, plain length, accesses, digest, ISRs inside
    [plain offset, T, label]] (passacc's row) and every $8669 CALL (below).
  SAVED STATES (every 48K capture holding items, and round1_2p48 with items laid under both players), FRAMES frames
    each with random keys (O P Q SPACE, and P2's 6 7 9 0 in 2P; seeded), contended: every $8669 call.

  calls   every $8669 CALL from the chain ($8D4C): [frame, the wall phase at its entry, its plain T to the RET (the
          ISRs and the delays out), the accesses (count, digest of 'o:k;' -- o its plain offset from the entry, k its T
          into its instruction), the instructions (count, digest of 'o:t;'), the ISRs inside [o, T, label], marks
          (the visits of MARKS' PCs), the handler (a power-up's $8838 JP (HL): [target, o] -- its span, to its RET into
          $87B2's caller, is OPAQUE: its accesses and instructions out, its T in o)]
  replays the FIRST call of each distinct (accesses, instructions) pair in a world, and EVERY call that takes, expires,
          dispatches, spawns or erases, run again from its entry PLAIN (no contention, interrupts OFF): the SEED (every
          byte >= $4000 read before written, as [start, hex] runs; the self-modified operands and opcodes SMC at their
          values), the accesses and the instructions to the handler's entry or the RET (count + digest, the same
          strings), the T, the marks; `same` = the replay's digests are the natural call's (an ISR inside a natural call
          can move what the rest of the walk reads: such a call is kept, flagged, and not a model row)
  forced  FORCED replays (declared): calls taken from the worlds above with one poke at the entry -- the flood ($FECE 1)
          and the storm ($FECF 1) on a walk with live entries (the weather skips $871E / $8725 to the blit), P1 carried
          (+$5A bit 4: the walk every pass, $8674's JR nz) -- the branches no natural run here takes

ASSERTED: the replay's own run ends at the RET or the handler's entry; no access or instruction is recorded inside a
handler; a natural call after its handler returns makes no access before its RET.  No ROM byte: offsets, T, phases,
digests and game-RAM bytes (the seeds) only.

Usage:  python tools/itemacc.py [capture|verify] [--jobs N]   -> build/itemacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import Harness, PC, T, IFF, SP, A as RA
from skoolkit.cmiosimulator import DELAYS_48K
import portconfig as pcfg
import revealentry as RE
import revealcont as RC
from passacc import SCRIPT
import potion as PO

FIXTURE = 'build/itemacc_fixture.json'
FD = 69888
ENTRY = 0x8669
# the PCs whose visits a call records (coverage, and the replay rule)
MARKS = {0x8689: 'walk', 0x8684: 'gate', 0x86A9: 'entry', 0x87A5: 'remap', 0x87B8: 'live', 0x87D3: 'xin', 0x87E2: 'yin',
         0x87E7: 'take', 0x8814: 'p2idx', 0x86E6: 'erase', 0x8774: 'solid', 0x86E3: 'expire', 0x8713: 'aged',
         0x86D3: 'tick', 0x8721: 'noflood', 0x8728: 'ink', 0x8730: 'bank0', 0x873E: 'rng', 0xA2C2: 'blit',
         0xA314: 'restore', 0x80FA: 'award', 0x8144: 'hicopy', 0x8CB1: 'chirp', 0x8838: 'dispatch', 0x89E4: 'points',
         0x8A12: 'power', 0x8A0B: 'r80'}
KEEP = {'take', 'expire', 'dispatch', 'erase', 'p2idx', 'hicopy'}
# the self-modified operands / opcodes the item pass reads as state (cost8669's list): seeded at their entry values
# the LD A,R sites the item pass reads R at (the ink's $873E, the power-up's narrow $8A2E and wide $8A38 draws): a replay
# records A after each, so a model fed the machine's draws walks the machine's path (the engine's R is a stand-in)
R_SITES = (0x873E, 0x8A2E, 0x8A38)
SMC = [0x8680, 0x86CD, 0x86CF, 0x872C, 0x8769, 0x8828, 0x87B2, 0xA304, 0xA307, 0xA30C, 0xA33D, 0xA349, 0xA355, 0x81BB]
REAL = [('potion:f600', 600, 2700), ('potion:f700', 700, 2800), ('fruit:f600', 600, 1300)]
# fruit:f600 -- [slot address, byte0 (X | type), byte1 (Y | phase)], X / Y relative to P1 where `p` says so
FRUIT_LAY = [(0x9605, ('p', 0, 3), ('p', 0, 0)),          # under P1: taken at once
             (0x9607, ('p', 32, 5), ('p', 0, 1)),         # in his walk right
             (0x9609, ('p', -32, 0), ('p', 0, 2)),        # ...and left
             (0x960B, (0xC0, 7), (0x40, 3)),              # far, phase 3: expires at the first tick
             (0x960D, (0x80, 9), (0x08, 1)),              # Y 8: its rows aimed at the ROM
             (0x960F, (0x40, 11), (0x60, 2)),
             (0x9611, (0xE0, 2), (0xA0, 3)),              # far, expires
             (0x9603, (0xD0, 4), (0x30, 3))]              # the power-up slot (bank 1), far, expires
STATES = ['candycane', 'ellight', 'elfire', 'elwater', 'water', 'fallcandy', 'peachcane', 'yellowcross2', 'umbrella',
          'fruit', 'powerup', 'spawn', 'crown', 'bottle', 'sweet', 'redcross', 'round1_2p48']
FRAMES = 600
# round1_2p48: items under each player and beside them (P2's take: $8814 INC A)
TWO_P_LAY = [(0x9605, ('p1', 0, 3), ('p1', 0, 0)), (0x9607, ('p2', 0, 6), ('p2', 0, 0)),
             (0x9609, ('p2', 32, 1), ('p2', 0, 1)), (0x960B, ('p1', 32, 8), ('p1', 0, 2))]


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


def lay(m, spec):
    """the items of a LAY list into the table, X / Y relative to P1 (or P2) where the spec says so"""
    pos = {'p': (m[0xFD85], m[0xFD86]), 'p1': (m[0xFD85], m[0xFD86]), 'p2': (m[0xFD8F], m[0xFD90])}
    for a, b0, b1 in spec:
        if isinstance(b0[0], str):
            x = (pos[b0[0]][0] + b0[1]) & 0xFF
            v0 = (x & 0xF0) | b0[2]
        else:
            v0 = (b0[0] & 0xF0) | b0[1]
        if isinstance(b1[0], str):
            y = (pos[b1[0]][1] + b1[1]) & 0xFF
            v1 = (y & 0xF8) | b1[2]
        else:
            v1 = (b1[0] & 0xF8) | b1[1]
        m[a], m[a + 1] = v0, v1


class Rec:
    """the natural run's recorder: the main line's passes (`win`: frames to record them in) and its $8669 calls"""

    def __init__(self, h, passes_from=None, passes_to=None):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.P = None                       # the pass being recorded
        self.C = None                       # the call being recorded
        self.passes, self.calls, self.kept, self.chirps = [], [], [], []
        self.pf, self.pt = passes_from, passes_to
        self.seen = set()
        self.pc = 0
        self.tb = 0
        self.d_ins = 0                      # the delays of the instruction being run (main line)
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend
        self._oc = oc

        def cont(t, timings):
            if self.st_isr is None:
                P, C = self.P, self.C
                tt, k = t, 0
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        if P is not None:
                            P['acc'].append('%d:%d;' % (tt - P['t0'] - P['D'] - P['I'], k))
                            P['D'] += d
                        if C is not None and not C['in_pu']:
                            C['acc'].append('%d:%d;' % (tt - C['t0'] - C['D'] - C['I'], k))
                        if C is not None:
                            C['D'] += d
                        self.d_ins += d
                        tt += d
                    tt += ts
                    k += ts
            return oc(t, timings)
        sim.contend = cont

    def before(self, frame):
        """at an instruction boundary on the main line: the pass / call bookkeeping; True = the instruction is the main
           line's (record its grid entry after it runs)"""
        h, r, mem = self.h, self.h.sim.registers, self.h.sim.memory
        pc = r[PC]
        if self.st_isr is not None:
            return False
        if pc == 0x8D0C:
            P = self.P
            if P is not None:
                P['len'] = r[T] - P['t0'] - P['D'] - P['I']
                self.passes.append([P['f'], P['ph'], P['len'], len(P['acc']), dig(P['acc']), P['isr']])
            self.P = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'isr': []} \
                if self.pf is not None and self.pf <= frame <= self.pt else None
        C = self.C
        if pc == ENTRY and C is None:
            sp = r[SP]
            self.C = C = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'ins': [], 'isr': [],
                          'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'marks': {}, 'in_pu': False,
                          'pu': None, 'pu_sp': None, 'pu_ret': None, 'after_pu': 0, 'state': h.save_state(), 'outs': []}
        elif C is not None:
            if C['in_pu']:
                if pc == C['pu_ret'] and r[SP] == C['pu_sp'] + 2:
                    C['in_pu'] = False
                    C['pu'].append(r[T] - C['t0'] - C['D'] - C['I'])
                    C['acc_mark'] = len(C['acc'])
            elif pc == C['ret'] and r[SP] == C['sp'] + 2:
                self.end_call(r)
                C = None
        C = self.C
        if C is not None and not C['in_pu']:
            name = MARKS.get(pc)
            if name:
                C['marks'][name] = C['marks'].get(name, 0) + 1
            if pc == 0x8838:                          # JP (HL): the handler -- opaque from its target
                C['pu_next'] = True
            if pc == 0x867C and 'ctr_o' not in C:     # the edge's counter read: the ISRs before it moved the counters
                C['ctr_o'] = r[T] - C['t0'] - C['D'] - C['I']
            if pc == 0x8CB4:                          # the chirp's OUT: its start on the wall clock [frame, phase]
                C['outs'].append([frame, r[T] % FD])
        self.pc = pc
        self.tb = r[T]
        self.d_ins = 0
        return True

    def after(self):
        """after a main-line instruction: its grid entry (plain offset, plain T) and the handler's entry"""
        C = self.C
        if C is None or C['in_pu']:
            return
        r = self.h.sim.registers
        o = self.tb - C['t0'] - (C['D'] - self.d_ins) - C['I']
        C['ins'].append('%d:%d;' % (o, r[T] - self.tb - self.d_ins))
        if C.pop('pu_next', False):
            mem = self.h.sim.memory
            sp = r[SP]
            C['in_pu'] = True
            C['pu'] = [r[PC], r[T] - C['t0'] - C['D'] - C['I']]
            C['pu_sp'] = sp
            C['pu_ret'] = mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8)

    def end_call(self, r):
        C = self.C
        self.C = None
        Tp = r[T] - C['t0'] - C['D'] - C['I']
        if C['pu'] is not None and 'acc_mark' in C:
            C['after_pu'] = len(C['acc']) - C['acc_mark']
        key = (dig(C['acc']), dig(C['ins']))
        ctr = sum(1 for x in C['isr'] if x[0] <= C['ctr_o']) if 'ctr_o' in C else 0
        row = [C['f'], C['ph'], Tp, len(C['acc']), key[0], len(C['ins']), key[1], C['isr'],
               dict(sorted(C['marks'].items())), C['pu'], C['after_pu'], ctr]
        self.calls.append(row)
        if C['outs']:
            self.chirps.append([len(self.calls) - 1, C['outs']])
        keep = key not in self.seen or any(k in KEEP for k in C['marks'])
        self.seen.add(key)
        if keep:
            self.kept.append((len(self.calls) - 1, C['state']))

    def isr_begin(self, t_):
        self.isr_t0 = t_

    def isr_end(self, label):
        T_ = self.h.sim.registers[T] - self.isr_t0
        for X in (self.P, self.C):
            if X is not None:
                X['isr'].append([self.isr_t0 - X['t0'] - X['D'] - X['I'], T_, label])
                X['I'] += T_


def run_real(wd):
    """a real-load world: passacc's drive and keys, potion.py's P / O after; the potion or FRUIT_LAY at the end of ISR F"""
    tag, F, END = wd
    h, m, r = world('boot')
    kf = PO.keyf(expand(SCRIPT))
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD
    nb = (r[T] // fd + 1) * fd
    rec = Rec(h, F - 2, END)
    frame, in_scan, pending, isr, adv = 0, False, None, None, None
    cm.keys(h, kf(0))
    while frame <= END:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if in_scan:
                pending = kf(L)
            else:
                cm.keys(h, kf(L))
            if L == F:
                if tag.startswith('potion'):
                    m[0x9603] = (m[0xFD85] & 0xF0) | 12
                    m[0x9604] = (m[0xFD86] & 0xF8) | 1
                else:
                    lay(m, FRUIT_LAY)
            rec.st_isr = None
            rec.isr_end(L)
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('%s: guard at $%04X' % (tag, pc))
        if pc == 0xF7B8:
            in_scan = True
        main = rec.before(frame)
        if main and pc == 0x97F8 and frame > F and adv is None:
            adv = frame
            if tag.startswith('potion'):
                break
        ops[mem[pc]]()
        if main:
            rec.after()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                rec.st_isr = isr
                rec.isr_begin(t_)
    return tag, rec, adv


def run_state(st):
    """a saved state's world: FRAMES frames of random keys (seeded by the name), every $8669 call"""
    h = RE.new(st)
    m, r = h.memobj.m, h.sim.registers
    two = st == 'round1_2p48'
    if two:
        lay(m, TWO_P_LAY)
    rng = random.Random('itemacc:' + st)
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    rec = Rec(h)
    frame, isr, keyrun, cur = 0, None, 0, []
    pool = ('O', 'P', 'Q', 'SPACE') + (('6', '7', '9', '0') if two else ())
    while frame < FRAMES:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            if keyrun <= 0:
                keyrun = rng.randint(4, 30)
                cur = [k for k in pool if rng.random() < 0.4]
            keyrun -= 1
            cm.keys(h, cur)
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            rec.st_isr = None
            rec.isr_end(isr[2])
            isr = None
        if pc in GUARD:
            raise Fail('%s: guard at $%04X' % (st, pc))
        main = rec.before(frame)
        ops[mem[pc]]()
        if main:
            rec.after()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                rec.st_isr = isr
                rec.isr_begin(t_)
    return st, rec, None


def replay(state, pokes=(), ctr=0):
    """from a call's entry, PLAIN (no contention, interrupts off): the seed, the accesses, the instructions, T, marks and
       the handler's entry -- the run stops there, or at the RET.  `ctr`: the ISRs the natural call took before its
       edge read ($867C) -- both frame counters ($8DB6, $8DBD: sixteen bits) advanced by it at the entry, as the read saw
       them"""
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    for a in (0x8DB6, 0x8DBD):
        v = (m[a] | (m[a + 1] << 8)) + ctr
        m[a], m[a + 1] = v & 0xFF, (v >> 8) & 0xFF
    m0 = bytes(h.memobj.m)
    rm = RE.SeedMem(h.memobj.m)
    log = []
    sim = RC.sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    if r[PC] != ENTRY:
        raise Fail('a replay not at $8669')
    rm.regs = r
    sp0 = r[SP]
    ret = mem[sp0] | (mem[(sp0 + 1) & 0xFFFF] << 8)
    t0 = r[T]
    acc, ins, marks, pu, draws, di = [], [], {}, None, [], []
    nlog = 0
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p in GUARD:
            raise Fail('replay: guard at $%04X' % p)
        name = MARKS.get(p)
        if name:
            marks[name] = marks.get(name, 0) + 1
        tb = r[T]
        if p in (0x87F9, 0x881F):                     # the take's DI, and LD C,$28's end (the CALL $8CB1 after the EI)
            di.append(tb - t0)
        sim.opcodes[mem[p]]()
        for t in log[nlog:]:
            acc.append('%d:%d;' % (t - t0, t - tb))
        nlog = len(log)
        ins.append('%d:%d;' % (tb - t0, r[T] - tb))
        if p in R_SITES:
            draws.append([p, r[RA]])
        if p == 0x8838:                               # JP (HL): the handler's entry ends the replay
            pu = [r[PC], r[T] - t0]
            break
        if r[T] - t0 > 2 * 10 ** 6:
            raise Fail('replay: no RET')
    rm.regs = None
    runs = []
    for a in sorted(set(a for a in rm.rd if a >= 0x4000) | set(SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return {'seed': runs, 'acc': [len(acc), dig(acc)], 'ins': [len(ins), dig(ins)], 'T': r[T] - t0,
            'marks': dict(sorted(marks.items())), 'pu': pu, 'draws': draws, 'di': di}


FORCED = [('flood', [(0xFECE, 1)]), ('storm', [(0xFECF, 1)]), ('carried', [(0xFDDA, None)])]


def world_job(wd):
    tag, rec, adv = run_real(wd) if isinstance(wd, tuple) else run_state(wd)
    reps = []
    for i, st in rec.kept:
        c = rec.calls[i]
        x = replay(st, ctr=c[11])
        x['call'], x['ctr'], x['row'] = i, c[11], c
        x['same'] = x['acc'][1] == c[4] and x['ins'][1] == c[6] if x['pu'] is None else \
            x['marks'] == {k: v for k, v in c[8].items()}
        reps.append(x)
    # the forced replays: the first kept call with live entries and no take / handler, poked
    forced = []
    for i, st in rec.kept:
        c = rec.calls[i]
        if c[8].get('entry', 0) >= 2 and not any(k in c[8] for k in ('take', 'dispatch', 'expire')):
            for name, pokes in FORCED:
                pk = [(a, (st[0][a] | 0x10) if v is None else v) for a, v in pokes]
                x = replay(st, pk)
                x['call'], x['forced'] = i, name
                x['pokes'] = pk
                forced.append(x)
            break
    out = {'tag': tag, 'n_calls': len(rec.calls), 'replays': reps, 'forced': forced,
           'cover': {}, 'bad_after_pu': sum(1 for c in rec.calls if c[10])}
    for c in rec.calls:
        for k, v in c[8].items():
            out['cover'][k] = out['cover'].get(k, 0) + v
    if rec.pf is not None:                        # a real-load world: its passes, its calls (marks out), its chirps
        out['passes'] = rec.passes
        out['advance'] = adv
        out['calls'] = [c[:8] + c[9:] for c in rec.calls]
        out['chirps'] = rec.chirps
    return out


def capture(jobs):
    jobsl = list(REAL) + list(STATES)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, jobsl))
    cover = {}
    for x in res:
        for k, v in x['cover'].items():
            cover[k] = cover.get(k, 0) + v
        if x['bad_after_pu']:
            raise Fail('%s: %d calls made accesses after their handler returned' % (x['tag'], x['bad_after_pu']))
        nr = len(x['replays'])
        ns = sum(1 for y in x['replays'] if y['same'])
        print('%-14s %5d calls, %4d replays (%d the natural\'s), %d forced%s' % (
            x['tag'], x['n_calls'], nr, ns, len(x['forced']),
            ', %d passes, advance %s' % (len(x['passes']), x['advance']) if 'passes' in x else ''), flush=True)
    print('cover:', ' '.join('%s=%d' % kv for kv in sorted(cover.items())))
    return {'meta': {'tool': 'tools/itemacc.py', 'no_rom_bytes': True,
                     'note': 'the item pass ($8669): access programs and instruction grids, natural and replayed; '
                             'seeds are game-RAM bytes read before written'},
            'script': [[k, v] for k, v in SCRIPT], 'real': [list(w) for w in REAL], 'fruit_lay': FRUIT_LAY,
            'two_p_lay': TWO_P_LAY, 'frames': FRAMES, 'smc': SMC, 'marks': {('%04X' % k): v for k, v in MARKS.items()},
            'worlds': {x['tag']: x for x in res}, 'cover': cover}


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
