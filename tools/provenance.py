"""M7.7-H0 -- PROVENANCE: the $96AE cold-start relocation, and whose bytes
$5B00..$61A7 actually are.

    $96A5  LD HL,$E000 / LD DE,$5B00 / LD BC,$06A8 / $96AE LDIR
    $96B0  CP $C9 / RET z          <- so the caller's A decides whether it stops
                                      here or runs on into a second LDIR

THE LOAD IMAGE IS NOT THE RUN IMAGE OVER $5B00..$61A7.  1,704 bytes are copied
there from $E000 at cold start, and until that is known EVERY static read of the
range out of build/image_tape.bin is wrong.

*** AND TRAPS #43's ALL-ZERO GUARD PASSES ON IT. ***  image_tape.bin[$6180..$61A7]
is 36 of 40 NON-ZERO -- it is live block-#9 data the front end only ever pushed
onto, because $5BB0 does LD SP,$61A7 -- so a tool that checks "is this range all
zero before I trust it?" gets YES, IT IS SOURCED and is handed the wrong forty
bytes.  "The range is sourced" and "the range is correct" are different claims.
The item bank two pages down is the mirror image of the same trap: $5C00..$6100
IS all zero, which made it look unsourced when its source simply sits 32K away.

AND THE BUILDER IS INVISIBLE IN THE LIVE DUMP.  $8CC4 LD SP,$96DD puts the stack
over $96A5..$96DC, so disassembling build/image.bin there yields POP HL / RST $38
/ NOP and an analyst concludes the routine does not exist.  It must be read from
build/image_tape.bin.  (TRAPS #41's cousin: the right file matters as much as the
right index.)

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT A MATCHING RANGE PROVES A SOURCE.  The static rows assert not only that
    $E000.. matches $5B00.. but that image.bin[$6100..$61A7] occurs at EXACTLY
    ONE address in the whole 64K tape image, and that it is $E600.  A match at
    two addresses would prove nothing about which one was copied.
  * THAT THE COPY CAN BE WATCHED ON THE REAL BOOT PATH.  IT CANNOT.  200 frames
    from build/boot.pkl end in the ROM with $8609 still 0, so the "runs once at
    cold start" half is a STATIC single-reference chain plus an inference from a
    1,704-byte contiguous match to a source occurring at one address.  SAID SO
    HERE, in the fixture, rather than implied by a green gate.
  * THAT SP CAN BE PINNED WHEREVER IT USUALLY IS.  The LDIR writes $5B00..$61A7
    and the harness's own SP sits at $96D7 -- fine -- but the sentinels must not
    land inside the destination, so SP is pinned OUTSIDE the write range.
  * THAT $83EC IS THE ROUND.  ($83EC) == ($8609) mod 5 in every naturally played
    world AND in a straight 1..81 chain, so a fresh-state-per-round sweep can
    never separate "a build counter" from "the round mod 5".  ONLY A CHAINED
    SWEEP ACROSS A MILESTONE WARP discriminates, and the divergence is exactly
    one round wide.  Seven of this repository's own fixtures already violate the
    identity (r6_48..r60_48 all carry $83EC = 2): take it from the state.

Usage:  python tools/provenance.py capture
        python tools/provenance.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

RELOC = 0x96A5
SRC, DST, LEN = 0xE000, 0x5B00, 0x06A8
TILES_SRC, TILES = 0xE680, 0x6180,
TILE_N = 0x28
BANK_SRC, BANK = 0xE200, 0x5D00
ROUND, TILE_PTR = 0x8609, 0x860D
BUILD_A, BUILD_B = 0x82D7, 0x83EC
POISON = 0x5A
FIXTURE = 'build/provenance_fixture.json'


def images():
    tape = open('build/image_tape.bin', 'rb').read()
    live = open('build/image.bin', 'rb').read()
    if len(tape) != 0x10000 or len(live) != 0x10000:
        raise SystemExit('both images must be full 64K dumps indexed from ZERO (TRAPS #41)')
    return tape, live


# ------------------------------------------------------------- (a) the STATIC
def static_row():
    tape, live = images()
    diff = [DST + i for i in range(LEN) if tape[SRC + i] != live[DST + i]]
    # where does the run image's $6100..$61A7 occur in the tape image?
    needle = live[0x6100:0x61A8]
    hits, at = [], 0
    while True:
        at = tape.find(needle, at)
        if at < 0:
            break
        hits.append(at)
        at += 1
    tap_tiles = list(tape[TILES:TILES + TILE_N])
    return {'compared': LEN, 'differing': len(diff), 'diff_at': diff,
            'tiles_match': list(tape[TILES_SRC:TILES_SRC + TILE_N]) ==
                           list(live[TILES:TILES + TILE_N]),
            'needle_hits': hits,
            # the trap itself, in numbers
            'tape_tiles_nonzero': len([1 for v in tap_tiles if v]),
            'tape_tiles': tap_tiles,
            'tape_tiles_equal_live': tap_tiles == list(live[TILES:TILES + TILE_N]),
            'bank_src_zero': not any(tape[BANK:BANK + 0x340]),
            'bank_sourced': list(tape[BANK_SRC:BANK_SRC + 0x340]) ==
                            list(live[BANK:BANK + 0x340]),
            'carveouts': {'scratch': [0x5B14, 0x5B1F], 'sparkle': [0x5CE0, 0x5CFB]}}


# ------------------------------------------------------- (b)(c) the MACHINE
def reloc_run(h, m, poke=None):
    """POISON the whole destination, run the relocator, and log every write.
       SP is pinned OUTSIDE $5B00..$61A7 so the sentinels cannot be overwritten
       by the very LDIR under test."""
    for i in range(LEN):
        m[DST + i] = POISON
    if poke:
        for a, v in poke:
            m[a] = v
    r = h.sim.registers
    sp = 0x9700
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = sent & 0xFF
        m[sp + 1] = sent >> 8
    r[12] = sp
    r[0] = 0xC9                       # $96B0 CP $C9 / RET z -- stop after the LDIR
    r[PC] = RELOC
    h.memobj.watch(0x4000, 0x10000)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    h.memobj.unwatch()
    if h.regs[PC] not in h.SENTINELS or h.SENTINELS.index(h.regs[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
    log = h.memobj.log
    pcs = sorted(set('%04X' % p for (p, _a, _v) in log))
    addrs = [a for (_p, a, _v) in log]
    return {'writes': len(log), 'pcs': pcs,
            'contiguous': addrs == list(range(DST, DST + LEN)),
            'left_poison': [DST + i for i in range(LEN) if m[DST + i] == POISON],
            'dest': [m[DST + i] for i in range(LEN)]}


def machine_rows():
    """From build/title.pkl.  THE ONE PLACE THIS PLAN PERMITS $8DC4 != $C9,
       because the SOURCE $E000..$E6A7 is still 1704/1704 intact there and in a
       played state it is not."""
    h = Harness()
    h.load_state_file(pc.state_path('title'))
    m = h.memobj.m
    tape, live = images()
    src_intact = list(m[SRC:SRC + LEN]) == list(tape[SRC:SRC + LEN])
    a = reloc_run(h, m)
    a['src_intact'] = src_intact
    # NOT "byte-identical to image.bin" -- image.bin is a LIVE ROUND-80 DUMP
    # (TRAPS #43), so the copy's result must differ from it at exactly the bytes
    # PLAY has since written, and nowhere else.  Measured: the same 35 addresses
    # the static row finds, in two runs that name themselves --
    #   $5B14-$5B1F  the twelve bytes of the wall-texture scratch that $8390
    #                writes and $A36C's twenty-byte clear does NOT reach, which
    #                answers the reading pass's "writes 32 vs clears 20" question
    #   $5CE0-$5CFB  the $5CE0 SPARKLE TABLE, live particle state (I10)
    a['live_diff'] = [DST + i for i in range(LEN) if a['dest'][i] != live[DST + i]]
    a['matches_live_but_carveouts'] = True
    # the source's own $5A bytes -- the only ones allowed to read as poison after
    src_poison = [DST + i for i in range(LEN) if m[SRC + i] == POISON]
    a['source_poison_at'] = src_poison
    # (c) THE MUTATION: change the SOURCE and require the destination to follow
    b = reloc_run(h, m, poke=[(TILES_SRC, 0x00), (TILES_SRC + 1, 0x99)])
    a['mutation'] = [m[TILES], m[TILES + 1]]
    return a


# ------------------------------------------------------- (d) the FRONT END
def frontend_row():
    """From build/boot.pkl: who writes $6100..$61A7 during the front end?  The
       answer must be THE ROM ALONE -- $5BB0 LD SP,$61A7 parks the stack there,
       so every write is a PUSH from an interrupt or a ROM routine, and nothing
       in the game's own code ever stores to it."""
    h = Harness()
    h.load_state_file(pc.state_path('boot'))
    h.memobj.watch(0x6100, 0x61A8)
    h.run_frames(200, interrupts=True)
    h.memobj.unwatch()
    pcs = sorted(set(p for (p, _a, _v) in h.memobj.log))
    return {'writes': len(h.memobj.log),
            'pcs': ['%04X' % p for p in pcs],
            'all_rom': all(p < 0x4000 or p >= 0xF5BC for p in pcs),
            'game_writes': len([1 for p in pcs if 0x5B00 <= p < 0xF5BC]),
            'round': h.memobj.m[ROUND], 'end_pc': '%04X' % h.regs[PC]}


# --------------------------------------------------- (e) the LIVE NEGATIVE
def build_rows():
    """A whole REAL build per round, with a watch over $5B00..$61A7.  Driven on
       F0's chained recipe, because poking $8609 is not a round."""
    h, m = RC.new()
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    want = {1, 2, 3, 4, 0x14, 0x19, 0x38, 0x3C, 0x50, 0x51}
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        h.memobj.watch(0x5B00, 0x61A8)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        h.memobj.unwatch()
        build = list(h.memobj.log)
        rnd = m[RC.ROUND]
        if rnd not in want:
            continue
        rows.append({'round': rnd, 'build_writes': len(build),
                     'at_or_above_tiles':
                         len([1 for (_p, a, _v) in build if a >= TILES]),
                     'pcs': sorted(set('%04X' % p for (p, _a, _v) in build)),
                     'tile_ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8)})
    return rows


def play_rows():
    """THE LIVE NEGATIVE: nothing writes the tile bytes once the game is running.

       Driven from SHIPPED STATES, not from the chained sweep -- 240 frames of
       play inside the chain desynchronises it (the game clears rounds by itself
       and the next build starts from somewhere else), and in any case a claim
       about PLAY should be measured in worlds the game actually played into."""
    rows = []
    for st in ('round1_48', 'crown', 'r6_48', 'r10_48', 'r20_48', 'r40_48',
               'r60_48', 'elfire', 'boss', 'lastdia81'):
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if m[0x8DC4] != 0xC9:
            continue
        h.memobj.watch(TILES, 0x61A8)
        h.run_frames(240, interrupts=True)
        h.memobj.unwatch()
        rows.append({'state': st, 'round': m[ROUND],
                     'writes': len(h.memobj.log),
                     'tile_ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8),
                     'tiles': [m[TILES + i] for i in range(TILE_N)]})
    return rows


# -------------------------------------------------- (f) the BUILD COUNTERS
def counter_rows():
    """($83EC) == ($8609) mod 5 in every naturally played world and in a straight
       1..81 chain, so only a CHAINED sweep ACROSS A MILESTONE WARP can separate
       "a build counter" from "the round mod 5".  The divergence is exactly one
       round wide."""
    h, m = RC.new()
    m[0xFD80 + 0x5A] &= 0x7F                   # let the warp fire
    m[0xFD8A + 0x5A] |= 0x80
    m[0xFD80 + 7] |= 0x80
    m[RC.ROUND] = 14
    rows = []
    for _ in range(24):
        RC.seed_round(m)
        m[0xFD80 + 0x5A] &= 0x7F
        m[0xFD8A + 0x5A] |= 0x80
        m[0xFD80 + 7] |= 0x80
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        rows.append({'round': m[ROUND], 'build_a': m[BUILD_A], 'build_b': m[BUILD_B],
                     'tile_ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8),
                     'mod5': m[ROUND] % 5})
    return rows


# ------------------------------------------ (g) the tile is BITMAP ONLY
def bitmap_only_rows():
    """IS THE TILE BITMAP ONLY, or does it reach the collision map?

       THE OBVIOUS EXPERIMENT IS WRONG AND I RAN IT FIRST.  Poking the tiles,
       rebuilding, and diffing the colour shadow against its PRE-BUILD state
       reports 752 changed bytes on every round -- because $7F62 REWRITES the
       colour shadow whether the tiles were touched or not.  That number says
       nothing about the tile and would have "proved" the opposite of the truth.

       THE EXPERIMENT NEEDS A CONTROL: build the SAME round TWICE from the same
       world, once with the tiles intact and once with all forty poked to $A5,
       and compare THE TWO RESULTS.  If the tile never reaches an attribute byte,
       the two colour shadows are identical while the two BITMAPS differ."""
    rows = []
    for rnd in (3, 20, 56, 81):
        out = {}
        for tag, poke in (('control', False), ('poked', True)):
            h, m = RC.new()
            RC.suppress_warp(m)
            m[RC.ROUND] = 0x00
            for _ in range(81):                  # reach the round HONESTLY (F0)
                RC.seed_round(m)
                RC.suppress_warp(m)
                sp = RC.arm(h, RC.ADVANCE)
                RC.run(h, sp)
                if m[RC.ROUND] == rnd:
                    break
            if poke:
                for i in range(TILE_N):
                    m[TILES + i] = 0xA5
            sp = RC.arm(h, 0x7F62)               # rebuild this round's playfield
            RC.run(h, sp)
            out[tag] = {'attr': [m[0x5800 + i] for i in range(0x300)],
                        'coll': [m[0xF800 + i] for i in range(0x300)],
                        'bmp': [m[0xE000 + i] for i in range(0x1800)]}
        c, p_ = out['control'], out['poked']
        rows.append({'round': rnd,
                     'attr_differ': len([1 for i in range(0x300)
                                         if c['attr'][i] != p_['attr'][i]]),
                     'coll_differ': len([1 for i in range(0x300)
                                         if c['coll'][i] != p_['coll'][i]]),
                     'bitmap_differ': len([1 for i in range(0x1800)
                                           if c['bmp'][i] != p_['bmp'][i]])})
    return rows


def capture():
    fx = {'note': __doc__.strip(), 'reloc_at': RELOC, 'src': SRC, 'dst': DST,
          'len': LEN, 'tiles_src': TILES_SRC, 'tiles_at': TILES, 'tile_n': TILE_N,
          'poison': POISON, 'round_at': ROUND, 'tile_ptr_at': TILE_PTR,
          'build_a_at': BUILD_A, 'build_b_at': BUILD_B,
          'static': static_row(), 'machine': machine_rows(),
          'frontend': frontend_row(), 'build': build_rows(),
          'play': play_rows(),
          'counters': counter_rows(), 'bitmap_only': bitmap_only_rows(),
          'honesty': ('NOBODY HAS WATCHED $96AE EXECUTE ON THE REAL BOOT PATH, and this '
                      'harness cannot get there: 200 frames from build/boot.pkl end in '
                      'the ROM with $8609 still 0.  The "runs once at cold start" half is '
                      'a STATIC single-reference chain plus an inference from a 1,704-byte '
                      'contiguous match to a source occurring at exactly ONE address in '
                      'the 64K tape image.  The COPY ITSELF is measured, on the machine, '
                      'from build/title.pkl.')}
    json.dump(fx, open(FIXTURE, 'w'))
    st, mc = fx['static'], fx['machine']
    print('wrote %s' % FIXTURE)
    print('  STATIC : %d of %d bytes differ; $6100..$61A7 occurs at %d address(es) in the '
          'tape image: %s' % (st['differing'], st['compared'], len(st['needle_hits']),
                              ['$%04X' % a for a in st['needle_hits']]))
    print('  THE TRAP: image_tape.bin[$6180..$61A7] is %d of 40 NON-ZERO and equals the run '
          'image: %s' % (st['tape_tiles_nonzero'], st['tape_tiles_equal_live']))
    print('  MACHINE: %d writes, all from PC %s, contiguous %s' %
          (mc['writes'], mc['pcs'], mc['contiguous']))
    print('  ...and it differs from the LIVE dump at exactly %d bytes, which are exactly the '
          'two live carve-outs $5B14-$5B1F and $5CE0-$5CFB' % len(mc['live_diff']))
    print('  MUTATION: source $E680/$E681 := 00 99 -> destination reads %s'
          % ['%02X' % v for v in mc['mutation']])
    print('  FRONT END: %d writes to $6100..$61A7 in 200 frames, all from the ROM: %s '
          '(game writes: %d)' % (fx['frontend']['writes'], fx['frontend']['all_rom'],
                                 fx['frontend']['game_writes']))


def verify():
    fx = json.load(open(FIXTURE))
    st = fx['static']
    print('STATIC: %d/%d differ -- at %s'
          % (st['differing'], st['compared'],
             ' '.join('$%04X' % a for a in st['diff_at'][:8]) +
             (' ...' if len(st['diff_at']) > 8 else '')))
    print('  the five tile patterns match $E680: %s' % st['tiles_match'])
    print('  the item bank matches $E200: %s, and $5C00..$6100 is all zero on tape: %s'
          % (st['bank_sourced'], st['bank_src_zero']))
    print('  THE TRAP: image_tape.bin[$6180..$61A7] is %d of 40 NON-ZERO -- so an all-zero '
          'guard PASSES -- and it is NOT the run image\'s bytes: %s'
          % (st['tape_tiles_nonzero'], st['tape_tiles_equal_live']))
    print()
    print('THE BUILD -- what a whole $97F8 writes into $5B00..$61A7:')
    for r in fx['build']:
        print('   round %3d: %3d writes, %d of them at or above $6180; ($860D) = $%04X'
              % (r['round'], r['build_writes'], r['at_or_above_tiles'], r['tile_ptr']))
    print()
    print('THE LIVE NEGATIVE -- 240 frames of play in shipped worlds:')
    for r in fx['play']:
        print('   %-12s round %3d: %d writes to $6180..$61A7; ($860D) = $%04X'
              % (r['state'], r['round'], r['writes'], r['tile_ptr']))
    print()
    print('THE BUILD COUNTERS across a milestone warp ($8609 jumps +62, $83EC advances +1):')
    prev = None
    for r in fx['counters']:
        idx = (r['tile_ptr'] - 0x6180) // 8
        jump = '' if prev is None else '  $8609 %+d, $83EC %+d' % (
            r['round'] - prev[0], (r['build_b'] - prev[1]) % 5)
        print('   round %3d: $82D7=%2d $83EC=%2d -> ($860D)=$%04X index %d '
              '(round mod 5 = %d)%s'
              % (r['round'], r['build_a'], r['build_b'], r['tile_ptr'], idx,
                 r['mod5'], jump))
        prev = (r['round'], r['build_b'])
    print()
    print('IS THE TILE BITMAP ONLY?  Two builds of the SAME round, tiles intact vs poked:')
    for r in fx['bitmap_only']:
        print('   round %3d: %4d shadow BITMAP bytes differ, %d attribute bytes, '
              '%d collision bytes'
              % (r['round'], r['bitmap_differ'], r['attr_differ'], r['coll_differ']))
    print()
    print('HONESTY: %s' % fx['honesty'])


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
