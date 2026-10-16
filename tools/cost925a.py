"""M7.87 (measurement) -- THE PLAYER/ENEMY PASS $925A AND ITS SCAN $92BB, RUN BY RUN, UNCONTENDED.

passcost (M7.86) put $925A at 15.0% of the main loop's T (184..2,123 T, its own 153..167, 122 paths,
its child $92BB 31..1,970).  This oracle records every run of $925A from the main loop's `$8D52 CALL
$925A` on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T:

  $925A  XOR A / LD ($92DE),A -- a NOP into $92DE, so $92BB's scan falls through into the second list
         ($92DF: Boris's pseudo-entity, +7 at $9257); P1 ($FD80) scanned if its +7 bit 7 is set
         ($9266 CALL nz $92BB), hit by a carry ($9269 CALL c $927D); P2 ($FD8A) the same ($9274), then
         LD A,$C9 / LD ($92DE),A and `RET nc` -- a carry FALLS INTO $927D with IX = $FD8A.
  $927D  the hit: ($FED0) = 0 -> refused if +$5A bit 4 / bit 3, else +$5A |= $84, +4 := $50; ($FED0) != 0
         -> $9298, the enemy dies: IY = the hit entity's base, DI, CALL $8BC2 (the corpse), A = 1 + +$5A
         bit 0, ($FFED) := $1000, CALL $80FA (the award), EI.
  $92BB  one player against the lists: +$5A bit 2 -> RET nz (the carry untouched); else the box from +5/+6
         and the walk $92E4 over ($AA57) - 2 slots from $FD9B (stride 10, $9312 the Y, $930A the X);
         a hit returns carry; with $92DE a NOP a miss walks ONE more slot at $9257.

  T        the run, $925A to its return to $8D55, LESS the nested callees and any interrupt (below)
  sub      the nested callees' runs, apart: [name, T] -- 'scan1' / 'scan2' the $92BB from $9266 / $9274,
           'birth' the $8BC2 from $92A2 (exact elsewhere: corpsecost), 'award' the $80FA from $92B6
           (exact elsewhere: awardcost, BB_AW)
  bb       for each nested $92BB, its index in `scans` (the scan rows; -1 when the row was not kept)
  isr      the T of each interrupt accepted inside the run, acceptance to its return (bracketed OUT)
  seed     every byte the run READS before it writes it, as (address, value), the stack and the opcode
           fetches excepted; reads inside 'birth' / 'award' are NOT recorded (their own oracles)
  post     every byte the run WRITES, at its final value -- the stack and the two callees' writes excepted
  path     the SOURCE PC of every instruction after which control did not fall through (a taken
           branch, a CALL, a RET, a JP) -- outside the nested callees; a scan's own path is in its row
  carry    the carry flag at $927C (the RET nc) -- recorded because the 9298 arm leaves the award's flag

  scans    the $92BB runs: T (its own, $92E4/$9312/$930A inside it), path (sources, as above), ix,
           smc (the OPCODE byte at $92DE at entry -- TRAPS #278: an opcode fetch is not a recorded read),
           n (($AA57) at entry), hit (carry at its return)

No memory value below $4000 is recorded (TRAPS #281): $925A / $92BB read RAM only, and the callees that
read the ROM ($80FA's glyphs) are outside the recorder; any read below $4000 is asserted absent.
$D000..$D2FF is never executed (asserted).

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; rows keep up to KEEP runs of every distinct (path, T), scan rows SKEEP of every
distinct (path, T).  The branches no natural run takes are FORCED CALLS (declared below, label FORCED):
$925A called once from a saved state with the player / entity / Boris bytes poked, interrupts off,
returning to $8D55.  `model` re-checks the instruction-sum model on the fixture; measure and verify
check it on EVERY run (kept or not) and print the count.

M7.89: 'contended' -- every state's natural runs again with contention OFF and ON, [runs, total T] each
(the run with its nested callees, the runs an interrupt landed in left out): the stretch the main loop's
wall clock sees.  'census' -- the same over round1_48's first CENSUS_FRAMES frames only, the window
BB_PASS_T was calibrated on (build/timing_fixture.json: 24 odd + 24 even frames of round1_48, 11 passes
a light frame): the share of the pass $925A held AS CALIBRATED (BB_PASS_PROV / BB_PASS_K, TRAPS #286).
Over 300 frames the key script kills P1 and $925A's mean falls to ~524; in the census window P1 is alive.

Usage:  python tools/cost925a.py [--jobs N]          (-> build/cost925a_fixture.json, N <= 6)
        python tools/cost925a.py verify [--jobs N]   (re-measure, compare, say MATCH)
        python tools/cost925a.py model               (the model against the fixture's rows)
"""
import sys, json, collections, time
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, F as RF
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/cost925a_fixture.json'
FRAMES = 300
CENSUS, CENSUS_FRAMES = 'round1_48', 48
KEEP = 2
SKEEP = 1
ENTRY, CALLER, BACK = 0x925A, 0x8D52, 0x8D55
SUBS = {0x92BB: {0x9266: ('scan1', 0x9269), 0x9274: ('scan2', 0x9277)},
        0x8BC2: {0x92A2: ('birth', 0x92A5)},
        0x80FA: {0x92B6: ('award', 0x92B9)}}
DEAF = ('birth', 'award')        # the recorder is off inside these

# ---------------------------------------------------------------- the model (Zilog sums)
# $925A, own (927D inline):
M = dict(
    HEAD=51,        # $925A XOR A 4 / LD ($92DE),A 13 / LD IX,nn 14 / BIT 7,(IX+7) 20
    CALL_T=17, CALL_N=10,   # CALL cc taken 17 | not taken 10 ($9266, $9269, $9274)
    MID=34,         # $926C LD IX,nn 14 / BIT 7,(IX+7) 20
    SET=20,         # $9277 LD A,$C9 7 / LD ($92DE),A 13
    RETNC_T=11, RETNC_N=5,  # $927C RET nc
    K_HEAD=17,      # $927D LD A,($FED0) 13 / OR A 4
    K_CARRIED=45,   # JR nz 7 / LD A,(IX+$5A) 19 / BIT 4,A 8 / RET nz taken 11 + K_HEAD = 62
    K_DYING=58,     # JR nz 7 / LD A,(IX+$5A) 19 / BIT 4,A 8 / RET nz 5 / BIT 3,A 8 / RET nz taken 11 + K_HEAD = 75
    K_KILL=116,     # JR nz 7 / LD 19 / BIT 8 / RET nz 5 / BIT 8 / RET nz 5 / SET 2,A 8 / SET 7,A 8 /
                    # LD (IX+$5A),A 19 / LD (IX+4),$50 19 / RET 10 + K_HEAD = 133
    H_IN=81,        # JR nz taken 12 / $9298 EX DE,HL 4 / LD IY,nn 14 / ADD IY,DE 15 / DI 4 / PUSH IX 15 /
                    # CALL $8BC2 17 + K_HEAD = 98
    H_P1=53,        # $92A5 POP IX 14 / LD A,1 7 / BIT 0,(IX+$5A) 20 / JR z taken 12
    H_P2=52,        # ... JR z 7 / INC A 4
    H_OUT=57,       # $92B0 LD HL,nn 10 / LD ($FFED),HL 16 / CALL $80FA 17 / EI 4 / RET 10
)
# $92BB, its own (the walk and the two axis tests inside it):
S = dict(
    OUT=31,         # $92BB BIT 2,(IX+$5A) 20 / RET nz taken 11
    IN=25,          # BIT 2 20 / RET nz 5
    SCAN=129,       # $92C0 LD HL 10 / LD A,(IX+5) 19 / ADD 7 / LD E,A 4 / ADD 7 / LD C,A 4 / LD A,(IX+6) 19 /
                    # ADD 7 / LD D,A 4 / ADD 7 / LD B,A 4 / LD A,($AA57) 13 / SUB 2 7 / CALL $92E4 17
    E_HEAD=27,      # $92E4 EX AF 4 / PUSH HL 11 / BIT 7,(HL) 12
    E_DEAD=12,      # JR z taken 12
    E_FROZEN=31,    # JR z 7 / BIT 3,(HL) 12 / JR nz taken 12
    E_LIVE=26,      # JR z 7 / BIT 3,(HL) 12 / JR nz 7
    AXIS=(57, 76, 71),  # DEC HL 6 / CALL 17 / LD A,(HL) 7 / CP r 4 / RET nc taken 11 / JR nc taken 12 (57) |
                    # RET nc 5 / ADD A,15 7 / CP r 4 / CCF 4 / RET 10, JR nc taken 12 (76) or 7 (71)
    HIT=20,         # $92FA POP HL 10 / RET 10
    HIT_RETC=11,    # list 1's hit: $92DD RET c taken 11
    E_TAIL=70,      # $92FC POP HL 10 / PUSH BC 11 / LD BC 10 / ADD HL,BC 11 / POP BC 10 / EX AF 4 / DEC A 4 / JP nz 10
    END=14,         # $9308 OR A 4 / RET 10
    RETC_N=5,       # $92DD RET c not taken
    SMC_RET=10,     # $92DE RET (one list)
    SMC_NOP=21,     # $92DE NOP 4 / $92DF LD HL,nn 10 / LD A,1 7 (falls into $92E4: list 2)
)


def model_scan(path):
    """$92BB's own T from its path (source PCs); also the outcome counts, for the report"""
    t = [p for p in path]
    if t == [0x92BF]:
        return S['OUT']
    T_ = S['IN'] + S['SCAN']
    i = 0
    assert t[i] == 0x92DA; i += 1

    def walk(i, lst):
        """the slots of one list from $92E4; returns (T, i, hit)"""
        tt = 0
        while True:
            tt += S['E_HEAD']
            miss = True
            if t[i] == 0x92E8:
                tt += S['E_DEAD']; i += 1
            elif t[i] == 0x92EC:
                tt += S['E_FROZEN']; i += 1
            else:
                tt += S['E_LIVE']
                ok = True
                for call, rnc, ret, jr in ((0x92EF, 0x9314, 0x9319, 0x92F2), (0x92F5, 0x930C, 0x9311, 0x92F8)):
                    assert t[i] == call; i += 1
                    if t[i] == rnc:
                        i += 1; assert t[i] == jr; i += 1
                        tt += S['AXIS'][0]; ok = False; break
                    assert t[i] == ret; i += 1
                    if i < len(t) and t[i] == jr:
                        i += 1; tt += S['AXIS'][1]; ok = False; break
                    tt += S['AXIS'][2]
                if ok:
                    assert t[i] == 0x92FB; i += 1
                    tt += S['HIT']
                    return tt, i, True
            tt += S['E_TAIL']
            if i < len(t) and t[i] == 0x9305:
                i += 1; continue
            assert t[i] == 0x9309; i += 1
            tt += S['END']
            return tt, i, False

    w, i, hit = walk(i, 1)
    T_ += w
    if hit:
        assert t[i] == 0x92DD; i += 1
        T_ += S['HIT_RETC']
    else:
        T_ += S['RETC_N']
        if i < len(t) and t[i] == 0x92DE:
            i += 1; T_ += S['SMC_RET']
        else:
            T_ += S['SMC_NOP']
            w, i, hit = walk(i, 2)
            T_ += w
    assert i == len(t), 'scan path not consumed'
    return T_


def model_pass(path):
    """$925A's own T (the nested callees apart) from its path (source PCs)"""
    t = path
    i = 0
    T_ = M['HEAD']

    def kill(i, called):
        tt = M['K_HEAD']
        if t[i] == 0x9281:
            i += 1; tt += M['H_IN']
            assert t[i] == 0x92A2; i += 1
            if t[i] == 0x92AD:
                i += 1; tt += M['H_P1']
            else:
                tt += M['H_P2']
            assert t[i] == 0x92B6; i += 1
            assert t[i] == 0x92BA; i += 1
            tt += M['H_OUT']
        elif t[i] == 0x9288:
            i += 1; tt += M['K_CARRIED']
        elif t[i] == 0x928B:
            i += 1; tt += M['K_DYING']
        else:
            assert t[i] == 0x9297; i += 1; tt += M['K_KILL']
        return tt, i

    if i < len(t) and t[i] == 0x9266:
        i += 1; T_ += M['CALL_T']
    else:
        T_ += M['CALL_N']
    if i < len(t) and t[i] == 0x9269:
        i += 1; T_ += M['CALL_T']
        k, i = kill(i, True); T_ += k
    else:
        T_ += M['CALL_N']
    T_ += M['MID']
    if i < len(t) and t[i] == 0x9274:
        i += 1; T_ += M['CALL_T']
    else:
        T_ += M['CALL_N']
    T_ += M['SET']
    if i < len(t) and t[i] == 0x927C:
        i += 1; T_ += M['RETNC_T']
    else:
        T_ += M['RETNC_N']
        k, i = kill(i, False); T_ += k
    assert i == len(t), 'pass path not consumed'
    return T_


# ---------------------------------------------------------------- FORCED CALLS (declared)
P1, P2 = 0xFD80, 0xFD8A
EN = 0xFD9B                       # the enemy list's first +7


def _pl(b, on=True, f5a=0x00, x=0x60, y=0x60):
    return [(b + 7, 0x80 if on else 0x00), (b + 0x5A, f5a), (b + 5, x), (b + 6, y)]


def _en(k, f7, x=0x60, y=0x60):
    p = EN + 10 * k
    return [(p, f7), (p - 2, x), (p - 1, y)]


def _quiet(n=8):
    """($AA57) = n: n - 2 enemy slots, every one empty; Boris empty; ($FED0) = 0"""
    assert n > 2
    return [(0xAA57, n)] + [(EN + 10 * k, 0x00) for k in range(n - 2)] + \
        [(0x9257, 0x00), (0xFED0, 0x00)]


def _score(base, n):
    """a score field as the four packed-BCD bytes the machine holds, LSB first"""
    return [(base + i, ((n // 10 ** (2 * i + 1)) % 10) << 4 | (n // 10 ** (2 * i)) % 10) for i in range(4)]


def _boris(f7, x=0x60, y=0x60):
    return [(0x9257, f7), (0x9255, x), (0x9256, y)]


CALLS = [
    # the 927D refusals and the kill, on P1 (a live enemy on top of P1); P2 absent
    ('p1_kill', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _en(0, 0x80)),
    ('p1_carried', 'round1_48', _quiet() + _pl(P1, f5a=0x10) + _pl(P2, False) + _en(0, 0x80)),
    ('p1_dying_b3', 'round1_48', _quiet() + _pl(P1, f5a=0x08) + _pl(P2, False) + _en(0, 0x80)),
    # P2 hit: the RET nc falls into 927D
    ('p2_kill', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2) + _en(0, 0x80)),
    ('p2_carried', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2, f5a=0x10) + _en(0, 0x80)),
    ('p2_dying_b3', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2, f5a=0x08) + _en(0, 0x80)),
    # both hit, P1 refused (carry cleared by OR A) and P2 killed
    ('both', 'round1_48', _quiet() + _pl(P1, f5a=0x10) + _pl(P2) + _en(0, 0x80)),
    # the heart arm ($FED0 != 0): the enemy dies, P1 (bit 0 clear) / P2 (bit 0 set) paid
    ('heart_p1', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _en(0, 0x80) + [(0xFED0, 1)]),
    ('heart_p2', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2, f5a=0x01) + _en(0, 0x80) + [(0xFED0, 1)]),
    # the heart arm on P1 with P2 present but dying (BIT 2 / RET nz keeps the carry the award left) and
    # absent (the carry at $927C is whatever $8BC2 / $80FA / EI left) -- the carry is RECORDED
    ('heart_p1_p2dying', 'round1_48', _quiet() + _pl(P1) + _pl(P2, f5a=0x04) + _en(0, 0x80) + [(0xFED0, 1)]),
    # ... and with P1 passing the HIGH score: $80FA's copy arm returns with $816B's flags, not the compare's
    ('heart_p1_high', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _en(0, 0x80) + [(0xFED0, 1)] +
        _score(0xFFE1, 0) + _score(0xFFE5, 5000)),
    ('heart_p1_high_p2dying', 'round1_48', _quiet() + _pl(P1) + _pl(P2, f5a=0x04) + _en(0, 0x80) + [(0xFED0, 1)] +
        _score(0xFFE1, 0) + _score(0xFFE5, 5000)),
    # the scan's dying exit for each player
    ('p1_dying_scan', 'round1_48', _quiet() + _pl(P1, f5a=0x04) + _pl(P2, False)),
    ('both_dying_scan', 'round1_48', _quiet() + _pl(P1, f5a=0x04) + _pl(P2, f5a=0x04)),
    ('none', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2, False)),
    # slot outcomes: dead, frozen (bit 3), Y early reject, Y CCF reject, X early reject, X CCF reject
    ('slots', 'round1_48', _quiet(9) + _pl(P1, x=0x60, y=0x60) + _pl(P2, False) +
        _en(0, 0x00) + _en(1, 0x88) + _en(2, 0x80, y=0x80) + _en(3, 0x80, y=0x40) +
        _en(4, 0x80, x=0x80) + _en(5, 0x80, x=0x40) + _en(6, 0x80)),
    # Boris: miss on each kind, then hit (list 2's hit returns straight to $925A)
    ('boris_hit', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x80)),
    ('boris_frozen', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x88)),
    ('boris_y', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x80, y=0x80)),
    ('boris_y2', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x80, y=0x40)),
    ('boris_x', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x80, x=0x80)),
    ('boris_x2', 'round1_48', _quiet() + _pl(P1) + _pl(P2, False) + _boris(0x80, x=0x40)),
    ('boris_p2_kill', 'round1_48', _quiet() + _pl(P1, False) + _pl(P2) + _boris(0x80)),
    # NOT FORCED: ($AA57) = 2 (SUB 2 -> 0, a 256-slot DO-WHILE) -- the stride-10 walk wraps past $FFFF
    # into the ROM, so its T would depend on ROM bytes; it is a slot COUNT, not a branch, and the model's
    # per-slot sum covers it.
]


# ---------------------------------------------------------------- the tracker
class Run:
    def __init__(self, h, rm, sp, t0):
        self.h, self.rm = h, rm
        self.sp, self.t0, self.x0 = sp, t0, 0
        self.path, self.seed, self.sub, self.isr, self.bb = [], [], [], [], []
        self.open = None          # [name, ret, sp, t0, x0, scanrow or None]
        self.carry = None
        rm.seen = set(); rm.rec = self.seed; rm.wr = self.post = {}; rm.stk = sp

    def recon(self):
        self.rm.rec = None if (self.open is not None and self.open[0] in DEAF) else self.seed


def tracked_step(h, rm, run, excl):
    """one instruction while `run` is open and no interrupt is: brackets, the path, the step"""
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    p, t, sp = r[PC], r[T], r[SP]
    o = run.open
    if o is not None and p == o[1] and sp == o[2]:
        d = (t - o[3]) - (excl - o[4])
        if o[5] is not None:
            o[5]['T'] = d; o[5]['hit'] = r[RF] & 1
            run.bb.append(o[5])
        run.sub.append([o[0], d]); run.open = None; run.recon()
    elif o is None and p in SUBS:
        pv = run.prev
        assert pv in SUBS[p], '$%04X entered from $%04X' % (p, pv)
        name, ret = SUBS[p][pv]
        assert raw[sp] | raw[(sp + 1) & 0xFFFF] << 8 == ret
        sc = None
        if p == 0x92BB:
            sc = {'ix': (0xFD80 if pv == 0x9266 else 0xFD8A), 'smc': raw[0x92DE], 'n': raw[0xAA57], 'path': []}
        run.open = [name, ret, (sp + 2) & 0xFFFF, t, excl, sc]; run.recon()
    if p == 0x927C and run.open is None:
        run.carry = r[RF] & 1
    fall = B._fall(raw, p)
    op[raw[p]]()
    if r[PC] != fall:
        o = run.open
        if o is None:
            run.path.append(p)
        elif o[5] is not None:
            o[5]['path'].append(p)
    run.prev = p


def _machine(state, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def finish(run, t, excl):
    run.rm.rec = None
    assert run.open is None
    run.T = (t - run.t0) - (excl - run.x0) - sum(d for _, d in run.sub)
    return run


def call_run(name, state, pokes):
    h, rm = _machine(state)
    r, raw = h.sim.registers, rm.m
    for a, v in pokes:
        raw[a] = v
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    run = Run(h, rm, sp, r[T]); run.prev = CALLER
    for _ in range(2000000):
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if run.open is None and r[SP] == (sp + 2) & 0xFFFF:
            assert p == BACK, name + ': returned to $%04X' % p
            break
        assert raw[p] != 0x76, 'HALT inside a forced call'
        tracked_step(h, rm, run, 0)
    else:
        raise AssertionError(name + ': no return')
    return finish(run, r[T], 0)


def run_state(name, frames=FRAMES, contended=False):
    h, rm = _machine(name, contended)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    runs, cur, prev, excl, isr = [], None, 0, 0, None
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
        p, t, sp = r[PC], r[T], r[SP]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if isr is not None and p == isr[0] and sp == isr[1]:
            d = t - isr[2]; excl += d
            prev = isr[3]                         # the interrupted instruction, not the ISR's RET
            if cur is not None:
                cur.isr.append(d); cur.recon()
            isr = None
        if isr is None:
            if cur is not None and cur.open is None and sp == (cur.sp + 2) & 0xFFFF:
                assert p == BACK, 'returned to $%04X' % p
                runs.append(finish(cur, t, excl)); cur = None
            if cur is None and p == ENTRY:
                assert prev == CALLER, '$925A entered from $%04X' % prev
                cur = Run(h, rm, sp, t); cur.x0 = excl; cur.prev = prev
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside $925A'
            h._fast_halt()
            prev = p
            continue
        if cur is not None and isr is None:
            tracked_step(h, rm, cur, excl)
        else:
            op[raw[p]]()
        prev = p
        if r[IFF] and r[T] % fd < ia:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                assert isr is None, 'an interrupt inside the ISR'
                isr = (b, spb, tt, p)
                if cur is not None:
                    rm.rec = None
    return runs


def _hex(seq):
    return ''.join('%04x%02x' % (a, v) for a, v in seq)


def rows_of(name, run):
    assert all(a >= 0x4000 for a, _ in run.seed), 'a ROM read in the recorded run'   # TRAPS #281
    scans = [{'state': name, 'T': s['T'], 'ix': s['ix'], 'smc': s['smc'], 'n': s['n'], 'hit': s['hit'],
              'path': ' '.join('%04x' % q for q in s['path'])} for s in run.bb]
    x = {'state': name, 'T': run.T, 'sub': run.sub, 'isr': run.isr, 'carry': run.carry,
         'seed': _hex(sorted(run.seed)), 'post': _hex(sorted(run.post.items())),
         'path': ' '.join('%04x' % q for q in run.path)}
    return x, scans


def _p(s):
    return [int(q, 16) for q in s.split()] if s else []


def check(x, scans):
    """the model against one run: 0 if exact, else 1"""
    bad = 0
    if model_pass(_p(x['path'])) != x['T']:
        bad += 1
    for s in scans:
        if model_scan(_p(s['path'])) != s['T']:
            bad += 1
    return bad


CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, tag = job
    out = []
    if tag:
        rs = [call_run(*CALLS_BY[tag])]
    else:
        rs = run_state(name)
    for run in rs:
        x, sc = rows_of(tag or name, run)
        out.append((x, sc, check(x, sc)))
    return out


def contended_one(job):
    """M7.89: one state's natural runs with contention OFF and ON -- [runs, total T] each (the run's own T
    and its nested callees'), the runs an interrupt landed in left out -- as cost931a's"""
    st, c, fr = job
    rs = [x for x in run_state(st, fr, c) if not x.isr]
    tot = [x.T + sum(d for _, d in x.sub) for x in rs]
    return [len(rs), sum(tot), len(set(tot))]


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    cwork = [(s, c, FRAMES) for s in A.STATES for c in (False, True)] + \
        [(CENSUS, c, CENSUS_FRAMES) for c in (False, True)]
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, cwork)
    contended = {s: [cres[2 * i][:2], cres[2 * i + 1][:2]] for i, s in enumerate(A.STATES)}
    census = {'state': CENSUS, 'frames': CENSUS_FRAMES, 'off': cres[-2][:2], 'on': cres[-1][:2],
              'distinct_T': [cres[-2][2], cres[-1][2]]}
    rows, scans, per, sper = [], [], collections.Counter(), collections.Counter()
    paths, spaths, ts, sts, own = set(), set(), [], [], collections.Counter()
    nat_bad, forced_bad, n_isr, n_scan = 0, 0, 0, 0
    branches = collections.Counter()
    for (s, tag), rs in zip(work, res):
        for x, sc, bad in rs:
            if tag:
                forced_bad += bad
            else:
                nat_bad += bad
                paths.add(x['path']); ts.append(x['T']); n_isr += len(x['isr'])
                for q in _p(x['path']): branches['%04x' % q] += 1
                for y in sc:
                    spaths.add(y['path']); sts.append(y['T']); n_scan += 1
                    for q in _p(y['path']): branches['%04x' % q] += 1
            idx = []
            for y in sc:
                k = (tag or '') + ' ' + y['path'] + ' %d' % y['T']
                if sper[k] < SKEEP:
                    sper[k] += 1; idx.append(len(scans)); scans.append(y)
                else:
                    idx.append(-1)
            key = (tag or '') + ' ' + x['path'] + ' %d' % x['T']
            if per[key] < (1 if tag else KEEP):
                per[key] += 1
                x['bb'] = idx
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'paths': len(paths), 'lo': min(ts), 'hi': max(ts), 'isr_in_runs': n_isr,
            'scan_runs': n_scan, 'scan_paths': len(spaths), 'scan_lo': min(sts), 'scan_hi': max(sts),
            'natural_sources': dict(sorted(branches.items())),
            'contended': contended, 'census': census,
            'model': {'M': M, 'S': S, 'natural_mismatch': nat_bad, 'forced_mismatch': forced_bad},
            'rows': rows, 'scans': scans}


def model_fixture():
    F = json.load(open(FIXTURE, encoding='utf-8'))
    bad = n = 0
    for x in F['rows']:
        sc = [F['scans'][i] for i in x['bb'] if i >= 0]
        bad += check(x, sc); n += 1 + len(sc)
    print('model vs fixture rows: %d checks, %d mismatches' % (n, bad))
    return bad


def main():
    args = sys.argv[1:]
    if 'model' in args:
        sys.exit(1 if model_fixture() else 0)
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    t0 = time.time()
    F = json.loads(json.dumps(measure(jobs)))
    mm = F['model']
    print('runs %d (isr inside %d)  paths %d  T %d..%d | scans %d  paths %d  T %d..%d | model mismatches natural %d forced %d | %.0f s'
          % (F['runs'], F['isr_in_runs'], F['paths'], F['lo'], F['hi'], F['scan_runs'], F['scan_paths'],
             F['scan_lo'], F['scan_hi'], mm['natural_mismatch'], mm['forced_mismatch'], time.time() - t0))
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('natural sources', F['natural_sources'])
    for x in F['rows']:
        if x['state'] in CALLS_BY:
            print('  FORCED %-18s T %4d carry %s sub %s path %s' % (x['state'], x['T'], x['carry'], x['sub'], x['path']))


if __name__ == '__main__':
    main()
