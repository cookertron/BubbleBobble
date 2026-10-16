# -*- coding: utf-8 -*-
"""M7.24 -- $948F, THE EXTEND TRIGGER: the last unwired entry of the chain.

This measures the OUTER HALF only -- $948F..$94C1 and $94A9..$94BF.  The
per-player completion $94C2 is a separate increment and this tool is built so
the probe CANNOT fall into it: every phase either keeps (IX+$63) away from $3F,
or arms an ABORT PC at $94C8 and stops the stepper there.  $94C2 wipes $1AFF
bytes of shadow, makes 160 PRNG draws and ends in an interrupt-driven wait on
`BIT 7,(IY+$2A)`, none of which belongs in a probe (TRAPS #139).

  $948F   LD A,($FED5) / OR A / RET z       -- the trigger
  $9494   XOR A / LD ($FEC5),A              -- the even ISR gate DOWN
  $9498   LD ($FED5),A                      -- ...and the trigger consumed
  $949B   LD IX,$FD80 / CALL $94C2          -- P1
  $94A2   LD IX,$FD8A / CALL $94C2          -- P2
  $94A9   LD A,($FECB) / INC A / CP 4       -- the cap
  $94AF   JR z,$94BA                        -- *** SKIPS THE STORE AS WELL ***
  $94B1   LD ($FECB),A / CALL $7E04 / CALL $BF5B
  $94BA   LD A,1 / LD ($FEC5),A             -- the gate back UP
  $94BF   JP $957E                          -- the EXTEND panel IS the return

  $94C2   LD A,(IX+$63) / SUB $3F / RET nz  -- all six letters, or nothing

Usage:  python tools/extenddone.py
        python tools/extenddone.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/extenddone_fixture.json'
BRANCH_BYTE = 0x8DC4
DONE = 0x948F
PER_PLAYER = 0x94C2
ACCEPTED = 0x94C8            # the first byte past $94C2's `RET nz`
PANEL = 0x957E
X7E04 = 0x7E04
XBF5B = 0xBF5B
TRIGGER = 0xFED5
GATE = 0xFEC5
CAP = 0xFECB
LETTERS = (0xFDE3, 0xFDED)   # (IX+$63) for $FD80 and $FD8A
STATE = 'round1_48'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    if not hasattr(h, '_sp0'):
        h._sp0 = r[SP]
    r[SP] = h._sp0
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, watch_pcs=(), abort_pcs=(), limit=4 * 10 ** 6):
    """One call.  Returns (watched PCs seen, aborted?).  An ABORT stops the
       stepper dead -- it is how this tool refuses to execute $94C2."""
    seen = set()
    r = h.sim.registers
    n = 0
    while n < limit:
        if r[PC] in abort_pcs:
            return seen, True
        if r[PC] in watch_pcs:
            seen.add(r[PC])
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            return seen, False
        n += 1
    raise SystemExit('bad bracket -- PC $%04X' % r[PC])


def quiet(m):
    """A world in which $94C2 returns at once for BOTH players, so the outer
       half can be driven without the completion ever running."""
    for a in LETTERS:
        m[a] = 0x00


def snapshot(m, lo=0x4000, hi=0x10000):
    return bytes(m[lo:hi])


def diff(a, b, lo=0x4000, floor=None):
    """*** THE SNAPSHOT MUST BE TAKEN AFTER arm(), NOT BEFORE. ***  arm() pushes
       the sentinel return addresses, so a snapshot taken first reports the
       PROBE'S OWN STACK as writes by the routine -- the first run of this tool
       called 128 of them a measurement, and all but one were `FE 02 FE 04 ...`,
       the sentinels themselves.

       *** AND THE EXCLUSION IS A 64-BYTE WINDOW, NOT "BELOW SP". ***  The first
       fix said `ad < floor` and the stack here sits at $96CB -- so it silently
       dropped the display, every game variable and $7E0E, the one write $7E04
       actually makes.  A filter wide enough to hide the measurement is worse
       than the artefact it removes.  Only [sp0-64, sp0) is dropped, which is
       where this routine's CALL/RET and PUSH IX traffic lives, and the count of
       what was dropped is reported beside the count of what was kept."""
    out = []
    for i in range(len(a)):
        if a[i] != b[i]:
            ad = lo + i
            if floor is not None and floor - 64 <= ad < floor:
                continue
            out.append([ad, a[i], b[i]])
    return out


# ------------------------------------------------------------ (a) the trigger
def phase_trigger():
    rows = []
    for trig in (0x00, 0x01, 0x80, 0xFF):
        h, m = new()
        quiet(m)
        m[TRIGGER] = trig
        m[GATE] = 1
        sp0 = arm(h, DONE)
        before = snapshot(m)                       # ...AFTER the arm
        seen, _ = run(h, (PER_PLAYER, PANEL, X7E04, XBF5B))
        after = snapshot(m)
        d = diff(before, after, floor=sp0)
        rows.append({'trigger': trig, 'fed5_after': m[TRIGGER],
                     'reached_94c2': PER_PLAYER in seen,
                     'reached_957e': PANEL in seen,
                     'writes': len(d),
                     'addrs': sorted(set('%04X' % r[0] for r in d))})
    print('(a) THE TRIGGER at ($FED5)')
    for r in rows:
        print('      $%02X -> $94C2 %-3s  $957E %-3s  ($FED5) now $%02X, %d writes %s'
              % (r['trigger'], 'yes' if r['reached_94c2'] else 'no',
                 'yes' if r['reached_957e'] else 'no', r['fed5_after'],
                 r['writes'], r['addrs'] if r['writes'] <= 8 else ''))
    return rows


# --------------------------------------------------------- (b) the ISR bracket
def phase_gate():
    """($FEC5) goes DOWN at $9495 and UP at $94BA, and the port has modelled
       that bracket twice already ($7E80, $A824).  Driven from both starting
       values, and the trigger byte is watched with it."""
    rows = []
    for start in (0, 1):
        h, m = new()
        quiet(m)
        m[TRIGGER] = 1
        m[GATE] = start
        arm(h, DONE)
        lows = []
        r = h.sim.registers
        n = 0
        while n < 4 * 10 ** 6:
            lows.append(m[GATE])
            h.step(1, interrupts=False)
            if r[PC] in h.SENTINELS:
                break
            n += 1
        rows.append({'gate_before': start, 'gate_after': m[GATE],
                     'went_low': 0 in lows, 'ended_high': m[GATE] == 1,
                     'fed5_after': m[TRIGGER]})
    print('(b) THE EVEN ISR GATE ($FEC5): %s'
          % '; '.join('from %d -> %d, went low %s' % (r['gate_before'], r['gate_after'],
                                                      r['went_low']) for r in rows))
    return rows


# ------------------------------------------------ (c) $94C2's own refusal
def phase_refuse():
    """$94C2 is `LD A,(IX+$63) / SUB $3F / RET nz`.  Swept over every value for
       BOTH players, with an ABORT armed at $94C8 so the accepted case is
       OBSERVED and never EXECUTED."""
    rows = []
    for who, addr in enumerate(LETTERS):
        accepted = []
        for v in range(0x00, 0x100):
            h, m = new()
            quiet(m)
            m[addr] = v
            m[TRIGGER] = 1
            arm(h, DONE)
            _, aborted = run(h, (), (ACCEPTED,))
            if aborted:
                accepted.append(v)
        rows.append({'player': who + 1, 'addr': '%04X' % addr, 'accepted': accepted})
    print('(c) $94C2 ACCEPTS ONLY ($%s)/($%s) == $3F: P1 accepts %s, P2 accepts %s'
          % (rows[0]['addr'], rows[1]['addr'],
             ['$%02X' % v for v in rows[0]['accepted']],
             ['$%02X' % v for v in rows[1]['accepted']]))
    return rows


# --------------------------------------------------------------- (d) the cap
def phase_cap():
    """$94A9 `LD A,($FECB) / INC A / CP 4 / JR z,$94BA` -- and the jump skips
       the STORE as well as the two calls, so the fourth extend leaves ($FECB)
       exactly where it was."""
    rows = []
    for v in range(0x00, 0x08):
        h, m = new()
        quiet(m)
        m[TRIGGER] = 1
        m[CAP] = v
        arm(h, DONE)
        seen, _ = run(h, (X7E04, XBF5B, PANEL))
        rows.append({'before': v, 'after': m[CAP],
                     'x7e04': X7E04 in seen, 'xbf5b': XBF5B in seen,
                     'panel': PANEL in seen})
    print('(d) THE ($FECB) CAP')
    for r in rows:
        print('      $%02X -> $%02X   $7E04 %-3s  $BF5B %-3s  $957E %s'
              % (r['before'], r['after'], 'yes' if r['x7e04'] else 'no',
                 'yes' if r['xbf5b'] else 'no', 'yes' if r['panel'] else 'no'))
    return rows


# -------------------------------------------------------------- (e) the tail
def phase_tail():
    """$94BF is a JP, not a CALL: $957E's RET is $948F's RET.  Measured by
       counting how many times the stepper passes $957E and by checking the
       stack pointer is back where it started when the sentinel is reached."""
    h, m = new()
    quiet(m)
    m[TRIGGER] = 1
    sp0 = arm(h, DONE)
    r = h.sim.registers
    hits, n = 0, 0
    last_sp = None
    while n < 4 * 10 ** 6:
        if r[PC] == PANEL:
            hits += 1
            last_sp = r[SP]
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            break
        n += 1
    out = {'panel_entries': hits, 'sp_at_panel': last_sp, 'sp_armed': sp0,
           'tail_is_jp': last_sp == sp0, 'steps': n}
    print('(e) THE TAIL: $957E entered %d time(s); SP there $%04X against $%04X at the '
          'arm -- %s' % (hits, last_sp or 0, sp0,
                         'a JP, so the panel RETURNS the routine' if out['tail_is_jp']
                         else 'NOT a plain JP'))
    return out


# ---------------------------------------------- (f) what the whole pass writes
def phase_writes():
    """The full outer half, byte for byte, on a world where no player has the
       letters.  This is the row a port is diffed against."""
    h, m = new()
    quiet(m)
    m[TRIGGER] = 1
    m[GATE] = 1
    m[CAP] = 0
    sp0 = arm(h, DONE)
    before = snapshot(m)                           # ...AFTER the arm
    run(h)
    after = snapshot(m)
    d = diff(before, after, floor=sp0)
    below = len(diff(before, after)) - len(d)
    print('(f) THE WHOLE OUTER PASS writes %d bytes above the armed SP (and %d below it, '
          'which is its own CALL/RET and PUSH IX traffic): %s'
          % (len(d), below,
             ' '.join('$%04X:$%02X->$%02X' % (a, x, y) for a, x, y in d[:16])
             + (' ...' if len(d) > 16 else '')))
    return {'writes': d, 'count': len(d), 'below_sp': below, 'sp': sp0}


# ------------------------------------- (g) the two STUBBED round-start calls
def phase_stubs():
    """$986F `CALL $957E` and $98A7 `CALL $BF39` are both COUNTED STUBS in the
       port while the routines behind them are fully transliterated and reached
       from somewhere else -- TRAPS #58's shape, twice.  This measures what each
       call actually writes at that point in the round start, so wiring them is
       a diff and not a hope.

       *** AND BOTH TARGETS MUST BE POISONED FIRST. ***  Driven on a plain
       round1_48 both calls write ZERO bytes -- $957E because the EXTEND masks
       are $00 and it draws nothing, $BF39 because the state is already in the
       condition it produces and every store agrees with what is already there.
       A zero is not a measurement of the routine; it is a measurement of the
       world.  So the masks are set to $3F and the regions each routine writes
       are filled with $5A before the arm."""
    rows = []
    for name, site, target, poison in (
            ('$986F CALL $957E', 0x986F, 0x957E, 'letters'),
            ('$98A7 CALL $BF39', 0x98A7, 0xBF39, 'bank')):
        h, m = new()
        if poison == 'letters':
            m[LETTERS[0]] = 0x3F
            m[LETTERS[1]] = 0x3F
            for base in (0x40E0, 0x4820, 0x4860, 0x48A0, 0x48E0, 0x5020):
                for r in range(8):
                    for off in (0, 0x1F):
                        a0 = (base + off + 0x100 * r) & 0xFFFF
                        m[a0] = 0x5A
                        m[(a0 + 0xA000) & 0xFFFF] = 0x5A
            #  ...AND THE ATTRIBUTE CELLS, which the first version left alone --
            #  it reported 10 of 12 and the missing two were simply cells that
            #  already held the colour $95D0 writes.  $A091's rule, spelled out:
            #  attr = $5800 | ((((base>>8) + 7) >> 3) & 3) << 8 | (base & $FF).
            for base in (0x40E0, 0x4820, 0x4860, 0x48A0, 0x48E0, 0x5020):
                for off in (0, 0x1F):
                    hi = 0x58 | ((((base >> 8) + 7) >> 3) & 3)
                    m[((hi << 8) | ((base + off) & 0xFF)) & 0xFFFF] = 0x5A
        else:
            for a in range(0xD380, 0xD500):
                m[a] = 0x5A
            for a in range(0x5CE0, 0x5D00):
                m[a] = 0x5A
        sp0 = arm(h, target)
        before = snapshot(m)
        run(h)
        after = snapshot(m)
        d = diff(before, after, floor=sp0)
        regions = {}
        for a, _, _ in d:
            k = ('display' if a < 0x5800 else 'attrs' if a < 0x5B00 else
                 'low' if a < 0x8000 else 'vars' if a < 0xC000 else
                 'banks' if a < 0xE000 else 'shadow')
            regions[k] = regions.get(k, 0) + 1
        rows.append({'case': name, 'site': '%04X' % site, 'target': '%04X' % target,
                     'writes': len(d), 'regions': regions,
                     'first': [['%04X' % a, x, y] for a, x, y in d[:8]],
                     'p1_mask': m[LETTERS[0]], 'p2_mask': m[LETTERS[1]]})
    print('(g) THE TWO STUBBED ROUND-START CALLS')
    for r in rows:
        print('      %-20s -> %4d writes %s  (the EXTEND masks here are $%02X/$%02X)'
              % (r['case'], r['writes'], r['regions'], r['p1_mask'], r['p2_mask']))
    return rows


def capture(jobs=15):
    out = {}
    out['trigger'] = phase_trigger()
    out['gate'] = phase_gate()
    out['refuse'] = phase_refuse()
    out['cap'] = phase_cap()
    out['tail'] = phase_tail()
    out['writes'] = phase_writes()
    out['stubs'] = phase_stubs()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
