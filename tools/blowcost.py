"""M7.74 -- THE BLOW CHECK'S T ($BD2C), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL).  This oracle records every run of the first arm, $BD2C -- both players'
blow checks, called from $B633 -- on an UNCONTENDED machine, so a run's T is the sum of its
instructions' own T:

  T        the run, $BD2C to its return to $B636, LESS its two nested callees (below)
  sub      the nested callees' runs, apart: [name, T] for each -- 'pop' the $B6D8 that the full pool's
           steal-the-oldest calls from $BDBC (-> $BDBF), 'award' the $80FA that the +$61 == 15 bonus
           calls from $BD6B (-> $BD6E).  Their T is NOT the blow's: the pop is the manager's arm (d)
           and the award is the score's; both stay provisional in the engine until they are made exact
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of the
           instruction being executed, except the self-modified operands read as STATE (TRAPS #275):
           the erase's accumulator $A431 (the pop's $BF0A)
  post     every byte the run WRITES, at its final value -- the stack excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (path, T).  The arms no natural
run reaches are FORCED CALLS (declared below): $BD2C called once on the machine from a saved state with
the player blocks poked, interrupts off, returning to $B636.

Usage:  python tools/blowcost.py [--jobs N]          (-> build/blowcost_fixture.json)
        python tools/blowcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/blowcost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 4
ENTRY, CALLER, BACK = 0xBD2C, 0xB633, 0xB636
SUBS = {0xB6D8: ('pop', 0xBDBC, 0xBDBF), 0x80FA: ('award', 0xBD6B, 0xBD6E)}
STATE_OPS = {0xA430: (0xA431,)}     # $A430 ADD A,n: the erase's accumulator


def _p(pl, v=1, f7=0x80, f5a=0, f5f=3, f61=0, x=0x60, y=0x90):
    """player pl's block: +$60 (the blow request), +7, +$5A, +$5F, +$61, +5 X, +6 Y"""
    b = 0xFD80 + 10 * pl
    return ((b + 0x60, v), (b + 7, f7), (b + 0x5A, f5a), (b + 0x5F, f5f), (b + 0x61, f61), (b + 5, x), (b + 6, y))


def _pool(ages, holds, flags, k0=0):
    """all twelve pool slots live: +4 the age, +9 the held enemy, +7 the flags, +5/+3 X, +6/+2 Y"""
    out = []
    for k in range(12):
        q = 0xFED8 + 10 * k
        x, y = 0x30 + 12 * k, 0x40 + 8 * (k % 6)
        out += [(q + 4, ages[k]), (q + 9, holds[k]), (q + 7, flags[k]), (q + 5, x), (q + 3, x), (q + 6, y), (q + 2, y)]
    return tuple(out)


IDLE = _p(0, v=0) + _p(1, v=0)
AGES = (0x20, 0x31, 0x18, 0x45, 0x45, 0x10, 0x3F, 0x60, 0x08, 0x50, 0x22, 0x01)
FREE = tuple((0xFED8 + 10 * k + 7, 0) for k in range(12))
# FORCED CALLS (declared): (name, state, pokes).  A blow request is +$60: 1 the press, 2 a held key with
# +7 bit 2; +$5A bit 2 dying, bit 1 the debounce (cleared while +$5F is 3), bit 5 fire mode, bit 6 the
# lightning ability, bit 0 player 2; +$61 the last power-up recorded, 15 the bubble bonus.
CALLS = [
    ('v2_spawn', 'round1_48', _p(0, v=2, f7=0x84) + _p(1, v=0) + FREE),
    ('v2_nobit', 'round1_48', _p(0, v=2, f7=0x80) + _p(1, v=0)),
    ('v3_bit', 'round1_48', _p(0, v=3, f7=0x84) + _p(1, v=0)),
    ('dying', 'round1_48', _p(0, f5a=0x04) + _p(1, v=0)),
    ('debounce', 'round1_48', _p(0, f5f=0, f5a=0x02) + _p(1, v=0)),
    ('nodebounce', 'round1_48', _p(0, f5f=0) + _p(1, v=0) + FREE),
    ('fire', 'round1_48', _p(0, f5a=0x20) + _p(1, v=0)),
    ('bonus', 'round1_48', _p(0, f61=15) + _p(1, v=0) + FREE),
    ('bonus_fire', 'round1_48', _p(0, f61=15, f5a=0x20) + _p(1, v=0)),
    ('bonus_p2', 'round1_48', _p(0, v=0) + _p(1, f61=15, f5a=0x01) + FREE),
    ('lightning', 'round1_48', _p(0, f5a=0x40) + _p(1, v=0) + FREE),
    ('both', 'round1_48', _p(0) + _p(1, f5a=0x41, x=0x90) + FREE),
    # slots 0..10 live, 11 free: the $BD7F scan runs to its last slot
    ('slot11', 'round1_48', _p(0) + _p(1, v=0) + _pool(AGES, (0,) * 12, (0xC0,) * 12) + ((0xFED8 + 10 * 11 + 7, 0),)),
    # the full pool: steal the oldest not holding an enemy, pop it ($BDBC CALL $B6D8), spawn there
    ('steal_risen', 'round1_48', _p(0) + _p(1, v=0) + _pool(AGES, (0, 3, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0), (0xC4,) * 12)),
    ('steal_travel', 'round1_48', _p(0) + _p(1, v=0) + _pool(AGES, (0,) * 12, (0xC0,) * 12)),
    ('steal_held', 'round1_48', _p(0) + _p(1, v=0) + _pool(AGES, (2,) * 12, (0xCC,) * 12)),
    ('steal_both', 'round1_48', _p(0) + _p(1, f5a=0x01, x=0x90) + _pool(AGES, (0,) * 12, (0xC4,) * 12)),
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


def _open(r, rm, sp):
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'prev': None, 'sub': [], 'open': None}
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
    op[raw[p]]()
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


def call_run(name, state, pokes):
    """one forced call: $BD2C at its own entry, returning to $B636"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, sp)
    for _ in range(200000):
        if r[SP] == (sp + 2) & 0xFFFF and cur['open'] is None:
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
        if cur is not None and cur['open'] is None and r[SP] == (cur['sp'] + 2) & 0xFFFF:
            assert p == BACK, 'returned to $%04X' % p
            runs.append(_close(r, rm, cur)); cur = None
        if cur is None and p == ENTRY and prev == CALLER:
            cur = _open(r, rm, r[SP])
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside a blow'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a blow'
                h.sim.accept_interrupt(r, rm, p)
    return runs


def row(name, x):
    """NO ROM BYTE IS STORED (house rule 7): a read below $4000 keeps its ADDRESS only ('rom'), and a run
    that read the ROM keeps its display-bitmap writes as addresses only ('blind') -- the bonus's award
    draws the score's digits from the ROM charset ($8042 -> $3D80..), the steal's pop can mark from a
    ROM chain window -- so a pixel the ROM supplied is never written down"""
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if rom and a < 0x5800]
    post = [(a, v) for a, v in post if not (rom and a < 0x5800)]
    return {'state': name, 'T': x['T'], 'sub': x['sub'],
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
            print('  %-13s T %5d  sub %s' % (x['state'], x['T'], x['sub']))


if __name__ == '__main__':
    main()
