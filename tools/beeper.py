# -*- coding: utf-8 -*-
"""THE 48K BEEPER LAYER -- every OUT ($FE) the 48K game makes that the port did not emit
(or emitted at the wrong time), measured in the harness.  One oracle for the sound
increment; build/beeper_fixture.json (test-only, ship:false).

EVERY `OUT ($FE)` IN THE GAME'S CODE (static census over round1_48, boot, title and
afterctrl48, instruction boundaries confirmed by back-decoding; $D000..$D2FF masked):
  $8C4E  $8C28's tail (the reveal)       XOR A / OUT        this increment
  $8CB4  $8CB1 the collect chirp         XOR $30 / OUT      this increment
  $8FD8/$8FDE  the jump tone             M7.15 (T-exact)
  $8FF9  the pause, LD A,4 / OUT         this increment
  $9003  the pause release, XOR A / OUT  this increment
  $906F/$9081/$908F  the HURRY UP! train M7.19 -- re-timed here
  $960E  the cold start, XOR A / OUT     border only: the speaker is LOW at load
  $A0B0  the storm tick, XOR A / OUT     this increment
  $A0E0  the painter's head, OUT with A  this increment (storm flash + strike; $A110's
                                          umbrella flash, which the port does not run)
  $ACAF  the blow click                  M7.44
  $B791/$B79E  the pop click             M7.45
  front end (the control select, NOT BUILT): $F6B5, $F716, $F7E7 and the ROM BEEPER
  sweep $F7D7..$F7E5.  $5BD1 is loader residue.  $970C $9791 $979F $9962 $9981 are the
  operand bytes of LD ($FED3),A / LD HL,$FED3 / LD A,($FED3) -- not instructions.

PHASES (every edge is [T offset, the FULL port byte]; T is stamped at the start of the
OUT instruction, as sfx_trace.py and jumpsfx.py stamp it):
  chirp      $8CB1 called directly, UNCONTENDED, C swept over nine values -- the site
             loads $28, the others make the 8-bit SLA and the B = 0 DJNZ reachable
  site       $881D (LD C,$28 / CALL $8CB1 / $8822 LD A,($872C) / OR A / RET z), both
             contention settings, and the contended chirp at eight frame phases
  natural    a REAL collect in play, interrupts ON: pop-kill N1's keys to ISR 299, then
             RIGHT held (itemage.py's drive) -- the chirp's 40 OUTs and every ISR that
             lands between two of them
  storm      $A09A with the edge detector primed, ($FECF) = v for v = 0..255: every OUT
             (T, PC, value), the cost, the PRNG words the flashes draw -- uncontended,
             plus the contended cost of each tick class at eight frame phases
  reveal     $8C28 called directly on two worlds: where its OUT lands and what it costs
  pause      a natural pause: SYM held until the spin, CAPS to release
  hurry      $9037 on hurry.py's 'ready' world, UNCONTENDED -- the arithmetic the
             contended fixture (hurry_fixture.speaker) carries jitter on
  census     every OUT ($FE) by executing PC over natural play (round1_48, 1,500 frames
             of walk/jump/blow) and over the load path (afterctrl48 -> the title -> '1')
  menuclick  the control select's key click $F7D4..$F7E7 from `title`, with interrupts
             held OFF -- the UNINTERRUPTED shape: FORTY calls of the ROM BEEPER, not one.
             On the machine the menu runs with IFF 1 (the ROM's RST $38 re-enables them;
             bb.test.js M7.53 row (p)), so a frame interrupt can land between two BEEPER
             calls -- on 2 of 8 frame phases, +1,205 T (M7.53's recon) -- which this phase
             does not record.  Recorded for front-end group 3; the ROM is executed in the
             harness and NO ROM BYTE is stored, only T and levels.

GUARDED: every run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/beeper.py capture   -> build/beeper_fixture.json
        python tools/beeper.py verify    re-run and diff against the fixture
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import Harness, PC, T, SP
import portconfig as pc
import sfxcensus
from keyprobe import press

FIXTURE = 'build/beeper_fixture.json'
GUARD = set(range(0xD000, 0xD300))
BRANCH_BYTE = 0x8DC4
FRAME_T = 69888
ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
PHASES = [k * (FRAME_T // 8) for k in range(8)]


class Fail(Exception):
    pass


def new(state='round1_48', contended=False):
    sfxcensus.install_hook()                           # BEFORE the Harness: the simulator binds the tracer at construction
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    if state not in ('title', 'boot', 'afterctrl48') and h.memobj.m[BRANCH_BYTE] != 0xC9:
        raise Fail('%s: $8DC4 is not $C9 -- not the 48K branch (TRAPS #28)' % state)
    return h, h.memobj.m


def run_until(h, targets, limit=10 ** 8, interrupts=False, predicate=None, stride=64):
    tg = set(targets) | GUARD
    why, n = h.run_until(tg, limit=limit, interrupts=interrupts, predicate=predicate, stride=stride)
    if h.regs[PC] in GUARD:
        raise Fail('PC entered the guard at $%04X' % h.regs[PC])
    return why


def call(h, addr, regs=None, limit=10 ** 8):
    """harness.call with the $D000..$D2FF guard in the target set; interrupts OFF"""
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    for k, v in (regs or {}).items():
        if k in ('HL', 'DE', 'BC', 'IX', 'IY'):
            hi, lo = {'HL': (harness.H, harness.L), 'DE': (harness.D, harness.E),
                      'BC': (harness.B, harness.C), 'IX': (harness.IXh, harness.IXl),
                      'IY': (harness.IYh, harness.IYl)}[k]
            r[hi], r[lo] = v >> 8, v & 0xFF
        else:
            r[harness.U.REGISTERS[k]] = v
    r[PC] = addr
    t0 = r[T]
    sfxcensus.LOG.clear()
    why = run_until(h, h.SENTINELS, limit=limit)
    if why != 'target':
        raise Fail('no return from $%04X' % addr)
    outs = [[t - t0, p, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    return h.SENTINELS.index(r[PC]), r[T] - t0, outs


# ------------------------------------------------------------------ the chirp
CHIRP_C = [0x28, 0x01, 0x02, 0x05, 0x7F, 0x80, 0x81, 0xFF, 0x00]


def phase_chirp():
    rows = []
    for c in CHIRP_C:
        h, m = new()
        ex, cost, outs = call(h, 0x8CB1, {'C': c})
        assert all(o[1] == 0x8CB4 for o in outs)
        rows.append(dict(C=c, exit=ex, cost=cost, edges=[[o[0], o[2]] for o in outs]))
        print('chirp C=$%02X  %3d OUTs  cost %8d T  first %s last %s'
              % (c, len(outs), cost, outs[0][:1] + outs[0][2:], outs[-1][:1] + outs[-1][2:]))
    return rows


def phase_site():
    out = {}
    for cont in (False, True):
        h, m = new(contended=cont)
        m[0x872C] = 0                                  # the FRUIT pass: $8826 RET z
        ex, cost, outs = call(h, 0x881D)
        out['contended' if cont else 'exact'] = dict(exit=ex, cost=cost, edges=[[o[0], o[2]] for o in outs],
                                                     pcs=sorted(set('%04X' % o[1] for o in outs)))
        print('site $881D contended=%s: %d OUTs, first at %d, cost %d' % (cont, len(outs), outs[0][0], cost))
    # the contended chirp at eight frame phases: the drift contention adds, per edge
    exact = out['exact']['edges']
    drift = []
    for ph in PHASES:
        h, m = new(contended=True)
        m[0x872C] = 0
        h.regs[T] = (h.regs[T] // FRAME_T) * FRAME_T + ph
        ex, cost, outs = call(h, 0x881D)
        d = [o[0] - e[0] for o, e in zip(outs, exact)]
        drift.append(dict(phase=ph, cost=cost, min_drift=min(d), max_drift=max(d), last_drift=d[-1],
                          levels_same=[o[2] for o in outs] == [e[1] for e in exact]))
    out['phases'] = drift
    print('site contended over 8 phases: drift %s, costs %s' % ([r['max_drift'] for r in drift],
                                                                [r['cost'] for r in drift]))
    return out


def phase_natural():
    """itemage.py's drive, with every OUT ($FE) and every ISR's entry/exit T recorded"""
    import popkill as PK
    sfxcensus.install_hook()                           # before PK.Run builds its Harness
    run = PK.Run('round1_48')
    h, m = run.h, run.m
    run.run_to(PK.ISR_IN)
    sfxcensus.LOG.clear()
    isrs = []
    found = None
    for i in range(1000):
        keys, kemp = PK.keys_n1(i) if i <= 299 else (['8'], 0)
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        h.ports.kempston = kemp
        t_in = h.regs[T]
        run.in_isr = True
        run.run_to(PK.ISR_OUT)
        h.step(1)
        run.in_isr = False
        t_out = h.regs[T]
        isrs.append((i, t_in, t_out))
        run.run_to(PK.ISR_IN)                          # the main loop after ISR i
        ch = [x for x in sfxcensus.LOG if x[1] == 0x8CB4]
        if ch and found is None:
            found = i
        if found is not None and i >= found + 2:
            break
    fe = [(t, p, v) for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    ch = [x for x in fe if x[1] == 0x8CB4]
    t0 = ch[0][0]
    inside = [(i, a - t0, b - t0) for i, a, b in isrs if ch[0][0] < a < ch[-1][0]]
    others = [[t - t0, '%04X' % p, v] for t, p, v in fe if p != 0x8CB4 and ch[0][0] - FRAME_T < t < ch[-1][0] + FRAME_T]
    edges = [[t - t0, v] for t, p, v in ch]
    gaps = [edges[k + 1][0] - edges[k][0] for k in range(len(edges) - 1)]
    print('natural collect after ISR %d: %d chirp OUTs, span %d T, ISRs inside %s, other OUTs %s'
          % (found, len(ch), edges[-1][0], inside, others))
    return dict(after_isr=found, edges=edges, gaps=gaps, isrs_inside=[list(x) for x in inside],
                other_outs=others, score=list(m[0xFFE5:0xFFE9]))


# ------------------------------------------------------------------ the storm
def storm_world(m, v):
    m[0xFECE] = 0                                      # the flood not armed (it wins)
    m[0xFECF] = v
    m[0xA09E] = m[0x8DBD] ^ 0x01                       # $A09D CP n: n is $A09E -- a CHANGE


def phase_storm():
    ticks = []
    for v in range(256):
        h, m = new()
        storm_world(m, v)
        # a DIFFERENT generator word per tick, so the seven flash ticks draw seven different
        # four-ink sequences ($FE85 is a bijection on 16 bits: any word is on a cycle)
        w = (0x2A5B + 0x9E37 * v) & 0xFFFF
        m[0xFE86], m[0xFE87] = w & 0xFF, w >> 8
        prng = [m[0xFE86], m[0xFE87]]
        ex, cost, outs = call(h, 0xA09A)
        ticks.append(dict(v=v, exit=ex, cost=cost, prng=prng, after=m[0xFECF],
                          outs=[[o[0], '%04X' % o[1], o[2]] for o in outs]))
    # classes: what the tick does with the counter AFTER the INC
    def cls(v):
        a = (v + 1) & 0xFF
        if v == 0:
            return 'idle'
        if a == 0:
            return 'wrap'
        if a >= 0xFD:
            return 'strike'
        if a >= 0xF0:
            return 'payload' if (a & 0x1F) else 'payload'
        return 'flash' if (a & 0x1F) == 0 else 'plain'
    for t in ticks:
        t['cls'] = cls(t['v'])
    # the contended cost of one tick of each class at eight frame phases
    reps = {'plain': 0x05, 'flash': 0x1F, 'payload': 0xF3, 'strike': 0xFD, 'wrap': 0xFF, 'idle': 0x00}
    cont = {}
    for name, v in reps.items():
        costs = []
        for ph in PHASES:
            h, m = new(contended=True)
            storm_world(m, v)
            h.regs[T] = (h.regs[T] // FRAME_T) * FRAME_T + ph
            ex, cost, outs = call(h, 0xA09A)
            costs.append(cost)
        cont[name] = costs
    by = {}
    for t in ticks:
        by.setdefault(t['cls'], []).append(t)
    for k, rows in sorted(by.items()):
        cs = sorted(set(r['cost'] for r in rows))
        print('storm %-8s %3d ticks  exact cost %s  OUTs/tick %s  contended %s'
              % (k, len(rows), cs if len(cs) < 6 else (cs[0], '..', cs[-1]),
                 sorted(set(len(r['outs']) for r in rows)), cont.get(k)))
    for v in (0x1F, 0xEF, 0xF0, 0xFC, 0xFD, 0xFE, 0xFF):
        t = ticks[v]
        print('  v=$%02X  cost %d  outs %s' % (v, t['cost'], t['outs']))
    return dict(ticks=ticks, contended=cont)


def phase_reveal():
    out = []
    for st in ('round1_48', 'r20_48'):
        for cont in (False, True):
            h, m = new(st, contended=cont)
            ex, cost, outs = call(h, 0x8C28)
            out.append(dict(state=st, contended=cont, exit=ex, cost=cost,
                            outs=[[o[0], '%04X' % o[1], o[2]] for o in outs]))
            print('reveal %s contended=%s: cost %d, outs %s' % (st, cont, cost, out[-1]['outs']))
    return out


# ------------------------------------------------------------------ the pause
def run_frames(h, n, interrupts=True):
    end = h.regs[T] + n * FRAME_T
    run_until(h, (), interrupts=interrupts, predicate=lambda hh: hh.regs[T] >= end, stride=16)


def phase_pause():
    h, m = new(contended=True)
    sfxcensus.LOG.clear()
    t0 = h.regs[T]
    run_frames(h, 3)
    h.ports.release_all()
    press(h.ports, 'SYM')
    why = run_until(h, (0x8FFB,), interrupts=True, limit=5 * 10 ** 6, stride=1)
    t_spin = h.regs[T]
    h.ports.release_all()
    run_until(h, (), interrupts=True, predicate=lambda hh: hh.regs[T] >= t_spin + 5 * FRAME_T, stride=16)
    in_spin = 0x8FFB <= h.regs[PC] <= 0x9000
    press(h.ports, 'CAPS')
    run_until(h, (0x9005,), interrupts=True, limit=5 * 10 ** 6, stride=1)
    t_rel = h.regs[T]
    h.ports.release_all()
    run_frames(h, 3)
    fe = [[t - t0, '%04X' % p, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    print('pause: spin reached (%s) at %d, still in the spin after 5 frames: %s, released at %d; OUTs %s'
          % (why, t_spin - t0, in_spin, t_rel - t0, fe))
    # ...and each OUT's offset EXACTLY, uncontended: $8FE7 entered with SYM held (the OUT
    # from the routine's entry), then CAPS held from the spin's head $8FFB (the OUT from it)
    h, m = new(contended=False)
    press(h.ports, 'SYM')
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        m[sp] = s & 0xFF
        m[sp + 1] = s >> 8
    r[SP] = sp
    r[PC] = 0x8FE7
    t1 = r[T]
    sfxcensus.LOG.clear()
    run_until(h, (0x8FFB,), limit=10 ** 6, stride=1)
    gate = [[t - t1, '%04X' % p, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    h.ports.release_all()
    press(h.ports, 'CAPS')
    t2 = r[T]
    sfxcensus.LOG.clear()
    run_until(h, (0x9005,), limit=10 ** 6, stride=1)
    rel = [[t - t2, '%04X' % p, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    print('pause exact: gate OUT %s from $8FE7, release OUT %s from $8FFB' % (gate, rel))
    return dict(t_spin=t_spin - t0, in_spin=in_spin, t_release=t_rel - t0, outs=fe,
                exact=dict(gate=gate, release=rel))


# ------------------------------------------------------------------ the hurry
def phase_hurry():
    import hurry as HU
    sfxcensus.install_hook()                           # before the Harness is built
    out = {}
    for cont in (False, True):
        h = Harness(contended=cont)
        h.load_state_file(pc.state_path(HU.STATE))
        m = h.memobj.m
        HU.ready(m)
        ex, cost, outs = call(h, HU.TRIG)
        out['contended' if cont else 'exact'] = dict(cost=cost, outs=[[o[0], '%04X' % o[1], o[2]] for o in outs])
        lv = [(o[2] >> 4) & 1 for o in outs]
        tr = [[outs[k][0], lv[k]] for k in range(len(outs)) if k == 0 or lv[k] != lv[k - 1]]
        out['contended' if cont else 'exact']['transitions'] = tr
        print('hurry contended=%s: cost %d, %d OUTs, transitions %s' % (cont, cost, len(outs), tr))
    return out


# ------------------------------------------------------------------ the census
def census_run(state, script, contended=True):
    h, m = new(state, contended=contended)
    sfxcensus.LOG.clear()
    for keys, frames in script:
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        run_frames(h, frames)
    tally = {'_end': {'round': m[0x8609], 'p1_in_play': int(bool(m[0xFD87] & 0x80)), 'pc': '%04X' % h.regs[PC]}}
    for t, p, port, v in sfxcensus.LOG:
        if (port & 0xFF) != 0xFE:
            continue
        e = tally.setdefault('%04X' % p, {'n': 0, 'values': []})
        e['n'] += 1
        if v not in e['values']:
            e['values'].append(v)
    return tally


OUT_PATS = {b'\xD3\xFE': 'OUT ($FE),A',
            b'\xED\x79': 'OUT (C),A',
            b'\xED\x41': 'OUT (C),B',
            b'\xED\x49': 'OUT (C),C',
            b'\xED\x51': 'OUT (C),D',
            b'\xED\x59': 'OUT (C),E',
            b'\xED\x61': 'OUT (C),H',
            b'\xED\x69': 'OUT (C),L',
            b'\xED\x71': 'OUT (C),0',
            b'\xED\xA3': 'OUTI',
            b'\xED\xB3': 'OTIR',
            b'\xED\xAB': 'OUTD',
            b'\xED\xBB': 'OTDR'}


def phase_sites():
    """the STATIC census: every OUT opcode pattern in RAM ($4000..$FFFF, $D000..$D2FF masked)
    of four states, with the number of start offsets in the 12 bytes before it from which a
    linear decode lands EXACTLY on it -- an instruction boundary shows 11-13, an operand byte
    1-2 (LD ($FED3),A is 32 D3 FE).  Addresses and decoded RAM only; no ROM byte is read."""
    import z80dis.z80 as z
    out = {}
    for st in ('round1_48', 'title', 'boot', 'afterctrl48'):
        h, m = new(st)
        mem = bytes(m)
        for pat, name in OUT_PATS.items():
            p = 0x4000
            while True:
                p = mem.find(pat, p)
                if p < 0:
                    break
                if p in GUARD or (p + 1) in GUARD:
                    p += 1
                    continue
                starts = 0
                for s0 in range(p - 12, p + 1):
                    a = s0
                    while a < p:
                        d = z.decode(mem[a:a + 4], a)
                        a += d.len if d.len else 1
                    starts += (a == p)
                key = '%04X' % p
                e = out.setdefault(key, {'op': name, 'starts': starts, 'states': []})
                e['starts'] = min(e['starts'], starts)
                e['states'].append(st)
                p += 1
    for k in sorted(out):
        print('site %s %-12s starts %2d  %s' % (k, out[k]['op'], out[k]['starts'], ','.join(out[k]['states'])))
    return out


def natural_run(h, until, limit_frames, isr_log):
    """run with interrupts ON, recording every ISR entry/exit T, until `until(h)`"""
    t_end = h.regs[T] + limit_frames * FRAME_T
    while h.regs[T] < t_end:
        why = run_until(h, (ISR_IN,), interrupts=True, limit=10 ** 7,
                        predicate=lambda hh: until(hh) or hh.regs[T] >= t_end, stride=16)
        if why != 'target':
            return
        t_in = h.regs[T]
        run_until(h, (ISR_OUT,), interrupts=True, limit=10 ** 7, stride=1)
        h.step(1)
        isr_log.append((t_in, h.regs[T]))


def phase_stormrun():
    """a WHOLE storm in play, interrupts ON: round1_48 armed ($FECF := 1, the flood off),
    run until the tick after the wrap -- every OUT and every ISR"""
    h, m = new(contended=True)
    m[0xFECE] = 0
    m[0xFECF] = 1
    sfxcensus.LOG.clear()
    t0 = h.regs[T]
    isrs = []
    seen = {'armed': True, 'wrapped': None}
    def until(hh):
        if seen['wrapped'] is None and hh.memobj.m[0xFECF] == 0:
            seen['wrapped'] = hh.regs[T]
        return seen["wrapped"] is not None and hh.regs[T] >= seen["wrapped"] + 8 * FRAME_T
    natural_run(h, until, 600, isrs)
    fe = [[t - t0, '%04X' % p, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    by = {}
    for t, p, v in fe:
        e = by.setdefault(p, {'n': 0, 'values': []})
        e['n'] += 1
        if v not in e['values']:
            e['values'].append(v)
    ticks = sum(1 for o in fe if o[1] == 'A0B0')
    wrap = (seen['wrapped'] - t0) if seen['wrapped'] is not None else None
    print('storm run: %d ticks, wrapped after %s T (%.1f frames), %d ISRs, OUT sites %s'
          % (ticks, wrap, (wrap or 0) / FRAME_T, len(isrs), by))
    return dict(ticks=ticks, wrap_T=wrap, isrs=len(isrs), sites=by,
                strike=[o for o in fe if o[1] == 'A0E0' and o[2] >= 0xFD],
                outs=len(fe))


def phase_hurryrun():
    """the HURRY UP! train in play, interrupts ON: hurry.py's ready world on round1_48 run
    until the train's last OUT -- the ISRs that land inside it (both gates closed) and the
    seven transitions on the machine's own clock"""
    import hurry as HU
    h, m = new(HU.STATE, contended=True)
    HU.ready(m)
    sfxcensus.LOG.clear()
    t0 = h.regs[T]
    isrs = []
    def until(hh):
        return sum(1 for x in sfxcensus.LOG if x[1] == 0x908F) >= 120
    natural_run(h, until, 200, isrs)
    fe = [(t - t0, p, v) for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    lv = [(v >> 4) & 1 for _, _, v in fe]
    tr = [[fe[k][0], lv[k]] for k in range(len(fe)) if k == 0 or lv[k] != lv[k - 1]]
    first = tr[0][0]
    inside = [[a - t0, b - t0] for a, b in isrs if first <= a - t0 <= tr[-1][0]]
    print('hurry run: %d OUTs, transitions (from the first) %s, %d ISRs inside, their costs %s'
          % (len(fe), [[t - first, l] for t, l in tr], len(inside), sorted(set(b - a for a, b in inside))))
    return dict(transitions=tr, isrs_inside=inside, outs=len(fe))


def phase_census():
    play = []
    for k in range(25):                                # 1,500 frames: walk, jump, blow
        play += [(['8'], 20), (['0'], 4), (['7'], 2), (['5'], 20), (['7', '0'], 4), ([], 10)]
    a = census_run('round1_48', play)
    b = census_run('afterctrl48', [([], 400), (['1'], 40), ([], 400)])
    print('census round1_48 play: %s' % a)
    print('census afterctrl48 -> title -> play: %s' % b)
    return dict(play=a, load=b)


# ------------------------------------------------------------------ the menu click
def phase_menuclick():
    h, m = new('title')
    r = h.sim.registers
    r[PC] = 0xF7D4                                     # LD HL,$0320 (the PUSH AF before it is the caller's)
    t0 = r[T]
    sfxcensus.LOG.clear()
    calls = [0]
    while True:                                        # interrupts held OFF: the uninterrupted shape
        run_until(h, (0xF7DB, 0xF7E9), limit=10 ** 8, stride=1)
        if r[PC] == 0xF7E9:
            break
        calls[0] += 1
        h.step(1, interrupts=False)
    fe = [[t - t0, v] for t, p, port, v in sfxcensus.LOG if (port & 0xFF) == 0xFE]
    lv = [(v >> 4) & 1 for _, v in fe]
    tr = sum(1 for k in range(1, len(lv)) if lv[k] != lv[k - 1])
    print('menu click: %d BEEPER calls, %d OUTs, %d EAR transitions, span %d T (%.2f frames), last OUT value %d'
          % (calls[0], len(fe), tr, fe[-1][0] - fe[0][0], (fe[-1][0] - fe[0][0]) / FRAME_T, fe[-1][1]))
    return dict(calls=calls[0], outs=len(fe), transitions=tr, span=fe[-1][0] - fe[0][0],
                first=fe[0], last=fe[-1], cost=r[T] - t0,
                values=sorted(set(v for _, v in fe)))


def capture():
    out = dict(chirp=phase_chirp(), site=phase_site(), natural=phase_natural(),
               storm=phase_storm(), reveal=phase_reveal(), pause=phase_pause(),
               hurry=phase_hurry(), census=phase_census(), menuclick=phase_menuclick(),
               stormrun=phase_stormrun(), hurryrun=phase_hurryrun(), sites=phase_sites())
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new_ = json.loads(json.dumps(capture()))
        bad = [k for k in old if old[k] != new_.get(k)]
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd in ('chirp', 'site', 'natural', 'storm', 'reveal', 'pause', 'hurry', 'census', 'menuclick',
                 'stormrun', 'hurryrun', 'sites'):
        globals()['phase_' + cmd]()
    return 0


if __name__ == '__main__':
    sys.exit(main())
