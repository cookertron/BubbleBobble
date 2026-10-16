#!/usr/bin/env python3
"""
sfxcensus.py -- phase 11 (sound): WHICH beeper/AY sites fire, WHEN, driven by a key script.

Runs a saved state, hooks every OUT with its PC and T-state, and prints the
$FE (beeper/border) writes grouped into BURSTS (a gap of more than one frame
starts a new burst) with the OUT sites that produced them, plus any other
ports touched (AY $FFFD/$BFFD, paging $7FFD).  The raw edge log
[(T-from-start, PC, value), ...] goes to --out as JSON for modelling.

    python tools/sfxcensus.py fruit --script "5:,30:P,60:" --out build/sfx/collect.json
    python tools/sfxcensus.py death --frames 320

Script grammar is keyprobe's: "N:KEY+KEY,N:,..." (N frames, keys held).
Lesson (Bubble Bobble, TRAPS #28): the same site can be data in one state
and code in another -- attribute by the PC that EXECUTED the OUT, never by
a static D3 FE scan (which also matches LD ($FED3),A = 32 D3 FE).
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness                                   # noqa: E402
from harness import Harness, PC, T               # noqa: E402
import portconfig, keyprobe                      # noqa: E402
from collections import Counter                  # noqa: E402

LOG = []


def _hook(self, regs, port, value):
    LOG.append((regs[T], regs[PC], port, value))


def install_hook():
    """Attribute every OUT to its PC.  Class-level because the simulator binds
    the tracer's bound method at construction; installed on first use only so
    importing this module leaves the harness untouched."""
    if harness.Ports.write_port is not _hook:
        harness.Ports.write_port = _hook


def census(state, script, out=None, quiet=False):
    """script = [(key-or-None, frames), ...]; returns the summary dict."""
    install_hook()
    LOG.clear()
    h = Harness()
    h.load_state_file(portconfig.state_path(state))
    fd = h.frame_duration
    t0 = h.regs[T]
    f = 0
    for keys, frames in script:
        h.ports.release_all()
        for k in (keys or []):
            keyprobe.press(h.ports, k)
        for _ in range(frames):
            h.run_frames(1)
            f += 1
    fe = [(t - t0, pc, v) for t, pc, p, v in LOG if (p & 0xFF) == 0xFE]
    other = Counter('%04X' % p for t, pc, p, v in LOG if (p & 0xFF) != 0xFE)
    bursts = []
    for t, pc, v in fe:
        site = '%04X' % pc
        if bursts and t - bursts[-1]['t1'] <= fd:
            b = bursts[-1]
            b['t1'] = t
            b['n'] += 1
            b['sites'][site] = b['sites'].get(site, 0) + 1
        else:
            bursts.append({'t0': t, 't1': t, 'n': 1, 'sites': {site: 1}})
    summary = {
        'state': state, 'script': script, 'frames': f, 'fe_writes': len(fe),
        'other_ports': dict(other),
        'bursts': [{'frame': round(b['t0'] / fd, 2), 'span_frames': round((b['t1'] - b['t0']) / fd, 2),
                    'writes': b['n'], 'sites': b['sites']} for b in bursts]}
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        json.dump({'summary': summary, 'fe': fe}, open(out, 'w'))
    if not quiet:
        print('== %s (%d frames, %d $FE writes, other ports %s)'
              % (state, f, len(fe), dict(other)))
        for b in summary['bursts'][:60]:
            print('   burst @f%-8s span %-6s writes %-5d sites %s'
                  % (b['frame'], b['span_frames'], b['writes'], b['sites']))
    return summary


def parse_script(text, frames):
    if not text:
        return [(None, frames)]
    out = []
    for seg in text.split(','):
        n, _, keys = seg.partition(':')
        out.append(([k for k in keys.split('+') if k] or None, int(n)))
    return out


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith('-'):
        print(__doc__)
        return 2
    state = args.pop(0)
    frames, script, out = 300, '', None
    while args:
        a = args.pop(0)
        if a == '--frames':
            frames = int(args.pop(0))
        elif a == '--script':
            script = args.pop(0)
        elif a == '--out':
            out = args.pop(0)
        else:
            print('unknown option', a)
            return 2
    census(state, parse_script(script, frames), out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
