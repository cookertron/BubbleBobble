# -*- coding: utf-8 -*-
"""FRONT-END GROUP 3, SUB-INCREMENT H-c: THE REDEFINE SCREEN $F723..$F7B0 -- and player 2's
paint after player 1 took KEYBOARD, which H-b's frame layer could not charge.

    $F723  CALL $F709 / CALL $F82A / CALL $F72F / JP $F6DB    the CLS, the rainbow, the loop, the builder
    $F72F  NOP                                                 (nothing writes it)
    $F730  LD IX,$F8AD / LD A,3 / LD HL,$4020 / CALL $F80B     CHOOSE KEYS FOR PLAYER n
    $F73C  LD IX,$F8C6 / LD A,9 / LD HL,$40A0 / CALL $F80B     LEFT :?
    $F748  CALL $F7B3 / LD ($F983),A                           the first answer ... five in all:
           RIGHT $4800 -> $F984, FIRE $4860 -> $F986, JUMP $48C0 -> $F985 (the THIRD and FOURTH
           SWAPPED), ALL OK ? $5020 -> $F987
    $F796  CP 'Y' / RET z                                      back to $F72C: JP $F6DB, the builder
    $F799  SUB 'R' / JR nz,$F7A7 / LD A,($F8C4) / SUB '2' / JR nz,$F7A7 / LD ($F6A3),A
                                                               PLAYER 2's 'R' turns $F6A3's RET into a NOP
    $F7A7  CALL $F6A3                                          a RET -- or, armed, the checksum $F6A4:
           A + ($F983..$F987) - $8F == 0 -> ($FA3F) := 0, OUT ($FE),2
    $F7AA  CALL $F709 / CALL $F82A / JP $F72F                  and the five questions again

The key read is H-b's $F7B3, unchanged -- but $F674 set $F850 to a NOP, so its echo PRINTS the
answer over the '?' ($F97F stepped back one column).

PHASES
  screen    every screen write, in order, of each drive from $F723 to the builder's RET: the
            CLS and the rainbow as the machine writes them, the printer's as (address, code,
            source row) -- no ROM byte; with the prompts' calls, the answers, the end state,
            every OUT that is not the click's and the T of every mark.  Interrupts OFF, the
            keys fed at each scan.  Eleven drives on four worlds, the cheat armed and fired.
  timing    the T the frame layer charges, interrupts OFF: the screen ($F723 -> $F748), each
            prompt (the read's $F801 -> the next CALL $F7B3), the loop ($F7AA -> $F748) -- each
            begun at 64 phases of the frame with 16 held-out midpoints -- the click with its
            echo at 64 phases for each of the five reads, the answer's exits and the builder
            by path; and PLAYER 2's PAINT after player 1's KEYBOARD ($F671 = $31) the same way
  frames    key scripts from boot.pkl's own $F5BC through the redefine screen, a sample at
            every frame boundary (interrupts ON, as the machine runs it)

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/redefine.py [capture|verify|<phase>]  -> build/redefine_fixture.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import (world, keys, run_to, Fail, GUARD, FRAME_T, OUTS, click_out, vars_of, sets_of,
                      expand, Nat)
from harness import Harness, PC, T, IFF, A as RA, H as RH, L as RL, D as RD, E as RE, IXh, IXl

FIXTURE = 'build/redefine_fixture.json'
CALL_READ = (0xF748, 0xF75A, 0xF76C, 0xF77E, 0xF790)        # the five CALL $F7B3
ANSWER_AT = (0xF983, 0xF984, 0xF986, 0xF985, 0xF987)        # where each answer is stored
MARKS = set(CALL_READ) | {0xF723, 0xF7D3, 0xF7E9, 0xF7F9, 0xF801, 0xF796, 0xF7A7, 0xF7AA, 0xF6DB,
                          0xF708, 0xF5C1, 0xF5C6, 0xF6A4, 0xF6B0, 0xF6B5}
WRITER = {0xF712: 'cls', 0xF713: 'cls', 0xF831: 'rainbow', 0xF84C: 'rainbow', 0xF84D: 'rainbow',
          0xF88A: 'printer', 0xF88D: 'printer'}
ENDS = (0xF5C1, 0xF5C6)                                     # the builder's RET into the spine
STATE = [('F829', 0xF829), ('F850', 0xF850), ('F671', 0xF671), ('F6A3', 0xF6A3), ('FA3F', 0xFA3F),
         ('F8C4', 0xF8C4), ('BORDCR', 0x5C48)]


def rd_world(p1=None):
    """the machine at $F723 with the dispatch done: player 1 took KEYBOARD (p1 None), or player 1
       took `p1` and player 2 took KEYBOARD.  Returns a saved state."""
    if p1 is None:
        h, m, r = world('title')
    else:
        h, m, r = world('p2' if p1 == '4' else 'title')
        if p1 != '4':
            keys(h, [p1])
            run_to(h, (0xF7F9,), True)
            keys(h, [])
            run_to(h, (0xF5E7,), True)
            run_to(h, (0xF664,), True)
    keys(h, ['1'])
    run_to(h, (0xF7F9,), True)
    keys(h, [])
    run_to(h, (0xF723,), True)
    if h.memobj.m[0xF8C4] != (0x31 if p1 is None else 0x32):
        raise Fail('the redefine screen was reached on the wrong pass')
    return h.save_state()


_W = {}


def rd(p1=None):
    if p1 not in _W:
        _W[p1] = rd_world(p1)
    h = Harness(contended=True)
    h.load_state(_W[p1])
    return h, h.memobj.m, h.sim.registers


def fed(h, answers, stop=ENDS, log=True, limit=3_000_000, until=None, check=True, min_taken=0):
    """from where h stands, interrupts OFF, to `stop`: each answer (a chord) held from the first
       scan of its read until the read accepts ($F7D3), then let go.  Records the screen writes
       by writer, the printer's (HL, DE) taps, the prompts' calls, the marks and the OUTs."""
    r, m = h.sim.registers, h.memobj.m
    chars = m[0x5C36] | (m[0x5C37] << 8)
    if log:
        h.memobj.watch(0x4000, 0x10000)
    taps, calls, marks = [], [], []
    out0 = len(OUTS)
    i, n, t0 = 0, 0, r[T]
    sp0 = r[cm.SP]
    reading = False
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('PC entered the guard at $%04X' % p)
        if (p in stop and i >= min_taken) or (until is not None and p in until):
            break
        if p in MARKS:
            marks.append([p, r[T] - t0])
        if p == 0xF7B8 and not reading:
            keys(h, answers[i] if i < len(answers) else [])
            reading = True
        elif p == 0xF7D3:
            i += 1
            keys(h, [])
            reading = False
        elif p in (0xF88A, 0xF88D):
            taps.append(((r[RH] << 8) | r[RL], (r[RD] << 8) | r[RE]))
        elif p == 0xF80B:
            calls.append([(r[IXh] << 8) | r[IXl], r[RA], (r[RH] << 8) | r[RL]])
        h.step(1, interrupts=False)
        n += 1
        if n > limit:
            raise Fail('never reached the end (PC $%04X, answer %d)' % (r[PC], i))
    wl = list(h.memobj.log) if log else []
    if log:
        h.memobj.unwatch()
    if check and i != len(answers):
        raise Fail('%d answers fed, %d taken' % (len(answers), i))
    return {'sp': sp0, 'wl': wl, 'taps': taps, 'calls': calls, 'marks': marks, 'chars': chars, 'T': r[T] - t0,
            'outs': [[t - t0, pc_, v] for t, pc_, port, v in OUTS[out0:] if port == 0xFE and not click_out(pc_)],
            'end': r[PC]}


def screen_runs(d):
    """the ordered screen writes as runs by writer: the CLS [start, n] (checked an ascending run
       of zeros), the rainbow [[a, v]], the printer [[a, code, row]] -- no ROM-derived value"""
    runs, ti = [], 0
    for p, a, v in d['wl']:
        if not (0x4000 <= a < 0x5B00):
            continue
        k = WRITER.get(p)
        if k is None:
            raise Fail('a screen write from $%04X at $%04X' % (p, a))
        if k == 'printer':
            hl, de = d['taps'][ti]
            ti += 1
            if hl != a:
                raise Fail('a printer tap at $%04X wrote $%04X' % (hl, a))
            off = (de - d['chars']) & 0xFFFF
            item = [a, off // 8, off % 8]
        else:
            item = [a, v]
        if not runs or runs[-1][0] != k:
            runs.append([k, []])
        runs[-1][1].append(item)
    out = []
    for k, w in runs:
        if k == 'cls':
            if [a for a, v in w] != list(range(0x4000, 0x4000 + len(w))) or any(v for a, v in w):
                raise Fail('a CLS that is not an ascending run of zeros')
            out.append(['cls', 0x4000, len(w)])
        else:
            out.append([k, w])
    if ti != len(d['taps']):
        raise Fail('printer taps left over')
    return out


def game_writes(d):
    """the last value of every game byte written from $5B00, less the ROM's system variables (all
       but LAST-K) and the stack -- neither modelled"""
    last = {}
    sp = d['sp']
    for p, a, v in d['wl']:
        if (0x5C00 <= a < 0x5CC0 and a != 0x5C08) or sp - 48 <= a < sp + 4:
            continue
        if a >= 0x5B00:
            last[a] = v
    return sorted([a, v] for a, v in last.items())


def state_of(m):
    return {n: m[a] for n, a in STATE} | {'answers': [m[a] for a in range(0xF983, 0xF988)],
                                          'F97B': [m[a] for a in range(0xF97B, 0xF983)],
                                          'cursor': m[0xF5E5] | (m[0xF5E6] << 8),
                                          'buffer': list(m[0xF5D2:0xF5E2])}


# ------------------------------------------------------------------ the screen drives
DRIVES = [
    ('p1_plain', None, ['O', 'P', 'Q', 'A', 'Y']),
    ('p1_specials', None, ['SPACE', 'ENTER', 'SYM+X', 'SYM+0', 'Y']),
    ('p1_shifted', None, ['SYM+H', 'CAPS+R', '0', 'Z', 'Y']),
    ('p1_loop', None, ['A', 'B', 'C', 'D', 'N', 'E', 'F', 'G', 'H', 'Y']),
    ('p1_r', None, ['O', 'O', 'O', 'P', 'R', '1', '2', '3', '4', 'Y']),
    ('p2_cheat', '4', ['O', 'O', 'O', 'P', 'R', 'A', 'B', 'C', 'D', 'Y']),
    ('p2_armed', '4', ['A', 'B', 'C', 'D', 'R', 'E', 'F', 'G', 'H', 'N', 'I', 'J', 'K', 'L', 'Y']),
    ('p2_armed_pass', '4', ['A', 'B', 'C', 'D', 'R', 'S', 'S', 'S', 'R', 'K', 'Q', 'W', 'E', 'T', 'Y']),
    ('p2_after_sinclair', '2', ['6', '7', '9', '0', 'Y']),
    ('p2_after_kempston', '3', ['Q', 'A', 'O', 'P', 'Y']),
    ('p1_twice_n', None, ['1', '1', '1', '1', 'N', '1', '1', '1', '1', 'N', 'W', 'X', 'Y', 'Z', 'Y']),
]


def chord(k):
    return k.split('+')


def phase_screen():
    out = {}
    for name, p1, ans in DRIVES:
        h, m, r = rd(p1)
        before = state_of(m)
        d = fed(h, [chord(k) for k in ans])
        out[name] = {'p1': p1, 'answers': ans, 'runs': screen_runs(d), 'calls': d['calls'],
                     'marks': d['marks'], 'outs': d['outs'], 'T': d['T'], 'end_pc': d['end'],
                     'before': before, 'after': state_of(m), 'writes': game_writes(d)}
        pr = sum(len(x[1]) for x in out[name]['runs'] if x[0] == 'printer')
        print('screen %-18s %d runs, %d printer writes, %d calls, outs %s, T %d, FA3F $%02X F6A3 $%02X' % (
            name, len(out[name]['runs']), pr, len(d['calls']), [(o[1], o[2]) for o in d['outs']],
            d['T'], m[0xFA3F], m[0xF6A3]))
    return out


# ------------------------------------------------------------------ the timing
N_PH = 64
STEP = FRAME_T // N_PH


def at_phase(h, ph):
    r = h.sim.registers
    r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph
    return r[T]


def seg(state, stop, ph, answers=()):
    """T from a saved state to `stop`, begun at phase `ph` of the next frame, interrupts OFF"""
    h = Harness(contended=True)
    h.load_state(state)
    t0 = at_phase(h, ph)
    d = fed(h, [chord(k) for k in answers], stop=(stop,), log=False, check=False)
    return d['T']


def states_along(p1, ans):
    """the saved states of one drive at $F723, at each read's $F801 and at $F7AA, and at each
       read's $F7D3 -- the starts the timing is measured from"""
    h, m, r = rd(p1)
    st = {'F723': h.save_state(), 'F801': [], 'F7AA': [], 'F7D3': [], 'F6DB': []}
    answers = [chord(k) for k in ans]
    for k, a in enumerate(answers):
        fed(h, [a], stop=(0xF7D3,), log=False, check=False)
        st['F7D3'].append(h.save_state())
        fed(h, [], stop=(0xF801,), log=False, check=False)
        st['F801'].append(h.save_state())
        if k % 5 == 4:
            if a == ['Y']:
                fed(h, [], stop=(0xF6DB,), log=False, check=False)
                st['F6DB'].append(h.save_state())
                break
            fed(h, [], stop=(0xF7AA,), log=False, check=False)
            st['F7AA'].append(h.save_state())
    return st


def phase_timing():
    out = {}
    st = states_along(None, ['A', 'B', 'C', 'D', 'N', 'E', 'F', 'G', 'H', 'Y'])
    ph = [k * STEP for k in range(N_PH)]
    held = [k * 4 * STEP + STEP // 2 for k in range(N_PH // 4)]
    tabs, ho = {}, {}

    def law(name, fn):
        tabs[name] = [fn(p) for p in ph]
        ho[name] = [[p, fn(p)] for p in held]

    law('screen', lambda p: seg(st['F723'], 0xF748, p))
    for i in range(4):
        law('prompt%d' % i, lambda p, i=i: seg(st['F801'][i], CALL_READ[i + 1], p))
    law('loop', lambda p: seg(st['F7AA'][0], 0xF748, p))
    #  ...and within it the CLS's OUT ($F716): when a red border the cheat sent goes back to black
    law('cls_out', lambda p: seg(st['F7AA'][0], 0xF716, p))
    #  the click with its echo, $F7D3 -> $F7F9, for each read: the mean of 64 phases (the click's own
    #  law is H-b's, a mean; the echo's glyph lands on a different row for each prompt)
    clk = []
    for i in range(5):
        xs = [seg(st['F7D3'][i], 0xF7F9, p) for p in ph]
        clk.append({'mean': sum(xs) / len(xs), 'min': min(xs), 'max': max(xs)})
    out['click_echo'] = clk
    #  the same screen on player 2's worlds: the law is the code's, not the pass's -- checked at 8 phases
    same = {}
    for p1 in ('4', '2', '3'):
        s2 = states_along(p1, ['A'])
        same[p1] = [[p, seg(s2['F723'], 0xF748, p), tabs['screen'][p // STEP]] for p in ph[::8]]
    out['screen_p2_same'] = same
    #  THE ANSWER'S EXITS AND THE BUILDER, BY PATH.  The code is above $8000, but every CALL, RET,
    #  PUSH and POP touches the stack at $61xx -- CONTENDED -- so each moves with the phase: each
    #  segment measured at 64 phases from its own saved start, the mean charged (BB_MENU's
    #  'meanPathT'), the spread kept
    def state_at(p1, ans, stop_pc):
        h, m, r = rd(p1)
        fed(h, [chord(k) for k in ans], stop=(stop_pc,), log=False, min_taken=len(ans))
        return h.save_state()
    EX = [('yes', None, 'OPQAY', 0xF801, 0xF6DB), ('build_p1', None, 'OPQAY', 0xF6DB, 0xF5C1),
          ('build_p2', '4', 'OPQAY', 0xF6DB, 0xF5C6), ('pre_plain', None, 'ABCDN', 0xF801, 0xF7A7),
          ('pre_r1', None, 'ABCDR', 0xF801, 0xF7A7), ('pre_r2', '4', 'ABCDR', 0xF801, 0xF7A7),
          ('call_ret', None, 'ABCDN', 0xF7A7, 0xF7AA), ('call_fail', '4', 'ABCDR', 0xF7A7, 0xF7AA),
          ('call_pass', '4', 'OOOPR', 0xF7A7, 0xF7AA), ('out_pass', '4', 'OOOPR', 0xF7A7, 0xF6B5)]
    exits = {}
    for name, p1, ans, a0, a1 in EX:
        s0 = state_at(p1, list(ans), a0)
        xs = [seg(s0, a1, p) for p in ph]
        exits[name] = {'mean': sum(xs) / len(xs), 'min': min(xs), 'max': max(xs), 'by_phase': xs}
    out['exits'] = exits
    #  PLAYER 2'S PAINT AFTER PLAYER 1'S KEYBOARD ($F671 = $31): the gate drops '1. KEYBOARD' AND the
    #  header, as the paint's skip counter meets 0 twice (H-a's bug, kept) -- by phase, as H-b's
    h, m, r = rd(None)
    fed(h, [['O'], ['P'], ['Q'], ['A'], ['Y']], stop=(0xF5E7,), log=False)
    keys(h, [])
    run_to(h, (0xF5F8,), False)
    if m[0xF671] != 0x31:
        raise Fail('$F671 is not $31 at player 2\'s paint')
    paint_at = h.save_state()

    def t_paint(p):
        h2 = Harness(contended=True)
        h2.load_state(paint_at)
        t0 = at_phase(h2, p)
        run_to(h2, (0xF664,), False)
        return h2.sim.registers[T] - t0
    law('paint_keyboard', t_paint)
    #  ...and the chars it prints: the skip gate's two drops
    h2 = Harness(contended=True)
    h2.load_state(paint_at)
    d = fed(h2, [], stop=(0xF664,), log=True)
    out['paint_keyboard_chars'] = sum(1 for p, a, v in d['wl'] if p in (0xF88A, 0xF88D) and 0x4000 <= a < 0x5B00) // 16
    out['by_phase'] = {'n': N_PH, 'step': STEP, 'tables': tabs, 'held_out': ho}
    print('timing: screen %d..%d, loop %d..%d, prompts %s' % (
        min(tabs['screen']), max(tabs['screen']), min(tabs['loop']), max(tabs['loop']),
        [(min(tabs['prompt%d' % i]), max(tabs['prompt%d' % i])) for i in range(4)]))
    print('        click+echo %s' % [(round(c['mean'], 1), c['min'], c['max']) for c in clk])
    print('        paint after KEYBOARD %d..%d, %d chars' % (
        min(tabs['paint_keyboard']), max(tabs['paint_keyboard']), out['paint_keyboard_chars']))
    print('        exits %s' % ' '.join('%s %.2f (%d..%d)' % (k, v['mean'], v['min'], v['max']) for k, v in exits.items()))
    print('        p2 screen same: %s' % all(a == b for rows in same.values() for p, a, b in rows))
    return out


# ------------------------------------------------------------------ the frames
REDEF_LABELS = {0xF723: 'redefine', 0xF7AA: 'redefine', 0xF801: 'prompt'}
for _a in CALL_READ:
    REDEF_LABELS[_a] = 'menu'


class RNat(Nat):
    """ctrlmenu's natural run, the redefine screen's stages labelled: 'redefine' (the screen and
       the loop's), 'menu' from each CALL $F7B3, 'prompt' from the read's return to the next read
       or the builder's RET; the answers and the cheat's bytes sampled with the rest.  $F801 is
       'menu' when the read returns to the menu's test ($F667) and 'prompt' when it returns into
       the redefine screen -- told apart by the return address under the PUSHed AF."""

    def run(self, max_frames, stops=(0xF5C6,), until=None):
        r, m = self.r, self.m
        base = dict(cm.LABEL_AT)
        base.update(REDEF_LABELS)

        class Lab(dict):
            def get(self_, pc, d=None):
                if pc == 0xF801:
                    sp = r[cm.SP]
                    ret = m[(sp + 2) & 0xFFFF] | (m[(sp + 3) & 0xFFFF] << 8)
                    return 'menu' if ret == 0xF667 else 'prompt'
                return dict.get(self_, pc, d)
        keep = cm.LABEL_AT
        cm.LABEL_AT = Lab(base)
        try:
            return Nat.run(self, max_frames, stops=stops)
        finally:
            cm.LABEL_AT = keep

    def sample(self):
        m = self.m
        row = Nat.sample(self)
        return row + [[m[a] for a in range(0xF983, 0xF988)], m[0xF6A3], m[0xFA3F], m[0xF829]]


SCRIPTS = {
    'kb_p1': [(8, []), (2, ['1']), (12, []), (2, ['O']), (8, []), (2, ['P']), (8, []), (2, ['Q']), (8, []),
              (2, ['A']), (8, []), (2, ['Y']), (16, []), (2, ['4']), (12, [])],
    'kb_loop': [(8, []), (2, ['1']), (12, []), (2, ['A']), (8, []), (2, ['B']), (8, []), (2, ['C']), (8, []),
                (2, ['D']), (8, []), (2, ['N']), (12, []), (2, ['E']), (8, []), (2, ['F']), (8, []), (2, ['G']),
                (8, []), (2, ['H']), (8, []), (2, ['Y']), (16, []), (2, ['1']), (8, []), (2, ['3']), (12, [])],
    'kb_p2_cheat': [(8, []), (2, ['4']), (16, []), (2, ['1']), (12, []), (2, ['O']), (8, []), (2, ['O']),
                    (8, []), (2, ['O']), (8, []), (2, ['P']), (8, []), (2, ['R']), (12, []), (2, ['A']), (8, []),
                    (2, ['B']), (8, []), (2, ['C']), (8, []), (2, ['D']), (8, []), (2, ['Y']), (12, [])],
    'kb_specials': [(8, []), (2, ['1']), (12, []), (2, ['SPACE']), (8, []), (2, ['ENTER']), (8, []),
                    (2, ['SYM', 'X']), (8, []), (2, ['CAPS', 'R']), (8, []), (2, ['Y']), (16, []), (2, ['2']),
                    (12, [])],
    'kb_held': [(8, []), (8, ['1']), (4, []), (3, ['O']), (1, []), (1, ['P']), (10, []), (2, ['A', 'B']),
                (2, ['Q']), (8, []), (2, ['CAPS', 'SYM']), (2, ['A']), (8, []), (6, ['Y']), (16, []),
                (2, ['4']), (12, []), (2, ['Z']), (8, []), (2, ['X']), (8, []), (2, ['C']), (8, []), (2, ['V']),
                (8, []), (2, ['Y']), (16, []), (2, ['4']), (12, [])],
}


def frames_drive(script):
    h, m, r = world('boot')
    seq = expand(script)
    nat = RNat(h, seq, label='open', pass_=1)
    why = nat.run(len(seq) + 1)
    nb0 = nat.nb - nat.frame * FRAME_T
    return {'stop': why, 'rows': nat.rows, 'nested': nat.n_nested, 'deferred': nat.n_deferred,
            'clicks': [[t - nb0, v] for t, p, port, v in OUTS[nat.out0:] if port == 0xFE and click_out(p)],
            'outs': [[t - nb0, p, v] for t, p, port, v in OUTS[nat.out0:] if port == 0xFE and not click_out(p)],
            'end': vars_of(m)}


def phase_frames():
    h, m, r = world('boot')
    out = {'boot_phase': r[T] % FRAME_T, 'scripts': {}}
    for name, script in SCRIPTS.items():
        d = frames_drive(script)
        d['script'] = [[n, k] for n, k in script]
        out['scripts'][name] = d
        labs = []
        for row in d['rows']:
            if not labs or labs[-1][0] != row[1]:
                labs.append([row[1], row[0]])
        print('frames %-12s stop %-8s %d frames, %d click OUTs; %s' % (
            name, d['stop'], len(d['rows']), len(d['clicks']), ' '.join('%s@%d' % (a, b) for a, b in labs)))
    return out


# ------------------------------------------------------------------ main
PHASES = ['screen', 'timing', 'frames']


def capture():
    out = {'meta': {'tool': 'tools/redefine.py', 'no_rom_bytes': True,
                    'note': 'screen writes as (address, value) for the CLS and the rainbow, (address, code, '
                            'source row) for the printer; key NAMES, counts and T'}}
    for p in PHASES:
        out[p] = globals()['phase_' + p]()
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new = json.loads(json.dumps(capture()))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd in PHASES:
        globals()['phase_' + cmd]()
    return 0


if __name__ == '__main__':
    sys.exit(main())
