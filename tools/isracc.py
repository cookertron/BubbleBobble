"""M7.114c (measurement) -- THE ISRs' OWN CONTENTION: every interrupt's ACCESS PROGRAM, on the real load.

Until M7.114c the engine's isrCost was the machine's UNCONTENDED ISR T (M7.99e, M7.113 R1Td): the odd ISR's $A3AD draw
runs past 14,335 T into the screen's lines, and every display access it makes there waits for the ULA.  This oracle
measures, on the REAL LOAD (passacc's drive: boot.pkl's $F5BC, the KEYBOARD menu, the title, round 1 and play, keys at
each ISR's end), every interrupt from frame ISR_FROM to LAST:

  isrs      label (the boundary it was taken at), its ACCEPTANCE PHASE (T mod 69,888 at the end of the instruction the
            interrupt was taken after), its T from the acceptance to the return, its contention delay D, and its
            PROGRAM per class -- every contended access ($4000..$7FFF, the ULA port's I/O cycle as SkoolKit's $4000
            pseudo-address): plain offset from the acceptance, T into its instruction; count and SHA-1 per class
  classes   ent  $A447..$A8FF -- $A447's erase and draw, called from $A3AD's pass ($A402) in the odd ISR
            bent $A447..$A8FF called from anywhere else (the even ISR's bubble-slot entries)
            in   $AB00..$AEFF -- the player handler's port reads ($AA60's slots 0 / 1)
            b5   $B500..$B5FF -- the settler's $73A6 reads
            bub  $B900..$BDFF -- the bubble blitters of the even ISR
  tmpl      $A447's erase and draw TEMPLATES (a sweep from round1_48: each path x Y & 7, three Y and two X bases, every
            sub-shift): (plain offset from $A447's entry, T into the instruction, row, column) of each display access --
            erase at the cached position with no beam carry ($A431 = 0), draw with no erase (bit 6 clear) on toggle
            phase 1.  ASSERTED one template per key.  M7.115c: S (by the draw's key) -- the same draw from type 0's
            facing-1 bank $5B80, which is CONTENDED: its sprite reads (offset, T into the instruction), the copy's
            bytes in order (asserted); the display's accesses asserted the D template's.

ASSERTED: each ISR's D is its program (all classes, in order) replayed from its acceptance phase -- each access waits
the ULA's delay at its wall phase -- so an ISR's contended T is a function of its phase and its program alone.
No ROM byte: offsets, T, phases and digests only.

Usage:  python tools/isracc.py            (-> build/isracc_fixture.json, ~20 s)
        python tools/isracc.py verify     (re-measure, compare, say MATCH)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, GUARD, expand, Fail
from harness import Harness, PC, T, IFF, SP
from skoolkit.cmiosimulator import DELAYS_48K
import portconfig as pcfg
import entdraw as ed
import passacc as pa

FIXTURE = 'build/isracc_fixture.json'
FD = 69888
ISR_FROM, LAST = 400, 760
CLASSES = ('ent', 'bent', 'in', 'b5', 'bub')
SLOT = 0xFDA8
SRC = 0x5B80                   # M7.115c: type 0's facing-1 sprite bank, the runtime mirror (BB_ENEMY_SPR)
B9E7_HEAD = 111 + 64           # BB_DR.PRO + BB_DR.SEL.EMPTY: $B9E7's entry to the body's first instruction


def cls_of(pc, caller):
    if 0xA447 <= pc < 0xA900:
        return 'ent' if caller == 0xA405 else 'bent'
    if 0xAB00 <= pc < 0xAF00:
        return 'in'
    if 0xB500 <= pc < 0xB600:
        return 'b5'
    if 0xB900 <= pc < 0xBE00:
        return 'bub'
    raise Fail('an ISR access at $%04X outside the known classes' % pc)


def digest(prog):
    return hashlib.sha1(''.join('%d:%d;' % (o, k) for o, k in prog).encode()).hexdigest()[:16]


def measure():
    h, m, r = world('boot')
    seq = expand(pa.SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    sim.t0, sim.t1 = -1, 1 << 40
    ia = h.int_active
    assert h.frame_duration == FD
    nb = (r[T] // FD + 1) * FD
    st = {'pc': 0, 'isr': None, 'I': None, 'caller': None}
    frame, in_scan, pending = 0, False, None
    isrs = []
    cm.keys(h, keyf(0))
    oc = sim.contend

    def cont(t, timings):
        I = st['I']
        if I is not None and I['l'] >= ISR_FROM:
            tt, k = t, 0
            for a, ts in timings:
                if 0x4000 <= a < 0x8000:
                    d = DELAYS_48K[tt % FD]
                    I['acc'].append((cls_of(st['pc'], st['caller']), tt - I['t0'] - I['D'], k))
                    I['D'] += d; tt += d
                tt += ts; k += ts
        return oc(t, timings)
    sim.contend = cont
    while frame <= LAST:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += FD
        isr = st['isr']
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            if in_scan: pending = keyf(isr[2])
            else: cm.keys(h, keyf(isr[2]))
            I = st['I']
            I['T'] = r[T] - I['t0']
            if I['l'] >= ISR_FROM: isrs.append(I)
            st['isr'] = None; st['I'] = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending); pending = None
        if pc in GUARD:
            raise Fail('guard at $%04X' % pc)
        if pc == 0xF7B8:
            in_scan = True
        if st['I'] is not None and pc == 0xA447:
            st['caller'] = m[r[SP]] | (m[(r[SP] + 1) & 0xFFFF] << 8)
        st['pc'] = pc
        ops[mem[pc]]()
        if r[IFF] and r[T] % FD < ia:
            b0, s0, t_ = r[PC], r[SP], r[T]
            if sim.accept_interrupt(r, mem, pc):
                assert st['isr'] is None, 'an interrupt inside the ISR'
                lab = frame + (1 if r[T] >= nb else 0)
                st['isr'] = (b0, s0, lab)
                st['I'] = {'l': lab, 't0': t_, 'ph': t_ % FD, 'D': 0, 'acc': []}
    sim.contend = oc
    return isrs


def replay(I):
    D = 0
    for c, o, k in I['acc']:
        D += DELAYS_48K[(I['t0'] + o + D) % FD]
    return D


def a447(h, base, flags, cx, cy, x, y, entry=0xA447, slot=SLOT, kind=0, spr=0xC100):
    """$A447 (or $B9E7) on a synthetic slot: [(pc, k, plain offset from the entry, address)] of every contended access"""
    m = h.memobj.m
    m[:] = base
    m[slot:slot + 10] = bytes([spr & 0xFF, spr >> 8, cy, cx, 0, x, y, flags, 0, kind])
    m[0xA3B2] = 1; m[0xA431] = 0; m[0xAA5F] = 5
    return call_prog(h, entry, slot)[0]


def call_prog(h, entry, iy):
    """call `entry` (IY = iy) on the world as it stands: its contended accesses and the PCs it ran"""
    m, sim, r = h.memobj.m, h.sim, h.sim.registers
    acc, st, pcs = [], {'t0': 0, 'D': 0, 'pc': 0}, set()
    oc = sim.contend

    def cont(t, timings):
        tt, k = t, 0
        for a, ts in timings:
            if 0x4000 <= a < 0x8000:
                d = DELAYS_48K[tt % FD]
                acc.append((st['pc'], k, tt - st['t0'] - st['D'], a))
                st['D'] += d; tt += d
            tt += ts; k += ts
        return oc(t, timings)
    sim.t0, sim.t1 = -1, 1 << 40
    sim.contend = cont
    sp = 0xFC80                                          # an uncontended stack ($B9E7 pushes)
    for s in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF; m[sp], m[sp + 1] = s & 0xFF, s >> 8
    r[SP] = sp
    r[10], r[11] = iy >> 8, iy & 0xFF                    # IY
    r[PC] = entry
    st['t0'] = r[T]
    ops, mem, n = sim.opcodes, sim.memory, 0
    while r[PC] not in h.SENTINELS:
        st['pc'] = r[PC]
        pcs.add(r[PC])
        ops[mem[r[PC]]]()
        n += 1
        assert n < 1000000, '$%04X did not return' % entry
    sim.contend = oc
    return acc, pcs


# M7.114c: the bubble manager's paths the real load does not reach, $B62C called on round1_48 with one pool slot poked
# (the rest of the pool emptied): (name, the slot's ten bytes from the world, $A431, the PC that proves the path)
def even_scenes():
    h = Harness(contended=True)
    h.load_state_file(pcfg.state_path('round1_48'))
    m = h.memobj.m
    base = bytes(m)
    ex, ey = base[0xFD99], base[0xFD9A]
    assert base[0xFD9B] & 0x80, 'round1_48: slot 2 is not live'
    cap = base[0xFDDE]
    SC = [('travel', [0x80, 0xC7, 0x60, 0x70, 3, 0x70, 0x60, 0x81, 0, 0], 0x10, 0xBE55),
          ('travel_carry', [0x80, 0xC7, 0x60, 0x70, 3, 0x70, 0x60, 0x81, 0, 0], 0xF0, 0xBE55),
          ('capture', [0x80, 0xC7, ey, (ex - 8) & 0xFF, 3, (ex - 8) & 0xFF, ey, 0x81, 0, 0], 0xF0, 0xBE6D),
          ('rise', [0x80, 0xC7, 0x60, 0x70, cap, 0x70, 0x60, 0x81, 0, 0], 0xF0, 0xBEE8),
          ('held', [0x00, 0xC9, 0x10, 0xF9, 0x10, 0x70, 0x60, 0x84, 0, 1], 0x10, 0xBA05)]   # +2/+3: its shadow marker
    out = {}
    for name, slot, acc0, proof in SC:
        m[:] = base
        for k in range(12): m[0xFED8 + 10 * k + 7] = 0
        m[0xFED8:0xFED8 + 10] = bytes(slot)
        m[0xA431] = acc0
        pokes = [[0xFD80 + i, base[0xFD80 + i]] for i in range(0x6A)] + [[0xAA57, base[0xAA57]]] + [[0xFED8 + 10 * k + 7, 0] for k in range(1, 12)] + [[0xFED8 + i, v] for i, v in enumerate(slot)] + [[0xA431, acc0]]
        acc, pcs = call_prog(h, 0xB62C, 0)
        assert proof in pcs, '%s: $%04X not reached' % (name, proof)
        out[name] = {'pokes': pokes, 'prog': [[o, k] for p, k, o, a in acc], 'proof': proof}
    return out


def box_rc(m, X, Y, a):
    for row in range(16):
        b = ed.row_base(m, (Y + row) & 0xFF, X)
        for c in range(3):
            if ed.col_addr(b, c) == a:
                return row, c
    raise Fail('$%04X is not in the box at (%d, %d)' % (a, X, Y))


def templates():
    h = Harness(contended=True)
    h.load_state_file(pcfg.state_path('round1_48'))
    m = h.memobj.m
    base = bytes(m)
    E, D = {}, {}
    for sh in (0, 2, 4, 6):
        for y7 in range(8):
            for Y0 in (0x40, 0x68, 0x90):
                for X0 in (0x40, 0x88):
                    X, Y = X0 + sh, Y0 + y7
                    acc = a447(h, base, 0xC0, X, Y, 0x10, 0x18)       # erase at (X, Y); the draw elsewhere
                    t = tuple((o, k) + box_rc(m, X, Y, a) for p, k, o, a in acc if 0xA469 <= p < 0xA5D9)
                    E.setdefault('E%d%d' % (sh != 0, y7), set()).add(t)
                    acc = a447(h, base, 0x80, 0, 0, X, Y)              # no erase (bit 6 clear); the draw at (X, Y)
                    assert all(p >= 0xA5D9 for p, k, o, a in acc)
                    t = tuple((o, k) + box_rc(m, X, Y, a) for p, k, o, a in acc)
                    D.setdefault('D%d%d' % (sh != 0, y7), set()).add(t)
                    # M7.115c: the same draw from type 0's facing-1 bank, $5B80 -- CONTENDED: its sprite reads (the
                    # blitter's POPs) are accesses too.  A bank is 352 bytes: the aligned copy (64) and three shifted
                    # ones (96 each, by (X & 6) / 2, gfx.js bbBlit16).  The display's accesses are the template above; the
                    # rest are the source's, (offset, k), ASSERTED to read the shift's copy byte after byte from its start
                    acc = a447(h, base, 0x80, 0, 0, X, Y, spr=SRC)
                    cb = SRC + (0 if sh == 0 else 64 + 96 * (sh // 2 - 1))
                    sa = [(o, k, a) for p, k, o, a in acc if SRC <= a < SRC + 352]
                    assert [a - cb for o, k, a in sa] == list(range(64 if sh == 0 else 96)), 'the copy is not read in order'
                    src = tuple((o, k) for o, k, a in sa)
                    disp = tuple((o, k) + box_rc(m, X, Y, a) for p, k, o, a in acc if not SRC <= a < SRC + 352)
                    assert disp == t, 'D%d%d: the display accesses move with a contended bank' % (sh != 0, y7)
                    D.setdefault('S%d%d' % (sh != 0, y7), set()).add(src)
    # $B9E7, the bubble blitter: an EMPTY bubble (kind 0) at (X, Y) in pool slot 0, offsets less PRO + SEL.EMPTY (the
    # sprite choice's arm: the engine adds its own)
    B = {}
    for x7 in range(8):
        for y7 in range(8):
            for Y0 in (0x40, 0x68, 0x90):
                for X0 in (0x40, 0x88):
                    X, Y = X0 + x7, Y0 + y7
                    acc = a447(h, base, 0x80, 0, 0, X, Y, entry=0xB9E7, slot=0xFED8)
                    t = tuple((o - B9E7_HEAD, k) + box_rc(m, X, Y, a) for p, k, o, a in acc)
                    B.setdefault('B%d' % y7, set()).add(t)
    out = {}
    for M in (E, D, B):
        for key, ts in M.items():
            assert len(ts) == 1, '%s: %d templates' % (key, len(ts))
            out[key] = [list(x) for x in next(iter(ts))]
    return dict(sorted(out.items()))


def build():
    isrs = measure()
    rows = []
    for I in isrs:
        assert replay(I) == I['D'], 'ISR %d: the replay is not the machine\'s' % I['l']
        per = {}
        for c in CLASSES:
            prog = [(o, k) for cc, o, k in I['acc'] if cc == c]
            if prog: per[c] = [len(prog), digest(prog)]
        rows.append([I['l'], I['ph'], I['T'], I['D'], len(I['acc']), digest([(o, k) for c, o, k in I['acc']]), per])
    return {'window': [ISR_FROM, LAST], 'script': [[n, k] for n, k in pa.SCRIPT], 'isrs': rows,
            'n_acc': sum(r[4] for r in rows), 'D': sum(r[3] for r in rows), 'tmpl': templates(),
            'even': even_scenes()}


if __name__ == '__main__':
    out = build()
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        print('MATCH' if json.loads(json.dumps(out)) == old else 'DIFFER')
    else:
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote %s: %d ISRs, %d accesses, D %d T, %d templates' % (FIXTURE, len(out['isrs']), out['n_acc'], out['D'],
                                                                       len(out['tmpl'])))
