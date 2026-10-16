# -*- coding: utf-8 -*-
"""FRONT-END GROUP 3, SUB-INCREMENT H-d: THE LOAD SPINE -- the black screen, the 48K/128K probe
$FAC3 and the hand-over into the game.

    $F5BC  LD A,'1' / CALL $F5E7       player 1's pass (H-a..H-c)
    $F5C1  LD A,'2' / CALL $F5E7       player 2's
    $F5C6  CALL $F709                  THE CLS -- the black screen the probe runs on
    $F5C9  CALL $FAC3                  THE PROBE:
      $FAC3  IM 1 / EI / HALT            sync to an interrupt (the ROM's IM 1 routine)
      $FAC7  LD BC,0 / LD HL,0 / LD (FRAMES),HL / LD ($5C79),HL / LD E,0 / LD A,$FF / LD HL,FRAMES
      $FADA  INC E / JR nz,$FADE / INC BC / $FADE CP (HL) / JR nz,$FADA   until FRAMES = $FF
      $FAE1  B = 7 and C = $5E or $63 -> $FAF4 LD A,$30 / RET (48K); else $FAEF LD A,$80 / JP $FA3B
      $FA3B  LD HL,$FA67 / PUSH HL / RET -> $FA67 LD A,$80 / RET -- back to $F5CC either way
    $F5CC  LD HL,$F5D2 / JP $7274 -> JP $8CC3: DI / LD SP,$96DD / CALL $95F3 (the cold start, whose
           $9601 LDIR copies the sixteen bytes at HL to $B5FD) / EI / ... / $8CD2 CALL $9575 /
           $8CDA JR $8D02 -> $8D06 CALL $96DF (DI) -> ... $970E EI: the title

PHASES
  cls       $F5C6 -> $F5C9 with interrupts OFF, begun at 64 phases of the frame (every 1,092 T) and
            16 held-out midpoints; the screen and the border it leaves
  probe     KEY SCRIPTS from $F5C6 (the machine after player 1 took '4' and player 2 '3'), interrupts
            ON as the machine runs it, the keys applied at each frame boundary: every interrupt
            accepted, in the CLS and in the probe, as (T past its boundary, its length with the
            13-T acceptance); the KSTATE sets at $F5C6, $F5C9 and $F5CC; the HALT's; and the probe's
            own answer -- BC, E, A, the leg and the T from $F5C9 to $F5CC
  isr       THE ROM INTERRUPT'S T, from the idle probe loop: every key alone and under each shift
            through new, held, repeat and release; a new key in set 0; the `full` path; every pair of
            the 38 plain keys and 338 wider chords (BB_ROMISR's law)
  cold      $F5CC -> $8CCA with interrupts OFF at 64 phases and 16 held-out midpoints
  handover  $F5CC -> $970E on the 48K leg at 8 phases and on two control-select paths: the T at
            each mark, every interrupt accepted, the key table the cold start copied and the
            counters $8DB5..$8DBE at $970E

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).  No ROM byte
is recorded: key names, counts, T and game-RAM bytes only.

Usage:  python tools/loadspine.py [capture|verify|<phase>] [--jobs N]  -> build/loadspine_fixture.json
"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
import ctrlselect as cs
from ctrlmenu import world, run_to, Fail, GUARD, FRAME_T, sets_of, expand
from harness import Harness, PC, T, IFF, A as RA, E as RE

FIXTURE = 'build/loadspine_fixture.json'
STEP = 1092                                   # BB_MENU.PHASE_STEP
CLS_AT, PROBE_AT, SPINE_END = 0xF5C6, 0xF5C9, 0xF5CC
MARKS = (0x8CC3, 0x8CCA, 0x8CD0, 0x8CD5, 0x8CDA, 0x8D02, 0x96DF, 0x970E)
PATHS = {'p4p3': ('4', '3'), 'p2p2': ('2', '2')}

_ST = {}


def f5c6_state(path='p4p3'):
    """the machine at $F5C6: from title.pkl, player 1's choice, player 2's, naturally"""
    if path not in _ST:
        p1, p2 = PATHS[path]
        h, m, r = world('title')
        cs.type_key(h, p1)
        run_to(h, (0xF7B3,), True, limit=20_000_000)
        cs.type_key(h, p2)
        run_to(h, (CLS_AT,), True, limit=50_000_000)
        _ST[path] = h.save_state()
    return _ST[path]


def at(path='p4p3', phase=None):
    h = Harness(contended=True)
    h.load_state(f5c6_state(path))
    r = h.sim.registers
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    return h, h.memobj.m, r


# ------------------------------------------------------------------ cls
def phase_cls():
    out = {'ph': [], 'mid': []}
    for k in range(64):
        for half, key in ((0, 'ph'), (STEP // 2, 'mid')):
            if key == 'mid' and k % 4:
                continue
            h, m, r = at(phase=k * STEP + half)
            t0 = r[T]
            h.ports.record_writes = True
            h.ports.writes = []
            why, _ = h.run_until({PROBE_AT} | GUARD, limit=2_000_000, interrupts=False, stride=64)
            if r[PC] != PROBE_AT:
                raise Fail('$F5C9 not reached')
            out[key].append(r[T] - t0)
            if k == 0 and not half:
                outs = [v for t, p, v in h.ports.writes if (p & 0xFF) == 0xFE]
                disp = sum(1 for a in range(0x4000, 0x5800) if m[a])
                attrs = sorted(set(m[a] for a in range(0x5800, 0x5B00)))
                out['screen'] = {'display_nonzero': disp, 'attrs': attrs, 'outs': outs,
                                 'bordcr': m[0x5C48] & 0x38}
    print('cls: %d..%d T over 64 phases; screen %s' % (min(out['ph']), max(out['ph']), out['screen']))
    return out


# ------------------------------------------------------------------ probe
def scripts():
    S = {'none': []}
    for n in (1, 4, 8, 12, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 30, 40):
        S['A%d' % n] = [(60, []), (n, ['A'])]
    for k in ('SPACE', 'ENTER', '1', 'Q', 'CAPS', 'SYM', 'CAPS+A', 'SYM+A', 'A+S', 'CAPS+SYM', 'A+D+G',
              'CAPS+SYM+A'):
        S['hold_' + k] = [(60, []), (22, k.split('+'))]
    #  A+D+G held long: a freezing chord's interrupt is CHEAPER than an idle one, so the count RISES --
    #  to $0763, the second 48K answer, which no other script reaches
    for n in (100, 115, 130):
        S['adg%d' % n] = [(20, []), (n, ['A', 'D', 'G'])]
    S['whole'] = [(300, ['A'])]
    S['cls_tap'] = [(1, []), (2, ['Q'])]
    S['taps'] = [(30, [])] + [(3, ['A']), (3, [])] * 40
    S['late'] = [(250, []), (14, ['A'])]
    pool = [['A'], ['Q'], ['1'], ['SPACE'], ['ENTER'], ['CAPS'], ['SYM'], ['CAPS', 'A'], ['SYM', 'X'],
            ['A', 'S'], ['CAPS', 'SYM']]
    for i in range(8):
        rnd = random.Random(1000 + i)
        sc, n = [], 0
        while n < 270:
            k = rnd.randint(1, 12)
            sc.append((k, rnd.choice(pool) if rnd.random() < 0.5 else []))
            n += k
        S['rnd%d' % i] = sc
    for k in (1, 17, 33, 49):
        S['none@%d' % k] = ('phase', k * STEP)
    #  THE CHEAT ARMED -- $FA3F a NOP, as player 2's 'R' and the checksum leave it (H-c): the 128K
    #  leg's trampoline falls into $FA40, which reads A+D+G.  The world is poked, not driven: the
    #  byte is the checksum's own product, measured by H-c
    #  ENTERED AT $F5C9 a few T before a frame boundary: CALL / IM 1 / EI (29 T) cross it, and the
    #  HALT finds the interrupt still active -- the probe's own entry T, which the HALT otherwise absorbs
    for k in (5, 20, 28, 30, 40):
        S['edge%d' % k] = ('f5c9', FRAME_T - k)
    S['armed_A'] = ('armed', [(60, []), (30, ['A'])])
    S['armed_ADG'] = ('armed', [(60, []), (60, ['A']), (130, []), (20, ['A', 'D', 'G'])])
    return S


def drive(name, sc):
    phase, armed, f5c9 = None, False, None
    if isinstance(sc, tuple) and sc[0] == 'phase':
        phase, sc = sc[1], []
    elif isinstance(sc, tuple) and sc[0] == 'f5c9':
        f5c9, sc = sc[1], []
    elif isinstance(sc, tuple):
        armed, sc = True, sc[1]
    h, m, r = at(phase=phase)
    if f5c9 is not None:                          # the CLS run as the machine runs it, then $F5C9 moved
        run_to(h, (PROBE_AT,), True, limit=10 ** 7)
        r[T] = (r[T] // FRAME_T) * FRAME_T + f5c9
    if armed:
        m[0xFA3F] = 0x00
    ram0 = bytes(m)
    seq = expand(sc)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    out = {'phase': r[T] % fd, 'sets_cls': sets_of(m), 'cls_isrs': [], 'isrs': [], 'halt': None}
    t_cls = r[T]
    nb = (r[T] // fd + 1) * fd
    frame = 0
    cm.keys(h, keyf(0))
    cur, where, stage = None, None, 'cls'
    t_probe = None
    leg = None
    while True:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            cm.keys(h, keyf(frame))
        if pc in GUARD:
            raise Fail('guard')
        if pc == PROBE_AT and stage == 'cls':
            out['cls_T'] = r[T] - t_cls
            out['phase_probe'] = r[T] % fd
            out['sets_probe'] = sets_of(m)
            out['frame_probe'] = frame
            t_probe = r[T]
            stage = 'probe'
        elif pc == 0xFAE1 and stage == 'probe':
            out['BC'] = h.bc()
            out['E'] = r[RE]
            stage = 'answer'
        elif pc == 0xFAF4:
            leg = 48
        elif pc == 0xFAEF:
            leg = 128
        elif pc == SPINE_END and stage == 'answer':
            out['A'] = r[RA]
            out['leg'] = leg
            out['T'] = r[T] - t_probe
            out['sets_end'] = sets_of(m)
            out['frames'] = frame
            #  what the spine changed in the GAME's RAM ($6200 up, the front end's own bytes and the
            #  stack excluded): the armed cheat's work, if any
            out['game_writes'] = [[a, ram0[a], m[a]] for a in range(0x6200, 0xF5BC) if m[a] != ram0[a]]
            return out
        if cur is not None and pc >= 0x4000:          # the ROM's routine has returned
            rec = [cur % fd, r[T] - cur]
            if stage == 'cls':
                out['cls_isrs'].append(rec + [frame])
            elif out['halt'] is None:
                out['halt'] = rec
            else:
                out['isrs'].append(rec)
            cur = None
        if mem[pc] == 0x76 and r[IFF]:                # the harness's HALT: the clock to the boundary
            h._fast_halt()
            cur = r[T] - 13
            continue
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            if sim.accept_interrupt(r, mem, pc) is not False:
                cur = r[T] - 13


def one(item):
    name, sc = item
    d = drive(name, sc)
    d['script'] = sc if not isinstance(sc, tuple) else [sc[0], sc[1]]
    return name, d


def phase_probe(jobs=1):
    S = scripts()
    items = list(S.items())
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as p:
            res = p.map(one, items)
    else:
        res = [one(i) for i in items]
    out = {}
    for name, d in res:
        out[name] = d
        print('probe %-14s BC $%04X A $%02X leg %s  %d isrs  T %d  cls %d T %d isrs' % (
            name, d['BC'], d['A'], d['leg'], len(d['isrs']), d['T'], d['cls_T'], len(d['cls_isrs'])))
    return out


# ------------------------------------------------------------------ isr
def idle_world():
    """the probe's count loop running with both KSTATE sets FREE: from $F5C6, keys up, to the
       third interrupt of the probe (the '3' set left by the menu is gone by then)"""
    if 'idle' not in _ST:
        h, m, r = at()
        cm.keys(h, [])
        while True:
            h.step(1)
            if r[PC] == 0xFADA and r[T] % FRAME_T > 20000 and m[0x5C78] >= 3 and                     all(s is None for s in sets_of(m)):
                break
        _ST['idle'] = h.save_state()
    return _ST['idle']


def isr_run(seq):
    """the loop from the idle world, the keys of seq[f] applied at boundary f+1: every interrupt's
       length (the 13-T acceptance included), one per frame"""
    h = Harness(contended=True)
    h.load_state(idle_world())
    r, m = h.sim.registers, h.memobj.m
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    f, cur, out = 0, None, []
    while len(out) < len(seq):
        pc = r[PC]
        if r[T] >= nb:
            cm.keys(h, seq[f] if f < len(seq) else [])
            f += 1
            nb += fd
        if pc in GUARD or not (pc < 0x4000 or 0xFAC3 <= pc < 0xFB00):
            raise Fail('left the probe at $%04X' % pc)
        if cur is not None and pc >= 0x4000:
            out.append(r[T] - cur)
            cur = None
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            if sim.accept_interrupt(r, mem, pc) is not False:
                cur = r[T] - 13
    return out


def one_isr(item):
    kind, keys = item
    if kind == 'single':
        seq = [[]] * 2 + [keys] * 42 + [[]] * 8
    elif kind == 'slot0':                     # another key's set still aging when this one is new
        seq = [[]] * 2 + [['Q'] if keys != ['Q'] else ['W']] + [keys] * 42 + [[]] * 8
    elif kind == 'full':                      # both sets held by other keys: this one is ignored
        seq = [[]] * 2 + [['Q'], [], ['W'], []] + [keys] * 3
    else:
        seq = [[]] * 2 + [keys] * 3
    return kind, keys, isr_run(seq)


def phase_isr(jobs=1):
    idle_world()
    names = cm.NAMES
    plain = [k for k in names if k not in ('CAPS', 'SYM')]
    items = []
    for k in plain:
        for sh in ([], ['CAPS'], ['SYM']):
            items.append(('single', sh + [k]))
    items += [('single', ['CAPS']), ('single', ['SYM']), ('single', ['CAPS', 'SYM'])]
    for k in ('A', 'SPACE', 'ENTER', '1', 'X'):
        items.append(('slot0', [k]))
    for k in (['A'], ['Z'], ['SPACE'], ['1'], ['CAPS', 'A'], ['SYM', 'M'], ['CAPS', 'SYM']):
        items.append(('full', k))
    for i in range(len(plain)):
        for j in range(i + 1, len(plain)):
            items.append(('chord', [plain[i], plain[j]]))
    for k in plain:
        items.append(('chord', ['CAPS', 'SYM', k]))
    rnd = random.Random(77)
    for _ in range(300):
        n = rnd.randint(2, 5)
        items.append(('chord', rnd.sample(names, n)))
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs, initializer=_seed, initargs=(dict(_ST),)) as p:
            res = p.map(one_isr, items, chunksize=16)
    else:
        res = [one_isr(i) for i in items]
    out = {'single': [], 'slot0': [], 'full': [], 'chord': []}
    for kind, keys, ts in res:
        out[kind].append([keys, ts])
    print('isr: %d singles, %d slot-0, %d full, %d chords' % (len(out['single']), len(out['slot0']), len(out['full']),
                                                          len(out['chord'])))
    return out


def _seed(st):
    _ST.update(st)


# ------------------------------------------------------------------ handover
def handover(path, phase):
    h, m, r = at(path)
    cm.keys(h, [])
    run_to(h, (SPINE_END,), True, limit=10 ** 8)
    r[T] = (r[T] // FRAME_T) * FRAME_T + phase if phase is not None else r[T]
    buf = list(m[0xF5D2:0xF5E2])
    t0 = r[T]
    marks, isrs, seen = {}, [], set()
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    ring, after = None, []
    nb = (t0 // fd + 1) * fd
    while True:
        pc = r[PC]
        if pc in GUARD:
            raise Fail('guard')
        if pc in MARKS and pc not in seen:
            seen.add(pc)
            marks['%04X' % pc] = r[T] - t0
            if pc == 0x8CCA:
                keytab = list(m[0xB5FD:0xB60D])
            if pc == 0x970E:
                counters = list(m[0x8DB5:0x8DBF])
                nb = (r[T] // fd + 1) * fd            # the boundaries AFTER $970E
        if pc == 0x8D72:
            isrs.append(r[T] - t0)
        if 0x970E in seen:
            if ring is None and pc == 0x9768:
                ring = r[T] - t0
            if r[T] >= nb:
                after.append(list(m[0x8DB6:0x8DB8]) + list(m[0x8DBD:0x8DBF]))
                nb += fd
                if len(after) >= 3 and ring is not None:
                    break
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            sim.accept_interrupt(r, mem, pc)
        if r[T] - t0 > 16 * FRAME_T:
            raise Fail('the title\'s ring not reached')
    return {'path': path, 'phase': t0 % fd, 'marks': marks, 'isrs': isrs, 'buffer': buf, 'keytab': keytab,
            'counters': counters, 'ring': ring, 'after': after[:3]}


def phase_cold():
    """$F5CC -> $8CCA (the JPs, the DI and the cold start) with interrupts OFF, begun at 64 phases and
       16 held-out midpoints -- the frame layer's law; the natural runs above say where interrupts land"""
    h, m, r = at('p4p3')
    run_to(h, (SPINE_END,), True, limit=10 ** 8)
    st = h.save_state()
    out = {'ph': [], 'mid': []}
    for k in range(64):
        for half, key in ((0, 'ph'), (STEP // 2, 'mid')):
            if key == 'mid' and k % 4:
                continue
            h.load_state(st)
            r[T] = (r[T] // FRAME_T) * FRAME_T + k * STEP + half
            t0 = r[T]
            h.run_until({0x8CCA} | GUARD, limit=10 ** 6, interrupts=False, stride=64)
            if r[PC] != 0x8CCA:
                raise Fail('$8CCA not reached')
            out[key].append(r[T] - t0)
    print('cold: %d..%d T over 64 phases' % (min(out['ph']), max(out['ph'])))
    return out


def phase_handover():
    out = []
    for k in range(8):
        out.append(handover('p4p3', k * (FRAME_T // 8)))
    out.append(handover('p2p2', None))
    #  CRAFTED NEAR THE EDGES OF THE INTERRUPT'S WINDOW: the frame interrupt is asserted for 32 T, so one
    #  that falls in a DI is still taken if EI (and the instruction after it) ends inside those 32 T.  The
    #  cold start's T moves several T a phase step, so only some offsets exist: every one within 30 T
    #  before $8CCA and before $970E is found from the cold start's own T (interrupts off, as it runs),
    #  and each is then run NATURALLY
    h, m, r = at('p4p3')
    cm.keys(h, [])
    run_to(h, (SPINE_END,), True, limit=10 ** 8)
    st = h.save_state()

    def cold_at(ph):
        h.load_state(st)
        r[T] = (r[T] // FRAME_T) * FRAME_T + ph
        t0 = r[T]
        h.run_until({0x8CCA} | GUARD, limit=10 ** 6, interrupts=False, stride=64)
        return r[T] - t0
    found = {}
    for lo, hi, b, mark, extra in ((2000, 6000, FRAME_T, '8CCA', 0), (56000, 65000, 2 * FRAME_T, '970E', 10179 + 525)):
        for ph in range(lo, hi):
            o = b - ph - cold_at(ph) - extra                            # the wait with no interrupt in it
            if -30 <= o < 0 and (mark, o) not in found:
                found[(mark, o)] = ph
    if not any(k[0] == '8CCA' for k in found) or not any(k[0] == '970E' for k in found):
        raise Fail('no boundary within 30 T before $8CCA or $970E')
    for (mark, o), ph in sorted(found.items()):
        d = handover('p4p3', ph)
        d['crafted'] = '%s%+d' % (mark, o)
        out.append(d)
    for d in out:
        print('handover %s phase %5d  %s  isrs %s  copy %s  ring %s  %s' % (d['path'], d['phase'], d['marks'], d['isrs'],
              d['keytab'] == d['buffer'], d['ring'], d.get('crafted', '')))
    return out


def phase_window():
    """the interrupt window's own terms: how long the harness asserts the frame interrupt, and the T of
       EI and the instruction after it at $8CCA and at $970E (interrupts off, from $F5CC)"""
    h, m, r = at('p4p3')
    cm.keys(h, [])
    run_to(h, (SPINE_END,), True, limit=10 ** 8)
    out = {'int_active': h.int_active}
    for a, b in ((0x8CCA, 0x8CCD), (0x970E, 0x97EB)):
        h.run_until({a} | GUARD, limit=10 ** 7, interrupts=False, stride=1)
        t0 = r[T]
        h.run_until({b} | GUARD, limit=10, interrupts=False, stride=1)
        if r[PC] != b:
            raise Fail('$%04X not reached from $%04X' % (b, a))
        out['ei_%04X' % a] = r[T] - t0
    print('window:', out)
    return out


# ------------------------------------------------------------------ main
def capture(jobs=1):
    return {'meta': {'tool': 'tools/loadspine.py', 'no_rom_bytes': True,
                     'note': 'T, interrupt (offset, length) pairs, key NAMES and counts, game-RAM bytes'},
            'cls': phase_cls(), 'probe': phase_probe(jobs), 'isr': phase_isr(jobs),
            'cold': phase_cold(), 'handover': phase_handover(), 'window': phase_window()}


def main():
    a = sys.argv[1:]
    jobs = 1
    if '--jobs' in a:
        i = a.index('--jobs'); jobs = int(a[i + 1]); del a[i:i + 2]
    cmd = a[0] if a else 'capture'
    if cmd == 'capture':
        out = capture(jobs)
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(out, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        new = json.loads(json.dumps(capture(jobs)))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd == 'probe':
        phase_probe(jobs)
    elif cmd == 'isr':
        phase_isr(jobs)
    elif cmd in ('cls', 'cold', 'handover', 'window'):
        globals()['phase_' + cmd]()
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
