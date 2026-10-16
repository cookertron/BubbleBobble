"""M7.45 -- THE POP KILL oracle: a popped enemy dies, flies, falls, lands as fruit, and the
round clears -- driven through the real machine code in the SkoolKit harness.

WHAT IT MEASURES.  The pop head $B6D8..$B6EE ($B6CD's HL stored into $B775, the operand of
the chain walk's LD HL,n; $BF0A caches and erases), the fall-through into the emit tail
$B6F2..$B797, the CHAIN WALK $B774..$B78D with its per-marker $B7A1, the owner byte $B9BC
(written by $B901 for BOTH players on every $B8E5 call, P1 first with A = 0, then P2 with
A = $10, BEFORE either's active test), the corpse dispatch $AAFC -> $8A78 for slots with
bit 7 AND bit 3 set, the corpse draw $A26F (an OR-draw through the $FD00 row table in three
row blocks, its column in the OPERAND $A2AE), and the pop click $B790/$B79C.

THE ROWS.  One row per ISR, numbered from 0 (the first ISR after the state loads), bracketed as tools/keyreader.py brackets them: the row's PRE is
the machine at the ISR entry $8D72 (the interrupt accepted, nothing of the ISR run), its POST
is the machine just past the ISR's RET $8DA1.  Keys and the Kempston byte change only at the
entry, and are held through the ISR and the main-loop passes after it.  The main loop between
two ISRs is NOT modelled by the gate -- the next row's PRE is stored as it stands -- and the
number of main-loop passes it made is recorded ($8D0C, the pass head, per row).

WHAT IS STORED (house rule 7 -- no ROM byte, no full 48K image).  A fixed ADDRESS VECTOR of
RAM regions, and per row the vector's changes: PRE as a diff from the previous row's POST,
POST as a diff from its own PRE.  The vector is
  the display $4000..$5AFF WITH THE HUD MASKED -- the score digits, the high score and the
    round number are drawn from the Spectrum ROM charset ($8042 -> $3C00 + 8*code) and the
    EXTEND letters from ROM glyphs too ($95C1), so the bitmap of character rows 0..2 and of
    columns 0, 1, 30 and 31 of every row is NOT stored.  Their POST bytes are kept only as a
    per-row SHA-1 digest, and every stored cell is CHECKED against every non-blank glyph of
    the machine's charset ($3D00..$3FFF, read from the harness and never written out): a
    match fails the capture;
  the sparkle table $5CE0..$5CFB, the item table $9603..$9644, the colour shadow
    $F800..$FBFF, $FD80..$FFFF (entities, players, pool, globals, scores, the mailbox), the
    key table $B5FD..$B60C, the wake delays $A891..$A89A, and the named scalars in SCALARS.
The machine's shadow screen $E000..$F7FF is not stored: it is asserted UNCHANGED across every
scenario except the named cells SHADOW_WRITERS allows (a respawn's lives-icon repaint, six bytes,
in I3, I10 and I13), so the gate may use the engine's own round-1 shadow; it is carried as a digest,
and each scenario records the addresses it did change (shadow_writes).

EVENTS per row, hooked by PC inside the ISR: the pops that pass $B6D8's gate, $B6E0's HL,
the fork's class, every $B7A1 mark (the window address and the marker -- the marker is
REDACTED when the window address is below $4000, because it is then a ROM byte), the award
$80FA and its player, the owner byte at every $B9B6 touch-pop, the corpse birth/tick/fall/
land/draw, $A26F's column operand, every $A447 entry OUTSIDE the $A3AD pass INSIDE the ISR ('erase': the entry
it came through -- $BF16, $BE92, $8C51, $91D6 -- the slot and its cached Y) and every $A430 add
outside the pass ('beam': that entry and the add; $A431 itself is a scalar, bracketed at every
$A430 call and every ISR edge into facts.a431), the pop click's two OUTs with their T offset from the ISR
entry, every marker clear $B6D3 whose target is outside the colour shadow, and every LD A,R
the ISR executes with its site, A and tag -- which the gate FEEDS to the engine's BB_Rng
(the refresh register is the one input no RAM image carries).  And for the $AA60 INTERLEAVE
(M7.48): every $AB38 entry ('ab38', the slot), the respawn's calm at $ABB7 ('calm', the slot and
$90D0), the jump edge at $AD0C ('jumpedge', the slot and +$5A), a PLAYER slot entering the $AB0C
tail with an odd X ('oddtail', the slot and X), and every blow click's OUT at $ACAF ('blowout',
the slot, the EAR level and the T offset); the dispatch ORDER at $AAE5 is kept as counts in facts.

SCENARIOS
  N1  round1_48, P1 blows ('7' held 2 frames in 16 for the first 400 ISRs), until the round
      advance $97F8 is entered: three captures, three kills, three landings, the clear.
  N2  round1_2p48, BOTH players blow (P1 '7' on 0..1 mod 16, P2's Kempston fire $10 on 8..9
      mod 16) for the first 400 ISRs, to 900 ISRs or the advance: the owner byte both ways.
  C1  N1 to ISR 332, then pool slot 9's (IY+7) |= $0A (a touch-pop, owner P1): a chain in RAM.
  C2  the same with |= $1A (owner bit 4 -> P2 is paid, $B7C2 = $10).
  C3  the same on slot 5, which RISES on ISR 335 and pops on 337 before any risen move has
      rewritten its (IY+2)/(IY+3) from the rise's parked $02xx: the chain window is ROM.  The
      machine marks from ROM bytes there, which no port without a ROM can reproduce -- the
      DECLARED GAP, and the gate's named counter.
  N3  round1_2p48, both players blow, WALK and JUMP (the M7.45 review's p2nat script: P1 '7'
      on 0..1 mod 16; P2's Kempston fire on 8..9, right/left in alternate 80-ISR phases, up on
      20..21 mod 48; blowing stops at 500), ISRs 0..1199 -- the review's whole run: risen
      bubbles meet a changed wind, so $B84C LD ($B892),A rewrites the operand of $B891 LD C,n
      (N1..C4 never change it -- the review found the port left it stale on 51 rows of 1,200),
      and P2 PUSHES slot 3 into a LEFT wind on ISRs 464, 466 and 482: $B952 CALL $BF0A erases
      it, and $B968 keeps the wind ($B971) because it is neither 2 nor 4.  (N3 was cut at 460
      until the drift fix: the port nulled every pushed wind and had no push erase.)
  B1  round1_48, no keys; at ISR 6 two risen EMPTY bubbles (slots 9, 10) are staged at P1's
      right in the $B984 band (X = P1 X + 14, his Y), their cells' wind bits set to 6: the
      BOUNCE -- $B9A7 writes C = 8 into P1's +8, $B9AA CALL $ADAA shoves him 2 px left, and
      $B9B0 LD (IY+8),A leaves $FD there (the POP AF takes the HL pushed at $B991); a later
      slot in the same pass reads that $FD at $B945 as PRESSING and is pushed.
  B2  the same with wind bits 0: the bounce without the move -- $FD only, then the push.
  B3  the same with wind bits $80 (code 4, DOWN): the later slot's push NULLS it ($B973).
  B4  round1_2p48, at ISR 6 one risen EMPTY bubble 18 px left of P2, who walks LEFT (Kempston
      $02) into it: fourteen pushes, the bubble crossing byte boundaries, each erased by $BF0A
      where it stood before the -2 -- the review's dotted mark is what is left without it.
  B5  round1_2p48, at ISR 6 one risen bubble in P1's $B984 band with wind 2 (= his B, so
      $B984 returns at once, C still the bubble X and B = 2), and P2 poked to the bubble X at
      Y 16: P2's $B901 tests B and C -- the registers P1's call left -- not the bubble, and at
      Y 16 he overlaps "Y 2" and touch-pops a bubble 150 px below him (owner $10).
  (M7.47 review -- the five surviving mutants and the registers $ADAA leaves.  'b984' is
  $B985 CP B with the wind in A; 'adaa' is $B9AD, just back from $ADAA, with B and C; 'shove'
  carries the player's +8, X, Y and jump phase as $B9AA CALLs $ADAA.)
  B6  round1_48, P1 facing LEFT, two risen bubbles at P1 X - 14 (B = 6) in a wind-2 cell: the
      bounce with C = 4 -- $ADAA shoves him RIGHT, across a cell, so $B9AD sees B = $F8, C = 0.
  B7  the same with wind 6 = B: $B985 CP B / JR z,$B937 returns at once -- no shove, no $FD.
  B8  B4 with wind 2 (RIGHT) on the bubble's cells: P2's push NULLS it ($B973).
  B9  round1_2p48, P1 walking RIGHT (to ISR 6) into a bubble at his X + 14 in a wind-6 cell (a push,
      C := 6, B = 2), P2 poked to (16, 16): P2's $B901 tests C = the WIND CODE and touch-pops it (owner $10).
  B10 round1_2p48, B6's shape with one bubble, P1 X poked to $30 (the right step crosses a cell)
      and P2 at (18, 16): $ADAA ends $AEED LD BC,$F800, and P2 -- inside "B 2, C 4" -- does NOT pop.
  B11 the same with P1 X $32 (the step stays in its cell: B = 2, $AE24 LD C,(X+15)&$F8 = $40) and P2
      at ($38, 16): P2 touch-pops it.
  B12 P1 facing RIGHT, the bubble at X + 14 in a wind-6 cell, P1 X $34 (a LEFT step inside the cell:
      B = 2, C = 8 unchanged), P2 at (20, 16): P2 touch-pops it.
  B13 B12's shape with P1 X $30 (the LEFT step crosses a cell) and P2 at (18, 16): BC = $F800, no pop --
      where C = 8 (the left step's C without the crossing) would have popped it.
  B14 B10's shape with P2 at ($38, 16): BC = $F800, no pop -- where C = (X+15)&$F8 = $38 would have.
  (M7.48 -- THE INTERLEAVE: $AA60 dispatches slots 0 and 1 to $AB38, the player routine, inside its
  slot loop.)
  I1  round1_48, P1 walks right, then left, jumping every 40 ISRs, the enemies awake: the enemies'
      $AAC9/$AACF copy is his POST-move X+8/Y.
  I2  round1_2p48, P2 walks (Kempston) and the last active enemy tracks him (+7 bit 4).
  I3  round1_48, P1 dying (+4 = 3) with the last enemy ANGRY and every other X at 8n + 4: the
      respawn's $ABB4/$ABB7/$ABBA -- $90D0 flipped to $96, the $90C1 walk CALMS and 8-aligns.
  I4  round1_48, P1 standing with +$5A bit 4 set jumps: $AD0C RES 4.
  I5  I1's walk with the FAST WALK (+7 bit 2): $AAE6 runs $AB38 twice per dispatch.
  I6  I2's walk with P2's fast walk.
  I7  P1's X made odd, walking right: the $AB0C tail evens it AFTER the move.
  I8  P1 at X $DF by the right wall walking right: from the odd X the step crosses and is BLOCKED
      (from $DE it would not cross) -- the scene that separates "tail after" from "tail before".
  I9  round1_2p48, a fast-walking P1 on his LAST death tick, RIGHT held: the second $AB38 run
      meets him INACTIVE and runs him anyway -- $AB38 has no activity test.
  I10 round1_2p48, P2 fast-walking AND dying (+4 = 6), the last enemy angry, P1 walking: the death
      ticks doubled, and P2's respawn CALMS (the calm is not P1's alone).
  I11 round1_2p48, +$5A bit 4 set on BOTH players, P2 jumps (Kempston up): $AD0C clears P2's bit
      and leaves P1's.
  I12 I9 for P2 at slot 1, Kempston LEFT held.
  I13 round1_48, I1's walk; the fast walk given at ISR 104 as P1 is hit NATURALLY: the whole death
      runs doubled and the respawn lands at ISR 186 (about 266 at single speed).
  I14 round1_48, P1 with the fast walk walks and BLOWS: the blow click's $ACAF OUT twice per
      dispatch, in the order and at the levels of the two runs.

Usage:  python tools/popkill.py capture   -> build/popkill_fixture.json
        python tools/popkill.py verify    re-run and diff against the fixture
"""
import sys, os, json, base64, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, T, PC, SP, A as RA, B as RB, C as RC, H as RH, L as RL, IYh, IYl
import portconfig as pc
from keyprobe import press

FIXTURE = 'build/popkill_fixture.json'
CLEAR = None
ISR_IN, ISR_OUT, PASS = 0x8D72, 0x8DA1, 0x8D0C
GUARD = range(0xD000, 0xD300)
BRANCH_BYTE = 0x8DC4
R_SITES = [0x7E04, 0x873E, 0x8A2E, 0x8A38, 0x9715, 0x9811, 0xA15F, 0xB008, 0xB0D5, 0xB88D, 0xFEAC]
SCALARS = [0x8DB6, 0x8DB7, 0x8DBD, 0x8DBE, 0x8E3B, 0x86CD, 0x86CE, 0x86CF, 0x87B2, 0x8B9F, 0x8BA0,
           0x8BA2, 0x92DE, 0xA2AE, 0xA5D9, 0xA98F, 0xA990, 0xAA57, 0xAA5F, 0xAA65, 0xB54B, 0xB54C,
           0xB54D, 0xB57C, 0xB60F, 0xB610, 0xB611, 0xB612, 0xB613, 0xB62D, 0xB657, 0xB742, 0xB775, 0xB776, 0xB796, 0xB7C2,
           0xB880, 0xB881, 0xB892, 0xB9BC, 0xBFF7,
           0x90D0,      # $90CF's opcode byte: the respawn flips it SET 2 <-> RES 2 (M7.48)
           0xA3B2,      # the $A3AD draw toggle: a scene that starts with a FLASHING (invulnerable)
                        # player draws him in the wrong phase without it (M7.48 recon)
           0xA431]      # $A430's addend, the beam accumulator: $A447 adds to it OUTSIDE the pass too (M7.49)
RANGES = [(0x5CE0, 0x5CFC), (0x9603, 0x9645), (0xA891, 0xA89B), (0xB5FD, 0xB60D),
          (0xF800, 0xFC00), (0xFD80, 0x10000)]


def hud_masked(a):
    """a display BITMAP address whose cell may hold a ROM glyph: char rows 0..2, cols 0,1,30,31"""
    if not 0x4000 <= a < 0x5800:
        return False
    col = a & 0x1F
    row = ((a >> 8) & 0x18) | ((a >> 5) & 7)
    return row < 3 or col in (0, 1, 30, 31)


def vector():
    v = [a for a in range(0x4000, 0x5B00) if not hud_masked(a)]
    for lo, hi in RANGES:
        v += list(range(lo, hi))
    v += SCALARS
    assert len(v) == len(set(v)), 'vector overlaps'
    assert all(a >= 0x4000 for a in v), 'a ROM address in the vector'
    return v


VEC = vector()
HUD = [a for a in range(0x4000, 0x5800) if hud_masked(a)]


def ranges_of(addrs):
    out, lo, prev = [], None, None
    for a in addrs:
        if lo is None:
            lo = prev = a
        elif a == prev + 1:
            prev = a
        else:
            out.append([lo, prev + 1]); lo = prev = a
    out.append([lo, prev + 1])
    return out


def pack(prev, cur):
    """the changes prev -> cur as runs: uint16 LE index, uint8 length, bytes; base64"""
    out = bytearray()
    i, n = 0, len(cur)
    while i < n:
        if prev[i] == cur[i]:
            i += 1; continue
        j = i + 1
        while j < n and j - i < 255:
            if prev[j] != cur[j]:
                j += 1; continue
            k = j
            while k < n and k - j < 3 and prev[k] == cur[k]:
                k += 1
            if k < n and k - j < 3 and k - i < 255:
                j = k; continue
            break
        out += bytes([i & 0xFF, i >> 8, j - i]) + bytes(cur[i:j])
        i = j
    return base64.b64encode(bytes(out)).decode()


def unpack(prev, s):
    cur = list(prev)
    b = base64.b64decode(s)
    p = 0
    while p < len(b):
        i = b[p] | (b[p + 1] << 8); n = b[p + 2]; p += 3
        cur[i:i + n] = b[p:p + n]; p += n
    return cur


class Fail(Exception):
    pass


class Run:
    def __init__(self, state):
        h = Harness()
        h.load_state_file(pc.state_path(state))
        self.h, self.m = h, h.memobj.m
        # the dispatch-order hooks read these on EVERY run_to, including callers that step
        # outside Run.isr() (tools/itemage.py) -- so they exist from construction
        self.disp_seen = self.disp_enemy = False
        if self.m[BRANCH_BYTE] != 0xC9:
            raise Fail('%s: $8DC4 is not $C9 -- not the 48K ISR' % state)
        self.rom_glyphs = set()
        for c in range(0x20, 0x80):
            g = bytes(self.m[0x3C00 + 8 * c:0x3C00 + 8 * c + 8])
            if any(g):
                self.rom_glyphs.add(g)
        self.ev = []
        self.mev = []
        self.r = []
        self.in_isr = False
        self.t0 = 0
        self.passes = 0
        self.advance = False
        self.facts = dict(b775_ok=0, b775_bad=[], tick_even=[], tick_notcorpse=[], a2ae_bad=[],
                          or_bad=0, or_writes=0, or_first=0, owner=[], clear_out=[], b892_rows=0,
                          disp_isrs=0, disp_players=0, disp_player_after_enemy=0, disp_player_not_ab38=0,
                          disp_ab38_not_player=0,
                          a431=dict(passes=0, seed_not_b9=0, first_not_b9=0, unaccounted=0, main_calls=0,
                                    calls=0, outside={}))
        self.a431_exp = None                        # $A431 as the bracketed adds leave it
        self.live = False                           # facts only from the first ISR entry on: a state
                                                    # saved MID-PASS (round1_2p48 is at $A4CB, inside
                                                    # $A447) finishes that pass before it, uncounted
        self.in_pass = False
        self.a447ctx = None
        self.first_add = False
        self.hook = {}
        for a in R_SITES:
            self.hook[a] = self._rsite
        H = self.hook
        H[0xB6DD] = lambda: self._e('pop', self.iy())
        H[0xB6E3] = self._b775
        H[0xB75C] = lambda: self._e('fork', self.iy(), self.h.regs[RA])
        H[0xB7A1] = self._mark
        H[0x80FA] = lambda: self._e('award', self.h.regs[RA])
        H[0xB9B6] = lambda: self._e('touch', self.iy(), self.m[0xB9BC])
        H[0x8BC2] = lambda: self._e('birth', self.iy())
        H[0x8A7D] = self._tick
        H[0x8B4E] = lambda: self._e('fall', self.iy())
        H[0x8B83] = lambda: self._e('land', self.iy())
        H[0xA26F] = lambda: self._e('draw', self.iy())
        H[0xA28F] = lambda: self._a2ae()
        H[0xB791] = lambda: self._e('click', 0, self.h.regs[T] - self.t0)
        H[0xB79E] = lambda: self._e('click', 1, self.h.regs[T] - self.t0)
        H[0xB6D3] = self._clr
        H[0xB952] = lambda: self._e('push', self.iy())
        H[0xB971] = lambda: self._e('pushwind', self.iy(), 'kept')
        H[0xB973] = lambda: self._e('pushwind', self.iy(), 'null')
        H[0xB9AA] = lambda: self._e('shove', self.iy(), self.m[self.iy() + 8], self.m[self.iy() + 5],
                                    self.m[self.iy() + 6], self.m[self.iy() + 9])
        H[0xB9B0] = lambda: self._e('bounce', self.iy(), self.h.regs[RA])
        H[0xB985] = lambda: self._e('b984', self.iy(), self.h.regs[RA], self.h.regs[RB])
        H[0xB9AD] = lambda: self._e('adaa', self.iy(), self.h.regs[RB], self.h.regs[RC])
        H[0x8ECF] = lambda: self._e('clear')
        # $A431, the operand of $A430 ADD A,n: bracketed at every $A430 call and every ISR edge
        H[0xA3AD] = self._a3ad
        H[0xA3D4] = self._a3d4
        H[0xA430] = self._a430
        H[0xA435] = self._a431chk
        H[0xA426] = self._a426
        H[0xA447] = self._a447
        H[0xAAE5] = self._disp                      # $AAE5 PUSH HL: IY = the slot, HL = its handler
        H[0xAB38] = lambda: self._e('ab38', self.iy())
        H[0xABB7] = lambda: self._e('calm', self.iy(), self.m[0x90D0])
        H[0xAD0C] = lambda: self._e('jumpedge', self.iy(), self.m[self.iy() + 0x5A])
        H[0xAB0C] = self._oddtail                   # $AB0C the per-slot tail, entered after the move
        H[0xACAF] = lambda: self._e('blowout', self.iy(), (self.h.regs[RA] >> 4) & 1,
                                    self.h.regs[T] - self.t0)   # $ACAF OUT ($FE),A -- the blow click
        H[0x97F8] = self._adv
        H[PASS] = self._pass

    # ------------------------------------------------------------------ hooks
    def iy(self):
        r = self.h.regs
        return (r[IYh] << 8) | r[IYl]

    def hl(self):
        r = self.h.regs
        return (r[RH] << 8) | r[RL]

    def _e(self, *x):
        if self.in_isr:
            self.ev.append(list(x))
        elif x[0] in ('clear', 'advance', 'award', 'land', 'birth', 'pop'):
            self.mev.append(list(x))

    def _rsite(self):
        site = self.h.regs[PC]
        self.h.step(1)                                  # execute the LD A,R
        a = self.h.regs[RA]
        iy = self.iy()
        tag = None
        if site == 0xB88D:
            tag = (iy - 0xFED8) // 10
        elif site in (0xB008, 0xB0D5):
            tag = (iy - 0xFD80) // 10
        elif site in (0x873E, 0x8A2E, 0x8A38, 0x7E04, 0x9811):
            tag = 0
        if self.in_isr:
            self.r.append([site, a, tag])
        return True                                     # already stepped

    def _b775(self):
        iy, hl = self.iy(), self.hl()
        cache = self.m[iy + 2] | (self.m[iy + 3] << 8)
        if hl == cache:
            self.facts['b775_ok'] += 1
        else:
            self.facts['b775_bad'].append(['%04X' % iy, '%04X' % hl, '%04X' % cache])
        self._e('b775', iy, hl)

    def _mark(self):
        hl, a = self.hl(), self.h.regs[RA]
        self._e('mark', hl, a if hl >= 0x4000 else None)

    def _tick(self):
        iy = self.iy()
        if not self.m[0x8DBD] & 1:
            self.facts['tick_even'].append('%04X' % iy)
        f = self.m[iy + 7]
        if not (f & 0x80 and f & 0x08 and self.m[iy + 9] == 0xFF):
            self.facts['tick_notcorpse'].append(['%04X' % iy, f, self.m[iy + 9]])
        self._e('tick', iy)

    def _a2ae(self):
        iy = self.iy()
        want = (self.m[iy + 5] >> 3) & 0x1F
        if self.m[0xA2AE] != want:
            self.facts['a2ae_bad'].append(['%04X' % iy, self.m[0xA2AE], want])
        self._e('col', iy, self.m[0xA2AE])

    def _clr(self):
        hl = self.hl()
        if not 0xF800 <= hl < 0xFC00:
            self.facts['clear_out'].append(['%04X' % hl, 1 if self.in_isr else 0])
            self._e('clrout', hl)

    def _disp(self):
        """the $AA60 dispatch ORDER, kept as counts (facts), not per-row events: slots 0 and 1
        ($FD80/$FD8A) take $AB38 and come BEFORE every enemy's handler in the same ISR"""
        iy, hl = self.iy(), self.hl()
        if not self.in_isr:
            return
        if not self.disp_seen:
            self.facts['disp_isrs'] += 1
        player = iy in (0xFD80, 0xFD8A)
        if player:
            self.facts['disp_players'] += 1
        if player and hl != 0xAB38:
            self.facts['disp_player_not_ab38'] += 1
        if hl == 0xAB38 and not player:
            self.facts['disp_ab38_not_player'] += 1
        if player and self.disp_enemy:
            self.facts['disp_player_after_enemy'] += 1
        if not player:
            self.disp_enemy = True
        self.disp_seen = True

    def _oddtail(self):
        """a PLAYER slot entering the $AB0C tail with an ODD X: only the staged I7/I8 make one,
        and the X it carries is the POST-move X the tail is about to even"""
        iy = self.iy()
        if iy in (0xFD80, 0xFD8A) and self.m[iy + 5] & 1:
            self._e('oddtail', iy, self.m[iy + 5])

    def _adv(self):
        self._e('advance')
        if not self.advance:
            self.shadow_at_adv = shadow_digest(self.m)
            self.glyph_scan('at the advance')
        self.advance = True

    def _pass(self):
        if not self.in_isr:
            self.passes += 1

    # ------------------------------------------------------------------ $A431
    A447_CALLERS = {0xA405: 'pass', 0x8C59: '8C51', 0x91D9: '91D6', 0xBE95: 'BE92', 0xBF2B: 'BF16'}

    def _ret(self):
        sp = self.h.regs[SP]
        return self.m[sp] | (self.m[(sp + 1) & 0xFFFF] << 8)

    def _a431chk(self):
        """$A431 must hold what the bracketed adds left: anything else is a writer not seen"""
        v = self.m[0xA431]
        if self.a431_exp is not None and v != self.a431_exp:
            self.facts['a431']['unaccounted'] += 1
        self.a431_exp = v

    def _a3ad(self):
        self._a431chk()
        self.in_pass = True
        if self.live:
            self.facts['a431']['passes'] += 1

    def _a3d4(self):
        """$A3D4 LD ($A431),A -- the seed, A from $A3D2 LD A,$B9"""
        self._a431chk()
        a = self.h.regs[RA]
        if a != 0xB9 and self.live:
            self.facts['a431']['seed_not_b9'] += 1
        self.a431_exp = a
        self.first_add = True

    def _a430(self):
        """$A430 ADD A,n -- n IS $A431; A is the add.  Outside a pass it is an event, by the
        entry to $A447 it came through"""
        self._a431chk()
        f, a = self.facts['a431'], self.h.regs[RA]
        if not self.live:
            self.a431_exp = (self.m[0xA431] + a) & 0xFF
            return
        f['calls'] += 1
        if not self.in_isr:
            f['main_calls'] += 1
        if self.in_pass and self.first_add:
            self.first_add = False
            if self.m[0xA431] != 0xB9:
                f['first_not_b9'] += 1
        if not self.in_pass:
            k = '%s+%d' % (self.a447ctx, a)
            f['outside'][k] = f['outside'].get(k, 0) + 1
            self._e('beam', self.a447ctx, a)
        self.a431_exp = (self.m[0xA431] + a) & 0xFF

    def _a426(self):
        self._a431chk()
        self.in_pass = False

    def _a447(self):
        ret = self._ret()
        self.a447ctx = self.A447_CALLERS.get(ret, '%04X' % ret)
        if not self.in_pass:
            iy = self.iy()
            self._e('erase', self.a447ctx, iy, self.m[iy + 2])

    # ------------------------------------------------------------------ driver
    def run_to(self, target):
        h, m, H = self.h, self.m, self.hook
        tg = set(H) | {target} | set(GUARD)
        first = h.regs[PC] == target
        while True:
            h.run_until(tg, limit=10 ** 7, stride=1)
            p = h.regs[PC]
            if p in GUARD:
                raise Fail('PC entered the guard at $%04X' % p)
            if p == target and not first:
                return
            first = False
            if p in H and H[p]() is True:
                continue
            h.step(1)

    def isr(self, keys, kemp):
        """keys/kemp from here on; run ISR entry -> past RET, sample pre and post"""
        h, m = self.h, self.m
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        h.ports.kempston = kemp
        if h.regs[PC] != ISR_IN:
            self.run_to(ISR_IN)
        self._a431chk()                                 # no unseen writer since the last ISR
        self.live = True
        self.glyph_scan('ISR entry')
        pre = [m[a] for a in VEC]
        disp0 = bytes(m[0x4000:0x5B00])                 # the PRE display, for _orcheck only
        b892 = m[0xB892]
        self.ev, self.r = [], []
        self.disp_seen = self.disp_enemy = False
        self.in_isr, self.t0 = True, h.regs[T]
        m_watch = h.memobj
        m_watch.watch(0x4000, 0x5B00)
        self.run_to(ISR_OUT)
        h.step(1)
        self._a431chk()
        m_watch.unwatch()
        self._orcheck(m_watch.log, disp0)
        if m[0xB892] != b892:
            self.facts['b892_rows'] += 1
        t = h.regs[T] - self.t0
        self.in_isr = False
        self.glyph_scan('ISR exit')
        post = [m[a] for a in VEC]
        hud = hashlib.sha1(bytes(m[a] for a in HUD)).hexdigest()[:16]
        ev, r = self.ev, self.r
        self.passes, self.mev = 0, []
        self.run_to(ISR_IN)
        return pre, post, dict(ev=ev, r=r, t=t, passes=self.passes, hud=hud, mev=self.mev)

    def _orcheck(self, log, disp0):
        """$A2B6/$A2BB are LD (HL),A after LD A,(DE) / OR (HL): every bit that was set stays set.
        `last` is SEEDED FROM THE PRE DISPLAY, so the FIRST write to a cell in the ISR is checked
        against the byte the ISR found there, not skipped (the M7.45 review's NIT 5)"""
        last = {}
        for pcw, a, v in log:
            if pcw in (0xA2B6, 0xA2BB):
                self.facts['or_writes'] += 1
                if a not in last:
                    self.facts['or_first'] += 1
                old = last.get(a, disp0[a - 0x4000])
                if (v & old) != old:
                    self.facts['or_bad'] += 1
            last[a] = v

    def glyph_scan(self, where):
        """no STORED display cell may equal a non-blank ROM glyph"""
        m = self.m
        hits = []
        for row in range(24):
            for col in range(32):
                a0 = 0x4000 | ((row & 0x18) << 8) | ((row & 7) << 5) | col
                if hud_masked(a0):
                    continue
                cell = bytes(m[a0 + (r << 8)] for r in range(8))
                if cell in self.rom_glyphs:
                    hits.append([row, col])
        if hits:
            raise Fail('%s: stored display cells equal ROM glyphs at %s' % (where, hits[:8]))


def shadow_digest(m):
    return hashlib.sha1(bytes(m[0xE000:0xF800])).hexdigest()[:16]


def swap_players(m):
    """swap P1's and P2's (IY+2),(IY+3),(IY+5),(IY+6) at the pre of ISR 147, after the capture at 146 and before P1's touch at 148"""
    for o in (2, 3, 5, 6):
        m[0xFD80 + o], m[0xFD8A + o] = m[0xFD8A + o], m[0xFD80 + o]


def keys_n1(i):
    return (['7'] if (i % 16) < 2 and i < 400 else []), 0


def keys_n2(i):
    k = ['7'] if (i % 16) < 2 and i < 400 else []
    return k, (0x10 if 8 <= (i % 16) < 10 and i < 400 else 0)


def keys_n3(i):
    """the M7.45 review's p2nat: P1 blows; P2 blows, walks right/left and jumps (Kempston)"""
    k = ['7'] if (i % 16) < 2 and i < 500 else []
    kemp = 0
    if (i % 16) in (8, 9) and i < 500:
        kemp |= 0x10
    ph = (i // 80) % 4
    if ph == 1:
        kemp |= 0x01
    elif ph == 3:
        kemp |= 0x02
    if (i % 48) in (20, 21):
        kemp |= 0x08
    return k, kemp


def keys_none(i):
    return [], 0


def stage_bounce(wind_bits):
    def poke(m):
        px, py = m[0xFD85], m[0xFD86]
        for k in (9, 10):
            b = 0xFED8 + 10 * k
            m[b + 7] = 0x85; m[b + 4] = 0x14; m[b + 5] = px + 14; m[b + 6] = py
            m[b + 9] = 0; m[b + 8] = 0; m[b + 2] = py; m[b + 3] = 0x02
        c = 0xF800 + ((py & 0xF8) << 2) + (((px + 14) >> 3) & 0x1F)
        for cc in (c, c - 0x20, c + 1, c - 0x1F):
            m[cc] = (m[cc] & 0x3F) | wind_bits
    poke.__doc__ = ('slots 9 and 10 risen EMPTY at (P1 X + 14, P1 Y), the $B984 band; wind bits $%02X '
                    'on their cell, the cell above and the two to the right' % wind_bits)
    return poke


def keys_b4(i):
    return [], (0x02 if i >= 6 else 0)


def stage_walk_p2(m):
    """slot 9 risen EMPTY 18 px left of P2 at his Y"""
    px, py = m[0xFD8F], m[0xFD90]
    b = 0xFED8 + 90
    m[b + 7] = 0x85; m[b + 4] = 0x14; m[b + 5] = (px - 18) & 0xFF; m[b + 6] = py
    m[b + 9] = 0; m[b + 8] = 0; m[b + 2] = py; m[b + 3] = 0x02


def stage_carry(m):
    """slot 9 risen EMPTY at (P1 X + 14, P1 Y), wind bits $40 (code 2) on its cells; P2 at (that X, Y 16)"""
    px, py = m[0xFD85], m[0xFD86]
    b = 0xFED8 + 90
    m[b + 7] = 0x85; m[b + 4] = 0x14; m[b + 5] = px + 14; m[b + 6] = py
    m[b + 9] = 0; m[b + 8] = 0; m[b + 2] = py; m[b + 3] = 0x02
    c = 0xF800 + ((py & 0xF8) << 2) + (((px + 14) >> 3) & 0x1F)
    for cc in (c, c - 0x20, c + 1, c - 0x1F):
        m[cc] = (m[cc] & 0x3F) | 0x40
    m[0xFD8F] = px + 14; m[0xFD90] = 0x10


def stage_bnc(face, wind_bits, p1x=None, p2=None, n=2):
    """the $B984 band on the side P1 FACES: facing right (face 1) the bubble is at P1 X + 14
    (B = 2), facing left (face 0) at P1 X - 14 (B = 6); `n` risen EMPTY bubbles from slot 9, their
    cells' wind bits ORed with `wind_bits`; P1 X poked to `p1x` first when given (the $ADAA step
    crossing a cell or not), and P2, when given, poked to (X, Y) facing RIGHT"""
    def poke(m):
        if p1x is not None:
            m[0xFD85] = p1x
        m[0xFD87] = (m[0xFD87] & 0xFE) | face
        px, py = m[0xFD85], m[0xFD86]
        bx = (px + 14 if face else px - 14) & 0xFF
        for k in range(9, 9 + n):
            b = 0xFED8 + 10 * k
            m[b + 7] = 0x85; m[b + 4] = 0x14; m[b + 5] = bx; m[b + 6] = py
            m[b + 9] = 0; m[b + 8] = 0; m[b + 2] = py; m[b + 3] = 0x02
        c = 0xF800 + ((py & 0xF8) << 2) + ((bx >> 3) & 0x1F)
        for cc in (c, c - 0x20, c + 1, c - 0x1F):
            m[cc] = (m[cc] & 0x3F) | wind_bits
        if p2 is not None:
            m[0xFD8F], m[0xFD90] = p2
            m[0xFD91] |= 1
    poke.__doc__ = ('%d risen EMPTY bubble(s) from slot 9 at P1 X %s 14 (P1 facing %s%s), wind bits $%02X on '
                    'their cell, the cell above and the two to the right%s'
                    % (n, '+' if face else '-', 'RIGHT' if face else 'LEFT',
                       '' if p1x is None else ', P1 X poked to $%02X' % p1x, wind_bits,
                       '' if p2 is None else '; P2 poked to (%d, %d) facing right' % p2))
    return poke


def stage_walk_p2_wind(m):
    """slot 9 risen EMPTY 18 px left of P2 at his Y, wind bits $40 (code 2, RIGHT) on its cells"""
    stage_walk_p2(m)
    b = 0xFED8 + 90
    bx, py = m[b + 5], m[b + 6]
    c = 0xF800 + ((py & 0xF8) << 2) + ((bx >> 3) & 0x1F)
    for cc in (c, c - 0x20, c + 1, c - 0x1F):
        m[cc] = (m[cc] & 0x3F) | 0x40


def stage_push_p2(m):
    """slot 9 risen EMPTY at (P1 X + 14, P1 Y) with P1 facing RIGHT, wind bits $C0 (code 6) on its
    cells; P2 poked to (16, 16) facing right"""
    m[0xFD87] |= 1
    px, py = m[0xFD85], m[0xFD86]
    b = 0xFED8 + 90
    m[b + 7] = 0x85; m[b + 4] = 0x14; m[b + 5] = px + 14; m[b + 6] = py
    m[b + 9] = 0; m[b + 8] = 0; m[b + 2] = py; m[b + 3] = 0x02
    c = 0xF800 + ((py & 0xF8) << 2) + (((px + 14) >> 3) & 0x1F)
    for cc in (c, c - 0x20, c + 1, c - 0x1F):
        m[cc] = (m[cc] & 0x3F) | 0xC0
    m[0xFD8F] = 0x10; m[0xFD90] = 0x10; m[0xFD91] |= 1


def keys_p1right(i):
    """P1 holds RIGHT ('8') up to the push on ISR 6 and lets go (cut there when the $AA60
    interleave was a declared gap; the I scenes below walk him with the enemies awake)"""
    return (['8'] if i <= 6 else []), 0


# the scenes allowed to change the shadow screen, and exactly where: a respawn runs $AB6D CALL
# $806C, the lives panel, which repaints the lost life's cell (row 23; column 2 for P1, 29 for P2)
# in the DISPLAY ($80B8) and the SHADOW ($80C0) inside the ISR.  The engine's livesPanel() runs
# livesIcons() (real since M7.10) and writes both: the display copy is in the vector and exact,
# and only the shadow copy is unstored -- the gate checks the engine writes the same six bytes.
_P1_ICON = ['F1E2', 'F2E2', 'F3E2', 'F4E2', 'F5E2', 'F6E2']
_P2_ICON = ['F1FD', 'F2FD', 'F3FD', 'F4FD', 'F5FD', 'F6FD']
SHADOW_WRITERS = {'I3': _P1_ICON, 'I10': _P2_ICON, 'I13': _P1_ICON}


def keys_iwalk(i):
    """P1 walks RIGHT on 6..69 and LEFT on 70..139, jumping on 20..21 mod 40"""
    k = []
    if 6 <= i < 70:
        k.append('8')
    elif 70 <= i < 140:
        k.append('5')
    if (i % 40) in (20, 21):
        k.append('0')
    return k, 0


def keys_ip2(i):
    """P2 walks RIGHT (Kempston $01) on 6..59, then LEFT ($02)"""
    return [], (0x01 if 6 <= i < 60 else (0x02 if i >= 60 else 0))


def keys_ijump(i):
    return (['0'] if i in (7, 8) else []), 0


def keys_iright(i):
    return (['8'] if i >= 6 else []), 0


def last_enemy(m):
    for k in range(m[0xAA57] - 1, 1, -1):
        if m[0xFD80 + 10 * k + 7] & 0x80:
            return 0xFD80 + 10 * k
    raise Fail('no active enemy slot')


def stage_track_p2(m):
    """the LAST active enemy's (IY+7) |= $10: it tracks P2, so $AAC5 copies P2's X+8/Y"""
    m[last_enemy(m) + 7] |= 0x10


def stage_respawn(m):
    """P1 dying (+$5A |= 4) with +4 = 3: the respawn $AB5E.. falls three heavy ticks later; the
    last active enemy is ANGRY (+7 |= 4) and every other active enemy's X is set to 8n + 4"""
    m[0xFDDA] |= 0x04; m[0xFD84] = 3
    b = last_enemy(m)
    m[b + 7] |= 0x04
    for k in range(2, m[0xAA57]):
        e = 0xFD80 + 10 * k
        if e != b and m[e + 7] & 0x80:
            m[e + 5] = (m[e + 5] & 0xF8) | 4


def stage_carried(m):
    """P1's +$5A bit 4 set while he stands: the jump edge $AD0C clears it"""
    m[0xFDDA] |= 0x10


def stage_fast(m):
    """P1 has the FAST WALK (item 14: +7 |= 4, +$5B := 3): $AAE6 runs $AB38 TWICE for him"""
    m[0xFD87] |= 0x04; m[0xFDDB] = 3


def stage_fast_p2(m):
    """P2 has the fast walk (+7 |= 4)"""
    m[0xFD91] |= 0x04


def stage_odd_x(m):
    """P1's X made ODD: the $AB0C tail evens it AFTER his move"""
    m[0xFD85] |= 1


def stage_final_fast(m):
    """P1 (two-player game) on his LAST death tick with the FAST WALK: dying (+$5A bit 2), +4 = 0 and
    no life left (+$5C = 0), +7 bit 2.  $AAE6 decides the second $AB38 run before the first, the
    first run's $AB64 RES 7 makes him inactive, and $AB38 has no activity test -- so the second run
    reads his keys and moves him anyway"""
    m[0xFDDA] |= 0x04; m[0xFD84] = 0; m[0xFDDC] = 0; m[0xFD87] |= 0x04


def stage_p2_fast_dying(m):
    """P2 with the FAST WALK (+7 |= 4, +$5B := 3) and DYING with +4 = 6: $AAE6 runs his death tick
    twice per dispatch and the respawn lands on a first run; the last active enemy ANGRY and every
    other active enemy's X at 8n + 4, so P2's calm shows"""
    m[0xFD91] |= 0x04; m[0xFDE5] = 3
    m[0xFDE4] |= 0x04; m[0xFD8E] = 6
    b = last_enemy(m)
    m[b + 7] |= 0x04
    for k in range(2, m[0xAA57]):
        e = 0xFD80 + 10 * k
        if e != b and m[e + 7] & 0x80:
            m[e + 5] = (m[e + 5] & 0xF8) | 4


def keys_p1walk(i):
    """P1 walks RIGHT on 6..39, then LEFT"""
    return (['8'] if 6 <= i < 40 else (['5'] if i >= 40 else [])), 0


def stage_carried_both(m):
    """+$5A bit 4 set on BOTH players: P2's jump edge must clear HIS, and leave P1's"""
    m[0xFDE4] |= 0x10; m[0xFDDA] |= 0x10


def keys_ip2jump(i):
    """P2 holds Kempston UP ($08) on ISRs 7 and 8"""
    return [], (0x08 if i in (7, 8) else 0)


def stage_final_fast_p2(m):
    """stage_final_fast for P2 (slot 1, $FD8A): dying (+$5A bit 2), +4 = 0, no life left (+$5C = 0),
    the fast walk (+7 bit 2)"""
    m[0xFDE4] |= 0x04; m[0xFD8E] = 0; m[0xFDE6] = 0; m[0xFD91] |= 0x04


def keys_ip2left(i):
    """P2 holds Kempston LEFT ($02) from ISR 6"""
    return [], (0x02 if i >= 6 else 0)


def keys_fastblow(i):
    """P1 walks RIGHT on 6..59, then LEFT, and blows ('7') on 0..1 mod 12"""
    k = ['8'] if 6 <= i < 60 else (['5'] if i >= 60 else [])
    if (i % 12) < 2:
        k.append('7')
    return k, 0


def stage_wall_odd(m):
    """P1's X := $DF (8k+7) by the right wall: his step RIGHT from the odd X crosses into
    column 30 and is BLOCKED, so the tail finds $DF and evens it to $DE.  A tail run BEFORE
    the move would even it to $DE first -- which does not cross -- and step him to $E0"""
    m[0xFD85] = 0xDF


def scenario(name, state, keyfn, nmax, poke=None, poke_at=None, nrows=None, covers=''):
    run = Run(state)
    m = run.m
    sh0 = shadow_digest(m)
    shb0 = bytes(m[0xE000:0xF800])
    rows, seed, prev = [], None, None
    i = 0
    run.run_to(ISR_IN)
    while i < nmax:
        keys, kemp = keyfn(i)
        if poke is not None and i == poke_at:
            if callable(poke):
                poke(m)
            else:
                for a, orv in poke:
                    m[a] |= orv
        rec = poke is None or i >= poke_at
        pre, post, x = run.isr(keys, kemp)
        if rec:
            if seed is None:
                seed = pre
                run.glyph_scan(name + ' seed')
                d_pre = ''
            else:
                d_pre = pack(prev, pre)
            rows.append(dict(i=i, keys=keys, kemp=kemp, pre=d_pre, post=pack(pre, post), **x))
            prev = post
            if nrows and len(rows) >= nrows:
                break
        i += 1
        if run.advance:
            break
    if not run.advance:
        run.glyph_scan(name + ' end')
    sh1 = run.shadow_at_adv if run.advance else shadow_digest(m)
    shw = []
    if sh0 != sh1:
        shw = ['%04X' % (0xE000 + k) for k, b in enumerate(m[0xE000:0xF800]) if b != shb0[k]]
        if shw != SHADOW_WRITERS.get(name):
            raise Fail('%s: the shadow screen changed during the run at %s' % (name, shw[:12]))
    return dict(name=name, state=state, covers=covers, first_isr=rows[0]['i'],
                poke=(poke.__doc__ if callable(poke) else [['%04X' % a, v] for a, v in (poke or [])]),
                poke_at=poke_at,
                advanced=run.advance, shadow=sh0, shadow_writes=shw,
                seed=base64.b64encode(bytes(seed)).decode(), rows=rows), run.facts


def capture():
    scs, facts = [], {}
    for args in [
        ('N1', 'round1_48', keys_n1, 1400, None, None, None,
         'P1 blows; three captures, three kills, flights, landings, the clear'),
        ('N2', 'round1_2p48', keys_n2, 260, None, None, None,
         'both players in, both blow: P1 touch-pops with P2 live, and P1 is paid'),
        ('C4', 'round1_2p48', keys_n2, 400, swap_players, 147, 12,
         'P1 and P2 swap places before the first kill: P2 touch-pops, $B9BC = $10, P2 is paid'),
        ('C1', 'round1_48', keys_n1, 400, [(0xFED8 + 90 + 7, 0x0A)], 332, 8,
         'slot 9 touch-popped for P1 at ISR 332: a chain inside RAM'),
        ('C2', 'round1_48', keys_n1, 400, [(0xFED8 + 90 + 7, 0x1A)], 332, 8,
         'the same with the owner bit: P2 is paid, $B7C2 = $10'),
        ('C3', 'round1_48', keys_n1, 400, [(0xFED8 + 50 + 7, 0x0A)], 332, 8,
         'slot 5 pops before its first risen move: the chain window is ROM (declared gap)'),
        ('N3', 'round1_2p48', keys_n3, 1200, None, None, None,
         'both players blow, walk and jump: risen bubbles meet new winds and $B84C rewrites $B892; P2 pushes into a left wind'),
        ('B1', 'round1_48', keys_none, 60, stage_bounce(0xC0), 6, None,
         'the $B984 bounce, wind 6: $ADAA shoves P1 left, +8 left $FD, a later slot pushed'),
        ('B2', 'round1_48', keys_none, 60, stage_bounce(0x00), 6, None,
         'the $B984 bounce, wind 0: +8 left $FD without a move, a later slot pushed'),
        ('B3', 'round1_48', keys_none, 60, stage_bounce(0x80), 6, None,
         'the $B984 bounce, wind 4: the later slot is pushed and $B973 nulls the wind'),
        ('B4', 'round1_2p48', keys_b4, 60, stage_walk_p2, 6, None,
         'P2 walks left into a risen bubble: fourteen pushes across byte boundaries, each erased first'),
        ('B5', 'round1_2p48', keys_none, 40, stage_carry, 6, None,
         'P2 at Y 16 tests the B/C that the P1 $B901 left and touch-pops a bubble far below him'),
        ('B6', 'round1_48', keys_none, 30, stage_bnc(0, 0x40), 6, None,
         'the $B984 bounce, wind 2 facing left: C = 4, $ADAA shoves P1 RIGHT across a cell (B = $F8)'),
        ('B7', 'round1_48', keys_none, 30, stage_bnc(0, 0xC0), 6, None,
         'the $B984 bounce, wind 6 = B: $B985 CP B returns at once -- no shove, no $FD'),
        ('B8', 'round1_2p48', keys_b4, 40, stage_walk_p2_wind, 6, None,
         'P2 walks left into a risen bubble in a RIGHT wind: the push nulls it ($B973)'),
        ('B9', 'round1_2p48', keys_p1right, 20, stage_push_p2, 6, None,
         'P1 pushes a bubble (C := the wind code 6); P2 at (16, 16) tests that C and touch-pops it'),
        ('B10', 'round1_2p48', keys_none, 20, stage_bnc(0, 0x40, p1x=0x30, p2=(18, 16), n=1), 8, None,
         'the bounce steps P1 across a cell: $ADAA leaves BC = $F800 and P2 at (18, 16) does not pop'),
        ('B11', 'round1_2p48', keys_none, 20, stage_bnc(0, 0x40, p1x=0x32, p2=(0x38, 16), n=1), 8, None,
         'the bounce steps P1 right inside his cell: B = 2, C = (X+15)&$F8, and P2 at ($38, 16) pops'),
        ('B12', 'round1_2p48', keys_none, 20, stage_bnc(1, 0xC0, p1x=0x34, p2=(20, 16), n=1), 8, None,
         'the bounce steps P1 left inside his cell: B = 2, C = 8 unchanged, and P2 at (20, 16) pops'),
        ('B13', 'round1_2p48', keys_none, 20, stage_bnc(1, 0xC0, p1x=0x30, p2=(18, 16), n=1), 8, None,
         'the bounce steps P1 LEFT across a cell: BC = $F800 and P2 at (18, 16) does not pop'),
        ('B14', 'round1_2p48', keys_none, 20, stage_bnc(0, 0x40, p1x=0x30, p2=(0x38, 16), n=1), 8, None,
         'the bounce steps P1 RIGHT across a cell: BC = $F800 and P2 at ($38, 16) does not pop'),
        ('I1', 'round1_48', keys_iwalk, 160, None, None, None,
         'P1 walks and jumps with the enemies awake: $AA60 moves him at slot 0, so they copy his POST-move X+8/Y'),
        ('I2', 'round1_2p48', keys_ip2, 120, stage_track_p2, 6, None,
         'P2 walks and the last enemy tracks him (bit 4): $AAC5 copies P2 post-move position'),
        ('I3', 'round1_48', keys_none, 40, stage_respawn, 6, None,
         'P1 respawns inside the slot loop: $ABB7 CALL $90C1 with $90D0 = $96 CALMS the enemies (RES 2) and 8-aligns their X before they move'),
        ('I4', 'round1_48', keys_ijump, 30, stage_carried, 6, None,
         'P1 jumps with +$5A bit 4 set: $AD0C RES 4 on the jump edge'),
        ('I5', 'round1_48', keys_iwalk, 100, stage_fast, 6, None,
         'P1 with the fast walk (+7 bit 2): $AAE6 runs $AB38 twice'),
        ('I6', 'round1_2p48', keys_ip2, 80, stage_fast_p2, 6, None,
         'P2 with the fast walk: $AB38 twice at slot 1'),
        ('I7', 'round1_48', keys_iright, 30, stage_odd_x, 7, None,
         'P1 walks from an ODD X: the $AB0C tail evens it after the move, not before'),
        ('I8', 'round1_48', keys_iright, 30, stage_wall_odd, 7, None,
         'P1 at X $DF walks into the right wall: the step from the ODD X is blocked, the tail evens it to $DE'),
        ('I9', 'round1_2p48', keys_iright, 24, stage_final_fast, 6, None,
         'a fast-walking P1 dies his last death: the doubled second $AB38 run meets him INACTIVE and runs him anyway'),
        ('I10', 'round1_2p48', keys_p1walk, 30, stage_p2_fast_dying, 6, None,
         'P2 fast-walking and dying: the death ticks doubled, and P2s respawn CALMS the enemies'),
        ('I11', 'round1_2p48', keys_ip2jump, 30, stage_carried_both, 6, None,
         '+$5A bit 4 on both players, P2 jumps: $AD0C clears his and leaves P1s'),
        ('I12', 'round1_2p48', keys_ip2left, 24, stage_final_fast_p2, 6, None,
         'I9 for P2 at slot 1: the doubled second $AB38 run meets him INACTIVE and walks him anyway'),
        ('I13', 'round1_48', keys_iwalk, 187, stage_fast, 104, None,
         'the fast walk given as P1 is hit NATURALLY at ISR 104: the whole death runs doubled, respawn at 186'),
        ('I14', 'round1_48', keys_fastblow, 90, stage_fast, 6, None,
         'P1 with the fast walk walks and BLOWS: the $ACAF click twice per dispatch'),
    ]:
        sc, f = scenario(*args)
        scs.append(sc); facts[sc['name']] = f
        print(sc['name'], len(sc['rows']), 'rows', 'advanced' if sc['advanced'] else '',
              'pops', sum(1 for r in sc['rows'] for e in r['ev'] if e[0] == 'pop'),
              'births', sum(1 for r in sc['rows'] for e in r['ev'] if e[0] == 'birth'),
              'lands', sum(1 for r in sc['rows'] for e in r['ev'] if e[0] == 'land'),
              'marks', sum(1 for r in sc['rows'] for e in r['ev'] if e[0] == 'mark'),
              'R', sum(len(r['r']) for r in sc['rows']))
    return scs, facts


CLEAR_TARGETS = ((0xF9EC, 0x2B), (0xC123, 0x5A), (0x02A8, None),
                 (0x3FFF, None), (0x4000, 0x3D), (0x7FFF, 0x77))


def clear_marker():
    """$B6C8 CALLED DIRECTLY on round1_48, pool slot 0 flagged risen (bit 2), with its cached
    (IY+2)/(IY+3) pointed at: a colour-shadow cell, plain RAM at $C123, the rise's parked $02A8
    in ROM, and THE BOUND ITSELF -- $3FFF (the last ROM byte), $4000 (the first RAM byte, the
    display) and $7FFF (the top of the lower 32K).  `LD A,(HL) / AND $E0 / LD (HL),A` writes
    wherever HL points; only a ROM write is discarded.  The call stops once at the store $B6D6
    LD (HL),A and records HL there (`store_hl`): the store EXECUTES at every target, ROM or
    not.  Stored: the RAM before/after for the RAM targets; for the ROM targets only booleans --
    whether the byte is unchanged after the store (`rom_unchanged`), and whether the write
    would have changed it and did not (`rom_write_discarded`; $3FFF's low five bits may be
    clear, so that one can be 0 there without saying anything) -- never the byte itself.
    (The harness's Mem.rom_writes cannot count these: the simulator drops a ROM write itself.)"""
    out = []
    for tgt, seed in CLEAR_TARGETS:
        h = Harness(); h.load_state_file(pc.state_path('round1_48')); m = h.memobj
        p = 0xFED8
        m[p + 7] = 0x85; m[p + 2] = tgt & 0xFF; m[p + 3] = tgt >> 8
        if seed is not None:
            m[tgt] = seed
        b0 = m.m[tgt]
        r = h.sim.registers                             # h.call's shape, with one stop inside
        sp = (r[SP] - 2) & 0xFFFF
        m.m[sp] = 0x00; m.m[sp + 1] = 0xFE; r[SP] = sp  # one sentinel return, $FE00
        r[IYh], r[IYl] = p >> 8, p & 0xFF
        r[PC] = 0xB6C8
        t0 = r[T]
        h.run_until((0xFE00, 0xB6D6), limit=10000, interrupts=False)
        store_hl = None
        if r[PC] == 0xB6D6:
            store_hl = '%04X' % ((r[RH] << 8) | r[RL])
            h.run_until((0xFE00,), limit=10000, interrupts=False)
        idx = 0 if r[PC] == 0xFE00 else None
        t = r[T] - t0
        # a ROM target: the write WOULD change the byte (its low five bits are not all
        # clear) and the byte is unchanged -- two booleans, never the byte itself
        would = (b0 & 0xE0) != b0
        row = dict(target='%04X' % tgt, ret=idx, t=t, store_hl=store_hl,
                   rom_write_discarded=int(tgt < 0x4000 and would and m.m[tgt] == b0))
        if tgt < 0x4000:
            row['rom_unchanged'] = int(m.m[tgt] == b0)
        if seed is not None:
            row.update(before=seed, after=m.m[tgt])
        out.append(row)
    return out


def assertions(scs, facts):
    """the recon's measured facts, asserted on the machine"""
    out = []

    def claim(name, held, measured):
        out.append(dict(claim=name, held=bool(held), measured=measured))
        if not held:
            print('  !! REFUTED:', name, measured)

    allf = {k: facts[k] for k in facts}
    claim('$B6E0 stores $B6CD\'s HL -- the popped bubble\'s (IY+2)/(IY+3) -- into $B775',
          all(not f['b775_bad'] for f in allf.values()) and sum(f['b775_ok'] for f in allf.values()) > 0,
          dict(ok=sum(f['b775_ok'] for f in allf.values()), bad=[f['b775_bad'] for f in allf.values()]))
    claim('$8A78 runs past its gate only on ODD ISRs, only for slots with (IY+7) bits 7 and 3 and (IY+9) = $FF',
          all(not f['tick_even'] and not f['tick_notcorpse'] for f in allf.values()),
          dict(even=[f['tick_even'][:4] for f in allf.values()],
               notcorpse=[f['tick_notcorpse'][:4] for f in allf.values()]))
    claim('$A28C writes (X >> 3) & $1F into $A2AE, the operand of $A2AD ADD A,n',
          all(not f['a2ae_bad'] for f in allf.values()),
          [f['a2ae_bad'][:4] for f in allf.values()])
    claim('$A2B6/$A2BB OR-DRAW: every display write keeps the bits the cell already had -- the FIRST write to a cell in an ISR checked against the PRE display',
          all(f['or_bad'] == 0 for f in allf.values()) and sum(f['or_writes'] for f in allf.values()) > 0 and
          sum(f['or_first'] for f in allf.values()) > 0,
          dict(writes=sum(f['or_writes'] for f in allf.values()), first=sum(f['or_first'] for f in allf.values()),
               bad=sum(f['or_bad'] for f in allf.values())))
    tp = [e for sc in scs for r in sc['rows'] for e in r['ev'] if e[0] == 'touch']
    claim('$B9B9 ORs $B9BC, the OWNER: $00 while P1 is tested, $10 while P2 is',
          len(tp) > 0 and all(e[2] in (0x00, 0x10) for e in tp) and
          any(e[2] == 0 for e in tp) and any(e[2] == 0x10 for e in tp),
          dict(touches=len(tp), owners=sorted(set(e[2] for e in tp))))
    n1 = scs[0]
    sc_ = {s['name']: s for s in scs}
    aw2 = lambda n: [e[1] for r in sc_[n]['rows'] for e in r['ev'] if e[0] == 'award']
    tch = lambda n: [e[2] for r in sc_[n]['rows'] for e in r['ev'] if e[0] == 'touch']
    claim('N2: with BOTH players in, P1 touch-pop writes owner $00 and P1 is paid; C4: P2 writes $10 and P2 is paid',
          aw2('N2') and set(aw2('N2')) == {1} and set(tch('N2')) == {0} and
          aw2('C4') and set(aw2('C4')) == {2} and set(tch('C4')) == {0x10},
          dict(N2=[aw2('N2'), tch('N2')], C4=[aw2('C4'), tch('C4')]))
    kills = [(r['i'], e) for r in n1['rows'] for e in r['ev'] if e[0] == 'birth']
    claim('N1: the natural scene kills by play and clears the round: three births, three landings, $8ECF, then $97F8',
          len(kills) == 3 and n1['advanced'] and
          sum(1 for r in n1['rows'] for e in r['ev'] if e[0] == 'land') == 3 and
          any(e[0] == 'clear' for r in n1['rows'] for e in r['mev']) and
          any(e[0] == 'advance' for e in n1['rows'][-1]['mev']),
          dict(births=[k[0] for k in kills], advanced=n1['advanced']))
    aw = [e for r in n1['rows'] for e in r['ev'] if e[0] == 'award']
    claim('N1: every award in the one-player scene is paid to P1 ($80FA with A = 1)',
          len(aw) > 0 and all(e[1] == 1 for e in aw), dict(awards=[e[1] for e in aw]))
    c3 = [s for s in scs if s['name'] == 'C3'][0]
    rm = [e for r in c3['rows'] for e in r['ev'] if e[0] == 'mark' and e[1] < 0x4000]
    claim('C3: a pop whose (IY+2)/(IY+3) still hold the rise\'s parked $02xx walks a ROM window and MARKS from ROM bytes',
          len(rm) > 0, dict(rom_marks=len(rm)))
    nat = [e for s in scs if s['name'] in ('N1', 'N2') for r in s['rows'] for e in r['ev']
           if e[0] == 'mark' and e[1] < 0x4000]
    claim('N1/N2: no natural pop reads a ROM window', len(nat) == 0, dict(rom_marks=len(nat)))
    cm = {r['target']: r for r in CLEAR}
    ram_t = [r for r in CLEAR if int(r['target'], 16) >= 0x4000]
    rom_t = [r for r in CLEAR if int(r['target'], 16) < 0x4000]
    claim('$B6C8 clears a marker WHEREVER (IY+2)/(IY+3) point: RAM outside the colour shadow is ANDed with $E0 like a shadow cell, and only a ROM target is a discarded write',
          cm['F9EC']['after'] == 0x2B & 0xE0 and cm['C123']['after'] == 0x5A & 0xE0 and
          cm['02A8']['rom_write_discarded'] == 1 and cm['F9EC']['rom_write_discarded'] == 0 and
          all(r['ret'] == 0 for r in CLEAR), CLEAR)
    claim('$B6C8 AT THE BOUND: the store $B6D6 executes with HL = the target every time; $4000 and $7FFF are written ($3D -> $20, $77 -> $60), and $3FFF, like $02A8, is a ROM store that leaves the byte as it was -- the bound is $4000, exactly',
          set(cm) >= {'3FFF', '4000', '7FFF'} and
          all(r['store_hl'] == r['target'] and r['ret'] == 0 for r in CLEAR) and
          cm['4000']['after'] == 0x3D & 0xE0 and cm['7FFF']['after'] == 0x77 & 0xE0 and
          all(r['after'] == r['before'] & 0xE0 for r in ram_t) and
          all(r['rom_unchanged'] == 1 and 'after' not in r for r in rom_t),
          [[r['target'], r['store_hl'], r.get('after'), r.get('rom_unchanged')] for r in CLEAR])
    b892 = {k: f['b892_rows'] for k, f in facts.items()}
    claim('$B84C LD ($B892),A: the wind code is stored into the operand of $B891 LD C,n -- N3 (natural two-player play) changes it on some rows',
          b892.get('N3', 0) > 0, b892)
    ev_ = lambda n, k: [(r['i'], e) for r in sc_[n]['rows'] for e in r['ev'] if e[0] == k]
    pw = ev_('N3', 'pushwind')
    claim('$B952 CALL $BF0A: a risen bubble PUSHED by a player is cached and ERASED, and $B968 nulls the '
          'wind ONLY for codes 2 and 4 -- N3 pushes into a left wind and $B971 keeps it',
          len(ev_('N3', 'push')) >= 3 and len(pw) == len(ev_('N3', 'push')) and
          all(e[2] == 'kept' for _, e in pw),
          dict(push=[i for i, _ in ev_('N3', 'push')], wind=[e[2] for _, e in pw]))
    b1s, b1b, b2s, b2b = ev_('B1', 'shove'), ev_('B1', 'bounce'), ev_('B2', 'shove'), ev_('B2', 'bounce')
    claim('$B984 THE BOUNCE: $B9B0 leaves $FD in the player +8 on every bounce (the POP AF takes the HL '
          'pushed at $B991); with wind 6 (B1) $B9AA CALLs $ADAA with +8 = 8 first, with wind 0 (B2) it does '
          'not; and a later slot in the same pass reads the $FD as pressing and is PUSHED',
          len(b1b) > 0 and len(b2b) > 0 and len(b1s) > 0 and len(b2s) == 0 and
          all(e[1] == 0xFD80 and e[2] == 0xFD for _, e in b1b + b2b) and
          all(e[1] == 0xFD80 and e[2] == 8 for _, e in b1s) and
          any(i in set(j for j, _ in b1b) for i, _ in ev_('B1', 'push')) and
          any(i in set(j for j, _ in b2b) for i, _ in ev_('B2', 'push')),
          dict(B1=dict(bounce=[i for i, _ in b1b], shove=[i for i, _ in b1s], push=[i for i, _ in ev_('B1', 'push')]),
               B2=dict(bounce=[i for i, _ in b2b], push=[i for i, _ in ev_('B2', 'push')])))
    b3w, b4p, b5t = ev_('B3', 'pushwind'), ev_('B4', 'push'), ev_('B5', 'touch')
    claim('$B968/$B973: a push into a DOWN wind (B3, code 4) NULLS it; P2 walking into a bubble (B4) '
          'pushes it at least ten times, each after $B952 CALL $BF0A; $B8EA/$B8ED load C/B once and the P1 '
          '$B901 leaves B = 2, so P2 at Y 16 (B5) touch-pops a bubble at Y $A8 with owner $10',
          len(b3w) > 0 and all(e[2] == 'null' for _, e in b3w) and len(b4p) >= 10 and
          len(b5t) == 1 and b5t[0][1][2] == 0x10 and b5t[0][0] == 6,
          dict(B3=[e[2] for _, e in b3w], B4=[i for i, _ in b4p], B5=[[i, e[2]] for i, e in b5t]))
    # ---- the M7.47 review's scenes
    def adaa_rule(c, X, Y, ph):
        if c & 4:
            e = (X + 15) & 0xFF
            cross, c0 = (e & 0xF8) != ((e + 2) & 0xF8), e & 0xF8
        else:
            cross, c0 = (X & 7) < 2, c
        if not cross:
            return (2, c0)
        if ((Y + 15) & 0xFF) >= 0x18:
            return (0xF8, 0)
        return (2, ph if ph < 0x10 else c0)
    pairs, pbad = [], []
    for s in scs:
        for r in s['rows']:
            sh = [e for e in r['ev'] if e[0] == 'shove']
            ad = [e for e in r['ev'] if e[0] == 'adaa']
            if len(sh) != len(ad):
                pbad.append([s['name'], r['i'], 'count'])
                continue
            for a, b in zip(sh, ad):
                pairs.append((s['name'], r['i'], (b[2], b[3])))
                if adaa_rule(a[2], a[3], a[4], a[5]) != (b[2], b[3]):
                    pbad.append([s['name'], r['i'], a[2:], b[2:]])
    kinds = set(p[2] if p[2][0] == 0xF8 else ('B2', 'C') for p in pairs)
    claim("$B9AA CALL $ADAA returns its OWN BC to the next player's $B901: B = 2 and C = (X+15)&$F8 "
          '(right) or C unchanged (left) within a cell, B = $F8 / C = 0 after a cell crossing ($AEDC '
          'LD B,H ... $AEED LD BC,$F800) -- every shove in the fixture against that rule',
          len(pairs) > 0 and not pbad and (0xF8, 0) in kinds and ('B2', 'C') in kinds,
          dict(shoves=len(pairs), bad=pbad[:6]))
    b6s, b7s = ev_('B6', 'shove'), ev_('B7', 'shove')
    b7e = ev_('B7', 'b984')
    claim('B6: a wind-2 bounce facing left shoves P1 RIGHT (+8 = 4) across a cell; B7: wind 6 = B '
          'returns at $B985 -- no shove and no $FD on the rows where $B985 is reached',
          len(b6s) > 0 and all(e[2] == 4 for _, e in b6s) and
          any(e[2] == 0xF8 for _, e in ev_('B6', 'adaa')) and
          len(b7e) > 0 and all(e[2] == e[3] == 6 for _, e in b7e) and not b7s and
          not ev_('B7', 'bounce'),
          dict(B6=[[i, e[2:]] for i, e in b6s], B7=[[i, e[2:]] for i, e in b7e]))
    b8w = ev_('B8', 'pushwind')
    claim('B8: P2 pushing a bubble in a RIGHT wind (code 2): $B968 CP 2 nulls it ($B973)',
          any(e[2] == 'null' for _, e in b8w) and len(ev_('B8', 'push')) == len(b8w),
          dict(B8=[[i, e[2]] for i, e in b8w]))
    b9 = ev_('B9', 'touch')
    claim("B9: after P1's push C holds the WIND CODE ($B950 LD C,A): P2 at (16, 16) touch-pops the "
          'bubble in the same ISR, owner $10',
          len(ev_('B9', 'push')) > 0 and len(b9) == 1 and b9[0][1][2] == 0x10 and
          b9[0][0] == ev_('B9', 'push')[0][0],
          dict(push=[i for i, _ in ev_('B9', 'push')], touch=[[i, e[2]] for i, e in b9]))
    p2 = {n: (ev_(n, 'adaa'), ev_(n, 'touch')) for n in ('B10', 'B11', 'B12', 'B13', 'B14')}
    claim('B10/B13/B14: after a crossing ($F800, right or left) P2 at (18, 16) or ($38, 16) never pops; '
          'B11 ((X+15)&$F8 = $40, P2 at $38) and B12 (C = 8, P2 at 20) do, on the shove ISR, owner $10',
          all(p2[n][0] and list(p2[n][0][0][1][2:]) == [0xF8, 0] and not p2[n][1] for n in ('B10', 'B13', 'B14')) and
          p2['B11'][0] and list(p2['B11'][0][0][1][2:]) == [2, 0x40] and len(p2['B11'][1]) == 1 and
          p2['B11'][1][0][0] == p2['B11'][0][0][0] and p2['B11'][1][0][1][2] == 0x10 and
          p2['B12'][0] and list(p2['B12'][0][0][1][2:]) == [2, 8] and len(p2['B12'][1]) == 1 and
          p2['B12'][1][0][0] == p2['B12'][0][0][0] and p2['B12'][1][0][1][2] == 0x10,
          {n: dict(adaa=[[i, list(e[2:])] for i, e in v[0]], touch=[[i, e[2]] for i, e in v[1]])
           for n, v in p2.items()})
    ck = [e for sc in scs for r in sc['rows'] for e in r['ev'] if e[0] == 'click']
    claim('$B790/$B79C: every award is bracketed by the pop click, level 0 then level 1, inside the ISR',
          len(ck) == 2 * sum(1 for sc in scs for r in sc['rows'] for e in r['ev'] if e[0] == 'fork') and
          all(e[2] > 0 for e in ck) and
          all([e[1] for e in r['ev'] if e[0] == 'click'] == [0, 1] * (len([e for e in r['ev'] if e[0] == 'click']) // 2)
              for sc in scs for r in sc['rows']),
          dict(clicks=len(ck)))
    dsum = {k: sum(f[k] for f in allf.values()) for k in
            ('disp_isrs', 'disp_players', 'disp_player_after_enemy', 'disp_player_not_ab38', 'disp_ab38_not_player')}
    claim('$AA60 INTERLEAVES THE PLAYERS: slots 0 and 1 ($FD80/$FD8A) are dispatched to $AB38 at $AAE5, '
          'and never after an enemy slot in the same ISR -- so every enemy $AAC9 copy follows the move',
          dsum['disp_isrs'] > 0 and dsum['disp_players'] > 100 and dsum['disp_player_after_enemy'] == 0 and
          dsum['disp_player_not_ab38'] == 0 and dsum['disp_ab38_not_player'] == 0, dsum)
    def per_row(n, slot):
        return [sum(1 for e in r['ev'] if e[0] == 'ab38' and e[1] == slot)
                for r in sc_[n]['rows'] if any(e[0] == 'ab38' for e in r['ev'])]
    i1, i5, i6 = per_row('I1', 0xFD80), per_row('I5', 0xFD80), per_row('I6', 0xFD8A)
    claim('I5/I6: the FAST WALK (+7 bit 2) makes $AAE6 run $AB38 TWICE for that player on every '
          'dispatching ISR; I1 (no fast walk) runs it once',
          i1 and set(i1) == {1} and i5 and set(i5) == {2} and i6 and set(i6) == {2},
          dict(I1=sorted(set(i1)), I5=sorted(set(i5)), I6=sorted(set(i6)), rows=[len(i1), len(i5), len(i6)]))
    cm = ev_('I3', 'calm')
    claim('I3: the respawn $ABB7 CALL $90C1 runs with $90D0 = $96 (CB 96 = RES 2,(HL)): the walk CALMS',
          len(cm) == 1 and cm[0][1][2] == 0x96, [[i, e[2]] for i, e in cm])
    je = ev_('I4', 'jumpedge')
    claim('I4: the jump edge reaches $AD0C RES 4,(IY+$5A) with bit 4 set',
          len(je) >= 1 and all(e[2] & 0x10 for _, e in je[:1]), [[i, e[2]] for i, e in je])
    o7, o8 = ev_('I7', 'oddtail'), ev_('I8', 'oddtail')
    oth = [sc['name'] for sc in scs if sc['name'] not in ('I7', 'I8')
           and any(e[0] == 'oddtail' for r in sc['rows'] for e in r['ev'])]
    # the STAGED X is the first recorded row's pre (the seed), read from the vector
    x7, x8 = [base64.b64decode(sc_[n]['seed'])[VEC.index(0xFD85)] for n in ('I7', 'I8')]
    claim('I7/I8: THE TAIL COMES AFTER THE MOVE.  I7: P1 staged at an odd X enters $AB0C at that '
          'X + 2 -- moved first; I8: staged at $DF by the right wall he enters it STILL at $DF -- the '
          'step from the odd X crossed into the wall and was blocked (from $DE it would not have '
          'crossed).  Once each: the tail evens X, so no later row is odd; no other scene has one',
          x7 & 1 == 1 and len(o7) == 1 and o7[0][1][1:] == [0xFD80, x7 + 2] and
          x8 == 0xDF and len(o8) == 1 and o8[0][1][1:] == [0xFD80, 0xDF] and not oth,
          dict(I7_staged=x7, I7=[[i, e[2]] for i, e in o7], I8_staged=x8,
               I8=[[i, e[2]] for i, e in o8], others=oth))
    # I9: the machine's own POST vector on the row where P1 takes $AB38 twice
    sc9, dbl, p9 = sc_['I9'], None, None
    cur = list(base64.b64decode(sc9['seed']))
    for k, r in enumerate(sc9['rows']):
        if k:
            cur = unpack(cur, r['pre'])
        post = unpack(cur, r['post'])
        if dbl is None and sum(1 for e in r['ev'] if e[0] == 'ab38' and e[1] == 0xFD80) == 2:
            dbl, p9 = r['i'], post
        cur = post
    g9 = (lambda a: p9[VEC.index(a)]) if p9 else (lambda a: -1)
    claim('I9: $AB38 HAS NO ACTIVITY TEST.  A fast-walking P1 on his last death tick takes $AB38 twice '
          '($AAE6 decides before the first run); the first is the final death ($AB64 RES 7, +4 := $50, '
          'X := $18) and the second still ticks +4 to $4F and walks him to $1A with RIGHT held',
          dbl is not None and not (g9(0xFD87) & 0x80) and g9(0xFD84) == 0x4F and g9(0xFD85) == 0x1A
          and g9(0xFDDC) == 0xFF,
          dict(isr=dbl, p7=g9(0xFD87), p4=g9(0xFD84), x=g9(0xFD85), lives=g9(0xFDDC)))

    def post_where(n, pick):
        """the machine's POST vector on the first row of scene n where pick(row) holds"""
        cur = list(base64.b64decode(sc_[n]['seed']))
        for k, r in enumerate(sc_[n]['rows']):
            if k:
                cur = unpack(cur, r['pre'])
            post = unpack(cur, r['post'])
            if pick(r):
                return r['i'], (lambda a, p=post: p[VEC.index(a)])
            cur = post
        return None, (lambda a: -1)

    two = lambda slot: (lambda r: sum(1 for e in r['ev'] if e[0] == 'ab38' and e[1] == slot) == 2)
    i12, g12 = post_where('I12', two(0xFD8A))
    claim('I12: THE SAME FOR P2 AT SLOT 1.  A fast-walking P2 on his last death tick takes $AB38 twice; the '
          'first is the final death (RES 7, X := $D8) and the second still ticks +4 to $4F and walks him to '
          '$D6 with Kempston LEFT held',
          i12 is not None and not (g12(0xFD91) & 0x80) and g12(0xFD8E) == 0x4F and g12(0xFD8F) == 0xD6
          and g12(0xFDE6) == 0xFF,
          dict(isr=i12, p7=g12(0xFD91), p4=g12(0xFD8E), x=g12(0xFD8F), lives=g12(0xFDE6)))
    c10, i10 = ev_('I10', 'calm'), per_row('I10', 0xFD8A)
    claim('I10: A DYING FAST WALKER TICKS TWICE, AND P2\'S RESPAWN CALMS.  P2 takes $AB38 twice on every '
          'dispatching ISR until his respawn (the respawn clears +7 bit 2), once after; the calm runs once, '
          'with IY = $FD8A and $90D0 = $96',
          len(c10) == 1 and c10[0][1][1] == 0xFD8A and c10[0][1][2] == 0x96 and
          len(i10) > 8 and i10[0] == 2 and set(i10) == {1, 2} and i10 == sorted(i10, reverse=True),
          dict(calm=[[i, e[1], e[2]] for i, e in c10], per_isr=i10))
    j11 = ev_('I11', 'jumpedge')
    i11, g11 = post_where('I11', lambda r: any(e[0] == 'jumpedge' for e in r['ev']))
    claim('I11: $AD0C CLEARS THE JUMPER\'S OWN BIT.  With +$5A bit 4 set on both players P2 jumps: the edge '
          'is reached with IY = $FD8A and bit 4 set, and leaves $FDE4 bit 4 clear and $FDDA bit 4 set',
          len(j11) >= 1 and j11[0][1][1] == 0xFD8A and (j11[0][1][2] & 0x10) and
          not (g11(0xFDE4) & 0x10) and (g11(0xFDDA) & 0x10),
          dict(edges=[[i, e[1], e[2]] for i, e in j11], p2=g11(0xFDE4), p1=g11(0xFDDA)))
    c13, i13 = ev_('I13', 'calm'), per_row('I13', 0xFD80)
    claim('I13: A NATURAL DEATH WITH THE FAST WALK RUNS DOUBLED.  From the hit to the respawn every '
          'dispatching ISR runs $AB38 twice for P1, and the respawn (the calm) lands at ISR 186',
          len(i13) >= 40 and set(i13) == {2} and len(c13) == 1 and c13[0][0] == 186 and c13[0][1][1] == 0xFD80,
          dict(per_isr=sorted(set(i13)), rows=len(i13), calm=[i for i, _ in c13]))
    bo = [(r['i'], [e for e in r['ev'] if e[0] == 'blowout']) for r in sc_['I14']['rows']]
    dbl14 = [(i, x) for i, x in bo if len(x) == 2]
    gaps = [x[1][3] - x[0][3] for _, x in dbl14]
    everyo = sum(1 for sc in scs for r in sc['rows'] for e in r['ev'] if e[0] == 'blowout')
    claim('I14: THE FAST WALKER CLICKS TWICE.  A blow click ($ACAF OUT ($FE)) comes once per $AB38 run, so '
          'a fast-walking blower OUTs twice in one ISR, from the same slot, the second 1,000 T or more after '
          'the first; blow OUTs happen only on ODD ISRs (never on a pop-click row)',
          len(dbl14) >= 3 and all(x[0][1] == x[1][1] == 0xFD80 for _, x in dbl14) and min(gaps) > 1000 and
          everyo > 50 and not any(e[0] == 'blowout' for sc in scs for r in sc['rows'] for e in r['ev']
                                  if any(x[0] == 'click' for x in r['ev'])),
          dict(doubled=len(dbl14), gaps=[min(gaps), max(gaps)] if gaps else [], levels=[[x[0][2], x[1][2]] for _, x in dbl14][:12],
               all_blowouts=everyo))
    # ---- $A431: the beam accumulator, bracketed
    a4 = [f['a431'] for f in allf.values()]
    tot = lambda k: sum(x[k] for x in a4)
    outside = {}
    for x in a4:
        for k, v in x['outside'].items():
            outside[k] = outside.get(k, 0) + v
    hi = hi_add = 0                  # $BF16 entries at cached Y >= $C0, and those followed by an add
    for s in scs:
        for r in s['rows']:
            e = r['ev']
            for k, x in enumerate(e):
                if x[0] == 'erase' and x[1] == 'BF16' and x[3] >= 0xC0:
                    hi += 1
                    if k + 1 < len(e) and e[k + 1][0] == 'beam':
                        hi_add += 1
    claim("$A431 IS $A430's OPERAND AND NOTHING BUT THE $A3D4 SEED AND $A430 MOVES IT: every $A3AD pass stores $B9 at $A3D4 and its "
          'first $A3D9 add reads $B9; bracketed at every $A430 call, every pass edge and every ISR edge, the '
          'byte changes by those adds alone; in these scenes no $A430 runs in the main loop (Boris\'s $91D6 '
          'and $8C51 on a LIVE enemy do, elsewhere, with interrupts off: boris_fixture phase (g), and the '
          'M7.49 review\'s probe for $8C51); OUTSIDE a pass the adds come '
          'through $A447 entered from $BF16 (+20: $A480 forced to JP, the shifted erase) and $BE92 (the '
          'capture\'s erase half, +7 here); and a $BF16 at cached Y >= $C0 adds nothing ($A464 reaches the '
          'patched RET first)',
          tot('passes') > 1000 and tot('seed_not_b9') == 0 and tot('first_not_b9') == 0 and
          tot('unaccounted') == 0 and tot('main_calls') == 0 and
          set(outside) <= {'BF16+20', 'BE92+7', 'BE92+20'} and outside.get('BF16+20', 0) > 1000 and
          outside.get('BE92+7', 0) > 0 and hi > 0 and hi_add == 0,
          dict(passes=tot('passes'), calls=tot('calls'), seed_not_b9=tot('seed_not_b9'),
               first_not_b9=tot('first_not_b9'), unaccounted=tot('unaccounted'),
               main_calls=tot('main_calls'), outside=outside, bf16_high=[hi, hi_add]))
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('capture', 'verify'):
        print(__doc__); sys.exit(2)
    global CLEAR
    scs, facts = capture()
    CLEAR = clear_marker()
    out = dict(
        tool='tools/popkill.py',
        vector=ranges_of(VEC), vector_len=len(VEC), hud_masked=len(HUD),
        scalars=['%04X' % a for a in SCALARS],
        clear_marker=CLEAR, scenarios=scs, facts={k: dict(v, b775_bad=v['b775_bad'][:8]) for k, v in facts.items()})
    out['assertions'] = assertions(scs, facts)
    if sys.argv[1] == 'capture':
        with open(FIXTURE, 'w') as f:
            json.dump(out, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes;',
              sum(1 for a in out['assertions'] if a['held']), 'of', len(out['assertions']), 'claims held')
    else:
        old = json.load(open(FIXTURE))
        same = json.dumps(old, sort_keys=True) == json.dumps(json.loads(json.dumps(out)), sort_keys=True)
        print('verify:', 'IDENTICAL' if same else 'DIFFERS')
        sys.exit(0 if same else 1)
    if not all(a['held'] for a in out['assertions']):
        sys.exit(1)


if __name__ == '__main__':
    main()
