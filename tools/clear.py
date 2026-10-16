"""$8E3A -- the LEVEL-CLEAR decision, and the tally $8EAA underneath it.

The main loop asks once per pass: `$8D5E CALL $8E3A / $8D61 JR z,$8D09`.  The
answer is the **Z FLAG**, not a memory cell -- so this is the project's first
oracle that has to capture a REGISTER rather than RAM.

    $8E3A  LD A,0 / OR A / JP nz,$8F29    $8E3B is that LD's own OPERAND: the
                                          clear-pending latch, so a cleared
                                          round skips the tally ever after
    $8E40  ($FED1) non-zero -> $8F36      the level-skip item owns the advance
    $8E47  ($8609) == $50   -> $8E4E      round 80 is the boss's HP instead
    $8EAA  the TALLY: count +7 BIT 7 over ($AA57) - 2 slots from $FD9B, publish
           it at $FECA
    $8EC5  zero alive  -> $8ECF, the one-shot cleanup, which FALLS THROUGH into
           the countdown
    $8EC7  two or more  -> RET NZ, nothing happens
    $8EC9  exactly one  -> CALL $90A9 (the anger pass, angerPass() -- M7.50)
                           then OR $2A, NZ
    $8F29  the COUNTDOWN: ($8DBE) must be exactly 1 and ($8DBD) >= $77, so the
           advance window is $0177..$01FF -- a 137-frame window, not a threshold

WHAT THIS ORACLE MUST NOT ASSUME.  The tally reads BIT 7 through RLCA/AND 1, so
a model reading bit 0 agrees on every slot whose flags happen to have both bits
equal -- and $C0, the ordinary live value, does not.  The sweep therefore uses
flag values whose bit 0 and bit 7 DIFFER ($C1, $80, $01, $41) as well as the
ordinary ones, or "count bit 7" and "count bit 0" are the same function.

THE ONE-LEFT ROWS: the exactly-one-alive path calls $90A9, the anger pass.
Until M7.50 the port's call was a stub and the gate held those rows' memory diff
out; it compares them now like every other row (the watch holds $90AA, $FEC4 and
$FEC5).  The walk's writes to the entity table are outside this watch and are
measured by tools/oneleft.py (build/oneleft_fixture.json).

Usage:  python tools/clear.py capture
        python tools/clear.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, F, IYh, IYl
import portconfig as pc

CHECK = 0x8E3A
TABLE, STRIDE = 0xFD80, 10
POOL = 0xFED8
FIXTURE = 'build/clear_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

# every byte the decision or its one-shot cleanup touches, so the gate can diff
# the whole footprint rather than the one cell it happens to think about
WATCH = {'FECA': 0xFECA, '8E3B': 0x8E3B, '9160': 0x9160, '8CB0': 0x8CB0,
         '86CD': 0x86CD, '9604': 0x9604, '9606': 0x9606, '9AE8': 0x9AE8,
         '9AE9': 0x9AE9, '8DBD': 0x8DBD, '8DBE': 0x8DBE, '9049': 0x9049,
         'FECC': 0xFECC, '90AA': 0x90AA, 'FEC4': 0xFEC4, 'FEC5': 0xFEC5,
         'AA57': 0xAA57, 'FED1': 0xFED1, '8609': 0x8609,
         # $9F62, THE BOSS HP BYTE, added by B2.  Without it the round-80 row
         # seeds no HP at all, the engine reads its own default and the WIRED
         # boss arm of the decision is ungated -- a mutation turning the whole
         # branch into a constant survives.  The critic of the H13 constructive
         # pass caught this; it is not a new watch, it is a hole being closed.
         '9F62': 0x9F62}


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{state}: not the 48K branch (TRAPS #28/#36)')
    SP0[0] = h.sim.registers[12]
    return h, m


def call(h, addr):
    """direct call with SP PINNED (TRAPS #42) -- returns (sentinel, Z flag)"""
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    h.run_until(tuple(h.SENTINELS), limit=10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('no sentinel -- PC $%04X' % h.regs[PC])
    return h.SENTINELS.index(h.regs[PC]), 1 if (r[F] & 0x40) else 0


def cases():
    """(alive, count, latch, fed1, round, lo, hi, flagval[, fecc])

       `alive` is how many of the enemy slots carry the live bit; `flagval` is
       the byte written into +7 for a live one.  $C1 / $80 / $01 / $41 exist so
       that bit 0 and bit 7 DIFFER -- with only $C0 in the sweep, a tally that
       counted bit 0 would agree everywhere.
    """
    out = []
    for alive in (0, 1, 2, 3, 7):
        for flagval in (0xC0, 0xC1, 0x80, 0x41):
            out.append((alive, 9, 0, 0, 1, 0x77, 1, flagval))
    for count in (2, 3, 4, 9, 12):
        for alive in (0, 1, 2):
            out.append((alive, count, 0, 0, 1, 0x77, 1, 0xC0))
    # the COUNTDOWN window, $0177..$01FF, reached through the latch so the tally
    # is skipped and the countdown is the only thing under test
    for (lo, hi) in ((0x00, 0x00), (0x76, 0x01), (0x77, 0x01), (0x78, 0x01),
                     (0xFF, 0x01), (0x77, 0x00), (0x77, 0x02), (0xFF, 0x02),
                     (0x00, 0x01), (0x76, 0x02)):
        out.append((3, 9, 1, 0, 1, lo, hi, 0xC0))
    # the two early branches
    for fed1 in (0, 1, 0xFF):
        out.append((3, 9, 0, fed1, 1, 0x77, 1, 0xC0))
    for rnd in (1, 0x4F, 0x50, 0x51):
        out.append((3, 9, 0, 0, rnd, 0x77, 1, 0xC0))
    # the latch, with a tally that WOULD have said something else
    for latch in (0, 1, 0xFF):
        for alive in (0, 3):
            out.append((alive, 9, latch, 0, 1, 0x77, 1, 0xC0))
    # ($FECC) is a HUD string the cleanup hands to $A84D and then CLEARS.  With
    # it zero on every row the clear is a no-op and unfalsifiable; these rows
    # give it something to clear.  The PAINT is M7.1's text layer and is not
    # modelled -- the gate compares $FECC and not the screen.
    for fecc in (1, 5, 0xFF):
        out.append((0, 9, 0, 0, 1, 0x77, 1, 0xC0, fecc))
    return out


def capture():
    h, m = new()
    rows = []
    for case in cases():
        (alive, count, latch, fed1, rnd, lo, hi, flagval) = case[:8]
        fecc = case[8] if len(case) > 8 else 0
        # a clean slate: every enemy dead, the named bytes at known values
        for k in range(12):
            m[TABLE + STRIDE * k + 7] = 0x40          # alive bit CLEAR
        for k in range(alive):
            m[TABLE + STRIDE * (2 + k) + 7] = flagval
        for k in range(12):
            m[POOL + STRIDE * k + 4] = 0x11
            m[POOL + STRIDE * k + 9] = 0x22
        m[0xAA57] = count
        m[0x8E3B] = latch
        m[0xFED1] = fed1
        m[0x8609] = rnd
        m[0x8DBD], m[0x8DBE] = lo, hi
        m[0x8DB6], m[0x8DB7] = 0x34, 0x12
        m[0x90AA] = 0                                  # the anger latch, unfired
        m[0xFECC] = fecc                               # a HUD string to repaint
        m[0xFECA] = 0xEE
        for a in (0x9160, 0x8CB0, 0x86CD, 0x9049, 0x9AE8, 0x9AE9):
            m[a] = 0
        m[0x9604] = m[0x9606] = 0x80
        m[0xFEC4] = m[0xFEC5] = 0x14
        before = {k: m[a] for k, a in WATCH.items()}
        pool = [m[POOL + i] for i in range(120)]
        sent, z = call(h, CHECK)
        rows.append({'alive': alive, 'count': count, 'latch': latch, 'fed1': fed1,
                     'round': rnd, 'lo': lo, 'hi': hi, 'flagval': flagval,
                     'fecc': fecc,
                     'z': z, 'sentinel': sent, 'before': before,
                     'after': {k: m[a] for k, a in WATCH.items()},
                     'pool_before': pool,
                     'pool_after': [m[POOL + i] for i in range(120)],
                     'angry': m[0x90AA] != 0})
    fx = {'note': __doc__.strip(), 'check_at': CHECK, 'table_at': TABLE,
          'pool_at': POOL, 'watch': WATCH, 'rows': rows}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d direct calls, %d advancing, %d that fired the anger pass'
          % (FIXTURE, len(rows), sum(r['z'] for r in rows),
             sum(1 for r in rows if r['angry'])))


def verify():
    fx = json.load(open(FIXTURE))
    R = fx['rows']
    print('rows %d   Z (advance) %d   anger pass fired %d'
          % (len(R), sum(r['z'] for r in R), sum(1 for r in R if r['angry'])))
    print('  $FECA distinct values:', sorted({r['after']['FECA'] for r in R}))
    print('  the bit-7 vs bit-0 discriminator:')
    for fv in (0xC0, 0xC1, 0x80, 0x41):
        rs = [r for r in R if r['flagval'] == fv and r['count'] == 9 and r['latch'] == 0]
        print('    flags $%02X -> $FECA %s' % (fv, sorted({r['after']['FECA'] for r in rs})))
    print('  the countdown window:')
    for r in R:
        if r['latch'] == 1 and r['count'] == 9:
            print('    $%02X%02X -> %s' % (r['hi'], r['lo'], 'ADVANCE' if r['z'] else '-'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
