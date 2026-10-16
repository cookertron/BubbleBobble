"""$727B -- the ROUND SPAWNER.  Oracle and verification.

Called once per round from $9866.  It clears the entity table, walks the round's
16-byte record in the $7491 spawn table, and stands up one entity per enemy:

  $727B  save $FD87/$FD91 (the two players' flag bytes), clear $FD80..$FDD9,
         LDIR 16 bytes $95F3 -> $7581, restore the player flags
  $729D  round = ($8609); CP $50 -> rounds >= 80 divert to the boss setup $79A2
  $72A5  HL = $7491 + round*16;  walk up to 7 two-byte entries, stopping at the
         first whose X byte is 0;  count = 7 - B
  $72C4  ($AA57) = count + 2    -- the two PLAYER slots.  (The CP 9 clamp at
         $72C6 is DISABLED: its JR displacement is 0, so it jumps to the store
         it was meant to guard.  count maxes at 7 so $AA57 maxes at 9, which is
         exactly why $A3AD clears bit 5 on NINE slots.)
  $72D0  ($743E) = 0 / $64 / 4 by which players are active
  $72F0  per enemy, into slots 2, 3, 4, ... :
           SET 7,(IY+7)                      active
           (IY+4) = ($73AF) += $5D           a rolling stagger, so enemies do
                                             not move in lockstep
           (IY+5) = byte0 & $F8              X
           (IX+$10) = byte0 & 7              type -> the $B552 behaviour list
           (IY+6) = byte1 & $F8              Y
           JP ($73B0 + 2*type)               the per-type initialiser, which
                                             sets the sprite pointer +0/+1 and
                                             the facing bits of +7
  $7336  then, for each enemy, COPY its Y into $73A6[i] and ZERO (IY+6): the
         enemies drop in from the top of the screen and the $B54B settler walks
         them down to their target rows.

Usage:  python tools/spawn.py capture
        python tools/spawn.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness
import portconfig as pc

SPAWN = 0x727B
TABLE, STRIDE, SLOTS = 0xFD80, 10, 12
SPAWN_TABLE = 0x7491
COUNT = 0xAA57
TARGET_Y = 0x73A6          # one byte per enemy: the row it descends to
ANIM_SEED = 0x73AF         # rolls by $5D per enemy spawned
BEHAV = 0xB552             # the behaviour-pointer list; +$10 per slot holds the type
FIXTURE = 'build/spawn_fixture.json'
STATE = 'round1_48'
BRANCH_BYTE = 0x8DC4
MAX_ROUND = 79             # 80 and 81 divert to the boss setup $79A2


def new():
    h = Harness()
    h.load_state_file(pc.state_path(STATE))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{STATE}: not the 48K branch (TRAPS #28/#36)')
    return h, m


def spawn(h, m, round_no, p1=True, p2=False, seed=0):
    m[0x8609] = round_no
    m[0xFD87] = 0xC1 if p1 else 0x00
    m[0xFD91] = 0xC1 if p2 else 0x00
    m[ANIM_SEED] = seed
    h.call(SPAWN)
    return {
        'round': round_no, 'p1': p1, 'p2': p2, 'seed': seed,
        'table': [m[TABLE + i] for i in range(SLOTS * STRIDE)],
        'count': m[COUNT], 'n_enemies': m[0x7460],
        'target_y': [m[TARGET_Y + i] for i in range(8)],
        'anim_seed': m[ANIM_SEED],
        'players_byte': m[0x743E],
        'behav': [m[BEHAV + i] for i in range(0x20)],
        # the tail $7356-$73A5: the per-enemy WAKE-UP DELAYS and the round timers
        'delays': [m[0xA891 + i] for i in range(8)],
        'hold': m[0x745A], 'round_timer': m[0x745C] | (m[0x745D] << 8),
        'seed_73ae': m[0x73AE],
    }


def capture():
    rows = []
    for r in range(1, MAX_ROUND + 1):
        h, m = new()
        rows.append(spawn(h, m, r))
    # the player-dependent byte, and a non-zero rolling seed
    extra = []
    for (p1, p2, seed, label) in ((True, True, 0, 'both_players'),
                                  (False, True, 0, 'p2_only'),
                                  (True, False, 0x40, 'seed_40'),
                                  (True, False, 0xF0, 'seed_F0_wraps')):
        h, m = new()
        row = spawn(h, m, 1, p1, p2, seed)
        row['label'] = label
        extra.append(row)
    h, m = new()
    tbl = [m[SPAWN_TABLE + i] for i in range(16 * (MAX_ROUND + 1))]
    # $738D: byte14 & 7 of the round record picks one of eight 8-byte delay
    # patterns starting at $7461 -- which overlaps the spawn table itself.
    pat = [m[0x7461 + i] for i in range(0x30)]
    fx = {'note': __doc__.strip().split('\n\n')[1].replace('\n', ' '),
          'state': STATE, 'spawn_table_at': SPAWN_TABLE, 'stride': 16,
          'max_round': MAX_ROUND, 'anim_step': 0x5D,
          'spawn_table': tbl,
          'table_b64': base64.b64encode(bytes(tbl)).decode(),
          'pattern_at': 0x7461,
          'pattern_b64': base64.b64encode(bytes(pat)).decode(),
          'delay_table_at': 0xA891, 'delay_bias': 0x1E,
          'enemy_sprite': {str(t): [None, None] for t in range(8)},
          'rounds': rows, 'variants': extra}
    json.dump(fx, open(FIXTURE, 'w'), indent=1)
    tot = sum(r['n_enemies'] for r in rows)
    print(f'wrote {FIXTURE}: {len(rows)} rounds, {tot} enemies, {len(extra)} variants')


def analyse():
    """what does each per-type initialiser leave in +0/+1 and +7?"""
    fx = json.load(open(FIXTURE))
    seen = {}
    for row in fx['rounds']:
        for k in range(2, SLOTS):
            b = k * STRIDE
            if not (row['table'][b + 7] & 0x80):
                continue
            i = k - 2
            byte0 = fx['spawn_table'][row['round'] * 16 + 2 * i]
            byte1 = fx['spawn_table'][row['round'] * 16 + 2 * i + 1]
            t = byte0 & 7
            spr = row['table'][b] | (row['table'][b + 1] << 8)
            key = (t, row['table'][b + 7] & 7)
            seen.setdefault(key, set()).add((spr, byte1 & 7))
    print(f'{"type":>4s} {"+7&7":>5s}  sprite(s)      from byte1&7')
    for (t, f7) in sorted(seen):
        vals = sorted(seen[(t, f7)])
        print(f'{t:4d} {f7:5d}  ' + ', '.join(f'${s:04X}<-{b}' for s, b in vals))


def verify():
    fx = json.load(open(FIXTURE))
    bad = 0
    for row in fx['rounds']:
        # a FRESH state per round, exactly as capture() did: $73A6 and the
        # behaviour list keep whatever the previous round left, on the machine
        # as much as in the engine, so reusing one harness compares a round
        # against a tail it never wrote.
        h, m = new()
        got = spawn(h, m, row['round'], row['p1'], row['p2'], row['seed'])
        for k in ('table', 'count', 'n_enemies', 'target_y', 'anim_seed', 'players_byte',
                  'behav', 'delays', 'hold', 'round_timer', 'seed_73ae'):
            if got[k] != row[k]:
                bad += 1
                print(f"  round {row['round']}: {k} differs")
                break
    print(f'-> {len(fx["rounds"]) - bad}/{len(fx["rounds"])} rounds reproduce')
    return bad


if __name__ == '__main__':
    v = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if v == 'capture':
        capture()
    elif v == 'analyse':
        analyse()
    else:
        sys.exit(1 if verify() else 0)
