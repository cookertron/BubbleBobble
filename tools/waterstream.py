"""M7.66 -- THE WATER STREAM: the arm $9460 -> $A15F and the tick $A159 -> $A190.

The arm (the element arm $93DC's `JR z,$9460` for a request of 2, i.e. a water bubble popped):

    $9460  LD A,($A15A) / OR A / RET nz      a stream already running: refused
           LD A,($FECE) / OR A / RET nz      the flood up: refused
           ($FFFB) := ($FFFA)                the triggering player
           HL := ((($FFF8)+9) AND $F8) * 4   EIGHT-BIT ADD, so it wraps
           DE := (($FFF7)+8) >> 3            $9F5C, and the ADD wraps too
           HL += DE + $5800 / JP $A15F
    $A15F  ($A1AA) := R                      the direction seed, the WATER_DIR draw
           ($A15A) := 1
           HL += $A000 / scan DOWN (DE=$20) up to 22 cells for the first cell whose SHADOW
           has bit 5 clear; none found -> HL := 9 (so the band is $6009)
           HL -= $A000 / the SEVEN words $A25D..$A26A := HL   ($A26B is left alone)

The tick ($9E50's `JP z,$A159` for element class 2, on the even ticks):

    $A159  LD A,n (n IS $A15A) / OR A / RET z
    $A190  ($A194) := ($8DBD)                the operand of a CP nobody reads
           ($A15A) := 1
           step(head, +$20) ; then step(head, ($A1AA) bit 0 ? +1 : -1) ; blocked both ->
           ($A1AA) ^= 1
    $A1C6  step: cand = head + d; shadow(cand + $A000) bit 5 -> blocked (RET nz).  Else POP AF
           (the tick returns after this step), LDDR the band down one word ($A25D..$A26A ->
           $A25F..$A26C), head := cand, cand <= $5AFF -> ($cand) := $2D.  tail := ($A26B):
           tail > $5AFF -> $A205 (($A15A) := 0, then $A208); else ($tail) := ($8309) AND 7
           OR $40.  THEN, if the head was past $5AFF, $A208: ($A25A) := ($A259) := 0 and RES 4
           of $FDDA and $FDE4.  Then the carry $A21F: X := (col * 8), Y := (row * 8 - 8) of the
           band's second word, and each player whose bit 4 is set is put there.

Captured:
  arms:     $9460 at its own entry on elwater for every ($FFF7) byte at three rows, every
            ($FFF8) byte at three columns, and the refusals ($A15A set, $FECE set).
  runs:     one arm then $A159 called until the stream stops (or a cap), CONTINUOUSLY, on
            elwater's own platforms from a grid of pops and on built shadows: an open field (the
            head leaves the bottom, $A208, then the tail, $A205), a corridor on row 0 that
            walks the head LEFT past $5800 into the bitmap, a corridor on row 23 that walks it
            RIGHT past $5AFF, a one-cell pocket (blocked three ways: $A1AA toggles, nothing
            moves), with the carry gates in every combination.  ($8DBD) steps by one per call.
  natural:  every $9460 and $A159 entry over 700 idle ISRs of elwater, each re-run from its
            entry with interrupts off.

Per call: the pre-state vector ($FD00..$FDFF, $A259..$A26D, the named scalars, and the shadow
$F7C0..$FC3F by reference into a table of distinct shadows), the R byte read at $A15F, every
display write IN ORDER (the paints are the behaviour), and every other non-stack write.  No ROM
byte: the watch starts at $4000, and no built world lets a band reach $6009 (whose shadow is ROM).

Usage:  python tools/waterstream.py            capture -> build/waterstream_fixture.json
        python tools/waterstream.py verify     re-run and diff against the fixture
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, SP, IFF, R as RR, A as RA, H as RH, L as RL
import portconfig as pc

FIXTURE = 'build/waterstream_fixture.json'
BRANCH_BYTE = 0x8DC4
ARM, TICK, R_READ = 0x9460, 0xA159, 0xA161
GUARD = range(0xD000, 0xD300)
SCALARS = [0xA15A, 0xA1AA, 0xA194, 0x8309, 0x8DBD, 0xFFF7, 0xFFF8, 0xFFF9, 0xFFFA, 0xFFFB, 0xFECE]
FD_LO, FD_HI = 0xFD00, 0xFE00
Q_LO, Q_HI = 0xA259, 0xA26E
SH_LO, SH_HI = 0xF7C0, 0xFC40
STATE = 'elwater'


def new(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, h.memobj.m


class Shadows:
    def __init__(self):
        self.table, self.index = [], {}

    def ref(self, m):
        s = bytes(m[SH_LO:SH_HI]).hex()
        if s not in self.index:
            self.index[s] = len(self.table)
            self.table.append(s)
        return self.index[s]


def vector(m, sh, full=True):
    v = {'scalars': [m[a] for a in SCALARS], 'shadow': sh.ref(m)}
    if full:
        v.update(fd=list(m[FD_LO:FD_HI]), q=list(m[Q_LO:Q_HI]))
    return v


def run_call(h, entry, sh, stop=None, full=True):
    """`entry` at its own entry with sentinels pushed (or, with `stop`, from the current PC
       to the return address `stop` at SP + 2), interrupts off, single-stepped."""
    m, r = h.memobj.m, h.sim.registers
    pre = vector(m, sh, full)
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
    rv, n = None, 0
    while True:
        p = r[PC]
        if p in GUARD:
            h.memobj.unwatch()
            raise SystemExit('GUARD: PC $%04X' % p)
        if p in stops and r[SP] == want_sp:
            break
        if p == R_READ:
            rv = r[RA]
        if p in (0xA172, 0xA1CC):                    # the two shadow reads: never ROM
            hl = (r[RH] << 8) | r[RL]
            if not SH_LO <= hl < SH_HI:
                h.memobj.unwatch()
                raise SystemExit('shadow read at $%04X outside the vector (PC $%04X)' % (hl, p))
        h.step(1, interrupts=False)
        n += 1
        if n > 200_000:
            h.memobj.unwatch()
            raise SystemExit('runaway')
    h.memobj.unwatch()
    if stop is None:
        r[SP] = sp0          # the sentinel RET leaves SP ten below (TRAPS #268)
    sp_lo = (sp - 0x100) & 0xFFFF
    post, disp = {}, []
    for _pc, a, v in h.memobj.log:
        if 0x4000 <= a < 0x5B00:
            disp.append([a, v])
        elif sp_lo <= a < sp0:
            pass
        else:
            post[a] = v
    return {'entry': entry, 'pre': pre, 'r': rv, 'disp': disp,
            'post': sorted([a, v] for a, v in post.items()), 'steps': n}


# ------------------------------------------------------------------ built
def arm_cases():
    C = []
    for y in (0x20, 0x57, 0xA8):
        for x in range(256):
            C.append(('x%02X_y%02X' % (x, y), x, y, {}))
    for x in (0x10, 0x63, 0xE8):
        for y in range(256):
            C.append(('y%02X_x%02X' % (y, x), x, y, {}))
    C += [('refused_running', 0x60, 0x40, {0xA15A: 1}),
          ('refused_flood', 0x60, 0x40, {0xFECE: 1}),
          ('p2', 0x60, 0x40, {0xFFFA: 2})]
    # on an OPEN shadow the band is the arm's own cell, so both eight-bit adds show whole
    for x in range(256):
        C.append(('open_x%02X' % x, x, 0x57, {'open': 1}))
    for y in range(256):
        C.append(('open_y%02X' % y, 0x63, y, {'open': 1}))
    return C


def arms(sh):
    h, m = new(STATE)
    base = h.save_state()
    out = []
    for i, (label, x, y, scal) in enumerate(arm_cases()):
        h.load_state(base)
        h.sim.registers[RR] = (i * 13) & 0x7F
        m[0xA15A], m[0xFECE] = 0, 0
        m[0xFFF7], m[0xFFF8] = x, y
        for a, v in scal.items():
            if a == 'open':
                shade(m, 0x00)
            else:
                m[a] = v
        c = run_call(h, ARM, sh, full=False)
        c.update(family='arm', label=label)
        out.append(c)
    return out


def shade(m, fill, open_cells=()):
    """a built shadow: every cell of $F800..$FAFF := fill, the listed ones open ($00); the
       margin before the file open, the margin after it `fill` except its column 0 (so a head
       on row 23 walks right through $5AFF to $5B00 before it falls)"""
    for a in range(SH_LO, SH_HI):
        m[a] = 0x00 if a < 0xFB00 or (a - 0xFB00) % 32 == 0 else fill
    for a in range(0xF800, 0xFB00):
        m[a] = fill
    for c in open_cells:
        m[0xF800 + c] = 0x00


def run_cases():
    C = []
    k = 0
    for row in range(1, 23, 4):                       # elwater's own platforms, a grid of pops
        for col in range(2, 32, 5):
            gates = (k % 4)                          # none, P1, P2, both
            C.append(('grid_r%02d_c%02d' % (row, col), col * 8, row * 8, gates, None, 120,
                      {0x8309: 0xF8 | k % 8} if k % 3 == 0 else {}))
            k += 1
    C += [
        ('open_field', 0x78, 0x30, 3, ('open',), 60, {0x8309: 0xB5}),
        ('left_wrap', 0x30, 0x00, 1, ('row', 0), 40, {}),
        ('right_edge', 0xC0, 0xB0, 2, ('row', 23), 60, {}),
        ('pocket', 0x60, 0x60, 3, ('pocket', 12 * 32 + 12), 12, {}),
    ]
    return C


def runs(sh):
    h, m = new(STATE)
    base = h.save_state()
    out = []
    for i, (label, x, y, gates, world, cap, scal) in enumerate(run_cases()):
        h.load_state(base)
        h.sim.registers[RR] = ((i >> 1) * 29 + 5) & 0x7F   # direction and gates decorrelated
        m[0xA15A], m[0xFECE] = 0, 0
        m[0xFFF7], m[0xFFF8] = x, y
        m[0xFDDA] = (m[0xFDDA] & 0xEF) | (0x10 if gates & 1 else 0)
        m[0xFDE4] = (m[0xFDE4] & 0xEF) | (0x10 if gates & 2 else 0)
        if world:
            if world[0] == 'open':
                shade(m, 0x00)
            elif world[0] == 'row':
                shade(m, 0x20, range(world[1] * 32, world[1] * 32 + 32))
            elif world[0] == 'pocket':
                shade(m, 0x20, (world[1],))
        # the arm scans DOWN from one row below ($FFF8 + 9); aim it at the row itself
        if world and world[0] == 'row':
            m[0xFFF8] = (world[1] * 8 - 9) & 0xFF
        if world and world[0] == 'pocket':
            m[0xFFF8] = ((world[1] >> 5) * 8 - 9) & 0xFF
            m[0xFFF7] = ((world[1] & 31) * 8 - 8) & 0xFF   # $947F ADD A,8
        for a, v in scal.items():
            m[a] = v
        calls = [run_call(h, ARM, sh)]
        for i in range(cap):
            m[0x8DBD] = (m[0x8DBD] + 1) & 0xFF
            calls.append(run_call(h, TICK, sh))
            if not m[0xA15A]:
                break
        first = calls[0]['pre']
        for c in calls:
            del c['pre']
        out.append({'family': 'run', 'label': label, 'pre': first, 'calls': calls})
    return out


# ------------------------------------------------------------------ natural
def natural(sh, isrs=700):
    h, m = new(STATE)
    r = h.sim.registers
    out, isr = [], 0
    while isr <= isrs:
        reason, _n = h.run_until((0x8D72, ARM, TICK), limit=3_000_000)
        if reason != 'target':
            raise SystemExit('natural: limit')
        p = r[PC]
        if p == 0x8D72:
            isr += 1
        else:
            snap = h.save_state()
            ret = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
            iff = r[IFF]
            c = run_call(h, p, sh, stop=ret)
            c.update(family='natural', label='isr%d_%04X' % (isr, p), iff=iff)
            out.append(c)
            h.load_state(snap)
        h.step(1)
    return out


def capture():
    sh = Shadows()
    a, rn, nat = arms(sh), runs(sh), natural(sh)
    return {'note': 'tools/waterstream.py -- see its docstring', 'scalars': SCALARS,
            'fd': [FD_LO, FD_HI], 'q': [Q_LO, Q_HI], 'shadow': [SH_LO, SH_HI],
            'shadows': sh.table, 'arms': a, 'runs': rn, 'natural': nat}


def summary(fx):
    print('shadows', len(fx['shadows']), 'arms', len(fx['arms']),
          'refused', sum(1 for c in fx['arms'] if not c['post']),
          'r values', sorted({c['r'] for c in fx['arms'] if c['r'] is not None})[:8], '...')
    for rn in fx['runs']:
        cs = rn['calls']
        a15 = [c for c in cs if any(a == 0xA15A and v == 0 for a, v in c['post'])]
        print('  run %-14s %3d calls, disp %4d, stops %d, carry %d' % (
            rn['label'], len(cs), sum(len(c['disp']) for c in cs), len(a15),
            sum(1 for c in cs if any(a in (0xFD85, 0xFD86, 0xFD8F, 0xFD90) for a, _ in c['post']))))
    nat = fx['natural']
    print('natural', len(nat), 'arms', sum(1 for c in nat if c['entry'] == ARM),
          'ticks live', sum(1 for c in nat if c['entry'] == TICK and c['post']),
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
