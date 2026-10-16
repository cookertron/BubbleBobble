# -*- coding: utf-8 -*-
"""M7.8-A -- THE ROUND BUILDER $7F62, and the composition $7F1B that drives it.

*** THE PORT'S ROUND ADVANCE PAINTS AN EMPTY BLACK SCREEN TODAY. ***  Measured
on the shipped page: after reset() the playfield has 0 of 704 invisible cells,
2,415 non-zero bitmap bytes, 2,247 non-zero platform-shadow bytes and 224 cells
carrying the drift bits.  After ONE roundAdvance(): 495 invisible, 0 bitmap, 0
shadow, 0 drift.  That is M7.3c's black screen one level up -- not in an asset
this time but in the engine -- and the M7.3c visibility gate cannot see it
because it runs only after reset().

AND THE ANSWER IS NOT AN ASSET.  A round's platform shadow IS NOT A FUNCTION OF
THE ROUND.  Measured here: the same round 20 built at different build-counter
phases differs in up to 2,083 of 6,144 shadow bytes; $83EC selects the tile
(five values in play, ten distinct shadows when poked out of band) and bit 7 of
the palette byte $82D7 selects a wall arm.  A faithful plate set is therefore
81 x 5 x 2 = 810 shadows, about 5 MB, against 768 bytes of Z80 over data the
port ALREADY SHIPS.  So the builder runs.

THE COMPOSITION, from build/image.bin:
  $7F1B  arms $9603..$9643 as LDI x32 + RET -- the scroll's blitter, written as
         DATA into bytes the round start later uses as the ITEM TABLE
  $7F2A  CALL $8207   the filler pattern (the ONE-ROUND LAG: $8584 gets the even
                      bytes of $856C BEFORE $830B refills it)
  $7F2D  CALL $7F62   THE BUILDER -- ten calls, no RET, falls into $7F80
  $7F33  round 1 SKIPS the scroll entirely
  $7F36  CALL $81E6 / $7F39 CALL $8404    separator + cascade
  $7F41  22 x ($840A scroll, $8447 push)
  $7F4E  CALL $8216   the repaint, which DISCARDS everything the scroll drew
  $7F51  CALL $7F80   the round number, a SECOND time
  $7F58  CALL z,$7FC0 round 1 only -- the score panel's RRD unpack
  $7F5B  CALL $806C   the lives icons
  $7F5E  CALL $854D   rows 2 and 23 DISPLAY -> SHADOW ($A000 + DE; the direction
                      is display to shadow, which docs/SPEC.md has right)

$81C3 is the one routine with no JS: LD HL,$F800 / CALL $81C9 / fall through
into $81C9 AGAIN, so the 9/4/6/4/9 CPL-alternating run happens TWICE -- 64 bytes
at $F800..$F83F, the collision map's two HUD rows.

Usage:  python tools/roundbuild.py            (capture the fixture)
        python tools/roundbuild.py verify     (print it back)
"""
import sys, json, zlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FIXTURE = 'build/roundbuild_fixture.json'
BRANCH_BYTE = 0x8DC4
BUILDER, COMPOSE = 0x7F62, 0x7F1B
ROUND, BUILD_A, BUILD_B = 0x8609, 0x82D7, 0x83EC
OPEN, SOLID = 0x8309, 0x830A
SHADOW, SHADOW_END = 0xE000, 0xF800
COLOUR, COLOUR_END = 0xF800, 0xFB00
DISPLAY, DISPLAY_END = 0x4000, 0x5B00
TILE_PTR, TILE_BUF, FILLER = 0x860C, 0x856C, 0x8584
ELEM_AT = 0x7E0E
CEILING, CEILING_END = 0xF800, 0xF840
ARM_LO, ARM_HI = 0x9603, 0x9644
SP_PIN = [0]

# the ten calls of $7F62, then the routines $7F1B adds around it
BUILDER_CALLS = [0x83EB, 0x82D6, 0x848C, 0x8390, 0x833A, 0x830B,
                 0x824A, 0x833A, 0x837A, 0x81C3, 0x7F80]
COMPOSE_CALLS = [0x8207, 0x7F62, 0x81E6, 0x8404, 0x840A, 0x8447,
                 0x8216, 0x7F80, 0x7FC0, 0x806C, 0x854D]
INNER = [0x81C9, 0x81E0, 0x8556, 0x8042, 0x7FAF, 0x82C5, 0x836A,
         0x837A, 0x83D9, 0x84D3, 0x850A, 0x8529, 0x9F5C]


def new(state='round1_48'):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP_PIN[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = SP_PIN[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def run(h, sp, limit=40 * 10 ** 6, interrupts=True):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=interrupts)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


def crc(bs):
    return zlib.crc32(bytes(bs)) & 0xFFFFFFFF


def seed(m, rnd, a, b):
    m[ROUND] = rnd
    m[BUILD_A] = a
    m[BUILD_B] = b


def build(h, m, rnd, a, b, entry=BUILDER, clear=True, stop=None,
          interrupts=True):
    """*** THE PLATFORM SHADOW IS AN INPUT TO THE BUILDER, AND THE CLOSURE TEST
       IS WHAT FOUND IT. ***  $824A merges with OR (HL), so building the same
       (round, $82D7, $83EC) from three different saved worlds gave THREE
       different shadows -- poking was not sampling and the oracle would have
       been invalid.  Zeroing $E000..$F7FF first makes it distinct = 1 on every
       row; zeroing the COLOUR shadow as well changes nothing, so that one is
       not an input.

       Zeroing here is FAITHFUL, not a fudge: $9858 is `LD HL,$E000 / LD C,$18 /
       CALL $AA49 / DEC C / JR nz` and $AA49 is `XOR A / LD (HL),A / INC HL /
       DJNZ`, a fill whose length is B FROM THE CALLER.  $9858 never sets B, so
       the clear is B + 23*256 bytes -- and MEASURED over 81 chained advances,
       B is 0 on all 81, which is 256 + 5888 = the whole 6,144.

       THE SHORT CLEARS ARE AN ARTEFACT OF THE ENTRY POINT, NOT A BEHAVIOUR.
       Arming at $9858 from a mid-play save gives B = 88 on round1_48 and 10 on
       r20_48 -- 5,976 and 5,898 bytes, leaving residue in the shadow's bottom
       sub-rows -- because B still held whatever the interrupted main loop left.
       Predicted and confirmed to the byte on four states.  A port that "fixed"
       shadowClear() to honour B would have been breaking a correct method to
       match a harness artefact.  TRAPS #94."""
    if clear:
        for x in range(SHADOW, SHADOW_END):            # $9858, B = 0
            m[x] = 0
    seed(m, rnd, a, b)
    sp = arm(h, entry)
    if stop is not None:
        h.run_until((stop,), limit=40 * 10 ** 6, stride=1, interrupts=interrupts)
        if h.regs[PC] != stop:
            raise SystemExit('never reached $%04X' % stop)
        return
    run(h, sp, interrupts=interrupts)


# *** THE TWO DECLARED GAPS, AS AN ADDRESS SET RATHER THAN A HAND-WAVE. ***
# The live sequence diverges from the machine on exactly these shadow bytes and
# no others, so the gate masks them, compares everything else byte for byte, and
# ALSO asserts the unmasked comparison still fails -- a mask nobody checks is a
# way to pass.
#   $E140..$E741 column 0/1  the round-number glyph (ROM font, declared)
#   $F0E0..$F7E4 columns 0-4 the lives icons ($806C, a counted stub)
#  *** THE LIVES HALF OF THIS MASK IS GONE, M7.10. ***  $806C was a counted
#  stub, so row 23 columns 0..4 had to be excluded; livesIcons() is wired now
#  and MEASURED to match the machine, so the mask is ONLY the glyph and the
#  gate is strictly stronger: the live sequence diverges on SIX bytes where it
#  used to diverge on about twenty-five, and round 1 on NONE at all.
DECLARED_MASK = set()
for _k in range(8):
    DECLARED_MASK.add(0xE140 + 0x100 * _k)
    DECLARED_MASK.add(0xE141 + 0x100 * _k)


def masked(m):
    b = bytearray(m[SHADOW:SHADOW_END])
    for a in DECLARED_MASK:
        b[a - SHADOW] = 0
    return bytes(b)


def snap(m):
    """THE PER-ROW CRC, not one whole-buffer checksum.  A single CRC over 6,144
       bytes tells a failing gate nothing about WHERE; twenty-two row CRCs name
       the row.  The colour shadow is only 768 bytes, so it ships whole."""
    rows = [crc(m[SHADOW + 0x40 + 256 * r: SHADOW + 0x40 + 256 * (r + 1)])
            for r in range(22)]
    return {'shadow_crc': crc(m[SHADOW:SHADOW_END]), 'shadow_rows': rows,
            # the SAME mask the live-sequence gate uses, so a compose row can be
            # compared with the two declared gaps excluded and the raw CRC kept
            # beside it to prove the mask is not simply a way to pass
            'masked_crc': crc(masked(m)),
            'colour': list(m[COLOUR:COLOUR_END]),
            'open': m[OPEN], 'solid': m[SOLID],
            'build_a': m[BUILD_A], 'build_b': m[BUILD_B],
            'tile_ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8),
            'tile_buf': list(m[TILE_BUF:TILE_BUF + 24]),
            'filler': list(m[FILLER:FILLER + 8]),
            'display_crc': crc(m[DISPLAY:DISPLAY_END])}


# ---------------------------------------------- (a) the executing closure
def phase_closure():
    """WHICH ROUTINES ACTUALLY RUN, counted by stopping on them -- not inferred
       from a static walk.  Four of the twenty-two do NOT run on every build,
       so 'every one executes on every build' is false and is recorded as false."""
    out = {}
    for rnd, a, b in ((1, 0, 0), (2, 1, 1), (5, 2, 2), (20, 1, 1), (81, 4, 4)):
        h, m = new()
        seed(m, rnd, a, b)
        sp = arm(h, BUILDER)
        targets = set(BUILDER_CALLS) | set(INNER) | set(h.SENTINELS)
        hits, total = {}, 0
        while total < 40 * 10 ** 6:
            h.run_until(targets, limit=40 * 10 ** 6, stride=1, interrupts=True)
            p = h.regs[PC]
            if p in h.SENTINELS:
                break
            hits[p] = hits.get(p, 0) + 1
            h.step(1, interrupts=True)
            total += 1
        out[str(rnd)] = {('%04X' % k): v for k, v in sorted(hits.items())}
    every = sorted(set.intersection(*[set(v) for v in out.values()]))
    some = sorted(set.union(*[set(v) for v in out.values()]) - set(every))
    return {'per_round': out, 'on_every_build': every, 'not_on_every_build': some}


# ------------------------------------------------------- (b) $81C3, the ceiling
def phase_ceiling():
    """$81C3 IS TWO PASSES, and that is the whole subtlety: `LD HL,$F800 /
       CALL $81C9` and then it FALLS THROUGH into $81C9 a second time.  One pass
       writes 32 bytes; the routine writes 64.  The run lengths are 9,4,6,4,9 and
       $81E0's CPL fires ONCE per group, so the values alternate $FF,$00,$FF,$00,
       $FF from A = 0."""
    h, m = new()
    for a in range(CEILING, CEILING_END):
        m[a] = 0x5A                       # poison: neither $00 nor $FF
    h.memobj.watch(CEILING - 0x40, COLOUR_END)
    sp = arm(h, 0x81C3)
    run(h, sp)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    pcs = {}
    for (p, ad, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
    got = list(m[CEILING:CEILING_END])
    runs = []
    for v in got:
        if runs and runs[-1][0] == v:
            runs[-1][1] += 1
        else:
            runs.append([v, 1])
    return {'writes': len(log), 'writer_pcs': pcs,
            'bytes': got, 'runs': [[('%02X' % v), n] for v, n in runs],
            'outside_ceiling': sum(1 for (_, ad, _) in log
                                   if not (CEILING <= ad < CEILING_END)),
            'poison_survivors': sum(1 for v in got if v == 0x5A)}


# --------------------------------------------- (c) the composition, in order
def phase_compose():
    """THE ORDERED CALL TRACE of $7F1B, on a round that scrolls and one that
       does not.  Round 1 takes $7F34's JR z and skips $81E6/$8404/$840A/$8447
       entirely, and is the ONLY round that calls $7FC0."""
    out = {}
    for rnd, a, b in ((1, 0, 0), (2, 1, 1), (20, 1, 1)):
        h, m = new()
        seed(m, rnd, a, b)
        sp = arm(h, COMPOSE)
        targets = set(COMPOSE_CALLS) | set(h.SENTINELS)
        seq, counts, total = [], {}, 0
        while total < 60 * 10 ** 6:
            h.run_until(targets, limit=60 * 10 ** 6, stride=1, interrupts=True)
            p = h.regs[PC]
            if p in h.SENTINELS:
                break
            k = '%04X' % p
            counts[k] = counts.get(k, 0) + 1
            if len(seq) < 40:
                seq.append(k)
            h.step(1, interrupts=True)
            total += 1
        out[str(rnd)] = {'first_40': seq, 'counts': counts}
    return out


# ------------------------------------- (d) $9603: the code/data alias
def phase_alias():
    """*** TWO THINGS LIVE AT $9603 AND THE ORDER DECIDES WHICH. ***  $7F1B's
       head writes $ED,$A0 thirty-two times plus $C9 -- LDI x32 / RET, the
       scroll's blitter, as SELF-MODIFIED CODE.  The port's itemRoundBuild()
       clears the SAME 64 bytes as the item table.  Watched across one WHOLE
       round start ($9858), in order, with the writer PCs named."""
    h, m = new()
    seed(m, 2, 1, 1)
    h.memobj.watch(ARM_LO, ARM_HI)
    sp = arm(h, 0x9858)
    run(h, sp, limit=200 * 10 ** 6)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    phases, last = [], None
    for (p, ad, v) in log:
        k = '%04X' % p
        if k != last:
            phases.append([k, 0])
            last = k
        phases[-1][1] += 1
    return {'writes': len(log), 'phases': phases,
            'final': list(m[ARM_LO:ARM_HI]),
            'armed_as_code': list(m[ARM_LO:ARM_LO + 4]) == [0xED, 0xA0, 0xED, 0xA0],
            'ends_with_ret': m[ARM_HI - 1] == 0xC9}


# ------------------------------- (d2) $9858's CLEAR, and the B that is not there
def phase_clear():
    """THE NEGATIVE THAT SAVED A CORRECT METHOD.  $9858's clear length is B from
       the caller and $9858 never sets B.  Measured two ways, because the two
       disagree and only one of them is the game:
         * armed at $9858 from a mid-play SAVE, B is whatever the interrupted
           main loop left -- 88 and 10 on round1_48 and r20_48, clearing 5,976
           and 5,898 of 6,144 and leaving residue in the bottom sub-rows;
         * driven through the REAL advance ($97F8, correctly seeded chain), B is
           0 on all 81 rounds, so the clear is the whole 6,144 every time.
       The port's shadowClear() is therefore right, and a port that "fixed" it
       to honour B would be matching a harness artefact."""
    from skoolkit.simutils import REGISTERS
    BREG = REGISTERS['B']
    import roundclass as rc
    armed = {}
    for st in ('round1_48', 'r20_48', 'r50_48', 'play1p48'):
        h, m = new(st)
        sp = arm(h, 0x9858)
        h.run_until((0xAA49,), limit=10 ** 7, stride=1, interrupts=False)
        b = h.sim.registers[BREG]
        h.run_until((COMPOSE,), limit=200 * 10 ** 6, stride=1, interrupts=False)
        armed[st] = {'B': b, 'predicted': (b or 256) + 23 * 256,
                     'survivors': sum(1 for x in range(SHADOW, SHADOW_END) if m[x])}
    h, m = rc.new('round1_48')
    rc.suppress_warp(m)
    m[rc.ROUND] = 0; m[rc.BUILD_A] = 0; m[rc.BUILD_B] = 0
    chained = {}
    for _ in range(81):
        rc.seed_round(m); rc.suppress_warp(m)
        sp = rc.arm(h, rc.ADVANCE)
        h.run_until((0x9858,), limit=200 * 10 ** 6, stride=1, interrupts=True)
        h.run_until((0xAA49,), limit=10 ** 7, stride=1, interrupts=True)
        b = h.sim.registers[BREG]
        rc.run(h, sp)
        chained[str(b)] = chained.get(str(b), 0) + 1
    return {'armed_from_save': armed, 'chained_B_histogram': chained,
            'real_advance_always_full': list(chained) == ['0'] and
                                        chained['0'] == 81}


# ------------------------------------- (e) IS THE INPUT SET CLOSED?
def phase_closed():
    """THE CLOSURE TEST, and the reason the oracle may poke at all.  If the
       builder's output is a function of ($8609, $82D7, $83EC) ALONE, then the
       same triple built from two DIFFERENT base worlds must give the same
       shadow.  If it is not, poking is not sampling and the whole oracle is
       invalid.  Driven from three shipped states whose other state differs."""
    rows = []
    for rnd, a, b in ((2, 1, 1), (20, 1, 1), (50, 3, 3), (81, 4, 4)):
        seen, unclear = {}, {}
        for st in ('round1_48', 'r20_48', 'r50_48'):
            h, m = new(st)
            build(h, m, rnd, a, b)
            s = snap(m)
            seen[st] = (s['shadow_crc'], crc(s['colour']), s['open'], s['solid'])
            h2, m2 = new(st)                     # ...and WITHOUT $9858's clear
            build(h2, m2, rnd, a, b, clear=False)
            unclear[st] = crc(m2[SHADOW:SHADOW_END])
        rows.append({'round': rnd, 'a': a, 'b': b,
                     'distinct': len(set(seen.values())),
                     'distinct_unclear': len(set(unclear.values())),
                     'per_state': {k: list(v) for k, v in seen.items()}})
    return {'rows': rows,
            'closed': all(r['distinct'] == 1 for r in rows),
            'open_without_the_clear': all(r['distinct_unclear'] == 3
                                          for r in rows)}


# --------------------------------------------------- (f) the oracle itself
#  The covering set is chosen so every ARM of the builder is driven, not so the
#  rounds look tidy: both record classes (SHORT 39-byte and LONG 77-byte, by
#  $8543's bitmap), both wall arms (palette bit 7 clear on index 0 only), all
#  five in-play tile indices, the round-1 skip, the round-81 no-digit path, and
#  $860C == 0.
#  *** AND "PALETTE BIT 7 IS CLEAR ON INDEX 0 ALONE" WAS FALSE. ***  $858C holds
#  17 95 8C 8D A6 9E A5 8E 96 9C 0F 9D 9F 8F 94 -- bit 7 is clear at index 0
#  ($17) AND at index 10 ($0F), which is used on rounds 11, 26, 41, 56 and 71.
#  The first covering set ran $82D7 only over 0..4, so ten of the fifteen
#  palette bytes were never selected and the $860C = 0 wall arm was driven
#  through index 0 alone.  (10, 2) and (13, 3) are added because index 10 and
#  index 13 give the SAME open/solid pair $47/$4F with DIFFERENT $860C, so the
#  two rows separate the wall arm from the attributes -- which no row did.
COVER = [(1, 0, 0), (1, 1, 1), (2, 1, 1), (2, 2, 2), (3, 2, 2), (5, 4, 4),
         (5, 0, 0), (11, 1, 1), (20, 1, 1), (20, 4, 4), (36, 2, 2),
         (50, 3, 3), (56, 0, 0), (69, 3, 3), (72, 1, 1), (80, 4, 4),
         (81, 4, 4), (81, 0, 0),
         (20, 10, 2), (20, 13, 3), (11, 10, 1), (26, 9, 4), (41, 14, 0)]


def phase_oracle():
    """Each row is captured TWICE: at the BUILDER's exit ($7F62, which falls
       through $7F80 and returns) and at the COMPOSITION's exit ($7F1B).  The
       two differ by the scroll, the repaint, the lives and $854D -- and a gate
       that only has the second cannot tell a missing builder from a missing
       repaint, because $8216 copies the shadow over the display either way."""
    rows = []
    for (rnd, a, b) in COVER:
        h, m = new()
        build(h, m, rnd, a, b, entry=BUILDER)
        at_builder = snap(m)
        # ...and again, stopped at $7F7D -- AFTER $81C3 and BEFORE the fall-through
        # into $7F80.  The round-number glyph is the port's DECLARED HUD-font
        # departure ($8042 indexes the ROM charset at $3C00, which is not shipped),
        # so the builder proper is compared byte-exact here and the six glyph bytes
        # are gated separately as the boundary they are.
        h3, m3 = new()
        build(h3, m3, rnd, a, b, entry=BUILDER, stop=0x7F80)
        at_predigits = snap(m3)
        # *** THE COMPOSITION IS CAPTURED WITH INTERRUPTS OFF, AND THAT IS A
        # DECLARED BOUNDARY, NOT A CONVENIENCE. ***  $7F1B contains no HALT, so
        # on the real machine the 50 Hz ISR fires DURING the scroll and draws
        # entities into the display -- and $854D then copies display rows 2 and
        # 23 back into the shadow, so an ISR sprite that lands in row 2 becomes
        # part of the built background.  MEASURED: with interrupts on it lands
        # on 1 of 23 covering rows (round 81 at $82D7 = 4, two bytes $E747 and
        # $E748, written $E0/$07 by $8562 out of a display the ISR had just
        # touched).  The port runs no ISR inside roundBuild(), so comparing
        # against an interrupts-on capture would be asserting a behaviour it
        # does not model.  The ISR's reach into the round build belongs to the
        # scroll/ISR increment and is recorded here, with its 1-in-23 rate.
        h2, m2 = new()
        build(h2, m2, rnd, a, b, entry=COMPOSE, interrupts=False)
        at_compose = snap(m2)
        h4, m4 = new()
        build(h4, m4, rnd, a, b, entry=COMPOSE, interrupts=True)
        at_compose_isr = snap(m4)
        rows.append({'round': rnd, 'a': a, 'b': b,
                     'builder': at_builder, 'predigits': at_predigits,
                     'compose': at_compose,
                     'compose_isr_crc': at_compose_isr['shadow_crc'],
                     'isr_changed_the_build':
                         at_compose_isr['shadow_crc'] != at_compose['shadow_crc']})
    return rows


def phase_anchor():
    """ONE FULL PLATE, byte for byte, so the gate is not only CRCs.  Round 1 at
       the new-game phase is the anchor because it is the one the shipped
       round1_48 state reproduces exactly."""
    h, m = new()
    build(h, m, 1, 0, 0, entry=BUILDER, stop=0x7F80)
    import base64
    return {'round': 1, 'a': 0, 'b': 0,
            'shadow_b64': base64.b64encode(bytes(m[SHADOW:SHADOW_END])).decode(),
            'colour_b64': base64.b64encode(bytes(m[COLOUR:COLOUR_END])).decode()}


def phase_digits():
    """THE DECLARED HUD-FONT DEPARTURE, MEASURED AS A BYTE LIST rather than
       waved at.  $7F80 draws the round number through $8042, which indexes the
       Spectrum ROM charset at $3C00 -- 7 reads below round 10, 14 from 10 -- and
       this port ships no ROM, so BB_DIGITS substitutes.  The difference is
       therefore EXACTLY the glyph, and here is its extent: the addresses $7F80
       changes, on rounds that take each arm."""
    out = {}
    for rnd in (1, 2, 11, 81):
        h, m = new()
        build(h, m, rnd, 0, 0, entry=BUILDER, stop=0x7F80)
        before = bytes(m[SHADOW:SHADOW_END])
        sp = arm(h, 0x7F80)
        run(h, sp)
        after = bytes(m[SHADOW:SHADOW_END])
        out[str(rnd)] = {
            'changed': ['%04X' % (SHADOW + i) for i in range(len(before))
                        if before[i] != after[i]],
            'rom_reads': True}
    return out


def phase_sequence():
    """*** THE GATE THAT WOULD HAVE CAUGHT ($83EC), AND DID NOT EXIST. ***

       The 18-row differential SEEDS all three inputs before every row, so it
       tested the builder against POKED TRIPLES and never against the sequence
       the port itself generates.  The port sat at ($82D7, $83EC) = (1, 0) -- a
       pair the machine is never in -- and built every round on the PREVIOUS
       round's tile while all 18 rows stayed green.

       This is the machine's own SEQUENCE: a new game ($8609 = $82D7 = $83EC =
       0, as $96FA..$9701 leave it), then N chained CALL $97F8, recording what
       each round LEAVES.  The engine side drives roundAdvance() the same number
       of times from reset() and must agree row for row.  Nothing is poked."""
    import roundclass as rc
    h, m = rc.new('round1_48')
    rc.suppress_warp(m)
    m[rc.ROUND] = 0
    m[rc.BUILD_A] = 0
    m[rc.BUILD_B] = 0
    rows = []
    for _ in range(24):
        # NOT rc.seed_round(m) here: that poisons ($7E0E) with the $EE sentinel
        # before every build, which is right for the census's written/not-written
        # question and WRONG for a sequence that must show what a real game
        # carries.  Round 81 inherits round 80's class because $7C89 returns.
        rc.suppress_warp(m)
        sp = rc.arm(h, rc.ADVANCE)
        rc.run(h, sp)
        rows.append({'round': m[ROUND], 'build_a': m[BUILD_A], 'build_b': m[BUILD_B],
                     'open': m[OPEN], 'solid': m[SOLID],
                     'tile_ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8),
                     'shadow_crc': crc(m[SHADOW:SHADOW_END]),
                     'masked_crc': crc(masked(m)),
                     # the COLOUR shadow, which the drift painter owns: bits 6/7
                     # are the per-round wind and the port wiped them on every
                     # advance until $7C57..$7E4A was wired
                     'colour_crc': crc(m[COLOUR:COLOUR_END]),
                     'drift67': sum(1 for a in range(COLOUR, COLOUR_END)
                                    if m[a] & 0xC0),
                     'elem': m[ELEM_AT],
                     'tile_buf': list(m[TILE_BUF:TILE_BUF + 24])})
    return {'rows': rows,
            'invariant': all(r['build_b'] == r['build_a'] % 5 for r in rows),
            'mask': ['%04X' % a for a in sorted(DECLARED_MASK)],
            'mask_why': {
                'glyph': 'the ROUND NUMBER, $7F80 through $8042 -- the DECLARED '
                         'ROM-font departure, since $8042 indexes the Spectrum '
                         'charset at $3C00 and no ROM is shipped',
                'lives': 'CLOSED by M7.10 -- $806C is wired and the row is no '
                         'longer masked'},
            'note': 'from a NEW GAME, nothing poked; $83EC == $82D7 mod 5 on every row'}


def phase_rowsto():
    """$854D ON ITS OWN, because in the composed path it is INVISIBLE.  After
       $8216 the display rows already equal the shadow, so $854D writes back
       identical bytes and changes nothing -- an adversarial pass replaced its
       whole body with a counter bump and the suite stayed green.  So drive it
       against a POISONED display, where every byte it copies is observable."""
    out = {}
    for poison in (0x5A, 0xA5):
        h, m = new()
        for x in range(0x4000, 0x5B00):
            m[x] = poison
        before = bytes(m[SHADOW:COLOUR_END])
        sp = arm(h, 0x854D)
        run(h, sp)
        after = bytes(m[SHADOW:COLOUR_END])
        ch = [i for i in range(len(before)) if before[i] != after[i]]
        out['%02X' % poison] = {
            'changed': len(ch),
            'lo': '%04X' % (SHADOW + ch[0]), 'hi': '%04X' % (SHADOW + ch[-1]),
            'rows': sorted(set((SHADOW + i) >> 8 for i in ch)),
            'all_poison': all(after[i] == poison for i in ch)}
    return out


def phase_hud():
    """$7FC0 IS A WHOLE HUD ROUTINE AND THE PORT MODELS ONLY ITS RRD LOOP.
       $7F58 CALL z,$7FC0 fires on round 1, and $7FC0's tail -- $7FD7 clearing
       64 attribute bytes, $7FDF CALL $806C, $7FE2 LD IX,$85C1 with two CALL
       $802E and two CALL $80FA -- is why the machine's trace counts $806C TWICE
       on round 1 and the engine once.  Measured extent, so the boundary has a
       magnitude instead of a shrug."""
    h, m = new()
    for x in range(SHADOW, SHADOW_END):
        m[x] = 0
    seed(m, 1, 0, 0)
    h.memobj.watch(0x4000, COLOUR_END)
    sp = arm(h, 0x7FC0)
    run(h, sp, interrupts=False)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    zones, pcs = {}, {}
    for (pcv, a, v) in log:
        pcs['%04X' % pcv] = pcs.get('%04X' % pcv, 0) + 1
        if 0x4000 <= a < 0x5800:
            z = 'display_bitmap'
        elif 0x5800 <= a < 0x5B00:
            z = 'attributes'
        elif SHADOW <= a < SHADOW_END:
            z = 'shadow'
        else:
            z = 'other'
        zones[z] = zones.get(z, 0) + 1
    return {'writes': len(log), 'zones': zones,
            'calls_806C': pcs.get('806C', 0),
            'top_pcs': dict(sorted(pcs.items(), key=lambda kv: -kv[1])[:8]),
            'modelled': 'the RRD loop $7FC0..$7FD5 only'}


def phase_extent():
    """THE BUILDER'S WRITE EXTENT AS AN ADDRESS SET, because a boundary check
       that names four ranges leaves everything between them unguarded: a
       mutation adding `ram[0x9000] = 0xFF` to ceiling() survived a battery,
       and the same scribble at $7000 was caught only because $7000 happens to
       fall inside the round records.  This is the whole 64K, measured."""
    out = {}
    for name, entry in (('builder', BUILDER), ('compose', COMPOSE)):
        sets = []
        for rnd, a, b in ((2, 1, 1), (20, 1, 1), (81, 4, 4)):
            h, m = new()
            for x in range(SHADOW, SHADOW_END):
                m[x] = 0
            seed(m, rnd, a, b)
            # *** THE EXTENT IS WHAT THE MACHINE **WRITES**, NOT WHAT IT
            # CHANGES. ***  A before/after diff misses a write that stores the
            # value already there -- $860E is written by $8400 on every build
            # and changed on none of them -- so a port writing a DIFFERENT value
            # there would look like it had scribbled outside the extent.  The
            # watch records every store.
            before = bytes(m[0:0x10000])
            h.memobj.watch(0x4000, 0x10000)
            sp = arm(h, entry)
            run(h, sp, limit=200 * 10 ** 6, interrupts=False)
            written = set(a for (_, a, _) in h.memobj.log)
            h.memobj.unwatch()
            after = bytes(m[0:0x10000])
            sets.append(written |
                        set(i for i in range(0x10000) if before[i] != after[i]))
        union = sorted(set().union(*sets))
        runs = []
        for a_ in union:
            if runs and a_ == runs[-1][1] + 1:
                runs[-1][1] = a_
            else:
                runs.append([a_, a_])
        out[name] = {'addresses': len(union),
                     'method': 'WRITE-WATCH over $4000..$FFFF unioned with a '
                               'whole-64K before/after diff; the watch is the '
                               'point, because a store of the value already '
                               'there changes nothing and is still a write',
                     'ranges': [['%04X' % lo, '%04X' % hi] for lo, hi in runs],
                     'rounds': [2, 20, 81]}
    return out


# ------------------------------------------------------- (g) the negatives
def phase_negatives():
    """WHAT THE BUILDER DOES NOT TOUCH.  Paired with the positives above so the
       gate states a boundary rather than asserting only what changes: the
       entity table, the spawn records, the tile PATTERNS and the round records
       must all come out byte-identical."""
    NEG = {'entities': (0xFD80, 0xFDEE), 'records': (0x7491, 0x7990),
           'tiles': (0x6180, 0x61A8), 'rounddata': (0x61A8, 0x7491),
           'palette': (0x858C, 0x859B)}
    out = {}
    for rnd, a, b in ((2, 1, 1), (20, 1, 1), (81, 4, 4)):
        h, m = new()
        seed(m, rnd, a, b)
        before = {k: bytes(m[lo:hi]) for k, (lo, hi) in NEG.items()}
        sp = arm(h, BUILDER)
        run(h, sp)
        out[str(rnd)] = {k: sum(1 for x, y in zip(before[k], bytes(m[lo:hi]))
                                if x != y)
                         for k, (lo, hi) in NEG.items()}
    return out


def capture():
    fx = {'note': __doc__.strip(), 'builder_at': BUILDER, 'compose_at': COMPOSE,
          'builder_calls': ['%04X' % a for a in BUILDER_CALLS],
          'compose_calls': ['%04X' % a for a in COMPOSE_CALLS],
          'cover': [list(c) for c in COVER],
          'closure': phase_closure(), 'ceiling': phase_ceiling(),
          'compose': phase_compose(), 'alias': phase_alias(),
          'clear': phase_clear(), 'closed': phase_closed(), 'oracle': phase_oracle(),
          'anchor': phase_anchor(), 'digits': phase_digits(), 'sequence': phase_sequence(),
          'rowsto': phase_rowsto(), 'hud': phase_hud(), 'extent': phase_extent(), 'negatives': phase_negatives()}
    json.dump(fx, open(FIXTURE, 'w'), sort_keys=True)
    print('wrote %s: %d oracle rows, closure on %d rounds, ceiling %d writes'
          % (FIXTURE, len(fx['oracle']), len(fx['closure']['per_round']),
             fx['ceiling']['writes']))
    return fx


def verify(fx=None):
    fx = fx or json.load(open(FIXTURE))
    c = fx['ceiling']
    print('\n$81C3 THE CEILING: %d writes from %s, %d outside $F800..$F83F, '
          '%d poison survivors\n   runs: %s'
          % (c['writes'], sorted(c['writer_pcs']), c['outside_ceiling'],
             c['poison_survivors'], c['runs']))
    cl = fx['closure']
    print('\nCLOSURE: on every build %s\n   NOT on every build %s'
          % (cl['on_every_build'], cl['not_on_every_build']))
    print('\nCOMPOSITION counts: ' + '; '.join(
        '%s -> %s' % (r, v['counts']) for r, v in sorted(fx['compose'].items())))
    a = fx['alias']
    print('\n$9603 ALIAS: %d writes, armed_as_code=%s ends_with_ret=%s\n   %s'
          % (a['writes'], a['armed_as_code'], a['ends_with_ret'], a['phases']))
    print('\nINPUT SET CLOSED: %s  %s'
          % (fx['closed']['closed'],
             [(r['round'], r['distinct']) for r in fx['closed']['rows']]))
    print('\nNEGATIVES: %s' % fx['negatives'])
    print('\nORACLE rows: %d' % len(fx['oracle']))
    for r in fx['oracle'][:6]:
        print('   r%-3d a=%d b=%d  build shadow %08X open/solid $%02X/$%02X'
              ' | compose shadow %08X'
              % (r['round'], r['a'], r['b'], r['builder']['shadow_crc'],
                 r['builder']['open'], r['builder']['solid'],
                 r['compose']['shadow_crc']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        verify(capture())
    else:
        verify()
