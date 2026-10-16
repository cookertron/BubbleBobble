"""M7.65 -- THE LIGHTNING BOLT'S ENEMY KILL: the scan $9EA6..$9ECE, its comparator $9F18,
and the kill $9EFE `CALL nc,$8BC2`.

$9E90 (one bolt slot) erases the bolt, then -- off the boss round -- scans the enemy table:

    $9EA6  LD HL,$FD9B          slot 2's +7
           LD A,($AA57) / SUB 2 / LD B,A     ($AA57) - 2 slots -- DJNZ, so B = 0 is 256
           LD DE,10
    $9EB2  BIT 7,(HL) / JR z,next           any slot with bit 7 SET: a live enemy, a frozen
                                            one, AND A CORPSE (bit 7 stays set while it flies)
           PUSH HL / DEC HL                 +6 (Y) against the bolt's +6
           LD A,(IY+6) / CALL $9F18 / JR nc,skip
           DEC HL                           +5 (X) against the bolt's +5
           LD A,(IY+5) / CALL $9F18 / JR nc,skip
           LD ($9EDF),HL                    the operand of $9EDE LD DE,nn := the +5 pointer --
                                            THE LAST HIT SLOT WINS, the scan does not stop
    skip   POP HL
    next   ADD HL,DE / DJNZ $9EB2

$9F18 is `EX AF,AF' / LD A,(HL) / AND $F8 / LD C,A / EX AF,AF' / AND $F8 / SUB 15 / CP C /
RET nc / ADD A,$1E / CP C / CCF / RET`: carry = hit, EIGHT-BIT, so both ends wrap.  Then the
physics runs and the bounds may RES 7 the bolt with the record set (no kill); else a record
with a nonzero high byte takes $9EE5 OR A / EX AF,AF' into the shared tail, where $9EF7
`LD IY,$FFFB / ADD IY,DE` turns the +5 pointer into the slot BASE and $9EFE CALL nc,$8BC2
births the corpse -- and a corpse the bolt passes through again is born AGAIN ($AA5F falls
twice).

  calls: $9E90 called at its own entry (interrupts off, uncontended) on built worlds of r20_48
         (the bolt and up to two enemies placed, the rest of the table dead), and every $9E90
         entry with the bolt live over natural idle play of ellight, each re-run from its entry
         with interrupts off.
  comparator: $9F18 at its own entry for every bolt byte against every enemy byte, 256 x 256
         (the enemy byte UNALIGNED too -- $9F19's AND $F8 is only visible there): 256 hex
         strings of 64 digits, bit v of the string's number = hit against enemy byte v.

Per call: the pre-state vector ($FD00..$FDFF and the named scalars), the record at $9ED0, the
slot $8BC2 was handed (IY at its entry), and every non-display, non-stack write classified:
'vector' (compared exactly), 'operand' (the erase and blit's own patched operands, which the
port does not model -- STATUS item 6), with the display writes counted only (their bytes are
the erase's, the blit's and $8C51's, gated by their own blocks).  No ROM byte: the watch starts
at $4000 and nothing below $4000 is read into the fixture.

Usage:  python tools/boltkill.py            capture -> build/boltkill_fixture.json
        python tools/boltkill.py verify     re-run and diff against the fixture
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, SP, IYh, IYl, IFF, A as RA, F as RF, H as RH, L as RL
import portconfig as pc

FIXTURE = 'build/boltkill_fixture.json'
BRANCH_BYTE = 0x8DC4
SLOT_ENTRY, SCAN_END, BIRTH, COMP = 0x9E90, 0x9ED0, 0x8BC2, 0x9F18
GUARD = range(0xD000, 0xD300)
SCALARS = [0x8609, 0xAA57, 0xAA5F, 0xA431, 0x9D83, 0x9F09, 0x9F62, 0x9EDF, 0x9EE0,
           0xA8DB, 0xA839, 0xFE86, 0xFE87, 0xA5D9, 0x81BB, 0x8605, 0x8606, 0x8607, 0x8608] + [
           a for a in range(0xFFE1, 0xFFF1)]         # the score award's own state
VECTOR_LO, VECTOR_HI = 0xFD00, 0xFE00
# the item erase $A314's and blit $A2C2's self-modified operands, and $A447's (the corpse's
# final repaint) -- written before they are read, inside every call; not modelled (STATUS 6)
OPERANDS = {0xA304, 0xA307, 0xA30C, 0xA33D, 0xA349, 0xA355,
            0xA50B, 0xA584, 0xA5A2, 0xA5A6, 0xA5B1, 0xA5B5, 0xA5BE, 0xA5C2, 0xA5CD, 0xA5D1,
            0xA5D9}
BOLT0, BOLT1 = 0xFDEE, 0xFDF8


def new(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, h.memobj.m


def vector(m):
    return {'fd': list(m[VECTOR_LO:VECTOR_HI]), 'scalars': [m[a] for a in SCALARS]}


def run_slot(h, iy, stop=None):
    """$9E90 with IY = iy (or, with `stop`, from the current PC to the return address `stop`
       at the entry SP + 2), interrupts off, single-stepped."""
    m, r = h.memobj.m, h.sim.registers
    pre = vector(m)
    sp0 = r[SP]
    if stop is None:
        sp = sp0
        for s in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp], m[sp + 1] = s & 0xFF, s >> 8
        r[SP] = sp
        r[IYh], r[IYl] = iy >> 8, iy & 0xFF
        r[PC] = SLOT_ENTRY
        stops, want_sp = set(h.SENTINELS), (sp + 2) & 0xFFFF
    else:
        sp = sp0
        stops, want_sp = {stop}, (sp0 + 2) & 0xFFFF
    h.memobj.watch(0x4000, 0x10000)
    rec, kills, n = None, [], 0
    while True:
        p = r[PC]
        if p in GUARD:
            h.memobj.unwatch()
            raise SystemExit('GUARD: PC $%04X' % p)
        if p in stops and r[SP] == want_sp:
            break
        if p == SCAN_END and rec is None:
            rec = m[0x9EDF] | (m[0x9EE0] << 8)
        if p == BIRTH:
            kills.append((r[IYh] << 8) | r[IYl])
        h.step(1, interrupts=False)
        n += 1
        if n > 400_000:
            h.memobj.unwatch()
            raise SystemExit('runaway')
    h.memobj.unwatch()
    sp_lo = (sp - 0x100) & 0xFFFF
    vec, ops, disp, other = {}, {}, 0, {}
    for _pc, a, v in h.memobj.log:
        if 0x4000 <= a < 0x5B00:
            disp += 1
        elif sp_lo <= a < sp0:
            pass
        elif a in OPERANDS:
            ops[a] = v
        else:
            vec[a] = v
    return {'iy': iy, 'pre': pre, 'rec': rec, 'kills': kills,
            'post': sorted([a, v] for a, v in vec.items()),
            'operand': sorted(ops), 'disp_writes': disp, 'steps': n}


# ------------------------------------------------------------------ BUILT worlds (r20_48)
def enemy(k, x, y, f7=0xE0):
    return (k, x, y, f7)


def built_cases():
    C = []
    for x in range(0x40, 0x81):                                   # X sweep across the window
        C.append(('sweep_x_%02X' % x, BOLT0, (x, 0x60, 0x81), [enemy(4, 0x60, 0x60)], {}))
    for y in range(0x40, 0x81):                                   # Y sweep across the window
        C.append(('sweep_y_%02X' % y, BOLT0, (0x60, y, 0x81), [enemy(4, 0x60, 0x60)], {}))
    C += [
        ('two_hit_last_wins', BOLT0, (0x60, 0x60, 0x81), [enemy(2, 0x58, 0x60), enemy(6, 0x66, 0x5A)], {}),
        ('two_hit_first_only', BOLT0, (0x60, 0x60, 0x81), [enemy(2, 0x58, 0x60), enemy(6, 0x90, 0x60)], {}),
        ('dead_in_window', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60, 0x60)], {}),
        ('frozen_in_window', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60, 0xE8)], {}),
        ('corpse_in_window', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60, 0xAD)], {}),
        ('first_visit_enemy', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60, 0x80)], {}),
        ('slot7_count7', BOLT0, (0x60, 0x60, 0x81), [enemy(7, 0x60, 0x60)], {0xAA57: 7}),
        ('slot7_count8', BOLT0, (0x60, 0x60, 0x81), [enemy(7, 0x60, 0x60)], {0xAA57: 8}),
        ('slot2_count3', BOLT0, (0x60, 0x60, 0x81), [enemy(2, 0x60, 0x60)], {0xAA57: 3}),
        ('slot3_count3', BOLT0, (0x60, 0x60, 0x81), [enemy(3, 0x60, 0x60)], {0xAA57: 3}),
        ('wrap_low_miss', BOLT0, (0x08, 0x60, 0x81), [enemy(4, 0x00, 0x60)], {}),
        ('wrap_low_y_miss', BOLT0, (0x60, 0x08, 0x81), [enemy(4, 0x60, 0x00)], {}),
        ('wrap_high_hit', BOLT0, (0xF0, 0x60, 0x80), [enemy(4, 0xF8, 0x60)], {}),
        ('wrap_high_miss', BOLT0, (0xF8, 0x60, 0x80), [enemy(4, 0xF8, 0x60)], {}),
        ('despawn_after_hit', BOLT0, (0x10, 0x60, 0x80), [enemy(4, 0x10, 0x60)], {}),
        ('despawn_right_after_hit', BOLT0, (0xE0, 0x60, 0x81), [enemy(4, 0xE0, 0x60)], {}),
        ('p2_bolt', BOLT0, (0x60, 0x60, 0x91), [enemy(4, 0x60, 0x60)], {}),
        ('stride_halved', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60)], {0x9D83: 0x00}),
        ('slot1_bolt', BOLT1, (0x60, 0x60, 0x80), [enemy(5, 0x60, 0x60)], {}),
        ('miss_moves_on', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0xA0, 0xA0)], {}),
        ('dead_bolt', BOLT0, (0x60, 0x60, 0x01), [enemy(4, 0x60, 0x60)], {}),
        ('aa5f_wraps', BOLT0, (0x60, 0x60, 0x81), [enemy(4, 0x60, 0x60)], {0xAA5F: 0x00}),
        ('unaligned_both', BOLT0, (0x6F, 0x57, 0x81), [enemy(4, 0x63, 0x61)], {}),
        # the enemy's low three bits: a miss that an unaligned compare would call a hit
        ('unaligned_enemy_x', BOLT0, (0x70, 0x60, 0x81), [enemy(4, 0x63, 0x60)], {}),
        ('unaligned_enemy_y', BOLT0, (0x60, 0x77, 0x81), [enemy(4, 0x60, 0x66)], {}),
    ]
    return C


def built_calls():
    h, m = new('r20_48')
    base = h.save_state()
    out = []
    for label, iy, (bx, by, bf), ens, scal in built_cases():
        h.load_state(base)
        for k in range(2, 10):                                     # the rest of the table DEAD
            m[0xFD80 + 10 * k + 7] &= 0x7F
        m[BOLT0 + 7] &= 0x7F
        m[BOLT1 + 7] &= 0x7F
        m[iy + 5], m[iy + 6], m[iy + 7] = bx, by, bf
        for k, x, y, f7 in ens:
            s = 0xFD80 + 10 * k
            m[s + 5], m[s + 6], m[s + 7] = x, y, f7
        for a, v in scal.items():
            m[a] = v
        c = run_slot(h, iy)
        c.update(family='built', state='r20_48', label=label)
        out.append(c)
    return out


# ------------------------------------------------------------------ NATURAL: ellight
def natural_calls(state='ellight', isrs=120):
    h, m = new(state)
    r = h.sim.registers
    out, isr, steps = [], 0, 0
    while isr <= isrs:
        p = r[PC]
        if p in GUARD:
            raise SystemExit('%s: GUARD at $%04X' % (state, p))
        if p == 0x8D72:
            isr += 1
        if p == SLOT_ENTRY:
            iy = (r[IYh] << 8) | r[IYl]
            if m[iy + 7] & 0x80:
                snap = h.save_state()
                ret = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
                iff = r[IFF]
                c = run_slot(h, iy, stop=ret)
                c.update(family='natural', state=state, label='isr%d_%04X' % (isr, iy), iff=iff)
                out.append(c)
                h.load_state(snap)
        h.step(1)
        steps += 1
        if steps > 80_000_000:
            raise SystemExit('%s: runaway natural run' % state)
    return out


# ------------------------------------------------------------------ the comparator
def comparator():
    h, m = new('r20_48')
    r = h.sim.registers
    sp0 = r[SP]
    masks = []
    for a in range(256):
        mask = 0
        for j in range(256):
            m[0xFD9A] = j
            r[RH], r[RL] = 0xFD, 0x9A                     # HL = $FD9A
            r[RA] = a
            sp = sp0
            for s in reversed(h.SENTINELS):
                sp = (sp - 2) & 0xFFFF
                m[sp], m[sp + 1] = s & 0xFF, s >> 8
            r[SP] = sp
            r[PC] = COMP
            h.run_until(tuple(h.SENTINELS), limit=1000, stride=1, interrupts=False)
            if r[RF] & 1:
                mask |= 1 << j
        masks.append('%064x' % mask)
    return masks


def capture():
    return {'note': 'tools/boltkill.py -- see its docstring', 'scalars': SCALARS,
            'vector': [VECTOR_LO, VECTOR_HI], 'operands': sorted(OPERANDS),
            'comparator': comparator(), 'calls': built_calls() + natural_calls()}


def summary(fx):
    calls = fx['calls']
    for fam in ('built', 'natural'):
        cs = [c for c in calls if c['family'] == fam]
        kills = [c for c in cs if c['kills']]
        print('%-8s %3d calls, %3d kill, %3d with a record, vector addrs %s' % (
            fam, len(cs), len(kills), sum(1 for c in cs if c['rec']),
            sorted({'%04X' % a for c in cs for a, _ in c['post'] if not VECTOR_LO <= a < VECTOR_HI})))
    for c in calls:
        if c['family'] == 'natural' and (c['kills'] or c['rec']):
            print('  natural %-14s rec $%04X kills %s' % (c['label'], c['rec'] or 0,
                                                       ['$%04X' % k for k in c['kills']]))
    print('comparator hits per bolt byte (first 40):', [bin(int(x, 16)).count('1') for x in fx['comparator'][:40]])


def main():
    fx = capture()
    if sys.argv[1:] == ['verify']:
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        same = json.loads(json.dumps(fx)) == old
        print('MATCH' if same else 'DIFFER')
        sys.exit(0 if same else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as f:
        json.dump(fx, f, separators=(',', ':'))
    print('wrote', FIXTURE)
    summary(fx)


if __name__ == '__main__':
    main()
