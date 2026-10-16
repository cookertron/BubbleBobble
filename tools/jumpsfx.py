# -*- coding: utf-8 -*-
"""M7.15 -- $8FA5, THE JUMP TONE: the first sound the port makes.

The chain's FIRST entry ($8D25) and the only one whose entire output is
`OUT ($FE)`.  Its shape is unusual enough to be worth measuring rather than
reading:

  * It is TWO CALLS THAT ARE ONE.  `$8FA5 LD HL,$FDDA / CALL $8FAE` then
    `$8FAB LD HL,$FDE4` and FALLS THROUGH into $8FAE -- so P2's tone is not a
    call site and a caller scan finds one, not two.
  * THE PITCH COMES OUT OF THE PLAYER'S ANIMATION BYTE, through a table.
    (base+9) indexes $B57D, whose entries are the signed range $FC..$04, and
    E = |entry - $10| + 1.  That maps the nine table values onto E = 13..21 and
    nothing else, which is why build/sfx/ holds exactly jump_E13..jump_E21.
  * $8FBB `INC A / RET z` then `DEC A / RET z` rejects BOTH $FF and $00, and
    the `LD L,A / LD H,0` at $8FCE is DEAD -- HL is never read again.
  * The generator is `B = 2` cycles of (speaker $30, delay E, speaker 0,
    delay E), so FOUR edges, and the two half-periods DIFFER: the second
    carries the DJNZ and the reload, 20 T more than the first.

Usage:  python tools/jumpsfx.py            (capture)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, T
import portconfig as pc

FIXTURE = 'build/jumpsfx_fixture.json'
BRANCH_BYTE = 0x8DC4
TONE = 0x8FA5
INNER = 0x8FAE
TABLE = 0xB57D
P1, P2 = 0xFD80, 0xFD8A
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
    sp = r[12]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def play(entry=TONE, p1=None, p2=None, state=STATE):
    """One $8FA5 with both player slots poked; returns the edge log and cost."""
    h, m = new(state)
    for base, fields in ((P1, p1), (P2, p2)):
        if fields is None:                      # leave this player OUT of play
            m[base + 7] &= 0x7F
            continue
        flags, anim, dying = fields
        m[base + 7] = flags
        m[base + 9] = anim
        pb = base + 0x5A
        m[pb] = (m[pb] & ~0x04) | (0x04 if dying else 0x00)
    h.ports.record_writes = True
    h.ports.writes = []
    arm(h, entry)
    t0 = h.regs[T]
    h.run_until(h.SENTINELS, limit=4 * 10 ** 6, stride=1, interrupts=False)
    if h.regs[PC] not in h.SENTINELS:
        raise SystemExit('bad bracket -- PC $%04X' % h.regs[PC])
    cost = h.regs[T] - t0
    edges = [[o[0] - t0, o[2] & 0x38] for o in h.ports.writes
             if (o[1] & 0xFF) == 0xFE]
    return edges, cost


# --------------------------------------------------------------- (a) the map
def phase_table():
    """EVERY (base+9) value 0..255 -> does it sound, and with what E?"""
    h, m = new()
    tab = [m[TABLE + i] for i in range(256)]
    rows = []
    for anim in range(256):
        edges, cost = play(p1=(0xE1, anim, False))
        rows.append({'anim': anim, 'edges': len(edges), 'cost': cost,
                     'half1': (edges[1][0] - edges[0][0]) if len(edges) > 1 else 0,
                     'half2': (edges[2][0] - edges[1][0]) if len(edges) > 2 else 0})
    sound = [r for r in rows if r['edges']]
    halves = sorted(set(r['half1'] for r in sound))
    #  the derived E, from the half-period the machine actually produced
    es = sorted(set((hp - 10) // 16 for hp in halves))
    print('(a) TABLE: %d of 256 animation bytes sound; first half-periods %s'
          % (len(sound), halves))
    print('    -> E = (half1 - 10) / 16 = %s' % es)
    silent = [r['anim'] for r in rows if not r['edges']]
    print('    SILENT: %s%s' % (silent[:8], ' ...' if len(silent) > 8 else ''))
    return {'rows': rows, 'table': tab, 'sounding': len(sound),
            'halves': halves, 'E': es, 'silent': silent}


# -------------------------------------------------------------- (b) the arms
def phase_arms():
    """The three RETs, each driven both ways."""
    cases = [
        ('P1 in play, anim 1, alive', dict(p1=(0xE1, 1, False)), True),
        ('P1 DYING (+$5A bit 2)', dict(p1=(0xE1, 1, True)), False),
        ('P1 not in play (+7 bit 7 clear)', dict(p1=(0x61, 1, False)), False),
        ('P1 anim $FF ($8FBB INC A / RET z)', dict(p1=(0xE1, 0xFF, False)), False),
        ('P1 anim $00 ($8FBD DEC A / RET z)', dict(p1=(0xE1, 0x00, False)), False),
        ('P2 ALONE -- the FALL-THROUGH at $8FAB',
         dict(p1=None, p2=(0xE0, 1, False)), True),
        ('BOTH players sounding', dict(p1=(0xE1, 1, False), p2=(0xE0, 1, False)), True),
        ('NEITHER in play', dict(p1=None, p2=None), False),
    ]
    rows = []
    for name, kw, want in cases:
        edges, cost = play(**kw)
        rows.append({'case': name, 'edges': len(edges), 'cost': cost,
                     'sounds': bool(edges), 'expected': want})
    print('(b) ARMS')
    for r in rows:
        print('      %-42s %d edges, %4d T  %s'
              % (r['case'], r['edges'], r['cost'],
                 'ok' if r['sounds'] == r['expected'] else '** UNEXPECTED'))
    return rows


# ------------------------------------------------------- (c) the edge stream
def phase_edges():
    """The complete stream for every reachable E, from $8FA5 (not $8FD4)."""
    seen = {}
    for anim in range(256):
        edges, cost = play(p1=(0xE1, anim, False))
        if not edges:
            continue
        e = (edges[1][0] - edges[0][0] - 10) // 16
        if e not in seen:
            seen[e] = {'E': e, 'anim': anim, 'cost': cost,
                       'edges': edges,
                       'half1': edges[1][0] - edges[0][0],
                       'half2': edges[2][0] - edges[1][0]}
    print('(c) EDGES, measured from $8FA5')
    for e in sorted(seen):
        r = seen[e]
        print('      E=%2d (anim %3d)  %4d T  halves %d/%d  %s'
              % (e, r['anim'], r['cost'], r['half1'], r['half2'],
                 r['edges']))
    return [seen[e] for e in sorted(seen)]


def phase_domain():
    """WHAT (base+9) ACTUALLY TAKES -- DRIVEN, and the jump key SWEPT for.

    The anim sweep above walks 0..255 and so reads past the 32-byte table at
    $B57D into the one at $B59D.  The DOMAIN is what the game puts there, and
    varmap calls $FD89 the jump-phase byte: 0 grounded, 1..32 the arc, $FF
    falling.  That is a claim, so it is driven: all forty keys held in turn for
    40 frames, and the (P1+9) values each produces recorded.  The key that
    makes the byte leave 0 is the jump key, and the set it visits is the domain
    the tone is defined over -- which is exactly the set $8FBB's two RETs
    ($FF and $00) carve out of.
    """
    from keyprobe import KEYS, press
    rows = []
    for (name, sel, bit) in KEYS:
        h, m = new()
        seen = {}
        h.ports.release_all()
        press(h.ports, name)
        for _ in range(40):
            h.run_frames(1)
            v = m[P1 + 9]
            seen[v] = seen.get(v, 0) + 1
        rows.append({'key': name, 'values': sorted(seen),
                     'max': max(seen), 'left_zero': sorted(seen) != [0]})
    movers = [r for r in rows if r['left_zero']]
    print('(f) DOMAIN: %d of 40 keys move (P1+9) off 0 -- %s'
          % (len(movers), ', '.join(r['key'] for r in movers) or 'NONE'))
    for r in movers:
        vs = r['values']
        print('      %-6s visits %d values, %s..%s%s'
              % (r['key'], len(vs), vs[0], vs[-1],
                 '  (includes $FF)' if 255 in vs else ''))
    #  40 frames is not a whole arc: hold the mover for 200 and watch the byte
    #  climb to the top of the table and then become $FF.
    longrun = {}
    if movers:
        h, m = new()
        h.ports.release_all()
        press(h.ports, movers[0]['key'])
        for _ in range(200):
            h.run_frames(1)
            v = m[P1 + 9]
            longrun[v] = longrun.get(v, 0) + 1
        lv = sorted(longrun)
        print('      %s held for 200 frames: %d values, %s..%s%s'
              % (movers[0]['key'], len(lv), lv[0], lv[-1],
                 '  -- and $FF, the FALL' if 255 in lv else ''))
    #  and the union over the whole sweep, which is the domain
    union = sorted(set(list(longrun) + [v for r in rows for v in r['values']]))
    arc = [v for v in union if 1 <= v <= 32]
    print('    DOMAIN over all forty: %d values, arc entries %s..%s (%d of them)'
          % (len(union), arc[0] if arc else '-', arc[-1] if arc else '-', len(arc)))
    return {'rows': rows, 'union': union, 'arc': arc,
            'longrun': {str(k): v for k, v in longrun.items()},
            'movers': [r['key'] for r in movers], 'frames': 40}


def phase_both():
    """BOTH players sounding: one stream or two, and where does P2's start?"""
    edges, cost = play(p1=(0xE1, 1, False), p2=(0xE0, 8, False))
    print('(d) BOTH: %d edges, %d T -- %s' % (len(edges), cost, edges))
    return {'edges': edges, 'cost': cost}


def phase_cost():
    """What the tone COSTS the pass, sounding against silent -- the number a
       port must not invent, and the reason it is only declared here."""
    silent, cs = play(p1=None, p2=None)
    one, c1 = play(p1=(0xE1, 1, False))
    two, c2 = play(p1=(0xE1, 1, False), p2=(0xE0, 1, False))
    print('(e) COST: silent %d T, one tone %d T, two %d T (delta %d / %d)'
          % (cs, c1, c2, c1 - cs, c2 - cs))
    return {'silent': cs, 'one': c1, 'two': c2}


def capture():
    out = {}
    out['table'] = phase_table()
    out['arms'] = phase_arms()
    out['edges'] = phase_edges()
    out['domain'] = phase_domain()
    out['both'] = phase_both()
    out['cost'] = phase_cost()
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
