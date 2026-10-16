"""M7.7-I2 -- the item UNPACK ($8779), the INK ($8728) and the DRAW ($A2C2/$A2D5).

THREE ROUTINES, captured by DIRECT CALL over a BUILT block:

  $8779  unpack an entry into the ten-byte draw record at $8903:
           $8908 := byte0 & $F0          the draw X
           $8909 := byte1 & $F8          the Y
           $8903/$8904 := $5D00 + index*32, and the INDEX comes from one of two
           places -- `type + 10` on the fruit pass, `$8639[type]` on the
           power-up pass, which jumps into the fruit path's own tail at $878C,
           so both share the *32 and differ only in the index.
  $8728  type -> ink -> the four attribute cells, then JP $A2C2.
  $A2C2  NOPs the two `OR (HL)` at $A307/$A30C, calls the 16x16 unmasked blit
         $A2D5, and restores $B6.  So the item blit is OPAQUE.

ONE TABLE, NOT TWO BANKS.  $8728 does `LD H,($872C) / DEC H / JR z` -- so a pass
flag of exactly 1 (the POWER-UP pass) indexes $861D directly, and anything else
adds $10 first.  The fruit pass therefore reads the HIGH half.  Getting this
backwards is invisible for types 0, 1 and 8, where the two halves agree.

WHAT THIS ORACLE REFUSES TO ASSUME (the equal-answers list):

  * BANK POLARITY.  $861D and $862D agree at exactly indices 0, 1 and 8, so a
    test driven by an ordinary banana can have the selection completely
    backwards and pass.  Every type is run through BOTH passes as a control
    pair, and the sweep includes type 10 ($FF vs $03), 5 (06 vs 07) and
    7 (05 vs 02).
  * THE INK WRITE IS INVISIBLE when the cell already holds that ink, and the
    round's own background colour $8309 is $46 -- ink 6, which several types
    also use.  All four cells are seeded to $FF, so the result $38|ink proves
    in one byte that paper survived, that BRIGHT and FLASH were cleared, and
    that a write happened at all.
  * OPAQUE vs OR IS INVISIBLE over blank background, and items sit on empty
    sky -- so the whole $A2C2 wrapper would test nothing.  Every draw case is
    run TWICE, with the 16x16 destination seeded $00 and $FF, and the two must
    produce byte-identical output.
  * THE $F0 vs $F8 MASK is identical for every type 0..7 and the drop generator
    only makes 0..7.  The sweep forces types >= 8.

THE BLIT PATCH BYTES ARE ASSERTED AFTER EVERY CALL.  $A2C2 NOPs $A307/$A30C and
restores them; a call that dies in between leaves them NOPped, and every later
OR-blit in the whole game silently turns opaque.  That would not show up here
at all -- it would show up as corrupted sprites three increments later.

WRITES ARE CAPTURED BY WATCHING MEMORY, not by predicting addresses: the
harness logs (PC, addr, value) for every write in range, so the fixture records
what the machine actually touched and a wrong address is a diff, not a miss.

SP IS PINNED PER CALL (TRAPS #42).

Usage:  python tools/itemdraw.py capture
        python tools/itemdraw.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

UNPACK  = 0x8779
INKDRAW = 0x8728
RNG_CP  = 0x8740          # the AND 7 straight after $873E LD A,R
REC     = 0x8903          # the ten-byte draw record
PASS    = 0x872C
INK_OP  = 0x8769          # the operand of $8768 OR n
PATCH   = (0xA307, 0xA30C)
SPR_AT, SPR_N = 0x5D00, 832
ENTRY   = 0x9605          # a real fruit slot to point HL at
FIXTURE = 'build/itemdraw_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

# the record's fields, by name, so a fixture row reads as something
RECF = {'spr_lo': 0x8903, 'spr_hi': 0x8904, 'X': 0x8908, 'Y': 0x8909}


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, hl=None):
    """IY MUST BE $8903.  The blit $A2D5 reads the draw record THROUGH IY
       (LD A,(IY+6) for the row, (IY)/(IY+1) for the sprite, (IY+5) for the
       column), and IY is loaded by $868D inside the WALK -- not by $8728 or
       $8779, which address the record absolutely.  Arming $8728 without it
       leaves a stale IY from the captured state, and the blit then reads
       somebody else's coordinates: the first version of this oracle blitted
       every case to $4041 regardless of Y, and still reported 96/96 agreement
       between its black and white runs, because being wrong in the same way
       twice is agreement.
    """
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[10], r[11] = REC >> 8, REC & 0xFF          # IYh, IYl
    if hl is not None:
        r[6], r[7] = hl >> 8, hl & 0xFF          # H, L
    r[PC] = addr


def run_call(h, trap_rng=False):
    """to a sentinel, collecting the $873E ink draw if it happens."""
    draws = []
    for _ in range(16):
        stops = ((RNG_CP,) if trap_rng else ()) + tuple(h.SENTINELS)
        h.run_until(stops, limit=10 ** 6, stride=1, interrupts=False)
        r = h.regs
        if trap_rng and r[PC] == RNG_CP:
            draws.append({'site': 0x873E, 'tag': 0, 'A': r[0] & 0x7F})
            h.step(1)
            continue
        break
    r = h.regs
    if r[PC] not in h.SENTINELS:
        raise SystemExit('never reached a sentinel -- PC $%04X' % r[PC])
    if h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('returned on the wrong sentinel -- the call ate its return')
    m = h.memobj.m
    for a in PATCH:
        if m[a] != 0xB6:
            raise SystemExit('$%04X left at $%02X, not $B6 -- the blit patch was not '
                             'restored, and every later OR-blit is now opaque' % (a, m[a]))
    return draws


# ------------------------------------------------------------------ part A
def unpack_rows(h, m):
    """$8779 over both passes.  byte0 swept whole, byte1 swept whole."""
    rows = []
    cases = []
    for b0 in range(256):
        cases.append((b0, 0x48))
    for b1 in range(256):
        cases.append((0x5A, b1))
    # and the corners that the sweeps above pin only one side of
    for b0, b1 in ((0x00, 0x00), (0xFF, 0xFF), (0x0F, 0x07), (0xF0, 0xF8)):
        cases.append((b0, b1))
    for pflag in (0, 1):
        for (b0, b1) in cases:
            m[ENTRY] = b0
            m[ENTRY + 1] = b1
            m[PASS] = pflag
            for a in RECF.values():
                m[a] = 0xEE                       # a seed neither pass produces
            arm(h, UNPACK, hl=ENTRY)
            run_call(h)
            rows.append({'b0': b0, 'b1': b1, 'pass': pflag,
                         'rec': {k: m[a] for k, a in RECF.items()}})
    return rows


# ------------------------------------------------------------------ part B
def draw_rows(h, m):
    """$8728: the ink lookup, the four attribute cells, and the opaque blit.

       Each case runs TWICE -- destination seeded $00 and $FF -- because over
       blank sky an opaque blit and an OR blit are the same function.
    """
    rows = []
    # A PASS FLAG OF 2.  $8728 does DEC H / JR z, so only EXACTLY 1 skips the
    # $10 offset -- but $8779 does OR A / JR nz, so anything non-zero takes the
    # power-up sprite.  A flag of 2 therefore gives the POWER-UP sprite with the
    # FRUIT ink, which is the only state that tells "exactly 1" apart from
    # "non-zero".  Unreachable in play (the walk only ever sets 0 then INCs to
    # 1), so it has to be built.
    for pflag in (0, 1, 2):
        for typ in range(16):
            # Y=$00 and Y=$10 are BOTH below $18, which is the only way to reach
            # two things that are otherwise dead: (a) $AEDC is $AED1 entered two
            # bytes later, WITHOUT its `CP $18` guard, so an item up here
            # computes a real shadow address where an enemy probe would get the
            # $712F dummy; and (b) rows 0 and 1 of the $FD00 table are $01FF, a
            # ROM address, so at Y=$00 the machine DROPS all 32 blit bytes and
            # the sprite simply vanishes while its four attribute cells still
            # get stamped.  Without these two positions both behaviours are
            # unreachable and a model that gets them wrong passes.
            for x, y in ((0x50, 0x48), (0x10, 0x18), (0xE0, 0xB8),
                         (0x30, 0x00), (0x70, 0x10)):
                pair = []
                for fill in (0x00, 0xFF):
                    m[ENTRY] = (x & 0xF0) | typ
                    m[ENTRY + 1] = (y & 0xF8) | 1
                    m[PASS] = pflag
                    # unpack first, exactly as $86B1 does
                    arm(h, UNPACK, hl=ENTRY)
                    run_call(h)
                    # Seed the WHOLE display, not a computed 16x16 window.  My
                    # first version computed the destination as
                    # 0x4000 + (y & $F8)*4 + (y & 7)<<8, which is the Spectrum's
                    # address only for the TOP THIRD -- so for Y=$48 and Y=$B8 it
                    # seeded bytes the blit never touches, and the black/white
                    # control then compared two identical unseeded screens and
                    # agreed 96 times out of 96 while proving nothing.  Filling
                    # the lot cannot miss, whatever the addressing.
                    for a in range(0x4000, 0x5800):
                        m[a] = fill
                    for a in range(0x5800, 0x5B40):   # PAST $5AFF: the bottom-row
                        # stamp spills, see the gate
                        m[a] = 0xFF
                    m[INK_OP] = 0xEE
                    h.memobj.watch(0x4000, 0x6000)
                    arm(h, INKDRAW, hl=ENTRY)
                    draws = run_call(h, trap_rng=True)
                    h.memobj.unwatch()
                    log = sorted(set((a, v) for _, a, v in h.memobj.log))
                    pair.append({'fill': fill, 'ink_op': m[INK_OP],
                                 'draws': draws,
                                 'writes': [[a, v] for a, v in log],
                                 'attrs': [m[0x5800 + (y >> 3) * 32 + (x >> 3) + c]
                                           for c in (0, 1, 32, 33)]})
                rows.append({'type': typ, 'pass': pflag, 'x': x, 'y': y,
                             'rec': {k: m[a] for k, a in RECF.items()},
                             'on_black': pair[0], 'on_white': pair[1]})
    return rows


def capture():
    h, m = new()
    unpack = unpack_rows(h, m)
    draw = draw_rows(h, m)
    fx = {'note': __doc__.strip(),
          'unpack_at': UNPACK, 'inkdraw_at': INKDRAW, 'rec_at': REC,
          'rec_fields': RECF, 'pass_at': PASS, 'ink_op_at': INK_OP,
          'patch_at': list(PATCH), 'entry_at': ENTRY,
          'ink_table': [m[0x861D + i] for i in range(32)],
          'remap': [m[0x8639 + i] for i in range(16)],
          'rowtab': [m[0xFD00 + i] for i in range(48)],
          'unpack': unpack, 'draw': draw}
    json.dump(fx, open(FIXTURE, 'w'))
    nw = sum(len(p['writes']) for r in draw for p in (r['on_black'], r['on_white']))
    nd = sum(len(p['draws']) for r in draw for p in (r['on_black'], r['on_white']))
    print('wrote %s: %d unpack rows, %d draw cases, %d writes, %d random-ink draws'
          % (FIXTURE, len(unpack), len(draw), nw, nd))
    same = sum(1 for r in draw if r['on_black']['writes'] == r['on_white']['writes'])
    print('  draw cases whose output is identical on black and on white: %d/%d'
          % (same, len(draw)))


def verify():
    fx = json.load(open(FIXTURE))
    U, D = fx['unpack'], fx['draw']
    print('ink table $861D:', ' '.join('%02X' % b for b in fx['ink_table'][:16]))
    print('          $862D:', ' '.join('%02X' % b for b in fx['ink_table'][16:]))
    agree = [i for i in range(16) if fx['ink_table'][i] == fx['ink_table'][16 + i]]
    print('  the two halves AGREE at indices %s -- a test using only those cannot '
          'tell the passes apart' % agree)
    print()
    print('type  fruit sprite   power sprite   fruit ink  power ink')
    for t in range(16):
        f = [r for r in U if r['pass'] == 0 and (r['b0'] & 0x0F) == t][0]
        p = [r for r in U if r['pass'] == 1 and (r['b0'] & 0x0F) == t][0]
        df = [r for r in D if r['pass'] == 0 and r['type'] == t][0]
        dp = [r for r in D if r['pass'] == 1 and r['type'] == t][0]
        print('  %2d   $%02X%02X          $%02X%02X           %02X         %02X'
              % (t, f['rec']['spr_hi'], f['rec']['spr_lo'],
                 p['rec']['spr_hi'], p['rec']['spr_lo'],
                 df['on_black']['ink_op'], dp['on_black']['ink_op']))
    print()
    nrand = sum(len(p['draws']) for r in D for p in (r['on_black'], r['on_white']))
    print('random-ink draws ($873E LD A,R):', nrand,
          '-- only reachable through $861D[10] = $FF, the power-up pass, type 10')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
