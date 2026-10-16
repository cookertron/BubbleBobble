"""M7.109: THE TITLE'S SPARKLE RING ON THE FRAME CLOCK -- $9768..$978F, interrupts ON, against the machine
frame by frame.

THE WORLD.  The real load: loadpath.py's kbd_sinclair drive from boot.pkl's own $F5BC, through both
control-select passes, the black screen, the probe and the hand-over, to the FIRST arrival at $9765
(the paint done, `LD HL,$5800` next).  Recorded there (game RAM and the display's attributes only --
no ROM byte): the frame phase, the attribute file, the PRNG $FE86/$FE87, $FED3, the ISR's counter
$8DBD and its gates $FEC4/$FEC5, and the T of the ISR before the arrival.

THE RUNS.  From that state, saved once:
  natural   at the machine's own phase (loadpath's arrival, both scripts agree on it)
  forced    the same state with the clock moved so $9765 falls at each of FORCED phases
  press     a key ('1' or '2') pressed at a frame boundary and held: the frame (boundaries since the
            arrival) and the phase at which the arm ($979E / $9790) is reached
Each run samples at every frame boundary, as loadpath.py does (the instruction in progress at the
boundary finished, the interrupt accepted, none of the ISR run): the ring iterations BEGUN since the
arrival ($9768 reached on the main line), the attributes' CRC-32, the PRNG; and the PC of the
instruction the interrupt was taken after (the CUT), and every ISR's wall T (acceptance to return).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/ringtime.py [capture|verify]  -> build/ringtime_fixture.json
"""
import sys, os, json, zlib, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, Fail, GUARD, expand
from harness import PC, T, IFF, SP
from keyprobe import KEYMAP, keymask
import loadpath as lp

FIXTURE = 'build/ringtime_fixture.json'
FRAMES = 30                                    # frame boundaries sampled past the arrival
FORCED = [0, 4100, 8200, 12300, 14335, 14400, 16000, 20000, 24000, 28000, 32000, 36000, 40000,
          44000, 48000, 52000, 56000, 57340, 60000, 64000, 68000]
PRESS = [('1', 5, 22702), ('2', 5, 22702), ('1', 3, 14400), ('2', 7, 30001), ('1', 2, 50000),
         ('2', 4, 3)]


def to_9765(script):
    """loadpath's drive, stopped at the first $9765 on the main line"""
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
        if pc == 0x9765 and isr is None:
            assert keyf(frame) == [], 'a key is down at $9765'
            return h, m, r, last_isr
        if mem[pc] == 0x76 and r[IFF]:
            h._fast_halt()
            continue
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0 = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b, s, t0)


def ring(h, m, r, phase=None, press=None, frames=FRAMES):
    """from $9765: `phase` moves the clock so $9765 falls there; `press` = (key, boundary k) presses
       the key at the k-th boundary and stops at the arm"""
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    if phase is not None:
        r[T] += (phase - r[T] % fd) % fd
    p0 = r[T] % fd
    nb = (r[T] // fd + 1) * fd
    h.ports.release_all()
    iters, rows, isrs, isr, cut, k, arm = 0, [], [], None, None, 0, None
    while True:
        pc = r[PC]
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            isrs.append(r[T] - isr[2])
            isr = None
        if r[T] >= nb:
            k += 1
            rows.append([iters, zlib.crc32(bytes(m[0x5800:0x5B00])), m[0xFE86] | m[0xFE87] << 8, cut])
            cut = None
            nb += fd
            if press is not None and k == press[1]:
                h.ports.press(KEYMAP[press[0]][0], keymask(KEYMAP[press[0]][1]))
            if press is None and k >= frames:
                break
            if k > 60:
                raise Fail('no arm within 60 frames')
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if isr is None:
            if pc == 0x9768:
                iters += 1
            if pc in (0x979E, 0x9790):
                arm = [k, r[T] % fd, iters, 1 if pc == 0x979E else 2]
                break
        assert mem[pc] != 0x76, 'a HALT at $%04X' % pc
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b, s, t0 = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert isr is None, 'an interrupt inside the ISR'
                isr = (b, s, t0)
                cut = pc
    return {'phase': p0, 'rows': rows, 'isrs': isrs, 'arm': arm}


def capture():
    h, m, r, last_isr = to_9765(lp.SCRIPTS['kbd_sinclair'])
    fd = h.frame_duration
    at = {'phase': r[T] % fd, 'attr_b64': base64.b64encode(bytes(m[0x5800:0x5B00])).decode(),
          'prng': m[0xFE86] | m[0xFE87] << 8, 'fed3': m[0xFED3], 'ctr': [m[0x8DBD], m[0x8DBE]],
          'gates': [m[0xFEC4], m[0xFEC5]], 'isr_before': last_isr}
    st = h.save_state()
    runs = {'natural': ring(h, m, r)}
    for p in FORCED:
        h.load_state(st)
        runs['forced_%d' % p] = ring(h, m, r, phase=p)
    for key, kb, p in PRESS:
        h.load_state(st)
        runs['press_%s_%d_%d' % (key, kb, p)] = ring(h, m, r, phase=p, press=(key, kb))
    cuts = {}
    for d in runs.values():
        for row in d['rows']:
            if row[3] is not None:
                cuts['%04X' % row[3]] = cuts.get('%04X' % row[3], 0) + 1
    out = {'meta': {'tool': 'tools/ringtime.py', 'no_rom_bytes': True,
                    'note': 'attributes, game-RAM bytes, counts, T, CRC-32s; the world is loadpath kbd_sinclair'},
           'at_9765': at, 'frames': FRAMES, 'runs': runs, 'cuts': dict(sorted(cuts.items()))}
    for name, d in runs.items():
        print('%-20s phase %5d  %s  isrs %s  arm %s' % (name, d['phase'], [x[0] for x in d['rows'][:6]],
                                                       sorted(set(d['isrs'])), d['arm']))
    print('cuts', out['cuts'])
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
