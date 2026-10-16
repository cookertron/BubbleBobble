"""M7.67 -- THE FIRE ELEMENTAL: the arm $93FD and the manager $9F63 (drop, landing, burn, end).

The arm (the element arm $93DC's `JR z,$93FD` for a request of 4, i.e. a fire bubble popped):

    $93FD  LD A,($9F64) / OR A / RET nz      a fire already alive: refused
           ($9F64) := 1
           ($FDF3) := (($FFF7) + 8) AND $F8   X, an EIGHT-BIT add
           ($FDF4) := (($FFF8) + 15) AND $F8  Y, an EIGHT-BIT add

The manager ($9E50's `JP z,$9F63` for element class 4, on the even ticks -- AFTER $9E64 has
already stepped a non-zero ($9F64) by one, whatever the class):

    $9F63  LD A,n (n IS $9F64) / OR A / RET z / INC A / CP $20 / JP nc,$A04E
           the DROP: erase its cell from the backing store ($9FE0 the address from the
           $FD00 row table, $9FF6 copies 8 bytes from addr + $A000); the shadow cell $AEDC of
           (X, Y) solid, or the one below it open -> $A00D FALL; else LAND
    $A00D  Y += 8 (eight-bit); >= $BF -> ($9F64) := 0 (gone, nothing drawn); else draw the
           drop glyph $B624 at the new cell
    $9F8F  LAND: (IX+4) := 1, spread LEFT then RIGHT from the floor cell, up to 4 steps each
           ($9FC8: the next floor cell must be floor AND the cell above it open), counting
           in ($FDF2); the left steps walk the SCREEN address's low byte down (DEC L, eight
           bit) and ($FDF0) := the leftmost; ($9F64) := $2A
    $A04E  BURN: ($9F64) := A; A >= $FA -> $A030; the frame $A39D / $A3A5 by bit 3 into
           $A074 (the operand of $A073 LD DE,nn); ($FDF2) := max(1, ($FDF2)) (SUB 1 / ADC
           A,1); the flames painted from ($FDF0), INC L eight-bit; the attributes $42
    $A030  END: ($9F64) := 0; the cells restored from the backing store; the attributes
           ($8309) OR $40 -- the WHOLE byte, no AND 7

Captured:
  arms:     $93FD at its own entry on elfire for every ($FFF7) byte at three Ys, every ($FFF8)
            byte at three Xs, and the refusal at three ($9F64) values.
  direct:   $9F63 at its own entry: every ($9F64) byte with a nine-flame row; every count
            0..12 mid-burn and at the end; the flame row's low byte at the page edge; every
            ($FDF4) byte and every ($FDF3) byte with ($9F64) = 1 on elfire and on a built floor.
  runs:     one arm, then $9E50 every frame (class 4 forced, ($8DBD) stepped) until the fire is
            gone and two frames more, CONTINUOUSLY: a grid of pops on elfire's own platforms and
            built shadows -- a full floor (the spread's search is the identity: 4 + 4), a gap at
            distance 1..5 each side, a wall at distance 1..5 each side, the drop at columns
            0/1/30/31 and on row 8 (the screen's DEC L wraps inside its third while the shadow
            walks back a row), an open field (off the bottom), a solid spawn cell, the Y wrap
            (the first erase lands in ROM via the table's rows 24..31), an immediate landing.
  natural:  every $93FD and $9F63 entry over idle ISRs of elfire, of firekill (a fire alive), and
            of elfire with a fire request poked in ($FFF9 = 4), each re-run from its entry with
            interrupts off.

Per call: the pre-state (named scalars, $FD00..$FDFF, and by reference into tables of distinct
blocks: the shadow $F7C0..$FC3F, the backing store $E000..$F7FF, the code pages $A000..$A9FF
where the flame frames and the $A074 operand live), every display write IN ORDER, and every
other non-stack write.  No ROM byte: the watch starts at $4000 and no vector reaches below.

Usage:  python tools/fireman.py            capture -> build/fireman_fixture.json
        python tools/fireman.py verify     re-run and diff against the fixture
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, SP, IFF
import portconfig as pc

FIXTURE = 'build/fireman_fixture.json'
BRANCH_BYTE = 0x8DC4
ARM, MGR, TICK = 0x93FD, 0x9F63, 0x9E50
GUARD = range(0xD000, 0xD300)
SCALARS = [0x9F64, 0x8309, 0x8609, 0x7E0E, 0x8DBD, 0x9E57, 0x9E5D, 0x9DDE, 0xFFF7, 0xFFF8,
           0xFFF9, 0xFFFA] + list(range(0xB624, 0xB62C))
FD_LO, FD_HI = 0xFD00, 0xFE00
BLOCKS = {'shadow': (0xF7C0, 0xFC40), 'back': (0xE000, 0xF800), 'code': (0xA000, 0xAA00)}
STATE = 'elfire'


def new(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, h.memobj.m


class Refs:
    def __init__(self):
        self.table = {k: [] for k in BLOCKS}
        self.index = {k: {} for k in BLOCKS}

    def ref(self, m, k):
        lo, hi = BLOCKS[k]
        s = bytes(m[lo:hi]).hex()
        if s not in self.index[k]:
            self.index[k][s] = len(self.table[k])
            self.table[k].append(s)
        return self.index[k][s]


def vector(m, rf, full=True):
    v = {'scalars': [m[a] for a in SCALARS]}
    if full:
        v['fd'] = list(m[FD_LO:FD_HI])
        for k in BLOCKS:
            v[k] = rf.ref(m, k)
    return v


def run_call(h, entry, rf, stop=None, full=True):
    """`entry` at its own entry with sentinels pushed (or, with `stop`, from the current PC
       to the return address `stop` at SP + 2), interrupts off, single-stepped."""
    m, r = h.memobj.m, h.sim.registers
    pre = vector(m, rf, full)
    sp0 = r[SP]
    if stop is None:
        sp = sp0
        for s in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp], m[sp + 1] = s & 0xFF, s >> 8
        r[SP] = sp
        r[PC] = entry
        stops, want_sp = set(h.SENTINELS), (sp + 2) & 0xFFFF
    else:
        sp = sp0
        stops, want_sp = {stop}, (sp0 + 2) & 0xFFFF
    h.memobj.watch(0x4000, 0x10000)
    n = 0
    while True:
        p = r[PC]
        if p in GUARD:
            h.memobj.unwatch()
            raise SystemExit('GUARD: PC $%04X' % p)
        if p in stops and r[SP] == want_sp:
            break
        h.step(1, interrupts=False)
        n += 1
        if n > 400_000:
            h.memobj.unwatch()
            raise SystemExit('runaway')
    h.memobj.unwatch()
    if stop is None:
        r[SP] = sp0          # the sentinel RET leaves SP ten below: continuous runs would walk it down
    sp_lo = (sp - 0x100) & 0xFFFF
    post, disp = {}, []
    for _pc, a, v in h.memobj.log:
        if 0x4000 <= a < 0x5B00:
            disp.append([a, v])
        elif sp_lo <= a < sp0:
            pass
        else:
            post[a] = v
    return {'entry': entry, 'pre': pre, 'disp': disp,
            'post': sorted([a, v] for a, v in post.items()), 'steps': n}


# ------------------------------------------------------------------ built worlds
def back_pattern(m):
    """a backing store whose every byte names its address, so a restore from the wrong cell
       or the wrong line cannot pass"""
    for a in range(0xE000, 0xF800):
        m[a] = (a * 7 + (a >> 8) * 13 + 1) & 0xFF


def world(m, floors=(), solids=()):
    """a built shadow: every cell open; `floors` (row, col0, col1) solid runs; `solids` cells"""
    for a in range(0xF7C0, 0xFC40):
        m[a] = 0x00
    for row, c0, c1 in floors:
        for c in range(c0, c1 + 1):
            m[0xF800 + row * 32 + c] = 0x20
    for row, c in solids:
        m[0xF800 + row * 32 + c] = 0x20
    back_pattern(m)


def pop_over(col, row):
    """($FFF7, $FFF8) whose arm puts the drop at (col, row): X = (x+8)&F8, Y = (y+15)&F8"""
    return (col * 8 - 8) & 0xFF, (row * 8 - 15) & 0xFF


# ------------------------------------------------------------------ the arms
def arm_cases():
    C = []
    for y in (0x20, 0x57, 0xA8):
        for x in range(256):
            C.append(('x%02X_y%02X' % (x, y), x, y, 0))
    for x in (0x10, 0x63, 0xE8):
        for y in range(256):
            C.append(('y%02X_x%02X' % (y, x), x, y, 0))
    C += [('refused_01', 0x60, 0x40, 0x01), ('refused_2A', 0x60, 0x40, 0x2A),
          ('refused_FF', 0x60, 0x40, 0xFF)]
    return C


def arms(rf):
    h, m = new(STATE)
    base = h.save_state()
    out = []
    for label, x, y, n in arm_cases():
        h.load_state(base)
        m[0x9F64], m[0xFFF7], m[0xFFF8] = n, x, y
        m[0xFDF3], m[0xFDF4] = 0x5A, 0x5A              # so "not written" and "wrote" differ
        c = run_call(h, ARM, rf, full=False)
        c.update(family='arm', label=label)
        out.append(c)
    return out


# ------------------------------------------------------------------ the manager, direct
def direct_cases():
    C = []
    for n in range(256):                               # every phase byte, a nine-flame row
        C.append(('n%02X' % n, {'n': n, 'fdf0': 0x48A3, 'cnt': 9}))
    for n in (0x40, 0x48, 0xF8, 0xF9):                 # every count, both frames, the end
        for cnt in range(13):
            C.append(('n%02X_c%02d' % (n, cnt), {'n': n, 'fdf0': 0x50C4, 'cnt': cnt}))
    C += [('edge_burn', {'n': 0x40, 'fdf0': 0x40FC, 'cnt': 9}),   # INC L wraps in the page
          ('edge_end', {'n': 0xF9, 'fdf0': 0x40FC, 'cnt': 9}),
          ('zero_end', {'n': 0xF9, 'fdf0': 0x4860, 'cnt': 0})]     # 256 cells, 256 attrs
    for y in range(256):                               # the drop at every Y, both worlds
        C.append(('fall_y%02X_el' % y, {'n': 1, 'x': 0x60, 'y': y}))
        C.append(('fall_y%02X_bu' % y, {'n': 1, 'x': 0x60, 'y': y, 'built': 1}))
    for x in range(256):                               # and every X
        C.append(('fall_x%02X_el' % x, {'n': 1, 'x': x, 'y': 0x48}))
        C.append(('fall_x%02X_bu' % x, {'n': 1, 'x': x, 'y': 0x98, 'built': 1}))
    for n in range(1, 0x20):                           # the fall's phase bytes, and the cut
        C.append(('fall_n%02X' % n, {'n': n, 'x': 0x60, 'y': 0x48}))
    return C


def directs(rf):
    h, m = new(STATE)
    base = h.save_state()
    out = []
    for label, d in direct_cases():
        h.load_state(base)
        m[0x9F64] = d['n']
        if 'fdf0' in d:
            m[0xFDF0], m[0xFDF1], m[0xFDF2] = d['fdf0'] & 0xFF, d['fdf0'] >> 8, d['cnt']
            m[0xFDF3], m[0xFDF4] = 0x60, 0x48
        else:
            m[0xFDF3], m[0xFDF4] = d['x'], d['y']
            m[0xFDF0], m[0xFDF1], m[0xFDF2] = 0x5A, 0x5A, 0x5A
        if d.get('built'):
            # a floor on row 20 with gaps and walls, so the drop's X sweep lands on all of them
            world(m, floors=[(20, 0, 9), (20, 11, 20), (20, 23, 31)], solids=[(19, 4), (19, 27)])
        c = run_call(h, MGR, rf)
        c.update(family='direct', label=label)
        out.append(c)
    return out


# ------------------------------------------------------------------ continuous runs
def run_cases():
    C = []
    k = 0
    for row in (3, 9, 15, 21):                         # elfire's own platforms
        for col in (3, 11, 19, 27):
            C.append(('grid_r%02d_c%02d' % (row, col), col * 8, row * 8, None,
                      {0x8309: (0x38, 0xF8, 0x05, 0x47)[k % 4]}))
            k += 1
    full = [(20, 0, 31)]
    C.append(('full_c15', *pop_over(15, 12), {'floors': full}, {0x8309: 0xB5}))
    for d in range(1, 6):
        C.append(('gapL%d' % d, *pop_over(15, 12), {'floors': [(20, 0, 14 - d), (20, 16 - d, 31)]}, {}))
        C.append(('gapR%d' % d, *pop_over(15, 12), {'floors': [(20, 0, 14 + d), (20, 16 + d, 31)]}, {}))
        C.append(('wallL%d' % d, *pop_over(15, 12), {'floors': full, 'solids': [(19, 15 - d)]}, {}))
        C.append(('wallR%d' % d, *pop_over(15, 12), {'floors': full, 'solids': [(19, 15 + d)]}, {}))
    for col in (0, 1, 2, 29, 30, 31):
        C.append(('edge_c%02d' % col, *pop_over(col, 12), {'floors': full}, {}))
    for col in (0, 1, 3, 31):                          # landing on row 8: the third's own page
        C.append(('third_c%02d' % col, *pop_over(col, 3), {'floors': [(9, 0, 31)]}, {}))
    C += [
        ('open_field', *pop_over(12, 4), {'floors': []}, {}),
        ('solid_spawn', *pop_over(12, 6), {'floors': full, 'solids': [(6, 12), (7, 12)]}, {}),
        ('y_wrap', 0x58, 0xE9, {'floors': [(5, 0, 31)]}, {}),
        ('land_now', *pop_over(12, 19), {'floors': full}, {}),
        ('x_wrap', 0xF8, 0x30, {'floors': full}, {}),
        ('bottom_row', *pop_over(8, 20), {'floors': [(23, 0, 31)]}, {}),
        # the left spread walks PAST column 0: the shadow goes back a row (linear), the screen
        # address's DEC L wraps inside its own third's page -- row 8 to $48FF, row 0 to $40FF
        ('third_wrap', *pop_over(1, 8), {'floors': [(9, 0, 31)], 'solids': [(8, 31)]}, {}),
        ('top_wrap', *pop_over(1, 0), {'floors': [(1, 0, 31)], 'solids': [(0, 31)]}, {}),
        ('mid_wrap', *pop_over(1, 12), {'floors': [(13, 0, 31)], 'solids': [(12, 31)]}, {}),
    ]
    return C


def runs(rf, cap=600):
    h, m = new(STATE)
    base = h.save_state()
    out = []
    for label, x, y, w, scal in run_cases():
        h.load_state(base)
        if w is not None:
            world(m, w.get('floors', ()), w.get('solids', ()))
        m[0x9F64], m[0x9DDE] = 0, 0
        m[0x7E0E], m[0x8609] = 4, 0x19
        m[0xFFF7], m[0xFFF8] = x, y
        m[0x9E57] = (m[0x8DBD] - 1) & 0xFF
        m[0x9E5D] = 0
        for a, v in scal.items():
            m[a] = v
        calls = [run_call(h, ARM, rf)]
        tail = None
        for i in range(cap):
            m[0x8DBD] = (m[0x8DBD] + 1) & 0xFF
            calls.append(run_call(h, TICK, rf, full=False))
            if tail is None and not m[0x9F64]:
                tail = 2
            elif tail is not None:
                tail -= 1
                if tail == 0:
                    break
        first = calls[0]['pre']
        for c in calls:
            del c['pre']
        out.append({'family': 'run', 'label': label, 'pre': first, 'calls': calls})
    return out


# ------------------------------------------------------------------ natural
def natural(rf, state, isrs, label, poke=None):
    h, m = new(state)
    if poke:
        for a, v in poke.items():
            m[a] = v
    r = h.sim.registers
    out, isr = [], 0
    while isr <= isrs:
        reason, _n = h.run_until((0x8D72, ARM, MGR), limit=3_000_000)
        if reason != 'target':
            raise SystemExit('natural: limit')
        p = r[PC]
        if p == 0x8D72:
            isr += 1
        else:
            snap = h.save_state()
            ret = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
            iff = r[IFF]
            c = run_call(h, p, rf, stop=ret)
            c.update(family='natural', label='%s_isr%d_%04X' % (label, isr, p), iff=iff)
            out.append(c)
            h.load_state(snap)
        h.step(1)
    return out


def capture():
    rf = Refs()
    a, d, rn = arms(rf), directs(rf), runs(rf)
    nat = (natural(rf, 'elfire', 300, 'elfire') + natural(rf, 'firekill', 300, 'firekill') +
           natural(rf, 'elfire', 400, 'request', {0xFFF9: 4, 0xFFFA: 1, 0xFFF7: 0x78, 0xFFF8: 0x40}))
    # the code page differs from call to call only in its self-modified operands: every entry
    # after the first is held as its [offset, value] differences from the first
    code = rf.table['code']
    b0 = bytes.fromhex(code[0])
    tables = dict(rf.table, code=[code[0]] + [
        [[i, v] for i, v in enumerate(bytes.fromhex(t)) if v != b0[i]] for t in code[1:]])
    return {'note': 'tools/fireman.py -- see its docstring', 'scalars': SCALARS,
            'fd': [FD_LO, FD_HI], 'blocks': {k: list(v) for k, v in BLOCKS.items()},
            'tables': tables, 'arms': a, 'direct': d, 'runs': rn, 'natural': nat}


def summary(fx):
    print('tables', {k: len(v) for k, v in fx['tables'].items()}, 'arms', len(fx['arms']),
          'refused', sum(1 for c in fx['arms'] if not c['post']), 'direct', len(fx['direct']))
    for rn in fx['runs']:
        cs = rn['calls']
        cnt = [v for c in cs for a, v in c['post'] if a == 0xFDF2]
        land = [c for c in cs if any(a == 0x9F64 and v == 0x2A for a, v in c['post'])]
        print('  run %-14s %3d calls, disp %5d, landed %d, flames %s' % (
            rn['label'], len(cs), sum(len(c['disp']) for c in cs), len(land),
            cnt[-1] if cnt else '-'))
    nat = fx['natural']
    print('natural', len(nat), 'arms', sum(1 for c in nat if c['entry'] == ARM),
          'live', sum(1 for c in nat if c['entry'] == MGR and c['post']),
          'disp', sum(len(c['disp']) for c in nat))


def main():
    fx = capture()
    if sys.argv[1:] == ['verify']:
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        same = json.loads(json.dumps(fx)) == old
        print('MATCH' if same else 'DIFFER')
        sys.exit(0 if same else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as f:
        json.dump(fx, f, separators=(',', ':'))
    print('wrote', FIXTURE)
    summary(fx)


if __name__ == '__main__':
    main()
