"""M7.115m (measurement) -- THE EVEN ISR'S LAST ACCESSES OFF ITS PROGRAM: THE POP, THE ESCAPE'S AND THE PUSH'S ERASES, THE
STEAL AND THE BLOW'S BONUS AWARD.

M7.114c put each interrupt's own contention on its ACCESS PROGRAM (isracc: every display access of $A447's erase and
draw and of $B9E7's blit, the player handler's port cycles, the settler's reads, the bubble manager's travel, capture and
rise transition), and the engine replays it from the acceptance phase (isrD).  The even ISR's bubble manager $B62C runs
more that touches contended memory, none of it on the program -- M7.115k's SK3 pin: ISR 804, 83 accesses short, its T 5
short:
  the POP $B6D8 -- from the held arm ($B6C3), the age's `CALL m` ($B669) and the blow's steal ($BDBC):
      its erase ($B6E3 CALL $BF0A -> $BF16 -> $A447's SHIFTED erase: 80 screen accesses at a Y the ROM rows do not cut),
      its seed of the sparkle table at $5CE0 ($B701's read of each slot it walks, $B713 / $B718's stores, $B723's cancel),
      a PAID pop's award ($B797 CALL $80FA: each drawn digit's eight glyph stores into the HUD, $8052) between its two
      OUT ($FE)s ($B791 / $B79E: the ULA's I/O cycle), and a class-1 pop's corpse birth ($B816 -> $8BC2 -> $8C51 -> $A447
      on the enemy: an erase on its live arm, none on its $A437 arms);
  the ESCAPE's erase ($B6B9 CALL $BF0A: a holding bubble whose age wraps -- its enemy released, the bubble erased);
  the PUSH's erase ($B952 CALL $BF0A, inside the rise $B836: a player pressing into a risen bubble);
  the blow's BONUS award ($BD6B CALL $80FA: the player whose last power-up was type 15, paid on every blow).
This oracle measures the bubble manager's whole program wherever one of them runs:

  SAVED STATES (sparkacc's 48), FRAMES frames each of random keys with SPACE (seeded 'popacc:'): natural pops (held,
  aged, chained, paid), pushes, escapes.
  calls   every even ISR's $B62C (entered by $8DAD's JP, its RET to $8D8F) is counted; the ones that run a pop, an
          escape's erase, a push's erase, a steal or the bonus award (KEEP) are kept: [frame, $B62C's entry from the
          ISR's acceptance, its plain T, the accesses (count, digest of 'o:k;' -- o the plain offset from $B62C's entry,
          k the T into the instruction; an OUT ($FE)'s I/O cycle is SkoolKit's $4000 pseudo-address), the marks [name,
          plain offset] (MARKS; a pop's name carries its caller's return address), the ISR's acceptance phase, the
          waits of its $B62C (D: the even ISR's whole contention -- nothing before or after $B62C touches contended memory)]
  replays every kept call run again PLAIN (no contention, interrupts off) from its entry to its RET: the SEED (every
          byte >= $4000 read before written, as [start, hex] runs, and the self-modified operands SMC fetched before
          written), the R draws (each LD A,R's A, in order: the rise's re-roll $B88D), the accesses (count + digest), T,
          the marks, the writes (count; the final value of each byte written outside the stack -- the blitters' own
          operands OPS and the glyph rows' bytes left out: the port draws its own digits -- count + digest of 'a:v;'; the
          addresses as [start, length] runs), the glyph rows' stores (count + digest of their addresses, in order), the
          chain walk's reads of the ROM and the marks it makes from them ([reads, marks]: a window parked at $02xx --
          DECLARED, the port ships no ROM); `same` = the replay's accesses are the natural call's
  forced  FORCED calls (declared): $B62C entered on round1_48 / round1_2p48 (the pool emptied, the scene's slots and
          bytes poked; its RET to $8D8F), each with the PROOF marks its path must reach: the pop at every Y & 7, the
          ROM's rows and the cancel's four edges, a Y the erase skips, the seed's busy walk and the full table (slot 13),
          each class (0, 1 frozen / dead / live aligned / live shifted / live unvisited, 2, 3, 4, 5, 12), every count
          of drawn digits and the HIGH copy, the guard out, the mailbox busy, player 2, a chain of two pops in one
          pass, the age pop, the escape, the push both ways and player 2's, the steal (unpaid, paid), the bonus award
          (player 1, player 2).  Each a replay as above, and its program in full ('prog': [o, k] pairs)

ASSERTED: $B62C's entry is BB_ISR_B62C (340) T after the acceptance; a replay's run ends at the RET; each forced call
reaches its PROOF marks; every instruction byte any run fetches before writing that a run writes as data is in SMC.  No
ROM byte: offsets, T, digests and game-RAM bytes (the seeds, the writes) only.

Usage:  python tools/popacc.py [capture|verify] [--jobs N]   -> build/popacc_fixture.json
"""
import sys, os, json, hashlib, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from ctrlmenu import GUARD, Fail
from harness import PC, T, SP, A as RA, H as HR, L as LR
from skoolkit.cmiosimulator import DELAYS_48K
import revealentry as RE
import revealcont as RC
from sparkacc import drive, STATES, FRAMES

FIXTURE = 'build/popacc_fixture.json'
FD = 69888
ENTRY = 0xB62C
RET = 0x8D8F                    # $8D84 LD DE,$8D8F / PUSH DE: the even branch's JP $B62C returns there
STACK = 0x96C1                  # SP at $B62C's entry in the even ISR (natural runs: $96BB..$96C3)
ISR_B62C = 340                  # BB_ISR_B62C: the IM2 response, $8D72's prologue, counters, even branch, gate, JP
BUB = 0xFED8
P1, P2 = 0xFD80, 0xFD8A
ENEMY = 0xFD94
TABLE = 0x5CE0
KEEP = {0xB6D8: 'pop', 0xB6B9: 'esc', 0xB952: 'push', 0xBDBC: 'steal', 0xBD6B: 'bonus'}
MARKS = {0xB6D8: 'pop', 0xB6B9: 'esc', 0xB952: 'push', 0xBDBC: 'steal', 0xBD6B: 'bonus', 0x80FA: 'award',
         0xBF0A: 'bf0a', 0xA469: 'erase', 0x8BC2: 'birth', 0xA437: 'a437', 0xB70A: 'slot13', 0xB721: 'cancel',
         0xB73D: 'paid', 0xB745: 'mail', 0xB7E5: 'mask', 0xB816: 'corpse', 0xB7A1: 'chain', 0xB790: 'tail',
         0x8158: 'abandon', 0x8140: 'copy', 0x815C: 'guard', 0x804F: 'digit', 0xA480: 'path'}
# the self-modified operands the bubble manager's code fetches before writing (each read as an instruction byte): the
# flash toggle $B62D ($B62C LD A,n), the age toggle $B657 ($B656 LD A,n), the beam addend $A431 ($A430 ADD A,n), the
# corpse birth's generator $FE85 (its LD HL,nn operand $FE86 / $FE87 is its state), and the others the pass writes before it
# reads them (the class $B742, the chain centre $B775, the owner $B796, $B7C2, the drift $B880 / $B892, the toucher $B9BC,
# the capture's patch $92DE, the patches $A5D9 / $A480 -- OPS too --, the HUD's suppress $81BB): an input only when fetched
# first
SMC = (0xB62D, 0xB657, 0xA431, 0xFE86, 0xFE87, 0xB742, 0xB775, 0xB776, 0xB796, 0xB7C2, 0xB880, 0xB881, 0xB892, 0xB9BC,
       0x92DE, 0xA5D9, 0xA480, 0x81BB)

# the blitters' own operands -- the $A447 erase's (its patched $A480 / $A5D9 among them: $BF16 and $8C51 patch and restore
# them) and $B9E7's draw's -- rewritten before every run of the code that reads them: not state.  The engine computes them
# and stores none, so the writes' digests leave them out (the earlier gates' OPS); every code byte a run rewrites before it
# runs is here or in SMC (ASSERTED)
OPS = (0xA480, 0xA50B, 0xA584, 0xA5A2, 0xA5A6, 0xA5B1, 0xA5B5, 0xA5BE, 0xA5C2, 0xA5CD, 0xA5D1, 0xA5D9,
       0xBA75, 0xBADB, 0xBADC, 0xBADE, 0xBB4A, 0xBBB2, 0xBBB3, 0xBC01, 0xBC6C, 0xBC6D, 0xBC6F, 0xBCDC)


def dig(parts):
    return hashlib.sha1(''.join(parts).encode()).hexdigest()[:16]


class SMem(RE.SeedMem):
    """SeedMem, and the instruction bytes fetched before any access (`fe`: a self-modified operand is an input) or after
       the run wrote them (`wf`: code rewritten before it runs)"""
    __slots__ = ('fe', 'wf', 'ws')

    def __init__(self, data):
        RE.SeedMem.__init__(self, data)
        self.fe, self.wf, self.ws = set(), set(), set()

    def __getitem__(self, i):
        if self.regs is not None and type(i) is int:
            p = self.regs[PC]
            if p <= i < p + 4:
                if i not in self.seen:
                    self.fe.add(i)
                elif i in self.ws:
                    self.wf.add(i)
        return RE.SeedMem.__getitem__(self, i)

    def __setitem__(self, i, v):
        if self.regs is not None and type(i) is int:
            self.ws.add(i)
        RE.SeedMem.__setitem__(self, i, v)


class Rec:
    """the natural run's recorder (sparkacc.drive's interface): every even ISR's $B62C call, kept when it runs a KEEP"""

    def __init__(self, h):
        self.h = h
        self.st_isr = None
        self.isr_t0 = 0
        self.pf = None
        self.armed = True
        self.ldar = []
        self.C = None
        self.calls, self.kept = [], []
        self.n_calls = 0
        self.ldr = False
        sim = h.sim
        sim.t0, sim.t1 = -1, 1 << 40
        oc = sim.contend

        def cont(t, timings):
            C = self.C
            if C is not None:
                tt, k = t, 0
                for a, ts in timings:
                    if 0x4000 <= a < 0x8000:
                        d = DELAYS_48K[tt % FD]
                        C['acc'].append('%d:%d;' % (tt - C['t0'] - C['D'], k))
                        C['D'] += d
                        tt += d
                    tt += ts
                    k += ts
            return oc(t, timings)
        sim.contend = cont

    def before(self, frame):
        if self.st_isr is None:
            return False
        h, r, mem = self.h, self.h.sim.registers, self.h.sim.memory
        pc = r[PC]
        C = self.C
        if pc == ENTRY and C is None:
            sp = r[SP]
            self.C = C = {'f': frame, 't0': r[T], 'off': r[T] - self.isr_t0, 'ph': self.isr_t0 % FD, 'D': 0, 'acc': [],
                          'marks': [], 'keep': False,
                          'sp': sp, 'ret': mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8), 'state': h.save_state()}
        elif C is not None and pc == C['ret'] and r[SP] == C['sp'] + 2:
            self.end_call()
            return False
        if C is None:
            return False
        if pc in MARKS:
            name = MARKS[pc]
            if pc == 0xB6D8:
                sp = r[SP]
                name += '@%04X' % (mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8))
            C['marks'].append([name, r[T] - C['t0'] - C['D']])
            if pc in KEEP:
                C['keep'] = True
        self.ldr = mem[pc] == 0xED and mem[(pc + 1) & 0xFFFF] == 0x5F
        return True

    def after(self):
        pass

    def end_call(self):
        C = self.C
        self.C = None
        self.n_calls += 1
        if C['off'] != ISR_B62C:
            raise Fail('frame %d: $B62C entered %d T after the acceptance, not %d' % (C['f'], C['off'], ISR_B62C))
        if not C['keep']:
            return
        r = self.h.sim.registers
        Tp = r[T] - C['t0'] - C['D']
        key = dig(C['acc'])
        self.calls.append([C['f'], C['off'], Tp, len(C['acc']), key, C['marks'], C['ph'], C['D']])
        self.kept.append((C['state'], C['sp'], C['ret'], C['f'], key))

    def isr_begin(self, t_, label):
        self.isr_t0 = t_

    def isr_end(self, label):
        if self.C is not None:
            raise Fail('ISR %d: $B62C did not return inside its ISR' % label)


def run_state(st):
    h = RE.new(st)
    rec = Rec(h)
    drive(h, rec, FRAMES, rng=random.Random('popacc:' + st), pool=('O', 'P', 'Q', 'SPACE'))
    return st, rec


def seed_runs(m0, rd, fe):
    runs = []
    for a in sorted(set(a for a in rd if a >= 0x4000) | set(a for a in fe if a in SMC)):
        if runs and runs[-1][0] + len(runs[-1][1]) // 2 == a:
            runs[-1][1] += '%02X' % m0[a]
        else:
            runs.append([a, '%02X' % m0[a]])
    return runs


def replay(state, sp_ret, pokes=(), keep_prog=False):
    """PLAIN (no contention, interrupts off) from the saved state at $B62C to its RET: the seed, the R draws, the
       accesses, T, the marks, the writes (the final value of each byte written outside the stack)"""
    sp0, ret = sp_ret
    h = RE.new('round1_48')
    h.load_state(state)
    m = h.memobj.m
    for a, v in pokes:
        m[a] = v
    m0 = bytes(h.memobj.m)
    rm = SMem(h.memobj.m)
    log = []
    sim = RC.sim_of(h, log, rm)
    r, mem = sim.registers, sim.memory
    if r[PC] != ENTRY:
        raise Fail('a replay not at $B62C')
    rm.regs = r
    t0 = r[T]
    acc, prog, marks, rdraws, glyph = [], [], [], [], []
    crom = [0, 0]
    nlog = 0
    while True:
        p = r[PC]
        if p == ret and r[SP] == sp0 + 2:
            break
        if p in GUARD:
            raise Fail('replay: guard at $%04X' % p)
        tb = r[T]
        hl = r[HR] << 8 | r[LR]
        if p == 0xB782 and hl < 0x4000:
            crom[0] += 1                                 # the chain walk reads the ROM (the window parked at $02xx)
        elif p == 0xB7A1 and hl < 0x4000:
            crom[1] += 1                                 # ...and marks from what it read there
        elif p == 0x8052:
            glyph.append(hl)                             # a glyph row's store ($804F's LD (HL),A)
        if p in MARKS:
            name = MARKS[p]
            if p == 0xB6D8:
                sp = r[SP]
                name += '@%04X' % (m[sp] | (m[(sp + 1) & 0xFFFF] << 8))
            marks.append([name, tb - t0])
        ldr = m[p] == 0xED and m[(p + 1) & 0xFFFF] == 0x5F
        rm.tins[0] = tb
        sim.opcodes[mem[p]]()
        if ldr:
            rdraws.append(r[RA])
        for t in log[nlog:]:
            acc.append('%d:%d;' % (t - t0, t - tb))
            prog.append([t - t0, t - tb])
        nlog = len(log)
        if r[T] - t0 > 10 ** 6:
            raise Fail('replay: no RET')
    rm.regs = None
    gset = set(glyph)
    wa = sorted(set(a for a, t in rm.wr if a not in OPS and a not in gset))
    fin = ['%d:%d;' % (a, m[a]) for a in wa]
    runs = []
    for a in wa:
        if runs and runs[-1][0] + runs[-1][1] == a:
            runs[-1][1] += 1
        else:
            runs.append([a, 1])
    out = {'seed': seed_runs(m0, rm.rd, rm.fe), 'r': rdraws, 'acc': [len(acc), dig(acc)], 'T': r[T] - t0,
           'marks': marks, 'wr': [len(rm.wr), len(fin), dig(fin)], 'wa': runs,
           'gw': [len(glyph), dig(['%d;' % a for a in glyph])], 'crom': crom}
    if keep_prog:
        out['prog'] = prog
        out['fin'] = [[a, m[a]] for a in wa]
    # the SMC census: the instruction bytes fetched before written, the addresses written as data, and the code rewritten
    # before it runs
    return out, (set(rm.fe), set(a for a, t in rm.wr), set(rm.wf))


# ---------------------------------------------------------------------------------------------------- the forced calls
def at_b62c(state_name):
    """a state at $B62C's entry: the world's registers, SP where the even ISR has it ($96C1: its pushes and the JP's
       return address $8D8F -- a saved state's own SP may be borrowed, round1_2p48's is $A447's blit pointer)"""
    h = RE.new(state_name)
    m, r = h.memobj.m, h.sim.registers
    sp = STACK
    m[sp], m[sp + 1] = RET & 0xFF, RET >> 8
    r[SP] = sp
    r[PC] = ENTRY
    return h.save_state(), sp


def slot(k, rec):
    """pokes: pool slot k's ten bytes"""
    return [(BUB + 10 * k + i, v) for i, v in enumerate(rec)]


def empty_pool():
    return [(BUB + 10 * k + 7, 0) for k in range(12)]


def held(x, y, flags=0x8C, cls=0, cell=None, age=0x14, enemy=0):
    """a held bubble (+7 $8C: live, risen, popping) -- its marker pointer `cell` (+2 / +3), its own cell at (x, y) unless
       given ($02xx: the rise's ROM park -- a paid pop's chain window there reads the ROM: DECLARED, chainRomReads)"""
    if cell is None:
        cell = 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)
    return [0x80, 0xC7, cell & 0xFF, cell >> 8, age, x, y, flags, enemy, cls]


def risen(x, y, flags=0x84, cls=0, cell=None, age=0x14, enemy=0):
    """a risen bubble, its marker cell at (x, y) unless given"""
    if cell is None:
        cell = 0xF800 + ((y & 0xF8) << 2) + ((x >> 3) & 0x1F)
    return [0x80, 0xC7, cell & 0xFF, cell >> 8, age, x, y, flags, enemy, cls]


def score(base, value):
    """an 8-digit BCD value at base (LSB first), e.g. score(0xFFE5, 9999990)"""
    s = '%08d' % value
    return [(base + i, int(s[6 - 2 * i:8 - 2 * i], 16)) for i in range(4)]


def table(busy):
    """the sparkle table with `busy` slots at phase 1 (X $40, Y $60), the rest free"""
    out = []
    for k in range(14):
        out += [(TABLE + 2 * k, 0x41 if k < busy else 0), (TABLE + 2 * k + 1, 0x60 if k < busy else 0)]
    return out


def blow(pb, extra=()):
    """a blow request by the player at pb: cadence 1, not dying, debounce clear, the rapid mask not 3, no bonus, no fire"""
    return [(pb + 0x60, 1), (pb + 0x5A, 0x00 if pb == P1 else 0x01), (pb + 0x5F, 0x07), (pb + 0x61, 0)] + list(extra)


def forced_list():
    """(name, base state, pokes, proof marks, marks that must NOT appear) -- declared"""
    E = empty_pool() + table(0)
    out = []
    for k in range(8):                    # the erase at every Y & 7, unpaid -- the marker parked in the ROM (its clear dropped)
        out.append(('y%d' % k, 'round1_48', E + slot(0, held(0x60, 0x50 + k, cell=0x0200 + 0x50 + k)), ['pop@B6C6', 'erase'],
                    ['paid']))
    out += [
        ('rom', 'round1_48', E + slot(0, held(0x80, 0x04)), ['pop@B6C6', 'cancel'], []),       # rows on ROM, cancelled
        ('y0f', 'round1_48', E + slot(0, held(0x70, 0x0F)), ['pop@B6C6', 'cancel'], []),
        ('y10', 'round1_48', E + slot(0, held(0x70, 0x10)), ['pop@B6C6'], ['cancel']),
        ('yae', 'round1_48', E + slot(0, held(0x70, 0xAE)), ['pop@B6C6'], ['cancel']),
        ('yaf', 'round1_48', E + slot(0, held(0x70, 0xAF)), ['pop@B6C6', 'cancel'], []),
        ('yc2', 'round1_48', E + slot(0, held(0x70, 0xC2)), ['pop@B6C6', 'cancel'], ['erase']),   # the erase skipped
        ('right', 'round1_48', E + slot(0, held(0xF8, 0x63)), ['pop@B6C6', 'erase'], []),
        ('cell', 'round1_48', E + slot(0, held(0x68, 0x58, cell=0xF800 + (0x58 >> 3) * 32 + (0x68 >> 3))),
         ['pop@B6C6'], []),
        ('busy3', 'round1_48', empty_pool() + table(3) + slot(0, held(0x60, 0x52)), ['pop@B6C6'], ['slot13']),
        ('full', 'round1_48', empty_pool() + table(14) + slot(0, held(0x60, 0x53)), ['pop@B6C6', 'slot13'], []),
        ('two', 'round1_48', E + slot(0, held(0x60, 0x54)) + slot(5, held(0x90, 0x75)), ['pop@B6C6'], []),
        # paid pops: player 1's, each class, the digits drawn (the new score's length), the HIGH copy
        ('c0', 'round1_48', E + slot(0, held(0x60, 0x50, flags=0x8E)) + score(0xFFE5, 0), ['paid', 'award', 'digit'],
         []),
        ('c2', 'round1_48', E + slot(0, held(0x60, 0x51, flags=0x8E, cls=2)) + score(0xFFE5, 0), ['award'], []),
        ('c3', 'round1_48', E + slot(0, held(0x60, 0x52, flags=0x8E, cls=3)) + score(0xFFE5, 123), ['award'], []),
        ('c4', 'round1_48', E + slot(0, held(0x60, 0x53, flags=0x8E, cls=4)) + score(0xFFE5, 4567), ['award'], []),
        ('c5', 'round1_48', E + slot(0, held(0x60, 0x54, flags=0x8E, cls=5)) + score(0xFFE5, 89012), ['mask', 'award'],
         []),
        ('c12', 'round1_48', E + slot(0, held(0x60, 0x55, flags=0x8E, cls=12)) + score(0xFFE5, 345678),
         ['mask', 'award'], []),
        ('d7', 'round1_48', E + slot(0, held(0x60, 0x56, flags=0x8E, cls=2)) + score(0xFFE5, 9999990), ['award'], []),
        ('d8', 'round1_48', E + slot(0, held(0x60, 0x57, flags=0x8E, cls=2)) + score(0xFFE5, 89999990) +
         score(0xFFE1, 99999999), ['award', 'abandon'], []),
        ('d0', 'round1_48', E + slot(0, held(0x60, 0x50, flags=0x8E, cls=2)) + score(0xFFE5, 99999990) +
         score(0xFFE1, 99999999), ['award', 'abandon'], ['digit']),                    # the wrap: no digit drawn
        ('high', 'round1_48', E + slot(0, held(0x60, 0x50, flags=0x8E, cls=2)) + score(0xFFE5, 19990) +
         score(0xFFE1, 20000), ['award', 'copy'], []),
        ('guard', 'round1_48', E + slot(0, held(0x60, 0x51, flags=0x8E)) + [(P1 + 7, 0x61)], ['award', 'guard'],
         ['digit']),
        ('mail', 'round1_48', E + slot(0, held(0x60, 0x52, flags=0x8E, cls=2)) + [(0xFFF9, 2)], ['award'], ['mail']),
        ('p2', 'round1_2p48', E + slot(0, held(0x60, 0x53, flags=0x9E, cls=2)) + score(0xFFE9, 450), ['award'], []),
        # class 1: the corpse birth on the enemy at (IY+8) -- frozen / dead ($A437), live (its erase: aligned, shifted),
        # live on its first visit (bit 6 clear: none)
        ('frozen', 'round1_48', E + slot(0, held(0x60, 0x54, flags=0x8E, cls=1, enemy=0)) + [(ENEMY + 7, 0xC8)],
         ['corpse', 'a437'], []),
        ('dead', 'round1_48', E + slot(0, held(0x60, 0x55, flags=0x8E, cls=1, enemy=3)) + [(ENEMY + 37, 0x00)],
         ['corpse', 'a437'], []),
        ('live_al', 'round1_48', E + slot(0, held(0x60, 0x56, flags=0x8E, cls=1, enemy=1)) +
         [(ENEMY + 17, 0xC0), (ENEMY + 12, 0x5A), (ENEMY + 13, 0x80)], ['corpse', 'erase'], ['a437']),
        ('live_sh', 'round1_48', E + slot(0, held(0x60, 0x57, flags=0x8E, cls=1, enemy=1)) +
         [(ENEMY + 17, 0xC0), (ENEMY + 12, 0x5B), (ENEMY + 13, 0x84)], ['corpse', 'erase'], ['a437']),
        ('live_new', 'round1_48', E + slot(0, held(0x60, 0x50, flags=0x8E, cls=1, enemy=1)) + [(ENEMY + 17, 0x80)],
         ['corpse'], ['a437']),
        # a chain: the popped bubble's 4x4 window holds slot 3's marker (12 - 3 = 9): it is marked, and pops later in
        # the same pass
        ('chain', 'round1_48', E + slot(0, held(0x60, 0x60, flags=0x8E, cls=2,
                                                 cell=0xF800 + (0x60 >> 3) * 32 + (0x60 >> 3))) +
         slot(3, risen(0x68, 0x60, cell=0xF800 + (0x60 >> 3) * 32 + (0x68 >> 3))) +
         [(0xF800 + (0x60 >> 3) * 32 + (0x68 >> 3), 9)], ['chain', 'award'], []),
        # the age pop: a risen empty bubble at +4 $7F with the toggle due ($B657 = 1: the INC runs)
        ('age', 'round1_48', E + slot(0, risen(0x70, 0x60, age=0x7F)) + [(0xB657, 1)], ['pop@B66C', 'erase'], []),
        ('age_cancel', 'round1_48', E + slot(0, risen(0x70, 0x0C, age=0x7F)) + [(0xB657, 1)], ['pop@B66C', 'cancel'],
         []),
        # the escape: a holding bubble (kind 1) at +4 $FF with the toggle due -- the wrap releases its enemy and erases it
        ('escape', 'round1_48', E + slot(0, risen(0x70, 0x60, cls=1, age=0xFF, enemy=0)) + [(0xB657, 1)], ['esc'], []),
        ('escape5', 'round1_48', E + slot(4, risen(0x48, 0x63, cls=1, age=0xFF, enemy=2)) + [(0xB657, 1)], ['esc'],
         []),
        # the push: a risen bubble 14 px right of player 1, who faces right and presses right ($FD88 bit 2) -- and
        # left (12 px left, facing left, bit 3); player 2's on the two-player world
        ('push_r', 'round1_48', E + slot(0, risen(0x26, 0xA8)) + [(P1 + 7, 0xE1), (P1 + 8, 0x04)], ['push'], []),
        ('push_l', 'round1_48', E + slot(0, risen(0x40, 0xA8)) + [(P1 + 5, 0x4C), (P1 + 7, 0xE0), (P1 + 8, 0x08)],
         ['push'], []),
        ('push_p2', 'round1_2p48', E + slot(2, risen(0xCA, 0xA8)) + [(P2 + 7, 0xC0), (P2 + 8, 0x08)], ['push'], []),
        # the steal: a full pool (twelve risen, the oldest of kind 0 -- slot 7, +4 $70 -- popped by player 1's blow) --
        # unpaid, and with the stolen bubble's pop pending and paid (+7 bits 3 / 1: class 0, one point)
        ('steal', 'round1_48', empty_pool() + table(0) + sum((slot(k, risen(0x30 + 12 * k, 0x40 + 4 * k,
                                                                             age=0x70 if k == 7 else 0x20 + k))
                                                               for k in range(12)), []) + blow(P1),
         ['steal', 'pop@BDBF', 'erase'], []),
        ('steal_paid', 'round1_48', empty_pool() + table(0) + sum((slot(k, risen(0x30 + 12 * k, 0x40 + 4 * k,
                                                                                  flags=0x8E if k == 7 else 0x84,
                                                                                  age=0x70 if k == 7 else 0x20 + k))
                                                                    for k in range(12)), []) + blow(P1),
         ['steal', 'pop@BDBF', 'award'], []),
        # the bonus: player 1's last power-up type 15 -- $0050 on every blow, through $80FA -- and player 2's
        ('bonus', 'round1_48', E + blow(P1, [(P1 + 0x61, 15)]) + score(0xFFE5, 340), ['bonus', 'award', 'digit'], []),
        ('bonus_p2', 'round1_2p48', E + blow(P2, [(P2 + 0x61, 15)]) + score(0xFFE9, 7), ['bonus', 'award'], []),
        # two events in one pass, each clock carrying the first's callee T: a pushed bubble that then age-pops, and one
        # that then escapes ($B656's clock: the push's erase in the rise's callees); two pushes of one bubble -- player
        # 2's tests read the registers player 1's push left (B = 2, C = the wind 2 at the bubble's cell), so player 2 at
        # ($10, $10) pushes too (its clock: player 1's erase); both players' bonuses (player 2's clock: player 1's award);
        # player 1's bonus and then its steal (the steal's pop: the award before it)
        ('push_age', 'round1_48', E + slot(0, risen(0x26, 0xA8, age=0x7F)) + [(P1 + 7, 0xE1), (P1 + 8, 0x04), (0xB657, 1)],
         ['push', 'pop@B66C'], []),
        ('push_esc', 'round1_48', E + slot(0, risen(0x26, 0xA8, cls=1, age=0xFF, enemy=0)) +
         [(P1 + 7, 0xE1), (P1 + 8, 0x04), (0xB657, 1)], ['push', 'esc'], []),
        ('push2', 'round1_2p48', E + slot(0, risen(0x26, 0xA8)) + [(P1 + 5, 0x18), (P1 + 6, 0xA8), (P1 + 7, 0xC1), (P1 + 8, 0x04),
                                                                   (P2 + 5, 0x10), (P2 + 6, 0x10), (P2 + 7, 0xC0), (P2 + 8, 0x08),
                                                                   (0xF800 + (0xA8 >> 3) * 32 + (0x26 >> 3), 0x40)],
         ['push', 'push'], []),
        ('bonus_both', 'round1_2p48', E + blow(P1, [(P1 + 0x61, 15)]) + blow(P2, [(P2 + 0x61, 15)]) + score(0xFFE5, 120) +
         score(0xFFE9, 30), ['bonus', 'bonus'], []),
        ('bonus_steal', 'round1_48', empty_pool() + table(0) + sum((slot(k, risen(0x30 + 12 * k, 0x40 + 4 * k,
                                                                                   age=0x70 if k == 7 else 0x20 + k))
                                                                     for k in range(12)), []) +
         blow(P1, [(P1 + 0x61, 15)]) + score(0xFFE5, 980), ['bonus', 'steal', 'pop@BDBF'], []),
    ]
    return out


def forced_job(spec):
    name, base, pokes, proof, absent = spec
    state, sp = at_b62c(base)
    x, census = replay(state, (sp, RET), pokes, keep_prog=True)
    got = [n for n, o in x['marks']]
    miss = [p for p in set(proof) if got.count(p) < proof.count(p)]   # a name given twice: at least twice
    bad = [p for p in absent if p in got]
    if miss or bad:
        raise Fail('forced %s: proof %s not reached, %s reached' % (name, miss, bad))
    x.update({'forced': name, 'base': base, 'pokes': pokes})
    return x, census


def world_job(st):
    tag, rec = run_state(st)
    reps, census = [], []
    for state, sp, ret, f, key in rec.kept:
        x, cs = replay(state, (sp, ret))
        x['f'] = f
        x['same'] = x['acc'][1] == key
        reps.append(x)
        census.append(cs)
    return {'tag': tag, 'n_calls': rec.n_calls, 'calls': rec.calls, 'replays': reps}, census


def capture(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(world_job, STATES))
        fres = list(ex.map(forced_job, forced_list()))
    worlds = {}
    fe_all, wr_all, wf_all = set(), set(), set()
    tot = {'calls': 0, 'kept': 0, 'same': 0}
    for x, census in res:
        worlds[x['tag']] = x
        for fe, wr, wf in census:
            fe_all |= fe
            wr_all |= wr
            wf_all |= wf
        tot['calls'] += x['n_calls']
        tot['kept'] += len(x['calls'])
        tot['same'] += sum(1 for y in x['replays'] if y['same'])
        print('%-12s %6d calls, %3d kept' % (x['tag'], x['n_calls'], len(x['calls'])), flush=True)
    forced = []
    for x, (fe, wr, wf) in fres:
        fe_all |= fe
        wr_all |= wr
        wf_all |= wf
        forced.append(x)
        print('forced %-10s %5d accesses, T %6d, marks %s' % (x['forced'], x['acc'][0], x['T'],
                                                              sorted(set(n for n, o in x['marks']))), flush=True)
    smc = sorted(a for a in fe_all & wr_all if a >= 0x4000)
    missing = [a for a in smc if a not in SMC]
    if missing:
        raise Fail('instruction bytes fetched before written that a run writes, not in SMC: %s'
                   % ' '.join('$%04X' % a for a in missing))
    rew = sorted(a for a in wf_all if a not in OPS and a not in SMC)
    if rew:
        raise Fail('code rewritten before it runs, in neither OPS nor SMC: %s' % ' '.join('$%04X' % a for a in rew))
    tot['forced'] = len(forced)
    print('total:', tot)
    return {'meta': {'tool': 'tools/popacc.py', 'no_rom_bytes': True,
                     'note': "the even ISR's $B62C wherever it pops, erases an escape or a push, steals or pays a bonus: "
                             'access programs (plain offsets from its entry), marks, seeds, writes; natural and forced'},
            'frames': FRAMES, 'smc': list(SMC), 'smc_seen': smc, 'ops': list(OPS), 'ops_seen': sorted(wf_all & set(OPS)), 'isr_b62c': ISR_B62C, 'ret': RET,
            'worlds': worlds, 'forced': forced, 'total': tot}


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
