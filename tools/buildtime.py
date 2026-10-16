# -*- coding: utf-8 -*-
"""M7.59 -- $97F8's ROUND BUILD, WRITE BY WRITE: where every byte of the new level's scroll-in,
repaint and HUD lands in main-line T, and what the frame interrupts do while it runs.

rounddrain.py (RA3) measured the build's MAIN-LINE T per round (BB_ROUND_BUILD_T) and
scroll.py / roundbuild.py WHAT it draws; none says WHEN inside it a byte is written, and the port
ran the whole build inside ONE call -- the new level appeared at once, where the machine's
separator band rises and the new playfield scrolls up over ~53 frames (26 steps, ~138K T each),
is repainted, and the lives go up.  Both ISR gates are SHUT ($984B's clear walk zeroes
($FEC4)/($FEC5)), so every interrupt inside it only counts.  This oracle records:

  natural   interrupts ON, contended.  The title hand-off (keys 1 and 2: round 1, no scroll), then
            in play rounds 2..81 built back to back with ($FECD) -- sixteen chunks of ten, each
            from its own hand-off with ($8609) poked to the round before and the warp refused
            (+$5A bit 7 on both players), for 1P and 2P, and again with the build counter
            ($83EC) moved two tiles on (the out-of-sample set).  Every advance, $97F8 to $9887:
            the routine marks in MAIN-LINE T (wall T less the interrupts before it), every
            $840A (scroll step) and $8447 (push) entry, every interrupt (gates, cost), the
            addresses the interrupts write and every one the build's main line reads (the
            premise: none), the number of display writes.  Two advances keep every display
            write's main-line T (run-length coded).
  direct    EXACT: a plain Simulator (fast_djnz / fast_ldir OFF, no contention), interrupts OFF,
            from the natural run's own machine at $97F8 on twelve worlds -- rounds 1 (both
            keys), 2, 11, 21, 51, 81 (the 80 -> 81 build), 2P round 2, lives 0 and 7, letters
            collected, player one out.  The marks; every write of each routine the port stamps
            against its hook -- the separator row, the 26 steps and 22 pushes (asserted identical
            instance to instance and world to world), the repaint, the digits, the HUD (round 1),
            the lives, the rows, the letter panel -- as (offset, address).  NO VALUE IS STORED
            (the display carries the round digits, drawn from the ROM charset).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/buildtime.py capture [--jobs N]   -> build/buildtime_fixture.json
        python tools/buildtime.py verify  [--jobs N]   re-run and diff against the fixture
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import harness
from harness import Harness, PC, T, SP, IFF
from skoolkit.simulator import Simulator
import portconfig as pc
import rounddrain as RD
from keyprobe import KEYMAP, keymask

FIXTURE = 'build/buildtime_fixture.json'
GUARD = set(range(0xD000, 0xD300))
FRAME_T = 69888
COUNTERS = {0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE}
# the routine boundaries, by the PC of the CALL (or the fall-in) that starts each
MARK = {0x97F8: 'adv', 0x9858: 'clear', 0x9863: 'build', 0x7F2A: 'fpat', 0x7F2D: 'bg',
        0x7F30: 'scroll', 0x7F36: 'filler', 0x7F39: 'preroll', 0x7F3C: 'loop', 0x7F4E: 'repaint',
        0x7F51: 'digits', 0x7F54: 'r1', 0x7FC0: 'hud', 0x7F5B: 'lives', 0x7F5E: 'rows',
        0x9866: 'spawn', 0x9869: 'pinit', 0x986C: 'bolt', 0x986F: 'panel', 0x9872: 'b610',
        0x9887: 'halt'}
STEP, PUSH = 0x840A, 0x8447
KEEP = {('1', 0, 11), ('2', 0, 51)}           # advances whose every display write is kept
CHUNKS = list(range(1, 81, 10))               # $8609 poked to 1, 11, ... 71: rounds 2..81


class Fail(Exception):
    pass


WL = None
RL = None


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


def sha(s):
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def rle(ts):
    """main-line T of successive writes as [delta, count] runs"""
    out, p = [], 0
    for t in ts:
        d = t - p
        p = t
        if out and out[-1][0] == d:
            out[-1][1] += 1
        else:
            out.append([d, 1])
    return out


def trace(h, interrupts, keep_writes=True):
    """PC at $97F8 on the main line: run to $9887 (not executed).  Main-line T excludes every
    interrupt, bracketed from its acceptance to the return to the interrupted PC and SP."""
    global WL, RL
    sim = h.sim
    r, op, mem = sim.registers, sim.opcodes, sim.memory
    m = mem.m
    fd, ia = h.frame_duration, h.int_active
    if r[PC] != 0x97F8:
        raise Fail('trace not at $97F8 ($%04X)' % r[PC])
    t0, isr_t, cur = r[T], 0, None
    rec = dict(marks=[], steps=[], pushes=[], writes=[], isrs=[], isr_w=set(), hits=set(), disp=0,
               round0=m[0x8609], tile=m[0x83EC], players=2 if m[0xFD91] & 0x80 else 1,
               phase=r[T] % FRAME_T)
    WL, RL = [], []
    try:
        n = 0
        while True:
            p = r[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if cur is not None and p == cur[0] and r[SP] == cur[1]:
                d = r[T] - cur[2]
                rec['isrs'].append([cur[2] - t0 - isr_t, d, cur[3], cur[4]])
                isr_t += d
                cur = None
            tm = r[T] - t0 - isr_t
            if cur is None:
                nm = MARK.get(p)
                if nm is not None:
                    rec['marks'].append([nm, tm])
                    if p == 0x9887:
                        rec['end'] = tm
                        rec['round'] = m[0x8609]
                        return rec
                if p == STEP:
                    rec['steps'].append(tm)
                elif p == PUSH:
                    rec['pushes'].append(tm)
            if mem[p] == 0x76:
                raise Fail('a HALT inside the build at $%04X' % p)
            del WL[:]
            del RL[:]
            op[mem[p]]()
            n += 1
            if cur is not None:
                for a, v in WL:
                    if not (r[SP] - 64 <= a < r[SP] + 64):
                        rec['isr_w'].add(a)
            else:
                for a, v in WL:
                    if 0x4000 <= a < 0x5B00:
                        rec['disp'] += 1
                    if keep_writes and not (r[SP] - 64 <= a < r[SP] + 64):
                        rec['writes'].append((tm, a, p))
                for a in RL:
                    if a in rec['isr_w']:
                        rec['hits'].add(a)
            if interrupts and r[IFF] and r[T] % fd < ia:
                b, spb, tt = r[PC], r[SP], r[T]
                if sim.accept_interrupt(r, mem, p):
                    cur = (b, spb, tt, m[0xFEC4], m[0xFEC5])
            if n > 3 * 10 ** 6:
                raise Fail('no $9887')
    finally:
        WL = RL = None


def my_handoff(key, hold=3):
    """rounddrain.handoff to the title's $97F8, not past it"""
    h = RD.s0()
    r = h.sim.registers
    fd = h.frame_duration
    h.ports.press(KEYMAP[key][0], keymask(KEYMAP[key][1]))
    st = {'rel': None}

    def rel(p, isrs):
        if st['rel'] is None and p in (0x9790, 0x979E):
            st['rel'] = r[T] + hold * fd
        if st['rel'] is not None and st['rel'] > 0 and r[T] >= st['rel']:
            h.ports.release_all()
            st['rel'] = -1
    RD.ledger(h, lambda p, i: p == 0x97C7, rel)
    RD.ledger(h, lambda p, i: p == 0x97F8, rel)
    if st['rel'] != -1:
        raise Fail('the key was never released')
    return h


def snap(h):
    return bytes(h.memobj.m), list(h.sim.registers)


def summary(rec, keep):
    """what a natural advance stores"""
    ws = rec['writes']
    out = dict(round=rec['round'], players=rec['players'], tile=rec['tile'], phase=rec['phase'],
               marks=rec['marks'], steps=rec['steps'], pushes=rec['pushes'], end=rec['end'],
               n_isrs=len(rec['isrs']), isr_gates=sorted(set((i[2], i[3]) for i in rec['isrs'])),
               isr_costs=sorted(set(i[1] for i in rec['isrs'])),
               isr_other=sorted('%04X' % a for a in rec['isr_w'] - COUNTERS),
               hits=sorted('%04X' % a for a in rec['hits']), disp=rec['disp'])
    if keep:
        d = [w for w in ws if 0x4000 <= w[1] < 0x5B00]
        out['disp_t'] = rle([w[0] for w in d])
        out['disp_a'] = sha(''.join('%04X' % w[1] for w in d))
    return out


def one_chunk(args):
    key, shift, start = args
    h = my_handoff(key)
    res, snaps = [], {}
    rec = trace(h, True)                                  # the title's advance: round 1
    if start == 1 and shift == 0:
        res.append(summary(rec, False))
        snaps[1] = None                                   # the direct runs take their own
    r, m = h.sim.registers, h.memobj.m
    RD.ledger(h, lambda p, i: p == 0x8D0C)
    t_end = r[T] + RD.F_PLAY * h.frame_duration
    RD.ledger(h, lambda p, i: p == 0x8D0C and r[T] >= t_end)
    m[0x8609] = start
    m[0xFDDA] |= 0x80
    m[0xFDE4] |= 0x80
    if shift:
        m[0x83EC] = (m[0x83EC] + shift) % 5
    n = 10
    m[0xFECD] = n
    for k in range(n):
        RD.ledger(h, lambda p, i: p == 0x97F8)
        rnd = (m[0x8609] + 1) & 0xFF
        rec = trace(h, True)
        res.append(summary(rec, (key, shift, rnd) in KEEP))
    return dict(key=key, shift=shift, start=start, runs=res)


# ---------------------------------------------------------------- direct (exact)
def exact_from(state_bytes, regs):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path('round1_48'))
    h.memobj.m[:] = state_bytes
    sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
    sim.registers[:] = regs
    h.sim = sim
    h.memobj.sim = sim
    sim.set_tracer(h.ports)
    h.frame_duration, h.int_active = sim.frame_duration, sim.int_active
    return h


def world_at(key, start, pokes):
    """the natural run's own machine at $97F8, for the round after `start` (0: the title's)"""
    h = my_handoff(key)
    if start:
        trace(h, True, keep_writes=False)
        r, m = h.sim.registers, h.memobj.m
        RD.ledger(h, lambda p, i: p == 0x8D0C)
        t_end = r[T] + RD.F_PLAY * h.frame_duration
        RD.ledger(h, lambda p, i: p == 0x8D0C and r[T] >= t_end)
        m[0x8609] = start
        m[0xFDDA] |= 0x80
        m[0xFDE4] |= 0x80
        m[0xFECD] = 1
        RD.ledger(h, lambda p, i: p == 0x97F8)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    return snap(h)


def segments(rec):
    """the writes of each routine, as (offset from its hook, address); steps and pushes by entry"""
    marks = rec['marks']
    seg = {}
    ws = rec['writes']
    bounds = [(nm, t) for nm, t in marks]
    for i, (nm, t) in enumerate(bounds[:-1]):
        t1 = bounds[i + 1][1]
        seg.setdefault(nm, []).append([[w[0] - t, w[1]] for w in ws if t <= w[0] < t1])
    # the scroll's steps and pushes, each from its own entry
    ent = sorted([(t, 's') for t in rec['steps']] + [(t, 'p') for t in rec['pushes']])
    rp = dict(marks)['repaint'] if rec['steps'] else None
    inst = []
    for i, (t, kind) in enumerate(ent):
        t1 = ent[i + 1][0] if i + 1 < len(ent) else rp
        inst.append((kind, [[w[0] - t, w[1]] for w in ws if t <= w[0] < t1 and 0x4000 <= w[1] < 0x5B00]))
    return seg, inst


DIRECT = [
    ('r1_1p', '1', 0, []), ('r1_2p', '2', 0, []), ('r2', '1', 1, []), ('r11', '1', 10, []),
    ('r21', '1', 20, []), ('r51', '1', 50, []), ('r81', '1', 80, []), ('r2_2p', '2', 1, []),
    ('lives0', '1', 10, [(0xFDDC, 0)]), ('lives7', '1', 10, [(0xFDDC, 7)]),
    ('letters', '2', 10, [(0xFDE3, 0x15), (0xFDED, 0x2A)]), ('p1out', '2', 10, [(0xFD87, 0x00)]),
]


def one_direct(args):
    name, key, start, pokes = args
    b, regs = world_at(key, start, pokes)
    h = exact_from(b, regs)
    rec = trace(h, False)
    seg, inst = segments(rec)
    other = {}
    for nm in ('fpat', 'bg', 'clear', 'adv', 'build', 'scroll', 'preroll', 'loop', 'r1'):
        for s in seg.get(nm, []):
            other[nm] = [len(s), sum(1 for w in s if 0x4000 <= w[1] < 0x5B00)]
    out = dict(name=name, round=rec['round'], players=rec['players'], tile=rec['tile'],
               marks=rec['marks'], steps=rec['steps'], pushes=rec['pushes'], end=rec['end'],
               counts=other)
    for nm in ('filler', 'repaint', 'hud', 'lives', 'panel'):
        if nm in seg:                                     # the routines that write the display
            out[nm] = [[w for w in s if 0x4000 <= w[1] < 0x5B00] for s in seg[nm]]
    for nm in ('digits', 'rows', 'spawn', 'pinit', 'bolt', 'b610'):
        for s in seg.get(nm, []):                         # ...and the ones that do not
            other[nm] = [len(s), sum(1 for w in s if 0x4000 <= w[1] < 0x5B00)]
    out['inst'] = inst
    return out


def phase_direct(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        runs = list(ex.map(one_direct, DIRECT))
    # the scroll's steps and pushes: every instance the same, in every world
    step = push = None
    for r in runs:
        for kind, ws in r.pop('inst'):
            if kind == 's':
                if step is None:
                    step = ws
                elif ws != step:
                    raise Fail('%s: a step differs' % r['name'])
            else:
                if push is None:
                    push = ws
                elif ws != push:
                    raise Fail('%s: a push differs' % r['name'])
    # the step and push entries from the scroll mark: the same in every scrolling world
    tl = None
    for r in runs:
        if not r['steps']:
            continue
        s0 = dict(r['marks'])['scroll']
        t = [x - s0 for x in r['steps']] + [x - s0 for x in r['pushes']]
        t.append(dict(r['marks'])['repaint'] - s0)
        if tl is None:
            tl = t
        elif t != tl:
            raise Fail('%s: the scroll timeline differs' % r['name'])
    # the separator row and the repaint's display writes: the same in every world that runs them
    once = {}
    for r in runs:
        for nm in ('filler', 'repaint'):
            if nm in r:
                v = r.pop(nm)
                if len(v) != 1:
                    raise Fail('%s: %d %s instances' % (r['name'], len(v), nm))
                if nm not in once:
                    once[nm] = v[0]
                elif v[0] != once[nm]:
                    raise Fail('%s: the %s differs' % (r['name'], nm))
    print('direct: %d worlds; a step %d display writes, a push %d; the scroll %d T from $7F30 to $7F4E; ends %s'
          % (len(runs), len(step), len(push), tl[-1], [r['end'] for r in runs]))
    return dict(step=step, push=push, filler=once['filler'], repaint=once['repaint'], timeline=tl, runs=runs)


def phase_natural(jobs):
    jl = [(k, s, c) for k in ('1', '2') for s in (0, 2) for c in CHUNKS]
    with ProcessPoolExecutor(jobs) as ex:
        chunks = list(ex.map(one_chunk, jl))
    runs = [dict(r, key=c['key'], shift=c['shift']) for c in chunks for r in c['runs']]
    bad = [r for r in runs if r['hits'] or r['isr_other'] or [list(g) for g in r['isr_gates']] != [[0, 0]]]
    for r in bad:
        print('  PREMISE: key %s shift %d round %d gates %s costs %s isr_other %d %s hits %s phase %d'
              % (r['key'], r['shift'], r['round'], r['isr_gates'], r['isr_costs'], len(r['isr_other']),
                 r['isr_other'][:8], r['hits'][:8], r['phase']))
    print('natural: %d advances, rounds %d..%d, ISRs %d..%d, costs %s, premise broken %d'
          % (len(runs), min(r['round'] for r in runs), max(r['round'] for r in runs),
             min(r['n_isrs'] for r in runs), max(r['n_isrs'] for r in runs),
             sorted(set(c for r in runs for c in r['isr_costs'])), len(bad)))
    return dict(runs=runs, premise_broken=len(bad))


def capture(jobs):
    return dict(meta=dict(tool='tools/buildtime.py', chunks=CHUNKS, keep=sorted(list(k) for k in KEEP)),
                direct=phase_direct(jobs), natural=phase_natural(jobs))


def main():
    a = sys.argv[1:]
    jobs = 8
    if '--jobs' in a:
        i = a.index('--jobs')
        jobs = int(a[i + 1])
        del a[i:i + 2]
    cmd = a[0] if a else 'capture'
    if cmd == 'capture':
        d = json.loads(json.dumps(capture(jobs)))
        with open(FIXTURE, 'w') as f:
            json.dump(d, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        d = json.loads(json.dumps(capture(jobs)))
        old = json.load(open(FIXTURE))
        if d == old:
            print('MATCH')
        else:
            for k in old:
                if old.get(k) != d.get(k):
                    print('DIFF in', k)
            sys.exit(1)
    elif cmd in ('direct', 'natural'):
        globals()['phase_' + cmd](jobs)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
