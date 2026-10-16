"""M7.7-I6 -- the POWER-UP DISPATCH $8839 and all sixteen handlers.

THE ORACLE LETS THE MACHINE ENUMERATE THE EFFECTS.  Every handler is called
with the whole world seeded to distinctive non-target values and EVERY WRITE IN
$4000-$FFFF is logged, so the fixture records what each handler actually touches
rather than what I believed it touched when I read it.  That is why this
increment is solo work: the measurement is cheap and complete, so there is no
belief of mine left for an independent reader to attack.

The jump table is READ OUT OF THE IMAGE at $8839, never hard-coded, so a wrong
entry is a diff rather than a shared assumption.

TWO FALL-THROUGHS and TWO SHARED TAILS are where a transliteration silently
diverges:
    $88EC (type 2)  CALLs $88F4 and then FALLS THROUGH into $88EF -- so it does
                    BOTH of what types 1 and 0 do.
    $88DC (type 9)  falls through into $88E0.
    $88E0  THE DIAMOND PIN: LD HL,9 / LD ($8B9F),HL writes 9 AND ZEROES $8BA0,
           which is the INC A OPCODE of the fruit-type generator, and
           LD A,$FF / LD ($8BA2),A turns its mask into $FF.  The generator is
           thereby pinned to a constant 9 -- every later corpse drops a DIAMOND.
           All thirteen in-game dumps hold $8BA0 = $3C and $8BA2 = $07, so the
           PATCHED state has never been captured; it only exists after a call.
    $8888  the shoot-gate refill: $A891 := $FF then LDIR 7 over $A892-$A898,
           and $8DBD := 0.

TWO HANDLERS WRITE BOTH PLAYERS -- $8859 by reloading IX, $889C by absolute
address ($FDDA and $FDE4).  With only P1 ever collecting, "write (IX+$61)" and
"write P1 always" agree on every row, so every handler is also called with
IX = $FD8A.

TYPE 6 DOES NOT RETURN: $88C0 JP $A110.  It is bracketed on PC == $A110 with SP
still pinned, so the capture stops at the jump rather than running $A110's body.

WHAT THIS ORACLE REFUSES TO ASSUME:
  * A HANDLER WRITING A VALUE ALREADY PRESENT.  Type 1 writes (IX+$5E) := $10
    over a struct that may already hold 16; type 14 writes (IX+$5B) := 3 over a
    previous 3.  BOTH players' full structs and both entity +7 bytes are seeded
    to $FF, so every write is a visible change and every non-write leaves $FF.
  * TYPES 0 AND 2 both end at (IX+$5F) := 3, so watching one byte cannot tell
    them apart -- the whole struct is compared, and type 2 must move $5E as well.
  * TYPES 4 AND 5 SHARE HANDLER $88FD and are genuinely identical here.  No gate
    can separate them at the handler level; they differ only in $8649 and $861D,
    which I2 and I4 already cover.  Recorded as a fact, not papered over.
  * TYPE 15 IS A BARE RET, so "correct" and "not implemented" are the same at
    collect.  Recorded as such; the discriminating read is $BD56, downstream.

Usage:  python tools/puhandlers.py capture
        python tools/puhandlers.py verify
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

TABLE = 0x8839
DISPATCH = 0x8822         # LD A,($872C) / OR A / RET z, then the jump
P1, P2 = 0xFD80, 0xFD8A
TYPE_OP = 0x8828
FIXTURE = 'build/puhandlers_fixture.json'
BRANCH_BYTE = 0x8DC4
SP0 = [0]

# handlers that leave by a JP rather than a RET: (type, the PC to stop on)
NORET = {6: 0xA110}
# Type 12 is the LEVEL-SKIP and it ARMS THE TREASURE ROOM.  The boundary MOVED
# FORWARD at M7.7-I11, from $8915 to $894B, and the move makes this gate stronger
# rather than weaker: the row now covers $A36C's forty bytes (twenty at $5B00 and
# twenty at $FDEE, the two bolt slots, all via the byte-fill $AA4A), $8E0A (which
# writes NOTHING -- measured, so its absence is an assertion), both tallies, BOTH
# LATCHES ($FED1 and $9049), the $8F3A capture of the timer's high byte, and both
# self-modified operands $896D and $899F.
# It stops at $8949 -- the PUSH IX immediately before CALL $8C14, chosen rather
# than $894B because the PUSH itself moves SP and this tool reads a moved SP at a
# jump stop as a consumed RET.  $8C14 is excluded because it RES 7s
# seven entity slots and twelve bubble slots and then repaints the whole
# playfield from the shadow through $8216 -- 7,076 display writes, measured.
# That is render work, it belongs to (h), and I11's own gate drives the FILL
# LOOP $8950 directly instead of pretending to reproduce a repaint.
SKIP_BODY = {12: 0x8949}

# every byte the handlers are known or suspected to touch, seeded distinctively
SEED = {}
for a in range(0xFECC, 0xFED3):
    SEED[a] = 0x5A
SEED[0x9049] = 0x5A
# I11: everything handler 12's tail writes, seeded to a value it does NOT write,
# so "written" and "already held the answer" separate (TRAPS #44)
SEED[0xFDE2] = 0x5A
SEED[0xFDEC] = 0x5A
SEED[0x896D] = 0x5A          # the fill's TYPE operand ($896C OR n)
SEED[0x899F] = 0x5A          # the probe OFFSET operand, low
SEED[0x89A0] = 0x5A          # ...and high
SEED[0x8F3A] = 0x5A          # the drain's CAPTURED high byte ($8F39 SUB n)
for a in range(0x5B00, 0x5B20):
    SEED[a] = 0x5A           # $A36C's twenty bytes, PLUS TWELVE GUARD BYTES: a
for a in range(0xFDEE, 0xFE0E):
    SEED[a] = 0x5A           # clear of 32 instead of 20 is invisible without them
for a in range(0xA891, 0xA899):
    SEED[a] = 0x5A
SEED[0x8B9F] = 0x11
SEED[0x8BA0] = 0x3C          # the INC A opcode the diamond pin NOPs out
SEED[0x8BA2] = 0x07          # the mask the diamond pin widens to $FF
SEED[0x8309] = 0x46
SEED[0x830A] = 0x66
SEED[0x8DBD] = 0x5A
# $8DBE is the SOURCE handler 12 captures into $8F3A, and $8F3A is seeded $5A
# too -- so with both at $5A the capture writes the value that was already
# there and "captured" and "never written" are the same observation (TRAPS
# #44).  Seeded APART at M7.7-I11.
SEED[0x8DBE] = 0x3C
SEED[0xFDE2] = 0x5A
SEED[0xFDEC] = 0x5A


def new(state='round1_48'):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP0[0] = h.sim.registers[12]
    return h, m


def arm(h, addr, ix):
    r = h.sim.registers
    sp = SP0[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[8], r[9] = ix >> 8, ix & 0xFF          # IXh, IXl
    r[PC] = addr
    return sp


def seed(m, fill):
    """Both players' whole structs and both +7 bytes to `fill`.

       EVERY HANDLER IS CAPTURED TWICE, at $FF and at $00, because neither seed
       alone makes every write visible: a SET n,(HL) over $FF changes nothing,
       and type 12's (IX+$62) := 0 over $00 changes nothing.  Between the two,
       every write moves at least one byte -- the same device as the item
       blitter's black-and-white destination in I2."""
    for base in (P1, P2):
        for off in range(0x5A, 0x64):
            m[(base + off) & 0xFFFF] = fill
        m[base + 7] = fill
    for a, v in SEED.items():
        m[a] = v


def call_handler(h, m, addr, ix, stop=None, fill=0xFF):
    seed(m, fill)
    m[TYPE_OP] = 0xEE
    # THE LFSR STATE BEFORE THE CALL.  Type 6 draws from $FE85, and the engine's
    # generator starts from its own seed, so without this the two disagree on
    # $FE86/$FE87 for reasons that have nothing to do with the handler.
    prng = [m[0xFE86], m[0xFE87]]
    h.memobj.watch(0x4000, 0x10000)
    sp = arm(h, addr, ix)
    stops = tuple(h.SENTINELS) + ((stop,) if stop else ())
    h.run_until(stops, limit=10 ** 6, stride=1, interrupts=False)
    h.memobj.unwatch()
    r = h.regs
    reached = r[PC]
    if stop and reached == stop:
        if r[12] != sp:
            raise SystemExit('$%04X reached with SP moved -- a RET was consumed' % stop)
        ended = 'jump'
    elif reached in h.SENTINELS:
        if h.SENTINELS.index(reached) != 0:
            raise SystemExit('returned on the wrong sentinel')
        ended = 'ret'
    else:
        raise SystemExit('bad bracket -- PC $%04X' % reached)
    # THE STACK IS NOT AN EFFECT.  SP sits just under $96D7 here, so a handler's
    # own PUSHes and the CALL/RET traffic land in $96Cx and would otherwise be
    # recorded as if they were power-up behaviour.
    lo, hi = (SP0[0] - 64) & 0xFFFF, SP0[0]
    writes = sorted(set((a, v) for _, a, v in h.memobj.log
                        if not (lo <= a <= hi)))
    return {'ended': ended, 'stop_pc': reached, 'fill': fill, 'prng': prng,
            'writes': [[a, v] for a, v in writes]}


def capture():
    h, m = new()
    table = [m[TABLE + 2 * t] | (m[TABLE + 2 * t + 1] << 8) for t in range(16)]
    rows = []
    for t in range(16):
        for ix in (P1, P2):
            for fill in (0xFF, 0x00):
                stop = NORET.get(t) or SKIP_BODY.get(t)
                r = call_handler(h, m, table[t], ix, stop, fill)
                r.update({'type': t, 'ix': ix, 'handler': table[t]})
                rows.append(r)
    # the $872C gate: with the flag at 0 the fruit pass RETs at $8826 and no
    # handler runs at all.  Seeded to $FF, the struct must come back $FF.
    gate = []
    # BOTH players: the recorder (IX+$61) is the only IX-relative write in the
    # dispatch itself, so with P1 alone "write (IX+$61)" and "always write
    # $FDE1" are the same function.
    for flag in (0, 1):
      for ix in (P1, P2):
        for t in (0, 1, 14):
            seed(m, 0xFF)
            m[TYPE_OP] = t
            m[0x872C] = flag
            h.memobj.watch(0x4000, 0x10000)
            sp = arm(h, DISPATCH, ix)
            stops = tuple(h.SENTINELS)
            h.run_until(stops, limit=10 ** 6, stride=1, interrupts=False)
            h.memobj.unwatch()
            lo, hi = (SP0[0] - 64) & 0xFFFF, SP0[0]
            w = sorted(set((a, v) for _, a, v in h.memobj.log
                           if not (lo <= a <= hi)))
            gate.append({'flag': flag, 'type': t, 'ix': ix,
                         'writes': [[a, v] for a, v in w],
                         'p1': [m[(P1 + o) & 0xFFFF] for o in range(0x5A, 0x64)],
                         'p2': [m[(P2 + o) & 0xFFFF] for o in range(0x5A, 0x64)]})
    fx = {'note': __doc__.strip(), 'table_at': TABLE, 'table': table,
          'dispatch_at': DISPATCH, 'type_op_at': TYPE_OP,
          'p1': P1, 'p2': P2, 'seed': {str(k): v for k, v in SEED.items()},
          'noret': {str(k): v for k, v in NORET.items()},
          'skip_body': {str(k): v for k, v in SKIP_BODY.items()},
          'rows': rows, 'gate': gate}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d handler calls, %d gate rows' % (FIXTURE, len(rows), len(gate)))
    print('  jump table:', ' '.join('$%04X' % a for a in table))
    print('  writes per type (IX = P1):')
    for t in range(16):
        r = [x for x in rows if x['type'] == t and x['ix'] == P1
             and x['fill'] == 0x00][0]
        print('    %2d -> $%04X  %-5s %2d writes  %s' % (t, r['handler'], r['ended'],
              len(r['writes']),
              ' '.join('$%04X=$%02X' % (a, v) for a, v in r['writes'][:6])))


def verify():
    fx = json.load(open(FIXTURE))
    print('THE $8839 JUMP TABLE, read out of the image:')
    for t in range(16):
        r = [x for x in fx['rows'] if x['type'] == t and x['ix'] == fx['p1']
             and x['fill'] == 0][0]
        q = [x for x in fx['rows'] if x['type'] == t and x['ix'] == fx['p2']
             and x['fill'] == 0][0]
        same = r['writes'] == q['writes']
        print('  type %2d -> $%04X  %2d writes  %s'
              % (t, fx['table'][t], len(r['writes']),
                 'IX-independent' if same else 'DIFFERS between P1 and P2'))
    print()
    print('THE $872C GATE -- a fruit (flag 0) must run NO handler:')
    for g in fx['gate']:
        print('   flag=%d type=%2d  %2d writes  struct %s'
              % (g['flag'], g['type'], len(g['writes']),
                 'untouched ($FF)' if all(v == 0xFF for v in g['p1']) else 'MOVED'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
