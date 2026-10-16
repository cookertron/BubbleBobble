"""M7.115c: A LATER ROUND'S START FREE-RUNNING -- the real load (passacc's world and keys) with ($FECD) poked in play, so
$8D12 advances the round, and the machine recorded from the poke through the build, the HALT, the tail, the banner and
into the new round's play: R1Td's check for rounds >= 2.

THE WORLDS.  passacc's: boot.pkl's $F5BC, the control select, the title and round 1, keys at each ISR's end.  At the END
of the ISR labelled F (the boundary it was taken at -- where the keys go in; the engine's step(F) starts there) the
pokes go in: ($FECD) = n (the advance count), and optionally ($8609) (the round before the first advance) with
($FDDA) / ($FDE4) bit 7 set (lrstart's chunks: the warp refused).  Or (where 'pass') at the main line's $8D0C of the first
pass in frame F that begins within 96 T of the boundary: the interrupt then falls inside the $FECD pass, before $97F8.

RECORDED, from the poke to frame END:
  isrs    every ISR [label, its T from the acceptance to the return, its own contention delay, its acceptance phase]
  marks   the main line's $97F8 / $9887 / $9888 / $8D0C-after-$9888, per advance: [frame, phase]
  rounds  ($8609) at each advance's $9888
  e7e85   the frame the new round's play first runs $7E80's long path ($7E85..: contended code, not on the engine's
          pass program -- DECLARED, paMiss), or null
  r9811   past round 81, the lookahead's LD A,R at $9811: [frame, A & $7F] -- the engine draws it from BB_Rng (a
          declared substitute), so its gate feeds it this
  scr     at the end of the ISR labelled END, the CRC-32 of the attributes and of the bitmap

DEVELOPMENT AIDS (environment; scratchpad/m7115c/ output, never the fixture): LRFREE_PROG=765,767 dumps those ISRs' contended
accesses [plain offset, k, address, delay, PC]; LRFREE_SCR=1 the screen at the end; LRFREE_PASSES=1 every pass after the
last tail [frame, phase, plain T, delay] and LRFREE_PDUMP=1,3 those passes' accesses; LRFREE_STOP=k returns the harness at
the k-th $97F8 (for tools/lrstart.py's advance(): its per-segment marks).

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/lrfree.py [capture|verify] [--jobs N]  -> build/lrfree_fixture.json  (~1.5 min on 11 workers)
"""
import sys, os, json, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP, A
from skoolkit.cmiosimulator import DELAYS_48K
from passacc import SCRIPT

# the bitmap's CRC leaves out the ROM font's cells -- r1build's mask, 1P (the HUD text, the round number): the engine
# draws them with its own font (R1Tc's rule)
_RB = json.load(open('build/r1build_fixture.json', encoding='utf-8'))['programs']['1']['mask_b64']
_RB = __import__('base64').b64decode(_RB)
MASK = [_RB[i] << 8 | _RB[i + 1] for i in range(0, len(_RB), 2)]
# ...and the round number's TENS digit (round 1 has none): cell (2, 0), rows 1..7 as r1build masks the units' (2, 1)
MASK += [0x4040 + (r << 8) for r in range(1, 8)]

FIXTURE = 'build/lrfree_fixture.json'
# a development aid: LRFREE_PROG=765,767 dumps those ISRs' contended accesses [plain offset, k, address, delay, PC]
PASSES = [] if os.environ.get('LRFREE_PASSES') else None   # a development aid: every pass after the last tail
PDUMP = {int(x): [] for x in os.environ.get('LRFREE_PDUMP', '').split(',') if x}
STOP = int(os.environ.get('LRFREE_STOP', '0'))
PROG = {int(x): [] for x in os.environ.get('LRFREE_PROG', '').split(',') if x}
FD = 69888
TAIL_F = 60                    # frames of the new round's play recorded after the last advance's $8D0C
LATE = FD - 96                 # a pass whose $8D0C is this late meets the interrupt before $97F8 (the $FECD pass is 96 T)
# (tag, poke frame, ($FECD), ($8609) or None, where): round 2 from five phases of round 1's play; rounds 10 / 41 / 81
# poked; three advances back to back; 81 and the wrap past it -- poked at the END of the ISR labelled F; and two poked at
# the main line's $8D0C of the first pass in frame F that begins at or past LATE (passacc: 546 at 69,842, 744 at 69,829),
# so the interrupt falls inside the advance pass and $97F8 is entered after it
WORLDS = [
    ('p480', 480, 1, None, 'isr'), ('p560', 560, 1, None, 'isr'), ('p640', 640, 1, None, 'isr'),
    ('p700', 700, 1, None, 'isr'), ('p745', 745, 1, None, 'isr'),
    ('r10', 700, 1, 9, 'isr'), ('r41', 650, 1, 40, 'isr'), ('n3', 520, 3, None, 'isr'), ('r81w', 600, 2, 80, 'isr'),
    ('late546', 546, 1, None, 'pass'), ('late744', 744, 1, None, 'pass'),
]


def run(wd):
    tag, F, n, rnd, where = wd
    END = None
    mask = MASK
    h, m, r = world('boot')
    seq = expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD
    nb = (r[T] // fd + 1) * fd
    st = {'isr': None, 't0': 0, 'D': 0, 'MD': 0, 'IT': 0}
    frame, in_scan, pending = 0, False, None
    isrs, marks, rounds, draws, cur, poked, scr, e7e85, late = [], [], [], [], None, False, None, None, None
    cm.keys(h, keyf(0))
    oc = sim.contend

    def poke():
        nonlocal poked
        m[0xFECD] = n
        if rnd is not None:
            m[0x8609] = rnd
            m[0xFDDA] |= 0x80
            m[0xFDE4] |= 0x80
        poked = True

    def cont(t, timings):
        if st['isr'] is None and PASSES is not None:
            tt = t
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    d = DELAYS_48K[tt % FD]
                    if PASSES is not None and len(PASSES) - 1 in PDUMP:
                        PDUMP[len(PASSES) - 1].append([tt - st['p0'] - (st['MD'] - st['md0']) - (st['IT'] - st['it0']), a, d, st['pc']])
                    st['MD'] += d
                    tt += d
                tt += ts
        if st['isr'] is not None:
            tt, k = t, 0
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    d = DELAYS_48K[tt % FD]
                    if st['isr'][2] in PROG:
                        PROG[st['isr'][2]].append([tt - st['t0'] - st['D'], k, a, d, st['pc']])
                    st['D'] += d
                    tt += d
                tt += ts
                k += ts
        return oc(t, timings)
    sim.contend = cont
    while scr is None:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            if frame > F + 400 * n + 200:
                raise Fail('%s: frame %d and %d of %d advances reached $8D0C: %s' % (tag, frame, len(marks), n, marks))
        isr = st['isr']
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if in_scan:
                pending = keyf(L)
            else:
                cm.keys(h, keyf(L))
            st['IT'] += r[T] - st['t0']
            if poked:
                isrs.append([L, r[T] - st['t0'], st['D'], st['t0'] % fd])
            if L == F and where == 'isr':
                poke()
            if L == END:
                bm = bytearray(m[0x4000:0x5800])
                for a in mask:
                    bm[a - 0x4000] = 0
                scr = [zlib.crc32(bytes(m[0x5800:0x5B00])), zlib.crc32(bytes(bm))]
                if os.environ.get('LRFREE_SCR'):           # a development aid: the screen itself
                    open('scratchpad/m7115c/scr_%s.bin' % tag, 'wb').write(bytes(m[0x4000:0x5B00]))
            st['isr'] = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        st['pc'] = pc
        if where == 'pass' and not poked and pc == 0x8D0C and st['isr'] is None and frame == F and r[T] % fd >= LATE:
            poke()
            late = r[T] % fd
        if pc == 0x7E85 and e7e85 is None and st['isr'] is None and len(marks) == n and marks and '8D0C' in marks[-1]:
            e7e85 = frame                              # $7E80's long path in the new round's play (DECLARED in the engine)
        if pc == 0x9813 and poked:                 # $9811 LD A,R: the wrap's lookahead draw (the engine's is BB_Rng's)
            draws.append([frame, r[A] & 0x7F])
        if poked and st['isr'] is None:
            if pc == 0x97F8:
                cur = {'97F8': [frame, r[T] % fd]}
                marks.append(cur)
                if STOP and len(marks) == STOP:              # a development aid: hand the machine over at $97F8
                    sim.contend = oc
                    return h
            elif cur is not None and pc in (0x9887, 0x9888) and ('%04X' % pc) not in cur:
                cur['%04X' % pc] = [frame, r[T] % fd]
                if pc == 0x9888:
                    rounds.append(m[0x8609])
            elif pc == 0x8D0C:
                if cur is not None and '9888' in cur and '8D0C' not in cur:
                    cur['8D0C'] = [frame, r[T] % fd]
                    if len(marks) == n:
                        END = frame + TAIL_F
                elif PASSES is not None and cur is not None and '8D0C' in cur and len(marks) == n:
                    if PASSES and len(PASSES[-1]) == 2:      # the last pass's plain T and delay
                        P0 = PASSES[-1]
                        P0 += [r[T] - st['p0'] - (st['MD'] - st['md0']) - (st['IT'] - st['it0']), st['MD'] - st['md0']]
                    PASSES.append([frame, r[T] % fd])
                    st['p0'], st['md0'], st['it0'] = r[T], st['MD'], st['IT']
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert st['isr'] is None, 'an interrupt inside the ISR'
                st['t0'], st['D'] = t_, 0
                st['isr'] = (b0, s0, frame + (1 if r[T] >= nb else 0))
    sim.contend = oc
    if PASSES is not None:
        json.dump(PASSES, open('scratchpad/m7115c/passes_%s.json' % tag, 'w'))
        json.dump(PDUMP, open('scratchpad/m7115c/pdump_%s.json' % tag, 'w'))
    if PROG:
        json.dump(PROG, open('scratchpad/m7115c/prog_%s.json' % tag, 'w'))
    if len(marks) != n or any('8D0C' not in x for x in marks):
        raise Fail('%s: %d advances to $8D0C, not %d: %s' % (tag, len(marks), n, marks))
    if where == 'pass' and late is None:
        raise Fail('%s: no pass in frame %d begins at or past %d' % (tag, F, LATE))
    return {'tag': tag, 'poke': F, 'where': where, 'late': late, 'fecd': n, 'round0': rnd, 'end': END, 'rounds': rounds, 'r9811': draws, 'e7e85': e7e85, 'isrs': isrs, 'marks': marks,
            'scr': scr}


def capture(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(run, WORLDS))
    for x in res:
        print('%-6s poke %d n %d: rounds %s, %d ISRs (to %d), $7E85 %s, marks %s, scr %08x %08x' % (
            x['tag'], x['poke'], x['fecd'], x['rounds'], len(x['isrs']), x['end'], x['e7e85'], x['marks'], x['scr'][0],
            x['scr'][1]), flush=True)
    return {'meta': {'tool': 'tools/lrfree.py', 'no_rom_bytes': True,
                     'note': 'T, phases and CRCs of a later round\'s start free-running on the real load'},
            'script': [[k, v] for k, v in SCRIPT], 'runs': {x['tag']: x for x in res}}


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
        print('verify:', 'MATCH' if old == new else 'DIFFER')
        return 0 if old == new else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
