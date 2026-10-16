"""M7.115j (measurement) -- $A9ED, THE BOSS TICK, ON THE PASS'S ACCESS PROGRAM AND ITS GRID.

M7.114a put every main-loop pass on the frame clock by its ACCESS PROGRAM (passacc), M7.114d placed each interrupt by the
pass's INSTRUCTION GRID (insgrid), M7.115f/g/i did it for the item pass, the callee an interrupt falls inside, and $7E80.
The boss tick's code is not contended ($A8C1..$AA4E), but a BODY ($AA0E: every 32nd tick) blits: the erase ($A9DA: four
$A929 rows of eight pixel rows, four LDIs each, from the shadow at $A000 + the screen address to the screen; and each
row's four attribute cells through $9D4C's LD (DE),A) and the draw ($A8C1: four character rows of eight, four LDIs each,
from the sprite at ($A8C2) to the screen; and the attribute walk's sixteen LDDs from ($A8FD) down).  Every LDI / LDD
writes the screen -- (DE) is contended, three times (SkoolKit's ldi: (DE) 3 T, 11 in, and two internal cycles at 14 and
15; (HL) 8 in, contended only when the source is) -- and every $9D4C store once, 4 T in: 832 contended accesses a body,
where the engine put none (EA3b's r80 pin: frame 1113's pass, the machine's 891, the engine's 59).  And the engine summed
the blits' keys out of the machine's order (`zs('A929', 4)`, `zs('A966t', 3)`: CALL keys summed n times), so the cursor
was lost in every body and an interrupt inside one ran after the whole tick: the census (tools/straddle.py) found 4
straddles taking another path (P1's Y / X read after the ISR moved him) and 10 whose ISR, run late, wrote otherwise (its
sprites read the screen bytes the blits write).

This oracle measures it:

  THE REAL LOAD (passacc's drive and keys) with ($8609) = $4F and ($FECD) = 1 poked at the END of ISR 1000 (bossfree's /
  emitacc's r80 way: $8D12 advances to the boss round), free-running, contended, to frame END:
    isrs    every ISR from FIRST [label, T, acceptance phase, digest of the bitmap $4000..$57FF and of the attributes
            $5800..$5AFF at its END] -- the screen the ISR leaves, for the page's to be compared with
  SAVED STATES on the boss round (blowbolt, boss, bosshit, bosskilled, bossspawn, bottle), FRAMES frames each of random
  keys (seeded), contended.

  calls   every $A9ED CALL from the chain ($8D2E): [frame, the wall phase at its entry, its plain T (the ISRs and the
          delays out), the accesses (count, digest of 'o:k;' -- o the plain offset from the entry, k the T into the
          instruction), the instructions (count, digest of 'o:t;'), the ISRs inside [o, T, label], marks (MARKS' PCs)]
  replays the FIRST call of each distinct (accesses, instructions) pair in a world, run again PLAIN (no contention,
          interrupts off) from its entry to the RET: the SEED (every byte >= $4000 read before written, as [start, hex]
          runs, and the self-modified operands SMC at their values), the accesses and the instructions (count + digest),
          T, marks, the writes (count; the final value of each byte written: count + digest of 'a:v;'; the addresses as
          [start, length] runs); `same` = the
          replay's digests are the natural call's (an ISR inside the natural call may move what it reads)
  forced  FORCED replays (declared), from the world's first body's entry: P2 in play over the boss ($FD91 bit 7, its Y /
          X = the box's: P2 asked first, $A971), P1 over the boss (the hit: $AA30's BIT 2,(IX+$5A) and $927D's kill),
          P1 dying over it ($AA34's RET nz), the comparator pair at the tape's SCF / RET ($A98F / $A990 = $37 $C9: every
          position an overlap), the sprite source at $5B00 (contended: the draw's (HL) on the program), the boss at the
          box's corners (both bounces' NEG); ILIST's keep the machine's instruction list [pc, plain offset]
  phased  PHASED runs (declared): a body's entry (P1 poked beside the boss -- his Y in the box, his X one cell left of it:
          the ISR draws him over the boss's left column, and $A98B reads his X -- or over it: the kill) with the CPU's T
          set so that the entry lies `shift` T before a frame boundary -- the bottom border, where nothing waits: plain
          offsets are wall offsets and the point lands to the T -- run with interrupts and contention to the RET; the
          point AT and 1 T into an instruction of the erase's LDIs, its attribute store, the bounce's store, the draw's
          LDIs and LDDs, P1's reads; at both parities of the ISR ($8DBD's bit 0 flipped, $AA00 re-aimed: still a body).  Each: the ISR [plain offset, T, label, acceptance phase], the call's instructions
          and accesses (count + digest, the ISR out), its seed (what the CALLEE read before writing it), its writes
          before the ISR, the ISR's changes, what the ISR read of the bytes the callee writes -- before it or after it, the
          late class -- [address, value it saw, the entry's value], the final
          value of every byte the call wrote or the ISR changed [address, value]

ASSERTED: each natural call's instructions tile its plain T; a replay's run ends at the RET; a phased run's ISR is the
one its shift put there (one ISR inside, at the shift or at the end of the instruction in progress).  No ROM byte:
offsets, T, phases, digests and game-RAM bytes (the seeds, the writes) only.

Usage:  python tools/bossacc.py [capture|verify] [--jobs N]   -> build/bossacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import Mem, PC, T, IFF, SP
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import revealentry as RE
import revealcont as RC
from passacc import SCRIPT
from emitacc import drive

FIXTURE = 'build/bossacc_fixture.json'
FD = 69888
IA = 32
ENTRY = 0xA9ED
MARKS = {0xA9F3: 'r80', 0xA84D: 'spawn', 0xA9FC: 'live', 0xAA05: 'tick', 0xAA0E: 'body', 0xAA40: 'neg',
         0x9D53: 'solid', 0xA8FC: 'attrs', 0xA97E: 'ask', 0xA983: 'y', 0xA98B: 'x', 0xA9AF: 'hit', 0xAA30: 'hitp',
         0xAA35: 'kill', 0x9298: 'kill2'}
# the operands the tick reads as instruction bytes: $A9FF SUB n ($AA00), $AA05 LD A,n ($AA06), the spawn's $A85B LD A,n
# ($A85C), the draw's LD DE,nn ($A8C2/3) / LD BC,nn ($A8DB/C: the X, also read as data) / LD DE,nn ($A8FD/E), and the
# comparator pair $A98F / $A990, EXECUTED (NOP / NOP decayed, SCF / RET on the tape)
SMC = [0xA85C, 0xA8C2, 0xA8C3, 0xA8DB, 0xA8DC, 0xA8FD, 0xA8FE, 0xA98F, 0xA990, 0xAA00, 0xAA06]
POKE = 1000
REAL = [('r80', 80, 1700)]
FIRST = POKE - 2
STATES = ['blowbolt', 'boss', 'bosshit', 'bosskilled', 'bossspawn', 'bottle']
FRAMES = 600
P1, P2 = 0xFD80, 0xFD8A


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


def dig_b(b):
    return hashlib.sha1(bytes(b)).hexdigest()[:16]


def cell_addrs(c):
    """the bitmap addresses of character cell c (0..767: row c >> 5, column c & 31), top pixel row first"""
    y, x = c >> 5, c & 31
    base = 0x4000 | ((y & 0x18) << 8) | ((y & 7) << 5) | x
    return [base + (k << 8) for k in range(8)]


def masked(m):
    """the bitmap with every cell that holds a ROM glyph (codes 33..127 of the charset at $3D00 -- the HUD's text, the
       banners, the round number: the machine prints them from the ROM, which the port does not ship, so it draws its
       own) zeroed, and the masked cells' indices (no ROM byte leaves this function).  A cell is a glyph's when its pixel
       rows 1..7 are the glyph's: the round number's digits keep the wall's row 0 above them"""
    glyphs = set(bytes(m[0x3D01 + 8 * i:0x3D08 + 8 * i]) for i in range(1, 96))
    bm = bytearray(m[0x4000:0x5800])
    mask = []
    for c in range(768):
        A = cell_addrs(c)
        if bytes(m[a] for a in A[1:]) in glyphs:
            mask.append(c)
            for a in A:
                bm[a - 0x4000] = 0
    return bm, mask


class Rec:
    """the natural run's recorder: its $A9ED calls; in a real world the ISRs' screens"""

    def __init__(self, h, pf=None):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.C = None
        self.calls, self.kept, self.isrs, self.ldar = [], [], [], []
        self.pf = pf
        self.seen = set()
        self.tb = 0
        self.d_ins = 0
        self.frame = 0
        self.first_body = None
        self.mask = []
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend

        def cont(t, timings):
            if self.st_isr is None:
                C = self.C
                tt, k = t, 0
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        if C is not None:
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
        if pc == 0x8D0C and C is not None:
            raise Fail('frame %d: an $A9ED call from frame %d never returned to the chain' % (frame, C['f']))
        if pc == ENTRY and C is None:
            sp = r[SP]
            self.C = C = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'ins': [], 'isr': [],
                          'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'marks': {}, 'state': h.save_state()}
        elif C is not None and pc == C['ret'] and r[SP] == C['sp'] + 2:
            self.end_call()
            C = None
        if C is not None:
            name = MARKS.get(pc)
            if name:
                C['marks'][name] = C['marks'].get(name, 0) + 1
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

    def end_call(self):
        C = self.C
        self.C = None
        r = self.h.sim.registers
        Tp = r[T] - C['t0'] - C['D'] - C['I']
        o_prev = 0
        for s in C['ins']:
            o, t = map(int, s[:-1].split(':'))
            if o != o_prev:
                raise Fail('frame %d: $A9ED\'s instructions do not tile at %d (expected %d)' % (C['f'], o, o_prev))
            o_prev = o + t
        if o_prev != Tp:
            raise Fail('frame %d: $A9ED\'s instructions end at %d, its T %d' % (C['f'], o_prev, Tp))
        key = (dig(C['acc']), dig(C['ins']))
        row = [C['f'], C['ph'], Tp, len(C['acc']), key[0], len(C['ins']), key[1], C['isr'], dict(sorted(C['marks'].items()))]
        self.calls.append(row)
        if 'body' in C['marks'] and self.first_body is None and not C['isr']:
            self.first_body = (len(self.calls) - 1, C['state'], C['sp'], C['ret'])
        if key not in self.seen:
            self.seen.add(key)
            self.kept.append((len(self.calls) - 1, C['state'], C['sp'], C['ret']))

    def isr_begin(self, t_, label):
        self.isr_t0 = t_

    def isr_end(self, label):
        r = self.h.sim.registers
        T_ = r[T] - self.isr_t0
        if self.pf is not None and label >= self.pf:
            m = self.h.memobj.m
            bm, mask = masked(m)
            row = [label, T_, self.isr_t0 % FD, dig_b(bm), dig_b(m[0x5800:0x5B00])]
            if mask != self.mask:
                row.append(mask)
                self.mask = mask
            self.isrs.append(row)
        C = self.C
        if C is not None:
            C['isr'].append([self.isr_t0 - C['t0'] - C['D'] - C['I'], T_, label])
            C['I'] += T_


def run_real(wd):
    tag, rnd, END = wd
    h, m, r = world('boot')
    seq = expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    rec = Rec(h, FIRST)
    drive(h, rec, END, keyf=keyf, poke=[(0x8609, rnd - 1), (0xFECD, 1)])
    return tag, rec


def run_state(st):
    h = RE.new(st)
    rec = Rec(h)
    drive(h, rec, FRAMES, rng=random.Random('bossacc:' + st), pool=('O', 'P', 'Q', 'SPACE'))
    return st, rec


def seed_runs(m0, rd):
    runs = []
    for a in sorted(set(a for a in rd if a >= 0x4000) | set(SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return runs


def replay(state, stop_sp_ret, pokes=()):
    """PLAIN (no contention, interrupts off) from the saved state to the RET: the seed, the accesses, the instructions,
       T, marks, the writes (the final value of each byte written outside the stack)"""
    sp0, ret = stop_sp_ret
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
        raise Fail('a replay not at $A9ED')
    rm.regs = r
    t0 = r[T]
    acc, ins, pcs, marks = [], [], [], {}
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
    wa = sorted(set(a for a, t in rm.wr))
    fin = ['%d:%d;' % (a, m[a]) for a in wa]
    runs = []
    for a in wa:
        if runs and runs[-1][0] + runs[-1][1] == a:
            runs[-1][1] += 1
        else:
            runs.append([a, 1])
    return {'seed': seed_runs(m0, rm.rd), 'acc': [len(acc), dig(acc)], 'ins': [len(ins), dig(ins)], 'T': r[T] - t0,
            'marks': dict(sorted(marks.items())), 'wr': [len(rm.wr), len(fin), dig(fin)], 'wa': runs,
            'fin': [m[0xA839], m[0xA8DB], m[0xAA47], m[0xAA48]]}, pcs


class TMem(Mem):
    """the phased run's memory: the CALLEE's reads before writes (its seed) and its writes; the ISR's old values of what it
       writes (its changes) and its first read of each byte (those the callee writes, before the ISR or after it, kept)"""
    __slots__ = ('mode', 'regs', 'seen', 'rd', 'wr', 'iold', 'irs', 'cw')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.mode, self.regs = 0, None
        self.seen, self.rd, self.wr, self.iold, self.irs, self.cw = set(), [], [], {}, {}, set()

    def __getitem__(self, i):
        if type(i) is int:
            if self.mode == 1:
                if i not in self.seen:
                    p = self.regs[PC]
                    if not (p <= i < p + 4):
                        self.seen.add(i)
                        self.rd.append(i)
            elif self.mode == 2 and i >= 0x4000 and i not in self.irs:
                self.irs[i] = self.m[i]                 # (every first read: those of bytes the callee writes kept below)
        return self.m[i]

    def __setitem__(self, i, v):
        if i < 0x4000:
            self.rom_writes += 1
            return
        if self.mode:
            sp = self.regs[SP]
            stack = sp - 64 <= i < sp + 64
            if self.mode == 1:
                self.seen.add(i)
                if not stack:
                    self.wr.append((i, v))
                    self.cw.add(i)
            elif not stack and i not in self.iold:
                self.iold[i] = self.m[i]
        self.m[i] = v


def phased(state, sp_ret, shift, pokes=()):
    """FORCED (declared): a body's entry state with `pokes`, moved to `shift` T before a frame boundary (the bottom border:
       nothing waits there), run with interrupts and contention to its RET"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    for a, v in pokes:
        h.memobj.m[a] = v
    m0 = bytes(h.memobj.m)
    tm = TMem(h.memobj.m)
    regs = list(h.sim.registers)
    sim = CMIOSimulator(tm, config={})
    sim.registers[:] = regs
    h.sim, h.memobj = sim, tm
    tm.sim = sim
    sim.set_tracer(h.ports)
    r, ops = sim.registers, sim.opcodes
    if r[PC] != ENTRY:
        raise Fail('a phased run not at $A9ED')
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
    ins, isr, wr_i, isr_info, t_end = [], None, None, [], t0 + 4 * FD
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            T_ = r[T] - isr[2]
            isr_info.append([isr[2] - t0 - st['D'] - st['I'], T_, isr[3]])
            st['I'] += T_
            st['in_isr'] = False
            tm.mode = 1
            isr = None
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
    if len(isr_info) != 1:
        raise Fail('phased run: %d ISRs inside' % len(isr_info))
    o, T_, ph = isr_info[0]
    if not (shift <= o + ph and o <= shift + 23):
        raise Fail('phased run: the ISR at %d (phase %d), the shift %d' % (o, ph, shift))
    m = tm.m
    chg = sorted([a, m[a]] for a, old in tm.iold.items() if m[a] != old)
    wa = sorted(set(a for a, v in tm.wr) | set(a for a, v in chg))
    fin = [[a, m[a]] for a in wa]
    seen = sorted([a, v, m0[a]] for a, v in tm.irs.items() if a in tm.cw)
    after = {}
    for a, v in tm.wr[wr_i:]:
        after[a] = v
    return {'isr': [o, T_, ph], 'ins': [len(ins), dig(ins)], 'acc': [len(st['acc']), dig(st['acc'])],
            'T': r[T] - t0 - st['D'] - st['I'], 'seed': seed_runs(m0, tm.rd), 'wr_i': wr_i, 'n_wr': len(tm.wr),
            'chg': chg, 'seen': seen, 'fin': fin,
            # the LATE class: the bytes the ISR read that the callee writes after it, otherwise -- an ISR run after the
            # whole call would read them as the call left them
            'late': sum(1 for a, v, v0 in seen if a in after and after[a] != v)}


# the forced runs that keep the machine's instruction list ([pc, plain offset] of each): every site's place, to the T, for
# bb.test.js BA7 (the kill path with every store kind but the NEG; P2's +7; both NEG arms)
ILIST = {'p1 over', 'p2 over', 'corner lo', 'corner hi'}
# the phased targets: [name, pc, its visit (0 = the first), shifts after its start: 0 = AT (the ISR before it), 1 = 1 T in
# (the ISR at its end)]
TARGETS = [('erase.ldi0', 0xA941, 0), ('erase.ldi', 0xA945, 13), ('erase.attr', 0x9D56, 5), ('erase.last', 0x9D56, 15),
           ('bounce.y', 0xAA45, 1), ('draw.ldi0', 0xA8E1, 0), ('draw.ldi', 0xA8E5, 17), ('draw.attr', 0xA914, 6),
           ('ask.p1', 0xA97E, 1), ('read.y', 0xA983, 0), ('read.x', 0xA98B, 0), ('hit', 0xAA30, 0)]


def world_job(wd):
    tag, rec = run_real(wd) if isinstance(wd, tuple) else run_state(wd)
    reps = []
    for i, st, sp, ret in rec.kept:
        c = rec.calls[i]
        x, _ = replay(st, (sp, ret))
        x['call'] = i
        x['same'] = len(c[7]) == 0 and x['acc'][1] == c[4] and x['ins'][1] == c[6]
        reps.append(x)
    forced, phase = [], []
    if rec.first_body is not None:
        i, st, sp, ret = rec.first_body
        m = st[0]
        b0, base, pcs = None, None, None
        base, pcs = replay(st, (sp, ret))
        by, bx = base['fin'][0], base['fin'][1]            # the boss after the bounces
        boxy, boxx = (by + 1) * 8, (bx + 1) * 8            # a pixel position inside the box
        F = [('p2 over', [(P2 + 7, m[P2 + 7] | 0x80), (P2 + 6, boxy), (P2 + 5, boxx)]),
             ('p1 over', [(P1 + 7, m[P1 + 7] | 0x80), (P1 + 6, boxy), (P1 + 5, boxx), (P1 + 0x5A, m[P1 + 0x5A] & ~0x1C & 0xFF)]),
             ('p1 dying', [(P1 + 7, m[P1 + 7] | 0x80), (P1 + 6, boxy), (P1 + 5, boxx), (P1 + 0x5A, m[P1 + 0x5A] | 0x04)]),
             ('p1 beside', [(P1 + 7, m[P1 + 7] | 0x80), (P1 + 6, boxy), (P1 + 5, (bx - 1) * 8)]),
             ('scf', [(0xA98F, 0x37), (0xA990, 0xC9)]),
             ('src 5B00', [(0xA8C2, 0x00), (0xA8C3, 0x5B)]),
             ('corner lo', [(0xA839, 3), (0xA8DB, 2), (0xAA47, 0xFF), (0xAA48, 0xFF)]),
             ('corner hi', [(0xA839, 19), (0xA8DB, 26), (0xAA47, 0x01), (0xAA48, 0x01)])]
        for name, pk in F:
            x, xp = replay(st, (sp, ret), pk)
            f = {'call': i, 'forced': name, 'pokes': pk, 'a': x}
            if name in ILIST:
                f['ilist'] = [[p, o] for p, o in xp]      # the machine's instruction list: BA7's places
            forced.append(f)
        if rec.pf is not None:
            # the phased runs: P1 beside the boss (his Y in the box, his X one cell left of it -- the ISR draws him over
            # the boss's left column; $A98B reads his X) and over it (the kill)
            # ...and at both parities of the ISR ($8DBD's bit 0, which it INCs first: the odd ISR services the player, the
            # even the bubble manager) -- $AA00 re-aimed so the tick's SUB gives the same nonzero result: still a body
            ctr, op = m[0x8DBD], (m[0x8DBD] - m[0xAA00]) & 0xFF
            par = [(0x8DBD, ctr ^ 1), (0xAA00, ((ctr ^ 1) - op) & 0xFF)]
            for pname, pk in (('beside', F[3][1]), ('over', F[1][1]), ('beside2', F[3][1] + par), ('over2', F[1][1] + par)):
                _, pcs = replay(st, (sp, ret), pk)
                for name, tpc, nth in TARGETS:
                    hits = [o for p, o in pcs if p == tpc]
                    if len(hits) <= nth:
                        continue
                    for d in (0, 1):
                        shift = hits[nth] + d
                        y = phased(st, (sp, ret), shift, pk)
                        y.update({'call': i, 'p1': pname, 'target': name, 'pc': tpc, 'nth': nth, 'd': d, 'shift': shift,
                                  'pokes': pk})
                        phase.append(y)
    out = {'tag': tag, 'n_calls': len(rec.calls), 'replays': reps, 'forced': forced, 'phased': phase, 'cover': {}}
    for c in rec.calls:
        for k, v in c[8].items():
            out['cover'][k] = out['cover'].get(k, 0) + v
    out['bodies'] = [c for c in rec.calls if 'body' in c[8]]
    if rec.pf is not None:
        out['isrs'] = rec.isrs
        out['ldar'] = [x for x in rec.ldar if x[0] >= FIRST]
    return out


def capture(jobs):
    jobsl = list(REAL) + list(STATES)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, jobsl))
    cover = {}
    for x in res:
        for k, v in x['cover'].items():
            cover[k] = cover.get(k, 0) + v
        nr = len(x['replays'])
        ns = sum(1 for y in x['replays'] if y['same'])
        print('%-10s %6d calls, %4d bodies, %4d replays (%d plain-comparable), %d forced, %d phased%s' % (
            x['tag'], x['n_calls'], len(x['bodies']), nr, ns, len(x['forced']), len(x['phased']),
            ', %d ISRs' % len(x['isrs']) if 'isrs' in x else ''), flush=True)
    print('cover:', ' '.join('%s=%d' % kv for kv in sorted(cover.items())))
    return {'meta': {'tool': 'tools/bossacc.py', 'no_rom_bytes': True,
                     'note': 'the boss tick ($A9ED): access programs and instruction grids, natural, replayed and phased; '
                             'seeds are game-RAM bytes read before written'},
            'script': [[k, v] for k, v in SCRIPT], 'poke': POKE, 'first': FIRST, 'real': [list(w) for w in REAL],
            'frames': FRAMES, 'smc': SMC, 'marks': {('%04X' % k): v for k, v in MARKS.items()},
            'targets': [[n, '%04X' % p, k] for n, p, k in TARGETS],
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
