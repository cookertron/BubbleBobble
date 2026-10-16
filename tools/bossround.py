"""B11 -- THE BOSS ROUND, END TO END: the differential, and the state selection
that invalidates part of the range behind it.

*** THE CORRECTION THIS ENTRY EXISTS TO CARRY. ***  build/boss.pkl and
build/bossspawn.pkl are captured INSIDE THE ROUND-80 SETTLE WINDOW.  $AA6E
reads ($B54B) and $AA72 `JP nz,$B520` ABANDONS THE WHOLE ENTITY PASS while it
is non-zero.  Every "the player never did X on round 80" negative measured on
those two states is partly a statement about the settler, not about the rule.

WHAT THIS ORACLE IS, AND WHAT IT IS NOT.  A byte-for-byte world differential
would need the engine seeded from a capture -- which means shipping the 48K
image, and house rule 7 forbids that.  So the differential is over the SAMPLED
STATE VECTOR: one row per MAIN-LOOP PASS, every field tagged with the increment
that owns it, and an `unimplemented` list the gate asserts is EXACTLY the set
that diverges.  "Not a differential failure, a missing increment" becomes an
assertion instead of a paragraph -- which is what the plan's own critic asked
for, and it is the only way a red row can name itself.

AND EVERY NEGATIVE HERE IS PAIRED.  A negative in this range is a ZERO, and a
zero is satisfied by a port that does less: $8ECF never entered, $A824's body
never entered, ($FED4) never written, ($FECA) stays 00.  Each one is driven
again in a world where it DOES fire, so the pair says something.

THE TWO ADDRESSES THE WHOLE PLAN LEFT UNOWNED, taken here:
  * $8E58 `LD ($FFEF),A` with A = $10 -- the +100000 boss-kill bonus, paid into
    the THIRD byte of the four-byte pending field, in the same frame as B6's
    +100 bolt award.  A port that owns one of the two is wrong by a factor of
    a thousand.
  * $9269 `CALL c,$927D` inside $9250, the chain's PLAYER-ENEMY pass at $8D52 --
    the SECOND caller of the damage tail.  B8 said "a CALL scan of $927D's
    callers misses it"; a CALL scan FINDS $9269 and misses $AA36, which is the
    tail JUMP.  "Entered only via $AA35" is a round-80-only statement.

Usage:  python tools/bossround.py     (capture -> build/bossround_fixture.json)
        python tools/bossround.py NAME [NAME...]   (one phase, no write)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bossround_fixture.json'
BRANCH_BYTE = 0x8DC4
ISR, LOOPTOP = 0x8D72, 0x8D0C
ROUND = 0x8609
SETTLER = 0xB54B
ENTITY_PASS = 0xAA60
PLAYER_TICK_LO, PLAYER_TICK_HI = 0xAB00, 0xAC40
DEATH_DISPATCH = 0xAB38
HP = 0x9F62
P1_SCORE = 0xFFE5
PEND = 0xFFED                      # four bytes: $FFED..$FFF0
MILLION = 0x8E58                   # LD ($FFEF),A with A = $10
KILLTAIL, KILL_C, KILL_JP = 0x927D, 0x9269, 0xAA35
PLAYER_ENEMY = 0x925A              # the chain entry at $8D52
CLEAR_LATCH, BOSS_LATCH = 0x8ECF, 0x8E3B
GIANT, GIANT_GATE = 0xA824, 0xA832
FED4, FECA = 0xFED4, 0xFECA
R81_TIMER = 0x745C
LOOKAHEAD = 0xFEC7

POISON = 0x5A

# ---- THE SAMPLED STATE VECTOR, and who owns each field. -------------------
# `None` means NO increment implements it yet: the gate asserts that list is
# exactly the set that diverges, so coverage cannot shrink in silence.
FIELDS = [
    # $8DBD is the frame counter the ISR drives.  It is sampled FIRST because
    # the engine-side differential REPLAYS it: the port's mainLoop() is fed the
    # machine's own frame timeline and nothing else, and must then reproduce
    # the boss's whole trajectory, the tick divider and $A09A's edge operand
    # from its own code.  Without it the divider never advances on either side
    # and the comparison is between two frozen worlds.
    ('8DBD', 0x8DBD, 'REPLAYED -- the ISR frame counter, the differential input'),
    ('8609', 0x8609, 'B0/F0 roundAdvance'),
    ('9F62', 0x9F62, 'B2/B6 boss HP'),
    ('A839', 0xA839, 'B3 boss Y'),
    ('A8DB', 0xA8DB, 'B4 boss X (the draw operand)'),
    ('AA00', 0xAA00, 'B0 the tick divider operand'),
    ('AA06', 0xAA06, 'B0 the 32-tick counter'),
    ('AA47', 0xAA47, 'B3 boss dX'),
    ('AA48', 0xAA48, 'B3 boss dY'),
    ('9F09', 0x9F09, 'B6 the award-owner operand'),
    ('8E3B', 0x8E3B, 'B1 the round-cleared latch'),
    ('B54B', 0xB54B, 'M7.7-a the settler'),
    ('FEC7', 0xFEC7, 'B0/M7.7-c the lookahead'),
    ('FEC8', 0xFEC8, 'B0 the pass counter'),
    ('FEC9', 0xFEC9, 'B1 the game-over counter'),
    ('FECD', 0xFECD, 'B0 the skip count'),
    ('A09E', 0xA09E, 'B10 the edge operand'),
    ('8309', 0x8309, 'H3/H8 the open palette'),
    ('830A', 0x830A, 'H3/H8 the solid palette'),
    # *** ADDED M7.8-A, AND THE REASON IS THE POINT. ***  These two were not
    # sampled because nothing in the port stepped them: the palette pair was
    # CARRIED from the render asset and the tile index was hard-seeded.  Wiring
    # the round builder $7F62 makes both LIVE INPUTS -- $82D6 reads ($82D7) and
    # $83EB reads ($83EC) -- so a differential that seeds only the 36 old fields
    # starts the port on round 1's counters against a round-80 world and
    # diverges on ($8309) at the advance, 70 against 69.  A field set is only
    # complete with respect to the increments that exist when it was written.
    ('82D7', 0x82D7, 'M7.8-A the palette build counter'),
    ('83EC', 0x83EC, 'M7.8-A the tile build counter'),
    ('FD87', 0xFD87, 'M7.4/B9 P1 flags'),
    ('FD91', 0xFD91, 'M7.4/B9 P2 flags'),
    ('FDDA', 0xFDDA, 'M7.4/B9 P1 state'),
    ('FDE4', 0xFDE4, 'M7.4/B9 P2 state'),
    ('FDF3', 0xFDF3, 'B6 bolt slot 0 +5 (X)'),
    ('FDF4', 0xFDF4, 'B6 bolt slot 0 +6 (Y)'),
    ('FDF5', 0xFDF5, 'B6 bolt slot 0 +7'),
    ('FDFD', 0xFDFD, 'B6 bolt slot 1 +5 (X)'),
    ('FDFE', 0xFDFE, 'B6 bolt slot 1 +6 (Y)'),
    ('FDFF', 0xFDFF, 'B6 bolt slot 1 +7'),
    # $A98F/$A990 ARE STATE, and leaving them out of the vector let the engine
    # run with reset()'s tape value `37 C9` -- SCF / RET, every position an
    # overlap -- while the machine had `00 00`.  The engine killed P1 on pass
    # 10 of bosshit and the differential called it a boss bug (B5, TRAPS #79).
    ('A98F', 0xA98F, 'B5 the comparator pair, low'),
    ('A990', 0xA990, 'B5 the comparator pair, high'),
    ('A85C', 0xA85C, None),          # B4 named it; the port does not carry it
    ('A8C2', 0xA8C2, None),
    ('A8FD', 0xA8FD, None),
    ('5B00', 0x5B00, None),          # the committed B8 projectile slots
    ('5B0A', 0x5B0A, None),
]


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


# ------------------------------------------------------------------ phase A
def phase_settle():
    """*** A CAPTURE CAN SIT INSIDE A WINDOW THAT SWITCHES A WHOLE PASS OFF. ***
       $AA72 `JP nz,$B520` abandons the entity pass while ($B54B) is non-zero,
       and two of the four boss captures are inside that window.  Profile the
       player tick BEFORE recording that it did not run."""
    out = {}
    for st in ('boss', 'bossspawn', 'bosshit', 'bosskilled', 'r50_48',
               'play1p48'):
        h, m = new(st)
        start = m[SETTLER]
        n = {'AA60': 0, 'AB38': 0, 'player_tick_range': 0}
        frames = 0
        zero_at = None
        while frames < 120:
            reason, _ = h.run_until((ISR, ENTITY_PASS, DEATH_DISPATCH),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frames += 1
                if m[SETTLER] == 0 and zero_at is None:
                    zero_at = frames
            elif p == ENTITY_PASS:
                n['AA60'] += 1
            else:
                n['AB38'] += 1
            h.step(1)
        # ...and the instruction census over $AB00..$AC40, which is the claim
        # that actually matters: "no player tick ran", not "a counter is zero".
        h2, m2 = new(st)
        hits = 0
        steps = 0
        while steps < 400000:
            pcv = h2.regs[PC]
            if PLAYER_TICK_LO <= pcv < PLAYER_TICK_HI:
                hits += 1
            h2.step(1)
            steps += 1
        out[st] = {'round': m[ROUND], 'B54B_start': start,
                   'B54B_end': m[SETTLER], 'zero_at_frame': zero_at,
                   'frames': frames, 'counts': n,
                   'instr_in_AB00_AC40_per_400k': hits,
                   'inside_settle_window': start != 0}
    return out


# ------------------------------------------------------------------ phase B
def sample(m):
    return [m[a] for (_, a, _) in FIELDS]


def phase_passdiff():
    """ONE ROW PER MAIN-LOOP PASS, every field tagged with its owner.

       *** A MAIN-LOOP PASS IS NOT ATOMIC WITH RESPECT TO THE FRAME COUNTER. ***
       The loop runs ~8.6 times per frame, so roughly one pass in nine STRADDLES
       an ISR and the chain members see DIFFERENT values of ($8DBD): the boss
       tick at $8D2E reads one, $A09A at $8D43 reads the next.  A replay that
       feeds one value per pass reproduces the boss and is off by one on
       $A09E -- which is what the first version of this phase did, and it looks
       exactly like an engine bug in the effect manager.
       So the row carries BOTH samples, taken at $A9ED and at $A09A, and the
       gate walks BB_CHAIN itself, switching the counter at the same point the
       machine did.

       AND A LOOP-TOP ROW IS THE RESULT OF THE PREVIOUS PASS.  The other fields
       in row r were produced by the chain of pass r-1, so the input that drove
       them is the counter sampled DURING that pass, not the one sampled beside
       them."""
    out = {'fields': [[k, '%04X' % a, o] for (k, a, o) in FIELDS],
           'unimplemented': [k for (k, _, o) in FIELDS if o is None],
           'runs': {}}
    BOSS_TICK, EDGE = 0xA9ED, 0xA09A
    for st, passes in (('bosshit', 600), ('bosskilled', 600),
                       ('r50_48', 400)):
        h, m = new(st)
        rows, inputs = [], []
        frames = 0
        n = 0
        at_boss, at_edge = m[0x8DBD], m[0x8DBD]
        straddles = 0
        while n < passes:
            reason, _ = h.run_until((LOOPTOP, ISR, BOSS_TICK, EDGE),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            pcv = h.regs[PC]
            if pcv == ISR:
                frames += 1
            elif pcv == BOSS_TICK:
                at_boss = m[0x8DBD]
            elif pcv == EDGE:
                at_edge = m[0x8DBD]
            else:
                rows.append(sample(m))
                inputs.append([at_boss, at_edge])
                if at_boss != at_edge:
                    straddles += 1
                n += 1
            h.step(1)
        changed = [i for i in range(len(FIELDS))
                   if len(set(r[i] for r in rows)) > 1]
        # WHERE THE ROUND ADVANCES, THE COMPARISON HAS TO STOP AND SAY SO.
        # $97F8's counter arithmetic is transliterated; the round BUILD it
        # leads to ($8C5E and everything under it) is not, so past that row the
        # two sides are different worlds -- the frame counter restarts, the HP
        # is re-armed and a FRESH SETTLE WINDOW opens.  The fields that differ
        # AT that row are the work the round-build increment inherits.
        ri = [k for (k, a, o) in FIELDS].index('8609')
        adv = next((n for n in range(1, len(rows))
                    if rows[n][ri] != rows[n - 1][ri]), None)
        handover = []
        if adv is not None:
            handover = [FIELDS[i][0] for i in range(len(FIELDS))
                        if rows[adv][i] != rows[adv - 1][i]]
        out['runs'][st] = {
            'round': rows[0][1] if rows else None,
            'passes': len(rows), 'frames': frames,
            'passes_per_frame': round(len(rows) / frames, 3) if frames else None,
            'straddling_passes': straddles,
            'first': rows[0] if rows else None,
            'last': rows[-1] if rows else None,
            'moving_fields': [FIELDS[i][0] for i in changed],
            'static_fields': [FIELDS[i][0] for i in range(len(FIELDS))
                              if i not in changed],
            'advance_row': adv, 'advance_handover': handover,
            # *** THIS STRING LIVED ONLY IN THE ARTIFACT AND A RECAPTURE ATE IT. ***
            # M7.7-R1 annotated advance_owner by editing build/bossround_fixture.json
            # directly; regenerating for M7.8-A silently reverted it to the 2026-09-17
            # text and took a gate red.  TRAPS #92 rule (b): the note belongs in the
            # PRODUCING TOOL, because the artifact is the tool's output and nothing
            # else.  The history is carried here now.
            'advance_owner':
                '$8C5E the round build -- NOT transliterated '
                '[SUPERSEDED 2026-09-22 by M7.7-R1, which wired the round-start '
                'sequence: the round build no longer diverges here.  What remains at '
                'row 20 is ($B54B), by exactly the settler ticks the ROUND BANNER '
                '$98B5.. spends.] '
                '[SUPERSEDED AGAIN 2026-09-23 by M7.8-A, which wired the BUILDER $7F62 '
                'itself through $7F1B.  ($830A) is no longer skipped by the drained '
                'differential and bosshit, r50_48 and bosskilled all walk GREEN with '
                'it live.  The handover grew 20 -> 22 because ($82D7) and ($83EC) '
                'joined the field set: they MOVE across the advance now, which is '
                'the builder stepping them, and they are the two the old 36-field '
                'vector could not see.]',
            'rows': rows[:60], 'inputs': inputs[:60]}
    return out


# ------------------------------------------------------------------ phase C
def phase_anchors():
    """Every anchor the entry names, re-measured -- with ($745C) SEEDED, because
       bosskilled already holds $03E8 [B10], and with the span asserted rather
       than the frame, because 76 is 256 - $B4 and the frame belongs to the
       state [B9]."""
    h, m = new('bosskilled')
    m[R81_TIMER] = 0xAA; m[R81_TIMER + 1] = 0xBB
    m[LOOKAHEAD] = POISON
    for i in range(4):
        m[PEND + i] = 0                     # the pending field, SEEDED ZERO
    before = {'hp': m[HP], 'round': m[ROUND],
              'score': [m[P1_SCORE + i] for i in range(4)],
              'r81_timer': (m[R81_TIMER + 1] << 8) | m[R81_TIMER],
              'lookahead': m[LOOKAHEAD]}
    h.memobj.watch(0x4000, 0x10000)
    marks = []
    prev = {'hp': m[HP], 'round': m[ROUND]}
    busy = 0
    frame = 0
    r81_written = False
    pend_writes = []
    while frame < 460:
        h.run_frames(1)
        frame += 1
        for (p, a, v) in h.memobj.log:
            if PEND <= a < PEND + 4:
                pend_writes.append([frame, '%04X' % p, '%04X' % a, v])
            if a == HP:
                marks.append([frame, 'hp', '%04X' % p, v])
            if a == ROUND:
                marks.append([frame, 'round', '%04X' % p, v])
            if a in (R81_TIMER, R81_TIMER + 1):
                r81_written = True
        h.memobj.log = []
        for k, a in (('hp', HP), ('round', ROUND)):
            prev[k] = m[a]
    h.memobj.unwatch()
    return {'before': before,
            'after': {'hp': m[HP], 'round': m[ROUND],
                      'score': [m[P1_SCORE + i] for i in range(4)],
                      'r81_timer': (m[R81_TIMER + 1] << 8) | m[R81_TIMER],
                      'lookahead': m[LOOKAHEAD], 'boss_y': m[0xA839]},
            'marks': marks, 'pend_writes': pend_writes,
            'hp_writers': sorted(set(x[2] for x in marks if x[1] == 'hp')),
            'round_frame': next((x[0] for x in marks if x[1] == 'round'), None),
            'r81_timer_written': r81_written,
            'frames': frame, 'busy': busy}


# ------------------------------------------------------------------ phase D
def phase_million():
    """$8E58 -- THE +100000, AND NOBODY OWNED IT.  `DI / LD A,$10 /
       LD ($FFEF),A`: the THIRD byte of the four-byte pending field, so $10 in
       BCD lands on the 100000s.  It is paid in the SAME FRAME as B6's +100
       bolt award, and the pending field is SEEDED ZERO first because $80FA
       clears it -- otherwise "paid a hundred thousand" and "paid nothing" are
       the same row (TRAPS #44)."""
    tape = open('build/image_tape.bin', 'rb').read()
    h, m = new('bosskilled')
    for i in range(4):
        m[PEND + i] = 0
    before = [m[P1_SCORE + i] for i in range(4)]
    h.memobj.watch(0x4000, 0x10000)
    seen = []
    counts = {}
    frame = 0
    while frame < 12:
        reason, _ = h.run_until((ISR, MILLION, 0x9F05, 0x8164), limit=400000,
                                stride=1)
        if reason != 'target':
            break
        p = h.regs[PC]
        if p == ISR:
            for (wp, a, v) in h.memobj.log:
                if PEND <= a < PEND + 4 or P1_SCORE <= a < P1_SCORE + 4:
                    seen.append([frame, '%04X' % wp, '%04X' % a, v])
            h.memobj.log = []
            frame += 1
        else:
            counts['%04X' % p] = counts.get('%04X' % p, 0) + 1
        h.step(1)
    h.memobj.unwatch()
    return {'opcode_at_8E56': list(tape[0x8E55:0x8E5B]),
            'counts': counts,
            'pending_byte': '%04X' % 0xFFEF,
            'score_before': before,
            'score_after': [m[P1_SCORE + i] for i in range(4)],
            'writes': seen[:40],
            'million_writes': [x for x in seen if x[1] == '8E58'],
            'bolt_writes': [x for x in seen if x[1] == '9F05'],
            # $9F05 writes TWO bytes and $8E58 writes one, so comparing the
            # frame LISTS compares [3] with [3, 3] and says "not the same
            # frame" about two writes in the same frame.  Compare the SETS.
            'million_frames': sorted(set(x[0] for x in seen
                                         if x[1] == '8E58')),
            'bolt_frames': sorted(set(x[0] for x in seen if x[1] == '9F05')),
            'same_frame': (bool([x for x in seen if x[1] == '8E58']) and
                           sorted(set(x[0] for x in seen if x[1] == '8E58')) ==
                           sorted(set(x[0] for x in seen if x[1] == '9F05')))}


# ------------------------------------------------------------------ phase E
def phase_second_caller():
    """$9269 -- THE SECOND CALLER OF $927D, AND IT IS IN THE CHAIN.  $9250 is
       reached from $8D52 (BB_CHAIN's `playerEnemy`), and its body is
       `BIT 7,(IX+7) / CALL nz,$92BB / CALL c,$927D` per player.  B8's negative
       said a CALL scan of $927D's callers MISSES it; a CALL scan FINDS $9269
       and misses $AA36, which is a JP.  Census both forms, then DRIVE it."""
    tape = open('build/image_tape.bin', 'rb').read()
    calls, jumps = [], []
    for i in range(0x4000, 0xFFFE):
        if tape[i + 1] == 0x7D and tape[i + 2] == 0x92:
            if tape[i] in (0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC,
                           0xF4, 0xFC):
                calls.append('%04X' % i)
            elif tape[i] in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA,
                             0xF2, 0xFA):
                jumps.append('%04X' % i)
    out = {'call_sites': calls, 'jump_sites': jumps,
           'a_call_scan_finds': calls, 'a_call_scan_misses': jumps}
    # ...and the POSITIVE row: drive $925A where the hurry-up block is live.
    for st in ('hurryup', 'r50_48', 'bosshit'):
        h, m = new(st)
        n = {'925A': 0, '9269': 0, '927D': 0, 'AA35': 0}
        frames = 0
        while frames < 120:
            reason, _ = h.run_until((ISR, PLAYER_ENEMY, KILL_C, KILLTAIL,
                                     KILL_JP), limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frames += 1
            else:
                n['%04X' % p] = n.get('%04X' % p, 0) + 1
            h.step(1)
        out[st] = {'round': m[ROUND], 'frames': frames, 'counts': n}
    # ...and the POSITIVE row, BUILT: $9269 runs on every round (721 / 588 /
    # 1018 entries in 120 frames on hurryup / r50_48 / bosshit) but $92BB only
    # returns CARRY on a real overlap, so in play $927D is entered ZERO times
    # from it and "the second caller exists" and "the second caller never
    # fires" are the same row.  Park an ACTIVE enemy on top of P1.
    for st in ('r50_48', 'hurryup'):
        h, m = new(st)
        px, py = m[0xFD85], m[0xFD86]
        m[0xFD87] |= 0x80                       # P1 in play
        m[0xFDDA] &= ~0x1C & 0xFF               # not already dying/carried
        for k in range(7):                      # every enemy slot, on the player
            b = 0xFD94 + 10 * k
            m[b + 5] = px; m[b + 6] = py
            m[b + 7] |= 0x80
        n = {'925A': 0, '9269': 0, '927D': 0, 'AA35': 0}
        frames = 0
        state_before = m[0xFDDA]
        while frames < 30:
            reason, _ = h.run_until((ISR, PLAYER_ENEMY, KILL_C, KILLTAIL,
                                     KILL_JP), limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frames += 1
            else:
                n['%04X' % p] = n.get('%04X' % p, 0) + 1
            h.step(1)
        out['built_' + st] = {'round': m[ROUND], 'frames': frames,
                              'counts': n, 'p1_pos': [px, py],
                              'state_before': state_before,
                              'state_after': m[0xFDDA],
                              'timer_after': m[0xFD84],
                              'reached_927D_from_9269': n['927D'] > 0 and
                                                        n['AA35'] == 0}
    return out


# ------------------------------------------------------------------ phase F
def phase_paired_negatives():
    """EVERY NEGATIVE IN THIS RANGE IS A ZERO, AND A ZERO IS SATISFIED BY A PORT
       THAT DOES LESS.  The first version of this phase reported all four
       probes surviving on all five states and called it done -- five negatives
       and not one positive, which is the shape the plan's own critic warned
       about.  Each is driven again in a world where it DOES fire.

       *** AND $A824's NEGATIVE WAS WRONG. ***  "The body never entered
       ($A832 CP $50 / RET z)" conflates two different gates.  $A824 reads
       ($A839) and RETs at $A828 when there is no giant; then it is a SECOND
       CP-FORM EDGE DETECTOR -- $A82C `CP $2A` against $A82D, ITS OWN OPERAND,
       exactly $A09A's idiom -- and only THEN does $A835 `CP $50 / RET z` send
       the boss round home.  So off round 80 it returns at $A828 for want of a
       giant, and ON round 80 it returns at $A837 having passed both earlier
       tests.  The body IS entered, 1300 times in 150 frames."""
    out = {'probes': {}, 'giant': {}}
    probes = (('8ECF', CLEAR_LATCH), ('8E3B', BOSS_LATCH), ('FED4', FED4),
              ('FECA', FECA))
    # ---- the NEGATIVE side, with its frame count (TRAPS #48) --------------
    for st in ('bosshit', 'bosskilled', 'r50_48', 'peachfall', 'hurryup'):
        h, m = new(st)
        for _, a in probes:
            m[a] = POISON
        h.memobj.watch(0x4000, 0x10000)
        n = {'A824': 0, 'A828': 0, 'A832': 0, 'A838': 0, '8ECF': 0,
             '8EC1': 0, '8ED1': 0}
        frames = 0
        while frames < 150:
            reason, _ = h.run_until((ISR, GIANT, 0xA828, GIANT_GATE, 0xA838,
                                     CLEAR_LATCH, 0x8EC1, 0x8ED1),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            pv = h.regs[PC]
            if pv == ISR:
                frames += 1
            else:
                n['%04X' % pv] = n.get('%04X' % pv, 0) + 1
            h.step(1)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        touched = {}
        for (pp, a, v) in log:
            for name, addr in probes:
                if a == addr:
                    touched.setdefault(name, []).append('%04X' % pp)
        out['probes'][st] = {
            'round': m[ROUND], 'frames': frames, 'counts': n,
            'probe_writers': {k: sorted(set(v)) for k, v in touched.items()},
            'survived': [name for name, a in probes if m[a] == POISON],
            'giant_exit': ('A828 no giant' if n['A828'] and not n['A832']
                           else 'A837 boss round' if n['A832'] and not n['A838']
                           else 'past A837' if n['A838'] else 'not entered')}
    # ---- the POSITIVE side: FORCE A ROUND CLEAR off the boss round --------
    # Zeroing the enemy slots is the recipe extract_round_colours.py uses; it
    # is the only way to reach $8ECF/$8EC1/$8ED1 inside a bounded run.
    for st in ('r50_48', 'hurryup'):
        h, m = new(st)
        for _, a in probes:
            m[a] = POISON
        for k in range(7):
            b = 0xFD94 + 10 * k
            for off in range(10):
                m[b + off] = 0
        h.memobj.watch(0x4000, 0x10000)
        n = {'8ECF': 0, '8EC1': 0, '8ED1': 0}
        frames = 0
        while frames < 200:
            reason, _ = h.run_until((ISR, CLEAR_LATCH, 0x8EC1, 0x8ED1),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            pv = h.regs[PC]
            if pv == ISR:
                frames += 1
            else:
                n['%04X' % pv] = n.get('%04X' % pv, 0) + 1
            h.step(1)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        touched = {}
        for (pp, a, v) in log:
            for name, addr in probes:
                if a == addr:
                    touched.setdefault(name, []).append('%04X' % pp)
        out['probes']['cleared_' + st] = {
            'round': m[ROUND], 'frames': frames, 'counts': n,
            'probe_writers': {k: sorted(set(v)) for k, v in touched.items()},
            'survived': [name for name, a in probes if m[a] == POISON],
            'fired': [name for name, a in probes if m[a] != POISON]}
    # ---- and $FED4: no positive exists, so ENUMERATE rather than assert ---
    tape = open('build/image_tape.bin', 'rb').read()
    direct = ['%04X' % i for i in range(0x4000, 0xFFFD)
              if tape[i] in (0x32, 0x22) and tape[i + 1] == (FED4 & 0xFF)
              and tape[i + 2] == (FED4 >> 8)]
    pointer = ['%04X' % i for i in range(0x4000, 0xFFFD)
               if tape[i] in (0x21, 0x11, 0x01) and tape[i + 1] == (FED4 & 0xFF)
               and tape[i + 2] == (FED4 >> 8)]
    out['FED4_enumeration'] = {
        'direct_stores': direct, 'pointer_loads': pointer,
        'note': ('no direct store and no 16-bit pointer load anywhere in 48K, '
                 'so the negative is STRUCTURAL: there is nothing to make fire, '
                 'which is a stronger statement than "it did not fire in N '
                 'frames" and is recorded as such')}
    # ---- the GIANT's own positive: a round where a giant IS present -------
    for st in ('peachfall', 'candycane', 'crown', 'bosshit'):
        try:
            h, m = new(st)
        except SystemExit:
            continue
        n = {'A824': 0, 'A828': 0, 'A832': 0, 'A838': 0}
        frames = 0
        while frames < 150:
            reason, _ = h.run_until((ISR, GIANT, 0xA828, GIANT_GATE, 0xA838),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            pv = h.regs[PC]
            if pv == ISR:
                frames += 1
            else:
                n['%04X' % pv] = n.get('%04X' % pv, 0) + 1
            h.step(1)
        out['giant'][st] = {'round': m[ROUND], 'A839': m[0xA839],
                            'A82D': m[0xA82D], 'frames': frames, 'counts': n,
                            'past_the_round_gate': n['A838'] > 0}
    return out


PHASES = [('settle', phase_settle), ('passdiff', phase_passdiff),
          ('anchors', phase_anchors), ('million', phase_million),
          ('second_caller', phase_second_caller),
          ('paired_negatives', phase_paired_negatives)]

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
