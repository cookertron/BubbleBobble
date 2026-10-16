# -*- coding: utf-8 -*-
"""THE INTERRUPTS-ON BLOCKS: CAN AN ISR'S PHASE SHIFT BE CARRIED?  (M7.99e, a measurement before a design)

M7.99c / M7.99d time a block with interrupts OFF from its first instruction by its contended accesses from the
entry's frame phase (revealcont.py).  The blocks with ISRs INSIDE keep BB_EXT_K (M7.99c's C3): $94C2 (the
EXTEND completion), $A0BE (the storm wrap's reveal), $A9B5 (the giant hit's), $8F4C (the treasure room's
PERFECT), $88C0 (the umbrella's head).  After each ISR the main line resumes at that ISR's end, and its access
delays depend on that phase.  Two questions:

  (a) CARRY  Is the main line exact if each segment is replayed from the machine's OWN ISR end?  The plain run
             (CMIOSimulator, interrupts off, every contended access logged, no delay) gives the block's
             instruction stream on the exact clock: each instruction's end, its accesses, IFF after it and
             whether an interrupt may follow it (not after EI or a lone DD/FD prefix -- SkoolKit's rule).  The
             replay walks it from the entry's phase: an access at exact a waits DELAYS_48K[(phase + a + D + I)
             % 69888] (D the main line's delays so far, I the ISRs' wall T so far); after an instruction with
             IFF set whose wall end is < 32 T into a frame an interrupt is ACCEPTED -- and the replay adds the
             MACHINE's wall T of that ISR (the one unknown it does not model).  It must give every acceptance
             (instruction index and wall T) and the block's end EXACTLY as the machine run does (contended,
             interrupts on), and the machine's main line must be the plain run's (instruction and access
             counts, a hash of the PCs) -- or the row says where it first parts.
  (b) ISR    Each ISR inside: its wall T on the machine (acknowledge to its RET), the contention delays of its
             own accesses, and so its UNCONTENDED T (wall - delays) -- what the engine's isrCost charges (STATUS:
             the ISR's arms are uncontended instruction sums; contention is the declared gap).  The ISR's
             delays are where an engine stamping on its own isrCost would lose the phase; their sum over the
             block is the drift a lazy, frame-by-frame stamp would carry.  The engine's own uncontended error
             on these frames is NOT measured here.

SOURCES (each at its own phase and the sixteen forced phases 4,368 apart; extend: own + 4, it runs ~17M T):
  wrap      revealentry.reach('A0BE', round1_48 / r50_48): $A0BE to the reveal's RET
  giant     revealentry.reach('A9D7', fallcandy / peachfall): $A9B5 to the reveal's RET -- and (M7.100) at the six
            phases of revealentry's that put a boundary inside the award's DI window
  perfect   perfecttime.reach(lastdia81 / lastdia82 / r1_lead): $8F4C to $8D61 with the entry's SP + 2
  head      umbrella.reach(natural): $88C0 to the first HALT (not run)
  extend    extcomp's state, all six letters, $94C2 armed with player 1's IX: to $8D09
            (M7.104) and three of extendtime.py's VARIANTS at their own phase only -- tick (items that expire: the erase
            cells and rows, bands into the ROM), tickflood (the flood's erase and blit), storm ($8728's blit) -- the item
            pass's other access paths
  join      (M7.108) $9961 to its RET, reached by holding the joining key (JOIN_SRC)
  potion    (M7.115e) $890D (power-up type 12) to its RET: a type-12 laid under P1 and played on to the game's own
            $890D on round1_48 / r50_48 / round1_2p48 / lastdia81 (round 81: type 9, offset -1), and the real load's
            (potion.py's f600: 'real' its frame and phase there); each also at three phases per DI ($890D's, $8C14's)
            that put a boundary 1..3 T after its start; the seed (what the plain run reads), the T of POTION_MARKS'
            first visits and every write outside the reveal ($8C14..$894E) as [T, address, value]

NO ROM BYTE IS STORED: counts, T, indices.  GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/isrcarry.py measure [--jobs N]  -> build/isrcarry_fixture.json
        python tools/isrcarry.py verify  [--jobs N]  re-run and diff against the fixture (MATCH)
"""
import sys, os, json, time
from array import array
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import PC, T, SP, IFF, IXh, IXl
from skoolkit.cmiosimulator import CMIOSimulator, DELAYS_48K
import revealentry as RE
import revealcont as RC
import perfecttime as PT
import umbrella as UMB
import extcomp as EC
import extendtime as ET
import potion as PO

FIXTURE = 'build/isrcarry_fixture.json'
FRAME_T = 69888
INT_T = 32
PHASES = [k * (FRAME_T // 16) for k in range(16)]
EXT_PHASES = [k * (FRAME_T // 4) for k in range(4)]
EXT_VARIANTS = ('tick', 'tickflood', 'storm')   # M7.104: own phase only
# M7.100: the giant also at revealentry's six phases that put a boundary inside the award's DI window (lost interrupts)
GIANT_WIN = [FRAME_T - b for b in (40, 500, 1500, 2500, 3500, 4300)]
# M7.105: three phases per source that put a boundary d = 1..3 T after its first DI's START (the DI the instruction in
# progress there; scratchpad/distraddle/probe.py: lost at 1..6, taken at -2..0 -- the line is sampled at an instruction's
# end, and the DI's end has cleared IFF)
STRADDLE = (1, 2, 3)
# M7.115e: and the CLOSING edge of the potion's head window ($890D DI .. $891D EI) -- a boundary 32 T before the end of the
# instruction after the EI (its whole pulse inside the window: lost) and 31 T before (the pulse still up at the close: taken
# there).  The reveal's window ($8C14 .. $8C4C EI) has no such phase: ~37,000 T of contended stores re-sync its main line
# to the ULA, so its close lands at frame phase ~188 or ~-2 whatever the entry (round1_48: the fixed point cycles)
CLOSE = (32, 31)
GUARD = set(range(0xD000, 0xD300))
REVEAL = 0x8C28
MASK = (1 << 61) - 1


class Fail(Exception):
    pass


def end_rule(kind, r, mem):
    """a predicate (called before each main-line instruction) that says the block is over"""
    if kind in ('wrap', 'giant'):
        st = {}

        def f(p):
            if p == REVEAL and 'sp0' not in st:
                st['sp0'], st['ret'] = r[SP], mem[r[SP]] | (mem[r[SP] + 1] << 8)
            return 'sp0' in st and p == st['ret'] and r[SP] == st['sp0'] + 2
        return f
    if kind == 'perfect':
        sp0 = r[SP]
        return lambda p: p == PT.BACK and r[SP] == sp0 + 2
    if kind == 'head':
        return lambda p: mem[p] == 0x76
    if kind == 'extend':
        return lambda p: p == EC.ADVANCE
    if kind in ('join', 'potion'):                   # M7.108: $9961 entered (the CALL done): to its RET at $8D34
        sp0 = r[SP]                                  # M7.115e: $890D entered by $8838 JP (HL) -- its RET is $87B2's
        ret = mem[sp0] | (mem[(sp0 + 1) & 0xFFFF] << 8)
        return lambda p: p == ret and r[SP] == (sp0 + 2) & 0xFFFF
    raise Fail(kind)


def start(src):
    """a harness at the source's entry"""
    kind, st = src['kind'], src['state']
    if kind == 'extend':
        h, m = EC.new()
        EC.ready(m)
        if src.get('variant'):                       # M7.104: extendtime's poke, player 1 completing
            who, poke = ET.VARIANTS[src['variant']]
            if who:
                raise Fail(src['name'] + ': a player-2 variant')
            poke(m)
        EC.arm(h, EC.COMPLETE, ix=EC.PLAYERS[0])
        return h
    h = RE.new('round1_48')
    h.load_state(st)
    if kind == 'join':                               # M7.108: the joining key held (load_state releases every key)
        h.ports.press(0xF7, 0xFF & ~src['key'])
    return h


def sim_for(src, h, log=None):
    """RC.sim_of, and for the join (M7.108) the harness's ports as the tracer: $9969 IN A,($FE) reads the key"""
    sim = RC.sim_of(h, log)
    if src['kind'] == 'join':
        sim.set_tracer(h.ports)
    return sim


# M7.108: the join's sources -- [name, world, pokes, key (2: P2 joins, 1: P1)], each reached by playing on from the world
# (interrupts on, contended) with the key held from frame 2 to the first $9961 that takes the join
JOIN_SRC = [('join:round1_48', 'round1_48', [], 2),
            ('join:r20_48', 'r20_48', [], 2),
            ('join:p1_round1', 'round1_48', [(0xFD87, 0x61), (0xFD91, 0xE0), (0xFDE6, 2)], 1)]


def reach_join(args):
    name, world, pokes, key = args
    h = RE.new(world)
    m, r = h.memobj.m, h.sim.registers
    for a, v in pokes:
        m[a] = v
    h.ports.release_all()
    t0 = r[T]
    try:
        RE.go(h, {}, 2 * FRAME_T)
    except RE.Fail:
        pass
    h.ports.press(0xF7, 0xFF & ~key)
    RE.go(h, {0x9961: lambda hh: True}, 20 * FRAME_T)
    st = h.save_state()
    sim, mem = h.sim, h.memobj.m                     # the join taken: its run reaches $9998 (checked, then undone)
    sp0 = r[SP]
    ret = mem[sp0] | (mem[(sp0 + 1) & 0xFFFF] << 8)
    seen = False
    while not (r[PC] == ret and r[SP] == (sp0 + 2) & 0xFFFF):
        seen = seen or r[PC] == 0x9998
        sim.opcodes[mem[r[PC]]]()
    if not seen:
        raise Fail(name + ': the first $9961 after the key did not join')
    return {'name': name, 'kind': 'join', 'state': st, 'own': st[1][T] % FRAME_T, 'key': key}


# M7.115e: THE POTION'S sources -- [name, world]: a type-12 item laid in the power-up entry under P1 (potion.py's poke) and
# the world played on (interrupts on, contended) to the game's own $890D; 'real' is potion.py's f600 world, the real load
POTION_SRC = [('potion:round1_48', 'round1_48'), ('potion:r50_48', 'r50_48'), ('potion:2p', 'round1_2p48'),
              ('potion:lastdia81', 'lastdia81'), ('potion:real', 'real')]
POTION_MARKS = (0x8915, 0x891D, 0x891E, 0x8949, 0x8C14, 0x8C28, 0x894E, 0x8950, 0x898F, 0x8994, 0x899C, 0x8974)


def reach_potion(args):
    name, world = args
    if world == 'real':
        x = PO.reach('f600')
        return {'name': name, 'kind': 'potion', 'state': x['state'], 'own': x['phase'], 'real': [x['frame'], x['phase']]}
    h = RE.new(world)
    m = h.memobj.m
    m[0x9603] = (m[0xFD85] & 0xF0) | 12
    m[0x9604] = (m[0xFD86] & 0xF8) | 1
    RE.go(h, {0x890D: lambda hh: True}, 10 * FRAME_T)
    st = h.save_state()
    return {'name': name, 'kind': 'potion', 'state': st, 'own': st[1][T] % FRAME_T}


def plain(src):
    """the block's instruction stream on the exact clock: per instruction its end, the access count after it,
    and flags (1 IFF after it, 2 an interrupt may follow it); the accesses' exact T; a hash of the PCs"""
    h = start(src)
    log = []
    sim = sim_for(src, h, log)
    r, mem = sim.registers, sim.memory
    t0 = r[T]
    done = end_rule(src['kind'], r, mem)
    ends, nacc, flags = array('q'), array('l'), bytearray()
    hsh = 0
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if done(p):
            break
        if mem[p] == 0x76:
            raise Fail('%s: a HALT inside the block at $%04X' % (src['name'], p))
        hsh = (hsh * 1000003 + p) & MASK
        op = mem[p]
        sim.opcodes[op]()
        ends.append(r[T] - t0)
        nacc.append(len(log))
        ok = not (op == 0xFB or (op in (0xDD, 0xFD) and r[PC] == (p + 1) & 0xFFFF))
        flags.append((1 if r[IFF] else 0) | (2 if ok else 0))
        if r[T] - t0 > 40 * 10 ** 6:
            raise Fail('%s: no end' % src['name'])
    acc = array('q', (t - t0 for t in log))
    return ends, nacc, flags, acc, hsh


def machine(src, phase, snaps=None):
    """contended, interrupts ON, from the entry at the phase to the block's end: the main line's instruction
    and access counts and PC hash, its delays, each ISR [main-line instruction index it follows, wall T
    of the acceptance from the entry, wall T of the ISR, its own delays, branch], the end's wall T"""
    h = start(src)
    sim = sim_for(src, h)
    r, mem = sim.registers, sim.memory
    fd = FRAME_T
    if phase is not None:
        r[T] = (r[T] // fd) * fd + phase
    t0 = r[T]
    done = end_rule(src['kind'], r, mem)
    bucket = [0, 0]                                  # main, ISR delays
    stack = []
    orig = sim.contend

    def contend(t, timings):
        d = orig(t, timings)
        bucket[1 if stack else 0] += d
        return d
    sim.contend = contend
    isrs = []
    n_ins = 0
    n_acc = 0
    hsh = 0
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        while stack and p == stack[-1][0] and r[SP] == stack[-1][1]:
            ret, spb, ta, k, d0 = stack.pop()
            isrs[k][2] = r[T] - ta
            isrs[k][3] = bucket[1] - d0
        if not stack:
            if done(p):
                break
            if mem[p] == 0x76:
                raise Fail('%s: a HALT inside the block at $%04X' % (src['name'], p))
            hsh = (hsh * 1000003 + p) & MASK
            n_ins += 1
        elif mem[p] == 0x76:
            raise Fail('a HALT inside an ISR')
        sim.opcodes[mem[p]]()
        if r[IFF] and r[T] % fd < INT_T:
            ta, spb = r[T], r[SP]
            odd = (mem[0x8DBD] + 1) & 1
            g = (mem[0xFEC4] if odd else mem[0xFEC5]) != 0
            pre = bytes(mem.m[0x4000:0x10000]) if snaps is not None and not stack else None
            if sim.accept_interrupt(r, mem, p):
                if pre is not None:
                    snaps.append(pre)
                isrs.append([n_ins - 1, ta - t0, None, None, ('odd' if odd else 'even') + ('' if g else '_closed')]
                            + ([1] if stack else []))
                stack.append((mem[r[SP]] | (mem[(r[SP] + 1) & 0xFFFF] << 8), spb, ta, len(isrs) - 1, bucket[1]))
        if r[T] - t0 > 60 * 10 ** 6:
            raise Fail('%s: no end on the machine' % src['name'])
    return {'phase0': t0 % fd, 'n_ins': n_ins, 'hash': hsh, 'main_delay': bucket[0], 'isrs': isrs,
            'end': r[T] - t0}


def replay(pl, phase, isr_walls):
    """the main line from the plain stream at the phase, the machine's ISR walls dropped in at each acceptance
    the replay predicts: [[instruction index, wall T]...], the end's wall T, the main line's delays"""
    ends, nacc, flags, acc, _ = pl
    D = I = j = 0
    out = []
    k = 0
    for i in range(len(ends)):
        hi = nacc[i]
        while j < hi:
            D += DELAYS_48K[(phase + acc[j] + D + I) % FRAME_T]
            j += 1
        if flags[i] == 3:
            w = ends[i] + D + I
            if (phase + w) % FRAME_T < INT_T:
                out.append([i, w])
                if k >= len(isr_walls):
                    return out, None, D
                I += isr_walls[k]
                k += 1
    return out, ends[-1] + D + I if len(ends) else 0, D


def acc_k(pl):
    """M7.101: each access of the plain run with the T into its instruction (k): a digest of 'T:k;' over the stream
    (T from the entry) and the k histogram -- what the engine's access programs must carry (bbAcc)"""
    import hashlib
    ends, nacc, _, acc, _ = pl
    s, hist, n0, start = [], {}, 0, 0
    for j in range(len(ends)):
        for i in range(n0, nacc[j]):
            k = acc[i] - start
            s.append('%d:%d;' % (acc[i], k))
            hist[str(k)] = hist.get(str(k), 0) + 1
        n0, start = nacc[j], ends[j]
    return hashlib.sha1(''.join(s).encode()).hexdigest()[:16], dict(sorted(hist.items(), key=lambda e: int(e[0])))


def first_di(src, nth=1):
    """M7.105: the main-line index of the source's first DI (IFF 1 -> 0), or None (M7.115e: the nth)"""
    h = start(src)
    sim = sim_for(src, h, [])
    r, mem = sim.registers, sim.memory
    done = end_rule(src['kind'], r, mem)
    i, prev = 0, r[IFF]
    while not done(r[PC]):
        sim.opcodes[mem[r[PC]]]()
        if prev and not r[IFF]:
            nth -= 1
            if not nth:
                return i
        prev = r[IFF]
        i += 1
    return None


def di_start(src, phase, idx):
    """M7.105: contended, interrupts ON from the phase: the wall T of main-line instruction idx-1's end (before any
    interrupt it lets in) -- the start of instruction idx"""
    if idx == 0:
        return 0
    h = start(src)
    sim = sim_for(src, h)
    r, mem = sim.registers, sim.memory
    r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    t0, n, stack = r[T], 0, []
    while True:
        p = r[PC]
        while stack and p == stack[-1][0] and r[SP] == stack[-1][1]:
            stack.pop()
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        sim.opcodes[mem[p]]()
        if not stack:
            n += 1
            if n == idx:
                return r[T] - t0
        if r[IFF] and r[T] % FRAME_T < INT_T:
            spb = r[SP]
            if sim.accept_interrupt(r, mem, p):
                stack.append((mem[r[SP]] | (mem[(r[SP] + 1) & 0xFFFF] << 8), spb))


def first_ei(src, nth=1):
    """M7.115e: the main-line index of the source's nth EI (IFF 0 -> 1), or None"""
    h = start(src)
    sim = sim_for(src, h, [])
    r, mem = sim.registers, sim.memory
    done = end_rule(src['kind'], r, mem)
    i, prev = 0, r[IFF]
    while not done(r[PC]):
        sim.opcodes[mem[r[PC]]]()
        if not prev and r[IFF]:
            nth -= 1
            if not nth:
                return i
        prev = r[IFF]
        i += 1
    return None


def fixed_phase(src, idx, off, what):
    """the phase (a fixed point) that puts a frame boundary `off` T after the start of main-line instruction idx"""
    ph = src['own'] or 0
    for _ in range(12):
        want = (-(di_start(src, ph, idx) + off)) % FRAME_T
        if want == ph:
            return ph
        ph = want
    raise Fail('%s: no phase puts a boundary %d T from %s' % (src['name'], off, what))


def straddle(src):
    """M7.105: [(d, phase)...] -- each phase (a fixed point) puts a frame boundary d T after the first DI's start
    (M7.115e: the potion's two DIs, $890D's and $8C14's -- [(d, phase, nth)...] -- and its head window's close, the end of
    the instruction after $891D's EI: [(-e, phase, 1)...], the boundary e = 32 / 31 T before it)"""
    out = []
    for nth in ((1, 2) if src['kind'] == 'potion' else (1,)):
        idx = first_di(src, nth)
        if idx is None:
            continue
        for d in STRADDLE:
            ph = fixed_phase(src, idx, d, 'its DI')
            out.append((d, ph) if src['kind'] != 'potion' else (d, ph, nth))
    if src['kind'] == 'potion':
        idx = first_ei(src, 1)
        for e in CLOSE:
            out.append((-e, fixed_phase(src, idx + 2, -e, "its head window's close"), 1))
    return out


def run_source(args):
    src, phases = args
    pl = plain(src)
    rows = []
    sd = [] if src.get('variant') else straddle(src)
    for i, ph in enumerate([src['own']] + phases + [x[1] for x in sd]):
        m = machine(src, ph)
        ph0 = m['phase0']
        same = m['n_ins'] == len(pl[0]) and m['hash'] == pl[4]
        top = [x for x in m['isrs'] if len(x) == 5]   # nested ISRs ride inside their parent's wall
        rp, rend, rD = replay(pl, ph0, [x[2] for x in top])
        acc_ok = [[x[0], x[1]] for x in top] == rp
        rows.append({'phase0': ph0, 'forced': i > 0, 'same_stream': same,
                     'n_ins': m['n_ins'], 'end': m['end'], 'replay_end': rend, 'main_delay': m['main_delay'],
                     'replay_delay': rD, 'accepts_exact': acc_ok, 'exact': acc_ok and rend == m['end'] and same,
                     'isrs': m['isrs'], 'first_diff': None if acc_ok else first_diff([[x[0], x[1]] for x in top], rp)})
        if i > len(phases):
            rows[-1]['straddle'] = sd[i - len(phases) - 1][0]
            if src['kind'] == 'potion':
                rows[-1]['di'] = sd[i - len(phases) - 1][2]
    out = {'name': src['name'], 'kind': src['kind'], 'own': src['own'], 'n_ins': len(pl[0]), 'n_acc': len(pl[3]),
           'exact_T': int(pl[0][-1]), 'acc_k': acc_k(pl), 'rows': rows}
    if src['kind'] == 'join':                        # M7.108: the bytes the run reads, for the engine's replay (LZ8)
        out['seed'] = join_seed(src)
        out['key'] = src['key']
    if src['kind'] == 'potion':                      # M7.115e: the same, and its marks and the writes outside the reveal
        x = {}
        out['seed'] = join_seed(src, x)
        out['marks'], out['ext'] = x['marks'], x['ext']
        if 'real' in src:
            out['real'] = src['real']
    return out


class ValMem(RE.SeedMem):
    """M7.115e: SeedMem, and each write's value beside it (the same writes: outside the stack)"""
    __slots__ = ('val',)

    def __init__(self, data):
        RE.SeedMem.__init__(self, data)
        self.val = []

    def __setitem__(self, i, v):
        if self.regs is not None:
            sp = self.regs[SP]
            if not (sp - 64 <= i < sp + 64):
                self.val.append(v & 0xFF)
        RE.SeedMem.__setitem__(self, i, v)


def join_seed(src, potion=None):
    """M7.108: the join's plain run (uncontended, interrupts off): every byte >= $4000 it READS before writing it, as
    [start, hex] runs (revealentry's seed_of), and its writes' count and digest.  M7.115e: the potion's too -- and into
    `potion` the T of each POTION_MARKS PC's first visit (from the entry) and every write outside the reveal ($8C14's
    hook to $894E) as [T, address, value]"""
    h = start(src)
    m0 = bytes(h.memobj.m)
    rm = (ValMem if potion is not None else RE.SeedMem)(h.memobj.m)
    RE.plain(h)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    r = h.sim.registers
    rm.regs = r
    t0 = r[T]
    done = end_rule(src['kind'], r, rm)
    marks = {}
    while not done(r[PC]):
        p = r[PC]
        if potion is not None and p in POTION_MARKS and p not in marks:
            marks[p] = r[T] - t0
        rm.tins[0] = r[T]
        h.sim.opcodes[rm.m[p]]()
    rm.regs = None
    if potion is not None:
        lo, hi = marks.get(0x8C14), marks.get(0x894E)
        if lo is None or hi is None:
            raise Fail('%s: no $8C14 / $894E in the plain run' % src['name'])
        potion['marks'] = {'%04X' % k: v for k, v in sorted(marks.items())}
        potion['ext'] = [[t - t0, a, v] for (a, t), v in zip(rm.wr, rm.val) if not (lo <= t - t0 < hi)]
        potion['marks']['end'] = r[T] - t0
    return RE.seed_of(rm, m0, t0)


def first_diff(a, b):
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else None
        y = b[i] if i < len(b) else None
        if x != y:
            return [i, x, y]
    return None


def sources(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        wr = list(ex.map(RE.reach, [('A0BE', w) for w in ('round1_48', 'r50_48')]))
        gi = list(ex.map(RE.reach, [('A9D7', w) for w in ('fallcandy', 'peachfall')]))
        pf = list(ex.map(PT.reach, ['lastdia81', 'lastdia82', 'r1_lead']))
        um = UMB.reach(UMB.RUNS[0])
        jn = list(ex.map(reach_join, JOIN_SRC))
        po = list(ex.map(reach_potion, POTION_SRC))
    out = []
    for x in wr:
        out.append({'name': 'wrap:' + x['world'], 'kind': 'wrap', 'state': x['state'], 'own': x['phase']})
    for x in gi:
        out.append({'name': 'giant:' + x['world'], 'kind': 'giant', 'state': x['state'], 'own': x['phase']})
    for x in pf:
        out.append({'name': 'perfect:' + x['name'], 'kind': 'perfect', 'state': x['state'], 'own': x['phase']})
    out.append({'name': 'head:' + UMB.RUNS[0][0], 'kind': 'head', 'state': um['state'],
                'own': um['state'][1][T] % FRAME_T})
    out.append({'name': 'extend:extcomp', 'kind': 'extend', 'state': None, 'own': None})
    for v in EXT_VARIANTS:
        out.append({'name': 'extend:' + v, 'kind': 'extend', 'state': None, 'own': None, 'variant': v})
    out.extend(jn)                                   # M7.108
    out.extend(po)                                   # M7.115e
    return out


def measure(jobs=6):
    srcs = sources(jobs)
    args = [(s, ([] if s.get('variant') else EXT_PHASES) if s['kind'] == 'extend'
             else PHASES + (GIANT_WIN if s['kind'] == 'giant' else [])) for s in srcs]
    args.sort(key=lambda a: a[0]['kind'] != 'extend')   # the long one first
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(run_source, args))
    return {'meta': {'phases': PHASES, 'ext_phases': EXT_PHASES, 'giant_win': GIANT_WIN, 'frame_t': FRAME_T,
                     'isr': '[main-line instruction index, accept T from entry, wall T, own delays, branch(, nested)]'},
            'sources': {r['name']: r for r in res}}


def report(out):
    tot = ex = 0
    for n, s in out['sources'].items():
        rows = s['rows']
        tot += len(rows)
        ex += sum(r['exact'] for r in rows)
        isr = [x for r in rows for x in r['isrs']]
        dl = [x[3] for x in isr]
        cum = [sum(x[3] for x in r['isrs']) for r in rows]
        br = sorted(set(x[4] for x in isr))
        print('%-22s ins %8d acc %7d exact %9d | exact %d/%d | ISRs/run %s | ISR delay %s..%s | sum/run %s..%s | %s' % (
            n, s['n_ins'], s['n_acc'], s['exact_T'], sum(r['exact'] for r in rows), len(rows),
            '%d..%d' % (min(len(r['isrs']) for r in rows), max(len(r['isrs']) for r in rows)),
            min(dl) if dl else '-', max(dl) if dl else '-', min(cum), max(cum), ','.join(br)))
        for r in rows:
            if not r['exact']:
                print('    phase %d: stream %s, accepts %s (first diff %s), end %s vs %s' % (
                    r['phase0'], r['same_stream'], r['accepts_exact'], r['first_diff'], r['replay_end'], r['end']))
    print('replay exact on %d of %d runs' % (ex, tot))


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
        if old == json.loads(json.dumps(out)):
            print('MATCH (%.1f s)' % (time.time() - t))
        else:
            print('DIFF (%.1f s)' % (time.time() - t))
            sys.exit(1)


if __name__ == '__main__':
    main()
