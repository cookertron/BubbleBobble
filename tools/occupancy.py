"""M7.7-H5 -- THE OCCUPANCY FIELD: bits 0-4 of the colour shadow.

THE THIRD LIFE OF $F800-$FAFF.  H3 settled bit 5 (SOLID) and H4 bits 6-7 (the
per-round DRIFT).  Bits 0-4 are a LIVE PER-CELL CLAIM: a bubble marks the cell it
occupies with its own slot number and releases it when it moves or pops.

    $B8B5  CALL $AEDC / LD A,($BFF7) / LD C,A
    $B8BC  LD A,(HL) / AND $E0 / OR C
    $B8C0  LD (HL),A            the CLAIM -- bits 5,6,7 are PRESERVED
    $B6D3  LD A,(HL) / AND $E0
    $B6D6  LD (HL),A            the RELEASE -- the same three bits preserved

ONE PROBE, TWO MASKS, TWO MEANINGS -- and this is the part a port gets wrong by
having one function:

    $AE7F  LD C,$3F  \\_ both fall into $AE81, which does CALL $AED1 then
    $AD35  LD C,$20  /  LD A,(HL) / AND C / JR nz

  $3F is bits 0-5: SOLID **OR** CLAIMED -- "can a bubble go here?"
  $20 is bit 5 alone: SOLID -- "is there a floor here?"
So the same cell reads BLOCKED to one caller and OPEN to the other, and a model
with a single "is this cell solid?" helper answers one of the two wrongly
everywhere a bubble is sitting.

AND E IS NOT A BOOLEAN.  $AE81 returns THREE kinds of answer:
    free, or drift bits only        E = 0
    SOLID (bit 5)                   E = 1, and solid SHORT-CIRCUITS at $AEA0
                                    before the IY test ever happens
    CLAIMED, (IY+8) bit 1 CLEAR     E = 10 * (12 - marker) -- the POOL OFFSET of
                                    the bubble that holds the cell, computed by
                                    $AEAD's AND $1F / LD A,12 / SUB B / x10
    CLAIMED, (IY+8) bit 1 SET       E = 1, (IY+9) := 1, and $AEAB POP HL / RET
                                    ABANDONS ITS CALLER -- the fourth routine
                                    here to do that, after $B679, $88B1 and $89B7
A port treating E as "blocked or not" is right twice and wrong twice.

*** AND A MARKER OF 12 IS THE ONE VALUE THAT HIDES IT. ***  Marker 12 resolves to
slot 0 and therefore to offset ZERO -- identical to "free".  My first case list
used exactly that value and read the claimed path as unblocked; marker 7 gives
E = 50 and shows it.  The rows below drive both.

AND THE CLAIM DIVERTS THE DRIFT INTO THE RNG.  $B87D does AND $1F on the target
cell and $B888 on the one $21 bytes on; if either is CLAIMED, $B88D takes
`LD A,R / AND 6` -- the same 0/2/4/6 code space H4's drift field uses, but drawn
from the refresh register instead of read from the map.  So H4's answer is the
direction a bubble takes ONLY when the cell it wants is free.  (LD A,R is TRAPS
#46: it cannot be sampled, only enumerated.)

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT $BFF7 IS A MYSTERY.  The reading pass calls its writer UNIDENTIFIED and
    notes the value "MOVES WITHIN A FRAME".  It is the bubble manager's own SLOT
    COUNTER -- $B63C sets 12 and $B674 decrements it per slot -- so it moves
    within a frame because it IS the loop index, and the marker is therefore
    12 minus the slot.  M7.5-v already had this; it is asserted here.
  * THAT "ROUNDS >= 2" DESCRIBES THE WRITERS.  round1_48 and `water` are BOTH
    round $01 and differ by 632 writes to ZERO.  Both are driven in the same row.
  * THAT A CHANGED-BIT MASK SET CAN BE WRITTEN FROM THE CODE.  The reading pass
    predicted {$01,$06,$0A,$0B,$0C} and the machine gives {$00,$06,$07,$0A,$0B,
    $0C} -- $01 NEVER OCCURS in over a thousand writes, while $00 (a same-value
    write-back) and $07 do.  Quoted from a run, not from the instructions.

Usage:  python tools/occupancy.py capture
        python tools/occupancy.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

MAP, MAP_N = 0xF800, 0x300
PROBE = 0xAE81           # the shared body; $AE7F and $AD35 only choose C
SOLID_OR_CLAIMED, SOLID_ONLY = 0x3F, 0x20
COUNTER = 0xBFF7
STATES = ('round1_48', 'water', 'r6_48', 'r10_48', 'hurryup', 'r20_48',
          'r50_48', 'boss')
FIXTURE = 'build/occupancy_fixture.json'


# ------------------------------------------------- (a) who writes, and what
def write_rows():
    rows = []
    for st in STATES:
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if m[0x8DC4] != 0xC9:
            continue
        before = [m[MAP + i] for i in range(MAP_N)]
        h.memobj.watch(MAP, MAP + MAP_N)
        h.run_frames(240, interrupts=True)
        h.memobj.unwatch()
        w = h.memobj.log
        pcs, masks, top = {}, set(), 0
        prev = dict()
        for (p, a, v) in w:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
            old = prev.get(a, before[a - MAP])
            masks.add(old ^ v)
            if (old & 0xE0) != (v & 0xE0):
                top += 1
            prev[a] = v
        rows.append({'state': st, 'round': m[0x8609], 'writes': len(w),
                     'writers': pcs, 'masks': sorted(masks),
                     'top_bits_changed': top,
                     'counter_end': m[COUNTER]})
    return rows


# ------------------------------------------- (b) ONE PROBE, TWO MASKS
def probe_rows(h, m):
    """The cell states x the two masks -- AND IT NEEDS AN IY, AND IT NEEDS MORE
       THAN ONE CELL POSITION.

       MY FIRST VERSION DROVE IT WITHOUT AN IY and read every case as "not
       blocked", which made the two masks agree everywhere.  $AE9A sets E := 1,
       $AE9C AND $20 splits SOLID from CLAIMED, and the CLAIMED branch falls into
       $AEA1 BIT 1,(IY+8) -- so for a claimed cell the answer is not a function
       of the cell at all, it depends on the bubble asking.

       MY SECOND VERSION USED ONE CELL POSITION and six mutations survived,
       because ALL of these were invisible:
         * the INC L is EIGHT BIT, so a probe starting at low byte $FE wraps
           inside its page instead of running into the next -- needs a cell at
           the end of a row;
         * $AE92 LD A,D / AND 6 / RET z gates the THIRD cell on bits 1-2 of Y,
           and every Y I drove was $60, whose bits 1-2 are ZERO, so the third
           cell was never reached;
         * the SECOND and THIRD cells are tested with the CALLER'S mask too, and
           I only ever put a value in the first;
         * the marker is masked $1F, and both markers I used (7 and 12) fit in
           four bits, so $0F and $1F gave the same slot."""
    rows = []
    IY = 0xFED8                          # bubble slot 0
    CASES = (
        # (name, x, y, [(cell offset, value), ...])
        ('empty', 0x50, 0x60, []),
        ('SOLID in cell 0', 0x50, 0x60, [(0, 0x20)]),
        ('CLAIMED slot 5 in cell 0', 0x50, 0x60, [(0, 0x07)]),
        ('CLAIMED slot 12 in cell 0', 0x50, 0x60, [(0, 0x0C)]),
        ('SOLID and CLAIMED in cell 0', 0x50, 0x60, [(0, 0x2C)]),
        ('drift bits only', 0x50, 0x60, [(0, 0xC0)]),
        ('drift + claimed', 0x50, 0x60, [(0, 0xCC)]),
        # the SECOND cell alone -- the first version never filled it
        ('CLAIMED slot 5 in cell 1 ONLY', 0x50, 0x60, [(1, 0x07)]),
        ('SOLID in cell 1 ONLY', 0x50, 0x60, [(1, 0x20)]),
        # Y with bits 1-2 SET, which is the only way the THIRD cell is reached
        # THE THIRD CELL IS GATED ON X, NOT Y -- $AE86 LD D,E overwrites D with
        # the X that came in, three instructions before $AE92 LD A,D / AND 6.
        # So these two groups separate the two readings, and every case above
        # has BOTH aligned, which is why a `y & 6` model survived a battery.
        ('X unaligned ($52), cell 2 CLAIMED', 0x52, 0x60, [(2, 0x07)]),
        ('X unaligned ($54), cell 2 SOLID', 0x54, 0x60, [(2, 0x20)]),
        ('X unaligned ($56), all three empty', 0x56, 0x60, []),
        ('X ALIGNED, cell 2 CLAIMED (unreached)', 0x50, 0x60, [(2, 0x07)]),
        ('Y unaligned but X aligned, cell 2 CLAIMED', 0x50, 0x62, [(2, 0x07)]),
        ('Y aligned but X unaligned, cell 2 CLAIMED', 0x52, 0x60, [(2, 0x07)]),
        # a marker with BIT 4 set -- $0F and $1F differ only here
        ('CLAIMED marker $15 (bit 4 set)', 0x50, 0x60, [(0, 0x15)]),
        ('CLAIMED marker $1F', 0x50, 0x60, [(0, 0x1F)]),
        # the END OF A ROW, where an eight-bit INC L wraps and a sixteen-bit
        # one walks into the next page
        # THE END OF A PAGE, not merely the end of a row.  x=$F8,y=$60 gives base
        # $F99F, whose low byte is $9F -- the eight-bit INC L and a sixteen-bit
        # one agree there and the wrap is invisible.  ((y & $F8) << 2) + (x >> 3)
        # must come to $FF, which y=$38 with x=$F8 does exactly: base $F8FF, so
        # the machine's INC L goes to $F800 and a sixteen-bit model to $F900.
        ('end of PAGE, cell 1 CLAIMED', 0xF8, 0x38, [(1, 0x07)]),
        ('end of PAGE, cell 1 SOLID', 0xF8, 0x38, [(1, 0x20)]),
        # THE DECOY.  A claim at the SIXTEEN-BIT target ($F900) with the
        # EIGHT-BIT one ($F800) left EMPTY: the machine wraps and finds nothing,
        # a sixteen-bit model walks into the next page and finds the claim.
        # Written as an ABSOLUTE address, because the seeding formula below
        # deliberately folds offsets the way the machine addresses them and
        # would otherwise put the decoy on top of the wrap target.
        ('end of PAGE, decoy in the NEXT page', 0xF8, 0x38, [('abs', 0xF900, 0x07)]),
    )
    for (name, x, y, pokes) in CASES:
        base = MAP + (((y & 0xF8) << 2) | ((x >> 3) & 0x1F))
        for (tag, c) in (('$3F solid-or-claimed', SOLID_OR_CLAIMED),
                         ('$20 solid only', SOLID_ONLY)):
            for bit1 in (0, 1):
                for i in range(MAP_N):
                    m[MAP + i] = 0
                for pk in pokes:
                    if pk[0] == 'abs':
                        m[pk[1]] = pk[2]
                        continue
                    off, v = pk
                    # the machine's INC L is EIGHT BIT, so the neighbours of a
                    # cell at the end of a page are at the START of that page
                    a = (base & 0xFF00) | ((base + off) & 0xFF)
                    m[a] = v
                for i in range(120):
                    m[0xFED8 + i] = 0
                m[IY + 8] = 0x02 if bit1 else 0x00
                m[IY + 9] = 0xAA          # POISONED: $AEA7 writes 1 here
                r = h.sim.registers
                r[3] = c                  # C -- the mask $AE7F/$AD35 choose
                r[5], r[4] = x, y         # E = X, D = Y
                sp = RC.arm(h, PROBE)
                r[10], r[11] = IY >> 8, IY & 0xFF
                h.run_until(h.SENTINELS, limit=10 ** 6, stride=1,
                            interrupts=False)
                if h.regs[PC] not in h.SENTINELS:
                    raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
                rows.append({'cell': name, 'x': x, 'y': y,
                             'pokes': [list(pk) for pk in pokes],
                             'mask': tag, 'c': c, 'iy8_bit1': bit1,
                             'e_out': h.regs[5], 'a_out': h.regs[0],
                             'iy9_out': m[IY + 9],
                             'sp_delta': h.regs[12] - sp,
                             'abandoned': h.regs[12] != sp + 2})
    return rows


# ------------------------------------------------ (c) $BFF7 is the counter
def counter_rows(h, m):
    """$B63C LD A,12 / LD ($BFF7),A, then $B674 DEC ($BFF7) per slot.  So it is
       the manager's loop index and the marker is 12 MINUS the slot -- which is
       why its value 'moves within a frame'."""
    h2 = Harness()
    h2.load_state_file(pc.state_path('r6_48'))
    mm = h2.memobj.m
    h2.memobj.watch(COUNTER, COUNTER + 1)
    h2.run_frames(4, interrupts=True)
    h2.memobj.unwatch()
    seq = [(('%04X' % p), v) for (p, _a, v) in h2.memobj.log]
    pcs = sorted(set(p for (p, _v) in seq))
    return {'writers': pcs, 'first_20': seq[:20],
            'values_seen': sorted(set(v for (_p, v) in seq))}


# --------------------------------- (d) the claim diverts the drift to the RNG
def rng_rows():
    """$B88D LD A,R / AND 6 -- the same 0/2/4/6 code space the drift field uses,
       drawn from the refresh register when the target cell is CLAIMED."""
    h = Harness()
    h.load_state_file(pc.state_path('r6_48'))
    fn = []
    for r in range(256):
        h.sim.registers[15] = r          # R
        h.sim.registers[PC] = 0xB88D
        h.step(2, interrupts=False)      # LD A,R / AND 6
        fn.append(h.sim.registers[0])
    return {'at': 0xB88D, 'fn': fn,
            'distinct': sorted(set(fn)),
            'offset': next((o for o in range(4)
                            if all(fn[r] == (((r + o) & 0xFF) & 6)
                                   for r in range(256))), None)}


def capture():
    h, m = RC.new()
    fx = {'note': __doc__.strip(), 'map_at': MAP, 'map_n': MAP_N,
          'probe_at': PROBE, 'solid_or_claimed': SOLID_OR_CLAIMED,
          'solid_only': SOLID_ONLY, 'counter_at': COUNTER,
          'writes': write_rows(), 'probe': probe_rows(h, m),
          'counter': counter_rows(h, m), 'rng': rng_rows()}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s' % FIXTURE)
    print('  WHO WRITES THE FIELD, 240 frames each:')
    for r in fx['writes']:
        print('     %-11s round %2d: %4d writes %s, top bits changed %d, masks %s'
              % (r['state'], r['round'], r['writes'], r['writers'],
                 r['top_bits_changed'], ['%02X' % v for v in r['masks']]))
    print('  $BFF7 writers: %s, values %s'
          % (fx['counter']['writers'], fx['counter']['values_seen']))
    print('  $B88D LD A,R / AND 6 -> %s' % fx['rng']['distinct'])


def verify():
    fx = json.load(open(FIXTURE))
    print('ONE PROBE, TWO MASKS -- the same cell, asked two questions (IY bit 1 CLEAR):')
    for r in fx['probe']:
        if r['iy8_bit1']:
            continue
        print('   %-24s %-22s -> E=%d  (IY+9)=$%02X  %s'
              % (r['cell'], r['mask'], r['e_out'], r['iy9_out'],
                 'ABANDONED ITS CALLER' if r['abandoned'] else ''))
    print()
    print('AND WITH (IY+8) BIT 1 SET -- the same cell, a different answer:')
    for r in fx['probe']:
        if not r['iy8_bit1'] or r['mask'] != '$3F solid-or-claimed':
            continue
        print('   %-24s -> E=%d  (IY+9)=$%02X  %s'
              % (r['cell'], r['e_out'], r['iy9_out'],
                 'ABANDONED ITS CALLER' if r['abandoned'] else ''))
    print()
    print('THE CHANGED-BIT MASKS, over every write in every world:')
    allm = sorted(set(v for r in fx['writes'] for v in r['masks']))
    print('   %s' % ['%02X' % v for v in allm])
    print('   ($01 never occurs; the reading pass predicted it and the machine did not)')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
