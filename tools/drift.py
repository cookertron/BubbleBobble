"""M7.7-H4 -- THE BUBBLE DRIFT FIELD: bits 6/7 of the colour shadow, and $B8DB.

A WHOLE SUBSYSTEM THE READING PASS DID NOT KNOW EXISTED, and one its own
grep-based reasoning declared possibly unread: "a grep finds no AND $40 and only
two AND $80".  THE GREP WAS TRUE AND THE INFERENCE WAS FALSE -- the read is a
TRIPLE ROTATE:

    $B843  CALL $AEDC          HL := the colour-shadow cell for the bubble's X,Y
    $B846  LD A,(HL)
    $B847  RLCA / RLCA / RLCA  bit 6 -> bit 1, bit 7 -> bit 2
    $B84A  AND 6               so the code is 2 * ((v >> 6) & 3)
    $B857  LD BC,$B8DB / ADD HL,BC

    $B8DB:  00 FF | 01 00 | 00 01 | FF 00
    code 0 (bits 00) -> ( 0,-1) UP      code 4 (bits 10) -> ( 0,+1) DOWN
    code 2 (bits 01) -> (+1, 0) RIGHT   code 6 (bits 11) -> (-1, 0) LEFT

SO THE COLOUR SHADOW HAS THREE LIVES, not two: bits 0-4 a live per-cell bubble
occupancy claim, bit 5 the static SOLID flag (H3), and BITS 6-7 A STATIC
PER-ROUND DRIFT DIRECTION.

*** THE PAINTER IS DEFERRED AND NAMED. ***  $7C57-$7E4A -- the three fixed
rectangles, the per-round $79AF stream with its sixteen $Fx redirects, the $7D50
mirror, the four doors and the rotating pattern table -- is ~500 bytes of
compressed table walking, and the reading pass's (a) asks for a Python decode of
it diffed against the machine on all 81 rounds.  THAT IS NOT DONE HERE.  Instead
the FIELD ITSELF is captured per round and carried as a declared asset, exactly
as $5D00's item bank is carried until its builder is found, and the port ORs it
in after H3's collision transform.  When the painter is transliterated the asset
should be DELETED, not kept as a cross-check.

AND THE RULE THIS INCREMENT EXISTS TO WRITE DOWN:
*** ANY "UNREAD" CLAIM IN THIS PORT MUST CARRY THE FRAME COUNT THAT MADE IT
TRUE. ***  An 80-frame differential over seven states says bits 6/7 are unread --
every run identical -- while the same rig at 600 frames on r6_48 diverges at
frame 108, which is the frame the first bubble reaches the drift stage.  A port
built on the 80-frame answer looks right for two seconds of round 1 and is wrong
everywhere after.

Usage:  python tools/drift.py capture
        python tools/drift.py verify
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, PC
import portconfig as pc
import roundclass as RC

MAP, MAP_N = 0xF800, 0x300
FULL = 0x79AC
TABLE = 0xB8DB
CODE_OP = 0xB892          # $B84C LD (nn),A -- the code, as a self-modified operand
FIXTURE = 'build/drift_fixture.json'
SEEDS = (0x47, 0x57, 0x46, 0x66, 0x45, 0x65, 0x00, 0xFF)


def codes(m):
    """The 768 two-bit codes, as the machine's own RLCA x3 / AND 6 computes them."""
    return [2 * ((m[MAP + i] >> 6) & 3) for i in range(MAP_N)]


def pack(cs):
    """Four cells to a byte -- the field is 2 bits per cell, so 192 bytes a round."""
    out = bytearray()
    for i in range(0, len(cs), 4):
        b = 0
        for k in range(4):
            b |= ((cs[i + k] >> 1) & 3) << (2 * k)
        out.append(b)
    return bytes(out)


# ------------------------------------------------- the field, all 81 rounds
def field_rows(h, m):
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        cs = codes(m)
        rows.append({'round': m[RC.ROUND],
                     'packed': base64.b64encode(pack(cs)).decode(),
                     'counts': [cs.count(c) for c in (0, 2, 4, 6)]})
    return rows


def seed_independence(h, m):
    """The field reads NOTHING from the map: the same round with the colour
       shadow pre-seeded eight different ways gives the same 768 codes."""
    out = []
    for seed in SEEDS:
        for i in range(MAP_N):
            m[MAP + i] = seed
        sp = RC.arm(h, FULL)
        RC.run(h, sp)
        out.append({'seed': seed, 'codes': codes(m)})
    same = all(r['codes'] == out[0]['codes'] for r in out)
    return {'identical': same, 'codes': out[0]['codes'],
            'seeds': [r['seed'] for r in out]}


def overflow_row(h, m):
    """ROUND $2D writes FIFTEEN cells OUTSIDE the map.  Every other round writes
       none, so the port's choice to bounds-check or not is a DECLARED
       DEPARTURE and this is the round it shows on."""
    RC.suppress_warp(m)
    m[RC.ROUND] = 0x00
    rows = []
    for _ in range(81):
        RC.seed_round(m)
        RC.suppress_warp(m)
        h.memobj.watch(0xFB00, 0x10000)
        sp = RC.arm(h, RC.ADVANCE)
        RC.run(h, sp)
        h.memobj.unwatch()
        out = [(p, a) for (p, a, _v) in h.memobj.log if 0xFB00 <= a < 0xFC00]
        if out:
            rows.append({'round': m[RC.ROUND], 'n': len(out),
                         'at': ['%04X' % a for a in sorted(set(a for (_p, a) in out))],
                         'pcs': sorted(set('%04X' % p for (p, _a) in out))})
    return rows


# ------------------------------------------------------------ the consumer
def table_row():
    img = open('build/image.bin', 'rb').read()
    t = list(img[TABLE:TABLE + 8])
    out = []
    for code in (0, 2, 4, 6):
        dx, dy = t[code], t[code + 1]
        out.append({'code': code, 'bits': (code >> 1),
                    'dx': dx - 256 if dx > 127 else dx,
                    'dy': dy - 256 if dy > 127 else dy})
    return {'bytes': t, 'deltas': out}


def live_codes(states=('r6_48', 'r10_48', 'r20_48', 'hurryup', 'water',
                       'round1_48', 'boss')):
    """$B84C stores the code into $B892.  Watch that byte over 600 frames and
       see which codes a real game actually reaches."""
    rows = []
    for st in states:
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if m[0x8DC4] != 0xC9:
            continue
        h.memobj.watch(CODE_OP, CODE_OP + 1)
        h.run_frames(600, interrupts=True)
        h.memobj.unwatch()
        vals = [v for (_p, _a, v) in h.memobj.log]
        rows.append({'state': st, 'round': m[0x8609], 'reads': len(vals),
                     'codes_seen': sorted(set(vals))})
    return rows


# ------------------------- THE RULE: an "unread" claim carries a frame count
def unread_rows():
    """MUTATE bits 6/7 of every map cell and compare the game against itself.

       At 80 frames the two runs are IDENTICAL in every state -- which reads as
       "nothing reads bits 6/7" and is FALSE.  At 600 frames they diverge, and
       the frame they diverge on is the frame the first bubble reaches the drift
       stage.  A control mutation on BIT 5 diverges almost at once, which is what
       says the rig works."""
    rows = []
    for st in ('r6_48', 'r10_48', 'hurryup', 'water', 'round1_48'):
        for (tag, mask, val) in (('bits 6/7 flipped', 0xC0, None),
                                 ('bit 5 flipped (CONTROL)', 0x20, None)):
            for frames in (80, 600):
                h = Harness()
                h.load_state_file(pc.state_path(st))
                m = h.memobj.m
                if m[0x8DC4] != 0xC9:
                    continue
                base = fingerprints(h, frames)
                h = Harness()
                h.load_state_file(pc.state_path(st))
                m = h.memobj.m
                for i in range(MAP_N):
                    m[MAP + i] ^= mask
                mut = fingerprints(h, frames)
                first = None
                for i in range(min(len(base), len(mut))):
                    if base[i] != mut[i]:
                        first = i
                        break
                rows.append({'state': st, 'mutation': tag, 'frames': frames,
                             'diverged_at': first})
    return rows


def fingerprints(h, frames):
    """One number a frame, from the bubble pool and the entity table."""
    out = []
    m = h.memobj.m
    for _ in range(frames):
        h.run_frames(1, interrupts=True)
        s = 0
        for i in range(120):
            s = (s * 31 + m[0xFED8 + i]) & 0xFFFFFFFF
        for i in range(120):
            s = (s * 31 + m[0xFD80 + i]) & 0xFFFFFFFF
        out.append(s)
    return out


def capture():
    h, m = RC.new()
    field = field_rows(h, m)
    h, m = RC.new()
    over = overflow_row(h, m)
    h, m = RC.new()
    indep = seed_independence(h, m)
    fx = {'note': __doc__.strip(), 'map_at': MAP, 'map_n': MAP_N,
          'table_at': TABLE, 'code_op_at': CODE_OP, 'full_at': FULL,
          'field': field, 'table': table_row(), 'independence': indep,
          'overflow': over, 'live': live_codes(), 'unread': unread_rows()}
    json.dump(fx, open(FIXTURE, 'w'))
    print('wrote %s: %d rounds of field' % (FIXTURE, len(field)))
    t = fx['table']
    for d in t['deltas']:
        print('  code %d (bits %s) -> (%+d, %+d)'
              % (d['code'], format(d['bits'], '02b'), d['dx'], d['dy']))
    print('  the field is seed-independent: %s' % indep['identical'])
    print('  rounds writing OUTSIDE the map: %s'
          % [(r['round'], r['n']) for r in over])


def verify():
    fx = json.load(open(FIXTURE))
    print('THE FIELD, code counts per round (UP / RIGHT / DOWN / LEFT):')
    for r in fx['field']:
        if r['round'] in (1, 2, 5, 20, 45, 0x2D, 80, 81):
            print('   round %2d: %s' % (r['round'], r['counts']))
    print()
    print('WHO READS IT, over 600 frames:')
    for r in fx['live']:
        print('   %-11s round %2d: %4d reads, codes seen %s'
              % (r['state'], r['round'], r['reads'], r['codes_seen']))
    print()
    print('*** THE FRAME-COUNT RULE ***')
    for r in fx['unread']:
        print('   %-11s %-26s %3d frames -> %s'
              % (r['state'], r['mutation'], r['frames'],
                 'IDENTICAL (reads as unread)' if r['diverged_at'] is None
                 else 'diverged at frame %d' % r['diverged_at']))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    {'capture': capture, 'verify': verify}[cmd]()
