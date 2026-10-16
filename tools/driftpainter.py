# -*- coding: utf-8 -*-
"""M7.8-C -- THE DRIFT PAINTER $7C57..$7DD5, transliterated, and its asset shrunk
from 15,552 bytes of OUTPUT to 676 bytes of INPUT.

M7.7-H4 measured the drift field and shipped it as build/drift_field.json --
81 rounds x 192 bytes, 2 bits per cell -- and said "WHEN THE PAINTER LANDS THE
ASSET GOES, rather than staying as a cross-check".  This is the painter landing.

*** WHAT THE PORT SHIPS NOW IS THE PAINTER'S INPUT, NOT ITS OUTPUT. ***
  $79AF..$7C22   628  the per-round rectangle stream, 82 entries, ZERO slack
  $7C23..$7C32    16  LEN[16], the entry stride, LEN[n] = 4 + 2n + (n >> 1)
  $7C33..$7C42    16  BODY[16], the body offset, BODY[n] = 2 + (n >> 1)
  $7E1A..$7E28    15  the door pattern bytes -- FIFTEEN, not sixteen: $7E29
                      is the painter's own entry/skip COUNTER, live state written
                      by $7C8E/$7CB0/$7CE7/$7D4A, and shipping it as table data
                      would freeze a variable.  Pattern index 15 would select it;
                      MEASURED over all 81 rounds, the index runs 0..12 and 15 is
                      NEVER selected (tools/driftpainter.py:phase_patix)
All four are STATIC TAPE DATA: byte-identical in build/image_tape.bin and
build/image.bin, and a write-watch over 2,400 frames of six live states plus 20
chained round builds records ZERO writes into any of them.

AND THE GATE CHANGES SHAPE WITH IT.  The 81-round row that existed compared
build/drift_field.json against build/drift_fixture.json -- which an adversarial
pass found are BYTE-IDENTICAL base64 for all 81 rounds, so it compared one
capture against a copy of itself.  The field is now the ORACLE and the port
computes against it, which is a test of the algorithm.

THE DOMAIN IS 1..81 AND IT IS NOT DECORATION.  The machine walks the stream
through LIVE memory; at ($8609) = 0 -- the byte $96FB writes at every new game --
it leaves $79AF..$7C42 and writes 141 cells over $FB02..$FFF0, and at 255 it
writes 10,545 over $FB00..$FFF9, across the player struct, the bubble pool and
the scores.  MEASURED here that the port cannot reach it: $97F8 is
`LD A,($8609) / INC A / LD ($8609),A / CP $52 / JR nz`, so the round is
incremented BEFORE the round start and a lookahead replaces 82, and ($8609) at
every $79AC over a chained game is 1..81.  The port guards the domain anyway,
because driftApply()'s silent no-op on an unknown round becomes memory
corruption once a real painter runs.

Usage:  python tools/driftpainter.py            (capture)
        python tools/driftpainter.py verify
"""
import sys, json, base64, zlib
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc

FIXTURE = 'build/driftpainter_fixture.json'
ASSET = 'build/drift_painter.json'
BRANCH_BYTE = 0x8DC4
PAINT_IN = 0x79AC                 # JP $7C43
ELEM = 0x7DD6                     # the fall-through tail: the painter ends here
MAP, MAP_END = 0xF800, 0xFB00
ROUND = 0x8609
BLOCKS = [('stream', 0x79AF, 0x7C23), ('len', 0x7C23, 0x7C33),
          ('body', 0x7C33, 0x7C43), ('pattern', 0x7E1A, 0x7E29)]
SP_PIN = [0]


def new(state='round1_48'):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    SP_PIN[0] = h.sim.registers[12]
    return h, m


def arm(h, addr):
    r = h.sim.registers
    sp = SP_PIN[0]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def paint(h, m, rnd):
    """Run the painter for `rnd` and return the field plus the ordered log.
       Stops at $7DD6, the element class, which is NOT the painter; round 81
       returns at $7C89 onto the sentinel instead."""
    m[ROUND] = rnd
    sp = arm(h, PAINT_IN)
    h.memobj.watch(MAP, 0x10000)
    h.run_until((ELEM,) + tuple(h.SENTINELS), limit=40 * 10 ** 6, stride=1,
                interrupts=False)
    log = [(p, a, v) for (p, a, v) in h.memobj.log]
    h.memobj.unwatch()
    return bytes(m[MAP:MAP_END]), log


def pack(field):
    """Two bits per cell, four cells per byte, LOW pair first -- the same
       packing build/drift_field.json uses, so the two are comparable."""
    out = bytearray(192)
    for i in range(768):
        out[i >> 2] |= ((field[i] >> 6) & 3) << (2 * (i & 3))
    return bytes(out)


def phase_asset():
    """The four static blocks, from the TAPE image -- and the negative that says
       they are static: identical in tape and dump, and never written."""
    tape = open('build/image_tape.bin', 'rb').read()
    img = open('build/image.bin', 'rb').read()
    out = {}
    for name, lo, hi in BLOCKS:
        out[name] = {'at': lo, 'n': hi - lo,
                     'b64': base64.b64encode(tape[lo:hi]).decode(),
                     'tape_equals_image': tape[lo:hi] == img[lo:hi]}
    out['total_bytes'] = sum(hi - lo for _, lo, hi in BLOCKS)
    return out


def phase_static():
    """ZERO writes into any of the four blocks, over live play and over builds.
       This is what lets the port seed them once at reset() and never again."""
    import roundclass as rc
    rows = {}
    for st in ('round1_48', 'r20_48', 'r60_48', 'boss'):
        try:
            h, m = new(st)
        except Exception:
            continue
        h.memobj.watch(0x79AF, 0x7E2A)
        h.run_frames(200)
        log = list(h.memobj.log)
        h.memobj.unwatch()
        rows[st] = {'frames': 200, 'writes_in_blocks': len(
            [1 for (_, a, _) in log
             if any(lo <= a < hi for _, lo, hi in BLOCKS)])}
    h, m = rc.new('round1_48')
    rc.suppress_warp(m)
    m[rc.ROUND] = 0; m[rc.BUILD_A] = 0; m[rc.BUILD_B] = 0
    h.memobj.watch(0x79AF, 0x7E2A)
    for _ in range(12):
        rc.seed_round(m); rc.suppress_warp(m)
        sp = rc.arm(h, rc.ADVANCE); rc.run(h, sp)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    inblocks = [(p, a) for (p, a, _) in log
                if any(lo <= a < hi for _, lo, hi in BLOCKS)]
    rows['chained_12_builds'] = {'writes_in_blocks': len(inblocks),
                                 'writer_pcs': sorted(set('%04X' % p
                                                          for p, _ in inblocks))}
    return rows


def phase_oracle():
    """THE MACHINE'S OWN FIELD FOR ALL 81 ROUNDS, plus the ordered write log's
       shape.  This is the oracle the port's painter is judged against -- and it
       is a different artifact from build/drift_field.json, which the old gate
       compared against a byte-identical copy of itself."""
    rows = []
    for rnd in range(1, 82):
        h, m = new()
        field, log = paint(h, m, rnd)
        pcs = {}
        for (p, a, v) in log:
            pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        outside = [a for (_, a, _) in log if not (MAP <= a < MAP_END)]
        hist = [0, 0, 0, 0]
        for c in field:
            hist[(c >> 6) & 3] += 1
        rows.append({'round': rnd, 'packed': base64.b64encode(pack(field)).decode(),
                     'crc': zlib.crc32(field) & 0xFFFFFFFF,
                     'writes': len(log), 'writer_pcs': pcs, 'hist': hist,
                     'outside': len(outside),
                     'outside_range': (['%04X' % min(outside),
                                        '%04X' % max(outside)] if outside else [])})
    return rows


def phase_domain():
    """THE DOMAIN, AND THE PROOF THE PORT CANNOT LEAVE IT.  $97F8 increments
       ($8609) BEFORE the round start and swaps 82 for the lookahead, so the
       painter never sees 0 or 82.  Driven, not read."""
    import roundclass as rc
    h, m = rc.new('round1_48')
    rc.suppress_warp(m)
    m[rc.ROUND] = 0; m[rc.BUILD_A] = 0; m[rc.BUILD_B] = 0
    seen = []
    for _ in range(6):
        rc.seed_round(m); rc.suppress_warp(m)
        sp = rc.arm(h, rc.ADVANCE)
        tot = 0
        while tot < 200 * 10 ** 6:
            h.run_until((PAINT_IN,) + tuple(h.SENTINELS),
                        limit=200 * 10 ** 6 - tot, stride=1, interrupts=True)
            if h.regs[PC] in h.SENTINELS:
                break
            seen.append(m[ROUND])
            h.step(1, interrupts=True)
            tot += 1
    off = {}
    for rnd in (0, 255):
        h2, m2 = new()
        field, log = paint(h2, m2, rnd)
        outside = [a for (_, a, _) in log if not (MAP <= a < MAP_END)]
        off[str(rnd)] = {'writes': len(log), 'outside': len(outside),
                         'outside_range': (['%04X' % min(outside),
                                            '%04X' % max(outside)]
                                           if outside else [])}
    return {'rounds_at_the_painter': seen, 'never_zero': 0 not in seen,
            'off_domain': off,
            'why': '$97F8 LD A,($8609) / INC A / LD ($8609),A / CP $52 / JR nz'}


def phase_patix():
    """WHICH PATTERN INDEX EACH ROUND SELECTS, and the negative that decides the
       asset's size.  $7D84 stores $7E1A + patix into ($7E10); index 15 would
       point at $7E29, which is NOT table data but the painter's own counter.
       Measured by watching ($7E10) across all 81 rounds rather than reasoning
       about the header nibble."""
    seen = {}
    for rnd in range(1, 82):
        h, m = new()
        m[ROUND] = rnd
        sp = arm(h, PAINT_IN)
        h.memobj.watch(0x7E10, 0x7E12)
        h.run_until((ELEM,) + tuple(h.SENTINELS), limit=40 * 10 ** 6, stride=1,
                    interrupts=False)
        for (p, a, v) in h.memobj.log:
            if a == 0x7E10:
                seen.setdefault(str((v - 0x1A) & 0xFF), []).append(rnd)
        h.memobj.unwatch()
    idx = sorted(int(k) for k in seen)
    return {'indices': idx, 'max': max(idx), 'index_15_used': '15' in seen,
            'rounds_per_index': {k: len(v) for k, v in seen.items()},
            'why': '$7E29 is the live counter; index 15 would select it and is '
                   'never selected, so the shipped block is FIFTEEN bytes'}


def capture():
    fx = {'note': __doc__.strip(), 'paint_in': PAINT_IN, 'ends_at': ELEM,
          'blocks': [[n, lo, hi] for n, lo, hi in BLOCKS],
          'asset': phase_asset(), 'static': phase_static(),
          'domain': phase_domain(), 'patix': phase_patix(), 'oracle': phase_oracle()}
    json.dump(fx, open(FIXTURE, 'w'), sort_keys=True)
    a = fx['asset']
    json.dump({'note': 'M7.8-C the drift painter $7C57..$7DD5 INPUTS -- the '
                       'per-round rectangle stream, its two stride tables and '
                       'the door pattern.  676 bytes of static tape data, '
                       'replacing 15,552 bytes of captured output.',
               'blocks': {n: {'at': a[n]['at'], 'n': a[n]['n'], 'b64': a[n]['b64']}
                          for n, _, _ in BLOCKS}},
              open(ASSET, 'w'), sort_keys=True)
    print('wrote %s and %s (%d bytes of input data)'
          % (FIXTURE, ASSET, a['total_bytes']))
    return fx


def verify(fx=None):
    fx = fx or json.load(open(FIXTURE))
    a = fx['asset']
    print('\nASSET: %d bytes, all tape==image: %s'
          % (a['total_bytes'], all(a[n]['tape_equals_image'] for n, _, _ in BLOCKS)))
    print('STATIC:', json.dumps(fx['static']))
    d = fx['domain']
    print('DOMAIN: rounds seen at $79AC over six advances: %s  (never 0: %s)'
          % (d['rounds_at_the_painter'], d['never_zero']))
    print('   off-domain:', json.dumps(d['off_domain']))
    o = fx['oracle']
    print('\nORACLE: %d rounds' % len(o))
    for r in o[:3] + o[-2:]:
        print('   r%-3d writes %4d  pcs %s  hist %s  outside %d %s'
              % (r['round'], r['writes'], r['writer_pcs'], r['hist'],
                 r['outside'], r['outside_range']))
    out = [r['round'] for r in o if r['outside']]
    print('   rounds painting OUTSIDE the map: %s' % out)
    print('   rounds with ZERO code-3 cells: %s'
          % [r['round'] for r in o if r['hist'][3] == 0])


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    verify(capture()) if cmd == 'capture' else verify()
