"""M7.81 -- THE HURRY'S ENTRY WINDOW, SURVEYED: can a frame interrupt land between $9037's entry and $9055?

$9037 (the HURRY UP! trigger) is called once a main-loop pass from $8D4F.  When it fires it shuts ($FEC5) at
$9052, 122 T in, and ($FEC4) at $9055, 135 T in (uncontended instruction sums, hurryblock 'direct').  An
interrupt accepted between the entry and $9055 runs with a gate open while the block's own reads were
made before it -- game.js DECLARES this window and does not model it.  The fire comes on the FIRST $9037
entry after the interrupt that counts the clock ($8DBD) past the threshold ($745C) -- hurryblock
'fireclock' -- so the candidates are exactly the first entry after each accepted interrupt, and the window
is hit iff the next interrupt is accepted within the window's T of such an entry.  A frame with NO entry
(a pass longer than a frame) is the other declared case: the clock counts twice before the next entry, and
the fire comes at threshold + 2.

This oracle plays every 48K saved state in aa60cost's list for FRAMES frames, interrupts on, CONTENDED (the
machine's own timing), under ab38cost's key script through each player's own key table, with the trigger
held off by its own latch ($9049, the operand of $9048 LD A,n: RET nz) so the world does not change -- $9037
is still entered every pass.  Per state it records every accepted interrupt's T and every $9037 entry's T,
and from them, per interrupt: the first entry after it and the T from that entry to the NEXT accepted
interrupt (the headroom), or 'none' when the next interrupt came first.  Then the FORCED probe: the state's
smallest-headroom candidate is re-run with the clock poked to fire on that entry, and the T from the entry
to $9055 is measured with every interrupt accepted in between (gate values at acceptance).

  states        per state: frames run, interrupts accepted, $9037 entries, candidates, frames with no
                entry, the smallest headroom and its entry phase (T since its interrupt), passes per frame
  hist          the candidates' headroom, binned by 1,000 T, all states together
  probe         per state: the forced fire on the closest candidate -- the entry-to-$9055 T, and any
                interrupt accepted inside it (T after the entry, $FEC4 / $FEC5 then)

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K music driver).

Usage:  python tools/hurryentry.py [--jobs N]          (-> build/hurryentry_fixture.json)
        python tools/hurryentry.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/hurryentry_fixture.json'
FRAMES = 300
ENTRY, G5, G4 = 0x9037, 0x9052, 0x9055
LATCH, FIRED = 0x9049, 0x904D           # the operands of $9048 LD A,n (disable) and $904C LD A,n (fired)
CLOCK, THRESH = 0x8DBD, 0x745C
ISR_IN = 0x8D72


def _keys(h, raw, ki):
    h.ports.release_all()
    for kt in (0xB5FD, 0xB605):
        for j, c in enumerate('LRJB'):
            sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
            if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                if sel == 0x1F:
                    h.ports.kempston |= mask
                else:
                    h.ports.press(sel, 0xFF & ~mask)


def play(name, frames, fire_at=None):
    """run `name` for `frames` frames; returns (isrs, entries).  With fire_at = n, the latch is opened and
    the clock poked past the threshold just before the n-th $9037 entry's interrupt... (see probe())"""
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(name))
    r, op, raw = h.sim.registers, h.sim.opcodes, h.memobj.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    raw[LATCH] = 1
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    isrs, entries, probe = [], [], None
    while r[T] < t_end:
        if r[T] >= nextk:
            _keys(h, raw, ki)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if p == ENTRY:
            entries.append(r[T])
            if fire_at is not None and len(entries) == fire_at + 1:
                probe = {'t0': r[T], 'isrs': [], 'g5': None, 'g4': None}
        if probe is not None:
            if p == G5 and probe['g5'] is None: probe['g5'] = r[T] - probe['t0']
            if p == G4 and probe['g4'] is None:
                probe['g4'] = r[T] - probe['t0']
                return isrs, entries, probe
        if raw[p] == 0x76:
            h._fast_halt(); isrs.append(r[T])
            if probe is not None: probe['isrs'].append([r[T] - probe['t0'], raw[0xFEC4], raw[0xFEC5]])
            if fire_at is not None and probe is None: _arm(raw, isrs, entries, fire_at)
        else:
            op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                h.sim.accept_interrupt(r, h.memobj, p); isrs.append(r[T])
                if probe is not None: probe['isrs'].append([r[T] - probe['t0'], raw[0xFEC4], raw[0xFEC5]])
                if fire_at is not None and probe is None: _arm(raw, isrs, entries, fire_at)
    return isrs, entries, probe


def _arm(raw, isrs, entries, fire_at):
    """after the interrupt that precedes the target entry (entries so far == fire_at): the clock to the
    threshold, so the ISR's own count (made inside it, from the acceptance just recorded) puts it past --
    the same counting the machine does; the latch and the fired flag cleared"""
    if len(entries) == fire_at:
        th = raw[THRESH] | (raw[THRESH + 1] << 8)
        raw[CLOCK] = th & 0xFF; raw[CLOCK + 1] = th >> 8
        raw[LATCH] = 0; raw[FIRED] = 0


def survey(isrs, entries):
    """per accepted interrupt: the first entry after it, and that entry's headroom to the next interrupt"""
    cands, none, ei = [], 0, 0
    for k in range(len(isrs) - 1):
        a, b = isrs[k], isrs[k + 1]
        while ei < len(entries) and entries[ei] < a:
            ei += 1
        if ei < len(entries) and entries[ei] < b:
            cands.append((b - entries[ei], entries[ei] - a, ei))
        else:
            none += 1
    return cands, none


def window(name, fire_at):
    """a window case, again: the RAM the gate-open interrupt changed (its stack excepted), and every byte
    the block's MAIN LOOP then reads before writing it, from that interrupt's end to $9037's RET (the
    interrupts inside the block not recorded) -- the intersection is what the port's run-ahead, which
    reads at the call, could read differently"""
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(name))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    raw[LATCH] = 1
    fd, ia = h.frame_duration, h.int_active
    ki, nextk = 0, r[T]
    isrs, entries = [], []
    st = {'phase': 0}
    regs = r

    class Reads(list):
        def append(self, x):                           # each first read with the PC that made it
            list.append(self, (x[0], x[1], regs[PC]))
    snap, wrote, isr_end, sp0, reads, after = None, None, None, None, Reads(), None
    t_end = r[T] + 2 * FRAMES * fd

    def accepted(p):
        nonlocal snap, isr_end
        isrs.append(r[T])
        if st['phase'] == 0:
            _arm(raw, isrs, entries, fire_at)
        elif st['phase'] == 1 and snap is None:
            snap = bytes(raw); isr_end = ret()
            rm.rec = None
        elif st['phase'] == 2:
            isr_end = ret(); rm.rec = None

    def ret():
        """where the interrupt just accepted returns: the address it pushed, and SP above it"""
        sp = r[SP]
        return (raw[sp] | (raw[(sp + 1) & 0xFFFF] << 8), (sp + 2) & 0xFFFF)
    while True:
        assert r[T] < t_end, name + ': the window run did not end'
        if r[T] >= nextk:
            _keys(h, raw, ki)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if isr_end is not None and p == isr_end[0] and r[SP] == isr_end[1]:
            if st['phase'] == 1:                       # the gate-open interrupt is over: its writes
                stk = r[SP]
                wrote = [a for a in range(0x4000, 0x10000) if raw[a] != snap[a] and not (stk - 0x40 <= a < stk + 2)]
                after = bytes(raw)
                st['phase'] = 2
                rm.seen = set(); rm.rec = reads; rm.wr = {}; rm.stk = sp0
            else:
                rm.rec = reads
            isr_end = None
        if p == ENTRY and st['phase'] == 0:
            entries.append(r[T])
            if len(entries) == fire_at + 1:
                st['phase'] = 1; sp0 = r[SP]
        if st['phase'] == 2 and isr_end is None and r[SP] == (sp0 + 2) & 0xFFFF:
            break                                      # $9037's RET
        if raw[p] == 0x76:
            h._fast_halt(); accepted(p)
        else:
            op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                q = r[PC]; h.sim.accept_interrupt(r, rm, q); accepted(q)
    rd = sorted(set(a for a, _, _ in reads if a >= 0x4000))
    both = sorted(set(wrote) & set(rd))
    by = {a: '%04x' % q for a, _, q in reads}
    return {'wrote': len(wrote), 'read': len(rd), 'both': [['%04x' % a, snap[a], after[a], by[a]] for a in both],
            'wrote_ranges': _ranges(wrote)}


def _ranges(xs):
    out = []
    for a in sorted(xs):
        if out and a == out[-1][1] + 1: out[-1][1] = a
        else: out.append([a, a])
    return ['%04x-%04x' % (a, b) if a != b else '%04x' % a for a, b in out]


def one(name):
    isrs, entries, _ = play(name, FRAMES)
    cands, none = survey(isrs, entries)
    if not cands:
        return {'state': name, 'isrs': len(isrs), 'entries': len(entries), 'cands': 0, 'none': none}, [], None
    head, phase, ei = min(cands)
    # the forced probe: fire on that entry (the clock armed at the interrupt before it)
    _, _, pr = play(name, FRAMES, fire_at=ei)
    st = {'state': name, 'isrs': len(isrs), 'entries': len(entries), 'cands': len(cands), 'none': none,
          'min_head': head, 'min_phase': phase, 'max_phase': max(c[1] for c in cands)}
    probe = None if pr is None else {'state': name, 'head': head, 'g5': pr['g5'], 'g4': pr['g4'],
                                     'isrs': pr['isrs'] if pr['g4'] is not None else len(pr['isrs'])}
    if probe and probe['g4'] is not None and probe['isrs']:
        probe['window'] = window(name, ei)
    return st, [c[0] for c in cands], probe


def measure(jobs):
    with Pool(jobs) as pool:
        res = pool.map(one, A.STATES)
    states, hist, probes = [], collections.Counter(), []
    for st, heads, pr in res:
        states.append(st)
        for x in heads: hist[x // 1000] += 1
        if pr: probes.append(pr)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': states, 'hist': {str(k * 1000): hist[k] for k in sorted(hist)}, 'probe': probes}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 12
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), indent=0)
    c = sum(s['cands'] for s in F['states']); n = sum(s['none'] for s in F['states'])
    print('candidates %d, frames with no entry %d, min headroom %s' % (
        c, n, min((s['min_head'], s['state']) for s in F['states'] if s['cands'])))
    for s in sorted((s for s in F['states'] if s['cands']), key=lambda s: s['min_head'])[:8]:
        print('  %-12s head %6d phase %6d none %3d' % (s['state'], s['min_head'], s['min_phase'], s['none']))
    for p in sorted(F['probe'], key=lambda p: p['head'])[:8]:
        print('  probe %-12s head %6d g5 %s g4 %s isrs %s %s' % (p['state'], p['head'], p['g5'], p['g4'], p['isrs'],
                                                              {k: v for k, v in p.get('window', {}).items() if k != 'wrote_ranges'}))
    print('hist', F['hist'])


if __name__ == '__main__':
    main()
