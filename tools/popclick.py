"""THE POP CLICK'S WIDTH, TAKEN APART: $B791 OUT (LOW) .. $B79E OUT (HIGH) = the award + 71 + contention.

BB_POPCLICK_PAID_T (3,924, PROVISIONAL BY RANGE) is the T between the pop click's two edges, read off
build/popkill_fixture.json's click offsets.  Between the edges the machine runs

    $B791 OUT ($FE),A 11 / $B793 PUSH IY 15 / $B795 LD A,n 7 / $B797 CALL $80FA 17
    ... $80FA, the award, to its RET (awardcost.py's T: entry to the return, RET included) ...
    $B79A POP IY 14 / $B79C LD A,$30 7                          -> $B79E OUT ($FE),A

so the width's uncontended T is the award's + BETWEEN (Zilog: 11 + 15 + 7 + 17 + 14 + 7 = 71).  This
oracle measures every click it can reach on the CONTENDED machine and splits it:

  wc       the click width as popkill measures it: T at $B79E's start - T at $B791's start, contended
  ec       the same between the two OUT port writes (the harness's write_port T): edge to edge
  ac       the award contended: T at $80FA's entry to T at $B79A (its RET in it)
  wu, eu, au   the same three re-run from the identical machine state on an UNCONTENDED simulator
  bu       wu - au: the instructions outside the award -- asserted == BETWEEN (71) on every click
  res      wc - wu: the contention; split as ra = ac - au (inside the award) and rb = res - ra
  who      $B796, A at $80FA;  paid  $80FA's own entry tests pass (who < 3 and $FD7D + 10*who bit 7)
  ph       T mod 69,888 at $B791 (the frame phase the contention depends on)

SOURCES.  (1) popkill.py's click-bearing scenarios replayed through its own Run (N1, N2, C4, C1, C2,
C3, N3, B5, B6, B7, B9, B11, B12, I14), each cut one ISR after its last click; every click's contended
width is asserted equal to the one build/popkill_fixture.json holds.  (2) NATURAL runs: every 48K saved
state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script (awardcost.py's drive),
contended, every $B791 reached.  No ROM byte is read into the fixture: only T counts are stored.

Usage:  python tools/popclick.py [--jobs N]          (-> build/popclick_fixture.json)
        python tools/popclick.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, os, json, time, collections
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, T, PC, IFF
import portconfig as pc
import aa60cost as A
import ab38cost as B
import popkill as K

FIXTURE = 'build/popclick_fixture.json'
POPKILL = 'build/popkill_fixture.json'
FRAMES = 300
LO, CALL, ENTRY, BACK, HI = 0xB791, 0xB797, 0x80FA, 0xB79A, 0xB79E
BETWEEN = 11 + 15 + 7 + 17 + 14 + 7          # Zilog: OUT (n),A / PUSH IY / LD A,n / CALL / POP IY / LD A,n
FRAME_T = 69888

# popkill's click-bearing scenarios, as its capture() runs them, nmax cut to one past the last click row
SCEN = {
    'N1': ('round1_48', K.keys_n1, 230, None, None),
    'N2': ('round1_2p48', K.keys_n2, 183, None, None),
    'C4': ('round1_2p48', K.keys_n2, 151, K.swap_players, 147),
    'C1': ('round1_48', K.keys_n1, 338, [(0xFED8 + 90 + 7, 0x0A)], 332),
    'C2': ('round1_48', K.keys_n1, 338, [(0xFED8 + 90 + 7, 0x1A)], 332),
    'C3': ('round1_48', K.keys_n1, 340, [(0xFED8 + 50 + 7, 0x0A)], 332),
    'N3': ('round1_2p48', K.keys_n3, 499, None, None),
    'B5': ('round1_2p48', K.keys_none, 9, K.stage_carry, 6),
    'B6': ('round1_48', K.keys_none, 12, K.stage_bnc(0, 0x40), 6),
    'B7': ('round1_48', K.keys_none, 12, K.stage_bnc(0, 0xC0), 6),
    'B9': ('round1_2p48', K.keys_p1right, 9, K.stage_push_p2, 6),
    'B11': ('round1_2p48', K.keys_none, 11, K.stage_bnc(0, 0x40, p1x=0x32, p2=(0x38, 16), n=1), 8),
    'B12': ('round1_2p48', K.keys_none, 11, K.stage_bnc(1, 0xC0, p1x=0x34, p2=(20, 16), n=1), 8),
    'I14': ('round1_48', K.keys_fastblow, 54, K.stage_fast, 6),
}

_HC = _HU = None


def _pair():
    global _HC, _HU
    if _HC is None:
        _HC, _HU = Harness(contended=True), Harness(contended=False)
        assert _HC.contended and not _HU.contended
    return _HC, _HU


def _replay(h, s):
    """from the machine at $B791 (state s), run to past $B79E's OUT: (width, edge width, award T)"""
    h.load_state(s)
    r = h.sim.registers
    assert r[PC] == LO and not r[IFF], 'not at $B791 with interrupts off'
    h.ports.writes = []; h.ports.record_writes = True
    t0, ta, tb = r[T], None, None
    for _ in range(400000):
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if p == ENTRY and ta is None:
            ta = r[T]
        elif p == BACK and tb is None:
            tb = r[T]
        elif p == HI:
            w = r[T] - t0
            h.step(1, interrupts=False)
            break
        h.step(1, interrupts=False)
    else:
        raise AssertionError('no $B79E')
    h.ports.record_writes = False
    ed = [t for t, port, v in h.ports.writes if port & 0xFF == 0xFE]
    assert len(ed) == 2, 'OUTs to $FE: %d' % len(ed)
    return w, ed[1] - ed[0], tb - ta


def measure_at(s, who, paid, src, at, k, inline=None):
    hc, hu = _pair()
    wc, ec, ac = _replay(hc, s)
    wu, eu, au = _replay(hu, s)
    if inline is not None:
        assert wc == inline, '%s %s: replay %d, inline %d' % (src, at, wc, inline)
    res, ra = wc - wu, ac - au
    return dict(src=src, at=at, k=k, who=who, paid=paid, ph=s[1][T] % FRAME_T,
                wc=wc, ec=ec, ac=ac, wu=wu, eu=eu, au=au, bu=wu - au, res=res, ra=ra, rb=res - ra)


def _who(m):
    who = m[0xB796]
    return who, int(who < 3 and bool(m[(0xFD7D + 10 * who) & 0xFFFF] & 0x80))


def scen(name):
    state, keyfn, nmax, poke, poke_at = SCEN[name]
    run = K.Run(state)
    h, m = run.h, run.m
    out, cur = [], {}
    orig = run.hook[LO]

    def at_lo():
        orig()
        who, paid = _who(m)
        cur['pend'] = (h.save_state(), who, paid, h.regs[T])
    run.hook[LO] = at_lo
    clicks = {}
    run.run_to(K.ISR_IN)
    pend = []
    orig_hi = run.hook[HI]

    def at_hi():
        orig_hi()
        s, who, paid, t0 = cur.pop('pend')
        pend.append((s, who, paid, h.regs[T] - t0))
    run.hook[HI] = at_hi
    for i in range(nmax):
        keys, kemp = keyfn(i)
        if poke is not None and i == poke_at:
            if callable(poke):
                poke(m)
            else:
                for a, orv in poke:
                    m[a] |= orv
        pend.clear()
        _, _, x = run.isr(keys, kemp)
        if poke is not None and i < poke_at:           # popkill records from the poke on (and these
            continue                                   # rows are its N scenario's, already measured)
        ck = [e for e in x['ev'] if e[0] == 'click']
        if ck:
            clicks[i] = ck
        for k, (s, who, paid, wi) in enumerate(pend):
            out.append(measure_at(s, who, paid, name, i, k, inline=wi))
        if run.advance:
            break
    return out, clicks


def natural(state):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    r, raw = h.sim.registers, h.memobj.m
    assert raw[0x8DC4] == 0xC9, state + ': not a 48K state'
    fd = h.frame_duration
    t_end = r[T] + FRAMES * fd
    ki, nextk, out, k, pend = 0, r[T], [], 0, None
    while r[T] < t_end:
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if p == LO:
            who, paid = _who(raw)
            pend = (h.save_state(), who, paid, r[T], (r[T] - (t_end - FRAMES * fd)) // fd)
        elif p == HI and pend is not None:
            s, who, paid, t0, fr = pend
            out.append(measure_at(s, who, paid, state, fr, k, inline=r[T] - t0))
            k += 1; pend = None
        h.step(1)
    return out, None


def one(job):
    kind, name = job
    return (scen if kind == 's' else natural)(name)


def popkill_clicks():
    d = json.load(open(POPKILL, encoding='utf-8'))
    got = {}
    for sc in d['scenarios']:
        if sc['name'] in SCEN:
            for row in sc['rows']:
                ck = [e for e in row['ev'] if e[0] == 'click']
                if ck:
                    got.setdefault(sc['name'], {})[str(row['i'])] = ck
    return got


def stats(rows):
    def rng(key, sel):
        v = [x[key] for x in rows if sel(x)]
        return [min(v), max(v)] if v else None
    by = {}
    for lab, sel in (('paid', lambda x: x['paid']), ('out', lambda x: not x['paid'])):
        by[lab] = dict(n=sum(1 for x in rows if sel(x)),
                       **{k: rng(k, sel) for k in ('wc', 'ec', 'ac', 'au', 'wu', 'res', 'ra', 'rb', 'bu')},
                       wc_freq=sorted(collections.Counter(x['wc'] for x in rows if sel(x)).items(),
                                      key=lambda kv: (-kv[1], kv[0]))[:6],
                       res_freq=sorted(collections.Counter(x['res'] for x in rows if sel(x)).items(),
                                       key=lambda kv: (-kv[1], kv[0]))[:6])
    return by


def measure(jobs):
    work = [('s', n) for n in SCEN] + [('n', s) for s in A.STATES]
    with Pool(jobs) as pool:
        res = pool.map(one, work, chunksize=1)
    rows, mismatch = [], []
    want = popkill_clicks()
    for (kind, name), (rs, clicks) in zip(work, res):
        rows += rs
        if kind == 's':
            got = {str(i): c for i, c in clicks.items()}
            if got != want.get(name, {}):
                mismatch.append(name)
    assert not mismatch, 'clicks differ from popkill_fixture: %s' % mismatch
    bad = [x for x in rows if x['bu'] != BETWEEN or x['wu'] != x['au'] + BETWEEN]
    assert not bad, 'uncontended width != award + %d: %s' % (BETWEEN, bad[:3])
    return {'note': __doc__.split('\n')[0], 'between': BETWEEN, 'frames': FRAMES,
            'scenarios': list(SCEN), 'states': A.STATES, 'popkill_match': True,
            'n': len(rows), 'stats': stats(rows), 'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    t0 = time.time()
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER', '(%d clicks, %.0f s)' % (F['n'], time.time() - t0))
        sys.exit(0 if ok else 1)
    with open(FIXTURE, 'w', encoding='utf-8') as f:
        json.dump(F, f, indent=0)
    print('wrote %s: %d clicks in %.0f s' % (FIXTURE, F['n'], time.time() - t0))
    print(json.dumps(F['stats'], indent=1))
    for x in F['rows']:
        print('  %-11s %4s %d who %d paid %d  wc %5d ec %5d ac %5d | wu %5d au %5d bu %d | res %4d ra %4d rb %3d ph %5d'
              % (x['src'], x['at'], x['k'], x['who'], x['paid'], x['wc'], x['ec'], x['ac'], x['wu'], x['au'],
                 x['bu'], x['res'], x['ra'], x['rb'], x['ph']))


if __name__ == '__main__':
    main()
