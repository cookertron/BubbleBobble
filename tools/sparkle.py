"""M7.7-I10 -- the $5CE0 BURST-SPARKLE engine ($C002), read from the bytes.

    $C002  LD IY,$C05E     the FAKE TEN-BYTE ENTITY RECORD -- +0/+1 sprite,
                           +5 X ($C063), +6 Y ($C064).  $A2D5 and $A314 both
                           read their subject THROUGH IY, so one pair of
                           blitters serves seven subsystems.
    $C006  LD HL,$5CE0 / LD B,14
    $C00B  LD A,(HL) / AND 7 / JR z,$C050        FREE means (byte0 & 7) == 0,
                                                 NOT byte0 == 0 -- an expired
                                                 slot KEEPS ITS X BITS.
    $C010  LD ($C04A),HL                         SELF-MOD: the operand of the
                                                 $C049 LD DE,nn that writes the
                                                 slot back at $C04C.
    $C013  LD DE,$C048 / $C016 LDI               copies byte0 to $C048 -- which
                                                 is the OPERAND of $C047 LD A,n.
                                                 THE LDI DECREMENTS THE 16-BIT
                                                 BC, so a serviced slot whose
                                                 X & $F8 is 0 leaves C == 0 for
                                                 the NEXT LDI, which borrows and
                                                 DECREMENTS B.  The walk is not
                                                 a clean fourteen iterations.
    $C019  LD A,(HL) / AND $F8 -> $C064          Y, MASKED (so Y & 7 is always 0
                                                 through this engine, and
                                                 $A314's third band is dead).
    $C020  LD A,(DE) / AND $F8 / LD C,A / -> $C063   X bits, and C for the LDI.
    $C027  LD A,(DE) / AND 7 / INC A / AND 7 / OR C / LD (DE),A   phase+1 mod 8.
    $C02F  AND 7 / JR z,$C055                    new phase 0 -> ERASE, and the
                                                 slot is written back with
                                                 (byte0 & 7) == 0, i.e. FREED.
    $C033  CP 2 / JR z,$C055                     new phase 2 -> ERASE (and it
                                                 does NOT expire: $C055 rejoins
                                                 at $C047 and writes back live).
    $C037  EXX / LD HL,$CAA0 / JR c,$C040 / LD HL,$CA80 / LD ($C05E),HL
           CALL $A2D5 / EXX                      OR-draw.
    $C047  LD A,n  <- $C048, the packed byte
    $C049  LD DE,nn <- $C04A, this slot
    $C04C  LD (DE),A / DJNZ $C00B / RET

$CAA0 AND THE JR c AT $C03B ARE DEAD BY CONSTRUCTION.  Carry at $C03B comes only
from CP 2, so it needs a NEW phase of 1, which needs an OLD phase of 0, which
$C00E skips.  A gate written to observe $CAA0 drawn can only ever fail; this
oracle asserts the NEGATIVE -- over the whole sweep $C05E/$C05F is never $CAA0.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THE IDEMPOTENT OR.  Phases 3..7 OR THE SAME sprite into THE SAME cells with
    no erase between, so "draws once", "draws three times" and "draws five
    times" give a BYTE-IDENTICAL screen.  Every pass is captured SEPARATELY and
    the per-pass table byte -- the only thing that actually moves -- is gated.
  * THE PHASE-2 ERASE LOOKS LIKE A NO-OP in play, because the pop has just run
    $BF0A -> $BF16 and restored that area.  The display is DIRTIED with a
    pattern that is in neither the shadow nor the sprite before every call.
  * ERASE FROM A ZERO SHADOW.  "Copy the shadow back" and "write zeros" agree if
    the shadow is $00, so the shadow is seeded NEVER-ZERO and DIFFERENT from the
    display at every address (display XOR $5A).
  * THE FREE-SLOT TEST.  In a freshly cleared table `(byte0 & 7) == 0` and
    `byte0 == 0` agree everywhere.  They diverge only after a particle has
    EXPIRED, so a full lifetime is run first and the SAME slot must be reused.
  * SLOT ORDER.  With one live particle, "walk all fourteen" and "walk only the
    active one" agree -- so one case runs FOURTEEN distinct live particles and
    gates the ORDERED write log.
  * THE OPAQUE PATCH.  $A2C2 NOPs $A307/$A30C for the ITEM blit and restores
    them; $C002 calls $A2D5 DIRECTLY, so it ORs.  Over a BLACK destination OR
    and store are the same function, so the destination is never black.

Usage:  python tools/sparkle.py capture
        python tools/sparkle.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

SPARK, POP = 0xC002, 0xB6D8
TABLE, NSLOT = 0x5CE0, 14
REC = 0xC05E                      # the fake entity record: +0/+1, +5, +6
PACK, PTR = 0xC048, 0xC04A        # the two self-modified operands
BUBBLE = 0xFED8                   # bubble pool slot 0
SHADOW_OFF = 0xA000
FIXTURE = 'build/sparkle_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    if 0x4000 <= SP0[0] < 0x6000:
        raise SystemExit('SP $%04X is inside the write watch' % SP0[0])
    return h, m


def arm(h, addr, iy, bc=None):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[10], r[11] = iy >> 8, iy & 0xFF
    r[PC] = addr
    if bc is not None:
        r[2], r[3] = bc >> 8, bc & 0xFF        # B, C
    return sp


def run(h, sp):
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


def pat(a):
    """Never zero, and different at neighbouring addresses."""
    return ((a * 31) & 0xFF) | 0x01


def seed_screen(m):
    """The display gets a never-zero pattern; the shadow gets that pattern XOR
       $5A, so it is never zero either and NEVER EQUAL to the display.  A model
       that leaves the cell alone, one that writes zero and one that copies the
       shadow all give three different answers."""
    for d in range(0x4000, 0x5800):
        p = pat(d)
        m[d] = p
        m[d + SHADOW_OFF] = p ^ 0x5A
    for a in range(0x5800, 0x5B00):
        m[a] = 0x47


def clear_table(m):
    for i in range(2 * NSLOT):
        m[TABLE + i] = 0


def seed_rec(m):
    """Seed the RECORD and both SELF-MODIFIED OPERANDS to recognisable values
       that are NOT what the pass writes (TRAPS #44): a world that already holds
       the answer cannot show the write.  +0/+1 are left at zero so that only a
       DRAW can set the sprite, which is how $CAA0 is asserted unreachable."""
    m[PACK] = 0xA5
    m[PTR], m[PTR + 1] = 0x34, 0x12
    for i, v in enumerate((0x00, 0x00, 0x11, 0x22, 0x33, 0xA5, 0x5A, 0x66, 0x77, 0x88)):
        m[REC + i] = v


def snap(m):
    return {'table': [m[TABLE + i] for i in range(2 * NSLOT)],
            'rec': [m[REC + i] for i in range(10)],
            'spr': (m[REC + 1] << 8) | m[REC],
            'pack': m[PACK], 'ptr': (m[PTR + 1] << 8) | m[PTR]}


LOOP_TOP = 0xC00B         # $C00B -- the loop top; $C04D DJNZ is its only back edge


def run_counting(h, sp):
    """`run`, but stepping so the LOOP TOP can be counted.

    The count is the thing the fixture never carried.  B is loaded 14 once, and
    $C016's LDI decrements the SAME B a second time, so a serviced slot whose X
    bits are $00 makes the DJNZ wrap and the walk runs on past the table -- which
    `bc` row 3 has been reporting as a pixel count all along."""
    n, iters = 0, 0
    r = h.regs
    while n < 4 * 10 ** 6:
        p = r[PC]
        if p in h.SENTINELS:
            break
        if p == LOOP_TOP:
            iters += 1
        h.step(1, interrupts=False)
        n += 1
    else:
        raise SystemExit('$C002 never returned in 4M steps')
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))
    return iters


def call_spark(h, m, bc=0x0E01):
    """One pass of $C002, with BC set EXPLICITLY: C is a LIVE INPUT to the LDI."""
    h.memobj.watch(0x4000, 0x6000)
    sp = arm(h, SPARK, REC, bc)
    iters = run_counting(h, sp)
    h.memobj.unwatch()
    log = [(a, v) for (_p, a, v) in h.memobj.log]
    out = snap(m)
    out['writes'] = log
    out['pix'] = len([1 for (a, _v) in log if a < 0x5800])
    out['attr'] = len([1 for (a, _v) in log if 0x5800 <= a < 0x5B00])
    out['tab'] = len([1 for (a, _v) in log if TABLE <= a < TABLE + 2 * NSLOT])
    out['iters'] = iters
    out['ptr_out'] = not (TABLE <= out['ptr'] < TABLE + 2 * NSLOT)
    return out


# ------------------------------------------------------------ the phase sweep
def phase_rows(h, m):
    """Every OLD phase 0..7 in slot 0, one pass each, over a dirtied screen."""
    rows = []
    x, y = 0x50, 0x61            # Y is RAW and deliberately NOT 8-aligned
    for p in range(8):
        seed_screen(m)
        clear_table(m)
        seed_rec(m)
        m[TABLE] = (x & 0xF8) | p
        m[TABLE + 1] = y
        r = call_spark(h, m)
        r['old_phase'] = p
        rows.append(r)
    return rows


def life_rows(h, m):
    """A full lifetime from the phase the POP seeds (1), captured after EVERY
       single pass -- because phases 3..7 OR the same sprite into the same cells
       and the finished screen cannot tell one draw from five."""
    seed_screen(m)
    clear_table(m)
    seed_rec(m)
    x, y = 0x50, 0x61
    m[TABLE] = (x & 0xF8) | 1
    m[TABLE + 1] = y
    rows = []
    for n in range(9):
        r = call_spark(h, m)
        r['n'] = n
        rows.append(r)
    return rows


def order_rows(h, m):
    """FOURTEEN distinct live particles: with one, "walk all fourteen" and "walk
       only the active one" are the same function."""
    seed_screen(m)
    clear_table(m)
    seed_rec(m)
    for s in range(NSLOT):
        m[TABLE + 2 * s] = ((0x20 + 8 * s) & 0xF8) | (3 + (s % 5))
        m[TABLE + 2 * s + 1] = 0x30 + 8 * (s % 9)
    return [call_spark(h, m)]


def bc_rows(h, m):
    """THE LDI's BC.  C entering the LDI is the PREVIOUS serviced slot's X & $F8
       (or the caller's C for the first).  When it is zero the decrement borrows
       and B loses one, so the walk is SHORT -- or, with enough such slots, B
       passes zero, WRAPS, and the walk leaves the table entirely.  Neither
       arrangement can occur in a captured world.

       *** ROW 3 IS THE RUNAWAY AND THIS FILE DID NOT SAY SO. ***  It reported
       pix = 4256 against row 1's 448 -- 133 sprite draws from fourteen seeded
       slots -- and ptr = $603C, 320 bytes past the table.  `iters` now counts
       it: 431 against 14.  A number the fixture already held, in a form that
       needed dividing to see."""
    rows = []
    for (name, c, xbase) in (('caller C = 1, X >= 8', 0x01, 0x20),
                             ('caller C = 0, X >= 8', 0x00, 0x20),
                             ('caller C = 1, every X < 8', 0x01, 0x00)):
        seed_screen(m)
        clear_table(m)
        seed_rec(m)
        for s in range(NSLOT):
            m[TABLE + 2 * s] = ((xbase + (8 * s if xbase else 0)) & 0xF8) | 3
            m[TABLE + 2 * s + 1] = 0x30 + 8 * (s % 9)
        r = call_spark(h, m, bc=0x0E00 | c)
        r['name'] = name
        r['advanced'] = [i for i in range(NSLOT)
                         if (m[TABLE + 2 * i] & 7) != 3]
        rows.append(r)
    return rows


# ------------------------------------------------------------- the POP seeding
def pop(h, m, x, y):
    for i in range(10):
        m[BUBBLE + i] = 0
    m[BUBBLE], m[BUBBLE + 1] = 0x80, 0xC7
    m[BUBBLE + 5], m[BUBBLE + 6] = x, y
    m[BUBBLE + 7] = 0x84                 # bit 7 alive, bit 2 = the POP flag
    m[BUBBLE + 9] = 0x01
    sp = arm(h, POP, BUBBLE)
    run(h, sp)


def seed_rows(h, m):
    rows = []
    for y in (0x0F, 0x10, 0x11, 0x80, 0xAE, 0xAF, 0xB0, 0xFF):
        seed_screen(m)
        clear_table(m)
        pop(h, m, 0x53, y)
        rows.append({'y': y, 'byte0': m[TABLE], 'byte1': m[TABLE + 1]})
    return rows


def full_rows(h, m):
    """The table-full fallback: SLOT 13 is reused."""
    seed_screen(m)
    clear_table(m)
    for s in range(NSLOT):
        m[TABLE + 2 * s] = ((0x20 + 8 * s) & 0xF8) | 5
        m[TABLE + 2 * s + 1] = 0x40
    before = [m[TABLE + i] for i in range(2 * NSLOT)]
    pop(h, m, 0x53, 0x60)
    return {'before': before,
            'table': [m[TABLE + i] for i in range(2 * NSLOT)]}


def reuse_rows(h, m):
    """THE FREE TEST.  `(byte0 & 7) == 0` and `byte0 == 0` agree on a cleared
       table and diverge ONLY after a particle has expired, because an expired
       slot keeps its X bits.  So: pop once, run the whole lifetime, and pop
       again -- the SAME slot index must be reused, and its byte0 is NOT zero."""
    seed_screen(m)
    clear_table(m)
    pop(h, m, 0xB3, 0x60)                       # X bits $B0, phase 1
    first = [m[TABLE], m[TABLE + 1]]
    passes = []
    for _ in range(7):
        call_spark(h, m)
        passes.append(m[TABLE])
    expired = m[TABLE]
    pop(h, m, 0x53, 0x70)
    return {'first': first, 'passes': passes, 'expired': expired,
            'after': [m[TABLE + i] for i in range(4)]}


def capture():
    h, m = new()
    fx = {'note': __doc__.strip(), 'spark_at': SPARK, 'pop_at': POP,
          'table_at': TABLE, 'nslot': NSLOT, 'rec_at': REC,
          'pack_at': PACK, 'ptr_at': PTR, 'bubble_at': BUBBLE,
          'shadow_off': SHADOW_OFF,
          'phase': phase_rows(h, m), 'life': life_rows(h, m),
          'order': order_rows(h, m), 'bc': bc_rows(h, m),
          'seed': seed_rows(h, m), 'full': full_rows(h, m),
          'reuse': reuse_rows(h, m)}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d phase rows, %d lifetime passes, %d order, %d bc, %d seed'
          % (FIXTURE, len(fx['phase']), len(fx['life']), len(fx['order']),
             len(fx['bc']), len(fx['seed'])))


def verify():
    fx = json.load(open(FIXTURE))
    print('OLD PHASE -> what the pass does (slot 0, X $50, raw Y $61):')
    for r in fx['phase']:
        print('   %d -> byte0 $%02X  sprite $%04X  %3d pixel writes, %d attr, %d table'
              % (r['old_phase'], r['table'][0], r['spr'], r['pix'], r['attr'],
                 r['tab']))
    print()
    print('A FULL LIFETIME from the phase the POP seeds:')
    for r in fx['life']:
        print('   pass %d -> byte0 $%02X (phase %d)  %3d pixel writes  sprite $%04X'
              % (r['n'], r['table'][0], r['table'][0] & 7, r['pix'], r['spr']))
    print()
    for r in fx['bc']:
        print('   %-26s -> slots advanced: %s' % (r['name'], r['advanced']))
    print()
    print('THE POP Y RANGE:')
    for r in fx['seed']:
        print('   Y $%02X -> byte0 $%02X byte1 $%02X  %s'
              % (r['y'], r['byte0'], r['byte1'],
                 'seeded' if r['byte0'] & 7 else 'CANCELLED'))
    print()
    ru = fx['reuse']
    print('FREE-SLOT REUSE: first $%02X, per pass %s, expired $%02X, after pop %s'
          % (ru['first'][0], ' '.join('%02X' % v for v in ru['passes']),
             ru['expired'], ' '.join('%02X' % v for v in ru['after'])))
    print('TABLE FULL: %s' % ' '.join('%02X' % v for v in fx['full']['table']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
