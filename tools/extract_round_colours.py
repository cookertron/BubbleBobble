#!/usr/bin/env python3
"""
extract_round_colours.py -- every round's platform layout IN ITS REAL COLOURS.

Each level has a different palette (a player who knows the original flagged it,
and it is confirmed: round 1 white-on-red, 2 cyan-on-red, 3 green-on-blue,
4 cyan-on-blue, ...).  The colour is a per-round attribute layer the round-start
sets; building a round in isolation does not reproduce it, so this drives the
GAME to advance round by round -- deactivating the enemy slots ($FD94-$FDD9)
makes the game clear the round and run its own next-round start (colour + build)
-- and captures each round as the clean platform bitmap (shadow $E000-$F7FF)
plus the real display attributes ($5800-$5AFF).

Writes build/rounds/colourNN.png per round, a colour contact sheet, and
build/round_palettes.json (the dominant platform attribute + full attr map).

Usage:
    python tools/extract_round_colours.py [--state round1] [--max 81]
"""
import os
import sys
import json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness, PC                                    # noqa: E402
import screen as scr                                               # noqa: E402
from PIL import Image                                              # noqa: E402

SHADOW = 0xE000
ENEMY_LO, ENEMY_HI = 0xFD94, 0xFDDA        # entity slots 2..8 (players are 0,1)
COL = ['black', 'blue', 'red', 'magenta', 'green', 'cyan', 'yellow', 'white']


def render_colour(m):
    """Clean platform layer (shadow bitmap) painted with the round's real attrs."""
    buf = bytearray(0x10000)
    buf[0x4000:0x5800] = m[SHADOW:SHADOW + 0x1800]
    buf[0x5800:0x5B00] = m[0x5800:0x5B00]
    return scr.render(buf, 0x4000, 0x5800)


def platform_attr(m):
    c = Counter(m[0x5840 + i] for i in range(0x2C0) if (m[0x5840 + i] >> 3) & 7)
    return c.most_common(1)[0][0] if c else 0


def advance_one(h, chunk=60, cap=16):
    """Clear the current round -> the game builds the NEXT round. Advances exactly
    ONE round (stop at the first increment; an absolute target overshoots to the
    boss round 81 if a chunk clears two rounds)."""
    m = h.memobj.m
    cur = m[0x8609]
    for _ in range(cap):
        for a in range(ENEMY_LO, ENEMY_HI):
            m[a] = 0
        h.run_frames(chunk)
        if m[0x8609] != cur:
            h.run_frames(150)                  # settle: build + colour + past the jingle start
            return m[0x8609]
    return None


def main():
    args = sys.argv[1:]
    state, rmax = 'round1', 81
    while args:
        if args[0] == '--state':
            state = args[1]; del args[:2]
        elif args[0] == '--max':
            rmax = int(args[1], 0); del args[:2]
        else:
            sys.exit(f'extract_round_colours: unknown argument {args[0]}')
    outdir = portconfig.path('build/rounds')
    os.makedirs(outdir, exist_ok=True)
    h = Harness(deck=False)
    h.load_state_file(portconfig.state_path(state))
    m = h.memobj.m

    tiles, palettes = [], {}
    first_attr = None
    for r in range(1, rmax + 1):
        if r > 1:
            got = advance_one(h)
            if got is None:
                print(f'round {r}: could not advance (stuck at {m[0x8609]}) -- stopping'); break
        rnd = m[0x8609]
        attr = platform_attr(m)
        if r == 1:
            first_attr = attr
        elif attr == first_attr and rnd != 1:
            print(f'round {rnd}: palette repeats round 1 ($%02X) -- colour cycle length = {r-1}' % attr)
            break
        palettes[rnd] = {'round': rnd, 'platform_attr': attr,
                       'ink': COL[attr & 7], 'paper': COL[(attr >> 3) & 7],
                       'bright': bool(attr & 0x40),
                       'attrs': m[0x5800:0x5B00].hex()}
        img = render_colour(m)
        img.save(os.path.join(outdir, f'colour{rnd:02d}.png'))
        tiles.append(img)
        print(f'round {rnd:2d}: platform attr $%02X = %s on %s%s'
              % (attr, COL[attr & 7], COL[(attr >> 3) & 7], ' BRIGHT' if attr & 0x40 else ''))

    # colour contact sheet
    if tiles:
        cols = 9
        tw, th = tiles[0].size
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * (tw // 3 + 4), rows * (th // 3 + 4)), (20, 20, 20))
        for i, img in enumerate(tiles):
            sheet.paste(img.resize((tw // 3, th // 3)),
                        ((i % cols) * (tw // 3 + 4), (i // cols) * (th // 3 + 4)))
        sheet.save(os.path.join(outdir, 'contact_colour.png'))
    json.dump(palettes, open(portconfig.path('build/round_palettes.json'), 'w'), indent=1)
    print(f'\n{len(tiles)} rounds -> {outdir}/colourNN.png + contact_colour.png; '
          f'palettes -> build/round_palettes.json')
    papers = Counter(p['paper'] for p in palettes.values())
    inks = Counter(p['ink'] for p in palettes.values())
    print('paper colours used:', dict(papers))
    print('ink colours used  :', dict(inks))


if __name__ == '__main__':
    main()
