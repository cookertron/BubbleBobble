"""$AA60 + $B028 -- the entity UPDATE pass and the shared enemy walker.

The second half of the odd ISR branch.  $AA60 walks ($AA57) slots; for each it
reads that slot's WAKE-UP DELAY from $A891 (built by the spawner, tools/spawn.py)
and, while the delay is non-zero, ticks it and RETURNS -- the slot is asleep.
The two player slots and any slot whose (IY+9) is $FF are exempt.  An awake slot
is dispatched through the handler the spawner wrote into $B54E+2j, and all eight
enemy handlers are thin wrappers around the SHARED WALKER $B028.

$B028 per frame:
    ($B611) = ($B610)                    the step, 2 px
    ($B60F) = $16, doubled to $2C when (IY+7) bit 2 is set (ANGRY: $B69A or $90CF)
    (IY+8) the PAUSE timer: non-zero -> tick it; at 0 set (IY+9) = 1 (a hop);
           at 11 and at 5 FLIP the facing (IY+7 bit 0)
    (IY+9) non-zero -> the ballistic branch $B0F7
    otherwise: INC (IY+4), probe at (X, Y+$11) via $B47B, and
         bit1 of the result (solid at body level)  -> $B079 fall
         bit0 (solid underfoot)                    -> $B09B move
         neither                                   -> $B079 fall
    $B079 is (IY+9) = 0; (IY+6) = (Y + 2) AND $FE

$B47B: $AED1 makes the colour-shadow address for (E = X, D = Y); OR together 2
cells (or 3 when X & 6) at that row and 2-3 one char row ABOVE it, test bit $20
in each, and return them in B as bit1 = upper, bit0 = foot.

This tool captures the machine's per-frame enemy table so the transliteration can
be diffed against it frame for frame.

Usage:  python tools/walker.py capture
        python tools/walker.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IYh, IYl
import portconfig as pc

ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
TABLE, STRIDE, SLOTS = 0xFD80, 10, 12
COUNT_A = 0xAA57          # the number of slots a sweep visits
FIXTURE = 'build/walker_fixture.json'
BRANCH_BYTE = 0x8DC4
# the globals the walk reads and writes
GLOBALS = {'AA57': 0xAA57, 'AA65': 0xAA65, 'B54B': 0xB54B, 'B57C': 0xB57C,
           'B60F': 0xB60F, 'B610': 0xB610, 'B611': 0xB611,
           'B612': 0xB612, 'B613': 0xB613, 'FEC6': 0xFEC6, 'A3B2': 0xA3B2}
SCENES = [('round1_48', 120), ('hurryup', 60), ('elwater', 60)]


SP0 = [0]                 # the resting stack pointer of the state new() loaded


def new(state):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{state}: not the 48K branch (TRAPS #28/#36)')
    SP0[0] = h.sim.registers[12]
    return h, m


# The CP $2A that follows each LD A,R.  There are TWO, and trapping only the
# first records `draws: []` for every type-6 call while the machine drew -- the
# engine would then throw UNEXPECTED DRAW the moment type 6 is wired.
#   $B0D5  inside the shared walker, gates the 12-frame wind-up
#   $B008  type 6's own, straight-line after its CALL $B028 returns; flips the
#          facing, and the sprite two instructions later uses the FLIPPED value
RNG_TRAP = {0xB0D7: 0xB0D5, 0xB00A: 0xB008}
HESIT = 0xB0D7          # kept for readers; use RNG_TRAP for new code


def draw_at(h, pc_now):
    """record the draw whose CP we have just stopped on"""
    iy = (h.regs[IYh] << 8) | h.regs[IYl]   # 10 is the HIGH byte (harness.py:95)
    return {'site': RNG_TRAP[pc_now], 'tag': (iy - TABLE) // STRIDE,
            'A': h.regs[0] & 0x7F}


def frame(h):
    """one [main loop][ISR], collecting the $B0D5 hesitation draws the walker
       makes.  The port substitutes for LD A,R (docs/RNG.md), so the gate has to
       be fed the machine's own draws or the two diverge on the 1-in-128."""
    h.run_until((ISR_IN,), limit=10 ** 7, stride=1)
    h.step(1)
    draws = []
    while True:
        h.run_until(tuple(RNG_TRAP) + (ISR_OUT,), limit=10 ** 7, stride=1)
        if h.regs[PC] not in RNG_TRAP:
            break
        draws.append(draw_at(h, h.regs[PC]))
        h.step(1)
    h.step(1)
    return draws


def snap(m):
    return {
        'table': [m[TABLE + i] for i in range(SLOTS * STRIDE)],
        'delays': [m[0xA891 + i] for i in range(16)],
        'behav': [m[0xB54E + i] for i in range(0x24)],
        'cursor': m[0xB54C] | (m[0xB54D] << 8),
        'g': {k: m[a] for k, a in GLOBALS.items()},
    }


def capture():
    scenes = []
    # ...plus a FRESHLY SPAWNED round.  Every shipped state is far enough into
    # its round that all its enemies are awake and the $A891 delays never move,
    # so the asleep path is invisible there (TRAPS #37).  Spawning round 4 -- the
    # first with seven enemies -- puts the whole wake-up staircase on show.
    # Rounds 40 and 60 are here because they are the only ones that spawn
    # types 6 and 7.  The census over build/spawn_fixture.json puts type 6 in
    # rounds 40/42/43/44/47/48/65/66/68/73 and type 7 in 60/61/62/63/64/67/
    # 76/77/78, and neither appears in round 4 or 10 -- so without these the
    # frame gate gives both types exactly zero coverage, while its held-out
    # count quietly drops to zero and the pass count rises.
    for round_no in (4, 10, 40, 60):
        h, m = new('round1_48')
        m[0x8609] = round_no
        m[0x73AF] = 0
        h.call(0x727B)
        rows = [snap(m)]
        for _ in range(120):
            d = frame(h)
            r = snap(m); r['draws'] = d
            rows.append(r)
        scenes.append({'state': f'spawned_round{round_no}', 'frames': 120,
                       'colour': base64.b64encode(bytes(m[0xF800:0xF800 + 0x300])).decode(),
                       'rows': rows})
        woke = sum(1 for i in range(8) if rows[0]['delays'][i] != rows[-1]['delays'][i])
        print(f'  spawned_round{round_no}: 120 frames, {woke} delay bytes ticked')
    # ...and a scene that forces a WALL TURN.  Nothing in the shipped states walks
    # an enemy into a side border within the capture window, so $B1DC / $B22D --
    # the only paths that flip a facing without the pause timer -- would go
    # untested (TRAPS #37).  Two type-0 enemies on the bottom floor, one walking
    # at each border.
    h, m = new('round1_48')
    for k, (x, face) in enumerate(((216, 1), (32, 0))):
        b = TABLE + STRIDE * (2 + k)
        m[b + 0], m[b + 1] = (0x80, 0x5B) if face else (0x00, 0xC1)
        m[b + 2], m[b + 3] = 0, 0
        m[b + 4] = 0x40 + k
        m[b + 5], m[b + 6] = x, 168
        m[b + 7] = 0x80 | face
        m[b + 8] = m[b + 9] = 0
    for k in (4, 5, 6, 7, 8):                       # quiet the rest
        m[TABLE + STRIDE * k + 7] &= 0x7F
    m[COUNT_A] = 4
    for i in range(16):
        m[0xA891 + i] = 0
    rows = [snap(m)]
    for _ in range(90):
        d = frame(h)
        r = snap(m); r['draws'] = d
        rows.append(r)
    scenes.append({'state': 'wall_turn', 'frames': 90,
                   'colour': base64.b64encode(bytes(m[0xF800:0xF800 + 0x300])).decode(),
                   'rows': rows})
    fl = sum(1 for k in (2, 3)
             if (rows[0]['table'][STRIDE * k + 7] & 1) != (rows[-1]['table'][STRIDE * k + 7] & 1))
    print(f'  wall_turn: 90 frames, {fl} of 2 enemies ended facing the other way')

    # ...and one scene that puts enemies into the STATES the shipped scenes never
    # reach: a pause already running (its facing flips at 11 and 5, and it hops at
    # 0), an ANGRY one (doubled threshold, handler run twice), and four parked
    # outside the bounds the per-slot tail $AB0C keeps.  Seeding these is legal --
    # the machine reaches every one of them -- and without it fifteen walker
    # branches have no scene at all (TRAPS #37).
    h, m = new('round1_48')
    # the anim counter matters: the movement divider only DISCRIMINATES between
    # the normal threshold (22) and the angry one (44) when it sits between them,
    # and an odd X is the only thing that shows the tail forcing X even.
    setup = [(2, 100, 168, 0x81, 13, 0x32), (3, 140, 168, 0x85, 0, 30),
             (4, 9, 168, 0x80, 0, 0x34), (5, 250, 168, 0x81, 0, 0x35),
             (6, 120, 0xCA, 0x81, 0, 0x36), (7, 161, 5, 0x81, 0, 0x37)]   # 161: ODD and IN RANGE, so the tail's
             # AND $FE shows rather than being masked by the $10 clamp
    for (k, x, y, f7, t8, t4) in setup:
        b = TABLE + STRIDE * k
        m[b + 0], m[b + 1] = 0x00, 0xC1
        m[b + 2], m[b + 3] = 0, 0
        m[b + 4] = t4
        m[b + 5], m[b + 6] = x, y
        m[b + 7] = f7
        m[b + 8], m[b + 9] = t8, 0
        m[0xB552 + 2 * (k - 2)] = 0x31          # every one a type-0 walker
        m[0xB552 + 2 * (k - 2) + 1] = 0xAF
    for k in (8, 9, 10, 11):
        m[TABLE + STRIDE * k + 7] &= 0x7F
    m[COUNT_A] = 8
    for i in range(16):
        m[0xA891 + i] = 0
    rows = [snap(m)]
    for _ in range(60):
        d = frame(h)
        r = snap(m); r['draws'] = d
        rows.append(r)
    scenes.append({'state': 'walker_states', 'frames': 60,
                   'colour': base64.b64encode(bytes(m[0xF800:0xF800 + 0x300])).decode(),
                   'rows': rows})
    print(f'  walker_states: 60 frames, 6 enemies in states the shipped scenes never reach')

    for state, n in SCENES:
        h, m = new(state)
        rows = [snap(m)]
        for _ in range(n):
            d = frame(h)
            r = snap(m); r['draws'] = d
            rows.append(r)
        # the clean platform layer the probe reads, and the colour shadow it is in
        scenes.append({
            'state': state, 'frames': n,
            'colour': base64.b64encode(bytes(m[0xF800:0xF800 + 0x300])).decode(),
            'rows': rows,
        })
        live = [k for k in range(SLOTS) if rows[0]['table'][STRIDE * k + 7] & 0x80]
        moved = sum(1 for k in live
                    if rows[0]['table'][STRIDE * k + 5] != rows[-1]['table'][STRIDE * k + 5]
                    or rows[0]['table'][STRIDE * k + 6] != rows[-1]['table'][STRIDE * k + 6])
        print(f'  {state}: {n} frames, {len(live)} live slots, {moved} of them moved')
    fx = {'note': __doc__.strip().split('\n\n')[1].replace('\n', ' '),
          'globals': GLOBALS, 'table_at': TABLE, 'stride': STRIDE,
          'delay_at': 0xA891, 'scenes': scenes, 'calls': capture_calls(), 'synth': capture_synth(),
          'handlers': capture_handlers(), 'arc': capture_arc(),
          'fly': capture_fly(), 't4': capture_t4(), 'capesc': capture_capesc()}
    json.dump(fx, open(FIXTURE, 'w'), indent=1)
    print(f'wrote {FIXTURE}: {len(scenes)} scenes, '
          f'{sum(len(s["rows"]) for s in scenes)} frames')


# ---------------------------------------------------------------- SP hygiene
# Harness.call pushes SENTINELS and NEVER RESTORES SP: the routine RETs to the
# first sentinel, so each call leaves SP 10 bytes lower than it found it (six
# sentinels pushed, one popped).  Over a long sweep that walks SP down through
# live data and finally below $4000, where the sentinel writes land in ROM and
# are dropped -- so run_until never sees a sentinel, the call burns the whole
# instruction limit, and every row after that is a silent "nothing happened".
# MEASURED on round1_48: SP rests at $96D7 and crosses $4000 at call 2223, which
# is exactly the row at which a 2560-case sweep went dead.  So pin it.
def arm_call(h, addr, slot, sp0):
    """point the machine at `addr` with IY = slot, from a FIXED stack pointer"""
    r = h.sim.registers
    sp = sp0
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[IYh], r[IYl] = slot >> 8, slot & 0xFF
    r[PC] = addr


# --------------------------------------------------------------- per-call
WALK = 0xB028
HESIT_CP = 0xB0D7          # the CP $2A right after $B0D5's LD A,R
SHADOW_LO, SHADOW_HI = 0xF800, 0xFC00     # the colour shadow AND the bytes just
                                          # past it, which a wrapped Y reaches
DUMMY_LO, DUMMY_HI = 0x7100, 0x7200       # around $712F, $AED1's dummy cell


def call_walk(h, slot, sp0=None):
    """$B028 once, catching the $B0D5 hesitation draws on the way through."""
    arm_call(h, WALK, slot, SP0[0] if sp0 is None else sp0)
    return run_to_sentinel(h)


def run_to_sentinel(h, force=None):
    """run to a sentinel, collecting every RNG draw on the way.

       `force` is an optional {site: value} that POKES R just before the CP, so a
       branch the machine takes one time in 128 can be exercised deliberately
       instead of waiting for it to happen.  Without it the taken side of both
       hesitations rests on where R happened to be -- across the whole fixture
       exactly ONE natural draw equalled $2A, and a case added anywhere earlier
       would move R and silently take it away."""
    draws = []
    for _ in range(64):
        # interrupts=False, as Harness.call does.  run_until DEFAULTS TO TRUE, so
        # a hand-rolled bracket that forgets it runs the whole IM2 ISR inside the
        # call it was meant to isolate -- which shows up as the render master's
        # fingerprints (+2/+3 written, bits 5-6 set) on the "walker" result.
        h.run_until(tuple(RNG_TRAP) + tuple(h.SENTINELS), limit=10 ** 6, stride=1,
                    interrupts=False)
        pc_now = h.regs[PC]
        if pc_now not in RNG_TRAP:
            break
        site = RNG_TRAP[pc_now]
        if force and site in force:
            # R is register 15; the CP re-reads A, so set A directly and let the
            # rest of the routine run on the machine exactly as it would have
            h.sim.registers[0] = force[site] & 0x7F
        draws.append(draw_at(h, pc_now))
        h.step(1)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('call did not reach a sentinel -- PC $%04X' % h.regs[PC])
    return draws


def walk_cases():
    """the sweep.  x, y, flags, anim(+4), pause(+8), player (px,py)"""
    out = []
    for x in (16, 17, 96, 97, 100, 101, 160, 161, 222, 223, 224, 248, 254):
        for y in (0, 3, 5, 6, 7, 8, 16, 40, 96, 97, 168, 169, 184, 190, 200, 210, 220):
            for f in (0x80, 0x81):
                out.append((x, y, f, 0x40, 0, 24, 168))
    # the divider, the angry doubling, the pause timer and the player's row
    for anim in (0, 10, 21, 22, 23, 30, 43, 44, 45, 0xFF):
        for f in (0x80, 0x81, 0x84, 0x85):
            for (px, py) in ((24, 40), (24, 168), (24, 200), (200, 96)):
                out.append((100, 168, f, anim, 0, px, py))
    for pause in (1, 2, 5, 6, 11, 12, 13, 20):
        for f in (0x80, 0x81):
            out.append((100, 168, f, 0x40, pause, 24, 168))
    return out


def capture_calls():
    h, m = new('round1_48')
    shadow = base64.b64encode(bytes(m[SHADOW_LO:SHADOW_HI])).decode()
    dummy = base64.b64encode(bytes(m[DUMMY_LO:DUMMY_HI])).decode()
    rows = []
    slot = TABLE + 2 * STRIDE
    for (x, y, f, anim, pause, px, py) in walk_cases():
        for i in range(STRIDE):
            m[slot + i] = 0
        m[slot + 0], m[slot + 1] = 0x00, 0xC1
        m[slot + 4] = anim
        m[slot + 5], m[slot + 6] = x, y
        m[slot + 7] = f
        m[slot + 8] = pause
        m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
        m[0xB612], m[0xB613] = (px + 8) & 0xFF, py
        m[0xB088] = 0
        before = [m[slot + i] for i in range(STRIDE)]
        g0 = {'B60F': m[0xB60F], 'B610': m[0xB610], 'B611': m[0xB611],
              'B612': m[0xB612], 'B613': m[0xB613], 'B088': m[0xB088]}
        draws = call_walk(h, slot)
        rows.append({'x': x, 'y': y, 'f': f, 'anim': anim, 'pause': pause,
                     'before': before, 'g': g0, 'draws': draws,
                     'after': [m[slot + i] for i in range(STRIDE)],
                     'gafter': {'B60F': m[0xB60F], 'B611': m[0xB611]}})
    return {'note': ('$B028 called DIRECTLY, once per case, over a sweep that includes the '
                     'corners a running game never reaches: an enemy above the HUD where $AED1 '
                     'early-outs, odd and page-edge X, a Y near the bottom wrap, both facings, '
                     'angry and not, and an anim counter either side of the movement divider.'),
            'shadow_lo': SHADOW_LO, 'shadow_b64': shadow,
            'dummy_lo': DUMMY_LO, 'dummy_b64': dummy,
            'rows': rows}


# ------------------------------------------------------- the SYNTHETIC world
# Two things the machine does that NO captured scene reaches, so the shadow and
# the dummy page are BUILT rather than sampled.
#
# (1) THE DUMMY CELL.  Above the HUD ($AED1 with D < $18) the routine does not
#     compute a cell at all: $AED7 LD HL,$712F / XOR A / RET.  The A = 0 is a Z
#     flag meaning "not solid", and only the WALL test reads it.  The floor
#     probe $B47B and the ledge look-ahead IGNORE Z and dereference HL, so they
#     read $712E-$7131 (foot, after INC L / INC L or DEC L) and $710F-$7111
#     (the row above, HL + $FFE0).  Those are LIVE BYTES, not code: the boot
#     image has $712F = $E4 with bit 5 SET, while round1_48 has $00 there -- so
#     the sampled sweep cannot tell "the probe returns nothing" from "the probe
#     reads the dummy", because in that state both answer FALL.  Poked, it can.
#
# (2) THE LEDGE -> HOP LAUNCH ($B20F/$B25E) and the EIGHT-BIT look-ahead.  Both
#     need an enemy standing on a platform EDGE, and the second needs its foot
#     cell at low byte $00 or $FF so INC L / DEC L wraps inside the page instead
#     of crossing into the next one.  The sampled sweep launched 0 hops in 618
#     cases.  Here the platform is one poked byte and the ledge is the absence
#     of the next, with the cell a SIXTEEN-bit walk would have reached poked to
#     the OPPOSITE value so the two cannot agree by accident.
SYN_SHADOW_LO, SYN_SHADOW_HI = 0xF800, 0xFC00
SYN_DUMMY_LO, SYN_DUMMY_HI = 0x70C0, 0x7140     # three char rows around $712F
SOLID = 0x20


def cell(x, y):
    """$AED1, dummy included."""
    return 0x712F if y < 0x18 else 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)


def stand(x, y, right, look_solid):
    """the cells that put an enemy ON a floor at (x, y) with its body clear and
       the cell its look-ahead reaches either solid or clear"""
    a = cell(x, (y + 0x11) & 0xFF)
    c = {a: SOLID}
    d = 2 if right else -1
    look = (a & 0xFF00) | ((a + d) & 0xFF)          # INC L / INC L, or DEC L
    look16 = (a + d) & 0xFFFF
    c[look] = SOLID if look_solid else 0
    if look16 != look:                              # the page wrapped
        c[look16] = 0 if look_solid else SOLID      # pin the 16-bit answer OPPOSITE
    return c


def synth_cases():
    """(label, x, y, right, anim, py, cells) -- cells are ABSOLUTE addresses."""
    out = []
    # ---- the ledge, on a built platform.  x = 248 puts the foot cell at low
    #      byte $FF (row 23, column 31) and x = 0 at $00 (row 16, column 0), so
    #      INC L and DEC L wrap; 96 and 100 differ in X & 6, which is what picks
    #      2 probe cells or 3.  py = y makes the player's row the enemy's (hop);
    #      py = 240 puts the player below it (step anyway).
    for (x, y) in ((96, 168), (100, 168), (248, 168), (0, 112), (254, 112)):
        for right in (True, False):
            for look_solid in (False, True):
                for py in (y, 240):
                    out.append(('ledge', x, y, right, 0x40, py,
                                stand(x, y, right, look_solid), 0, 0x80))
    # ---- THE PATCH BYTES.  Types 6 and 7 write $C9 (RET) over $B20D/$B25D, and
    #      7 also over $B088, around their call to the walker.  $B20D/$B25D sit
    #      inside the ledge decision AFTER $B1FF/$B24F have PUSHed the STEP's
    #      address, so the RET lands on the step: a patched walker walks straight
    #      off a ledge instead of hopping.  $B088 is read as DATA by $B09B and
    #      $B0ED -- non-zero means always step, never pause.  No captured round
    #      has either set, because only these two handlers set them.
    for (x, y) in ((96, 168), (100, 168), (248, 168), (0, 112)):
        for right in (True, False):
            for look_solid in (False, True):
                for py in (y, 240):
                    for patch in (1, 2, 3, 4, 7):
                        out.append(('patched', x, y, right, 0x40, py,
                                    stand(x, y, right, look_solid), patch, 0x80))
    # ---- $B088 ON THE FALL PATH.  $B087 is LD A,n and $B088 is its OPERAND, so
    #      a patched FALLER turns to face the player ($B08B-$B09A) -- a third
    #      reader that no absolute-operand scan can find.  The patched rows above
    #      all stand on a floor, so 0 of them fall and the whole arm was
    #      unreachable.  Here the floor is REMOVED so the probe returns fall, and
    #      the tracked player sits either side of the enemy with both facings.
    for x in (96, 100):
        for right in (True, False):
            for px in (0x20, x - 1, x, x + 1, 0xF0):
                for patch in (0, 4):
                    out.append(('patchfall', x, 168, right, 0x40, 240, {}, patch, px))
    # ---- $B088 where it MATTERS: anim BELOW the divider AND a floor in the
    #      three-row search window, so unpatched ends in a 12-frame wind-up and
    #      patched steps.  Anywhere else the divider would have passed anyway
    #      and the two answers coincide.
    for x in (96, 100):
        for right in (True, False):
            for py in (40, 240):
                for patch in (0, 4):
                    c = stand(x, 168, right, True)
                    c[cell(x, (168 - 8) & 0xFF)] = SOLID
                    out.append(('divider', x, 168, right, 0, py, c, patch, 0x80))
    # ---- the dummy cell.  y = 0/2/6 put BOTH the foot probe (Y+$11) and the
    #      wall test (Y+$0F) above the HUD; y = 8 puts only the wall test there,
    #      so the foot is a real cell and the two paths are mixed in one call.
    for y in (0, 2, 6, 8):
        for x in (96, 100):                         # X & 6 == 0 -> 2 cells, else 3
            for right in (True, False):
                for (f31, f2e, up) in ((0, 0, 0), (SOLID, 0, 0), (0, SOLID, 0),
                                       (SOLID, SOLID, 0), (0, 0, SOLID)):
                    c = {0x712F: SOLID, 0x7130: 0, 0x7131: f31, 0x712E: f2e,
                         0x710F: up, 0x7110: 0, 0x7111: 0}
                    if y + 0x11 >= 0x18:            # a real foot cell as well
                        c.update(stand(x, y, right, False))
                    out.append(('dummy', x, y, right, 0x40, y, c, 0, 0x80))
    # ---- the three-row floor search reached from above the HUD: the divider
    #      FAILS (anim = 0), and (IY+6) - 8 WRAPS, so the search starts at row
    #      31 of the shadow rather than anywhere near the enemy.
    for y in (0, 4):
        for x in (96, 100):
            for r31 in (0, SOLID):
                out.append(('wrapsearch', x, y, True, 0, y,
                            {0x712F: SOLID, 0x7130: 0, 0x7131: 0, 0x712E: 0,
                             0x710F: 0, 0x7110: 0, 0x7111: 0,
                             0xF800 + 31 * 32 + (x >> 3): r31}, 0, 0x80))
    # ---- ODD Y, where Y + $10 and Y + $11 land in DIFFERENT character rows.
    #      They agree for every even Y (both stay inside one row), so the whole
    #      sampled sweep cannot tell the two apart -- and the per-slot tail
    #      forces X even but never Y, while the ballistic hop moves Y by odd
    #      amounts.  Here the two candidate rows are poked to OPPOSITE values.
    for y in (167, 175, 103):
        for x in (96, 100):
            for right in (True, False):
                for solid in (True, False):
                    a11 = cell(x, (y + 0x11) & 0xFF)
                    a10 = cell(x, (y + 0x10) & 0xFF)
                    out.append(('oddy', x, y, right, 0x40, 240,
                                {a11: SOLID if solid else 0,
                                 a10: 0 if solid else SOLID}, 0, 0x80))
    return out


def capture_synth():
    h, m = new('round1_48')
    for a in range(SYN_SHADOW_LO, SYN_SHADOW_HI):
        m[a] = 0
    for a in range(SYN_DUMMY_LO, SYN_DUMMY_HI):
        m[a] = 0
    rows = []
    slot = TABLE + 2 * STRIDE
    for (label, x, y, right, anim, py, cells, patch, px) in synth_cases():
        for a in range(SYN_SHADOW_LO, SYN_SHADOW_HI):
            m[a] = 0
        for a in range(SYN_DUMMY_LO, SYN_DUMMY_HI):
            m[a] = 0
        for (a, v) in cells.items():
            m[a] = v
        # ONE BIT PER BYTE -- bit 0 $B20D, bit 1 $B25D, bit 2 $B088 -- so a model
        # that swapped the two ledge bytes between the facings is visible.  The
        # real handlers use 3 (type 6: both ledge bytes) and 7 (type 7: all).
        m[0xB20D] = 0xC9 if (patch & 1) else 0x00
        m[0xB25D] = 0xC9 if (patch & 2) else 0x00
        m[0xB088] = 0xC9 if (patch & 4) else 0x00
        for i in range(STRIDE):
            m[slot + i] = 0
        m[slot + 0], m[slot + 1] = 0x00, 0xC1
        m[slot + 4] = anim
        m[slot + 5], m[slot + 6] = x, y
        m[slot + 7] = 0x81 if right else 0x80
        m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
        m[0xB612], m[0xB613] = px, py
        before = [m[slot + i] for i in range(STRIDE)]
        g0 = {'B60F': m[0xB60F], 'B610': m[0xB610], 'B611': m[0xB611],
              'B612': m[0xB612], 'B613': m[0xB613], 'B088': m[0xB088],
              'B20D': m[0xB20D], 'B25D': m[0xB25D]}
        draws = call_walk(h, slot)
        rows.append({'label': label, 'x': x, 'y': y, 'right': right, 'anim': anim,
                     'py': py, 'patch': patch, 'px': px,
                     'cells': {str(a): v for a, v in sorted(cells.items())},
                     'before': before, 'g': g0, 'draws': draws,
                     'after': [m[slot + i] for i in range(STRIDE)],
                     'gafter': {'B60F': m[0xB60F], 'B611': m[0xB611]}})
    for a in (0xB088, 0xB20D, 0xB25D):
        m[a] = 0x00
    return {'note': ('$B028 over a BUILT world: the colour shadow and the $712F dummy page '
                     'cleared and then poked cell by cell, so the ledge -> hop launch, the '
                     'eight-bit INC L / DEC L look-ahead and the above-the-HUD dummy reads are '
                     'reachable. No captured round puts an enemy where these paths run.'),
            'shadow_lo': SYN_SHADOW_LO, 'shadow_hi': SYN_SHADOW_HI,
            'dummy_lo': SYN_DUMMY_LO, 'dummy_hi': SYN_DUMMY_HI,
            'rows': rows}


# ------------------------------------------------------------- the handlers
# $AA60 dispatches by POINTER, and the eight enemy handlers are not eight copies
# of one wrapper: type 0 calls the walker unconditionally, types 1 and 5 gate it
# on BIT 1,(IY+7), and the other five rescale the step or patch the walker's own
# code.  Whether type 0 really is ungated cannot be seen in any capture, because
# the spawner clears bit 1 ($7455 RES 1) and nothing that runs yet sets it.  So
# the bit is SET here and the handler called directly.  The same sweep pins the
# whole (type, facing) sprite table -- $AF34 BIT 0,(IY+7) and the +$160 mirror
# at $AF2C -- against the machine rather than against a reading of it.
HANDLERS = [0xAF31, 0xAF47, 0xAF95, 0xAFAF, 0xAF77, 0xAF5F, 0xAFF6, 0xAFC4]
# the bytes the handlers SELF-MODIFY, restored between cases
PATCHED = (0xB088, 0xB20D, 0xB25D)


# The four worlds a handler call has to be tried in.  In the FLOOR world -- the
# only one the first version used -- all three patch bytes are INERT: the floor
# ahead makes $B1FA jump to the step, so the block $B20D/$B25D live in is never
# entered; anim $40 clears the divider, so $B088's read at $B09B changes nothing;
# and the floor underfoot means no fall, so $B087 never matters.  Deleting all
# five patch installs from types 6 and 7 on the machine gives byte-identical
# results there -- which is exactly the TRAPS #37/#40 shape.
#   floor    a platform with floor ahead                 -- walks, nothing else
#   ledge    floor underfoot, NONE ahead, player level   -- reaches $B20D/$B25D
#   divider  anim below $16, floor in the search window  -- reaches $B088/$B09B
#   fall     no floor at all, player to one side         -- reaches $B088/$B087
HANDLER_WORLDS = ('floor', 'ledge', 'divider', 'fall')


def handler_world(m, name, x, y, right):
    """build the world; return the (anim, player Y, player X) that goes with it"""
    for a in range(SYN_SHADOW_LO, SYN_SHADOW_HI):
        m[a] = 0
    if name == 'floor':
        for (a, v) in stand(x, y, right, True).items():
            m[a] = v
        return 0x40, 240, 0x80
    if name == 'ledge':
        for (a, v) in stand(x, y, right, False).items():
            m[a] = v
        return 0x40, y, 0x80              # player on the enemy row -> hop
    if name == 'divider':
        for (a, v) in stand(x, y, right, True).items():
            m[a] = v
        m[cell(x, (y - 8) & 0xFF)] = SOLID
        return 0x00, 40, 0x80             # anim under $16, player ABOVE -> pause
    return 0x40, 240, 0xF0                # fall: nothing underfoot, player right


def capture_handlers():
    h, m = new('round1_48')
    for a in range(SYN_DUMMY_LO, SYN_DUMMY_HI):
        m[a] = 0
    rows = []
    shadows = {}
    slot = TABLE + 2 * STRIDE
    for (t, addr) in enumerate(HANDLERS):
      for world in HANDLER_WORLDS:
        for bit1 in (0, 2):
            for face in (0, 1):
                anim, py, px = handler_world(m, world, 96, 168, face == 1)
                key = '%s:%d' % (world, face)
                if key not in shadows:
                    shadows[key] = base64.b64encode(
                        bytes(m[SYN_SHADOW_LO:SYN_SHADOW_LO + 0x400])).decode()
                for i in range(STRIDE):
                    m[slot + i] = 0
                m[slot + 4] = anim
                m[slot + 5], m[slot + 6] = 96, 168
                m[slot + 7] = 0x80 | face | bit1
                for a in PATCHED:
                    m[a] = 0x00
                m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
                m[0xB612], m[0xB613] = px, py
                before = [m[slot + i] for i in range(STRIDE)]
                prng0 = [m[0xFE86], m[0xFE87]]
                arm_call(h, addr, slot, SP0[0])
                draws = run_to_sentinel(h)
                rows.append({'type': t, 'handler': addr, 'bit1': bit1, 'face': face,
                             'world': world, 'forced': False, 'key': key,
                             'g': {'B612': px, 'B613': py},
                             'before': before, 'draws': draws,
                             'after': [m[slot + i] for i in range(STRIDE)],
                             'patched': {hex(a): m[a] for a in PATCHED},
                         'prng': prng0, 'prng_after': [m[0xFE86], m[0xFE87]],
                             'prng': prng0, 'prng_after': [m[0xFE86], m[0xFE87]],
                             'gafter': {'B60F': m[0xB60F], 'B610': m[0xB610],
                                        'B611': m[0xB611]}})
    # ...and a STEPS pass.  Every row above enters with ($B610) = ($B611) = 2,
    # which cannot separate "the doubling is restored" from "it was never
    # doubled", nor see that $AFCA's SLA on $B611 is DEAD -- $B028's first act
    # overwrites it, so $B611 comes back equal to $B610's ENTRY value and not to
    # its own.  Nor can it see that the SLA/SRL round trip loses BIT 7.  The
    # game only ever writes 2 ($9874 is the sole writer, measured over 600
    # frames), so these entry values do not occur in play -- but the machine
    # answers for them, and they are the only thing that pins the arithmetic.
    for (t, addr) in enumerate(HANDLERS):
        for (e610, e611) in ((2, 2), (3, 7), (1, 0), (5, 5), (0x80, 5), (0xC0, 9)):
            anim, py, px = handler_world(m, 'floor', 96, 168, True)
            key = 'floor:1'
            for i in range(STRIDE):
                m[slot + i] = 0
            m[slot + 4] = anim
            m[slot + 5], m[slot + 6] = 96, 168
            m[slot + 7] = 0x81
            for a in PATCHED:
                m[a] = 0x00
            m[0xB60F] = 0x16
            m[0xB610], m[0xB611] = e610, e611
            m[0xB612], m[0xB613] = px, py
            before = [m[slot + i] for i in range(STRIDE)]
            prng0 = [m[0xFE86], m[0xFE87]]
            arm_call(h, addr, slot, SP0[0])
            draws = run_to_sentinel(h)
            rows.append({'type': t, 'handler': addr, 'bit1': 0, 'face': 1,
                         'world': 'floor', 'forced': False, 'key': key,
                         'g': {'B612': px, 'B613': py, 'B610': e610, 'B611': e611},
                         'before': before, 'draws': draws,
                         'after': [m[slot + i] for i in range(STRIDE)],
                         'patched': {hex(a): m[a] for a in PATCHED},
                         'prng': prng0, 'prng_after': [m[0xFE86], m[0xFE87]],
                         'gafter': {'B60F': m[0xB60F], 'B610': m[0xB610],
                                    'B611': m[0xB611]}})
    m[0xB610] = m[0xB611] = 2
    # ...and the whole sweep again with R FORCED to $2A at BOTH sites, so the
    # taken side of each 1-in-128 is exercised on purpose instead of waited for.
    # Across the entire fixture exactly ONE natural draw equalled $2A, and it
    # would vanish the moment any earlier case moved R.
    for (t, addr) in enumerate(HANDLERS):
      for world in HANDLER_WORLDS:
        for face in (0, 1):
            anim, py, px = handler_world(m, world, 96, 168, face == 1)
            key = '%s:%d' % (world, face)
            if key not in shadows:
                shadows[key] = base64.b64encode(
                    bytes(m[SYN_SHADOW_LO:SYN_SHADOW_LO + 0x400])).decode()
            for i in range(STRIDE):
                m[slot + i] = 0
            m[slot + 4] = anim
            m[slot + 5], m[slot + 6] = 96, 168
            m[slot + 7] = 0x80 | face
            for a in PATCHED:
                m[a] = 0x00
            m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
            m[0xB612], m[0xB613] = px, py
            before = [m[slot + i] for i in range(STRIDE)]
            prng0 = [m[0xFE86], m[0xFE87]]
            arm_call(h, addr, slot, SP0[0])
            draws = run_to_sentinel(h, force={0xB0D5: 0x2A, 0xB008: 0x2A})
            rows.append({'type': t, 'handler': addr, 'bit1': 0, 'face': face,
                         'world': world, 'forced': True, 'key': key,
                         'g': {'B612': px, 'B613': py},
                         'before': before, 'draws': draws,
                         'after': [m[slot + i] for i in range(STRIDE)],
                         'patched': {hex(a): m[a] for a in PATCHED},
                         'prng': prng0, 'prng_after': [m[0xFE86], m[0xFE87]],
                         'gafter': {'B60F': m[0xB60F], 'B610': m[0xB610],
                                    'B611': m[0xB611]}})
    for a in PATCHED:
        m[a] = 0x00
    return {'note': ('each of the eight handlers at $B54E called DIRECTLY, on a built platform '
                     'with floor ahead so a walk steps and a gated one does not, with BIT 1 of '
                     'the flags (the walk gate) and BIT 0 (the facing) both ways. The spawner '
                     'clears bit 1, so no capture of a running round can tell the unconditional '
                     'CALL $B028 of type 0 from the CALL z of types 1 and 5.'),
            'handlers': HANDLERS, 'patched_at': list(PATCHED),
            'worlds': list(HANDLER_WORLDS), 'stand_x': 96, 'stand_y': 168,
            'shadows': shadows,
            'shadow_lo': SYN_SHADOW_LO, 'shadow_hi': SYN_SHADOW_HI,
            'dummy_lo': SYN_DUMMY_LO, 'dummy_hi': SYN_DUMMY_HI,
            'cells': {str(a): v for a, v in sorted(stand(96, 168, True, True).items())},
            'cells_left': {str(a): v for a, v in sorted(stand(96, 168, False, True).items())},
            'rows': rows}


# ------------------------------------------------------- the BALLISTIC HOP
# $B0F7, reached from $B05E whenever (IY+9) is non-zero.  (IY+9) is BOTH the
# state and the CURSOR: bits 0-6 minus one index a 32-byte arc table, bit 7
# picks WHICH table, and the whole byte (bit 7 included) is compared against
# $11 to decide whether to look for a landing at all.
#
#   $B59D  the BIG arc   -4 -4 -4 -4 -4 -3 ... +4 +4, peak 40 px up at frame 14
#          taken when bit 7 is CLEAR, i.e. the hop the PAUSE wind-up starts
#          ($B046 sets (IY+9) = 1 when the timer runs out)
#   $B5BD  the SMALL arc -2 -2 -1 -1 ... +2 +2, peak 14 px up
#          taken when bit 7 is SET, i.e. the LEDGE hop ($B20F/$B25E set $81)
#
# Both are 32 bytes and both sum to ZERO, so a hop that runs its course lands at
# the height it left.  They are NOT runtime-built, despite differing from the
# boot image at $B59D: the whole page is RELOCATED -- live $B000-$BFFF is boot
# $F000-$FFFF (4045 of 4096 bytes identical, the rest being buffers and the
# self-modified operands), and the loader hands over at $F5BC, inside it.
ARC_POS, ARC_NEG = 0xB59D, 0xB5BD     # bit 7 clear / bit 7 set
ARC_LEN = 32


def arc_cells(m, x, y, st, right, wall, floor, head, search=0):
    """the cells a hop in state `st` at (x, y) will actually touch"""
    c = {}
    step = 2
    if st & 0x80:                     # only the bit-7 arc moves horizontally
        if right:
            edge = (x + 15) & 0xFF
            dest = (edge + step) & 0xFF
            if (dest & 0xF8) != (edge & 0xF8):
                c[cell(dest, (y + 15) & 0xFF)] = SOLID if wall else 0
        elif (x & 7) - step < 0:
            c[cell((x - step) & 0xFF, (y + 15) & 0xFF)] = SOLID if wall else 0
    # the landing probe happens AFTER the horizontal move, at the new X
    nx = x
    if (st & 0x80) and not wall:
        nx = ((x + step) if right else (x - step)) & 0xFF
    dy = m[(ARC_NEG if st & 0x80 else ARC_POS) + ((st - 1) & 0x7F)]
    a = cell(nx, (dy + 15 + y) & 0xFF)
    if floor:
        c[a] = SOLID
    else:
        c.setdefault(a, 0)
    if head:
        c[(a - 32) & 0xFFFF] = SOLID
    else:
        c.setdefault((a - 32) & 0xFFFF, 0)
    # a floor inside the three-row search window $B0AC opens after a landing
    if search:
        c[cell(nx, (y - 8) & 0xFF)] = SOLID
    return c


def arc_cases():
    """(x, y, st, right, wall, floor, head, anim, search, py)"""
    out = []
    # the cursor values that matter: the first and last index of each arc, and
    # BOTH sides of the $B16B CP $11 that decides whether to look for a landing
    STATES = (1, 2, 0x10, 0x11, 0x12, 0x1F, 0x20,
              0x81, 0x82, 0x90, 0x91, 0x9F, 0xA0)
    WORLDS = ((0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 0, 0), (1, 1, 0))
    for st in STATES:
        for (x, y) in ((96, 168), (100, 168), (102, 168), (0, 112), (248, 112),
                       (16, 40), (224, 200), (96, 8)):
            for right in (True, False):
                for (wall, floor, head) in WORLDS:
                    out.append((x, y, st, right, wall, floor, head, 0x40, 0, 240))
    # LANDING INTO THE MOVE.  $B192 is a JP to $B09B, the TOP of the move
    # decision -- not to the step -- so a landing with the anim counter below
    # the threshold runs the three-row floor search, reaches the 1/128 $B0D5
    # hesitation and can end in a PAUSE rather than a step.  Without a floor in
    # that window every path still ends at the step, and "landed into the move"
    # is indistinguishable from "landed into the step".
    for st in (0x11, 0x20, 0x81, 0xA0):
        for x in (96, 100):
            for right in (True, False):
                for anim in (0, 0x10, 0x15, 0x16):
                    for (search, py) in ((0, 240), (1, 240), (1, 40)):
                        out.append((x, 168, st, right, 0, 1, 0, anim, search, py))
    # ODD Y.  The fall path aligns Y to even ($B079 AND $FE) and so does the
    # landing ($B189), but the ARC does not: the big table steps by -3, -1, +1
    # and +3, so a hop in flight is the one thing that gives an enemy an odd Y
    # -- which is exactly where Y + $10 and Y + $11 stop agreeing.
    for y in (167, 169):
        for st in (1, 0x11, 0x81, 0x91):
            for x in (96, 100):
                for right in (True, False):
                    for floor in (0, 1):
                        out.append((x, y, st, right, 0, floor, 0, 0x40, 0, 240))
    return out


def capture_arc():
    h, m = new('round1_48')
    pos = base64.b64encode(bytes(m[ARC_POS:ARC_POS + ARC_LEN])).decode()
    neg = base64.b64encode(bytes(m[ARC_NEG:ARC_NEG + ARC_LEN])).decode()
    rows = []
    slot = TABLE + 2 * STRIDE
    for (x, y, st, right, wall, floor, head, anim, search, py) in arc_cases():
        cells = arc_cells(m, x, y, st, right, wall, floor, head, search)
        for a in range(SYN_SHADOW_LO, SYN_SHADOW_HI):
            m[a] = 0
        for a in range(SYN_DUMMY_LO, SYN_DUMMY_HI):
            m[a] = 0
        for (a, v) in cells.items():
            m[a] = v
        for i in range(STRIDE):
            m[slot + i] = 0
        m[slot + 0], m[slot + 1] = 0x00, 0xC1
        m[slot + 4] = anim            # $40 is past the divider; 0 is not
        m[slot + 5], m[slot + 6] = x, y
        m[slot + 7] = 0x81 if right else 0x80
        m[slot + 8] = 0               # no pause: $B03E falls through to $B05A
        m[slot + 9] = st
        for a in (0xB088, 0xB20D, 0xB25D):
            m[a] = 0x00
        m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
        m[0xB612], m[0xB613] = 0x80, py
        before = [m[slot + i] for i in range(STRIDE)]
        draws = call_walk(h, slot)
        rows.append({'x': x, 'y': y, 'st': st, 'right': right, 'anim': anim,
                     'wall': wall, 'floor': floor, 'head': head, 'py': py, 'search': search,
                     'cells': {str(a): v for a, v in sorted(cells.items())},
                     'before': before, 'draws': draws,
                     'after': [m[slot + i] for i in range(STRIDE)],
                     'gafter': {'B60F': m[0xB60F], 'B611': m[0xB611]}})
    return {'note': ('$B028 entered with (IY+9) non-zero, so it routes to the ballistic branch '
                     '$B0F7, over a BUILT world: the cells the hop will touch -- the horizontal '
                     'wall test and the landing probe at the arc-displaced row -- are poked per '
                     'case, since no captured round has an enemy mid-hop anywhere useful.'),
            'arc_pos_at': ARC_POS, 'arc_pos_b64': pos,
            'arc_neg_at': ARC_NEG, 'arc_neg_b64': neg,
            'shadow_lo': SYN_SHADOW_LO, 'shadow_hi': SYN_SHADOW_HI,
            'dummy_lo': SYN_DUMMY_LO, 'dummy_hi': SYN_DUMMY_HI,
            'rows': rows}


# ------------------------------------------------------- the 2-D FLYER $B26F
# The mover types 2 and 3 use INSTEAD of the shared walker.  It is not a walker
# variant: no gravity, no floor-following, no player tracking, no hop.  It moves
# one step on X and one on Y per call and REVERSES on either axis when the
# leading edge of the step would enter a solid colour-shadow cell.
#
#   (IY+7) bit 0 = X direction (0 left, 1 right)   -- as everywhere
#   (IY+7) bit 1 = Y direction (0 up,   1 down)    -- REPURPOSED. Types 1 and 5
#                  use the same bit as their walk gate.
#
# $B26F copies X/Y/flags into the private scratch $B579/$B57A/$B57B, calls the
# VERTICAL dispatcher, re-stores Y from the entity (discarding that call's move
# but KEEPING any direction flip), calls the HORIZONTAL dispatcher, calls the
# vertical one again, then writes all three back.  The pre-call is what makes a
# vertical reversal cost no frame.
#
# The two probes are NOT the same shape and must not share a helper:
#   horizontal ($B2C3/$B302) walks +$20 -- one CHARACTER ROW down, 16-bit --
#       and takes a third cell when the SCRATCH Y ($B57A) AND 6 is non-zero;
#   vertical   ($B346/$B384) walks INC HL -- one CELL right, 16-bit, so column
#       31 carries into column 0 of the next row -- and takes a third cell when
#       the SCRATCH X ($B579) AND 6 is non-zero.
# Both call $AEDC, which is $AED1's body WITHOUT the CP $18 guard, so a flyer
# above the HUD computes a real (wrapped) cell rather than taking the $712F
# dummy.  Horizontal uses step $B610, VERTICAL uses $B611 -- which is why type
# 3's single SRL makes it 2 px across and 1 px down.
FLY = {2: 0xAF95, 3: 0xAFAF}
SCRATCH = (0xB579, 0xB57A, 0xB57B)


def fly_patterns():
    """Deterministic sparse worlds. Hand-built worlds only test the cells I
       thought of; these put solid cells where I did not choose them, so the
       probes meet configurations the model was not written against."""
    out = []
    for (name, fn) in (
            ('empty',  lambda r, c: False),
            ('full',   lambda r, c: True),
            ('sparse', lambda r, c: (r * 31 + c * 17) % 7 == 0),
            ('stripe', lambda r, c: (r * 5 + c * 3) % 11 < 2),
            ('dense',  lambda r, c: (r * 13 + c * 29) % 3 == 0)):
        b = bytearray(0x400)
        for r in range(32):
            for c in range(32):
                if fn(r, c):
                    b[r * 32 + c] = SOLID
        out.append((name, bytes(b)))
    return out


def fly_cases():
    """(pattern, x, y, flags, typ, b610)"""
    out = []
    # The offsets are the point.  The borrow gate is (coord AND 7) - step, so it
    # fires only for offsets below the step -- 0 and 1 for a 2 px axis, 0 for a
    # 1 px one.  An earlier sweep offered offsets {0,4,6,7} only, which left
    # `<= 0` and `AND 6` alive over all 2,560 rows: one firing value and three
    # far-away non-firing ones cannot separate them.  Offsets 1, 2, 3 and 5 are
    # ordinary in play ($AB0C forces X even, so X AND 7 cycles 0,2,4,6; type 3's
    # 1 px vertical step gives Y every offset including the odd ones).
    XS = (0, 1, 2, 3, 5, 7, 96, 97, 98, 99, 101, 102, 127, 128, 248, 254, 255)
    # $C6 and $C7 exist so the DOWN move lands in [$C8,$DC), the tail's middle
    # band -- the one branch edge the whole flyer never reached.  $AB0C leaves a
    # stored Y below $C8, and $C7 + 2 = $C9 is inside it, so it is reachable.
    YS = (0, 1, 2, 3, 5, 7, 16, 100, 101, 102, 168, 190, 198, 199,
          0xC8, 0xD0, 0xD9, 0xDA, 0xDB, 248)
    for pi in range(5):
        for x in XS:
            for y in YS:
                for f in (0x80, 0x81, 0x82, 0x83):
                    for typ in (2, 3):
                        out.append((pi, x, y, f, typ, 2))
    for pi in (2, 3, 4):
        for x in (0, 1, 2, 3, 5, 7, 96, 97, 99, 101, 248, 255):
            for y in (0, 1, 3, 5, 7, 100, 101, 103, 168, 248):
                for f in (0x80, 0x81, 0x82, 0x83):
                    for typ in (2, 3):
                        for b610 in (1, 3):
                            out.append((pi, x, y, f, typ, b610))
    return out


def capture_fly():
    h, m = new('round1_48')
    pats = fly_patterns()
    rows = []
    slot = TABLE + 2 * STRIDE
    for (pi, x, y, f, typ, b610) in fly_cases():
        m[SYN_SHADOW_LO:SYN_SHADOW_LO + 0x400] = pats[pi][1]
        for i in range(STRIDE):
            m[slot + i] = 0
        m[slot + 0], m[slot + 1] = 0x00, 0xC1
        m[slot + 4] = 0x40
        m[slot + 5], m[slot + 6] = x, y
        m[slot + 7] = f
        for a in SCRATCH:
            m[a] = 0
        for a in (0xB088, 0xB20D, 0xB25D):
            m[a] = 0x00
        m[0xB60F], m[0xB610], m[0xB611] = 0x16, b610, b610
        m[0xB612], m[0xB613] = 0x80, 240
        before = [m[slot + i] for i in range(STRIDE)]
        arm_call(h, FLY[typ], slot, SP0[0])
        h.run_until(tuple(h.SENTINELS), limit=10 ** 6, stride=1, interrupts=False)
        if h.regs[PC] not in h.SENTINELS:
            raise SystemExit('fly: no sentinel after p=%d x=%d y=%d f=%02X typ=%d -- PC $%04X'
                             % (pi, x, y, f, typ, h.regs[PC]))
        rows.append({'p': pi, 'x': x, 'y': y, 'f': f, 'typ': typ, 'b610': b610,
                     'before': before,
                     'after': [m[slot + i] for i in range(STRIDE)],
                     'scratch': [m[a] for a in SCRATCH],
                     'gafter': {'B610': m[0xB610], 'B611': m[0xB611]}})
    return {'note': ('$AF95 (type 2) and $AFAF (type 3) called DIRECTLY over five deterministic '
                     'worlds -- empty, full and three sparse patterns -- so the flyer probes meet '
                     'configurations that were not hand-picked to match a model. X and Y sweep '
                     'both page edges and both sides of a character-cell boundary; the flags sweep '
                     'all four (X direction, Y direction) combinations.'),
            'shadow_lo': SYN_SHADOW_LO,
            'patterns': [{'name': n, 'b64': base64.b64encode(b).decode()} for (n, b) in pats],
            'scratch_at': list(SCRATCH), 'handlers': FLY,
            'rows': rows}


# ------------------------------------------------------------------ TYPE 4
# $B3C5, the last handler, and it shares nothing with the other seven: its own
# probe, its own horizontal move, its own arc machinery, and the only enemy draw
# from the $FE85 LFSR rather than LD A,R.
#
# The cursor is (IY+8) -- the byte every other type uses as a PAUSE TIMER -- and
# it runs 0..$20 INCLUSIVE against a 32-byte table, so the last airborne frame
# reads ONE BYTE PAST the end.  For the bit-7-clear arc that is $B5DD + $20 =
# $B5FD, the first byte of P1's KEY TABLE, taken as a signed Y delta of -33.
# (IY+9) is only the state; its bit 7 picks $B5BD or $B5DD.
T4 = 0xAF77
ARC_TALL, ARC_SMALL = 0xB5DD, 0xB5BD
KEYTAB = 0xB5FD


def t4_cases():
    """(x, y, st, cur, anim, right, py, px, world, seed, entry)"""
    out = []
    # ---- $B3C5 called DIRECTLY, bypassing $AF77.  The wrapper's tail clamps Y
    #      at $BF, which MASKS $B3F0's own $C0 wrap in every case reachable
    #      through the handler -- a fall landing anywhere in [$C0,$C8) is sent to
    #      0 by the tail whatever $B3F0 did.  Only a direct call can see it.
    for y in (0xB8, 0xBA, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xC2, 0xC4, 0xC5, 0xC6):
        for world in ('air', 'floor'):
            for right in (True, False):
                out.append((96, y, 0, 0, 0x40, right, 240, 0x80, world, 0, 'B3C5'))
    # ---- a launch with the cursor ALREADY non-zero, so $B3F8's reset is visible
    for cur in (1, 0x10, 0x20, 0xFF):
        for right in (True, False):
            for py in (168, 240):
                out.append((96, 168, 0, cur, 0x40, right, py, 0x80, 'floor', 0, 'AF77'))
    # ---- a LANDING world: the cell the arc-displaced probe will read, with and
    #      without the row above it solid, so "floor below" and "nothing above"
    #      are separable.  The floor world pokes a different row entirely, so the
    #      head arm of $B457 was never exercised.
    for st in (0x81, 0x01):
        for cur in (0x11, 0x14, 0x18):
            for x in (96, 100):
                for right in (True, False):
                    for world in ('land', 'landhead'):
                        out.append((x, 168, st, cur, 0x40, right, 240, 0x80, world, 0, 'AF77'))
    # GROUNDED: the three outcomes of the $B3D9 probe, and the $B3F0 bottom wrap
    for y in (168, 0xBC, 0xBD, 0xBE, 0xC6):
        for x in (96, 100):
            for right in (True, False):
                for world in ('floor', 'body', 'air'):
                    for py in (168, 240, 40):
                        out.append((x, y, 0, 0, 0x40, right, py, 0x80, world, 0, 'AF77'))
    # THE LAUNCH's three arms: enemy above the player, below it, and LEVEL --
    # only the level case reaches the LFSR, and there the draw is compared with
    # the ANIM COUNTER, so sweep that too, and both sides of the player.
    for anim in (0, 1, 0x40, 0x80, 0xFF):
        for py in (100, 168, 240):
            for px in (0x20, 0x60, 0x61, 0xF0):
                for right in (True, False):
                    for seed in (0x002A, 0x1234, 0xBB02, 0x7F7F):
                        out.append((96, 168, 0, 0, anim, right, py, px, 'floor', seed, 'AF77'))
    # AIRBORNE: every cursor value, both tables, including the OVERRUN at $20
    for st in (0x81, 0x01):
        for cur in (0, 1, 0x0F, 0x10, 0x11, 0x1E, 0x1F, 0x20):
            for x in (8, 96, 100, 248):
                for right in (True, False):
                    for world in ('floor', 'air'):
                        out.append((x, 168, st, cur, 0x40, right, 240, 0x80, world, 0, 'AF77'))
    # ...and the $B445 CP $10 quirk: it compares whatever $B4AC left in A, which
    # is the NEW X on a move and the NEW FLAGS on a turn.  An X below $10 skips
    # the landing test; flags never can, being >= $80.
    for x in (0, 2, 8, 0x11, 0x12, 0x20):
        for st in (0x81, 0x01):
            for cur in (0x10, 0x18):
                for right in (True, False):
                    for world in ('floor', 'air', 'wall'):
                        out.append((x, 168, st, cur, 0x40, right, 240, 0x80, world, 0, 'AF77'))
    return out


def t4_world(m, name, x, y, right, st=0, cur=0):
    """build the world and RETURN the cells it poked, so the gate seeds exactly
       what the machine saw instead of re-deriving it"""
    for a in range(SYN_SHADOW_LO, SYN_SHADOW_HI):
        m[a] = 0
    c = {}
    if name == 'body':                      # solid at BODY level -> $B3DC fall
        c[cell(x, (y + 0x11) & 0xFF)] = SOLID
        c[(cell(x, (y + 0x11) & 0xFF) - 32) & 0xFFFF] = SOLID
    elif name == 'wall':                    # a wall in the way of the step
        for d in (0, 1, 2):
            c[(cell((x + 15 + 2) & 0xFF, (y + 15) & 0xFF) + d) & 0xFFFF] = SOLID
            c[(cell((x - 2) & 0xFF, (y + 15) & 0xFF) + d) & 0xFFFF] = SOLID
    elif name in ('land', 'landhead'):
        # poke the cell the ARC-DISPLACED landing probe will read, not the one
        # under the enemy's feet -- $B44A adds the arc value to Y + 15
        dy = m[(ARC_SMALL if (st & 0x80) else ARC_TALL) + cur]
        a = cell(x, (y + 15 + dy) & 0xFF)
        c[a] = SOLID
        if name == 'landhead':
            c[(a - 32) & 0xFFFF] = SOLID
    elif name == 'floor':
        c[cell(x, (y + 0x11) & 0xFF)] = SOLID
    for (a, v) in c.items():
        m[a] = v
    return c


def capture_t4():
    h, m = new('round1_48')
    for a in range(SYN_DUMMY_LO, SYN_DUMMY_HI):
        m[a] = 0
    rows = []
    slot = TABLE + 2 * STRIDE
    for (x, y, st, cur, anim, right, py, px, world, seed, entry) in t4_cases():
        cells = t4_world(m, world, x, y, right, st, cur)
        for i in range(STRIDE):
            m[slot + i] = 0
        m[slot + 0], m[slot + 1] = 0x00, 0xC1
        m[slot + 4] = anim
        m[slot + 5], m[slot + 6] = x, y
        m[slot + 7] = 0x80 | (1 if right else 0)
        m[slot + 8], m[slot + 9] = cur, st
        for a in (0xB088, 0xB20D, 0xB25D):
            m[a] = 0x00
        m[0xB60F], m[0xB610], m[0xB611] = 0x16, 2, 2
        m[0xB612], m[0xB613] = px, py
        if seed:
            m[0xFE86], m[0xFE87] = seed & 0xFF, seed >> 8
        before = [m[slot + i] for i in range(STRIDE)]
        prng0 = [m[0xFE86], m[0xFE87]]
        arm_call(h, T4 if entry == 'AF77' else 0xB3C5, slot, SP0[0])
        draws = run_to_sentinel(h)
        rows.append({'x': x, 'y': y, 'st': st, 'cur': cur, 'anim': anim,
                     'right': right, 'py': py, 'px': px, 'world': world, 'entry': entry,
                     'cells': {str(a): v for a, v in sorted(cells.items())},
                     'before': before, 'draws': draws, 'prng': prng0,
                     'after': [m[slot + i] for i in range(STRIDE)],
                     'prng_after': [m[0xFE86], m[0xFE87]],
                     'gafter': {'B60D': m[0xB60D], 'B60E': m[0xB60E]}})
    return {'note': ('$AF77 called DIRECTLY over four built worlds -- floor, body-solid, open air '
                     'and a wall -- sweeping every arc cursor value INCLUDING the $20 overrun that '
                     'reads past the table into the key table, both arc tables, the three arms of '
                     'the launch (above / below / LEVEL with the player, only the last of which '
                     'draws from the LFSR), the anim counter the draw is compared against, and '
                     'the X values that make $B445 CP $10 skip the landing test.'),
            'handler': T4, 'arc_tall': ARC_TALL, 'arc_small': ARC_SMALL, 'keytab': KEYTAB,
            'shadow_lo': SYN_SHADOW_LO, 'shadow_hi': SYN_SHADOW_HI,
            'dummy_lo': SYN_DUMMY_LO, 'dummy_hi': SYN_DUMMY_HI,
            'worlds': ['floor', 'body', 'air', 'wall', 'land', 'landhead'],
            'entries': {'AF77': T4, 'B3C5': 0xB3C5},
            # The key tables are LIVE STATE, not constants: the tape's defaults
            # are DF 02 DF 01 FB 01 7F 01 (O P Q SPACE) but round1_48 holds
            # F7 10 EF 04 EF 01 EF 08 -- the CURSOR keys P1 was set to, and $1F
            # pairs for P2, which is the Kempston port.  At the title they are
            # all zero.  Type 4's arc overrun reads the first byte, so which
            # controls the player chose changes how its jump finishes.
            'keytab_b64': base64.b64encode(bytes(m[0xB5FD:0xB60D])).decode(),
            'rows': rows}


# ------------------------------------------------- CAPTURE and ESCAPE
# $BE5B, the capture: a travelling EMPTY bubble that overlaps an enemy takes it.
# $92C0 (with $92DE patched to RET) builds the bubble's box -- the sprite inset
# by two on every side, X+2..X+14 and Y+2..Y+14 -- and walks the enemies' +7
# bytes from $FD9B in steps of ten, skipping any that is not alive or is already
# FROZEN.  The overlap test on each axis is `v < hi AND (v + 15) >= lo`, both
# eight-bit, so the boundaries are the interesting part.
#
# $B679, the escape: reached whenever a bubble's kind is non-zero, but it does
# nothing unless the kind is exactly 1.  A holding bubble ages and, when the age
# WRAPS to zero, releases its enemy -- unfrozen, ANGRY, dropped at the bubble's
# cell-aligned position -- and dies.
#
# A capture also ABANDONS its caller: $BEA8 POPs the return address before the
# final JP, so with sentinels pushed the call comes back on sentinel INDEX 1
# rather than 0.  That index is recorded, because it IS the observable.
CAPTURE, ESCAPE, TRAVEL = 0xBE5B, 0xB679, 0xBE07
POOL = 0xFED8                      # the bubble pool, 12 slots of 10
ESC_DELAY = 0x745A                 # the round's escape delay, read at $BEA2


def csum(m, lo, hi):
    """h = h * 31 + b, 32-bit -- the same arithmetic the gate does in JS.
       Without it a gate that reads only entity slots cannot see the ERASE a
       capture and an escape both perform, nor the marker an escape releases."""
    h = 0
    for a in range(lo, hi):
        h = (h * 31 + m[a]) & 0xFFFFFFFF
    return h


def cap_cases():
    """(bx, by, ex, ey, eflags, count, delay, kind, slot[, ecx, ecy]) -- ecx/ecy, the
    enemy's CACHED X/Y (+3/+2), default to ex/ey"""
    out = []
    # THE OVERLAP BOUNDARIES.  With the bubble at 96 the box is 98..110, so the
    # enemy X matters around 110 (v < hi) and 83 (v + 15 >= lo).
    for ex in (80, 82, 83, 84, 95, 96, 97, 109, 110, 111, 112):
        for ey in (80, 82, 83, 84, 96, 109, 110, 111):
            out.append((96, 96, ex, ey, 0xC0, 3, 0x30, 0, 0))
    # THE EIGHT-BIT WRAP in `v + 15`.  It only shows where the FIRST test still
    # passes (v < X+14), so the bubble must sit high enough that its far edge
    # wraps too: at bx = 240 the box is 242..254, and an enemy at 245 has
    # v + 15 = 260 -- which is 4 eight-bit (no overlap) and 260 sixteen-bit (yes).
    for bx in (236, 240, 244, 248, 250):
        for ex in (238, 241, 245, 250, 252, 254, 0, 2):
            out.append((bx, 96, ex, 96, 0xC0, 3, 0x30, 0, 0))
    for by in (236, 244, 250):
        for ey in (241, 245, 252, 0):
            out.append((96, by, 96, ey, 0xC0, 3, 0x30, 0, 0))
    # THE TWO AXES APART.  Every case above has bx == by and ex == ey, so a test
    # that compared the Y coordinate against the X box was indistinguishable.
    for (bx, by) in ((96, 40), (40, 96), (96, 200), (200, 96)):
        for (ex, ey) in ((96, 40), (40, 96), (96, 96), (40, 40), (96, 200), (200, 96)):
            out.append((bx, by, ex, ey, 0xC0, 3, 0x30, 0, 0))
    # THE SKIP FLAGS: dead (bit 7 clear) and already frozen (bit 3) are passed
    # over, so one bubble cannot steal the enemy another is holding.
    for f in (0xC0, 0x40, 0xC8, 0x88, 0x80, 0xE0):
        for ex in (96, 104):
            out.append((96, 96, ex, 96, f, 3, 0x30, 0, 0))
    # THE COUNT, with the enemy in a LATER slot so the count actually decides:
    # ($AA57) = 3 scans one slot and misses it, 8 reaches it.  With the enemy
    # always in slot 2 the count was free.
    for cnt in (2, 3, 4, 8, 12):
        for slot in (0, 1, 3, 4):
            out.append((96, 96, 96, 96, 0xC0, cnt, 0x30, 0, slot))
    # the escape delay the capture stamps into the bubble's age
    for d in (0, 1, 0x30, 0x80, 0xFF):
        out.append((96, 96, 96, 96, 0xC0, 3, d, 0, 0))
    # a bubble that is not empty is still offered -- $BE5B does not check
    for k in (0, 1, 2, 4):
        out.append((96, 96, 96, 96, 0xC0, 3, 0x30, k, 0))
    # THE CACHED POSITION HELD APART from the current one (two trailing fields,
    # the enemy's +3 and +2).  $BE92's erase is $A447's, so its $A430 add is
    # chosen by the CACHED X ($A480 on (+3) & 6: +7 aligned, +20 shifted) and
    # gated by bit 6 and the cached Y ($A464 CP $C0) -- none of which the cases
    # above, with +3 = +5 and +2 = +6, can tell from the current X (M7.49).
    for (ex, ecx) in ((96, 98), (96, 100), (96, 102), (98, 96), (100, 96), (102, 96),
                      (97, 99), (99, 97)):
        out.append((96, 96, ex, 96, 0xC0, 3, 0x30, 0, 0, ecx, 96))
    for ecx in (96, 98):
        out.append((96, 96, 96, 96, 0x80, 3, 0x30, 0, 0, ecx, 96))    # first visit
        for ecy in (0xBF, 0xC0):
            out.append((96, 96, 96, 96, 0xC0, 3, 0x30, 0, 0, ecx, ecy))
    return out


def esc_cases():
    """(kind, age, idx, bx, by, eflags, etimer, estate)"""
    out = []
    for kind in (0, 1, 2, 3, 4):
        for age in (0, 0xFE, 0xFF):
            out.append((kind, age, 0, 100, 100, 0xC8, 0, 0))
    for idx in (0, 1, 2, 5, 9, 25, 26, 30):
        out.append((1, 0xFF, idx, 100, 100, 0xC8, 0, 0))
    for (bx, by) in ((0, 0), (7, 7), (8, 8), (100, 100), (103, 103), (248, 190),
                     (255, 255)):
        out.append((1, 0xFF, 0, bx, by, 0xC8, 0, 0))
    for f in (0xC8, 0x88, 0xCC, 0x8C, 0xFF, 0x08):
        out.append((1, 0xFF, 0, 100, 100, f, 0, 0))
    # $B6AE and $B6B2 clear the enemy's TIMER and STATE, and every case above
    # already had both zero, so neither clear was observable.
    for (tm, st) in ((12, 0), (0, 0x81), (7, 0x20), (0xFF, 0xFF), (12, 0x81)):
        out.append((1, 0xFF, 0, 100, 100, 0xC8, tm, st))
    return out


def capture_capesc():
    h, m = new('round1_48')
    shadow = base64.b64encode(bytes(m[0xF800:0xFC00])).decode()
    # the DISPLAY is restored per row too: both routines paint, so without it
    # each row would inherit the previous row's pixels and the checksum would be
    # a function of the sweep ORDER rather than of the routine
    disp = base64.b64encode(bytes(m[0x4000:0x5B00])).decode()
    rows = []
    bub = POOL + 3 * 10                 # an arbitrary middle bubble slot
    for case in cap_cases():
        bx, by, ex, ey, eflags, count, delay, kind, slot = case[:9]
        ecx, ecy = case[9:] if len(case) > 9 else (ex, ey)
        m[0xF800:0xFC00] = base64.b64decode(shadow)
        m[0x4000:0x5B00] = base64.b64decode(disp)
        for k in range(12):             # quiet every enemy, then place one
            m[TABLE + 10 * k + 7] &= 0x7F
        for i in range(10):
            m[bub + i] = 0
        m[bub + 0], m[bub + 1] = 0x80, 0xC7
        m[bub + 2], m[bub + 3] = by, bx
        m[bub + 4] = 5
        m[bub + 5], m[bub + 6] = bx, by
        m[bub + 7] = 0x80
        m[bub + 9] = kind
        e = TABLE + (2 + slot) * STRIDE
        for i in range(10):
            m[e + i] = 0
        m[e + 0], m[e + 1] = 0x00, 0xC1
        m[e + 2], m[e + 3] = ecy, ecx
        m[e + 5], m[e + 6] = ex, ey
        m[e + 7] = eflags
        m[0xAA57] = count
        m[ESC_DELAY] = delay
        m[0xFDDA] = 0xFF
        m[0xFDE4] = 0xFF
        m[0xA431] = 0                   # $A430's addend: every add the call makes lands here
        before = [m[bub + i] for i in range(10)] + [m[e + i] for i in range(10)]
        arm_call(h, CAPTURE, bub, SP0[0])
        be92 = None                     # $A431 across $BE92 CALL $A447 (returns to $BE95)
        while True:
            h.run_until(tuple(h.SENTINELS) + (0xBE92, 0xBE95), limit=10 ** 6, stride=1,
                        interrupts=False)
            if h.regs[PC] == 0xBE92:
                a0 = m[0xA431]
            elif h.regs[PC] == 0xBE95:
                be92 = (m[0xA431] - a0) & 0xFF
            else:
                break
            h.step(1, interrupts=False)
        assert h.regs[PC] in h.SENTINELS, 'capture: no sentinel, PC $%04X' % h.regs[PC]
        rows.append({'kind': 'capture', 'bx': bx, 'by': by, 'ex': ex, 'ey': ey,
                     'ecx': ecx, 'ecy': ecy,
                     'eflags': eflags, 'count': count, 'delay': delay, 'bkind': kind,
                     'slot': slot, 'eslot': e, 'before': before,
                     'after': [m[bub + i] for i in range(10)] + [m[e + i] for i in range(10)],
                     'sentinel': h.SENTINELS.index(h.regs[PC]),
                     'owner': [m[0xFDDA], m[0xFDE4]],
                     'a431': m[0xA431], 'be92': be92,
                     'disp': csum(m, 0x4000, 0x5B00), 'shad': csum(m, 0xF800, 0xFC00)})
    for (kind, age, idx, bx, by, eflags, etim, esta) in esc_cases():
        m[0xF800:0xFC00] = base64.b64decode(shadow)
        m[0x4000:0x5B00] = base64.b64decode(disp)
        for k in range(12):
            m[TABLE + 10 * k + 7] &= 0x7F
        for i in range(10):
            m[bub + i] = 0
        m[bub + 0], m[bub + 1] = 0x00, 0xC9
        m[bub + 2], m[bub + 3] = 0xF8, 0xF9      # a marker address inside the shadow
        m[bub + 4] = age
        m[bub + 5], m[bub + 6] = bx, by
        m[bub + 7] = 0x84                        # alive, bit 2 -- it owns a marker
        # The erase repaints the display FROM the shadow, so on a settled screen
        # it writes the bytes that are already there and no checksum moves
        # (TRAPS #37).  Dirty the box it will repaint, and give the marker byte
        # low bits for the AND $E0 to clear, or neither is observable.
        # The erase repaints the display FROM the shadow, so on a settled screen
        # it writes the bytes already there and no checksum moves (TRAPS #37).
        # Fill the display with a pattern nothing could repaint to, and give the
        # MARKER byte low bits for the AND $E0 to clear.  The marker address is
        # little-endian out of +2/+3 -- L from +2, H from +3 -- so with $F8/$F9
        # it is $F9F8, not $F8F9.
        for a in range(0x4000, 0x5B00):
            m[a] = (a * 7) & 0xFF
        m[0xF9F8] = 0x3F
        m[bub + 8] = idx
        m[bub + 9] = kind
        e = (TABLE + 2 * STRIDE + ((10 * idx) & 0xFF)) & 0xFFFF
        for i in range(10):
            m[(e + i) & 0xFFFF] = 0
        m[(e + 5) & 0xFFFF], m[(e + 6) & 0xFFFF] = 40, 40
        m[(e + 7) & 0xFFFF] = eflags
        m[(e + 8) & 0xFFFF] = etim
        m[(e + 9) & 0xFFFF] = esta
        before = ([m[bub + i] for i in range(10)] +
                  [m[(e + i) & 0xFFFF] for i in range(10)])
        # $B679 does NOT return: both its exits JP to $B66C, the manager's
        # slot-advance, which walks IY on and loops while ($BFF7) is non-zero.
        # Setting the counter to 1 makes that advance DEC it to zero and RET, so
        # the call comes back after exactly this slot instead of running the rest
        # of the loop over whatever follows the pool.
        m[0xBFF7] = 1
        m[0xA431] = 0                            # $A430's addend (M7.49)
        arm_call(h, ESCAPE, bub, SP0[0])
        h.sim.registers[0] = kind                # $B679 is entered with A = (IY+9)
        h.run_until(tuple(h.SENTINELS), limit=10 ** 6, stride=1, interrupts=False)
        assert h.regs[PC] in h.SENTINELS, 'escape: no sentinel, PC $%04X' % h.regs[PC]
        rows.append({'kind': 'escape', 'ekind': kind, 'age': age, 'idx': idx,
                     'bx': bx, 'by': by, 'eflags': eflags, 'eslot': e,
                     'etim': etim, 'esta': esta, 'before': before,
                     'dirty': True, 'marker_at': 0xF9F8, 'a431': m[0xA431],
                     'after': ([m[bub + i] for i in range(10)] +
                               [m[(e + i) & 0xFFFF] for i in range(10)]),
                     'sentinel': h.SENTINELS.index(h.regs[PC]),
                     'disp': csum(m, 0x4000, 0x5B00), 'shad': csum(m, 0xF800, 0xFC00)})
    # ---- $BE07, the whole travel step, so the ABANDONMENT is observable.
    #      $BEA8 POPs the caller's return address, so on a capture the wall
    #      probe and the cap test that follow $BE31 never run.  Calling $BE5B
    #      alone cannot show that; only running the step around it can.
    for ex in (80, 96, 104, 200):
        for age in (1, 2, 5, 0x30):
            for face in (0, 1):
                m[0xF800:0xFC00] = base64.b64decode(shadow)
                m[0x4000:0x5B00] = base64.b64decode(disp)
                for k in range(12):
                    m[TABLE + 10 * k + 7] &= 0x7F
                for i in range(10):
                    m[bub + i] = 0
                m[bub + 0], m[bub + 1] = 0x80, 0xC7
                m[bub + 2], m[bub + 3] = 96, 96
                m[bub + 4] = age
                m[bub + 5], m[bub + 6] = 96, 96
                m[bub + 7] = 0x80 | face
                e = TABLE + 2 * STRIDE
                for i in range(10):
                    m[e + i] = 0
                m[e + 0], m[e + 1] = 0x00, 0xC1
                m[e + 2], m[e + 3] = 96, ex
                m[e + 5], m[e + 6] = ex, 96
                m[e + 7] = 0xC0
                m[0xAA57] = 3
                m[ESC_DELAY] = 0x30
                m[0xFDDA] = 0xFF
                m[0xFDE4] = 0xFF
                m[0xFDDE], m[0xFDDF] = 8, 7
                before = [m[bub + i] for i in range(10)] + [m[e + i] for i in range(10)]
                m[0xA431] = 0                    # $A430's addend (M7.49)
                arm_call(h, TRAVEL, bub, SP0[0])
                h.run_until(tuple(h.SENTINELS), limit=10 ** 6, stride=1, interrupts=False)
                assert h.regs[PC] in h.SENTINELS, 'travel: no sentinel'
                rows.append({'kind': 'travel', 'ex': ex, 'age': age, 'face': face,
                             'eslot': e, 'before': before,
                             'after': [m[bub + i] for i in range(10)] +
                                      [m[e + i] for i in range(10)],
                             'sentinel': h.SENTINELS.index(h.regs[PC]),
                             'a431': m[0xA431],
                             'disp': csum(m, 0x4000, 0x5B00),
                             'shad': csum(m, 0xF800, 0xFC00)})
    return {'note': ('$BE5B and $B679 called DIRECTLY. The capture rows sweep the overlap test on '
                     'both axes across its boundaries and its eight-bit wrap, with the axes held '
                     'APART so one cannot be tested against the other box; the flags that make the '
                     'scan skip an enemy; the slot count, with the enemy placed in a LATER slot so '
                     'the count decides; and the escape delay it stamps into the age. A capture '
                     'ABANDONS its caller ($BEA8 POPs the return address), so the sentinel INDEX '
                     'says whether one happened: 1 yes, 0 no. The escape rows sweep the kind (only '
                     'exactly 1 escapes), the age either side of its wrap, the enemy index -- '
                     'whose 10*i is eight-bit -- the cell alignment of the release, and the '
                     'enemy timer and state the release clears. Every row carries a CHECKSUM of '
                     'the display and the colour shadow, because both routines PAINT and both '
                     'release a marker, and a gate reading only entity slots cannot see either. '
                     'M7.49: every row seeds $A431, the operand of $A430 ADD A,n, to 0 and records '
                     'it after (a431), and a capture row records what $BE92 CALL $A447 added '
                     '(be92) -- the erase half picks +7/+20 by the CACHED X and adds nothing on a '
                     'first visit or at a cached Y of $C0 or more, so the capture cases also hold '
                     'the cached +3/+2 (ecx/ecy) apart from the current +5/+6.'),
            'bubble_at': POOL + 30, 'table_at': TABLE, 'esc_delay_at': ESC_DELAY,
            'shadow_lo': 0xF800, 'shadow_b64': shadow,
            'disp_lo': 0x4000, 'disp_hi': 0x5B00, 'disp_b64': disp,
            # $B62D is the flash toggle the bubble blitter consults at $BA0D for
            # a HOLDING bubble whose age has passed $E6 -- so it decides which
            # sprite a capture with a high escape delay draws
            'b62d': m[0xB62D],
            'rows': rows}



def census():
    """what actually changes, per slot, frame to frame -- the transliteration map"""
    fx = json.load(open(FIXTURE))
    for sc in fx['scenes']:
        rows = sc['rows']
        print(f"--- {sc['state']} ---")
        for k in range(SLOTS):
            b = STRIDE * k
            if not (rows[0]['table'][b + 7] & 0x80):
                continue
            fields = {}
            for i in range(1, len(rows)):
                for o in range(STRIDE):
                    if rows[i]['table'][b + o] != rows[i - 1]['table'][b + o]:
                        fields.setdefault(o, 0)
                        fields[o] += 1
            first, last = rows[0]['table'][b:b + STRIDE], rows[-1]['table'][b:b + STRIDE]
            print(f'  slot {k:2d}: changes/frame by offset {fields}')
            print(f'           first {[f"{v:02X}" for v in first]}')
            print(f'           last  {[f"{v:02X}" for v in last]}')


if __name__ == '__main__':
    v = sys.argv[1] if len(sys.argv) > 1 else 'census'
    if v == 'capture':
        capture()
    else:
        census()
