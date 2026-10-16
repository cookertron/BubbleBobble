"""M7.99a (measurement) -- THE BOSS TICK'S TWO DECLARED-UNCHARGED ARMS, RUN BY RUN, UNCONTENDED.

$A9ED (the boss tick, called from $8D2E, returning to $8D31) has two arms M7.96 / M7.97 left declared:

  'spawn'  $A9F7 LD A,4 / $A9F9 JP z,$A84D -- the boss's spawn, a TAIL JUMP (its RET returns to $8D31), so the
           whole of $A84D is inside $A9ED's own frame.  Every natural run that takes it (bossspawn, the one saved
           state whose ($A839) is 0 in the boss round), FRAMES frames, interrupts on, ab38cost's key script.
  'heart'  $AA35 JP $927D with ($FED0) non-zero: $9281 JR nz,$9298 -- EX DE,HL / LD IY,$FFF9 / ADD IY,DE / DI /
           PUSH IX / CALL $8BC2 / POP IX / LD A,1 / BIT 0,(IX+$5A) / JR z / INC A / LD HL,$1000 / LD ($FFED),HL /
           CALL $80FA / EI / RET.  No saved state holds ($FED0) in the boss round, so FORCED: ($FED0) poked, the
           divider's two self-modified operands poked so the body runs ($AA00 := not ($8DBD), $AA06 := $1F, as
           costsmall's), a player glued into the boss's 4x4 tile box at $AA2C (after the body's move, before $A969
           asks; the other player four rows below it) -- and NOTHING ELSE: HL is what $A969 leaves.
           MEASURED: HL = $A9AF on every run -- the address $A994 PUSHes (the comparator's SCF / RET), so $9299
           makes IY = $A9A8 and $8BC2 BIRTHS A CORPSE OVER CODE: $A9A8..$A9B1 (inside $A969's comparator).
           costsmall's two forced runs (a9ed_award_p1 / _p2) poked HL := $FD9B at $927D, which the boss path never has.
           A run is called at $A9ED with interrupts off, returning to $8D31 (call_run's way).
  'control' the same worlds with ($FED0) = 0: the kill ($9288 / $928B fall through) -- the prefix the two share.
  'after'  boss, ($FED0) := 1 and P1 glued to the box at each frame boundary, interrupts on, no keys: the natural
           kill, then on until the machine first EXECUTES a byte the kill wrote (frame, PC) -- and stopped there:
           what follows is the corrupted comparator (the machine resets, PC into the ROM; not run here: the
           guarded range $D000..$D2FF is never executed).

The ARM's T (Zilog, from the listing above; asserted against every heart run: own(heart) = own(the same world's
carried refusal) - (9281f 34 + 9288t 11) + ARM):
  9281t 122   JR nz taken 12 / EX DE,HL 4 / LD IY,nn 14 / ADD IY,DE 15 / DI 4 / PUSH IX 15 / CALL 17 / POP IX 14 /
              LD A,n 7 / BIT 0,(IX+d) 20
  92ADt  59   JR z taken 12 / LD HL,nn 10 / LD (nn),HL 16 / CALL 17 / EI 4          (bit 0 clear: P1 paid)
  92ADf  58   JR z 7 / INC A 4 / LD HL,nn 10 / LD (nn),HL 16 / CALL 17 / EI 4         (bit 0 set: P2 paid)
  92BAx  10   RET
Rows keep the run's T, own, path, kids ([entry, T, own, sig, kids]), HL / DE / IX at $9298 and IY at $92A2, the
seed (every byte read before written; the divider's operands as state; ROM addresses only, never a value) and
the writes (bitmap writes addresses only when the run read the ROM -- the award's glyphs).
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

Usage:  python tools/bosskillcost.py [measure] [--jobs N]   (-> build/bosskillcost_fixture.json, N <= 6)
        python tools/bosskillcost.py verify [--jobs N]      (re-measure, compare, say MATCH)
"""
import sys, json, time
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import T, PC, IFF, SP
import aa60cost as AA
import cost8fa5 as G
import costsmall as CS

FIXTURE = 'build/bosskillcost_fixture.json'
FRAMES = G.FRAMES
ENTRY, BACK = 0xA9ED, 0x8D31
_OPS = {}


def ops_for(state):
    """every self-modified byte (costsmall's smc_set: an absolute store's target) an instruction at pc is made
    of -- read as STATE when that instruction runs (TRAPS #275 / #278): the divider's operands, the draw's
    pointers, $A85B's operand"""
    if state not in _OPS:
        h, rm = G.machine(state, {})
        smc = CS.smc_set(rm.m)
        _OPS[state] = {p: tuple(a for a in range(p, p + 4) if a in smc) for p in range(0x4000, 0x10000)
                       if any(a in smc for a in range(p, p + 4))}
    return _OPS[state]
ARM = {'9281t': 122, '92ADt': 59, '92ADf': 58, '92BAx': 10}
PREFIX_REFUSE = 34 + 11                                          # 9281f + 9288t: the carried refusal's tail
HL_PUSHED = 0xA9AF
CODE = (0xA9A8, 0xA9B2)                                          # IY = $A9A8: the corpse's ten bytes
AFTER_FRAMES = 40
# (label, state, who, ($5A) of the glued player, ($FED0))
HEART = [
    ('boss_p1', 'boss', 1, 0x80, 1), ('boss_p1_bit0', 'boss', 1, 0x81, 1), ('boss_p2', 'boss', 2, 0x01, 1),
    ('boss_p1_ff', 'boss', 1, 0x80, 0xFF),
    ('bosshit_p1', 'bosshit', 1, 0x80, 1), ('bosshit_p2', 'bosshit', 2, 0x41, 1),
    ('bosskilled_p1', 'bosskilled', 1, 0x80, 1), ('bosskilled_p2', 'bosskilled', 2, 0x41, 1),
]


def r16(r, hi, lo):
    return r[hi] << 8 | r[lo]


def glue(raw, who, f5a=None):
    """the player in the boss's box (tile row ($A839), column ($A8DB)); the other one out of it"""
    ix = 0xFD80 if who == 1 else 0xFD8A
    other = 0xFD8A if who == 1 else 0xFD80
    raw[ix + 6] = (raw[0xA839] * 8) & 0xFF
    raw[ix + 5] = (raw[0xA8DB] * 8) & 0xFF
    raw[ix + 7] |= 0x80
    if f5a is not None:
        raw[ix + 0x5A] = f5a
    raw[other + 6] = ((raw[0xA839] + 8) * 8) & 0xFF                # four tiles past the box's bottom row


def call(label, state, who, f5a, fed0):
    """$A9ED called once, interrupts off, returning to $8D31, the world forced as the docstring says"""
    h, rm = G.machine(state, ops_for(state))
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, state + ': not a 48K state'
    assert raw[0x8609] == 0x50 and raw[0xA839], state + ': not the boss round with the boss present'
    assert raw[0xA98F] == 0 and raw[0xA990] == 0, state + ': the overlap pair is not NOP / NOP'
    raw[0xAA00] = (raw[0x8DBD] + 1) & 0xFF
    raw[0xAA06] = 0x1F
    raw[0xFED0] = fed0
    if f5a is not None:
        raw[(0xFD80 if who == 1 else 0xFD8A) + 0x5A] = f5a
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    tr = G.Tracker(ENTRY)
    tr.open(r, rm, BACK)
    at = {}
    for _ in range(400000):
        p = r[PC]
        if p == 0xAA2C and tr.isr is None:
            glue(raw, who)        # the body has moved the boss: the player into the box it now holds
        if p == 0x9298:
            at.update(hl='%04X' % r16(r, 6, 7), de='%04X' % r16(r, 4, 5), ix='%04X' % r16(r, 8, 9))
        if p == 0x92A2:
            at['iy'] = '%04X' % r16(r, 10, 11)
        tr.step(r, op, raw, rm, h)
        if tr.isr is None and tr.cur is not None:
            tr.close_frames(r, rm)
        if tr.cur is None:
            break
    else:
        raise AssertionError(label + ': no return')
    x = tr.done[0]
    rw = G.row_base(label, x)
    rw.update({'who': who, 'f5a': f5a, 'fed0': fed0, 'at': at})
    return rw


def spawn_runs(state='bossspawn'):
    """the natural boss-tick spawns: every $A9ED run that took $A9F9 JP z"""
    rows = []
    for x in G.run(state, ENTRY, BACK, ops_for(state), FRAMES):
        if 'a9f9:t1' in x['sig']:
            rows.append(G.row_base(state, x))
    return rows


def after(state='boss'):
    """the natural kill (interrupts on, no keys), then on to the first execution of a byte it wrote"""
    h, rm = G.machine(state, ops_for(state))
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    fd = h.frame_duration
    raw[0xFED0] = 1
    h.ports.release_all()
    t0 = r[T]
    out = {'state': state}
    kill = None
    lastf = -1
    written = {}
    while True:
        f = (r[T] - t0) // fd
        if kill is None and f != lastf:
            glue(raw, 1)
            lastf = f
        assert f < 300, 'no kill / no execution within 300 frames'
        p = r[PC]
        assert not (AA.GLO <= p < AA.GHI), 'ENTERED THE GUARDED RANGE'
        if kill is None and p == 0x9298:
            kill = {'frame': f, 'hl': '%04X' % r16(r, 6, 7), 'before': [raw[a] for a in range(*CODE)]}
        if kill is not None and p == 0x92BA:
            if 'after' not in kill:
                kill['after'] = [raw[a] for a in range(*CODE)]
                kill['aa5f'] = raw[0xAA5F]
                written = {a for a in range(*CODE) if raw[a] != kill['before'][a - CODE[0]]}
        if kill is not None and 'after' in kill and p in written:
            out['first_exec'] = {'frame': f, 'frames_after': f - kill['frame'], 'pc': '%04X' % p}
            break
        if raw[p] == 0x76 and r[IFF]:
            h._fast_halt()
            continue
        op[raw[p]]()
        if r[IFF] and r[T] % fd < h.int_active:
            h.sim.accept_interrupt(r, rm, p)
    out['kill'] = kill
    out['written'] = sorted('%04X' % a for a in written)
    return out


def one(job):
    kind, arg = job
    if kind == 'heart':
        return kind, call(*arg)
    if kind == 'control':
        label, state, who, f5a, fed0 = arg
        return kind, call(label + '_ctl', state, who, f5a & ~0x10 | 0x10, 0)   # the carried refusal: same prefix
    if kind == 'spawn':
        return kind, spawn_runs()
    return kind, after()


def measure(jobs):
    work = [('heart', c) for c in HEART] + [('control', c) for c in HEART] + [('spawn', None), ('after', None)]
    with Pool(jobs) as pool:
        res = pool.map(one, work)
    F = {'note': 'tools/bosskillcost.py (M7.99a): the boss tick\'s spawn arm (natural) and its kill through $9298 '
                 '(forced ($FED0), natural HL)', 'frames': FRAMES, 'arm': ARM, 'hl_pushed': '%04X' % HL_PUSHED,
         'heart': [], 'control': [], 'spawn': [], 'after': None}
    for kind, v in res:
        if kind == 'spawn':
            F['spawn'] = v
        elif kind == 'after':
            F['after'] = v
        else:
            F[kind].append(v)
    # the model: every heart run's own = its control's own - the refusal's tail + the arm
    bad = []
    for h_, c in zip(F['heart'], F['control']):
        arm = ARM['9281t'] + (ARM['92ADt'] if not (h_['f5a'] & 1) else ARM['92ADf']) + ARM['92BAx']
        kids = dict((k[0], k[1]) for k in h_['kids'])
        ok = (h_['own'] == c['own'] - PREFIX_REFUSE + arm and h_['at'].get('hl') == '%04X' % HL_PUSHED
              and h_['at'].get('iy') == '%04X' % (HL_PUSHED - 7) and h_['T'] == h_['own'] + sum(k[1] for k in h_['kids'])
              and '8BC2' in kids and '80FA' in kids and '9281:t1f0' in h_['sig'] and '9281:t0f1' in c['sig'])
        if not ok:
            bad.append(h_['state'])
    F['model'] = {'bad': bad, 'checked': len(F['heart'])}
    return F


def report(F):
    for h_ in F['heart']:
        print('%-16s T %6d own %4d HL %s IY %s IX %s kids %s' % (h_['state'], h_['T'], h_['own'], h_['at'].get('hl'),
              h_['at'].get('iy'), h_['at'].get('ix'), [(k[0], k[1]) for k in h_['kids']]))
    for s in F['spawn']:
        print('spawn %s T %d own %d' % (s['state'], s['T'], s['own']))
    print('after:', json.dumps(F['after']))
    print('model: bad %d of %d' % (len(F['model']['bad']), F['model']['checked']))


def main():
    args = sys.argv[1:]
    t0 = time.time()
    F = json.loads(json.dumps(measure(G.jobs_arg(args))))
    rc = G.finish(F, FIXTURE, args, report)
    print('%.0f s' % (time.time() - t0))
    sys.exit(rc)


if __name__ == '__main__':
    main()
