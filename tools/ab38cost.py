"""M7.69 -- THE PLAYER HANDLER $AB38's T, RUN BY RUN, UNCONTENDED.

M7.68 made $AA60's skeleton charge itself exactly and left each handler RUN at its fixture
median (BB_AA60_RUN, PROVISIONAL).  The player's runs span 189..8,229 T contended.  This
oracle records every $AB38 run on an UNCONTENDED machine, so a run's T is the sum of its
instructions' own T and nothing else:

  T        the run: from $AB38's entry ($AAEA RET z / $AAEB JP (HL)) to its return
  slot     0 (P1, IY = $FD80) or 1 (P2, IY = $FD8A)
  kb       the keyboard as the run saw it: the (select, value) half-rows held, from this
           oracle's own script -- ACTIONS, pressed through EACH PLAYER'S OWN TABLE ($B5FD for P1,
           $B605 for P2: left, right, jump, blow), because aa60cost's O/P/Q/SPACE never reaches
           the jump entry of any state's table
  seed     every byte the run READS before it writes it, as (address, value) -- not the
           bytes of the instruction being executed (the opcode and operand fetches)
  post     every byte the run WRITES, at its final value -- the stack excepted (the 64 bytes below
           the run's entry SP) -- so the gate checks what the run did as well as what it cost
  path     the run's PCs where control did not fall through (the branch targets), for a
           diagnostic when a row fails

Every 48K saved state, 300 frames, interrupts on, ACTIONS 25 frames each; the rows keep up to
2 runs of every distinct path.  FORCED rows (declared, poked at load) reach the paths no
natural run reaches: the final death ($AB64, $AB68 -> $BF0A), P2's respawn ($ABCC).

Usage:  python tools/ab38cost.py [--jobs N]          (-> build/ab38cost_fixture.json)
        python tools/ab38cost.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, os, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, Mem, T, PC, IFF, SP
import portconfig as pc
from keyprobe import KEYMAP, keymask
import aa60cost as A

FIXTURE = 'build/ab38cost_fixture.json'
FRAMES = 300
KEEP = 2                                      # runs kept per distinct path
# 25 frames each, both players at once: L R J B by each player's own key table
ACTIONS = ['RB', 'L', '', 'JB', 'RJB', 'LJ', 'B', 'J', 'LR', 'RJ', 'LB', 'J']
KEY_FRAMES = 25
H = 0xAB38
CALLS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
# FORCED (declared): (name, state, pokes[, actions[, held]]) -- each run's first 100 frames, up to
# FORCED_KEEP runs of each path; `held` pokes are RE-APPLIED EVERY FRAME (a shadow cell the game repaints)
FORCED = [
    # P1 dying on its last life: +$5A bit 2 (dying), +4 = 0 (the tick goes negative), +$5C = 0
    ('final_death', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 0))),
    # ...and at each of $BF0A's forced erase's Y classes: cell-aligned, odd, even non-zero, >= $C0
    ('final_death_y0', 'r20_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 0),
                                  (0xFD80 + 6, 0x58))),
    ('final_death_odd', 'r20_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 0),
                                   (0xFD80 + 6, 0x63))),
    ('final_death_even', 'r20_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 0),
                                    (0xFD80 + 6, 0x7A))),
    ('final_death_high', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 0),
                                       (0xFD80 + 6, 0xC6))),
    # P2 dying with a life left: the respawn's P2 arm ($ABCC)
    ('p2_respawn', 'round1_2p48', ((0xFD8A + 0x5A, lambda b: b | 0x04), (0xFD8A + 4, 0), (0xFD8A + 0x5C, 2))),
    # a respawn on round 80 ($AB7D LD ($8CB0),A), and one with six lives left (the panel caps at 5, $80A2)
    ('round80', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 2),
                              (0x8609, 0x50))),
    ('lives5', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x04), (0xFD80 + 4, 0), (0xFD80 + 0x5C, 7))),
    # P1 on a KEMPSTON table ($AC11 JP z,$AEF5): left 2, right 1, up 8, fire 16
    ('kempston', 'round1_48', tuple((0xB5FD + i, v) for i, v in
                                    enumerate((0x1F, 0x02, 0x1F, 0x01, 0x1F, 0x08, 0x1F, 0x10))),
     ['RB', 'L', 'J', 'LJ', 'RJB', 'LR', 'B', '']),
    # the BUBBLE-JUMP ($AEA7): the platform P1's jump lands on (row 19, cells 2..5) poked to $05 -- low
    # bits, no bit 5 -- and RE-POKED EVERY FRAME (the shadow is repainted), with jump held from the
    # first frame, so the arc's descent probe lands on it
    ('bounce', 'round1_48', (), ['J'], tuple((0xFA60 + c, 0x05) for c in range(2, 6))),
    # free-fall at Y = $BE: (Y AND $FE) + 2 >= $BF, the tail's wrap to Y = 2 ($AD60)
    ('wrap', 'round1_48', ((0xFD80 + 6, 0xBE), (0xFD80 + 9, 0xFF)), ['']),
    # an arc at phase 32: the new phase 33 becomes $FF ($AD72)
    ('phase33', 'round1_48', ((0xFD80 + 5, 0x18), (0xFD80 + 6, 0x50), (0xFD80 + 9, 0x20), (0xFD80 + 8, 0)), ['']),
    # rising at a row edge against the left wall, LEFT locked in from the last read (+8 bit 3): $ADEB's
    # ascending arm, foot AND up ($ADEF..$ADFD)
    ('climb_left', 'round1_48', ((0xFD80 + 5, 0x10), (0xFD80 + 6, 0x80), (0xFD80 + 9, 0x05), (0xFD80 + 8, 0x08)),
     ['L']),
    # ...with the wall cell ABOVE the foot cleared ($FA01, held): the step goes, and $AE0F's clamp ($AE1A)
    ('climb_gap', 'round1_48', ((0xFD80 + 5, 0x10), (0xFD80 + 6, 0x80), (0xFD80 + 9, 0x05), (0xFD80 + 8, 0x08)),
     ['L'], ((0xFA01, 0x00),)),
    # the HEART: ($FED0) = 1 (held) with P1 invulnerable -- $ABE8 JR z, the countdown frozen
    ('heart', 'round1_48', ((0xFD80 + 0x5A, lambda b: b | 0x08), (0xFD80 + 4, 0x30)), [''], ((0xFED0, 1),)),
    # a bubble cell under P1 whose pool slot is DEAD: row 23 cells 2..5 := $05 (tag 5 -> slot 7, flags
    # $FF25 := 0), held, no keys -- the floor tick's second probe pops it ($AEC0 RET z)
    ('pop_dead', 'round1_48', (), [''], tuple((0xFAE0 + c, 0x05) for c in range(2, 6)) + ((0xFF25, 0x00),)),
    # ABOVE THE HUD with $712F..$7131 SOLID (held; zero in every saved state) and $710F clear: $AED7's XOR A makes
    # the move's foot clear whatever $712F holds, while the floor probe's cell walk does read it
    ('above_hud', 'round1_48', ((0xFD80 + 5, 0x30), (0xFD80 + 6, 0x02), (0xFD80 + 9, 0x00), (0xFD80 + 8, 0x08)),
     ['L'], ((0x712F, 0x20), (0x7130, 0x20), (0x7131, 0x20))),
]
FORCED_FRAMES = 100
FORCED_KEEP = 4


class RecMem(Mem):
    """the harness memory, recording the FIRST access of each byte while a run is open"""
    __slots__ = ('rec', 'seen', 'pc_lo', 'regs', 'wr', 'stk')

    def __init__(self, base):
        Mem.__init__(self, base.m)
        self.sim = base.sim
        self.rec = None; self.seen = None; self.pc_lo = -1; self.regs = None; self.wr = None; self.stk = 0

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            p = self.regs[PC]
            if not (p <= i < p + 4):              # not this instruction's own bytes
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return self.m[i]

    def __setitem__(self, i, v):
        if self.rec is not None:
            self.seen.add(i)                     # written first: not an input
            if not (self.stk - 0x40 <= i < self.stk + 2) and i >= 0x4000:
                self.wr[i] = v
        Mem.__setitem__(self, i, v)


def run(name, pokes=(), frames=FRAMES, tab=None, actions=None, hold=()):
    """the runs; with `tab` (a dict) also each executed instruction's T by (pc, next pc) --
    the authoring aid the engine's BB_AB38 sums were added up from"""
    h = Harness(contended=False)
    h.load_state_file(pc.state_path(name))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    rm.regs = r
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    for a, v in pokes:
        raw[a] = v(raw[a]) if callable(v) else v
    fd, ia = h.frame_duration, h.int_active
    t_end = r[T] + frames * fd
    ki, nextk, held = 0, r[T], {}
    acts = actions or ACTIONS
    nextf = r[T]
    runs, cur = [], None
    while r[T] < t_end:
        if hold and r[T] >= nextf:
            for a, v in hold:
                raw[a] = v
            nextf += fd
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if c in acts[ki % len(acts)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask            # ACTIVE HIGH
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            held = dict(h.ports.pressed)
            ki += 1; nextk = r[T] + KEY_FRAMES * fd
        p = r[PC]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if cur is not None and r[SP] == (cur['sp'] + 2) & 0xFFFF:
            rm.rec = None
            cur['T'] = r[T] - cur['t0']
            runs.append(cur); cur = None
        if cur is None and p == H:
            iy = h.iy()
            cur = {'t0': r[T], 'sp': r[SP], 'slot': (iy - 0xFD80) // 10, 'kb': sorted(held.items()),
                   'kemp': h.ports.kempston,
                   'seed': [], 'path': [], 'last': None}
            assert iy in (0xFD80, 0xFD8A), 'IY $%04X' % iy
            rm.seen = set(); rm.rec = cur['seed']; rm.wr = cur['post'] = {}; rm.stk = r[SP]
        elif cur is not None and cur['last'] is not None and p != cur['last']:
            cur['path'].append(p)
        if raw[p] == 0x76:
            h._fast_halt()
            if cur is not None: cur['last'] = None
        else:
            t0 = r[T]
            op[raw[p]]()
            if cur is not None:
                cur['last'] = None if r[PC] == H else _fall(raw, p)
                if tab is not None:
                    tab.setdefault(p, set()).add((r[T] - t0, r[PC]))
            if r[IFF] and r[T] % fd < ia:
                h.sim.accept_interrupt(r, rm, p)
    return runs


LEN = {}
def _fall(raw, p):
    """the fall-through address after the instruction at p (its length, from z80dis)"""
    if p not in LEN:
        from z80dis import z80
        d = z80.decode(bytes(raw[p:p + 4]), p)
        LEN[p] = d.len
    return (p + LEN[p]) & 0xFFFF


def row(name, x):
    return {'state': name, 'slot': x['slot'], 'kb': x['kb'], 'kemp': x['kemp'], 'T': x['T'],
            'seed': ''.join('%04x%02x' % (a, v) for a, v in sorted(x['seed'])),
            'post': ''.join('%04x%02x' % (a, v) for a, v in sorted(x['post'].items())),
            'path': ' '.join('%04x' % q for q in x['path'])}


def one(job):
    name, pokes, frames, tag = job
    out = []
    for x in run(name, FORCED_POKES[tag] if tag else (), frames, actions=FORCED_ACTS.get(tag),
                 hold=FORCED_HOLD.get(tag, ())):
        out.append(row(tag or name, x))
    return out


FORCED_POKES = {f[0]: f[2] for f in FORCED}
FORCED_ACTS = {f[0]: f[3] for f in FORCED if len(f) > 3}
FORCED_HOLD = {f[0]: f[4] for f in FORCED if len(f) > 4}


def measure(jobs):
    work = [(s, None, FRAMES, None) for s in A.STATES] + \
           [(f[1], None, FORCED_FRAMES, f[0]) for f in FORCED]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    rows, per, Ts, forced, npaths = [], collections.Counter(), [], collections.Counter(), set()
    for (s, _, _, tag), rs in zip(work, res):
        for x in rs:
            Ts.append(x['T'])
            k = x['path']
            if not tag: npaths.add(k)
            if (tag and per[tag + k] < FORCED_KEEP) or (not tag and per[k] < KEEP):
                per[tag + k if tag else k] += 1
                if tag: forced[tag] += 1
                rows.append(x)
    Ts.sort()
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': ACTIONS, 'key_frames': KEY_FRAMES,
            'states': A.STATES, 'forced': [f[0] for f in FORCED], 'forced_frames': FORCED_FRAMES,
            'runs': len(Ts), 'paths': len(npaths), 't_lo': Ts[0], 't_hi': Ts[-1],
            'forced_rows': dict(forced), 'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 12
    F = measure(jobs)
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), indent=0)
    print('runs %d  paths %d  rows %d  T %d..%d  forced %s' % (F['runs'], F['paths'], len(F['rows']),
                                                             F['t_lo'], F['t_hi'], F['forced_rows']))


if __name__ == '__main__':
    main()
