"""M7.7-H8 -- THE PLATFORM TILE, THE WALLS, AND THE ORDER DEPENDENCY.

H7 turned 81 records into 616 COLLISION cells.  This is what turns those cells
into PIXELS, and it is where the two write modes live.

  $83EB  the tile INDEX.  $83EC is the operand of LD A,n and is LIVE STATE -- a
         BUILD counter mod 5, carried and never recomputed from $8609 -- and
         ($860D) := $6180 + 8 * idx.  Five 8-byte patterns (H0: tape data at
         $E680..$E6A7, relocated to $6180 at cold start).
  $830B  paints column 2 of all 22 shadow rows $A0/$50 alternating, then LDIs the
         eight tile bytes into the EVEN bytes of $856C.  `LD C,$FF` IS LOOP
         CONTROL: LDI does a SIXTEEN-BIT DEC BC, so a C that could wrap would
         borrow into B and cost the DJNZ a count (TRAPS #45).
  $824A  the 16x12 blit, per solid cell, over the colour shadow from $F842.
         *** TWO WRITE MODES IN ONE ROUTINE ***
             main 8 rows:  $8288 LD (HL),A  STORE the left byte
                           $828C OR (HL)    OR    the right byte
             tail 4 rows:  $82A6 and $82AB  OR    BOTH
         and the LAST map row SKIPS THE TAIL ($8296 DEC L / JR z), so a cell
         there writes 16 bytes and not 24.
  $82C5  fires EXACTLY ONCE, on the CALL z after the FIRST row (A is still $16),
         and rewrites three odd bytes of the tile buffer.
  $8390  builds the 32-byte wall pattern at $5B00, two expansions chosen by
         ($860C).
  $833A  draws ONE wall, and $833B is BOTH STATE AND ARGUMENT: LD A,$1E / XOR
         $1E toggles it between $1E and $00, which is also the COLUMN.
  $837A  marks columns 0, 1, 30 and 31 SOLID in the collision map, 22 rows --
         H7's four unowned columns, filled here.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT A CHECKSUM OVER THE SHADOW MEANS ANYTHING.  $9858 hands the builder a
    ZEROED buffer and $7F62 covers only 2,248 of 6,144 addresses, so 63% of a
    whole-shadow checksum certifies bytes nobody wrote.  The shadow is PRE-FILLED
    $5A and the gate asserts the VALUE at every address AND the exact COVERAGE
    SET.

  * THAT `OR (HL)` CAN BE SEEN AT ALL.  TWO OF THE THREE SITES ARE UNOBSERVABLE
    against the machine's own build, and on round 1 both are: the scan runs
    left-to-right, so cell c's OR'd right byte is immediately STORED over by cell
    c+1's left byte, and at a run's right edge the target is still zero, where
    OR == STORE.  This drives the blit over a background the tile DISAGREES with
    ($FF under $00 bytes), which is the only way the distinction appears.

  * THAT $856C IS EIGHT BYTES, OR SIXTEEN.  It has been read three ways.  DE runs
    CONTINUOUSLY through both loops -- 8 rows x 2 plus 4 rows x 2 -- so it is
    TWENTY-FOUR, and the gate seeds 24 DISTINCT bytes so every one is pinned to a
    position rather than summed into a checksum.

  * THAT THE WALL ORDER SHOWS UP IN A COUNT.  It does not: both orders leave the
    same number of non-zero bytes in columns 30 and 31.  The gate compares BYTES.

Usage:  python tools/roundtile.py capture
        python tools/roundtile.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

BLIT = 0x824A
TOPROW = 0x82C5
IDX = 0x83EB
IDX_OP = 0x83EC
TILE_PTR = 0x860D
TILE_AT = 0x6180
PREP = 0x830B
WALL = 0x833A
WALL_OP = 0x833B
WALL_PAT = 0x8390
WALL_BUF = 0x5B00
COLL_WALLS = 0x837A
BUILD = 0x7F62
BUF, BUF_N = 0x856C, 24
SHADOW, SHADOW_N = 0xE000, 0x1800
COLOUR = 0xF800
OPEN_AT, SOLID_AT = 0x8309, 0x830A
EXPAND_SEL = 0x860C
ROUND = 0x8609
ROW_TAB = 0xFD44
S_OPEN, S_SOLID, S_BG = 0x11, 0x22, 0x5A
FIXTURE = 'build/roundtile_fixture.json'


def clear_colour(m, v):
    for i in range(0x300):
        m[COLOUR + i] = v


def clear_shadow(m, v):
    for i in range(SHADOW_N):
        m[SHADOW + i] = v


# ------------------------------------------------------ (a) the tile index
def index_rows(h, m):
    """$83EC is an OPERAND and a BUILD counter mod 5 -- never recomputed from the
       round, which H0 already gates.  Driven twelve times to catch the wrap
       twice."""
    m[IDX_OP] = 0
    out = []
    for _ in range(12):
        sp = RC.arm(h, IDX)
        RC.run(h, sp)
        out.append({'op': m[IDX_OP],
                    'ptr': m[TILE_PTR] | (m[TILE_PTR + 1] << 8)})
    return out


# -------------------------------------- (b) the buffer, 24 bytes and ordered
def single_cell(h, m, row, col, seeds=True):
    """ONE solid cell in an otherwise open map, over a ZEROED shadow, with the
       tile buffer seeded 24 DISTINCT bytes so every write pins a position."""
    m[OPEN_AT], m[SOLID_AT] = S_OPEN, S_SOLID
    clear_colour(m, S_OPEN)
    m[COLOUR + row * 32 + col] = S_SOLID
    clear_shadow(m, 0x00)
    if seeds:
        for i in range(BUF_N):
            m[BUF + i] = i + 1                       # $01..$18, none of them $A0/$50
    h.memobj.watch(SHADOW, SHADOW + SHADOW_N)
    sp = RC.arm(h, BLIT)
    RC.run(h, sp)
    log = [('%04X' % p, '%04X' % a, v) for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    return log


def buffer_rows(h, m):
    """And the $856C region's OWN writes: three at $824A's entry and three more
       from $82C5, which fires once after the first row."""
    m[OPEN_AT], m[SOLID_AT] = S_OPEN, S_SOLID
    clear_colour(m, S_OPEN)
    clear_shadow(m, 0x00)
    for i in range(BUF_N):
        m[BUF + i] = 0x5A
    h.memobj.watch(BUF, BUF + BUF_N)
    sp = RC.arm(h, BLIT)
    RC.run(h, sp)
    log = [('%04X' % p, '%04X' % a, v) for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    return log


# ------------------------------------------------- (c) STORE versus OR
def store_vs_or(h, m, row, col):
    """The ONLY configuration in which the distinction is visible: a background
       the tile bytes DISAGREE with.  Shadow all $FF, tile bytes $00.
       LEFT byte STORED  -> $00 wins
       RIGHT byte OR'd   -> $FF survives
       and in the TAIL both are OR'd, so BOTH stay $FF."""
    m[OPEN_AT], m[SOLID_AT] = S_OPEN, S_SOLID
    clear_colour(m, S_OPEN)
    m[COLOUR + row * 32 + col] = S_SOLID
    clear_shadow(m, 0xFF)
    for i in range(BUF_N):
        m[BUF + i] = 0x00
    h.memobj.watch(SHADOW, SHADOW + SHADOW_N)
    sp = RC.arm(h, BLIT)
    RC.run(h, sp)
    log = [('%04X' % p, '%04X' % a, v) for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    zeroed = sum(1 for (_p, _a, v) in log if v == 0x00)
    return {'writes': len(log), 'zeroed': zeroed,
            'kept_ff': len(log) - zeroed,
            'by_pc': {k: sum(1 for (p, _a, v) in log if p == k and v == 0)
                      for k in sorted({p for (p, _a, _v) in log})},
            'log': log}


def prep_rows(h, m):
    """$830B ALONE -- column 2 of every shadow row, then the LDI into the buffer.
       Gated separately because a whole build hides it: the tile blit writes over
       most of what it lays down."""
    m[IDX_OP] = 0
    sp = RC.arm(h, IDX)
    RC.run(h, sp)
    clear_shadow(m, S_BG)
    for i in range(BUF_N):
        m[BUF + i] = 0x5A
    h.memobj.watch(SHADOW, SHADOW + SHADOW_N)
    sp = RC.arm(h, PREP)
    RC.run(h, sp)
    log = [('%04X' % p_, '%04X' % a, v) for (p_, a, v) in h.memobj.log]
    h.memobj.unwatch()
    return {'writes': len(log),
            'cols': sorted({int(a, 16) & 0x1F for (_p, a, _v) in log}),
            'vals': sorted({v for (_p, _a, v) in log}),
            'lo': min(int(a, 16) for (_p, a, _v) in log),
            'hi': max(int(a, 16) for (_p, a, _v) in log),
            'first8': [('%04X' % (int(log[k][1], 16)), log[k][2]) for k in range(8)],
            'buf': [m[BUF + i] for i in range(BUF_N)]}


def wall_ordered(h, m):
    """$833A with the wall buffer seeded THIRTY-TWO DISTINCT bytes, so every one
       of the 352 writes pins a source position.  A UNIFORM buffer cannot tell
       "reads $5B00..$5B1F once per row pair" from "restarts at $5B00 for each of
       the two calls", and cannot tell a STORE from an OR either."""
    clear_shadow(m, S_BG)
    for i in range(0x20):
        m[WALL_BUF + i] = 0x80 | i                  # $80..$9F, distinct, and OR-able
    m[WALL_OP] = 0x1E
    h.memobj.watch(SHADOW, SHADOW + SHADOW_N)
    sp = RC.arm(h, WALL)
    RC.run(h, sp)
    log = [('%04X' % a, v) for (_p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    return {'writes': len(log), 'log': log,
            'cols': sorted({int(a, 16) & 0x1F for (a, _v) in log}),
            'op_out': m[WALL_OP]}


# ------------------------------------------------ (d) a whole build, covered
def whole_build(h, m, rnd, wall_op=None, tile_idx=0, pal_idx=0, count_walls=False):
    """*** PIN EVERY CARRIED COUNTER. ***  My first version of the order
       experiment ran the two builds one after the other and got 1,556 differing
       bytes across all 32 columns -- because $83EC (the TILE INDEX) and $82D7
       (the PALETTE INDEX) are BUILD counters, not round numbers (H0), so the
       second build drew a DIFFERENT TILE in a DIFFERENT COLOUR.  The wall order
       was the one thing that experiment did not isolate.  Both are pinned here,
       which is also the only way $860C's branch is under the gate's control."""
    m[ROUND] = rnd
    m[IDX_OP] = tile_idx
    m[0x82D7] = pal_idx
    clear_shadow(m, S_BG)
    if wall_op is not None:
        m[WALL_OP] = wall_op
    walls = 0
    h.memobj.watch(SHADOW, SHADOW + SHADOW_N)
    sp = RC.arm(h, BUILD)
    if count_walls:
        stops = {WALL} | set(h.SENTINELS)
        while True:
            h.run_until(stops, limit=40 * 10 ** 6, stride=1, interrupts=True)
            if h.regs[PC] in h.SENTINELS:
                break
            walls += 1
            h.step(1, interrupts=True)
        if h.regs[PC] not in h.SENTINELS or h.SENTINELS.index(h.regs[PC]) != 0:
            raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
    else:
        RC.run(h, sp)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    cover = sorted({a for (_p, a, _v) in log})
    return {'round': rnd, 'wall_op_in': wall_op, 'walls': walls,
            'writes': len(log), 'covered': len(cover),
            'untouched': SHADOW_N - len(cover),
            'wall_op_out': m[WALL_OP], 'idx_op': m[IDX_OP],
            'expand_sel': m[EXPAND_SEL],
            'shadow': [m[SHADOW + i] for i in range(SHADOW_N)],
            'cover': cover}


def order_rows(h, m):
    """THE ORDER DEPENDENCY.  $833B is state AND argument, so the two walls are
       drawn in whichever order the carried byte dictates.  Two whole builds of
       the same round, started from the two values -- and the gate compares
       BYTES, because both orders leave the same non-zero COUNTS."""
    a = whole_build(h, m, 2, wall_op=0x1E, tile_idx=0, pal_idx=0, count_walls=True)
    b = whole_build(h, m, 2, wall_op=0x00, tile_idx=0, pal_idx=0, count_walls=True)
    diff = [i for i in range(SHADOW_N) if a['shadow'][i] != b['shadow'][i]]
    cols = sorted({(SHADOW + i) & 0x1F for i in diff})

    def nz(row, c):
        return sum(1 for i in range(SHADOW_N)
                   if ((SHADOW + i) & 0x1F) == c and row['shadow'][i])
    return {'differing': len(diff), 'columns': cols,
            'diff_at': ['%04X' % (SHADOW + i) for i in diff],
            'diff_vals': [[a['shadow'][i], b['shadow'][i]] for i in diff],
            'nonzero_30': [nz(a, 30), nz(b, 30)],
            'nonzero_31': [nz(a, 31), nz(b, 31)],
            'counts_identical': nz(a, 30) == nz(b, 30) and nz(a, 31) == nz(b, 31),
            'a_op_out': a['wall_op_out'], 'b_op_out': b['wall_op_out'],
            'walls_per_build': [a['walls'], b['walls']],
            'a_cols_bg': sorted({(SHADOW + i) & 0x1F for i in range(SHADOW_N)
                                 if a['shadow'][i] == S_BG and
                                 ((SHADOW + i) & 0x1F) in (0, 1, 30, 31)}),
            'b_cols_bg': sorted({(SHADOW + i) & 0x1F for i in range(SHADOW_N)
                                 if b['shadow'][i] == S_BG and
                                 ((SHADOW + i) & 0x1F) in (0, 1, 30, 31)})}


# ------------------------------------------------ (e) the wall pattern + walls
def expand_rows(h, m):
    """$8390's two branches, selected by ($860C).  The interleave at $83B4 is
       UNREACHABLE FROM ROUND 1: $860C is 0 for eleven rounds and round 1 is one
       of them, so a round-1 gate exercises the MINORITY path only."""
    out = []
    for sel in (0, 1, 0x80):
        m[EXPAND_SEL] = sel
        m[IDX_OP] = 0
        sp = RC.arm(h, IDX)
        RC.run(h, sp)
        for i in range(0x20):
            m[WALL_BUF + i] = 0x5A
        h.memobj.watch(WALL_BUF, WALL_BUF + 0x20)
        sp = RC.arm(h, WALL_PAT)
        RC.run(h, sp)
        log = [('%04X' % p, '%04X' % a, v) for (p, a, v) in h.memobj.log]
        h.memobj.unwatch()
        out.append({'sel': sel, 'writes': len(log),
                    'buf': [m[WALL_BUF + i] for i in range(0x20)],
                    'pcs': sorted({p for (p, _a, _v) in log}),
                    'src': [m[TILE_AT + i] for i in range(8)]})
    return out


def coll_wall_rows(h, m):
    """$837A: columns 0, 1, 30 and 31 of all 22 rows, SOLID -- H7's four unowned
       columns.  Seeded to a third value so "written" and "already solid" are
       separable."""
    m[OPEN_AT], m[SOLID_AT] = S_OPEN, S_SOLID
    clear_colour(m, S_BG)
    h.memobj.watch(COLOUR, COLOUR + 0x300)
    sp = RC.arm(h, COLL_WALLS)
    RC.run(h, sp)
    log = [a for (_p, a, _v) in h.memobj.log]
    h.memobj.unwatch()
    return {'writes': len(log),
            'cols': sorted({a & 0x1F for a in log}),
            'rows': sorted({(a - COLOUR) >> 5 for a in log}),
            'all_solid': all(m[a] == S_SOLID for a in log),
            'others_clean': all(m[COLOUR + i] == S_BG for i in range(0x300)
                                if (COLOUR + i) not in log)}


# --------------------------------------------------------------------- main
def capture():
    h, m = RC.new()
    rows24 = single_cell(h, m, 2, 2)
    rows16 = single_cell(h, m, 23, 2)
    out = {
        'note': ('M7.7-H8 the PLATFORM TILE.  $824A has TWO WRITE MODES -- STORE on '
                 'the left byte and OR on the right in the main 8 rows, OR on BOTH in '
                 'the 4-row tail -- and the last map row skips the tail.  $856C is a '
                 'TWENTY-FOUR byte buffer walked continuously by DE.  $833B is state '
                 'AND argument, so the wall ORDER is carried between builds.'),
        'blit_at': BLIT, 'toprow_at': TOPROW, 'idx_at': IDX, 'idx_op_at': IDX_OP,
        'tile_ptr_at': TILE_PTR, 'tile_at': TILE_AT, 'prep_at': PREP,
        'wall_at': WALL, 'wall_op_at': WALL_OP, 'wall_pat_at': WALL_PAT,
        'wall_buf_at': WALL_BUF, 'coll_walls_at': COLL_WALLS, 'build_at': BUILD,
        'buf_at': BUF, 'buf_n': BUF_N, 'shadow_at': SHADOW, 'shadow_n': SHADOW_N,
        'expand_sel_at': EXPAND_SEL, 'colour_at': COLOUR,
        'row_tab_at': ROW_TAB, 's_open': S_OPEN, 's_solid': S_SOLID, 's_bg': S_BG,
        'tile_bytes': [m[TILE_AT + i] for i in range(40)],
        'row_tab': [m[ROW_TAB + 2 * i] | (m[ROW_TAB + 2 * i + 1] << 8)
                    for i in range(22)],
        'index': index_rows(h, m),
        'cell24': rows24,
        'cell16': rows16,
        'buffer': buffer_rows(h, m),
        'prep': prep_rows(h, m),
        'wall_ordered': wall_ordered(h, m),
        'store_or': store_vs_or(h, m, 2, 2),
        'expand': expand_rows(h, m),
        'coll_walls': coll_wall_rows(h, m),
        'order': order_rows(h, m),
    }
    builds = []
    for (rnd, pal) in ((1, 0), (2, 0), (5, 1), (2, 1)):
        b = whole_build(h, m, rnd, wall_op=0x1E, tile_idx=0, pal_idx=pal)
        b['nonzero'] = sum(1 for v in b['shadow'] if v not in (0, S_BG))
        b['left_bg'] = sum(1 for v in b['shadow'] if v == S_BG)
        b['pal_idx'] = pal
        del b['shadow'], b['cover']
        builds.append(b)
    out['builds'] = builds
    # THE TWO EXPANSIONS, SAME ROUND, EVERYTHING ELSE PINNED: if these agreed,
    # the branch would be unobservable and $860C untestable through a build.
    x0 = whole_build(h, m, 2, wall_op=0x1E, tile_idx=0, pal_idx=0)
    x1 = whole_build(h, m, 2, wall_op=0x1E, tile_idx=0, pal_idx=1)
    d = [i for i in range(SHADOW_N) if x0['shadow'][i] != x1['shadow'][i]]
    out['expand_build'] = {
        'sel': [x0['expand_sel'], x1['expand_sel']],
        'differing': len(d),
        'columns': sorted({(SHADOW + i) & 0x1F for i in d}),
    }
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    print('tile index $83EC: %s' % [r['op'] for r in f['index']])
    print('  ($860D): %s' % ['%04X' % r['ptr'] for r in f['index'][:6]])
    print('one solid cell, row 2  -> %d writes, PCs %s'
          % (len(f['cell24']), sorted({p for (p, _a, _v) in f['cell24']})))
    print('one solid cell, row 23 -> %d writes, PCs %s'
          % (len(f['cell16']), sorted({p for (p, _a, _v) in f['cell16']})))
    print('  ordered values: %s' % ' '.join('%02X' % v for (_p, _a, v) in f['cell24']))
    print('$856C region writes: %d  %s'
          % (len(f['buffer']),
             ' '.join('%s->%s=%02X' % (p, a, v) for (p, a, v) in f['buffer'])))
    so = f['store_or']
    print('STORE vs OR over an $FF background: %d writes, %d wrote $00 (STORE), '
          '%d kept $FF (OR).  zeros by PC: %s'
          % (so['writes'], so['zeroed'], so['kept_ff'], so['by_pc']))
    for e in f['expand']:
        print('  $8390 sel=$%02X -> %d writes, PCs %s' % (e['sel'], e['writes'], e['pcs']))
        print('     buf %s' % ' '.join('%02X' % v for v in e['buf']))
    pr = f['prep']
    print('$830B: %d shadow writes, columns %s, values %s, $%04X..$%04X; buffer %s'
          % (pr['writes'], pr['cols'], ['%02X' % v for v in pr['vals']], pr['lo'],
             pr['hi'], ' '.join('%02X' % v for v in pr['buf'])))
    wo = f['wall_ordered']
    print('$833A over 32 DISTINCT buffer bytes: %d writes, columns %s, first 8 %s'
          % (wo['writes'], wo['cols'],
             ' '.join('%s=%02X' % (a, v) for (a, v) in wo['log'][:8])))
    cw = f['coll_walls']
    print('$837A: %d collision writes, columns %s, rows %d..%d, all solid %s, '
          'nothing else touched %s'
          % (cw['writes'], cw['cols'], min(cw['rows']), max(cw['rows']),
             cw['all_solid'], cw['others_clean']))
    o = f['order']
    print('WALL ORDER (%s $833A call(s) per build): %d differing bytes, columns %s; '
          'non-zero col 30 %s, col 31 %s, counts identical %s'
          % (o['walls_per_build'], o['differing'], o['columns'], o['nonzero_30'],
             o['nonzero_31'], o['counts_identical']))
    print('  columns left UNWRITTEN ($5A): order A %s, order B %s'
          % (o['a_cols_bg'], o['b_cols_bg']))
    eb = f.get('expand_build')
    if eb:
        print('$8390 branch through a WHOLE build ($860C %s): %d differing bytes in columns %s'
              % (eb['sel'], eb['differing'], eb['columns']))
    for b in f['builds']:
        print('  round %2d pal %d: %d writes covering %d of %d shadow bytes (%d never '
              'written, %d still $5A), $860C=%d, $83EC=%d'
              % (b['round'], b['pal_idx'], b['writes'], b['covered'], f['shadow_n'],
                 b['untouched'], b['left_bg'], b['expand_sel'], b['idx_op']))


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
