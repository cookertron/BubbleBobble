#!/usr/bin/env python3
"""
debug_mutants.py -- THE DEBUG LAYER'S MUTATION RUN (house rule 3: a test that cannot fail is not a test).

    python tools/debug_mutants.py [--jobs N] [NAME ...]

Each mutant breaks ONE behaviour of web/debug.js (a single exact replacement, asserted to match once).  Its debug page is
assembled exactly as tools/build_debug.py assembles one (build_debug.assemble: the built faithful page plus the layer,
the boundary checked) and goes through test/debug.test.js with BB_DEBUG_PAGE naming it (no build).  A mutant is KILLED
when a check FAILs (or the run times out -- said apart); a CONTROL, the layer unmutated through the same assembly, must
pass whole, or nothing the table says counts.  NAMEs select mutants (the control always runs).

The pages hold the game's assets (tape-derived, house rule 7): they and each run's output go to scratch/debug_mutants/,
which is git-ignored.  Build the faithful page first (python tools/build_debug.py does).  All 29 at --jobs 14 take ~30
minutes; a run longer than 40 minutes is stopped and counted TIMEOUT.  Exit status 1 if the control fails or a mutant
survives.
"""
import argparse
import io
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_debug                                           # noqa: E402

OUT = os.path.join(ROOT, 'scratch', 'debug_mutants')
TIMEOUT = 2400

# (name, the layer's text, its mutant) -- each the behaviour a named check in test/debug.test.js holds
MUTANTS = [
    ('counters',    'const d = n - c - 1;', 'const d = 0;'),                          # T1: the build counters
    ('warp',        'if (warp){ ram[D.PLAYER[0] + 0x5A] |= 0x80; ram[D.PLAYER[1] + 0x5A] |= 0x80; }', 'if (false){ }'),   # T5
    ('warp-back',   'ram[a] = (ram[a] & 0x7F) | (f[p] & 0x80);', 'void a;'),         # T5: bit 7 put back
    ('corpse',      'corpse(g, s); k++;', 'ram[s + 7] &= 0x7F; k++;'),                # A12: $8BC2, not a removal
    ('burst',       'ram[s + 3] = 10; ram[s + 7] |= 0x08; ram[s + 7] |= 0x02;  // $A0FF', 'void s;  // $A0FF'),   # A19
    ('parity',      'w = (v + ((v - t) & 1)) & 0xFFFF;', 'w = v & 0xFFFF;'),         # A11: the timer's parity
    ('skip',        'if (timer(g) < 0x0175){', 'if (false){'),                        # A13: the clear's wait skipped
    ('room-skip',   'w = setTimer(g, ((ram[D.ROOM_CAP] + 8) & 0xFF) << 8);', 'w = t;'),   # A15: the drain's window
    ('expiry',      'ram[at + 1] = (ram[at + 1] & 0xF8) | 3; ram[D.CLOCK] = 0xFF;', 'void at;'),   # A4: a busy slot
    ('latch',       'ram[D.LATCHES] |= latch;', 'void latch;'),                       # A3 / A7: the spawn's latch
    ('phase',       'ram[at + 1] = (ram[at + 1] & 0xF8) | 1;', 'void at;'),          # A4: a fresh item's phase
    ('umb-lock',    'if (at === D.PU && t === 6) ram[D.UMB_LOCK] = 6;', 'void t;'),  # A5: $8A45's lock
    ('letter',      'g.ram[at] |= 1 << i;', 'g.ram[at] |= 1 << (i + 1);'),           # A8: the letter's bit
    ('trigger',     'g.ram[D.TRIGGER] = 1;                              // $B808', 'void 0;                              // $B808'),   # A8
    ('extend',      'g.ram[D.PLAYER[p] + 0x63] = 0x3F;', 'g.ram[D.PLAYER[p] + 0x63] = 0x3E;'),   # A8: all six
    ('add-life',    'g.ram[at]++;', 'void at;'),                                       # A9
    ('redraw',      'try { g.livesPanel(); } finally { g.pT = pT; }', 'void pT;'),    # A9: $806C
    ('hurry-wait',  "if (ram[D.RESET]) return 'wait';", 'void 0;'),                   # A11: the respawn's $9160
    ('god-count',   'ram[b + 0x5A] |= 0x08; ram[b + 4] = 0x50; }', 'ram[b + 0x5A] |= 0x08; }'),   # A10: the count held
    ('god-bit',     'ram[b + 0x5A] |= 0x08; ram[b + 4] = 0x50; }', 'ram[b + 4] = 0x50; }'),      # A10: the bit held
    ('inf-lives',   'ram[b + 0x5C] = st.lives[p]; livesRedraw(g); }', 'livesRedraw(g); }'),     # A9
    ('umb-cancel',  'ram[D.UMB] = 0;  ', 'void 0;  '),                                # A6b: a skip ended by a jump
    ('tens',        'if (n < 10) ram[D.TENS] = 0x20;', 'void n;'),                    # T4: $97C2's blank
    ('r1-mid',      'st.r1Mid = n === 1 && c !== 0;', 'st.r1Mid = false;'),           # T1: round 1 from a round
    ('spent',       "if (st.queue[i].advance){ st.queue[i].result = 'done'; st.queue.splice(i, 1); }", 'void i;'),   # A8b
    ('mute',        'sound.on = false; st.muted = true;', 'st.muted = true;'),        # A18
    ('boss',        'if (ram[D.ROUND] === D.BOSS && ram[D.BOSS_HP]) bossKill(g, 0);', 'void 0;'),   # T1 / T3
    ('freeze',      'if (st.frozen){ n = st.stepReq > 0 ? 1 : 0; if (n) st.stepReq--; }', 'if (st.frozen){ n = 1; }'),   # A1
    ('god-at-once', 'if (st.god[p] && game && !busy(game)) holds(game);', 'void p;'), # A10
]


def run(job):
    name, page_path = job
    env = dict(os.environ, BB_DEBUG_PAGE=page_path)
    try:
        r = subprocess.run(['node', os.path.join(ROOT, 'test', 'debug.test.js')], cwd=ROOT, env=env, capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=TIMEOUT)
        out, timed = r.stdout + r.stderr, False
    except subprocess.TimeoutExpired as e:
        out, timed = (e.stdout if isinstance(e.stdout, str) else '') + '\nTIMEOUT after %d s\n' % TIMEOUT, True
    io.open(os.path.join(OUT, name + '.out'), 'w', encoding='utf-8').write(out)
    m = re.search(r'(\d+)/(\d+) checks passed', out)
    fails = [re.match(r'\s*FAIL\s+(\S+)', l).group(1) for l in out.splitlines() if re.match(r'\s*FAIL\s+', l)]
    return name, (m.group(0) if m else 'TIMEOUT' if timed else 'NO RESULT'), fails, timed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=14)
    ap.add_argument('names', nargs='*')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    out_rel, _ = build_debug.paths()
    page = io.open(os.path.join(ROOT, out_rel), 'rb').read().decode('utf-8')
    layer = io.open(os.path.join(ROOT, build_debug.LAYER), 'rb').read().decode('utf-8').replace('\r\n', '\n')
    unknown = set(a.names) - {m[0] for m in MUTANTS}
    if unknown:
        sys.exit('no such mutant: ' + ', '.join(sorted(unknown)))
    jobs = []
    for name, old, new in [('control', '', '')] + MUTANTS:
        if name != 'control':
            if a.names and name not in a.names:
                continue
            n = layer.count(old)
            if n != 1:
                sys.exit('mutant %s: its text occurs %d times in %s' % (name, n, build_debug.LAYER))
        mut = layer.replace(old, new) if old else layer
        p = os.path.join(OUT, name + '.html')
        io.open(p, 'wb').write(build_debug.assemble(page, mut, out_rel).encode('utf-8'))
        jobs.append((name, p))
    with ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(run, jobs))
    bad, killed = 0, 0
    for name, line, fails, timed in res:
        if name == 'control':
            tag = 'PASS' if not fails and not timed and 'checks passed' in line else 'FAIL'
            bad += tag != 'PASS'
        else:
            tag = 'TIMEOUT' if timed else 'KILLED' if fails or 'checks passed' not in line else 'SURVIVED'
            killed += tag != 'SURVIVED'
            bad += tag == 'SURVIVED'
        print('%-12s %-9s %-22s %s' % (name, tag, line, ' '.join(fails[:10])))
    print('%d of %d mutants killed (a TIMEOUT counts, said apart)' % (killed, len(jobs) - 1))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
