"""M7.7-F0 -- THE ROUND-CLASS CENSUS, and the CHAINED-BUILD RECIPE that F1, F2,
G2, H3 and I11 all consume.

THE RECIPE IS THE DELIVERABLE.  Four later increments need a per-round number and
NOT ONE OF THEM CAN GET A TRUE ONE BY POKING $8609 into a fresh state:

  * $8609 := 19 IS NOT A ROUND-20 SAMPLE.  It warps to 81 and produces round 81's
    signature to the T-state.  The warp must be suppressed FIRST.
  * Round 1 needs $8609 := 0 -- the new-game value $96FB writes -- which no
    shipped state carries.
  * $AA57 and $745C are INHERITED on rounds 80 and 81, so a fresh poke hands you
    whatever the source state happened to hold.

So: 81 sequential CALL $97F8 in ONE world, the milestone warp suppressed with
$FDDA |= $80 and $FDE4 |= $80, SP PINNED per build with the index-0 sentinel
asserted (TRAPS #42), and -- the part that makes the census mean anything --
$745C := $AABB and $7E0E := $EE RESEEDED BEFORE EVERY BUILD.

WHY THE SENTINEL, AND WHY BEFORE EVERY BUILD:
"not written" and "written with the same value" are INDISTINGUISHABLE on a chained
sweep, because rounds 78 and 79 both give $03E8 and both leave $AA57 = 9.  A
sentinel no code path can write is the only thing that separates them -- and
reseeding it only once, or only around rounds 80/81, would prove the negative
exactly where it was already suspected and nowhere else.  The negative asserted
here is over ALL 81 ROWS: $745C survives as $AABB on EXACTLY rounds 80 and 81.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT POKING $8609 IS A ROUND SAMPLE.  See above.  Every row here comes from a
    real build in a world that reached it by building every round before it.
  * THAT THE WARP IS A FUNCTION OF TWO FLAGS.  It has THREE inputs -- the two
    died-flags at (IX+$5A) bit 7 AND the surviving player's IN-PLAY flag at
    (IX+7) bit 7, read through whichever IX the died-flag test left.  The sixteen
    rows poke all four apart (TRAPS #37), and six of them warp.
  * THAT THE TWO EXTRA LIVES RIDE ON THE WARP.  They are granted in ALL SIXTEEN
    rows, before and independent of it.
  * THAT $9811 CAN BE SAMPLED AT ALL.  An earlier pass saw eight consecutive EVEN
    draws (44,32,52,40,60,48,36,56) and nearly concluded that 41 and 61 are
    unreachable in simulation.  I then made the SAME MISTAKE here in this file:
    stepping `1 + (i % 17)` instructions between samples gave 31 of 32 values
    over 420 samples with the value 38 missing, because R advances with the
    INSTRUCTION COUNT and any periodic schedule is a comb through its residues.
    This oracle therefore SETS R to all 256 values and asserts the FUNCTION;
    the distribution question is answered separately by driving REAL frames.
  * THAT $FEC7 CAN CARRY A SENTINEL.  $9817 writes it UNCONDITIONALLY on every
    build, so a sentinel there survives zero rounds and tests nothing.  The
    quantity that deviates is $8609.

Usage:  python tools/roundclass.py capture
        python tools/roundclass.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

R_REG = 15                        # skoolkit.simutils.REGISTERS['R']

ADVANCE = 0x97F8
ROUND, LOOKAHEAD = 0x8609, 0xFEC7
THRESH, COUNT, ELEM = 0x745C, 0xAA57, 0x7E0E
BUILD_A, BUILD_B = 0x82D7, 0x83EC
P1, P2 = 0xFD80, 0xFD8A
DIED = 0x5A
LIVES1, LIVES2 = 0xFDDC, 0xFDE6
RECORDS = (0x7491, 0x7990)          # the enemy spawn records, which must not move
SENT_T, SENT_E = 0xAABB, 0xEE       # values no code path can write
FIXTURE = 'build/roundclass_fixture.json'
BRANCH_BYTE = 0x8DC4
SP_PIN = [0]

# The PC set whose per-round counts ARE the class signature.  Counted by stopping
# on them, not by hooking every instruction: the counts are small (1..19) so this
# is O(stops), not O(60 million).
SIG = [0x7FC0, 0x806C, 0x81E6, 0x840A, 0x8447, 0x98BC, 0x72CA, 0x7373,
       0x79A2, 0x7F97, 0x7FA9, 0x7336, 0x9826, 0x9811, 0x9806, 0x7E04,
       0xA36C, 0x957E, 0x99A8, 0x99C3, 0x99D4, 0xBF39, 0xBF5B, 0x9904,
       0x8C66, 0x7F1B, 0x7F62, 0x8216, 0x854D, 0x8207, 0x79AC, 0x8C5E,
       0x9887, 0x82D6, 0x83EB, 0x7C87, 0x8CA5, 0x98E4, 0x98F0, 0x7F80,
       0x7F83, 0x9855]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP_PIN[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    """Pin SP and push the sentinels.  TRAPS #42: Harness.call never restores SP,
       so a sweep of 81 builds would walk the stack into ROM and start quietly
       capturing 'nothing happened' rows."""
    r = h.sim.registers
    sp = SP_PIN[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def run(h, sp, limit=40 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=True)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


def run_counting(h, sp, limit=40 * 10 ** 6):
    """Run to the sentinel, counting visits to every PC in SIG on the way."""
    hits = {}
    targets = set(SIG) | set(h.SENTINELS)
    total = 0
    while total < limit:
        h.run_until(targets, limit=limit - total, stride=1, interrupts=True)
        p = h.regs[PC]
        if p in h.SENTINELS:
            break
        hits[p] = hits.get(p, 0) + 1
        h.step(1, interrupts=True)          # step off it, or run_until returns here
        total += 1
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))
    return hits


def seed_round(m):
    """The sentinels, before EVERY build."""
    m[THRESH], m[THRESH + 1] = SENT_T & 0xFF, SENT_T >> 8
    m[ELEM] = SENT_E


def suppress_warp(m):
    m[P1 + DIED] |= 0x80
    m[P2 + DIED] |= 0x80


# ------------------------------------------------------------ (a) the census
def census_rows(h, m, counting=True):
    """*** THE NEW-GAME SEED IS THREE BYTES, NOT ONE. ***  This wrote only
       ($8609) and inherited round1_48's ($82D7) = ($83EC) = 1, so every build
       counter in the census -- and therefore every palette byte and every tile
       index derived from one -- came out ONE BUILD AHEAD of a real new game.
       $96FA is `XOR A / LD ($8609),A / LD ($83EC),A / LD ($82D7),A`: all three.
       MEASURED (M7.8-0): with the one-byte seed, round 1 builds with $82D7 = 2
       and a $45/$55 palette; the shipped round1_48 state carries $82D7 = 1 and
       $47/$57, and the three-byte seed reproduces it -- $5840..$5AFF 0 of 704,
       $F840..$FAFF 0 of 768 and $E000..$F7FF 0 of 6144 differing.  The platform
       shadow is not a function of the round: the SAME round 1 built at the two
       phases differs in 1,661 of 6,144 bytes.  Two agents in the M7.8 pass took
       81-round sweeps off the one-byte seed and published tables that are each
       shifted by exactly one round.  TRAPS #93."""
    suppress_warp(m)
    m[ROUND] = 0x00                          # $96FB
    m[BUILD_B] = 0x00                        # $96FE
    m[BUILD_A] = 0x00                        # $9701
    before = bytes(m[RECORDS[0]:RECORDS[1]])
    rows = []
    for _ in range(81):
        seed_round(m)
        suppress_warp(m)                     # $97F8 may clear them; reassert
        sp = arm(h, ADVANCE)
        hits = run_counting(h, sp) if counting else (run(h, sp) or {})
        th = m[THRESH] | (m[THRESH + 1] << 8)
        rows.append({'round': m[ROUND], 'look': m[LOOKAHEAD],
                     'thresh': th, 'thresh_written': th != SENT_T,
                     'count': m[COUNT], 'elem': m[ELEM],
                     'elem_written': m[ELEM] != SENT_E,
                     'build_a': m[BUILD_A], 'build_b': m[BUILD_B],
                     'sig': {('%04X' % k): v for k, v in sorted(hits.items())}})
    after = bytes(m[RECORDS[0]:RECORDS[1]])
    return rows, (before == after)


# ------------------------------------------------------- (b) the warp table
def warp_rows(h, m):
    """SIXTEEN rows: the two died-flags and the two in-play flags POKED APART.
       Driven at rounds 19, 39 and 59 (the lookahead becomes 21/41/61) and at
       three rounds that are not milestones at all."""
    rows = []
    for r0 in (19, 39, 59, 20, 3, 79):
        for bits in range(16):
            m[ROUND] = r0
            m[P1 + DIED] = 0x80 if (bits & 1) else 0x00
            m[P2 + DIED] = 0x80 if (bits & 2) else 0x00
            m[P1 + 7] = 0x80 if (bits & 4) else 0x00
            m[P2 + 7] = 0x80 if (bits & 8) else 0x00
            m[LIVES1], m[LIVES2] = 3, 3
            seed_round(m)
            sp = arm(h, ADVANCE)
            run(h, sp)
            rows.append({'from': r0, 'bits': bits,
                         'p1_died': (bits & 1) != 0, 'p2_died': (bits & 2) != 0,
                         'p1_inplay': (bits & 4) != 0, 'p2_inplay': (bits & 8) != 0,
                         'round': m[ROUND], 'look': m[LOOKAHEAD],
                         'warped': m[ROUND] == 0x51,
                         'lives': [m[LIVES1], m[LIVES2]]})
    return rows


# ---------------------------------------------------- (d) the $9811 reseed
def reseed_rows(h, m):
    """$9811 LD A,R / AND $1F / ADD $1E.

       SAMPLING THIS IS A TRAP AND I FELL INTO IT HERE, having just written the
       warning about it at the top of this file.  An earlier pass saw eight
       consecutive EVEN draws and nearly concluded that 41 and 61 are unreachable
       in simulation.  My own first attempt stepped `1 + (i % 17)` instructions
       between samples and got 31 of the 32 values over 420 samples, with counts
       running from 1 to 32 and the value 38 (R & $1F == 8) MISSING ENTIRELY.
       That was the stepping pattern, not the machine: R advances deterministically
       with the instruction count, so any periodic schedule is a comb through its
       residues, and the reading pass's predicted "distinct == 32" was right while
       my measurement was wrong.

       So this does not sample.  It SETS R to all 256 values and asserts the
       FUNCTION, which no phase artefact can fake.  The separate question -- is
       the distribution degenerate in play? -- is answered by driving REAL frames,
       where the machine's own instruction stream sets R."""
    fn = []
    for r in range(256):
        h.sim.registers[R_REG] = r
        h.sim.registers[PC] = 0x9811
        h.step(3, interrupts=False)               # LD A,R / AND $1F / ADD $1E
        fn.append(h.sim.registers[0])             # A
    # AND THE NEGATIVE RESULT, kept because it is the point: driving whole frames
    # does NOT sample this either.  run_frames(1) is deterministic, so R at the
    # call site is phase-locked to the frame parity and 200 samples take exactly
    # TWO values.  An idle harness cannot answer "what is the distribution in
    # play?" at all; the honest claim is the FUNCTION plus this demonstration,
    # not a histogram with two bars in it.
    live = []
    for _ in range(200):
        h.run_frames(1, interrupts=True)
        h.sim.registers[PC] = 0x9811
        h.step(3, interrupts=False)
        live.append(h.sim.registers[0])
    return {'fn': fn, 'live': live, 'r_offset': 2}


def capture():
    h, m = new()
    warp = warp_rows(h, m)
    reseed = reseed_rows(h, m)
    h, m = new()                                   # a clean world for the chain
    rows, records_intact = census_rows(h, m)
    fx = {'note': __doc__.strip(), 'advance_at': ADVANCE, 'round_at': ROUND,
          'look_at': LOOKAHEAD, 'thresh_at': THRESH, 'count_at': COUNT,
          'elem_at': ELEM, 'build_a_at': BUILD_A, 'build_b_at': BUILD_B,
          'p1_at': P1, 'p2_at': P2, 'died_off': DIED,
          'lives_at': [LIVES1, LIVES2], 'sentinel_thresh': SENT_T,
          'sentinel_elem': SENT_E, 'records_at': list(RECORDS),
          'records_intact': records_intact, 'sig_pcs': ['%04X' % p for p in SIG],
          'census': rows, 'warp': warp, 'reseed': reseed}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d census rows, %d warp rows, %d R values + %d live frames'
          % (FIXTURE, len(rows), len(warp), len(reseed['fn']),
             len(reseed['live'])))
    print('  the $7491-$7990 records survived the sweep: %s' % records_intact)
    stale = [r['round'] for r in rows if not r['thresh_written']]
    print('  $745C kept its $AABB sentinel on rounds: %s' % stale)


def verify():
    fx = json.load(open(FIXTURE))
    rows = fx['census']
    print('ROUND  LOOK  $745C   $AA57  $7E0E  $82D7 $83EC  signature PCs hit')
    for r in rows:
        if r['round'] in (1, 2, 3, 20, 21, 55, 56, 57, 72, 73, 79, 80, 81):
            print('  %3d  %4d  %6s  %4d  %5s  %4d %5d   %d'
                  % (r['round'], r['look'],
                     ('$%04X' % r['thresh']) if r['thresh_written'] else 'STALE',
                     r['count'],
                     r['elem'] if r['elem_written'] else 'STALE',
                     r['build_a'], r['build_b'], len(r['sig'])))
    print()
    print('$745C STALE on rounds: %s'
          % [r['round'] for r in rows if not r['thresh_written']])
    print('$AA57 range: %d..%d' % (min(r['count'] for r in rows),
                                   max(r['count'] for r in rows)))
    ws = [r for r in fx['warp'] if r['warped']]
    print('\nWARP: %d of %d rows warp' % (len(ws), len(fx['warp'])))
    for r in fx['warp'][:16]:
        print('   from %2d  died %d%d  inplay %d%d -> round %2d  %s  lives %s'
              % (r['from'], r['p1_died'], r['p2_died'], r['p1_inplay'],
                 r['p2_inplay'], r['round'],
                 'WARP' if r['warped'] else '    ', r['lives']))
    fn, live = fx['reseed']['fn'], fx['reseed']['live']
    off = fx['reseed']['r_offset']
    exact = len([1 for r in range(256)
                 if fn[r] == (((r + off) & 0x1F) + 0x1E)])
    print('\n$9811 AS A FUNCTION of all 256 R values: %d distinct, range %d..%d,'
          ' exactly (((R + %d) & $1F) + $1E) on %d of 256'
          % (len(set(fn)), min(fn), max(fn), off, exact))
    print('   the +%d is LD A,R (ED 5F) reading R after its own TWO M1 cycles;'
          ' R bit 7 is irrelevant, as AND $1F requires' % off)
    print('$9811 over %d WHOLE FRAMES: only %d distinct (%s) -- run_frames is'
          ' deterministic, so R is phase-locked to the frame parity.  THIS IS A'
          ' HARNESS ARTEFACT, NOT A FACT ABOUT THE GAME; it is kept as the'
          ' demonstration that an idle harness cannot sample $9811 at all.'
          % (len(live), len(set(live)), sorted(set(live))))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
