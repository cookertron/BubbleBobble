"""M7.111: THE TITLE'S EXIT IN TIME -- the arm ($979E / $9790 .. $97B6), the release passes ($97B7 CALL $97EB, the CLS,
then $97BA's test of every key, interrupts ON) and the leave ($97C2 .. $97EA, its two RETs) to $8D09's CALL $97F8,
against the machine frame by frame.

THE WORLD.  The real load: painttime's drive (loadpath's kbd_sinclair) to its first $970F, then the paint run on the
machine to $9765 (the ring's start; ringtime's world).  Recorded there (game RAM and the display only, the strings'
cells zeroed -- their glyphs are the ROM's, which the port does not ship): the frame phase, the display file and
attributes, the PRNG, $FED3, the ISR's counter $8DBD/$8DBE and gates $FEC4/$FEC5, the T of the ISR before, and the
strings' cells (MASK: every address $8052 / $8065 / $8067 stored to on the main line, as painttime finds it).

THE PROGRAMS.  The plain runs (CMIOSimulator, no contention, interrupts off -- painttime's way) of each segment:
'arm1' $979E..$97B6, 'arm2' $9790..$97B6, 'pass' $97B7..$97BF ($97C0's JR is 12 taken / 7 not), 'leave' $97C2..$97F7
($8D09's CALL included): the instruction count, the T sum, the contended accesses, the CRC-32 of 'PC:T:k,k;' over every
instruction -- what the engine's program must be, instruction for instruction.

THE RUNS.  From the $9765 state, saved once: (key, press boundary, held frames, phase).  The key is pressed at the
press boundary and released (every key up) `held` boundaries later; the phase moves the clock so $9765 falls there
(None: the machine's own).  Each samples at every frame boundary as loadpath does (the instruction in progress
finished, the interrupt accepted, none of the ISR run) until $97F8 on the main line: the ring iterations begun, the
release passes begun ($97B7), the CRC-32 of the attributes and of the bitmap less MASK, the cut (the PC the interrupt
was taken after).  Marks [boundary, phase] at the arm, every $97B7, every $97C0 (the test's JR), $97C2 and $97F8; every
ISR's wall T; at $97F8 the bytes the exit wrote ($FED3, $FD87, $FD91, $FDDA, $FDE4, $9A0E, the players' $5B..$60).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/titleexit.py [capture|verify]  -> build/titleexit_fixture.json
"""
import sys, os, json, zlib, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctrlmenu import Fail, GUARD
from harness import PC, T, IFF, SP
from keyprobe import KEYMAP, keymask
import loadpath as lp
import revealcont as RC
import painttime as PTM

FIXTURE = 'build/titleexit_fixture.json'
FD = 69888
# (key, press boundary, held boundaries, phase of $9765 or None)
RUNS = [('1', 3, 1, None), ('2', 3, 1, None), ('1', 2, 3, None), ('1', 4, 5, None), ('2', 5, 8, None),
        ('1', 3, 2, 3), ('2', 2, 4, 14400), ('1', 5, 3, 30001), ('2', 3, 6, 50000), ('1', 2, 7, 68000),
        ('1', 6, 1, 20000), ('2', 4, 2, 41000), ('1', 3, 9, 8200), ('2', 2, 11, 60000), ('1', 7, 4, 57340),
        ('2', 3, 3, 26000)]
PLAYERS = [0xFD80 + d for d in range(0x5B, 0x61)] + [0xFD8A + d for d in range(0x5B, 0x61)]
WROTE = [0xFED3, 0xFD87, 0xFD91, 0xFDDA, 0xFDE4, 0x9A0E] + PLAYERS


def to_9765():
    """painttime's world at $970F, then the machine's paint to $9765: the harness there, MASK, the ISR before"""
    h, m, r, last_isr = PTM.to_970f(lp.SCRIPTS['kbd_sinclair'])
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    mask, isr = set(), None
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            last_isr = r[T] - isr[2]
            isr = None
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if isr is None:
            if pc == 0x9765:
                return h, m, r, last_isr, mask
            if pc in (0x8052, 0x8065, 0x8067):
                mask.add(r[6] << 8 | r[7])
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0 = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b, s, t0)


def stream(h, stop):
    """(h is spent) the plain stream from where h stands to `stop`: count, T, accesses, CRC-32 of 'PC:T:k,k;'"""
    log = []
    sim = RC.sim_of(h, log)
    r, mem = sim.registers, sim.memory
    s, n0, tsum, nacc = [], 0, 0, 0
    while r[PC] != stop:
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


def run(h, m, r, mask, key, kp, held, phase=None, upto=None):
    """from $9765: the key down at boundary kp, every key up at kp + held; to $97F8 (or to `upto`, a PC, for the
       programs' seeds: returns there with no sampling)"""
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    if phase is not None:
        r[T] += (phase - r[T] % fd) % fd
    p0 = r[T] % fd
    nb = (r[T] // fd + 1) * fd
    h.ports.release_all()
    iters, passes, rows, isrs, isr, cut, k = 0, 0, [], [], None, None, 0
    marks = []

    def bitmap():
        b = bytearray(m[0x4000:0x5800])
        for a in mask:
            b[a - 0x4000] = 0
        return zlib.crc32(bytes(b))
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            isrs.append(r[T] - isr[2])
            isr = None
        if r[T] >= nb:
            k += 1
            rows.append([iters, passes, zlib.crc32(bytes(m[0x5800:0x5B00])), bitmap(), cut])
            cut = None
            nb += fd
            if k == kp:
                h.ports.press(KEYMAP[key][0], keymask(KEYMAP[key][1]))
            if k == kp + held:
                h.ports.release_all()
            if k > 80:
                raise Fail('no $97F8 within 80 frames')
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if isr is None:
            if upto is not None and pc == upto:
                return h
            if pc == 0x9768:
                iters += 1
            if pc == 0x97B7:
                passes += 1
            if pc in (0x979E, 0x9790, 0x97B7, 0x97C0, 0x97C2, 0x97F8):
                marks.append(['%04X' % pc, k, r[T] % fd])
            if pc == 0x97F8:
                wrote = [m[a] for a in WROTE]
                break
        assert mem[pc] != 0x76, 'a HALT at $%04X' % pc
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0 = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert isr is None, 'an interrupt inside the ISR'
                isr = (b, s, t0)
                cut = pc
    return {'phase': p0, 'rows': rows, 'isrs': isrs, 'marks': marks, 'wrote': wrote}


def programs():
    out = {}
    for key, seg, (start, stop) in (('1', 'arm1', (0x979E, 0x97B7)), ('2', 'arm2', (0x9790, 0x97B7)),
                                    ('1', 'pass', (0x97B7, 0x97C0)), ('1', 'leave', (0x97C2, 0x97F8))):
        h, m, r, _, mask = to_9765()
        run(h, m, r, mask, key, 1, 1, upto=start)
        h.ports.release_all()
        out[seg] = stream(h, stop)
    return out


def capture():
    h, m, r, last_isr, mask = to_9765()
    fd = h.frame_duration
    st = h.save_state()
    bm = bytearray(m[0x4000:0x5800])
    for a in mask:
        bm[a - 0x4000] = 0
    at = {'phase': r[T] % fd, 'bitmap_b64': base64.b64encode(bytes(bm)).decode(),
          'attr_b64': base64.b64encode(bytes(m[0x5800:0x5B00])).decode(),
          'mask_b64': base64.b64encode(bytes(b for a in sorted(mask) for b in (a >> 8, a & 0xFF))).decode(),
          'prng': m[0xFE86] | m[0xFE87] << 8, 'fed3': m[0xFED3], 'ctr': [m[0x8DBD], m[0x8DBE]],
          'gates': [m[0xFEC4], m[0xFEC5]], 'isr_before': last_isr}
    progs = programs()
    runs = {}
    for key, kp, held, ph in RUNS:
        h.load_state(st)
        runs['%s_%d_%d_%s' % (key, kp, held, 'n' if ph is None else ph)] = run(h, m, r, mask, key, kp, held, phase=ph)
    out = {'meta': {'tool': 'tools/titleexit.py', 'no_rom_bytes': True,
                    'note': 'the display at $9765 with the strings\' cells zeroed (the glyphs are the ROM\'s), game-RAM '
                            'bytes, counts, T, CRC-32s; the world is loadpath kbd_sinclair'},
           'at_9765': at, 'programs': progs, 'wrote_at': WROTE, 'runs': runs}
    print('programs', progs)
    for name, d in runs.items():
        last = d['marks'][-1]
        print('%-14s phase %5d  passes %d  arm %s  97F8 %s  isrs %s' % (
            name, d['phase'], d['rows'][-1][1] if d['rows'] else 0, d['marks'][0], last, sorted(set(d['isrs']))))
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
