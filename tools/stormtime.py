# -*- coding: utf-8 -*-
"""M7.58 -- $A09A's STORM FLASH AND STRIKE TICKS, WRITE BY WRITE: where every byte the painter
$A0E0 puts into the attribute file lands in main-line T, and what the frame interrupts do while
the tick holds the main loop.

beeper.py's 'storm' measured each tick's OUTs and COST (BB_STORM), one tick at a time with
interrupts off.  None says WHEN inside the tick a byte is written, and the port painted all four
of a flash tick's 704-byte passes inside ONE call -- so only the last was ever seen, where the
machine's four inks follow each other 29,088 T apart across 1.7 frames.  And the rest of the
pass ran at once.  Unlike the hurry's or the completion's block, BOTH ISR GATES ARE OPEN (the
storm comes in play): the interrupts inside the tick run the whole bubble manager and entity
pass.  This oracle records:

  direct    round1_48 with the storm armed ($FECF := v, the flood off, the edge detector primed),
            $A09A called with interrupts OFF.  EXACT: a plain Simulator with fast_djnz /
            fast_ldir OFF and no contention.  Flash ticks (v = $1F, $3F, $DF, four generator
            words) and the three strikes (v = $FC, $FD, $FE -- the payload $A0F5 first).  Every
            write: the painter's ($A0F0) against the model (each $A0E0 entry E, then pass p's
            byte i at E + PASS[p] + 41 i), the rest listed; each $A0E0 entry; the OUTs; the end.
  phases    the flash ($1F) and a strike ($FD) at sixteen frame phases, contended, interrupts
            off: every painter write's T.
  natural   interrupts ON, contended, in play: the storm armed two ticks early and run to the
            flash (or strike) tick's RET.  FREE on seven worlds (the entry phase is the world's);
            FORCED on round1_48 and r50_48 at sixteen phases (T moved to the phase at the tick's
            $A09A).  Every painter write in MAIN-LINE T (wall T less the interrupts before it),
            every OUT, every interrupt (its main-line T, wall cost, gates, parity), the end; the
            port's seed (the attribute file, the generator, the pool's flags); and THE PREMISE:
            the addresses the interrupts write, how many are attribute bytes, how many attribute
            bytes they read, every byte the tick's main line reads AFTER an interrupt wrote it,
            and every byte an interrupt reads BEFORE the tick's main line's last write of it
            (both must be none: the port's interrupt runs after the call).  The bytes the
            interrupts read AFTER the main line wrote them are listed too -- the strike's
            payload flags, which the bubble manager reads.

NO ROM BYTE IS STORED (the painter writes attribute bytes computed from the seed).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/stormtime.py capture [--jobs N]   -> build/stormtime_fixture.json
        python tools/stormtime.py verify  [--jobs N]   re-run and diff against the fixture
        python tools/stormtime.py direct|phases|natural
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import sfxcensus
sfxcensus.install_hook()                 # BEFORE any Harness: the simulator binds the tracer at construction
import harness
from harness import Harness, PC, T, SP, IFF
from skoolkit.simulator import Simulator
import portconfig as pc

FIXTURE = 'build/stormtime_fixture.json'
GUARD = set(range(0xD000, 0xD300))
FRAME_T = 69888
ISR_RET = 0x8DA1
ENTRY, PAINTER, STORE = 0xA09A, 0xA0E0, 0xA0F0
FORCED = [1000 + k * 4368 for k in range(16)]
FREE = ['round1_48', 'r10_48', 'r20_48', 'r40_48', 'r50_48', 'round1_2p48', 'boss']
FLASH_V, STRIKE_V = 0x1F, 0xFD
PRNGS = [(0x5B, 0x2A), (0x01, 0x00), (0xFF, 0xFF), (0x37, 0xC4)]
ATTR = range(0x5800, 0x5B00)


class Fail(Exception):
    pass


# ---------------------------------------------------------------- instrumentation
RL = None                                # reads, while a list
WL = None                                # writes (addr, value), while a list


def _get(self, i):
    if RL is not None:
        RL.append(i)
    return self.m[i]


def _set(self, i, v):
    if i < 0x4000:
        self.rom_writes += 1
        return
    if WL is not None:
        WL.append((i, v))
    self.m[i] = v


harness.Mem.__getitem__ = _get
harness.Mem.__setitem__ = _set


def new(state, contended):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[0x8DC4] != 0xC9:
        raise Fail('%s: not the 48K branch (TRAPS #28)' % state)
    if not contended:
        regs = list(h.sim.registers)
        sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
        sim.registers[:] = regs
        h.sim = sim
        h.memobj.sim = sim
        sim.set_tracer(h.ports)
        h.frame_duration, h.int_active = sim.frame_duration, sim.int_active
    return h, h.memobj.m


def storm_world(m, v):
    m[0xFECE] = 0                        # the flood not armed (it wins)
    m[0xFECF] = v
    m[0xA09E] = m[0x8DBD] ^ 0x01         # $A09D CP n: n is $A09E -- a CHANGE


def sha(b):
    return hashlib.sha1(bytes(b)).hexdigest()[:16]


def deltas(ts):
    out, p = [], 0
    for t in ts:
        out.append(t - p)
        p = t
    return out


def trace(h, interrupts, want=None, force=None, limit_frames=40):
    """step one instruction at a time.  Direct (want None): PC is at $A09A with a sentinel
    return pushed.  Natural: run until the main line enters $A09A with ($FECF) = want and a
    change pending, then record to its RET.  Returns the tick's record."""
    global RL, WL
    sim = h.sim
    regs, opcodes, mem = sim.registers, sim.opcodes, sim.memory
    m = mem.m
    fd, ia = h.frame_duration, h.int_active
    t_end = regs[T] + limit_frames * FRAME_T
    in_isr, cur = None, None
    RL, WL = [], []
    sfxcensus.LOG.clear()
    try:
        while regs[T] < t_end:
            p = regs[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if cur is None and in_isr is None and p == ENTRY and (
                    want is None or (m[0xFECF] == want and m[0xA09E] != m[0x8DBD])):
                if force is not None:
                    regs[T] = (regs[T] // FRAME_T) * FRAME_T + force
                sp = regs[SP]
                cur = dict(t0=regs[T], sp=sp, ret=m[sp] | (m[sp + 1] << 8), isr_t=0,
                           seed=dict(attr=bytes(m[0x5840:0x5B00]).hex(), prng=[m[0xFE86], m[0xFE87]],
                                     fecf=m[0xFECF], pool=[m[0xFED8 + 10 * k + 7] for k in range(12)]),
                           phase=regs[T] % FRAME_T, paint=[], entries=[], other=[], outs=[], isrs=[],
                           isr_w={}, isr_attr_r=0, isr_r={}, mreads=[], mw={})
                sfxcensus.LOG.clear()
            del RL[:]
            del WL[:]
            nlog = len(sfxcensus.LOG)
            if cur is not None and in_isr is None:
                tm = regs[T] - cur['t0'] - cur['isr_t']
                if p == PAINTER:
                    cur['entries'].append(tm)
            opcodes[mem[p]]()
            if cur is not None:
                if in_isr is not None:
                    for a, v in WL:
                        if not (regs[SP] - 64 <= a < regs[SP] + 64):
                            cur['isr_w'].setdefault(a, regs[T])
                    cur['isr_attr_r'] += sum(1 for a in RL if a in ATTR)
                    for a in RL:
                        cur['isr_r'].setdefault(a, regs[T])
                else:
                    for a, v in WL:
                        if p == STORE:
                            cur['paint'].append((tm, a, v))
                        elif not (regs[SP] - 64 <= a < regs[SP] + 64):
                            cur['other'].append([tm, a, v])
                        if not (regs[SP] - 64 <= a < regs[SP] + 64):
                            cur['mw'][a] = regs[T]
                    for a in RL:
                        cur['mreads'].append((regs[T], a, p))
                    for (tw, pw, port, v) in sfxcensus.LOG[nlog:]:
                        if (port & 0xFF) == 0xFE:
                            cur['outs'].append([tw - cur['t0'] - cur['isr_t'], v])
            if in_isr is not None and p == ISR_RET:
                d = regs[T] - in_isr[0]
                if cur is not None:
                    cur['isrs'].append([in_isr[0] - cur['t0'] - cur['isr_t'], d] + in_isr[1:])
                    cur['isr_t'] += d
                in_isr = None
            if cur is not None and in_isr is None and regs[PC] == cur['ret'] and regs[SP] == cur['sp'] + 2:
                cur['end'] = regs[T] - cur['t0'] - cur['isr_t']
                cur['attr_after'] = sha(m[0x5840:0x5B00])
                cur['prng_after'] = [m[0xFE86], m[0xFE87]]
                return cur
            if interrupts and regs[IFF] and regs[T] % fd < ia:
                in_isr = [regs[T], m[0xFEC4], m[0xFEC5], (m[0x8DBD] + 1) & 1]
                sim.accept_interrupt(regs, mem, p)
                if regs[PC] != 0xFFFF:
                    raise Fail('an interrupt went to $%04X' % regs[PC])
        raise Fail('no tick within %d frames' % limit_frames)
    finally:
        RL = WL = None


def direct_call(h):
    r = h.sim.registers
    sp = (r[SP] - 2) & 0xFFFF
    s = h.SENTINELS[0]
    h.memobj.m[sp], h.memobj.m[sp + 1] = s & 0xFF, s >> 8
    r[SP] = sp
    r[PC] = ENTRY
    return trace(h, False)


# ---------------------------------------------------------------- the painter model
def painter_offsets(paint, entries):
    """each write's T from its pass's $A0E0 entry; asserts the passes' shape"""
    n = len(paint)
    if n != 704 * len(entries):
        raise Fail('%d painter writes for %d entries' % (n, len(entries)))
    offs = []
    for k, e in enumerate(entries):
        ws = paint[704 * k:704 * (k + 1)]
        if [w[1] for w in ws] != list(range(0x5840, 0x5B00)):
            raise Fail('pass %d addresses' % k)
        offs.append([w[0] - e for w in ws])
    return offs


def model(pass_):
    """PASS from the exact runs: 192 + 256 + 256 bytes, 41 T apart, three starts"""
    starts = [pass_[0], pass_[192], pass_[448]]
    for i, o in enumerate(pass_):
        j = 0 if i < 192 else (1 if i < 448 else 2)
        b = i - (0, 192, 448)[j]
        if o != starts[j] + 41 * b:
            raise Fail('painter byte %d at %d, not %d + 41 x %d' % (i, o, starts[j], b))
    return starts


def one_direct(args):
    v, prng = args
    h, m = new('round1_48', False)
    storm_world(m, v)
    m[0xFE86], m[0xFE87] = prng
    c = direct_call(h)
    offs = painter_offsets(c['paint'], c['entries'])
    return dict(v=v, prng=list(prng), seed=c['seed'], entries=c['entries'], offs=offs, end=c['end'],
                outs=c['outs'], other=c['other'], attr_after=c['attr_after'], prng_after=c['prng_after'],
                values=sha([w[2] for w in c['paint']]))


def phase_direct(jobs=8):
    jl = [(v, p) for v in (FLASH_V, 0x3F, 0xDF) for p in PRNGS] + [(v, PRNGS[0]) for v in (0xFC, 0xFD, 0xFE)]
    jl = list(dict.fromkeys(jl))
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_direct, jl))
    shape = None
    for r in runs:
        for o in r['offs']:
            s = model(o)
            if shape is None:
                shape = s
            elif s != shape:
                raise Fail('v=$%02X: pass starts %s, not %s' % (r['v'], s, shape))
        del r['offs']
    fl = [r for r in runs if r['v'] < 0xF0]
    st = [r for r in runs if r['v'] >= 0xF0]
    for r in fl:
        if len(r['entries']) != 4:
            raise Fail('flash v=$%02X: %d passes' % (r['v'], len(r['entries'])))
    print('direct: PASS starts %s, 41 T a byte; flash entries %s end %s; strike entries %s end %s'
          % (shape, sorted(set(tuple(r['entries']) for r in fl)), sorted(set(r['end'] for r in fl)),
             sorted(set(tuple(r['entries']) for r in st)), sorted(set(r['end'] for r in st))))
    return dict(pass_starts=shape, byte=41, runs=runs)


def one_phase(args):
    v, ph = args
    h, m = new('round1_48', True)
    storm_world(m, v)
    m[0xFE86], m[0xFE87] = PRNGS[0]
    h.regs[T] = (h.regs[T] // FRAME_T) * FRAME_T + ph
    c = direct_call(h)
    return dict(v=v, phase=ph, end=c['end'], entries=c['entries'], t=deltas([w[0] for w in c['paint']]))


def phase_phases(jobs=8):
    jl = [(v, ph) for v in (FLASH_V, STRIKE_V) for ph in FORCED]
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_phase, jl))
    for v in (FLASH_V, STRIKE_V):
        e = [r['end'] for r in runs if r['v'] == v]
        print('phases v=$%02X: end %d..%d' % (v, min(e), max(e)))
    return dict(flash=[r for r in runs if r['v'] == FLASH_V], strike=[r for r in runs if r['v'] == STRIKE_V])


def one_natural(args):
    state, v, force = args
    h, m = new(state, True)
    m[0xFECE] = 0
    m[0xFECF] = (v - 2) & 0xFF           # two plain ticks first: the storm as the machine runs it
    c = trace(h, True, want=v, force=force)
    first = c['isr_w']
    hits = sorted(set('%04X@%04X' % (a, p) for (t, a, p) in c['mreads'] if a in first and t > first[a]))
    return dict(state=state, v=v, forced=force, phase=c['phase'], seed=c['seed'], end=c['end'],
                entries=c['entries'], t=deltas([w[0] for w in c['paint']]), n=len(c['paint']),
                values=sha([w[2] for w in c['paint']]), outs=c['outs'], isrs=c['isrs'],
                other=len(c['other']), attr_after=c['attr_after'],
                premise=dict(isr_addrs=len(first), isr_attr_w=sum(1 for a in first if a in ATTR),
                             isr_attr_r=c['isr_attr_r'], reads=len(set(a for (t, a, p) in c['mreads'])),
                             hits=hits,
                             isr_reads_main_w=sorted('%04X' % a for a in c['isr_r'] if a in c['mw']),
                             isr_read_first=sorted('%04X' % a for a in c['isr_r']
                                                   if a in c['mw'] and c['isr_r'][a] < c['mw'][a])))


def phase_natural(jobs=8):
    jl = ([(s, v, None) for v in (FLASH_V, STRIKE_V) for s in FREE] +
          [(s, v, ph) for v in (FLASH_V, STRIKE_V) for s in ('round1_48', 'r50_48') for ph in FORCED])
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_natural, jl))
    bad = [r for r in runs if r['premise']['hits'] or r['premise']['isr_attr_w'] or r['premise']['isr_attr_r']
           or r['premise']['isr_read_first']]
    for r in runs:
        if r['n'] != (2816 if r['v'] == FLASH_V else 704):
            raise Fail('%s v=$%02X: %d painter writes' % (r['state'], r['v'], r['n']))
    for v in (FLASH_V, STRIKE_V):
        rs = [r for r in runs if r['v'] == v]
        print('natural v=$%02X: %d runs, end %d..%d main-line T, %s ISRs in the tick, gates %s'
              % (v, len(rs), min(r['end'] for r in rs), max(r['end'] for r in rs),
                 sorted(set(len(r['isrs']) for r in rs)), sorted(set((i[2] != 0, i[3] != 0) for r in rs for i in r['isrs']))))
    print('premise: %d of %d runs break it' % (len(bad), len(runs)))
    return dict(flash=[r for r in runs if r['v'] == FLASH_V], strike=[r for r in runs if r['v'] == STRIKE_V],
                premise_broken=len(bad))


# ---------------------------------------------------------------- the payload $A0F5 (M7.60)
PAYLOAD_V = (0xEF, 0xF0, 0xFB, 0xFC, 0xFD, 0xFE)       # ($FECF) before the INC: $F0..$FF call it
PAYLOAD_SWEEP = list(range(120, 200)) + list(range(200, 1260, 53)) + list(range(1260, 1360))


def payload_run(v, contended, off=None):
    """$A09A called with ($FECF) = v.  Every instruction's end T from the entry; with `off`, the
    frame's interrupt line rises `off` T after the entry and the first instruction end with IFF
    set and the line still up (T mod frame < int_active), not straight after an EI, is where the
    machine would take it --
    recorded, and the run stops there."""
    h, m = new('round1_48', contended)
    storm_world(m, v)
    m[0xFE86], m[0xFE87] = PRNGS[0]
    r = h.sim.registers
    if off is not None:
        r[T] = (r[T] // FRAME_T + 2) * FRAME_T - off
    sp = (r[SP] - 2) & 0xFFFF
    s = h.SENTINELS[0]
    m[sp], m[sp + 1] = s & 0xFF, s >> 8
    r[SP] = sp
    r[PC] = ENTRY
    t0, fd, ia = r[T], h.frame_duration, h.int_active
    out = dict(v=v, di=None, ei=None, open=None, writes=[], taken=None)
    global WL
    WL = []
    try:
        while True:
            p = r[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if p == s:
                break
            del WL[:]
            tm = r[T] - t0
            h.sim.opcodes[m[p]]()
            if 0xA0F5 <= p <= 0xA10F:
                for a, x in WL:
                    if not (r[SP] - 64 <= a < r[SP] + 64):
                        out['writes'].append([tm, a, x])
            if p == 0xA0F5:
                out['di'] = r[T] - t0
            elif p == 0xA10E:
                out['ei'] = r[T] - t0
            elif p == 0xA10F:
                out['open'] = r[T] - t0                  # the instruction after EI has ended
            # the Z80 takes none straight after EI (SkoolKit's accept_interrupt: `opcode == 0xFB`)
            if off is not None and r[IFF] and r[T] % fd < ia and m[p] != 0xFB:
                out['taken'] = r[T] - t0
                break
            if r[T] - t0 > 40000:
                raise Fail('the tick ran past 40,000 T')
    finally:
        WL = None
    out['end'] = r[T] - t0
    return out


def one_payload(args):
    kind, v, off = args
    if kind == 'exact':
        return payload_run(v, False)
    x = payload_run(v, True, off)
    return dict(off=off, taken=x['taken'], di=x['di'], open=x['open'])


def phase_payload(jobs=8):
    with ProcessPoolExecutor(jobs) as ex:
        exact = list(ex.map(one_payload, [('exact', v, None) for v in PAYLOAD_V]))
        sweep = list(ex.map(one_payload, [('sweep', 0xEF, o) for o in PAYLOAD_SWEEP]))
    w = exact[0]
    for x in exact:
        if (x['di'], x['ei'], x['open'], x['writes']) != (w['di'], w['ei'], w['open'], w['writes']):
            raise Fail('v=$%02X: the payload differs from v=$%02X' % (x['v'], w['v']))
    lost = [x['off'] for x in sweep if x['taken'] is None]
    print('payload: DI %d EI %d open %d, %d writes %d..%d; ends %s; contended sweep: %d of %d offsets '
          'lost, %d..%d' % (w['di'], w['ei'], w['open'], len(w['writes']), w['writes'][0][0],
                            w['writes'][-1][0], sorted(set(x['end'] for x in exact)), len(lost),
                            len(sweep), min(lost), max(lost)))
    return dict(exact=exact, sweep=sweep, int_active=32)


def capture(jobs=8):
    return dict(meta=dict(tool='tools/stormtime.py', forced=FORCED, free=FREE, flash_v=FLASH_V, strike_v=STRIKE_V),
                direct=phase_direct(jobs), phases=phase_phases(jobs), natural=phase_natural(jobs),
                payload=phase_payload(jobs))


def main():
    a = sys.argv[1:]
    jobs = 8
    if '--jobs' in a:
        i = a.index('--jobs')
        jobs = int(a[i + 1])
        del a[i:i + 2]
    cmd = a[0] if a else 'capture'
    if cmd == 'capture':
        d = capture(jobs)
        with open(FIXTURE, 'w') as f:
            json.dump(d, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        d = capture(jobs)
        old = json.load(open(FIXTURE))
        new_ = json.loads(json.dumps(d))
        if new_ == old:
            print('MATCH')
        else:
            for k in old:
                if old.get(k) != new_.get(k):
                    print('DIFF in', k)
            sys.exit(1)
    elif cmd in ('direct', 'phases', 'natural', 'payload'):
        globals()['phase_' + cmd](jobs)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
