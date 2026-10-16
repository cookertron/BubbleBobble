"""M7.114d (measurement) -- THE INSTRUCTION GRID OF EVERY PASS, and the instruction each interrupt is taken after.

M7.114c replayed each ISR's own access program from its ACCEPTANCE PHASE -- the end of the instruction in progress at
the boundary -- and the engine knew that phase only at a HALT (else BB_ISR_ACCEPT, 4 T, PROVISIONAL).  This oracle
measures, on the REAL LOAD (passacc's drive: boot.pkl's $F5BC, the KEYBOARD menu, the title, round 1 and play, keys at
each ISR's end), every main-loop pass of frames FIRST..LAST (passacc's window):

  passes   frame, wall phase, the number of main-line instructions in the pass and the SHA-1 of its GRID -- each
           instruction's plain offset from $8D0C (T less the ISRs' T and the contention delays before it) and its plain T
           ('o:t;' per instruction, the ISRs bracketed out)
  isrs     every interrupt accepted inside a pass: its label (the boundary), the pass's index, the instruction it was
           taken after (index, plain offset, plain T) and the acceptance phase (T mod 69,888 at that instruction's end)

ASSERTED: each pass's instructions TILE it (each starts where the last ended); each ISR's acceptance is at the end of
an instruction that started before its boundary -- or of the one after an EI that did (the Z80 takes no interrupt
straight after EI: $8D0C's).  No ROM byte: offsets, T, phases and digests only.

Usage:  python tools/insgrid.py            (-> build/insgrid_fixture.json, ~15 s)
        python tools/insgrid.py verify     (re-measure, compare, say MATCH)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP
from skoolkit.cmiosimulator import DELAYS_48K
import passacc as pa

FIXTURE = 'build/insgrid_fixture.json'
FD = 69888
FIRST, LAST = pa.FIRST, pa.LAST


def digest(ins):
    return hashlib.sha1(''.join('%d:%d;' % (o, t) for o, t in ins).encode()).hexdigest()[:16]


def measure():
    h, m, r = world('boot')
    seq = expand(pa.SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    sim.t0, sim.t1 = -1, 1 << 40
    ia = h.int_active
    assert h.frame_duration == FD
    nb = (r[T] // FD + 1) * FD
    st = {'P': None, 'isr': None, 'isr_t0': 0, 'd': 0}
    frame, in_scan, pending = 0, False, None
    passes, isrs = [], []
    cm.keys(h, keyf(0))
    oc = sim.contend

    def cont(t, timings):
        tt = t
        for a, ts in timings:
            if 0x4000 <= a < 0x8000:
                d = DELAYS_48K[tt % FD]
                st['d'] += d; tt += d
            tt += ts
        return oc(t, timings)
    sim.contend = cont
    while frame <= LAST:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += FD
        isr = st['isr']
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            if in_scan: pending = keyf(isr[2])
            else: cm.keys(h, keyf(isr[2]))
            P = st['P']
            if P is not None: P['I'] += r[T] - st['isr_t0']
            st['isr'] = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending); pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        if pc == 0x8D0C and st['isr'] is None:
            P = st['P']
            if P is not None: passes.append(P)
            st['P'] = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'ins': [], 'ei': []} \
                if FIRST <= frame <= LAST else None
        P = st['P']
        main = st['isr'] is None
        t0, op = r[T], mem[pc]
        st['d'] = 0
        ops[op]()
        if main and P is not None:
            P['ins'].append((t0 - P['t0'] - P['D'] - P['I'], r[T] - t0 - st['d']))
            P['ei'].append(op == 0xFB)
            P['D'] += st['d']
        if r[IFF] and r[T] % FD < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert st['isr'] is None, 'an interrupt inside the ISR'
                st['isr_t0'] = t_
                lab = frame + (1 if r[T] >= nb else 0)
                st['isr'] = (b0, s0, lab)
                if P is not None and main:
                    isrs.append([lab, len(passes), len(P['ins']) - 1, t_ % FD, t_ - t_ % FD, t0])
    sim.contend = oc
    return passes, isrs


def build():
    passes, isrs = measure()
    rows = []
    for P in passes:
        ins = P['ins']
        for (o0, t0), (o1, _) in zip(ins, ins[1:]):
            assert o1 == o0 + t0, 'frame %d: the pass\'s instructions do not tile at %d' % (P['f'], o1)
        rows.append([P['f'], P['ph'], len(ins), digest(ins)])
    out = []
    for lab, pi, ii, ph, bnd, tstart in isrs:
        if pi >= len(passes): continue                   # the pass the window's end cuts
        P = passes[pi]
        o, t = P['ins'][ii]
        # the instruction it was taken after started before the boundary -- or follows an EI that did
        assert tstart < bnd or (ii > 0 and P['ei'][ii - 1]), 'ISR %d: taken after an instruction that began past it' % lab
        out.append([lab, pi, ii, o, t, ph])
    return {'window': [FIRST, LAST], 'script': [[n, k] for n, k in pa.SCRIPT], 'passes': rows, 'isrs': out,
            'n_passes': len(rows), 'n_ins': sum(r[2] for r in rows)}


if __name__ == '__main__':
    out = build()
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        old = json.load(open(FIXTURE))
        print('MATCH' if json.loads(json.dumps(out)) == old else 'DIFFER')
    else:
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote %s: %d passes, %d instructions, %d ISRs inside them' % (FIXTURE, out['n_passes'], out['n_ins'],
                                                                         len(out['isrs'])))
