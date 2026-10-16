"""B5 -- THE OVERLAP TEST, $A98F/$A990, AND THE DAMAGE TAIL.

THE COMPARATOR IS TWO BYTES OF LIVE STATE SITTING INSIDE ITS OWN CALLER.
$A98F/$A990 are `37 C9` -- SCF / RET -- on the tape, which makes EVERY position
an overlap, and `00 00` -- NOP / NOP -- in the round-80 dump, which lets control
fall through into the real comparator at $A991.  There is no sixteen-bit
reference to $A98F anywhere in 64K except the CALL's own operand, so no grep
finds this; it was found by poisoning the pair and letting a write-watch name
the decrementer.

EVERY BOSS CAPTURE ALREADY HOLDS `00 00`, so:
  * seeding `00 00` is TRAPS #44 -- the write becomes a no-op and "the game
    zeroed the pair" and "the port never had the pair" are the same observation;
  * the DECAY can only be measured from a state where the pair is still alive,
    which means round 1 and a long run;
  * and "the comparator is correct" and "the comparator was deleted" are the
    same claim unless the pair is forced to `00 00` and the fixture says so.

ONE POSITION IS NOT A TEST OF A BOX (TRAPS #49), so the accept set is swept over
all 32x24 tiles at TWO boss positions -- (20,9) and (2,3).  The second is the
one that matters: at the left wall any accept set that extended leftward would
be truncated, and the truncation would look like a correct answer.

Usage:  python tools/bossoverlap.py    (-> build/bossoverlap_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bossoverlap_fixture.json'
BRANCH_BYTE = 0x8DC4
OVERLAP = 0xA969
DRIVER = 0xA97D
CMP = 0xA98F
KILL = 0x927D
DECAY = 0xAAA1               # the DEC (HL) in the $AA60 slot walker
BOSS_Y, BOSS_X = 0xA839, 0xA8DB
P1, P2 = 0xFD80, 0xFD8A
HOLDOFF = 0xA891


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


def call(h, addr):
    arm(h, addr)
    h.run_until(tuple(h.SENTINELS), limit=200000, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('no sentinel -- PC $%04X' % h.regs[PC])
    return h.sim.registers[1] & 1          # the CARRY flag


def frames(h, n, watch=None):
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    for f in range(n):
        tgt = regs[T] + fd
        while regs[T] < tgt:
            p = regs[PC]
            if watch is not None:
                watch(p, f)
            if mem[p] == 0x76 and regs[IFF]:
                h._fast_halt()
                continue
            op[mem[p]]()
            if regs[IFF] and regs[T] % fd < ia:
                sim.accept_interrupt(regs, mem, p)


# ---------------------------------------------------------------- phase A
def phase_accept_set():
    """the accept set as a FULL 32x24 tile sweep, at TWO boss positions.

       The pair is forced `00 00` and the fixture says so: with `37 C9` in place
       every position is an overlap and a correct comparator and a deleted one
       are the same function."""
    out = {}
    for (bx, by) in ((20, 9), (2, 3)):
        h, m = new('boss')
        m[CMP], m[CMP + 1] = 0x00, 0x00
        m[BOSS_X], m[BOSS_Y] = bx, by
        m[P2 + 7] &= 0x7F                       # P2 OUT, so only P1 answers
        m[P1 + 7] |= 0x80
        m[P1 + 0x5A] &= ~0x04 & 0xFF
        hits = []
        for ty in range(24):
            for tx in range(32):
                m[P1 + 6] = (ty * 8) & 0xFF     # (IX+6) is the Y PIXEL
                m[P1 + 5] = (tx * 8) & 0xFF     # (IX+5) the X PIXEL
                if call(h, OVERLAP):
                    hits.append([tx, ty])
        out['%d_%d' % (bx, by)] = {
            'bx': bx, 'by': by, 'hits': hits, 'n': len(hits),
            'offsets': sorted({(x - bx, y - by) for (x, y) in hits}),
            'pair': [m[CMP], m[CMP + 1]]}
    return out


# ---------------------------------------------------------------- phase B
def phase_pair_ledger():
    """the two states of the pair, pinned to the image ledger, and the decay --
       which no boss capture can show, because every one already holds `00 00`.
       Driven on ROUND 1 and on ROUND 20, because ($AA57) is enemies + 2 and the
       histogram's shape is a function of it: a decay rate measured at one enemy
       count is not the rule."""
    with open('build/image_tape.bin', 'rb') as f:
        tape = f.read()
    out = {'tape': [tape[CMP], tape[CMP + 1]], 'states': {}, 'decay': {}}
    for st in ('boss', 'bosshit', 'bosskilled', 'bossspawn', 'round1_48', 'r20_48'):
        h, m = new(st)
        out['states'][st] = {'pair': [m[CMP], m[CMP + 1]],
                             'aa57': m[0xAA57],
                             'holdoff': [m[HOLDOFF + i] for i in range(8)]}
    for (st, nf) in (('play1p48', 600), ('r20_48', 600)):
        h, m = new(st)
        m[CMP], m[CMP + 1] = 0x37, 0xC9        # ALIVE -- the experiment
        hist, zero_at = {}, {}

        def watch(p, f, h=h, hist=hist, zero_at=zero_at, m=m):
            if p == DECAY:
                hl = h.sim.registers[H] << 8 | h.sim.registers[L]
                k = '$%04X' % hl
                hist[k] = hist.get(k, 0) + 1
                if hl in (CMP, CMP + 1) and m[hl] == 1:
                    zero_at.setdefault(k, f)

        frames(h, nf, watch)
        out['decay'][st] = {'frames': nf, 'round': m[0x8609], 'aa57': m[0xAA57],
                            'hist': hist, 'zero_at': zero_at,
                            'pair_after': [m[CMP], m[CMP + 1]]}
    return out


# ---------------------------------------------------------------- phase C
def phase_causal():
    """THE ROW THAT MAKES THE ENTRY WORTH ITS RISK: with the pair alive, a
       player NOWHERE NEAR the boss dies anyway."""
    out = {}
    for pair in ((0x00, 0x00), (0x37, 0xC9)):
        h, m = new('boss')
        m[CMP], m[CMP + 1] = pair
        m[BOSS_X], m[BOSS_Y] = 2, 3
        m[P1 + 5], m[P1 + 6] = 200, 150         # nowhere near it
        m[P1 + 7] |= 0x80
        m[P1 + 0x5A] = 0x80                     # in play, not dying, not carried
        m[P1 + 4] = 0x00
        m[P2 + 7] &= 0x7F
        m[0xFED0] = 0
        arm(h, 0xAA2C)                          # the body's own CALL $A969
        h.run_until(tuple(h.SENTINELS), limit=200000, stride=1, interrupts=False)
        out['%02X%02X' % pair] = {'p1_5a': m[P1 + 0x5A], 'p1_4': m[P1 + 4],
                                  'boss': [m[BOSS_X], m[BOSS_Y]],
                                  'player_px': [m[P1 + 5], m[P1 + 6]]}
    return out


# ---------------------------------------------------------------- phase D
def phase_kill():
    """$927D over the states of (IX+$5A) that reach it, and with ($FED0) poked
       to the value no captured world holds."""
    rows = []
    for (name, fed0, f5a) in (('normal', 0, 0x80), ('carried', 0, 0x90),
                              ('dying', 0, 0x88), ('already hit', 0, 0x84),
                              ('fed0 set', 1, 0x80),
                              # bit 7 CLEAR: every other row already has it set,
                              # so `SET 7` is invisible in all of them
                              ('bit7 clear', 0, 0x00),
                              ('carried only', 0, 0x10),
                              ('dying only', 0, 0x08)):
        h, m = new('boss')
        m[0xFED0] = fed0
        m[P1 + 0x5A] = f5a
        m[P1 + 4] = 0x5A
        r = h.sim.registers
        arm(h, KILL)
        r[8], r[9] = P1 >> 8, P1 & 0xFF          # IX = $FD80
        h.run_until(tuple(h.SENTINELS), limit=400000, stride=1, interrupts=False)
        rows.append({'case': name, 'fed0': fed0, 'f5a_in': f5a,
                     'f5a_out': m[P1 + 0x5A], 'p4_out': m[P1 + 4],
                     'pc': '$%04X' % h.regs[PC]})
    return rows


# ---------------------------------------------------------------- phase E
def phase_negatives():
    """the arm nothing reaches, the dead compares, and the census."""
    h, m = new('boss')
    counts = {}
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    tgt = regs[T] + 240 * fd
    while regs[T] < tgt:
        p = regs[PC]
        if p in (0xAA2C, 0xA969, 0xAA35, 0x927D, 0xA991, 0xA9A3, 0xA9AF, 0xA9AC):
            counts['$%04X' % p] = counts.get('$%04X' % p, 0) + 1
        if mem[p] == 0x76 and regs[IFF]:
            h._fast_halt()
            continue
        op[mem[p]]()
        if regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, p)
    # the census of $A98F: the CALL's own operand and nothing else
    g, mm = new('boss')
    refs = g.find_bytes(bytes([CMP & 0xFF, CMP >> 8]), 0x4000, 0x10000)
    # ...and of $FED0, the kill's diverter
    fed0 = [a - 1 for a in g.find_bytes(bytes([0xD0, 0xFE]), 0x4000, 0x10000)]
    names = {0x32: 'LD (nn),A', 0x3A: 'LD A,(nn)', 0xCD: 'CALL', 0x21: 'LD HL,nn'}
    # THE DEAD COMPARES, enumerated rather than transliterated: after the first
    # four tests A is the tile and D is boss+3, so INC A / CP D can only match a
    # tile the earlier tests already accepted -- unless INC A wraps, and the
    # tile is `AND $1F`, so it never exceeds 31.
    dead = {'tile_max': max((t >> 3) & 0x1F for t in range(256)),
            'wrap_needs': 255}
    return {'counts_240_frames': counts,
            'refs_a98f': [{'at': '$%04X' % (a - 1), 'opcode': mm[a - 1],
                           'form': names.get(mm[a - 1])} for a in refs],
            'refs_fed0': [{'at': '$%04X' % a, 'opcode': mm[a],
                           'form': names.get(mm[a])} for a in fed0],
            'dead_compares': dead}


# ---------------------------------------------------------------- phase F
def phase_pair_corners():
    """the four corner values of the pair, driven through $A969.

       `37 C9` is SCF / RET -- every position hits.  `00 00` is NOP / NOP and
       falls through to the comparator.  The other two corners are what a gate
       testing ONE byte, or testing "non-zero", cannot tell apart:
         `37 00` is SCF / NOP -- it ALSO falls through, and the carry it set is
           discarded by $9F5C's AND $1F, so it is the comparator;
         `00 C9` is NOP / RET -- it returns with the CALLER's carry, which
           $A97D cleared for the Y axis, so it is "always miss".
       The last is UNREACHABLE: the decay takes $A98F to zero at frame 137 while
       $A990 is still around $89, so `00 C9` never exists.  Measured anyway, so
       that the port's model can be compared against the truth and the gap
       DECLARED rather than discovered later."""
    out = {}
    for pair in ((0x37, 0xC9), (0x37, 0x00), (0x00, 0xC9), (0x00, 0x00)):
        h, m = new('boss')
        m[CMP], m[CMP + 1] = pair
        m[BOSS_X], m[BOSS_Y] = 20, 9
        m[P2 + 7] &= 0x7F
        m[P1 + 7] |= 0x80
        hits = []
        for (tx, ty) in ((20, 9), (23, 12), (24, 9), (0, 0), (2, 3)):
            m[P1 + 5], m[P1 + 6] = (tx * 8) & 0xFF, (ty * 8) & 0xFF
            hits.append([tx, ty, call(h, OVERLAP)])
        out['%02X%02X' % pair] = {'pair': list(pair), 'probes': hits,
                                  'n_hit': sum(1 for p_ in hits if p_[2])}
    return out


def main():
    fx = {'accept': phase_accept_set(),
          'pair': phase_pair_ledger(),
          'causal': phase_causal(),
          'kill': phase_kill(),
          'negatives': phase_negatives(),
          'corners': phase_pair_corners()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    for k, v in fx['accept'].items():
        print('  accept at (%d,%d): %d tiles, offsets %s'
              % (v['bx'], v['by'], v['n'], v['offsets']))
    print('pair on tape:', ['%02X' % b for b in fx['pair']['tape']])
    for k, v in fx['pair']['states'].items():
        print('   %-12s pair %s  $AA57=%d  holdoff %s'
              % (k, ['%02X' % b for b in v['pair']], v['aa57'], v['holdoff']))
    for k, v in fx['pair']['decay'].items():
        print('   decay %-10s round %d, $AA57=%d, hist %s, zero at %s, after %s'
              % (k, v['round'], v['aa57'], v['hist'], v['zero_at'],
                 ['%02X' % b for b in v['pair_after']]))
    print('causal:', fx['causal'])
    for r in fx['kill']:
        print('   kill %-12s $FED0=%d  +$5A %02X -> %02X, +4 -> %02X'
              % (r['case'], r['fed0'], r['f5a_in'], r['f5a_out'], r['p4_out']))
    for k, v in fx['corners'].items():
        print('   pair %s -> %d of 5 probes hit: %s'
              % (k, v['n_hit'], [(p[0], p[1], p[2]) for p in v['probes']]))
    print('negatives:', fx['negatives']['counts_240_frames'])
    print('   $A98F refs:', [r['at'] + ' ' + str(r['form'])
                             for r in fx['negatives']['refs_a98f']])
    print('   $FED0 refs:', [r['at'] + ' ' + str(r['form'])
                             for r in fx['negatives']['refs_fed0']])


if __name__ == '__main__':
    main()
