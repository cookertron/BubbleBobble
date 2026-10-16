"""M7.7-I9 -- the corpse FALL $8B4E, the floor PROBE $8BB4, the LANDING $8B83.

THE PROBE, read from the bytes:
    $8B65  CALL $AED1 with E = X, D = Y+16   -> HL = the cell for (X, Y+16)
    $8B68  INC HL                            -> (X+8, Y+16)
    $8B6B  LD A,(HL) / AND $20               -> ONLY (X+8, Y+16) IS TESTED HERE.
           docs/M7.7-ITEMS-READING says "land only if (X,Y+16) OR (X+8,Y+16) is
           solid"; the left cell is never read on this path.  The case list
           below sets bit 5 in exactly one of the two and lets the machine say.
    $8B79  CALL $8BB4 twice.  Each call does ADD HL,$FFE0 -- one cell row UP --
           then tests that row's RIGHT cell and, if clear, its LEFT one.  So the
           two calls cover rows Y+8 and Y, both columns.
    LAND only if the floor cell is SOLID and all four body cells are AIR.
    "Embedded" (a body cell solid) means KEEP FALLING.

THE LANDING writes the fruit entry, and its TYPE comes from a THREE-BYTE
SELF-MODIFIED GENERATOR, one of which is an OPCODE:
    $8B9E  LD A,n    <- $8B9F is the COUNTER
    $8BA0  INC A     <- $8BA0 is the OPCODE, which $88E0 overwrites with $00
    $8BA1  AND n     <- $8BA2 is the MASK, which $88E0 widens to $FF
So types cycle 0..7 in LANDING ORDER, and after any of power-ups 7, 8 or 9 the
generator is pinned to a constant 9 and every later corpse drops a DIAMOND.
THAT CROSS-INCREMENT CASE IS BUILT HERE deliberately: I6 proved the pin writes
those bytes, I9 is where the generator runs, and neither gate alone would catch
the pair.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * `AND $F0` ON X at $8B98 is a NO-OP in every normal landing, because $8AF2
    already snapped X to a multiple of 16 when the fall began.  $8B4E is entered
    with bit 4 PRE-SET and X = $38, which was never snapped.
  * `AND $F8` ON Y at $8BAC is a no-op from an 8-aligned Y -- $8B83 is called
    with (IY+6) = $A6.
  * `OR 1` on byte1 is invisible if the entry already has its low bit set, so
    the whole table is seeded $FF, never 0.
  * `AND 7` on the type is a no-op for counter values 0..6, so $8B9F starts at
    $05 and the wrap happens inside the sweep.
  * THE ROUND RESET: from a snapshot where $8B9F is already $FF, "resets at
    round init" and "never resets" both give type 0 first.  A MID-CYCLE value is
    seeded and the FIRST landing must give value+1.
  * THE FREE-SLOT BASE: with an empty table, scanning from $9605 and from $9607
    both write something usable.  Entry 0 is left explicitly FREE and the write
    must go to $9607 with $9605 still $00.
  * THE PROBE vs A DISPLAY PROBE: a world that sets bit 5 AND paints pixels
    cannot tell them apart.  Bit 5 is set with NO pixels, and pixels are painted
    with bit 5 CLEAR, as separate cases.

Usage:  python tools/corpseland.py capture
        python tools/corpseland.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FALL = 0x8B4E
LAND = 0x8B83
PIN = 0x88E0
SLOT = 0xFD94
SHADOW = 0xF800
BLOCK = 0x9603
GEN, GEN_OP, GEN_MASK = 0x8B9F, 0x8BA0, 0x8BA2
FIXTURE = 'build/corpseland_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]
FIELDS = ['spr_lo', 'spr_hi', 'cy', 'cx', 'anim', 'x', 'y', 'flags', 'pack', 'state']


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, iy):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[10], r[11] = iy >> 8, iy & 0xFF
    r[PC] = addr
    return sp


def run(h, sp):
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


def cell(x, y):
    return (SHADOW + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)) & 0xFFFF


def clear_shadow(m):
    for a in range(SHADOW, SHADOW + 0x300):
        m[a] = 0x00


def slot(m):
    return {k: m[SLOT + i] for i, k in enumerate(FIELDS)}


# --------------------------------------------------------------- the probe
def probe_rows(h, m):
    """Which of the six cells actually decides.  Bit 5 is set with NO pixels
       painted, so a model probing the DISPLAY cannot agree by accident."""
    rows = []
    x, y = 0x50, 0x60
    names = {'floor_left': (x, y + 16), 'floor_right': (x + 8, y + 16),
             'body_left_8': (x, y + 8), 'body_right_8': (x + 8, y + 8),
             'body_left_0': (x, y), 'body_right_0': (x + 8, y),
             # ONE CELL ROW ABOVE the corpse.  $8BB4 is called exactly twice, so
             # this row is never read -- but it is CLEAR in every world above,
             # which makes "two body rows" and "three" the same function.
             'above_left': (x, y - 8), 'above_right': (x + 8, y - 8)}
    cases = [[], ['floor_left'], ['floor_right'], ['floor_left', 'floor_right'],
             ['floor_right', 'body_left_8'], ['floor_right', 'body_right_8'],
             ['floor_right', 'body_left_0'], ['floor_right', 'body_right_0'],
             ['floor_right', 'body_left_8', 'body_right_8',
              'body_left_0', 'body_right_0'],
             ['floor_right', 'above_left'], ['floor_right', 'above_right'],
             ['floor_left', 'above_left', 'above_right']]
    for case in cases:
        clear_shadow(m)
        for i in range(10):
            m[SLOT + i] = 0
        m[SLOT], m[SLOT + 1] = 0x60, 0xD3   # a FLIGHT frame, not $C700:
        # a world already holding $C700 cannot see the fall force it there
        m[SLOT + 5], m[SLOT + 6] = x, y
        m[SLOT + 7] = 0x9C                 # bit 7 alive, bit 4 the FALL phase
        m[SLOT + 9] = 0xFF
        m[SLOT + 4] = 0x10                 # well short of the 256-frame timeout
        m[SLOT + 8] = 0x5A                 # the packed byte NON-ZERO: zeroed from
                                           # an already-zero slot is invisible
        for i in range(0x40):
            m[BLOCK + i] = 0xFF            # so OR 1 and the free scan are visible
        for n in case:
            cx, cy = names[n]
            m[cell(cx, cy)] |= 0x20
        sp = arm(h, FALL, SLOT)
        run(h, sp)
        landed = (m[SLOT + 7] & 0x80) == 0
        rows.append({'set': case, 'landed': landed, 'y_after': m[SLOT + 6],
                     'slot': slot(m)})
    # ...and the converse: PIXELS painted with bit 5 CLEAR must not land
    clear_shadow(m)
    for i in range(10):
        m[SLOT + i] = 0
    m[SLOT], m[SLOT + 1] = 0x60, 0xD3   # a FLIGHT frame, not $C700:
    # a world already holding $C700 cannot see the fall force it there
    m[SLOT + 5], m[SLOT + 6] = x, y
    m[SLOT + 7] = 0x9C
    m[SLOT + 9] = 0xFF
    m[SLOT + 8] = 0x5A
    m[SLOT + 4] = 0x10                     # as the twelve cases above -- the
    for i in range(0x40):                  # gate compares all ten slot bytes
        m[BLOCK + i] = 0xFF
    for a in range(0x4000, 0x5800):
        m[a] = 0xFF
    sp = arm(h, FALL, SLOT)
    run(h, sp)
    rows.append({'set': ['PIXELS ONLY, bit 5 clear'],
                 'landed': (m[SLOT + 7] & 0x80) == 0,
                 'y_after': m[SLOT + 6], 'slot': slot(m)})
    return rows


def timeout_rows(h, m):
    """THE 256-FRAME TIMEOUT.  A fall from the top of the playfield is about 96
       frames at two pixels, so in play the counter never wraps and (IY+4) never
       exceeds a shimmer cursor's range.  With bit 5 clear EVERYWHERE the corpse
       can never land any other way, so the wrap is the only thing that ends the
       fall -- which is what separates "lands on the wrap to zero" from "lands at
       255", and a full eight-bit counter from a mod-3 one."""
    clear_shadow(m)
    for i in range(10):
        m[SLOT + i] = 0
    m[SLOT], m[SLOT + 1] = 0x60, 0xD3   # a FLIGHT frame, not $C700:
    # a world already holding $C700 cannot see the fall force it there
    m[SLOT + 5], m[SLOT + 6] = 0x50, 0x20
    m[SLOT + 7] = 0x9C
    m[SLOT + 9] = 0xFF
    m[SLOT + 8] = 0x5A
    m[SLOT + 4] = 0x00
    for i in range(0x40):
        m[BLOCK + i] = 0
    rows = []
    for f in range(260):
        sp = arm(h, FALL, SLOT)
        run(h, sp)
        landed = (m[SLOT + 7] & 0x80) == 0
        if f < 6 or f > 250 or landed:
            rows.append({'f': f, 'landed': landed, 'slot': slot(m)})
        if landed:
            break
    return rows


def dummy_rows(h, m):
    """$AED1 returns the $712F dummy for Y+16 < $18 -- above the HUD."""
    rows = []
    for y in (0x00, 0x02, 0x07, 0x08, 0x10):
        clear_shadow(m)
        # SET bit 5 in exactly the FLOOR row the unguarded path would read,
        # and in NOTHING else.  With the shadow clear up here, "the guard
        # returns the $712F dummy" and "there is no guard, and the cell happens
        # to be air" give the same answer, and $18 against $10 as the threshold
        # is equally invisible.  Seeding the body rows as well is no good
        # either: a solid body cell means EMBEDDED, so every height would fall
        # whatever the guard did.
        for xx in (0x50, 0x58):
            m[cell(xx, (y + 0x10) & 0xFF)] |= 0x20
        for i in range(10):
            m[SLOT + i] = 0
        m[SLOT], m[SLOT + 1] = 0x60, 0xD3   # a FLIGHT frame, not $C700:
        # a world already holding $C700 cannot see the fall force it there
        m[SLOT + 5], m[SLOT + 6] = 0x50, y
        m[SLOT + 7] = 0x9C
        m[SLOT + 9] = 0xFF
        m[SLOT + 8] = 0x5A
        sp = arm(h, FALL, SLOT)
        run(h, sp)
        rows.append({'y': y, 'y_after': m[SLOT + 6],
                     'landed': (m[SLOT + 7] & 0x80) == 0, 'slot': slot(m)})
    return rows


# ------------------------------------------------------- the type generator
def gen_rows(h, m, pinned=False):
    rows = []
    for i in range(0x40):
        m[BLOCK + i] = 0xFF
    for i in range(0x40):
        m[BLOCK + i] = 0
    m[BLOCK] = 0                                   # entry 0 explicitly FREE
    m[GEN], m[GEN_OP], m[GEN_MASK] = 0x05, 0x3C, 0x07   # MID-CYCLE, not $FF
    if pinned:
        sp = arm(h, PIN, SLOT)
        run(h, sp)
    for n in range(20):
        for i in range(10):
            m[SLOT + i] = 0
        m[SLOT + 5] = (0x38 + 16 * (n % 3)) & 0xFF     # NOT 16-aligned
        m[SLOT + 6] = (0xA6 - 8 * (n % 4)) & 0xFF      # NOT 8-aligned
        m[SLOT + 7] = 0x9C
        m[SLOT + 9] = 0xFF
        sp = arm(h, LAND, SLOT)
        run(h, sp)
        rows.append({'n': n, 'gen': m[GEN], 'gen_op': m[GEN_OP],
                     'gen_mask': m[GEN_MASK],
                     'block': [m[BLOCK + i] for i in range(0x40)],
                     'over': [m[0x9643], m[0x9644]],
                     'x': m[SLOT + 5], 'y': m[SLOT + 6],
                     'flags': m[SLOT + 7]})
    return rows


def slotscan_rows(h, m):
    """Which entry the scan chooses, and the unguarded overrun."""
    rows = []
    for (name, occupied) in (('entry 0 free, 1..4 taken', [1, 2, 3, 4]),
                             # ALL THIRTY-ONE fruit slots: 1..30 leaves entry 31
                             # free and the scan simply uses it, which is not the
                             # overrun at all.  The DJNZ counts $1E = 30 entries
                             # from $9607, so filling 1..31 is what pushes HL two
                             # bytes past the block.
                             ('all thirty-one taken', list(range(1, 32))),
                             ('entry 3 freed mid-run', [1, 2, 4, 5]),
                             # BYTE1 ZERO on every occupied entry.  "free means
                             # byte0 == 0" and "free means byte1 == 0" agree on
                             # every world where the two are seeded together.
                             ('occupied, byte1 zero', [2, 3, 4])):
        for i in range(0x40):
            m[BLOCK + i] = 0
        m[0x9643], m[0x9644] = 0xAA, 0xBB          # the two bytes PAST the block
        b1 = 0x00 if name.endswith('byte1 zero') else 0x88
        for e in occupied:
            m[BLOCK + 2 * e] = 0x70 | (e & 7)
            m[BLOCK + 2 * e + 1] = b1
        m[GEN], m[GEN_OP], m[GEN_MASK] = 0x05, 0x3C, 0x07
        for i in range(10):
            m[SLOT + i] = 0
        m[SLOT + 5], m[SLOT + 6] = 0x38, 0xA6
        m[SLOT + 7] = 0x9C
        m[SLOT + 9] = 0xFF
        sp = arm(h, LAND, SLOT)
        run(h, sp)
        rows.append({'name': name, 'occupied': occupied, 'b1': b1,
                     'block': [m[BLOCK + i] for i in range(0x40)],
                     'over': [m[0x9643], m[0x9644]]})
    return rows


def capture():
    h, m = new()
    fx = {'note': __doc__.strip(), 'fall_at': FALL, 'land_at': LAND,
          'pin_at': PIN, 'slot_at': SLOT, 'block_at': BLOCK, 'shadow_at': SHADOW,
          'gen_at': GEN, 'gen_op_at': GEN_OP, 'gen_mask_at': GEN_MASK,
          'fields': FIELDS,
          'probe': probe_rows(h, m), 'dummy': dummy_rows(h, m),
          'timeout': timeout_rows(h, m),
          'gen': gen_rows(h, m, False), 'gen_pinned': gen_rows(h, m, True),
          'slotscan': slotscan_rows(h, m)}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d probe rows, %d dummy, %d timeout, %d gen, %d pinned,'
          ' %d scan' % (FIXTURE, len(fx['probe']), len(fx['dummy']),
                        len(fx['timeout']), len(fx['gen']),
                        len(fx['gen_pinned']), len(fx['slotscan'])))
    t = fx['timeout'][-1]
    print('  the fall ended at frame %d, (IY+4) = %d, landed=%s'
          % (t['f'], t['slot']['anim'], t['landed']))


def verify():
    fx = json.load(open(FIXTURE))
    print('THE PROBE -- which cells decide:')
    for r in fx['probe']:
        print('   %-56s -> %s  (Y %d)' % (', '.join(r['set']) or '(nothing solid)',
              'LANDED' if r['landed'] else 'fell', r['y_after']))
    print()
    print('THE 256-FRAME TIMEOUT (bit 5 clear everywhere):')
    for r in fx['timeout'][-3:]:
        print('   frame %3d -> (IY+4) %3d  Y %3d  %s'
              % (r['f'], r['slot']['anim'], r['slot']['y'],
                 'LANDED' if r['landed'] else 'fell'))
    print()
    print('ABOVE THE HUD ($AED1 dummy for Y+16 < $18):')
    for r in fx['dummy']:
        print('   Y=%3d -> %3d  %s' % (r['y'], r['y_after'],
              'LANDED' if r['landed'] else 'fell'))
    print()
    print('THE TYPE GENERATOR, seeded MID-CYCLE at $05:')
    print('   free:  ', ' '.join(str(r['gen']) for r in fx['gen'][:12]))
    print('   pinned:', ' '.join(str(r['gen']) for r in fx['gen_pinned'][:12]))
    print()
    for r in fx['slotscan']:
        w = [i for i in range(32) if r['block'][2 * i] and i not in r['occupied']]
        print('   %-26s -> wrote entry %s, $9643/$9644 = $%02X $%02X'
              % (r['name'], w, r['over'][0], r['over'][1]))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
