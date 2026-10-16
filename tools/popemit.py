"""B7 -- THE POP-EMIT TAIL AND THE AWARD FORK.

THE POPPED BUBBLE'S CLASS TRAVELS THROUGH AN OPCODE.  `$B6F5` writes the
bubble's `+9` into `$B742` -- the operand of `$B741 LD A,3` -- and then zeroes
`+9`, so the class reaches the fork inside an instruction.  **The tape and the
round-80 dump BOTH hold `$03` there**, so a provenance diff between the two
images shows nothing whatever; only a world whose `($7E0E)` is not 3 separates
"the operand is a constant" from "the operand is the class".

AND THE AWARD FIELD IS CONSUMED BY THE AWARD IT FEEDS.  `$80FA` clears
`$FFED..$FFF0` at `$8164`/`$8167`, so a run that does not SEED them cannot tell
"paid ten" from "paid nothing" -- the same shape B2 and B6 each paid for once.

TWO MORE THINGS EVERY CAPTURE HIDES:
  * `($AA5F)` reads `$00` in the states this oracle runs on (r20_48, boss),
    taken between entity passes -- NOT in every shipped state: four were
    captured mid-pass inside `$A447` (`$05..$09`) and the Boris rounds read
    `$FE`/`$FF`.  An unseeded decrement wraps to `$FF` and reads as
    garbage, so the arm is invisible.  And the arm is NOT a bit-5 test, though
    `$A437` looks like one: it is reached through `$A447`, which diverts to it
    only when bit 7 is CLEAR (`$A451 JP p`) or bit 3 is SET (`$A456 JR nz`), so
    the second decrement needs (BIT 7 CLEAR **OR** BIT 3 SET) **AND** BIT 5
    CLEAR -- phase G below sets no bit 3; tools/corpserepaint.py measures that
    half (M7.51).  A model that reads `$A437` alone charges a live enemy twice.
  * `$A5D9` is a CODE byte written and then restored to `$00`, and the tape and
    the dump both hold `$00`.  Seeded `$5A`, the write appears.

Usage:  python tools/popemit.py     (capture -> build/popemit_fixture.json)
"""
import sys, json, glob, os
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/popemit_fixture.json'
BRANCH_BYTE = 0x8DC4
EMIT = 0xB6F2            # the pop-emit head
FORK = 0xB75C            # the award fork
CLASS_OP = 0xB742        # $B741 LD A,n -- n IS the popped class
OWNER_OP = 0xB796        # $B795 LD A,n -- n IS the player index
MASK_TAB = 0xB80E
CORPSE = 0xB816
KILL = 0x8BC2
AA5F = 0xAA5F
A5D9 = 0xA5D9
PEND = 0xFFED
POOL = 0xFED8            # the bubble pool, 12 x 10


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
    r[10], r[11] = v >> 8, v & 0xFF


def score(m, p=1):
    return [m[0xFFE1 + 4 * p + i] for i in range(4)]


# ---------------------------------------------------------------- phase A
def phase_fork():
    """the award fork end to end, on TWO rounds, with the pending field SEEDED
       ZERO -- $80FA clears it, so an unseeded run cannot tell "paid ten" from
       "paid nothing"."""
    rows = []
    for st in ('boss', 'r20_48'):
        for cls in (0, 1, 2, 3, 4, 5, 8, 0xFF):
            h, m = new(st)
            for i in range(4):
                m[PEND + i] = 0x00
            m[OWNER_OP] = 1
            m[AA5F] = 0x77
            m[A5D9] = 0x5A
            m[0xFD87] |= 0x80
            before = score(m, 1)
            h.memobj.watch(0x4000, 0x10000)
            arm(h, FORK)
            h.sim.registers[A] = cls
            # THE FIELD AT THE PAY SITE, because $B816 RETURNS HL and $B771
            # stores whatever it left: class 1 pays $0100 -- the corpse's own
            # value -- where class 0 pays the $0001 the fork loaded.
            sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
            sent = set(h.SENTINELS)
            pend_at_pay, n = None, 0
            while n < 400000:
                pcv = regs[PC]
                if pcv in sent:
                    break
                if pcv == 0xB795:
                    pend_at_pay = [m[PEND + i] for i in range(4)]
                op[mem[pcv]]()
                n += 1
            log = list(h.memobj.log)
            h.memobj.unwatch()
            rows.append({'state': st, 'round': m[0x8609], 'cls': cls,
                         'pend_at_pay': pend_at_pay,
                         'score_before': before, 'score_after': score(m, 1),
                         'pend': [m[PEND + i] for i in range(4)],
                         'aa5f': m[AA5F], 'a5d9': m[A5D9],
                         'corpse': any(0xFD94 <= a <= 0xFDD9 for (_, a, _) in log),
                         'writes': len(log)})
    return rows


# ---------------------------------------------------------------- phase B
def phase_mailbox():
    """$B6F2..$B75B -- the class into $B742, the +9 zeroed, and the $FFF9
       mailbox armed ONLY when it is empty ($B740 OR A / $B743 JR nz)."""
    rows = []
    for (pending, plus9, flags) in ((0, 3, 0x82), (0, 2, 0x82), (0, 4, 0x92),
                                    (3, 3, 0x82), (0, 3, 0x80)):
        h, m = new('r20_48')
        iy = POOL + 10
        m[iy + 9] = plus9
        m[iy + 5], m[iy + 6] = 0x93, 0x57
        m[iy + 7] = flags
        m[0xFFF9] = pending
        m[0xFFF7] = m[0xFFF8] = m[0xFFFA] = 0x5A
        m[CLASS_OP] = 0x5A
        m[OWNER_OP] = 0x5A
        set_iy(h, iy)
        arm(h, EMIT)
        run(h)
        rows.append({'pending_in': pending, 'plus9_in': plus9, 'flags': flags,
                     'class_op': m[CLASS_OP], 'plus9_out': m[iy + 9],
                     'fff9': m[0xFFF9], 'fffa': m[0xFFFA],
                     'fff7': m[0xFFF7], 'fff8': m[0xFFF8],
                     'owner_op': m[OWNER_OP]})
    return rows


# ---------------------------------------------------------------- phase C
def phase_corpse_index():
    """$B816's index BUILT: IY := $FD94 + 10*(IY+8), swept over k = 0..8 --
       INCLUDING a k whose target slot is EMPTY, which is the case that exposes
       both the missing active check and the $AA5F double decrement.

       THE ENEMY ARRAY IS ONLY SEVEN SLOTS: k = 7 writes $FDDA, which is P1's
       status record, and k = 8 writes $FDE4, which is P2's."""
    rows = []
    for k in range(9):
        h, m = new('r20_48')
        iy = POOL + 10
        m[iy + 8] = k
        m[AA5F] = 0x77
        tgt = (0xFD94 + 10 * k) & 0xFFFF
        for i in range(10):
            m[(tgt + i) & 0xFFFF] = 0x5A
        m[(tgt + 7) & 0xFFFF] = 0x00 if k >= 5 else 0x20      # bit 5: live or not
        cur = [m[0xFE86], m[0xFE87]]
        set_iy(h, iy)
        h.memobj.watch(0x4000, 0x10000)
        arm(h, CORPSE)
        run(h)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        rows.append({'k': k, 'target': '$%04X' % tgt,
                     'plus7_in': 0x00 if k >= 5 else 0x20,
                     'rng_before': cur,
                     'aa5f': m[AA5F],
                     'slot': [m[(tgt + i) & 0xFFFF] for i in range(10)],
                     'addrs': sorted(set('$%04X' % a for (_, a, _) in log))[:12]})
    return rows


# ---------------------------------------------------------------- phase D
def phase_rng_draws():
    """$8BC2 builds the corpse's (IY+8) from TWO $FE85 draws, which also advance
       the RNG cursor: one draw looks like a constant and passes every
       single-kill row."""
    rows = []
    for seed in (0x00, 0x40, 0x80, 0xC0):
        h, m = new('r20_48')
        m[0xFEBB] = seed
        cur = (m[0xFE86], m[0xFE87])
        iy = 0xFD94
        for i in range(10):
            m[iy + i] = 0x5A
        m[iy + 7] = 0x20
        m[AA5F] = 0x77
        set_iy(h, iy)
        arm(h, KILL)
        # COUNT the draws: one $FE85 call looks exactly like two until the
        # calls themselves are counted, because both leave the same (IY+8) on
        # any single row.
        sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
        sent = set(h.SENTINELS)
        draws, n = 0, 0
        while n < 400000:
            pcv = regs[PC]
            if pcv in sent:
                break
            if pcv == 0xFE85:
                draws += 1
            op[mem[pcv]]()
            n += 1
        rows.append({'seed': seed, 'draws': draws, 'cursor_before': list(cur),
                     'cursor_after': [m[0xFE86], m[0xFE87]],
                     'plus8': m[iy + 8], 'plus7': m[iy + 7],
                     'aa5f': m[AA5F]})
    return rows


# ---------------------------------------------------------------- phase E
def phase_class_census():
    """the pool census over every shipped state.  A STATIC enumeration of the
       (IY+9) writers concluded classes 2 and 4 were unreachable and $9460 dead
       code; this refutes it in one run."""
    seen, per = {}, {}
    n = 0
    for f in sorted(glob.glob('build/*.pkl')):
        st = os.path.basename(f)[:-4]
        h = Harness()
        try:
            h.load_state_file(f)
        except Exception:
            continue
        m = h.memobj.m
        if m[BRANCH_BYTE] != 0xC9:
            continue
        n += 1
        cs = []
        for k in range(12):
            base = POOL + 10 * k
            if m[base + 7] & 0x80:
                cs.append(m[base + 9])
        for c in cs:
            seen[c] = seen.get(c, 0) + 1
        if cs:
            per[st] = {'round': m[0x8609], 'elem': m[0x7E0E], 'classes': cs}
    return {'states': n, 'histogram': {str(k): v for k, v in sorted(seen.items())},
            'per_state': {k: per[k] for k in
                          ('elwater', 'elfire', 'ellight', 'round1_48', 'boss')
                          if k in per}}


# ---------------------------------------------------------------- phase F
def phase_negatives():
    """the ledger and the censuses this entry stands on."""
    with open('build/image_tape.bin', 'rb') as f:
        tape = f.read()
    with open('build/image.bin', 'rb') as f:
        dump = f.read()
    h, m = new('boss')
    names = {0x32: 'LD (nn),A', 0x3A: 'LD A,(nn)', 0x21: 'LD HL,nn', 0xCD: 'CALL'}
    out = {'ledger': {}}
    for (label, addr) in (('$B742', CLASS_OP), ('$B796', OWNER_OP),
                          ('$A5D9', A5D9), ('$AA5F', AA5F)):
        # THREE columns, not two: the tape, the round-80 DUMP FILE, and the
        # live boss.pkl.  The plan's claim was about the first two.
        out['ledger'][label] = {'tape': tape[addr], 'dump': dump[addr],
                                'boss_pkl': m[addr]}
    for (label, addr) in (('$B796', OWNER_OP), ('$AA5F', AA5F)):
        hits = h.find_bytes(bytes([addr & 0xFF, addr >> 8]), 0x4000, 0x10000)
        out[label] = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1],
                       'form': names.get(m[a - 1])} for a in hits]
    # $B7E5 has NO bounds check: class $FF indexes $B80E + $FA
    out['mask_table'] = {'base': '$%04X' % MASK_TAB,
                         'bytes': list(tape[MASK_TAB:MASK_TAB + 8]),
                         'class_FF_index': '$%04X' % ((MASK_TAB + 0xFA) & 0xFFFF)}
    # round 80 carries no entities, so no bubble can acquire class 1 in fair play
    g, mm = new('boss')
    out['round80_entities'] = [mm[0xFD94 + 10 * k + 7] for k in range(7)]
    return out


# ---------------------------------------------------------------- phase G
def phase_aa5f_arms():
    """WHICH (IY+7) COSTS TWO.  $A437 is `LD SP,IX / BIT 5,(IY+7) / RET nz /
       SET 5,(IY+7) / LD HL,$AA5F / DEC (HL)`, so on its own it is a bit-5 test
       -- but it is reached THROUGH $A447, the entity master, which diverts to
       it only when bit 7 is CLEAR ($A451 JP p) or bit 3 is SET ($A456 JR nz).
       So the second decrement needs bit 5 clear AND (bit 7 clear or bit 3
       set) -- none of the eight values below sets bit 3; corpserepaint.py
       measures that half (M7.51) -- and a model that tests bit 5 alone
       charges a live enemy twice.
       ($AA5F) is SEEDED $77: r20_48 reads $00 (not every shipped state does),
       so an unseeded decrement wraps to $FF and the arms are indistinguishable."""
    rows = []
    for f7 in (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC1, 0xE1):
        h, m = new('r20_48')
        iy = 0xFD94
        for i in range(10):
            m[iy + i] = 0x5A
        m[iy + 7] = f7
        m[AA5F] = 0x77
        cur = [m[0xFE86], m[0xFE87]]
        set_iy(h, iy)
        arm(h, KILL)
        sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
        sent = set(h.SENTINELS)
        seen, n = [], 0
        while n < 400000:
            pcv = regs[PC]
            if pcv in sent:
                break
            if pcv in (0x8C51, 0xA447, 0xA437, 0xA442):
                seen.append('$%04X' % pcv)
            op[mem[pcv]]()
            n += 1
        rows.append({'plus7_in': f7, 'aa5f_in': 0x77, 'aa5f_out': m[AA5F],
                     'rng_before': cur, 'rng_after': [m[0xFE86], m[0xFE87]],
                     'cost': (0x77 - m[AA5F]) & 0xFF,
                     'plus7_out': m[iy + 7], 'pcs': seen})
    return rows


def main():
    fx = {'fork': phase_fork(),
          'mailbox': phase_mailbox(),
          'corpse_index': phase_corpse_index(),
          'rng': phase_rng_draws(),
          'census': phase_class_census(),
          'negatives': phase_negatives(),
          'aa5f_arms': phase_aa5f_arms()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    for r in fx['fork']:
        if r['state'] != 'boss':
            continue
        print('  fork cls %-3d score %s -> %s, pend %s, $AA5F %02X, $A5D9 %02X, corpse %s'
              % (r['cls'], r['score_before'], r['score_after'], r['pend'],
                 r['aa5f'], r['a5d9'], r['corpse']))
    for r in fx['mailbox']:
        print('  mailbox pending %d +9 %d flags %02X -> $B742 %02X, +9 %d, $FFF9 %d, '
              '$FFFA %02X, XY %02X/%02X'
              % (r['pending_in'], r['plus9_in'], r['flags'], r['class_op'],
                 r['plus9_out'], r['fff9'], r['fffa'], r['fff7'], r['fff8']))
    for r in fx['corpse_index']:
        print('  corpse k=%d -> %s (+7 in %02X) $AA5F $77->%02X, slot %s'
              % (r['k'], r['target'], r['plus7_in'], r['aa5f'], r['slot']))
    for r in fx['rng']:
        print('  rng seed %02X: %d draws, cursor %s -> %s, (IY+8) %02X, (IY+7) %02X'
              % (r['seed'], r['draws'], r['cursor_before'], r['cursor_after'],
                 r['plus8'], r['plus7']))
    print('census:', fx['census']['states'], 'states, classes',
          fx['census']['histogram'])
    for k, v in fx['census']['per_state'].items():
        print('   %-10s round %d elem %d classes %s' % (k, v['round'], v['elem'],
                                                        v['classes']))
    print('ledger:', fx['negatives']['ledger'])
    print('$B796 refs:', [r['at'] + ' ' + str(r['form'])
                          for r in fx['negatives']['$B796']])
    print('round-80 entity +7:', fx['negatives']['round80_entities'])
    for r in fx['aa5f_arms']:
        print('  $AA5F arm: (IY+7) %02X -> cost %d, +7 out %02X, %s'
              % (r['plus7_in'], r['cost'], r['plus7_out'], r['pcs']))


if __name__ == '__main__':
    main()
