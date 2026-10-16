"""M7.78 -- THE BUBBLE ESCAPE'S T ($B679), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL); M7.74..M7.77 made the blow, the draw, the rise and the pop exact.  This oracle
records every run of the ESCAPE arm, $B679 -- JUMPED to from $B664 (`JR nz`, a risen bubble whose class is
not 0, on the age toggle's even call) and leaving by a jump to $B66C at the same SP -- on an UNCONTENDED
machine, so a run's T is the sum of its instructions' own T: the class test (DEC A, the class arrives in A
from $B660), the age INC, and on the age's WRAP the release of the held enemy, the marker release $B6C8 and
the slot's death:

  T        the run, $B679 to $B66C, LESS its nested erase (below)
  sub      the nested callee's runs, apart: [name, T] -- 'erase' the $BF0A from $B6B9 (-> $B6BC), exact in
           the engine (cacheSetAndErase's return)
  cls      A at entry: the bubble's class (IY+9), which the skeleton read and the arm tests in A
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of the
           instruction being executed, except the self-modified operand read as STATE (TRAPS #275 / #278):
           the erase's accumulator $A431
  post     every byte the run WRITES, at its final value -- the stack and the ROM excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic
  iy       the slot (IY) at entry

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (path, T).  The arms no natural run
reaches are FORCED CALLS (declared below): $B679 entered once on the machine from a saved state with the
pool and the enemy table poked, A = the class, interrupts off, until it jumps to $B66C.

Usage:  python tools/escapecost.py [--jobs N]          (-> build/escapecost_fixture.json)
        python tools/escapecost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl
from harness import A as RA
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/escapecost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 1
ENTRY, BACK, FROM = 0xB679, 0xB66C, 0xB664
SUBS = {0xBF0A: ('erase', 0xB6B9, 0xB6BC)}
STATE_OPS = {0xA430: (0xA431,)}               # $A430 ADD A,n: the erase's accumulator
POOL = 0xFED8
M0 = 0xF94C                                   # the bubble's marker cell (a playfield cell, row 10)


def _slot(k, f7=0xC4, x=0x63, y=0x62, cls=1, enemy=2, age=0xFF, mark=None):
    """pool slot k: +7 the flags, +5/+6 X/Y, +9 the class, +8 the enemy, +4 the age, +2/+3 the marker cell"""
    p = POOL + 10 * k
    m = M0 if mark is None else mark
    return [(p + 7, f7), (p + 5, x), (p + 6, y), (p + 9, cls), (p + 8, enemy), (p + 4, age),
            (p + 2, m & 0xFF), (p + 3, m >> 8), (M0, 12 - k)]


def _enemy(k, f7=0xC8, x=0x50, y=0x40):
    """enemy slot k (from $FD94, stride 10): frozen (bit 3) and drawn (bit 6), a timer and a state to clear"""
    q = 0xFD94 + 10 * k
    return [(q + 7, f7), (q + 5, x), (q + 6, y), (q + 8, 0x33), (q + 9, 0x44)]


# FORCED CALLS (declared): (name, state, pokes).  A later poke of an address wins.
CALLS = [
    # an element bubble (class 2): DEC A / JR nz -- it does not even age
    ('elem', 'round1_48', _slot(0, cls=2, age=0x10)),
    # a holding bubble (class 1), the age short of the wrap: INC / JR nz
    ('age', 'round1_48', _slot(0, age=0x10) + _enemy(2)),
    ('age_fe', 'round1_48', _slot(0, age=0xFE) + _enemy(2)),
    # the WRAP: the enemy released -- the erase at each of its Y phases (even, cell-aligned, odd, past $C0)
    ('wrap', 'round1_48', _slot(0) + _enemy(2)),
    ('wrap_y8', 'round1_48', _slot(0, y=0x60) + _enemy(2)),
    ('wrap_odd', 'round1_48', _slot(0, y=0x61) + _enemy(2)),
    ('wrap_hi', 'round1_48', _slot(0, y=0xC4) + _enemy(2)),
    # the enemy index: 0, the last (7), and one past 25 whose 10 * index wraps in eight bits
    ('wrap_e0', 'round1_48', _slot(0, enemy=0) + _enemy(0)),
    ('wrap_e7', 'round1_48', _slot(0, enemy=7) + _enemy(7)),
    ('wrap_e30', 'round1_48', _slot(0, enemy=30)),
    # the marker release: a cell in ROM ($BEE8 parks +3 at 2: the write is discarded), and bit 2 clear
    # ($B6C8 BIT 2 / RET z -- no natural run, the age path needs bit 2; it is the routine's own branch)
    ('wrap_rom', 'round1_48', _slot(0, mark=0x0250) + _enemy(2)),
    ('wrap_b2', 'round1_48', _slot(0, f7=0xC0) + _enemy(2)),
    # another slot (IY at slot 5), the marker its own
    ('wrap_s5', 'round1_48', _slot(5) + _enemy(2)),
]


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operand the run reads as STATE enters the seed"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = STATE_OPS.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _iy(r):
    return r[IYh] << 8 | r[IYl]


def _open(r, rm):
    sp = r[SP]
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'prev': None, 'sub': [], 'open': None,
           'iy': _iy(r), 'cls': r[RA]}
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


def _done(r, cur):
    """a JUMPED arm: done when it reaches $B66C at its own SP"""
    return cur['open'] is None and r[PC] == BACK and r[SP] == cur['sp']


def call_run(name, state, pokes):
    """one forced call: $B679 with IY on the poked slot and A = its class, until it jumps to $B66C"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    k = next(j for j in range(12) if any(a == POOL + 10 * j + 7 for a, _ in pokes))
    iy = POOL + 10 * k
    r[IFF] = 0
    r[IYh], r[IYl] = iy >> 8, iy & 0xFF
    r[RA] = raw[iy + 9]
    raw[0xBFF7] = 12 - k              # the manager's slot counter, as $B63C leaves it
    r[PC] = ENTRY
    cur = _open(r, rm)
    for _ in range(400000):
        if _done(r, cur):
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
            runs.append(_close(r, rm, cur))
            cur = None
        if cur is None and p == ENTRY and prev == FROM:
            cur = _open(r, rm)
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside an escape'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside an escape'
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
    return {'state': name, 'T': x['T'], 'sub': x['sub'], 'cls': x['cls'], 'iy': x['iy'],
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
    rows, per, forced, npaths, ts, kinds = [], collections.Counter(), collections.Counter(), set(), [], collections.Counter()
    for (s, tag), rs in zip(work, res):
        for x in rs:
            if not tag:
                npaths.add(x['path']); ts.append(x['T'])
                kinds['elem' if x['cls'] != 1 else 'wrap' if x['sub'] else 'age'] += 1
            key = (tag or '') + ' ' + x['path'] + ' %d' % x['T']
            if per[key] < (FORCED_KEEP if tag else KEEP):
                per[key] += 1
                if tag: forced[tag] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'paths': len(npaths), 'lo': min(ts), 'hi': max(ts), 'kinds': dict(kinds),
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
    print('runs %d  paths %d  rows %d  T %d..%d  kinds %s' % (F['runs'], F['paths'], len(F['rows']), F['lo'], F['hi'],
                                                              F['kinds']))
    for x in F['rows']:
        print('  %-10s cls %d iy %04x T %4d  sub %s  %s' % (x['state'], x['cls'], x['iy'], x['T'], x['sub'], x['path'][:60]))


if __name__ == '__main__':
    main()
