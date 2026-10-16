"""B4 -- THE BOSS DRAW AND ERASE, AND $9D4C's RECONSTRUCTION.

THE ERASE DOES NOT RESTORE THE ATTRIBUTES.  IT RECONSTRUCTS THEM.  $9D4C reads
BIT 5 of the COLOUR SHADOW and writes ($8309) or ($830A) -- the round's open and
solid attributes -- into the DISPLAY.  On a captured world the cells already
hold what it writes, so "restores from the shadow" and "reconstructs from the
palette pair" are the same function there.  The separator is a POISONED PAIR:
$8309 := $5A and $830A := $A5, two values no round palette produces.

AND THE DRAFTED CONTROLS CANNOT FAIL, which the H13 falsification pass caught
before this file existed.  Every natural row is UNIFORM -- all sixteen cells
clear on boss/bosskilled/bossspawn -- so a port reading bit 5 from the wrong
address (wrong stride, wrong page wrap, the DISPLAY attributes instead of
$F8xx) is byte-identical on all of them and on both uniform controls.  Only
bosshit discriminates, and only in four of sixteen cells.  So the world this
oracle gates on is a CHECKERBOARD: bit 5 = (row + col) & 1 over the whole
colour shadow, which makes every one of the sixteen cells discriminating and
the written value a pure function of the shadow bit AT THAT CELL.

TWO MORE THINGS A DIFF CANNOT SEE:
  * seeded $5A -- the value $9D4C writes -- the same sixteen writes report as
    ZERO changed bytes.  TRAPS #44, and it is cheaper to demonstrate here than
    anywhere else in the range.
  * on bossspawn ($A839 = 0) rows 0 and 1 BOTH divert through the $FD00 guard's
    $01FF and land on the SAME four cells, so SIXTEEN writes show as TWELVE
    distinct addresses.  The count has to come from a LOG.

Usage:  python tools/bossdraw.py    (capture -> build/bossdraw_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bossdraw_fixture.json'
BRANCH_BYTE = 0x8DC4
DRAW = 0xA8C1
ERASE = 0xA9DA
ROW_ERASE = 0xA929
ATTR_ERASE = 0xA951
RECON = 0x9D4C

BOSS_Y, BOSS_X, BOSS_XH = 0xA839, 0xA8DB, 0xA8DC
OPEN, SOLID = 0x8309, 0x830A
SPR_PTR = 0xA8C2                 # $A8C1 LD DE,nn -- the sprite source
ATTR_PTR = 0xA8FD                # $A8FC LD DE,nn -- the attribute block
CLASS = 0xA85C
SHADOW = 0xF800                  # the colour shadow
ATTRS = 0x5800


def new(state='boss', contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, sp=0x96DD):
    r = h.sim.registers
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def call_logged(h, addr, lo=0x4000, hi=0x10000):
    """one call, interrupts OFF, SP pinned, with the WRITE LOG -- never a diff."""
    h.memobj.watch(lo, hi)
    arm(h, addr)
    h.run_until(tuple(h.SENTINELS), limit=2_000_000, stride=1, interrupts=False)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('no sentinel -- PC $%04X' % h.regs[PC])
    return log


def checkerboard(m, bit5=True):
    """bit 5 = (row + col) & 1 over all 768 cells of the colour shadow.  A
       UNIFORM world cannot tell a right address from a wrong one; this one
       can, because every neighbour differs."""
    for row in range(24):
        for col in range(32):
            v = 0x20 if ((row + col) & 1) == (1 if bit5 else 0) else 0x00
            m[SHADOW + 32 * row + col] = v


# ---------------------------------------------------------------- phase A
def phase_reconstruct():
    """$A9DA with the palette pair POISONED, over the natural states and over
       the worlds that can actually separate the models."""
    out = {}
    worlds = [('boss', None), ('bosshit', None), ('bosskilled', None),
              ('bossspawn', None),
              ('uniform_00', 0x00), ('uniform_20', 0x20),
              ('checker_0', 'c0'), ('checker_1', 'c1')]
    for (name, mode) in worlds:
        st = name if mode is None else 'boss'
        h, m = new(st)
        m[OPEN], m[SOLID] = 0x5A, 0xA5
        if mode == 'c0':
            checkerboard(m, False)
        elif mode == 'c1':
            checkerboard(m, True)
        elif mode is not None:
            for i in range(768):
                m[SHADOW + i] = mode
        for i in range(768):
            m[ATTRS + i] = 0xFF            # a value $9D4C never writes
        log = call_logged(h, ERASE, 0x5800, 0x5B00)
        cells = [['$%04X' % a, v] for (_, a, v) in log]
        out[name] = {'state': st, 'x': m[BOSS_X], 'y': m[BOSS_Y],
                     'writes': len(log), 'distinct': len(set(a for (_, a, _) in log)),
                     'cells': cells,
                     'values': sorted(set(v for (_, a, v) in log)),
                     'n_solid': sum(1 for (_, _, v) in log if v == 0xA5),
                     'n_open': sum(1 for (_, _, v) in log if v == 0x5A)}
    return out


# ---------------------------------------------------------------- phase B
def phase_diff_blind():
    """THE TRAPS #44 CONTROL, and it fires: seeded with the value the routine
       writes, sixteen writes report as zero changed bytes."""
    h, m = new('boss')
    m[OPEN], m[SOLID] = 0x5A, 0xA5
    for i in range(768):
        m[ATTRS + i] = 0x5A               # exactly what $9D4C will write
    before = bytes(m[ATTRS:ATTRS + 768])
    log = call_logged(h, ERASE, 0x5800, 0x5B00)
    after = bytes(m[ATTRS:ATTRS + 768])
    return {'writes_logged': len(log),
            'bytes_changed': sum(1 for i in range(768) if before[i] != after[i]),
            'seed': 0x5A}


# ---------------------------------------------------------------- phase C
def phase_row01():
    """bossspawn has $A839 = 0, so rows 0 and 1 divert through the $FD00 guard's
       $01FF and land on the SAME four cells: SIXTEEN writes, TWELVE distinct."""
    h, m = new('bossspawn')
    m[OPEN], m[SOLID] = 0x5A, 0xA5
    for i in range(768):
        m[ATTRS + i] = 0xFF
    log = call_logged(h, ERASE, 0x5800, 0x5B00)
    addrs = ['$%04X' % a for (_, a, _) in log]
    dupes = sorted({a for a in addrs if addrs.count(a) > 1})
    return {'y': m[BOSS_Y], 'x': m[BOSS_X], 'writes': len(log),
            'distinct': len(set(addrs)), 'addrs': addrs, 'repeated': dupes,
            'rowtab_0': m[0xFD00] | (m[0xFD01] << 8),
            'rowtab_1': m[0xFD02] | (m[0xFD03] << 8)}


# ---------------------------------------------------------------- phase D
def phase_draw():
    """the draw: 128 display bytes plus a SIXTEEN-byte attribute LDD walk, so
       144 writes and not 128."""
    out = {}
    for name in ('boss', 'bosshit', 'bossspawn'):
        h, m = new(name)
        log = call_logged(h, DRAW, 0x4000, 0x5B00)
        bitmap = [a for (_, a, _) in log if a < 0x5800]
        attr = [(a, v) for (_, a, v) in log if a >= 0x5800]
        out[name] = {'x': m[BOSS_X], 'y': m[BOSS_Y],
                     'spr': m[SPR_PTR] | (m[SPR_PTR + 1] << 8),
                     'ptr': m[ATTR_PTR] | (m[ATTR_PTR + 1] << 8),
                     'writes': len(log), 'bitmap': len(bitmap),
                     'attr': len(attr),
                     'bitmap_first': '$%04X' % bitmap[0] if bitmap else None,
                     'bitmap_last': '$%04X' % bitmap[-1] if bitmap else None,
                     'attr_addrs': ['$%04X' % a for (a, _) in attr],
                     'attr_desc': attr[0][0] > attr[-1][0] if attr else None}
    return out


# ---------------------------------------------------------------- phase E
def phase_ptr_sweep():
    """$A8FD poked over C = 0..6, including the C the game cannot produce, and
       over the TAPE RESIDUE $A881 -- which is not of the form $A890 + 16C at
       all and makes the LDD walk read the spawn routine's own source table."""
    out = []
    for (label, ptr) in ([('C=%d' % c, 0xA890 + 16 * c) for c in range(7)] +
                         [('tape residue', 0xA881)]):
        h, m = new('boss')
        m[ATTR_PTR] = ptr & 0xFF
        m[ATTR_PTR + 1] = ptr >> 8
        log = call_logged(h, DRAW, 0x4000, 0x5B00)
        attr = [(a, v) for (_, a, v) in log if a >= 0x5800]
        out.append({'label': label, 'ptr': ptr, 'attr_writes': len(attr),
                    'values': [v for (_, v) in attr],
                    'source': ['$%02X' % m[(ptr - i) & 0xFFFF] for i in range(16)]})
    return out


# ---------------------------------------------------------------- phase F
def phase_a8dc():
    """the high byte nobody writes, and $A901's dead RET z guard."""
    out = {}
    for v in (0, 1):
        h, m = new('boss')
        m[BOSS_XH] = v
        log = call_logged(h, DRAW, 0x4000, 0x5B00)
        a = [x for (_, x, _) in log]
        out['xh_%d' % v] = {'writes': len(a), 'first': '$%04X' % min(a),
                            'last': '$%04X' % max(a)}
    # $A901 RET z: the attribute walk is skipped when the pointer's HIGH byte is 0
    h, m = new('boss')
    m[ATTR_PTR + 1] = 0
    log = call_logged(h, DRAW, 0x4000, 0x5B00)
    out['a8fe_zero'] = {'writes': len(log),
                        'attr': len([1 for (_, x, _) in log if x >= 0x5800])}
    return out


# ---------------------------------------------------------------- phase G
def phase_palette_pair():
    """$8309/$830A have TWO writers each, neither fires during the fight, and
       the effect-7 item sets BOTH to $2F -- which makes $9D4C's two arms the
       SAME FUNCTION and the bit-5 test unobservable."""
    h, m = new('boss')
    names = {0x32: 'LD (nn),A', 0x3A: 'LD A,(nn)', 0x21: 'LD HL,nn'}
    refs = {}
    for (label, addr) in (('$8309', OPEN), ('$830A', SOLID)):
        hits = h.find_bytes(bytes([addr & 0xFF, addr >> 8]), 0x4000, 0x10000)
        refs[label] = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1],
                        'form': names.get(m[a - 1])} for a in hits]
    # and nobody writes them during the fight
    g, mm = new('boss')
    g.memobj.watch(OPEN, SOLID + 1)
    sim, regs, op, mem = g.sim, g.sim.registers, g.sim.opcodes, g.sim.memory
    fd, ia = g.frame_duration, g.int_active
    tgt = regs[T] + 240 * fd
    while regs[T] < tgt:
        p = regs[PC]
        if mem[p] == 0x76 and regs[IFF]:
            g._fast_halt()
            continue
        op[mem[p]]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, p)
    fight = [['$%04X' % p, '$%04X' % a, v] for (p, a, v) in g.memobj.log]
    g.memobj.unwatch()
    # the EQUAL-ANSWER world: open == solid makes the branch unobservable
    k, km = new('boss')
    km[OPEN], km[SOLID] = 0x2F, 0x2F
    checkerboard(km)
    for i in range(768):
        km[ATTRS + i] = 0xFF
    log = call_logged(k, ERASE, 0x5800, 0x5B00)
    return {'refs': refs, 'writes_in_240_frames': fight,
            'live': {'$8309': m[OPEN], '$830A': m[SOLID]},
            'equal_pair': {'values': sorted(set(v for (_, _, v) in log)),
                           'writes': len(log)}}


# ---------------------------------------------------------------- phase H
def phase_recon_callers():
    """$9D4C has FIVE callers, and four of them are a 2x2 entity painter that
       writes MORE attribute bytes per frame than the boss erase does.  A gate
       watching $5800..$5AFF globally captures their writes and calls them the
       boss's."""
    h, m = new('boss')
    hits = h.find_bytes(bytes([0x4C, 0x9D]), 0x4000, 0x10000)
    callers = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1]} for a in hits]
    counts = {}
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    tgt = regs[T] + 120 * fd
    while regs[T] < tgt:
        p = regs[PC]
        if p in (0x9CFC, 0x9D01, 0x9D0B, 0x9D10, 0xA961, 0x9D4C, 0xA925,
                 0xA9B1, 0xA844, 0xA847, 0xA824):
            counts['$%04X' % p] = counts.get('$%04X' % p, 0) + 1
        if mem[p] == 0x76 and regs[IFF]:
            h._fast_halt()
            continue
        op[mem[p]]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, p)
    # $A951 is NOT an entry point
    entry = {'CD 51 A9': len(h.find_bytes(bytes([0xCD, 0x51, 0xA9]), 0x4000, 0x10000)),
             'C3 51 A9': len(h.find_bytes(bytes([0xC3, 0x51, 0xA9]), 0x4000, 0x10000))}
    return {'callers': callers, 'counts_120_frames': counts, 'a951_entry': entry}


# ---------------------------------------------------------------- phase I
def phase_bitmap():
    """THE BITMAP HALF, which the attribute gate cannot see at all.

       The shadow is seeded with a POSITION-DEPENDENT pattern -- (addr * 7) & $FF
       -- so that "copies from the shadow", "copies from the display" and "copies
       from the wrong page" all produce different bytes, and the full 128-write
       log is compared address for address AND value for value.

       Two BUILT rows sit beside it: an X that makes the four LDIs straddle
       E = $FF (they are SIXTEEN-bit and carry into D, which the following four
       eight-bit `DEC E`s cannot take back), and $A8DC := 1, which moves the
       whole erase by +$100."""
    out = {}
    for (name, x, y, xh) in (('plain', 20, 9, 0), ('straddle', 29, 12, 0),
                             ('high_byte', 20, 9, 1)):
        h, m = new('boss')
        m[OPEN], m[SOLID] = 0x5A, 0xA5
        checkerboard(m)
        # ONLY $E000..$F7FF: $F800 is the colour shadow this phase just
        # checkerboarded and $FD00 is the ROW TABLE.  Seeding to $10000 wiped
        # both and the erase wrote nowhere the watch could see -- 0 bytes.
        for a in range(0xE000, 0xF800):
            m[a] = (a * 7) & 0xFF          # the SHADOW, position-dependent
        for a in range(0x4000, 0x5800):
            m[a] = 0xFF                    # a value the copy never produces
        m[BOSS_X], m[BOSS_Y], m[BOSS_XH] = x, y, xh
        log = call_logged(h, ERASE, 0x4000, 0x5B00)
        bm = [['$%04X' % a, v] for (_, a, v) in log if a < 0x5800]
        out[name] = {'x': x, 'y': y, 'xh': xh,
                     'bitmap': bm, 'n_bitmap': len(bm),
                     'n_attr': len([1 for (_, a, _) in log if a >= 0x5800]),
                     'pages': sorted(set(b[0][:3] for b in bm))}
    return out


# ---------------------------------------------------------------- phase J
def phase_draw_bitmap():
    """the DRAW's 128 bitmap bytes, from a position-dependent sprite, so that
       "the sprite cursor runs on" and "the sprite cursor reloads each row" are
       different observations -- they are identical from a uniform source."""
    out = {}
    for (name, x, y) in (('plain', 20, 9), ('straddle', 29, 12)):
        h, m = new('boss')
        for a in range(0xFE02, 0x10000):
            m[a] = (a * 11) & 0xFF         # the SPRITE, position-dependent
        for a in range(0x4000, 0x5800):
            m[a] = 0xFF
        m[BOSS_X], m[BOSS_Y], m[BOSS_XH] = x, y, 0
        m[SPR_PTR], m[SPR_PTR + 1] = 0x02, 0xFE
        log = call_logged(h, DRAW, 0x4000, 0x5800)
        out[name] = {'x': x, 'y': y, 'spr': 0xFE02,
                     'bitmap': [['$%04X' % a, v] for (_, a, v) in log],
                     'n': len(log),
                     'pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log))}
    return out


# ---------------------------------------------------------------- phase K
def phase_built_edges():
    """the two eight-bit masks that no reachable world exercises, BUILT.

       (a) $A951's `AND 3` after three RRAs: it differs from `AND 7` only when
           bit 5 of (D-1) is set, which needs the erase's final D in $21..$40 --
           poked into the $FD00 row table, since no display row produces it.
       (b) $A90C's three `INC L`: eight-bit, so a block starting at L >= $FD
           wraps inside its page instead of climbing into the next."""
    out = {}
    h, m = new('boss')
    m[OPEN], m[SOLID] = 0x5A, 0xA5
    checkerboard(m)
    for i in range(768):
        m[ATTRS + i] = 0xFF
    m[0xFD00 + 2 * 9] = 0x00               # row 9 -> $3800, so D ends at $40
    m[0xFD00 + 2 * 9 + 1] = 0x38
    m[BOSS_X], m[BOSS_Y], m[BOSS_XH] = 20, 9, 0
    log = call_logged(h, ERASE, 0x4000, 0x10000)
    # EVERY write at or above $5800, not only the ones inside the attribute
    # file: the poked row's four go to $5B14, and `AND 7` would send them to
    # $5F14 -- a window that stopped at $5B00 filtered the discriminator out.
    # ...and NOT the stack: the sentinel block sits at $96DD, so a bare
    # `a >= $5800` filter collected four PUSH writes and called them attributes.
    out['mask3'] = {'attr_writes': ['$%04X' % a for (_, a, v) in log
                                    if 0x5800 <= a < 0x6000],
                    'in_file': ['$%04X' % a for (_, a, v) in log if 0x5800 <= a < 0x5B00],
                    'all_pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log))}
    g, mm = new('boss')
    for a in range(0x4000, 0x5B00):
        mm[a] = 0xFF
    mm[BOSS_X], mm[BOSS_Y], mm[BOSS_XH] = 29, 12, 0
    log2 = call_logged(g, DRAW, 0x5800, 0x5B00)
    out['attr_wrap'] = {'addrs': ['$%04X' % a for (_, a, _) in log2]}
    return out


# ---------------------------------------------------------------- phase L
def phase_erase_edges():
    """the erase's OWN eight-bit masks, none of which any reachable world
       exercises: the row walk (`$A9DE`'s four rows are added to ($A839) as
       BYTES), the pixel-row `INC H`, and the attribute `INC E`/`INC L`."""
    out = {}
    # (a) the row walk: Y = 254 makes the four rows 254, 255, 0, 1
    h, m = new('boss')
    m[OPEN], m[SOLID] = 0x5A, 0xA5
    checkerboard(m)
    for a in range(0xE000, 0xF800):
        m[a] = (a * 7) & 0xFF
    for a in range(0x4000, 0x5B00):
        m[a] = 0xFF
    m[BOSS_X], m[BOSS_Y], m[BOSS_XH] = 20, 254, 0
    # $FD00 + 2*256 is $FF00, and a SIXTEEN-bit row walk would read THERE.
    # Seeded with a real display address so that "the rows wrap in eight bits"
    # and "the rows run on" write to DIFFERENT places -- unseeded, $FF00 holds
    # a non-display value and both models drop the row, which is no test at all.
    m[0xFF00], m[0xFF01] = 0x00, 0x48
    m[0xFF02], m[0xFF03] = 0x20, 0x48
    log = call_logged(h, ERASE, 0x4000, 0x9000)
    out['row_wrap'] = {'y': 254, 'writes': len(log),
                       'seed_ff00': [0x4800, 0x4820],
                       'addrs': ['$%04X' % a for (_, a, _) in log][:8],
                       'pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log))}
    # (b) the pixel-row INC H: $A8DC poked so the shadow page climbs past $FF
    g, mm = new('boss')
    mm[OPEN], mm[SOLID] = 0x5A, 0xA5
    checkerboard(mm)
    for a in range(0x4000, 0x5B00):
        mm[a] = 0xFF
    mm[BOSS_X], mm[BOSS_Y], mm[BOSS_XH] = 20, 9, 0x1D
    log2 = call_logged(g, ERASE, 0x4000, 0x9000)
    out['h_wrap'] = {'xh': 0x1D, 'writes': len(log2),
                     'pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log2))}
    # (c) the attribute INC E: an X whose attribute low byte reaches $FD
    k, km = new('boss')
    km[OPEN], km[SOLID] = 0x5A, 0xA5
    checkerboard(km)
    for a in range(0x4000, 0x5B00):
        km[a] = 0xFF
    km[BOSS_X], km[BOSS_Y], km[BOSS_XH] = 29, 12, 0
    log3 = call_logged(k, ERASE, 0x5800, 0x5C00)
    out['e_wrap'] = {'x': 29, 'y': 12,
                     'addrs': ['$%04X' % a for (_, a, _) in log3]}
    return out


def main():
    fx = {'reconstruct': phase_reconstruct(),
          'diff_blind': phase_diff_blind(),
          'row01': phase_row01(),
          'draw': phase_draw(),
          'ptr_sweep': phase_ptr_sweep(),
          'a8dc': phase_a8dc(),
          'palette': phase_palette_pair(),
          'callers': phase_recon_callers(),
          'bitmap': phase_bitmap(),
          'draw_bitmap': phase_draw_bitmap(),
          'edges': phase_built_edges(),
          'erase_edges': phase_erase_edges()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    for k, v in fx['reconstruct'].items():
        print('  %-12s (X,Y)=(%2d,%2d) %2d writes, %2d distinct, values %s, '
              'solid %d / open %d' % (k, v['x'], v['y'], v['writes'],
                                      v['distinct'], v['values'], v['n_solid'],
                                      v['n_open']))
    d = fx['diff_blind']
    print('TRAPS #44: %d writes logged, %d bytes changed'
          % (d['writes_logged'], d['bytes_changed']))
    r = fx['row01']
    print('row 0/1: %d writes, %d distinct, repeated %s (rowtab[0]=$%04X)'
          % (r['writes'], r['distinct'], r['repeated'], r['rowtab_0']))
    for k, v in fx['draw'].items():
        print('  draw %-10s %d writes = %d bitmap + %d attr, %s..%s, spr $%04X ptr $%04X'
              % (k, v['writes'], v['bitmap'], v['attr'], v['bitmap_first'],
                 v['bitmap_last'], v['spr'], v['ptr']))
    for v in fx['ptr_sweep']:
        print('  ptr %-13s $%04X -> %d attr writes, values %s'
              % (v['label'], v['ptr'], v['attr_writes'], v['values'][:6]))
    print('$A8DC:', fx['a8dc'])
    print('$8309/$830A refs:',
          {k: [r['at'] + ' ' + str(r['form']) for r in v]
           for k, v in fx['palette']['refs'].items()})
    print('   writes in 240 frames:', fx['palette']['writes_in_240_frames'],
          ' equal-pair values:', fx['palette']['equal_pair']['values'])
    print('$9D4C callers:', [c['at'] for c in fx['callers']['callers']],
          fx['callers']['counts_120_frames'])
    print('$A951 as an entry point:', fx['callers']['a951_entry'])
    for k, v in fx['bitmap'].items():
        print('  erase bitmap %-10s (X,Y,XH)=(%d,%d,%d) %d bytes, pages %s'
              % (k, v['x'], v['y'], v['xh'], v['n_bitmap'], v['pages']))
    for k, v in fx['draw_bitmap'].items():
        print('  draw bitmap  %-10s %d bytes, pages %s' % (k, v['n'], v['pages']))
    for k, v in fx['erase_edges'].items():
        print('  erase edge %-9s %s' % (k, {kk: vv for kk, vv in v.items()
                                            if kk != 'addrs'}))
    print('  edges:', fx['edges']['mask3']['attr_writes'][:4],
          fx['edges']['mask3']['all_pages'],
          fx['edges']['attr_wrap']['addrs'][:4])


if __name__ == '__main__':
    main()
