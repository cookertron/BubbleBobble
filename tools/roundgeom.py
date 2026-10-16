"""M7.7-H7 -- THE ROUND-RECORD WALKER AND THE GEOMETRY.

THE ASSET-EXTRACTION BINDING.  If this decode is wrong the port ships 81 wrong
maps, and because they are PLAUSIBLE-LOOKING maps nobody notices until an enemy
walks through a floor.

THE STRUCTURE, and the arithmetic that proves it closes:

  $8529  the SIZE PROBE.  ($8528) is the record cursor; $9F5C is RRA/RRA/RRA/
         AND $1F, so the byte is $8543 + (i >> 3), and `LD A,(i) / AND 7 /
         INC A / LD B,A / LD C,(HL) / RL C / DJNZ` leaves the CARRY holding
         BIT (7 - (i & 7)) -- MSB FIRST within each byte.
         CARRY SET = SHORT.  51 rounds short, 30 long.
  $848C  walks from $61A8 adding $27 (39) or $4D (77) per record until the
         cursor reaches ($8609) - 1, then probes ONCE MORE for the selected
         record and patches TWO OPERANDS from the answer:
             LONG   $84E5 := $1C (28 wide)   $8500 := 4     no mirror
             SHORT  $84E5 := $0E (14 wide)   $8500 := $12   then $850A
  $84D3  paints 22 rows from IX = $F842 -- ROW TWO, COLUMN TWO -- one cell per
         bit, $8309 for a 0 and $830A for a 1.
  $850A  mirrors columns 2..15 onto 29..16, REVERSED.

  AND THE BIT BUDGET CLOSES ON THE NOSE, which is why the records are 39 and 77:
      LONG   22 rows x 28 = 616 bits = 77.0 bytes exactly
      SHORT  22 rows x 14 = 308 bits = 38.5 -> 39 bytes, 4 bits spare
  51 x 39 + 30 x 77 = 4299, so the table runs $61A8..$7272 with EIGHT bytes of
  slack before $727B, and record index 80 (round 81) starts at $7226.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT THE BIT CURSOR RESTARTS EACH ROW.  IT DOES NOT.  E (bits left in C) is
    PUSHed and POPped around the row advance at $84FE/$8504 precisely so it
    SURVIVES.  The stream is CONTINUOUS across all 22 rows, and a port that
    re-aligns per row is right on row 1 and wrong from row 2 on -- so the gate
    compares CELL VALUES, never a row count.

  * THAT THE MIRROR CAN BE SEEN ON ANY ROUND.  It cannot: on a left-right
    symmetric record "28 wide direct", "14 wide + reversed mirror" and "14 wide +
    non-reversed mirror" ALL AGREE.  The gate finds rounds whose rows are
    ASYMMETRIC and reports how many, and drives all three models.

  * THAT A POKED RECORD BYTE CHANGES ANYTHING.  Round 1's first record byte is
    ALREADY $FF, so poking it to $FF is a no-op no byte comparison can see
    (TRAPS #44).  The poke is to $00, and the EXPECTED changed set is COMPUTED
    from the original byte's bits rather than asserted as a magic 16.

  * THAT ONE RECORD CLASS EXERCISES BOTH.  Whichever class a single build uses,
    the other's two self-modified operands are never written -- and that is
    visible in the images themselves: image_tape.bin holds $84E5 = $0E /
    $8500 = $0004 and image.bin (a round-80 dump) holds $1C / $0012, caught on
    opposite branches.  Round 1 is SHORT and round 81 is LONG; both are built and
    both operands are gated AS STATE.

  * THAT $8309/$830A SHOULD CARRY THEIR REAL VALUES HERE.  They are seeded to
    two SENTINELS instead, and the shadow to a third.  With the real palette,
    "this cell was never painted" and "this cell was painted OPEN" are the same
    byte over most of the map; with sentinels the three are three values.

Usage:  python tools/roundgeom.py capture
        python tools/roundgeom.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

WALK = 0x848C
PROBE = 0x8529
BITMAP, BITMAP_N = 0x8543, 11
TABLE = 0x61A8
TABLE_END = 0x727B                # the next thing after the records
SHORT_N, LONG_N = 0x27, 0x4D      # 39 / 77
CURSOR = 0x8528                   # ($8528) -- the record cursor
PTR = 0x84B7                      # the running pointer, an OPERAND of LD HL,(nn)
WIDTH_OP = 0x84E5                 # the operand of $84E4 LD B,n
ADV_OP = 0x8500                   # the operand of $84FF LD DE,nn
OPEN_AT, SOLID_AT = 0x8309, 0x830A
SHADOW = 0xF800
FIRST = 0xF842                    # row 2, column 2
LAST = 0xFAFD                     # row 23, column 29
ROUND = 0x8609
S_OPEN, S_SOLID, S_BG = 0x11, 0x22, 0x5A     # three distinguishable values
ROUNDS = (1, 2, 3, 20, 45, 56, 80, 81)
FIXTURE = 'build/roundgeom_fixture.json'


# ---------------------------------------------------- (a) the Python walk
def is_short(m, i):
    """$8529 in one line: bit (7 - (i & 7)) of byte $8543 + (i >> 3)."""
    return (m[BITMAP + (i >> 3)] >> (7 - (i & 7))) & 1


def layout(m):
    base, rows = TABLE, []
    for i in range(81):
        s = is_short(m, i)
        rows.append({'round': i + 1, 'base': base, 'size': SHORT_N if s else LONG_N,
                     'short': bool(s)})
        base += SHORT_N if s else LONG_N
    return rows, base


def paint_ref(m, row):
    """The reference map, as {address: bit}.  ONE CONTINUOUS BIT STREAM over all
       22 rows -- not 22 independent rows."""
    w = 14 if row['short'] else 28
    cells, bitpos = {}, 0
    for r in range(22):
        for c in range(w):
            byte = m[row['base'] + (bitpos >> 3)]
            cells[SHADOW + (2 + r) * 32 + 2 + c] = (byte >> (7 - (bitpos & 7))) & 1
            bitpos += 1
    if row['short']:                                  # $850A, REVERSED
        for r in range(22):
            for c in range(14):
                cells[SHADOW + (2 + r) * 32 + 29 - c] = \
                    cells[SHADOW + (2 + r) * 32 + 2 + c]
    return cells


def separability(m, rows):
    """WHICH ROUNDS CAN TELL THE THREE MODELS APART -- and they are not the same
       rounds, which is the whole trap.

       MY FIRST VERSION COUNTED THE WRONG THING.  It asked how many rounds have a
       left-right ASYMMETRIC finished map, got 30, and that number is just "the
       30 LONG rounds": a short round is symmetric BY CONSTRUCTION, because the
       mirror is what makes it so.  It proves LONG does not mirror and says
       NOTHING about the mirror's REVERSAL, which is the part that can be wrong.

       The reversal is observable only on a SHORT round with a row that is not a
       PALINDROME -- there cell 2+k differs from cell 16+k, so "reversed" and
       "straight" disagree.  Both counts are reported."""
    long_asym = short_nonpal = 0
    straight_diff = wide_diff = 0
    for row in rows:
        c = paint_ref(m, row)
        if not row['short']:
            for r in range(22):
                b = SHADOW + (2 + r) * 32
                if any(c[b + 2 + k] != c[b + 29 - k] for k in range(14)):
                    long_asym += 1
                    break
            continue
        hit = False
        for r in range(22):
            b = SHADOW + (2 + r) * 32
            # a STRAIGHT mirror would put cell 2+k at 16+k, not 29-k
            for k in range(14):
                if c[b + 2 + k] != c[b + 2 + (13 - k)]:
                    straight_diff += 1
                    hit = True
        if hit:
            short_nonpal += 1
    # and the THIRD model: reading 28 bits per row off a 39-byte record walks
    # off the end of it, which is its own observable
    for row in rows:
        if row['short']:
            wide_diff += 1 if (22 * 28 + 7) // 8 > row['size'] else 0
    return {'long_asymmetric': long_asym, 'short_nonpalindromic': short_nonpal,
            'straight_vs_reversed_cells': straight_diff,
            'short_records_too_small_for_28_wide': wide_diff}


# ------------------------------------------------- (b) the machine, per round
def seed(h, m, rnd):
    m[ROUND] = rnd
    m[OPEN_AT], m[SOLID_AT] = S_OPEN, S_SOLID
    for i in range(0x300):
        m[SHADOW + i] = S_BG
    m[WIDTH_OP] = 0x99                       # neither $1C nor $0E
    m[ADV_OP], m[ADV_OP + 1] = 0x99, 0x99    # neither 4 nor $12
    m[CURSOR] = 0x99
    m[PTR], m[PTR + 1] = 0x99, 0x99


def build(h, m, rnd, watch=True):
    seed(h, m, rnd)
    if watch:
        h.memobj.watch(SHADOW, SHADOW + 0x300)
    sp = RC.arm(h, WALK)
    RC.run(h, sp)
    log = list(h.memobj.log) if watch else []
    if watch:
        h.memobj.unwatch()
    return {
        'round': rnd,
        'cursor': m[CURSOR],
        'ptr': m[PTR] | (m[PTR + 1] << 8),
        'width_op': m[WIDTH_OP],
        'adv_op': m[ADV_OP] | (m[ADV_OP + 1] << 8),
        'writes': len(log),
        'lo': min((a for (_p, a, _v) in log), default=0),
        'hi': max((a for (_p, a, _v) in log), default=0),
        'pcs': sorted({'%04X' % p for (p, _a, _v) in log}),
        'map': [m[SHADOW + i] for i in range(0x300)],
    }


def compare(m, rows, row_out):
    """Cell by cell against the Python walk -- and the cells the walker must NOT
       touch counted separately, because a painter that runs two columns wide is
       invisible to a check on the ones it was supposed to write."""
    r = [x for x in rows if x['round'] == row_out['round']][0]
    want = paint_ref(m, r)
    wrong = untouched_bad = 0
    for i in range(0x300):
        a = SHADOW + i
        got = row_out['map'][i]
        if a in want:
            if got != (S_SOLID if want[a] else S_OPEN):
                wrong += 1
        elif got != S_BG:
            untouched_bad += 1
    return wrong, untouched_bad


# ------------------------------------------------------- (c) the mutation
def poke_rows(h, m, rows):
    """A record byte poked to $00 -- NOT $FF, which round 1 already holds.  The
       expected changed set is COMPUTED from the original byte."""
    out = []
    for rnd in (1, 81):
        r = [x for x in rows if x['round'] == rnd][0]
        base = r['base']
        orig = m[base]
        clean = build(h, m, rnd, watch=False)['map']
        m[base] = 0x00
        dirty = build(h, m, rnd, watch=False)['map']
        m[base] = orig
        changed = sorted(SHADOW + i for i in range(0x300) if clean[i] != dirty[i])
        # what SHOULD change: the first 8 cells of row 2 whose bit was 1, and
        # (short records only) their mirrors
        want = []
        for k in range(8):
            if (orig >> (7 - k)) & 1:
                want.append(SHADOW + 2 * 32 + 2 + k)
                if r['short']:
                    want.append(SHADOW + 2 * 32 + 29 - k)
        out.append({'round': rnd, 'base': base, 'orig': orig,
                    'changed': ['%04X' % a for a in changed],
                    'expected': ['%04X' % a for a in sorted(want)],
                    'agree': changed == sorted(want)})
    return out


# ------------------------------------------------------------------- main
def capture():
    h, m = RC.new()
    tape = bytearray(open('build/image_tape.bin', 'rb').read())
    if bytes(tape[BITMAP:BITMAP + BITMAP_N]) != bytes(m[BITMAP:BITMAP + BITMAP_N]):
        raise SystemExit('the size bitmap differs between the images (TRAPS #43)')
    if not any(tape[BITMAP:BITMAP + BITMAP_N]):
        raise SystemExit('the size bitmap is all zero -- wrong image')

    rows, end = layout(m)
    builds = [build(h, m, r) for r in ROUNDS]
    for b in builds:
        b['wrong'], b['untouched_bad'] = compare(m, rows, b)
        del b['map']

    out = {
        'note': ('M7.7-H7 the ROUND-RECORD WALKER.  $8529 probes bit (7 - (i & 7)) of '
                 '$8543 + (i >> 3); a SET carry means a 39-byte SHORT record painted '
                 '14 wide and MIRRORED, a clear one a 77-byte LONG record painted 28 '
                 'wide.  The bit stream is CONTINUOUS across all 22 rows.  The two '
                 'width/advance operands are STATE, and a build of one class never '
                 'writes the other class\'s pair.'),
        'walk_at': WALK, 'probe_at': PROBE, 'bitmap_at': BITMAP,
        'table_at': TABLE, 'table_end': TABLE_END,
        'cursor_at': CURSOR, 'ptr_at': PTR,
        'width_op_at': WIDTH_OP, 'adv_op_at': ADV_OP,
        'open_at': OPEN_AT, 'solid_at': SOLID_AT,
        'first': FIRST, 'last': LAST,
        's_open': S_OPEN, 's_solid': S_SOLID, 's_bg': S_BG,
        'bitmap': [m[BITMAP + i] for i in range(BITMAP_N)],
        'layout': rows,
        'end': end,
        'slack': TABLE_END - end,
        'n_short': sum(1 for r in rows if r['short']),
        'n_long': sum(1 for r in rows if not r['short']),
        'separable': separability(m, rows),
        'builds': builds,
        'poke': poke_rows(h, m, rows),
        'img_tape_ops': {'width': tape[WIDTH_OP],
                         'adv': tape[ADV_OP] | (tape[ADV_OP + 1] << 8)},
    }
    live = bytearray(open('build/image.bin', 'rb').read())
    out['img_live_ops'] = {'width': live[WIDTH_OP],
                           'adv': live[ADV_OP] | (live[ADV_OP + 1] << 8)}
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    print('%d SHORT (39B, 14 wide + mirror) + %d LONG (77B, 28 wide); table '
          '$%04X..$%04X, %d bytes slack before $%04X'
          % (f['n_short'], f['n_long'], f['table_at'], f['end'] - 1, f['slack'],
             f['table_end']))
    print('record index 80 (round 81) base $%04X' % f['layout'][80]['base'])
    sp = f['separable']
    print('separability: %d LONG rounds are left-right ASYMMETRIC (so LONG does not '
          'mirror); %d SHORT rounds have a NON-PALINDROMIC row, disagreeing with a '
          'STRAIGHT mirror in %d cells; and all %d short records are TOO SMALL to '
          'hold 28 bits x 22 rows'
          % (sp['long_asymmetric'], sp['short_nonpalindromic'],
             sp['straight_vs_reversed_cells'],
             sp['short_records_too_small_for_28_wide']))
    print('the two operands as found in the images: tape %s   live(round 80) %s'
          % (f['img_tape_ops'], f['img_live_ops']))
    for b in f['builds']:
        r = f['layout'][b['round'] - 1]
        print('  round %2d %-5s ptr $%04X (base $%04X + %d)  cursor %2d  width $%02X '
              'adv $%04X  writes %d $%04X..$%04X  wrong %d  spill %d'
              % (b['round'], 'SHORT' if r['short'] else 'LONG', b['ptr'],
                 r['base'], r['size'], b['cursor'], b['width_op'], b['adv_op'],
                 b['writes'], b['lo'], b['hi'], b['wrong'], b['untouched_bad']))
    for p in f['poke']:
        print('  poke round %2d base $%04X ($%02X -> $00): %d cells changed, '
              'expected %d, agree %s'
              % (p['round'], p['base'], p['orig'], len(p['changed']),
                 len(p['expected']), p['agree']))


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
