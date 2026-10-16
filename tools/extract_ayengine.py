"""M10.1 -- THE AY ENGINE'S BYTES, the shipped asset: build/ay_engine.json (port.json key `aybytes`, required, shipped).

The 128K branch's music engine is 3,860 bytes on the tape at $E6A8..$F5BB, just below the entry $F5BC: its data
(7 sounds x 3 slot streams, $C350..$CF7F once copied), its code ($CF80..$D1E1), its state words ($D1E2..$D1ED, zero) and
its sound table ($D1EE..$D241).  The cold start's 128K leg ($96B3..$96D8) LDIRs them through the display file into bank
1 at $C350..$D263, the rest of bank 1 zero.  The port's JS engine (web/game.js BB_Ay, M10.1) runs over a bank 1 built
from these bytes, and M10.2's leg lays them the way the machine does.

ASSERTED before anything is written:
  - the bytes are build/image_tape.bin's $E6A8..$F5BB;
  - bank 1 after the GAME'S OWN leg on the M10 machine (tools/ayengine.py fresh48: the 48K harness with paging, the
    probe's answer forced to $80, BANKM $10) is exactly these bytes at $C350 and zero elsewhere -- all 16K;
  - that bank's SHA-1 is the oracle fixture's (build/ayengine_fixture.json bank1.sha1, the bank every stream starts
    from), so the asset and the gate's fixture are one bank.
Tape-derived DATA as decoded JSON (house rule 7), like build/tape_bytes.json; no ROM byte.

Usage:  python tools/extract_ayengine.py [extract|verify]       (~3 s)
"""
import sys, os, json, base64, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayengine as ae

OUT = 'build/ay_engine.json'


def sha(b):
    return hashlib.sha1(bytes(b)).hexdigest()


def build():
    n = ae.ENG_HI - ae.ENG_LO
    tape = open(ae.TAPE, 'rb').read()
    src = tape[ae.TAPE_LO:ae.TAPE_LO + n]
    if n != 3860 or len(src) != n or ae.TAPE_LO - ae.ENG_LO != 0x2358:
        raise SystemExit('the copy is not 3,860 bytes from $E6A8 to $C350')
    h, _st = ae.fresh48()                       # the game's own leg; fresh48 asserts the leg ran and the layout
    b1 = bytes(h.paging.bank(1))
    want = bytearray(0x4000)
    want[ae.ENG_LO - 0xC000:ae.ENG_HI - 0xC000] = src
    if b1 != bytes(want):
        bad = [a for a in range(0x4000) if b1[a] != want[a]]
        raise SystemExit('bank 1 after the leg is not the bytes at $C350 and zero elsewhere: %d bytes differ, first $%04X'
                         % (len(bad), 0xC000 + bad[0]))
    fx = json.load(open(ae.FIXTURE))
    if sha(b1) != fx['bank1']['sha1']:
        raise SystemExit('bank 1 is not the oracle fixture\'s (%s, the fixture %s)' % (sha(b1), fx['bank1']['sha1']))
    return {
        'note': ('M10.1 THE AY ENGINE\'S BYTES (tools/extract_ayengine.py): the tape\'s $E6A8..$F5BB, which the cold '
                 'start\'s 128K leg $96B3..$96D8 copies through the display file into bank 1 at $C350..$D263 (the '
                 'rest of bank 1 zero) -- the engine\'s data $C350..$CF7F, code $CF80..$D1E1, state words '
                 '$D1E2..$D1ED and sound table $D1EE..$D241.  Asserted equal to bank 1 after the game\'s own leg on '
                 'the M10 machine, and that bank to build/ayengine_fixture.json\'s.  Read by web/game.js bbAyBytes'),
        'tape': ae.TAPE_LO, 'at': ae.ENG_LO, 'n': n,
        'sha1': sha(src), 'bank1_sha1': sha(b1),
        'b64': base64.b64encode(src).decode(),
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'extract'
    out = build()
    if mode == 'verify':
        same = json.load(open(OUT)) == out
        print('MATCH' if same else 'DIFFERS')
        sys.exit(0 if same else 1)
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote %s: $%04X..$%04X -> $%04X, %d bytes, sha1 %s, bank 1 %s'
          % (OUT, out['tape'], out['tape'] + out['n'] - 1, out['at'], out['n'], out['sha1'], out['bank1_sha1']))


if __name__ == '__main__':
    main()
