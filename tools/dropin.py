"""M7.7-H12 -- THE ENEMY DROP-IN, AND THE THREE PROVISIONAL NUMBERS.

The reading pass moved three of its own claims OUT of the settled model and into
LOW CONFIDENCE, to be taken here and nowhere else:
    "2 px per tick on the ODD ISR = 1 px/frame"
    "targets over rounds 2..21 range 0..168, window 88 x 2 = 176 px"
    "the top-of-playfield CLIP -- invisible until Y ~ 4, slides out from under
     the HUD at pixel row 16"
*** THE THIRD IS ALREADY WRONG. ***  There is no top-of-playfield clip on that
path.  $A3E3/$A3EA/$A3F2/$A3F9 call $A42B, which is an EXCLUSION test -- the
entity is SKIPPED when its Y lies INSIDE a 30-pixel band -- and $A430
SELF-MODIFIES ITS OWN ADDEND at $A431, so the band walks DOWN THROUGH A PASS
(re-seeded $B9 by $A3D2 before every pass -- it does NOT persist across frames,
CORRECTED M7.49).  It is beam avoidance, not a clip, and
at low Y the entity is drawn.  Measured, not read.

  $7336  the ARMING: for ($AA57)-2 slots at stride 10, target := (IY+6) into
         $73A6+i and then (IY+6) := 0, so every enemy starts at the top and
         falls to where the spawner put it.  ($AA57)-2 is 3..7 in the shipped
         game (F0), so it walks 3 to 7 slots and never more.  It also patches
         the count into $7460.
  $B520  the settler: +2 per tick on the ODD ISR only, toward $73A6[i].
  $AA72  JP nz,$B520 ABANDONS the rest of the entity pass INCLUDING BOTH
         PLAYERS -- which is the shipped bug M7.7-a found.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT A CAPTURED ROUND CAN GATE THE RAMP.  settle.py already records why: an
    enemy's ordinary FALL is also (Y+2) on the odd ISR, the one steady capture
    has every enemy already AT its target, and round 1's targets are all equal.
    The worlds here are BUILT.

  * THAT EVERY SLOT MOVES.  Rounds 14 and 17 have enemies whose target IS 0 and
    which never move -- include one, or "the settler ran" and "the settler was a
    no-op" are the same observation.

  * THAT THE RAMP CAN OVERSHOOT.  Y <= target always, because $7336 zeroes every
    Y and every target comes from the record.  ASSERTED AS A NEGATIVE over a full
    window, and (IY+6) is poked ABOVE its target to characterise the unclamped
    eight-bit INC that case would take.

Usage:  python tools/dropin.py capture
        python tools/dropin.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC
import settle as ST

ARM = 0x7336
TARGETS = 0x73A6
COUNT_OP = 0x7460
SETTLER = 0xB520
FREEZE = 0xB54B
ENEMY0 = 0xFD94
P1 = 0xFD80
STRIDE = 10
ENEMIES = 0xAA57
BUILD = 0x97F8
ROUND = 0x8609
DRAW = 0xA3AD
CLIP = 0xA42B
BAND = 0xA430
BAND_OP = 0xA431
BAND_W = 0x1E
ROUNDS = (1, 2, 10, 14, 17)
FIXTURE = 'build/dropin_fixture.json'


def build_to(h, m, target):
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    for _ in range(100):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, BUILD)
        RC.run(h, sp)
        if m[ROUND] == target:
            return
    raise SystemExit('never reached round %d' % target)


# ------------------------------------------------- (a) the arming, per round
def arm_rows(h, m):
    """At the end of a real build: every enemy's (IY+6) is ZERO and $73A6[i]
       holds the Y the spawner parked."""
    rows = []
    for rnd in ROUNDS:
        build_to(h, m, rnd)
        n = (m[ENEMIES] - 2) & 0xFF
        rows.append({
            'round': rnd, 'enemies': m[ENEMIES], 'walked': n,
            'count_operand': m[COUNT_OP],
            'ys': [m[ENEMY0 + STRIDE * i + 6] for i in range(n)],
            'targets': [m[TARGETS + i] for i in range(n)],
            'freeze': m[FREEZE],
        })
    return rows


# ------------------------------------------ (b) the ramp, per frame, per slot
def ramp_rows(rnd, armed=True):
    """*** BUILT ON settle.py, WHICH ALREADY SOLVED THIS. ***  My first version
       ran RC.run($97F8) and then free-ran frames -- but a direct call leaves PC
       parked on a SENTINEL, which is game DATA, so the Z80 executes bytes that
       are not code until an interrupt rescues it.  Every enemy Y came back as 2,
       the freeze never armed and P1 drifted.  settle.py documents exactly that
       and its spawn_world(resume=True) restores SP and puts PC on the LOOP TOP.

       $727B spawns the round with every enemy at Y = 0 and its real row in
       $73A6, which is the drop-in's starting state by construction."""
    h, m = ST.new()
    ST.spawn_world(h, m, rnd, resume=True)
    n = (m[ENEMIES] - 2) & 0xFF
    targets = [m[TARGETS + i] for i in range(n)]
    m[FREEZE] = (0x14 if rnd == 1 else 0x58) if armed else 0
    m[0xFEC4] = 0x14
    frames = []
    for f in range(220):
        frames.append({'f': f, 'freeze': m[FREEZE],
                       'ys': [m[ENEMY0 + STRIDE * i + 6] for i in range(n)]})
        h.run_frames(1, interrupts=True)
    return {'round': rnd, 'armed': armed, 'n': n, 'targets': targets,
            'frames': frames,
            'final': [m[ENEMY0 + STRIDE * i + 6] for i in range(n)]}


def overshoot_rows(rnd):
    """THE NEGATIVE: Y never passes its target in the shipped game, because
       $7336 zeroes every Y and every target comes from the record.  Poked ABOVE
       its target, the ramp is CHARACTERISED rather than guessed -- settle.py
       already records that both INCs are eight-bit with no clamp."""
    h, m = ST.new()
    ST.spawn_world(h, m, rnd, resume=True)
    tgt = m[TARGETS]
    m[ENEMY0 + 6] = (tgt + 8) & 0xFF
    m[FREEZE] = 0x58
    m[0xFEC4] = 0x14
    seen = []
    for _ in range(60):
        h.run_frames(1, interrupts=True)
        seen.append(m[ENEMY0 + 6])
    return {'round': rnd, 'target': tgt, 'poked_to': (tgt + 8) & 0xFF,
            'trace': seen[:28], 'final': seen[-1]}


# ------------------------------------------------------ (c) the FREEZE window
def freeze_rows():
    """P1's X every frame with a MOVEMENT KEY HELD, each armed window PAIRED
       WITH A CONTROL at $B54B = 0 and the same key -- settle.py's rule: a player
       that was never asked to move is frozen either way, so without the control
       the armed window proves nothing."""
    out = []
    for armed in (True, False):
        h, m = ST.new()
        x0 = m[P1 + 5]
        m[FREEZE] = 0x58 if armed else 0
        m[0xFEC4] = 0x14
        h.ports.pressed = {}
        h.ports.press(0xEF, 0xFF & ~0x04)          # hold '8' -- P1 right
        seen = []
        for f in range(200):
            seen.append({'f': f, 'x': m[P1 + 5], 'freeze': m[FREEZE]})
            h.run_frames(1, interrupts=True)
        # THE ASSERTION IS "CONSTANT WHILE THE COUNTER IS NON-ZERO", not "never
        # moves": 88 ticks on the ODD ISR is 176 frames, and a 200-frame window
        # runs 24 frames PAST the freeze, in which P1 walks 12 steps.  Reporting
        # only the whole-window spread would make the armed case look unfrozen.
        frozen = [s['x'] for s in seen if s['freeze'] != 0]
        after = [s['x'] for s in seen if s['freeze'] == 0]
        out.append({'armed': armed, 'x_at_entry': x0,
                    'frames_frozen': len(frozen),
                    'x_while_frozen': sorted(set(frozen)),
                    'x_after_thaw': sorted(set(after)),
                    'constant_while_frozen': len(set(frozen)) <= 1,
                    'distinct_x': sorted({s['x'] for s in seen}),
                    'moved': len({s['x'] for s in seen}) > 1,
                    'freeze_first': seen[0]['freeze'],
                    'freeze_last': seen[-1]['freeze'],
                    'samples': seen[:80]})
    return out


# ------------------------------------------------------------ (d) THE CLIP
def clip_rows(h, m):
    """*** NOT A TOP-OF-PLAYFIELD CLIP. ***  $A42B skips the entity when its Y is
       INSIDE a 30-pixel band, and $A430 self-modifies the band's base at $A431
       so it walks DOWN through a pass (re-seeded $B9 before every pass, M7.49)."""
    r = h.sim.registers
    m[BAND_OP] = 0x2A
    walk = []
    for _ in range(10):
        sp = RC.arm(h, BAND)
        r[0] = 1
        h.run_until(h.SENTINELS, limit=1000, stride=1, interrupts=False)
        walk.append({'returned': r[0], 'operand': m[BAND_OP]})
    table = []
    for b in (0x2B, 0x60):
        row = []
        for y in range(0, 0x100, 4):
            sp = RC.arm(h, CLIP)
            r[0], r[2], r[3] = y, b, (b + BAND_W) & 0xFF
            h.run_until(h.SENTINELS, limit=1000, stride=1, interrupts=False)
            row.append({'y': y, 'skip': (r[1] & 1) == 1})
        table.append({'base': b, 'ceil': (b + BAND_W) & 0xFF, 'row': row})
    return {'band_walk': walk, 'band_width': BAND_W, 'tables': table,
            'four_tests': ['(IY+6)', '(IY+6)+$10', '(IY+2)', '(IY+2)+$10']}


# --------------------------------------------------------------------- main
def capture():
    # *** ONE HARNESS PER PHASE. ***  The first run died with "SP ended at $96CB,
    # expected $96CD": a phase that drives routines directly, with interrupts
    # off, leaves the machine in a state the next phase's chained build does not
    # expect.  H9 paid for the same shape twice (an ISR contaminating a census, a
    # destructive probe left unrestored).  A fresh harness per phase costs a few
    # seconds and removes the whole class.
    h, m = RC.new()
    out = {
        'note': ('M7.7-H12 the enemy drop-in.  $7336 moves every enemy Y into $73A6 as '
                 'a TARGET and zeroes the enemy, so they fall in from the top; $B520 '
                 'ramps them +2 per tick on the ODD ISR while $AA72 abandons the rest '
                 'of the pass INCLUDING BOTH PLAYERS.  *** AND THE READING PASS\'S '
                 '"top-of-playfield clip" IS NOT ONE ***: $A42B EXCLUDES a 30-pixel '
                 'band and $A430 self-modifies its base at $A431, so the band walks '
                 'down through a pass ($A3D2 re-seeds $B9 before every pass -- M7.49).'),
        'arm_at': ARM, 'targets_at': TARGETS, 'count_op': COUNT_OP,
        'settler_at': SETTLER, 'freeze_at': FREEZE, 'enemy0': ENEMY0,
        'stride': STRIDE, 'enemies_at': ENEMIES, 'p1_at': P1,
        'draw_at': DRAW, 'clip_at': CLIP, 'band_at': BAND, 'band_op': BAND_OP,
        'band_width': BAND_W,
        'arm': arm_rows(h, m),
    }
    h, m = RC.new(); out['clip'] = clip_rows(h, m)
    out['ramp2'] = ramp_rows(2)
    out['ramp2_control'] = ramp_rows(2, armed=False)
    out['ramp14'] = ramp_rows(14)
    out['overshoot'] = overshoot_rows(2)
    out['freeze'] = freeze_rows()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    for r in f['arm']:
        print('round %2d: $AA57=%d, walks %d slots (operand %d), Ys %s, targets %s, freeze %d'
              % (r['round'], r['enemies'], r['walked'], r['count_operand'],
                 r['ys'], r['targets'], r['freeze']))
    for k in ('ramp2', 'ramp2_control', 'ramp14'):
        rr = f[k]
        fr = rr['frames']
        print('%s (armed=%s): %d slots, targets %s -> final %s'
              % (k, rr['armed'], rr['n'], rr['targets'], rr['final']))
        print('   first 6 frames: %s' % [(x['f'], x['freeze'], x['ys']) for x in fr[:6]])
        print('   last frame:     %s' % [(fr[-1]['f'], fr[-1]['freeze'], fr[-1]['ys'])])
    ov = f['overshoot']
    print('OVERSHOOT: target %d poked to %d -> %s ... final %d'
          % (ov['target'], ov['poked_to'], ov['trace'][:12], ov['final']))
    for fz in f['freeze']:
        print('FREEZE armed=%s: %d frames frozen, X while frozen %s (constant %s), '
              '%d distinct X after the thaw; freeze %d -> %d'
              % (fz['armed'], fz['frames_frozen'], fz['x_while_frozen'],
                 fz['constant_while_frozen'], len(fz['x_after_thaw']),
                 fz['freeze_first'], fz['freeze_last']))
    cl = f['clip']
    print('THE BAND walks: %s' % [w['operand'] for w in cl['band_walk']])
    for t in cl['tables']:
        sk = [x['y'] for x in t['row'] if x['skip']]
        print('   base $%02X ceil $%02X -> SKIPPED Ys $%02X..$%02X (%d of %d sampled)'
              % (t['base'], t['ceil'], min(sk), max(sk), len(sk), len(t['row'])))


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
