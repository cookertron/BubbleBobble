"""THE BOSS ON THE PAGE'S OWN PATH -- the owner, 2026-10-11: "the boss doesn't move and hitting it once with a lightning
bolt kills it straight away".  Measured where the page plays it: the REAL LOAD (passacc's world and keys, lrfree's drive:
boot.pkl's $F5BC, the keys put in at each ISR's end) with ($8609) = $4F and ($FECD) = 1 poked at the END of the ISR
labelled POKE, so $8D12 advances to round 80 -- $72A2's JP nc,$79A2 (the boss setup), the build, the round start, the
spawn, the boss's play.  POKE is 1000: by then the comparator pair $A98F / $A990 has decayed to NOP / NOP (play from
frame ~550, 429 frames to $A990's zero -- bossdamage's 'decay').  Poked at 600 the boss's $A969 still executes the
decaying pair, and the machine crashes 271 frames after the spawn (scratch-measured; the engine keeps its own
comparator, bossAxis -- DECLARED there).

RUNS (each recorded at every ISR end from the poke, labelled as lrfree labels them -- the frame the ISR was taken in):
  quiet  no keys after passacc's script.  'bodies' every BODY: [the frame of its entry $AA0E, then at $AA29 (both bounces
         done) Y, X, dx, dy] -- the entry's frame, because the erase before the bounces can cross a frame boundary;
         'spawn' the frame of $A84D (the spawn's tail jump from $A9F9); 'e7e85' the first frame of $7E80's long path
         ($7E85..: contended code the engine does not time -- DECLARED, paMiss: the frames of the bodies after it drift,
         their positions do not); 'hp' [L, ($9F62), ($79A3)] at each ISR end to the round start + 2
  bolt   the same, and at the end of the ISR labelled BOLT (between two bodies) a lightning bolt poked into slot $FDEE --
         sprite $A37D, X = boss X * 8, Y = (boss Y - 2) * 8 (inside $9F29's accept set), +7 = $80 (live, moving left):
         'rows' [L, ($9F62), bolt X, bolt +7] at each ISR end to BOLT + SPAN, and 'hits' every $9F51 (a hit) frame.
         THE MACHINE: ONE HIT, 42 -> 41 -- the boss moves on and the bolt flies.  A hit skips the bolt's own physics
         ($9F57 returns to $9EE7, past $9ED0), so a bolt dwells while it is aligned: the port's boss, whose velocities
         were never laid down ($AA47 / $AA48: tapereads' census), stood still and took all 42
  kill   as bolt, with ($9F62) = 1 poked with the bolt: the hit kills -- $8E55's death and its three busy waits, the
         advance to round 81 ($79A2 again: the seed's second RLCA into the HP), round 81's start; 'rows' [L, ($8609),
         ($9F62), ($79A3)] at each ISR end to KILL_END
  seed   as quiet to SEED_END, with ($79A3) = $85 poked with the round: $79A4's RLCA carries bit 7 into bit 0 ($0B), which
         the shipped seed reaches only on its sixth boss build ($05 $0A $14 $28 $50 $A0 -> $41)

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).

Usage:  python tools/bossfree.py [capture|verify]  -> build/bossfree_fixture.json  (~20 s, four workers)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
import ctrlmenu as cm
from harness import PC, T, IFF, SP
from passacc import SCRIPT

FIXTURE = 'build/bossfree_fixture.json'
POKE = 1000                 # ($8609) = $4F, ($FECD) = 1 at this ISR's end
QUIET_END = 1400            # the quiet run's last ISR
BOLT = 1117                 # the bolt's ISR: bodies at 1116 and 1119 on the machine, the engine's the same
SPAN = 44                   # the bolt run's rows: BOLT .. BOLT + SPAN
KILL_END = 1540             # past round 81's start ($98B2 at 1532)
SEED_END = 1070             # past round 80's start ($98B2 at 1067)
SEED = 0x85                 # the seed run's ($79A3): bit 7 set
SLOT = 0xFDEE


class Fail(Exception):
    pass


def run(kind):
    h, m, r = cm.world('boot')
    seq = cm.expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr, poked, body = 0, False, None, None, False, None
    end = {'quiet': QUIET_END, 'bolt': BOLT + SPAN, 'kill': KILL_END, 'seed': SEED_END}[kind]
    out = {'bodies': [], 'spawn': None, 'e7e85': None, 'hp': [], 'rows': [], 'hits': [], 'start': None}
    cm.keys(h, keyf(0))
    while True:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if in_scan:
                pending = keyf(L)
            else:
                cm.keys(h, keyf(L))
            if L == POKE:
                m[0x8609] = 0x4F
                m[0xFECD] = 1
                poked = True
                if kind == 'seed':
                    m[0x79A3] = SEED
            if kind in ('bolt', 'kill') and L == BOLT:
                bx, by = m[0xA8DB], m[0xA839]
                if not by:
                    raise Fail('%s: no boss at the bolt\'s ISR %d' % (kind, L))
                m[SLOT], m[SLOT + 1] = 0x7D, 0xA3
                m[SLOT + 5] = (bx * 8) & 0xFF
                m[SLOT + 6] = ((by - 2) * 8) & 0xFF
                m[SLOT + 7] = 0x80
                if kind == 'kill':
                    m[0x9F62] = 1
            if poked:
                if out['start'] is None or L <= out['start'] + 2:
                    out['hp'].append([L, m[0x9F62], m[0x79A3]])
                if kind == 'bolt' and L >= BOLT:
                    out['rows'].append([L, m[0x9F62], m[SLOT + 5], m[SLOT + 7]])
                if kind == 'kill' and L >= BOLT:
                    out['rows'].append([L, m[0x8609], m[0x9F62], m[0x79A3]])
                if L >= end:
                    return kind, out
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in cm.GUARD:
            raise Fail('%s: PC $%04X, the 128K driver' % (kind, pc))
        if pc == 0xF7B8:
            in_scan = True
        if poked and isr is None:
            if pc == 0xAA0E:
                body = frame                      # the body's frame is its ENTRY's: the erase can cross a boundary
            elif pc == 0xAA29:
                out['bodies'].append([body, m[0xA839], m[0xA8DB], m[0xAA47], m[0xAA48]])
            elif pc == 0xA84D and out['spawn'] is None and m[0x8609] == 0x50:
                out['spawn'] = frame
            elif pc == 0x7E85 and out['e7e85'] is None:
                out['e7e85'] = frame
            elif pc == 0x9F51:
                out['hits'].append(frame)
            elif pc == 0x98B2 and out['start'] is None:
                out['start'] = frame              # round 80's start: $98B2 LD ($9F62),A
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b0, s0 = r[PC], r[SP]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))


def capture():
    with ProcessPoolExecutor(4) as ex:
        res = dict(ex.map(run, ['quiet', 'bolt', 'kill', 'seed']))
    q, b, k, sd = res['quiet'], res['bolt'], res['kill'], res['seed']
    print('quiet: spawn %s, %d bodies, $7E85 %s, round start %s, hp %s' % (
        q['spawn'], len(q['bodies']), q['e7e85'], q['start'], sorted({x[1] for x in q['hp']})), flush=True)
    print('bolt: hits %s, hp %d -> %d' % (b['hits'], b['rows'][0][1], b['rows'][-1][1]), flush=True)
    print('kill: hits %s, rounds %s, hp at the end %d, $79A3 %s' % (
        k['hits'], sorted({x[1] for x in k['rows']}), k['rows'][-1][2], sorted({x[3] for x in k['rows']})), flush=True)
    print('seed: $%02X -> ($79A3, $9F62) %s' % (SEED, sorted({(x[2], x[1]) for x in sd['hp']})), flush=True)
    return {'meta': {'tool': 'tools/bossfree.py', 'no_rom_bytes': True,
                     'note': 'the boss on the real load\'s path: its bodies, a bolt\'s hit, the kill and round 81'},
            'poke': POKE, 'bolt_at': BOLT, 'span': SPAN, 'quiet_end': QUIET_END, 'kill_end': KILL_END, 'seed_end': SEED_END,
            'seed': SEED,
            'script': [[n, k_] for n, k_ in SCRIPT], 'runs': res}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture()))
        print('verify:', 'MATCH' if old == new else 'DIFFER')
        return 0 if old == new else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
