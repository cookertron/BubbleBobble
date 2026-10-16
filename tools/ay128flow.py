"""M10.0c -- THE 128K BRANCH'S FLOW ON THE PORT'S CLOCK: the real load as the page drives it, on the M10 machine,
frame by frame -- every request, wait, tick and AY write, every ISR's T and its sound hook's, every main-loop pass.
The oracle M10.2's gates are drawn from (docs/M10-PLAN.md section 4, M10.0).

THE MACHINE (M10-PLAN section 2, option A: the 128K branch on the 48K clock): boot.pkl's $F5BC -- the real Bleepload
load's hand-over, the page's own start -- on the 48K harness, contended, with the opt-in paging port and AY
(Harness(paging=$10)), and:
  - THE 128K LOAD'S 14 BYTES laid at $F5BC: every byte outside the display where build/boot128.z80's 48K view differs
    from build/boot48.z80's (ASSERTED: those 14) -- BANKM $5B5C = $10 (the one the branch reads: $95F5 copies it to
    $9AE7, the hooks page with ($9AE7) | 1), $6000 = $10 (the loader's copy of it) and twelve system variables in
    $5C0A..$5CC8, among them REPPER $5C0A = 2 (the 48K load's 5): the front end's key repeat, the ROM's KEYBOARD
    reading it (the engine's BB_MENU.REPPER is the 48K's).  The 128K load's R (23, not 11) is NOT laid: a register.
  - THE PROBE ANSWERS $80: at $FAE1 BC := $0759, the 128K's count (the 48K counts $075E), so the machine's own compare
    takes $FAEF LD A,$80 / JP $FA3B and the 128K exit's trampoline T ($FA3B..$FA3F, $FA67) -- DECLARED in the layer.
    With `skip` (the page's skipProbe, ADDED and ON by default) the probe is skipped as the port skips it: at $F5C9 the
    CALL is not made, A := $80, PC := $F5CC, at that T.

THE DRIVE (sparkacc's): every instruction executed (no HALT skip), keys applied at each ISR's END (in the front end's
scan, held to the scan's end) -- and, in the pause's spin ($8FF6 DI .. $9009 EI: no interrupt for frames), at each
frame boundary (pausespin's convention; applied anywhere IFF is 0 it moved the front end: the probe's phase 52,024 ->
2,240) -- pokes at ISR ends (`pokes`: {label: [(addr, value or fn(ram)), ...]}, each applied value recorded),
frames counted from the start state's frame (frame k = the k-th boundary).  An ISR's label is the frame whose
boundary it was taken at.

RECORDS (lists of rows; t = T mod 69,888 at the event, `frame` the drive's):
  frames   [frame, busy $8E06, cur $FED4, cad $8DE0, hurry $904D, IFF, $8DB7, alive $FECA, paged]  at each boundary
           BEFORE that frame's interrupt (IFF 0 = the frame's interrupt is lost); STORED only where it changes
  isrs     [label, acceptance t, T to the return, hook T or None, ticked 0/1]   (the hook: $8D8F CALL $8DC4 .. $8D92)
  ticks    [frame, t, T, A]       $CF80 entry .. its return
  ereqs    [frame, t, n, T, A]    $D167 entry .. its return (inside $8E0A)
  reqs     [frame, t, site, A, cur, iff, T]   $8E0A entry (A = the sound, cur = $FED4 then) .. its return; site = the
           CALL / JP that reached it, or the wait's site when a $8E05 wait fell into it
  waits    [site, frame, t, A, busy0, turns, frame_end, t_end]   $8E05 .. the fall into $8E0A
  hooks    [label, frame, t, cur $FED4, hurry $904D, $8DB7, alive $FECA, cad $8DE0, busy $8E06]  at each $8D8F CALL
           $8DC4 inside an ISR (t its first T): the hook's inputs as it reads them -- the boundary's frames row can be
           stale by then, the ISR's passes run first (p1's ISR 1697: the player's respawn at $ABA8, in $AA60's pass,
           clears the HURRY latch before the hook, and the main line's $9059 sets it again before the next boundary)
  ay       [frame, t, reg, val]   every AY data write ($BFFD), t the OUT's first T
  p7ffd    [frame, t, pc, val]
  passes   [frame, t]             each $8D0C (the main loop's top) outside an ISR
  ldar     [frame, pc, A]         every LD A,R (the engine's stand-in is fed these)
  spk      [frame, t, v]          every OUT to the ULA that changes bit 4 (the beeper's edges)
  marks    {name: [frame, t]}     the first arrival at each named PC (MARKS)

SCENES (SCENES below; each from boot.pkl's $F5BC with the real load's control select, CTRL: P1 KEYBOARD, P2 SINCLAIR;
`window`: rows from that frame on -- before it the scene is p1's or idle's):
  p1      '1' at 450: the cold start (3, the 81-frame wait, 5), the title, 7, the round-1 wait (516..739, RIGHT held
          560..599: the player walks while the enemies stand), 1 and its 2-in-3 cadence, play, the pause (SYM; 0) and
          the unpause (CAPS; 1 re-requested with the interrupts off: the theme restarts), HURRY UP (poked at 1400) at
          full rate from 1462, Boris
  p2      '2' at 450: the 2-player start (the round-1 wait 221 frames)
  idle    '1' and no key: deaths (no request), game over at 2272 ($8CE4: 5), the title again
  skip    the page's skipProbe at its natural phase (52,024): the hand-over at frame 88, the wait 81 frames
  potion  the potion poked at 840 (B's poke): $891A's 3, the treasure room's wait (82), 4
  heart   the HEART: $887D's 4
  extend  EXTEND: $94D5's 2, $953C's wait (182), 3; the next round's $98FC 1
  boss    bossfree's route (($8609) = $4F, ($FECD) = 1 at 1240): $9901's 6; the HP poked 0 at 1700: $8E77's 3, $8E8A's
          wait (82; its request a no-op), $8E95's (11), 2; round 81: 1, $891A's 3, $8991's wait (81), 4
  alive7  the same route to round 10: the alive-7 rule's full rate under 1 from 2075
skip_sweep  THE PAGE'S SKIP AT 64 PHASES of $F5C9 (every 1,092 T): [phase, the $8CD7 wait's frames, request 5's frame,
          $970E's, the busy byte at the wait, its turns].  MEASURED: 19 of 64 (27,300..46,956) do not wait -- the busy
          byte is still 1 (no tick between the request and the wait: one turn) -- so 3 is replaced by 5 at once and the
          title comes 4 frames on, not 85.  The probe's
          own hand-over is pinned at phase 1,051 ($F5CC; its HALT and FRAMES count): a waiting phase.
di_window A TAKEN REQUEST WITH THE INTERRUPTS ON ($8E10 DI .. $8E28 EI / $8E29 RET, 548 T on this clock): the boundary
          placed o T after the DI (FORCED, only the clock moved): [o, acceptance T from the boundary, the label's frame
          offset].  MEASURED: taken at o <= 0 (before the DI), LOST at o = 1..516, taken at the window's end at 517..
hook      per scene, the sound hook's T per ISR by the gate's state: MEASURED theme ticks ~617 T (383..2,549), theme skips
          150..172, full-rate ticks ~410..490 (291..3,028) -- the 2-in-3 theme ~464 T an ISR on average (D's open
          question 1; C's +434 / +517 were the same machine).

No ROM byte: T, phases, game-RAM bytes and the engine's AY writes only.
Usage:  python tools/ay128flow.py capture | verify       -> build/ay128flow_fixture.json (~5 min, MATCH)
        python tools/ay128flow.py scene NAME | timeline [frames] | explore1p [frames]      (explore)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import PC, T, SP, IFF, A as RA, B as RB, C as RC
from skoolkit.snapshot import Snapshot
import ctrlmenu as cm
from ctrlmenu import world, expand, Fail
import passacc as pa

FIXTURE = 'build/ay128flow_fixture.json'             # M10.2a's gates read it (moved from build/pending/, TRAPS #342)
FD = 69888
BC128 = 0x0759                                       # the probe's count on the 128K (B's harness, M10-PLAN 1.1)
MARKS = {0xF5C9: 'probe', 0xFAE1: 'probe_end', 0xFAEF: 'probe_128', 0xFAF4: 'probe_48', 0xF5CC: 'handover',
         0x8CC3: 'cold', 0x969A: 'leg48', 0x96B3: 'leg128', 0x8CCA: 'cold_end', 0x8CD2: 'delay9575', 0x8CD7: 'wait_cold',
         0x8CDA: 'cold_done', 0x96DF: 'reset_half', 0x970E: 'title_ei', 0x9768: 'title_ring', 0x97B4: 'req7_start',
         0x98F5: 'r1_wait', 0x8D0C: 'main_loop', 0x8FF3: 'pause', 0x9006: 'unpause', 0x8CE4: 'game_over'}
HOOK_IN, HOOK_OUT = 0x8D8F, 0x8D92
REQ, WAIT, TICK, EREQ = 0x8E0A, 0x8E05, 0xCF80, 0xD167


def load128_bytes():
    """the 14 bytes outside the display where the 128K load differs from the 48K load: {addr: value_128}"""
    s128, s48 = Snapshot.get('build/boot128.z80'), Snapshot.get('build/boot48.z80')
    r = s128.ram(-1)
    b = [r[i * 0x4000:(i + 1) * 0x4000] for i in range(8)]
    v128 = bytes(b[5]) + bytes(b[2]) + bytes(b[s128.out7ffd & 7])
    v48 = bytes(s48.ram(-1))
    d = {0x4000 + i: v128[i] for i in range(0x1B00, 0xC000) if v48[i] != v128[i]}
    if sorted(d) != [0x5B5C, 0x5C0A, 0x5C3B, 0x5C5B, 0x5C74, 0x5C75, 0x5C78, 0x5C7F, 0x5C81, 0x5CC5, 0x5CC6, 0x5CC7,
                     0x5CC8, 0x6000] or d[0x5B5C] != 0x10 or any(v128[i] != v48[i] for i in range(0x1B00)):
        raise Fail('the 128K load no longer differs from the 48K load in the 14 bytes M10-PLAN 1.1 names')
    return d


def machine():
    """the M10 machine at boot.pkl's $F5BC: (h, m, r)"""
    h, m, r = world('boot')
    if r[PC] != 0xF5BC:
        raise Fail('boot.pkl is not at $F5BC')
    h.enable_paging(0x10)
    for a, v in load128_bytes().items():
        m[a] = v
    return h, m, r


class Flow:
    """the drive and its records (the module docstring)"""

    def __init__(self, h, keyf=None, pokes=None, skip=False, force_bc=True):
        self.h, self.keyf, self.pokes, self.skip, self.force_bc = h, keyf, pokes or {}, skip, force_bc
        self.r, self.m = h.sim.registers, h.memobj.m
        self.frames, self.isrs, self.ticks, self.ereqs, self.reqs, self.waits = [], [], [], [], [], []
        self.hooks = []
        self.ay, self.p7ffd, self.passes, self.ldar, self.spk, self.marks = [], [], [], [], [], {}
        self.applied = []
        self.stop_pc = None         # run() returns with PC here, before it runs (one run() a Flow: keys restart at 0)
        self.frame = 0
        self.base = self.r[T] // FD
        self.isr = None             # (return PC, SP, label, acceptance T)
        self.hook = None
        self.stack = []             # open CALL-level events: (kind, return pc, sp, row, T0)
        self.wait = None
        self.prev = None
        self.outfe = h.ports.__dict__.get('_m10_outfe', 0)
        h.ports.record_writes = True
        del h.ports.writes[:]
        del h.paging.ay_log[:]
        del h.paging.p7ffd[:]

    def ft(self, t_abs):
        return [t_abs // FD - self.base, t_abs % FD]

    def ret_of(self):
        m, sp = self.m, self.r[SP]
        return m[sp] | (m[(sp + 1) & 0xFFFF] << 8), sp

    def site_of(self, target):
        """the CALL / JP (any condition) that reached `target`: prev's when it jumped there, else ret - 3's"""
        m, prev = self.m, self.prev
        if prev is not None and m[prev] in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA) and \
                m[(prev + 1) & 0xFFFF] | (m[(prev + 2) & 0xFFFF] << 8) == target:
            return prev
        ret, sp = self.ret_of()
        c = (ret - 3) & 0xFFFF
        if m[c] in (0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC):
            return c
        return -1

    def on_pc(self, pc):
        r, m = self.r, self.m
        if pc in MARKS and MARKS[pc] not in self.marks:
            self.marks[MARKS[pc]] = self.ft(r[T])
        if pc == 0xF5C9 and self.skip:
            r[RA], r[PC] = 0x80, 0xF5CC                      # the page's skipProbe, answering $80 at once
            return True
        if pc == 0xFAE1 and self.force_bc:
            r[RB], r[RC] = BC128 >> 8, BC128 & 0xFF
        if pc == HOOK_IN and self.isr is not None:
            self.hook = [r[T], len(self.ticks)]
            self.hooks.append([self.isr[2], *self.ft(r[T]), m[0xFED4], m[0x904D], m[0x8DB7], m[0xFECA], m[0x8DE0],
                               m[0x8E06]])
        elif pc == HOOK_OUT and self.hook is not None:
            self.isr_hook = (r[T] - self.hook[0], int(len(self.ticks) > self.hook[1]))
            self.hook = None
        if pc == WAIT and self.wait is None:
            self.wait = [self.site_of(WAIT), *self.ft(r[T]), r[RA], m[0x8E06], 0]
        if pc == WAIT:
            self.wait[5] += 1
        if pc == REQ:
            if self.wait is not None:
                site = self.wait[0]
                self.waits.append(self.wait + self.ft(r[T]))
                self.wait = None
            else:
                site = self.site_of(REQ)
            row = [*self.ft(r[T]), site, r[RA], m[0xFED4], r[IFF], None]
            self.reqs.append(row)
            self._open('req', row, 6)
        elif pc == TICK:
            row = [*self.ft(r[T]), None, None]
            self.ticks.append(row)
            self._open('tick', row, 2, 3)
        elif pc == EREQ:
            row = [*self.ft(r[T]), r[RA], None, None]
            self.ereqs.append(row)
            self._open('ereq', row, 3, 4)
        if pc == 0x8D0C and self.isr is None:
            self.passes.append(self.ft(r[T]))
        return False

    def _open(self, kind, row, ti, ai=None):
        ret, sp = self.ret_of()
        self.stack.append((ret, (sp + 2) & 0xFFFF, row, self.r[T], ti, ai))

    def _close(self, pc):
        r = self.r
        while self.stack and self.stack[-1][0] == pc and self.stack[-1][1] == r[SP]:
            ret, sp, row, t0, ti, ai = self.stack.pop()
            row[ti] = r[T] - t0
            if ai is not None:
                row[ai] = r[RA]

    def boundary(self):
        m, r = self.m, self.r
        self.frames.append([self.frame, m[0x8E06], m[0xFED4], m[0x8DE0], m[0x904D], r[IFF], r[PC], m[0x8DB7],
                            m[0xFECA], self.h.paging.cur])

    def run(self, until):
        h, r, m = self.h, self.r, self.m
        sim, ops = h.sim, h.sim.opcodes
        fd, ia = h.frame_duration, h.int_active
        assert fd == FD
        nb = (r[T] // fd + 1) * fd
        keyf = self.keyf
        in_scan, pending = False, None
        if keyf:
            cm.keys(h, keyf(0))
        while self.frame <= until:
            pc = r[PC]
            if r[T] >= nb:
                self.frame += 1
                nb += fd
                self.boundary()
                if keyf and not r[IFF] and 0x8FF6 <= r[PC] <= 0x9009:
                    cm.keys(h, keyf(self.frame))          # the pause's spin (DI): the frame's keys from its boundary
            isr = self.isr
            if isr is not None and pc == isr[0] and r[SP] == isr[1]:
                L = isr[2]
                if keyf:
                    if in_scan:
                        pending = keyf(L)
                    else:
                        cm.keys(h, keyf(L))
                for a, v in self.pokes.get(L, ()):
                    v = v(m) if callable(v) else v
                    m[a] = v
                    self.applied.append([L, a, v])
                hk = getattr(self, 'isr_hook', None)
                self.isrs.append([L, isr[3] % fd, r[T] - isr[3], hk[0] if hk else None, hk[1] if hk else 0])
                self.isr_hook = None
                self.isr = None
            if pc == 0xF7B9 and in_scan:
                in_scan = False
                if pending is not None:
                    cm.keys(h, pending)
                    pending = None
            if pc == 0xF7B8:
                in_scan = True
            if self.stack and pc == self.stack[-1][0]:
                self._close(pc)
            if pc == self.stop_pc:
                break
            if self.on_pc(pc):
                continue
            self.prev = pc
            op = m[pc]
            ops[op]()
            if op == 0xED and m[(pc + 1) & 0xFFFF] == 0x5F:
                self.ldar.append([self.frame, pc, r[RA]])
            if r[IFF] and r[T] % fd < ia:
                b0, s0, t_ = r[PC], r[SP], r[T]
                if sim.accept_interrupt(r, m, pc):
                    if self.isr is not None:
                        raise Fail('an interrupt inside an ISR at frame %d' % self.frame)
                    self.isr = (b0, s0, self.frame + (1 if r[T] >= nb else 0), t_)
        self.collect()

    def collect(self):
        h = self.h
        for t_abs, pc, reg, val in h.paging.ay_log:
            self.ay.append([*self.ft(t_abs), reg, val])
        del h.paging.ay_log[:]
        for t_abs, pc, val, applied in h.paging.p7ffd:
            self.p7ffd.append([*self.ft(t_abs), pc, val])
        del h.paging.p7ffd[:]
        fe = self.outfe
        for t_abs, port, val in h.ports.writes:
            if port & 1 == 0:
                if (val ^ fe) & 0x10:
                    self.spk.append([*self.ft(t_abs), val & 0x10])
                fe = val
        self.outfe = fe
        del h.ports.writes[:]
        del cm.OUTS[:]


def script_keyf(script):
    seq = expand(script)
    return lambda L: seq[L] if L < len(seq) else []


CTRL = pa.SCRIPT[:14]          # the real load's control select: P1 KEYBOARD (O P SPACE Q, Y), P2 SINCLAIR ('2'): 82 frames


def explore(script, frames, skip=False, pokes=None):
    h, m, r = machine()
    f = Flow(h, keyf=script_keyf(script), skip=skip, pokes=pokes)
    f.run(frames)
    print('marks', {k: v for k, v in sorted(f.marks.items(), key=lambda kv: kv[1])})
    print('reqs', f.reqs)
    print('waits', f.waits)
    print('applied', f.applied)
    print('ticks', len(f.ticks), 'ay', len(f.ay), 'isrs', len(f.isrs), 'passes', len(f.passes), 'spk', len(f.spk),
          'ldar', len(f.ldar), 'p7ffd', len(f.p7ffd), 'unsupported', h.paging.unsupported)
    return f


# ------------------------------------------------------------------ the scenes
# The no-skip timeline (measured, explore1p): the probe $F5C9 at 88, the hand-over at 344, request 3 at 347, the
# cold-start wait 348..429, request 5 at 429, the title's ring at 438; '1' at 450 -> request 7 at 450, the round-1 wait
# $98F5 516..739, request 1 and the main loop at 739.
IDLE_TO_TITLE = 368                                    # CTRL's 82 frames + 368 = '1' at 450, the title up since 438
PLAY = pa.SCRIPT[16:]                                  # the real load's play keys after '1' (427 frames)


def item(kind):
    """an item of `kind` laid in the item block's slot 0 at player 1's cell (agent B's declared poke)"""
    return [(0x9603, lambda m: (m[0xFD85] & 0xF0) | kind), (0x9604, lambda m: (m[0xFD86] & 0xF8) | 1)]


def hurry60(m):
    """the play timer $8DBD := the round's threshold ($745C) - 60: HURRY UP in 60 timer steps (agent B's poke)"""
    return (m[0x745C] | m[0x745D] << 8) - 60


SCENES = {
    # the faithful load, player 1: the cold start, the title, 7, the round-1 wait with the player walking (RIGHT held),
    # 1 and its 2-in-3 cadence, play, the pause (SYM, CAPS), HURRY UP (poked) at full rate, Boris
    'p1': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1']), (107, []), (40, ['P']), (160, [])] + PLAY +
               [(3, []), (3, ['SYM']), (60, []), (3, ['CAPS']), (100, [])],
               pokes={1400: [(0x8DBD, lambda m: hurry60(m) & 0xFF), (0x8DBE, lambda m: hurry60(m) >> 8)]},
               frames=1900, window=0),
    # two players: '2' at the title
    'p2': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['2'])], frames=1100, window=0),
    # player 1 idle: deaths (no request), game over ($8CE4: 5), the title again
    'idle': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])], frames=3300, window=0),
    # the page's skipProbe (ADDED, ON by default): the hand-over at $F5C9's T, the cold start from that phase
    'skip': dict(script=CTRL + [(118, []), (3, ['1'])], skip=True, frames=800, window=0),
    # player 1 idle, then at an ISR end of play: the potion (3, the treasure room's wait, 4), the HEART (4), EXTEND
    # (2, the wait, 3) -- agent B's declared pokes
    'potion': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])], pokes={840: item(12)}, frames=1700, window=830),
    'heart': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])], pokes={840: item(10)}, frames=1300, window=830),
    'extend': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])], pokes={840: [(0xFDE3, 0x3F), (0xFED5, 1)]},
                   frames=1700, window=830),
    # bossfree's route to round 80: ($8609) = $4F, ($FECD) = 1 at an ISR end 500 frames into play (past the comparator
    # pair's decay), so $8D12 advances to 80: 6 at $9901; later the boss's HP ($9F62) := 0: $8E55's defeat (3, the
    # waits for 3 and for 2), the advance to 81
    'boss': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])],
                 pokes={1240: [(0x8609, 0x4F), (0xFECD, 1)], 1700: [(0x9F62, 0)]}, frames=2400, window=1230),
    # the alive-7 rule ($8DB7 >= 3 and ($FECA) == 7: full rate under 1): round 10 by the same route
    'alive7': dict(script=CTRL + [(IDLE_TO_TITLE, []), (3, ['1'])], pokes={1240: [(0x8609, 9), (0xFECD, 1)]},
                   frames=2500, window=1230),
}


def run_scene(name):
    sc = SCENES[name]
    h, m, r = machine()
    f = Flow(h, keyf=script_keyf(sc['script']), skip=sc.get('skip', False), pokes=sc.get('pokes'))
    f.run(sc['frames'])
    return f


def records(f, window):
    """the scene's rows from frame `window` on; frames rows only where their state changes"""
    W = lambda rows, i=0: [x for x in rows if x[i] >= window]
    fr, last = [], None
    for x in f.frames:
        key = x[1:6] + x[7:]
        if x[0] >= window and key != last:
            fr.append(x[:6] + x[7:])
            last = key
    return {'window': window, 'marks': f.marks, 'applied': f.applied, 'frames': fr, 'isrs': W(f.isrs),
            'ticks': W(f.ticks), 'ereqs': W(f.ereqs), 'reqs': W(f.reqs), 'waits': [x for x in f.waits if x[1] >= window],
            'hooks': W(f.hooks),
            'ay': W(f.ay), 'p7ffd': W(f.p7ffd), 'passes': W(f.passes), 'ldar': W(f.ldar), 'spk': W(f.spk),
            'unsupported': f.h.paging.unsupported}


def hook_costs(f):
    """the sound hook's T per ISR, by the gate's state at the ISR (the frames row before it): the 2-in-3 theme (cur 1,
       no hurry), full rate (any other sound or the hurry latch), skipped frames counted apart"""
    st = {x[0]: x for x in f.frames}
    out = {}
    for L, t, T_, hk, ticked in f.isrs:
        if hk is None:
            continue
        x = st.get(L)
        if x is None:
            continue
        kind = ('theme' if x[2] == 1 and not x[4] else 'full') + ('_tick' if ticked else '_skip')
        o = out.setdefault(kind, [0, 0, 1 << 30, 0])
        o[0] += 1
        o[1] += hk
        o[2] = min(o[2], hk)
        o[3] = max(o[3], hk)
    return {k: {'n': v[0], 'mean': round(v[1] / v[0], 1), 'min': v[2], 'max': v[3]} for k, v in sorted(out.items())}


def skip_sweep(steps=64):
    """the page's skip at 64 phases of $F5C9 (every 1,092 T): does the cold start's $8CD7 wait happen, and when does
       the title's EI come?  [phase, wait frames or None, request 5's frame offset, $970E's frame offset]"""
    h, m, r = machine()
    f = Flow(h, keyf=script_keyf(CTRL))
    f.stop_pc = 0xF5C9
    f.run(200)
    if r[PC] != 0xF5C9:
        raise Fail('$F5C9 not reached')
    st = h.save_state()
    out = []
    for k in range(steps):
        h.load_state(st)
        ph = k * (FD // steps)
        r[T] = (r[T] // FD) * FD + ph
        g = Flow(h, skip=True)
        g.run(120)
        w = g.waits[0] if g.waits else None
        q5 = [x for x in g.reqs if x[3] == 5]
        out.append([ph, (w[6] - w[1]) if w and w[3] == 5 else None, q5[0][0] if q5 else None,
                    g.marks.get('title_ei', [None])[0], w[4] if w else None, w[5] if w else None])
    return out


DI_OFFSETS = sorted(set(range(-40, 601, 4)) | set(range(-4, 6)) | set(range(510, 524)))   # every 4 T, 1 T at the edges


def di_window(offsets=DI_OFFSETS):
    """A TAKEN REQUEST WITH THE INTERRUPTS ON IS A DI WINDOW ($8E10 DI .. $8E28 EI / $8E29 RET): the cold start's request
       3 ($8CCD, IFF 1 since $8CCA's EI) from its $8E0A entry, the clock moved so the next frame boundary falls `o` T
       after the DI's first T (o in DI_OFFSETS), then run to the first interrupt accepted.  FORCED (only the clock moved:
       borisacc's phased runs).  Rows [o, the acceptance's T from the boundary or None, that ISR's label - the
       boundary's frame]: label 0 and T < 36 the frame's interrupt taken (before the DI, or at the window's end while
       the INT is still up); label 1 LOST (the next frame's)"""
    h, m, r = machine()
    f = Flow(h, keyf=script_keyf(CTRL))
    f.stop_pc = REQ
    f.run(400)
    if r[PC] != REQ or r[RA] != 3 or not r[IFF]:
        raise Fail('the cold start\'s request 3 with IFF 1 not reached')
    st = h.save_state()
    di = 29                                   # $8E0A LD HL,nn 10 / CP (HL) 7 / LD (HL),A 7 / RET z 5: uncontended
    out = []
    for o in offsets:
        h.load_state(st)
        b0 = (r[T] // FD + 2) * FD
        r[T] = b0 - di - o
        sim, ops, mm = h.sim, h.sim.opcodes, h.memobj.m
        seen_di = None
        while True:
            pc = r[PC]
            if pc == 0x8E10 and seen_di is None:
                seen_di = r[T]
            ops[mm[pc]]()
            if r[IFF] and r[T] % FD < h.int_active:
                t_ = r[T]
                if sim.accept_interrupt(r, mm, pc):
                    out.append([o, t_ - (t_ // FD) * FD, t_ // FD - b0 // FD])
                    break
            if r[T] > b0 + 2 * FD:
                out.append([o, None, None])
                break
        if seen_di is not None and seen_di != b0 - o:              # (None: the interrupt came before the DI)
            raise Fail('o %d: the DI began at %s, not boundary - %d' % (o, seen_di, o))
    return out


def capture():
    out = {'what': 'M10.0c THE 128K BRANCH FLOW ON THE PORT CLOCK (tools/ay128flow.py): the real load on the M10 '
                   'machine, scene by scene; the module docstring is the format',
           'bytes128': {'$%04X' % a: v for a, v in sorted(load128_bytes().items())}, 'bc128': BC128,
           'scenes': {}, 'hook': {}}
    for name, sc in SCENES.items():
        f = run_scene(name)
        rec = records(f, sc['window'])
        rec['script'] = [[n, k] for n, k in sc['script']]
        rec['skip'] = sc.get('skip', False)
        rec['frames_to'] = sc['frames']
        out['scenes'][name] = rec
        out['hook'][name] = hook_costs(f)
        print('  %-7s %d frames: %d reqs, %d waits, %d ticks, %d AY, %d ISRs, %d passes' % (
            name, sc['frames'], len(rec['reqs']), len(rec['waits']), len(rec['ticks']), len(rec['ay']), len(rec['isrs']),
            len(rec['passes'])), flush=True)
    out['skip_sweep'] = skip_sweep()
    out['di_window'] = di_window()
    return out


def timeline(frames):
    """explore: the real load's control select (passacc's script to player 2's '2'), then no key"""
    h, m, r = machine()
    seq = expand(pa.SCRIPT[:15])
    f = Flow(h, keyf=lambda L: seq[L] if L < len(seq) else [])
    f.run(frames)
    print('marks', {k: v for k, v in sorted(f.marks.items(), key=lambda kv: kv[1])})
    print('reqs', f.reqs)
    print('waits', f.waits)
    print('ereqs', f.ereqs[:10])
    print('ticks', len(f.ticks), 'ay', len(f.ay), 'isrs', len(f.isrs), 'passes', len(f.passes), 'spk', len(f.spk),
          'ldar', len(f.ldar), 'p7ffd', len(f.p7ffd), 'unsupported', h.paging.unsupported)
    hk = [x for x in f.isrs if x[3] is not None]
    print('hooks', len(hk), 'ticked', sum(x[4] for x in hk), 'T min/max', min(x[3] for x in hk) if hk else None,
          max(x[3] for x in hk) if hk else None)
    return f


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'timeline'
    if mode == 'timeline':
        timeline(int(sys.argv[2]) if len(sys.argv) > 2 else 700)
    elif mode == 'scene':
        f = run_scene(sys.argv[2])
        print('marks', {k: v for k, v in sorted(f.marks.items(), key=lambda kv: kv[1])})
        print('reqs', f.reqs)
        print('waits', f.waits)
        print('applied', f.applied)
        print('ticks', len(f.ticks), 'ay', len(f.ay), 'isrs', len(f.isrs), 'passes', len(f.passes), 'spk', len(f.spk),
              'ldar', len(f.ldar), 'p7ffd', len(f.p7ffd), 'unsupported', f.h.paging.unsupported)
    elif mode in ('capture', 'verify'):
        out = capture()
        if mode == 'verify':
            same = json.loads(json.dumps(out)) == json.load(open(FIXTURE))
            print('MATCH' if same else 'DIFFERS')
            sys.exit(0 if same else 1)
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, 'w') as fh:
            json.dump(out, fh, separators=(',', ':'))
        print('wrote %s (%d bytes)' % (FIXTURE, os.path.getsize(FIXTURE)))
    elif mode == 'explore1p':
        explore(CTRL + [(368, []), (3, ['1'])], int(sys.argv[2]) if len(sys.argv) > 2 else 1200)
