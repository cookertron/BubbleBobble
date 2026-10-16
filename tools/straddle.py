"""M7.115g (measurement) -- THE CALLEE AN INTERRUPT FALLS INSIDE: a census.

The engine runs a main-loop pass callee by callee (chainWalk); when the frame's interrupt point falls at or before a
callee's entry the pass is CUT there and the callee runs after the ISR (M7.114a), and a counter read past the point sees
the ISR's INC (ctrRead).  A callee the point falls INSIDE runs whole before the ISR: its later reads see the world as it
was before the interrupt.  On the machine they see what the ISR wrote -- M7.115f found two (IA3's pins): the treasure
room's item walk (its box tests read P1 where the odd ISR moved him) and $931A's probes.  This census asks the machine
how often that matters, callee by callee:

  NATURAL  every main-loop pass of a free-running contended world; every chain CALL ($8D22 CALL z,$7FFC, $8D25..$8D5B,
           $8D5E CALL $8E3A) recorded from its entry to its RET: the instructions it runs (PCs, the ISR's out), its
           contended accesses (instruction index, T into it), its writes outside the stack (address, value), its plain T.
           A call with exactly one ISR accepted inside it and no HALT is a STRADDLE: the ISR's plain offset from the entry,
           its label and parity, the bytes it changed (outside its stack), and which of them the callee READ after it.
  REPLAYED each straddle from the callee's entry, plain and atomic (no interrupt):
           before  the entry's state -- what the engine does when the point falls inside (the callee whole before the ISR)
           after   the entry's state with the ISR's changes laid over it -- the callee whole AFTER the ISR (the engine's
                   cut at the entry, and its edge-read cut: BB_EDGE_LOOK)
           each compared with the natural call: 'same' (instructions, accesses and writes), 'wr' (the same instructions
           and accesses, other writes), 'acc' (the same instructions, other accesses), 'path' (other instructions: the
           first index they part at and the PCs there), 'halt' / 'long' (the replay meets a HALT / runs away).

WORLDS: the real load's three (itemacc's REAL: the potion at ISR 600 / 700 to the room's advance, fruit:f600 to 1,300)
and every saved state on the 48K branch, FRAMES frames of random keys each (seeded by the name; P2's keys in 2P).

No ROM byte: PCs, offsets, T, labels and game-RAM addresses only.

Usage:  python tools/straddle.py [capture|verify] [--jobs N]   -> build/straddle_fixture.json
"""
import sys, os, json, hashlib, random, copy
from array import array
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import Mem, Ports, PC, T, IFF, SP, R
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import portconfig as pcfg
import revealentry as RE
import revealcont as RC
from passacc import SCRIPT
import potion as PO
import itemacc as IA

FIXTURE = 'build/straddle_fixture.json'
FD = 69888
FRAMES = 600
# the chain's CALLs: callee entry -> its return address (the byte after its CALL)
CHAIN = {0x7FFC: 0x8D25, 0x8FA5: 0x8D28, 0x8FE7: 0x8D2B, 0x900B: 0x8D2E, 0xA9ED: 0x8D31, 0x9961: 0x8D34,
         0x915F: 0x8D37, 0x948F: 0x8D3A, 0x7E80: 0x8D3D, 0x93DC: 0x8D40, 0x9E50: 0x8D43, 0xA09A: 0x8D46,
         0xA824: 0x8D49, 0xC002: 0x8D4C, 0x8669: 0x8D4F, 0x9037: 0x8D52, 0x925A: 0x8D55, 0x931A: 0x8D58,
         0x9AEB: 0x8D5B, 0x8E2A: 0x8D5E, 0x8E3A: 0x8D61}
# the edge detectors' frame-counter reads (BB_EDGE_LOOK's): the engine cuts the pass at the callee's ENTRY when the
# read's instruction starts at or past the point (the callee whole after the ISR), else runs it whole before
EDGE_READ = {0xA824: 0xA829, 0xA9ED: 0xA9FC, 0x9037: 0x903D, 0x8669: 0x867C}
# the frame counters (ctrRead gives a read past the point the ISR's INC)
CTR = (0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE)
# M7.115g's gate: the callees it cuts -- every row the old rule got wrong, and every SAMPLE-th of the rest, carry what a
# fresh engine needs to run the call with the machine's ISR at the machine's point (bb.test.js SG2); M7.115h's three more
# (the jump tone's arms, the contact's scans and the kill, the tally's slots: bb.test.js SH2); M7.115j's boss tick (P1's Y /
# X read after the ISR, and the screen its blits and the ISR's sprites share: bb.test.js BA5); M7.115k's sparkle walk (the
# table a pop's seed writes, the screen its blits OR and the ISR's sprites share: bb.test.js SK5)
GATE = {0x8669, 0x931A, 0x8FA5, 0x925A, 0x8E3A, 0xA9ED, 0xC002}
SAMPLE = 40
# ...$8E3A every tenth (its countdown, drain and anger paths are a few of a world's straddles); $A9ED every tenth, and
# EVERY row whose ISR run late writes otherwise (LATE_KEEP: its blits' screen bytes)
SAMPLE_AT = {0x8E3A: 10, 0xA9ED: 10}
LATE_KEEP = {0xA9ED, 0xC002}
# M7.115k: the sparkle walk's kids' own operands ($A304 the blit's column, $A355 / $A349 / $A33D the restore's), rewritten
# at every entry before the code that reads them -- not state, the engine computes them and stores none: out of 'fin'
OPS_C002 = (0xA304, 0xA33D, 0xA349, 0xA355)
# operands a gate callee READS as instruction bytes (the seed's rule leaves an instruction's own bytes out): the item
# pass's (itemacc's SMC); $8E3A's -- the clear latch $8E3B ($8E3A LD A,n), the drain's base $8F3A ($8F39 SUB n), the
# one-left latch $90AA ($90A9 LD A,n) and the walk's SET / RES $90D0 ($90CF's second byte, the respawn's calm XORs it)
SMC_SEED = {0x8669: set(IA.SMC), 0x8E3A: {0x8E3B, 0x8F3A, 0x90AA, 0x90D0},
            # M7.115j: the boss tick's (tools/bossacc.py's SMC): $A9FF SUB n, $AA05 LD A,n, the spawn's LD A,n, the draw's
            # LD DE,nn / LD BC,nn / LD DE,nn, the comparator pair $A98F / $A990 (EXECUTED)
            0xA9ED: {0xA85C, 0xA8C2, 0xA8C3, 0xA8DB, 0xA8DC, 0xA8FD, 0xA8FE, 0xA98F, 0xA990, 0xAA00, 0xAA06}}
# M7.115h: $8E3A's paths no natural straddle walks, FORCED from FORCED_WORLD's first $8E3A entry with these pokes and
# replayed plain and atomic (no contention, no interrupt) to its RET: the machine's grid for each (bb.test.js SH2).  The
# one-left anger's first walk (one slot, four slots: $90AA open, one enemy left), the countdown's advance (latched, the
# timer $0180) and the drain's band with an item left ($8DBE - $8F3A = 8: its advance)
FORCED_WORLD = 'round1_48'
_ROUND = [(0x8E3B, 0), (0xFED1, 0), (0x8609, 1)]
FORCED_8E3A = [
    ('anger: the first walk, one slot', _ROUND + [(0xAA57, 3), (0xFD9B, 0x80), (0x90AA, 0)]),
    ('anger: the first walk, four slots', _ROUND + [(0xAA57, 6), (0xFD9B, 0x80), (0xFDA5, 0), (0xFDAF, 0), (0xFDB9, 0),
                                                    (0x90AA, 0)]),
    ('countdown: the advance', [(0x8E3B, 1), (0x8DBE, 1), (0x8DBD, 0x80)]),
    ('drain: the band, an item left', [(0x8E3B, 0), (0xFED1, 1), (0x8F3A, 5), (0x8DBE, 13), (0x8DBD, 0)] +
                                      [(a, 0) for a in range(0x9605, 0x9605 + 62)] + [(0x9605, 0x21)]),
]
STATES = sorted(os.path.splitext(f)[0] for f in os.listdir('build') if f.endswith('.pkl'))


def dig(seq):
    if isinstance(seq, str):
        return hashlib.sha1(seq.encode()).hexdigest()[:16]
    return hashlib.sha1(repr(seq).encode()).hexdigest()[:16]


class TrackMem(Mem):
    """the natural run's memory: the census's write and read hooks (cheap when off)"""
    __slots__ = ('cen',)

    def __init__(self, data, cen):
        Mem.__init__(self, data)
        self.cen = cen

    def __getitem__(self, i):
        c = self.cen
        if c.sd_on and i not in c.sd_seen:
            p = c.cur_pc
            if not (p <= i < p + 4):                  # not this instruction's own bytes (revealentry's SeedMem rule)
                c.sd_seen.add(i)
                if i >= 0x4000:
                    c.sd_rd.append(i)
        if c.rd_on and i in c.changed:
            rd = c.C['rd']
            if i in rd:
                rd[i][1] += 1
            else:
                rd[i] = ['%04X' % c.cur_pc, 1]
        return self.m[i]

    def __setitem__(self, i, v):
        if i < 0x4000:
            self.rom_writes += 1
            return
        c = self.cen
        w = c.wmode
        if w:
            sp = c.regs[SP]
            if c.sd_on:
                c.sd_seen.add(i)
            if not (sp - 64 <= i < sp + 64):
                if w == 1:
                    c.C['wr'].append((i, v))
                    if c.rd_on:
                        c.changed.discard(i)
                else:
                    if i not in c.isr_old:
                        c.isr_old[i] = self.m[i]
                    c.isr_wr.append((i, v))
        self.m[i] = v


class Census:
    """the natural run's recorder: every chain call, and the straddles' rows (replayed at the call's RET)"""

    def __init__(self, rep, tag):
        self.rep, self.tag = rep, tag
        self.h = self.regs = None
        self.C = None
        self.st_isr = None
        self.isr_t0 = 0
        self.wmode = 0
        self.rd_on = False
        self.changed = set()
        self.isr_old = {}
        self.isr_wr = []
        self.rows, self.calls, self.blocks = [], {}, {}
        self.frame = 0
        self.cur_pc = 0
        self.r0 = 0
        self.pt = None
        self.keys_due = False
        self.sd_on = False
        self.sd_seen = set()
        self.sd_rd = []
        self.tb = 0
        self.d0 = 0
        self.n_gate = {}
        self.e3a = None

    def attach(self, h):
        """the natural run on a TrackMem: a fresh CMIOSimulator over the same bytes, registers and keyboard, every
           access through the contention hook"""
        tm = TrackMem(h.memobj.m, self)
        sim = CMIOSimulator(tm, config={})
        sim.registers[:] = list(h.sim.registers)
        h.sim, h.memobj = sim, tm
        tm.sim = sim
        sim.set_tracer(h.ports)
        self.h, self.regs = h, sim.registers
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend

        def cont(t, timings):
            C = self.C
            if C is not None and self.st_isr is None:
                tt, k, i = t, 0, len(C['pcs']) - 1
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        C['acc'].append((i, k))
                        C['D'] += d
                        tt += d
                    tt += ts
                    k += ts
            return oc(t, timings)
        sim.contend = cont

    def before(self, pc):
        """at a main-line instruction boundary (no ISR running)"""
        C = self.C
        self.cur_pc = pc
        if C is not None:
            if C['g'] is not None:                    # the gate callees: each instruction's plain start, and its T after
                self.tb, self.d0 = self.regs[T], C['D']
                self.sd_on = True
            C['pcs'].append(pc)
            if self.h.memobj.m[pc] == 0x76:
                C['halt'] = True
            if pc == C['rdpc'] and C['o_read'] is None:
                C['o_read'] = self.regs[T] - C['t0'] - C['D'] - C['I']

    def after(self):
        """after a main-line instruction: a chain call's entry or its RET"""
        r, m = self.regs, self.h.memobj.m
        pc = r[PC]
        C = self.C
        if C is not None:
            g = C['g']
            if g is not None:
                self.sd_on = False
                if C['pu'] is None:
                    g.append('%d:%d;' % (self.tb - C['t0'] - self.d0 - C['I'], r[T] - self.tb - (C['D'] - self.d0)))
                    if C['pcs'][-1] == 0x8838 and C['a'] == 0x8669:
                        C['pu'] = len(g)                  # the handler's JP (HL): the grid ends there (itemacc's rule)
                if C['pcs'][-1] in IA.R_SITES and C['a'] == 0x8669:
                    C['draws'].append([C['pcs'][-1], r[0]])
            if pc == C['ret'] and r[SP] == C['sp0'] + 2:
                self.end_call()
            return
        ret = CHAIN.get(pc)
        if ret is not None:
            sp = r[SP]
            if m[sp] | (m[(sp + 1) & 0xFFFF] << 8) == ret:
                self.C = {'a': pc, 'f': self.frame, 't0': r[T], 'D': 0, 'I': 0, 'sp0': sp, 'ret': ret,
                          'state': self.h.save_state(), 'pcs': array('H'), 'acc': [], 'wr': [], 'isr': None,
                          'nisr': 0, 'rd': {}, 'halt': False, 'chg': None, 'rdpc': EDGE_READ.get(pc),
                          'o_read': None, 'isr_i': None, 'dR': 0, 'g': [] if pc in GATE else None, 'pu': None,
                          'draws': []}
                if pc == 0x8E3A and self.e3a is None:
                    self.e3a = self.C['state']        # M7.115h: the forced replays' entry (FORCED_8E3A)
                self.wmode = 1
                self.sd_seen = set()
                self.sd_rd = []

    def isr_begin(self, t_, r0):
        self.isr_t0 = t_
        self.r0 = r0
        C = self.C
        if C is not None:
            C['nisr'] += 1
            if C['nisr'] == 1:
                C['isr_i'] = len(C['pcs'])
                C['wr_i'] = len(C['wr'])
                C['pt'] = self.pt
                self.keys_due = True                  # the keys the ISR reads: at its first instruction (isr_keys)
            self.wmode = 2
            self.isr_old = {}
            self.isr_wr = []
            self.rd_on = False
            self.sd_on = False

    def isr_keys(self):
        """at the ISR's first instruction, after the driver's key change at the frame boundary (run_state's) and before
           its change at the ISR's end (run_real's): the keys the ISR reads"""
        self.keys_due = False
        if self.C is not None:
            self.C['keys'] = (copy.deepcopy(self.h.ports.pressed), self.h.ports.kempston)

    def isr_end(self, label):
        C = self.C
        if C is None:
            return
        T_ = self.regs[T] - self.isr_t0
        m = self.h.memobj.m
        if C['nisr'] == 1:
            chg = {a: m[a] for a, old in self.isr_old.items() if m[a] != old}
            C['isr'] = [self.isr_t0 - C['t0'] - C['D'] - C['I'], T_, label, m[0x8DBD] & 1]
            C['chg'] = chg
            C['dR'] = (self.regs[R] - self.r0) & 0x7F
            C['isr_wr'] = self.isr_wr
            C['isr_T'] = T_
            self.changed = set(chg)
            self.rd_on = True
        else:
            self.rd_on = False
        C['I'] += T_
        self.wmode = 1

    def end_call(self):
        C = self.C
        self.C = None
        self.wmode = 0
        self.rd_on = False
        a = '%04X' % C['a']
        n = self.calls.setdefault(a, [0, 0])
        n[0] += 1
        if C['isr'] is None:
            return
        if C['nisr'] > 1 or C['halt']:
            self.blocks[a] = self.blocks.get(a, 0) + 1
            return
        n[1] += 1
        nat = (C['pcs'], C['acc'], C['wr'])
        Tp = self.regs[T] - C['t0'] - C['D'] - C['I']
        chg, i, dR = C['chg'], C['isr_i'], C['dR']
        ctr = {x: v for x, v in chg.items() if x in CTR}
        self.rep.keys(C['keys'])
        vx = self.rep.compare(C['state'], nat, cut=(i, chg, dR))           # the exact cut: must be the natural call
        if vx != ['same']:
            raise AssertionError('%s frame %d $%s: the exact cut is not the natural call: %r' % (self.tag, C['f'], a, vx))
        vb = self.rep.compare(C['state'], nat, cut=(i, ctr, dR))           # whole before, counters at the point
        va = self.rep.compare(C['state'], nat, ov0=chg, dR0=dR)            # whole after
        o, Ti, label, par = C['isr']
        pol = 'a' if o == 0 or (C['o_read'] is not None and o <= C['o_read']) else 'b'
        rd = sorted([('%04X' % k), v[0], v[1]] for k, v in C['rd'].items())
        late = C['wr'][C['wr_i']:]
        vl = self.rep.isr_late(C['pt'], C['keys'], late, C['isr_wr'], C['isr_T']) if late else ['nowr']
        row = [C['f'], a, o, Tp, len(C['pcs']), par, pol, vb, va, rd, C['o_read'], vl]
        g = C['g']
        if g is not None and pol == 'b':
            k = self.n_gate[a] = self.n_gate.get(a, 0) + 1
            if vb[0] != 'same' or k % SAMPLE_AT.get(C['a'], SAMPLE) == 0 or (C['a'] in LATE_KEEP and vl[0] == 'diff'):
                gl = g[:C['pu']] if C['pu'] is not None else g
                m0 = C['state'][0]
                runs = []
                for x in sorted(set(self.sd_rd) | SMC_SEED.get(C['a'], set())):
                    if runs and runs[-1][0] + len(runs[-1][1]) // 2 == x:
                        runs[-1][1] += '%02X' % m0[x]
                    else:
                        runs.append([x, '%02X' % m0[x]])
                X = {'grid': [len(gl), dig(''.join(gl))], 'pu': C['pu'] is not None, 'seed': runs,
                     'chg': sorted([x, v] for x, v in chg.items()), 'draws': C['draws'], 'class': vb[0] != 'same'}
                if C['a'] == 0xC002:
                    X['c'] = C['state'][1][3]         # M7.115k: C at the entry -- the walk's LDI borrows when it is 0
                if C['a'] in LATE_KEEP:
                    # M7.115j: the final byte at every address the call wrote or the ISR changed (the natural run's, at the
                    # RET) and, on a late row, what the ISR read of the call's writes AS IT READ IT -- the entry's byte, or
                    # the call's last write to it before the ISR -- and the entry's byte (the call writes those bytes and
                    # never reads them: no seed holds them)
                    mm = self.h.memobj.m
                    X['fin'] = sorted([x, mm[x]] for x in set(x for x, v in C['wr']) | set(chg)
                                      if not (C['a'] == 0xC002 and x in OPS_C002))
                    X['wr_i'] = C['wr_i']
                    if vl[0] == 'diff':
                        at = {}
                        for x, v in C['wr'][:C['wr_i']]:
                            at[x] = v
                        X['seen'] = [[int(ah, 16), at.get(int(ah, 16), m0[int(ah, 16)]), m0[int(ah, 16)]] for ah, pc in vl[4]]
                row.append(X)
        self.rows.append(row)


class WMem(Mem):
    __slots__ = ('wr', 'regs', 'watch', 'seen')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.wr, self.regs, self.watch, self.seen = [], None, None, None

    def __getitem__(self, i):
        w = self.watch
        if w is not None and i in w and i not in self.seen:
            self.seen[i] = '%04X' % self.regs[PC]
        return self.m[i]

    def __setitem__(self, i, v):
        if i < 0x4000:
            return
        r = self.regs
        if r is not None:
            sp = r[SP]
            if not (sp - 64 <= i < sp + 64):
                self.wr.append((i, v))
        self.m[i] = v


class Replayer:
    """one plain simulator per worker: a callee from its entry to its RET, atomic"""

    def __init__(self):
        h = RE.new('round1_48')
        self.wm = WMem(h.memobj.m)
        sim = CMIOSimulator(self.wm, config={})
        sim.t0, sim.t1 = -1, 1 << 40
        self.acc, self.cur = [], [0]

        def contend(t, timings):
            k, i = 0, self.cur[0]
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    self.acc.append((i, k))
                k += ts
            return 0
        sim.contend = contend
        self.ports = Ports()
        sim.set_tracer(self.ports)
        self.sim = sim

    def run(self, state, ov0=None, dR0=0, cut=None):
        wm, sim = self.wm, self.sim
        m = wm.m
        m[:] = state[0]
        r = sim.registers
        r[:] = state[1]
        if ov0:
            for a, v in ov0.items():
                m[a] = v
        if dR0:
            r[R] = (r[R] & 0x80) | ((r[R] + dR0) & 0x7F)
        ci = cut[0] if cut else -1
        sp0 = r[SP]
        ret = m[sp0] | (m[(sp0 + 1) & 0xFFFF] << 8)
        pcs, ops = array('H'), sim.opcodes
        self.acc = []
        wm.wr = []
        wm.regs = r
        try:
            while True:
                p = r[PC]
                if p == ret and r[SP] == sp0 + 2:
                    break
                if p in GUARD:
                    raise Fail('replay: guard at $%04X' % p)
                if m[p] == 0x76:
                    return 'halt'
                if len(pcs) == ci:
                    for a, v in cut[1].items():
                        m[a] = v
                    r[R] = (r[R] & 0x80) | ((r[R] + cut[2]) & 0x7F)
                self.cur[0] = len(pcs)
                pcs.append(p)
                ops[m[p]]()
                if len(pcs) > 500000:
                    return 'long'
        finally:
            wm.regs = None
        return pcs, self.acc, wm.wr

    def isr_late(self, pt, keys, late, nwr, nT):
        """the ISR from the point's state (registers before the acceptance), the callee's post-point writes laid over it
           first, the natural keys held: its writes outside the stack and its T against the natural ISR's"""
        wm, sim = self.wm, self.sim
        m = wm.m
        m[:] = pt[0][0]
        p0 = pt[0][0]
        for a, v in late:
            m[a] = v
        watch = {a for a, v in late if m[a] != p0[a]}
        wm.seen = {}
        r = sim.registers
        r[:] = pt[0][1]
        self.keys(keys)
        b0, s0 = r[PC], r[SP]
        wm.wr = []
        if not sim.accept_interrupt(r, wm, pt[1]):
            return ['noaccept']
        wm.regs = r
        wm.watch = watch
        ops, n = sim.opcodes, 0
        try:
            while not (r[PC] == b0 and r[SP] == s0):
                if r[PC] in GUARD:
                    raise Fail('isr replay: guard at $%04X' % r[PC])
                ops[m[r[PC]]]()
                n += 1
                if n > 200000:
                    return ['long']
        finally:
            wm.regs = None
            wm.watch = None
        rd = sorted(['%04X' % a, pc] for a, pc in wm.seen.items())
        if wm.wr != nwr:
            i = next((j for j in range(min(len(wm.wr), len(nwr))) if wm.wr[j] != nwr[j]), min(len(wm.wr), len(nwr)))
            return ['diff', i, ['%04X' % nwr[i][0], nwr[i][1]] if i < len(nwr) else None,
                    ['%04X' % wm.wr[i][0], wm.wr[i][1]] if i < len(wm.wr) else None, rd]
        return ['same', rd]

    def keys(self, keys):
        self.ports.pressed, self.ports.kempston = copy.deepcopy(keys[0]), keys[1]

    def compare(self, state, nat, **kw):
        x = self.run(state, **kw)
        if isinstance(x, str):
            return [x]
        pcs, acc, wr = x
        npcs, nacc, nwr = nat
        if pcs != npcs:
            i = next((j for j in range(min(len(pcs), len(npcs))) if pcs[j] != npcs[j]), min(len(pcs), len(npcs)))
            return ['path', i, '%04X' % npcs[i] if i < len(npcs) else '-', '%04X' % pcs[i] if i < len(pcs) else '-',
                    len(pcs)]
        if acc != nacc:
            return ['acc', len(acc), len(nacc)]
        if wr != nwr:
            i = next((j for j in range(min(len(wr), len(nwr))) if wr[j] != nwr[j]), min(len(wr), len(nwr)))
            return ['wr', i, list(nwr[i]) if i < len(nwr) else None, list(wr[i]) if i < len(wr) else None]
        return ['same']


def run_real(wd, rep):
    """a real-load world (itemacc's REAL): passacc's drive and keys, P / O after; the potion or FRUIT_LAY at ISR F"""
    tag, F, END = wd
    h, m, r = world('boot')
    cen = Census(rep, tag)
    cen.attach(h)
    m, r = h.memobj.m, h.sim.registers
    kf = PO.keyf(expand(SCRIPT))
    sim, ops = h.sim, h.sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr, adv = 0, False, None, None, None
    cm.keys(h, kf(0))
    while frame <= END:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            cen.frame = frame
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
                    IA.lay(m, IA.FRUIT_LAY)
            cen.st_isr = None
            cen.isr_end(L)
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
        if cen.keys_due:
            cen.isr_keys()
        main = cen.st_isr is None
        if main:
            cen.before(pc)
        if main and pc == 0x97F8 and frame > F and adv is None:
            adv = frame
            if tag.startswith('potion'):
                break
        ops[m[pc]]()
        if main:
            cen.after()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_, r0 = r[PC], r[SP], r[T], r[R]
            cen.pt = (cen.h.save_state(), pc) if cen.C is not None and cen.C['nisr'] == 0 else None
            if sim.accept_interrupt(r, sim.memory, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                cen.st_isr = isr
                cen.isr_begin(t_, r0)
    return cen


def run_state(st, rep):
    """a saved state's world: FRAMES frames of random keys (seeded by the name)"""
    h = RE.new(st)
    cen = Census(rep, st)
    cen.attach(h)
    m, r = h.memobj.m, h.sim.registers
    two = '2p' in st
    rng = random.Random('straddle:' + st)
    sim, ops = h.sim, h.sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, isr, keyrun, cur = 0, None, 0, []
    pool = ('O', 'P', 'Q', 'SPACE') + (('6', '7', '9', '0') if two else ())
    while frame < FRAMES:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            cen.frame = frame
            if keyrun <= 0:
                keyrun = rng.randint(4, 30)
                cur = [k for k in pool if rng.random() < 0.4]
            keyrun -= 1
            cm.keys(h, cur)
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            cen.st_isr = None
            cen.isr_end(isr[2])
            isr = None
        if pc in GUARD:
            raise Fail('%s: guard at $%04X' % (st, pc))
        if cen.keys_due:
            cen.isr_keys()
        main = cen.st_isr is None
        if main:
            cen.before(pc)
        ops[m[pc]]()
        if main:
            cen.after()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_, r0 = r[PC], r[SP], r[T], r[R]
            cen.pt = (cen.h.save_state(), pc) if cen.C is not None and cen.C['nisr'] == 0 else None
            if sim.accept_interrupt(r, sim.memory, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                cen.st_isr = isr
                cen.isr_begin(t_, r0)
    return cen


def forced_grid(state, pokes, a=0x8E3A):
    """M7.115h: a call from its entry state with the pokes laid over it, plain and atomic (no contention, no interrupt) to
       its RET: its grid (o:t of every instruction from the entry), its T, and its seed (the bytes >= $4000 it read before
       writing them, and SMC_SEED's operands, at the poked entry's values)"""
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for x, v in pokes:
        m[x] = v
    m0 = bytes(m)
    rm = RE.SeedMem(h.memobj.m)
    sim = RC.sim_of(h, [], rm)
    r, mem = sim.registers, sim.memory
    if r[PC] != a:
        raise Fail('forced: not at $%04X' % a)
    rm.regs = r
    sp0 = r[SP]
    ret = mem[sp0] | (mem[(sp0 + 1) & 0xFFFF] << 8)
    t0 = r[T]
    gl = []
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p in GUARD:
            raise Fail('forced: guard at $%04X' % p)
        tb = r[T]
        sim.opcodes[mem[p]]()
        gl.append('%d:%d;' % (tb - t0, r[T] - tb))
        if r[T] - t0 > 10 ** 6:
            raise Fail('forced: no RET')
    rm.regs = None
    runs = []
    for x in sorted(set(x for x in rm.rd if x >= 0x4000) | SMC_SEED.get(a, set())):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == x:
            runs[-1][1] += '%02X' % m0[x]
        else:
            runs.append([x, '%02X' % m0[x]])
    return {'grid': [len(gl), dig(''.join(gl))], 'T': r[T] - t0, 'seed': runs}


_REP = []


def world_job(wd):
    if not _REP:
        _REP.append(Replayer())
    rep = _REP[0]
    try:
        cen = run_real(wd, rep) if isinstance(wd, tuple) else run_state(wd, rep)
    except (Fail, RE.Fail) as e:
        return {'tag': wd[0] if isinstance(wd, tuple) else wd, 'skip': str(e)}
    out = {'tag': cen.tag, 'calls': cen.calls, 'blocks': cen.blocks, 'rows': cen.rows}
    if cen.tag == FORCED_WORLD:
        if cen.e3a is None:
            raise Fail('%s: no $8E3A call to force from' % cen.tag)
        out['forced'] = [dict(forced_grid(cen.e3a, pk), name=nm, pokes=pk) for nm, pk in FORCED_8E3A]
    return out


def summary(res):
    S = {}
    for x in res:
        for r in x.get('rows', ()):
            s = S.setdefault(r[1], {'n': 0, 'a': 0, 'before': {}, 'after': {}, 'engine': {}, 'rd': {}, 'late': {},
                                     'late_at': {}})
            s['late'][r[11][0]] = s['late'].get(r[11][0], 0) + 1
            if r[11][0] == 'diff':
                for a, pc in r[11][4]:
                    key = a + '@' + pc
                    s['late_at'][key] = s['late_at'].get(key, 0) + 1
            s['n'] += 1
            s['a'] += r[6] == 'a'
            v = r[7] if r[6] == 'b' else r[8]
            for k, x in (('before', r[7][0]), ('after', r[8][0]), ('engine', v[0])):
                s[k][x] = s[k].get(x, 0) + 1
            if v[0] != 'same':
                for a, pc, c in r[9]:
                    key = a + '@' + pc
                    s['rd'][key] = s['rd'].get(key, 0) + 1
    return S


def capture(jobs):
    jobsl = list(IA.REAL) + list(STATES)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, jobsl))
    for x in res:
        if 'skip' in x:
            print('%-14s skipped: %s' % (x['tag'], x['skip']), flush=True)
            continue
        nb = sum(1 for r in x['rows'] if (r[7] if r[6] == 'b' else r[8])[0] != 'same')
        print('%-14s %6d calls, %5d straddles (%d differ on the engine rule), %d blocks' % (
            x['tag'], sum(v[0] for v in x['calls'].values()), len(x['rows']), nb, sum(x['blocks'].values())),
            flush=True)
        for f in x.get('forced', ()):
            print('    forced $8E3A %-36s %4d instructions, %6d T' % (f['name'], f['grid'][0], f['T']), flush=True)
    S = summary(res)
    for a in sorted(S, key=lambda k: -S[k]['n']):
        s = S[a]
        top = sorted(s['rd'].items(), key=lambda kv: -kv[1])[:8]
        print('$%s %5d (a %4d)  engine %-34s before %-34s after %-34s rd %s' % (
            a, s['n'], s['a'], json.dumps(s['engine']), json.dumps(s['before']), json.dumps(s['after']),
            ' '.join('%s:%d' % kv for kv in top)))
        lt = sorted(s['late_at'].items(), key=lambda kv: -kv[1])[:8]
        print('       late ISR %s  it read the callee writes %s' % (json.dumps(s['late']),
                                                                    ' '.join('%s:%d' % kv for kv in lt)))
    return {'meta': {'tool': 'tools/straddle.py', 'no_rom_bytes': True,
                     'note': 'the chain callee an interrupt falls inside: natural vs atomic replays (before / after '
                             'the ISR); rows [frame, callee, ISR offset, plain T, instructions, parity, before, '
                             'after, reads of ISR-changed bytes]'},
            'frames': FRAMES, 'chain': {('%04X' % k): ('%04X' % v) for k, v in CHAIN.items()},
            'worlds': {x['tag']: x for x in res}, 'summary': S}


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
    elif cmd == 'one':
        x = world_job(sys.argv[2] if not sys.argv[2].startswith('(') else eval(sys.argv[2]))
        print(json.dumps(summary([x]), indent=1)[:4000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
