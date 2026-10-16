"""M10.0b -- THE AY ENGINE, DIRECT: the 128K branch's music engine in bank 1, called at its two entries -- $D167 the
REQUEST (A = the sound) and $CF80 the TICK -- from a fresh copy, on the port's clock.  The oracle M10.1's JS engine is
gated against, write for write.  (docs/M10-PLAN.md 1.2: the engine; section 4: M10.0.)

THE MACHINE is the M10 layer's: the 48K harness with the opt-in paging port and AY (Harness(paging=$10), the 128K branch
on the 48K clock).  Bank 1 is laid by the game's OWN cold-start leg: loadspine's world 'p4p3' run through the CLS and the
probe to $F5CC, the probe's answer forced to $80 and BANKM $5B5C := $10 (the 128K load's), then $8CC3 -> $8CCA with the
interrupts off: $96B3's LDIR through the display file, OUT ($7FFD),$11, the LDIR into $C350, OUT ($7FFD),$10.  ASSERTED:
the 128K leg ran ($969A's patch not), the hooks $8DC4 / $8E05 / $8E0A kept ($F3 / $0E / $21), $9AE7 = $10, bank 1 =
the tape's $E6A8..$F5BB at $C350 and zero elsewhere, bank 0's $C350.. still the tape's sprites.

STREAMS, each from that fresh engine, interrupts off, bank 1 paged as $8E0A pages it:
  '0'..'7'   CALL $D167 with A = n, then 3,000 x CALL $CF80
  'none'     CALL $CF80 with no request, to the first data read below $4000 by the engine (its pointers are 0 at the
             copy: the ROM) -- recorded as rom_fetch [tick, the reading PC, the address] and the stream STOPS there:
             what that tick writes is ROM bytes, and no ROM byte is recorded
  'chainS'   agent D's seeded random chains (scratchpad/ay_cross/lockstep.py chain(), the same generator): requests
             0..7 at random tick counts -- mid-note, mid-loop, mid-mute -- carrying the history byte $D13F (slot B's
             shape: 1 forever once sound 1 or 6 wrote R13 = 1) and request 0's mute
EVENTS: a request ['R', n, A, T, w]; a tick [A, T, w]; an integer k = k IDLE ticks (A 0, T 116, no write: asserted,
never assumed).  w = [reg, val, dt, reg, val, dt, ...] in order, dt = the OUT ($BFFD)'s first T from the call's entry
(PC at the entry; the CALL not counted, the RET counted).  Each stream's bank-1 SHA-1 at its end (the state lives in
the engine's own operand bytes, so the JS engine's 16K must end equal).

UNCONTENDED: on the 48K bank 1 is never contended and the OUTs go to $FFFD / $BFFD (high bytes $FF / $BF, odd ports),
so every T here is the uncontended T.  ASSERTED: every stream re-run on the PLAIN simulator at another phase is identical.

THE 128K CROSS-CHECK: the same streams on tools/harness128.py (engine 'c'), bank 1 laid by the 128K machine's own boot
(build/boot128.z80: the menu '4' / '3', the probe answering $80 by itself, the cold start to $96D0): bank 1 identical
(all 16K), every event's writes and A identical.  T is not compared: bank 1 is contended on the 128K.

No ROM byte: the writes are the engine's data; the ROM fetch is an address.  Tape-derived values only as decoded data.
Usage:  python tools/ayengine.py [capture|verify]       -> build/ayengine_fixture.json  (~15 s)
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import Harness, PC, T, SP, A as RA
import ctrlmenu as cm
import loadspine as ls

# registered in port.json as `ayengine` (ship: false) and read by test/bb.test.js's M10.1 block: the suite requires every
# build/*.json registered AND read by a check (its fixture guards), so it waited in build/pending/ until M10.1's gate
FIXTURE = 'build/ayengine_fixture.json'
TAPE = 'build/image_tape.bin'
ENG_LO, ENG_HI = 0xC350, 0xD264            # bank 1's copy, [lo, hi)
TAPE_LO = 0xE6A8                           # the copy's source on the tape: ENG_LO + $2358
CODE_LO, CODE_HI = 0xCF80, 0xD1E2          # the engine's code
REQ, TICK = 0xD167, 0xCF80
IDLE_T = 116
TICKS = 3000
CHAIN_SEEDS, CHAIN_N = (1, 2, 3, 4), 60


class Fail(Exception):
    pass


def sha(b):
    return hashlib.sha1(bytes(b)).hexdigest()


# ------------------------------------------------------------------ the 48K machine with paging
def fresh48():
    """The M10 machine at $8CCA: bank 1 just laid by the game's own leg.  -> (h, state)"""
    h, m, r = ls.at('p4p3')
    cm.keys(h, [])
    cm.run_to(h, (ls.SPINE_END,), True, limit=10 ** 8)          # the CLS and the 48K probe, to $F5CC
    h.enable_paging(0x10)
    r[RA] = 0x80                                                # the probe's 128K answer: forced (M10)
    m[0x5B5C] = 0x10                                            # BANKM, as the 128K load leaves it
    seen = set()
    marks = (0x969A, 0x96B3, 0x96D8)
    while r[PC] != 0x8CCA:
        if r[PC] in marks:
            seen.add(r[PC])
        h.step(1, interrupts=False)
        if r[T] > 10 ** 9:
            raise Fail('$8CCA never reached')
    tape = open(TAPE, 'rb').read()
    b0, b1 = h.paging.bank(0), h.paging.bank(1)
    checks = {
        'leg_128K': sorted('$%04X' % x for x in seen) == ['$96B3', '$96D8'],
        'hooks_kept': list(m[a] for a in (0x8DC4, 0x8E05, 0x8E0A)) == [0xF3, 0x0E, 0x21],
        '9AE7': m[0x9AE7] == 0x10,
        'bank0_paged': h.paging.cur == 0,
        'bank1_engine': b1[ENG_LO - 0xC000:ENG_HI - 0xC000] == tape[TAPE_LO:TAPE_LO + ENG_HI - ENG_LO],
        'bank1_zero_elsewhere': not any(b1[:ENG_LO - 0xC000]) and not any(b1[ENG_HI - 0xC000:]),
        'bank0_sprites': b0[ENG_LO - 0xC000:ENG_HI - 0xC000] == tape[ENG_LO:ENG_HI],
        'outs_7FFD': [r_[2] for r_ in h.paging.p7ffd] == [0x11, 0x10],
        'unsupported': h.paging.unsupported == {},
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise Fail('the cold start\'s 128K leg: %s' % bad)
    del cm.OUTS[:]
    return h, h.save_state()


class FetchWatch(harness.Mem):
    """harness.Mem noting every read below $4000 the engine's code makes (registers[PC] in its code)."""
    __slots__ = ()
    hits = []

    def __getitem__(self, i):
        if i < 0x4000 and CODE_LO <= self.sim.registers[PC] < CODE_HI:
            FetchWatch.hits.append((self.sim.registers[PC], i))
        return self.m[i]


def _fetch128():
    from skoolkit.pagingtracer import Memory

    class Fetch128(Memory):
        """pagingtracer.Memory noting every read below $4000 the engine's code makes (engine 'py')"""
        hits = []

        def __getitem__(self, index):
            if isinstance(index, int) and index < 0x4000 and CODE_LO <= self.h.sim.registers[PC] < CODE_HI:
                Fetch128.hits.append((self.h.sim.registers[PC], index))
            return Memory.__getitem__(self, index)
    return Fetch128


Fetch128 = _fetch128()


class Caller:
    """Direct calls into the engine on a machine whose bank 1 is paged; both harnesses."""

    def __init__(self, h, is128=False):
        self.h, self.is128 = h, is128
        self.r = h.sim.registers
        self.sp = self.r[SP]
        self.hits = []

    def watch(self, on):
        """note the engine's reads below $4000 in self.hits (the 128K: engine 'py' only)"""
        FetchWatch.hits = Fetch128.hits = self.hits
        if self.is128:
            from skoolkit.pagingtracer import Memory
            if self.h.engine != 'py':
                raise Fail('the 128K read watch needs engine "py"')
            self.h.sim.memory.__class__ = Fetch128 if on else Memory
        else:
            self.h.memobj.__class__ = FetchWatch if on else harness.Mem

    def log(self):
        return self.h.ay_log if self.is128 else self.h.paging.ay_log

    def call(self, addr, a=None):
        h, r = self.h, self.r
        lg = self.log()
        del lg[:]
        del cm.OUTS[:]                       # ctrlmenu's global OUT record: unbounded otherwise
        t0 = r[T]
        idx, t, steps = h.call(addr, {'A': a} if a is not None else None, limit=200_000, interrupts=False)
        r[SP] = self.sp
        if idx != 0:
            raise Fail('$%04X did not return to its caller (sentinel %s)' % (addr, idx))
        if self.is128:
            w = [x for row in lg for x in (row[3], row[4], row[5] - t0)]
        else:
            w = [x for row in lg for x in (row[2], row[3], row[0] - t0)]
        return r[RA], t, w


def run_plan(c, plan):
    """plan: [('R', n) | ('T', k)].  -> (events, rom_fetch).  The stream STOPS at the first read below $4000 by the
       engine's code -- the ROM, through a pointer still 0 from the copy -- recorded as rom_fetch [the tick's number in
       the stream, the reading PC, the address]; that tick's writes are ROM bytes and are NOT recorded.  The read watch
       needs the 48K harness or the 128K's py engine (rom_fetch None on the 128K's C engine: unwatched).  On the 128K an
       idle tick is A 0 and no write whatever its T: bank 1 is contended there"""
    ev = []

    def put(e):
        if e[0] == 0 and not e[2] and (c.is128 or e[1] == IDLE_T):
            if ev and isinstance(ev[-1], int):
                ev[-1] += 1
            else:
                ev.append(1)
        else:
            if not e[2] and e[0] == 0:
                raise Fail('a tick with no write and A 0 took %d T, not %d' % (e[1], IDLE_T))
            ev.append(list(e))
    watching = not c.is128 or c.h.engine == 'py'
    if watching:
        c.watch(True)
    rom, tick = None, 0
    try:
        for kind, n in plan:
            if kind == 'R':
                a, t, w = c.call(REQ, n)
                if c.hits:
                    raise Fail('request %d read $%04X' % (n, c.hits[0][1]))
                ev.append(['R', n, a, t, w])
                continue
            for _ in range(n):
                tick += 1
                a, t, w = c.call(TICK)
                if c.hits:
                    rom = [tick, c.hits[0][0], c.hits[0][1]]
                    break
                put((a, t, w))
            if rom:
                break
    finally:
        if watching:
            c.watch(False)
    return ev, rom


def chain_plan(seed, n):
    """agent D's generator (scratchpad/ay_cross/lockstep.py chain()), n requests"""
    rnd = random.Random(seed)
    plan, first = [], True
    for _ in range(n):
        req = rnd.randint(1, 7) if first else rnd.choice([0, 1, 2, 3, 4, 5, 6, 7, 1, 6, 5])
        first = False
        kind = rnd.random()
        if kind < 0.35:
            k = rnd.randint(0, 6)
        elif kind < 0.7:
            k = rnd.randint(7, 120)
        elif kind < 0.9:
            k = rnd.randint(120, 700)
        else:
            k = rnd.randint(700, 2000)
        plan += [('R', req), ('T', k)]
    return plan


def plans():
    out = {str(n): [('R', n), ('T', TICKS)] for n in range(8)}
    out['none'] = [('T', 600)]
    for s in CHAIN_SEEDS:
        out['chain%d' % s] = chain_plan(s, CHAIN_N)
    return out


def streams48(h, st, contended_phase=None):
    out = {}
    for name, plan in plans().items():
        h.load_state(st)
        if contended_phase is not None:
            r = h.sim.registers
            r[T] = (r[T] // 69888) * 69888 + contended_phase
        h.paging.page(1)
        c = Caller(h)
        ev, rom = run_plan(c, plan)
        if rom:                    # the state BEFORE the fetching tick: after it, bank 1 holds what the ROM fed it
            h.load_state(st)
            h.paging.page(1)
            cut, left = [], rom[0] - 1
            for k, n in plan:
                cut.append((k, n if k == 'R' else min(n, left)))
                left -= 0 if k == 'R' else min(n, left)
            if run_plan(Caller(h), cut) != (ev, None):
                raise Fail('%s: the re-run to the fetching tick differs' % name)
        out[name] = {'plan': [[k, n] for k, n in plan], 'events': ev, 'end_sha1': sha(h.paging.bank(1))}
        if rom:
            out[name]['rom_fetch'] = rom
    return out


# ------------------------------------------------------------------ the 128K cross-check
def fresh128():
    import harness128 as H8
    h = H8.Harness128(engine='c')
    why, n = h.run_until(0xF664, limit=10_000_000)
    if why != 'target':
        raise Fail('128K: the menu read $F664 never reached')
    h.drive([(3, ['4']), (30, []), (3, ['3'])])
    h.ports.release_all()
    why, n = h.run_until(0x96D0, limit=80_000_000)
    if why != 'target' or h.paged() != 1:
        raise Fail('128K: $96D0 with bank 1 paged never reached (%s)' % why)
    return h


def cross128(ref, b1_48):
    h = fresh128()
    b1 = h.bank_peek(1, 0xC000, 0x4000)
    res = {'bank1_equal': b1 == b1_48, 'streams': 0, 'events': 0, 'differ': []}
    st = h.save_state()
    import harness128 as H8
    for name, plan in plans().items():
        if 'rom_fetch' in ref[name]:            # the read watch needs the py engine: those streams only
            h = H8.Harness128(engine='py', state=st)
        else:
            h.load_state(st)
        c = Caller(h, True)
        ev, rom = run_plan(c, plan)
        mine = ref[name]
        res['streams'] += 1
        res['events'] += len(ev)
        strip = lambda evs: [e if isinstance(e, int) else
                             (['R', e[1], e[2], e[4][0::3], e[4][1::3]] if e[0] == 'R' else [e[0], e[2][0::3], e[2][1::3]])
                             for e in evs]
        if strip(ev) != strip(mine['events']) or (rom or [None])[:1] != (mine.get('rom_fetch') or [None])[:1] \
                or ('rom_fetch' not in mine and sha(h.bank_peek(1, 0xC000, 0x4000)) != mine['end_sha1']):
            res['differ'].append(name)
    return res


# ------------------------------------------------------------------ capture / verify
def summary(streams):
    s = {}
    for name, x in streams.items():
        ticks = sum(e if isinstance(e, int) else (0 if e[0] == 'R' else 1) for e in x['events'])
        idle = sum(e for e in x['events'] if isinstance(e, int))
        tk = [e for e in x['events'] if isinstance(e, list) and e[0] != 'R']
        rq = [e for e in x['events'] if isinstance(e, list) and e[0] == 'R']
        s[name] = {'ticks': ticks, 'idle': idle, 'requests': len(rq), 'writes': sum(len(e[2]) // 3 for e in tk) +
                   sum(len(e[4]) // 3 for e in rq), 'ends': sum(1 for e in tk if e[0] == 1),
                   'T_max': max([e[1] for e in tk] + [IDLE_T]), 'req_T': sorted({e[3] for e in rq})}
    return s


def capture():
    h, st = fresh48()
    streams = streams48(h, st)
    hp = Harness(contended=False)
    hp.load_state(st)
    plain = streams48(hp, hp.save_state(), contended_phase=12345)
    if plain != streams:
        bad = [k for k in streams if streams[k] != plain.get(k)]
        raise Fail('the plain simulator at another phase differs: %s' % bad)
    h.load_state(st)
    b1 = h.paging.bank(1)
    x128 = cross128(streams, b1)
    if not x128['bank1_equal'] or x128['differ']:
        raise Fail('the 128K cross-check: %s' % x128)
    return {
        'what': 'M10.0b THE AY ENGINE, DIRECT (tools/ayengine.py): $D167 / $CF80 called from a fresh bank 1 on the M10 '
                'machine (the 48K harness + paging); see the tool\'s docstring for the event format',
        'idle_T': IDLE_T,
        'bank1': {'sha1': sha(b1), 'engine': [ENG_LO, ENG_HI], 'code': [CODE_LO, CODE_HI], 'tape': TAPE_LO},
        'uncontended': 'every stream identical on the plain simulator at phase 12345',
        'cross128': x128,
        'summary': summary(streams),
        'streams': streams,
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    out = capture()
    if mode == 'verify':
        old = json.load(open(FIXTURE))
        same = json.loads(json.dumps(out)) == old
        print('MATCH' if same else 'DIFFERS')
        sys.exit(0 if same else 1)
    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    with open(FIXTURE, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print('wrote %s (%d bytes)' % (FIXTURE, os.path.getsize(FIXTURE)))
    for name, s in out['summary'].items():
        print('  %-7s %s' % (name, s))
    print('  cross128', {k: v for k, v in out['cross128'].items()})


if __name__ == '__main__':
    main()
