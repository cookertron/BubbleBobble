"""M7.86 (measurement) -- THE MAIN LOOP'S PASS, $8D0C TO $8D0C: the skeleton and its callees, UNCONTENDED.

The port charges every main-loop pass a flat BB_PASS_T (6,186 T, PROVISIONAL: round1_48's own
median).  This oracle brackets every pass by CONTROL FLOW on an UNCONTENDED machine, so a part's T
is the sum of its instructions' own T:

  pass     $8D0C (EI, SP = the loop's SP S0) -> the next $8D0C at S0.  A pass that leaves the loop
           ($8D11 RET nz, $8D6F RET nc) is not a pass: counted as `exits`, dropped.
  isr      every interrupt accepted inside a pass, from the acceptance (its acknowledge in it) to
           the return to the interrupted PC at the interrupted SP -- BRACKETED OUT of every part
  halt     a HALT inside a pass ($7EC2's EI / HALT): from the HALT to the interrupt it waits for --
           bracketed out too (the port ends the frame there, `blocked`)
  calls    each CALL made at S0 (the twenty-one chain CALLs, $8D09's CALL $97F8, $8D22's CALL z
           $7FFC): from the callee's entry (the CALL's own 17 T stays in the skeleton) to its return
           at S0, the RET in it.  A callee that leaves without returning ($94C2's two discarded
           return addresses and JP $8D09) closes when SP is back at S0 AND the PC is on the loop's
           line ($8D09..$8D71: $956C..$9570 stay in the callee) -- flagged `abn`.
           Nested CALLs/RSTs inside a callee are bracketed apart the same way (entry PC + return
           SP), so a callee's `own` T is its own instructions, its children's T reported by address.
  skel     pass - isr - halt - calls: $8D0C..$8D70's own instructions, a closed function of the
           pass's path through the main line's six branches ($8D11 $8D16 $8D22 $8D61 $8D68 $8D6F,
           a letter each: t taken, f fell through) -- `sig`
  path     a top-level call's path: a fingerprint of every (pc, next pc) where control did not fall
           through or a conditional/repeat instruction ran, nested callees in it

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through
each player's own key table (mgrcost's drive).  The parts tile the whole on every pass (asserted).
No memory value is recorded (no ROM byte can reach the fixture -- TRAPS #281); $D000..$D2FF is never
executed (asserted).

Usage:  python tools/passcost.py [--jobs N]          (-> build/passcost_fixture.json, N <= 6)
        python tools/passcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/passcost_fixture.json'
FRAMES = 300
KEEP = 2
TOP = 0x8D0C
LOOP_LO, LOOP_HI = 0x8D09, 0x8D72
BRANCH = {0x8D11: 1, 0x8D16: 2, 0x8D22: 3, 0x8D61: 2, 0x8D68: 2, 0x8D6F: 1}   # pc: length
EXITS = (0x8D11, 0x8D6F)
CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RST_OPS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1
ED_REP = {0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}
MASK = (1 << 61) - 1
BLOCK = 69888                    # a call longer than a frame is a BLOCK (hurry, storm, extend, build...)


def run(name, frames=FRAMES):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(name))
    r, op, raw = h.sim.registers, h.sim.opcodes, h.memobj.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    s0 = None
    excl = 0                         # T bracketed out so far (ISR + HALT waits), monotonic
    isr = None                       # (return pc, return sp, t at acceptance) while an ISR runs
    pa = None
    stack = []                       # open calls: [entry, ret, sp0, t0, x0, child, hash, depth1]
    passes, nested, exits = [], collections.defaultdict(collections.Counter), 0
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
        if isr is not None:
            if p == isr[0] and sp == isr[1]:
                d = t - isr[2]
                excl += d
                if pa is not None:
                    pa['isr'].append(d)
                isr = None
        if isr is None:
            # close every call whose return address has been popped
            while stack and sp >= stack[-1][2] and (len(stack) > 1 or p == stack[0][1] or LOOP_LO <= p < LOOP_HI):
                f = stack.pop()
                T_ = (t - f[3]) - (excl - f[4])
                own = T_ - f[5]
                if stack:
                    stack[-1][5] += T_
                    nested[f[0]][T_] += 1
                    if len(stack) == 1:
                        stack[0][7][f[0]] = stack[0][7].get(f[0], 0) + T_
                else:
                    pa['calls'].append((f[0], T_, own, f[6], 0 if p == f[1] else 1, f[7]))
            if p == TOP and (s0 is None or sp == s0):
                if s0 is None:
                    s0 = sp
                if pa is not None:
                    pa['tot'] = (t - pa['t0']) - (excl - pa['x0'])
                    passes.append(pa)
                pa = {'t0': t, 'x0': excl, 'sig': '', 'isr': [], 'halt': 0, 'calls': []}
        o = raw[p]
        if o == 0x76:
            assert isr is None, 'HALT inside the ISR'
            tt = t if t % fd < ia else (t // fd + 1) * fd
            h._fast_halt()
            assert r[PC] != (p + 1) & 0xFFFF, 'a HALT the interrupt did not take'
            excl += tt - t
            if pa is not None:
                pa['halt'] += tt - t
            isr = ((p + 1) & 0xFFFF, sp, tt)
            continue
        op[o]()
        np_, nsp = r[PC], r[SP]
        if isr is None and pa is not None:
            if stack:
                if COND[o] or not (0 < np_ - p <= 4) or (o == 0xED and raw[(p + 1) & 0xFFFF] in ED_REP):
                    stack[0][6] = hash((stack[0][6], p, np_)) & MASK
            elif sp == s0:
                if p in BRANCH:
                    pa['sig'] += 'f' if np_ == p + BRANCH[p] else 't'
                    if p in EXITS and np_ != p + 1:
                        exits += 1; pa = None
                else:
                    assert LOOP_LO <= p < LOOP_HI, 'main line outside the loop at %04X' % p
            if pa is not None and nsp == (sp - 2) & 0xFFFF and \
                    ((o in CALL_OPS and np_ != p + 3) or o in RST_OPS):
                ret = (p + (1 if o in RST_OPS else 3)) & 0xFFFF
                if raw[nsp] | raw[nsp + 1] << 8 == ret:
                    stack.append([np_, ret, sp, r[T], excl, 0, 0, {}])
        if r[IFF] and r[T] % fd < ia:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, h.memobj, p):
                assert isr is None, 'an interrupt inside the ISR'
                isr = (b, spb, tt)
    out = []
    for x in passes:
        skel = x['tot'] - sum(c[1] for c in x['calls'])
        out.append((x['sig'], skel, x['tot'], x['isr'], x['halt'],
                    [(c[0], c[1], c[2], c[3], c[4], sorted(c[5].items())) for c in x['calls']]))
    return out, {a: dict(c) for a, c in nested.items()}, exits, pa is not None


def summ(vals):
    v = sorted(vals.elements()) if isinstance(vals, collections.Counter) else sorted(vals)
    if not v:
        return None
    return {'n': len(v), 'total': sum(v), 'min': v[0], 'max': v[-1], 'median': v[len(v) >> 1],
            'distinct': len(set(v))}


def measure(jobs):
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(run, A.STATES)
    rows, seen = [], collections.Counter()
    sigs = collections.defaultdict(collections.Counter)
    tots, isrs, halts = collections.Counter(), collections.Counter(), collections.Counter()
    calls = collections.defaultdict(collections.Counter)
    owns = collections.defaultdict(collections.Counter)
    paths = collections.defaultdict(lambda: collections.defaultdict(set))
    abn = collections.Counter()
    kids = collections.defaultdict(collections.Counter)      # top-level callee -> child -> calls
    nested = collections.defaultdict(collections.Counter)
    per_state, n, n_exits = {}, 0, 0
    for nm, (P, N, ex, op_) in zip(A.STATES, res):
        per_state[nm] = [len(P), ex, int(op_)]
        n_exits += ex
        for a, c in N.items():
            nested['%04X' % a].update({int(k): v for k, v in c.items()})
        for sig, skel, tot, isr, halt, cl in P:
            n += 1
            assert skel + sum(c[1] for c in cl) == tot
            tots[tot] += 1
            sigs[sig][skel] += 1
            for d in isr:
                isrs[d] += 1
            if halt:
                halts[halt] += 1
            for a, T_, own, hs, ab, ch in cl:
                k = '%04X' % a
                calls[k][T_] += 1; owns[k][own] += 1
                paths[k][hs].add(T_)
                abn[k] += ab
                for ca, ct in ch:
                    kids[k]['%04X' % ca] += 1
            if seen[(sig, skel)] < KEEP:
                seen[(sig, skel)] += 1
                rows.append({'state': nm, 'sig': sig, 'skel': skel, 'tot': tot,
                             'calls': [['%04X' % c[0], c[1], c[2]] for c in cl]})
    grand = sum(sum(t * m for t, m in c.items()) for c in calls.values()) + \
        sum(s * m for c in sigs.values() for s, m in c.items())
    small = sum(sum(t * m for t, m in c.items() if t <= BLOCK) for c in calls.values()) + \
        sum(s * m for c in sigs.values() for s, m in c.items())
    callees = {}
    for k in calls:
        callees[k] = {'T': summ(calls[k]), 'own': summ(owns[k]), 'paths': len(paths[k]),
                      'path_conflicts': sum(1 for s in paths[k].values() if len(s) > 1),
                      'abnormal': abn[k], 'children': dict(sorted(kids[k].items())),
                      'share_ppm': round(1e6 * sum(t * m for t, m in calls[k].items()) / grand),
                      'blocks': sum(m for t, m in calls[k].items() if t > BLOCK),
                      'share_ppm_noblock': round(1e6 * sum(t * m for t, m in calls[k].items() if t <= BLOCK) / small),
                      'T_noblock': summ(collections.Counter({t: m for t, m in calls[k].items() if t <= BLOCK}))}
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS,
            'key_frames': B.KEY_FRAMES, 'states': A.STATES, 'per_state': per_state,
            'passes_tiled': n, 'exits': n_exits, 'pass_T': summ(tots),
            'skel': {s: sorted([[t, m] for t, m in c.items()]) for s, c in sorted(sigs.items())},
            'skel_closed': all(len(c) == 1 for c in sigs.values()),
            'isr': summ(isrs), 'halt': summ(halts), 'grand_T': grand, 'noblock_T': small,
            'skel_ppm_noblock': round(1e6 * sum(s * m for c in sigs.values() for s, m in c.items()) / small),
            'callees': dict(sorted(callees.items(), key=lambda kv: -kv[1]['share_ppm'])),
            'nested': {k: summ(c) for k, c in sorted(nested.items())},
            'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('passes %d  exits %d  pass_T %s' % (F['passes_tiled'], F['exits'], F['pass_T']))
    print('noblock skel ppm', F['skel_ppm_noblock'])
    print('skel closed', F['skel_closed'], F['skel'])
    print('isr', F['isr'], 'halt', F['halt'])
    for k, c in F['callees'].items():
        print(k, c['share_ppm'], c['T'], 'own', c['own']['min'], c['own']['max'], 'paths', c['paths'],
              'conf', c['path_conflicts'], 'abn', c['abnormal'], 'kids', len(c['children']),
              '| noblock', c['share_ppm_noblock'], c['blocks'], c['T_noblock'] and (c['T_noblock']['min'], c['T_noblock']['max'], c['T_noblock']['median']))


if __name__ == '__main__':
    main()
