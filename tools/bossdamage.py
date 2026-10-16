"""B8 -- THE DAMAGE MODEL: what can hurt what, and from where.

B5 transliterated the boss -> player arm and B6 the player -> boss arm.  NEITHER
HAD EVER BEEN SHOWN TO *REACH*: every measurement in both increments was an
isolated `h.call`, so "the rule is right" and "the rule never runs in play" were
the same green row.  This increment closes that, and the closing measurement is
the one thing a player would notice first.

*** A BOLT DOES REACH THE ACCEPT SET IN FAIR PLAY, WITH NO POKES AT ALL. ***
Keyboard only, on build/bosshit.pkl (round $50), pressing P1's OWN keys read
from the live table at $B5FD: bubbles get blown, popped, ($FFF9) becomes 3,
$93DC consumes it, $941B allocates, and ($9F62) comes down.  The headline is a
HISTOGRAM WITH ITS N, not a single run -- two independent measurement passes
each ran one key-script family and each declared the OPPOSITE cell "the case
fair play produces" (TRAPS #84).

AND THE THINGS THE SWEEP ALONE CANNOT SAY:
  * THE STRIDE STEPS OVER ACCEPTED COLUMNS.  $9D77 moves the bolt exactly one
    tile per test, so a static reading says it visits every column -- but THE
    BOSS MOVES TOO, so dx = boltTile - bossTile changes by 0, 1 OR 2 per test.
  * ONE BOLT CAN WALK ALL THREE ACCEPTED ROWS.  The bolt's Y is frozen at
    allocation ($941B writes ($FFF8) & $F8 once) and the boss CLIMBS underneath
    it, so a single flight can score at dy = -3, then -2, then -1.
  * THE DAMAGE PER ALIGNMENT IS NOT ONE.  $9F57 skips the physics on a damaging
    frame, so the bolt DWELLS: several decrements at the same cell.  A port that
    hard-codes "one hit, one HP" is wrong about the kill time, which is the only
    thing this behaviour is for.

Usage:  python tools/bossdamage.py      (capture -> build/bossdamage_fixture.json)
        python tools/bossdamage.py NAME [NAME...]    (one phase, no write)
"""
import sys, json, random
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A, B, C, D, E, H, L
import portconfig as pc

FIXTURE = 'build/bossdamage_fixture.json'
BRANCH_BYTE = 0x8DC4
ROUND = 0x8609
HP = 0x9F62
BOSS_X, BOSS_Y = 0xA8DB, 0xA839
SLOT0, SLOT1 = 0xFDEE, 0xFDF8
KEYTAB = 0xB5FD                  # P1's four (select, mask) pairs: O P Q SPACE
PAIR = 0xA98F                    # ...and $A990: two bytes that are two opcodes

HITTEST, ALLOC = 0x9F29, 0x941B
HPDEC, SLOTRUN = 0x9F53, 0x9E90
BLOW, MAILBOX = 0xBDC1, 0xB745
KILLJP, KILLTAIL = 0xAA35, 0x927D
ISR = 0x8D72


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


def set_iy(h, v):
    r = h.sim.registers
    r[10], r[11] = v >> 8, v & 0xFF


def get_iy(h):
    r = h.sim.registers
    return (r[10] << 8) | r[11]


def tile(v):
    return (v >> 3) & 0x1F


def decide(h, m, tx, ty):
    """One $9F29 decision, with the HP byte seeded to a value the decrement
       changes VISIBLY and checked on the REJECTS too (TRAPS #44)."""
    m[HP] = 0x2A
    m[SLOT0 + 5] = (tx * 8) & 0xFF
    m[SLOT0 + 6] = (ty * 8) & 0xFF
    m[SLOT0 + 7] = 0x80
    set_iy(h, SLOT0)
    arm(h, HITTEST)
    h.run_until((0x9F51, 0x9ED0) + tuple(h.SENTINELS),
                limit=200000, stride=1, interrupts=False)
    hit = h.regs[PC] == 0x9F51
    if not hit and m[HP] != 0x2A:
        raise SystemExit('HP moved on a reject at %d,%d' % (tx, ty))
    return hit


# ------------------------------------------------------------------ phase A
def phase_accept_map():
    """THE WHOLE PLAYFIELD, not eleven squares.  B6 swept 11x11 around the boss
       and found six cells; that sweep cannot say what the other 647 tiles do,
       and "accepted" and "never reached" are the same row in any sweep that
       never visits the rejects.  768 cells at THREE boss positions."""
    out = {}
    for (bx, by) in ((20, 9), (2, 3), (26, 19)):
        h, m = new('boss')
        m[BOSS_X], m[BOSS_Y] = bx, by
        acc, offs = [], []
        for ty in range(24):
            for tx in range(32):
                hit = decide(h, m, tx, ty)
                acc.append('1' if hit else '0')
                if hit:
                    offs.append([tx - bx, ty - by])
        out['%d_%d' % (bx, by)] = {
            'bx': bx, 'by': by, 'map': ''.join(acc),
            'accepted': acc.count('1'), 'rejected': acc.count('0'),
            'offsets': sorted(offs)}
    return out


# ------------------------------------------------------------------ phase B
def phase_overlap():
    """THE DERIVED TABLE THAT MAKES A LATER "FIX" FAIL A NAMED ROW.  The bolt is
       drawn 16x16 at tiles [tx, tx+1] and the boss 32x32 at [bx, bx+3].  Cross
       "the sprites visibly overlap" with "$9F29 accepts" -- measured, not
       assumed -- and the two sets barely meet."""
    h, m = new('boss')
    bx, by = 20, 9
    m[BOSS_X], m[BOSS_Y] = bx, by
    rows = []
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            tx, ty = bx + dx, by + dy
            if not (0 <= tx < 32 and 0 <= ty < 24):
                continue
            acc = decide(h, m, tx, ty)
            over = (tx <= bx + 3 and tx + 1 >= bx and
                    ty <= by + 3 and ty + 1 >= by)
            rows.append([dx, dy, 1 if over else 0, 1 if acc else 0])
    return {'rows': rows,
            'overlap': sum(r[2] for r in rows),
            'accept': sum(r[3] for r in rows),
            'both': sum(1 for r in rows if r[2] and r[3]),
            'both_cells': [[r[0], r[1]] for r in rows if r[2] and r[3]],
            'accept_no_overlap': [[r[0], r[1]] for r in rows
                                  if r[3] and not r[2]]}


# ------------------------------------------------------------------ phase C
def keys(m):
    """P1's four keys, read LIVE -- the table is RAM, not tape, and the player
       may have redefined it.  $B5FD holds (half-row SELECT, BIT MASK) pairs and
       the game tests `IN A,(sel) / AND mask / JR z`, so the mask has the key's
       bit SET.  THE HARNESS WANTS THE OPPOSITE: Ports.press stores the value the
       port RETURNS, where a pressed key is a ZERO.  Handing it the table value
       verbatim presses the SEVEN OTHER KEYS of that half-row -- and on $7F that
       includes the PAUSE key, so the machine sits in $8FFB's
       `IN A,($FE) / RRA / JR c` loop with interrupts off and every subsequent
       measurement reads "nothing happened".  That cost an entire empty phase."""
    return [(m[KEYTAB + 2 * i], 0xFF ^ m[KEYTAB + 2 * i + 1]) for i in range(4)]


def fair_run(seed, frames=600, state='bosshit'):
    """Free-running, ISR live, NO POKES.  The only input is h.ports.press of
       P1's own keys.  Everything else is the machine."""
    h, m = new(state)
    if m[ROUND] != 0x50:
        raise SystemExit('%s is round $%02X, not the boss' % (state, m[ROUND]))
    kt = keys(m)
    rnd = random.Random(seed)
    targets = (ISR, BLOW, MAILBOX, ALLOC, SLOTRUN, HITTEST, HPDEC,
               KILLJP, KILLTAIL)
    log = {'hits': [], 'tests': [], 'allocs': [], 'emits': [],
           'kills': [], 'hp0': m[HP]}
    counts = dict.fromkeys(('blow', 'emit', 'alloc', 'slot', 'test',
                            'dec', 'kill'), 0)
    frame = 0
    last_seg = -1
    while frame < frames:
        if frame != last_seg and frame % 8 == 0:
            last_seg = frame
            h.ports.release_all()
            for i in range(4):
                if rnd.random() < 0.5:
                    h.ports.press(*kt[i])
        reason, _ = h.run_until(targets, limit=400000, stride=1)
        if reason != 'target':
            break
        p = h.regs[PC]
        if p == ISR:
            frame += 1
        elif p == BLOW:
            counts['blow'] += 1
        elif p == MAILBOX:
            counts['emit'] += 1
            log['emits'].append([frame, m[0xB742], m[0xFFF9]])
        elif p == ALLOC:
            counts['alloc'] += 1
            log['allocs'].append([frame, m[SLOT0 + 7], m[SLOT1 + 7],
                                  m[0xFFF7], m[0xFFF8]])
        elif p == SLOTRUN:
            counts['slot'] += 1
        elif p == HITTEST:
            counts['test'] += 1
            iy = get_iy(h)
            log['tests'].append([frame, tile(m[iy + 5]) - m[BOSS_X],
                                 tile(m[iy + 6]) - m[BOSS_Y],
                                 tile(m[iy + 5]), tile(m[iy + 6])])
        elif p == HPDEC:
            counts['dec'] += 1
            iy = get_iy(h)
            log['hits'].append([frame, tile(m[iy + 5]) - m[BOSS_X],
                                tile(m[iy + 6]) - m[BOSS_Y], m[HP]])
        else:
            counts['kill'] += 1
            log['kills'].append([frame, p])
        h.step(1)
    log['hp1'] = m[HP]
    log['counts'] = counts
    log['frames'] = frame
    return log


def phase_fairplay():
    """*** THE ANSWER TO THE ONE QUESTION B5 AND B6 COULD NOT ANSWER. ***
       No pokes.  Four independent key scripts, each named by its seed, each
       600 frames, and the result reported as a HISTOGRAM WITH ITS N -- because
       a single script is a sample of one script, not a property of the game
       (TRAPS #84)."""
    runs, hist = [], {}
    keep = None
    for seed in (0, 3, 5, 7, 9, 10, 11, 12):
        r = fair_run(seed)
        if seed == 0:
            keep = r
        runs.append({'seed': seed, 'frames': r['frames'],
                     'counts': r['counts'],
                     'hp_before': r['hp0'], 'hp_after': r['hp1'],
                     'hits': r['hits'], 'kills': r['kills'],
                     'emit_classes': sorted(set(e[1] for e in r['emits'])),
                     'alloc_drops': sum(1 for a in r['allocs']
                                        if (a[1] & 0x80) and (a[2] & 0x80)),
                     'mailbox_blocks': sum(1 for e in r['emits']
                                           if e[2] != 0)})
        for hc in r['hits']:
            k = '%d,%d' % (hc[1], hc[2])
            hist[k] = hist.get(k, 0) + 1
    fr = [t[0] for t in keep['tests']]
    gaps = {}
    for i in range(1, len(fr)):
        g = str(fr[i] - fr[i - 1])
        gaps[g] = gaps.get(g, 0) + 1
    dwell, run_len, prev = {}, 0, None
    for r in runs:
        for hc in r['hits']:
            k = (r['seed'], hc[1], hc[2])
            if k == prev:
                run_len += 1
            else:
                if prev is not None:
                    dwell[str(run_len)] = dwell.get(str(run_len), 0) + 1
                run_len, prev = 1, k
    if prev is not None:
        dwell[str(run_len)] = dwell.get(str(run_len), 0) + 1
    return {'runs': runs,
            'n_bolts': sum(r['counts']['alloc'] for r in runs),
            'n_tests': sum(r['counts']['test'] for r in runs),
            'n_decrements': sum(r['counts']['dec'] for r in runs),
            'n_scripts': len(runs),
            'cell_histogram': hist,
            'cells_seen': sorted(hist),
            'test_frame_gaps': gaps,
            'dwell_histogram': dwell,
            'seed0_test_count': len(keep['tests'])}


# ------------------------------------------------------------------ phase D
def phase_stride():
    """DOES THE STRIDE STEP OVER AN ACCEPTED COLUMN?  $9D77 adds exactly one
       tile per test, so a static reading says no.  IT IS WRONG, because the
       BOSS MOVES: track dx over one whole flight and watch it skip.
       Armed at the POP INTERFACE -- ($FFF9)/($FFF7)/($FFF8) -- so $93DC and
       $941B do the allocation.  That is not an isolated $9F29 call."""
    out = {}
    for (name, poptile, facing) in (('left_flight', (1, 2), 0),
                                    ('right_flight', (28, 2), 1)):
        h, m = new('bosshit')
        m[0xFD87] = (m[0xFD87] & 0xFE) | facing
        m[0xFFF7], m[0xFFF8] = poptile[0] * 8, poptile[1] * 8
        m[0xFFF9], m[0xFFFA] = 3, 1
        hp0 = m[HP]
        seq, frame = [], 0
        while frame < 200:
            reason, _ = h.run_until((ISR, HITTEST), limit=400000, stride=1)
            if reason != 'target':
                break
            if h.regs[PC] == ISR:
                frame += 1
            else:
                iy = get_iy(h)
                seq.append([frame, tile(m[iy + 5]) - m[BOSS_X],
                            tile(m[iy + 5]), m[BOSS_X]])
            h.step(1)
        dxs = [s[1] for s in seq]
        jumps = {}
        for i in range(1, len(dxs)):
            j = str(dxs[i] - dxs[i - 1])
            jumps[j] = jumps.get(j, 0) + 1
        skipped = sorted(set(
            v for i in range(1, len(dxs)) for v in (0, -3)
            if min(dxs[i - 1], dxs[i]) < v < max(dxs[i - 1], dxs[i])))
        out[name] = {'tests': len(seq), 'dx': dxs,
                     'columns': sorted(set(s[2] for s in seq)),
                     'dx_jumps': jumps, 'accepted_columns_skipped': skipped,
                     'hp_before': hp0, 'hp_after': m[HP]}
    return out


# ------------------------------------------------------------------ phase E
def phase_offround():
    """THE NEGATIVE, AND THE EMPTY ROW IT REPLACES.  A PASSIVE control round
       proves nothing: on r50_48 the scripted player never even blows, so
       "0 allocations, 0 hit tests, HP unchanged" is the absence of a bubble,
       not the presence of $9EA1's gate.  INJECT the same class-3 request on
       every round and compare (TRAPS #50).

       AND THERE ARE TWO GATES, NOT ONE.  $9E71 `CP $50` in the TICK decides
       whether the bolt slots run at all, and $9E9E `CP $50` inside the SLOT
       decides whether a running bolt goes to the boss hit test or to the enemy
       scan.  r20_48 and r50_48 separate neither, because their ($7E0E) is not
       LIGHTNING so $9E71's other arm drops them anyway -- the row that
       separates the two is `ellight`, an off-boss round whose element IS 3."""
    out = {}
    for state in ('bosshit', 'r20_48', 'r50_48', 'ellight'):
        h, m = new(state)
        rnd = m[ROUND]
        m[0xFFF7], m[0xFFF8] = 12 * 8, 8 * 8
        m[0xFFF9], m[0xFFFA] = 3, 1
        hp0 = m[HP]
        n = dict.fromkeys(('alloc', 'slot', 'test', 'dec'), 0)
        frame = 0
        while frame < 120:
            reason, _ = h.run_until((ISR, ALLOC, SLOTRUN, HITTEST, HPDEC),
                                    limit=400000, stride=1)
            if reason != 'target':
                break
            p = h.regs[PC]
            if p == ISR:
                frame += 1
            elif p == ALLOC:
                n['alloc'] += 1
            elif p == SLOTRUN:
                n['slot'] += 1
            elif p == HITTEST:
                n['test'] += 1
            else:
                n['dec'] += 1
            h.step(1)
        out[state] = {'round': rnd, 'element': m[0x7E0E], 'counts': n,
                      'hp_before': hp0, 'hp_after': m[HP], 'frames': frame}
    h, m = new('r50_48')
    kt = keys(m)
    rnd = random.Random(0)
    blows, frame = 0, 0
    while frame < 300:
        if frame % 12 == 0:
            h.ports.release_all()
            for i in range(4):
                if rnd.random() < 0.45:
                    h.ports.press(*kt[i])
        reason, _ = h.run_until((ISR, BLOW), limit=400000, stride=1)
        if reason != 'target':
            break
        if h.regs[PC] == ISR:
            frame += 1
        else:
            blows += 1
        h.step(1)
    out['passive_r50_is_an_empty_row'] = {'frames': frame, 'blows': blows,
                                          'element': m[0x7E0E],
                                          'round': m[ROUND]}
    return out


# ------------------------------------------------------------------ phase F
def phase_decay():
    """$A98F/$A990.  B5 measured 55 and 201 decrements and called the COUNTS the
       invariant.  THE COUNTS ARE A TAUTOLOGY: $AAA1 decrements to zero and
       $AA9C's zero guard stops, so "55" is "$A98F started at $37" restated and
       is the same on every round.  THE FRAMES are the only rate-carrying
       observation, and they VARY."""
    out = {}
    for state in ('play1p48', 'r20_48', 'r50_48'):
        h, m = new(state)
        start = [m[PAIR], m[PAIR + 1]]
        zero = [None, None]
        counts = [0, 0]
        prev = list(start)
        for f in range(700):
            h.run_frames(1)
            for i in (0, 1):
                if m[PAIR + i] != prev[i]:
                    counts[i] += 1
                    prev[i] = m[PAIR + i]
                if m[PAIR + i] == 0 and zero[i] is None:
                    zero[i] = f
            if zero[0] is not None and zero[1] is not None:
                break
        out[state] = {'round': m[ROUND], 'start': start,
                      'zero_frame': zero, 'decrements': counts}
    return out


PHASES = [('accept_map', phase_accept_map), ('overlap', phase_overlap),
          ('fairplay', phase_fairplay), ('stride', phase_stride),
          ('offround', phase_offround), ('decay', phase_decay)]

if __name__ == '__main__':
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    only = [a for a in sys.argv[1:] if not a.startswith('-')]
    fx = {}
    for name, fn in PHASES:
        if only and name not in only:
            continue
        print('--', name, flush=True)
        fx[name] = fn()
        print(json.dumps(fx[name])[:1200], flush=True)
    if not only:
        json.dump(fx, open(FIXTURE, 'w'), indent=1, sort_keys=True)
        print('\nwrote', FIXTURE)
