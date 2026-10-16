"""M7.99b (measurement) -- THE JOIN'S TAIL AND BORIS'S ERASE, WRITE BY WRITE, UNCONTENDED.

M7.96 made `$9961` (the mid-game join) and `$915F` (the hurry reset) charge their own T, and declared two
fidelity gaps: the join's tail -- `$9998 JP $7FC0` -- runs `$7FD7`'s 64-cell attribute clear (`LD HL,$5800 /
LD B,$40 / CALL $AA49`) and the lives panel (`$7FDF CALL $806C`), which the port charged and did not make; and
`$915F` with its request up runs `$9173 LD IY,$9250 / CALL $A314` -- Boris's pixel restore -- which the port
charged and did not make.  This oracle records, for every run, EVERY main-line write with the T of the start of
the instruction that makes it, measured from the routine's entry (the CALL's landing); interrupts accepted
inside a run are bracketed out (acceptance to the return to the interrupted PC at the interrupted SP) and their
writes are not the run's.

  join     natural: a 1P saved state played on (interrupts on, no keys but '2' -- half-row $F7, bit 1 -- held
           from frame F), every `$9961` run from its call site `$8D31` until one takes the join (P2 comes in);
           F varies so the interrupt lands at different places in the tail.  Forced: `$9961` called once with
           pokes (P1 out / P2 out / lives counts across the panel's cap / the panel's paper already its ink),
           the key held, interrupts off.
  boris    natural: saved states played on with ab38cost's key script; every `$915F` run that finds its request
           ($9160) = 1 (a respawn) is kept.  Forced: the request poked, Boris's record ($9255 X, $9256 Y) moved
           over every Y & 7 phase (the restore's third band).

A row: state, label, forced, T (main-line, the run), isr ([offset, T] each), marks (offsets of the PCs in MARKS
reached on the main line, first visit), seed (every byte the main line READ before writing it, outside the
stack window, ROM ADDRESSES DROPPED -- TRAPS #281; the self-modified operand $9160 read as state), writes [[t, addr, value]] -- value -1 for a bitmap byte
($4000..$57FF or its shadow $E000..$F7FF) written outside the clear / panel / restore code: the text and award
glyphs are the ROM charset's (never stored), the engine's font is its own.

Usage:  python tools/jointail.py measure [--jobs N]   (-> build/jointail_fixture.json, N <= 6)
        python tools/jointail.py verify [--jobs N]    (re-measure, compare, say MATCH)
"""
import sys, json
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, Mem, T, PC, IFF, SP
import portconfig as pc

FIXTURE = 'build/jointail_fixture.json'
MAXJOBS = 6
GLO, GHI = 0xD000, 0xD300                      # the 128K music driver: never executed
JOIN, JOIN_SITE = 0x9961, 0x8D31
BORIS, BORIS_SITE = 0x915F, 0x8D34
MARKS = {0x7FC0: 'hud', 0x7FD7: 'clear', 0xAA49: 'aa49', 0x806C: 'panel', 0x7FE2: 'text', 0x7FFC: 'attr',
         0xA314: 'a314', 0x917A: 'ei'}
# code whose bitmap writes carry RAM values (kept): $AA49's fill, $806C's panel, $A314's restore
KEEP_PC = [(0xAA49, 0xAA50), (0x806C, 0x80FA), (0xA314, 0xA380)]
KEY_FRAMES = 25
# operands the game rewrites, read as STATE (TRAPS #275 / #278): $915F's `LD A,n` operand IS the request
SMC = {0x9160}


def _blind(p, a):
    bitmap = 0x4000 <= a < 0x5800 or 0xE000 <= a < 0xF800
    return bitmap and not any(lo <= p < hi for lo, hi in KEEP_PC)


class RunMem(Mem):
    """the harness memory, logging the open run's main-line writes (with the instruction's start T) and its
       first reads (the seed)"""
    __slots__ = ('on', 'tm', 'pc', 'w', 'seen', 'seed', 'regs', 'slo', 'shi')

    def __init__(self, base):
        Mem.__init__(self, base.m)
        self.sim = base.sim
        self.on = False; self.tm = 0; self.pc = 0; self.w = None; self.seen = None; self.seed = None
        self.regs = None; self.slo = self.shi = 0

    def __getitem__(self, i):
        if self.on and type(i) is int and i not in self.seen:
            p = self.pc
            if (i in SMC or not (p <= i < p + 4)) and not (self.slo <= i < self.shi):
                self.seen.add(i)
                if i >= 0x4000:
                    self.seed.append((i, self.m[i]))
        return self.m[i]

    def __setitem__(self, i, v):
        if self.on:
            self.seen.add(i)
            if not (self.slo <= i < self.shi):
                self.w.append([self.tm, i, -1 if _blind(self.pc, i) else v & 0xFF])
        Mem.__setitem__(self, i, v)


def _machine(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = RunMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    assert rm.m[0x8DC4] == 0xC9, state + ': not a 48K state'
    return h, rm


def _trace(h, rm, root, interrupts, budget=3 * 10 ** 6):
    """PC at the root's entry with its return address on the stack: run to the return, the main line
       recorded.  Returns the row's body."""
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    fd, ia = h.frame_duration, h.int_active
    sp0 = r[SP]
    ret = raw[sp0] | (raw[(sp0 + 1) & 0xFFFF] << 8)
    t0, isr_t, cur = r[T], 0, None
    rm.w, rm.seen, rm.seed = [], set(), []
    rm.slo, rm.shi = (sp0 - 64) & 0xFFFF, sp0 + 2
    isrs, marks, pcs = [], {}, set()
    for _ in range(budget):
        p = r[PC]
        assert not (GLO <= p < GHI), 'THE GUARDED RANGE $%04X' % p
        if cur is not None and p == cur[0] and r[SP] == cur[1]:
            d = r[T] - cur[2]
            isrs.append([cur[2] - t0 - isr_t, d])
            isr_t += d
            cur = None
        tm = r[T] - t0 - isr_t
        if cur is None:
            if p == ret and r[SP] == (sp0 + 2) & 0xFFFF:
                rm.on = False
                return {'T': tm, 'isr': isrs, 'marks': marks, 'seed': sorted(rm.seed), 'writes': rm.w,
                        'pcs': pcs}
            if p in MARKS and MARKS[p] not in marks:
                marks[MARKS[p]] = tm
            pcs.add(p)
            rm.on = True; rm.tm = tm; rm.pc = p
        else:
            rm.on = False
        op[raw[p]]()
        rm.on = False
        if interrupts and r[IFF] and r[T] % fd < ia and cur is None:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                cur = (b, spb, tt)
    raise AssertionError('no return from $%04X' % root)


def _row(state, label, forced, x):
    return {'state': state, 'label': label, 'forced': forced, 'T': x['T'], 'isr': x['isr'], 'marks': x['marks'],
            'seed': ''.join('%04x%02x' % sv for sv in x['seed']), 'writes': x['writes']}


def _enter(h, rm, root, site):
    """a CALL from the root's site, made by hand: the return address pushed, PC at the root"""
    r, raw = h.sim.registers, rm.m
    back = (site + 3) & 0xFFFF
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[(sp + 1) & 0xFFFF] = back & 0xFF, back >> 8
    r[SP] = sp; r[PC] = root


# ---------------------------------------------------------------- the forced calls (declared)
def forced(job):
    kind, label, state, pokes, key = job
    h, rm = _machine(state)
    r, raw = h.sim.registers, rm.m
    for a, v in pokes:
        raw[a] = v
    r[IFF] = 0
    fd = h.frame_duration
    r[T] = (r[T] // fd + 1) * fd + h.int_active
    if key:
        h.ports.press(0xF7, 0xFF & ~key)
    root, site = (JOIN, JOIN_SITE) if kind == 'join' else (BORIS, BORIS_SITE)
    _enter(h, rm, root, site)
    x = _trace(h, rm, root, False)
    if kind == 'join':
        assert 0x9998 in x['pcs'], label + ': no join'
    else:
        assert 0xA314 in x['pcs'], label + ': no erase'
    return kind, _row(state, label, True, x)


P1L, P2L = 0xFDDC, 0xFDE6
P1F, P2F = 0xFD87, 0xFD91
FORCED = [
    # P2 joins: P1 in play with 0..7 lives (the panel caps at 5), P1 out, P2's first cell already its ink
    ('join', 'p2_join_p1_3', 'round1_48', [(0xFED3, 1)], 2),
    ('join', 'p2_join_p1_0', 'round1_48', [(0xFED3, 1), (P1L, 0)], 2),
    ('join', 'p2_join_p1_1', 'round1_48', [(0xFED3, 1), (P1L, 1)], 2),
    ('join', 'p2_join_p1_5', 'round1_48', [(0xFED3, 1), (P1L, 5)], 2),
    ('join', 'p2_join_p1_7', 'round1_48', [(0xFED3, 1), (P1L, 7)], 2),
    ('join', 'p2_join_p1_out', 'round1_48', [(0xFED3, 1), (P1F, 0x61)], 2),
    ('join', 'p2_join_same', 'round1_48', [(0xFED3, 1), (0x5AFF, 0x28), (0x5AFE, 0x2D)], 2),
    # P1 joins: P2 in play with 2 / 6 lives, P2 out; P1's first cell already its ink
    ('join', 'p1_join_p2_2', 'round1_48', [(0xFED3, 1), (P1F, 0x61), (P2F, 0xE0), (P2L, 2)], 1),
    ('join', 'p1_join_p2_6', 'round1_48', [(0xFED3, 1), (P1F, 0x61), (P2F, 0xE0), (P2L, 6)], 1),
    ('join', 'p1_join_p2_out', 'round1_48', [(0xFED3, 1), (P1F, 0x61)], 1),
    ('join', 'p1_join_same', 'round1_48', [(0xFED3, 1), (P1F, 0x61), (0x5AE0, 0x20), (0x5AE1, 0x24)], 1),
    # another round's world (the tile buffer the spent cell is drawn from)
    ('join', 'p2_join_r20', 'r20_48', [(0xFED3, 1)], 2),
] + [
    ('boris', 'boris_y%02x_x%02x' % (y, x), 'round1_48', [(0x9160, 1), (0x9255, x), (0x9256, y)], 0)
    for x, y in ((0x88, 0xA8), (0x10, 0xA9), (0xE0, 0xAA), (0x60, 0x53), (0x30, 0x54), (0x98, 0x5D), (0x48, 0x2E),
                 (0x70, 0x17))
]


# ---------------------------------------------------------------- the natural runs
def _play_to(h, rm, root, site, press_at, frames, want, keyfn=None):
    """play on from the state (interrupts on); at each main-line CALL to the root from its site, trace the run;
       return the first that `want` accepts, or None"""
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    fd, ia = h.frame_duration, h.int_active
    t_start = r[T]
    t_end = t_start + frames * fd
    ki, nextk = 0, t_start
    depth_isr = None
    while r[T] < t_end:
        if keyfn and r[T] >= nextk:
            keyfn(h, raw, ki); ki += 1; nextk = r[T] + KEY_FRAMES * fd
        if press_at is not None and r[T] >= t_start + press_at * fd:
            h.ports.press(0xF7, 0xFF & ~2)
        p = r[PC]
        assert not (GLO <= p < GHI), 'THE GUARDED RANGE $%04X' % p
        if depth_isr is not None and p == depth_isr[0] and r[SP] == depth_isr[1]:
            depth_isr = None
        if depth_isr is None and p == site and raw[p] == 0xCD and (raw[p + 1] | (raw[p + 2] << 8)) == root:
            op[0xCD]()
            assert r[PC] == root
            if r[IFF] and r[T] % fd < ia:          # an interrupt on the CALL's own boundary: not a clean entry
                b, spb = r[PC], r[SP]
                if h.sim.accept_interrupt(r, rm, p):
                    depth_isr = (b, spb)
                    continue
            x = _trace(h, rm, root, True)
            if want(x, raw):
                return x
            continue
        op[raw[p]]()
        if r[IFF] and r[T] % fd < ia and depth_isr is None:
            b, spb = r[PC], r[SP]
            if h.sim.accept_interrupt(r, rm, p):
                depth_isr = (b, spb)
    return None


JOIN_NAT = [(s, f) for s in ('round1_48', 'r10_48', 'r20_48', 'r50_48', 'candycane', 'boris', 'lastdia81', 'crown')
            for f in (2, 5)]


def natural_join(job):
    state, f = job
    h, rm = _machine(state)
    x = _play_to(h, rm, JOIN, JOIN_SITE, f, f + 6, lambda x, raw: 0x9998 in x['pcs'])
    if x is None:
        return 'join', None
    return 'join', _row(state, 'nat_f%d' % f, False, x)


BORIS_NAT = ('death', 'boriskill', 'bosshit', 'bottle', 'hurryup', 'boris', 'fbkill', 'redcross')


def natural_boris(state):
    import costsmall as CS
    h, rm = _machine(state)
    rows = []
    r = h.sim.registers
    t_end = r[T] + 300 * h.frame_duration
    while r[T] < t_end:
        x = _play_to(h, rm, BORIS, BORIS_SITE, None, max(1, (t_end - r[T]) // h.frame_duration),
                     lambda x, raw: 0xA314 in x['pcs'], keyfn=CS._keys)
        if x is None:
            break
        rows.append(_row(state, 'nat_%d' % len(rows), False, x))
        if len(rows) >= 2:
            break
    return 'boris', rows


def measure(jobs):
    jobs = max(1, min(MAXJOBS, jobs))
    with Pool(jobs) as pool:
        f = pool.map(forced, FORCED)
        nj = pool.map(natural_join, JOIN_NAT)
        nb = pool.map(natural_boris, BORIS_NAT)
    out = {'note': __doc__.strip().split('\n\n')[0], 'marks': {'%04X' % k: v for k, v in MARKS.items()},
           'join': [], 'boris': []}
    for kind, rw in nj:
        if rw is not None:
            out['join'].append(rw)
    for kind, rws in nb:
        out['boris'].extend(rws)
    for kind, rw in f:
        out[kind].append(rw)
    return out


def summary(fx):
    lines = []
    for kind in ('join', 'boris'):
        rs = fx[kind]
        nat = [x for x in rs if not x['forced']]
        lines.append('%s: %d natural (%d with an interrupt inside), %d forced' %
                     (kind, len(nat), sum(1 for x in nat if x['isr']), len(rs) - len(nat)))
        for x in rs:
            m = x['marks']
            if kind == 'join':
                cl = [w for w in x['writes'] if 0x5800 <= w[1] < 0x5840 and m['clear'] <= w[0] < m['panel']]
                pn = [w for w in x['writes'] if m['panel'] <= w[0] < m['text']]
                lines.append('  %-10s %-16s T %6d isr %d  $7FC0 at %5d  clear %d (%d..%d)  panel %d writes (%d..%d)'
                             % (x['state'], x['label'], x['T'], len(x['isr']), m['hud'], len(cl), cl[0][0],
                                cl[-1][0], len(pn), pn[0][0], pn[-1][0]))
            else:
                ew = [w for w in x['writes'] if 0x4000 <= w[1] < 0x5B00]
                lines.append('  %-10s %-16s T %5d isr %d  erase at %d: %d display writes (%d..%d)'
                             % (x['state'], x['label'], x['T'], len(x['isr']), m['a314'], len(ew), ew[0][0],
                                ew[-1][0]))
    return '\n'.join(lines)


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else MAXJOBS
    cmd = a[0] if a and not a[0].startswith('--') else 'measure'
    if cmd not in ('measure', 'verify'):
        raise SystemExit('usage: jointail.py measure|verify [--jobs N]')
    fx = measure(jobs)
    print(summary(fx))
    if cmd == 'measure':
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(fx, f, separators=(',', ':'))
        print('wrote', FIXTURE)
        return
    with open(FIXTURE, encoding='utf-8') as f:
        old = json.load(f)
    if old == json.loads(json.dumps(fx)):
        print('MATCH')
    else:
        for k in ('join', 'boris'):
            if old.get(k) != json.loads(json.dumps(fx[k])):
                print('DIFFER in', k)
        raise SystemExit('MISMATCH')


if __name__ == '__main__':
    main()
