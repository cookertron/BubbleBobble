"""The ISR COST oracle: what each half of the interrupt actually costs.

Captured to replace BB_ISR_UNMODELLED_ODD, the single inexact term in the
engine's frame model.  The headline of the measurement (docs/TIMING.md) is that
the 20900 T was never a measurement gap: it is the cost of the ENEMIES THE
ENGINE DOES NOT SIMULATE, and it reaches zero when $FD80 matches the machine.

Every cost here is bracketed by CONTROL FLOW -- an entry address to the matching
RET -- and never by the stack pointer, which is what produced a 19x error once
before (TRAPS #35).  Four brackets per sampled interrupt:

    TOTAL   $8D72 -> one step past the RET at $8DA1
    A3AD    $A3AD -> one step past the RET at $A42A      (odd branch only)
    AA60    $AA60 -> one step past the RET it reaches     (odd branch only)
    B62C    $B62C -> one step past the RET it reaches     (even branch only)

and TOTAL - (the parts) is the skeleton, which must come out at the measured
constant for that (parity, gate) pair or the capture is wrong.

STATES.  Any state whose byte $8DC4 is $F3 was captured on the 128K branch and
has 3860 bytes of AY engine over the graphics (TRAPS #28, #36).  Every state is
branch-checked here and a bad one is refused, not skipped quietly.

Usage:  python tools/isrcost.py capture
        python tools/isrcost.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, T, PC
import portconfig as pc

ISR_IN, ISR_OUT = 0x8D72, 0x8DA1
EPILOGUE_IN = 0x8D8F        # where both branch bodies RET to
A3AD, A3AD_RET = 0xA3AD, 0xA42A
AA60 = 0xAA60
B62C = 0xB62C
TABLE, POOL, STRIDE, SLOTS = 0xFD80, 0xFED8, 10, 12
COUNT, TOGGLE = 0xAA57, 0xA3B2
FIXTURE = 'build/isrcost_fixture.json'
BRANCH_BYTE = 0x8DC4                       # $C9 = 48K, $F3 = the 128K branch

# states with visibly different populations; all branch-checked at load
STATES = ['round1_48', 'elfire', 'elwater', 'ellight', 'hurryup']

# MEASURED skeleton segments (isr_overhead, three independent brackets, zero variance)
SEG = dict(PROLOGUE=130, COUNTERS=91, BRANCH_ODD=41, BRANCH_EVEN=46,
           GATE_OPEN=22, GATE_CLOSED=28, EPILOGUE=157,
           CALL_A3AD=17, JP_AA60=10, JP_B62C=10, B62C_TOGGLE=27)
SKEL = {
    ('odd', False): SEG['PROLOGUE'] + SEG['COUNTERS'] + SEG['BRANCH_ODD'] + SEG['GATE_CLOSED'] + SEG['EPILOGUE'],
    ('even', False): SEG['PROLOGUE'] + SEG['COUNTERS'] + SEG['BRANCH_EVEN'] + SEG['GATE_CLOSED'] + SEG['EPILOGUE'],
    ('odd', True): SEG['PROLOGUE'] + SEG['COUNTERS'] + SEG['BRANCH_ODD'] + SEG['GATE_OPEN'] + SEG['EPILOGUE']
                   + SEG['CALL_A3AD'] + SEG['JP_AA60'],
    ('even', True): SEG['PROLOGUE'] + SEG['COUNTERS'] + SEG['BRANCH_EVEN'] + SEG['GATE_OPEN'] + SEG['EPILOGUE']
                    + SEG['JP_B62C'],
}


def new(state):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit(f'{state}: $8DC4 = ${m[BRANCH_BYTE]:02X} -- NOT the 48K branch, refusing '
                         f'(TRAPS #28/#36: the AY engine is LDIRed over $C350-$D263)')
    return h, m


def bracket(h, entry, exits):
    """cost of a routine, entry address to the first of `exits`, by CONTROL FLOW"""
    h.run_until((entry,), limit=10 ** 7, stride=1)
    t0 = h.regs[T]
    h.run_until(tuple(exits), limit=10 ** 7, stride=1)
    h.step(1)
    return h.regs[T] - t0


def sample_isr(h):
    """one interrupt, with each half bracketed inside it"""
    m = h.memobj.m
    h.run_until((ISR_IN,), limit=10 ** 7, stride=1)
    t0 = h.regs[T]
    h.step(1)
    # the branch is decided by the NEW parity, after $8DB5 increments the counters
    h.run_until((0x8D88,), limit=10 ** 7, stride=1)
    odd = (m[0x8DBD] & 1) == 1
    gate = bool(m[0xFEC4] if odd else m[0xFEC5])
    parts = {}
    if gate:
        if odd:
            h.run_until((A3AD,), limit=10 ** 7, stride=1)
            ta = h.regs[T]
            h.run_until((A3AD_RET,), limit=10 ** 7, stride=1); h.step(1)
            parts['a3ad'] = h.regs[T] - ta
            h.run_until((AA60,), limit=10 ** 7, stride=1)
            tb = h.regs[T]
            h.run_until((EPILOGUE_IN,), limit=10 ** 7, stride=1)   # its RET lands on $8D8F
            parts['aa60'] = h.regs[T] - tb
        else:
            h.run_until((B62C,), limit=10 ** 7, stride=1)
            tb = h.regs[T]
            h.run_until((EPILOGUE_IN,), limit=10 ** 7, stride=1)
            parts['b62c'] = h.regs[T] - tb
    h.run_until((ISR_OUT,), limit=10 ** 7, stride=1)
    h.step(1)
    return {'odd': odd, 'gate': gate, 'total': h.regs[T] - t0, **parts}


def census(m):
    ents = [k for k in range(SLOTS) if m[TABLE + STRIDE * k + 7] & 0x80]
    pool = [k for k in range(SLOTS) if m[POOL + STRIDE * k + 7] & 0x80]
    return {
        'ents': len(ents), 'count': m[COUNT], 'toggle': m[TOGGLE],
        'pool': len(pool),
        'pool_travelling': sum(1 for k in pool if not (m[POOL + STRIDE * k + 7] & 0x04)),
        'pool_risen': sum(1 for k in pool if (m[POOL + STRIDE * k + 7] & 0x04)
                          and not (m[POOL + STRIDE * k + 7] & 0x08)),
        'pool_burst': sum(1 for k in pool if (m[POOL + STRIDE * k + 7] & 0x0C) == 0x0C),
        'players': sum(1 for k in (0, 1) if m[TABLE + STRIDE * k + 7] & 0x80),
    }


def capture(frames=90):
    rows = []
    for st in STATES:
        h, m = new(st)
        for f in range(frames):
            before_table = [m[TABLE + i] for i in range(SLOTS * STRIDE)]
            before_pool = [m[POOL + i] for i in range(SLOTS * STRIDE)]
            c = census(m)
            s = sample_isr(h)
            skel = SKEL[('odd' if s['odd'] else 'even', s['gate'])]
            parts = s.get('a3ad', 0) + s.get('aa60', 0) + s.get('b62c', 0)
            rows.append({
                'state': st, 'frame': f, **s, 'skeleton': skel,
                'slack': s['total'] - skel - parts, 'census': c,
                'table': before_table, 'pool_bytes': before_pool,
            })
        print(f'  {st}: {frames} interrupts')
    img = {'note': ('Per-interrupt ISR costs, each half bracketed by CONTROL FLOW inside the '
                    'interrupt. `slack` is total - skeleton - parts and MUST be 0: the parts tile '
                    'the whole. Skeleton constants are the MEASURED segment decomposition.'),
           'segments': SEG, 'skeleton': {f'{k[0]}_{"open" if k[1] else "closed"}': v
                                         for k, v in SKEL.items()},
           'states': STATES, 'branch_checked': '$8DC4 == $C9 for every state',
           'rows': rows}
    json.dump(img, open(FIXTURE, 'w'), indent=1)
    nz = sum(1 for r in rows if r['slack'] != 0)
    print(f'wrote {FIXTURE}: {len(rows)} interrupts, {nz} with non-zero slack')
    if nz:
        bad = [r for r in rows if r['slack'] != 0][:3]
        for r in bad:
            print(f"   SLACK {r['state']} f{r['frame']} odd={r['odd']} gate={r['gate']} "
                  f"total={r['total']} skel={r['skeleton']} slack={r['slack']}")


def verify():
    fx = json.load(open(FIXTURE))
    rows = fx['rows']
    nz = [r for r in rows if r['slack'] != 0]
    print(f'{len(rows)} interrupts, slack non-zero on {len(nz)}')
    import collections
    for key in ('odd', 'even'):
        for gate in (True, False):
            sel = [r for r in rows if (r['odd'] == (key == 'odd')) and r['gate'] == gate]
            if not sel:
                continue
            tot = sorted(r['total'] for r in sel)
            print(f"  {key}/{'open  ' if gate else 'closed'}  n={len(sel):4d}  "
                  f"total min/med/max = {tot[0]}/{tot[len(tot)//2]}/{tot[-1]}  "
                  f"skeleton={sel[0]['skeleton']}")
    over = [r for r in rows if r['total'] > 69888]
    print(f'  interrupts exceeding one frame (69888 T): {len(over)}')
    return 1 if nz else 0


if __name__ == '__main__':
    v = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if v == 'capture':
        capture()
    else:
        sys.exit(verify())
