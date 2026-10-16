"""M7.89 (measurement) -- THE LEVEL-CLEAR DECISION'S T ($8E3A, its children $8F94 / $90A9 / $90C1), RUN BY RUN, UNCONTENDED.

passcost (M7.86): $8E3A is 4.8% of the main loop's T, 49..1,718 T without blocks (median 366, 18 paths),
and 2 runs are frame-long BLOCKS (up to 1,754,419 T).  This oracle records every run of $8E3A from its
one caller ($8D5E CALL $8E3A; $8D61 tests its Z flag) on an UNCONTENDED machine, so a run's T is the sum
of its instructions' own T, and brackets every nested CALL apart by entry PC + return SP (cost931a's way):

  $8E3A    LD A,n -- $8E3B, its own OPERAND, is the clear-pending LATCH (read as state, TRAPS #278) --
           non-zero: JP $8F29, the countdown (($8DBE) = 1 and ($8DBD) >= $77 -> Z, the advance).
           Else ($FED1) non-zero: JP $8F36, the treasure drain ((($8DBE) - ($8F3A)) = 8, the band,
           and the $8F94 live-item count, called once or twice; empty -> $8F4C the award and $8F78
           "PERFECT !" x256 -- a BLOCK).  Else ($8609) = $50, the boss round: ($9F62) - 1 signed
           positive -> $8ECC OR $2A / RET (NZ); else $8E55, the boss death -- a BLOCK ($9573 x3).
           Else the tally $8EAA: bit 7 of +7 over ($AA57) - 2 slots from $FD9B (DJNZ: 0 is 256) into
           ($FECA); none -> $8ECF the one-shot clear (the latch, twelve bubble slots, ($FECC) to $A84D
           when non-zero) and on into $8F29; one -> CALL $90A9 (the anger pass) and OR $2A; more -> RET nz
  $8F94    the live-item count: 31 entries from $9605, step 2 -- 1,517 - k T, k the non-zero entries
  $90A9    the anger pass: LD A,n -- $90AA, its own OPERAND, the latch (state) -- RET nz; else the latch,
           ($FEC4), CALL $90C1, the gates
  $90C1    the temper walk over ($AA57) - 2 slots (DJNZ: 0 is 256)
  $A84D    the GIANT-ITEM SPAWN the clear hands ($FECC) to ($8F26 CALL $A84D, A = ($FECC): the shared boss /
           giant spawn) -- bracketed apart, its T reported, NOT modelled (M7.93: was labelled 'the HUD repaint')

A run longer than a frame (BLOCK = 69,888 T) is a BLOCK: labelled ('block': 'boss' / 'perfect'), its T
and own kept, its children as [entry, calls, T total, T min, T max], its seed/post not, and it is NOT checked against the model nor counted in 'contended'
(game.js times the boss death's waits by busyWait; the perfect draw is its own declared departure).

Every interrupt accepted inside a run is BRACKETED OUT (acceptance to the return to the interrupted PC
at the interrupted SP); such a run keeps its T and path, its seed/post are not kept ('irq').  A HALT
inside a run is an error (asserted: none).  Row fields as cost8fa5's ('sig': each conditional pc with
its taken / fell counts, 'kids' nested [entry, T, own, sig, kids]).

THE MODEL (Zilog T, asserted against EVERY non-block run, natural and forced -- 'model'): M8E3A from
the path's counts, $8F94 = CNT_BASE - k, $90A9 latched / unlatched, $90C1 = WALK_HEAD + WALK n.

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table.  FORCED CALLS (declared, CALLS below) for the branches no natural run takes:
$8E3A called once from a saved state with pokes, interrupts off at entry, returning to $8D61.
'contended': {state: [[runs, T] contention off, [runs, T] on]}, irq runs and blocks out.
'window' (M7.93): round1_48's first WINDOW frames, contention off and on -- [runs, total T, {sig: n}] -- the
frames BB_PASS_T was CALIBRATED on (the timing census, build/timing_fixture.json 'seq': 48 frames); the share
the main loop's flat rest gives up is this window's (TRAPS #286: the share AS CALIBRATED).  Blocks and irq out.
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/cost8e3a.py [--jobs N]          (-> build/cost8e3a_fixture.json, N <= 6)
        python tools/cost8e3a.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections, time
from multiprocessing import Pool
sys.path.insert(0, 'tools')
import aa60cost as A
import ab38cost as B
import cost8fa5 as G

FIXTURE = 'build/cost8e3a_fixture.json'
FRAMES = G.FRAMES
WINDOW = G.WINDOW   # M7.93: the timing census's 48 frames
KEEP = 2
BLOCK = 69888
ENTRY, CALLER, BACK = 0x8E3A, 0x8D5E, 0x8D61
COUNT, ANGER, WALK, PAINT = 0x8F94, 0x90A9, 0x90C1, 0xA84D
# the operands read as STATE: $8E3A LD A,n ($8E3B), $90A9 LD A,n ($90AA), $8F39 SUB n ($8F3A)
STATE_OPS = {0x8E3A: (0x8E3B,), 0x90A9: (0x90AA,), 0x8F39: (0x8F3A,)}

# ---------------------------------------------------------------- the model (Zilog T)
W = dict(
    # $8E3A LD A,n 7 / OR A 4 / JP nz 10
    PRE=21,
    # $8F29 LD A,(nn) 13 / DEC A 4
    CD=17,
    # $8F2D RET nz taken 11
    CD_NZ=11,
    # $8F2D RET nz 5 / LD A,(nn) 13 / CP n 7
    CD_HI=25,
    # $8F33 RET c taken 11 (below $77)
    CD_LOW=11,
    # $8F33 RET c 5 / XOR A 4 / RET 10 -- Z, the advance
    CD_ADV=19,
    # $8E40 LD A,(nn) 13 / OR A 4 / JP nz 10
    UNL=27,
    # $8E47 LD A,(nn) 13 / CP n 7
    RND=20,
    # $8E4C JR nz taken 12 (not the boss round) | 7
    RND_T=12, RND_F=7,
    # $8E4E LD A,(nn) 13 / DEC A 4 / JP p 10 ; alive -> $8ECC OR n 7 / RET 10
    BOSS=27, BOSS_LIVE=17,
    # $8EAA LD A,(nn) 13 / SUB n 7 / LD B,A 4 / LD HL,nn 10 / LD DE,nn 10 / LD C,D 4
    TALLY=48,
    # $8EB7 LD A,(HL) 7 / RLCA 4 / AND n 7 / ADD A,C 4 / LD C,A 4 / ADD HL,DE 11 / DJNZ 13 -- the last 8
    SLOT=50, SLOT_END=-5,
    # $8EC0 LD A,C 4 / LD (nn),A 13 / OR A 4
    TALLY_TAIL=21,
    # $8EC5 JR z taken 12 (none) | 7 ; $8EC7 DEC A 4 / RET nz taken 11 (more than one)
    NONE=12, SOME=7, MANY=15,
    # $8EC7 DEC A 4 / RET nz 5 / CALL $90A9 17 / $8ECC OR n 7 / RET 10 (exactly one)
    ONE=43,
    # $8ECF LD A,n 7 / LD (nn),A 13 x2 / LD A,n 7 / LD (nn),A 13 x2 / (LD A,(nn) 13 / OR n 7 / LD (nn),A 13)
    # x2 / LD HL,(nn) 16 / LD (nn),HL 16 / DI 4 / XOR A 4 / LD L,A 4 / LD H,A 4 / LD (nn),HL 16 /
    # INC A 4 / LD (nn),A 13 / LD IX,nn 14 x2 / LD DE,nn 10 / LD B,n 7 / LD C,n 7
    CLEAR=265,
    # $8F0F LD (IX+d),D 19 / LD (IX+d),C 19 / ADD IX,DE 15 / DJNZ 13 x12, the last DJNZ 8
    BUBBLES=787,
    # $8F19 EI 4 / LD A,(nn) 13 / OR A 4
    CLEAR_TAIL=21,
    # $8F1E JR z taken 12 (($FECC) zero) ; 7 / LD C,A 4 / XOR A 4 / LD (nn),A 13 / LD A,C 4 / CALL 17
    HUD_NO=12, HUD=49,
    # $8F36 LD A,(nn) 13 / SUB n 7 / CP n 7
    TR=27,
    # $8F3D JR z taken 12 (the band) ; 7 / CALL $8F94 17 / INC C 4 / DEC C 4
    TR_BAND=12, TR_ASK=32,
    # $8F44 RET nz taken 11 (items left, not the band) | 5
    TR_LEFT=11, TR_EMPTY=5,
    # $8F45 CALL $8F94 17 / INC C 4 / DEC C 4
    TR_ASK2=25,
    # $8F4A JR nz taken 12 / $8F92 XOR A 4 / RET 10 (items left in the band: Z, cleared)
    TR_ADV=26,
)
CNT = dict(
    # $8F94 LD HL,nn 10 / LD B,n 7 / LD C,n 7 ; per entry LD A,(HL) 7 / AND A 4 / JR z taken 12 (zero) or
    # 7 / INC C 4 (live: one T less) / INC HL 6 x2 / DJNZ 13 -- 31 entries, the last DJNZ 8 ; RET 10
    #   = 24 + 31 x 48 - 5 + 10 - k
    BASE=1517,
)
ANG = dict(
    # $90A9 LD A,n 7 / OR A 4 / RET nz taken 11
    LATCHED=22,
    # 7 / 4 / RET nz 5 / INC A 4 / LD (nn),A 13 / XOR A 4 / LD (nn),A 13 / CALL $90C1 17 / LD A,n 7 /
    # LD (nn),A 13 x2 / RET 10
    FIRST=110,
)
WK = dict(
    # $90C1 LD HL,nn 10 / LD A,(nn) 13 / SUB n 7 / LD B,A 4 / LD DE,nn 10 / LD C,n 7 ; RET 10, the last
    # DJNZ 8 (-5)  = 51 + 10 - 5
    HEAD=56,
    # $90CF SET 2,(HL) 15 / DEC HL 6 x2 / LD A,(HL) 7 / AND C 4 / LD (HL),A 7 / ADD HL,DE 11 / DJNZ 13
    SLOT=69,
)


def _c(d, q):
    return d.get(q, (0, 0))


def _tk(d, q):
    """the one execution of conditional q: 't' / 'f' (asserted single)"""
    c = _c(d, q)
    assert c[0] + c[1] == 1, '%04x ran %s' % (q, c)
    return 't' if c[0] else 'f'


def M8E3A(d):
    """$8E3A's own T from its path's counts {pc: (taken, fell)}; None for a block's path"""
    t = W['PRE']
    cd = False
    if _tk(d, 0x8E3D) == 't':
        cd = True
    else:
        t += W['UNL']
        if _tk(d, 0x8E44) == 't':
            t += W['TR']
            if _tk(d, 0x8F3D) == 't':
                t += W['TR_BAND']
            else:
                t += W['TR_ASK']
                if _tk(d, 0x8F44) == 't':
                    return t + W['TR_LEFT']
                t += W['TR_EMPTY']
            t += W['TR_ASK2']
            if _tk(d, 0x8F4A) == 't':
                return t + W['TR_ADV']
            return None                       # $8F4C: the award and the perfect draw -- a block
        t += W['RND']
        if _tk(d, 0x8E4C) == 'f':
            t += W['RND_F'] + W['BOSS']
            if _tk(d, 0x8E52) == 't':
                return t + W['BOSS_LIVE']
            return None                       # $8E55: the boss death -- a block
        t += W['RND_T'] + W['TALLY']
        c = _c(d, 0x8EBE)
        t += W['SLOT'] * (c[0] + c[1]) + W['SLOT_END'] + W['TALLY_TAIL']
        if _tk(d, 0x8EC5) == 'f':
            t += W['SOME']
            if _tk(d, 0x8EC8) == 't':
                return t + W['MANY']
            return t + W['ONE']
        t += W['NONE'] + W['CLEAR'] + W['BUBBLES'] + W['CLEAR_TAIL']
        t += W['HUD_NO'] if _tk(d, 0x8F1E) == 't' else W['HUD']
        cd = True
    assert cd
    t += W['CD']
    if _tk(d, 0x8F2D) == 't':
        return t + W['CD_NZ']
    t += W['CD_HI']
    if _tk(d, 0x8F33) == 't':
        return t + W['CD_LOW']
    return t + W['CD_ADV']


def MCHILD(node):
    """a modelled child's own T from its path; None for a child not modelled ($A84D)"""
    e, T_, own, sg, kids = node
    d = {}
    for part in sg.split():
        q, tf = part.split(':t')
        nt, nf = tf.split('f')
        d[int(q, 16)] = (int(nt), int(nf))
    if e == '%04X' % COUNT:
        c = _c(d, 0x8F9D)
        assert c[0] + c[1] == 31
        return CNT['BASE'] - c[1]             # fell through = a live entry
    if e == '%04X' % ANGER:
        return ANG['LATCHED'] if _tk(d, 0x90AC) == 't' else ANG['FIRST']
    if e == '%04X' % WALK:
        c = _c(d, 0x90D7)
        return WK['HEAD'] + WK['SLOT'] * (c[0] + c[1])
    return None


def check(x):
    """the model against one run (not a block): (ok, unmodelled child T)"""
    m = M8E3A(x['cnt'])
    ok = m == x['own']
    other = 0
    stack = list(x['kids'])
    while stack:
        n = stack.pop()
        p = MCHILD(n)
        if p is None:
            other += n[1]                     # its whole T, its own children in it
            continue
        ok = ok and p == n[2]
        stack.extend(n[4])
    return ok, other


def block_kind(x):
    c = x['cnt']
    if _c(c, 0x8E52)[1]:
        return 'boss'
    if _c(c, 0x8F4A)[1]:
        return 'perfect'
    return '?'


# ---------------------------------------------------------------- forced calls (declared)
def _quiet(n):
    """($AA57) = n + 2 slots walked, every +7 bit 7 clear; not the treasure room, not the boss round,
    latch clear"""
    k = 256 if n == 0 else n
    return [(0x8E3B, 0), (0xFED1, 0), (0x8609, 0x00), (0xAA57, (n + 2) & 0xFF)] + \
           [((0xFD9B + 10 * i) & 0xFFFF, 0) for i in range(k)]


def _live(i):
    return [((0xFD9B + 10 * i) & 0xFFFF, 0x80)]


def _items(k):
    """the $9605 table with k live entries (1..k)"""
    return [(0x9605 + 2 * i, 1 if i < k else 0) for i in range(31)]


def _treasure(band, k):
    """the treasure room: ($8DBE) - ($8F3A) = 8 when band, else 0"""
    return [(0x8E3B, 0), (0xFED1, 1), (0x8F3A, 5), (0x8DBE, 13 if band else 5)] + _items(k)


CALLS = [
    # the latch set: the countdown's three ends
    ('latch_nz', 'round1_48', [(0x8E3B, 1), (0x8DBE, 0), (0x8DBD, 0x80)]),
    ('latch_low', 'round1_48', [(0x8E3B, 1), (0x8DBE, 1), (0x8DBD, 0x76)]),
    ('latch_adv', 'round1_48', [(0x8E3B, 1), (0x8DBE, 1), (0x8DBD, 0x77)]),
    # the tally: many / one (latched, unlatched with 1 and 30 slots walked) / none (with and without
    # the HUD repaint) ; ($AA57) = 2: the DJNZ walks 256 slots
    ('many', 'round1_48', _quiet(5) + _live(0) + _live(3)),
    ('one_latched', 'round1_48', _quiet(5) + _live(2) + [(0x90AA, 1)]),
    ('one_first', 'round1_48', _quiet(1) + _live(0) + [(0x90AA, 0)]),
    ('one_first30', 'round1_48', _quiet(30) + _live(29) + [(0x90AA, 0)]),
    ('none', 'round1_48', _quiet(5) + [(0xFECC, 0)]),
    ('none_hud', 'round1_48', _quiet(5) + [(0xFECC, 1)]),
    ('tally256', 'round1_48', _quiet(0)),
    # the boss round, alive
    ('boss_live', 'round1_48', [(0x8E3B, 0), (0xFED1, 0), (0x8609, 0x50), (0x9F62, 0x2A)]),
    # the treasure drain's non-block ends: items left outside the band (twice: the power-up entry 0
    # live and not counted) / items left inside it (an empty table reaches the award -- a block, below)
    ('tr_left', 'round1_48', _treasure(False, 3)),
    ('tr_band_left', 'round1_48', _treasure(True, 31)),
    ('tr_left_power', 'round1_48', _treasure(False, 1) + [(0x9603, 1)]),
    # the two blocks, forced once each (labelled, not modelled)
    ('tr_perfect', 'round1_48', _treasure(False, 0)),
    ('boss_dead', 'round1_48', [(0x8E3B, 0), (0xFED1, 0), (0x8609, 0x50), (0x9F62, 0)]),
]
CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, tag = job
    if tag:
        c = CALLS_BY[tag]
        runs = [G.call_run(c[1], c[2], ENTRY, BACK, STATE_OPS, limit=20000000)]
    else:
        runs = G.run(name, ENTRY, BACK, STATE_OPS)
    out = []
    for x in runs:
        rw = G.row_base(tag or name, x)
        if x['T'] >= BLOCK:
            for k in ('seed', 'post', 'rom', 'blind'):
                rw.pop(k, None)
            rw['block'] = block_kind(x)
            agg = {}
            for k in x['kids']:
                a = agg.setdefault(k[0], [k[0], 0, 0, k[1], k[1]])
                a[1] += 1; a[2] += k[1]; a[3] = min(a[3], k[1]); a[4] = max(a[4], k[1])
            rw['kids'] = sorted(agg.values())          # [entry, calls, T total, T min, T max]
            out.append((None, 0, rw))
            continue
        ok, other = check(x)
        out.append((ok, other, rw))
    return out


def contended_one(st):
    return G.contended_pair(st, ENTRY, BACK, STATE_OPS, keep=lambda x: x['T'] < BLOCK)


def window_one(c):
    """M7.93: round1_48's first WINDOW frames, contention off / on: [runs, total T, {sig: n}], the runs an
    interrupt landed in and the blocks left out"""
    rs = [x for x in G.run('round1_48', ENTRY, BACK, STATE_OPS, WINDOW, c) if not x['irq'] and x['T'] < BLOCK]
    return [len(rs), sum(x['T'] for x in rs), dict(collections.Counter(x['sig'] for x in rs))]


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, A.STATES)
        wres = pool.map(window_one, (False, True))
    contended = {s: cres[i] for i, s in enumerate(A.STATES)}
    rows, per = [], collections.Counter()
    n_runs = n_irq = n_checked = 0
    ts, owns, sigs, blocks, bad, others = [], collections.Counter(), set(), [], [], []
    sigs_forced = set()
    kidT = collections.defaultdict(collections.Counter)
    for (s, tag), rs in zip(work, res):
        for ok, other, x in rs:
            if 'block' in x:
                blocks.append({'state': x['state'], 'T': x['T'], 'own': x['own'], 'irq': x['irq'],
                               'block': x['block'], 'kids': x['kids'], 'forced': bool(tag)})
                if not tag:
                    n_runs += 1; n_irq += 1 if x['irq'] else 0
                continue
            n_checked += 1
            if not ok:
                bad.append([x['state'], x['T'], x['own'], x['sig']])
            if other:
                others.append([x['state'], other, [k[0] for k in x['kids']]])
            if tag:
                sigs_forced.add(x['sig']); rows.append(x)
                continue
            n_runs += 1; n_irq += 1 if x['irq'] else 0
            ts.append(x['T']); owns[x['own']] += 1; sigs.add(x['sig'])
            for k in x['kids']:
                kidT[k[0]][k[1]] += 1
            key = x['sig'] + ' %d' % x['own'] + ' ' + ','.join(k[0] + ':' + k[3] for k in x['kids'])
            if per[key] < KEEP and not x['irq']:
                per[key] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS], 'W': W, 'CNT': CNT, 'ANG': ANG, 'WK': WK,
            'runs': n_runs, 'irq_runs': n_irq, 'blocks': blocks, 'paths': len(sigs), 'T': [min(ts), max(ts)],
            'T_median': sorted(ts)[len(ts) // 2],
            'own': [min(owns), max(owns)], 'own_distinct': len(owns),
            'kid_T': {k: [min(v), max(v), sum(v.values())] for k, v in sorted(kidT.items())},
            'paths_list': sorted(sigs), 'forced_paths_new': sorted(sigs_forced - sigs),
            'unmodelled_kids': others,
            'contended': contended,
            'window': {'frames': WINDOW, 'state': 'round1_48', 'off': wres[0], 'on': wres[1]},
            'model': {'bad': bad, 'checked': n_checked},
            'rows': rows}


def report(F):
    print('runs %d (irq %d, blocks %d) paths %d T %s median %d own %s/%d | rows %d' % (
        F['runs'], F['irq_runs'], len(F['blocks']), F['paths'], F['T'], F['T_median'], F['own'],
        F['own_distinct'], len(F['rows'])))
    print('model: bad %d of %d' % (len(F['model']['bad']), F['model']['checked']))
    for b in F['model']['bad'][:12]: print('  BAD', b)
    for b in F['blocks']: print('  BLOCK', b)
    print('kid T:', F['kid_T'])
    print('unmodelled kids:', F['unmodelled_kids'][:6])
    print('paths:'); [print('  ', s) for s in F['paths_list']]
    print('forced new:'); [print('  ', s) for s in F['forced_paths_new']]
    for x in F['rows']:
        if x['state'] in CALLS_BY:
            print('  %-14s T %6d own %5d %s | %s' % (x['state'], x['T'], x['own'], x['sig'],
                                                   [(k[0], k[1], k[2]) for k in x['kids']]))
    n0, t0 = F['contended']['round1_48'][0]; n1, t1 = F['contended']['round1_48'][1]
    print('round1_48 uncontended %d runs mean %.3f | contended %d runs mean %.3f' % (n0, t0 / n0, n1, t1 / n1))
    w0, w1 = F['window']['off'], F['window']['on']
    print('window %d frames: contended %d runs %d T mean %.3f ; uncontended %d runs %d T mean %.3f ; K %.6f ; sigs %s %s' % (
        WINDOW, w1[0], w1[1], w1[1] / w1[0], w0[0], w0[1], w0[1] / w0[0], (w1[1] / w1[0]) / (w0[1] / w0[0]), w0[2], w1[2]))


def main():
    args = sys.argv[1:]
    t0 = time.time()
    F = json.loads(json.dumps(measure(G.jobs_arg(args))))
    rc = G.finish(F, FIXTURE, args, report)
    print('%.0f s' % (time.time() - t0))
    sys.exit(rc)


if __name__ == '__main__':
    main()
