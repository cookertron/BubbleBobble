"""M7.97 (measurement) -- THE GIANT-ITEM SPAWN $A84D, RUN BY RUN, UNCONTENDED.

$A84D has two entries on the machine:
  $8F26 CALL $A84D   the level clear's one-shot ($8F1A LD A,($FECC) / OR A / JR z / LD C,A / XOR A /
                     LD ($FECC),A / LD A,C): A = the giant mailbox -- 1 the giant DIAMOND ($88F9, the candy
                     cane), 3 the giant FRUIT ($88FD, the red cane); returns to $8F29 (the countdown)
  $A9F9 JP z,$A84D   the boss tick's spawn with A = 4 (a TAIL JUMP: it returns to $A9ED's caller)
Its body (Zilog T): DEC A 4 / LD ($A85C),A 13 / LD A,14 7 / LD ($A8DB),A 13 / LD A,3 7 / LD ($A839),A 13 /
LD A,n 7 -- n IS $A85C, the operand it has just written -- / LD C,A 4 / ADD A,A 4 x4 / LD L,A 4 / LD H,0 7 /
LD DE,$A890 10 / ADD HL,DE 11 / LD ($A8FD),HL 16 / LD A,C 4 / LD HL,$5B00 10 / OR A 4  = HEAD 150, then
  c = 0     JR z taken 12 / LD ($A8C2),HL 16 / RET 10                                     DIA   38 -> 188
  c = 2     JR z 7 / LD HL,$C080 10 / CP 2 7 / JR z taken 12 / LD ($A8C2),HL 16 / RET 10    FRUIT 62 -> 212
  other     JR z 7 / LD HL 10 / CP 2 7 / JR z 7 / LD HL,$FE02 10 / LD ($A8C2),HL 16 / RET 10 OTHER 67 -> 217
(asserted against EVERY run, natural and forced: 'model').

'natural': every $A84D run in every 48K saved state of aa60cost's list, FRAMES frames, interrupts on,
ab38cost's key script -- T, own, the entry's A and return address, the frame it ran in, its writes
(address, value) and its reads (the seed: only the return address its RET pops -- the operand $A85C that
$A85B reads is written at $A84E first, so the routine reads no input but A), 'irq' the interrupts accepted inside (bracketed out).
'mailbox': the saved states whose ($FECC) is non-zero at load, with ($A839) -- the arms the clear consumes.
'forced': $A84D called from round1_48 with A poked (every value the routine separates, the eight-bit wrap
of the table walk, A = 0), interrupts off, returning to $8F29 -- the arms no natural run takes.
'through': round1_48 with ($FECC) := 1 or 3 and bit 7 of every walked enemy +7 cleared (the round CLEARED
with the mailbox set), no keys, and the overlap pair $A98F/$A990 poked to its DECAYED `00 00` -- round1_48
holds `00 69`, mid-decay (it reaches `00 00` 429 frames into round 1 and stays: $AA9E skips a zero), and the
giant's collide then runs the intermediate opcode pair: NOP / LD L,C, and $A969 RETurns into $8A00 and the
machine crashes at frame 91 (MEASURED, box 1); the port models the two endpoints only (bossAxis): the clear's spawn (its T and writes) and then ($A839), ($A8DB) at every
frame boundary for THROUGH frames after it, every $A824 entry that ran the body (frame, the row before its INC),
($A82D) at the spawn -- the once-a-frame operand that decides whether the giant ticks in the clear's own frame
($8EF9 has just zeroed ($8DBD)) -- and the same byte in build/boot.pkl, the machine right after the load;
'zero': [the frame ($A839) went to 0, the PC that wrote it, the frame of the last $A824 entry before it] -- the
round advance's $9855 clear walk; when the last entry is a frame EARLIER the advancing pass STRADDLED the
interrupt ($A824 ran before it, $8E3A's countdown after it), which an atomic pass cannot do (TRAPS #90).
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/giantspawn.py [measure] [--jobs N]   (-> build/giantspawn_fixture.json, N <= 6)
        python tools/giantspawn.py verify [--jobs N]      (re-measure, compare, say MATCH)
"""
import sys, json, time
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import T, PC, IFF, SP, A as RA
import aa60cost as AA
import ab38cost as B
import cost8fa5 as G

FIXTURE = 'build/giantspawn_fixture.json'
FRAMES = G.FRAMES
THROUGH = 400
ENTRY = 0xA84D
OPS = {0xA85B: (0xA85C,)}          # $A85B LD A,n -- its operand is STATE (written at $A84E first)
MODEL = dict(HEAD=150, DIA=38, FRUIT=62, OTHER=67)
FORCED_A = [1, 3, 4, 2, 5, 0, 0x11, 0x13, 0x80, 0xFF]


def M(a):
    c = (a - 1) & 0xFF
    return MODEL['HEAD'] + (MODEL['DIA'] if c == 0 else MODEL['FRUIT'] if c == 2 else MODEL['OTHER'])


def row(x, a, ret, frame, name):
    rw = G.row_base(name, x)
    rw.update({'A': a, 'ret': '%04X' % ret, 'frame': frame, 'model': M(a)})
    return rw


def natural(name, frames=FRAMES):
    h, rm = G.machine(name, OPS)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t0 = r[T]
    t_end = t0 + frames * fd
    ki, nextk = 0, r[T]
    tr = G.Tracker(ENTRY)
    meta = []
    while r[T] < t_end or tr.cur is not None:
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
        if tr.cur is None and tr.isr is None and p == ENTRY:
            sp = r[SP]
            ret = raw[sp] | raw[(sp + 1) & 0xFFFF] << 8
            meta.append((r[RA], ret, (r[T] - t0) // fd))
            tr.open(r, rm, ret)
        tr.step(r, op, raw, rm, h)
    return [row(x, *m, name) for x, m in zip(tr.done, meta)]


def forced(a):
    h, rm = G.machine('round1_48', OPS)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    r[IFF] = 0
    r[RA] = a
    back = 0x8F29
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = back & 0xFF, back >> 8
    r[SP] = sp; r[PC] = ENTRY
    tr = G.Tracker(ENTRY)
    tr.open(r, rm, back)
    for _ in range(1000):
        tr.step(r, op, raw, rm, h)
        if tr.isr is None and tr.cur is not None:
            tr.close_frames(r, rm)
        if tr.cur is None:
            break
    else:
        raise AssertionError('$A84D: no return')
    return row(tr.done[0], a, back, 0, 'a%02x' % a)


def through(box):
    """round1_48, the round cleared with ($FECC) = box: the spawn, then the giant frame by frame.  Its own
    loop (the clear's world runs ISRs the Tracker's bracketing does not expect); the spawn is bracketed by
    its entry and the RET to the address it found on the stack at the same SP, and asserted interrupt-free"""
    h, rm = G.machine('round1_48', OPS)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    n = (raw[0xAA57] - 2) & 0xFF or 256
    for i in range(n):
        a = (0xFD9B + 10 * i) & 0xFFFF
        raw[a] &= 0x7F
    raw[0xFECC] = box
    raw[0xA98F] = raw[0xA990] = 0                     # the overlap pair DECAYED (see the docstring)
    fd, ia = h.frame_duration, h.int_active
    h.ports.release_all()
    spawn, run, a82d, zero, last_entry = None, None, None, None, None
    frame, samples, bodies = 0, [], []
    lastf = r[T] // fd
    t0 = r[T]
    t_stop = None
    while t_stop is None or r[T] < t_stop:
        p = r[PC]
        assert not (AA.GLO <= p < AA.GHI), 'ENTERED THE GUARDED RANGE'
        if p == ENTRY:
            assert run is None and spawn is None, 'a second spawn'
            sp = r[SP]
            ret = raw[sp] | raw[(sp + 1) & 0xFFFF] << 8
            run = {'A': r[RA], 'ret': ret, 'sp': sp, 't': r[T], 'seed': [], 'post': {}, 'cnt': {}}
            a82d = raw[0xA82D]                           # $A824's once-a-frame operand at the spawn
            rm.seen = set(); rm.rec = run['seed']; rm.wr = run['post']; rm.stk = sp
            t_stop = (r[T] // fd + THROUGH + 1) * fd
            frame = 0
        if spawn is not None and p == 0xA838:
            bodies.append([frame, raw[0xA839]])          # the row BEFORE $A83A INC A / the store
        if spawn is not None and p == 0xA824 and zero is None:
            last_entry = frame                           # the last $A824 entry before the giant is gone
        if raw[p] == 0x76:
            assert run is None, 'HALT inside the spawn'
            h._fast_halt()
        else:
            o = raw[p]
            op[o]()
            if run is not None and G.COND[o]:
                c = run['cnt'].setdefault(p, [0, 0])
                c[1 if r[PC] == B._fall(raw, p) else 0] += 1
            if run is not None and r[PC] == run['ret'] and r[SP] == (run['sp'] + 2) & 0xFFFF:
                rm.rec = None
                x = {'T': r[T] - run['t'], 'own': r[T] - run['t'], 'sig': G.sig(run['cnt']), 'irq': 0,
                     'kids': [], 'seed': run['seed'], 'post': run['post']}
                spawn = row(x, run['A'], run['ret'], 0, 'through%d' % box)
                run = None
            if r[IFF] and r[T] % fd < ia:
                if h.sim.accept_interrupt(r, rm, p):
                    assert run is None, 'an interrupt inside the spawn'
        if spawn is not None and zero is None and raw[0xA839] == 0:
            zero = [frame, '%04X' % p, last_entry]       # who zeroed the row, and when
        f = r[T] // fd
        if f != lastf:
            lastf = f
            if spawn is not None or run is not None:
                frame += 1
                samples.append([raw[0xA839], raw[0xA8DB]])
        assert t_stop is not None or r[T] - t0 < 60 * fd, 'no spawn in 60 frames'
    return {'box': box, 'slots': n, 'a82d': a82d, 'zero': zero, 'boot_a82d': boot_a82d(), 'spawn': spawn, 'samples': samples,
            'bodies': bodies}


def boot_a82d():
    """$A82D -- $A824's once-a-frame operand -- in build/boot.pkl, the machine right after the tape's load"""
    h, rm = G.machine('boot', {})
    return rm.m[0xA82D]


def mailbox(name):
    h, rm = G.machine(name, OPS)
    return [name, rm.m[0xFECC], rm.m[0xA839]]


def job(j):
    k, v = j
    if k == 'n':
        return natural(v)
    if k == 'f':
        return forced(v)
    if k == 't':
        return through(v)
    return mailbox(v)


def measure(jobs):
    work = ([('m', s) for s in AA.STATES] + [('f', a) for a in FORCED_A] + [('t', 1), ('t', 3)] +
            [('n', s) for s in AA.STATES])
    with Pool(jobs) as pool:
        res = pool.map(job, work)
    mb = [x for (k, _), x in zip(work, res) if k == 'm']
    fo = [x for (k, _), x in zip(work, res) if k == 'f']
    th = [x for (k, _), x in zip(work, res) if k == 't']
    nat = [x for (k, _), xs in zip(work, res) if k == 'n' for x in xs]
    bad = [[x['state'], x['A'], x['T'], x['model']] for x in nat + fo + [t['spawn'] for t in th]
           if x['own'] != x['T'] or x['T'] != x['model'] or x['kids']]
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'through_frames': THROUGH,
            'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES, 'states': AA.STATES, 'MODEL': MODEL,
            'mailbox': [m for m in mb if m[1] or m[2]],
            'natural': nat, 'forced': fo, 'through': th,
            'model': {'bad': bad, 'checked': len(nat) + len(fo) + len(th)}}


def report(F):
    print('mailbox states:', F['mailbox'])
    print('natural runs %d, forced %d, through %d; model bad %d of %d' % (
        len(F['natural']), len(F['forced']), len(F['through']), len(F['model']['bad']), F['model']['checked']))
    for x in F['natural']:
        print('  NAT %-12s A %d ret %s frame %d T %d irq %d post %s' % (x['state'], x['A'], x['ret'], x['frame'],
                                                                     x['T'], x['irq'], x.get('post')))
    for x in F['forced']:
        print('  FRC %-6s T %d post %s' % (x['state'], x['T'], x['post']))
    for t in F['through']:
        print('  THR box %d slots %d spawn T %d ret %s; bodies %s' % (t['box'], t['slots'], t['spawn']['T'],
                                                                     t['spawn']['ret'], t['bodies'][:24]))
        print('      samples', t['samples'][:24])


def main():
    args = sys.argv[1:]
    t0 = time.time()
    F = json.loads(json.dumps(measure(G.jobs_arg(args))))
    rc = G.finish(F, FIXTURE, args, report)
    print('%.0f s' % (time.time() - t0))
    sys.exit(rc)


if __name__ == '__main__':
    main()
