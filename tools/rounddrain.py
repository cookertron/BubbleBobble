"""RA1..RA4 -- THE ROUND ADVANCE'S DRAIN, as MAIN-LINE T and an ISR ledger.

$8D09 CALL $97F8 runs, on the machine, with the interrupt firing all the way through:
    $97F8..$9887   the advance, the clear walk ($FEC4/$FEC5 := 0) and the build -- every
                   ISR here is GATE-CLOSED (488/493 T), it only counts
    $9887 HALT     waits FOR the interrupt; that ISR sees the arm ($FEC4 := 20/88), so
                   its branch -- the PARITY of counter B -- decides whether $A3AD+$AA60 run
    $9888..$98B4   counters zeroed, the tail, then $98AF $FEC5 := 42
    $98B5..$8D0C   the banner (256 iterations), then RET to the loop top
The port spends MAIN-LINE T and lets step() run the ISRs, so every number here is
main-line: wall T minus the T of every ISR bracketed inside the span (entry to the
return to the interrupted PC with the same SP -- control flow, never SP alone).

  handoff  the title's $97F8 on the S0 world of gameover.phase_title_wait, keys 1 and 2
           (asserted equal to title_wait.start_8d0c's rows: same T, same ISR counts)
  sweep    in play: the hand-off, F frames, then $FECD := 80 at a loop top -- rounds
           2..81 back to back (20/40/60 WARP to 81 on this world), keys 1 and 2; and
           rounds 20/40/60 driven again with both +$5A bit 7 set, so the warp is refused
  aa60     the $AA60 bracket ($AA60 -> $8D8F) split by $B54B: DIVERTED ($AA72 JP nz,$B520)
           or not, on the hand-off's drain

Usage:  python tools/rounddrain.py        (-> build/rounddrain_fixture.json)
"""
import sys, os, json, statistics
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
from harness import R as RR_
import portconfig as pc
from keyprobe import KEYMAP, keymask

FIXTURE = 'build/rounddrain_fixture.json'
CS_PATCH = (0x8DC4, 0x8E05, 0x8E0A); TP_R0 = 107; TP_SEED = 0x002A; TP_POISON = 0xAA
TP_START, TP_END = 0x970F, 0x9765; RESET = 0x96DF
GLO, GHI = 0xD000, 0xD300                         # $D167 guard
MS = (0x97F8, 0x9858, 0x9884, 0x9887, 0x9888, 0x98AF, 0x98B5, 0x8D0C)
SEGS = ((0x97F8, 0x9887, 'build'), (0x9887, 0x9888, 'halt'), (0x9888, 0x98B5, 'tail'),
        (0x98B5, 0x8D0C, 'banner'), (0x97F8, 0x8D0C, 'all'))
F_PLAY = 10


def s0():
    """gameover.phase_title_wait's S0: round1_48, the stack as $8D02 builds it, $96DF run
       to $970F, GROUP 1's conditions, the paint to $9765 with interrupts off."""
    h = Harness(contended=True)
    h.load_state_file(pc.state_path('round1_48'))
    m, r = h.memobj.m, h.sim.registers
    assert [m[a] for a in CS_PATCH] == [0xC9] * 3
    m[0x96DB], m[0x96DC] = 0xDC, 0x8C
    m[0x96D9], m[0x96DA] = 0x09, 0x8D
    r[SP], r[PC], r[IFF] = 0x96D9, RESET, 0
    op, mem = h.sim.opcodes, h.sim.memory

    def go(stop):
        n = 0
        while r[PC] not in stop:
            assert mem[r[PC]] != 0x76
            op[mem[r[PC]]](); n += 1; assert n < 2_000_000
    go((TP_START,))
    m[0xFE86], m[0xFE87] = TP_SEED & 0xFF, TP_SEED >> 8
    m[0xFEBB] = 0xFF
    for a in range(0x4000, 0x5C00):
        m[a] = TP_POISON
    r[RR_] = TP_R0; r[IFF] = 0
    go((TP_END,))
    r[IFF] = 1
    return h


def ledger(h, stop, on_main=None):
    r, op, mem = h.sim.registers, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    isrs, cur = [], None
    while True:
        p = r[PC]
        assert not (GLO <= p < GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and p == cur['ret'] and r[SP] == cur['sp']:
            cur['cost'] = r[T] - cur['t0']; cur['b_post'] = mem[0x8DBD]
            if cur['a0'] is not None:
                cur['aa60'] = None                 # entered, never returned: impossible
            isrs.append(cur); cur = None
        if cur is None:
            if on_main:
                on_main(p, isrs)
            if stop(p, isrs):
                return isrs
        else:
            if p == 0xAA60 and cur['a0'] is None:
                cur['a0'] = (r[T], mem[0xB54B])
            elif p == 0x8D8F and cur['a0'] is not None:
                cur['aa60'] = [cur['a0'][1] != 0, r[T] - cur['a0'][0]]; cur['a0'] = None
        acc = None
        if mem[p] == 0x76:
            t = r[T]; tt = t if t % fd < ia else (t // fd + 1) * fd; sp0 = r[SP]
            h._fast_halt()
            if r[PC] != (p + 1) & 0xFFFF:
                acc = ((p + 1) & 0xFFFF, sp0, tt)
        else:
            op[mem[p]]()
            if r[IFF] and r[T] % fd < ia:
                b, spb, tt = r[PC], r[SP], r[T]
                if h.sim.accept_interrupt(r, mem, p):
                    acc = (b, spb, tt)
        if acc is not None:
            cur = {'ret': acc[0], 'sp': acc[1], 't0': acc[2], 'b_pre': mem[0x8DBD],
                   'fec4': mem[0xFEC4], 'fec5': mem[0xFEC5], 'b54b': mem[0xB54B],
                   'a0': None, 'aa60': None}


def one_advance(h):
    """from a main-line point before $97F8 to the loop top it RETs to."""
    r, m = h.sim.registers, h.memobj.m
    fd = h.frame_duration
    arr = {}

    def on(p, isrs):
        if p in MS and p not in arr and (p != 0x8D0C or 0x97F8 in arr):
            arr[p] = (r[T], len(isrs), m[0x8DBD], m[0xB54B], m[0x8609])
    isrs = ledger(h, lambda p, i: p == 0x8D0C and 0x97F8 in arr and r[T] > arr[0x97F8][0], on)
    t97 = arr[0x97F8][0]
    seg = {}
    for a, b, nm in SEGS:
        ii = [x for x in isrs if arr[a][0] <= x['t0'] < arr[b][0]]
        w = arr[b][0] - arr[a][0]; s = sum(x['cost'] for x in ii)
        seg[nm] = {'wall': w, 'isrs': len(ii), 'isr_T': s, 'main': w - s}
    halt = [x for x in isrs if x['ret'] == 0x9888]
    assert len(halt) == 1
    span = [x for x in isrs if x['t0'] >= t97]
    return {'round': arr[0x8D0C][4], 'players': 2 if m[0xFD91] & 0x80 else 1,
            'phase_97f8': t97 % fd, 'ctr_b_at_97f8': arr[0x97F8][2],
            'ctr_b_at_8d0c': arr[0x8D0C][2], 'b54b_at_8d0c': arr[0x8D0C][3],
            'tphase_at_8d0c': arr[0x8D0C][0] % fd, 'seg': seg,
            'halt_isr': {'b_post': halt[0]['b_post'], 'cost': halt[0]['cost'],
                         'ran_aa60': halt[0]['aa60'] is not None},
            'isrs': [[x['b_pre'], x['b_post'], x['cost'], x['fec4'], x['fec5'], x['b54b'],
                      x['aa60']] for x in span]}


def handoff(key, hold=3):
    h = s0(); r = h.sim.registers; fd = h.frame_duration
    h.ports.press(KEYMAP[key][0], keymask(KEYMAP[key][1]))
    st = {'rel': None}

    def rel(p, isrs):
        if st['rel'] is None and p in (0x9790, 0x979E):
            st['rel'] = r[T] + hold * fd
        if st['rel'] is not None and st['rel'] > 0 and r[T] >= st['rel']:
            h.ports.release_all(); st['rel'] = -1
    ledger(h, lambda p, i: p == 0x97C7, rel)
    ledger(h, lambda p, i: p == 0x97F8, rel)
    assert st['rel'] == -1
    return h, one_advance(h)


def sweep(h, n, nowarp_from=None):
    r, m = h.sim.registers, h.memobj.m
    t_end = r[T] + F_PLAY * h.frame_duration
    ledger(h, lambda p, i: p == 0x8D0C and r[T] >= t_end)
    if nowarp_from is not None:
        m[0x8609] = nowarp_from
        m[0xFDDA] |= 0x80; m[0xFDE4] |= 0x80
    m[0xFECD] = n
    return [one_advance(h) for _ in range(n)]


def main():
    GO = json.load(open('build/gameover_fixture.json'))['title_wait']['start_8d0c']
    out = {'handoff': {}, 'sweep': {}, 'nowarp': {}}
    for key in ('1', '2'):
        h, row = handoff(key)
        ref = [x for x in GO if x['key'] == key and x['world'].startswith('S0')][0]
        assert row['seg']['all']['wall'] == ref['T_97f8_to_8d0c'], (row['seg']['all'], ref['T_97f8_to_8d0c'])
        assert row['seg']['all']['isrs'] == ref['isrs_97f8_to_8d0c']
        assert row['ctr_b_at_8d0c'] == ref['ctr_b_at_8d0c']
        out['handoff'][key] = row
        out['sweep'][key] = sweep(h, 80)
        out['nowarp'][key] = []
        for r0 in (19, 39, 59):
            h2, _ = handoff(key)
            out['nowarp'][key] += sweep(h2, 1, nowarp_from=r0)
        print('key', key, 'handoff', {k: v['main'] for k, v in row['seg'].items()},
              'sweep rounds', [a['round'] for a in out['sweep'][key]][:5], '...', flush=True)
    # natural advances on the saved worlds (roundstart.py's five: bosskilled as it stands,
    # the rest with their enemy slots zeroed to force the clear) -- the phase and the
    # counter at $97F8 are what a phase-true differential needs
    out['natural'] = {}
    for st, clear in (('bosskilled', False), ('round1_48', True), ('r20_48', True),
                      ('r50_48', True), ('hurryup', True)):
        h = Harness(contended=True); h.load_state_file(pc.state_path(st)); m = h.memobj.m
        if clear:
            for k in range(7):
                for o in range(10):
                    m[0xFD94 + 10 * k + o] = 0
        ledger(h, lambda p, i: p == 0x97F8)
        out['natural'][st] = one_advance(h)
    # the $FECD ADVANCE PASS (M7.43 review): the main loop's $8D12 route runs $8D0C..$97F8
    # and nothing else -- the port charged it a whole BB_PASS_T.  Main line, interrupts
    # OFF, from a loop top on each saved world, at three entry phases.
    fp = []
    for st in ('r20_48', 'r50_48', 'round1_48'):
        for ph in (0, 23296, 46592):
            h = Harness(contended=True); h.load_state_file(pc.state_path(st))
            m, r = h.memobj.m, h.sim.registers
            r[IFF] = 0
            reason, _n = h.run_until(0x8D0C, limit=3000000, interrupts=False)
            assert reason == 'target', (st, reason)
            fd = h.frame_duration
            r[T] = (r[T] // fd) * fd + ph
            m[0xFECD] = 1
            t0 = r[T]
            reason, _n = h.run_until(0x97F8, limit=20000, interrupts=False)
            assert reason == 'target', (st, reason)
            fp.append([st, ph, r[T] - t0])
    out['fecd_pass'] = {'rows': fp, 'T': sorted(set(x[2] for x in fp))}
    assert len(out['fecd_pass']['T']) <= 2 and max(out['fecd_pass']['T']) < 200, out['fecd_pass']
    # the per-(players, round) tables the port spends
    tab = {'build': [[0] * 82, [0] * 82], 'tail': [[0] * 82, [0] * 82]}
    spread = {'build': 0, 'tail': 0}
    for key in ('1', '2'):
        p = int(key) - 1
        tab['build'][p][1] = out['handoff'][key]['seg']['build']['main']
        tab['tail'][p][1] = out['handoff'][key]['seg']['tail']['main']
        by = {}
        for a in out['sweep'][key] + out['nowarp'][key]:
            by.setdefault(a['round'], []).append(a)
        assert sorted(by) == list(range(2, 82)), sorted(by)
        for rd, xs in by.items():
            for nm in ('build', 'tail'):
                v = [x['seg'][nm]['main'] for x in xs]
                tab[nm][p][rd] = round(statistics.mean(v))
                spread[nm] = max(spread[nm], max(v) - min(v))
    allv = [a for k in ('1', '2') for a in out['sweep'][k] + out['nowarp'][k] + [out['handoff'][k]]]
    ban = [a['seg']['banner']['main'] for a in allv if a['round'] != 0x51]
    r81 = [a['seg']['banner']['main'] for a in allv if a['round'] == 0x51]
    out['tables'] = tab
    out['same_round_spread'] = spread
    out['banner_main'] = {'median': round(statistics.median(ban)), 'min': min(ban), 'max': max(ban), 'n': len(ban)}
    out['r81_main'] = {'median': round(statistics.median(r81)), 'min': min(r81), 'max': max(r81), 'n': len(r81)}
    div = [x[6][1] for k in ('1', '2') for x in out['handoff'][k]['isrs'] if x[6] and x[6][0]]
    und = [x[6][1] for k in ('1', '2') for x in out['handoff'][k]['isrs'] if x[6] and not x[6][0]]
    out['aa60'] = {'diverted': sorted(set(div)), 'undiverted': sorted(set(und))}
    json.dump(out, open(FIXTURE, 'w'), indent=0)
    print('banner main', out['banner_main'], 'r81', out['r81_main'], 'spread', spread, 'aa60', out['aa60'])
    print('wrote', FIXTURE)


if __name__ == '__main__':
    main()
