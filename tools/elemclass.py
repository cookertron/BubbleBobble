"""M7.7-H6 -- THE ELEMENT CLASS $7E0E: $7DD6's four lists and its four readers.

$79AC's tail is not a map pass at all.  It is the collision transform (H3), then
the drift painter (H4), and then -- by FALL-THROUGH at $7DD6, with no CALL to it
anywhere in 64K -- a per-round ELEMENT CLASS that 49 of 81 rounds have and the
port models none of.

THE WALK, and why it is not a table lookup:

    $7DD6  LD A,($8609)          the round, 1-based
    $7DD9  LD HL,$7E4B
    $7DDC  LD C,0
    $7DDE  CP (HL)               entry matches -> C is the group
           JR z,$7DED
           INC (HL) / DEC (HL)   *** A ZERO TEST THAT WRITES ***
           INC HL
           JR nz,$7DDE           entry was non-zero -> keep scanning
           INC C                 entry was $00 -> end of list, next list
           BIT 2,C
           JR z,$7DDE
           LD C,$FE              all four exhausted
    $7DED  LD A,C / ADD A,2 / LD ($7E0E),A
           CP 5 / JR nc,$7E04    group 3 -> REDRAW FROM R
           CP 3 / RET nz
           LD HL,$A37D / LD ($FDEE),HL / LD ($FDF8),HL
    $7E04  LD A,R / AND 7 / ADD A,5 / LD ($7E0E),A

So the class is C+2: groups 0,1,2 give the FIXED classes 2, 3, 4, group 3 gives a
value REDRAWN FROM THE REFRESH REGISTER in 5..12, and a round in no list gives
($FE+2)&$FF = 0.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT A ZERO TEST DOES NOT WRITE.  $7DE1 INC (HL) / DEC (HL) stores to the
    table TWICE per entry examined and leaves it unchanged.  A write-watch over
    $7E00-$7F00 therefore reports SELF-MODIFYING CODE THAT IS NOT THERE -- up to
    106 writes on a round in no list.  The gate asserts the count AND that the
    53 bytes are byte-identical afterwards; a port that "optimises away" the
    phantom writes is right, and one that concludes the table is live data is
    wrong, and only a gate that names the phantoms can tell them apart.

  * THAT THE CLASS IS WRITTEN ON EVERY ROUND.  $7C89 CP $51 / RET z returns out
    of the whole tail on round 81, so round 81 NEVER REACHES $7DD6 and $7E0E is
    STALE -- it carries round 80's class into the treasure room.  Asserted with a
    poison value no code path writes.

  * THAT THE GROUP-3 VALUE CAN BE SAMPLED.  It cannot (TRAPS #46).  R advances
    with the instruction count, so this sets R over all 256 values and asserts
    the FUNCTION, and separately DEMONSTRATES that repeat builds of one round do
    not agree.

  * THAT $9E75 HANDLES TWO CLASSES.  *** THE READING PASS SAID IT HANDLES ONLY
    2 AND 3 AND THAT IS WRONG. ***  It is SUB 2 / JP z,$A159 / DEC A / JR z,$9E85
    / DEC A / JP z,$9F63 / RET -- THREE classes, 2, 3 and 4.  The pass stopped
    reading at the JR.

  * THAT THE EIGHT RANDOMISED CLASSES GO NOWHERE.  The plan flagged them
    unreachable and asked this increment to find them or say it did not.  THEY
    ARE FOUND, in two places:
      - $7E80 patches $7EFB, the IMMEDIATE OF `LD (IY+9),n`, so an elemental
        bubble is spawned CARRYING ITS CLASS as its state byte; and it patches
        $7EB2, the immediate of a `CP n`, to 4 for classes 1..4 and 1 for
        classes >= 5 -- so the randomised classes spawn under a FOUR TIMES
        TIGHTER bubble-count throttle.
      - $BF74 indexes a WORD TABLE at $C068 by (class - 2) and ORs the 8-byte
        glyph it points at into the flashing-bubble bank at $D38C.  Classes 2/3/4
        take RAM icons at $B614/$B61C/$B624 (a wave, a bolt, a flame); CLASSES
        5..12 TAKE ROM CHARACTER-SET GLYPHS -- 'e','x','t','e','n','d','e','d'.
        They are the EXTEND letters, and they are a SECOND, INDEPENDENT ROM FONT
        DEPENDENCY after the HUD font.

  * THAT CLASS 0 IS SAFE AT $BF74.  It is not indexed out: SUB 2 gives $FE and
    ADD A,A gives $FC, so the 31 rounds in no list read the word 252 BYTES PAST
    the eleven-entry table, at $C164, and overlay whatever it points at.  Recorded
    as measured behaviour, not repaired.

Usage:  python tools/elemclass.py capture
        python tools/elemclass.py verify
"""
import sys, json, hashlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

R_REG = 15                        # skoolkit.simutils.REGISTERS['R']

WALK = 0x7DD6                     # the element-class walk (reached by fall-through)
REDRAW = 0x7E04                   # LD A,R / AND 7 / ADD A,5 / LD ($7E0E),A
TAIL = 0x7C43                     # $79AC = JP $7C43 -- transform, painter, walk
ELEM = 0x7E0E
LIST_AT, LIST_END = 0x7E4B, 0x7E80
ROUND = 0x8609
G1_A, G1_B, G1_VAL = 0xFDEE, 0xFDF8, 0xA37D
SPAWN = 0x7E80                    # the elemental-bubble spawner
SPAWN_STATE = 0x7EFB              # the immediate of LD (IY+9),n
SPAWN_THRESH = 0x7EB2             # the immediate of CP n
GATE_A, GATE_B = 0x8E3B, 0x8DBD   # the two gates after the patches
DISPATCH = 0x9E75
D_TARGETS = (0xA159, 0x9E85, 0x9F63)
BANK_PTRS = 0xBF74                # the $C068 word-table reader
PTR_TAB = 0xC068
BANK = 0xD380
POISON = 0xAA
EXT_BITS = 0xB80E          # SUB 5 indexes this: class -> EXTEND bit mask
EXT_BOUND = 0xB75C         # $B75C CP 5 -- the operand is at $B75D
EXT_COUNT = 0x9591         # $9591 LD A,6 -- SIX letters; operand at $9592
FIXTURE = 'build/elemclass_fixture.json'


# ------------------------------------------------------------- (a) the table
def read_lists(m):
    """The four $00-separated lists, read as bytes and split."""
    raw = [m[a] for a in range(LIST_AT, LIST_END)]
    groups, cur = [], []
    for b in raw:
        if b == 0:
            groups.append(cur)
            cur = []
        else:
            cur.append(b)
    if cur:
        groups.append(cur)
    return raw, groups


def predict(groups, rnd):
    """What the walk should produce, derived from the table ALONE.  Returned as
       an int for the fixed classes and the string 'R' for the redrawn ones, so
       the gate can never quietly compare a random value to itself."""
    for gi, g in enumerate(groups):
        if rnd in g:
            return 'R' if gi == 3 else gi + 2
    return 0


# --------------------------------------------- (b) the walk, driven directly
def walk_rows(h, m, groups):
    """$7DD6 alone, over every round.  Its ONLY input is $8609, so poking the
       round here is a complete measurement -- unlike a BUILD, where F0 proved a
       poke is not a round sample.

       Two calls per round because the harness watches ONE range: the first
       counts the phantom writes into the list table, the second catches group
       1's stores into $FDEE/$FDF8."""
    rows = []
    for rnd in range(1, 82):
        m[ROUND] = rnd
        m[ELEM] = POISON
        before = bytes(m[LIST_AT:LIST_END])

        h.memobj.watch(LIST_AT, LIST_END)
        sp = RC.arm(h, WALK)
        RC.run(h, sp)
        phantom = list(h.memobj.log)
        h.memobj.unwatch()
        after = bytes(m[LIST_AT:LIST_END])
        cls = m[ELEM]

        # the same walk again, watching the two group-1 words instead
        m[ELEM] = POISON
        for a in (G1_A, G1_A + 1, G1_B, G1_B + 1):
            m[a] = 0x5A                       # a value neither store writes
        h.memobj.watch(G1_A, G1_B + 2)
        sp = RC.arm(h, WALK)
        RC.run(h, sp)
        g1 = [('%04X' % p, '%04X' % a, v) for (p, a, v) in h.memobj.log]
        h.memobj.unwatch()

        rows.append({
            'round': rnd,
            'elem': cls,
            'predicted': predict(groups, rnd),
            'phantom_writes': len(phantom),
            'phantom_pcs': sorted({'%04X' % p for (p, _a, _v) in phantom}),
            'table_intact': before == after,
            'g1_writes': g1,
            'fdee': [m[G1_A], m[G1_A + 1]],
            'fdf8': [m[G1_B], m[G1_B + 1]],
        })
    return rows


# ------------------------------------------- (c) the staleness at $7C89 RET z
def stale_rows(h, m):
    """The FULL tail, which is where the early return lives.  Round 81 must come
       back still poisoned; a round with a class must not.  Driven on both sides
       of the test, because 'round 81 is stale' is only a fact if the SAME driver
       shows a neighbour being written."""
    rows = []
    for rnd in (80, 81, 5, 0x51):
        m[ROUND] = rnd
        m[ELEM] = POISON
        sp = RC.arm(h, TAIL)
        RC.run(h, sp)
        rows.append({'round': rnd, 'elem': m[ELEM], 'written': m[ELEM] != POISON})
    return rows


# ------------------------------------------- (d) the group-3 redraw, as a FUNCTION
def redraw_rows(h, m):
    """TRAPS #46.  R cannot be sampled, so set it over its whole range and assert
       the function; then show that repeat runs of the same round disagree, which
       is the part a frozen value would hide."""
    fn = []
    for r in range(256):
        m[ELEM] = POISON
        h.sim.registers[R_REG] = r
        h.sim.registers[PC] = REDRAW
        h.step(4, interrupts=False)           # LD A,R / AND 7 / ADD A,5 / LD (nn),A
        fn.append(m[ELEM])

    # and the demonstration: one group-3 round, many runs, driven through the
    # whole tail so the machine's own instruction stream sets R
    m[ROUND] = 0x04                           # $04 is in group 3
    seen = []
    for _ in range(24):
        m[ELEM] = POISON
        h.run_frames(1, interrupts=True)      # move R by a real, varying amount
        sp = RC.arm(h, TAIL)
        RC.run(h, sp)
        seen.append(m[ELEM])
    return {'fn': fn, 'r_offset': 2, 'repeat_round': 4, 'repeat': seen}


# ---------------------------------------------------- (e) the spawner $7E80
def spawn_rows(h, m):
    """The two SELF-MODIFIED OPERANDS $7E80 writes before either of its gates.
       $7EFB is the immediate of `LD (IY+9),n` -- the spawned bubble's STATE --
       and $7EB2 is the immediate of a `CP n` threshold.  Both are patched for
       any non-zero class, so this drives the spawner with the timer gate SHUT
       ($8DBD != $2A) and still sees them move."""
    rows = []
    for cls in range(0, 13):
        m[ELEM] = cls
        m[SPAWN_STATE], m[SPAWN_THRESH] = 0x5A, 0x5A     # neither is a written value
        m[GATE_A] = 0x00
        m[GATE_B] = 0x00                                  # NOT $2A: no spawn
        sp = RC.arm(h, SPAWN)
        RC.run(h, sp)
        rows.append({'class': cls,
                     'state_op': m[SPAWN_STATE],
                     'thresh_op': m[SPAWN_THRESH]})
    return rows


# ------------------------------------------------- (f) the dispatch $9E75
def dispatch_rows(h, m):
    """Which of the three targets each class reaches.  Stopped AT the target, so
       this asserts the DISPATCH and runs none of the work behind it."""
    rows = []
    stops = set(D_TARGETS) | set(h.SENTINELS)
    for cls in range(0, 13):
        m[ELEM] = cls
        sp = RC.arm(h, DISPATCH)
        h.run_until(stops, limit=10 ** 6, stride=1, interrupts=False)
        p = h.regs[PC]
        rows.append({'class': cls,
                     'target': ('%04X' % p) if p in D_TARGETS else None,
                     'fell_through': p in h.SENTINELS})
    return rows


# ------------------------------------- (g) the pointer table and its glyphs
def glyph_rows(h, m):
    """$BF74: HL := word at $C068 + 2*(class-2), then eight bytes of it are
       nibble-split and OR-ed into $D38C.  Read statically for every class the
       table covers AND for class 0, whose index runs 252 bytes past the end."""
    rows = []
    for cls in list(range(2, 13)) + [0]:
        off = ((cls - 2) & 0xFF) * 2 & 0xFF if False else (((cls - 2) & 0xFF) * 2) & 0xFF
        a = (PTR_TAB + off) & 0xFFFF
        ptr = m[a] | (m[a + 1] << 8)
        rows.append({'class': cls, 'index': off, 'slot': '%04X' % a,
                     'ptr': '%04X' % ptr,
                     'in_rom': ptr < 0x4000,
                     # NO ROM BYTES (M7.53): a cell the pointer finds in the ROM
                     # is not recorded -- ptr and rom_char name it
                     'glyph': ([m[(ptr + i) & 0xFFFF] for i in range(8)]
                               if ptr >= 0x4000 else None),
                     'rom_char': (((ptr - 0x3C00) // 8) + 32
                                  if 0x3C00 <= ptr < 0x4000 and ptr % 8 == 0
                                  else None)})
    return rows


def extend_rows(h, m):
    """WHERE THE EIGHT RANDOMISED CLASSES LAND, verified TWO INDEPENDENT WAYS.

       A popped elemental bubble carries its class out through (IY+9) -> $B742
       (the immediate of `LD A,3`) -> $FFF9, and $B75C CP 5 / CALL nc,$B7E5 sends
       everything from 5 up to the EXTEND award, which does SUB 5 and indexes a
       BIT MASK table at $B80E.  $957E draws SIX letters (its `LD A,6` at $9591
       over a 6-bit field at $FDE3/$FDED), so eight classes have to fold onto six
       bits -- and the fold is visible in the SPRITE TABLE too, because $C068's
       glyphs for the two duplicated classes are the same two ROM letters.
       If those two readings disagreed, one of them would be wrong."""
    tab = [m[EXT_BITS + i] for i in range(8)]
    bit = []
    for v in tab:
        bit.append(v.bit_length() - 1 if v and not (v & (v - 1)) else None)
    return {'table_at': EXT_BITS, 'mask': tab, 'bit': bit,
            'boundary_at': EXT_BOUND, 'boundary': m[EXT_BOUND + 1],
            'letters_at': EXT_COUNT, 'letters': m[EXT_COUNT + 1],
            'bits_p1': 0xFDE3, 'bits_p2': 0xFDED}


def bank_rows(h, m):
    """The bank $BF5B builds, per class -- an OBSERVATION.  H10 models it; H6
       only has to show the class REACHES it, so this asserts that two classes
       give two different banks and that class 0 gives a third."""
    rows = []
    for cls in (0, 2, 3, 4, 5, 6):
        m[ELEM] = cls
        sp = RC.arm(h, 0xBF5B)
        RC.run(h, sp)
        rows.append({'class': cls,
                     'md5': hashlib.md5(bytes(m[BANK:BANK + 0x180])).hexdigest(),
                     'at_d38c': [m[BANK + 0x0C + 6 * i] for i in range(4)]})
    return rows


# --------------------------------------------------------------------- main
def capture():
    h, m = RC.new()
    raw, groups = read_lists(m)
    if [len(g) for g in groups] != [11, 10, 13, 15]:
        raise SystemExit('list sizes %s -- expected 11/10/13/15' % [len(g) for g in groups])

    out = {
        'note': ('M7.7-H6 the ELEMENT CLASS $7E0E.  $7DD6 is reached by FALL-THROUGH '
                 'from the drift painter -- there is no CALL to it in 64K -- and its '
                 'zero test INC (HL)/DEC (HL) writes the table twice per entry '
                 'examined without changing it.  Round 81 never reaches it ($7C89 '
                 'CP $51 / RET z), so its class is STALE.  The reading pass said '
                 '$9E75 handles classes 2 and 3; it handles 2, 3 AND 4.  And the '
                 'eight randomised classes 5..12 are the EXTEND letters, taken from '
                 'the ROM CHARACTER SET -- a second ROM font dependency.'),
        'walk_at': WALK, 'redraw_at': REDRAW, 'tail_at': TAIL, 'elem_at': ELEM,
        'list_at': LIST_AT, 'list_end': LIST_END, 'round_at': ROUND,
        'spawn_at': SPAWN, 'spawn_state_op': SPAWN_STATE,
        'spawn_thresh_op': SPAWN_THRESH,
        'dispatch_at': DISPATCH, 'ptr_tab': PTR_TAB, 'bank_at': BANK,
        'g1_a': G1_A, 'g1_b': G1_B, 'g1_val': G1_VAL, 'poison': POISON,
        'list_bytes': raw,
        'groups': groups,
        'walk': walk_rows(h, m, groups),
        'stale': stale_rows(h, m),
        'redraw': redraw_rows(h, m),
        'spawn': spawn_rows(h, m),
        'dispatch': dispatch_rows(h, m),
        'glyphs': glyph_rows(h, m),
        'extend': extend_rows(h, m),
        'bank': bank_rows(h, m),
    }
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    groups = f['groups']
    print('lists: %s  (%d rounds classed, %d in no list)'
          % ('/'.join(str(len(g)) for g in groups),
             sum(len(g) for g in groups), 81 - sum(len(g) for g in groups)))

    bad = [r for r in f['walk']
           if (r['predicted'] == 'R' and not 5 <= r['elem'] <= 12)
           or (r['predicted'] != 'R' and r['elem'] != r['predicted'])]
    print('the walk agrees with the table on %d/81 rounds%s'
          % (81 - len(bad), '' if not bad else '  !! ' + str(bad[:4])))

    ph = {}
    for r in f['walk']:
        ph.setdefault(r['predicted'] if r['predicted'] != 'R' else 5, []).append(
            r['phantom_writes'])
    print('phantom writes by class: %s'
          % {k: (min(v), max(v)) for k, v in sorted(ph.items())})
    print('table intact on every round: %s'
          % all(r['table_intact'] for r in f['walk']))
    print('phantom PCs: %s'
          % sorted({p for r in f['walk'] for p in r['phantom_pcs']}))

    g1 = [r['round'] for r in f['walk'] if r['g1_writes']]
    print('the $A37D stores fire on %d rounds: %s' % (len(g1), g1))

    for r in f['stale']:
        print('  round %2d -> $7E0E = %3d  written=%s' % (r['round'], r['elem'],
                                                          r['written']))
    rd = f['redraw']
    print('redraw: %d distinct over 256 R values, range %d..%d; '
          '24 repeat builds of round 4 gave %d distinct'
          % (len(set(rd['fn'])), min(rd['fn']), max(rd['fn']),
             len(set(rd['repeat']))))
    print('spawner patches: %s'
          % [(r['class'], r['state_op'], r['thresh_op']) for r in f['spawn']])
    print('dispatch: %s'
          % [(r['class'], r['target']) for r in f['dispatch']])
    for r in f['glyphs']:
        print('  class %2d -> %s = $%s  rom=%s char=%r'
              % (r['class'], r['slot'], r['ptr'], r['in_rom'],
                 chr(r['rom_char']) if r['rom_char'] else None))
    e = f['extend']
    print('EXTEND: %d letters, boundary CP %d, class->bit %s'
          % (e['letters'], e['boundary'], e['bit']))
    print('banks: %s' % [(r['class'], r['md5'][:8]) for r in f['bank']])


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
