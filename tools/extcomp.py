# -*- coding: utf-8 -*-
"""M7.25 -- $94C2, THE EXTEND COMPLETION: a 4.9-second cutscene.

$948F offers each player to $94C2 (M7.24).  This is what happens when one of
them has all six letters.  MEASURED on `extcomp`, a real round-9 state sitting
at $FDE3 = $3E -- five of six -- with the sixth bit poked in, so the world is
the machine's own and not a synthetic one.

  $94C2   LD A,(IX+$63) / SUB $3F / RET nz     -- all six, or nothing
  $94C8   LD (IX+$63),A                        -- ...and A is 0, so they clear
  $94CB   DI / ($FEC4)=0 / ($FEC5)=0 / A=2 / CALL $8E0A / EI
  $94D9   ($87B2) := $C9                       -- ITEM COLLECTION OFF
  $94DE   PUSH IX
  $94E0   ($9AB3) := $31 + ((IX+$5A) AND 1)    -- '1' or '2' in the banner
  $94EA   LD (HL),L / LDIR                     -- $E000..$FAFF := 0, SIX THOUSAND
                                                  NINE HUNDRED AND TWELVE bytes
  $94F6   $856C, $856E .. $857A := 0           -- eight, at stride two
  $9500   CALL $8C14                           -- RES 7 x19, then the reveal
  $9503   CALL $957E                           -- the EXTEND panel
  $9506   ten passes of sixteen records at $9605, each pass CALL $8689
  $9537   CALL $806C                           -- the lives icons
  $953A   A=3 / CALL $8E05                     -- RET on 48K
  $953F   the banner, through $801D and $994F
  $9553   CALL $9573                           -- ~120 frames
  $9556   POP IX / INC (IX+$5C)                -- *** A LIFE ***
  $955B   CALL $806C / CALL $9573              -- ~112 frames
  $9561   BIT 7,(IY+$2A) / DEC (IX+$63) / JR nz -- 256 times, and the BIT's
                                                  flags are DISCARDED by the DEC
  $956A   POP HL / POP HL                      -- its caller's return AND $948F's
  $956C   ($87B2) := 0 / JP $8D09              -- THE ROUND ADVANCE

*** THE LOOP AT $9561 IS THREE INSTRUCTIONS, NOT THE TWO CALLS ABOVE IT. ***
$9568's `JR nz` displacement is $F7, which targets $9561 -- past $955B and
$955E.  A reading that put the calls inside it would make this routine minutes
long instead of seconds.

Most phases ABORT at $9553, before the two multi-million-T delays, so they run
in seconds; the delays are measured on their own by arming $9573 directly, and
one phase runs the whole thing once for the total and the exit state.

Usage:  python tools/extcomp.py
        python tools/extcomp.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/extcomp_fixture.json'
BRANCH_BYTE = 0x8DC4
COMPLETE = 0x94C2
BANNER = 0x9553                 # the first CALL $9573 -- the abort line
DELAY = 0x9573
ADVANCE = 0x8D09
PLAYERS = (0xFD80, 0xFD8A)
LETTERS = (0xFDE3, 0xFDED)      # (IX+$63)
LIVES = (0xFDDC, 0xFDE6)        # (IX+$5C)
ITEMGATE = 0x87B2
DIGIT = 0x9AB3
SHADOW_LO, SHADOW_HI = 0xE000, 0xFB00
TILE_BUF = 0x856C
RECORDS = 0x9605
STATE = 'extcomp'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr, ix=None):
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
    if ix is not None:
        #  IXh/IXl are 8/9 in this simulator, not 13/14 -- the first version of
        #  this tool wrote 13/14 (which are SP-adjacent and I) and reported that
        #  PLAYER TWO ACCEPTS NOTHING, because IX never moved off whatever the
        #  state had.  A probe that cannot aim is not a measurement.
        r[IXh] = (ix >> 8) & 0xFF
        r[IXl] = ix & 0xFF
    return sp


def ixreg(h):
    r = h.sim.registers
    return r[IXl] | (r[IXh] << 8)


def run(h, watch=(), abort=(), limit=30 * 10 ** 6):
    """Returns (watched PCs seen in order, aborted?, steps, T spent)."""
    seen = []
    r = h.sim.registers
    t0 = r[T]
    n = 0
    while n < limit:
        if r[PC] in abort:
            return seen, True, n, r[T] - t0
        if r[PC] in watch:
            seen.append(r[PC])
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            return seen, False, n, r[T] - t0
        n += 1
    raise SystemExit('bad bracket -- PC $%04X after %d steps' % (r[PC], n))


def ready(m, who=0, letters=0x3F):
    """One player holding all six letters.  `extcomp` already has five."""
    m[LETTERS[who]] = letters
    return m


def snap(m):
    return bytes(m[0x4000:0x10000])


def diff(a, b, floor=None, lo=0x4000):
    out = []
    for i in range(len(a)):
        if a[i] != b[i]:
            ad = lo + i
            if floor is not None and floor - 64 <= ad < floor:
                continue        # the probe's own CALL/RET traffic (TRAPS #146/#147)
            out.append([ad, a[i], b[i]])
    return out


# ---------------------------------------------------------- (a) the gate
def phase_gate():
    """Both players, every value, with an ABORT one byte past the `RET nz`."""
    rows = []
    for who in (0, 1):
        accepted = []
        for v in range(0x100):
            h, m = new()
            m[LETTERS[0]] = 0x00
            m[LETTERS[1]] = 0x00
            m[LETTERS[who]] = v
            arm(h, COMPLETE, ix=PLAYERS[who])
            _, aborted, _, _ = run(h, (), (0x94C8,))
            if aborted:
                accepted.append(v)
        rows.append({'player': who + 1, 'ix': '%04X' % PLAYERS[who],
                     'letters_at': '%04X' % LETTERS[who], 'accepted': accepted})
    print('(a) THE GATE: P1 accepts %s, P2 accepts %s'
          % (['$%02X' % v for v in rows[0]['accepted']],
             ['$%02X' % v for v in rows[1]['accepted']]))
    return rows


# ------------------------------------------------- (b) the prologue's writes
def phase_prologue():
    """Everything from $94C2 to $9553, byte for byte, for BOTH players."""
    rows = []
    for who in (0, 1):
        h, m = new()
        ready(m, who)
        if who == 1:
            m[LETTERS[0]] = 0x00
        sp0 = arm(h, COMPLETE, ix=PLAYERS[who])
        before = snap(m)
        seen, aborted, steps, t = run(h, (0x8C14, 0x957E, 0x8689, 0x806C, 0x801D,
                                          0x994F, 0x8E05, 0x8E0A), (BANNER,))
        after = snap(m)
        d = diff(before, after, floor=sp0)
        regions = {}
        for a, _, _ in d:
            k = ('display' if a < 0x5800 else 'attrs' if a < 0x5B00 else
                 'low' if a < 0x8000 else 'vars' if a < 0xC000 else
                 'banks' if a < 0xE000 else 'shadow')
            regions[k] = regions.get(k, 0) + 1
        rows.append({
            'player': who + 1, 'aborted': aborted, 'steps': steps, 't': t,
            'writes': len(d), 'regions': regions,
            'letters_after': m[LETTERS[who]],
            'itemgate': m[ITEMGATE], 'digit': m[DIGIT],
            'fec4': m[0xFEC4], 'fec5': m[0xFEC5],
            'calls': ['%04X' % p for p in seen],
            'call_counts': {('%04X' % p): seen.count(p) for p in set(seen)},
        })
    print('(b) THE PROLOGUE to $9553')
    for r in rows:
        print('      P%d: %d writes %s; ($87B2)=$%02X ($9AB3)=$%02X letters=$%02X '
              '($FEC4/$FEC5)=%d/%d; %d steps, %d T'
              % (r['player'], r['writes'], r['regions'], r['itemgate'], r['digit'],
                 r['letters_after'], r['fec4'], r['fec5'], r['steps'], r['t']))
        print('          calls: %s' % r['call_counts'])
    return rows


# -------------------------------------------------------------- (c) the wipe
def phase_wipe():
    """*** SIX THOUSAND NINE HUNDRED AND TWELVE BYTES, $E000..$FAFF. ***  The
       port's existing shadowClear() does 6,144 ($E000..$F7FF) and leaves the
       COLOUR shadow alone, so it cannot be reused.  Driven with the whole
       window poisoned so the bounds are visible at both ends."""
    h, m = new()
    ready(m)
    #  *** POISON ONLY AS WIDE AS THE QUESTION. ***  The first version filled
    #  $DF00..$FFFF and then reported the wipe as "$E000..$FEC5 with 963 gaps",
    #  because $94CD/$94D0 zero ($FEC4) and ($FEC5) BEFORE the LDIR and those two
    #  bytes were inside the poison.  A poison wider than the routine measures
    #  the routine's NEIGHBOURS.
    for a in range(0xDF00, 0xFB80):
        m[a] = 0x5A
    m[LETTERS[0]] = 0x3F
    m[ITEMGATE] = 0x00
    sp0 = arm(h, COMPLETE, ix=PLAYERS[0])
    # stop the moment the LDIR is done, before $8C14 repaints anything
    _, aborted, _, _ = run(h, (), (0x94F6,))
    lo = 0xE000
    hi = lo
    while hi < 0xFB80 and m[hi] == 0:
        hi += 1
    hi -= 1
    zeroed = [a for a in range(0xDF00, 0xFB80) if m[a] == 0]
    gaps = [a for a in range(lo, hi + 1) if m[a] != 0]
    print('(c) THE WIPE: a CONTIGUOUS run of %d zero bytes, $%04X..$%04X, %d gaps '
          'inside, %d zero anywhere in the poisoned window; $DFFF below it '
          'untouched: %s; $FB00 above it untouched: %s'
          % (hi - lo + 1, lo, hi, len(gaps), len(zeroed),
             m[0xDFFF] == 0x5A, m[0xFB00] == 0x5A))
    print('      shadowClear() does $E000..$F7FF (6144); THIS does $F800..$FAFF too '
          '-- the COLOUR shadow: %s' % ('zeroed' if m[0xFAFF] == 0 else 'NOT zeroed'))
    return {'count': hi - lo + 1, 'lo': lo, 'hi': hi, 'gaps': len(gaps),
            'zero_in_window': len(zeroed),
            'below_untouched': m[0xDFFF] == 0x5A, 'above_untouched': m[0xFB00] == 0x5A,
            'colour_shadow_zeroed': m[0xFAFF] == 0}


# ------------------------------------------------------- (d) the tile buffer
def phase_tilebuf():
    """$94F6 writes C -- zero after the LDIR -- into eight bytes at stride two."""
    h, m = new()
    ready(m)
    for a in range(TILE_BUF, TILE_BUF + 0x18):
        m[a] = 0x5A
    sp0 = arm(h, COMPLETE, ix=PLAYERS[0])
    run(h, (), (0x9500,))
    after = [m[TILE_BUF + i] for i in range(0x18)]
    written = [TILE_BUF + i for i in range(0x18) if after[i] != 0x5A]
    print('(d) $856C: %d of 24 written, at %s, all $%02X'
          % (len(written), ' '.join('$%04X' % a for a in written),
             after[0] if written else 0x5A))
    return {'written': ['%04X' % a for a in written], 'after': after,
            'value': after[0] if written else None}


# -------------------------------------------------------- (e) $8C14's prefix
def phase_res7():
    """$8C14 is $8C28 with a 20-byte prefix: RES 7 over seven enemy slots and
       twelve bubble slots.  Driven with every one of those bits SET first."""
    h, m = new()
    ready(m)
    for i in range(7):
        m[(0xFD9B + 10 * i) & 0xFFFF] = 0xFF
    for i in range(12):
        m[(0xFEDF + 10 * i) & 0xFFFF] = 0xFF
    sp0 = arm(h, COMPLETE, ix=PLAYERS[0])
    run(h, (), (0x9503,))
    en = [m[(0xFD9B + 10 * i) & 0xFFFF] for i in range(7)]
    bu = [m[(0xFEDF + 10 * i) & 0xFFFF] for i in range(12)]
    print('(e) $8C14 RES 7: enemies %s ; bubbles %s'
          % (' '.join('%02X' % v for v in en), ' '.join('%02X' % v for v in bu)))
    return {'enemies': en, 'bubbles': bu,
            'enemy_addrs': ['%04X' % ((0xFD9B + 10 * i) & 0xFFFF) for i in range(7)],
            'bubble_addrs': ['%04X' % ((0xFEDF + 10 * i) & 0xFFFF) for i in range(12)]}


# ------------------------------------------------------- (f) the item shower
def phase_records():
    """Ten passes of sixteen two-byte records at $9605, and IX is re-seeded at
       the top of every pass -- so it is 160 WRITES into SIXTEEN entries."""
    h, m = new()
    ready(m)
    for a in range(RECORDS, RECORDS + 64):
        m[a] = 0x5A
    #  the generator's state at the arm, so a gate can seed the port with it and
    #  compare the surviving block EXACTLY rather than structurally
    seed = m[0xFE86] | (m[0xFE87] << 8)
    sp0 = arm(h, COMPLETE, ix=PLAYERS[0])
    #  watch every store into the record block by stepping and sampling
    r = h.sim.registers
    writes = []
    prev = [m[RECORDS + i] for i in range(64)]
    passes = 0
    n = 0
    while n < 30 * 10 ** 6:
        if r[PC] == BANNER:
            break
        if r[PC] == 0x8689:
            passes += 1
        pc = r[PC]
        h.step(1, interrupts=False)
        cur = [m[RECORDS + i] for i in range(64)]
        for i in range(64):
            if cur[i] != prev[i]:
                writes.append([RECORDS + i, cur[i], '%04X' % pc])
        prev = cur
        n += 1
    touched = sorted(set(a for a, _, _ in writes))
    by_pc = {}
    for _, _, p in writes:
        by_pc[p] = by_pc.get(p, 0) + 1
    final = [m[RECORDS + i] for i in range(64)]
    #  *** AND THE SPLIT REFUTED THE GUESS THAT PROMPTED IT. ***  283 changes
    #  against a loop that makes 320 writes looked like a second writer -- $8689
    #  ageing the records it had just been given.  It is not: by PC the changes
    #  are $951C 123 and $9527 160, both inside the loop, and $8689 writes NONE
    #  of these bytes.  The 37 missing are $951C stores whose value already
    #  agreed, because byte0 carries a two-bit PRNG draw that repeats across ten
    #  passes.  The attribution is kept because it is what settled it.
    print('(f) THE SHOWER: %d changes into %d distinct addresses ($%04X..$%04X), '
          '%d passes through $8689; by writer PC: %s'
          % (len(writes), len(touched), touched[0] if touched else 0,
             touched[-1] if touched else 0, passes,
             dict(sorted(by_pc.items(), key=lambda kv: -kv[1]))))
    print('      the surviving block: %s'
          % ' '.join('%02X' % v for v in final[:32]))
    return {'writes': len(writes), 'distinct': len(touched), 'by_pc': by_pc,
            'addrs': ['%04X' % a for a in touched], 'passes': passes,
            'final': final, 'prng_seed': seed}


# --------------------------------------------------------- (g) the two delays
def _delay_slice(args):
    lo, hi = args
    h, m = new()
    out = []
    for a, b in [(v >> 8, v & 0xFF) for v in range(lo, hi)]:
        r = h.sim.registers
        arm(h, DELAY)
        r[0] = a          # A
        r[2] = b          # B
        t0 = r[T]
        _, _, steps, t = run(h)
        out.append([a, b, t, steps])
    return out


def phase_delay(jobs=15):
    """$9573 is a pure busy-wait.  Swept over a grid of (A, B) to get the closed
       form, and then the two real call sites are read out of the registers."""
    grid = [(a << 8) | b for a in (0, 1, 2, 45, 207, 255) for b in (0, 1, 4, 255)]
    bands = []
    for v in grid:
        bands.append((v, v + 1))
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for part in ex.map(_delay_slice, bands):
            rows.extend(part)
    #  the registers at the two real sites
    h, m = new()
    ready(m)
    arm(h, COMPLETE, ix=PLAYERS[0])
    r = h.sim.registers
    sites = {}
    n = 0
    while n < 30 * 10 ** 6:
        if r[PC] in (0x9553, 0x955E) and ('%04X' % r[PC]) not in sites:
            sites['%04X' % r[PC]] = {'a': r[0], 'b': r[2]}
        if r[PC] == 0x9561:
            break
        h.step(1, interrupts=False)
        n += 1
    print('(g) $9573, THE BUSY-WAIT: %d (A,B) points sampled' % len(rows))
    for a, b, t, steps in rows[:6]:
        print('      A=%3d B=%3d -> %d T (%.2f frames), %d steps'
              % (a, b, t, t / 69888.0, steps))
    print('      the two real sites: %s' % sites)
    return {'grid': rows, 'sites': sites}


# ---------------------------------------------------- (h) the whole thing once
def phase_whole():
    """One complete run: the total cost, the life award, the 256-iteration loop,
       the restored item gate and the exit at $8D09."""
    h, m = new()
    ready(m)
    lives0 = m[LIVES[0]]
    #  *** THE ITEM AGEING IS GATED ON ($86CD) AND ($86CF), and they are part of
    #  the world. ***  $86CC is `LD A,n / AND n / JR nz` -- when the AND is
    #  non-zero the whole age step is skipped, and $8689 (unlike $8669) never
    #  INCs the tick.  On this state they are $8A and $FF, so the shower's
    #  records are NOT aged and byte1 survives as $24.  A port whose reset()
    #  leaves them at zero ages every record and gets $25, which looks like a
    #  transliteration bug and is a world difference.
    tick = [m[0x86CD], m[0x86CF], m[0xFED1]]
    sp0 = arm(h, COMPLETE, ix=PLAYERS[0])
    before = snap(m)
    r = h.sim.registers
    t0 = r[T]
    loop = 0
    n = 0
    reached = None
    census = {}
    WATCH = (0x8C14, 0x957E, 0x8689, 0x806C, 0x801D, 0x994F, 0x8E05, 0x8E0A)
    while n < 40 * 10 ** 6:
        if r[PC] in WATCH:
            k = '%04X' % r[PC]
            census[k] = census.get(k, 0) + 1
        if r[PC] == 0x9561:
            loop += 1
        if r[PC] == ADVANCE:
            reached = 'advance'
            break
        h.step(1, interrupts=False)
        if r[PC] in h.SENTINELS:
            reached = 'sentinel'
            break
        n += 1
    t = r[T] - t0
    after = snap(m)
    d = diff(before, after, floor=sp0)
    print('(h) THE WHOLE THING: %s after %d steps, %d T (%.1f frames, %.2f s); '
          'the $9561 loop ran %d times; lives $%02X -> $%02X; ($87B2) $%02X; SP $%04X'
          % (reached, n, t, t / 69888.0, t / 3500000.0, loop,
             lives0, m[LIVES[0]], m[ITEMGATE], r[SP]))
    print('      the FULL-RUN call census (the prologue one stops at $9553): %s'
          % dict(sorted(census.items())))
    print('      the ageing gate at the arm: ($86CD)=$%02X ($86CF)=$%02X ($FED1)=$%02X'
          % tuple(tick))
    return {'reached': reached, 'steps': n, 't': t, 'frames': t / 69888.0,
            'loop': loop, 'lives_before': lives0, 'lives_after': m[LIVES[0]],
            'itemgate_after': m[ITEMGATE], 'sp_after': r[SP], 'sp_armed': sp0,
            'letters_after': m[LETTERS[0]], 'writes': len(d),
            'census': census, 'tick_86cd': tick[0], 'tick_86cf': tick[1],
            'fed1': tick[2]}


def capture(jobs=15):
    out = {}
    out['gate'] = phase_gate()
    out['prologue'] = phase_prologue()
    out['wipe'] = phase_wipe()
    out['tilebuf'] = phase_tilebuf()
    out['res7'] = phase_res7()
    out['records'] = phase_records()
    out['delay'] = phase_delay(jobs)
    out['whole'] = phase_whole()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
