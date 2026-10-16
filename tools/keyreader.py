"""KR1 -- the IN-PLAY KEY READER oracle: $ABF4..$ACEB and the Kempston branch $AEF5..$AF29.

The machine reads the controls ONCE PER ODD ISR, inside the player handler $AB38 that
$AA60 dispatches -- P1 then P2 in the same interrupt -- and stores the direction byte at
$ACEB LD (IY+8),C.  Everything below is driven through the real machine code in the
SkoolKit harness; nothing is modelled into the fixture.

THE BOUNDARY.  Rows are taken exactly as tools/capture.py's frame() takes them: run to the
ISR entry $8D72, step into it, run to its RET $8DA1, step over that, sample.  Keys (and the
Kempston byte) change ONLY at that boundary, so a row is one ISR, not one video frame, and
the input column is what the keyboard held for the main loop + ISR that the row closes.
(capture.drive() itself cannot carry the guard and the hooks below, so the loop is
repeated here with the same boundary; the seed carries every field capture.drive records.)

THE READER, read from the code (adis over $ABF4..$ACF0 and $AEF5..$AF29, recon file
scratchpad/keys_machine/ac54_ace8.txt), and CHECKED AGAINST THE MACHINE ON EVERY READ of
every scenario by model() below -- pre-lock C/B at $AC54 and the final C, +7, +9, +$60 and
+0/+1 at $ACEB:

  $ABF4  table = $B605 if (IY+$5A) bit 0 else $B5FD
  $AC00  C = (IY+8) << 4 (previous low nibble -> high nibble), B = (IY+7) bit 0
  $AC0E  first table byte == $1F -> Kempston $AEF5 (only pair 0 is tested)
  $AC15  pair = (IN ($FE) with A=select) AND mask == 0 -> pressed
         LEFT -> SET 3,C, B=0, and pair 2 is SKIPPED (INC HL x2, no IN)
         else RIGHT -> SET 2,C, B=1;  $AC2F (IY+7) bit0 := B;  JUMP -> bit 1;  BLOW -> bit 0
  $AEF5  Kempston: IN ($1F) AND mask != 0 -> pressed; L -> bit3 B=0, R -> bit2 B=1 (NO
         priority: L+R = both bits, B=1), $AF0C facing := B, U($08) -> bit1, F($10) -> bit0
  $AC4B  (IY+7) bit0 := B
  $AC54  ph = (IY+9): 0 or $FF -> skip to $AC9B.
         ph+1 < $11 (ph 1..$0F): LOCK -- C bits 2,3 := previous L/R ((C>>4)&$0C), then $AC83
         ph $10..$FE: if C&$0C != previous L/R -> (IY+9) := $FF and $AC83 on A = C&$0C;
                      unchanged -> $AC9B, facing untouched
  $AC83  L bit set -> B=0; else R set -> B=1; else neither -> B and facing UNCHANGED
         (as $AC2F/$AC4B wrote them); then (IY+7) bit0 := B
  $AC9B  HL = $D7C0 if B==1 else $D920
  $ACA5  cad = (IY+$60): nonzero -> OUT ($FE),cad*8 (speaker/MIC bits, border 0);
         cad := (cad+1) AND (IY+$5F); offset = $580 if [(IY+$5F)==3 ? cad==2 : 4<=cad<7]
         else $2C0; HL += offset.   cad == 0 -> if C bit 4 clear and bit 0 set: cad := 1
         (the blow edge; HL stays the base)
  $ACE5  (IY+0/1) := HL;  $ACEB (IY+8) := C

GUARDS on every run: a write-watch over $FD88 and $FD92 (P1/P2 +8) that records every writer
PC -- $ACEB is the only one allowed while a player is live, anything else is reported by PC;
a PC guard over $D000..$D2FF (never entered: the run stops if it is); every state is
branch-checked ($8DC4 == $C9, the 48K ISR).  No ROM byte is read into the output: the
fixture holds RAM fields only.

Usage:  python tools/keyreader.py capture      -> build/keyreader_fixture.json
        python tools/keyreader.py verify       re-run and diff against the fixture
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, T, PC, B as RB, C as RC, IYh, IYl
import portconfig as pc
from keyprobe import press

FIXTURE = 'build/keyreader_fixture.json'
ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
H_ENTRY, H_PRE, H_STORE = 0xABF4, 0xAC54, 0xACEB
GUARD_LO, GUARD_HI = 0xD000, 0xD300
BRANCH_BYTE = 0x8DC4
P1T, P2T = 0xB5FD, 0xB605
SLOT = (0xFD80, 0xFD8A)
KL, KR, KD, KU, KF = 0x02, 0x01, 0x04, 0x08, 0x10
CURSOR = [0xF7, 0x10, 0xEF, 0x04, 0xEF, 0x01, 0xEF, 0x08]
KEMP = [0x1F, 0x02, 0x1F, 0x01, 0x1F, 0x08, 0x1F, 0x10]
BB_KEYTAB = [0xDF, 0x02, 0xDF, 0x01, 0xFB, 0x01, 0x7F, 0x01,
             0xEF, 0x10, 0xEF, 0x08, 0xEF, 0x02, 0xEF, 0x01]
COLS = ['par', 'ev', 'pc', 'keys', 'kemp', 'rd', 'p1', 'p2']
PCOLS = ['d', 'f7', 'ph', 'cad', 'spr', 'x', 'y']


class Fail(Exception):
    pass


# ---------------------------------------------------------------- the model
def port_fe(keys, hi):
    """harness.Ports.read_port for an even port, from a key-name list"""
    from harness import Ports
    p = Ports()
    for k in keys:
        press(p, k)
    return p.read_port(None, (hi << 8) | 0xFE)


def model(e, tab, keys, kemp):
    """$ABF4..$ACEB from the disassembly.  e = entry fields of the slot."""
    C = (e['d'] << 4) & 0xF0
    B = e['f7'] & 1
    if tab[0] == 0x1F:
        if kemp & tab[1]: C |= 8; B = 0
        if kemp & tab[3]: C |= 4; B = 1
        if kemp & tab[5]: C |= 2
        if kemp & tab[7]: C |= 1
    else:
        if port_fe(keys, tab[0]) & tab[1] == 0:
            C |= 8; B = 0
        elif port_fe(keys, tab[2]) & tab[3] == 0:
            C |= 4; B = 1
        if port_fe(keys, tab[4]) & tab[5] == 0: C |= 2
        if port_fe(keys, tab[6]) & tab[7] == 0: C |= 1
    pre = (C, B)
    ph = e['ph']
    if ph not in (0, 0xFF):
        prev = (C >> 4) & 0x0C
        face = None
        if ph + 1 < 0x11:
            C = (C & 0xF3) | prev
            face = C
        elif (C & 0x0C) != prev:
            ph = 0xFF
            face = C & 0x0C
        if face is not None:
            if face & 8: B = 0
            elif face & 4: B = 1
    f7 = (e['f7'] & 0xFE) | B
    hl = 0xD7C0 if B == 1 else 0xD920
    cad = e['cad']
    if cad:
        cad = (cad + 1) & e['m5f']
        big = (cad == 2) if e['m5f'] == 3 else (4 <= cad < 7)
        hl += 0x580 if big else 0x2C0
    elif not C & 0x10 and C & 1:
        cad = 1
    return pre, dict(d=C, f7=f7, ph=ph, cad=cad, spr=hl)


# ---------------------------------------------------------------- the driver
def slotf(m, s):
    b = SLOT[s]
    return dict(d=m[b + 8], f7=m[b + 7], ph=m[b + 9], cad=m[b + 0x60], m5f=m[b + 0x5F],
                m5a=m[b + 0x5A], spr=m[b] | (m[b + 1] << 8), x=m[b + 5], y=m[b + 6])


def prow(m, s):
    if not m[SLOT[s] + 7] & 0x80:
        return None
    f = slotf(m, s)
    return [f[k] for k in PCOLS]


class Run:
    def __init__(self, state, pokes):
        h = Harness()
        h.load_state_file(pc.state_path(state))
        m = h.memobj.m
        if m[BRANCH_BYTE] != 0xC9:
            raise Fail(f'{state}: $8DC4=${m[BRANCH_BYTE]:02X}, not the 48K branch')
        self.pokes = pokes or {}
        self.h, self.m = h, m
        self.targets = set(range(GUARD_LO, GUARD_HI)) | {ISR_IN, ISR_OUT, H_ENTRY, H_PRE, H_STORE}
        self.fd = h.frame_duration
        self.writers = []          # (row, pc, addr, value) for $FD88/$FD92 writes not at $ACEB
        self.nwrites = 0
        self.last_vf = None
        h.memobj.watch(0xFD88, 0xFD93)

    def go(self, stop):
        h, r = self.h, self.h.sim.registers
        while True:
            reason, _ = h.run_until(self.targets, limit=10 ** 7, stride=1)
            if reason != 'target':
                raise Fail('run_until limit')
            p = r[PC]
            if GUARD_LO <= p < GUARD_HI:
                raise Fail(f'GUARD: PC ${p:04X} inside $D000..$D2FF')
            if p == stop:
                return
            self.hook(p)
            h.step(1)

    def frame(self):
        """capture.frame(): to $8D72, into it, to its RET $8DA1, over it -- with hooks"""
        self.reads = []
        self.go(ISR_IN)
        m = self.m
        vf = self.h.sim.registers[T] // self.fd
        self.dv = 0 if self.last_vf is None else vf - self.last_vf
        self.last_vf = vf
        self.entry = dict(ev=m[0x8DBD], fec4=m[0xFEC4], b54b=m[0xB54B],
                          act=[bool(m[SLOT[s] + 7] & 0x80) for s in (0, 1)],
                          dying=[bool(m[SLOT[s] + 0x5A] & 4) for s in (0, 1)])
        t_in = self.h.sim.registers[T]
        self.h.step(1)
        self.cur = None
        self.go(ISR_OUT)
        self.h.step(1)
        self.isr_t = self.h.sim.registers[T] - t_in

    def _hook(self, p):
        m, r = self.m, self.h.sim.registers
        if p in (ISR_IN, ISR_OUT):
            return                    # a state saved mid-ISR meets $8DA1 before $8D72 (align frame)
        if p != H_ENTRY and self.cur is None:
            return                    # ditto: a read already under way when the state was saved
        iy = (r[IYh] << 8) | r[IYl]
        s = SLOT.index(iy) if iy in SLOT else None
        if s is None:
            raise Fail(f'hook ${p:04X} with IY=${iy:04X}')
        if p == H_ENTRY:
            e = slotf(m, s)
            t = P2T if e['m5a'] & 1 else P1T
            self.cur = dict(s=s, e=e, tab=list(m[t:t + 8]), t=t)
        elif p == H_PRE:
            self.cur['pre'] = (r[RC], r[RB])
        elif p == H_STORE:
            f = slotf(m, s)
            self.cur['out'] = dict(d=r[RC], f7=f['f7'], ph=f['ph'], cad=f['cad'], spr=f['spr'])
            self.reads.append(self.cur)
            self.cur = None

    hook = _hook


def drive(name, state, n, script, pokes=None, check=True):
    """script(k, m, ctx) -> (keys list, kemp byte), called before frame k"""
    R = Run(state, pokes)
    m, h = R.m, R.h
    R.frame()                                     # align, as capture.drive(align=True)
    for a, vals in R.pokes.items():               # pokes AFTER the align ISR, so row 0's read
        for i, v in enumerate(vals):              # is the first one to see them
            m[a + i] = v
    R.h.memobj.log = []
    seed = {
        "8DBD": m[0x8DBD] | (m[0x8DBE] << 8), "8DB6": m[0x8DB6] | (m[0x8DB7] << 8),
        "AA65": m[0xAA65], "FEC4": m[0xFEC4], "FEC5": m[0xFEC5], "FEC9": m[0xFEC9],
        "FED0": m[0xFED0], "B657": m[0xB657], "FDDE": m[0xFDDE], "FDDF": m[0xFDDF],
        "FDE0": m[0xFDE0], "B54B": m[0xB54B],
        "slot0": [m[0xFD80 + i] for i in range(10)],
        "slot1": [m[0xFD8A + i] for i in range(10)],
        "pers1": [m[0xFDDA + i] for i in range(10)],
        "pers2": [m[0xFDE4 + i] for i in range(10)],
        "keytab": list(m[0xB5FD:0xB60D]),
        "x5A": [m[0xFDDA], m[0xFDE4]], "x5F": [m[0xFDDF], m[0xFDE9]], "x60": [m[0xFDE0], m[0xFDEA]],
    }
    ctx = {'rows': [], 'reads': []}
    rows, errs, reads_all = [], [], []
    pbreaks, lost, isr_max = [], [], 0
    for k in range(n):
        keys, kemp = script(k, m, ctx)
        h.ports.release_all()
        for key in keys:
            press(h.ports, key)
        h.ports.kempston = kemp
        pred_odd = (m[0x8DBD] + 1) & 1
        R.frame()
        for pcw, a, v in R.h.memobj.log:
            if a in (0xFD88, 0xFD92):
                R.nwrites += 1
                if pcw != H_STORE:
                    R.writers.append([k, pcw, a, v])
        R.h.memobj.log = []
        E = R.entry
        par = m[0x8DBD] & 1
        if par != pred_odd:                       # $8DBD did not simply count (measured: respawn)
            pbreaks.append([k, par])
        if R.dv != 1:
            lost.append([k, R.dv])
        isr_max = max(isr_max, R.isr_t)
        rd = []
        for rr in R.reads:
            s = rr['s']
            rd.append([s, rr['pre'][0]])
            if check:
                pre, out = model(rr['e'], rr['tab'], keys, kemp)
                if pre != tuple(rr['pre']) or out != rr['out']:
                    errs.append(f'{name} row {k} slot {s}: MODEL MISMATCH entry={rr["e"]} tab={rr["tab"]} '
                                f'keys={keys} kemp={kemp:02X} machine pre={rr["pre"]} out={rr["out"]} '
                                f'model pre={pre} out={out}')
            reads_all.append(dict(k=k, s=s, e=rr['e'], pre=rr['pre'], out=rr['out'], keys=keys, kemp=kemp))
        # the skip rule: a slot is read iff odd ISR, gate $FEC4 open, $B54B == 0, active, not dying
        for s in (0, 1):
            should = bool(par and E['fec4'] and not E['b54b'] and E['act'][s] and not E['dying'][s])
            did = any(x[0] == s for x in rd)
            if should != did:
                errs.append(f'{name} row {k} slot {s}: read={did} but rule says {should} (entry {E})')
        if len(rd) == 2 and [x[0] for x in rd] != [0, 1]:
            errs.append(f'{name} row {k}: read order {rd}')
        row = [par, m[0x8DBD] | (m[0x8DBE] << 8), h.regs[PC], '+'.join(keys), kemp, rd,
               prow(m, 0), prow(m, 1)]
        rows.append(row)
        ctx['rows'].append(dict(par=par, rd=rd, entry=E, m5a=[m[0xFDDA], m[0xFDE4]]))
        ctx['reads'] = reads_all
    h.memobj.unwatch()
    sc = {'name': name, 'state': state,
          'pokes': {f'{a:04X}': v for a, v in (pokes or {}).items()},
          'seed': seed, 'rows': rows, 'writers_not_ACEB': R.writers, 'fd88_writes': R.nwrites,
          'parity_breaks': pbreaks, 'lost_interrupts': lost, 'isr_T_max': isr_max}
    return sc, errs, reads_all


# ---------------------------------------------------------------- scripts
def segs(*parts):
    """(frames, keys, kemp) segments -> script"""
    seq = []
    for nf, keys, kemp in parts:
        seq += [(list(keys), kemp)] * nf
    return (lambda k, m, ctx: seq[k] if k < len(seq) else ([], 0)), len(seq)


def K(s):
    return [x for x in s.split('+') if x]


def s1():
    parts = []
    for ks in ['', '5', '8', '5+8', '7', '8+7', '0', '5+0+7']:
        parts += [(8, K(ks), 0), (4, [], 0)]
    return segs(*parts)


def s2():
    """7 tapped for ONE frame at a time: first only on frames whose ISR is even (the reader
       does not run), then only on odd ones."""
    def f(k, m, ctx):
        odd = (m[0x8DBD] + 1) & 1
        if k < 24:
            return (['7'] if (not odd and (k // 2) % 2 == 0) else []), 0
        if k < 48:
            return (['7'] if (odd and (k // 2) % 2 == 0) else []), 0
        return [], 0
    return f, 60


def s3():
    """7 held; released for exactly one read mid-cadence; re-pressed on the read whose ENTRY
       cadence is 3 (row 7; no restart -- cad == 4 only advances this script's stage);
       held through the cadence end (bit 4 blocks); released one read; pressed (new blow)."""
    st = {'stage': 0}
    def f(k, m, ctx):
        odd = (m[0x8DBD] + 1) & 1
        cad = m[0xFDE0]
        g = st['stage']
        if g == 0:                                  # hold until the blow starts
            if cad: st['stage'] = 1
            return ['7'], 0
        if g == 1:                                  # at a read with cad==2 release for one read
            if odd and cad == 2:
                st['stage'] = 2; return [], 0
            return ['7'], 0
        if g == 2:                                  # re-press when cad == 4 at a read
            if odd and cad == 4:
                st['stage'] = 3; return ['7'], 0
            return ([] if not odd else ['7']) if cad != 4 else [], 0
        if g == 3:                                  # hold until cad back to 0, then 6 more reads
            if cad == 0:
                st['n'] = st.get('n', 0) + (1 if odd else 0)
                if st['n'] > 6:
                    st['stage'] = 4
            return ['7'], 0
        if g == 4:                                  # release for exactly one read
            if odd:
                st['stage'] = 5
            return [], 0
        return ['7'], 0
    return f, 90


def s4(j0, hold1, steps, n=96):
    """one jump; j0 held until the jump starts, then hold1, then at a read whose entry phase is
       steps[i][0] switch to steps[i][1]."""
    st = {'stage': 'j', 'i': 0, 'held': K(hold1)}
    def f(k, m, ctx):
        odd = (m[0x8DBD] + 1) & 1
        ph = m[0xFD89]
        if st['stage'] == 'j':
            if ph != 0:
                st['stage'] = 'air'
            else:
                return K(j0), 0
        if st['i'] < len(steps) and odd and ph == steps[st['i']][0]:
            st['held'] = K(steps[st['i']][1]); st['i'] += 1
        return st['held'], 0
    return f, n


def s12():
    """8 held and 7 tapped on every other read, to fill the bubble pool"""
    def f(k, m, ctx):
        return (['8', '7'] if (k // 2) % 2 == 0 else ['8']), 0
    return f, 400


SCEN = []


def add(name, state, covers, fn_n, pokes=None):
    SCEN.append((name, state, covers, fn_n, pokes))


add('S1', 'round1_48', 'LEFT priority, bits, high nibble', s1())
add('S2', 'round1_48', 'a key held only on a non-reading (even) ISR is never seen', s2())
add('S3', 'round1_48', 'the blow edge (bit 4), no restart mid-cadence', s3())
S4 = [('S4a', '0', '', [(0x01, '5')], 'nothing->5 at phase 1: locked (none), facing left kept, drop at $10'),
      ('S4b', '0', '', [(0x0F, '5')], 'nothing->5 at phase $0F: locked, drop at $10'),
      ('S4c', '0+8', '8', [(0x10, '5')], '8->5 at phase $10: drop to $FF'),
      ('S4d', '0+8', '8', [(0x11, '5')], '8->5 at phase $11: drop'),
      ('S4e', '0', '', [(0x10, '5')], 'nothing->5 at $10: drop'),
      ('S4f', '0+8', '8', [(0x10, '')], '8->nothing at $10: drop'),
      ('S4g', '0+8', '8', [], '8 held through the arc: no drop'),
      ('S4h', '0+8', '8', [(0x10, '5'), (0xFF, '8')], 'change during $FF: no lock, phase stays $FF'),
      ('S4i', '0+5', '5', [(0x03, '8')], '5->8 at phase 3: locked L, $AC83 turns facing back left'),
      ('S4j', '0+8', '8', [(0x0F, '5')], '8->5 at $0F: locked R, $AC83 facing right; drop at $10')]
for nm, j0, h1, st, cov in S4:
    add(nm, 'round1_48', '$AC54 air rule: ' + cov, s4(j0, h1, st))
add('S5', 'round1_48', 'the ($00,$00) permanently-pressed pair (BLOW pair poked 00 00)',
    segs((20, [], 0)), {0xB603: [0x00, 0x00]})
add('S6', 'round1_48', '$1F only means Kempston in pair 0 (JUMP pair poked 1F 08)',
    segs(*[p for ks in ['N', 'J', 'U', 'H', '0'] for p in ((4, K(ks), 0), (4, [], 0))],
         (4, [], KU), (4, [], 0)), {0xB601: [0x1F, 0x08]})
add('S7', 'round1_48', 'Kempston: no LEFT priority, L+R faces right, down ignored',
    segs(*[p for kb in [KL, KL | KR, KD, KU | KF, KR, KL] for p in ((8, [], kb), (4, [], 0))]),
    {P1T: KEMP})
# S7b (M7.44 review of the prototype): $AC83 decides facing with BIT 3 first -- LEFT wins
# (only the LOCK case is driven: the second jump ends in an enemy death, row 83)
# when BOTH L and R reach it, which only happens AIRBORNE (the lock or the drop carries the
# pair in) and only from Kempston (the keyboard has LEFT priority).  No other scenario puts
# both bits there, so a RIGHT-first $AC83 was an undetected mutant.
add('S7b', 'round1_48', 'Kempston L+R held through a jump: $AC83 tests LEFT first',
    segs((8, [], KL | KR), (4, [], 0), (40, [], KL | KR | KU), (8, [], 0),
         (8, [], KR), (40, [], KL | KR | KU), (8, [], 0)),
    {P1T: KEMP})
# S14 (M7.44 review): RAPID FIRE -- +$5F = 3 (the power-up at $88EF sets it), so the cadence
# is (cad+1) AND 3 and the big frame is cad == 2: the $ACBA/$ACC9 branch no other scenario takes.
add('S14', 'round1_48', 'rapid fire: +$5F = 3, the blow cadence masked by 3 and the cad==2 frame',
    segs((60, ['7'], 0), (4, [], 0), (30, ['7'], 0)), {0xFDDF: [0x03]})
add('S8', 'round1_2p48', 'P2 table select (Kempston), P1+P2 same-ISR order; the twop script',
    segs((60, ['8'], KL), (340, ['8'], KL | KU)))
add('S9', 'round1_2p48', 'BB_KEYTAB seed, both keyboards',
    segs(*[p for ks in ['O', 'P', 'O+P', '6', '7', '6+7', 'O+7', 'P+6', 'Q+9', 'SPACE+0',
                         'O+P+Q+SPACE+6+7+9+0'] for p in ((6, K(ks), 0), (4, [], 0))]),
    {P1T: BB_KEYTAB})
add('S10', 'round1_48', 'all-zero tables (the tape): C=$0B then $BB',
    segs((12, [], 0)), {P1T: [0] * 16})
add('S11', 'round1_48', 'reader skipped while dying (+8 stale); death and respawn',
    segs((131, ['8'], 0), (100, ['5'], 0), (100, ['0', '7'], 0), (60, ['8'], 0)))
# S12 (a lost interrupt) is DROPPED: 400 ISRs of 8 held + 7 tapped every other read on round1_48
# peaked at 61285 T per ISR (< 69888), no interrupt lost; isrcost_fixture's five states peak at
# 57273 T.  It could not be arranged reliably, so it is not faked.  The no-lost-interrupt
# assertion below still guards every scenario.
add('S13', 'round1_48', 'reader skipped under the $B54B settle divert (poked 20)',
    segs((60, ['8'], 0)), {0xB54B: [20]})


# ---------------------------------------------------------------- assertions
def assertions(res):
    """the machine report's measured claims, each checked against the scenario covering it"""
    A = []

    def chk(name, ok, detail, refuted=False):
        a = {'claim': name, 'held': bool(ok), 'measured': detail}
        if refuted:
            a['refuted_as_stated'] = True     # kept FAILED on purpose; the measured claim follows
        A.append(a)

    rd = {nm: v[2] for nm, v in res.items()}
    sc = {nm: v[0] for nm, v in res.items()}

    # LEFT priority: 5+8 -> pre-lock low nibble 8, steady C=$88
    r58 = [x for x in rd['S1'] if x['s'] == 0 and set(x['keys']) == {'5', '8'}]
    chk('S1 LEFT priority: 5+8 reads LEFT only; steady C=$88',
        r58 and all(x['pre'][0] & 0x0F == 8 for x in r58) and r58[-1]['out']['d'] == 0x88,
        [f"{x['pre'][0]:02X}" for x in r58])
    for ks, bit in [('5', 8), ('8', 4), ('0', 2), ('7', 1)]:
        rr = [x for x in rd['S1'] if x['s'] == 0 and x['keys'] == [ks]]
        chk(f'S1 key {ks} -> bit {bit:#x}', rr and all(x['pre'][0] & 0x0F == bit for x in rr),
            [f"{x['pre'][0]:02X}" for x in rr])
    # high nibble = previous stored low nibble
    allr = [x for v in rd.values() for x in v]
    chk('high nibble of C = previous +8 low nibble (every read, every scenario)',
        all(x['pre'][0] >> 4 == x['e']['d'] & 0x0F for x in allr), len(allr))
    # S2
    r2 = rd['S2']
    ev_taps = [k for k in range(24) if sc['S2']['rows'][k][3] == '7']
    od_taps = [k for k in range(24, 48) if sc['S2']['rows'][k][3] == '7']
    chk('S2 7 held only on even-ISR frames is never seen (no BLOW bit, no cadence)',
        ev_taps and all(sc['S2']['rows'][k][0] == 0 for k in ev_taps)
        and all(x['pre'][0] & 1 == 0 for x in r2 if x['k'] < 24)
        and all(x['out']['cad'] == 0 for x in r2 if x['k'] < 24),
        {'even_taps': ev_taps})
    chk('S2 7 held on an odd-ISR frame is seen', od_taps and all(
        any(x['k'] == k and x['pre'][0] & 1 for x in r2) for k in od_taps), {'odd_taps': od_taps})
    # S3
    cads = [(x['k'], x['e']['cad'], x['out']['cad'], x['pre'][0], '+'.join(x['keys'])) for x in rd['S3']]
    starts = [c for c in cads if c[1] == 0 and c[2] == 1]
    chk('S3 blow edge: exactly two blows (initial press, press after one released read); '
        'no restart mid-cadence; held key blocked by bit 4',
        len(starts) == 2 and all(not (c[1] and c[2] == 1) for c in cads), cads)
    # S4
    ph_seen = {}
    for nm in [s[0] for s in S4]:
        for x in rd[nm]:
            if x['s'] != 0: continue
            e, o = x['e']['ph'], x['out']['ph']
            prev = (x['pre'][0] >> 4) & 0x0C
            chg = (x['pre'][0] & 0x0C) != prev
            if e in (0,):
                continue
            kind = ('lock' if 1 <= e <= 0x0F else ('drop' if o == 0xFF and e != 0xFF else
                    ('ff' if e == 0xFF else 'keep')))
            ph_seen.setdefault((e, chg, kind), []).append(nm)
    need = [(1, True, 'lock'), (0x0F, True, 'lock'), (0x10, True, 'drop'), (0x11, True, 'drop'),
            (0x10, False, 'keep'), (0x18, False, 'keep'), (0xFF, True, 'ff')]
    chk('S4 air-rule edges covered: change at 1 and $0F locks; change at $10 and $11 drops to $FF; '
        'no change at $10..$18 keeps; change at $FF neither locks nor re-drops',
        all(n in ph_seen for n in need),
        {f'{e:02X}/{"chg" if c else "same"}/{kd}': sorted(set(v)) for (e, c, kd), v in sorted(ph_seen.items())})
    x = [x for x in rd['S4a'] if x['e']['ph'] == 1][0]
    chk('S4a $AC83: lock leaves neither L nor R -> facing stays LEFT as $AC2F wrote it',
        x['out']['d'] & 0x0C == 0 and x['out']['f7'] & 1 == 0 and x['out']['spr'] == 0xD920, x['out'])
    x = [x for x in rd['S4i'] if x['e']['ph'] == 3][0]
    chk('S4i $AC83: 8 pressed while locked to L -> facing back LEFT (B from $AC83, not $AC2F)',
        x['pre'][1] == 1 and x['out']['f7'] & 1 == 0 and x['out']['d'] & 0x0C == 8, x['out'])
    chk('S4 no death in any S4 sub-scenario',
        not any(c['entry']['dying'][0] for nm in [s[0] for s in S4] for c in res[nm][3]),
        [nm for nm in [s[0] for s in S4] if any(c['entry']['dying'][0] for c in res[nm][3])])
    # S5
    r5 = [x for x in rd['S5'] if x['s'] == 0]
    chk('S5 ($00,$00) BLOW pair: bit 0 set on every read with no key; exactly one blow',
        all(x['pre'][0] & 1 for x in r5) and sum(1 for x in r5 if x['e']['cad'] == 0 and x['out']['cad'] == 1) == 1,
        [f"{x['out']['d']:02X}/{x['out']['cad']}" for x in r5])
    # S6
    res6 = {}
    for x in rd['S6']:
        if x['s'] == 0:
            key = '+'.join(x['keys']) or (f"kemp{x['kemp']:02X}" if x['kemp'] else '')
            if key: res6.setdefault(key, set()).add(x['pre'][0] & 2)
    chk('S6 JUMP pair (1F,08) read as keyboard rows $7F|$BF|$DF: N/J/U jump; H, 0 and Kempston U do not',
        res6.get('N') == {2} and res6.get('J') == {2} and res6.get('U') == {2}
        and res6.get('H') == {0} and res6.get('0') == {0} and res6.get('kemp08') == {0},
        {k: sorted(v) for k, v in res6.items()})
    # S7
    lr = [x for x in rd['S7'] if x['s'] == 0 and x['kemp'] == KL | KR]
    chk('S7 Kempston L+R: both bits (C low $C, steady $CC), facing RIGHT, sprite $D7C0 base',
        lr and all(x['pre'][0] & 0x0F == 0x0C for x in lr) and lr[-1]['out']['d'] == 0xCC
        and all(x['out']['f7'] & 1 for x in lr) and lr[0]['e']['f7'] & 1 == 0,
        [(f"{x['out']['d']:02X}", x['out']['f7'] & 1, f"{x['out']['spr']:04X}", x['e']['ph']) for x in lr])
    dd = [x for x in rd['S7'] if x['s'] == 0 and x['kemp'] == KD]
    chk('S7 Kempston DOWN ignored', dd and all(x['pre'][0] & 0x0F == 0 for x in dd),
        [f"{x['pre'][0]:02X}" for x in dd])
    # S7b
    lk = [x for x in rd['S7b'] if x['s'] == 0 and x['e']['ph'] and x['e']['ph'] < 0x10
          and x['pre'][0] & 0x0C == 0x0C]
    chk('S7b $AC83 LEFT first: a lock carrying Kempston L+R turns facing LEFT ($D920)',
        lk and all(x['out']['f7'] & 1 == 0 and x['out']['spr'] == 0xD920 for x in lk),
        [(f"{x['out']['d']:02X}", x['e']['ph'], f"{x['out']['spr']:04X}") for x in lk][:6])
    # S14
    r14 = [x for x in rd['S14'] if x['s'] == 0]
    cads = [x['out']['cad'] for x in r14]
    chk('S14 rapid fire: the cadence never exceeds 3 (masked by +$5F) and the cad==2 frame uses +$580',
        cads and max(cads) <= 3 and any(c == 2 for c in cads)
        and all(x['out']['spr'] in (0xD7C0 + 0x580, 0xD920 + 0x580) for x in r14 if x['out']['cad'] == 2),
        cads[:24])
    # S8
    both = {}
    for x in rd['S8']:
        both.setdefault(x['k'], []).append(x['s'])
    p2 = [x for x in rd['S8'] if x['s'] == 1]
    chk('S8 P2 reads $B605 (Kempston) and P1 then P2 in the same ISR',
        all(v == [0, 1] for v in both.values() if len(v) == 2) and p2
        and all(x['pre'][0] & 0x0F == ((8 if x['kemp'] & KL else 0) | (2 if x['kemp'] & KU else 0)) for x in p2),
        {'isrs_with_both': sum(1 for v in both.values() if v == [0, 1]),
         'p1_only': sum(1 for v in both.values() if v == [0]), 'p2_only': sum(1 for v in both.values() if v == [1])})
    ent = res['S8'][3]
    p1dead = [k for k, c in enumerate(ent) if c['entry']['dying'][0]]
    p2dead = [k for k, c in enumerate(ent) if c['entry']['dying'][1]]
    chk('S8 (spec 3.4) one player dying does not stop or reorder the other player read: P2 read on every odd '
        'ISR while P1 died, P1 on every odd ISR while P2 died',
        p1dead and p2dead
        and all(any(x['k'] == k and x['s'] == 1 for x in rd['S8']) for k in p1dead if sc['S8']['rows'][k][0])
        and all(any(x['k'] == k and x['s'] == 0 for x in rd['S8']) for k in p2dead if sc['S8']['rows'][k][0]),
        {'p1_dying_isrs': [p1dead[0], p1dead[-1]] if p1dead else None,
         'p2_dying_isrs': [p2dead[0], p2dead[-1]] if p2dead else None,
         'parity_breaks': sc['S8']['parity_breaks']})
    # S9
    r9 = rd['S9']
    ok9 = True
    for x in r9:
        ks = set(x['keys'])
        if x['s'] == 0:
            want = (8 if 'O' in ks else (4 if 'P' in ks else 0)) | (2 if 'Q' in ks else 0) | (1 if 'SPACE' in ks else 0)
        else:
            want = (8 if '6' in ks else (4 if '7' in ks else 0)) | (2 if '9' in ks else 0) | (1 if '0' in ks else 0)
        ok9 &= (x['pre'][0] & 0x0F) == want
    chk('S9 BB_KEYTAB: P1 O/P/Q/SPACE, P2 6/7/9/0, LEFT priority on both', ok9 and len(r9) > 0, len(r9))
    # S10
    r10 = [f"{x['out']['d']:02X}" for x in rd['S10'] if x['s'] == 0]
    chk('S10 all-zero table: C=$0B then $BB', r10[:2] == ['0B', 'BB'] and set(r10[1:]) == {'BB'}, r10)
    # S11: dying skip + stale +8
    rows = sc['S11']['rows']
    dying = [k for k, c in enumerate(res['S11'][3]) if c['entry']['dying'][0]]
    resp = dying[-1] if dying else None           # the respawn ISR: $ABA1 LD (IY+8),1
    stale = all(rows[k][6][0] == rows[dying[0] - 1][6][0] for k in dying[:-1]) and rows[resp][6][0] == 1         and sc['S11']['writers_not_ACEB'] == [[resp, 0xABA1, 0xFD88, 1]] if dying else False
    chk('S11 reader skipped while dying: no read on any dying ISR, +8 stale through the death; '
        'the respawn ISR writes +8 := 1 at $ABA1 (the only non-$ACEB writer)',
        dying and not any(x['k'] in dying for x in rd['S11']) and stale,
        {'dying_isrs': [dying[0], dying[-1]] if dying else None,
         'd_during': sorted(set(rows[k][6][0] for k in dying if rows[k][6])) if dying else None,
         'parity_breaks': sc['S11']['parity_breaks'],
         'writers_not_ACEB': sc['S11']['writers_not_ACEB']})
    # S12
    chk('no lost interrupt in any scenario (every ISR entered one video frame after the last)',
        not any(v[0]['lost_interrupts'] for v in res.values()),
        {nm: v[0]['isr_T_max'] for nm, v in res.items()})
    # S13
    r13 = sc['S13']['rows']
    arm = [k for k, c in enumerate(res['S13'][3]) if c['entry']['b54b']]
    chk('S13 reader skipped under $B54B: no read while armed, reads resume after',
        arm and not any(x['k'] in arm for x in rd['S13']) and any(x['k'] > arm[-1] for x in rd['S13']),
        {'armed_isrs': [arm[0], arm[-1]] if arm else None,
         'd_while_armed': sorted(set(r13[k][6][0] for k in arm))})
    nsp, badsp = 0, []
    for nm, v in res.items():
        for x in v[2]:
            if v[3][x['k']]['m5a'][x['s']] & 4:
                continue                      # hit later in the same ISR: the death sprite takes over
            nsp += 1
            if v[0]['rows'][x['k']][6 + x['s']][4] != x['out']['spr']:
                badsp.append([nm, x['k'], x['s']])
    chk('+0/+1 after the ISR == the $ACE5 write on every read (physics $ACF0.. adds no walk frame)',
        not badsp, {'reads': nsp, 'differ': badsp[:10]})
    from capture import check_boundary
    bad = {nm: check_boundary([{'pc': r[2]} for r in v[0]['rows']])[1] for nm, v in res.items()}
    chk('every row lands at the ISR-exit boundary (capture.check_boundary)', not any(bad.values()),
        {k: v for k, v in bad.items() if v})
    # every scenario: only $ACEB writes +8
    wr = {nm: v[0]['writers_not_ACEB'] for nm, v in res.items() if v[0]['writers_not_ACEB']}
    chk('write-watch: $ACEB is the only writer of $FD88/$FD92 (exceptions listed by PC)', not wr,
        {nm: [[k, f'{p:04X}', f'{a:04X}', v] for k, p, a, v in w] for nm, w in wr.items()}, refuted=bool(wr))
    ok = all(p == 0xABA1 and v == 1 and res[nm][3][k]['entry']['dying'][(a - 0xFD88) // 10]
             for nm, w in wr.items() for k, p, a, v in w)
    chk('write-watch, as measured: the only other writer is the respawn $ABA1 LD (IY+8),1, '
        'on the dying ISR that ends the death', ok,
        {nm: [[k, f'{p:04X}', f'{a:04X}', v] for k, p, a, v in w] for nm, w in wr.items()})
    return A


def ctx_capture(only=None):
    res, errs = {}, []
    for nm, st, cov, (fn, n), pokes in SCEN:
        if only and nm not in only:
            continue
        holder = {}
        def fn2(k, m, ctx, fn=fn):
            holder['ctx'] = ctx
            return fn(k, m, ctx)
        sc, e, reads = drive(nm, st, n, fn2, pokes)
        sc['covers'] = cov
        res[nm] = (sc, e, reads, holder['ctx']['rows'])
        errs += e
        print(f'{nm}: {n} rows, {len(reads)} reads, {len(e)} errors', flush=True)
    return res, errs


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
    res, errs = ctx_capture(only)
    for e in errs[:40]:
        print('ERR', e)
    A = assertions(res) if not only else []
    for a in A:
        print(('HELD  ' if a['held'] else 'FAILED'), a['claim'], '|', json.dumps(a['measured'])[:400])
    fx = {
        'note': __doc__.split('Usage:')[0].strip(),
        'boundary': 'capture.frame(): $8D72 -> step -> $8DA1 -> step; keys change only here; one row per ISR',
        'cols': COLS, 'pcols': PCOLS,
        'col_notes': {'par': '$8DBD & 1 after the ISR (1 = the odd, reading ISR)',
                      'ev': '$8DBD/$8DBE after the ISR', 'pc': 'interrupted main-loop PC',
                      'keys': 'Spectrum keys held for this row', 'kemp': 'port $1F byte (active high)',
                      'rd': '[slot, C at $AC54 (before the air rule)] per read, in machine order',
                      'p1/p2': 'd=+8 f7=+7 ph=+9 cad=+$60 spr=+0|+1<<8 x=+5 y=+6 after the ISR; null if inactive'},
        'model_mismatches': len([e for e in errs if 'MODEL' in e]),
        'errors': errs,
        'assertions': A,
        'scenarios': [res[nm][0] for nm, *_ in SCEN if nm in res],
    }
    if cmd == 'capture' and not only:
        with open(FIXTURE, 'w') as f:
            json.dump(fx, f, separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE))
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new = json.loads(json.dumps(fx, separators=(',', ':')))
        same = old['scenarios'] == new['scenarios'] and old['assertions'] == new['assertions']
        print('VERIFY', 'IDENTICAL' if same else 'DIFFERS')
        if not same:
            sys.exit(1)
    if errs or any(not a['held'] and not a.get('refuted_as_stated') for a in A):
        sys.exit(2)


if __name__ == '__main__':
    main()
