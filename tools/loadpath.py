"""M7.64: THE WHOLE LOAD, ONE DRIVE -- from boot.pkl's own $F5BC through player 1's pass, the redefine
screen (when a player takes KEYBOARD), player 2's pass, the black screen, the 48K/128K probe $FAC3
(RUN, not skipped), the hand-over $F5CC..$970E and on into the title, the keys of a per-frame
script applied at each frame boundary.  The stages were measured one at a time (ctrlmenu.py,
redefine.py, loadspine.py); this is the machine the PAGE is diffed against, frame for frame.

A sample at every frame boundary: [frame, stage, pass, border, CRC-32 of the bitmap $4000..$57FF,
CRC-32 of the attributes $5800..$5AFF] (the bitmap's text is the ROM font's here and the substitute's
in the port -- the no-ROM rule -- so only the attributes can agree where there is text).  The stage
is the label of the last mark the machine passed:
    $F5E7 'menu' (A = '1' or '2' names the pass)   $F723 'redefine'   $F5C6 'spine'
    $F5C9 'probe'   $F5CC 'hand'   $970E 'title'
the border is the last OUT ($FE)'s low three bits.  At the end: the frame and T (past the drive's
first boundary) of each mark's first pass, the key table $B5FD..$B60C and the staging buffer.

Keys change BETWEEN SCANS, as ctrlmenu.Nat has it: an explicit scan in flight at a boundary
($F7B8's RST $38 .. $F7B9) finishes on the keys it began with.

GUARDED: every run stops with an error if PC enters $D000..$D2FF (the 128K driver).  No ROM byte is
recorded: key NAMES, counts, T, CRCs of the display and game-RAM bytes only.

Usage:  python tools/loadpath.py [capture|verify]  -> build/loadpath_fixture.json
"""
import sys, os, json, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctrlmenu as cm
from ctrlmenu import world, Fail, GUARD, FRAME_T, expand, OUTS, click_out
from harness import PC, T, IFF, A as RA

FIXTURE = 'build/loadpath_fixture.json'
MARKS = {0xF723: 'redefine', 0xF5C6: 'spine', 0xF5C9: 'probe', 0xF5CC: 'hand', 0x970E: 'title'}
AFTER = 40                                     # frames sampled past $970E

SCRIPTS = {
    #  player 1 KEYBOARD, redefined O / P / SPACE / Q (left, right, BLOW, JUMP: the
    #  screen's order) and confirmed -- the key table BB_KEYTAB, the test world's; player 2 SINCLAIR ('6790')
    'kbd_sinclair': [(8, []), (2, ['1']), (12, []), (2, ['O']), (8, []), (2, ['P']), (8, []), (2, ['SPACE']),
                     (8, []), (2, ['Q']), (8, []), (2, ['Y']), (16, []), (2, ['2']), (12, [])],
    #  player 1 CURSOR, player 2 KEMPSTON
    'cursor_kempston': [(8, []), (3, ['4']), (14, []), (3, ['3']), (12, [])],
}


def drive(script):
    h, m, r = world('boot')
    seq = expand(script)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    nb0 = nb
    out0 = len(OUTS)
    frame, stage, pass_ = 0, 'menu', 1
    in_scan, pending = False, None
    title_frame = None
    marks, rows = {}, []
    cm.keys(h, keyf(0))

    def border():
        for t, p, port, v in reversed(OUTS[out0:]):
            if port == 0xFE and not click_out(p):
                return v & 7
        return None

    while True:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            if in_scan:
                pending = keyf(frame)
            else:
                cm.keys(h, keyf(frame))
            rows.append([frame, stage, pass_, border(), zlib.crc32(bytes(m[0x4000:0x5800])),
                         zlib.crc32(bytes(m[0x5800:0x5B00]))])
            nb += fd
            if title_frame is not None and frame >= title_frame + AFTER:
                break
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in GUARD:
            raise Fail('PC entered the guard at $%04X' % pc)
        if pc == 0xF5E7:
            stage, pass_ = 'menu', (1 if r[RA] == 0x31 else 2)
        elif pc in MARKS:
            stage = MARKS[pc]
            if stage not in marks:
                marks[stage] = [frame, r[T] - nb0]
            if stage == 'title' and title_frame is None:
                title_frame = frame
        if pc == 0xF7B8:
            in_scan = True
        if mem[pc] == 0x76 and r[IFF]:            # a HALT: the clock to the boundary
            h._fast_halt()
            continue
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            sim.accept_interrupt(r, mem, pc)
    return {'rows': rows, 'marks': marks, 'keytab': list(m[0xB5FD:0xB60D]),
            'buffer': list(m[0xF5D2:0xF5E2])}


def capture():
    h, m, r = world('boot')
    out = {'meta': {'tool': 'tools/loadpath.py', 'no_rom_bytes': True,
                    'note': 'key NAMES, stage labels, border colours, display CRC-32s, T and game-RAM bytes'},
           'boot_phase': r[T] % FRAME_T, 'after': AFTER, 'scripts': {}}
    for name, script in SCRIPTS.items():
        d = drive(script)
        d['script'] = [[n, k] for n, k in script]
        out['scripts'][name] = d
        labs = []
        for row in d['rows']:
            if not labs or labs[-1][0] != row[1]:
                labs.append([row[1], row[0]])
        print('%-16s %d frames; %s' % (name, len(d['rows']), ' '.join('%s@%d' % (a, b) for a, b in labs)))
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'capture'
    if cmd == 'capture':
        out = capture()
        json.dump(out, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes')
    elif cmd == 'verify':
        old = json.load(open(FIXTURE, encoding='utf-8'))
        new = json.loads(json.dumps(capture()))
        bad = sorted(set(k for k in set(old) | set(new) if old.get(k) != new.get(k)))
        print('verify:', 'MATCH' if not bad else 'DIFFER in %s' % bad)
        return 1 if bad else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
