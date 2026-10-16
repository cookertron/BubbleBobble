"""B6 -- THE ELEMENTAL BOLT: the only thing that damages the boss.

THE HIT WINDOW IS NOT A BOX, AND IT HAD NEVER BEEN MEASURED.  $9F2D reads the
bolt's tile X and accepts it on TWO columns -- bossX and bossX-3 -- then reads
its tile Y and accepts THREE rows -- bossY-1, bossY-2, bossY-3.  Every AABB
model agrees on the tiles it happens to contain and disagrees at bossX+1 and
bossX+2, which must MISS, and at row bossY, which must MISS.  THE SEPARATING
INPUT IS A BOLT AT (bossX+1, bossY-2): inside the boss's own 4x4 sprite, and not
a hit.

AND ONE POSITION CANNOT SERVE.  At bossX = 2 the bossX-3 column is off-screen,
so a sweep taken there alone passes a port that implements offset 0 only.  That
is TRAPS #49 for the second time in this range, so the sweep runs at THREE
positions -- (20,9) and the bounce's own bounds (2,3) and (26,19).

TWO MORE THINGS NO CAPTURE SHOWS:
  * the bolt DOES NOT MOVE on the frame it damages the boss.  $9F29 pushed
    $9ED0 (the physics) and $9F57 `LD HL,$9EE7 / EX (SP),HL / RET` replaces it
    with the award tail, so the physics is skipped -- but the draw runs either
    way, so an end-of-frame comparison sees nothing.
  * the boss hit SUPPRESSES the enemy kill.  $9F51 stashes carry SET through
    EX AF,AF', so the shared tail's $9EFE `CALL nc,$8BC2` does not fire; the
    enemy path stashes CLEAR at $9EE5.  On round 80 the enemy scan is jumped
    entirely ($9E9E), so "the SCF suppressed the kill" and "there was no enemy
    to kill" are the same observation -- the discriminator is the SAME bolt over
    the SAME enemy on round 20 against round 80.

Usage:  python tools/bolt.py       (capture -> build/bolt_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bolt_fixture.json'
BRANCH_BYTE = 0x8DC4
HITTEST = 0x9F29
PHYSICS = 0x9D77
TICK = 0x9E50
ALLOC = 0x941B
ARM = 0x93DC
ERASE16 = 0xA314
DRAW16 = 0xA2D5
STRIDE = 0x9D83          # the third ADD A,A -- an OPCODE byte that is also state
HP = 0x9F62
BOSS_X, BOSS_Y = 0xA8DB, 0xA839
SLOT0, SLOT1 = 0xFDEE, 0xFDF8
AWARD_OP = 0x9F09


def new(state='boss', contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, sp=0x96DD):
    r = h.sim.registers
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, limit=400000):
    h.run_until(tuple(h.SENTINELS), limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('no sentinel -- PC $%04X' % h.regs[PC])


def set_iy(h, v):
    r = h.sim.registers
    r[10], r[11] = v >> 8, v & 0xFF          # IYh, IYl


# ---------------------------------------------------------------- phase A
def phase_window():
    """the hit window, swept 11x11 at THREE boss positions, with the HP byte
       seeded to a value the decrement changes VISIBLY and compared on every
       row -- including the ones where nothing is expected (TRAPS #44)."""
    out = {}
    for (bx, by) in ((20, 9), (2, 3), (26, 19)):
        h, m = new('boss')
        m[BOSS_X], m[BOSS_Y] = bx, by
        hits = []
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                tx, ty = bx + dx, by + dy
                if not (0 <= tx < 32 and 0 <= ty < 24):
                    continue
                m[HP] = 0x2A
                m[SLOT0 + 5] = (tx * 8) & 0xFF
                m[SLOT0 + 6] = (ty * 8) & 0xFF
                m[SLOT0 + 7] = 0x80
                set_iy(h, SLOT0)
                arm(h, HITTEST)
                # stop at the two exits rather than running the physics or the
                # award tail: this phase is about the DECISION
                h.run_until((0x9F51, 0x9ED0) + tuple(h.SENTINELS),
                            limit=200000, stride=1, interrupts=False)
                hit = h.regs[PC] == 0x9F51
                if hit:
                    hits.append([dx, dy])
                elif m[HP] != 0x2A:
                    raise SystemExit('HP moved on a miss at %d,%d' % (dx, dy))
        out['%d_%d' % (bx, by)] = {'bx': bx, 'by': by, 'offsets': hits,
                                   'n': len(hits)}
    # ...and the DECREMENT itself, once, on a hit
    h, m = new('boss')
    m[BOSS_X], m[BOSS_Y] = 20, 9
    m[HP] = 0x2A
    m[SLOT0 + 5], m[SLOT0 + 6], m[SLOT0 + 7] = 20 * 8, 8 * 8, 0x80
    set_iy(h, SLOT0)
    arm(h, HITTEST)
    h.run_until((0x9F57,) + tuple(h.SENTINELS), limit=200000, stride=1,
                interrupts=False)
    out['decrement'] = {'hp_before': 0x2A, 'hp_after': m[HP],
                        'carry_stashed': h.sim.registers[1] & 1}
    return out


# ---------------------------------------------------------------- phase B
def phase_alloc():
    """$941B over sixteen rows.  BOTH slots seeded $5A, because "dropped" and
       "wrote the same values" are otherwise identical."""
    rows = []
    for st in ('boss', 'r20_48'):
        for (s0, s1) in ((0x00, 0x00), (0x80, 0x00), (0x00, 0x80), (0x80, 0x80)):
            for p in (1, 2):
                h, m = new(st)
                for s in (SLOT0, SLOT1):
                    for i in range(10):
                        m[s + i] = 0x5A
                m[SLOT0 + 7], m[SLOT1 + 7] = s0, s1
                # BIT 3 SET IN BOTH: $F8 and $F0 differ only there, and $93/$57
                # have it clear -- so the first seeding could not tell the two
                # masks apart at all.
                m[0xFFF7], m[0xFFF8] = 0x9B, 0x5F       # NOT $F8-aligned, bit 3 set
                m[0xFFFA] = p
                m[0xFD87] = 0xE1                        # P1 facing bit 0 = 1
                m[0xFD91] = 0x60                        # P2 facing bit 0 = 0
                # ...and $FD8D, which `$FD87 + 6p` would reach, seeded to the
                # OPPOSITE of $FD91's bit 0, or the two strides agree.
                m[0xFD8D] = 0xE1
                arm(h, ALLOC)
                run(h)
                rows.append({'state': st, 'round': m[0x8609],
                             's0_in': s0, 's1_in': s1, 'p': p,
                             'slot0': [m[SLOT0 + i] for i in range(10)],
                             'slot1': [m[SLOT1 + i] for i in range(10)]})
    return rows


# ---------------------------------------------------------------- phase C
def phase_physics():
    """$9D77: (IY+7) bit 0 picks the sign, THREE `ADD A,A` scale it to 8, and
       the add to (IY+5) is EIGHT BIT with no clamp.  $9D83 is the third one --
       an OPCODE byte that is also state, which B8's kind-1 handler pokes to
       $00 to halve the stride -- and the tape and the round-80 dump BOTH read
       $87, so no image diff can ever find it."""
    out = {'tape_9d83': None, 'rows': []}
    with open('build/image_tape.bin', 'rb') as f:
        out['tape_9d83'] = f.read()[STRIDE]
    for stride in (0x87, 0x00):
        for facing in (0, 1):
            for x in (0x50, 0x00, 0xF8, 0x04):
                h, m = new('boss')
                m[STRIDE] = stride
                m[SLOT0 + 5] = x
                m[SLOT0 + 7] = 0x80 | facing
                set_iy(h, SLOT0)
                arm(h, PHYSICS)
                run(h)
                out['rows'].append({'stride': stride, 'facing': facing,
                                    'x_in': x, 'x_out': m[SLOT0 + 5]})
    return out


# ---------------------------------------------------------------- phase D
def phase_bounds():
    """$9ED3's bounds despawn before the eight-bit wrap can be reached, so the
       wrap is a METHOD-level fact and the bounds are the play-level one."""
    rows = []
    for x in (0x00, 0x08, 0x0E, 0x0F, 0x10, 0xE6, 0xE7, 0xE8, 0xF8):
        h, m = new('boss')
        m[SLOT0 + 5] = x
        m[SLOT0 + 6] = 0x50
        m[SLOT0 + 7] = 0x80
        m[STRIDE] = 0x87
        set_iy(h, SLOT0)
        arm(h, 0x9ED3)
        h.run_until((0x9F13, 0x9EDE) + tuple(h.SENTINELS), limit=200000,
                    stride=1, interrupts=False)
        rows.append({'x': x, 'despawn': h.regs[PC] == 0x9F13})
    return rows


# ---------------------------------------------------------------- phase E
def phase_blit():
    """$A314's geometry in a BUILT world -- clear the display, fill the shadow
       with a marker, and read back which bytes moved.  And the $FD00 ROM
       SINKS, whose only visible signature is the byte COUNT."""
    out = {}
    for (name, x, y) in (('aligned', 0x50, 0x50), ('subrow', 0x50, 0x54),
                         ('row0', 0x50, 0x00), ('row1', 0x50, 0x08),
                         ('row23', 0x50, 0xB8), ('row23_sub', 0x50, 0xBC),
                         ('x_f8', 0xF8, 0x50), ('x_ff', 0xFF, 0x50)):
        h, m = new('boss')
        for a in range(0x4000, 0x5800):
            m[a] = 0x00
        for a in range(0xE000, 0xF800):
            m[a] = 0xC3                       # a marker the display never holds
        m[SLOT0 + 5], m[SLOT0 + 6] = x, y
        set_iy(h, SLOT0)
        h.memobj.watch(0x4000, 0x5800)
        arm(h, ERASE16)
        run(h)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        out['erase_' + name] = {
            'x': x, 'y': y, 'writes': len(log),
            'pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log)),
            # the CHARACTER ROWS, which is what the sub-row pairing is about:
            # a page set cannot show it because a 16-row sprite spans eight
            # pages whether it straddles two char rows or three.
            'char_rows': sorted(set(((a - 0x4000) >> 11) * 8 +
                                    (((a - 0x4000) >> 5) & 7)
                                    for (_, a, _) in log)),
            'first': '$%04X' % log[0][1] if log else None,
            'x_after': m[SLOT0 + 5]}
        g, mm = new('boss')
        for a in range(0x4000, 0x5800):
            mm[a] = 0x00
        mm[SLOT0 + 5], mm[SLOT0 + 6] = x, y
        set_iy(g, SLOT0)
        g.memobj.watch(0x4000, 0x5800)
        arm(g, DRAW16)
        run(g)
        log2 = list(g.memobj.log)
        g.memobj.unwatch()
        out['draw_' + name] = {
            'x': x, 'y': y, 'writes': len(log2),
            'char_rows': sorted(set(((a - 0x4000) >> 11) * 8 +
                                    (((a - 0x4000) >> 5) & 7)
                                    for (_, a, _) in log2)),
            'pages': sorted(set('$%02X' % (a >> 8) for (_, a, _) in log2))}
    return out


# ---------------------------------------------------------------- phase F
def phase_suppression():
    """THE SAME BOLT OVER THE SAME ENEMY ON ROUND 20 AND ROUND 80.

       $9F51's SCF is stashed through EX AF,AF' and the shared tail's
       $9EFE `CALL nc,$8BC2` therefore does not fire.  On round 80 the enemy
       scan is jumped entirely, so the suppression and the absence of an enemy
       are the same observation there -- which is why both rounds are driven."""
    out = {}
    for st in ('boss', 'r20_48'):
        h, m = new(st)
        counts = {}
        m[SLOT0 + 5], m[SLOT0 + 6], m[SLOT0 + 7] = 20 * 8, 8 * 8, 0x80
        m[SLOT1 + 7] = 0x00
        if st == 'boss':
            m[BOSS_X], m[BOSS_Y] = 20, 9
        # TWO GATES stand in front of the slots and both are self-modified:
        # $9E56 CP n (n IS $9E57) is a B0-shaped EDGE DETECTOR on ($8DBD), and
        # $9E5C LD A,n (n IS $9E5D) is an every-other-frame toggle.  Unseeded,
        # $9E50 RETs before doing anything at all -- which is what an unseeded
        # drive of this routine measures: nothing.
        m[0x9E57] = (m[0x8DBD] ^ 0xFF) & 0xFF
        m[0x9E5D] = 0x00
        m[0x7E0E] = 3                      # LIGHTNING, the class that owns $FDEE
        set_iy(h, SLOT0)
        arm(h, TICK)
        sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
        sent = set(h.SENTINELS)
        n = 0
        while n < 400000:
            p = regs[PC]
            if p in sent:
                break
            if p in (0x9E9E, 0x9F29, 0x9EA6, 0x9EDE, 0x9EE7, 0x9EFE, 0x8BC2,
                     0x9F51, 0x9ED0, 0x9D77, 0xA2D5, 0x9F13, 0x9E71):
                counts['$%04X' % p] = counts.get('$%04X' % p, 0) + 1
            op[mem[p]]()
            n += 1
        out[st] = {'round': m[0x8609], 'counts': counts, 'elem': m[0x7E0E],
                   'hp': m[HP], 'x_after': m[SLOT0 + 5],
                   'award_op': m[AWARD_OP],
                   'pending': [m[0xFFED + i] for i in range(4)]}
    return out


# ---------------------------------------------------------------- phase G
def phase_negatives():
    """the censuses and the reads this entry stands on."""
    h, m = new('boss')
    names = {0x32: 'LD (nn),A', 0x3A: 'LD A,(nn)', 0x21: 'LD HL,nn',
             0xCD: 'CALL', 0xC3: 'JP', 0xFD: 'IY-prefixed'}
    out = {}
    for (label, addr) in (('$9F09', AWARD_OP), ('$FDEE', SLOT0)):
        hits = h.find_bytes(bytes([addr & 0xFF, addr >> 8]), 0x4000, 0x10000)
        out[label] = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1],
                       'form': names.get(m[a - 1])} for a in hits]
    # $A33D/$A349/$A355 are recomputed at EVERY entry, not carried
    with open('build/image_tape.bin', 'rb') as f:
        tape = f.read()
    out['recomputed'] = {'tape': [tape[0xA33D], tape[0xA349], tape[0xA355]],
                         'live': [m[0xA33D], m[0xA349], m[0xA355]]}
    g, mm = new('boss')
    before = [mm[0xA33D], mm[0xA349], mm[0xA355]]
    mm[0xA33D] = mm[0xA349] = mm[0xA355] = 0x5A
    mm[SLOT0 + 5], mm[SLOT0 + 6] = 0x50, 0x50
    set_iy(g, SLOT0)
    arm(g, ERASE16)
    run(g)
    out['recomputed']['after_poison'] = [mm[0xA33D], mm[0xA349], mm[0xA355]]
    out['recomputed']['before'] = before
    # the award: $0100 into the pending field, paid to ($9F09)
    return out


def main():
    fx = {'window': phase_window(),
          'alloc': phase_alloc(),
          'physics': phase_physics(),
          'bounds': phase_bounds(),
          'blit': phase_blit(),
          'suppression': phase_suppression(),
          'negatives': phase_negatives()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    for k, v in fx['window'].items():
        if k == 'decrement':
            print('  decrement: HP %02X -> %02X, carry %d'
                  % (v['hp_before'], v['hp_after'], v['carry_stashed']))
        else:
            print('  window at (%2d,%2d): %d hits %s'
                  % (v['bx'], v['by'], v['n'], v['offsets']))
    a = [r for r in fx['alloc'] if r['s0_in'] == 0 and r['p'] == 1][0]
    print('alloc slot0 free, P1:', a['slot0'])
    print('  and when both are taken:',
          [r['slot0'][5:8] for r in fx['alloc'] if r['s0_in'] and r['s1_in']][:2])
    print('physics tape $9D83 = $%02X' % fx['physics']['tape_9d83'])
    for r in fx['physics']['rows'][:8]:
        print('   stride $%02X facing %d: X $%02X -> $%02X'
              % (r['stride'], r['facing'], r['x_in'], r['x_out']))
    print('bounds:', [(hex(r['x']), r['despawn']) for r in fx['bounds']])
    for k, v in fx['blit'].items():
        print('  %-16s %d writes, pages %s' % (k, v['writes'], v['pages']))
    for k, v in fx['suppression'].items():
        print('  suppression %-8s round %d: %s' % (k, v['round'], v['counts']))
    print('negatives:', {k: [r['at'] + ' ' + str(r['form']) for r in v]
                         for k, v in fx['negatives'].items() if k != 'recomputed'})
    print('   recomputed:', fx['negatives']['recomputed'])


if __name__ == '__main__':
    main()
