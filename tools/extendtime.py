# -*- coding: utf-8 -*-
"""M7.57 -- $94C2's EXTEND COMPLETION, WRITE BY WRITE: where every byte of the 4.9-second cutscene
lands in main-loop T, and what the frame interrupts do while it is up.

extcomp.py (M7.25) measured WHAT $94C2 writes and how long it takes; it does not say WHEN inside it
a byte is written, and the port ran the whole of it -- and the round advance after it -- inside
ONE call, so the page never showed any of it.  On the machine the playfield is repainted from the
wiped shadow, ten rows of fruit fill the screen, "N I C E   n P" goes up, the extra life appears
~120 frames later and the round advances ~112 frames after that; both ISR gates are CLOSED for all
of it ($94CD/$94D0, under DI).  This oracle records:

  direct     $94C2 armed with IX on the player, interrupts OFF, to $8D09 (its JP).  EXACT: a plain
             Simulator with fast_djnz / fast_ldir OFF and no contention, so every instruction --
             every LDIR iteration -- is its own T stamp.  Every write outside the stack, in order,
             as [T from $94C2, address, writer PC, value] -- or, when the value came out of the
             SPECTRUM ROM, [T, address, writer PC, None, code, row]: never the byte.  A write is
             ROM-fed when its PC is a known glyph writer, or when its value equals a ROM byte read
             within the last ROM_WINDOW instructions; both rules are applied and must agree.
             VARIANTS, each on extcomp with one thing changed: which player completes, the round
             (two digits, 81), the other player's letters, a two-player panel, the lives cap,
             fifteen world items and the power-up slot, the item-age tick, the flood, the storm.
             The three uniform bulk segments (the wipe, the repaint, the attribute copy) are kept
             write by write for 'base' only and summarised for the others.
  contended  the harness's own simulator, 'base', at PHASES frame phases: the events only -- the
             anchors contention moves.
  natural    interrupts ON, contended: extcomp with the sixth letter and ($FED5) poked in after
             `lead` T (sixteen leads: the entry phase), run to the chain's $948F, then $948F..$8D09 bracketed -- every ISR (the
             main loop's T at it, $8D72..RET, the gates, the parity), the MAIN-LINE T of every event
             (wall T less the ISRs before it), and a RAM diff across every ISR, which must change NO
             byte the block's main line READS (the run-ahead premise the port rests on).  The first
             natural run keeps every write's main-line T.

NO ROM BYTE IS STORED.  GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/extendtime.py capture [--jobs N]   -> build/extendtime_fixture.json
        python tools/extendtime.py verify  [--jobs N]   re-run and diff against the fixture
        python tools/extendtime.py direct|contended|natural
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import hurryblock as HB                  # its Mem / port hooks and its Tracer (EVT, CHAIN swapped)
import harness
from harness import Harness, PC, T, SP, IFF, IXh, IXl, A, B
from skoolkit.simulator import Simulator
import portconfig as pc

FIXTURE = 'build/extendtime_fixture.json'
FRAME_T = 69888
PHASES = [k * (FRAME_T // 16) for k in range(16)]
STATE = 'extcomp'
DONE, ENTRY, END = 0x948F, 0x94C2, 0x8D09
PLAYERS = (0xFD80, 0xFD8A)
LETTERS = (0xFDE3, 0xFDED)               # (IX+$63)
TRIGGER = 0xFED5
ROMW = {0x8065, 0x8067, 0x7FB5, 0x95C3, 0x95C6}   # writers whose value is a ROM glyph row
ROM_WINDOW = 6
# the operand patches the port does not write, DECLARED: $A2C2's NOP pair and $A304 and their
# restores (the item blit), and $A314's three (the item erase) -- excluded from every list, counted
UNMODELLED = {0xA2C3, 0xA2C6, 0xA2F1, 0xA2CE, 0xA2D1, 0xA31A, 0xA323, 0xA32A}
HOOK_EV = ('entry', 'wipe', 'stride2', 'res7', 'repaint', 'digits', 'derive', 'panel', 'lives', 'items',
           'double', 'runs', 'award', 'gate_on')
DIGEST_ONLY = ('wipe', 'repaint')        # base's two bulk routines: their digest, not their list
KEEP_PASSES = 1                          # a variant's differing item passes stored write by write
LEADS = tuple(k * 12345 for k in range(16))   # natural runs: T before the poke (extcomp clears its
                                         # round ~7 frames in, so all of them inside 2.9 frames)

# the block's main-line events: every routine it calls, its own landmarks, and the delay loops
EVT = {0x948F: 'done', 0x94C2: 'entry', 0x94EA: 'wipe', 0x94F6: 'stride2', 0x8C14: 'res7', 0x8C28: 'reveal',
       0x8216: 'repaint', 0x823C: 'attrcopy', 0x7F80: 'digits', 0x8C2B: 'derive', 0x957E: 'panel',
       0x806C: 'lives', 0x8C4D: 'out', 0x9503: 'panel2', 0x9506: 'shower', 0x950F: 'rec', 0x8689: 'items',
       0x86A9: 'entry_item', 0x9537: 'lives2', 0x953F: 'banner', 0x801D: 'double', 0x994F: 'runs',
       0x9553: 'delay1', 0x9556: 'award', 0x955B: 'lives3', 0x955E: 'delay2', 0x9561: 'spin',
       0x956A: 'pops', 0x956C: 'gate_on', 0x8D09: 'advance', 0x8E05: 'mute3', 0x8E0A: 'mute2',
       0x873E: 'rng'}
RNGW = (0x8742, 0x876A)                  # the ink store and its four cells, after $873E LD A,R
HB.EVT = EVT
HB.CHAIN = {}


class Fail(Exception):
    pass


# ---------------------------------------------------------------- the ROM reads and the main line's READS
ROMRD = [None, None, 0]                  # the last ROM read: address, value, instruction count
NSTEP = [0]
READS = None                             # the addresses the block's main line reads, while a set
TRC = None                               # the tracer whose in_isr says main line or ISR
_hb_get = harness.Mem.__getitem__


def _getitem(self, i):
    v = _hb_get(self, i)
    if i < 0x4000:
        ROMRD[0], ROMRD[1], ROMRD[2] = i, v, NSTEP[0]
    if READS is not None and TRC is not None and TRC.in_isr is None:
        READS.add(i)
    return v


harness.Mem.__getitem__ = _getitem


class XTracer(HB.Tracer):
    """HB.Tracer with every write kept: [T, address, writer PC, value, isr] -- or, ROM-fed,
    [T, address, writer PC, None, isr, code, row]; the instruction count is kept for the ROM rule"""

    def __init__(self, h, t0):
        HB.Tracer.__init__(self, h, t0)
        self.romfed_pcs, self.disagree = set(), []
        _orig = h.sim.opcodes

    def classify(self, tw, pw, a, v):
        t = tw - self.t0
        isr = 1 if self.in_isr is not None else 0
        sp = self.h.sim.registers[SP]
        if not (0x4000 <= a < 0x5B00) and sp - 64 <= a < sp + 64:
            return                                      # the stack
        dyn = (ROMRD[0] is not None and 0x3C00 <= ROMRD[0] < 0x4000 and v == ROMRD[1] and
               NSTEP[0] - ROMRD[2] <= ROM_WINDOW and not isr)
        if dyn:
            self.romfed_pcs.add(pw)
        if (pw in ROMW) != dyn and not (pw in ROMW and v == 0):
            # a known glyph writer storing a blank row is not flagged by value; anything else is a
            # disagreement and the run fails below unless the writer is added to ROMW
            self.disagree.append('%04X' % pw)
        if pw in ROMW or dyn:
            s = ROMRD[0] - 0x3C00
            self.writes.append([t, a, pw, None, isr, s // 8, s % 8])
        elif pw in RNGW and not isr and self.rng_entry():
            self.writes.append([t, a, pw, None, isr, 'r'])      # the value is the R register's
        else:
            self.writes.append([t, a, pw, v, isr])

    def rng_entry(self):
        """inside an item entry that took $873E's LD A,R -- the last of the two events is 'rng'"""
        for t, tag in reversed(self.events):
            if tag in ('rng', 'entry_item', 'items'):
                return tag == 'rng'
        return False


def count_steps(h):
    """wrap the simulator's opcode table so NSTEP counts instructions (the ROM rule's window)"""
    ops = h.sim.opcodes
    if getattr(h, '_counted', False):
        return
    regs = h.sim.registers
    h.waits = []                                 # (A, B) at every $9573 entry -- the busy wait's counts
    new = []
    for f in ops:
        def g(f=f):
            NSTEP[0] += 1
            if regs[PC] == 0x9573:
                h.waits.append([regs[A], regs[B]])
            return f()
        new.append(g)
    h.sim.opcodes = new
    h._counted = True


# ---------------------------------------------------------------- worlds
def items_world(m, phase_of=None):
    """fifteen world items in slots 16..30 -- every type 0..14, X across the width, Y from the top
    rows (the ROM-dropped band) to the floor -- and a power-up in the slot at $9603"""
    for k in range(15):
        x = (k * 0x10 + 0x08) & 0xF0
        y = [0x00, 0x08, 0x10, 0x28, 0x40, 0x58, 0x70, 0x88, 0xA0, 0xB0, 0x30, 0x60, 0x90, 0x18, 0x48][k]
        ph = phase_of(k) if phase_of else 0
        m[0x9625 + 2 * k] = x | k
        m[0x9626 + 2 * k] = y | ph
    m[0x9603] = 0x70 | 10                      # type 10: the power-up ink table's $FF, the RNG ink
    m[0x9604] = 0x98 | 1


VARIANTS = {
    'base': (0, None),
    'p2': (1, None),
    'r23': (0, lambda m: m.__setitem__(0x8609, 23)),
    'r81': (0, lambda m: m.__setitem__(0x8609, 0x51)),
    'letters': (0, lambda m: m.__setitem__(0xFDED, 0x2B)),
    'twop': (0, lambda m: [m.__setitem__(0xFD91, 0xE0), m.__setitem__(0xFDE6, 3), m.__setitem__(0xFDED, 0x15)]),
    'lives': (0, lambda m: m.__setitem__(0xFDDC, 7)),
    'lives0': (0, lambda m: m.__setitem__(0xFDDC, 0)),
    'r45': (0, lambda m: m.__setitem__(0x8609, 45)),
    'r67': (0, lambda m: m.__setitem__(0x8609, 67)),
    'p2letters': (1, lambda m: m.__setitem__(0xFDE3, 0x1E)),
    'p1out': (1, lambda m: [m.__setitem__(0xFD87, 0x61), m.__setitem__(0xFD91, 0xE0), m.__setitem__(0xFDE6, 2)]),
    'items': (0, lambda m: items_world(m)),
    # the tick with a mask that is not $FF: $0F AND $F0 is zero, so $86D1 falls through
    'tick': (0, lambda m: [m.__setitem__(0x86CD, 0x0F), m.__setitem__(0x86CF, 0xF0),
                           items_world(m, lambda k: (3, 0, 6, 2)[k % 4])]),
    'heart': (0, lambda m: [m.__setitem__(0x86CD, 0), m.__setitem__(0xFED1, 1),
                            items_world(m, lambda k: (3, 0, 6, 2)[k % 4])]),
    'tickflood': (0, lambda m: [m.__setitem__(0x86CD, 0), m.__setitem__(0xFECE, 1),
                                items_world(m, lambda k: (3, 0, 6, 2)[k % 4])]),
    'lives5': (0, lambda m: m.__setitem__(0xFDDC, 5)),
    'paper4': (0, lambda m: m.__setitem__(0x8309, 0x20 | 7)),
    'flood': (0, lambda m: [m.__setitem__(0xFECE, 1), items_world(m)]),
    'storm': (0, lambda m: [m.__setitem__(0xFECF, 1), items_world(m)]),
}


def world(who, exact=False, contended=True, poke=None):
    """extcomp with player `who` holding all six letters (the other none); EXACT is a plain
    Simulator with fast_djnz and fast_ldir OFF and no contention"""
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(STATE))
    m = h.memobj.m
    if m[0x8DC4] != 0xC9:
        raise Fail('%s: not the 48K branch (TRAPS #28)' % STATE)
    m[LETTERS[0]] = 0
    m[LETTERS[1]] = 0
    m[LETTERS[who]] = 0x3F
    if poke:
        poke(m)
    if exact:
        regs = list(h.sim.registers)
        sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
        sim.registers[:] = regs
        h.sim = sim
        h.memobj.sim = sim
        sim.set_tracer(h.ports)
        h.frame_duration, h.int_active = sim.frame_duration, sim.int_active
    count_steps(h)
    return h, m


def arm(h, addr, ix):
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    r[PC] = addr
    r[IXh], r[IXl] = ix >> 8, ix & 0xFF


def seed_of(m):
    """what the block's writes depend on in the world, for a port world to copy (data only)"""
    return {'round': m[0x8609],
            'players': [[m[ix + 7], m[ix + 0x5A], m[ix + 0x5C], m[ix + 0x63]] for ix in PLAYERS],
            'items': [m[a] for a in range(0x9603, 0x9643)],
            'prng': [m[0xFE86], m[0xFE87]],
            'tick': [m[0x86CD], m[0x86CF]], 'fed1': m[0xFED1], 'fece': m[0xFECE], 'fecf': m[0xFECF],
            'fecb': m[0xFECB], 'tilebuf': [m[a] for a in range(0x856C, 0x8584)],
            'palette': [m[0x8309], m[0x830A], m[0x5AC0]],
            'res7': [m[0xFD9B + 10 * i] for i in range(7)] + [m[0xFEDF + 10 * i] for i in range(12)],
            'spin': m[0x861C]}


def timeline(events, spins):
    """the port's hooks with the machine's T of each: the routine entries, the first $950F of each
    records loop, $8C4C (the EI before $8C4D) for the OUT, the first $9561 for the spin"""
    out, prev = [], False
    for t, tag in events:
        if tag == 'rec':
            if not prev:
                out.append(['records', t])
            prev = True
            continue
        prev = False
        if tag == 'out':
            out.append(['out', t - 4])
        elif tag in HOOK_EV:
            out.append([tag, t])
    out.append(['spin', spins[0]])
    out.sort(key=lambda x: x[1])
    return out


def canon(w, t0):
    """one write as the digest reads it: address, value (or ROM glyph, or r for the R register's),
    T from its hook"""
    if w[3] is None and w[5] == 'r':
        return '%d:r@%d;' % (w[1], w[0] - t0)
    if w[3] is None:
        return '%d:g%d.%d@%d;' % (w[1], w[5], w[6], w[0] - t0)
    return '%d:%d@%d;' % (w[1], w[3], w[0] - t0)


def split(tl, ws, cost):
    """each write into the routine instance whose hook it follows"""
    bounds = [x[1] for x in tl] + [cost + 1]
    inst = [[] for _ in tl]
    k = 0
    for w in ws:
        while w[0] >= bounds[k + 1]:
            k += 1
        inst[k].append(w)
    return inst


def full_of(ws, t0):
    """an instance write by write: T from its hook DELTA-coded, address, value (-1 ROM-fed), and
    the ROM-fed ones' (index, code, row)"""
    ts = [w[0] - t0 for w in ws]
    return {'t': [ts[0]] + [b - a for a, b in zip(ts, ts[1:])] if ts else [], 'a': [w[1] for w in ws],
            'v': [w[3] if w[3] is not None else (-2 if w[5] == 'r' else -1) for w in ws],
            'g': [[j, w[5], w[6]] for j, w in enumerate(ws) if w[3] is None and w[5] != 'r']}


def segs_of(events, cost):
    """[tag, start, end] for every segment the item entries and records do not split"""
    s = [e for e in events if e[1] not in ('entry_item', 'rec', 'spin')]
    return [[e[1], e[0], (s[k + 1][0] if k + 1 < len(s) else cost)] for k, e in enumerate(s)]


# ---------------------------------------------------------------- direct
def one_direct(args):
    name, exact, phase = args
    who, poke = VARIANTS[name]
    h, m = world(who, exact=exact, poke=poke)
    r = h.sim.registers
    arm(h, ENTRY, PLAYERS[who])
    r[IFF] = 0
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    seed = seed_of(m)
    tr = XTracer(h, r[T])
    stop = tr.run({END} | HB.GUARD, limit=3 * 10 ** 6, interrupts=False)
    if stop != END:
        raise Fail('direct %s: stopped at $%04X' % (name, stop))
    if tr.disagree:
        raise Fail('direct %s: the two ROM rules disagree at %s (ROM-fed writers %s)' % (
            name, sorted(set(tr.disagree)), sorted('%04X' % p for p in tr.romfed_pcs)))
    cost = r[T] - tr.t0
    ev = tr.events
    segs = segs_of(ev, cost)
    out = {'name': name, 'who': who, 'exact': exact, 'phase': phase, 'cost': cost, 'seed': seed,
           'events': [e for e in ev if e[1] != 'spin'], 'spins': [e[0] for e in ev if e[1] == 'spin'],
           'romfed': sorted('%04X' % p for p in tr.romfed_pcs), 'waits': h.waits}
    tl = timeline(ev, out['spins'])
    out['timeline'] = tl
    if not exact:
        return {'phase': phase, 'cost': cost, 'timeline': tl}
    ws = [w for w in tr.writes if w[2] not in UNMODELLED]
    out['unmodelled'] = len(tr.writes) - len(ws)
    inst = split(tl, ws, cost)
    out['n'] = [len(x) for x in inst]
    out['digest'] = [hashlib.sha1(''.join(canon(w, tl[k][1]) for w in x).encode()).hexdigest()[:16]
                     for k, x in enumerate(inst)]
    out['rng'] = {str(k): [j for j, w in enumerate(x) if w[3] is None and w[5] == 'r']
                  for k, x in enumerate(inst) if any(w[3] is None and w[5] == 'r' for w in x)}
    out['_inst'] = inst
    del out['events']
    return out


def phase_direct(jobs=8):
    names = list(VARIANTS)
    with ProcessPoolExecutor(max_workers=min(jobs, len(names))) as ex:
        res = dict(zip(names, ex.map(one_direct, [(n, True, None) for n in names])))
    base = res['base']
    for name, x in res.items():
        inst, tl = x.pop('_inst'), x['timeline']
        full, passes = {}, 0
        for k, ws in enumerate(inst):
            romfed = any(w[3] is None and w[5] != 'r' for w in ws)
            if name == 'base':
                keep = tl[k][0] not in DIGEST_ONLY
            else:
                differs = x['digest'][k] != base['digest'][k] or tl[k][0] != base['timeline'][k][0]
                keep = romfed or (differs and (tl[k][0] != 'items' or passes < KEEP_PASSES))
                if differs and tl[k][0] == 'items':
                    passes += 1
            if romfed and not keep:
                raise Fail('%s: instance %d (%s) has ROM-fed writes and no list' % (name, k, tl[k][0]))
            if keep:
                full[str(k)] = full_of(ws, tl[k][1])
        x['full'] = full
        print('direct EXACT %-9s P%d: cost %d, %d writes (%d unmodelled), %d hooks, %d instances in full, '
              'waits (A,B) %s, ROM-fed writers %s' % (name, x['who'] + 1, x['cost'], sum(x['n']),
                                                     x['unmodelled'], len(tl), len(full), x['waits'], x['romfed']))
    return res


def phase_contended(jobs=8):
    with ProcessPoolExecutor(max_workers=min(jobs, len(PHASES))) as ex:
        res = list(ex.map(one_direct, [('base', False, ph) for ph in PHASES]))
    for x in res:
        print('   CONTENDED base phase %5d: cost %d, $9556 at %s' % (
            x['phase'], x['cost'], [h[1] for h in x['timeline'] if h[0] == 'award']))
    return res


# ---------------------------------------------------------------- natural
def main_of(t, isrs):
    """wall T from $948F -> main-line T: less every ISR that ended at or before it"""
    return t - sum(x[2] - x[0] for x in isrs if x[2] <= t)


def to_done(lead):
    """extcomp, interrupts ON, `lead` T, then the sixth letter and the trigger; on to the chain's
    $948F through the machine's own frames"""
    h, m = world(0)
    m[LETTERS[0]] = 0x3E                                    # extcomp's own five, until the poke
    r = h.sim.registers
    fd = h.frame_duration
    t_end = r[T] + lead
    if lead:
        why, n = h.run_until(HB.GUARD, limit=10 ** 7, interrupts=True, stride=64,
                             predicate=lambda hh: hh.sim.registers[T] >= t_end)
        if r[PC] in HB.GUARD or r[T] < t_end:
            raise Fail('lead %d: stopped at $%04X (%s)' % (lead, r[PC], why))
    m[LETTERS[0]] = 0x3F
    m[TRIGGER] = 1
    t_give_up = r[T] + 5 * fd
    while r[PC] != DONE:
        h.step(1, interrupts=True)
        if r[PC] in HB.GUARD:
            raise Fail('guard at $%04X' % r[PC])
        if r[T] > t_give_up:
            raise Fail('$948F not reached within five frames (PC $%04X)' % r[PC])
    return h, m


def one_natural(args):
    global READS, TRC
    lead, phase, keep = args
    h, m = to_done(lead)
    r = h.sim.registers
    if phase is not None:
        # the entry phase FORCED at $948F: the interrupts that follow come where they would had the
        # main line reached $948F there -- the unforced leads reach only four phases (a pass
        # reaches $948F at much the same point of every frame), and the unforced runs are kept as
        # the check that forcing reproduces them
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    t0 = r[T]
    seed = seed_of(m)
    tr = XTracer(h, t0)
    READS, TRC = set(), tr
    try:
        stop = tr.run({END} | HB.GUARD, limit=4 * 10 ** 6, interrupts=True, snap_isr=True)
    finally:
        reads, READS, TRC = READS, None, None
    if stop != END:
        raise Fail('natural lead %d: stopped at $%04X' % (lead, stop))
    isrs = tr.isrs
    ev = tr.events
    tend = r[T] - t0
    ws = [w for w in tr.writes if not w[4]]
    own = set(w[1] for w in ws)
    mws = [w for w in ws if w[2] not in UNMODELLED]     # (from $94C2 on: $948F's two stores are the chain's)
    rows, violations, other = [], set(), set()
    for x in isrs:
        sp = x[6]
        diff = x[7]
        rest = [a for a in diff if not (sp - 64 <= a < sp + 2) and a not in own]
        other.update(a for a in rest if a not in HB.COUNTERS)
        violations.update(a for a in rest if a in reads)
        rows.append([main_of(x[0], isrs), x[2] - x[0], x[3], x[4], x[5], x[1]])
    # every main-line T from $94C2's entry, the port's clock for the block (entry_main is $948F's
    # 83-odd T before it)
    tl = timeline(ev, [e[0] for e in ev if e[1] == 'spin'])
    e0 = main_of(tl[0][1], isrs)
    mws = [w for w in mws if w[0] >= tl[0][1]]
    out = {'lead': lead, 'forced': phase is not None, 't0_phase': t0 % FRAME_T, 'seed': seed,
           'entry_main': e0, 'hooks': [[x[0], main_of(x[1], isrs) - e0] for x in tl],
           'n_isrs': len(rows), 'isr_costs': sorted(set(x[1] for x in rows)),
           'isr_gates': sorted(set((x[2], x[3]) for x in rows)), 'parities': ''.join(str(x[4]) for x in rows),
           'end_main': main_of(tend, isrs) - e0, 'end_wall': tend,
           'premise_violations': ['%04X' % a for a in sorted(violations)],
           'isr_other': ['%04X' % a for a in sorted(other)],
           'reads': len(reads), 'n_writes': len(mws), 'unmodelled': len(ws) - len(mws)}
    if keep or rows[0][2] or rows[0][3]:           # the kept run, and an ISR inside the entry window
        out['isrs'] = [[x[0] - e0] + x[1:] for x in rows]
    if keep:
        tm = [main_of(w[0], isrs) - e0 for w in mws]
        out['t_main'] = [tm[0]] + [b - a for a, b in zip(tm, tm[1:])]
    first_closed = next((k for k, x in enumerate(rows) if x[2] == 0 and x[3] == 0), None)
    print('natural lead %6d: $948F %5d T into its frame; %d ISRs, gates %s, first shut at #%s; $8D72..RET %s; '
          'main-line end %d; premise violations %s (of %d read); ISR writes outside counters/stack %s' % (
              lead, out['t0_phase'], len(rows), sorted(set((x[2], x[3]) for x in rows)), first_closed,
              sorted(set(x[1] for x in rows)), out['end_main'], out['premise_violations'], len(reads),
              out['isr_other']))
    return out


def phase_natural(jobs=8):
    jl = [(ld, None, False) for k, ld in enumerate(LEADS)] + [(0, ph, ph == PHASES[8]) for ph in PHASES]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jl))) as ex:
        res = list(ex.map(one_natural, jl))
    free, seen = [], set()
    for x in res[:len(LEADS)]:                 # the unforced leads, one run per distinct entry phase
        if x['t0_phase'] not in seen:
            seen.add(x['t0_phase'])
            free.append(x)
    return {'free': free, 'forced': res[len(LEADS):]}


# ---------------------------------------------------------------- main
def capture(jobs=8):
    return {'meta': {'frame_t': FRAME_T, 'entry': '94C2', 'end': '8D09', 'state': STATE,
                     'variants': list(VARIANTS), 'digest_only': list(DIGEST_ONLY), 'keep_passes': KEEP_PASSES,
                     'unmodelled': ['%04X' % p for p in sorted(UNMODELLED)], 'phases': PHASES, 'leads': list(LEADS)},
            'direct': phase_direct(jobs), 'contended': phase_contended(jobs), 'natural': phase_natural(jobs)}


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
    elif cmd == 'contended':
        phase_contended(jobs)
    elif cmd == 'natural':
        phase_natural(jobs)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
