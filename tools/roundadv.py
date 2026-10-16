"""M7.7-H1 -- THE TRANSITION SPINE: what a whole $97F8 does, and to what.

F0 took the round-class census, the warp truth table and the $8609 sweep, so this
increment keeps the parts F0 does not: THE PIXEL CENSUS, the per-build PC
counters, and four NEGATIVES.

*** THIS INCREMENT HAS PIXELS, AND THEY ARE AFTER $8216. ***  The reading pass
originally said "NO PIXELS AT ALL" and that was retracted: the transition paints
the display in FOUR places the spine never named --
    $7F58 CALL z,$7FC0   round 1 ONLY: the HUD text and both score panels
    $7F5B CALL $806C     EVERY round: the lives icons at $50E0.., doubled for P2
    $986F CALL $957E     EVERY round: the collected-specials row, ZERO in a
                         fresh build because no EXTEND bit is set
    $9904                a FOURTH nobody named at all: the banner restore
and $806C's first display write follows $8216's by about 8,200 instructions.
That matters because H2 proved $8216 DISCARDS the scroll: if H1 did not count
these, H2's patch pair would be asserting over a display three routines paint
after the discard.  H1 COUNTS them; H9 models them.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT "TENS OF THOUSANDS OF PIXELS FOLLOW THE DISCARD" IS A ROUND-INDEPENDENT
    FACT.  It is 50,593 on round 1 and 248 on round 81, which has no banner.
  * THAT THE $9AC1 TABLE IS WRITTEN.  It is a table of NINETEEN POINTERS and the
    walk writes only their TARGETS.  A port that also zeroes $9AC1..$9AE6 is
    green on round 1 and writes nineteen bytes into ROM on round 2 -- so the
    gate asserts the 38 bytes AT $9AC1 are UNTOUCHED.
  * THAT THE NINETEEN TARGETS CAN BE OBSERVED AS THEY LIE.  MOST ARE ALREADY
    ZERO when a round ends: in one measured transition only $FEC4, $FEC5, $8E3B
    and $9049 actually CHANGED.  They are seeded to $FF first (TRAPS #44).
  * THAT THE SPARKLE TABLE IS CLEARED ONCE.  It is cleared TWICE, 24 bytes by
    $989C and 28 by $BF53, and $5CFC..$5CFF -- which holds live runtime-built
    data a 16-slot table would pick up as a particle -- must come back UNTOUCHED.
  * THAT $D380 IS A FUNCTION OF THE ROUND.  It is not: on the group-3 rounds
    $7E0E is redrawn from LD A,R and two builds of the same round differ in up to
    69 of 384 bytes.  Its md5 is recorded as an OBSERVATION, never frozen.

AND ONE CROSS-INCREMENT FACT WORTH ITS OWN LINE: $9891 RESTORES THE CORPSE-FRUIT
GENERATOR ($8B9F/$8BA0/$8BA2), WHICH UNDOES $88E0's DIAMOND PIN EVERY ROUND.  I6
measured the pin and I9 measured the generator; neither could see that the pin
lasts exactly one round.

Usage:  python tools/roundadv.py capture
        python tools/roundadv.py verify
"""
import sys, json, hashlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

REPAINT = 0x8216
RESET_TAB = 0x9AC1
SPARKLE = 0x5CE0
GEN, GEN_OP, GEN_MASK = 0x8B9F, 0x8BA0, 0x8BA2
FREEZE_A, FREEZE_B = 0xFEC4, 0xB54B
ELEM_BANK = 0xD380
PAINTERS = (0x7FC0, 0x806C, 0x957E, 0x9904)
COUNTERS = (0xA36C, 0x957E, 0x99A8, 0x99C3, 0x99D4, 0xBF39, 0xBF5B)
ROUNDS = (1, 2, 5, 56, 72, 80, 81)
FIXTURE = 'build/roundadv_fixture.json'


def split_build(h, m):
    """One $97F8, with the display writes split at the FIRST visit to $8216 --
       everything before it is discarded, everything after it survives."""
    h.memobj.watch(0x4000, 0x5B00)
    sp = RC.arm(h, RC.ADVANCE)
    h.run_until((REPAINT,), limit=40 * 10 ** 6, stride=1, interrupts=True)
    hit = h.regs[PC] == REPAINT
    pre = list(h.memobj.log)
    h.memobj.log = []
    RC.run(h, sp)
    post = list(h.memobj.log)
    h.memobj.unwatch()
    return hit, pre, post


def census(rows):
    out = {}
    for (p, a, _v) in rows:
        k = '%04X' % p
        out[k] = out.get(k, 0) + 1
    return out


def painter_bands(h, m):
    """EACH PAINTER'S OWN WRITE BAND, bracketed by its stack frame.

       MY FIRST VERSION keyed a write census by the WRITING PC and looked the
       painters up by their ENTRY addresses -- which found nothing, because the
       writes come from inside the routines ($7FCA, $806C's inner loop) and never
       from the entry.  A painter has to be bracketed, not grepped for."""
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        rnd_next = None
        bands = {}
        sp = RC.arm(h, RC.ADVANCE)
        # walk the build, stopping at each painter entry and measuring its frame
        stops = set(PAINTERS) | set(h.SENTINELS)
        guard = 0
        while guard < 200:
            guard += 1
            h.run_until(stops, limit=40 * 10 ** 6, stride=1, interrupts=True)
            p_ = h.regs[PC]
            if p_ in h.SENTINELS:
                break
            entry_sp = h.regs[12]
            h.memobj.watch(0x4000, 0x5B00)
            h.step(1, interrupts=True)
            h.run_until((), limit=10 ** 7, stride=1, interrupts=True,
                        predicate=lambda hh: hh.regs[12] > entry_sp)
            h.memobj.unwatch()
            k = '%04X' % p_
            b = bands.setdefault(k, {'calls': 0, 'display': 0, 'attrs': 0})
            b['calls'] += 1
            for (_pc, a, _v) in h.memobj.log:
                if a < 0x5800:
                    b['display'] += 1
                else:
                    b['attrs'] += 1
        rnd_next = m[RC.ROUND]
        if rnd_next in ROUNDS:
            rows.append({'round': rnd_next, 'bands': bands})
    return rows


def build_rows(h, m):
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        # seed everything the negatives need to be observable
        for i in range(0x20):
            m[SPARKLE + i] = 0xA5
        m[GEN], m[GEN_OP], m[GEN_MASK] = 9, 0x00, 0xFF     # $88E0's DIAMOND PIN
        hit, pre, post = split_build(h, m)
        rnd = m[RC.ROUND]
        if rnd not in ROUNDS:
            continue
        rows.append({'round': rnd, 'saw_repaint': hit,
                     'pre': len(pre), 'post': len(post),
                     'post_by_pc': census(post),

                     'gen': [m[GEN], m[GEN_OP], m[GEN_MASK]],
                     'sparkle': [m[SPARKLE + i] for i in range(0x20)],
                     'freeze': [m[FREEZE_A], m[FREEZE_B]],
                     'bank_md5': hashlib.md5(
                         bytes(m[ELEM_BANK:ELEM_BANK + 0x180])).hexdigest()})
    return rows


def counter_rows(h, m):
    """The seven per-build PC counters F0 added, plus the four painters."""
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    targets = set(COUNTERS) | set(PAINTERS) | {REPAINT}
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, RC.ADVANCE)
        hits, total = {}, 0
        stops = targets | set(h.SENTINELS)
        while total < 40 * 10 ** 6:
            h.run_until(stops, limit=40 * 10 ** 6 - total, stride=1,
                        interrupts=True)
            p = h.regs[PC]
            if p in h.SENTINELS:
                break
            hits['%04X' % p] = hits.get('%04X' % p, 0) + 1
            h.step(1, interrupts=True)
            total += 1
        if h.regs[PC] not in h.SENTINELS or h.SENTINELS.index(h.regs[PC]) != 0:
            raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
        rnd = m[RC.ROUND]
        if rnd in ROUNDS:
            rows.append({'round': rnd, 'hits': hits})
    return rows


def reset_walk(h, m):
    """$984B -- the nineteen pointers.  Seed every TARGET to $FF, because most of
       them are ALREADY ZERO when a round ends and "written" and "already 0"
       would otherwise be the same observation."""
    img = open('build/image.bin', 'rb').read()
    targets = [img[RESET_TAB + 2 * i] | (img[RESET_TAB + 2 * i + 1] << 8)
               for i in range(19)]
    for a in targets:
        m[a] = 0xFF
    table_before = [m[RESET_TAB + i] for i in range(38)]
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, 0x984B)
    # $984B is NOT a routine: it falls straight through into $9858's 24 x 256
    # shadow clear and on into the whole build.  Armed without a stop it made
    # 75,708 writes.  The walk proper is $984B..$9856 -- LD B,$13, LD (DE),A,
    # DJNZ -- and ends at $9858.
    h.run_until((0x9858,), limit=10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] != 0x9858:
        raise SystemExit('the walk did not reach $9858 -- PC $%04X' % h.regs[PC])
    h.memobj.unwatch()
    lo, hi = (RC.SP_PIN[0] - 64) & 0xFFFF, RC.SP_PIN[0]
    w = [(p, a, v) for (p, a, v) in h.memobj.log if not (lo <= a <= hi)]
    return {'targets': ['%04X' % a for a in targets],
            'writes': len(w),
            'pcs': sorted(set('%04X' % p for (p, _a, _v) in w)),
            'all_zero': all(m[a] == 0 for a in targets),
            'table_untouched': [m[RESET_TAB + i] for i in range(38)] == table_before,
            'wrote_table': len([1 for (_p, a, _v) in w
                                if RESET_TAB <= a < RESET_TAB + 38])}


def capture():
    h, m = RC.new()
    rows = build_rows(h, m)
    h, m = RC.new()
    counters = counter_rows(h, m)
    h, m = RC.new()
    walk = reset_walk(h, m)
    h, m = RC.new()
    bands = painter_bands(h, m)
    fx = {'note': __doc__.strip(), 'repaint_at': REPAINT,
          'reset_tab_at': RESET_TAB, 'sparkle_at': SPARKLE,
          'gen_at': [GEN, GEN_OP, GEN_MASK], 'freeze_at': [FREEZE_A, FREEZE_B],
          'bank_at': ELEM_BANK, 'painters': ['%04X' % p for p in PAINTERS],
          'counters_at': ['%04X' % p for p in COUNTERS],
          'builds': rows, 'counters': counters, 'walk': walk,
          'bands': bands}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s' % FIXTURE)
    print('  THE PIXEL CENSUS, split at the first $8216:')
    for r in rows:
        print('     round %2d: %6d discarded, %6d SURVIVE'
              % (r['round'], r['pre'], r['post']))
    print('  THE PAINTERS, each bracketed by its own frame:')
    for r in bands:
        print('     round %2d: %s' % (r['round'], r['bands']))
    print('  $9AC1: %d writes from %s, all targets zero %s, table untouched %s'
          % (walk['writes'], walk['pcs'], walk['all_zero'],
             walk['table_untouched']))


def verify():
    fx = json.load(open(FIXTURE))
    print('THE PIXEL CENSUS -- what survives the discard:')
    for r in fx['builds']:
        print('   round %2d: %6d before $8216 (DISCARDED), %6d after (SURVIVE)'
              % (r['round'], r['pre'], r['post']))
    print()
    print('THE PER-BUILD PC COUNTERS:')
    for r in fx['counters']:
        print('   round %2d: %s' % (r['round'], r['hits']))
    print()
    print('THE CORPSE-FRUIT GENERATOR, pinned to DIAMOND before every build:')
    for r in fx['builds']:
        print('   round %2d -> $8B9F=%d $8BA0=$%02X $8BA2=$%02X   %s'
              % (r['round'], r['gen'][0], r['gen'][1], r['gen'][2],
                 'PIN SURVIVED' if r['gen'][1] == 0 else 'pin UNDONE by $9891'))
    print()
    print('THE SPARKLE TABLE, seeded $A5 before every build:')
    for r in fx['builds'][:1]:
        print('   $5CE0..$5CFB: %s' % ['%02X' % v for v in r['sparkle'][:28]])
        print('   $5CFC..$5CFF: %s' % ['%02X' % v for v in r['sparkle'][28:32]])
    print()
    print('$D380 md5 per round (NOT frozen -- the group-3 rounds redraw it):')
    for r in fx['builds']:
        print('   round %2d: %s' % (r['round'], r['bank_md5'][:16]))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
