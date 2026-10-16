"""M7.7-H10 -- THE $D380 PRE-SHIFTED ELEMENT SPRITE BANK ($BF39 -> $BF5B).

BLOCKING for anything that draws an element or EXTEND bubble, and it KILLS the
idea of shipping $D380 as an asset: the bank's CONTENT IS A FUNCTION OF ($7E0E),
which H6 showed is redrawn from the refresh register on fifteen rounds.  Two
builds of the SAME ROUND can differ, so nothing here may be keyed on the round.

  $BF39  a 12-slot bubble-pool clear ($FED8, stride 10) that FALLS INTO $BF53
         (the 28-byte sparkle clear) and then into $BF5B.  Three routines, one
         entry, no CALL between them.
  $BF5B  LD HL,$D380 / LD B,$80 / CALL $AA49 / CALL $AA49.
         *** 384 ZERO BYTES, NOT 128. ***  $AA49 is XOR A / LD (HL),A / INC HL /
         DJNZ, which leaves B = 0, so the SECOND call runs 256 times (TRAPS #45).
         All 384 are then overwritten by the LDIR from $C780 at $BF6F.
  $BF74  the element patch: LD A,($7E0E) / SUB 2 / ADD A,A into a TWELVE-entry
         word table at $C068 -- $B614/$B61C/$B624 for classes 2/3/4, then eight
         ROM charset pointers for 5..12 (H6).  Four groups of four writes at
         $D38C/$D38D/$D391/$D390, stepping SIX.
  $BFB5  the seven regenerated shifts.

*** THE SHIFT RULE, BECAUSE THE OBVIOUS IMPLEMENTATION FAILS. ***  Each block is
EIGHT groups of SIX bytes.  Bytes 0,1,2 shift right as ONE 24-bit MSB-first value
(SRL / RR / RR).  Then $BFD4 ADD HL,3 lands on byte 5, and bytes 5,4,3 shift as a
SECOND 24-bit value WITH BYTE 5 AS THE MSB -- the second triple is stored in
REVERSED byte order.  A naive 48-bit MSB-first shift of the 6-byte row fails.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * THAT THE BANK IS A FUNCTION OF THE ROUND.  It is a function of ($7E0E).  The
    md5s are keyed on the CLASS, and the class is driven over its whole range
    0..12 directly, not sampled from whatever rounds happen to produce.

  * THAT CLASS 0 IS SAFE.  H6 measured SUB 2 / ADD A,A giving $FC for class 0, so
    the 31 rounds in no list read the word 252 BYTES PAST the twelve entries, at
    $C164.  That bank is built from a pointer nobody chose, and it is REPRODUCED,
    not repaired.

  * THAT COPYING $C780 IS ENOUGH.  $C780's OWN blocks 1..7 are NOT equal to the
    regenerated ones -- the generator overwrites them -- so the gate compares the
    finished bank, not the source.

  * THAT A ZEROED DESTINATION SHOWS THE FILL.  $D380 is seeded $5A first, or the
    384-byte clear and the 384-byte LDIR are indistinguishable from each other
    and from nothing at all (TRAPS #44).

Usage:  python tools/elembank.py capture
        python tools/elembank.py verify
"""
import sys, json, hashlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

POOLCLR = 0xBF39
SPARKCLR = 0xBF53
BANK_BUILD = 0xBF5B
BANK, BANK_N = 0xD380, 0x180          # 384 = 8 blocks x 48
SRC = 0xC780
PTR_TAB = 0xC068
ELEM = 0x7E0E
PATCH_AT = 0xD38C
BUILD = 0x97F8
ROUND = 0x8609
POOL = 0xFED8
SPARKLE = 0x5CE0
SEED = 0x5A
ROUNDS = (1, 2, 5, 20, 56, 72, 80, 81)
FIXTURE = 'build/elembank_fixture.json'


def census(h, m, addr, seed_bank=True):
    if seed_bank:
        for i in range(BANK_N):
            m[BANK + i] = SEED
    h.memobj.watch(0x4000, 0x10000)
    sp = RC.arm(h, addr)
    h.run_until(h.SENTINELS, limit=40 * 10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS or h.SENTINELS.index(h.regs[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
    log = list(h.memobj.log)
    h.memobj.unwatch()
    by_pc = {}
    for (p_, _a, _v) in log:
        k = '%04X' % p_
        by_pc[k] = by_pc.get(k, 0) + 1
    bank = bytes(m[BANK:BANK + BANK_N])
    return {'writes': len(log), 'by_pc': by_pc,
            'bank_writes': sum(1 for (_p, a, _v) in log if BANK <= a < BANK + BANK_N),
            'md5': hashlib.md5(bank).hexdigest(),
            'still_seed': sum(1 for b in bank if b == SEED)}


# ------------------------------------------- (a) the class, over its whole range
def class_rows(h, m):
    """THE BANK IS A FUNCTION OF ($7E0E) AND OF NOTHING ELSE.  Driven over the
       whole range the walk can produce -- 0, 2, 3, 4 and the eight randomised
       classes 5..12 -- plus 1, which the walk never produces but the arithmetic
       admits."""
    rows = []
    for cls in range(0, 13):
        m[ELEM] = cls
        c = census(h, m, BANK_BUILD)
        a = (PTR_TAB + (((cls - 2) & 0xFF) * 2 & 0xFF)) & 0xFFFF
        c['class'] = cls
        c['ptr_slot'] = '%04X' % a
        c['ptr'] = '%04X' % (m[a] | (m[a + 1] << 8))
        c['bank'] = [m[BANK + i] for i in range(BANK_N)]
        rows.append(c)
    return rows


# --------------------------------------- (b) whole builds -- keyed on the CLASS
def build_rows(h, m):
    RC.suppress_warp(m)
    m[ROUND] = 0x00
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        for i in range(BANK_N):
            m[BANK + i] = SEED
        sp = RC.arm(h, BUILD)
        RC.run(h, sp)
        if m[ROUND] in ROUNDS:
            bank = bytes(m[BANK:BANK + BANK_N])
            rows.append({'round': m[ROUND], 'elem': m[ELEM],
                         'md5': hashlib.md5(bank).hexdigest(),
                         'still_seed': sum(1 for b in bank if b == SEED)})
    return rows


# ------------------------------------------------- (c) the FALL-THROUGH chain
def fallthrough_rows(h, m):
    """$BF39 -> $BF53 -> $BF5B are three routines with ONE entry and no CALL
       between them, so entering at $BF39 does all three.  Seeded apart so each
       stage is separable."""
    out = {}
    for name, addr in (('BF39', POOLCLR), ('BF53', SPARKCLR), ('BF5B', BANK_BUILD)):
        for i in range(120):
            m[POOL + i] = 0x5A
        for i in range(0x20):
            m[SPARKLE + i] = 0x5A
        for i in range(BANK_N):
            m[BANK + i] = SEED
        h.memobj.watch(0x4000, 0x10000)
        sp = RC.arm(h, addr)
        h.run_until(h.SENTINELS, limit=10 ** 7, stride=1, interrupts=False)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        out[name] = {
            'writes': len(log),
            'pool': sum(1 for (_p, a, _v) in log if POOL <= a < POOL + 120),
            'sparkle': sum(1 for (_p, a, _v) in log if SPARKLE <= a < SPARKLE + 0x20),
            'bank': sum(1 for (_p, a, _v) in log if BANK <= a < BANK + BANK_N),
            'pool_left': [m[POOL + i] for i in range(10)],
            'sparkle_left': sum(1 for i in range(0x20) if m[SPARKLE + i] == 0x5A),
        }
    return out


# ----------------------------------------------------- (d) the PYTHON MODEL
def model(m, cls):
    """Block 0 = $C780[0..47] with the element glyph OR'd in, then seven
       successive one-pixel RIGHT shifts under the two-triple rule."""
    blk = [m[SRC + i] for i in range(48)]
    a = (PTR_TAB + (((cls - 2) & 0xFF) * 2 & 0xFF)) & 0xFFFF
    ptr = m[a] | (m[a + 1] << 8)
    ix = PATCH_AT - BANK
    # $BFEE is LD A,(HL) / RRCA x4 / LD C,A / AND 15 -- FOUR ROTATES SWAP THE
    # NIBBLES, so A comes back holding the ORIGINAL HIGH nibble in the LOW
    # position and C holds the whole swapped byte.  `LD A,C / AND $F0` is then
    # the original LOW nibble in the HIGH position.  I first modelled it as a
    # plain low/high mask and the bank came out 42 to 109 bytes wrong, while the
    # SHIFT rule alone reproduced block 1 from block 0 exactly -- which is what
    # located the error.
    for k in range(4):                                   # $BFB3 DJNZ, B = 4
        d = m[(ptr + 2 * k) & 0xFFFF]
        blk[ix] |= (d >> 4) & 0x0F                       # $BF8E OR (IX)
        blk[ix + 1] |= (d << 4) & 0xF0                   # $BF97 OR (IX+1)
        d2 = m[(ptr + 2 * k + 1) & 0xFFFF]
        blk[ix + 5] |= (d2 >> 4) & 0x0F                  # $BFA1 OR (IX+5)
        blk[ix + 4] |= (d2 << 4) & 0xF0                  # $BFAA OR (IX+4)
        ix += 6                                          # $BFB1 ADD IX,DE
    out = list(blk)
    for _ in range(7):                                   # $BFB9 LD A,7
        nxt = list(blk)
        for g in range(8):                               # $BFCA LD B,8
            o = g * 6
            v = (nxt[o] << 16) | (nxt[o + 1] << 8) | nxt[o + 2]
            v >>= 1                                      # SRL / RR / RR
            nxt[o], nxt[o + 1], nxt[o + 2] = (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF
            w = (nxt[o + 5] << 16) | (nxt[o + 4] << 8) | nxt[o + 3]   # BYTE 5 IS THE MSB
            w >>= 1
            nxt[o + 5], nxt[o + 4], nxt[o + 3] = (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF
        out += nxt
        blk = nxt
    return out


def model_rows(h, m):
    out = []
    for cls in range(0, 13):
        m[ELEM] = cls
        census(h, m, BANK_BUILD)
        got = [m[BANK + i] for i in range(BANK_N)]
        want = model(m, cls)
        bad = [i for i in range(BANK_N) if got[i] != want[i]]
        out.append({'class': cls, 'differing': len(bad),
                    'first_bad': bad[0] if bad else None})
    return out


def naive_rows(h, m):
    """AND THE MODEL THAT LOOKS RIGHT AND IS NOT: one 48-bit MSB-first shift of
       each six-byte row.  Reported as the number of bytes it gets wrong, so the
       two-triple rule is a MEASUREMENT and not a preference."""
    out = []
    for cls in (0, 2, 3, 4, 11):
        m[ELEM] = cls
        census(h, m, BANK_BUILD)
        got = [m[BANK + i] for i in range(BANK_N)]
        blk = model(m, cls)[:48]
        naive = list(blk)
        acc = list(blk)
        for _ in range(7):
            nxt = list(acc)
            for g in range(8):
                o = g * 6
                v = 0
                for j in range(6):
                    v = (v << 8) | nxt[o + j]
                v >>= 1
                for j in range(5, -1, -1):
                    nxt[o + j] = v & 0xFF
                    v >>= 8
            naive += nxt
            acc = nxt
        out.append({'class': cls,
                    'naive_differing': sum(1 for i in range(BANK_N)
                                           if got[i] != naive[i])})
    return out


def substitute_rows(h, m):
    """*** THE PORT CANNOT BUILD THREE OF THESE BANKS FAITHFULLY, AND THIS SAYS
       EXACTLY HOW MUCH. ***  Classes 5..12 overlay SPECTRUM ROM CHARSET cells and
       class 0 overlays $05E0 -- eight bytes of ROM *CODE* (not quoted: no ROM byte is
       written in this repository), reached because SUB 2 / ADD A,A runs 252 bytes past the twelve-entry
       table.  Measured: that overlay changes 99 of the 384 bytes, so it is not
       invisible and cannot be waved away.

       The port ships no ROM.  So for every class whose pointer lands below
       $4000 the MACHINE is made to build the bank from the PORT'S OWN
       substitute -- the drawn letters for 5..12, zeros for class 0 and 1 -- by
       repointing the table entry at a RAM scratch block.  That gives the engine
       an EXACT target for everything except the eight glyph bytes themselves,
       which are the declared departure.  (The harness drops writes below $4000,
       so the substitute cannot simply be poked over the ROM.)"""
    letters = json.load(open('build/letters.json'))['letters']
    rom_at = [int(a, 16) for a in json.load(open('build/letters.json'))['rom_at']]
    SCRATCH = 0x7000
    rows = []
    for cls in range(0, 13):
        a = (PTR_TAB + (((cls - 2) & 0xFF) * 2 & 0xFF)) & 0xFFFF
        ptr = m[a] | (m[a + 1] << 8)
        if ptr >= 0x4000:                       # $B614/$B61C/$B624 -- real RAM data
            m[ELEM] = cls
            c = census(h, m, BANK_BUILD)
            rows.append({'class': cls, 'ptr': '%04X' % ptr, 'substituted': False,
                         'glyph': [m[(ptr + i) & 0xFFFF] for i in range(8)],
                         'md5': c['md5'],
                         'bank': [m[BANK + i] for i in range(BANK_N)]})
            continue
        sub = letters[rom_at.index(ptr)] if ptr in rom_at else [0] * 8
        for i in range(8):
            m[SCRATCH + i] = sub[i]
        keep = (m[a], m[a + 1])
        m[a], m[a + 1] = SCRATCH & 0xFF, SCRATCH >> 8
        m[ELEM] = cls
        c = census(h, m, BANK_BUILD)
        bank = [m[BANK + i] for i in range(BANK_N)]
        m[a], m[a + 1] = keep
        rows.append({'class': cls, 'ptr': '%04X' % ptr, 'substituted': True,
                     'rom_glyph': ptr in rom_at, 'glyph': sub,
                     'md5': c['md5'], 'bank': bank})
    return rows


# --------------------------------------------------------------------- main
def capture():
    h, m = RC.new()
    out = {
        'note': ('M7.7-H10 the $D380 element bank.  ITS CONTENT IS A FUNCTION OF '
                 '($7E0E), not of the round, so nothing here is keyed on the round. '
                 '$BF5B zeroes 384 bytes and not 128 because $AA49 leaves B = 0 and '
                 'the second call runs 256 times (TRAPS #45).  The seven shifts are '
                 'TWO 24-BIT SHIFTS PER SIX-BYTE GROUP, the second with byte 5 as '
                 'the MSB -- a naive 48-bit shift fails.'),
        'bank_at': BANK, 'bank_n': BANK_N, 'src_at': SRC, 'ptr_tab': PTR_TAB,
        'elem_at': ELEM, 'patch_at': PATCH_AT, 'build_at': BANK_BUILD,
        'pool_clear_at': POOLCLR, 'spark_clear_at': SPARKCLR,
        'pool_at': POOL, 'sparkle_at': SPARKLE, 'seed': SEED,
        'src_bytes': [m[SRC + i] for i in range(48)],
        'classes': class_rows(h, m),
        'fallthrough': fallthrough_rows(h, m),
        'model': model_rows(h, m),
        'substitute': substitute_rows(h, m),
        'naive': naive_rows(h, m),
        'builds': build_rows(h, m),
    }
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('wrote %s' % FIXTURE)
    verify(out)


def verify(f=None):
    if f is None:
        f = json.load(open(FIXTURE))
    for r in f['classes']:
        print('class %2d  ptr %s=$%s  %4d writes (%d into the bank), %d still $5A, md5 %s'
              % (r['class'], r['ptr_slot'], r['ptr'], r['writes'], r['bank_writes'],
                 r['still_seed'], r['md5'][:12]))
    print('write census by PC (class 2): %s'
          % {k: v for k, v in sorted(f['classes'][2]['by_pc'].items()) if v > 3})
    ft = f['fallthrough']
    for k in ('BF39', 'BF53', 'BF5B'):
        print('entry $%s -> %d writes: pool %d, sparkle %d, bank %d (sparkle left $5A: %d)'
              % (k, ft[k]['writes'], ft[k]['pool'], ft[k]['sparkle'], ft[k]['bank'],
                 ft[k]['sparkle_left']))
    print('PYTHON MODEL differing bytes per class: %s'
          % {r['class']: r['differing'] for r in f['model']})
    sub = f['substitute']
    print('SUBSTITUTED banks (the port ships no ROM): %s'
          % [(r['class'], r['ptr'], 'sub' if r['substituted'] else 'real')
             for r in sub])
    print('the NAIVE 48-bit shift gets wrong: %s'
          % {r['class']: r['naive_differing'] for r in f['naive']})
    byclass = {}
    for r in f['builds']:
        byclass.setdefault(r['elem'], set()).add(r['md5'][:12])
    print('whole builds, keyed on $7E0E: %s'
          % {k: sorted(v) for k, v in sorted(byclass.items())})
    print('  rounds: %s' % [(r['round'], r['elem'], r['md5'][:8]) for r in f['builds']])


if __name__ == '__main__':
    (capture if (len(sys.argv) > 1 and sys.argv[1] == 'capture') else verify)()
