"""The PER-ROUND BUBBLE DRIFT FIELD -> build/drift_field.json.

Bits 6 and 7 of each colour-shadow cell are a static per-round drift direction,
read by $B846's RLCA x3 / AND 6 into a code of 0/2/4/6 that indexes $B8DB.

*** THIS IS A DECLARED ASSET STANDING IN FOR A ROUTINE. ***  The painter is
$7C57-$7E4A -- three fixed rectangles, a per-round compressed stream at $79AF
with sixteen $Fx redirects, a mirror, four doors and a rotating pattern table --
and it is NOT transliterated yet.  So the FIELD is captured from the machine, one
768-cell map per round at two bits a cell (192 bytes), exactly as $5D00's item
bank is carried until its builder is found.  WHEN THE PAINTER LANDS, DELETE THIS,
do not keep it as a cross-check.

The rounds are reached with F0's chained recipe, because poking $8609 is not a
round sample.

    python tools/extract_drift.py
"""
import sys, json, base64
sys.path.insert(0, 'tools')
import roundclass as RC

MAP, MAP_N = 0xF800, 0x300
OUT = 'build/drift_field.json'


def main():
    h, m = RC.new()
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    fields = {}
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        cs = [(m[MAP + i] >> 6) & 3 for i in range(MAP_N)]
        out = bytearray()
        for i in range(0, MAP_N, 4):
            b = 0
            for k in range(4):
                b |= cs[i + k] << (2 * k)
            out.append(b)
        fields[str(m[RC.ROUND])] = base64.b64encode(bytes(out)).decode()
    if len(fields) != 81:
        raise SystemExit('expected 81 rounds, got %d' % len(fields))
    d = {'note': __doc__.strip(), 'map_at': MAP, 'map_n': MAP_N,
         'bits_per_cell': 2, 'rounds': 81, 'field': fields}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: %d rounds x %d bytes' % (OUT, len(fields), MAP_N // 4))


if __name__ == '__main__':
    main()
