"""M7.80 -- THE SCORE AWARD'S T ($80FA), RUN BY RUN, UNCONTENDED.

M7.74..M7.79 made every arm of the even pass $B62C exact; the one PROVISIONAL figure left inside it was
the award $80FA (BB_B62C_ARM.award, 3,525 -- blowcost's one forced 'bonus' figure), nested in the blow's
+$61 bonus and the pop's emit.  This oracle records every run of $80FA from all eleven `CALL $80FA` sites
on an UNCONTENDED machine, so a run's T is the sum of its instructions' own T: the entry tests (CP 3, the
player entity's BIT 7), the BCD add, the HUD redraw $816B (its digits through $8042 / $81B9 / $804F), the
MSB-first high-score compare, and on a copy the HIGH redraw.  Nothing nested is bracketed apart: every
callee is the score's own.

The glyphs come from the ROM charset on the machine ($8042: $3C00 + 8 * (digit + $30)) and from the
substitute font on the page.  The T does NOT depend on a glyph byte -- $804F copies eight rows whatever
they hold -- so no window is declared; but the VALUES are never stored (house rule 7): a run's ROM reads
keep their addresses ('rom'), and its display-bitmap writes are addresses only ('blind').

  T        the run, $80FA to its return to the caller
  caller   the CALL's address
  a        A at entry (the player index)
  seed     every byte the run READS before it writes it, as (address, value), the ROM excepted
  post     every byte the run WRITES, at its final value -- the stack, the ROM and the bitmap excepted
  rom      the addresses below $4000 the run read (values never stored)
  blind    the display-bitmap bytes the run wrote, as addresses only
  path     the run's PCs where control did not fall through, for a diagnostic

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through each
player's own key table; the rows keep up to KEEP runs of every distinct (caller, path, T).  A natural run
an interrupt lands inside is COUNTED ('irq') and not kept: its T would carry the ISR.  The paths no
natural run reaches are FORCED CALLS (declared below): $80FA called once from a saved state with A, the
three score fields, the pending amount and the guards poked, interrupts off.

Usage:  python tools/awardcost.py [--jobs N]          (-> build/awardcost_fixture.json)
        python tools/awardcost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP, A as RA
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/awardcost_fixture.json'
FRAMES = 300
KEEP = 2
ENTRY = 0x80FA
CALLERS = (0x7FF4, 0x7FF9, 0x8817, 0x8E6A, 0x8F6B, 0x8F74, 0x92B6, 0x9F0A, 0xA9CB, 0xB797, 0xBD6B)
BACK = 0xB79A                     # a forced call returns here (after the pop's CALL); never executed
GUARD = {0: 0xFD7D, 1: 0xFD87, 2: 0xFD91}


def _bcd(n):
    """n as four packed-BCD bytes, LSB first"""
    return [((n // 10 ** (2 * i + 1)) % 10) << 4 | (n // 10 ** (2 * i)) % 10 for i in range(4)]


def _f(base, n):
    return [(base + i, v) for i, v in enumerate(_bcd(n))]


def _w(a, high, p1, p2, amt, live=(1, 2)):
    """A = a; HIGH / P1 / P2 / the pending amount; the guards of the players in `live` set, others clear"""
    g = [(GUARD[k], 0x80 if k in live else 0x00) for k in GUARD]
    return a, _f(0xFFE1, high) + _f(0xFFE5, p1) + _f(0xFFE9, p2) + _f(0xFFED, amt) + g


# FORCED CALLS (declared): (name, state, A, pokes).  Scores in decimal, as the BCD the machine holds.
CALLS = [
    ('a3', 'round1_48') + _w(3, 5000, 100, 0, 10),                    # CP 3 / RET nc, the pending kept
    ('a255', 'round1_48') + _w(255, 5000, 100, 0, 10),
    ('out_p1', 'round1_48') + _w(1, 5000, 100, 0, 10, live=(2,)),     # the guard: discarded
    ('out_p2', 'round1_48') + _w(2, 5000, 100, 200, 10, live=(1,)),
    ('wrap_zero', 'round1_48') + _w(1, 5000, 99999990, 0, 10),        # wraps to 0: no digit drawn
    # the compare abandoned at each step (HIGH above the player at its MSB, then one byte lower...)
    ('ab0', 'round1_48') + _w(1, 10000000, 120, 0, 10),
    ('ab1', 'round1_48') + _w(1, 100000, 120, 0, 10),
    ('ab2', 'round1_48') + _w(1, 5000, 120, 0, 10),
    ('ab3', 'round1_48') + _w(1, 99, 20, 0, 10),
    # the copy at each step (HIGH below), and all four equal (the DJNZ runs out into the copy)
    ('cp0', 'round1_48') + _w(1, 5000, 10000000, 0, 1),
    ('cp1', 'round1_48') + _w(1, 5000, 100000, 0, 1),
    ('cp2', 'round1_48') + _w(1, 5000, 9000, 0, 10),
    ('cp3', 'round1_48') + _w(1, 30, 20, 0, 50),
    ('equal', 'round1_48') + _w(1, 5010, 5000, 0, 10),
    # every digit count 1..8 on P2 (abandoned at the MSB: HIGH 99,999,999), zeros inside drawn
    ('d1', 'round1_48') + _w(2, 99999999, 0, 0, 7),
    ('d2', 'round1_48') + _w(2, 99999999, 0, 10, 20),
    ('d3', 'round1_48') + _w(2, 99999999, 0, 100, 5),
    ('d4', 'round1_48') + _w(2, 99999999, 0, 1000, 0),
    ('d5', 'round1_48') + _w(2, 99999999, 0, 10000, 3),
    ('d6', 'round1_48') + _w(2, 99999999, 0, 100000, 0),
    ('d7', 'round1_48') + _w(2, 99999999, 0, 1000000, 1),
    ('d8', 'round1_48') + _w(2, 99999998, 0, 10203040, 0),
    # A = 0, the HIGH field's own: its guard $FD7D, compared with itself (equal), redrawn twice
    ('a0', 'round1_48') + _w(0, 5000, 100, 0, 10, live=(0, 1, 2)),
    ('a0_out', 'round1_48') + _w(0, 5000, 100, 0, 10),
    # the copy redraws a HIGH of eight digits
    ('cp_big', 'round1_48') + _w(2, 12345678, 0, 12345678, 1),
]


def _open(r, rm, sp, caller):
    cur = {'t0': r[T], 'sp': sp, 'seed': [], 'path': [], 'last': None, 'caller': caller, 'a': r[RA], 'irq': False}
    rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = sp
    return cur


def _step(r, op, raw, cur):
    p = r[PC]
    if cur['last'] is not None and p != cur['last']:
        cur['path'].append(p)
    op[raw[p]]()
    cur['last'] = B._fall(raw, p)


def _close(r, rm, cur):
    rm.rec = None
    cur['T'] = r[T] - cur['t0']
    return cur


def _machine(state):
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(state))
    rm = B.RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


def _done(r, cur):
    return r[SP] == (cur['sp'] + 2) & 0xFFFF


def call_run(name, state, a, pokes):
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for ad, v in pokes:
        raw[ad] = v
    r[IFF] = 0
    r[RA] = a
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    cur = _open(r, rm, sp, 0xB797)
    for _ in range(200000):
        if _done(r, cur):
            assert r[PC] == BACK, name + ': returned to $%04X' % r[PC]
            break
        _step(r, op, raw, cur)
    else:
        raise AssertionError(name + ': no return')
    return _close(r, rm, cur)


def run(name, frames=FRAMES):
    h, rm = _machine(name)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    runs, irq, cur, prev = [], 0, None, 0
    while r[T] < t_end:
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and _done(r, cur):
            assert p == (cur['caller'] + 3) & 0xFFFF, 'returned to $%04X' % p
            x = _close(r, rm, cur)
            if x['irq']: irq += 1
            else: runs.append(x)
            cur = None
        if cur is None and p == ENTRY:
            assert prev in CALLERS, '$80FA entered from $%04X' % prev
            cur = _open(r, rm, r[SP], prev)
        prev = p
        if raw[p] == 0x76:
            assert cur is None, 'HALT inside an award'
            h._fast_halt()
        else:
            if cur is not None:
                _step(r, op, raw, cur)
            else:
                op[raw[p]]()
            if r[IFF] and r[T] % fd < ia:
                if cur is not None:
                    cur['irq'] = True
                h.sim.accept_interrupt(r, rm, p)
    return runs, irq


def row(name, x):
    """NO ROM BYTE IS STORED (house rule 7): a read below $4000 keeps its ADDRESS only, and the display
    bitmap's writes -- the glyphs' rows, the ROM's bytes on the machine -- are addresses only"""
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if a < 0x5800]
    post = [(a, v) for a, v in post if a >= 0x5800]
    return {'state': name, 'T': x['T'], 'caller': x['caller'], 'a': x['a'],
            'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
            'post': ''.join('%04x%02x' % (a, v) for a, v in post),
            'rom': len(rom), 'blind': ' '.join('%04x' % a for a in blind),
            'path': ' '.join('%04x' % q for q in x['path'])}


CALLS_BY = {c[0]: c for c in CALLS}


def one(job):
    name, tag = job
    if tag:
        return [row(tag, call_run(*CALLS_BY[tag]))], 0
    runs, irq = run(name)
    return [row(name, x) for x in runs], irq


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    rows, per, npaths, ts, callers, irq = [], collections.Counter(), set(), [], collections.Counter(), 0
    for (s, tag), (rs, ni) in zip(work, res):
        irq += ni
        for x in rs:
            if not tag:
                npaths.add(x['path']); ts.append(x['T']); callers['%04x' % x['caller']] += 1
            key = (tag or '') + '%04x ' % x['caller'] + x['path'] + ' %d' % x['T']
            if per[key] < (1 if tag else KEEP):
                per[key] += 1
                rows.append(x)
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS],
            'runs': len(ts), 'irq': irq, 'paths': len(npaths), 'lo': min(ts), 'hi': max(ts),
            'callers': dict(callers), 'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 12
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), indent=0)
    print('runs %d (+%d irq)  paths %d  rows %d  T %d..%d  callers %s' % (F['runs'], F['irq'], F['paths'], len(F['rows']),
                                                                         F['lo'], F['hi'], F['callers']))
    for x in F['rows']:
        if x['state'] in CALLS_BY:
            print('  %-10s a %3d T %5d' % (x['state'], x['a'], x['T']))


if __name__ == '__main__':
    main()
