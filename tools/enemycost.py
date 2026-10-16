"""M7.70 -- THE ENEMY HANDLERS' T ($AF31..$AFF6 and the walker $B028), RUN BY RUN, UNCONTENDED.

M7.68 left each enemy handler RUN at its fixture median (BB_AA60_RUN, PROVISIONAL); M7.69 made the
player's $AB38 exact.  This oracle records every run of the eight enemy handlers on an UNCONTENDED
machine, so a run's T is the sum of its instructions' own T and nothing else:

  T        the run: from the handler's entry ($AAEA RET z / $AAEB JP (HL), or for an ANGRY slot's second
           run the first run's RET into the handler again) to its return
  h        the handler address
  slot     the entity slot (IY = $FD80 + 10 * slot)
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of
           the instruction being executed
  post     every byte the run WRITES, at its final value -- the stack excepted
  rng      each `LD A,R` the run executes, as (site, A) -- the gate feeds them to BB_Rng
  path     the run's PCs where control did not fall through, for a diagnostic

Every 48K saved state, 300 frames, interrupts on, ab38cost's key script (the players move, so the
enemies chase); the rows keep up to KEEP runs of every distinct (handler, path, T).

Usage:  python tools/enemycost.py [--jobs N]          (-> build/enemycost_fixture.json)
        python tools/enemycost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A as RA, IYh, IYl
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/enemycost_fixture.json'
FRAMES = 300
KEEP = 2
HANDLERS = (0xAF31, 0xAF47, 0xAF5F, 0xAF77, 0xAF95, 0xAFAF, 0xAFC4, 0xAFF6)
DISPATCH = (0xAAEA, 0xAAEB)                   # RET z / JP (HL) -- or, doubled, the first run's own RET
FORCED = []                                   # (name, state, pokes[, actions[, held]]) as ab38cost
FORCED_FRAMES = 100
FORCED_KEEP = 4
# FORCED CALLS (declared): the arms no natural run reaches.  Each is ONE call of the slot's own handler
# on the machine -- a saved state, interrupts off, uncontended, IY the slot, the return $AAEC -- with
# the slot's fields, the tracked player's copy $B612/$B613 ($AAC9 writes it before every handler) and
# the shadow cells the run reads poked first: (name, state, slot, handler, pokes).  A cell is the
# colour shadow's $F800 + 32 * row + column.
def _cells(*cv):
    return tuple(cv)
def _slot(slot, x, y, f, a4, a8, a9):
    b = 0xFD80 + 10 * slot
    return ((b + 5, x), (b + 6, y), (b + 7, f), (b + 4, a4), (b + 8, a8), (b + 9, a9))
Q4 = lambda *a: _slot(4, *a)                    # r30_48 slot 4, type 4 ($AF77)
UNDER = _cells((0xFB26, 0), (0xFB27, 0), (0xFB06, 0), (0xFB07, 0))     # rows 25 / 24 at columns 6, 7
LEDGE_R = _cells((0xF948, 0x20), (0xF949, 0x20), (0xF928, 0), (0xF929, 0), (0xF92A, 0), (0xF94A, 0),
                 (0xB612, 0x18), (0xB613, 0x00))
LEDGE_L = _cells((0xF948, 0x20), (0xF949, 0x20), (0xF928, 0), (0xF929, 0), (0xF927, 0), (0xF947, 0),
                 (0xB612, 0x18), (0xB613, 0x00))
CALLS = [
    # type 4 falling at Y $BE, nothing under it: Y + 2 = $C0, $B3F0's wrap to 0 ($B3F3)
    ('q_fall_wrap', 'r30_48', 4, 0xAF77, Q4(0x30, 0xBE, 0xC1, 0x30, 0, 0) + UNDER),
    # ...at Y $BD: $BF, under $C0, so the handler's own $AF8F wrap ($AF90)
    ('q_tail_wrap', 'r30_48', 4, 0xAF77, Q4(0x30, 0xBD, 0xC1, 0x30, 0, 0) + UNDER),
    # grounded (row 10 solid under, row 9 clear) BELOW the player's row: the launch's RES 7 ($B40F)
    ('q_launch_below', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC1, 0x30, 0, 0) +
     _cells((0xF946, 0x20), (0xF947, 0x20), (0xF926, 0), (0xF927, 0), (0xB612, 0x80), (0xB613, 0x20))),
    # ...LEVEL with it, (IY+4) $FE so the $FE85 draw is under it, the player to the right: SET 0 ($B423)
    ('q_aim_right', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC0, 0xFE, 0, 0) +
     _cells((0xF946, 0x20), (0xF947, 0x20), (0xF926, 0), (0xF927, 0), (0xB612, 0x80), (0xB613, 0x40))),
    # ...with the row above SOLID: $B3DE JR nz taken, a fall
    ('q_blocked_up', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC1, 0x30, 0, 0) +
     _cells((0xF946, 0x20), (0xF947, 0x20), (0xF926, 0x20), (0xF927, 0))),
    # airborne on the TALL arc ((IY+9) bit 7 clear, $B439), moving right through clear cells
    ('q_tall', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC1, 0x30, 5, 1) +
     _cells(*[(0xF900 + 32 * r + c, 0) for r in range(0, 4) for c in range(6, 10)])),
    # airborne on the small arc, descending ((IY+8) $18), over a floor: the LANDING ($B45E)
    ('q_land', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC1, 0x30, 0x18, 0x81) +
     _cells((0xF928, 0), (0xF926, 0), (0xF927, 0), (0xF946, 0x20), (0xF947, 0x20), (0xF948, 0x20))),
    # ...and over the same floor with the row ABOVE it solid: $B459 JR nz taken, it flies on
    ('q_air_up', 'r30_48', 4, 0xAF77, Q4(0x30, 0x40, 0xC1, 0x30, 0x18, 0x81) +
     _cells((0xF928, 0x20), (0xF926, 0x20), (0xF927, 0x20), (0xF946, 0x20), (0xF947, 0x20), (0xF948, 0x20))),
    # airborne facing left at X $10: the move takes X under $10, so $B447 JP c skips the landing look
    ('q_low_x', 'r30_48', 4, 0xAF77, Q4(0x10, 0x40, 0xC0, 0x30, 5, 0x81) + _cells((0xF921, 0))),
    # type 3 flying DOWN at Y $C7 (its step 1): $C8, the flyer's $B2A7 wrap to 0
    ('fly_wrap_c8', 'r30_48', 2, 0xAFAF, ((0xFD94 + 5, 0x50), (0xFD94 + 6, 0xC7), (0xFD94 + 7, 0xC2)) +
     _cells((0xFB09, 0), (0xFB29, 0), (0xFB49, 0))),
    # ...at Y $C2: the flyer's last Y in $C0..$C7, under $C8 (no wrap)
    ('fly_low', 'r30_48', 2, 0xAFAF, ((0xFD94 + 5, 0x50), (0xFD94 + 6, 0xC2), (0xFD94 + 7, 0xC2)) +
     _cells((0xFB09, 0), (0xFB29, 0), (0xFB49, 0))),
    # AT THE HUD's EDGE, where $AED1's D crosses $18 (the $AED7 arm): row 3 solid under, row 2 clear --
    # a big-arc hop at Y 6 descending 3 (D = $18) LANDS, and its move searches for a floor from Y - 8 = -2
    ('hop_top', 'round1_48', 2, 0xAF31, _slot(2, 0x40, 0x06, 0xE1, 0x00, 0, 0x18) +
     _cells((0xF868, 0x20), (0xF869, 0x20), (0xF848, 0), (0xF849, 0))),
    # a walker standing on row 3 at Y 8 (D = $19), past the divider: the step's foot D $19, its wall D $17
    ('walk_top', 'round1_48', 2, 0xAF31, _slot(2, 0x40, 0x08, 0xE1, 0x80, 0, 0) +
     _cells((0xF868, 0x20), (0xF869, 0x20), (0xF86A, 0x20), (0xF848, 0), (0xF849, 0))),
    # type 4 grounded on row 3 at Y 8, above the player: the launch
    ('q_top', 'r30_48', 4, 0xAF77, Q4(0x30, 0x08, 0xC1, 0x30, 0, 0) +
     _cells((0xF866, 0x20), (0xF867, 0x20), (0xF846, 0), (0xF847, 0), (0xB612, 0x80), (0xB613, 0xA8))),
    # type 4 on the small arc at Y 8 descending 1 ((IY+8) 20): the landing look's D $18, over row 3
    ('q_land_top', 'r30_48', 4, 0xAF77, Q4(0x30, 0x08, 0xC1, 0x30, 20, 0x81) +
     _cells((0xF866, 0x20), (0xF867, 0x20), (0xF868, 0x20), (0xF846, 0), (0xF847, 0), (0xF848, 0))),
    # type 6 at a LEDGE, the player above: $B20D / $B25D hold $C9, so the RET steps off (right, left)
    ('t6_ledge_r', 'r40_48', 4, 0xAFF6, _slot(4, 0x40, 0x40, 0xE1, 0x80, 0, 0) + LEDGE_R),
    ('t6_ledge_l', 'r40_48', 4, 0xAFF6, _slot(4, 0x40, 0x40, 0xE0, 0x80, 0, 0) + LEDGE_L),
    # type 7 the same (its $B088 patch skips the divider; the step doubled to 4)
    ('t7_ledge_r', 'r60_48', 2, 0xAFC4, _slot(2, 0x40, 0x40, 0xC1, 0x10, 0, 0) + LEDGE_R),
]


def call_run(name, state, slot, handler, pokes, tab=None):
    """one forced call: the handler at its own entry, IY the slot, returning to $AAEC"""
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    rm.regs = r
    assert raw[0xB54E + 2 * slot] | raw[0xB54F + 2 * slot] << 8 == handler, name + ': not the slot handler'
    for a, v in pokes:
        raw[a] = v
    iy = 0xFD80 + 10 * slot
    r[IYh], r[IYl] = iy >> 8, iy & 0xFF
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = 0xEC, 0xAA
    r[SP] = sp; r[PC] = handler
    cur = {'t0': r[T], 'sp': sp, 'h': handler, 'slot': slot, 'seed': [], 'path': [], 'rng': [], 'last': None}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    for _ in range(100000):
        p = r[PC]
        if r[SP] == (sp + 2) & 0xFFFF:
            assert p == 0xAAEC, name + ': returned to $%04X' % p
            break
        if cur['last'] is not None and p != cur['last']:
            cur['path'].append(p)
        ldar = raw[p] == 0xED and raw[(p + 1) & 0xFFFF] == 0x5F
        t0 = r[T]
        op[raw[p]]()
        if ldar:
            cur['rng'].append((p, r[RA]))
        cur['last'] = B._fall(raw, p)
        if tab is not None:
            tab.setdefault(p, set()).add((r[T] - t0, r[PC]))
    else:
        raise AssertionError(name + ': no return')
    rm.rec = None
    cur['T'] = r[T] - cur['t0']
    return cur


class RecMem(B.RecMem):
    """ab38cost's recorder, but $FE85 LD HL,nn's OPERAND is the PRNG's state, not code: a run that
    draws from it reads $FE86/$FE87 as data, so they enter the seed like any other read"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen and self.regs[PC] == 0xFE85                 and i in (0xFE86, 0xFE87):
            self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def run(name, pokes=(), frames=FRAMES, tab=None, actions=None, hold=()):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(name))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    rm.regs = r
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    for a, v in pokes:
        raw[a] = v(raw[a]) if callable(v) else v
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    acts = actions or B.ACTIONS
    nextf = r[T]
    runs, cur, prev = [], None, 0
    while r[T] < t_end:
        if hold and r[T] >= nextf:
            for a, v in hold:
                raw[a] = v
            nextf += fd
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in acts[ki % len(acts)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and r[SP] == (cur['sp'] + 2) & 0xFFFF:
            rm.rec = None
            cur['T'] = r[T] - cur['t0']
            runs.append(cur); cur = None
        if cur is None and p in HANDLERS and (prev in DISPATCH or raw[prev] == 0xC9):   # a doubled run's second: the first's RET
            iy = h.iy()
            assert 0xFD94 <= iy < 0xFE20 and (iy - 0xFD80) % 10 == 0, 'IY $%04X' % iy
            cur = {'t0': r[T], 'sp': r[SP], 'h': p, 'slot': (iy - 0xFD80) // 10,
                   'seed': [], 'path': [], 'rng': [], 'last': None}
            rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = r[SP]
        elif cur is not None and cur['last'] is not None and p != cur['last']:
            cur['path'].append(p)
        prev = p
        if raw[p] == 0x76:
            h._fast_halt()
            if cur is not None: cur['last'] = None
        else:
            t0 = r[T]
            ldar = raw[p] == 0xED and raw[(p + 1) & 0xFFFF] == 0x5F
            op[raw[p]]()
            if cur is not None:
                if ldar:
                    cur['rng'].append((p, r[RA]))
                cur['last'] = B._fall(raw, p)
                if tab is not None:
                    tab.setdefault(p, set()).add((r[T] - t0, r[PC]))
            if r[IFF] and r[T] % fd < ia:
                h.sim.accept_interrupt(r, rm, p)
    return runs


def row(name, x):
    return {'state': name, 'h': x['h'], 'slot': x['slot'], 'T': x['T'],
            'seed': ''.join('%04x%02x' % (a, v) for a, v in sorted(x['seed'])),
            'post': ''.join('%04x%02x' % (a, v) for a, v in sorted(x['post'].items())),
            'rng': [[s, v] for s, v in x['rng']],
            'path': ' '.join('%04x' % q for q in x['path'])}


FORCED_POKES = {f[0]: f[2] for f in FORCED}
FORCED_ACTS = {f[0]: f[3] for f in FORCED if len(f) > 3}
FORCED_HOLD = {f[0]: f[4] for f in FORCED if len(f) > 4}
CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, frames, tag = job
    if frames is None:                            # a forced call
        return [row(tag, call_run(*CALLS_BY[tag]))]
    return [row(tag or name, x) for x in run(name, FORCED_POKES[tag] if tag else (), frames,
                                             actions=FORCED_ACTS.get(tag), hold=FORCED_HOLD.get(tag, ()))]


def measure(jobs):
    work = [(s, FRAMES, None) for s in A.STATES] + [(f[1], FORCED_FRAMES, f[0]) for f in FORCED] + \
           [(c[1], None, c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    rows, per, forced, npaths = [], collections.Counter(), collections.Counter(), set()
    byh = collections.defaultdict(list)
    for (s, _, tag), rs in zip(work, res):
        for x in rs:
            byh['%04x' % x['h']].append(x['T'])
            k = '%04x ' % x['h'] + x['path']
            if not tag: npaths.add(k)
            # the T too: a conditional RET that falls through and then RETs to the same place leaves the
            # same branch targets as one that is taken (the type-4 arc's end, the left homing fall)
            key = (tag or '') + k + ' %d' % x['T']
            if per[key] < (FORCED_KEEP if tag else KEEP):
                per[key] += 1
                if tag: forced[tag] += 1
                rows.append(x)
    hs = {k: {'runs': len(v), 'lo': min(v), 'hi': max(v)} for k, v in sorted(byh.items())}
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [f[0] for f in FORCED] + [c[0] for c in CALLS], 'forced_frames': FORCED_FRAMES,
            'runs': sum(v['runs'] for v in hs.values()), 'paths': len(npaths), 'handlers': hs,
            'forced_rows': dict(forced), 'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 12
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), indent=0)
    print('runs %d  paths %d  rows %d  forced %s' % (F['runs'], F['paths'], len(F['rows']), F['forced_rows']))
    for k, v in F['handlers'].items():
        print('  $%s  runs %5d  T %d..%d' % (k.upper(), v['runs'], v['lo'], v['hi']))


if __name__ == '__main__':
    main()
