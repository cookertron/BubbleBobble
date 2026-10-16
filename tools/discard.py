"""M7.7-H2 -- THE DISCARD: proving the scroll-in is an ANIMATION, and that an
end-state screen gate CANNOT FAIL.

    $7F30  LD A,($8609) / DEC A / $7F34 JR z,$7F4E      round 1 skips the scroll
    $7F36  CALL $81E6 ...                               the scroll, rounds 2+
    $7F4E  CALL $8216                                   AND THEN THIS
    $8216  22 rows x 8 x 32 bytes, SHADOW -> DISPLAY    5,632 bitmap writes
    $823C  $F840 -> $5840, $02C0                          704 attribute writes
    $8247  JP $7F80                                     the round-number digits

$8216 REPAINTS THE WHOLE PLAYFIELD FROM THE SHADOW three instructions after the
scroll loop exits.  So whatever the scroll drew is thrown away, and a gate that
compares the screen at the END of a round transition passes a port with:
    * no scroll at all
    * a backwards scroll
    * a wrong-speed scroll
    * the wrong filler tile
    * the wrong attribute source in $8447
    * the wrong number of pre-roll steps
    * a pixel-smooth scroll
THAT IS WHY THIS INCREMENT EXISTS.  It is the cheapest decisive measurement in
the plan and it must come before any scroll geometry, because getting it wrong
does not produce a wrong screen -- it produces a GATE THAT CANNOT FAIL, and then
every later scroll increment is theatre.

THE PROOF IS A PATCH PAIR.  $7F34 is `28 18` (JR z,$7F4E); patched to `18 18`
it is unconditional and NO round ever scrolls.  Chain to round N-1, SAVE THE
WHOLE MACHINE, build once unpatched, restore, build again patched.

AND THE RESULT IS STRONGER THAN "THE SCREEN IS THE SAME".  Measured on all six
rounds: the SHADOW and the COLOUR SHADOW come out BYTE-IDENTICAL -- 0 of 6,144
and 0 of 768 -- so the scroll's output is discarded COMPLETELY from both buffers
the port actually models.  The DISPLAY is identical too on five of the six; on
round 3 it differs in 53 bytes, and those 53 are NOT the scroll.  They are two
settling enemies two pixels apart, because the scrolled build costs 8.2M T
against 4.5M and the hurry timer ticked once more inside it (54 against 53), so
the interrupt handler ran the settler one extra time.  Slots 4 and 5 sit at
Y=56 scrolled and Y=54 not, at X=48 and X=192, which are exactly the columns the
differing bytes fall in.

That is the honest form of the claim, and the reading pass's anchor ("0 differing
bytes of $1B00" on rounds 2, 3, 21 and 45) was true only of the rounds it
happened to sample and silent about why.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * THAT THE DISPLAY STARTED EMPTY.  It is pre-dirtied to $A5 before every build,
    so "repainted" and "never touched" cannot agree.
  * THAT $854D's DIRECTION IS OBSERVABLE AFTER $8216.  It is not, in the purest
    form of TRAPS #37: $8216 has just made display == shadow at every address, so
    copying either way gives the same bytes.  It is driven separately with the
    two sides POKED APART.
  * THAT $7F80 DRAWING NOTHING IS VISIBLE.  On round 81 it returns at once, and
    with $9A0E/$9A0F left at whatever the last round put there, "draws nothing"
    and "draws the old number" are the same picture.  They are SEEDED $AA.
  * THAT $7F80 RUNS ONCE.  It runs THREE times per build and is IDEMPOTENT, so a
    port calling it once after the copy paints the same picture by another route.
    The EXECUTION COUNT is what separates them -- and the FIRST of the three puts
    the digit into the SHADOW, before $8216 copies it out.

Usage:  python tools/discard.py capture
        python tools/discard.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

REPAINT = 0x8216
DIGITS = 0x7F80
D2S = 0x854D
PATCH_AT = 0x7F34
PATCH_FROM, PATCH_TO = (0x28, 0x18), (0x18, 0x18)
DISPLAY, DISPLAY_N = 0x4000, 0x1B00
SHADOW, COLOUR = 0xE000, 0xF800
TENS, UNITS = 0x9A0E, 0x9A0F
DIRTY = 0xA5
ROUNDS = (2, 3, 21, 45, 80, 81)
FIXTURE = 'build/discard_fixture.json'


def run_noint(h, sp):
    """RC.run drives with INTERRUPTS ON, which is right for a whole $97F8 (it
       contains a HALT) and WRONG for an isolated routine: measuring $8216 that
       way logged 6,208 bitmap writes instead of 5,632, because the ISR fired
       mid-call and ran the entity render.  576 of the "repaint" was the
       interrupt handler."""
    h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X' % (r[12], sp + 2))


def dirty(m):
    for a in range(DISPLAY, DISPLAY + DISPLAY_N):
        m[a] = DIRTY


def one_build(h, m, patched):
    """One $97F8 over a display pre-dirtied to $A5."""
    m[PATCH_AT], m[PATCH_AT + 1] = PATCH_TO if patched else PATCH_FROM
    RC.seed_round(m)
    RC.suppress_warp(m)
    dirty(m)
    t0 = h.sim.registers[25]
    sp = RC.arm(h, RC.ADVANCE)
    RC.run(h, sp)
    return {'display': [m[DISPLAY + i] for i in range(DISPLAY_N)],
            'shadow': [m[SHADOW + i] for i in range(0x1800)],
            'colour': [m[COLOUR + i] for i in range(0x300)],
            'ents': [[k, m[0xFD80 + 10 * k + 5], m[0xFD80 + 10 * k + 6],
                      m[0xFD80 + 10 * k + 7]] for k in range(12)],
            'timer': m[0x8DBD] | (m[0x8DBE] << 8),
            't': h.sim.registers[25] - t0,
            'still_dirty': len([1 for i in range(DISPLAY_N)
                                if m[DISPLAY + i] == DIRTY]),
            'round': m[RC.ROUND]}


def patch_pair():
    """THE SAME BUILD, TWICE, FROM THE SAME PRE-STATE.

       MY FIRST VERSION RAN TWO WHOLE CHAINED GAMES, one patched throughout, and
       called it a stronger claim.  It is not -- it is a DIFFERENT and CONFOUNDED
       one: suppressing the scroll changes the timing of every later build, so
       the two games DRIFT, and rounds 3 and 45 came back with 53 and 236 bytes
       differing for reasons that have nothing to do with the discard.  The
       comparison has to isolate ONE build: chain to round N-1, SAVE THE WHOLE
       MACHINE, build once unpatched, restore, build again patched."""
    rows = []
    for target in ROUNDS:
        h, m = RC.new()
        RC.suppress_warp(m)
        m[RC.ROUND] = 0x00
        while m[RC.ROUND] != target - 1:            # reach N-1 HONESTLY (F0)
            RC.seed_round(m)
            RC.suppress_warp(m)
            sp = RC.arm(h, RC.ADVANCE)
            RC.run(h, sp)
            if m[RC.ROUND] == 0:
                raise SystemExit('the chain wrapped before reaching round %d' % target)
        saved = h.save_state()
        a = one_build(h, m, False)
        h.load_state(saved)
        m = h.memobj.m
        b = one_build(h, m, True)
        if a['round'] != target or b['round'] != target:
            raise SystemExit('built round %d/%d, wanted %d'
                             % (a['round'], b['round'], target))
        d = [i for i in range(DISPLAY_N) if a['display'][i] != b['display'][i]]
        ds = [i for i in range(0x1800) if a['shadow'][i] != b['shadow'][i]]
        dc = [i for i in range(0x300) if a['colour'][i] != b['colour'][i]]
        moved = [k for k in range(12)
                 if a['ents'][k][1:] != b['ents'][k][1:]]
        rows.append({'round': target, 'differing': len(d),
                     'shadow_differing': len(ds), 'colour_differing': len(dc),
                     'diff_at': ['%04X' % (DISPLAY + i) for i in d[:16]],
                     'ents_moved': moved,
                     'ents_scrolled': [a['ents'][k] for k in moved],
                     'ents_not': [b['ents'][k] for k in moved],
                     'timer_scrolled': a['timer'], 'timer_not': b['timer'],
                     't_scrolled': a['t'], 't_not': b['t'],
                     'still_dirty_scrolled': a['still_dirty'],
                     'still_dirty_not': b['still_dirty']})
    return rows


def repaint_row(h, m):
    """$8216 alone, over a dirtied display."""
    dirty(m)
    m[TENS], m[UNITS] = 0xAA, 0xAA
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, REPAINT)
    run_noint(h, sp)
    h.memobj.unwatch()
    lo, hi = (RC.SP_PIN[0] - 64) & 0xFFFF, RC.SP_PIN[0]
    w = [(p, a, v) for (p, a, v) in h.memobj.log if not (lo <= a <= hi)]
    return {'bitmap': len([1 for (_p, a, _v) in w if 0x4000 <= a < 0x5800]),
            'attrs': len([1 for (_p, a, _v) in w if 0x5800 <= a < 0x5B00]),
            'shadow': len([1 for (_p, a, _v) in w if SHADOW <= a < COLOUR]),
            'colour': len([1 for (_p, a, _v) in w if COLOUR <= a < 0xFB00]),
            'still_dirty': len([1 for i in range(DISPLAY_N)
                                if m[DISPLAY + i] == DIRTY]),
            'pcs': sorted(set('%04X' % p for (p, _a, _v) in w))}


def digit_rows(h, m):
    """$7F80 with the two digit cells SEEDED, because on round 81 it draws
       NOTHING and "drew nothing" and "drew the old number" are otherwise the
       same picture."""
    rows = []
    for rnd in (1, 2, 9, 10, 11, 45, 79, 80, 81):
        m[RC.ROUND] = rnd
        m[TENS], m[UNITS] = 0xAA, 0xAA
        for i in range(0x40):
            m[0xE040 + i] = 0x5A
        m[0xF840] = 0x5A
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, DIGITS)
        run_noint(h, sp)
        h.memobj.unwatch()
        lo, hi = (RC.SP_PIN[0] - 64) & 0xFFFF, RC.SP_PIN[0]
        w = [(p, a, v) for (p, a, v) in h.memobj.log if not (lo <= a <= hi)]
        rows.append({'round': rnd,
                     'shadow_writes': len([1 for (_p, a, _v) in w
                                           if SHADOW <= a < COLOUR]),
                     'colour_writes': len([1 for (_p, a, _v) in w
                                           if COLOUR <= a < 0xFB00]),
                     'display_writes': len([1 for (_p, a, _v) in w
                                            if 0x4000 <= a < 0x5B00]),
                     # THE ADDRESSES, not just the counts.  The glyph BYTES are
                     # the declared HUD-font departure and cannot be compared,
                     # but WHERE they land and what the colour bytes are can --
                     # and without them the whole draw side is ungated, which is
                     # how eight mutations survived a battery.
                     'shadow_at': sorted(set('%04X' % a for (_p, a, _v) in w
                                             if SHADOW <= a < COLOUR)),
                     'colour_at': sorted(set('%04X' % a for (_p, a, _v) in w
                                             if COLOUR <= a < 0xFB00)),
                     'colour_vals': sorted(set(v for (_p, a, v) in w
                                               if COLOUR <= a < 0xFB00)),
                     'tens': m[TENS], 'units': m[UNITS]})
    return rows


def direction_row(h, m):
    """$854D copies DISPLAY -> SHADOW, which is the opposite of $8216.  It is
       UNOBSERVABLE after $8216 -- that routine has just made the two equal at
       every address -- so the two sides are POKED APART first (TRAPS #37)."""
    m[0xE340], m[0x4340] = 0xAA, 0x55
    m[0xE0E0 + 0x260], m[0x40E0 + 0x260] = 0xAA, 0x55
    sp = RC.arm(h, D2S)
    run_noint(h, sp)
    return {'shadow_after': m[0xE340], 'display_after': m[0x4340],
            'direction': ('display -> shadow' if m[0xE340] == 0x55
                          else 'shadow -> display' if m[0x4340] == 0xAA
                          else 'neither')}


def capture():
    pair = patch_pair()
    h, m = RC.new()
    fx = {'note': __doc__.strip(), 'repaint_at': REPAINT, 'digits_at': DIGITS,
          'd2s_at': D2S, 'patch_at': PATCH_AT, 'patch_from': list(PATCH_FROM),
          'patch_to': list(PATCH_TO), 'display_at': DISPLAY, 'display_n': DISPLAY_N,
          'shadow_at': SHADOW, 'colour_at': COLOUR, 'tens_at': TENS,
          'units_at': UNITS, 'dirty': DIRTY,
          'pair': pair, 'repaint': repaint_row(h, m),
          'digits': digit_rows(h, m), 'direction': direction_row(h, m)}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s' % FIXTURE)
    print('  THE PATCH PAIR -- the SAME build twice, with and without the scroll:')
    for r in pair:
        print('     round %2d: shadow %d, colour %d, display %d differ   '
              '(T %d vs %d, timer %d vs %d%s)'
              % (r['round'], r['shadow_differing'], r['colour_differing'],
                 r['differing'], r['t_scrolled'], r['t_not'],
                 r['timer_scrolled'], r['timer_not'],
                 '; slots %s moved' % r['ents_moved'] if r['ents_moved'] else ''))
    rp = fx['repaint']
    print('  $8216: %d bitmap + %d attribute writes, %d shadow + %d colour from its $7F80 '
          'tail; %d display bytes left dirty'
          % (rp['bitmap'], rp['attrs'], rp['shadow'], rp['colour'], rp['still_dirty']))
    print('  $854D copies %s' % fx['direction']['direction'])


def verify():
    fx = json.load(open(FIXTURE))
    print('THE HEADLINE -- suppress the scroll entirely and compare what the build produced:')
    for r in fx['pair']:
        print('   round %2d: SHADOW %d of 6144 differ, COLOUR %d of 768, display %d of %d'
              % (r['round'], r['shadow_differing'], r['colour_differing'],
                 r['differing'], fx['display_n']))
        if r['ents_moved']:
            print('             (and the display difference is the ISR: slots %s at %s '
                  'scrolled vs %s not, timer %d vs %d, T %d vs %d)'
                  % (r['ents_moved'],
                     [e[1:3] for e in r['ents_scrolled']],
                     [e[1:3] for e in r['ents_not']],
                     r['timer_scrolled'], r['timer_not'],
                     r['t_scrolled'], r['t_not']))
    print()
    print('$7F80, the round-number digits (seeded $AA so "drew nothing" is visible):')
    for r in fx['digits']:
        print('   round %2d -> %2d shadow writes, %d colour, %d display; $9A0E/$9A0F = %02X %02X%s'
              % (r['round'], r['shadow_writes'], r['colour_writes'], r['display_writes'],
                 r['tens'], r['units'],
                 '   <-- STALE, nothing drawn' if r['tens'] == 0xAA and
                                                  r['units'] == 0xAA else ''))
    print()
    print('$854D: %s (shadow $E340 ended $%02X, display $4340 ended $%02X)'
          % (fx['direction']['direction'], fx['direction']['shadow_after'],
             fx['direction']['display_after']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
