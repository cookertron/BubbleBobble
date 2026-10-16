# -*- coding: utf-8 -*-
"""M7.13 -- $8FE7, THE PAUSE, the second chain entry ($8D28) and the only one
that STOPS the machine.

It is worth a tool because three of its four facts are unguessable from the
listing alone:

  (a) $8E0A IS `C9 RET` ON THE 48K BRANCH.  The routine reads ($FED4), pushes
      it, calls $8E0A with A=0, and on the way out pops it and calls $8E0A
      again -- the 128K music driver's mute/unmute.  On 48K both calls are
      returns, so ($FED4) is read and put straight back and THE WHOLE ROUTINE
      WRITES NO MEMORY AT ALL.  A port that models the mute invents state.
  (b) WHICH KEY.  `LD A,$7F / IN A,($FE) / AND 2` is SYM SHIFT by the standard
      half-row map, and `LD A,$FE / IN A,($FE) / RRA / JR c` is CAPS SHIFT --
      but the map is a claim about the machine, so all forty keys are swept
      through the real routine, both for the ARM and for the RELEASE.
  (c) THE SPIN IS A BUSY WAIT WITH INTERRUPTS OFF.  $8FF6 DI .. $9009 EI
      brackets it, so while paused the ISR does not run: nothing is drawn, no
      sound is made, and the pass the pause interrupted is SUSPENDED IN THE
      MIDDLE -- on release it continues at $900B, it does not restart at $8D25.

Usage:  python tools/pausegate.py            (capture)
"""
import sys, json
sys.path.insert(0, 'tools')
from harness import Harness, PC, T
from keyprobe import KEYS
import portconfig as pc

FIXTURE = 'build/pausegate_fixture.json'
BRANCH_BYTE = 0x8DC4
PAUSE = 0x8FE7
SPIN = 0x8FFB
MUSIC = 0x8E0A
CHAIN0 = 0x8D25
AFTER_PAUSE = 0x900B
STATES = ['round1_48', 'r20_48', 'play1p48', 'boss']


def new(state='round1_48'):
    h = Harness(contended=True)
    h.load_state_file(pc.state_path(state))
    m = h.memobj.m
    if m[BRANCH_BYTE] != 0xC9:
        raise SystemExit('%s: not the 48K branch (TRAPS #28/#36)' % state)
    return h, m


def arm(h, addr):
    """the $8FE7 bracket: sentinels under the routine, PC on its first byte"""
    r = h.sim.registers
    sp = r[12]
    for sent in reversed(h.SENTINELS):
        sp = (sp - 2) & 0xFFFF
        h.memobj.m[sp] = sent & 0xFF
        h.memobj.m[sp + 1] = sent >> 8
    r[12] = sp
    r[PC] = addr
    return sp


def settle(h, limit=200000):
    """run to a sentinel OR to the step limit, and report WHICH.  A routine
       that spins is not an error here -- it is the measurement."""
    reason, steps = h.run_until(h.SENTINELS, limit=limit, stride=1,
                                interrupts=False)
    return (reason, steps, h.regs[PC])


# ---------------------------------------------------------------- (a) branch
def phase_branch():
    """$8E0A on every 48K state, and the 128K states for contrast."""
    rows = {}
    for s in STATES + ['round1', 'play1p']:
        h = Harness(contended=True)
        h.load_state_file(pc.state_path(s))
        m = h.memobj.m
        rows[s] = {'branch': m[BRANCH_BYTE], 'music_entry': m[MUSIC],
                   'is48': m[BRANCH_BYTE] == 0xC9}
    n48 = sum(1 for r in rows.values() if r['is48'])
    ret = sum(1 for r in rows.values() if r['is48'] and r['music_entry'] == 0xC9)
    print('(a) $8E0A: %d of %d 48K states have $C9 (RET) at the music entry'
          % (ret, n48))
    for s, r in rows.items():
        print('      %-12s $8DC4=%02X  ($8E0A)=%02X  %s'
              % (s, r['branch'], r['music_entry'],
                 '48K' if r['is48'] else '128K'))
    return rows


# ------------------------------------------------------------------- (b) key
def phase_arm():
    """ALL FORTY KEYS through the real $8FE7.  A key that PAUSES makes the
       routine never reach a sentinel; every other key returns at once."""
    rows = []
    for (name, sel, bit) in KEYS:
        h, m = new()
        h.ports.release_all()
        h.ports.press(sel, (~(1 << bit)) & 0xFF)
        arm(h, PAUSE)
        reason, steps, p = settle(h, limit=20000)
        rows.append({'key': name, 'select': sel, 'bit': bit,
                     'spun': reason != 'target', 'steps': steps, 'pc': p})
    h, m = new()
    h.ports.release_all()
    arm(h, PAUSE)
    reason, steps, p = settle(h, limit=20000)
    ctrl = {'key': '(none)', 'spun': reason != 'target', 'steps': steps, 'pc': p}
    spun = [r['key'] for r in rows if r['spun']]
    print('(b) ARM: %d of 40 keys pause -- %s   (no key: %s, %d steps)'
          % (len(spun), ', '.join(spun) or 'NONE',
             'SPUN' if ctrl['spun'] else 'returned', ctrl['steps']))
    for r in rows:
        if r['spun']:
            print('      %-6s select $%02X bit %d -> PC $%04X after %d steps'
                  % (r['key'], r['select'], r['bit'], r['pc'], r['steps']))
    return {'rows': rows, 'control': ctrl}


def phase_release(armkey):
    """with the ARM key held and the routine inside the spin, sweep all forty
       again: which one lets it out?"""
    asel, abit = armkey
    rows = []
    for (name, sel, bit) in KEYS:
        h, m = new()
        h.ports.release_all()
        h.ports.press(asel, (~(1 << abit)) & 0xFF)
        arm(h, PAUSE)
        h.run_until((SPIN,), limit=20000, stride=1, interrupts=False)
        if h.regs[PC] != SPIN:
            raise SystemExit('never reached the spin with the arm key held')
        h.ports.press(sel, (~(1 << bit)) & 0xFF)
        reason, steps, p = settle(h, limit=20000)
        rows.append({'key': name, 'select': sel, 'bit': bit,
                     'freed': reason == 'target', 'steps': steps, 'pc': p})
    freed = [r['key'] for r in rows if r['freed']]
    print('(b) RELEASE: %d of 40 keys free it -- %s'
          % (len(freed), ', '.join(freed) or 'NONE'))
    return rows


# --------------------------------------------------------------- (c) effects
def phase_effects(armkey, relkey):
    """every RAM write and every OUT of one COMPLETE pause, arm to release."""
    (asel, abit), (rsel, rbit) = armkey, relkey
    h, m = new()
    h.ports.release_all()
    h.ports.press(asel, (~(1 << abit)) & 0xFF)
    h.ports.record_writes = True
    h.ports.writes = []
    sp = arm(h, PAUSE)
    h.memobj.watch(0x4000, 0x10000)
    h.memobj.log.clear()
    h.run_until((SPIN,), limit=20000, stride=1, interrupts=False)
    spin_writes = list(h.memobj.log)
    spin_outs = list(h.ports.writes)
    h.ports.press(rsel, (~(1 << rbit)) & 0xFF)
    reason, steps, p = settle(h, limit=20000)
    h.memobj.unwatch()
    allw = list(h.memobj.log)
    allo = list(h.ports.writes)
    # the sentinel frames live just under the entry SP; a PUSH AF there is the
    # routine's own stack and not a change to the world
    stack_lo = (sp - 16) & 0xFFFF
    world = [w for w in allw if not (stack_lo <= w[1] <= sp + 16)]
    border = [(o[1] & 0xFF, o[2] & 0x07) for o in allo if (o[1] & 0xFF) == 0xFE]
    print('(c) EFFECTS: %d RAM writes in total, %d of them OUTSIDE the stack'
          % (len(allw), len(world)))
    for w in world[:8]:
        print('      PC $%04X -> $%04X = $%02X' % (w[0], w[1], w[2]))
    print('    OUT ($FE) values in order: %s'
          % ' '.join('%d' % v for _, v in border))
    return {'ram_writes': len(allw), 'world_writes': len(world),
            'world': [[w[0], w[1], w[2]] for w in world],
            'spin_writes': len(spin_writes), 'spin_outs': len(spin_outs),
            'border': [v for _, v in border], 'exit_steps': steps}


# ---------------------------------------------------------------- (d) resume
def phase_resume(armkey, relkey):
    """THE PASS IS SUSPENDED, NOT RESTARTED.  Enter the chain at $8D25 with the
       arm key down; it must settle in the spin.  Release it, and the NEXT
       chain address reached must be $900B -- the entry after the pause -- not
       $8D25 and not $8FA5."""
    (asel, abit), (rsel, rbit) = armkey, relkey
    h, m = new()
    h.ports.release_all()
    h.ports.press(asel, (~(1 << abit)) & 0xFF)
    arm(h, CHAIN0)
    h.run_until((SPIN,), limit=400000, stride=1, interrupts=False)
    if h.regs[PC] != SPIN:
        raise SystemExit('the chain did not reach the spin -- PC $%04X'
                         % h.regs[PC])
    t_spin = h.regs[T]
    snap = h.snapshot(0x4000, 0x10000)
    pcs = set()
    for _ in range(4000):
        h.step(1, interrupts=False)
        pcs.add(h.regs[PC])
    quiet = h.diff(snap, 0x4000, 0x10000)
    h.ports.press(rsel, (~(1 << rbit)) & 0xFF)
    reason, steps = h.run_until((AFTER_PAUSE, CHAIN0, 0x8FA5), limit=20000,
                                stride=1, interrupts=False)
    landed = h.regs[PC]
    print('(d) RESUME: the spin visits %d distinct PCs %s; %d bytes changed '
          'while paused; on release the chain lands at $%04X (%s)'
          % (len(pcs), '$%04X..$%04X' % (min(pcs), max(pcs)), len(quiet),
             landed, 'THE ENTRY AFTER THE PAUSE' if landed == AFTER_PAUSE
             else 'NOT $900B'))
    return {'spin_pcs': sorted(pcs), 'quiet_bytes': len(quiet),
            'landed': landed, 'steps': steps, 'spin_t': t_spin}


# -------------------------------------------------------- (e) the DI interval
def phase_di(armkey):
    """the spin runs with INTERRUPTS OFF.  Drive it with interrupts ENABLED in
       the simulator and show the ISR still never runs."""
    asel, abit = armkey
    h, m = new()
    h.ports.release_all()
    h.ports.press(asel, (~(1 << abit)) & 0xFF)
    arm(h, PAUSE)
    h.run_until((SPIN,), limit=20000, stride=1, interrupts=False)
    isr_pc = 0x8D72
    seen = 0
    N = 200000
    for _ in range(N):
        h.step(1, interrupts=True)
        if h.regs[PC] == isr_pc:
            seen += 1
    print('(e) DI: %d ISR entries in %d steps of the spin' % (seen, N))
    return {'isr_entries': seen, 'steps': N}


def capture():
    out = {}
    out['branch'] = phase_branch()
    a = phase_arm()
    out['arm'] = a
    spun = [r for r in a['rows'] if r['spun']]
    if len(spun) != 1:
        raise SystemExit('the arm sweep found %d keys, not 1' % len(spun))
    armkey = (spun[0]['select'], spun[0]['bit'])
    out['arm_key'] = spun[0]['key']
    rel = phase_release(armkey)
    out['release'] = rel
    freed = [r for r in rel if r['freed']]
    if len(freed) != 1:
        raise SystemExit('the release sweep found %d keys, not 1' % len(freed))
    relkey = (freed[0]['select'], freed[0]['bit'])
    out['release_key'] = freed[0]['key']
    out['effects'] = phase_effects(armkey, relkey)
    out['resume'] = phase_resume(armkey, relkey)
    out['di'] = phase_di(armkey)
    json.dump(out, open(FIXTURE, 'w'), indent=1)
    print('\nwrote %s' % FIXTURE)
    return out


if __name__ == '__main__':
    capture()
