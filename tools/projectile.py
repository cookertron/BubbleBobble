# -*- coding: utf-8 -*-
"""M7.55 -- THE PROJECTILES: $9BB4, the per-frame update of the two slots $5B00/$5B0A.

$9AEB (M7.23, tools/enemyfire.py) drafts an eligible enemy into one of two pseudo-entity slots
and sets the slot's (IY+8) to the enemy's TYPE; an ACTIVE slot (bit 7 of +7) is sent by
$9B0B JP nz,$9BB4 to the update instead.  $9BB4 is entered from $9B0B ONLY (census below).

  $9BB4  LD A,(IY+6) / PUSH AF / AND $F8 / LD (IY+6),A / CALL $A314 / POP AF / LD (IY+6),A
         -- the ERASE at the character-aligned Y, then the full Y back (kind 1 keeps a phase in
         its low three bits)
  $9BC4  (IY+8): 8 -> $9CF4, 7 -> $9CDC, 6 -> $9C4B, 5 -> $9C8C, 1 -> $9BE3 (DEC A / JR z),
         ANYTHING ELSE -> LD (IY+8),0 / RET (the slot stays ACTIVE: it is erased every tick and
         never drawn)
  $9BE3  kind 1, the BOULDER: a delay phase in (IY+6) & 7 -- 0 moves every tick; otherwise it
         is stepped (INC / AND 7), a step to 0 unmarks the shooter ($9C43 RES 1) and RETs, a step
         to 1 or 2 RETs, 3..7 moves.  The move is $9D77 with $9D83 -- the THIRD `ADD A,A` --
         zeroed (a NOP: +-4) and restored from $9D82 after.  Sprite $6000/$6020 by X & 4.
         $AEDC at the destination: EITHER cell solid (it or the one below) -> $9D58; X < $10 or
         >= $E0 -> $9D58; else $9D8B (the player hit) and JP $A2D5 (the OR draw).
  $9C4B  kind 6, the BREATH (and kind 8's mover): $9D77 +-8, sprite $6040/$6080 by facing,
         +$20 when ($A37C) bit 1; X < $10 / >= $E0 -> $9D58; kind 8 skips the wall test; else
         $AEDC -- and $9C7A `JR z,$9C86` means ONLY BOTH cells solid releases it.
  $9C8C  kind 5, the BOTTLE: $9D77 +-8, sprite $60C0 + (($A37C) x 16) & $60; NO X bound; the
         destination cell solid -> reversed once (SET 2 + facing flipped) and drawn where it
         stands, solid again -> $9D58; reversed and back at its launch X ((X & $F8) == (IY+9))
         -> $9D58.
  $9CDC  kind 7, the DROP: (IY+6) += 8 (eight bit), >= $C0 -> $9D58, sprite $6140 (+$20).
  $9CF4  kind 8, the PLAYER'S FIREBALL: the 2x2 attribute cells it stands on are rebuilt from
         the colour shadow's bit 5 ($9D4C: ($8309) or ($830A)), $9D5C and $9D8B are PATCHED to
         RET ($C9), $9C4B runs, they go back to NOP ($00), and a fireball still active paints its
         new 2x2 cells $42 -- bright red, which is what $931A's environment kill reads.
  $9D58  RES 7,(IY+7) / [$9D5C: NOP or RET] / LD L,(IY+4) / LD H,$FD / RES 1,(HL) / RET
  $9D8B  [NOP or RET] / C = X & $F8, B = Y & $F8 / P1 ($FD85) by CALL $9DA1, P2 ($FD8F) by
         FALL-THROUGH: X & $F8 against C-1, C, C+1 and Y & $F8 against B, B+1, B-1 (only the
         middle compare can ever match an 8-aligned C or B), then +$5A bits 3, 4, 2 refuse,
         else SET 2,(IX+$5A) and (IX+4) := $64.  NO in-play test.

$9DE1 (the player fireball's SPAWN, the next increment) and $9DD4 (the blow's request) are
MEASURED here too (phase `fireball`); the port's elemPreTick stays a counted stub.

WHAT IS STORED (house rule 7 -- no ROM byte, no image).  VEC_D, a fixed address vector: the
display $4000..$5AFF and the pixel shadow $E000..$F7FF with the HUD cells MASKED (tools/popkill.py's
rule: character rows 0..2 and columns 0, 1, 30, 31 -- the ROM-charset glyph cells), the colour
shadow $F800..$FBFF, the slots $5B00..$5B13, the projectile sprites $6000..$615F, $FD00..$FFFF, and
the named scalars.  Every stored display/shadow cell is scanned against every non-blank glyph of
the harness's charset (read, never written out): a match fails the capture.  A write to a masked
address is logged with its value REDACTED.  $A355/$A349/$A33D ($A314's operands) and $A304
($A2D5's) are NOT in the vector: each is written by the same call before it is read ($A34D is
entered only from $A33E/$A344 and by fall-through; $A2FB only from $A2F4 and by fall-through --
the census), so no value survives from one call to the next.

PHASES
  census    every reference to the routines and operands, from a live image (r20_48)
  direct    $9BB4 at its own entry, interrupts OFF, UNCONTENDED, on BUILT worlds (r6_48 plus the
            row's pokes): every kind, every branch, both slots.  PRE/POST over VEC_D, the ordered
            write log (address, value) outside the stack, the branch PCs visited, and T
  cost      the contended T of a subset of the direct rows at eight frame phases
  hit       $9D8B at its own entry: P1 and P2 swept over 33 x 33 positions around a projectile,
            the refusals, both players, not in play, the RET patch
  fireball  $9DE1 at its own entry (the request, both slots, the recycle, the Y window, P2, and
            ($FEC5) before and after), and $9DD4 -- for the next increment
  natural   interrupts ON, contended, from states where enemies fire: every ISR's PRE/POST over
            VEC_N, the R draws of every ISR and every main-loop span, the passes, the events, the
            main-loop PC each interrupt cut and the chain entry it was in; and every $9AEB call
            that reaches its body ($9AFC), PRE at $9AEB and POST at its return

GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/projectile.py capture [--jobs N]   -> build/projectile_fixture.json
        python tools/projectile.py verify [--jobs N]    re-run and diff against the fixture
        python tools/projectile.py <phase>              one phase, printed
"""
import sys, os, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import harness
from harness import Harness, T, PC, SP, A as RA, IYh, IYl, IXh, IXl
import portconfig as pc
import popkill as PK

FIXTURE = 'build/projectile_fixture.json'
GUARD = set(range(0xD000, 0xD300))
BRANCH_BYTE = 0x8DC4
FRAME_T = 69888
PHASES8 = [k * (FRAME_T // 8) for k in range(8)]
UPDATE = 0x9BB4
SLOTS = (0x5B00, 0x5B0A)
SP_MAIN = 0x96D7                  # the main loop's stack at a chain call (fbkill, extcomp, r40_48)
BASE = 'r6_48'
ISR_IN, ISR_OUT, PASS = 0x8D72, 0x8DA1, 0x8D0C
FIRE, FIRE_RET = 0x9AEB, 0x8D5B   # $8D58 CALL $9AEB returns to $8D5B
CHAIN_RETS = set(0x8D28 + 3 * i for i in range(20)) | {0x8D61}   # $8D25 + 3i CALLs, $8D5E CALL $8E3A
R_SITES = PK.R_SITES

hud_masked = PK.hud_masked


class Fail(Exception):
    pass


# ---------------------------------------------------------------------------- the vectors
D_SCALARS = [0x8309, 0x830A, 0x8DBD, 0x8DBE, 0x9AF5, 0x9D82, 0x9D83, 0x9D5C, 0x9D8B, 0xA37C]
N_SCALARS = sorted(set(PK.SCALARS + D_SCALARS + [
    0x7E0E, 0x7EB2, 0x7EFB, 0x8609, 0x8828, 0x872C, 0x9049, 0x904D, 0x90AA, 0x9160, 0x93C4,
    0x9E57, 0x9E5D, 0x9F64, 0xA09E, 0xA82D, 0x9EDF, 0x9EE0, 0x9F62, 0x9F09, 0x745C, 0x745D,
    0x9DDE, 0x9DDF, 0x9DE0] + list(range(0x9250, 0x925A))))


def _disp():
    return [a for a in range(0x4000, 0x5B00) if not hud_masked(a)]


def _shadow():
    return [a for a in range(0xE000, 0xF800) if not hud_masked(a - 0xA000)]


def vec_d():
    v = _disp() + _shadow() + list(range(0xF800, 0xFC00)) + list(range(0x5B00, 0x5B14)) + \
        list(range(0x6000, 0x6160)) + list(range(0xFD00, 0x10000)) + D_SCALARS
    assert len(v) == len(set(v)) and all(a >= 0x4000 for a in v)
    return v


def vec_n():
    v = _disp() + _shadow() + list(range(0xF800, 0xFC00)) + list(range(0x5B00, 0x5B14)) + \
        list(range(0x5CE0, 0x5CFC)) + list(range(0x9603, 0x9645)) + list(range(0xA891, 0xA89B)) + \
        list(range(0xB552, 0xB574)) + list(range(0xB5FD, 0xB60D)) + list(range(0xFD00, 0x10000))
    v += [a for a in N_SCALARS if a not in set(v)]
    assert len(v) == len(set(v)) and all(a >= 0x4000 for a in v)
    return v


VEC_D = vec_d()
VEC_N = vec_n()
IN_VEC_D = set(VEC_D)
ranges_of, pack, unpack = PK.ranges_of, PK.pack, PK.unpack


def glyphs(m):
    out = set()
    for c in range(0x20, 0x80):
        g = bytes(m[0x3C00 + 8 * c:0x3C00 + 8 * c + 8])
        if any(g):
            out.add(g)
    return out


def glyph_scan(m, gl, where):
    """no STORED display or shadow cell may equal a non-blank ROM glyph"""
    hits = []
    for base in (0x4000, 0xE000):
        for row in range(24):
            for col in range(32):
                a0 = 0x4000 | ((row & 0x18) << 8) | ((row & 7) << 5) | col
                if hud_masked(a0):
                    continue
                a0 += base - 0x4000
                cell = bytes(m[a0 + (r << 8)] for r in range(8))
                if cell in gl:
                    hits.append(['%04X' % a0, row, col])
    if hits:
        raise Fail('%s: stored cells equal ROM glyphs at %s' % (where, hits[:8]))


# ---------------------------------------------------------------------------- the machine
def new(state=BASE, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise Fail('%s: $8DC4 is not $C9 -- not the 48K branch (TRAPS #28)' % state)
    return h, m


def call(h, addr, regs=None, limit=10 ** 7, marks=()):
    """a routine at its own entry, interrupts OFF, the $D000..$D2FF guard in the target set;
    returns (exit index, T, the marks visited in order)"""
    r = h.sim.registers
    sp = SP_MAIN
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    for k, v in (regs or {}).items():
        hi, lo = {'HL': (harness.H, harness.L), 'DE': (harness.D, harness.E),
                  'BC': (harness.B, harness.C), 'IX': (IXh, IXl), 'IY': (IYh, IYl)}[k]
        r[hi], r[lo] = v >> 8, v & 0xFF
    r[PC] = addr
    t0 = r[T]
    seen = []
    tg = set(h.SENTINELS) | GUARD | set(marks)
    n = 0
    while True:
        why, k = h.run_until(tg, limit=limit, interrupts=False, stride=1 << 30)
        n += k
        p = r[PC]
        if p in GUARD:
            raise Fail('PC entered the guard at $%04X' % p)
        if p in h.SENTINELS:
            return h.SENTINELS.index(p), r[T] - t0, seen
        if why != 'target' or n > limit:
            raise Fail('no return from $%04X' % addr)
        seen.append('%04X' % p)
        h.step(1, interrupts=False)
        n += 1


# the branch marks: one PC per arm, so a row names the path it took
MARKS = {0x9BDE: 'default', 0x9BE3: 'k1', 0x9BF3: 'k1-step', 0x9C43: 'k1-unmark', 0x9BFC: 'k1-wait?',
         0x9BFE: 'k1-move', 0x9C4B: 'k6', 0x9C71: 'k6-wall', 0x9C7C: 'k6-below', 0x9C8C: 'k5',
         0x9CAD: 'k5-solid', 0x9CB4: 'k5-reverse', 0x9CC9: 'k5-home?', 0x9CDC: 'k7', 0x9CF4: 'k8',
         0x9D25: 'k8-back', 0x9D2A: 'k8-paint', 0x9D58: 'release', 0x9D5D: 'unmark', 0x9D8C: 'hit-test',
         0x9DBE: 'hit', 0x9DCE: 'kill', 0xA2D5: 'draw', 0xA314: 'erase'}


def stack_range():
    return range(SP_MAIN - 64, SP_MAIN + 2)


# ---------------------------------------------------------------------------- direct rows
def cs_cell(x, y):
    return 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)


def world(m, row):
    """the row's built world over r6_48: both slots cleared, the operands at rest, the shooter
    (enemy 0, +7 at $FD9B) MARKED, then the slot and the row's pokes"""
    for s in SLOTS:
        for i in range(10):
            m[s + i] = 0
    m[0x9D83], m[0x9D5C], m[0x9D8B] = 0x87, 0x00, 0x00
    m[0xA37C] = row.get('a37c', 0)
    m[0xFD9B] = 0xC2                           # enemy 0 in play, facing right, MARKED (bit 1)
    iy = row.get('iy', SLOTS[0])
    x, y = row['x'], row['y']
    m[iy + 0], m[iy + 1] = 0x00, 0x60
    m[iy + 4] = row.get('iy4', 0x9B)
    m[iy + 5], m[iy + 6] = x, y
    m[iy + 7] = 0xC0 | row.get('face', 1) | (0x04 if row.get('rev') else 0)
    m[iy + 8] = row['kind']
    m[iy + 9] = row.get('home', x & 0xF8)
    # the destination cells: solid bits as the row asks, OPEN otherwise
    k = row['kind']
    if k == 7:
        dx, dy = x, (y + 8) & 0xFF
    else:
        step = 4 if k == 1 else 8
        if row.get('d83') is not None and k != 1:
            step = 4 if row['d83'] == 0 else 8
        dx, dy = (x + (step if row.get('face', 1) else -step)) & 0xFF, y
    top, below = cs_cell(dx, dy), (cs_cell(dx, dy) + 0x20) & 0xFFFF
    m[top] = (m[top] & 0xDF) | (0x20 if row.get('top') else 0)
    m[below] = (m[below] & 0xDF) | (0x20 if row.get('below') else 0)
    if row.get('p1_at_dest'):
        m[0xFD85], m[0xFD86] = dx, dy & 0xF8
    for a, v in row.get('pokes', {}).items():
        m[a] = v
    if row.get('d83') is not None:
        m[0x9D83] = row['d83']
    return iy, (dx, dy)


R = []


def row(label, **kw):
    kw['label'] = label
    R.append(kw)


# kind 1 -- the BOULDER
row('K1 phase 1 -> 2: the first tick WAITS (erase only, no move, no draw)', kind=1, x=0x70, y=0x61)
row('K1 phase 2 -> 3: moves +4 (the third ADD A,A NOPped), sprite $6020 (X & 4), draws', kind=1, x=0x70, y=0x62)
row('K1 phase 3 -> 4 facing LEFT: X $70 -> $6C', kind=1, x=0x70, y=0x63, face=0)
row('K1 phase 4 -> 5: X $74 -> $78, sprite $6000', kind=1, x=0x74, y=0x64)
row('K1 phase 5 -> 6', kind=1, x=0x78, y=0x65)
row('K1 phase 6 -> 7', kind=1, x=0x7C, y=0x66)
row('K1 phase 7 -> 0: $9C43 UNMARKS the shooter and RETs -- no move, no draw', kind=1, x=0x70, y=0x67)
row('K1 phase 0: moves on EVERY tick (the $9BE9 JR z)', kind=1, x=0x70, y=0x60)
row('K1 phase 0 facing left from X $74: $70, sprite $6000', kind=1, x=0x74, y=0x60, face=0)
row('K1: $9D83 is ZEROED for the move and restored from $9D82 -- entered $00, left $87', kind=1, x=0x70,
    y=0x60, pokes={0x9D83: 0x00})
row('K1: the destination cell SOLID -> $9D58: RES 7 and the shooter unmarked, no draw', kind=1, x=0x70,
    y=0x60, top=1)
row('K1: only the cell BELOW solid -> $9D58 too (EITHER cell)', kind=1, x=0x70, y=0x60, below=1)
row('K1: both cells solid -> $9D58', kind=1, x=0x70, y=0x60, top=1, below=1)
row('K1: X lands at $0E (< $10) -> $9D58', kind=1, x=0x12, y=0x60, face=0)
row('K1: X lands at $10 -> drawn (the bound is < $10)', kind=1, x=0x14, y=0x60, face=0)
row('K1: X lands at $E0 -> $9D58 (>= $E0)', kind=1, x=0xDC, y=0x60)
row('K1: X lands at $DC -> drawn', kind=1, x=0xD8, y=0x60)
row('K1: the release with $9D5C = RET ($C9): RES 7 and NO unmark', kind=1, x=0xDC, y=0x60,
    pokes={0x9D5C: 0xC9})
row('K1: P1 in the destination cell -> KILLED (+$5A SET 2, +4 := $64)', kind=1, x=0x70, y=0x60,
    p1_at_dest=1)
row('K1: P1 in the cell with $9D8B = RET ($C9) -> not hit', kind=1, x=0x70, y=0x60, p1_at_dest=1,
    pokes={0x9D8B: 0xC9})
row('K1 in slot $5B0A', kind=1, x=0x70, y=0x60, iy=SLOTS[1])
row('K1: (IY+4) = $AF -- the unmark lands on enemy 2\'s +7 ($FDAF)', kind=1, x=0xDC, y=0x60, iy4=0xAF,
    pokes={0xFDAF: 0xC2})
row('K1: (IY+4) = $87 -- the unmark lands on P1\'s +7 ($FD87): RES 1 of a PLAYER byte', kind=1,
    x=0xDC, y=0x60, iy4=0x87, pokes={0xFD87: 0xE3})
# kind 6 -- the BREATH
row('K6 facing right, ($A37C) bit 1 clear: +8, sprite $6080', kind=6, x=0x70, y=0x60, a37c=0x00)
row('K6 facing right, ($A37C) bit 1 SET: sprite $60A0', kind=6, x=0x70, y=0x60, a37c=0x02)
row('K6 facing left, ($A37C) bit 1 clear: -8, sprite $6040', kind=6, x=0x70, y=0x60, face=0, a37c=0x01)
row('K6 facing left, ($A37C) = $FF: sprite $6060', kind=6, x=0x70, y=0x60, face=0, a37c=0xFF)
row('K6: BOTH cells solid -> $9D58', kind=6, x=0x70, y=0x60, top=1, below=1)
row('K6: only the destination cell solid -> DRAWN (the second test must fail too)', kind=6, x=0x70,
    y=0x60, top=1)
row('K6: only the cell below solid -> DRAWN ($9C7A JR z skips the second test)', kind=6, x=0x70,
    y=0x60, below=1)
row('K6: X lands at $0E -> $9D58', kind=6, x=0x16, y=0x60, face=0)
row('K6: X lands at $E0 -> $9D58', kind=6, x=0xD8, y=0x60)
row('K6: X lands at $10 -> drawn', kind=6, x=0x18, y=0x60, face=0)
row('K6: $9D83 = $00 (state no chain leaves behind) -> the step is 4: the operand is READ', kind=6,
    x=0x70, y=0x60, d83=0x00)
row('K6: P1 in the destination cell -> KILLED', kind=6, x=0x70, y=0x60, p1_at_dest=1)
row('K6 in slot $5B0A, the release unmarks via ITS (IY+4)', kind=6, x=0xD8, y=0x60, iy=SLOTS[1])
# kind 5 -- the BOTTLE
row('K5 ($A37C) = 0: sprite $60C0', kind=5, x=0x70, y=0x60, a37c=0)
row('K5 ($A37C) = 2: sprite $60E0', kind=5, x=0x70, y=0x60, a37c=2)
row('K5 ($A37C) = 4: sprite $6100', kind=5, x=0x70, y=0x60, a37c=4)
row('K5 ($A37C) = 6: sprite $6120', kind=5, x=0x70, y=0x60, a37c=6)
row('K5 ($A37C) = $F9: EIGHT-BIT ADD A,A x4 -> $90, AND $60 -> $00: sprite $60C0', kind=5, x=0x70,
    y=0x60, a37c=0xF9)
row('K5 facing left', kind=5, x=0x70, y=0x60, face=0, a37c=3)
row('K5: the destination cell solid, not yet reversed -> SET 2, facing FLIPPED, drawn IN the wall',
    kind=5, x=0x70, y=0x60, top=1)
row('K5: the destination cell solid, ALREADY reversed -> $9D58', kind=5, x=0x70, y=0x60, top=1, rev=1)
row('K5: reversed and back at its launch X ((X & $F8) == +9) -> $9D58', kind=5, x=0x70, y=0x60, rev=1,
    home=0x78)
row('K5: reversed, X & $F8 != +9 -> drawn', kind=5, x=0x70, y=0x60, rev=1, home=0x40)
row('K5: reversed, +9 = $7A (never aligned in play) -> no match, drawn', kind=5, x=0x72, y=0x60, rev=1,
    home=0x7A)
row('K5: only the cell BELOW solid -> drawn (one cell)', kind=5, x=0x70, y=0x60, below=1)
row('K5: NO X bound -- X $04 facing left wraps to $FC (eight bit)', kind=5, x=0x04, y=0x60, face=0)
row('K5: P1 in the destination cell -> KILLED', kind=5, x=0x70, y=0x60, p1_at_dest=1)
# kind 7 -- the DROP
row('K7: Y $60 -> $68, sprite $6140', kind=7, x=0x70, y=0x60, a37c=0)
row('K7: ($A37C) bit 1 -> sprite $6160', kind=7, x=0x70, y=0x61, a37c=2)
row('K7: Y $B8 -> $C0 -> $9D58', kind=7, x=0x70, y=0xB8)
row('K7: Y $B7 -> $BF -> drawn (rows 23 and 24 of the $FD00 table)', kind=7, x=0x70, y=0xB7)
row('K7: Y $F8 -> $00 -- EIGHT-BIT add, below $C0, drawn', kind=7, x=0x70, y=0xF8)
row('K7: P1 in the destination cell -> KILLED', kind=7, x=0x70, y=0x60, p1_at_dest=1)
row('K7: a solid destination is IGNORED (no wall test)', kind=7, x=0x70, y=0x60, top=1, below=1)
# kind 8 -- the PLAYER'S FIREBALL
row('K8 facing right: attrs rebuilt, +8, drawn $6080, $42 painted', kind=8, x=0x70, y=0x60)
row('K8 facing left, ($A37C) bit 1: -8, $6060', kind=8, x=0x70, y=0x60, face=0, a37c=2)
row('K8: $8309/$830A poisoned $5A/$A5, the old cells\' bit 5 mixed -> each cell its own', kind=8,
    x=0x70, y=0x60, pokes={0x8309: 0x5A, 0x830A: 0xA5}, mixed=1)
row('K8: BOTH cells solid -> NOT released (the $9C6D CP 8 skips the wall test)', kind=8, x=0x70,
    y=0x60, top=1, below=1)
row('K8: X lands at $E0 -> RES 7 ONLY ($9D5C is RET: no unmark) and no $42 ($9D29 RET z)', kind=8,
    x=0xD8, y=0x60)
row('K8: P1 in the destination cell -> NOT hit ($9D8B is RET)', kind=8, x=0x70, y=0x60, p1_at_dest=1)
row('K8 at X $F8 (column 31) on row 12: $599F + INC E is $59A0 -- eight and sixteen bit agree here',
    kind=8, x=0xF8, y=0x60)
row('K8 at X $F8 on ROW 7 (built: a live fireball is never past column 27): $58FF + INC E is $5800 -- EIGHT bit',
    kind=8, x=0xF8, y=0x38)
row('K8: $9D5C and $9D8B entered as RET -> left NOP', kind=8, x=0x70, y=0x60, pokes={0x9D5C: 0xC9,
                                                                                      0x9D8B: 0xC9})
row('K8 at an UNALIGNED Y $61 (built: $9E21 aligns every real one): $9D3A is Y*4 + $5800, not (Y & $F8)*4',
    kind=8, x=0x70, y=0x61)
row('K6 at an unaligned Y $63: the erase and the $AEDC test both align it, the draw row is Y >> 3', kind=6,
    x=0x70, y=0x63, below=1)
# the default
for k in (0, 2, 3, 4, 9, 0x80, 0xFF):
    row('default: kind $%02X -> (IY+8) := 0, erase only, STILL ACTIVE' % k, kind=k, x=0x70, y=0x60)


def one_direct(r):
    h, m = new(BASE)
    iy, dest = world(m, r)
    if r.get('mixed'):
        # the four OLD cells the fireball stands on: bit 5 set in two of them
        c = cs_cell(r['x'], r['y'])
        for k, s in zip((c, c + 1, c + 0x20, c + 0x21), (1, 0, 0, 1)):
            m[k] = (m[k] & 0xDF) | (0x20 if s else 0)
    pre = [m[a] for a in VEC_D]
    h.memobj.watch(0x4000, 0x10000)
    ex, cost, seen = call(h, UPDATE, {'IY': iy}, marks=MARKS)
    log = h.memobj.log
    h.memobj.unwatch()
    post = [m[a] for a in VEC_D]
    st = stack_range()
    writes = []
    for p, a, v in log:
        if a in st:
            continue
        if a in (0xA355, 0xA349, 0xA33D, 0xA304):
            continue
        writes.append([a, v if a in IN_VEC_D else None])
    bad = [a for a, v in writes if a not in IN_VEC_D and not hud_masked(a) and not hud_masked(a - 0xA000)]
    if bad:
        raise Fail('%s: writes outside the vector at %s' % (r['label'], ['%04X' % a for a in bad[:8]]))
    return dict(label=r['label'], iy=iy, kind=r['kind'], dest=list(dest), exit=ex, cost=cost,
                marks=[MARKS[int(s, 16)] for s in seen], pre=pre, post=post, writes=writes)


def phase_direct(jobs=8):
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        out = list(ex.map(one_direct, R))
    h, m = new(BASE)
    gl = glyphs(m)
    base = [m[a] for a in VEC_D]       # every row's PRE is stored as a diff from plain r6_48
    rows = []
    for o in out:
        rows.append(dict(label=o['label'], iy=o['iy'], kind=o['kind'], dest=o['dest'], exit=o['exit'],
                         cost=o['cost'], marks=o['marks'], pre=pack(base, o['pre']),
                         post=pack(o['pre'], o['post']), writes=o['writes']))
        print('direct %-92s %5d T  %s' % (o['label'][:92], o['cost'], ' '.join(o['marks'])))
    # the glyph scan over the base and every row's POST
    glyph_scan(m, gl, 'the base')
    for o in out:
        mm = bytearray(m)
        for a, v in zip(VEC_D, o['post']):
            mm[a] = v
        glyph_scan(mm, gl, o['label'])
    return dict(state=BASE, sp=SP_MAIN, vector=ranges_of(VEC_D), vector_len=len(VEC_D),
                base=base64.b64encode(bytes(base)).decode(), rows=rows)


# ---------------------------------------------------------------------------- contended cost
COST_ROWS = ['K1 phase 1 -> 2', 'K1 phase 0: moves', 'K1: the destination cell SOLID', 'K6 facing right, ($A37C) bit 1 clear',
             'K5 ($A37C) = 0', 'K7: Y $60', 'K8 facing right', 'default: kind $00', 'K1: P1 in the destination cell']


def one_cost(args):
    label, ph = args
    r = [x for x in R if x['label'].startswith(label)][0]
    h, m = new(BASE, contended=True)
    iy, _ = world(m, r)
    h.regs[T] = (h.regs[T] // FRAME_T) * FRAME_T + ph
    ex, cost, seen = call(h, UPDATE, {'IY': iy})
    return label, ph, cost


def phase_cost(jobs=8):
    args = [(l, ph) for l in COST_ROWS for ph in PHASES8]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        res = list(ex.map(one_cost, args))
    out = {}
    for l, ph, c in res:
        out.setdefault(l, []).append(c)
    for l in COST_ROWS:
        print('cost %-40s contended at 8 phases: %s' % (l, out[l]))
    return out


# ---------------------------------------------------------------------------- the hit test
def hit_world(m, px, py, who, p5a=0x80, p7=0xE1, iy=SLOTS[0], x=0x70, y=0x60):
    for s in SLOTS:
        for i in range(10):
            m[s + i] = 0
    m[iy + 5], m[iy + 6], m[iy + 7], m[iy + 8] = x, y, 0xC1, 1
    m[0x9D8B] = 0
    # both players far away and alive, then the one under test placed
    for b in (0xFD80, 0xFD8A):
        m[b + 5], m[b + 6], m[b + 4] = 0x20, 0xA8, 0x00
        m[b + 0x5A] = (m[b + 0x5A] & 0x01) | 0x80
        m[b + 7] = 0xE1 if b == 0xFD80 else 0xE0
    b = 0xFD80 if who == 1 else 0xFD8A
    m[b + 5], m[b + 6] = px, py
    m[b + 0x5A] = (m[b + 0x5A] & 0x01) | p5a
    m[b + 7] = p7


def _hit_slice(args):
    who, xs = args
    out = []
    for px in xs:
        for py in range(0x50, 0x71):
            h, m = new(BASE)
            hit_world(m, px, py, who)
            b = 0xFD80 if who == 1 else 0xFD8A
            call(h, 0x9D8B, {'IY': SLOTS[0]})
            out.append([px, py, 1 if m[b + 0x5A] & 4 else 0, m[b + 4]])
    return out


def phase_hit(jobs=8):
    xs = list(range(0x60, 0x81))
    args = [(w, xs[i::6]) for w in (1, 2) for i in range(6)]
    sweep = {1: [], 2: []}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for (w, _), part in zip(args, ex.map(_hit_slice, args)):
            sweep[w] += part
    for w in (1, 2):
        sweep[w].sort()
        hits = [(px, py) for px, py, k, t in sweep[w] if k]
        print('hit P%d: %d of %d positions kill: X %s, Y %s; +4 on a kill %s'
              % (w, len(hits), len(sweep[w]), sorted(set('%02X' % p for p, _ in hits)),
                 sorted(set('%02X' % q for _, q in hits)), sorted(set(t for px, py, k, t in sweep[w] if k))))
    cases = []

    def case(name, who, px=0x70, py=0x60, p5a=0x80, p7=None, poke=None, both=False, x=0x70, y=0x60):
        h, m = new(BASE)
        hit_world(m, px, py, who, p5a=p5a, p7=(p7 if p7 is not None else (0xE1 if who == 1 else 0xE0)), x=x, y=y)
        if both:
            m[0xFD85], m[0xFD86] = px, py
            m[0xFD8F], m[0xFD90] = px, py
        if poke:
            for a, v in poke.items():
                m[a] = v
        pre = {a: m[a] for a in (0xFD84, 0xFDDA, 0xFD8E, 0xFDE4)}
        ex, cost, seen = call(h, 0x9D8B, {'IY': SLOTS[0]}, marks=(0x9DBE, 0x9DCE, 0x9D9E))
        post = {a: m[a] for a in (0xFD84, 0xFDDA, 0xFD8E, 0xFDE4)}
        cases.append(dict(case=name, who=who, px=px, py=py, x=x, y=y, p5a=p5a, both=both, poke=poke or {},
                          pre=['%04X=%02X' % (a, pre[a]) for a in sorted(pre)],
                          post=['%04X=%02X' % (a, post[a]) for a in sorted(post)],
                          p1=[post[0xFD84], post[0xFDDA]], p2=[post[0xFD8E], post[0xFDE4]],
                          marks=seen, cost=cost))
        print('hit case %-58s -> P1 +4/+5A %02X/%02X  P2 %02X/%02X  %s' % (name, post[0xFD84], post[0xFDDA],
                                                                           post[0xFD8E], post[0xFDE4], ' '.join(seen)))

    for who in (1, 2):
        case('P%d in the cell' % who, who)
        case('P%d invulnerable (+$5A bit 3)' % who, who, p5a=0x88)
        case('P%d water-carried (+$5A bit 4)' % who, who, p5a=0x90)
        case('P%d already dying (+$5A bit 2)' % who, who, p5a=0x84)
        case('P%d NOT IN PLAY (+7 bit 7 clear) -- still hit' % who, who, p7=0x61 if who == 1 else 0x60)
        case('P%d fire mode (+$5A bit 5) -- hit' % who, who, p5a=0xA0)
        case('P%d with $9D8B = RET' % who, who, poke={0x9D8B: 0xC9})
        case('P%d at X $77 (same cell, unaligned)' % who, who, px=0x77, py=0x67)
        case('P%d at X $78 (the next cell)' % who, who, px=0x78)
        case('P%d at X $00 against a projectile at X $00: DEC A is $FF' % who, who, px=0x00, x=0x00)
    case('BOTH players in the cell: P1 is killed, $9DD3 RETs into $9D9E and P2 is killed too', 1, both=True)
    case('BOTH in the cell, P1 invulnerable: P2 alone', 1, both=True, p5a=0x88)
    return dict(sweep={'1': sweep[1], '2': sweep[2]}, cases=cases)


# ---------------------------------------------------------------------------- census
CENSUS_TARGETS = [0x9BB4, 0x9C4B, 0x9C8C, 0x9CDC, 0x9CF4, 0x9D3A, 0x9D4C, 0x9D58, 0x9D5C, 0x9D65, 0x9D70,
                  0x9D77, 0x9D82, 0x9D83, 0x9D8B, 0x9DA1, 0x9DD4, 0x9DDE, 0x9DDF, 0x9DE1, 0xA314, 0xA34D,
                  0xA355, 0xA349, 0xA33D, 0xA2D5, 0xA2FB, 0xA304, 0xA37C]


def phase_census():
    import z80dis.z80 as z
    h, m = new('r20_48')
    b = bytes(m)
    out = {}
    for t in CENSUS_TARGETS:
        pat = bytes([t & 0xFF, t >> 8])
        refs = []
        p = 0x4000
        while True:
            p = b.find(pat, p)
            if p < 0:
                break
            for s in (p - 1, p - 2):
                if s < 0x4000 or s in GUARD or p in GUARD:
                    continue
                d = z.decode(b[s:s + 4], s)
                if d.len and s + d.len == p + 2 and ('0x%04x' % t) in z.decoded2str(d).lower():
                    starts = 0
                    for s0 in range(s - 12, s + 1):
                        a = s0
                        while a < s:
                            dd = z.decode(b[a:a + 4], a)
                            a += dd.len if dd.len else 1
                        starts += (a == s)
                    if starts >= 10:
                        refs.append(['%04X' % s, z.decoded2str(d)])
            p += 1
        out['%04X' % t] = refs
        print('census $%04X: %s' % (t, '; '.join('%s %s' % tuple(r) for r in refs)))
    return out


# ---------------------------------------------------------------------------- the fireball ($9DE1)
def fb_world(m, req=1, who=1, s0=None, s1=None, py=0x60, px=0x70, p7=None, fec5=0x01):
    for s in SLOTS:
        for i in range(10):
            m[s + i] = 0
    if s0:
        for i, v in enumerate(s0):
            m[SLOTS[0] + i] = v
    if s1:
        for i, v in enumerate(s1):
            m[SLOTS[1] + i] = v
    m[0x9DDE] = req
    ix = 0xFD80 if who == 1 else 0xFD8A
    m[0x9DDF], m[0x9DE0] = ix & 0xFF, ix >> 8
    m[ix + 5], m[ix + 6] = px, py
    if p7 is not None:
        m[ix + 7] = p7
    else:
        m[ix + 7] = 0xE1 if who == 1 else 0xE0
    m[ix + 0x5A] = (0x80 | 0x20 | (0 if who == 1 else 1))
    m[0xFEC5] = fec5
    m[0xFD9B] = 0xC2                            # a marked shooter for the recycle's unmark


def phase_fireball():
    rows = []
    SHOT = [0x00, 0x60, 0, 0, 0x9B, 0x40, 0x40, 0xC1, 0x01, 0x40]     # an active enemy boulder
    FB = [0xA0, 0x60, 0, 0, 0x00, 0x40, 0x40, 0x81, 0x08, 0x00]       # an active player fireball

    def case(name, **kw):
        h, m = new(BASE)
        fb_world(m, **kw)
        pre = [m[a] for a in range(0x5B00, 0x5B14)] + [m[0x9DDE], m[0xFEC5], m[0xFD9B]]
        h.memobj.watch(0x4000, 0x10000)
        ex, cost, seen = call(h, 0x9DE1, marks=(0x9E1E, 0x9E4A, 0x9E05, 0x9E0C, 0x9D58, 0xA314))
        log = [[p, a, v] for p, a, v in h.memobj.log if a not in stack_range()]
        h.memobj.unwatch()
        fec5 = [v for p, a, v in log if a == 0xFEC5]
        post = [m[a] for a in range(0x5B00, 0x5B14)] + [m[0x9DDE], m[0xFEC5], m[0xFD9B]]
        rows.append(dict(case=name, kw={k: v for k, v in kw.items()}, pre=pre, post=post, fec5_writes=fec5,
                         marks=seen, cost=cost, disp_writes=sum(1 for p, a, v in log if a < 0x5800)))
        print('fireball %-66s -> s0 %s | s1 %s | req %02X fec5 %02X (writes %s) shooter %02X  %s'
              % (name, ' '.join('%02X' % v for v in post[0:10]), ' '.join('%02X' % v for v in post[10:20]),
                 post[20], post[21], fec5, post[22], ' '.join(seen)))

    case('no request: RET z, nothing written', req=0)
    case('request, P1, both slots free -> slot 0', req=1)
    case('request, P1 facing left (+7 bit 0 clear)', req=1, p7=0xE0)
    case('request, P2 -> +7 bit 4 set', req=1, who=2)
    case('request, ($FEC5) was 0 -> left 1', req=1, fec5=0)
    case('request, slot 0 busy -> slot 1', req=1, s0=SHOT)
    case('request, both busy, slot 1 an ENEMY shot -> RECYCLED: erased, released, unmarked, refilled',
         req=1, s0=SHOT, s1=SHOT)
    case('request, both busy, slot 1 a FIREBALL -> nothing', req=1, s0=SHOT, s1=FB)
    case('request, P1 Y $0F -> Y & $F8 = $08 < $10: nothing', req=1, py=0x0F)
    case('request, P1 Y $10 -> spawned', req=1, py=0x10)
    case('request, P1 Y $B1 -> $B0 < $B2: spawned', req=1, py=0xB1)
    case('request, P1 Y $B8 -> >= $B2: nothing', req=1, py=0xB8)
    case('request, recycle then Y out of window: the shot is GONE and no fireball', req=1, s0=SHOT,
         s1=SHOT, py=0x08)
    case('request, P1 not in play (+7 bit 7 clear) -> a slot with bit 7 CLEAR', req=1, p7=0x61)
    case('request, X unaligned $73 -> $70', req=1, px=0x73)
    SHOT3 = SHOT[:6] + [0x43] + SHOT[7:]                              # a boulder mid-delay: +6 low bits
    case('request, recycle an UNALIGNED shot (+6 $43), Y out of window: slot 1 left ALIGNED', req=1, s0=SHOT,
         s1=SHOT3, py=0x08)
    case('request, recycle an UNALIGNED shot (+6 $43), refilled', req=1, s0=SHOT, s1=SHOT3)
    # $9DD4 itself
    h, m = new(BASE)
    m[0x9DDE] = 0
    ex, cost, seen = call(h, 0x9DD4, {'IX': 0xFD8A})
    req = dict(req=m[0x9DDE], ptr='%02X%02X' % (m[0x9DE0], m[0x9DDF]), cost=cost)
    print('$9DD4 with IX = $FD8A: ($9DDE) %02X, ($9DDF) $%s, %d T' % (req['req'], req['ptr'], cost))
    return dict(rows=rows, request=req)


# ---------------------------------------------------------------------------- natural scenes
def keys_none(i):
    return []


def stage_slot(slot, dx, face, kind=6, shooter=4):
    """a live kind-`kind` slot, as $9B4D..$9B6A would have filled it, `dx` px from P1 on his row"""
    def poke(m):
        iy = SLOTS[slot]
        p7 = (0xFD9B + 10 * shooter) & 0xFFFF
        m[p7] |= 0x02                           # the shooter MARKED, as $9B52 marks it
        x = (m[0xFD85] + dx) & 0xFF
        m[iy + 0], m[iy + 1] = 0x40, 0x60
        m[iy + 4] = p7 & 0xFF
        m[iy + 5] = x
        m[iy + 6] = (m[0xFD86] & 0xF8) | 1
        m[iy + 7] = 0xC0 | face
        m[iy + 8] = kind
        m[iy + 9] = x & 0xF8
    poke.__doc__ = ('slot $%04X := kind %d, %+d px from P1 on his row, facing %s, shooter enemy %d marked'
                    % (SLOTS[slot], kind, dx, 'RIGHT' if face else 'LEFT', shooter))
    return poke


SCENES = {
    'N1': dict(state='r6_48', keys=keys_none, lo=560, hi=1200,
               what='round 6, two type-1 boulder throwers, P1 standing: spawns, the delay phase, the unmark, two kills'),
    'N5': dict(state='r50_48', keys=keys_none, lo=430, hi=1000,
               what='round 50, seven type-5 bottle throwers: the reversal, the return home, kills'),
    'N7': dict(state='r60_48', keys=keys_none, lo=60, hi=620,
               what='round 60, four type-7 droppers: no row match, the fall, the floor, kills'),
    'N8': dict(state='fbkill', keys=keys_none, lo=0, hi=500,
               what='round 8 with P1\'s fireball (kind 8) in flight: the repaint, the $42 paint, the kill by colour'),
    'N6': dict(state='r40_48', keys=keys_none, lo=0, hi=600,
               stage=[(0, stage_slot(0, 40, 0)), (180, stage_slot(1, 16, 1)), (330, stage_slot(0, 24, 0)),
                      (480, stage_slot(1, 8, 1))],
               what='round 40, STAGED SLOTS: four kind-6 breaths written into the slots at ISRs 0, 180, 330 and '
                    '480 (no type-6 enemy of round 40 reaches P1\'s row: none fired in 5,000 natural frames); '
                    'every update after each is natural'),
}
EVENTS = {0x9BB4: 'upd', 0x9B4D: 'spawn', 0x9D58: 'release', 0x9C43: 'unmark7', 0x9DCE: 'kill',
          0x9CB4: 'reverse', 0x9D2A: 'fbpaint', 0x97F8: 'advance', 0x8BC2: 'corpse', 0x9DE6: 'fbreq'}


class Nat:
    def __init__(self, name):
        sc = SCENES[name]
        self.name, self.sc = name, sc
        self.h, self.m = new(sc['state'], contended=True)
        self.gl = glyphs(self.m)

    def iy(self):
        r = self.h.regs
        return (r[IYh] << 8) | r[IYl]


def scene(name):
    """run one natural scene; $9AEB's return is caught with a second target, $8D5B"""
    nat = Nat(name)
    h, m, sc = nat.h, nat.m, nat.sc
    r = h.regs
    tg = set(R_SITES) | set(EVENTS) | {ISR_IN, ISR_OUT, PASS, FIRE, 0x9AFC, FIRE_RET} | GUARD
    frames, calls = [], []
    cur_r, cur_ev = [], []
    isr = -1
    in_isr = False
    passes = gate_calls = 0
    call_open = None
    pre_isr = None
    main_r, main_ev = [], []
    while True:
        why, n = h.run_until(tg, limit=10 ** 8, interrupts=True, stride=1 << 30)
        p = r[PC]
        if p in GUARD:
            raise Fail('%s: PC entered the guard at $%04X' % (name, p))
        if why != 'target':
            raise Fail('%s: ran away' % name)
        if p in R_SITES:
            h.step(1)
            a = r[RA]
            iy = nat.iy()
            tag = None
            if p == 0xB88D:
                tag = (iy - 0xFED8) // 10
            elif p in (0xB008, 0xB0D5):
                tag = (iy - 0xFD80) // 10
            elif p in (0x873E, 0x8A2E, 0x8A38, 0x7E04, 0x9811):
                tag = 0
            (cur_r if in_isr else main_r).append([p, a, tag])
            continue
        if p == ISR_IN:
            isr += 1
            in_fire = call_open is not None
            if in_fire:
                call_open['cut'] = 1                   # this ISR landed inside the $9AEB bracket
            sp = r[SP]
            where = m[sp] | (m[(sp + 1) & 0xFFFF] << 8)   # the main-loop PC the interrupt cut
            # the CHAIN ENTRY it cut: the nearest $8D25-chain return address on the stack
            # ($8D28 + 3i returns from entry i; $8D61 from $8D5E CALL $8E3A)
            chain = None
            for k in range(1, 40):
                w = m[(sp + 2 * k) & 0xFFFF] | (m[(sp + 2 * k + 1) & 0xFFFF] << 8)
                if w in CHAIN_RETS:
                    chain = w
                    break
            if isr >= sc['lo']:
                vec = [m[a] for a in VEC_N]
                glyph_scan(m, nat.gl, '%s ISR %d entry' % (name, isr))
                if frames:
                    frames[-1].update(r_main=main_r, ev_main=main_ev, passes=passes, gate_calls=gate_calls,
                                      next_pre=vec, next_where='%04X' % where, next_in_fire=int(in_fire),
                                      next_chain=('%04X' % chain) if chain is not None else None)
                pre_isr = vec
            # a STAGE is written AFTER the PRE sample, so the PRE is the machine's own and the
            # POST of this ISR -- the next row's seed -- carries it
            for at, fn in sc.get('stage', []):
                if isr == at:
                    fn(m)
            if isr >= sc['hi']:
                break
            cur_r, cur_ev = [], []
            in_isr = True
            h.step(1)
            continue
        if p == ISR_OUT and in_isr:
            h.step(1)
            in_isr = False
            if isr >= sc['lo']:
                frames.append(dict(i=isr, pre=pre_isr, post=[m[a] for a in VEC_N], r_isr=cur_r, ev_isr=cur_ev))
            main_r, main_ev = [], []
            passes = gate_calls = 0
            continue
        if in_isr:
            if p in EVENTS and isr >= sc['lo']:
                cur_ev.append([EVENTS[p], '%04X' % nat.iy()])
            h.step(1)
            continue
        # ---- the main loop
        if p == PASS:
            passes += 1
        elif p == FIRE and isr >= sc['lo']:
            call_open = dict(isr=isr, sp=r[SP], pre=[m[a] for a in VEC_N], cut=0, body=0, ev=[])
        elif p == 0x9AFC and call_open is not None:
            call_open['body'] = 1
        elif p == FIRE_RET and call_open is not None and r[SP] == call_open['sp'] + 2:
            if call_open['body']:
                call_open['post'] = [m[a] for a in VEC_N]
                calls.append(call_open)
            else:
                gate_calls += 1
            call_open = None
        elif p in EVENTS and isr >= sc['lo']:
            iy = nat.iy()
            e = [EVENTS[p], '%04X' % iy]
            if p == 0x9BB4:
                e.append(m[iy + 8])
            elif p == 0x9DCE:
                e.append('%04X' % ((r[harness.D] << 8) | r[harness.E]))
            main_ev.append(e)
            if call_open is not None:
                call_open['ev'].append(e)
        h.step(1)
    # pack: frames chain PRE -> POST -> next PRE; calls as diffs from their frame's POST
    seed = frames[0]['pre']
    prev = seed
    fr = []
    post_of = {}
    for f in frames:
        d = dict(i=f['i'], pre=pack(prev, f['pre']), post=pack(f['pre'], f['post']), r_isr=f['r_isr'],
                 r_main=f.get('r_main', []), ev_isr=f['ev_isr'], ev_main=f.get('ev_main', []),
                 passes=f.get('passes'), gate_calls=f.get('gate_calls'),
                 next_where=f.get('next_where'), next_in_fire=f.get('next_in_fire'),
                 next_chain=f.get('next_chain'))
        fr.append(d)
        post_of[f['i']] = f['post']
        prev = f['post']
    cl = []
    for c in calls:
        if c['isr'] not in post_of:
            continue
        base = post_of[c['isr']]
        cl.append(dict(isr=c['isr'], cut=c['cut'], ev=c['ev'], pre=pack(base, c['pre']),
                       post=pack(c['pre'], c['post'])))
    last_pre = frames[-1].get('next_pre')
    return dict(name=name, state=sc['state'], what=sc['what'], lo=sc['lo'], hi=sc['hi'],
                staged=[[at, fn.__doc__] for at, fn in sc.get('stage', [])],
                seed=base64.b64encode(bytes(seed)).decode(), frames=fr,
                last_pre=pack(prev, last_pre) if last_pre else None, calls=cl)


def phase_natural(jobs=5, names=None):
    names = names or list(SCENES)
    with ProcessPoolExecutor(max_workers=min(jobs, len(names))) as ex:
        out = list(ex.map(scene, names))
    for s in out:
        evs = {}
        for f in s['frames']:
            for e in f['ev_main']:
                evs[e[0]] = evs.get(e[0], 0) + 1
        print('natural %s (%s): %d frames, %d body calls (%d cut), events %s'
              % (s['name'], s['state'], len(s['frames']), len(s['calls']), sum(c['cut'] for c in s['calls']), evs))
    return dict(vector=ranges_of(VEC_N), vector_len=len(VEC_N), scenes=out)


# ---------------------------------------------------------------------------- the claims
def claims(out):
    """the oracle's own claims, each MEASURED above and re-checked here on the captured data"""
    c = []

    def claim(name, held, detail=''):
        c.append(dict(name=name, held=bool(held), detail=detail))
        print('claim %-5s %s %s' % ('HELD' if held else 'FAIL', name, detail))

    cen = out['census']
    refs = lambda t: sorted(r[0] for r in cen.get(t, []))
    claim('$9BB4 is entered from $9B0B only', refs('9BB4') == ['9B0B'])
    claim('$9D5C is written at $9D15 and $9D1F only; $9D8B at $9D18 and $9D22 only (and CALLed at $9C3D, $9C86, '
          '$9CD6, $9CEE)', refs('9D5C') == ['9D15', '9D1F'] and
          refs('9D8B') == ['9C3D', '9C86', '9CD6', '9CEE', '9D18', '9D22'])
    claim('$9D83 is written at $9BFE and $9C07 only; $9D82 is read at $9C04 and nowhere else',
          refs('9D83') == ['9BFE', '9C07'] and refs('9D82') == ['9C04'])
    claim('$9D77 has four callers, one of them the BOLT ($9ED0): $9D83 is shared state',
          refs('9D77') == ['9C01', '9C4B', '9C8C', '9ED0'])
    claim('$A355/$A349/$A33D are written inside $A314 only and $A34D is entered only from $A33E/$A344; $A304 is '
          'written at $A2F1 only and $A2FB entered only from $A2F4 -- set before use, never carried between calls',
          refs('A355') == ['A31A'] and refs('A349') == ['A323'] and refs('A33D') == ['A32A'] and
          refs('A34D') == ['A33E', 'A344'] and refs('A304') == ['A2F1'] and refs('A2FB') == ['A2F4'])
    claim('$9DD4 is reached from $BD74 only and $9DE1 from $9E50 only', refs('9DD4') == ['BD74'] and
          refs('9DE1') == ['9E50'])
    rows = out['direct']['rows']
    kinds = sorted(set(r['kind'] for r in rows))
    claim('the direct rows drive every kind (1, 5, 6, 7, 8) and seven default values',
          all(k in kinds for k in (1, 5, 6, 7, 8)) and
          sum(1 for r in rows if 'default' in r['marks']) == 7)
    arms = set(m for r in rows for m in r['marks'])
    claim('every branch mark is visited by some direct row', all(v in arms for v in MARKS.values()),
          str(sorted(set(MARKS.values()) - arms)))
    for w in ('1', '2'):
        sw = out['hit']['sweep'][w]
        hits = [(x, y) for x, y, k, t in sw if k]
        claim('the P%s hit set is exactly the projectile cell, 8 x 8 (64 of %d), and every kill leaves +4 = $64'
              % (w, len(sw)), sorted(hits) == [(x, y) for x in range(0x70, 0x78) for y in range(0x60, 0x68)] and
              all(t == 0x64 for x, y, k, t in sw if k))
    nat = {s['name']: s for s in out['natural']['scenes']}

    def ev(s, k):
        return sum(1 for f in s['frames'] for e in f['ev_main'] if e[0] == k)
    claim('N1: boulders spawn, wait, unmark, release and KILL P1', ev(nat['N1'], 'spawn') > 0 and
          ev(nat['N1'], 'unmark7') > 0 and ev(nat['N1'], 'release') > 0 and ev(nat['N1'], 'kill') > 0)
    claim('N5: bottles REVERSE and kill', ev(nat['N5'], 'reverse') > 0 and ev(nat['N5'], 'kill') > 0)
    claim('N7: drops spawn with no row match and kill', ev(nat['N7'], 'spawn') > 0 and ev(nat['N7'], 'kill') > 0)
    claim('N8: the fireball paints $42 and an enemy is corpsed ($8BC2) by the colour',
          ev(nat['N8'], 'fbpaint') > 0 and ev(nat['N8'], 'corpse') > 0)
    claim('N6: a staged breath kills P1 and every breath is released', ev(nat['N6'], 'kill') > 0 and
          ev(nat['N6'], 'release') >= 4)
    claim('the vectors hold no address below $4000 and no HUD glyph cell',
          all(lo >= 0x4000 for lo, hi in out['direct']['vector']) and
          all(lo >= 0x4000 for lo, hi in out['natural']['vector']))
    return c


# ---------------------------------------------------------------------------- driver
def capture(jobs=8):
    out = dict(census=phase_census(), direct=phase_direct(jobs), cost=phase_cost(jobs), hit=phase_hit(jobs),
               fireball=phase_fireball(), natural=phase_natural(min(jobs, 5)))
    out['mask'] = dict(hud=sum(1 for a in range(0x4000, 0x5800) if hud_masked(a)))
    out['assertions'] = claims(out)
    if not all(x['held'] for x in out['assertions']):
        raise Fail('a claim did not hold: %s' % [x['name'] for x in out['assertions'] if not x['held']])
    return out


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 8
    cmd = a[0] if a else 'capture'
    if cmd == 'capture':
        out = capture(jobs)
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new_ = json.loads(json.dumps(capture(jobs)))
        bad = [k for k in old if old[k] != new_.get(k)]
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd == 'direct':
        phase_direct(jobs)
    elif cmd == 'cost':
        phase_cost(jobs)
    elif cmd == 'hit':
        phase_hit(jobs)
    elif cmd == 'census':
        phase_census()
    elif cmd == 'fireball':
        phase_fireball()
    elif cmd == 'natural':
        names = [x for x in a[1:] if not x.startswith('--') and x in SCENES]
        phase_natural(min(jobs, 5), names or None)
    return 0


if __name__ == '__main__':
    sys.exit(main())
