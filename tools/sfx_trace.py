#!/usr/bin/env python3
"""
sfx_trace.py -- phase 11.4 (6.6): the beeper emitters' EDGE TRAINS by isolated call.

Each 48K sound is a routine (or a per-tick OUT) in the game code.  This calls
every emitter in the harness with its live parameters -- across the parameter
range where there is one -- hooks every OUT ($FE) and writes the edge train
[T-offset, value] plus a summary to build/sfx/<name>.json.  These are the
oracle fixtures the engine's generators are compared against (cmp_sfx.js /
sfxgate.py, M7): edge COUNT and every PERIOD, not "sounds about right".

    python tools/sfx_trace.py            # all emitters -> build/sfx/*.json + index.json
    python tools/sfx_trace.py collect    # one

Emitters (Bubble Bobble 48K branch, SPEC "M6 sound"):
  collect     CALL $8CB1, C=40 (constant at $881D)     rising chirp on item collect
  jump_E13..21  CALL $8FD4 with E preset                two square-wave cycles per main-loop pass
  hurry       CALL $9062                                HURRY UP! (blocking; 3 clicks + text flash)
  letter      CALL $B790, IY=player                     one click per EXTEND letter / score pop
  rom_click   CALL ROM BEEPER $03B5, HL=$0320 DE=2      front-end key click
  blow        DRIVEN: round1_48 + BLOW key ('7' = cursor-scheme BLOW)               one OUT of BLOW_CADENCE*8 every 2 frames
Values are the raw port byte: bit 4 = speaker, bit 3 = MIC, bits 0-2 = border.
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import Harness, PC, T                 # noqa: E402
import portconfig, keyprobe                        # noqa: E402
import sfxcensus                                   # noqa: E402

OUT_DIR = portconfig.path('build/sfx') if hasattr(portconfig, 'path') else os.path.join(HERE, '..', 'build', 'sfx')
FD = 69888


def _edges(t0):
    return [[t - t0, v] for t, pc, p, v in sfxcensus.LOG if (p & 0xFF) == 0xFE]


def _summary(edges):
    if not edges:
        return {'edges': 0}
    ts = [e[0] for e in edges]
    spk = [(e[1] >> 4) & 1 for e in edges]
    # speaker-level transitions only (an OUT that repeats the level is not an edge you can hear)
    trans = [ts[i] for i in range(len(ts)) if i == 0 or spk[i] != spk[i - 1]]
    periods = [trans[i + 1] - trans[i] for i in range(len(trans) - 1)]
    return {'edges': len(edges), 'speaker_transitions': len(trans),
            'span_T': ts[-1] - ts[0], 'span_frames': round((ts[-1] - ts[0]) / FD, 3),
            'half_period_min_T': min(periods) if periods else None,
            'half_period_max_T': max(periods) if periods else None,
            'values': sorted(set(e[1] for e in edges))}


def isolated(name, state, entry, regs=None, pokes=(), limit=6_000_000, note=''):
    sfxcensus.install_hook()
    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    for a, v in pokes:
        h.memobj.m[a] = v
    sfxcensus.LOG.clear()
    t0 = h.regs[T]
    idx, cost, steps = h.call(entry, regs or {}, limit=limit, interrupts=False)
    edges = _edges(t0)
    rec = {'name': name, 'kind': 'isolated', 'state': state, 'entry': '0x%04X' % entry,
           'regs': {k: ('0x%X' % v) for k, v in (regs or {}).items()}, 'pokes': ['0x%04X=0x%02X' % p for p in pokes],
           'exit': idx, 'cost_T': cost, 'note': note, 'summary': _summary(edges), 'edges': edges}
    return rec


def driven(name, state, script, note=''):
    """script = [(keys-or-None, frames), ...]; edges stamped from the first key press."""
    sfxcensus.install_hook()
    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    sfxcensus.LOG.clear()
    t0 = h.regs[T]
    for keys, frames in script:
        h.ports.release_all()
        for k in (keys or []):
            keyprobe.press(h.ports, k)
        for _ in range(frames):
            h.run_frames(1)
    edges = _edges(t0)
    rec = {'name': name, 'kind': 'driven', 'state': state, 'script': script, 'note': note,
           'summary': _summary(edges), 'edges': edges}
    return rec


def all_emitters(only=None):
    S48 = 'round1_48'
    jobs = []
    jobs.append(lambda: isolated('collect', S48, 0x8CB1, {'C': 40},
                                 note='item-collect chirp; C=40 is the constant LD C,$28 at $881D before CALL $8CB1 ($881F)'))
    for E in range(13, 22):
        jobs.append(lambda E=E: isolated('jump_E%d' % E, S48, 0x8FD4, {'E': E},
                                         note='jump tone inner generator: B=2 cycles, half-period 16E+10 T; E=|$B57D[phase]-16|+1'))
    jobs.append(lambda: isolated('hurry', S48, 0x9062, {'IX': 0xFD80},
                                 note='HURRY UP! routine, blocking; speaker OFF/ON only at the 3 text-colour toggles'))
    jobs.append(lambda: isolated('letter', S48, 0xB790, {'IY': 0xFD80},
                                 note='EXTEND letter / score click: OUT 0, +1 score, OUT $30'))
    jobs.append(lambda: isolated('rom_click', 'title', 0x03B5, {'HL': 0x0320, 'DE': 2},
                                 note='front-end key click via ROM BEEPER (HL=period word, DE=cycles) as called at $F7DB'))
    jobs.append(lambda: driven('blow', 'round1_48', [(['7'], 6), (None, 30)],
                               note='blow clicks: OUT (IY+$60)*8 every 2 frames while the counter runs 1..7'))
    out = []
    for j in jobs:
        rec = j()
        if only and rec['name'] != only:
            continue
        out.append(rec)
    return out


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    os.makedirs(OUT_DIR, exist_ok=True)
    index = []
    for rec in all_emitters(only):
        path = os.path.join(OUT_DIR, rec['name'] + '.json')
        json.dump(rec, open(path, 'w'), indent=1)
        s = rec['summary']
        index.append({'name': rec['name'], 'kind': rec['kind'], 'file': os.path.basename(path), **s})
        print('%-10s %-8s edges %4d  spk-trans %4d  span %8s T (%6s f)  half-period %s..%s T  values %s  exit %s'
              % (rec['name'], rec['kind'], s.get('edges', 0), s.get('speaker_transitions', 0), s.get('span_T', '-'),
                 s.get('span_frames', '-'), s.get('half_period_min_T'), s.get('half_period_max_T'), s.get('values'), rec.get('exit', '-')))
    if not only:
        json.dump(index, open(os.path.join(OUT_DIR, 'index.json'), 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
