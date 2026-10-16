# -*- coding: utf-8 -*-
"""M7.10 -- $806C, THE LIVES ICONS: the sixth method written, gated in isolation
and never called.

M7.8-A promoted it onto the round-advance path at $7F5B and found only a COUNTED
STUB there; M7.8-A's live-sequence gate has been masking row 23 columns 0..4 as
a declared gap ever since.  livesIcons(), livesRow() and livesCell() are all
transliterated already.  What was missing is the STATE they read: reset() leaves
($FD87), ($FD91), ($FDDC) and ($FDE6) at ZERO, and $8097's `RET p` means a
player whose +7 bit 7 is clear draws nothing at all -- so wiring the icons
without the state would have drawn an empty row and looked like success.

Usage:  python tools/livespanel.py            (capture)
        python tools/livespanel.py verify
"""
import sys, json, zlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FIXTURE = 'build/livespanel_fixture.json'
BRANCH_BYTE = 0x8DC4
PANEL = 0x806C
DISPLAY, DISPLAY_END = 0x4000, 0x5B00
SHADOW, SHADOW_END = 0xE000, 0xFB00
#  *** THE SHADOW IS A WINDOW, NOT A HALF OF MEMORY. ***  $80C0 writes the byte
#  it just drew to display + $A000, so the shadow $806C touches is exactly
#  $E000..$FB00 -- and the first version of this tool excluded `a >= 0xE000`,
#  which swallowed the whole of the game's working RAM with it.  ($FD87),
#  ($FD91), ($FDDC) and ($FDE6) -- the four addresses this increment EXISTS for,
#  the ones reset() left at zero -- were therefore missing from its own
#  "measured input set", and nothing noticed until a structural check asked
#  which test-only fixtures no check reads (TRAPS #116).
SP_PIN = [0]


def new(state='round1_48'):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP_PIN[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = SP_PIN[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def run(h, sp, limit=20 * 10 ** 6):
    h.run_until(h.SENTINELS, limit=limit, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])


def phase_inputs():
    """EVERY ADDRESS $806C READS, outside its own code.  This is the list the
       port must seed, and it is measured rather than guessed -- reset() had
       four of them at zero and $8097's RET p would have drawn nothing."""
    h, m = new()
    reads = {}
    orig_get = type(h.memobj).__getitem__

    def spy(self, a):
        if isinstance(a, int):
            reads[a] = reads.get(a, 0) + 1
        return orig_get(self, a)
    type(h.memobj).__getitem__ = spy
    try:
        sp = arm(h, PANEL)
        run(h, sp)
    finally:
        type(h.memobj).__getitem__ = orig_get
    #  exclude the routine's OWN code and the display/shadow it writes; what is
    #  left is the state it consumes -- which is the list reset() must seed.
    outside = {('%04X' % a): {'n': n, 'value': m[a]}
               for a, n in reads.items()
               if not (0x8000 <= a < 0x8200)
               and not (DISPLAY <= a < DISPLAY_END)
               and not (SHADOW <= a < SHADOW_END)
               and a >= 0x5B00}
    return {'reads_outside_its_code': dict(sorted(outside.items())),
            'total_distinct_reads': len(reads)}


def phase_writes():
    """WHAT IT DRAWS, on the shipped states, as an ordered write log."""
    out = {}
    for st in ('round1_48', 'r20_48', 'play1p48'):
        try:
            h, m = new(st)
        except Exception:
            continue
        h.memobj.watch(DISPLAY, 0x10000)
        sp = arm(h, PANEL)
        run(h, sp)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        pcs = {}
        for (p, a, v) in log:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        cells = sorted(set(a for (_, a, _) in log if DISPLAY <= a < DISPLAY_END))
        out[st] = {'writes': len(log), 'writer_pcs': pcs,
                   'lo': '%04X' % min(cells), 'hi': '%04X' % max(cells),
                   'display_crc': zlib.crc32(bytes(m[DISPLAY:DISPLAY_END])) & 0xFFFFFFFF,
                   'p1_lives': m[0xFDDC], 'p2_lives': m[0xFDE6],
                   'p1_flags': m[0xFD87], 'p2_flags': m[0xFD91]}
    return out


def phase_lives():
    """THE ICON ROW FOR EVERY LIFE COUNT, both players, in play and not.
       $809E clamps at 5 and $8097's RET p is the in-play gate, so the sweep
       drives 0..7 AND both sides of bit 7."""
    rows = []
    for who, flags_at, lives_at in (('P1', 0xFD87, 0xFDDC), ('P2', 0xFD91, 0xFDE6)):
        for inplay in (True, False):
            for lives in range(8):
                h, m = new()
                m[0xFD87] &= 0x7F
                m[0xFD91] &= 0x7F
                if inplay:
                    m[flags_at] |= 0x80
                m[lives_at] = lives
                h.memobj.watch(DISPLAY, DISPLAY_END)
                sp = arm(h, PANEL)
                run(h, sp)
                log = list(h.memobj.log)
                h.memobj.unwatch()
                rows.append({'who': who, 'inplay': inplay, 'lives': lives,
                             'writes': len(log),
                             'cells': sorted(set('%04X' % a for (_, a, _) in log
                                                 if a >= 0x5800))})
    return rows


def capture():
    fx = {'note': __doc__.strip(), 'panel_at': PANEL,
          'inputs': phase_inputs(), 'writes': phase_writes(),
          'lives': phase_lives()}
    json.dump(fx, open(FIXTURE, 'w'), sort_keys=True)
    verify(fx)
    return fx


def verify(fx=None):
    fx = fx or json.load(open(FIXTURE))
    i = fx['inputs']
    print('\n$806C READS %d distinct addresses; outside its own code:'
          % i['total_distinct_reads'])
    for a, v in i['reads_outside_its_code'].items():
        print('   $%s  x%-3d  = $%02X' % (a, v['n'], v['value']))
    print('\nWRITES:')
    for st, r in fx['writes'].items():
        print('   %-10s %3d writes from %s, $%s..$%s  (lives %d/%d flags $%02X/$%02X)'
              % (st, r['writes'], sorted(r['writer_pcs']), r['lo'], r['hi'],
                 r['p1_lives'], r['p2_lives'], r['p1_flags'], r['p2_flags']))
    L = fx['lives']
    print('\nLIVES SWEEP: %d rows' % len(L))
    for r in L:
        if r['who'] == 'P1' and r['inplay']:
            print('   P1 in play, lives %d -> %2d writes, %d attr cells'
                  % (r['lives'], r['writes'], len(r['cells'])))
    print('   NOT in play (any lives): %s'
          % sorted(set(r['writes'] for r in L if not r['inplay'])))


if __name__ == '__main__':
    (capture if (len(sys.argv) < 2 or sys.argv[1] == 'capture') else verify)()
