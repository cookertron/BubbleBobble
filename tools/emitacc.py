"""M7.115i (measurement) -- $7E80, THE ELEMENT EMITTER, ON THE PASS'S ACCESS PROGRAM: its code is in CONTENDED RAM.

M7.114a put every main-loop pass on the frame clock by its ACCESS PROGRAM (passacc) and M7.114d placed each interrupt by
the pass's INSTRUCTION GRID (insgrid); M7.115f did the same for the item pass (itemacc).  $7E80 ($8D3A, the eighth chain
entry) lives at $7E80..$7F0A -- below $8000 -- so every opcode fetch, operand read and internal cycle on its pc there
waits in the screen fetch, and the engine put only its first two instructions on the program ($7E80 LD A,($7E0E) /
$7E83 OR A / $7E84 RET z).  On a round with an element ($7E0E non-zero: 49 of the 81, the boss's among them) EVERY pass
runs on: `$7E85 LD ($7EFB),A / CP 5 / LD A,4 / JR c / LD A,1 / LD ($7EB2),A / LD A,($8E3B) / OR A / RET nz /
LD A,($8DBD) / CP $2A / RET nz` -- and in the frame ($8DBD) = $2A (42 frames into a round, then every 256) the scan of
the twelve bubble slots, the free-slot search and `$7EC2 EI / HALT`: the frame is given away, and after the ISR
`$7EC4 BIT 7,(HL) / RET nz` asks again and the emit fills the slot ($7EEB BIT 5 / RET nz: the emit point solid).

This oracle measures it where it runs:

  THE REAL LOAD (passacc's drive and keys) with ($8609) = round - 1 and ($FECD) = 1 poked at the END of ISR 1000 (bossfree's
  way: $8D12 advances to the round), free-running, contended, to frame END -- rounds 80 (the boss: lightning), 10 (water),
  25 (fire), 3 (a randomised class, 5..12: cap 1) and 17 (lightning):
    passes  every main-line pass from frame 998 [frame, wall phase, plain length, accesses, digest, ISRs inside [plain
            offset, T, label]] -- passacc's row; a pass that HALTs keeps the HALT's steps apart: 'halt' [plain offset of
            its start, steps, their delays]
    isrs    every ISR from 998 [label, T, acceptance phase]
    ldar    every LD A,R from 998 [frame, pc, A] -- the draws the engine's stand-in (BB_Rng) is fed (round 3's class, $7E04)
  SAVED STATES (costsmall's $7E80 worlds: the scan, the emit, the solid point, the cap, the clear's RET), FRAMES frames each
  of random keys (seeded), contended.

  calls   every $7E80 CALL from the chain ($8D3A) -- the fixture keeps the real worlds' HALTing ones: [frame, the wall
          phase at its entry, its plain T to the RET (the ISRs and the delays out; a HALT's steps IN, 4 T each), the accesses (count, digest of 'o:k;' -- o the plain offset from the
          entry, k the T into the instruction; a HALT's own steps OUT), the instructions (count, digest of 'o:t;'; the HALT's
          steps out), the ISRs inside [o, T, label], marks (the visits of MARKS' PCs), halt [plain offset, steps, delays, the
          wall phase of its first step, the acceptance phase] or None]
  replays the FIRST call of each distinct (accesses, instructions) pair in a world and EVERY call that scans ($7E9E), run
          again PLAIN (no contention, interrupts off) from its entry to the RET -- or to the HALT ($7EC3, not run): 'a';
          a call that HALTs also from $7EC4 after its ISR to the RET: 'b' (its seed the machine's RAM after the ISR).  Each
          part: the SEED (every byte >= $4000 read before written, as [start, hex] runs, and the self-modified operands SMC
          at their values), the accesses and the instructions (count + digest, the same strings, o from the part's start),
          T, marks; `same` = the replay's digests are the natural call's (an ISR inside a natural call that is not the
          HALT's can move what it reads: kept, flagged, not a model row)
  forced  FORCED replays (declared): a scanning call's entry poked -- every slot's +7 bit 7 set (no free slot: $7EC1 RET),
          ($8E3B) = 1 (the clear's RET nz at $7E97); its 'b' with the found slot's +7 bit 7 set (filled during the HALT:
          $7EC6 RET nz) and with the emit point's bit 5 set ($7EEB: solid, RET nz to $7F05)

  phased  PHASED runs (declared; a real world's first HALTing call): its entry state with the CPU's T set so that the entry
          lies `shift` T before a frame boundary -- the bottom border, where nothing waits: plain offsets are wall offsets
          and the point lands to the T -- and ($8DBD) poked, run with interrupts and contention to the RET (PHASED: 10 / 70 T
          in; AT and 1 T into $7E98's read; AT and 2 T into the EI; AT and 1 T into the HALT's first step): [plain T, the
          ISRs [plain offset, T, acceptance phase], the HALT, marks, the seed]
  halts   every HALT [world, frame, the wall phase of its start (after the EI), steps, delays, the acceptance phase, the
          label of the ISR] -- the HALT runs 4-T steps, each an M1 at $7EC3 then $7EC4 (CONTENDED: SkoolKit's halt), and
          the interrupt is taken at the end of the first step that ends in the interrupt window: the engine's walk, from
          the start relative to that ISR's boundary (before it; after it when an EI in progress there held the interrupt)

ASSERTED: each natural call's accesses and instructions tile its plain T; a replay's run ends at the RET or the HALT; every
HALT's steps, delays and acceptance are the step walk's from its start.  No ROM byte: offsets, T, phases, digests and game-RAM bytes
(the seeds) only.

Usage:  python tools/emitacc.py [capture|verify] [--jobs N]   -> build/emitacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import PC, T, IFF, SP, A as RA
from skoolkit.cmiosimulator import DELAYS_48K
import revealentry as RE
import revealcont as RC
from passacc import SCRIPT

FIXTURE = 'build/emitacc_fixture.json'
FD = 69888
IA = 32                                 # the interrupt window (the harness's int_active, asserted)
ENTRY, HALT_PC, RESUME = 0x7E80, 0x7EC3, 0x7EC4
MARKS = {0x7E85: 'long', 0x7E8E: 'cap1', 0x7E98: 'noclr', 0x7E9E: 'scan', 0x7EAC: 'live', 0x7EB4: 'room',
         0x7EBE: 'busy', 0x7EC1: 'full', 0x7EC2: 'halt', 0x7EC7: 'free', 0x7EEE: 'emit', 0x7F05: 'gate1'}
KEEP = {'scan'}
# the operands $7E80 rewrites and reads back as instruction bytes: $7EB1 CP n, $7ED6 LD A,n, $7EF8 LD (IY+9),n
SMC = [0x7EB2, 0x7ED7, 0x7EFB]
POKE = 1000
REAL = [('r80', 80, 1700), ('r10', 10, 1700), ('r25', 25, 1700), ('r3', 3, 1700), ('r17', 17, 1700)]
FIRST = POKE - 2
STATES = ['blowbolt', 'boris', 'boss', 'bossspawn', 'bosshit', 'candycane', 'elfire', 'ellight', 'elwater', 'extend',
          'extn', 'firekill', 'hurryup', 'lastdia81', 'r10_48', 'r20_48', 'r30_48', 'redcross']
FRAMES = 600


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


def halt_walk(rel):
    """the HALT's steps from its first's start `rel` T from the boundary its interrupt comes at (negative before it; at or
       past it when an EI in progress there held the interrupt): each 4 T + the ULA's delay at its start (the M1 at $7EC3,
       then $7EC4: contended); the interrupt is taken at the end of the first that ends at or past the boundary -- the
       first step always runs -> (steps, delays, the acceptance phase)"""
    t, n, d = rel, 0, 0
    while True:
        w = DELAYS_48K[t % FD]
        t += w + 4
        n += 1
        d += w
        if t >= 0:
            assert t < IA, 'a HALT step jumped the interrupt window'
            return n, d, t


class Rec:
    """the natural run's recorder: the main line's passes (`pf`..`pt`: frames to record them in) and its $7E80 calls"""

    def __init__(self, h, pf=None, pt=None):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.isr_ph = 0
        self.P = None
        self.C = None
        self.passes, self.calls, self.kept, self.isrs, self.halts, self.ldar = [], [], [], [], [], []
        self.pf, self.pt = pf, pt
        self.seen = set()
        self.tb = 0
        self.d_ins = 0
        self.frame = 0
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend
        self._oc = oc

        def cont(t, timings):
            if self.st_isr is None:
                P, C = self.P, self.C
                hl = C is not None and C['in_halt']
                tt, k = t, 0
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        if P is not None:
                            if not hl:
                                P['acc'].append('%d:%d;' % (tt - P['t0'] - P['D'] - P['I'], k))
                            P['D'] += d
                        if C is not None:
                            if hl:
                                C['hD'] += d
                            else:
                                C['acc'].append('%d:%d;' % (tt - C['t0'] - C['D'] - C['I'], k))
                            C['D'] += d
                        self.d_ins += d
                        tt += d
                    tt += ts
                    k += ts
            return oc(t, timings)
        sim.contend = cont

    def before(self, frame):
        """at an instruction boundary on the main line: the pass / call bookkeeping; True = the instruction is the main
           line's (its grid entry recorded after it runs)"""
        h, r, mem = self.h, self.h.sim.registers, self.h.sim.memory
        pc = r[PC]
        self.frame = frame
        if self.st_isr is not None:
            return False
        if pc == 0x8D0C:
            P = self.P
            if P is not None:
                P['len'] = r[T] - P['t0'] - P['D'] - P['I']
                row = [P['f'], P['ph'], P['len'], len(P['acc']), dig(P['acc']), P['isr']]
                if P['halt'] is not None:
                    row.append(P['halt'])
                self.passes.append(row)
            self.P = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'isr': [], 'halt': None} \
                if self.pf is not None and self.pf <= frame <= self.pt else None
        C = self.C
        if pc == ENTRY and C is None:
            sp = r[SP]
            self.C = C = {'f': frame, 't0': r[T], 'ph': r[T] % FD, 'D': 0, 'I': 0, 'acc': [], 'ins': [], 'isr': [],
                          'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'marks': {}, 'state': h.save_state(),
                          'in_halt': False, 'halt': None, 'hD': 0, 'bstate': None, 'b_o': None}
        elif C is not None:
            if C['in_halt'] and pc != HALT_PC:
                # the HALT is over and its ISR has returned: the main line resumes at $7EC4
                if pc != RESUME:
                    raise Fail('the HALT resumed at $%04X' % pc)
                C['in_halt'] = False
                C['halt'][2] = C['hD']
                C['bstate'] = h.save_state()
                C['b_o'] = r[T] - C['t0'] - C['D'] - C['I']
                if self.P is not None and self.P['halt'] is not None:
                    self.P['halt'][2] = C['hD']
            elif pc == C['ret'] and r[SP] == C['sp'] + 2:
                self.end_call()
                C = None
        C = self.C
        if C is not None and not C['in_halt']:
            name = MARKS.get(pc)
            if name:
                C['marks'][name] = C['marks'].get(name, 0) + 1
            if pc == HALT_PC:
                o = r[T] - C['t0'] - C['D'] - C['I']
                C['in_halt'] = True
                C['halt'] = [o, 0, 0, r[T] % FD, None, frame]
                if self.P is not None:
                    self.P['halt'] = [r[T] - self.P['t0'] - self.P['D'] - self.P['I'], 0, 0]
        elif C is not None and C['in_halt']:
            pass
        self.tb = r[T]
        self.d_ins = 0
        return True

    def after(self):
        """after a main-line instruction: its grid entry (plain offset, plain T); a HALT step is counted apart"""
        C = self.C
        if C is None:
            return
        r = self.h.sim.registers
        if C['in_halt']:
            C['halt'][1] += 1
            if self.P is not None and self.P['halt'] is not None:
                self.P['halt'][1] += 1
            return
        o = self.tb - C['t0'] - (C['D'] - self.d_ins) - C['I']
        C['ins'].append('%d:%d;' % (o, r[T] - self.tb - self.d_ins))

    def end_call(self):
        C = self.C
        self.C = None
        r = self.h.sim.registers
        Tp = r[T] - C['t0'] - C['D'] - C['I']
        key = (dig(C['acc']), dig(C['ins']))
        # the instructions tile the call: each starts where the last ended (the HALT's steps between, 4 T each)
        o_prev = 0
        for s in C['ins']:
            o, t = map(int, s[:-1].split(':'))
            if C['halt'] is not None and o == C['halt'][0] + 4 * C['halt'][1] and o_prev == C['halt'][0]:
                o_prev = o
            if o != o_prev:
                raise Fail('frame %d: $7E80\'s instructions do not tile at %d (expected %d)' % (C['f'], o, o_prev))
            o_prev = o + t
        if o_prev != Tp:
            raise Fail('frame %d: $7E80\'s instructions end at %d, its T %d' % (C['f'], o_prev, Tp))
        halt = None
        if C['halt'] is not None:
            o, n, d, ph, acc, hf = C['halt']
            halt = [o, n, d, ph, acc]
        row = [C['f'], C['ph'], Tp, len(C['acc']), key[0], len(C['ins']), key[1], C['isr'],
               dict(sorted(C['marks'].items())), halt]
        self.calls.append(row)
        keep = key not in self.seen or any(k in KEEP for k in C['marks'])
        self.seen.add(key)
        if keep:
            self.kept.append((len(self.calls) - 1, C['state'], C['bstate'], C['b_o'], C['sp'], C['ret']))

    def isr_begin(self, t_, label):
        self.isr_t0 = t_
        C = self.C
        if C is not None and C['in_halt']:
            C['halt'][4] = t_ % FD                   # the acceptance phase: the end of the HALT's last step
            self.halts.append([C['halt'][5], C['halt'][3], C['halt'][1], C['hD'], t_ % FD, label])

    def isr_end(self, label):
        r = self.h.sim.registers
        T_ = r[T] - self.isr_t0
        self.isrs.append([label, T_, self.isr_t0 % FD])
        for X in (self.P, self.C):
            if X is not None:
                X['isr'].append([self.isr_t0 - X['t0'] - X['D'] - X['I'], T_, label])
                X['I'] += T_


def drive(h, rec, until, keyf=None, poke=None, rng=None, pool=()):
    """the natural run: passacc's ISR-end keys (keyf) or random keys at frame boundaries (rng); `poke` at the end of ISR
       POKE; to frame `until`"""
    sim, ops, mem, r = h.sim, h.sim.opcodes, h.sim.memory, h.sim.registers
    fd, ia = h.frame_duration, h.int_active
    assert fd == FD and ia == IA
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr, keyrun, cur = 0, False, None, None, 0, []
    if keyf:
        cm.keys(h, keyf(0))
    while frame <= until:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
            if rng is not None:
                if keyrun <= 0:
                    keyrun = rng.randint(4, 30)
                    cur = [k for k in pool if rng.random() < 0.4]
                keyrun -= 1
                cm.keys(h, cur)
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if keyf:
                if in_scan:
                    pending = keyf(L)
                else:
                    cm.keys(h, keyf(L))
            if poke and L == POKE:
                for a, v in poke:
                    mem[a] = v
            rec.st_isr = None
            rec.isr_end(L)
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        main = rec.before(frame)
        ops[mem[pc]]()
        if main:
            rec.after()
        if mem[pc] == 0xED and mem[(pc + 1) & 0xFFFF] == 0x5F:
            rec.ldar.append([frame, pc, r[RA]])          # LD A,R: the draw, for the engine's stand-in to be fed
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                rec.st_isr = isr
                rec.isr_begin(t_, isr[2])


def run_real(wd):
    tag, rnd, END = wd
    h, m, r = world('boot')
    seq = expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    rec = Rec(h, FIRST, END)
    drive(h, rec, END, keyf=keyf, poke=[(0x8609, rnd - 1), (0xFECD, 1)])
    return tag, rec


def run_state(st):
    h = RE.new(st)
    rec = Rec(h)
    drive(h, rec, FRAMES, rng=random.Random('emitacc:' + st), pool=('O', 'P', 'Q', 'SPACE'))
    return st, rec


def replay(state, stop_sp_ret, pokes=(), part='a'):
    """PLAIN (no contention, interrupts off) from the saved state to the RET (SP back above the call) or, part 'a', to the
       HALT ($7EC3, not run): the seed, the accesses, the instructions, T, marks, where it stopped"""
    sp0, ret = stop_sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    m0 = bytes(h.memobj.m)
    rm = RE.SeedMem(h.memobj.m)
    log = []
    sim = RC.sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    want = ENTRY if part == 'a' else RESUME
    if r[PC] != want:
        raise Fail('a replay not at $%04X' % want)
    rm.regs = r
    t0 = r[T]
    acc, ins, marks, end = [], [], {}, 'ret'
    nlog = 0
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p == HALT_PC:
            end = 'halt'
            break
        if p in GUARD:
            raise Fail('replay: guard at $%04X' % p)
        name = MARKS.get(p)
        if name:
            marks[name] = marks.get(name, 0) + 1
        tb = r[T]
        sim.opcodes[mem[p]]()
        for t in log[nlog:]:
            acc.append('%d:%d;' % (t - t0, t - tb))
        nlog = len(log)
        ins.append('%d:%d;' % (tb - t0, r[T] - tb))
        if r[T] - t0 > 10 ** 5:
            raise Fail('replay: no RET')
    rm.regs = None
    runs = []
    for a in sorted(set(a for a in rm.rd if a >= 0x4000) | set(SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return {'seed': runs, 'acc': [len(acc), dig(acc)], 'ins': [len(ins), dig(ins)], 'T': r[T] - t0,
            'marks': dict(sorted(marks.items())), 'end': end, 'hl': [r[6], r[7]]}


def phased(state, sp_ret, shift, ctr):
    """FORCED (declared): a scanning call's entry moved to `shift` T before a frame boundary (the bottom border: nothing
       waits there) with ($8DBD) = ctr, run with interrupts and contention to its RET -- the interrupt the natural runs never
       put inside $7E80 before its HALT.  -> [plain T, its ISRs [plain offset, T, acceptance phase], its HALT [plain offset,
       steps, delays, start phase, acceptance phase], marks]"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    m, r = h.memobj.m, h.sim.registers
    if r[PC] != ENTRY:
        raise Fail('a phased run not at $7E80')
    r[T] = (r[T] // FD + 1) * FD - shift
    m[0x8DBD] = ctr
    rec = Rec(h)
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, isr, t_end = 0, None, r[T] + 3 * FD
    while not rec.calls:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            rec.st_isr = None
            rec.isr_end(isr[2])
            isr = None
        if pc in GUARD or r[T] > t_end:
            raise Fail('phased run: guard at $%04X / no RET' % pc)
        main = rec.before(frame)
        ops[mem[pc]]()
        if main:
            rec.after()
        if r[IFF] and r[T] % fd < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))
                rec.st_isr = isr
                rec.isr_begin(t_, isr[2])
    c = rec.calls[0]
    return {'T': c[2], 'isr': [[o, t, ph] for (o, t, L), (_, _, ph) in zip(c[7], rec.isrs)], 'halt': c[9],
            'marks': c[8], 'halts': rec.halts}


# the phased runs (declared): the boundary 10 / 70 T into the call with ($8DBD) = $29 (the ISR before $7E98's read steps
# it to $2A: the scan, and the HALT after the interrupt -- LATE); with ($8DBD) = $2A, 'ei0' AT its EI's start (the
# instruction before it ends there: the interrupt taken before the EI -- LATE), 'ei' 2 T into the EI, 'step0' at the HALT's
# first step's start (the EI ends there) and 'step1' 1 T into it (each taken at that ONE step's end).  The last four are
# placed from the replay's T to the HALT (the EI its last 4 T).  And 'rd0' AT $7E98's start ($8DBD) = $29 (the RET nz before
# it ends there: the ISR first, the read sees $2A) and 'rd1' 1 T into it (the read before the ISR: $29, no scan) -- $7E98 is
# 96 T in (98 on the capped path: '7E8Cf')
PHASED = [('late10', 10, 0x29), ('late70', 70, 0x29), ('ei0', -4, 0x2A), ('ei', -2, 0x2A), ('step0', 0, 0x2A),
          ('step1', 1, 0x2A), ('rd0', 0, 0x29), ('rd1', 1, 0x29)]


def world_job(wd):
    tag, rec = run_real(wd) if isinstance(wd, tuple) else run_state(wd)
    reps, forced = [], []
    for i, st, bst, b_o, sp, ret in rec.kept:
        c = rec.calls[i]
        x = {'call': i, 'a': replay(st, (sp, ret))}
        if bst is not None:
            x['b'] = replay(bst, (sp, ret), part='b')
            x['b_o'] = b_o
        # the natural call's digests are the parts' when no ISR but the HALT's lies inside it (a HALT call's are not
        # comparable whole: the parts are checked against the natural's split at the HALT by the gate's model)
        x['same'] = (len(c[7]) == 0 and x['a']['acc'][1] == c[4] and x['a']['ins'][1] == c[6]) if c[9] is None else \
            len(c[7]) == 1
        reps.append(x)
    # the forced replays: the first scanning call's entry and, the first halting call's 'b'
    for i, st, bst, b_o, sp, ret in rec.kept:
        c = rec.calls[i]
        if 'scan' in c[8] and 'room' in c[8] and not any(f['forced'] == 'all_busy' for f in forced):
            pk = [(0xFEDF + 10 * j, st[0][0xFEDF + 10 * j] | 0x80) for j in range(12)]
            forced.append({'call': i, 'forced': 'all_busy', 'pokes': pk, 'a': replay(st, (sp, ret), pk)})
            forced.append({'call': i, 'forced': 'clearing', 'pokes': [(0x8E3B, 1)], 'a': replay(st, (sp, ret), [(0x8E3B, 1)])})
        if bst is not None and not any(f['forced'] == 'filled' for f in forced):
            # the found slot's +7: HL at $7EC4 (the saved state's registers: H 6, L 7)
            mm, rr = bst[0], bst[1]
            hl = rr[7] | (rr[6] << 8)
            pk = [(hl, mm[hl] | 0x80)]
            forced.append({'call': i, 'forced': 'filled', 'pokes': pk, 'b': replay(bst, (sp, ret), pk, part='b'),
                           'b_o': b_o})
            # the emit point solid: $7F0B + 4 x ((($7ED7) + 1) & 3) -> the pointer; its byte's bit 5
            nxt = (mm[0x7ED7] + 1) & 3
            tb = 0x7F0B + 4 * nxt
            ptr = mm[tb] | (mm[tb + 1] << 8)
            pk2 = [(ptr, mm[ptr] ^ 0x20)]
            forced.append({'call': i, 'forced': 'solid' if not (mm[ptr] & 0x20) else 'open', 'pokes': pk2,
                           'b': replay(bst, (sp, ret), pk2, part='b'), 'b_o': b_o})
    # the phased runs: from the first HALTing call's entry (a real world's), the boundary moved onto it
    phase = []
    if rec.pf is not None:
        for (i, st, bst, b_o, sp, ret), x in zip(rec.kept, reps):
            if bst is None:
                continue
            for name, s, ctr in PHASED:
                shift = s if name.startswith('late') else                     (96 if st[0][0x7E0E] < 5 else 98) + s if name.startswith('rd') else x['a']['T'] + s
                y = phased(st, (sp, ret), shift, ctr)
                y.update({'call': i, 'phased': name, 'shift': shift, 'ctr': ctr, 'seed': x['a']['seed']})
                phase.append(y)
            break
    out = {'tag': tag, 'n_calls': len(rec.calls), 'replays': reps, 'forced': forced, 'cover': {},
           'halts': rec.halts + [hh for y in phase for hh in y.pop('halts')], 'phased': phase}
    for c in rec.calls:
        for k, v in c[8].items():
            out['cover'][k] = out['cover'].get(k, 0) + v
    if rec.pf is not None:
        out['passes'] = rec.passes
        out['isrs'] = [x for x in rec.isrs if x[0] >= FIRST]
        out['calls'] = [c for c in rec.calls if c[0] >= FIRST and c[9] is not None]      # the HALTing calls
        out['e7e85'] = next((c[0] for c in rec.calls if 'long' in c[8] and c[0] >= POKE), None)
        out['ldar'] = [x for x in rec.ldar if x[0] >= FIRST]
    return out


def capture(jobs):
    jobsl = list(REAL) + list(STATES)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, jobsl))
    cover = {}
    halts = []
    for x in res:
        for k, v in x['cover'].items():
            cover[k] = cover.get(k, 0) + v
        for hh in x['halts']:
            # hh: [the frame the HALT began in, its start phase, steps, delays, acceptance phase, the ISR's label]
            n, d, ph = halt_walk(hh[1] - FD if hh[0] < hh[5] else hh[1])
            if (n, d, ph) != (hh[2], hh[3], hh[4]):
                raise Fail('%s frame %d: the HALT from phase %d took %d steps (%d delays) to %d; the walk says %d / %d / %d'
                           % (x['tag'], hh[0], hh[1], hh[2], hh[3], hh[4], n, d, ph))
            halts.append([x['tag']] + hh)
        nr = len(x['replays'])
        ns = sum(1 for y in x['replays'] if y['same'])
        print('%-10s %6d calls, %4d replays (%d plain-comparable), %d forced, %d HALTs%s' % (
            x['tag'], x['n_calls'], nr, ns, len(x['forced']), len(x['halts']),
            ', %d passes, $7E85 from %s' % (len(x['passes']), x['e7e85']) if 'passes' in x else ''), flush=True)
    print('cover:', ' '.join('%s=%d' % kv for kv in sorted(cover.items())))
    return {'meta': {'tool': 'tools/emitacc.py', 'no_rom_bytes': True,
                     'note': 'the element emitter ($7E80): access programs and instruction grids, natural and replayed; '
                             'seeds are game-RAM bytes read before written'},
            'script': [[k, v] for k, v in SCRIPT], 'poke': POKE, 'first': FIRST, 'real': [list(w) for w in REAL],
            'frames': FRAMES, 'smc': SMC, 'marks': {('%04X' % k): v for k, v in MARKS.items()},
            'worlds': {x['tag']: x for x in res}, 'cover': cover, 'halts': halts}


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
