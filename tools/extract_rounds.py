#!/usr/bin/env python3
"""
extract_rounds.py -- every round's platform layout, by the LIVE path (manual Q7).

The round background is not a raw bitmap; it is a packed per-round record at
$61A8 that the builder $7F62 (walker $848C -> tile drawer $824A/$8260) renders
into the clean platform-layer shadow at $E000-$F7FF (black + striped platforms; no scenery).  Rather than decode the
pack by hand, this pokes the round counter $8609 and CALLs $7F62, then dumps
the rendered shadow -- the platform ledges exactly as the game draws them (on black).

For each round it writes build/rounds/roundNN.png (the shadow bitmap) and a
100-up contact sheet; it prints a non-empty-cell count per round and stops
reporting "real" rounds where the layout degenerates (past the last round the
walker reads rubbish).  Self-check: round 1 rebuilt must equal the shadow in
the live round-1 state.

Usage:
    python tools/extract_rounds.py [--state round1] [--max 99] [--build-entry 0x7F62]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness                                        # noqa: E402
import screen as scr                                               # noqa: E402
from PIL import Image                                              # noqa: E402

SHADOW = 0xE000            # background byte for display D is at D + $A000; $E000 = display $4000
SHADOW_LEN = 0x1800        # 6144 bytes = one screen bitmap


def render_shadow(mem):
    """The 6144-byte shadow bitmap as a 256x192 image (uniform bright-white ink)."""
    buf = bytearray(0x10000)
    buf[0x4000:0x5800] = mem[SHADOW:SHADOW + SHADOW_LEN]
    buf[0x5800:0x5B00] = b'\x47' * 0x300       # bright white on black, so the shape shows
    return scr.render(buf, 0x4000, 0x5800)


def cells_set(mem):
    return sum(1 for b in mem[SHADOW:SHADOW + SHADOW_LEN] if b)


def main():
    args = sys.argv[1:]
    state = 'round1'
    rmax = 90
    entry = 0x7F62
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--max':
            rmax = int(args[1], 0); del args[:2]
        elif args[0] == '--build-entry':
            entry = int(args[1], 0); del args[:2]
        else:
            sys.exit(f'extract_rounds: unknown argument {args[0]}')
    statepath = portconfig.state_path(state)
    outdir = portconfig.path('build/rounds')
    os.makedirs(outdir, exist_ok=True)

    h = Harness(deck=False)
    # self-check: round 1 rebuilt vs the live shadow already in round1
    h.load_state_file(statepath)
    live_r1 = bytes(h.memobj.m[SHADOW:SHADOW + SHADOW_LEN])

    tiles = []
    counts = []
    for r in range(1, rmax + 1):
        h.load_state_file(statepath)             # fresh live context each round
        h.memobj.m[0x8609] = r                   # poke the round counter
        sent, dt, steps = h.call(entry, interrupts=False)
        m = h.memobj.m
        n = cells_set(m)
        counts.append((r, n, sent))
        img = render_shadow(m)
        img.save(os.path.join(outdir, f'round{r:02d}.png'))
        tiles.append(img)
        # a real round fills ~1500-4300 cells; past the last round the walker reads
        # rubbish and the count spikes.  Stop after two consecutive out-of-band rounds.
        if len(counts) >= 2 and all(c > 4400 or c < 1200 for _, c, _ in counts[-2:]):
            print(f'round {r}: layout degenerate -- stopping (past the last round)')
            break
        if r == 1:
            rebuilt = bytes(m[SHADOW:SHADOW + SHADOW_LEN])
            same = rebuilt == live_r1
            print(f'self-check: round 1 rebuilt {"==" if same else "!="} the live round-1 shadow'
                  f' ({sum(a==b for a,b in zip(rebuilt, live_r1))}/{SHADOW_LEN} bytes)')

    # contact sheet: 10 columns
    cols = 10
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (tw // 3 + 4), rows * (th // 3 + 4)), (30, 30, 30))
    for i, img in enumerate(tiles):
        small = img.resize((tw // 3, th // 3))
        sheet.paste(small, ((i % cols) * (tw // 3 + 4), (i // cols) * (th // 3 + 4)))
    sheet.save(os.path.join(outdir, 'contact.png'))

    print(f'\nrendered {len(tiles)} rounds to {outdir} (+ contact.png)')
    print('round : non-empty cells : call-exit')
    for r, n, sent in counts:
        flag = '' if n > 40 else '   <- degenerate (past the last round?)'
        print(f'  {r:3d} : {n:5d} : sentinel {sent}{flag}')


if __name__ == '__main__':
    main()
