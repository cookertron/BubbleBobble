#!/usr/bin/env python3
"""
extract_tables.py -- ship the located data tables (phase 5.3) as build/tables.json.

Every table here was found by READING ITS LOADER/CONSUMER elsewhere in the project
(addresses recorded in docs/SPEC.md and tools/varmap.json); this tool just decodes
them from the 64K image so the engine can load them at the original's addresses.
It interprets NOTHING new -- it is the "read the table its decoder reads" step, with
the decode rules taken from the measured consumers.

  python tools/extract_tables.py            # -> build/tables.json (+ summary)

Tape-derived material is never committed (house rule 7); build/*.json = decoded data,
which is fine.
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portconfig                                                    # noqa: E402


def load_image():
    p = portconfig.path(portconfig.get('z80', 'image'))
    if not os.path.exists(p):
        sys.exit(f'extract_tables: no image at {p} -- run tools/snapimport.py first')
    return bytearray(open(p, 'rb').read())


def w16(m, a):
    return m[a] | (m[a + 1] << 8)


def sgn(b):
    return b - 256 if b > 127 else b


def main():
    m = load_image()
    T = {}

    # ---- collectibles $9605: 31 x 2 bytes (byte0=(X&F8)|type, byte1=(Y&F8)|flags) ----
    ent = []
    for i in range(31):
        a = 0x9605 + i * 2
        b0, b1 = m[a], m[a + 1]
        ent.append({'i': i, 'b0': b0, 'b1': b1, 'X': b0 & 0xF8, 'type': b0 & 0x07,
                    'Y': b1 & 0xF8, 'flags': b1 & 0x07})
    T['collectibles'] = {'addr': '0x9605', 'count': 31, 'stride': 2,
                         'note': 'byte0=(X&F8)|type(0-7 -> $861D class); byte1=(Y&F8)|flags. '
                                 'The one live-fruit + spawned-special table (base = entry 0).',
                         'entries': ent}

    # ---- item-class $861D: 16 bytes, collectible type -> class/value index ($FF = "?" random) ----
    T['item_class'] = {'addr': '0x861D', 'count': 16, 'note': 'type nibble -> item class/value ($FF=? random)',
                       'bytes': [m[0x861D + i] for i in range(16)]}

    # ---- power-up selection ramp $8639 (16) + dispatch $8839 (16 x 2-byte handler ptrs) ----
    T['powerup_selection'] = {'addr': '0x8639', 'count': 16,
                              'note': 'per-index ramp; likely the "which power-up spawns next" progression',
                              'bytes': [m[0x8639 + i] for i in range(16)]}
    disp = [{'type': i, 'handler': f'0x{w16(m, 0x8839 + 2 * i):04X}'} for i in range(16)]
    T['powerup_dispatch'] = {'addr': '0x8839', 'count': 16, 'stride': 2,
                             'note': 'collect handler per pu-type (see docs/SPEC "Power-ups -- the dispatch map")',
                             'entries': disp}

    # ---- elemental-per-level scan table $7E4B (scanned by $7DD6 with the round number) ----
    T['elemental_per_level'] = {'addr': '0x7E4B', 'count': 24,
                                'note': 'scanned by $7DD6 vs round $8609 -> elemental type $7E0E '
                                        '(0 none / 2 water / 3 lightning / 4 fire / >=5 randomised)',
                                'bytes': [m[0x7E4B + i] for i in range(24)]}

    # ---- ballistic arc tables (24 signed bytes each) ----
    for name, base, role in (('arc_player', 0xB57D, 'player jump/fall dY, indexed by $FD89 phase'),
                             ('arc_enemy', 0xB59D, 'enemy ballistic arc dY'),
                             ('arc_gentle', 0xB5BD, 'gentler arc (bubble-bounce?)')):
        T[name] = {'addr': f'0x{base:04X}', 'count': 24, 'note': role,
                   'dY': [sgn(m[base + i]) for i in range(24)]}

    # ---- score-display pointer table $85FC (3 live entries: P1 / HIGH / P2 screen positions) ----
    T['score_display_ptrs'] = {'addr': '0x85FC', 'note': 'screen positions for the 3 HUD scores (P1/HIGH/P2)',
                               'ptrs': [f'0x{w16(m, 0x85FC + 2 * i):04X}' for i in range(3)]}

    # ---- element-art pointer table $C068 (elements 2..13: water/lightning/fire + EXTEND letters) ----
    art = []
    labels = {2: 'water', 3: 'lightning', 4: 'fire', 5: 'E', 6: 'X', 7: 'T', 8: 'E',
              9: 'N', 10: 'D', 11: 'E', 12: 'D', 13: '(unused/garbage)'}
    for e in range(2, 14):
        a = 0xC068 + (e - 2) * 2
        art.append({'element': e, 'label': labels.get(e, '?'), 'ptr': f'0x{w16(m, a):04X}'})
    T['element_art'] = {'addr': '0xC068', 'note': 'index = ($7E0E-2); the bubble element/letter glyph source '
                                                  '(elems 5-10 spell E-X-T-E-N-D)', 'entries': art}

    # ---- text string table $9A06 (0-terminated ROM-font strings: ROUND/READY/HURRY UP/GAME OVER/CREDIT) ----
    strs = []
    a = 0x9A06
    while a < 0x9AD0 and len(strs) < 12:
        s = bytearray()
        start = a
        while m[a] not in (0, 0xFF) and a < start + 24:
            s.append(m[a]); a += 1
        txt = ''.join(chr(c) if 32 <= c < 127 else '.' for c in s)
        if txt.strip():
            strs.append({'addr': f'0x{start:04X}', 'text': txt})
        a += 1
    T['text_strings'] = {'addr': '0x9A06', 'note': 'ROM-font message strings (printed via $802E)',
                         'strings': strs}

    out = portconfig.path('build/tables.json')
    json.dump({'_note': 'Data tables decoded from the image by their measured decoders '
                        '(docs/SPEC.md). build/*.json = decoded data, safe to commit.',
               'tables': T}, open(out, 'w'), indent=1)
    print(f'-> {out}')
    for k, v in T.items():
        n = len(v.get('entries', v.get('strings', v.get('bytes', v.get('dY', v.get('ptrs', []))))))
        print(f'  {k:22s} @{v["addr"]:8s} {n} items')


if __name__ == '__main__':
    main()
