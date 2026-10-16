"""RESPAWN / INVULNERABILITY COST -- the player's death, respawn and (IY+$5A) bit 3 frames, UNCONTENDED.

TIMING.md "Still not measured" item 6: the respawn frame and the invulnerability flash had no natural
evidence in any 48K state (no SAVED state has (IY+$5A) bit 3 set).  A run reaches them NATURALLY: with
NO KEYS held an enemy walks into the player ($925A -> $927D sets +$5A bit 2), the death tick $AB3F
counts +4 down from $50, and the respawn $AB6B..$ABD4 writes +$5A := (+$5A & 1) | $88 -- bit 3, which
$ABDE counts down for 161 heavy frames while $A447's $A5FB `BIT 3,(IY+$5A) / RET nz` skips the
player's draw on the $A3B2 toggle's phase 0: the flash.

MACHINE ONLY (TRAPS #239).  This tool reads NOTHING from web/; every number in the fixture is the Z80's.
A gate seeds a fresh engine from a row's `seed`, calls the port's function for that bracket, and compares
its T (and writes) with the row's `T` (and `post`).  The engine's side is computed by the gate.

NATURAL_STATES run FRAMES frames each, no keys, interrupts on, UNCONTENDED (a run's T is the sum of its
instructions' own T).  The brackets, all inside the ISR (an interrupt accepted inside one is asserted
absent):

  a447    every $A447 call from the pass ($A402 CALL z, return $A405), ANY slot: entry -> back at $A405
  ab38    every $AB38 run on a DYING player (+$5A bit 2 at entry): entry -> the RET (SP back to entry+2);
          arms 'dying' ($AB5D RET p taken), 'respawn' ($AB61 JP p taken), 'final' ($AB61 not taken:
          $AB64 RES 7 / CALL $BF0A)
  count   $ABDE -> $ABF4, the invulnerability countdown, from EVERY $AB38 run
  panel   $806C -> $AB70, the lives panel inside a respawn / final run

Every bracket row carries:
  T      the machine T, entry to exit
  sig    every conditional executed, 'pppp' + t/f + '*n' (taken / fall-through, count) -- the branch
         outcomes (the arm and path), the machine's own
  seg    T between marks (a447: head / erase / junction / gate / draw; ab38: head / panel / mid / calm / tail)
  seed   every byte READ before it is written in the bracket, 'aaaavv' hex (not the instruction's own
         bytes, not the bracket's stack window [SP-$40, SP+2)) -- plus the self-modified bytes read as STATE:
         the opcodes at $A5D9 (NOP / RET, the junction) and $A480 (JP nz / JP), $A430's operand $A431 (the beam)
  rom    the addresses below $4000 read (NEVER their values, TRAPS #281)
  post   every byte written ($4000 up, outside the stack window), its final value; when `rom` is not empty the
         bitmap writes ($4000..$57FF) are addresses only, in `blind`
Rows are kept KEEP per (kind, label, T, forced); `terms` and `segs` count EVERY bracket.

LABELS are machine facts: slot (0 / 1 / 'e' an enemy or other, by IY), the branch outcomes, the cached
geometry (+2 Y class: 0 if Y&7 == 0, 1 odd, 2 even non-zero; +6 Y&7 != 0) and the toggle phase ($A3B2 & 1).
  a447:  'skip-b7' ($A451 JP p taken) | 'skip-b3' ($A456 JR nz taken) | 'first' ($A45E JP z taken: no cache)
         | 'high' ($A466 JP nc: cached Y >= $C0) | 'erase{A,S}{y3}' ($A480 JP nz not taken A / taken S);
         then 'ph1' ($A5E8 JR c taken) or 'ph0'; 'b3' when the slot's +$5A bit 3 is set; 'flash-return'
         ($A5FF RET nz taken); 'draw{A,S}{0,1}' ($A611 JP nz not taken A / taken S); '+cN' = N beam
         carries ($A435 RET nc not taken)
  ab38:  'dying spr{C6C0,D300}' | 'respawn r80{0,1} p{1,2} calm{n}' | 'final ...'
  count: 'off' ($ABE2 JR z taken) | 'frozen' ($ABE8 JR z taken) | 'tick' ($ABED JP p taken) | 'tick-end'
  panel: its sig

THE TERMS, AS ZILOG SUMS (from `python tools/adis.py`; a gate may re-derive them from `segs`):
  countdown ($ABDE..$ABF4):
    off       BIT 3,(IY+d) 20 / JR z taken 12                                                    = 32
    frozen    BIT 20 / JR z 7 / LD A,(nn) 13 / DEC A 4 / JR z taken 12                            = 56
    tick      BIT 20 / JR z 7 / LD A,(nn) 13 / DEC A 4 / JR z 7 / DEC (IY+d) 23 / JP p 10         = 84
    tick-end  tick 84 + RES 3,(IY+d) 23                                                            = 107
  a447 head ($A447..$A460, a cached position): LD IX,0 14 / ADD IX,SP 15 / LD A,(IY+7) 19 / AND A 4 /
    JP p 10 / BIT 3,A 8 / JR nz 7 / BIT 6,A 8 / SET 6,(IY+7) 23 / JP z 10                         = 118
  a447 junction ($A5D9..$A5E3): NOP 4 / LD SP,IX 10 / LD HL,nn 10 / DEC (HL) 11 / SET 5,(IY+7) 23  = 58
  a447 gate ($A5E4 .. $A600 or the RET):
    ph1                LD A,(nn) 13 / RRA 4 / JR c taken 12                                        = 29
    ph0 slot 0, b3=0   13 / 4 / JR c 7 / PUSH IY 15 / POP HL 10 / LD DE,nn 10 / OR A 4 / SBC HL,DE 15 /
                       LD A,L 4 / OR H 4 / JR z taken 12 / BIT 3,(IY+d) 20 / RET nz 5               = 123
    ph0 slot 1, b3=0   as slot 0 with JR z 7 / CP n 7 / JR nz 7 for the JR z taken 12              = 132
    ph0 other          13/4/7/15/10/10/4/15/4/4 / JR z 7 / CP n 7 / JR nz taken 12                 = 112
    ph0 slot 0, b3=1   the slot-0 path to BIT 3 (118) / RET nz taken 11                            = 129
    ph0 slot 1, b3=1   138
  so the flash RETURN (head + junction + gate, the erase between) is 118+58+129 = 305 (slot 0) /
  314 (slot 1), and the phase-0 DELTA over ph1 is 123-29 = 94 / 132-29 = 103 / 112-29 = 83.
  ab38 dying ($AB38..$AB5D RET p taken): BIT 2,(IY+d) 20 / JP z 10 / LD A,(nn) 13 / AND n 7 /
    LD HL,nn 10 / JR z taken 12 | JR z 7 + LD HL,nn 10 / LD (IY+0),L 19 / LD (IY+1),H 19 / LD A,(IY+5) 19 /
    AND n 7 / LD (IY+5),A 19 / DEC (IY+4) 23 / RET p taken 11              = 189 ($C6C0) / 194 ($D300)

FORCED (declared, labelled in the rows): 'heart' -- round1_48 with P1 poked invulnerable
(+$5A |= 8, +4 := $30) and ($FED0) := 1 held every frame: the frozen countdown arm ($ABE8 JR z),
which no no-keys run reaches (the heart is an item).
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/respawncost.py [--jobs N]          (-> build/pending/respawncost_fixture.json, N <= 6)
        python tools/respawncost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, Mem, T, PC, IFF, SP, HALT, R
import portconfig as pc
from ab38cost import _fall

FIXTURE = 'build/respawncost_fixture.json'
GLO, GHI = 0xD000, 0xD300                     # never execute the 128K driver range
NATURAL_STATES = ['round1_48', 'round1_2p48', 'play1p48', 'r6_48', 'death']
FRAMES = 1700
FORCED = [('heart', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x08), (0xFD80 + 4, 0x30)),
           ((0xFED0, 1),), 120)]
FORCED_BY = {f[0]: f for f in FORCED}
FORCED_TEXT = {'heart': 'round1_48; P1 +$5A |= 8, +4 := $30; ($FED0) := 1 held every frame; 120 frames'}
KEEP = 2                                      # seeded rows kept per (kind, label, T, forced)
P0, P1S = 0xFD80, 0xFD8A
OPSTATE = {0xA5D9: (0xA5D9,), 0xA480: (0xA480,), 0xA430: (0xA431,)}   # self-modified bytes read as state
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1
A447_MARKS = (0xA461, 0xA5D9, 0xA5E4, 0xA600)
AB38_MARKS = (0x806C, 0xAB70, 0x90C1, 0xABBA)


class Rec:
    __slots__ = ('seed', 'seen', 'post', 'stk', 'rom')

    def __init__(self, sp):
        self.seed = []; self.seen = set(); self.post = {}; self.stk = sp; self.rom = set()


class RecMem(Mem):
    """the harness memory; every open Rec records its first reads (seed) and its writes (post)"""
    __slots__ = ('act', 'regs')

    def __init__(self, base):
        Mem.__init__(self, base.m)
        self.sim = base.sim
        self.act = []; self.regs = None

    def __getitem__(self, i):
        if self.act and type(i) is int:
            p = self.regs[PC]
            if not (p <= i < p + 4):
                for rc in self.act:
                    if i not in rc.seen:
                        rc.seen.add(i)
                        if i < 0x4000:
                            rc.rom.add(i)
                        elif not (rc.stk - 0x40 <= i < rc.stk + 2):
                            rc.seed.append((i, self.m[i]))
        return self.m[i]

    def __setitem__(self, i, v):
        if self.act:
            for rc in self.act:
                rc.seen.add(i)
                if i >= 0x4000 and not (rc.stk - 0x40 <= i < rc.stk + 2):
                    rc.post[i] = v & 0xFF
        Mem.__setitem__(self, i, v)


def _slot(iy):
    return 0 if iy == P0 else 1 if iy == P1S else 'e'


def _y3(y):
    return 0 if (y & 7) == 0 else (1 if (y & 1) else 2)


class Br:
    """one open bracket"""

    def __init__(self, kind, r, raw, rm, iy, f, end_pc=None):
        self.kind = kind; self.t0 = r[T]; self.sp = r[SP]; self.iy = iy; self.f = f
        self.end_pc = end_pc
        self.sig = collections.Counter(); self.marks = {}; self.carry = []
        self.rec = Rec(r[SP]); rm.act.append(self.rec)
        self.inp = {}

    def close(self, r, rm):
        self.T = r[T] - self.t0
        rm.act.remove(self.rec)


def run(name, pokes=(), hold=(), frames=FRAMES):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(name))
    fd, ia = h.frame_duration, h.int_active
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    rm.regs = r
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    for a, v in pokes:
        raw[a] = v(raw[a]) if callable(v) else v
    h.ports.release_all()                     # NO KEYS
    t_start = r[T]; t_end = t_start + frames * fd; nextf = t_start
    isrs, done = [], []
    isr = ab = dc = cnt = pan = None

    while r[T] < t_end or isr is not None:
        if hold and r[T] >= nextf:
            for a, v in hold:
                raw[a] = v
            nextf += fd
        p = r[PC]
        assert not (GLO <= p < GHI), 'ENTERED THE GUARDED RANGE'
        # ---- bracket ends
        if isr is not None and p == isr['ret'] and r[SP] == isr['sp']:
            isr['T'] = r[T] - isr['t0']; isr = None
        if cnt is not None and p == 0xABF4:
            cnt.close(r, rm); done.append(cnt); cnt = None
        if pan is not None and p == 0xAB70:
            pan.close(r, rm); done.append(pan); pan = None
        if ab is not None and r[SP] == (ab.sp + 2) & 0xFFFF:
            assert cnt is None and pan is None
            ab.close(r, rm)
            if ab.inp['f5a'] & 0x04:
                done.append(ab)
            ab = None
        if dc is not None and p == 0xA405 and r[SP] == (dc.sp + 2) & 0xFFFF:
            dc.close(r, rm); done.append(dc); dc = None
        # ---- bracket starts
        if p == 0xAB38 and ab is None and isr is not None:
            iy = h.iy(); assert iy in (P0, P1S), 'IY $%04X' % iy
            ab = Br('ab38', r, raw, rm, iy, isr['f'])
            ab.inp = {'f5a': raw[iy + 0x5A], 'aa57': raw[0xAA57]}
            isr['ab'].append(ab)
        if p == 0xABDE and ab is not None:
            cnt = Br('count', r, raw, rm, ab.iy, ab.f)
        if p == 0x806C and ab is not None and pan is None:
            pan = Br('panel', r, raw, rm, ab.iy, ab.f)
        if p == 0xA447 and dc is None and isr is not None:
            sp = r[SP]
            if raw[sp] | (raw[(sp + 1) & 0xFFFF] << 8) == 0xA405:
                iy = h.iy()
                dc = Br('a447', r, raw, rm, iy, isr['f'])
                dc.inp = {'f7': raw[iy + 7], 'c2': raw[iy + 2], 'y': raw[iy + 6], 'tog': raw[0xA3B2] & 1,
                          'b3': (raw[iy + 0x5A] >> 3) & 1 if iy in (P0, P1S) else 0}
        opn = [b for b in (ab, cnt, pan, dc) if b is not None]
        if opn:
            if p in OPSTATE:
                for a in OPSTATE[p]:
                    for b in opn:
                        rc = b.rec
                        if a not in rc.seen:
                            rc.seen.add(a); rc.seed.append((a, raw[a]))
            for b in opn:
                if b.kind == 'a447' and p in A447_MARKS and p not in b.marks:
                    b.marks[p] = r[T]
                elif b.kind == 'ab38' and p in AB38_MARKS and p not in b.marks:
                    b.marks[p] = r[T]
        # ---- execute, and take the interrupt
        o = raw[p]
        if o == 0x76 and r[IFF]:
            assert not opn, 'HALT inside a bracket'
            t = r[T]
            if t % fd >= ia:
                nt = (t // fd + 1) * fd
                sk = (nt - t) // 4
                r[T] = nt; r[R] = (r[R] & 0x80) | ((r[R] + sk) & 0x7F)
            r[PC] = (p + 1) & 0xFFFF; r[HALT] = 0
            ta, spa = r[T], r[SP]
            if h.sim.accept_interrupt(r, rm, p):
                assert isr is None
                isr = _isr(ta, spa, (p + 1) & 0xFFFF, raw, t_start, fd); isrs.append(isr)
            continue
        op[o]()
        if opn and COND[o]:
            oc = 'f' if r[PC] == _fall(raw, p) else 't'
            for b in opn:
                b.sig[(p, oc)] += 1
                if p == 0xA435 and oc == 'f':
                    b.carry.append(r[T])
        if r[IFF] and r[T] % fd < ia:
            ta, spa, rp = r[T], r[SP], r[PC]
            if h.sim.accept_interrupt(r, rm, p):
                assert not opn and isr is None, 'an interrupt inside a bracket'
                isr = _isr(ta, spa, rp, raw, t_start, fd); isrs.append(isr)
    return isrs, done


def _isr(ta, spa, rp, raw, t0, fd):
    return {'t0': ta, 'sp': spa, 'ret': rp, 'f': (ta - t0) // fd,
            'p1': raw[P0 + 0x5A], 'p2': raw[P1S + 0x5A], 'ab': []}


# ------------------------------------------------------------------ labels, by the machine's own branches
def _o(b, pc):
    """the outcome of the conditional at pc in the bracket: 't', 'f', or None (not executed)"""
    t, f = b.sig.get((pc, 't'), 0), b.sig.get((pc, 'f'), 0)
    assert not (t and f), 'two outcomes at $%04X' % pc
    return 't' if t else 'f' if f else None


def label_a447(b):
    out = []
    if _o(b, 0xA451) == 't':
        out.append('skip-b7')
    elif _o(b, 0xA456) == 't':
        out.append('skip-b3')
    elif _o(b, 0xA45E) == 't':
        out.append('first')
    elif _o(b, 0xA466) == 't':
        out.append('high')
    else:
        out.append('erase%s%d' % ('S' if _o(b, 0xA480) == 't' else 'A', _y3(b.inp['c2'])))
    if 0xA5E4 in b.marks:
        out.append('ph1' if _o(b, 0xA5E8) == 't' else 'ph0')
        if b.inp['b3']:
            out.append('b3')
        if _o(b, 0xA5FF) == 't':
            out.append('flash-return')
        elif 0xA600 in b.marks:
            out.append('draw%s%d' % ('S' if _o(b, 0xA611) == 't' else 'A', 1 if b.inp['y'] & 7 else 0))
    elif 0xA5D9 in b.marks:
        out.append('junction-ret')
    if b.carry:
        out.append('+c%d' % len(b.carry))
    return 'slot%s %s' % (_slot(b.iy), ' '.join(out))


def segs_a447(b):
    """T between the marks; a segment's carries counted into its key"""
    m = b.marks; end = b.t0 + b.T
    pts = [('head', b.t0)] + [(n, m[q]) for n, q in (('erase', 0xA461), ('junction', 0xA5D9),
                                                      ('gate', 0xA5E4), ('draw', 0xA600)) if q in m]
    out = {}
    for i, (n, t0) in enumerate(pts):
        t1 = pts[i + 1][1] if i + 1 < len(pts) else end
        out[n] = [t1 - t0, sum(1 for c in b.carry if t0 <= c < t1)]
    return out


def seg_key_a447(b, name, nc):
    s = 'slot%s' % _slot(b.iy)
    if name == 'head':
        k = label_a447(b).split()[1]
        k = k if not k.startswith('erase') else 'cached'
    elif name == 'erase':
        k = [w for w in label_a447(b).split() if w.startswith('erase')][0]
    elif name == 'junction':
        k = ''
    elif name == 'gate':
        k = '%s ph%d b3=%d' % (s, b.inp['tog'], b.inp['b3'])
    else:
        k = [w for w in label_a447(b).split() if w.startswith('draw')][0]
    return ('a447 %s %s%s' % (name, k, ' +c%d' % nc if nc else '')).rstrip()


def label_ab38(b):
    spr = 'sprD300' if _o(b, 0xAB47) == 'f' else 'sprC6C0'
    if _o(b, 0xAB5D) == 't':
        return 'dying ' + spr
    arm = 'respawn' if _o(b, 0xAB61) == 't' else 'final'
    n = ((b.inp['aa57'] - 2) & 0xFF) or 256
    return '%s %s r80%d p%d calm%d' % (arm, spr, 1 if _o(b, 0xAB7B) == 'f' else 0,
                                       2 if _o(b, 0xABC1) == 't' else 1, n)


def segs_ab38(b):
    m = b.marks
    if 0x806C not in m:
        return {}
    end = b.t0 + b.T
    return {'head': m[0x806C] - b.t0, 'panel': m[0xAB70] - m[0x806C], 'mid': m[0x90C1] - m[0xAB70],
            'calm': m[0xABBA] - m[0x90C1], 'tail': end - m[0xABBA]}


def label_count(b):
    if _o(b, 0xABE2) == 't': return 'off'
    if _o(b, 0xABE8) == 't': return 'frozen'
    return 'tick' if _o(b, 0xABED) == 't' else 'tick-end'


def sigstr(b):
    return ' '.join('%04x%s*%d' % (q, c, n) for (q, c), n in sorted(b.sig.items()))


def label(b):
    if b.kind == 'a447': return label_a447(b)
    if b.kind == 'ab38': return 'slot%d %s' % (_slot(b.iy), label_ab38(b))
    if b.kind == 'count': return 'slot%d %s' % (_slot(b.iy), label_count(b))
    return 'slot%d %s' % (_slot(b.iy), sigstr(b))


def row(b, lab, tag):
    rc = b.rec
    rom = sorted(rc.rom)
    post = sorted(rc.post.items())
    blind = [a for a, _ in post if a < 0x5800] if rom else []
    if rom:
        post = [(a, v) for a, v in post if a >= 0x5800]
    out = {'run': tag, 'kind': b.kind, 'label': lab, 'T': b.T, 'f': b.f, 'iy': '%04X' % b.iy, 'slot': _slot(b.iy),
           'sig': sigstr(b),
           'seed': ''.join('%04x%02x' % (a, v) for a, v in sorted(rc.seed)),
           'rom': ' '.join('%04x' % a for a in rom),
           'post': ''.join('%04x%02x' % (a, v) for a, v in post),
           'blind': ' '.join('%04x' % a for a in blind)}
    if b.kind == 'a447':
        out['seg'] = segs_a447(b)
    elif b.kind == 'ab38':
        out['seg'] = segs_ab38(b)
    return out


def one(job):
    tag, name, frames = job
    f = FORCED_BY.get(tag)
    pokes, hold = (f[2], f[3]) if f else ((), ())
    isrs, done = run(name, pokes, hold, frames)
    terms, segs = collections.Counter(), collections.Counter()
    kept, rows = collections.Counter(), []
    for b in done:
        lab = label(b)
        terms[(b.kind + ' ' + lab, b.T)] += 1
        if b.kind == 'a447':
            for n, (t, nc) in segs_a447(b).items():
                segs[(seg_key_a447(b, n, nc), t)] += 1
        elif b.kind == 'ab38':
            for n, t in segs_ab38(b).items():
                segs[('ab38 %s %s' % (n, label_ab38(b).split()[0]), t)] += 1
        key = (b.kind, lab, b.T)
        if kept[key] < KEEP:
            kept[key] += 1
            rows.append(row(b, lab, tag))
    # the ISR context: frames with a player dying / invulnerable, and the respawn frames' ISR T
    live = sum(1 for s in isrs if 'T' in s and (s['p1'] | s['p2']) & 0x0C)
    bit3 = sum(1 for s in isrs if 'T' in s and (s['p1'] | s['p2']) & 0x08)
    resp, prev = [], None
    for s in isrs:
        if 'T' not in s: continue
        if any(a.kind == 'ab38' and hasattr(a, 'T') and a.inp['f5a'] & 4 and 0x806C in a.marks for a in s['ab']):
            resp.append([s['f'], s['T'], prev])
        if s['ab']:
            prev = s['T']
    return {'run': tag, 'state': name, 'forced': tag != name, 'frames': frames,
            'terms': [[k, t, n] for (k, t), n in terms.items()],
            'segs': [[k, t, n] for (k, t), n in segs.items()],
            'isr': {'dying_or_invuln_frames': live, 'bit3_frames': bit3, 'respawn_or_final': resp},
            'rows': rows}


def _merge(res, field):
    acc = collections.defaultdict(lambda: collections.Counter())
    for R_ in res:
        for k, t, n in R_[field]:
            acc[k][(t, 1 if R_['forced'] else 0)] += n
    out = {}
    for k in sorted(acc):
        ts = sorted({t for t, _ in acc[k]})
        out[k] = [[t, acc[k][(t, 0)], acc[k][(t, 1)]] for t in ts]
    return out


def measure(jobs):
    work = [(s, s, FRAMES) for s in NATURAL_STATES] + [(f[0], f[1], f[4]) for f in FORCED]
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(one, work)
    rows, kept = [], collections.Counter()
    for R_ in res:
        for x in R_['rows']:
            key = (x['kind'], x['label'], x['T'], R_['forced'])
            if kept[key] < KEEP:
                kept[key] += 1
                x['forced'] = R_['forced']
                rows.append(x)
    for x in rows:
        assert all(int(x['seed'][i:i + 4], 16) >= 0x4000 for i in range(0, len(x['seed']), 6)), 'ROM in a seed'
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'states': NATURAL_STATES, 'forced': FORCED_TEXT,
            'keep': KEEP,
            'terms_shape': 'key -> [[T, natural count, forced count], ...]',
            'terms': _merge(res, 'terms'), 'segs': _merge(res, 'segs'),
            'isr': {R_['run']: R_['isr'] for R_ in res},
            'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    F = json.loads(json.dumps(measure(jobs)))
    for k, v in F['terms'].items():
        if not k.startswith('panel'):
            print('%-50s %s' % (k, v[:10]))
    for k, v in F['segs'].items():
        print('  seg %-46s %s' % (k, v[:10]))
    print('rows', len(F['rows']), collections.Counter(x['kind'] for x in F['rows']))
    print('isr', F['isr'])
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as fh:
        json.dump(F, fh, separators=(',', ':'))
    print('wrote', FIXTURE)


if __name__ == '__main__':
    main()
