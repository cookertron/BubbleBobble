# -*- coding: utf-8 -*-
"""M7.23 -- $9AEB, THE ENEMY SPECIAL-MOVE SPAWNER: the chain's last unread entry.

$5B00 and $5B0A are TWO of the five fields the B-series differential tagged
UNIMPLEMENTED, and they were static across all 1,600 sampled passes on all three
states.  This is why: the spawner needs an enemy whose TYPE, read from $B562, is
1 or 5-and-up, and on those rounds every entry is 2.

What it does, once a frame and then only every other one:

  $9AEB   `LD A,($8DBD) / LD HL,$A37C / CP (HL) / LD (HL),A / RET z`
          -- the same self-modified frame detector $A82D uses, except the
          "operand" here is an ordinary byte at $A37C.
  $9AF4   `LD A,n / XOR 1 / LD ($9AF5),A / RET z` -- an OPERAND that halves it
          again, so the spawner runs on every OTHER frame it is reached on.
  $9AFC   two slots, $5B00 and $5B0A, the second reached by FALL-THROUGH.
          An ACTIVE slot (bit 7 of +7) jumps to $9BB4, the per-frame update.
  $9B0E   otherwise try to spawn, P1 first and then P2 by FALL-THROUGH, and
          $9B15's `BIT 7,(IY+7) / RET nz` stops after the first that works.
  $9B1E   the spawn: a PRNG draw AND 7 (zero does nothing), the index checked
          against ($AA57) - 3, and the type from $B562 at stride two.
  $9B70   the eligibility: the enemy's wake delay must be 0, its +7 must have
          bit 7 SET and bits 3 and 1 CLEAR, its +9 must be 0, its +6 must be
          character-aligned, and -- UNLESS THE TYPE IS 7 -- it must be on the
          SAME CHARACTER ROW as the player.

$9BB4, the per-frame update and its five-way dispatch on (IY+8), is $9BB4..$9D9x
and is NOT this increment's.

Usage:  python tools/enemyfire.py            (capture)
        python tools/enemyfire.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/enemyfire_fixture.json'
BRANCH_BYTE = 0x8DC4
FIRE = 0x9AEB
UPDATE = 0x9BB4
SLOTS = (0x5B00, 0x5B0A)
FRAME_SEEN = 0xA37C
OP_ALT = 0x9AF5
CLOCK = 0x8DBD
TYPES = 0xB562            # stride 2, the round's enemy roster types
COUNT = 0xAA57
DELAYS = 0xA891
ENEMIES = 0xFD9B          # slot 0's +7
PRNG = 0xFE86
STATE = 'round1_48'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    if not hasattr(h, '_sp0'):
        h._sp0 = r[SP]
    r[SP] = h._sp0
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, watch_pcs=(), limit=8 * 10 ** 6):
    """Runs one call; returns the set of watched PCs it visited."""
    seen = set()
    r = h.sim.registers
    n = 0
    while n < limit:
        if r[PC] in watch_pcs:
            seen.add(r[PC])
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            return seen
        n += 1
    raise SystemExit('bad bracket -- PC $%04X' % r[PC])


def ready(m, etype=1, idx=0, seed=None):
    """A world $9AEB will spawn in."""
    m[FRAME_SEEN] = (m[CLOCK] - 1) & 0xFF     # the frame has CHANGED
    #  *** THE ALTERNATION RUNS WHEN THE OPERAND IS ZERO, not when it is one. ***
    #  $9AF4 loads the operand, XORs 1, stores the RESULT and `RET z` on it -- so
    #  a stored 0 means the NEXT call proceeds.  Phase (a) walked 0101010101 and
    #  reached the slots on 1, 3, 5, 7, 9, which is the same thing said forwards.
    m[OP_ALT] = 0
    for s in SLOTS:
        for i in range(10):
            m[s + i] = 0x00
    #  the roster: every type 2 except the one we want
    for k in range(8):
        m[TYPES + 2 * k] = 0x02
        m[TYPES + 2 * k + 1] = 0x00
    m[TYPES + 2 * idx] = etype
    m[COUNT] = 12
    for k in range(8):
        m[DELAYS + k] = 0x00
    #  the enemy at `idx`: in play, not a corpse, not marked, +9 = 0, aligned
    p = (ENEMIES + 10 * idx) & 0xFFFF
    m[p] = 0x80
    m[p + 1] = 0x00                            # +8, bit 1 must be clear
    m[p + 2] = 0x00                            # +9
    m[(p - 1) & 0xFFFF] = 0x60                 # +6, & 7 == 0
    m[(p - 2) & 0xFFFF] = 0x40                 # +5
    #  the players: P1 in play, alive, on the SAME row
    m[0xFD87] = 0xE1
    m[0xFDDA] = 0x80
    m[0xFD86] = 0x60
    m[0xFD91] = 0x60                           # P2 out
    if seed is not None:
        m[PRNG] = seed & 0xFF
        m[PRNG + 1] = (seed >> 8) & 0xFF


def enemy_at(idx):
    """The enemy's +7, its struct base, and the fields around it."""
    return (ENEMIES + 10 * idx) & 0xFFFF


def spawned(m):
    for i, s in enumerate(SLOTS):
        if m[s + 7] & 0x80:
            return i
    return None


# ------------------------------------------------------------ (a) the gates
def phase_frame():
    """The frame detector and the alternation, driven ten calls each way."""
    rows = []
    for advance, name in ((False, 'the frame counter is still'),
                          (True, 'the frame counter advances')):
        h, m = new()
        ready(m)
        seen = []
        for i in range(10):
            if advance:
                m[CLOCK] = (m[CLOCK] + 1) & 0xFF
            arm(h, FIRE)
            hit = run(h, (0x9AFC,))
            seen.append({'call': i, 'reached_slots': 0x9AFC in hit,
                         'a37c': m[FRAME_SEEN], 'alt': m[OP_ALT]})
        rows.append({'case': name, 'calls': seen})
    print('(a) THE FRAME DETECTOR at $A37C and the ALTERNATION at $9AF5')
    for r in rows:
        print('      %-30s reached the slots on %s'
              % (r['case'], [c['call'] for c in r['calls'] if c['reached_slots']]))
        print('        $9AF5 walked %s'
              % ''.join(str(c['alt']) for c in r['calls']))
    return rows


# ------------------------------------------------------------- (b) the draw
def _seed_slice(args):
    """Which PRNG seeds give which `AND 7`, so the sweep can pick one each."""
    lo, hi = args
    h, m = new()
    out = []
    for seed in range(lo, hi):
        #  *** ARM AT $FE85, NOT AT $9B28. ***  $9B28 is the CALL, so running
        #  from there executes the draw AND the whole rest of $9B1E, and the A
        #  that comes back is not the draw at all -- the first version of this
        #  phase found only two residues in 512 seeds because of it.
        m[PRNG] = seed & 0xFF
        m[PRNG + 1] = (seed >> 8) & 0xFF
        arm(h, 0xFE85)
        run(h)
        a = h.sim.registers[0]
        out.append([seed, a, a & 7])
    return out


def phase_draw(jobs=15):
    bands = [(v, min(v + 32, 512)) for v in range(0, 512, 32)]
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(_seed_slice, bands):
            rows.extend(part)
    by = {}
    for seed, a, v in rows:
        by.setdefault(v, seed)
    print('(b) THE DRAW: $9B28 is a PRNG site and `AND 7` of it picks the enemy.')
    print('    %d seeds sampled, %d of the eight residues reachable: %s'
          % (len(rows), len(by),
             ' '.join('%d:$%04X' % (k, by[k]) for k in sorted(by))))
    return {'sample': rows[:64], 'seed_for': {str(k): v for k, v in by.items()}}


# ------------------------------------------------------------ (c) the types
def phase_types(seed_for):
    """$9B40 `CP 1 / JR z / CP 5 / RET c` -- the type must be 1, or 5 and up."""
    rows = []
    s = seed_for['1']                      # a draw of 1 -> index 0
    for t in range(0, 16):
        h, m = new()
        ready(m, etype=t, idx=0, seed=s)
        arm(h, FIRE)
        run(h)
        rows.append({'type': t, 'slot': spawned(m)})
    print('(c) TYPES: %s'
          % ' '.join('%d:%s' % (r['type'], 'Y' if r['slot'] is not None else '-')
                     for r in rows))
    return rows


# ------------------------------------------------- (d) the eligibility gates
def phase_eligible(seed_for):
    s = seed_for['1']
    rows = []

    def one(name, pokes):
        h, m = new()
        ready(m, etype=1, idx=0, seed=s)
        for a, v in pokes.items():
            m[a] = v
        arm(h, FIRE)
        run(h)
        rows.append({'case': name, 'slot': spawned(m),
                     'enemy8': m[ENEMIES + 1]})

    p = ENEMIES
    one('eligible', {})
    one('...P1 not in play', {0xFD87: 0x61})
    one('...P1 dying (+$5A bit 2)', {0xFDDA: 0x84})
    one('...the wake delay is not zero', {DELAYS: 1})
    one('...the enemy is not in play (+7 bit 7)', {p: 0x00})
    one('...the enemy is a CORPSE (+7 bit 3)', {p: 0x88})
    one('...the enemy is already marked (+7 bit 1)', {p: 0x82})
    one('...the enemy +9 is not zero', {p + 2: 1})
    one('...the enemy +6 is not row-aligned', {(p - 1) & 0xFFFF: 0x61})
    one('...the player is on a DIFFERENT row', {0xFD86: 0x70})
    one('...($AA57) is 3, which at index 0 refuses NOTHING', {COUNT: 3})
    print('(d) ELIGIBILITY')
    for r in rows:
        print('      %-44s -> %s' % (r['case'],
                                     'slot %d' % r['slot'] if r['slot'] is not None
                                     else '-'))
    return rows


def phase_count(seed_for):
    """$9B31 `LD A,($AA57) / SUB 3 / CP C / RET c` -- and it cannot refuse a LOW
       index at all.  With index 0 the comparison is (count-3) against 0, and
       `SUB 3` WRAPS, so a count of 2 gives $FF and still passes.  The gate only
       bites high in the roster, so the sweep is driven at index 6 -- the largest
       a draw of 7 can produce."""
    s = seed_for['7']                      # residue 7 -> index 6
    rows = []
    for count in (6, 7, 8, 9, 10, 12, 3, 2, 0):
        h, m = new()
        ready(m, etype=1, idx=6, seed=s)
        m[COUNT] = count
        arm(h, FIRE)
        run(h)
        rows.append({'count': count, 'index': 6, 'slot': spawned(m)})
    #  ...and the same count at index 0, to show the gate is about the INDEX
    low = []
    for count in (2, 3):
        h, m = new()
        ready(m, etype=1, idx=0, seed=seed_for['1'])
        m[COUNT] = count
        arm(h, FIRE)
        run(h)
        low.append({'count': count, 'index': 0, 'slot': spawned(m)})
    print('(d2) ($AA57) AT INDEX 6: %s'
          % ' '.join('%d:%s' % (r['count'], 'Y' if r['slot'] is not None else '-')
                     for r in rows))
    print('     ...and at INDEX 0 the same counts pass: %s'
          % ' '.join('%d:%s' % (r['count'], 'Y' if r['slot'] is not None else '-')
                     for r in low))
    return {'index6': rows, 'index0': low}


def phase_iy4(seed_for):
    """$9B87 `LD (IY+4),L` runs BEFORE the +7 checks and AFTER the wake delay,
       so a late rejection still leaves the pointer behind and an early one does
       not.  Both arms, and the slot poisoned first so the write is visible."""
    s = seed_for['1']
    rows = []
    for name, pokes in (('accepted', {}),
                        ('rejected LATE, at the corpse bit', {ENEMIES: 0x88}),
                        ('rejected EARLY, at the wake delay', {DELAYS: 1})):
        h, m = new()
        ready(m, etype=1, idx=0, seed=s)
        for a, v in pokes.items():
            m[a] = v
        m[SLOTS[0] + 4] = 0x5A             # poison
        arm(h, FIRE)
        run(h)
        rows.append({'case': name, 'iy4': m[SLOTS[0] + 4], 'slot': spawned(m)})
    print('(h) (IY+4), THE POINTER LEFT BEHIND: %s'
          % '; '.join('%s -> $%02X' % (r['case'], r['iy4']) for r in rows))
    return rows


def phase_type7(seed_for):
    """$9BA1 `CP 7 / JR z,$9BB1` -- type 7 SKIPS the row match."""
    s = seed_for['1']
    rows = []
    for t in (1, 7, 8):
        for same, name in ((True, 'same row'), (False, 'different row')):
            h, m = new()
            ready(m, etype=t, idx=0, seed=s)
            if not same:
                m[0xFD86] = 0x70
            arm(h, FIRE)
            run(h)
            rows.append({'type': t, 'same_row': same, 'slot': spawned(m)})
    print('(e) THE ROW MATCH, and type 7 is exempt: %s'
          % ' '.join('t%d/%s:%s' % (r['type'], 'same' if r['same_row'] else 'diff',
                                    'Y' if r['slot'] is not None else '-')
                     for r in rows))
    return rows


# --------------------------------------------------------- (f) the fields
def phase_fields(seed_for):
    s = seed_for['1']
    h, m = new()
    ready(m, etype=6, idx=0, seed=s)
    m[(ENEMIES - 2) & 0xFFFF] = 0x4D          # +5, so the AND $F8 shows
    m[(ENEMIES - 1) & 0xFFFF] = 0x60          # +6
    m[ENEMIES + 1] = 0x00                     # +8
    arm(h, FIRE)
    run(h)
    i = spawned(m)
    rec = [m[SLOTS[i] + k] for k in range(10)] if i is not None else None
    #  *** THE `SET 1` AT $9B52 LANDS ON THE ENEMY'S +7, NOT ITS +8. ***  $9B70
    #  returns with HL at the +6 (it walked back there for the row match), so
    #  $9B51's INC HL reaches +7 -- the SAME byte $9B91's `BIT 1,A` rejects on.
    #  The mark is therefore what stops one enemy being drafted twice.  The first
    #  version of this phase read $FD9C and printed $00, which is true and means
    #  nothing.
    print('(f) THE SLOT: %s -> %s ; the enemy +7 is now $%02X (SET 1 at $9B52)'
          % (i, ' '.join('%02X' % v for v in rec) if rec else 'none', m[ENEMIES]))
    return {'slot': i, 'record': rec, 'enemy7': m[ENEMIES], 'enemy8': m[ENEMIES + 1],
            'enemy5': m[(ENEMIES - 2) & 0xFFFF], 'enemy6': m[(ENEMIES - 1) & 0xFFFF]}


# --------------------------------------------------- (g) the second slot
def _pair_slice(args):
    """Two CONSECUTIVE draws from one seed -- $9AFC gives each slot its own."""
    lo, hi = args
    h, m = new()
    out = []
    for seed in range(lo, hi):
        m[PRNG] = seed & 0xFF
        m[PRNG + 1] = (seed >> 8) & 0xFF
        r = []
        for _ in range(2):
            arm(h, 0xFE85)
            run(h)
            r.append(h.sim.registers[0] & 7)
        out.append([seed, r[0], r[1]])
    return out


def phase_second(seed_for, jobs=15):
    """$5B0A IS REACHED BY FALL-THROUGH, and the first version of this phase
       never once filled it.  Slot 0 is tried first; if it is taken, $9B15's
       `RET nz` stops THAT slot's attempt, and the enemy it took is now MARKED,
       so slot 1's draw finds nothing.  To see $5B0A filled at all the FIRST
       draw must come up 0 -- which spawns nothing -- and the SECOND must come
       up 1.  So the seed is swept for exactly that pair."""
    #  *** (0,1) DOES NOT OCCUR IN 4096 SEEDS, and a sweep that says nothing
    #  when it finds nothing is a sweep that proved nothing. ***  So: take any
    #  pair whose FIRST draw is 0 -- slot 0 spawns nothing -- and put the
    #  eligible enemy wherever the SECOND draw points.  The census of what was
    #  and was not reachable is printed either way.
    bands = [(v, min(v + 256, 4096)) for v in range(0, 4096, 256)]
    first = {}
    n = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(_pair_slice, bands):
            for seed, a, b in part:
                n += 1
                if a == 0 and b != 0:
                    first.setdefault(b, seed)
    print('(g0) %d seeds swept for a first draw of 0; second draws reachable: %s'
          % (n, ' '.join('%d:$%04X' % (k, first[k]) for k in sorted(first))
             or 'NONE'))
    rows = []
    if first:
        b = sorted(first)[0]
        pair = first[b]
        h, m = new()
        ready(m, etype=1, idx=b - 1, seed=pair)
        arm(h, FIRE)
        hit = run(h, (UPDATE,))
        rows.append({'case': 'draws (0,%d): slot 0 passes, $5B0A is FILLED' % b,
                     'seed': pair, 'index': b - 1,
                     'slot0': m[SLOTS[0] + 7], 'slot1': m[SLOTS[1] + 7],
                     'record1': [m[SLOTS[1] + k] for k in range(10)],
                     'update': UPDATE in hit})
    #  ...and the plain case: slot 0 takes it, and the MARK keeps slot 1 empty
    s = seed_for['1']
    h, m = new()
    ready(m, etype=1, idx=0, seed=s)
    arm(h, FIRE)
    hit = run(h, (UPDATE,))
    rows.append({'case': 'draw 1: slot 0 takes it and the mark empties slot 1',
                 'seed': s, 'slot0': m[SLOTS[0] + 7], 'slot1': m[SLOTS[1] + 7],
                 'record1': [m[SLOTS[1] + k] for k in range(10)],
                 'update': UPDATE in hit})
    #  ...and an ACTIVE slot 0 goes to $9BB4 instead of spawning
    h, m = new()
    ready(m, etype=1, idx=0, seed=s)
    m[SLOTS[0] + 7] = 0xC0
    arm(h, FIRE)
    hit = run(h, (UPDATE,))
    rows.append({'case': 'slot 0 ACTIVE: $9B0B jumps to $9BB4',
                 'seed': s, 'slot0': m[SLOTS[0] + 7], 'slot1': m[SLOTS[1] + 7],
                 'record1': [m[SLOTS[1] + k] for k in range(10)],
                 'update': UPDATE in hit})
    print('(g) THE SECOND SLOT, $5B0A, reached by FALL-THROUGH')
    for r in rows:
        print('      %-52s seed $%04X -> +7 $%02X/$%02X, $9BB4 %s'
              % (r['case'], r['seed'], r['slot0'], r['slot1'],
                 'entered' if r['update'] else 'not'))
    assert any(r['slot1'] & 0x80 and not r['update'] for r in rows),         '$5B0A was never filled -- the phase proves nothing about the fall-through'
    return rows


def capture(jobs=15):
    out = {}
    out['frame'] = phase_frame()
    d = phase_draw(jobs)
    out['draw'] = d
    sf = d['seed_for']
    out['types'] = phase_types(sf)
    out['eligible'] = phase_eligible(sf)
    out['type7'] = phase_type7(sf)
    out['count'] = phase_count(sf)
    out['iy4'] = phase_iy4(sf)
    out['fields'] = phase_fields(sf)
    out['second'] = phase_second(sf, jobs)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
