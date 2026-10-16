"""M7.79 -- THE BUBBLE TRAVEL'S T ($BDFE), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL); M7.74..M7.78 made the blow, the draw, the rise, the pop and the escape exact.
This oracle records every run of the last arm, the TRAVEL, $BDFE -- JUMPED to from $B648 (`JP z`: a live
bubble not yet risen) and leaving by `JP $B66C` at the same SP -- on an UNCONTENDED machine, so a run's T is
the sum of its instructions' own T: `CALL $BE07` (the step, the capture $BE5B and its scan $92C0, the wall
probe $BEAF and $AEDC, the cap test, the rise transition $BEE8) and the tick `INC (IY+4)`:

  T        the run, $BDFE to $B66C, LESS its nested callees (below)
  sub      the nested callees' runs, apart: [name, T] for each -- 'erase' a $BF16 CALLed from $BE55, $BEA9
           or $BEE8 (-> the CALL + 3); 'eh' the captured enemy's $A447 from $BE92 (-> $BE95); 'draw' the
           $B9E7 JUMPED to from $BE58 or $BEAC, until its RET lands on $BE01 at the arm's own SP
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of the
           instruction being executed, except the self-modified operands read as STATE (TRAPS #275 / #278):
           the erase's accumulator $A431, the opcode $92DE the scan executes
  post     every byte the run WRITES, at its final value -- the stack and the ROM excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  romt     the T the scan spent on slots whose +7 lies in the ROM, beyond a dead slot's 109 (E_HEAD +
           E_DEAD + E_TAIL) -- a $AA57 of 2 walks 256 slots and wraps through it; the one part of a run the
           page cannot compute (it holds no ROM), recorded as a figure only, with 'romn' the slots counted
  path     the run's PCs where control did not fall through, for a diagnostic
  iy       the slot (IY) at entry

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (path, T).  The arms no natural run
reaches are FORCED CALLS (declared below): $BDFE entered once on the machine from a saved state with the
pool, the enemy table and the colour shadow poked, interrupts off, until it jumps to $B66C.

Usage:  python tools/travelcost.py [--jobs N]          (-> build/travelcost_fixture.json)
        python tools/travelcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl, H
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/travelcost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 1
ENTRY, BACK, FROM = 0xBDFE, 0xB66C, 0xB648
CALLED = {0xBF16: ('erase', (0xBE55, 0xBEA9, 0xBEE8)), 0xA447: ('eh', (0xBE92,))}
JUMPED = {0xB9E7: ('draw', (0xBE58, 0xBEAC), 0xBE01)}
STATE_OPS = {0xA430: (0xA431,)}               # $A430 ADD A,n: the erase's accumulator
OPCODE_STATE = (0x92DE,)                      # the scan's RET / NOP, executed: read as state
POOL = 0xFED8
DEAD_SLOT = 109                               # $92E4 27 + JR z taken 12 + $92FC's tail 70


def _slot(k, f7=0x80, x=0x60, y=0x60, age=5, cls=0):
    """pool slot k, travelling (bit 2 clear): +7 the flags (bit 0 the facing, bit 4 the owner), +5/+6 X/Y,
    +4 the age (the step count), +9 the class"""
    p = POOL + 10 * k
    return [(p + 7, f7), (p + 5, x), (p + 6, y), (p + 4, age), (p + 9, cls)]


def _enemies(n=0):
    """the enemy count ($AA57 = n + 2) and every enemy slot dead, unless poked after"""
    return [(0xAA57, n + 2)] + [(0xFD94 + 10 * j + 7, 0) for j in range(8)]


def _enemy(k, f7=0xC0, x=0x60, y=0x60, cx=None, cy=None):
    """enemy slot k (from $FD94): +7 the flags (live, drawn: $C0), +5/+6 where it is, +3/+2 where it was drawn"""
    q = 0xFD94 + 10 * k
    return [(q + 7, f7), (q + 5, x), (q + 6, y), (q + 3, x if cx is None else cx), (q + 2, y if cy is None else cy)]


def _clear(x, y):
    """the colour-shadow cells the wall probe reads around (x, y), clear of the solid bit"""
    c = 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)
    return [(c + d, 0) for d in (-1, 0, 1, 2, 31, 32, 33, 34)]


def _wall(x, y, d=0):
    """the solid bit $20 at the probe's cell + d (0, 1 the next column, 32 the row below, 33)"""
    c = 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)
    return [(c + d, 0x20)]


# FORCED CALLS (declared): (name, state, pokes).  A later poke of an address wins.  Positions are AFTER the
# step: a bubble at X steps to X - 8 (facing left, bit 0 clear) or X + 8 (right).
L, R, P2 = 0x80, 0x81, 0x90        # +7: travelling, facing left / right; player 2's bubble (left)
CAPS = [(0xFDDE, 0x30), (0xFDE8, 0x30)]                 # both owners' range, past any age used below
AIR = _enemies(3) + CAPS + _clear(0x60, 0x60)           # three dead slots, the probe's cells clear
CALLS = [
    # the step: facing left / right, X & 6 after it 0 or not ($BEC4 JR z,+0), the first two ticks
    ('open_l', 'round1_48', AIR + _slot(0, L, x=0x68)),
    ('open_r', 'round1_48', AIR + _slot(0, R, x=0x58)),
    ('open_x2', 'round1_48', AIR + _clear(0x62, 0x60) + _slot(0, L, x=0x6A)),
    ('open_x1', 'round1_48', AIR + _clear(0x61, 0x60) + _slot(0, L, x=0x69)),   # X & 6 = 0 but X odd
    ('age0', 'round1_48', AIR + _slot(0, L, x=0x68, age=0)),
    ('age1', 'round1_48', AIR + _slot(0, L, x=0x68, age=1)),
    ('age2', 'round1_48', AIR + _slot(0, L, x=0x68, age=2)),
    # the range reached: the rise transition, player 1's and player 2's
    ('cap', 'round1_48', AIR + _slot(0, L, x=0x68, age=0x30)),
    ('cap_p2', 'round1_48', AIR + _slot(0, P2, x=0x68, age=0x30)),
    # the wall probe: each of its four cells, a bubble born flush (age < 2), player 2's
    ('wall_0', 'round1_48', AIR + _wall(0x60, 0x60, 0) + _slot(0, L, x=0x68)),
    ('wall_32', 'round1_48', AIR + _wall(0x60, 0x60, 32) + _slot(0, L, x=0x68)),
    ('wall_1', 'round1_48', AIR + _wall(0x60, 0x60, 1) + _slot(0, L, x=0x68)),
    ('wall_33', 'round1_48', AIR + _wall(0x60, 0x60, 33) + _slot(0, L, x=0x68)),
    ('wall_born', 'round1_48', AIR + _wall(0x60, 0x60, 0) + _slot(0, L, x=0x68, age=1)),
    ('wall_p2', 'round1_48', AIR + _wall(0x60, 0x60, 0) + _slot(0, P2, x=0x68)),
    # the scan's refusals: frozen, each axis out at each edge; $AA57 = 2 walks 256 slots
    ('frozen', 'round1_48', AIR + _enemy(0, 0xC8) + _slot(0, L, x=0x68)),
    ('y_far', 'round1_48', AIR + _enemy(0, y=0x70) + _slot(0, L, x=0x68)),
    ('y_near', 'round1_48', AIR + _enemy(0, y=0x50) + _slot(0, L, x=0x68)),
    ('x_far', 'round1_48', AIR + _enemy(0, x=0x70) + _slot(0, L, x=0x68)),
    ('x_near', 'round1_48', AIR + _enemy(0, x=0x50) + _slot(0, L, x=0x68)),
    ('scan256', 'round1_48', _enemies(0) + CAPS + _clear(0x60, 0x60) + _slot(0, L, x=0x68)),
    # the capture: the enemy's index (the loop), its erase at each class -- aligned / shifted X, Y aligned /
    # odd / even, cached Y past $C0, never drawn (bit 6 clear) -- and player 2's bubble
    ('capt', 'round1_48', AIR + _enemy(0) + _slot(0, L, x=0x68)),
    ('capt_k2', 'round1_48', AIR + _enemy(2) + _slot(0, L, x=0x68)),
    ('capt_k6', 'round1_48', _enemies(7) + CAPS + _clear(0x60, 0x60) + _enemy(6) + _slot(0, L, x=0x68)),
    ('capt_sh', 'round1_48', AIR + _enemy(0, cx=0x62) + _slot(0, L, x=0x68)),
    ('capt_odd', 'round1_48', AIR + _enemy(0, cy=0x61) + _slot(0, L, x=0x68)),
    ('capt_even', 'round1_48', AIR + _enemy(0, cy=0x62) + _slot(0, L, x=0x68)),
    ('capt_sh_odd', 'round1_48', AIR + _enemy(0, cx=0x63, cy=0x63) + _slot(0, L, x=0x68)),
    ('capt_hi', 'round1_48', AIR + _enemy(0, cy=0xC4) + _slot(0, L, x=0x68)),
    ('capt_b6', 'round1_48', AIR + _enemy(0, 0x80) + _slot(0, L, x=0x68)),
    ('capt_p2', 'round1_48', AIR + _enemy(0) + _slot(0, P2, x=0x68)),
]


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operands the run reads as STATE enter the seed"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            pcv = self.regs[PC]
            s = STATE_OPS.get(pcv)
            if (s and i in s) or (i in OPCODE_STATE and i == pcv):
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _iy(r):
    return r[IYh] << 8 | r[IYl]


def _open(r, rm):
    sp = r[SP]
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'prev': None, 'sub': [], 'open': None,
           'iy': _iy(r), 'romt': 0, 'romn': 0, 'rs': None}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    return cur


def _step(r, op, raw, cur):
    p = r[PC]
    o = cur['open']
    if o is not None and p == o[1] and r[SP] == o[2]:
        cur['sub'].append([o[0], r[T] - o[3]]); cur['open'] = None; o = None
    if o is None:
        if p in CALLED and cur['prev'] in CALLED[p][1]:
            cur['open'] = (CALLED[p][0], cur['prev'] + 3, (r[SP] + 2) & 0xFFFF, r[T])
        elif p in JUMPED and cur['prev'] in JUMPED[p][1]:
            cur['open'] = (JUMPED[p][0], JUMPED[p][2], cur['sp'], r[T])
    if cur['last'] is not None and p != cur['last']:
        cur['path'].append(p)
    if p in (0x92E4, 0x9308, 0x92FA) and cur['rs'] is not None:
        assert p != 0x92FA, 'a hit in the ROM'
        cur['romt'] += r[T] - cur['rs'] - DEAD_SLOT; cur['rs'] = None
    if p == 0x92E4 and r[H] < 0x40:
        cur['rs'] = r[T]; cur['romn'] += 1
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
    """one forced call: $BDFE with IY on the poked slot, until it jumps to $B66C"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    k = next(j for j in range(12) if any(a == POOL + 10 * j + 7 for a, _ in pokes))
    iy = POOL + 10 * k
    r[IFF] = 0
    r[IYh], r[IYl] = iy >> 8, iy & 0xFF
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
            assert cur is None, 'HALT inside a travel'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a travel'
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
    return {'state': name, 'T': x['T'], 'sub': x['sub'], 'iy': x['iy'], 'romt': x['romt'], 'romn': x['romn'],
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


def kind(x):
    """the run's shape, for the summary: which callees it entered"""
    return '+'.join(s[0] for s in x['sub']) or 'none'


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    rows, per, forced, npaths, ts, kinds = [], collections.Counter(), collections.Counter(), set(), [], collections.Counter()
    for (s, tag), rs in zip(work, res):
        for x in rs:
            if not tag:
                npaths.add(x['path']); ts.append(x['T']); kinds[kind(x)] += 1
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
        print('  %-10s iy %04x T %4d  sub %s  %s' % (x['state'], x['iy'], x['T'], x['sub'], x['path'][:70]))


if __name__ == '__main__':
    main()
