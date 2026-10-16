"""THE TAPE'S BYTES THE GAME READS IN PLAY -- the sweep for the class of the giant / Boris bugs, and the blocks it found.

THE CLASS.  A routine reads bytes the TAPE put in RAM that the port never laid down, so its transliteration read zeros.
2026-10-08: the giant peach's and the boss's sprite banks (build/giant_sprites.json).  2026-10-10, the owner: "Boris
doesn't appear after the hurry up" -- his bank $FF50..$FF8F.  Every one hid behind gates that seed their world from the
machine (entdraw's sprites, fireman's read seeds): the seed supplied the missing bytes.  2026-10-11, the owner: "the boss
doesn't move and hitting it once with a lightning bolt kills it straight away" -- its velocities $AA47 / $AA48, which
the STATIC rule below could not see: the bounce WRITES them ($AA43 NEG), so they are live state -- live state that only
the tape initialises.  A bolt that hits skips its own physics ($9F57's return past $9ED0) and dwells while it is
aligned; the machine's boss moves on after a hit or so, the port's stood still and took all 42.  Hence THE CENSUS.

THE SWEEP (`capture` / `verify`, ~6 min on 20 workers).  Every saved state but the front end's (boot, title: the cold
start's copies, which the port lays down as their results -- reloc, coldstart.py) and iball (another image), each run
twice for FRAMES frames: random P1 keys (O P Q SPACE held 4..30 frames) and none (so the hurry and Boris come); and
r60_48 WARPED to every round 1..81 for WARP_FRAMES (lrfree's poke: ($FECD) = 1, ($8609) = r - 1, both warp bits; keys
on the odd rounds) -- the saved states alone reach 25 rounds.  The
simulator's memory is wrapped: for every address >= $5B00 outside the shadow screen ($E000..$F7FF, built by the cold start
and each round), every read made BEFORE the run's first write to it is kept with its PC and kind --
    D  a data read (not the instruction's own bytes PC..PC+3, not the stack window SP-2..SP+1)
    S  a stack-window read (POP blits: $A651.. draws Boris with SP as the source pointer)
    I  one of the executing instruction's own bytes, kept only when the run later WRITES it (a self-modified operand)
-- dropping two kinds that carry no value to anything:
    a HALT's own byte ($76 at PC-1), which the harness re-reads after the PC has moved;
    the shadow<->display copies and merges (COPY_PCS: $A35F, $A4A5.., $A522.., $A5A0.., $A941.., $BA70..$BD30) reading
    $A000..$A9FF -- the shadow's row is the display's + $A0, so the display row is $00..$09, ROM, and the machine drops
    the store.  ASSERTED per read (a display pointer -- DE, HL or $BB40's other-set HL -- on that row), not assumed.
A read is STATIC when no run writes its address at all (a value read before this run's first write can be a live
variable that happens to hold the tape's value: the map, the entity and bubble slots, the self-modified operands); the
shipped blocks' live cells are the exception, listed and checked by name (WRITERS).
THE CENSUS (2026-10-11) -- the rule for live state, which STATIC cannot give: every address any run reads before its
first write (any value, any lineage), with the machine's RAM there at the END of the ISR labelled CENSUS_F on the REAL
LOAD (passacc's world and keys, lrfree's drive -- round 1, P1 in play).  bb.test's TB2 drives the page the same way and
requires its RAM equal at every one, but for a declared list (each still differing, each with its reason); 'tape_read'
marks the addresses where some run read the TAPE'S value, so "read only after a write" is a checked claim.
A read is THE TAPE'S when its value is build/image_tape.bin's -- in a REAL-LOAD state, or, in the eleven built from
build/image.bin (IMAGE_STATES; TRAPS #300: mkimage's guess), only where the two images agree.  boss.pkl equals image.bin
at all 8,253 bytes the images disagree on; the eleven hold image.bin's $EE at $FF67, every other state the tape's $E6.

    -> build/tapereads_fixture.json (test-only): 'reads' [addr, value, kinds, PCs, n states] for every static tape read
       (and every read of a block byte); 'runs'
       (each with every write to a shipped block); 'calls' -- the machine's own runs of the routines that read the
       blocks, for bb.test's TR gates; 'census' {frame, n, runs [[addr, hex of the machine's RAM at frame]],
       tape_read [[addr, n]]} for TB2.

THE BLOCKS (`extract`) -> build/tape_bytes.json (shipped: reset() lays them down):
    $A37D..$A3AC  the lightning bolt ($A2D5's blit from ($FDEE) = $A37D: two bands of eight rows of two bytes) and the
                  fire's two frames ($A04E: $A39D / $A3A5, eight bytes each).  The port drew blank bolts -- the boss fight's
                  too -- and blank flames
    $AAE9         $56: the giant DIAMOND (the candy cane's giant, mailbox 1) is TYPE 0 ($A85C), and $A9C1 reads the award
                  table at $A9EA + (0 - 1) & $FF = $AAE9, the last byte of $AAE6 BIT 2,(IY+7) -- so the diamond awards $56
                  into ($FFEE), +56,000 on the HUD (SPEC, measured live 2026-09-09); the port's was 0
    $FB07..$FB0B, $FB27..$FB2B, $FB47..$FB4B  $40: the 15 cells round 45's paint spills into below the map (rows 24..26).
                  The tape already holds them (the image was saved after a round 45), and the map probes read them in
                  every round before it ($8B6B, $AE89.., $B2DF.., $B3A2.., $B48C..; the engine's enemyProbeAt /
                  bubbleRiseStep).  Live cells: a bubble marks one ($B8C0 stores $4C) and clears it ($B6D6: $40), and
                  round 45's paint ($7E3E) writes them again
    $FF50..$FF8F  Boris's masked 16x16 ($9250's pointer $FF50, drawn by $A447 from $91D6).  NOT read-only: $B7A1, a
                  popped bubble's chain mark, indexes the bubble flags at $FEDF + 10 x (12 - marker) in EIGHT BITS, and
                  markers 20..26 land on $FF8F $FF85 $FF7B $FF71 $FF67 $FF5D $FF53 -- $B7C3 sets bit 3 (and 1) of any whose
                  bits 7 and 2 are set: $FF67's $E6 becomes $EE, one pixel of Boris (water, round 1; umbrella, round 28)
    $AA47..$AA48  $01 $01: the boss's velocities dx / dy -- $AA38 LD A,(DE) with DE = $AA47 then $AA48, the bounce's
                  $AA40 LD A,(DE) / NEG / $AA43 LD (DE),A.  Nothing else writes them: not the round build, not the spawn
                  (bosstick.py).  LIVE: $AA43 is their writer
    $79A3         $05: $79A2 LD A,n's operand -- the boss setup ($72A2 JP nc,$79A2 on rounds 80 and 81) RLCAs it, stores it
                  back ($79A5) and into the HP ($79A8), which $98B2's 42 supersedes two frames on.  LIVE: $79A5
Each ASSERTED here: the tape image's bytes; read in the fixture (every non-zero byte, by the readers named); written in
the sweep by its named writers only (WRITERS); equal in every real-load state.

    python tools/tapereads.py capture [--jobs 20]   # the sweep + the calls -> build/tapereads_fixture.json
    python tools/tapereads.py verify  [--jobs 20]   # re-run, compare
    python tools/tapereads.py extract               # -> build/tape_bytes.json (needs the fixture)
"""
import sys, os, json, glob, random, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ProcessPoolExecutor
from harness import Harness, PC, SP, T, IFF, A, D, E, H, L
from skoolkit.simulator import IYh, IYl
from skoolkit.simutils import REGISTERS
import portconfig as pc
import ctrlmenu as cm
from passacc import SCRIPT

FIXTURE = 'build/tapereads_fixture.json'
OUT = 'build/tape_bytes.json'
FRAMES = 4000
WARP_FRAMES = 1500
WARP_BASE = 'r60_48'
TAPE = open('build/image_tape.bin', 'rb').read()
IMG = open('build/image.bin', 'rb').read()
SHADOW = (0xE000, 0xF800)
SKIP_STATES = {'boot', 'title', 'iball'}
IMAGE_STATES = {'blowbolt', 'boss', 'bosshit', 'bosskilled', 'bossspawn', 'bottle', 'elfire', 'firekill', 'lastdia81',
                'lastdia82', 'umbrella'}
FRONT = {'afterctrl', 'afterctrl48'}            # the control select's states: passacc's script first
XH = REGISTERS['^H']                             # the alternate set's H
COPY_PCS = ({0xA35F, 0xA363} | set(range(0xA4A5, 0xA541)) | set(range(0xA5A0, 0xA5D5)) | set(range(0xBA70, 0xBD31)) |
            set(range(0xA941, 0xA949)))
# the shipped blocks: (at, n, what)
BLOCKS = [
    (0xA37D, 48, 'the lightning bolt ($A2D5 from ($FDEE) = $A37D, 32 bytes) and the fire\'s two frames ($A04E: $A39D, $A3A5)'),
    (0xAAE9, 1, 'the giant diamond\'s award: $A9C1 reads $A9EA + (TYPE 0 - 1) & $FF, the last byte of $AAE6 BIT 2,(IY+7)'),
    (0xFB07, 5, 'round 45\'s paint below the map, row 24 -- on the tape, read by the map probes in every round before it'),
    (0xFB27, 5, '... row 25'),
    (0xFB47, 5, '... row 26'),
    (0xFF50, 64, 'Boris\'s masked 16x16 ($9250 -> $FF50; $A447 from $91D6)'),
    (0xAA47, 2, 'the boss\'s velocities dx / dy ($AA38 LD A,(DE), DE = $AA47 / $AA48): nothing initialises them but the tape'),
    (0x79A3, 1, '$79A2 LD A,n\'s operand: the boss setup\'s seed, RLCA\'d back ($79A5) and into the HP ($79A8)'),
]
CENSUS_F = 600                                   # THE CENSUS's frame: the real load's round 1, P1 in play
WATCH = sorted({a for at, n, _w in BLOCKS for a in range(at, at + n)})
# who may write a block in play: the $FB cells, a bubble's mark and its clear and round 45's paint ($7E3E, the fill's
# store); Boris's bank, $B7A1's chain mark where a
# marker of 20..26 wraps onto it (($FEDF + 10 x (12 - m)) & $FFFF, eight-bit products)
CHAIN_HITS = {(0xFEDF + ((((12 - m) & 0xFF) * 10) & 0xFF)) & 0xFFFF for m in range(1, 32)} & set(range(0xFF50, 0xFF90))
WRITERS = {a: {0xB6D6, 0xB8C0, 0x7E3E} for at, n, _w in BLOCKS if 0xFB00 <= at < 0xFC00 for a in range(at, at + n)}
WRITERS.update({a: {0xB7C3} for a in CHAIN_HITS})
WRITERS.update({0xAA47: {0xAA43}, 0xAA48: {0xAA43}, 0x79A3: {0x79A5}})   # the bounce's NEG; the boss setup's RLCA


class SweepMem:
    """the simulator's memory, recording every read made before the run's first write to its address"""
    __slots__ = ('m', 'regs', 'written', 'kind', 'val', 'pcs', 'watch', 'bw')

    def __init__(self, m, regs):
        self.m, self.regs = m, regs
        self.written = bytearray(0x10000)
        self.kind = bytearray(0x10000)
        self.val = bytearray(0x10000)
        self.pcs = {}
        self.bw = set()
        self.watch = bytearray(0x10000)
        for a in WATCH:
            self.watch[a] = 1

    def __len__(self):
        return 0x10000

    def __iter__(self):
        return iter(self.m)

    def __getitem__(self, i):
        if i >= 0x5B00 and not self.written[i] and not (SHADOW[0] <= i < SHADOW[1]):
            r = self.regs
            p = r[PC]
            if p <= i <= p + 3:
                k = 2
            elif ((i - r[SP] + 2) & 0xFFFF) < 4:
                k = 4
            elif i == p - 1 and self.m[i] == 0x76:
                k = 0                                   # a HALT's own byte, re-read after the PC moved
            elif p in COPY_PCS and 0xA000 <= i < 0xAA00:
                # the copy's display pointer -- DE, or HL / HL' in $BB40's two-set merge -- is the shadow's row - $A0
                hi = (i >> 8) - 0xA0
                if r[D] != hi and r[H] != hi and r[XH] != hi:
                    raise RuntimeError('$%04X read $%04X: no display pointer on row $%02X -- not a dropped copy' %
                                       (p, i, hi))
                k = 0
            else:
                k = 1
            if k:
                self.kind[i] |= k
                self.val[i] = self.m[i]
                if k != 2:
                    ps = self.pcs.get(i)
                    if ps is None:
                        self.pcs[i] = [p]
                    elif len(ps) < 4 and p not in ps:
                        ps.append(p)
        return self.m[i]

    def __setitem__(self, i, v):
        if i >= 0x4000:
            if self.watch[i]:
                self.bw.add((i, self.regs[PC], v))
            self.written[i] = 1
            self.m[i] = v


def lineage(st, m):
    """'image' for the eleven built from build/image.bin, 'tape' for the rest -- each checked at $FF67"""
    want = IMG[0xFF67] if st in IMAGE_STATES else TAPE[0xFF67]
    if m[0xFF67] != want:
        raise RuntimeError('%s: $FF67 = $%02X, not its lineage\'s $%02X -- a state saved after a chain mark (or from '
                           'another image): decide its lineage by hand' % (st, m[0xFF67], want))
    return 'image' if st in IMAGE_STATES else 'tape'


def run(job):
    st, seed, quiet, frames, warp = job
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(st))
    m0 = h.memobj.m
    lin = lineage(st, m0)
    if warp:                                            # lrfree's poke: the next $8D12 advances to round `warp`
        m0[0xFECD] = 1
        m0[0x8609] = warp - 1
        m0[0xFDDA] |= 0x80
        m0[0xFDE4] |= 0x80
    sm = SweepMem(m0, h.sim.registers)
    h.sim.memory = sm
    h.sim.create_opcodes()
    h.sim.set_tracer(h.ports)
    sim, regs, ops = h.sim, h.sim.registers, h.sim.opcodes
    fd, ia = h.frame_duration, h.int_active
    m = sm.m
    rng = random.Random(seed)
    script = cm.expand(SCRIPT) if st in FRONT else []
    f, reset, armed, keyrun, cur, rounds = 0, None, False, 0, [], set()
    while f < frames:
        if f < len(script):
            cur = script[f]
        elif keyrun <= 0:
            keyrun = rng.randint(4, 30)
            cur = [] if quiet else [k for k in ('O', 'P', 'Q', 'SPACE') if rng.random() < 0.4]
        keyrun -= 1
        cm.keys(h, cur)
        end = regs[T] + fd
        while regs[T] < end:
            p = regs[PC]
            op = m[p]
            if op == 0x76 and regs[IFF]:
                h._fast_halt()
                continue
            ops[op]()
            if regs[IFF] and regs[T] % fd < ia:
                sim.accept_interrupt(regs, m, p)
        f += 1
        tramp = m[0xFFF4] == 0xC3 and m[0xFFF5] == 0x72 and m[0xFFF6] == 0x8D
        if tramp:
            armed = True
        elif armed:
            reset = f                                   # the IM2 trampoline gone: the machine reset
            break
        rounds.add(m[0x8609])
    out, allr = [], []
    for a in range(0x5B00, 0x10000):
        k = sm.kind[a]
        if not k or (k == 2 and not sm.written[a]):
            continue
        allr.append(a)                                  # THE CENSUS: every read before the first write, any value
        v = sm.val[a]
        if v != TAPE[a] or (lin == 'image' and TAPE[a] != IMG[a]):
            continue
        out.append((a, v, k & (5 | (2 if sm.written[a] else 0)), sm.pcs.get(a, [])))
    wrote = [a for a in range(0x5B00, 0x10000) if sm.written[a]]
    return {'state': st, 'warp': warp, 'seed': seed, 'quiet': quiet, 'frames': f, 'reset': reset, 'lineage': lin,
            'rounds': sorted(rounds), 'block_writes': sorted([a, p, v] for a, p, v in sm.bw),
            'written': len(wrote)}, (out, wrote, allr)


def states():
    names = sorted(set(os.path.splitext(os.path.basename(p))[0] for p in glob.glob('build/*.pkl')))
    return [n for n in names if n not in SKIP_STATES]


# ------------------------------------------------------------------------------------------------ the calls
def keyed(st, seed, quiet):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(st))
    return h, h.memobj.m, h.sim.registers, random.Random(seed), quiet


def run_to(h, m, r, rng, quiet, cond, frames=4000):
    """run (keys as the sweep's) until cond(r, m) at an instruction boundary; returns the frame or None"""
    keyrun, cur = 0, []
    for f in range(frames):
        if keyrun <= 0:
            keyrun = rng.randint(4, 30)
            cur = [] if quiet else [k for k in ('O', 'P', 'Q', 'SPACE') if rng.random() < 0.4]
        keyrun -= 1
        cm.keys(h, cur)
        end = r[T] + h.frame_duration
        while r[T] < end:
            if cond(r, m):
                return f
            h.step(1)
    return None


def call_here(h, lo=0x4000, hi=0x5B00):
    """run the routine entered at this PC to its return (interrupts off, sentinels pushed); its writes in [lo, hi).
       The machine is put back as it was, so the natural run goes on (and runs the routine itself)."""
    st = h.save_state()
    h.memobj.watch(lo, hi)
    reason = h.call(h.sim.registers[PC], interrupts=False)
    log = [[a, v] for _p, a, v in h.memobj.log]
    h.memobj.unwatch()
    h.load_state(st)
    if reason[0] != 0:
        raise RuntimeError('the routine at the call did not return normally: %r' % (reason,))
    return log


def iy(r):
    return r[IYh] << 8 | r[IYl]


def capture_calls():
    calls = {'boris': [], 'bolt': [], 'fire': [], 'cane': []}
    # Boris: $91D6's CALL $A447 with IY = $9250, from the boris state (no keys) -- ticks 0..3, then every 40th to 160
    # (he enters at X 24 and climbs: every draw in reach is the ALIGNED one, which reads all 64 bytes of the bank)
    h, m, r, rng, q = keyed('boris', 7, True)
    for k in range(161):
        f = run_to(h, m, r, rng, q, lambda r, m: r[PC] == 0xA447 and iy(r) == 0x9250)
        if f is None:
            raise RuntimeError('boris: no $A447 call for $9250')
        if k < 4 or k % 40 == 0:
            snap = bytes(m)
            log = call_here(h)
            calls['boris'].append({'tick': k, 'fields': list(snap[0x9250:0x925A]), 'toggle': snap[0xA3B2],
                                   'pstate': snap[0x9250 + 0x5A], 'left': snap[0xAA5F],
                                   'before': {str(a): snap[a] for a, _v in log},
                                   'shadow': {str(a): snap[(a + 0xA000) & 0xFFFF] for a, _v in log},
                                   'writes': log})
        h.step(1)
    # the lightning bolt: $A2D5 with IY = ($FDEE)'s slot, from ellight (random keys, seed 7)
    h, m, r, rng, q = keyed('ellight', 7, False)
    for k in range(4):
        f = run_to(h, m, r, rng, q, lambda r, m: r[PC] == 0xA2D5 and iy(r) in (0xFDEE, 0xFDF8) and
                   (m[iy(r)] | m[iy(r) + 1] << 8) == 0xA37D)
        if f is None:
            raise RuntimeError('ellight: no bolt blit')
        snap = bytes(m)
        rec = iy(r)
        log = call_here(h)
        calls['bolt'].append({'frame': f, 'rec': rec, 'fields': list(snap[rec:rec + 10]),
                              'before': {str(a): snap[a] for a, _v in log}, 'writes': log})
        h.step(1)
    # the fire's burn: $A04E (A = the phase), from elfire -- built from image.bin, whose $A39D..$A3AC are the tape's
    h, m, r, rng, q = keyed('elfire', 7, False)
    if any(m[a] != TAPE[a] for a in range(0xA39D, 0xA3AD)):
        raise RuntimeError('elfire: the fire frames are not the tape\'s')
    for k in range(4):
        f = run_to(h, m, r, rng, q, lambda r, m: r[PC] == 0xA04E and r[A] < 0xFA)
        if f is None:
            raise RuntimeError('elfire: no burn')
        snap = bytes(m)
        a = r[A]
        log = call_here(h)
        calls['fire'].append({'frame': f, 'a': a, 'fdf0': list(snap[0xFDF0:0xFDF3]),
                              'before': {str(x): snap[x] for x, _v in log}, 'writes': log})
        h.step(1)
    # the giant diamond's award: $A9C2, just after $A9C1 LD A,(HL), from candycane (random keys, seed 3: a hit at frame 61)
    h, m, r, rng, q = keyed('candycane', 3, False)
    f = run_to(h, m, r, rng, q, lambda r, m: r[PC] == 0xA9C2, frames=1500)
    if f is None:
        raise RuntimeError('candycane: no award')
    calls['cane'].append({'frame': f, 'type': m[0xA85C], 'hl': r[H] << 8 | r[L], 'a': r[A]})
    return calls


# ------------------------------------------------------------------------------------------------ capture / verify
def sweep(jobs):
    work = []
    for i, n in enumerate(states()):
        work += [(n, 100 + i, False, FRAMES, 0), (n, 200 + i, True, FRAMES, 0)]
    work += [(WARP_BASE, 1000 + r, r % 2 == 0, WARP_FRAMES, r) for r in range(1, 82)]
    agg, runs, ever, census, tread = {}, [], bytearray(0x10000), set(), set()
    with ProcessPoolExecutor(jobs) as ex:
        for info, (out, wrote, allr) in ex.map(run, work):
            runs.append(info)
            for a in wrote:
                ever[a] = 1
            census.update(allr)
            tread.update(a for a, _v, _k, _ps in out)
            for a, v, k, ps in out:
                e = agg.setdefault(a, [v, 0, [], set()])
                e[1] |= k
                for p in ps:
                    if p not in e[2] and len(e[2]) < 4:
                        e[2].append(p)
                e[3].add(info['state'] + ('@%d' % info['warp'] if info['warp'] else ''))
    blk = set(WATCH)
    reads = [[a, e[0], e[1], sorted(e[2]), len(e[3])] for a, e in sorted(agg.items()) if not ever[a] or a in blk]
    return runs, reads, census_of(census, tread)


def census_ram():
    """the machine's RAM at the END of the ISR labelled CENSUS_F on the real load -- lrfree's drive: boot.pkl's $F5BC,
       passacc's keys put in at each ISR's end (or after the front end's RST $38 scan, if one is open)"""
    h, m, r = cm.world('boot')
    seq = cm.expand(SCRIPT)
    keyf = lambda f: seq[f] if f < len(seq) else []
    sim, ops, mem = h.sim, h.sim.opcodes, h.sim.memory
    fd, ia = h.frame_duration, h.int_active
    nb = (r[T] // fd + 1) * fd
    frame, in_scan, pending, isr = 0, False, None, None
    cm.keys(h, keyf(0))
    while True:
        pc = r[PC]
        if r[T] >= nb:
            frame += 1
            nb += fd
        if isr is not None and pc == isr[0] and r[SP] == isr[1]:
            L = isr[2]
            if in_scan:
                pending = keyf(L)
            else:
                cm.keys(h, keyf(L))
            if L == CENSUS_F:
                return bytes(m)
            isr = None
        if pc == 0xF7B9 and in_scan:
            in_scan = False
            if pending is not None:
                cm.keys(h, pending)
                pending = None
        if pc in cm.GUARD:
            raise RuntimeError('census: PC $%04X, the 128K driver' % pc)
        if pc == 0xF7B8:
            in_scan = True
        ops[mem[pc]]()
        if r[IFF] and r[T] % fd < ia:
            b0, s0 = r[PC], r[SP]
            if sim.accept_interrupt(r, mem, pc):
                isr = (b0, s0, frame + (1 if r[T] >= nb else 0))


def census_of(census, tread):
    ram = census_ram()
    runs, tr = [], []
    for a in sorted(census):
        if runs and a == runs[-1][0] + len(runs[-1][1]):
            runs[-1][1].append(ram[a])
        else:
            runs.append([a, [ram[a]]])
        if a in tread:
            if tr and a == tr[-1][0] + tr[-1][1]:
                tr[-1][1] += 1
            else:
                tr.append([a, 1])
    return {'frame': CENSUS_F, 'n': len(census), 'runs': [[a0, bytes(v).hex()] for a0, v in runs], 'tape_read': tr}


def capture(jobs):
    runs, reads, census = sweep(jobs)
    d = {'note': __doc__.strip(), 'frames': FRAMES, 'runs': runs, 'reads': reads, 'calls': capture_calls(),
         'census': census}
    check(d)
    json.dump(d, open(FIXTURE, 'w'), separators=(',', ':'))
    print('wrote %s: %d runs, %d tape reads, block writes %d, calls %s, census %d addresses (%d runs, %d tape-read)' % (
        FIXTURE, len(runs), len(reads), sum(len(x['block_writes']) for x in runs),
        {k: len(v) for k, v in d['calls'].items()}, census['n'], len(census['runs']),
        sum(n for _a, n in census['tape_read'])))


def check(d):
    bad = [x for x in d['runs'] if x['reset'] is not None]
    if bad:
        raise SystemExit('runs that reset: %s' % bad[:4])
    for x in d['runs']:
        for a, p, v in x['block_writes']:
            if p not in WRITERS.get(a, ()):
                raise SystemExit('%s (seed %d): $%04X written by $%04X -- not a named writer' % (x['state'], x['seed'], a, p))
            if 0xFB00 <= a < 0xFC00 and not v & 0x40:
                raise SystemExit('%s: $%04X := $%02X drops the tape\'s bit 6' % (x['state'], a, v))
    rd = {x[0]: x for x in d['reads']}
    for at, n, what in BLOCKS:
        for a in range(at, at + n):
            if TAPE[a] and a not in rd:
                raise SystemExit('$%04X (%s): a non-zero tape byte of a block the sweep never saw read' % (a, what))


def verify(jobs):
    old = json.load(open(FIXTURE))
    runs, reads, census = sweep(jobs)
    calls = capture_calls()
    same = old['runs'] == runs and old['reads'] == reads and old['calls'] == calls and old.get('census') == census
    print('MATCH' if same else 'DIFFER: runs %s reads %s calls %s census %s' % (
        old['runs'] == runs, old['reads'] == reads, old['calls'] == calls, old.get('census') == census))
    if not same:
        sys.exit(1)


def extract():
    d = json.load(open(FIXTURE))
    check(d)
    for st in states():
        h = Harness()
        h.load_state_file(pc.state_path(st))
        m = h.memobj.m
        if lineage(st, m) != 'tape':
            continue
        for at, n, what in BLOCKS:
            if bytes(m[at:at + n]) != TAPE[at:at + n]:
                raise SystemExit('%s: $%04X..$%04X differs from the tape image' % (st, at, at + n - 1))
    if IMG[0xFF67] != 0xEE or TAPE[0xFF67] != 0xE6:
        raise SystemExit('$FF67: the images no longer hold $EE / $E6')
    h = Harness()
    h.load_state_file(pc.state_path('boss'))
    m = h.memobj.m
    diff = [a for a in range(0x4000, 0x10000) if TAPE[a] != IMG[a]]
    if any(m[a] != IMG[a] for a in diff):
        raise SystemExit('boss.pkl is not image.bin at every byte the images disagree on')
    rd = {x[0]: x for x in d['reads']}
    out = {'note': __doc__.strip(),
           'blocks': [{'at': at, 'n': n, 'what': what, 'b64': base64.b64encode(TAPE[at:at + n]).decode(),
                       'readers': sorted({'$%04X' % p for a in range(at, at + n) if a in rd for p in rd[a][3]})}
                      for at, n, what in BLOCKS]}
    json.dump(out, open(OUT, 'w'), indent=1)
    print('wrote %s: %s' % (OUT, ', '.join('$%04X..$%04X' % (at, at + n - 1) for at, n, _w in BLOCKS)))


def main():
    a = sys.argv[1:]
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 20
    cmd = a[0] if a else 'verify'
    if cmd == 'capture':
        capture(jobs)
    elif cmd == 'verify':
        verify(jobs)
    elif cmd == 'extract':
        extract()
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
