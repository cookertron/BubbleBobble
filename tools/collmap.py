"""M7.7-H3 -- THE COLLISION TRANSFORM: the palette $82D6 and $79AC -> $7C43.

THIS IS WHERE M7.1 BINDS.  A wrong answer is baked simultaneously into the
geometry, the asset extraction, the collision model and every fixture built on
them -- and each wrong version looks individually plausible.

    $82D6  LD A,5 / INC A / CP 15 / JR nz / XOR A / LD ($82D7),A
                                        $82D7 is a COUNT OF BUILDS, wrapping 0..14
    $82E4  LD DE,$858C / ADD HL,DE / LD A,(HL)      the fifteen palette bytes
    $82E9  LD HL,$860C / LD (HL),0
    $82EE  RLA / RL (HL) / RRA           bit 7 of the palette byte is STRIPPED
                                         into $860C.  The carry entering RLA is
                                         ADD HL,DE's, and a 15-entry table can
                                         never carry out of sixteen bits, so it
                                         is always 0 and A comes back p & $7F.
    $82F2  OR $40 / LD ($830A),A         the SOLID attribute
    $82F7  AND $47 / LD ($8309),A        the OPEN attribute
    $82FC  ...LDIR the background fill

    $79AC = JP $7C43
    $7C43  LD HL,$F800 / LD BC,3         SIXTEEN-BIT: it sets B to ZERO ITSELF,
                                         so the inner DJNZ runs 256 times and the
                                         outer DEC C three times = 768 cells.
                                         A TRAPS #45 site that is NOT caller-
                                         dependent, which is the interesting half.
    $7C49  LD A,(HL) / AND $38
    $7C4C  LD (HL),A                     WRITER ONE, on every cell
    $7C4D  JR z,$7C51
    $7C4F  LD (HL),$20                   WRITER TWO, only when $38 bits were set
    So the rule is (v & $38) ? $20 : $00.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT "BIT 5 MEANS SOLID" CAN BE GATED WITH A BITMASK.  It is true of the RAW
    BUILD attributes on eleven rounds and FALSE on seventy, so a bit-5 gate
    passes whether $79AC ran or not on whichever class of round it happens to
    use.  Worse, $7C46 is a TRAPS #45 site: a port that converts 3 bytes instead
    of 768 leaves 765 raw attributes in place, and on those eleven rounds THAT
    failure is invisible to a bit-5 gate too.  So the FULL 768-BYTE OUTPUT is
    asserted, never a mask, and both a bit-5-clear palette and a bit-5-set one
    are driven.
  * THAT THE LOAD-BEARING FACT IS "BIT 5 IS SET FOR INDICES 4 AND 6".  It is not.
    THE INEQUALITY IS: OPEN & $38 == 0 and SOLID & $38 != 0, for every one of the
    fifteen indices.  Bit 5 in SOLID happens to be true for exactly indices 4
    ($66) and 6 ($65) and is an accident of two palette bytes.
  * THAT THREE WRITERS IS THE CENSUS.  A seed of $47 has $47 & $38 == 0, so every
    cell takes the JR z path and $7C4F NEVER FIRES -- which is how an earlier
    pass measured three writers and missed one entirely (TRAPS #44 in its purest
    form: the seed chose the branch).  Seeds are driven on BOTH sides of the test.
  * THAT $81C3 IS UNNECESSARY.  It is the CEILING, and poking it to $C9 makes the
    two gaps at columns 9-12 and 19-22 vanish.

Usage:  python tools/collmap.py capture
        python tools/collmap.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

PALETTE = 0x82D6
PAL_IDX, PAL_TAB = 0x82D7, 0x858C
OPEN_AT, SOLID_AT, HIBIT_AT = 0x8309, 0x830A, 0x860C
XFORM, XFORM_END = 0x7C43, 0x7C57
FULL = 0x79AC
CEIL = 0x81C3
MAP, MAP_N = 0xF800, 0x300
POISON = 0x5A
SEEDS = (0x47, 0x57, 0x46, 0x66, 0x45, 0x65, 0x00, 0xFF)
FIXTURE = 'build/collmap_fixture.json'


def run_to(h, sp, stop):
    h.run_until(tuple(h.SENTINELS) + (stop,), limit=10 ** 7, stride=1,
                interrupts=False)
    r = h.regs
    if r[PC] == stop:
        return 'stop'
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))
    return 'ret'


# ------------------------------------------------------------ (a) the palette
def palette_rows(h, m):
    rows = []
    for idx in range(15):
        m[PAL_IDX] = idx
        m[OPEN_AT] = m[SOLID_AT] = m[HIBIT_AT] = POISON
        # POISON THE WHOLE NEIGHBOURHOOD, not just the fill: the two CEILING rows
        # below it and the bytes past the map.  Checking only $F840..$FAFF
        # cannot see a fill that starts a row early or runs a row long, and two
        # mutations doing exactly that survived a battery.
        for i in range(0x340):
            m[MAP + i] = POISON
        h.memobj.watch(MAP, MAP + 0x340)
        sp = RC.arm(h, PALETTE)
        RC.run(h, sp)
        h.memobj.unwatch()
        wa = [a for (_p, a, _v) in h.memobj.log]
        rows.append({'index': idx, 'palette': m[PAL_TAB + idx],
                     'open': m[OPEN_AT], 'solid': m[SOLID_AT],
                     'hibit': m[HIBIT_AT], 'next_index': m[PAL_IDX],
                     'fill_lo': min(wa) if wa else None,
                     'fill_hi': max(wa) if wa else None,
                     'fill_writes': len(wa),
                     'before_fill': [m[MAP + i] for i in range(0x40)],
                     'past_map': [m[MAP + 0x300 + i] for i in range(0x40)]})
    return rows


# ---------------------------------------------------------- (b) the transform
def transform_rows(h, m):
    """$7C43 ALONE (bracketed at $7C57, where H4's passes begin), over seeds on
       BOTH SIDES of the $38 test -- because a seed with no $38 bits sends every
       cell down the JR z path and $7C4F never fires at all."""
    rows = []
    for seed in SEEDS:
        for i in range(MAP_N):
            m[MAP + i] = seed
        h.memobj.watch(MAP, MAP + MAP_N)
        sp = RC.arm(h, XFORM)
        how = run_to(h, sp, XFORM_END)
        h.memobj.unwatch()
        w = h.memobj.log
        pcs = {}
        for (p, _a, _v) in w:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        rows.append({'seed': seed, 'ended': how,
                     'out': [m[MAP + i] for i in range(MAP_N)],
                     'writers': pcs, 'writes': len(w)})
    return rows


def census_rows(h, m):
    """THE FULL $79AC, for the WRITER CENSUS.  H3 owns $7C4C/$7C4F; $7D73 and
       $7E3E are H4's and are asserted here only as writers that PRESERVE bits
       0-5, so that H3's claim about bit 5 survives the later passes."""
    rows = []
    for seed in SEEDS:
        for i in range(MAP_N):
            m[MAP + i] = seed
        h.memobj.watch(MAP, MAP + MAP_N)
        sp = RC.arm(h, FULL)
        RC.run(h, sp)
        h.memobj.unwatch()
        w = h.memobj.log
        pcs = {}
        for (p, _a, _v) in w:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        # does anything after the transform disturb bit 5?
        after4C = {}
        for (p, a, v) in w:
            if p not in (0x7C4C, 0x7C4F):
                after4C.setdefault('%04X' % p, []).append((a, v))
        rows.append({'seed': seed, 'writers': pcs,
                     'out': [m[MAP + i] for i in range(MAP_N)],
                     'later_writers': sorted(after4C.keys())})
    return rows


# --------------------------------------------------------- (c) end to end
def endtoend_rows(h, m):
    """A whole $97F8 per round, then the post-$79AC region byte for byte.
       Rounds reached with F0's chained recipe -- round 1 needs $8609 := 0,
       which no shipped state carries."""
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    want = {0x01, 0x02, 0x05, 0x14, 0x38, 0x48, 0x50, 0x51}
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        rnd = m[RC.ROUND]
        if rnd not in want:
            continue
        rows.append({'round': rnd, 'map': [m[MAP + i] for i in range(MAP_N)],
                     'open': m[OPEN_AT], 'solid': m[SOLID_AT],
                     'pal_idx': m[PAL_IDX]})
    return rows


def live_rows():
    """The same region out of SHIPPED states, so the end-to-end row is compared
       against worlds the game really played into."""
    rows = []
    for st, rnd in (('round1_48', 0x01), ('hurryup', 0x04), ('r6_48', 0x06),
                    ('r10_48', 0x0A), ('r20_48', 0x14), ('r30_48', 0x1E),
                    ('r40_48', 0x28), ('r50_48', 0x32), ('r60_48', 0x3C),
                    ('boss', 0x50), ('lastdia81', 0x51)):
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if m[0x8DC4] != 0xC9:
            continue
        rows.append({'state': st, 'round': m[0x8609],
                     'map': [m[MAP + i] for i in range(MAP_N)]})
    return rows


# ------------------------------------------------------------ (d) the ceiling
def ceiling_rows(h, m):
    """$81C3/$81E1 build the CEILING.  Rows 0 and 1 come out SOLID except two
       four-wide gaps, and poking $81C3 to $C9 makes them VANISH -- which is why
       the instruction to prove the port need not implement it was deleted."""
    rows = []
    for patched in (False, True):
        hh, mm = RC.new()
        RC.suppress_warp(mm)
        mm[RC.ROUND] = 0x00
        for _ in range(3):
            RC.seed_round(mm)
            RC.suppress_warp(mm)
            sp = RC.arm(hh, RC.ADVANCE)
            RC.run(hh, sp)
        if patched:
            mm[CEIL] = 0xC9
        # POISON ROWS 0 AND 1 FIRST.  $82D6's LDIR fill starts at $F840 -- ROW
        # TWO -- so rows 0 and 1 are written by $81C3/$81E1 ALONE.  Left as the
        # previous build made them, "drew the ceiling" and "did nothing" are the
        # same picture, and patching $81C3 changes nothing visible.
        for i in range(64):
            mm[MAP + i] = POISON
        sp = RC.arm(hh, 0x7F62)
        RC.run(hh, sp)
        sp = RC.arm(hh, FULL)
        RC.run(hh, sp)
        rows.append({'patched': patched, 'round': mm[RC.ROUND],
                     'row0': [mm[MAP + i] for i in range(32)],
                     'row1': [mm[MAP + 32 + i] for i in range(32)]})
    return rows


# ---------------------------------------------------------- (e) the play row
def play_rows():
    """WRITTEN SO IT CANNOT PASS ON ROUND 1 ALONE.  round1_48 and `water` are
       BOTH round $01 and differ by 632 writes to zero, so "rounds >= 2" is
       itself a false model: the writers fire whenever a BUBBLE HOLDS A CELL,
       which is not a function of the round."""
    rows = []
    for st in ('round1_48', 'water', 'r6_48', 'r10_48', 'hurryup', 'r20_48',
               'r50_48', 'boss'):
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if m[0x8DC4] != 0xC9:
            continue
        before = [m[MAP + i] for i in range(MAP_N)]
        h.memobj.watch(MAP, MAP + MAP_N)
        h.run_frames(240, interrupts=True)
        h.memobj.unwatch()
        w = h.memobj.log
        pcs = {}
        for (p, _a, _v) in w:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        # did ANY of them disturb bits 5, 6 or 7?
        broke = 0
        for (_p, a, v) in w:
            if (v & 0xE0) != (before[a - MAP] & 0xE0):
                broke += 1
        rows.append({'state': st, 'round': m[0x8609], 'writes': len(w),
                     'writers': pcs, 'top_bits_changed': broke})
    return rows


def capture():
    h, m = RC.new()
    fx = {'note': __doc__.strip(), 'palette_at': PALETTE, 'pal_idx_at': PAL_IDX,
          'pal_tab_at': PAL_TAB, 'open_at': OPEN_AT, 'solid_at': SOLID_AT,
          'hibit_at': HIBIT_AT, 'xform_at': XFORM, 'xform_end': XFORM_END,
          'full_at': FULL, 'ceil_at': CEIL, 'map_at': MAP, 'map_n': MAP_N,
          'poison': POISON, 'seeds': list(SEEDS),
          'palette': palette_rows(h, m),
          'transform': transform_rows(h, m),
          'census': census_rows(h, m),
          'ceiling': ceiling_rows(h, m),
          'play': play_rows()}
    h, m = RC.new()
    fx['endtoend'] = endtoend_rows(h, m)
    fx['live'] = live_rows()
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s' % FIXTURE)
    print('  the palette, fifteen indices:')
    for r in fx['palette']:
        print('     %2d: $%02X -> open $%02X solid $%02X hibit %d   (open&$38=%d solid&$38=%d)'
              % (r['index'], r['palette'], r['open'], r['solid'], r['hibit'],
                 r['open'] & 0x38, r['solid'] & 0x38))
    print('  the transform, by seed:')
    for r in fx['transform']:
        print('     seed $%02X -> %d writes, writers %s'
              % (r['seed'], r['writes'], r['writers']))


def verify():
    fx = json.load(open(FIXTURE))
    print('THE WRITER CENSUS over the whole $79AC -- three writers or four?')
    for r in fx['census']:
        print('   seed $%02X: %s' % (r['seed'], r['writers']))
    print()
    print('END TO END, a real build against the shipped states:')
    live = {r['round']: r for r in fx['live']}
    for r in fx['endtoend']:
        L = live.get(r['round'])
        if not L:
            print('   round $%02X: (no shipped state at this round)' % r['round'])
            continue
        same = len([1 for i in range(fx['map_n']) if r['map'][i] == L['map'][i]])
        print('   round $%02X vs %-11s %d of %d bytes agree'
              % (r['round'], L['state'], same, fx['map_n']))
    print()
    print('THE PLAY ROW -- who writes the map once the game is running:')
    for r in fx['play']:
        print('   %-11s round $%02X: %4d writes, writers %s, top bits disturbed %d'
              % (r['state'], r['round'], r['writes'], r['writers'],
                 r['top_bits_changed']))
    print()
    for r in fx['ceiling']:
        gaps = [i for i in range(32) if not (r['row0'][i] & 0x20)]
        print('   $81C3 %-7s -> row 0 open columns %s'
              % ('patched' if r['patched'] else 'intact', gaps))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
