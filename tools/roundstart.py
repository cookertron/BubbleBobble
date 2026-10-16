"""M7.7-R1 -- THE ROUND-START SEQUENCE $9858..$98B4, the gap B11 stopped at.

B11's differential reproduced the machine row for row and STOPPED BY NAME at
the 80 -> 81 advance, because $97F8's counter arithmetic is transliterated and
the sequence it leads into is not.  Twenty fields move across that row.  This
is the sequence that moves them.

WHAT THE PORT HAD: roundAdvance() -> roundReset() (the 19-pointer clear walk),
and a transitionTail() covering $9891..$98A4 THAT NOTHING CALLED.  Between them
lay $9858..$988E and $98A7..$98B4, unread.

*** THE SETTLE WINDOW IS 88 FRAMES ON EVERY ROUND AND 20 ON ROUND ONE. ***
  $9877 LD A,($8609) / DEC A / LD A,$58 / JR nz,$9881 / LD A,$14
  $9881 LD ($B54B),A / $9884 LD ($FEC4),A
ONE load feeds BOTH bytes.  B11 measured play1p48 sitting inside a settle window
with $B54B = 14 and recorded it as "not a boss-state quirk"; this is the
mechanism, and it is a round-1 SPECIAL CASE rather than a property of captures.
$B54B is the byte $AA72 `JP nz,$B520` uses to abandon the entire entity pass,
so round 1 gives the player 20 frames of frozen entities and every other round
gives 88.

AND THE SEQUENCE CONTAINS A HALT.  $9887 waits for the ISR in the middle of the
build, between arming the settler and zeroing the frame counter, so the two
halves are on opposite sides of a frame boundary.

$988B and $988E ARE SIXTEEN-BIT STORES: `LD HL,0 / LD ($8DBD),HL` zeroes $8DBD
AND $8DBE, and `LD ($8DB6),HL` zeroes $8DB6 AND $8DB7.  Poisoned here, because
seeding zero makes both halves invisible (TRAPS #44).

Usage:  python tools/roundstart.py     (capture -> build/roundstart_fixture.json)
        python tools/roundstart.py NAME [NAME...]
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/roundstart_fixture.json'
BRANCH_BYTE = 0x8DC4
ROUND = 0x8609
SEQ = 0x9858                       # the sequence entry, just past the clear walk
SEQ_END = 0x98B5                   # LD A,($8609) / CP $51 -- the next thing
SETTLER, SETTLER2 = 0xB54B, 0xFEC4
FRAMECT, ITEMCT = 0x8DBD, 0x8DB6
STEP = 0xB610
ISR = 0x8D72
POISON = 0x5A

# every CALL in the sequence, with the increment that already owns it
CALLS = [
    (0x9863, 0x7F1B, 'H11 -- the scroll copier and the whole scroll-in'),
    (0x9866, 0x727B, 'M7.6 -- the enemy spawner (UNOWNED here)'),
    (0x9869, 0x99A8, 'M7.4 -- the player init (UNOWNED here)'),
    (0x986C, 0xA36C, 'UNOWNED'),
    (0x986F, 0x957E, 'H9 -- the silent painter'),
    (0x98A1, 0xAA49, 'I10 -- the sparkle table clear'),
    (0x98A4, 0x79AC, 'H3/H8 -- the collision transform and the map'),
    (0x98A7, 0xBF39, 'H10 -- the bubble sprite bank'),
    (0x98AA, 0x8C5E, 'I6/I7 -- the per-round item init'),
]

FIELDS = ['8DBD', '8609', '9F62', 'A839', 'AA00', 'AA06', 'B54B', 'FEC7',
          'FEC8', 'A09E', '830A', 'FD87', 'FDDA', 'FDE4', 'FDF3', 'FDF4',
          'FDF5', 'FDFD', 'FDFE', 'FDFF']


def new(state):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch' % state)
    return h, m


def arm(h, addr, sp=0x96DD):
    r = h.sim.registers
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr


def to_sequence(h, limit=40_000_000):
    r, _ = h.run_until((SEQ,), limit=limit, stride=1)
    return r == 'target'


def bucket(log):
    b = {}
    for (p, a, v) in log:
        k = ('disp' if 0x4000 <= a < 0x5800 else
             'attr' if a < 0x5B00 else
             'shadow' if 0xE000 <= a < 0xF800 else
             'colshad' if 0xF800 <= a < 0xFB00 else
             'ents' if 0xFD80 <= a < 0xFF60 else 'vars')
        b[k] = b.get(k, 0) + 1
    return b


# ------------------------------------------------------------------ phase A
def phase_calls():
    """EVERY CALL IN THE SEQUENCE, BRACKETED ON ITS OWN.  A first version armed
       all nine at once and measured TWO: seven of the return addresses ARE the
       next call site, so the loop treated them as arms and threw the log away.
       Each is run separately now, and the shape is what the port's stubs are
       gated against -- so "the stub is a stub" and "the stub does nothing"
       stay different statements."""
    out = {}
    for site, target, owner in CALLS:
        h, m = new('bosskilled')
        if not to_sequence(h):
            out['%04X' % target] = {'reached': False}
            continue
        r, _ = h.run_until((site,), limit=8_000_000, stride=1)
        if r != 'target':
            out['%04X' % target] = {'reached': False, 'owner': owner}
            continue
        h.memobj.watch(0x4000, 0x10000)
        r, _ = h.run_until((site + 3,), limit=8_000_000, stride=1)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        out['%04X' % target] = {
            'reached': r == 'target', 'site': '%04X' % site, 'owner': owner,
            'writes': len(log), 'buckets': bucket(log),
            'distinct_pcs': len(set(p for (p, _, _) in log))}
    return out


# ------------------------------------------------------------------ phase B
def phase_settler():
    """*** 88 FRAMES ON EVERY ROUND, 20 ON ROUND ONE, AND ONE LOAD FEEDS TWO
       BYTES. ***  $9877 reads ($8609) and DECs it; the branch is taken for
       every round but 1.  Enumerated over the whole byte by driving $9877
       itself, and confirmed on a LIVE round-1 world (play1p48 holds $B54B = 14
       with no poke at all)."""
    out = {'rows': [], 'live': {}}
    h0, m0 = new('bosskilled')
    if not to_sequence(h0):
        raise SystemExit('never reached $9858')
    for rnd in list(range(0, 6)) + [0x14, 0x32, 0x50, 0x51, 0x80, 0xFF]:
        h, m = new('bosskilled')
        to_sequence(h)
        m[ROUND] = rnd
        m[SETTLER] = POISON
        m[SETTLER2] = POISON
        r = h.sim.registers
        sp = 0x96DD
        for sent in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp] = sent & 0xFF
            m[sp + 1] = sent >> 8
        r[SP] = sp
        r[PC] = 0x9877
        h.run_until((0x9887,), limit=200000, stride=1, interrupts=False)
        out['rows'].append([rnd, m[SETTLER], m[SETTLER2]])
    out['round1_value'] = 0x14
    out['other_value'] = 0x58
    out['one_load_two_bytes'] = all(r[1] == r[2] for r in out['rows'])
    for st in ('play1p48', 'round1_48', 'r20_48', 'bosshit'):
        h, m = new(st)
        out['live'][st] = {'round': m[ROUND], 'B54B': m[SETTLER],
                           'FEC4': m[SETTLER2]}
    return out


# ------------------------------------------------------------------ phase C
def phase_zeroing():
    """$988B AND $988E ARE SIXTEEN-BIT STORES.  `LD HL,0 / LD ($8DBD),HL` zeroes
       $8DBD AND $8DBE; `LD ($8DB6),HL` zeroes $8DB6 AND $8DB7.  All four bytes
       are POISONED first, because zero is the value the store writes and a
       seeded zero makes the whole thing invisible (TRAPS #44)."""
    h, m = new('bosskilled')
    if not to_sequence(h):
        raise SystemExit('never reached $9858')
    for a in (FRAMECT, FRAMECT + 1, ITEMCT, ITEMCT + 1, STEP):
        m[a] = POISON
    before = {'8DBD': m[FRAMECT], '8DBE': m[FRAMECT + 1],
              '8DB6': m[ITEMCT], '8DB7': m[ITEMCT + 1], 'B610': m[STEP]}
    r = h.sim.registers
    sp = 0x96DD
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = sent & 0xFF
        m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = 0x9872                       # LD A,2 / LD ($B610),A, then on
    h.memobj.watch(0x4000, 0x10000)
    h.run_until((0x9891,), limit=400000, stride=1)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    return {'before': before,
            'after': {'8DBD': m[FRAMECT], '8DBE': m[FRAMECT + 1],
                      '8DB6': m[ITEMCT], '8DB7': m[ITEMCT + 1],
                      'B610': m[STEP]},
            'writers': {'%04X' % a: sorted(set('%04X' % p for (p, aa, _) in log
                                               if aa == a))
                        for a in (FRAMECT, FRAMECT + 1, ITEMCT, ITEMCT + 1,
                                  STEP)},
            'both_halves_written': (m[FRAMECT] == 0 and m[FRAMECT + 1] == 0 and
                                    m[ITEMCT] == 0 and m[ITEMCT + 1] == 0)}


# ------------------------------------------------------------------ phase D
def phase_handover():
    """B11'S TWENTY FIELDS, ACROSS THE WHOLE SEQUENCE, with the PC that wrote
       each -- the list the differential stopped at, turned into a work order."""
    h, m = new('bosskilled')
    if not to_sequence(h):
        raise SystemExit('never reached $9858')
    addrs = {int(f, 16): f for f in FIELDS}
    before = {f: m[int(f, 16)] for f in FIELDS}
    h.memobj.watch(0x4000, 0x10000)
    r, _ = h.run_until((SEQ_END,), limit=20_000_000, stride=1)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    w = {}
    for (p, a, v) in log:
        if a in addrs:
            w.setdefault(addrs[a], []).append(['%04X' % p, v])
    return {'reached_end': r == 'target',
            'before': before,
            'after': {f: m[int(f, 16)] for f in FIELDS},
            'writers': {k: sorted(set(x[0] for x in v)) for k, v in w.items()},
            'write_counts': {k: len(v) for k, v in w.items()},
            'untouched': [f for f in FIELDS if f not in w],
            'total_writes': len(log), 'buckets': bucket(log)}


def phase_frames():
    """*** HOW MANY FRAMES THE SEQUENCE COSTS, AND THE BANNER ROUND 81 SKIPS. ***

       B11's differential, re-run with the sequence wired, goes GREEN over all
       60 rows of bosshit and r50_48 and reaches bosskilled's row 20 -- the
       80 -> 81 advance -- differing on ONE field by ONE: ($B54B) 87 against 88.
       The engine arms the settler and stops; the machine arms it and then
       SPENDS FRAMES, during which $AA60 runs and $B521 decrements it.

       THE FIRST MODEL WAS "ONE TICK" AND IT IS WRONG.  Measured on five worlds
       (bosskilled naturally, the rest by zeroing the enemy slots to force a
       clear), the count between arming and the first loop top is 1, 28 or 31 --
       and splitting it at $98B5 says why: the part this increment transliterated
       costs 2..4 interrupts and 1..3 ticks, and THE BANNER AFTER IT COSTS 51..58
       INTERRUPTS ON AN ORDINARY ROUND AND ONE ON ROUND 81, because $98B8
       `CP $51 / JR z,$98E4` skips it.  A ~1-second animation nobody had costed.

       So the port's roundStart() ends at $98B4 by measurement, not by choice,
       and the ticks it cannot reproduce are the banner's.  That is the work the
       banner increment inherits, and this row is its brief."""
    out = {'states': {}}
    for st, clear in (('bosskilled', False), ('r50_48', True),
                      ('r20_48', True), ('round1_48', True),
                      ('hurryup', True)):
        h, m = new(st)
        if clear:
            for k in range(7):
                b = 0xFD94 + 10 * k
                for o in range(10):
                    m[b + o] = 0
        if not to_sequence(h, limit=60_000_000):
            out['states'][st] = {'reached': False}
            continue
        h.run_until((0x9881,), limit=8_000_000, stride=1)
        h.step(1)
        seq = {'ISR': 0, 'B521': 0}
        while True:
            r, _ = h.run_until((SEQ_END, ISR, 0xB521), limit=8_000_000,
                               stride=1)
            if r != 'target' or h.regs[PC] == SEQ_END:
                break
            seq['ISR' if h.regs[PC] == ISR else 'B521'] += 1
            h.step(1)
        ban = {'ISR': 0, 'B521': 0}
        while True:
            r, _ = h.run_until((0x8D0C, ISR, 0xB521), limit=8_000_000,
                               stride=1)
            if r != 'target' or h.regs[PC] == 0x8D0C:
                break
            ban['ISR' if h.regs[PC] == ISR else 'B521'] += 1
            h.step(1)
        out['states'][st] = {'reached': True, 'round': m[ROUND],
                             'sequence': seq, 'banner': ban,
                             'B54B_at_loop_top': m[SETTLER],
                             'armed': 0x14 if m[ROUND] == 1 else 0x58}
    got = [v for v in out['states'].values() if v.get('reached')]
    r81 = [v for v in got if v['round'] == 0x51]
    other = [v for v in got if v['round'] != 0x51]
    out['round81_skips_the_banner'] = (
        bool(r81) and bool(other) and
        max(v['banner']['ISR'] for v in r81) < 5 and
        min(v['banner']['ISR'] for v in other) > 40)
    out['sequence_cost_isr'] = sorted(set(v['sequence']['ISR'] for v in got))
    out['banner_cost_isr'] = sorted(set(v['banner']['ISR'] for v in got))
    out['ticks_between_arm_and_loop_top'] = sorted(set(
        v['sequence']['B521'] + v['banner']['B521'] for v in got))
    return out


def phase_banner():
    """*** THE ROUND BANNER $98B5..$98EF: 256 ITERATIONS, AND IT ERASES ITSELF. ***

       B IS ZERO AT $98B5 ON EVERY STATE, so $98E2's DJNZ runs 256 times --
       TRAPS #45 for the third time in this project.  Each iteration draws two
       text rows through $802E and writes ten attribute cells through $995A at
       $594C and $598C; then $98E4 calls $9904 TWICE and the twenty cells go
       back to the round's palette.

       SO THE END STATE IS INDISTINGUISHABLE FROM NEVER HAVING RUN.  The only
       observable is the TIME: 50.4 frames on a one-digit round, 58..59 on a
       two-digit one, and 0.1 on round 81, which $98B8 `CP $51 / JR z,$98E4`
       sends straight to the erase.  That is H2's lesson again -- a pure
       animation whose end-state gate cannot fail.  WALL-CLOCK the cost splits
       by the ROUND'S DIGIT COUNT (0.05% and 1.2% within a class, 15% between);
       `main_T` (M7.43, RA1) removes every ISR inside the span and is FLAT --
       the 15% is ISR load, and main_T is what the engine spends."""
    out = {'states': {}}
    for st, clear in (('round1_48', True), ('hurryup', True), ('r20_48', True),
                      ('r50_48', True), ('bosskilled', False)):
        h, m = new(st)
        if clear:
            for k in range(7):
                b = 0xFD94 + 10 * k
                for o in range(10):
                    m[b + o] = 0
        r, _ = h.run_until((0x98B5,), limit=60_000_000, stride=1)
        if r != 'target':
            out['states'][st] = {'reached': False}
            continue
        rnd = m[ROUND]
        bval = h.sim.registers[B]
        before = [m[0x594C + i] for i in range(10)] +                  [m[0x598C + i] for i in range(10)]
        h.memobj.watch(0x4000, 0x10000)
        t0 = h.sim.registers[T]
        n = {'98BC': 0, '802E': 0, '995A': 0, '9904': 0}
        while True:
            rr, _x = h.run_until((0x98F0, 0x98BC, 0x802E, 0x995A, 0x9904),
                                 limit=20_000_000, stride=1)
            if rr != 'target' or h.regs[PC] == 0x98F0:
                break
            n['%04X' % h.regs[PC]] += 1
            h.step(1)
        dt = h.sim.registers[T] - t0
        log = list(h.memobj.log)
        h.memobj.unwatch()
        attrs = [(p, a, v) for (p, a, v) in log if 0x5800 <= a < 0x5B00]
        cells = sorted(set(a for (_, a, _) in attrs))
        after = [m[0x594C + i] for i in range(10)] +                 [m[0x598C + i] for i in range(10)]
        out['states'][st] = {
            'reached': True, 'round': rnd, 'B_at_entry': bval,
            'iterations': n['98BC'], 'glyph_calls': n['802E'],
            'attr_calls': n['995A'], 'erases': n['9904'],
            'T': dt, 'frames': round(dt / 69888.0, 2),
            'digits': len(str(rnd)),
            'attr_writes': len(attrs), 'attr_cells': len(cells),
            'cell_lo': '%04X' % cells[0] if cells else None,
            'cell_hi': '%04X' % cells[-1] if cells else None,
            'attr_writer_pcs': sorted(set('%04X' % p for (p, _, _) in attrs)),
            'cells_before': before, 'cells_after': after,
            'restored_to_palette': after == [m[0x830A] if before[i] == m[0x830A]
                                             else after[i]
                                             for i in range(20)]}
        out['states'][st]['end_state_equals_start'] = before == after
        # RA1: the same span as MAIN-LINE T.  'T' above is WALL-CLOCK (run_until takes
        # the interrupts), and the port's step() runs those ISRs itself.
        from rounddrain import ledger
        h, m = new(st)
        if clear:
            for k in range(7):
                for o in range(10):
                    m[0xFD94 + 10 * k + o] = 0
        h.run_until((0x98B5,), limit=60_000_000, stride=1)
        t0 = h.sim.registers[T]
        isrs = ledger(h, lambda p, i: p == 0x8D0C)
        wall = h.sim.registers[T] - t0
        out['states'][st]['wall_T_to_8d0c'] = wall
        out['states'][st]['isrs_to_8d0c'] = len(isrs)
        out['states'][st]['main_T'] = wall - sum(x['cost'] for x in isrs)
    got = [v for v in out['states'].values() if v.get('reached')]
    one = [v for v in got if v['digits'] == 1 and v['round'] != 0x51]
    two = [v for v in got if v['digits'] == 2 and v['round'] != 0x51]
    out['B_is_zero_everywhere'] = all(v['B_at_entry'] == 0 for v in got)
    out['iterations'] = sorted(set(v['iterations'] for v in got))
    out['one_digit_T'] = sorted(v['T'] for v in one)
    out['two_digit_T'] = sorted(v['T'] for v in two)
    out['round81_T'] = [v['T'] for v in got if v['round'] == 0x51]
    out['one_digit_main_T'] = sorted(v['main_T'] for v in one)
    out['two_digit_main_T'] = sorted(v['main_T'] for v in two)
    out['round81_main_T'] = [v['main_T'] for v in got if v['round'] == 0x51]
    out['cells'] = 20
    return out


def phase_unowned():
    """THE TWO CALLS THE SEQUENCE EXPOSED THAT NO INCREMENT OWNED.

       $99A8 IS THE ROUND'S PLAYER INIT, and it is a TWO-ENTRY SHARED BODY:
       $99A8 CALLs $99C3 (which does P2 and falls into the tail), comes back,
       sets P1 up and JRs into the SAME tail at $99D4.  So the routine runs its
       tail twice with C = 1 then C = 0, and C is both the player index and the
       source of the (IY+7) MASK.

       $A36C is twenty bytes at $5B00 and twenty at $FDEE through $AA49 -- and
       THE PORT ALREADY HAD IT, INLINED inside I6's item handler 12 (the level
       skip, $8915).  One routine, two call sites, transliterated at one of them
       (TRAPS #58's shape).

       Every byte either routine can touch is POISONED $5A first, so a field it
       leaves alone and a field it writes with zero stay different rows."""
    POISON_OFFS = (0, 1, 5, 6, 7, 8, 0x5A, 0x5B, 0x60, 0x61)
    out = {}
    for name, entry in (('99A8', 0x99A8), ('A36C', 0xA36C)):
        h, m = new('bosskilled')
        if not to_sequence(h):
            raise SystemExit('never reached $9858')
        for base in (0xFD80, 0xFD8A):
            for off in POISON_OFFS:
                m[base + off] = POISON
        for i in range(0x14):
            m[0x5B00 + i] = POISON
            m[0xFDEE + i] = POISON
        h.memobj.watch(0x4000, 0x10000)
        arm(h, entry)
        h.run_until(tuple(h.SENTINELS), limit=400000, stride=1,
                    interrupts=False)
        log = [['%04X' % p, '%04X' % a, v] for (p, a, v) in h.memobj.log
               if a >= 0xFD80 or 0x5B00 <= a < 0x5B14]
        h.memobj.unwatch()
        out[name] = {
            'writes': len(log), 'log': log,
            'writer_pcs': sorted(set(r[0] for r in log)),
            'addrs': sorted(set(r[1] for r in log)),
            'p1': {'%02X' % o: m[0xFD80 + o] for o in POISON_OFFS},
            'p2': {'%02X' % o: m[0xFD8A + o] for o in POISON_OFFS},
            'slots_5B00_zero': all(m[0x5B00 + i] == 0 for i in range(0x14)),
            'slots_FDEE_zero': all(m[0xFDEE + i] == 0 for i in range(0x14)),
            'poison': POISON}
    return out


PHASES = [('calls', phase_calls), ('settler', phase_settler),
          ('unowned', phase_unowned),
          ('frames', phase_frames), ('banner', phase_banner),
          ('zeroing', phase_zeroing), ('handover', phase_handover)]

if __name__ == '__main__':
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    only = [a for a in sys.argv[1:] if not a.startswith('-')]
    fx = {}
    for nm, fn in PHASES:
        if only and nm not in only:
            continue
        print('--', nm, flush=True)
        fx[nm] = fn()
        print(json.dumps(fx[nm])[:1000], flush=True)
    if not only:
        json.dump(fx, open(FIXTURE, 'w'), indent=1, sort_keys=True)
        print('\nwrote', FIXTURE)
