"""M7.7-I4 -- the SCORE AWARD $80FA and the pending-field clear $8161.

THE RENDERER IS NOT STUBBED, AND CANNOT BE.  $816B does not merely draw: its
four-iteration loop ends with HL four bytes below where it started, so it
RETURNS HL = base - 1, and $8129's `LD DE,4 / ADD HL,DE` depends on exactly
that to point the high-score compare at the player's MSB.  Poking $816B to RET
-- which is how the first version of this oracle tried to isolate the
arithmetic -- leaves HL four bytes high, so $812E compares against the PENDING
FIELD instead and the copy silently stops firing.  The award and the renderer
are one mechanism; they are captured together.

    $80FA  CP 3 / RET nc                    -- A >= 3 rejected, pending NOT cleared
    $80FD  C := 4*A   (the score stride)    and  HL := 10*A  (the entity stride)
    $8108  LD DE,$FD7D / ADD HL,DE / BIT 7,(HL) / JR z,$815C
                                            -- the guard is the PLAYER ENTITY's +7
    $8112  LD HL,$FFE1 / ADD HL,BC          -- base = $FFE1 + 4*A
    $811B  four times: LD A,(DE) / ADC A,(HL) / DAA / LD (HL),A
    $8123  LD ($8607),HL / CALL $816B       -- and $816B CLEARS the pending
    $812E  compare $FFE4 down against base+3, MSB first
    $8140  LD DE,$FFE4 / LDD x4             -- copy the player's field into HIGH
    $815C  the inactive player: CALL $8161 and DISCARD the pending

THREE FIELDS, four packed-BCD bytes each, MSB at the HIGH address:
    HIGH $FFE1-$FFE4    P1 $FFE5-$FFE8    P2 $FFE9-$FFEC
and the player index is 1 or 2, never 0 -- $880E BIT 0,(IX+$5A) makes it so, and
slot 0 of the table is the high score itself.

WHAT THIS ORACLE REFUSES TO ASSUME:

  * HIGH == P1 IN THE CAPTURES.  image.bin holds both at 34 63 04 00, and that
    coincidence is exactly what put "P1 SCORE = $FFE4-$FFE7, TRIPLY confirmed"
    into docs/SPEC.md -- a four-byte window starting one byte early, straddling
    the high-score MSB.  Every award row therefore pokes HIGH to 99 99 99 99 so
    the copy CANNOT fire, and asserts that only the player's own four bytes move;
    then the mirror rows let the copy fire and check it lands in $FFE1-$FFE4.
  * THE PENDING FIELD IS NEVER SEEDED TO ZERO when the clear is under test.
    $FFED-$FFF0 is 00 00 00 00 at rest, so "clear four bytes", "clear two" and
    "do not clear at all" are the same function.  $8161's rows seed FF FF FF FF.
  * THE FOURTH ADD ITERATION.  No captured score reaches 1,000,000 internal, so
    a three-byte add is indistinguishable from the real four-byte one.  Rows
    poke 99 99 99 xx and award enough to carry into the top byte.
  * OVERFLOW PAST EIGHT DIGITS.  The carry out of the fourth DAA is DISCARDED,
    so the score wraps mod 100,000,000.  Poked to 99 99 99 99.
  * THE LINEAR PART OF $8649.  Types 0..8 are exactly $0010 * (t+1), so a port
    that COMPUTES the value instead of reading the table passes every low-type
    row.  The award sweep covers all sixteen types, 9..15 included.
  * THE INACTIVE-PLAYER DISCARD.  In one-player play $80FA is reached with A=2
    only where the pending is already zero, so the discard is invisible.  Rows
    clear the guard bit AND seed the pending non-zero.

PROVED EQUIVALENT, NOT TESTED: the carry into the FIRST ADC.  $8115's ADD HL,BC
sums $FFE1 + 4*A with A <= 2, so it maxes at $FFE9 and can never carry out of
sixteen bits -- ADD and "ADC with whatever carry survived" agree on every
reachable input.  It is recorded here as a bounded-operand argument rather than
as a row, because no measurement can distinguish them.

SP IS PINNED PER CALL and the sentinel asserted (TRAPS #42).

Usage:  python tools/score.py capture
        python tools/score.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

AWARD = 0x80FA
CLEAR = 0x8161
HUD = 0x816B              # poked to RET: I4b
PEND = 0xFFED             # the pending add, four bytes
FIELD = 0xFFE1            # HIGH; +4 = P1, +8 = P2
GUARD = 0xFD7D            # the guard byte is ($FD7D + 10*A), i.e. the entity's +7
VALUES = 0x8649
FIXTURE = 'build/scoreaward_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, a=None):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    if a is not None:
        r[0] = a
    r[PC] = addr
    return sp


def run(h, sp):
    h.run_until(h.SENTINELS, limit=10 ** 6, stride=1, interrupts=False)
    r = h.regs
    if r[PC] not in h.SENTINELS or h.SENTINELS.index(r[PC]) != 0:
        raise SystemExit('bad bracket -- PC $%04X' % r[PC])
    if r[12] != sp + 2:
        raise SystemExit('SP ended at $%04X, expected $%04X -- the call ate the stack'
                         % (r[12], sp + 2))


def fields(m):
    return {'high': [m[FIELD + i] for i in range(4)],
            'p1':   [m[FIELD + 4 + i] for i in range(4)],
            'p2':   [m[FIELD + 8 + i] for i in range(4)],
            'pend': [m[PEND + i] for i in range(4)]}


def award_cases():
    """(name, A, amount, high, p1, p2, guard_set)

       Scores are little-endian packed BCD, MSB last.
    """
    Z = [0, 0, 0, 0]
    BIG = [0x99, 0x99, 0x99, 0x99]
    out = []
    # THE COPY CANNOT FIRE: HIGH pinned at the maximum.  Only the player's own
    # four bytes may move, which is the check that would have caught SPEC's
    # one-byte-early window.
    for a in (1, 2):
        for amt in ([0x10, 0, 0, 0], [0x00, 0x10, 0, 0], [0x00, 0x04, 0, 0],
                    [0x99, 0x99, 0x99, 0x99], [0x01, 0, 0, 0]):
            out.append(('copy blocked A=%d amt=%s' % (a, amt[:2]),
                        a, amt, list(BIG), Z[:], Z[:], True))
    # ...and now let the copy fire, from a LOW high score
    for a in (1, 2):
        out.append(('copy fires A=%d' % a, a, [0x00, 0x10, 0, 0],
                    [0x00, 0x01, 0, 0], Z[:], Z[:], True))
    # A COPY WHOSE EVERY BYTE DIFFERS.  In the rows above the player's LSB and
    # HIGH's LSB happen to match, so copying three bytes and copying four are
    # the same function -- the mutation "the copy is three bytes" survives them
    # all.  Here every one of the four differs.
    out.append(('copy fires, all four bytes differ', 1, [0x11, 0x11, 0x11, 0x00],
                [0x22, 0x33, 0x44, 0x00], [0x55, 0x66, 0x77, 0x00], Z[:], True))
    # THE ABANDON BRANCH ($8139 JP $8158): HIGH strictly greater, so no copy
    out.append(('abandon branch', 1, [0x10, 0, 0, 0],
                [0x00, 0x00, 0x02, 0], Z[:], Z[:], True))
    # ALL FOUR BYTES EQUAL -- the DJNZ exhausts and FALLS THROUGH into the copy
    out.append(('all four equal', 1, [0, 0, 0, 0],
                [0x34, 0x63, 0x04, 0], [0x34, 0x63, 0x04, 0], Z[:], True))
    # THE FOURTH ADD ITERATION, and the wrap past eight digits
    out.append(('carry into the top byte', 1, [0x01, 0, 0, 0],
                list(BIG), [0x99, 0x99, 0x99, 0x12], Z[:], True))
    out.append(('overflow past 8 digits', 1, [0x01, 0, 0, 0],
                list(BIG), list(BIG), Z[:], True))
    # THE INACTIVE PLAYER: the pending is DISCARDED, the score untouched
    for a in (1, 2):
        out.append(('inactive A=%d' % a, a, [0x55, 0x55, 0, 0],
                    list(BIG), [0x11, 0x11, 0, 0], [0x22, 0x22, 0, 0], False))
    # A >= 3: rejected WITHOUT clearing the pending -- no shipped caller does this
    for a in (3, 4, 255):
        out.append(('rejected A=%d' % a, a, [0x77, 0x77, 0x77, 0x77],
                    list(BIG), Z[:], Z[:], True))
    # A = 0 -- arithmetically legal; the target is the HIGH SCORE ITSELF and the
    # guard is $FD7D.  Characterised, not asserted.
    out.append(('A=0, the high score as the target', 0, [0x10, 0, 0, 0],
                [0x00, 0x01, 0, 0], Z[:], Z[:], True))
    # every $8649 value, so a port that COMPUTES types 0..8 is caught on 9..15
    return out


def award_rows(h, m):
    rows = []
    for (name, a, amt, high, p1, p2, guard) in award_cases():
        for i in range(4):
            m[PEND + i] = amt[i]
            m[FIELD + i], m[FIELD + 4 + i], m[FIELD + 8 + i] = high[i], p1[i], p2[i]
        # the guard byte is the PLAYER ENTITY's +7, at $FD7D + 10*A
        g = (GUARD + 10 * a) & 0xFFFF
        m[g] = 0x80 if guard else 0x00
        before = fields(m)
        h.memobj.watch(0x4000, 0x5800)
        sp = arm(h, AWARD, a=a)
        run(h, sp)
        h.memobj.unwatch()
        # THE SCREEN WRITES ARE RECORDED AS ADDRESSES AND A CHECKSUM, NEVER AS
        # PIXELS.  $8042 sources its glyphs from $3C00 -- the SPECTRUM ROM
        # character set -- and this project ships no ROM transcription, so the
        # byte values must not enter a committed fixture.  The addresses and the
        # count are enough to gate the renderer's addressing, its row walk and
        # its leading-zero suppression; the glyph pixels are a separate question.
        addrs = sorted(set(a2 for _, a2, _ in h.memobj.log))
        ck = 0
        for _, a2, v in h.memobj.log:
            ck = ((ck * 33) ^ (a2 & 0xFFFF) ^ v) & 0xFFFFFFFF
        rows.append({'name': name, 'a': a, 'amt': amt, 'guard': guard,
                     'guard_at': g, 'before': before, 'after': fields(m),
                     'end_ptr': m[0x8607] | (m[0x8608] << 8),
                     'screen_addrs': addrs, 'screen_n': len(h.memobj.log),
                     'screen_ck': ck})
    return rows


def value_rows(h, m):
    """Every $8649 entry, awarded to P1 from zero -- so a port that computes the
       linear part (types 0..8 are $0010*(t+1)) is caught on types 9..15."""
    rows = []
    for t in range(16):
        lo, hi = m[VALUES + 2 * t], m[VALUES + 2 * t + 1]
        for i in range(4):
            m[FIELD + i] = 0x99                      # HIGH pinned: no copy
            m[FIELD + 4 + i] = 0
            m[FIELD + 8 + i] = 0
        m[PEND], m[PEND + 1], m[PEND + 2], m[PEND + 3] = lo, hi, 0, 0
        m[(GUARD + 10) & 0xFFFF] = 0x80
        sp = arm(h, AWARD, a=1)
        run(h, sp)
        rows.append({'type': t, 'value': [lo, hi],
                     'p1': [m[FIELD + 4 + i] for i in range(4)]})
    return rows


AWARD_TAIL = 0x87F9
P1E, P2E = 0xFD80, 0xFD8A


def tail_rows(h, m):
    """$87F9 -- the collect's own award tail, for every item type.

       $87FA reads $8828 (the OPERAND of $8827 LD A,n), doubles it, indexes
       $8649, stores the word at $FFED, then $880E BIT 0,(IX+$5A) picks the
       player -- 1 or 2, never 0 -- and calls $80FA.  $8822 LD A,($872C) / OR A
       / RET z ends the fruit pass here.

       Without these rows nothing in the suite ever reaches itemAward(), so the
       whole lookup-and-dispatch is ungated: four separate mutations of it
       survived the first battery.
    """
    rows = []
    for t in range(16):
        for who, bit in ((P1E, 0x00), (P2E, 0x01)):
            for i in range(4):
                m[FIELD + i] = 0x99                  # HIGH pinned: no copy
                m[FIELD + 4 + i] = 0
                m[FIELD + 8 + i] = 0
                m[PEND + i] = 0
            m[0x8828] = t
            m[0x872C] = 0                            # the fruit pass: RET z at $8826
            m[who + 0x5A] = bit
            m[(GUARD + 10) & 0xFFFF] = 0x80          # both players active
            m[(GUARD + 20) & 0xFFFF] = 0x80
            r = h.sim.registers
            r[8], r[9] = who >> 8, who & 0xFF        # IXh, IXl
            sp = arm(h, AWARD_TAIL)
            run(h, sp)
            rows.append({'type': t, 'who': who, 'bit': bit,
                         'p1': [m[FIELD + 4 + i] for i in range(4)],
                         'p2': [m[FIELD + 8 + i] for i in range(4)],
                         'pend': [m[PEND + i] for i in range(4)]})
    return rows


def clear_rows(h, m):
    """$8161 seeded FF FF FF FF -- at rest the field is already zero, so a clear
       of two bytes, of four, or of none at all are the same function."""
    rows = []
    for seed in ([0xFF] * 4, [0x12, 0x34, 0x56, 0x78], [0, 0, 0, 0]):
        for i in range(4):
            m[PEND + i] = seed[i]
        sp = arm(h, CLEAR)
        run(h, sp)
        r = h.regs
        rows.append({'seed': seed, 'after': [m[PEND + i] for i in range(4)],
                     'hl': (r[6] << 8) | r[7]})
    return rows


HUD_BLIT = 0x8052         # $804F's store, reached by $81C0 JP $804F
HUD_SUPP = 0x81BB         # the leading-zero suppressor: an OPCODE byte, $C8 or $00
HUD_TAB = 0x85FC          # three destination words, indexed by C>>1
CHARSET = 0x3C00


def hud_trace_rows(h, m):
    """$816B's writes IN ORDER, as (destination, character code, row index).

    *** NO ROM BYTE. ***  The code and the row come from the SOURCE address the
    routine read -- $8042/$8044 build $3C00 + 8*code -- so a gate computes the
    expected pixel from the PORT'S OWN font and compares it at the machine's
    destination.  award_rows records `sorted(set(addresses))` and a ROM-derived
    checksum, which is right about the ROM bytes and threw away the order, the
    repeats and the digit as well; the suite's HUD row consequently stubs the
    blitter with a body of `void digit`.

    Recorded per case: the ordered glyph writes, $81BB before and after, the
    twelve RLD writes to the record's own bytes (the THIRD restores, so an
    end-state diff sees none of them), and the cursor at $8605.
    """
    CASES = [
        ('zero',      0x04, [0x00, 0x00, 0x00, 0x00]),
        ('12',        0x04, [0x00, 0x00, 0x00, 0x12]),
        ('046334',    0x04, [0x34, 0x63, 0x04, 0x00]),
        ('01',        0x04, [0x00, 0x00, 0x00, 0x01]),
        ('10',        0x04, [0x00, 0x00, 0x00, 0x10]),
        ('99999999',  0x04, [0x99, 0x99, 0x99, 0x99]),
        ('12345678',  0x04, [0x78, 0x56, 0x34, 0x12]),
        ('high99',    0x00, [0x99, 0x99, 0x99, 0x99]),
        ('high046334', 0x00, [0x34, 0x63, 0x04, 0x00]),
        ('p2_99',     0x08, [0x99, 0x99, 0x99, 0x99]),
        ('p2_046334', 0x08, [0x34, 0x63, 0x04, 0x00]),
    ]
    rows = []
    for (name, c, rec) in CASES:
        h2, m2 = new()
        base = FIELD + c
        for i in range(4):
            m2[base + i] = rec[i]
        #  the pending field is what $8161 clears; seed it NON-zero so those four
        #  writes are visible (TRAPS #44)
        for i in range(4):
            m2[PEND + i] = 0x5A
        m2[0x8607] = (base + 4) & 0xFF
        m2[0x8608] = ((base + 4) >> 8) & 0xFF
        supp_before = m2[HUD_SUPP]
        r = h2.sim.registers
        sp = arm(h2, HUD)
        r[3] = c                       # C -- the field selector, 4*player
        glyphs, recwrites, supp = [], [], []
        n = 0
        while n < 2 * 10 ** 6:
            p = r[PC]
            if p in h2.SENTINELS:
                break
            if p == HUD_BLIT:
                dest = r[7] | (r[6] << 8)          # HL
                src = r[5] | (r[4] << 8)           # DE
                off = (src - CHARSET) & 0xFFFF
                glyphs.append(['%04X' % dest, off // 8, off % 8])
            elif p in (0x818A, 0x819E, 0x81B2):    # the three RLDs
                recwrites.append('%04X' % ((r[7] | (r[6] << 8)) & 0xFFFF))
            elif p == 0x81BD:                      # the disarm store
                supp.append('%04X' % p)
            h2.step(1, interrupts=False)
            n += 1
        else:
            raise SystemExit('$816B never returned for %r' % name)
        entry = m2[HUD_TAB + (c >> 1)] | (m2[HUD_TAB + (c >> 1) + 1] << 8)
        rows.append({
            'name': name, 'c': c, 'record': list(rec),
            'entry': '%04X' % entry,
            'glyphs': glyphs, 'n_glyphs': len(glyphs),
            'digits_drawn': len(glyphs) // 8,
            'supp_before': supp_before, 'supp_after': m2[HUD_SUPP],
            'disarm_stores': len(supp),
            'rld_writes': recwrites,
            'record_after': [m2[base + i] for i in range(4)],
            'record_restored': [m2[base + i] for i in range(4)] == list(rec),
            'pend_after': [m2[PEND + i] for i in range(4)],
            'cursor': m2[0x8605] | (m2[0x8606] << 8),
        })
    print('$816B ORDERED TRACE -- destination, code, row; no ROM byte')
    for r0 in rows:
        print('    %-11s C=$%02X rec %s -> entry $%s  %2d digits, %2d writes, '
              '$81BB $%02X->$%02X (%d disarms), record %s, cursor $%04X'
              % (r0['name'], r0['c'],
                 ' '.join('%02X' % b for b in r0['record']), r0['entry'],
                 r0['digits_drawn'], r0['n_glyphs'],
                 r0['supp_before'], r0['supp_after'], r0['disarm_stores'],
                 'RESTORED' if r0['record_restored'] else '*** MANGLED ***',
                 r0['cursor']))
    #  the claims, asserted so the phase cannot ship an inert measurement
    assert all(r0['record_restored'] for r0 in rows), 'an RLD left a record mangled'
    assert all(r0['n_glyphs'] == 8 * r0['digits_drawn'] for r0 in rows)
    assert all(len(r0['rld_writes']) == 12 for r0 in rows), 'not twelve RLD writes'
    drew = [r0 for r0 in rows if r0['digits_drawn'] > 0]
    assert drew and all(r0['supp_after'] == 0x00 for r0 in drew), \
        'a call that drew did not leave $81BB disarmed'
    zero = [r0 for r0 in rows if r0['digits_drawn'] == 0]
    assert zero and all(r0['supp_after'] == 0xC8 for r0 in zero), \
        'the all-zero record did not leave $81BB armed'
    assert all(r0['disarm_stores'] == r0['digits_drawn'] for r0 in rows), \
        '$81BD did not fire once per DRAWN digit'
    assert all(r0['pend_after'] == [0, 0, 0, 0] for r0 in rows), \
        '$8161 did not clear the pending field'
    print('    -> record RESTORED in every case; $81BB left $00 by any call that drew '
          'and $C8 by the all-zero one; $81BD fires ONCE PER DRAWN DIGIT, not once')
    return rows


def capture():
    h, m = new()
    aw = award_rows(h, m)
    va = value_rows(h, m)
    cl = clear_rows(h, m)
    tl = tail_rows(h, m)
    fx = {
        'hud_trace': hud_trace_rows(h, m),'note': __doc__.strip(), 'award_at': AWARD, 'clear_at': CLEAR,
          'field_at': FIELD, 'pend_at': PEND, 'guard_at': GUARD,
          'values_at': VALUES,
          'values': [m[VALUES + i] for i in range(32)],
          'award': aw, 'value_sweep': va, 'clear': cl, 'tail': tl,
          'tail_at': AWARD_TAIL}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d award rows, %d value rows, %d clear rows'
          % (FIXTURE, len(aw), len(va), len(cl)))
    moved = sum(1 for r in aw if r['after']['high'] != r['before']['high'])
    print('  rows where the HIGH field moved: %d' % moved)
    print('  %d award-tail rows ($87F9, every type through both players)' % len(tl))


def bcd(v):
    return ''.join('%02X' % b for b in reversed(v))


def verify():
    fx = json.load(open(FIXTURE))
    print('%-34s %-9s %-9s %-9s %s' % ('case', 'HIGH', 'P1', 'P2', 'pending'))
    for r in fx['award']:
        print('  %-32s %s %s %s  %s' % (r['name'][:32], bcd(r['after']['high']),
              bcd(r['after']['p1']), bcd(r['after']['p2']), bcd(r['after']['pend'])))
    print()
    print('the $8649 sweep, each awarded to P1 from zero:')
    for r in fx['value_sweep']:
        print('   type %2d  value $%02X%02X -> P1 %s' % (r['type'], r['value'][1],
              r['value'][0], bcd(r['p1'])))
    print()
    for r in fx['clear']:
        print('   $8161 seed %s -> %s, HL=$%04X' % (bcd(r['seed']), bcd(r['after']), r['hl']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
