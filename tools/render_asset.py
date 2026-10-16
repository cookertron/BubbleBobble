"""M7.3c -- THE PLAYFIELD ATTRIBUTE PAINT, and why the port renders a black screen.

*** THE ROUND RENDER ASSET'S ATTRIBUTE THIRD HELD THE COLOUR SHADOW. ***
`build/render_round1.json`'s `display` is a full 6912-byte display file, and its
attribute third for rows 2..23 is BYTE-IDENTICAL to the `colour` shadow.  It is
not the display's attribute file at all: the machine's round-1 plate holds 525
cells of $47 and 206 of $57 -- the round's OPEN and SOLID palette entries --
where the asset holds $00, $20, $40, $A0, $C0, $E0, which are H3/H4/H5's
solidity, drift and occupancy BIT FIELDS.  Ink 0 on paper 0: black on black.

The asset had no producing tool.  This is it.

AND THE OPEN ITEM'S FRAMING WAS WRONG.  It read "something paints entity colour
and the engine does not model it".  NOTHING paints entity colour: a 60-frame
write watch over $5800..$5AFF on round1_48 records 122 writes and ALL of them
come from $8017, the HUD score.  Rows 2..23 are not touched in play at all.
The enemies are visible because the WHOLE PLAYFIELD carries the round palette
and the sprites inherit it.

WHERE THE ATTRIBUTES COME FROM, MEASURED:
  * $82D6 picks the palette byte `BB_PALETTE[($82D7 - 1) mod 15]`, makes
    solid = (p & $7F) | $40 into ($830A) and open = solid & $47 into ($8309),
    and fills the colour shadow from $F840 with `open`.  PREDICTED AND
    CONFIRMED on six states: round1_48 57/47, r10/r20/r30/r50 55/45, bosshit
    66/46.  $82D7 is a BUILD counter, not the round -- r10, r20, r30 and r50
    all read 2 -- so it must be carried, not derived from ($8609).
  * $823C, the tail of $8216, is a PLAIN LDIR $F840 -> $5840.  It is correct at
    BUILD time, when the shadow still holds the palette bytes; it is wrong over
    a mid-play capture, where the shadow has been repurposed.
  * $8C28 is the one that works on a LIVE shadow: `BIT 5,(HL)` picks ($8309) or
    ($830A) per cell.  Run over round1_48 it changes ONE cell of 704 -- so the
    live display IS that derivation -- and the same derivation predicts 700 of
    704 on round1_48 and 698 of 704 on r20_48.
  * THE CELLS IT DOES NOT PREDICT ARE OWNED BY OTHER PAINTERS, and they are the
    same four every time: row 2 columns 0-1 (the ROUND NUMBER, $7F80) and row 23
    columns 0-3.  They are recorded here rather than smoothed over.

Usage:  python tools/render_asset.py            (rewrite build/render_round1.json)
        python tools/render_asset.py --check    (measure, write nothing)
"""
import sys, json, base64
sys.path.insert(0, 'tools')
from harness import Harness, PC, SP
import portconfig as pc

ASSET = 'build/render_round1.json'
FIXTURE = 'build/attrpaint_fixture.json'
BRANCH_BYTE = 0x8DC4
ATTRS, ATTR_END = 0x5800, 0x5B00
SHADOW = 0xF800
OPEN, SOLID = 0x8309, 0x830A
PAL_IDX = 0x82D7
TILE_IDX = 0x83EC
RESTORE = 0x8C28
PALETTE_AT = 0x858C

def _palette():
    """*** THIS WAS A HARDCODED LIST AND SIX OF THE LAST SEVEN BYTES WERE WRONG.
       ***  It read ...8E, 1F, 96, 9D, AE, 87, 8F, 9F; the image holds
       ...8E, 96, 9C, 0F, 9D, 9F, 8F, 94 -- indices 8, 9, 10, 11, 12 and 14 all
       differ.  It was latent only because the six states this tool samples all
       carry build counter 1, 2 or 5, i.e. indices 0, 1 and 4.  Pointed at a
       round whose counter lands in 9..15 it would silently produce the wrong
       OPEN/SOLID pair, and the visibility gate would not catch it because a
       wrong-but-valid attribute still has ink != paper.  READ IT FROM THE
       IMAGE; nothing writes $858C in 64K."""
    img = open('build/image.bin', 'rb').read()
    return list(img[PALETTE_AT:PALETTE_AT + 15])


PALETTE = _palette()


def new(state):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch' % state)
    return h, m


def b64(bs):
    return base64.b64encode(bytes(bs)).decode('ascii')


def phase_palette():
    """($830A) and ($8309) PREDICTED from the build counter, on six states.
       $82D7 is a BUILD counter and not the round: r10, r20, r30 and r50 all
       read 2, so a port that derives the palette from ($8609) is right on
       round 1 and wrong on four of the five others."""
    out = {'palette': PALETTE, 'states': {}}
    for st in ('round1_48', 'r10_48', 'r20_48', 'r30_48', 'r50_48', 'bosshit'):
        h, m = new(st)
        idx = m[PAL_IDX]
        p = PALETTE[(idx - 1) % 15]
        solid = ((p & 0x7F) | 0x40) & 0xFF
        open_ = solid & 0x47
        out['states'][st] = {
            'round': m[0x8609], 'build_counter': idx,
            'palette_byte': p, 'predicted': [open_, solid],
            'live': [m[OPEN], m[SOLID]], 'byte_860C': m[0x860C],
            'ok': open_ == m[OPEN] and solid == m[SOLID]}
    out['all_predicted'] = all(v['ok'] for v in out['states'].values())
    out['counter_is_not_the_round'] = len(
        set(v['build_counter'] for v in out['states'].values())) < \
        len(set(v['round'] for v in out['states'].values()))
    return out


def phase_derive():
    """THE DERIVATION, against the live display: `BIT 5` on the colour shadow
       picks ($830A) or ($8309).  Reported as the MISMATCH LIST, not a
       percentage, so the cells another painter owns are named."""
    out = {}
    for st in ('round1_48', 'r20_48', 'r50_48'):
        h, m = new(st)
        op, so = m[OPEN], m[SOLID]
        bad = []
        for i in range(0x40, 0x300):
            pred = so if (m[SHADOW + i] & 0x20) else op
            if pred != m[ATTRS + i]:
                bad.append(['%04X' % (ATTRS + i), i // 32, i % 32,
                            m[ATTRS + i], m[SHADOW + i], pred])
        # ...and $8C28 itself, which is the machine's own derivation
        sp = 0x96DD
        for sent in reversed(h.SENTINELS):
            sp = (sp - 2) & 0xFFFF
            m[sp] = sent & 0xFF
            m[sp + 1] = sent >> 8
        h.sim.registers[SP] = sp
        h.sim.registers[PC] = RESTORE
        before = [m[ATTRS + i] for i in range(0x300)]
        h.run_until(tuple(h.SENTINELS), limit=900000, stride=1,
                    interrupts=False)
        changed = [i for i in range(0x40, 0x300) if m[ATTRS + i] != before[i]]
        out[st] = {'round': m[0x8609], 'open': op, 'solid': so,
                   'cells': 704, 'mismatches': len(bad), 'mismatch_list': bad,
                   'changed_by_8C28': len(changed),
                   'changed_cells': ['%04X' % (ATTRS + i) for i in changed]}
    return out


def phase_no_entity_paint():
    """THE OPEN ITEM SAID "something paints entity colour".  NOTHING DOES.
       60 frames of round1_48 with the attribute file watched: every write comes
       from the HUD, and rows 2..23 are never touched.  Carried with its frame
       count (TRAPS #48) and with the enemy positions, so "no writes" and "no
       enemies" cannot be confused."""
    h, m = new('round1_48')
    enemies = []
    for k in range(7):
        b = 0xFD94 + 10 * k
        if m[b + 7] & 0x80:
            enemies.append([k, m[b + 5], m[b + 6], m[b + 7]])
    h.memobj.watch(ATTRS, ATTR_END)
    h.run_frames(60)
    log = list(h.memobj.log)
    h.memobj.unwatch()
    pcs = {}
    rows = {}
    for (p, a, v) in log:
        pcs['%04X' % p] = pcs.get('%04X' % p, 0) + 1
        rows[str((a - ATTRS) // 32)] = rows.get(str((a - ATTRS) // 32), 0) + 1
    under = []
    for (k, x, y, f) in enemies:
        cell = ATTRS + (y // 8) * 32 + (x // 8)
        under.append(['%04X' % cell, m[cell], m[cell + 0xA000]])
    return {'frames': 60, 'writes': len(log), 'writer_pcs': pcs,
            'rows_written': sorted(rows), 'enemies': enemies,
            'attr_under_enemies': under,
            'playfield_rows_untouched': all(int(r) < 2 for r in rows)}


def rebuild_asset(check):
    h, m = new('round1_48')
    d = json.load(open(ASSET))
    disp = bytearray(base64.b64decode(d['display']))
    old = bytes(disp[0x1840:0x1B00])
    new_attrs = bytes(m[ATTRS + 0x40:ATTR_END])
    same = old == new_attrs
    col = base64.b64decode(d['colour'])
    was_shadow = old == col[0x40:0x300]
    if not check:
        disp[0x1840:0x1B00] = new_attrs
        d['display'] = b64(disp)
        d['palette'] = [m[OPEN], m[SOLID]]
        d['build_counter'] = m[PAL_IDX]
        # *** ($83EC) IS CARRIED TOO, AS OF M7.8-A. ***  This tool captured only
        # ($82D7), so the port seeded the tile counter from a bare literal 0
        # while taking the palette counter from here -- and round1_48 carries
        # BOTH at 1.  The pair (1, 0) is one the machine is never in: $83EC ==
        # $82D7 mod 5 on all five shipped states and all 81 chained builds,
        # because both advance by one per build and 5 divides 15.  While the
        # builder was unwired the byte was inert; M7.8-A made it the tile index
        # and every round the port built came out on the PREVIOUS round's tile.
        d['tile_counter'] = m[TILE_IDX]
        # ...and the TILE BUFFER's per-round half.  $856C..$8583 is 24 bytes in
        # TWO halves with different provenance, which BB_TILE_SEED did not mark:
        # the ODD bytes +1..+15 and the whole of +16..+23 are STATIC TAPE DATA
        # that no build ever writes, while the EVEN bytes +0..+14 are PER-ROUND
        # STATE that $8334 rewrites every build.  Seeding all 24 from the tape
        # left the evens at zero where round-1's world holds round 1's tile, so
        # $8207's filler -- which lifts the EVEN bytes BEFORE $830B refills them,
        # the one-round lag -- came out zero where the machine has $87 $0F $1E
        # $3C $78 $F0 $E1 $C3.  The evens are carried from the round's own world.
        d['tile_buf'] = list(m[0x856C:0x856C + 24])
        d['note'] = (d['note'] + '  ATTRIBUTE THIRD CORRECTED 2026-09-22 '
                     '(M7.3c): rows 2-23 held the COLOUR SHADOW, not the '
                     'display attributes -- black on black.  Taken from '
                     'round1_48 $5840..$5AFF, which 60 frames of write-watch '
                     'show is never touched in play (all writes are the HUD). '
                     'Palette and build counter carried, because $82D7 is a '
                     'BUILD counter and cannot be derived from ($8609).')
        json.dump(d, open(ASSET, 'w'))
    from collections import Counter
    return {'attr_third_was_the_colour_shadow': was_shadow,
            # *** THE HISTORICAL MEASUREMENT, RECORDED RATHER THAN RE-DERIVED.
            # ***  `was_shadow` is a live re-measurement of the CURRENT asset,
            # so once M7.3c fixed the asset it reads False forever -- and the
            # gate that asserted it True went red the next time this tool ran.
            # That is TRAPS #97: a fact about a past artifact cannot be
            # recovered by measuring the present one.  These numbers come from
            # git blob 1a2ee8b:build/render_round1.json, the pre-fix asset, and
            # they are frozen here with their provenance.
            # NOTE the count: M7.3c's own write-up says 433 invisible cells.
            # Re-measured on that blob it is 495 of 704 (498 over the whole
            # 768-byte attribute file); 433 is not reproducible under any
            # definition tried, and 495 is what the artifact holds.
            'historical': {
                'blob': '1a2ee8b:build/render_round1.json',
                'attr_third_was_the_colour_shadow': True,
                'invisible_cells_of_704': 495,
                'invisible_over_full_768': 498,
                'note': 'M7.3c reported 433; the artifact measures 495'},
            'already_correct': same,
            'old_values': [['%02X' % k, v] for k, v in
                           Counter(old).most_common(6)],
            'new_values': [['%02X' % k, v] for k, v in
                           Counter(new_attrs).most_common(6)],
            'palette': [m[OPEN], m[SOLID]], 'build_counter': m[PAL_IDX],
            'tile_counter': m[TILE_IDX],
            'invariant_83EC_is_82D7_mod_5': m[TILE_IDX] == m[PAL_IDX] % 5}


if __name__ == '__main__':
    check = '--check' in sys.argv
    fx = {'palette': phase_palette(), 'derive': phase_derive(),
          'no_entity_paint': phase_no_entity_paint()}
    fx['asset'] = rebuild_asset(check)
    for k in fx:
        print('--', k, json.dumps(fx[k])[:700], flush=True)
    if not check:
        json.dump(fx, open(FIXTURE, 'w'), indent=1, sort_keys=True)
        print('\nwrote', FIXTURE, 'and', ASSET)
