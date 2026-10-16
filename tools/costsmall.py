"""M7.96 (measurement) -- THE MAIN LOOP'S SMALL CALLEES, RUN BY RUN, UNCONTENDED: fourteen routines in one oracle.

passcost (M7.86) left fourteen callees inside the flat BB_PASS_T: $8E2A $9961 $900B $8FE7 $9AEB $93DC $9E50
$A9ED $A824 $915F $948F $7E80 $9037 $A09A.  This oracle records every run of each from its ONE main-loop call
site (CALLSITE below) on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T, and
brackets every nested CALL / RST apart by entry PC + return SP (passcost's way: a frame closes when SP is back
at or above the SP its CALL was made at; the root closes when SP is back at or above its own, on its return
address -- or, flagged 'abn', on the main loop's line $8D09..$8D71: $94C2's discarded returns):

  T        the run, entry (the CALL's landing) to its return, the ISRs and HALT waits out, its children IN
  own      T less every direct child's T
  sig      the root's own decision events, in order, run-length compressed ('pc' + outcome, 'xN' repeats):
             t / f   a conditional (JR cc, JP cc, CALL cc, RET cc, DJNZ) taken / not; an LDIR-class repeat
                     taken (repeats) / not (the last)
             x       the RET that closes the frame (an unconditional RET; a RET cc taken closes as 't')
             rDDDD   a RET (or RET cc taken) that does NOT close the frame: it returns to a PUSHed address
                     DDDD inside the routine ($7E80's PUSH $7F05, $9E50's PUSH $9ED0 / EX (SP),HL)
             jDDDD   a JP (HL) / (IX) / (IY) to DDDD
  kids     [entry, T] of each direct child
  halt     the HALTs the run met: each one, from the HALT to the interrupt it waits for and that ISR to its
           return, is BRACKETED OUT (passcost's way: the port ends the frame there); its own T is 0 here
  irq      the interrupts accepted inside the run, each bracketed out from acceptance to the return to the
           interrupted PC at the interrupted SP; such a run keeps its T and path, not its seed / post
  seed     every byte the run READS before it writes it (its children's reads in; not its instructions' own
           bytes -- EXCEPT the self-modified ones: an operand or OPCODE byte any absolute store in RAM targets
           (SMC below) is read as STATE and recorded, TRAPS #275 / #278); post: every byte written, final
           value, stack and ROM out.  A read below $4000 keeps its ADDRESS only ('rom', TRAPS #281); when there
           is one the bitmap writes are addresses only ('blind')

THE MODEL (Zilog T; asserted against EVERY frame of every run, natural and forced, the root AND every nested
child, by entry): a frame's own T is

      own = S(entry) + sum over its decision events e of E(e)

  S(a)     the straight-line T from a up to (not including) the next decision instruction: every instruction's
           Zilog T summed, JP nn / JR followed, CALL nn / RST 17 / 11 and on at the return address (the callee
           apart), HALT 0 (bracketed out), from the code bytes the routine runs
  E(e)     the decision instruction's Zilog T for its outcome, plus S(where it goes):
             JR cc 12 / 7, JP cc 10 / 10, DJNZ 13 / 8, CALL cc 17 / 10 (then S(pc + 3)), RET cc 11 (closing) /
             5, RET 10, LDIR-class 21 / 16, JP (HL) 4, JP (IX) 8; 'r' adds S(the address returned to)
  The Zilog table (ZT below) is written from the Z80 manual, not read from the simulator; every block's
  instruction list is in the fixture ('blocks': per entry, 'S pc' and 'E pc+outcome' -> [T, the list]).

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table.  FORCED CALLS (declared, CALLS below, labelled): a routine called once from a saved
state with pokes (and, for $8FE7's pause, the keys pressed / released at named points), interrupts off,
returning to its natural return address, for the root's own branches no natural run takes.

  contended  {state: {root: [[n, T] uncontended, [n, T] contended]}}: the natural runs no interrupt landed in
  window_world  round1_48's WORLD_BYTES (the toggles' phases, the gates) at the window's start
  window     round1_48's first WINDOW frames (the timing census, BB_PASS_T's calibration -- TRAPS #286),
             contention off and on, NO KEYS (cost8669's census world) and, apart, ab38cost's keys
             ('window_keys', costc002's): per root {all: [n, T], noirq: [n, T], by_passes: {passes in the
             run's frame: [n, T]}, eleven: [n, T] (entered with ($8DBD) even: the census's 11-pass frames,
             cost8669's split), by_own: {own: n}}, and the frames' pass counts

No value below $4000 is stored; $D000..$D2FF is never executed nor disassembled (asserted).

Usage:  python tools/costsmall.py [--jobs N]          (-> build/costsmall_fixture.json, N <= 4)
        python tools/costsmall.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
import z80dis.z80 as Z
from harness import Harness, T, PC, IFF, SP, A as RA, F as RF
import portconfig as pc
import aa60cost as AA
import ab38cost as B

FIXTURE = 'build/costsmall_fixture.json'
FRAMES = 300
WINDOW = 48
KEEP = 2
MAXJOBS = 4
TOP = 0x8D0C
LOOP_LO, LOOP_HI = 0x8D09, 0x8D72
CALLSITE = {0x8FE7: 0x8D28, 0x900B: 0x8D2B, 0xA9ED: 0x8D2E, 0x9961: 0x8D31, 0x915F: 0x8D34, 0x948F: 0x8D37,
            0x7E80: 0x8D3A, 0x93DC: 0x8D3D, 0x9E50: 0x8D40, 0xA09A: 0x8D43, 0xA824: 0x8D46, 0x9037: 0x8D4F,
            0x9AEB: 0x8D58, 0x8E2A: 0x8D5B}
ROOTS = sorted(CALLSITE)
# M7.96: round1_48's bytes the small callees' once-a-frame toggles, edge operands and gates read, recorded so the
# engine's census world can be the machine's (TRAPS #286): which frames a toggle's work lands in is their phase
WORLD_BYTES = (0x8DBD, 0x8DBE, 0x9E57, 0x9E5D, 0x9AF5, 0xA37C, 0xA09E, 0xA82D, 0xFED3, 0x9DDE, 0x9F64, 0x7E0E)
BY_SITE = {s: e for e, s in CALLSITE.items()}
CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RST_OPS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1
ED_REP = {0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}
GLO, GHI = AA.GLO, AA.GHI


def _guard(a):
    assert not (GLO <= a < GHI), 'THE GUARDED RANGE $%04X' % a


# ---------------------------------------------------------------- the Zilog table (the Z80 manual)
R8 = {'A', 'B', 'C', 'D', 'E', 'H', 'L', 'IXH', 'IXL', 'IYH', 'IYL', 'I', 'R'}
R16 = {'BC', 'DE', 'HL', 'SP', 'AF', 'IX', 'IY'}
ALU = {'ADD', 'ADC', 'SUB', 'SBC', 'AND', 'XOR', 'OR', 'CP'}
ROT = {'RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SLL', 'SRL', 'SL1'}
CCS = {'NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M'}


def _kind(o):
    o = o.strip().upper()
    if o in R8:
        return 'r'
    if o in R16 or o == "AF'":
        return 'rr'
    if o == '(HL)':
        return '(hl)'
    if o in ('(BC)', '(DE)'):
        return '(rr)'
    if o in ('(SP)',):
        return '(sp)'
    if o in ('(C)',):
        return '(c)'
    if o.startswith('(IX') or o.startswith('(IY'):
        return '(ix)' if o not in ('(IX)', '(IY)') or True else '(ix)'
    if o.startswith('('):
        return '(nn)'
    return 'n'


def zilog(text):
    """(T base / not taken, T taken or None) for one instruction from its z80dis text"""
    u = text.upper().replace(', ', ',')
    sp = u.split(None, 1)
    mn = sp[0]
    ops = sp[1].split(',') if len(sp) > 1 else []
    k = [_kind(o) for o in ops]
    idx = any(o.strip() in ('IX', 'IY', 'IXH', 'IXL', 'IYH', 'IYL') for o in ops)
    if mn == 'JP' and ops and ops[0] in ('(HL)', '(IX)', '(IY)'):
        return (4 if ops[0] == '(HL)' else 8), None
    if mn in ('NOP', 'DAA', 'CPL', 'CCF', 'SCF', 'RLCA', 'RRCA', 'RLA', 'RRA', 'DI', 'EI', 'EXX'):
        return 4, None
    if mn == 'HALT':
        return 0, None                      # bracketed out (the wait and its ISR): 0 by declaration
    if mn == 'NEG':
        return 8, None
    if mn == 'EX':
        if ops[0] == '(SP)':
            return (23 if ops[1] in ('IX', 'IY') else 19), None
        return 4, None
    if mn == 'LD':
        a, b = k
        if a == 'r' and b == 'r':
            if ops[0] in ('I', 'R') or ops[1] in ('I', 'R'):
                return 9, None
            return (8 if idx else 4), None
        if a == 'r' and b == 'n':
            return (11 if idx else 7), None
        if (a == 'r' and b in ('(hl)', '(rr)')) or (a in ('(hl)', '(rr)') and b == 'r'):
            return 7, None
        if a == '(hl)' and b == 'n':
            return 10, None
        if (a == 'r' and b == '(ix)') or (a == '(ix)' and b in ('r', 'n')):
            return 19, None
        if a == 'r' and b == '(nn)' or a == '(nn)' and b == 'r':
            return 13, None
        if a == 'rr' and b == 'n':
            return (14 if idx else 10), None
        if a == 'rr' and b == '(nn)' or a == '(nn)' and b == 'rr':
            r = ops[0] if a == 'rr' else ops[1]
            return (16 if r == 'HL' else 20), None
        if a == 'rr' and b == 'rr':           # LD SP,HL / IX
            return (10 if idx else 6), None
    if mn in ('PUSH', 'POP'):
        return (15 if mn == 'PUSH' else 14) if idx else (11 if mn == 'PUSH' else 10), None
    if mn in ALU:
        src = ops[-1]
        ks = _kind(src)
        if len(ops) == 2 and k[0] == 'rr':      # ADD/ADC/SBC HL,rr ; ADD IX,rr
            if mn == 'ADD':
                return (15 if ops[0] in ('IX', 'IY') else 11), None
            return 15, None
        if ks == 'r':
            return (8 if src in ('IXH', 'IXL', 'IYH', 'IYL') else 4), None
        if ks == 'n':
            return 7, None
        if ks == '(hl)':
            return 7, None
        if ks == '(ix)':
            return 19, None
    if mn in ('INC', 'DEC'):
        kk = k[0]
        if kk == 'r':
            return (8 if idx else 4), None
        if kk == 'rr':
            return (10 if idx else 6), None
        if kk == '(hl)':
            return 11, None
        if kk == '(ix)':
            return 23, None
    if mn in ROT or mn in ('BIT', 'SET', 'RES'):
        t = k[-1]
        if t == 'r':
            return 8, None
        if t == '(hl)':
            return (12 if mn == 'BIT' else 15), None
        if t == '(ix)':
            return (20 if mn == 'BIT' else 23), None
    if mn in ('RRD', 'RLD'):
        return 18, None
    if mn in ('LDI', 'LDD', 'CPI', 'CPD', 'INI', 'IND', 'OUTI', 'OUTD'):
        return 16, None
    if mn in ('LDIR', 'LDDR', 'CPIR', 'CPDR', 'INIR', 'INDR', 'OTIR', 'OTDR'):
        return 16, 21
    if mn == 'IM':
        return 8, None
    if mn in ('IN', 'OUT'):
        return (12 if '(C)' in ops else 11), None
    if mn == 'JP':
        return 10, 10
    if mn == 'JR':
        return (7, 12) if len(ops) == 2 else (12, None)
    if mn == 'DJNZ':
        return 8, 13
    if mn == 'CALL':
        return (10, 17) if len(ops) == 2 else (17, None)
    if mn == 'RET':
        return (5, 11) if ops else (10, None)
    if mn in ('RETI', 'RETN'):
        return 14, None
    if mn == 'RST':
        return 11, None
    raise ValueError('no Zilog T for ' + text)


# ---------------------------------------------------------------- the model: S and E from the code bytes
_DEC = {}


def dec(m, a):
    """(length, text) of the instruction at a, cached by its address and bytes (a relative jump's text
    names its absolute target)"""
    _guard(a)
    b = bytes(m[a:a + 4])
    key = (a, b)
    d = _DEC.get(key)
    if d is None:
        x = Z.decode(b, a)
        t = Z.decoded2str(x)
        d = _DEC[key] = (x.len, t)
    return d


def _target(m, a, ln):
    o = m[a]
    if o in (0x18, 0x20, 0x28, 0x30, 0x38, 0x10):
        e = m[a + 1]
        return (a + 2 + (e - 256 if e > 127 else e)) & 0xFFFF
    return m[a + ln - 2] | m[a + ln - 1] << 8


def _is_decision(m, a):
    o = m[a]
    if COND[o] or o == 0xC9 or o == 0xE9:
        return True
    if o in (0xDD, 0xFD) and m[a + 1] == 0xE9:
        return True
    if o == 0xED and (m[a + 1] in ED_REP or m[a + 1] in (0x45, 0x4D, 0x55, 0x5D, 0x65, 0x6D, 0x75, 0x7D)):
        return True
    return False


def _text(m, a, ln, txt):
    """the instruction's text with its address, for the block lists (absolute operands as they are)"""
    return '%04X %s' % (a, txt)


def straight(m, a):
    """S(a): [T, [(text, T)...]] -- from a up to the next decision instruction"""
    t, out, n = 0, [], 0
    while not _is_decision(m, a):
        n += 1
        assert n < 4000, 'S($%04X) runs away' % a
        ln, txt = dec(m, a)
        o = m[a]
        z = zilog(txt)[0]
        t += z; out.append((_text(m, a, ln, txt), z))
        if o == 0xC3:
            a = _target(m, a, 3)
        elif o == 0x18:
            a = _target(m, a, 2)
        elif o == 0xCD:
            a = (a + 3) & 0xFFFF
        else:
            a = (a + ln) & 0xFFFF
    out.append(('%04X (stops: a decision)' % a, 0))     # its bytes are in the cache's cover, its T is not
    return t, out


def edge(m, p, ev):
    """E(pc, outcome): [T, list]"""
    ln, txt = dec(m, p)
    zb, zt = zilog(txt)
    o = m[p]
    c = ev[0]
    if c == 'e':                                # the frame ended (abnormally) before p: less S(p)
        s, l2 = straight(m, p)
        return -s, [('%04X (the frame ends here: less S)' % p, 0)] + [(a, -z) for a, z in l2]
    if c == 'k':                                # a callee returned to DDDD, not to p: S(DDDD) - S(p)
        d = int(ev[1:], 16)
        s0, l0 = straight(m, p)
        s1, l1 = straight(m, d)
        return s1 - s0, [('%04X (a callee came back at $%04X: less S(%04X), plus S(%04X))' % (p, d, p, d), 0)] +             [(a, -z) for a, z in l0] + l1
    if c == 'x':
        return zb, [(_text(m, p, ln, txt) + ' (closes)', zb)]
    if c == 'r':
        d = int(ev[1:], 16)
        z = zt if zt is not None else zb       # RET cc taken 11 / RET 10
        s, l2 = straight(m, d)
        return z + s, [(_text(m, p, ln, txt) + ' (to $%04X)' % d, z)] + l2
    if c == 'j':
        d = int(ev[1:], 16)
        s, l2 = straight(m, d)
        return zb + s, [(_text(m, p, ln, txt), zb)] + l2
    ed = o == 0xED
    if c == 't':
        if ed:
            return zt, [(_text(m, p, ln, txt) + ' (repeats)', zt)]
        if (o & 0xC7) == 0xC0:                      # RET cc taken: closes
            return zt, [(_text(m, p, ln, txt) + ' (taken, closes)', zt)]
        if o in CALL_OPS:
            d = (p + 3) & 0xFFFF
        else:
            d = _target(m, p, ln)
        s, l2 = straight(m, d)
        return zt + s, [(_text(m, p, ln, txt) + ' (taken)', zt)] + l2
    assert c == 'f'
    s, l2 = straight(m, (p + ln) & 0xFFFF)
    return zb + s, [(_text(m, p, ln, txt) + ' (not)', zb)] + l2


class Model:
    """S and E, cached by the code bytes they walked (a self-modified byte re-walks)"""

    def __init__(self):
        self.cache = {}
        self.blocks = collections.defaultdict(dict)      # entry -> {'S pc' | 'E pc ev': [T, list]}

    def _get(self, m, key, fn):
        c = self.cache.get(key)
        if c is not None:
            ok = all(m[a] == v for a, v in c[2])
            if ok:
                return c[0], c[1]
        t, lst = fn()
        cover = []
        for s, _ in lst:
            a = int(s[:4], 16)
            ln = dec(m, a)[0]
            cover += [(a + i, m[a + i]) for i in range(ln)]
        if key[0] == 'E':
            ln = dec(m, key[1])[0]
            cover += [(key[1] + i, m[key[1] + i]) for i in range(ln)]
        self.cache[key] = (t, lst, cover)
        return t, lst

    def S(self, m, entry, owner):
        """S(entry), on the code as it is NOW (called as the frame opens)"""
        t, lst = self._get(m, ('S', entry), lambda: straight(m, entry))
        self._note(owner, 'S %04X' % entry, t, lst)
        return t

    def E(self, m, p, ev, owner):
        """E(p, ev), on the code as it is NOW (called as the decision is taken: the code it walks runs next)"""
        t, lst = self._get(m, ('E', p, ev), lambda: edge(m, p, ev))
        self._note(owner, 'E %04X%s' % (p, ev), t, lst)
        return t

    def _note(self, entry, k, t, lst):
        """a block, once; a self-modified variant with another T under its own key ('k Tn')"""
        b = self.blocks[entry]
        if k not in b:
            b[k] = [t, ['%s %d' % x for x in lst]]
        elif b[k][0] != t and ('%s T%d' % (k, t)) not in b:
            b['%s T%d' % (k, t)] = [t, ['%s %d' % x for x in lst]]


# ---------------------------------------------------------------- the self-modified bytes (read as state)
def smc_set(m):
    """every address an absolute store in RAM targets: LD (nn),A / LD (nn),HL / LD (nn),rr / LD (nn),IX|IY
    (a byte grep: a false hit is harmless, it only records a byte a run reads anyway)"""
    out = set()
    for a in range(0x4000, 0xFFFC):
        if GLO <= a < GHI:
            continue
        o = m[a]
        if o == 0x32:
            out.add(m[a + 1] | m[a + 2] << 8)
        elif o == 0x22:
            n = m[a + 1] | m[a + 2] << 8; out.update((n, (n + 1) & 0xFFFF))
        elif o == 0xED and m[a + 1] in (0x43, 0x53, 0x63, 0x73):
            n = m[a + 2] | m[a + 3] << 8; out.update((n, (n + 1) & 0xFFFF))
        elif o in (0xDD, 0xFD) and m[a + 1] == 0x22:
            n = m[a + 2] | m[a + 3] << 8; out.update((n, (n + 1) & 0xFFFF))
    return frozenset(x for x in out if x >= 0x5B00)


# ---------------------------------------------------------------- the machine and the tracker
def _machine(state, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


class Tracker:
    """the open root run: a stack of frames [entry, sp, t0, x0, kidT, sig, kids, ret]"""

    def __init__(self, h, rm, record=True):
        self.h, self.rm = h, rm
        self.r, self.op, self.raw = h.sim.registers, h.sim.opcodes, rm.m
        self.cur = None; self.stack = []; self.excl = 0; self.isr = None; self.done = []
        self.record = record
        self.smc = smc_set(rm.m) if record else frozenset()
        self.lens = {}
        self.frames_closed = []          # (entry, own, sig) of every nested frame of the open run
        self.hook = None                 # forced calls: hook(tracker, pc) before each instruction
        self.model = None                # a Model: each frame predicted AT ITS CLOSE, on the code it ran

    def open(self, root, ret, frame_idx=0, passes_key=None):
        r, rm = self.r, self.rm
        sp0 = (r[SP] + 2) & 0xFFFF
        self.cur = {'root': root, 'seed': [], 'irq': 0, 'halt': 0, 'nested': [], 'abn': 0, 'frame': frame_idx,
                    'par': rm.m[0x8DBD] & 1}
        if self.record:
            rm.seen = set(); rm.rec = self.cur['seed']; rm.wr = self.cur['post'] = {}; rm.stk = sp0 - 2
        else:
            self.cur['post'] = {}
        self.stack = [[root, sp0, r[T], self.excl, 0, [], [], ret, self._S(root)]]

    def _S(self, a):
        return self.model.S(self.raw, a, a) if self.model is not None else 0

    def _E(self, f, p, ev):
        if self.model is not None:
            f[8] += self.model.E(self.raw, p, ev, f[0])

    def close_frames(self):
        r, rm = self.r, self.rm
        sp, t, p = r[SP], r[T], r[PC]
        while self.stack and sp >= self.stack[-1][1] and (sp - self.stack[-1][1] < 0x100) and \
                (len(self.stack) > 1 or p == self.stack[0][7] or LOOP_LO <= p < LOOP_HI):
            f = self.stack.pop()
            T_ = (t - f[2]) - (self.excl - f[3])
            own = T_ - f[4]
            abn = p != f[7]
            if abn:
                # it came back elsewhere (a POPped return, a JP out): its own T ends before p, and its caller
                # goes on at p, not at the return address
                f[5].append((p, 'e')); self._E(f, p, 'e')
            if self.stack:
                par = self.stack[-1]
                par[4] += T_
                par[6].append((f[0], T_))
                if abn:
                    ev = 'k%04X' % p
                    par[5].append((f[7], ev)); self._E(par, f[7], ev)
                self.cur['nested'].append((f[0], own, tuple(f[5]), f[8] if self.model is not None else None))
            else:
                x = self.cur
                x['abn'] = 1 if abn else 0
                x['pred'] = f[8] if self.model is not None else None
                x['T'] = T_; x['own'] = own; x['sig'] = tuple(f[5]); x['kids'] = f[6]
                rm.rec = None
                self.done.append(x)
                self.cur = None

    def pre(self):
        """before an instruction: an ISR back at its interrupted PC / SP ends its bracket; frames close"""
        r, rm = self.r, self.rm
        p, sp = r[PC], r[SP]
        if self.isr is not None and p == self.isr[0] and sp == self.isr[1]:
            self.excl += r[T] - self.isr[2]
            self.isr = None
            if self.cur is not None and self.record:
                rm.rec = self.cur['seed']
        if self.isr is None and self.cur is not None:
            self.close_frames()

    def step(self):
        r, op, raw, rm, h = self.r, self.op, self.raw, self.rm, self.h
        p, sp = r[PC], r[SP]
        _guard(p)
        self.pre()
        if self.hook is not None:
            self.hook(self, p)
        o = raw[p]
        live = self.cur is not None and self.isr is None
        if live and self.record:
            ln = self.lens.get((p, o))
            if ln is None:
                ln = self.lens[(p, o)] = dec(raw, p)[0]
            for a in range(p, p + ln):
                if a in self.smc and a not in rm.seen:
                    rm.seen.add(a); rm.rec.append((a, raw[a]))      # read as STATE (TRAPS #275 / #278)
        if o == 0x76:
            assert self.isr is None, 'HALT inside the ISR'
            t = r[T]
            fd, ia = h.frame_duration, h.int_active
            tt = t if t % fd < ia else (t // fd + 1) * fd
            h._fast_halt()
            assert r[PC] != (p + 1) & 0xFFFF, 'a HALT the interrupt did not take'
            self.excl += tt - t
            self.isr = ((p + 1) & 0xFFFF, sp, tt)
            if self.cur is not None:
                self.cur['halt'] += 1
                rm.rec = None
            return
        top = self.stack[-1] if live else None
        op[o]()
        if top is not None:
            np_, nsp = r[PC], r[SP]
            ev = None
            if o == 0xC9 or (COND[o] and (o & 0xC7) == 0xC0):
                if o != 0xC9 and np_ == (p + 1) & 0xFFFF and nsp == sp:
                    ev = 'f'
                elif nsp >= top[1] and nsp - top[1] < 0x100:
                    ev = 'x' if o == 0xC9 else 't'
                else:
                    ev = 'r%04X' % np_
            elif COND[o]:
                if o in CALL_OPS:
                    ev = 't' if nsp == (sp - 2) & 0xFFFF else 'f'
                else:
                    ev = 'f' if np_ == (p + dec(raw, p)[0]) & 0xFFFF else 't'
            elif o == 0xED and raw[(p + 1) & 0xFFFF] in ED_REP:
                ev = 't' if np_ == p else 'f'
            elif o == 0xE9 or (o in (0xDD, 0xFD) and raw[(p + 1) & 0xFFFF] == 0xE9):
                ev = 'j%04X' % np_
            if ev is not None:
                top[5].append((p, ev)); self._E(top, p, ev)
            if nsp == (sp - 2) & 0xFFFF and ((o in CALL_OPS and np_ != (p + 3) & 0xFFFF) or o in RST_OPS):
                ret = (p + (1 if o in RST_OPS else 3)) & 0xFFFF
                if raw[nsp] | raw[(nsp + 1) & 0xFFFF] << 8 == ret:
                    self.stack.append([np_, sp, r[T], self.excl, 0, [], [], ret, self._S(np_)])
        if r[IFF] and r[T] % h.frame_duration < h.int_active:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                assert self.isr is None, 'an interrupt inside the ISR'
                self.isr = (b, spb, tt)
                if self.cur is not None:
                    self.cur['irq'] += 1
                    rm.rec = None


def _keys(h, raw, ki):
    h.ports.release_all()
    for kt in (0xB5FD, 0xB605):
        for j, c in enumerate('LRJB'):
            sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
            if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                if sel == 0x1F:
                    h.ports.kempston |= mask
                else:
                    h.ports.press(sel, 0xFF & ~mask)


def run(name, frames=FRAMES, contended=False, keys=True, record=True):
    """the natural runs of every root; returns (runs, {frame index: passes})"""
    h, rm = _machine(name, contended)
    r, raw = h.sim.registers, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t_start = r[T]
    t_end = t_start + frames * fd
    ki, nextk = 0, r[T]
    tr = Tracker(h, rm, record)
    passes = collections.Counter()
    s0 = None
    while r[T] < t_end or tr.cur is not None:
        if r[T] >= nextk:
            if keys:
                _keys(h, raw, ki)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        tr.pre()                                 # a run that returns onto the next call site closes first
        if tr.isr is None and p == TOP and (s0 is None or r[SP] == s0):
            s0 = r[SP]
            passes[r[T] // fd] += 1                # the frame: interrupt to interrupt (T is absolute)
        if s0 is not None and tr.cur is None and tr.isr is None and p in BY_SITE:
            # the CALL itself, then open at its landing BEFORE an interrupt can be accepted on its boundary
            root = BY_SITE[p]
            o = raw[p]
            assert o == 0xCD
            tr.op[o]()
            assert r[PC] == root
            tr.open(root, (p + 3) & 0xFFFF, r[T] // fd)
            if r[IFF] and r[T] % fd < h.int_active:
                b, spb, tt = r[PC], r[SP], r[T]
                if h.sim.accept_interrupt(r, rm, p):
                    tr.isr = (b, spb, tt); tr.cur['irq'] += 1; rm.rec = None
            continue
        if tr.cur is None and s0 is not None:
            assert p not in CALLSITE, 'a root entered other than from its call site ($%04X)' % p
        tr.step()
    return tr.done, dict(passes)


# ---------------------------------------------------------------- forced calls (declared)
def _hook_pause(release_after):
    """$8FE7's pause: SYMBOL SHIFT held at $8FE9's IN; CAPS SHIFT pressed after `release_after` visits of the
    spin's IN at $8FFD (the keys are the forced input, declared)"""
    st = {'n': 0}

    def hook(tr, p):
        h = tr.h
        if p == 0x8FE7:
            h.ports.release_all(); h.ports.press(0x7F, 0xFF & ~0x02)
        elif p == 0x8FFB:
            st['n'] += 1
            h.ports.release_all()
            if st['n'] > release_after:
                h.ports.press(0xFE, 0xFF & ~0x01)
    return hook


def _hooks(*items):
    """declared forced inputs at named PCs, every visit:
         ('key', pc, row, mask)   the key held from that PC on (a half-row select byte, its bit)
         ('reg', pc, index, v)    a register poked (harness indices: A 0, F 1, H 6, L 7, IXh 8, IXl 9)
         ('carry', pc)            the carry flag set
         ('poke', pc, addr, v)    a byte poked as the PC is reached"""
    def hook(tr, p):
        r = tr.r
        for it in items:
            if it[1] != p:
                continue
            k = it[0]
            if k == 'key':
                tr.h.ports.press(it[2], 0xFF & ~it[3])
            elif k == 'reg':
                r[it[2]] = it[3]
            elif k == 'carry':
                r[RF] |= 1
            elif k == 'poke':
                tr.raw[it[2]] = it[3]
    return hook


def _next(a):
    """a value that differs from the byte at a (the edge gates' self-modified compare operands)"""
    return lambda m: (m[a] + 1) & 0xFF


def _copy(a):
    return lambda m: m[a]


# $7E80: twelve element slots (+0 at $FEDF + 10k, +2 at $FEE1 + 10k)
def _slots7e(busy):
    out = []
    for k in range(12):
        out += [(0xFEDF + 10 * k, 0x80 if busy else 0x00), (0xFEE1 + 10 * k, 0)]
    return out


_E7E = [(0x7E0E, 3), (0x8E3B, 0), (0x8DBD, _copy(0x7E9C))]
# $9037's hurry, fired and timed out: the Boris paths ($917C on)
_H = [(0x745C, 0), (0x745D, 0), (0x8DBD, 0x00), (0x8DBE, 0x03), (0x9049, 0), (0x904D, 1), (0x8609, 0x01)]
# $9AEB: the gates open, P1 out, record $5B00 live as type 2 (its kid call clears it and returns: P2 is left to
# the root's own walk), record $5B0A as each case sets it
_G9A = [(0xA37C, _next(0x8DBD)), (0x9AF5, 0), (0x5B07, 0x80), (0x5B08, 2), (0xFD87, 0)]


def _rec9a(typ, f7, x, y, f9=0):
    """record $5B0A: +7, +8 the type, +5 X, +6 Y, +9, +4 the slot's low byte, +0/+1 a sprite pointer"""
    return [(0x5B11, f7), (0x5B12, typ), (0x5B0F, x), (0x5B10, y), (0x5B13, f9), (0x5B0E, 0x9B),
            (0x5B0A, 0x00), (0x5B0B, 0x60)]


# $9E50: the gates open, the first bubble record ($FDEE) idle, the second ($FDF8) live
_G9E = [(0x9E57, _next(0x8DBD)), (0x9E5D, 0), (0x9F64, 0), (0xFDF5, 0x00), (0xFDFF, 0x80)]
# $A09A: the edge gate open
_GA0 = [(0xA09E, _next(0x8DBD))]
# $A9ED: the boss round's gates open, the tick due; $A969's answer forced (carry), IX = P1 at $AA30, HL = slot
# 0's +7 at $927D (IY = slot 0 for the corpse birth)
_GA9 = [(0xAA00, _next(0x8DBD)), (0xAA06, 0x1F)]
_HA9 = [('carry', 0xAA2F), ('reg', 0xAA30, 8, 0xFD), ('reg', 0xAA30, 9, 0x80),
        ('reg', 0x927D, 6, 0xFD), ('reg', 0x927D, 7, 0x9B)]
_G99 = [(0xFED3, 1)]

# (label, root, state, pokes, hook, iff) -- the root's own branches no natural run takes, found by the survey.
# A poke's value may be a function of the state's memory (the gate operands).  iff 1: the run is entered with
# interrupts ON (a HALT path: the main loop's EI holds there).  Every forced call starts just past a frame's
# interrupt window (T aligned), so a run shorter than a frame meets no interrupt.
CALLS = [
    # $7E80: every slot busy ($7EBF DJNZ falls through, RET); a free slot that is busy after the HALT ($7EC6
    # RET nz taken: the fill is poked at $7EC4, standing for the interrupt's work)
    ('7e80_all_busy', 0x7E80, 'round1_48', _E7E + _slots7e(True), None, 0),
    ('7e80_halt_filled', 0x7E80, 'round1_48', _E7E + _slots7e(False), _hooks(('poke', 0x7EC4, 0xFEDF, 0x80)), 1),
    # $8E2A: no player in play ($8E33 RET m falls through: the game-over trigger)
    ('8e2a_none', 0x8E2A, 'round1_48', [(0xFD87, 0), (0xFD91, 0)], None, 0),
    # $8FE7: SYMBOL SHIFT down (the pause), CAPS SHIFT after 0 / 3 spins
    ('8fe7_pause0', 0x8FE7, 'round1_48', [], _hook_pause(0), 0),
    ('8fe7_pause3', 0x8FE7, 'round1_48', [], _hook_pause(3), 0),
    # $900B: ($FED0) set (the LDIR of $64s over $A891..); ($FED2) = 1 with the delays all zero (DJNZ 7, the CALL
    # $8C28); with one non-zero ($902D RET nz)
    ('900b_fed0', 0x900B, 'round1_48', [(0xFED0, 1), (0xFED2, 0)], None, 0),
    ('900b_fed2_zero', 0x900B, 'round1_48', [(0xFED0, 0), (0xFED2, 1)] + [(0xA891 + i, 0) for i in range(8)], None, 0),
    ('900b_fed2_busy', 0x900B, 'round1_48', [(0xFED0, 0), (0xFED2, 1)] + [(0xA891 + i, 0) for i in range(8)] +
     [(0xA894, 5)], None, 0),
    # $9037 past the hurry's fire: Boris's first move with the RLC carrying ($91B2 CALL c); his counter at 15
    # ($91EB falls through); the X chase both ways ($9225 / $923F / $9246 -- the HALT at $91D4: interrupts on)
    ('9037_rlc', 0x9037, 'round1_48', _H + [(0x918B, 0), (0x9194, 0xFF), (0x919C, 1), (0x9254, 0x80)], None, 0),
    ('9037_count15', 0x9037, 'round1_48', _H + [(0x918B, 1), (0x91E4, 0x0F)], None, 0),
    ('9037_chase_right', 0x9037, 'round1_48', _H + [(0x918B, 1), (0x91E4, 0), (0x91BC, 1), (0xFD8F, 0x80),
                                                   (0x9255, 0x40)], None, 1),
    ('9037_chase_near', 0x9037, 'round1_48', _H + [(0x918B, 1), (0x91E4, 0), (0x91BC, 1), (0xFD8F, 0x40),
                                                  (0x9255, 0x44)], None, 1),
    # $93DC: ($FFF9) = 3 with both bubble records busy / the second free; 4 with ($9F64) busy; 2 with ($A15A) set,
    # with the flood up, and with the column walk meeting two paper-bit rows then a clear one / all 22
    ('93dc_3_busy', 0x93DC, 'round1_48', [(0xFFF9, 3), (0xFDF5, 0x80), (0xFDFF, 0x80)], None, 0),
    ('93dc_3_second', 0x93DC, 'round1_48', [(0xFFF9, 3), (0xFDF5, 0x80), (0xFDFF, 0x00)], None, 0),
    ('93dc_4_busy', 0x93DC, 'round1_48', [(0xFFF9, 4), (0x9F64, 1)], None, 0),
    ('93dc_2_a15a', 0x93DC, 'round1_48', [(0xFFF9, 2), (0xA15A, 1)], None, 0),
    ('93dc_2_flood', 0x93DC, 'round1_48', [(0xFFF9, 2), (0xA15A, 0), (0xFECE, 1)], None, 0),
    ('93dc_2_walk2', 0x93DC, 'round1_48', [(0xFFF9, 2), (0xA15A, 0), (0xFECE, 0), (0xFFF7, 0x58), (0xFFF8, 0xF7)] +
     [(0xF80C + 32 * k, 0x20 if k < 2 else 0) for k in range(22)], None, 0),
    ('93dc_2_walk22', 0x93DC, 'round1_48', [(0xFFF9, 2), (0xA15A, 0), (0xFECE, 0), (0xFFF7, 0x58), (0xFFF8, 0xF7)] +
     [(0xF80C + 32 * k, 0x20) for k in range(22)], None, 0),
    # $948F: the extend flag up, neither player's letters complete ($94C2 RET nz twice); ($FECB) = 3 ($94AF JR z),
    # P2's letters 1 and 3 held ($959A CALL c)
    ('948f_fecb3', 0x948F, 'round1_48', [(0xFED5, 1), (0xFECB, 3), (0xFDE3, 0x05), (0xFDED, 0x0A)], None, 0),
    # $9961: no credit / ($FED3) negative; key 1 with P1 in / out (the join: $7FC0 at the root); key 2 likewise
    ('9961_none', 0x9961, 'round1_48', [(0xFED3, 0)], None, 0),
    ('9961_neg', 0x9961, 'round1_48', [(0xFED3, 0x80)], None, 0),
    ('9961_key1_in', 0x9961, 'round1_48', _G99 + [(0xFD87, 0x80)], _hooks(('key', 0x9961, 0xF7, 0x01)), 0),
    ('9961_key1_join', 0x9961, 'round1_48', _G99 + [(0xFD87, 0x00)], _hooks(('key', 0x9961, 0xF7, 0x01)), 0),
    ('9961_key2_in', 0x9961, 'round1_48', _G99 + [(0xFD91, 0x80)], _hooks(('key', 0x9961, 0xF7, 0x02)), 0),
    ('9961_key2_join', 0x9961, 'round1_48', _G99 + [(0xFD91, 0x00)], _hooks(('key', 0x9961, 0xF7, 0x02)), 0),
    # $9AEB, record $5B0A idle, P2 in: its +$5A bit 2 ($9B27 RET nz); the RNG's draw made 1 at $9B2B (slot 0), the
    # behaviour byte 1 ($9B43 JR z) with the slot's delay set ($9B4C RET nz) / 5 ($9B47 falls) with the slot
    # lined up on P2's row ($9B4C falls: the record is filled)
    ('9aeb_p2_bit2', 0x9AEB, 'round1_48', _G9A + [(0x5B11, 0), (0xFD91, 0x80), (0xFDE4, 0x04)], None, 0),
    ('9aeb_p2_type1_delay', 0x9AEB, 'round1_48', _G9A + [(0x5B11, 0), (0xFD91, 0x80), (0xFDE4, 0), (0xAA57, 5),
                                                         (0xB562, 1), (0xA891, 9)],
     _hooks(('reg', 0x9B2B, 0, 1)), 0),
    ('9aeb_p2_type5_fill', 0x9AEB, 'round1_48', _G9A + [(0x5B11, 0), (0xFD91, 0x80), (0xFDE4, 0), (0xAA57, 5),
                                                        (0xB562, 5), (0xA891, 0), (0xFD9B, 0x80), (0xFD9D, 0),
                                                        (0xFD9A, 0x60), (0xFD90, 0x60)],
     _hooks(('reg', 0x9B2B, 0, 1)), 0),
    # record $5B0A live: type 2 ($9BDC falls: cleared); type 6 at the left / right edge, on a clear cell, on a
    # paper cell over a paper / clear one; type 5 on a paper cell with bit 2 set / clear, on a clear cell with
    # +9 = its column / not; type 1 on a clear cell over a paper one, and at the left edge
    ('9aeb_t2', 0x9AEB, 'round1_48', _G9A + _rec9a(2, 0x80, 0x60, 0x60), None, 0),
    ('9aeb_t6_left', 0x9AEB, 'round1_48', _G9A + _rec9a(6, 0x80, 0x08, 0x60), None, 0),
    ('9aeb_t6_right', 0x9AEB, 'round1_48', _G9A + _rec9a(6, 0x81, 0xF0, 0x60), None, 0),
    ('9aeb_t6_clear', 0x9AEB, 'round1_48', _G9A + _rec9a(6, 0x80, 0x60, 0x60) + [(0xF98B, 0), (0xF9AB, 0)], None, 0),
    ('9aeb_t6_paper_paper', 0x9AEB, 'round1_48', _G9A + _rec9a(6, 0x80, 0x60, 0x60) + [(0xF98B, 0x20), (0xF9AB, 0x20)],
     None, 0),
    ('9aeb_t6_paper_clear', 0x9AEB, 'round1_48', _G9A + _rec9a(6, 0x80, 0x60, 0x60) + [(0xF98B, 0x20), (0xF9AB, 0)],
     None, 0),
    ('9aeb_t5_paper_b2', 0x9AEB, 'round1_48', _G9A + _rec9a(5, 0x84, 0x60, 0x60) + [(0xF98B, 0x20)], None, 0),
    ('9aeb_t5_paper', 0x9AEB, 'round1_48', _G9A + _rec9a(5, 0x80, 0x60, 0x60) + [(0xF98B, 0x20)], None, 0),
    ('9aeb_t5_clear_col', 0x9AEB, 'round1_48', _G9A + _rec9a(5, 0x84, 0x60, 0x60, 0x58) + [(0xF98B, 0)], None, 0),
    ('9aeb_t5_clear_other', 0x9AEB, 'round1_48', _G9A + _rec9a(5, 0x84, 0x60, 0x60, 0x00) + [(0xF98B, 0)], None, 0),
    ('9aeb_t1_clear_paper', 0x9AEB, 'round1_48', _G9A + _rec9a(1, 0x80, 0x60, 0x60) + [(0xF98B, 0), (0xF9AB, 0x20)],
     None, 0),
    ('9aeb_t1_left', 0x9AEB, 'round1_48', _G9A + _rec9a(1, 0x80, 0x08, 0x60) + [(0xF980, 0), (0xF9A0, 0)], None, 0),
    # $9E50 (element 3 round): the second bubble's scan over a dead slot, a far row, a far column and a hit (the
    # corpse birth: $9EFE CALL nc); the bubble at the left / right edge
    ('9e50_scan_hit', 0x9E50, 'round1_48', _G9E + [(0x8609, 0x01), (0x7E0E, 3), (0xFDFD, 0x60), (0xFDFE, 0x60),
                                                  (0xAA57, 6), (0xFD9B, 0x00),
                                                  (0xFDA5, 0x80), (0xFDA4, 0x20), (0xFDA3, 0x60),
                                                  (0xFDAF, 0x80), (0xFDAE, 0x60), (0xFDAD, 0xC0),
                                                  (0xFDB9, 0x80), (0xFDB8, 0x60), (0xFDB7, 0x60)], None, 0),
    ('9e50_left', 0x9E50, 'round1_48', _G9E + [(0x8609, 0x01), (0x7E0E, 3), (0xFDFD, 0x08), (0xFDFE, 0x60),
                                              (0xAA57, 3), (0xFD9B, 0)], None, 0),
    ('9e50_right', 0x9E50, 'round1_48', _G9E + [(0x8609, 0x01), (0x7E0E, 3), (0xFDFD, 0xF0), (0xFDFE, 0x60),
                                               (0xAA57, 3), (0xFD9B, 0)], None, 0),
    # $9E50 in the boss round: the bubble's column / row against the boss's ($A8DB / $A839), each test's arms
    ('9e50_boss_c0_r1', 0x9E50, 'boss', _G9E + [(0x8609, 0x50), (0xFDFD, 0x60), (0xFDFE, 0x60), (0xA8DB, 0x0C),
                                               (0xA839, 0x0D)], None, 0),
    ('9e50_boss_c3_r2', 0x9E50, 'boss', _G9E + [(0x8609, 0x50), (0xFDFD, 0x60), (0xFDFE, 0x60), (0xA8DB, 0x0F),
                                               (0xA839, 0x0E)], None, 0),
    ('9e50_boss_c0_r3', 0x9E50, 'boss', _G9E + [(0x8609, 0x50), (0xFDFD, 0x60), (0xFDFE, 0x60), (0xA8DB, 0x0C),
                                               (0xA839, 0x0F)], None, 0),
    ('9e50_boss_c0_r4', 0x9E50, 'boss', _G9E + [(0x8609, 0x50), (0xFDFD, 0x60), (0xFDFE, 0x60), (0xA8DB, 0x0C),
                                               (0xA839, 0x10)], None, 0),
    ('9e50_boss_c9', 0x9E50, 'boss', _G9E + [(0x8609, 0x50), (0xFDFD, 0x60), (0xFDFE, 0x60), (0xA8DB, 0x15),
                                            (0xA839, 0x0D)], None, 0),
    # $9E50 (element 4 round, the lightning at $9F63): its cell on paper ($9F82 JP nz), at the floor ($A014)
    ('9e50_bolt_paper', 0x9E50, 'round1_48', [(0x9E57, _next(0x8DBD)), (0x9E5D, 0), (0x9F64, 1), (0x8609, 0x01),
                                             (0x7E0E, 4), (0xFDF3, 0x60), (0xFDF4, 0x60), (0xF98C, 0x20)], None, 0),
    ('9e50_bolt_floor', 0x9E50, 'round1_48', [(0x9E57, _next(0x8DBD)), (0x9E5D, 0), (0x9F64, 1), (0x8609, 0x01),
                                             (0x7E0E, 4), (0xFDF3, 0x60), (0xFDF4, 0xB8), (0xFAEC, 0x20)], None, 0),
    # $A09A: the strike ($A0BA CALL nc, $A0C3 falls: $A0E0 at the root), a payload tick ($FECF $EF), the wrap
    # ($A0BE JP z,$8C28 at the root), and the flood: a row, the ramp, its payload, past it, the disarm
    ('a09a_strike', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0), (0xFECF, 0xFC)], None, 0),
    ('a09a_payload', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0), (0xFECF, 0xEF)], None, 0),
    ('a09a_wrap', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0), (0xFECF, 0xFF)], None, 0),
    ('a09a_flood_row', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0x01)], None, 0),
    ('a09a_flood_ramp', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0xB0)], None, 0),
    ('a09a_flood_payload', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0xC8)], None, 0),
    ('a09a_flood_past', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0xC9)], None, 0),
    ('a09a_flood_disarm', 0xA09A, 'round1_48', _GA0 + [(0xFECE, 0xFE)], None, 0),
    # $A9ED in the boss round: P1 carried ($9288 RET nz); ($FED0) set, P1's / P2's award ($92AD both ways)
    ('a9ed_carried', 0xA9ED, 'boss', _GA9 + [(0xFDDA, 0x10)], _hooks(*(_HA9 + [('poke', 0x927D, 0xFED0, 0)])), 0),
    ('a9ed_award_p1', 0xA9ED, 'boss', _GA9 + [(0xFDDA, 0x00)], _hooks(*(_HA9 + [('poke', 0x927D, 0xFED0, 1)])), 0),
    ('a9ed_award_p2', 0xA9ED, 'boss', _GA9 + [(0xFDDA, 0x01)], _hooks(*(_HA9 + [('poke', 0x927D, 0xFED0, 1)])), 0),
]
CALLS_BY = {c[0]: c for c in CALLS}


def call_run(label, root, state, pokes, hook=None, iff=0, model=None):
    h, rm = _machine(state)
    r, raw = h.sim.registers, rm.m
    for ad, v in pokes:
        raw[ad] = v(raw) if callable(v) else v
    r[IFF] = iff
    fd = h.frame_duration
    r[T] = (r[T] // fd + 1) * fd + h.int_active          # just past a frame's interrupt window
    back = (CALLSITE[root] + 3) & 0xFFFF
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[(sp + 1) & 0xFFFF] = back & 0xFF, back >> 8
    r[SP] = sp; r[PC] = root
    tr = Tracker(h, rm)
    tr.hook = hook
    tr.model = model
    tr.open(root, back)
    for _ in range(6000000):
        tr.step()
        if tr.isr is None and tr.cur is not None:
            tr.close_frames()
        if tr.cur is None:
            break
    else:
        raise AssertionError(label + ': no return')
    return tr.done[0], rm.m


# ---------------------------------------------------------------- rows, checks
def _rle(sig):
    out = []
    for p, ev in sig:
        tok = '%04x%s' % (p, ev)
        if out and out[-1][0] == tok:
            out[-1][1] += 1
        else:
            out.append([tok, 1])
    return ' '.join(t if n == 1 else '%sx%d' % (t, n) for t, n in out)


def check(model, m, x):
    """the model against the root and every nested frame, each predicted at its own close: (n, exact,
    misses) -- every frame, the abnormal ones too ('e' / 'k' events)"""
    n = ok = 0
    miss = []
    frames = [(x['root'], x['own'], x['sig'], x['pred'])] + list(x['nested'])
    for e, own, sig, v in frames:
        n += 1
        if v == own:
            ok += 1
        else:
            miss.append(['%04X' % e, own, v, _rle(sig)[:300]])
    return n, ok, miss


def row(label, x, forced):
    seed = x['seed']
    rom = sorted(a for a, _ in seed if a < 0x4000)
    sd = sorted((a, v) for a, v in seed if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if rom and a < 0x5800]
    post = [(a, v) for a, v in post if not (rom and a < 0x5800) and a >= 0x4000]
    out = {'state': label, 'forced': forced, 'root': '%04X' % x['root'], 'T': x['T'], 'own': x['own'],
           'sig': _rle(x['sig']), 'irq': x['irq'], 'halt': x['halt'], 'abn': x['abn'],
           'kids': [['%04X' % k, t] for k, t in x['kids']]}
    if not x['irq']:
        out.update({'seed': ''.join('%04x%02x' % (a, v) for a, v in sd),
                    'post': ''.join('%04x%02x' % (a, v) for a, v in post),
                    'rom': ' '.join('%04x' % a for a in rom), 'blind': ' '.join('%04x' % a for a in blind)})
    return out


def _key(x):
    return '%04X %d %s|%s' % (x['root'], x['own'], _rle(x['sig']), ','.join('%04X:%d' % k for k in x['kids']))


def one(job):
    """a natural survey of one state (or one forced call): per run (check, slim, key, row-or-None), and the
    model's blocks met"""
    name, tag = job
    model = Model()
    out = []
    if tag:
        c = CALLS_BY[tag]
        x, m = call_run(*c, model=model)
        out.append((check(model, m, x), _slim(x), _key(x), row(tag, x, True)))
    else:
        # the model is evaluated on the machine's memory AT the run's close
        runs, m = _run_checked(name, model)
        seen = collections.Counter()
        for x, chk in runs:
            k = _key(x)
            rw = None
            if seen[k] < KEEP and not x['irq']:
                seen[k] += 1
                rw = row(name, x, False)
            out.append((chk, _slim(x), k, rw))
    return out, {'%04X' % e: b for e, b in model.blocks.items()}


def _run_checked(name, model):
    """run() with each closed run checked against the model on the memory as the run left it (a later
    self-modification cannot reach a run already checked)"""
    h, rm = _machine(name, False)
    r, raw = h.sim.registers, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t_start = r[T]
    t_end = t_start + FRAMES * fd
    ki, nextk = 0, r[T]
    tr = Tracker(h, rm)
    tr.model = model
    out = []
    armed = False             # from the first pass top: a state saved inside a call (or its ISR) is not a run
    while r[T] < t_end or tr.cur is not None:
        if r[T] >= nextk:
            _keys(h, raw, ki)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        n0 = len(tr.done)
        tr.pre()                                 # a run that returns onto the next call site closes first
        if len(tr.done) > n0:
            x = tr.done[-1]
            out.append((x, check(model, raw, x)))
            tr.done = []
        if p == TOP and tr.isr is None:
            armed = True
        if armed and tr.cur is None and tr.isr is None and p in BY_SITE:
            root = BY_SITE[p]
            assert raw[p] == 0xCD
            tr.op[0xCD]()
            assert r[PC] == root
            tr.open(root, (p + 3) & 0xFFFF)
            if r[IFF] and r[T] % fd < h.int_active:
                b, spb, tt = r[PC], r[SP], r[T]
                if h.sim.accept_interrupt(r, rm, p):
                    tr.isr = (b, spb, tt); tr.cur['irq'] += 1; rm.rec = None
            continue
        if tr.cur is None and armed:
            assert p not in CALLSITE, 'a root entered other than from its call site ($%04X)' % p
        n0 = len(tr.done)
        tr.step()
        if len(tr.done) > n0:
            x = tr.done[-1]
            out.append((x, check(model, raw, x)))
            tr.done = []
    return out, raw


def _slim(x):
    return {'root': x['root'], 'T': x['T'], 'own': x['own'], 'sig': x['sig'], 'irq': x['irq'], 'halt': x['halt'],
            'abn': x['abn'], 'kids': x['kids']}


def contended_one(name):
    """one state's natural runs with contention ON: {root: [n, T]}, the runs an interrupt landed in left out"""
    runs, _ = run(name, FRAMES, True, record=False)
    out = collections.defaultdict(lambda: [0, 0])
    for x in runs:
        if not x['irq']:
            out['%04X' % x['root']][0] += 1; out['%04X' % x['root']][1] += x['T']
    return dict(out)


def window_one(job):
    """round1_48's first WINDOW frames, contention off / on, keys off / on"""
    c, keys = job
    runs, passes = run('round1_48', WINDOW, c, keys=keys, record=False)
    per = {}
    for e in ROOTS:
        rs = [x for x in runs if x['root'] == e]
        bp = collections.defaultdict(lambda: [0, 0])
        for x in rs:
            q = passes.get(x['frame'], 0)
            bp[str(q)][0] += 1; bp[str(q)][1] += x['T']
        ni = [x for x in rs if not x['irq']]
        ev = [x for x in rs if x['par'] == 0]
        per['%04X' % e] = {'all': [len(rs), sum(x['T'] for x in rs)], 'noirq': [len(ni), sum(x['T'] for x in ni)],
                           'eleven': [len(ev), sum(x['T'] for x in ev)],
                           'by_passes': {k: bp[k] for k in sorted(bp, key=int)},
                           'by_own': {str(k): v for k, v in sorted(collections.Counter(x['own'] for x in rs).items())},
                           'irq': sum(1 for x in rs if x['irq']), 'halt': sum(x['halt'] for x in rs)}
    return {'roots': per, 'passes': {str(k): passes[k] for k in sorted(passes)}}


def _stat(v):
    v = sorted(v)
    return {'n': len(v), 'min': v[0], 'max': v[-1], 'median': v[len(v) // 2], 'total': sum(v),
            'distinct': len(set(v))} if v else None


def static_decisions(m, entry):
    """the root's own decision points reachable without entering a callee: {pc: possible outcomes}"""
    out, todo, seen = {}, [entry], set()
    while todo:
        a = todo.pop()
        while a not in seen:
            seen.add(a)
            _guard(a)
            ln, txt = dec(m, a)
            o = m[a]
            if _is_decision(m, a):
                if o == 0xC9:
                    out[a] = ['x']
                    break
                if o == 0xE9 or o in (0xDD, 0xFD):
                    out[a] = ['j']
                    break
                if (o & 0xC7) == 0xC0:
                    out[a] = ['t', 'f']
                elif o == 0xED:
                    out[a] = ['t', 'f']
                else:
                    out[a] = ['t', 'f']
                    if o not in CALL_OPS:
                        todo.append(_target(m, a, ln))
                a = (a + ln) & 0xFFFF
                continue
            if o == 0xC3 or o == 0x18:
                a = _target(m, a, ln)
                continue
            a = (a + ln) & 0xFFFF
    return out


# root-level outcomes no call from the root's own call site can take (declared, with the reason)
UNREACHABLE = {
    '9C6Ft': '$9AEB: $9C6F JR z is taken only for type 8, and type 8 reaches $9C4B only as the CALL from $9D1B '
             '(a child frame); at the root $9C4B is reached by $9BD3 JP z for type 6',
    'A871t': '$A9ED: $A84D is entered with A = 4 ($A9F7), so C = 3 at $A85D: $A871 JR z (C = 0) cannot be taken',
    'A878t': '$A9ED: likewise C = 3: $A878 JR z (C = 2) cannot be taken',
}


def _letter(ev):
    """an event's outcome for the coverage: a RET that returned to a PUSHed address was taken"""
    return 't' if ev[0] == 'r' else ev[0]


def measure(jobs):
    jobs = min(jobs, MAXJOBS)
    work = [(s, None) for s in AA.STATES] + [(c[2], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, AA.STATES)
        wres = pool.map(window_one, [(False, False), (True, False), (False, True), (True, True)])
    per = {e: {'T': [], 'own': [], 'paths': collections.Counter(), 'irq': 0, 'halt': 0, 'abn': 0,
               'kids': collections.defaultdict(list), 'events': collections.Counter(), 'rows': [],
               'forced_events': collections.Counter(), 'forced_rows': []} for e in ROOTS}
    tally = {'natural': [0, 0], 'forced': [0, 0]}
    misses = []
    blocks = collections.defaultdict(dict)
    unc = {s: collections.defaultdict(lambda: [0, 0]) for s in AA.STATES}
    rowseen = collections.Counter()
    for (s, tag), (rs, bl) in zip(work, res):
        for e, b in bl.items():
            blocks[e].update(b)
        for (n, ok, miss), x, key, rw in rs:
            k = 'forced' if tag else 'natural'
            tally[k][0] += n; tally[k][1] += ok
            misses += [[tag or s] + mm for mm in miss][:6]
            q = per[x['root']]
            if tag:
                for p, ev in x['sig']:
                    q['forced_events']['%04X%s' % (p, _letter(ev))] += 1
                q['forced_rows'].append(rw)
                continue
            q['T'].append(x['T']); q['own'].append(x['own']); q['paths'][_rle(x['sig'])] += 1
            q['irq'] += 1 if x['irq'] else 0; q['halt'] += x['halt']; q['abn'] += x['abn']
            for ke, kt in x['kids']:
                q['kids']['%04X' % ke].append(kt)
            for p, ev in x['sig']:
                q['events']['%04X%s' % (p, _letter(ev))] += 1
            if not x['irq']:
                unc[s]['%04X' % x['root']][0] += 1; unc[s]['%04X' % x['root']][1] += x['T']
            if rw is not None and rowseen[key] < KEEP:
                rowseen[key] += 1
                q['rows'].append(rw)
    # the static decision map from round1_48's code (a root's reachable own decisions), for the coverage
    h, rm = _machine('round1_48')
    # M7.96: the census world's self-modified toggles, edge operands and gates -- round1_48 at the window's start
    world = {'%04X' % a: rm.m[a] for a in WORLD_BYTES}
    out = {}
    for e in ROOTS:
        q = per[e]
        sd = static_decisions(rm.m, e)
        possible = sorted('%04X%s' % (a, o) for a, os_ in sd.items() for o in os_ if o not in ('j',))
        nat = set(q['events'])
        allseen = nat | set(q['forced_events'])
        ek = '%04X' % e
        out[ek] = {
            'callsite': '%04X' % CALLSITE[e], 'runs': len(q['T']), 'irq_runs': q['irq'], 'halts': q['halt'],
            'abnormal': q['abn'], 'T': _stat(q['T']), 'own': _stat(q['own']), 'paths': len(q['paths']),
            'path_counts': dict(sorted(q['paths'].items(), key=lambda kv: -kv[1])[:60]),
            'kids': {k: _stat(v) for k, v in sorted(q['kids'].items())},
            'events_natural': dict(sorted(q['events'].items())),
            'events_forced': dict(sorted(q['forced_events'].items())),
            'static_outcomes': possible,
            'never_natural': [d for d in possible if d not in nat and not d.endswith('x')],
            'never_at_all': [d for d in possible if d not in allseen and not d.endswith('x')],
            'unreachable': {d: UNREACHABLE[d] for d in possible if d in UNREACHABLE},
            'uncovered': [d for d in possible if d not in allseen and not d.endswith('x') and d not in UNREACHABLE],
            'contended': {s: [list(unc[s].get(ek, [0, 0])), list(cres[i].get(ek, [0, 0]))]
                          for i, s in enumerate(AA.STATES)},
            'window': {'off': wres[0]['roots'][ek], 'on': wres[1]['roots'][ek]},
            'window_keys': {'off': wres[2]['roots'][ek], 'on': wres[3]['roots'][ek]},
            'blocks': {k: blocks[ek][k] for k in sorted(blocks.get(ek, {}))},
            'rows': q['rows'], 'forced': q['forced_rows']}
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'window_frames': WINDOW, 'actions': B.ACTIONS,
            'key_frames': B.KEY_FRAMES, 'states': AA.STATES, 'forced': [[c[0], '%04X' % c[1]] for c in CALLS],
            'model': {'checked_exact': tally, 'misses': misses[:60]},
            'window_passes': {'off': wres[0]['passes'], 'on': wres[1]['passes'],
                              'keys_off': wres[2]['passes'], 'keys_on': wres[3]['passes']},
            'kid_blocks': {k: v for k, v in sorted(blocks.items()) if int(k, 16) not in CALLSITE},
            'window_world': world, 'routines': out}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else MAXJOBS
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('model', F['model']['checked_exact'])
    for mm in F['model']['misses'][:20]:
        print('  MISS', mm)
    for e, q in F['routines'].items():
        w0, w1 = q['window']['off']['noirq'], q['window']['on']['noirq']
        print('%s runs %d irq %d halt %d abn %d paths %d T %s..%s own %s..%s | window off %s on %s | uncovered %s' % (
            e, q['runs'], q['irq_runs'], q['halts'], q['abnormal'], q['paths'], q['T']['min'], q['T']['max'],
            q['own']['min'], q['own']['max'], w0, w1, q['uncovered']))


if __name__ == '__main__':
    main()
