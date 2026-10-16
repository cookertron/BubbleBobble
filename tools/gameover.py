"""B1 -- THE EXIT AND THE GAME LIFECYCLE ($8E2A, $8CDC, $96DF, $97D2).

WHY THE SHIPPED WORLDS CANNOT GATE THIS.  `$8E2A` is the only routine in the
chain that can END a game, and it ends it by finding bit 7 CLEAR in BOTH
`$FD87` and `$FD91`.  ALMOST every .pkl in build/ has P1's bit 7 SET -- **48 of
49**, and the docstring said "48 of 48" while the fixture this very tool writes
says `states` 49, `in_play` 48 and `both_clear` ['afterctrl48'].  A round number
in prose against a measurement in the same file, and the prose was wrong: there
IS one shipped counter-example.  The point stands for the other 48 --
`$8E36 LD ($FEC9),A` is unreachable from them, and a gate driven from any of them
is green on an engine that can never exit at all.
The world is BUILT: clear bit 7 of both, and run the ARMED case against a
CONTROL that clears neither.

AND `$FEC9` MUST BE SEEDED ZERO, NOT $B4.  Seeding it with the value `$8E34`
writes is TRAPS #44 exactly: the write becomes a no-op and "the trigger fired"
and "the trigger did nothing" are the same world.  Seeded 0, the write is
visible; and the COUNTDOWN is then driven separately by seeding `$FEC9` to
values the game itself never puts there, which is what separates "counts up to
the eight-bit wrap" from "waits 76 frames".

`$8CDC` is the game-over screen AND the game's own entry point: the HALT loop
runs until `INC ($FEC9)` wraps, and then FALLS THROUGH into `$8D02`, which
re-PUSHes `$8CDC` and CALLs `$96DF` -- the reset -- and `$97F8`.  So "game over"
and "start a game" are 38 bytes apart and share a routine.

M7.31'S PHASES STAND ON round1_48, AND THE REASON IS MEASURED: `title` has
$8E0A = $21 and $8DC4 = $F3 -- the TAPE bytes verbatim -- so $8CE2's CALL would
run code there instead of returning.  round1_48 has both at $C9.

AND `title` IS NOT A 128K CAPTURE, WHICH IS WHAT "not the 48K branch" IMPLIES AND
IS NOT WHAT IT IS.  It is PRE-$9690: the branch patcher has never run, which
`($FFE3)` = $38 shows -- not the 2 that $9692 stores -- and $96A5's $E000->$5B00
LDIR not having happened confirms.  `boot` is the same.  The states that really
took the 128K branch are afterctrl, crowd, play1p, play2p and round1.  The
distinction matters because "unpatched" and "128K" want different states as a
control.

$8CE2's CALL is not quite nothing either: 27 T and two stack writes, and `A = 5`
is dead because $802E opens with `LD A,(IX)`.  And there is a PROOF better than
any census that the 48K branch discards the game-over jingle -- $969A is
`LD A,$C9 / LD ($8DC4),A / LD ($8E05),A / LD ($8E0A),A`, three straight-line
stores past one `JR z`, so on 48K this screen is SILENT.

Usage:  python tools/gameover.py       (capture -> build/gameover_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, IXh, IXl
import portconfig as pc

FIXTURE = 'build/gameover_fixture.json'
BRANCH_BYTE = 0x8DC4
OVER = 0x8CDC           # the game-over screen, and $8D02 is the game entry
TRIG = 0x8E2A           # the chain's last-but-one call
RESET = 0x96DF
P1F, P2F = 0xFD87, 0xFD91
FEC9 = 0xFEC9


def new(state, contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def frames(h, n, watch=None, per_frame=None):
    sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    for f in range(n):
        tgt = regs[T] + fd
        while regs[T] < tgt:
            p = regs[PC]
            if watch is not None and watch(p, f):
                return f
            if mem[p] == 0x76 and regs[IFF]:
                h._fast_halt()
                continue
            op[mem[p]]()
            if regs[IFF] and regs[T] % fd < ia:
                sim.accept_interrupt(regs, mem, p)
        if per_frame is not None:
            per_frame(f)
    return None


# ---------------------------------------------------------------- phase A
def phase_trigger(states=('boss', 'round1_48', 'play1p48'), limit=2000):
    """ARMED against CONTROL.  Armed: bit 7 cleared in BOTH player flag bytes.
       Control: the shipped world, untouched.  $FEC9 seeded 0 in both."""
    out = []
    for st in states:
        for armed in (True, False):
            h, m = new(st)
            m[FEC9] = 0
            if armed:
                m[P1F] &= 0x7F
                m[P2F] &= 0x7F
            hit = {'f': None, 'sp': None, 'stacked': None, 'fec9_at_trigger': None}

            def watch(p, f, h=h, m=m, hit=hit):
                if p == 0x8E36 and hit['fec9_at_trigger'] is None:
                    hit['fec9_at_trigger'] = m[FEC9]
                if p == OVER:
                    sp = h.sim.registers[SP]
                    hit['f'] = f
                    hit['sp'] = sp
                    hit['stacked'] = m[sp - 2] | (m[sp - 1] << 8)
                    return True
                return False

            frames(h, limit, watch)
            out.append({'state': st, 'armed': armed,
                        'p1_bit7': bool(m[P1F] & 0x80), 'p2_bit7': bool(m[P2F] & 0x80),
                        'reached_8cdc': hit['f'] is not None, 'frames': hit['f'],
                        'sp': hit['sp'], 'sp_hex': hit['sp'] and '$%04X' % hit['sp'],
                        'word_below_sp': hit['stacked'],
                        'fec9_seen_at_trigger': hit['fec9_at_trigger'],
                        'fec9_now': m[FEC9], 'limit': limit})
    return out


def phase_inplay_census():
    """the reason phase A builds its world: 48 of 48 shipped states have a
       player in play, so $8E36 is unreachable from every one of them."""
    import glob, os
    rows, n, live = [], 0, 0
    for f in sorted(glob.glob('build/*.pkl')):
        st = os.path.basename(f)[:-4]
        h = Harness()
        try:
            h.load_state_file(f)
        except Exception:
            continue
        m = h.memobj.m
        if m[BRANCH_BYTE] != 0xC9:
            continue
        n += 1
        inplay = bool((m[P1F] | m[P2F]) & 0x80)
        live += 1 if inplay else 0
        rows.append([st, m[0x8609], m[P1F], m[P2F], inplay])
    return {'states': n, 'in_play': live,
            'both_clear': [r[0] for r in rows if not r[4]], 'rows': rows}


# ---------------------------------------------------------------- phase B
def phase_countdown(seeds=(0xB4, 0xFF, 0x80, 0x01, 0x40)):
    """$8CFB HALT / $8CFC INC ($FEC9) / $8D00 JR nz: the screen holds until the
       counter WRAPS, so the wait is 256 - n frames and $B4's 76 is one row of
       that table, not the rule."""
    out = []
    for seed in seeds:
        h, m = new('round1_48')
        m[P1F] &= 0x7F
        m[P2F] &= 0x7F
        m[FEC9] = 0
        frames(h, 2000, lambda p, f: p == OVER)
        m[FEC9] = seed                      # re-seed AT the screen
        st = {'halts': 0, 'left': None}

        def watch(p, f, st=st):
            if p == 0x8CFB:
                st['halts'] += 1
            elif p == 0x8D02:
                st['left'] = st['halts']
                return True
            return False

        frames(h, 600, watch)
        out.append({'seed': seed, 'halts': st['left'], 'expected': 256 - seed})
    return out


# ---------------------------------------------------------------- phase C
def phase_screen():
    """what the screen loop actually writes, logged rather than assumed: the
       glyph run at $484C and the attribute run at $594C."""
    h, m = new('round1_48')
    m[P1F] &= 0x7F
    m[P2F] &= 0x7F
    m[FEC9] = 0
    frames(h, 2000, lambda p, f: p == OVER)
    before = bytes(m[0x4000:0x5B00])
    m[FEC9] = 0xFE                          # two iterations, then out
    #  *** THE WRITE LOG HERE WAS DEAD AND SAID NOTHING. ***  `hasattr(m2,
    #  'writes')` is False -- harness.Mem carries `log`, not `writes` -- so this
    #  collected [] on every run, returned it to nobody, and the watch/unwatch
    #  pair cost appends for a list that was never read.  Removed rather than
    #  fixed: what this phase is for is the CHANGED-CELL diff below, and the
    #  per-write record belongs to phase_glyphs, which watches $8052.
    frames(h, 40, lambda p, f: p == 0x8D02)
    after = bytes(m[0x4000:0x5B00])
    diff = [0x4000 + i for i in range(len(before)) if before[i] != after[i]]
    attrs = {'$%04X' % a: m[a] for a in range(0x594C, 0x5955)}
    return {'changed_cells': len(diff),
            'bitmap_changed': len([a for a in diff if a < 0x5800]),
            'attr_changed': ['$%04X' % a for a in diff if a >= 0x5800],
            'attr_values': attrs,
            'first': ['$%04X' % a for a in diff[:8]]}


# ---------------------------------------------------------------- phase D
def phase_reset():
    """$96DF's reset half, over a world seeded to values it does NOT write, so
       that every store is VISIBLE (TRAPS #44) -- including the twelve-byte
       clear from $FFE5, whose whole point is that the HIGH SCORE at
       $FFE1..$FFE4 is OUTSIDE it."""
    h, m = new('round1_48')
    seeds = {0xFDE3: 0x5A, 0xFDED: 0x5A, FEC9: 0x5A, 0x8DBD: 0x5A, 0x8DBE: 0x5A,
             0xFEC4: 0x5A, 0xFEC5: 0x5A, 0x8609: 0x5A, 0x83EC: 0x5A, 0x82D7: 0x5A,
             0x8A76: 0x5A, 0xFED3: 0x5A, 0xFED4: 0x5A}
    for a, v in seeds.items():
        m[a] = v
    for i in range(16):                      # $FFE1..$FFF0: scores and beyond
        m[0xFFE1 + i] = 0xA0 + i
    before = {'$%04X' % a: m[a] for a in sorted(seeds)}
    hi = [m[0xFFE1 + i] for i in range(4)]
    h.sim.registers[SP] = 0x96DD
    h.call(RESET, limit=200000)
    after = {'$%04X' % a: m[a] for a in sorted(seeds)}
    return {'seeded': before, 'after': after,
            'high_before': hi, 'high_after': [m[0xFFE1 + i] for i in range(4)],
            'scores_after': [m[0xFFE5 + i] for i in range(12)],
            'beyond': [m[0xFFF1 + i] for i in range(0)],
            'fed4_untouched': m[0xFED4] == 0x5A}


# ---------------------------------------------------------------- phase E
def phase_title_cls():
    """$97EB -- THE TITLE SCREEN'S CLS, and the 185-byte gap the port skips.

        $970B  LD ($FED3),A     <- where the port's gameReset() stopped (before M7.42)
        $970E  EI
        $970F  CALL $97EB       <- a CALL, so $97EB RETURNS and $96DF continues
        ...
        $97EB  LD HL,$4000 / LD DE,$4001 / LD BC,$1AFF / LD (HL),L / LDIR / RET

    Until M7.42 the port's gameReset() modelled $96DF..$970B and then called
    playersInit(), which is $97C7/$97D2 -- so it JUMPED FROM $970B TO $97C7 and skipped
    $970E..$97C6: the EI, this CLS, the starfield, the four strings, the credit line, the
    sparkle ring and the key wait.  185 bytes.  This phase closed the first of them;
    M7.41 and M7.42 closed the rest.

    THE COUNT IS 6,912, NOT 6,911.  BC=$1AFF is 6,911 LDIR copies PLUS the `LD (HL),L`
    that seeds the first byte; $4000..$5AFF inclusive.  Two of M7.37's seven sub-blocks
    disagreed about exactly this, and $5AFF is the credit line's ninth attribute cell,
    which the port's creditLine() gate already asserts -- so a port clearing to $5AFE
    leaves the brightest cell on the screen dirty and tests over a dirty world.

    THE FILL VALUE IS L, NOT AN IMMEDIATE, AND THAT IS DRIVEN rather than read off the
    opcode: patch $97EC/$97ED (the operand of `LD HL,$4000`) to $40xx and the byte
    written at the new start comes back as $xx.  A port with `= 0` hard-coded passes an
    opcode check and fails this one.

    The state is round1_48, not title: $97EB reads no state, and gameover.py's new()
    guards m[$8DC4] == $C9, which title.pkl FAILS ($F3) because it is captured before
    $95F3 applies the RET patches.
    """
    h, m = new('round1_48')
    #  poison PAST the end, so "it stopped in the right place" is observable
    for a in range(0x4000, 0x5C00):
        m[a] = 0xAA
    h.memobj.watch(0x4000, 0x5C00)
    h.sim.registers[SP] = 0x96DD
    h.call(0x97EB, limit=200000)
    writes = [(a, v) for (_p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    zeroed = [a for a in range(0x4000, 0x5C00) if m[a] == 0]
    lo, hi = min(zeroed), max(zeroed)

    #  ---- the fill value FOLLOWS L, driven three ways -------------------------
    follows = []
    for low in (0x00, 0x05, 0x7E):
        g, mm = new('round1_48')
        for a in range(0x4000, 0x5C00):
            mm[a] = 0xAA
        mm[0x97EC] = low                    # the operand of LD HL,$4000 -> $40xx
        g.sim.registers[SP] = 0x96DD
        g.call(0x97EB, limit=200000)
        #  *** THE SEED CELL IS ITSELF OVERWRITTEN. ***  DE trails HL by only 4, so
        #  four LDIR steps later the copy writes over the byte `LD (HL),L` has just
        #  seeded.  My first version read $4000+L, saw the poison come back, and that
        #  looked like a refutation of the claim when it was a wrong probe address.
        #  The witness is the FIRST DESTINATION, $4001 -- the value L wrote, carried
        #  there by the first copy.
        follows.append({'L': low, 'written_at_first_dest': mm[0x4001],
                        'seed_cell_clobbered': mm[0x4000 + low] != low})

    out = {'n_zeroed': len(zeroed), 'lo': '%04X' % lo, 'hi': '%04X' % hi,
           'contiguous': (hi - lo + 1) == len(zeroed),
           'past_end': '%02X' % m[0x5B00],
           'n_writes': len(writes),
           'first_write_at': '%04X' % writes[0][0],
           'ldir_copies': 0x1AFF,
           'opcode_97F4': '%02X' % m[0x97F4],
           'opcode_970F': '%02X' % m[0x970F],
           'opcode_97F7': '%02X' % m[0x97F7],
           'fill_follows_L': follows,
           'gap_lo': '970E', 'gap_hi': '97C6', 'gap_bytes': 0x97C7 - 0x970E}
    print('$97EB -- the title screen\'s CLS')
    print('    %d bytes zeroed, $%s..$%s, contiguous %s; $5B00 left $%s'
          % (out['n_zeroed'], out['lo'], out['hi'], out['contiguous'], out['past_end']))
    print('    %d writes = 1 (LD (HL),L, opcode $%s) + %d (LDIR, BC=$1AFF); first at $%s'
          % (out['n_writes'], out['opcode_97F4'], out['ldir_copies'],
             out['first_write_at']))
    print('    the fill value FOLLOWS L, witnessed at the FIRST DESTINATION $4001: %s'
          % ', '.join('L=$%02X -> $%02X' % (f['L'], f['written_at_first_dest'])
                      for f in follows))
    print('    $970F opcode $%s (CD = CALL, so $97EB returns), $97F7 $%s (C9 = RET)'
          % (out['opcode_970F'], out['opcode_97F7']))
    print('    -> the port\'s gameReset() skips $%s..$%s, %d bytes'
          % (out['gap_lo'], out['gap_hi'], out['gap_bytes']))
    assert out['n_zeroed'] == 6912, 'not 6,912 bytes: %d' % out['n_zeroed']
    assert lo == 0x4000 and hi == 0x5AFF, 'wrong range $%04X..$%04X' % (lo, hi)
    assert out['contiguous'], 'the cleared range is not contiguous'
    assert m[0x5B00] == 0xAA, '$5B00 was touched'
    assert out['n_writes'] == 1 + 0x1AFF, 'not 1 + 6,911 writes: %d' % out['n_writes']
    assert m[0x97F4] == 0x75, '$97F4 is not LD (HL),L: $%02X' % m[0x97F4]
    assert m[0x970F] == 0xCD, '$970F is not a CALL: $%02X' % m[0x970F]
    assert m[0x97F7] == 0xC9, '$97F7 is not a RET'
    for f in follows:
        assert f['written_at_first_dest'] == f['L'], \
            'the fill value did NOT follow L: L=$%02X carried $%02X' \
            % (f['L'], f['written_at_first_dest'])
    return out




# ============================================================================ phase G
#  $8CC3 / $95F3 -- THE COLD START, increment G (M7.40).
#
#  Landed from the pre-mortem agent's phase_cold_start_pre(), whose thirteen gate rows
#  read exactly these keys.  The oracle agent's longer phase (scratchpad/recon/
#  zzg_oracle_phase.py, 218 asserts) is kept there as the research record, NOT shipped:
#  one measurement, one spelling (TRAPS #202).
#
#  NO ROM BYTES.  $D167..$D18F -- the 128K music driver -- is never entered, read or
#  reported: step_to() asserts a PC guard over it on every instruction.
from harness import A as RA, B as RB, C as RC, H as RH, L as RL

CS_POISON = 0x5A
CS_PATCH = (0x8DC4, 0x8E05, 0x8E0A)
CS_GUARD_LO, CS_GUARD_HI = 0xD167, 0xD190
CS_CALLS = (0x4000, 0x4800, 0x5000, 0x0000)
CS_PORT_KEYTAB = [0xDF, 0x02, 0xDF, 0x01, 0xFB, 0x01, 0x7F, 0x01,
               0xEF, 0x10, 0xEF, 0x08, 0xEF, 0x02, 0xEF, 0x01]
CS_PORT_ROW1 = '      00   000200000       00'


def phase_cold_start():
    def world(state='title', a=0x30, sp=0x96DD, entry=0x8CC3, phase=0):
        h = Harness(contended=True)
        h.load_state_file(pc.state_path(state))
        m, r = h.memobj.m, h.sim.registers
        r[SP], r[PC], r[RA] = sp, entry, a
        r[RH], r[RL] = 0xF5, 0xD2
        if phase:
            r[T] = (r[T] + phase) % h.frame_duration
        return h, m, r

    def step_to(h, stops, limit=4000000):
        r, op, mem = h.sim.registers, h.sim.opcodes, h.sim.memory
        n, t0, stops = 0, r[T], set(stops)
        while n < limit:
            p = r[PC]
            if p in stops:
                return p, n, r[T] - t0
            assert not (CS_GUARD_LO <= p < CS_GUARD_HI), 'ENTERED THE GUARDED RANGE'
            op[mem[p]]()
            n += 1
        return None, n, r[T] - t0

    def poison(m):
        for a in CS_PATCH:
            m[a] = CS_POISON
        for i in range(0x6A8 + 4):
            m[0x5B00 + i] = CS_POISON
        for i in range(0x13):
            m[0xFFE1 + i] = CS_POISON
        for i in range(0x14):
            m[0xB5FD + i] = CS_POISON

    OUT = {}

    # ---------------- the 48K leg, and every byte the rows read from it -------
    h, m, r = world()
    assert m[0x8DC4] != 0xC9, 'title.pkl is already patched -- TRAPS #44'
    patch_tape = [m[a] for a in CS_PATCH]
    tape_row1 = ''.join(chr(m[0x85DE + i]) for i in range(29))
    selfmod = [m[0x7581 + i] for i in range(16)]
    poison(m)
    step_to(h, {0x8CC7})
    h.memobj.watch(0x4000, 0x10000)
    stop, n48, t48 = step_to(h, {0x8CCA})
    log48 = list(h.memobj.log)
    h.memobj.unwatch()
    assert stop == 0x8CCA and n48 == 3322 and len(log48) == 2440, (stop, n48, len(log48))

    tab = [m[0xFD00 + i] for i in range(128)]
    words = [tab[2 * i] | (tab[2 * i + 1] << 8) for i in range(64)]
    OUT['rowtab'] = words
    OUT['rowtab_raw'] = [w for w in words[:32]]
    OUT['rowtab_raw'][0] = CS_CALLS[0]                 # $967F's overwrite undone, so the
    OUT['rowtab_raw'][1] = CS_CALLS[0] | 0x20          #   +$A000 identity is checkable
    OUT['patch_tape'] = patch_tape
    OUT['patch_after'] = [m[a] for a in CS_PATCH]
    OUT['high'] = {'ffe1_16': [m[0xFFE1 + i] for i in range(16)],
                   'poison_past': [m[0xFFF1 + i] for i in range(3)],
                   #  COMPUTED (they were typed): the four BCD bytes little-endian,
                   #  and x10 because $7FC0 writes eight digits and the template's
                   #  ninth, $85F1, is '0' -- asserted below, not assumed
                   'stored': int(''.join('%02X' % m[0xFFE4 - i] for i in range(4))),
                   'displayed': 10 * int(''.join('%02X' % m[0xFFE4 - i] for i in range(4)))}
    assert m[0x85F1] == 0x30, 'the ninth HUD digit is not the template 0'
    assert OUT['high']['stored'] == 20000, OUT['high']['stored']
    OUT['clears'] = {'fec4_18': [m[0xFEC4 + i] for i in range(18)],
                     'fed6_past': [m[0xFED6 + i] for i in range(4)],
                     'b_at_968B': 0x10, 'b_at_9613': 0x12, 'bc_at_963E': 0x0080,
                     'iters_963E': 256,
                     'fd80_all_zero': all(m[0xFD80 + i] == 0 for i in range(128))}
    im2w = [(p2, a) for p2, a, _ in log48 if 0xFC00 <= a <= 0xFD00]
    OUT['im2'] = {'fc00_fcff_all_FF': all(m[a] == 0xFF for a in range(0xFC00, 0xFD00)),
                  'n_bytes': len({a for _, a in im2w}),
                  'writers': sorted({'$%04X' % p2 for p2, a in im2w
                                     if p2 in (0x9621, 0x9623)}),
                  'n_writes_9621': sum(1 for p2, _ in im2w if p2 == 0x9621),
                  'n_writes_9623': sum(1 for p2, _ in im2w if p2 == 0x9623),
                  'the_257th_is_unobservable':
                      'FD00 ends $FF whether the fill is 256 or 257, because $9641 '
                      'zeroes it and $967F writes $01FF back -- assert the CENSUS',
                  'fd00_03': [m[0xFD00 + i] for i in range(4)],
                  'ffff': m[0xFFFF], 'fff4_6': [m[0xFFF4 + i] for i in range(3)],
                  'handler': m[0xFFF5] | (m[0xFFF6] << 8)}
    OUT['selfmod'] = {'payload': selfmod,
                      'dst_after': [m[0x95F3 + i] for i in range(16)],
                      'src_unchanged': [m[0x7581 + i] for i in range(16)] == selfmod,
                      'next_operands_intact': [m[0x9603 + i] for i in range(6)]}
    OUT['template'] = {'row1_tape': tape_row1, 'row1_port': CS_PORT_ROW1,
                       'row0_tape': ''.join(chr(m[0x85C1 + i]) for i in range(28)),
                       'nine_tape': ''.join(chr(m[0x85E9 + i]) for i in range(9)),
                       'byte_85F1': m[0x85F1],
                       'port_row1_matches_tape': CS_PORT_ROW1 == tape_row1}
    OUT['write_runs'] = []
    seen = sorted({a for _, a, _ in log48})
    i = 0
    while i < len(seen):
        j = i
        while j + 1 < len(seen) and seen[j + 1] == seen[j] + 1:
            j += 1
        OUT['write_runs'].append(['$%04X..$%04X' % (seen[i], seen[j]),
                                  seen[j] - seen[i] + 1])
        i = j + 1

    # ---- M7.40 pre-commit review: everything the fix rows need, MEASURED -----------
    #  per-run WRITE counts (write_runs holds distinct addresses; a run written twice,
    #  like $FD00, counts every store)
    OUT['write_counts'] = {}
    for run, _n in OUT['write_runs']:
        lo, hi = int(run[1:5], 16), int(run[8:12], 16)
        OUT['write_counts'][run] = sum(1 for _p, a, _v in log48 if lo <= a <= hi)
    #  the IM 2 window: stores into $FC00..$FD00 BEFORE the first $FFFF store -- the one
    #  count that sees the 257th write, which $9641/$9662/$967F all overwrite later
    first_ffff = next(k for k, (_p, a, _v) in enumerate(log48) if a == 0xFFFF)
    OUT['im2_window_before_FFFF'] = sum(1 for _p, a, _v in log48[:first_ffff]
                                        if 0xFC00 <= a <= 0xFD00)
    assert OUT['im2_window_before_FFFF'] == 257, OUT['im2_window_before_FFFF']
    #  the three $AA49 clears, counted by their STORE's PC -- these were typed
    def aa4a(lo, hi):
        return sum(1 for p2, a, _v in log48 if p2 == 0xAA4A and lo <= a <= hi)
    OUT['clears']['aa4a_fec4'] = aa4a(0xFEC4, 0xFED5)
    OUT['clears']['aa4a_fd00'] = aa4a(0xFD00, 0xFDFF)
    OUT['clears']['aa4a_ffe1'] = aa4a(0xFFE1, 0xFFF0)
    assert (OUT['clears']['aa4a_fec4'], OUT['clears']['aa4a_fd00'],
            OUT['clears']['aa4a_ffe1']) == (18, 256, 16), OUT['clears']
    OUT['clears']['iters_963E'] = OUT['clears']['aa4a_fd00']   # was typed 256

    #  an UNPOISONED drive for BANKM: the main drive poisons $5B00.. and so cannot say
    #  what $9AE7 really receives.  $95F5 reads $5B5C BEFORE $96A5 relocates over it.
    hu, mu, ru = world()
    b5c_before = mu[0x5B5C]
    OUT['f5cc_bytes'] = [mu[0xF5CC + i] for i in range(3)]      # LD HL,$F5D2
    step_to(hu, {0x8CCA})
    OUT['bankm'] = {'5B5C_before': b5c_before, '9AE7_after': mu[0x9AE7],
                    '5B5C_after': mu[0x5B5C]}
    assert OUT['bankm']['9AE7_after'] == b5c_before, OUT['bankm']
    assert OUT['bankm']['5B5C_after'] != b5c_before, 'the order would be invisible'
    assert OUT['f5cc_bytes'][0] == 0x21, OUT['f5cc_bytes']

    keytab_mine = [m[0xB5FD + i] for i in range(16)]

    # ---------------- the two legs, side by side -----------------------------
    OUT['branch'] = {}
    for a_in, key in ((0x30, '48'), (0x80, '128')):
        g, mg, rg = world(a=a_in)
        poison(mg)
        step_to(g, {0x8CC7})
        g.memobj.watch(0x4000, 0x10000)
        st, nn, tt = step_to(g, {0x8CCA, 0x96B3}, limit=400000)
        lg = list(g.memobj.log)
        g.memobj.unwatch()
        OUT['branch'][key] = {
            'A_in': a_in, 'stopped_at': '$%04X' % st, 'instr': nn, 'writes': len(lg),
            'patch_after': [mg[p] for p in CS_PATCH], 'ffe3': mg[0xFFE3],
            'display_writes': sum(1 for _, ad, _ in lg if 0x4000 <= ad < 0x5B00),
            'writers_of_patch': sorted({'$%04X' % p2 for p2, ad, _ in lg if ad in CS_PATCH}),
            'A_at_stop': rg[RA]}
    b48, b128 = OUT['branch']['48'], OUT['branch']['128']
    assert b48['instr'] - b128['instr'] == 4, 'the patch is 4 instructions'
    assert b48['writes'] - b128['writes'] == 3, 'the patch is 3 writes'

    # ---------------- the T-state spread, sixteen phases ---------------------
    phases = []
    for k in range(16):
        g, mg, rg = world(phase=k * (69888 // 16))
        poison(mg)
        step_to(g, {0x8CC7})
        g.memobj.watch(0x4000, 0x10000)
        _, nn, tt = step_to(g, {0x8CCA}, limit=400000)
        w = len(g.memobj.log)
        g.memobj.unwatch()
        phases.append({'phase_T': k * (69888 // 16), 'instr': nn, 'writes': w,
                       'tstates': tt})
    ts = [p['tstates'] for p in phases]
    OUT['tstates'] = {'phases': phases, 'min': min(ts), 'max': max(ts),
                      'spread': max(ts) - min(ts),
                      'spread_pct': round(100.0 * (max(ts) - min(ts)) / min(ts), 1),
                      'instr_constant': len({p['instr'] for p in phases}) == 1,
                      'writes_constant': len({p['writes'] for p in phases}) == 1,
                      'instr': phases[0]['instr'], 'writes': phases[0]['writes'],
                      'uncontended_note': 'contended=True throughout; the fixture '
                                          'records the RANGE, never one drive'}

    # ---------------- $9575, body and call, and its ONE call site ------------
    g, mg, rg = world()
    step_to(g, {0x8CD0})
    b_in, a_in2 = rg[RB], rg[RA]
    step_to(g, {0x8CD2})
    _, n_call, t_call = step_to(g, {0x8CD5})
    # the BODY alone: enter at $9575 with a sentinel return address on the stack
    g2, mg2, rg2 = world()
    step_to(g2, {0x8CD2})
    sent = 0xFFFE
    rg2[SP] = (rg2[SP] - 2) & 0xFFFF
    mg2[rg2[SP]] = 0x00
    mg2[rg2[SP] + 1] = 0x10                        # return to $1000, a stop we choose
    rg2[PC] = 0x9575
    _, n_body, t_body = step_to(g2, {0x1000}, limit=400000)
    img = bytes(mg[0x0000:0x10000])
    sites = ['$%04X' % (a - 1) for a in range(0x4000, 0xFFFF)
             if img[a] == 0x75 and img[a + 1] == 0x95 and img[a - 1] == 0xCD]
    OUT['delay'] = {'with_call': t_call, 'body': t_body, 'instr_with_call': n_call,
                    'instr_body': n_body, 'B_at_entry': b_in, 'A_at_entry': a_in2,
                    'C_at_entry': 1, 'call_sites': sites,
                    'B_zero_means_256': b_in == 0}
    assert t_call == 10050, t_call
    assert t_call - t_body == 17, (t_call, t_body)
    assert sites == ['$8CD2'], sites

    # ---------------- the SP order, as a mechanism ---------------------------
    g, mg, rg = world(sp=0x61A7, entry=0x8CC7)
    poison(mg)
    g.memobj.watch(0x4000, 0x10000)
    st, nn, tt = step_to(g, {0x8CCA}, limit=400000)
    lg = list(g.memobj.log)
    g.memobj.unwatch()
    stackw = sorted({'$%04X' % ad for p2, ad, _ in lg
                     if 0x5B00 <= ad <= 0x61A7 and p2 in (0x95F3, 0x9662, 0xAA49)})
    OUT['sp_order'] = {
        'incoming_sp': '$61A7', 'dst': '$5B00..$61A7',
        'incoming_sp_is_last_byte_of_dst': True,
        'without_ld_sp': {'reached': st == 0x8CCA, 'runaway_pc': '$%04X' % rg[PC],
                          'instr': nn,
                          'stack_writes_in_dst': stackw,
                          'popped_from_source':
                              [mg[0x61A5], mg[0x61A6]] == [mg[0xE6A5], mg[0xE6A6]]},
        'with_ld_sp': {'reached': True, 'instr': 3322, 'sp_after': '$96DD',
                       'stack_writes': '$96D9..$96DC'}}
    assert OUT['sp_order']['without_ld_sp']['reached'] is False

    # ---------------- the key table: FOUR worlds, FOUR answers ---------------
    afterctrl = None
    try:
        hh = Harness(contended=True)
        hh.load_state_file(pc.state_path('afterctrl48'))
        afterctrl = [hh.memobj.m[0xB5FD + i] for i in range(16)]
    except Exception:
        afterctrl = None
    OUT['keytab'] = {
        'bc': 0x10, 'dst': '$B5FD', 'src_is_a_live_parameter': True,
        'no_LD_HL_nn_in_95F3_9602': True,
        'worlds': {
            'before the control-select menus (title.pkl, MINE)': keytab_mine,
            "the oracle's boot drive, keys '2' and '4'":
                [239, 16, 239, 8, 239, 2, 239, 1, 247, 16, 239, 4, 239, 1, 239, 8],
            'afterctrl48': afterctrl,
            "the port's BB_KEYTAB (image.bin defaults)": CS_PORT_KEYTAB}}

    # ---------------- $9662's two 8-bit adds --------------------------------
    def b8(hl):
        lo, hi, out = hl & 0xFF, hl >> 8, []
        for _ in range(8):
            out.append((((hi) << 8) | lo, (((hi + 0xA0) & 0xFF) << 8) | lo))
            lo = (lo + 0x20) & 0xFF
        return out

    def b16(hl):
        out = []
        for _ in range(8):
            out.append((hl & 0xFFFF, (hl + 0xA000) & 0xFFFF))
            hl = (hl + 0x20) & 0xFFFF
        return out

    OUT['sep_high_bytes'] = len([h2 for h2 in range(0, 0x10000, 0x100)
                                 if b8(h2) != b16(h2)])
    OUT['sep_low_bytes'] = len([l for l in range(0x100)
                                if b8(0x4000 | l) != b16(0x4000 | l)])
    OUT['agree_on_the_four_operands'] = all(b8(c) == b16(c) for c in CS_CALLS)
    assert OUT['sep_high_bytes'] == 0 and OUT['sep_low_bytes'] == 224
    assert OUT['agree_on_the_four_operands'] is True
    assert OUT['im2']['n_bytes'] == 257, OUT['im2']['n_bytes']
    assert OUT['im2']['n_writes_9621'] == 1 and OUT['im2']['n_writes_9623'] == 256
    return OUT


# ============================================================================ group 1
#  $970F..$9764 -- THE TITLE SCREEN'S STRAIGHT-LINE PAINT, GROUP 1 (M7.41 oracle).
#
#  ONE drive of the machine from $970F to $9765 with interrupts OFF, the CLS included
#  ($970F is CALL $97EB), bracketed at $9729 (snapshot A: CLS + starfield) and $9765
#  (snapshot B: + four double-height strings + the credit line).  Every write is logged
#  and keyed on the SOURCE PC of the writing instruction (TRAPS #200), which this phase
#  tags itself and cross-checks against the harness's own log PC.
#
#  THE R PHASE IS PINNED, CHOSEN TO MATCH THE RECON.  The recon's 820 / 940 / 120
#  numbers (zzv_critic_report 4.10, zzv_bwalk_report) were driven from $9712 on title.pkl
#  with its CAPTURED R, which is 111 there.  $970F..$9711 (the CLS: 6,911 LDIR steps)
#  advances R by +4 mod 128, MEASURED (r0 = 0 -> R = 4 at $9712; 111 -> 115).  So
#  TP_R0 = 107 puts R = 111 at $9712 and this drive stands on the same starfield the
#  recon counted.  A different r0 is a different one of the 128 starfields (838 / 834 /
#  829 lit for r0 = 0 / 42 / 111, measured) -- the counts are phase facts, not constants.
#
#  NO ROM BYTES.  The display file at $9765 holds the credit line's single-height glyphs,
#  which are the ROM character set copied verbatim, so it is recorded as a SHA-256 digest
#  and counts, NOT base64.  The display file at $9729 is starfield dots only (masks from
#  the game's $FEBD table) and goes in as base64; so does every attribute file.  Character
#  codes come ARITHMETICALLY from the glyph address $8044 built -- (DE - $3C00) / 8 at
#  $803B -- never from a ROM read.  $D167..$D18F is guarded on every instruction.
TP_R0 = 107                  # R at $970F; -> 111 at $9712, title.pkl's captured phase
TP_SP = 0x96DD
TP_SEED = 0x002A
TP_POISON = 0xAA             # asserted below never to be a value either leg writes
TP_START, TP_MID, TP_END = 0x970F, 0x9729, 0x9765


def phase_title_paint():
    import base64, collections, hashlib
    from harness import A as RA_, C as RC_, D as RD_, E as RE_, H as RH_, L as RL_, R as RR_

    def world(fec4=0x00):
        h = Harness(contended=True)
        h.load_state_file(pc.state_path('title'))
        m, r = h.memobj.m, h.sim.registers
        pre = {'patch_tape': [m[a] for a in CS_PATCH],
               'seed_tape': m[0xFE86] | (m[0xFE87] << 8),
               'fec4_tape': m[0xFEC4], 'r_tape': r[RR_] & 0x7F}
        for a in CS_PATCH:                      # what $969A stores on 48K
            m[a] = 0xC9
        m[0xFEC4], m[0xFEC5] = fec4, 0x00      # what $96EF leaves (fec4 = the arm)
        m[0xFE86], m[0xFE87] = TP_SEED & 0xFF, TP_SEED >> 8
        m[0xFEBB] = 0xFF                        # `AND 7` can never produce it
        for a in range(0x4000, 0x5C00):         # display + attributes + $5B00..$5BFF
            m[a] = TP_POISON
        r[IFF] = 0
        r[SP] = TP_SP
        r[PC] = TP_START
        r[RR_] = TP_R0
        return h, m, r, pre

    def run(h, stop, taps=None, limit=2000000):
        """steps to `stop`, interrupts off; returns writes as (src_pc, log_pc, addr, v)"""
        r, op, mem, lg = h.sim.registers, h.sim.opcodes, h.sim.memory, h.memobj
        h.memobj.watch(0x4000, 0x10000)
        out, n = [], 0
        while r[PC] != stop:
            p = r[PC]
            assert not (CS_GUARD_LO <= p < CS_GUARD_HI), 'ENTERED THE GUARDED RANGE'
            assert p not in CS_PATCH, 'executed a RET patch at $%04X' % p
            assert n < limit, 'never reached $%04X -- PC $%04X' % (stop, p)
            k = len(lg.log)
            op[mem[p]]()
            n += 1
            for (lp, a, v) in lg.log[k:]:
                out.append((p, lp, a, v))
            if taps is not None:
                taps(p, r, mem)
        h.memobj.unwatch()
        return out, n

    def outside(ws):
        c = collections.Counter(a for _p, _l, a, _v in ws if not 0x4000 <= a < 0x5B00)
        return [[a, c[a]] for a in sorted(c)]

    def screen_counts(m):
        d = [m[a] for a in range(0x4000, 0x5800)]
        return {'lit': sum(1 for v in d if v), 'pixels': sum(bin(v).count('1') for v in d),
                'bit0': sum(1 for v in d if v & 1)}

    OUT = {}
    # ------------------------------------------------ THE drive, leg 1: $970F -> $9729
    h, m, r, pre = world()
    assert pre['seed_tape'] == TP_SEED, 'title.pkl PRNG is not $002A: $%04X' % pre['seed_tape']
    #  the r0 justification is title.pkl's captured R -- if the capture changes, say so
    assert pre['r_tape'] == 111, 'title.pkl R is no longer 111: %d' % pre['r_tape']
    assert pre['patch_tape'] != [0xC9] * 3, 'title.pkl already patched -- TRAPS #44'
    rows = collections.defaultdict(list)

    def tap1(p, r, mem):
        if p == 0x9715:
            rows['r9715'].append(r[RA_] & 0x7F)
            rows['a9715_bit7'].append(r[RA_] >> 7)
        elif p == 0xFEAC:
            rows['rFEAC'].append(r[RA_] & 0x7F)
        if r[PC] == 0x9720 and p != 0x9720:     # the RET of the $971D call just ran
            rows['draw'].append(mem[0xFE86] | (mem[0xFE87] << 8))

    w1, n1 = run(h, TP_MID, tap1)
    r_at_mid = r[RR_] & 0x7F
    snapA = bytes(m[0x4000:0x5B00])
    sA = screen_counts(m)
    past_A = [m[0x5B00 + i] for i in range(0x100)]
    #  the starfield rows, from the WRITES, keyed on the source PC
    disp = [(a, v) for p, _l, a, v in w1 if p == 0xFEB0]
    attr = [(a, v) for p, _l, a, v in w1 if p == 0xFEBA]
    cls_writes = sum(1 for p, _l, _a, _v in w1 if p in (0x97F4, 0x97F5))
    pc_mismatch1 = sum(1 for p, l, _a, _v in w1 if p != l)
    ph = rows['r9715']
    steps = collections.Counter((ph[i + 1] - ph[i]) % 128 for i in range(len(ph) - 1))
    offs = collections.Counter((rows['rFEAC'][i] - ph[i]) % 128 for i in range(len(ph)))
    odd = [i for i in range(len(ph) - 1) if (ph[i + 1] - ph[i]) % 128 == 53]
    #  the PRNG, re-derived independently of the draw tap
    s, model = TP_SEED, []
    for _ in range(len(rows['draw'])):
        lo, hi = s & 0xFF, s >> 8
        a = (((hi << 1) | (hi >> 7)) & 0xFF) ^ lo
        hi = (a + 0xFE) & 0xFF
        lo = (((hi >> 1) | (hi << 7)) & 0xFF) ^ lo
        s = (hi << 8) | lo
        model.append(s)
    OUT['r0'] = TP_R0
    OUT['r_tape'] = pre['r_tape']
    OUT['r_at_9712'] = None
    OUT['first_draw_r9715'] = ph[0]
    OUT['seed'] = TP_SEED
    OUT['fec4'] = 0x00
    OUT['sp'] = TP_SP
    OUT['poison'] = TP_POISON
    OUT['star'] = {
        'n_instr': n1, 'n_writes': len(w1), 'cls_writes': cls_writes,
        'disp': [a for a, _ in disp], 'attr': [a for a, _ in attr],
        'mask': [v for _, v in disp], 'ink': [v for _, v in attr],
        'draw': rows['draw'], 'r9715': ph, 'rFEAC': rows['rFEAC'],
        'prng_end': m[0xFE86] | (m[0xFE87] << 8), 'febb_end': m[0xFEBB],
        'r_at_9729': r_at_mid,
        'outside': outside(w1),
        'lit': sA['lit'], 'pixels': sA['pixels'], 'bit0': sA['bit0'],
        'distinct_disp': len({a for a, _ in disp}),
        'screen_b64': base64.b64encode(snapA).decode('ascii'),
        'screen_sha': hashlib.sha256(snapA).hexdigest()[:16],
        'step_hist': [[k, steps[k]] for k in sorted(steps)],
        'offset_hist': [[k, offs[k]] for k in sorted(offs)],
        'step53_at': odd,
        'past_end_intact': all(v == TP_POISON for v in past_A),
        'src_pc_ne_log_pc': pc_mismatch1,
        'log_pc_mismatch_addrs': sorted({a for p, l, a, _v in w1 if p != l}),
        'log_pc_mismatch_srcs': sorted({p for p, l, a, _v in w1 if p != l}),
        'a9715_bit7_set': sum(rows['a9715_bit7']),
        'draw_matches_prng_model': rows['draw'] == model}
    st = OUT['star']

    # ------------------------------------------------ the SAME drive, leg 2: -> $9765
    v803c_before = [m[0x803C], m[0x803D]]
    taps2 = {'codes': [], 'ix9751': None}

    def tap2(p, r, mem):
        if r[PC] == 0x803B:                     # DE = $3C00 + 8 * code, built by $8044
            de = (r[RD_] << 8) | r[RE_]
            taps2['codes'].append((de - 0x3C00) & 0xFFFF)
        if r[PC] == 0x9751 and taps2['ix9751'] is None:
            taps2['ix9751'] = (r[IXh] << 8) | r[IXl]

    w2, n2 = run(h, TP_END, tap2)
    snapB = bytes(m[0x4000:0x5B00])
    sB = screen_counts(m)
    past_B = [m[0x5B00 + i] for i in range(0x100)]
    dw = [(p, a) for p, _l, a, _v in w2 if 0x4000 <= a < 0x5800]
    aw = [(a, v) for p, _l, a, v in w2 if 0x5800 <= a < 0x5B00]
    awpc = collections.Counter(p for p, _l, a, _v in w2 if 0x5800 <= a < 0x5B00)
    dpc = collections.Counter(p for p, _a in dw)
    runs = []
    for a, v in aw:
        if runs and a == runs[-1][0] + runs[-1][1] and v == runs[-1][2]:
            runs[-1][1] += 1
        else:
            runs.append([a, 1, v])
    raw = taps2['codes']
    assert all(c % 8 == 0 for c in raw), 'a glyph address off the 8-byte grid'
    codes = [c // 8 for c in raw]
    cc = collections.Counter(codes)
    #  the cross-check route: the string bytes themselves (game RAM, not ROM), walked
    #  to their NULs -- compared, NOT stored
    walked, a = [], 0x9A32
    for _ in range(4):
        while m[a] != 0:
            walked.append(m[a]); a += 1
        a += 1
    chain_end = a
    a = 0x9AB8
    while m[a] != 0:
        walked.append(m[a]); a += 1
    written_vals = {v for _p, _l, a, v in w1 + w2 if 0x4000 <= a < 0x5C00}   # mask/ink/glyph/attr
    OUT['strings'] = {
        'n_instr': n2, 'n_writes': len(w2),
        'disp_addr': [a for _p, a in dw],
        'disp_pcs': [[p, dpc[p]] for p in sorted(dpc)],
        'attr_addr': [a for a, _ in aw], 'attr_val': [v for _, v in aw],
        'attr_pcs': [[p, awpc[p]] for p in sorted(awpc)],
        'attr_runs': runs,
        'attr_values': sorted({v for _, v in aw}),
        'attr_values_in_order': [x[2] for x in runs],
        'n_disp_writes': len(dw), 'n_attr_writes': len(aw),
        'n_disp_distinct': len({a for _p, a in dw}),
        'v803c_before': v803c_before, 'v803c_after': [m[0x803C], m[0x803D]],
        'ix_at_9751': taps2['ix9751'], 'chain_end_plus1': chain_end,
        'attr_b64': base64.b64encode(snapB[0x1800:]).decode('ascii'),
        'display_sha': hashlib.sha256(snapB[:0x1800]).hexdigest(),
        'display_note': 'digest only -- the credit line is ROM glyph bytes verbatim',
        'lit': sB['lit'], 'pixels': sB['pixels'], 'bit0': sB['bit0'],
        'outside': outside(w2),
        'codes': [[k, cc[k]] for k in sorted(cc)], 'n_chars': len(codes),
        'n_codes': len(cc), 'codes_match_string_bytes': codes == walked,
        'past_end_intact': all(v == TP_POISON for v in past_B),
        'src_pc_ne_log_pc': sum(1 for p, l, _a, _v in w2 if p != l),
        'log_pc_mismatch_addrs': sorted({a for p, l, a, _v in w2 if p != l}),
        'log_pc_mismatch_srcs': sorted({p for p, l, a, _v in w2 if p != l}),
        'poison_written': TP_POISON in written_vals}
    sg = OUT['strings']

    # ------------------------------------------------ the two machine-side controls
    ctl = {}
    for f in (0x14, 0x01):
        g, mg, rg, _ = world(fec4=f)
        run(g, TP_MID)
        ctl['%02X' % f] = screen_counts(mg)
    OUT['controls'] = {'fec4_14': ctl['14'], 'fec4_01': ctl['01']}

    #  R at $9712, from a third short drive (the tap above is at $9715)
    g, mg, rg, _ = world()
    run(g, 0x9712)
    OUT['r_at_9712'] = rg[RR_] & 0x7F

    # ------------------------------------------------ report, then EVERY claim asserted
    print('$970F..$9764 -- the title paint, one drive, r0=%d (R=%d at $9712), seed $%04X'
          % (TP_R0, OUT['r_at_9712'], TP_SEED))
    print('    leg 1: %d instr, %d writes (CLS %d); %d dots, first draw R=%d; lit %d '
          'pixels %d bit0 %d; PRNG end $%04X'
          % (n1, len(w1), cls_writes, len(disp), ph[0], st['lit'], st['pixels'],
             st['bit0'], st['prng_end']))
    print('    steps %s  offsets %s  +53 at %s  outside %s'
          % (st['step_hist'], st['offset_hist'], odd,
             ['$%04Xx%d' % (a, c) for a, c in st['outside']]))
    print('    leg 2: %d instr, %d display writes %s, %d attr writes in %d runs %s'
          % (n2, sg['n_disp_writes'], ['$%04Xx%d' % (p, c) for p, c in sg['disp_pcs']],
             sg['n_attr_writes'], len(runs), ['%02X' % v for v in sg['attr_values_in_order']]))
    print('    $803C/D %s -> %s; IX at $9751 $%04X; %d chars, %d codes; outside %s'
          % (sg['v803c_before'], sg['v803c_after'], sg['ix_at_9751'], len(codes),
             len(cc), ['$%04Xx%d' % (a, c) for a, c in sg['outside']]))
    print('    controls: $FEC4=$14 %s  $FEC4=$01 %s' % (ctl['14'], ctl['01']))

    assert OUT['r_at_9712'] == 111, 'R at $9712 is %d, not 111' % OUT['r_at_9712']
    print('    log PC != source PC: leg1 %d at %s from %s; leg2 %d at %s from %s'
          % (st['src_pc_ne_log_pc'], ['$%04X' % a for a in st['log_pc_mismatch_addrs']],
             ['$%04X' % a for a in st['log_pc_mismatch_srcs']], sg['src_pc_ne_log_pc'],
             ['$%04X' % a for a in sg['log_pc_mismatch_addrs']],
             ['$%04X' % a for a in sg['log_pc_mismatch_srcs']]))
    assert st['a9715_bit7_set'] == 0, 'R bit 7 was set'
    assert cls_writes == 6912, cls_writes
    assert len(disp) == 1024 and len(attr) == 1024, (len(disp), len(attr))
    assert len(ph) == 1024 and len(rows['rFEAC']) == 1024 and len(rows['draw']) == 1024
    assert st['draw_matches_prng_model'], 'the $971D draws are not the $FE85 PRNG'
    assert st['prng_end'] == rows['draw'][-1]
    assert dict(steps) == {51: 1020, 53: 3}, dict(steps)
    assert dict(offs) == {35: 1024}, dict(offs)
    assert odd == [255, 511, 767], odd
    assert st['ink'] == [x & 7 for x in ph], 'ink is not R & 7'
    assert all(0x4000 <= a < 0x5800 for a in st['disp'])
    assert all(0x5800 <= a < 0x5B00 for a in st['attr'])
    assert (st['lit'], st['bit0'], st['pixels']) == (820, 0, 820), \
        (st['lit'], st['bit0'], st['pixels'])
    assert st['past_end_intact'] and sg['past_end_intact'], '$5B00..$5BFF was touched'
    assert st['febb_end'] != 0xFF, 'the ink variable was never written'
    out1 = {a for a, _c in st['outside']}
    assert {0xFE86, 0xFE87, 0xFEBB} <= out1, st['outside']
    assert all(a in (0xFE86, 0xFE87, 0xFEBB) or TP_SP - 8 <= a < TP_SP
               for a in out1), 'leg 1 wrote outside the files and stack: %r' % st['outside']
    assert sg['n_disp_writes'] == 1328, sg['n_disp_writes']
    assert sg['n_disp_distinct'] == 1328, 'display writes are not distinct'
    assert sum(c for p, c in sg['disp_pcs'] if p in (0x8065, 0x8067)) == 1264
    assert sum(c for p, c in sg['disp_pcs'] if p == 0x8052) == 64
    assert sg['n_attr_writes'] == 167, sg['n_attr_writes']
    assert [p for p, _c in sg['attr_pcs']] == [0x995C], sg['attr_pcs']
    assert len(runs) == 9, runs
    assert [x[0] for x in runs] == [0x5845, 0x5865, 0x5906, 0x5926, 0x5967, 0x5987,
                                    0x5A2A, 0x5A4A, 0x5AF7], runs
    assert sg['attr_values_in_order'] == [0x47, 0x47, 0x46, 0x46, 0x43, 0x43,
                                          0xCC, 0xCC, 0x45]
    assert set(sg['attr_values']) == {0x47, 0x46, 0x43, 0xCC, 0x45}
    assert sg['ix_at_9751'] == 0x9A85 == sg['chain_end_plus1'], \
        (sg['ix_at_9751'], sg['chain_end_plus1'])
    assert len(codes) == 87 and sg['codes_match_string_bytes'], \
        'the glyph-address route and the string bytes disagree'
    out2 = {a for a, _c in sg['outside']}
    assert all(a in (0x803C, 0x803D) or TP_SP - 16 <= a < TP_SP for a in out2), \
        'leg 2 wrote outside the files, stack and $803C/D: %r' % sg['outside']
    #  TRAPS #200 on the harness itself: its log PC is read at WRITE time, and a CALL
    #  pushes after PC has moved -- so the two keys may differ, but ONLY on the stack
    for leg in (st, sg):
        assert all(TP_SP - 16 <= a < TP_SP for a in leg['log_pc_mismatch_addrs']),             'a non-stack write carries a log PC that is not its source PC'
    assert not sg['poison_written'], 'the poison is a value the game writes'
    assert ctl['14']['lit'] == 940, ctl['14']
    assert ctl['01']['bit0'] == 120, ctl['01']
    #  THE TAPE'S OWN BYTES for what reset() seeds, so the port's constants are tied
    #  to the image rather than typed twice (TRAPS #202): the banner block from
    #  'ROUND' through the $9A85 table, and the seven mask constants.  Game data,
    #  outside the relocated window -- no ROM here.
    with open('build/image_tape.bin', 'rb') as f:
        img = f.read()
    OUT['tape'] = {'banner_9a06': list(img[0x9A06:0x9A95]),
                   'masks_febd': list(img[0xFEBD:0xFEC4]), 'fec4': img[0xFEC4]}
    assert OUT['tape']['masks_febd'] == [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02]
    # ------------------------------------------------ leg 3: INTERRUPTS ON (M7.41 review)
    #  $970E is EI, so the machine paints with interrupts LIVE, and every ISR landing
    #  inside the pass moves R.  The port's walk has no in-loop ISR bumps -- a DECLARED
    #  departure, because WHERE the ISRs land needs a T-state clock the port does not
    #  model.  What survives them is the PRNG-only projection: for each dot, the display
    #  page, the mask and bit 7 of the display low byte (H is final before R is read,
    #  and R is seven bits).  Driven on round1_48 -- a cold-started world whose IM 2
    #  vector and ISR are the real ones -- at SIXTEEN frame phases, from $9712 with the
    #  seed and $FEC4 of leg 1.  Rows keyed on the SOURCE PC (an ISR RETs to the
    #  interrupted address, so a destination probe records a dot twice).
    inv_rows = []
    for k in range(16):
        h3 = Harness(contended=True)
        h3.load_state_file(pc.state_path('round1_48'))
        m3, r3 = h3.memobj.m, h3.sim.registers
        assert m3[0x8DC4] == 0xC9, 'round1_48 is not a 48K cold-started world'
        m3[0xFEC4], m3[0xFEC5] = 0x00, 0x00
        m3[0xFE86], m3[0xFE87] = TP_SEED & 0xFF, TP_SEED >> 8
        fd, ia = h3.frame_duration, h3.int_active
        r3[T] = (r3[T] // fd) * fd + (k * fd) // 16
        r3[RR_] = 111
        r3[IFF] = 1
        r3[SP] = TP_SP
        r3[PC] = 0x9712
        op, mem = h3.sim.opcodes, h3.sim.memory
        inv, ph, nisr, n = [], [], 0, 0
        while r3[PC] != TP_MID:
            p = r3[PC]
            assert not (CS_GUARD_LO <= p < CS_GUARD_HI), 'ENTERED THE GUARDED RANGE'
            assert n < 1000000, 'leg 3 never reached $9729 -- PC $%04X' % p
            if mem[p] == 0x76 and r3[IFF]:
                h3._fast_halt()
                n += 1
                continue
            op[mem[p]]()
            n += 1
            if p == 0x9715:
                ph.append(r3[RA_] & 0x7F)
            elif p == 0xFEB0:
                inv.append((r3[RH_] << 9) | (r3[RC_] << 1) | ((r3[RL_] >> 7) & 1))
            if r3[IFF] and r3[T] % fd < ia:
                b = r3[PC]
                h3.sim.accept_interrupt(r3, mem, p)
                if r3[PC] != b:
                    nisr += 1
        steps = collections.Counter((ph[i + 1] - ph[i]) % 128 for i in range(len(ph) - 1))
        inv_rows.append({'tphase': k, 'n_isr': nisr, 'dots': len(inv), 'inv': inv,
                         'steps': sorted([a, b] for a, b in steps.items()),
                         'prng_after': m3[0xFE86] | (m3[0xFE87] << 8)})
    inv0 = inv_rows[0]['inv']
    OUT['ints_on'] = {
        'world': 'round1_48', 'phases': 16,
        'inv': inv0,
        'inv_note': 'per dot: (display page << 9) | (mask << 1) | bit 7 of the display low byte',
        'distinct_inv': len(set(tuple(x['inv']) for x in inv_rows)),
        'n_isr': sorted(set(x['n_isr'] for x in inv_rows)),
        'prng_after': sorted(set(x['prng_after'] for x in inv_rows)),
        'non51_steps': sorted(set(a for x in inv_rows for a, _b in x['steps'] if a not in (51, 53))),
        'distinct_step_hists': len(set(json.dumps(x['steps']) for x in inv_rows)),
    }
    io_ = OUT['ints_on']
    assert io_['distinct_inv'] == 1, 'the PRNG-only projection is not interrupt-invariant'
    assert all(x['dots'] == 1024 for x in inv_rows)
    assert io_['prng_after'] == [OUT['star']['prng_end']], io_['prng_after']
    assert min(io_['n_isr']) >= 1, 'no ISR landed -- this leg measured nothing'
    assert io_['non51_steps'], 'the ISRs left no mark on the walk'
    #  and the interrupts-OFF leg projects onto the SAME sequence
    st_ = OUT['star']
    proj1 = [((d >> 8) << 9) | (mk << 1) | ((d >> 7) & 1) for d, mk in zip(st_['disp'], st_['mask'])]
    assert proj1 == inv0, 'leg 1 and leg 3 disagree on the PRNG-only projection'

    # ------------------------------------------------ $994F past the 8-bit L wrap
    #  The port's second-row arithmetic was argued from the bytes; these are the
    #  machine's own answers, so the gate compares against a measurement.
    wraps = []
    for hl, b in ((0x5845, 24), (0x58F0, 32), (0x5AF0, 32), (0x59FF, 1), (0x5845, 0)):
        hw = Harness(contended=True)
        hw.load_state_file(pc.state_path('title'))
        mw, rw = hw.memobj.m, hw.sim.registers
        for a in range(0x5700, 0x5C00):
            mw[a] = 0x00
        rw[IFF] = 0
        rw[SP] = TP_SP
        rw[RA_] = 0x01
        hw.memobj.watch(0x4000, 0x10000)
        idx, _t, _n = hw.call(0x994F, regs={'HL': hl, 'BC': (b << 8)})
        ws = [(a, v) for _p, a, v in hw.memobj.log if 0x5700 <= a < 0x5C00]
        hw.memobj.unwatch()
        assert idx == 0, '$994F did not return'
        wraps.append({'hl': hl, 'b': b, 'addrs': [a for a, _v in ws],
                      'values': sorted(set(v for _a, v in ws))})
    OUT['attr_double'] = wraps
    assert wraps[1]['addrs'][32] == 0x5810 and wraps[2]['addrs'][32] == 0x5A10, wraps
    assert all(a < 0x5B00 for w in wraps for a in w['addrs'])
    assert len(wraps[4]['addrs']) == 512, 'B = 0 is 256 per row: %d' % len(wraps[4]['addrs'])

    # ------------------------------------------------ nothing enters the middle
    #  $9729, $9751 and $9765 are fallen into; the census is every CALL, JP and
    #  conditional form, and every JR / DJNZ, over the image outside both screen
    #  files ($4000..$5AFF also holds a copy of $FA00.., so it is excluded).
    ops16 = [0xCD, 0xC3] + [0xC4 + 8 * i for i in range(8)] + [0xC2 + 8 * i for i in range(8)]
    ops8 = [0x18, 0x20, 0x28, 0x30, 0x38, 0x10]
    census = {}
    for tgt in (0x9729, 0x9751, 0x9765):
        hits = []
        for a in range(0x5B00, 0xFFFD):
            if img[a] in ops16 and img[a + 1] == (tgt & 0xFF) and img[a + 2] == (tgt >> 8):
                hits.append(a)
            if img[a] in ops8:
                d = img[a + 1] - 256 if img[a + 1] > 127 else img[a + 1]
                if (a + 2 + d) & 0xFFFF == tgt:
                    hits.append(a)
        census['%04X' % tgt] = hits
    OUT['no_entry'] = census
    #  the two FALL-INS are the only branch-shaped bytes allowed near them: $9727 JR nz
    #  targets $9715 and $974F DJNZ targets $9733 -- neither is a hit here
    assert all(v == [] for v in census.values()), census

    assert img[0x9A0E:0x9A10] == bytes([0x20, 0x30]), 'the tape no longer says ROUND    0'
    return OUT


# ============================================================================ GROUP 2
#  $9765..$97EA -- THE SPARKLE RING, THE KEY WAIT, THE RELEASE WAIT, the hand-off to
#  playersInit and the RET to $8D09: front-end GROUP 2 (C + D), ONE capture.
#
#  NO ROM BYTES.  $D000..$D2FF is never entered: go() asserts a PC guard over it on
#  every instruction, ISR included.
TW_GUARD_LO, TW_GUARD_HI = 0xD000, 0xD300
TW_RING_LO, TW_RING_HI = 0x5800, 0x5B00            # the ring, half-open
TW_ARMS = (0x9790, 0x979E)                          # 2P, 1P
TW_LAND = 0x8D09
TW_STACK = (0x9680, 0x96DD)                         # below $8CC4's LD SP,$96DD
TW_POISON = 0x5A                                    # neither arm nor $97AB.. writes it
TW_FIELDS = [0xFDDA + i for i in range(7)] + [0xFDE4 + i for i in range(7)] + [0x9A0E]
TW_ISR_WRITES = [0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE]    # recon zzv_spark_isr.py
#  the loop's T-states, uncontended, summed from the disassembly (not measured here):
#   head  $9768 INC HL 6 / LD A,H 4 / CP $5B 7 / JR nz 12 (taken)          = 29
#         wrap: JR nz 7 + $976E LD H,$58 7 in place of the 12             = +2
#   test  $9770 BIT 6,(HL) 12 / $9772 JR nz 12 taken | 7
#   draw  $9774 EX DE,HL 4 / CALL $FE85 17 / $FE85 body 71 / EX DE,HL 4 / AND 7 7
#         ($FE85: LD HL,nn 10 LD A,H 4 RLCA 4 XOR L 4 ADD A,n 7 LD H,A 4 RRCA 4
#          XOR L 4 LD L,A 4 LD (nn),HL 16 RET 10 = 71)
#   gate  $977B JR nz 12 taken | 7 ; write $977D LD A,D 4 / AND 7 7 / LD (HL),A 7
#   keys  $9781 LD A,$F7 7 / IN A,($FE) 11 / CPL 4 / AND $1F 7 / JR z 12   = 41
TW_T_SKIP = 29 + 12 + 12 + 41                               # 94
TW_T_FAIL = 29 + 12 + 7 + (4 + 17 + 71 + 4 + 7) + 12 + 41   # 204
TW_T_WRITE = 29 + 12 + 7 + (4 + 17 + 71 + 4 + 7) + 7 + 18 + 41   # 217
#  $97EB = 10+10+10+7+(6910*21+16)+10 = 145,173; the $97B7 loop adds 17+4+11+4+7+12
#  = 55 when the JR nz is taken and 50 when it is not (M7.38 / zzv_rel_report s2)
TW_T_CLS_TAKEN, TW_T_CLS_OUT = 145173 + 55, 145173 + 50


def phase_title_wait():
    """$9765..$97EA -- front-end GROUP 2's oracle: the sparkle ring + key wait (C) and
    the release wait + playersInit (D), gated as ONE capture because C's exits ARE D's
    entry and the 15-vs-18 census delta ({$FD87, $FD91, $FED3}) is the boundary.

    THE WORLD.  title.pkl is NOT a cold-started world: I = $3F, IM 1, $FFF4..$FFF6 are
    not JP $8D72 -- its ISR is the ROM's, not the game's.  So the world is round1_48
    (I = $FC, IM 2, $FCFF -> $FFFF, $FFFF JR -> $FFF4 JP $8D72, the three RET patches
    applied): the stack built as the machine builds it ($8CC4 LD SP,$96DD; $8D02 PUSH
    $8CDC; $8D06 CALL $96DF pushes $8D09, so SP = $96D9), $96DF RUN to $970F (so
    $FED3 = 6 is $970B's store, not a typed literal), and then GROUP 1's exact
    conditions at $970F -- seed $002A, $FEC4/$FEC5 = 0, R = TP_R0, both files
    poisoned -- driven to $9765 with interrupts off.  It is asserted byte-identical,
    display + attributes + PRNG, to phase_title_paint's own title.pkl drive, so this
    phase starts exactly where GROUP 1's gate ends.

    *** prng16_at_9765 IS $2CCD IN THAT WORLD, NOT $5044. ***  $5044 (-> $E235 on the
    exit) is round1_48's NATIVE state at $9765: its own seed $16F9 and its own R at
    $970F.  Both are recorded; 'recon_world' is the native one.

    Rows are keyed on the SOURCE PC (TRAPS #200): the harness's log PC is read at
    write time, and a CALL pushes after PC has moved."""
    import base64, collections, statistics
    from harness import A as RA_, D as RD_, H as RH_, L as RL_, R as RR_, I as RI_, IM as RIM_
    from keyprobe import KEYMAP, keymask

    assert KEYMAP['1'] == (0xF7, 0) and KEYMAP['2'] == (0xF7, 1)

    def prng_next(s):
        lo, hi = s & 0xFF, s >> 8
        a = (((hi << 1) | (hi >> 7)) & 0xFF) ^ lo
        hi = (a + 0xFE) & 0xFF
        lo = (((hi >> 1) | (hi << 7)) & 0xFF) ^ lo
        return (hi << 8) | lo

    def prng(m):
        return m[0xFE86] | (m[0xFE87] << 8)

    def go(h, stop=(), ints=False, hook=None, ctl=None, limit=40_000_000):
        """one instruction at a time.  hook(p) runs before every MAIN-LINE instruction
           (never inside the ISR) and may return True to stop; ctl['release_at'] /
           ctl['press_at'] + ctl['press'] act on the keyboard at a T.  Every write is
           kept as (source PC, or -1 inside the ISR, addr, value)."""
        r, op, mem, lg = h.sim.registers, h.sim.opcodes, h.sim.memory, h.memobj
        fd, ia = h.frame_duration, h.int_active
        ctl = ctl if ctl is not None else {}
        lg.watch(0x4000, 0x10000)
        ws, n, nisr, costs, nested, isr = [], 0, 0, [], 0, None
        while True:
            p = r[PC]
            assert not (TW_GUARD_LO <= p < TW_GUARD_HI), 'ENTERED THE GUARDED RANGE'
            if isr is not None and p == isr[0] and r[SP] == isr[1]:
                costs.append(r[T] - isr[2])
                isr = None
            if isr is None:
                if ctl.get('release_at') is not None and r[T] >= ctl['release_at']:
                    h.ports.release_all()
                    ctl['released_T'], ctl['release_at'] = r[T], None
                if ctl.get('press_at') is not None and r[T] >= ctl['press_at']:
                    for k in ctl['press']:
                        h.ports.press(KEYMAP[k][0], keymask(KEYMAP[k][1]))
                    ctl['pressed_T'], ctl['press_at'] = r[T], None
                if p in stop or (hook is not None and hook(p)):
                    break
            assert n < limit, 'go() ran out at PC $%04X' % p
            assert mem[p] != 0x76, 'a HALT at $%04X -- not modelled here' % p
            k = len(lg.log)
            op[mem[p]]()
            n += 1
            tag = -1 if isr is not None else p
            for (_lp, a, v) in lg.log[k:]:
                ws.append((tag, a, v))
            if ints and r[IFF] and r[T] % fd < ia:
                b, spb, t0 = r[PC], r[SP], r[T]
                k = len(lg.log)
                if h.sim.accept_interrupt(r, mem, p):
                    if isr is not None:
                        nested += 1
                    nisr += 1
                    isr = (b, spb, t0)
                    for (_lp, a, v) in lg.log[k:]:
                        ws.append((-1, a, v))
        lg.unwatch()
        assert nested == 0, 'an interrupt was accepted inside the ISR'
        return {'ws': ws, 'n': n, 'nisr': nisr, 'isr_costs': costs}

    def build(contended=True, natural=False):
        h = Harness(contended=contended)
        h.load_state_file(pc.state_path('round1_48'))
        m, r = h.memobj.m, h.sim.registers
        assert [m[a] for a in CS_PATCH] == [0xC9] * 3, 'round1_48 is not patched'
        m[0x96DB], m[0x96DC] = 0xDC, 0x8C       # $8D02 PUSH $8CDC
        m[0x96D9], m[0x96DA] = 0x09, 0x8D       # $8D06 CALL $96DF -> returns to $8D09
        r[SP], r[PC], r[IFF] = 0x96D9, RESET, 0
        g = go(h, (TP_START,), limit=10000)
        fed3_writers = sorted({p for p, a, _v in g['ws'] if a == 0xFED3})
        if not natural:
            m[0xFE86], m[0xFE87] = TP_SEED & 0xFF, TP_SEED >> 8
            assert m[0xFEC4] == 0 and m[0xFEC5] == 0, '$96EF did not leave $FEC4/5 zero'
            m[0xFEBB] = 0xFF
            for a in range(0x4000, 0x5C00):
                m[a] = TP_POISON
            r[RR_] = TP_R0
        r[IFF] = 0
        go(h, (0x9765,), limit=200000)
        assert r[SP] == 0x96D9, 'SP at $9765 is $%04X' % r[SP]
        return h, m, r, fed3_writers

    OUT = {}
    # ------------------------------------------------ the world at $9765
    h, m, r, fed3_writers = build()
    vec = (r[RI_] << 8) | 0xFF
    isr_ok = (r[RIM_] == 2 and r[RI_] == 0xFC and m[vec] | (m[vec + 1] << 8) == 0xFFFF
              and m[0xFFFF] == 0x18 and [m[0xFFF4], m[0xFFF5], m[0xFFF6]] == [0xC3, 0x72, 0x8D])
    assert isr_ok, 'round1_48 no longer has the game ISR (IM 2, $FFF4 JP $8D72)'
    #  ... and title.pkl does NOT, which is why this is not title.pkl
    ht = Harness(contended=True)
    ht.load_state_file(pc.state_path('title'))
    rt, mt = ht.sim.registers, ht.memobj.m
    title_isr = {'i': rt[RI_], 'im': rt[RIM_],
                 'fff4_is_jp_8d72': [mt[0xFFF4], mt[0xFFF5], mt[0xFFF6]] == [0xC3, 0x72, 0x8D]}
    assert not (title_isr['im'] == 2 and title_isr['fff4_is_jp_8d72']), \
        'title.pkl now has the real ISR -- revisit the choice of world'
    #  GROUP 1's own drive of title.pkl (phase_title_paint's world()), to $9765
    for a in CS_PATCH:
        mt[a] = 0xC9
    mt[0xFEC4], mt[0xFEC5] = 0, 0
    mt[0xFE86], mt[0xFE87] = TP_SEED & 0xFF, TP_SEED >> 8
    mt[0xFEBB] = 0xFF
    for a in range(0x4000, 0x5C00):
        mt[a] = TP_POISON
    rt[IFF], rt[SP], rt[PC], rt[RR_] = 0, TP_SP, TP_START, TP_R0
    go(ht, (0x9765,), limit=200000)
    same_as_group1 = (bytes(mt[0x4000:0x5B00]) == bytes(m[0x4000:0x5B00])
                      and prng(mt) == prng(m) and mt[0xFEBB] == m[0xFEBB])
    assert same_as_group1, 'the round1_48 world at $9765 is not GROUP 1\'s title.pkl world'
    assert m[0x9782] == 0xF7, '$9781 LD A,$F7 operand moved: $%02X' % m[0x9782]
    assert m[0x9787] == 0x1F, '$9786 AND $1F operand moved: $%02X' % m[0x9787]
    assert m[0x9766] | (m[0x9767] << 8) == 0x5800, 'the cursor seed moved'
    S0 = h.save_state()
    fd = h.frame_duration
    P0 = prng(m)
    attr0 = bytes(m[0x5800:0x5B00])
    bright = [a for a in range(TW_RING_LO, TW_RING_HI) if m[a] & 0x40]
    runs = []
    for a in bright:
        if runs and a == runs[-1][0] + runs[-1][1]:
            runs[-1][1] += 1
        else:
            runs.append([a, 1])
    OUT['world'] = {
        'state': 'round1_48', 'why': 'title.pkl has I=$%02X IM %d and no JP $8D72 at $FFF4'
                                     % (title_isr['i'], title_isr['im']),
        'same_as_group1_title_drive': same_as_group1,
        'sp': r[SP], 'tphase_at_9765': r[T] % fd, 'frame_duration': fd,
        'int_active': h.int_active, 'i': r[RI_], 'im': r[RIM_],
        'fed3_at_9765': m[0xFED3], 'fed3_writers': fed3_writers,
        'in_select': m[0x9782], 'in_mask': m[0x9787]}
    assert m[0xFED3] == 6 and fed3_writers == [0x970B], (m[0xFED3], fed3_writers)
    assert len(bright) == 167, len(bright)
    assert runs == [[0x5845, 24], [0x5865, 24], [0x5906, 21], [0x5926, 21], [0x5967, 20],
                    [0x5987, 20], [0x5A2A, 14], [0x5A4A, 14], [0x5AF7, 9]], runs

    # ------------------------------------------------ (a) 400 iterations, ints OFF, no key
    def ring_rows(hh, n_iter):
        mm, rr = hh.memobj.m, hh.sim.registers
        rows, after, cur = [], [], {}

        def hook(p):
            if p == 0x9770:
                if cur:
                    rows.append([cur['i'], cur['a'], cur['skip'], cur['gate'], cur['val']])
                    after.append(prng(mm))
                if len(rows) == n_iter:
                    return True
                a = (rr[RH_] << 8) | rr[RL_]
                cur.update({'i': len(rows), 'a': a, 'skip': 1 if mm[a] & 0x40 else 0,
                            'gate': -1, 'val': -1})
            elif p == 0x9779:
                cur['gate'] = rr[RA_] & 7
            elif p == 0x9780:
                cur['val'] = rr[RA_]
            return False
        g = go(hh, (), hook=hook)
        return rows, after, g

    rows, after, g = ring_rows(h, 400)
    w9780 = [v for p, a, v in g['ws'] if p == 0x9780]
    assert w9780 == [x[4] for x in rows if x[4] >= 0], 'the $9780 writes are not the rows'
    assert all(TW_RING_LO <= a < TW_RING_HI for p, a, _v in g['ws'] if p == 0x9780)
    #  the model, row for row: skip iff bit 6; one draw per non-skipped cell; write
    #  newHigh & 7 iff newLow & 7 == 0; the cursor steps +1 through $5801..$5AFF, $5800
    s, model = P0, []
    for x in rows:
        if x[2]:
            model.append([x[0], x[1], 1, -1, -1])
        else:
            s = prng_next(s)
            model.append([x[0], x[1], 0, s & 7, (s >> 8) & 7 if s & 7 == 0 else -1])
    assert rows == model, 'the rows disagree with the skip/gate/value model'
    assert [x[1] for x in rows] == [0x5801 + i for i in range(400)]
    assert after[-1] == s
    OUT['ring'] = {
        'prng16_at_9765': P0, 'cursor_start': rows[0][1],
        'rows': rows, 'prng_after': after,
        'attr_at_9765_b64': base64.b64encode(attr0).decode('ascii'),
        'attr_after_400_b64': base64.b64encode(bytes(m[0x5800:0x5B00])).decode('ascii'),
        'bright_runs': runs, 'n_bright': len(bright),
        'skips': sum(x[2] for x in rows), 'writes': len(w9780),
        'rows_note': '[iter, cursor, skipped, gate = newLow & 7 or -1, value or -1]'}
    #  and title.pkl's own drive gives the SAME 400 rows
    rows_t, after_t, _g = ring_rows(ht, 400)
    assert rows_t == rows and after_t == after, 'title.pkl and round1_48 disagree at $9765'

    # ------------------------------------------------ (b) the bit-6 witness
    WIT = {0x5802: 0x80, 0x5803: 0xC0, 0x5804: 0x40, 0x5805: 0x00}
    wit = {}
    for laps in (2, 100):
        h.load_state(S0)
        for a, v in WIT.items():
            m[a] = v
        cnt = collections.Counter()
        seen = {'i': 0, 'a': None}

        def hook(p):
            if p == 0x9770:
                seen['a'] = (r[RH_] << 8) | r[RL_]
                if seen['a'] in WIT:
                    cnt[('visit', seen['a'])] += 1
                seen['i'] += 1
                return seen['i'] > 767 + 768 * (laps - 1)
            if p == 0x9775 and seen['a'] in WIT:
                cnt[('draw', seen['a'])] += 1
            return False
        g = go(h, (), hook=hook)
        wc = collections.Counter(a for p, a, _v in g['ws'] if p == 0x9780 and a in WIT)
        wit['laps%d' % laps] = [[a, WIT[a], cnt[('visit', a)], cnt[('draw', a)], wc[a]]
                                for a in sorted(WIT)]
    wit['note'] = '[addr, seeded, visits, draws, writes]'
    OUT['bit6'] = wit
    for a, v, vis, dr, wr in wit['laps2']:
        assert vis == 2, (a, vis)
        assert dr == (0 if v & 0x40 else 2), 'bit 6 is not the whole skip predicate at $%04X' % a
    for a, v, vis, dr, wr in wit['laps100']:
        assert (wr == 0) == bool(v & 0x40), 'cell $%04X seeded $%02X written %d' % (a, v, wr)

    # ------------------------------------------------ (c) the exits, ints OFF
    CEN15 = TW_FIELDS
    exits = []
    for keys in (['1'], ['2'], ['1', '2'], ['3'], ['4', '5'], []):
        h.load_state(S0)
        for a in CEN15 + [P1F, P2F]:
            m[a] = TW_POISON
        fed3_before = m[0xFED3]
        for k in keys:
            h.ports.press(KEYMAP[k][0], keymask(KEYMAP[k][1]))
        c = {'it': 0, 'dr': 0}

        def hook(p):
            if p == 0x9770:
                c['it'] += 1
                return c['it'] > 3 * 768
            if p == 0x9775:
                c['dr'] += 1
            return False
        g = go(h, TW_ARMS, hook=hook)
        row = {'keys': '+'.join(keys) or 'none', 'arm': r[PC] if r[PC] in TW_ARMS else None,
               'iterations': c['it'], 'draws': c['dr'], 'prng_at_arm': prng(m),
               'fed3_before': fed3_before}
        if row['arm'] is None:
            row.update({'fed3_after': m[0xFED3], 'fd87': m[P1F], 'fd91': m[P2F]})
            exits.append(row)
            continue
        h.ports.release_all()                    # released the instant the arm is reached
        cn = collections.Counter()
        t_arm = r[T]

        def hook2(p):
            cn[p] += 1
            return False
        g = go(h, (TW_LAND,), hook=hook2)
        ws = g['ws']
        nd = {}
        for p, a, v in ws:
            if not (0x4000 <= a < 0x5B00 or TW_STACK[0] <= a < TW_STACK[1]):
                nd[a] = v
        stack = sorted({a for p, a, _v in ws if TW_STACK[0] <= a < TW_STACK[1]})
        row.update({
            'fed3_after': m[0xFED3], 'fd87': m[P1F], 'fd91': m[P2F],
            'cls_entries': cn[0x97EB], 'reached_97c7': cn[0x97C7], 'rets_97ea': cn[0x97EA],
            'display_writes': sum(1 for _p, a, _v in ws if 0x4000 <= a < 0x5B00),
            'display_zero': all(m[a] == 0 for a in range(0x4000, 0x5B00)),
            'census': [[a, nd[a]] for a in sorted(nd)],
            'stack_writes': [len([1 for _p, a, _v in ws if TW_STACK[0] <= a < TW_STACK[1]]),
                             stack[0] if stack else None, stack[-1] if stack else None],
            'land_pc': r[PC], 'land_sp': r[SP], 'word_at_sp': m[r[SP]] | (m[r[SP] + 1] << 8),
            'fields': [m[a] for a in CEN15],
            'T_arm_to_land': r[T] - t_arm})
        exits.append(row)
    OUT['exits'] = exits
    ex = {e['keys']: e for e in exits}
    P1 = prng_next(P0)
    for k, arm in (('1', 0x979E), ('2', 0x9790), ('1+2', 0x979E)):
        e = ex[k]
        assert e['arm'] == arm, (k, e['arm'])
        assert e['iterations'] == 1 and e['draws'] == 1 and e['prng_at_arm'] == P1, e
        assert (e['fed3_before'], e['fed3_after']) == (6, 5), e
        assert (e['fd87'], e['fd91']) == ((0x80, 0x00) if arm == 0x979E else (0x80, 0x80)), e
        assert e['cls_entries'] == 1 and e['reached_97c7'] == 1 and e['rets_97ea'] == 2, e
        assert e['display_writes'] == 6912 and e['display_zero'], e
        assert (e['land_pc'], e['land_sp'], e['word_at_sp']) == (TW_LAND, 0x96DB, OVER), e
        want = {a: TW_POISON for a in CEN15}
        want.update({0xFDDA: 0, 0xFDE4: 0, 0x9A0E: 0x20})
        for base in (0xFDDB, 0xFDE5):
            for i, v in enumerate((2, 3, 8, 8, 7, 0)):
                want[base + i] = v
        want.update({P1F: 0x80, P2F: 0x00 if arm == 0x979E else 0x80, 0xFED3: 5})
        assert e['census'] == [[a, want[a]] for a in sorted(want)], (k, e['census'])
        assert len(e['census']) == 18
    for k in ('3', '4+5', 'none'):
        e = ex[k]
        assert e['arm'] is None and e['iterations'] == 3 * 768 + 1, e
        assert (e['fed3_after'], e['fd87'], e['fd91']) == (6, TW_POISON, TW_POISON), e

    #  the recon's world: round1_48 NATIVE at $9765 ($16F9 seed, its own R)
    hn, mn, rn, _fw = build(natural=True)
    pn = prng(mn)
    hn.ports.press(0xF7, keymask(0))
    go(hn, TW_ARMS)
    OUT['recon_world'] = {'prng16_at_9765': pn, 'prng_at_arm': prng(mn), 'arm': rn[PC]}
    assert (pn, prng(mn), rn[PC]) == (0x5044, 0xE235, 0x979E), OUT['recon_world']

    # ------------------------------------------------ (d) the release wait, key held N frames
    rel = []
    for ints in (False, True):
        for N in (0, 1, 2, 3, 5, 10, 30):
            h.load_state(S0)
            r[IFF] = 1 if ints else 0
            h.ports.press(0xF7, keymask(0))
            ctl = {}
            st = {'cls': 0, 'done': 0, 'done_held': 0, 'c7': 0, 'b7': [], 'arm_T': None,
                  'c7_T': None, 'c2_T': None}

            def hook(p):
                if p in TW_ARMS and st['arm_T'] is None:
                    st['arm_T'] = r[T]
                    if N == 0:
                        h.ports.release_all()
                        ctl['released_T'] = r[T]
                    else:
                        ctl['release_at'] = r[T] + N * fd
                elif p == 0x97EB:
                    st['cls'] += 1
                elif p == 0x97BA:
                    st['done'] += 1
                    if 'released_T' not in ctl or r[T] < ctl['released_T']:
                        st['done_held'] += 1
                elif p == 0x97B7:
                    st['b7'].append(r[T])
                elif p == 0x97C2:
                    st['c2_T'] = r[T]
                elif p == 0x97C7:
                    st['c7'] += 1
                    st['c7_T'] = r[T]
                return False
            g = go(h, (TW_LAND,), ints=ints, hook=hook, ctl=ctl)
            tp = [b - a for a, b in zip(st['b7'], st['b7'][1:] + [st['c2_T']])]
            rel.append({'ints': int(ints), 'n': N, 'arm': st['arm_T'] is not None,
                        'cls': st['cls'], 'completed_held': st['done_held'],
                        'completed': st['done'],
                        'pass_T': [min(tp), max(tp), round(statistics.fmean(tp), 1)],
                        'T_arm_to_97c7': st['c7_T'] - st['arm_T'],
                        'frames_arm_to_97c7': st['c7_T'] // fd - st['arm_T'] // fd,
                        'T_release_to_97c7': st['c7_T'] - ctl['released_T'],
                        'reached_97c7': st['c7'], 'n_isr': g['nisr'],
                        'land': [r[PC], r[SP], m[r[SP]] | (m[r[SP] + 1] << 8)]})
    OUT['release'] = rel
    for x in rel:
        assert x['reached_97c7'] == 1, x
        assert x['land'] == [TW_LAND, 0x96DB, OVER], x
        assert x['completed'] == x['cls'] and x['completed_held'] == x['cls'] - 1, x
        assert 170000 < x['pass_T'][0] and x['pass_T'][1] < 195000, x
        assert (x['n_isr'] > 0) == bool(x['ints']), x
    #  the recon's entries table (zzfm_rel_report s2, entered at $97AB, ints OFF) holds
    #  from the real arm, and interrupts ON do not move a single count (zzv_rel_report s7)
    RECON_CLS = {0: 1, 1: 1, 2: 1, 3: 2, 5: 2, 10: 4, 30: 12}
    for x in rel:
        assert x['cls'] == RECON_CLS[x['n']], ('recon entries table', x)

    # ------------------------------------------------ (e) the ring per FRAME, ints ON
    h.load_state(S0)
    r[IFF] = 1
    t0 = r[T]
    NF = 320
    e_st = {'hits': [], 'bound': [], 'f': t0 // fd, 'draw_T': []}

    def hook(p):
        f = r[T] // fd
        if f != e_st['f']:
            e_st['bound'].append([f, prng(m)])
            e_st['f'] = f
        if p == 0x9770:
            e_st['hits'].append(r[T])
        return r[T] >= (t0 // fd + NF + 1) * fd
    g = go(h, TW_ARMS, ints=True, hook=hook)
    assert r[PC] not in TW_ARMS, 'the ring exited with no key down'
    b = collections.Counter(t // fd for t in e_st['hits'])
    ks = sorted(b)[1:-1]                                  # whole frames only
    per = [b[k] for k in ks]
    isr_w = sorted({a for p, a, _v in g['ws'] if p == -1
                    and not TW_STACK[0] <= a < TW_STACK[1]})
    isr_stack = sorted({a for p, a, _v in g['ws'] if p == -1 and TW_STACK[0] <= a < TW_STACK[1]})
    main_w = sorted({a for p, a, _v in g['ws'] if p != -1 and not (
        TW_RING_LO <= a < TW_RING_HI or a in (0xFE86, 0xFE87)
        or TW_STACK[0] <= a < TW_STACK[1])})
    ic = g['isr_costs']
    OUT['per_frame'] = {
        'frames': len(per), 'iters': per,
        'mean': round(statistics.fmean(per), 3), 'min': min(per), 'max': max(per),
        'prng_at_boundary': [x[1] for x in e_st['bound'][:64]],
        'n_isr': g['nisr'], 'isr_writes': isr_w,
        'isr_stack': [isr_stack[0], isr_stack[-1]] if isr_stack else None,
        'isr_T': [min(ic), max(ic), round(statistics.fmean(ic), 1)],
        'isr_T_distinct': len(set(ic)),
        'mainline_other_writes': main_w}
    pf = OUT['per_frame']
    assert isr_w == TW_ISR_WRITES, 'the ISR writes %s' % ['$%04X' % a for a in isr_w]
    assert main_w == [], main_w
    assert pf['n_isr'] >= NF, pf['n_isr']
    #  zzv_spark_report: 346..401 a frame, mean 374.02..374.11 -- a band, not a constant
    assert 340 <= pf['min'] and pf['max'] <= 410 and 373.5 < pf['mean'] < 374.5, pf
    #  the ISR never touches the PRNG: every frame-boundary state is on the $FE85 orbit
    s, orbit = P0, {P0}
    for _ in range(len(e_st['hits']) + 1):
        s = prng_next(s)
        orbit.add(s)
    assert all(x[1] in orbit for x in e_st['bound']), 'a boundary PRNG state off the orbit'

    # ------------------------------------------------ path costs: arithmetic, measured
    def path_costs(hh, n_iter):
        rr = hh.sim.registers
        seq, cur = [], {}

        def hook(p):
            if p == 0x9770:
                if cur:
                    seq.append((cur['t'], cur['k'], cur['a']))
                if len(seq) == n_iter:
                    return True
                cur.update({'t': rr[T], 'k': 's', 'a': (rr[RH_] << 8) | rr[RL_]})
            elif p == 0x977D:
                cur['k'] = 'w'
            elif p == 0x9775:
                cur['k'] = 'f'
            return False
        go(hh, (), hook=hook)
        out = collections.defaultdict(list)
        for (t, k, _a), (t2, _k2, a2) in zip(seq, seq[1:]):
            out[k + ('W' if a2 == 0x5800 else '')].append(t2 - t)
        return out
    hu = Harness(contended=False)
    hu.load_state(S0)
    assert not hu.contended
    cu = path_costs(hu, 2400)
    h.load_state(S0)
    cc = path_costs(h, 20000)
    OUT['path_T'] = {
        'arith': {'skip': TW_T_SKIP, 'fail': TW_T_FAIL, 'write': TW_T_WRITE, 'wrap': 2},
        'uncontended': {k: sorted(set(v)) for k, v in sorted(cu.items())},
        'contended': {k: [min(v), max(v), round(statistics.fmean(v), 2), len(v)]
                      for k, v in sorted(cc.items())}}
    assert cu['s'] and cu['f'] and cu['w'] and set(cu['s']) == {TW_T_SKIP}, sorted(set(cu['s']))
    assert set(cu['f']) == {TW_T_FAIL} and set(cu['w']) == {TW_T_WRITE}, (set(cu['f']), set(cu['w']))
    assert all(set(v) == {{'s': TW_T_SKIP, 'f': TW_T_FAIL, 'w': TW_T_WRITE}[k[0]] + 2}
               for k, v in cu.items() if k.endswith('W')), dict(cu)
    for k, v in cc.items():
        assert min(v) >= {'s': TW_T_SKIP, 'f': TW_T_FAIL, 'w': TW_T_WRITE}[k[0]], (k, min(v))

    #  the CLS pass, uncontended: taken (key held) and not taken (released)
    hu.load_state(S0)
    hu.ports.press(0xF7, keymask(0))
    b7 = []

    def hook(p):
        if p == 0x97B7:
            b7.append(hu.sim.registers[T])
            if len(b7) == 2:
                hu.ports.release_all()
        elif p == 0x97C2:
            b7.append(hu.sim.registers[T])
            return True
        return False
    go(hu, (), hook=hook)
    OUT['cls_T_uncontended'] = {'taken': b7[1] - b7[0], 'not_taken': b7[2] - b7[1]}
    assert OUT['cls_T_uncontended'] == {'taken': TW_T_CLS_TAKEN, 'not_taken': TW_T_CLS_OUT}, \
        OUT['cls_T_uncontended']

    # ------------------------------------------------ (f) '1' pressed MID-FRAME, ints ON
    mid = []
    for k8 in range(8):
        h.load_state(S0)
        r[IFF] = 1
        f0 = r[T] // fd
        ctl = {'press_at': (f0 + 6) * fd + (k8 * fd) // 8, 'press': ['1']}
        c = {'it': 0, 'dr': 0}

        def hook(p):
            if p == 0x9770:
                c['it'] += 1
            elif p == 0x9775:
                c['dr'] += 1
            return False
        g = go(h, TW_ARMS, ints=True, hook=hook, ctl=ctl)
        mid.append({'k': k8, 'press_T_in_frame': (k8 * fd) // 8, 'arm': r[PC],
                    'iterations': c['it'], 'draws': c['dr'], 'prng_at_arm': prng(m),
                    'T_press_to_arm': r[T] - ctl['pressed_T'], 'n_isr': g['nisr']})
    OUT['mid_frame'] = mid
    for x in mid:
        assert x['arm'] == 0x979E, x
        assert 0 <= x['T_press_to_arm'] < fd, x
    assert len({x['iterations'] for x in mid}) == 8, 'the exit does not move with the phase'
    #  the exit state is ON the orbit: iterations and draws say where
    for x in mid:
        s = P0
        for _ in range(x['draws']):
            s = prng_next(s)
        assert s == x['prng_at_arm'], x

    # ------------------------------------------------ (g) the REAL ISR across the paint, the
    #  start and the drain: 'gameover_wrap', 'paint', 'start_8d0c', 'drain'.
    #  go() refuses a HALT; $8CFB and $9887 are HALTs, so these legs use run_i(), which
    #  takes a HALT the harness's way (_fast_halt: the clock jumps to the interrupt
    #  window) and keeps one record per accepted ISR.  Milestones are keyed on the
    #  SOURCE PC at ARRIVAL (TRAPS #200).  The ISR audit (scratchpad isr_audit/s1, s3)
    #  stamped a milestone AFTER executing it (its on_step runs after the step); its
    #  numbers are reproduced in that convention first ('*_audit'), then the arrival ones
    #  are recorded beside them.
    def run_i(hh, stop=(), hook=None, post=None, limit=60_000_000):
        rr, op, mem = hh.sim.registers, hh.sim.opcodes, hh.sim.memory
        fdd, iaa = hh.frame_duration, hh.int_active
        isrs, cur, n = [], None, 0
        while True:
            p = rr[PC]
            assert not (TW_GUARD_LO <= p < TW_GUARD_HI), 'ENTERED THE GUARDED RANGE'
            if cur is not None and p == cur['ret'] and rr[SP] == cur['sp']:
                cur['cost'] = rr[T] - cur['t0']
                cur['b_post'] = mem[0x8DBD] | (mem[0x8DBE] << 8)
                isrs.append(cur)
                cur = None
            main = cur is None
            if main:
                if p in stop or (hook is not None and hook(p, len(isrs))):
                    break
            elif p in (0xA3AD, 0xAA60):
                cur['deep'].add(p)
            n += 1
            assert n < limit, 'run_i ran out at PC $%04X' % p
            acc = None
            if mem[p] == 0x76:
                assert rr[IFF], 'a HALT at $%04X with interrupts off' % p
                t = rr[T]
                t0 = t if t % fdd < iaa else (t // fdd + 1) * fdd
                sp0 = rr[SP]
                hh._fast_halt()
                if rr[PC] != (p + 1) & 0xFFFF:
                    acc = ((p + 1) & 0xFFFF, sp0, t0)
            else:
                op[mem[p]]()
                if rr[IFF] and rr[T] % fdd < iaa:
                    b, spb, t0 = rr[PC], rr[SP], rr[T]
                    if hh.sim.accept_interrupt(rr, mem, p):
                        acc = (b, spb, t0)
            if acc is not None:
                assert cur is None, 'an interrupt was accepted inside the ISR'
                cur = {'ret': acc[0], 'sp': acc[1], 't0': acc[2], 'phase': acc[2] % fdd,
                       'b_pre': mem[0x8DBD] | (mem[0x8DBE] << 8), 'deep': set()}
            if main and post is not None:
                post(p, len(isrs) + (1 if cur is not None else 0))
        assert cur is None, 'stopped inside the ISR'
        return isrs

    def ctr_a(mm):
        return mm[0x8DB6] | (mm[0x8DB7] << 8)

    def ctr_b(mm):
        return mm[0x8DBD] | (mm[0x8DBE] << 8)

    PAINT_M = (0x8D02, 0x96DF, 0x970E, TP_START, 0x9712, TP_MID, 0x9751, TP_END)
    PAINT_STAGES = (('cls', TP_START, 0x9712), ('starfield', 0x9712, TP_MID),
                    ('text', TP_MID, 0x9751), ('credit', 0x9751, TP_END))

    def paint(hh):
        """from ARRIVAL at $8D02 (SP $96DD, the real path) to the first arrival at $9765."""
        rr, mm = hh.sim.registers, hh.memobj.m
        assert rr[PC] == 0x8D02 and rr[SP] == 0x96DD and rr[IFF], (rr[PC], rr[SP], rr[IFF])
        arr, pst = {}, {}
        a0 = ctr_a(mm)

        def hook(p, k):
            if p in PAINT_M and p not in arr:
                arr[p] = (rr[T], k, ctr_b(mm))
            return p == TP_END

        def post(p, k):
            if p in PAINT_M and p not in pst:
                pst[p] = (rr[T], k)
        isrs = run_i(hh, hook=hook, post=post)
        assert rr[SP] == 0x96D9 and mm[0x96DB] | (mm[0x96DC] << 8) == OVER \
            and mm[0x96D9] | (mm[0x96DA] << 8) == TW_LAND, 'the $8D02 stack is not the real one'
        t_end = arr[TP_END][0]
        return {
            'tphase_at_8d02': arr[0x8D02][0] % fd, 'tphase_after_8d02_audit': pst[0x8D02][0] % fd,
            'T_total': t_end - arr[0x8D02][0], 'T_total_audit': t_end - pst[0x8D02][0],
            'T_970f_9765': t_end - arr[TP_START][0], 'T_970f_9765_audit': t_end - pst[TP_START][0],
            'T_stage': {s: arr[b][0] - arr[a][0] for s, a, b in PAINT_STAGES},
            'T_stage_audit': {s: (arr[b][0] if b == TP_END else pst[b][0]) - pst[a][0]
                              for s, a, b in PAINT_STAGES},
            'isrs_stage': {s: arr[b][1] - arr[a][1] for s, a, b in PAINT_STAGES},
            'isrs_to_970f': arr[TP_START][1], 'n_isr': len(isrs),
            'isr_phases': [x['phase'] for x in isrs], 'isr_ret': [x['ret'] for x in isrs],
            'isr_cost': sorted({x['cost'] for x in isrs}),
            'ctr_b_at_9765': ctr_b(mm), 'ctr_a_delta': (ctr_a(mm) - a0) & 0xFFFF,
            'ctr_a_at_8d02': a0, 'ctr_a_at_9765': ctr_a(mm),
            'fed3_at_9765': mm[0xFED3], 'prng_at_9765': prng(mm), 'sp_at_9765': rr[SP]}

    # ---- (g3) the natural game over on round1_48 (audit s1): both bit 7 clear, $FEC9 0
    hw = Harness(contended=True)
    hw.load_state_file(pc.state_path('round1_48'))
    mw, rw = hw.memobj.m, hw.sim.registers
    assert [mw[a] for a in CS_PATCH] == [0xC9] * 3
    mw[P1F] &= 0x7F
    mw[P2F] &= 0x7F
    mw[FEC9] = 0
    run_i(hw, stop=(OVER,))
    t_8cdc, a_8cdc, b_8cdc = rw[T], ctr_a(mw), ctr_b(mw)
    wl = {'8ce7': 0, 'fec4_5_at_8ce7': None}

    def hook(p, k):
        if p == 0x8CE7:
            wl['8ce7'] += 1
            if wl['fec4_5_at_8ce7'] is None:
                wl['fec4_5_at_8ce7'] = [mw[0xFEC4], mw[0xFEC5]]
        return p == 0x8D02
    isrs_w = run_i(hw, hook=hook)
    wrap_paint = paint(hw)
    S_WRAP_9765 = hw.save_state()
    OUT['gameover_wrap'] = {
        'from': 'round1_48, bit 7 of $FD87/$FD91 cleared, $FEC9 = 0 (isr_audit s1)',
        'tphase_at_8cdc': t_8cdc % fd, 'T_8cdc_to_8d02': rw[T] - t_8cdc - wrap_paint['T_total'],
        'loop_8ce7': wl['8ce7'], 'fec4_5_at_8ce7': wl['fec4_5_at_8ce7'],
        'isrs_8cdc_to_8d02': len(isrs_w),
        'isr_cost_8cdc_to_8d02': sorted({x['cost'] for x in isrs_w}),
        'ctr_a_at_8cdc': a_8cdc, 'ctr_b_at_8cdc': b_8cdc,
        'tphase_at_8d02': wrap_paint['tphase_at_8d02'], 'paint': wrap_paint}
    gw = OUT['gameover_wrap']
    #  the audit (s1.json), reproduced first -- in ITS convention (stamped after the step)
    assert gw['loop_8ce7'] == 76 and gw['isrs_8cdc_to_8d02'] == 76, gw
    assert gw['fec4_5_at_8ce7'] == [0, 0], gw
    assert wrap_paint['tphase_after_8d02_audit'] == 531, wrap_paint
    assert wrap_paint['T_total_audit'] == 639889, wrap_paint
    assert wrap_paint['T_970f_9765_audit'] == 639315, wrap_paint
    assert wrap_paint['T_stage_audit'] == {'cls': 187634, 'starfield': 386294, 'text': 60991,
                                           'credit': 4396}, wrap_paint
    assert wrap_paint['n_isr'] == 9 and wrap_paint['ctr_b_at_9765'] == 9, wrap_paint
    assert (wrap_paint['ctr_a_at_8d02'], wrap_paint['ctr_a_at_9765']) == (308, 317), wrap_paint
    assert wrap_paint['fed3_at_9765'] == 6 and wrap_paint['prng_at_9765'] == 0x5044, wrap_paint
    #  ... and then the arrival convention: LD HL,$8CDC is 10 T, so the phase is 521
    assert wrap_paint['tphase_at_8d02'] == 521 and wrap_paint['T_total'] == 639889 + 10, wrap_paint

    # ---- (g1) 'paint': round1_48 entered AT $8D02 (not the wrap).  The one thing the
    #  wrap does that this world needs is $8CDF LD ($FEC4),HL with HL = 0 -- round1_48 has
    #  $FEC4 = $14, and an ISR between $8D02 and $96DF's DI would run the entity pass.
    #  SP $96DD as $8CC4 leaves it; $8D05 PUSHes $8CDC and $8D06 CALLs $96DF for real.
    def entry(phase):
        hh = Harness(contended=True)
        hh.load_state_file(pc.state_path('round1_48'))
        mm, rr = hh.memobj.m, hh.sim.registers
        mm[0xFEC4], mm[0xFEC5] = 0, 0
        rr[SP], rr[PC], rr[IFF] = 0x96DD, 0x8D02, 1
        rr[T] = (rr[T] // fd + 2) * fd + phase
        return hh
    PH_NAT = wrap_paint['tphase_at_8d02']
    hp = entry(PH_NAT)
    main_paint = paint(hp)
    sweep = []
    for k8 in range(8):
        ph = (k8 * fd) // 8
        x = paint(entry(ph))
        sweep.append({'phase': ph, 'n_isr': x['n_isr'], 'T_total': x['T_total'],
                      'ctr_b_at_9765': x['ctr_b_at_9765'], 'isr_phases': x['isr_phases']})
    main_paint['world'] = 'round1_48 at $8D02: SP $96DD, IFF 1, $FEC4/5 = 0, T phase %d (the wrap\'s)' % PH_NAT
    main_paint['phase_sweep'] = sweep
    main_paint['n_isr_by_phase'] = [x['n_isr'] for x in sweep]
    main_paint['isr_count_varies'] = len({x['n_isr'] for x in sweep}) > 1
    main_paint['same_T_as_wrap'] = main_paint['T_total'] == wrap_paint['T_total']
    OUT['paint'] = main_paint
    assert main_paint['tphase_at_8d02'] == PH_NAT
    assert main_paint['n_isr'] == 9 and main_paint['ctr_b_at_9765'] == 9, main_paint
    assert main_paint['ctr_a_delta'] == 9 and main_paint['fed3_at_9765'] == 6, main_paint
    assert main_paint['isr_cost'] == [488, 493], main_paint           # audit s2: odd / even
    assert abs(main_paint['T_total'] - wrap_paint['T_total']) < 2000, main_paint

    # ---- (g2) 'start_8d0c' and (g4) 'drain': from $9765, key held 3 frames past the arm
    ST_M = (0x9790, 0x979E, 0x97AB, 0x97C7, TW_LAND, 0x97F8, 0x9884, 0x9887, 0x9888, 0x8D0C)
    AT_8D0C = [P1F, P2F, 0xFED3, 0x8609, 0xFDDA, 0xFDE4, 0xFEC4, 0xFEC5, 0xFE86, 0xFE87, 0xB54B]
    HOLD = 3

    def start(hh, key):
        rr, mm = hh.sim.registers, hh.memobj.m
        assert rr[PC] == TP_END
        rr[IFF] = 1
        b0, t0 = ctr_b(mm), rr[T]
        hh.ports.press(KEYMAP[key][0], keymask(KEYMAP[key][1]))
        arr, ctl = {}, {}

        def hook(p, k):
            if ctl.get('rel') is not None and rr[T] >= ctl['rel']:
                hh.ports.release_all()
                ctl['released_T'], ctl['rel'] = rr[T], None
            if p in ST_M and p not in arr:
                arr[p] = (rr[T], k, ctr_a(mm), ctr_b(mm), mm[0xFEC4])
                if p in TW_ARMS:
                    ctl['rel'] = rr[T] + HOLD * fd
            return p == 0x8D0C
        isrs = run_i(hh, hook=hook)
        arm = [a for a in TW_ARMS if a in arr]
        assert len(arm) == 1, arm
        A_ = arr[arm[0]]
        halt = [x for x in isrs if x['ret'] == 0x9888]
        assert len(halt) == 1, 'not exactly one ISR out of the $9887 HALT'
        hx = halt[0]

        def nisr(a, b):
            return arr[b][1] - arr[a][1]
        row = {
            'key': key, 'hold_frames': HOLD, 'arm': arm[0], 'ctr_b_at_9765': b0,
            'T_9765_to_arm': A_[0] - t0, 'held_T': ctl['released_T'] - A_[0],
            'isrs_arm_to_97c7': arr[0x97C7][1] - A_[1], 'isrs_97c7_to_97f8': nisr(0x97C7, 0x97F8),
            'isrs_97f8_to_8d0c': nisr(0x97F8, 0x8D0C), 'isrs_97f8_to_9888': nisr(0x97F8, 0x9888),
            'isrs_9888_to_8d0c': nisr(0x9888, 0x8D0C),
            'T_97f8_to_8d0c': arr[0x8D0C][0] - arr[0x97F8][0],
            'T_97f8_to_9887': arr[0x9887][0] - arr[0x97F8][0],
            'ctr_a_at_8d0c': ctr_a(mm), 'ctr_b_at_8d0c': ctr_b(mm),
            'ctr_b_at_9887': arr[0x9887][3], 'ctr_b_at_9887_parity': arr[0x9887][3] & 1,
            'halt_isr': {'ctr_b_new': hx['b_post'], 'new_parity': hx['b_post'] & 1,
                         'cost': hx['cost'], 'phase': hx['phase'],
                         'ran_a3ad': 0xA3AD in hx['deep'], 'ran_aa60': 0xAA60 in hx['deep'],
                         'fec4_at_9887': arr[0x9887][4]},
            'at_8d0c': {'$%04X' % a: mm[a] for a in AT_8D0C},
            'players_fddb_e0': [mm[a] for a in range(0xFDDB, 0xFDE1)],
            'players_fde5_ea': [mm[a] for a in range(0xFDE5, 0xFDEB)],
            'prng_at_8d0c': prng(mm), 'tphase_at_8d0c': arr[0x8D0C][0] % fd,
            'milestones': {'$%04X' % a: [arr[a][0] - t0, arr[a][1], arr[a][3]]
                           for a in ST_M if a in arr},
            'milestones_note': '[T since $9765, ISRs so far, counter B] at first arrival'}
        return row
    starts = []
    for key in ('1', '2'):
        h.load_state(S0)
        starts.append(dict(start(h, key), world='S0 (GROUP 1 drive, ints OFF paint: counter B 0)'))
    for key in ('1', '2'):
        hw.load_state(S_WRAP_9765)
        starts.append(dict(start(hw, key), world='gameover_wrap at $9765 (ints ON paint: counter B 9)'))
    OUT['start_8d0c'] = starts
    for x in starts:
        assert x['arm'] == (0x979E if x['key'] == '1' else 0x9790), x
        #  $9888 / $988E zero both counters; every ISR after it counts from zero
        assert x['ctr_b_at_8d0c'] == x['isrs_9888_to_8d0c'] == x['ctr_a_at_8d0c'], x
        assert x['at_8d0c']['$FED3'] == 5, x
        #  the audit's rule: an ODD new counter B at the HALT ISR opens $A3AD + $AA60
        assert x['halt_isr']['ran_a3ad'] == x['halt_isr']['ran_aa60'] == bool(
            x['halt_isr']['new_parity']), x
        assert x['halt_isr']['ctr_b_new'] == x['ctr_b_at_9887'] + 1, x
        assert x['isrs_97c7_to_97f8'] == 0 and x['isrs_97f8_to_9888'] == 11, x
    #  the audit's HALT-ISR costs (s3: 13,514 T for '1', 16,594 T for '2' on an ODD
    #  counter; 493 T on an even one) and its key-'2' drain of 63 (s3_2_31) -- reproduced
    #  on the wrap's world, whose counter B is 9 at $9765 as on the machine
    assert [(x['halt_isr']['cost'], x['isrs_97f8_to_8d0c']) for x in starts] == \
        [(493, 61), (493, 62), (13514, 61), (16594, 63)], starts
    #  the ISR count across the paint moves with the entry phase: phase 0 takes one
    #  before $96DF's DI
    assert main_paint['n_isr_by_phase'] == [10, 9, 9, 9, 9, 9, 9, 9], main_paint['n_isr_by_phase']

    d1 = starts[0]
    OUT['drain'] = {
        'path': "key '1', S0 world, $97F8 -> first $8D0C",
        'isrs_97f8_to_8d0c': d1['isrs_97f8_to_8d0c'], 'isrs_before_9888': d1['isrs_97f8_to_9888'],
        'isrs_after_9888': d1['isrs_9888_to_8d0c'], 'T_97f8_to_8d0c': d1['T_97f8_to_8d0c'],
        'b54b_at_8d0c': d1['at_8d0c']['$B54B'],
        'by_world_key': [['S0' if x['world'].startswith('S0') else 'wrap', x['key'], x['isrs_97f8_to_9888'], x['isrs_9888_to_8d0c']]
                         for x in starts],
        'by_world_key_note': '[world, key, ISRs $97F8..$9888, ISRs $9888..$8D0C]; for key 2 '
                             'the drain is 62 on an even HALT counter (S0) and 63 on an odd one '
                             '(the wrap) -- the parity leak reaches the drain length on 2P'}
    dr = OUT['drain']
    #  audit s3 (natural title, N 30 / 31, key '1'): 61 = 11 + 50, $B54B already 0
    assert (dr['isrs_97f8_to_8d0c'], dr['isrs_before_9888'], dr['isrs_after_9888']) == (61, 11, 50), dr
    assert dr['b54b_at_8d0c'] == 0, dr

    # ------------------------------------------------ report
    print('$9765..$97EA -- the ring, the key wait, the release wait (GROUP 2)')
    print('    world round1_48 == GROUP 1 title drive at $9765: %s; PRNG $%04X (recon world $%04X'
          ' -> $%04X); $FED3 %d by %s; T phase %d'
          % (same_as_group1, P0, pn, OUT['recon_world']['prng_at_arm'], OUT['world']['fed3_at_9765'],
             ['$%04X' % a for a in fed3_writers], OUT['world']['tphase_at_9765']))
    print('    (a) 400 rows: %d skips, %d writes; PRNG after 400 $%04X'
          % (OUT['ring']['skips'], OUT['ring']['writes'], after[-1]))
    print('    (b) bit 6: %s / %s' % (wit['laps2'], wit['laps100']))
    for e in exits:
        print('    (c) %-5s arm %s it %d draws %d PRNG $%04X FED3 %d->%d FD87 %02X FD91 %02X %s'
              % (e['keys'], e['arm'] and '$%04X' % e['arm'], e['iterations'], e['draws'],
                 e['prng_at_arm'], e['fed3_before'], e['fed3_after'], e['fd87'], e['fd91'],
                 ('cls %d census %d disp %d land $%04X' % (e['cls_entries'], len(e['census']),
                  e['display_writes'], e['land_pc'])) if e['arm'] else ''))
    for x in rel:
        print('    (d) ints %d N %2d: cls %d done %d/%d pass %s arm->97C7 %d T (%d frames) '
              'isr %d' % (x['ints'], x['n'], x['cls'], x['completed_held'], x['completed'],
                          x['pass_T'], x['T_arm_to_97c7'], x['frames_arm_to_97c7'], x['n_isr']))
    print('    (e) %d frames: iters/frame min %d max %d mean %.3f; ISR %d, T %s, writes %s, '
          'stack %s' % (pf['frames'], pf['min'], pf['max'], pf['mean'], pf['n_isr'],
                        pf['isr_T'], ['$%04X' % a for a in isr_w], pf['isr_stack']))
    print('    path T: %s' % OUT['path_T'])
    print('    CLS uncontended: %s' % OUT['cls_T_uncontended'])
    for x in mid:
        print('    (f) k %d: it %d draws %d PRNG $%04X latency %d T' %
              (x['k'], x['iterations'], x['draws'], x['prng_at_arm'], x['T_press_to_arm']))
    for nm, x in (('wrap', wrap_paint), ('paint', main_paint)):
        print('    (g) %-5s $8D02 phase %d: %d T (audit conv. %d), $970F->$9765 %d, stages %s, '
              'ISR %d %s, B %d, A +%d' % (nm, x['tphase_at_8d02'], x['T_total'], x['T_total_audit'],
                                          x['T_970f_9765'], x['T_stage'], x['n_isr'],
                                          x['isrs_stage'], x['ctr_b_at_9765'], x['ctr_a_delta']))
    print('    (g) wrap: $8CE7 x%d, ISR by entry phase %s' % (gw['loop_8ce7'], main_paint['n_isr_by_phase']))
    for x in starts:
        print('    (g) start %s [%s] ISR arm->97C7 %d 97C7->97F8 %d 97F8->8D0C %d (%d+%d) %d T; '
              'B@9887 %d HALT-ISR %d T A3AD %s; A/B@8D0C %d/%d'
              % (x['key'], x['world'][:2], x['isrs_arm_to_97c7'], x['isrs_97c7_to_97f8'],
                 x['isrs_97f8_to_8d0c'], x['isrs_97f8_to_9888'], x['isrs_9888_to_8d0c'],
                 x['T_97f8_to_8d0c'], x['ctr_b_at_9887'], x['halt_isr']['cost'],
                 x['halt_isr']['ran_a3ad'], x['ctr_a_at_8d0c'], x['ctr_b_at_8d0c']))
    return OUT


def phase_writers():
    """the NEGATIVE: how many places in 64K can write $FEC9 at all.  A raw byte
       census over `32 C9 FE` finds operands as readily as opcodes (TRAPS #68),
       so every hit is disassembled back one byte and checked for the $32."""
    h, m = new('round1_48')
    hits = h.find_bytes(bytes([0x32, 0xC9, 0xFE]), 0x4000, 0x10000)
    real = [a for a in hits if m[a] == 0x32]
    # AND THE FORM THE FIRST CENSUS CANNOT SEE: $8CFC writes it through HL
    # (LD HL,$FEC9 / INC (HL)), which no `32 C9 FE` scan finds.  Counting only
    # the direct stores says TWO writers and the answer is THREE.
    ptr = [a for a in h.find_bytes(bytes([0x21, 0xC9, 0xFE]), 0x4000, 0x10000)
           if m[a] == 0x21]
    return {'raw_hits': ['$%04X' % a for a in hits],
            'direct_writers': ['$%04X' % a for a in real],
            'pointer_loads': ['$%04X' % a for a in ptr],
            'writers': ['$%04X' % a for a in real] + ['$%04X' % a for a in ptr],
            'note': 'a `32 C9 FE` census finds the DIRECT stores only; $8CFC '
                    'loads the address into HL and INCs through it, so a mask '
                    'or byte-pair scan reports two writers where there are three'}


# ---------------------------------------------------------------- phase F
def phase_two_players():
    """$97D2 runs TWICE: once by CALL with IY = $FD80 and once by FALL-THROUGH
       with IY = $FD8A.  A call-graph scan finds ONE call site and concludes one
       player is initialised.  Both structs are seeded to values the routine does
       not write, and BOTH are asserted."""
    h, m = new('round1_48')
    fields = [0x5C, 0x5F, 0x60, 0x5E, 0x5D, 0x5B]
    want = {0x5C: 3, 0x5F: 7, 0x60: 0, 0x5E: 8, 0x5D: 8, 0x5B: 2}
    for base in (0xFD80, 0xFD8A):
        for f in fields:
            m[base + f] = 0x5A
    h.sim.registers[SP] = 0x96DD
    h.call(0x97C7, limit=100000)
    out = {}
    for name, base in (('p1_$FD80', 0xFD80), ('p2_$FD8A', 0xFD8A)):
        out[name] = {'$%02X' % f: m[base + f] for f in fields}
    out['expected'] = {'$%02X' % f: want[f] for f in fields}
    out['seed'] = 0x5A
    return out


# ---------------------------------------------------------------- phase G
def phase_patches():
    """$9690's three 48K RET patches are LIVE STATE, not code: $8DC4, $8E05 and
       $8E0A get $C9 on a 48K machine and keep their real opcode on a 128K one.
       Every tool in this repo already gates on the first of them."""
    h, m = new('round1_48')
    return {'$8DC4': m[0x8DC4], '$8E05': m[0x8E05], '$8E0A': m[0x8E0A],
            'tape_bytes': _tape_at((0x8DC4, 0x8E05, 0x8E0A))}


def _tape_at(addrs):
    with open('build/image_tape.bin', 'rb') as f:
        img = f.read()
    return {'$%04X' % a: img[a] for a in addrs}


# ---------------------------------------------------------------- phase H
def phase_join():
    """$9961 -- THE MID-GAME JOIN, and the three RETs in front of it.

       `LD A,($FED3) / OR A / RET z / RET m`: no credits, no join.  Then half-row
       $F7 is read ONCE and rotated TWICE -- bit 0 ('1') goes to $999B and P1,
       bit 1 ('2') falls on to $9970 and P2 -- and BOTH branches meet at $9980,
       where `DEC (HL)` takes ONE credit.  "A two-player start costs two credits"
       is the natural reading and it is wrong.

       The CONTROL is the same key with ($FED3) = 0."""
    rows = []
    for (name, key, mask, credits, out_bit7, cut) in (
            ('p2 joins',        '2', 0xFD, 6, None,   False),
            ('p2 joins, no tail','2', 0xFD, 6, None,  True),
            ('p2, no credit',   '2', 0xFD, 0, None,   False),
            ('p1 joins',        '1', 0xFE, 6, 0xFD87, False),
            ('p1 joins, no tail','1', 0xFE, 6, 0xFD87, True),
            ('no key',          '-', 0xFF, 6, None,   False)):
        h, m = new('round1_48')
        if cut:
            # $9998 JP $7FC0 is a TAIL JUMP into the whole HUD repaint, which
            # RRD-converts both players' score records on its way past.  Cutting
            # it to a RET is the control that separates what the JOIN writes
            # from what the HUD does afterwards.
            m[0x9998] = 0xC9
        m[0xFED3] = credits
        if out_bit7 is not None:
            m[out_bit7] &= 0x7F               # P1 is OUT, so '1' can bring it back
        for a in range(0xFFE5, 0xFFF1):
            m[a] = 0x5A                       # a value neither clear writes
        for base in (0xFD80, 0xFD8A):
            m[base + 0x5C] = 0x5A
            m[base + 4] = 0x5A
        if mask != 0xFF:
            h.ports.press(0xF7, mask)
        h.sim.registers[SP] = 0x96DD
        h.call(0x9961, limit=200000)
        rows.append({'case': name, 'key': key, 'tail_cut': cut,
                     'credits_before': credits,
                     'credits_after': m[0xFED3],
                     'p1_flags': m[0xFD87], 'p2_flags': m[0xFD91],
                     'p1_lives': m[0xFD80 + 0x5C], 'p2_lives': m[0xFD8A + 0x5C],
                     'p1_timer': m[0xFD80 + 4], 'p2_timer': m[0xFD8A + 4],
                     'p1_score': [m[0xFFE5 + i] for i in range(4)],
                     'p2_score': [m[0xFFE9 + i] for i in range(4)],
                     'beyond': [m[0xFFED + i] for i in range(4)]})
    return rows


def phase_7fc0_refs():
    """THE CORRECTION.  web/game.js says of $7FC0: "its sole reference in both
       images is `CC C0 7F` (CALL z), so A PORT THAT NEVER BUILDS ROUND 1 HAS NO
       HUD AT ALL".  A census of the ADDRESS rather than of one opcode form finds
       TWO: $7F58 CALL z,$7FC0 and $9998 JP $7FC0 -- the mid-game join's tail
       jump.  The HUD score is therefore repainted whenever a second player
       joins, on ANY round, and "round 1 only" is false."""
    h, m = new('round1_48')
    names = {0xCD: 'CALL', 0xCC: 'CALL z', 0xC4: 'CALL nz', 0xC3: 'JP',
             0xCA: 'JP z', 0xC2: 'JP nz'}
    hits = h.find_bytes(bytes([0xC0, 0x7F]), 0x4000, 0x10000)
    out = []
    for a in hits:
        op = m[a - 1]
        out.append({'at': '$%04X' % (a - 1), 'opcode': op,
                    'form': names.get(op), 'is_reference': op in names})
    return {'hits': out,
            'references': [r['at'] + ' ' + r['form'] for r in out if r['is_reference']]}


# ---------------------------------------------------------------- phase I
def phase_start_states():
    """WHAT A STARTED GAME LOOKS LIKE, and what it cost.

       `afterctrl48` is the front end: six credits, every player byte zero.
       `round1_48` and `round1_2p48` are games in progress -- and BOTH have FIVE
       credits.  Two players cost ONE credit, which is the same fact $9980's
       single `DEC (HL)` states in the join and is worth having from a captured
       world as well as from a driven one.

       It is also the measurement that keeps $8E2A OUT of the port's chain for
       now: the port's reset() world has $FD87 = $FD91 = $00, so wiring the
       trigger would end every game on the first pass -- faithfully, for a world
       the machine is never in."""
    out = {}
    for st in ('afterctrl48', 'round1_48', 'round1_2p48'):
        h, m = new(st)
        out[st] = {'credits': m[0xFED3], 'p1_flags': m[0xFD87], 'p2_flags': m[0xFD91],
                   'p1_sprite': m[0xFD80] | (m[0xFD81] << 8),
                   'p1_x': m[0xFD85], 'p1_y': m[0xFD86],
                   'p1_5b': m[0xFDDB], 'p1_lives': m[0xFDDC],
                   'in_play': [bool(m[0xFD87] & 0x80), bool(m[0xFD91] & 0x80)]}
    return out


# ---------------------------------------------------------------- phase M7.31a
def phase_glyphs():
    """THE GLYPH RUN AT CODE AND ROW LEVEL, which phase_screen() cannot see.

    phase_screen() counts CHANGED CELLS over $4000..$5B00 and that was the right
    measurement for a declared gap: the engine drew none, so a count was enough
    to say how many it owed.  Drawing them needs the ordered list -- which
    display address, which character code, which row of the glyph -- and that
    only comes from watching $8052 the way every other banner oracle does.

    Interrupts OFF and $8CE7 entered directly, so the HALT is never reached and
    nothing but the routine writes.
    """
    h, m = new('round1_48')
    r = h.sim.registers
    #  POISON, wider than the run: all 32 columns of character row 10 and the
    #  whole attribute row.  NOT all of $4000..$5B00 -- that would delete the
    #  string at $9A95 nothing, but it would also hide a write outside the row,
    #  and TRAPS #159 was a gate that wiped 64K and deleted what it then read.
    base = 0x484C & 0xF8E0
    row = [(base | (px << 8) | col) & 0xFFFF
           for px in range(8) for col in range(32)]
    for a in row:
        m[a] = 0xFF
    for col in range(32):
        m[(0x594C & 0xFFE0) | col] = 0xFF

    h.sim.registers[SP] = 0x8CE5          # a scratch stack below the routine
    glyphs, attrs = [], []
    r[PC] = 0x8CE7
    n = 0
    while n < 4 * 10 ** 6:
        p = r[PC]
        if p == 0x8CFB:                   # the HALT: the pass is over
            break
        if p == 0x8052:                   # $802E's blit, as every banner reads it
            glyphs.append([r[7] | (r[6] << 8), r[5] | (r[4] << 8)])
        elif p == 0x995C:                 # $995A's store
            attrs.append([r[7] | (r[6] << 8), r[0]])
        h.step(1, interrupts=False)
        n += 1
    else:
        raise SystemExit('never reached the HALT -- PC $%04X' % r[PC])

    codes, i = [], 0x9A95
    while m[i]:
        codes.append(m[i])
        i += 1
    touched = set(a for a, _ in glyphs) | set(a for a, _ in attrs)
    stray = [a for a in row if a not in touched and m[a] != 0xFF]
    gcols = sorted(set(a & 0x1F for a, _ in glyphs))
    acols = sorted(set(a & 0x1F for a, _ in attrs))
    #  the character row each address sits in, so "same row" is measured and not
    #  inferred from the two constants looking alike
    def charrow(a):
        return ((a >> 8) & 7) * 0 + (((a >> 11) & 3) * 8) + (((a >> 5) & 7))
    grows = sorted(set(charrow(a) for a, _ in glyphs))
    arow = sorted(set(((a - 0x5800) >> 5) for a, _ in attrs))
    out = {
        'codes': codes, 'text': ''.join(chr(c) for c in codes),
        'writes': len(glyphs), 'cells': len(attrs),
        'glyphs': [{'at': '%04X' % a, 'code': ((de - 0x3C00) & 0xFFFF) // 8,
                    'row': ((de - 0x3C00) & 0xFFFF) % 8} for a, de in glyphs],
        'attrs': [['%04X' % a, v] for a, v in attrs],
        'glyph_cols': gcols, 'attr_cols': acols,
        'glyph_rows': grows, 'attr_rows': arow,
        'stray': ['%04X' % a for a in stray],
        'ix_after': '%04X' % (r[IXl] | (r[IXh] << 8)),
        'same_place': gcols == acols and grows == arow,
        'exact': len(attrs) == len(codes),
    }
    print('glyphs: %r -- %d characters, %d display writes, %d attribute cells '
          '$%s..$%s all $%02X, IX left at $%s'
          % (out['text'], len(codes), len(glyphs), len(attrs),
             out['attrs'][0][0], out['attrs'][-1][0], out['attrs'][0][1],
             out['ix_after']))
    print('        columns: glyphs %s rows %s / attributes %s rows %s -- %s'
          % (gcols, grows, acols, arow,
             '*** SAME PLACE, AND NINE CELLS UNDER NINE CHARACTERS ***'
             if out['same_place'] and out['exact'] else '*** NOT ALIGNED ***'))
    print('        %d stray writes in the poisoned row outside the two runs' % len(stray))
    return out


# ---------------------------------------------------------------- phase M7.31b
def phase_handcoded():
    """THE COUNT-VERSUS-LENGTH TABLE FOR THE HAND-CODED $995A SITES.

    *** THIS PHASE EXISTS TO FALSIFY A GENERALISATION AND ITS FIRST VERSION MADE
    THE SAME ONE. ***  M7.30 wrote that the off-by-one "belongs to the hand-coded
    call sites", from $8E83's 11-for-10 and $9760's 9-for-8 against the $9A85
    table's four-for-four.  M7.31 added $8CF6's 9-for-9 and said ONE OF THREE.
    There are SIX.  The three I had not named -- $98CA, $98DA and $9948 -- are all
    exact, so it is FOUR OF SIX, and the generalisation was wrong twice in a row
    in the same increment (TRAPS #169).

    So this does not take a list of pairs on trust.  It ENUMERATES every entry to
    $995A -- `CALL` and `JP`, because $A04B and $A08D reach it by jump and a
    `CD 5A 99` census cannot see them -- pairs each with its `LD B,n`, and then
    ASSERTS that the number of TEXT sites equals the number of rows in the table.
    A seventh site cannot hide behind my typing.

    AND THE ASSERT EARNED ITS PLACE ON ITS FIRST RUN: it named $9074, which
    neither I nor the verification pass had.  $9071/$9074 colours the SAME ten
    cells as $9948 -- the hurry-up banner has two runs on one strip, one to paint
    it and one to FLASH it from $9068's border loop, with the colour living in the
    operand at $9077 ($8CF6's neighbour idiom).  Ten for ten: exact.

    SEVEN SITES, FIVE EXACT.  The sequence of claims about this one property reads
    M7.30 "it belongs to the hand-coded sites" (from 2 of 3), M7.31 "1 of 3", a
    verification pass "4 of 6", and the assert "5 of 7".  Four numbers, three
    wrong, and the only one that came from an enumeration instead of a list I typed
    is the last.

    AND NO STORY IS ATTACHED TO THE COUNT.  "Ten-character strings are exact and
    odd lengths carry a spare" is the obvious pattern and it is FALSE: $8E83 loads
    ELEVEN for the ten characters of "WELL DONE!".  Five of seven are exact; the
    two that are not are the boss banner and the credit line; nothing about the
    strings separates them from the five that are.  That is the whole finding, and
    it is a count with no narrative attached on purpose.
    """
    h, m = new('round1_48')
    calls = [a for a in h.find_bytes(bytes([0xCD, 0x5A, 0x99]), 0x4000, 0x10000)
             if m[a] == 0xCD]
    jumps = [a for a in h.find_bytes(bytes([0xC3, 0x5A, 0x99]), 0x4000, 0x10000)
             if m[a] == 0xC3]
    sites = []
    for a in sorted(calls + jumps):
        #  walk back for the LD B,n that feeds the DJNZ at $995E
        b_at = n_cells = None
        for back in range(2, 14):
            if m[a - back] == 0x06:
                b_at, n_cells = a - back, m[a - back + 1]
                break
        #  ...and the LD HL,nn that gives the attribute address
        hl_at = attr = None
        for back in range(3, 20):
            if m[a - back] == 0x21:
                hl_at, attr = a - back, m[a - back + 1] | (m[a - back + 2] << 8)
                break
        sites.append({'entry': '%04X' % a,
                      'form': 'JP' if m[a] == 0xC3 else 'CALL',
                      'ld_b_at': None if b_at is None else '%04X' % b_at,
                      'cells': n_cells,
                      'attr': None if attr is None else '%04X' % attr})

    #  THE PAIRS, each one a `LD B,n` address and the string whose glyphs the run
    #  colours.  Two of the six do not name their string: $98DA prints the chain
    #  $802E's own `INC IX` carried past $9A06's NUL, and $9948 is reached through
    #  $9940's bracket from $910D.  The DISPLAY address is what pairs them --
    #  $594C under $484C, $598C under $488C.
    PAIRS = (
        (0x98CA, 0x9A06, '$98C4 round banner, row 1'),
        (0x98DA, 0x9A11, '$98D4 round banner, row 2 -- IX CHAINED, not named'),
        (0x9948, 0x9A1C, '$910D hurry-up, through $9940 -- COMPUTED address'),
        (0x9074, 0x9A1C, '$9068 hurry-up FLASH, same ten cells, $9077 operand'),
        (0x8CF6, 0x9A95, '$8CEE game over'),
        (0x8E83, 0x9A27, '$8E9D boss banner'),
        (0x9760, 0x9AB8, '$9758 credit line'),
    )
    table = []
    for ld_b, sptr, who in PAIRS:
        assert m[ld_b] == 0x06, 'not an LD B,n at $%04X' % ld_b
        t, i = '', sptr
        while m[i]:
            t += chr(m[i])
            i += 1
        table.append({'ld_b': '%04X' % ld_b, 'string': '%04X' % sptr, 'who': who,
                      'text': t, 'length': len(t), 'cells': m[ld_b + 1],
                      'slack': m[ld_b + 1] - len(t),
                      'exact': m[ld_b + 1] == len(t)})

    #  *** THE ASSERT THAT WOULD HAVE CAUGHT THE FIRST VERSION. ***  Every site
    #  whose B comes from an immediate is a fixed-width run; the ones that take B
    #  from memory ($A04B and $A08D read ($FDF2)) are not text banners.  The
    #  number of immediate-B sites must equal the number of pairs.
    immediate = [x for x in sites if x['ld_b_at'] is not None]
    named = set(x['ld_b'] for x in table)
    found = set(x['ld_b_at'] for x in immediate)
    missing = sorted(found - named)
    assert not missing, ('$995A sites with an immediate B that the table does not '
                         'name: %r -- enumerate them before claiming a pattern'
                         % missing)
    assert len(immediate) == len(table), ('%d immediate-B sites, %d pairs'
                                          % (len(immediate), len(table)))

    n_exact = sum(1 for r in table if r['exact'])
    out = {'sites': sites, 'n_entries': len(sites),
           'n_call': len(calls), 'n_jump': len(jumps),
           'table': table, 'n_exact': n_exact, 'n_sites': len(table),
           'all_exact': n_exact == len(table),
           'hand_coded_is_off_by_one': False,
           'ten_char_story_holds': all(r['exact'] == (r['length'] == 10)
                                       for r in table)}
    print('$995A: %d entries -- %d CALL + %d JP (%s reach it by jump, and a '
          '`CD 5A 99` census cannot see them)'
          % (len(sites), len(calls), len(jumps),
             ', '.join('$' + x['entry'] for x in sites if x['form'] == 'JP')))
    for r in table:
        print('        LD B at $%s  %-12r length %2d  cells %2d  %-8s %s'
              % (r['ld_b'], r['text'], r['length'], r['cells'],
                 'EXACT' if r['exact'] else 'SLACK %+d' % r['slack'], r['who']))
    print('        -> %d of %d EXACT.  M7.30 said the off-by-one BELONGED to the '
          'hand-coded sites; M7.31 first said 1 of 3 because it enumerated three '
          'of six, and the ASSERT BELOW found the seventh (TRAPS #169).'
          % (n_exact, len(table)))
    print('        -> and the obvious pattern is FALSE: "ten characters are exact" '
          'fails on $8E83, eleven cells for the ten of "WELL DONE!".  A count with '
          'no story: %s' % ('story holds' if out['ten_char_story_holds']
                            else '%d of %d, and nothing separates the two that are not'
                            % (n_exact, len(table))))
    return out


# ---------------------------------------------------------------- phase M7.31c
def phase_802e_refs():
    """EVERY REFERENCE TO $802E IN THE IMAGE, so "nine" is data and not a label.

    TRAPS #165: the claim "$8EA7 is the last $802E call site" was counted from
    BB_BANNER_STR -- the port's own record of what it draws -- instead of from
    the image, and it was wrong by four.  The row that replaced it states NINE,
    and that nine was still a constant typed into a string.  It is measured now.

    BOTH FORMS, because $8EA7 reaches the printer by `JP $802E`: a census of
    `CD 2E 80` alone finds eight of the nine.  Same shape as phase_writers'
    `32 C9 FE`, which finds two of $FEC9's three writers.
    """
    h, m = new('round1_48')
    calls = [a for a in h.find_bytes(bytes([0xCD, 0x2E, 0x80]), 0x4000, 0x10000)
             if m[a] == 0xCD]
    jumps = [a for a in h.find_bytes(bytes([0xC3, 0x2E, 0x80]), 0x4000, 0x10000)
             if m[a] == 0xC3]
    refs = sorted(calls + jumps)
    out = {'calls': ['%04X' % a for a in calls],
           'jumps': ['%04X' % a for a in jumps],
           'refs': ['%04X' % a for a in refs],
           'n': len(refs), 'n_call_only': len(calls)}
    print('$802E: %d references -- %d CALL %s + %d JP %s'
          % (len(refs), len(calls), out['calls'], len(jumps), out['jumps']))
    print('        a `CD 2E 80` census alone would find %d of %d'
          % (len(calls), len(refs)))
    return out


def main():
    fx = {
        'meta': {'note': 'every shipped state has a player in play, so the '
                         'trigger is BUILT and paired with a control'},
        'census': phase_inplay_census(),
        'trigger': phase_trigger(),
        'countdown': phase_countdown(),
        'screen': phase_screen(),
        'glyphs': phase_glyphs(),          # M7.31
        'handcoded': phase_handcoded(),    # M7.31
        'refs_802e': phase_802e_refs(),    # M7.31
        'reset': phase_reset(),
        'title_cls': phase_title_cls(),    # front-end increment A (M7.38)
        'cold': phase_cold_start(),        # front-end increment G (M7.40)
        'title_paint': phase_title_paint(),  # front-end GROUP 1 oracle (M7.41)
        'title_wait': phase_title_wait(),    # front-end GROUP 2 oracle (C + D)
        'writers': phase_writers(),
        'two_players': phase_two_players(),
        'patches': phase_patches(),
        'join': phase_join(),
        'refs_7fc0': phase_7fc0_refs(),
        'start_states': phase_start_states(),
    }
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    c = fx['census']
    print('census: %d states on the 48K branch, %d with a player IN PLAY, '
          'both-clear in %s' % (c['states'], c['in_play'], c['both_clear'] or 'NONE'))
    for r in fx['trigger']:
        print('  %-10s armed=%-5s -> $8CDC %-5s at frame %-5s SP %s'
              % (r['state'], r['armed'], r['reached_8cdc'], r['frames'], r['sp_hex']))
    print('countdown:', [(hex(r['seed']), r['halts'], r['expected'])
                         for r in fx['countdown']])
    print('screen:', fx['screen']['changed_cells'], 'cells,',
          fx['screen']['attr_changed'], '=', list(fx['screen']['attr_values'].values()))
    print('reset:', fx['reset']['after'])
    print('  high score before/after:', fx['reset']['high_before'],
          fx['reset']['high_after'])
    print('$FEC9 writers:', fx['writers']['writers'],
          '(direct', fx['writers']['direct_writers'],
          '+ through HL', fx['writers']['pointer_loads'], ')')
    print('$97D2 both structs:', fx['two_players'])
    print('$9690 patches:', fx['patches'])
    for r in fx['join']:
        print('  join %-14s credits %d->%s  FD87 %02X FD91 %02X  lives %s/%s  '
              'scores %s %s' % (r['case'], r['credits_before'], r['credits_after'],
              r['p1_flags'], r['p2_flags'], r['p1_lives'], r['p2_lives'],
              r['p1_score'], r['p2_score']))
    print('$7FC0 references:', fx['refs_7fc0']['references'])
    for k, v in fx['start_states'].items():
        print('  %-12s credits %d  in play %s' % (k, v['credits'], v['in_play']))


if __name__ == '__main__':
    main()
