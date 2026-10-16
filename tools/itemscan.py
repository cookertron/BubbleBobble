"""M7.7-I1 -- the ITEM BLOCK, the two-pass scan, and the per-round clear/decode.

TWO ROUTINES, captured by DIRECT CALL over a BUILT block:

  $8C5E  the round clear + spawn decode.  Clears SIXTY-FOUR bytes from $9603 via
         $AA49, then decodes ONE byte out of the 81-byte round table $FF90 into
         the two staged X positions ($8CAE/$8CAF) and the shared Y byte, which it
         writes to BOTH $9604 and $9606.
  $8689  the per-frame walk.  $872C := 0, THIRTY-ONE entries from $9605 with
         B=$1F, then $872C := 1 and ONE fall-through pass over $9603.

THE BLOCK IS ONE 64-BYTE ALLOCATION, $9603..$9642 = 32 slots x 2 bytes.
SLOT 0 ($9603/$9604) is the single POWER-UP slot; slots 1..31 ($9605..$9642) are
the FRUIT / points table.  Reading the base as $9605 -- which docs/SPEC.md did for
three sessions -- makes the power-up look like it lives somewhere else entirely.
    byte0 = (X & $F0) | (type & $0F)      the type is FOUR bits, 0..15
    byte1 = (Y & $F8) | (phase & 7)
    byte0 == 0 means EMPTY.  byte1 is not part of the test.

WHAT THIS ORACLE REFUSES TO ASSUME (the equal-answers list for this increment):

  * THE CLEAR IS 64 BYTES, NOT 62.  With $9603/$9604 already zero, clearing from
    $9603 and clearing from $9605 are the same function.  So the whole block is
    seeded to $FF before every call.
  * THE SCAN IS 31 ENTRIES, NOT 32.  In a zero-filled table, stopping at 31 and
    stopping at 32 agree.  So $9643/$9644 -- the two bytes PAST the block, which
    a full table's landing scan would overrun into -- are seeded to $FF, and the
    capture records whether the pass ever visits them.
  * THE ODD-ROUND SWAP IS INVISIBLE ON EVERY EVEN ROUND, and the one live dump is
    round 80.  A model that never swaps passes it.  So all 81 rounds are swept and
    the odd rows are compared against the even ones; round 81 is the control --
    odd, but exempted by $8CA5 CP $51 / RET z before the swap.
  * B = 0 ON ENTRY TO THE CPIR.  $8C61 LD B,$40 is consumed by $AA49's DJNZ, so
    BC = 14 exactly at $8C77.  A transliteration that drops the clear's counter
    would scan $860F with BC = $4000.  The sweep covers every round, so a wrong
    membership answer shows up as a wrong Y bit 7.

THE TRAVERSAL IS CAPTURED PURE: $86B1 is poked to $C9 for part B, so $86A9 pushes,
calls, returns and pops -- the visit happens and nothing downstream of it runs.
($8779's unpack, $87B2's collision and $86E6's erase are I2/I3/I5; with $86B1
RETting they are never reached, so no poke of those is needed.)

SP IS PINNED PER CALL.  Harness.call pushes six sentinels and never restores SP
(TRAPS #42) -- 10 bytes lower each time.  Over 100+ calls that walks the stack
down through the game's own variables and the capture goes quietly dead.

Usage:  python tools/itemscan.py capture
        python tools/itemscan.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

BUILD   = 0x8C5E          # the round clear + spawn decode
WALK    = 0x8689          # the two-pass scan
ENTRY   = 0x86A9          # the per-entry call -- where the visits are trapped
PERSLOT = 0x86B1          # poked to $C9 so the traversal is pure
BLOCK   = 0x9603          # slot 0 = the power-up slot
BLOCK_N = 64              # 32 slots x 2 bytes
OVERRUN = 0x9643          # the two bytes PAST the block
ROUND_TAB, ROUND_N = 0xFF90, 81
MEMBERS = 0x860F          # the 14-byte round list the CPIR searches
FIXTURE = 'build/itemscan_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

WATCH = {'8CAE': 0x8CAE, '8CAF': 0x8CAF, '8CB0': 0x8CB0,
         '872C': 0x872C, '8609': 0x8609}


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    """point the machine at `addr` from a FIXED stack pointer (TRAPS #42)"""
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr


def run_call(h):
    """run to a sentinel; assert it is the one the call was armed on."""
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS:
        raise SystemExit('never reached a sentinel -- PC $%04X' % r[PC])
    idx = h.SENTINELS.index(r[PC])
    if idx != 0:
        raise SystemExit('returned on sentinel %d, not 0 -- the call ate its own '
                         'return address' % idx)


def run_walk(h):
    """$8689 to its sentinel, trapping every $86A9 visit on the way.

       Each trap records the entry POINTER (HL) and the pass flag ($872C) as the
       machine had them at that instant -- so the capture answers "which slots, in
       what order, under which bank" rather than just "how many".
    """
    visits = []
    for _ in range(80):
        h.run_until((ENTRY,) + tuple(h.SENTINELS), limit=10 ** 6, stride=1,
                    interrupts=False)
        r = h.regs
        if r[PC] != ENTRY:
            break
        hl = (r[6] << 8) | r[7]                     # H, L
        visits.append({'hl': hl, 'pass': h.memobj.m[0x872C]})
        h.step(1)
    r = h.regs
    if r[PC] not in h.SENTINELS:
        raise SystemExit('walk never returned -- PC $%04X' % r[PC])
    if h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('walk returned on the wrong sentinel')
    return visits


# ------------------------------------------------------------------ part A
def build_rows(h, m):
    """$8C5E over every one of the 81 rounds."""
    rows = []
    for rnd in range(1, ROUND_N + 1):
        for i in range(BLOCK_N + 2):                # the block AND the overrun
            m[BLOCK + i] = 0xFF
        for a in (0x8CAE, 0x8CAF, 0x8CB0):
            m[a] = 0xFF
        # $872C belongs to the WALK, not the build.  Seeding it to a sentinel
        # turns its row into the negative assertion "the build leaves the pass
        # flag alone" -- rather than a comparison of whatever the previous call
        # happened to leave behind, which is what it was.
        m[0x872C] = 0xFF
        m[0x8609] = rnd
        arm(h, BUILD)
        run_call(h)
        rows.append({'round': rnd,
                     'src': m[ROUND_TAB + rnd - 1],
                     'block': [m[BLOCK + i] for i in range(BLOCK_N)],
                     'overrun': [m[OVERRUN], m[OVERRUN + 1]],
                     'after': {k: m[a] for k, a in WATCH.items()}})
    return rows


# ------------------------------------------------------------------ part B
def walk_cases():
    """(name, {slot: byte0}) -- the block is otherwise empty.

       Slot 0 is the power-up slot, slots 1..31 the fruit table.  Every case
       names the slots it fills, so a model that walks the wrong range, the wrong
       direction, or the wrong number of entries disagrees on the ORDER, not just
       the count.
    """
    out = [
        ('empty', {}),
        ('all 32 slots', dict((k, 0x10 | (k & 0x0F)) for k in range(32))),
        ('the power-up slot alone', {0: 0x31}),
        ('the first fruit slot alone', {1: 0x42}),
        ('the LAST fruit slot alone -- proves B=$1F reaches entry 31', {31: 0x53}),
        ('both ends, no middle', {0: 0x64, 1: 0x75, 31: 0x86}),
        ('the fruit table full, the power-up slot empty',
         dict((k, 0x10 | (k & 0x0F)) for k in range(1, 32))),
        ('the power-up slot only, fruit table full',
         dict([(0, 0x97)] + [(k, 0x20 | (k & 0x0F)) for k in range(1, 32)])),
        ('every other slot', dict((k, 0x10 | (k & 0x0F)) for k in range(0, 32, 2))),
        ('the odd slots', dict((k, 0x10 | (k & 0x0F)) for k in range(1, 32, 2))),
        # a byte0 whose LOW NIBBLE is zero but whose X is not: still non-empty
        ('byte0 = $F0 -- X set, type 0, must NOT read as empty', {5: 0xF0}),
        # ...and the converse: type set, X zero
        ('byte0 = $0F -- X zero, type 15, must NOT read as empty', {6: 0x0F}),
    ]
    # THE STATE $8C5E ACTUALLY LEAVES: byte0 cleared to zero, byte1 holding the
    # staged Y.  Without this, byte0 and byte1 are zero and non-zero together in
    # every case, so "empty means byte0 == 0" and "empty means byte1 == 0" agree
    # everywhere and a gate cannot tell them apart -- which is exactly how the
    # mutation "the power-up slot uses the same emptiness test as byte1" survived.
    out.append(('the power-up slot CLEARED but its Y staged -- what the round '
                'build leaves', {}, {0: 0x41}))
    out.append(('a fruit slot cleared but its Y left behind -- a collected item',
                {}, {4: 0xAA}))
    out.append(('slot 0 staged AND a fruit present: only the fruit is visited',
                {7: 0x25}, {0: 0x41}))
    return out


def walk_rows(h, m):
    rows = []
    saved = m[PERSLOT]
    m[PERSLOT] = 0xC9                                # pure traversal
    for case in walk_cases():
        name, fill = case[0], case[1]
        b1 = case[2] if len(case) > 2 else {}
        for i in range(BLOCK_N):
            m[BLOCK + i] = 0
        m[OVERRUN] = 0xFF                            # the 31-vs-32 tie-breaker
        m[OVERRUN + 1] = 0xFF
        for slot, b0 in fill.items():
            m[BLOCK + 2 * slot] = b0
            m[BLOCK + 2 * slot + 1] = 0x40 | (slot & 7)
        for slot, v in b1.items():                   # byte1 WITHOUT a byte0
            m[BLOCK + 2 * slot + 1] = v
        m[0x872C] = 0xFF                             # neither 0 nor 1 to start
        arm(h, WALK)
        visits = run_walk(h)
        rows.append({'name': name,
                     'fill': dict((str(k), v) for k, v in fill.items()),
                     'b1': dict((str(k), v) for k, v in b1.items()),
                     'visits': visits,
                     'block': [m[BLOCK + i] for i in range(BLOCK_N)],
                     'overrun': [m[OVERRUN], m[OVERRUN + 1]],
                     'after_872C': m[0x872C]})
    m[PERSLOT] = saved
    return rows


def capture():
    h, m = new()
    members = [m[MEMBERS + i] for i in range(14)]
    rounds = build_rows(h, m)
    walks = walk_rows(h, m)
    fx = {'note': __doc__.strip(),
          'build_at': BUILD, 'walk_at': WALK, 'entry_at': ENTRY,
          'block_at': BLOCK, 'block_n': BLOCK_N, 'overrun_at': OVERRUN,
          'round_tab': ROUND_TAB, 'members_at': MEMBERS, 'members': members,
          'round_bytes': [m[ROUND_TAB + i] for i in range(ROUND_N)],
          'watch': WATCH, 'rounds': rounds, 'walks': walks}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d rounds, %d walk cases, %d visits total'
          % (FIXTURE, len(rounds), len(walks),
             sum(len(w['visits']) for w in walks)))
    print('  rounds whose Y byte has bit 7 (found in the $860F list): %d'
          % sum(1 for r in rounds if r['block'][1] & 0x80))


def verify():
    fx = json.load(open(FIXTURE))
    R, W = fx['rounds'], fx['walks']
    print('the $860F membership list:', ' '.join('%02X' % b for b in fx['members']))
    print()
    print('round  src  $8CAE $8CAF   $9604 $9606  bit7  swap?')
    for r in R[:6] + [x for x in R if x['round'] in (79, 80, 81)]:
        b = r['src']
        xpu = (b >> 1) & 0x70
        print('  %3d   %02X    %02X    %02X      %02X    %02X    %s   %s'
              % (r['round'], b, r['after']['8CAE'], r['after']['8CAF'],
                 r['block'][1], r['block'][3],
                 'Y' if r['block'][1] & 0x80 else '-',
                 'SWAPPED' if r['after']['8CAE'] != xpu else 'no'))
    print()
    print('the block is cleared to zero on every round (bar the two staged Y bytes):',
          all(all(v == 0 for i, v in enumerate(r['block']) if i not in (1, 3))
              for r in R))
    print('the two bytes past the block are NEVER touched by the clear:',
          all(r['overrun'] == [0xFF, 0xFF] for r in R))
    print()
    for w in W:
        order = ' '.join('$%04X/%d' % (v['hl'], v['pass']) for v in w['visits'])
        print('  %-58s %2d visits  %s'
              % (w['name'], len(w['visits']), order[:64]))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
