"""M7.112: THE ROUND-1 BUILD FROM THE TITLE, EXACT -- $97F8 (from $8D09's CALL, the title's exit) to the HALT at $9887,
against the machine frame by frame.

THE WORLD.  titleexit's: the real load to its first $9765, then each of its 16 runs (key, press boundary, held frames,
phase) to $97F8 on the machine.  Two more runs poke the high score ($FFE1..$FFE4) at $9765 first ('hi1' / 'hi2': a second
game's world), to show the program does not move with it.

THE PROGRAMS.  From each run's $97F8 the plain run (no contention, interrupts off) to $9887: every contended access as
(a, k) -- a its T from $97F8, k its T into its instruction -- the plain T at the marks ($7F30 the scroll's CALL, $7F4E the
repaint's CALL, $8216 its entry, $7F51 the digits' CALL, $7FC0 the HUD, $9887 the HALT) and the end.  MEASURED: one
program for one player and one for two, the same in every run (asserted: the digest of every 'a:k;' per player count).
The engine ships the repaint's accesses as its own generator (extModel('repaint'), from $8216's entry) and the rest as
DATA ('data_b64': per access k, then a's step from the access before as LEB128, the repaint's span left out).

THE RUNS.  From $97F8 on the machine (contended, interrupts on) to $9887 on the main line: every ISR [main-line T at its
acceptance, its T]; the main-line T (ISRs taken out) at each mark and at $9887; $9887's [frame after $97F8's, phase];
every display write ($4000..$5AFF) on the main line as [address, main-line T of its instruction's start] -- the count and
the SHA-1 of the 'a@t;' list sorted by (t, a) in all, and per frame (the main-line T's frame from $97F8's phase).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/r1build.py [capture|verify|emit]  -> build/r1build_fixture.json  (emit: the JS data strings)
"""
import sys, os, json, base64, hashlib, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctrlmenu import Fail, GUARD
from harness import PC, T, IFF, SP
import titleexit as TE
import revealcont as RC
from isrcarry import DELAYS_48K

FIXTURE = 'build/r1build_fixture.json'
FD = 69888
MARKS = {0x7F30: '7F30', 0x7F4E: '7F4E', 0x8216: '8216', 0x7F51: '7F51', 0x7FC0: '7FC0', 0x7FF4: '7FF4', 0x7FF7: '7FF7',
         0x7FF9: '7FF9', 0x7FFC: '7FFC', 0x9887: '9887'}
CALL = 17
HI = [0x01, 0x23, 0x45, 0x67]          # $FFE1..$FFE4: a high score of 67,452,301 (BCD, the MSB at $FFE4)
RUNS = [(k, kp, held, ph, None) for k, kp, held, ph in TE.RUNS] + [('1', 3, 1, None, 'hi1'), ('2', 3, 1, None, 'hi2')]


def name_of(key, kp, held, ph, tag):
    return tag or '%s_%d_%d_%s' % (key, kp, held, 'n' if ph is None else ph)


def plain(h):
    """(h at $97F8) the plain run to $9887: accesses [(a, k, pc)], marks {name: plain T}, end, the glyph cells (every
    address $8052 stores to -- $802E's text -- and the display cell under every shadow byte $7F80 stores to -- the round
    number, which the repaint copies up: the ROM's glyphs); h's simulator restored"""
    sim0, mem0 = h.sim, h.memobj
    st = h.save_state()
    log = []
    sim = RC.sim_of(h, log)
    r, mem = sim.registers, sim.memory
    t0, n0, acc, marks, glyph = r[T], 0, [], {}, set()
    try:
        while True:
            p, ts = r[PC], r[T]
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            if p in MARKS and MARKS[p] not in marks:
                marks[MARKS[p]] = ts - t0
                if p == 0x9887:
                    break
            if p == 0x8052:
                glyph.add(r[6] << 8 | r[7])
            elif 0x7F80 <= p < 0x7FC0 and mem[p] == 0x77 and 0xE000 <= (r[6] << 8 | r[7]) < 0xF800:
                glyph.add((r[6] << 8 | r[7]) - 0xA000)    # $7F80's digit rows into the shadow: the repaint's copy
            sim.opcodes[mem[p]]()
            for x in log[n0:]:
                acc.append((x - t0, x - ts, p))
            n0 = len(log)
            if r[T] - t0 > 2 * 10 ** 6:
                raise Fail('no $9887 in the plain run')
    finally:
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
        h.load_state(st)
    return acc, marks, marks['9887'], glyph


def rep_span(acc, r0):
    """the repaint's LDIR accesses: from $8216's entry to the last access made by code at $82xx"""
    r1 = max(a for a, _, p in acc if p >> 8 == 0x82) + 1
    inside = [p for a, _, p in acc if r0 <= a < r1]
    assert all(p >> 8 == 0x82 for p in inside), 'an access in the repaint span from outside $82xx'
    return r1, len(inside)


def machine(h, mask):
    """(h at $97F8) the machine to $9887 on the main line: ISRs, marks, the end, the display writes; at every frame
    boundary (titleexit's sampling: the instruction in progress finished, the interrupt accepted, none of the ISR run)
    and at $9888 (the ISR that ends $9887's HALT run: the first with a gate open, which draws the players -- the engine's
    step() ends with it) the CRC-32 of the attributes and of the bitmap less `mask`"""
    sim0, mem0 = h.sim, h.memobj
    st = h.save_state()
    wm = RC.WriteMem(mem0.m)
    sim = RC.sim_of(h, None, wm)
    sim.set_tracer(h.ports)
    r, mem = sim.registers, sim.memory
    fd, ia = h.frame_duration, h.int_active
    t0 = r[T]
    f0, ph = t0 // fd, t0 % fd
    odd = (mem[0x8DBD] + 1) & 1
    wm.regs = r
    isr, isrs, walls, marks, wr, rows, end = None, [], 0, {}, [], [], None
    m = mem0.m
    nb = (f0 + 1) * fd

    def row():
        b = bytearray(m[0x4000:0x5800])
        for a in mask:
            b[a - 0x4000] = 0
        return [zlib.crc32(bytes(m[0x5800:0x5B00])), zlib.crc32(bytes(b))]
    try:
        while True:
            p = r[PC]
            if r[T] >= nb:
                if end is None:                       # past $9887 the last row is taken at $9888
                    rows.append(row())
                nb += fd
            if isr is not None and p == isr[0] and r[SP] == isr[1]:
                if isr[4]:                            # not the one that ends the HALT
                    isrs.append([isr[3], r[T] - isr[2]])
                walls += r[T] - isr[2]
                isr = None
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            main = isr is None
            if main:
                mt = r[T] - t0 - walls
                if p in MARKS and MARKS[p] not in marks:
                    marks[MARKS[p]] = mt
                    if p == 0x9887:
                        end = [r[T] // fd - f0, r[T] % fd]
                if p == 0x9888:                       # the ISR that ends the HALT has run: the last row
                    rows.append(row())
                    break
                wm.tins[0] = (mt, r[T] // fd - f0)
            sim.opcodes[mem[p]]()
            if main and end is None:
                for a, (t, f) in wm.wr:
                    if 0x4000 <= a < 0x5B00:
                        wr.append((t, a, f))
            del wm.wr[:]
            if r[IFF] and r[T] % fd < ia:
                b, s, ta = r[PC], r[SP], r[T]
                if sim.accept_interrupt(r, mem, p):
                    assert isr is None, 'an interrupt inside the ISR'
                    isr = (b, s, ta, ta - t0 - walls, end is None)
            if r[T] - t0 > 3 * 10 ** 6:
                raise Fail('no $9887 on the machine')
    finally:
        wm.regs = None
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
        h.load_state(st)
    wr.sort()
    frames = {}
    for t, a, f in wr:
        frames.setdefault(str(f), []).append('%d@%d;' % (a, t))
    sha = lambda xs: hashlib.sha1(''.join(xs).encode('ascii')).hexdigest()[:16]
    return {'phase': ph, 'odd': odd, 'isrs': isrs, 'marks': marks, 'end': end, 'rows': rows,
            'writes': [len(wr), sha('%d@%d;' % (a, t) for t, a, _ in wr)],
            'wframes': {f: [len(x), sha(x)] for f, x in frames.items()}}


def awards(pm):
    """the two awards' T ($80FA's entry to its return), from the plain marks"""
    return [pm['7FF7'] - pm['7FF4'] - CALL, pm['7FFC'] - pm['7FF9'] - CALL]


def normal(acc, pm):
    """the program with the awards' T taken out -- what moves with the world (the high score) is their T alone;
    X1 / X2 the normalized T of the returns ($7FF7 / $7FFC): an access at or past X shifts by that award's T"""
    a1, a2 = awards(pm)
    r1, r2 = pm['7FF7'], pm['7FFC']
    assert not any(pm['7FF4'] + CALL <= a < r1 or pm['7FF9'] + CALL <= a < r2 for a, _, _ in acc), 'an access inside an award'
    out = [(a - (a1 if a >= r1 else 0) - (a2 if a >= r2 else 0), k, p) for a, k, p in acc]
    return out, r1 - a1, r2 - a1 - a2


def replay(acc, end, phase, odd):
    """the main-line T of the plain `end` from the access program at $97F8's phase, each ISR's T (488 odd / 493 even,
    gate-closed) added at the first instruction that starts past its boundary: [main-line end, ISRs before it]"""
    D = I = n = 0
    nb, o = FD - phase, odd
    for a, k, _ in acc:
        while a - k + D + I >= nb:
            I += 488 if o else 493
            nb += FD; o ^= 1; n += 1
        D += DELAYS_48K[(phase + a + D + I) % FD]
    while end + D + I >= nb:
        I += 488 if o else 493
        nb += FD; o ^= 1; n += 1
    return [end + D, n]


def digest(acc):
    return hashlib.sha1(''.join('%d:%d;' % (a, k) for a, k, _ in acc).encode('ascii')).hexdigest()[:16]


def encode(acc, r0, r1):
    """the accesses outside the repaint's span [r0, r1): per access k, then a's step from the last as LEB128"""
    out, last = bytearray(), 0
    for a, k, _ in acc:
        if r0 <= a < r1:
            continue
        assert 0 <= k < 128 and a >= last
        out.append(k)
        d = a - last
        while True:
            b = d & 0x7F
            d >>= 7
            out.append(b | (0x80 if d else 0))
            if not d:
                break
        last = a
    return base64.b64encode(bytes(out)).decode()


def capture():
    h, m, r, last_isr, mask = TE.to_9765()
    st = h.save_state()
    progs, runs = {}, {}
    for key, kp, held, ph, tag in RUNS:
        h.load_state(st)
        if tag:
            for i, v in enumerate(HI):
                m[0xFFE1 + i] = v
        TE.run(h, m, r, mask, key, kp, held, phase=ph)
        acc, pm, pend, glyph = plain(h)
        d = machine(h, glyph)
        d['mask_n'] = len(glyph)
        name = name_of(key, kp, held, ph, tag)
        aw = awards(pm)
        nacc, x1, x2 = normal(acc, pm)
        nend = pend - sum(aw)
        g = digest(nacc)
        p = progs.get(key)
        if p is None:
            r0 = pm['8216']
            r1, n_rep = rep_span(acc, r0)             # the repaint's tail JPs to $7F80: contended code, data
            progs[key] = {'n_acc': len(acc), 'digest': g, 'marks': pm, 'awards': aw, 'x': [x1, x2], 'end_n': nend,
                          'end': pend, 'rep': [r0, r1, n_rep], 'data_b64': encode(nacc, r0, r1),
                          'data_n': len(acc) - n_rep,
                          'mask_b64': base64.b64encode(bytes(b for x in sorted(glyph) for b in (x >> 8, x & 0xFF))).decode()}
        elif p['digest'] != g or p['end_n'] != nend or p['x'] != [x1, x2] or                 base64.b64decode(p['mask_b64']) != bytes(b for x in sorted(glyph) for b in (x >> 8, x & 0xFF)):
            raise Fail('%s: the plain program is not %s players\' first (%s / %s)' % (name, key, g, p['digest']))
        d['players'] = int(key)
        d['awards'] = aw
        d['plain_end'] = pend
        d['digest_raw'] = digest(acc)
        rp = replay(acc, pend, d['phase'], d['odd'])
        if rp != [d['marks']['9887'], len(d['isrs'])]:
            raise Fail('%s: the replay gives %s, the machine %s' % (name, rp, [d['marks']['9887'], len(d['isrs'])]))
        runs[name] = d
        print('%-12s phase %5d odd %d  isrs %s  end %s  main %d  writes %d  awards %s  frames %s' % (
            name, d['phase'], d['odd'], sorted(set(w for _, w in d['isrs'])), d['end'], d['marks']['9887'], d['writes'][0],
            aw, sorted(map(int, d['wframes']))),
            flush=True)
    for k, p in progs.items():
        print('players %s: %d accesses, %d in the repaint, end %d, marks %s, data %d bytes' % (
            k, p['n_acc'], p['rep'][2], p['end'], p['marks'], len(p['data_b64'])))
    return {'meta': {'tool': 'tools/r1build.py', 'no_rom_bytes': True,
                     'note': 'T, counts and digests of the round-1 build from the title (titleexit\'s world); '
                             'the data strings are access timings, not tape bytes'},
            'hi': HI, 'programs': progs, 'runs': runs}


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
        P = json.load(open(FIXTURE, encoding='utf-8'))['programs']
        for k in sorted(P):
            print("  %s: '%s'," % (k, P[k]['data_b64']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
