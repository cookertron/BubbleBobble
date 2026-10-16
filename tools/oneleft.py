"""M7.50 -- $8EC9 CALL $90A9: THE ONE-ENEMY-LEFT ANGER, driven through the real machine code.

The level-clear decision $8E3A tallies bit 7 of +7 over ($AA57) - 2 slots ($8EAA) and, with
exactly one set, `$8EC9 CALL $90A9 / $8ECC OR $2A / RET`.  $90A9 is

    $90A9  LD A,n / OR A / RET nz      $90AA is that LD's own OPERAND: the anger LATCH
    $90AD  INC A / LD ($90AA),A
    $90B1  XOR A / LD ($FEC4),A        the odd ISR pass gate CLOSED around the walk
    $90B5  CALL $90C1                  the temper walk: SET 2,(+7) / AND $F8 on +5, every
                                       enemy slot, ($AA57) - 2 of them, a DJNZ (0 = 256)
    $90B8  LD A,1 / LD ($FEC4),A / LD ($FEC5),A / RET

and the hurry-up $9037 reaches the SAME body by falling into it from $90A6 (no CALL).

WHY THIS ORACLE AND NOT tools/popkill.py.  popkill's rows are ONE ISR EACH, re-seeded from the
machine's PRE: the main loop between two ISRs -- where $8E3A runs -- is never executed by that
gate, and the PRE of the next row already carries whatever $8EC9 wrote, so a stub, a wired call
and a wrong walk all pass it identically (the stub passed the whole pre-M7.50 suite).  This
oracle samples the routine where it runs: at its own entry, interrupts off (DIRECT, SEQUENCE),
and at every one of its main-loop calls in natural play (DECISIONS: the PRE at $8E3A and the
POST at $8D61, the instruction after `$8D5E CALL $8E3A`).

PHASES
  direct     $8E3A called at its own entry over BUILT worlds from round1_48 (SP pinned,
             interrupts off): the living slot anywhere, live/corpse/angry flag values,
             dead-slot flags with bit 2 clear, +5 with its low three bits set on EVERY slot
             (so the AND $F8 is visible where it lands and where it does not), the latch
             0/1/$FF/$80/2, $90D0 $D6/$96, the two gates from six starts, ($AA57) 3..9 and
             the unreachable 12 (which walks into both players' status records), and the
             controls that never reach $8EC9 with one alive (the clear latch $8E3B, the
             level-skip $FED1, the boss round) or reach it with two.
  sequence   machine call SEQUENCES on one world: $8E3A twice (the latch), the hurry $9037
             then $8E3A (the hurry's walk latches the one-left out), $8E3A then $9037 (the
             one-left's walk latches the hurry's fall-in out), the respawn's calm
             ($ABD5 / $90C1 / $ABD5, as $ABB4..$ABBA runs it) then $8E3A (SET again), $8E3A
             then the calm then $8E3A (the enemies stay CALM), and $8E3A then the round
             reset $984B (to $9858) then $8E3A (the latch cleared, the walk again).
  natural    interrupts ON, key scripts, hooks: every $8EC9 call, every $90A9 entry with its
             return address, every walk ($90C1 .. $90D9) with the table before and after,
             every calm ($ABB7), hurry ($9052), corpse landing ($8B83), clear ($8ECF), advance
             ($97F8) and hurry reset ($9163), a WRITE WATCH on $90AA, and every enemy slot's X/Y/+7 per ISR.
               N1  round1_48, popkill's N1 keys ('7' 2 frames in 16 for ISRs < 400), to the
                   advance and 60 ISRs on: the last "alive" slot is a flying CORPSE.
               L1  round1_48, the same keys cut at ISR 200: the last enemy is ALIVE and
                   walking when the second corpse lands -- the anger, its speed, and the
                   respawn's calm that the latch then keeps.
  decisions  N1 and L1 again, every $8E3A call: PRE at $8E3A, POST at $8D61, the Z flag, the
             walk events inside it, and whether an ISR landed inside the bracket.
  census     long natural runs over several states: the $90AA WRITERS and the event counts.

STORED: a fixed RAM VECTOR (the item block $9603..$9644, $FD80..$FFFF, and the named scalars)
as packed diffs; per-ISR enemy X/Y/+7; event lists.  No ROM byte, no display byte.

Usage:  python tools/oneleft.py capture               -> build/oneleft_fixture.json
        python tools/oneleft.py capture direct ...    re-run only the named phases, merged
        python tools/oneleft.py verify                re-run direct + sequence and diff
"""
import sys, os, json, base64, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, PC, SP, T, F, IYh, IYl
import portconfig as pc
from keyprobe import press

FIXTURE = 'build/oneleft_fixture.json'
BRANCH_BYTE = 0x8DC4
GUARD = range(0xD000, 0xD300)
ISR_IN = 0x8D72
CHECK, CHECK_RET = 0x8E3A, 0x8D61
ONELEFT = 0x8EC9
ANGER, LATCH_ST, WALK, WALK_SET, WALK_END, ANGER_RET = 0x90A9, 0x90AE, 0x90C1, 0x90CF, 0x90D9, 0x90C0
HURRY, HURRY_FIRE = 0x9037, 0x9052
FLIP, CALM = 0xABD5, 0xABB7
RESET_WALK, RESET_END = 0x984B, 0x9858
LATCH, OPCODE, G4, G5, SLOTS = 0x90AA, 0x90D0, 0xFEC4, 0xFEC5, 0xAA57
TABLE, POOL = 0xFD80, 0xFED8
RANGES = [(0x9603, 0x9645), (0xFD80, 0x10000)]
SCALARS = [0x745C, 0x745D, 0x8609, 0x86CD, 0x8CB0, 0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE, 0x8E3B,
           0x8F3A, 0x9049, 0x904D, 0x90AA, 0x90D0, 0x9160, 0x9257, 0x9AE8, 0x9AE9, 0x9F62, 0xAA57]


def vector():
    v = []
    for lo, hi in RANGES:
        v += list(range(lo, hi))
    v += SCALARS
    assert len(v) == len(set(v)), 'vector overlaps'
    assert all(a >= 0x4000 for a in v), 'a ROM address in the vector'
    assert not any(0x4000 <= a < 0x5B00 for a in v), 'a display address in the vector'
    return v


VEC = vector()


def pack(prev, cur):
    """the changes prev -> cur as runs: uint16 LE index, uint8 length, bytes; base64"""
    out = bytearray()
    i, n = 0, len(cur)
    while i < n:
        if prev[i] == cur[i]:
            i += 1
            continue
        j = i + 1
        while j < n and j - i < 255 and prev[j] != cur[j]:
            j += 1
        out += bytes([i & 0xFF, i >> 8, j - i]) + bytes(cur[i:j])
        i = j
    return base64.b64encode(bytes(out)).decode()


def unpack(prev, s):
    cur = list(prev)
    b = base64.b64decode(s)
    p = 0
    while p < len(b):
        i = b[p] | (b[p + 1] << 8)
        n = b[p + 2]
        p += 3
        cur[i:i + n] = b[p:p + n]
        p += n
    return cur


def b64(v):
    return base64.b64encode(bytes(v)).decode()


def sample(m):
    return [m[a] for a in VEC]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


# ------------------------------------------------------------------ direct calls
class Caller:
    """direct calls with SP PINNED at the state's own (TRAPS #42), interrupts off, and a
       count of the PCs that say what ran: $8EC9, $90A9, the latch store $90AE, the walk's
       SET $90CF (once per slot visited), $9052 (the hurry fired)"""
    COUNT = (ONELEFT, ANGER, LATCH_ST, WALK_SET, HURRY_FIRE)

    def __init__(self, state='round1_48'):
        self.h, self.m = new(state)
        self.sp0 = self.h.sim.registers[SP]

    def call(self, addr, stop=None, limit=10 ** 8):
        h, m = self.h, self.m
        r = h.sim.registers
        sp = self.sp0
        for sent in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp] = sent & 0xFF
            m[sp + 1] = sent >> 8
        r[SP] = sp
        r[PC] = addr
        seen = {k: 0 for k in self.COUNT}
        gw = None                                   # ($FEC4, $FEC5) as the $90C1 walk is entered
        targets = set(h.SENTINELS) | set(self.COUNT) | set(GUARD) | {WALK}
        if stop is not None:
            targets.add(stop)
        t0 = r[T]
        n = 0
        while True:
            h.run_until(targets, limit=limit, stride=1, interrupts=False)
            p = r[PC]
            if p in GUARD:
                raise SystemExit('PC entered the guard at $%04X' % p)
            if p in h.SENTINELS or p == stop:
                break
            if p in seen:
                seen[p] += 1
            if p == WALK and gw is None:
                gw = [m[G4], m[G5]]
            h.step(1, interrupts=False)
            n += 1
            if n > 10 ** 6:
                raise SystemExit('runaway from $%04X' % addr)
        z = 1 if (r[F] & 0x40) else 0
        ret = h.SENTINELS.index(p) if p in h.SENTINELS else 'stop'
        return dict(z=z, ret=ret, t=r[T] - t0,
                    oneleft=seen[ONELEFT], anger=seen[ANGER], latched=seen[LATCH_ST],
                    iters=seen[WALK_SET], hurry=seen[HURRY_FIRE], gates_at_walk=gw)


def xpat(kind, k):
    """the +5 seed for slot k: 'odd' has its low three bits all SET, 'mixed' varies them,
       'aligned' is already a multiple of 8"""
    if kind == 'odd':
        return (0x17 + 16 * k) & 0xFF
    if kind == 'mixed':
        return (0x13 + 37 * k) & 0xFF
    return (0x10 + 16 * k) & 0xF8


def build(m, c):
    """one DIRECT world from round1_48: every enemy slot dead with `dead`, `alive` of them
       live with `live` from slot `at`; +5 of all twelve slots from `x5`; the players' +5
       odd and +7 bit 2 clear; the named bytes at known values"""
    for k in range(12):
        b = TABLE + 10 * k
        m[b + 5] = xpat(c['x5'], k)
        if k >= 2:
            m[b + 7] = c['dead']
            m[b + 9] = 0x00
    m[TABLE + 7] = 0xC1
    m[TABLE + 17] = 0xC0
    for j in range(c['alive']):
        k = c['at'] + j
        m[TABLE + 10 * k + 7] = c['live']
        m[TABLE + 10 * k + 9] = c.get('nine', 0x00)
    for k in range(12):
        m[POOL + 10 * k + 4] = 0x11
        m[POOL + 10 * k + 9] = 0x22
    m[SLOTS] = c['count']
    m[LATCH] = c['latch']
    m[OPCODE] = c['op']
    m[G4], m[G5] = c['gates']
    m[0x8E3B] = c.get('clear', 0)
    m[0xFED1] = c.get('fed1', 0)
    m[0x8609] = c.get('round', 1)
    m[0x9F62] = c.get('hp', 0x2A)
    m[0x8DBD], m[0x8DBE] = 0x40, 0x02
    m[0x8DB6], m[0x8DB7] = 0x34, 0x12
    m[0xFECA] = 0xEE
    for a in (0x9160, 0x8CB0, 0x86CD, 0x9049, 0x904D, 0x9AE8, 0x9AE9, 0xFECC):
        m[a] = 0


BASE = dict(count=5, alive=1, at=3, live=0xC0, dead=0x40, x5='odd', latch=0, op=0xD6,
            gates=(0x14, 0x01))


def direct_cases():
    out = [('base: one live enemy at slot 3 of three, dead flags $40, every +5 odd', {})]
    for v in (1, 0xFF, 0x80, 0x02):
        out.append(('the latch $%02X' % v, dict(latch=v)))
    out.append(('$90D0 = $96 (RES 2,(HL)): the walk CALMS', dict(op=0x96, live=0xC4, dead=0x44)))
    for g in ((0x58, 0x01), (0x00, 0x00), (0x01, 0x00), (0x00, 0x01), (0x14, 0x14)):
        out.append(('gates ($%02X, $%02X)' % g, dict(gates=g)))
        out.append(('gates ($%02X, $%02X), latched' % g, dict(gates=g, latch=1)))
    for n in (3, 4, 9):
        out.append(('($AA57) = %d, the one alive FIRST' % n, dict(count=n, at=2)))
        out.append(('($AA57) = %d, the one alive LAST' % n, dict(count=n, at=n - 1)))
    out.append(('($AA57) = 12 (unreachable): the walk runs into both players\' status records',
                dict(count=12, at=11)))
    for v in (0xC1, 0x80, 0xC4, 0xE1, 0x8C, 0x8D, 0xC8):
        out.append(('the one alive has flags $%02X' % v, dict(live=v)))
    out.append(('a flying corpse ($8D, +9 = $FF) is the one alive', dict(live=0x8D, nine=0xFF)))
    for v in (0x00, 0x3E, 0x3B, 0x7F):
        out.append(('dead flags $%02X' % v, dict(dead=v)))
    out.append(('every +5 already 8-aligned', dict(x5='aligned')))
    out.append(('+5 mixed', dict(x5='mixed', count=9, at=5)))
    # the controls: one alive, but $8EC9 is never reached -- and two alive
    out.append(('control: the clear latch $8E3B set (the countdown owns the pass)', dict(clear=1)))
    out.append(('control: $FED1 set (the level-skip drain owns the pass)', dict(fed1=1)))
    out.append(('control: the boss round, HP alive', dict(round=0x50)))
    out.append(('control: TWO alive', dict(alive=2, at=2)))
    out.append(('control: NONE alive (the one-shot cleanup)', dict(alive=0)))
    return out


def phase_direct():
    rows = []
    for label, over in direct_cases():
        c = dict(BASE)
        c.update(over)
        cl = Caller()
        build(cl.m, c)
        pre = sample(cl.m)
        x = cl.call(CHECK)
        post = sample(cl.m)
        rows.append(dict(label=label, case={k: (list(v) if isinstance(v, tuple) else v)
                                            for k, v in c.items()},
                         pre=b64(pre), post=pack(pre, post), **x))
    return rows


# ------------------------------------------------------------------ sequences
def calm(cl):
    """$ABB4 CALL $ABD5 / $ABB7 CALL $90C1 / $ABBA CALL $ABD5 -- the respawn's three calls"""
    a = cl.call(FLIP)
    b = cl.call(WALK)
    c = cl.call(FLIP)
    return dict(z=c['z'], ret=[a['ret'], b['ret'], c['ret']], t=a['t'] + b['t'] + c['t'],
                oneleft=0, anger=0, latched=0, iters=b['iters'], hurry=0,
                gates_at_walk=b['gates_at_walk'])


def hurry_ready(m):
    """the clock one past the state's own threshold, both hurry latches clear (hurry.py's
       ready(), without its latch poke: $90AA is whatever the sequence left)"""
    th = m[0x745C] | (m[0x745D] << 8)
    c = (th + 1) & 0xFFFF
    m[0x8DBD], m[0x8DBE] = c & 0xFF, c >> 8
    m[0x9049] = 0
    m[0x904D] = 0


SEQS = [
    ('S1', 'the one-left call twice: the second returns at $90AC', ['check', 'check']),
    ('S2', 'the hurry fires first and walks; the one-left call then returns at the latch',
     ['hurry', 'check']),
    ('S3', 'the one-left call walks first; the hurry then fires its banner and its fall-in returns at the latch',
     ['check', 'hurry']),
    ('S4', 'the respawn calm on angry enemies, then the one-left call: the walk SETs again',
     ['calm', 'check']),
    ('S5', 'the one-left walk, the respawn calm, the one-left call again: the enemies stay CALM',
     ['check', 'calm', 'check']),
    ('S6', 'the one-left walk, the round reset $984B..$9857, the one-left call: the latch is clear and it walks again',
     ['check', 'reset', 'check']),
]


def phase_sequence():
    out = []
    for name, what, steps in SEQS:
        cl = Caller()
        c = dict(BASE)
        if steps[0] == 'calm':
            c.update(live=0xC4, dead=0x44)          # angry enemies for the calm to calm
        build(cl.m, c)
        pre = sample(cl.m)
        prev = pre
        rows = []
        for st in steps:
            if st == 'hurry':
                hurry_ready(cl.m)
            before = sample(cl.m)
            if st == 'check':
                x = cl.call(CHECK)
            elif st == 'hurry':
                x = cl.call(HURRY)
            elif st == 'calm':
                x = calm(cl)
            elif st == 'reset':
                x = cl.call(RESET_WALK, stop=RESET_END)
            post = sample(cl.m)
            rows.append(dict(step=st, pokes=pack(prev, before), post=pack(before, post), **x))
            prev = post
        out.append(dict(name=name, what=what, case={k: (list(v) if isinstance(v, tuple) else v)
                                                    for k, v in c.items()},
                        pre=b64(pre), rows=rows))
    return out


# ------------------------------------------------------------------ natural play
def keys_n1(i):
    return (['7'] if (i % 16) < 2 and i < 400 else []), 0


def keys_l1(i):
    return (['7'] if (i % 16) < 2 and i < 200 else []), 0


def keys_blow(i):
    return (['7'] if (i % 16) < 2 else []), 0


def keys_walkblow(i):
    k = ['8'] if (i // 120) % 2 == 0 else ['5']
    if (i % 12) < 2:
        k.append('7')
    if (i % 60) in (30, 31):
        k.append('0')
    return k, 0


KEYS = {'n1': keys_n1, 'l1': keys_l1, 'blow': keys_blow, 'walkblow': keys_walkblow}


class Stop(Exception):
    pass


class Natural:
    def __init__(self, state, keyname, nisr, after_advance=None, decisions=False):
        self.h, self.m = new(state)
        self.state, self.keyname, self.keyfn = state, keyname, KEYS[keyname]
        self.nisr, self.after_advance, self.want_dec = nisr, after_advance, decisions
        self.isr = -1
        self.in_isr = False
        self.stop_at = None
        self.ev = []
        self.ents = []
        self.dec = []
        self.dec_open = None
        self.dec_prev = None
        self.dec_seed = None
        self.logmarks = []
        self.hooks = {
            ISR_IN: self.on_isr,
            0x8DA1: self.on_isr_ret,
            CHECK: self.on_check,
            CHECK_RET: self.on_check_ret,
            ONELEFT: self.on_oneleft,
            ANGER: lambda: self.e('anger', '%04X' % self.ret(), self.m[LATCH]),
            LATCH_ST: lambda: self.e('latch'),
            WALK: lambda: self.e('walk', '%04X' % self.ret(), self.m[OPCODE], self.table()),
            WALK_END: lambda: self.e('walkend', self.m[OPCODE], self.table()),
            ANGER_RET: lambda: self.e('gates', self.m[G4], self.m[G5]),
            HURRY_FIRE: lambda: self.e('hurry', self.clock()),
            CALM: lambda: self.e('calm', '%04X' % self.iy(), self.m[OPCODE]),
            0x8ECF: lambda: self.e('clear'),
            0x8B83: lambda: self.e('land', (self.iy() - TABLE) // 10),   # $8B83 the corpse LANDS: $8B87 RES 7
            0x97F8: self.on_advance,
            0x9163: lambda: self.e('hurryreset'),
        }

    # ---- helpers
    def iy(self):
        r = self.h.regs
        return (r[IYh] << 8) | r[IYl]

    def ret(self):
        sp = self.h.regs[SP]
        return self.m[sp] | (self.m[(sp + 1) & 0xFFFF] << 8)

    def clock(self):
        return self.m[0x8DBD] | (self.m[0x8DBE] << 8)

    def e(self, *x):
        self.ev.append([self.isr] + list(x))
        if self.dec_open is not None:
            self.dec_open['ev'].append(list(x[:1]))

    def table(self):
        """every enemy slot's +5, +7 (the walk's two bytes) and +6"""
        m = self.m
        return [[k, m[TABLE + 10 * k + 5], m[TABLE + 10 * k + 6], m[TABLE + 10 * k + 7]]
                for k in range(2, m[SLOTS])]

    # ---- hooks
    def on_isr(self):
        self.isr += 1
        if self.isr >= self.nisr or (self.stop_at is not None and self.isr >= self.stop_at):
            raise Stop()
        self.logmarks.append(len(self.h.memobj.log))
        self.in_isr = True
        if self.dec_open is not None:
            self.dec_open['isr_inside'] = 1
        keys, kemp = self.keyfn(self.isr)
        p = self.h.ports
        p.release_all()
        for k in keys:
            press(p, k)
        p.kempston = kemp
        self.ents.append([[k, x, y, f] for k, x, y, f in self.table()])

    def on_isr_ret(self):
        self.in_isr = False

    def on_oneleft(self):
        m = self.m
        alive = [k for k in range(2, m[SLOTS]) if m[TABLE + 10 * k + 7] & 0x80]
        self.e('oneleft', m[LATCH], m[G4], m[G5], alive,
               [[k, m[TABLE + 10 * k + 7], m[TABLE + 10 * k + 9]] for k in alive])

    def on_advance(self):
        self.e('advance', self.m[0x8609])
        if self.after_advance is not None and self.stop_at is None:
            self.stop_at = self.isr + self.after_advance

    def on_check(self):
        if not self.want_dec or self.in_isr:
            return
        pre = sample(self.m)
        if self.dec_seed is None:
            self.dec_seed = pre
            d_pre = ''
        else:
            d_pre = pack(self.dec_prev, pre)
        self.dec_open = dict(i=self.isr, pre=d_pre, ev=[], isr_inside=0, _pre=pre)

    def on_check_ret(self):
        """one DECISION row, compact: [ISR, PRE (packed from the last POST), POST (packed from
           its PRE), Z, cut (an ISR landed inside the bracket), the event kinds inside]"""
        d = self.dec_open
        if d is None:
            return
        post = sample(self.m)
        z = 1 if (self.h.regs[F] & 0x40) else 0
        self.dec.append([d['i'], d['pre'], pack(d['_pre'], post), z, d['isr_inside'],
                         [e[0] for e in d['ev']]])
        self.dec_prev = post
        self.dec_open = None

    def run(self):
        h, H = self.h, self.hooks
        h.memobj.watch(LATCH, LATCH + 1)
        tg = set(H) | set(GUARD)
        if h.regs[PC] in tg:
            h.step(1)
        try:
            while True:
                h.run_until(tg, limit=10 ** 9, stride=1)
                p = h.regs[PC]
                if p in GUARD:
                    raise SystemExit('PC entered the guard at $%04X' % p)
                H[p]()
                h.step(1)
        except Stop:
            pass
        import bisect
        w = [['%04X' % pcw, v, bisect.bisect_right(self.logmarks, j) - 1]
             for j, (pcw, a, v) in enumerate(h.memobj.log)]
        h.memobj.unwatch()
        return w


def phase_natural():
    out = []
    for name, state, keys, n, after in (('N1', 'round1_48', 'n1', 1400, 60),
                                        ('L1', 'round1_48', 'l1', 800, None)):
        nat = Natural(state, keys, n, after_advance=after, decisions=True)
        w = nat.run()
        out.append(dict(name=name, state=state, keys=keys, nisr=nat.isr, ev=nat.ev,
                        ents=nat.ents, w90aa=w,
                        dec_seed=b64(nat.dec_seed), decisions=nat.dec))
        print('  %s: %d ISRs, %d events, %d decisions, $90AA writes %s'
              % (name, nat.isr, len(nat.ev), len(nat.dec), w), flush=True)
    return out


CENSUS = [('round1_48', 'walkblow', 4000), ('r6_48', 'walkblow', 4000),
          ('r20_48', 'blow', 4000), ('r50_48', 'walkblow', 4000),
          ('r60_48', 'walkblow', 4000), ('round1_2p48', 'blow', 4000), ('hurryup', 'blow', 3000)]


def phase_census():
    out = []
    for state, keys, n in CENSUS:
        nat = Natural(state, keys, n)
        w = nat.run()
        kinds = {}
        for e in nat.ev:
            kinds[e[1]] = kinds.get(e[1], 0) + 1
        walks = [[e[0], e[2], e[3]] for e in nat.ev if e[1] == 'walk']
        out.append(dict(state=state, keys=keys, nisr=nat.isr, w90aa=w, counts=kinds,
                        walks=walks,
                        events=[e for e in nat.ev if e[1] in ('latch', 'hurry', 'calm', 'clear',
                                                              'advance', 'hurryreset')],
                        anger_from=sorted(set(e[2] for e in nat.ev if e[1] == 'anger'))))
        print('  census %s %s: %d ISRs, %s, $90AA writers %s'
              % (state, keys, nat.isr, kinds, sorted(set((x[0], x[1]) for x in w))), flush=True)
    return out


# ------------------------------------------------------------------ claims
def assertions(fx):
    """the claims the gate leans on, checked HERE on the machine's own numbers"""
    A = []

    def claim(name, ok, detail=''):
        A.append(dict(name=name, held=bool(ok), detail=detail))

    D = fx['direct']
    walked = [r for r in D if r['latched']]
    claim('every direct row that walked entered $8EC9 and $90A9 once and latched once',
          all(r['oneleft'] == 1 and r['anger'] == 1 and r['latched'] == 1 for r in walked))
    claim('a non-zero latch always returns at $90AC: no latch store, no walk',
          all(r['latched'] == 0 and r['iters'] == 0 for r in D
              if r['case']['latch'] != 0 and r['oneleft']))
    claim('the walk visits ($AA57) - 2 slots',
          all(r['iters'] == r['case']['count'] - 2 for r in walked))
    claim('the decision is NZ on every one-left row, walked or latched',
          all(r['z'] == 0 for r in D if r['oneleft']))
    claim('the controls never reach $8EC9',
          all(r['oneleft'] == 0 for r in D if r['label'].startswith('control')))
    for sc in fx['natural']:
        ev = sc['ev']
        calls = [e for e in ev if e[1] == 'oneleft']
        walks = [e for e in ev if e[1] == 'walk' and e[2] == '90B8']
        claim('%s: exactly one $90A9 walk per round, the first $8EC9 call' % sc['name'],
              len(walks) == 1 and calls and calls[0][2] == 0 and
              all(e[2] == 1 for e in calls[1:]),
              '%d calls, walk at ISR %s' % (len(calls), [e[0] for e in walks]))
        claim('%s: the only $90AA writers are $90AE (:= 1) and $9855 (:= 0)' % sc['name'],
              all((w[0], w[1]) in (('90AE', 1), ('9855', 0)) for w in sc['w90aa']))
        inside = [d for d in sc['decisions'] if d[4]]
        claim('%s: no decision bracket carrying a walk was cut by an ISR' % sc['name'],
              not any('latch' in d[5] for d in inside), '%d brackets cut' % len(inside))
        claim('%s: every walk is inside a decision bracket (the $8EC9 call, not the hurry)' % sc['name'],
              sum(1 for d in sc['decisions'] if 'latch' in d[5]) == len(walks))
    return A


def capture(phases=None):
    """all phases, or only the named ones merged into the existing fixture (the census is
       ten minutes and stores no vector, so a VEC change need not re-run it)"""
    t0 = time.time()
    if phases:
        fx = json.load(open(FIXTURE))
    else:
        fx = {}
        phases = ['direct', 'sequence', 'natural', 'census']
    fx.update(note=__doc__.strip(), vector=[[lo, hi] for lo, hi in RANGES], scalars=SCALARS,
              vector_len=len(VEC))
    if 'direct' in phases:
        fx['direct'] = phase_direct()
        print('direct: %d rows (%d walked)' % (len(fx['direct']),
                                              sum(1 for r in fx['direct'] if r['latched'])), flush=True)
    if 'sequence' in phases:
        fx['sequence'] = phase_sequence()
        print('sequence: %d' % len(fx['sequence']), flush=True)
    if 'natural' in phases:
        fx['natural'] = phase_natural()
    if 'census' in phases:
        fx['census'] = phase_census()
    fx['assertions'] = assertions(fx)
    bad = [a for a in fx['assertions'] if not a['held']]
    for a in fx['assertions']:
        print('  %s %s %s' % ('ok ' if a['held'] else 'BAD', a['name'], a['detail']))
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s in %.0fs (%d claims, %d failed)' % (FIXTURE, time.time() - t0,
                                                       len(fx['assertions']), len(bad)))
    if bad:
        raise SystemExit(1)


def verify():
    old = json.load(open(FIXTURE))
    new_d = phase_direct()
    new_s = phase_sequence()
    bad = 0
    for a, b in zip(old['direct'], new_d):
        if a != b:
            bad += 1
            print('direct differs:', a['label'])
    for a, b in zip(old['sequence'], new_s):
        if a != b:
            bad += 1
            print('sequence differs:', a['name'])
    print('verify: %d differing (direct and sequence re-run; natural and census are not)' % bad)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        capture(sys.argv[2:] or None)
    else:
        verify()
