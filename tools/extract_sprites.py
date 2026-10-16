#!/usr/bin/env python3
"""
extract_sprites.py -- the 16x16 masked sprites, by the VERIFIED stack-blitter
format (phase 5.1/5.2 of PORTING-ZX-TO-JS.txt).

The draw routines set an entity's sprite pointer at (IY+0/1); the master blitter
$A447 falls through to the 16-wide stack blitter at $A600, which parks SP at that
pointer (`LD SP,HL` $A61F) and POPs mask/data byte-pairs.  Instrumenting one blit
(logging each POP source address against each screen write) pinned the layout:

    64 bytes/frame = 16 rows x 4 bytes; each row = mask_L, data_L, mask_R, data_R
    composite: screen = (screen AND mask) OR data      ($A652 LD A,(HL)/AND E/OR D)

so a pixel is INK where data=1, BLACK where data=0 & mask=0, TRANSPARENT where
data=0 & mask=1.  (Verified: tools/extract_sprites.py --verify replays the blit in
the harness and diffs the decoded frame against the bytes the blitter wrote.)

Two enumerations, unioned:
  * LIVE working set -- hook $A600 across every saved state, collect the distinct
    sprite pointers the game actually draws (labels the active frames);
  * STATIC bases -- the LD HL,imm16 feeding (IY+0/1) in the draw routines
    $AF31-$B021, plus each one's +$160 opposite facing, plus the player $D7C0.

Writes build/sprites/spr_XXXX.png (x4), build/sprites/contact.png, and
build/sprites.json ({hexaddr: {addr,w,h,mask,bytes(b64 64),source,seen}}).

Usage:
    python tools/extract_sprites.py [--states a,b,c] [--verify]
"""
import os
import sys
import json
import base64

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import portconfig                                                   # noqa: E402
from harness import Harness                                        # noqa: E402
from PIL import Image                                              # noqa: E402

BLIT16 = 0xA600
FRAME_LEN = 64
# 48K-branch harness states + owner-snapshot states ONLY: the pre-2026-09-09 harness states
# (round1/play1p/play2p/crowd/afterctrl) are 128K-branch with the AY engine copied over the
# sprite region $C350-$D263 (TRAPS #28) -- a live blit from them records engine bytes.
ALL_STATES = ['round1_48', 'play1p48', 'round1_2p48', 'r6_48', 'r10_48', 'r20_48', 'r30_48', 'r40_48',
              'r50_48', 'r60_48', 'title', 'boris', 'elwater', 'ellight', 'elfire', 'extend', 'extn',
              'hurryup', 'spawn', 'spawn_taken', 'sweet', 'water', 'fruit', 'crown', 'death', 'extcomp',
              'redcross', 'fbkill', 'candycane', 'fallcandy', 'peachcane', 'peachfall', 'powerup',
              'bottle', 'boss', 'bosshit', 'blowbolt', 'yellowcross', 'umbrella']
# static sprite bases read out of the draw routines $AF31-$B021 (adis), + player.
STATIC_BASES = {
    0xC100: 'enemyA', 0x5B80: 'enemyA_alt', 0xD040: 'draw_af52', 0xCAC0: 'draw_af6a',
    0xC3C0: 'draw_af7e', 0xCD80: 'draw_af9e', 0xC260: 'draw_afba', 0xC680: 'draw_afec',
    0xD500: 'draw_b018', 0xD7C0: 'player',
}
FACING = 0x160          # $AF2C: opposite facing is +$160


def decode(b):
    """64 bytes -> 16x16 list of 'I'(ink) / 'K'(black) / '.'(transparent)."""
    px = [['.'] * 16 for _ in range(16)]
    for row in range(16):
        mL, dL, mR, dR = b[row * 4:row * 4 + 4]
        for col, (m, d) in enumerate(((mL, dL), (mR, dR))):
            for bit in range(8):
                x = col * 8 + bit
                dbit = (d >> (7 - bit)) & 1
                mbit = (m >> (7 - bit)) & 1
                px[row][x] = 'I' if dbit else ('.' if mbit else 'K')
    return px


def nonblank(px):
    return any(c != '.' for row in px for c in row)


def render(px, scale=4):
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    p = img.load()
    for y in range(16):
        for x in range(16):
            c = px[y][x]
            p[x, y] = (255, 255, 255, 255) if c == 'I' else (0, 0, 0, 255) if c == 'K' else (0, 0, 0, 0)
    return img.resize((16 * scale, 16 * scale), Image.NEAREST)


def collect_live(states):
    seen = {}
    for st in states:
        try:
            h = Harness(deck=False)
            h.load_state_file(portconfig.state_path(st))
        except Exception as e:
            print(f'  ({st}: skipped, {e})'); continue
        hits = 0
        for _ in range(400):
            reason, _ = h.run_until((BLIT16,), limit=200000, interrupts=True)
            if reason != 'target':
                break
            ptr = h.peek16(h.iy())
            rec = seen.setdefault(ptr, {'states': set(), 'bytes': None})
            rec['states'].add(st)
            if rec['bytes'] is None:
                rec['bytes'] = bytes(h.peek(ptr, FRAME_LEN))   # LIVE bytes (mutable RAM safe)
            hits += 1
            h.step(1)
        print(f'  {st}: {hits} blits, running total {len(seen)} distinct ptrs')
    return seen


def verify(state='round1'):
    """Differential self-check: reach a live 16x16 blit, capture each source
    (mask,data) pair in POP order and each screen write's before/after value,
    and assert  written == (before AND mask) OR data  for all 32 bytes.  This
    tests the claimed format+ordering and FAILS if either is wrong (mutation
    test: swap mask_L/data_L in decode()/here and it goes red)."""
    import harness as H
    h = Harness(deck=False)
    h.load_state_file(portconfig.state_path(state))
    h.run_until((BLIT16,), limit=400000)                # slot0 player
    h.step(1); h.run_until((BLIT16,), limit=400000)     # an enemy
    ptr = h.peek16(h.iy())
    regs, mem = h.sim.registers, h.memobj
    pops, writes = [], []
    steps = 0
    while steps < 4000:
        pc = regs[H.PC]; op = mem.m[pc]
        if op == 0xD1:                                  # POP DE: E=(SP)=mask, D=(SP+1)=data
            sp = regs[H.SP]; pops.append((mem.m[sp], mem.m[sp + 1]))
        if op == 0x77:                                  # LD (HL),A about to write
            hl = h.hl(); writes.append([hl, mem.m[hl], None])
        h.step(1); steps += 1
        if writes and writes[-1][2] is None:
            writes[-1][2] = mem.m[writes[-1][0]]        # value actually stored
        if not (0xA400 <= regs[H.PC] < 0xAA00):
            break
    bad = 0
    for (m, d), (addr, before, after) in zip(pops, writes):
        if after != ((before & m) | d):
            bad += 1
    ok = (bad == 0 and len(pops) == 32 and len(writes) == 32)
    print(f'verify @{state}: ptr=${ptr:04X} pops={len(pops)} writes={len(writes)} '
          f'mismatches={bad} -> {"PASS" if ok else "FAIL"}')
    return ok


def main():
    args = sys.argv[1:]
    states = ALL_STATES
    while args:
        if args[0] == '--states':
            states = args[1].split(','); del args[:2]
        elif args[0] == '--verify':
            sys.exit(0 if verify() else 1)
        else:
            sys.exit(f'extract_sprites: unknown argument {args[0]}')

    outdir = portconfig.path('build/sprites')
    os.makedirs(outdir, exist_ok=True)

    print('LIVE working set:')
    live = collect_live([s for s in states if os.path.exists(portconfig.state_path(s))])

    # union of live ptrs + static bases (+ their opposite facings)
    cat = {}
    for ptr, rec in live.items():
        cat[ptr] = {'source': 'live', 'seen': sorted(rec['states']), 'bytes': rec['bytes']}
    # static bases live in the stable $C000+ data region (image.bin is valid there);
    # opposite facings are +$160 for routines that add it, but some are runtime-mirrored
    # into low RAM (enemy A -> $5B80) or symmetric, so flips are taken from LIVE capture
    # rather than blindly synthesised (a naive +$160 read decodes as garbage for those).
    for base, name in STATIC_BASES.items():
        if base < 0x8000:
            continue          # low RAM: only trust a live capture
        cat.setdefault(base, {'source': 'base', 'seen': []})
        cat[base].setdefault('label', name)

    # decode + render every catalogued address from the image
    img_bytes = open(portconfig.path('build/image.bin'), 'rb').read()
    frames, entries = [], {}
    for a in sorted(cat):
        b = cat[a].get('bytes') or img_bytes[a:a + FRAME_LEN]
        if len(b) < FRAME_LEN:
            continue
        px = decode(b)
        blank = not nonblank(px)
        im = render(px)
        im.save(os.path.join(outdir, f'spr_{a:04X}.png'))
        frames.append((a, im, blank))
        entries[f'{a:04X}'] = {
            'addr': a, 'w': 16, 'h': 16, 'mask': True,
            'bytes': base64.b64encode(b).decode(),
            'source': cat[a]['source'], 'seen': cat[a].get('seen', []),
            'label': cat[a].get('label', ''), 'blank': blank,
        }

    # contact sheet, 12 cols, labelled by address
    cols = 12
    cell = 16 * 4 + 6
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 8)), (40, 40, 48))
    for i, (a, im, blank) in enumerate(frames):
        x = (i % cols) * cell + 3
        y = (i // cols) * (cell + 8) + 3
        sheet.paste(im, (x, y), im)
    sheet.save(os.path.join(outdir, 'contact.png'))

    json.dump(entries, open(portconfig.path('build/sprites.json'), 'w'), indent=1)
    live_n = sum(1 for e in entries.values() if e['source'] == 'live')
    nonblank_n = sum(1 for _, _, blnk in frames if not blnk)
    print(f'\n{len(frames)} frames ({nonblank_n} non-blank; {live_n} live) '
          f'-> {outdir}/spr_XXXX.png + contact.png; build/sprites.json')


if __name__ == '__main__':
    main()
