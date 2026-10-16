# -*- coding: utf-8 -*-
"""M7.54 -- $9037's BLOCK, WRITE BY WRITE: where every byte, gate and edge of the HURRY UP!
banner lands in main-loop T, and what the machine's frame interrupts do while it runs.

M7.19 measured the block END TO END (2,963,896 T contended, hurry.py 'cost') and M7.52 timed
its speaker train (beeper.py 'hurry').  Neither says WHEN inside the block the banner moves,
and the port ran all 22 walker steps in one call inside one frame.  This oracle records:

  direct    $9037 called on hurry.py's 'ready' world with interrupts OFF, UNCONTENDED (a plain
            Simulator with fast_djnz/fast_ldir OFF, so every LDIR iteration is its own step and
            its own T stamp) and CONTENDED: every write the block makes, in order, classed --
               E  $9910's LDIR: a display byte out of the shadow   (address only)
               A  $9932: an erase ATTRIBUTE, re-derived from the palette (address, value)
               R  $995C: $995A's run -- the recolour and the flash (address, value)
               G  $8052: $802E's glyph blit -- (address, CHARACTER CODE, GLYPH ROW), NEVER the
                  byte, which is the SPECTRUM ROM's; the port draws BB_BANNER_FONT
               O  any other RAM write outside the stack (address, value, PC)
            and every event PC ($90DA walk, $90E9 delay end, $9904 erase, $9940 recolour,
            $9114 glyph call, $911A Boris, the train's OUTs, the gates, $90A9, $90C1, $90C0)
            with its T from $9037's entry.  Stamps are the T at the START of the writing
            instruction (an LDIR iteration is an instruction), as sfx_trace.py stamps an OUT.
            Also: the TWO-PLAYER world (round1_2p48, P2 in play): $913D's JR nz is taken at both
            Boris setups -- $914B is called once, not twice -- so everything after each setup
            comes 101 T sooner (exact), 184..333 T contended.
  latched   the same with $90AA = 1 ($90AC RET nz): the tail from $90A3, both contentions
  tails     the tail from $90A3 with ($AA57) = 2, 3, 5 and 8 (the temper walks 256, 1, 3 and 6
            slots -- $90D7's DJNZ from B = 0 is 256 turns)
  bits      exact, with bit 5 of the colour shadow FLIPPED under every banner attribute cell:
            each bit-5 cell costs $9932's loop 8 T more (JR z not taken 7 + LD A,($830A) 13
            against JR z taken 12 + nothing), which moves the recolour and the glyphs after it
  phases    the contended block at eight frame phases: its cost, and every delay end's drift
  natural   the machine's OWN block, interrupts ON, contended, from round1_48 + ready: every
            ISR bracketed -- the main loop's last T, the $8D72 entry after the 19 T IM2
            response and the 22 T $FFFF JR / $FFF4 JP trampoline, the T after its RET,
            ($FEC4)/($FEC5) at entry and the parity it branches on -- the natural T of every
            block write, the events and the chain after the block with their frames, a RAM
            diff across each ISR inside the block with the block's own writes taken out, and
            every main-loop READ of the four counter bytes the ISR writes: there are TWO,
            $903D's LD DE,($8DBD) at T 25, before the block's first write
  heldout   the same on worlds the port's gates were NOT fitted to: round1_2p48 at its own
            phase (40,542 T into its frame), and round1_48 entered 15,500 T later (22,909) --
            a phase where the machine's block ends in the 42nd frame and the port's ledger
            puts it in the 43rd (declared)
  tailisr   the natural place the block's run-ahead premise fails (the other is the ENTRY: an
            interrupt before $9055 shuts ($FEC4), 135 T in -- declared in game.js, not measured
            here): the tail reopens the gates at
            $90A3/$90A6 BEFORE $90C1's walk read-modify-writes each enemy's +7 (SET/RES 2) and
            +5 (AND $F8), so an interrupt inside the tail -- the 43rd, EVEN at the natural fire
            -- runs the bubble manager and the walk then works on what it left.  The block runs
            at its natural phase to $90A1, then the frame interrupt is placed D T after $90A3:
               release  bubble 0 holds slot 4's enemy at age $FF with $B657 = 1, so the even
                        pass's $B679 releases it; D = 137, 282, 297, 309, 310, 316, 320, 321, 327 --
                        the window's edges: slot 4's $90D3 LD A,(HL) starts 309 T after $90A3 and
                        its $90D5 store 320 T, and an interrupt raised inside either instruction is
                        taken at its end
               capture  a travelling bubble one 8-px step left of the last live enemy, D = 20
               escape   a risen bubble holding that enemy, one age tick short of the wrap, D = 20
               odd      the release scene's world with the clock one on, so the 43rd ISR is
                        ODD (forced state -- not the natural parity), D = 27
  fireclock the fire clock when the machine's own interrupts count up to the threshold: clock
            poked to threshold - K, run until $9052 -- it fires at threshold + 1, and every
            shipped threshold is even, so the 43rd interrupt after the fire is even
  keys      the same run with keys pressed at $9037's entry: SYM (the pause) and CAPS+SPACE
            (BREAK) held from then on, and each released at the block's RET; every IN the
            machine makes.  (Held from the START of the run, SYM pauses round1_48's pass
            BEFORE $9037 -- $8FE7 comes first in the chain -- so the keys go down at $9037.)
            No IN comes while BOTH gates are shut; an odd interrupt after $90A3 would run the
            key reader, and the port's does too.

NO ROM BYTE IS STORED: glyph writes carry (code, row); the bytes $9910 copies are the shadow's
and are not stored either -- a gate reads the port's own shadow.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/hurryblock.py capture [--jobs N]   -> build/hurryblock_fixture.json
        python tools/hurryblock.py verify  [--jobs N]   re-run and diff against the fixture
        python tools/hurryblock.py direct|phases|natural|heldout|tailisr|fireclock|keys
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import harness
from harness import Harness, PC, T, SP, IFF, D as RD, E as RE
from skoolkit.simulator import Simulator
import portconfig as pc
from keyprobe import press
import hurry as HU

FIXTURE = 'build/hurryblock_fixture.json'
GUARD = set(range(0xD000, 0xD300))
FRAME_T = 69888
ISR_IN, ISR_RET = 0x8D72, 0x8DA1
PHASES = [k * (FRAME_T // 8) for k in range(8)]
STATE = HU.STATE
STATE_2P = 'round1_2p48'
COUNTERS = (0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE)          # what a closed-gate ISR writes
B0 = 0xFED8                                           # bubble slot 0
E4 = 0xFD80 + 40                                      # slot 4: the enemy the release scene holds
TAIL_D = (137, 282, 297, 309, 310, 316, 320, 321, 327)
BOUNDARY_AT = 15500                                   # round1_48 + 15,500 T: entry phase 22,909

# the main-loop PCs of the block, and what each one is
EVT = {
    0x9037: 'entry', 0x9052: 'g5:=0', 0x9055: 'g4:=0', 0x9058: 'fired',
    0x90DA: 'walk', 0x90E9: 'delay_end', 0x9904: 'erase', 0x9101: 'erase_done',
    0x9940: 'recolour', 0x9114: 'glyphs', 0x9117: 'glyphs_done', 0x911A: 'boris',
    0x9068: 'train', 0x906F: 'flash_out0', 0x907D: 'flash', 0x9081: 'flash_out0b',
    0x908F: 'high', 0x9094: 'walk2_setup', 0x909A: 'walk3_setup',
    0x90A3: 'g4:=1', 0x90A6: 'g5:=1', 0x90A9: 'anger_test', 0x90AC: 'ret_nz',
    0x90B2: 'anger_g4:=0', 0x90C1: 'anger_walk', 0x90BA: 'anger_g4:=1',
    0x90BD: 'anger_g5:=1', 0x90C0: 'ret',
}
# the chain after $9037, and the loop around it (natural runs only)
CHAIN = {
    0x8D52: '8D52', 0x925A: '925A', 0x931A: '931A', 0x9AEB: '9AEB', 0x8E2A: '8E2A',
    0x8E3A: '8E3A', 0x8D61: '8D61', 0x8D63: '8D63', 0x8D6F: '8D6F', 0x8D70: '8D70',
    0x8D09: '8D09', 0x8D0C: '8D0C', 0x8D25: '8D25', 0x8FE7: '8FE7', 0x8FFB: '8FFB',
    0x9005: '9005', 0x900B: '900B', 0x917C: '917C', 0x8CDC: '8CDC',
}


class Fail(Exception):
    pass


# ---------------------------------------------------------------- instrumentation
WLOG = None                                   # [(T, PC, addr, value)] while not None
RLOG = None                                   # [(T, PC, port)] port reads while not None
MREAD = None                                  # [(T, PC, addr)] reads of COUNTERS while not None


def _setitem(self, i, v):
    if i < 0x4000:
        self.rom_writes += 1
        return
    if WLOG is not None:
        r = self.sim.registers
        WLOG.append((r[T], r[PC], i, v))
    self.m[i] = v


def _getitem(self, i):
    if MREAD is not None and i in COUNTERS:
        r = self.sim.registers
        MREAD.append((r[T], r[PC], i))
    return self.m[i]


_real_read = harness.Ports.read_port


def _read_port(self, registers, port):
    if RLOG is not None:
        RLOG.append((registers[T], registers[PC], port))
    return _real_read(self, registers, port)


harness.Mem.__setitem__ = _setitem
harness.Mem.__getitem__ = _getitem
harness.Ports.read_port = _read_port


def new(contended, state=STATE, anger=0):
    """hurry.py's 'ready' world; UNCONTENDED runs get a plain Simulator with fast_djnz and
    fast_ldir OFF, so every LDIR iteration is its own step and its own T stamp"""
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[0x8DC4] != 0xC9:
        raise Fail('%s: not the 48K branch (TRAPS #28)' % state)
    if not contended:
        regs = list(h.sim.registers)
        sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
        sim.registers[:] = regs
        h.sim = sim
        h.memobj.sim = sim
        sim.set_tracer(h.ports)
        h.frame_duration, h.int_active = sim.frame_duration, sim.int_active
    HU.ready(m)
    m[HU.OP_ANGER] = anger
    return h, m


def de(r):
    return r[RE] | (r[RD] << 8)


def to_9037(h):
    """interrupts ON, to $9037's entry through the machine's own frames; every stop is checked
    against the guard AND for having reached its target"""
    r = h.sim.registers
    t_give_up = r[T] + 5 * FRAME_T
    while True:
        why, n = h.run_until({ISR_IN, 0x9037} | GUARD, limit=10 ** 6, interrupts=True, stride=1)
        if r[PC] in GUARD:
            raise Fail('guard at $%04X' % r[PC])
        if r[PC] == 0x9037:
            return
        if r[T] > t_give_up or why != 'target':
            raise Fail('$9037 not reached within five frames (PC $%04X)' % r[PC])
        why, n = h.run_until({ISR_RET} | GUARD, limit=10 ** 6, interrupts=True, stride=1)
        if r[PC] in GUARD or why != 'target':
            raise Fail('an ISR did not reach its RET (PC $%04X, %s)' % (r[PC], why))
        h.step(1)


class Tracer:
    """one instruction at a time -- the harness's own step() loop with the IM2 response split
    out: every event PC, every write classed, every ISR bracketed"""

    def __init__(self, h, t0):
        self.h, self.t0 = h, t0
        self.events, self.writes, self.isrs, self.chain = [], [], [], []
        self.glyph = None                       # (code, row) of the $8052 about to run
        self.in_isr = None

    def run(self, stop, limit=4 * 10 ** 6, interrupts=False, until_chain=None, snap_isr=False):
        global WLOG
        h = self.h
        sim = h.sim
        regs, opcodes, mem = sim.registers, sim.opcodes, sim.memory
        fd, ia = h.frame_duration, h.int_active
        n = 0
        WLOG = []
        wl = WLOG
        try:
            while n < limit:
                p = regs[PC]
                if p in GUARD:
                    raise Fail('PC entered the guard at $%04X' % p)
                if p in stop:
                    return p
                t = regs[T]
                if self.in_isr is None:
                    tag = EVT.get(p)
                    if tag is not None:
                        self.events.append([t - self.t0, tag])
                    ct = CHAIN.get(p)
                    if ct is not None:
                        self.chain.append([t - self.t0, ct])
                        if until_chain is not None and until_chain(ct, t):
                            return p
                    if p == 0x8052:             # the glyph blit: DE -> $3C00 + 8*code + row
                        s = (de(regs) - 0x3C00) & 0xFFFF
                        self.glyph = (s // 8, s % 8)
                elif self.in_isr['tin'] is None and p == ISR_IN:
                    self.in_isr['tin'] = t - self.t0
                if interrupts and mem[p] == 0x76 and regs[IFF]:
                    raise Fail('a HALT inside the traced span at $%04X' % p)
                k = len(wl)
                opcodes[mem[p]]()
                for (tw, pw, a, v) in wl[k:]:
                    self.classify(tw, pw, a, v)
                del wl[:]
                if p == ISR_RET and self.in_isr is not None:
                    x = self.in_isr
                    # [the main loop's last T, $8D72's T, the T after the RET, ($FEC4), ($FEC5),
                    #  the parity it branches on, SP]; the IM2 response is 19 T plus the 22 T
                    #  $FFFF JR / $FFF4 JP trampoline -- all of it is time the main loop loses
                    row = [x['acc0'], x['tin'], regs[T] - self.t0, x['g4'], x['g5'], x['par'], x['sp']]
                    if x['snap'] is not None:
                        now = bytes(mem.m[0x4000:0x10000])
                        snap = x['snap']
                        row.append([0x4000 + i for i in range(len(now)) if now[i] != snap[i]])
                    self.isrs.append(row)
                    self.in_isr = None
                if interrupts and regs[IFF] and regs[T] % fd < ia:
                    t_end = regs[T]
                    snap = bytes(mem.m[0x4000:0x10000]) if snap_isr else None
                    sp = regs[SP]
                    sim.accept_interrupt(regs, mem, p)
                    if regs[PC] != 0xFFFF:
                        raise Fail('an interrupt went to $%04X, not the $FFFF trampoline' % regs[PC])
                    m = mem.m
                    self.in_isr = {'acc0': t_end - self.t0, 'tin': None, 'g4': m[0xFEC4], 'g5': m[0xFEC5],
                                   'par': (m[0x8DBD] + 1) & 1, 'snap': snap, 'sp': sp}
                n += 1
            raise Fail('limit: PC $%04X' % regs[PC])
        finally:
            WLOG = None

    def classify(self, tw, pw, a, v):
        t = tw - self.t0
        isr = 1 if self.in_isr is not None else 0
        if 0x4000 <= a < 0x5B00:
            if pw == 0x9910:
                self.writes.append([t, a, 'E', isr])
            elif pw == 0x9932:
                self.writes.append([t, a, 'A', isr, v])
            elif pw == 0x995C:
                self.writes.append([t, a, 'R', isr, v])
            elif pw == 0x8052:
                self.writes.append([t, a, 'G', isr, self.glyph[0], self.glyph[1]])
            else:
                self.writes.append([t, a, '?%04X' % pw, isr])
        else:
            sp = self.h.sim.registers[SP]
            if sp - 64 <= a < sp + 64:
                return                                  # the stack
            self.writes.append([t, a, 'O', isr, v, '%04X' % pw])


def arm(h, addr):
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    r[PC] = addr


def seq_of(ws):
    """the write SEQUENCE without its times: what is written, in order"""
    out = []
    for w in ws:
        if w[2] == 'E':
            out.append([w[1], 'E'])
        elif w[2] in ('A', 'R'):
            out.append([w[1], w[2], w[4]])
        elif w[2] == 'G':
            out.append([w[1], 'G', w[4], w[5]])
        elif w[2] == 'O':
            out.append([w[1], 'O', w[4], w[5]])
        else:
            out.append([w[1], w[2]])
    return out


def delay_ends(events):
    return [e[0] for e in events if e[1] == 'delay_end']


# ------------------------------------------------------------------ direct runs
def one_direct(args):
    contended, anger, phase, poke, state = args
    h, m = new(contended, state=state, anger=anger)
    r = h.sim.registers
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    if poke == 'bits':
        # bit 5 of the colour shadow FLIPPED under every cell the banner's erase re-derives:
        # character rows 0..23, columns 11..20
        for row in range(24):
            for col in range(11, 21):
                m[0xF800 + 32 * row + col] ^= 0x20
    elif isinstance(poke, int):
        m[0xAA57] = poke
    if state == STATE_2P:
        # round1_2p48 was saved inside the sprite blitter, with SP switched into the $FD00 row
        # table ($A437 LD SP,IX) -- sentinels pushed there would overwrite the table the banner
        # walks.  So this world reaches $9037 through its own main loop (interrupts on, its own
        # stack and phase) and the block runs from there, interrupts OFF, to its RET at $8D52.
        to_9037(h)
        tr = Tracer(h, r[T])
        stop = tr.run({0x8D52}, interrupts=False)
        exit_ = 0 if stop == 0x8D52 else None
    else:
        arm(h, 0x9037)
        tr = Tracer(h, r[T])
        tr.run(set(h.SENTINELS), interrupts=False)
        exit_ = h.SENTINELS.index(r[PC])
    cost = r[T] - tr.t0
    ws = [w for w in tr.writes if not w[3]]
    return {'contended': contended, 'anger': anger, 'phase': phase, 'poke': poke, 'state': state, 'cost': cost,
            'exit': exit_, 'events': tr.events, 'writes': ws,
            'end': {'g4': m[0xFEC4], 'g5': m[0xFEC5], 'ptr': m[0x9A04] | (m[0x9A05] << 8),
                    '9077': m[0x9077], '904D': m[0x904D], '90AA': m[0x90AA], '9102': m[0x9102]}}


def tail_of(d):
    """the tail from $90A3: each write's T from it, and where the block ends"""
    t3 = [e[0] for e in d['events'] if e[1] == 'g4:=1'][0]
    return {'open': t3, 'end': d['cost'] - t3,
            'writes': [[w[0] - t3, w[1], w[4]] for w in d['writes'] if w[0] >= t3]}


def phase_direct(jobs=8):
    jobsl = [(False, 0, None, None, STATE), (True, 0, None, None, STATE),
             (False, 1, None, None, STATE), (True, 1, None, None, STATE),
             (False, 0, None, 'bits', STATE),
             (False, 0, None, 2, STATE), (False, 0, None, 3, STATE), (False, 0, None, 5, STATE),
             (False, 0, None, 8, STATE),
             (False, 0, None, None, STATE_2P), (True, 0, None, None, STATE_2P)]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jobsl))) as ex:
        res = list(ex.map(one_direct, jobsl))
    ex_, co, exl, col, bits = res[0], res[1], res[2], res[3], res[4]
    tails = res[5:9]
    x2, c2 = res[9], res[10]
    seq = seq_of(ex_['writes'])
    for d in (co, exl, col, bits):
        s = seq_of(d['writes'])
        base = seq
        if d is bits:                                  # the attribute VALUES are the point there
            s = [x if x[1] != 'A' else x[:2] for x in s]
            base = [x if x[1] != 'A' else x[:2] for x in seq]
        if d is exl or d is col:                       # the latched tail differs from $90A9 on
            t3 = [e[0] for e in d['events'] if e[1] == 'g4:=1'][0]
            n = len([w for w in d['writes'] if w[0] < t3])
            s, base = s[:n], base[:n]
        if s != base:
            raise Fail('the write sequence differs between runs (%s)' % (d['poke'],))
    seq2 = seq_of(x2['writes'])
    if seq_of(c2['writes']) != seq2:
        raise Fail('the 2P sequence differs between its two runs')
    out = {
        'seq': seq,
        'exact': {'t': [w[0] for w in ex_['writes']], 'events': ex_['events'], 'cost': ex_['cost'],
                  'end': ex_['end']},
        'contended': {'t': [w[0] for w in co['writes']], 'events': co['events'], 'cost': co['cost'],
                      'end': co['end']},
        'latched': {'exact': dict(tail_of(exl), cost=exl['cost'], end_state=exl['end']),
                    'contended': dict(tail_of(col), cost=col['cost'])},
        'anger_tail': {'exact': tail_of(ex_), 'contended': tail_of(co)},
        'tails': [dict(tail_of(d), slots=d['poke'], cost=d['cost']) for d in tails],
        'bits': {'t': [w[0] for w in bits['writes']], 'events': bits['events'], 'cost': bits['cost'],
                 'attrs': [w[4] for w in bits['writes'] if w[2] == 'A']},
        'two_player': {'state': STATE_2P, 'seq': seq2,
                       'exact': {'t': [w[0] for w in x2['writes']], 'events': x2['events'], 'cost': x2['cost']},
                       'contended': {'t': [w[0] for w in c2['writes']], 'events': c2['events'],
                                     'cost': c2['cost']}},
    }
    cls = {}
    for w in seq:
        cls[w[1]] = cls.get(w[1], 0) + 1
    print('direct: %d writes %s; exact %d T, contended %d T (+%d); latched %d / %d; bits %d'
          % (len(seq), cls, ex_['cost'], co['cost'], co['cost'] - ex_['cost'], exl['cost'], col['cost'],
             bits['cost']))
    dx, dc = delay_ends(ex_['events']), delay_ends(co['events'])
    print('  delay ends exact     %s' % dx)
    print('  delay ends contended %s' % dc)
    print('  contention at each   %s' % [c - x for c, x in zip(dc, dx)])
    for t in out['tails']:
        print('  tail, ($AA57) = %d: %d writes, ends %d after $90A3' % (t['slots'], len(t['writes']), t['end']))
    print('  latched: ends %d after $90A3; anger (3 slots) %d'
          % (out['latched']['exact']['end'], out['anger_tail']['exact']['end']))
    d2x, d2c = delay_ends(x2['events']), delay_ends(c2['events'])
    print('  2P: %d writes, exact %d T (%+d), contended %d T (%+d); delay ends exact-1P %s; contended-1P %s'
          % (len(seq2), x2['cost'], x2['cost'] - ex_['cost'], c2['cost'], c2['cost'] - co['cost'],
             sorted(set(a - b for a, b in zip(d2x, dx))), sorted(set(a - b for a, b in zip(d2c, dc)))))
    return out


# ------------------------------------------------------------------ phases
def phase_phases(jobs=8):
    jobsl = [(True, 0, ph, None, STATE) for ph in PHASES]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jobsl))) as ex:
        res = list(ex.map(one_direct, jobsl))
    base = one_direct((False, 0, None, None, STATE))
    bev = base['events']
    rows = []
    for d in res:
        if [e[1] for e in d['events']] != [e[1] for e in bev]:
            raise Fail('phase %d: a different event sequence' % d['phase'])
        dr = [e[0] - b[0] for e, b in zip(d['events'], bev)]
        rows.append({'phase': d['phase'], 'cost': d['cost'], 'min_drift': min(dr), 'max_drift': max(dr),
                     'delay_ends': delay_ends(d['events'])})
        print('phase %5d: cost %d (+%d), drift %d..%d'
              % (d['phase'], d['cost'], d['cost'] - base['cost'], min(dr), max(dr)))
    return {'exact_cost': base['cost'], 'rows': rows}


# ------------------------------------------------------------------ natural
def natural(keys=None, keys_in_block=False, stop_after=None, snap_isr=True, rlog=False, mread=False,
            state=STATE, at=0):
    """<state> + ready, interrupts ON, contended.  `keys` go down at $9037's entry and stay
       down (or, with keys_in_block, come up again at the block's RET).  `at` moves the T
       counter at $9037's entry -- a new frame phase for the block, nothing else changed."""
    global RLOG, MREAD
    h, m = new(True, state=state)
    r = h.sim.registers
    to_9037(h)
    r[T] += at
    t0 = r[T]
    for k in (keys or ()):
        press(h.ports, k)
    tr = Tracer(h, t0)
    if rlog:
        RLOG = []
    if mread:
        MREAD = []
    seen = {'ret': False, 'n8D25': 0}

    def until(ct, t):
        if ct == '8D25' and seen['ret']:
            seen['n8D25'] += 1
            # the natural run stops at the next pass's head; a key run goes one pass further,
            # so a pause or a BREAK the next pass would take has had its chance
            return seen['n8D25'] >= (1 if stop_after is None else 2)
        if ct == '8D52' and not seen['ret']:
            seen['ret'] = True
            if keys and keys_in_block:
                h.ports.release_all()
        return False
    try:
        why = tr.run(set(stop_after or ()), limit=6 * 10 ** 6, interrupts=True, until_chain=until,
                     snap_isr=snap_isr)
    finally:
        reads, mreads = RLOG, MREAD
        RLOG = MREAD = None
    return h, m, tr, t0, why, reads, mreads


def frame_of(t, isrs):
    return sum(1 for x in isrs if x[0] <= t)


def natural_record(state=STATE, at=0, full=True):
    h, m, tr, t0, why, reads, mreads = natural(rlog=True, mread=True, state=state, at=at, snap_isr=full)
    isrs = tr.isrs
    ev = tr.events
    tret = [e[0] for e in ev if e[1] == 'ret'][0]
    blk = [x for x in isrs if x[0] < tret]
    bw = [w for w in tr.writes if not w[3] and w[0] <= tret]
    own = set(w[1] for w in bw)
    per = []
    if full:
        for x in blk:
            sp = x[6]
            d = [a for a in x[7] if a not in own]
            per.append({'counters': ['%04X' % a for a in d if a in COUNTERS],
                        'stack': ['%04X' % a for a in d if a not in COUNTERS and sp - 40 <= a < sp],
                        'other': ['%04X' % a for a in d if a not in COUNTERS and not (sp - 40 <= a < sp)]})
    ins = [[t - t0, '%04X' % p, '%04X' % port] for (t, p, port) in (reads or [])]
    in_block = [x for x in ins if x[0] < tret]
    rd = [[t - t0, '%04X' % p, '%04X' % a] for (t, p, a) in (mreads or [])]

    def in_isr(t):
        return any(x[0] <= t < x[2] for x in isrs)
    # a main-loop read of a counter byte while the block is up (the ISR's own reads are not the
    # main loop's, so they are bracketed out by the ISR rows)
    rd_main = [x for x in rd if x[0] < tret and not in_isr(x[0])]
    rd_isr = [x for x in rd if x[0] < tret and in_isr(x[0])]
    out = {'state': state, 'at': at, 't0_phase': t0 % FRAME_T,
           'isrs': [x[:6] for x in isrs],
           'block_isrs': len(blk),
           'seq': seq_of(bw),
           't': [w[0] for w in bw],
           'events': [[e[0], e[1], frame_of(e[0], isrs)] for e in ev],
           'chain': [[c[0], c[1], frame_of(c[0], isrs)] for c in tr.chain],
           'ret': tret, 'ret_frame': frame_of(tret, isrs),
           'ins_in_block': in_block,
           'counter_reads_in_block': rd_main, 'counter_reads_by_isr': len(rd_isr),
           'stop': '%04X' % why if why is not None else None}
    if full:
        out['ramdiff'] = per
    costs = sorted(set(x[2] - x[1] for x in blk))
    loss = sorted(set(x[2] - x[0] for x in blk))
    print('natural %s +%d: $9037 entered %d T into its frame; %d ISRs inside the block, $8D72..RET %s T, the '
          'main loop loses %s; the block RETs at %d (frame %d)' % (state, at, out['t0_phase'], len(blk), costs, loss,
                                                                  tret, out['ret_frame']))
    print('   gates at every block ISR: %s; parities %s' % (sorted(set((x[3], x[4]) for x in blk)),
                                                          ''.join(str(x[5]) for x in blk)))
    ev_f = out['events']
    print('   reopen %s; first $925A %s; INs in block %d; counter reads in block: main loop %s, ISRs %d'
          % ([e for e in ev_f if e[1] == 'g4:=1'], [c for c in out['chain'] if c[1] == '925A'][:1],
             len(in_block), rd_main, len(rd_isr)))
    if full:
        cnt, stk, oth = {}, set(), set()
        for p in per:
            for c in p['counters']:
                cnt[c] = cnt.get(c, 0) + 1
            stk.update(p['stack'])
            oth.update(p['other'])
        print('   ISR RAM diffs (block writes out): counters %s; stack %d bytes %s..%s; other %s'
              % (cnt, len(stk), min(stk) if stk else '-', max(stk) if stk else '-', sorted(oth)))
    return out


def one_natural(args):
    state, at, full = args
    return natural_record(state, at, full)


def phase_natural():
    return natural_record()


def phase_heldout(jobs=8):
    jobsl = [(STATE_2P, 0, False), (STATE, BOUNDARY_AT, False)]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jobsl))) as ex:
        res = list(ex.map(one_natural, jobsl))
    return {'two_player': res[0], 'boundary': res[1]}


# ------------------------------------------------------------------ tailisr
def one_tail(args):
    kind, D = args
    h, m = new(True)
    r = h.sim.registers
    to_9037(h)
    n = ((m[0xAA57] - 2) & 0xFF) or 256
    slots = [0xFD94 + 10 * i for i in range(n)]
    if kind in ('release', 'odd'):
        # bubble 0 holds slot 4's enemy at age $FF; $B657 = 1, so the next even pass's age tick
        # wraps it and $B679 releases the enemy.  Set at $9037's entry: the 42 closed interrupts
        # do not touch a bubble ($FEC5 = 0)
        for k in range(12):
            m[B0 + 10 * k + 7] = 0
        m[E4 + 7] |= 0x08
        m[B0 + 7], m[B0 + 9], m[B0 + 8], m[B0 + 4], m[B0 + 5], m[B0 + 6] = 0x84, 1, 2, 0xFF, 0xA3, 0x44
        m[0xB657] = 1
    tr = Tracer(h, r[T])
    stop = tr.run({0x90A1}, limit=6 * 10 ** 6, interrupts=True)
    if stop != 0x90A1:
        raise Fail('no $90A1')
    if len(tr.isrs) != 42 or any(x[3] or x[4] for x in tr.isrs):
        raise Fail('the block to $90A1 did not run its 42 closed interrupts')
    tgt = E4
    if kind in ('capture', 'escape'):
        live = [s for s in slots if (m[s + 7] & 0x80) and not (m[s + 7] & 0x08)]
        tgt = live[-1]
        for k in range(12):
            m[B0 + 10 * k + 7] = 0
        ex, ey = m[tgt + 5], m[tgt + 6]
        # a travelling bubble one 8-px $BE07 step left of the enemy, moving right
        vals = [0x80, 0xC7, ey, (ex - 8) & 0xFF, 0, (ex - 8) & 0xFF, ey, 0x81, 0, 0]
        if kind == 'escape':
            # a RISEN bubble HOLDING the enemy, one age tick short of the wrap, the toggle primed
            m[tgt + 7] |= 0x08
            vals = [0x80, 0xC7, 0x45, 0x63, 0xFF, 0x63, 0x45, 0x84, (tgt - 0xFD94) // 10, 1]
            m[0xB657] = 1
        for i, v in enumerate(vals):
            m[B0 + i] = v
    if kind == 'odd':
        c = ((m[0x8DBD] | (m[0x8DBE] << 8)) + 1) & 0xFFFF      # FORCED: the 43rd interrupt odd
        m[0x8DBD], m[0x8DBE] = c & 0xFF, c >> 8
    pre = [[m[s + 5], m[s + 6], m[s + 7]] for s in slots]
    bub_pre = [m[B0 + i] for i in range(10)]
    # the next frame's interrupt line D T after $90A3 ($90A1 LD A,1 is 7 T); the tail's code and
    # data are above $8000, so moving T here moves no contention inside it
    F = (r[T] // FRAME_T + 2) * FRAME_T
    r[T] = F - 7 - D
    tr2 = Tracer(h, r[T] + 7)
    seen = {'ret': False}

    def until(ct, t):
        if ct == '8D52':
            seen['ret'] = True
        return ct == '925A' and seen['ret']
    tr2.run(set(), limit=10 ** 6, interrupts=True, until_chain=until)
    isr = tr2.isrs[0][:6] if tr2.isrs else None
    watch = set()
    for s in slots:
        watch.update((s + 5, s + 6, s + 7))
    ws = [[w[0], w[1], 'ISR' if w[3] else 'main', w[4], w[5]] for w in tr2.writes
          if w[2] == 'O' and w[1] in watch]
    ev = [e for e in tr2.events if e[1] in ('g4:=1', 'g5:=1', 'anger_g4:=0', 'anger_walk', 'ret')]
    return {'kind': kind, 'D': D, 'target': tgt, 'slots': slots, 'pre': pre, 'bubble_pre': bub_pre,
            'isr': isr, 'writes': ws, 'events': ev,
            'after': [[m[s + 5], m[s + 6], m[s + 7]] for s in slots],
            'bubble_after': [m[B0 + i] for i in range(10)]}


def phase_tailisr(jobs=8):
    jobsl = [('release', d) for d in TAIL_D] + [('capture', 20), ('escape', 20), ('odd', 27)]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jobsl))) as ex:
        res = list(ex.map(one_tail, jobsl))
    for d in res:
        i = d['slots'].index(d['target'])
        print('tailisr %-8s D %3d: ISR %s; target $%04X pre %s after %s; bubble +7/+8/+9 %s -> %s'
              % (d['kind'], d['D'], d['isr'], d['target'], d['pre'][i], d['after'][i],
                 d['bubble_pre'][7:10], d['bubble_after'][7:10]))
    return res


# ------------------------------------------------------------------ fireclock
def one_fire(args):
    K, pre_frames = args
    h, m = new(True)
    r = h.sim.registers
    th = m[0x745C] | (m[0x745D] << 8)
    HU.ready(m, clock=th + 1 + 50)
    m[0x9049] = 1                                       # held off while the phase moves
    t_end = r[T] + pre_frames * FRAME_T // 3
    why, n = h.run_until(GUARD, limit=10 ** 7, interrupts=True, stride=1,
                         predicate=lambda hh: hh.regs[T] >= t_end)
    if r[PC] in GUARD:
        raise Fail('guard')
    HU.ready(m, clock=th - K)
    m[0x9049] = 0
    why, n = h.run_until({0x9052} | GUARD, limit=10 ** 8, interrupts=True, stride=1)
    if r[PC] in GUARD or why != 'target':
        raise Fail('no fire (%s, PC $%04X)' % (why, r[PC]))
    clock = m[0x8DBD] | (m[0x8DBE] << 8)
    return [K, pre_frames, th, clock - th]


def phase_fireclock(jobs=8):
    jobsl = [(K, p) for K in (1, 2, 5) for p in (0, 1, 2)]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jobsl))) as ex:
        res = list(ex.map(one_fire, jobsl))
    print('fireclock: [K, pre, threshold, fire clock - threshold] %s' % res)
    return res


# ------------------------------------------------------------------ keys
def one_keys(args):
    name, keys, inblk = args
    h, m, tr, t0, why, reads, mreads = natural(keys=keys, keys_in_block=inblk, snap_isr=False,
                                               stop_after=[0x8FFB, 0x8CDC], rlog=True)
    ev = tr.events
    tret = [e[0] for e in ev if e[1] == 'ret'][0]
    ins = [(t - t0, p) for (t, p, port) in (reads or []) if (port & 0xFF) == 0xFE]
    stop_t = tr.h.sim.registers[T] - t0
    return {'case': name, 'stop': ('%04X' % why) if why is not None else None,
            'stop_T': stop_t, 'stop_frame': frame_of(stop_t, tr.isrs), 'ret': tret,
            'ret_frame': frame_of(tret, tr.isrs),
            'chain_after': [[c[0], c[1], frame_of(c[0], tr.isrs)] for c in tr.chain if c[0] >= tret][:16],
            'ins_in_block': sorted(set('%04X' % p for t, p in ins if t < tret)),
            'ins_after': sorted(set('%04X' % p for t, p in ins if t >= tret))}


def phase_keys(jobs=8):
    cases = [('none', [], False), ('SYM from $9037 on', ['SYM'], False),
             ('CAPS+SPACE from $9037 on', ['CAPS', 'SPACE'], False),
             ('SYM inside the block only', ['SYM'], True),
             ('CAPS+SPACE inside the block only', ['CAPS', 'SPACE'], True)]
    with ProcessPoolExecutor(max_workers=min(jobs, len(cases))) as ex:
        res = list(ex.map(one_keys, cases))
    for d in res:
        print('keys %-34s stop %s at %d (frame %d; the block RETs in frame %d); chain after %s; '
              'INs in block %s, after %s'
              % (d['case'], d['stop'], d['stop_T'], d['stop_frame'], d['ret_frame'],
                 [c[1] for c in d['chain_after']], d['ins_in_block'], d['ins_after']))
    return res


def capture(jobs=8):
    return {'meta': {'state': STATE, 'frame_t': FRAME_T, 'isr': '8D72', 'trampoline': 'FFFF,FFF4',
                     'counters': ['%04X' % a for a in COUNTERS]},
            'direct': phase_direct(jobs), 'phases': phase_phases(jobs),
            'natural': phase_natural(), 'heldout': phase_heldout(jobs), 'tailisr': phase_tailisr(jobs),
            'fireclock': phase_fireclock(jobs), 'keys': phase_keys(jobs)}


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else 'capture'
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 8
    if cmd == 'capture':
        out = capture(jobs)
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new_ = json.loads(json.dumps(capture(jobs)))
        bad = [k for k in old if old[k] != new_.get(k)]
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd == 'direct':
        phase_direct(jobs)
    elif cmd == 'phases':
        phase_phases(jobs)
    elif cmd == 'natural':
        phase_natural()
    elif cmd == 'heldout':
        phase_heldout(jobs)
    elif cmd == 'tailisr':
        phase_tailisr(jobs)
    elif cmd == 'fireclock':
        phase_fireclock(jobs)
    elif cmd == 'keys':
        phase_keys(jobs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
