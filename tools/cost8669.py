"""M7.89 (measurement) -- THE ITEM MANAGER'S T ($8669 and its callees), RUN BY RUN, UNCONTENDED.

passcost (M7.86): $8669 is 11.7% of the main loop's T (no blocks), 206..69,539 T (median 211), own
129..1,841 over 84 paths, children $86A9 / $86B1 / $89CB, and 147 calls that are frame-long BLOCKS.
This oracle records every run of $8669 from its one caller ($8D4C CALL $8669) on an UNCONTENDED
machine, so a run's T is the sum of its instructions' own T, and brackets EVERY nested CALL apart by
entry PC + return SP (popcost's way), so each routine's `own` is its own instructions:

  $8669  CALL $89CB; the carried bypass (BIT 4 of P1's +$5A / +$64, JR nz -> $8689); the edge gate
         ($867F CP n, n = $8680 its own operand; $8684 RET z); INC ($86CD); the walk of 31 fruit
         entries from $9605 (CALL nz,$86A9), INC ($872C), the power-up slot $9603 by FALLING INTO
         $86A9 (PUSH / PUSH / CALL $86B1 / POP / POP / RET at $8669's own level)
  $89CB  the spawn flow (two CPIRs at $8A28 / $8A3E, counted)            -- itemSpawn / puSpawn*
  $86A9  PUSH HL / PUSH BC / CALL $86B1 / POP BC / POP HL / RET          -- itemEntry's wrapper
  $86B1  unpack, collide P2 then P1, the clock ($86CC), the expiry ($86E4 falls into the ERASE
         body $86E6, which JPs to $A314's body), the weather skips and the ink ($8728, JP $A2C2's
         body): $A314's and $A2C2's bodies run in $86B1's frame and are charged to its own
  $86E6  the ERASE body when CALLed from the collect ($87F4) -- the same code as above
  $8779  the unpack; $87B2 the collect (its first byte an OPCODE: NOP / RET, TRAPS #278);
  $930A / $9312 the box tests; $AEDC the shadow cell; $876C an erase cell; $8765 an ink cell;
  $A2D5 / $A2FB the blit and its band (the $A307 / $A30C opcodes: NOP under $A2C2); $A34D a
  restore band; $9F5C RRA x3 / AND / RET

LABELLED APART, NOT MODELLED (their T recorded, not summed into anyone's own):
  award  $80FA, the score award (exact in the engine: BB_AW, awardcost)
  chirp  $8CB1, the collect chirp (exact in the engine: itemChirp)
  pu     the POWER-UP EFFECT: from $8838 JP (HL) (the $8839 table, by the type in $8828) to $87B2's
         RET, labelled by its target -- the frame-long BLOCKS live here
Every interrupt accepted inside a run is BRACKETED OUT (passcost's way); such a run keeps its T and
paths, its seed/post are not kept ('irq').  A HALT is allowed only inside a labelled frame ('halt').

  T        the $8669 run, entry to RET, the ISRs out (its children IN)
  own      T less every nested child's T
  sig      its path: each conditional at its own level, pc + t/f ('t' = control did not fall
           through); a CPIR/LDIR's every repeat is a 't', its last a 'f'
  calls    every modelled frame nested in the run: [entry, mode, own, sig]
  opaque   every labelled frame: [label, entry/target, T]
  seed     every byte the run READS before it writes it (not its own instruction bytes; the
           self-modified operands read as STATE -- $8680 $86CD $86CF $872C $8769 $8828 $A304 $A33D
           $A349 $A355 $FE86/7 -- in, and the self-modified OPCODES $87B2 $A307 $A30C at their own
           PC, TRAPS #275/#278), the ROM's VALUES never (TRAPS #281: their count in 'rom');
           post: every byte written, final value, stack and ROM out; when 'rom' > 0 the bitmap
           writes are addresses only ('blind')

THE MODEL (Zilog T, asserted against EVERY modelled frame of EVERY run, natural and forced): one
path-walker per routine below (M_*), its terms in W with their instruction lists.

Every 48K saved state in aa60cost's list, 300 frames, interrupts on, ab38cost's key script through
each player's own key table.  FORCED CALLS (declared, CALLS below) for branches no natural run takes:
$8669 called once from a saved state with pokes, interrupts off at entry, returning to $8D4F.
No value below $4000 is stored; $D000..$D2FF is never executed (asserted).

UNREACHED, DECLARED: $A34C RET z falling into a third restore band from $86B1 / $86E6 (the record's
Y at $8909 is written AND $F8 by $8779, so Y & 7 = 0: _band3 is exercised only through $A34D's own
frames); $A2D5 / $A2FB with $A307 / $A30C = OR (HL) ('O', K_ROW_OR: $A2C2 NOPs them first); the
power-up effects' T (labelled 'pu', by target).

  contended  {state: [[n, T] uncontended, [n, T] contended]} over the natural runs with no interrupt
             AND no labelled frame (award / chirp / pu: timed by their own code) -- the stretch the
             main loop's wall clock sees on the modelled part.

  window     M7.92 (costc002's): round1_48's first WINDOW frames, contention off and on, NO KEYS -- [runs,
             total T, {own: [n, T]}] over all runs and over the 11-pass frames' ('eleven'), the labelled and
             interrupted runs counted -- the frames BB_PASS_T was CALIBRATED
             on (the timing census, build/timing_fixture.json 'seq': 48 frames), so the share the flat rest gives
             up is the 11-pass frames' contended mean, whose count BB_PASS_T was fit to (TRAPS #286: AS
             CALIBRATED; the whole window's 387 left a carry-dependent 12th pass in one of them) and the stretch is its contended T over its
             uncontended T PATH BY PATH (the edge gate walks once a frame, so mean over mean is the mix's ratio)

Usage:  python tools/cost8669.py [--jobs N]          (-> build/cost8669_fixture.json, N <= 6)
        python tools/cost8669.py verify [--jobs N]   (re-measure, compare, say MATCH)
"""
import sys, json, collections
from multiprocessing import Pool
sys.path.insert(0, 'tools')
from harness import Harness, T, PC, IFF, SP
from skoolkit.simutils import R as REG_R
import portconfig as pc
import aa60cost as A
import ab38cost as B

FIXTURE = 'build/cost8669_fixture.json'
FRAMES = 300
WINDOW = 48       # M7.92: the timing census's frames (BB_PASS_T's calibration), round1_48 from its start
KEEP = 2
ENTRY, CALLER, BACK = 0x8669, 0x8D4C, 0x8D4F
OPAQUE = {0x80FA: 'award', 0x8CB1: 'chirp'}
PU_JP = 0x8838
STATE_OPS = {0x867F: (0x8680,), 0x86CC: (0x86CD,), 0x86CE: (0x86CF,), 0x872B: (0x872C,),
             0x8768: (0x8769,), 0x8827: (0x8828,), 0xA303: (0xA304,), 0xA33C: (0xA33D,),
             0xA348: (0xA349,), 0xA354: (0xA355,), 0xFE85: (0xFE86, 0xFE87)}
SMC_OPCODES = (0x87B2, 0xA307, 0xA30C)
CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
RST_OPS = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
ED_REP = {0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}
COND = bytearray(256)
for _o in (0x10, 0x20, 0x28, 0x30, 0x38) + tuple(range(0xC0, 0x100, 8)) + tuple(range(0xC2, 0x100, 8)) \
        + tuple(range(0xC4, 0x100, 8)):
    COND[_o] = 1

# ---------------------------------------------------------------- the model (Zilog T)
W = dict(
    # ---- $8669
    # CALL $89CB 17 / LD IX,nn 14 / BIT 4,(IX+d) 20
    I_PRE=51,
    # $8674 JR nz taken 12 (P1 +$5A bit 4: carried)
    I_P1C=12,
    # $8674 JR nz 7 / BIT 4,(IX+d) 20
    I_P1N=27,
    # $867A JR nz taken 12 (+$64 bit 4)
    I_P2C=12,
    # $867A JR nz 7 / LD A,(nn) 13 / CP n 7 / LD (nn),A 13
    I_GATE=40,
    # $8684 RET z taken 11 (no edge)
    I_SAME=11,
    # $8684 RET z 5 / LD HL,nn 10 / INC (HL) 11
    I_TICK=26,
    # $8689 XOR A 4 / LD (nn),A 13 / LD IY,nn 14 / LD HL,nn 10 / LD B,n 7
    I_WALK0=48,
    # $8696 LD A,(HL) 7 / OR A 4 / CALL nz 10 (not taken) / INC HL 6 / INC HL 6
    I_EMPTY=33,
    # ... CALL nz taken 17
    I_LIVE=40,
    # $869D DJNZ 13 / the last 8
    I_DJNZ=13, I_DJNZ_END=8,
    # $869F LD HL,nn 10 / INC (HL) 11 / LD HL,nn 10 / LD A,(HL) 7 / AND A 4
    I_POST=42,
    # $86A8 RET z taken 11 (the slot empty)
    I_NOSLOT=11,
    # $86A8 RET z 5 / $86A9 PUSH HL 11 / PUSH BC 11 / CALL $86B1 17 / POP BC 10 / POP HL 10 / RET 10
    I_SLOT=74,
    # ---- $86A9 (CALLed): PUSH HL 11 / PUSH BC 11 / CALL $86B1 17 / POP BC 10 / POP HL 10 / RET 10
    E_WRAP=69,
    # ---- $89CB
    # LD HL,nn 10 / LD A,(nn) 13 / CP n 7
    S_PRE=30,
    # $89D3 JR nc 7 / LD A,(nn) 13 / CP n 7
    S_LOW=27,
    # $89D3 JR nc taken 12 (round >= $50)
    S_HIGH=12,
    # $89DA JR z taken 12 (timer hi = 4)
    S_T4=12,
    # $89DA JR z 7 / CP n 7
    S_NOT4=14,
    # $89DE RET nz taken 11 / $89E1 RET nz taken 11 / $8A0F RET nz taken 11
    S_RET=11,
    # $89DE RET nz 5 / BIT 1,(HL) 12
    S_T2=17,
    # $89E1 RET nz 5 / SET 1,(HL) 15 / LD H,n 7 / LD A,(nn) 13 / LD L,A 4 / CP H 4 / LD A,n 7
    S_PTS=55,
    # $89ED JR nc taken 12 ; JR nc 7 / LD A,H 4 / SUB L 4 / CP H 4
    S_PTS_HI=12, S_PTS_SUB=19,
    # $89F2 JR nz taken 12 ; JR nz 7 / DEC A 4
    S_PTS_NZ=12, S_PTS_Z=11,
    # $89F5 LD DE,nn 10 / LD HL,nn 10
    S_PTS_DST=20,
    # $89FB LDI 16 / EX DE,HL 4 / DEC HL 6 / AND n 7 / LD C,A 4 / LD A,(HL) 7 / AND n 7 / OR C 4 /
    # LD (HL),A 7 / INC HL 6 / RET 10
    S_TAIL=78,
    # $8A09 JR nz taken 12 ; JR nz 7 / LD (HL),0 10
    S_NOT50=12, S_IS50=17,
    # $8A0D BIT 0,(HL) 12
    S_PU=12,
    # $8A0F RET nz 5 / SET 0,(HL) 15 / LD A,(nn) 13 / LD C,A 4 / SUB n 7 / LD B,A 4 / LD A,n 7
    S_PU_GO=55,
    # $8A1B JR z taken 12 (round $50) ; JR z 7 / DEC A 4 / DEC B 4
    S_R50=12, S_NOT_R50=15,
    # $8A1F JR z taken 12 (round $51) ; JR z 7 / LD A,C 4 / LD HL,nn 10 / LD BC,nn 10
    S_R51=12, S_LIST=31,
    # a CPIR's repeat 21, its last 16
    S_CPIR=21, S_CPIR_END=16,
    # INC C 4 / DEC C 4
    S_INCDEC=8,
    # $8A2C JR z taken 12 (not listed) ; JR z 7 / LD A,R 9 / AND n 7 / SUB n 7 / ADC A,n 7 / JR 12
    S_WIDE=12, S_NARROW=49,
    # $8A38 LD A,R 9 / AND n 7 / LD C,n 7
    S_WIDE_GO=23,
    # $8A42 JR z taken 12 (not excluded) ; JR z 7 / XOR A 4
    S_KEEP=12, S_EXCL=11,
    # $8A45 CP n 7 ; $8A47 JR nz taken 12 ; JR nz 7 / LD (nn),A 13
    S_CP=7, S_NOT6=12, S_IS6=20,
    # $8A4E JR nz taken 12 ; JR nz 7 / LD A,(nn) 13 / CP n 7 / LD A,n 7
    S_NOT7=12, S_IS7=34,
    # $8A57 JR nz taken 12 ; JR nz 7 / ADD A,A 4
    S_7KEEP=12, S_7DBL=11,
    # $8A5A LD DE,nn 10 / LD HL,nn 10 / JR 12
    S_PU_DST=32,
    # ---- $86B1
    # CALL $8779 17 / PUSH HL 11 / LD IX,nn 14 / CALL $87B2 17 / POP HL 10 / LD A,(HL) 7 / OR A 4
    B_PRE=80,
    # $86BF / $86CB RET z taken 11 (taken by a player)
    B_TAKEN=11,
    # $86BF RET z 5 / PUSH HL 11 / LD IX,nn 14 / CALL $87B2 17 / POP HL 10 / LD A,(HL) 7 / OR A 4
    B_P1=68,
    # $86CB RET z 5 / LD A,n 7 / AND n 7 / INC HL 6
    B_CLOCK=25,
    # $86D1 JR nz taken 12 (no tick) / $86D7 JR nz taken 12 (the heart)
    B_SKIP=12,
    # $86D1 JR nz 7 / LD A,(nn) 13 / OR A 4
    B_TICK=24,
    # $86D7 JR nz 7 / LD A,(HL) 7 / AND n 7 / INC A 4 / AND n 7 / CP n 7
    B_PHASE=39,
    # $86E1 JR nz taken 12 / $8713 LD C,A 4 / LD A,(HL) 7 / AND n 7 / OR C 4 / LD (HL),A 7
    B_AGE=41,
    # $86E1 JR nz 7 / DEC HL 6 / LD (HL),0 10
    B_EXPIRE=23,
    # $8719 DEC HL 6 / LD A,($FECE) 13 / OR A 4
    B_WX=23,
    # $871E / $8725 JP nz taken 10 (the flood / the storm: to $A2C2's body)
    B_WX_SKIP=10,
    # $871E JP nz 10 / LD A,($FECF) 13 / OR A 4
    B_WX_FLOOD_NO=27,
    # $8725 JP nz 10 / LD A,(HL) 7 / AND n 7 / LD H,n 7 / DEC H 4
    B_INK=35,
    # $872E JR z taken 12 (the pass flag 1) ; JR z 7 / ADD A,n 7
    B_BANK1=12, B_BANK0=14,
    # $8732 LD L,A 4 / LD H,n 7 / LD DE,nn 10 / ADD HL,DE 11 / LD A,(HL) 7 / OR A 4
    B_LOOK=43,
    # $873B JP p taken 10 ; JP p 10 / LD A,R 9 / AND n 7
    B_FIXED=10, B_RNG=26,
    # $8742 LD (nn),A 13 / LD DE,(nn) 20 / CALL $AEDC 17 / LD A,H 4 / SUB n 7 / LD H,A 4 / CALL 17 /
    # INC L 4 / CALL 17 / LD BC,nn 10 / ADD HL,BC 11 / CALL 17 / INC L 4 / CALL 17 / JP $A2C2 10
    B_INKCELLS=172,
    # ---- the ERASE body ($86E6, in $86B1's frame or its own)
    # $86E6 LD A,($FECE) 13 / OR A 4
    X_PRE=17,
    # $86EA JP nz taken 10 (the flood: to $A314 at once)
    X_FLOOD=10,
    # $86EA JP nz 10 / LD DE,(nn) 20 / CALL $AEDC 17 / LD A,H 4 / SUB n 7 / LD D,A 4 / LD E,L 4 /
    # CALL 17 / INC L 4 / INC E 4 / CALL 17 / LD BC,nn 10 / ADD HL,BC 11 / EX DE,HL 4 / ADD HL,BC 11 /
    # EX DE,HL 4 / CALL 17 / INC L 4 / INC E 4 / CALL 17 / JP $A314 10
    X_CELLS=200,
    # ---- $A314's body (in the frame that JPed to it)
    # LD A,(IY+5) 19 / CALL $9F5C 17 / LD (nn),A 13 / LD A,(IY+6) 19 / LD C,A 4 / AND n 7 / LD (nn),A 13 /
    # LD B,A 4 / LD A,n 7 / SUB B 4 / LD (nn),A 13 / LD A,C 4 / CALL $9F5C 17 / ADD A,A 4 / LD E,A 4 /
    # LD D,n 7 / LD IX,nn 14 / ADD IX,DE 15 / LD A,B 4 / LD B,n 7 / CALL $A34D 17 / XOR A 4 / LD B,n 7 /
    # CALL $A34D 17 / XOR A 4 / LD B,n 7 / INC B 4 / DEC B 4
    R_PRE=260,
    # $A34C RET z taken 11 (Y & 7 = 0: no third band)
    R_END=11,
    # $A34C RET z 5 -- then the third band inline ($A34D's body, its RET the frame's)
    R_BAND3=5,
    # ---- $A34D's body: ADD A,(IX+d) 19 / LD D,A 4 / ADD A,n 7 / LD H,A 4 / LD A,n 7 / ADD A,(IX+d) 19 /
    # INC IX 10 / INC IX 10 / LD E,A 4 / LD L,A 4
    D_PRE=88,
    # a row: LD A,(HL) 7 / LD (DE),A 7 / INC E 4 / INC L 4 / LD A,(HL) 7 / LD (DE),A 7 / DEC E 4 /
    # DEC L 4 / INC H 4 / INC D 4  (+ DJNZ 13, the last 8)
    D_ROW=52,
    # RET 10
    RET=10,
    # ---- $A2C2's body: XOR A 4 / LD (nn),A 13 / LD (nn),A 13 / CALL $A2D5 17 / LD A,n 7 / LD (nn),A 13 /
    # LD (nn),A 13 / RET 10
    G_BODY=90,
    # ---- $A2D5: LD A,(IY+6) 19 / CALL $9F5C 17 / ADD A,A 4 / LD D,n 7 / LD E,A 4 / LD IX,nn 14 /
    # ADD IX,DE 15 / LD E,(IY+0) 19 / LD D,(IY+1) 19 / LD A,(IY+5) 19 / CALL $9F5C 17 / LD (nn),A 13 /
    # CALL $A2FB 17 / INC IX 10 / INC IX 10
    K_PRE=204,
    # ---- a blit band ($A2FB): LD B,n 7 / LD H,(IX+1) 19 / LD A,(IX+0) 19 / ADD A,n 7 / LD L,A 4
    K_BAND=56,
    # a row: LD A,(DE) 7 / $A307 NOP 4 / LD (HL),A 7 / INC L 4 / INC DE 6 / LD A,(DE) 7 / $A30C NOP 4 /
    # LD (HL),A 7 / INC DE 6 / DEC L 4 / INC H 4  (+ DJNZ 13, the last 8); OR (HL) 7 for each NOP
    K_ROW_NOP=60, K_ROW_OR=66,
    # ---- $8779
    # PUSH HL 11 / LD A,(HL) 7 / LD C,A 4 / AND n 7 / LD (nn),A 13 / LD A,(nn) 13 / OR A 4
    U_PRE=59,
    # $8785 JR nz taken 12 / LD A,C 4 / AND n 7 / LD E,A 4 / LD D,n 7 / LD HL,nn 10 / ADD HL,DE 11 /
    # LD A,(HL) 7 / JR 12 (the power-up remap)
    U_REMAP=74,
    # $8785 JR nz 7 / LD A,C 4 / AND n 7 / ADD A,n 7
    U_FRUIT=25,
    # $878C ADD A,A 4 x3 / LD L,A 4 / LD H,n 7 / ADD HL,HL 11 x2 / LD DE,nn 10 / ADD HL,DE 11 /
    # LD (nn),HL 16 / POP HL 10 / INC HL 6 / LD A,(HL) 7 / AND n 7 / LD (nn),A 13 / DEC HL 6 / RET 10
    U_POST=141,
    # ---- $87B2
    # $87B2 RET 10 (collection off)
    C_OFF=10,
    # $87B2 NOP 4 / LD A,(IX+7) 19 / RLA 4
    C_PRE=27,
    # RET nc / RET nz taken 11 (out)
    C_OUT=11,
    # $87B7 RET nc 5 / LD A,(IX+5) 19 / LD E,A 4 / ADD A,n 7 / LD C,A 4 / LD A,(IX+6) 19 / LD D,A 4 /
    # ADD A,n 7 / LD B,A 4 / LD A,(HL) 7 / EX AF,AF' 4 / LD A,(HL) 7 / AND n 7 / LD (HL),A 7 / CALL 17 /
    # EX AF,AF' 4 / LD (HL),A 7 / EX AF,AF' 4
    C_X=137,
    # $87D2 RET nc 5 / INC HL 6 / LD A,(HL) 7 / EX AF,AF' 4 / LD A,(HL) 7 / AND n 7 / LD (HL),A 7 /
    # CALL 17 / EX AF,AF' 4 / LD (HL),A 7 / EX AF,AF' 4 / DEC HL 6
    C_Y=81,
    # $87E1 RET nc 5 / BIT 6,(IX+d) 20
    C_LOCK=25,
    # $87E6 RET nz 5 / INC (IX+d) 23 / LD A,(HL) 7 / AND n 7 / LD (nn),A 13 / LD (HL),n 10 / PUSH IX 15 /
    # CALL $86E6 17 / POP IX 14 / DI 4 / LD A,(nn) 13 / ADD A,A 4 / LD L,A 4 / LD H,n 7 / LD DE,nn 10 /
    # ADD HL,DE 11 / LD A,(HL) 7 / INC HL 6 / LD H,(HL) 7 / LD L,A 4 / LD (nn),HL 16 / LD A,n 7 /
    # BIT 0,(IX+d) 20
    C_TAKE=231,
    # $8812 JR z taken 12 (P1) ; JR z 7 / INC A 4 (P2)
    C_IDX1=12, C_IDX2=11,
    # PUSH IX 15 / CALL $80FA 17 / POP IX 14 / EI 4 / LD C,n 7 / CALL $8CB1 17 / LD A,(nn) 13 / OR A 4
    C_PAY=91,
    # $8826 RET z taken 11 (a fruit pass)
    C_FRUIT=11,
    # $8826 RET z 5 / LD A,n 7 / LD (IX+d),A 19 / ADD A,A 4 / LD L,A 4 / LD H,n 7 / LD DE,nn 10 /
    # ADD HL,DE 11 / LD E,(HL) 7 / INC HL 6 / LD D,(HL) 7 / EX DE,HL 4 / JP (HL) 4 (the effect: 'pu')
    C_PU=95,
    # ---- $930A / $9312: LD A,(HL) 7 / CP r 4 / RET nc taken 11 ; RET nc 5 / ADD A,n 7 / CP r 4 / CCF 4 /
    # RET 10
    O_NC=22, O_GO=41,
    # ---- $876C: LD A,(HL) 7 / AND n 7 / LD A,(nn) 13 / JR z taken 12 / LD (DE),A 7 / RET 10 ;
    # JR z 7 / LD A,(nn) 13
    L_OPEN=56, L_SOLID=64,
    # ---- $8765: LD A,(HL) 7 / AND n 7 / OR n 7 / LD (HL),A 7 / RET 10
    N_CELL=38,
    # ---- $AEDC: LD A,D 4 / AND n 7 / LD L,A 4 / LD H,n 7 / LD B,H 4 / ADD HL,HL 11 x2 / LD A,E 4 /
    # RRA 4 x3 / AND n 7 / LD C,A 4 / ADD HL,BC 11 / LD BC,nn 10 / ADD HL,BC 11 / LD A,(HL) 7 /
    # AND n 7 / RET 10
    Q_CELL=131,
    # ---- $9F5C: RRA 4 x3 / AND n 7 / RET 10
    F_RRA=29,
)


class Walk:
    """a path-walker over one frame's sig: nx(pc) -> taken?, asserting the order"""

    def __init__(self, sig):
        self.s, self.i = sig, 0

    def nx(self, q):
        assert self.i < len(self.s), 'sig short at %04X' % q
        p, c = self.s[self.i]
        assert p == q, 'sig %04X where %04X' % (p, q)
        self.i += 1
        return c == 't'

    def rep(self, q):
        """a repeat instruction's turns: the count of 't' then the closing 'f'"""
        n = 0
        while self.nx(q):
            n += 1
        return n

    def end(self, t):
        assert self.i == len(self.s), 'sig long'
        return t


def M8669(s, m):
    w, t = Walk(s), W['I_PRE']
    if w.nx(0x8674):
        t += W['I_P1C']
    else:
        t += W['I_P1N']
        if w.nx(0x867A):
            t += W['I_P2C']
        else:
            t += W['I_GATE']
            if w.nx(0x8684):
                return w.end(t + W['I_SAME'])
            t += W['I_TICK']
    t += W['I_WALK0']
    for k in range(31):
        t += W['I_LIVE'] if w.nx(0x8698) else W['I_EMPTY']
        t += W['I_DJNZ'] if w.nx(0x869D) else W['I_DJNZ_END']
    t += W['I_POST']
    if w.nx(0x86A8):
        return w.end(t + W['I_NOSLOT'])
    return w.end(t + W['I_SLOT'])


def M86A9(s, m):
    return Walk(s).end(W['E_WRAP'])


def _s_tail(w, t):
    return t + W['S_TAIL']


def M89CB(s, m):
    w, t = Walk(s), W['S_PRE']
    pu = False
    if w.nx(0x89D3):
        t += W['S_HIGH']
        if w.nx(0x8A09):
            t += W['S_NOT50']
        else:
            t += W['S_IS50']
        pu = True
    else:
        t += W['S_LOW']
        if w.nx(0x89DA):
            t += W['S_T4']; pu = True
        else:
            t += W['S_NOT4']
            if w.nx(0x89DE):
                return w.end(t + W['S_RET'])
            t += W['S_T2']
            if w.nx(0x89E1):
                return w.end(t + W['S_RET'])
            t += W['S_PTS']
            if w.nx(0x89ED):
                t += W['S_PTS_HI']
            else:
                t += W['S_PTS_SUB']
                t += W['S_PTS_NZ'] if w.nx(0x89F2) else W['S_PTS_Z']
            return w.end(t + W['S_PTS_DST'] + W['S_TAIL'])
    # $8A0D
    t += W['S_PU']
    if w.nx(0x8A0F):
        return w.end(t + W['S_RET'])
    t += W['S_PU_GO']
    if w.nx(0x8A1B):
        t += W['S_R50']
    else:
        t += W['S_NOT_R50']
        if w.nx(0x8A1F):
            t += W['S_R51']
        else:
            t += W['S_LIST']
            n = w.rep(0x8A28)
            t += W['S_CPIR'] * n + W['S_CPIR_END'] + W['S_INCDEC']
            if w.nx(0x8A2C):
                t += W['S_WIDE'] + W['S_WIDE_GO']
                n = w.rep(0x8A3E)
                t += W['S_CPIR'] * n + W['S_CPIR_END'] + W['S_INCDEC']
                t += W['S_KEEP'] if w.nx(0x8A42) else W['S_EXCL']
            else:
                t += W['S_NARROW']
    # $8A45
    t += W['S_CP']
    t += W['S_NOT6'] if w.nx(0x8A47) else W['S_IS6']
    t += W['S_CP']
    if w.nx(0x8A4E):
        t += W['S_NOT7']
    else:
        t += W['S_IS7']
        t += W['S_7KEEP'] if w.nx(0x8A57) else W['S_7DBL']
    return w.end(t + W['S_PU_DST'] + W['S_TAIL'])


def _band3(w, t):
    """$A34D's body inline (the restore's third band) to its RET"""
    t += W['D_PRE']
    while w.nx(0xA369):
        t += W['D_ROW'] + 13
    return t + W['D_ROW'] + 8 + W['RET']


def _restore(w, t):
    """$A314's body to the frame's RET"""
    t += W['R_PRE']
    if w.nx(0xA34C):
        return t + W['R_END']
    return _band3(w, t + W['R_BAND3'])


def _erase(w, t):
    """$86E6's body: the cells unless the flood, then $A314's body"""
    t += W['X_PRE']
    if w.nx(0x86EA):
        t += W['X_FLOOD']
    else:
        t += W['X_CELLS']
    return _restore(w, t)


def M86B1(s, m):
    w, t = Walk(s), W['B_PRE']
    if w.nx(0x86BF):
        return w.end(t + W['B_TAKEN'])
    t += W['B_P1']
    if w.nx(0x86CB):
        return w.end(t + W['B_TAKEN'])
    t += W['B_CLOCK']
    if w.nx(0x86D1):
        t += W['B_SKIP']
    else:
        t += W['B_TICK']
        if w.nx(0x86D7):
            t += W['B_SKIP']
        else:
            t += W['B_PHASE']
            if w.nx(0x86E1):
                t += W['B_AGE']
            else:
                return w.end(_erase(w, t + W['B_EXPIRE']))
    # $8719
    t += W['B_WX']
    if w.nx(0x871E):
        return w.end(t + W['B_WX_SKIP'] + W['G_BODY'])
    t += W['B_WX_FLOOD_NO']
    if w.nx(0x8725):
        return w.end(t + W['B_WX_SKIP'] + W['G_BODY'])
    t += W['B_INK']
    t += W['B_BANK1'] if w.nx(0x872E) else W['B_BANK0']
    t += W['B_LOOK']
    t += W['B_FIXED'] if w.nx(0x873B) else W['B_RNG']
    return w.end(t + W['B_INKCELLS'] + W['G_BODY'])


def M86E6(s, m):
    w = Walk(s)
    return w.end(_erase(w, 0))


def MA34D(s, m):
    w = Walk(s)
    return w.end(_band3(w, 0))


def _kband(w, m):
    row = W['K_ROW_NOP'] if m == 'N' else W['K_ROW_OR']
    t = W['K_BAND']
    while w.nx(0xA311):
        t += row + 13
    return t + row + 8 + W['RET']


def MA2D5(s, m):
    w = Walk(s)
    return w.end(W['K_PRE'] + _kband(w, m))


def MA2FB(s, m):
    w = Walk(s)
    return w.end(_kband(w, m))


def M8779(s, m):
    w = Walk(s)
    return w.end(W['U_PRE'] + (W['U_REMAP'] if w.nx(0x8785) else W['U_FRUIT']) + W['U_POST'])


def M87B2(s, m):
    w = Walk(s)
    if m == 'R':
        return w.end(W['C_OFF'])
    assert m == 'N', m
    t = W['C_PRE']
    if w.nx(0x87B7):
        return w.end(t + W['C_OUT'])
    t += W['C_X']
    if w.nx(0x87D2):
        return w.end(t + W['C_OUT'])
    t += W['C_Y']
    if w.nx(0x87E1):
        return w.end(t + W['C_OUT'])
    t += W['C_LOCK']
    if w.nx(0x87E6):
        return w.end(t + W['C_OUT'])
    t += W['C_TAKE']
    t += W['C_IDX1'] if w.nx(0x8812) else W['C_IDX2']
    t += W['C_PAY']
    if w.nx(0x8826):
        return w.end(t + W['C_FRUIT'])
    return w.end(t + W['C_PU'])


def _box(q):
    def f(s, m):
        w = Walk(s)
        return w.end(W['O_NC'] if w.nx(q) else W['O_GO'])
    return f


def M876C(s, m):
    w = Walk(s)
    return w.end(W['L_OPEN'] if w.nx(0x8772) else W['L_SOLID'])


def _const(k):
    def f(s, m):
        return Walk(s).end(W[k])
    return f


MODEL = {0x8669: M8669, 0x89CB: M89CB, 0x86A9: M86A9, 0x86B1: M86B1, 0x86E6: M86E6, 0x8779: M8779,
         0x87B2: M87B2, 0x930A: _box(0x930C), 0x9312: _box(0x9314), 0x876C: M876C,
         0x8765: _const('N_CELL'), 0xAEDC: _const('Q_CELL'), 0x9F5C: _const('F_RRA'),
         0xA2D5: MA2D5, 0xA2FB: MA2FB, 0xA34D: MA34D}


def model(entry, sig, mode):
    try:
        return MODEL[entry](sig, mode)
    except (AssertionError, KeyError) as e:
        return 'ERR %s' % e


# ---------------------------------------------------------------- forced calls (declared)
P1, P2 = 0xFD80, 0xFD8A


def _clear_items():
    return [(0x9603, 0)] + [(0x9605 + 2 * i, 0) for i in range(31)]


def _pl(base, x=None, y=None, live=True, lock=False, idx2=False, carried=False):
    out = [(base + 7, 0x80 if live else 0)]
    if x is not None:
        out += [(base + 5, x), (base + 6, y)]
    out += [(base + 0x5A, (0x40 if lock else 0) | (0x01 if idx2 else 0) | (0x10 if carried else 0))]
    return out


def _item(at, x, y, typ, phase):
    return [(at, (x & 0xF0) | typ), (at + 1, (y & 0xF8) | phase)]


_Q = _clear_items() + _pl(P2, live=False) + [(0xFDDA, 0x00), (0xFDE4, 0x01)]   # quiet: no items, P2 out
_ON = _pl(P1, 0x60, 0x60)                                                     # P1 over (60, 60)
_TICK = [(0x8680, 0xE7), (0x86CD, 0xFF)]       # the gate passes ($8DB6 = $E8) and $86CD wraps: a tick
_NOTICK = [(0x8680, 0xE7), (0x86CD, 0x10)]

# (name, state, pokes[, R at the entry]) -- each for branches the 48 x 300 natural survey never takes;
# round1_48 holds $8609 = 1, $8DB7 = 0 ($89CB's RET nz at $89DE), P1 at ($18, $A8), P2 not live
CALLS = [
    # $8674 / $867A JR nz: a carried player (P1's +$5A, P2's = P1's +$64) bypasses the gate
    ('p1_carried', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + [(0xFDDA, 0x10)]),
    ('p2_carried', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + [(0xFDE4, 0x11)]),
    # P2 live over a fruit: $86BF RET z (taken by P2), $8812 JR z falls (P2's +$5A bit 0: index 2)
    ('p2_take', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _pl(P2, 0x60, 0x60, idx2=True)),
    # P1 over a fruit with the collect lock (+$5A bit 6): $87E6 RET nz
    ('p1_lock', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _pl(P1, 0x60, 0x60, lock=True)),
    # collection OFF ($87B2 = RET, $94DB's patch)
    ('coll_off', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _ON + [(0x87B2, 0xC9)]),
    # a phase-3 fruit ticking under the flood: the expiry's erase JP nz,$A314 at $86EA
    ('flood_expire', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 3) + _TICK + [(0xFECE, 1)]),
    # the weather skips: the flood ($871E) and the storm ($8725) straight to $A2C2
    ('flood_skip', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _NOTICK + [(0xFECE, 1)]),
    ('storm_skip', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _NOTICK + [(0xFECF, 1)]),
    # the power-up slot, type 10: the ink table's $FF at $861D+10 -> $873E LD A,R ($873B JP p falls)
    ('rng_ink', 'round1_48', _Q + _item(0x9603, 0x60, 0x60, 10, 0) + _NOTICK),
    # P1 collects under the flood: the collect's $86E6 JP nz,$A314
    ('collect_flood', 'round1_48', _Q + _item(0x9605, 0x60, 0x60, 1, 0) + _ON + [(0xFECE, 1)]),
    # $89CB: the points item with $9AE9 >= 12 ($89ED JR nc) and = 0 ($89F2 falls: DEC A)
    ('pts_hi', 'round1_48', _Q + [(0x8DB7, 2), (0x8CB0, 0), (0x9AE9, 12)]),
    ('pts_zero', 'round1_48', _Q + [(0x8DB7, 2), (0x8CB0, 0), (0x9AE9, 0)]),
    # the power-up on a LISTED round ($8609 = 3, $8A62's first byte): the narrow draw ($8A2C falls)
    ('pu_narrow', 'round1_48', _Q + [(0x8DB7, 4), (0x8CB0, 0), (0x8609, 3)]),
    # the wide draw, R at the entry chosen (a sweep of R 0..127, declared) to draw: an EXCLUDED
    # value ($8A42 falls: XOR A), 6 ($8A47 falls: the umbrella lock), 7 ($8A4E falls) with $7E0E
    # not 2 ($8A57 JR nz taken) and = 2 ($8A57 falls: ADD A,A -> 14)
    ('pu_excl', 'round1_48', _Q + [(0x8DB7, 4), (0x8CB0, 0)], 111),
    ('pu_six', 'round1_48', _Q + [(0x8DB7, 4), (0x8CB0, 0)], 104),
    ('pu_seven', 'round1_48', _Q + [(0x8DB7, 4), (0x8CB0, 0), (0x7E0E, 0)], 105),
    ('pu_seven2', 'round1_48', _Q + [(0x8DB7, 4), (0x8CB0, 0), (0x7E0E, 2)], 105),
]
CALLS_BY = {c[0]: c for c in CALLS}


class RecMem(B.RecMem):
    """ab38cost's recorder, but the operands read as STATE enter the seed (popcost's)"""
    __slots__ = ()

    def __getitem__(self, i):
        if self.rec is not None and type(i) is int and i not in self.seen:
            s = STATE_OPS.get(self.regs[PC])
            if s and i in s:
                self.seen.add(i); self.rec.append((i, self.m[i]))
        return B.RecMem.__getitem__(self, i)


def _machine(state, contended=False):
    h = Harness(contended=contended)
    h.load_state_file(pc.state_path(state))
    rm = RecMem(h.memobj)
    h.memobj = rm; h.sim.memory = rm; h.sim.create_opcodes(); h.sim.set_tracer(h.ports)
    rm.regs = h.sim.registers
    return h, rm


# a frame: [entry, sp0, t0, x0, kidT, sig, kids, mode, ret, label]
class Tracker:
    def __init__(self):
        self.cur = None; self.stack = []; self.excl = 0; self.isr = None; self.done = []

    def open(self, r, rm, ret):
        sp0 = (r[SP] + 2) & 0xFFFF
        self.cur = {'seed': [], 'irq': 0, 'halt': 0, 'calls': [], 'opaque': [], 'par': rm.m[0x8DBD] & 1}
        rm.seen = set(); rm.rec = self.cur['seed']; rm.wr = self.cur['post'] = {}; rm.stk = sp0 - 2
        self.stack = [[ENTRY, sp0, r[T], self.excl, 0, [], [], '-', ret, None]]

    def opaque_open(self):
        return any(f[9] for f in self.stack)

    def close_frames(self, r, rm):
        sp, t = r[SP], r[T]
        while self.stack and sp >= self.stack[-1][1] and sp - self.stack[-1][1] < 0x100:
            f = self.stack.pop()
            T_ = (t - f[2]) - (self.excl - f[3])
            own = T_ - f[4]
            if self.stack:
                par = self.stack[-1]
                par[4] += T_
                par[6].append((f[0], T_))
                if f[9]:
                    self.cur['opaque'].append((f[9], f[0], T_))
                else:
                    self.cur['calls'].append((f[0], f[7], own, tuple(f[5])))
            else:
                assert r[PC] == f[8], '$8669 returned to $%04X' % r[PC]
                x = self.cur
                x['T'] = T_; x['own'] = own; x['sig'] = tuple(f[5]); x['kids'] = f[6]
                rm.rec = None
                self.done.append(x)
                self.cur = None

    def step(self, r, op, raw, rm, h):
        p, sp = r[PC], r[SP]
        assert not (A.GLO <= p < A.GHI), 'ENTERED THE GUARDED RANGE'
        if self.isr is not None and p == self.isr[0] and sp == self.isr[1]:
            self.excl += r[T] - self.isr[2]
            self.isr = None
            if self.cur is not None:
                rm.rec = self.cur['seed']
        if self.isr is None and self.cur is not None:
            self.close_frames(r, rm)
        o = raw[p]
        live = self.cur is not None and self.isr is None
        if live and p in SMC_OPCODES and p not in rm.seen:
            rm.seen.add(p); rm.rec.append((p, o))           # an OPCODE read as state (TRAPS #278)
        if o == 0x76:
            assert self.cur is None or self.isr is not None or self.opaque_open(), 'HALT in a modelled frame'
            if live:
                self.cur['halt'] += 1
            h._fast_halt()
            return
        top = self.stack[-1] if live else None
        if top is not None and top[9] is None:
            if p == 0x87B2:
                top[7] = 'R' if o == 0xC9 else ('N' if o == 0x00 else '?%02x' % o)
            elif p in (0xA307, 0xA30C):
                m = 'N' if o == 0x00 else ('O' if o == 0xB6 else '?%02x' % o)
                assert top[7] in ('-', m), 'the two blit opcodes differ'
                top[7] = m
        op[o]()
        if top is not None and top[9] is None:
            np_, nsp = r[PC], r[SP]
            if COND[o]:
                top[5].append((p, 'f' if np_ == B._fall(raw, p) else 't'))
            elif o == 0xED and raw[(p + 1) & 0xFFFF] in ED_REP:
                top[5].append((p, 't' if np_ == p else 'f'))
            if nsp == (sp - 2) & 0xFFFF and ((o in CALL_OPS and np_ != (p + 3) & 0xFFFF) or o in RST_OPS):
                ret = (p + (1 if o in RST_OPS else 3)) & 0xFFFF
                if raw[nsp] | raw[(nsp + 1) & 0xFFFF] << 8 == ret:
                    self.stack.append([np_, sp, r[T], self.excl, 0, [], [], '-', ret, OPAQUE.get(np_)])
            elif p == PU_JP and top[0] == 0x87B2:
                # the power-up effect: from the JP (HL) to $87B2's RET, a pseudo-frame on $87B2's SP
                self.stack.append([np_, top[1], r[T], self.excl, 0, [], [], '-', top[8], 'pu'])
        if r[IFF] and r[T] % h.frame_duration < h.int_active:
            b, spb, tt = r[PC], r[SP], r[T]
            if h.sim.accept_interrupt(r, rm, p):
                assert self.isr is None, 'an interrupt inside the ISR'
                self.isr = (b, spb, tt)
                if self.cur is not None:
                    self.cur['irq'] += 1
                    rm.rec = None


def run(name, frames=FRAMES, contended=False, keys=True):
    h, rm = _machine(name, contended)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    assert raw[0x8DC4] == 0xC9, name + ': not a 48K state'
    fd = h.frame_duration
    t_end = r[T] + frames * fd
    ki, nextk = 0, r[T]
    tr = Tracker()
    while r[T] < t_end or tr.cur is not None:
        if r[T] >= nextk:
            h.ports.release_all()
            for kt in (0xB5FD, 0xB605):
                for j, c in enumerate('LRJB'):
                    sel, mask = raw[kt + 2 * j], raw[kt + 2 * j + 1]
                    if keys and c in B.ACTIONS[ki % len(B.ACTIONS)] and mask:
                        if sel == 0x1F:
                            h.ports.kempston |= mask
                        else:
                            h.ports.press(sel, 0xFF & ~mask)
            ki += 1; nextk = r[T] + B.KEY_FRAMES * fd
        p = r[PC]
        if tr.cur is None and tr.isr is None and p == ENTRY:
            sp = r[SP]
            assert raw[sp] | raw[(sp + 1) & 0xFFFF] << 8 == BACK, '$8669 entered not from $8D4C'
            tr.open(r, rm, BACK)
        tr.step(r, op, raw, rm, h)
    return tr.done


def call_run(name, state, pokes, r0=None):
    h, rm = _machine(state)
    r, op, raw = h.sim.registers, h.sim.opcodes, rm.m
    for ad, v in pokes:
        raw[ad] = v
    if r0 is not None:
        r[REG_R] = r0                                   # the refresh register at the entry (declared)
    r[IFF] = 0
    sp = (r[SP] - 2) & 0xFFFF
    raw[sp], raw[sp + 1] = BACK & 0xFF, BACK >> 8
    r[SP] = sp; r[PC] = ENTRY
    tr = Tracker()
    tr.open(r, rm, BACK)
    for _ in range(4000000):
        tr.step(r, op, raw, rm, h)
        if tr.isr is None and tr.cur is not None:
            tr.close_frames(r, rm)
        if tr.cur is None:
            break
    else:
        raise AssertionError(name + ': no return')
    return tr.done[0]


def _ss(sig):
    return ' '.join('%04x%s' % (q, c) for q, c in sig)


def check(x):
    """the model against one run: [own, model] of every frame that disagrees, with its entry"""
    bad = []
    for e, m, own, sig in [(ENTRY, '-', x['own'], x['sig'])] + x['calls']:
        v = model(e, sig, m)
        if v != own:
            bad.append(['%04X' % e, m, own, v, _ss(sig)])
    return bad


def row(name, x):
    rom = sorted(a for a, _ in x['seed'] if a < 0x4000)
    seed = sorted((a, v) for a, v in x['seed'] if a >= 0x4000)
    post = sorted(x['post'].items())
    blind = [a for a, _ in post if a < 0x5800] if rom else []
    if rom:
        post = [(a, v) for a, v in post if a >= 0x5800]
    out = {'state': name, 'T': x['T'], 'own': x['own'], 'sig': _ss(x['sig']), 'irq': x['irq'], 'halt': x['halt'],
           'kids': [['%04X' % k, t] for k, t in x['kids']],
           'calls': [['%04X' % e, m, own, _ss(s)] for e, m, own, s in x['calls']],
           'opaque': [[l, '%04X' % e, t] for l, e, t in x['opaque']]}
    if not x['irq']:
        out.update({'seed': ''.join('%04x%02x' % (a, v) for a, v in seed),
                    'post': ''.join('%04x%02x' % (a, v) for a, v in post),
                    'rom': len(rom), 'blind': ' '.join('%04x' % a for a in blind)})
    return out


def _slim(x):
    """what the parent needs of a run (the seed/post only as the kept row)"""
    return {'T': x['T'], 'own': x['own'], 'sig': x['sig'], 'irq': x['irq'], 'halt': x['halt'],
            'calls': x['calls'], 'opaque': x['opaque'], 'kids': x['kids']}


def one(job):
    name, tag = job
    runs = [call_run(*CALLS_BY[tag])] if tag else run(name)
    out = []
    seen = collections.Counter()
    for x in runs:
        bad = check(x)
        key = _key(x)
        r = None
        if (tag or (seen[key] < KEEP and not x['irq'])):
            seen[key] += 1
            r = row(tag or name, x)
        out.append((bad, _slim(x), key, r))
    return out


def _key(x):
    return _ss(x['sig']) + ' %d|' % x['own'] + ','.join(sorted(set('%04X%s%d:%s' % (e, m, own, _ss(s))
                                                                   for e, m, own, s in x['calls'])))


def contended_one(job):
    """one state's natural runs with contention OFF and ON -- [runs, total T] each, the runs an
    interrupt landed in (and the runs with a labelled frame) left out"""
    st, c = job
    rs = [x for x in run(st, FRAMES, c) if not x['irq'] and not x['opaque']]
    return [len(rs), sum(x['T'] for x in rs)]


def window_one(c):
    """M7.92: round1_48's first WINDOW frames, contention off / on, NO KEYS (the census is idle round 1: the key
    script's jumps and blows change the passes a frame, and with them this routine's mix) -- [runs, total T,
    {own: [n, T]}, labelled, irq].  EVERY run, the ones an interrupt landed in too (their T has the ISR bracketed
    out; they are walks, and leaving them out would bias the mix).  By $8669's own T (its own code touches
    no contended byte) because the edge gate lets ONE pass a frame walk the items: contention changes the
    passes a frame, so the two machines' MIXES differ and the stretch is taken path by path.
    'eleven': the same over the runs entered with ($8DBD) EVEN -- the frames after the light ISR, the census's
    11-pass frames (build/timing_fixture.json 'odd_passes': its parity is read after the frame's closing ISR).
    The edge gate walks once a frame, so an 11-pass frame's mean is lighter than the window's: THAT is the
    share BB_PASS_T held where it was fit (its band is the 11-pass frames', M7.90's 6,182..6,211 T)"""
    rs = run('round1_48', WINDOW, c, keys=False)

    def tab(q):
        by = collections.defaultdict(lambda: [0, 0])
        for x in q:
            by[str(x['own'])][0] += 1; by[str(x['own'])][1] += x['T']
        return [len(q), sum(x['T'] for x in q), {k: by[k] for k in sorted(by)}]
    return {'all': tab(rs), 'eleven': tab([x for x in rs if x['par'] == 0]),
            'labelled': sum(1 for x in rs if x['opaque']), 'irq': sum(1 for x in rs if x['irq'])}


def _stat(v):
    v = sorted(v)
    return {'n': len(v), 'min': v[0], 'max': v[-1], 'median': v[len(v) // 2], 'total': sum(v)} if v else None


def measure(jobs):
    work = [(s, None) for s in A.STATES] + [(c[1], c[0]) for c in CALLS]
    cwork = [(s, c) for s in A.STATES for c in (False, True)]
    with Pool(min(jobs, 6)) as pool:
        res = pool.map(one, work)
        cres = pool.map(contended_one, cwork)
        wres = pool.map(window_one, (False, True))
    contended = {s: [cres[2 * i], cres[2 * i + 1]] for i, s in enumerate(A.STATES)}
    rows, perkey = [], collections.Counter()
    n_runs = n_irq = n_halt = 0
    ts, ts_nb, owns, sigs = [], [], collections.Counter(), set()
    bad, checked = [], collections.Counter()
    paths = collections.defaultdict(dict)       # entry -> {mode sig: [count, own]}
    forced_new = collections.defaultdict(set)
    opq = collections.defaultdict(list)
    kidn = collections.Counter()
    branches = collections.defaultdict(set)     # entry -> {pc t/f}
    for (s, tag), rs in zip(work, res):
        for b, x, key, r in rs:
            bad += [[x_ for x_ in [tag or s]] + bb for bb in b]
            frames_ = [(ENTRY, '-', x['own'], x['sig'])] + x['calls']
            for e, m, own, sg in frames_:
                checked['%04X' % e] += 1
                k = m + ' ' + _ss(sg)
                if tag:
                    if k not in paths['%04X' % e]:
                        forced_new['%04X' % e].add(k)
                    continue
                for q, c in sg:
                    branches['%04X' % e].add('%04x%s' % (q, c))
                d = paths['%04X' % e]
                if k in d:
                    d[k][0] += 1
                    assert d[k][1] == own, 'one path, two owns: %04X %s' % (e, k)
                else:
                    d[k] = [1, own]
            if tag:
                rows.append(r)
                continue
            n_runs += 1; n_irq += 1 if x['irq'] else 0; n_halt += 1 if x['halt'] else 0
            ts.append(x['T']); owns[x['own']] += 1; sigs.add(_ss(x['sig']))
            if not x['opaque']:
                ts_nb.append(x['T'])
            for l, e, t in x['opaque']:
                opq['%s %04X' % (l, e)].append(t)
            for k, t in x['kids']:
                kidn['%04X' % k] += 1
            if r is not None and perkey[key] < KEEP:
                perkey[key] += 1
                rows.append(r)
    for e in forced_new:
        forced_new[e] = sorted(forced_new[e])
    return {'note': __doc__.split('\n')[0], 'frames': FRAMES, 'actions': B.ACTIONS, 'key_frames': B.KEY_FRAMES,
            'states': A.STATES, 'forced': [c[0] for c in CALLS], 'W': W,
            'runs': n_runs, 'irq_runs': n_irq, 'halt_runs': n_halt, 'paths': len(sigs), 'T': _stat(ts),
            'T_no_labelled': _stat(ts_nb), 'own': [min(owns), max(owns)], 'own_distinct': len(owns),
            'kids': dict(kidn), 'labelled': {k: _stat(v) for k, v in sorted(opq.items())},
            'routine_paths': {e: {k: v for k, v in sorted(d.items())} for e, d in sorted(paths.items())},
            'branches': {e: sorted(v) for e, v in sorted(branches.items())},
            'forced_paths_new': {e: v for e, v in sorted(forced_new.items())},
            'contended': contended,
            'window': {'frames': WINDOW, 'state': 'round1_48', 'off': wres[0], 'on': wres[1]},
            'model': {'bad': bad, 'checked': dict(sorted(checked.items()))},
            'rows': rows}


def main():
    args = sys.argv[1:]
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 6
    F = json.loads(json.dumps(measure(jobs)))
    if 'verify' in args:
        old = json.load(open(FIXTURE, encoding='utf-8'))
        ok = json.dumps(old, sort_keys=True) == json.dumps(F, sort_keys=True)
        print('MATCH' if ok else 'DIFFER'); sys.exit(0 if ok else 1)
    json.dump(F, open(FIXTURE, 'w', encoding='utf-8'), separators=(',', ':'))
    print('runs %d (irq %d, halt %d) paths %d T %s own %s/%d | rows %d' % (
        F['runs'], F['irq_runs'], F['halt_runs'], F['paths'], F['T'], F['own'], F['own_distinct'], len(F['rows'])))
    print('T without labelled frames', F['T_no_labelled'])
    print('kids', F['kids'])
    print('labelled', json.dumps(F['labelled']))
    print('model: bad %d; checked %s' % (len(F['model']['bad']), F['model']['checked']))
    for b in F['model']['bad'][:20]: print('  BAD', b)
    for e, d in F['routine_paths'].items():
        print('%s: %d paths, own %s' % (e, len(d), sorted(set(v[1] for v in d.values()))))
    print('branches:'); [print('  ', e, ' '.join(v)) for e, v in F['branches'].items()]
    print('forced new:', json.dumps(F['forced_paths_new']))
    for part in ('all', 'eleven'):
        w0, w1 = F['window']['off'][part], F['window']['on'][part]
        km = w1[1] / sum(v[0] * w0[2][k][1] / w0[2][k][0] for k, v in w1[2].items())
        print('window %d frames %s: contended %d runs %d T mean %.3f ; uncontended %d runs %d T mean %.3f ; '
              'mean/mean %.6f ; by path %.6f ; owns %s %s' % (
            WINDOW, part, w1[0], w1[1], w1[1] / w1[0], w0[0], w0[1], w0[1] / w0[0], (w1[1] / w1[0]) / (w0[1] / w0[0]),
            km, w0[2], w1[2]))
    print('window labelled / irq runs: off %d / %d, on %d / %d' % (F['window']['off']['labelled'], F['window']['off']['irq'],
                                                                   F['window']['on']['labelled'], F['window']['on']['irq']))


if __name__ == '__main__':
    main()
