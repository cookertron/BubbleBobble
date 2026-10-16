"""B10 -- THE ENDGAME: there is no ending, and the last dark bytes in the chain.

$A09A is the LAST UNREAD CODE IN THE MAIN-LOOP CHAIN, and the port has carried
it as a stub labelled "lightning" since B0.  It is not lightning.  It is a
two-armed FULL-SCREEN EFFECT MANAGER behind a CP-form once-per-frame edge
detector whose compare operand $A09E is ITS OWN SELF-MODIFIED BYTE.

NEITHER ARM IS REACHABLE FROM ANY SHIPPED STATE, and both are dead on the boss
round, so every number here comes from a BUILT world.

*** FOUR THINGS THE PLAN GOT WRONG, ALL CHECKED AGAINST THE DISASSEMBLY. ***
 1. $A0E0 masks 704 attribute bytes, NOT 384.  $A0E7 CALL $A0ED, $A0EA CALL
    $A0ED -- and $A0ED IS THE NEXT INSTRUCTION, so the second CALL returns into
    the loop and the routine falls through for a third pass.  B = $C0 then 0
    then 0, and TRAPS #45's DJNZ-with-B=0 is 256: 192 + 256 + 256 = 704, and
    $5840 + 704 = $5B00 EXACTLY.  The CALL-then-fall-through shape again.
 2. THE REASON FOR SAFETY WAS BACKWARDS.  `AND $F8 / OR E` CLEARS AND REWRITES
    bits 0-2; it does not leave them untouched.  What makes it safe is that it
    writes the DISPLAY attribute file $5840..$5AFF and never the colour shadow
    $F8xx -- and $8C28 copies 704 bytes STRAIGHT BACK from $F840 to $5840.  The
    same 704 both ways: the flash is transient by construction.
 3. $A110 IS NOT PART OF $A09A.  The only 16-bit reference to it in 64K is
    $88C1 -- item effect type 6, which build/puhandlers_fixture.json already
    records as noret {"6": 41232} = $A110.  The plan's negative ("entered from
    the flood arm only") names the wrong owner.  $A127, by contrast, has ZERO
    16-bit references and is reached only by $A0A7's relative JR.
 4. $A0C5 LD DE,$0042 / JR $A0E0 -- at A >= $FD the thunder's last three steps
    paint all 704 cells FLAT $42 (D = $00, so `AND D` is zero).  Unmentioned.

AND "54 EDGES, ONCE PER VIDEO FRAME" IS NOT AN INVARIANT: bossspawn gives 11
edges against 49 frames.  The census is a row here, not a claim.

Usage:  python tools/endgame.py      (capture -> build/endgame_fixture.json)
        python tools/endgame.py NAME [NAME...]   (one phase, no write)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/endgame_fixture.json'
BRANCH_BYTE = 0x8DC4
ROUND = 0x8609

EDGE, EDGE_OP = 0xA09A, 0xA09E          # the CP-form detector and ITS OPERAND
PAST_EDGE = 0xA0A3                      # past $A0A2 RET z
FLOOD_ARM, THUNDER_ARM = 0xFECE, 0xFECF
FLOOD, THUNDER = 0xA127, 0xA0AE
PAINT, PAINT_BODY = 0xA0E0, 0xA0ED
PAYLOAD, TYPE6 = 0xA0F5, 0xA110
FLAT42, EVERY32 = 0xA0C5, 0xA0CA
WRAP_TAIL, RESTORE = 0x8C28, 0x8C28
DISARM, WINDOW = 0xA154, 0xA146
POOL, POOL_N, POOL_STRIDE = 0xFED8, 12, 10
ATTR_LO, ATTR_HI = 0x5840, 0x5B00       # 704 bytes
SHADOW_LO, SHADOW_HI = 0xF800, 0xFB00   # the COLOUR shadow, which must not move

ADVANCE, WALK, WALK_END = 0x97F8, 0x984B, 0x9858
LOOKAHEAD, R81_TIMER, BOSS_Y = 0xFEC7, 0x745C, 0xA839
HP = 0x9F62
P1_SCORE = 0xFFE5                       # I4: HIGH $FFE1, P1 $FFE5, P2 $FFE9
ISR = 0x8D72

POISON = 0x5A


def new(state, contended=True):
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


def sentinels(h):
    return tuple(h.SENTINELS)


STATES = ('boss', 'bosshit', 'bosskilled', 'bossspawn', 'r20_48', 'r50_48',
          'round1_48', 'play1p48')


# ------------------------------------------------------------------ phase A
def phase_edge():
    """THE CP-FORM EDGE DETECTOR, AND THE TWO CLAIMS ABOUT IT THAT DO NOT HOLD.

       $A09D `CP $2A` compares against $A09E, WHICH IS ITS OWN OPERAND, and
       $A09F writes the play timer straight back into it.  Every static reading
       gives the tape's $2A -- and so does play1p48, which is exactly why a
       round-1 world cannot separate "the constant $2A" from "live state".
       Census it across eight states and name the ones that differ.

       AND THE RATE IS NOT ONE PER FRAME EVERYWHERE.  Count $A09A entries,
       $A0A3 entries (past the RET z) and ISR entries per state."""
    tape = open('build/image_tape.bin', 'rb').read()
    out = {'tape_A09E': tape[EDGE_OP], 'states': {}}
    for st in STATES:
        h, m = new(st)
        live = m[EDGE_OP]
        n = {'A09A': 0, 'A0A3': 0, 'ISR': 0}
        frames = 0
        while frames < 60:
            reason, _ = h.run_until((ISR, EDGE, PAST_EDGE), limit=400000,
                                    stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                n['ISR'] += 1
                frames += 1
            elif p == EDGE:
                n['A09A'] += 1
            else:
                n['A0A3'] += 1
            h.step(1)
        out['states'][st] = {'round': m[ROUND], 'A09E_live': live,
                             'A09E_equals_tape': live == tape[EDGE_OP],
                             'counts': n,
                             'edges_per_frame': round(n['A0A3'] / n['ISR'], 3)
                             if n['ISR'] else None}
    out['differs_from_tape'] = sorted(k for k, v in out['states'].items()
                                      if not v['A09E_equals_tape'])
    out['one_per_frame'] = sorted(k for k, v in out['states'].items()
                                  if v['edges_per_frame'] == 1.0)
    out['not_one_per_frame'] = sorted(k for k, v in out['states'].items()
                                      if v['edges_per_frame'] != 1.0)
    return out


# ------------------------------------------------------------------ phase B
def paint_probe(h, m, entry, seed_attr=0x5A, seed_shadow=0x00):
    """Call one painter entry with the DISPLAY attributes poisoned and the
       COLOUR SHADOW poisoned DIFFERENTLY, and report the PC-attributed writes.
       Seeding both with the same value would make the safety claim -- "it
       never touches $F8xx" -- unfalsifiable (TRAPS #44)."""
    for a in range(0x5800, 0x5B00):
        m[a] = seed_attr
    for a in range(SHADOW_LO, SHADOW_HI):
        m[a] = seed_shadow
    h.memobj.watch(0x4000, 0x10000)
    arm(h, entry)
    h.run_until(sentinels(h), limit=400000, stride=1, interrupts=False)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    attrs = [(p, a, v) for (p, a, v) in log if 0x5800 <= a < 0x5B00]
    shadow = [(p, a, v) for (p, a, v) in log if SHADOW_LO <= a < SHADOW_HI]
    lo = min((a for (_, a, _) in attrs), default=None)
    hi = max((a for (_, a, _) in attrs), default=None)
    vals = sorted(set(v for (_, _, v) in attrs))
    return {'writes': len(log), 'attr_writes': len(attrs),
            'shadow_writes': len(shadow),
            'attr_lo': '%04X' % lo if lo is not None else None,
            'attr_hi': '%04X' % hi if hi is not None else None,
            'distinct_attr_values': vals[:8], 'n_values': len(vals),
            'writer_pcs': sorted(set('%04X' % p for (p, _, _) in attrs))}


def phase_paint():
    """*** $A0E0 MASKS 704 BYTES, NOT 384, AND $5840 + 704 = $5B00 EXACTLY. ***
       Three passes, not two: $A0EA's CALL returns into $A0ED, which is the
       NEXT INSTRUCTION, so the routine falls through for a third.  B is $C0,
       then 0, then 0, and DJNZ with B = 0 runs 256 times (TRAPS #45).

       And the safety claim, driven rather than argued: the colour shadow
       $F800..$FAFF is poisoned to a DIFFERENT value and must not be written."""
    h, m = new('r50_48')
    r = h.sim.registers
    out = {}
    for name, (dd, ee) in (('ink_0', (0xF8, 0x00)), ('ink_3', (0xF8, 0x03)),
                           ('flat_42', (0x00, 0x42)),
                           ('flood_row', (0x00, 0x2F))):
        h, m = new('r50_48')
        r = h.sim.registers
        r[D], r[E] = dd, ee
        out[name] = paint_probe(h, m, PAINT)
        out[name]['D'], out[name]['E'] = dd, ee
    # ...and the ROW the flood arm paints is only 32 cells, because it enters
    # at $A0ED with B = $20 -- the SAME body, a different entry (TRAPS #52's
    # dual: one routine, two doors).
    h, m = new('r50_48')
    r = h.sim.registers
    r[D], r[E] = 0x00, 0x2F
    r[B] = 0x20
    r[H], r[L] = 0x5A, 0xE0
    out['flood_row_direct'] = paint_probe(h, m, PAINT_BODY)
    return out


# ------------------------------------------------------------------ phase C
def phase_thunder():
    """THE THUNDER ARM, BUILT.  ($FECF) is armed by I6's item type 8 ($88D5)
       and is 0 in every shipped state, so this whole arm is unreachable
       without the build.  Step it and record every threshold."""
    out = {'steps': []}
    h, m = new('r50_48')
    m[FLOOD_ARM] = 0                                   # the other arm OFF
    m[THUNDER_ARM] = 1
    rows = []
    for step in range(300):
        before = m[THUNDER_ARM]
        for a in range(0x5800, 0x5B00):
            m[a] = 0x5A
        h.memobj.watch(0x4000, 0x10000)
        arm(h, THUNDER)
        # $A0AE is `LD B,A` -- the counter arrives in A from $A0A9's
        # `LD A,($FECF)`, so entering mid-routine without setting it measures
        # whatever the last instruction left behind (TRAPS #42's cousin).
        h.sim.registers[A] = before
        h.run_until(sentinels(h) + (WRAP_TAIL,), limit=400000, stride=1,
                    interrupts=False)
        wrapped = h.regs[PC] == WRAP_TAIL
        log = list(h.memobj.log)
        h.memobj.unwatch()
        attrs = [(p, a, v) for (p, a, v) in log if 0x5800 <= a < 0x5B00]
        pool = [(p, a, v) for (p, a, v) in log if POOL <= a < POOL + 120]
        vals = sorted(set(v for (_, _, v) in attrs))
        rows.append({'step': step, 'before': before, 'after': m[THUNDER_ARM],
                     'attr_writes': len(attrs), 'pool_writes': len(pool),
                     'values': vals[:6], 'wrapped': wrapped})
        if wrapped:
            break
    painted = [r for r in rows if r['attr_writes']]
    out['n_steps'] = len(rows)
    out['painting_steps'] = [r['step'] for r in painted]
    out['first_painting'] = painted[0] if painted else None
    out['payload_steps'] = [r['step'] for r in rows if r['pool_writes']]
    out['flat42_steps'] = [r['step'] for r in rows
                           if r['values'] == [0x42]]
    out['wrap_step'] = next((r['step'] for r in rows if r['wrapped']), None)
    out['wrap_tail'] = '%04X' % WRAP_TAIL
    out['sample'] = [r for r in rows if r['attr_writes'] or r['pool_writes']
                     or r['wrapped']][:24]
    return out


# ------------------------------------------------------------------ phase D
def phase_payload():
    """$A0F5 -- the payload BOTH arms reach.  DI, twelve slots at $FED8 stride
       10, (IX+3) := 10 and SET 3 / SET 1 on (IX+7).  The slots are SEEDED
       POISON, because $00 would make `SET` and `:= 10` invisible."""
    h, m = new('r50_48')
    # THE POISON HAS TO HAVE BITS 1 AND 3 CLEAR.  My first run seeded $5A --
    # 0101 1010, which ALREADY has both -- so `SET 3` and `SET 1` wrote the
    # value back unchanged and the flags column read $5A on every slot,
    # exactly as if nothing had happened.  TRAPS #44 committed by the seed
    # itself.  $A5 is 1010 0101: both bits clear, and $A5 | $0A = $AF.
    FLAGS_POISON = 0xA5
    for k in range(POOL_N + 2):                      # two PAST the twelve
        b = POOL + POOL_STRIDE * k
        m[b + 3] = POISON
        m[b + 7] = FLAGS_POISON
    h.memobj.watch(0x4000, 0x10000)
    arm(h, PAYLOAD)
    h.run_until(sentinels(h), limit=400000, stride=1, interrupts=False)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    slots = []
    for k in range(POOL_N + 2):
        b = POOL + POOL_STRIDE * k
        slots.append([k, '%04X' % b, m[b + 3], m[b + 7]])
    return {'writes': len(log),
            'writer_pcs': sorted(set('%04X' % p for (p, _, _) in log)),
            'addrs': sorted(set('%04X' % a for (_, a, _) in log)),
            'slots': slots,
            'poison': [POISON, FLAGS_POISON],
            'expect_flags': FLAGS_POISON | 0x0A,
            'touched': sum(1 for s in slots if s[2] != POISON),
            'flags_set': sum(1 for s in slots if s[3] == (FLAGS_POISON | 0x0A)),
            'untouched_past_twelve': [s for s in slots
                                      if s[0] >= POOL_N]}


# ------------------------------------------------------------------ phase E
def phase_flood():
    """THE FLOOD ARM, BUILT, on a CROSS round -- $8A16 forces the round-80
       power-up type to 13, so no water cross exists on the boss round.
       ($FECE) is armed by I6's item type 7 ($8843).  Three exits: the ADD's
       CARRY disarms at $A154, A >= $AF takes the SUB-2 window at $A146 whose
       $C8..$C9 pair JPs to the payload, and everything else paints ONE 32-cell
       row at $5AE0 - (A & $F8) * 4."""
    out = {'rows': []}
    h, m = new('redcross')
    rnd = m[ROUND]
    m[THUNDER_ARM] = 0
    m[FLOOD_ARM] = 1
    seen = []
    for step in range(200):
        before = m[FLOOD_ARM]
        for a in range(0x5800, 0x5B00):
            m[a] = 0x5A
        for k in range(POOL_N):
            b = POOL + POOL_STRIDE * k
            m[b + 3] = POISON; m[b + 7] = POISON
        h.memobj.watch(0x4000, 0x10000)
        arm(h, FLOOD)
        r = h.sim.registers
        r[A] = before
        h.run_until(sentinels(h), limit=400000, stride=1, interrupts=False)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        attrs = [(p, a, v) for (p, a, v) in log if 0x5800 <= a < 0x5B00]
        pool = [(p, a, v) for (p, a, v) in log if POOL <= a < POOL + 120]
        lo = min((a for (_, a, _) in attrs), default=None)
        seen.append({'step': step, 'A_in': before, 'after': m[FLOOD_ARM],
                     'attr_writes': len(attrs), 'pool_writes': len(pool),
                     'row_base': '%04X' % lo if lo is not None else None,
                     'values': sorted(set(v for (_, _, v) in attrs))[:4]})
        if m[FLOOD_ARM] == 0:
            break
    out['round'] = rnd
    out['n_steps'] = len(seen)
    out['disarm_step'] = next((s['step'] for s in seen if s['after'] == 0),
                              None)
    out['payload_steps'] = [s['step'] for s in seen if s['pool_writes']]
    out['row_steps'] = [s['step'] for s in seen if s['attr_writes'] == 32]
    out['distinct_rows'] = sorted(set(s['row_base'] for s in seen
                                      if s['attr_writes'] == 32))
    out['rows'] = seen[:40]
    out['tail'] = seen[-8:]
    return out


# ------------------------------------------------------------------ phase F
def phase_restore():
    """*** WHY THE FLASH CANNOT CORRUPT ANYTHING: $8C28 PUTS IT BACK. ***
       `CALL $8216 / LD BC,$02C0 / LD HL,$F840 / LD DE,$5840` -- 704 bytes,
       from the COLOUR SHADOW to the DISPLAY attribute file.  The same 704
       $A0E0 trashes.  That, and not "bits 0-2 are untouched", is the reason
       the effect is safe: `AND $F8 / OR E` clears and REWRITES bits 0-2."""
    h, m = new('r50_48')
    for a in range(0x5800, 0x5B00):
        m[a] = 0x5A                                   # a trashed display
    for a in range(0xF800, 0xFB00):
        m[a] = 0x27                                   # a DIFFERENT shadow
    h.memobj.watch(0x4000, 0x10000)
    arm(h, RESTORE)
    h.run_until(sentinels(h), limit=900000, stride=1, interrupts=False)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    attrs = [(p, a, v) for (p, a, v) in log if 0x5800 <= a < 0x5B00]
    shadow = [(p, a, v) for (p, a, v) in log if 0xF800 <= a < 0xFB00]
    lo = min((a for (_, a, _) in attrs), default=None)
    hi = max((a for (_, a, _) in attrs), default=None)
    below = sum(1 for a in range(0x5800, 0x5840) if m[a] == 0x5A)
    final = {}
    for a in range(0x5840, 0x5B00):
        final[m[a]] = final.get(m[a], 0) + 1
    # $8C28 does NOT copy the shadow: $8C34 `BIT 5,(HL)` picks ($8309) or
    # ($830A) -- H3's open/solid palette pair -- so the display attribute file
    # is RE-DERIVED, cell by cell, from the shadow's solidity bit.  With the
    # shadow seeded a uniform $27 (bit 5 SET) every cell must land on the
    # SOLID entry, and none may keep the $5A the display was trashed with.
    return {'attr_writes': len(attrs), 'shadow_writes': len(shadow),
            'shadow_writer_pcs': sorted(set('%04X' % p for (p, _, _) in shadow)),
            'attr_lo': '%04X' % lo, 'attr_hi': '%04X' % hi,
            'palette_open': m[0x8309], 'palette_solid': m[0x830A],
            'shadow_seed': 0x27, 'display_seed': 0x5A,
            'final_values': {str(k): v for k, v in sorted(final.items())},
            'trash_left': final.get(0x5A, 0),
            'hud_rows_left_alone': below,
            'span': (hi - lo + 1) if lo is not None else None}


# ------------------------------------------------------------------ phase G
def phase_advance():
    """THE 80 -> 81 ADVANCE, DRIVEN LIVE, WITH $745C SEEDED.  The plan's anchor
       "at the far end $745C = $03E8" is satisfied by a port that NEVER TOUCHES
       IT: on bosskilled it already reads $03E8 at frame 0.  Seed it to a
       poison (F0's own recipe does) or the row cannot fail.

       And there is a +300 award in this run that appears in no entry -- so the
       score is watched with its PC."""
    h, m = new('bosskilled')
    m[R81_TIMER] = 0xAA; m[R81_TIMER + 1] = 0xBB      # the POISON F0 uses
    m[LOOKAHEAD] = POISON
    before = {'round': m[ROUND], 'lookahead': m[LOOKAHEAD],
              'r81_timer': (m[R81_TIMER + 1] << 8) | m[R81_TIMER],
              'boss_y': m[BOSS_Y], 'hp': m[HP],
              'score': [m[P1_SCORE + i] for i in range(4)]}
    h.memobj.watch(0x4000, 0x10000)
    marks = []
    prev = {'round': m[ROUND], 'lookahead': m[LOOKAHEAD], 'hp': m[HP],
            'boss_y': m[BOSS_Y]}
    score_writes = []
    pend = []
    frame = 0
    while frame < 460:
        h.run_frames(1)
        frame += 1
        for (p, a, v) in h.memobj.log:
            if P1_SCORE <= a < P1_SCORE + 4:
                score_writes.append([frame, '%04X' % p, '%04X' % a, v])
            if a == R81_TIMER or a == R81_TIMER + 1:
                marks.append([frame, 'r81_timer', '%04X' % p, v])
            # THE +300 AT f417 APPEARS IN NO ENTRY.  Name it: the PENDING
            # award field $FFED/$FFEE, the award-owner operand $9F09 that B6
            # found, and the boss HP byte, each with the PC that wrote it.
            if 0xFFED <= a <= 0xFFEE or a == 0x9F09 or a == HP:
                pend.append([frame, '%04X' % p, '%04X' % a, v])
        h.memobj.log = []
        for k, a in (('round', ROUND), ('lookahead', LOOKAHEAD),
                     ('hp', HP), ('boss_y', BOSS_Y)):
            if m[a] != prev[k]:
                marks.append([frame, k, prev[k], m[a]])
                prev[k] = m[a]
    h.memobj.unwatch()
    return {'before': before,
            'after': {'round': m[ROUND], 'lookahead': m[LOOKAHEAD],
                      'r81_timer': (m[R81_TIMER + 1] << 8) | m[R81_TIMER],
                      'boss_y': m[BOSS_Y], 'hp': m[HP],
                      'score': [m[P1_SCORE + i] for i in range(4)]},
            'marks': marks,
            'r81_timer_written': any(x[1] == 'r81_timer' for x in marks),
            'score_writers': sorted(set(x[1] for x in score_writes)),
            'score_write_frames': sorted(set(x[0] for x in score_writes)),
            'score_writes': score_writes[:40],
            'award_trail': pend,
            'award_writers': sorted(set(x[1] for x in pend)),
            'hp_writers': sorted(set(x[1] for x in pend if x[2] == '9F62')),
            'frames': frame}


# ------------------------------------------------------------------ phase H
def phase_walk_negative():
    """THE CLEAR WALK'S SURVIVORS -- the genuinely new half of (c).  H1's
       roundadv.py already gates the 19 targets it DOES zero; this is the list
       it does NOT, poisoned so that "survived" is a measurement and not the
       absence of a write."""
    survivors = {'A8DB': 0xA8DB, 'AA47': 0xAA47, 'AA48': 0xAA48,
                 'AA06': 0xAA06, 'A82D': 0xA82D, '9F62': 0x9F62,
                 'A98F': 0xA98F, 'A990': 0xA990}
    for i in range(8):
        survivors['A89%X' % (1 + i)] = 0xA891 + i
    h, m = new('bosskilled')
    for a in survivors.values():
        m[a] = POISON
    h.memobj.watch(0x4000, 0x10000)
    arm(h, WALK)
    h.run_until((WALK_END,) + sentinels(h), limit=400000, stride=1,
                interrupts=False)
    stopped = '%04X' % h.regs[PC]
    log = list(h.memobj.log)
    h.memobj.unwatch()
    after = {k: m[a] for k, a in survivors.items()}
    return {'stopped_at': stopped,
            'writes': len(log),
            'writer_pcs': sorted(set('%04X' % p for (p, _, _) in log)),
            'written_addrs': sorted(set('%04X' % a for (_, a, _) in log)),
            'survivors': after,
            'all_survived': all(v == POISON for v in after.values()),
            'n_survivors': len(after),
            'overlap_with_written': sorted(
                k for k, a in survivors.items()
                if any(x[1] == a for x in log))}


PHASES = [('edge', phase_edge), ('paint', phase_paint),
          ('thunder', phase_thunder), ('payload', phase_payload),
          ('flood', phase_flood), ('restore', phase_restore),
          ('advance', phase_advance), ('walk_negative', phase_walk_negative)]

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
        print(json.dumps(fx[nm])[:1200], flush=True)
    if not only:
        json.dump(fx, open(FIXTURE, 'w'), indent=1, sort_keys=True)
        print('\nwrote', FIXTURE)
