"""M7.7-I11 -- THE TREASURE ROOM's FILL: handler 12's tail $890D and the
placement probe $899E/$89B7.

    $891E  XOR A / LD ($FDE2),A / LD ($FDEC),A     both players' tallies := 0
    $8925  INC A / LD ($FED1),A                    THE LATCH, and $8E40 diverts on it
    $8929  LD ($9049),A                            ...and the hurry-up latch too
    $892C  LD A,($8DBE) / LD ($8F3A),A             CAPTURE the timer HIGH byte into
                                                   the operand of $8F39's SUB n
    $8932  LD A,($8609) / CP $51                   round 81?
    $8937  LD A,1 / LD HL,$FFDF                      no  -> type 1, probe offset -$21
    $893E  LD A,9 / LD HL,$FFFF                      yes -> type 9, probe offset -1
    $8943  LD ($896D),A / LD ($899F),HL            BOTH are SELF-MODIFIED OPERANDS
    $894B  CALL $8C14
    $8950  ...the FILL: 6 rows x 7 columns, 31 entries max, X from $20 step $20,
           Y from $20 step $18, writing byte0 = X | type and byte1 = Y into the
           item block FROM $9605 -- ENTRY 1, a THIRD base over the same 64 bytes
           after I1's $9603 and I9's $9607.

THE FILL RUNS ON TWO REGISTER SETS.  MAIN holds (B = entries left, HL = the item
cursor, D = Y, E = X); ALT holds (B = columns left, C = rows left, HL = the
colour-shadow probe cursor).  A model that keeps one set agrees on a full map and
diverges the moment the table fills mid-row.

THE PROBE ABANDONS ITS CALLER.  $89B7 checks three consecutive colour-shadow
cells for bit 5, and on finding one does POP HL / RET -- discarding $899E's frame
and returning to $890D's $8967 with CARRY CLEAR, bypassing the $89B5 SCF.  That
is the third routine in this game to return past its caller, after $B679 and
$88B1.  So "no carry" is not a value $899E computes; it is a control-flow fact.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT THE COUNT IS A CONSTANT.  It is a function of the MAP (the probe reads
    the colour shadow) AND of the TYPE (the $899F offset is -$21 for type 1 and
    -1 for type 9).  The two offsets AGREE on some maps and differ on others, so
    a gate driven only on a map where they agree cannot tell them apart.  Every
    count here is READ FROM THE MACHINE and the two offsets are run side by side.
  * THAT POKING $8609 GIVES YOU A ROUND.  It does not (F0).  The rounds here are
    reached with F0's chained-build recipe, so the map under the probe is the map
    that round really builds.
  * THAT THE SELF-MODIFIED BYTES START WHERE THE IMAGE HAS THEM.  $896D, $899F
    and $8F3A are all LIVE STATE, and $8F3A differs between the two images
    (image.bin SUB 5, image_tape.bin SUB $2A).  All four are POISONED to $5A
    before every call, so "written" and "happened to already be right" separate.

Usage:  python tools/treasure.py capture
        python tools/treasure.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

FILL = 0x890D
BLOCK, BLOCK_N = 0x9603, 64
TYPE_OP, PROBE_OP = 0x896D, 0x899F
CAPTURE_OP = 0x8F3A
LATCH, HURRY_LATCH = 0xFED1, 0x9049
TALLY1, TALLY2 = 0xFDE2, 0xFDEC
TIMER_HI = 0x8DBE
SHADOW = 0xF800
POISON = 0x5A
FIXTURE = 'build/treasure_fixture.json'
ROUNDS = (1, 2, 5, 20, 56, 80, 81)


def poison(m):
    """Every byte the tail writes, set to something it does NOT write -- so a
       model that omits the write cannot agree by inheritance (TRAPS #44)."""
    m[TYPE_OP] = POISON
    m[PROBE_OP], m[PROBE_OP + 1] = POISON, POISON
    m[CAPTURE_OP] = POISON
    m[LATCH] = POISON
    m[HURRY_LATCH] = POISON
    m[TALLY1], m[TALLY2] = POISON, POISON
    for i in range(BLOCK_N):
        m[BLOCK + i] = 0
    m[BLOCK] = 0x77          # entry 0 NON-ZERO: the $9605 base and a $9603 base
    m[BLOCK + 1] = 0x88      # agree whenever slot 0 is empty (the I9 trap, one over)
    for i in range(6):
        m[BLOCK + BLOCK_N + i] = 0xC9    # the image's own RET, and a guard


def snap(m):
    ent = []
    for k in range(32):
        b0, b1 = m[BLOCK + 2 * k], m[BLOCK + 2 * k + 1]
        if b0:
            ent.append([k, b0, b1])
    return {'entries': ent, 'count': len(ent),
            'block': [m[BLOCK + i] for i in range(BLOCK_N)],
            # PAST THE BLOCK.  A fill given 32 entries instead of 31, or one
            # whose counter is never decremented, writes here -- and a gate that
            # stops at 64 bytes cannot see it (the I9 overrun, one increment on).
            'over': [m[BLOCK + BLOCK_N + i] for i in range(6)],
            'type_op': m[TYPE_OP],
            'probe_op': m[PROBE_OP] | (m[PROBE_OP + 1] << 8),
            'capture_op': m[CAPTURE_OP], 'latch': m[LATCH],
            'hurry_latch': m[HURRY_LATCH],
            'tally': [m[TALLY1], m[TALLY2]]}


def fill_at(h, m, ix=0xFD80, timer_hi=0x2C):
    poison(m)
    m[TIMER_HI] = timer_hi
    r = h.sim.registers
    r[8], r[9] = ix >> 8, ix & 0xFF          # IX -- $8949 PUSH IX / $894E POP IX
    sp = RC.arm(h, FILL)
    RC.run(h, sp)
    return snap(m)


def fill_only(h, m, type_, off):
    """THE FILL LOOP ALONE, over whatever map the world already holds.

       $890D's tail calls $8C14 first, and $8C14 RES 7s seven entity slots and
       twelve bubble slots, then CALLs $8216 to repaint the whole playfield from
       the shadow (7,076 display writes, measured) and recolours it.  That is
       render work and it belongs to (h), so the port models the tail's LATCHES
       and the FILL, and the gate drives $8950 directly rather than pretending to
       reproduce a repaint this increment does not own."""
    poison(m)
    m[TYPE_OP] = type_
    m[PROBE_OP], m[PROBE_OP + 1] = off & 0xFF, off >> 8
    sp = RC.arm(h, 0x8950)
    RC.run(h, sp)
    return snap(m)


def built_rows(h, m):
    """BUILT WORLDS, because no round the game ships can separate two models of
       the table-full exit.

       $8974's EI / RET ends the WHOLE fill; a model that merely ends the current
       ROW differs only when the table fills with passing cells STILL TO COME IN
       A LATER ROW.  Measured over all 81 rounds: only round 80 fills at all, at
       32 of its 42 cells, and its one spare cell is in the same row as the last
       placement -- so on every shipped map "end the fill" and "end the row" are
       the same function.

       With the colour shadow CLEAR everywhere all 42 cells pass, the table fills
       on cell 31 with eleven still to come across two later rows, and the two
       models finally diverge -- the wrong one carrying the entry counter past
       zero to $FF and writing over the six bytes past the block, which is where
       I9 measured the corpse landing scribbling on the image's own RET."""
    rows = []
    for (name, fill) in (('every cell open', 0x00),
                         ('every cell solid', 0x20),
                         ('alternate ROWS solid', None)):
        for i in range(0x300):
            if fill is None:
                m[SHADOW + i] = 0x20 if ((i // 0x20) % 6) < 3 else 0x00
            else:
                m[SHADOW + i] = fill
        r = fill_only(h, m, 1, 0xFFDF)
        r['name'] = name
        r['shadow'] = [m[SHADOW + i] for i in range(0x300)]
        rows.append(r)
    return rows


def forced_offset(h, m, off, ix=0xFD80):
    """The SAME map, filled with the probe offset forced BOTH ways.  This is the
       equal-answer separator: the two offsets agree on some maps and not others,
       and a gate driven only where they agree tests nothing about the choice."""
    poison(m)
    r = h.sim.registers
    r[8], r[9] = ix >> 8, ix & 0xFF
    # run the tail, then redo only the fill with the offset forced
    sp = RC.arm(h, FILL)
    RC.run(h, sp)
    poison(m)
    m[TYPE_OP] = 1
    m[PROBE_OP], m[PROBE_OP + 1] = off & 0xFF, off >> 8
    sp = RC.arm(h, 0x8950)                   # the FILL loop alone
    RC.run(h, sp)
    return snap(m)


# ------------------------------------------------------------- the DRAIN
CHECK = 0x8E3A
PEND = 0xFFED
SCORES = 0xFFE1
P1F, P2F = 0xFD87, 0xFD91          # the two players' +7 ACTIVE flags
TALLY_P1, TALLY_P2 = 0xFDE2, 0xFDEC
PERFECT_CELLS = (0x484B, 0x594B, 0x596B)
F = 1                              # skoolkit.simutils.REGISTERS['F']


def drain_rows(h, m):
    """$8E3A -> $8F36, driven as the WHOLE DECISION so the wiring is gated too.

       THE WINDOW IS AN EQUALITY, so the sweep must include deltas ABOVE 8: a
       port that writes `>=` agrees on 0..7 and on every empty-table row, and
       only a delta of 9 or more with items still live can tell them apart.
       $FF and $F8 are in the sweep because the subtraction WRAPS in eight bits.

       AND THE PLAYERS ARE SEEDED ACTIVE.  $80FA tests BIT 7,(IX+7) and discards
       the award when it is clear; a clean slate that zeroes every slot's +7
       across twelve slots hits $FD87 and $FD91 -- BOTH PLAYERS -- and then no
       row can observe an award at all."""
    rows = []
    for (name, delta, live, t1, t2, twop, latch, rnd) in (
            ('window short, items live',        0, 5, 0x10, 0x08, 1, 0, 2),
            ('window short by one, items live', 7, 5, 0x10, 0x08, 1, 0, 2),
            ('THE WINDOW, items live',          8, 5, 0x10, 0x08, 1, 0, 2),
            ('window PAST by one, items live',  9, 5, 0x10, 0x08, 1, 0, 2),
            ('window past by eight, items live', 0x10, 5, 0x10, 0x08, 1, 0, 2),
            ('window wrapped, items live',   0xF8, 5, 0x10, 0x08, 1, 0, 2),
            ('window at -1, items live',     0xFF, 5, 0x10, 0x08, 1, 0, 2),
            ('window short, table EMPTY',       0, 0, 0x10, 0x08, 1, 0, 2),
            ('THE WINDOW, table EMPTY',         8, 0, 0x10, 0x08, 1, 0, 2),
            ('window past, table EMPTY',        9, 0, 0x10, 0x08, 1, 0, 2),
            ('one item left',                   0, 1, 0x10, 0x08, 1, 0, 2),
            ('P2 ahead',                        0, 0, 0x08, 0x10, 1, 0, 2),
            ('a TIE',                           0, 0, 0x10, 0x10, 1, 0, 2),
            ('the SIGNED boundary, P1 $7F',     0, 0, 0x7F, 0x80, 1, 0, 2),
            ('the SIGNED boundary, P1 $80',     0, 0, 0x80, 0x7F, 1, 0, 2),
            ('ONE PLAYER only',                 0, 0, 0x10, 0x08, 0, 0, 2),
            ('the $8E3B latch PREEMPTS',        0, 0, 0x10, 0x08, 1, 1, 2),
            ('round 20',                        0, 0, 0x10, 0x08, 1, 0, 20),
            ('round 81',                        0, 0, 0x10, 0x08, 1, 0, 81),
            ('round 81, THE WINDOW, live',      8, 5, 0x10, 0x08, 1, 0, 81),
            # THE WRAP, for real: with the capture near the top of the byte the
            # eight-bit difference is 8 while the plain subtraction is -248, so
            # "& $FF" and "no mask" finally disagree.  Every row above has them
            # agreeing, which is why a sixteen-bit model survived a battery.
            ('capture $FC, high $04 -- A REAL WRAP', 8, 0, 0x10, 0x08, 1, 0, 2),
            ('capture $FC, high $04, items live',    8, 5, 0x10, 0x08, 1, 0, 2),
            ('capture $FC, off by one',              9, 5, 0x10, 0x08, 1, 0, 2)):
        # a clean slate that does NOT wipe the players
        for k in range(12):
            m[0xFD80 + 10 * k + 7] = 0x40
        m[P1F] = 0x80                                  # ACTIVE -- $810C BIT 7,(IX+7)
        m[P2F] = 0x80 if twop else 0x00
        for i in range(BLOCK_N):
            m[BLOCK + i] = 0
        m[BLOCK] = 0x77                                # entry 0 live: $8F94 starts at $9605
        m[BLOCK + 1] = 0x88                            # and must NOT count it
        for i in range(6):
            m[BLOCK + BLOCK_N + i] = 0xC9
        # THE LIVE ENTRIES GO AT THE TOP OF THE TABLE, not the bottom.  With
        # them at entries 1..5 a 30-entry walk and a 31-entry walk both find
        # them, and the corpse scan's own B = $1E could not be told from this
        # one's $1F.  Entry 31 is inside only the longer walk.
        for k in range(live):
            e = 31 - k
            m[BLOCK + 2 * e] = 0x21
            m[BLOCK + 2 * e + 1] = 0x40
        # AND A BYTE1-ONLY ENTRY, always: byte0 zero, byte1 loud.  It separates
        # "counts byte0" from "counts byte1", and a two-byte stride from a
        # one-byte stride, neither of which any row with both bytes set can do.
        m[BLOCK + 2 * 20] = 0x00
        m[BLOCK + 2 * 20 + 1] = 0x7E
        m[TALLY_P1], m[TALLY_P2] = t1, t2
        m[0xFED1] = 1
        m[0x8E3B] = latch
        m[0x8609] = rnd
        cap = 0xFC if name.startswith('capture $FC') else 0x20
        m[CAPTURE_OP] = cap
        m[TIMER_HI] = (cap + delta) & 0xFF
        m[0x8DBD] = 0x00
        for i in range(4):
            m[PEND + i] = 0x99                         # NON-ZERO: $8F66/$8F6F write only two
        for i in range(12):
            m[SCORES + i] = 0
        for a in PERFECT_CELLS:
            m[a] = 0x5A
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, CHECK)
        h.run_until(h.SENTINELS, limit=40 * 10 ** 6, stride=1, interrupts=False)
        h.memobj.unwatch()
        r = h.regs
        if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
            raise SystemExit('bad bracket -- PC $%04X' % r[PC])
        z = 1 if (r[F] & 0x40) else 0
        lo, hi = (RC.SP_PIN[0] - 64) & 0xFFFF, RC.SP_PIN[0]
        wr = [(a, v) for (_p, a, v) in h.memobj.log if not (lo <= a <= hi)]
        rows.append({'name': name, 'delta': delta, 'live': live,
                     't1': t1, 't2': t2, 'twop': twop, 'latch': latch,
                     'round': rnd, 'z': z,
                     'scores': [m[SCORES + i] for i in range(12)],
                     'pend': [m[PEND + i] for i in range(4)],
                     'perfect': [m[a] for a in PERFECT_CELLS],
                     'over': [m[BLOCK + BLOCK_N + i] for i in range(6)],
                     'screen_writes': len([1 for (a, _v) in wr
                                           if 0x4000 <= a < 0x5B00]),
                     'block': [m[BLOCK + i] for i in range(BLOCK_N)]})
    return rows


def capture():
    h, m = RC.new()
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows, off_rows = [], []
    want = set(ROUNDS)
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)                        # a REAL build of this round
        rnd = m[RC.ROUND]
        if rnd not in want:
            continue
        shadow_md5 = sum(m[SHADOW + i] for i in range(0x300))
        row = fill_at(h, m)
        row['round'] = rnd
        row['shadow_sum'] = shadow_md5
        rows.append(row)
        a = fill_only(h, m, 1, 0xFFDF)
        b = fill_only(h, m, 9, 0xFFFF)
        off_rows.append({'round': rnd, 'off_DF': a['count'], 'off_FF': b['count'],
                         'entries_DF': a['entries'], 'entries_FF': b['entries'],
                         'block_DF': a['block'], 'block_FF': b['block'],
                         'over_DF': a['over'], 'over_FF': b['over'],
                         'shadow': [m[SHADOW + i] for i in range(0x300)]})
    built = built_rows(h, m)
    drain = drain_rows(h, m)
    fx = {'note': __doc__.strip(), 'fill_at': FILL, 'block_at': BLOCK,
          'check_at': CHECK, 'pend_at': PEND, 'scores_at': SCORES,
          'p1f_at': P1F, 'p2f_at': P2F,
          'tally_at2': [TALLY_P1, TALLY_P2],
          'perfect_cells': list(PERFECT_CELLS), 'drain': drain,
          'type_op_at': TYPE_OP, 'probe_op_at': PROBE_OP,
          'capture_op_at': CAPTURE_OP, 'latch_at': LATCH,
          'hurry_latch_at': HURRY_LATCH, 'tally_at': [TALLY1, TALLY2],
          'timer_hi_at': TIMER_HI, 'shadow_at': SHADOW, 'poison': POISON,
          'rows': rows, 'offsets': off_rows, 'built': built}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d fill rows, %d offset pairs, %d built, %d drain rows'
          % (FIXTURE, len(rows), len(off_rows), len(fx['built']), len(fx['drain'])))
    for r in fx['built']:
        print('  BUILT %-22s -> %2d entries, past the block %s'
              % (r['name'], r['count'], ['%02X' % v for v in r['over']]))
    for r in rows:
        print('  round %2d -> %2d entries, type %d, probe $%04X, capture $%02X'
              % (r['round'], r['count'], r['type_op'], r['probe_op'],
                 r['capture_op']))


def verify():
    fx = json.load(open(FIXTURE))
    print('ROUND  ENTRIES  TYPE  PROBE   CAPTURE  LATCH  TALLY  slot0')
    for r in fx['rows']:
        print('  %3d    %3d     %2d   $%04X     $%02X     %d    %s   %s'
              % (r['round'], r['count'], r['type_op'], r['probe_op'],
                 r['capture_op'], r['latch'], r['tally'],
                 'FREE' if r['block'][0] == 0 else '$%02X' % r['block'][0]))
    print()
    print('THE DRAIN -- Z is the answer ($8E3A returns it in the flag, M7.7-b):')
    for r in fx['drain']:
        print('  %-32s delta %3d live %d -> Z=%d  P1 %s  P2 %s  %5d screen writes'
              % (r['name'], r['delta'], r['live'], r['z'],
                 ''.join('%02X' % v for v in r['scores'][4:8]),
                 ''.join('%02X' % v for v in r['scores'][8:12]),
                 r['screen_writes']))
    print()
    print('THE PROBE OFFSET, same map both ways -- where they AGREE a gate tests nothing:')
    print('(the fill loop $8950 driven DIRECTLY, so no repaint is in the comparison)')
    for r in fx['offsets']:
        print('  round %2d: offset -$21 -> %2d entries, offset -$01 -> %2d  %s'
              % (r['round'], r['off_DF'], r['off_FF'],
                 'DIFFER' if r['off_DF'] != r['off_FF'] else 'agree'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
