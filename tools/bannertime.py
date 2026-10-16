# -*- coding: utf-8 -*-
"""M7.56 -- $98B5's ROUND BANNER, WRITE BY WRITE: where every byte of "ROUND n / READY !" lands
in main-loop T, and what the frame interrupts do while it is up.

roundbanner.py (M7.28) measured WHAT the banner draws and erases, roundstart.py measured it END
TO END (256 iterations, the erase, 50..59 frames of wall clock) and rounddrain.py its MAIN-LINE
T (BB_BANNER_T.LOOP).  None says WHEN inside it a byte is written, and the port drew the banner
256 times and erased it inside ONE call -- so the page never showed it.  On the machine it is up for the whole ~40 frames of main-line T, and BOTH ISR
gates are OPEN ($FEC4 = the settle window $9884 armed, $FEC5 = $98AF's $2A): the enemies settle
in under it.  This oracle records:

  direct    the title hand-off (rounddrain's S0 world, key '1') stopped at $98B5, then $98B5..$8D0C
            with interrupts OFF.  EXACT: a plain Simulator with fast_djnz / fast_ldir OFF and no
            contention, so every instruction -- every LDIR iteration -- is its own T stamp.
            CONTENDED: the harness's own simulator at eight frame phases.  Every write is classed
            by hurryblock.Tracer --
               G  $8052: $802E's glyph blit (address, CHARACTER CODE, GLYPH ROW) -- never the
                  byte, which is the SPECTRUM ROM's; the port draws BB_BANNER_FONT
               R  $995C: $995A's attribute run (address, value)
               E  $9910: the erase's LDIR out of the shadow (address only)
               A  $9932: the erase's attribute, re-derived from the colour shadow (address, value)
               O  any other write outside the stack
            Recorded: iteration 0's writes with T from ITS $98BC, the $98BC T of all 256
            iterations, the erase's writes with T from each $9904 entry, the two $9904 entries,
            $98F0 and $8D0C.  Asserted: every iteration writes the same sequence at the same
            offsets.  Also: the string poked to other characters (the T does not move: $802E's
            path does not look at the code), and round 81 ($98B8 CP $51 / JR z: the erase only).
  natural   the hand-off (keys '1' and '2'), interrupts ON, contended, $98B5 to $8D0C: every ISR
            bracketed (the main loop's T at it, $8D72..RET, the gates, the parity), the MAIN-LINE
            T of every $98BC and $9904 (wall T less the ISRs before it), a RAM diff across every
            ISR -- which must change NO byte the banner's main line READS (the run-ahead premise
            the port rests on) -- and every banner cell an ISR repaints (a sprite crossing it).
  inplay    the same on in-play advances: from the hand-off's first loop top, ten frames, then
            $FECD := N and rounds 2..N+1 back to back -- 88-tick settle windows, where the
            enemies descend under the banner.

NO ROM BYTE IS STORED: glyph writes carry (code, row).  The erase's display bytes are the
shadow's and are not stored either.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/bannertime.py capture [--jobs N]   -> build/bannertime_fixture.json
        python tools/bannertime.py verify  [--jobs N]   re-run and diff against the fixture
        python tools/bannertime.py direct|natural|inplay
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import hurryblock as HB                  # its Mem / port hooks and its Tracer (EVT, CHAIN swapped)
import rounddrain as RD                  # the S0 world, the hand-off and the ISR ledger
import harness
from harness import Harness, PC, T, SP, IFF
from skoolkit.simulator import Simulator
import portconfig as pc

FIXTURE = 'build/bannertime_fixture.json'
FRAME_T = 69888
PHASES = [k * (FRAME_T // 8) for k in range(8)]
ENTRY, ITER, LOOP_TOP = 0x98B5, 0x98BC, 0x8D0C
ROUND = 0x8609
KEYS = ('1', '2')
INPLAY_N = 6                             # rounds 2..7 after each hand-off

# the banner's main-line events
EVT = {0x98B5: 'entry', 0x98BC: 'iter', 0x98C4: 'print1', 0x98CE: 'attr1', 0x98D4: 'print2',
       0x98DE: 'attr2', 0x98E4: 'erase_hl', 0x9904: 'erase', 0x98F0: 'tail'}
HB.EVT = EVT
HB.CHAIN = {}

# the code the banner's main line runs: $98B5..$9903, $802E's printer and its two cell writers,
# $995A, and $9904 with its $9938 helper
BANNER_PC = (set(range(0x98B5, 0x9904)) | set(range(0x802E, 0x8070)) |
             set(range(0x995A, 0x9961)) | set(range(0x9904, 0x9940)))
# the cells it writes: rows $484C and $488C, ten columns, eight pixel rows; $594C and $598C
CELLS = sorted([base + (r << 8) + c for base in (0x484C, 0x488C) for r in range(8) for c in range(10)] +
               [base + c for base in (0x594C, 0x598C) for c in range(10)])
CELL_SET = set(CELLS)


class Fail(Exception):
    pass


# ---------------------------------------------------------------- the main line's READS
READS = None                             # the addresses the banner's main line reads, while a set
TRC = None                               # the tracer whose in_isr says main line or ISR
_hb_get = harness.Mem.__getitem__


def _getitem(self, i):
    if READS is not None and TRC is not None and TRC.in_isr is None:
        if self.sim.registers[PC] in BANNER_PC:
            READS.add(i)
    return _hb_get(self, i)


harness.Mem.__getitem__ = _getitem


# ---------------------------------------------------------------- worlds
def to_98b5(key, hold=3):
    """rounddrain.handoff to $97F8, then on to $98B5 through the machine's own frames"""
    h = RD.s0()
    r = h.sim.registers
    fd = h.frame_duration
    h.ports.press(RD.KEYMAP[key][0], RD.keymask(RD.KEYMAP[key][1]))
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
    RD.ledger(h, lambda p, i: p == ENTRY)
    return h


def snap_of(h):
    return bytes(h.memobj.m), list(h.sim.registers)


def rebuild(snap, exact):
    """a fresh harness holding the snapshot; EXACT is a plain Simulator with fast_djnz and
    fast_ldir OFF (every LDIR iteration its own step and its own T) and no contention"""
    mem, regs = snap
    h = Harness(contended=True)
    h.load_state_file(pc.state_path('round1_48'))
    h.memobj.m[0x4000:] = mem[0x4000:]
    h.sim.registers[:] = regs
    if exact:
        sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
        sim.registers[:] = regs
        h.sim = sim
        h.memobj.sim = sim
        sim.set_tracer(h.ports)
        h.frame_duration, h.int_active = sim.frame_duration, sim.int_active
    return h


def tag_t(ev, tag):
    return [e[0] for e in ev if e[1] == tag]


# ---------------------------------------------------------------- direct
def one_direct(args):
    snap, exact, phase, poke = args
    h = rebuild(snap, exact)
    m, r = h.memobj.m, h.sim.registers
    r[IFF] = 0
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    if poke == 'r81':
        m[ROUND] = 0x51
    elif poke == 'bits':
        # bit 5 of the colour shadow FLIPPED under every attribute cell the erase re-derives
        for a in CELLS:
            if a >= 0x5800:
                m[a + 0xA000] ^= 0x20
    elif poke == 'string':
        # every printable character of both strings moved to another: '0'..'9' and 'A'..'Z'
        for a in range(0x9A06, 0x9A1C):
            if 0x30 <= m[a] <= 0x5A:
                m[a] = 0x30 + (m[a] - 0x30 + 7) % 43
    tr = HB.Tracer(h, r[T])
    stop = tr.run({LOOP_TOP} | HB.GUARD, limit=4 * 10 ** 6, interrupts=False)
    if stop != LOOP_TOP:
        raise Fail('direct: stopped at $%04X' % stop)
    ev = tr.events
    its = tag_t(ev, 'iter')
    ers = tag_t(ev, 'erase')
    ws = [w for w in tr.writes if not w[3]]
    out = {'exact': exact, 'phase': phase, 'poke': poke, 'cost': r[T] - tr.t0,
           'iter_t': its, 'erase_at': ers, 'tail_at': tag_t(ev, 'tail'),
           'string': [m[a] for a in range(0x9A06, 0x9A1C)] if poke == 'string' else None}
    # iteration by iteration: the same writes at the same offsets from its $98BC?
    bounds = its + (ers[:1] or [out['cost']])
    per = []
    for k in range(len(its)):
        lo, hi = bounds[k], bounds[k + 1]
        per.append([[w[0] - lo] + w[1:3] + w[4:] for w in ws if lo <= w[0] < hi])
    out['same_every_iteration'] = all(p == per[0] for p in per) if per else None
    out['writes0'] = per[0] if per else []
    out['writes_per_iteration'] = sorted(set(len(p) for p in per))
    er = []
    for k, e0 in enumerate(ers):
        hi = ers[k + 1] if k + 1 < len(ers) else out['cost']
        er.append([[w[0] - e0] + w[1:3] + w[4:] for w in ws if e0 <= w[0] < hi])
    out['erase'] = er
    out['other'] = [w for w in ws if w[2] not in ('G', 'R', 'E', 'A')]
    out['n_writes'] = len(ws)
    d = [its[k + 1] - its[k] for k in range(len(its) - 1)]
    out['periods'] = sorted(set(d))
    if not exact:
        out.pop('writes0')
        out.pop('erase')
    return out


def phase_direct(jobs=8):
    snap = snap_of(to_98b5('1'))
    jl = [(snap, True, None, None), (snap, True, None, 'string'), (snap, True, None, 'r81'), (snap, True, None, 'bits')]
    jl += [(snap, False, ph, None) for ph in PHASES] + [(snap, False, None, None)]
    jl += [(snap, False, ph, 'r81') for ph in PHASES]
    with ProcessPoolExecutor(max_workers=min(jobs, len(jl))) as ex:
        res = list(ex.map(one_direct, jl))
    ex_, st_, r81, bits = res[0], res[1], res[2], res[3]
    con = res[4:4 + len(PHASES)]
    own = res[4 + len(PHASES)]
    r81c = res[5 + len(PHASES):]
    for x in (ex_, st_):
        if not x['same_every_iteration'] or len(x['iter_t']) != 256:
            raise Fail('direct: the iterations differ (%s, %d)' % (x['same_every_iteration'], len(x['iter_t'])))
    out = {'exact': ex_,
           'string_moved': {'cost': st_['cost'], 'iter_t_same': st_['iter_t'] == ex_['iter_t'],
                            'erase_at_same': st_['erase_at'] == ex_['erase_at'],
                            'codes_moved': sorted(set(w[3] for w in st_['writes0'] if w[2] == 'G')) !=
                                           sorted(set(w[3] for w in ex_['writes0'] if w[2] == 'G'))},
           'r81': {'cost': r81['cost'], 'iters': len(r81['iter_t']), 'erase_at': r81['erase_at'],
                   'n_writes': r81['n_writes'], 'erase': r81['erase']},
           'r81_contended': [{'phase': c['phase'], 'cost': c['cost'], 'erase_at': c['erase_at']} for c in r81c],
           'bits': {'cost': bits['cost'], 'erase_at': bits['erase_at'], 'erase': bits['erase']},
           'contended': con, 'own_phase': own}
    print('direct EXACT: cost %d, iterations %d, periods %s, $98BC[0] %d, erases at %s, tail %s, writes %d '
          '(%s per iteration), other %s' % (ex_['cost'], len(ex_['iter_t']), ex_['periods'], ex_['iter_t'][0],
                                            ex_['erase_at'], ex_['tail_at'], ex_['n_writes'],
                                            ex_['writes_per_iteration'], ex_['other']))
    print('   string moved: cost %d, same T %s/%s, codes moved %s' % (
        st_['cost'], out['string_moved']['iter_t_same'], out['string_moved']['erase_at_same'],
        out['string_moved']['codes_moved']))
    print('   bit 5 flipped under the cells: cost %d (%+d), erases at %s, attribute offsets %s' % (
        bits['cost'], bits['cost'] - ex_['cost'], bits['erase_at'], [w[0] for w in bits['erase'][0] if w[2] == 'A']))
    print('   round 81: cost %d, %d iterations, erases at %s, %d writes' % (
        r81['cost'], len(r81['iter_t']), r81['erase_at'], r81['n_writes']))
    for c in con + [own]:
        print('   CONTENDED phase %s: cost %d, periods %d..%d, $98BC[0] %d, erases at %s' % (
            c['phase'], c['cost'], min(c['periods']), max(c['periods']), c['iter_t'][0], c['erase_at']))
    for c in r81c:
        print('   ROUND 81 CONTENDED phase %s: cost %d, erases at %s' % (c['phase'], c['cost'], c['erase_at']))
    return out


# ---------------------------------------------------------------- natural
def main_of(t, isrs):
    """wall T from $98B5 -> main-line T: less every ISR that ended at or before it"""
    return t - sum(x[2] - x[0] for x in isrs if x[2] <= t)


def banner_record(h, label):
    """$98B5 to $8D0C, interrupts ON: the ISR ledger, the main-line landmarks, the premise"""
    global READS, TRC
    r = h.sim.registers
    t0 = r[T]
    rnd = h.memobj.m[ROUND]
    tr = HB.Tracer(h, t0)
    READS, TRC = set(), tr
    try:
        stop = tr.run({LOOP_TOP} | HB.GUARD, limit=8 * 10 ** 6, interrupts=True, snap_isr=True)
    finally:
        reads, READS, TRC = READS, None, None
    if stop != LOOP_TOP:
        raise Fail('%s: stopped at $%04X' % (label, stop))
    isrs = tr.isrs
    ev = tr.events
    ws = [w for w in tr.writes if not w[3]]
    tend = r[T] - t0
    rows, violations, intr = [], set(), []
    stack, screen = set(), set()
    for x in isrs:
        sp = x[6]
        diff = x[7]
        stk = [a for a in diff if sp - 64 <= a < sp + 2]
        stack.update(stk)
        rest = [a for a in diff if not (sp - 64 <= a < sp + 2)]
        # the NEGATIVE CONTROL for 'intrusions': the ISRs do repaint the screen, elsewhere
        screen.update(a for a in rest if 0x4000 <= a < 0x5B00)
        violations.update(a for a in rest if a in reads)
        cells = [a for a in rest if a in CELL_SET]
        n_before = sum(1 for w in ws if w[0] < x[0])
        rows.append([main_of(x[0], isrs), x[2] - x[0], x[3], x[4], x[5], n_before, len(cells)])
        if cells:
            intr.append([len(rows) - 1, min(cells), max(cells), len(cells)])
    its = [main_of(t, isrs) for t in tag_t(ev, 'iter')]
    out = {'label': label, 'round': rnd, 't0_phase': t0 % FRAME_T,
           'isrs': rows, 'n_isrs': len(rows),
           'iter_main': its, 'erase_main': [main_of(t, isrs) for t in tag_t(ev, 'erase')],
           'tail_main': [main_of(t, isrs) for t in tag_t(ev, 'tail')],
           'end_main': main_of(tend, isrs), 'end_wall': tend,
           'first_write_main': main_of(ws[0][0], isrs) if ws else None,
           'last_write_main': main_of(ws[-1][0], isrs) if ws else None,
           'n_writes': len(ws),
           'reads_outside_code': len([a for a in reads if not (0x802E <= a < 0x9A00 or a < 0x4000)]),
           'premise_violations': ['%04X' % a for a in sorted(violations)],
           'intrusions': intr,
           'isr_screen_bytes': len(screen),
           'isr_attr_bytes': len([a for a in screen if a >= 0x5800]),
           'reads': len(reads)}
    print('%s (round %d): $98B5 %d T into its frame; %d ISRs, $8D72..RET %s; gates %s; parities %s; '
          'main-line end %d; iterations %d..%d apart; premise violations %s (of %d addresses read); '
          'intrusions %d ISRs; the ISRs repaint %d screen bytes elsewhere'
          % (label, rnd, out['t0_phase'], len(rows), sorted(set(x[1] for x in rows))[:3] + ['...'],
             sorted(set((x[2], x[3]) for x in rows)), ''.join(str(x[4]) for x in rows), out['end_main'],
             min(b - a for a, b in zip(its, its[1:])) if len(its) > 1 else 0,
             max(b - a for a, b in zip(its, its[1:])) if len(its) > 1 else 0,
             out['premise_violations'], len(reads), len(intr), len(screen)))
    return out


def one_natural(key):
    h = to_98b5(key)
    return banner_record(h, 'handoff %s' % key)


def phase_natural(jobs=8):
    with ProcessPoolExecutor(max_workers=min(jobs, len(KEYS))) as ex:
        res = list(ex.map(one_natural, KEYS))
    return dict(zip(KEYS, res))


def one_inplay(key):
    h = to_98b5(key)
    r, m = h.sim.registers, h.memobj.m
    banner_record(h, 'handoff %s (to the first loop top)' % key)
    t_end = r[T] + RD.F_PLAY * h.frame_duration
    RD.ledger(h, lambda p, i: p == LOOP_TOP and r[T] >= t_end)
    m[0xFECD] = INPLAY_N
    out = []
    for k in range(INPLAY_N):
        RD.ledger(h, lambda p, i: p == ENTRY)
        out.append(banner_record(h, 'inplay %s #%d' % (key, k)))
    return out


def phase_inplay(jobs=8):
    with ProcessPoolExecutor(max_workers=min(jobs, len(KEYS))) as ex:
        res = list(ex.map(one_inplay, KEYS))
    return dict(zip(KEYS, res))


# ---------------------------------------------------------------- main
def capture(jobs=8):
    return {'meta': {'frame_t': FRAME_T, 'entry': '98B5', 'iter': '98BC', 'end': '8D0C',
                     'cells': len(CELLS), 'inplay_n': INPLAY_N},
            'direct': phase_direct(jobs), 'natural': phase_natural(jobs), 'inplay': phase_inplay(jobs)}


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
    elif cmd == 'natural':
        phase_natural(jobs)
    elif cmd == 'inplay':
        phase_inplay(jobs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
