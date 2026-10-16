#!/usr/bin/env python3
"""romscan.py -- the NO-ROM-BYTES check (M7.53; TRAPS #229).

Scans every tracked file, plus untracked files git does not ignore, for content equal to the
local 48K ROM, and prints LOCATIONS and COUNTS ONLY -- never a byte:

  CELLS   a run equal to one of the ROM character set's aligned 8-byte cells ($3D00..$3FFF)
          with 3 or more inked rows -- a transcribed glyph.  Must be 0.
  STRONG  a run equal to ANY 8-byte ROM window with >= 5 non-zero bytes and >= 4 distinct
          values -- code, tables, text.  Must be 0 outside ALLOW (the game's own "Program:"
          at $9A61, which the ROM's tape messages happen to share).
Weak windows (mostly-zero runs such as one pixel row of '_' or '-') match by coincidence in any
screen dump and are counted but not failed.

Runs are decoded from hex tokens (0xNN / $NN / NN), decimal lists, base64 blobs and JSON integer
lists.  The ROM image is the one SkoolKit ships (the harness needs it); it is read, never copied.

Usage:  python tools/romscan.py            (exit 1 on any CELLS or unallowed STRONG hit)
"""
import base64
import json
import os
import re
import subprocess
import sys

import skoolkit

ROM = open(os.path.join(os.path.dirname(skoolkit.__file__), 'resources', '48.rom'), 'rb').read()
W = 8
WIN = {}
for i in range(len(ROM) - W + 1):
    w = ROM[i:i + W]
    if len(set(w)) > 1:
        WIN.setdefault(w, i)
CELLS = set(ROM[a:a + W] for a in range(0x3D00, 0x4000, 8) if sum(1 for x in ROM[a:a + W] if x) >= 3)
ALLOW = {('build/gameover_fixture.json', 0x09C2)}       # "Program:" -- the game's own text at $9A61

SKIP = ('.tzx', '.tap', '.pkl', '.bin', '.z80', '.png', '.zip', '.rom', '.sna')
SEQ = re.compile(r'((?:(?:0x|\$)?[0-9A-Fa-f]{2}[\s,;]+){7,}(?:0x|\$)?[0-9A-Fa-f]{2})')
DECSEQ = re.compile(r'((?:\b\d{1,3}\b[\s,]+){7,}\b\d{1,3}\b)')
B64 = re.compile(r'[A-Za-z0-9+/]{16,}={0,2}')

cells, strong, weak = [], [], 0


def check(buf, where):
    global weak
    buf = bytes(buf)
    for i in range(len(buf) - W + 1):
        w = buf[i:i + W]
        if w in CELLS:
            cells.append(where)
            return
        a = WIN.get(w)
        if a is not None:
            if sum(1 for x in w if x) >= 5 and len(set(w)) >= 4:
                strong.append((where, a))
            else:
                weak += 1
            return


def walk(o, f, path):
    if isinstance(o, list):
        if o and all(isinstance(x, int) and 0 <= x < 256 for x in o):
            check(o, '%s:%s' % (f, path))
        for k, x in enumerate(o[:5000]):
            walk(x, f, '%s[%d]' % (path, k))
    elif isinstance(o, dict):
        for k, x in o.items():
            walk(x, f, '%s.%s' % (path, k))


def main():
    files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                           capture_output=True, text=True).stdout.split('\n')
    files = [f for f in files if f and os.path.isfile(f) and not f.endswith(SKIP)]
    for f in files:
        try:
            text = open(f, 'rb').read().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        for ln, line in enumerate(text.split('\n'), 1):
            where = '%s:%d' % (f, ln)
            for m in SEQ.finditer(line):
                check([int(t, 16) for t in re.findall(r'(?:0x|\$)?([0-9A-Fa-f]{2})(?![0-9A-Fa-f])', m.group(1))], where)
            for m in DECSEQ.finditer(line):
                v = [int(t) for t in re.findall(r'\d{1,3}', m.group(1))]
                if all(t < 256 for t in v):
                    check(v, where)
            for m in B64.finditer(line):
                s = m.group(0)
                try:
                    check(base64.b64decode(s + '=' * (-len(s) % 4)), where)
                except Exception:
                    pass
        if f.endswith('.json'):
            try:
                walk(json.loads(text), f, '$')
            except ValueError:
                pass
    bad = [(w, a) for w, a in strong if (w.split(':')[0], a) not in ALLOW]
    print('scanned %d files: CELLS %d, STRONG %d (%d allowed), weak %d' % (len(files), len(cells), len(strong),
                                                                           len(strong) - len(bad), weak))
    for w in cells[:20]:
        print('  CELL   %s' % w)
    for w, a in bad[:20]:
        print('  STRONG %s  (ROM window at $%04X)' % (w, a))
    return 1 if cells or bad else 0


if __name__ == '__main__':
    sys.exit(main())
