"""M7.72 -- THE CORPSE FLIGHT'S T ($8A78), RUN BY RUN, UNCONTENDED.

M7.68 left every corpse flight at its fixture median (BB_AA60_CORPSE, PROVISIONAL); M7.69 and M7.70
made the player's and the eight enemy handlers' runs exact.  This oracle records every run of $8A78
called from $AA60's $AB00 CALL z on an UNCONTENDED machine, so a run's T is the sum of its
instructions' own T and nothing else:

  T        the run: from $8A78 to its return to $AB03 (the $BF0A erase and the $A26F draw inside it)
  slot     the entity slot (IY = $FD80 + 10 * slot)
  seed     every byte the run READS before it writes it, as (address, value) -- not the bytes of
           the instruction being executed, except the self-modified operands it reads as STATE:
           the PRNG's $FE86/$FE87, the landing's type generator $8B9F/$8BA0/$8BA2 and the erase's
           accumulator $A431 (TRAPS #275)
  post     every byte the run WRITES, at its final value -- the stack excepted
  rom      the addresses below $4000 the run read: their VALUES are never stored (house rule 7)
  blind    when `rom` is not empty, the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic

Every 48K saved state, 300 frames, interrupts on, ab38cost's key script; the rows keep up to KEEP runs
of every distinct (path, T).  The arms no natural run reaches are FORCED CALLS (declared below): $8A78
called once on the machine from a saved state, interrupts off, IY the slot, returning to $AB03.

Usage:  python tools/corpsecost.py [--jobs N]          (-> build/corpsecost_fixture.json)
        python tools/corpsecost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IYh, IYl
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/corpsecost_fixture.json'
FRAMES = 300
KEEP = 2
FORCED_KEEP = 4
ENTRY, CALLER, BACK = 0x8A78, 0xAB00, 0xAB03
STATE_OPS = {0xFE85: (0xFE86, 0xFE87), 0x8B9E: (0x8B9F,), 0x8BA1: (0x8BA2,),
             0xA430: (0xA431,)}     # $A430 ADD A,n: the erase's accumulator


def _slot(slot, x, y, f, a4, a8, extra=()):
    """a corpse at slot: (IY+9) $FF, (IY+5) X, (IY+6) Y, (IY+7) f, (IY+4), (IY+8)"""
    b = 0xFD80 + 10 * slot
    return ((b + 5, x), (b + 6, y), (b + 7, f), (b + 4, a4), (b + 8, a8), (b + 9, 0xFF)) + tuple(extra)


# FORCED CALLS (declared): (name, state, slot, pokes) -- the arms no natural run reaches.  A flight's
# flags are $8C|dir with bit 1 set once it descends ($8E) and bit 4 in the fall ($9E); $FEC6's parity
# picks the shimmer (even) or the redraw (odd).  A cell is the colour shadow's $F800 + 32 * row + column.
C2 = lambda *a, **k: _slot(2, *a, **k)
EVEN, ODD = (0xFEC6, 0x00), (0xFEC6, 0x01)
FLOOR = ((0xF948, 0x20), (0xF949, 0x20), (0xF928, 0), (0xF929, 0), (0xF908, 0), (0xF909, 0))   # X $40, Y $40
CALLS = [
    # descending at Y $B8: + 8 is $C0, the bob's wrap to 0 ($8ABF)
    ('wrap_down', 'round1_48', 2, C2(0x40, 0xB8, 0x8E, 0, 0x25, (EVEN,))),
    # the leg ends descending at X $08: into the fall, the X clamp up to $10 ($8AEA)
    ('fall_low_x', 'round1_48', 2, C2(0x08, 0x40, 0x8E, 0, 0x20, (EVEN,))),
    # the fall's eight-bit timeout wraps: the landing straight from $8B51
    ('fall_timeout', 'round1_48', 2, C2(0x40, 0x40, 0x9E, 0xFF, 0, FLOOR)),
    # on a floor, the row at Y + 8 clear and the row at Y solid on the right / the left: $8B81 taken
    ('probe2_r', 'round1_48', 2, C2(0x40, 0x40, 0x9E, 0, 0, FLOOR + ((0xF909, 0x20),))),
    ('probe2_l', 'round1_48', 2, C2(0x40, 0x40, 0x9E, 0, 0, FLOOR + ((0xF908, 0x20),))),
    # the landing with all thirty fruit entries taken: the DJNZ runs out, HL $9643 ($8B96)
    ('table_full', 'round1_48', 2, C2(0x40, 0x40, 0x9E, 0, 0, FLOOR + tuple((0x9607 + 2 * i, 1) for i in range(30)))),
    # falling above the HUD: Y + 16 < $18, $AED1's $AED7 arm
    ('fall_top', 'round1_48', 2, C2(0x40, 0x02, 0x9E, 0, 0)),
    # the erase's and the draw's Y classes no flight reaches: odd, even unaligned, $C0 and over
    ('erase_odd', 'round1_48', 2, C2(0x40, 0x41, 0x8C, 0, 0x25, (ODD,))),
    ('erase_even', 'round1_48', 2, C2(0x40, 0x42, 0x8C, 0, 0x25, (ODD,))),
    ('erase_high', 'round1_48', 2, C2(0x40, 0xC4, 0x8C, 0, 0x25, (ODD,))),
]


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operands the flight reads as STATE enter the seed"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = STATE_OPS.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _open(r, rm, slot, sp):
    cur = {'t0': r[T], 'sp': sp, 'slot': slot, 'seed': [], 'path': [], 'last': None}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    return cur


def _step(r, op, raw, cur, tab, rm):
    p = r[PC]
    if p == 0x8BA0 and p not in rm.seen:         # an OPCODE read as state: the fetch bypasses the recorder
        rm.seen.add(p); rm.rec.append((p, raw[p]))
    if cur['last'] is not None and p != cur['last']:
        cur['path'].append(p)
    t0 = r[T]
    op[raw[p]]()
    cur['last'] = B._fall(raw, p)
    if tab is not None:
        tab.setdefault(p, set()).add((r[T] - t0, r[PC]))


def _machine(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def call_run(name, state, slot, pokes, tab=None):
    """one forced call: $8A78 at its own entry, IY the slot, returning to $AB03"""
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for a, v in pokes:
        raw[a] = v
    iy = 0xFD80 + 10 * slot
    r[IYh], r[IYl] = iy >> 8, iy & 0xFF
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, slot, sp)
    for _ in range(100000):
        if r[SP] == (sp + 2) & 0xFFFF:
            assert r[PC] == BACK, name + ': returned to $%04X' % r[PC]
            break
        _step(r, op, raw, cur, tab, rm)
    else:
        raise AssertionError(name + ': no return')
    rm.rec = None
    cur['T'] = r[T] - cur['t0']
    return cur


def run(name, frames=FRAMES, tab=None):
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
        if cur is not None and r[SP] == (cur['sp'] + 2) & 0xFFFF:
            assert p == BACK, 'returned to $%04X' % p
            rm.rec = None
            cur['T'] = r[T] - cur['t0']
            runs.append(cur); cur = None
        if cur is None and p == ENTRY and prev == CALLER:
            iy = h.iy()
            assert 0xFD80 <= iy < 0xFE20 and (iy - 0xFD80) % 10 == 0, 'IY $%04X' % iy
            cur = _open(r, rm, (iy - 0xFD80) // 10, r[SP])
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside a flight'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur, tab, rm)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                assert cur is None, 'an interrupt inside a flight'
                h.sim.accept_interrupt(r, rm, p)
    return runs


def row(name, x):
    """M7.74: NO ROM BYTE IS STORED (house rule 7; TRAPS #281).  A read below $4000 keeps its ADDRESS
    only ('rom'), and a run that read the ROM keeps its display-bitmap writes as addresses only ('blind')
    -- until M7.74 this fixture carried 201 ROM bytes in its seeds"""
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if rom and a < 0x5800]
    post = [(a, v) for a, v in post if not (rom and a < 0x5800)]
    return {'state': name, 'slot': x['slot'], 'T': x['T'],
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
    print('runs %d  paths %d  rows %d  T %d..%d  forced %s' % (F['runs'], F['paths'], len(F['rows']),
                                                             F['lo'], F['hi'], F['forced_rows']))


if __name__ == '__main__':
    main()
