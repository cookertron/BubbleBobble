"""M7.68 -- $AA60's T, SLOT BY SLOT: the skeleton, the handlers, the corpse flight.

The odd ISR's second half, $AA60 (the entity update), was charged a flat 8,381 T
(BB_ISR_ABSENT_AA60, the round1_48 median) whatever the population.  This oracle
brackets it by CONTROL FLOW on the machine, slot by slot:

  prologue   $AA60 -> the first $AA85 (the cadence's JR decides 150 / 152)
  slot       $AA85 -> the next $AA85 (the last slot: -> $8D8F, the final RET's 10 in it)
  run        a handler run: from the handler's entry ($AAEA RET z or $AAEB JP (HL)) to the
             next entry with SP one word up (the doubled run) or to $AAEC -- each run's T
  corpse     $8A78 entered from $AB00's CALL z -> $AB03 (its RET in it; the CALL in the slot)
  skeleton   slot - its runs - its corpse: what $AA60 itself costs, a closed function of
             the slot's flags, its delay byte, its place in the walk, its X/Y at $AB0C

and the DIVERTED pass ($AA72 JP nz,$B520) whole, on an UNcontended machine, with the bytes
it reads.  Every 48K saved state in build/, F frames, interrupts on, a key script.

  rows       undiverted passes: the seed ($FD80 table, $A891 delays and the players'
             $A98F/$A990 -- the 8-bit index reaches them -- $AA57, $AA65, the $B54E handler
             list, the $73A6 targets) and per slot the skeleton, the runs, the corpse, the slot's
             ten bytes at $AA99 and at $AB0C -- every pass whose slot skeletons include one
             not yet seen 3 times, plus the first 2 of each state
  runs       every handler run's T, CONTENDED, by handler address (a Counter)
  corpse     every corpse flight's T, CONTENDED
  diverted   uncontended diverted passes: seed and T

Usage:  python tools/aa60cost.py          (-> build/aa60cost_fixture.json)
        python tools/aa60cost.py verify   (re-measure, compare, say MATCH)
"""
import sys, os, json, collections
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
import portconfig as pc
from keyprobe import KEYMAP, keymask

FIXTURE = 'build/aa60cost_fixture.json'
STATES = ['blowbolt', 'boris', 'boriskill', 'boss', 'bosshit', 'bosskilled', 'bossspawn', 'bottle',
          'candycane', 'crown', 'crown_taken', 'death', 'elfire', 'ellight', 'elwater', 'extcomp',
          'extend', 'extn', 'fallcandy', 'fbkill', 'firekill', 'fruit', 'fruit_taken', 'hurryup',
          'lastdia81', 'lastdia82', 'peachcane', 'peachfall', 'peachspawn', 'play1p48', 'powerup',
          'r10_48', 'r20_48', 'r30_48', 'r40_48', 'r50_48', 'r60_48', 'r6_48', 'redcross',
          'round1_2p48', 'round1_48', 'spawn', 'spawn_taken', 'sweet', 'umbrella', 'water',
          'yellowcross', 'yellowcross2']
FRAMES = 300
KEYS = [['P', 'SPACE'], ['O'], [], ['SPACE', 'Q'], ['P', 'Q', 'SPACE'], ['O', 'SPACE'], ['SPACE'], []]
                                                       # 25 frames each, P1's O/P/Q/SPACE
KEY_FRAMES = 25
# FORCED runs (declared): three skeleton paths no natural run above reaches, each poked into a
# state at load and its first two passes kept as rows (never counted into the medians)
FORCED = [
    ('p2track', 'round1_2p48', ((0xFD94 + 7, lambda b: b | 0x10),)),        # slot 2 tracks P2 ($AAC5)
    ('corpse_asleep', 'r10_48', ((0xFDA8 + 7, lambda b: b | 0x08),          # slot 4 a corpse whose
                                 (0xFDA8 + 9, 0xFF))),                       #   delay is still running
    ('high_y', 'round1_48', ((0xFD8A + 6, 0xE0),)),                         # absent P2's Y >= $DC
]
FORCED_FRAMES = 6
GLO, GHI = 0xD000, 0xD300                              # $D167 guard: never run the 128K driver


def hexs(b):
    return bytes(b).hex()


def run(name, contended, pokes=(), frames=FRAMES):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(name))
    r, op, mem = h.sim.registers, h.sim.opcodes, h.sim.memory
    assert mem[0x8DC4] == 0xC9, name + ': not a 48K state'
    for a, v in pokes:
        mem[a] = v(mem[a]) if callable(v) else v
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    passes, div = [], []
    cur = pa = None
    ki, nextk = 0, r[T]
    while r[T] < t_end:
        if r[T] >= nextk:
            h.ports.release_all()
            for c in KEYS[ki % len(KEYS)]:
                h.ports.press(KEYMAP[c][0], keymask(KEYMAP[c][1]))
            ki += 1; nextk = r[T] + KEY_FRAMES * fd
        p = r[PC]
        assert not (GLO <= p < GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and p == cur[0] and r[SP] == cur[1]:
            assert pa is None, 'an ISR returned inside $AA60'
            cur = None
        if cur is not None:
            t = r[T]
            if p == 0xAA60:
                assert pa is None
                pa = {'t0': t, 'div': mem[0xB54B] != 0, 'slots': [],
                      'seed': {'tab': hexs(mem[0xFD80:0xFDF8]), 'dly': hexs(mem[0xA891:0xA89D]),
                               'dly2': hexs(mem[0xA98F:0xA991]),
                               'aa57': mem[0xAA57], 'aa65': mem[0xAA65], 'b54b': mem[0xB54B],
                               'lst': hexs(mem[0xB54E:0xB566]), 'tgt': hexs(mem[0x73A6:0x73B2])}}
            elif pa is not None:
                if p == 0x8D8F:
                    pa['tot'] = t - pa['t0']
                    if pa['slots']:
                        pa['slots'][-1]['end'] = t
                    (div if pa['div'] else passes).append(pa); pa = None
                elif p == 0xAA85:
                    if pa['slots']:
                        pa['slots'][-1]['end'] = t
                    else:
                        pa['pro'] = t - pa['t0']
                    pa['slots'].append({'t': t, 'runs': [], 'corpse': None, 'h': None})
                elif pa['slots']:
                    s = pa['slots'][-1]
                    if p == 0xAA99:
                        iy = h.iy(); s['iy'] = iy; s['visit'] = hexs(mem[iy:iy + 10])
                    elif p == 0xAB0C:
                        s['post'] = hexs(mem[s['iy']:s['iy'] + 10])
                    elif p == 0x8A78 and s.get('cs'):
                        s['c0'] = t
                    elif p == 0xAB03 and s.get('c0') is not None:
                        s['corpse'] = t - s['c0']; s['c0'] = None; s['cs'] = False
                    if s['h'] is not None and p == s['h'] and r[SP] == (s['sp'] + 2) & 0xFFFF \
                            and s.get('r0') is not None and t > s['r0']:
                        s['runs'].append(t - s['r0']); s['r0'] = t
                    elif s.get('r0') is not None and p == 0xAAEC:
                        s['runs'].append(t - s['r0']); s['r0'] = None
        acc = None
        if mem[p] == 0x76:
            t = r[T]; tt = t if t % fd < ia else (t // fd + 1) * fd; sp0 = r[SP]
            h._fast_halt()
            if r[PC] != (p + 1) & 0xFFFF:
                acc = ((p + 1) & 0xFFFF, sp0, tt)
        else:
            sp_before = r[SP]
            op[mem[p]]()
            if pa is not None and pa['slots']:
                s = pa['slots'][-1]
                if p in (0xAAEA, 0xAAEB) and r[PC] != 0xAAEB and s['h'] is None:
                    s['h'] = r[PC]; s['r0'] = r[T]
                    s['sp'] = sp_before            # the word holding the handler's address
                elif p == 0xAB00 and r[PC] == 0x8A78:
                    s['cs'] = True
            if r[IFF] and r[T] % fd < ia:
                b, spb, tt = r[PC], r[SP], r[T]
                if h.sim.accept_interrupt(r, mem, p):
                    acc = (b, spb, tt)
        if acc is not None:
            cur = acc
    return passes, div


def slot_row(s):
    skel = s['end'] - s['t'] - sum(s['runs']) - (s['corpse'] or 0)
    return [skel, s['h'] or 0, s['runs'], s['corpse'], s['visit'], s.get('post')]


def measure():
    rows, runs, corpse, diverted, seen = [], collections.defaultdict(collections.Counter), \
        collections.Counter(), [], collections.Counter()
    tile = 0
    for nm in STATES:
        P, _ = run(nm, True)
        for i, x in enumerate(P):
            sl = [slot_row(s) for s in x['slots']]
            for s in x['slots']:
                if s['h']:
                    for v in s['runs']:
                        runs['%04X' % s['h']][v] += 1
                if s['corpse'] is not None:
                    corpse[s['corpse']] += 1
            # the parts tile the whole: prologue + every slot == the bracket
            assert x['pro'] + sum(s['end'] - s['t'] for s in x['slots']) == x['tot']
            tile += 1
            keys = [(r[0], len(r[2])) for r in sl]
            if i < 2 or any(seen[k] < 3 for k in keys):
                rows.append({'state': nm, 'seed': x['seed'], 'pro': x['pro'], 'tot': x['tot'], 'slots': sl})
                for k in keys:
                    seen[k] += 1
        _, D = run(nm, False)
        for x in D:
            diverted.append({'state': nm, 'seed': x['seed'], 'tot': x['tot']})
        print(nm, len(P), 'passes,', len(D), 'diverted', file=sys.stderr)
    for tag, nm, pokes in FORCED:
        P, _ = run(nm, True, pokes, FORCED_FRAMES)
        for x in P[:2]:
            assert x['pro'] + sum(s['end'] - s['t'] for s in x['slots']) == x['tot']
            rows.append({'state': nm, 'forced': tag, 'seed': x['seed'], 'pro': x['pro'], 'tot': x['tot'],
                         'slots': [slot_row(s) for s in x['slots']]})
    return {'note': __doc__.strip().split('\n')[0], 'frames': FRAMES, 'keys': KEYS, 'key_frames': KEY_FRAMES,
            'states': STATES, 'passes_tiled': tile, 'rows': rows,
            'runs': {k: sorted([[t, n] for t, n in v.items()]) for k, v in sorted(runs.items())},
            'corpse': sorted([[t, n] for t, n in corpse.items()]), 'diverted': diverted}


if __name__ == '__main__':
    out = measure()
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        print('MATCH' if json.dumps(old, sort_keys=True) == json.dumps(out, sort_keys=True) else 'MISMATCH')
    else:
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, len(out['rows']), 'rows', out['passes_tiled'], 'passes tiled',
              len(out['diverted']), 'diverted')
