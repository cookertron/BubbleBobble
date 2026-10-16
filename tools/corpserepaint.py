"""M7.51 -- $8C51, THE DYING ENEMY'S FINAL REPAINT: $A447's ERASE-ONLY ENTRY on every arm.

$8BC2 (the corpse birth) is `DI / LD HL,$AA5F / DEC (HL) / CALL $8C51 / ...`, and $8C51 is

    $8C51  LD A,$C9 / LD ($A5D9),A     the entity master's erase/draw junction := RET
    $8C56  CALL $A447                  the master, with the dying enemy's OWN flags
    $8C59  XOR A / LD ($A5D9),A / RET  the junction back to NOP -- a SET, not a restore

-- the same "erase half only" entry $BE92 (the capture) runs.  $A447's gates, in order:

    $A44D  LD A,(IY+7) / AND A / JP p,$A437     bit 7 CLEAR -> $A437
    $A454  BIT 3,A / JR nz,$A437                bit 3 SET   -> $A437
    $A458  BIT 6,A / SET 6,(IY+7) / JP z,$A5D9  a first visit: SET 6 and out (no erase)
    $A461  LD A,(IY+2) / CP $C0 / JP nc,$A5D9   a cached Y of $C0 or more: out (no erase)
    $A469..$A480  the ERASE at the CACHED (+3, +2), aligned ($A483, +7 at $A485) or shifted
                  ($A53C, +20 at $A56A) by the CACHED X & 6, each with its own $A430 add
    $A5D9  the patched RET -- so no $A5DC DEC, no $A5E0 SET 5, no draw
and $A437 is `LD SP,IX / BIT 5,(IY+7) / RET nz / SET 5,(IY+7) / LD HL,$AA5F / DEC (HL) / RET`.

Until M7.51 the port modelled only the $A437 bookkeeping, and only for bit 7 CLEAR: a LIVE
enemy (bit 7 set, bit 3 clear, bit 6 set, cached Y below $C0) left its last frame on the
display and $A431 short by the erase's add, and a FROZEN enemy with bit 5 clear cost $AA5F
one where the machine costs two.  This oracle measures every arm.

THREE FAMILIES.
  BUILT    direct calls at their own entry ($8BC2 AND $8C51 -- the latter so $A447's +7 is
           seen before $8BF3 overwrites it), interrupts OFF, uncontended, on a world BUILT
           in slot 4 ($FDA8) of r20_48 and of firekill: the display and the shadow of both
           boxes (cached and current) filled with synthetic patterns (display != shadow, so
           a copy is visible and the shifted composite's mask matters), $AA5F seeded $77,
           $A431 and the generator $FE86/$FE87 seeded per world.  Worlds: live at cached X
           & 6 = 0/2/4/6 and an odd X, the natural live flags ($E4, bit 5 set), the cached X
           held apart from the current X both ways and far apart, a first visit (bit 6
           clear, with and without bit 5, and at a cached Y of $C8 -- $A45A SETs bit 6 before
           $A464 looks), cached Y $BF / $C0 / $C8 / $FF, the sentinel rows
           at the top (cached Y $08 and $0B -- the $FD00 table's $01FF addresses ROM and
           those writes are dropped), the right-edge page wrap, $A431 seeded to carry, a
           FROZEN enemy (bit 3) with bit 5 clear and set and on a first visit, an EMPTY slot
           (bit 7 clear) with bit 5 clear ($00, $40) and set ($20, $60, $28), and a corpse's
           own $3F.
  NATURAL  the same two calls on every enemy slot (2..8) of r20_48, elfire and firekill AS
           THEY STAND -- the real flags, cached positions, sprites and background ($AA5F
           seeded $77, $A431 seeded $21).  r20_48's five live enemies are all aligned (the
           M7.49 review's $21 -> $28); elfire and firekill carry every shifted X & 6 and
           cached X held apart from the current X by the walk.
  KILL     the first ENVIRONMENT KILL of a live enemy in natural idle play from fbkill (a
           shifted erase, ISR 11) and elwater (aligned, ISR 576): the machine's pre-state
           at $931A's entry
           (found by breaking at $8C56 with $93D3 -- the $93D0 CALL's return -- on the stack,
           in a $931A call that no ISR has entered before the kill; the first such kill is
           taken), then re-run from that entry to $931A's RET at $8D58 with interrupts off --
           up to the kill that is exactly the natural path, and after it ($93D3 EI) the rest
           of the walk runs without the ISR the natural run might have taken there.
           The vector is the attribute file, $FD80..$FDFF and named scalars, plus the
           display and shadow at every byte the erase writes.  (firekill's only idle kill
           in 7,369 ISRs (the M7.51 review) comes in a $931A call an ISR entered first -- the ISR moves the
           enemy into the fire -- so it cannot be re-run from the call's entry.)
  CENSUS   every $8C56 entry in those two runs up to the kill, and in 600 idle ISRs of
           ellight: the $8BC2 caller (the return address on the stack), the slot, its +7,
           IFF, and whether an ISR had entered the $931A call first.  ellight's live kills
           come through $9EFE -- the elemental bolt's enemy kill, which the port does not
           wire yet (boltCorpse is a counted stub) -- not $93D0.

WHAT IS RECORDED per call: every write $4000..$FFFF with its PC, split into the display
($4000..$5AFF, in order, with the pre-call display and shadow byte at each address), the
MODELLED bytes (the slot, $AA5F, $A431, $FE86/$FE87 -- and for a kill the rest of the table,
$93C4 and whatever else $931A writes), $A447's own SELF-MODIFIED OPERANDS ($A50B, $A584, the
eight mask operands $A5A2..$A5D1, $A5D9 -- the port does not model them: every one is
written by the same call before that call's loop reads it, and $A5D9 is set back to $00),
and the stack -- and every READ of an operand (the instruction that carries it executing) is
checked against the log: it must follow a write to that byte in the same call; every $A430
entry (the call site from the return address, A, and $A431 before); the $A447 arm PCs visited; A at $8BDA and $8BE2 (the two $FE85 draws); and the
call's T (uncontended).  A write to ROM never reaches the log (SkoolKit's simulator drops
it before the memory object sees it), so the claims count an erase's RAM rows from the
$FD00 table instead: a whole erase is two or three columns of those rows.

NO ROM BYTE.  The write watch starts at $4000 and the harness drops every ROM write, so no
value read or written at a ROM address is ever stored.  The natural display may hold ROM
charset glyphs in the HUD cells (char rows 0..2, columns 0, 1, 30, 31 -- tools/popkill.py's
hud_masked): a natural call that touches one FAILS the capture, and every complete 8-byte
cell this fixture stores (display before, display after, shadow) is checked against every
non-blank glyph of the machine's charset, read from the harness and never written out.

GUARD.  Every call is single-stepped with a PC check and stops before anything in
$D000..$D2FF (a 128K music driver) executes; the 48K branch byte $8DC4 must be $C9.

Usage:  python tools/corpserepaint.py capture   -> build/corpserepaint_fixture.json
        python tools/corpserepaint.py verify    re-run and diff against the fixture
"""
import sys, os, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, PC, SP, IYh, IYl, T, IFF, A as RA
import portconfig as pc

FIXTURE = 'build/corpserepaint_fixture.json'
NOTE = ('M7.51: $8C51 -- `LD A,$C9 / LD ($A5D9),A / CALL $A447 / XOR A / LD ($A5D9),A` -- is '
        '$A447 with its erase/draw junction patched to RET, the erase-only entry the capture '
        '$BE92 runs.  Gates: bit 7 clear or bit 3 set -> $A437 (BIT 5 / RET nz / SET 5 / DEC '
        '($AA5F)); else SET 6, and a first visit or a cached Y >= $C0 -> out; else the erase at '
        'the CACHED (+3, +2), aligned (+7 at $A485) or shifted (+20 at $A56A) by the CACHED X & 6. '
        'calls: $8BC2 and $8C51 called at their own entries (interrupts off, uncontended) on '
        'built worlds in slot 4 of r20_48 and firekill and on every enemy slot of r20_48, '
        'elfire and firekill as they stand; kills: fbkill\'s and elwater\'s first natural '
        'environment kill, $931A re-run from its entry; census: every $8C56 entry on those runs '
        'and on 600 idle ISRs of ellight.  writes = the display writes in order; disp_before / '
        'shadow = the bytes before at those addresses; modelled / operand / other = the rest, '
        'classified (the stack is counted); adds = [site, A, $A431 before] per $A430 entry; '
        'draws = [site, A] per $FE85 call; t = the call\'s T.  No ROM byte is stored.')
BIRTH, REPAINT, MASTER, BEAM = 0x8BC2, 0x8C51, 0xA447, 0xA430
ENVKILL, ENVKILL_RET, KILL_RET = 0x931A, 0x8D58, 0x93D3
GUARD = range(0xD000, 0xD300)
BRANCH_BYTE = 0x8DC4
ROWTAB, ENT_MASK, SHADOW = 0xFD00, 0xAA4F, 0xA000
ACC, LEFT, PRNG, JUNCTION = 0xA431, 0xAA5F, 0xFE86, 0xA5D9
SLOT = 0xFDA8                                   # the BUILT worlds' slot: slot 4, an enemy slot
# the $A430 call sites, from the return address the CALL pushed
SITE = {0xA488: 'A485', 0xA56D: 'A56A', 0xA619: 'A616', 0xA70B: 'A708'}
ARM_PCS = {0xA437: 'A437', 0xA43E: 'A43E', 0xA442: 'A442', 0xA45A: 'A45A', 0xA461: 'A461',
           0xA469: 'A469', 0xA483: 'A483', 0xA53C: 'A53C', 0xA5D9: 'A5D9', 0xA5DC: 'A5DC',
           0xA5E0: 'A5E0'}
DRAW_AT = {0x8BDA: 0x8BD7, 0x8BE2: 0x8BDF}      # A just after each CALL $FE85 returns
# $A447's self-modified operands: the aligned erase's $A491 LD ($A50B),A, the shifted erase's
# $A573 LD ($A584),A and its eight mask stores $A544..$A55A, and the $8C51 junction patch
OPERANDS = [0xA50B, 0xA584, 0xA5A2, 0xA5A6, 0xA5B1, 0xA5B5, 0xA5BE, 0xA5C2, 0xA5CD, 0xA5D1, 0xA5D9]
# ...and the instruction that READS each one: $A50A LD A,n, $A583 LD B,n, the eight AND n of the
# shifted loop, and $A5D9 itself, executed as an opcode (the patched RET)
OPERAND_AT = {0xA50A: 0xA50B, 0xA583: 0xA584, 0xA5A1: 0xA5A2, 0xA5A5: 0xA5A6, 0xA5B0: 0xA5B1,
              0xA5B4: 0xA5B5, 0xA5BD: 0xA5BE, 0xA5C1: 0xA5C2, 0xA5CC: 0xA5CD, 0xA5D0: 0xA5D1,
              0xA5D9: 0xA5D9}


def hud_masked(a):
    """a display BITMAP address whose cell may hold a ROM glyph (tools/popkill.py)"""
    if not 0x4000 <= a < 0x5800:
        return False
    col = a & 0x1F
    row = ((a >> 8) & 0x18) | ((a >> 5) & 7)
    return row < 3 or col in (0, 1, 30, 31)


def new(state, contended=None):
    h = Harness() if contended is None else Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, h.memobj.m


def glyphs(h):
    rom = bytes(h.memobj.m[0x3D00:0x4000])           # read in memory, never written out
    return {rom[i * 8:i * 8 + 8] for i in range(96)} - {bytes(8)}


def glyph_scan(G, stored, where):
    """no complete 8-byte display cell this fixture stores may equal a non-blank ROM glyph"""
    cells = {}
    for a, v in stored.items():
        if 0x4000 <= a < 0x5800:
            cells.setdefault(a & ~0x0700, {})[(a >> 8) & 7] = v
    hits = ['$%04X' % b for b, rows in cells.items()
            if len(rows) == 8 and bytes(rows[i] for i in range(8)) in G]
    if hits:
        raise SystemExit('%s: stored display cells equal ROM glyphs at %s' % (where, hits[:8]))
    return sum(1 for rows in cells.values() if len(rows) == 8)


def screen_addr(m, y):
    e = ROWTAB + 2 * ((y >> 3) & 0x1F)
    return (m[e] | ((m[e + 1] + (y & 7)) << 8)) & 0xFFFF


def box(m, x, y):
    """the up-to-3x16 bytes an erase at (x, y) can reach, through the $FD00 row table"""
    out = set()
    for r in range(16):
        sa = screen_addr(m, (y + r) & 0xFF)
        base = (sa & 0xFF00) | ((sa + (x >> 3)) & 0xFF)
        for c in range(3):
            a = (base & 0xFF00) | ((base + c) & 0xFF)
            if 0x4000 <= a < 0x5800:
                out.add(a)
    return out


def classify(a, sp_lo, sp_hi, modelled):
    if 0x4000 <= a < 0x5B00:
        return 'display'
    if sp_lo <= a < sp_hi:
        return 'stack'
    if a in OPERANDS:
        return 'operand'
    if a in modelled:
        return 'modelled'
    return 'other'


def run_call(h, entry, slot, stop=None, modelled=()):
    """CALL `entry` with IY = slot (or, with `stop`, run from the current PC -- a bracket whose
       caller already pushed the return address -- until PC == stop at the entry SP + 2),
       interrupts OFF, single-stepped with the guard.  Returns the record of everything the
       call did."""
    m, r = h.memobj.m, h.sim.registers
    pre = bytes(m)
    sp0 = r[SP]
    if stop is None:
        sp = sp0
        for s in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp], m[sp + 1] = s & 0xFF, s >> 8
        r[SP] = sp
        r[IYh], r[IYl] = slot >> 8, slot & 0xFF
        r[PC] = entry
        stops, want_sp = set(h.SENTINELS), (sp + 2) & 0xFFFF
    else:
        sp = sp0
        stops, want_sp = {stop}, (sp0 + 2) & 0xFFFF
    t0 = r[T]
    h.memobj.watch(0x4000, 0x10000)
    adds, arms, draws, masters, reads = [], [], [], [], []
    n = 0
    while True:
        p = r[PC]
        if p in GUARD:
            h.memobj.unwatch()
            raise SystemExit('GUARD: PC $%04X in $D000..$D2FF' % p)
        if p in stops and (stop is None or r[SP] == want_sp):
            break
        if p == BEAM:
            ret = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
            adds.append([SITE.get(ret, '%04X' % ret), r[RA], m[ACC]])
        if p in ARM_PCS:
            arms.append(ARM_PCS[p])
        if p in DRAW_AT:
            draws.append([DRAW_AT[p], r[RA]])
        if p in OPERAND_AT:                              # the operand is fetched NOW
            reads.append((OPERAND_AT[p], len(h.memobj.log)))
        if p == 0x8C56:                                  # $8C51's CALL $A447: the slot as it stands
            iy = (r[IYh] << 8) | r[IYl]
            masters.append({'slot': iy, 'f7': m[iy + 7], 'cy': m[iy + 2], 'cx': m[iy + 3],
                            'y': m[iy + 6], 'x': m[iy + 5], 'nadds': len(adds),
                            'caller': '%04X' % ((m[(r[SP] + 2) & 0xFFFF] | (m[(r[SP] + 3) & 0xFFFF] << 8)) - 3)})
        h.step(1, interrupts=False)
        n += 1
        if n > 400_000:
            h.memobj.unwatch()
            raise SystemExit('runaway: $%04X did not return' % (entry if entry is not None else r[PC]))
    h.memobj.unwatch()
    if r[SP] != want_sp:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[SP], want_sp))
    if stop is None and h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('$%04X abandoned %d frames' % (entry, h.SENTINELS.index(r[PC])))
    sp_lo, sp_hi = (sp - 0x100) & 0xFFFF, sp0
    disp, cls = [], {'modelled': {}, 'operand': {}, 'stack': 0, 'other': {}}
    for _pc, a, v in h.memobj.log:
        k = classify(a, sp_lo, sp_hi, modelled)
        if k == 'display':
            disp.append([a, v])
        elif k == 'stack':
            cls['stack'] += 1
        else:
            cls[k][a] = v
    touched = sorted({a for a, _v in disp})
    first_w = {}
    for i, (_pc, a, _v) in enumerate(h.memobj.log):
        if a in OPERAND_AT.values() and a not in first_w:
            first_w[a] = i
    rbw = sorted({'%04X' % a for a, at in reads if first_w.get(a, 1 << 30) >= at})
    return {
        'writes': disp,
        'disp_before': [[a, pre[a]] for a in touched],
        'shadow': [[a, pre[(a + SHADOW) & 0xFFFF]] for a in touched],
        'modelled': sorted([a, v] for a, v in cls['modelled'].items()),
        'operand': sorted([a, v] for a, v in cls['operand'].items()),
        'other': sorted([a, v] for a, v in cls['other'].items()),
        'stack_writes': cls['stack'],
        'operand_reads': len(reads), 'operand_read_before_write': rbw,
        'adds': adds, 'arms': arms, 'draws': draws, 'masters': masters,
        't': r[T] - t0, 'steps': n, '_pre': pre,
    }


# ------------------------------------------------------------------ BUILT worlds
#  label                  +7    cy    cx    y     x    $A431
BUILT = [
    ('live_aligned',        0xC0, 0x60, 0x50, 0x64, 0x58, 0x21),
    ('live_shift2_oddY',    0xC0, 0x61, 0x52, 0x61, 0x52, 0x21),
    ('live_shift4',         0xC0, 0x63, 0x54, 0x66, 0x54, 0x21),
    ('live_shift6',         0xC0, 0x67, 0x56, 0x6A, 0x56, 0x21),
    ('live_oddX_shift',     0xC0, 0x65, 0x53, 0x65, 0x53, 0x21),   # X & 6 = 2, X & 7 = 3
    ('live_natural_E4',     0xE4, 0x70, 0x5A, 0x74, 0x5C, 0x21),   # bit 5 SET on the live arm
    ('apart_cached_aligned', 0xC0, 0x70, 0x60, 0x78, 0x62, 0x21),  # current shifted
    ('apart_cached_shifted', 0xC0, 0x70, 0x64, 0x78, 0x68, 0x21),  # current aligned
    ('apart_far',           0xC1, 0x30, 0xA2, 0x90, 0x20, 0x21),
    ('first_visit',         0x80, 0x60, 0x52, 0x60, 0x52, 0x21),   # bit 6 clear
    ('first_visit_bit5',    0xA0, 0x60, 0x50, 0x60, 0x50, 0x21),
    ('cachedY_BF',          0xC0, 0xBF, 0x52, 0xB0, 0x52, 0x21),   # one row, the rest ROM
    ('cachedY_C0',          0xC0, 0xC0, 0x52, 0x60, 0x52, 0x21),
    ('cachedY_C8',          0xC0, 0xC8, 0x50, 0x60, 0x50, 0x21),
    ('cachedY_FF',          0xC0, 0xFF, 0x54, 0x60, 0x54, 0x21),
    ('top_rows',            0xC0, 0x08, 0x50, 0x20, 0x50, 0x21),   # char row 1 is the $01FF sentinel
    ('top_rows_odd',        0xC0, 0x0B, 0x56, 0x20, 0x56, 0x21),
    ('right_edge_shifted',  0xC0, 0x38, 0xFA, 0x38, 0xFA, 0x21),   # the page wrap
    ('right_edge_aligned',  0xC0, 0x3C, 0xF8, 0x3C, 0xF8, 0x21),
    ('carry_shifted',       0xC0, 0x60, 0x52, 0x60, 0x52, 0xF0),   # $F0 + $14 = $104
    ('carry_aligned',       0xC0, 0x60, 0x50, 0x60, 0x50, 0xFC),   # $FC + 7 = $103
    ('frozen_bit5_clear',   0xC8, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('frozen_bit5_set',     0xE8, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('frozen_first_visit',  0x88, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('frozen_bit7_clear',   0x08, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('empty_00',            0x00, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('empty_40',            0x40, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('empty_20',            0x20, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('empty_60',            0x60, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('empty_28',            0x28, 0x60, 0x52, 0x60, 0x52, 0x21),
    ('corpse_3F',           0x3F, 0x60, 0x50, 0x60, 0x50, 0x21),
    ('first_visit_cachedY_C8', 0x80, 0xC8, 0x52, 0x60, 0x52, 0x21),  # bit 6 clear AND cached Y >= $C0
    # ($AA5F) seeded $00 (the M7.51 review): $A437's DEC -- and $8BC6's -- must WRAP, not saturate
    ('frozen_bit5_clear_AA5F00', 0xC8, 0x60, 0x50, 0x60, 0x50, 0x21, 0x00),
    ('empty_1F_AA5F00',          0x1F, 0x60, 0x50, 0x60, 0x50, 0x21, 0x00),
]
BUILT_STATES = {'r20_48': (0x5A, 0xA5), 'firekill': (0x3C, 0xC3)}   # per-state pattern salts


def slot_fields(m, s):
    return [m[s + i] for i in range(10)]


def build_world(m, i, salt, w):
    label, f7, cy, cx, y, x, a431 = w[:7]
    aa5f = w[7] if len(w) > 7 else 0x77                  # ($AA5F): $77, or a world's own seed
    s = SLOT
    m[s], m[s + 1] = 0x60, 0xC2                          # a real enemy sprite (the erase never reads it)
    m[s + 2], m[s + 3], m[s + 4] = cy, cx, 0x33
    m[s + 5], m[s + 6], m[s + 7], m[s + 8], m[s + 9] = x, y, f7, 0x00, 0x00
    for a in sorted(box(m, cx, cy) | box(m, x, y)):      # DIRTY, so display != shadow
        d = ((a * 7) ^ salt[0] ^ (i * 29)) & 0xFF
        sh = ((a * 13) ^ salt[1] ^ (i * 17)) & 0xFF
        if sh == d:
            sh ^= 0x5A
        m[a] = d
        m[(a + SHADOW) & 0xFFFF] = sh
    m[ACC], m[LEFT], m[JUNCTION] = a431, aa5f, 0x00
    m[PRNG], m[PRNG + 1] = (0x11 + 37 * i) & 0xFF, (0x2B + 91 * i) & 0xFF


def pack_call(rec, family, state, label, entry, slot, pre_m, extra=None):
    pre = rec.pop('_pre')
    rec.pop('masters')                                   # a direct call has no caller to name
    out = {'family': family, 'state': state, 'label': label, 'entry': entry, 'slot': slot,
           'pre': {'fields': [pre[slot + i] for i in range(10)], 'a431': pre[ACC], 'aa5f': pre[LEFT],
                   'prng': [pre[PRNG], pre[PRNG + 1]], 'a5d9': pre[JUNCTION]},
           'post': {'fields': slot_fields(pre_m, slot), 'a431': pre_m[ACC], 'aa5f': pre_m[LEFT],
                    'prng': [pre_m[PRNG], pre_m[PRNG + 1]], 'a5d9': pre_m[JUNCTION]}}
    out.update(rec)
    if extra:
        out.update(extra)
    return out


def modelled_for(slot):
    return set(range(slot, slot + 10)) | {ACC, LEFT, PRNG, PRNG + 1}


def built_calls():
    out = []
    for state, salt in BUILT_STATES.items():
        h, m = new(state, contended=False)
        base = h.save_state()
        for i, w in enumerate(BUILT):
            for entry in (BIRTH, REPAINT):
                h.load_state(base)
                build_world(m, i, salt, w)
                rec = run_call(h, entry, SLOT, modelled=modelled_for(SLOT))
                out.append(pack_call(rec, 'built', state, w[0], entry, SLOT, m))
    return out


# ------------------------------------------------------------------ NATURAL slots
NATURAL_STATES = ('r20_48', 'elfire', 'firekill')


def natural_calls():
    out = []
    for state in NATURAL_STATES:
        h, m = new(state, contended=False)
        base = h.save_state()
        for k in range(2, 9):
            s = 0xFD80 + 10 * k
            for entry in (BIRTH, REPAINT):
                h.load_state(base)
                m[LEFT], m[ACC], m[JUNCTION] = 0x77, 0x21, 0x00
                rec = run_call(h, entry, s, modelled=modelled_for(s))
                bad = [w[0] for w in rec['writes'] if hud_masked(w[0])]
                if bad:
                    raise SystemExit('%s slot %d: a natural erase touches the HUD cells %s' % (
                        state, k, ['$%04X' % a for a in bad[:4]]))
                out.append(pack_call(rec, 'natural', state, 'slot%d_%02X' % (k, rec['_pre'][s + 7]),
                                     entry, s, m))
    return out


# ------------------------------------------------------------------ KILL: natural $931A
KILL_STATES = ('fbkill', 'elwater')
CENSUS_ONLY = {'ellight': 600}
SCALARS = [0xAA57, 0xAA5F, 0xA431, 0xFE86, 0xFE87, 0x93C4, 0xFECE, 0xA5D9]
TABLE_LO, TABLE_HI = 0xFD80, 0xFE00


def first_kill(state, max_steps=60_000_000, max_isr=None):
    """natural idle play until a $931A call corpses a LIVE enemy (or, with max_isr, for that
       many ISRs); returns (h, m, pre, record, isr, census) -- record None for a census run"""
    h, m = new(state)
    r = h.sim.registers
    last = None
    isr = 0
    steps = 0
    census = []
    while steps < max_steps:
        p = r[PC]
        if p in GUARD:
            raise SystemExit('%s: GUARD at $%04X' % (state, p))
        if p == 0x8D72:
            isr += 1
            if max_isr is not None and isr > max_isr:
                return h, m, None, None, max_isr, census
        if p == ENVKILL:
            last = (h.save_state(), isr)
        if p == 0x8C56:
            ret2 = m[(r[SP] + 2) & 0xFFFF] | (m[(r[SP] + 3) & 0xFFFF] << 8)
            iy = (r[IYh] << 8) | r[IYl]
            census.append({'isr': isr, 'caller': '%04X' % ((ret2 - 3) & 0xFFFF), 'slot': iy,
                           'f7': m[iy + 7], 'cy': m[iy + 2], 'cx': m[iy + 3], 'iff': r[IFF],
                           'clean': last is not None and last[1] == isr})
        if p == 0x8C56 and last is not None and max_isr is None:
            ret2 = m[(r[SP] + 2) & 0xFFFF] | (m[(r[SP] + 3) & 0xFFFF] << 8)
            iy = (r[IYh] << 8) | r[IYl]
            f7 = m[iy + 7]
            # the kill must come in a $931A call NO ISR has entered yet: the bracket re-runs
            # it from its entry with interrupts off, and must see what the natural run saw
            if ret2 == KILL_RET and (f7 & 0x80) and not (f7 & 0x08) and last[1] == isr:
                st, at_isr = last
                h.load_state(st)
                pre = bytes(m)
                mod = set(range(TABLE_LO, TABLE_HI)) | set(SCALARS)
                rec = run_call(h, None, None, stop=ENVKILL_RET, modelled=mod)
                live = [x for x in rec['masters']
                        if x['caller'] == '93D0' and (x['f7'] & 0x80) and not (x['f7'] & 0x08)]
                if not live:
                    raise SystemExit('%s: the bracket did not reproduce the live kill' % state)
                return h, m, pre, rec, at_isr, census
        h.step(1)
        steps += 1
    raise SystemExit('%s: no live environment kill in %d steps' % (state, max_steps))


def kill_rows():
    out, census = [], {}
    for state, n in CENSUS_ONLY.items():
        census[state] = {'isrs': n, 'entries': first_kill(state, max_isr=n)[5]}
    for state in KILL_STATES:
        h, m, pre, rec, at_isr, cen = first_kill(state)
        census[state] = {'isrs': at_isr, 'entries': cen}
        bad = [w[0] for w in rec['writes'] if hud_masked(w[0])]
        if bad:
            raise SystemExit('%s: the kill erases HUD cells %s' % (state, ['$%04X' % a for a in bad[:4]]))
        rec.pop('_pre')
        out.append({
            'family': 'kill', 'state': state, 'isr': at_isr, 'entry': ENVKILL,
            'pre': {'attrs': base64.b64encode(pre[0x5800:0x5B00]).decode(),
                    'table': base64.b64encode(pre[TABLE_LO:TABLE_HI]).decode(),
                    'scalars': {'%04X' % a: pre[a] for a in SCALARS}},
            'post': {'attrs': base64.b64encode(bytes(m[0x5800:0x5B00])).decode(),
                     'table': base64.b64encode(bytes(m[TABLE_LO:TABLE_HI])).decode(),
                     'scalars': {'%04X' % a: m[a] for a in SCALARS}},
            **rec})
    return out, census


# ------------------------------------------------------------------ claims
def ram_rows(rowtab, cy):
    """how many of an erase's sixteen rows the $FD00 table sends to RAM"""
    return sum(1 for r in range(16) if rowtab[((cy + r) & 0xFF) >> 3] >= 0x4000)


def claims(calls, kills, census, rowtab):
    C = []

    def claim(text, held, **kw):
        C.append(dict(claim=text, held=bool(held), **kw))

    def arm_of(c):
        f = c['pre']['fields'][7]
        if not (f & 0x80) or (f & 0x08):
            return 'a437_set5' if not (f & 0x20) else 'a437_ret'
        if not (f & 0x40):
            return 'first_visit'
        if c['pre']['fields'][2] >= 0xC0:
            return 'cached_y_high'
        return 'erase_shifted' if (c['pre']['fields'][3] & 6) else 'erase_aligned'

    by = {}
    for c in calls:
        by.setdefault(arm_of(c), []).append(c)
    er = by.get('erase_aligned', []) + by.get('erase_shifted', [])
    claim('EVERY LIVE CALL ERASES AT THE CACHED (+3, +2) AND ADDS ITS OWN $A430: +7 at $A485 when '
          'the CACHED X & 6 is 0, +20 at $A56A otherwise -- one add per call, never a draw add',
          er and all(c['adds'] == [['A485' if not (c['pre']['fields'][3] & 6) else 'A56A',
                                    7 if not (c['pre']['fields'][3] & 6) else 20, c['pre']['a431']]]
                     for c in er), n=len(er))
    ncol = lambda c: 3 if c['pre']['fields'][3] & 6 else 2
    full = [c for c in er if ram_rows(rowtab, c['pre']['fields'][2]) == 16]
    part = [c for c in er if ram_rows(rowtab, c['pre']['fields'][2]) < 16]
    claim('...and a whole erase writes 32 display bytes aligned and 48 shifted (two and three '
          'columns of sixteen rows); a row the $FD00 table sends to ROM (char rows 0-1 and past '
          '23) writes nothing the log can see',
          full and part and all(len(c['writes']) == 16 * ncol(c) for c in full) and
          all(len(c['writes']) == ram_rows(rowtab, c['pre']['fields'][2]) * ncol(c) for c in er),
          n=len(er), whole=len(full), partial=len(part))
    apart = [c for c in er if (c['pre']['fields'][3] & 6) != (c['pre']['fields'][5] & 6)]
    claim('...and the CURRENT X (+5) chooses nothing: calls whose cached and current X & 6 differ '
          'take the cached one\'s path', len(apart) >= 4, n=len(apart))
    quiet = by.get('first_visit', []) + by.get('cached_y_high', [])
    claim('A FIRST VISIT (bit 6 clear) AND A CACHED Y OF $C0 OR MORE ERASE NOTHING AND ADD NOTHING',
          quiet and all(not c['writes'] and not c['adds'] and 'A469' not in c['arms'] for c in quiet),
          n=len(quiet))
    fv = [c for c in by.get('first_visit', []) if c['entry'] == REPAINT]
    fvh = [c for c in fv if c['pre']['fields'][2] >= 0xC0]
    claim('...and $A45A SETs bit 6 before $A45E tests the old value, so before $A464 tests the cached Y: '
          '$8C51 leaves +7 | $40 on every first visit, a cached Y of $C0 or more included ($A461 never runs)',
          fv and fvh and all(c['post']['fields'][7] == (c['pre']['fields'][7] | 0x40) and
                             'A461' not in c['arms'] for c in fv), n=len(fv), high=len(fvh))
    s5 = by.get('a437_set5', [])
    r5 = by.get('a437_ret', [])
    claim('BIT 7 CLEAR OR BIT 3 SET GOES TO $A437: bit 5 clear -> SET 5 and $AA5F one lower; bit 5 '
          'set -> RET nz, nothing.  No erase, no add either way',
          s5 and r5 and all(not c['writes'] and not c['adds'] for c in s5 + r5) and
          all(c['arms'][:1] == ['A437'] and 'A442' in c['arms'] for c in s5) and
          all(c['arms'] == ['A437'] for c in r5), set5=len(s5), ret=len(r5))
    b = [c for c in calls if c['entry'] == BIRTH]
    claim('$8BC2 COSTS $AA5F ONE, OR TWO WHEN $A437 FINDS BIT 5 CLEAR -- eight-bit, so a seed of $00 '
          'WRAPS to $FF / $FE (seeded $77, and $00 in two worlds)',
          all(c['post']['aa5f'] == (c['pre']['aa5f'] - (2 if arm_of(c) == 'a437_set5' else 1)) & 0xFF
              for c in b) and any(c['pre']['aa5f'] == 0 for c in b), n=len(b))
    rp = [c for c in calls if c['entry'] == REPAINT]
    claim('$8C51 ALONE: $AA5F one lower on the $A437 SET-5 arm and untouched otherwise; +7 bit 5 '
          'set on that arm, bit 6 set on the live arm, and nothing else of the slot moves',
          all(c['post']['aa5f'] == (c['pre']['aa5f'] - (1 if arm_of(c) == 'a437_set5' else 0)) & 0xFF
              for c in rp) and
          all(c['post']['fields'][:7] == c['pre']['fields'][:7] and
              c['post']['fields'][8:] == c['pre']['fields'][8:] for c in rp), n=len(rp))
    claim('THE TWO DRAWS: $8BC2 calls $FE85 exactly at $8BD7 and $8BDF, $8C51 never',
          all([d[0] for d in c['draws']] == [0x8BD7, 0x8BDF] for c in b) and
          all(not c['draws'] for c in rp))
    claim('NO DRAW HALF: $A5D9 is the patched RET on every call -- no $A5DC DEC, no $A5E0 SET 5, no '
          '$A616/$A708 add -- and $8C51 leaves $A5D9 = $00',
          all('A5DC' not in c['arms'] and 'A5E0' not in c['arms'] for c in calls) and
          all(a[0] in ('A485', 'A56A') for c in calls for a in c['adds']) and
          all(c['post']['a5d9'] == 0 for c in calls))
    claim('THE MACHINE WRITES NOTHING THE PORT DOES NOT MODEL, BESIDE $A447\'s OWN OPERANDS AND THE '
          'STACK: every other write is the slot, $AA5F, $A431 or $FE86/$FE87',
          all(not c['other'] for c in calls + kills))
    claim('$A447\'s OPERANDS are only $A50B (aligned), $A584 and the eight mask bytes (shifted) and '
          '$A5D9 (the junction, $00 after)',
          all(set(a for a, _v in c['operand']) <= set(OPERANDS) for c in calls + kills))
    nr = sum(c['operand_reads'] for c in calls + kills)
    claim('...and EVERY ONE IS WRITTEN BEFORE IT IS READ, in the same call: no operand fetch finds a '
          'value an earlier call left -- which is why the port need not model them',
          nr > 1000 and all(not c['operand_read_before_write'] for c in calls + kills), reads=nr)
    carry = [c for c in er if c['pre']['a431'] + c['adds'][0][1] > 0xFF]
    claim('$A431 WRAPS: an add past $FF leaves the low byte',
          carry and all(c['post']['a431'] == (c['pre']['a431'] + c['adds'][0][1]) & 0xFF for c in carry),
          n=len(carry))
    nat = [c for c in calls if c['family'] == 'natural' and c['state'] == 'r20_48' and
           c['entry'] == BIRTH and arm_of(c).startswith('erase')]
    claim('r20_48\'s FIVE LIVE ENEMIES (the M7.49 review\'s k = 0..4): $A431 $21 -> $28 each, 32 '
          'display writes each', len(nat) == 5 and all(c['post']['a431'] == 0x28 and len(c['writes']) == 32
                                                       for c in nat), n=len(nat))
    claim('THE NATURAL KILLS: fbkill\'s and elwater\'s first environment kill of a live enemy comes '
          'through $93D0 in $931A with bit 6 set and a cached Y below $C0, and erases -- one shifted '
          '(+20, 48 writes), one aligned (+7, 32 writes)',
          len(kills) == len(KILL_STATES) and
          all(len(k['masters']) == 1 and k['masters'][0]['caller'] == '93D0' and
              (k['masters'][0]['f7'] & 0xC8) == 0xC0 and k['masters'][0]['cy'] < 0xC0 for k in kills) and
          sorted(len(k['writes']) for k in kills) == [32, 48] and
          sorted(a[1] for k in kills for a in k['adds']) == [7, 20], kills=len(kills))
    ent = [e for c in census.values() for e in c['entries']]
    frozen = [e for e in ent if (e['f7'] & 0x88) != 0x80]
    live = [e for e in ent if (e['f7'] & 0x88) == 0x80]
    claim('THE CENSUS: every natural $8C51 entry of a LIVE enemy runs with interrupts off ($8BC2 '
          'opens with DI) through $93D0 (the environment kill) or $9EFE (the elemental bolt, '
          'ellight); the pop\'s come through $B82B and are frozen; and every frozen or empty slot the '
          'census meets has bit 5 SET -- none reaches $A437\'s SET 5 / DEC arm',
          live and frozen and all(e['iff'] == 0 for e in ent) and
          all(e['caller'] in ('93D0', '9EFE') for e in live) and
          any(e['caller'] == '9EFE' for e in live) and any(e['caller'] == '93D0' for e in live) and
          all(e['f7'] & 0x20 for e in frozen),
          live=len(live), frozen=len(frozen), callers=sorted({e['caller'] for e in ent}))
    return C


def capture():
    calls = built_calls() + natural_calls()
    kills, census = kill_rows()
    h, m = new('r20_48', contended=False)
    G = glyphs(h)
    ncells = 0
    for c in calls + kills:
        where = '%s/%s/%s' % (c['family'], c['state'], c.get('label', c.get('isr')))
        ncells += glyph_scan(G, dict(map(tuple, c['disp_before'])), where + ' before')
        ncells += glyph_scan(G, dict(map(tuple, c['writes'])), where + ' writes')
        ncells += glyph_scan(G, dict(map(tuple, c['shadow'])), where + ' shadow')
    rowtab = [m[ROWTAB + 2 * i] | (m[ROWTAB + 2 * i + 1] << 8) for i in range(32)]
    C = claims(calls, kills, census, rowtab)
    fx = {
        'note': NOTE,
        'rowtable': rowtab,
        'mask_table': [m[ENT_MASK + i] for i in range(8)], 'mask_addr': ENT_MASK,
        'slot': SLOT, 'operands': OPERANDS,
        'glyph_cells_checked': ncells,
        'calls': calls, 'kills': kills, 'census': census, 'claims': C,
    }
    return fx


def summary(fx):
    for c in fx['calls']:
        if c['family'] == 'built' and c['state'] != 'r20_48':
            continue
        print('  %-7s %-8s %-22s %s  +7 $%02X cy %3d cx %3d  writes %2d  adds %-16s arms %s  '
              '$A431 $%02X->$%02X  $AA5F $%02X->$%02X  T %d'
              % (c['family'], c['state'], c['label'], '8BC2' if c['entry'] == BIRTH else '8C51',
                 c['pre']['fields'][7], c['pre']['fields'][2], c['pre']['fields'][3], len(c['writes']),
                 c['adds'], ','.join(c['arms']), c['pre']['a431'], c['post']['a431'],
                 c['pre']['aa5f'], c['post']['aa5f'], c['t']))
    for k in fx['kills']:
        print('  kill    %-8s ISR %4d  writes %2d  kills %s  adds %s  other %s  operands %d'
              % (k['state'], k['isr'], len(k['writes']),
                 [(('%04X' % x['slot']), '$%02X' % x['f7'], x['cy'], x['cx']) for x in k['masters']],
                 k['adds'], k['other'], len(k['operand'])))
    for st, c in fx['census'].items():
        print('  census %-8s %4d ISRs: %s' % (st, c['isrs'], [(e['isr'], e['caller'], '$%02X' % e['f7'],
              'clean' if e['clean'] else 'isr-in') for e in c['entries']]))
    held = sum(1 for c in fx['claims'] if c['held'])
    for c in fx['claims']:
        print('  %s %s' % ('HELD  ' if c['held'] else 'FAILED', c['claim'][:110]))
    print('claims %d/%d held; %d calls, %d kills; %d complete cells glyph-scanned'
          % (held, len(fx['claims']), len(fx['calls']), len(fx['kills']), fx['glyph_cells_checked']))
    return held == len(fx['claims'])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    fx = capture()
    ok = summary(fx)
    if cmd == 'capture':
        with open(FIXTURE, 'w') as f:
            json.dump(fx, f, separators=(',', ':'))
        print('wrote %s (%d bytes)' % (FIXTURE, os.path.getsize(FIXTURE)))
    else:
        old = json.load(open(FIXTURE))
        same = json.loads(json.dumps(fx)) == old
        print('verify: %s' % ('the fixture is reproduced exactly' if same else 'DIFFERS from the fixture'))
        ok = ok and same
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
