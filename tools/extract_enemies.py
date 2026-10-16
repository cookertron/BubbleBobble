#!/usr/bin/env python3
"""
extract_enemies.py -- the per-round enemy spawn table (phase 5.3 of the manual).

The spawner reads it at `$72A5`: `LD A,($8609)` (round, 1-based); `CP $50` (rounds
>=80 branch to the boss setup `$79A2`); else `HL = $7491 + round*16` (16 bytes per
round). It walks up to 7 enemies (`$72B3 LD B,7`), each **2 bytes**:

    byte0 = (X & $F8) | (type & 7)      type indexes the 8-entry jump table $73B0
    byte1 = (Y & $F8) | (facing & 7)    the low 3 bits seed the initial facing

stopping at the first entry with X==0.  Type -> behaviour routine + sprite bank
(read from the $73B0 initialisers, see docs/SPEC.md Entities):

    0 $C100  1 $D040  2 $CD80  3 $C260  4 $C3C0  5 $CAC0  6 $D500  7 $C680

Writes build/enemies.json ({round: [{type,x,y,facing}], types:{...}}).

Self-check: round 1 decodes to 3x type 0 (matches the live round-1 slots, which
draw sprite $C100), and every decoded type is in 0-7.

Usage:  python tools/extract_enemies.py
"""
import os
import sys
import json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portconfig                                                   # noqa: E402

TABLE = 0x7491
STRIDE = 16
MAXR = 79                    # rounds 1..79 use the table; 80,81 = boss ($79A2)
MAXE = 7                     # $72B3 LD B,7
BANK = {0: 0xC100, 1: 0xD040, 2: 0xCD80, 3: 0xC260,
        4: 0xC3C0, 5: 0xCAC0, 6: 0xD500, 7: 0xC680}


def decode(img):
    rounds = {}
    for r in range(1, MAXR + 1):
        base = TABLE + r * STRIDE
        ens = []
        for i in range(0, MAXE * 2, 2):
            b0, b1 = img[base + i], img[base + i + 1]
            if (b0 & 0xF8) == 0:
                break
            ens.append({'type': b0 & 7, 'x': b0 & 0xF8, 'y': b1 & 0xF8, 'facing': b1 & 7})
        rounds[r] = ens
    return rounds


def main():
    img = open(portconfig.path('build/image.bin'), 'rb').read()
    rounds = decode(img)

    # self-check + invariants
    r1 = rounds[1]
    assert len(r1) == 3 and all(e['type'] == 0 for e in r1), f'round 1 != 3x type0: {r1}'
    alltypes = [e['type'] for ens in rounds.values() for e in ens]
    assert all(0 <= t <= 7 for t in alltypes), 'a type escaped 0-7'
    counts = Counter(len(e) for e in rounds.values())
    assert min(len(e) for e in rounds.values()) >= 3, 'a round has < 3 enemies'

    types = {}
    first = {}
    tc = Counter(alltypes)
    for ens in rounds.values():
        for e in ens:
            first.setdefault(e['type'], None)
    for r in range(1, MAXR + 1):
        for e in rounds[r]:
            if first.get(e['type']) is None:
                first[e['type']] = r
    for t in range(8):
        types[t] = {'bank': f'${BANK[t]:04X}', 'first_round': first.get(t), 'spawns': tc[t]}

    out = {'stride': STRIDE, 'table': f'${TABLE:04X}', 'rounds': rounds, 'types': types,
           'total': len(alltypes)}
    json.dump(out, open(portconfig.path('build/enemies.json'), 'w'), indent=1)
    print(f'self-check PASS: round1 = 3x type0; all types in 0-7; per-round counts {dict(sorted(counts.items()))}')
    print(f'{len(alltypes)} enemies across rounds 1-{MAXR}; type first-appearances: '
          + ", ".join(f"t{t}@r{types[t]['first_round']}" for t in range(8)))
    print('-> build/enemies.json')


if __name__ == '__main__':
    main()
