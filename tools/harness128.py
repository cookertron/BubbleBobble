#!/usr/bin/env python3
"""
harness128.py -- THE 128K MACHINE: SkoolKit 10's contended simulator over
pagingtracer.Memory, with tools/harness.py's API wherever it fits.

For a port whose game has a 128K branch (an AY music engine in a paged bank,
say).  tools/harness.py's opt-in shim, Harness(paging=$10), is the OTHER
machine: the 128K branch's code on the 48K clock, which is what a port that
measured everything else on the 48K runs.  This file is the 128K machine
itself: what that shim's declared differences (the frame, the clock, the
contention, the ROMs) are measured against, and the oracle for a port that
models the 128K outright.

ENGINES
  engine='py'  skoolkit.cmiosimulator.CMIOSimulator, pure Python, contended
               (the 128K's pattern because the memory is 128K).  THE REFERENCE.
  engine='c'   skoolkit.CCMIOSimulator, SkoolKit's C port of the same class,
               about 3.4x faster through this loop.  An accelerator only:
               selftest proves it identical to 'py' -- registers, T, all eight
               banks and every log -- on a program that pages, writes the AY,
               runs contended and HALTs under interrupts.  (The C core pages
               on OUT ($7FFD) by itself; the tracer here pages too, so the two
               views agree while the lock bit is clear.)

MACHINE (simutils): frame 70,908 T, the interrupt active 36 T, 3,546,900 Hz;
contention from T 14,361 on 228-T lines, on banks 1/3/5/7 at $C000 and bank 5
at $4000.  FRAME NUMBER = T // 70,908, with T the simulator's absolute clock
(a snapshot's own T-states to start); t = T % 70,908.

API (harness.Harness's names where they fit):
  h = Harness128(snapshot=None|path|False, engine='py'|'c', state=None, out7ffd=None)
      snapshot None -> port.json z80.snapshot128 if it is set and exists, else
      a blank machine; False -> a blank machine: zeroed banks, PC 0, IM 1,
      IFF 0, $7FFD = out7ffd (default $10: ROM 1, bank 0).  A 48K snapshot is
      refused.  state: a pickle path or a save_state() tuple to start from.
  h.regs h.mem h.ports h.pc() h.tstates() h.frame() h.t_in_frame() h.o7ffd()
  h.paged() h.hl() h.de() h.bc() h.ix() h.iy()
  h.peek(a, n) / h.peek16(a) / h.poke(a, *v)   the CPU's view (writes below $4000 ignored)
  h.bank_peek(b, a, n) / h.bank_poke(b, a, *v)  one bank, a = a $C000-based address or an offset
  h.step(n) / h.run_until(targets, limit, stride, interrupts, predicate) -> (reason, steps)
      reason 'target' (PC at a target, not executed), 'limit', 'predicate', 'time',
      or the string a hook put in h.stop_now
  h.run_frames(n) / h.run_to_frame(f)
  h.call(addr, regs, limit, interrupts=False) -> (sentinel index | None, T, steps)
  h.set_regs({'A': .., 'BC': .., 'SP': ..}) / h.push(v)
  h.add_hook(pc, fn(h, pc, prev)) / h.clear_hooks()
      fn runs as PC arrives at pc, before the instruction; h.stop_now = 'why'
      inside it ends the run there (PC still at pc; resuming does not re-fire it)
  h.on_return(fn(h))   inside a hook at a routine's entry: fn runs once, when
      that CALL returns (PC at the return address with SP back above it)
  h.frame_hooks        [fn(h, frame)]: at the first instruction boundary at or
      past each frame's start, BEFORE that frame's interrupt is accepted
      (regs[IFF] 0 there = the frame's interrupt is lost)
  h.keys([names]) / h.drive([(frames, [names]), ...] or '40:,3:4')   keyprobe's names
  h.save_state() / h.load_state(s) / h.save_state_file(p) / h.load_state_file(p)
      (the eight banks, $7FFD, the registers, the ports and the AY -- no ROM byte, no log)
  h.mark(name) / h.since(name[, upto])   the logs between marks
  h.watch_bank(b, on)  (engine 'py') count every write into bank b while it is
      paged at $C000, by (PC, address), in h.bank_writes
  h.fast_halt = False  execute every HALT cycle (selftest proves the skip exact)
  h.ctx                any value: stamped on each AY row (set it in your hooks)

PORTS (the tracer): the keyboard matrix and Kempston exactly as harness.Ports
(B = 0 selects every half-row); $7FFD (port & $8002 == 0) pages unless bit 5
has locked it; the AY's register select and read $FFFD (port & $C002 ==
$C000, unimplemented bits read 0), its data $BFFD (port & $C002 == $8000);
an even port is the ULA: border and speaker, an EDGE a change of bit 4.
Unattached ports read $FF.

LOGS (rows; T is the tracer's: the start of the OUT / IN instruction, before
its own contention and length -- SkoolKit calls the tracer first):
  ay_log     [frame, t, pc, reg, val, T, ctx]
  ay_reads   [frame, t, pc, reg, val, T]
  ay_ignored [frame, t, pc, latch, val, T]     a data write with the latch >= 16
  p7ffd_log  [frame, t, pc, val, T, applied]
  spk_log    [frame, t, pc, val, T]            bit 4 of an OUT to an even port changed
  fe_count   {pc: n}                           every OUT to an even port

HALT: like tools/harness.py the clock is jumped instead of executing ~17,000
HALT cycles a frame, but EXACTLY as the simulator's own HALT loop would end:
the first 4-T HALT cycle is executed by the simulator; if the CPU is still
halted the remaining k cycles are skipped to the first T with T % 70,908 < 36
(T + 4k), R advanced by k, then the interrupt accepted.  Only when the HALT's
refetch address is uncontended; otherwise every cycle runs (slow_halts).

Usage:  python tools/harness128.py [snapshot.z80]    (prints the machine)
"""
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from skoolkit import simutils as U                        # noqa: E402
from skoolkit.pagingtracer import Memory                  # noqa: E402
from skoolkit.cmiosimulator import CMIOSimulator          # noqa: E402
from skoolkit.snapshot import Snapshot                    # noqa: E402
try:
    from skoolkit import CCMIOSimulator                   # noqa: E402
except ImportError:                                       # pragma: no cover
    CCMIOSimulator = None

import keyprobe                                           # noqa: E402
import portconfig                                         # noqa: E402
from harness import AY_MASK                               # noqa: E402

# --- SkoolKit register indices --------------------------------------------
A, F, B, C, D, E, H, L = 0, 1, 2, 3, 4, 5, 6, 7
IXh, IXl, IYh, IYl = 8, 9, 10, 11
SP, I, R = 12, 14, 15
xA, xF, xB, xC, xD, xE, xH, xL = 16, 17, 18, 19, 20, 21, 22, 23
PC, T, IFF, IM, HALT, MEMPTR = 24, 25, 26, 27, 28, 29

FRAME_T = U.FRAME_DURATIONS[1]          # 70,908
INT_ACTIVE = U.INT_ACTIVE[1]            # 36
CPU_HZ = U.CLOCK_SPEEDS[1]              # 3,546,900
SENTINELS = (0xFE00, 0xFE02, 0xFE04, 0xFE06, 0xFE08, 0xFE0A)


class WatchMemory(Memory):
    """pagingtracer.Memory that counts writes into bank h.watched while it is
    paged at $C000 (the Python engine only: the C core writes its bytearrays
    directly).  Swapped in and out by assigning __class__, so the unwatched
    path costs nothing."""

    def __setitem__(self, index, value):
        if index >= 0xC000 and self.o7ffd & 7 == self.h.watched:
            key = (self.h.sim.registers[PC], index)
            w = self.h.bank_writes
            w[key] = w.get(key, 0) + 1
        self.memory[index // 0x4000][index % 0x4000] = value


class Ports128:
    """The 128K tracer: keyboard and Kempston as harness.Ports, $7FFD paging,
    the AY's latch, data and read, the ULA's border and speaker."""

    def __init__(self, h, out7ffd, outfffd, ay, outfe):
        self.h = h
        self.pressed = {}
        self.kempston = 0x00
        self.unattached = 0xFF
        self.out7ffd = out7ffd
        self.outfffd = outfffd
        self.ay = list(ay)
        self.outfe = outfe
        self.border = outfe & 7
        self.reads = {}

    # -- input, exactly harness.Ports -------------------------------------
    def press(self, select, value):
        self.pressed[select] = self.pressed.get(select, 0xFF) & value

    def release_all(self):
        self.pressed.clear()
        self.kempston = 0x00

    def read_port(self, registers, port):
        self.reads[port] = self.reads.get(port, 0) + 1
        low = port & 0xFF
        if low & 1 == 0:
            hi = (port >> 8) & 0xFF
            v = 0xFF
            if hi == 0:
                for val in self.pressed.values():
                    v &= val
            else:
                for select, val in self.pressed.items():
                    if (~hi & ~select) & 0xFF:
                        v &= val
            return v
        if port & 0xC002 == 0xC000:                    # $FFFD: the latched AY register
            r = self.outfffd
            v = (self.ay[r] & AY_MASK[r]) if r < 16 else 0xFF
            self.h._on_ay_read(registers, r, v)
            return v
        if low == 0x1F:
            return self.kempston
        return self.unattached

    def write_port(self, registers, port, value):
        h = self.h
        if port & 1 == 0:                               # the ULA
            old = self.outfe
            self.outfe = value
            self.border = value & 7
            h._on_fe(registers, value, old)
        if port & 0x8002 == 0:                          # $7FFD
            applied = not (self.out7ffd & 0x20)
            if applied:
                h.sim.memory.out7ffd(value)
                self.out7ffd = value
            h._on_7ffd(registers, value, applied)
        if port & 0xC002 == 0xC000:                     # $FFFD: register select
            self.outfffd = value
        elif port & 0xC002 == 0x8000:                   # $BFFD: data into the latched register
            r = self.outfffd
            if r < 16:
                self.ay[r] = value
                h._on_ay(registers, r, value)
            else:
                t = registers[T]
                h.ay_ignored.append([t // FRAME_T, t % FRAME_T, registers[PC], r, value, t])

    def state(self):
        return {'out7ffd': self.out7ffd, 'outfffd': self.outfffd, 'ay': list(self.ay),
                'outfe': self.outfe, 'border': self.border}

    def set_state(self, s):
        self.out7ffd = s['out7ffd']
        self.outfffd = s['outfffd']
        self.ay = list(s['ay'])
        self.outfe = s['outfe']
        self.border = s['border']


class Harness128:
    """A 128K machine (the module docstring is the manual)."""

    SENTINELS = SENTINELS
    LOGS = ('ay_log', 'ay_reads', 'ay_ignored', 'p7ffd_log', 'spk_log')

    def __init__(self, snapshot=None, engine='py', state=None, out7ffd=None):
        if engine not in ('py', 'c'):
            raise ValueError(f'engine {engine!r}: py or c')
        if engine == 'c' and CCMIOSimulator is None:
            raise RuntimeError('this SkoolKit has no CCMIOSimulator (engine="c")')
        self.engine = engine
        self.cls = CMIOSimulator if engine == 'py' else CCMIOSimulator
        if snapshot is None:
            cfg = portconfig.path(portconfig.get('z80', 'snapshot128'))
            snapshot = cfg if cfg is not None and os.path.exists(cfg) else False
        cfg = {'frame_duration': FRAME_T, 'int_active': INT_ACTIVE}
        if snapshot is False:
            o = 0x10 if out7ffd is None else out7ffd
            self.snapshot_path = None
            self.info = f'blank 128K: $7FFD=${o:02X} PC=$0000 IM=1 IFF=0'
            self.sim = self.cls(Memory(None, o, '128K'), {'PC': 0, 'SP': 0xFFFF},
                                {'im': 1, 'iff': 0, 'tstates': 0}, cfg)
            ports = (o, 0, [0] * 16, 0)
        else:
            snap = Snapshot.get(snapshot)
            if len(snap.ram(-1)) != 0x20000:
                raise RuntimeError(f'{snapshot} is a 48K snapshot: tools/harness.py is the 48K machine')
            self.snapshot_path = snapshot
            self.info = (f'snapshot {os.path.basename(snapshot)} ({snap.type}, {snap.machine}): PC=${snap.pc:04X} '
                         f'SP=${snap.sp:04X} IM={snap.im} IFF={snap.iff1} 7FFD=${snap.out7ffd:02X} T={snap.tstates}')
            self.sim = U.from_snapshot(self.cls, snap)
            o = snap.out7ffd if out7ffd is None else out7ffd
            ports = (o, snap.outfffd, list(snap.ay), snap.outfe)
        self.sim.memory.out7ffd(o)
        self.ports = Ports128(self, *ports)
        self.sim.memory.h = self
        self.sim.set_tracer(self.ports)
        if engine == 'py':        # the C core keeps its own copy: selftest holds it to the py engine
            assert (self.sim.frame_duration, self.sim.int_active) == (FRAME_T, INT_ACTIVE)
        self.user_hooks = {}          # pc -> [fn(h, pc, prev)], kept across load_state
        self.frame_hooks = []
        self.stop_now = None
        self.fast_halt = True
        self.watched = None
        self.ctx = None
        self._reset_tracking()
        self.clear_logs()
        if state is not None:
            if isinstance(state, str):
                self.load_state_file(state)
            else:
                self.load_state(state)

    # -- bookkeeping ------------------------------------------------------
    def _reset_tracking(self):
        self.dyn = {}                 # pc -> [(fn, sp)]: one-shot return hooks
        self._last_hook = (-1, -1)
        self.prev_pc = None
        self._nb = None
        self.halts_skipped = 0
        self.slow_halts = 0
        self._rebuild_hooks()

    def clear_logs(self):
        self.ay_log = []
        self.ay_reads = []
        self.ay_ignored = []
        self.p7ffd_log = []
        self.spk_log = []
        self.fe_count = {}
        self.bank_writes = {}
        self.marks = {}

    def _rebuild_hooks(self):
        hk = {}
        for pc, fns in self.user_hooks.items():
            for fn in fns:
                hk.setdefault(pc, []).append(lambda p, q, fn=fn: fn(self, p, q))
        for pc, lst in self.dyn.items():
            if lst:
                hk.setdefault(pc, []).append(self._dyn_dispatch)
        self.hooks = hk

    def add_hook(self, pc, fn):
        self.user_hooks.setdefault(pc, []).append(fn)
        self._rebuild_hooks()

    def clear_hooks(self):
        self.user_hooks = {}
        self._rebuild_hooks()

    def on_return(self, fn):
        """Call inside a hook at a routine's entry (PC there, its return address
        on top of the stack): fn(h) runs once, when that CALL returns."""
        m = self.sim.memory
        sp = self.sim.registers[SP]
        ret = m[sp] | (m[(sp + 1) & 0xFFFF] << 8)
        self.dyn.setdefault(ret, []).append((lambda p, q: fn(self), (sp + 2) & 0xFFFF))
        self.hooks.setdefault(ret, [])
        if self._dyn_dispatch not in self.hooks[ret]:
            self.hooks[ret].append(self._dyn_dispatch)

    def _dyn_dispatch(self, pc, prev):
        lst = self.dyn.get(pc)
        if not lst:
            return
        sp = self.sim.registers[SP]
        keep, fired = [], []
        for f, want_sp in lst:
            (fired if want_sp == sp else keep).append((f, want_sp))
        if keep:
            self.dyn[pc] = keep
        else:
            del self.dyn[pc]
            self.hooks[pc] = [g for g in self.hooks[pc] if g != self._dyn_dispatch]
            if not self.hooks[pc]:
                del self.hooks[pc]
        for f, _ in fired:
            f(pc, prev)

    # -- accessors --------------------------------------------------------
    @property
    def regs(self):
        return self.sim.registers

    @property
    def mem(self):
        return self.sim.memory

    def reg16(self, hi, lo):
        return self.sim.registers[lo] + 256 * self.sim.registers[hi]

    def hl(self):
        return self.reg16(H, L)

    def de(self):
        return self.reg16(D, E)

    def bc(self):
        return self.reg16(B, C)

    def ix(self):
        return self.reg16(IXh, IXl)

    def iy(self):
        return self.reg16(IYh, IYl)

    def pc(self):
        return self.sim.registers[PC]

    def tstates(self):
        return self.sim.registers[T]

    def frame(self):
        return self.sim.registers[T] // FRAME_T

    def t_in_frame(self):
        return self.sim.registers[T] % FRAME_T

    def o7ffd(self):
        return self.sim.memory.o7ffd

    def paged(self):
        return self.sim.memory.o7ffd & 7

    def peek(self, a, n=1):
        m = self.sim.memory
        return bytes(m[(a + i) & 0xFFFF] for i in range(n))

    def peek16(self, a):
        m = self.sim.memory
        return m[a] | (m[(a + 1) & 0xFFFF] << 8)

    def poke(self, a, *vals):
        """The CPU's view; writes below $4000 are ignored, as on the machine."""
        m = self.sim.memory
        for i, v in enumerate(vals):
            ad = (a + i) & 0xFFFF
            if ad >= 0x4000:
                m.memory[ad // 0x4000][ad % 0x4000] = v & 0xFF

    def bank_peek(self, bank, addr, n=1):
        """Bank `bank` at a $C000-based address (or a 0..$3FFF offset)."""
        off = addr - 0xC000 if addr >= 0xC000 else addr
        return bytes(self.sim.memory.banks[bank][off:off + n])

    def bank_poke(self, bank, addr, *vals):
        off = addr - 0xC000 if addr >= 0xC000 else addr
        b = self.sim.memory.banks[bank]
        for i, v in enumerate(vals):
            b[off + i] = v & 0xFF

    def watch_bank(self, bank, on=True):
        """Count every write into `bank` while it is paged at $C000, by (PC,
        address), in bank_writes -- engine 'py' only."""
        if self.engine != 'py':
            raise RuntimeError('watch_bank needs engine="py"')
        self.watched = bank if on else None
        self.sim.memory.__class__ = WatchMemory if on else Memory

    # -- the tracer's log callbacks -----------------------------------------
    def _on_fe(self, regs, value, old):
        pc = regs[PC]
        self.fe_count[pc] = self.fe_count.get(pc, 0) + 1
        if (value ^ old) & 0x10:
            t = regs[T]
            self.spk_log.append([t // FRAME_T, t % FRAME_T, pc, value, t])

    def _on_7ffd(self, regs, value, applied):
        t = regs[T]
        self.p7ffd_log.append([t // FRAME_T, t % FRAME_T, regs[PC], value, t, applied])

    def _on_ay(self, regs, r, value):
        t = regs[T]
        self.ay_log.append([t // FRAME_T, t % FRAME_T, regs[PC], r, value, t, self.ctx])

    def _on_ay_read(self, regs, r, value):
        t = regs[T]
        self.ay_reads.append([t // FRAME_T, t % FRAME_T, regs[PC], r, value, t])

    def _frame_boundary(self):
        f = self.sim.registers[T] // FRAME_T
        self._nb = (f + 1) * FRAME_T
        for fn in self.frame_hooks:
            fn(self, f)

    # -- running ------------------------------------------------------------
    def _halt_ff(self, pc):
        """One HALT cycle ran and the CPU is still halted (IFF 1, outside the
        interrupt window): skip the remaining k cycles exactly."""
        regs = self.sim.registers
        t = regs[T]
        nbt = (t // FRAME_T + 1) * FRAME_T
        k = (nbt - t + 3) // 4
        regs[T] = t + 4 * k
        regs[R] = (regs[R] & 0x80) | ((regs[R] + k) & 0x7F)
        regs[PC] = (pc + 1) & 0xFFFF
        regs[HALT] = 0
        self.halts_skipped += k
        if self._nb is not None and regs[T] >= self._nb:
            self._frame_boundary()               # before the acceptance: IFF as the frame starts
        self.sim.accept_interrupt(regs, self.sim.memory, pc)

    def _run(self, t_stop=None, targets=None, limit=None, interrupts=True,
             predicate=None, stride=4096):
        sim = self.sim
        regs = sim.registers
        mem = sim.memory
        fd, ia = FRAME_T, INT_ACTIVE
        py = self.engine == 'py'
        ops = sim.opcodes if py else None
        run1 = None if py else sim.run
        accept = sim.accept_interrupt
        if self._nb is None or self._nb <= regs[T] - fd or self._nb > regs[T] + fd:
            self._nb = (regs[T] // fd + 1) * fd
        nb = self._nb
        tg = set(targets) if targets else None
        prev = self.prev_pc
        last_hook = self._last_hook
        n = 0
        reason = None
        hooks = self.hooks
        while True:
            pc = regs[PC]
            if pc in hooks:
                key = (pc, regs[T])
                if key != last_hook:
                    last_hook = key
                    for f in list(hooks.get(pc, ())):
                        f(pc, prev)
                    hooks = self.hooks
                    if self.stop_now is not None:
                        reason = self.stop_now
                        self.stop_now = None
                        break
                    if regs[PC] != pc:
                        continue
            if tg is not None and pc in tg:
                reason = 'target'
                break
            if py:
                ops[mem[pc]]()
            else:
                run1()
            if regs[HALT]:
                if interrupts and regs[IFF]:
                    a1 = (pc + 1) & 0xFFFF
                    if not self.fast_halt or 0x4000 <= a1 < 0x8000 or (a1 >= 0xC000 and mem.o7ffd & 1):
                        self.slow_halts += 1
                    else:
                        self._halt_ff(pc)
                        nb = self._nb
            elif interrupts and regs[IFF] and regs[T] % fd < ia:
                if regs[T] >= nb:
                    self._frame_boundary()
                    nb = self._nb
                accept(regs, mem, pc)
            prev = pc
            n += 1
            if regs[T] >= nb:
                self._frame_boundary()
                nb = self._nb
            if t_stop is not None and regs[T] >= t_stop:
                reason = 'time'
                break
            if limit is not None and n >= limit:
                reason = 'limit'
                break
            if predicate is not None and n % stride == 0 and predicate(self):
                reason = 'predicate'
                break
        self.prev_pc = prev
        self._last_hook = last_hook
        return reason, n

    def step(self, n=1, interrupts=True):
        return self._run(limit=n, interrupts=interrupts)[1]

    def run_until(self, targets=(), limit=50_000_000, stride=4096, interrupts=True, predicate=None):
        if isinstance(targets, int):
            targets = (targets,)
        return self._run(targets=targets, limit=limit, interrupts=interrupts,
                         predicate=predicate, stride=stride)

    def run_frames(self, n, interrupts=True):
        """Advance n frames of T (to the same phase).  Returns the instructions run."""
        return self._run(t_stop=self.sim.registers[T] + n * FRAME_T, interrupts=interrupts)[1]

    def run_to_frame(self, f, interrupts=True):
        """Run until the clock reaches frame f's start (T >= f * 70,908)."""
        return self._run(t_stop=f * FRAME_T, interrupts=interrupts)[1]

    def call(self, addr, regs=None, limit=5_000_000, interrupts=False):
        """harness.Harness.call: six distinct sentinels pushed; returns
        (sentinel index or None, T, steps).  Restore SP yourself in a loop."""
        r = self.sim.registers
        for s in reversed(self.SENTINELS):
            self.push(s)
        if regs:
            self.set_regs(regs)
        r[PC] = addr
        t0 = r[T]
        reason, steps = self.run_until(self.SENTINELS, limit=limit, interrupts=interrupts)
        if reason != 'target':
            return (None, r[T] - t0, steps)
        return (self.SENTINELS.index(r[PC]), r[T] - t0, steps)

    def set_regs(self, d):
        r = self.sim.registers
        for k, v in d.items():
            if k in ('HL', 'DE', 'BC', 'IX', 'IY'):
                hi, lo = {'HL': (H, L), 'DE': (D, E), 'BC': (B, C), 'IX': (IXh, IXl), 'IY': (IYh, IYl)}[k]
                r[hi], r[lo] = (v >> 8) & 0xFF, v & 0xFF
            elif k == 'SP':
                r[SP] = v & 0xFFFF
            else:
                r[U.REGISTERS[k]] = v

    def push(self, v):
        r = self.sim.registers
        m = self.sim.memory
        sp = (r[SP] - 2) & 0xFFFF
        m[sp] = v & 0xFF
        m[(sp + 1) & 0xFFFF] = (v >> 8) & 0xFF
        r[SP] = sp

    # -- keys (keyprobe's names and script format) --------------------------
    def keys(self, names):
        self.ports.release_all()
        for k in names:
            keyprobe.press(self.ports, k)

    def drive(self, script):
        """keyprobe.drive: [(frames, [keys]), ...] or '40:,3:4,...'."""
        if isinstance(script, str):
            script = keyprobe.parse_script(script)
        for frames, names in script:
            self.keys(names)
            self.run_frames(frames)
        self.ports.release_all()

    # -- states ---------------------------------------------------------------
    def save_state(self):
        m = self.sim.memory
        return ('h128/1', [bytes(b) for b in m.banks], m.o7ffd, [int(x) for x in self.sim.registers],
                self.ports.state())

    def load_state(self, s):
        tag, banks, o7ffd, regs, ports = s
        assert tag == 'h128/1', tag
        watched = self.watched
        mem = Memory([list(b) for b in banks], o7ffd, '128K')
        self.sim = self.cls(mem, {}, {}, {'frame_duration': FRAME_T, 'int_active': INT_ACTIVE})
        r = self.sim.registers
        for i, v in enumerate(regs):
            r[i] = v
        self.sim.memory.out7ffd(o7ffd)
        self.sim.memory.h = self
        self.ports.set_state(ports)
        self.ports.release_all()
        self.ports.out7ffd = o7ffd
        self.sim.set_tracer(self.ports)
        if watched is not None:
            self.watch_bank(watched)
        self._reset_tracking()

    def save_state_file(self, path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self.save_state(), f)

    def load_state_file(self, path):
        with open(path, 'rb') as f:
            self.load_state(pickle.load(f))

    # -- marks ------------------------------------------------------------------
    def mark(self, name):
        self.marks[name] = {'T': self.sim.registers[T], 'frame': self.frame(),
                            **{k: len(getattr(self, k)) for k in self.LOGS},
                            'fe_count': dict(self.fe_count)}
        return self.marks[name]

    def since(self, name, upto=None):
        """The logs between mark `name` and mark `upto` (or now)."""
        m0 = self.marks[name]
        m1 = self.marks[upto] if upto else None
        out = {'T0': m0['T'], 'frame0': m0['frame'],
               'T1': m1['T'] if m1 else self.sim.registers[T],
               'frame1': m1['frame'] if m1 else self.frame()}
        for k in self.LOGS:
            lst = getattr(self, k)
            out[k] = lst[m0[k]:(m1[k] if m1 else len(lst))]
        fe1 = m1['fe_count'] if m1 else self.fe_count
        out['fe_count'] = {pc: n - m0['fe_count'].get(pc, 0) for pc, n in fe1.items()
                           if n - m0['fe_count'].get(pc, 0)}
        return out


def silent(ay):
    """The AY makes no sound: every tone and noise off in R7, or every
    channel's amplitude 0 with the envelope bit clear."""
    return (ay[7] & 0x3F) == 0x3F or all((ay[r] & 0x1F) == 0 for r in (8, 9, 10))


if __name__ == '__main__':
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip())
        sys.exit(0)
    h = Harness128(sys.argv[1] if len(sys.argv) > 1 else None)
    print(h.info)
    print(f'engine {h.engine}  frame {FRAME_T} T  interrupt {INT_ACTIVE} T  {CPU_HZ} Hz  '
          f'PC ${h.pc():04X}  frame #{h.frame()}  bank {h.paged()} at $C000')
