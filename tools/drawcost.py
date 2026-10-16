"""M7.75 -- THE BUBBLE DRAW'S T ($B9E7), RUN BY RUN, UNCONTENDED.

M7.73 made the even pass $B62C charge itself: its skeleton exact, its arms at their fixture medians
(BB_B62C_ARM, PROVISIONAL); M7.74 made the blow arm exact.  This oracle records every run of the
draw arm, $B9E7 called from $B653 (a risen bubble, between the drift and the age tick), on an
UNCONTENDED machine, so a run's T is the sum of its instructions' own T:

  T        the run, $B9E7 to its return to $B656.  The routine borrows SP as its sprite pointer
           (`LD IX,0 / ADD IX,SP`, then `LD SP,HL` ... `LD SP,IX / RET`), so the run ends on the return
           PC AND the caller's SP, never on the first SP rise
  seed     every byte the run READS before it writes it, as (address, value) -- the sprite's bytes
           POPped through SP among them, not the bytes of the instruction being executed
  post     every byte the run WRITES, at its final value -- its self-modified operands among them
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic
  iy       the slot the run drew (IY)
  y, kind  the bubble's (IY+6) and (IY+9) at entry -- what the T is a function of, with
  sel      the sprite choice's arms executed: 'h' kind 1, 'a' its age past $E6, 'b' the second test
           ($C780 unless 'x', the element's $D380; 'h' alone or 'ha' with the toggle set: $C900)

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (path, T).  The draws no natural
run reaches are FORCED CALLS (declared below): $B9E7 called once on the machine from a saved state with
slot 0 poked risen at a chosen Y, kind and age, interrupts off, returning to $B656.

Usage:  python tools/drawcost.py [--jobs N]          (-> build/drawcost_fixture.json)
        python tools/drawcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/drawcost_fixture.json'
FRAMES = 300
KEEP = 2
ENTRY, CALLER, BACK = 0xB9E7, 0xB653, 0xB656
SLOT0 = 0xFED8
# the sprite choice's instructions, by the one that marks each arm: kind 1 ($BA05), its age past $E6
# ($BA0F), the second test entered ($BA15), the element base ($BA1B)
SEL_PCS = {0xBA05: 'h', 0xBA0F: 'a', 0xBA15: 'b', 0xBA1B: 'x'}


def _slot(y, kind=0, age=0x40, flash=None, x=0x60):
    """slot 0 risen (+7 $C4) at X x, Y y, holding `kind`, aged `age`; flash the $B62D toggle"""
    p = SLOT0
    out = [(p + 7, 0xC4), (p + 5, x), (p + 6, y), (p + 9, kind), (p + 4, age)]
    if flash is not None:
        out.append((0xB62D, flash))
    return tuple(out)


# FORCED CALLS (declared): (name, state, pokes).  Every Y phase (Y & 7, both parities) for each of the
# routine's four sprite choices: kind 0 (the empty bubble, $C780), kind 1 young (holding, $C900), kind 1
# past $E6 with the toggle 0 (flashing to empty, $C780) or 1 (holding), kind >= 2 (an element, $D380).
CALLS = []
for _y in range(0x40, 0x48):
    CALLS += [('empty_y%02x' % _y, 'round1_48', _slot(_y)),
              ('held_y%02x' % _y, 'round1_48', _slot(_y, kind=1)),
              ('flash0_y%02x' % _y, 'round1_48', _slot(_y, kind=1, age=0xF0, flash=0)),
              ('flash1_y%02x' % _y, 'round1_48', _slot(_y, kind=1, age=0xF0, flash=1)),
              ('elem_y%02x' % _y, 'round1_48', _slot(_y, kind=3))]
# the screen's edges: the top row (the blocked drift's wrap, $B8AC), Y 1 and $B7 (the drift's, $B864),
# the right-hand columns
CALLS += [('top_y00', 'round1_48', _slot(0x00)), ('top_y01', 'round1_48', _slot(0x01)),
          ('low_yb7', 'round1_48', _slot(0xB7)), ('right_xf0', 'round1_48', _slot(0x44, x=0xF0))]
# the age test's own edge ($BA0B CP $E6 / JR c): $E5 still holding, $E6 the first flashing age
CALLS += [('age_e5', 'round1_48', _slot(0x42, kind=1, age=0xE5, flash=0)),
          ('age_e6', 'round1_48', _slot(0x42, kind=1, age=0xE6, flash=0))]


def _iy(r):
    return r[IYh] << 8 | r[IYl]


def _open(r, rm, sp):
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None,
           'y': rm.m[(_iy(r) + 6) & 0xFFFF], 'kind': rm.m[(_iy(r) + 9) & 0xFFFF], 'sel': '', 'iy': _iy(r)}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    return cur


def _step(r, op, raw, cur):
    p = r[PC]
    if cur['last'] is not None and p != cur['last']:
        cur['path'].append(p)
    if p in SEL_PCS:
        cur['sel'] += SEL_PCS[p]
    op[raw[p]]()
    cur['last'] = B._fall(raw, p)


def _close(r, rm, cur):
    rm.rec = None
    cur['T'] = r[T] - cur['t0']
    return cur


def _machine(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def _done(r, cur):
    return r[SP] == (cur['sp'] + 2) & 0xFFFF and r[PC] == BACK


def call_run(name, state, pokes):
    """one forced call: $B9E7 at its own entry with IY on slot 0, returning to $B656"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    r[IFF] = 0
    r[IYh], r[IYl] = SLOT0 >> 8, SLOT0 & 0xFF
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, sp)
    for _ in range(200000):
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
            runs.append(_close(r, rm, cur)); cur = None
        if cur is None and p == ENTRY and prev == CALLER:
            cur = _open(r, rm, r[SP])
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside a draw'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a draw'
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
    pa = x['path']
    return {'state': name, 'T': x['T'], 'iy': x['iy'], 'y': x['y'], 'kind': x['kind'], 'sel': x['sel'],
            'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
            'post': ''.join('%04x%02x' % (a, v) for a, v in post),
            'rom': ' '.join('%04x' % a for a in rom), 'blind': ' '.join('%04x' % a for a in blind),
            'path': ' '.join('%04x' % q for q in pa)}


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
            if tag or per[key] < KEEP:
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


if __name__ == '__main__':
    main()
