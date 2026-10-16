"""M7.45b -- THE ITEM AGE oracle: where $86CE/$86CF come from, and what an item does on the
machine when nothing kills it early.

THE BYTES.  $86CC..$86CF is `LD A,n / AND n` -- $86CD, the LD's operand, is the item clock
($8688 INC (HL) counts it), $86CE is the AND OPCODE ($E6) and $86CF its operand, the MASK.
$86D0 INC HL does not touch the flags, so $86D1 JR nz reads the AND: an item's phase steps
only when (clock AND mask) == 0.  The port's reset() left $86CE/$86CF at zero, the mask was
0, every call stepped the phase, and every item died three calls after it appeared.

WHAT IS MEASURED, and nothing is assumed:
  provenance  the tape image (build/image_tape.bin) and the live dump (build/image.bin) at
              $86CC..$86CF; a CENSUS of every shipped state (build/*.pkl); a WRITE WATCH over
              $86CC..$86CF, by writer PC, across (a) afterctrl48 -> '1' -> the title, the game
              start, the round-1 build and 300 ISRs of play, and (b) round1_48 driven by the
              pop-kill scene N1 through the three kills, the clear ($8ECF) and the advance
              ($97F8) into round 2.
  the drive   round1_48, N1's key script to ISR 299; SEED = the RAM vector after ISR 299's RET
              (tools/popkill.py's vector WITHOUT $86CE/$86CF -- the engine must supply those
              itself, which is the point -- plus the item pass's own scalars); then P1 holds
              RIGHT ('8' under round1_48's CURSOR table) and every ISR's item table, P1 X and
              score are recorded until the landed fruit in entry 2 ($9607) is COLLECTED --
              and (M7.73) the ISR's T, $8D72 to just past its RET: where it runs past a frame
              the machine loses the next interrupt, and the engine's drive must too.
No ROM byte is stored; the seed is RAM regions and scalars only.

Usage:  python tools/itemage.py capture   -> build/itemage_fixture.json
        python tools/itemage.py verify
"""
import sys, os, json, base64, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Harness, PC, T
import portconfig as pc
from keyprobe import press
import popkill as PK

FIXTURE = 'build/itemage_fixture.json'
WATCH = (0x86CC, 0x86D0)
EXTRA = [0x8680, 0x872C, 0x8908, 0x8909, 0x8CB0, 0x86CD]
SEED_AT = 299
VEC = [a for a in PK.VEC if a not in (0x86CE, 0x86CF)]
VEC += [a for a in EXTRA if a not in VEC]


def census():
    """[$86CD, $86CE, $86CF, loaded] per state.  `loaded` = the ISR's own code $8D72..$8DA1 is
    the tape's: a state taken before the game's code block is in memory (the loader's) says
    nothing about these bytes, and is reported rather than dropped."""
    tape = open('build/image_tape.bin', 'rb').read()
    out = {}
    for p in sorted(glob.glob(os.path.join(pc.path(pc.get('z80', 'states')), '*.pkl'))):
        h = Harness(); h.load_state_file(p); m = h.memobj.m
        loaded = bytes(m[0x8D72:0x8DA2]) == tape[0x8D72:0x8DA2]
        out[os.path.splitext(os.path.basename(p))[0]] = [m[0x86CD], m[0x86CE], m[0x86CF], int(loaded)]
    return out


def images():
    out = {}
    for k, f in (('tape', 'build/image_tape.bin'), ('live', 'build/image.bin')):
        b = open(f, 'rb').read()
        out[k] = list(b[0x86CC:0x86D0])
    return out


def watch_front():
    """afterctrl48 -> '1' -> play; every write to $86CC..$86CF by writer PC"""
    h = Harness(); h.load_state_file(pc.state_path('afterctrl48')); m = h.memobj.m
    mem = h.memobj
    mem.watch(*WATCH)
    started, frames = None, 0
    for f in range(3000):
        h.ports.release_all()
        if 100 <= f < 160:
            press(h.ports, '1')
        h.run_frames(1)
        frames = f + 1
        if started is None and m[0x8609] == 1 and m[0xFEC4] and m[0xFD87] & 0x80:
            started = f
        if started is not None and f >= started + 300:
            break
    mem.unwatch()
    return dict(frames=frames, play_at=started, round=m[0x8609], writes=tally(mem.log),
                end=[m[0x86CD], m[0x86CE], m[0x86CF]])


def tally(log):
    t = {}
    for pcw, a, v in log:
        k = '%04X>%04X' % (pcw, a)
        t[k] = t.get(k, 0) + 1
    return t


def watch_n1():
    """round1_48 through N1's kills, the clear and the advance into round 2 (the ISRs are
    run here, not through PK.Run.isr, whose display watch would replace this one)"""
    run = PK.Run('round1_48')
    h, m, mem = run.h, run.m, run.h.memobj
    run.run_to(PK.ISR_IN)
    mem.watch(*WATCH)
    adv_at, i = None, 0
    for i in range(1400):
        keys, kemp = PK.keys_n1(i)
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        h.ports.kempston = kemp
        run.in_isr = True
        run.run_to(PK.ISR_OUT)
        h.step(1)
        run.in_isr = False
        run.run_to(PK.ISR_IN)
        if run.advance and adv_at is None:
            adv_at = i
        if adv_at is not None and i >= adv_at + 150:
            break
    mem.unwatch()
    return dict(isrs=i + 1, advance_after=adv_at, round=m[0x8609], writes=tally(mem.log),
                end=[m[0x86CD], m[0x86CE], m[0x86CF]])


def drive():
    """round1_48 with N1's keys to ISR 299, then RIGHT held.  Row j = the machine just past
    ISR j's RET (j > 299); the SEED is the same sample at j = 299.  So engine step k (main
    loop, then ISR) lands on row 300 + k."""
    run = PK.Run('round1_48')
    h, m = run.h, run.m
    run.run_to(PK.ISR_IN)
    seed, rows = None, []
    for i in range(1000):
        keys, kemp = PK.keys_n1(i) if i <= SEED_AT else (['8'], 0)
        h.ports.release_all()
        for k in keys:
            press(h.ports, k)
        h.ports.kempston = kemp
        run.ev, run.r, run.mev = [], [], []
        run.in_isr = True
        t0 = h.sim.registers[T]
        run.run_to(PK.ISR_OUT)
        h.step(1)
        run.in_isr = False
        row = None
        if i == SEED_AT:
            run.glyph_scan('the item seed')          # no stored display cell is a ROM glyph
            seed = [m[a] for a in VEC]
        elif i > SEED_AT:
            row = dict(i=i, items=[[j, m[0x9603 + 2 * j], m[0x9604 + 2 * j]] for j in range(32)
                                   if m[0x9603 + 2 * j]],
                       x=m[0xFD85], score=list(m[0xFFE5:0xFFE9]), clock=m[0x86CD],
                       t=h.sim.registers[T] - t0)
            rows.append(row)
        run.mev = []
        run.run_to(PK.ISR_IN)                          # the main loop after ISR i
        if row is not None:
            row['mev'] = [e for e in run.mev if e[0] in ('award', 'clear')]
            if not any(e[0] == 2 for e in row['items']):
                break
    gone = next((r['i'] for r in rows if not any(e[0] == 2 for e in r['items'])), None)
    e2 = next((e for e in rows[0]['items'] if e[0] == 2), None) if rows else None
    return dict(seed_at=SEED_AT, keys_after='8', seed=base64.b64encode(bytes(seed)).decode(),
                rows=rows, entry2=e2, collected_at=gone)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('capture', 'verify'):
        print(__doc__); sys.exit(2)
    out = dict(tool='tools/itemage.py', images=images(), census=census(),
               watch_front=watch_front(), watch_n1=watch_n1(),
               vector=PK.ranges_of(VEC), vector_len=len(VEC))
    out['drive'] = drive()
    C = out['census']; W1 = out['watch_front']; W2 = out['watch_n1']; D = out['drive']
    claims = []

    def claim(name, held, measured):
        claims.append(dict(claim=name, held=bool(held), measured=measured))
        if not held:
            print('  !! REFUTED:', name, measured)
    claim('$86CE/$86CF are TAPE bytes: $E6 $FF (AND $FF) in the tape image and the live dump',
          out['images']['tape'][2:] == [0xE6, 0xFF] and out['images']['live'][2:] == [0xE6, 0xFF],
          out['images'])
    claim('every shipped state with the game loaded holds $E6 $FF there',
          all(v[1:3] == [0xE6, 0xFF] for v in C.values() if v[3]) and sum(v[3] for v in C.values()) >= 50,
          dict(states=len(C), loaded=sum(v[3] for v in C.values()),
               not_loaded=[k for k, v in C.items() if not v[3]],
               odd=[k for k, v in C.items() if v[3] and v[1:3] != [0xE6, 0xFF]]))
    claim('NOTHING WRITES $86CE/$86CF from the control select to play, nor through a round clear and advance',
          not any(k.endswith('>86CE') or k.endswith('>86CF') for k in list(W1['writes']) + list(W2['writes'])),
          dict(front=W1['writes'], n1=W2['writes']))
    claim('$86CD is the tape $03 until play, then counted by $8688 INC (HL) alone; $8EDC stores $FF at the clear',
          C.get('boot', [0])[0] == 3 and C.get('afterctrl48', [0])[0] == 3 and C.get('play1p48', [0])[0] == 3 and
          set(W1['writes']) == {'8688>86CD'} and set(W2['writes']) <= {'8688>86CD', '8EDC>86CD'} and
          '8EDC>86CD' in W2['writes'],
          dict(front=W1['writes'], n1=W2['writes']))
    got = D['collected_at']
    prev = next((r for r in D['rows'] if r['i'] == (got or 0) - 1), None)
    last = D['rows'][-1] if D['rows'] else None
    claim('the landed fruit PERSISTS and is COLLECTED by walking onto it: entry 2 lives through %s ISRs of P1 walking right, and the main loop that takes it pays P1 ($80FA A=1)' % (
              (got or 0) - SEED_AT - 1),
          got is not None and got - SEED_AT > 100 and prev is not None and
          any(e == ['award', 1] for e in prev['mev']) and last['score'] != prev['score'],
          dict(collected_at=got, award=prev and prev['mev'], score=[prev and prev['score'], last and last['score']]))
    out['assertions'] = claims
    if sys.argv[1] == 'capture':
        json.dump(out, open(FIXTURE, 'w'), separators=(',', ':'))
        print('wrote', FIXTURE, os.path.getsize(FIXTURE), 'bytes;', sum(c['held'] for c in claims), 'of',
              len(claims), 'claims held; entry 2 gone after ISR', D['collected_at'])
    else:
        old = json.load(open(FIXTURE))
        same = json.dumps(old, sort_keys=True) == json.dumps(json.loads(json.dumps(out)), sort_keys=True)
        print('verify:', 'IDENTICAL' if same else 'DIFFERS'); sys.exit(0 if same else 1)
    if not all(c['held'] for c in claims):
        sys.exit(1)


if __name__ == '__main__':
    main()
