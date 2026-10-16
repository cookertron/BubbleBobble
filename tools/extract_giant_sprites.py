"""THE GIANT / BOSS SPRITE BANKS at $C080 and $FE02 -> build/giant_sprites.json.

$A84D (bossSpawn) points the self-modified source of $A8C1's draw ($A8C2) at one of three banks by the giant's
TYPE c = A - 1 ($A85C): c = 0 -> $5B00, c = 2 -> $C080, anything else -> $FE02.  Each is 128 bytes: $A8C1 draws four
character rows of eight pixel rows of four bytes (four LDIs a row).  $5B00 lies in the cold start's relocated block
(build/reloc.json), which the port already lays down -- so the candy cane drew; $C080 (the giant PEACH, A = 3 from
$8F26) and $FE02 (A = 4 -- the BOSS, from $A9F9's tail jump) were never in the port's RAM and drew zeros.

THESE ARE TAPE BYTES: build/image_tape.bin holds them, and ASSERTED here they are byte-identical in the live saved
states that carry them (peachfall: $A8C2 = $C080; boss: $A8C2 = $FE02) and in the others checked -- nothing writes
either range in play.

    python tools/extract_giant_sprites.py
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness
import portconfig as pc

OUT = 'build/giant_sprites.json'
BANKS = [(0xC080, 128), (0xFE02, 128)]
STATES = ['peachfall', 'boss', 'peachspawn', 'fallcandy', 'round1_48']


def main():
    tap = open('build/image_tape.bin', 'rb').read()
    for at, n in BANKS:
        if not any(tap[at:at + n]):
            raise SystemExit('$%04X: the tape image is all zeros -- wrong source' % at)
    for st in STATES:
        h = Harness(); h.load_state_file(pc.state_path(st)); m = h.memobj.m
        for at, n in BANKS:
            if bytes(m[at:at + n]) != tap[at:at + n]:
                raise SystemExit('%s: $%04X..$%04X differs from the tape image' % (st, at, at + n - 1))
    d = {'note': __doc__.strip(), 'states_agreeing': STATES,
         'blocks': [{'at': at, 'n': n, 'b64': base64.b64encode(tap[at:at + n]).decode()} for at, n in BANKS]}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: %s, each equal to the tape image in %d live states' %
          (OUT, ', '.join('$%04X..$%04X' % (a, a + n - 1) for a, n in BANKS), len(STATES)))


if __name__ == '__main__':
    main()
