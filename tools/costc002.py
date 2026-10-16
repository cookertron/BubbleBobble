"""M7.87 (measurement) -- THE BURST-SPARKLE PASS'S T ($C002, $A2D5, $A314), RUN BY RUN, UNCONTENDED.

passcost (M7.86) priced $C002 at 14.0% of the main loop's T, 890..4,668 T, with two children, the OR
blit $A2D5 and the pixel restore $A314.  This oracle records every run of $C002 from its one caller
($8D49 CALL $C002) on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T, and
brackets every nested CALL apart by entry PC + return SP (popcost / travelcost): $A2D5 and $A314 are
recorded as runs of their own, and inside them the divide $9F5C (RRA x3 / AND $1F / RET) is bracketed
apart too.  $A2FB (the blit's band, CALLed once and fallen into once) and $A34D (the restore's band,
CALLed twice and fallen into once) are their routines' OWN code, not callees: they are not bracketed.

  T        a $C002 run, $C002 to its return at the caller, with its ISRs bracketed out (below)
  own      T less its nested callees ($A2D5 / $A314 runs, whole)
  path     the walk, one letter per iteration, from the branch outcomes the run took:
             f  $C00E JR z taken (a free slot: AND 7 == 0)
             z  $C031 JR z taken (the new phase is 0: erase, the slot freed)
             e  $C035 JR z taken (the new phase is 2: erase)
             d  $C03B JR c not taken (draw $CA80)      D  $C03B JR c taken (draw $CAA0)
           its length is the iteration count: $C016's LDI decrements BC, so an LDI with C = 0 costs B one
  c        C at entry (the LDI's borrow input: $8D46's CALL $A824 leaves it)
  subs     the nested runs, apart: [addr, T, own, path] -- $A2D5's path is '' (no branch), $A314's the
           outcome of $A34C RET z ('t' taken: Y & 7 == 0, the third band skipped; 'f' fell into it)
  isr      the T of each interrupt accepted inside the run, acceptance to return, bracketed out;
           the recorder is paused inside it (its reads and writes are not the run's)
  seed     every byte the run READS before it writes it, as (address, value), the ROM excepted
  post     every byte the run WRITES, at its final value -- the stack and the ROM excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (TRAPS #281)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only

THE MODEL (`model()` below): own T is a closed function of the path, the constants Zilog sums with
their instruction lists in BLOCKS; every recorded run, natural and forced, is checked against it, the
children by the same rule ($A2D5 = A2D5_OWN, $A314 = A314_HEAD + band(8 - s) + band(8) + tail(s)),
and $9F5C against DIV.  The tallies of runs the model took exactly are in 'model'.

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table.  The rows keep up to KEEP runs of every distinct (path, own T, children).  The
branches no natural run takes are FORCED CALLS (declared in CALLS): the routine called once from a saved
state with the burst table / the record $C05E poked, interrupts off, returning to its natural return
address (never executed).  One is forced by a REGISTER poke, not by data: 'carry' sets the carry flag
as $C03B is reached, because the branch is unreachable by data (game.js BB_SPARK's proof: the new phase
is never 1).  No memory value below $4000 reaches the fixture; $D000..$D2FF is never executed (asserted).

M7.90 adds two surveys, both natural runs only:
  contended  per state, the runs with contention OFF and ON -- [runs, total T] each, the runs an interrupt
             landed in left out (cost931a's) -- for the stretch the main loop's wall clock sees
  c_feca     C at entry against ($FECA), the tally $8EAA left (its LD C,A at $8EBC is C's writer on the
             main path: $931A's unmatched EXX at $931D swaps the banks every pass, so the bank $C002 sees
             is the one $8E3A's tally wrote last pass) -- the borrow reads only C == 0 at the first LIVE
             slot's LDI, so the runs with a live slot are counted by whether (C == 0) == (($FECA) == 0)
  window     round1_48's first WINDOW frames, contention off and on -- [runs, total T, paths] -- the frames
             BB_PASS_T was CALIBRATED on (the timing census, build/timing_fixture.json 'seq': 48 frames).
             The 300-frame mean holds 7 live-sparkle runs near frame 68 the calibration never saw, so the
             share the flat rest gives up is this window's (TRAPS #286: the share AS CALIBRATED)

Usage:  python tools/costc002.py [--jobs N]          (-> build/costc002_fixture.json, N <= 6)
        python tools/costc002.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, F, C as RC, IYh, IYl
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/costc002_fixture.json'
FRAMES = 300
WINDOW = 48       # M7.90: the timing census's frames (BB_PASS_T's calibration), round1_48 from its start
KEEP = 2
ENTRY, CALLER = 0xC002, 0x8D49
A2D5, A314, DIV = 0xA2D5, 0xA314, 0x9F5C
SUBS = (A2D5, A314, DIV)
OWN_CALLS = (0xA2FB, 0xA34D)     # the bands: CALLed inside their own routine, its own code
TABLE, REC = 0x5CE0, 0xC05E
BR = {0xC00E: 'f', 0xC031: 'z', 0xC035: 'e', 0xC03B: 'D'}   # taken -> letter; $C03B not taken -> 'd'

# ---- THE MODEL: Zilog T per instruction, summed per block -------------------------------------------
BLOCKS = {
    'ENTRY': [('LD IY,nn', 14), ('LD HL,nn', 10), ('LD B,n', 7)],
    'EXIT': [('DJNZ (not taken)', 8), ('RET', 10)],
    'DJNZ': [('DJNZ (taken)', 13)],
    'FREE': [('LD A,(HL)', 7), ('AND n', 7), ('JR z (taken)', 12), ('INC HL', 6), ('INC HL', 6), ('JP nn', 10)],
    'LIVE': [('LD A,(HL)', 7), ('AND n', 7), ('JR z (not)', 7), ('LD (nn),HL', 16), ('LD DE,nn', 10),
             ('LDI', 16), ('DEC DE', 6), ('LD A,(HL)', 7), ('INC HL', 6), ('AND n', 7), ('LD (nn),A', 13),
             ('LD A,(DE)', 7), ('AND n', 7), ('LD C,A', 4), ('LD (nn),A', 13), ('LD A,(DE)', 7), ('AND n', 7),
             ('INC A', 4), ('AND n', 7), ('OR C', 4), ('LD (DE),A', 7), ('AND n', 7)],
    'ERASE_Z': [('JR z (taken)', 12)],
    'ERASE_E': [('JR z (not)', 7), ('CP n', 7), ('JR z (taken)', 12)],
    'ERASE_TAIL': [('PUSH HL', 11), ('PUSH BC', 11), ('CALL nn', 17), ('POP BC', 10), ('POP HL', 10), ('JR', 12)],
    'DRAW': [('JR z (not)', 7), ('CP n', 7), ('JR z (not)', 7), ('EXX', 4), ('LD HL,nn', 10), ('JR c (not)', 7),
             ('LD HL,nn', 10), ('LD (nn),HL', 16), ('CALL nn', 17), ('EXX', 4)],
    'DRAW_C': [('JR z (not)', 7), ('CP n', 7), ('JR z (not)', 7), ('EXX', 4), ('LD HL,nn', 10), ('JR c (taken)', 12),
               ('LD (nn),HL', 16), ('CALL nn', 17), ('EXX', 4)],
    'WB': [('LD A,n', 7), ('LD DE,nn', 10), ('LD (DE),A', 7)],
    # $9F5C, bracketed apart wherever it is called
    'DIV': [('RRA', 4), ('RRA', 4), ('RRA', 4), ('AND n', 7), ('RET', 10)],
    # $A2D5 less its two $9F5C runs: the head, CALL $A2FB, the two INC IX, and two bands
    'A2D5_HEAD': [('LD A,(IY+d)', 19), ('CALL nn', 17), ('ADD A,A', 4), ('LD D,n', 7), ('LD E,A', 4),
                  ('LD IX,nn', 14), ('ADD IX,DE', 15), ('LD E,(IY+d)', 19), ('LD D,(IY+d)', 19),
                  ('LD A,(IY+d)', 19), ('CALL nn', 17), ('LD (nn),A', 13), ('CALL nn', 17), ('INC IX', 10),
                  ('INC IX', 10)],
    'A2D5_BAND_HEAD': [('LD B,n', 7), ('LD H,(IX+d)', 19), ('LD A,(IX+d)', 19), ('ADD A,n', 7), ('LD L,A', 4)],
    'A2D5_ROW': [('LD A,(DE)', 7), ('OR (HL)', 7), ('LD (HL),A', 7), ('INC L', 4), ('INC DE', 6), ('LD A,(DE)', 7),
                 ('OR (HL)', 7), ('LD (HL),A', 7), ('INC DE', 6), ('DEC L', 4), ('INC H', 4)],
    'A2D5_BAND_END': [('DJNZ (not taken)', 8), ('RET', 10)],
    # $A314 less its two $9F5C runs
    'A314_HEAD': [('LD A,(IY+d)', 19), ('CALL nn', 17), ('LD (nn),A', 13), ('LD A,(IY+d)', 19), ('LD C,A', 4),
                  ('AND n', 7), ('LD (nn),A', 13), ('LD B,A', 4), ('LD A,n', 7), ('SUB B', 4), ('LD (nn),A', 13),
                  ('LD A,C', 4), ('CALL nn', 17), ('ADD A,A', 4), ('LD E,A', 4), ('LD D,n', 7), ('LD IX,nn', 14),
                  ('ADD IX,DE', 15), ('LD A,B', 4), ('LD B,n', 7), ('CALL nn', 17), ('XOR A', 4), ('LD B,n', 7),
                  ('CALL nn', 17), ('XOR A', 4), ('LD B,n', 7), ('INC B', 4), ('DEC B', 4)],
    'A314_RETZ': [('RET z (taken)', 11)],
    'A314_FALL': [('RET z (not)', 5)],
    'A314_BAND_HEAD': [('ADD A,(IX+d)', 19), ('LD D,A', 4), ('ADD A,n', 7), ('LD H,A', 4), ('LD A,n', 7),
                       ('ADD A,(IX+d)', 19), ('INC IX', 10), ('INC IX', 10), ('LD E,A', 4), ('LD L,A', 4)],
    'A314_ROW': [('LD A,(HL)', 7), ('LD (DE),A', 7), ('INC E', 4), ('INC L', 4), ('LD A,(HL)', 7), ('LD (DE),A', 7),
                 ('DEC E', 4), ('DEC L', 4), ('INC H', 4), ('INC D', 4)],
    'A314_BAND_END': [('DJNZ (not taken)', 8), ('RET', 10)],
}
K = {k: sum(t for _, t in v) for k, v in BLOCKS.items()}


def a2d5_band():
    return K['A2D5_BAND_HEAD'] + 8 * K['A2D5_ROW'] + 7 * K['DJNZ'] + K['A2D5_BAND_END']


def a314_band(n):
    """n rows (n = 0 is 256: DJNZ)"""
    n = n or 256
    return K['A314_BAND_HEAD'] + n * K['A314_ROW'] + (n - 1) * K['DJNZ'] + K['A314_BAND_END']


def model_c002(path):
    own = K['ENTRY'] + K['EXIT'] + K['DJNZ'] * (len(path) - 1)
    for ch in path:
        if ch == 'f':
            own += K['FREE']
        else:
            own += K['LIVE'] + K['WB'] + {'z': K['ERASE_Z'] + K['ERASE_TAIL'], 'e': K['ERASE_E'] + K['ERASE_TAIL'],
                                          'd': K['DRAW'], 'D': K['DRAW_C']}[ch]
    return own


def model_a2d5():
    return K['A2D5_HEAD'] + 2 * a2d5_band()


def model_a314(s):
    """s = Y & 7 (the self-modified $A33D = 8 - s, $A349 = s)"""
    own = K['A314_HEAD'] + a314_band(8 - s) + a314_band(8)
    return own + (K['A314_RETZ'] if s == 0 else K['A314_FALL'] + a314_band(s))


def _tab(slots):
    """the burst table: slots {k: (byte0, byte1)}, every other slot zero (free)"""
    out = []
    for k in range(14):
        b0, b1 = slots.get(k, (0, 0))
        out += [(TABLE + 2 * k, b0), (TABLE + 2 * k + 1, b1)]
    return out


def _rec(x, y, spr=0xCA80):
    return [(REC, spr & 0xFF), (REC + 1, spr >> 8), (REC + 5, x), (REC + 6, y)]


# FORCED CALLS (declared): (name, state, entry, C at entry, pokes, carry forced at $C03B).
CALLS = [
    # one of each iteration kind: old phase 7 (-> 0, $C031), 1 (-> 2, $C035), 3 and 6 (draws)
    ('mix', 'round1_48', ENTRY, 3, _tab({0: (0x47, 0x50), 1: (0x61, 0x60), 2: (0x83, 0x70), 3: (0x26, 0x30)}), False),
    # $C03B JR c taken: unreachable by data, forced by setting the carry flag as $C03B is reached
    ('carry', 'round1_48', ENTRY, 3, _tab({0: (0x43, 0x50)}), True),
    # C = 0 at the first live LDI: the borrow, thirteen iterations
    ('borrow', 'round1_48', ENTRY, 0, _tab({0: (0x43, 0x50)}), False),
    # X = 0 on two live slots after C = 0: the borrow twice, twelve iterations
    ('borrow2', 'round1_48', ENTRY, 0, _tab({0: (0x03, 0x50), 1: (0x03, 0x60)}), False),
    # every slot busy, every kind, Y at the seed's two edges ($10, $AE)
    ('full', 'round1_48', ENTRY, 3, _tab({k: ((0x10 + 0x10 * k) & 0xF8 | (1 + k % 7), 0x10 + 12 * k) for k in range(14)}),
     False),
    # $A314 with Y & 7 = 1..7 (the third band, $A34C RET z not taken) -- unreachable from $C002 (Y AND $F8)
] + [('a314_s%d' % s, 'round1_48', A314, 3, _rec(0x40, 0x50 + s), False) for s in range(1, 8)] + [
    # $A314 and $A2D5 at Y = 0: the $FD00 row table's ROM rows ($01FF), the blit ORing ROM bytes
    ('a314_y0', 'round1_48', A314, 3, _rec(0x40, 0x00), False),
    ('a2d5_y0', 'round1_48', A2D5, 3, _rec(0x40, 0x00), False),
]
RET_OF = {ENTRY: CALLER + 3, A314: 0xC05A, A2D5: 0xC046}


def _iy(r):
    return r[IYh] << 8 | r[IYl]


class Tracker:
    """the frames open inside one root run, nested CALLs by entry PC + return SP, ISRs bracketed out"""

    def __init__(self, h, rm):
        self.h, self.rm = h, rm
        self.r, self.op, self.raw = h.sim.registers, h.sim.opcodes, rm.m
        self.stack, self.excl, self.isr, self.done = [], 0, None, []
        self.force_carry = False

    def open_root(self, entry, caller, c):
        r = self.r
        f = {'addr': entry, 'ret': (caller + 3) & 0xFFFF, 'sp': (r[SP] + 2) & 0xFFFF, 't0': r[T], 'x0': 0,
             'kids': 0, 'path': '', 'subs': [], 'c': c, 'isr': [], 'seed': [], 'iy': _iy(r),
             'feca': self.raw[0xFECA]}
        self.excl = 0
        rm = self.rm
        rm.seen = set(); rm.rec = f['seed']; rm.wr = f['post'] = {}; rm.stk = r[SP]
        self.stack = [f]

    def step(self):
        """one instruction (or one ISR's acceptance); returns the closed root frame or None"""
        r, raw = self.r, self.raw
        p, t, sp = r[PC], r[T], r[SP]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if self.isr is not None:
            if p == self.isr[0] and sp == self.isr[1]:
                d = t - self.isr[2]
                self.excl += d
                self.stack[0]['isr'].append(d)
                self.rm.rec = self.stack[0]['seed']
                self.isr = None
        if self.isr is None:
            while self.stack and p == self.stack[-1]['ret'] and sp == self.stack[-1]['sp']:
                f = self.stack.pop()
                f['T'] = (t - f['t0']) - (self.excl - f['x0'])
                f['own'] = f['T'] - f['kids']
                if self.stack:
                    par = self.stack[-1]
                    par['kids'] += f['T']
                    par['subs'].append(f)
                else:
                    self.rm.rec = None
                    return f
            if self.force_carry and p == 0xC03B:
                r[F] |= 1
        o = raw[p]
        assert o != 0x76, 'HALT inside the run'
        self.op[o]()
        np_, nsp = r[PC], r[SP]
        if self.isr is None and self.stack:
            top = self.stack[-1]
            if top['addr'] == ENTRY and p in BR:
                if np_ != p + 2:
                    top['path'] += BR[p]
                elif p == 0xC03B:
                    top['path'] += 'd'
            elif top['addr'] == A314 and p == 0xA34C:
                top['path'] += 'f' if np_ == p + 1 else 't'
            if o == 0xCD and nsp == (sp - 2) & 0xFFFF and np_ != p + 3 and np_ not in OWN_CALLS:
                assert np_ in SUBS, 'an unexpected callee $%04X from $%04X' % (np_, p)
                self.stack.append({'addr': np_, 'ret': (p + 3) & 0xFFFF, 'sp': sp, 't0': r[T], 'x0': self.excl,
                                   'kids': 0, 'path': '', 'subs': [], 'iy': _iy(r),
                                   's': raw[(_iy(r) + 6) & 0xFFFF] & 7 if np_ == A314 else None})
        if r[IFF] and r[T] % self.h.frame_duration < self.h.int_active:
            b, spb, tt = r[PC], r[SP], r[T]
            if self.h.sim.accept_interrupt(r, self.rm, p):
                if self.stack:
                    assert self.isr is None, 'an interrupt inside the ISR'
                    self.isr = (b, spb, tt)
                    self.rm.rec = None
        return None


def _machine(state, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def call_run(name, state, entry, c, pokes, carry):
    h, rm = _machine(state)
    r, raw = h.sim.registers, rm.m
    for ad, v in pokes:
        raw[ad] = v
    r[IFF] = 0
    r[RC] = c
    if entry != ENTRY:
        r[IYh], r[IYl] = REC >> 8, REC & 0xFF
    back = RET_OF[entry]
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = back & 0xFF, back >> 8
    r[SP] = sp; r[PC] = entry
    tk = Tracker(h, rm)
    tk.force_carry = carry
    tk.open_root(entry, (back - 3) & 0xFFFF, c)
    if entry == A314:
        tk.stack[0]['s'] = raw[REC + 6] & 7
    for _ in range(2000000):
        f = tk.step()
        if f is not None:
            assert r[PC] == back
            return f
    raise AssertionError(name + ': no return')


def run(name, frames=FRAMES, contended=False):
    h, rm = _machine(name, contended)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    runs, prev, tk = [], 0, None
    while r[T] < t_end:
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
        if tk is not None:
            f = tk.step()
            if f is not None:
                runs.append(f); tk = None
            continue
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        assert p != ENTRY, '$C002 entered other than by $8D49 (from $%04X)' % prev
        prev = p
        if raw[p] == 0x76:
            h._fast_halt()
        else:
            op[raw[p]]()
            if p == CALLER and r[PC] == ENTRY:
                # opened at the CALL's landing, BEFORE an interrupt can be accepted on its boundary
                tk = Tracker(h, rm)
                tk.open_root(ENTRY, CALLER, r[RC])
            if r[IFF] and r[T] % fd < ia:
                b, spb, tt = r[PC], r[SP], r[T]
                if h.sim.accept_interrupt(r, rm, p) and tk is not None:
                    tk.isr = (b, spb, tt); rm.rec = None
    return runs


def _sub(f):
    return [f['addr'], f['T'], f['own'], f['path'], [[g['addr'], g['T']] for g in f['subs']]] + \
        ([f['s']] if f['addr'] == A314 else [])


def check(f):
    """the model against one frame and every frame nested in it: (n checked, n exact, the misses)"""
    n, ok, miss = 0, 0, []
    todo = [f]
    while todo:
        g = todo.pop()
        todo += g['subs']
        a = g['addr']
        m = model_c002(g['path']) if a == ENTRY else model_a2d5() if a == A2D5 else \
            model_a314(g['s']) if a == A314 else K['DIV']
        n += 1
        if m == g['own']:
            ok += 1
        else:
            miss.append(['%04X' % a, g['path'], g['own'], m])
    return n, ok, miss


def row(name, f, forced):
    seed = f['seed']
    rom = sorted(a for a, _ in seed if a < 0x4000)
    sd = sorted((a, v) for a, v in seed if a >= 0x4000)
    post = sorted(f['post'].items())
    blind = [a for a, _ in post if rom and a < 0x5800]
    post = [(a, v) for a, v in post if not (rom and a < 0x5800) and a >= 0x4000]
    return {'state': name, 'forced': forced, 'entry': '%04X' % f['addr'], 'T': f['T'], 'own': f['own'],
            'path': f['path'], 'c': f['c'], 'feca': f['feca'], 'isr': f['isr'], 'subs': [_sub(g) for g in f['subs']],
            's': f.get('s'),
            'seed': ''.join('%04x%02x' % (a, v) for a, v in sd),
            'post': ''.join('%04x%02x' % (a, v) for a, v in post),
            'rom': ' '.join('%04x' % a for a in rom), 'blind': ' '.join('%04x' % a for a in blind)}


CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, tag = job
    if tag:
        f = call_run(*CALLS_BY[tag])
        return [(row(tag, f, True), check(f), f)],
    out = []
    for f in run(name):
        out.append((row(name, f, False), check(f), None))
    return out,


def contended_one(job):
    """M7.90: one state's natural runs with contention OFF and ON -- [runs, total T] each, the runs an
    interrupt landed in left out (cost931a's) -- for the stretch the main loop's wall clock sees"""
    st, c = job
    rs = [f for f in run(st, FRAMES, c) if not f['isr']]
    return [len(rs), sum(f['T'] for f in rs)]


def window_one(c):
    """M7.90: round1_48's first WINDOW frames, contention off / on: [runs, total T, {path: n}], the runs an
    interrupt landed in left out"""
    rs = [f for f in run('round1_48', WINDOW, c) if not f['isr']]
    return [len(rs), sum(f['T'] for f in rs), dict(collections.Counter(f['path'] for f in rs))]


def summ(v):
    v = sorted(v)
    return {'n': len(v), 'min': v[0], 'max': v[-1], 'median': v[len(v) >> 1], 'distinct': len(set(v))} if v else None


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    cwork = [(s, c) for s in A.STATES for c in (False, True)]
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, cwork)
        wres = pool.map(window_one, (False, True))
    contended = {s: [cres[2 * i], cres[2 * i + 1]] for i, s in enumerate(A.STATES)}
    cf = collections.Counter()
    rows, per = [], collections.Counter()
    ts, owns, paths, iters, cs, isrs = [], [], collections.Counter(), collections.Counter(), collections.Counter(), []
    kid = collections.defaultdict(list)
    kidpaths = collections.defaultdict(collections.Counter)
    letters = collections.Counter()
    tally = {'natural': [0, 0], 'forced': [0, 0]}
    misses = []
    per_state = {}
    for (s, tag), (rs,) in zip(work, res):
        if not tag:
            per_state[s] = len(rs)
        for x, (n, ok, miss), _ in rs:
            k = 'forced' if tag else 'natural'
            tally[k][0] += n; tally[k][1] += ok
            misses += [[x['state']] + m for m in miss][:4]
            if not tag:
                live = any(ch != 'f' for ch in x['path'])
                if not live:
                    cf['idle'] += 1
                elif (x['c'] == 0) == (x['feca'] == 0):
                    cf['agree'] += 1
                    cf['agree_borrow' if x['c'] == 0 else 'agree_none'] += 1
                else:
                    cf['machine_only' if x['c'] == 0 else 'feca_only'] += 1
                ts.append(x['T']); owns.append(x['own']); paths[x['path']] += 1
                iters[len(x['path'])] += 1; cs[x['c']] += 1; isrs += x['isr']
                letters.update(x['path'])
                for g in x['subs']:
                    kid[g[0]].append(g[2]); kidpaths[g[0]][g[3]] += 1
            key = (tag or '') + ' %s %d %s' % (x['path'], x['own'], json.dumps([g[:4] for g in x['subs']]))
            if per[key] < (1 if tag else KEEP):
                per[key] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'per_state': per_state, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'T': summ(ts), 'own': summ(owns), 'paths': len(paths),
            'path_counts': dict(sorted(paths.items(), key=lambda kv: -kv[1])), 'iterations': dict(iters),
            'c_entry': {str(k): v for k, v in sorted(cs.items())}, 'letters': dict(letters), 'isr': summ(isrs),
            'contended': contended, 'c_feca': dict(cf), 'window': {'frames': WINDOW, 'state': 'round1_48',
                                                                   'off': wres[0], 'on': wres[1]},
            'children': {'%04X' % a: {'own': summ(v), 'paths': dict(kidpaths[a])} for a, v in sorted(kid.items())},
            'blocks': {k: [[m, t] for m, t in v] for k, v in BLOCKS.items()}, 'K': K,
            'model': {'checked_exact': tally, 'misses': misses[:40]},
            'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('runs %d  paths %d  rows %d  T %s  own %s' % (F['runs'], F['paths'], len(F['rows']), F['T'], F['own']))
    print('iterations', F['iterations'], 'c', F['c_entry'], 'letters', F['letters'], 'isr', F['isr'])
    print('children', F['children'])
    print('model', F['model'])
    print('K', K)
    print('c_feca', F['c_feca'])
    w0, w1 = F['window']['off'], F['window']['on']
    print('window %d frames: contended %d runs %d T mean %.3f ; uncontended %d runs %d T mean %.3f ; K %.6f ; paths %s %s' % (
        WINDOW, w1[0], w1[1], w1[1] / w1[0], w0[0], w0[1], w0[1] / w0[0], (w1[1] / w1[0]) / (w0[1] / w0[0]), w0[2], w1[2]))
    c0, c1 = F['contended']['round1_48']
    print('round1_48 contended %d runs %d T mean %.3f ; uncontended %d runs %d T mean %.3f ; K %.6f' % (
        c1[0], c1[1], c1[1] / c1[0], c0[0], c0[1], c0[1] / c0[0], (c1[1] / c1[0]) / (c0[1] / c0[0])))
    for x in F['rows']:
        if x['forced']:
            print('  %-9s %s T %5d own %5d path %-14s subs %s' % (x['state'], x['entry'], x['T'], x['own'], x['path'],
                                                                  [g[:4] + g[5:] for g in x['subs']]))


if __name__ == '__main__':
    main()
