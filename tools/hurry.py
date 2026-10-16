# -*- coding: utf-8 -*-
"""M7.19 -- $9037, THE HURRY-UP TRIGGER: a one-shot built out of THREE operands,
an ISR-gate dance, a border flash and the enemies' temper.

The seventeenth chain entry ($8D4F).  It is tested every pass and does its work
ONCE:

  (a) THE CLOCK IS A THRESHOLD COMPARE, NOT A COUNTDOWN.  `LD DE,($8DBD) /
      LD HL,($745C) / OR A / SBC HL,DE / RET nc` -- ($745C) is TAPE DATA and
      reads $03E8, so the banner fires when the sixteen-bit frame clock passes
      ONE THOUSAND.
  (b) THREE OPERANDS, NOT A FLAG BYTE.  $9049 and $904D are the operands of two
      `LD A,n` instructions, and $90AA is a third: the first is a permanent
      disable, the second latches "already fired" and diverts every later pass
      to $917C, and the third makes the enemies' temper a one-shot INSIDE the
      one-shot.
  (c) IT TURNS BOTH ISR GATES OFF AND BACK ON, and not symmetrically: $9052
      clears ($FEC5) then ($FEC4), $90A1 sets both, and then $90B1 clears
      ($FEC4) ALONE around $90C1 before $90B8 sets both again.
  (d) $995A IS NOT A TEXT PRINTER.  It is `OR $40 / LD (HL),A / INC L / DJNZ` --
      ten ATTRIBUTE cells, BRIGHT forced on.  The banner's glyphs come from the
      SPECTRUM ROM charset through $802E/$8044, which this project does not
      ship; the FLASH is pure data and is measured here.

Usage:  python tools/hurry.py            (capture)
        python tools/hurry.py --jobs 15
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, T, F, SP
import portconfig as pc

FIXTURE = 'build/hurry_fixture.json'
BRANCH_BYTE = 0x8DC4
TRIG = 0x9037
ANGER = 0x90C1
WALK = 0x90DA
BORIS = 0x9250
TARGET = 0x914B
TICK = 0x917C             # the per-frame Boris chase -- M7.20
THRESH = 0x745C
CLOCK = 0x8DBD
ROUND = 0x8609
OP_DISABLE = 0x9049       # the operand of $9048 LD A,n
OP_FIRED = 0x904D         # the operand of $904C LD A,n
OP_ANGER = 0x90AA         # the operand of $90A9 LD A,n
OP_COLOUR = 0x9077        # the operand of $9076 LD A,n -- 6 XOR 5 -> 3
OP_SIDE = 0x914C          # the operand of $914B LD A,n -- the P1/P2 toggle
BANNER_PTR = 0x9A04
G4, G5 = 0xFEC4, 0xFEC5
ENEMIES = 0xFD9B
SLOTS = 0xAA57
ATTRS = 0x5800
STATE = 'round1_48'


def new(state=STATE):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = r[SP]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[SP] = sp
    r[PC] = addr
    return sp


def run(h, limit=40 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])


def ready(m, clock=None):
    """A world the trigger will fire in: the clock past the threshold, both
       latches clear, a sane round.

       *** THE THRESHOLD IS LIVE STATE, NOT TAPE DATA. ***  build/image.bin
       holds $03E8 at $745C and round1_48 holds $05DC, so a fixture that hard-
       codes 1000 measures the tape and not the game.  The clock is taken from
       whatever the state's own threshold is."""
    if clock is None:
        clock = ((m[THRESH] | (m[THRESH + 1] << 8)) + 1) & 0xFFFF
    m[ROUND] = 0x03
    m[CLOCK] = clock & 0xFF
    m[CLOCK + 1] = (clock >> 8) & 0xFF
    m[OP_DISABLE] = 0
    m[OP_FIRED] = 0
    m[OP_ANGER] = 0


# ------------------------------------------------------------ (a) the clock
def phase_clock():
    h, m = new()
    thresh = m[THRESH] | (m[THRESH + 1] << 8)
    tape = None
    try:
        import io as _io
        img = _io.open('build/image.bin', 'rb').read()
        tape = img[THRESH] | (img[THRESH + 1] << 8)
    except Exception:
        pass
    rows = []
    for clock in (0, thresh - 1, thresh, thresh + 1, thresh + 2, 0xFFFF):
        h, m = new()
        ready(m, clock)
        arm(h, TRIG)
        run(h)
        rows.append({'clock': clock, 'fired': m[OP_FIRED] == 1})
    print('(a) THRESHOLD ($745C) = %d in round1_48 and %s on the TAPE -- it is LIVE'
          % (thresh, tape))
    print('    STATE.  The trigger fires when the clock ($8DBD) passes it: %s'
          % ' '.join('%d:%s' % (r['clock'], 'FIRE' if r['fired'] else '-')
                     for r in rows))
    return {'threshold': thresh, 'tape_threshold': tape, 'rows': rows}


# ------------------------------------------------------------ (b) the gates
def phase_gates():
    rows = []

    def one(name, pokes):
        h, m = new()
        ready(m)
        for a, v in pokes.items():
            m[a] = v
        before = (m[OP_FIRED], m[G4], m[G5])
        arm(h, TRIG)
        run(h)
        rows.append({'case': name, 'fired': m[OP_FIRED] == 1,
                     'fired_before': before[0], 'boris7': m[BORIS + 7]})

    one('ready', {})
    one('...round $50 (the boss)', {ROUND: 0x50})
    one('...the DISABLE operand $9049 set', {OP_DISABLE: 1})
    one('...ALREADY FIRED ($904D set)', {OP_FIRED: 1})
    print('(b) GATES: %s'
          % '; '.join('%s -> %s' % (r['case'], 'FIRED' if r['fired'] and
                                    not r['fired_before'] else '-')
                      for r in rows))
    return rows


# ----------------------------------------------------- (c) the ISR gate dance
def phase_gatedance():
    h, m = new()
    ready(m)
    h.memobj.watch(G4, G5 + 1)
    h.memobj.log.clear()
    arm(h, TRIG)
    run(h)
    log = [[p, a, v] for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    print('(c) ISR GATES, in order: %s'
          % ' '.join('$%04X:($%04X):=%d' % (p, a, v) for (p, a, v) in log))
    print('    end state ($FEC4, $FEC5) = (%d, %d)' % (m[G4], m[G5]))
    return {'log': log, 'end': [m[G4], m[G5]]}


# --------------------------------------------------------- (d) border + flash
def phase_flash():
    h, m = new()
    ready(m)
    h.ports.record_writes = True
    h.ports.writes = []
    h.memobj.watch(ATTRS, 0x5B00)
    h.memobj.log.clear()
    arm(h, TRIG)
    run(h)
    outs = [o[2] & 0x07 for o in h.ports.writes if (o[1] & 0xFF) == 0xFE]
    log = list(h.memobj.log)
    h.memobj.unwatch()
    by995a = [w for w in log if 0x995A <= w[0] <= 0x9960]
    cells = sorted(set(a for (_, a, _) in by995a))
    vals = sorted(set(v for (_, _, v) in by995a))
    #  how many times did $995A run from the FLASH site ($907D) as against the
    #  banner's own recolour ($994A)?
    print('(d) BORDER: %d OUTs, values %s' % (len(outs), sorted(set(outs))))
    print('    $995A wrote %d attribute cells, %d distinct: $%04X..$%04X, values %s'
          % (len(by995a), len(cells), min(cells), max(cells),
             ' '.join('$%02X' % v for v in vals)))
    return {'border': outs, 'flash_writes': len(by995a),
            'cells': ['%04X' % a for a in cells],
            'values': vals, 'attr_total': len(log)}


# ------------------------------------------------------------- (e) the anger
def phase_anger():
    h, m = new()
    ready(m)
    m[SLOTS] = 6                       # four enemy slots
    for k in range(4):
        p = (ENEMIES + 12 * k) & 0xFFFF
        m[p] = 0x80
        m[(p - 2) & 0xFFFF] = 0xFF     # +5, all bits set
    h.memobj.watch(0xFD90, 0xFE00)
    h.memobj.log.clear()
    arm(h, ANGER)
    run(h)
    log = [[p, a, v] for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    print('(e) ANGER $90C1: %d writes -- %s'
          % (len(log), ' '.join('$%04X:=$%02X' % (a, v) for (_, a, v) in log)))
    return {'log': log, 'slots': m[SLOTS]}


def phase_anger_stride():
    """THE STRIDE IS TWELVE FROM +5, WHICH IS TEN FROM +7.  `SET 2,(HL)` at +7,
       two DECs to +5, `AND $F8`, then `ADD HL,12`.  Swept over slot counts."""
    rows = []
    for n in (2, 3, 5, 9):
        h, m = new()
        ready(m)
        m[SLOTS] = n
        for k in range(16):
            p = (ENEMIES + 10 * k) & 0xFFFF
            m[p] = 0x00
            m[(p - 2) & 0xFFFF] = 0xFF
        h.memobj.watch(0xFD90, 0xFE00)
        h.memobj.log.clear()
        arm(h, ANGER)
        run(h)
        touched = sorted(set(a for (_, a, _) in h.memobj.log))
        h.memobj.unwatch()
        rows.append({'slots': n, 'writes': len(h.memobj.log),
                     'addrs': ['%04X' % a for a in touched]})
    print('(e) STRIDE: %s'
          % '; '.join('($AA57)=%d -> %d writes at %s'
                      % (r['slots'], r['writes'], ','.join(r['addrs'][:6]))
                      for r in rows))
    return rows


# ------------------------------------------------- (f) Boris and his target
def phase_boris():
    rows = []
    for p1, p2, name in ((0xE1, 0x60, 'P1 only'), (0x61, 0xE0, 'P2 only'),
                         (0xE1, 0xE0, 'both'), (0x61, 0x60, 'neither')):
        h, m = new()
        ready(m)
        m[0xFD87] = p1
        m[0xFD91] = p2
        m[OP_SIDE] = 0
        arm(h, TRIG)
        run(h)
        rows.append({'case': name, 'p1': p1, 'p2': p2,
                     'rec': [m[BORIS + i] for i in range(10)],
                     'x91F8': m[0x91F8] | (m[0x91F9] << 8),
                     'x921C': m[0x921C] | (m[0x921D] << 8),
                     'side': m[OP_SIDE]})
    print('(f) BORIS: $9250 after the trigger, and the TARGET operands')
    for r in rows:
        print('      %-8s rec %s  ($91F8) = $%04X  ($921C) = $%04X  toggle %d'
              % (r['case'], ' '.join('%02X' % v for v in r['rec']),
                 r['x91F8'], r['x921C'], r['side']))
    return rows


# --------------------------------------------------------- (g) the banner
def phase_banner():
    """The walker's shape: how many iterations, where $9A04 ends, how many
       times the ROM-charset printer runs, and the write census."""
    h, m = new()
    ready(m)
    start = m[BANNER_PTR] | (m[BANNER_PTR + 1] << 8)
    h.memobj.watch(0x4000, 0x5B00)
    h.memobj.log.clear()
    arm(h, TRIG)
    seen = {}
    n = 0
    while n < 40 * 10 ** 6:
        h.step(1, interrupts=False)
        p = h.regs[PC]
        if p in (0x802E, 0x9904, 0x9940, 0x995A, 0x90DA, 0x804F):
            seen[p] = seen.get(p, 0) + 1
        if p in h.SENTINELS:
            break
        n += 1
    log = list(h.memobj.log)
    h.memobj.unwatch()
    disp = [a for (_, a, _) in log if a < ATTRS]
    attr = [a for (_, a, _) in log if a >= ATTRS]
    end = m[BANNER_PTR] | (m[BANNER_PTR + 1] << 8)
    print('(g) BANNER: $9A04 $%04X -> $%04X (%d steps of 2); entries %s'
          % (start, end, (start - end) // 2,
             ' '.join('$%04X x%d' % (k, v) for k, v in sorted(seen.items()))))
    print('    writes: %d display over %d cells, %d attribute over %d'
          % (len(disp), len(set(disp)), len(attr), len(set(attr))))
    return {'ptr_start': start, 'ptr_end': end, 'calls': {'%04X' % k: v
                                                          for k, v in seen.items()},
            'display': len(disp), 'display_cells': len(set(disp)),
            'attrs': len(attr), 'attr_cells': len(set(attr)),
            'steps': n}


def phase_writers():
    """THE WRITE CENSUS BY PC, so the ROM-dependent half can be separated from
       the rest.  $802E/$804F is the SPECTRUM ROM CHARSET printer and this
       project ships no ROM; $9904's erase, $9940's recolour and $995A's flash
       are all pure data and the port can do every one of them."""
    h, m = new()
    ready(m)
    h.memobj.watch(0x4000, 0x5B00)
    h.memobj.log.clear()
    arm(h, TRIG)
    run(h)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    pcs = {}
    for (p, a, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
    rom = sum(v for k, v in pcs.items() if 0x8000 <= int(k, 16) < 0x8100)
    print('(i) WRITERS: %s'
          % ' '.join('$%s x%d' % (k, v)
                     for k, v in sorted(pcs.items(), key=lambda kv: -kv[1])[:10]))
    print('    ROM-charset printer ($80xx) wrote %d of %d' % (rom, len(log)))
    return {'pcs': pcs, 'total': len(log), 'rom_writes': rom}


def phase_operands():
    """EVERY OPERAND OF THE HURRY SYSTEM, on the tape and in each state.

    *** $9077 IS LIVE STATE. ***  The port seeds the tape value; a fixture that
    hard-codes one is measuring a moment, not a rule.

    M7.114a (TRAPS #300): THE TAPE IS build/image_tape.bin -- bleepload's rebuild,
    cross-checked byte for byte against the snapshot of the real loader (boot.pkl)
    -- NOT build/image.bin, mkimage's asserted postcondition, which for this
    Bleepload tape holds $06 / $AA at $9077 / $9194 where the loaded game has
    $03 / $04 (the real load carries them to the first pass of play)."""
    import io as _io
    img = _io.open('build/image_tape.bin', 'rb').read()
    ops = [(0x9049, 'disable'), (0x904D, 'fired'), (0x90AA, 'temper'),
           (0x9077, 'flash_colour'), (0x9102, 'walker_mode'),
           (0x914C, 'side'), (0x9194, 'tick_counter'), (0x9160, 'reset_flag'),
           (0x9250, 'boris_sprite_lo'), (0x9251, 'boris_sprite_hi')]
    out = {'tape': {n: img[a] for a, n in ops}, 'states': {}}
    for st in ('round1_48', 'r20_48', 'play1p48', 'hurryup', 'boss'):
        try:
            h, m = new(st)
        except (Exception, SystemExit):
            continue
        out['states'][st] = {n: m[a] for a, n in ops}
    print('(m) OPERANDS: tape %s'
          % ' '.join('%s=$%02X' % (n, v) for n, v in out['tape'].items()))
    for st, d in out['states'].items():
        diff = [n for n in d if d[n] != out['tape'][n]]
        print('      %-12s differs from the tape in %s' % (st, diff or 'NOTHING'))
    return out


def phase_footprint():
    """WHERE each writer writes, not merely how often.  A count cannot tell an
       eight-row erase from a seven-row one, nor an erase at the position the
       banner is LEAVING from one at the position it is arriving at."""
    h, m = new()
    ready(m)
    h.memobj.watch(0x4000, 0x5B00)
    h.memobj.log.clear()
    arm(h, TRIG)
    run(h)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    out = {}
    for pc, name in ((0x9910, 'erase_display'), (0x9932, 'erase_attrs'),
                     (0x995C, 'attr_run'), (0x8052, 'rom_glyphs')):
        rows = [(a, v) for (p, a, v) in log if p == pc]
        addrs = sorted(set(a for a, _ in rows))
        out[name] = {'pc': '%04X' % pc, 'writes': len(rows),
                     'cells': len(addrs),
                     'lo': '%04X' % addrs[0], 'hi': '%04X' % addrs[-1],
                     'first16': ['%04X' % a for a, _ in rows[:16]],
                     'all': ['%04X' % a for a in addrs],
                     'values': sorted(set(v for _, v in rows))[:8],
                     'by_value': {str(v): sum(1 for _, w in rows if w == v)
                                  for v in sorted(set(v for _, v in rows))[:8]}}
    print('(l) FOOTPRINT, by writer')
    for k, v in out.items():
        print('      %-14s $%s  %5d writes over %4d cells, $%s..$%s; first %s'
              % (k, v['pc'], v['writes'], v['cells'], v['lo'], v['hi'],
                 ' '.join(v['first16'][:6])))
    return out


def phase_speaker():
    """EVERY OUT ($FE), with its T offset and its FULL value.  $908D's $10 is
       BIT 4 -- the SPEAKER -- not a border colour, so the `border flash` is a
       120-step PULSE TRAIN and M7.15's edge machinery is what plays it."""
    h, m = new()
    ready(m)
    h.ports.record_writes = True
    h.ports.writes = []
    arm(h, TRIG)
    t0 = h.regs[T]
    run(h)
    outs = [[o[0] - t0, o[2]] for o in h.ports.writes if (o[1] & 0xFF) == 0xFE]
    lvl = [1 if (v & 0x10) else 0 for _, v in outs]
    edges = [outs[i] for i in range(len(outs))
             if i == 0 or lvl[i] != lvl[i - 1]]
    gaps = [outs[i + 1][0] - outs[i][0] for i in range(len(outs) - 1)]
    print('(j) SPEAKER: %d OUTs, values %s; %d are EDGES'
          % (len(outs), sorted(set(v for _, v in outs)), len(edges)))
    print('    gaps: min %d, max %d, distinct %d; span %d T (%.1f frames)'
          % (min(gaps), max(gaps), len(set(gaps)), outs[-1][0] - outs[0][0],
             (outs[-1][0] - outs[0][0]) / 69888.0))
    return {'outs': outs, 'edges': edges, 'levels': lvl,
            'gap_min': min(gaps), 'gap_max': max(gaps),
            'span': outs[-1][0] - outs[0][0]}


def phase_string():
    h, m = new()
    b = []
    a = 0x9A1C
    while m[a] and len(b) < 24:
        b.append(m[a])
        a += 1
    print('(k) STRING at $9A1C: %r (%d chars, terminated by $%02X)'
          % (''.join(chr(c) for c in b), len(b), m[a]))
    return {'bytes': b, 'text': ''.join(chr(c) for c in b)}


# ------------------------------------------------------------- (h) the cost
def phase_cost():
    rows = []
    for name, pokes in (('fires', {}), ('declines on the round', {ROUND: 0x50}),
                        ('declines on the clock', {CLOCK: 0, CLOCK + 1: 0}),
                        ('already fired', {OP_FIRED: 1})):
        h, m = new()
        ready(m)
        for a, v in pokes.items():
            m[a] = v
        arm(h, TRIG)
        t0 = h.regs[T]
        run(h)
        rows.append({'case': name, 'T': h.regs[T] - t0})
    print('(h) COST: %s' % '; '.join('%s %d T' % (r['case'], r['T']) for r in rows))
    return rows


def capture(jobs=15):
    out = {}
    out['clock'] = phase_clock()
    out['gates'] = phase_gates()
    out['gatedance'] = phase_gatedance()
    out['flash'] = phase_flash()
    out['anger'] = phase_anger()
    out['anger_stride'] = phase_anger_stride()
    out['boris'] = phase_boris()
    out['banner'] = phase_banner()
    out['writers'] = phase_writers()
    out['operands'] = phase_operands()
    out['footprint'] = phase_footprint()
    out['speaker'] = phase_speaker()
    out['string'] = phase_string()
    out['cost'] = phase_cost()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--operands' in a:                      # M7.114a: re-measure that phase alone, into the fixture
        fx = json.load(open(FIXTURE))
        fx['operands'] = phase_operands()
        json.dump(fx, open(FIXTURE, 'w'), indent=1)
        print('wrote %s operands' % FIXTURE)
        sys.exit(0)
    j = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 15
    capture(j)
