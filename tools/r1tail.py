"""M7.113: THE ROUND-1 TAIL AND BANNER FROM THE TITLE, EXACT -- $9888 (after the ISR that ends $9887's HALT) to $8D0C
(the RET of $8D09's CALL $97F8), against the machine frame by frame.

THE WORLD.  titleexit's: the real load to its first $9765, then each of its 16 runs (key, press boundary, held frames,
phase) to $97F8 and on through the round-1 build (r1build's span) to $9888 on the machine.

THE HALT.  $9887's HALT starts at phase p (r1build's 'end'); the HALT runs as 4-T steps, so the interrupt that ends it
is taken at the first step end at or past the boundary: p % 4 T into the frame (FD is a multiple of 4).  Recorded per
run: p, that ISR's T and its own contention delay, and $9888's phase.

THE PROGRAM.  From $9888 the plain run (no contention, interrupts off) to $8D0C: every contended access as (a, k) -- a
its T from $9888, k its T into its instruction -- the marks, the end, and every write the engine holds on its clock:
the display ($4000..$5AFF) and the two gate stores ($98AF $FEC5, $98B2 $9F62) as [address, plain T of the instruction's
start].  MEASURED: one program for every run, one player or two (asserted: the digest of every 'a:k;').  The engine
ships it as 'data_lz' (per access k, then a's step as LEB128, packed by a byte LZ77: tools/r1tail.py lz()).

THE RUNS.  From $9888 on the machine (contended, interrupts on, both gates open from $98AF) to $8D0C on the main line:
every ISR [main-line T at its acceptance, its T, its own contention delay, its acceptance phase]; the main-line T at each mark and $8D0C;
$8D0C's [frame after $9888's, phase]; every held write on the main line as [address, main-line T] (count + SHA-1 of
'a@t;' sorted by (t, a)); at the END of every ISR (where the engine's step() ends) the CRC-32 of the attributes and of
the bitmap less the ROM font's cells: the banner's (every address $8052 stores to) and the build's (r1build's mask: the
HUD text and the round number).  The tool asserts that the
program replayed from $9888's phase with the machine's ISR T gives every mark, the end and the ISR count.

THE INSTRUCTION GRID (R1Tf).  The plain run's every instruction's T, in order (asserted one sequence for every run, no EI
and no HALT in it): the engine finds the instruction in progress at each interrupt point from it, and the ISR's own
contention is replayed from that instruction's end ('ins_lz', the same LZ77 over one byte per instruction).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/r1tail.py [capture|verify|emit]  -> build/r1tail_fixture.json  (emit: the JS data string)
"""
import sys, os, json, base64, hashlib, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctrlmenu import Fail, GUARD
from harness import PC, T, IFF, SP
import titleexit as TE
import revealcont as RC
from isrcarry import DELAYS_48K

FIXTURE = 'build/r1tail_fixture.json'
FD = 69888
MARKS = {0x98A1: '98A1', 0x98A4: '98A4', 0x98A7: '98A7', 0x98AA: '98AA', 0x98AD: '98AD', 0x98B5: '98B5',
         0x98E4: '98E4', 0x98E7: '98E7', 0x98EA: '98EA', 0x8D0C: '8D0C'}
E9904 = 0x9904
HELD = (0xFEC5, 0x9F62)


def held(a):
    return 0x4000 <= a < 0x5B00 or a in HELD


def leb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return out


def lz(src, chain=64):
    """a byte LZ77: a token < $80 is a literal run of token + 1 bytes; $80 a copy, then LEB128 length - 4 and LEB128
    distance - 1.  Greedy, the longest match over a hash chain of 4-byte keys."""
    out, lit, heads, prev = bytearray(), bytearray(), {}, {}
    i, n = 0, len(src)

    def flush():
        while lit:
            run = lit[:128]
            out.append(len(run) - 1)
            out.extend(run)
            del lit[:128]

    def put(q):
        if q + 4 <= n:
            k = bytes(src[q:q + 4])
            prev[q] = heads.get(k)
            heads[k] = q
    while i < n:
        best, bd = 0, 0
        if i + 4 <= n:
            j, c = heads.get(bytes(src[i:i + 4])), 0
            while j is not None and c < chain:
                L = 0
                while i + L < n and src[j + L] == src[i + L]:
                    L += 1
                if L > best:
                    best, bd = L, i - j
                j, c = prev.get(j), c + 1
        if best >= 4:
            flush()
            out.append(0x80)
            out.extend(leb(best - 4))
            out.extend(leb(bd - 1))
            for q in range(i, i + best):
                put(q)
            i += best
        else:
            put(i)
            lit.append(src[i])
            i += 1
    flush()
    return bytes(out)


def unlz(s):
    out, i = bytearray(), 0

    def rd():
        nonlocal i
        v, sh = 0, 0
        while True:
            c = s[i]
            i += 1
            v |= (c & 0x7F) << sh
            sh += 7
            if not c & 0x80:
                return v
    while i < len(s):
        t = s[i]
        i += 1
        if t < 0x80:
            out.extend(s[i:i + t + 1])
            i += t + 1
        else:
            L, d = rd() + 4, rd() + 1
            for _ in range(L):
                out.append(out[-d])
    return bytes(out)


def encode(acc):
    out, last = bytearray(), 0
    for a, k, _ in acc:
        assert 0 <= k < 128 and a >= last
        out.append(k)
        out.extend(leb(a - last))
        last = a
    return bytes(out)


def digest(xs):
    return hashlib.sha1(''.join(xs).encode('ascii')).hexdigest()[:16]


def plain(h):
    """(h at $9888) the plain run to $8D0C: accesses [(a, k, pc)], marks {name: plain T}, the $9904 entries, the end,
    the held writes [(a, t)], the glyph cells; h's simulator restored"""
    sim0, mem0 = h.sim, h.memobj
    st = h.save_state()
    log = []
    wm = RC.WriteMem(mem0.m)
    sim = RC.sim_of(h, log, wm)
    wm.regs = sim.registers
    r, mem = sim.registers, sim.memory
    t0, n0, acc, marks, e9904, wr, glyph, ins = r[T], 0, [], {}, [], [], set(), []
    try:
        while True:
            p, ts = r[PC], r[T]
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            if p in MARKS and MARKS[p] not in marks:
                marks[MARKS[p]] = ts - t0
            if p == 0x8D0C:
                break
            if p == E9904:
                e9904.append(ts - t0)
            if p == 0x8052:
                glyph.add(r[6] << 8 | r[7])
            wm.tins[0] = ts - t0
            if mem[p] in (0xFB, 0x76):
                raise Fail('an EI / HALT in the tail at $%04X: the instruction-in-progress rule needs its case' % p)
            sim.opcodes[mem[p]]()
            ins.append(r[T] - ts)
            for x in log[n0:]:
                acc.append((x - t0, x - ts, p))
            n0 = len(log)
            for a, t in wm.wr:
                if held(a):
                    wr.append((a, t))
            del wm.wr[:]
            if r[T] - t0 > 5 * 10 ** 6:
                raise Fail('no $8D0C in the plain run')
    finally:
        wm.regs = None
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
        h.load_state(st)
    assert sum(ins) == ts - t0
    return acc, marks, e9904, ts - t0, wr, glyph, ins


def machine(h, stop, mask=None, rows=False):
    """(h) the machine until the main line reaches `stop`: ISRs [main T at acceptance, T, own delay], marks, the end
    [main T, frame after the start's, phase], held writes [(a, main T)], rows (at every ISR's end) -- h left at `stop`"""
    sim0, mem0 = h.sim, h.memobj
    wm = RC.WriteMem(mem0.m)
    sim = RC.sim_of(h, None, wm)
    sim.set_tracer(h.ports)
    r, mem = sim.registers, sim.memory
    ia = h.int_active
    t0 = r[T]
    f0 = t0 // FD
    wm.regs = r
    bucket = [0]
    orig = sim.contend
    isr = None

    def contend(t, timings):
        d = orig(t, timings)
        if isr is not None:
            bucket[0] += d
        return d
    sim.contend = contend
    m = mem0.m
    isrs, walls, marks, wr, rws = [], 0, {}, [], []

    def row():
        b = bytearray(m[0x4000:0x5800])
        for a in mask:
            b[a - 0x4000] = 0
        return [zlib.crc32(bytes(m[0x5800:0x5B00])), zlib.crc32(bytes(b))]
    try:
        while True:
            p = r[PC]
            if isr is not None and p == isr[0] and r[SP] == isr[1]:
                isrs.append([isr[3], r[T] - isr[2], bucket[0] - isr[4], isr[2] % FD])   # R1Tf: its acceptance phase
                walls += r[T] - isr[2]
                isr = None
                if rows:
                    rws.append(row())
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            main = isr is None
            if main:
                mt = r[T] - t0 - walls
                if p in MARKS and MARKS[p] not in marks:
                    marks[MARKS[p]] = mt
                if p == 0x9887 and 'p9887' not in marks:
                    marks['p9887'] = r[T] % FD          # the HALT's start phase
                if p == stop:
                    end = [mt, r[T] // FD - f0, r[T] % FD]
                    break
                wm.tins[0] = mt
            sim.opcodes[mem[p]]()
            if main:
                for a, t in wm.wr:
                    if held(a):
                        wr.append((a, t))
            del wm.wr[:]
            if r[IFF] and r[T] % FD < ia:
                b, s, ta = r[PC], r[SP], r[T]
                if sim.accept_interrupt(r, mem, p):
                    assert isr is None, 'an interrupt inside the ISR'
                    isr = (b, s, ta, ta - t0 - walls, bucket[0])
            if r[T] - t0 > 6 * 10 ** 6:
                raise Fail('no $%04X on the machine' % stop)
    finally:
        wm.regs = None
        sim.contend = orig
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
    sim0.registers[:] = r                             # the harness carries on from `stop` over the same RAM
    return isrs, marks, end, wr, rws


def replay(acc, end, phase, isrT):
    """the main-line T of plain T `end` from the access program at $9888's phase, ISR i's T added at the first access
    whose instruction starts at or past its boundary: [main-line end, ISRs before it]"""
    D = I = n = 0
    nb = FD - phase
    for a, k, _ in acc:
        while a - k + D + I >= nb:
            I += isrT[n]
            nb += FD
            n += 1
        D += DELAYS_48K[(phase + a + D + I) % FD]
    while end + D + I >= nb:
        I += isrT[n]
        nb += FD
        n += 1
    return [end + D, n]


def at(acc, t, phase, isrT):
    """plain T t -> main-line T (the delays of the accesses before it, the ISRs as replay())"""
    D = I = n = 0
    nb = FD - phase
    for a, k, _ in acc:
        if a >= t:
            break
        while a - k + D + I >= nb:
            I += isrT[n]
            nb += FD
            n += 1
        D += DELAYS_48K[(phase + a + D + I) % FD]
    return t + D


def capture():
    RB = json.load(open('build/r1build_fixture.json', encoding='utf-8'))
    h, m, r, last_isr, mask0 = TE.to_9765()
    st = h.save_state()
    prog, runs = None, {}
    for key, kp, held_, ph in TE.RUNS:
        h.load_state(st)
        TE.run(h, m, r, mask0, key, kp, held_, phase=ph)
        name = '%s_%d_%d_%s' % (key, kp, held_, 'n' if ph is None else ph)
        bi, bm, bend, _, _ = machine(h, 0x9888)       # $97F8 -> $9888: the HALT and the ISR that ends it
        halt = [bm['p9887'], bi[-1][1], bi[-1][2]]   # the HALT's phase, the T and own delay of the ISR ending it
        phase = r[T] % FD
        acc, pm, e9904, pend, pwr, glyph, ins = plain(h)
        gi = digest('%d;' % t for t in ins)
        mask = sorted(glyph)
        g = digest('%d:%d;' % (a, k) for a, k, _ in acc)
        wd = digest('%d@%d;' % (a, t) for a, t in sorted(pwr, key=lambda x: (x[1], x[0])))
        if prog is None:
            data = encode(acc)
            z = lz(data)
            assert unlz(z) == data
            zi = lz(bytes(ins))
            assert unlz(zi) == bytes(ins) and max(ins) < 256
            prog = {'n_acc': len(acc), 'digest': g, 'marks': pm, 'e9904': e9904, 'end': pend,
                    'n_ins': len(ins), 'ins_digest': gi, 'ins_lz': base64.b64encode(zi).decode(),
                    'writes': [len(pwr), wd], 'n_lz': len(z), 'data_lz': base64.b64encode(z).decode(),
                    'mask_b64': base64.b64encode(bytes(b for x in mask for b in (x >> 8, x & 0xFF))).decode()}
        elif prog['digest'] != g or prog['ins_digest'] != gi or prog['end'] != pend or prog['writes'] != [len(pwr), wd] or prog['e9904'] != e9904:
            raise Fail('%s: the plain program is not the first run\'s (%s / %s)' % (name, g, prog['digest']))
        rb = base64.b64decode(RB['programs'][key]['mask_b64'])          # the build's HUD text and round number
        rmask = sorted(set(mask) | set(rb[i] << 8 | rb[i + 1] for i in range(0, len(rb), 2)))
        isrs, marks, end, wr, rows = machine(h, 0x8D0C, rmask, rows=True)
        isrT = [x[1] for x in isrs]
        rp = replay(acc, pend, phase, isrT)
        if rp != [end[0], len(isrs)]:
            raise Fail('%s: the replay gives %s, the machine %s' % (name, rp, [end[0], len(isrs)]))
        for k, v in pm.items():
            if at(acc, v, phase, isrT) != marks[k]:
                raise Fail('%s: the replay puts %s at %d, the machine %d' % (name, k, at(acc, v, phase, isrT), marks[k]))
        wr.sort(key=lambda x: (x[1], x[0]))
        d = {'players': int(key), 'phase': phase, 'halt': halt, 'isrs': isrs, 'marks': marks, 'end': end, 'rows': rows,
             'writes': [len(wr), digest('%d@%d;' % (a, t) for a, t in wr)]}
        runs[name] = d
        print('%-12s phase %5d halt %s  isrs %d (own delay %d)  end %s  writes %d  rows %d' % (
            name, phase, halt, len(isrs), sum(x[2] for x in isrs), end, len(wr), len(rows)), flush=True)
    print('program: %d accesses, end %d, marks %s, $9904 at %s, held writes %d, lz %d bytes, mask %d' % (
        prog['n_acc'], prog['end'], prog['marks'], prog['e9904'], prog['writes'][0], prog['n_lz'], len(mask)))
    return {'meta': {'tool': 'tools/r1tail.py', 'no_rom_bytes': True,
                     'note': 'T, counts and digests of the round-1 tail and banner from the title (titleexit\'s world); '
                             'the data string is access timings, not tape bytes'},
            'program': prog, 'runs': runs}


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
        P = json.load(open(FIXTURE, encoding='utf-8'))['program']
        print("  DATA: '%s'," % P['data_lz'])
        print("  INS: '%s'," % P['ins_lz'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
