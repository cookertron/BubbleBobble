"""B0 -- THE PASS CLOCK AND THE CHAIN SPINE ($8D0C-$8D70).

WHAT MAKES THIS GATEABLE AT ALL IS THAT THERE ARE **TWO MACHINES**, not one
world.  The main loop has no frame wait: it free-runs, and every divider in the
boss code counts PASSES, not frames.  On a single capture "the divider counts
frames" and "the divider counts passes" agree at 32/9.5 = 3.33 frames per body
fire and NOTHING separates them.  Run the SAME state with contention on and off
and the pass rate moves (9.633 -> 9.777 per frame on build/boss.pkl) while the
PASS interval stays exactly 32 in every interval of both runs.  That is the
only discriminator, so every table here is captured twice.

THREE MORE DEGENERACIES, each with its own countermeasure:

  - $A824's CP form ($A82C CP n / LD ($A82D),A) writes back THE VALUE IT JUST
    READ, so it is an EDGE DETECTOR on $8DBD -- but "write back a constant" and
    "write back what you read" are the same function while the timer is still.
    Driven with the timer MOVING, and the operand logged every pass.

  - $A9FC's SUB form ($A9FF SUB n / LD ($AA00),A) looks like the same idiom and
    is an INVOLUTION: op' = f - op, a 2-cycle, which LATCHES (RET z) only when
    the stored operand equals the frame byte.  From either shipped boss state it
    latches ZERO times in 300 frames, so a capture tests nothing at all.  The
    orbit is BUILT: seed $AA00 := mem[$8DBD] and the very next call latches.

  - "$7FFC fires once per 256 frames" and "once per 256 PASSES" differ by 9.5x
    and both look like "rarely".  Counted per frame AND per pass in the same run.

AND THE PLAN'S OWN NEGATIVE IS WRONG, WHICH IS WHY IT IS MEASURED HERE:
"there is no HALT and no frame wait in $8D0C..$8D70" is true of those 101 bytes
and false of the loop -- $7E80's subtree reaches $7EC2 EI / HALT, and on
build/boss.pkl frame 230 that costs the whole frame (1 pass, against a 6..12
spread).  A port whose pass loop can never block cannot reproduce it.

Usage:  python tools/passclock.py            (capture -> build/passclock_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc

FIXTURE = 'build/passclock_fixture.json'
LOOP_TOP = 0x8D25          # the first CALL of the 21-call chain
EI_TOP   = 0x8D0C          # the loop's real head
BRANCH_BYTE = 0x8DC4

# the chain, in the machine's order, read off $8D25..$8D5E
CHAIN = [0x8FA5, 0x8FE7, 0x900B, 0xA9ED, 0x9961, 0x915F, 0x948F, 0x7E80,
         0x93DC, 0x9E50, 0xA09A, 0xA824, 0xC002, 0x8669, 0x9037, 0x925A,
         0x931A, 0x9AEB, 0x8E2A, 0x8E3A]


def new(state='boss', contended=None):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def frames(h, n, watch, per_frame=None):
    """run n video frames, calling watch(pc, frame) before every instruction.

       It uses the harness's own _fast_halt: without it a HALT spins, and on
       build/boss.pkl past frame 230 the machine walks out of its own loop and
       ends up executing the score area at $FFF4.  That is a rig fault, not a
       finding, and it is why this helper exists instead of a hand-rolled loop.
    """
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    for f in range(n):
        tgt = regs[T] + fd
        while regs[T] < tgt:
            p = regs[PC]
            watch(p, f)
            if mem[p] == 0x76 and regs[IFF]:
                h._fast_halt()
                continue
            op[mem[p]]()
            if regs[IFF] and regs[T] % fd < ia:
                sim.accept_interrupt(regs, mem, p)
        if per_frame is not None:
            per_frame(f)


# ---------------------------------------------------------------- phase A
def phase_two_machines(nframes=900):
    """the SAME state on two machines.  A capture has ONE pass rate, so it
       cannot tell a pass divider from a frame divider; the contention toggle
       can, and nothing else here does."""
    out = {}
    for cont in (True, False):
        h, m = new('boss', cont)
        st = {'passes': 0, 'a9ed': 0, 'body_pass': [], 'body_frame': [],
              'a824': 0, 'a824_past': 0, 'ffc': [], 'halts': {},
              'fec8': [], 'a9fc': 0, 'aa05': 0, 'body_tick': []}
        per = []

        def watch(p, f, st=st, m=m):
            if p == LOOP_TOP:
                st['passes'] += 1
            elif p == 0xA9ED:
                st['a9ed'] += 1
            elif p == 0xAA0E:                       # the body: past $AA0D RET nz
                st['body_pass'].append(st['passes'])
                st['body_frame'].append(f)
                st['body_tick'].append(st['aa05'])
            elif p == 0xA824:
                st['a824'] += 1
            elif p == 0xA832:                       # past $A831 RET z -- an EDGE
                st['a824_past'] += 1
            elif p == 0x7FFC:
                st['ffc'].append((f, st['passes']))
            elif p == 0xA9FC:
                st['a9fc'] += 1
            elif p == 0xAA05:
                st['aa05'] += 1
            elif m[p] == 0x76:
                k = '$%04X' % p
                st['halts'][k] = st['halts'].get(k, 0) + 1

        def each(f, st=st, per=per, m=m, h=h):
            per.append(st['passes'])
            st['fec8'].append(m[0xFEC8])

        frames(h, nframes, watch, each)
        pf = [per[0]] + [per[i] - per[i - 1] for i in range(1, len(per))]
        bp, bf, bt = st['body_pass'], st['body_frame'], st['body_tick']
        pint = sorted(set(bp[i] - bp[i - 1] for i in range(1, len(bp))))
        tint = sorted(set(bt[i] - bt[i - 1] for i in range(1, len(bt))))
        fint = [bf[i] - bf[i - 1] for i in range(1, len(bf))]
        out['contended' if cont else 'uncontended'] = {
            'frames': nframes, 'passes': st['passes'],
            'passes_per_frame': round(st['passes'] / nframes, 4),
            'per_frame_min': min(pf), 'per_frame_max': max(pf),
            'per_frame_head': pf[:20],
            'per_frame_hist': {str(k): pf.count(k) for k in sorted(set(pf))},

            'a9ed_entries': st['a9ed'], 'body_fires': len(bp),
            'pass_intervals': pint, 'tick_intervals': tint,
            'frame_interval_mean': round(sum(fint) / len(fint), 3),
            'frame_interval_min': min(fint), 'frame_interval_max': max(fint),
            'a824_entries': st['a824'], 'a824_edges': st['a824_past'],
            'a824_edges_per_frame': round(st['a824_past'] / nframes, 4),
            'ffc_fires': len(st['ffc']), 'ffc_rows': st['ffc'][:12],
            'halts': st['halts'],
            'halt_frames': [i for i, n in enumerate(pf) if n <= 2],
            'a9fc_entries': st['a9fc'], 'aa05_entries': st['aa05'],
            'aa04_latches': st['a9fc'] - st['aa05'],
        }
        h = None
    return out




# ---------------------------------------------------------------- phase B
def phase_involution(nframes=40):
    """$A9FC LD A,($8DBD) / SUB n / LD (n),A / RET z -- the operand at $AA00 is
       the state, and op' = f - op is an INVOLUTION, not a divider.

       A DIVIDER and an INVOLUTION agree for 300 frames from either shipped boss
       state, because neither latches there at all.  The orbit is BUILT: seed
       $AA00 := mem[$8DBD] and the very next call must latch, and then every
       OTHER call while the frame byte holds still -- which is the opposite of a
       divider, whose period cannot be 2."""
    rows = {}
    for seeded in (True, False):
        h, m = new('boss', True)
        log, st = [], {'pend': None, 'passes': 0, 'armed': not seeded}

        def watch(p, f, m=m, log=log, st=st):
            if p == LOOP_TOP:
                st['passes'] += 1
            elif p == 0xA9FC:
                if not st['armed']:
                    # seed AT THE CALL, not before it: a poke one ISR earlier is
                    # stale by one and the orbit never contains zero at all.
                    m[0xAA00] = m[0x8DBD]
                    st['armed'] = True
                st['pend'] = [st['passes'], m[0x8DBD], m[0xAA00]]
            elif p == 0xAA04:
                if st['pend'] is not None:
                    st['pend'].append(m[0xAA00])
                    st['pend'].append(True)        # latched unless $AA05 follows
                    log.append(st['pend']); st['pend'] = None
            elif p == 0xAA05 and log:
                log[-1][-1] = False

        frames(h, nframes, watch)
        rows['seeded' if seeded else 'shipped'] = {
            'calls': len(log), 'latches': sum(1 for r in log if r[-1]),
            'head': log[:12],
            'first_latch_index': next((i for i, r in enumerate(log) if r[-1]), None),
            'latch_gaps': sorted(set(
                b - a for a, b in zip([i for i, r in enumerate(log) if r[-1]],
                                      [i for i, r in enumerate(log) if r[-1]][1:]))),
        }
    return rows


# ---------------------------------------------------------------- phase C
def phase_fecd(state='r20_48', pokes=(0, 1, 3), nframes=400):
    """$8D12: ($FECD) non-zero -> DEC, store, JR $8D09 -- a SECOND round-advance
       driver, one FULLY BUILT and immediately discarded round per count."""
    out = []
    for k in pokes:
        h, m = new(state, True)
        r0 = m[0x8609]
        m[0xFECD] = k
        n = {'adv': 0}
        frames(h, nframes, lambda p, f, n=n: n.__setitem__('adv', n['adv'] + (p == 0x97F8)))
        out.append({'poke': k, 'round_before': r0, 'round_after': m[0x8609],
                    'advanced': (m[0x8609] - r0) & 0xFF,
                    'x97f8_entries': n['adv'], 'fecd_after': m[0xFECD]})
    return out


# ---------------------------------------------------------------- phase D
def phase_returns(nframes=120):
    """the H9 method: at each chain entry read the return address off the stack
       and check it is the byte after that CALL.  It is the only check that
       survives a tail call, and it is what tells "the chain runs $A824" from
       "something else in the image also calls $A824"."""
    h, m = new('boss', True)
    site = {}
    addr = 0x8D25
    for a in CHAIN:
        site[a] = addr + 3
        addr += 3
    seen = {}

    def watch(p, f, m=m, h=h, site=site, seen=seen):
        if p in site:
            sp = h.sim.registers[SP]
            ret = m[sp] | (m[sp + 1] << 8)
            k = '$%04X' % p
            d = seen.setdefault(k, {'calls': 0, 'from_chain': 0, 'others': {}})
            d['calls'] += 1
            if ret == site[p]:
                d['from_chain'] += 1
            else:
                d['others']['$%04X' % ret] = d['others'].get('$%04X' % ret, 0) + 1

    frames(h, nframes, watch)
    return {'frames': nframes, 'sites': {'$%04X' % a: '$%04X' % site[a] for a in CHAIN},
            'seen': seen}


# ---------------------------------------------------------------- phase E
def phase_counters(nframes=200):
    """$8DB5 and $8DBC are each `LD HL,0` WHOSE OPERAND IS THE STORAGE:
       $8DB6-7 and $8DBD-E are incremented and written back into the very
       instruction that loaded them.  Both advance once per VIDEO FRAME while
       $FEC8 advances once per PASS, and a port that ties them together passes
       every single-counter gate ever written."""
    h, m = new('boss', True)
    st = {'passes': 0, 'x8db5': 0}
    rows = []

    def watch(p, f, st=st):
        if p == LOOP_TOP:
            st['passes'] += 1
        elif p == 0x8DB5:              # the ISR's CALL $8DB5 -- COUNTED, not sampled:
            st['x8db5'] += 1           #   a sampler straddles the interrupt and reports 201

    def each(f, m=m, st=st, rows=rows):
        rows.append([f, m[0x8DB6] | (m[0x8DB7] << 8), m[0x8DBD] | (m[0x8DBE] << 8),
                     m[0xFEC8], st['passes']])

    start = [m[0x8DB6] | (m[0x8DB7] << 8), m[0x8DBD] | (m[0x8DBE] << 8)]
    frames(h, nframes, watch, each)
    end = [m[0x8DB6] | (m[0x8DB7] << 8), m[0x8DBD] | (m[0x8DBE] << 8)]
    d1 = [rows[i][1] - rows[i - 1][1] for i in range(1, len(rows))]
    d2 = [rows[i][2] - rows[i - 1][2] for i in range(1, len(rows))]
    return {'frames': nframes, 'head': rows[:8], 'tail': rows[-3:],
            'x8db6_deltas': sorted(set(d1)), 'x8dbd_deltas': sorted(set(d2)),
            'x8db6_per_frame': len([d for d in d1 if d == 1]), 'samples': len(d1),
            'x8db5_calls': st['x8db5'],
            'x8db6_total': end[0] - start[0], 'x8dbd_total': end[1] - start[1],
            'passes': st['passes'],
            'passes_per_frame': round(st['passes'] / nframes, 4),
            'fec8_wraps': sum(1 for i in range(1, len(rows))
                              if rows[i][3] < rows[i - 1][3])}


# ---------------------------------------------------------------- phase F
def phase_exits():
    """TWO exits, not one.  $8D0D's game-over gate is the documented one; the
       loop ALSO ends at $8D63-$8D6F, which reads half-row $FE bit 0 (CAPS
       SHIFT) and half-row $7F bit 0 (SPACE) and RETs when BOTH are held --
       BREAK, returning through the same $8CDC that $8D05 pushed.  A port that
       models only the game-over exit is missing a way out of the game."""
    out = {}
    for name in ('gameover', 'break', 'control'):
        h, m = new('boss', True)
        if name == 'gameover':
            m[0xFEC9] = 1
        elif name == 'break':
            h.ports.press(0xFE, 0xFE)          # CAPS SHIFT
            h.ports.press(0x7F, 0xFE)          # SPACE
        r, n = h.run_until((0x8CDC,), limit=3_000_000, stride=1)
        out[name] = {'reached_8cdc': r == 'target', 'steps': n,
                     'pc': '$%04X' % h.regs[PC]}
    return out


# ---------------------------------------------------------------- phase G
def phase_hudattrs():
    """$7FFC, called from $8D22 CALL z,$7FFC on ($FEC8)'s EIGHT-BIT wrap -- the
       HUD attribute repaint.  Four runs written with INC L, so the walk is
       8-BIT and cannot leave page $5800."""
    h, m = new('boss', True)
    before = [m[0x5800 + i] for i in range(64)]
    for i in range(64):
        m[0x5800 + i] = 0x5A               # a value the routine does not write
    h.call(0x7FFC)
    after = [m[0x5800 + i] for i in range(64)]
    runs, i = [], 0
    while i < 64:
        j = i
        while j + 1 < 64 and after[j + 1] == after[i]:
            j += 1
        runs.append([i, j - i + 1, after[i]])
        i = j + 1
    return {'seed': 0x5A, 'before': before, 'after': after, 'runs': runs,
            'untouched': [i for i in range(64) if after[i] == 0x5A]}


# ---------------------------------------------------------------- phase H
def phase_sparkle_cleared(states=('round1_48', 'r20_48', 'boss')):
    """WHAT WIRING $C002 INTO THE CHAIN EXPOSED.

       $5CE0 -- the 14-slot burst-sparkle table -- is INSIDE the relocated block
       $5B00..$61A7, so a port that relocates and then builds a round without
       running the build's own clear has eleven live slots of sprite data sitting
       in it.  One pass of $C002 over that world writes 642 display bytes.

       On the machine the table is ZERO on every round state on disk, and the
       bubble pool carries (IY+3) = 2 -- which is $BF4B, one instruction inside
       the same $BF39 chain that clears the table at $BF53.  So the clear is not
       a patch for the symptom: it is a routine the port's reset was missing."""
    out = {}
    for st in states:
        h, m = new(st, True)
        out[st] = {
            'round': m[0x8609],
            'sparkle28': [m[0x5CE0 + i] for i in range(28)],
            'live_slots': sum(1 for i in range(14) if m[0x5CE0 + 2 * i] & 7),
            'pool_plus3': [m[0xFED8 + 10 * k + 3] for k in range(12)],
        }
    with open('build/image_tape.bin', 'rb') as f:
        img = f.read()
    # $5CE0 - $5B00 = $1E0, so the relocation SOURCE of the sparkle table is
    # $E1E0 -- 28 bytes of live sprite data that the build then clears.
    out['relocation_source'] = {'at_$E1E0': list(img[0xE1E0:0xE1E0 + 28])}
    return out


def main():
    fx = {
        'meta': {'state': 'boss (round $50)', 'note':
                 'every phase gets a FRESH harness: one phase inheriting '
                 "another's machine is how H12 grew an SP imbalance."},
        'chain': ['$%04X' % a for a in CHAIN],
        'two_machines': phase_two_machines(900),
        'involution': phase_involution(40),
        'fecd': phase_fecd('r20_48', (0, 1, 3), 400),
        'returns': phase_returns(120),
        'counters': phase_counters(200),
        'exits': phase_exits(),
        'hudattrs': phase_hudattrs(),
        'sparkle_cleared': phase_sparkle_cleared(),
    }
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    a = fx['two_machines']
    print('wrote', FIXTURE)
    for k in ('contended', 'uncontended'):
        v = a[k]
        print('%-12s %d frames -> %d passes (%.4f/frame), body fires %d, '
              'PASS intervals %s, TICK intervals %s, halts %s'
              % (k, v['frames'], v['passes'], v['passes_per_frame'],
                 v['body_fires'], v['pass_intervals'], v['tick_intervals'],
                 v['halts']))
    inv = fx['involution']
    print('involution: shipped %d calls / %d latches;  SEEDED %d calls / %d '
          'latches, first at %s, stride %s'
          % (inv['shipped']['calls'], inv['shipped']['latches'],
             inv['seeded']['calls'], inv['seeded']['latches'],
             inv['seeded']['first_latch_index'], inv['seeded']['latch_gaps']))
    print('$FECD:', [(r['poke'], r['advanced'], r['x97f8_entries']) for r in fx['fecd']])
    print('exits:', {k: (v['reached_8cdc'], v['steps']) for k, v in fx['exits'].items()})
    print('$7FFC runs:', fx['hudattrs']['runs'])
    for k, v in fx['sparkle_cleared'].items():
        if 'live_slots' in v:
            print('%-10s $5CE0 live slots %d, pool (IY+3) %s'
                  % (k, v['live_slots'], sorted(set(v['pool_plus3']))))


if __name__ == '__main__':
    main()
