"""B9 -- THE DEATH SEQUENCE, AND THE LINK FROM A DEATH TO A GAME OVER.

The death tick $AB3F-$ABD4 has been shipped and gated since M7.4d-iii.  What it
has never had is the OUT-OF-LIVES BRANCH -- three instructions that only run
when `DEC (IY+$5C)` goes negative:

    $AB5E DEC (IY+$5C) / $AB61 JP p,$AB6B / $AB64 RES 7,(IY+7) / $AB68 CALL $BF0A

*** $AB68 IS AN UNNAMED OMISSION: THE PORT'S FINAL DEATH LEAVES THE PLAYER'S
LAST FRAME ON SCREEN. ***  A grep of web/game.js and every docs/*.md for AB68
returned nothing.  $BF0A sets the erase cache from the LIVE position and, having
no RET of its own, falls through into $BF16 and rubs the sprite out.

AND THE OBVIOUS ORACLE FOR IT CANNOT FAIL.  The drafted plan says to poison the
cache bytes (IY+2)/(IY+3) and diff the display file.  $FD82/$FD83 have TWO
ORDINARY PER-FRAME WRITERS -- $A603 and $A623 -- which wipe the poison long
before the death branch runs, and $BF0A writes the live position those two have
already put there.  TRAPS #44 in its purest form: a port that omits $AB68
ENTIRELY passes that oracle, and the display diff is thousands of bytes of
unrelated rendering.  Phase B measures the poison being wiped AS A ROW, so the
false oracle is refuted in the fixture and not just in a comment.

THE SEPARATOR IS A PC-ATTRIBUTED WRITE LOG.  $BF0D and $BF13 are the two
instructions that write the cache inside $BF0A; they must fire EXACTLY ONCE on
the out-of-lives frame and NEVER on a respawn, and the 3-lives run is the
control that says so.

THE LOAD-BEARING SUBTLETY: $AB64 clears bit 7 BEFORE $AB68 runs, and $A447
sends a bit-7-CLEAR slot to $A437 -- the bookkeeping arm, which erases nothing.
$BF16 gets the erase anyway by FORCING (IY+7) := $C0 across the call and
restoring it afterwards.  So "the player is out of play, so skip the erase" is
exactly the wrong optimisation, and phase B drives the flags byte to prove it.

NO CAPTURE CAN SERVE.  Every shipped .pkl has at least one player in play, so
the whole arrow -- death, out of lives, out of play, $8E2A, the exit -- is
unreachable without a BUILD.

HAZARD (measured by the plan, reproduced here as a rule): an isolated
h.call($AB5E) RUNS AWAY -- 2,000,000 steps, no sentinel -- because $AB5E is
MID-ROUTINE and falls through the respawn, $806C, $AB76 and on past $ABD4 with
register and stack state an isolated call does not reproduce.  Everything here
is driven by RUNNING FRAMES with the lives byte seeded.

Usage:  python tools/bossdeath2.py     (capture -> build/bossdeath2_fixture.json)
        python tools/bossdeath2.py NAME [NAME...]   (one phase, no write)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bossdeath2_fixture.json'
BRANCH_BYTE = 0x8DC4
ROUND = 0x8609

P1, P2 = 0xFD80, 0xFD8A          # the two player slots, stride 10 on +0..+9
P1_FLAGS, P2_FLAGS = 0xFD87, 0xFD91          # +7
P1_STATE, P2_STATE = 0xFDDA, 0xFDE4          # +$5A
P1_LIVES, P2_LIVES = 0xFDDC, 0xFDE6          # +$5C
P1_CACHE_Y, P1_CACHE_X = 0xFD82, 0xFD83      # +2 / +3
P1_TIMER, P1_X, P1_Y = 0xFD84, 0xFD85, 0xFD86

OVER = 0xFEC9                    # the game-over counter $8CFC INCs
DEATH = 0xAB38                   # the death dispatch
DEC_LIVES, SKIP, RES7, AB68 = 0xAB5E, 0xAB61, 0xAB64, 0xAB68
PANEL_CALL, R80_LATCH = 0xAB6D, 0xAB7D
BF0A, BF0D, BF13, BF16 = 0xBF0A, 0xBF0D, 0xBF13, 0xBF16
PANEL, PANEL_TAIL = 0x806C, 0x8097
WATCH, LATCH = 0x8E2A, 0x8E36
ISR = 0x8D72
KILLJP, KILLTAIL = 0xAA35, 0x927D
BUSYWAIT = 0x9573
LATCH_8E3B, LATCH_8ECF = 0x8E3B, 0x8ECF
FED0, FED4, FECA, HURRY_REQ = 0xFED0, 0xFED4, 0xFECA, 0x9160

POISON = 0x5A


def new(state, contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def build_death(m, lives, timer=0x02, poison_cache=False, poison_over=True):
    """THE BUILD, because no capture can serve.  P2 out of play, P1 dying, its
       death countdown two ticks from the end, and its LIVES byte set so that
       $AB5E's DEC does or does not go negative.

       ($FEC9) is seeded 0, NOT $B4: $8E36 writes $B4, so seeding $B4 makes the
       latch invisible (TRAPS #44).  Likewise the cache poison is $5A, a value
       $BF0A never writes -- but see phase B for why the poison is not enough."""
    m[P2_FLAGS] &= 0x7F                  # P2 OUT OF PLAY
    m[P1_FLAGS] |= 0x80                  # P1 in play, for now
    m[P1_STATE] |= 0x04                  # $AB38's dispatch bit: DYING
    m[P1_TIMER] = timer                  # +4, so the branch lands in 3 ticks
    m[P1_LIVES] = lives                  # +$5C: 0 -> out of lives, 3 -> respawn
    if poison_over:
        m[OVER] = 0x00
    if poison_cache:
        m[P1_CACHE_Y] = POISON
        m[P1_CACHE_X] = POISON


def drive(h, m, frames, targets=(), watch=None):
    """Run whole frames with the ISR live, stopping at `targets` to count them.
       Returns (counts, events, log) where log is the PC-attributed write log
       collected over the whole run if `watch` is a (lo, hi) pair."""
    counts = {}
    events = []
    frame = 0
    tset = (ISR,) + tuple(targets)
    if watch:
        h.memobj.watch(*watch)
    while frame < frames:
        reason, _ = h.run_until(tset, limit=400000, stride=1)
        if reason != 'target':
            break
        p = h.regs[PC]
        if p == ISR:
            frame += 1
        else:
            k = '%04X' % p
            counts[k] = counts.get(k, 0) + 1
            events.append([frame, k])
        h.step(1)
    log = list(h.memobj.log)          # ALWAYS: the caller may have armed the
    h.memobj.unwatch()                #   watch itself, and returning [] then
    return counts, events, log, frame  #   reads as "nothing was written".


# ------------------------------------------------------------------ phase A
def phase_chain():
    """THE ARROW, DRIVEN WHOLE: death -> out of lives -> out of play -> $8E2A
       -> the exit.  Two rounds, and on each the LAST LIFE against a 3-LIVES
       CONTROL, because "the arm is correct" and "the arm never ran" are one
       row otherwise."""
    out = {}
    for state in ('bosshit', 'r50_48'):
        for name, lives in (('last_life', 0x00), ('three_lives', 0x03)):
            h, m = new(state)
            rnd = m[ROUND]
            build_death(m, lives)
            before = {'flags': m[P1_FLAGS], 'lives': m[P1_LIVES],
                      'over': m[OVER], 'p2_flags': m[P2_FLAGS]}
            marks = {}
            prev = {'flags': m[P1_FLAGS], 'lives': m[P1_LIVES], 'over': m[OVER]}
            counts = {}
            frame = 0
            tset = (ISR, DEATH, DEC_LIVES, RES7, AB68, PANEL_CALL, R80_LATCH,
                    WATCH, LATCH, BUSYWAIT, KILLJP, KILLTAIL)
            over_seq = []
            while frame < 130:
                reason, _ = h.run_until(tset, limit=400000, stride=1)
                if reason != 'target':
                    break
                p = h.regs[PC]
                if p == ISR:
                    frame += 1
                    over_seq.append(m[OVER])
                    for k, a in (('flags', P1_FLAGS), ('lives', P1_LIVES),
                                 ('over', OVER)):
                        if m[a] != prev[k]:
                            marks.setdefault(k, []).append(
                                [frame, prev[k], m[a]])
                            prev[k] = m[a]
                else:
                    kk = '%04X' % p
                    counts[kk] = counts.get(kk, 0) + 1
                h.step(1)
            arm = marks.get('over', [[None]])[0][0] if 'over' in marks else None
            wrap = None
            for f, a, b in marks.get('over', []):
                if b == 0 and a != 0:
                    wrap = f
            out['%s_%s' % (state, name)] = {
                'round': rnd, 'before': before, 'counts': counts,
                'transitions': marks, 'frames': frame,
                'arm_frame': arm, 'wrap_frame': wrap,
                'span': (wrap - arm) if (arm is not None and wrap is not None)
                        else None,
                'latch_value': 0xB4,
                'after': {'flags': m[P1_FLAGS], 'lives': m[P1_LIVES],
                          'over': m[OVER], 'x': m[P1_X], 'y': m[P1_Y],
                          'timer': m[P1_TIMER], 'state': m[P1_STATE]}}
    return out


# ------------------------------------------------------------------ phase B
def phase_ab68():
    """*** THE ONE GENUINELY NEW MEASUREMENT, AND THE FALSE ORACLE BESIDE IT. ***

       (1) THE FALSE ORACLE, MEASURED: seed the cache bytes with $5A and watch
           who writes them.  $A603 and $A623 are ordinary per-frame writers and
           they wipe the poison within a frame or two -- long before the death
           branch -- and $BF0A then writes the live position they already put
           there.  A DISPLAY DIFF CANNOT SEE $AB68.
       (2) THE REAL SEPARATOR: the PC-attributed write log.  $BF0D and $BF13
           fire exactly once on the out-of-lives frame and never on a respawn.
       (3) THE SUBTLETY: $AB64 clears bit 7 first, and $A447 sends a
           bit-7-clear slot to $A437, which erases nothing.  $BF16 forces
           (IY+7) := $C0 across the call, so the erase happens anyway and the
           flags come back unchanged."""
    out = {}
    for name, lives in (('last_life', 0x00), ('three_lives', 0x03)):
        h, m = new('bosshit')
        build_death(m, lives, poison_cache=True)
        seeded = [m[P1_CACHE_Y], m[P1_CACHE_X]]
        h.memobj.watch(P1_CACHE_Y, P1_CACHE_X + 1)
        counts = {}
        cache_writes = []
        frame = 0
        tset = (ISR, AB68, BF0A, BF0D, BF13, BF16, RES7)
        flags_at_ab68 = None
        while frame < 40:
            reason, _ = h.run_until(tset, limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                for (wpc, addr, val) in h.memobj.log:
                    cache_writes.append([frame, '%04X' % wpc,
                                         '%04X' % addr, val])
                h.memobj.log = []
                frame += 1
            else:
                counts['%04X' % p] = counts.get('%04X' % p, 0) + 1
                if p == AB68:
                    flags_at_ab68 = m[P1_FLAGS]
            h.step(1)
        h.memobj.unwatch()
        writers = {}
        for (_, wpc, _, _) in cache_writes:
            writers[wpc] = writers.get(wpc, 0) + 1
        poison_gone = None
        for (f, wpc, _, _) in cache_writes:
            poison_gone = f
            break
        out[name] = {
            'seeded': seeded, 'counts': counts, 'cache_writers': writers,
            'first_overwrite_frame': poison_gone,
            'cache_writes': cache_writes[:24],
            'flags_at_ab68': flags_at_ab68,
            'flags_after': m[P1_FLAGS],
            'cache_after': [m[P1_CACHE_Y], m[P1_CACHE_X]],
            'live_pos': [m[P1_Y], m[P1_X]]}
    # ...and the ERASE ITSELF, attributed: what does the out-of-lives frame
    # write that the respawn frame does not?  Watched over the WHOLE writable
    # range, bucketed, because "it erased" is not a number (TRAPS #54).
    for name, lives in (('last_life', 0x00), ('three_lives', 0x03)):
        h, m = new('bosshit')
        build_death(m, lives)
        frame = 0
        buckets = {}
        total = 0
        pcs = {}
        armed = False
        done = False
        # THE EXACT BRACKET.  $AB5E is the DEC and $AB6B is where both arms
        # converge, so everything in between IS the out-of-lives branch and
        # nothing else.  (An earlier version harvested at $ABD4 and measured
        # ZERO: $ABD4 is P2's RET -- P1 leaves the tick at $ABCB, so the
        # harvest point was never reached.  TRAPS #81's shape again.)
        while frame < 12 and not done:
            reason, _ = h.run_until((ISR, DEC_LIVES, 0xAB6B), limit=400000,
                                    stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frame += 1
            elif p == DEC_LIVES:
                h.memobj.watch(0x4000, 0x10000)
                armed = True
            else:                                  # $AB6B, the join
                if armed:
                    for (wpc, addr, val) in h.memobj.log:
                        total += 1
                        k = ('display' if 0x4000 <= addr < 0x5800 else
                             'attrs' if addr < 0x5B00 else
                             'shadow' if 0xE000 <= addr < 0xF800 else
                             'colshadow' if 0xF800 <= addr < 0xFB00 else
                             'entity' if 0xFD80 <= addr < 0xFE00 else
                             'other')
                        buckets[k] = buckets.get(k, 0) + 1
                        pcs['%04X' % wpc] = pcs.get('%04X' % wpc, 0) + 1
                    h.memobj.unwatch()
                    done = True
            h.step(1)
        out['erase_' + name] = {'writes': total, 'buckets': buckets,
                                'writer_pcs': pcs}
    return out


# ------------------------------------------------------------------ phase C
def phase_panel():
    """$AB6D CALL $806C, the LIVES PANEL, converted from a named omission into
       a GATED NEGATIVE the HUD increment inherits.

       AND IT IS NOT SYMMETRIC.  $806C reads ($FD87) / ($FD91) and its shared
       tail $8097 is `RET p` -- it refuses to draw a player whose bit 7 is
       CLEAR.  $AB64 cleared P1's bit 7 two instructions earlier, so ON THE
       LAST LIFE THE DYING PLAYER'S OWN PANEL IS NOT REDRAWN."""
    out = {}
    for name, lives in (('last_life', 0x00), ('three_lives', 0x03)):
        h, m = new('bosshit')
        build_death(m, lives)
        frame = 0
        armed = False
        writes = []
        counts = {}
        done = False
        flags_at_panel = None
        # THE EXACT BRACKET is $AB6D CALL $806C to $AB70 POP IY.  (Harvesting
        # at $ABD4 measures ZERO: that is P2's RET; P1 leaves at $ABCB.)
        while frame < 12 and not done:
            reason, _ = h.run_until((ISR, PANEL_CALL, 0xAB70, PANEL, PANEL_TAIL),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frame += 1
            elif p == PANEL_CALL:
                flags_at_panel = [m[P1_FLAGS], m[P2_FLAGS]]
                h.memobj.watch(0x4000, 0x10000)
                armed = True
            elif p in (PANEL, PANEL_TAIL):
                counts['%04X' % p] = counts.get('%04X' % p, 0) + 1
            else:                                   # $AB70, the POP IY
                if armed:
                    for (wpc, addr, val) in h.memobj.log:
                        writes.append([wpc, addr, val])
                    h.memobj.unwatch()
                    done = True
            h.step(1)
        panel = sorted(set('%04X' % w[1] for w in writes
                           if 0x5000 <= w[1] < 0x5800))
        icons = sorted(set('%04X' % w[1] for w in writes
                           if 0x85B1 <= w[1] < 0x85B9))
        out[name] = {'counts': counts, 'writes': len(writes),
                     'panel_cells': panel, 'n_panel_cells': len(panel),
                     'icon_bytes': icons,
                     'writer_pcs': sorted(set('%04X' % w[0] for w in writes)),
                     'flags_at_panel': flags_at_panel,
                     'p1_flags': m[P1_FLAGS], 'p2_flags': m[P2_FLAGS]}
    return out


# ------------------------------------------------------------------ phase D
def phase_negatives():
    """The boss-round context as explicit rows, and every one of them driven on
       ROUND 50 as well -- because a negative measured only where the code is
       switched off is the absence of the code, not the presence of a rule."""
    out = {}
    for state in ('bosshit', 'r50_48'):
        h, m = new(state)
        rnd = m[ROUND]
        build_death(m, 0x00)
        m[0x8CB0] = 0xAA                       # poison: $AB7D writes 0
        seeds = {'8CB0': m[0x8CB0], 'FECA': m[FECA], '9160': m[HURRY_REQ],
                 'FED0': m[FED0], 'FED4': m[FED4],
                 '8E3B': m[LATCH_8E3B], '8ECF': m[LATCH_8ECF]}
        counts, events, log, frames = drive(
            h, m, 120, targets=(BUSYWAIT, KILLJP, KILLTAIL, WATCH, LATCH,
                                R80_LATCH, DEATH), watch=(0x4000, 0x10000))
        touched = {}
        for (wpc, addr, val) in log:
            if addr in (0x8CB0, FECA, HURRY_REQ, FED0, FED4,
                        LATCH_8E3B, LATCH_8ECF, OVER):
                k = '%04X' % addr
                touched.setdefault(k, []).append(['%04X' % wpc, val])
        out[state] = {
            'round': rnd, 'seeds': seeds, 'counts': counts, 'frames': frames,
            'writers': {k: sorted(set(w[0] for w in v))
                        for k, v in touched.items()},
            'write_counts': {k: len(v) for k, v in touched.items()},
            'after': {'8CB0': m[0x8CB0], 'FECA': m[FECA],
                      '9160': m[HURRY_REQ], 'FED0': m[FED0],
                      'FED4': m[FED4], '8E3B': m[LATCH_8E3B],
                      '8ECF': m[LATCH_8ECF]},
            'busywait_9573': counts.get('9573', 0),
            'kill_927D': counts.get('927D', 0)}
    return out


# ------------------------------------------------------------------ phase E
def phase_guard():
    """The two "equal answers" the plan names, each driven to its separating
       input.

       (1) "bit 2 of (IX+$5A) is the guard" vs "$927D is idempotent": with
           (IX+$5A) ALREADY $84, $927D still rewrites (IX+4) := $50.  The guard
           is $AA30's, not the routine's -- a port that guards internally gives
           the player a rolling death timer under a resting boss.
       (2) "the respawn's invulnerability protects against the boss" vs "the
           boss simply missed": park a respawned, bit-3 player ON the boss's
           tile.  No capture contains that."""
    out = {}
    h, m = new('bosshit')
    m[P1_STATE] = 0x84                        # already dying
    m[P1_TIMER] = 0x11                        # a value $927D overwrites
    r = h.sim.registers
    r[8], r[9] = P1 >> 8, P1 & 0xFF           # IXh, IXl  (TRAPS: IXh is 8)
    h.memobj.watch(0x4000, 0x10000)
    sp = 0x96DD
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = sent & 0xFF
        m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = KILLTAIL
    h.run_until(tuple(h.SENTINELS), limit=200000, stride=1, interrupts=False)
    writes = [['%04X' % p, '%04X' % a, v] for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    out['idempotent'] = {'state_before': 0x84, 'timer_before': 0x11,
                         'state_after': m[P1_STATE], 'timer_after': m[P1_TIMER],
                         'writes': writes[:16], 'n_writes': len(writes)}
    # (2) the respawn's bit 3, parked on the boss
    for name, state_byte in (('invulnerable', 0x88), ('vulnerable', 0x80)):
        h, m = new('bosshit')
        m[P1_STATE] = state_byte
        m[P1_X] = m[0xA8DB] * 8
        m[P1_Y] = m[0xA839] * 8
        m[P1_TIMER] = 0x11
        r = h.sim.registers
        r[8], r[9] = P1 >> 8, P1 & 0xFF
        sp = 0x96DD
        for sent in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp] = sent & 0xFF
            m[sp + 1] = sent >> 8
        r[SP] = sp
        r[PC] = KILLTAIL
        h.run_until(tuple(h.SENTINELS), limit=200000, stride=1,
                    interrupts=False)
        out[name] = {'state_before': state_byte, 'state_after': m[P1_STATE],
                     'timer_before': 0x11, 'timer_after': m[P1_TIMER],
                     'killed': m[P1_TIMER] == 0x50}
    return out


PHASES = [('chain', phase_chain), ('ab68', phase_ab68),
          ('panel', phase_panel), ('negatives', phase_negatives),
          ('guard', phase_guard)]

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
        print(json.dumps(fx[nm])[:1400], flush=True)
    if not only:
        json.dump(fx, open(FIXTURE, 'w'), indent=1, sort_keys=True)
        print('\nwrote', FIXTURE)
