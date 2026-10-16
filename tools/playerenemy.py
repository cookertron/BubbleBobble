# -*- coding: utf-8 -*-
"""M7.17 -- $925A, THE PLAYER/ENEMY COLLISION PASS, and $92DE, AN OPCODE THAT
IS ALSO A MODE SWITCH.

The fifteenth chain entry ($8D52).  What makes it worth a tool:

  (a) *** $92DE IS AN OPCODE AND IT IS STATE. ***  `$925A XOR A / LD ($92DE),A`
      writes $00 -- a NOP -- so the scan at $92C0 FALLS THROUGH into a SECOND
      list at $92DF.  `$9277 LD A,$C9 / LD ($92DE),A` writes a RET, so the same
      scan does ONE list.  And the other caller does the OPPOSITE: $BE5B (the
      bubble/enemy capture) writes $C9 BEFORE its `CALL $92C0` and $00 after.
      So the two writers DISAGREE about what to leave behind, and neither
      depends on the resting value -- each SETS BEFORE USE.  "Restore" is the
      wrong word for it, and a port that models a restore models a fiction.
  (b) THE SECOND LIST IS ONE PSEUDO-ENTITY AT $9250, whose +7 field is $9257 --
      three bytes before the routine's own first instruction.  Its +5/+6 are
      $88/$A8 on the tape and its +7 is $00, so it is INACTIVE as shipped.
      Whether anything ever activates it is a measurement, not a reading.
  (c) THE BOX TEST IS NOT AN AABB WITH EQUAL EDGES.  $9312/$930A are
      `LD A,(HL) / CP B / RET nc / ADD A,15 / CP D / CCF / RET`, so one edge is
      strict and the other is not, and `ADD A,15` is EIGHT BIT.  It is swept
      over all 65,536 entity positions, at TWO player positions (TRAPS #49).
  (d) $927D HAS TWO ARMS AND THE PORT HAS ONE.  ($FED0) != 0 sends it to
      $9298, where the ENEMY dies instead ($8BC2, +1000 to the player who
      touched it).

Usage:  python tools/playerenemy.py            (capture)
        python tools/playerenemy.py --jobs 15  (the sweep, across cores)
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/playerenemy_fixture.json'
BRANCH_BYTE = 0x8DC4
PASS_ = 0x925A            # the chain entry
PER_PLAYER = 0x92BB       # the per-player scan
SCAN = 0x92E4             # the list walk
MODE = 0x92DE             # the OPCODE that is a mode switch
LIST2 = 0x9250            # the second list's pseudo-entity base
HIT = 0x927D              # the player-hit handler
BUBBLE = 0xBE5B           # the other writer of $92DE
ENEMIES = 0xFD9B          # slot 0's +7 field
SLOTS = 0xAA57
HEART = 0xFED0
STATE = 'round1_48'
SCRATCH = 0xFC00          # an unused page for the synthetic one-entry list


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, limit=4 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])


# ------------------------------------------------- (a) the opcode mode switch
def phase_mode():
    """What $92DE holds, who writes it, and what each writer LEAVES."""
    rows = {}
    for s in ('round1_48', 'r20_48', 'play1p48', 'boss', 'hurryup', 'elwater'):
        try:
            h, m = new(s)
        except (Exception, SystemExit):
            continue
        rows[s] = m[MODE]
    #  drive each writer and read the byte afterwards
    h, m = new()
    before = m[MODE]
    arm(h, PASS_)
    run(h)
    after_pass = m[MODE]
    h, m = new()
    r = h.sim.registers
    r[10], r[11] = 0xFD, 0x94            # IY = an enemy slot, for $BE5B
    arm(h, BUBBLE)
    run(h)
    after_bub = m[MODE]
    print('(a) $92DE in the saved states: %s'
          % ' '.join('%s=$%02X' % (k, v) for k, v in rows.items()))
    print('    after $925A: $%02X (%s)   after $BE5B: $%02X (%s)   before: $%02X'
          % (after_pass, 'RET' if after_pass == 0xC9 else 'NOP',
             after_bub, 'RET' if after_bub == 0xC9 else 'NOP', before))
    return {'states': rows, 'after_pass': after_pass, 'after_bubble': after_bub,
            'before': before}


# ------------------------------------------------------- (b) the second list
def phase_list2():
    """$9250..$9259 as shipped, and whether ANYTHING writes it in play."""
    rows = {}
    for s in ('round1_48', 'r20_48', 'play1p48', 'boss', 'hurryup', 'elwater',
              'death', 'bottle', 'fruit', 'extend'):
        try:
            h, m = new(s)
        except (Exception, SystemExit):
            continue
        rows[s] = [m[LIST2 + i] for i in range(10)]
    #  a write watch over driven play
    from keyprobe import KEYS, press
    watch = {}
    for s in ('round1_48', 'hurryup'):
        try:
            h, m = new(s)
        except (Exception, SystemExit):
            continue
        h.memobj.watch(LIST2, LIST2 + 10)
        h.memobj.log.clear()
        for frames, keys in [(60, []), (40, ['0']), (40, ['O']), (40, ['P']),
                             (60, ['0', 'P']), (60, [])]:
            h.ports.release_all()
            for k in keys:
                press(h.ports, k)
            h.run_frames(frames)
        watch[s] = {'writes': len(h.memobj.log), 'frames': 300,
                    'log': [[p, a, v] for (p, a, v) in h.memobj.log[:20]]}
        h.memobj.unwatch()
    print('(b) SECOND LIST $9250..$9259: %s'
          % ' '.join('%02X' % v for v in rows[STATE]))
    print('    +5 = $%02X (x %d), +6 = $%02X (y %d), +7 = $%02X (%s)'
          % (rows[STATE][5], rows[STATE][5], rows[STATE][6], rows[STATE][6],
             rows[STATE][7],
             'ACTIVE' if rows[STATE][7] & 0x80 else 'inactive'))
    ident = all(v == rows[STATE] for v in rows.values())
    print('    identical in all %d states: %s;  writes in 300 driven frames: %s'
          % (len(rows), ident,
             ', '.join('%s %d' % (k, v['writes']) for k, v in watch.items())))
    return {'states': rows, 'identical': ident, 'watch': watch}


# ----------------------------------------------------------- (c) the box test
def _sweep_slice(args):
    """One band of entity Y values, swept over every entity X."""
    ylo, yhi, px, py = args
    h, m = new()
    r = h.sim.registers
    m[SCRATCH + 7] = 0x80                 # active, not a corpse
    accept = []
    base = arm(h, SCAN)                   # one bracket, reused
    for ey in range(ylo, yhi):
        m[SCRATCH + 6] = ey
        for ex in range(256):
            m[SCRATCH + 5] = ex
            r[SP] = base
            r[PC] = SCAN
            r[6], r[7] = (SCRATCH + 7) >> 8, (SCRATCH + 7) & 0xFF   # HL
            r[0] = 1                                                # A = 1 entry
            r[5] = (px + 2) & 0xFF                                  # E
            r[3] = (px + 14) & 0xFF                                 # C
            r[4] = (py + 2) & 0xFF                                  # D
            r[2] = (py + 14) & 0xFF                                 # B
            h.run_until(h.SENTINELS, limit=4000, stride=1, interrupts=False)
            if r[F] & 1:
                accept.append((ex, ey))
    return accept


def phase_box(jobs=15):
    """ALL 65,536 entity positions, at TWO player positions."""
    out = {}
    #  (235, 100) IS THE ANCHOR THAT SEPARATES EIGHT BITS FROM SIXTEEN.  The
    #  `ADD A,15` can only wrap when the entity is at 241 or above, and the
    #  `CP B` above it only lets such an entity through when player + 14 is
    #  bigger still -- so the two arithmetics agree everywhere except a player
    #  in [228, 241].  Three anchors missed it and a mutation survived.
    for (px, py) in ((100, 100), (200, 150), (250, 250), (235, 100)):
        bands = [(y, min(y + 16, 256), px, py) for y in range(0, 256, 16)]
        acc = []
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for part in ex.map(_sweep_slice, bands):
                acc.extend(part)
        xs = sorted(set(a for a, _ in acc))
        ys = sorted(set(b for _, b in acc))
        #  is it a rectangle?
        rect = len(acc) == len(xs) * len(ys)
        out['%d,%d' % (px, py)] = {
            'px': px, 'py': py, 'n': len(acc),
            'x_lo': xs[0] if xs else None, 'x_hi': xs[-1] if xs else None,
            'y_lo': ys[0] if ys else None, 'y_hi': ys[-1] if ys else None,
            'x_contiguous': bool(xs) and xs == list(range(xs[0], xs[-1] + 1)),
            'y_contiguous': bool(ys) and ys == list(range(ys[0], ys[-1] + 1)),
            'rectangle': rect,
            'xs': xs, 'ys': ys,
            'accept': ['%02X%02X' % (a, b) for (a, b) in acc[:12]],
        }
        print('(c) BOX at player (%d,%d): %d of 65,536 accept -- x %s..%s (%s), '
              'y %s..%s (%s), rectangle %s'
              % (px, py, len(acc), out['%d,%d' % (px, py)]['x_lo'],
                 out['%d,%d' % (px, py)]['x_hi'],
                 'contiguous' if out['%d,%d' % (px, py)]['x_contiguous'] else 'SPLIT',
                 out['%d,%d' % (px, py)]['y_lo'], out['%d,%d' % (px, py)]['y_hi'],
                 'contiguous' if out['%d,%d' % (px, py)]['y_contiguous'] else 'SPLIT',
                 rect))
    return out


# -------------------------------------------------- (d) one list against two
def phase_lists():
    """The SAME world scanned with $92DE = NOP and with $92DE = RET."""
    rows = []
    for mode, name in ((0x00, 'NOP -- two lists'), (0xC9, 'RET -- one list')):
        h, m = new()
        m[MODE] = mode
        #  make the second list HIT: put its box on top of the player
        m[LIST2 + 5] = m[0xFD85]
        m[LIST2 + 6] = m[0xFD86]
        m[LIST2 + 7] = 0x80
        #  ...and make sure the FIRST list cannot, by emptying it
        m[SLOTS] = 2
        r = h.sim.registers
        r[8], r[9] = 0xFD, 0x80           # IX = P1
        arm(h, PER_PLAYER)
        run(h)
        rows.append({'mode': mode, 'name': name, 'carry': r[F] & 1,
                     'hl': (r[6] << 8) | r[7]})
    print('(d) ONE LIST AGAINST TWO, same world: %s'
          % '; '.join('%s -> carry %d, HL $%04X' % (r['name'], r['carry'], r['hl'])
                      for r in rows))
    return rows


# ---------------------------------------------------------------- (e) the arms
def _scan(pokes, ix=0xFD80, entry=PER_PLAYER, carry_in=0):
    """One $92BB with the world poked AND THE CARRY SET DELIBERATELY.

    *** BIT AND LD DO NOT TOUCH THE CARRY, so $92BB's early `RET nz` returns
    with whatever carry it was CALLed with. ***  A probe that leaves the flag to
    chance is measuring its own harness."""
    h, m = new()
    for a, v in pokes.items():
        m[a] = v
    r = h.sim.registers
    r[8], r[9] = ix >> 8, ix & 0xFF
    r[F] = (r[F] & 0xFE) | (carry_in & 1)
    arm(h, entry)
    run(h)
    return h, m, r[F] & 1


def phase_arms():
    cases = []
    h0, m0 = new()
    px, py = m0[0xFD85], m0[0xFD86]
    on = {0xFD99: px, 0xFD9A: py, ENEMIES: 0x80, SLOTS: 3}

    def merged(extra):
        d = dict(on)
        d.update(extra)
        return d

    def one(name, pokes):
        row = {'case': name}
        for cin in (0, 1):
            _, _, c = _scan(pokes, carry_in=cin)
            row['carry_in_%d' % cin] = c
        cases.append(row)

    one('enemy on the player', merged({}))
    one('...player DYING (+$5A bit 2)', merged({0xFDDA: 0x04}))
    one('...enemy INACTIVE (+7 bit 7 clear)', merged({ENEMIES: 0x00}))
    one('...enemy is a CORPSE (+7 bit 3)', merged({ENEMIES: 0x88}))
    one('...zero slots to scan ($AA57 = 2)', merged({SLOTS: 2}))
    one('...enemy one pixel too far right', merged({0xFD99: (px + 15) & 0xFF}))
    print('(e) ARMS, driven with the carry BOTH ways on entry')
    for c in cases:
        print('      %-42s carry in 0 -> %d, in 1 -> %d%s'
              % (c['case'], c['carry_in_0'], c['carry_in_1'],
                 '   ** PRESERVES THE CALLER\'S CARRY'
                 if c['carry_in_0'] != c['carry_in_1'] else ''))
    return cases


def phase_carry():
    """$92BB's early RETs preserve the caller's carry -- so does $927D.  What
       does the WHOLE pass do when P1 hits and P2 cannot?

       $925A opens with `XOR A`, which CLEARS the carry, so P1's scan is always
       entered with it clear.  P2's is not: $9269's `CALL c,$927D` runs on P1's
       carry and $927D returns without touching it, so a P2 whose scan RETs
       early inherits P1's result and $927C `RET nc` falls into $927D AGAIN."""
    h0, m0 = new()
    px, py = m0[0xFD85], m0[0xFD86]
    rows = []
    for p2dying, label in ((True, 'P2 DYING (its scan RETs early)'),
                           (False, 'P2 alive and nowhere near')):
        h, m = new()
        #  P1 in play with an enemy on top of it; P2 in play, far away
        m[0xFD87] |= 0x80
        m[0xFD91] |= 0x80
        m[0xFD8F] = 0x08            # P2 X, far from the enemy
        m[0xFD90] = 0x08            # P2 Y
        m[0xFD99] = px
        m[0xFD9A] = py
        m[ENEMIES] = 0x80
        m[SLOTS] = 3
        m[0xFDDA] = 0x80            # P1 plain
        m[0xFDE4] = 0x84 if p2dying else 0x80
        before = (m[0xFDDA], m[0xFDE4], m[0xFD84], m[0xFD8E])
        arm(h, PASS_)
        run(h)
        rows.append({'case': label,
                     'p1_5a': [before[0], m[0xFDDA]],
                     'p2_5a': [before[1], m[0xFDE4]],
                     'p1_anim': [before[2], m[0xFD84]],
                     'p2_anim': [before[3], m[0xFD8E]]})
    print('(g) THE CARRY THAT IS NOT CLEARED, driven through the WHOLE $925A')
    for r in rows:
        print('      %-34s P1 +$5A $%02X->$%02X (+4 $%02X->$%02X), '
              'P2 +$5A $%02X->$%02X (+4 $%02X->$%02X)'
              % (r['case'], r['p1_5a'][0], r['p1_5a'][1], r['p1_anim'][0],
                 r['p1_anim'][1], r['p2_5a'][0], r['p2_5a'][1],
                 r['p2_anim'][0], r['p2_anim'][1]))
    return rows


def phase_or_a():
    """*** WHY P2 IS NOT HIT TWICE, MEASURED AT THE FLAG ITSELF. ***

    $92BB's early `RET nz` does NOT touch the carry (BIT and LD never do), so on
    paper P2's scan can inherit P1's hit and $927C `RET nc` would fall into
    $927D a second time with IX = $FD8A.  It does not, and the reason is
    $9280 `OR A` -- the heart test, three instructions into $927D -- which
    CLEARS the carry on the way past.

    A byte patch cannot isolate that: $9280's `OR A` also sets the Z flag
    $9281's `JR nz` reads, so NOPping it breaks the heart branch as well and
    P1 stops being hit at all (measured: +$5A $80, +4 $00).  So the claim is
    measured AT THE FLAG instead -- single-step the whole pass and record the
    carry at $9277, at $927C and at every entry to $927D, with the IX each
    entry carried."""
    rows = []
    h0, m0 = new()
    px, py = m0[0xFD85], m0[0xFD86]
    for p2, label in ((0x84, 'P2 DYING -- its scan RETs early'),
                      (0x80, 'P2 alive and nowhere near')):
        h, m = new()
        m[0xFD87] |= 0x80
        m[0xFD91] |= 0x80
        m[0xFD8F] = 0x08
        m[0xFD90] = 0x08
        m[0xFD99] = px
        m[0xFD9A] = py
        m[ENEMIES] = 0x80
        m[SLOTS] = 3
        m[0xFDDA] = 0x80
        m[0xFDE4] = p2
        r = h.sim.registers
        arm(h, PASS_)
        marks = {}
        hits = []
        n = 0
        while n < 4 * 10 ** 6:
            h.step(1, interrupts=False)
            p = r[PC]
            if p in (0x9277, 0x927C) and p not in marks:
                marks['%04X' % p] = r[F] & 1
            if p == 0x927D:
                hits.append('%04X' % ((r[8] << 8) | r[9]))
            if p == 0x9280:
                marks['carry_before_ORA'] = r[F] & 1
            if p == 0x9283:
                marks['carry_after_ORA'] = r[F] & 1
            if p in h.SENTINELS:
                break
            n += 1
        rows.append({'case': label, 'marks': marks, 'hit_entries': hits,
                     'p1_5a': m[0xFDDA], 'p2_5a': m[0xFDE4],
                     'p1_anim': m[0xFD84], 'p2_anim': m[0xFD8E]})
    print('(i) THE CARRY, measured at the flag')
    for r in rows:
        print('      %-34s $927D entered with IX %s; carry at $9277 %s, at $927C %s; '
              'ORA %s -> %s'
              % (r['case'], r['hit_entries'], r['marks'].get('9277'),
                 r['marks'].get('927C'), r['marks'].get('carry_before_ORA'),
                 r['marks'].get('carry_after_ORA')))
    return rows


def phase_boris():
    """THE SECOND LIST HAS A NAME.  $9121 -- inside the HURRY-UP code -- is
       `LD IY,$9250 / (IY+9) := 8 / (IY+8) := A / (IY+5) := $18 / (IY+6) := $A8
       / (IY+4) := 2`, and $9167 writes ($9257), the +7 field this scan tests.
       $9250 is BORIS, the hurry-up chaser, and he is not in the enemy table --
       which is the whole reason for a second list."""
    rows = {}
    for st in ('round1_48', 'hurryup', 'boss', 'r20_48'):
        try:
            h, m = new(st)
        except (Exception, SystemExit):
            continue
        rows[st] = {'rec': [m[LIST2 + i] for i in range(10)],
                    'active': bool(m[LIST2 + 7] & 0x80)}
    #  and the writers, found by byte-grep and confirmed here by a write watch
    #  over a HURRY-UP state driven long enough for the trigger to fire
    h, m = new('hurryup')
    h.memobj.watch(LIST2, LIST2 + 10)
    h.memobj.log.clear()
    h.run_frames(400)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    pcs = {}
    for (p, a, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
    print('(h) BORIS: $9250 across states')
    for k, v in rows.items():
        print('      %-12s %s  %s' % (k, ' '.join('%02X' % b for b in v['rec']),
                                      'ACTIVE' if v['active'] else 'inactive'))
    print('    hurryup, 400 frames: %d writes from %s' % (len(log), pcs))
    return {'states': rows, 'writes': len(log), 'writer_pcs': pcs,
            'log': [[p, a, v] for (p, a, v) in log[:24]]}


# ------------------------------------------------------------ (f) $927D's arms
def phase_hit():
    rows = []
    for heart in (0, 1):
        for f5a, label in ((0x80, 'plain'), (0x90, 'bit 4 water-carry'),
                           (0x88, 'bit 3 invulnerable')):
            h, m = new()
            m[HEART] = heart
            m[0xFDDA] = f5a
            before = [m[0xFFE1 + i] for i in range(12)]
            slots_before = m[0xAA5F]
            r = h.sim.registers
            r[8], r[9] = 0xFD, 0x80                 # IX = P1
            r[6], r[7] = 0xFD, 0x9B                 # HL = enemy slot 0's +7
            arm(h, HIT)
            run(h)
            rows.append({'heart': heart, 'f5a': f5a, 'label': label,
                         'f5a_after': m[0xFDDA], 'anim': m[0xFD84],
                         'aa5f': [slots_before, m[0xAA5F]],
                         'score_moved': [i for i in range(12)
                                         if m[0xFFE1 + i] != before[i]],
                         'corpse9': m[0xFD9D], 'corpse7': m[0xFD9B]})
    print('(f) $927D: heart / (IY+$5A) -> what moved')
    for r in rows:
        print('      heart %d, $%02X %-22s +$5A -> $%02X, (+4) $%02X, $AA5F %d->%d, '
              'score bytes %s, enemy +9 $%02X'
              % (r['heart'], r['f5a'], r['label'], r['f5a_after'], r['anim'],
                 r['aa5f'][0], r['aa5f'][1], r['score_moved'], r['corpse9']))
    return rows


def capture(jobs=15):
    out = {}
    out['mode'] = phase_mode()
    out['list2'] = phase_list2()
    out['lists'] = phase_lists()
    out['arms'] = phase_arms()
    out['carry'] = phase_carry()
    out['or_a'] = phase_or_a()
    out['boris'] = phase_boris()
    out['hit'] = phase_hit()
    out['box'] = phase_box(jobs)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
