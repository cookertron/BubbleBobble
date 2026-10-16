# -*- coding: utf-8 -*-
"""FRONT-END GROUP 3, SUB-INCREMENT H-b: THE KEY READ $F7B3, THE MENU $F664, THE DISPATCH $F680,
THE THREE PRESETS AND THE KEY-TABLE BUILDER $F6DB -- and the frame layer that runs them.

    $F664  CALL $F7B3                    the key read, then the menu test $F667..$F672
    $F7B3  LD HL,LAST-K / LD (HL),0      LAST-K zeroed ON ENTRY ONLY -- the spin loops to $F7B8
    $F7B8  RST $38 / LD A,(HL) / AND A / JR z,$F7B8      the ROM's interrupt routine CALLED
    $F7BD..$F7D1                         the filter (game code): SPACE -> '_', ENTER -> ']',
                                         >= ':' less $20, accept iff '0' <= A <= 'Z'
    $F7D3..$F7E7                         the key click: forty CALLs of the ROM BEEPER, OUT 0
    $F7E9..$F7F8                         the echo: DEC ($F97F), ($F980) := A, CALL $F850
    $F7F9..$F7FF                         the release wait, then POP AF / RET
    $F674..$F690                         the dispatch: printing ON, the block, $F982, four arms
    $F692 KEMPSTON  $F6B8 SINCLAIR  $F6D0 CURSOR      $F723 KEYBOARD (H-c's, not driven here)
    $F6DB..$F708                         the builder: four codes through $F988 to the cursor

THE ROM'S KEYBOARD ROUTINE IS NOT TRANSCRIBED.  Its effect is MEASURED here as input/output over
key histories -- which combinations emit, when, and which emission a held key repeats -- and the
RAM it keeps (KSTATE, LAST-K) is observed, never its code or its tables.  NO ROM BYTE IS STORED:
the decode of a combination is kept only as the FILTER's verdict (the game's code) -- 'acc' with
the code the filter passes, or 'rej' -- and, for the accepted rows alone, the raw code the filter
was handed.  A set's key is kept by NAME (the keyprobe / platform naming), its counters as counts.

PHASES
  tape      the bytes H-b's methods read that the tape holds ($F988's 96, the presets, the
            staging buffer and its cursor, the SINCLAIR one-shot $F6B9) -- boot equals the tape
  filter    $F7BD entered with A = 0..255: the filter's verdict for every value
  decode    40 keys x {none, CAPS, SYM, CAPS+SYM} from KSTATE free, on P1's world AND on P2's
  pairs     all 780 pairs of the 40 keys, the 38 CAPS+SYM+key triples and a sample of wider
            chords: FREEZE (nothing changes), NOKEY (the sets age) or KEY (which key)
  history   scan-by-scan key histories: the repeat, the latch, the release count, the freeze,
            the two sets, and a 3,000-scan random walk
  menu      the menu naturally (interrupts on): 48 single keys and chords at P1's menu, the
            blocked options on P2's, the latch at the menu, the key held through P2's paint
  dispatch  every option's writes from $F674 to its RET (and to $F723 for KEYBOARD)
  builder   $F6DB at its own entry over its whole reachable domain
  click     the 241 OUTs, uncontended and at eight phases; interrupts landing at 64 phases
  timing    the measured T of every path the frame layer charges
  frames    key scripts from boot.pkl's own $F5BC, a sample at every frame boundary

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/ctrlmenu.py [capture|verify|<phase>]  -> build/ctrlmenu_fixture.json
"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, PC, T, SP, IFF, A as RA, F as RF, H as RH, L as RL, D as RD, E as RE
from harness import B as RB, C as RC
import portconfig as pc
import harness

#  every OUT with the PC of the instruction that made it (the harness's own record keeps T,
#  port and byte only): installed before any Harness is built, as the simulator binds its tracer
OUTS = []
_write_port = harness.Ports.write_port


def _out_hook(self, regs, port, value):
    _write_port(self, regs, port, value)
    OUTS.append((regs[T], regs[PC], port & 0xFF, value))


harness.Ports.write_port = _out_hook


def click_out(pc_):
    """an OUT ($FE) of the key click: the ROM BEEPER's, or $F7E7's -- not $F709's ($F716)"""
    return pc_ < 0x4000 or pc_ == 0xF7E7
from keyprobe import press, KEYS, KEYMAP

FIXTURE = 'build/ctrlmenu_fixture.json'
GUARD = set(range(0xD000, 0xD300))
FRAME_T = 69888
LASTK = 0x5C08
KSTATE = 0x5C00
NAMES = [k for k, s, b in KEYS]                       # the 40, half-row order
SHIFTS = [('none', []), ('CAPS', ['CAPS']), ('SYM', ['SYM']), ('CAPS+SYM', ['CAPS', 'SYM'])]
NONSHIFT = [k for k in NAMES if k not in ('CAPS', 'SYM')]


class Fail(Exception):
    pass


# ------------------------------------------------------------------ the machine
_P2 = {}


def world(state='title', contended=True):
    """a capture holding the front end -- boot or title (P1's menu read) -- or 'p2': player 2's
       menu world, driven from title (P1 takes '4') to P2's $F664 once and reloaded"""
    h = Harness(contended=contended)
    if state == 'p2':
        if 'state' not in _P2:
            _P2['state'] = p2_world()
        h.load_state(_P2['state'])
    elif state == 'p2b':
        if 'blocked' not in _P2:
            _P2['blocked'] = p2_world('3')
        h.load_state(_P2['blocked'])
    else:
        h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[0xF7B3] != 0x21 or m[0xF7B8] != 0xFF or m[0xF6DB] != 0xD9 or m[0xF664] != 0xCD:
        raise Fail('%s: the front end at $F664/$F6DB/$F7B3 is not the tape copy' % state)
    return h, m, h.sim.registers


def guard(h):
    if h.sim.registers[PC] in GUARD:
        raise Fail('PC entered the guard at $%04X' % h.sim.registers[PC])


def keys(h, names):
    h.ports.release_all()
    for k in names:
        press(h.ports, k)


def free_sets(m):
    """both KSTATE sets free, as boot.pkl and title.pkl hold them (+0 and +4 = $FF)"""
    m[KSTATE] = 0xFF
    m[KSTATE + 4] = 0xFF


def scan(h, names):
    """ONE explicit KEYBOARD call: PC := $F7B8 (the RST $38), interrupts OFF, until $F7B9.
       LAST-K is zeroed first, so a non-zero LAST-K after is THIS scan's emission."""
    r, m = h.sim.registers, h.memobj.m
    keys(h, names)
    m[LASTK] = 0
    r[PC] = 0xF7B8
    t0, n = r[T], 0
    while True:
        h.step(1, interrupts=False)
        n += 1
        if r[PC] in GUARD:
            raise Fail('guard')
        if r[PC] == 0xF7B9:
            return m[LASTK], r[T] - t0
        if n > 200000:
            raise Fail('a scan never returned')


FILTER = {}


def filt(v):
    """the game's filter's verdict for a raw LAST-K, measured in phase `filter`"""
    if not FILTER:
        phase_filter()
    return FILTER[v]


def verdict(v):
    """a raw code as the fixture keeps it: 'acc' + the code the filter passes, or 'rej'"""
    f = filt(v)
    return ['acc', f] if f >= 0 else ['rej', None]


MAIN = {}


def identity_of(m, set_at):
    """the NAME of the key a KSTATE set holds -- its +0 byte looked up among the codes a fresh
       single press of each key stores there (phase `decode` builds MAIN); the byte itself is
       never kept"""
    b = m[set_at]
    if b == 0xFF:
        return None
    if not MAIN:
        build_main('title')
    if b not in MAIN:
        raise Fail('a set holds a key no single press stores')
    return MAIN[b]


def sets_of(m):
    """both KSTATE sets as the fixture keeps them: None when free, else [key NAME, the 5-scan
       count, the repeat count, the filter's verdict on the code the set will repeat]"""
    out = []
    for at in (KSTATE, KSTATE + 4):
        k = identity_of(m, at)
        out.append(None if k is None else [k, m[at + 1], m[at + 2]] + verdict(m[at + 3]))
    return out


# ------------------------------------------------------------------ tape
TAPE_RANGES = [('buffer', 0xF5D2, 0xF5E5), ('cursor', 0xF5E5, 0xF5E7), ('sinclair_once', 0xF6B9, 0xF6BA),
               ('keymap', 0xF988, 0xF9E8), ('presets', 0xF9E8, 0xF9F4), ('kempston', 0xF9F4, 0xF9FC)]


def phase_tape():
    img = open('build/image_tape.bin', 'rb').read()
    h, m, r = world('boot')
    out = {}
    same = True
    for name, lo, hi in TAPE_RANGES:
        out[name] = list(img[lo:hi])
        same = same and all(img[x] == m[x] for x in range(lo, hi))
    out['boot_equals_tape'] = same
    out['ranges'] = [[n, lo, hi] for n, lo, hi in TAPE_RANGES]
    #  the ROM keyboard's two repeat constants live in RAM (system variables REPDEL / REPPER)
    out['repdel'] = m[0x5C09]
    out['repper'] = m[0x5C0A]
    out['kstate_free_at_boot'] = m[KSTATE] == 0xFF and m[KSTATE + 4] == 0xFF
    hT, mT, rT = world('title')
    out['kstate_free_at_title'] = mT[KSTATE] == 0xFF and mT[KSTATE + 4] == 0xFF
    out['title_equals_tape'] = all(img[x] == mT[x] for name, lo, hi in TAPE_RANGES for x in range(lo, hi))
    print('tape: boot == tape %s, title == tape %s, REPDEL %d REPPER %d, KSTATE free at boot %s / title %s'
          % (same, out['title_equals_tape'], out['repdel'], out['repper'], out['kstate_free_at_boot'],
             out['kstate_free_at_title']))
    assert same and out['title_equals_tape'] and out['kstate_free_at_boot'] and out['kstate_free_at_title']
    return out


# ------------------------------------------------------------------ the filter
def phase_filter():
    rows = []
    for v in range(256):
        h, m, r = world('title')
        r[RA] = v
        r[PC] = 0xF7BD
        n = 0
        while r[PC] not in (0xF7D3, 0xF7B3):
            h.step(1, interrupts=False)
            n += 1
            if n > 50:
                raise Fail('the filter did not decide on $%02X' % v)
        out = r[RA] if r[PC] == 0xF7D3 else -1
        FILTER[v] = out
        rows.append(out)
    acc = [(v, o) for v, o in enumerate(rows) if o >= 0]
    print('filter: %d of 256 accepted, %d distinct codes out' % (len(acc), len(set(o for v, o in acc))))
    return {'out': rows}


# ------------------------------------------------------------------ the 160 rows
LATCH = ['A', 'M', 'Q', 'P']


def latch_key(combo):
    for k in LATCH:
        if k not in combo:
            return k
    raise Fail('no latch key')


def classify(state, combo):
    """FREEZE / NOKEY / KEY for one chord, by behaviour: a latch key L pressed (a set taken,
       its count 5), the chord scanned FOUR times, then L again -- L emits afresh only if the
       four scans AGED its set out (the chord was a valid scan with no key); a chord that
       emits on its first scan is a KEY, and its identity is the one of its keys that, held
       alone after it, continues its hold instead of emitting"""
    L = latch_key(combo)
    h, m, r = world(state)
    free_sets(m)
    if not scan(h, [L])[0]:
        raise Fail('the latch key %s did not emit' % L)
    first = scan(h, combo)[0]
    if first:
        #  identity: from a fresh world, the chord once and each candidate alone after it
        ident = None
        for c in [x for x in combo if x not in ('CAPS', 'SYM')] or [None]:
            h2, m2, r2 = world(state)
            free_sets(m2)
            if not scan(h2, combo)[0]:
                raise Fail('%s emitted once and not again' % combo)
            if c is None:                         # CAPS+SYM: only the chord itself continues it
                if not scan(h2, combo)[0]:
                    ident = 'SYM'
            elif not scan(h2, [c])[0]:
                if ident is not None:
                    raise Fail('two identities for %s' % combo)
                ident = c
        if ident is None:
            raise Fail('no identity for %s' % combo)
        return 'key', ident
    for _ in range(3):
        if scan(h, combo)[0]:
            raise Fail('%s emitted on a later scan from a latched world' % combo)
    return ('nokey' if scan(h, [L])[0] else 'freeze'), None


def decode_rows(state):
    rows = []
    for key in NAMES:
        for sname, sh in SHIFTS:
            combo = list(dict.fromkeys(sh + [key]))
            h, m, r = world(state)
            free_sets(m)
            v, t = scan(h, combo)
            if v:
                ver = verdict(v)
                rows.append([key, sname, ver[0], ver[1], v if ver[0] == 'acc' else None])
            else:
                rows.append([key, sname, classify(state, combo)[0], None, None])
    return rows


def build_main(state='title'):
    """the +0 byte each single key leaves in the set it takes -- kept in memory only, to NAME
       the key a set holds; CAPS+SYM's is named 'SYM'"""
    MAIN.clear()
    for key in NONSHIFT:
        h, m, r = world(state)
        free_sets(m)
        scan(h, [key])
        b = m[KSTATE + 4]
        if b in MAIN:
            raise Fail('two keys store one +0 byte')
        MAIN[b] = key
    h, m, r = world(state)
    free_sets(m)
    scan(h, ['CAPS', 'SYM'])
    MAIN[m[KSTATE + 4]] = 'SYM'
    if len(MAIN) != 39:
        raise Fail('the +0 bytes are not 39 distinct')


def p2_world(p1='4'):
    """player 2's menu world: from title.pkl, P1 takes `p1` ('4', CURSOR, by default), P2's
       screen painted to its $F664 -- saved as a state the rows can reload"""
    h, m, r = world('title')
    keys(h, [p1])
    run_to(h, (0xF7F9,), True)
    keys(h, [])
    run_to(h, (0xF5E7,), True)
    if r[RA] != 0x32:
        raise Fail('P2\'s $F5E7 not reached')
    run_to(h, (0xF664,), True)
    return h.save_state()


def run_to(h, targets, ints, limit=50_000_000):
    why, n = h.run_until(set(targets) | GUARD, limit=limit, interrupts=ints, stride=64)
    guard(h)
    if why != 'target':
        raise Fail('never reached %s (PC $%04X)' % (['$%04X' % x for x in targets], h.sim.registers[PC]))
    return n


def phase_decode():
    build_main('title')
    out = {st: decode_rows(st) for st in ('title', 'p2')}
    rows = out['title']
    cnt = {}
    for key, sname, c, code, raw in rows:
        cnt.setdefault(sname, {}).setdefault(c, 0)
        cnt[sname][c] += 1
    emit = sum(1 for r in rows if r[2] in ('acc', 'rej'))
    acc = sum(1 for r in rows if r[2] == 'acc')
    print('decode: 160 rows, %d emit, %d accepted; by shift %s; P2 world identical: %s'
          % (emit, acc, cnt, out['title'] == out['p2']))
    assert out['title'] == out['p2'] and len(rows) == 160
    return {'rows': rows, 'same_on_p2': out['title'] == out['p2'], 'counts': cnt}


# ------------------------------------------------------------------ chords
def phase_pairs():
    if not MAIN:
        build_main('title')
    rows = []
    for i in range(len(NAMES)):
        for j in range(i + 1, len(NAMES)):
            combo = [NAMES[i], NAMES[j]]
            h, m, r = world('title')
            free_sets(m)
            v, t = scan(h, combo)
            if v:
                c, ident = classify('title', combo)
                rows.append([combo, c, ident] + verdict(v)[:1])
            else:
                c, ident = classify('title', combo)
                rows.append([combo, c, ident, None])
    trip = []
    for k in NONSHIFT:
        trip.append(['CAPS', 'SYM', k])
    rng = random.Random(0x5B)
    seen = set()
    while len(trip) < 38 + 200:
        n = rng.choice((3, 3, 3, 4, 5))
        c = tuple(sorted(rng.sample(NAMES, n), key=NAMES.index))
        if c in seen:
            continue
        seen.add(c)
        trip.append(list(c))
    wide = []
    for combo in trip:
        c, ident = classify('title', combo)
        wide.append([combo, c, ident])
    cnt = {}
    for r_ in rows:
        cnt[r_[1]] = cnt.get(r_[1], 0) + 1
    wcnt = {}
    for r_ in wide:
        wcnt[r_[1]] = wcnt.get(r_[1], 0) + 1
    print('pairs: %d pairs %s; %d wider chords %s' % (len(rows), cnt, len(wide), wcnt))
    return {'pairs': rows, 'wide': wide}


# ------------------------------------------------------------------ histories
def dash(x):
    return '-' if x is None else str(x)


def hist_row(v, sets):
    """one scan as the fixture keeps it: ONE string -- the emission, the filter's verdict on it, and
       both sets (key, count, delay, the verdict on the code it would repeat), '-' for none -- so no
       run of small counters sits in the file as numbers"""
    head = ' '.join(dash(x) for x in [1 if v else 0] + (verdict(v) if v else [None, None]))
    return head + '|' + '|'.join('-' if s is None else ' '.join(dash(x) for x in s) for s in sets)


def run_history(seq, state='title'):
    if not MAIN:
        build_main('title')
    h, m, r = world(state)
    free_sets(m)
    rows = []
    for combo in seq:
        v, t = scan(h, combo)
        rows.append(hist_row(v, sets_of(m)))
    return rows


def histories():
    H = {}
    H['hold'] = [['A']] * 80
    H['caps_then_bare'] = [['CAPS', 'A']] + [['A']] * 100
    H['sym_then_bare'] = [['SYM', 'A']] + [['A']] * 100
    H['caps_digit'] = [['CAPS', '2']] + [['2']] * 60
    H['bare_then_caps'] = [['Q']] + [['CAPS', 'Q']] * 45
    for k in range(0, 7):
        H['release_%d' % k] = [['A']] + [[]] * k + [['A']] * 45
    for k in (1, 4, 6):
        H['freeze_%d' % k] = [['A']] + [['A', 'B']] * k + [['A']] * 45
    H['three_keys'] = [['A'], ['B']] + [['C']] * 10
    H['three_keys_slow'] = [['A'], ['A'], ['B']] + [['C']] * 10
    for g in (['CAPS'], ['SYM'], ['CAPS', 'SYM']):
        for k in (3, 4):
            H['gap_%s_%d' % ('+'.join(g), k)] = [['A']] + [g] * k + [['A']] * 45
    #  THE RANDOM WALK: runs of 1..12 scans over chords drawn from a pool that holds every
    #  class -- bare keys, shifted keys, the shifts alone, CAPS+SYM, pairs, a triple, nothing
    pool = [[], ['A'], ['Q'], ['2'], ['M'], ['ENTER'], ['SPACE'], ['CAPS'], ['SYM'], ['CAPS', 'SYM'],
            ['CAPS', 'A'], ['SYM', 'A'], ['CAPS', '2'], ['SYM', 'X'], ['CAPS', 'Q'], ['CAPS', 'Z'],
            ['A', 'Q'], ['2', 'M'], ['CAPS', 'SYM', 'A'], ['SYM', 'H'], ['SYM', '0']]
    rng = random.Random(0xB3)
    walk = []
    while len(walk) < 3000:
        c = rng.choice(pool)
        walk += [c] * rng.randint(1, 12)
    H['walk'] = walk[:3000]
    return H


def phase_history():
    H = histories()
    out = {}
    for name, seq in H.items():
        out[name] = {'seq': ['+'.join(c) for c in seq], 'rows': run_history(seq)}
        em = [i for i, row in enumerate(out[name]['rows']) if row[0] == '1']
        if name != 'walk':
            print('history %-18s emissions at %s' % (name, em[:8]))
    w = out['walk']['rows']
    print('history walk: %d scans, %d emissions, %d accepted' %
          (len(w), sum(1 for r_ in w if r_[0] == '1'), sum(1 for r_ in w if r_.startswith('1 acc'))))
    return out


# ------------------------------------------------------------------ the machine, naturally
#  a label per PC the drive passes -- the frame layer's own state names.  $F674 (the dispatch)
#  opens player 2's pass or reaches the spine, and folds into whichever comes next.
LABEL_AT = {0xF5BC: 'open', 0xF5E7: 'open', 0xF5F0: 'wait', 0xF5F8: 'paint', 0xF664: 'menu',
            0xF7D3: 'click', 0xF7F9: 'release', 0xF801: 'menu', 0xF674: 'dispatch',
            0xF723: 'redefine', 0xF5C6: 'spine'}
STOPS = (0xF723, 0xF5C6)
VARS = [('F8C4', 0xF8C4), ('F671', 0xF671), ('F850', 0xF850), ('F982', 0xF982), ('F6B9', 0xF6B9),
        ('F97F', 0xF97F), ('F980', 0xF980)]


def vars_of(m):
    return [m[a] for n, a in VARS] + [m[0xF5E5] | (m[0xF5E6] << 8), list(m[0xF5D2:0xF5E2])]


class Nat:
    """the machine run NATURALLY: interrupts ON -- the ROM's IM 1 routine, as the menu has them
       -- the keys of a per-frame SCRIPT applied at each frame boundary (before the interrupt
       routine that begins the frame reads them), a sample taken at each boundary, every OUT
       ($FE) counted, every explicit scan ($F7B8) and every accepted interrupt counted"""

    def __init__(self, h, script, label='open', pass_=1):
        self.h, self.m, self.r = h, h.memobj.m, h.sim.registers
        self.script = script                     # list of key lists, one per frame
        self.label, self.pass_ = label, pass_
        self.frame = 0
        self.nb = (self.r[T] // FRAME_T + 1) * FRAME_T
        self.outs = []
        self.n_rst = self.n_isr = self.n_nested = self.n_deferred = 0
        self.rows = []
        self.in_scan = False                     # between $F7B8's RST $38 and its return
        self.pending = None
        self.out0 = len(OUTS)
        h.ports.record_writes = True
        h.ports.writes = []
        keys(h, self.keys_for(0))

    def keys_for(self, f):
        return self.script[f] if f < len(self.script) else []

    def sample(self):
        m = self.m
        lab = self.label
        if lab == 'dispatch':
            lab = 'open' if self.pass_ == 1 else 'spine'
        return [self.frame, lab, self.pass_, self.n_click(), self.n_rst, self.n_isr] + vars_of(m) + [sets_of(m)]

    def n_fe(self):
        return sum(1 for t, p, v in self.h.ports.writes if (p & 0xFF) == 0xFE)

    def n_click(self):
        return sum(1 for t, p, port, v in OUTS[self.out0:] if port == 0xFE and click_out(p))

    def run(self, max_frames, stops=STOPS, until=None):
        h, r = self.h, self.r
        sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
        fd, ia = h.frame_duration, h.int_active
        while True:
            pc = r[PC]
            if r[T] >= self.nb:
                self.frame += 1
                #  THE KEYS CHANGE BETWEEN SCANS: an explicit scan in flight at the boundary
                #  (almost always -- the frame interrupt lands inside it, IFF 1) finishes on the
                #  keys it began with, and so does the interrupt nested in it; a change in the
                #  middle of the ROM's line scan would be a TORN read the port's atomic scans
                #  cannot have (a chord A+B read as B alone)
                if self.in_scan:
                    self.pending = self.keys_for(self.frame)
                    self.n_deferred += 1
                else:
                    keys(h, self.keys_for(self.frame))
                self.rows.append(self.sample())
                self.nb += FRAME_T
                if self.frame >= max_frames:
                    return 'frames'
            if pc == 0xF7B9 and self.in_scan:
                self.in_scan = False
                if self.pending is not None:
                    keys(h, self.pending)
                    self.pending = None
            if pc in GUARD:
                raise Fail('PC entered the guard at $%04X' % pc)
            lab = LABEL_AT.get(pc)
            if lab:
                if pc == 0xF5E7:
                    self.pass_ = 1 if r[RA] == 0x31 else 2
                self.label = lab
                if pc in stops:
                    return lab
                if until is not None and pc in until:
                    return pc
            if pc == 0xF7B8:
                self.n_rst += 1
                self.in_scan = True
            ops[mem[pc]]()
            if r[IFF] and r[T] % fd < ia:
                sim.accept_interrupt(r, mem, pc)
                self.n_isr += 1
                if self.in_scan:
                    self.n_nested += 1


# ------------------------------------------------------------------ the menu
def menu_try(state, combo, hold=2, after=10):
    """one chord at the menu, naturally: held `hold` frames, then nothing: did it click (the
       key read ACCEPTED it), did the menu take it (PC reached $F674), and the echo's bytes"""
    h, m, r = world(state)
    f97f, f980 = m[0xF97F], m[0xF980]
    nat = Nat(h, [combo] * (hold + 1), label='menu', pass_=1 if state == 'title' else 2)
    why = nat.run(hold + after, stops=(0xF674,) + STOPS)
    return {'combo': '+'.join(combo), 'outs': nat.n_fe(), 'menu': why == 'dispatch',
            'F97F': (m[0xF97F] - f97f) & 0xFF, 'F980': m[0xF980], 'frames': nat.frame,
            'label': nat.label}


def phase_menu():
    out = {}
    #  (1) at P1's menu: every single key, and the chords that reach it
    rows = []
    for k in NAMES:
        rows.append(menu_try('title', [k]))
    for c in (['CAPS', 'Q'], ['CAPS', 'R'], ['CAPS', 'S'], ['CAPS', 'T'], ['CAPS', 'P'], ['CAPS', 'Y'],
              ['CAPS', 'Z'], ['SYM', 'X'], ['SYM', '0'], ['SYM', 'H'], ['CAPS', '1'], ['SYM', '2'],
              ['CAPS', 'SYM'], ['CAPS', 'SYM', '3'], ['1', '2'], ['3', '4']):
        rows.append(menu_try('title', c))
    out['p1'] = rows
    #  (2) player 2's menu after each of P1's presets: the other player's option is BLOCKED --
    #  except SINCLAIR, which $F679 never writes into $F671
    blk = []
    for p1 in ('2', '3', '4'):
        h, m, r = world('title')
        nat = Nat(h, [[p1]] * 3, label='menu')
        nat.run(200, stops=(0xF664,) + STOPS, until=None) if False else None
        keys(h, [p1])
        run_to(h, (0xF7F9,), True)
        keys(h, [])
        run_to(h, (0xF5E7,), True)
        run_to(h, (0xF664,), True)
        st = h.save_state()
        for k in ('1', '2', '3', '4'):
            if k == '1':
                continue                  # KEYBOARD leads into the redefine screen (H-c)
            h2 = Harness(contended=True)
            h2.load_state(st)
            m2 = h2.memobj.m
            nat2 = Nat(h2, [[k]] * 3, label='menu', pass_=2)
            why = nat2.run(12, stops=(0xF674,) + STOPS)
            blk.append({'p1': p1, 'key': k, 'F671': m2[0xF671], 'outs': nat2.n_fe(),
                        'menu': why == 'dispatch'})
    out['p2_block'] = blk
    #  (3) THE LATCH AT THE MENU (the recon's fact 1, re-measured): a shift and a digit, then
    #  the shift let go with the digit held -- no click, no accept, for 20 frames; let go ONE
    #  frame and pressed again, accepted at once
    lat = []
    for first, bare in ((['CAPS', '2'], ['2']), (['SYM', '2'], ['2']), (['CAPS', 'A'], ['A']),
                        (['SYM', 'A'], ['A']), (['CAPS', '4'], ['4'])):
        h, m, r = world('title')
        script = [first] * 2 + [bare] * 20 + [[]] + [bare] * 3 + [[]] * 10
        nat = Nat(h, script, label='menu')
        why = nat.run(len(script), stops=(0xF674,) + STOPS)
        first_click = None
        for row in nat.rows:
            if row[3] and first_click is None:
                first_click = row[0]
        lat.append({'first': '+'.join(first), 'bare': '+'.join(bare), 'menu': why == 'dispatch',
                    'frame_of_first_out': first_click, 'outs': nat.n_fe(), 'frames': nat.frame})
    out['latch'] = lat
    #  (4) a key pressed during P2's PAINT and held into the menu: the interrupts during the
    #  paint scan it, so P2's first key read finds it already HELD and waits out the repeat
    #  delay -- where P1's (interrupts off through its paint) takes it at the first scan
    held = []
    for p1, k in (('2', '4'), ('4', '3'), ('3', '2')):
        h, m, r = world('title')
        keys(h, [p1])
        run_to(h, (0xF7F9,), True)
        keys(h, [])
        run_to(h, (0xF5F8,), True)            # P2's paint begins: every key is up
        t_paint = r[T]
        keys(h, [k])
        isrs_paint = 0
        sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
        fd, ia = h.frame_duration, h.int_active
        while r[PC] != 0xF664:
            pc = r[PC]
            if pc in GUARD:
                raise Fail('guard')
            ops[mem[pc]]()
            if r[IFF] and r[T] % fd < ia:
                sim.accept_interrupt(r, mem, pc)
                isrs_paint += 1
        t_menu = r[T]
        n0 = sum(1 for t, p, v in h.ports.writes)
        #  the first scan of P2's key read, and the first OUT of the click
        rst, t_first_rst, t_accept, isr = 0, None, None, 0
        sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
        fd, ia = h.frame_duration, h.int_active
        while True:
            pc = r[PC]
            if pc in GUARD:
                raise Fail('guard')
            if pc == 0xF7B8:
                rst += 1
                if t_first_rst is None:
                    t_first_rst = r[T]
            if pc == 0xF7D3:
                t_accept = r[T]
                break
            ops[mem[pc]]()
            if r[IFF] and r[T] % fd < ia:
                sim.accept_interrupt(r, mem, pc)
                isr += 1
        held.append({'p1': p1, 'key': k, 'scans_to_accept': rst, 'isrs_menu': isr, 'isrs_paint': isrs_paint,
                     'T_menu_to_accept': t_accept - t_menu, 'T_paint': t_menu - t_paint})
    #  ...and P1's, for the contrast: the key down through the paint (interrupts off) is taken
    #  on the first scan
    h, m, r = world('boot')
    run_to(h, (0xF5F8,), False)
    keys(h, ['4'])
    run_to(h, (0xF664,), True)
    n = 0
    while r[PC] != 0xF7D3:
        if r[PC] == 0xF7B8:
            n += 1
        h.step(1, interrupts=True)
        guard(h)
    out['held'] = held
    out['held_p1_scans'] = n
    print('menu: P1 %d rows -- clicks %d, menu accepts %s' % (
        len(rows), sum(1 for x in rows if x['outs']), [x['combo'] for x in rows if x['menu']]))
    print('      P2 blocks %s' % [(b['p1'], b['key'], b['outs'], b['menu']) for b in blk])
    print('      latch %s' % [(x['first'], x['menu'], x['frame_of_first_out']) for x in lat])
    print('      held through P2\'s paint %s; P1: %d scan' % (
        [(x['p1'], x['key'], x['scans_to_accept'], x['isrs_menu']) for x in held], n))
    return out


# ------------------------------------------------------------------ the dispatch
ENTRY_AT = [0xF671, 0xF6B9, 0xF850, 0xF5E5, 0xF5E6, 0xF982] + list(range(0xF983, 0xF988)) +     list(range(0xF5D2, 0xF5E5))


def entry_of(m):
    """the bytes the dispatch and its arms read or write, at $F674"""
    return [[a, m[a]] for a in ENTRY_AT]


def dispatch_run(state, key):
    """from the menu with `key` pressed: the write census from $F674 to the RET into the spine
       ($F5C1 for P1, $F5C6 for P2) -- or to $F723 for KEYBOARD -- and its T"""
    h, m, r = world(state)
    keys(h, [key])
    run_to(h, (0xF7F9,), True)
    keys(h, [])
    run_to(h, (0xF674,), True)
    entry, a_in = entry_of(m), r[RA]
    t0 = r[T]
    h.memobj.watch(0x4000, 0x10000)
    why, n = h.run_until({0xF5C1, 0xF5C6, 0xF723} | GUARD, limit=1_000_000, interrupts=False, stride=1)
    guard(h)
    log = [(p, a, v) for p, a, v in h.memobj.log if not (0x6100 <= a < 0x6200)]
    h.memobj.unwatch()
    return {'key': key, 'a': a_in, 'entry': entry, 'end': r[PC], 'T': r[T] - t0,
            'writes': [[a, v] for p, a, v in log], 'cursor': m[0xF5E5] | (m[0xF5E6] << 8)}


def phase_dispatch():
    rows = []
    for k in ('1', '2', '3', '4'):
        rows.append(dict(dispatch_run('title', k), who='P1'))
    #  player 2 after each preset; SINCLAIR twice takes the SECOND preset
    for p1 in ('2', '3', '4'):
        h, m, r = world('title')
        keys(h, [p1])
        run_to(h, (0xF7F9,), True)
        keys(h, [])
        run_to(h, (0xF664,), True)            # P2's menu
        _P2[p1] = h.save_state()
        for k in ('2', '3', '4'):
            if k == p1 and k != '2':
                continue                      # blocked
            h2 = Harness(contended=True)
            h2.load_state(_P2[p1])
            m2, r2 = h2.memobj.m, h2.sim.registers
            keys(h2, [k])
            run_to(h2, (0xF7F9,), True)
            keys(h2, [])
            run_to(h2, (0xF674,), True)
            entry, a_in = entry_of(m2), r2[RA]
            t0 = r2[T]
            h2.memobj.watch(0x4000, 0x10000)
            why, n = h2.run_until({0xF5C1, 0xF5C6, 0xF723} | GUARD, limit=1_000_000, interrupts=False, stride=1)
            guard(h2)
            log = [(p, a, v) for p, a, v in h2.memobj.log if not (0x6100 <= a < 0x6200)]
            h2.memobj.unwatch()
            rows.append({'who': 'P2', 'p1': p1, 'key': k, 'a': a_in, 'entry': entry, 'end': r2[PC], 'T': r2[T] - t0,
                         'writes': [[a, v] for p, a, v in log],
                         'cursor': m2[0xF5E5] | (m2[0xF5E6] << 8)})
    for x in rows:
        print('dispatch %s%s %s -> $%04X, %d writes, %d T, cursor $%04X' % (
            x['who'], (' after ' + x['p1']) if 'p1' in x else '', x['key'], x['end'], len(x['writes']),
            x['T'], x['cursor']))
    return {'rows': rows}


# ------------------------------------------------------------------ the menu's test
def phase_test():
    """$F667..$F672 entered with A = 0..255 and $F671 (the other player's option) = $2A (the
       tape's: none), '1', '3', '4': the exit taken -- $F669 (below '1'), $F66E ('5' or above),
       $F672 (the blocked option) back to $F664, or on to $F674"""
    rows = {}
    for blk in (0x2A, 0x31, 0x33, 0x34):
        out = []
        for a in range(256):
            h, m, r = world('title')
            m[0xF671] = blk
            r[RA] = a
            r[PC] = 0xF667
            last = None
            n = 0
            while r[PC] not in (0xF664, 0xF674):
                last = r[PC]
                h.step(1, interrupts=False)
                n += 1
                if n > 20:
                    raise Fail('the test did not decide')
            out.append({0xF674: 'taken', 0xF669: 'low', 0xF66E: 'high', 0xF672: 'blocked'}[
                0xF674 if r[PC] == 0xF674 else last])
        rows['%02X' % blk] = out
    print('test: %s' % {k: {x: v.count(x) for x in ('low', 'high', 'blocked', 'taken')} for k, v in rows.items()})
    return rows


# ------------------------------------------------------------------ the builder
def phase_builder():
    """$F6DB at its own entry: slot 0 over all 48 codes $30..$5F (slots 1-3 fixed), each slot
       over the four answers, and the cursor at $F5D2 and $F5DA -- its eight writes and the
       cursor after, interrupts off.  Its domain is the filter's output set plus the presets'
       digits: $F6EA's SUB $30 and $F6F1's EIGHT-bit SLA take no range check"""
    rows = []

    def one(codes, cursor):
        h, m, r = world('title')
        for i, c in enumerate(codes):
            m[0xF983 + i] = c
        m[0xF5E5], m[0xF5E6] = cursor & 0xFF, cursor >> 8
        for a in range(0xF5D2, 0xF5E5):
            m[a] = 0xA5
        sp = r[SP]
        for s in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp], m[sp + 1] = s & 0xFF, s >> 8
        r[SP] = sp
        r[PC] = 0xF6DB
        t0 = r[T]
        h.memobj.watch(0x4000, 0x10000)
        why, n = h.run_until(set(h.SENTINELS) | GUARD, limit=100000, interrupts=False, stride=1)
        guard(h)
        log = [[a, v] for p, a, v in h.memobj.log if not (0x6100 <= a < 0x6200)]
        h.memobj.unwatch()
        return {'codes': codes, 'cursor_in': cursor, 'writes': log,
                'cursor': m[0xF5E5] | (m[0xF5E6] << 8), 'T': r[T] - t0}
    for c in range(0x30, 0x60):
        rows.append(one([c, 0x31, 0x5A, 0x5F], 0xF5D2))
    rows.append(one([0x35, 0x38, 0x30, 0x37], 0xF5D2))
    rows.append(one([0x36, 0x37, 0x39, 0x30], 0xF5DA))
    rows.append(one([0x5D, 0x5F, 0x3A, 0x40], 0xF5DA))
    #  answers the filter never passes, $B0..$DF: (code - $30) x 2 overflows eight bits and the
    #  wrapped offset lands back inside $F988's map -- $F6F1's SLA is eight-bit, MEASURED, not argued
    rows.append(one([0xB0, 0xB5, 0xC9, 0xDF], 0xF5D2))
    print('builder: %d drives, T %d..%d' % (len(rows), min(x['T'] for x in rows), max(x['T'] for x in rows)))
    return {'rows': rows}


# ------------------------------------------------------------------ the click
def click_outs(contended, phase=None, ints=False, code=0x34, bordcr=None):
    """$F7D3 entered with A = an accepted code, run to $F7F9: every OUT ($FE) [T from $F7D3,
       the byte], the BEEPER calls' entry and return T, the interrupts accepted"""
    h, m, r = world('title', contended=contended)
    if bordcr is not None:
        m[0x5C48] = bordcr
    if phase is not None:
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + phase
    r[RA] = code
    r[PC] = 0xF7D3
    h.ports.record_writes = True
    h.ports.writes = []
    t0 = r[T]
    calls, isr = [], []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    while r[PC] != 0xF7F9:
        pc = r[PC]
        if pc in GUARD:
            raise Fail('guard')
        if pc == 0xF7DB:
            calls.append([r[T] - t0, None])
        if pc == 0xF7DE:
            calls[-1][1] = r[T] - t0
        ops[mem[pc]]()
        if ints and r[IFF] and r[T] % fd < ia:
            ta = r[T]
            sim.accept_interrupt(r, mem, pc)
            isr.append([ta - t0, pc])
    outs = [[t - t0, v] for t, p, v in h.ports.writes if (p & 0xFF) == 0xFE]
    return {'outs': outs, 'calls': calls, 'isr': isr, 'T': r[T] - t0,
            'F97F': m[0xF97F], 'F980': m[0xF980]}


def phase_click():
    unc = click_outs(False)
    con = click_outs(True)
    sweep = []
    for k in range(8):
        c = click_outs(True, phase=k * (FRAME_T // 8))
        sweep.append({'phase': k * (FRAME_T // 8), 'T': c['T'],
                      'dev': max(abs(a[0] - b[0]) for a, b in zip(c['outs'], unc['outs'])),
                      'same_values': [v for t, v in c['outs']] == [v for t, v in unc['outs']]})
    #  THE CONTENTION ON THE TRAIN: at 64 phases (interrupts off) the i-th OUT is late on the
    #  uncontended one by a mean that grows in a straight line with i -- the slope, through the
    #  origin, is the per-OUT term the port adds; kept with its worst residuals
    excess = []
    for k in range(64):
        c = click_outs(True, phase=k * (FRAME_T // 64) + 500)
        excess.append([c['outs'][i][0] - unc['outs'][i][0] for i in range(len(unc['outs']))])
    n_out = len(unc['outs'])
    mean_ex = [sum(e[i] for e in excess) / len(excess) for i in range(n_out)]
    slope = sum(mean_ex[i] * (i + 1) for i in range(n_out)) / sum((i + 1) ** 2 for i in range(n_out))
    cont = {'slope': round(slope, 4),
            'mean_resid_max': round(max(abs(mean_ex[i] - (i + 1) * round(slope, 4)) for i in range(n_out)), 1),
            'phase_resid_max': round(max(abs(e[i] - (i + 1) * round(slope, 4)) for e in excess for i in range(n_out)), 1),
            'uncontended_max': max(abs(x) for e in excess for x in e),
            'end_mean': round(sum(e[-1] for e in excess) / len(excess), 1)}
    land = []
    for k in range(64):
        c = click_outs(True, phase=k * (FRAME_T // 64), ints=True)
        land.append({'phase': k * (FRAME_T // 64), 'n_isr': len(c['isr']), 'T': c['T'],
                     'isr_after_call': [sum(1 for cl in c['calls'] if cl[0] < t) for t, p in c['isr']],
                     'isr_pcs': [p for t, p in c['isr']]})
    t_no = [x['T'] for x in land if x['n_isr'] == 0]
    #  the OUT byte's border bits come from BORDCR (the lower screen's attribute, which $F709
    #  ANDs with $F8): poisoned, the same train carries them -- so the port CHECKS BORDCR's
    #  border bits and does not interpret them
    bord = {}
    for b in (0x00, 0x18, 0x38, 0x07, 0xC0):
        c = click_outs(False, bordcr=b)
        bord['%02X' % b] = sorted(set(v for t, v in c['outs']))
    print('click: %d OUTs, values %s, %d calls, T %d uncontended / %d contended; eight phases T %d..%d, '
          'OUT drift <= %d T; ISR landings on %d of 64 phases (%s), T with none %d..%d'
          % (len(unc['outs']), sorted(set(v for t, v in unc['outs'])), len(unc['calls']), unc['T'], con['T'],
             min(s['T'] for s in sweep), max(s['T'] for s in sweep), max(s['dev'] for s in sweep),
             sum(1 for x in land if x['n_isr']), [(x['phase'], x['isr_after_call']) for x in land if x['n_isr']],
             min(t_no), max(t_no)))
    print('       BORDCR -> OUT values %s' % bord)
    print('       contention: %s' % cont)
    return {'uncontended': unc, 'contended': con, 'sweep': sweep, 'land': land, 'bordcr': bord,
            'contention': cont}


# ------------------------------------------------------------------ the timing
def combo_class(combo, before):
    """the scan's path as the port's model names it: FREEZE, NONE (no key: nothing, a shift
       alone), and for a key: HELD / REPEAT (it holds a set), NEW (a set was free), FULL"""
    ns = [k for k in combo if k not in ('CAPS', 'SYM')]
    sh = [k for k in combo if k in ('CAPS', 'SYM')]
    if len(ns) > 1 or (len(ns) == 1 and len(sh) == 2):
        return 'freeze', None
    if not ns:
        if len(sh) == 2:
            return 'key', 'SYM'
        return 'none', None
    return 'key', ns[0]


class Timer:
    """a natural run that times every spin pass, every interrupt and every step of the key
       read, each classed by the scan's path"""

    def __init__(self, h):
        self.h, self.m, self.r = h, h.memobj.m, h.sim.registers
        self.ev = []
        self.isr = []

    def run(self, script, frames, stops=(), keep_going=None):
        h, r, m = self.h, self.r, self.m
        sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
        fd, ia = h.frame_duration, h.int_active
        nb = (r[T] // FRAME_T + 1) * FRAME_T
        f = 0
        keys(h, script[0] if script else [])
        cur = script[0] if script else []
        pend = None                                  # an interrupt in flight
        in_scan, waiting = False, None
        self.nested = 0
        while f < frames:
            pc = r[PC]
            if r[T] >= nb:
                f += 1
                nxt = script[f] if f < len(script) else []
                if in_scan:                          # between scans, as Nat does
                    waiting = nxt
                else:
                    cur = nxt
                    keys(h, cur)
                nb += FRAME_T
            if pc == 0xF7B9 and in_scan:
                in_scan = False
                if waiting is not None:
                    cur = waiting
                    keys(h, cur)
                    waiting = None
            if pc == 0xF7B8:
                in_scan = True
            if pc in GUARD:
                raise Fail('guard')
            if pend and pc == pend[1] and r[SP] == pend[2]:
                #  classed by the keys its scan READ -- the frame's, applied after acceptance
                self.isr.append([pend[0], r[T] - pend[0], '+'.join(cur), pend[4], sets_of(m), pend[5]])
                pend = None
            if pc in (0xF7B8, 0xF7B9, 0xF7BD, 0xF7B3, 0xF7D3, 0xF5F0, 0xF5F8, 0xF7F9, 0xF801, 0xF664,
                      0xF674, 0xF5E7, 0xF5C1, 0xF5C6):
                self.ev.append([pc, r[T], m[LASTK], '+'.join(cur), sets_of(m), pend is not None, r[IFF]])
            if pc in stops:
                return pc
            ops[mem[pc]]()
            if r[IFF] and r[T] % fd < ia:
                ta, ret = r[T], r[PC]                # the return address is the NEXT instruction
                before = sets_of(m)
                sim.accept_interrupt(r, mem, pc)
                pend = (ta, ret, (r[SP] + 2) & 0xFFFF, '+'.join(cur), before, m[LASTK])
                if in_scan:
                    self.nested += 1
        return None


def isr_T_between(isr, t0, t1):
    return sum(d for ta, d, *rest in isr if t0 <= ta < t1)


def scan_class(combo, before):
    """the path ONE scan takes, as the measured rule names it, from the keys it reads and the
       sets before it: FREEZE and NONE (no key) change no set's key; a key HOLDS a set that
       survives this scan's aging (count > 1) -- REPEAT when its repeat count runs out now,
       HELD otherwise -- else it is NEW if a set is (or comes) free, else FULL"""
    c, ident = combo_class(combo.split('+') if combo else [], before)
    if c == 'none':
        return 'aging' if any(x is not None for x in before) else 'idle'   # no key: does a set age?
    if c != 'key':
        return c
    alive = [x for x in before if x is not None and x[1] > 1]
    for x in alive:
        if x[0] == ident:
            return 'repeat' if x[2] == 1 else 'held'
    return 'new' if len(alive) < 2 else 'full'


def spin_passes(t):
    """from the events: every explicit pass $F7B8 -> the next $F7B8 (nothing to read) or
       $F7B8 -> $F7BD (a code to read), less the interrupts inside it, classed"""
    ev = t.ev
    rows = []
    for i in range(len(ev) - 1):
        a = ev[i]
        if a[0] != 0xF7B8:
            continue
        #  the $F7B9 after it gives LAST-K and the sets after the scan
        j = i + 1
        while j < len(ev) and ev[j][0] != 0xF7B9:
            j += 1
        if j >= len(ev):
            break
        b = ev[j]
        k = j + 1
        if k >= len(ev):
            break
        c = ev[k]
        if c[0] not in (0xF7B8, 0xF7BD):
            continue
        emitted = b[2] != 0 and a[2] == 0
        dt = c[1] - a[1] - isr_T_between(t.isr, a[1], c[1])
        rows.append([scan_class(a[3], a[4]), 'read' if c[0] == 0xF7BD else 'spin', dt])
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def phase_timing():
    out = {}
    #  (a) the spin and the interrupt, naturally, at P1's menu: idle, a REJECTED chord held
    #  (new, then held, then its repeats), a freeze, the shifts alone, and fresh rejected presses
    script = ([[]] * 12 + [['CAPS', 'A']] * 20 + [[]] * 4 + [['A', 'B']] * 6 + [['CAPS']] * 3 + [['SYM']] * 3 +
              [['CAPS', 'SYM']] * 8 + [['SYM', 'A']] * 2 + [['CAPS', 'S']] * 2 + [['SYM', 'D']] * 2 +
              [['CAPS', 'F']] * 2 + [['SYM', '2']] * 5 + [[]] * 10)
    t = Timer(world('title')[0])
    t.run(script, len(script))
    out['nested'] = [t.nested, len(t.isr)]
    passes = spin_passes(t)
    cls = {}
    for c, kind, dt in passes:
        cls.setdefault(c + ':' + kind, []).append(dt)
    out['spin'] = {k: [len(v), round(mean(v), 2), min(v), max(v)] for k, v in sorted(cls.items())}
    icls = {}
    for ta, d, combo, before, after, lk in t.isr:
        icls.setdefault(scan_class(combo, before), []).append(d)
    out['isr'] = {k: [len(v), round(mean(v), 2), min(v), max(v)] for k, v in sorted(icls.items())}
    #  (b) the filter's two exits: $F7BD -> $F7B3 -> $F7B8 (reject) and $F7BD -> $F7D3 (accept)
    rej, acc = [], []
    ev = t.ev
    for i in range(len(ev) - 1):
        if ev[i][0] == 0xF7BD:
            j = i + 1
            while j < len(ev) and ev[j][0] not in (0xF7B8, 0xF7D3):
                j += 1
            if j < len(ev):
                d = ev[j][1] - ev[i][1] - isr_T_between(t.isr, ev[i][1], ev[j][1])
                (rej if ev[j][0] == 0xF7B8 else acc).append(d)
    out['reject'] = [len(rej), round(mean(rej), 2), min(rej), max(rej)] if rej else None
    #  (c) accept -> click -> echo -> the release wait -> the menu test, naturally, over keys the
    #  filter takes and the menu refuses ('5', 'A', ENTER) and keys it takes (on copies of P1's
    #  menu): $F7BD -> $F7D3, $F7D3 -> $F7F9 (the click and echo, interrupts inside it counted),
    #  the $F7F9 passes, $F7F9's last pass -> $F7B8 (refused) or -> $F674 (taken)
    rows = []
    for k, hold, st in (('5', 3, 'title'), ('A', 3, 'title'), ('ENTER', 8, 'title'), ('0', 12, 'title'),
                        ('4', 3, 'title'), ('2', 9, 'title'), ('SPACE', 3, 'title'), ('3', 3, 'p2b')):
        tt = Timer(world(st)[0])
        tt.run([[k]] * hold + [[]] * 12, hold + 12, stops=(0xF674, 0xF723, 0xF5E7))
        e = tt.ev
        at = {pc: [x[1] for x in e if x[0] == pc] for pc in (0xF7BD, 0xF7D3, 0xF7F9, 0xF801, 0xF7B8, 0xF674)}
        t_bd = [x for x in at[0xF7BD]][0]
        t_d3 = at[0xF7D3][0]
        t_f9 = at[0xF7F9][0]
        t_01 = at[0xF801][0]
        nxt = [x for x in at[0xF7B8] if x > t_01] + at[0xF674]
        t_nx = min(nxt)
        n_isr_click = sum(1 for ta, d, *r_ in tt.isr if t_d3 <= ta < t_f9)
        rows.append({'key': k, 'hold': hold, 'world': st, 'accept': t_d3 - t_bd, 'click': t_f9 - t_d3,
                     'click_isrs': n_isr_click,
                     'release': t_01 - t_f9 - isr_T_between(tt.isr, t_f9, t_01),
                     'release_isrs': sum(1 for ta, d, *r_ in tt.isr if t_f9 <= ta < t_01),
                     'after': t_nx - t_01 - isr_T_between(tt.isr, t_01, t_nx),
                     'taken': bool(at[0xF674])})
    out['accept_path'] = rows
    #  (d) one $F7F9 pass and one $F5F0 pass: a key held through each, the pass T by division
    h, m, r = world('title')
    keys(h, ['9'])
    run_to(h, (0xF7F9,), True)
    t0 = r[T]
    n = 0
    while n < 20000:
        if r[PC] == 0xF7F9:
            n += 1
        h.step(1, interrupts=False)
    #  n passes began at $F7F9 in (T - t0): the last one is incomplete by at most one pass
    out['release_pass'] = round((r[T] - t0) / n, 3)
    h, m, r = world('boot')
    keys(h, ['ENTER'])
    run_to(h, (0xF5F0,), False)
    t0 = r[T]
    n = 0
    while n < 20000:
        if r[PC] == 0xF5F0:
            n += 1
        h.step(1, interrupts=False)
    out['wait_pass'] = round((r[T] - t0) / n, 3)
    #  (e) the wait's exit: ENTER held into $F5F0 at P1 (interrupts off, as P1 is), let go: the
    #  T from the pass that sees no key to $F5F8
    h.step(1, interrupts=False)
    run_to(h, (0xF5F0,), False)                  # the top of a pass, the key still down
    keys(h, [])
    t1 = r[T]
    run_to(h, (0xF5F8,), False)
    out['wait_exit'] = r[T] - t1
    #  (f) the entry to the key read: $F664 -> the first $F7B8
    h, m, r = world('boot')
    run_to(h, (0xF664,), False)
    t0 = r[T]
    run_to(h, (0xF7B8,), False)
    out['menu_entry'] = r[T] - t0
    #  (f2) the two paths a frame-sampled menu reaches only at its first scan or through the
    #  interrupt: NEW read by the spin ($F7B8 -> $F7BD, a fresh press found by an explicit scan
    #  -- P1's first scan with a key down through the paint) and FULL ($F7B8 -> $F7B8, both sets
    #  held by keys no longer down): scan-level drives over sixteen frame phases and five keys
    nr, fl = [], []
    for ph in range(16):
        for combo in (['A'], ['1'], ['CAPS', 'A'], ['SYM', 'A'], ['ENTER']):
            h, m, r = world('title')
            r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph * (FRAME_T // 16)
            free_sets(m)
            m[LASTK] = 0
            keys(h, combo)
            r[PC] = 0xF7B8
            t0 = r[T]
            run_to(h, (0xF7BD,), False, limit=10000)
            nr.append(r[T] - t0)
        h, m, r = world('title')
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph * (FRAME_T // 16)
        free_sets(m)
        scan(h, ['CAPS', 'A'])
        scan(h, ['CAPS', 'S'])
        keys(h, ['CAPS', 'D'])
        m[LASTK] = 0
        r[PC] = 0xF7B8
        t0 = r[T]
        h.step(1, interrupts=False)
        run_to(h, (0xF7B8,), False, limit=10000)
        fl.append(r[T] - t0)
    out['new_read'] = [len(nr), round(mean(nr), 2), min(nr), max(nr)]
    out['full_spin'] = [len(fl), round(mean(fl), 2), min(fl), max(fl)]
    #  (f2b) EVERY PASS PATH BUILT ON PURPOSE -- the state before the scan made by scans, the
    #  keys held, $F7B8 at 64 phases of the frame (+300 T), interrupts off, to the next $F7B8
    #  (nothing to read) or to $F7BD (a code to read).  The port's SCAN_T: a path's mean with ONE
    #  key (or none) down, and the shifts' own terms, CAPS and SYM, measured over the same path
    def pass_T(pre, now, n=64):
        ts = []
        cls = None
        for k in range(n):
            h, m, r = world('title')
            free_sets(m)
            for c in pre:
                scan(h, c)
            cls = scan_class('+'.join(now), sets_of(m))
            keys(h, now)
            m[LASTK] = 0
            r[T] = (r[T] // FRAME_T + 1) * FRAME_T + k * (FRAME_T // n) + 300
            r[PC] = 0xF7B8
            t0 = r[T]
            h.step(1, interrupts=False)
            while r[PC] not in (0xF7B8, 0xF7BD):
                h.step(1, interrupts=False)
                guard(h)
            ts.append(r[T] - t0)
        return [cls, round(mean(ts), 2), min(ts), max(ts)]
    PASSES = {'idle': ([], []), 'aging': ([['A']], []), 'shift_caps': ([], ['CAPS']), 'shift_sym': ([], ['SYM']),
              'aging_caps': ([['A']], ['CAPS']), 'freeze': ([], ['A', 'B']), 'freeze3': ([], ['A', 'B', 'C']),
              'new': ([], ['A']), 'new_digit': ([], ['1']), 'new_caps': ([], ['CAPS', 'A']),
              'new_sym': ([], ['SYM', 'A']), 'held': ([['A']], ['A']), 'held_caps': ([['CAPS', 'A']], ['CAPS', 'A']),
              'repeat': ([['A']] * 35, ['A']), 'repeat_caps': ([['CAPS', 'A']] * 35, ['CAPS', 'A']),
              'full': ([['A'], ['B']], ['C'])}
    out['pass'] = {name: pass_T(pre, now) for name, (pre, now) in PASSES.items()}
    #  (f3) THE INTERRUPT BY PATH, each class built on purpose: an IM 1 acceptance at the frame's
    #  first T (where every one lands -- the top border, before the display's contention), PC in
    #  the $F7F9 loop, run to the return; the natural means above mix the classes' states
    setups = {'none': ([], []), 'none_aging': ([['A']], []), 'new': ([], ['A']),
              'held': ([['A']], ['A']), 'repeat': ([['A']] * 35, ['A']), 'freeze': ([['A']], ['A', 'B']),
              'full': ([['A'], ['B']], ['C']), 'shift_caps': ([], ['CAPS']), 'shift_sym': ([], ['SYM']),
              'new_digit': ([], ['1'])}
    ic = {}
    for name, (pre, now) in setups.items():
        h, m, r = world('title')
        free_sets(m)
        for c in pre:
            scan(h, c)
        keys(h, now)
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + 4
        r[PC] = 0xF7F9
        ret, sp0 = r[PC], r[SP]
        before = sets_of(m)
        t0 = r[T]
        m[LASTK] = 0
        h.sim.accept_interrupt(r, h.sim.memory, 0xF7F9)
        while not (r[PC] == ret and r[SP] == sp0):
            h.step(1, interrupts=False)
            guard(h)
        ic[name] = [r[T] - t0, scan_class('+'.join(now), before), 1 if m[LASTK] else 0]
    out['isr_class'] = ic
    #  (f4) THE IDLE MENU'S OWN RATE (the recon's fact 2), the cross-check on SCAN_T and ISR_T:
    #  title.pkl, no key, 50 frames -- every explicit scan and every interrupt accepted
    h, m, r = world('title')
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    end = r[T] + 50 * FRAME_T
    n_rst = n_isr = n_ins = 0
    while r[T] < end:
        pc = r[PC]
        if pc == 0xF7B8:
            n_rst += 1
        ops[mem[pc]]()
        n_ins += 1
        if r[IFF] and r[T] % fd < ia:
            sim.accept_interrupt(r, mem, pc)
            n_isr += 1
    out['idle50'] = {'frames': 50, 'explicit': n_rst, 'isrs': n_isr, 'steps': n_ins}
    #  (g0) P2's paint at ONE phase -- boot.pkl's own $F5F8 phase, interrupts off -- after each
    #  preset: the paint's T moves only with the string the skip gate drops
    h, m, r = world('boot')
    run_to(h, (0xF5E7,), False, limit=100)
    out['load_open_phase'] = r[T] % FRAME_T          # P1's $F5E7 at the load: OPEN_T's own phase
    run_to(h, (0xF5F8,), False)
    ph_f8 = r[T] % FRAME_T
    out['load_paint_phase'] = ph_f8                  # P1's $F5F8: PAINT_T's own phase
    same = {}
    for p1 in ('2', '3', '4'):
        h, m, r = world('title')
        keys(h, [p1])
        run_to(h, (0xF7F9,), True)
        keys(h, [])
        run_to(h, (0xF5F8,), True)
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph_f8
        t0 = r[T]
        run_to(h, (0xF664,), False)
        same[p1] = r[T] - t0
    out['p2_paint_at_p1_phase'] = same
    #  (g1) THE CONTENTION LAW BY START PHASE: the open ($F5E7 -> $F5F0, the digits and the CLS),
    #  the paint ($F5F8 -> $F664) for each line player 2's gate can drop, and the click ($F7D3 ->
    #  $F7F9), each begun at 64 phases of the frame (every 1,092 T), interrupts off -- and at 16
    #  HELD-OUT midpoints, against which the port's straight-line interpolation is checked
    def t_open(ph):
        h, m, r = world('boot')
        run_to(h, (0xF5E7,), False, limit=100)
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph
        t0 = r[T]
        run_to(h, (0xF5F0,), False)
        return r[T] - t0
    paint_at = {'none': None}
    h, m, r = world('boot')
    run_to(h, (0xF5F8,), False)
    paint_at['none'] = h.save_state()
    for p1, key in (('3', 'kempston'), ('4', 'cursor')):
        h, m, r = world('title')
        keys(h, [p1])
        run_to(h, (0xF7F9,), True)
        keys(h, [])
        run_to(h, (0xF5F8,), True)
        paint_at[key] = h.save_state()

    def t_paint(key, ph):
        h = Harness(contended=True)
        h.load_state(paint_at[key])
        r = h.sim.registers
        r[T] = (r[T] // FRAME_T + 1) * FRAME_T + ph
        t0 = r[T]
        run_to(h, (0xF664,), False)
        return r[T] - t0

    def t_click(ph):
        c = click_outs(True, phase=ph)
        return c['T']
    N = 64
    step = FRAME_T // N
    tabs = {'open': [t_open(k * step) for k in range(N)],
            'click': [t_click(k * step) for k in range(N)]}
    for key in ('none', 'kempston', 'cursor'):
        tabs['paint_' + key] = [t_paint(key, k * step) for k in range(N)]
    held = {}
    for name, fn in (('open', t_open), ('click', t_click), ('paint_none', lambda ph: t_paint('none', ph)),
                     ('paint_kempston', lambda ph: t_paint('kempston', ph)),
                     ('paint_cursor', lambda ph: t_paint('cursor', ph))):
        held[name] = [[k * 4 * step + step // 2, fn(k * 4 * step + step // 2)] for k in range(N // 4)]
    out['by_phase'] = {'n': N, 'step': step, 'tables': tabs, 'held_out': held}
    #  (g) player 2's open and paint, after each preset, interrupts on: T, the interrupts landing
    #  in each and their T -- the port charges the interrupts itself, so its debt is the rest
    p2 = []
    for p1 in ('2', '3', '4'):
        tt = Timer(world('title')[0])
        tt.run([[p1]] * 3 + [[]] * 30, 33, stops=(0xF664,))
        e = tt.ev
        t_ret = [x[1] for x in e if x[0] == 0xF5C1][0]
        t_e7 = [x[1] for x in e if x[0] == 0xF5E7][0]
        t_f0 = [x[1] for x in e if x[0] == 0xF5F0][0]
        t_f8 = [x[1] for x in e if x[0] == 0xF5F8][0]
        t_64 = tt.r[T]
        ch = {'2': 118, '3': 107, '4': 104}[p1]
        p2.append({'p1': p1, 'chars': ch, 'spine': t_e7 - t_ret,
                   'open': t_f0 - t_e7, 'open_isrs': [d for ta, d, *r_ in tt.isr if t_e7 <= ta < t_f0],
                   'wait': t_f8 - t_f0, 'wait_isrs': [d for ta, d, *r_ in tt.isr if t_f0 <= ta < t_f8],
                   'paint': t_64 - t_f8, 'paint_isrs': [d for ta, d, *r_ in tt.isr if t_f8 <= ta < t_64]})
    out['p2'] = p2
    print('timing: spin %s' % out['spin'])
    print('        isr %s' % out['isr'])
    print('        reject %s; accept path %s' % (out['reject'], [(x['key'], x['accept'], x['click'], x['click_isrs'], x['release'], x['after'], x['taken']) for x in rows]))
    print('        release pass %.3f, wait pass %.3f, wait exit %d, menu entry %d' % (
        out['release_pass'], out['wait_pass'], out['wait_exit'], out['menu_entry']))
    for x in p2:
        print('        P2 after %s: spine %d open %d (%s) wait %d (%s) paint %d (%s)' % (
            x['p1'], x['spine'], x['open'], x['open_isrs'], x['wait'], x['wait_isrs'], x['paint'], x['paint_isrs']))
    return out


# ------------------------------------------------------------------ the frames
#  key scripts from the LOAD's own hand-over (boot.pkl at $F5BC, its own frame phase), as
#  (frames, keys) runs; frame 0 is the part-frame the load hands over in.  Each drive stops at
#  the spine ($F5C6, after player 2) or the redefine screen ($F723, KEYBOARD -- H-c's).
SCRIPTS = {
    'cursor_kempston': [(8, []), (3, ['4']), (14, []), (3, ['3']), (12, [])],
    'sinclair_twice': [(8, []), (2, ['2']), (16, []), (2, ['2']), (12, [])],
    'blocked': [(8, []), (2, ['3']), (16, []), (2, ['3']), (8, []), (2, ['4']), (12, [])],
    'latch': [(7, []), (2, ['CAPS', '2']), (20, ['2']), (1, []), (3, ['2']), (14, []), (2, ['CAPS', 'T']),
              (12, [])],
    'clicks': [(7, []), (2, ['A']), (8, []), (2, ['5']), (8, []), (9, ['ENTER']), (8, []), (2, ['CAPS', 'R']),
               (14, []), (2, ['SYM', 'X']), (8, []), (2, ['4']), (12, [])],
    'held_paint': [(8, []), (2, ['3']), (7, []), (6, ['4']), (12, [])],
    'held_load': [(5, ['ENTER']), (6, []), (2, ['4']), (14, []), (2, ['3']), (12, [])],
    'keyboard': [(8, []), (2, ['1']), (10, [])],
    'chords': [(7, []), (3, ['A', 'B']), (2, ['CAPS', 'SYM']), (2, ['CAPS', 'SYM', '3']), (2, ['CAPS']),
               (2, ['SYM']), (2, ['1', '2']), (1, []), (2, ['3']), (14, []), (2, ['4']), (12, [])],
    'early_key': [(1, []), (6, ['4']), (4, []), (2, ['4']), (14, []), (2, ['2']), (12, [])],
    'shift_switch': [(7, []), (2, ['SYM', '4']), (3, ['CAPS', '4']), (3, ['4']), (1, []), (2, ['CAPS', 'R']),
                     (16, []), (2, ['CAPS', 'S']), (12, [])],
    'alias_keyboard': [(8, []), (2, ['CAPS', 'Q']), (10, [])],
}


def expand(script):
    out = []
    for n, k in script:
        out += [k] * n
    return out


def frames_drive(script):
    h, m, r = world('boot')
    seq = expand(script)
    nat = Nat(h, seq, label='open', pass_=1)
    why = nat.run(len(seq) + 1)
    nb0 = nat.nb - nat.frame * FRAME_T               # the first frame boundary of the drive
    return {'stop': why, 'rows': nat.rows, 'nested': nat.n_nested, 'deferred': nat.n_deferred,
            'clicks': [[t - nb0, v] for t, p, port, v in OUTS[nat.out0:] if port == 0xFE and click_out(p)],
            'end': vars_of(m)}


def phase_frames():
    h, m, r = world('boot')
    out = {'boot_phase': r[T] % FRAME_T, 'scripts': {}}
    for name, script in SCRIPTS.items():
        d = frames_drive(script)
        d['script'] = [[n, k] for n, k in script]
        out['scripts'][name] = d
        labs = []
        for row in d['rows']:
            if not labs or labs[-1][0] != row[1]:
                labs.append([row[1], row[0]])
        print('frames %-16s stop %-9s %d frames, %d click OUTs; %s' % (
            name, d['stop'], len(d['rows']), len(d['clicks']), ' '.join('%s@%d' % (a, b) for a, b in labs)))
    return out


# ------------------------------------------------------------------ main
PHASES = ['tape', 'filter', 'decode', 'pairs', 'history', 'menu', 'test', 'dispatch', 'builder', 'click',
          'timing', 'frames']


def capture():
    out = {'meta': {'tool': 'tools/ctrlmenu.py', 'no_rom_bytes': True,
                    'note': 'the filter\'s verdicts, key NAMES, counts and T only; raw codes '
                            'only where the game\'s filter accepts them'}}
    for p in PHASES:
        out[p] = globals()['phase_' + p]()
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE))
        new = json.loads(json.dumps(capture()))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    elif cmd in PHASES:
        globals()['phase_' + cmd]()
    return 0


if __name__ == '__main__':
    sys.exit(main())
