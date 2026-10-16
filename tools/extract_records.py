"""M7.7-H7 -- the round-record table and its size bitmap, as a port asset.

The 81 maps are 4,299 bytes of BIT STREAM at $61A8 selected by an 11-byte size
bitmap at $8543.  Both are TAPE DATA: byte-identical in build/image_tape.bin and
build/image.bin and unwritten over 300 frames of play in eight states, so they
are extracted once and shipped as DECODED DATA (house rule 7: build/*.json is
fine, build/*.bin is not).

READ FROM image_tape.bin, NOT image.bin (TRAPS #43): image.bin is a round-80
dump.  The two are asserted identical over both ranges before anything is
written, and the extraction refuses on an all-zero range -- which is the guard
that was NOT enough in H0, so the sizes are checked as well.

Usage:  python tools/extract_records.py
"""
import sys, json, base64, hashlib
sys.path.insert(0, 'tools')

TABLE = 0x61A8
BITMAP, BITMAP_N = 0x8543, 11
SHORT_N, LONG_N = 0x27, 0x4D
OUT = 'build/round_records.json'


def main():
    tape = bytearray(open('build/image_tape.bin', 'rb').read())
    live = bytearray(open('build/image.bin', 'rb').read())

    if tape[BITMAP:BITMAP + BITMAP_N] != live[BITMAP:BITMAP + BITMAP_N]:
        raise SystemExit('the size bitmap differs between the two images')
    if not any(tape[BITMAP:BITMAP + BITMAP_N]):
        raise SystemExit('the size bitmap is all zero -- wrong image (TRAPS #47)')

    # the table's LENGTH is a consequence of the bitmap, so derive it, never
    # guess it: 51 x 39 + 30 x 77 = 4299
    n_short = sum((tape[BITMAP + (i >> 3)] >> (7 - (i & 7))) & 1 for i in range(81))
    length = n_short * SHORT_N + (81 - n_short) * LONG_N
    if (n_short, length) != (51, 4299):
        raise SystemExit('bitmap gives %d short / %d bytes -- expected 51 / 4299'
                         % (n_short, length))
    if tape[TABLE:TABLE + length] != live[TABLE:TABLE + length]:
        raise SystemExit('the record table differs between the two images')
    if not any(tape[TABLE:TABLE + length]):
        raise SystemExit('the record table is all zero -- wrong image')

    rec = bytes(tape[TABLE:TABLE + length])
    bm = bytes(tape[BITMAP:BITMAP + BITMAP_N])
    json.dump({
        'note': ('M7.7-H7: the 81 round records as ONE CONTINUOUS BIT STREAM each '
                 '(22 rows x 14 or 28 bits, no per-row alignment) and the 11-byte '
                 'size bitmap that selects between them.  Bit (7 - (i & 7)) of byte '
                 '$8543 + (i >> 3) SET means a 39-byte record painted 14 wide and '
                 'MIRRORED; clear means 77 bytes painted 28 wide.'),
        'at': TABLE, 'len': length, 'b64': base64.b64encode(rec).decode(),
        'md5': hashlib.md5(rec).hexdigest(),
        'bitmap_at': BITMAP, 'bitmap_len': BITMAP_N,
        'bitmap_b64': base64.b64encode(bm).decode(),
        'n_short': n_short, 'n_long': 81 - n_short,
        'short_n': SHORT_N, 'long_n': LONG_N,
    }, open(OUT, 'w'), indent=1)
    print('wrote %s: %d bytes at $%04X (%d short + %d long), bitmap %d bytes at $%04X'
          % (OUT, length, TABLE, n_short, 81 - n_short, BITMAP_N, BITMAP))


if __name__ == '__main__':
    main()
