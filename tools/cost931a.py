"""M7.87 (measurement) -- THE ENVIRONMENT KILL'S T ($931A, and its probe $9377), RUN BY RUN, UNCONTENDED.

passcost (M7.86) ranked $931A first of the main loop's callees: 24.2% of the pass's T (no blocks), 621..6,765
T, own 383..2,039 over 53 paths, its child $9377 23..4,213.  This oracle records every run of $931A from its
one caller ($8D55 CALL $931A) on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T,
and brackets every nested CALL apart by entry PC + return SP (popcost's way):

  $931A    clear $93C4 to NOP, walk ($AA57)-2 enemy +7 fields from $FD9B (stride 10, DJNZ: 0 is 256) through
           $9377, set $93C4 to RET, then each player ($FD80 / $FD8A) not already carried (BIT 4,(IX+$5A))
           through $9377; an answer of $28 (paper 5 under the player) reaches the tail $9360, which sets the
           WATER-CARRY bit unless the flood ($FECE) is up or the jump bit (IX+8 bit 1) is set
  $9377    one entity's +7 field: out if not live (bit 7) or bit 3 set, out (INC HL) if Y < $10; else the
           attribute cell (Y>>3)*32 + ($9F5C: X>>3) and cell+$21 tested for paper 5 / bright ink 2, cell+$20
           (DEC L, eight bit) for the ink only; a hit lands on $93C4 -- RET (the player's mode, A = $28 or
           $42) or NOP, falling into $93C5: CALL $8BC2 (the corpse birth), EI, the registers back
  $9F5C    RRA x3 / AND $1F / RET -- a child of $9377, bracketed apart (constant 29, asserted per run)
  $8BC2    the corpse birth (DI; its own children $8C51 / $FE85), bracketed apart: exact in the engine
           already (corpseBirth's return, M7.77 / M7.79)

Every interrupt accepted inside a run is BRACKETED OUT, from its acceptance to the return to the
interrupted PC at the interrupted SP (passcost's way); such a run keeps its T and path, its seed/post are
not kept ('irq').  A HALT inside a run is an error (asserted: none).

  T        the $931A run, entry to RET, the ISRs out (its children IN)
  own      T less every nested child's T
  sig      its path: 'n' = the DJNZ walk's length, then each conditional at $931A's own level, pc + t/f
  kids     [entry, T] of each direct child ($9377 x n+0..2)
  probes   the nested $9377 runs: [ret (the caller's return pc), mode ('R' / 'N', the opcode $93C4 held when
           a hit reached it -- an opcode, so read from raw memory, TRAPS #278; '-' when no hit), own, sig,
           kids]
  seed     every byte the run READS before it writes it (not its own instruction bytes; the operands read
           as STATE -- $FE85's seed $FE86/7, $A430's $A431 -- in, TRAPS #275/#278), the ROM's VALUES never
           (TRAPS #281: their count in 'rom'); post: every byte written, final value, stack and ROM out;
           when 'rom' > 0 the bitmap writes are addresses only ('blind')

THE MODEL (Zilog T, asserted against EVERY run, natural and forced -- 'model' in the fixture):
  $931A own = PRE 75 + WALK 41 n - 5 + MID 64 + the players' arms (see M931A below)
  $9377 own = see M9377 below; $9F5C = 29

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table.  FORCED CALLS (declared, CALLS below) for the branches no natural run takes:
$931A called once from a saved state with pokes, interrupts off at entry, returning to $8D58.
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/cost931a.py [--jobs N]          (-> build/pending/cost931a_fixture.json, N <= 6)
        python tools/cost931a.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, H, L
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/cost931a_fixture.json'
FRAMES = 300
KEEP = 2
ENTRY, CALLER, BACK = 0x931A, 0x8D55, 0x8D58
PROBE, RRA3, BIRTH = 0x9377, 0x9F5C, 0x8BC2
STATE_OPS = {0xA430: (0xA431,), 0xFE85: (0xFE86, 0xFE87)}
CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RST_OPS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1

# ---------------------------------------------------------------- the model (Zilog T)
W = dict(
    # $931A LD BC,nn 10 / EXX 4 / XOR A 4 / LD (nn),A 13 / LD HL,nn 10 / LD DE,nn 10 / LD A,(nn) 13 / SUB n 7 /
    # LD B,A 4
    PRE=75,
    # $932E CALL 17 / ADD HL,DE 11 / DJNZ 13 -- the last DJNZ 8 (-5)
    WALK=41, WALK_END=-5,
    # $9334 LD A,n 7 / LD (nn),A 13 / LD IX,nn 14 / LD HL,nn 10 / BIT 4,(IX+d) 20
    MID=64,
    # $9344 JR nz taken 12 (P1 carried already)
    P1_SKIP=12,
    # $9344 JR nz 7 / CALL $9377 17 / SUB n 7
    P1_ASK=31,
    # $934B JR z taken 12 (paper 5) -> the tail ; 7 -> P2
    P1_HIT=12, P1_MISS=7,
    # $934D LD IX,nn 14 / BIT 4,(IX+d) 20
    P2=34,
    # $9355 RET nz taken 11 (P2 carried already)
    P2_SKIP=11,
    # $9355 RET nz 5 / LD HL,nn 10 / XOR A 4 / CALL $9377 17 / SUB n 7
    P2_ASK=43,
    # $935F RET nz taken 11 ; 5 -> the tail
    P2_MISS=11, P2_HIT=5,
    # $9360 LD A,(nn) 13 / OR A 4
    TAIL=17,
    # $9364 RET nz taken 11 (the flood)
    FLOOD=11,
    # $9364 RET nz 5 / BIT 1,(IX+d) 20
    NOFLOOD=25,
    # $9369 RET nz taken 11 (jumping)
    JUMP=11,
    # $9369 RET nz 5 / SET 4,(IX+d) 23 / LD (IX+d),A 19 / LD (IX+d),A 19 / RET 10
    CARRY=76,
)
P = dict(
    # $9377 BIT 7,(HL) 12 / RET z taken 11
    DEAD=23,
    # BIT 7,(HL) 12 / RET z 5
    LIVE=17,
    # $937A BIT 3,(HL) 12 / RET nz taken 11
    B3=23,
    # BIT 3,(HL) 12 / RET nz 5 / DEC HL 6 / LD A,(HL) 7 / CP n 7
    Y=37,
    # $9381 JR c taken 12 / $9375 INC HL 6 / RET 10
    LOWY=28,
    # $9381 JR c 7 / EXX 4 / AND n 7 / LD L,A 4 / LD H,n 7 / ADD HL,HL 11 / ADD HL,HL 11 / EXX 4 / DEC HL 6 /
    # LD A,(HL) 7 / INC HL 6 / INC HL 6 / EXX 4 / CALL $9F5C 17 / LD E,A 4 / LD D,n 7 / ADD HL,DE 11 /
    # ADD HL,BC 11   ($9F5C's own 29 apart: RRA 4 x3 / AND n 7 / RET 10)
    CELL=134,
    # a test: LD A,(HL) 7 / AND n 7 / CP n 7 / JR z taken 12 (33) | 7 (28)
    TEST_HIT=33, TEST_MISS=28,
    # $93A7 LD DE,nn 10 / ADD HL,DE 11
    NEXT=21,
    # $93B9 DEC L 4
    LEFT=4,
    # $93C1 EXX 4 / XOR A 4 / RET 10
    MISS=18,
    # $93C4 RET 10 (the players' mode)
    RET=10,
    # $93C4 NOP 4 / EXX 4 / PUSH HL 11 / PUSH DE 11 / PUSH BC 11 / EX DE,HL 4 / LD IY,nn 14 / ADD IY,DE 15 /
    # CALL $8BC2 17 / EI 4 / LD BC,nn 10 / EXX 4 / POP BC 10 / POP DE 10 / POP HL 10 / RET 10
    CORPSE=149,
)
RRA3_T = 29
TESTS = (0x939E, 0x93A5, 0x93B0, 0x93B7, 0x93BF)


def M931A(n, d):
    """$931A's own T from its path: n the walk's length, d {pc: 't'/'f'} of its own conditionals"""
    t = W['PRE'] + W['WALK'] * n + W['WALK_END'] + W['MID']
    tail = False
    if d[0x9344] == 't':
        t += W['P1_SKIP']
    else:
        t += W['P1_ASK']
        if d[0x934B] == 't':
            t += W['P1_HIT']; tail = True
        else:
            t += W['P1_MISS']
    if not tail:
        t += W['P2']
        if d[0x9355] == 't':
            return t + W['P2_SKIP']
        t += W['P2_ASK']
        if d[0x935F] == 't':
            return t + W['P2_MISS']
        t += W['P2_HIT']
    t += W['TAIL']
    if d[0x9364] == 't':
        return t + W['FLOOD']
    t += W['NOFLOOD']
    if d[0x9369] == 't':
        return t + W['JUMP']
    return t + W['CARRY']


def M9377(d, mode):
    """$9377's own T from its path ({pc: 't'/'f'}) and the $93C4 opcode a hit met ('R' / 'N')"""
    if d[0x9379] == 't':
        return P['DEAD']
    t = P['LIVE']
    if d[0x937C] == 't':
        return t + P['B3']
    t += P['Y']
    if d[0x9381] == 't':
        return t + P['LOWY']
    t += P['CELL']
    for k, q in enumerate(TESTS):
        if d[q] == 't':
            return t + P['TEST_HIT'] + (P['RET'] if mode == 'R' else P['CORPSE'])
        t += P['TEST_MISS']
        if k == 1:
            t += P['NEXT']
        if k == 3:
            t += P['LEFT']
    return t + P['MISS']


# ---------------------------------------------------------------- forced calls (declared)
SL0 = 0xFD9B          # the first enemy +7 field; +5 X, +6 Y
P1F, P2F = 0xFD87, 0xFD91


def _ent(f7, x, y, base):
    return [(base, f7), (base - 1, y), (base - 2, x)]


def _quiet_enemies(n=1):
    """($AA57) = n + 2, and every walked enemy dead (bit 7 clear)"""
    return [(0xAA57, n + 2)] + [(SL0 + 10 * i, 0) for i in range(n)]


def _cell(x, y):
    return 0x5800 + (y >> 3) * 32 + (x >> 3)


def _players(p1=None, p2=None, c1=0, c2=0, flood=0, j1=0, j2=0):
    """the two players: None = not live; else (x, y) live at that spot; c1/c2 the attribute at its cell;
    +$5A bit 4 clear; the jump bit (IX+8 bit 1) j1/j2; the flood byte"""
    out = [(0xFECE, flood), (0xFDDA, 0x00), (0xFDE4, 0x00), (0xFD88, 2 if j1 else 0), (0xFD92, 2 if j2 else 0)]
    for f, xy, c in ((P1F, p1, c1), (P2F, p2, c2)):
        if xy is None:
            out += [(f, 0)]
        else:
            out += _ent(0x80, xy[0], xy[1], f) + [(_cell(*xy), c), (_cell(*xy) + 0x21, 0), (_cell(*xy) + 0x20, 0)]
    return out


def _enemy_cells(x, y, c0, c1, c2):
    a = _cell(x, y)
    return [(a, c0), (a + 0x21, c1), (a + 0x20, c2)]


# (name, state, pokes) -- filled after the natural survey showed which arms no run reaches
CALLS = [
    # P1 on paper 5, no flood, not jumping: the water-carry SET ($936A)
    ('p1_carry', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60), c1=0x28)),
    # the same with the flood up: $9364 RET nz
    ('p1_flood', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60), c1=0x28, flood=1)),
    # the same, jumping: $9369 RET nz
    ('p1_jump', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60), c1=0x28, j1=1)),
    # P2 on paper 5: its tail ($935F falls through)
    ('p2_carry', 'round1_48', _quiet_enemies() + _players(p2=(0x60, 0x60), c2=0x28)),
    # P1 already carried (BIT 4 set): $9344 taken; P2 carried too: $9355 RET nz
    ('both_carried', 'round1_48', _quiet_enemies() + _players() + [(0xFDDA, 0x10), (0xFDE4, 0x10)]),
    # P1 on bright ink 2 (A = $42): the RET-mode hit that is not paper 5 ($934B falls through)
    ('p1_ink', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60), c1=0x42)),
    # an enemy hit at each of the five tests (the corpse arm, NOP mode), one test each
    ('e_t1_paper', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x60, SL0) + _players() +
        _enemy_cells(0x60, 0x60, 0x28, 0, 0)),
    ('e_t2_ink', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x60, SL0) + _players() +
        _enemy_cells(0x60, 0x60, 0x42, 0, 0)),
    ('e_t3_paper', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x60, SL0) + _players() +
        _enemy_cells(0x60, 0x60, 0, 0x28, 0)),
    ('e_t4_ink', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x60, SL0) + _players() +
        _enemy_cells(0x60, 0x60, 0, 0x42, 0)),
    ('e_t5_ink', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x60, SL0) + _players() +
        _enemy_cells(0x60, 0x60, 0, 0, 0x42)),
    # a player at each of the five tests (RET mode): paper at t3, ink at t4 / t5, all clear (miss)
    ('p1_t3_paper', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60)) + [(_cell(0x60, 0x60) + 0x21, 0x28)]),
    ('p1_t5_ink', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60)) + [(_cell(0x60, 0x60) + 0x20, 0x42)]),
    ('p1_miss', 'round1_48', _quiet_enemies() + _players(p1=(0x60, 0x60))),
    # bit 3 set ($937C RET nz) and Y < $10 ($9381 JR c) on an enemy
    ('e_b3', 'round1_48', _quiet_enemies() + _ent(0x88, 0x60, 0x60, SL0) + _players()),
    ('e_lowy', 'round1_48', _quiet_enemies() + _ent(0x80, 0x60, 0x08, SL0) + _players()),
    # the walk's length: 1 and 30 ($AA57 = 3 / 32), every walked slot dead
    ('walk1', 'round1_48', _quiet_enemies(1) + _players()),
    ('walk30', 'round1_48', _quiet_enemies(30) + _players()),
]
CALLS_BY = {c[0]: c for c in CALLS}


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operands read as STATE enter the seed (popcost's)"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = STATE_OPS.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _machine(state, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


class Tracker:
    """the open $931A run: a stack of frames [entry, sp0, t0, x0, kidT, sig, kids, mode, ret]"""

    def __init__(self):
        self.cur = None; self.stack = []; self.excl = 0; self.isr = None; self.done = []

    def open(self, r, rm, ret):
        sp0 = (r[SP] + 2) & 0xFFFF
        self.cur = {'seed': [], 'irq': 0, 'probes': []}
        rm.seen = set(); rm.rec = self.cur['seed']; rm.wr = self.cur['post'] = {}; rm.stk = sp0 - 2
        self.stack = [[ENTRY, sp0, r[T], self.excl, 0, [], [], '-', ret]]

    def close_frames(self, r, rm):
        sp, t = r[SP], r[T]
        while self.stack and sp >= self.stack[-1][1] and sp - self.stack[-1][1] < 0x100:
            f = self.stack.pop()
            T_ = (t - f[2]) - (self.excl - f[3])
            own = T_ - f[4]
            if self.stack:
                par = self.stack[-1]
                par[4] += T_
                par[6].append((f[0], T_))
                if f[0] == PROBE:
                    assert len(self.stack) == 1, '$9377 nested deeper'
                    self.cur['probes'].append((f[8], f[7], own, f[5], f[6]))
                elif f[0] == RRA3:
                    assert T_ == RRA3_T, '$9F5C ran %d' % T_
            else:
                assert r[PC] == f[8], '$931A returned to $%04X' % r[PC]
                x = self.cur
                x['T'] = T_; x['own'] = own; x['sig'] = f[5]; x['kids'] = f[6]
                rm.rec = None
                self.done.append(x)
                self.cur = None

    def step(self, r, op, raw, rm, h):
        """one instruction (or a HALT) with the ISR bracketing; returns nothing"""
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
            assert self.cur is None or self.isr is not None, 'HALT inside a $931A run'
            h._fast_halt()
            return
        top = self.stack[-1] if (self.cur is not None and self.isr is None) else None
        if top is not None and top[0] == PROBE and p == 0x93C4:
            top[7] = 'R' if o == 0xC9 else ('N' if o == 0x00 else '?%02x' % o)
        op[o]()
        if top is not None:
            np_, nsp = r[PC], r[SP]
            if top[0] in (ENTRY, PROBE) and COND[o]:
                top[5].append((p, 'f' if np_ == B._fall(raw, p) else 't'))
            if nsp == (sp - 2) & 0xFFFF and ((o in CALL_OPS and np_ != (p + 3) & 0xFFFF) or o in RST_OPS):
                ret = (p + (1 if o in RST_OPS else 3)) & 0xFFFF
                if raw[nsp] | raw[(nsp + 1) & 0xFFFF] << 8 == ret:
                    self.stack.append([np_, sp, r[T], self.excl, 0, [], [], '-', ret])
        if r[IFF] and r[T] % h.frame_duration < h.int_active:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                assert self.isr is None, 'an interrupt inside the ISR'
                self.isr = (b, spb, tt)
                if self.cur is not None:
                    self.cur['irq'] += 1
                    rm.rec = None


def run(name, frames=FRAMES, contended=False):
    h, rm = _machine(name, contended)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    tr = Tracker()
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
        if tr.cur is None and tr.isr is None and p == ENTRY:
            sp = r[SP]
            assert raw[sp] | raw[(sp + 1) & 0xFFFF] << 8 == BACK, '$931A entered not from $8D55'
            tr.open(r, rm, BACK)
        tr.step(r, op, raw, rm, h)
    return tr.done


def call_run(name, state, pokes):
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for ad, v in pokes:
        raw[ad] = v
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    tr = Tracker()
    tr.open(r, rm, BACK)
    for _ in range(400000):
        tr.step(r, op, raw, rm, h)
        if tr.isr is None and tr.cur is not None:
            tr.close_frames(r, rm)
        if tr.cur is None:
            break
    else:
        raise AssertionError(name + ': no return')
    return tr.done[0]


def _d(sig):
    d = {}
    for q, c in sig:
        d[q] = c
    return d


def check(x):
    """the model against one run: returns (ok931a, [ok per probe])"""
    n = sum(1 for q, _ in x['sig'] if q == 0x9332)
    ok = M931A(n, _d(x['sig'])) == x['own']
    po = [M9377(_d(s), m) == own for _, m, own, s, kids in x['probes']]
    return ok, po


def _sigs(sig):
    n = sum(1 for q, _ in sig if q == 0x9332)
    return 'n%d ' % n + ' '.join('%04x%s' % (q, c) for q, c in sig if q != 0x9332)


def row(name, x):
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if a < 0x5800] if rom else []
    if rom:
        post = [(a, v) for a, v in post if a >= 0x5800]
    out = {'state': name, 'T': x['T'], 'own': x['own'], 'sig': _sigs(x['sig']), 'irq': x['irq'],
           'kids': [['%04X' % k, t] for k, t in x['kids']],
           'probes': [['%04X' % ret, m, own, ' '.join('%04x%s' % (q, c) for q, c in s),
                       [['%04X' % k, t] for k, t in kids]] for ret, m, own, s, kids in x['probes']]}
    if not x['irq']:
        out.update({'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
                    'post': ''.join('%04x%02x' % (a, v) for a, v in post),
                    'rom': len(rom), 'blind': ' '.join('%04x' % a for a in blind)})
    return out


def one(job):
    name, tag = job
    runs = [call_run(*CALLS_BY[tag])] if tag else run(name)
    out = []
    for x in runs:
        ok, po = check(x)
        out.append((ok, po, row(tag or name, x)))
    return out


WINDOW = 48       # the timing census's frames (BB_PASS_T's calibration), round1_48 from its start


def window_one(c):
    """round1_48's first WINDOW frames, contention off / on: [runs, total T], the runs an interrupt landed
    in left out -- the share the flat rest gives up AS CALIBRATED (TRAPS #286, M7.90's refinement)"""
    rs = [x for x in run('round1_48', WINDOW, c) if not x['irq']]
    return [len(rs), sum(x['T'] for x in rs)]


def contended_one(job):
    """M7.88: one state's natural runs with contention OFF and ON -- [runs, total T] each, the runs an
    interrupt landed in left out -- for the stretch the main loop's wall clock sees"""
    st, c = job
    rs = [x for x in run(st, FRAMES, c) if not x['irq']]
    return [len(rs), sum(x['T'] for x in rs)]


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    cwork = [(s, c) for s in A.STATES for c in (False, True)]
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, cwork)
        wres = pool.map(window_one, (False, True))
    contended = {s: [cres[2 * i], cres[2 * i + 1]] for i, s in enumerate(A.STATES)}
    rows, per = [], collections.Counter()
    n_runs = n_irq = 0
    ts, owns, sigs, psig, pts, pown = [], collections.Counter(), set(), set(), [], collections.Counter()
    bad, pbad, np_ = [], [], 0
    psigs_forced, sigs_forced = set(), set()
    for (s, tag), rs in zip(work, res):
        for ok, po, x in rs:
            if not ok:
                bad.append([x['state'], x['sig'], x['own']])
            for (ret, m, own, sg, kids), k in zip(x['probes'], po):
                if not k:
                    pbad.append([x['state'], ret, m, own, sg])
            if tag:
                sigs_forced.add(x['sig'])
                for pr in x['probes']:
                    psigs_forced.add(pr[1] + ' ' + pr[3])
                rows.append(x)
                continue
            n_runs += 1; n_irq += 1 if x['irq'] else 0
            ts.append(x['T']); owns[x['own']] += 1; sigs.add(x['sig'])
            for ret, m, own, sg, kids in x['probes']:
                np_ += 1; psig.add(m + ' ' + sg); pts.append(sum(t for _, t in kids) + own); pown[own] += 1
            key = x['sig'] + ' %d' % x['own'] + ' ' + ','.join(sorted(set(p[1] + p[3] + str(p[2]) for p in x['probes'])))
            if per[key] < KEEP and not x['irq']:
                per[key] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'W': W, 'P': P, 'rra3': RRA3_T,
            'runs': n_runs, 'irq_runs': n_irq, 'paths': len(sigs), 'T': [min(ts), max(ts)],
            'own': [min(owns), max(owns)], 'own_distinct': len(owns),
            'probe_runs': np_, 'probe_paths': len(psig), 'probe_T': [min(pts), max(pts)],
            'probe_own': [min(pown), max(pown)], 'probe_own_distinct': len(pown),
            'probe_paths_list': sorted(psig), 'paths_list': sorted(sigs),
            'forced_paths_new': sorted(sigs_forced - sigs), 'forced_probe_paths_new': sorted(psigs_forced - psig),
            'contended': contended,
            'window': {'frames': WINDOW, 'state': 'round1_48', 'off': wres[0], 'on': wres[1]},
            'model': {'931A_bad': bad, '9377_bad': pbad, 'checked_931A': n_runs + len(CALLS),
                      'checked_9377': np_ + sum(len(x['probes']) for x in rows if x['state'] in CALLS_BY)},
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
    print('runs %d (irq %d) paths %d T %s own %s/%d | probes %d paths %d T %s own %s/%d | rows %d' % (
        F['runs'], F['irq_runs'], F['paths'], F['T'], F['own'], F['own_distinct'], F['probe_runs'],
        F['probe_paths'], F['probe_T'], F['probe_own'], F['probe_own_distinct'], len(F['rows'])))
    print('model: 931A bad %d of %d, 9377 bad %d of %d' % (len(F['model']['931A_bad']), F['model']['checked_931A'],
                                                         len(F['model']['9377_bad']), F['model']['checked_9377']))
    for b in F['model']['931A_bad'][:10]: print('  BAD931A', b)
    for b in F['model']['9377_bad'][:10]: print('  BAD9377', b)
    print('paths:'); [print('  ', s) for s in F['paths_list']]
    print('probe paths:'); [print('  ', s) for s in F['probe_paths_list']]
    print('forced new:', F['forced_paths_new']); print('forced new probe:', F['forced_probe_paths_new'])
    for x in F['rows']:
        if x['state'] in CALLS_BY:
            print('  %-13s T %5d own %5d %s | %s' % (x['state'], x['T'], x['own'], x['sig'],
                                                   [(p[0], p[1], p[2], p[3]) for p in x['probes'] if p[2] > 23]))


if __name__ == '__main__':
    main()
