"""M7.115k (measurement) -- $C002, THE BURST-SPARKLE WALK, ON THE PASS'S ACCESS PROGRAM AND ITS GRID.

M7.114a put every main-loop pass on the frame clock by its ACCESS PROGRAM (passacc), M7.114d placed each interrupt by the
pass's INSTRUCTION GRID (insgrid), M7.115f/g/i/j did it for the item pass, the callee an interrupt falls inside, $7E80 and
the boss tick.  $C002 ($8D49, the thirteenth chain entry) walks the fourteen two-byte particles at $5CE0 (CONTENDED: its
$C00B / $C016 / $C019 reads and its $C04C write-back were on the program since M7.114a); a LIVE slot (byte0 & 7 != 0)
advances its phase and either restores the pixels under it ($C057 CALL $A314: sixteen rows of two stores into the screen
from the shadow, phase 2 and phase 0 -- the free) or ORs its sprite in ($C043 CALL $A2D5: sixteen rows of two `OR (HL)`
reads of the screen and two stores into it; the sprite at $CA80 is not contended).  The engine put none of a live slot's
keys on the grid (its region a MISS) and none of its kids' 32 / 64 contended accesses on the program (IA3's fruit pin:
frame 806's pass 32 accesses short, the first sparkle's erase).  And it ran the walk whole before the ISR: the census
(tools/straddle.py) found 11 straddles whose OR read the screen bytes the ISR had drawn its sprites on after the point,
one whose ISR seeded slot 0 before the walk read it (the walk takes another path), and 5 whose ISR, run late, read the
screen the walk writes after the point (its sprites on the sparkle's bytes) or the table the walk frees.

This oracle measures it:

  THE REAL LOAD (passacc's drive and keys, potion.py's P / O walk after them) with the table LAID (declared) at the end of
  every LAY_STEP-th ISR from F to END: six particles -- three on P1's cells (the odd ISR draws him over them), three
  fixed -- at six phases, so that every walk after a lay has live slots on all paths (the erase at 2, the draws, the erase
  at 0 that frees), free-running, contended, to frame END:
    passes  every main-line pass from F - 2 [frame, wall phase, plain length, accesses, digest, ISRs inside [plain offset,
            T, label]] (passacc's row)
    isrs    every ISR from F - 2 [label, T, acceptance phase, digest of the bitmap with the ROM-glyph cells zeroed (bossacc's
            masked: the port draws its own glyphs) and of the attributes at its END (+ the mask when it changes)]
    ldar    every LD A,R from F - 2 [frame, pc, A] -- the draws the engine's stand-in (BB_Rng) is fed
  SAVED STATES (costc002's 48), FRAMES frames each of random keys with SPACE (seeded): natural pops, natural sparkles.

  calls   every $C002 CALL from the chain ($8D49) is counted; the LIVE ones (a slot not free) are kept: [frame, the wall
          phase at its entry, its plain T, the accesses (count, digest of 'o:k;' -- o the plain offset from the entry, k the
          T into the instruction), the instructions (count, digest of 'o:t;'), the ISRs inside [o, T, label], its path (a
          letter a slot: f free, e erase, d draw), C at its entry]
  replays the FIRST call of each distinct (accesses, instructions) pair in a world, run again PLAIN (no contention,
          interrupts off) from its entry to the RET: C at the entry, the SEED (every byte >= $4000 read before written, as
          [start, hex] runs, and SMC -- the blit's two OR opcodes, which the item's $A2C2 patches and restores -- at their
          values), the accesses and the instructions (count + digest), T, the path, the writes (count; the final value of
          each byte written: count + digest of 'a:v;'; the addresses as [start, length] runs -- the kids' own operands OPS
          left out: rewritten before every read, not state); `same` = the replay's digests are the natural call's (an ISR
          inside the natural call may move what it reads)
  forced  FORCED replays (declared), from the real world's first live call: all seven phases at once (every path in one
          walk), C = 0 with live slots (the LDI's borrow: thirteen iterations), sparkles whose rows the $FD00 table aims at
          the ROM (the reads read it, the stores drop), at the screen's right and bottom edges, fourteen drawing, fourteen
          freeing; ILIST's keep the machine's instruction list [pc, plain offset]
  phased  PHASED runs (declared): that call's entry with the CPU's T set so that the entry lies `shift` T before a frame
          boundary -- the bottom border, where nothing waits: plain offsets are wall offsets and the point lands to the T --
          run with interrupts and contention to the RET; the point AT and 1 T into TARGETS (the slots' reads, the LDI, the Y
          read, the write-backs, the blit's OR reads and stores, the restore's stores), in two scenes: 'over' -- three
          particles on P1's cells, the ODD ISR next (its entity pass draws him: the sprites on the walk's bytes) -- and
          'pop' -- three on a HELD bubble's cells, the EVEN ISR next (the bubble manager pops it: its erase on the walk's
          bytes, and its seed into the first free slot: the third particle's write-back frees one).  Each: the ISR [plain
          offset, T, label, acceptance phase], the call's instructions and accesses (count + digest, the ISR out), its seed,
          its stores before the ISR (those the ISR can see: the screen, the table -- obs), the ISR's changes, what the ISR
          read of the bytes the callee writes before writing them itself [address, value it saw, the entry's value], the
          final value of every byte the call wrote or the ISR changed [address, value]

ASSERTED: each natural call's instructions tile its plain T; a replay's run ends at the RET; a phased run's ISR is the one
its shift put there.  No ROM byte: offsets, T, phases, digests and game-RAM bytes (the seeds, the writes) only.

Usage:  python tools/sparkacc.py [capture|verify] [--jobs N]   -> build/sparkacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP, A as RA, C as RCr
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import revealentry as RE
import revealcont as RC
from passacc import SCRIPT
import potion as PO
from bossacc import masked, dig_b, TMem

FIXTURE = 'build/sparkacc_fixture.json'
FD = 69888
IA = 32
ENTRY = 0xC002
TABLE = 0x5CE0
MARKS = {0xC00B: 'slot', 0xC010: 'live', 0xC050: 'free', 0xC037: 'draw', 0xC055: 'erase', 0xC04C: 'wb', 0xA2D5: 'blit',
         0xA314: 'restore'}
# the bytes the walk's kids read as instruction bytes that something else patches: the blit's two OR (HL) opcodes, which
# the item's $A2C2 turns to NOPs for its own blit and puts back ($B6) -- the engine's sparkle ORs (its or_ argument)
SMC = [0xA307, 0xA30C]
# the kids' own operands, rewritten at every entry before the code that reads them (the blit's column $A304, the restore's
# column $A355, band 3's count $A349 and band 1's $A33D): not live state -- the engine computes them and stores none
# (bb.test's earlier gates' OPS) -- so the writes' digests and the stores' counts leave them out
OPS = (0xA304, 0xA33D, 0xA349, 0xA355)


def obs(a):
    """the bytes the walk writes that the ISR reads: the screen (its sprites) and the table (a pop's seed searches it) -- a
       phased run's stores before the ISR are counted over these (the walk's others -- $C048, $C04A, the record $C05E.. --
       no ISR reads: the engine may take the ISR after them, at the next site, the same machine)"""
    return 0x4000 <= a < 0x5800 or TABLE <= a < TABLE + 28


class STMem(TMem):
    """bossacc's phased memory, the ISR's first read of a byte kept only when the ISR has not written it before (its
       sprites' erase writes the cells its draw then reads: what it reads there is its own, not the walk's)"""
    __slots__ = ()

    def __getitem__(self, i):
        if type(i) is int and self.mode == 2 and i in self.iold:
            return self.m[i]
        return TMem.__getitem__(self, i)
REAL = [('spark', 600, 1300)]
LAY_STEP = 4
# the lay: [slot, X (P1's + dx, or fixed), Y (P1's + dy, or fixed), phase] -- the walk after it advances each phase:
# 2 -> 3 draws, 1 -> 2 erases, 6 -> 7 draws, 7 -> 0 erases and frees, 3 -> 4 and 4 -> 5 draw
LAY = [(0, ('p', 0), ('p', 0), 2), (1, ('p', 8), ('p', 0), 1), (2, ('p', 0), ('p', -8), 6),
       (3, 0x28, 0x30, 7), (4, 0x80, 0x58, 3), (5, 0xC8, 0x90, 4)]
STATES = ['blowbolt', 'boris', 'boriskill', 'boss', 'bosshit', 'bosskilled', 'bossspawn', 'bottle', 'candycane', 'crown',
          'crown_taken', 'death', 'elfire', 'ellight', 'elwater', 'extcomp', 'extend', 'extn', 'fallcandy', 'fbkill',
          'firekill', 'fruit', 'fruit_taken', 'hurryup', 'lastdia81', 'lastdia82', 'peachcane', 'peachfall', 'peachspawn',
          'play1p48', 'powerup', 'r10_48', 'r20_48', 'r30_48', 'r40_48', 'r50_48', 'r60_48', 'r6_48', 'redcross',
          'round1_2p48', 'round1_48', 'spawn', 'spawn_taken', 'sweet', 'umbrella', 'water', 'yellowcross', 'yellowcross2']
FRAMES = 600
P1 = 0xFD80
BUB = 0xFED8                    # the bubble pool: twelve ten-byte slots
# a HELD bubble (+7 $8C: live, popping, held -- $B64B's arm, the pop at once; +7 bit 1 clear: no award), its record from a
# natural one (water's slot 0) with its cell marker aimed at the ROM (+3 = 2: the clear discarded, as the rise leaves it)
HELD = [0x80, 0xC7, 0x00, 0x02, 0xD5, None, None, 0x8C, 0x00, 0x00]


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


def lay(m, spec=LAY):
    """the particles of a LAY list into the table (X / Y relative to P1 where the spec says so; X to its cell)"""
    for k, xs, ys, ph in spec:
        x = (m[P1 + 5] + xs[1]) & 0xFF if isinstance(xs, tuple) else xs
        y = (m[P1 + 6] + ys[1]) & 0xFF if isinstance(ys, tuple) else ys
        m[TABLE + 2 * k] = (x & 0xF8) | ph
        m[TABLE + 2 * k + 1] = y


def table_pokes(spec):
    """[slot, X, Y, phase] -> pokes of the table (fixed positions)"""
    out = []
    for k, x, y, ph in spec:
        out += [(TABLE + 2 * k, (x & 0xF8) | ph), (TABLE + 2 * k + 1, y)]
    return out


class Rec:
    """the natural run's recorder: the main line's passes (`pf`..`pt`), its $C002 calls; in a real world the ISRs' screens"""

    def __init__(self, h, pf=None, pt=None):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.P = None
        self.C = None
        self.passes, self.lives, self.kept, self.isrs, self.ldar = [], [], [], [], []
        self.n_calls = 0
        self.pf, self.pt = pf, pt
        self.seen = set()
        self.tb = 0
        self.d_ins = 0
        self.frame = 0
        self.first_live = None
        self.mask = []
        self.armed = pf is None          # a real world's forced / phased base: the first live call after the first lay
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend

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
        if pc == 0x8D0C:
            if C is not None:
                raise Fail('frame %d: a $C002 call from frame %d never returned to the chain' % (frame, C['f']))
            P = self.P
            if P is not None:
                P['len'] = r[T] - P['t0'] - P['D'] - P['I']
                self.passes.append([P['f'], P['ph'], P['len'], len(P['acc']), dig(P['acc']), P['isr']])
            self.P = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'isr': []} \
                if self.pf is not None and self.pf <= frame <= self.pt else None
        if pc == ENTRY and C is None:
            sp = r[SP]
            self.C = C = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'ins': [], 'isr': [],
                          'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'path': [], 'c': r[RCr],
                          'state': h.save_state()}
        elif C is not None and pc == C['ret'] and r[SP] == C['sp'] + 2:
            self.end_call()
            C = None
        if C is not None:
            if pc == 0xC050:
                C['path'].append('f')
            elif pc == 0xC037:
                C['path'].append('d')
            elif pc == 0xC055:
                C['path'].append('e')
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
        self.n_calls += 1
        r = self.h.sim.registers
        Tp = r[T] - C['t0'] - C['D'] - C['I']
        o_prev = 0
        for s in C['ins']:
            o, t = map(int, s[:-1].split(':'))
            if o != o_prev:
                raise Fail('frame %d: $C002\'s instructions do not tile at %d (expected %d)' % (C['f'], o, o_prev))
            o_prev = o + t
        if o_prev != Tp:
            raise Fail('frame %d: $C002\'s instructions end at %d, its T %d' % (C['f'], o_prev, Tp))
        path = ''.join(C['path'])
        key = (dig(C['acc']), dig(C['ins']))
        live = any(x != 'f' for x in path)
        if live:
            self.lives.append([C['f'], C['ph'], Tp, len(C['acc']), key[0], len(C['ins']), key[1], C['isr'], path, C['c']])
            if self.armed and self.first_live is None and not C['isr']:
                self.first_live = (C['state'], C['sp'], C['ret'], C['f'])
        if key not in self.seen:
            self.seen.add(key)
            self.kept.append((C['state'], C['sp'], C['ret'], C['f'], key, len(C['isr']), path))

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
        for X in (self.P, self.C):
            if X is not None:
                X['isr'].append([self.isr_t0 - X['t0'] - X['D'] - X['I'], T_, label])
                X['I'] += T_


def drive(h, rec, until, keyf=None, lays=(), rng=None, pool=()):
    """the natural run: keys at ISR ends (keyf, itemacc's real drive: the menu's scan holds a change to its end) or random
       keys at frame boundaries (rng); the table laid at the END of each ISR in `lays`; to frame `until`"""
    sim, ops, mem, r = h.sim, h.sim.opcodes, h.sim.memory, h.sim.registers
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD and ia == IA
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr, keyrun, cur = 0, False, None, None, 0, []
    lays = set(lays)
    if keyf:
        cm.keys(h, keyf(0))
    while frame <= until:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            if rng is not None:
                if keyrun <= 0:
                    keyrun = rng.randint(4, 30)
                    cur = [k for k in pool if rng.random() < 0.4]
                keyrun -= 1
                cm.keys(h, cur)
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if keyf:
                if in_scan:
                    pending = keyf(L)
                else:
                    cm.keys(h, keyf(L))
            if L in lays:
                lay(mem)
                rec.armed = True
            rec.st_isr = None
            rec.isr_end(L)
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        main = rec.before(frame)
        ops[mem[pc]]()
        if main:
            rec.after()
        if rec.pf is not None and frame >= rec.pf and mem[pc] == 0xED and mem[(pc + 1) & 0xFFFF] == 0x5F:
            rec.ldar.append([frame, pc, r[RA]])          # LD A,R: the draw, for the engine's stand-in to be fed
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                rec.st_isr = isr
                rec.isr_begin(t_, isr[2])


def run_real(wd):
    tag, F, END = wd
    h, m, r = world('boot')
    rec = Rec(h, F - 2, END)
    drive(h, rec, END, keyf=PO.keyf(expand(SCRIPT)), lays=range(F, END, LAY_STEP))
    return tag, rec


def run_state(st):
    h = RE.new(st)
    rec = Rec(h)
    drive(h, rec, FRAMES, rng=random.Random('sparkacc:' + st), pool=('O', 'P', 'Q', 'SPACE'))
    return st, rec


def seed_runs(m0, rd):
    runs = []
    for a in sorted(set(a for a in rd if a >= 0x4000) | set(SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return runs


def replay(state, sp_ret, pokes=(), c=None):
    """PLAIN (no contention, interrupts off) from the saved state to the RET: C at the entry, the seed, the accesses, the
       instructions, T, the path, the writes (the final value of each byte written outside the stack)"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    if c is not None:
        h.sim.registers[RCr] = c
    m0 = bytes(h.memobj.m)
    rm = RE.SeedMem(h.memobj.m)
    log = []
    sim = RC.sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    if r[PC] != ENTRY:
        raise Fail('a replay not at $C002')
    c0 = r[RCr]
    rm.regs = r
    t0 = r[T]
    acc, ins, pcs, path = [], [], [], []
    nlog = 0
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p in GUARD:
            raise Fail('replay: guard at $%04X' % p)
        if p == 0xC050:
            path.append('f')
        elif p == 0xC037:
            path.append('d')
        elif p == 0xC055:
            path.append('e')
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
    wa = sorted(set(a for a, t in rm.wr if a not in OPS))
    fin = ['%d:%d;' % (a, m[a]) for a in wa]
    runs = []
    for a in wa:
        if runs and runs[-1][0] + runs[-1][1] == a:
            runs[-1][1] += 1
        else:
            runs.append([a, 1])
    return {'c': c0, 'seed': seed_runs(m0, rm.rd), 'acc': [len(acc), dig(acc)], 'ins': [len(ins), dig(ins)],
            'T': r[T] - t0, 'path': ''.join(path), 'wr': [sum(1 for a, t in rm.wr if a not in OPS), len(fin), dig(fin)],
            'wa': runs}, pcs


def phased(state, sp_ret, shift, pokes=()):
    """FORCED (declared): a live call's entry state with `pokes`, moved to `shift` T before a frame boundary (the bottom
       border: nothing waits there), run with interrupts and contention to its RET"""
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
        raise Fail('a phased run not at $C002')
    c0 = r[RCr]
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
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            T_ = r[T] - isr[2]
            isr_info.append([isr[2] - t0 - st['D'] - st['I'], T_, isr[3]])
            st['I'] += T_
            st['in_isr'] = False
            tm.mode = 1
            isr = None
            # the ISR's changes AS IT LEFT THEM (the walk may write the same bytes after it: a seeded slot's write-back)
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
    if len(isr_info) != 1:
        raise Fail('phased run: %d ISRs inside' % len(isr_info))
    o, T_, ph = isr_info[0]
    if not (shift <= o + ph and o <= shift + 23):
        raise Fail('phased run: the ISR at %d (phase %d), the shift %d' % (o, ph, shift))
    m = tm.m
    wa = sorted(set(a for a, v in tm.wr if a not in OPS) | set(a for a, v in chg))
    fin = [[a, m[a]] for a in wa]
    seen = sorted([a, v, m0[a]] for a, v in tm.irs.items() if a in tm.cw)
    after = {}
    for a, v in tm.wr[wr_i:]:
        after[a] = v
    n_before = sum(1 for a, v in tm.wr[:wr_i] if obs(a))      # the stores the ISR can see (obs), before it and in all
    n_all = sum(1 for a, v in tm.wr if obs(a))
    return {'c': c0, 'isr': [o, T_, ph, m[0x8DBD] & 1], 'ins': [len(ins), dig(ins)], 'acc': [len(st['acc']), dig(st['acc'])],
            'T': r[T] - t0 - st['D'] - st['I'], 'seed': seed_runs(m0, tm.rd), 'wr_i': n_before, 'n_wr': n_all,
            'chg': chg, 'seen': seen, 'fin': fin,
            # the LATE class: the bytes the ISR read that the callee writes after it, otherwise -- an ISR run after the
            # whole call would read them as the call left them
            'late': sum(1 for a, v, v0 in seen if a in after and after[a] != v)}


# the forced runs that keep the machine's instruction list ([pc, plain offset] of each): every site's place, to the T, for
# the gates' site check (every path, the borrow, the rows aimed at the ROM)
ILIST = {'all7', 'borrow', 'rom'}
# the phased targets: [name, pc, its visit (0 = the first)]; shifts after its start: 0 = AT (the ISR before it), 1 = 1 T in
# (the ISR at its end).  'over' and 'pop' lay slot 0 drawing (2 -> 3), slot 1 erasing (1 -> 2), slot 2 freeing (7 -> 0):
# the blit's rows are visits 0..15 of $A307.., the restores' 0..15 (slot 1) and 16..31 (slot 2) of $A360 / $A364; in
# 'pop' the seed goes to slot 2 once its write-back has freed it, else to slot 3 (read after).  'pop0' lays none: the seed
# goes to slot 0, its read before the ISR or after it
TARGETS = [('slot0', 0xC00B, 0), ('ldi0', 0xC016, 0), ('y0', 0xC019, 0), ('or.0', 0xA307, 0), ('st.0', 0xA308, 0),
           ('or1.0', 0xA30C, 0), ('st1.0', 0xA30D, 0), ('or.9', 0xA307, 9), ('st1.12', 0xA30D, 12), ('wb0', 0xC04C, 0),
           ('rs.0', 0xA360, 0), ('rs1.0', 0xA364, 0), ('rs.10', 0xA360, 10), ('wb1', 0xC04C, 1), ('rs.16', 0xA360, 16),
           ('rs1.30', 0xA364, 30), ('wb2', 0xC04C, 2), ('slot3', 0xC00B, 3)]
TARGETS_POP0 = [('slot0', 0xC00B, 0), ('slot1', 0xC00B, 1)]


def scenes(m):
    """the phased scenes' pokes from the base call's RAM: 'over' -- particles 0..2 on P1's cells, 3..13 free, the ODD ISR
       next ($8DBD even: the ISR INCs it first); 'pop' -- a HELD bubble in pool slot 11 at a fixed cell and particles 0..2
       on its cells, 3..13 free, the EVEN ISR next; 'pop0' -- the bubble, every particle free"""
    free = [(TABLE + 2 * k, 0) for k in range(3, 14)]
    px, py = m[P1 + 5], m[P1 + 6]
    over = table_pokes([(0, px, py, 2), (1, px + 8, py, 1), (2, px, (py + 8) & 0xFF, 7)]) + free + \
        [(0x8DBD, m[0x8DBD] & 0xFE)]
    bx, by = 0x60, 0x50
    b = BUB + 10 * 11
    bub = [(b + i, v) for i, v in enumerate(HELD) if v is not None] + [(b + 5, bx), (b + 6, by)]
    pop = table_pokes([(0, bx, by, 2), (1, bx + 8, by, 1), (2, bx, by + 8, 7)]) + free + bub + \
        [(0x8DBD, m[0x8DBD] | 1)]
    pop0 = [(TABLE + 2 * k, 0) for k in range(14)] + bub + [(0x8DBD, m[0x8DBD] | 1)]
    return [('over', over, TARGETS), ('pop', pop, TARGETS), ('pop0', pop0, TARGETS_POP0)]


def forced_list(m):
    """the forced pokes (declared): every path in one walk; the borrow; the ROM's rows; the screen's edges; fourteen
       drawing; fourteen freeing"""
    free = lambda k0: [(TABLE + 2 * k, 0) for k in range(k0, 14)]
    pos = [(0x18 + 0x10 * k, 0x18 + 0x0C * k) for k in range(14)]
    all7 = table_pokes([(k, pos[k][0], pos[k][1], k + 1) for k in range(7)]) + free(7)
    return [
        ('all7', all7, None),
        ('borrow', table_pokes([(0, 0x40, 0x40, 2), (1, 0x60, 0x40, 1)]) + free(2) + [(0xFECA, 0)], 0),
        ('rom', table_pokes([(0, 0x80, 0x08, 2), (1, 0x90, 0x00, 1), (2, 0xA0, 0x0C, 7)]) + free(3), None),
        ('edge', table_pokes([(0, 0xF8, 0xA8, 2), (1, 0xF8, 0x10, 1), (2, 0x00, 0xA8, 7)]) + free(3), None),
        ('draw14', table_pokes([(k, pos[k][0], pos[k][1], 2) for k in range(14)]), None),
        ('free14', table_pokes([(k, pos[k][0], pos[k][1], 7) for k in range(14)]), None),
    ]


def world_job(wd):
    tag, rec = run_real(wd) if isinstance(wd, tuple) else run_state(wd)
    reps = []
    for st, sp, ret, f, key, nisr, path in rec.kept:
        x, _ = replay(st, (sp, ret))
        x['f'] = f
        x['same'] = nisr == 0 and x['acc'][1] == key[0] and x['ins'][1] == key[1]
        reps.append(x)
    forced, phase = [], []
    if isinstance(wd, tuple) and rec.first_live is not None:
        st, sp, ret, f0 = rec.first_live
        m = st[0]
        for name, pk, c in forced_list(m):
            x, xp = replay(st, (sp, ret), pk, c)
            fx = {'forced': name, 'pokes': pk, 'c': c, 'a': x}
            if name in ILIST:
                fx['ilist'] = [[p, o] for p, o in xp]
            forced.append(fx)
        for sname, pk, targets in scenes(m):
            _, pcs = replay(st, (sp, ret), pk)
            for name, tpc, nth in targets:
                hits = [o for p, o in pcs if p == tpc]
                if len(hits) <= nth:
                    raise Fail('scene %s: no visit %d of $%04X' % (sname, nth, tpc))
                for d in (0, 1):
                    shift = hits[nth] + d
                    y = phased(st, (sp, ret), shift, pk)
                    y.update({'scene': sname, 'target': name, 'pc': tpc, 'nth': nth, 'd': d, 'shift': shift, 'pokes': pk})
                    phase.append(y)
    out = {'tag': tag, 'n_calls': rec.n_calls, 'lives': rec.lives, 'replays': reps, 'forced': forced, 'phased': phase}
    if rec.pf is not None:
        out['passes'] = rec.passes
        out['isrs'] = rec.isrs
        out['ldar'] = rec.ldar
        out['base'] = rec.first_live[3] if rec.first_live else None
    return out


def capture(jobs):
    jobsl = list(REAL) + list(STATES)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, jobsl))
    tot = {'calls': 0, 'lives': 0, 'replays': 0}
    for x in res:
        tot['calls'] += x['n_calls']
        tot['lives'] += len(x['lives'])
        tot['replays'] += len(x['replays'])
        nr = len(x['replays'])
        ns = sum(1 for y in x['replays'] if y['same'])
        print('%-12s %6d calls, %5d live, %4d replays (%d plain-comparable), %d forced, %d phased%s' % (
            x['tag'], x['n_calls'], len(x['lives']), nr, ns, len(x['forced']), len(x['phased']),
            ', %d passes, %d ISRs' % (len(x['passes']), len(x['isrs'])) if 'isrs' in x else ''), flush=True)
    print('total:', tot)
    return {'meta': {'tool': 'tools/sparkacc.py', 'no_rom_bytes': True,
                     'note': 'the burst-sparkle walk ($C002): access programs and instruction grids, natural, replayed and '
                             'phased; seeds are game-RAM bytes read before written'},
            'script': [[k, v] for k, v in SCRIPT], 'real': [list(w) for w in REAL], 'lay_step': LAY_STEP,
            'lay': [[k, list(xs) if isinstance(xs, tuple) else xs, list(ys) if isinstance(ys, tuple) else ys, ph]
                    for k, xs, ys, ph in LAY],
            'frames': FRAMES, 'smc': SMC, 'held': HELD,
            'targets': [[n, '%04X' % p, k] for n, p, k in TARGETS],
            'targets_pop0': [[n, '%04X' % p, k] for n, p, k in TARGETS_POP0],
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
