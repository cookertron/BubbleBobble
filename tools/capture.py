"""Re-baseline capture driver.

Every behavioural fixture is re-captured at a STRUCTURAL boundary instead of a
fixed T offset:  run to the ISR entry $8D72, step into it, run to its RET
$8DA1, step over that, THEN sample.  The ISR's length is state-dependent
(measured 1841 T empty to >112000 T with a full bubble pool), so any fixed
`t0 + k*FRAME_T` phase slices a pass in half -- which is exactly how the bogus
slot-split manager model got in (TRAPS #34).

Every row also records the sample PC, so a future reader can see at a glance
that rows land at the boundary and not mid-routine.
"""
import sys
sys.path.insert(0, 'tools')
from harness import Harness, T, PC
import portconfig as pc
from keyprobe import press

ISR_IN, ISR_OUT = 0x8D72, 0x8DA1


def new(state):
    h = Harness()
    h.load_state_file(pc.state_path(state))
    return h, h.memobj.m


def frame(h):
    """advance exactly one [main loop][ISR] and stop just past the ISR RET"""
    h.run_until((ISR_IN,), limit=10 ** 7, stride=1)
    h.step(1)
    h.run_until((ISR_OUT,), limit=10 ** 7, stride=1)
    h.step(1)


def drive(state, script, n, sample, pokes=None, align=True, kempston=None):
    """script: {frame_index: 'key' or None to release or a list of keys}
       sample: fn(m) -> dict of the row's fields
       pokes:  {addr: value} applied once at load
       kempston: {frame_index: bits} for the P2 Kempston port"""
    h, m = new(state)
    if callable(pokes):
        pokes(m)                     # for pokes that depend on the loaded state
    else:
        for a, v in (pokes or {}).items():
            m[a] = v
    if align:
        frame(h)                     # land on a boundary before recording
    seed = {
        "8DBD": m[0x8DBD] | (m[0x8DBE] << 8),
        "8DB6": m[0x8DB6] | (m[0x8DB7] << 8),
        "AA65": m[0xAA65], "FEC4": m[0xFEC4], "FEC5": m[0xFEC5],
        "FEC9": m[0xFEC9], "FED0": m[0xFED0], "B657": m[0xB657],
        "FDDE": m[0xFDDE], "FDDF": m[0xFDDF], "FDE0": m[0xFDE0],
        "slot0": [m[0xFD80 + i] for i in range(10)],
        "slot1": [m[0xFD8A + i] for i in range(10)],
        "pers1": [m[0xFDDA + i] for i in range(10)],
        "pers2": [m[0xFDE4 + i] for i in range(10)],
    }
    rows = []
    for k in range(n):
        if k in script:
            h.ports.release_all()
            keys = script[k]
            if keys:
                for key in ([keys] if isinstance(keys, str) else keys):
                    press(h.ports, key)
        if kempston is not None and k in kempston:
            h.ports.kempston = kempston[k]
        frame(h)
        r = sample(m)
        r["pc"] = h.regs[PC]
        rows.append(r)
    return seed, rows


def check_boundary(rows):
    """The sample point is structural by construction (just past the ISR RET),
    but the PC there is the INTERRUPTED MAIN-LOOP address, which legitimately
    varies -- the interrupt lands wherever the chain happens to be.  What must
    NOT appear is a PC inside a routine the ISR calls, which would mean the row
    was taken mid-pass (the TRAPS #34 failure).  Returns (ok, offenders)."""
    BAD = ((0xA3AD, 0xA45F), (0xAA60, 0xAB40), (0xB62C, 0xB700),
           (0xB836, 0xB9F0), (0xBD2C, 0xBF40))
    bad = sorted(set(r["pc"] for r in rows
                     if any(lo <= r["pc"] < hi for lo, hi in BAD)))
    return not bad, bad
