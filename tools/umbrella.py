# -*- coding: utf-8 -*-
"""THE UMBRELLA'S $A110 BLOCK -- what collecting the umbrella does between $88C0 JP $A110 and the RET
that returns into the item manager, and what the main loop does after it.  (revealentry.py measured the
five reveals' windows; this is the whole block, segment by segment, for the port's M7.98.)

THE CODE (adis.py; nothing else is in the block):
  $88B1  CALL $FE85 / AND 3 / SUB 1 / ADC A,0 / ADD A,A / ADD A,3 / LD ($FECD),A   {3,3,5,7}
  $88C0  JP $A110
  $A110  LD B,5
  $A112  PUSH BC / LD DE,$0010 / CALL $A0E0     the FLASH: $A0E0 OUT ($FE),A (A is whatever it is: on
                                                the first turn ($FECD), after a reveal 0), then
                                                $5840..$5AFF := (x AND D) OR E = $10, 704 cells, via
                                                $A0ED's loop CALLed twice and fallen into (192+256+256)
  $A119  EI / HALT                              wait for the frame interrupt
  $A11B  DI / CALL $8C28                        the REVEAL, interrupts off to its own $8C4C EI
  $A11F  EI / HALT
  $A121  DI / POP BC / DJNZ $A112               turns 2..5: the flash runs with interrupts OFF
  $A125  EI / RET
So the block is FIVE flashes and FIVE reveals whatever ($FECD) is -- the count only reaches the main
loop's $8D12, which skips that many rounds after the RET.  ($FECD) itself shows in the block only as
the first flash's border (OUT ($FE),A with A = 3 / 5 / 7).

THE SEGMENTS, each between two HALTs (a segment starts on the instruction after the HALT, the ISR
that ended it done):
  head    $88C0 .. the HALT at $A11A   (interrupts as the main loop has them: ON)
  reveal  $A11B .. the HALT at $A120   (k = 1..5)
  flash   $A121 .. the HALT at $A11A   (k = 2..5; DI at $A121)
  end     $A121 .. the RET's landing   (DI / POP BC / DJNZ falls / EI / RET)

RUNS:
  natural  the umbrella world (round 25, the umbrella above player 1): the jump key held from the load to
           $88B1 (the collect), then every key released; ($FECD) is the PRNG's.
  f3/f5/f7 FORCED on round1_48 (and f5 on r50_48): at the main loop's $8D25, $88BD (LD ($FECD),A) called
           with A = 3 / 5 / 7 and IX = player 1, interrupts ON; at its return the pass goes on at $8D25.

PER RUN:
  exact    each segment from its own start state (as the contended run reached it), a plain Simulator,
           fast_djnz / fast_ldir OFF, no contention, interrupts OFF, to the HALT (the 'end' to the RET's
           landing): its T, its stamps (DI / EI ends, $A0E0, its OUT, its RET; the reveal's hooks as
           revealentry's), its OUTs to $FE [T, value], and every write outside the stack with its
           instruction's start T -- a flash's as RLE runs [address, T, d_address, d_T, n] with the one
           value they all write, a reveal's as count + digest of 'address@T;' (values left out: the
           digits are the ROM charset's) -- and for a reveal the SEED (bytes of $4000.. read before
           written, [start, hex] runs; a read below $4000 as its address alone), or 'seed_as' naming the
           earlier reveal of the run whose seed is the same.
  free     CONTENDED, interrupts ON, from $88C0 (T0) to the block's RET: every accepted interrupt [T,
           ISR wall T, PC interrupted], every HALT's start, every segment's start, every DI window, every
           frame boundary inside and whether it was LOST, the main-line OUTs to $FE [T, value], the RET.
  after    the same machine on to where the main loop runs its chain again with ($FECD) = 0: each $97F8
           entry (T, ($8609) there), ($FECD) and ($8609) at the RET and at that $8D25, the T.
  NO ROM BYTE IS STORED.  GUARDED: a run stops with an error if PC enters $D000..$D2FF.

Usage:  python tools/umbrella.py measure [--jobs N]  -> build/umbrella_fixture.json
        python tools/umbrella.py verify  [--jobs N]  re-run and diff against the fixture (MATCH)
"""
import sys, os, json, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, Mem, PC, T, SP, IFF, IXh, IXl, A as RA
from skoolkit.simulator import Simulator
import portconfig as pc

FIXTURE = 'build/umbrella_fixture.json'
FRAME_T = 69888
INT_T = 32
GUARD = set(range(0xD000, 0xD300))
LOOP_TOP = 0x8D25
HALT1, HALT2 = 0xA11A, 0xA120          # after the flash / after the reveal
SEG_R, SEG_F = 0xA11B, 0xA121          # the instruction after each HALT
REVEAL = 0x8C28
RV_HOOKS = {0x8216: 'repaint', 0x7F80: 'digits', 0x8C2B: 'derive', 0x957E: 'panel', 0x806C: 'lives',
            0x8C4C: 'out'}
RUNS = [('natural', 'umbrella', None), ('f3', 'round1_48', 3), ('f5', 'round1_48', 5),
        ('f7', 'round1_48', 7), ('r50_f5', 'r50_48', 5)]


class Fail(Exception):
    pass


def new(state):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    if h.memobj.m[0x8DC4] != 0xC9:
        raise Fail('%s: not the 48K branch (TRAPS #28)' % state)
    return h


def plain(h):
    """swap in a plain Simulator, fast_djnz / fast_ldir OFF, no contention"""
    regs = list(h.sim.registers)
    sim = Simulator(h.memobj, config={'fast_djnz': False, 'fast_ldir': False})
    sim.registers[:] = regs
    h.sim = sim
    h.memobj.sim = sim
    sim.set_tracer(h.ports)
    h.frame_duration, h.int_active = sim.frame_duration, sim.int_active


class SeedMem(Mem):
    """the first access of each byte (a read before any write is an input) and every write outside the
    stack: (address, its instruction's start T, value)"""
    __slots__ = ('seen', 'rd', 'wr', 'regs', 'tins')

    def __init__(self, data):
        Mem.__init__(self, data)
        self.seen, self.rd, self.wr, self.regs, self.tins = set(), [], [], None, [0]

    def __getitem__(self, i):
        if self.regs is not None and type(i) is int and i not in self.seen:
            p = self.regs[PC]
            if not (p <= i < p + 4):
                self.seen.add(i)
                self.rd.append(i)
        return self.m[i]

    def __setitem__(self, i, v):
        if self.regs is not None:
            self.seen.add(i)
            sp = self.regs[SP]
            if not (sp - 64 <= i < sp + 64):
                self.wr.append((i, self.tins[0], v & 0xFF))
        Mem.__setitem__(self, i, v)


def rle(wr):
    """[address, T, d_address, d_T, n] runs of a (address, T) list"""
    out = []
    for a, t in wr:
        if out:
            r = out[-1]
            if r[4] == 1:
                r[2], r[3], r[4] = a - r[0], t - r[1], 2
                continue
            if a - (r[0] + r[2] * (r[4] - 1)) == r[2] and t - (r[1] + r[3] * (r[4] - 1)) == r[3]:
                r[4] += 1
                continue
        out.append([a, t, 0, 0, 1])
    return out


def push_call(h, addr, ix=None, a=None):
    r = h.sim.registers
    sp = r[SP]
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = s & 0xFF
        h.memobj.m[sp + 1] = s >> 8
    r[SP] = sp
    r[PC] = addr
    if ix is not None:
        r[IXh], r[IXl] = ix >> 8, ix & 0xFF
    if a is not None:
        r[RA] = a


def keys_jump(h):
    m = h.memobj.m
    h.ports.release_all()
    sel, mask = m[0xB5FD + 4], m[0xB5FD + 5]          # 'LRJB': the jump's (select, mask)
    h.ports.press(sel, 0xFF & ~mask)


def step1(h, interrupts=True):
    """one main-line instruction (or a HALT to its interrupt); returns the accepted interrupt's T or None"""
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    p = r[PC]
    if p in GUARD:
        raise Fail('guard at $%04X' % p)
    if interrupts and mem[p] == 0x76 and r[IFF]:
        h._fast_halt()
        return r[T]
    sim.opcodes[mem[p]]()
    if interrupts and r[IFF] and r[T] % h.frame_duration < h.int_active:
        tb = r[T]
        if sim.accept_interrupt(r, mem, p):
            return tb
    return None


def reach(run):
    """the machine at $88C0 with what the block returns to"""
    name, world, v = run
    h = new(world)
    m, r = h.memobj.m, h.sim.registers
    t0 = r[T]
    info = {}
    if v is None:
        keys_jump(h)
        while r[PC] != 0x88B1:
            step1(h)
            if r[T] - t0 > 300 * FRAME_T:
                raise Fail('%s: no collect' % name)
        h.ports.release_all()
        info['collect_frames'] = round((r[T] - t0) / FRAME_T, 3)
        info['phase_88b1'] = r[T] % FRAME_T
        sp0 = r[SP]
        ret = m[sp0] | (m[sp0 + 1] << 8)
        resume = None
    else:
        while not (r[PC] == LOOP_TOP):
            step1(h)
            if r[T] - t0 > 4 * FRAME_T:
                raise Fail('%s: no loop top' % name)
        resume = (r[PC], r[SP])
        push_call(h, 0x88BD, 0xFD80, v)
        sp0 = r[SP]
        ret = m[sp0] | (m[sp0 + 1] << 8)
    while r[PC] != 0x88C0:
        step1(h)
    info.update(fecd=m[0xFECD], round=m[0x8609], phase_88c0=r[T] % FRAME_T, iff=r[IFF],
                a=r[RA])
    return {'state': h.save_state(), 'ret': ret, 'sp0': sp0, 'resume': resume, 'info': info}


def exact_seg(st, kind, k, ret, sp0):
    """one segment, plain, interrupts off, from its start to the HALT (or the 'end' to the RET's landing)"""
    h = new('round1_48')
    h.load_state(st)
    rm = SeedMem(h.memobj.m)
    h.memobj = rm
    m0 = bytes(rm.m)
    plain(h)
    h.ports.record_writes = True
    h.ports.writes = []
    r, sim, mem = h.sim.registers, h.sim, h.sim.memory
    t0 = r[T]
    rm.regs = r
    stamps, prev, rv_sp = [], None, None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if kind == 'end':
            if p == ret and r[SP] == sp0 + 2:
                break
        elif p in (HALT1, HALT2) and mem[p] == 0x76:
            break
        if kind == 'reveal':
            if p == REVEAL and rv_sp is None:
                rv_sp = r[SP]
                stamps.append(['reveal', r[T] - t0])
            if p in RV_HOOKS and rv_sp is not None and prev != p:
                stamps.append([RV_HOOKS[p], r[T] - t0])
            if p == 0x8C4E:
                stamps.append(['outI', r[T] - t0])
            if p == 0xA11F:
                stamps.append(['ret', r[T] - t0])
        else:
            if p == 0xA0E0:
                stamps.append(['a0e0', r[T] - t0])
            if p == 0xA119:
                stamps.append(['ret', r[T] - t0])
        iff = r[IFF]
        rm.tins[0] = r[T]
        sim.opcodes[mem[p]]()
        if iff and not r[IFF]:
            stamps.append(['di_end', r[T] - t0])
        if not iff and r[IFF]:
            stamps.append(['ei_end', r[T] - t0])
        prev = p
        if r[T] - t0 > 10 ** 6:
            raise Fail('exact %s %d: no end' % (kind, k))
    rm.regs = None
    outs = [[t - t0, v] for t, port, v in h.ports.writes if port & 0xFF == 0xFE]
    seg = {'kind': kind, 'k': k, 'T': r[T] - t0, 'stamps': stamps, 'outs': outs}
    wr = rm.wr
    if kind in ('head', 'flash'):
        vals = sorted(set(v for a, t, v in wr))
        seg['n_writes'] = len(wr)
        seg['writes'] = rle([(a, t - t0) for a, t, v in wr])
        seg['values'] = vals
    elif kind == 'reveal':
        s = ''.join('%d@%d;' % (a, t - t0) for a, t, v in wr)
        seg['n_writes'] = len(wr)
        seg['writes'] = hashlib.sha1(s.encode('ascii')).hexdigest()[:16]
        runs = []
        for a in sorted(a for a in rm.rd if a >= 0x4000):
            if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
                runs[-1][1] += '%02X' % m0[a]
            else:
                runs.append([a, '%02X' % m0[a]])
        seg['seed'] = {'ram': runs, 'rom': sorted(a for a in rm.rd if a < 0x4000)}
    else:
        seg['n_writes'] = len(wr)
    return seg


def _exact(a):
    return exact_seg(*a)


def free(x, name):
    """contended, interrupts on, from $88C0 to the block's RET, then on to the main loop's chain again"""
    h = new('round1_48')
    h.load_state(x['state'])
    m, r, sim, mem = h.memobj.m, h.sim.registers, h.sim, h.sim.memory
    fd = h.frame_duration
    h.ports.record_writes = True
    h.ports.writes = []
    t0 = r[T]
    ret, sp0 = x['ret'], x['sp0']
    isrs, halts, segs, wins, starts = [], [], [['head', 0, 0]], [], []
    isr = None
    di_t, ei_pending = None, False
    kk = {'reveal': 0, 'flash': 1}
    seg_states = [[('head', 1), x['state']]]
    end = None
    while True:
        p = r[PC]
        if p in GUARD:
            raise Fail('guard at $%04X' % p)
        if isr is not None and p == isr[0] and r[SP] == isr[1]:
            isrs[-1].append(r[T] - t0 - isrs[-1][0])
            isr = None
            if p in (SEG_R, SEG_F):
                if p == SEG_R:
                    kk['reveal'] += 1
                    kind = ('reveal', kk['reveal'])
                elif kk['flash'] < 5:
                    kk['flash'] += 1
                    kind = ('flash', kk['flash'])
                else:
                    kind = ('end', 0)
                segs.append([kind[0], kind[1], r[T] - t0])
                seg_states.append([kind, h.save_state()])
        if isr is None and p == ret and r[SP] == sp0 + 2:
            end = r[T] - t0
            break
        if mem[p] == 0x76 and r[IFF] and isr is None:
            if ei_pending:
                wins.append([di_t, r[T] - t0])
                ei_pending, di_t = False, None
            halts.append([p, r[T] - t0])
            pp = p
            h._fast_halt()
            isrs.append([r[T] - t0, pp])
            isr = ((pp + 1) & 0xFFFF, r[SP] + 2)
            continue
        iff = r[IFF]
        sim.opcodes[mem[p]]()
        if isr is None:
            if ei_pending and r[IFF]:
                wins.append([di_t, r[T] - t0])
                ei_pending, di_t = False, None
            if iff and not r[IFF] and di_t is None:
                di_t = r[T] - t0
            if not iff and r[IFF] and di_t is not None:
                ei_pending = True
        if r[IFF] and r[T] % fd < h.int_active:
            tb, spb = r[T], r[SP]
            if sim.accept_interrupt(r, mem, p):
                isrs.append([tb - t0, p])
                isr = (mem[r[SP]] | (mem[r[SP] + 1] << 8), spb)
        if r[T] - t0 > 40 * FRAME_T:
            raise Fail('%s: no end of the block' % name)
    first = fd - (t0 % fd)
    bounds = list(range(first, end, fd))
    acc = [i[0] for i in isrs]
    lost = [b for b in bounds if not any(b <= a < b + INT_T for a in acc)]
    # the OUTs to $FE outside the ISRs
    def in_isr(t):
        return any(i[0] <= t < i[0] + (i[2] if len(i) > 2 else 0) for i in isrs)
    outs = [[t - t0, v] for t, port, v in h.ports.writes if port & 0xFF == 0xFE and not in_isr(t - t0)]
    fr = {'phase0': t0 % fd, 'isrs': [[i[0], i[2] if len(i) > 2 else None, i[1]] for i in isrs],
          'halts': halts, 'segs': segs, 'windows': wins, 'bounds': bounds, 'lost': lost, 'outs': outs,
          'end': end, 'fecd_end': m[0xFECD], 'round_end': m[0x8609]}
    # ...and on: for a forced run the pass goes on at $8D25 as it stood
    if x['resume'] is not None:
        r[PC], r[SP] = x['resume']
    advances = []
    t1 = r[T]
    while True:
        p = r[PC]
        if p == 0x97F8:
            advances.append([r[T] - t0, m[0x8609]])
        if p == LOOP_TOP and m[0xFECD] == 0 and (advances or x['info']['fecd'] == 0):
            break
        step1(h)
        if r[T] - t1 > 2000 * FRAME_T:
            raise Fail('%s: the main loop never came back' % name)
    aft = {'advances': advances, 'resume_T': r[T] - t0, 'round': m[0x8609], 'fecd': m[0xFECD]}
    return fr, aft, seg_states


def one(run):
    x = reach(run)
    fr, aft, seg_states = free(x, run[0])
    return run, x, fr, aft, seg_states


def measure(jobs=6):
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(one, RUNS))
    ex_args, owners = [], []
    for run, x, fr, aft, seg_states in res:
        for (kind, k), st in seg_states:
            ex_args.append((st, kind, k, x['ret'], x['sp0']))
            owners.append(run[0])
    with ProcessPoolExecutor(jobs) as ex:
        segs = list(ex.map(_exact, ex_args))
    out = {'meta': {'frame_t': FRAME_T, 'int_t': INT_T,
                    'runs': [[a, b, c] for a, b, c in RUNS]}, 'runs': {}}
    for run, x, fr, aft, seg_states in res:
        mine = [s for s, o in zip(segs, owners) if o == run[0]]
        seen = []
        for s in mine:
            if s['kind'] == 'reveal':
                for j, (k2, sd) in enumerate(seen):
                    if sd == s['seed']:
                        s['seed_as'] = k2
                        del s['seed']
                        break
                else:
                    seen.append((s['k'], s['seed']))
        out['runs'][run[0]] = {'world': run[1], 'forced': run[2], 'reach': x['info'],
                               'exact': mine, 'free': fr, 'after': aft}
    return out


def report(out):
    for name, d in out['runs'].items():
        i = d['reach']
        print('%-7s %-9s FECD %d round %d phase@$88C0 %d iff %d A %d %s' % (
            name, d['world'], i['fecd'], i['round'], i['phase_88c0'], i['iff'], i['a'],
            ('collect in %.2f frames' % i['collect_frames']) if 'collect_frames' in i else 'forced'))
        print('   exact: ' + ', '.join('%s%d %d T (%d w%s)' % (s['kind'], s['k'], s['T'], s['n_writes'],
              (' seed_as %d' % s['seed_as']) if 'seed_as' in s else '') for s in d['exact']))
        f = d['free']
        print('   free: end %d T (%.2f frames), %d ISRs, %d bounds, %d lost, %d windows, outs %s' % (
            f['end'], f['end'] / FRAME_T, len(f['isrs']), len(f['bounds']), len(f['lost']), len(f['windows']),
            f['outs']))
        print('   segs: ' + ' '.join('%s%d@%d' % (a, b, c) for a, b, c in f['segs']))
        a = d['after']
        print('   after: %d advances %s; resumes at T %d (%.1f frames) round %d FECD %d' % (
            len(a['advances']), [x[1] for x in a['advances']], a['resume_T'], a['resume_T'] / FRAME_T,
            a['round'], a['fecd']))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'measure'
    jobs = 6
    if '--jobs' in sys.argv:
        jobs = min(6, int(sys.argv[sys.argv.index('--jobs') + 1]))
    if cmd not in ('measure', 'verify'):
        raise SystemExit(__doc__)
    t = time.time()
    out = measure(jobs)
    report(out)
    if cmd == 'measure':
        with open(FIXTURE, 'w', encoding='utf-8') as f:
            json.dump(out, f, separators=(',', ':'))
        print('wrote %s (%.1f s)' % (FIXTURE, time.time() - t))
    else:
        with open(FIXTURE, encoding='utf-8') as f:
            old = json.load(f)
        new_ = json.loads(json.dumps(out))
        if old == new_:
            print('MATCH (%.1f s)' % (time.time() - t))
        else:
            bad = [k for k in old['runs'] if old['runs'][k] != new_['runs'].get(k)]
            print('DIFF in %s (%.1f s)' % (bad, time.time() - t))
            sys.exit(1)


if __name__ == '__main__':
    main()
