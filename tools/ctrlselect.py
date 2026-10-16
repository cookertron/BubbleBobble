# -*- coding: utf-8 -*-
"""M7.53 -- FRONT-END GROUP 3, SUB-INCREMENT H-a: THE CONTROL-SELECT SCREEN, $F5E7..$F663.

The cold-start front end calls $F5E7 twice, A = '1' then '2', and each call PAINTS a screen
before it reads a single key:

    $F5E7  LD ($F8C4),A / LD ($F932),A    the player digit into both headers    ctrlOpen()
    $F5ED  CALL $F709                     CLS + border: $97EB's twelve bytes,   feCls()
                                          then OUT ($FE),0 and BORDCR AND $F8
    $F5F0  XOR A / IN A,($FE) / CPL / AND $1F / JR nz   -- ALL KEYS UP (the frame layer's)
    $F5F8  LD IY,$5C3A                    the ROM's IY, for $FA71's channel     ctrlPaint()
    $F5FC  CALL $F82A                     the rainbow, 832 attribute stores     feRainbow()
    $F5FF  CALL $FA71                     "LICENSED BY FIREBIRD SOFTWARE", ROM  firebirdLine()
    $F602  LD A,$FE / LD ($F829),A        the skip counter
    $F607  seven CALL $F80B, a DEC ($F829) between the 2nd and 3rd         fePrint()
    $F65F  LD A,$C9 / LD ($F850),A        printing OFF: the menu does not echo
    $F664  CALL $F7B3                     <- the FIRST KEY READ: sub-increment H-b's

WHY THIS IS AN INCREMENT OF ITS OWN (the split, measured -- phase `split`):
  * the screen is COMPLETE before the first key read, and title.pkl -- a capture nobody drove --
    sits exactly on that boundary: driven from boot to $F664, the display file, the attribute
    file and every byte of $6200..$FFFF equal title.pkl's, and the only differences are LAST-K,
    FRAMES and the stack, the key read's own footprint;
  * on the menu the key read writes NO display byte ($F850 is $C9 from $F65F), while the
    redefine screen INTERLEAVES its prints and reads (prompts 2..5 are printed after reads
    1..4) -- so the redefine screen cannot be painted without the key read, and this one can;
  * $FAC3's footprint is FRAMES, the KSTATE set holding the last key, and the stack: disjoint
    from all of it.  Its duration is a LAW, not a number: $F5CC comes 994 T after the 256th
    frame boundary after $F5C9, so it is 256 x 69,888 + 994 - (the frame phase at $F5C9) --
    measured on two naturally driven paths and a sweep of the press phase (`split`).

WHAT IT LEAVES THAT THE PORT DOES NOT MODEL (phase `sysreads`, the M7.53 review's F1): 14 ROM
system variables, 2 bytes of the channel table ($5CBB/$5CBC, the 'S' channel's output address)
and 20 bytes of stack.  13 of those 36 are READ before the $96A5 relocation overwrites them --
FLAGS by the ROM keyboard scan behind $F7B8's RST $38, ten more by ROM code -- the channel
print of player 2's Firebird line reads every one of them, and on the P1 '1' path the key read
reaches FLAGS2 first -- and $61A5/$61A6 (CALL $F5E7's return address) by the game's own RET at
$F708 -- but NO game PC reads any of the 16, and their VALUES are dead: restored to boot's at
$F664, player 2's screen, all of $4000..$FFFF at $96B0, every register and T come out the same,
on both paths driven.  A poisoned P_FLAG is the control that the comparison can see a difference.

NO ROM BYTE IS RECORDED.  The ROM runs in the harness -- the Firebird line is the ROM's channel-2
printer (CALL $1601 / RST $10) and the double-height strings read the ROM charset through CHARS
($5C36) -- and the fixture carries only what they DID: which bytes they wrote and in what order,
the character CODE and source ROW each write came from (arithmetic on the source address), the
attribute values (the rainbow's immediates and the ROM's `old AND $3F`, measured over all 256
old values), reader PCs and access kinds, and BOOLEANS for "each display write stored the charset
row unmodified".  No display value written by the ROM or copied from the charset is stored.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver, never run).

Usage:  python tools/ctrlselect.py [capture|verify|<phase>]  -> build/ctrlselect_fixture.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, Mem, PC, T, SP, IFF, IM, A as RA, D as RD, E as RE, H as RH, L as RL
from harness import IXh, IXl
import portconfig as pc
from keyprobe import press

FIXTURE = 'build/ctrlselect_fixture.json'
GUARD = set(range(0xD000, 0xD300))
FRAME_T = 69888
CHARS = 0x5C36
BORDCR = 0x5C48
P_FLAG = 0x5C91
STR_LO, STR_HI = 0xF893, 0xF97B          # FOURTEEN '@'-terminated strings, contiguous: thirteen
                                         # printed, and $F8FD's second banner referenced by nothing
VARS_LO, VARS_HI = 0xF97B, 0xF988        # row base, counter, column, the echo cell, the answers
FB_AT, FB_END = 0xFA81, 0xFAA9           # the RST $10 stream, its '@' at $FAA8
SELF = (0xF829, 0xF850, 0xF671)          # the skip counter, the enable byte, $F670's CP operand
PAINT_PCS = {0xF712: 'cls', 0xF713: 'cls', 0xF831: 'rainbow', 0xF84C: 'rainbow',
             0xF84D: 'rainbow', 0x0BBC: 'firebird', 0x0C08: 'firebird',
             0xF88A: 'printer', 0xF88D: 'printer'}
CALLS = (0xF610, 0xF61C, 0xF62C, 0xF638, 0xF644, 0xF650, 0xF65C)   # the seven CALL $F80B
FAC3_OFFSET = 994                        # $F5CC after the 256th frame boundary after $F5C9
FRAMES_AT = (0x5C78, 0x5C79, 0x5C7A)


class Fail(Exception):
    pass


def world(state='boot', contended=True):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    #  the front end must be the TAPE's: boot and title are the only captures that hold it
    #  (it is inside the game's bitmap and colour shadows, destroyed within frames of play)
    if m[0xF80B] != 0x32 or m[0xF81F] != 0xFE or m[0xF820] != 0x40 or m[0xF82A] != 0x21:
        raise Fail('%s: the front end at $F80B/$F82A is not the tape\'s' % state)
    return h, m, h.sim.registers


def guard(h):
    if h.sim.registers[PC] in GUARD:
        raise Fail('PC entered the guard at $%04X' % h.sim.registers[PC])


def run_to(h, targets, ints, limit=20_000_000, predicate=None, stride=64):
    why, n = h.run_until(set(targets) | GUARD, limit=limit, interrupts=ints,
                         predicate=predicate, stride=stride)
    guard(h)
    return why, n


def keys(h, *names):
    h.ports.release_all()
    for k in names:
        press(h.ports, k)


def type_key(h, key, ints=True, runner=None):
    """a key read the natural way: held until $F7F9 (the release wait), then let go"""
    runner = runner or run_to
    keys(h, *key.split('+'))
    why, _ = runner(h, (0xF7F9,), ints, limit=5_000_000)
    if why != 'target':
        raise Fail('the key %s was never accepted (PC $%04X)' % (key, h.sim.registers[PC]))
    keys(h)
    why, _ = runner(h, (0xF802,), ints, limit=5_000_000)
    if why != 'target':
        raise Fail('no RET from $F7B3 after %s' % key)


def step_log(h, stop, ints, limit=2_000_000):
    """single-step to `stop` with the write watch on over $4000..$FFFF, tapping (HL, DE) at the
       printer's two stores and (IX, A, HL, the counter) at every $F80B entry.  Returns the
       write log [(pc, addr, value)], the store taps, the call taps, instructions, T."""
    r = h.sim.registers
    m = h.memobj.m
    stores, calls = [], []
    h.memobj.watch(0x4000, 0x10000)
    t0, n = r[T], 0
    while r[PC] != stop:
        p = r[PC]
        if p in GUARD:
            raise Fail('PC entered the guard at $%04X' % p)
        if p in (0xF88A, 0xF88D):
            stores.append(((r[RH] << 8) | r[RL], (r[RD] << 8) | r[RE]))
        elif p == 0xF80B:
            calls.append({'ix': (r[IXh] << 8) | r[IXl], 'a': r[RA], 'hl': (r[RH] << 8) | r[RL]})
        elif p == 0xF81A:                          # CP (HL): A = ($F671) - $31, (HL) = counter
            calls[-1]['counter'] = m[0xF829]
            calls[-1]['other'] = r[RA]
        h.step(1, interrupts=ints)
        n += 1
        if n > limit:
            raise Fail('never reached $%04X (PC $%04X)' % (stop, r[PC]))
    log = list(h.memobj.log)
    h.memobj.unwatch()
    return log, stores, calls, n, r[T] - t0


def charset_row(m, chars, code, row):
    return m[(chars + 8 * code + row) & 0xFFFF]


def screen_record(m, log, stores, calls, chars):
    """the ordered writes over $4000..$5AFF, by writer, with NO ROM-derived value kept:
       the CLS as a range, the rainbow and the Firebird attributes with their values, the
       Firebird display writes and the printer's writes as (address, code, source row)."""
    scr = [(p, a, v) for (p, a, v) in log if 0x4000 <= a < 0x5B00]
    order = []
    for p, a, v in scr:
        seg = PAINT_PCS.get(p)
        if seg is None:
            raise Fail('a screen write from an unexpected PC $%04X at $%04X' % (p, a))
        if order and order[-1][0] == seg:
            order[-1][1] += 1
        else:
            order.append([seg, 1])
    cls = [(a, v) for p, a, v in scr if PAINT_PCS[p] == 'cls']
    if [a for a, v in cls] != list(range(0x4000, 0x4000 + len(cls))) or any(v for a, v in cls):
        raise Fail('the CLS is not an ascending run of zeros')
    rainbow = [[a, v] for p, a, v in scr if PAINT_PCS[p] == 'rainbow']
    #  THE FIREBIRD LINE: (8 display, 1 attribute) x 32, and each display write the charset
    #  row of the stream's k-th printable code -- checked here, recorded only as a boolean
    fb = [(p, a, v) for p, a, v in scr if PAINT_PCS[p] == 'firebird']
    stream = [m[FB_AT + 7 + i] for i in range(32)]
    fb_disp, fb_attr, plain, inter = [], [], True, True
    for k in range(32):
        grp = fb[9 * k: 9 * k + 9]
        if len(grp) != 9 or any(q[0] != 0x0BBC for q in grp[:8]) or grp[8][0] != 0x0C08:
            inter = False
            break
        for row, (p, a, v) in enumerate(grp[:8]):
            col = a & 0x1F
            fb_disp.append([a, col, (a >> 8) & 7])
            if v != charset_row(m, chars, stream[col], (a >> 8) & 7):
                plain = False
        fb_attr.append([grp[8][1], grp[8][2]])
    #  THE PRINTER: each store paired with the (HL, DE) tapped before it
    pr = [(p, a, v) for p, a, v in scr if PAINT_PCS[p] == 'printer']
    if len(pr) != len(stores):
        raise Fail('printer stores %d against %d taps' % (len(pr), len(stores)))
    printer, doubled = [], True
    for i, ((p, a, v), (hl, de)) in enumerate(zip(pr, stores)):
        if hl != a:
            raise Fail('a printer tap at $%04X wrote $%04X' % (hl, a))
        off = (de - chars) & 0xFFFF
        printer.append([a, off // 8, off % 8])
        if v != m[de]:
            doubled = False
    #  every source row goes down TWICE (writes 2k and 2k+1 carry the same row)
    doubled = doubled and all(printer[2 * k][1:] == printer[2 * k + 1][1:]
                              for k in range(len(printer) // 2))
    return {'order': order, 'cls': [0x4000, len(cls)], 'rainbow': rainbow,
            'firebird': {'disp': fb_disp, 'attr': fb_attr, 'interleave_8d1a': inter,
                         'plain_store': plain, 'stream_codes': stream},
            'printer': printer, 'printer_doubled_plain': doubled,
            'calls': [[c['ix'], c['a'], c['hl'], c.get('counter'), c.get('other')] for c in calls]}


def vars_of(m):
    return {'F829': m[0xF829], 'F850': m[0xF850], 'F671': m[0xF671], 'F8C4': m[0xF8C4],
            'F932': m[0xF932], 'F97B_F987': list(m[VARS_LO:VARS_HI]),
            'BORDCR': m[BORDCR], 'CHARS': m[CHARS] | (m[CHARS + 1] << 8)}


def census(log):
    """every address written outside the two screen files, classified.  The port writes the
       game's own.  It does NOT model the rest: 14 ROM system variables plus 2 bytes of the
       channel table ($5CBB/$5CBC) -- 'sysvars' here -- and the stack.  Their VALUES are dead
       (phase `sysreads`), though the ROM reads some of them before the $96A5 relocation
       overwrites them, and the game's own RETs read the stack."""
    game, sysv, stack = set(), set(), set()
    bypc = {}
    for p, a, v in log:
        k = 'D' if a < 0x5800 else ('A' if a < 0x5B00 else 'O')
        bypc.setdefault(k, {})
        bypc[k]['%04X' % p] = bypc[k].get('%04X' % p, 0) + 1
        if a >= 0x5B00:
            if 0x5C00 <= a < 0x5CC0:
                (game if a == BORDCR else sysv).add(a)
            elif 0x6100 <= a < 0x6200:
                stack.add(a)
            else:
                game.add(a)
    return {'by_pc': bypc, 'game': sorted(game), 'sysvars': sorted(sysv),
            'stack': [min(stack), max(stack)] if stack else None, 'n_stack': len(stack)}


# ------------------------------------------------------------------ tape: what the port seeds
def phase_tape():
    img = open('build/image_tape.bin', 'rb').read()
    h, m, r = world('boot')
    strings, a = [], STR_LO
    while a < STR_HI:
        b = a
        while img[b] != 0x40:
            b += 1
        strings.append([a, img[a:b].decode('ascii')])
        a = b + 1
    if a != STR_HI:
        raise Fail('the strings do not end at $%04X' % STR_HI)
    ranges = [(STR_LO, STR_HI), (VARS_LO, VARS_HI), (FB_AT, FB_END)] + [(x, x + 1) for x in SELF]
    same = all(img[x] == m[x] for lo, hi in ranges for x in range(lo, hi))
    out = {'strings': strings, 'vars_f97b': list(img[VARS_LO:VARS_HI]),
           'firebird': list(img[FB_AT:FB_END]),
           'self': {'%04X' % x: img[x] for x in SELF},
           'boot_equals_tape': same,
           'boot_chars': m[CHARS] | (m[CHARS + 1] << 8), 'boot_bordcr': m[BORDCR]}
    print('tape: %d strings $%04X..$%04X, boot == tape at every seeded byte: %s, CHARS $%04X, '
          'BORDCR $%02X' % (len(strings), STR_LO, STR_HI - 1, same, out['boot_chars'], out['boot_bordcr']))
    for s in strings:
        print('   $%04X %r' % (s[0], s[1]))
    assert same, 'boot.pkl differs from the tape image at a seeded byte'
    assert out['firebird'][:7] == [0x10, 8, 0x11, 8, 0x16, 21, 0] and out['firebird'][-1] == 0x40
    return out


# ------------------------------------------------------------------ p1: the machine's own entry
def p1_times(phase=None):
    """($F5E7 -> $F5F0, $F5F8 -> $F664) T from boot, at boot.pkl's own frame phase or a given
       one -- the paint runs with IFF 0, so only ULA contention moves it"""
    h, m, r = world('boot')
    if phase is not None:
        r[T] = (r[T] // FRAME_T) * FRAME_T + phase
    run_to(h, (0xF5E7,), False, limit=100)
    t0 = r[T]
    run_to(h, (0xF5F0,), False, limit=5_000_000)
    t1 = r[T]
    run_to(h, (0xF5F8,), False, limit=10000)
    t2 = r[T]
    run_to(h, (0xF664,), False, limit=5_000_000)
    return t1 - t0, r[T] - t2


def phase_p1():
    out = {}
    for ints in (False, True):
        h, m, r = world('boot')
        chars = m[CHARS] | (m[CHARS + 1] << 8)
        entry_phase = r[T] % FRAME_T
        t0 = r[T]
        log0, _, _, n0, t_open = step_log(h, 0xF5F0, ints)       # $F5BC..$F5EF: ctrlOpen
        v_open = vars_of(m)
        cleared = all(m[x] == 0 for x in range(0x4000, 0x5B00))
        why, nw = run_to(h, (0xF5F8,), ints, limit=10000)        # the wait: no key is down
        t_wait = r[T] - t0 - t_open
        log1, stores, calls, n1, t_paint = step_log(h, 0xF664, ints)
        rec = screen_record(m, log0 + log1, stores, calls, chars)
        rec.update({'T_open': t_open, 'T_wait': t_wait, 'T_paint': t_paint, 'instr': n0 + nw + n1,
                    'iff_at_F664': r[IFF], 'cleared_at_F5F0': cleared,
                    'open_writes': sorted(set(a for p, a, v in log0 if a >= 0x5B00)),
                    'vars_at_F5F0': v_open, 'vars': vars_of(m), 'census': census(log0 + log1),
                    'entry_phase': entry_phase, 'snap': bytes(m[0x4000:0x10000])})
        out['on' if ints else 'off'] = rec
    off, on = out['off'], out['on']
    same = off['snap'] == on['snap'] and off['T_paint'] == on['T_paint'] and off['T_open'] == on['T_open']
    for k in ('off', 'on'):
        del out[k]['snap']
    rec = off
    rec['ints_on_identical'] = same
    #  ctrlOpen's and ctrlPaint's own spans, and how the loader's frame phase moves them
    t_o, t_p = p1_times()
    rec['T_F5E7_F5F0'] = t_o
    rec['phase_sweep'] = [[ph] + list(p1_times(ph)) for ph in range(0, FRAME_T, FRAME_T // 8)]
    print('p1: %d instructions, open %d T + wait %d T + paint %d T, IFF %d at $F664, ints on == off: %s'
          % (rec['instr'], rec['T_open'], rec['T_wait'], rec['T_paint'], rec['iff_at_F664'], same))
    print('    $F5E7->$F5F0 %d T, $F5F8->$F664 %d T at boot.pkl\'s phase %d; over eight phases %s'
          % (t_o, t_p, rec['entry_phase'], rec['phase_sweep']))
    print('    order %s' % rec['order'])
    print('    rainbow %d, firebird %d+%d (interleave %s, plain store %s), printer %d (doubled %s)'
          % (len(rec['rainbow']), len(rec['firebird']['disp']), len(rec['firebird']['attr']),
             rec['firebird']['interleave_8d1a'], rec['firebird']['plain_store'], len(rec['printer']),
             rec['printer_doubled_plain']))
    print('    calls %s' % ['$%04X a=%d $%04X ctr=$%02X' % (c[0], c[1], c[2], c[3]) for c in rec['calls']])
    print('    census: game %s' % ' '.join('%04X' % a for a in rec['census']['game']))
    print('            sysvars %s, stack %s (%d)' % (' '.join('%04X' % a for a in rec['census']['sysvars']),
                                                    rec['census']['stack'], rec['census']['n_stack']))
    assert same, 'interrupts ON changed the paint -- an interrupt was accepted in it'
    assert rec['iff_at_F664'] == 0
    #  $F5BC's LD A,'1' / CALL $F5E7 is 33 T, not 24: the CALL's push lands on contended RAM
    assert t_p == rec['T_paint'] and rec['T_open'] - t_o == 33
    assert rec['order'] == [['cls', 6912], ['rainbow', 832], ['firebird', 288], ['printer', 1888]]
    assert rec['firebird']['interleave_8d1a'] and rec['firebird']['plain_store']
    assert rec['printer_doubled_plain'] and rec['cleared_at_F5F0']
    assert [c[3] for c in rec['calls']] == [0xFF, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04]
    return {'p1': rec}


# ------------------------------------------------------------------ p2: after each P1 choice
P1_REDEFINE = ['Q', 'A', 'N', 'M', 'Y']
P2_REDEFINE = ['O', 'P', 'Z', 'X', 'Y']


def phase_p2():
    rows = []
    for p1 in ('2', '3', '4', '1'):
        h, m, r = world('title')              # parked in P1's menu read ($F7BA), the screen done
        chars = m[CHARS] | (m[CHARS + 1] << 8)
        type_key(h, p1)
        if p1 == '1':
            for k in P1_REDEFINE:
                why, _ = run_to(h, (0xF7B3,), True, limit=5_000_000)
                type_key(h, k)
        why, _ = run_to(h, (0xF5E7,), True, limit=5_000_000)
        if why != 'target' or r[RA] != 0x32:
            raise Fail('P2\'s $F5E7 not reached with A = \'2\'')
        entry = vars_of(m)
        iff_in = r[IFF]
        log0, _, _, n0, t_open = step_log(h, 0xF5F0, True)
        run_to(h, (0xF5F8,), True, limit=10000)
        log1, stores, calls, n1, t_paint = step_log(h, 0xF664, True)
        rec = screen_record(m, log0 + log1, stores, calls, chars)
        chars_printed = len(rec['printer']) // 16
        rows.append({'p1': p1, 'entry': entry, 'iff_at_F5E7': iff_in, 'T_open': t_open,
                     'T_paint': t_paint, 'chars': chars_printed, 'printer': rec['printer'],
                     'calls': rec['calls'], 'order': rec['order'],
                     'rainbow_as_p1': None, 'vars': vars_of(m)})
        rows[-1]['_rb'] = rec['rainbow']
        rows[-1]['_fb'] = rec['firebird']
        rows[-1]['_cls'] = rec['cls']
        print('p2 after P1=%s: $F671 $%02X, $F850 $%02X at entry, %d chars, counters %s, T open %d paint %d, IFF %d'
              % (p1, entry['F671'], entry['F850'], chars_printed,
                 ['%02X' % c[3] for c in rec['calls']], t_open, t_paint, iff_in))
    return rows


# ------------------------------------------------------------------ row 21: the transform
def phase_row21():
    """$FA71 over row 21 poisoned with ALL 256 attribute values (eight drives of 32), rows 20
       and 22 guarded; and the display row poisoned $FF, to see a STORE and not an OR.  All with
       the hand-over's permanent colours (ATTR-P, MASK-P, P-FLAG as boot.pkl holds them): the law
       is measured for those, and the stream's INK 8 / PAPER 8 act on top of them"""
    pairs, guarded, disp_ok, n_attr = [], True, True, 0
    for k in range(8):
        h, m, r = world('boot')
        run_to(h, (0xFA71,), False, limit=5_000_000)
        for col in range(32):
            m[0x5AA0 + col] = (k * 32 + col) & 0xFF
            m[0x5A80 + col] = 0xE1
            m[0x5AC0 + col] = 0xE2
            for row in range(8):
                m[0x50A0 + col + 0x100 * row] = 0xFF
        chars = m[CHARS] | (m[CHARS + 1] << 8)
        stream = [m[FB_AT + 7 + i] for i in range(32)]
        h.memobj.watch(0x4000, 0x5B00)
        run_to(h, (0xF602,), False, limit=5_000_000)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        n_attr += sum(1 for p, a, v in log if a >= 0x5800)
        for col in range(32):
            pairs.append([(k * 32 + col) & 0xFF, m[0x5AA0 + col]])
            if m[0x5A80 + col] != 0xE1 or m[0x5AC0 + col] != 0xE2:
                guarded = False
            for row in range(8):
                if m[0x50A0 + col + 0x100 * row] != charset_row(m, chars, stream[col], row):
                    disp_ok = False
    pairs.sort()
    law = all(new == old & 0x3F for old, new in pairs)
    #  ...and the ROM's print takes its glyphs from CHARS, as $F863 does: moved by $100 every
    #  character comes 32 codes on; off the eight-byte grid, rows straddle two cells
    moved = {}
    for base in (0x3D00, 0x3C01):
        h, m, r = world('boot')
        run_to(h, (0xFA71,), False, limit=5_000_000)
        m[CHARS], m[CHARS + 1] = base & 0xFF, base >> 8
        stream = [m[FB_AT + 7 + i] for i in range(32)]
        run_to(h, (0xF602,), False, limit=5_000_000)
        moved['%04X' % base] = all(m[0x50A0 + col + 0x100 * row] == m[(base + 8 * stream[col] + row) & 0xFFFF]
                                   for col in range(32) for row in range(8))
    print('row21: %d old values, new == old AND $3F for all: %s, rows 20/22 intact: %s, '
          'the $FF display row came back the bare glyphs: %s, %d attribute writes; CHARS moved: %s'
          % (len(pairs), law, guarded, disp_ok, n_attr, moved))
    assert len(pairs) == 256 and law and guarded and disp_ok and n_attr == 256 and all(moved.values())
    return {'pairs': pairs, 'law_and_3F': law, 'rows_20_22_intact': guarded,
            'store_not_or': disp_ok, 'attr_writes': n_attr, 'reads_chars': moved}


# ------------------------------------------------------------------ the printer, directly
def f80b(h, m, ix, a, hl):
    """$F80B at its own entry, single-stepped to a sentinel: the store taps give each store's
       source (DE) and the $F863 taps the code IX points at; only addresses and codes are kept"""
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = s & 0xFF
        m[sp + 1] = s >> 8
    r[SP] = sp
    r[IXh], r[IXl] = ix >> 8, ix & 0xFF
    r[RA] = a
    r[RH], r[RL] = hl >> 8, hl & 0xFF
    r[PC] = 0xF80B
    sents = set(h.SENTINELS)
    stores, codes = [], []
    h.memobj.watch(0x4000, 0x10000)
    n = 0
    while r[PC] not in sents:
        p = r[PC]
        if p in GUARD:
            raise Fail('PC entered the guard at $%04X' % p)
        if p in (0xF88A, 0xF88D):
            stores.append(((r[RH] << 8) | r[RL], (r[RD] << 8) | r[RE]))
        elif p == 0xF863:
            ixv = (r[IXh] << 8) | r[IXl]
            codes.append((m[ixv], m[CHARS] | (m[CHARS + 1] << 8)))
        h.step(1, interrupts=False)
        n += 1
        if n > 1_000_000:
            raise Fail('$F80B never returned')
    log = list(h.memobj.log)
    h.memobj.unwatch()
    scr = [x for p, x, v in log if 0x4000 <= x < 0x5B00]
    #  every store's source is CHARS + 8 x (the code at IX) + the source row, the row going down
    #  twice -- the machine's own arithmetic, checked here and kept as a boolean
    src_law = len(stores) == 16 * len(codes) and all(
        de == (codes[i // 16][1] + 8 * codes[i // 16][0] + (i % 16) // 2) & 0xFFFF
        for i, (hl_, de) in enumerate(stores))
    #  relative to the ROM set's own base: ON the grid when every store reads row (i % 16) // 2
    #  of some cell, OFF it when no store does
    rel_rows = [((de - 0x3C00) & 0xFFFF) % 8 == (i % 16) // 2 for i, (hl_, de) in enumerate(stores)]
    return {'disp': len(scr), 'first': scr[0] if scr else None, 'addrs': scr,
            'ix_after': (r[IXh] << 8) | r[IXl], 'F97F': m[0xF97F],
            'F97D': m[0xF97D] | (m[0xF97E] << 8), 'F829': m[0xF829],
            'F97B': m[0xF97B] | (m[0xF97C] << 8), 'n_chars': len(codes), 'src_law': src_law,
            'on_grid': bool(rel_rows) and all(rel_rows), 'off_grid': bool(rel_rows) and not any(rel_rows),
            'stores_rel3C00': [[hl_, ((de - 0x3C00) & 0xFFFF) // 8, ((de - 0x3C00) & 0xFFFF) % 8]
                               for hl_, de in stores],
            'written': sorted(set(x for p, x, v in log if x >= 0x5B00 and not (0x6100 <= x < 0x6200)))}


def phase_printer():
    rows = {}

    def fresh(enable=0x00, other=0x2A, counter=0x04, text=None, at=0xF400, chars=None):
        h, m, r = world('boot')
        m[0xF850], m[0xF671], m[0xF829] = enable, other, counter
        for x in range(0x4000, 0x5B00):
            m[x] = 0xAA
        if text is not None:
            for i, b in enumerate(text):
                m[at + i] = b
        if chars is not None:
            m[CHARS], m[CHARS + 1] = chars & 0xFF, chars >> 8
        return h, m
    #  the enable byte: $00 prints, $C9 prints NOTHING and still walks the string
    for en in (0x00, 0xC9):
        h, m = fresh(en)
        rows['enable_%02X' % en] = f80b(h, m, 0xF934, 9, 0x4800)
    #  the terminator is '@', and a NUL is a character like any other
    for name, text in (('AB', b'AB@'), ('A_NUL_B', b'A\x00B@'), ('AB_at_C', b'AB@C@'),
                       ('at_first', b'@AB@')):
        h, m = fresh(text=text)
        rows['term_' + name] = f80b(h, m, 0xF400, 3, 0x4020)
    #  the dead load: $F851's HL is overwritten by $F863 before it is used
    for cnt in (0x4000, 0x9999):
        h, m = fresh()
        m[0xF97D], m[0xF97E] = cnt & 0xFF, cnt >> 8
        rows['count_%04X' % cnt] = f80b(h, m, 0xF934, 9, 0x4800)
    #  the skip gate, from $F829 = counter: the INC comes FIRST, then CP (($F671) - $31)
    for other, counter in ((0x31, 0xFF), (0x31, 0xFE), (0x33, 0x01), (0x2A, 0xF8)):
        h, m = fresh(other=other, counter=counter)
        rows['skip_%02X_%02X' % (other, counter)] = f80b(h, m, 0xF934, 9, 0x4800)
    #  the SIXTEEN-bit column add: column 32 on the row base $50C0 reaches the attribute file
    h, m = fresh(text=b'  @')
    res = f80b(h, m, 0xF400, 32, 0x50C0)
    res['attr_touched'] = [x for x in range(0x5800, 0x5B00) if m[x] != 0xAA]
    rows['col32'] = res
    #  ...and the column add CARRIES INTO H: row base $50E0 + column $28 is $5108, where an
    #  eight-bit add (the in-game $802E's INC L) would stay on $50xx.  No string the game
    #  prints makes it carry (the widest is $50C0 + 33), so only a probe can tell them apart
    h, m = fresh(text=b'A@')
    rows['col_carry'] = f80b(h, m, 0xF400, 0x28, 0x50E0)
    #  CHARS moved (the review's F13): the source of EVERY store is CHARS + 8 x code + row, so a
    #  base $100 on reads 32 codes on, and one off the grid reads rows that straddle two cells
    for base in (0x3D00, 0x3C01):
        h, m = fresh(chars=base)
        rows['chars_%04X' % base] = f80b(h, m, 0xF934, 9, 0x4800)
    for k, v in rows.items():
        print('printer %-14s %s' % (k, {q: (('$%04X' % w) if isinstance(w, int) and w > 255 else w)
                                          for q, w in v.items()
                                          if q not in ('written', 'addrs', 'stores_rel3C00')}))
    assert rows['enable_C9']['disp'] == 0 and rows['enable_00']['disp'] == 176
    assert rows['term_A_NUL_B']['disp'] == 48 and rows['term_AB_at_C']['disp'] == 32
    assert rows['col32']['attr_touched'] == [0x5800, 0x5801]
    assert rows['col_carry']['first'] == 0x5108, rows['col_carry']
    assert all(v['src_law'] for v in rows.values())
    assert rows['chars_3D00']['disp'] == 176 and rows['chars_3C01']['disp'] == 176
    assert rows['chars_3D00']['on_grid']
    assert rows['chars_3C01']['off_grid'] and not rows['chars_3D00']['off_grid']
    return rows


# ------------------------------------------------------------------ $F709's BORDCR
def phase_cls():
    """$F718 LD A,(BORDCR) / AND $F8 / LD (BORDCR),A over values the load never holds -- boot's
       $07 comes back $00 under AND $F8, AND $F0, AND $38 or a plain store of 0 alike, so only a
       poisoned BORDCR tells them apart (TRAPS #44)"""
    rows = []
    for v in (0x07, 0xFF, 0x5A, 0xC3):
        h, m, r = world('boot')
        m[BORDCR] = v
        h.ports.record_writes = True
        run_to(h, (0xF5F0,), False, limit=5_000_000)
        outs = [(port & 0xFF, val) for t, port, val in h.ports.writes if (port & 0xFF) == 0xFE]
        rows.append([v, m[BORDCR], outs])
    print('cls: BORDCR in -> out %s, the OUTs to $FE %s' % (['$%02X->$%02X' % (a, b) for a, b, o in rows],
                                                          rows[0][2]))
    assert all(b == a & 0xF8 for a, b, o in rows)
    return {'bordcr': [[a, b] for a, b, o in rows], 'outs': rows[0][2]}


# ------------------------------------------------------------------ the release wait
def phase_release(frames=50):
    """ENTER held from the load (it is how LOAD "" ends): the CLS is done, then NOTHING is
       written while the key is down -- the wait sits between ctrlOpen() and ctrlPaint()"""
    h, m, r = world('boot')
    keys(h, 'ENTER')
    why, _ = run_to(h, (0xF5F0,), False, limit=5_000_000)
    t0 = r[T]
    h.memobj.watch(0x4000, 0x10000)
    end = t0 + frames * FRAME_T
    run_to(h, (0xF5F8,), False, limit=50_000_000, predicate=lambda hh: hh.regs[T] >= end, stride=64)
    held = list(h.memobj.log)
    h.memobj.unwatch()
    in_wait = 0xF5F0 <= r[PC] <= 0xF5F6
    zero = all(m[x] == 0 for x in range(0x4000, 0x5B00))
    keys(h)
    run_to(h, (0xF664,), False, limit=5_000_000)
    h2, m2, r2 = world('boot')
    run_to(h2, (0xF664,), False, limit=5_000_000)
    same = bytes(m[0x4000:0x10000]) == bytes(m2[0x4000:0x10000])
    print('release: ENTER held %d frames -- still in the wait %s, %d writes while held, screen all '
          'zero %s; released, the end state equals the unheld drive: %s'
          % (frames, in_wait, len(held), zero, same))
    assert in_wait and not held and zero and same
    return {'frames': frames, 'in_wait': in_wait, 'writes_while_held': len(held),
            'screen_zero_while_held': zero, 'end_state_same': same}


# ------------------------------------------------------------------ the split, measured
FAC3_PATHS = [('P1 4, P2 3', '4', None, '3', None, 0),
              ('P1 3, P2 1 (redefine O P Z X Y)', '3', None, '1', P2_REDEFINE, 0)]


def fac3_run(p1, r1, p2, r2, delay):
    """from title.pkl: P1's choice (and redefine), P2's first key read, `delay` T of looking at
       the menu, P2's choice (and redefine), then $F5C9 -> $F5CC with the write watch on"""
    h, m, r = world('title')
    type_key(h, p1)
    for k in (r1 or []):
        run_to(h, (0xF7B3,), True, limit=20_000_000)
        type_key(h, k)
    why, _ = run_to(h, (0xF7B3,), True, limit=20_000_000)
    if why != 'target':
        raise Fail('P2\'s key read not reached')
    if delay:
        end = r[T] + delay
        run_to(h, (), True, limit=10 ** 8, stride=1, predicate=lambda hh: hh.regs[T] >= end)
    type_key(h, p2)
    for k in (r2 or []):
        run_to(h, (0xF7B3,), True, limit=20_000_000)
        type_key(h, k)
    why, _ = run_to(h, (0xF5C9,), True, limit=50_000_000)
    if why != 'target':
        raise Fail('$F5C9 not reached (PC $%04X)' % r[PC])
    phase = r[T] % FRAME_T
    t0 = r[T]
    h.memobj.watch(0x4000, 0x10000)
    why, n = run_to(h, (0xF5CC,), True, limit=10 ** 8, stride=4096)
    w = sorted(set(x for p, x, v in h.memobj.log))
    h.memobj.unwatch()
    if why != 'target':
        raise Fail('$F5CC not reached')
    t = r[T] - t0
    other = [x for x in w if x < 0x6100 and x not in FRAMES_AT]
    stack = [x for x in w if x >= 0x6100]
    return {'A': r[RA], 'BC': h.bc(), 'T': t, 'instr': n, 'phase_at_F5C9': phase,
            'writes': [x for x in w if x < 0x6100], 'kstate': other,
            'stack': [min(stack), max(stack)] if stack else None,
            'law': t == 256 * FRAME_T + FAC3_OFFSET - phase}


def phase_split():
    #  (1) title.pkl IS the boundary: the driven $F664 against a capture nobody drove
    h, m, r = world('boot')
    run_to(h, (0xF664,), False, limit=5_000_000)
    hT, mT, rT = world('title')
    d_screen = sum(1 for x in range(0x4000, 0x5B00) if m[x] != mT[x])
    d_high = sum(1 for x in range(0x6200, 0x10000) if m[x] != mT[x])
    d_low = [x for x in range(0x5B00, 0x6200) if m[x] != mT[x]]
    sysv = sorted(x for x in d_low if x < 0x6100)
    stack = [x for x in d_low if x >= 0x6100]
    #  (2) the key read on the menu writes no display byte; (3) the redefine interleaves
    h, m, r = world('title')
    keys(h, '4')
    h.memobj.watch(0x4000, 0x10000)
    run_to(h, (0xF7F9,), True, limit=5_000_000)
    keys(h)
    run_to(h, (0xF667,), True, limit=5_000_000)
    menu_disp = sum(1 for p, x, v in h.memobj.log if 0x4000 <= x < 0x5B00)
    h.memobj.unwatch()
    h, m, r = world('title')
    type_key(h, '1')
    seq, script = [], list(P1_REDEFINE)
    while True:
        run_to(h, (0xF80B, 0xF7B3, 0xF5C1, 0xF709, 0xF82A), True, limit=5_000_000, stride=1)
        p = r[PC]
        seq.append('%04X' % p)
        if p == 0xF5C1:
            break
        if p == 0xF7B3:
            type_key(h, script.pop(0))
        else:
            h.step(1)
    #  (4) $FAC3 on two naturally driven paths, and the press phase swept on the first: the
    #  duration is a LAW of the frame phase at $F5C9, and the non-stack writes are FRAMES and
    #  the two countdown bytes of whichever KSTATE set holds the last key
    paths = []
    for name, p1, r1, p2, r2, d in FAC3_PATHS:
        o = fac3_run(p1, r1, p2, r2, d)
        o['name'] = name
        paths.append(o)
    sweep = []
    for k in range(8):
        o = fac3_run('4', None, '3', None, k * (FRAME_T // 8))
        sweep.append([k * (FRAME_T // 8), o['phase_at_F5C9'], o['T'], o['A'], o['BC'], o['law'],
                      o['kstate']])
    fr = [x[2] / FRAME_T for x in sweep] + [p['T'] / FRAME_T for p in paths]
    out = {'title_boundary': {'screen_diff': d_screen, 'ram_6200_diff': d_high,
                              'sysvars_diff': sysv, 'stack_diff': [min(stack), max(stack)] if stack else None},
           'menu_read_display_writes': menu_disp,
           'redefine_sequence': seq,
           'fac3': paths[0],
           'fac3_paths': paths,
           'fac3_sweep': sweep,
           'fac3_law': {'frame_T': FRAME_T, 'offset': FAC3_OFFSET, 'frames_min': round(min(fr), 3),
                        'frames_max': round(max(fr), 3)}}
    print('split: title.pkl vs the driven $F664 -- screen %d, $6200..$FFFF %d, sysvars %s, stack %s'
          % (d_screen, d_high, ['%04X' % x for x in sysv], out['title_boundary']['stack_diff']))
    print('       the key read on the menu: %d display writes; the redefine: %s' % (menu_disp, ' '.join(seq)))
    for p in paths:
        print('       $FAC3 on %-34s A=$%02X BC=$%04X %d T (%.3f fr) phase@$F5C9 %d law %s writes %s stack %s'
              % (p['name'], p['A'], p['BC'], p['T'], p['T'] / FRAME_T, p['phase_at_F5C9'], p['law'],
                 ' '.join('%04X' % x for x in p['writes']), p['stack']))
    for s in sweep:
        print('       sweep: press delay %5d -> phase %5d, %d T (%.3f fr), A=$%02X BC=$%04X, law %s, KSTATE %s'
              % (s[0], s[1], s[2], s[2] / FRAME_T, s[3], s[4], s[5], ' '.join('%04X' % x for x in s[6])))
    print('       frames %.3f..%.3f' % (out['fac3_law']['frames_min'], out['fac3_law']['frames_max']))
    assert d_screen == 0 and d_high == 0 and sysv == [0x5C08, 0x5C78, 0x5C79] and menu_disp == 0
    for o in paths + [{'A': s[3], 'BC': s[4], 'law': s[5], 'kstate': s[6]} for s in sweep]:
        assert o['A'] == 0x30 and o['BC'] == 0x075E and o['law']
        assert len(o['kstate']) == 2 and o['kstate'][0] in (0x5C00, 0x5C04) and o['kstate'][1] == o['kstate'][0] + 1
    assert paths[0]['kstate'] == [0x5C04, 0x5C05] and paths[1]['kstate'] == [0x5C00, 0x5C01]
    return out


# ------------------------------------------------------------------ what the port leaves out
class _Track:
    on = False
    pc = None
    watch = set()
    first = {}
    reads = {}


class TrackMem(Mem):
    """harness.Mem that records, for the addresses in _Track.watch, the kind of the FIRST access
       and every reading PC -- addresses and PCs only, never a value"""
    __slots__ = ()

    def __getitem__(self, i):
        if _Track.on and not isinstance(i, slice) and i in _Track.watch:
            _Track.first.setdefault(i, ('R', _Track.pc))
            d = _Track.reads.setdefault(i, {})
            d[_Track.pc] = d.get(_Track.pc, 0) + 1
        return self.m[i]

    def __setitem__(self, i, v):
        if _Track.on and not isinstance(i, slice) and i in _Track.watch:
            _Track.first.setdefault(i, ('W', _Track.pc))
        Mem.__setitem__(self, i, v)


def run_tracked(h, targets, ints, limit=200_000_000, **kw):
    """harness.run_until's loop, with _Track.pc set to each instruction's own PC (the interrupted
       PC for an acceptance) so every access is billed to the instruction that made it"""
    sim = h.sim
    regs = sim.registers
    opcodes = sim.opcodes
    mem = sim.memory
    fd, ia = h.frame_duration, h.int_active
    targets = set(targets) | GUARD
    n = 0
    while n < limit:
        p = regs[PC]
        if p in targets:
            guard(h)
            return 'target', n
        _Track.pc = p
        if ints and mem[p] == 0x76 and regs[IFF]:
            h._fast_halt()
            n += 1
            continue
        opcodes[mem[p]]()
        if ints and regs[IFF] and regs[T] % fd < ia:
            sim.accept_interrupt(regs, mem, p)
        n += 1
    return 'limit', n


SYSREAD_PATHS = [('43', '4', None, '3', None), ('12', '1', P1_REDEFINE, '2', None)]


def sys_drive(p1, r1, p2, r2, patch=None, track=False):
    """boot -> P1's $F664 (interrupts off, as the machine) -> P1's choice -> P2's pass to its
       $F664 (the screen kept) -> P2's choice -> $F5C9 -> $FAC3 -> $8CC3 -> $95F3 ... -> $96AE,
       the relocation's LDIR, and on to $96B0 when it is done"""
    h, m, r = world('boot')
    h.memobj.watch(0x4000, 0x10000)
    run_to(h, (0xF664,), False, limit=5_000_000)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    sysv = sorted(set(a for p, a, v in log if 0x5C00 <= a < 0x5CC0 and a != BORDCR))
    stack = sorted(set(a for p, a, v in log if 0x6100 <= a < 0x6200))
    runner = run_to
    if track:
        h.memobj.__class__ = TrackMem
        _Track.watch = set(sysv + stack)
        _Track.first, _Track.reads = {}, {}
        _Track.on = True
        runner = run_tracked
    if patch:
        patch(m)
    try:
        type_key(h, p1, runner=runner)
        for k in (r1 or []):
            runner(h, (0xF7B3,), True, limit=20_000_000)
            type_key(h, k, runner=runner)
        why, _ = runner(h, (0xF5E7,), True, limit=20_000_000)
        if why != 'target' or r[RA] != 0x32:
            raise Fail('P2\'s $F5E7 not reached')
        runner(h, (0xF664,), True, limit=20_000_000)
        p2screen = bytes(m[0x4000:0x5B00])
        type_key(h, p2, runner=runner)
        for k in (r2 or []):
            runner(h, (0xF7B3,), True, limit=20_000_000)
            type_key(h, k, runner=runner)
        why, _ = runner(h, (0x96AE,), True, limit=10 ** 8)
        if why != 'target':
            raise Fail('$96AE not reached (PC $%04X)' % r[PC])
    finally:
        _Track.on = False
        if track:
            h.memobj.__class__ = Mem
    #  the relocation: does $96AE overwrite every one of the 36?
    h.memobj.watch(0x5B00, 0x6200)
    run_to(h, (0x96B0,), True, limit=10_000)
    reloc = set(a for p, a, v in h.memobj.log if p == 0x96AE)
    h.memobj.unwatch()
    return {'sysv': sysv, 'stack': stack, 'p2screen': p2screen, 'ram': bytes(m[0x4000:0x10000]),
            'regs': list(r), 'reloc_covers': all(a in reloc for a in sysv + stack)}


def phase_sysreads():
    out = {'paths': {}}
    ref = {}
    for name, p1, r1, p2, r2 in SYSREAD_PATHS:
        d = sys_drive(p1, r1, p2, r2, track=True)
        first, reads = dict(_Track.first), {a: dict(v) for a, v in _Track.reads.items()}
        rec = {'sysvars': d['sysv'], 'stack': d['stack'], 'first': {}, 'rom_readers': {},
               'game_readers': {}, 'reloc_covers_all': d['reloc_covers']}
        for a in d['sysv'] + d['stack']:
            f = first.get(a)
            rec['first']['%04X' % a] = [f[0], f[1]] if f else None
            rd = reads.get(a, {})
            rec['rom_readers']['%04X' % a] = sorted(p for p in rd if p < 0x4000)
            rec['game_readers']['%04X' % a] = sorted(p for p in rd if p >= 0x4000)
        rec['read_first'] = sorted(a for a in d['sysv'] + d['stack']
                                   if rec['first']['%04X' % a] and rec['first']['%04X' % a][0] == 'R')
        rec['sysvars_read'] = sum(1 for a in d['sysv'] if reads.get(a))
        rec['sysvar_game_readers'] = sorted(set(p for a in d['sysv'] for p in rec['game_readers']['%04X' % a]))
        out['paths'][name] = rec
        #  the same path untracked: the reference for the un-write
        ref[name] = sys_drive(p1, r1, p2, r2)
        print('sysreads P1 %s P2 %s: %d sysvars, %d stack; read first %s; sysvars read %d of %d; game '
              'PCs reading a sysvar %s; the relocation covers all: %s'
              % (p1, p2, len(d['sysv']), len(d['stack']), ' '.join('%04X' % a for a in rec['read_first']),
                 rec['sysvars_read'], len(d['sysv']), rec['sysvar_game_readers'], d['reloc_covers']))
    #  the un-write: the 16 put back to boot's values at P1's $F664 -- nothing downstream moves
    hB, mB, rB = world('boot')
    boot_vals = {a: mB[a] for a in out['paths']['43']['sysvars']}

    def unwrite(m):
        for a, v in boot_vals.items():
            m[a] = v
    out['unwrite'] = {}
    for name, p1, r1, p2, r2 in SYSREAD_PATHS:
        alt = sys_drive(p1, r1, p2, r2, patch=unwrite)
        rf = ref[name]
        out['unwrite'][name] = {
            'p2_screen_diff': sum(1 for i in range(len(rf['p2screen'])) if rf['p2screen'][i] != alt['p2screen'][i]),
            'ram_diff_at_96B0': sum(1 for i in range(len(rf['ram'])) if rf['ram'][i] != alt['ram'][i]),
            'regs_differing': [i for i in range(len(rf['regs'])) if rf['regs'][i] != alt['regs'][i]]}
    #  the positive control: a poisoned P_FLAG DOES reach player 2's screen, so the comparison sees
    def poison(m):
        m[P_FLAG] = 0xFF
    alt = sys_drive('4', None, '3', None, patch=poison)
    rf = ref['43']
    out['control'] = {'poke': [P_FLAG, 0xFF],
                      'p2_screen_diff': sum(1 for i in range(len(rf['p2screen']))
                                            if rf['p2screen'][i] != alt['p2screen'][i])}
    print('sysreads: un-write %s; control P_FLAG $FF -> P2 screen differs in %d bytes'
          % (out['unwrite'], out['control']['p2_screen_diff']))
    for name, rec in out['paths'].items():
        assert len(rec['sysvars']) == 16 and len(rec['stack']) == 20 and rec['reloc_covers_all']
        assert rec['sysvar_game_readers'] == [] and rec['sysvars_read'] == 16
    for u in out['unwrite'].values():
        assert u['p2_screen_diff'] == 0 and u['ram_diff_at_96B0'] == 0 and u['regs_differing'] == []
    assert out['control']['p2_screen_diff'] > 0
    return out


def capture():
    out = {'meta': {'tool': 'tools/ctrlselect.py', 'no_rom_bytes': True,
                    'note': 'addresses, codes, source rows, attribute values, reader PCs and booleans only'}}
    out['tape'] = phase_tape()
    out.update(phase_p1())
    p2 = phase_p2()
    P1 = out['p1']
    for row in p2:
        row['rainbow_as_p1'] = row.pop('_rb') == P1['rainbow']
        fb = row.pop('_fb')
        cls = row.pop('_cls')
        #  the review's F8: the display VALUES too -- a plain store of the same stream codes in the
        #  same interleave -- not only the addresses
        row['firebird_as_p1'] = (fb['disp'] == P1['firebird']['disp'] and fb['attr'] == P1['firebird']['attr'] and
                                 fb['plain_store'] and fb['interleave_8d1a'] and
                                 fb['stream_codes'] == P1['firebird']['stream_codes'])
        row['cls_as_p1'] = cls == P1['cls']
        assert row['rainbow_as_p1'] and row['firebird_as_p1'] and row['cls_as_p1']
    out['p2'] = p2
    out['row21'] = phase_row21()
    out['printer'] = phase_printer()
    out['cls'] = phase_cls()
    out['release'] = phase_release()
    out['split'] = phase_split()
    out['sysreads'] = phase_sysreads()
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
    elif cmd in ('tape', 'p1', 'p2', 'row21', 'printer', 'cls', 'release', 'split', 'sysreads'):
        globals()['phase_' + cmd]()
    return 0


if __name__ == '__main__':
    sys.exit(main())
