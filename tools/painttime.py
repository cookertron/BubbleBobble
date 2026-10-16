"""M7.110: THE TITLE'S PAINT IN TIME -- $970F..$9765 (the CLS, the starfield, the four strings, the credit line),
interrupts ON, against the machine frame by frame.

THE WORLD.  The real load: loadpath.py's kbd_sinclair drive from boot.pkl's own $F5BC to the FIRST $970F on the main
line ($970E's EI done, the CALL $97EB next).  Recorded there (game RAM and the display only -- no ROM byte): the frame
phase, the display file and attributes ($4000..$5AFF), the PRNG $FE86/$FE87, $FED3, the ISR's counter $8DBD and its
gates $FEC4/$FEC5, and the T of the ISR before.

THE PROGRAM.  The plain run (CMIOSimulator, no contention, interrupts off -- isrcarry.plain's way) from $970F to $9765:
the instruction count, the T sum, and a CRC-32 of 'PC:T:k,k;' over every instruction (k: each contended access's T
into it) -- what the engine's BB_PAINT program must be, instruction for instruction.

THE RUNS.  From the $970F state, saved once: its own phase and FORCED phases.  Each samples at every frame boundary as
loadpath does (the instruction in progress finished, the interrupt accepted, none of the ISR run) until RING frames past
the arrival at $9765: the paint's main-line instructions done since $970F (capped at the program's length once it is
over), the ring iterations begun ($9768 on the main line), the CRC-32 of the attributes $5800..$5AFF, the CRC-32 of the
bitmap $4000..$57FF with the strings' cells zeroed (MASK: every address the main line's $8052 / $8065 / $8067 LD (HL),A
stores to -- the glyphs are the ROM's, which the port does not ship), the PRNG.  The mask itself: its size and the CRC-32
of its sorted addresses ('%04X;'), so the port's string stores can be checked to land on the same cells.  And R at $9712 (the
starfield's phase: the engine's walk is R + 3 at the first $9715 read, each ISR inside adding 52 odd / 53 even), the
arrival's boundary and phase, every ISR's wall T.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/painttime.py [capture|verify]  -> build/painttime_fixture.json
"""
import sys, os, json, zlib, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, Fail, GUARD, expand
from harness import PC, T, IFF, SP, R
import loadpath as lp
import revealcont as RC

FIXTURE = 'build/painttime_fixture.json'
RING = 4                                       # boundaries sampled past the arrival at $9765
FD = 69888
FORCED = [4368 * k for k in range(1, 16)] + [100, 14300, 69800]
ISR_R = {'odd': 52, 'even': 53}                 # measured below on every run (each ISR's R step)


def to_970f(script):
    """loadpath's drive, stopped at the first $970F on the main line"""
    h, m, r = world('boot')
    seq = expand(script)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr, last_isr = 0, False, None, None, None
    cm.keys(h, keyf(0))
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            last_isr = r[T] - isr[2]
            isr = None
        if r[T] >= nb:
            frame += 1
            if in_scan:
                pending = keyf(frame)
            else:
                cm.keys(h, keyf(frame))
            nb += fd
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        if pc == 0x970F and isr is None:
            assert keyf(frame) == [], 'a key is down at $970F'
            return h, m, r, last_isr
        if mem[pc] == 0x76 and r[IFF]:
            h._fast_halt()
            continue
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0 = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b, s, t0)


def program(h):
    """(h is spent: RC.sim_of puts its logging simulator in h.sim)  the plain stream $970F..$9765: count, T, CRC-32 of 'PC:T:k,k;', the contended accesses"""
    log = []
    sim = RC.sim_of(h, log)
    r, mem = sim.registers, sim.memory
    s, n0, tsum, nacc = [], 0, 0, 0
    while r[PC] != 0x9765:
        p, ts = r[PC], r[T]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        sim.opcodes[mem[p]]()
        ks = [x - ts for x in log[n0:]]
        n0 = len(log)
        nacc += len(ks)
        tsum += r[T] - ts
        s.append('%04X:%d:%s;' % (p, r[T] - ts, ','.join(map(str, ks))))
    return {'n_ins': len(s), 'T': tsum, 'n_acc': nacc, 'crc': zlib.crc32(''.join(s).encode())}


def paint(h, m, r, n_paint, phase=None):
    """from $970F (the state loaded): `phase` moves the clock so $970F falls there"""
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    if phase is not None:
        r[T] += (phase - r[T] % fd) % fd
    p0 = r[T] % fd
    nb = (r[T] // fd + 1) * fd
    h.ports.release_all()
    done, iters, rows, isrs, isr, k, arr, r9712, after = 0, 0, [], [], None, 0, None, None, 0
    mask = set()

    def bitmap():
        b = bytearray(m[0x4000:0x5800])
        for a in mask:
            b[a - 0x4000] = 0
        return zlib.crc32(bytes(b))
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            isrs.append(r[T] - isr[2])
            if ((r[R] - isr[3]) & 0x7F) != ISR_R[isr[4]]:
                raise Fail('an ISR moved R by %d' % ((r[R] - isr[3]) & 0x7F))
            isr = None
        if r[T] >= nb:
            k += 1
            rows.append([min(done, n_paint), iters, zlib.crc32(bytes(m[0x5800:0x5B00])), bitmap(),
                         m[0xFE86] | m[0xFE87] << 8])
            nb += fd
            if arr is not None:
                after += 1
                if after >= RING:
                    break
            if k > 40:
                raise Fail('no $9765 within 40 frames')
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if isr is None:
            if pc == 0x9712 and r9712 is None:
                r9712 = r[R] & 0x7F
            if pc == 0x9765 and arr is None:
                arr = [k, r[T] % fd]
                if done != n_paint:
                    raise Fail('%d main-line instructions to $9765, the plain run %d' % (done, n_paint))
            if pc == 0x9768:
                iters += 1
            if pc in (0x8052, 0x8065, 0x8067) and arr is None:
                a = r[6] << 8 | r[7]
                if not 0x4000 <= a < 0x5800:
                    raise Fail('a string store at $%04X' % a)
                mask.add(a)
            done += 1
        assert mem[pc] != 0x76, 'a HALT at $%04X' % pc
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0, r0 = r[PC], r[SP], r[T], r[R]
            odd = (mem[0x8DBD] + 1) & 1
            if sim.accept_interrupt(r, mem, pc):
                assert isr is None, 'an interrupt inside the ISR'
                isr = (b, s, t0, r0, 'odd' if odd else 'even')
    return {'phase': p0, 'r9712': r9712, 'arrive': arr, 'rows': rows, 'isrs': isrs,
            'mask': [len(mask), zlib.crc32(''.join('%04X;' % a for a in sorted(mask)).encode())]}


def capture():
    h, m, r, last_isr = to_970f(lp.SCRIPTS['kbd_sinclair'])
    fd = h.frame_duration
    st = h.save_state()
    at = {'phase': r[T] % fd, 'screen_b64': base64.b64encode(bytes(m[0x4000:0x5B00])).decode(),
          'prng': m[0xFE86] | m[0xFE87] << 8, 'fed3': m[0xFED3], 'ctr': [m[0x8DBD], m[0x8DBE]],
          'gates': [m[0xFEC4], m[0xFEC5]], 'isr_before': last_isr}
    prog = program(to_970f(lp.SCRIPTS['kbd_sinclair'])[0])   # its own harness: sim_of swaps h.sim for a logger
    runs = {'natural': paint(h, m, r, prog['n_ins'])}
    for p in FORCED:
        h.load_state(st)
        runs['forced_%d' % p] = paint(h, m, r, prog['n_ins'], phase=p)
    out = {'meta': {'tool': 'tools/painttime.py', 'no_rom_bytes': True,
                    'note': 'the display file at $970F (the load drew it), game-RAM bytes, counts, T, CRC-32s; '
                            'the world is loadpath kbd_sinclair'},
           'at_970f': at, 'program': prog, 'isr_r': ISR_R, 'ring': RING, 'runs': runs}
    print('program', prog)
    for name, d in runs.items():
        print('%-16s phase %5d  R9712 %3d  arrive %s  frames %d  isrs %s' % (
            name, d['phase'], d['r9712'], d['arrive'], len(d['rows']), sorted(set(d['isrs']))))
    return out


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
    return 0


if __name__ == '__main__':
    sys.exit(main())
