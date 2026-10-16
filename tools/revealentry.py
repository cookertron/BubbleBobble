# -*- coding: utf-8 -*-
"""$8C28, THE REVEAL, AT ITS FOUR OTHER ENTRIES -- what each costs, whether interrupts are off
across it, and how many frame interrupts the machine loses there.  (TIMING.md 'Still not
measured' item 10; M7.57 closed the fifth entry, $8C14's fall-in inside $94C2.)

THE ENTRIES (read with adis.py):
  $A0BE  JP z,$8C28    the storm's wrap: $A0B3 INC A takes ($FECF) to 0; $A0BA CALL nc,$A0F5 is
                       NOT taken (A = 0 < $F0), so NO DI precedes it -- the main loop's IFF (1).
  $9032  CALL $8C28    the cross's release, $9031 DI first; EI at $9035 after the RET.  Inside the
                       reveal $8C4C EI ends the window.
  $A9D7  JP $8C28      the giant's hit: $A9B5 DI .. $A9D6 EI brackets the award ($80FA) -- the EI
                       comes BEFORE the jump, so the reveal runs with interrupts ON.
  $A11C  CALL $8C28    the umbrella's flash loop $A110 (item type 6, $88C0 JP $A110): five turns of
                       CALL $A0E0 / EI / HALT / DI / CALL $8C28 / EI / HALT / DI / POP BC / DJNZ.
                       Each reveal is entered one ISR after a HALT -- its phase is the ISR's end.

HOW EACH IS REACHED (no saved state has any of them pending):
  storm     SEMI-NATURAL: ($FECF) := $FD (stormtime.py's 'armed two ticks early'), then free play
            with interrupts ON, contended, to $A0BE with ($FECF) = 0.
  cross     SEMI-NATURAL: at the main loop's top ($8D25) the cross's own handler $8883 is called
            (($FED2) := 1, $A891..$A898 := $FF, ($8DBD) := 0 -- what collecting it does), then free
            play to $9031.  Only a round with SEVEN live enemy slots ever releases (the gate ORs
            $A891..$A897 and the entity pass ticks only live slots): r50_48 and r10_48.
  giant     NATURAL: fallcandy and peachfall reach the hit by free play (the giant parked on row 19).
  umbrella  FORCED: at $8D25, $88B1 (handler 6) called with IX = player 1 and interrupts ON; the
            five reveals' phases are the machine's own (HALT-synchronised), not swept.

RUNS, per entry and world:
  exact     from the entry's first instruction of interest (the DI, or $A0BE) to the reveal's RET,
            a plain Simulator with fast_djnz / fast_ldir OFF, no contention, interrupts OFF: the
            T stamps of the DI's end, $8C28, $8216 (repaint), $7F80 (digits), $8C2B (derive),
            $957E (panel), $806C (lives), $8C4C (EI), $8C4E (OUT), the RET's end.
  free      the semi-natural / natural run, contended, interrupts ON, from the force point to the
            reveal's return (umbrella: to $A110's RET).
  phases    (not umbrella) the same with T moved to k * 4,368 into its frame at the force point,
            sixteen phases; for the giant six more (FRAME_T - 40 .. - 4,300) that put a boundary
            inside its 4,350-T award window, which the 4,368 grid steps over.  A boundary AT the
            force point is not counted (the instruction before it, never run, would have taken it).
  seed      ($9032 M7.86; $A0BE and $A9D7 M7.94) the exact run's INPUTS from $9031 to the reveal's RET: every byte of
            $4000.. it read before writing it (not its own instruction bytes), as [start, hex] runs
            -- and the address alone of a read below $4000 (TRAPS #281: no ROM value is kept) -- so
            the port can be put in the machine's world at $9031; and its OUTPUT, the write stream
            outside the stack: the count and a digest of 'address@T;' (T from $9031, the writing
            instruction's start), values left out (the digits' glyphs are the ROM's).
            M7.94: for $A0BE and $A9D7 the same from their EXACT_FROM, but the write stream is split at
            the $8C28 entry: 'n_pre' writes before it (the giant's award; none from $A0BE), and the
            count / digest of the rest with T FROM $8C28 ('rel': 'reveal'); and the giant's IX
            (the hit player's struct, read at $A9C5) in 'ix'.
  Each contended run records every accepted interrupt (its T and its ISR's wall T), every DI
  window (IFF clear from the DI's end to the end of the instruction after the EI -- the first
  point an interrupt can be taken), every frame boundary b inside the run and whether its
  interrupt was taken (LOST if no interrupt is accepted in [b, b+32)), and two predictions of the
  lost set by M7.57's rule (lost iff w0 <= b and b + 32 <= w1): one on the MEASURED window, one on
  the K MODEL's window (the exact segments stretched by game.js BB_EXT_K: repaint 1.251408, digits
  1.133095, derive 1.015841, panel 1, lives 1.002276, out 1; the prefix 1).

NO ROM BYTE IS STORED: the fixture holds T counts, addresses of code and counts only.
GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/revealentry.py capture [--jobs N]  -> build/revealentry_fixture.json
        python tools/revealentry.py verify  [--jobs N]  re-run and diff against the fixture (MATCH)
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, Mem, PC, T, SP, IFF, IXh, IXl, F
import hashlib
from skoolkit.simulator import Simulator
import portconfig as pc

FIXTURE = 'build/revealentry_fixture.json'
FRAME_T = 69888
INT_T = 32
PHASES = [k * (FRAME_T // 16) for k in range(16)]
GUARD = set(range(0xD000, 0xD300))
# the giant's award window ($A9B5 DI .. $A9D7, ~4,350 T) is shorter than the 4,368 grid: phases that
# put a frame boundary inside it
GIANT_PHASES = [FRAME_T - d for d in (40, 500, 1500, 2500, 3500, 4300)]
LOOP_TOP = 0x8D25
REVEAL, EI_AT, OUT_AT = 0x8C28, 0x8C4C, 0x8C4E
HOOKS = {0x8216: 'repaint', 0x7F80: 'digits', 0x8C2B: 'derive', 0x957E: 'panel', 0x806C: 'lives',
         0x8C4C: 'out'}
# game.js BB_EXT_K (M7.57's fitted stretch), the routines the reveal is made of
K = {'pre': 1.0, 'repaint': 1.251408, 'digits': 1.133095, 'derive': 1.015841, 'panel': 1.0,
     'lives': 1.002276, 'out': 1.0}
ENTRIES = {
    'A0BE': {'how': 'storm', 'worlds': ('round1_48', 'r50_48'), 'force': 0xA0BE},
    '9032': {'how': 'cross', 'worlds': ('r50_48', 'r10_48'), 'force': 0x9031},
    'A9D7': {'how': 'giant', 'worlds': ('fallcandy', 'peachfall'), 'force': 0xA9B5},
    'A11C': {'how': 'umbrella', 'worlds': ('umbrella', 'round1_48', 'r50_48'), 'force': 0x88B1},
}
EXACT_FROM = {'A0BE': 0xA0BE, '9032': 0x9031, 'A9D7': 0xA9B5, 'A11C': 0xA11B}


class Fail(Exception):
    pass


def new(state):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[0x8DC4] != 0xC9:
        raise Fail('%s: not the 48K branch (TRAPS #28)' % state)
    return h


def plain(h):
    """swap in a plain Simulator, fast_djnz / fast_ldir OFF, no contention (extendtime.py's EXACT)"""
    regs = list(h.sim.registers)
    sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
    sim.registers[:] = regs
    h.sim = sim
    h.memobj.sim = sim
    sim.set_tracer(h.ports)
    h.frame_duration, h.int_active = sim.frame_duration, sim.int_active


class SeedMem(Mem):
    """the plain run's memory: the FIRST access of each byte (a read before any write is an input)
    and every write outside the stack with its instruction's start T"""
    __slots__ = ('seen', 'rd', 'wr', 'regs', 'tins')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.seen, self.rd, self.wr, self.regs, self.tins = set(), [], [], None, [0]

    def __getitem__(self, i):
        if self.regs is not None and type(i) is int and i not in self.seen:
            p = self.regs[PC]
            if not (p <= i < p + 4):                  # not this instruction's own bytes
                self.seen.add(i)
                self.rd.append(i)
        return self.m[i]

    def __setitem__(self, i, v):
        if self.regs is not None:
            self.seen.add(i)
            sp = self.regs[SP]
            if not (sp - 64 <= i < sp + 64):          # the stack is not the reveal's output
                self.wr.append((i, self.tins[0]))
        Mem.__setitem__(self, i, v)


def seed_of(rm, m0, t0, rel=None):
    """the inputs as [start, hex] runs (>= $4000, values as they stood at $9031) and the ROM's
    addresses alone; the writes' count and digest (M7.94: with `rel`, the $8C28 entry's T from t0,
    only the writes from it on, their T from it, and the count of those before it)"""
    runs = []
    for a in sorted(a for a in rm.rd if a >= 0x4000):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    wr, extra = rm.wr, {}
    if rel is not None:
        extra = {'rel': 'reveal', 'n_pre': sum(1 for a, t in wr if t - t0 < rel)}
        wr = [(a, t) for a, t in wr if t - t0 >= rel]
        t0 += rel
    s = ''.join('%d@%d;' % (a, t - t0) for a, t in wr)
    out = {'ram': runs, 'rom': sorted(a for a in rm.rd if a < 0x4000), 'n_writes': len(wr),
           'writes': hashlib.sha1(s.encode('ascii')).hexdigest()[:16]}
    out.update(extra)
    return out


def go(h, stop, limit_t, interrupts=True):
    """free run to a PC in `stop` (or a predicate-less limit); guarded"""
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    end = r[T] + limit_t
    while r[T] < end:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if p in stop and stop[p](h):
            return p
        if interrupts and mem[p] == 0x76 and r[IFF]:
            h._fast_halt()
            continue
        sim.opcodes[mem[p]]()
        if interrupts and r[IFF] and r[T] % fd < ia:
            sim.accept_interrupt(r, mem, p)
    raise Fail('no stop within %d T (PC $%04X)' % (limit_t, r[PC]))


def push_call(h, addr, ix=None):
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    r[PC] = addr
    if ix is not None:
        r[IXh], r[IXl] = ix >> 8, ix & 0xFF


def reach(args):
    """the force point of one entry on one world, as a saved state, plus how it was reached"""
    entry, world = args
    how = ENTRIES[entry]['how']
    h = new(world)
    m, r = h.memobj.m, h.sim.registers
    t0 = r[T]
    yes = lambda hh: True
    if how == 'storm':
        m[0xFECF] = 0xFD
        go(h, {0xA0BE: lambda hh: m[0xFECF] == 0}, 60 * FRAME_T)
    elif how == 'cross':
        go(h, {LOOP_TOP: yes}, 4 * FRAME_T)
        save = (r[PC], r[SP])
        push_call(h, 0x8883)
        go(h, {s: yes for s in h.SENTINELS}, 10 ** 5, interrupts=False)
        r[PC], r[SP] = save
        go(h, {0x9031: yes}, 2000 * FRAME_T)
    elif how == 'giant':
        go(h, {0xA9B5: yes}, 200 * FRAME_T)
    elif how == 'umbrella':
        go(h, {LOOP_TOP: yes}, 4 * FRAME_T)
        push_call(h, 0x88B1, 0xFD80)
    return {'entry': entry, 'world': world, 'state': h.save_state(), 'frames_to_reach': (r[T] - t0) / FRAME_T,
            'phase': r[T] % FRAME_T}


def exact(st, entry):
    """uncontended, fast off, interrupts off, from EXACT_FROM to the reveal's RET"""
    h = new('round1_48')
    h.load_state(st)
    if entry == 'A11C':                       # run (contended, interrupts on) to the first $A11B
        go(h, {0xA11B: lambda hh: True}, 4 * FRAME_T)
    rm = None
    if entry in ('9032', 'A0BE', 'A9D7'):     # M7.86 / M7.94: the inputs and the write stream (seed_of)
        rm = SeedMem(h.memobj.m)
        h.memobj = rm
        m0 = bytes(rm.m)
    plain(h)
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    if r[PC] != EXACT_FROM[entry]:
        raise Fail('exact %s: at $%04X' % (entry, r[PC]))
    t0 = r[T]
    ix0 = (r[IXh] << 8) | r[IXl]
    if rm is not None:
        rm.regs = r
    stamps, sp0, ret, prev = [], None, None, None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if p == REVEAL and sp0 is None:
            sp0, ret = r[SP], mem[r[SP]] | (mem[r[SP] + 1] << 8)
        if sp0 is not None and p == ret and r[SP] == sp0 + 2:
            stamps.append(['ret', r[T] - t0])
            break
        if p == REVEAL:
            stamps.append(['reveal', r[T] - t0])
        if p in HOOKS and sp0 is not None and prev != p:
            stamps.append([HOOKS[p], r[T] - t0])
        if p == OUT_AT:
            stamps.append(['outI', r[T] - t0])
        iff = r[IFF]
        if rm is not None:
            rm.tins[0] = r[T]
        sim.opcodes[mem[p]]()
        if iff and not r[IFF]:
            stamps.append(['di_end', r[T] - t0])
        if not iff and r[IFF]:
            stamps.append(['ei_end', r[T] - t0])
        prev = p
        if r[T] - t0 > 10 ** 6:
            raise Fail('exact %s: no return' % entry)
    if rm is not None:
        rm.regs = None
        if entry == '9032':
            return stamps, seed_of(rm, m0, t0)
        sd = seed_of(rm, m0, t0, dict(stamps)['reveal'])
        if entry == 'A9D7':
            sd['ix'] = ix0
        return stamps, sd
    return stamps, None


def kmodel(stamps):
    """the K model's T at each stamp: segments from the reveal on stretched by the routine they open"""
    out, cur, last, kk = {}, 0.0, 0, K['pre']
    for name, t in stamps:
        cur += kk * (t - last)
        last = t
        out[name] = cur
        if name in K:
            kk = K[name]
    return out


def traced(st, entry, phase):
    """contended, interrupts ON, from the force point to the reveal's return (umbrella: $A110's RET)"""
    h = new('round1_48')
    h.load_state(st)
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    if phase is not None:
        r[T] = (r[T] // fd) * fd + phase
    t0 = r[T]
    sents = set(h.SENTINELS)
    accepts, wins, marks = [], [], []
    isr = None
    di_t, ei_pending = None, False
    sp0 = ret = None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if isr is not None and p == isr[1] and r[SP] == isr[2]:
            accepts[-1].append(r[T] - t0 - accepts[-1][0])
            isr = None
        if entry == 'A11C':
            if p in sents:
                marks.append(['end', r[T] - t0])
                break
        else:
            if p == REVEAL and sp0 is None:
                sp0, ret = r[SP], mem[r[SP]] | (mem[r[SP] + 1] << 8)
            if sp0 is not None and p == ret and r[SP] == sp0 + 2:
                marks.append(['end', r[T] - t0])
                break
        if p == REVEAL:
            marks.append(['reveal', r[T] - t0])
        if p in (0x9032, 0xA9D7, 0xA11C, 0xA0BE) and isr is None:
            marks.append(['entry', r[T] - t0])
        if p == OUT_AT:
            marks.append(['outI', r[T] - t0])
        if mem[p] == 0x76 and r[IFF]:
            if ei_pending and isr is None:            # the HALT after an EI: acceptable from here
                wins.append([di_t, r[T] - t0])
                ei_pending, di_t = False, None
            h._fast_halt()
            accepts.append([r[T] - t0, p])
            isr = (None, (p + 1) & 0xFFFF, r[SP] + 2)
            continue
        iff = r[IFF]
        sim.opcodes[mem[p]]()
        if isr is None:
            # a window opens at the end of the main-line instruction that clears IFF, and closes at
            # the end of the first instruction after the EI (the first point an interrupt is taken)
            if ei_pending and r[IFF]:
                wins.append([di_t, r[T] - t0])
                ei_pending, di_t = False, None
            if iff and not r[IFF] and di_t is None:
                di_t = r[T] - t0
            if not iff and r[IFF] and di_t is not None:
                ei_pending = True
        if r[IFF] and r[T] % fd < ia:
            tb = r[T]
            spb = r[SP]
            if sim.accept_interrupt(r, mem, p):
                accepts.append([tb - t0, p])
                isr = (None, mem[r[SP]] | (mem[r[SP] + 1] << 8), spb)
        if r[T] - t0 > 40 * FRAME_T:
            raise Fail('traced %s: no end' % entry)
    tend = marks[-1][1]
    # every frame boundary inside the run, and whether its interrupt was taken
    # (strictly after the force point: a boundary AT it would have been taken by the instruction
    # before, which a forced run never executes)
    first = fd - (t0 % fd)
    bounds = list(range(first, tend, fd))
    acc_t = [a[0] for a in accepts]
    lost = [b for b in bounds if not any(b <= a < b + INT_T for a in acc_t)]
    rule = [b for b in bounds if any(w[0] <= b and b + INT_T <= w[1] for w in wins)]
    return {'phase0': t0 % fd, 'marks': marks, 'isrs': [[a[0], a[2] if len(a) > 2 else None] for a in accepts],
            'windows': wins, 'bounds': bounds, 'lost': lost, 'rule_lost': rule}


def one(args):
    st, entry, world, phase, stamps = args
    x = traced(st, entry, phase)
    x.update(entry=entry, world=world, forced=phase is not None)
    # the K model's window: the measured DI end + the K-stretched exact span to the EI's end
    if entry in ('9032', 'A11C'):
        km = kmodel(stamps)
        span = km['ei_end'] + 4 - km['di_end']        # + the instruction after EI (XOR A, 4 T)
        ex_span = dict(stamps)['ei_end'] + 4 - dict(stamps)['di_end']
        kw = []
        for w in x['windows']:
            if w[1] - w[0] > 100000:                     # the reveal's window, not $A121..$A119's
                kw.append([w[0], w[0] + round(span)])
        x['kmodel_windows'] = kw
        x['kmodel_lost'] = [b for b in x['bounds'] if any(w[0] <= b and b + INT_T <= w[1] for w in kw)]
        x['exact_span'] = ex_span
        x['kmodel_span'] = round(span)
    # main-line T of the reveal: wall from $8C28 to the end less the ISRs inside it
    rv = [m[1] for m in x['marks'] if m[0] == 'reveal']
    ends = [m[1] for m in x['marks'] if m[0] == 'end']
    if entry != 'A11C':
        a, b = rv[0], ends[-1]
        isr_in = sum(i[1] for i in x['isrs'] if a <= i[0] < b and i[1] is not None)
        x['reveal_wall'] = b - a
        x['reveal_main'] = b - a - isr_in
        x['reveal_isrs'] = sum(1 for i in x['isrs'] if a <= i[0] < b)
    return x


def capture(jobs=6):
    wl = [(e, w) for e, d in ENTRIES.items() for w in d['worlds']]
    with ProcessPoolExecutor(jobs) as ex:
        reached = list(ex.map(reach, wl))
    ex_args = [(x['state'], x['entry']) for x in reached]
    with ProcessPoolExecutor(jobs) as ex:
        exacts = list(ex.map(_exact, ex_args))
    seeds = [e[1] for e in exacts]
    exacts = [e[0] for e in exacts]
    runs = []
    for x, st in zip(reached, exacts):
        runs.append((x['state'], x['entry'], x['world'], None, st))
        if x['entry'] != 'A11C':
            for ph in PHASES + (GIANT_PHASES if x['entry'] == 'A9D7' else []):
                runs.append((x['state'], x['entry'], x['world'], ph, st))
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(one, runs))
    out = {'meta': {'phases': PHASES, 'K': K, 'int_t': INT_T}, 'entries': {}}
    for x, st, sd in zip(reached, exacts, seeds):
        rows = [r for r in res if r['entry'] == x['entry'] and r['world'] == x['world']]
        out['entries'].setdefault(x['entry'], {})[x['world']] = {
            'how': ENTRIES[x['entry']]['how'], 'frames_to_reach': round(x['frames_to_reach'], 3),
            'reach_phase': x['phase'], 'exact': st, 'kmodel': {k: round(v, 1) for k, v in kmodel(st).items()},
            'free': rows[0], 'phases': rows[1:]}
        if sd is not None:
            out['entries'][x['entry']][x['world']]['seed'] = sd
    return out


def _exact(a):
    return exact(*a)


def report(out):
    for e, ws in out['entries'].items():
        for w, d in ws.items():
            ex = dict(d['exact'])
            print('$%s %-10s %-8s reached in %.2f frames at phase %d' % (e, w, d['how'], d['frames_to_reach'],
                                                                       d['reach_phase']))
            print('   exact: %s' % d['exact'])
            print('   exact reveal ($8C28..RET) %d T; entry window (di_end..ei_end+4) %s' % (
                ex['ret'] - ex['reveal'],
                (ex['ei_end'] + 4 - ex['di_end']) if 'di_end' in ex and 'ei_end' in ex else 'n/a'))
            for r in [d['free']] + d['phases']:
                wins = [[a, b, b - a] for a, b in r['windows']]
                print('   %s ph %5d: wall %s main %s isrs-in %s | bounds %d lost %d (at %s) rule %d kmodel %s | '
                      'windows %s' % ('F' if r['forced'] else 'N', r['phase0'], r.get('reveal_wall'),
                                      r.get('reveal_main'), r.get('reveal_isrs'), len(r['bounds']),
                                      len(r['lost']), r['lost'], len(r['rule_lost']),
                                      len(r['kmodel_lost']) if 'kmodel_lost' in r else '-', wins))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    jobs = 6
    if '--jobs' in sys.argv:
        jobs = min(6, int(sys.argv[sys.argv.index('--jobs') + 1]))
    t = time.time()
    out = capture(jobs)
    report(out)
    if cmd == 'capture':
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1)
        print('wrote %s (%.1f s)' % (FIXTURE, time.time() - t))
    elif cmd == 'verify':
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        new_ = json.loads(json.dumps(out))
        if old == new_:
            print('MATCH (%.1f s)' % (time.time() - t))
        else:
            bad = [k for k in old['entries'] if old['entries'][k] != new_['entries'].get(k)]
            print('DIFF in %s (%.1f s)' % (bad, time.time() - t))
            sys.exit(1)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
