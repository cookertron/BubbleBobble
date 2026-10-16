"""M7.115d: THE POTION (power-up type 12, $890D -- the level skip that opens the treasure room), through play on the
machine: what the owner's "fills the level, then crashes" was measured against.

THE WORLD.  passacc's real load (boot.pkl's $F5BC, the control select, the title, round 1; keys at each ISR's end), then
P (right) and O (left) alternately, 20 frames each.  At the END of the ISR labelled F a type-12 item is laid in the
power-up entry ($9603 = P1's X & $F0 | 12, $9604 = P1's Y & $F8 | 1) under P1, so the game's own item pass takes it.

RECORDED, from F - 2 to frame END:
  rows      every ISR [label, ($FEC4), ($FEC5), P1 X, P1 Y, ($FED1), ($8609), live bubble slots] -- a label missing
            between two rows is an interrupt the machine lost (DI)
  take      $87F0 (the collect's byte0 := 0) [frame, phase]; dispatch $890D [frame, phase]
  gates     every main-line write that changes ($FEC4) / ($FEC5) from the dispatch to the room's end: [frame, PC, 4, 5]
  advance   the room's round advance, $97F8 [frame, phase]

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

M7.115e: reach(tag) stops the same run at the game's own $890D and returns the harness state there -- tools/isrcarry.py's
'potion:real' source (the potion's block on the frame clock, from the real load's own phase).  And 'fill': $8950's fill to
its RET, PLAIN (no contention, interrupts off), on every map build/treasure_fixture.json holds -- each round's colour
shadow with both probe offsets (type 1 / -$21, type 9 / -1) and the three built shadows -- its T and every write
[T, address, value], T from $8950 at the writing instruction's start: the engine's ptFillModel against the machine,
the table-full exit ($8974 EI / RET: round 80, every cell open) among them.

Usage:  python tools/potion.py [capture|verify] [--jobs N]  -> build/potion_fixture.json  (~2.5 min on 2 workers)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP
from passacc import SCRIPT

FIXTURE = 'build/potion_fixture.json'
FD = 69888
WORLDS = [('f600', 600, 2700), ('f700', 700, 2800)]       # (tag, the ISR the item is laid after, last frame)


def keyf(seq):
    return lambda f: seq[f] if f < len(seq) else (['P'] if f % 40 < 20 else ['O'])


def run(wd, stop=False):
    """the world's rows; with `stop` (M7.115e) the harness state at the game's own $890D instead, its frame and phase --
    the real load's potion source for tools/isrcarry.py"""
    tag, F, END = wd
    h, m, r = world('boot')
    kf = keyf(expand(SCRIPT))
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD
    nb = (r[T] // fd + 1) * fd
    st = {'isr': None}
    frame, in_scan, pending = 0, False, None
    rows, take, dispatch, gates, advance = [], None, None, [], None
    cm.keys(h, kf(0))
    while frame < END:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        isr = st['isr']
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if in_scan:
                pending = kf(L)
            else:
                cm.keys(h, kf(L))
            if L == F:
                m[0x9603] = (m[0xFD85] & 0xF0) | 12
                m[0x9604] = (m[0xFD86] & 0xF8) | 1
            if L >= F - 2:
                rows.append([L, m[0xFEC4], m[0xFEC5], m[0xFD85], m[0xFD86], m[0xFED1], m[0x8609],
                             sum(1 for k in range(12) if m[0xFED8 + 10 * k + 7] & 0x80)])
            st['isr'] = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('%s: guard at $%04X' % (tag, pc))
        if pc == 0xF7B8:
            in_scan = True
        main = st['isr'] is None
        if main and frame >= F:
            if pc == 0x87F0 and take is None:
                take = [frame, r[T] % fd]
            elif pc == 0x890D and dispatch is None:
                dispatch = [frame, r[T] % fd]
                if stop:
                    return {'tag': tag, 'state': h.save_state(), 'frame': frame, 'phase': r[T] % fd}
            elif pc == 0x97F8 and dispatch is not None and advance is None:
                advance = [frame, r[T] % fd]
        b4, b5 = m[0xFEC4], m[0xFEC5]
        ops[mem[pc]]()
        if main and dispatch is not None and advance is None and (m[0xFEC4] != b4 or m[0xFEC5] != b5) and \
                pc not in (0x93E1, 0x93F9):           # $93DC's dark window: every pass (M7.114b)
            gates.append([frame, pc, m[0xFEC4], m[0xFEC5]])
        if r[IFF] and r[T] % fd < ia:
            b0, s0 = r[PC], r[SP]
            if sim.accept_interrupt(r, mem, pc):
                st['isr'] = (b0, s0, frame + (1 if r[T] >= nb else 0))
    if take is None or dispatch is None or advance is None:
        raise Fail('%s: take %s dispatch %s advance %s' % (tag, take, dispatch, advance))
    labels = [x[0] for x in rows]
    lost = [L for L in range(labels[0], labels[-1] + 1) if L not in set(labels)]
    return {'tag': tag, 'F': F, 'end': END, 'take': take, 'dispatch': dispatch, 'gates': gates, 'advance': advance,
            'lost': lost, 'rows': rows}


def reach(tag):
    """M7.115e: the real load stopped at the game's own $890D (a WORLDS tag) -- tools/isrcarry.py's potion:real source"""
    return run(next(w for w in WORLDS if w[0] == tag), stop=True)


TREASURE = 'build/treasure_fixture.json'


def fill_times():
    """M7.115e: [{map, type, off, T, writes: [[T, address, value]...]}...] -- $8950 to its RET on each treasure map"""
    import revealentry as RE
    import isrcarry as IC
    TF = json.load(open(TREASURE, encoding='utf-8'))
    maps = [('round %d' % x['round'], x['shadow'], t, o) for x in TF['offsets'] for t, o in ((1, 0xFFDF), (9, 0xFFFF))] +            [(x['name'], x['shadow'], 1, 0xFFDF) for x in TF['built']]
    h = RE.new('round1_48')
    RE.plain(h)
    rm = IC.ValMem(h.memobj.m)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes()
    r, raw = h.sim.registers, rm.m
    sp0 = r[SP]
    out = []
    for name, shadow, type_, off in maps:
        for i in range(0x300):
            raw[0xF800 + i] = shadow[i]
        for i in range(64):
            raw[0x9603 + i] = 0
        raw[0x9603], raw[0x9604] = 0x77, 0x88            # entry 0 live: the fill starts at $9605 (treasure.py's)
        for i in range(6):
            raw[0x9643 + i] = 0xC9                       # past the block
        raw[0x896D] = type_
        raw[0x899F], raw[0x89A0] = off & 0xFF, off >> 8
        r[SP] = sp0
        RE.push_call(h, 0x8950)
        del rm.wr[:], rm.val[:]
        t0 = r[T]
        rm.regs = r
        n = 0
        while r[PC] != h.SENTINELS[0]:
            rm.tins[0] = r[T]
            h.sim.opcodes[raw[r[PC]]]()
            n += 1
            if n > 200000:
                raise Fail('%s: the fill did not return' % name)
        rm.regs = None
        out.append({'map': name, 'type': type_, 'off': off, 'T': r[T] - t0,
                    'writes': [[t - t0, a, v] for (a, t), v in zip(rm.wr, rm.val)]})
    return out


def capture(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(run, WORLDS))
    for x in res:
        print('%-5s take %s dispatch %s gates %s lost %s advance %s, %d rows' % (
            x['tag'], x['take'], x['dispatch'], ['%d $%04X %d %d' % tuple(g) for g in x['gates']], x['lost'],
            x['advance'], len(x['rows'])), flush=True)
    return {'meta': {'tool': 'tools/potion.py', 'no_rom_bytes': True,
                     'note': 'gates, positions, latches and frame / phase marks of the potion (type 12) on the real load'},
            'script': [[k, v] for k, v in SCRIPT], 'runs': {x['tag']: x for x in res}, 'fill': fill_times()}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 2
    if cmd == 'capture':
        out = capture(jobs)
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture(jobs)))
        print('verify:', 'MATCH' if old == new else 'DIFFER')
        return 0 if old == new else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
