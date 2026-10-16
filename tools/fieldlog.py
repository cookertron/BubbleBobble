#!/usr/bin/env python3
"""
fieldlog.py -- watch a list of RAM fields evolve over driven play, printing only
the frames where something CHANGES.  The transition-diff-over-time companion to
readwatch.py: readwatch finds WHO reads a buffer; fieldlog shows HOW named
variables (a player's X, an entity slot's flags, a timer) move, so you read a
state machine's behaviour off a table before reading its code (manual 8.2/10).

This is exactly the ad-hoc "sample these offsets each frame, print changed rows"
loop you would otherwise rewrite per port; it is game-agnostic (fields are given
on the command line or from the manifest varmap) and does no interpretation.

Columns come from any of:
  --fields NAME=ADDR[:W],...          scalar fields (W=1 default, 2 = 16-bit LE)
  --slots BASE:STRIDE:COUNT --off O[:W],...   an entity table: each slot's offsets
  --varmap                            every field in tools/varmap.json ({name:{addr,width}})

Usage:
  python tools/fieldlog.py --state round1 --frames 240 \
        --slots 0xFD94:10:1 --off 0:2,4,5,6,7,8,9
  python tools/fieldlog.py --state play1p --keys P --frames 120 \
        --fields p1x=0xFD85,p1y=0xFD86,p1flags=0xFD87 [--dec] [--all] [--out build/fl.json]

--keys   keys HELD throughout (names as keyprobe.py prints them), applied after --warm
--warm   frames to run before logging (default 0)
--all    print every frame, not only the ones that change
--dec    print values in decimal (default hex); coordinates read better in decimal
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness                                        # noqa: E402
from keyprobe import press                                         # noqa: E402
from filmstrip import run_frames                                   # noqa: E402


def parse_fields(spec):
    cols = []
    for item in spec.split(','):
        if not item:
            continue
        name, _, rhs = item.partition('=')
        addr, _, w = rhs.partition(':')
        cols.append((name, int(addr, 0), int(w) if w else 1))
    return cols


def parse_offs(spec):
    offs = []
    for item in spec.split(','):
        if not item:
            continue
        o, _, w = item.partition(':')
        offs.append((int(o, 0), int(w) if w else 1))
    return offs


def main():
    args = sys.argv[1:]
    if not args or '-h' in args or '--help' in args:
        print(__doc__.strip()); sys.exit(0)
    state = None
    keys = []
    warm = 0
    frames = 120
    cols = []
    slots = None
    offs = [(0, 1)]
    use_varmap = False
    show_all = False
    dec = False
    out = None
    while args:
        a = args[0]
        if a == '--state': state = args[1]; del args[:2]
        elif a == '--keys': keys = [k for k in args[1].split(',') if k]; del args[:2]
        elif a == '--warm': warm = int(args[1]); del args[:2]
        elif a == '--frames': frames = int(args[1]); del args[:2]
        elif a == '--fields': cols += parse_fields(args[1]); del args[:2]
        elif a == '--slots': slots = args[1]; del args[:2]
        elif a == '--off': offs = parse_offs(args[1]); del args[:2]
        elif a == '--varmap': use_varmap = True; del args[:1]
        elif a == '--all': show_all = True; del args[:1]
        elif a == '--dec': dec = True; del args[:1]
        elif a == '--out': out = args[1]; del args[:2]
        else: sys.exit(f'fieldlog: unknown argument {a}')
    if state is None:
        sys.exit('fieldlog: --state NAME is required')

    if use_varmap:
        vm = json.load(open(portconfig.path(portconfig.get('z80', 'varmap'))))
        for name, d in sorted(vm.items(), key=lambda kv: kv[1]['addr']):
            cols.append((name, d['addr'], d.get('width', 1)))
    if slots is not None:
        base, stride, count = (int(x, 0) for x in slots.split(':'))
        for s in range(count):
            for o, w in offs:
                cols.append((f's{s}+{o:X}', base + s * stride + o, w))
    if not cols:
        sys.exit('fieldlog: give columns via --fields, --slots or --varmap')

    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for k in keys:
        press(h.ports, k)
    if warm:
        run_frames(h, warm)
    m = h.memobj.m

    def read():
        return tuple(m[a] if w == 1 else (m[a] | (m[a + 1] << 8)) for _, a, w in cols)

    fmt = (lambda v, w: f'{v:>3d}') if dec else (lambda v, w: f'{v:0{w * 2}X}')
    widths = [max(len(c[0]), (3 if dec else c[2] * 2)) for c in cols]
    header = 'frame | ' + ' '.join(f'{c[0]:>{widths[i]}}' for i, c in enumerate(cols))
    print(header)
    print('-' * len(header))

    rows = []
    prev = None
    changed = 0
    for f in range(frames):
        cur = read()
        if show_all or cur != prev:
            line = ' '.join(f'{fmt(v, cols[i][2]):>{widths[i]}}' for i, v in enumerate(cur))
            print(f'{f:5d} | {line}')
            rows.append([f] + list(cur))
            if prev is not None and cur != prev:
                changed += 1
            prev = cur
        h.run_frames(1)

    print(f'\n{frames} frames, {changed} changes, {len(cols)} columns'
          f'{" (keys=" + ",".join(keys) + ")" if keys else ""}')
    if out:
        json.dump({'state': state, 'keys': keys, 'frames': frames,
                   'cols': [{'name': c[0], 'addr': c[1], 'w': c[2]} for c in cols],
                   'rows': rows}, open(portconfig.path(out), 'w'), indent=1)
        print(f'-> {out}')


if __name__ == '__main__':
    main()
