# -*- coding: utf-8 -*-
"""M7.33 -- $AD65, THE PLAYER'S JUMP ARC, and the gate the port had backwards.

NOT tools/jumpsfx.py, which is $8FA5's TONE: a different routine that happens to
read the same table at $B57D with a DIFFERENT index base ($8FC5 by PHASE, $AD7C by
PHASE-1).  Nothing in tools/ drove the arc MOVER before this.

    AD65  CALL $ADAA                the horizontal step (returns at once if (IY+8)&12 = 0)
    AD68  LD A,(IY+9)               the phase
    AD6B  LD L,A / DEC L            L = phase-1  *** EIGHT BIT, L ALONE ***
    AD6D  INC A                     A = the NEW phase
    AD6E  CP $21 / JR nz / LD A,$FF clamp 33 -> $FF
    AD74  LD (IY+9),A               *** STORED BEFORE THE PROBE DECIDES ***
    AD77  LD H,0                    *** THE INDEX IS UNSIGNED ***
    AD79  LD DE,$B57D / ADD HL,DE
    AD7D  CP $10 / JR nc,$AD90      *** THE NEW PHASE AGAINST 16 ***
    AD81  LD A,(IY+6) / ADD A,(HL) / LD (IY+6),A
    AD88  CP $C0 / RET c / LD (IY+6),0      the PLAIN step's bottom wrap -> 0
    AD90  ...probe... / JR nz,$AD81 / JP $AD51
    AD51  LD (IY+9),$FF / ADD A,2 / CP $BF / LD (IY+6),2   free-fall, wrap -> 2

*** WHAT THIS TOOL EXISTS TO MEASURE. ***  The port gated the descent probe on
`dy > 0`, which first holds at phase 19.  The machine gates on $AD7D `CP $10`, and A
there is the NEW phase, so it probes from OLD PHASE >= 15.  Phases 15..18 are exactly
the table's ZERO-DELTA entries, so the port skipped the probe on four phases the
machine takes it on -- REACHABLE, on any short hop whose apex has floor 16 px below.
phase_gate() is that differential, driven with floor AND without.

Everything is recorded as a DIFFERENCE between two runs of the same instruction
sequence, never as a single reading.

NO ROM BYTE is recorded: this routine reads the game's own table at $B57D.

Usage:  python tools/jumparc.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, SP
import portconfig as pc

FIXTURE = 'build/jumparc_fixture.json'
BRANCH_BYTE = 0x8DC4
DISPATCH = 0x8ACF0 & 0xFFFF     # $ACF0, the phase dispatch
ARC = 0xAD65
PROBE = 0xAD90
PLAIN = 0xAD81
FREEFALL = 0xAD51
INDEXED = 0xAD84
TABLE = 0xB57D
IY0 = 0xFD80
COLOUR = 0xF800
STATE = 'round1_48'
STATES = ('round1_48', 'play1p48')


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def place(h, m, phase, x, y, floor):
    """The WORLD the routine computes from, not its arguments.

    (IY+8) & 12 = 0 so $ADAA returns at $ADAF and the horizontal step cannot move
    the player -- the arc is then the only thing writing, which is what makes the
    Y difference attributable.  The colour shadow is cleared and then, if `floor`,
    ONE solid cell is placed on the row the probe will read.

    *** THE SOLID BIT: the machine's probe uses MASK $3F ($AE7F LD C,$3F) and the
    port's solidBelow uses $20. ***  A cell written $20 sets a bit both masks see,
    so this world cannot tell them apart -- deliberately, because that difference
    is its own follow-up and not what this phase measures.
    """
    r = h.sim.registers
    m[IY0 + 5] = x
    m[IY0 + 6] = y
    m[IY0 + 8] = 0
    m[IY0 + 9] = phase
    m[IY0 + 7] = 0xE1                  # in play, bit 7 set
    for a in range(COLOUR, COLOUR + 0x300):
        m[a] = 0
    if floor:
        #  the row the probe reads: (Y + 16 + dy) >> 3, and dy is 0 for the phases
        #  this matters for -- but place the whole row so the probe finds floor for
        #  any dy in -4..+4 rather than only for one
        for dy in range(-8, 9):
            row = COLOUR + (((y + 16 + dy) & 0xF8) << 2)
            for col in range(32):
                m[row + col] = 0x20
    r[10], r[11] = (IY0 >> 8) & 0xFF, IY0 & 0xFF     # IYh, IYl
    return r


def drive(h, m, start=ARC, limit=200000):
    """Run from `start` to a RET at the harness sentinel, logging the PCs that
       decide, and every write to the player's record."""
    r = h.sim.registers
    if not hasattr(h, '_sp0'):
        h._sp0 = r[SP]
    r[SP] = h._sp0
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = sent & 0xFF
        m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = start
    seen = []
    hl_at_index = None
    n = 0
    while n < limit:
        p = r[PC]
        if p in h.SENTINELS:
            break
        if p in (PROBE, PLAIN, FREEFALL, INDEXED, ARC, 0xAD88, 0xAD5D):
            seen.append('%04X' % p)
        if p == INDEXED and hl_at_index is None:
            #  *** H IS 6 AND L IS 7; 4/5 ARE D/E. ***  The first version of this
            #  line read DE, which $AD79 loads with the table BASE -- so every
            #  phase reported HL = $B57D and phase 0's -3 delta contradicted the
            #  -4 the base holds.  The measurement's own inconsistency is what
            #  caught it (TRAPS #151: a probe that cannot aim is not a
            #  measurement -- read the harness's register table, do not assume).
            hl_at_index = r[7] | (r[6] << 8)          # HL
        h.step(1, interrupts=False)
        n += 1
    else:
        raise SystemExit('never returned from $%04X' % start)
    return {'path': seen, 'hl': None if hl_at_index is None else '%04X' % hl_at_index,
            'y': m[IY0 + 6], 'phase': m[IY0 + 9], 'steps': n}


# ------------------------------------------------------------------ phase A
def phase_gate(x=0x18, y=0x90):
    """*** THE HEADLINE: WHICH PHASES PROBE THE FLOOR. ***

    Phases 13..21 over a world WITH floor on the probe row and a CONTROL with the
    colour shadow cleared.  A phase that probes and finds floor abandons the arc for
    free-fall (phase $FF); one that does not takes the plain step.  The port gated on
    `dy > 0`; if that were the machine's rule, phases 15..18 would take the plain step
    in BOTH worlds.
    """
    rows = []
    for state in STATES:
        for phase in range(13, 22):
            out = {}
            for floor in (True, False):
                h, m = new(state)
                place(h, m, phase, x, y, floor)
                y0 = m[IY0 + 6]
                res = drive(h, m)
                out['floor' if floor else 'clear'] = {
                    'y_before': y0, 'y_after': res['y'], 'phase_after': res['phase'],
                    'probed': PROBE in [int(p, 16) for p in res['path']],
                    'freefall': res['phase'] == 0xFF,
                    'hl': res['hl'], 'path': res['path']}
            dy = m[TABLE + phase - 1]
            dy_signed = dy - 256 if dy >= 0x80 else dy
            rows.append({'state': state, 'phase': phase, 'dy': dy_signed,
                         'probed': out['floor']['probed'],
                         'diverted_on_floor': out['floor']['freefall'],
                         'diverted_on_clear': out['clear']['freefall'],
                         'port_rule_dy_gt_0': dy_signed > 0,
                         'machine_rule_newphase_ge_16': (phase + 1) >= 0x10,
                         'floor': out['floor'], 'clear': out['clear']})
    print('(A) WHICH PHASES PROBE -- floor on the probe row against a cleared control')
    print('    phase  dy   probed  diverted(floor)  diverted(clear)  dy>0   newph>=16  AGREE?')
    bad = []
    for r0 in rows:
        if r0['state'] != STATES[0]:
            continue
        agree = r0['diverted_on_floor'] == r0['port_rule_dy_gt_0']
        if not agree:
            bad.append(r0['phase'])
        print('    %5d  %3d  %6s  %15s  %15s  %5s  %9s  %s'
              % (r0['phase'], r0['dy'], r0['probed'], r0['diverted_on_floor'],
                 r0['diverted_on_clear'], r0['port_rule_dy_gt_0'],
                 r0['machine_rule_newphase_ge_16'],
                 'yes' if agree else '*** NO ***'))
    print('    -> the port rule `dy > 0` is WRONG on phases %s; the machine gate is '
          'the NEW PHASE against 16 ($AD7D CP $10 on A after $AD6D INC A)' % bad)
    #  and the machine's own rule must agree with the observation everywhere
    for r0 in rows:
        assert r0['diverted_on_floor'] == r0['machine_rule_newphase_ge_16'], \
            'the newphase>=16 rule does not predict phase %d on %s' % (r0['phase'], r0['state'])
    assert bad == [15, 16, 17, 18], 'expected 15..18 to diverge, got %r' % bad
    return {'rows': rows, 'diverging': bad}


# ------------------------------------------------------------------ phase B
def phase_wraps():
    """THE TWO BOTTOM WRAPS, and they are NOT the same one.

        $AD88  CP $C0 / LD (IY+6),0     the PLAIN arc step
        $AD5D  CP $BF / LD (IY+6),2     the FREE-FALL tail the descent jumps to

    Driven from Y values that straddle each threshold, with the colour shadow CLEAR
    for the plain path (so no probe diverts it) and SOLID for the descent path.
    """
    out = {'plain': [], 'freefall': []}
    #  plain: a phase below 15 so the probe is never taken, dy = +4 is impossible
    #  there, so use the LAST ascending phase and walk Y up to the threshold
    for y in (0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xC1, 0xFC, 0xFE):
        h, m = new()
        place(h, m, 21, 0x18, y, False)       # phase 21 -> dy = +2, no floor
        res = drive(h, m)
        dy = m[TABLE + 20]
        out['plain'].append({'y_before': y, 'dy': dy - 256 if dy >= 0x80 else dy,
                             'y_after': res['y'], 'wrapped': res['y'] == 0})
    for y in (0xB8, 0xBA, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0):
        h, m = new()
        place(h, m, 19, 0x18, y, True)        # phase 19 -> probes, floor -> free-fall
        res = drive(h, m)
        out['freefall'].append({'y_before': y, 'y_after': res['y'],
                                'phase_after': res['phase'],
                                'wrapped': res['y'] == 2})
    print('(B) THE TWO BOTTOM WRAPS')
    print('    PLAIN ($AD88 CP $C0 -> 0):')
    for r0 in out['plain']:
        print('       Y $%02X + %d -> $%02X %s' % (r0['y_before'], r0['dy'],
              r0['y_after'], 'WRAPPED to 0' if r0['wrapped'] else ''))
    print('    FREE-FALL ($AD5D CP $BF -> 2):')
    for r0 in out['freefall']:
        print('       Y $%02X + 2 -> $%02X phase $%02X %s'
              % (r0['y_before'], r0['y_after'], r0['phase_after'],
                 'WRAPPED to 2' if r0['wrapped'] else ''))
    pw = [r0['y_before'] for r0 in out['plain'] if r0['wrapped']]
    fw = [r0['y_before'] for r0 in out['freefall'] if r0['wrapped']]
    print('    -> plain wraps from Y >= $%02X (landing 0); free-fall from Y >= $%02X '
          '(landing 2).  DIFFERENT thresholds AND different landing values.'
          % (min(pw) if pw else 0, min(fw) if fw else 0))
    out['plain_first_wrap'] = min(pw) if pw else None
    out['freefall_first_wrap'] = min(fw) if fw else None
    return out


# ------------------------------------------------------------------ phase C
def phase_zero():
    """PHASE 0: unreachable through the dispatch, determinate inside the routine.

    $ACF0 `LD A,(IY+9) / OR A / JP m,$AD11 / JP nz,$AD65 / CALL $ADAA` -- the
    `JP nz` IS the guard, so phase 0 never reaches $AD65.  Both arms are driven:
    from the DISPATCH (where it must not reach the arc) and from $AD65 DIRECTLY
    (where the index is an UNSIGNED 255, not a -1).
    """
    rows = []
    for phase in (0, 1):
        h, m = new()
        place(h, m, phase, 0x18, 0x90, False)
        y0 = m[IY0 + 6]
        d = drive(h, m, start=0xACF0)
        reached = 'AD84' in d['path'] or 'AD81' in d['path']
        rows.append({'entry': 'ACF0', 'phase': phase, 'y_before': y0,
                     'y_after': d['y'], 'phase_after': d['phase'],
                     'reached_arc': reached, 'hl': d['hl'], 'path': d['path']})
    direct = []
    for phase in (0, 1):
        h, m = new()
        place(h, m, phase, 0x18, 0x90, False)
        y0 = m[IY0 + 6]
        d = drive(h, m, start=ARC)
        direct.append({'entry': 'AD65', 'phase': phase, 'y_before': y0,
                       'y_after': d['y'], 'phase_after': d['phase'],
                       'hl': d['hl'], 'dy': (d['y'] - y0) if d['y'] >= y0
                                            else (d['y'] - y0)})
    print('(C) PHASE 0')
    for r0 in rows:
        print('    from $ACF0 phase %d: Y $%02X -> $%02X, phase -> $%02X, reached the '
              'arc: %s' % (r0['phase'], r0['y_before'], r0['y_after'],
                           r0['phase_after'], r0['reached_arc']))
    for r0 in direct:
        print('    from $AD65 phase %d: Y $%02X -> $%02X (%+d), HL at the read $%s'
              % (r0['phase'], r0['y_before'], r0['y_after'], r0['dy'], r0['hl']))
    z = [r0 for r0 in rows if r0['phase'] == 0][0]
    assert not z['reached_arc'], '$ACF7 did NOT guard phase 0'
    d0 = [r0 for r0 in direct if r0['phase'] == 0][0]
    print('    -> $ACF7 `JP nz` guards it, so the port is right to refuse; and INSIDE '
          'the routine the index is an UNSIGNED 255 ($AD6C DEC L on L alone, $AD77 '
          'LD H,0), landing on $%s -- NOT $B57C, the byte before the table.'
          % d0['hl'])
    return {'dispatch': rows, 'direct': direct,
            'guarded': not z['reached_arc'], 'phase0_hl': d0['hl'],
            'phase0_dy': d0['dy']}


# ------------------------------------------------------------------ phase D
def phase_index():
    """THE INDEX IS ONE FLAT UNSIGNED BYTE -- no modulus, no second table.

    HL at $AD84 for every phase 1..32, plus a few above, so the port's
    `(idx - 24) & 7` can be checked against what the machine actually does.
    """
    rows = []
    for phase in list(range(1, 33)) + [33, 40]:
        h, m = new()
        place(h, m, phase, 0x18, 0x60, False)   # high up, no floor, no wrap
        d = drive(h, m)
        hl = int(d['hl'], 16) if d['hl'] else None
        rows.append({'phase': phase, 'hl': d['hl'],
                     'offset': None if hl is None else hl - TABLE,
                     'expected_offset': (phase - 1) & 0xFF,
                     'flat': hl is not None and (hl - TABLE) == ((phase - 1) & 0xFF),
                     #  the STORED phase, so $AD6E's clamp is measured and not
                     #  derived: a battery survivor showed no gate drove phase 31,
                     #  where `CP $21` versus `CP $20` first differ
                     'phase_after': d['phase'],
                     'y_after': d['y']})
    ok = all(r0['flat'] for r0 in rows if r0['hl'])
    print('(D) THE INDEX: base $%04X + (phase-1), one flat unsigned byte' % TABLE)
    for r0 in rows:
        if r0['phase'] in (1, 24, 25, 31, 32, 33, 40):
            print('    phase %2d -> HL $%s  offset %s (expected %d)  %s'
                  % (r0['phase'], r0['hl'], r0['offset'], r0['expected_offset'],
                     'flat' if r0['flat'] else '*** NOT FLAT ***'))
    print('    -> %s.  The port\'s `(idx - 24) & 7` is a NO-OP over phases 25..32 '
          '(indices 24..31) and WRONG above 32, where the machine walks straight into '
          'the next table -- but $AD6E `CP $21` clamps 33 to $FF before the store, so '
          'no phase above 32 is ever indexed.'
          % ('every phase indexes flat' if ok else 'A PHASE DOES NOT INDEX FLAT'))
    return {'rows': rows, 'all_flat': ok}


# ------------------------------------------------------------------ phase E
def phase_floortick():
    """THE FLOOR TICK $AD18 AT ITS OWN ENTRY, and it does TWO PROBES.

        AD35  LD C,$20 / CALL $AE81    probe ONE: the FEET row (Y+15), mask $20,
                                       with $AE9C PATCHED TO RET for the duration
        AD45  INC D / CALL $AE7F       probe TWO: the row BELOW, mask $3F
        AD4C  LD (IY+9),0              LAND -- only if one found NOTHING and two DID

    So the world that makes it land has the FEET ROW CLEAR and THE ROW BELOW SOLID.
    The first version of this phase put floor on both and every row fell, floored and
    floorless alike; the assert below is what refused to write that fixture.

    A consequence that falls out of the arithmetic: the two probes read different
    CHARACTER rows only when (Y & $FE) + 15 is a cell's last pixel row, i.e. Y = 0
    mod 8.  Anywhere else both read the same cell and landing is impossible, so the
    machine lands only on eight-pixel boundaries without anything checking for it.

    *** THE PORT MODELS ONE PROBE. ***  `playerFloorTick` calls solidBelow once, with
    mask $20, at the row below.  Recorded here, gated as a KNOWN DIVERGENCE, and left
    for its own increment: two masks, two rows and two self-modified bytes.
    """
    rows = []
    for y in (0x60, 0x68, 0xB8, 0xBA, 0xBC, 0xBD, 0xBE, 0xC0, 0xFE):
        for world in ('below', 'both', 'none'):
            h, m = new()
            place(h, m, 0xFF, 0x18, y, False)        # clears the colour shadow
            ya = y & 0xFE
            feet = COLOUR + ((((ya + 15) >> 3) & 0x1F) << 5)
            under = COLOUR + ((((ya + 16) >> 3) & 0x1F) << 5)
            if world in ('below', 'both'):
                for c in range(32):
                    m[under + c] = 0x20
            if world == 'both':
                for c in range(32):
                    m[feet + c] = 0x20
            same_cell = ((ya + 15) >> 3) == ((ya + 16) >> 3)
            d = drive(h, m, start=0xAD18)
            rows.append({'y_before': y, 'y_even': ya, 'world': world,
                         'same_cell': same_cell,
                         'y_after': d['y'], 'phase_after': d['phase'],
                         'landed': d['phase'] == 0,
                         'wrapped': (not d['phase'] == 0) and d['y'] == 2})
    print('(E) THE FLOOR TICK at $AD18 -- TWO probes, so THREE worlds')
    for r0 in rows:
        print('    Y $%02X (even $%02X) %-5s %s -> Y $%02X phase $%02X %s%s'
              % (r0['y_before'], r0['y_even'], r0['world'],
                 'same-cell' if r0['same_cell'] else 'two-cell ',
                 r0['y_after'], r0['phase_after'],
                 'LANDED' if r0['landed'] else 'fell',
                 '  WRAPPED to 2' if r0['wrapped'] else ''))
    #  the claims, asserted so this phase cannot report an inert control
    landed = [r0 for r0 in rows if r0['landed']]
    assert landed, 'NO world landed -- the control is inert'
    assert all(r0['world'] == 'below' for r0 in landed), \
        'something other than a clear-feet/solid-below world landed'
    assert all(not r0['same_cell'] for r0 in landed), \
        'a same-cell world landed, which the two-probe arithmetic forbids'
    both = [r0 for r0 in rows if r0['world'] == 'both']
    assert not any(r0['landed'] for r0 in both), \
        'a SOLID FEET row landed -- probe one should send it to free-fall'
    wrapped = [r0['y_before'] for r0 in rows if r0['wrapped']]
    print('    -> lands ONLY on a clear-feet/solid-below world at a two-cell Y '
          '(Y = 0 mod 8): %s' % sorted(set(r0['y_before'] for r0 in landed)))
    print('    -> a SOLID FEET row falls instead of landing, which is probe one, and '
          'the port models ONE probe: a KNOWN DIVERGENCE, its own increment')
    print('    -> $AD5D wraps to 2 from Y >= $%02X, measured HERE and not borrowed '
          'from the arc path' % (min(wrapped) if wrapped else 0))
    return {'rows': rows, 'first_wrap': min(wrapped) if wrapped else None,
            'landing_ys': sorted(set(r0['y_before'] for r0 in landed)),
            'two_probes': True,
            'port_models_one_probe': True}


# ------------------------------------------------------------------ phase F
def phase_probe():
    """$AE7F ITSELF, over ALL 256 X -- including the odd ones the movers never reach.

        AE7F  LD C,$3F              the ARC's entry
        AE81  PUSH BC               the FLOOR TICK's, C already loaded
        AE82  CALL $AED1            HL := the colour cell from D (row) and E (X)
        AE86  LD D,E / LD E,0       D := the X low byte, E := 0 (clear)
        AE89  LD A,(HL) / AND C / JR nz,$AE9A
        AE8D  INC L / LD A,(HL) / AND C / JR nz,$AE9A
        AE92  LD A,D / AND 6 / RET z        <- THE THIRD CELL IS CONDITIONAL ON X
        AE96  INC L / LD A,(HL) / AND C / RET z
        AE9A  LD E,1                        E := 1 (solid)

    The third cell is read only when `X & 6` is non-zero, so a sprite straddling three
    cells probes all three and one straddling two probes two.  `AND 6` and `AND 7`
    differ only at X = 1 mod 8, which no mover produces -- X parity is preserved over
    1,024 driven $ADAA runs -- so the distinction is gated HERE, at the routine's own
    entry, rather than through a caller that cannot express it.

    The world puts floor in the THIRD cell only, so a probe that reads it says solid
    and one that stops at two says clear -- the difference is the whole measurement.
    """
    rows = []
    h0, m0 = new()
    for x in range(256):
        h, m = new()
        r = h.sim.registers
        for a in range(COLOUR, COLOUR + 0x300):
            m[a] = 0
        row = COLOUR + ((0x60 >> 3) << 5)
        c0 = row + ((x >> 3) & 0x1F)
        #  FLOOR IN THE THIRD CELL ONLY: cells 0 and 1 clear, cell 2 solid
        m[(c0 + 2) & 0xFFFF] = 0x20
        if not hasattr(h, '_sp0'):
            h._sp0 = r[SP]
        sp = r[SP]
        for sent in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp] = sent & 0xFF
            m[sp + 1] = sent >> 8
        r[SP] = sp
        r[4] = 0x60                      # D = the pixel row
        r[5] = x                         # E = X
        r[PC] = 0xAE7F
        n = 0
        while n < 40000 and r[PC] not in h.SENTINELS:
            h.step(1, interrupts=False)
            n += 1
        rows.append({'x': x, 'solid': r[5] == 1,
                     'third_read': (x & 6) != 0,
                     'and6': (x & 6) != 0, 'and7': (x & 7) != 0})
    differ = [r0['x'] for r0 in rows if r0['and6'] != r0['and7']]
    #  the measured outcome must follow AND 6, not AND 7
    wrong = [r0['x'] for r0 in rows if r0['solid'] != r0['and6']]
    print('(F) $AE7F OVER ALL 256 X, floor in the THIRD cell only')
    print('    solid for %d of 256 X values; X where `AND 6` and `AND 7` disagree: %s'
          % (sum(1 for r0 in rows if r0['solid']), differ[:8] +
             (['...'] if len(differ) > 8 else [])))
    print('    X values where the MEASURED result disagrees with `AND 6`: %s'
          % (wrong or 'NONE'))
    assert not wrong, 'the measured probe does not follow `AND 6`: %r' % wrong[:8]
    assert differ, 'no X distinguishes AND 6 from AND 7 -- the phase measures nothing'
    print('    -> the third cell is read exactly when `X & 6` is non-zero, and the %d '
          'X values at 1 mod 8 are what separate it from `AND 7`' % len(differ))
    return {'rows': rows, 'differ_at': differ,
            'solid_count': sum(1 for r0 in rows if r0['solid'])}


# ------------------------------------------------------------------ phase G
POOL = 0xFED8             # bubble slot 0; stride 10, flags at +7
POOL_FLAGS = 0xFEDF       # $AEBA LD HL,$FEDF -- slot 0's flags
BOUNCE = 0xAEA7
STAMP = 0xAEAD
FLOOR_RET = 0xAEA0
TAIL = 0xAEA1
PROBE_SOLID = 0xAE9A


def place_cell(m, x, y, dy, value):
    """Put `value` in the colour cell the probe will read, and clear the rest."""
    for a in range(COLOUR, COLOUR + 0x300):
        m[a] = 0
    row = COLOUR + ((((y + 16 + dy) & 0xF8) << 2))
    for col in range(32):
        m[row + col] = value
    return row


def phase_tail():
    """THE THREE BRANCHES, from BOTH entries, as a difference table.

    Every row differs from its neighbour in ONE input -- the cell (wall against
    bubble) or the jump bit -- so each line of the table is attributable.  A live
    bubble is placed in the slot the tag names, because $AEC0 `BIT 7,(HL) / RET z`
    refuses a dead one and a dead slot would make the pop path look like a no-op.
    """
    rows = []
    for entry, phase in ((0xAD18, 0x00), (0xAD65, 0x14)):
        for cellname, cell in (('wall', 0x20), ('bubble', 0x0C)):
            for jump in (False, True):
                h, m = new()
                place(h, m, phase, 0x18, 0x90, False)
                #  the probe row: for the floor tick it is (Y&$FE)+16, for the arc
                #  it is Y + 16 + dy.  Fill BOTH so one world serves both entries.
                for d in range(-8, 9):
                    r0 = COLOUR + ((((0x90 + 16 + d) & 0xF8) << 2))
                    for col in range(32):
                        m[r0 + col] = cell
                #  tag 12 -> slot 0; give that slot a LIVE bubble
                slot = (12 - (cell & 0x1F)) & 0xFF if (cell & 0x1F) else 0
                m[(POOL_FLAGS + 10 * slot) & 0xFFFF] = 0x84
                m[IY0 + 8] = 0x22 if jump else 0x44     # bit 1 = JUMP held
                m[IY0 + 0x5A] = 0x5A                    # bit 0 clear -> credit P1
                y0, ph0 = m[IY0 + 6], m[IY0 + 9]
                fl0 = m[(POOL_FLAGS + 10 * slot) & 0xFFFF]
                d = drive(h, m, start=entry)
                rows.append({
                    'entry': '%04X' % entry, 'phase_in': phase,
                    'cell': cellname, 'cell_value': cell, 'jump': jump,
                    'slot': slot,
                    'y_before': y0, 'y_after': d['y'],
                    'phase_after': d['phase'],
                    'flags_before': fl0,
                    'flags_after': m[(POOL_FLAGS + 10 * slot) & 0xFFFF],
                    'bounced': d['phase'] == 1 and d['y'] == y0,
                    'path': d['path']})
    print('(G) THE TAIL -- three branches, both entries, one input changing per row')
    print('    entry  phase  cell    jump  ->  phase   Y        bubble flags   what')
    for r0 in rows:
        what = ('BOUNCE' if r0['bounced'] else
                ('POP' if r0['flags_after'] != r0['flags_before'] else 'floor'))
        print('    $%s  %3d   %-6s %-5s -> $%02X   $%02X->$%02X  $%02X->$%02X   %s'
              % (r0['entry'], r0['phase_in'], r0['cell'], r0['jump'],
                 r0['phase_after'], r0['y_before'], r0['y_after'],
                 r0['flags_before'], r0['flags_after'], what))
    #  the claims, asserted so an inert table cannot ship
    bounced = [r0 for r0 in rows if r0['bounced']]
    assert len(bounced) == 2, 'expected a bounce from BOTH entries, got %d' % len(bounced)
    assert all(r0['cell'] == 'bubble' and r0['jump'] for r0 in bounced)
    assert all(r0['y_after'] == r0['y_before'] for r0 in bounced), \
        'the bounce moved Y'
    assert all(r0['flags_after'] == r0['flags_before'] for r0 in bounced), \
        'the bounce disturbed the bubble'
    popped = [r0 for r0 in rows if r0['cell'] == 'bubble' and not r0['jump']]
    assert popped and all(r0['flags_after'] != r0['flags_before'] for r0 in popped), \
        'a bubble under a non-jumping player was not stamped'
    walls = [r0 for r0 in rows if r0['cell'] == 'wall']
    assert all(r0['flags_after'] == r0['flags_before'] for r0 in walls), \
        'a WALL cell stamped a bubble'
    assert all(not r0['bounced'] for r0 in walls), 'a WALL cell bounced'
    print('    -> BOTH entries bounce; the bounce leaves Y AND the bubble alone; a '
          'non-jumping player STAMPS it; a wall does neither, because $AE9C finds bit 5')
    return rows


# ------------------------------------------------------------------ phase H
def phase_stamp():
    """$AEAD's slot arithmetic over EVERY tag, and the bits it sets.

    `12 - tag`, times ten, from $FEDF -- the exact inverse of $B8C0's claim.  HL is
    read out of the register file at $AEC0 rather than predicted, and the write set
    is compared against the prediction so a wrong stride shows as a wrong ADDRESS
    and not merely a wrong byte.
    """
    rows = []
    for tag in range(0, 16):
        h, m = new()
        place(h, m, 0x00, 0x18, 0x90, False)
        for d in range(-8, 9):
            r0 = COLOUR + ((((0x90 + 16 + d) & 0xF8) << 2))
            for col in range(32):
                m[r0 + col] = tag                   # bit 5 CLEAR: a bubble cell
        m[IY0 + 8] = 0x44                           # jump NOT held -> the STAMP path
        m[IY0 + 0x5A] = 0x5A
        for k in range(12):
            m[(POOL_FLAGS + 10 * k) & 0xFFFF] = 0x84
        before = [m[(POOL_FLAGS + 10 * k) & 0xFFFF] for k in range(12)]
        r = h.sim.registers
        hl_at = None
        #  drive, breaking at $AEC0 to read HL
        sp = None
        if not hasattr(h, '_sp0'):
            h._sp0 = r[SP]
        r[SP] = h._sp0
        spv = r[SP]
        for sent in reversed(h.SENTINELS):
            spv = (spv - 2) & 0xFFFF
            m[spv] = sent & 0xFF
            m[spv + 1] = sent >> 8
        r[SP] = spv
        r[PC] = 0xAD18
        n = 0
        while n < 200000 and r[PC] not in h.SENTINELS:
            if r[PC] == 0xAEC0 and hl_at is None:
                hl_at = r[7] | (r[6] << 8)
            h.step(1, interrupts=False)
            n += 1
        after = [m[(POOL_FLAGS + 10 * k) & 0xFFFF] for k in range(12)]
        moved = [k for k in range(12) if after[k] != before[k]]
        #  *** THE x10 IS EIGHT-BIT. ***  $AEB4 is ADD A,A / LD B,A / ADD A,A /
        #  ADD A,A / ADD A,B on the ACCUMULATOR, so 10*slot truncates to a byte
        #  before $AEBA's LD D,0 / ADD HL,DE.  My first prediction multiplied in
        #  Python's arbitrary precision and disagreed with the machine for every
        #  tag above 12 -- which is how the out-of-range wrap got measured: tag 13
        #  gives slot $FF, 10*$FF = $9F6 truncated to $F6, and $FEDF + $F6 = $FFD5,
        #  ABOVE the pool and near the score bytes.
        slot8 = (12 - tag) & 0xFF
        pred = (POOL_FLAGS + ((10 * slot8) & 0xFF)) & 0xFFFF
        rows.append({'tag': tag, 'hl': None if hl_at is None else '%04X' % hl_at,
                     'predicted': '%04X' % pred,
                     'matches': hl_at == pred,
                     'slots_moved': moved,
                     'flags_after': [after[k] for k in moved],
                     'reached': hl_at is not None})
    print('(H) $AEAD -- 12 - tag, times ten, from $FEDF')
    for r0 in rows:
        print('    tag %2d -> HL %s (predicted $%s) %s  slots moved %s %s'
              % (r0['tag'], ('$' + r0['hl']) if r0['hl'] else '(not reached)',
                 r0['predicted'], 'ok' if r0['matches'] else '*** NO ***',
                 r0['slots_moved'],
                 ['$%02X' % v for v in r0['flags_after']]))
    #  EVERY tag must land where the EIGHT-BIT arithmetic predicts, including the
    #  out-of-range ones -- that is the claim, not just that the live ones work
    reached = [r0 for r0 in rows if r0['reached']]
    assert all(r0['matches'] for r0 in reached),         'a tag did not land where the 8-bit arithmetic predicts: %r' %         [r0['tag'] for r0 in reached if not r0['matches']]
    live = [r0 for r0 in rows if 1 <= r0['tag'] <= 12]
    assert all(r0['matches'] for r0 in live), 'a live tag did not land where predicted'
    #  tag 0 is not solid at all, so the tail is never entered
    z = [r0 for r0 in rows if r0['tag'] == 0]
    assert z and not z[0]['reached'], 'a ZERO cell reached the tail -- it is not solid'
    #  and tags 13..15 land ABOVE the pool, which is the latent out-of-range write
    oor = [r0 for r0 in rows if r0['tag'] >= 13]
    assert all(int(r0['hl'], 16) > POOL_FLAGS + 110 for r0 in oor),         'an out-of-range tag did not land above the pool'
    assert all(not r0['slots_moved'] for r0 in oor),         'an out-of-range tag stamped a pool slot'
    assert all(len(r0['slots_moved']) <= 1 for r0 in rows), \
        'a stamp touched more than one slot'
    stamped = [r0 for r0 in live if r0['slots_moved']]
    assert stamped and all(v == (0x84 | 0x08 | 0x02) & 0xEF for v in
                           [x for r0 in stamped for x in r0['flags_after']]), \
        'the stamped bits are not SET 3 / SET 1 / RES 4'
    print('    -> tags 1..12 land exactly on $FEDF + 10*(12-tag), each touching ONE '
          'slot, and the bits are SET 3 / SET 1 / RES 4 (credit P1)')
    return rows


# ------------------------------------------------------------------ phase I
def phase_attrib():
    """THE ATTRIBUTION BIT: $AEC9 `BIT 0,(IY+$5A) / RET z / SET 4,(HL)`.

    Bit 4 of the slot's flags is which player gets the credit, and it comes from
    bit 0 of (IY+$5A) -- NOT from which record IY points at.  Both IY values are
    driven with both values of the bit, so a port keying on the record fails here.
    """
    rows = []
    for iy in (0xFD80, 0xFD8A):
        for bit in (0, 1):
            h, m = new()
            #  the routine reads (IY+...) so IY must be the record under test
            r = h.sim.registers
            place(h, m, 0x00, 0x18, 0x90, False)
            for d in range(-8, 9):
                r0 = COLOUR + ((((0x90 + 16 + d) & 0xF8) << 2))
                for col in range(32):
                    m[r0 + col] = 0x0C            # tag 12 -> slot 0
            m[iy + 8] = 0x44                      # jump NOT held
            m[iy + 6] = 0x90
            m[iy + 5] = 0x18
            m[iy + 7] = 0xE1
            m[iy + 9] = 0x00
            m[(iy + 0x5A) & 0xFFFF] = 0x5A | bit
            m[POOL_FLAGS] = 0x84
            r[10], r[11] = (iy >> 8) & 0xFF, iy & 0xFF
            d = drive(h, m, start=0xAD18)
            rows.append({'iy': '%04X' % iy, 'bit0': bit,
                         'flags': m[POOL_FLAGS],
                         'bit4': (m[POOL_FLAGS] >> 4) & 1})
    print('(I) ATTRIBUTION -- bit 4 of the flags from BIT 0 of (IY+$5A)')
    for r0 in rows:
        print('    IY $%s  (IY+$5A)&1 = %d  ->  flags $%02X, bit 4 = %d'
              % (r0['iy'], r0['bit0'], r0['flags'], r0['bit4']))
    for r0 in rows:
        assert r0['bit4'] == r0['bit0'], \
            'attribution does not follow (IY+$5A) bit 0 for IY $%s' % r0['iy']
    by_iy = {}
    for r0 in rows:
        by_iy.setdefault(r0['iy'], set()).add(r0['bit4'])
    assert all(v == {0, 1} for v in by_iy.values()), \
        'one IY did not produce both attributions -- the record is not the input'
    print('    -> it follows the BIT, not the record: BOTH IY values give BOTH '
          'attributions, so a port keying on which player IY points at is wrong')
    return rows


def capture():
    out = {'gate': phase_gate(), 'wraps': phase_wraps(),
           'zero': phase_zero(), 'index': phase_index(),
           'floortick': phase_floortick(), 'probe': phase_probe(),
           'tail': phase_tail(), 'stamp': phase_stamp(), 'attrib': phase_attrib()}
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s (no ROM byte: the game\'s own $B57D table and its own record)'
          % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
