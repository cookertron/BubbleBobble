"""M7.7-I8 -- CORPSE BIRTH $8BC2 and FLIGHT $8A78-$8B4D.

BIRTH.  $8BC2 turns a dying enemy into a corpse: DEC ($AA5F), CALL $8C51 (the
enemy's final repaint), sprite := $C700, (IY+9) := $FF, and then THREE RNG USES
FROM TWO DRAWS:

    $8BD7  draw 1 & 7, + 8      -> the LOW nibble of (IY+8), 8..15
    $8BDF  draw 2 & 3, + 1, x16 -> the HIGH nibble of (IY+8), 1..4
    $8BF1  RR H                 -> bit 0 of the LFSR's H AFTER the second draw
                                   becomes bit 0 of (IY+7), the X DIRECTION

That third use is not a draw.  It reads the generator's internal H, which is
$FE87 once $FE91 has stored HL back, so the engine can take it from RAM --
but a model that draws a THIRD time, or hard-codes the direction, agrees with
the machine on about half of all seeds.  Sixteen seeds are swept and bit 0 is
compared ROW BY ROW, never in aggregate.

FLIGHT.  $8A78 runs only when (IY+9) == $FF, and $8A7D CALL $BF0A does not
return -- it falls through into $BF16 -- so every frame begins "erase me where I
am".  ($FEC6) parity then splits the frame: ODD frames redraw and nothing else.

On an EVEN frame: the 3-frame shimmer cursor (IY+4) picks $C700 / $D340 /
$D360; Y steps +8 with a wrap to $00 at $C0, or -8 with a wrap to $B8 on
borrow; then the packed (IY+8) is serviced.  Its LOW nibble counts down, and
when it runs out the leg ends -- rising legs take a fresh low nibble and SET
bit 1, descending legs SET bit 4 (the fall), zero (IY+4), clamp X to [$10,$E0],
AND $F0, and RET at $8AF7 WITHOUT DRAWING.
The X step is h' * 8 where h' is the old high nibble minus one, or a FRESH
draw of 1..4 when the high nibble had reached 1.  Crossing $10 or $E0 clamps
AND calls $8B45, which XORs bit 0 of (IY+7) -- the corpse bounces.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THE PARITY GATE.  Calling $8A78 always from the same ($FEC6) parity hides
    the whole odd-frame path, so the sweep ALTERNATES and asserts odd frames
    change nothing but the display.
  * THE Y WRAPS.  Only reachable if a bob happens to cross $C0 or 0, so they
    are forced: (+6) = $BC rising must give $00 (NOT $C0 and not $B8), and
    (+6) = $04 falling must give $B8.
  * THE X CLAMP AND FLIP, forced by putting a corpse at the edge with the
    largest step.
  * (IY+4)'s DOUBLE ROLE.  In flight it is a 0/1/2 cursor; in the fall it is a
    full 8-bit counter.  A model keeping the mod-3 wrap agrees on every frame
    but the 256th -- and the captured dumps settle it independently
    (candy_image slot 3 holds $0E, fruit_image $1D, both impossible for a
    0/1/2 cursor).
  * THE NO-DRAW FRAME at $8AF7 -- one frame per corpse, invisible unless the
    display writes are counted.
  * THE $AA5F DECREMENT: seeded to $7F, never 0, and read as an exact delta.

SP IS PINNED PER CALL: $8BC2 nests $8C51 -> $A447 and $8A78 nests
$BF0A -> $BF16 -> $A447.

Usage:  python tools/corpse.py capture
        python tools/corpse.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

BIRTH = 0x8BC2
FLIGHT = 0x8A78
SLOT = 0xFD94              # entity slot 2
PARITY = 0xFEC6
ALIVE = 0xAA5F
PRNG = 0xFE86
FIXTURE = 'build/corpse_fixture.json'
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


def disp_ck(m):
    """A checksum of the play area.  The slot fields alone cannot see the erase
       at all -- $BF0A's fall-through into $BF16 writes only the SCREEN -- so
       three separate mutations of it survived a battery that compared only
       state.  This is what makes them observable."""
    ck = 0
    for a in range(0x4000, 0x5800):
        ck = ((ck * 33) ^ m[a]) & 0xFFFFFFFF
    return ck


def run(h, sp, watch=False):
    if watch:
        h.memobj.watch(0x4000, 0x5B00)
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    if watch:
        h.memobj.unwatch()
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))
    return len(h.memobj.log) if watch else 0


def slot(m):
    return {k: m[SLOT + i] for i, k in enumerate(FIELDS)}


def lfsr_twice(l, hh):
    """$FE85 twice in Python, so the third use -- bit 0 of H after the SECOND
       call -- can be predicted independently of the machine."""
    for _ in range(2):
        a = ((hh << 1) | (hh >> 7)) & 0xFF
        a ^= l
        a = (a + 0xFE) & 0xFF
        hh = a
        a = ((a >> 1) | (a << 7)) & 0xFF
        a ^= l
        l = a
    return l, hh


def birth_rows(h, m):
    rows = []
    for seed in range(16):
        lo, hi = (seed * 37 + 11) & 0xFF, (seed * 91 + 5) & 0xFF
        m[PRNG], m[PRNG + 1] = lo, hi
        m[ALIVE] = 0x7F                       # never 0, so the delta is exact
        for i, k in enumerate(FIELDS):
            m[SLOT + i] = 0xEE
        # BIT 3 SET in both, so `AND $F8` and `AND $F0` give DIFFERENT answers.
        # With $55/$66 they agree, and the mask is untestable.
        m[SLOT + 5], m[SLOT + 6] = 0x5C, 0x6E
        m[SLOT + 7] = 0xC1                        # a plausible live-enemy flag byte
        predicted = lfsr_twice(lo, hi)
        sp = arm(h, BIRTH, SLOT)
        run(h, sp)
        rows.append({'seed': seed, 'prng_in': [lo, hi],
                     'prng_out': [m[PRNG], m[PRNG + 1]],
                     'predicted_h': predicted[1],
                     'alive': m[ALIVE], 'slot': slot(m),
                     'a5d9': m[0xA5D9], 'a480': m[0xA480]})
    return rows


def flight_rows(h, m):
    """$8A78 frame by frame, ALTERNATING the parity, over several seeded corpses
       chosen to reach the wraps and the clamp."""
    runs = []
    cases = [
        ('mid-screen, rising',   0x78, 0x60, 0x8C, 0x29, 0),
        ('mid-screen, falling',  0x78, 0x60, 0x8E, 0x29, 0),
        ('Y wrap UP at $C0',     0x78, 0xBC, 0x8E, 0x19, 0),
        ('Y wrap DOWN past 0',   0x78, 0x04, 0x8C, 0x19, 0),
        # X=20 with a step of 24 does NOT reach the left clamp: ADD A,(IY+5) is
        # EIGHT BIT, so 20 - 24 wraps to 252, which is above $E0 and takes the
        # RIGHT clamp instead.  A corpse stepping off the left edge reappears
        # clamped at the right.  X=30 with the same step lands on 6, in range,
        # and is the only way to reach $8B31.
        ('X wraps left into the RIGHT clamp', 0x14, 0x60, 0x4C, 0x48, 0),
        ('X clamp at the left, no wrap',      0x1E, 0x60, 0x4C, 0x48, 0),
        ('X clamp at the right', 0xDC, 0x60, 0x4D, 0x48, 0),
        ('leg runs out at once', 0x78, 0x60, 0x8D, 0x10, 0),
    ]
    for (name, x, y, flags, pack, par0) in cases:
        for i, k in enumerate(FIELDS):
            m[SLOT + i] = 0
        m[SLOT] , m[SLOT + 1] = 0x00, 0xC7
        m[SLOT + 5], m[SLOT + 6] = x, y
        m[SLOT + 7] = flags
        m[SLOT + 8] = pack
        m[SLOT + 9] = 0xFF
        m[PRNG], m[PRNG + 1] = 0xF3, 0xD8
        # TRAPS #40: an erase that repaints what is already there shows nothing.
        # The play area is filled with a pattern neither the erase nor the draw
        # can reproduce, so both become visible in the checksum.
        for a in range(0x4000, 0x5800):
            m[a] = (a * 7 + 0x5A) & 0xFF
            # ...and the SHADOW it restores from, with a DIFFERENT pattern, so
            # "restore the shadow" and "leave the display alone" cannot agree.
            m[(a + 0xA000) & 0xFFFF] = (a * 13 + 0xA5) & 0xFF
        frames = []
        for f in range(40):
            m[PARITY] = (par0 + f) & 0xFF
            sp = arm(h, FLIGHT, SLOT)
            n = run(h, sp, watch=True)
            frames.append({'f': f, 'parity': m[PARITY] & 1,
                           'slot': slot(m), 'writes': n, 'ck': disp_ck(m),
                           'prng': [m[PRNG], m[PRNG + 1]]})
        runs.append({'name': name, 'x': x, 'y': y, 'flags': flags,
                     'pack': pack, 'frames': frames})
    return runs


def capture():
    h, m = new()
    b = birth_rows(h, m)
    f = flight_rows(h, m)
    fx = {'note': __doc__.strip(), 'birth_at': BIRTH, 'flight_at': FLIGHT,
          'slot_at': SLOT, 'parity_at': PARITY, 'alive_at': ALIVE,
          'prng_at': PRNG, 'fields': FIELDS, 'birth': b, 'flight': f}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d births, %d flight runs x %d frames'
          % (FIXTURE, len(b), len(f), len(f[0]['frames'])))
    ok = sum(1 for r in b if (r['slot']['flags'] & 1) == (r['predicted_h'] & 1))
    print('  bit 0 of (+7) == bit 0 of the predicted LFSR H: %d/%d' % (ok, len(b)))
    print('  (+7) values: %s' % sorted(set(r['slot']['flags'] for r in b)))
    print('  $AA5F 127 -> %s' % sorted(set(r['alive'] for r in b)))


def verify():
    fx = json.load(open(FIXTURE))
    print('BIRTH -- three uses from two draws:')
    for r in fx['birth'][:6]:
        p = r['slot']['pack']
        print('   seed %2d  (+8) = $%02X  low %2d high %d   (+7) = $%02X  dir %d  '
              'predicted H bit0 %d'
              % (r['seed'], p, p & 15, p >> 4, r['slot']['flags'],
                 r['slot']['flags'] & 1, r['predicted_h'] & 1))
    print()
    for run in fx['flight']:
        print('%s  (x=%d y=%d flags=$%02X pack=$%02X)'
              % (run['name'], run['x'], run['y'], run['flags'], run['pack']))
        for fr in run['frames'][:9]:
            s = fr['slot']
            print('    f%-2d par%d  x=%3d y=%3d anim=%d flags=$%02X pack=$%02X  %2d writes'
                  % (fr['f'], fr['parity'], s['x'], s['y'], s['anim'],
                     s['flags'], s['pack'], fr['writes']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
