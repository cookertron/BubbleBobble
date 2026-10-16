"""M7.7-H11 -- THE SCROLL-IN, GATED AS AN ANIMATION.

*** H2 PROVED THE END STATE TESTS NOTHING. ***  $7F4E CALL $8216 repaints the
playfield from the shadow three instructions after the scroll loop exits, so an
end-state screen gate passes a port with NO SCROLL AT ALL, a backwards scroll, a
wrong-speed scroll or a pixel-smooth one.  Everything here is either a MID-SCROLL
comparison or a per-routine differential in a world built for the purpose.

  $7F30  LD A,($8609) / DEC A / JR z -- ROUND 1 SKIPS THE WHOLE SCROLL, so this
         increment must drive a round >= 2.
  $7F39  CALL $8404 -- and $8404/$8407/$840A is a CASCADE THAT USES RETURN
         ADDRESSES AS A LOOP: $8404 CALLs $8407, whose return address is $840A;
         $8407 CALLs $840A, whose return address is also $840A.  Entering at
         $8404 therefore runs $840A FOUR TIMES.  Four pre-roll steps, then 22
         content steps = 26 steps over a 176-pixel playfield.
  $840A  a DISPLAY-FILE SELF-COPY: rows 2..22 := rows 3..23, bitmap AND
         attributes, 21 table pairs from $FD04.
  $8447  pushes a new row 23 from the SHADOW, and its ATTRIBUTE SOURCE IS THE
         COLOUR SHADOW -- not the attribute plane.
  $9603  *** SELF-WRITTEN CODE. ***  $7F1B lays 32 unrolled LDIs (ED A0) and a
         RET at $9603 immediately before the scroll.  Those 64 bytes, $9603..
         $9642, ARE I1'S ITEM BLOCK -- the same sixty-four bytes are executable
         code during the build and live item data during play, and the chain's
         RET at $9643 is the byte just past the block.  It IGNORES BC because
         nothing tests BC: 32 LDIs each decrement it and none branch on it.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT THE FINISHED SCREEN IS EVIDENCE.  It is not (H2).  The filmstrip
    snapshots every step boundary by PC.

  * THAT ATTRIBUTES MOVING WITH THE BITMAP AND ATTRIBUTES RE-DERIVED PER STEP
    ARE DISTINGUISHABLE IN THE CONTENT STEPS.  They are not -- the scroll unit is
    a whole character row, so both models agree for all 22.  THE FOUR-STEP
    PRE-ROLL SEPARATES THEM, because there the attribute rows carry the OLD
    round's colours up and no shadow row exists to re-derive from.

  * THAT `CALL $9603` COPIES BC BYTES.  It copies 32 whatever BC holds, so BC is
    driven at $0000, $001F, $0020 and $1234 and the RESIDUE is asserted.

  * THAT $FD44 IS A SECOND TABLE.  $FD44[k] == $FD04[k] + $A000 on all 22
    entries, so "the shadow is display+$A000" and "there is a second table"
    cannot be told apart -- ONE ENTRY is poked away from its partner.

  * THAT THE TWO OUT-OF-RANGE TABLE ENTRIES ARE REACHED.  $840A's 22nd pair
    ($FD30 = $0000, ROM) is unreachable because $840E loads $15 = 21, and $8447
    with k >= 22 ($FD70) is unreachable because $8604 runs $16..1.  ASSERTED AS
    NEGATIVES: a port writing `for i in range(22)` in $840A and a port adding a
    bounds check to $8447 are departing in OPPOSITE directions.

Usage:  python tools/scroll.py capture
        python tools/scroll.py verify
"""
import sys, json, hashlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

DRIVER = 0x7F30
CHAIN_AT, CHAIN_N = 0x9603, 0x20      # 32 LDIs, then a RET at $9643
STEP = 0x840A
PUSH = 0x8447
PREROLL = 0x8404
COPY = 0x9603
FILLER = 0x81E6
COUNT = 0x8604
ROW_TAB, SHADOW_TAB = 0xFD04, 0xFD44
BUILD = 0x97F8
ROUND = 0x8609
SCREEN, ATTRS = 0x4000, 0x5800
SHADOW, COLOUR = 0xE000, 0xF800
BOUNDARIES = (0x7F41, 0x7F44, 0x7F47)
FIXTURE = 'build/scroll_fixture.json'


def disp(r, p, c=0):
    """Display address of char row r, pixel row p, column c."""
    return SCREEN + ((r >> 3) << 11) + (p << 8) + ((r & 7) << 5) + c


def lay_chain(m):
    """$7F1B's 32 unrolled LDIs and the RET -- laid by hand, because the whole
       point is that this code does not exist until the build writes it."""
    a = CHAIN_AT
    for _ in range(CHAIN_N):
        m[a] = 0xED
        m[a + 1] = 0xA0
        a += 2
    m[a] = 0xC9
    return a


def synth(m):
    """THE SYNTHETIC WORLD, which is what makes this gate able to fail.  All 24
       display rows, 24 attribute rows, 24 shadow rows and 24 colour-shadow rows
       PAIRWISE DISTINCT, so any row landing anywhere names both ends."""
    for r in range(24):
        for p in range(8):
            v = (r << 3) | p
            for c in range(32):
                m[disp(r, p, c)] = v
                m[disp(r, p, c) + 0xA000] = v ^ 0xFF
        for c in range(32):
            m[ATTRS + r * 32 + c] = 0x40 + r
            m[COLOUR + r * 32 + c] = 0x80 + r


def snap(m):
    return ([m[SCREEN + i] for i in range(0x1800)],
            [m[ATTRS + i] for i in range(0x300)])


# ------------------------------------------------- (a) $840A in the synth world
def step_rows(h, m):
    synth(m)
    lay_chain(m)
    before_b, before_a = snap(m)
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, STEP)
    t0 = h.sim.registers[25]
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    t = h.sim.registers[25] - t0
    log = list(h.memobj.log)
    h.memobj.unwatch()
    after_b, after_a = snap(m)

    rows_written = sorted({(a - SCREEN) and 0 or 0 for (_p, a, _v) in log if False})
    bitmap = [a for (_p, a, _v) in log if SCREEN <= a < ATTRS]
    attr = [a for (_p, a, _v) in log if ATTRS <= a < 0x5B00]
    # SEPARATE THE STACK FROM THE SHADOW.  The plan's claim is that $840A writes
    # NO shadow and NO colour shadow -- but $841F PUSH HL / PUSH DE and the CALLs
    # write plenty, all of it stack.  Lumping them together makes "1050 outside"
    # look like a violation when the real answer is zero.
    shadow = [a for (_p, a, _v) in log if SHADOW <= a < 0x10000]
    other = [a for (_p, a, _v) in log
             if not (SCREEN <= a < 0x5B00) and not (SHADOW <= a < 0x10000)]

    def rowof(a):
        o = a - SCREEN
        return ((o >> 11) << 3) | ((o & 0x7FF) >> 5 & 7)

    moved = all(after_b[disp(r, p, c) - SCREEN] == before_b[disp(r + 1, p, c) - SCREEN]
                for r in range(2, 23) for p in range(8) for c in (0, 17, 31))
    moved_a = all(after_a[r * 32 + c] == before_a[(r + 1) * 32 + c]
                  for r in range(2, 23) for c in (0, 17, 31))
    untouched = all(after_b[disp(r, p, c) - SCREEN] == before_b[disp(r, p, c) - SCREEN]
                    for r in (0, 1, 23) for p in range(8) for c in (0, 17, 31)) and \
                all(after_a[r * 32 + c] == before_a[r * 32 + c]
                    for r in (0, 1, 23) for c in (0, 17, 31))
    return {'writes': len(log), 'bitmap': len(bitmap), 'attrs': len(attr),
            'shadow_or_colour': len(shadow), 'stack_or_other': len(other), 't': t,
            'bitmap_rows': sorted({rowof(a) for a in bitmap}),
            'attr_rows': sorted({(a - ATTRS) >> 5 for a in attr}),
            'rows_moved_up': moved, 'attr_rows_moved_up': moved_a,
            'rows_0_1_23_intact': untouched}


# --------------------------------------------- (b) $8447 over every k it reaches
def push_rows(h, m):
    out = []
    for k in range(0, 22):
        synth(m)
        lay_chain(m)
        m[COUNT] = 0x16 - k
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, PUSH)
        h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        src = 2 + k
        bit_ok = all(m[disp(23, p, c)] == ((src << 3) | p) ^ 0xFF
                     for p in range(8) for c in (0, 17, 31))
        attr_ok = all(m[ATTRS + 23 * 32 + c] == 0x80 + src for c in (0, 17, 31))
        out.append({'k': k, 'count': 0x16 - k, 'src_row': src,
                    'writes': len(log),
                    'bitmap_from_shadow': bit_ok,
                    'attr_from_COLOUR_shadow': attr_ok,
                    'shadow_or_colour': len([a for (_p, a, _v) in log
                                             if SHADOW <= a < 0x10000]),
                    'screen': len([a for (_p, a, _v) in log if SCREEN <= a < 0x5B00])})
    return out


# ----------------------------------------------- (c) the copier that ignores BC
def copy_rows(h, m):
    out = []
    for bc in (0x0000, 0x001F, 0x0020, 0x1234):
        lay_chain(m)
        for i in range(64):
            m[0x7100 + i] = 0xA5
            m[0x7200 + i] = 0x5A
        r = h.sim.registers
        sp = RC.arm(h, COPY)
        r[2], r[3] = bc >> 8, bc & 0xFF          # B, C
        r[6], r[7] = 0x71, 0x00                  # HL = $7100 (source)
        r[4], r[5] = 0x72, 0x00                  # DE = $7200 (dest)
        h.memobj.watch(0x7000, 0x7400)
        h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        out.append({'bc_in': bc, 'writes': len(log),
                    'bc_out': (r[2] << 8) | r[3],
                    'expected_out': (bc - 32) & 0xFFFF,
                    'copied': sum(1 for i in range(64) if m[0x7200 + i] == 0xA5)})
    return out


# ------------------------------------------- (d) the two tables, and the poke
def table_rows(h, m):
    same = all((m[ROW_TAB + 2 * k] | (m[ROW_TAB + 2 * k + 1] << 8)) + 0xA000 ==
               (m[SHADOW_TAB + 2 * k] | (m[SHADOW_TAB + 2 * k + 1] << 8))
               for k in range(22))
    # POKE ONE ENTRY AWAY FROM ITS PARTNER: if $8447 still lands on the right
    # row, it is using $FD44 and not display+$A000 arithmetic.
    synth(m)
    lay_chain(m)
    m[COUNT] = 0x16
    keep = (m[SHADOW_TAB], m[SHADOW_TAB + 1])
    m[SHADOW_TAB], m[SHADOW_TAB + 1] = 0x00, 0xE4      # point entry 0 at row 18's shadow
    sp = RC.arm(h, PUSH)
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    got = [m[disp(23, p, 0)] for p in range(8)]
    m[SHADOW_TAB], m[SHADOW_TAB + 1] = keep
    return {'shadow_is_display_plus_A000_on_all_22': same,
            'poked_entry_followed': got[0] != ((2 << 3) | 0) ^ 0xFF,
            'row23_after_poke': got}


# ------------------------------------------------ (e) the unreachable entries
def unreachable_rows(h, m):
    return {
        'step_pairs': 21, 'step_operand_at': 0x840E, 'step_operand': m[0x840F],
        'fd30': '%04X' % (m[0xFD30] | (m[0xFD31] << 8)),
        'fd70': '%04X' % (m[0xFD70] | (m[0xFD71] << 8)),
        'count_runs': [0x16, 1],
    }


# ------------------------------------------------ (f) THE MID-SCROLL FILMSTRIP
def filmstrip(h, m):
    """The only evidence that survives H2: a snapshot at EVERY step boundary,
       bracketed by PC and never by division."""
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    RC.seed_round(m)
    RC.suppress_warp(m)
    sp = RC.arm(h, BUILD)
    RC.run(h, sp)                                   # now at round 1
    RC.seed_round(m)
    RC.suppress_warp(m)
    sp = RC.arm(h, BUILD)
    frames, guard = [], 0
    stops = set(BOUNDARIES) | set(h.SENTINELS)
    t0 = h.sim.registers[25]
    while guard < 200:
        guard += 1
        h.run_until(stops, limit=40 * 10 ** 6, stride=1, interrupts=True)
        p = h.regs[PC]
        if p in h.SENTINELS:
            break
        frames.append({'pc': '%04X' % p, 'count': m[COUNT],
                       't': h.sim.registers[25] - t0,
                       'md5': hashlib.md5(bytes(m[SCREEN:0x5B00])).hexdigest(),
                       'row2': [m[disp(2, 0, c)] for c in range(0, 32, 8)],
                       'row23': [m[disp(23, 0, c)] for c in range(0, 32, 8)]})
        h.step(1, interrupts=True)
    return {'round': m[ROUND], 'frames': frames}


def round1_rows(h, m):
    """ROUND 1 SKIPS THE WHOLE SCROLL: $7F34 JR z.  Counted by how many times
       $9603 is ENTERED, which is zero."""
    out = []
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    for _ in range(3):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, BUILD)
        n = 0
        stops = {COPY} | set(h.SENTINELS)
        total = 0
        while total < 40 * 10 ** 6:
            h.run_until(stops, limit=40 * 10 ** 6 - total, stride=1, interrupts=True)
            if h.regs[PC] in h.SENTINELS:
                break
            n += 1
            h.step(1, interrupts=True)
            total += 1
        out.append({'round': m[ROUND], 'copier_entries': n})
    return out


def filler_rows(h, m):
    """$81E6 -- THE SEPARATOR ROW, which had no oracle at all and let four
       mutations through.  *** ITS FILL CALLS $AA4A, NOT $AA49 *** -- one byte
       past the XOR A -- so the 32 attribute bytes take whatever A holds, which
       is ($5AC0), the OLD round's colour.  A port calling the obvious "clear"
       entry point paints the separator band black."""
    synth(m)
    lay_chain(m)
    m[0x5AC0] = 0x3B                                  # a value no other row has
    before = [m[disp(23, p_, 0)] for p_ in range(8)]
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, FILLER)
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    log = [('%04X' % a, v) for (_p, a, v) in h.memobj.log
           if SCREEN <= a < 0x5B00]
    h.memobj.unwatch()
    return {'writes': len(log), 'log': log,
            'attr_value': m[ATTRS + 23 * 32],
            'attr_source': m[0x5AC0],
            'attrs_all_same': len({m[ATTRS + 23 * 32 + c] for c in range(32)}) == 1,
            'row23': [m[disp(23, p_, 0)] for p_ in range(8)],
            'pattern': [m[0x8584 + i] for i in range(8)],
            'before': before}


def driver_rows(h, m):
    """THE WHOLE DRIVER in the synthetic world, bracketed to stop BEFORE $7F4E's
       discard -- so this is the scroll's own output and nothing else.  Gating
       $7F30 by its step count alone let three ordering mutations through: a
       pre-roll that pushes, a counter decremented early, and a push before the
       step all produce 26 steps."""
    synth(m)
    lay_chain(m)
    m[ROUND] = 2
    m[0x5AC0] = 0x3B
    # PIN THE SEPARATOR PATTERN.  $7F30 does not lay it -- $8207 runs earlier, at
    # $7F2A -- so entering here leaves $8584 holding whatever the PREVIOUS
    # measurement left, and the fixture would be non-deterministic.
    for i in range(8):
        m[0x8584 + i] = 0xE0 + i
    h.memobj.watch(0x4000, 0x5B00)
    sp = RC.arm(h, DRIVER)
    # *** BRACKET THE PRE-ROLL SEPARATELY. ***  H2's lesson has an inner
    # analogue: the separator band the filler draws into row 23, and anything a
    # pre-roll push would put there, is SCROLLED OFF THE TOP before the animation
    # ends -- so neither is visible in the final screen, and two mutations
    # survived a gate that only compared it.  $7F3C is after the filler and the
    # four-step cascade and before the counter is set.
    h.run_until((0x7F3C,), limit=40 * 10 ** 6, stride=1, interrupts=False)
    pre = {'stopped_at': '%04X' % h.regs[PC], 'writes': len(h.memobj.log),
           'screen': [m[SCREEN + i] for i in range(0x1B00)],
           'md5': hashlib.md5(bytes(m[SCREEN:0x5B00])).hexdigest()}
    h.run_until((0x7F4E,), limit=40 * 10 ** 6, stride=1, interrupts=False)
    stopped = h.regs[PC]
    log = list(h.memobj.log)
    h.memobj.unwatch()
    return {'preroll': pre, 'pattern': [0xE0 + i for i in range(8)],
            'stopped_at': '%04X' % stopped, 'writes': len(log),
            'count_left': m[COUNT],
            'screen_md5': hashlib.md5(bytes(m[SCREEN:0x5B00])).hexdigest(),
            'row2': [m[disp(2, p_, 0)] for p_ in range(8)],
            'row23': [m[disp(23, p_, 0)] for p_ in range(8)],
            'attr2': m[ATTRS + 2 * 32], 'attr23': m[ATTRS + 23 * 32],
            'screen': [m[SCREEN + i] for i in range(0x1B00)]}


# --------------------------------------------------------------------- main
def capture():
    h, m = RC.new()
    out = {
        'note': ('M7.7-H11 the scroll-in.  H2 proved the END STATE TESTS NOTHING, so '
                 'everything here is mid-scroll or a per-routine differential in a '
                 'synthetic world.  $9603 is SELF-WRITTEN CODE -- 32 unrolled LDIs and '
                 'a RET laid by $7F1B -- occupying the SAME 64 BYTES as I1\'s item '
                 'block, $9603..$9642.  $8404/$8407/$840A is a cascade that uses '
                 'return addresses as a loop and runs $840A FOUR times.'),
        'driver_at': DRIVER, 'step_at': STEP, 'push_at': PUSH, 'preroll_at': PREROLL,
        'copy_at': COPY, 'chain_at': CHAIN_AT, 'chain_n': CHAIN_N,
        'count_at': COUNT, 'row_tab': ROW_TAB, 'shadow_tab': SHADOW_TAB,
        'filler_at': FILLER, 'filler_pattern_at': 0x8584,
        'boundaries': ['%04X' % b for b in BOUNDARIES],
        'chain_bytes': None,
        'step': step_rows(h, m),
        'push': push_rows(h, m),
        'copy': copy_rows(h, m),
        'filler': filler_rows(h, m),
        'driver': driver_rows(h, m),
        'tables': table_rows(h, m),
        'unreachable': unreachable_rows(h, m),
    }
    lay_chain(m)
    out['chain_bytes'] = [m[CHAIN_AT + i] for i in range(2 * CHAIN_N + 1)]
    out['round1'] = round1_rows(h, m)
    out['film'] = filmstrip(h, m)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    s = f['step']
    print('$840A in the synthetic world: %d writes = %d bitmap + %d attrs, %d into the '
          'SHADOW or COLOUR SHADOW; T = %d' % (s['writes'], s['bitmap'], s['attrs'], s['shadow_or_colour'], s['t']))
    print('   bitmap rows %s' % s['bitmap_rows'])
    print('   attr rows   %s' % s['attr_rows'])
    print('   rows 2..22 := 3..23 (bitmap %s, attrs %s); rows 0/1/23 intact %s'
          % (s['rows_moved_up'], s['attr_rows_moved_up'], s['rows_0_1_23_intact']))
    p = f['push']
    print('$8447 over k = 0..21: bitmap from SHADOW %d/22, attrs from COLOUR SHADOW %d/22, '
          'screen writes %s, shadow writes %d'
          % (sum(1 for r in p if r['bitmap_from_shadow']),
             sum(1 for r in p if r['attr_from_COLOUR_shadow']),
             sorted({r['screen'] for r in p}),
             sum(r['shadow_or_colour'] for r in p)))
    print('$9603 ignores BC: %s'
          % [(hex(r['bc_in']), r['writes'], hex(r['bc_out']), hex(r['expected_out']))
             for r in f['copy']])
    fl = f['filler']
    print('$81E6: %d screen writes; attr row 23 = $%02X from ($5AC0) = $%02X, all '
          'same %s; row 23 pattern %s'
          % (fl['writes'], fl['attr_value'], fl['attr_source'],
             fl['attrs_all_same'], ['%02X' % v for v in fl['row23']]))
    dr = f['driver']
    print('DRIVER to $%s: %d screen writes, counter left %d, md5 %s'
          % (dr['stopped_at'], dr['writes'], dr['count_left'],
             dr['screen_md5'][:12]))
    print('   after the FILLER + PRE-ROLL only ($%s): %d writes, md5 %s'
          % (dr['preroll']['stopped_at'], dr['preroll']['writes'],
             dr['preroll']['md5'][:12]))
    print('tables: %s' % f['tables'])
    print('unreachable: %s' % f['unreachable'])
    print('round 1 copier entries: %s' % [(r['round'], r['copier_entries'])
                                          for r in f['round1']])
    fm = f['film']
    print('FILMSTRIP round %d: %d step boundaries, %d distinct screens'
          % (fm['round'], len(fm['frames']),
             len({x['md5'] for x in fm['frames']})))
    print('   first 6: %s' % [(x['pc'], x['count']) for x in fm['frames'][:6]])


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
