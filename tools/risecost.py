"""M7.76 -- THE BUBBLE RISE'S T ($B836), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL); M7.74 made the blow arm exact, M7.75 the draw.  This oracle records every
run of the rise arm, $B836 called from $B650 (a risen bubble's move: the marker clear $B6C8, the wind
read, the player contact $B8E5, the drift, the probe and its blocked re-roll, the marker write, the X
clamp), on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T:

  T        the run, $B836 to its return to $B653, LESS its two nested callees (below)
  sub      the nested callees' runs, apart: [name, T] for each -- 'erase' the $BF0A a push calls from
           $B952 (-> $B955), 'move' the $ADAA a bounce calls from $B9AA (-> $B9AD).  Both are exact in
           the engine already (cacheSetAndErase's return, adaaT): the gate checks them apart
  rng      each `LD A,R` the run executes, as (site, A) -- the blocked re-roll's $B88D
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of the
           instruction being executed, except the self-modified operands read as STATE (TRAPS #275):
           the erase's accumulator $A431
  post     every byte the run WRITES, at its final value -- the stack and the ROM excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7) -- the
           first clear after the rise transition reads its marker through (IY+2/3) = $02xx
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic
  iy       the slot (IY)

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (path, T).  The arms no natural
run reaches are FORCED CALLS (declared below): $B836 called once on the machine from a saved state with
slot 0 poked risen and the players poked, interrupts off, returning to $B653.

Usage:  python tools/risecost.py [--jobs N]          (-> build/risecost_fixture.json)
        python tools/risecost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl
from harness import A as RA
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/risecost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 1
ENTRY, CALLER, BACK = 0xB836, 0xB650, 0xB653
SUBS = {0xBF0A: ('erase', 0xB952, 0xB955), 0xADAA: ('move', 0xB9AA, 0xB9AD)}
STATE_OPS = {0xA430: (0xA431,)}     # $A430 ADD A,n: the erase's accumulator
SLOT0 = 0xFED8


def cell(x, y):
    return 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)


def _slot(x=0x60, y=0x60, wind=0, kind=0, mark=None, block=False):
    """slot 0 risen (+7 $C4) at X x, Y y, holding `kind`; the shadow cell under it carries the wind
    (bits 7-6 = wind << 5) and clear low bits; its marker pointer (+2/+3) at `mark` (default the cell
    + $21, as the last pass left it); `block` marks the post-drift cell occupied"""
    p = SLOT0
    m = cell(x, y) + 0x21 if mark is None else mark
    out = [(p + 7, 0xC4), (p + 5, x), (p + 6, y), (p + 9, kind), (p + 4, 0x40), (p + 2, m & 0xFF), (p + 3, m >> 8)]
    c = cell(x, y)
    out += [(c, wind << 5), (c + 0x21, 0)]
    if block:
        out.append(('block', 0))
    return out


def _pl(k, act=True, x=0x60, y=0x60, face=1, dirn=0, dying=False):
    """player k's block: +7 (bit 7 active, bit 0 facing right), +5 X, +6 Y, +8 the direction bits,
    +$5A bit 2 dying"""
    b = 0xFD80 + 10 * k
    return [(b + 7, (0x80 if act else 0) | (face & 1)), (b + 5, x), (b + 6, y), (b + 8, dirn),
            (b + 0x5A, 0x04 if dying else 0)]


NOP = _pl(0, act=False) + _pl(1, act=False)


def _resolve(pokes):
    """'block' marks the cell the drift lands on (computed from the slot's own X, Y and wind)"""
    out, d = [], dict((a, v) for a, v in pokes if a != 'block')
    for a, v in pokes:
        if a != 'block':
            out.append((a, v)); continue
        x, y = d[SLOT0 + 5], d[SLOT0 + 6]
        w = (d.get(cell(x, y), 0) >> 5) & 6
        dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][w // 2]
        c = cell((x + dx) & 0xFF, (y + dy) & 0xFF)
        out.append((c, (d.get(c, 0) & 0xE0) | 0x05))     # the low five bits: a marker; the wind kept
    return out


# FORCED CALLS (declared): (name, state, pokes).  The wind is the cell's bits 7-6 >> 5: 0 up, 2 right,
# 4 down, 6 left ($B8DB's table).
CALLS = [
    # the drift's Y wraps: up onto 0 -> $B7 ($B86A); down past $BF -> 1 ($B873)
    ('wrap_top', 'round1_48', _slot(y=0x01) + NOP),
    ('wrap_low', 'round1_48', _slot(y=0xBF, wind=4) + NOP),
    # the X clamp after the marker: below $10 -> $11 ($B8CE), $E1 and up -> $E0 ($B8D6)
    ('clamp_lo', 'round1_48', _slot(x=0x10, wind=6) + NOP),
    ('clamp_hi', 'round1_48', _slot(x=0xE0, wind=2) + NOP),
    # blocked: the re-roll from the pre-contact position; its own wrap ($B8AC): Y $BF re-rolled down to
    # $C0 (boris's R at $B88D draws direction 4 -- found by trying the saved states)
    ('blocked', 'round1_48', _slot(block=True) + NOP),
    ('blocked_wrap', 'boris', _slot(y=0xBF, block=True) + NOP),
    # ... and onto $BF exactly, kept ($B8AC's edge: Y $BE re-rolled down, the same draw)
    ('blocked_bf', 'boris', _slot(y=0xBE, block=True) + NOP),
    # the marker clear through a ROM pointer ($BEE8 parks +3 at 2)
    ('clear_rom', 'round1_48', _slot(mark=0x0250) + NOP),
    # the contact: inactive / dying players, no Y overlap / no X overlap
    ('p1_dying', 'round1_48', _slot() + _pl(0, dying=True) + _pl(1, act=False)),
    ('p1_noy', 'round1_48', _slot() + _pl(0, y=0x90) + _pl(1, act=False)),
    ('p1_nox', 'round1_48', _slot() + _pl(0, x=0xA0) + _pl(1, act=False)),
    ('p1_noy_lo', 'round1_48', _slot() + _pl(0, y=0x50) + _pl(1, act=False)),
    ('p1_nox_lo', 'round1_48', _slot() + _pl(0, x=0x40) + _pl(1, act=False)),
    # the touch pop: facing right / left, P1 / P2
    ('pop_r', 'round1_48', _slot() + _pl(0, x=0x58) + _pl(1, act=False)),
    ('pop_l', 'round1_48', _slot() + _pl(0, x=0x58, face=0) + _pl(1, act=False)),
    ('pop_p2', 'round1_48', _slot() + _pl(0, act=False) + _pl(1, x=0x58)),
    # the push: facing right pressing right into a right wind (nulled) / an up wind (kept); left into left
    ('push_r_w2', 'round1_48', _slot(wind=2) + _pl(0, x=0x52, dirn=4) + _pl(1, act=False)),
    ('push_r_w0', 'round1_48', _slot(wind=0) + _pl(0, x=0x52, dirn=4) + _pl(1, act=False)),
    ('push_l_w6', 'round1_48', _slot(wind=6) + _pl(0, x=0x6E, face=0, dirn=8) + _pl(1, act=False)),
    ('push_l_w4', 'round1_48', _slot(wind=4) + _pl(0, x=0x6E, face=0, dirn=8) + _pl(1, act=False)),
    # the push's own X clamp ($B977): left below $10 -> $11, right to $E1 -> $E0
    ('push_clamp_lo', 'round1_48', _slot(x=0x11) + _pl(0, x=0x1F, face=0, dirn=8) + _pl(1, act=False)),
    ('push_clamp_hi', 'round1_48', _slot(x=0xDF) + _pl(0, x=0xD1, dirn=4) + _pl(1, act=False)),
    # the bounce: not pressing, wind == B / the toggle 0 / wind 2 and 6 shove the player ($ADAA) / wind 0
    ('bounce_eq', 'round1_48', _slot(wind=2) + _pl(0, x=0x52) + _pl(1, act=False)),
    ('bounce_t0', 'round1_48', _slot(wind=6) + _pl(0, x=0x52) + _pl(1, act=False) + [(0xB62D, 0)]),
    ('bounce_w6', 'round1_48', _slot(wind=6) + _pl(0, x=0x52) + _pl(1, act=False) + [(0xB62D, 1)]),
    ('bounce_w2', 'round1_48', _slot(wind=2) + _pl(0, x=0x6E, face=0) + _pl(1, act=False) + [(0xB62D, 1)]),
    ('bounce_w0', 'round1_48', _slot(wind=0) + _pl(0, x=0x52) + _pl(1, act=False) + [(0xB62D, 1)]),
    ('bounce_w4', 'round1_48', _slot(wind=4) + _pl(0, x=0x52) + _pl(1, act=False) + [(0xB62D, 1)]),
    # both players on the bubble: the second tests the registers the first left
    ('both_push', 'round1_48', _slot(wind=0) + _pl(0, x=0x52, dirn=4) + _pl(1, x=0x6E, face=0, dirn=8)),
    ('both_bounce', 'round1_48', _slot(wind=6) + _pl(0, x=0x52) + _pl(1, x=0x6E, face=0) + [(0xB62D, 1)]),
]


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operands the run reads as STATE enter the seed"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = STATE_OPS.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _iy(r):
    return r[IYh] << 8 | r[IYl]


def _open(r, rm, sp):
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'prev': None, 'sub': [], 'open': None,
           'rng': [], 'iy': _iy(r)}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    return cur


def _step(r, op, raw, cur):
    p = r[PC]
    o = cur['open']
    if o is not None and p == o[1] and r[SP] == o[2]:
        cur['sub'].append([o[0], r[T] - o[3]]); cur['open'] = None
    if o is None and p in SUBS and cur['prev'] == SUBS[p][1]:
        cur['open'] = (SUBS[p][0], SUBS[p][2], (r[SP] + 2) & 0xFFFF, r[T])
    if cur['last'] is not None and p != cur['last']:
        cur['path'].append(p)
    ldar = raw[p] == 0xED and raw[(p + 1) & 0xFFFF] == 0x5F
    op[raw[p]]()
    if ldar:
        cur['rng'].append([p, r[RA]])
    cur['last'] = B._fall(raw, p); cur['prev'] = p


def _close(r, rm, cur):
    rm.rec = None
    assert cur['open'] is None
    cur['T'] = r[T] - cur['t0'] - sum(t for _, t in cur['sub'])
    return cur


def _machine(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def _done(r, cur):
    return cur['open'] is None and r[SP] == (cur['sp'] + 2) & 0xFFFF


def call_run(name, state, pokes):
    """one forced call: $B836 at its own entry with IY on slot 0, returning to $B653"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in _resolve(pokes):
        raw[a] = v
    r[IFF] = 0
    r[IYh], r[IYl] = SLOT0 >> 8, SLOT0 & 0xFF
    raw[0xBFF7] = 12                  # the manager's slot counter, as $B63C leaves it for slot 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, sp)
    for _ in range(200000):
        if _done(r, cur):
            assert r[PC] == BACK, name + ': returned to $%04X' % r[PC]
            break
        _step(r, op, raw, cur)
    else:
        raise AssertionError(name + ': no return')
    return _close(r, rm, cur)


def run(name, frames=FRAMES):
    h, rm = _machine(name)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    runs, cur, prev = [], None, 0
    while r[T] < t_end:
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and _done(r, cur):
            assert p == BACK, 'returned to $%04X' % p
            runs.append(_close(r, rm, cur)); cur = None
        if cur is None and p == ENTRY and prev == CALLER:
            cur = _open(r, rm, r[SP])
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside a rise'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a rise'
                h.sim.accept_interrupt(r, rm, p)
    return runs


def row(name, x):
    """NO ROM BYTE IS STORED (house rule 7): a read below $4000 keeps its ADDRESS only ('rom'), and a run
    that read the ROM keeps its display-bitmap writes as addresses only ('blind')"""
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if rom and a < 0x5800]
    post = [(a, v) for a, v in post if not (rom and a < 0x5800)]
    return {'state': name, 'T': x['T'], 'sub': x['sub'], 'rng': x['rng'], 'iy': x['iy'],
            'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
            'post': ''.join('%04x%02x' % (a, v) for a, v in post),
            'rom': ' '.join('%04x' % a for a in rom), 'blind': ' '.join('%04x' % a for a in blind),
            'path': ' '.join('%04x' % q for q in x['path'])}


CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, tag = job
    if tag:
        return [row(tag, call_run(*CALLS_BY[tag]))]
    return [row(name, x) for x in run(name)]


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    rows, per, forced, npaths, ts = [], collections.Counter(), collections.Counter(), set(), []
    for (s, tag), rs in zip(work, res):
        for x in rs:
            if not tag:
                npaths.add(x['path']); ts.append(x['T'])
            key = (tag or '') + x['path'] + ' %d' % x['T']
            if per[key] < (FORCED_KEEP if tag else KEEP):
                per[key] += 1
                if tag: forced[tag] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'paths': len(npaths), 'lo': min(ts), 'hi': max(ts),
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
    print('runs %d  paths %d  rows %d  T %d..%d' % (F['runs'], F['paths'], len(F['rows']), F['lo'], F['hi']))
    for x in F['rows']:
        if x['state'] in CALLS_BY:
            print('  %-12s T %5d  sub %s rng %s  %s' % (x['state'], x['T'], x['sub'], x['rng'], x['path']))


if __name__ == '__main__':
    main()
