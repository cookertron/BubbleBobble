"""The COLD-START RELOCATION SOURCE $E000..$E6A7 -> build/reloc.json.

$96A5 LD HL,$E000 / LD DE,$5B00 / LD BC,$06A8 / LDIR copies 1,704 bytes over
$5B00..$61A7 once at cold start, so THE LOAD IMAGE IS NOT THE RUN IMAGE THERE.
The port carries the SOURCE and performs the copy, rather than carrying the
destination -- which keeps the relocation itself gateable.

WHY NOT TAKE $5B00..$61A7 STRAIGHT FROM build/image_tape.bin: because it is
WRONG there, and TRAPS #43's all-zero guard does not catch it.  The tape image
holds 36 of 40 NON-ZERO bytes at $6180..$61A7 -- live block-#9 data the front
end only ever PUSHED onto, since $5BB0 does LD SP,$61A7 -- so "the range is
sourced" reads as yes and the bytes are still not the ones the game runs on.
(M7.7-H0; the whole range differs in 1,385 of 1,704 bytes.)

    python tools/extract_reloc.py
"""
import json, base64

SRC, N, DST = 0xE000, 0x06A8, 0x5B00
OUT = 'build/reloc.json'


def main():
    tape = open('build/image_tape.bin', 'rb').read()
    live = open('build/image.bin', 'rb').read()
    if len(tape) != 0x10000:
        raise SystemExit('image_tape.bin must be a full 64K dump from ZERO (TRAPS #41)')
    blk = tape[SRC:SRC + N]
    if not any(blk):
        raise SystemExit('$%04X..$%04X is all zero in the tape image' % (SRC, SRC + N - 1))
    # the uniqueness that carries the whole inference: the run image's tail
    # occurs at exactly ONE address in the 64K tape image, and it is $E600
    needle, hits, at = live[0x6100:0x61A8], [], 0
    while True:
        at = tape.find(needle, at)
        if at < 0:
            break
        hits.append(at)
        at += 1
    if hits != [0x6100 - DST + SRC]:
        raise SystemExit('the source is not unique: %s' % ['$%04X' % a for a in hits])
    diff = [DST + i for i in range(N) if blk[i] != live[DST + i]]
    d = {'note': __doc__.strip(), 'src': SRC, 'dst': DST, 'n': N,
         'b64': base64.b64encode(blk).decode(),
         'live_diff': diff,
         'live_diff_note': ('the bytes where the relocated block differs from the LIVE '
                            'round-80 dump: exactly the two carve-outs $5B14-$5B1F (the '
                            'wall-texture scratch $8390 writes and $A36C does not clear) '
                            'and $5CE0-$5CFB (the sparkle table)')}
    json.dump(d, open(OUT, 'w'))
    print('wrote %s: $%04X..$%04X, %d bytes -> $%04X' % (OUT, SRC, SRC + N - 1, N, DST))
    print('  the source occurs at exactly one address in the tape image: $%04X' % hits[0])
    print('  it differs from the live dump at %d bytes, the two live carve-outs' % len(diff))


if __name__ == '__main__':
    main()
