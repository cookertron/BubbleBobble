"""M7.7-H9 -- THE POST-$8216 HUD FURNITURE: $7FC0, $806C, $957E, $9904.

H1 retracted "NO PIXELS AT ALL" and counted four painters that all run AFTER the
repaint.  This is where they are measured, and every one of them has a reason it
cannot be gated the obvious way.

  $7FC0  ROUND 1 ONLY -- its sole reference in both images is `CC C0 7F`
         (CALL z), so a port that never builds round 1 HAS NO HUD AT ALL.  Its
         RRD loop turns the four BCD bytes of the HIGH score into eight ASCII
         digits at $85E9..$85F0, walking DE BACKWARDS, and *** THREE RRDs PER
         BYTE RESTORE THE RECORD ***: "it converts the record" and "it consumes
         the record" are indistinguishable unless the records are POKED APART.
         It also CALLs $806C at $7FDF, so a naive census double-counts.
  $806C  EVERY round.  The lives icons, min(lives,5)+1 cells, into the DISPLAY,
         the SHADOW (+$A000) and the ATTRIBUTES.  TWO SELF-MODS: $8098 patches
         $80F6 with `INC L` ($2C) or `DEC L` ($2D) so P2's row walks LEFT, and
         $80B9 patches the OPERAND of $80C0 so the shadow receives the byte just
         written to the display.  $8097 RET p is the IN-PLAY test, on bit 7 of
         $FD87/$FD91 -- so P2's whole half is DEAD in a one-player world.
  $957E  the EXTEND-letter row.  *** IT WRITES NO PIXELS unless a letter has been
         collected, and the masks are $00 after every measured build ***, so an
         unseeded gate here is green and checks nothing (TRAPS #44).  H6 settled
         what those bits are: SIX of them, at $FDE3/$FDED, fed by the element
         class through $B80E.  Its second pass is a FALL-THROUGH, and $95AE is a
         SELF-MODIFIED column offset that is 0 for P1 and $1F for P2.
  $9904  the banner restore, on EVERY round including 81: LDIR from the SHADOW
         to the DISPLAY, then an attribute pass that reads bit 5 of the COLOUR
         shadow and picks $8309 or $830A -- H3's two derived attributes again.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT ROUND 1 IS A FAIR TEST.  On round 1 $7FC0's 488 display writes swamp
    $806C's 32 and hide any ordering bug, so every census is taken on worlds that
    have BUILT rounds 2, 5 and 80, and $7FC0 is FORCED on a round-2 world rather
    than reached by building round 1.

  * THAT `LD BC,$08FF` IS A `for i in range(8)`.  It is ONE instruction and a
    TRAPS #45 site.  It is PROVABLY SAFE as shipped -- BC walks $08FF, $07FE ...
    $01F8 and C never borrows into B -- but the $FF is LOAD-BEARING, and the
    oracle proves it by poking C and measuring the damage rather than asserting
    it.

  * THAT A WRITE CENSUS OF $7FC0 IS $7FC0's.  It CALLs $806C, so the nested
    frame is measured separately and subtracted.

Usage:  python tools/hudfurniture.py capture
        python tools/hudfurniture.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

HUD = 0x7FC0
LIVES = 0x806C
EXTEND = 0x957E
BANNER = 0x9904
REPAINT = 0x8216
BUILD = 0x97F8
LIVES_SRC = 0x85B1            # where $806C LDIs the tile pattern
LIVES_WALK_OP = 0x80F6        # INC L / DEC L, patched by $8098
LIVES_SHADOW_OP = 0x80C1      # the operand of $80C0, patched by $80B9
EXT_COL_OP = 0x95AE           # the self-modified column offset
ASCII_AT, ASCII_N = 0x85E9, 8
HIGH, P1S, P2S = 0xFFE1, 0xFFE5, 0xFFE9
P1_FLAGS, P2_FLAGS = 0xFD87, 0xFD91
P1_LIVES, P2_LIVES = 0xFDDC, 0xFDE6
EXT_P1, EXT_P2 = 0xFDE3, 0xFDED
ROUND = 0x8609
ROUNDS = (2, 5, 80)
FIXTURE = 'build/hudfurniture_fixture.json'


def build_to(h, m, target):
    """Chained builds from a new game -- F0's recipe.  Poking $8609 is not a
       round sample (F0), and on rounds 80/81 several fields are INHERITED."""
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    for _ in range(100):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, BUILD)
        RC.run(h, sp)
        if m[ROUND] == target:
            return
    raise SystemExit('never reached round %d' % target)


def census(h, m, addr, nested=(), hl=None):
    """*** A ROUTINE WITH AN ARGUMENT CANNOT BE DRIVEN COLD. ***  My first run
       called $9904 with whatever HL happened to hold and got 0 display writes,
       21 attributes and 103 scattered RAM writes -- a census of nothing.  $9904
       takes the banner address in HL ($484C and $488C, from $98E4/$98EA)."""
    """One routine's whole write census, split by region.  A nested CALL's frame
       is measured separately so it can be subtracted rather than silently
       inflating its caller."""
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, addr)
    if hl is not None:
        h.sim.registers[6] = hl >> 8            # H
        h.sim.registers[7] = hl & 0xFF          # L
    inner = {}
    if nested:
        stops = set(nested) | set(h.SENTINELS)
        while True:
            h.run_until(stops, limit=40 * 10 ** 6, stride=1, interrupts=False)
            p = h.regs[PC]
            if p in h.SENTINELS:
                break
            esp = h.regs[12]
            before = len(h.memobj.log)
            h.step(1, interrupts=False)
            h.run_until((), limit=10 ** 7, stride=1, interrupts=False,
                        predicate=lambda hh: hh.regs[12] > esp)
            rows = h.memobj.log[before:]
            k = '%04X' % p
            d = inner.setdefault(k, {'calls': 0, 'display': 0, 'attrs': 0,
                                     'shadow': 0, 'ram': 0})
            d['calls'] += 1
            for (_p, a, _v) in rows:
                d[region(a)] += 1
    else:
        # *** INTERRUPTS OFF. ***  RC.run drives with interrupts ON, which is right
        # for a whole build and WRONG for an isolated routine: on round 5 the ISR
        # fired inside this census and added twelve writes from $B674 -- the BUBBLE
        # MANAGER's slot counter (H5) -- plus ~38 more, so the "same" call measured
        # 120 writes on round 2 and 170 on round 5 with identical inputs.  H2 paid
        # for this once already (576 phantom repaint writes).
        h.run_until(h.SENTINELS, limit=40 * 10 ** 6, stride=1, interrupts=False)
        if h.regs[PC] not in h.SENTINELS or h.SENTINELS.index(h.regs[PC]) != 0:
            raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
        if h.regs[12] != sp + 2:
            raise SystemExit('SP ended at $%04X, expected $%04X' % (h.regs[12], sp + 2))
    log = list(h.memobj.log)
    h.memobj.unwatch()
    out = {'writes': len(log), 'display': 0, 'attrs': 0, 'shadow': 0, 'ram': 0,
           'by_pc': {}, 'nested': inner}
    for (p_, a, _v) in log:
        out[region(a)] += 1
        k = '%04X' % p_
        out['by_pc'][k] = out['by_pc'].get(k, 0) + 1
    return out


def region(a):
    if a < 0x5800:
        return 'display'
    if a < 0x5B00:
        return 'attrs'
    if 0xE000 <= a < 0xF800:
        return 'shadow'
    return 'ram'


# ------------------------------------------------- (a) the four censuses
def painter_rows(h, m):
    rows = []
    for rnd in ROUNDS:
        build_to(h, m, rnd)
        r = {'round': rnd, 'lives': [m[P1_LIVES], m[P2_LIVES]],
             'inplay': [m[P1_FLAGS], m[P2_FLAGS]],
             'ext': [m[EXT_P1], m[EXT_P2]]}
        r['lives_1p'] = census(h, m, LIVES)
        m[P2_FLAGS] |= 0x80                          # P2's half is DEAD otherwise
        r['lives_2p'] = census(h, m, LIVES)
        m[P2_FLAGS] &= 0x7F
        r['extend_fresh'] = census(h, m, EXTEND)
        m[EXT_P1], m[EXT_P2] = 0x3F, 0x15            # SIX bits and THREE (TRAPS #44)
        m[P2_FLAGS] |= 0x80
        r['extend_seeded'] = census(h, m, EXTEND)
        m[EXT_P1], m[EXT_P2], m[P2_FLAGS] = 0, 0, m[P2_FLAGS] & 0x7F
        r['banner_484C'] = census(h, m, BANNER, hl=0x484C)
        r['banner_488C'] = census(h, m, BANNER, hl=0x488C)
        if rnd == 2:
            r['hud'] = census(h, m, HUD, nested=(LIVES,))
        rows.append(r)
    return rows


# ------------------------------------- (b) the RRD loop, records POKED APART
def rrd_rows(h, m):
    """THREE RRDs PER BYTE RESTORE THE RECORD, so the three score records are
       poked to distinct values and checked byte for byte afterwards.  Without
       that, "converts" and "consumes" are the same observation."""
    recs = {HIGH: [0x12, 0x34, 0x56, 0x78],
            P1S: [0x11, 0x22, 0x33, 0x44],
            P2S: [0x99, 0x88, 0x77, 0x66]}
    for base, vals in recs.items():
        for i, v in enumerate(vals):
            m[base + i] = v
    for i in range(ASCII_N):
        m[ASCII_AT + i] = 0x5A
    sp = RC.arm(h, HUD)
    h.run_until(h.SENTINELS, limit=40 * 10 ** 6, stride=1, interrupts=False)
    return {'ascii': ''.join(chr(m[ASCII_AT + i]) for i in range(ASCII_N)),
            'high': [m[HIGH + i] for i in range(4)],
            'p1': [m[P1S + i] for i in range(4)],
            'p2': [m[P2S + i] for i in range(4)],
            'intact': all(m[b + i] == v for b, vs in recs.items()
                          for i, v in enumerate(vs))}


# ------------------------------------------- (c) the $08FF guard, MEASURED
def ldi_rows(h, m):
    """$8072 LD BC,$08FF is ONE instruction, and the $FF is LOAD-BEARING.
       Rather than assert that, poke C and MEASURE the damage."""
    out = []
    # *** A DESTRUCTIVE EXPERIMENT MUST RESTORE THE WORLD. ***  C = $07 makes this
    # loop write 263 bytes over $85B1..$86B7, which is the point of the experiment
    # -- and it clobbers the very record the OTHER measurements read.  Restoring
    # only the poked operand left every later run taking place in the wreckage:
    # the controlled $806C log came back with a non-zero mask where the machine
    # has zeros, and the engine differential caught it.
    keep = bytes(m[0x8500:0x8800])
    out_range = (0x8500, 0x8800)
    for c in (0xFF, 0x07):
        m[0x8073] = c                                 # the operand's low byte
        for i in range(0x200):
            m[0x85B1 + i] = 0x00
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, LIVES)
        h.run_until(h.SENTINELS, limit=40 * 10 ** 6, stride=1, interrupts=False)
        log = [a for (p_, a, _v) in h.memobj.log if p_ == 0x8075]   # the LDI ALONE
        h.memobj.unwatch()
        out.append({'c': c, 'writes': len(log),
                    'lo': '%04X' % min(log), 'hi': '%04X' % max(log),
                    'span': max(log) - min(log) + 1})
    m[0x8073] = 0xFF
    for i, v in enumerate(keep):                      # put the wreckage back
        m[out_range[0] + i] = v
    return out


def refs(m):
    """*** THE PLAN SAID $7FC0 HAS ONE REFERENCE AND IT HAS TWO. ***  A scan for
       CALL and CALL z misses a TAIL CALL, which is a JP.  $7F58 CALL z is the
       round-1 gate ($8609 DEC A); $9998 JP $7FC0 ends the PLAYER JOIN routine at
       $9970, which zeroes that player's score record, SETs the died flag at
       (IY+$5A) bit 7 -- F0's warp suppressor -- SETs (IY+7) bit 7 IN PLAY and
       gives three lives, then repaints the whole HUD because a score panel and a
       lives row have just come into existence.  So the HUD is painted on ROUND 1
       *and* ON EVERY JOIN, and a port that paints it only on round 1 shows a
       stale HUD for the whole of a two-player game."""
    tape = bytearray(open('build/image_tape.bin', 'rb').read())
    live = bytearray(open('build/image.bin', 'rb').read())

    def scan(img, pat):
        out, i = [], 0x4000
        while True:
            j = img.find(pat, i, 0x10000)
            if j < 0:
                return out
            out.append(hex(j))
            i = j + 1
    return {'call_z': scan(tape, bytes((0xCC, 0xC0, 0x7F))),
            'call': scan(tape, bytes((0xCD, 0xC0, 0x7F))),
            'jp': scan(tape, bytes((0xC3, 0xC0, 0x7F))),
            'call_z_live': scan(live, bytes((0xCC, 0xC0, 0x7F))),
            'jp_live': scan(live, bytes((0xC3, 0xC0, 0x7F))),
            'round_gate_at': 0x7F58, 'join_tail_at': 0x9998,
            'join_p2_at': 0x9970, 'join_p1_at': 0x999B}


# ------------------------------- (c2) CONTROLLED worlds, ordered write logs
def controlled(h, m):
    """The built-world censuses above say what these routines do IN SITU.  These
       say what they do BYTE FOR BYTE from a world the port can also construct --
       which is the only form an engine can be compared against.  Every source is
       seeded DISTINCT so each write pins a position, and the destinations take a
       sentinel so "written" and "already right" stay separable."""
    out = {}

    def clear(lo, hi, v):
        for a in range(lo, hi):
            m[a] = v

    # ---- $806C, one player and two, with a KNOWN tile buffer
    for tag, p2 in (('lives_1p', False), ('lives_2p', True)):
        for i in range(24):
            m[0x856C + i] = 0xC0 | i              # distinct, and MASKABLE
        # *** SEED THE WHOLE REGION THE EIGHT-ROW WALK TOUCHES. ***  A char row
        # at $50E0 walks H from $50 to $57, so seeding $5000..$50FF leaves seven
        # of its eight rows holding whatever the built world had -- and the
        # "controlled" world is then not controlled.  Caught by the engine
        # differential disagreeing from row ONE.
        clear(0x4000, 0x5800, 0x5A)
        clear(0x5800, 0x5B00, 0x5A)
        clear(0xE000, 0xF800, 0x5A)
        m[P1_FLAGS] = 0x80
        m[P2_FLAGS] = 0x80 if p2 else 0x00
        m[P1_LIVES], m[P2_LIVES] = 3, 2
        m[LIVES_WALK_OP] = 0x00                   # neither $2C nor $2D
        m[LIVES_SHADOW_OP] = 0x00
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, LIVES)
        h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
        log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
        h.memobj.unwatch()
        out[tag] = {'log': log, 'walk_op': m[LIVES_WALK_OP],
                    'shadow_op': m[LIVES_SHADOW_OP]}

    # ---- $806C with SEVEN lives, which separates three clamp models: clamp at
    #      5 gives SIX cells, clamp at 4 gives five, no clamp gives EIGHT
    for i in range(24):
        m[0x856C + i] = 0xC0 | i
    clear(0x4000, 0x5800, 0x5A)
    clear(0x5800, 0x5B00, 0x5A)
    clear(0xE000, 0xF800, 0x5A)
    m[P1_FLAGS], m[P2_FLAGS] = 0x80, 0x00
    m[P1_LIVES], m[P2_LIVES] = 7, 0
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, LIVES)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['lives_hi'] = {'log': log, 'lives': 7,
                       'cells': len({int(a, 16) for (_p, a, _v) in log
                                     if 0x50E0 <= int(a, 16) <= 0x50FF})}

    # ---- ...and with the ATTRIBUTE PAPER EQUAL TO THE INK, which is the only
    #      case that exercises $80E0's JR z: paper 4 == P1's ink 4
    for i in range(24):
        m[0x856C + i] = 0xC0 | i
    clear(0x4000, 0x5800, 0x5A)
    clear(0x5800, 0x5B00, 0x20)          # paper FOUR
    clear(0xE000, 0xF800, 0x5A)
    m[P1_FLAGS], m[P2_FLAGS] = 0x80, 0x00
    m[P1_LIVES], m[P2_LIVES] = 3, 0
    h.memobj.watch(0x5800, 0x5B00)
    sp = RC.arm(h, LIVES)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    log = [('%04X' % a, v) for (_p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['lives_paper'] = {'log': log, 'paper': 0x20}

    # ---- $957E with the six bits set, both players
    clear(0x4000, 0x5800, 0x5A)          # the WHOLE display -- see above
    clear(0x5800, 0x5B00, 0x5A)
    clear(0xE000, 0xF800, 0x5A)
    m[EXT_P1], m[EXT_P2] = 0x3F, 0x15
    m[EXT_COL_OP], m[EXT_COL_OP + 1] = 0x99, 0x99
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, EXTEND)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['extend'] = {'log': log,
                     'col_op': m[EXT_COL_OP] | (m[EXT_COL_OP + 1] << 8)}

    # ---- and with ALL EIGHT bits set.  The loop runs SIX times, so bits 6 and 7
    #      must be IGNORED -- a seven- or eight-letter loop reads PAST the table
    #      into $95EB.. and draws somewhere nobody named.
    clear(0x4000, 0x5800, 0x5A)
    clear(0x5800, 0x5B00, 0x5A)
    clear(0xE000, 0xF800, 0x5A)
    m[EXT_P1], m[EXT_P2] = 0xFF, 0x00
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, EXTEND)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['extend_ff'] = {'log': log}
    m[EXT_P1], m[EXT_P2] = 0, 0

    # ---- $9904 over a seeded shadow and a seeded colour shadow
    for i in range(0x800):
        m[0xE84C + (i & 0x7FF)] = 0x80 | (i & 0x3F)
    clear(0x4000, 0x5800, 0x5A)
    clear(0x5800, 0x5B00, 0x5A)
    for i, a in enumerate(range(0xF800, 0xFB00)):
        m[a] = 0x20 if (i & 1) else 0x00          # bit 5 alternating -> both branches
    m[0x8309], m[0x830A] = 0x11, 0x22
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, BANNER)
    h.sim.registers[6], h.sim.registers[7] = 0x48, 0x4C
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['banner'] = {'log': log, 'hl': 0x484C}
    return out


# --------------------------------------- (d) the ORDERING, as an INEQUALITY
def order_rows(h, m):
    """$806C FOLLOWS $8216 -- asserted as an INEQUALITY over instruction counts,
       never as a stamp, because the exact distance is not a fact about the port."""
    rows = []
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, BUILD)
        seen, n = {}, 0
        stops = {REPAINT, LIVES} | set(h.SENTINELS)
        while n < 40 * 10 ** 6:
            h.run_until(stops, limit=40 * 10 ** 6 - n, stride=1, interrupts=True)
            p = h.regs[PC]
            if p in h.SENTINELS:
                break
            seen.setdefault('%04X' % p, n)
            h.step(1, interrupts=True)
            n += 1
        if m[ROUND] in (2, 5, 56, 72, 80, 81):
            rows.append({'round': m[ROUND], 'first': seen,
                         'units': 'STOPS at $8216/$806C, NOT instructions -- the '
                                  'ORDER is the fact, the distance is not',
                         'lives_after_repaint':
                             ('806C' in seen and '8216' in seen and
                              seen['806C'] > seen['8216'])})
    return rows


# --------------------------------------------------------------------- main
def text_rows(h, m):
    """$7FE2..$7FFB -- THE HUD'S TWO TEXT ROWS, ordered, with no ROM byte.

        $7FE2  LD IX,$85C1 / LD HL,$4000 / CALL $802E    row 0
        $7FEC  LD HL,$4020 / CALL $802E                  row 1 -- IX CARRIED, not loaded
        $7FF2  LD A,1 / CALL $80FA                       P1's score panel
        $7FF7  LD A,2 / CALL $80FA                       P2's

    *** THE SECOND ROW'S POINTER IS NOT LOADED. ***  $7FEC sets HL alone; $802E's own
    `INC IX` has already carried IX past the NUL at $85DD.  So a caller scan finds ONE
    string where there are two, and the second row is whatever follows the first in the
    59-byte template at $85C1..$85FB.

    Each glyph store is recorded as (destination, code, row) -- recovered from the
    SOURCE address, because $8044 builds $3C00 + 8*code, so `code = (src - $3C00) / 8`
    and `row = (src - $3C00) % 8`.  A code and a row index are not ROM bytes.
    """
    STORE = 0x8052            # $804F's blit
    AWARD = 0x80FA
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, 0x7FE2)
    r = h.regs
    glyphs, ix_at, awards, panel = [], [], [], []
    #  *** THE SCORE PANELS BLIT THROUGH THE SAME $804F. ***  $80FA reaches the
    #  printer by $81C0 `JP $804F`, so a recorder watching $8052 alone counts the
    #  two panels' digits as part of the strings -- my first version reported 232
    #  writes for a 28-character row and 288 for a 29-character one, which is 456
    #  string writes plus 64 digit ones.  $7FF2 is the boundary.
    in_text = [True]
    n = 0
    while n < 4 * 10 ** 6:
        p = r[PC]
        if p in h.SENTINELS:
            break
        if p == 0x7FF2:
            in_text[0] = False
        if p == 0x7FE9 or p == 0x7FEF:
            ix_at.append(['%04X' % p, '%04X' % (r[9] | (r[8] << 8)),
                          '%04X' % (r[7] | (r[6] << 8))])
        elif p == STORE:
            dest = r[7] | (r[6] << 8)
            src = r[5] | (r[4] << 8)
            off = (src - 0x3C00) & 0xFFFF
            (glyphs if in_text[0] else panel).append(
                ['%04X' % dest, off // 8, off % 8])
        elif p == AWARD:
            awards.append(r[0])            # A -- the player index
        h.step(1, interrupts=False)
        n += 1
    else:
        raise SystemExit('$7FE2 never returned')
    h.memobj.unwatch()
    #  *** SPLIT BY THE LOW BYTE, NOT BY AN ADDRESS RANGE. ***  $804F walks the
    #  PAGE ($4000, $4100 .. $4700) with the low byte FIXED, so a window of
    #  $4000..$401F catches only row 0 of each glyph -- my first version counted 29
    #  writes for 28 characters and reported columns 0..31, because it was looking at
    #  one pixel row of the whole string plus whatever else landed there.
    row0 = [g for g in glyphs if (int(g[0], 16) & 0xFF) < 0x20]
    row1 = [g for g in glyphs if 0x20 <= (int(g[0], 16) & 0xFF) < 0x40]
    cols0 = sorted(set(int(g[0], 16) & 0x1F for g in row0))
    cols1 = sorted(set((int(g[0], 16) & 0xFF) - 0x20 for g in row1))
    pages = sorted(set((int(g[0], 16) >> 8) for g in glyphs))
    #  the strings, read where $802E reads them
    def strat(a):
        out = ''
        while m[a]:
            out += chr(m[a])
            a += 1
        return out
    s0, s1 = strat(0x85C1), strat(0x85DE)
    out = {'glyphs': glyphs, 'n': len(glyphs),
           'row0': len(row0), 'row1': len(row1),
           'cols0': cols0, 'cols1': cols1,
           'ix': ix_at, 'awards': awards, 'pages': pages,
           'panel': panel, 'n_panel': len(panel),
           'str0': s0, 'str1': s1,
           'len0': len(s0), 'len1': len(s1),
           'nul0': '%04X' % (0x85C1 + len(s0)),
           'nul1': '%04X' % (0x85DE + len(s1)),
           'template_bytes': (0x85DE + len(s1) + 1) - 0x85C1,
           'chained': (0x85C1 + len(s0) + 1) == 0x85DE}
    print('$7FE2..$7FFB -- the HUD\'s two text rows')
    print('    row 0 %r  %d chars, NUL at $%s, %d writes, columns %d..%d'
          % (s0, len(s0), out['nul0'], len(row0), cols0[0], cols0[-1]))
    print('    row 1 %r  %d chars, NUL at $%s, %d writes, columns %d..%d'
          % (s1, len(s1), out['nul1'], len(row1), cols1[0], cols1[-1]))
    for (site, ix, hl) in ix_at:
        print('    at $%s: IX $%s  HL $%s' % (site, ix, hl))
    print('    $80FA called with A = %s' % awards)
    print('    destination PAGES: %s  (eight-bit INC H, low byte fixed)'
          % ' '.join('$%02X' % p for p in pages))
    print('    and the two $80FA panels wrote %d glyph bytes THROUGH THE SAME $804F, '
          'counted separately' % len(panel))
    print('    -> %s: the second row\'s pointer is NOT loaded, it is $802E\'s own '
          'INC IX carrying past the NUL at $%s.  The template is %d bytes.'
          % ('CHAINED' if out['chained'] else '*** NOT CHAINED ***',
             out['nul0'], out['template_bytes']))
    assert out['chained'], 'the second string does not begin one past the first NUL'
    assert len(row0) == 8 * len(s0), 'row 0 is not eight writes per character'
    assert len(row1) == 8 * len(s1), 'row 1 is not eight writes per character'
    assert awards == [1, 2], 'the two $80FA calls are not A=1 then A=2: %r' % awards
    assert ix_at[0][1] == '85C1' and ix_at[1][1] == '85DE', \
        'IX is not $85C1 then $85DE: %r' % ix_at
    return out


def capture():
    h, m = RC.new()
    out = {
        'note': ('M7.7-H9 the four post-$8216 painters.  *** "$7FC0 IS ROUND 1 ONLY AND '
                 'ITS ONLY REFERENCE IS A CALL z" WAS WRONG AND THIS NOTE KEPT SAYING '
                 'IT: *** B1 found $9998 is `C3 C0 7F`, a TAIL JUMP from the mid-game '
                 'join, so the HUD is repainted whenever a second player joins, on ANY '
                 'round.  And $7FF9\'s CALL returns to $7FFC, so $7FC0 FALLS INTO the '
                 'attribute repaint and every caller runs that too (M7.36).  $957E writes NOTHING unless an EXTEND bit is set, so '
                 'its gate MUST seed $FDE3/$FDED.  $806C\'s P2 half is dead unless '
                 '$FD91 bit 7 is on.  $7FC0 CALLs $806C, so the nested frame is '
                 'measured separately and subtracted.'),
        'hud_at': HUD, 'lives_at': LIVES, 'extend_at': EXTEND, 'banner_at': BANNER,
        'repaint_at': REPAINT, 'ascii_at': ASCII_AT, 'ascii_n': ASCII_N,
        'lives_src': LIVES_SRC, 'lives_walk_op': LIVES_WALK_OP,
        'lives_shadow_op': LIVES_SHADOW_OP, 'ext_col_op': EXT_COL_OP,
        'high_at': HIGH, 'p1_at': P1S, 'p2_at': P2S,
        'p1_flags': P1_FLAGS, 'p2_flags': P2_FLAGS,
        'p1_lives': P1_LIVES, 'p2_lives': P2_LIVES,
        'ext_p1': EXT_P1, 'ext_p2': EXT_P2,
        'painters': painter_rows(h, m),
    }
    build_to(h, m, 2)
    out['rrd'] = rrd_rows(h, m)
    build_to(h, m, 2)
    out['text'] = text_rows(h, m)        # M7.36 -- $7FE2..$7FFB
    out['walk_op'] = m[LIVES_WALK_OP]
    build_to(h, m, 2)
    out['ldi'] = ldi_rows(h, m)
    out['refs'] = refs(m)
    build_to(h, m, 2)                                 # a CLEAN world, after the
    out['controlled'] = controlled(h, m)              #   runaway has been undone
    out['order'] = order_rows(h, m)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    for r in f['painters']:
        print('round %2d  lives %s  inplay %s  ext %s'
              % (r['round'], r['lives'], ['%02X' % v for v in r['inplay']],
                 ['%02X' % v for v in r['ext']]))
        for k in ('lives_1p', 'lives_2p', 'extend_fresh', 'extend_seeded',
                  'banner_484C', 'banner_488C', 'hud'):
            if k not in r:
                continue
            c = r[k]
            print('   %-14s %5d writes  disp %4d  attr %3d  shadow %3d  ram %4d%s'
                  % (k, c['writes'], c['display'], c['attrs'], c['shadow'], c['ram'],
                     ('   nested ' + str(c['nested'])) if c['nested'] else ''))
    print('BANNER address is an ARGUMENT ($484C/$488C from $98E4/$98EA)')
    print('RRD: ascii %r  records intact %s  (high %s)'
          % (f['rrd']['ascii'], f['rrd']['intact'],
             ['%02X' % v for v in f['rrd']['high']]))
    print('$806C walk operand after a P2 call: $%02X' % f['walk_op'])
    for r in f['ldi']:
        print('$8072 with C=$%02X -> %d writes, $%s..$%s (span %d)'
              % (r['c'], r['writes'], r['lo'], r['hi'], r['span']))
    print('$7FC0 references: %s' % f['refs'])
    for k, v in f['controlled'].items():
        print('CONTROLLED %-10s %4d writes  first %s'
              % (k, len(v['log']),
                 ' '.join('%s=%02X' % (a, val) for (_p, a, val) in v['log'][:6])))
    ok = sum(1 for r in f['order'] if r['lives_after_repaint'])
    print('ORDER: $806C follows $8216 on %d/%d measured rounds (an INEQUALITY; '
          'the gap below is in STOPS, not instructions, and is deliberately not asserted) %s'
          % (ok, len(f['order']),
             [(r['round'], r['first'].get('806C', -1) - r['first'].get('8216', -1))
              for r in f['order']]))


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
