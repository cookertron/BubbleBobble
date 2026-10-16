"""B3 -- THE BOSS TICK: gates, divider, move frame, bounce, spawn.

WHAT THE BODY ACTUALLY IS.  `$AA0E` erases four rows at the LIVE `$A839`, bounces
X through `$AA38` with (DE = `$AA47`, HL = `$A8DB`, C = 2, B = 27), bounces Y with
(DE = `$AA48`, HL = `$A839`, C = 3, B = 20), draws, and then asks `$A969` whether
the boss is touching a player.  So the box `X in [2,26]`, `Y in [3,19]` is two
register pairs, not two constants -- and this oracle reads it off the MACHINE by
watching the coordinates move, so that a port with the right numbers in the
wrong pair still fails.

THE THREE THINGS A CAPTURE CANNOT SHOW:

  * `$A839` is BOTH the boss's row AND its presence flag, so `build/boss.pkl`
    (which holds 9) can never take the spawn arm.  `build/bossspawn.pkl` can.
  * `$AA47`/`$AA48` are the two bytes in front of `$AA49`, and disassembling from
    them invents `LD BC,$AF01` -- they are DATA.  NOTHING INITIALISES THEM: not
    the round build, not the spawn.  Proved by an 81-round chained build carrying
    POISONED velocities ($03/$FD), which survive the build AND the spawn and then
    step three tiles a tick.
  * `$A8DC` has no writer anywhere in 64K and is still the high byte of the
    16-bit offset at `$A8DA LD BC,0` -- BUILT here, because a byte nobody writes
    cannot be measured by watching.

AND ONE PAIR OF MODELS THAT ARE BEHAVIOURALLY IDENTICAL: "dy defaults to -1" and
"dy defaults to +1".  The spawn puts Y at its LOW bound, so `$FF` bounces before
the first store and both give the same 150 frames.  Recorded so that nobody
"fixes" the engine into disagreeing with a fact that has no observable side.

Usage:  python tools/bosstick.py     (capture -> build/bosstick_fixture.json)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bosstick_fixture.json'
BRANCH_BYTE = 0x8DC4
TICK = 0xA9ED           # the chain's CALL at $8D2E
BODY = 0xAA0E           # past $AA0D RET nz -- the move frame
AFTER = 0xAA29          # both bounces done, before the draw
BOUNCE = 0xAA38
SPAWN = 0xA84D
ADVANCE = 0x97F8

BOSS_Y = 0xA839         # the ROW -- and the presence flag
BOSS_X = 0xA8DB         # the COLUMN (low byte of a 16-bit offset)
BOSS_XH = 0xA8DC        # ...and its HIGH byte, which nothing writes
DX, DY = 0xAA47, 0xAA48
DIVIDER = 0xAA06
INVOL = 0xAA00
SPRITE = 0xA85C         # $A85B LD A,n -- n IS $A85C, and $A84E writes it


def new(state='boss', contended=True):
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
    return sp


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
def phase_track(state='boss', nframes=900):
    """the coordinates read off the machine, one row per BODY, so the box comes
       from watching the boss move rather than from reading $AA38's operands."""
    h, m = new(state)
    rows, st = [], {'passes': 0}

    def watch(p, f, m=m, st=st, rows=rows):
        if p == 0x8D25:
            st['passes'] += 1
        elif p == BODY:
            st['pre'] = [f, st['passes'], m[BOSS_X], m[BOSS_Y], m[DX], m[DY]]
        elif p == AFTER and 'pre' in st:
            rows.append(st.pop('pre') + [m[BOSS_X], m[BOSS_Y], m[DX], m[DY]])
        return False

    frames(h, nframes, watch)
    xs = [r[6] for r in rows]
    ys = [r[7] for r in rows]
    fl = [(rows[i][4] != rows[i][8], rows[i][5] != rows[i][9]) for i in range(len(rows))]
    # the HEAD is mid-flight and every row of it has dx == dy == 1, so it cannot
    # tell the two axes apart.  The FLIP rows are the ones that can: keep every
    # row where either velocity reversed, plus the row on each side of it.
    flip_ix = [i for i in range(len(rows)) if fl[i][0] or fl[i][1]]
    keep = sorted(set(sum([[i - 1, i, i + 1] for i in flip_ix], [])))
    return {'state': state, 'frames': nframes, 'bodies': len(rows),
            'head': rows[:16],
            'flip_rows': [rows[i] for i in keep if 0 <= i < len(rows)], 'x_range': [min(xs), max(xs)],
            'y_range': [min(ys), max(ys)],
            'x_at_flip': sorted(set(rows[i][2] for i in range(len(rows)) if fl[i][0])),
            'y_at_flip': sorted(set(rows[i][3] for i in range(len(rows)) if fl[i][1])),
            'dx_values': sorted(set(r[8] for r in rows)),
            'dy_values': sorted(set(r[9] for r in rows)),
            'body_frames': sorted(set(rows[i + 1][0] - rows[i][0]
                                      for i in range(len(rows) - 1))),
            'bodies_per_frame': round(len(rows) / nframes, 4)}


# ---------------------------------------------------------------- phase B
def phase_spawn():
    """the arm build/boss.pkl cannot take: $A839 is the presence flag AND the
       row, and boss.pkl holds 9.  Every target is seeded with a marker first."""
    h, m = new('bossspawn')
    targets = [SPRITE, BOSS_X, BOSS_Y, 0xA8FD, 0xA8FE, 0xA8C2, 0xA8C3]
    for a in targets:
        m[a] = 0x5A
    m[BOSS_Y] = 0                      # the gate: $A9F6 OR A / $A9F9 JP z
    st = {'f': None, 'a': None}
    h.memobj.watch(0x4000, 0x10000)

    def watch(p, f, h=h, st=st):
        if p == SPAWN and st['f'] is None:
            st['f'] = f
            st['a'] = h.sim.registers[A]
        return p == 0xA880 and st['f'] is not None      # the spawn's RET

    hit = frames(h, 400, watch)
    log = [(pc_, a, v) for (pc_, a, v) in h.memobj.log if a in targets]
    h.memobj.unwatch()
    return {'frame': st['f'], 'a_at_entry': st['a'], 'stopped_at_frame': hit,
            'writes': [['$%04X' % p, '$%04X' % a, v] for (p, a, v) in log],
            'after': {'$%04X' % a: m[a] for a in targets},
            'seed': 0x5A}


# ---------------------------------------------------------------- phase C
def phase_bounce():
    """$AA38 driven over EVERY position for both axes and six velocities.

       new = v + pos; if new < C or new >= B then v = -v and new = v + pos.
       Both comparisons are EIGHT BIT and the NEG is in place, so the velocity
       is state and its magnitude is whatever the tape left."""
    out = {}
    h, m = new('boss')
    for (name, lo, hi, dev, hlv) in (('x', 2, 27, DX, BOSS_X),
                                     ('y', 3, 20, DY, BOSS_Y)):
        for v in (1, 0xFF, 3, 0xFD, 2, 0xFE):
            rows = []
            for pos in range(256):
                m[dev] = v
                m[hlv] = pos
                r = h.sim.registers
                arm(h, BOUNCE)
                r[D], r[E] = dev >> 8, dev & 0xFF
                r[H], r[L] = hlv >> 8, hlv & 0xFF
                r[B], r[C] = hi, lo
                h.run_until(tuple(h.SENTINELS), limit=200, stride=1,
                            interrupts=False)
                rows.append([pos, m[hlv], m[dev]])
            kept = [r[0] for r in rows if r[2] == v]
            runs = []
            for k in kept:
                if runs and k == runs[-1][1] + 1:
                    runs[-1][1] = k
                else:
                    runs.append([k, k])
            out['%s_%02X' % (name, v)] = {
                'lo': lo, 'hi': hi, 'v': v,
                'kept_runs': runs, 'n_kept': len(kept), 'n_flipped': 256 - len(kept),
                'sample': [r for r in rows if r[0] in
                           (lo - 1, lo, lo + 1, hi - 2, hi - 1, hi, hi + 1)],
            }
    return out


# ---------------------------------------------------------------- phase D
def phase_poison():
    """THE NEGATIVE THAT NEEDS A CHAINED BUILD: nothing initialises the
       velocities.  81 sequential CALL $97F8 in one world with the milestone
       warp suppressed, POISONED velocities poked once at the start, and then
       the spawn -- and they are still $03/$FD, stepping three tiles a tick."""
    h, m = new('round1_48')
    sp0 = h.sim.registers[SP]
    m[0xFDDA] |= 0x80                  # suppress the milestone warp (F0's recipe)
    m[0xFDE4] |= 0x80
    m[DX], m[DY] = 0x03, 0xFD
    m[BOSS_XH] = 0x00
    m[0x8609] = 0
    rounds = []
    for k in range(81):
        sp = arm(h, ADVANCE, sp0)
        h.run_until(tuple(h.SENTINELS), limit=40 * 10 ** 6, stride=1,
                    interrupts=True)
        if h.regs[PC] not in h.SENTINELS:
            raise SystemExit('build %d: no sentinel' % k)
        rounds.append([m[0x8609], m[DX], m[DY]])
    after_build = [m[DX], m[DY], m[0x8609]]
    # ...and now the spawn, which also does not touch them
    m[BOSS_Y] = 0
    arm(h, SPAWN, sp0)
    h.sim.registers[A] = 4
    h.run_until(tuple(h.SENTINELS), limit=200000, stride=1, interrupts=False)
    after_spawn = [m[DX], m[DY]]
    # ...and three ticks of the body's bounces, with the machine's own bounce
    steps = []
    for _ in range(4):
        for (dev, hlv, lo, hi) in ((DX, BOSS_X, 2, 27), (DY, BOSS_Y, 3, 20)):
            arm(h, BOUNCE, sp0)
            r = h.sim.registers
            r[D], r[E] = dev >> 8, dev & 0xFF
            r[H], r[L] = hlv >> 8, hlv & 0xFF
            r[B], r[C] = hi, lo
            h.run_until(tuple(h.SENTINELS), limit=200, stride=1, interrupts=False)
        steps.append([m[BOSS_X], m[BOSS_Y], m[DX], m[DY]])
    return {'rounds_built': len(rounds), 'last_rounds': rounds[-3:],
            'after_build': after_build, 'after_spawn': after_spawn,
            'steps': steps, 'poison': [0x03, 0xFD]}


# ---------------------------------------------------------------- phase E
def phase_negatives():
    """the censuses, and the byte nobody writes."""
    h, m = new('boss')
    names = {0x32: 'LD (nn),A', 0x21: 'LD HL,nn', 0x11: 'LD DE,nn',
             0x22: 'LD (nn),HL', 0x2A: 'LD HL,(nn)', 0x3A: 'LD A,(nn)',
             0x01: 'LD BC,nn', 0xED: 'ED-prefixed'}
    out = {}
    for (label, addr) in (('$AA47', DX), ('$AA48', DY), ('$A8DC', BOSS_XH),
                          ('$A839', BOSS_Y), ('$A8DB', BOSS_X)):
        hits = h.find_bytes(bytes([addr & 0xFF, addr >> 8]), 0x4000, 0x10000)
        out[label] = [{'at': '$%04X' % (a - 1), 'opcode': m[a - 1],
                       'form': names.get(m[a - 1])} for a in hits]
    # $A8DC BUILT: it is the high byte of $A8DA LD BC,0, so a 1 there moves the
    # draw by +$100.  Nothing can measure a byte nobody writes except by poking.
    shifted = {}
    for v in (0, 1):
        g, mm = new('boss')
        mm[BOSS_XH] = v
        g.memobj.watch(0x4000, 0x5B00)
        arm(g, 0xA8C1)
        g.run_until(tuple(g.SENTINELS), limit=200000, stride=1, interrupts=False)
        w = [a for (_, a, _) in g.memobj.log]
        g.memobj.unwatch()
        shifted[v] = {'writes': len(w), 'first': '$%04X' % min(w),
                      'last': '$%04X' % max(w)}
    # $A824's body is DEAD on round 80
    g, mm = new('boss')
    hist = g.profile(400000)
    dead = {'$%04X' % a: hist.get(a, 0) for a in
            (0xA824, 0xA832, 0xA838, 0xA83F, 0xA844, 0xA847, 0xA9B1)}
    return {'refs': out, 'a8dc_built': shifted, 'a824_profile': dead}


# ---------------------------------------------------------------- phase F
def phase_inherit():
    """$AA06, $A82D, $A98F/$A990, $A8DB and $9F62 are NOT in the $9AC1 clear
       table, so they are INHERITED across the 80 -> 81 advance.  Seeded with
       markers, advanced once, and read back."""
    h, m = new('boss')
    marks = {DIVIDER: 0x5A, 0xA82D: 0x5B, 0xA98F: 0x5C, 0xA990: 0x5D,
             BOSS_X: 0x5E, 0x9F62: 0x5F, BOSS_Y: 0x60}
    for a, v in marks.items():
        m[a] = v
    before = {'$%04X' % a: v for a, v in marks.items()}
    sp = arm(h, ADVANCE)
    h.memobj.watch(0x4000, 0x10000)
    h.run_until(tuple(h.SENTINELS), limit=40 * 10 ** 6, stride=1, interrupts=True)
    wlog = [['$%04X' % p, '$%04X' % a, v] for (p, a, v) in h.memobj.log
            if a in marks]
    h.memobj.unwatch()
    return {'round_after': m[0x8609], 'before': before, 'writers': wlog,
            'after': {'$%04X' % a: m[a] for a in marks},
            'survived': ['$%04X' % a for a, v in marks.items() if m[a] == v]}


# ---------------------------------------------------------------- phase G
def phase_dy_default(nframes=150):
    """"dy defaults to -1" and "dy defaults to +1" are BEHAVIOURALLY IDENTICAL:
       the spawn puts Y at its LOW bound, so $FF bounces before the first store.
       Two 150-frame runs, compared row for row."""
    out = {}
    for v in (0x01, 0xFF):
        h, m = new('bossspawn')
        m[DY] = v
        rows = []

        def watch(p, f, m=m, rows=rows):
            if p == AFTER:
                rows.append([f, m[BOSS_X], m[BOSS_Y], m[DX], m[DY]])
            return False

        frames(h, nframes, watch)
        out['%02X' % v] = rows
    a, b = out['01'], out['FF']
    return {'rows_01': len(a), 'rows_FF': len(b),
            'identical': a == b, 'head_01': a[:6], 'head_FF': b[:6]}


# ---------------------------------------------------------------- phase H
def phase_gates():
    """the four gates as a TABLE.  Each row pokes the whole input and records
       what the tick did -- whether it spawned, whether the body ran, and what
       it left in the two self-modified counters.  A gate that is merely
       "usually taken" is indistinguishable from one that is always taken until
       the input that separates them is driven."""
    rows = []
    cases = [
        ('round 1',        0x01, 9, 0x10, 0x20, 0x05),
        ('round 79',       0x4F, 9, 0x10, 0x20, 0x05),
        ('round 80',       0x50, 9, 0x10, 0x20, 0x05),
        ('round 81',       0x51, 9, 0x10, 0x20, 0x05),
        ('no boss',        0x50, 0, 0x10, 0x20, 0x05),
        ('no boss, r81',   0x51, 0, 0x10, 0x20, 0x05),
        ('involution 0',   0x50, 9, 0x20, 0x20, 0x05),   # $AA00 == $8DBD -> latch
        ('divider 30',     0x50, 9, 0x10, 0x20, 0x1E),
        ('divider 31',     0x50, 9, 0x10, 0x20, 0x1F),   # -> wraps to 0, BODY
        ('divider 0',      0x50, 9, 0x10, 0x20, 0x00),
    ]
    for (name, rnd, boss, aa00, f, aa06) in cases:
        h, m = new('boss')
        m[0x8609] = rnd
        m[BOSS_Y] = boss
        m[INVOL] = aa00
        m[0x8DBD] = f
        m[DIVIDER] = aa06
        m[BOSS_X] = 20
        m[DX], m[DY] = 1, 1
        st = {'spawn': 0, 'body': 0}

        def watch(p, f_, st=st):
            if p == SPAWN:
                st['spawn'] += 1
            elif p == BODY:
                st['body'] += 1
            return False

        sp = arm(h, TICK)
        sim, regs, op, mem = h.sim, h.sim.registers, h.sim.opcodes, h.sim.memory
        n = 0
        sent = set(h.SENTINELS)
        while n < 300000:
            pcv = regs[PC]
            if pcv in sent:
                break
            watch(pcv, 0)
            op[mem[pcv]]()
            n += 1
        rows.append({'case': name, 'round': rnd, 'boss_in': boss,
                     'aa00_in': aa00, 'frame': f, 'aa06_in': aa06,
                     'spawned': st['spawn'], 'body': st['body'],
                     'aa00_out': m[INVOL], 'aa06_out': m[DIVIDER],
                     'x_out': m[BOSS_X], 'y_out': m[BOSS_Y]})
    return rows


# ---------------------------------------------------------------- phase I
def phase_spawn_sweep():
    """$A84D over indices the game never passes it, because the sixteen-bit
       truncation of `ADD A,A` x4 only shows above 15 and the CP 2 only shows
       at 1.  Gated at the method, as H12 gated its band wrap."""
    out = []
    for a in (1, 2, 3, 4, 10, 17, 21, 0):
        h, m = new('boss')
        m[BOSS_Y] = 0
        arm(h, SPAWN)
        h.sim.registers[A] = a
        h.run_until(tuple(h.SENTINELS), limit=200000, stride=1, interrupts=False)
        out.append({'a': a, 'a85c': m[SPRITE],
                    'ptr': m[0xA8FD] | (m[0xA8FE] << 8),
                    'spr': m[0xA8C2] | (m[0xA8C3] << 8),
                    'x': m[BOSS_X], 'y': m[BOSS_Y]})
    return out


def main():
    fx = {'track': phase_track('boss', 900),
          'track_240': phase_track('boss', 240),
          'spawn': phase_spawn(),
          'bounce': phase_bounce(),
          'poison': phase_poison(),
          'negatives': phase_negatives(),
          'inherit': phase_inherit(),
          'dy_default': phase_dy_default(),
          'gates': phase_gates(),
          'spawn_sweep': phase_spawn_sweep()}
    with open(FIXTURE, 'w') as f:
        json.dump(fx, f, indent=1)
    print('wrote', FIXTURE)
    t = fx['track']
    print('track 900f: %d bodies (%.4f/frame), X %s Y %s, flips at X %s Y %s, '
          'dx %s dy %s, frame gaps %s'
          % (t['bodies'], t['bodies_per_frame'], t['x_range'], t['y_range'],
             t['x_at_flip'], t['y_at_flip'], t['dx_values'], t['dy_values'],
             t['body_frames']))
    s = fx['spawn']
    print('spawn at frame %s with A=%s; writes %s' % (s['frame'], s['a_at_entry'],
                                                      s['writes']))
    for k in ('x_01', 'x_FF', 'y_01', 'y_FF', 'x_03', 'y_FD'):
        b = fx['bounce'][k]
        print('  bounce %-5s lo=%d hi=%d -> KEPT %s (%d of 256)'
              % (k, b['lo'], b['hi'], b['kept_runs'], b['n_kept']))
    p = fx['poison']
    print('poison: %d rounds built, ends %s; after build %s, after spawn %s, '
          'steps %s' % (p['rounds_built'], p['last_rounds'], p['after_build'],
                        p['after_spawn'], p['steps']))
    n = fx['negatives']
    for k, v in n['refs'].items():
        print('  %s refs: %s' % (k, [r['at'] + ' ' + str(r['form']) for r in v]))
    print('  $A8DC built:', n['a8dc_built'])
    print('  $A824 profile:', n['a824_profile'])
    i = fx['inherit']
    print('inherit: round -> $%02X, survived %s' % (i['round_after'], i['survived']))
    print('   and the ones that did NOT:', i['writers'])
    d = fx['dy_default']
    print('dy default: %d rows each, identical = %s' % (d['rows_01'], d['identical']))
    for r in fx['gates']:
        print('  gate %-14s spawn %d body %d  $AA00 %02X->%02X  $AA06 %02X->%02X  (X,Y)=(%d,%d)'
              % (r['case'], r['spawned'], r['body'], r['aa00_in'], r['aa00_out'],
                 r['aa06_in'], r['aa06_out'], r['x_out'], r['y_out']))
    for r in fx['spawn_sweep']:
        print('  spawn A=%-3d -> $A85C=%-3d ptr $%04X spr $%04X  (X,Y)=(%d,%d)'
              % (r['a'], r['a85c'], r['ptr'], r['spr'], r['x'], r['y']))


if __name__ == '__main__':
    main()
