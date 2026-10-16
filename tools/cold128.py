"""M10.2a: THE 128K COLD START'S ACCESS PROGRAM -- $F5CC -> $8CCA on the M10 machine (the 48K harness with the paging
port and the AY, Harness(paging=$10), the 128K load's 14 bytes laid: tools/ay128flow.py's machine), the probe's answer
$80 in A: LD HL,$F5D2 / JP $7274 -> JP $8CC3: DI / LD SP,$96DD / CALL $95F3 -- the cold start with interrupts OFF, its
$9698 JR z taken over the three RET patches, $96B0 CP $C9 / RET z NOT taken, and THE LEG:

    $96B3  LD DE,$4000 / LD BC,$0F14 / LDIR            the tape's $E6A8..$F5BB through the display file (HL runs on from
                                                       $96A5's relocation, $E6A8)
    $96BB  LD BC,$7FFD / LD A,($9AE7) / OR 1 / $96C3 OUT (C),A      bank 1 paged in ($11)
    $96C5  LD HL,$4000 / LD DE,$C350 / LD BC,$0F14 / LDIR           ...into bank 1 at $C350..$D263
    $96D0  ... $96D6 OUT (C),A / $96D8 RET                          bank 0 back ($10), RET to $8CCA

As tools/coldstart.py does for the 48K stretch (PA4c): the plain run (no contention) is ONE sequence -- its T, and every
contended access as its plain offset from $F5CC (SkoolKit's contend() hook with its window forced open: the display
writes of the first LDIR and their five internal cycles, the second LDIR's display reads, and the four 1-T I/O cycles of
each OUT ($7FFD) -- port $7FFD's high byte is in $40..$7F, low bit set: C:1 x 4 -- all of them at $4000..$7FFF).  The
engine replays it from the phase the stretch begins at, each access waiting the ULA's delay at its wall phase.  Bank 1
and the AY are NOT contended on this machine (they are on a 128K: DECLARED, M10-PLAN 1.7).

ASSERTED: one program (count and SHA-1) from three worlds at $F5CC -- the real load as the flow oracle drives it (p1's
control select, the probe run and forced to $80 at $FAE1: phase 1,051), the page's skip at its natural phase (A := $80 at
$F5C9: phase 52,024), and loadspine's p4p3 made the M10 machine and skipped; the replay equals the machine's T at 64
phases, 16 midpoints, 400 random phases and each world's own; bank 1 after the leg is the asset's (build/ay_engine.json:
the bytes at $C350, zero elsewhere) and the display's first 3,860 bytes are the tape's $E6A8..; the leg's marks (the
first T of $96B3, of each OUT, of the RET) as plain offsets.

Shipped as 'lz' (r1tail's byte LZ77 of the LEB128 steps), as BB_SPINE.COLD.  Offsets, T, phases and digests only -- no
ROM byte, no tape byte (the bank and the display are checked by SHA-1 against the shipped asset).

AND THE 128K LOAD'S REPPER ('repper'): the ROM's KEYBOARD reads the repeat period from $5C0A, which the 128K load leaves 2
(the 48K load's 5: BB_MENU.REPPER).  tools/ctrlmenu.py's 24 key histories (its phase 'history': a hold, the shifts let go,
releases of 0..6 scans, freezes, the gaps, three keys, the 3,000-scan random walk) re-run on its title world with $5C0A :=
the 128K load's value -- the M10 machine's front end (the 48K ROM) -- each scan's emission, the filter's verdict and both
sets, in ctrlmenu's row form.  The port's front end under m128 is gated on them (bb.test's H block).

AND AN OUT ($7FFD)'S I/O WAITS ('io7ffd'): the request's $8E1A OUT (C),A with BC = $7FFD run alone on the M10 machine at
every phase of two contended lines and the borders around them, and at 40 random phases: [phase, T] -- 12 plus the waits
of its I/O cycle (port $7FFD: the high byte in $40..$7F and the low bit set, so C:1 four times from 8 T in).  The phases
where the fourth wait is not zero are counted (bbIo7ffd's every term is held to the machine).

Usage:  python tools/cold128.py [capture|verify|emit]  -> build/cold128_fixture.json  (emit: the JS data line)
"""
import sys, os, json, base64, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import run_to, GUARD, Fail
from harness import PC, T, A as RA, B as RB, C as RC
from skoolkit.cmiosimulator import DELAYS_48K
import loadspine as ls
import ay128flow as af
from coldstart import digest, replay
from r1tail import lz, unlz, leb

FIXTURE = 'build/cold128_fixture.json'
FD = 69888
START, END = 0xF5CC, 0x8CCA
MARKS = {0x96B3: 'leg', 0x96C3: 'out11', 0x96C5: 'ldir2', 0x96D6: 'out10', 0x96D8: 'ret'}
ASSET = 'build/ay_engine.json'


def run(h, st, ph=None, rec=None, marks=None):
    """$F5CC -> $8CCA from the saved state (at the phase given, or its own), interrupts off: (T, D).  `marks`: the first
       T of each MARKS pc as its PLAIN offset from $F5CC"""
    r, sim = h.sim.registers, h.sim
    h.load_state(st)
    if ph is not None:
        r[T] = (r[T] // FD) * FD + ph
    if r[PC] != START or r[RA] != 0x80:
        raise Fail('the state is not at $F5CC with A = $80')
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
        if marks is None:
            h.run_until({END} | GUARD, limit=10 ** 6, interrupts=False, stride=1)
        else:                                           # one instruction at a time, each mark at its first arrival
            mem, ops = h.memobj.m, sim.opcodes
            for _ in range(10 ** 6):
                pc = r[PC]
                if pc == END or pc in GUARD:
                    break
                if pc in MARKS and MARKS[pc] not in marks:
                    marks[MARKS[pc]] = r[T] - t0 - D[0]
                ops[mem[pc]]()
    finally:
        sim.contend = oc
    if r[PC] != END:
        raise Fail('$8CCA not reached (PC $%04X)' % r[PC])
    return r[T] - t0, D[0]


def flow_state(skip):
    """the M10 machine at $F5CC on the real load's control select (p1's), the probe run (forced at $FAE1) or skipped"""
    h, m, r = af.machine()
    f = af.Flow(h, keyf=af.script_keyf(af.CTRL + [(1000, [])]), skip=skip)
    f.stop_pc = START
    f.run(400)
    if r[PC] != START or r[RA] != 0x80:
        raise Fail('$F5CC with A = $80 not reached (skip %s)' % skip)
    return h, h.save_state(), f.frame, r[T] % FD


def spine_state(path):
    """loadspine's world made the M10 machine (the paging port, the 14 bytes), the CLS run, the probe skipped: A := $80"""
    h, m, r = ls.at(path)
    h.enable_paging(0x10)
    for a, v in af.load128_bytes().items():
        m[a] = v
    cm.keys(h, [])
    run_to(h, (0xF5C9,), True, limit=10 ** 8)
    r[RA], r[PC] = 0x80, START
    return h, h.save_state(), r[T] % FD


def repper():
    """ctrlmenu's key histories on its title world with $5C0A := the 128K load's REPPER: {name: {seq, rows}}"""
    rp = af.load128_bytes()[0x5C0A]
    if rp != 2:
        raise Fail("the 128K load's REPPER is %d, not 2" % rp)
    if not cm.MAIN:
        cm.build_main('title')
    out = {}
    for name, seq in cm.histories().items():
        h, m, r = cm.world('title')
        cm.free_sets(m)
        m[0x5C0A] = rp
        rows = []
        for combo in seq:
            v, t = cm.scan(h, combo)
            rows.append(cm.hist_row(v, cm.sets_of(m)))
        out[name] = {'seq': ['+'.join(c) for c in seq], 'rows': rows}
    em = [i for i, row in enumerate(out['hold']['rows']) if row[0] == '1']
    print('REPPER %d: hold emits at %s; walk %d emissions' % (rp, em[:8], sum(1 for x in out['walk']['rows'] if x[0] == '1')))
    return out


def io7ffd():
    """OUT (C),A at $8E1A with BC = $7FFD, A = $11 on the M10 machine, alone, at each phase: [[phase, T], ...]"""
    h, m, r = af.machine()
    st = h.save_state()
    line = 14335 + 100 * 224
    phs = sorted(set(list(range(14335 - 24, 14335 + 2 * 224 + 8)) + list(range(line - 8, line + 232)) +
                     random.Random(0x7FFD).sample(range(FD), 40) + [0]))
    out = []
    for ph in phs:
        h.load_state(st)
        r[PC], r[RB], r[RC], r[RA] = 0x8E1A, 0x7F, 0xFD, 0x11
        if m[0x8E1A] != 0xED or m[0x8E1B] != 0x79:
            raise Fail('$8E1A is not OUT (C),A')
        r[T] = (r[T] // FD + 1) * FD + ph
        t0 = r[T]
        h.sim.opcodes[m[0x8E1A]]()
        if r[PC] != 0x8E1C:
            raise Fail('the OUT did not run alone')
        out.append([ph, r[T] - t0])
    def waits(t, n):                                  # n 1-T I/O checks from 8 T in, each waiting the ULA
        p, d = t + 8, 0
        for _ in range(n):
            w = DELAYS_48K[p % FD]
            d += w
            p += w + 1
        return d
    if any(t != 12 + waits(ph, 4) for ph, t in out):
        raise Fail('an OUT ($7FFD) is not 12 T plus four 1-T I/O checks')
    w4 = sum(1 for ph, t in out if waits(ph, 4) != waits(ph, 3))
    print('OUT ($7FFD): %d phases, %d contended, T %d..%d, the fourth check waits at %d' % (
        len(out), sum(1 for _, t in out if t > 12), min(t for _, t in out), max(t for _, t in out), w4))
    return out


def capture():
    sha = lambda b: hashlib.sha1(bytes(b)).hexdigest()
    asset = json.load(open(ASSET, encoding='utf-8'))
    eng = base64.b64decode(asset['b64'])
    want_bank = bytearray(0x4000)
    want_bank[asset['at'] - 0xC000:asset['at'] - 0xC000 + len(eng)] = eng
    h, st, frame, rph = flow_state(False)
    prog, marks = [], {}
    t, d = run(h, st, None, prog, marks)
    plain = t - d
    g = digest(prog)
    bank = h.paging.bank(1)
    if sha(bank) != sha(want_bank) or sha(bank) != asset['bank1_sha1']:
        raise Fail('bank 1 after the leg is not the asset\'s')
    if bytes(h.memobj.m[0x4000:0x4000 + len(eng)]) != eng:
        raise Fail('the display file does not hold the tape\'s $E6A8.. after the leg')
    if h.paging.cur != 0 or [x[2] for x in h.paging.p7ffd[-2:]] != [0x11, 0x10]:
        raise Fail('the leg did not page bank 1 in ($11) and back ($10)')
    if any(h.memobj.m[a] == 0xC9 for a in (0x8DC4, 0x8E05, 0x8E0A)):
        raise Fail('a hook was RET-patched on the 128K leg')
    worlds = {'real': [frame, rph, t]}
    checked = 0
    phs = [k * ls.STEP for k in range(64)] + [k * ls.STEP + ls.STEP // 2 for k in range(0, 64, 4)] + \
        random.Random(0x96B3).sample(range(FD), 400)
    for ph in phs:
        p2 = [] if ph % ls.STEP == 0 and ph // ls.STEP % 16 == 0 else None
        t2, d2 = run(h, st, ph, p2)
        if t2 - d2 != plain or (p2 is not None and digest(p2) != g):
            raise Fail('phase %d: a different plain run (%d) or program' % (ph, t2 - d2))
        if replay(prog, plain, ph) != t2:
            raise Fail('phase %d: the replay gives %d, the machine %d' % (ph, replay(prog, plain, ph), t2))
        checked += 1
    hs, sts, fs, phs_ = flow_state(True)
    ps = []
    ts_, ds = run(hs, sts, None, ps)
    if digest(ps) != g or ts_ - ds != plain or replay(prog, plain, phs_) != ts_:
        raise Fail('the skip: not the same program, or the replay is not its T')
    worlds['skip'] = [fs, phs_, ts_]
    h3, st3, ph3 = spine_state('p4p3')
    p3 = []
    t3, d3 = run(h3, st3, None, p3)
    if digest(p3) != g or t3 - d3 != plain or replay(prog, plain, ph3) != t3:
        raise Fail('p4p3: not the same program, or the replay is not its T')
    worlds['p4p3'] = [None, ph3, t3]
    steps = bytearray()
    last = 0
    for o in prog:
        steps += leb(o - last)
        last = o
    z = lz(bytes(steps))
    assert unlz(z) == bytes(steps)
    print('the 128K cold start: plain %d T, %d accesses (%s), replay exact at %d phases + the skip + p4p3; the real '
          'load frame %d phase %d: %d T; marks %s; lz %d bytes' % (plain, len(prog), g, checked, frame, rph, t, marks,
                                                                 len(z)))
    return {'meta': {'tool': 'tools/cold128.py', 'no_rom_bytes': True,
                     'note': 'the 128K cold start $F5CC -> $8CCA on the M10 machine: plain T, its contended accesses\' '
                             'plain offsets (count, SHA-1, LEB128 steps packed by a byte LZ77), the leg\'s marks (plain '
                             'offsets from $F5CC), three worlds [frame, phase, T]'},
            'plain': plain, 'n_acc': len(prog), 'digest': g, 'checked': checked, 'marks': marks, 'worlds': worlds,
            'bank1_sha1': sha(bank), 'samples': [[ph, replay(prog, plain, ph)] for ph in phs[80:120]],
            'repper': repper(), 'io7ffd': io7ffd(),
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
        d = json.load(open(FIXTURE, encoding='utf-8'))
        print("  COLD128: { PLAIN: %d, N: %d, LZ: '%s' }," % (d['plain'], d['n_acc'], d['lz']))
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
