"""M7.7-I3 -- the OVERLAP BOX ($930A/$9312) and the COLLECT ($87B2, $87E2-$8826).

THE PRIMARY ORACLE IS EXHAUSTIVE.  $930A and $9312 are PURE PREDICATES of three
bytes, so instead of sampling them through gameplay they are called directly
over ALL 256x256 combinations and the CARRY FLAG is captured:

    $930A  LD A,(HL) / CP C / RET nc / ADD A,15 / CP E / CCF / RET
    $9312  LD A,(HL) / CP B / RET nc / ADD A,15 / CP D / CCF / RET

with $87B8 setting E = px, C = px+15, D = py, B = py+15.  So an item overlaps
in X iff  ix < (px+15)&$FF  AND  (ix+15)&$FF >= px,  and the same in Y.  Both
adds are EIGHT BIT, so the box wraps at the screen edges.

WHY EXHAUSTIVE RATHER THAN SAMPLED.  An item's X is always a multiple of 16 and
the player moves in coarse steps, so a +-15 box and a +-16 box -- and `<` versus
`<=` on the right edge -- agree at almost every position the game can actually
produce.  SPEC's one recorded datum (player at X=50 collecting a fruit at X=64)
passes under all four readings.  Driving the predicate directly, where the item
coordinate is a free byte rather than something the game chose, is the only way
to pin the edges.  65,536 rows per axis.

AND THE TWO AXES ARE GATED SEPARATELY, because the draw Y mask and the collide
Y mask are BOTH $F8: a model that wrongly uses one mask for both axes is right
in Y and wrong only in X, so a combined pass/fail hides it.

THE SECONDARY ORACLE is $87B2 itself, which is where the mask split lives:
$877C takes the draw X with AND $F0, but $87C9 writes byte0 & $F8 BACK INTO THE
TABLE for the duration of the call and restores it afterwards (the original is
stashed in A' across the CALL by the EX AF,AF' pair).  $F8 keeps BIT 3 -- part
of the type nibble -- as an X bit, so every item of type 8..15 is collision
tested EIGHT PIXELS RIGHT of where it is drawn.  Invisible for types 0..7, and
the drop generator only makes 0..7, so the sweep forces types >= 8 and uses
same-X control pairs (type 1 against type 9).

$87B2's FIRST BYTE IS LIVE STATE, not code: $94DB writes $C9 (collection OFF)
and $956D writes $00 (a NOP, collection ON).  That is why an earlier session
could stand a player on a fruit and watch nothing happen.  Both states swept.

SP IS PINNED PER CALL and the sentinel asserted (TRAPS #42); over 130k calls an
unpinned stack walks into ROM and every later row reads as "nothing happened".

Usage:  python tools/itembox.py capture
        python tools/itembox.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

BOX_X, BOX_Y = 0x930A, 0x9312
COLLIDE = 0x87B2
SCRATCH = 0x9605          # a real fruit slot; HL points here
PATCH = 0x87B2            # the enable/disable byte
P1, P2 = 0xFD80, 0xFD8A
FIXTURE = 'build/itembox_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]
A, F, B, C, D, E, H, L = 0, 1, 2, 3, 4, 5, 6, 7


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr


def run(h):
    h.run_until(h.SENTINELS, limit=10000, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    return r[F] & 0x01                      # THE CARRY FLAG is the answer


# ------------------------------------------------------- the pure predicates
def sweep_axis(h, m, addr, lo_reg, hi_reg):
    """All 256x256 of (item coord, player coord), packed one bit per row.

       Returns bytes, 8192 of them: bit (p*256 + i) is the carry for item
       coordinate i against player coordinate p.
    """
    r = h.sim.registers
    bits = bytearray(8192)
    m[SCRATCH + 1] = 0                       # keep the neighbour byte quiet
    for p in range(256):
        r[lo_reg] = p                        # E (or D) = the player coordinate
        r[hi_reg] = (p + 15) & 0xFF          # C (or B) = player + 15
        for i in range(256):
            m[SCRATCH] = i
            r[H], r[L] = SCRATCH >> 8, SCRATCH & 0xFF
            arm(h, addr)
            if run(h):
                n = p * 256 + i
                bits[n >> 3] |= 1 << (n & 7)
    return bytes(bits)


# ------------------------------------------------------------ $87B2 itself
def collide_cases():
    """(name, type, itemX, itemY, playerX, playerY, which player, patch, lock)"""
    out = []
    # THE MASK SPLIT.  Same drawn X, type 1 against type 9: $F8 keeps bit 3, so
    # type 9 collides eight pixels right of where it draws.  The control pair is
    # the point -- either row alone proves nothing.
    for typ in (1, 9):
        for px in range(0x30, 0x60, 2):
            out.append(('mask split t%d px=%d' % (typ, px),
                        typ, 0x40, 0x88, px, 0x88, P1, 0x00, False))
    # the box edges in X, walked one pixel at a time across a real entry
    for px in range(0x31, 0x60):
        out.append(('X edge px=%d' % px, 0, 0x40, 0x88, px, 0x88, P1, 0x00, False))
    # ...and in Y, so a model using one mask for both axes is caught
    for py in range(0x79, 0x98):
        out.append(('Y edge py=%d' % py, 0, 0x40, 0x88, 0x44, py, P1, 0x00, False))
    # THE PATCH BYTE: the same overlapping case with collection disabled
    for patch in (0x00, 0xC9):
        out.append(('patch $%02X' % patch, 0, 0x40, 0x88, 0x44, 0x88, P1, patch, False))
    # THE BIT-6 LOCK, which no round below 80 can reach
    for lock in (False, True):
        out.append(('bit6 lock %s' % lock, 0, 0x40, 0x88, 0x44, 0x88, P1, 0x00, lock))
    # P2 as the collector
    out.append(('P2 collects', 0, 0x40, 0x88, 0x44, 0x88, P2, 0x00, False))
    # the eight-bit WRAP: an item at the right edge and a player at the left
    for (ix, px) in ((0xF0, 0x02), (0xF8, 0x00), (0x00, 0xF4), (0x08, 0xFE)):
        out.append(('wrap ix=%d px=%d' % (ix, px), 0, ix, 0x88, px, 0x88, P1, 0x00, False))
    return out


def collide_rows(h, m):
    rows = []
    saved_patch = m[PATCH]
    saved_erase = m[0x86E6]
    m[0x86E6] = 0xC9                          # the erase is I5; keep this run pure
    for (name, typ, ix, iy, px, py, who, patch, lock) in collide_cases():
        m[PATCH] = patch
        m[SCRATCH] = (ix & 0xF0) | typ
        m[SCRATCH + 1] = (iy & 0xF8) | 1
        m[0x8908], m[0x8909] = ix & 0xF0, iy & 0xF8
        for base in (P1, P2):
            m[base + 7] = 0x80 if base == who else 0x00      # only the tested player is live
            m[base + 5], m[base + 6] = px, py
            m[base + 0x5A] = 0x40 if lock else 0x00
            m[base + 0x62] = 0
        m[0xFFED] = m[0xFFEE] = 0
        m[0x8828] = 0xEE
        before = {'b0': m[SCRATCH], 'b1': m[SCRATCH + 1]}
        r = h.sim.registers
        r[8], r[9] = who >> 8, who & 0xFF                     # IXh, IXl
        r[H], r[L] = SCRATCH >> 8, SCRATCH & 0xFF
        arm(h, COLLIDE)
        carry = run(h)
        rows.append({'name': name, 'type': typ, 'ix': ix, 'iy': iy,
                     'px': px, 'py': py, 'who': who, 'patch': patch, 'lock': lock,
                     'before': before, 'carry': carry,
                     'b0': m[SCRATCH], 'b1': m[SCRATCH + 1],
                     'counter': m[who + 0x62], 'pend': [m[0xFFED], m[0xFFEE]],
                     'type_op': m[0x8828]})
    m[PATCH] = saved_patch
    m[0x86E6] = saved_erase
    return rows


# ----------------------------------------------------- the P2-before-P1 order
PERSLOT = 0x86B1


def contest_rows(h, m):
    """$86B1 with BOTH players live over ONE entry.

       $86B5 loads IX = $FD8A (P2) and tests first; $86BD re-reads byte0 and
       RET z, so an entry P2 took is abandoned for the frame and P1 never sees
       it.  In a one-player game P2's +7 bit 7 is clear, so $87B7 returns before
       anything else happens and the ordering is completely invisible -- which
       is why it has to be BUILT rather than sampled.
    """
    rows = []
    saved = m[0x86E6]
    m[0x86E6] = 0xC9                       # the erase is I5
    # The px=8 rows are the ones that make $86BD's guard OBSERVABLE.  An emptied
    # slot has byte0 = 0, and byte0 = 0 only falls inside the box when the player
    # is near X=0 -- at px=68 the guard is a no-op, because P1 tests the zeroed
    # entry and misses it anyway.  Near the left edge P1 WOULD take the same slot
    # a second time, so "abandon the entry once taken" stops being free.
    for (p1live, p2live, px, name) in (
            (True, True, 0x44, 'both players on the item'),
            (True, False, 0x44, 'P1 only'),
            (False, True, 0x44, 'P2 only'),
            (False, False, 0x44, 'neither'),
            (True, True, 0x08, 'both at the LEFT EDGE -- an emptied slot still overlaps'),
            (True, False, 0x08, 'P1 only at the left edge'),
            (False, True, 0x08, 'P2 only at the left edge')):
        m[SCRATCH] = 0x00 if px == 0x08 else 0x40
        m[SCRATCH + 1] = 0x89
        if px == 0x08:
            m[SCRATCH] = 0x01      # X=0, type 1: byte0 non-zero but its X IS zero
        m[0x872C] = 0
        for base, live in ((P1, p1live), (P2, p2live)):
            m[base + 7] = 0x80 if live else 0x00
            m[base + 5], m[base + 6] = px, 0x88
            m[base + 0x5A] = 0
            m[base + 0x62] = 0
        r = h.sim.registers
        r[H], r[L] = SCRATCH >> 8, SCRATCH & 0xFF
        arm(h, PERSLOT)
        run(h)
        rows.append({'name': name, 'p1live': p1live, 'p2live': p2live, 'px': px,
                     'b0_before': 0x01 if px == 0x08 else 0x40,
                     'b0': m[SCRATCH], 'b1': m[SCRATCH + 1],
                     'p1_counter': m[P1 + 0x62], 'p2_counter': m[P2 + 0x62]})
    m[0x86E6] = saved
    return rows


def capture():
    h, m = new()
    print('sweeping $930A, 65536 rows...')
    x = sweep_axis(h, m, BOX_X, E, C)
    print('sweeping $9312, 65536 rows...')
    y = sweep_axis(h, m, BOX_Y, D, B)
    print('collect cases...')
    rows = collide_rows(h, m)
    print('contested-item ordering...')
    contest = contest_rows(h, m)
    fx = {'note': __doc__.strip(),
          'box_x_at': BOX_X, 'box_y_at': BOX_Y, 'collide_at': COLLIDE,
          'patch_at': PATCH, 'scratch': SCRATCH,
          'x_b64': base64.b64encode(x).decode(),
          'y_b64': base64.b64encode(y).decode(),
          'collide': rows, 'contest': contest}
    json.dump(fx, open(FIXTURE, 'w'))
    nx = sum(bin(b).count('1') for b in x)
    ny = sum(bin(b).count('1') for b in y)
    print('wrote %s' % FIXTURE)
    print('  $930A: %d of 65536 combinations overlap' % nx)
    print('  $9312: %d of 65536 combinations overlap' % ny)
    print('  identical bitmaps (the two axes are the same predicate): %s' % (x == y))
    print('  %d collect cases' % len(rows))
    for c in contest:
        print('    %-26s -> P1 counter %d, P2 counter %d, byte0 $%02X'
              % (c['name'], c['p1_counter'], c['p2_counter'], c['b0']))


def verify():
    fx = json.load(open(FIXTURE))
    x = base64.b64decode(fx['x_b64'])
    get = lambda p, i: (x[(p * 256 + i) >> 3] >> ((p * 256 + i) & 7)) & 1
    print('the X box, as a span of item coordinates per player coordinate:')
    for p in (0, 1, 15, 16, 40, 100, 240, 250, 255):
        s = [i for i in range(256) if get(p, i)]
        runs, cur = [], None
        for i in s:
            if cur and i == cur[1] + 1: cur[1] = i
            else: cur = [i, i]; runs.append(cur)
        print('   px=%3d  %2d hits  %s' % (p, len(s),
              ' '.join('%d..%d' % (a, b) for a, b in runs)))
    print()
    # $87B2 has FIVE exits, so the carry alone does not say what happened --
    # a collect is identified by its SIDE EFFECTS.
    took = lambda r: r['b0'] == 0 and r['before']['b0'] != 0
    ms = [r for r in fx['collide'] if r['name'].startswith('mask split')]
    print('THE MASK SPLIT -- same drawn X ($40), two types:')
    for typ in (1, 9):
        hit = [r['px'] for r in ms if r['type'] == typ and took(r)]
        print('   type %2d  draws at X=%d, collects for px in %d..%d  (collide X = %d)'
              % (typ, 0x40, min(hit), max(hit), (0x40 | typ) & 0xF8))
    print()
    print('byte1 is PRESERVED through a collect:',
          all(r['b1'] == r['before']['b1'] for r in fx['collide'] if took(r)))
    pa = [r for r in fx['collide'] if r['name'].startswith('patch')]
    print('the $87B2 patch byte:', ' '.join(
        '$%02X -> %s' % (r['patch'], 'COLLECTS' if took(r) else 'nothing') for r in pa))
    lk = [r for r in fx['collide'] if r['name'].startswith('bit6')]
    print('the BIT 6 lock:      ', ' '.join(
        '%s -> %s' % (r['lock'], 'COLLECTS' if took(r) else 'LOCKED OUT') for r in lk))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
