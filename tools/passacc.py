"""M7.114a (measurement) -- THE IN-PLAY PASS ON THE FRAME CLOCK: every main-loop pass's ACCESS PROGRAM, on the real load.

The port charged a pass its plain T stretched by round1_48's contended means (BB_PASS_K) plus a flat 78 T (BB_PASS_REST),
the pass ATOMIC (the frame's ISR after it).  This oracle measures what the machine does instead, on the REAL LOAD -- the
page's own drive: boot.pkl's $F5BC (the tap2sna snapshot of the real Bleepload loader), the control select, the title
and round 1, keys at each ISR's end (the engine's convention; scratchpad/world's machisr drive, embedded here):

  pass     $8D0C at the loop's SP to the next; its WALL PHASE (T mod 69,888 at $8D0C) and its PLAIN length (T less
           the ISRs' T and the contention delays)
  program  every CONTENDED access the main line makes in it ($4000..$7FFF, the ULA port's I/O cycle as SkoolKit's
           0x4000 pseudo-address): its plain offset from $8D0C, its T into its instruction, its delay.  The
           simulator's contention window is opened to the whole frame so an access in the border is listed (delay 0)
  isr      every ISR (label = the boundary it was taken at), its T from the acceptance to the return
  gates    (M7.114b) ($FEC5) as each ISR in the window finds it at its acceptance -- 0 when the point fell inside
           $93DC's dark window ($93E1 stores 0, $93F9 stores 1, 62 T later on the request-0 path)

ASSERTED: each pass's contended T is its program replayed from its phase with the ISRs' T put in at their points
(an access is the ISR's or after it iff its instruction starts at or past the point -- the machine accepts at an
instruction's end) -- the fixture is the machine's, and the replay rule is the engine's (passWait / passTailWait).

Also recorded: the bytes the port reads that the tape leaves to play (`tape_ops`, the machine's values at the first
$8D0C of play, each ASSERTED equal to build/image_tape.bin -- bleepload's rebuild, NOT mkimage's build/image.bin,
TRAPS #300).  No ROM byte: offsets, T, phases, digests and game-RAM bytes only.

The window is frames 470 (the first pass of play) .. 759: the engine, seeded at the first pass's phase and given each
ISR's T, is the machine pass for pass there (M7.114a PA2); at 760 the worlds part (the frame-534 even ISR, M7.114b).

Usage:  python tools/passacc.py            (-> build/passacc_fixture.json, ~15 s)
        python tools/passacc.py verify     (re-measure, compare, say MATCH)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP
from skoolkit.cmiosimulator import DELAYS_48K

FIXTURE = 'build/passacc_fixture.json'
FD = 69888
FIRST, LAST = 470, 759
ISR_FROM = 380
# the real load's keys (scratchpad/world/machplay_s.py: loadpath's KEYBOARD menu drive, then play), per frame
SCRIPT = [(8, []), (2, ['1']), (12, []), (2, ['O']), (8, []), (2, ['P']), (8, []), (2, ['SPACE']), (8, []), (2, ['Q']),
          (8, []), (2, ['Y']), (16, []), (2, ['2']), (12, []), (310, []), (3, ['1']), (40, []), (20, ['P']), (6, []),
          (3, ['Q']), (20, ['O']), (4, ['SPACE']), (10, []), (30, ['P']), (2, ['Q']), (30, []), (2, ['SPACE']),
          (60, ['O']), (200, [])]
# the 52 bytes the port reads that nothing writes before play (BB_TAPE_OPS's addresses)
TAPE_OPS = [0x7ED7, 0x8680, 0x8769, 0x896D, 0x899F, 0x89A0, 0x8F3A, 0x9077, 0x9194, 0x91D0, 0x91DC, 0x91E4, 0x91F8,
            0x91F9, 0x921C, 0x921D, 0x9254, 0x9255, 0x9256, 0x9259, 0x92DE, 0x9AE9, 0x9AF5, 0x9E57, 0xA09E, 0xA194,
            0xA1AA, 0xA25D, 0xA25E, 0xA25F, 0xA260, 0xA26B, 0xA26C, 0xA2AE, 0xA85C, 0xA8C3, 0xA8FD, 0xA8FE, 0xAA00,
            0xAA06, 0xB60F, 0xB611, 0xB62D, 0xB742, 0xB796, 0xB880, 0xB9BC, 0xC001, 0xFFF7, 0xFFF8, 0xFFFA, 0xFFFB]
# M7.114e: the bytes the port reads that the load hands over and the round start READS BEFORE IT WRITES them -- so
# TAPE_OPS' rule (taken at play) cannot see them: $72F8's ADD to $73AF, the spawn's rolling +4 seed.  Taken at $F5BC
# (BB_TAPE_RMW's addresses; scratchpad/m7114e/firstread.py + handcmp.js found it: every byte the machine reads before
# writing from the hand-over to frame 760, against the engine's RAM after handDone)
BOOT_RMW = [0x73AF]


def digest(prog):
    return hashlib.sha1(''.join('%d:%d;' % (o, k) for o, k in prog).encode()).hexdigest()[:16]


def measure():
    h, m, r = world('boot')
    seq = expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    sim.t0, sim.t1 = -1, 1 << 40              # every access through contend (DELAYS_48K is 0 outside the window)
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD
    nb = (r[T] // fd + 1) * fd
    st = {'P': None, 'pc': 0, 'isr': None, 'isr_t0': 0}
    frame, in_scan, pending = 0, False, None
    passes, isrs, tape, gates = [], [], None, []
    boot_rmw = {a: m[a] for a in BOOT_RMW}
    cm.keys(h, keyf(0))
    oc = sim.contend

    def cont(t, timings):
        P = st['P']
        if P is not None and st['isr'] is None:
            tt, k = t, 0
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    d = DELAYS_48K[tt % FD]
                    P['acc'].append((st['pc'], k, tt - P['t0'] - P['D'] - P['I'], d))
                    P['D'] += d; tt += d
                tt += ts; k += ts
        return oc(t, timings)
    sim.contend = cont
    while frame <= LAST:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        isr = st['isr']
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            if in_scan: pending = keyf(isr[2])
            else: cm.keys(h, keyf(isr[2]))
            T_ = r[T] - st['isr_t0']
            if isr[2] >= ISR_FROM: isrs.append([isr[2], T_])
            P = st['P']
            if P is not None:
                P['isr'].append([st['isr_t0'] - P['t0'] - P['D'] - P['I'], T_, isr[2]])
                P['I'] += T_
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
            if P is not None:
                P['len'] = r[T] - P['t0'] - P['D'] - P['I']
                passes.append(P)
            if frame >= FIRST and tape is None:
                tape = {a: m[a] for a in TAPE_OPS}
            st['P'] = {'f': frame, 't0': r[T], 'ph': r[T] % fd, 'D': 0, 'I': 0, 'acc': [], 'isr': []} \
                if FIRST <= frame <= LAST else None
        st['pc'] = pc
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert st['isr'] is None, 'an interrupt inside the ISR'
                st['isr_t0'] = t_
                st['isr'] = (b0, s0, frame + (1 if r[T] >= nb else 0))
                if FIRST <= st['isr'][2] <= LAST + 1:
                    gates.append([st['isr'][2], m[0xFEC5]])   # M7.114b: the even gate the ISR finds
    sim.contend = oc
    return passes, isrs, tape, gates, boot_rmw


def replay(P):
    """the engine's rule: from the phase, each access waits at its wall phase; an ISR's T goes in before the first
       access whose instruction starts at or past its point"""
    D, I, j, isr = 0, 0, 0, P['isr']
    for pc, k, o, d in P['acc']:
        while j < len(isr) and o - k >= isr[j][0]:
            I += isr[j][1]; j += 1
        D += DELAYS_48K[(P['t0'] + o + D + I) % FD]
    return D


def build():
    passes, isrs, tape, gates, boot_rmw = measure()
    img = open('build/image_tape.bin', 'rb').read()
    bad = [hex(a) for a in TAPE_OPS if tape[a] != img[a]]
    assert not bad, 'the play-start bytes differ from build/image_tape.bin at ' + ' '.join(bad)
    bad = [hex(a) for a in BOOT_RMW if boot_rmw[a] != img[a]]
    assert not bad, 'the read-first bytes of the load differ from build/image_tape.bin at ' + ' '.join(bad)
    rows, sites = [], {}
    for P in passes:
        D = sum(x[3] for x in P['acc'])
        assert replay(P) == D, 'frame %d phase %d: the replay is not the machine\'s' % (P['f'], P['ph'])
        prog = [(o, k) for pc, k, o, d in P['acc']]
        for pc, k, o, d in P['acc']:
            key = '%04X:%d' % (pc, k)
            sites[key] = sites.get(key, 0) + 1
        rows.append([P['f'], P['ph'], P['len'], len(prog), D, digest(prog), [x[:2] for x in P['isr']]])
    return {'window': [FIRST, LAST], 'script': [[n, k] for n, k in SCRIPT], 'isr_from': ISR_FROM,
            'isrs': isrs, 'passes': rows, 'sites': sites, 'tape_ops': {str(a): tape[a] for a in TAPE_OPS},
            'boot_rmw': {str(a): boot_rmw[a] for a in BOOT_RMW},
            'n_passes': len(rows), 'n_acc': sum(r[3] for r in rows), 'gates': gates}


if __name__ == '__main__':
    out = build()
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        old = json.load(open(FIXTURE))
        print('MATCH' if json.loads(json.dumps(out)) == old else 'DIFFER')
    else:
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote %s: %d passes, %d accesses, %d ISRs, %d sites' % (FIXTURE, out['n_passes'], out['n_acc'],
                                                                       len(out['isrs']), len(out['sites'])))
