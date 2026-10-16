# -*- coding: utf-8 -*-
"""M7.18 -- $931A, THE ENVIRONMENT KILL: death by ATTRIBUTE COLOUR, and a
second self-modified opcode that means the same thing twice over.

The sixteenth chain entry ($8D55).  It walks the enemy table and then both
players, and asks the same question of each: what colour is the screen where
you are standing?

  (a) *** $93C4 IS AN OPCODE AND IT IS A MODE SWITCH, EXACTLY LIKE $92DE. ***
      `$931E XOR A / LD ($93C4),A` writes $00, so a hazard hit FALLS THROUGH
      into $93C5 and the entity is CORPSED; `$9334 LD A,$C9` writes a RET, so
      a hit RETURNS with the matched attribute in A and the caller decides.
      The enemies are swept with the NOP, the players with the RET.
  (b) THE PROBE IS THREE CELLS AND THEY ARE NOT TESTED ALIKE.  The entity's own
      attribute cell and the one at +$21 are tested for PAPER 5 (`AND $38 /
      CP $28`) AND for BRIGHT INK 2 (`AND $47 / CP $42`); the cell at +$20 --
      reached by `DEC L`, which is EIGHT BIT -- is tested ONLY for the ink.
  (c) AND THE PLAYER DOES NOT DIE THE WAY AN ENEMY DOES.  $9349 and $935D are
      `SUB $28`, so of the two conditions only PAPER 5 reaches the player's
      tail -- and that tail is not a death at all: `SET 4,(IX+$5A)` is the
      WATER-CARRY bit, the very bit $9286 refuses a kill on.

Usage:  python tools/envkill.py            (capture)
        python tools/envkill.py --jobs 15  (the sweeps, across cores)
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/envkill_fixture.json'
BRANCH_BYTE = 0x8DC4
PASS_ = 0x931A
PROBE = 0x9377            # the per-entity attribute test
MODE = 0x93C4             # the OPCODE that is a mode switch
CORPSE = 0x93C5
ATTRS = 0x5800
ENEMIES = 0xFD9B          # slot 0's +7
SLOTS = 0xAA57
FLOOD = 0xFECE
STATE = 'round1_48'
SCRATCH = 0xFC00


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, limit=8 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])


def quiet(m):
    """A world where NOTHING is in a hazard: every attribute a harmless $07."""
    for a in range(ATTRS, 0x5B00):
        m[a] = 0x07


# ------------------------------------------------- (a) the opcode mode switch
def phase_mode():
    rows = {}
    for s in ('round1_48', 'r20_48', 'play1p48', 'boss', 'hurryup', 'elwater'):
        try:
            h, m = new(s)
        except (Exception, SystemExit):
            continue
        rows[s] = m[MODE]
    h, m = new()
    quiet(m)
    before = m[MODE]
    arm(h, PASS_)
    run(h)
    print('(a) $93C4 in the saved states: %s'
          % ' '.join('%s=$%02X' % (k, v) for k, v in rows.items()))
    print('    before $931A: $%02X   after: $%02X (%s)'
          % (before, m[MODE], 'RET' if m[MODE] == 0xC9 else 'NOP'))
    return {'states': rows, 'before': before, 'after': m[MODE]}


# --------------------------------------------------- (b) every attribute byte
def _attr_slice(args):
    """ALL 256 attribute values through $9377, as an ENEMY and as a PLAYER."""
    lo, hi = args
    h, m = new()
    quiet(m)
    r = h.sim.registers
    #  a synthetic entity at a known cell
    m[SCRATCH + 7] = 0x80              # active, not a corpse
    m[SCRATCH + 6] = 0x40              # Y = 64  -> attr row 8
    m[SCRATCH + 5] = 0x40              # X = 64  -> attr col 8
    cell = ATTRS + 8 * 32 + 8
    base = arm(h, PROBE)
    out = []
    for v in range(lo, hi):
        row = {'attr': v}
        for mode, key in ((0x00, 'enemy'), (0xC9, 'player')):
            m[MODE] = mode
            for a in (cell, cell + 0x20, cell + 0x21):
                m[a] = 0x07
            m[cell] = v
            m[SCRATCH + 7] = 0x80
            m[SCRATCH + 9] = 0x00
            r[SP] = base
            r[PC] = PROBE
            r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
            r[2], r[3] = 0x58, 0x00        # BC = $5800 (the main set)
            r[0] = 0
            #  $931A does `LD BC,$5800 / EXX`, so the ALTERNATE BC carries it
            r[18], r[19] = 0x58, 0x00
            h.run_until(h.SENTINELS, limit=20000, stride=1, interrupts=False)
            row[key] = {'A': r[0], 'corpsed': m[SCRATCH + 9] == 0xFF}
        out.append(row)
    return out


def phase_attrs(jobs=15):
    bands = [(v, min(v + 16, 256)) for v in range(0, 256, 16)]
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(_attr_slice, bands):
            rows.extend(part)
    rows.sort(key=lambda r: r['attr'])
    kills = [r['attr'] for r in rows if r['enemy']['corpsed']]
    carries = [r['attr'] for r in rows if r['player']['A'] == 0x28]
    inked = [r['attr'] for r in rows if r['player']['A'] == 0x42]
    print('(b) ATTRIBUTE VALUES, all 256:')
    print('    %d corpse an ENEMY; %d leave A = $28 for a player and %d leave $42'
          % (len(kills), len(carries), len(inked)))
    print('    paper-5 set: %s' % ' '.join('%02X' % v for v in carries[:10]))
    print('    ink-set    : %s' % ' '.join('%02X' % v for v in inked[:10]))
    return {'rows': rows, 'kills': kills, 'paper5': carries, 'ink': inked}


# --------------------------------------------------- (c) which cells are READ
def phase_cells():
    """A READ WATCH over the attribute file: exactly which cells $9377 asks
       about, and -- by poking one at a time -- which TEST each one gets."""
    h, m = new()
    quiet(m)
    m[SCRATCH + 7] = 0x80
    m[SCRATCH + 6] = 0x40
    m[SCRATCH + 5] = 0x40
    cell = ATTRS + 8 * 32 + 8
    reads = []
    orig = type(h.memobj).__getitem__

    def spy(self, a):
        if isinstance(a, int) and ATTRS <= a < 0x5B00:
            reads.append(a)
        return orig(self, a)
    type(h.memobj).__getitem__ = spy
    try:
        m[MODE] = 0xC9
        r = h.sim.registers
        arm(h, PROBE)
        r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
        r[18], r[19] = 0x58, 0x00
        run(h)
    finally:
        type(h.memobj).__getitem__ = orig
    seen = sorted(set(reads))
    #  ...and one cell at a time, both conditions
    per = {}
    for off in (0x00, 0x20, 0x21):
        per['%d' % off] = {}
        for v, name in ((0x28, 'paper5'), (0x42, 'ink2bright')):
            h2, m2 = new()
            quiet(m2)
            m2[SCRATCH + 7] = 0x80
            m2[SCRATCH + 6] = 0x40
            m2[SCRATCH + 5] = 0x40
            m2[MODE] = 0xC9
            m2[cell + off] = v
            r2 = h2.sim.registers
            arm(h2, PROBE)
            r2[6], r2[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
            r2[18], r2[19] = 0x58, 0x00
            r2[0] = 0
            run(h2)
            per['%d' % off][name] = r2[0]
    print('(c) CELLS READ: %s  (the entity is at $%04X, so +%s)'
          % (' '.join('$%04X' % a for a in seen), cell,
             '/+'.join('%02X' % (a - cell) for a in seen)))
    for off, d in per.items():
        print('      +$%02X -> paper5 A = $%02X, ink A = $%02X'
              % (int(off), d['paper5'], d['ink2bright']))
    return {'cells': ['%04X' % a for a in seen], 'base': '%04X' % cell,
            'per_cell': per}


# ------------------------------------------------------------ (d) the gates
def phase_gates():
    cases = []

    def one(name, pokes, regs=None):
        h, m = new()
        quiet(m)
        m[SCRATCH + 7] = 0x80
        m[SCRATCH + 6] = 0x40
        m[SCRATCH + 5] = 0x40
        m[MODE] = 0x00                      # the ENEMY mode
        #  the cell follows the POKED position, not the default one -- the Y
        #  gate cases move the entity, and poking the old cell made "Y = $10"
        #  look like a refusal when it is an acceptance somewhere else.
        ey = pokes.get(SCRATCH + 6, 0x40)
        ex = pokes.get(SCRATCH + 5, 0x40)
        cell = ATTRS + (ey >> 3) * 32 + ((ex >> 3) & 0x1F)
        m[cell] = 0x28                      # ...standing in water
        #  the scratch page is not ZERO in a saved state: $FC09 already held
        #  $FF, so "corpsed" read TRUE on every arm including the ones that
        #  return before doing anything.  Clear it, and detect the corpse by
        #  REACHING $93C5 rather than by a byte that was already there.
        m[SCRATCH + 9] = 0x00
        for a, v in pokes.items():
            m[a] = v
        r = h.sim.registers
        arm(h, PROBE)
        r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
        r[18], r[19] = 0x58, 0x00
        for k, v in (regs or {}).items():
            r[k] = v
        reached = [False]
        n = 0
        while n < 8 * 10 ** 6:
            h.step(1, interrupts=False)
            if r[PC] == CORPSE:
                reached[0] = True
            if r[PC] in h.SENTINELS:
                break
            n += 1
        cases.append({'case': name, 'corpsed': reached[0],
                      'plus9': m[SCRATCH + 9], 'A': r[0]})

    one('active, in water', {})
    one('...INACTIVE (+7 bit 7 clear)', {SCRATCH + 7: 0x00})
    one('...a CORPSE (+7 bit 3)', {SCRATCH + 7: 0x88})
    one('...Y = $0F, one below the $937F CP $10 gate', {SCRATCH + 6: 0x0F})
    one('...Y = $10, the first Y the probe accepts', {SCRATCH + 6: 0x10})
    print('(d) GATES: %s' % '; '.join('%s -> %s' % (c['case'],
                                                    'CORPSED' if c['corpsed'] else '-')
                                      for c in cases))
    return cases


# ------------------------------------------------------ (e) the player's tail
def phase_player():
    rows = []
    cell = ATTRS + 8 * 32 + 8

    def one(name, attr, pokes):
        h, m = new()
        quiet(m)
        m[cell] = attr
        m[0xFD87] = 0xE1
        m[0xFD91] = 0x60                    # P2 out
        m[0xFD85] = 0x40
        m[0xFD86] = 0x40
        m[0xFDDA] = 0x80
        m[0xFD88] = 0x00
        m[0xFD89] = 0x05
        m[SLOTS] = 2
        m[FLOOD] = 0
        for a, v in pokes.items():
            m[a] = v
        arm(h, PASS_)
        run(h)
        rows.append({'case': name, 'attr': attr,
                     'f5a': m[0xFDDA], 'dir': m[0xFD88], 'phase': m[0xFD89]})

    one('PAPER 5 under the player', 0x28, {})
    one('BRIGHT INK 2 under the player', 0x42, {})
    one('...paper 5, but already CARRIED (+$5A bit 4)', 0x28, {0xFDDA: 0x90})
    one('...paper 5, but the FLOOD is up ($FECE)', 0x28, {FLOOD: 1})
    one('...paper 5, but JUMP is held ((IX+8) bit 1)', 0x28, {0xFD88: 0x02})
    one('nothing under the player', 0x07, {})
    print('(e) THE PLAYER TAIL: $936A SET 4 is the WATER-CARRY bit, not a death')
    for r in rows:
        print('      %-46s +$5A $%02X, +8 $%02X, +9 $%02X'
              % (r['case'], r['f5a'], r['dir'], r['phase']))
    return rows


# ----------------------------------------------------- (f) position -> cell
def _pos_slice(args):
    ylo, yhi = args
    h, m = new()
    quiet(m)
    m[SCRATCH + 7] = 0x80
    m[MODE] = 0xC9
    r = h.sim.registers
    base = arm(h, PROBE)
    out = []
    for ey in range(ylo, yhi):
        for ex in range(0, 256, 8):
            for a in range(ATTRS, 0x5B00):
                m[a] = 0x07
            m[SCRATCH + 6] = ey
            m[SCRATCH + 5] = ex
            reads = []
            orig = type(h.memobj).__getitem__

            def spy(self, a, _r=reads):
                if isinstance(a, int) and ATTRS <= a < 0x5B00:
                    _r.append(a)
                return orig(self, a)
            type(h.memobj).__getitem__ = spy
            try:
                r[SP] = base
                r[PC] = PROBE
                r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
                r[18], r[19] = 0x58, 0x00
                h.run_until(h.SENTINELS, limit=20000, stride=1, interrupts=False)
            finally:
                type(h.memobj).__getitem__ = orig
            if reads:
                out.append([ex, ey, min(reads) - ATTRS, len(set(reads))])
    return out


def phase_positions(jobs=15):
    bands = [(y, min(y + 8, 192)) for y in range(0, 192, 8)]
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(_pos_slice, bands):
            rows.extend(part)
    model_ok = all(off == ((ey >> 3) * 32 + (ex >> 3)) for (ex, ey, off, _) in rows)
    print('(f) POSITION -> CELL: %d sampled positions, the first cell is '
          '(Y>>3)*32 + (X>>3) on %s of them' % (len(rows),
                                                'ALL' if model_ok else 'NOT all'))
    return {'rows': rows[:400], 'n': len(rows), 'model_ok': model_ok,
            'distinct_cells': sorted(set(r[3] for r in rows))}


def phase_wrap():
    """*** $93B9 `DEC L` IS EIGHT BIT, AND IT WRAPS SOMEWHERE REACHABLE. ***

    The third probe is `ADD HL,$21` and then `DEC L` -- sixteen bits forward and
    eight bits back.  They agree unless cell + $21 has a LOW BYTE OF ZERO, and
    that happens at row*32 + col = 223, 479 or 735: COLUMN 31 of rows 6, 14 and
    22.  At those three positions the third cell is not cell + $20 at all; it is
    255 bytes further on.  Driven by read-watch at every column-31 row."""
    rows = []
    for row in range(24):
        h, m = new()
        quiet(m)
        m[SCRATCH + 7] = 0x80
        m[SCRATCH + 6] = row * 8
        m[SCRATCH + 5] = 31 * 8
        m[MODE] = 0xC9
        cell = ATTRS + row * 32 + 31
        reads = []
        orig = type(h.memobj).__getitem__

        def spy(self, a, _r=reads):
            if isinstance(a, int) and 0x5000 <= a < 0x6000:
                _r.append(a)
            return orig(self, a)
        type(h.memobj).__getitem__ = spy
        try:
            r = h.sim.registers
            arm(h, PROBE)
            r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF
            r[18], r[19] = 0x58, 0x00
            run(h)
        finally:
            type(h.memobj).__getitem__ = orig
        seen = sorted(set(reads))
        third = seen[-1] if len(seen) >= 3 else None
        rows.append({'row': row, 'cell': '%04X' % cell,
                     'cells': ['%04X' % a for a in seen],
                     'offsets': [a - cell for a in seen],
                     'wrapped': bool(third is not None and third - cell > 0x21)})
    w = [r['row'] for r in rows if r['wrapped']]
    print('(g) `DEC L` WRAP at column 31: rows %s of 24 read a third cell that '
          'is NOT cell + $20' % w)
    for r in rows:
        if r['wrapped']:
            print('      row %2d, cell $%s -> offsets %s'
                  % (r['row'], r['cell'], r['offsets']))
    return {'rows': rows, 'wrapped_rows': w}


def capture(jobs=15):
    out = {}
    out['mode'] = phase_mode()
    out['cells'] = phase_cells()
    out['gates'] = phase_gates()
    out['player'] = phase_player()
    out['attrs'] = phase_attrs(jobs)
    out['wrap'] = phase_wrap()
    out['positions'] = phase_positions(jobs)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
