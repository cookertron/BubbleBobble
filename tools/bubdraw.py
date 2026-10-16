"""$B9E7 -- the BUBBLE BLITTER: decode, verify, capture.

$B9E7 is not the 16x16 entity blitter.  Its one caller is $B653, inside the
twelve-slot bubble manager, on the risen-bubble path only.  What makes it
different, and what a display-only oracle cannot show, is that it reads the
CLEAN PLATFORM LAYER out of the shadow buffer (display + $A000) and composites
the bubble on top into the display file.  A draw is therefore a function of the
SHADOW as well as the display -- which is why the display-only oracle captured
in M7.5-vii looked like "neither a store nor an OR".

THE OPERATION, per pixel row, three columns from X >> 3, M = ($BFF8 + (X & 7)):

    col 0   disp = (disp & M)  | (shad & ~M) | spr      ($BA97-$BAA2)
    col 1   disp =  shad                     | spr      ($BAA5-$BAA9)
    col 2   disp = (disp & ~M) | (shad &  M) | spr      ($BAAB-$BAB6)

So the two edge columns keep the display outside the bubble's 24-pixel window
and take the clean background inside it; the middle column is wholly inside.

SIXTEEN rows from Y, and the sprite's 48 bytes run in BOUSTROPHEDON order --
row 0 left to right, row 1 right to left, alternating -- because the routine
walks L forward through a row and back through the next instead of reloading
it.  Two rows per DJNZ iteration, three blocks so the pointer can be re-fetched
from the $FD00 row table at each character-row boundary:

    even Y ($BA37): 8-(Y&7) rows, then 8, then (Y&7)      -- 16
    odd  Y ($BBC3): 8-(Y&7) rows (odd count, so the second block starts in the
                    reversed phase and adds 2 to its column -- $BC71), then 8,
                    then (Y&7)-1                          -- 16

TWO ROWS CARRY NO SPRITE.  The prologue at $BA78 is the loop body at $BA97 with
its three `OR` instructions REMOVED, so row 0 is a pure background restore (its
three sprite bytes are POPped and discarded), and the tail at $BB94 re-writes
the last row background-only.  Hence 51 writes to 48 addresses.

Usage:  python tools/bubdraw.py verify [--sweep]   model vs the machine
        python tools/bubdraw.py capture            rewrite the oracle fixture
        python tools/bubdraw.py d380               the $D380 builder ($BF5B)
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness
import portconfig as pc

SLOT, DRAW = 0xFED8, 0xB9E7
MASKTAB, ROWTAB, SHADOW = 0xBFF8, 0xFD00, 0xA000
BASES = {'EMPTY': 0xC780, 'HOLDING': 0xC900, 'FLASHING': 0xD380}
STATE = 'round1_48'
FIXTURE = 'build/bubdraw_fixture.json'
# the $D380 builder ($BF5B): source sprite, element-glyph pointer table, the
# element id it indexes with, and where the glyph is OR'd in.
ELEM_PTRS, ELEM_ID, GLYPH_AT = 0xC068, 0x7E0E, 0xD38C


def new(state=STATE):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    return h, h.memobj.m


def screen_addr(m, y):
    """the routine's own address for pixel row y: the $FD00 table, then (y & 7)
       added to the HIGH byte ($BA67 EX AF,AF' / ADD A,(HL))."""
    e = ROWTAB + 2 * ((y >> 3) & 0x1F)
    return (m[e] | ((m[e + 1] + (y & 7)) << 8)) & 0xFFFF


def row_base(m, y, x):
    """the row's first column address.  Both the column offset ($BA61 ADD A,(HL))
       and the walk along a row ($BAA3 INC L / $BAC3 DEC L) are EIGHT-BIT, so the
       three columns WRAP INSIDE the 256-byte page -- a bubble at the right edge
       of a row whose low byte is $FE writes $..FF then $..00, not the next page."""
    sa = screen_addr(m, y)
    return (sa & 0xFF00) | ((sa + (x >> 3)) & 0xFF)


def col_addr(base, c):
    return (base & 0xFF00) | ((base + c) & 0xFF)


def box_of(m, x, y, rows=16):
    return sorted({col_addr(row_base(m, (y + r) & 0xFF, x), c)
                   for r in range(rows) for c in range(3)})


def variant(m, slot=SLOT):
    """$B9FE-$BA1D.  (IY+9) is the bubble's KIND: 0 empty, 1 holding an enemy,
       2 water, 3 lightning, 4 fire (MEASURED from the el* states).  A holding
       bubble past age $E6 FLASHES, alternating with the empty sprite on the
       $B62D toggle -- it does NOT switch to $D380."""
    k = m[slot + 9]
    if k == 1:
        return 'HOLDING' if (m[slot + 4] < 0xE6 or m[0xB62D] != 0) else 'EMPTY'
    return 'EMPTY' if k == 0 else 'FLASHING'


def predict(m, x, y, sprite):
    """every write $B9E7 makes, in order, as (addr, value).  `m` is the memory
       BEFORE the call; a private display overlay threads earlier rows into
       later reads, as the machine's own stores do."""
    disp = {}
    rd = lambda a: disp.get(a, m[a])
    mask = m[MASKTAB + (x & 7)]
    nmask = mask ^ 0xFF
    out = []

    def row(r, withspr):
        base = row_base(m, (y + r) & 0xFF, x)
        cols = (0, 1, 2) if (r & 1) == 0 else (2, 1, 0)
        for i, c in enumerate(cols):
            a = col_addr(base, c)
            s = m[(a + SHADOW) & 0xFFFF]
            spr = sprite[3 * r + i] if withspr else 0
            if c == 0:
                v = (rd(a) & mask) | (s & nmask) | spr
            elif c == 1:
                v = s | spr
            else:
                v = (rd(a) & nmask) | (s & mask) | spr
            disp[a] = v
            out.append((a, v))

    for r in range(16):
        row(r, r != 0)                      # $BA78: row 0 has no OR -- pure restore
    # the $BB94 tail: the last row again, background only, left to right
    base = row_base(m, (y + 15) & 0xFF, x)
    for c in (0, 1, 2):
        a = col_addr(base, c)
        s = m[(a + SHADOW) & 0xFFFF]
        v = ((rd(a) & mask) | (s & nmask)) if c == 0 else \
            (s if c == 1 else ((rd(a) & nmask) | (s & mask)))
        disp[a] = v
        out.append((a, v))
    return out


# ------------------------------------------------------------------ the ERASE
#
# $BF16 is NOT a bubble routine.  It calls the ENTITY draw master $A447 with two
# self-modifying patches -- $A5D9 (the junction where the erase half ends and the
# draw half begins) set to RET, and $A480's `JP nz` made unconditional -- and the
# flags forced to $C0.  The effect is "run only the ERASE half", which repaints
# the 3x16 box at the CACHED position (IY+2 = Y, IY+3 = X) from the shadow, with
# exactly the composite the bubble blitter uses for its two sprite-less rows:
#
#     col 0   disp = (disp & M)  | (shad & ~M)
#     col 1   disp =  shad
#     col 2   disp = (disp & ~M) | (shad &  M)
#
# TWO differences from $B9E7, both measured.  The mask comes from the ENTITY
# table $AA4F indexed by **X & 6**, not $BFF8 indexed by X & 7 -- same eight
# bytes, but the erase snaps to the entity blitter's even sub-position, so for
# an odd X it uses a mask one step coarser than the draw did.  And the
# boustrophedon restarts FORWARD at each of the three block boundaries
# (8-(Y&7), 8, Y&7 rows) because each block re-derives its address from the row
# table, where $B9E7 runs one unbroken zig-zag.
ERASE = 0xBF16
ENT_MASK = 0xAA4F


def predict_erase(m, cx, cy):
    """every write $BF16 makes, in order.  Nothing at all if the cached Y is
       >= $C0 ($A466 JP nc -> the patched RET)."""
    if cy >= 0xC0:
        return []
    disp = {}
    rd = lambda a: disp.get(a, m[a])
    mask = m[ENT_MASK + (cx & 6)]
    nmask = mask ^ 0xFF
    out = []
    n1 = 8 - (cy & 7)                       # the three blocks, each restarting forward
    for r in range(16):
        i = r if r < n1 else (r - n1 if r < n1 + 8 else r - n1 - 8)
        base = row_base(m, (cy + r) & 0xFF, cx)
        for c in ((0, 1, 2) if (i & 1) == 0 else (2, 1, 0)):
            a = col_addr(base, c)
            s = m[(a + SHADOW) & 0xFFFF]
            v = ((rd(a) & mask) | (s & nmask)) if c == 0 else \
                (s if c == 1 else ((rd(a) & nmask) | (s & mask)))
            disp[a] = v
            out.append((a, v))
    return out


def call_erase(h, slot=SLOT):
    h.memobj.watch(0x4000, 0x5B00)
    h.call(ERASE, regs={'IY': slot})
    log = [(a, v) for _pc, a, v in h.memobj.log]
    h.memobj.unwatch()
    return log


def arm(m, x, y, holding, age, b62d=None, slot=SLOT):
    if b62d is not None:
        m[0xB62D] = b62d
    m[slot + 5], m[slot + 6] = x & 0xFF, y & 0xFF
    m[slot + 9], m[slot + 4] = holding & 0xFF, age & 0xFF
    m[slot + 7] = 0x84                       # active + risen
    return variant(m, slot)


def call_draw(h, slot=SLOT):
    h.memobj.watch(0x4000, 0x5B00)
    h.call(DRAW, regs={'IY': slot})
    log = [(a, v) for _pc, a, v in h.memobj.log]
    h.memobj.unwatch()
    return log


def sprite_of(m, kind, x):
    base = BASES[kind] + 48 * (x & 7)
    return bytes(m[base:base + 48])


# ---------------------------------------------------------------- the oracle
#
# Two properties of the RESTING scene hide most of the routine, and an oracle
# captured on it alone is green against a blitter that gets the operation quite
# wrong (the first mutation battery on this increment: six survivors):
#
#   * the display EQUALS the shadow at every address a draw touches, because
#     the platform layer has just been restored.  While d == s, reading the
#     shadow and reading the display are the same thing, and the two edge
#     masks are interchangeable -- (d&M)|(s&~M) == (d&~M)|(s&M).
#   * rows 0 and 15 of the real bubble sprites are BLANK, so discarding row 0's
#     sprite bytes and re-writing the last row background-only are both
#     invisible.
#
# So cases carry two flags.  DIRTY fills the box in the DISPLAY with a pattern
# the shadow does not have -- exactly the state the machine is in when a sprite
# was composited there -- and SYNTH replaces the sprite table with one whose
# every byte is non-zero, which forces all sixteen rows to show.  Together they
# make each of those structural facts observable.
def dirty_pattern(a):
    return ((a * 5) ^ 0xA5) & 0xFF


def synth_table():
    """384 bytes, none of them zero and none equal to the dirty pattern, so a
       row taken from the wrong place shows up as a wrong byte."""
    return bytes((((i * 7 + 0x13) & 0xFF) or 0xFF) for i in range(384))


#        x    y   kind age  b62d  dirty  synth  label
CASES = ([(80 + s, 96 + (s & 1), 0, 0x20, None, 0, 0,
           f'xshift{s}_{"odd" if s & 1 else "even"}') for s in range(8)] +
         [(84, 88, 0, 0x20, None, 0, 0, 'over_platform_even'),
          (84, 89, 0, 0x20, None, 0, 0, 'over_platform_odd'),
          (84, 96, 1, 0x20, 0, 0, 0, 'holding'),
          (85, 97, 1, 0x20, 0, 0, 0, 'holding_shift1_odd'),
          (84, 96, 1, 0xF0, 0, 0, 0, 'holding_past_E6_toggle_clear'),   # -> EMPTY
          (84, 96, 1, 0xF0, 1, 0, 0, 'holding_past_E6_toggle_set'),     # -> HOLDING
          (84, 96, 2, 0x20, None, 0, 0, 'element_water'),
          (84, 97, 3, 0x20, None, 0, 0, 'element_lightning_odd'),
          (86, 96, 4, 0x20, None, 0, 0, 'element_fire'),
          (16, 96, 0, 0x20, None, 0, 0, 'left_edge'),
          (240, 96, 0, 0x20, None, 0, 0, 'right_edge'),
          (84, 32, 0, 0x20, None, 0, 0, 'high_row'),
          (248, 120, 0, 0x20, None, 1, 1, 'page_wrap_col31_even'),
          (248, 121, 0, 0x20, None, 1, 1, 'page_wrap_col31_odd'),
          (250, 56, 0, 0x20, None, 1, 1, 'page_wrap_row7'),
          (84, 168, 0, 0x20, None, 0, 0, 'low_row'),
          # the display made to DIFFER from the shadow -- the edge masks and the
          # shadow source only become observable here
          (84, 96, 0, 0x20, None, 1, 0, 'dirty_bg_even'),
          (85, 97, 0, 0x20, None, 1, 0, 'dirty_bg_odd'),
          (80, 96, 0, 0x20, None, 1, 0, 'dirty_bg_shift0_even'),
          (87, 97, 0, 0x20, None, 1, 0, 'dirty_bg_shift7_odd'),
          # ...and with every sprite byte non-zero, so rows 0 and 15 show
          (84, 96, 0, 0x20, None, 1, 1, 'synth_dirty_even'),
          (83, 97, 0, 0x20, None, 1, 1, 'synth_dirty_odd'),
          (80, 96, 0, 0x20, None, 1, 1, 'synth_dirty_shift0'),
          (87, 97, 0, 0x20, None, 1, 1, 'synth_dirty_shift7'),
          (86, 88, 0, 0x20, None, 1, 1, 'synth_dirty_over_platform'),
          # the $FD00 SENTINEL rows: char rows 0 and 1 hold $01FF, not a screen
          # address, so those writes land in ROM and are DROPPED.  A blitter
          # that computes the ULA address instead would scribble on the HUD.
          (84, 8, 0, 0x20, None, 1, 1, 'sentinel_half_row1'),
          (84, 0, 0, 0x20, None, 1, 1, 'sentinel_all_hud')])


def capture():
    h, m = new()
    cases = []
    empty_save = bytes(m[BASES['EMPTY']:BASES['EMPTY'] + 384])
    synth = synth_table()
    for (x, y, hold, age, b62d, dirty, use_synth, label) in CASES:
        m[BASES['EMPTY']:BASES['EMPTY'] + 384] = synth if use_synth else empty_save
        kind = arm(m, x, y, hold, age, b62d)
        # the BOX: three columns by seventeen rows (sixteen plus the tail's
        # repeat), recorded whole so untouched addresses are gated too
        box = box_of(m, x, y)
        clean = {a: m[a] for a in box}            # before dirtying, to restore from
        if dirty:
            for a in box:
                if a >= 0x4000:
                    m[a] = dirty_pattern(a)
        snap = bytes(m)
        writes = call_draw(h)
        cases.append({
            'label': label, 'x': x, 'y': y, 'holding': hold, 'age': age,
            'b62d': m[0xB62D], 'kind': kind, 'xshift': x & 7, 'ypar': y & 1,
            'dirty': dirty, 'synth': use_synth,
            'sprite': base64.b64encode(synth).decode() if use_synth else None,
            'writes': [{'a': a, 'v': v} for a, v in writes],
            'box': box,
            'before': {str(a): snap[a] for a in box},
            'shadow': {str(a): snap[(a + SHADOW) & 0xFFFF] for a in box},
            'after': {str(a): m[a] for a in box},
        })
        # restore the display so cases do not accumulate
        for a, v in clean.items():
            if a >= 0x4000:
                m[a] = v
    m[BASES['EMPTY']:BASES['EMPTY'] + 384] = empty_save
    img = open('build/image.bin', 'rb').read()
    tape = open('build/image_tape.bin', 'rb').read()
    fx = {
        'note': ('BUBBLE DRAW oracle. $B9E7 composites the SHADOW buffer (display + $A000) '
                 'and the display: col0 (disp&M)|(shad&~M)|spr, col1 shad|spr, col2 '
                 '(disp&~M)|(shad&M)|spr, M = ($BFF8 + (X&7)).  16 rows from Y, sprite bytes '
                 'in BOUSTROPHEDON order (row 0 L-to-R, row 1 R-to-L).  Row 0 carries no '
                 'sprite ($BA78 omits the ORs) and the $BB94 tail re-writes the last row '
                 'background-only, so 51 writes land on 48 addresses.  (IY+9) is the KIND: '
                 '0 empty, 1 holding, 2 water, 3 lightning, 4 fire.'),
        'state': STATE, 'shift_stride': 48, 'shifts': 8,
        'bases': {k: v for k, v in BASES.items()},
        'masktable': [m[MASKTAB + i] for i in range(8)],
        'rowtable': [m[ROWTAB + 2 * i] | (m[ROWTAB + 2 * i + 1] << 8) for i in range(24)],
        'provenance': {
            'EMPTY': {'addr': '$C780', 'source': 'tape (static)',
                      'identical_to_image': sum(1 for i in range(384) if m[0xC780 + i] == img[0xC780 + i]),
                      'identical_to_tape': sum(1 for i in range(384) if m[0xC780 + i] == tape[0xC780 + i]),
                      'of': 384},
            'HOLDING': {'addr': '$C900', 'source': 'tape (static)',
                        'identical_to_image': sum(1 for i in range(384) if m[0xC900 + i] == img[0xC900 + i]),
                        'identical_to_tape': sum(1 for i in range(384) if m[0xC900 + i] == tape[0xC900 + i]),
                        'of': 384},
            'FLASHING': {'addr': '$D380', 'source': 'RUNTIME-BUILT by $BF5B',
                         'identical_to_image': sum(1 for i in range(384) if m[0xD380 + i] == img[0xD380 + i]),
                         'identical_to_tape': sum(1 for i in range(384) if m[0xD380 + i] == tape[0xD380 + i]),
                         'of': 384},
        },
        'sprites': {k: base64.b64encode(bytes(m[v:v + 384])).decode() for k, v in BASES.items()},
        'cases': cases,
    }
    fx['d380'] = d380_oracle()
    fx['erase'] = {
        'note': ('$BF16: the ENTITY master $A447 with $A5D9 patched to RET (so only its ERASE '
                 'half runs) and $A480 made unconditional.  Repaints the 3x16 box at the CACHED '
                 'position (IY+2 = Y, IY+3 = X) from the shadow: col0 (disp&M)|(shad&~M), '
                 'col1 shad, col2 (disp&~M)|(shad&M).  Mask from the ENTITY table $AA4F indexed '
                 'by X & 6 -- NOT $BFF8 by X & 7.  Boustrophedon restarts FORWARD at each of the '
                 'three block boundaries (8-(Y&7), 8, Y&7 rows).  Cached Y >= $C0 writes nothing.'),
        'mask_table': [m[ENT_MASK + i] for i in range(8)],
        'mask_addr': ENT_MASK,
        'callers': {'$BE55': 'travel: erase then JP $B9E7 draw',
                    '$BEA9': 'capture tail: erase then JP $B9E7 draw',
                    '$BEE8': 'the travel -> rise transition, before +3 is parked at 2'},
        'cases': capture_erase(h, m),
    }
    json.dump(fx, open(FIXTURE, 'w'), indent=1)
    print(f'wrote {FIXTURE}: {len(cases)} cases, '
          f'{sum(len(c["writes"]) for c in cases)} writes, '
          f'{len(fx["d380"]["states"])} $D380 build oracles')

    # the SHIPPING asset: the two static tables, all eight shifts each.  $D380
    # is deliberately absent -- it is built at runtime, not loaded.
    asset = {
        'note': ('The two STATIC bubble sprite tables, 8 pre-shifted copies of 48 bytes each '
                 '(stride 48, index X & 7).  Byte-identical in build/image_tape.bin, '
                 'build/image.bin and every current in-play state -- tape data, not built. '
                 'The third base $D380 is NOT here: it is rebuilt at runtime by $BF5B '
                 'whenever the element changes.'),
        'stride': 48, 'shifts': 8, 'rows': 16, 'cols': 3,
        'empty': {'addr': 0xC780, 'b64': base64.b64encode(bytes(m[0xC780:0xC780 + 384])).decode()},
        'holding': {'addr': 0xC900, 'b64': base64.b64encode(bytes(m[0xC900:0xC900 + 384])).decode()},
        'rowtable': [m[ROWTAB + 2 * i] | (m[ROWTAB + 2 * i + 1] << 8) for i in range(24)],
        'masktable': [m[MASKTAB + i] for i in range(8)],
        'elem_ptrs': [m[ELEM_PTRS + 2 * i] | (m[ELEM_PTRS + 2 * i + 1] << 8) for i in range(12)],
        'provenance': fx['provenance'],
    }
    json.dump(asset, open('build/bubble_sprites.json', 'w'), indent=1)
    print('wrote build/bubble_sprites.json: EMPTY + HOLDING, 384 bytes each')


# --------------------------------------------------- the $D380 element build
def build_d380(m, elem):
    """$BF5B transliterated.  Copy the EMPTY table, OR the element glyph into
       rows 4..11 of shift 0, then generate the other seven shifts by shifting
       each 24-bit row right one bit at a time."""
    b = bytearray(m[BASES['EMPTY']:BASES['EMPTY'] + 384])          # $BF66 LDIR
    p = ELEM_PTRS + 2 * (elem - 2)                                 # $BF71-$BF7D
    g = m[p] | (m[p + 1] << 8)
    ix = GLYPH_AT - 0xD380                                         # $BF82 -> row 4
    for _ in range(4):                                             # $BF89 LD B,4
        v = m[g]; b[ix] |= v >> 4; b[ix + 1] |= (v << 4) & 0xF0    # even row: cols 0,1
        g += 1
        v = m[g]; b[ix + 5] |= v >> 4; b[ix + 4] |= (v << 4) & 0xF0  # odd row, reversed
        g += 1
        ix += 6                                                    # $BFB1 ADD IX,6
    for s in range(7):                                             # $BFB9 LD A,7
        src, dst = 48 * s, 48 * (s + 1)
        b[dst:dst + 48] = b[src:src + 48]                          # $BFC4 LDIR
        i = dst
        for _ in range(8):                                         # $BFCA LD B,8
            c = 0
            for k in (0, 1, 2):                                    # even row: +0,+1,+2
                nc = b[i + k] & 1; b[i + k] = (b[i + k] >> 1) | (c << 7); c = nc
            i += 5                                                 # $BFD4 ADD HL,3 after +2
            c = 0
            for k in (0, -1, -2):                                  # odd row: +5,+4,+3
                nc = b[i + k] & 1; b[i + k] = (b[i + k] >> 1) | (c << 7); c = nc
            i += 1                                                 # $BFE2 INC HL
    return bytes(b)


def d380_oracle():
    out = {'note': ('$D380 is RUNTIME-BUILT by $BF5B (one caller, $94B7): LDIR $C780 -> $D380, '
                    'OR the element glyph at ($C068 + 2*(($7E0E) - 2)) into rows 4-11 of shift 0, '
                    'then generate shifts 1-7 by shifting each 24-bit row right one bit. '
                    'That is why it is an EXACT pre-shift table while $C780/$C900, which are '
                    'hand-drawn tape data, are not.'),
            'elem_ptrs': ELEM_PTRS, 'elem_id_at': ELEM_ID, 'glyph_at': GLYPH_AT,
            'states': []}
    for st in ('elfire', 'elwater', 'ellight', STATE):
        try:
            _h, m = new(st)
        except Exception:
            continue
        elem = m[ELEM_ID]
        row = {'state': st, 'elem': elem,
               'empty': base64.b64encode(bytes(m[0xC780:0xC780 + 384])).decode(),
               'glyph': base64.b64encode(bytes(m[0xB600:0xB600 + 0x40])).decode(),
               'ptrs': [m[ELEM_PTRS + i] for i in range(8)],
               'live': base64.b64encode(bytes(m[0xD380:0xD380 + 384])).decode()}
        if 2 <= elem <= 4:
            built = build_d380(m, elem)
            row['python_matches'] = sum(1 for i in range(384) if built[i] == m[0xD380 + i])
        out['states'].append(row)
    return out


# ------------------------------------------------------------------ verbs
def verify(sweep=False):
    h, m = new()
    fx = json.load(open(FIXTURE)) if __import__('os').path.exists(FIXTURE) else None
    bad = 0
    if fx:
        print(f'=== {len(fx["cases"])} recorded oracle cases ===')
        empty_save = bytes(m[BASES['EMPTY']:BASES['EMPTY'] + 384])
        for c in fx['cases']:
            if c.get('sprite'):
                m[BASES['EMPTY']:BASES['EMPTY'] + 384] = base64.b64decode(c['sprite'])
            else:
                m[BASES['EMPTY']:BASES['EMPTY'] + 384] = empty_save
            kind = arm(m, c['x'], c['y'], c['holding'], c['age'], c.get('b62d'))
            clean = {int(a): m[int(a)] for a in c['before']}
            for a, v in c['before'].items():
                if int(a) >= 0x4000:
                    m[int(a)] = v
            snap = bytes(m)
            got = call_draw(h)
            want = [(w['a'], w['v']) for w in c['writes']]
            pred = [(a, v) for a, v in predict(snap, c['x'], c['y'], sprite_of(m, kind, c['x']))
                    if a >= 0x4000]
            ok = got == want and got == pred
            bad += not ok
            print(f'  {"ok  " if ok else "FAIL"} {c["label"]:30s} x={c["x"]:3d} y={c["y"]:3d} '
                  f'kind={kind:8s} writes={len(got):2d}'
                  f'{"  dirty" if c.get("dirty") else ""}{" synth" if c.get("synth") else ""}')
            if not ok:
                for i in range(max(len(got), len(pred))):
                    if (got[i] if i < len(got) else None) != (pred[i] if i < len(pred) else None):
                        print(f'       vs model [{i}] got {got[i] if i<len(got) else None} '
                              f'pred {pred[i] if i<len(pred) else None}')
                        break
            for a, v in clean.items():
                if a >= 0x4000:
                    m[a] = v
        m[BASES['EMPTY']:BASES['EMPTY'] + 384] = empty_save
        print(f'-> {len(fx["cases"]) - bad}/{len(fx["cases"])} match both the recorded oracle and the model')
    if sweep:
        n = f = 0
        for x in range(64, 80):
            for y in range(88, 104):
                for (hold, age, b62d) in ((0, 0x20, 0), (1, 0x20, 0), (1, 0xF0, 0),
                                          (1, 0xF0, 1), (2, 0x20, 0), (4, 0x20, 0)):
                    kind = arm(m, x, y, hold, age, b62d)
                    snap = bytes(m)
                    got = call_draw(h)
                    n += 1
                    if got != predict(snap, x, y, sprite_of(m, kind, x)):
                        f += 1
                        if f <= 3:
                            print(f'  SWEEP FAIL x={x} y={y} kind={kind}')
                    for a, _v in got:
                        m[a] = snap[a]
        print(f'-> sweep {n - f}/{n} match the model')
        bad += f
    return bad


#             cx   cy   dirty  label
ERASE_CASES = [(84, 96, 1, 'erase_even_x_even_y'),
               (85, 97, 1, 'erase_odd_x_odd_y'),
               (86, 96, 1, 'erase_x6_6'),
               (82, 99, 1, 'erase_x6_2_y7_3'),
               (80, 96, 1, 'erase_aligned_mask0'),
               (81, 96, 1, 'erase_odd_x_mask0'),       # X&6 == 0 but X&7 == 1
               (83, 103, 1, 'erase_y7_7'),
               (84, 88, 1, 'erase_over_platform'),
               (84, 96, 0, 'erase_clean_bg'),
               (16, 120, 1, 'erase_left_edge'),
               (240, 120, 1, 'erase_right_edge'),
               (248, 120, 1, 'erase_page_wrap_col31'),
               (250, 56, 1, 'erase_page_wrap_row7'),
               (84, 8, 1, 'erase_sentinel_half'),
               (84, 0, 1, 'erase_sentinel_all'),
               (84, 0xC0, 1, 'erase_cached_Y_ge_C0_skips'),
               (84, 0xC8, 1, 'erase_cached_Y_high_skips')]


def capture_erase(h, m):
    cases = []
    for (cx, cy, dirty, label) in ERASE_CASES:
        m[SLOT + 0], m[SLOT + 1] = 0x80, 0xC7
        m[SLOT + 2], m[SLOT + 3] = cy & 0xFF, cx & 0xFF
        m[SLOT + 5], m[SLOT + 6] = cx & 0xFF, cy & 0xFF
        m[SLOT + 7] = 0x84
        box = box_of(m, cx, cy)
        clean = {a: m[a] for a in box}
        if dirty:
            for a in box:
                if a >= 0x4000:
                    m[a] = dirty_pattern(a)
        snap = bytes(m)
        writes = call_erase(h)
        cases.append({
            'label': label, 'cx': cx, 'cy': cy, 'dirty': dirty,
            'writes': [{'a': a, 'v': v} for a, v in writes],
            'box': box,
            'before': {str(a): snap[a] for a in box},
            'shadow': {str(a): snap[(a + SHADOW) & 0xFFFF] for a in box},
            'after': {str(a): m[a] for a in box},
        })
        for a, v in clean.items():
            if a >= 0x4000:
                m[a] = v
    return cases


def verify_erase(sweep=False):
    h, m = new()
    fx = json.load(open(FIXTURE))
    bad = 0
    print(f'=== {len(fx["erase"]["cases"])} erase oracle cases ===')
    for c in fx['erase']['cases']:
        m[SLOT + 2], m[SLOT + 3] = c['cy'] & 0xFF, c['cx'] & 0xFF
        m[SLOT + 5], m[SLOT + 6] = c['cx'] & 0xFF, c['cy'] & 0xFF
        m[SLOT + 7] = 0x84
        clean = {int(a): m[int(a)] for a in c['before']}
        for a, v in c['before'].items():
            if int(a) >= 0x4000:
                m[int(a)] = v
        snap = bytes(m)
        got = call_erase(h)
        want = [(w['a'], w['v']) for w in c['writes']]
        pred = [(a, v) for a, v in predict_erase(snap, c['cx'], c['cy']) if a >= 0x4000]
        ok = got == want and got == pred
        bad += not ok
        print(f'  {"ok  " if ok else "FAIL"} {c["label"]:32s} x={c["cx"]:3d} y={c["cy"]:3d} '
              f'writes={len(got):2d}')
        if not ok:
            for i in range(max(len(got), len(pred))):
                if (got[i] if i < len(got) else None) != (pred[i] if i < len(pred) else None):
                    print(f'       [{i}] got {got[i] if i<len(got) else None} '
                          f'pred {pred[i] if i<len(pred) else None}')
                    break
        for a, v in clean.items():
            if a >= 0x4000:
                m[a] = v
    print(f'-> {len(fx["erase"]["cases"]) - bad}/{len(fx["erase"]["cases"])} erase cases match')
    if sweep:
        n = f = 0
        for cx in range(64, 80):
            for cy in range(88, 104):
                m[SLOT + 2], m[SLOT + 3] = cy, cx
                m[SLOT + 7] = 0x84
                box = box_of(m, cx, cy)
                clean = {a: m[a] for a in box}
                for a in box:
                    if a >= 0x4000:
                        m[a] = dirty_pattern(a)
                snap = bytes(m)
                got = call_erase(h)
                n += 1
                if got != [(a, v) for a, v in predict_erase(snap, cx, cy) if a >= 0x4000]:
                    f += 1
                    if f <= 3:
                        print(f'  SWEEP FAIL cx={cx} cy={cy}')
                for a, v in clean.items():
                    if a >= 0x4000:
                        m[a] = v
        print(f'-> erase sweep {n - f}/{n} match')
        bad += f
    return bad


def main():
    v = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if v == 'capture':
        capture()
    elif v == 'erase':
        sys.exit(1 if verify_erase('--sweep' in sys.argv) else 0)
    elif v == 'd380':
        o = d380_oracle()
        for r in o['states']:
            print(f'  {r["state"]:10s} element={r["elem"]}  '
                  f'python build matches live $D380: {r.get("python_matches", "n/a")}/384')
    else:
        sys.exit(1 if verify('--sweep' in sys.argv) else 0)


if __name__ == '__main__':
    main()
