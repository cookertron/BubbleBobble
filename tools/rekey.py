"""KR2 -- RE-KEY the legacy behavioural fixtures.

The 2026-09-11 re-baseline (fc6bf31) re-captured thirteen fixtures with
tools/capture.py from key scripts "recovered from the old fixture's own $FD88
bytes", but the script that did it was never committed, and no fixture stores
the keys it pressed or the key table they were pressed under.  Once the in-play
reader $ABF4..$ACEB is wired into the engine, every gate that pokes $FD88 would
be overwritten on the first odd ISR -- so each fixture needs its KEYS back.

For every fixture this tool:

  1. reads the capture state's OWN key table, the 16 bytes at $B5FD..$B60C, from
     the state file (never assumed), and each player's table select
     ((IY+$5A) bit 0: $FDDA for P1, $FDE4 for P2 -> $B5FD or $B605);
  2. inverts each reading row's recorded direction byte (low nibble: bit 3 LEFT,
     bit 2 RIGHT, bit 1 JUMP, bit 0 BLOW) into keys under that table -- or into
     the Kempston byte when the table's first byte is $1F;
  3. re-runs capture.drive() with that script, the fixture's own pokes and its
     own sampler, and compares EVERY committed field of EVERY row, the seed and
     the sample PC;
  4. if a row differs, SEARCHES the ambiguous frames (rising-arc lock, $FF drop,
     rows where the reader did not run) before it for the input that reproduces
     it, greedily, first differing row first;
  5. only when the whole fixture reproduces, writes it back with two ADDED
     fields -- per-row `keys` (key names, keyprobe spelling) and `kemp` (the
     Kempston byte), and `keytab` (the 16 bytes) in the seed -- after proving
     that every pre-existing field is identical and that the file re-serialises
     byte-for-byte.

Reading rows: the reader runs only in the ISR that makes the parity ODD, so
row i with par = 1 reads the keys held during frame i.  capture.drive changes
keys at ISR exit only, so the keys of an even row are never read by $ABF4; the
script gives an even row the keys of the NEXT reading row (a press one frame
early), which is the same input to the reader.

Guards (every run): the harness never enters $D000..$D2FF (the frame stepper is
wrapped with those addresses as stop targets and a hit is fatal); nothing in
the output is ROM -- the only new bytes are the RAM table at $B5FD.

Usage:  python tools/rekey.py [--write --backup DIR] [NAME ...]
        (no --write: verify only)
"""
import sys
import os
import json
import copy
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture                                          # noqa: E402
from harness import PC                                  # noqa: E402
from keyprobe import KEYMAP, press                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYTAB = 0xB5FD
GUARD = tuple(range(0xD000, 0xD300))


class GuardHit(Exception):
    pass


def guarded_frame(h):
    """capture.frame with the $D000..$D2FF guard: the run stops on any of those
       addresses and the capture dies rather than execute there."""
    for tgt in (capture.ISR_IN, capture.ISR_OUT):
        h.run_until((tgt,) + GUARD, limit=10 ** 7, stride=1)
        pc = h.regs[PC]
        if pc != tgt:
            raise GuardHit('PC $%04X (wanted $%04X)' % (pc, tgt))
        h.step(1)


capture.frame = guarded_frame          # drive() looks the global up per call

KEYNAME = {(sel, 1 << bit): name for name, (sel, bit) in KEYMAP.items()}


# ---------------------------------------------------------------------------
# the key tables, read from the state
# ---------------------------------------------------------------------------

def state_tables(state):
    h, m = capture.new(state)
    tab = [m[KEYTAB + i] for i in range(16)]
    sel = [m[0xFDDA] & 1, m[0xFDE4] & 1]          # (IY+$5A) bit 0, P1 / P2
    return tab, sel


def player_table(tab, sel):
    base = 8 * sel
    return tab[base:base + 8]


def nibble_to_input(t, nib):
    """(keys, kemp) that make the reader produce `nib` under the 8-byte table t.
       Pair order: LEFT bit3, RIGHT bit2, JUMP bit1, BLOW bit0."""
    keys, kemp = [], 0
    for j, bit in enumerate((8, 4, 2, 1)):
        if not nib & bit:
            continue
        if t[0] == 0x1F:                            # $AC0E: the whole table is Kempston
            kemp |= t[2 * j + 1]
        else:
            name = KEYNAME.get((t[2 * j], t[2 * j + 1]))
            if name is None:
                raise SystemExit('table pair %d (%02X,%02X) is not a single key'
                                 % (j, t[2 * j], t[2 * j + 1]))
            keys.append(name)
    return keys, kemp


# ---------------------------------------------------------------------------
# samplers: each reproduces the committed row shape field for field
# ---------------------------------------------------------------------------

def par(m):
    return m[0x8DBD] & 1


def w16(m, a):
    return m[a] | (m[a + 1] << 8)


def s_move(m):
    return {'par': par(m), 'dir': m[0xFD88], 'x': m[0xFD85], 'y': m[0xFD86],
            'air': m[0xFD89]}


def s_walk(m):
    r = s_move(m)
    r['xbk'] = m[0xFD83]
    r['fl'] = m[0xFD87]
    return r


def s_blow(m):
    return {'par': par(m), 'dir': m[0xFD88], 'fde0': m[0xFDE0], 'fdda': m[0xFDDA],
            'px': m[0xFD85], 'py': m[0xFD86], 'pf': m[0xFD87],
            's': [[m[b + 5], m[b + 6], m[b + 7], m[b + 4]]
                  for b in (0xFED8, 0xFEE2)]}


def s_death(m):
    return {'par': par(m), 'dir': m[0xFD88], 'px': m[0xFD85], 'py': m[0xFD86],
            'anim': m[0xFD84], 'pf': m[0xFD87], 'spr': w16(m, 0xFD80),
            'fdda': m[0xFDDA], 'lives': m[0xFDDC], 'air': m[0xFD89],
            'x2': m[0xFD82], 'x3': m[0xFD83], 'hurry': w16(m, 0x8DBD),
            'master': w16(m, 0x8DB6), 'aa65': m[0xAA65], 'r9160': m[0x9160],
            'fde0': m[0xFDE0], 'fdde': m[0xFDDE], 'fddf': m[0xFDDF],
            'd8': m[0xFD88]}


def pl(m, b):
    return [m[b + 5], m[b + 6], m[b + 9], m[b + 7], m[b + 4]]


def s_twop(m):
    return {'par': par(m), 'd1': m[0xFD88], 'd2': m[0xFD92],
            'p1': pl(m, 0xFD80), 'p2': pl(m, 0xFD8A),
            'fdda': m[0xFDDA], 'fde4': m[0xFDE4], 'aa65': m[0xAA65]}


def s_join(m):
    r = s_twop(m)
    r['lives2'] = m[0xFDE6]
    r['hurry'] = w16(m, 0x8DBD)
    r['r9160'] = m[0x9160]
    r['spr2'] = w16(m, 0xFD8A)
    return r


def bub(m, b=0xFED8):
    return {'x': m[b + 5], 'y': m[b + 6], 'f7': m[b + 7], 'a4': m[b + 4]}


def s_bubwall(m):
    r = {'par': par(m), 'dir': m[0xFD88]}
    r.update(bub(m))
    return r


def s_bubpush(m):
    s0 = bub(m)
    s0['cell'] = w16(m, 0xFED8 + 2)
    return {'par': par(m), 'dir': m[0xFD88], 'px': m[0xFD85], 'py': m[0xFD86],
            'pf': m[0xFD87], 's0': s0}


def s_bubage(m):
    b = 0xFED8
    return {'par': par(m), 'dir': m[0xFD88], 'a4': m[b + 4], 'f7': m[b + 7],
            'x': m[b + 5], 'y': m[b + 6]}


# ---------------------------------------------------------------------------
# the fixture catalogue
# ---------------------------------------------------------------------------

def poke_player_x(px):
    def f(m):
        m[0xFD83] = m[0xFD85] = px
    return f


def poke_bubpush(seed):
    def f(m):
        m[0xFD83] = m[0xFD85] = seed['px']
        for i in range(10):                       # the poked RISEN bubble, slot 0
            m[0xFED8 + i] = seed['slot0'][i]
    return f


def units():
    """(fixture, label, get(fx) -> (seed dict, seq list), sampler, dirs, pokes,
        extra keys, seed overrides) for every re-keyed sequence."""
    U = []

    def add(name, label, get, sampler, dirs=('dir', None), pokes=None,
            extra=(), seed_fix=None):
        U.append(dict(name=name, label=label, get=get, sampler=sampler,
                      dirs=dirs, pokes=pokes, extra=list(extra), seed_fix=seed_fix))

    top = lambda fx: (fx['seed'], fx['seq'])            # noqa: E731
    add('walk', 'walk', top, s_walk)
    for n in ('jump', 'leftwall', 'airsteer', 'fall'):
        add(n, n, top, s_move)
    add('fallleft', 'fallleft', top, s_move,
        pokes=lambda fx: {int(k, 16): v for k, v in fx['poke'].items()})
    for sc in ('blow', 'blow2', 'blowleft'):
        add('blow', sc, (lambda s: lambda fx: (fx['seeds'], fx['scenarios'][s]))(sc), s_blow)
    add('death', 'death', top, s_death)
    add('twop', 'twop', top, s_twop, dirs=('d1', 'd2'))
    add('join', 'join', top, s_join, dirs=('d1', 'd2'), extra=['2'])
    add('bubwall', 'bubwall', top, s_bubwall,
        pokes=lambda fx: poke_player_x(fx['seed']['px']),
        seed_fix=lambda fx, sd: dict(sd, px=fx['seed']['px']))
    for sc in ('push', 'touch'):
        g = (lambda s: lambda fx: (fx['scenarios'][s]['seed'], fx['scenarios'][s]['seq']))(sc)
        add('bubpush', sc, g, s_bubpush,
            pokes=(lambda s: lambda fx: poke_bubpush(fx['scenarios'][s]['seed']))(sc),
            seed_fix=(lambda s: lambda fx, sd: dict(
                sd, slot0=fx['scenarios'][s]['seed']['slot0'],
                px=fx['scenarios'][s]['seed']['px']))(sc))
    add('bubage', 'bubage', top, s_bubage)
    return U


# ---------------------------------------------------------------------------
# inversion, re-run, search
# ---------------------------------------------------------------------------

ADDED_ROW = ('keys', 'kemp')


def committed(row):
    return {k: v for k, v in row.items() if k not in ADDED_ROW}


def reading_rows(seq, fld):
    """rows whose dir is the reader's own output: par 1 AND the high nibble is
       the previous row's low nibble ($AC00 shifts the OLD +8 up).  A par-1 row
       failing that test was written by something else (the $AB6B respawn's
       +8 := 1, a join's +8 := 0) or left stale -- the reader did not run, and
       its low nibble says nothing about the keys held."""
    out = []
    for i, r in enumerate(seq):
        if r['par'] != 1:
            continue
        if i > 0 and (r[fld] >> 4) != (seq[i - 1][fld] & 0x0F):
            continue
        out.append(i)
    return out


def naive_nibbles(seq, fld):
    """per-frame low nibble: reading rows invert their own dir; every other row
       (even rows, and odd rows the reader did not write) takes the NEXT reading
       row's keys -- i.e. the keys are already held -- or the last one's at the
       tail."""
    n = len(seq)
    out = [0] * n
    rd = set(reading_rows(seq, fld))
    nxt = None
    for i in range(n - 1, -1, -1):
        if i in rd:
            nxt = seq[i][fld] & 0x0F
        out[i] = nxt
    last = 0
    for i in range(n):
        if out[i] is None:
            out[i] = last
        last = out[i]
    return out


def build_inputs(nibs, tables, extra):
    """nibs: [per-player list of per-frame nibbles] -> (keys list, kemp list)"""
    n = len(nibs[0])
    keys, kemp = [], []
    for i in range(n):
        ks, kb = list(extra), 0
        for p, pn in enumerate(nibs):
            if pn is None:
                continue
            k, b = nibble_to_input(tables[p], pn[i])
            ks += [x for x in k if x not in ks]
            kb |= b
        keys.append(ks)
        kemp.append(kb)
    return keys, kemp


def run(state, pokes, keys, kemp, sampler):
    n = len(keys)
    script = {i: (list(keys[i]) or None) for i in range(n)}
    kmp = {i: kemp[i] for i in range(n)}
    seed, rows = capture.drive(state, script, n, sampler, pokes=pokes,
                               kempston=kmp)
    return seed, rows


def first_diff(rows, seq):
    for i, (a, b) in enumerate(zip(rows, seq)):
        if a != committed(b):
            return i
    if len(rows) != len(seq):
        return min(len(rows), len(seq))
    return None


def describe(a, b):
    b = committed(b)
    return ', '.join('%s %r!=%r' % (k, a.get(k), b.get(k))
                     for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k))


def rekey_unit(u, fx, log):
    name, state = u['name'], fx['state']
    seed_c, seq = u['get'](fx)
    tab, sel = state_tables(state)
    tables = [player_table(tab, sel[0]), player_table(tab, sel[1])]
    fields = [f for f in u['dirs'] if f]
    nibs = [naive_nibbles(seq, f) if f else None for f in u['dirs']]
    pokes = u['pokes'](fx) if u['pokes'] else None
    naive = [list(x) if x else None for x in nibs]
    searched = set()
    tries = 0
    while True:
        keys, kemp = build_inputs(nibs, tables, u['extra'])
        seed, rows = run(state, pokes, keys, kemp, u['sampler'])
        tries += 1
        r = first_diff(rows, seq)
        if r is None:
            break
        log('   %s: row %d differs (%s); searching' % (u['label'], r, describe(rows[r], seq[r])))
        fixed = False
        # candidates: each frame from r back to r-8 (reading rows first), each
        # player's nibble at that frame set to any of 16 values, holding it from
        # that frame through r (the lock / drop / stale-row cases all live here)
        for f in range(r, max(-1, r - 9), -1):
            for p, pn in enumerate(nibs):
                if pn is None:
                    continue
                for v in range(16):
                    if v == pn[f]:
                        continue
                    trial = [list(x) if x else None for x in nibs]
                    for g in range(f, r + 1):
                        trial[p][g] = v
                    k2, b2 = build_inputs(trial, tables, u['extra'])
                    _, rows2 = run(state, pokes, k2, b2, u['sampler'])
                    tries += 1
                    r2 = first_diff(rows2, seq)
                    if r2 is None or r2 > r:
                        nibs = trial
                        searched.update(range(f, r + 1))
                        fixed = True
                        break
                if fixed:
                    break
            if fixed:
                break
        if not fixed:
            return dict(ok=False, row=r, why=describe(rows[r], seq[r]), tries=tries)
    # the seed: drive's own, with the overrides the re-capture wrote over it
    exp = dict(seed)
    if u['seed_fix']:
        exp = u['seed_fix'](fx, exp)
    sc = {k: v for k, v in seed_c.items() if k != 'keytab'}
    if exp != sc:
        bad = sorted(k for k in set(exp) | set(sc) if exp.get(k) != sc.get(k))
        return dict(ok=False, row=-1, why='seed differs: %s' % bad, tries=tries)
    changed = sum(1 for p in range(len(nibs)) if nibs[p]
                  for i in range(len(seq)) if nibs[p][i] != naive[p][i])
    keys, kemp = build_inputs(nibs, tables, u['extra'])
    # the ambiguity census, from one more run with the final script: for each
    # player's reading rows, the phase (+9) the reader saw (the previous row's),
    # and the rows where the reader did not run at all.  Also proves the table
    # at $B5FD is never rewritten during the capture.
    aux = lambda m: {'ph': (m[0xFD89], m[0xFD93]),                 # noqa: E731
                     'tab': tuple(m[KEYTAB + i] for i in range(16))}
    _, arows = run(state, pokes, keys, kemp, aux)
    if any(list(a['tab']) != tab for a in arows):
        return dict(ok=False, row=-1, why='the key table changed during the run', tries=tries)
    amb = {'lock_1_0F': 0, 'at_10': 0, 'drop_11_FE': 0, 'ff': 0, 'not_read': 0}
    for p, f in enumerate(u['dirs']):
        if not f:
            continue
        rd = set(reading_rows(seq, f))
        for i in range(len(seq)):
            if seq[i]['par'] == 1 and i not in rd:
                amb['not_read'] += 1
            if i not in rd or i == 0:
                continue
            ph = arows[i - 1]['ph'][p]
            if 1 <= ph <= 0x0F:
                amb['lock_1_0F'] += 1
            elif ph == 0x10:
                amb['at_10'] += 1
            elif 0x11 <= ph <= 0xFE:
                amb['drop_11_FE'] += 1
            elif ph == 0xFF:
                amb['ff'] += 1
    return dict(ok=True, rows=len(seq), keys=keys, kemp=kemp, keytab=tab,
                sel=sel, searched=len(searched), changed=changed, tries=tries,
                fields=fields, amb=amb)


# ---------------------------------------------------------------------------
# settle: its own capture loop (tools/settle.py capture_window), key-driven
# ---------------------------------------------------------------------------

def rekey_settle(fx, log):
    import settle as S
    h, m = S.new()
    out = []
    plan = ((1, True), (4, True), (10, True), (1, False), (4, False), (10, False),
            (None, True), (None, False))
    for wi, (round_no, armed) in enumerate(plan):
        if round_no is None:
            h2, m2 = S.new()
            h.sim.registers[:] = h2.sim.registers[:]
            m[:] = m2[:]
        else:
            S.spawn_world(h, m, round_no, resume=True)
        m[S.B54B] = 0 if not armed else (0x14 if round_no == 1 else 0x58)
        m[0xFEC4] = 0x14
        keytab = [m[KEYTAB + i] for i in range(16)]
        w = fx['windows'][wi]
        if [w['key'][0], w['key'][1]] != [0xEF, 0x04]:
            return dict(ok=False, row=wi, why='window key is not EF/04')
        name = KEYNAME[(w['key'][0], w['key'][1])]           # '8'
        frames = []
        for f in range(200):
            h.ports.release_all()
            press(h.ports, name)
            guarded_frame(h)
            frames.append({'b54b': m[S.B54B], 'fec6': m[0xFEC6], 'aa65': m[0xAA65],
                           'par': m[0x8DBD], 'par_hi': m[0x8DBE],
                           'slots': [m[S.TABLE + i] for i in range(120)]})
            if round_no is None and f >= 40:
                break
            if armed and m[S.B54B] == 0 and f > 8:
                break
            if not armed and f >= 40:
                break
        h.ports.pressed = {}
        if [m[KEYTAB + i] for i in range(16)] != keytab:
            return dict(ok=False, row=wi, why='keytab changed inside the window')
        cw = [committed(r) for r in w['frames']]
        if frames != cw:
            i = next((i for i, (a, b) in enumerate(zip(frames, cw)) if a != b),
                     min(len(frames), len(cw)))
            return dict(ok=False, row=(wi, i), why='window %d frame %d differs' % (wi, i))
        head = {'round': round_no if round_no is not None else 0, 'live': round_no is None,
                'armed': armed, 'b54b0': 0 if not armed else (0x14 if round_no == 1 else 0x58),
                'targets': [m[S.TARGETS + i] for i in range(12)], 'count': m[S.COUNT_A]}
        for k, v in head.items():
            if w[k] != v:
                return dict(ok=False, row=wi, why='window %d header %s differs' % (wi, k))
        out.append(dict(keytab=keytab, n=len(frames), key=name))
    return dict(ok=True, windows=out, rows=sum(o['n'] for o in out))


# ---------------------------------------------------------------------------
# write-back with proof
# ---------------------------------------------------------------------------

def strip_added(o, seed_keys=('keytab',)):
    """remove every field this tool adds, recursively"""
    if isinstance(o, dict):
        return {k: strip_added(v) for k, v in o.items()
                if k not in ADDED_ROW and k not in seed_keys}
    if isinstance(o, list):
        return [strip_added(v) for v in o]
    return o


def path_of(name):
    return os.path.join(ROOT, 'build', '%s_fixture.json' % name)


def load(name):
    raw = open(path_of(name), encoding='utf-8').read()
    fx = json.loads(raw)
    if json.dumps(fx) != raw:
        raise SystemExit('%s: the file does not re-serialise byte-for-byte' % name)
    return raw, fx


def apply_unit(fx, u, res):
    seed, seq = u['get'](fx)
    seed['keytab'] = res['keytab']
    for i, row in enumerate(seq):
        row['keys'] = res['keys'][i]
        row['kemp'] = res['kemp'][i]


def apply_settle(fx, res):
    for w, r in zip(fx['windows'], res['windows']):
        w['keytab'] = r['keytab']
        for fr in w['frames']:
            fr['keys'] = [r['key']]
            fr['kemp'] = 0


def prove_and_write(name, raw, fx, new, backup, write):
    old = json.loads(raw)
    if strip_added(new) != strip_added(old):
        raise SystemExit('%s: an existing field changed' % name)
    # a file this tool already re-keyed must come out IDENTICAL (a re-run is a
    # verification); a file that was never re-keyed must have no field named
    # like an added one, or strip_added would hide a change to it
    if strip_added(old) != old and new != old:
        raise SystemExit('%s: already re-keyed, and the re-derived keys differ' % name)
    s = json.dumps(new)
    if json.loads(s) != new:
        raise SystemExit('%s: round-trip failed' % name)
    if write:
        os.makedirs(backup, exist_ok=True)
        dst = os.path.join(backup, '%s_fixture.json' % name)
        if not os.path.exists(dst):
            shutil.copy2(path_of(name), dst)
        with open(path_of(name), 'w', encoding='utf-8', newline='') as f:
            f.write(s)
        if json.loads(open(path_of(name), encoding='utf-8').read()) != new:
            raise SystemExit('%s: re-read after write differs' % name)
    return len(s) - len(raw)


def main(argv):
    write = '--write' in argv
    backup = None
    if '--backup' in argv:
        backup = argv[argv.index('--backup') + 1]
    if write and not backup:
        raise SystemExit('--write needs --backup DIR (the originals are copied there first)')
    names = [a for a in argv if not a.startswith('--') and a != backup]
    U = units()
    order = []
    for u in U:
        if u['name'] not in order:
            order.append(u['name'])
    order.append('settle')
    if names:
        order = [n for n in order if n in names]
    report = {}
    log = lambda s: print(s, flush=True)                 # noqa: E731
    for name in order:
        raw, fx = load(name)
        new = copy.deepcopy(fx)
        if name == 'settle':
            res = rekey_settle(fx, log)
            if not res['ok']:
                report[name] = res
                log('%-9s NOT REPRODUCED: %s' % (name, res['why']))
                continue
            apply_settle(new, res)
            grow = prove_and_write(name, raw, fx, new, backup, write)
            report[name] = dict(ok=True, rows=res['rows'], windows=len(res['windows']),
                                keytab=' '.join('%02X' % b for b in res['windows'][0]['keytab']),
                                keytabs_equal=len({tuple(w['keytab']) for w in res['windows']}) == 1,
                                searched=0, grew=grow)
            log('%-9s reproduced %d frames over %d windows; keytab %s; +%d bytes%s'
                % (name, res['rows'], len(res['windows']), report[name]['keytab'], grow,
                   ' WRITTEN' if write else ''))
            continue
        allok, parts = True, []
        for u in [u for u in U if u['name'] == name]:
            res = rekey_unit(u, fx, log)
            parts.append((u, res))
            if not res['ok']:
                allok = False
                log('%-9s %-9s NOT REPRODUCED at row %s: %s'
                    % (name, u['label'], res['row'], res['why']))
        if not allok:
            report[name] = dict(ok=False, parts={u['label']: r for u, r in parts})
            continue
        for u, res in parts:
            apply_unit(new, u, res)
        grow = prove_and_write(name, raw, fx, new, backup, write)
        report[name] = dict(ok=True, grew=grow, parts={})
        for u, res in parts:
            kt = ' '.join('%02X' % b for b in res['keytab'])
            report[name]['parts'][u['label']] = dict(
                rows=res['rows'], searched=res['searched'], changed=res['changed'],
                runs=res['tries'], keytab=kt, sel=res['sel'], amb=res['amb'])
            log('%-9s %-9s reproduced %4d rows; %d rows needed search (%d frames changed '
                'from the inversion, %d runs); keytab %s; select P1=$%s P2=$%s; ambiguous %s'
                % (name, u['label'], res['rows'], res['searched'], res['changed'], res['tries'],
                   kt, 'B605' if res['sel'][0] else 'B5FD', 'B605' if res['sel'][1] else 'B5FD',
                   res['amb']))
        log('%-9s existing fields identical; +%d bytes%s' % (name, grow, ' WRITTEN' if write else ''))
    ok = all(r['ok'] for r in report.values())
    print('ALL REPRODUCED' if ok else 'SOME FIXTURES NOT REPRODUCED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
