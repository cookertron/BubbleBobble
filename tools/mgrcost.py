"""M7.73 -- THE BUBBLE MANAGER $B62C'S T, SLOT BY SLOT: the skeleton and its arms, UNCONTENDED.

The even ISR's half, $B62C (the blow checks, then all twelve bubble slots), was charged
MGR_FRAME_FIXED + BLOW_CHECK + PER_BUBBLE x pool -- a flat 5,300 T slope per live bubble.  This
oracle brackets every pass by CONTROL FLOW on an UNCONTENDED machine, so a part's T is the sum of
its instructions' own T:

  tot      $B62C -> its return to $8D8F (the final RET in it)
  pro      $B62C .. $B63F less the blow arm: the flash toggle, the CALL $BD2C, the loop set-up
  blow     the arm $BD2C (entered by $B633's CALL) -> $B636
  slot     $B63F -> the next $B63F, the last one -> $B678 (the RET is `ret`)
  arms     inside a slot, each callee or jumped-to arm, entered at the skeleton's own SP:
             travel  $BDFE (JP z at $B648)      -> $B66C
             held    $B6C3 (JP nz at $B64D)     -> $B66C   (a holding bubble's pop)
             rise    $B836 (CALL at $B650)      -> $B653
             draw    $B9E7 (CALL at $B653)      -> $B656
             agepop  $B6D8 (CALL m at $B669)    -> $B66C
             escape  $B679 (JR nz at $B664)     -> $B66C
  skel     slot - its arms: $B62C's own instructions, a closed function of the slot's path
           through the six branches $B644 $B648 $B64D $B65E $B664 $B669 (`sig`, a letter each:
           t taken, f fell through)

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script
through each player's own key table (so the players blow).  The parts tile the whole on every
pass (asserted).

  rows     per distinct (sig, skel, slot, flags) up to KEEP slots: the slot's index, sig and skeleton T, and the
           bytes the skeleton itself READ, as it read them: `read` = [the flags C at $B644, $B657 at
           $B656 before the flip, (IY+9) at $B660, (IY+4) at $B666] (null where the path skips it)
  pro_ret  every pass's (pro, ret), counted
  arms     every arm run's T by arm (a histogram) -- the medians the engine charges, PROVISIONAL

Usage:  python tools/mgrcost.py [--jobs N]          (-> build/mgrcost_fixture.json)
        python tools/mgrcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, C
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/mgrcost_fixture.json'
FRAMES = 300
KEEP = 2
ENTRY, BACK, TOP, BOTTOM, LAST = 0xB62C, 0x8D8F, 0xB63F, 0xB66C, 0xB678
BRANCH = (0xB644, 0xB648, 0xB64D, 0xB65E, 0xB664, 0xB669)
JUMPED = {0xBDFE: 'travel', 0xB6C3: 'held', 0xB679: 'escape'}         # entered at the skeleton's SP
CALLED = {0xB836: ('rise', 0xB653), 0xB9E7: ('draw', 0xB656), 0xB6D8: ('agepop', 0xB66C),
          0xBD2C: ('blow', 0xB636)}                                   # entered one word down
ARMS = ('blow', 'travel', 'held', 'rise', 'draw', 'agepop', 'escape')


def run(name, frames=FRAMES):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(name))
    r, op, raw = h.sim.registers, h.sim.opcodes, h.memobj.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    passes, pa, arm = [], None, None
    while r[T] < t_end:
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                        if sel == 0x1F: h.ports.kempston |= mask
                        else: h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p, t, sp = r[PC], r[T], r[SP]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if pa is None:
            if p == ENTRY:
                pa = {'t0': t, 'sp': sp, 'slots': [], 'arms': [], 'blow': 0}
        else:
            if arm is not None and p == arm[1] and sp == pa['sp']:
                T_ = t - arm[2]
                if arm[0] == 'blow':
                    pa['blow'] = T_
                else:
                    pa['slots'][-1]['arms'].append((arm[0], T_))
                pa['arms'].append((arm[0], T_)); arm = None
            if arm is None:
                if p == BACK and sp == (pa['sp'] + 2) & 0xFFFF:
                    pa['tot'] = t - pa['t0']
                    passes.append(pa); pa = None
                elif sp == pa['sp']:
                    if p == TOP or p == LAST:
                        if pa['slots']:
                            pa['slots'][-1]['end'] = t
                        else:
                            pa['pro'] = t - pa['t0'] - pa['blow']
                        if p == TOP:
                            pa['slots'].append({'t': t, 'arms': [], 'sig': ''})
                        else:
                            pa['ret0'] = t
                    elif p in JUMPED:
                        arm = (JUMPED[p], BOTTOM, t)
                elif sp == (pa['sp'] - 2) & 0xFFFF and p in CALLED:
                    arm = (CALLED[p][0], CALLED[p][1], t)
        if pa is not None and arm is None and sp == pa['sp'] and pa['slots']:
            s = pa['slots'][-1]
            if p == 0xB644: s['f'] = r[C]                        # the flags the slot is routed by
            elif p == 0xB656: s['tg'] = raw[0xB657]              # the age toggle before its flip
            elif p == 0xB660: s['i9'] = raw[h.iy() + 9]          # (IY+9) as the age reads it
            elif p == 0xB666: s['i4'] = raw[h.iy() + 4]          # (IY+4) before its INC
        if raw[p] == 0x76:
            assert pa is None, 'HALT inside the pass'
            h._fast_halt()
        else:
            op[raw[p]]()
            if pa is not None and arm is None and p in BRANCH and sp == pa['sp']:
                pa['slots'][-1]['sig'] += 'f' if r[PC] == (p + (3 if p in (0xB648, 0xB64D, 0xB669) else 2)) else 't'
            if r[IFF] and r[T] % fd < ia:
                assert pa is None, 'an interrupt inside the pass'
                h.sim.accept_interrupt(r, h.memobj, p)
    out = []
    for x in passes:
        ret = x['tot'] - (x['ret0'] - x['t0'])
        sl = [(s['sig'], s['end'] - s['t'] - sum(v for _, v in s['arms']),
               [s.get(k) for k in ('f', 'tg', 'i9', 'i4')]) for s in x['slots']]
        assert len(sl) == 12, len(sl)
        assert x['pro'] + x['blow'] + sum(s['end'] - s['t'] for s in x['slots']) + ret == x['tot']
        out.append({'pro': x['pro'], 'ret': ret, 'slots': sl, 'arms': x['arms'], 'tot': x['tot']})
    return out


def measure(jobs):
    with Pool(jobs) as pool:
        res = pool.map(run, A.STATES)
    rows, seen, arms, tiled = [], collections.Counter(), {a: collections.Counter() for a in ARMS}, 0
    pro = collections.Counter()
    for nm, P in zip(A.STATES, res):
        for x in P:
            tiled += 1
            pro[(x['pro'], x['ret'])] += 1
            for a, v in x['arms']:
                arms[a][v] += 1
            for k, (sig, sk, rd) in enumerate(x['slots']):
                if seen[(sig, sk, k, rd[0])] < KEEP:
                    seen[(sig, sk, k, rd[0])] += 1
                    rows.append({'state': nm, 'slot': k, 'sig': sig, 'skel': sk, 'read': rd})
    med = {}
    for a, c in arms.items():
        v = sorted(c.elements())
        med[a] = v[len(v) >> 1] if v else None
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'passes_tiled': tiled,
            'pro_ret': sorted([[a, b, n] for (a, b), n in pro.items()]),
            'sigs': sorted(set(r['sig'] for r in rows)), 'rows': rows,
            'arms': {a: sorted([[t, n] for t, n in c.items()]) for a, c in arms.items()},
            'median': med}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 12
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('passes %d  rows %d  pro/ret %s' % (F['passes_tiled'], len(F['rows']), F['pro_ret']))
    print('sigs', {s: sorted(set(r['skel'] for r in F['rows'] if r['sig'] == s)) for s in F['sigs']})
    print('runs', {a: sum(n for _, n in v) for a, v in F['arms'].items()})
    print('median', F['median'])


if __name__ == '__main__':
    main()
