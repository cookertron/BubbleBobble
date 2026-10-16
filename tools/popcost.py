"""M7.77 -- THE BUBBLE POP'S T ($B6D8), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL); M7.74 made the blow arm exact, M7.75 the draw, M7.76 the rise.  This oracle
records every run of the pop, $B6D8, from its three callers -- $B6C3 (a holding bubble, the HELD arm),
$B669 (`CALL m`, the age pop) and $BDBC (the blow's steal of the oldest) -- on an UNCONTENDED machine, so a
run's T is the sum of its instructions' own T: the marker release $B6CD, the slot's death, the burst seed
$B6FC, and for a paid pop the mailbox, the award fork ($B7E5's mask, the corpse), the chain walk $B774 and
its marks $B7A1, the two click edges:

  T        the run, $B6D8 to its return to the caller, LESS its three nested callees (below)
  sub      the nested callees' runs, apart: [name, T] for each -- 'erase' the $BF0A from $B6E3 (-> $B6E6),
           exact in the engine (cacheSetAndErase's return); 'birth' the corpse $8BC2 from $B82B (-> $B82E);
           'award' the score $80FA from $B797 (-> $B79A)
  caller   the CALL's address
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of the
           instruction being executed, except the self-modified operands read as STATE (TRAPS #275 / #278):
           the erase's accumulator $A431, the generator's seed $FE86/7
  post     every byte the run WRITES, at its final value -- the stack and the ROM excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  arm      a HELD run's whole arm, $B6C3 to $B66C (the CALL, the run, its callees, the JR back); else None
  romt     the T the chain walk spent on $B7A1 calls made from ROM cells, beyond `CALL nz` not taken --
           the one part of a run the page cannot compute (it holds no ROM), recorded as a figure only
  path     the run's PCs where control did not fall through, for a diagnostic
  iy       the slot (IY) at entry

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (caller, path, T).  The arms no
natural run reaches are FORCED CALLS (declared below): $B6D8 called once on the machine from a saved state
with the pool, the burst table and the shadow window poked, interrupts off, returning to $B66C.

Usage:  python tools/popcost.py [--jobs N]          (-> build/popcost_fixture.json)
        python tools/popcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl, H, L
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/popcost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 1
ENTRY, BACK = 0xB6D8, 0xB66C
CALLERS = (0xB6C3, 0xB669, 0xBDBC)
SUBS = {0xBF0A: ('erase', 0xB6E3, 0xB6E6), 0x8BC2: ('birth', 0xB82B, 0xB82E), 0x80FA: ('award', 0xB797, 0xB79A)}
STATE_OPS = {0xA430: (0xA431,),               # $A430 ADD A,n: the erase's accumulator
             0xFE85: (0xFE86, 0xFE87)}        # $FE85 LD HL,nn: the generator's seed
POOL = 0xFED8
SPARK = 0x5CE0
M0 = 0xF94C                                   # the popped bubble's marker cell (a playfield cell, row 10)


def _slot(k, f7, x=0x60, y=0x60, cls=0, enemy=0, mark=None, age=0x80):
    """pool slot k: +7 the flags, +5/+6 X/Y, +9 the class, +8 the enemy, +2/+3 the marker cell"""
    p = POOL + 10 * k
    m = M0 if mark is None else mark
    return [(p + 7, f7), (p + 5, x), (p + 6, y), (p + 9, cls), (p + 8, enemy), (p + 4, age),
            (p + 2, m & 0xFF), (p + 3, m >> 8)]


def _quiet(keep=(0,)):
    """every other pool slot empty, the window around M0 free of markers, a free burst slot, no request"""
    out = [(POOL + 10 * k + 7, 0) for k in range(12) if k not in keep]
    for r in range(4):
        for c in range(4):
            out.append((M0 - 0x21 + 0x20 * r + c, 0))
    out += [(SPARK, 0), (0xFFF9, 0)]
    return out


def _mark(cell, k):
    """the window cell `cell` carries slot k's marker (12 - k in the low five bits)"""
    return [(cell, 12 - k)]


def _enemy(k, f7):
    q = 0xFD94 + 10 * k
    return [(q + 7, f7), (q + 5, 0x63), (q + 6, 0x55), (q + 2, 0x50), (q + 3, 0x60)]


PAID = 0xC6        # risen (7, 6, 2) and paid (bit 1): the emit runs on
FULL = [(SPARK + 2 * j, 0x21) for j in range(14)]

# FORCED CALLS (declared): (name, state, pokes).  A later poke of an address wins.
CALLS = [
    # not risen: BIT 2 / RET z
    ('retz', 'round1_48', _quiet() + _slot(0, 0x80)),
    # unpaid (bit 1 clear): the seed, then RET z -- at the burst table's edges: a free slot, none free
    # (DEC DE x2 backs onto slot 13), Y below $10 / at $10 / $AE / $AF (the cancel's two CPs)
    ('unpaid', 'round1_48', _quiet() + _slot(0, 0xC4)),
    ('seed_full', 'round1_48', _quiet() + FULL + _slot(0, 0xC4)),
    ('y_0f', 'round1_48', _quiet() + _slot(0, 0xC4, y=0x0F)),
    ('y_10', 'round1_48', _quiet() + _slot(0, 0xC4, y=0x10)),
    ('y_ae', 'round1_48', _quiet() + _slot(0, 0xC4, y=0xAE)),
    ('y_af', 'round1_48', _quiet() + _slot(0, 0xC4, y=0xAF)),
    # paid: the class fork -- 0 (HL = 1), 2 / 3 / 4 (HL = $10), 5 and 12 (the mask), the corpse (1)
    ('cls0', 'round1_48', _quiet() + _slot(0, PAID, cls=0)),
    ('cls2', 'round1_48', _quiet() + _slot(0, PAID, cls=2)),
    ('cls3', 'round1_48', _quiet() + _slot(0, PAID, cls=3)),
    ('cls4', 'round1_48', _quiet() + _slot(0, PAID, cls=4)),
    ('cls5', 'round1_48', _quiet() + _slot(0, PAID, cls=5)),
    ('cls12', 'round1_48', _quiet() + _slot(0, PAID, cls=12)),
    ('cls5_p2', 'round1_48', _quiet() + _slot(0, PAID | 0x10, cls=5)),
    # the corpse's enemy: frozen with bit 5 set / clear, empty, live (the erase inside the birth)
    ('corpse', 'round1_48', _quiet() + _slot(0, PAID, cls=1, enemy=2) + _enemy(2, 0xAC)),
    ('corpse_b5', 'round1_48', _quiet() + _slot(0, PAID, cls=1, enemy=2) + _enemy(2, 0x8C)),
    ('corpse_off', 'round1_48', _quiet() + _slot(0, PAID, cls=1, enemy=2) + _enemy(2, 0x00)),
    ('corpse_live', 'round1_48', _quiet() + _slot(0, PAID, cls=1, enemy=2) + _enemy(2, 0xC0)),
    # the mailbox already holding a request: skipped
    ('mail_busy', 'round1_48', _quiet() + _slot(0, PAID, cls=3) + [(0xFFF9, 2)]),
    # player 2's pop (bit 4: the owner 2, $B7C2 = $10)
    ('p2', 'round1_48', _quiet() + _slot(0, PAID | 0x10, cls=2)),
    # the chain window: a risen neighbour is marked; a travelling one, an empty one and a risen one already
    # marked by player 2 are tested; the corner cells both ways
    ('chain', 'round1_48', _quiet((0, 3, 4, 5, 6)) + _slot(0, PAID, cls=2) +
        _slot(3, 0xC4, mark=M0 - 0x21) + _mark(M0 - 0x21, 3) +
        _slot(4, 0x80, mark=M0 + 1) + _mark(M0 + 1, 4) +
        _slot(5, 0x00, mark=M0 + 0x20) + _mark(M0 + 0x20, 5) +
        _slot(6, 0xD4, mark=M0 + 0x42) + _mark(M0 + 0x42, 6)),
    ('chain_p2', 'round1_48', _quiet((0, 3)) + _slot(0, PAID | 0x10, cls=2) +
        _slot(3, 0xC4, mark=M0 + 0x22) + _mark(M0 + 0x22, 3)),
    # the window through a ROM pointer ($BEE8 parks +3 at 2): sixteen ROM reads
    ('rom', 'round1_48', _quiet() + _slot(0, PAID, cls=2, mark=0x0250)),
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


def _open(r, rm, sp, caller):
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'prev': None, 'sub': [], 'open': None,
           'iy': _iy(r), 'caller': caller, 'romt': 0, 'rc': None}
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
    if p == 0xB785 and r[H] < 0x40 and cur['open'] is None:
        cur['rc'] = r[T]                          # a ROM cell's CALL nz,$B7A1
    elif p == 0xB788 and cur['rc'] is not None:
        cur['romt'] += r[T] - cur['rc'] - 10; cur['rc'] = None   # less the CALL nz not taken
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
    return cur['open'] is None and r[SP] == (cur['sp'] + 2) & 0xFFFF


def call_run(name, state, pokes):
    """one forced call: $B6D8 at its own entry with IY on slot 0, returning to $B66C"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    r[IFF] = 0
    r[IYh], r[IYl] = POOL >> 8, POOL & 0xFF
    raw[0xBFF7] = 12                  # the manager's slot counter, as $B63C leaves it for slot 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, sp, 0xB669)
    for _ in range(400000):
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
    runs, cur, prev, h0, pend = [], None, 0, None, None
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
            assert p == (cur['caller'] + 3) & 0xFFFF, 'returned to $%04X' % p
            runs.append(_close(r, rm, cur))
            if cur['caller'] == 0xB6C3: pend = cur
            cur = None
        if p == 0xB6C3 and cur is None:
            h0 = r[T]
        if p == BACK and pend is not None:
            pend['arm'] = r[T] - h0; pend = None      # the HELD arm, $B6C3 to $B66C, whole
        if cur is None and p == ENTRY and prev in CALLERS:
            cur = _open(r, rm, r[SP], prev)
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside a pop'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a pop'
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
    return {'state': name, 'T': x['T'], 'sub': x['sub'], 'caller': x['caller'], 'iy': x['iy'], 'romt': x['romt'], 'arm': x.get('arm'),
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
    rows, per, forced, npaths, ts, callers = [], collections.Counter(), collections.Counter(), set(), [], collections.Counter()
    for (s, tag), rs in zip(work, res):
        for x in rs:
            if not tag:
                npaths.add(x['path']); ts.append(x['T']); callers['%04x' % x['caller']] += 1
            key = (tag or '') + '%04x ' % x['caller'] + x['path'] + ' %d' % x['T']
            if per[key] < (FORCED_KEEP if tag else KEEP):
                per[key] += 1
                if tag: forced[tag] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'paths': len(npaths), 'lo': min(ts), 'hi': max(ts), 'callers': dict(callers),
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
    print('runs %d  paths %d  rows %d  T %d..%d  callers %s' % (F['runs'], F['paths'], len(F['rows']), F['lo'], F['hi'],
                                                                 F['callers']))
    for x in F['rows']:
        if x['state'] in CALLS_BY or x['romt']:
            print('  %-12s %04x T %5d romt %4d  sub %s' % (x['state'], x['caller'], x['T'], x['romt'], x['sub']))


if __name__ == '__main__':
    main()
