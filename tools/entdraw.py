"""$A447 / $A3AD -- the ENTITY render pass.  Decode, verify, capture.

This is how the display is actually maintained, and it is not what the engine
was doing.  MEASURED on round1_48: the whole-screen platform restore $8216 does
NOT run per frame (0 executions in 20 frames).  Instead 272-288 display writes
happen on the ODD-parity ISR frame and ZERO on the even one, all from pages
$A4-$A7.  Each entity is ERASED at its CACHED position and REDRAWN at its
current one, and the draw updates the cache.  So the display is maintained
incrementally, and anything drawn into it -- a bubble, say -- persists.

$A447, per entity (IY = a $FD80 slot, stride 10):

  gates      bit7 of +7 clear, or bit3 set  -> $A437: mark done, draw nothing
             bit6 clear (no cached position) -> skip the erase, and SET bit6
             cached Y (+2) >= $C0            -> skip the erase
  erase      at (+3, +2).  (+3) & 6 == 0 takes the ALIGNED path $A483: TWO
             columns, a PLAIN COPY from the shadow, no mask.  Otherwise the
             SHIFTED path $A53C: three columns, masked from $AA4F + ((+3) & 6),
             exactly the composite $BF16 uses.  Sixteen rows either way, in
             three blocks (8-(Y&7), 8, Y&7) that each restart FORWARD.
  mark       SET bit5 of +7, DEC ($AA5F) -- counted as done even if not drawn
  flash      on the $A3B2 toggle phase 0, slots 0 and 1 ONLY: if bit3 of
             (IY+$5A) is set ($FDDA / $FDE4, the player state byte) the routine
             RETURNS without drawing -- that IS the invulnerability flash.  The
             cache is then NOT updated, so the next frame still erases the old
             position and the player reappears there.
  draw       (+3) := (+5), (+2) := (+6), then the 16x16 masked blit at (+5,+6):
             `screen = (screen AND mask) OR data`, two screen bytes when X & 6
             == 0 and three otherwise, rows in order, columns left to right.

Both halves address rows through the $FD00 table (so character rows 0-1, which
hold the sentinel $01FF, address ROM and are dropped) and walk columns with
EIGHT-BIT arithmetic, so a row's columns wrap inside the 256-byte page.

$A3AD, the pass, is a BEAM-CHASING SCHEDULER, not a simple loop:

  toggle $A3B2 ^= 1; clear bit5 on +7 of NINE slots; ($AA58) = ($AA5F) = ($AA57)
  seed the beam accumulator ($A431) = $B9
  each visit: acc += 1; window = [acc, acc + $1E); SKIP this entity if any of
    (+6), (+6)+$10, (+2), (+2)+$10 lands inside it ($A42B, plain 8-bit compares
    -- so when acc + $1E WRAPS, the window is empty and nothing is skipped).
    Otherwise draw it if bit5 is clear.  acc += 1 per slot either way, and the
    drawing itself adds MEASURED 7 (aligned erase) or 20 (shifted erase) plus 8
    (aligned draw) or 11 (shifted draw).
  after ($AA57) slots, rewind to $FD80 and sweep AGAIN while ($AA5F) != 0.

Usage:  python tools/entdraw.py verify [--sweep]
        python tools/entdraw.py capture
        python tools/entdraw.py carry     (merges `carry_calls` into the fixture; capture runs it too)
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

MASTER, PASS, PASS_RET = 0xA447, 0xA3AD, 0xA42A
TABLE, STRIDE, SLOTS = 0xFD80, 10, 12
ROWTAB, SHADOW = 0xFD00, 0xA000
ENT_MASK = 0xAA4F
TOGGLE, COUNT, LEFT, SWEEP, ACC = 0xA3B2, 0xAA57, 0xAA5F, 0xAA58, 0xA431
PLAYER_STATE = 0x5A                     # (IY+$5A) -> $FDDA / $FDE4
STATE = 'round1_48'
FIXTURE = 'build/entdraw_fixture.json'
ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
# MEASURED beam-accumulator costs (scratchpad ent4): the $A430 CALLs at $A485 (after
# $A483 LD A,7), $A56A, $A616 and $A708 (inside the shifted draw, entered at $A6F3).
ACC_ERASE = {False: 7, True: 20}        # keyed by "shifted"
ACC_DRAW = {False: 8, True: 11}


def new(state=STATE):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    return h, h.memobj.m


# ----------------------------------------------------------------- addressing
def screen_addr(m, y):
    e = ROWTAB + 2 * ((y >> 3) & 0x1F)
    return (m[e] | ((m[e + 1] + (y & 7)) << 8)) & 0xFFFF


def row_base(m, y, x):
    """EIGHT-BIT: $A64D `ADD A,L`, $A49C `ADD HL,BC` then only L is walked."""
    sa = screen_addr(m, y)
    return (sa & 0xFF00) | ((sa + (x >> 3)) & 0xFF)


def col_addr(base, c):
    return (base & 0xFF00) | ((base + c) & 0xFF)


def block_index(y):
    """(row, index within its block) -- each block restarts its zig-zag FORWARD"""
    n1 = 8 - (y & 7)
    return [(r, r if r < n1 else (r - n1 if r < n1 + 8 else r - n1 - 8)) for r in range(16)]


# --------------------------------------------------------------------- erase
def erase_writes(m, cx, cy):
    if cy >= 0xC0:                                   # $A464 CP $C0 / JP nc
        return []
    disp, out = {}, []
    rd = lambda a: disp.get(a, m[a])
    shifted = (cx & 6) != 0                          # $A47E AND 6 / $A480 JP nz
    mask = m[ENT_MASK + (cx & 6)]
    nmask = mask ^ 0xFF
    ncol = 3 if shifted else 2
    for r, i in block_index(cy):
        base = row_base(m, (cy + r) & 0xFF, cx)
        order = list(range(ncol)) if (i & 1) == 0 else list(reversed(range(ncol)))
        for c in order:
            a = col_addr(base, c)
            s = m[(a + SHADOW) & 0xFFFF]
            if not shifted:
                v = s                                # $A4A5: a plain copy, both columns
            elif c == 0:
                v = (rd(a) & mask) | (s & nmask)
            elif c == 1:
                v = s
            else:
                v = (rd(a) & nmask) | (s & mask)
            disp[a] = v
            out.append((a, v))
    return out


# ---------------------------------------------------------------------- draw
def draw_writes(m, spr, X, Y):
    """the 16x16 masked blit ($A614 aligned / $A6F3 shifted).  The sprite is 352
       bytes = FOUR pre-shifted copies picked by X & 6."""
    x = X & 0xFE
    s = x & 6
    nb = 3 if s else 2
    o = spr + (2 * (24 * s - 16) if s else 0)
    disp, out = {}, []
    rd = lambda a: disp.get(a, m[a])
    for r in range(16):
        base = row_base(m, (Y + r) & 0xFF, x)
        for i in range(nb):
            a = col_addr(base, i)
            mask, data = m[o + 2 * i], m[o + 2 * i + 1]
            v = (rd(a) & mask) | data
            disp[a] = v
            out.append((a, v))
        o += nb * 2
    return out


# --------------------------------------------------------------------- $A447
def predict_call(m, slot, toggle=None):
    """returns (ordered writes, {field offset: new value}, beam-accumulator cost)"""
    if toggle is None:
        toggle = m[TOGGLE]
    f = m[slot + 7]
    if not (f & 0x80) or (f & 0x08):                 # $A451 JP p / $A456 JR nz -> $A437
        return [], {7: f | 0x20}, 0                  # $A43E SET 5 (and DEC ($AA5F))
    out, cost = [], 0
    f |= 0x40                                        # $A45A SET 6,(IY+7)
    if (m[slot + 7] & 0x40) and m[slot + 2] < 0xC0:
        out += erase_writes(m, m[slot + 3], m[slot + 2])
        cost += ACC_ERASE[(m[slot + 3] & 6) != 0]
    f |= 0x20                                        # $A5E0 SET 5,(IY+7)
    fields = {7: f}
    is_player = (slot - TABLE) in (0, STRIDE)
    if (toggle & 1) == 0 and is_player and (m[slot + PLAYER_STATE] & 0x08):
        return out, fields, cost                     # $A5FF RET -- the invuln FLASH
    fields[3] = m[slot + 5]                          # $A603 (IY+3) := (IY+5)
    fields[2] = m[slot + 6]                          # $A623 (IY+2) := (IY+6)
    mm = bytearray(m)                                # the draw reads the erased display
    for a, v in out:
        if a >= 0x4000:
            mm[a] = v
    out += draw_writes(mm, m[slot] | (m[slot + 1] << 8), m[slot + 5], m[slot + 6])
    cost += ACC_DRAW[(m[slot + 5] & 6) != 0]
    return out, fields, cost


# --------------------------------------------------------------------- $A3AD
def predict_pass(m):
    """the whole scheduler: the ordered writes of the entire pass, and the world
       it leaves behind (a copy)."""
    mm = bytearray(m)
    mm[TOGGLE] ^= 1                                  # $A3B1-$A3B5
    for k in range(9):                               # $A3C0: NINE slots, not twelve
        mm[TABLE + STRIDE * k + 7] &= 0xDF
    n = mm[COUNT]
    mm[SWEEP] = mm[LEFT] = n
    acc = 0xB9                                       # $A3D2
    out, slot, guard = [], TABLE, 0
    while True:
        guard += 1
        if guard > 20000:
            raise RuntimeError('the scheduler did not converge')
        acc = (acc + 1) & 0xFF                       # $A3D7 LD A,1 / CALL $A430
        b, c = acc, (acc + 0x1E) & 0xFF
        # $A42B: skipped iff (A < C) and (A >= B), plain 8-bit compares -- so a
        # window whose top has WRAPPED is empty and skips nothing.
        ys = [mm[slot + 6], (mm[slot + 6] + 0x10) & 0xFF,
              mm[slot + 2], (mm[slot + 2] + 0x10) & 0xFF]
        if not any(b <= y < c for y in ys) and not (mm[slot + 7] & 0x20):
            w, fields, cost = predict_call(mm, slot)
            for a, v in w:
                if a >= 0x4000:
                    mm[a] = v
            for off, v in fields.items():
                mm[slot + off] = v
            out += w
            mm[LEFT] = (mm[LEFT] - 1) & 0xFF
            acc = (acc + cost) & 0xFF
        slot += STRIDE                               # $A405
        acc = (acc + 1) & 0xFF                       # $A40A LD A,1 / CALL $A430
        mm[SWEEP] = (mm[SWEEP] - 1) & 0xFF
        if mm[SWEEP] != 0:
            continue
        slot = TABLE                                 # $A417 rewind and sweep again
        mm[SWEEP] = mm[COUNT]
        if mm[LEFT] == 0:
            break
    mm[ACC] = acc
    return out, mm


# ------------------------------------------------------------------- harness
def call_master(h, slot, toggle=None):
    m = h.memobj.m
    if toggle is not None:
        m[TOGGLE] = toggle
    m[LEFT] = 5
    h.memobj.watch(0x4000, 0x5B00)
    h.call(MASTER, regs={'IY': slot})
    log = [(a, v) for _p, a, v in h.memobj.log]
    h.memobj.unwatch()
    return log


def natural_pass(h):
    """advance to the NEXT in-ISR $A3AD and bracket it by control flow"""
    h.run_until((PASS,), limit=10 ** 7, stride=1)
    before = bytes(h.memobj.m)
    h.memobj.watch(0x4000, 0x5B00)
    h.run_until((PASS_RET,), limit=10 ** 7, stride=1)
    h.step(1)
    log = [(a, v) for _p, a, v in h.memobj.log]
    h.memobj.unwatch()
    return before, log


# ------------------------------------------------------------------- capture
CALL_CASES = [
    #  cx   cy    x    y  flags tog pstate  label
    (80, 96, 88, 96, 0xC0, 0, 0, 'erase_aligned_draw_aligned'),
    (80, 96, 82, 96, 0xC0, 0, 0, 'erase_aligned_draw_shifted'),
    (82, 96, 88, 96, 0xC0, 0, 0, 'erase_shifted_draw_aligned'),
    (82, 96, 86, 98, 0xC0, 0, 0, 'erase_shifted_draw_shifted'),
    (84, 99, 86, 103, 0xC0, 0, 0, 'both_shifted_odd_rows'),
    (80, 96, 88, 96, 0x80, 0, 0, 'no_cache_draw_only'),
    (80, 96, 88, 96, 0x40, 0, 0, 'inactive_bit7_clear'),
    (80, 96, 88, 96, 0xC8, 0, 0, 'bit3_set_skipped'),
    (80, 0xC8, 88, 96, 0xC0, 0, 0, 'cached_Y_ge_C0_no_erase'),
    (240, 120, 248, 120, 0xC0, 0, 0, 'page_wrap_right_edge'),
    (250, 56, 252, 56, 0xC0, 0, 0, 'page_wrap_shifted'),
    (88, 16, 88, 8, 0xC0, 0, 0, 'sentinel_rows_partial'),
    (88, 8, 88, 0, 0xC0, 0, 0, 'sentinel_rows_all'),
    (88, 176, 88, 184, 0xC0, 0, 0, 'bottom_edge'),
    (80, 96, 88, 96, 0xC0, 0, 0x08, 'player_flash_toggle0_skips_draw'),
    (80, 96, 88, 96, 0xC0, 1, 0x08, 'player_flash_toggle1_draws'),
    (80, 96, 88, 96, 0xC0, 0, 0x00, 'player_no_flash_bit'),
    # an ODD cached X on the SHIFTED erase path: X & 6 = 2 but X & 7 = 3, so the
    # two mask tables' INDEX rules disagree.  Without this the erase reading
    # $BFF8[X&7] instead of $AA4F[X&6] is indistinguishable.
    (83, 96, 88, 96, 0xC0, 0, 0, 'odd_cached_x_shifted_erase'),
    (85, 99, 91, 101, 0xC0, 0, 0, 'odd_cached_x_odd_rows'),
]
# the same, driven from a NON-player slot: the flash must NOT apply there
CALL_CASES_SLOT2 = [
    (80, 96, 88, 96, 0xC0, 0, 0x08, 'nonplayer_slot_flash_bit_ignored'),
    (80, 96, 88, 96, 0xC0, 1, 0x08, 'nonplayer_slot_flash_bit_toggle1'),
]
SPRITES = (0xC100, 0xD7C0, 0xCD80, 0xC260)


# Entity tables built to EXERCISE the scheduler.  The first window of a pass is
# [$BA, $D8) = [186, 216), so an entity whose Y or Y+$10 lands there is hidden on
# its first visit and the list must be swept again.  Screen Y runs 0..191, so
# Y in 170..191 reaches it -- and round 1's floor is at Y=168, so this is not a
# contrived corner.  MEASURED: the eight NATURAL passes hide nothing and sweep
# once, which is why ten scheduler mutations survived the first battery.
def ent(slot, spr, cx, cy, x, y, flags=0xC0):
    return (slot, spr, cx, cy, x, y, flags)


PASS_SCENES = [
    ('sched_hidden_low_rows', 5, 0, (0, 0), [
        ent(0, 0xC100, 64, 176, 64, 176), ent(1, 0xC100, 96, 180, 96, 180),
        ent(2, 0xC100, 128, 184, 128, 184), ent(3, 0xC100, 160, 40, 160, 40)]),
    ('sched_cached_hidden_only', 5, 0, (0, 0), [
        ent(0, 0xC100, 64, 178, 64, 40), ent(2, 0xC100, 96, 48, 96, 48)]),
    ('sched_mixed', 9, 0, (0, 0), [
        ent(0, 0xC100, 60, 172, 62, 174), ent(1, 0xC100, 90, 60, 92, 62),
        ent(3, 0xC100, 120, 182, 122, 184), ent(5, 0xC100, 150, 90, 152, 92),
        ent(7, 0xC100, 180, 176, 182, 178)]),
    ('sched_player_flash_toggle0', 5, 0, (0x08, 0), [
        ent(0, 0xC100, 64, 96, 66, 98), ent(2, 0xC100, 96, 60, 98, 62)]),
    ('sched_player_flash_toggle1', 5, 1, (0x08, 0), [
        ent(0, 0xC100, 64, 96, 66, 98), ent(2, 0xC100, 96, 60, 98, 62)]),
    ('sched_p2_flash', 5, 0, (0, 0x08), [
        ent(0, 0xC100, 64, 96, 66, 98), ent(1, 0xC100, 96, 60, 98, 62)]),
    ('sched_nine_slots', 9, 0, (0, 0), [
        ent(k, 0xC100, 40 + 20 * k, 40 + 8 * k, 42 + 20 * k, 42 + 8 * k) for k in range(9)]),
    ('sched_all_hidden_first_visit', 5, 0, (0, 0), [
        ent(0, 0xC100, 40, 176, 40, 176), ent(1, 0xC100, 70, 177, 70, 177),
        ent(2, 0xC100, 100, 178, 100, 178), ent(3, 0xC100, 130, 179, 130, 179),
        ent(4, 0xC100, 160, 180, 160, 180)]),
]


def box_of(m, x, y, ncol=4):
    return sorted({col_addr(row_base(m, (y + r) & 0xFF, x), c)
                   for r in range(16) for c in range(ncol)})


def capture():
    h, m = new()
    cases = []
    for (cx, cy, x, y, fl, tog, ps, label), slot in (
            [(c, TABLE) for c in CALL_CASES] +
            [(c, TABLE + 2 * STRIDE) for c in CALL_CASES_SLOT2]):
        for spr in (0xC100,):
            m[slot + 0], m[slot + 1] = spr & 0xFF, spr >> 8
            m[slot + 2], m[slot + 3] = cy & 0xFF, cx & 0xFF
            m[slot + 5], m[slot + 6] = x & 0xFF, y & 0xFF
            m[slot + 7] = fl
            m[slot + PLAYER_STATE] = ps
            m[TOGGLE] = tog
            m[ACC] = 0                               # a known beam-accumulator seed
            box = sorted(set(box_of(m, cx, cy) + box_of(m, x, y)))
            clean = {a: m[a] for a in box}
            for a in box:                            # DIRTY, so shadow != display
                if a >= 0x4000:
                    m[a] = ((a * 5) ^ 0xA5) & 0xFF
            snap = bytes(m)
            writes = call_master(h, slot)
            cases.append({
                'label': label, 'cx': cx, 'cy': cy, 'x': x, 'y': y, 'flags': fl,
                'toggle': tog, 'pstate': ps, 'spr': spr, 'slot': slot,
                'writes': [{'a': a, 'v': v} for a, v in writes],
                'box': box,
                'before': {str(a): snap[a] for a in box},
                'shadow': {str(a): snap[(a + SHADOW) & 0xFFFF] for a in box},
                'after': {str(a): m[a] for a in box},
                'fields_before': [snap[slot + o] for o in range(10)],
                'fields_after': [m[slot + o] for o in range(10)],
                'acc_after': m[ACC],                 # what this visit costs the beam
            })
            for a, v in clean.items():
                if a >= 0x4000:
                    m[a] = v

    # the natural in-ISR scheduler pass, several frames running
    h2, m2 = new()
    passes = []
    for f in range(8):
        before, log = natural_pass(h2)
        touched = sorted({a for a, _v in log})
        passes.append({
            'label': f'natural_{f}', 'synthetic': 0,
            'frame': f,
            'table_before': [before[TABLE + i] for i in range(SLOTS * STRIDE)],
            'table_after': [m2[TABLE + i] for i in range(SLOTS * STRIDE)],
            'toggle_before': before[TOGGLE], 'count': before[COUNT],
            'pstate': [before[0xFDDA], before[0xFDE4]],
            'writes': [{'a': a, 'v': v} for a, v in log],
            'acc_after': m2[ACC], 'left_after': m2[LEFT], 'sweep_after': m2[SWEEP],
            'before': {str(a): before[a] for a in touched},
            'shadow': {str(a): before[(a + SHADOW) & 0xFFFF] for a in touched},
        })

    # ...and the SYNTHETIC scenes that actually exercise the scheduler
    h3, m3 = new()
    for (label, count, tog, pstate, ents) in PASS_SCENES:
        for k in range(SLOTS):                       # a clean table
            for o in range(STRIDE):
                m3[TABLE + STRIDE * k + o] = 0
        for (slot, spr, cx, cy, x, y, flags) in ents:
            b = TABLE + STRIDE * slot
            m3[b + 0], m3[b + 1] = spr & 0xFF, spr >> 8
            m3[b + 2], m3[b + 3] = cy & 0xFF, cx & 0xFF
            m3[b + 5], m3[b + 6] = x & 0xFF, y & 0xFF
            m3[b + 7] = flags
        m3[COUNT] = count
        m3[TOGGLE] = tog
        m3[0xFDDA], m3[0xFDE4] = pstate
        # bit5 set on the +7 bytes of slots 9, 10 and 11 -- $FDE1/$FDEB/$FDF5,
        # which are inside the PLAYERS' parameter blocks, not spare table space.
        # $A3C0 clears bit5 on NINE slots only, so these must survive; a pass
        # that cleared twelve would corrupt player state.  (An earlier version
        # of this seeded $FDD9/$FDE3/$FDED, which are slot 8 +9 and slots 9/10
        # +3 -- not the bytes the loop touches -- and the mutation survived.)
        for k in (9, 10, 11):
            m3[TABLE + STRIDE * k + 7] |= 0x20
        box = set()
        for (slot, spr, cx, cy, x, y, flags) in ents:
            box |= set(box_of(m3, cx, cy)) | set(box_of(m3, x, y))
        box = sorted(box)
        for a in box:
            if a >= 0x4000:
                m3[a] = ((a * 5) ^ 0xA5) & 0xFF
        before = bytes(m3)
        h3.memobj.watch(0x4000, 0x5B00)
        h3.call(PASS)
        log = [(a, v) for _p, a, v in h3.memobj.log]
        h3.memobj.unwatch()
        touched = sorted({a for a, _v in log} | set(box))
        passes.append({
            'label': label, 'synthetic': 1, 'frame': -1,
            'table_before': [before[TABLE + i] for i in range(SLOTS * STRIDE)],
            'table_after': [m3[TABLE + i] for i in range(SLOTS * STRIDE)],
            'toggle_before': before[TOGGLE], 'count': before[COUNT],
            'pstate': [before[0xFDDA], before[0xFDE4]],
            'writes': [{'a': a, 'v': v} for a, v in log],
            'acc_after': m3[ACC], 'left_after': m3[LEFT], 'sweep_after': m3[SWEEP],
            'before': {str(a): before[a] for a in touched},
            'shadow': {str(a): before[(a + SHADOW) & 0xFFFF] for a in touched},
        })
        for a in box:                                # restore the display
            if a >= 0x4000:
                m3[a] = before[a]

    used = sorted({m2[TABLE + STRIDE * k] | (m2[TABLE + STRIDE * k + 1] << 8)
                   for k in range(SLOTS)} | set(SPRITES))
    fx = {
        'note': __doc__.strip().split('\n\n')[1].replace('\n', ' '),
        'state': STATE,
        'rowtable': [m[ROWTAB + 2 * i] | (m[ROWTAB + 2 * i + 1] << 8) for i in range(32)],
        'mask_table': [m[ENT_MASK + i] for i in range(8)],
        'mask_addr': ENT_MASK,
        'acc_cost': {'erase_aligned': ACC_ERASE[False], 'erase_shifted': ACC_ERASE[True],
                     'draw_aligned': ACC_DRAW[False], 'draw_shifted': ACC_DRAW[True]},
        'sprites': {f'{a:04X}': base64.b64encode(bytes(m[a:a + 352])).decode()
                    for a in used if a >= 0x4000},
        'calls': cases,
        'passes': passes,
    }
    json.dump(fx, open(FIXTURE, 'w'), indent=1)
    print(f'wrote {FIXTURE}: {len(cases)} $A447 calls, {len(passes)} $A3AD passes, '
          f'{sum(len(c["writes"]) for c in cases) + sum(len(p["writes"]) for p in passes)} writes')
    carry()                      # M7.49: one command makes the whole fixture, carry_calls included


# --------------------------------------------------------------- carry (M7.49)
# $A447's OWN $A430 calls ($A485 +7 / $A56A +20 in the erase, $A616 +8 / $A708 +11
# in the draw) pay `RET nc` NOT taken when the add carries: +4 T.  No natural pass
# witnesses it where the T is exact -- every $A447-site carry in the isrcost
# fixture falls in a CONTENDED pass, where the directional gate cannot see a
# shortfall -- so it is measured here directly: $A447 CALLED with $A431 seeded so
# that the sum lands exactly on $100 at the erase's add or at the draw's (and, as
# the edge, exactly on $FF: no carry), on the UNCONTENDED harness, because the
# engine models the routine and not the ULA.  Every $A430 entry is logged as the
# machine made it -- (A, $A431 before) at PC $A430 -- so which add carried is
# the machine's record, not the seed arithmetic's.
CARRY_CASES = [
    (80, 96, 88, 96, 0xC0, 0, 0, 'erase_aligned_draw_aligned'),
    (80, 96, 82, 96, 0xC0, 0, 0, 'erase_aligned_draw_shifted'),
    (82, 96, 88, 96, 0xC0, 0, 0, 'erase_shifted_draw_aligned'),
    (82, 96, 86, 98, 0xC0, 0, 0, 'erase_shifted_draw_shifted'),
    (84, 99, 86, 103, 0xC0, 1, 0, 'both_shifted_odd_rows_toggle1'),
    (80, 96, 88, 96, 0x80, 0, 0, 'no_cache_draw_only'),
    (80, 0xC8, 88, 96, 0xC0, 0, 0, 'cached_Y_ge_C0_no_erase'),
    (82, 96, 88, 96, 0xC0, 0, 0x08, 'player_flash_toggle0_erase_only'),
]
BEAM_ADD = 0xA430


def call_logged(h, slot):
    """h.call($A447) with a PC breakpoint on $A430: returns (T, [(A, $A431 before)], exit index)"""
    from harness import A as RA, SP, PC, T, U
    r, m = h.sim.registers, h.memobj.m
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp], m[sp + 1] = s & 0xFF, s >> 8
    r[SP] = sp
    r[U.REGISTERS['IYl']], r[U.REGISTERS['IYh']] = slot & 0xFF, slot >> 8
    r[PC] = MASTER
    t0, adds = r[T], []
    while True:
        why, _n = h.run_until((BEAM_ADD,) + h.SENTINELS, limit=2_000_000, interrupts=False)
        if why != 'target':
            raise RuntimeError('$A447 did not return')
        if r[PC] != BEAM_ADD:
            return r[T] - t0, adds, h.SENTINELS.index(r[PC])
        adds.append((r[RA], m[ACC]))
        h.step(1, interrupts=False)                  # past the ADD, on to the sentinel


def carry():
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(STATE))
    m = h.memobj.m
    base = h.save_state()
    out = []
    for (cx, cy, x, y, fl, tog, ps, label) in CARRY_CASES:
        e = ((ACC_ERASE[(cx & 6) != 0]) if ((fl & 0x40) and cy < 0xC0) else 0)
        d = 0 if ((tog & 1) == 0 and (ps & 0x08)) else ACC_DRAW[(x & 6) != 0]
        seeds = [('none', 0)]
        if e:
            seeds.append(('erase_carries', 0x100 - e))
        if d:
            seeds.append(('draw_carries', 0x100 - e - d))
        seeds.append(('sum_exactly_FF', (0xFF - e - d) & 0xFF))
        for tag, seed in seeds:
            h.load_state(base)
            slot, spr = TABLE, 0xC100
            m[slot + 0], m[slot + 1] = spr & 0xFF, spr >> 8
            m[slot + 2], m[slot + 3] = cy & 0xFF, cx & 0xFF
            m[slot + 5], m[slot + 6] = x & 0xFF, y & 0xFF
            m[slot + 7] = fl
            m[slot + PLAYER_STATE] = ps
            m[TOGGLE] = tog
            m[LEFT] = 5
            m[ACC] = seed
            t, adds, ex = call_logged(h, slot)
            if ex != 0:
                raise RuntimeError(f'{label}/{tag}: $A447 abandoned {ex} frames')
            out.append({'label': label, 'tag': tag, 'cx': cx, 'cy': cy, 'x': x, 'y': y,
                        'flags': fl, 'toggle': tog, 'pstate': ps, 'slot': slot, 'spr': spr,
                        'seed': seed, 't': t, 'acc_after': m[ACC],
                        'adds': [list(a) for a in adds],
                        'carries': [a for a, b in adds if a + b > 0xFF]})
    by = {}
    for r in out:
        by.setdefault(r['label'], {})[r['tag']] = r
    for r in out:
        dt = r['t'] - by[r['label']]['none']['t']
        print(f"  {r['label']:32s} {r['tag']:15s} seed ${r['seed']:02X}  T {r['t']:5d}  "
              f"dT {dt:+d}  adds {r['adds']}  carried {r['carries']}  $A431 ${r['acc_after']:02X}")
        if dt != 4 * len(r['carries']):
            raise RuntimeError(f"{r['label']}/{r['tag']}: dT {dt} for {len(r['carries'])} carries")
    fx = json.load(open(FIXTURE))
    fx['carry_calls'] = out
    fx['carry_note'] = ('M7.49: $A447 CALLED directly on the UNCONTENDED harness (round1_48, '
                        'interrupts off), $A431 seeded so that the erase add or the draw add '
                        'sums exactly $100, or the whole call exactly $FF; `adds` is every $A430 '
                        'entry as (A, $A431 before) at the breakpoint, `t` the call to its RET.')
    json.dump(fx, open(FIXTURE, 'w'), indent=1)
    sites = sorted({a for r in out for a in r['carries']})
    print(f'merged {len(out)} carry calls into {FIXTURE}; sites that carried: {sites}')

# -------------------------------------------------------------------- verify
def verify(sweep=False):
    h, m = new()
    fx = json.load(open(FIXTURE))
    bad = 0
    print(f'=== {len(fx["calls"])} $A447 call cases ===')
    for c in fx['calls']:
        slot = c['slot']
        for i, v in enumerate(c['fields_before']):
            m[slot + i] = v
        m[slot + PLAYER_STATE] = c['pstate']
        m[TOGGLE] = c['toggle']
        clean = {int(a): m[int(a)] for a in c['before']}
        for a, v in c['before'].items():
            if int(a) >= 0x4000:
                m[int(a)] = v
        snap = bytes(m)
        got = call_master(h, slot)
        want = [(w['a'], w['v']) for w in c['writes']]
        pred, fields, cost = predict_call(snap, slot, c['toggle'])
        if 'acc_after' in c and cost != c['acc_after']:
            print(f'       ACC {c["label"]}: machine {c["acc_after"]}, model {cost}')
        pred = [(a, v) for a, v in pred if a >= 0x4000]
        fok = all(m[slot + o] == v for o, v in fields.items())
        ok = got == want and got == pred and fok
        bad += not ok
        print(f'  {"ok  " if ok else "FAIL"} {c["label"]:34s} writes={len(got):3d}'
              f'{"" if fok else "  FIELDS"}')
        if not ok:
            for i in range(max(len(got), len(pred))):
                if (got[i] if i < len(got) else None) != (pred[i] if i < len(pred) else None):
                    print(f'       [{i}] machine {got[i] if i<len(got) else None} '
                          f'model {pred[i] if i<len(pred) else None}')
                    break
        for a, v in clean.items():
            if a >= 0x4000:
                m[a] = v
    print(f'-> {len(fx["calls"]) - bad}/{len(fx["calls"])} call cases match')

    print(f'\n=== {len(fx["passes"])} $A3AD scheduler passes ===')
    pbad = 0
    for p in fx['passes']:
        mm = bytearray(m)
        for i, v in enumerate(p['table_before']):
            mm[TABLE + i] = v
        mm[TOGGLE] = p['toggle_before']
        mm[COUNT] = p['count']
        mm[0xFDDA], mm[0xFDE4] = p['pstate']
        for a, v in p['before'].items():
            if int(a) >= 0x4000:
                mm[int(a)] = v
        for a, v in p['shadow'].items():
            mm[(int(a) + SHADOW) & 0xFFFF] = v
        pred, after = predict_pass(mm)
        if 'acc_after' in p and after[ACC] != p['acc_after']:
            print(f'       ACC {p.get("label")}: machine {p["acc_after"]}, model {after[ACC]}')
        pred = [(a, v) for a, v in pred if a >= 0x4000]
        want = [(w['a'], w['v']) for w in p['writes']]
        tok = all(after[TABLE + i] == v for i, v in enumerate(p['table_after']))
        ok = pred == want and tok
        pbad += not ok
        print(f'  {"ok  " if ok else "FAIL"} {p.get("label", p["frame"]):28s} '
              f'writes={len(want):4d}{"" if tok else "  TABLE"}')
        if not ok:
            for i in range(max(len(want), len(pred))):
                if (want[i] if i < len(want) else None) != (pred[i] if i < len(pred) else None):
                    print(f'       [{i}] machine {want[i] if i<len(want) else None} '
                          f'model {pred[i] if i<len(pred) else None}')
                    break
            if not tok:
                for i, v in enumerate(p['table_after']):
                    if after[TABLE + i] != v:
                        print(f'       table[{i}] (slot {i//10} +{i%10}): '
                              f'machine {v} model {after[TABLE + i]}')
                        break
    print(f'-> {len(fx["passes"]) - pbad}/{len(fx["passes"])} scheduler passes match')
    bad += pbad

    if sweep:
        n = f = 0
        slot = TABLE
        for x in range(80, 92):
            for y in range(92, 104):
                for fl in (0xC0, 0x80):
                    m[slot + 0], m[slot + 1] = 0x00, 0xC1
                    m[slot + 2], m[slot + 3] = (y - 2) & 0xFF, (x - 4) & 0xFF
                    m[slot + 5], m[slot + 6] = x, y
                    m[slot + 7] = fl
                    m[slot + PLAYER_STATE] = 0
                    m[TOGGLE] = 0
                    box = sorted(set(box_of(m, x - 4, y - 2) + box_of(m, x, y)))
                    clean = {a: m[a] for a in box}
                    for a in box:
                        if a >= 0x4000:
                            m[a] = ((a * 5) ^ 0xA5) & 0xFF
                    snap = bytes(m)
                    got = call_master(h, slot)
                    pred, _fields, _c = predict_call(snap, slot, 0)
                    n += 1
                    if got != [(a, v) for a, v in pred if a >= 0x4000]:
                        f += 1
                        if f <= 3:
                            print(f'  SWEEP FAIL x={x} y={y} flags=${fl:02X}')
                    for a, v in clean.items():
                        if a >= 0x4000:
                            m[a] = v
        print(f'-> sweep {n - f}/{n} match')
        bad += f
    return bad


def main():
    v = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if v == 'capture':
        capture()
    elif v == 'carry':
        carry()
    else:
        sys.exit(1 if verify('--sweep' in sys.argv) else 0)


if __name__ == '__main__':
    main()
