"""M7.115: A LATER ROUND'S START, EXACT -- $97F8 (the advance, in play) to $9887's HALT, the ISR that ends it, and $9888 to
$8D0C (the RET to the loop top), rounds 2..81 and the wrap past 81, against the machine frame by frame.

THE WORLDS.  buildtime's natural chunks (rounddrain's title hand-off, round 1 played F_PLAY frames, then ($8609) poked to the
round before the chunk's first, the warp refused, ($FECD) = 10: ten advances back to back), keys 1 and 2, every tenth round,
the build counter ($83EC) as found and moved two tiles on; one chunk from round 81 (the wrap to ($FEC7)'s lookahead); and
single advances with pokes: lives 0 / 7 and two EXTEND letter panels (buildtime's DIRECT worlds), and the palette index
($82D7: 0 is bit 7 clear, 1 set) against each of the five tiles ($83EC) -- every wallPattern key.

THE PROGRAMS.  From each advance's $97F8 the plain run (no contention, interrupts off) to $9887, and from $9888 (the machine's,
after the ISR that ends the HALT) to $8D0C: every contended access as (a, k) -- a its T from the segment's start, k its T
into its instruction -- split at the routine marks (SEGS).  MEASURED: every segment but three is a function of the round
alone and the player count -- the spawn ($727B) is 10..19 T longer with two (asserted: one segment list per round and
player count over every world); the three are made by the engine's own models and carried
here per world for its gates --
  'win'    $97F8..$9858: no contended access; its T is the entry walk's path (BB_BUILD_WIN) to $9855's first store plus
           the walk's fixed rest (asserted: the same rest in every world)
  'lives'  $7F5B CALL $806C .. $7F5E: extModel('lives', cp) -- its accesses and T by the players' flags, lives and the
           attributes it reads
  'panel'  $986F CALL $957E .. $9872: extModel('panel', cp) -- the EXTEND letters
  'tjr'    $83F1 JR nz .. $83F4 in the background's tile index ($83EB): 12 T, or 11 (JR 7, XOR A 4) when the index wraps
           from 4 -- MEASURED: the tile counter ($83EC) moves the background by that 1 T and nothing else
The tail's instruction grid (R1Tf's: every instruction's plain T from $9888, one byte each) is split the same way: an
instruction belongs to the segment it starts in.  Each distinct segment is stored once: its plain T, its accesses (k, then a's
step from the access before -- the first from the segment's start -- LEB128) and its grid bytes, all segments in one stream
packed by r1tail's byte LZ77 ('lz').  Access timings and instruction lengths, not tape bytes.

THE RUNS.  The machine (contended, interrupts on) from $97F8: every ISR in the build [main-line T at acceptance, T, ($FEC4),
($FEC5)], the marks, $9887's [frame after $97F8's, phase], the display writes (count + SHA-1 of 'a@t;' by main-line T); the
ISR that ends the HALT [its T]; then from $9888 every ISR [main-line T, T, own contention delay, acceptance phase], the marks,
$8D0C's [main-line T, frame after $9888's, phase], the held writes (display, $FEC5, $9F62: count + SHA-1).  The tool asserts
that each half's program replayed from its phase with the machine's ISR T gives every mark, the end and the ISR count.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/lrstart.py [capture|verify] [--jobs N]  -> build/lrstart_fixture.json
"""
import sys, os, json, base64, hashlib, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from ctrlmenu import Fail, GUARD
from harness import PC, T, IFF, SP
import buildtime as BT
import rounddrain as RD
import revealcont as RC
from isrcarry import DELAYS_48K
from r1tail import leb, lz, unlz, held

FIXTURE = 'build/lrstart_fixture.json'
FD = 69888
# the segment boundaries: each is the PC of the instruction that starts it (the first time the main line reaches it)
BSEG = [(0x97F8, 'win'), (0x9858, 'clear'), (0x9863, 'build'), (0x7F2A, 'fpat'), (0x7F2D, 'bg'), (0x83F1, 'tjr'), (0x83F4, 'bg2'),
        (0x7F6B, 'wpat'), (0x7F6E, 'bg3'), (0x7F30, 'scroll'),
        (0x7F36, 'filler'), (0x7F39, 'preroll'), (0x7F3C, 'loop'), (0x7F4E, 'repaint'), (0x7F51, 'digits'),
        (0x7F54, 'r1'), (0x7F5B, 'lives'), (0x7F5E, 'rows'), (0x9866, 'spawn'), (0x9869, 'pinit'), (0x986C, 'bolt'),
        (0x986F, 'panel'), (0x9872, 'b610')]
TSEG = [(0x9888, 'resume'), (0x98A1, 'aa49'), (0x98A4, '79ac'), (0x98A7, 'bf39'), (0x98AA, '8c5e'), (0x98AD, 'gate'),
        (0x98E4, 'e1'), (0x98E7, 'e2'), (0x98EA, 'e3')]
HOLES = ('win', 'tjr', 'lives', 'panel')
# KEYED: a segment that is a function of a key the engine knows, not of the round -- [$860C] (paletteStep's bit 7: the
# expand path) and the tile pointer [$860D] (tileIndex's), read at the segment's start
# SNAP: the RAM a hole's model reads, kept at the hole's start for the engine's gate (the player blocks, the bottom rows'
# attributes; at $97F8 also the lookahead $FEC7, the palette and tile indices -- the world the advance starts from)
SNAP = {'win': ((0xFD80, 0x80), (0x5AC0, 0x40), (0xFEC7, 1), (0x82D7, 1), (0x83EC, 1)), 'lives': ((0xFD80, 0x80), (0x5AC0, 0x40)),
        'panel': ((0xFD80, 0x80), (0x5AC0, 0x40))}
KEYED = {'wpat': lambda m: '%d_%04X' % (m[0x860C], m[0x860D] | m[0x860E] << 8)}
CHUNKS = [(k, s, sh) for k in '12' for s in range(1, 81, 10) for sh in (0, 2)] + [('1', 81, 0)]
POKED = [('lives0', '1', 10, [(0xFDDC, 0)]), ('lives7', '1', 10, [(0xFDDC, 7)]),
         ('letters', '2', 10, [(0xFDE3, 0x15), (0xFDED, 0x2A)])] +         [('pal%d_tile%d' % (pi, ti), '1', 10, [(0x82D7, pi), (0x83EC, ti)]) for pi in (0, 1) for ti in range(5)]
B9904 = 0x9904


def sha(xs):
    return hashlib.sha1(''.join(xs).encode('ascii')).hexdigest()[:16]


def plain(h, segs, stop, halt_skip=False):
    """(h at the first segment's PC) the plain run to `stop`: [(name, start T, [(a, k)], [instruction T])] and the end;
    the $9904 entries; the held writes [(a, t)]; h's simulator restored"""
    sim0, mem0 = h.sim, h.memobj
    st = h.save_state()
    log = []
    wm = RC.WriteMem(mem0.m)
    sim = RC.sim_of(h, log, wm)
    wm.regs = sim.registers
    r, mem = sim.registers, sim.memory
    marks = dict(segs)
    t0, n0, out, seen, e9904, wr, keys = r[T], 0, [], set(), [], [], {}
    cur = None
    try:
        while True:
            p, ts = r[PC], r[T]
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            if p in marks and p not in seen:
                seen.add(p)
                cur = (marks[p], ts - t0, [], [])
                if marks[p] in KEYED:
                    keys[marks[p]] = KEYED[marks[p]](mem)
                if marks[p] in SNAP:
                    keys['snap_' + marks[p]] = [[a0, bytes(mem[a0 + i] for i in range(n)).hex()] for a0, n in SNAP[marks[p]]]
                out.append(cur)
            if p == stop:
                break
            if p == B9904:
                e9904.append(ts - t0)
            if mem[p] in (0xFB, 0x76):
                raise Fail('an EI / HALT at $%04X in the plain run' % p)
            wm.tins[0] = ts - t0
            sim.opcodes[mem[p]]()
            cur[3].append(r[T] - ts)
            for x in log[n0:]:
                cur[2].append((x - t0 - cur[1], x - ts))
            n0 = len(log)
            for a, t in wm.wr:
                if held(a):
                    wr.append((a, t))
            del wm.wr[:]
            if r[T] - t0 > 8 * 10 ** 6:
                raise Fail('no $%04X in the plain run' % stop)
    finally:
        wm.regs = None
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
        h.load_state(st)
    if [n for n, _, _, _ in out] != [n for _, n in segs]:
        raise Fail('the plain run met the marks as %s' % [n for n, _, _, _ in out])
    plain.keys = keys
    return out, ts - t0, e9904, wr


def machine(h, segs, stop, disp=False):
    """(h) the machine until the main line reaches `stop`: ISRs [main T at acceptance, T, own delay, acceptance phase,
    ($FEC4), ($FEC5)], the marks {name: main T}, the end [main T, frame after the start's, phase], the writes [(a, main T)]
    (display only, or held()); h left at `stop`"""
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
    names = dict(segs)

    def contend(t, timings):
        d = orig(t, timings)
        if isr is not None:
            bucket[0] += d
        return d
    sim.contend = contend
    isrs, walls, marks, wr = [], 0, {}, []
    keep = (lambda a: 0x4000 <= a < 0x5B00) if disp else held
    try:
        while True:
            p = r[PC]
            if isr is not None and p == isr[0] and r[SP] == isr[1]:
                isrs.append([isr[3], r[T] - isr[2], bucket[0] - isr[4], isr[2] % FD, isr[5], isr[6]])
                walls += r[T] - isr[2]
                isr = None
            if p in GUARD:
                raise Fail('guard at $%04X' % p)
            main = isr is None
            if main:
                mt = r[T] - t0 - walls
                if p in names and names[p] not in marks:
                    marks[names[p]] = mt
                if p == 0x9887 and 'p9887' not in marks:
                    marks['p9887'] = [r[T] // FD - f0, r[T] % FD, mt]
                if p == stop:
                    end = [mt, r[T] // FD - f0, r[T] % FD]
                    break
                wm.tins[0] = mt
            sim.opcodes[mem[p]]()
            if main:
                for a, t in wm.wr:
                    if keep(a):
                        wr.append((a, t))
            del wm.wr[:]
            if r[IFF] and r[T] % FD < ia:
                b, s, ta = r[PC], r[SP], r[T]
                g4, g5 = mem[0xFEC4], mem[0xFEC5]
                if sim.accept_interrupt(r, mem, p):
                    assert isr is None, 'an interrupt inside the ISR'
                    isr = (b, s, ta, ta - t0 - walls, bucket[0], g4, g5)
            if r[T] - t0 > 8 * 10 ** 6:
                raise Fail('no $%04X on the machine' % stop)
    finally:
        wm.regs = None
        sim.contend = orig
        h.sim, h.memobj = sim0, mem0
        mem0.sim = sim0
    sim0.registers[:] = r                             # the harness carries on from `stop` over the same RAM
    return isrs, marks, end, wr


def flat(segs):
    """a segment list -> the whole program [(a, k)] from the first segment's start"""
    return [(t + a, k) for _, t, acc, _ in segs for a, k in acc]


def replay(acc, end, phase, isrT):
    """r1tail's: the main-line T of plain T `end` from the program at `phase`, ISR i's T at the first access whose
    instruction starts at or past its boundary: [main-line end, ISRs before it]"""
    D = I = n = 0
    nb = FD - phase
    for a, k in acc:
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
    D = I = n = 0
    nb = FD - phase
    for a, k in acc:
        if a >= t:
            break
        while a - k + D + I >= nb:
            I += isrT[n]
            nb += FD
            n += 1
        D += DELAYS_48K[(phase + a + D + I) % FD]
    return t + D


def enc(acc, ins, length):
    """a segment's bytes: LEB128 plain T, access count, instruction count, then per access k and a's step, then the grid"""
    out = bytearray(leb(length) + leb(len(acc)) + leb(len(ins)))
    last = 0
    for a, k in acc:
        if not (0 <= k < 128 and a >= last):
            raise Fail('an access out of order or k %d' % k)
        out.append(k)
        out.extend(leb(a - last))
        last = a
    for x in ins:
        if not 0 < x < 256:
            raise Fail('an instruction of %d T' % x)
        out.extend([x])
    return bytes(out)


def segbytes(segs, end, tail):
    """each segment's bytes (holes: None) and the lengths; the build carries no grid (its ISRs are gate-closed or
    run at the window's own T), the tail does"""
    res = []
    for i, (nm, t, acc, ins) in enumerate(segs):
        t1 = segs[i + 1][1] if i + 1 < len(segs) else end
        res.append((nm, t1 - t, acc, ins if tail else []))
    return res


def advance(h, tag):
    """(h at $97F8 in play) one advance measured; h left at $8D0C"""
    r, m = h.sim.registers, h.memobj.m
    rnd0 = m[0x8609]
    phase = r[T] % FD
    odd = (m[0x8DBD] + 1) & 1
    bsegs, bend, _, _ = plain(h, BSEG, 0x9887)
    keys = plain.keys
    bi, bm, bE, bw = machine(h, BSEG, 0x9888, disp=True)
    halt = bi[-1]                                     # the ISR that ends $9887's HALT
    bi = bi[:-1]
    rnd = m[0x8609]
    bacc = flat(bsegs)
    if bsegs[0][2]:
        raise Fail('%s: a contended access in $97F8..$9858' % tag)
    bT = [x[1] for x in bi]
    brp = replay(bacc, bend, phase, bT)
    if brp != [bm['p9887'][2], len(bi)]:
        raise Fail('%s: the build replay gives %s, the machine %s' % (tag, brp, [bm['p9887'][2], len(bi)]))
    for nm, t, _, _ in bsegs:
        if at(bacc, t, phase, bT) != bm[nm]:
            raise Fail('%s: the build replay puts %s at %d, the machine %d' % (tag, nm, at(bacc, t, phase, bT), bm[nm]))
    tphase = r[T] % FD
    tsegs, tend, e9904, pwr = plain(h, TSEG, 0x8D0C)
    ti, tm, tE, tw = machine(h, TSEG, 0x8D0C)
    tacc = flat(tsegs)
    trp = replay(tacc, tend, tphase, [x[1] for x in ti])
    if trp != [tE[0], len(ti)]:
        raise Fail('%s: the tail replay gives %s, the machine %s' % (tag, trp, [tE[0], len(ti)]))
    for nm, t, _, _ in tsegs:
        if at(tacc, t, tphase, [x[1] for x in ti]) != tm[nm]:
            raise Fail('%s: the tail replay puts %s off the machine' % (tag, nm))
    bw.sort(key=lambda x: (x[1], x[0]))
    tw.sort(key=lambda x: (x[1], x[0]))
    pwr.sort(key=lambda x: (x[1], x[0]))
    return {
        'tag': tag, 'round0': rnd0, 'round': rnd, 'players': 2 if m[0xFD91] & 0x80 else 1, 'phase': phase, 'odd': odd,
        'build': {'segs': segbytes(bsegs, bend, False), 'end': bend, 'replay': brp, 'isrs': bi, 'marks': bm,
                  'p9887': bm['p9887'], 'writes': [len(bw), sha('%d@%d;' % (a, t) for a, t in bw)]},
        'keys': keys, 'halt': [halt[1], halt[2], halt[3]],
        'tail': {'phase': tphase, 'segs': segbytes(tsegs, tend, True), 'end': tend, 'e9904': e9904, 'isrs': ti,
                 'marks': tm, 'stop': tE, 'writes': [len(tw), sha('%d@%d;' % (a, t) for a, t in tw)],
                 'plain_writes': [len(pwr), sha('%d@%d;' % (a, t) for a, t in pwr)]},
    }


def pack(adv):
    """an advance's segments -> (name, length, bytes) with zlib'd bytes for the trip home"""
    out = {}
    for half in ('build', 'tail'):
        segs = []
        for nm, L, acc, ins in adv[half]['segs']:
            segs.append([nm, L, zlib.compress(enc(acc, ins, L), 6)])
        out[half] = segs
    return out


def chunk(args):
    key, start, shift = args
    h = BT.my_handoff(key)
    BT.trace(h, True, keep_writes=False)              # the title's advance: round 1
    r, m = h.sim.registers, h.memobj.m
    RD.ledger(h, lambda p, i: p == 0x8D0C)
    t_end = r[T] + RD.F_PLAY * h.frame_duration
    RD.ledger(h, lambda p, i: p == 0x8D0C and r[T] >= t_end)
    m[0x8609] = start
    m[0xFDDA] |= 0x80
    m[0xFDE4] |= 0x80
    if shift:
        m[0x83EC] = (m[0x83EC] + shift) % 5
    n = 10 if start < 81 else 3
    m[0xFECD] = n
    res = []
    for k in range(n):
        RD.ledger(h, lambda p, i: p == 0x97F8)
        tag = '%s_%d_%d_%d' % (key, start, shift, k)
        a = advance(h, tag)
        a['bytes'] = pack(a)
        for half in ('build', 'tail'):
            a[half]['segs'] = [[nm, L] for nm, L, _, _ in a[half]['segs']]
        res.append(a)
    return res


def poked(args):
    tag, key, start, pokes = args
    mb, regs = BT.world_at(key, start, pokes)
    h = BT.exact_from(mb, regs)
    # world_at's machine is a plain one; run this advance on the contended harness from the same bytes
    from harness import Harness
    import portconfig as pc
    hc = Harness(contended=True)
    hc.load_state_file(pc.state_path('round1_48'))
    hc.memobj.m[:] = mb
    hc.sim.registers[:] = regs
    a = advance(hc, tag)
    a['bytes'] = pack(a)
    for half in ('build', 'tail'):
        a[half]['segs'] = [[nm, L] for nm, L, _, _ in a[half]['segs']]
    return [a]


def job(x):
    return chunk(x[1:]) if x[0] == 'c' else poked(x[1:])


def capture(jobs):
    work = [('c',) + c for c in CHUNKS] + [('p',) + p for p in POKED]
    cache = os.environ.get('LRSTART_CACHE')           # a development aid: the advances pickled, not the fixture
    if cache and os.path.exists(cache):
        import pickle
        advs = pickle.load(open(cache, 'rb'))
    else:
        with ProcessPoolExecutor(jobs) as ex:
            advs = [a for res in ex.map(job, work) for a in res]
        if cache:
            import pickle
            pickle.dump(advs, open(cache, 'wb'))
    table, index, rounds, holes, runs, bad, keyed = [], {}, {}, {}, {}, [], {}
    for a in advs:
        ids = {}
        for half in ('build', 'tail'):
            lst = []
            for (nm, L), (_, _, zb) in zip(a[half]['segs'], a['bytes'][half]):
                b = zlib.decompress(zb)
                if nm in HOLES:
                    if nm == 'win' and b[len(leb(L)):len(leb(L)) + 1] != b'\x00':
                        raise Fail('%s: a contended access in $97F8..$9858' % a['tag'])
                    holes.setdefault(nm, {})
                    d = hashlib.sha1(b).hexdigest()[:16]
                    holes[nm].setdefault(d, {'len': L, 'b64': base64.b64encode(b).decode(), 'worlds': []})['worlds'].append(a['tag'])
                    lst.append([nm, L, d])
                    continue
                d = hashlib.sha1(b).hexdigest()
                if d not in index:
                    index[d] = len(table)
                    table.append(b)
                if nm in KEYED:
                    k = a['keys'][nm]
                    was = keyed.setdefault(nm, {}).setdefault(k, index[d])
                    if was != index[d]:
                        bad.append('%s: %s keyed %s is not its first' % (a['tag'], nm, k))
                    lst.append([nm, k])
                    continue
                lst.append(index[d])
            ids[half] = lst
        sig = [[x for x in ids['build'] if not isinstance(x, list)], ids['tail']]  # holes and keyed are lists
        key = '%d_%d' % (a['round'], a['players'])
        prev = rounds.get(key)
        if prev is None:
            rounds[key] = {'build': ids['build'], 'tail': ids['tail'], 'sig': sig, 'worlds': [a['tag']]}
        elif prev['sig'] != sig:
            names = [n for _, n in BSEG if n not in HOLES and n not in KEYED] + [n for _, n in TSEG]
            diff = [n for n, x, y in zip(names, prev['sig'][0] + prev['sig'][1], sig[0] + sig[1]) if x != y]
            bad.append('%s: round %d\'s program is not %s\'s in %s' % (a['tag'], a['round'], prev['worlds'][0], diff))
        else:
            prev['worlds'].append(a['tag'])
        del a['bytes']
        a['holes'] = {x[0]: [x[1], x[2]] for x in ids['build'] if isinstance(x, list) and x[0] in HOLES}
        runs[a['tag']] = a
        print('%-12s r%-3d %dP phase %5d  build isrs %d (gates %s) end %s  halt %s  tail isrs %d end %s' % (
            a['tag'], a['round'], a['players'], a['phase'], len(a['build']['isrs']),
            sorted(set((x[4], x[5]) for x in a['build']['isrs'])), a['build']['p9887'], a['halt'],
            len(a['tail']['isrs']), a['tail']['stop']), flush=True)
    if bad:
        for x in bad:
            print(x)
        raise Fail('%d advances not their round\'s first' % len(bad))
    stream = b''.join(table)
    z = lz(stream)
    assert unlz(z) == stream
    for v in rounds.values():
        del v['sig']
    print('segments %d, stream %d -> %d bytes; rounds %s' % (len(table), len(stream), len(z), sorted(rounds)))
    return {'meta': {'tool': 'tools/lrstart.py', 'no_rom_bytes': True,
                     'note': 'T, counts and digests of a later round\'s start ($97F8..$8D0C) on natural advances; the stream '
                             'is access timings and instruction lengths, not tape bytes'},
            'segs': [len(b) for b in table], 'lz': base64.b64encode(z).decode(), 'n_stream': len(stream),
            'keyed': keyed, 'rounds': dict(sorted(rounds.items(), key=lambda kv: tuple(map(int, kv[0].split('_'))))), 'holes': holes, 'runs': runs}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 20
    if cmd == 'capture':
        out = capture(jobs)
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture(jobs)))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd == 'emit':
        F = json.load(open(FIXTURE, encoding='utf-8'))
        code = {'win': 'w', 'tjr': 'j', 'lives': 'l', 'panel': 'p', 'wpat': 'k'}
        one = lambda x: code[x[0]] if isinstance(x, list) else str(x)
        rs = ', '.join("'%s': '%s|%s'" % (k, ','.join(map(one, v['build'])), ','.join(map(one, v['tail'])))
                       for k, v in F['rounds'].items())
        print("  N: %d, SEGS: %d," % (F['n_stream'], len(F['segs'])))
        print("  WPAT: {%s}," % ', '.join("'%s': %d" % kv for kv in sorted(F['keyed']['wpat'].items())))
        print("  R: {%s}," % rs)
        print("  LZ: '%s'," % F['lz'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
