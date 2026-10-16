"""M7.7-I5 -- the item LIFETIME CLOCK, the EXPIRY, and the ERASE.

  $8669  the gated wrapper.  $867F CP $58 with $8680 AS ITS OWN OPERAND, so the
         test is "has $8DB6's low byte CHANGED since the previous call", not
         "is it equal to a constant".  A water-carried player ($5A or $64 bit 4)
         jumps straight to $8689, BYPASSING both the gate and the INC ($86CD) --
         so the item clock FREEZES while anyone is carried.
  $86CC  LD A,n / AND n, where $86CD is the lifetime counter and $86CF the mask.
         INC HL does not touch the flags, so the JR nz at $86D1 is still reading
         the AND: the phase steps only when (counter & mask) == 0, i.e. once in
         256 ticks with the mask at $FF.
  $86D9  phase = (phase + 1) & 7, and DELETION FIRES WHEN THE INCREMENTED VALUE
         IS 4 -- so only from phase 3.  A phase-4 entry steps to 5 and SURVIVES.
         That matters: the round-transition row writer seeds phase 4 into 160
         entries, and a model that deleted on a stored 4 would wipe them all.
  $86E6  the erase, entered by FALL-THROUGH from the expiry and by CALL from the
         collect.  $876C picks $8309 (open cell) or $830A (platform) PER CELL,
         by bit 5 of the COLOUR SHADOW, and writes the REAL attribute file.
  $A314  the pixel restore: sixteen rows copied back from display + $A000, in
         three bands of (8 - Y&7), 8 and Y&7 rows.  Items always have Y&7 == 0,
         so the third band's INC B / DEC B / RET z always returns and BAND 3 IS
         DEAD CODE for collectibles -- a gate claiming to cover it cannot pass.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THE PHASE STEP PERIOD.  With the mask at $FF the step happens one call in
    256, so a gate running fewer than 256 calls sees nothing and "never steps"
    and "steps every 256" are the same table.  Rows poke $86CD = $FF for the
    positive case AND run a control at $86CD = $00 asserting it does NOT step.
  * THE $8669 EARLY-OUT.  Inside a live frame $8DB6 always moves, so the gate is
    never taken.  $8DB6 is FROZEN and the routine called TWICE, asserting the
    second call is a total no-op -- including that $86CD did not tick.
  * THE ERASE THAT REPAINTS.  $86E6 writes $8309/$830A into four cells that
    normally already hold the background colour, so a diff shows nothing.  This
    is TRAPS #40 exactly.  All four attribute cells are seeded $FF first.
  * THE $8309 vs $830A CHOICE is invisible when the two are equal or when all
    four shadow cells agree.  They are set DIFFERENT ($46 and $66) and bit 5 is
    set in exactly TWO of the four shadow cells, so both branches run in one
    call and the result names which cell took which.
  * THE PIXEL RESTORE is invisible over a zero shadow -- "copy the shadow back"
    and "write zeros" then agree.  The shadow is seeded with a DISTINCT value
    per cell, and the display is dirtied to its complement.
  * DELETE-AT-4.  A model that deletes on a STORED phase of 4 and one that
    deletes on the INCREMENTED value agree on a phase-3 entry and differ only on
    a phase-4 one.  Phase 4 is swept explicitly.

SP IS PINNED PER CALL and the sentinel asserted (TRAPS #42).

Usage:  python tools/itemlife.py capture
        python tools/itemlife.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

GATE = 0x8669             # the wrapper with the edge detector
ERASE = 0x86E6
PERSLOT = 0x86B1          # poked to RET when only the gate is under test
CNT, MASK = 0x86CD, 0x86CF
CPOP = 0x8680             # the operand of $867F CP n
TIMER = 0x8DB6
SKIP = 0xFED1
FLOOD = 0xFECE
OPEN_C, PLAT_C = 0x8309, 0x830A
REC = 0x8903
ENTRY = 0x9605
P1 = 0xFD80
FIXTURE = 'build/itemlife_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, hl=None, iy=None):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    if iy is not None:
        r[10], r[11] = iy >> 8, iy & 0xFF
    if hl is not None:
        r[6], r[7] = hl >> 8, hl & 0xFF
    r[PC] = addr
    return sp


def run(h, sp):
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


# ------------------------------------------------------------ the gate $8669
def gate_rows(h, m):
    """$8669 called TWICE with $8DB6 frozen, so the edge detector is observable."""
    rows = []
    saved = m[PERSLOT]
    m[PERSLOT] = 0xC9                       # the per-entry body is I1/I2/I3
    # carry 0 = nobody; 1 = P1's +$5A bit 4; 2 = P2's +$64 bit 4.  Both bytes are
    # swept because $8670 and $8676 are separate tests and a model that honours
    # only one of them passes every row where the other is the carried player.
    # AND THE TABLE IS NOT EMPTY: the bypass still runs the WALK, so with an empty
    # table "bypass to the walk" and "bypass and return" are the same function.
    for carry in (0, 1, 2):
        for timer in (0x40, 0x41):
            for i in range(64):
                m[ENTRY + 2 * i] = 0
                m[ENTRY + 2 * i + 1] = 0
            m[ENTRY] = 0x40             # one live fruit, so the walk is observable
            m[ENTRY + 1] = 0x89
            m[CNT] = 0x10
            m[CPOP] = 0x99                  # deliberately NOT equal to the timer
            m[TIMER] = timer
            m[TIMER + 1] = 0x10
            m[P1 + 0x5A] = 0x10 if carry == 1 else 0x00
            m[P1 + 0x64] = 0x10 if carry == 2 else 0x00
            m[0x872C] = 0xEE      # seeded ONCE: calls 2 and 3 take the early-out,
            seq = []              # so the flag must still read what call 1 left
            for call in range(3):
                sp = arm(h, GATE)
                run(h, sp)
                seq.append({'cnt': m[CNT], 'cpop': m[CPOP],
                            'pass_flag': m[0x872C]})
            rows.append({'carry': carry, 'timer': timer, 'seq': seq})
    m[PERSLOT] = saved
    return rows


# ------------------------------------------------- the clock and the phase step
def life_rows(h, m):
    """$86B1's tail, reached by CALLing $86CC directly with HL at the entry."""
    rows = []
    saved = m[0x8719]
    m[0x8719] = 0xC9                        # the DRAW is I2; stop at the draw entry
    # $10 is the separator: ($10 & $FF) is non-zero so the real code does NOT
    # step, but ($10 & $07) is zero so a model with a hard-coded \$07 mask does.
    for cnt in (0x00, 0x01, 0x10, 0xFF):
        for skip in (0, 1):
            for phase in range(8):
                m[ENTRY] = 0x40             # X=64, type 0
                m[ENTRY + 1] = 0x88 | phase
                m[CNT] = cnt
                m[MASK] = 0xFF
                m[SKIP] = skip
                m[FLOOD] = 0
                m[OPEN_C], m[PLAT_C] = 0x46, 0x66
                m[0x8908], m[0x8909] = 0x40, 0x88
                # the four attribute cells, dirtied: a phase-3 entry EXPIRES and
                # falls through into the erase, so these must come back repainted
                base = 0x5800 + (0x88 >> 3) * 32 + (0x40 >> 3)
                cells = [base, base + 1, base + 32, base + 33]
                for c in cells:
                    m[c & 0xFFFF] = 0xFF
                shad = 0xF800 + ((0x88 & 0xF8) << 2) + ((0x40 >> 3) & 0x1F)
                for c in (shad, shad + 1, shad + 32, shad + 33):
                    m[c & 0xFFFF] = 0x00
                sp = arm(h, 0x86CC, hl=ENTRY, iy=REC)
                run(h, sp)
                rows.append({'cnt': cnt, 'skip': skip, 'phase': phase,
                             'b0': m[ENTRY], 'b1': m[ENTRY + 1],
                             'new_phase': m[ENTRY + 1] & 7,
                             'attrs': [m[c & 0xFFFF] for c in cells]})
    m[0x8719] = saved
    return rows


# ------------------------------------------------------------- the erase $86E6
def erase_rows(h, m):
    """The attribute restore AND the pixel restore, over a dirtied world."""
    rows = []
    for flood in (0, 1):
        for (x, y) in ((0x50, 0x48), (0x10, 0x18), (0xE0, 0xB8)):
            m[0x8908], m[0x8909] = x, y
            m[OPEN_C], m[PLAT_C] = 0x46, 0x66     # DIFFERENT, so the choice shows
            m[FLOOD] = flood
            # the four attribute cells, and their colour-shadow counterparts
            base = 0x5800 + (y >> 3) * 32 + (x >> 3)
            cells = [base, base + 1, base + 32, base + 33]
            shad = 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)
            scells = [shad, shad + 1, shad + 32, shad + 33]
            for c in cells:
                m[c & 0xFFFF] = 0xFF                # TRAPS #40: never leave it
            for i, c in enumerate(scells):          # bit 5 set in exactly TWO
                m[c & 0xFFFF] = 0x20 if i in (1, 2) else 0x00
            # the pixels: a DISTINCT shadow value per row, display = its complement
            rt = 0xFD00 + 2 * ((y >> 3) & 0x1F)
            disp = []
            for band in range(2):
                lo = m[rt + 2 * band]
                hi = m[rt + 2 * band + 1]
                for r in range(8):
                    for c in range(2):
                        a = (((hi + r) & 0xFF) << 8) | ((lo + ((x >> 3) & 0x1F) + c) & 0xFF)
                        disp.append(a)
            for i, a in enumerate(disp):
                # ONLY where the display target is real.  The bottom row's second
                # band reads $FD30 -- the entry past the 24-entry table, which is
                # $0000 -- so it addresses page 0 and the machine DROPS the
                # writes; its source is $A0xx, which on the machine is the game's
                # own CODE.  Seeding there corrupts the machine under test, so the
                # engine-side "nothing below $4000" check seeds the ENGINE's
                # $A0xx instead (see the gate) -- the machine needs no help,
                # because its source is already non-zero.
                if a >= 0x4000:
                    m[a] = (i * 7 + 1) & 0xFF                    # the display, dirty
                    m[(a + 0xA000) & 0xFFFF] = (i * 13 + 3) & 0xFF   # the shadow
            h.memobj.watch(0x4000, 0x6000)
            sp = arm(h, ERASE, iy=REC)
            run(h, sp)
            h.memobj.unwatch()
            log = sorted(set((a, v) for _, a, v in h.memobj.log))
            # the bottom row's second band reads $FD30, the entry PAST the
            # 24-entry table, which is $0000 -- so it addresses page 0 and the
            # machine DROPS the writes.  Recorded as a count so the engine's
            # guard is falsifiable.
            rows.append({'flood': flood, 'x': x, 'y': y,
                         'attrs': [m[c & 0xFFFF] for c in cells],
                         'shadow_bits': [m[c & 0xFFFF] for c in scells],
                         'writes': [[a, v] for a, v in log],
                         'n': len(h.memobj.log)})
    return rows


def perslot_rows(h, m):
    """$86B1 over a live entry: unpack, collide, AGE, draw.

       Without these rows nothing gates the ORDER -- "age then draw" and "draw
       without ageing" leave the same table, and only the SCREEN tells them
       apart.  A phase-3 entry expires, erases, and must not be drawn at all.
    """
    rows = []
    for phase in (1, 3):
        for cnt in (0x00, 0x01):
            m[ENTRY] = 0x40
            m[ENTRY + 1] = 0x88 | phase
            m[CNT] = cnt
            m[MASK] = 0xFF
            m[SKIP] = 0
            m[FLOOD] = 0
            m[0xFECF] = 0
            m[0x872C] = 0
            m[OPEN_C], m[PLAT_C] = 0x46, 0x66
            for base in (P1, 0xFD8A):
                m[base + 7] = 0x00          # no player: the collect cannot fire
            h.memobj.watch(0x4000, 0x5B00)
            sp = arm(h, PERSLOT, hl=ENTRY, iy=REC)
            run(h, sp)
            h.memobj.unwatch()
            log = sorted(set((a, v) for _, a, v in h.memobj.log))
            rows.append({'phase': phase, 'cnt': cnt,
                         'b0': m[ENTRY], 'b1': m[ENTRY + 1],
                         'writes': [[a, v] for a, v in log],
                         'n': len(h.memobj.log)})
    return rows


def capture():
    h, m = new()
    g = gate_rows(h, m)
    l = life_rows(h, m)
    e = erase_rows(h, m)
    ps = perslot_rows(h, m)
    fx = {'note': __doc__.strip(), 'gate_at': GATE, 'erase_at': ERASE,
          'cnt_at': CNT, 'mask_at': MASK, 'cpop_at': CPOP, 'timer_at': TIMER,
          'skip_at': SKIP, 'flood_at': FLOOD, 'entry_at': ENTRY, 'rec_at': REC,
          'open_at': OPEN_C, 'plat_at': PLAT_C,
          'gate': g, 'life': l, 'erase': e, 'perslot': ps,
          'perslot_at': PERSLOT}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d gate rows, %d life rows, %d erase rows'
          % (FIXTURE, len(g), len(l), len(e)))
    died = sum(1 for r in l if r['b0'] == 0)
    print('  life rows where the entry EXPIRED: %d' % died)
    print('  erase writes: %s' % [r['n'] for r in e])
    for r in ps:
        print('    $86B1 phase %d cnt $%02X -> byte0 $%02X, %d screen writes'
              % (r['phase'], r['cnt'], r['b0'], r['n']))


def verify():
    fx = json.load(open(FIXTURE))
    print('THE GATE $8669 -- three back-to-back calls with $8DB6 frozen:')
    for r in fx['gate']:
        print('   carry=%d timer=$%02X  counter %s' %
              (r['carry'], r['timer'], ' -> '.join('$%02X' % s['cnt'] for s in r['seq'])))
    print()
    print('THE PHASE STEP -- counter $FF is the only one that ticks:')
    for cnt in (0x00, 0x01, 0xFF):
        row = [r for r in fx['life'] if r['cnt'] == cnt and r['skip'] == 0]
        print('   $86CD=$%02X  phase %s' % (cnt,
              '  '.join('%d->%s' % (r['phase'], 'DEAD' if r['b0'] == 0 else r['new_phase'])
                        for r in row)))
    print()
    print('THE ERASE -- four attribute cells, two shadow bits set:')
    for r in fx['erase']:
        print('   flood=%d (%3d,%3d)  attrs %s  from shadow bits %s  %d writes'
              % (r['flood'], r['x'], r['y'],
                 ' '.join('$%02X' % v for v in r['attrs']),
                 ' '.join('$%02X' % v for v in r['shadow_bits']), r['n']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
