# -*- coding: utf-8 -*-
"""M7.16 -- $A824, THE GIANT OBJECT, and the ONCE-PER-FRAME GATE THAT IS AN
OPERAND.

The twelfth chain entry ($8D46).  Three things make it worth a tool:

  (a) `$A829 LD A,($8DBD) / CP $43 / LD ($A82D),A / RET z` -- the $43 is the
      OPERAND OF ITS OWN COMPARE, and the store one instruction later rewrites
      it with the current frame counter.  So the routine runs ONCE PER FRAME
      however many passes the loop makes, and the state that makes it so is a
      byte inside an instruction.  A port that keeps a `lastFrame` field is
      right; a port that reads the listing and hard-codes $43 runs never.
  (b) `$A838 LD A,9` is the SAME trick: the 9 at $A839 is the giant's row AND
      its presence flag, and $A83F writes the incremented row back into it.
  (c) Two saved states have a giant -- fallcandy and peachfall, both round 3
      with the row at $13 -- so the `$A83B CP $14` stop is ONE CALL AWAY on
      the machine, and the increment can be driven rather than reasoned about.

Usage:  python tools/giant.py            (capture)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, T
import portconfig as pc

FIXTURE = 'build/giant_fixture.json'
BRANCH_BYTE = 0x8DC4
GIANT = 0xA824
ROW_OP = 0xA839            # the operand of $A838 LD A,n -- the row AND the flag
FRAME_OP = 0xA82D          # the operand of $A82C CP n
CLOCK = 0x8DBD
ROUND = 0x8609
STATES = ['fallcandy', 'peachfall']
CALLEES = {0xA8C1: '$A8C1 draw', 0xA9B1: '$A9B1 collide', 0xA925: '$A925 erase'}
DISPLAY, DISPLAY_END = 0x4000, 0x5B00


def new(state):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = r[12]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def call(h, watch=None):
    lo, hi = watch or (DISPLAY, 0x10000)
    h.memobj.watch(lo, hi)
    h.memobj.log.clear()
    arm(h, GIANT)
    h.run_until(h.SENTINELS, limit=8 * 10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
    log = list(h.memobj.log)
    h.memobj.unwatch()
    return log


# ------------------------------------------------- (a) the once-a-frame gate
def phase_frame_gate(state='fallcandy'):
    """FOUR CALLS IN ONE FRAME: the first works, the rest do nothing.  Then
       move ($8DBD) by hand and watch it wake up."""
    h, m = new(state)
    rows = []
    for i in range(4):
        before = (m[ROW_OP], m[FRAME_OP])
        log = call(h)
        rows.append({'call': i, 'clock': m[CLOCK], 'op_before': before[1],
                     'op_after': m[FRAME_OP], 'row_before': before[0],
                     'row_after': m[ROW_OP], 'writes': len(log)})
    #  ...and now the frame moves
    m[CLOCK] = (m[CLOCK] + 1) & 0xFF
    log = call(h)
    rows.append({'call': 'after a frame', 'clock': m[CLOCK],
                 'op_before': None, 'op_after': m[FRAME_OP],
                 'row_before': None, 'row_after': m[ROW_OP],
                 'writes': len(log)})
    print('(a) FRAME GATE on %s -- $A82D is the operand of $A82C CP n' % state)
    for r in rows:
        print('      call %-14s clock $%02X  operand -> $%02X  row -> $%02X  '
              '%5d writes' % (r['call'], r['clock'], r['op_after'],
                              r['row_after'], r['writes']))
    return rows


# --------------------------------------------------------- (b) the row walk
def phase_rows(state='fallcandy'):
    """One call per starting row, each from a fresh machine."""
    rows = []
    for row in list(range(0, 0x18)):
        h, m = new(state)
        m[ROW_OP] = row
        m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF      # make sure the frame gate opens
        log = call(h)
        rows.append({'row_in': row, 'row_out': m[ROW_OP], 'writes': len(log)})
    print('(b) ROW WALK: $A83A INC A / $A83B CP $14 / JR z,$A842')
    print('      in  -> out (writes): %s'
          % ' '.join('%d->%d(%d)' % (r['row_in'], r['row_out'], r['writes'])
                     for r in rows))
    return rows


# ------------------------------------------------------------ (c) the round
def phase_round(state='fallcandy'):
    rows = []
    for rnd in (0x01, 0x03, 0x4F, 0x50, 0x51):
        h, m = new(state)
        m[ROUND] = rnd
        m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
        log = call(h)
        rows.append({'round': rnd, 'writes': len(log), 'row_after': m[ROW_OP]})
    print('(c) ROUND: $A832 CP $50 / RET z -- writes by round: %s'
          % ' '.join('$%02X:%d' % (r['round'], r['writes']) for r in rows))
    return rows


# ------------------------------------------------------------- (d) the body
def phase_body(state='fallcandy'):
    """The ordered CALL trace and the write census of one working call."""
    h, m = new(state)
    m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
    h.memobj.watch(DISPLAY, 0x10000)
    h.memobj.log.clear()
    arm(h, GIANT)
    seen = []
    n = 0
    while n < 8 * 10 ** 6:
        h.step(1, interrupts=False)
        p = h.regs[PC]
        if p in CALLEES and (not seen or seen[-1] != p):
            seen.append(p)
        if p in h.SENTINELS:
            break
        n += 1
    log = list(h.memobj.log)
    h.memobj.unwatch()
    disp = [a for (_, a, _) in log if DISPLAY <= a < 0x5800]
    attr = [a for (_, a, _) in log if 0x5800 <= a < DISPLAY_END]
    shad = [a for (_, a, _) in log if a >= 0xE000]
    pcs = {}
    for (p, a, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
    out = {'state': state, 'writes': len(log), 'display': len(disp),
           'display_cells': len(set(disp)), 'attrs': len(attr),
           'attr_cells': len(set(attr)), 'shadow': len(shad),
           'order': [CALLEES[p] for p in seen],
           'writer_pcs': dict(sorted(pcs.items(), key=lambda kv: -kv[1])[:12]),
           'steps': n, 'row_after': m[ROW_OP]}
    print('(d) BODY on %s: %d writes -- %d display (%d cells), %d attribute '
          '(%d cells), %d shadow' % (state, out['writes'], out['display'],
                                     out['display_cells'], out['attrs'],
                                     out['attr_cells'], out['shadow']))
    print('    CALL ORDER: %s' % (' -> '.join(out['order']) or 'NONE'))
    return out


# -------------------------------------------------------- (e) the negatives
def phase_negatives(state='fallcandy'):
    rows = []
    cases = [('no giant ($A839 = 0)', {ROW_OP: 0}),
             ('same frame (the operand already matches)', {}),
             ('round $50 (the boss owns $A839)', {ROUND: 0x50})]
    for name, pokes in cases:
        h, m = new(state)
        if name.startswith('same frame'):
            m[FRAME_OP] = m[CLOCK]
        else:
            m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
        for a, v in pokes.items():
            m[a] = v
        log = call(h)
        rows.append({'case': name, 'writes': len(log)})
    print('(e) NEGATIVES: %s'
          % '; '.join('%s: %d' % (r['case'], r['writes']) for r in rows))
    return rows


# ------------------------------------------------------- (f) the award tail
TYPE_OP = 0xA85C           # the operand of $A85B LD A,n -- the giant's TYPE
AWARD_TAB = 0xA9EA         # $A9BD LD DE,$A9EA -- indexed by TYPE - 1
PENDING = 0xFFEE           # $A9C2 LD ($FFEE),A -- the score amount's high byte


def phase_award(state='fallcandy'):
    """$A9B1's tail: the award comes out of a THREE-BYTE table indexed by the
       giant's TYPE, which is itself an operand ($A85C).  And $A9D5 `POP HL`
       DISCARDS $A824's return address before `JP $8C28`, so the reveal returns
       to $A824's CALLER and the erase at $A84A NEVER RUNS."""
    h, m = new(state)
    tab = [m[AWARD_TAB + i] for i in range(3)]
    rows = []
    for ty in (1, 2, 3):
        h, m = new(state)
        m[TYPE_OP] = ty
        m[ROW_OP] = 13                       # a row where $A969 overlaps
        m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
        #  $80FA writes the PLAYER's record at $FFE1 + 4*player, not $FFE1
        #  itself -- that is the HIGH score.  Both are recorded.
        before = [m[0xFFE1 + i] for i in range(12)]
        log = call(h)
        rows.append({'type': ty, 'pending': [m[0xFFED + i] for i in range(4)],
                     'pending_hi': m[PENDING],
                     'score': [m[0xFFE1 + i] for i in range(12)],
                     'score_before': before,
                     'row_after': m[ROW_OP], 'fecc': m[0xFECC],
                     'writes': len(log)})
    print('(f) AWARD: the table at $A9EA is %s, and TYPE indexes it'
          % ' '.join('$%02X' % v for v in tab))
    for r in rows:
        d = [i for i in range(12) if r['score'][i] != r['score_before'][i]]
        print('      type %d -> HIGH %s P1 %s P2 %s (changed at $FFE1+%s), '
              '($A839) %d, ($FECC) %d, %d writes'
              % (r['type'],
                 ''.join('%02X' % v for v in r['score'][0:4]),
                 ''.join('%02X' % v for v in r['score'][4:8]),
                 ''.join('%02X' % v for v in r['score'][8:12]),
                 d, r['row_after'], r['fecc'], r['writes']))
    return {'table': tab, 'rows': rows}


def phase_no_erase(state='fallcandy'):
    """THE ERASE IS SKIPPED ON A HIT, and a PC watch is the only way to see it:
       $A9D5 POPs $A824's return address, so `JP $8C28` returns past $A84A."""
    out = {}
    for row, name in ((13, 'hit'), (3, 'miss')):
        h, m = new(state)
        m[ROW_OP] = row
        m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
        arm(h, GIANT)
        seen = []
        n = 0
        while n < 8 * 10 ** 6:
            h.step(1, interrupts=False)
            p = h.regs[PC]
            if p in (0xA8C1, 0xA9B1, 0xA925, 0x8C28, 0x80FA) and \
               (not seen or seen[-1] != p):
                seen.append(p)
            if p in h.SENTINELS:
                break
            n += 1
        names = {0xA8C1: 'draw', 0xA9B1: 'collide', 0xA925: 'erase',
                 0x8C28: 'reveal', 0x80FA: 'award'}
        out[name] = {'row': row, 'trace': [names[p] for p in seen],
                     'steps': n, 'row_after': m[ROW_OP]}
        print('(g) %-5s row %2d -> %s  (%d steps, row now %d)'
              % (name, row, ' -> '.join(out[name]['trace']), n, m[ROW_OP]))
    return out


def phase_erase(state='fallcandy'):
    """WHERE THE ERASE WRITES.  $A925 is $A929 entered one row higher, so the
       footprint is the OLD row's -- and a write COUNT cannot tell that from the
       new row's.  The addresses can."""
    out = {}
    for row in (3, 10):
        h, m = new(state)
        m[ROW_OP] = row
        m[FRAME_OP] = (m[CLOCK] + 1) & 0xFF
        m[0xA98F] = 0
        m[0xA990] = 0
        h.memobj.watch(DISPLAY, DISPLAY_END)
        h.memobj.log.clear()
        arm(h, GIANT)
        seen = []
        n = 0
        erasing = False
        while n < 8 * 10 ** 6:
            h.step(1, interrupts=False)
            p = h.regs[PC]
            if p == 0xA925:
                erasing = True
                mark = len(h.memobj.log)
            if p in h.SENTINELS:
                break
            n += 1
        log = list(h.memobj.log)
        h.memobj.unwatch()
        tail = log[mark:] if erasing else []
        cells = sorted(set(a for (_, a, _) in tail if DISPLAY <= a < 0x5800))
        out[str(row)] = {'row_in': row, 'row_out': m[ROW_OP],
                         'erase_writes': len(tail),
                         'cells': ['%04X' % a for a in cells],
                         'lo': '%04X' % cells[0], 'hi': '%04X' % cells[-1]}
    print('(i) ERASE FOOTPRINT: %s'
          % '; '.join('row %s -> %d writes over %d cells $%s..$%s'
                      % (k, v['erase_writes'], len(v['cells']), v['lo'], v['hi'])
                      for k, v in out.items()))
    return out


def phase_world():
    """THE TWO BYTES THAT MAKE EVERY POSITION AN OVERLAP.  $A98F/$A990 are live
       state inside $A97D's own control flow -- `37 C9` (SCF/RET) on the tape,
       decayed to `00 00` in play (B4).  A gate for the ROW WALK has to be in
       the machine's world or the giant hits the player on row 1."""
    out = {}
    for s in STATES:
        h, m = new(s)
        out[s] = {'A98F': m[0xA98F], 'A990': m[0xA990],
                  'p1': [m[0xFD85], m[0xFD86], m[0xFD87]],
                  'p2': [m[0xFD8F], m[0xFD90], m[0xFD91]],
                  'A8DB': m[0xA8DB], 'A8DC': m[0xA8DC],
                  'type': m[TYPE_OP]}
    print('(h) WORLD: %s'
          % '; '.join('%s $A98F/$A990 = $%02X $%02X, P1 (x %d, y %d, flags $%02X), '
                      'type %d' % (k, v['A98F'], v['A990'], v['p1'][0],
                                   v['p1'][1], v['p1'][2], v['type'])
                      for k, v in out.items()))
    return out


def capture():
    out = {'states': {}}
    for s in STATES:
        h, m = new(s)
        out['states'][s] = {'row': m[ROW_OP], 'round': m[ROUND],
                            'clock': m[CLOCK], 'frame_op': m[FRAME_OP]}
    print('THE TWO STATES WITH A GIANT: %s'
          % ', '.join('%s row $%02X round $%02X' % (k, v['row'], v['round'])
                      for k, v in out['states'].items()))
    out['frame_gate'] = phase_frame_gate()
    out['rows'] = phase_rows()
    out['round'] = phase_round()
    out['body'] = {s: phase_body(s) for s in STATES}
    out['negatives'] = phase_negatives()
    out['award'] = phase_award()
    out['no_erase'] = phase_no_erase()
    out['world'] = phase_world()
    out['erase'] = phase_erase()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
