# -*- coding: utf-8 -*-
"""M7.83 -- $A09A's FLOOD TICK ($A127), WRITE BY WRITE: what every step of the blue-cross flood
ramp costs, where each byte it writes lands in main-line T, and what the frame interrupts do
while it runs.

The port's effectFlood charged NOTHING for a flood tick (the idle path's 90 T sit in BB_PASS_T)
and wrote its row ($A13F LD B,$20 / JR $A0ED -- the painter's body entered at its loop) and its
payload ($A151 JP $A0F5) at the call.  stormtime.py timed the thunder's ticks and its payload;
this is the same measurement for the flood's door.  This oracle records:

  direct    round1_48 with the flood armed (($FECE) := v for EVERY v in 1..255, the storm off,
            the edge detector primed), $A09A called with interrupts OFF.  EXACT: a plain
            Simulator, fast_djnz / fast_ldir OFF, no contention.  Each run: its exit (row,
            ramping, payload, past, disarm -- by the PC that returns), the end T, every write but
            the stack's (T from the entry, address, value), $A0ED's entry, DI / EI / the open
            point (the instruction after the EI ended), ($FECE) after.
  phases    three row ticks (the top row, a middle row, the bottom row) and a payload tick at
            sixteen frame phases, contended, interrupts off: the end and every store's T.
  sweep     a payload tick, contended, the interrupt line rising `off` T after the entry, over a
            sweep of offsets: taken (and where) or lost.
  natural   interrupts ON, contended, in play: the flood armed two steps early and run to the
            row tick (v = $10 at the entry) and to the payload tick (v = $C7).  FREE on seven
            worlds; FORCED on round1_48 and r50_48 at sixteen entry phases (none straddles the
            interrupt) and at eight EDGE phases 20..1,640 T before it (the tick straddles it).  Every store in
            MAIN-LINE T, every interrupt (main-line T, wall cost, gates, parity), the end, and
            THE PREMISE: the interrupts write and read no attribute byte, read no byte before the
            tick's main line writes it, and write none the main line reads after.

NO ROM BYTE IS STORED (the row writes $2F, the payload 10 and its flags).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/floodtime.py capture [--jobs N]   -> build/floodtime_fixture.json
        python tools/floodtime.py verify  [--jobs N]   re-run and diff against the fixture
        python tools/floodtime.py direct|phases|sweep|natural
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import stormtime as st                   # its instrumentation (reads, writes, OUTs) and worlds
from stormtime import Fail, new, sha, deltas, FRAME_T, ISR_RET, GUARD, ATTR, FORCED, FREE
import sfxcensus
from harness import PC, T, SP, IFF

FIXTURE = 'build/floodtime_fixture.json'
ENTRY, BODY, STORE = 0xA09A, 0xA0ED, 0xA0F0
ROW_V = (0x10, 0x58, 0xAB)               # the bottom row $5AE0, a middle one, the top $5840
PAY_V = 0xC7                             # $C7 + 3 - 2 = $C8: the payload
EDGE = [FRAME_T - d for d in (20, 150, 400, 800, 1200, 1310, 1500, 1640)]   # the tick straddles the interrupt
SWEEP = list(range(100, 200)) + list(range(200, 1260, 53)) + list(range(1260, 1380))


def flood_world(m, v):
    m[0xFECE] = v
    m[0xFECF] = 0                        # the storm off (the flood wins anyway)
    m[0xA09E] = m[0x8DBD] ^ 0x01         # $A09D CP n: n is $A09E -- a CHANGE


def call(h, v, off=None):
    """$A09A called with ($FECE) = v, a sentinel return pushed.  Every instruction stepped;
    with `off`, the frame's interrupt line rises `off` T after the entry and the first
    instruction end with IFF set and the line up, not straight after an EI, is where the
    machine takes it -- recorded, and the run stops there."""
    m = h.memobj.m
    flood_world(m, v)
    r = h.sim.registers
    if off is not None:
        r[T] = (r[T] // FRAME_T + 2) * FRAME_T - off
    sp = (r[SP] - 2) & 0xFFFF
    s = h.SENTINELS[0]
    m[sp], m[sp + 1] = s & 0xFF, s >> 8
    r[SP] = sp
    r[PC] = ENTRY
    t0, fd, ia = r[T], h.frame_duration, h.int_active
    out = dict(v=v, exit=None, body=None, di=None, ei=None, open=None, writes=[], taken=None)
    st.WL = []
    try:
        while True:
            p = r[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if p == s:
                break
            if p == BODY and out['body'] is None:
                out['body'] = r[T] - t0
            del st.WL[:]
            tm = r[T] - t0
            h.sim.opcodes[m[p]]()
            for a, x in st.WL:
                if not (r[SP] - 64 <= a < r[SP] + 64):
                    out['writes'].append([tm, a, x])
            if p == 0xA0F5:
                out['di'] = r[T] - t0
            elif p == 0xA10E:
                out['ei'] = r[T] - t0
            elif p == 0xA10F:
                out['open'] = r[T] - t0
            if off is not None and r[IFF] and r[T] % fd < ia and m[p] != 0xFB:
                out['taken'] = r[T] - t0
                break
            if r[T] - t0 > 20000:
                raise Fail('the tick ran past 20,000 T')
    finally:
        st.WL = None
    out['end'] = r[T] - t0
    out['fece'] = m[0xFECE]
    return out


def classify(x):
    v = x['v']
    if v + 3 > 0xFF:
        return 'disarm'
    if x['body'] is not None:
        return 'row'
    if x['di'] is not None:
        return 'payload'
    a = v + 3 - 2
    return 'ramping' if a < 0xC8 else 'past'


def one_direct(v):
    h, m = new('round1_48', False)
    x = call(h, v)
    x['exit'] = classify(x)
    del x['taken']
    return x


def phase_direct(jobs=8):
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_direct, range(1, 256)))
    by = {}
    for x in runs:
        by.setdefault(x['exit'], set()).add(x['end'])
    for k in sorted(by):
        n = sum(1 for x in runs if x['exit'] == k)
        print('direct %-8s %3d ticks, end %s' % (k, n, sorted(by[k])))
    for x in runs:
        if x['exit'] == 'row':
            ws = x['writes'][1:]                      # [0] is $A09F's operand store, [1] $A129's
            row = (0x5AE0 - ((x['v'] + 3) & 0xF8) * 4) & 0xFFFF
            if [w[1] for w in ws[1:]] != list(range(row, row + 32)) or any(w[2] != 0x2F for w in ws[1:]):
                raise Fail('v=$%02X: the row' % x['v'])
            if [w[0] - ws[1][0] for w in ws[1:]] != [41 * i for i in range(32)]:
                raise Fail('v=$%02X: the row is not 41 T a cell' % x['v'])
    rows = [x for x in runs if x['exit'] == 'row']
    pays = [x for x in runs if x['exit'] == 'payload']
    print('row: body at %s, first store %s; payload: DI %s EI %s open %s, %d writes' % (
        sorted(set(x['body'] for x in rows)), sorted(set(x['writes'][2][0] for x in rows)),
        sorted(set(x['di'] for x in pays)), sorted(set(x['ei'] for x in pays)),
        sorted(set(x['open'] for x in pays)), len(pays[0]['writes'])))
    return runs


def one_phase(args):
    v, ph = args
    h, m = new('round1_48', True)
    h.sim.registers[T] = (h.sim.registers[T] // FRAME_T) * FRAME_T + ph
    x = call(h, v)
    return dict(v=v, phase=ph, end=x['end'], t=deltas([w[0] for w in x['writes']]))


def phase_phases(jobs=8):
    jl = [(v, ph) for v in ROW_V + (PAY_V,) for ph in FORCED]
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_phase, jl))
    for v in ROW_V + (PAY_V,):
        e = [r['end'] for r in runs if r['v'] == v]
        print('phases v=$%02X: end %d..%d' % (v, min(e), max(e)))
    return runs


def one_sweep(off):
    h, m = new('round1_48', True)
    x = call(h, PAY_V, off)
    return dict(off=off, taken=x['taken'], di=x['di'], open=x['open'])


def phase_sweep(jobs=8):
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_sweep, SWEEP))
    lost = [x['off'] for x in runs if x['taken'] is None and x['off'] <= x['open']]
    print('sweep: %d of %d offsets lost, %s..%s' % (len(lost), len(runs), min(lost) if lost else None,
                                                    max(lost) if lost else None))
    return runs


def trace(h, want, force=None, limit_frames=40):
    """interrupts ON: run until the main line enters $A09A with ($FECE) = want and a change
    pending, then record to its RET (stormtime.trace's shape, the flood's door)"""
    sim = h.sim
    regs, opcodes, mem = sim.registers, sim.opcodes, sim.memory
    m = mem.m
    fd, ia = h.frame_duration, h.int_active
    t_end = regs[T] + limit_frames * FRAME_T
    in_isr, cur = None, None
    st.RL, st.WL = [], []
    RL, WL = st.RL, st.WL
    try:
        while regs[T] < t_end:
            p = regs[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if cur is None and in_isr is None and p == ENTRY and m[0xFECE] == want and m[0xA09E] != m[0x8DBD]:
                if force is not None:
                    regs[T] = (regs[T] // FRAME_T) * FRAME_T + force
                sp = regs[SP]
                cur = dict(t0=regs[T], sp=sp, ret=m[sp] | (m[sp + 1] << 8), isr_t=0,
                           phase=regs[T] % FRAME_T, writes=[], isrs=[], isr_w={}, isr_attr_r=0,
                           isr_r={}, mreads=[], mw={},
                           seed=dict(pool=[m[0xFED8 + 10 * k + 7] for k in range(12)]))
            del RL[:]
            del WL[:]
            tm = regs[T] - cur['t0'] - cur['isr_t'] if cur is not None else None
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
                        if not (regs[SP] - 64 <= a < regs[SP] + 64):
                            cur['writes'].append([tm, a, v])
                            cur['mw'][a] = regs[T]
                    for a in RL:
                        cur['mreads'].append((regs[T], a, p))
            if in_isr is not None and p == ISR_RET:
                d = regs[T] - in_isr[0]
                if cur is not None:
                    cur['isrs'].append([in_isr[0] - cur['t0'] - cur['isr_t'], d] + in_isr[1:])
                    cur['isr_t'] += d
                in_isr = None
            if cur is not None and in_isr is None and regs[PC] == cur['ret'] and regs[SP] == cur['sp'] + 2:
                cur['end'] = regs[T] - cur['t0'] - cur['isr_t']
                return cur
            if regs[IFF] and regs[T] % fd < ia and mem[p] != 0xFB:   # none straight after EI
                in_isr = [regs[T], m[0xFEC4], m[0xFEC5], (m[0x8DBD] + 1) & 1]
                sim.accept_interrupt(regs, mem, p)
                if regs[PC] != 0xFFFF:
                    raise Fail('an interrupt went to $%04X' % regs[PC])
        raise Fail('no tick within %d frames' % limit_frames)
    finally:
        st.RL = st.WL = None


def one_natural(args):
    state, v, force = args
    h, m = new(state, True)
    m[0xFECF] = 0
    m[0xFECE] = (v - 6) if v < 0xAF else (v - 2)      # two steps first: the flood as the machine runs it
    c = trace(h, v, force=force)
    first = c['isr_w']
    hits = sorted(set('%04X@%04X' % (a, p) for (t, a, p) in c['mreads'] if a in first and t > first[a]))
    wall = c['end'] + c['isr_t']
    # the line rose inside and fell before the tick's end with nothing taking it (a line still up at
    # the RET's end is taken there -- after the call, as the port's interrupt runs)
    lost = c['phase'] + wall >= FRAME_T + h.int_active and not c['isrs']
    return dict(state=state, v=v, forced=force, phase=c['phase'], seed=c['seed'], end=c['end'], lost=lost,
                writes=c['writes'], isrs=c['isrs'],
                premise=dict(isr_addrs=len(first), isr_attr_w=sum(1 for a in first if a in ATTR),
                             isr_attr_r=c['isr_attr_r'], hits=hits,
                             isr_reads_main_w=sorted('%04X' % a for a in c['isr_r'] if a in c['mw']),
                             isr_read_first=sorted('%04X' % a for a in c['isr_r']
                                                   if a in c['mw'] and c['isr_r'][a] < c['mw'][a])))


def phase_natural(jobs=8):
    vs = (ROW_V[0], PAY_V)
    jl = ([(s, v, None) for v in vs for s in FREE] +
          [(s, v, ph) for v in vs for s in ('round1_48', 'r50_48') for ph in FORCED + EDGE])
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_natural, jl))
    bad = [r for r in runs if r['premise']['hits'] or r['premise']['isr_attr_w'] or r['premise']['isr_attr_r']
           or r['premise']['isr_read_first']]
    for v in vs:
        rs = [r for r in runs if r['v'] == v]
        print('natural v=$%02X: %d runs, end %d..%d main-line T, %s ISRs in the tick, gates %s, '
              'isr reads main writes %s'
              % (v, len(rs), min(r['end'] for r in rs), max(r['end'] for r in rs),
                 sorted(set(len(r['isrs']) for r in rs)),
                 sorted(set((i[2] != 0, i[3] != 0) for r in rs for i in r['isrs'])),
                 sorted(set(a for r in rs for a in r['premise']['isr_reads_main_w']))))
    for v in vs:
        f = [r for r in runs if r['v'] == v and r['forced'] in FORCED]
        print('v=$%02X forced: mean end %.2f over %d; lost at %s' % (
            v, sum(r['end'] for r in f) / len(f), len(f),
            sorted(set(FRAME_T - r['forced'] for r in runs if r['v'] == v and r['lost']))))
    print('premise: %d of %d runs break it' % (len(bad), len(runs)))
    for r in bad:
        print('  BROKEN', r['state'], hex(r['v']), r['forced'], r['premise'])
    return dict(runs=runs, premise_broken=len(bad))


def capture(jobs=8):
    return dict(meta=dict(tool='tools/floodtime.py', forced=FORCED, edge=EDGE, free=FREE, row_v=list(ROW_V), pay_v=PAY_V),
                direct=phase_direct(jobs), phases=phase_phases(jobs), sweep=phase_sweep(jobs),
                natural=phase_natural(jobs))


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
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(d, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        d = capture(jobs)
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        new_ = json.loads(json.dumps(d))
        if new_ == old:
            print('MATCH')
        else:
            for k in old:
                if old.get(k) != new_.get(k):
                    print('DIFF in', k)
            sys.exit(1)
    elif cmd in ('direct', 'phases', 'sweep', 'natural'):
        globals()['phase_' + cmd](jobs)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
