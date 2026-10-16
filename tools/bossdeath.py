"""B2 -- THE BOSS HP BYTE, THE DEATH TAIL, AND "WELL DONE!".

THE HP BRANCH EXISTS IN NO CAPTURE.  `$9F62` is seeded 42 and only ever
decremented, and every shipped boss state holds `$2A`, so `$8E51 DEC A /
$8E52 JP p` has been measured on exactly one input.  The signed half -- the
values that make the branch go the other way -- is reachable only by poking, so
this oracle pokes ALL 256 and records which side each one takes.

AND THE TWO SEEDERS AGREE ON EVERY CAPTURED WORLD.  `$79A2` seeds the HP and
`$98B2` writes `$2A` on every round build, and since `$9F62 == $2A` everywhere,
"the seeder is $79A2" and "the seeder is $98B2" are the same claim.  **The
discriminator is `$79A3`, not `$9F62`**: it is `$79A2`'s OWN OPERAND, so the
seeder DOUBLES ITSELF -- tape `3E 05`, `$0A` on a round-80 state, `$14` on 81.

THE DEATH IS NOT A LATCH AND NOT A WAIT.  It returns Z on the frame the HP test
sees 0, and the six-point-nine seconds are spent INSIDE the call, in three
triple-nested busy loops at `$9573`.  Nothing animates: 176 display bytes in
total, and the boss still on screen is the last frame anything drew.

Usage:  python tools/bossdeath.py     (capture -> build/bossdeath_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc

FIXTURE = 'build/bossdeath_fixture.json'
BRANCH_BYTE = 0x8DC4
DECIDE = 0x8E3A
DEATH = 0x8E55          # the boss-death arm
ALIVE = 0x8ECC          # $8E52 JP p -- "not yet"
HP = 0x9F62
SEED_OP = 0x79A3        # $79A2 LD A,n -- n IS THE STATE
WAIT = 0x9573


def new(state='boss', contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, sp=0x96DD):
    """PC at `addr` from a PINNED stack pointer.  Harness.call never restores SP
       (TRAPS #42), and one of its sentinels is $FE02, which in this area is the
       boss sprite's own pixels (TRAPS #69) -- so nothing may be stepped on from
       a sentinel return."""
    r = h.sim.registers
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr


# ---------------------------------------------------------------- phase A
def phase_hp_branch():
    """all 256 values of the HP byte, and which arm each one takes.  Stopped AT
       the branch target, so the 24 million T of busy wait are never run."""
    rows = []
    for hp in range(256):
        h, m = new('boss')
        m[HP] = hp
        m[0x8E3B] = 0          # the clear latch, or $8E3D diverts first
        m[0xFED1] = 0          # the treasure latch, or $8E44 diverts first
        m[0x8609] = 0x50
        arm(h, DECIDE)
        r, n = h.run_until((DEATH, ALIVE) + tuple(h.SENTINELS),
                           limit=200000, stride=1, interrupts=False)
        pcv = h.regs[PC]
        rows.append({'hp': hp,
                     'arm': 'death' if pcv == DEATH else
                            ('alive' if pcv == ALIVE else '$%04X' % pcv),
                     'a': h.sim.registers[0]})
    dead = [r['hp'] for r in rows if r['arm'] == 'death']
    alive = [r['hp'] for r in rows if r['arm'] == 'alive']
    return {'rows': rows[:8], 'dead': dead, 'alive_first': alive[:4],
            'alive_last': alive[-4:], 'n_dead': len(dead), 'n_alive': len(alive),
            'alive_range': [min(alive), max(alive)] if alive else None,
            'a_at_alive': {str(r['hp']): r['a'] for r in rows
                           if r['arm'] == 'alive' and r['hp'] in (1, 2, 42, 128)}}


# ---------------------------------------------------------------- phase B
def phase_seeders():
    """$79A3 is $79A2's own operand, so the seeder DOUBLES ITSELF.  $9F62 is
       $2A in every captured world, so it cannot tell the two writers apart."""
    with open('build/image_tape.bin', 'rb') as f:
        img = f.read()
    out = {'tape_$79A2': list(img[0x79A2:0x79A5]), 'states': {}}
    for st in ('round1_48', 'r20_48', 'r50_48', 'boss', 'bosshit',
               'bosskilled', 'lastdia81'):
        try:
            h, m = new(st)
        except SystemExit:
            continue
        out['states'][st] = {'round': m[0x8609], 'hp_$9F62': m[HP],
                             'seed_op_$79A3': m[SEED_OP]}
    # every writer of $9F62, by ADDRESS census with the opcode classified
    h, m = new('boss')
    names = {0x32: 'LD (nn),A', 0x21: 'LD HL,nn', 0x22: 'LD (nn),HL',
             0x2A: 'LD HL,(nn)', 0x3A: 'LD A,(nn)'}
    hits = h.find_bytes(bytes([HP & 0xFF, HP >> 8]), 0x4000, 0x10000)
    out['refs_$9F62'] = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1],
                          'form': names.get(m[a - 1])} for a in hits]
    return out


# ---------------------------------------------------------------- phase C
def phase_wait_grid():
    """$9573 LD C,10 / DJNZ / DEC A / JR nz / DEC C / JR nz -- THREE counters,
       and only C is its own.  On the shipped path B is always 0 and A only ever
       3/0/2, so "a constant delay", "A is the middle count" and "the middle
       count is 3" are the same function; the (A,B) grid is the only separator."""
    rows = []
    for (a, b) in ((3, 0), (0, 0), (2, 0), (1, 1), (255, 255), (0, 1), (1, 0)):
        h, m = new('boss')
        arm(h, WAIT)
        h.sim.registers[0] = a
        h.sim.registers[2] = b          # B
        t0 = h.sim.registers[T]
        h.run_until(tuple(h.SENTINELS), limit=40_000_000, stride=1,
                    interrupts=False)
        rows.append({'a': a, 'b': b, 't': h.sim.registers[T] - t0,
                     'pc': '$%04X' % h.regs[PC]})
    return rows


# ---------------------------------------------------------------- phase D
def phase_death():
    """the death itself, driven once, with a WRITE LOG rather than a diff.

       THE DIFFERENCE MATTERS HERE.  $8E3B has to be ZERO for the death arm to be
       reached at all ($8E3C OR A / JP nz diverts first), so its "never written"
       claim CANNOT be tested by seeding a marker -- seeding it with the value a
       writer would leave is TRAPS #44, and seeding it with anything else sends
       the decision somewhere else entirely.  A write log sees the write a diff
       cannot: it records (PC, address, value) for every store, so "nobody wrote
       $8E3B" is a statement about the LOG and is true whatever the value was."""
    h, m = new('boss')
    m[HP] = 0
    m[0x8E3B] = 0             # REQUIRED: the clear latch, or $8E3D diverts
    m[0xFED1] = 0             # REQUIRED: the treasure latch, or $8E44 diverts
    m[0x8609] = 0x50          # REQUIRED: the round, or $8E4C diverts
    negatives = [0x8E3B, 0x8609, 0xFEC7, 0x9F62, 0x86CD, 0x8CB0,
                 0x9604, 0x9606, 0x9160]
    marked = [a for a in negatives if a not in (0x8E3B, 0x8609, 0x9F62)]
    for a in marked:
        m[a] = 0x5A
    for i in range(4):                         # the award needs BOTH halves
        m[0xFFE5 + i] = 0x11
        m[0xFFED + i] = 0x22
    # $8E62/$8E66 RES 7 BOTH players' +$5A and +$64.  On build/boss.pkl $FDE4 is
    # already $01, so the SECOND one writes the value that was there and is
    # invisible to any comparison (TRAPS #44).  Seeded with bit 7 SET, both show.
    # ...and seeded with OTHER BITS SET as well, because RES 7 and "clear the
    # byte" agree on $80 and $81 and differ on nothing else a shipped world has.
    m[0xFDDA] = 0xC5
    m[0xFDE4] = 0xA3
    before = bytes(m[0x4000:0x5B00])
    flags_before = (m[0xFDDA], m[0xFDE4])
    arm(h, DECIDE)
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    pcs = {}
    sent = set(h.SENTINELS)
    h.memobj.watch(0x4000, 0x10000)
    t0 = regs[T]
    n = 0
    while n < 40_000_000:
        p = regs[PC]
        if p in sent:
            break
        if p in (0x8E55, 0x8E9D, 0x8ECF, 0xD167, 0x9573, 0x8E9B, 0x80FA,
                 0x8E05, 0x8E0A, 0x802E, 0x995A, 0xA090):
            pcs['$%04X' % p] = pcs.get('$%04X' % p, 0) + 1
        op[mem[p]]()
        n += 1
    log = list(h.memobj.log)
    h.memobj.unwatch()
    after = bytes(m[0x4000:0x5B00])
    diff = [0x4000 + i for i in range(len(before)) if before[i] != after[i]]
    negset = set(negatives)
    return {'t': regs[T] - t0, 'instructions': n,
            'a': regs[0], 'f': regs[1], 'pc': '$%04X' % regs[PC],
            'pcs': pcs,
            'writes_total': len(log),
            'writes_distinct': len(set(a for (_, a, _) in log)),
            'writes_to_negatives': [['$%04X' % pc, '$%04X' % a, v]
                                    for (pc, a, v) in log if a in negset],
            # $8E56 LD A,$10 / LD ($FFEF),A writes into the PENDING field, and
            # $80FA's own cleanup at $8161 zeroes $FFED..$FFF0 two instructions
            # later -- so the write exists ONLY in the log.  An end-state
            # comparison says $8E56 never happened.
            'writes_to_pending': [['$%04X' % pc, '$%04X' % a, v]
                                  for (pc, a, v) in log if 0xFFED <= a <= 0xFFF0],
            'display_writes': len([1 for (_, a, _) in log
                                   if 0x4000 <= a < 0x5800]),
            'attr_writes': len([1 for (_, a, _) in log if 0x5800 <= a < 0x5B00]),
            'display_bytes': len([a for a in diff if a < 0x5800]),
            'display_first': ['$%04X' % a for a in diff[:4]],
            'attr_cells': ['$%04X' % a for a in diff if a >= 0x5800],
            'attr_values': {'$%04X' % a: m[a] for a in diff if a >= 0x5800},
            'negatives_after': {'$%04X' % a: m[a] for a in negatives},
            'negatives_marked': ['$%04X' % a for a in marked],
            'flags_before': list(flags_before),
            'flags_after': [m[0xFDDA], m[0xFDE4]],
            'score_p1': [m[0xFFE5 + i] for i in range(4)],
            'pending_p1': [m[0xFFED + i] for i in range(4)],
            'award_index_$9F09': m[0x9F09]}


# ---------------------------------------------------------------- phase E
def phase_wrap():
    """$8E9D with HL = $48FA, so BOTH eight-bit walks wrap inside their pages.

       $8E9D is PUSH HL / CALL $A090 (H -> its attribute page) / CALL $995A
       (B cells, INC L) / POP HL / JP $802E (B glyphs, INC L).  Both walks are
       EIGHT BIT and the shipped call starts at $484B with B = 11, which cannot
       reach either wrap: the only way to see them is to place the call where
       they happen.  A sixteen-bit walk writes into the NEXT page and the two
       models agree everywhere else."""
    out = {}
    for (hl, b) in ((0x484B, 11), (0x48FA, 11)):
        h, m = new('boss')
        h.memobj.watch(0x4000, 0x5B00)
        arm(h, 0x8E9D)
        r = h.sim.registers
        r[6], r[7] = hl >> 8, hl & 0xFF        # H, L
        r[2] = b                               # B
        r[0] = 0x85                            # A -- the attribute, before $995A's OR $40
        r[8], r[9] = 0x9A, 0x27                # IX = $9A27 -- IXh IS 8, IXl IS 9
        #   (getting these the wrong way round pointed IX at $279A in ROM, and
        #   $802E, which is bounded by a ZERO TERMINATOR and not by B, then drew
        #   21 glyphs instead of 11.  The attribute count comes from B and the
        #   GLYPH count from the string: two different bounds in one call.)
        h.run_until(tuple(h.SENTINELS), limit=500000, stride=1, interrupts=False)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        out['$%04X' % hl] = {
            'b': b,
            'attr_addrs': ['$%04X' % a for (_, a, _) in log if a >= 0x5800],
            'attr_values': sorted(set(v for (_, a, v) in log if a >= 0x5800)),
            'glyph_addrs': ['$%04X' % a for (_, a, _) in log if a < 0x5800],
            'writes': len(log),
        }
    return out


# ---------------------------------------------------------------- phase F
def phase_award_who():
    """$8E5F LD A,($9F09) -- WHICH player is paid.  ($9F09) is 1 in all four
       shipped boss states, so "the award goes to P1" and "the award goes to
       ($9F09)" are the same claim there.  Poked 0, 1, 2 and 3: the score base
       is $FFE1 + 4p, so p = 0 pays the HIGH SCORE slot and p = 3 pays nobody
       ($80FA CP 3 / RET nc).

       AND INDEX 0'S GUARD IS NOT A PLAYER BYTE.  $8108 LD DE,$FD7D / ADD HL,DE
       with HL = 10*A puts the BIT 7 test on $FD87 for 1 and $FD91 for 2 -- but
       on $FD7D for 0, three bytes BELOW the entity table.  It reads $A0 on
       every state on disk, so index 0 always passes a guard that belongs to no
       player.  The port carries zeros there and index 0 is unreachable in play
       ($9F09 is 1 in all four boss states), so the gate seeds it and says so."""
    out = []
    for who in (0, 1, 2, 3):
        h, m = new('boss')
        m[HP] = 0
        m[0x8E3B] = 0
        m[0xFED1] = 0
        m[0x8609] = 0x50
        m[0x9F09] = who
        m[0xFD87] |= 0x80
        m[0xFD91] |= 0x80
        for i in range(16):
            m[0xFFE1 + i] = 0x11
        for i in range(4):
            m[0xFFED + i] = 0x22
        # driven through THE WHOLE DEATH, not through $80FA alone: $8E56 writes
        # $10 into $FFEF before the award reads the pending field, so a driver
        # that starts at $80FA measures a different sum and the engine, which
        # runs the death, disagrees with it by exactly that $10.
        arm(h, DECIDE)
        h.run_until(tuple(h.SENTINELS), limit=40_000_000, stride=1,
                    interrupts=False)
        out.append({'who': who, 'guard_$FD7D': m[0xFD7D],
                    'high': [m[0xFFE1 + i] for i in range(4)],
                    'p1': [m[0xFFE5 + i] for i in range(4)],
                    'p2': [m[0xFFE9 + i] for i in range(4)],
                    'pending': [m[0xFFED + i] for i in range(4)]})
    return out


def main():
    fx = {'hp_branch': phase_hp_branch(),
          'seeders': phase_seeders(),
          'wait_grid': phase_wait_grid(),
          'death': phase_death(),
          'wrap': phase_wrap(),
          'award_who': phase_award_who()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    hb = fx['hp_branch']
    print('HP branch: %d ALIVE (%s..%s), %d DEAD -- dead set %s'
          % (hb['n_alive'], hb['alive_range'][0], hb['alive_range'][1],
             hb['n_dead'], (str(hb['dead'][:3]) + '...' + str(hb['dead'][-3:]))))
    print('A at $8ECC:', hb['a_at_alive'])
    sd = fx['seeders']
    print('$79A2 tape:', ['%02X' % b for b in sd['tape_$79A2']])
    for k, v in sd['states'].items():
        print('   %-12s round $%02X  $9F62=%02X  $79A3=%02X'
              % (k, v['round'], v['hp_$9F62'], v['seed_op_$79A3']))
    print('$9F62 refs:', [r['at'] + ' ' + str(r['form']) for r in sd['refs_$9F62']])
    print('$9573 grid:', [(r['a'], r['b'], r['t']) for r in fx['wait_grid']])
    d = fx['death']
    print('death: T=%d  A=%02X F=%02X  display %d WRITES vs %d CHANGED, attrs %s = %s'
          % (d['t'], d['a'], d['f'], d['display_writes'], d['display_bytes'],
             d['attr_cells'],
             sorted(set(d['attr_values'].values()))))
    print('   pcs', d['pcs'])
    print('   writes %d (%d distinct); to the NINE negatives: %s'
          % (d['writes_total'], d['writes_distinct'], d['writes_to_negatives']))
    print('   negatives after', d['negatives_after'])
    for k, v in fx['wrap'].items():
        print('   $8E9D from %s: attrs %s..%s (%d) values %s'
              % (k, v['attr_addrs'][0], v['attr_addrs'][-1],
                 len(v['attr_addrs']), v['attr_values']))
        print('       glyph pages %s'
              % sorted(set(a[:3] for a in v['glyph_addrs'])))
    for r in fx['award_who']:
        print('   $9F09 = %d -> high %s p1 %s p2 %s pending %s'
              % (r['who'], r['high'], r['p1'], r['p2'], r['pending']))
    print('   flags %s -> %s  score %s  pending %s'
          % (d['flags_before'], d['flags_after'], d['score_p1'], d['pending_p1']))


if __name__ == '__main__':
    main()
