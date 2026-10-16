"""PA4c: THE COLD START'S ACCESS PROGRAM -- $F5CC -> $8CCA (LD HL,$F5D2 / JP $7274 -> JP $8CC3: DI / LD SP,$96DD /
CALL $95F3 ... the cold start, interrupts OFF), as the machine runs it.

Until PA4c the engine charged this stretch by BB_SPINE.COLD_PH (loadspine.py 'cold': 64 phases, every 1,092 T) with
straight lines between the samples: exact at a sample, up to ~150 T off between them -- and on the real load (the hand-over
at the phase the probe ends at) 0.218 T over the machine, the fraction PA4 pinned from M7.114c on.

THE PROGRAM.  The plain run (no contention) is ONE sequence: its T, and every contended access ($4000..$7FFF, SkoolKit's
contend() hook with its window forced open) as its plain offset from $F5CC.  The engine replays it from the phase the
stretch begins at -- each access waits the ULA's delay at its wall phase (DELAYS_48K) -- for the stretch's T.

ASSERTED: one program (count and SHA-1 of the offsets) from loadspine's world ('p4p3' and 'p2p2') and from the REAL LOAD
(passacc's drive and script, boot.pkl's $F5BC: the KEYBOARD menu, the redefinition, '2') at its own phase; and the replay
equals the machine's T at loadspine's 64 phases and 16 midpoints, 400 random phases, and the real load's.

Shipped as 'lz': per access its step from the one before as LEB128, packed by r1tail's byte LZ77.  Offsets, T, phases and
digests only -- no ROM byte, no tape byte.

Usage:  python tools/coldstart.py [capture|verify|emit]  -> build/coldstart_fixture.json  (emit: the JS data string)
"""
import sys, os, json, base64, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, run_to, GUARD, expand, Fail
from harness import PC, T, IFF, SP
from skoolkit.cmiosimulator import DELAYS_48K
import loadspine as ls
import passacc as pa
from r1tail import lz, unlz, leb

FIXTURE = 'build/coldstart_fixture.json'
FD = 69888
START, END = 0xF5CC, 0x8CCA


def digest(prog):
    return hashlib.sha1(''.join('%d;' % o for o in prog).encode()).hexdigest()[:16]


def run(h, st, ph=None, rec=None):
    """$F5CC -> $8CCA from the saved state (at the phase given, or its own), interrupts off: (T, D)"""
    r, sim = h.sim.registers, h.sim
    h.load_state(st)
    if ph is not None:
        r[T] = (r[T] // FD) * FD + ph
    if r[PC] != START:
        raise Fail('the state is not at $F5CC')
    t0, D = r[T], [0]
    oc = sim.contend
    sim.t0, sim.t1 = -1, 1 << 40

    def cont(t, timings):
        tt = t
        for a, ts in timings:
            if 0x4000 <= a < 0x8000:
                d = DELAYS_48K[tt % FD]
                if rec is not None:
                    rec.append(tt - t0 - D[0])
                D[0] += d
                tt += d
            tt += ts
        return oc(t, timings)
    sim.contend = cont
    try:
        h.run_until({END} | GUARD, limit=10 ** 6, interrupts=False, stride=1)
    finally:
        sim.contend = oc
    if r[PC] != END:
        raise Fail('$8CCA not reached')
    return r[T] - t0, D[0]


def replay(prog, plain, ph):
    D = 0
    for o in prog:
        D += DELAYS_48K[(ph + o + D) % FD]
    return plain + D


def spine_state(path):
    h, m, r = ls.at(path)
    cm.keys(h, [])
    run_to(h, (START,), True, limit=10 ** 8)
    return h, h.save_state()


def real_load_state():
    """the real load (passacc's script, keys at each ISR's end, a scan's keys held to its end) to $F5CC"""
    h, m, r = world('boot')
    seq = expand(pa.SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    ia = h.int_active
    nb = (r[T] // FD + 1) * FD
    frame, in_scan, pending, isr = 0, False, None, None
    cm.keys(h, keyf(0))
    while r[PC] != START:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += FD
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            if in_scan:
                pending = keyf(isr[2])
            else:
                cm.keys(h, keyf(isr[2]))
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        ops[mem[pc]]()
        if r[IFF] and r[T] % FD < ia:
            b0, s0 = r[PC], r[SP]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
        if frame > 2000:
            raise Fail('$F5CC not reached on the real load')
    return h, h.save_state(), frame, r[T] % FD


def capture():
    h, st = spine_state('p4p3')
    prog = []
    t, d = run(h, st, 0, prog)
    plain = t - d
    g = digest(prog)
    checked = 0
    phs = [k * ls.STEP for k in range(64)] + [k * ls.STEP + ls.STEP // 2 for k in range(0, 64, 4)] + \
        random.Random(0x8CCA).sample(range(FD), 400)
    for ph in phs:
        p2 = [] if ph % ls.STEP == 0 and ph // ls.STEP % 16 == 0 else None
        t, d = run(h, st, ph, p2)
        if t - d != plain or (p2 is not None and digest(p2) != g):
            raise Fail('phase %d: a different plain run (%d) or program' % (ph, t - d))
        if replay(prog, plain, ph) != t:
            raise Fail('phase %d: the replay gives %d, the machine %d' % (ph, replay(prog, plain, ph), t))
        checked += 1
    h2, st2 = spine_state('p2p2')
    p2 = []
    t, d = run(h2, st2, None, p2)
    if digest(p2) != g or t - d != plain:
        raise Fail('p2p2: not the same program')
    h3, st3, frame, rph = real_load_state()
    p3 = []
    rt, rd = run(h3, st3, None, p3)
    if digest(p3) != g or rt - rd != plain or replay(prog, plain, rph) != rt:
        raise Fail('the real load: not the same program, or the replay is not its T')
    steps = bytearray()
    last = 0
    for o in prog:
        steps += leb(o - last)
        last = o
    z = lz(bytes(steps))
    assert unlz(z) == bytes(steps)
    print('cold start: plain %d T, %d accesses (%s), replay exact at %d phases + p2p2 + the real load '
          '(frame %d, phase %d: %d T); lz %d bytes' % (plain, len(prog), g, checked, frame, rph, rt, len(z)))
    return {'meta': {'tool': 'tools/coldstart.py', 'no_rom_bytes': True,
                     'note': 'the cold start $F5CC -> $8CCA: plain T, its contended accesses\' plain offsets (count, '
                             'SHA-1, LEB128 steps packed by a byte LZ77), the real load\'s phase and T'},
            'plain': plain, 'n_acc': len(prog), 'digest': g, 'checked': checked,
            'real': {'frame': frame, 'phase': rph, 't': rt},
            'samples': [[ph, replay(prog, plain, ph)] for ph in phs[80:120]],
            'lz': base64.b64encode(z).decode()}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture()))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd == 'emit':
        print("  COLD: '%s'," % json.load(open(FIXTURE, encoding='utf-8'))['lz'])
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
