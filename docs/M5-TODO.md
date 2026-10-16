# M5 polish -- to-do checklist

_Origin: the `m5-polish-audit` workflow (5 auditors + synth). Items were candidates to verify, not
asserted facts. This file is the running record of what M5 closed and what genuinely remains._

**STATUS 2026-09-10: buckets A and B are CLOSED.** Bucket A (self-driven
reconciliations + static RE) closed 2026-09-08. Bucket B (the snapshot-driven behaviours) is
closed: every power-up, both giant items, item lifetime, lives/death/game-over, EXTEND completion,
the RED CROSS + projectile system, the YELLOW CROSS storm, WATER end-to-end, the 2P lightning
twin bolt, later-round enemy types 1-7 live, the player-vs-bubble contact rule, the wall-blow
rule, the randomised elementals (inert), Boris's full approach+kill, and the boss spawn + WELL DONE
ending + round-81 treasure room are all MEASURED and in docs/SPEC.md. The M6 sound gate is closed.
**All that remains is M7/engine code** (the sound-generator gate and the deferred list below).

---

## A. Self-driven reconciliations + static RE -- CLOSED 2026-09-08

All 39 items applied and spot-checked (colour formula 0/19 mismatch, `$FFE4`=HIGH live, boss death
+100000 mutation, elemental map byte-exact, `$B612`=playerX+8, disasm confirmations of the N/R
findings). See git history around commit `c3c4d8e` and docs/SPEC.md. Two owner-question follow-ups
landed here later and are also done:

- [x] Player-vs-bubble CONTACT RULE ("spikes on the back", 2026-09-09): `$B8E5-$B9E6`; any overlap
  in the box pops EXCEPT a 2 px (facing right) / 5 px (facing left) front-edge band, where walking
  into the bubble pushes it at walk speed; travelling bubbles pass through. SPEC "riding/bouncing".
- [x] Blowing against a wall (2026-09-09): flush = burst on the spot by the travel code `$BEDC`;
  4-12 px = the stopped bubble sits in the contact box and the spikes rule bursts it; >=16 px it
  stops at the wall and rises. SPEC "Blowing against a wall".

## B. Snapshot-driven behaviours -- CLOSED

- [x] Later-round enemy types 1-7 LIVE (harness-built r6/r10/r20/r30/r40/r50/r60_48): banks +
  mirrors confirmed, per-type movement census in SPEC. Side discovery: the NO-DEATH WARP
  (rounds 21/41/61 send a never-died player to round 81).
- [x] Enemy-death corpse frame drawn LIVE (`fbkill`, 2026-09-09): `$C700`/`$D340` read through the
  mono blitter `$A2B4`/`$A2B9` in flight -- the mono 32B format confirmed in situ.
- [x] All 16 power-up effects MEASURED (poke-collect + `yellow_cross.szx`): 0 rapid-fire, 1 range,
  2 range+rapid, 3/4/5 giants, 6 umbrella, 7 water fill, 8 lightning storm, 9 red-cross fire mode,
  10 contact-kill/invulnerable, 11 no-shooting, 12 level-skip, 13 lightning-blow, 14 fast-walk,
  15 +500/blow.
- [x] Power-up + points-item SPAWN rule (2026-09-09): per-round byte table `$FF90` -> position +
  power-up type; points-item type = the rotating counter `$9AE9` (advanced at level-clear `$8EF2`);
  8 rounds validated against live spawns. SPEC "Items: SOLVED".
- [x] Giant diamond + giant fruit fully CLOSED (candy-cane / peach snapshots): draw `$A8C1` 32x32,
  values +5600 (diamond OOB quirk) / +2000 (fruit), HUD x10.
- [x] Item LIFETIME (3-bit phase, 256-frame clock, remove at 4 `$86E4`) + level-clear cleanup
  (`$8ED4+`: power-up and points item clear on the last-corpse settle; corpse drops persist).
- [x] Collectible types 12/13 (`$5FC0`/`$5FE0`): blank all-zero tiles + ink 0 = invisible, unused.
- [x] HUD LIVES (`death.szx`): counters `$FDDC`/`$FDE6`, icons at row 23 corners; init to 3 at the
  new-game player init `$97D2`; death/respawn/game-over chain measured.
- [x] EXTEND completion (`EXTEND_complete.szx`): message "N I C E   1P/2P", +1 life, round advance.
- [x] WATER end-to-end (`elemental_water.szx`, the bubble pops on the player's head): attach probe
  `$9377`, natural detach at the bottom edge, 2P carry (join key '2'), flood/storm draw branch,
  free-enemy kill inside the `$AA57` slot bound.
- [x] FIRE floor-flame KILL MEASURED LIVE 2026-09-09 (`fire_kill.szx`): flame = bright RED `$42` on
  the floor surface row, 9 cells wide (the `$9FC8` cap, live `$FDF2`=9); the kill is the SHARED
  attribute probe `$9377`->`$8BC2` red branch (same as the red cross), enemy->corpse at f15.
  (Only the column-growth CADENCE is unsampled -- this capture is already fully spread.)
- [x] Blue-bottle LIGHTNING bubble (`boss_blow_bolt.szx`) + 2P twin bolt (first-free slots
  `$FDEE`/`$FDF8`) + the boss alt-pose question (it was the giant-item sprites, not a boss frame).
- [x] Bubble-pop frame `$CAA0`: NOT selected by any pop kind measured (empty/holding/timeout/storm
  bulk all read only frame 0 `$CA80`); left low-confidence, non-blocking.
- [x] Boris approach + kill MEASURED LIVE 2026-09-10 (`boris_kills_player.szx`, code `$918B`): a
  phase machine (`+4` doubles 02->80, resets $40) with a ~512-frame WAIT per stage, alternating
  Y-align to the live player Y and X-approach to the live player X (+-8 px/frame), lunging into the
  player for the AABB kill. Live-targeting verified (poked player -> Boris re-aims). One struct,
  no extra copies. SPEC "HURRY UP! + Boris".
- [x] Higher/randomised elementals (types 5-12) RESOLVED 2026-09-10 -- an UNFINISHED / INERT feature:
  the effect dispatch `$9E75` handles only 2/3/4 (5-12 hit a bare RET; h.call measured), and the
  `$C068` bubble-glyph table has real art only for water/lightning/fire (idx 0-2); types 5-12 point
  into the Spectrum ROM font (type5='E', 7='T', 12='D'...), so the bubble is drawn as a letter-glyph
  and popping it does nothing (null-sprite object, no kill, +10 pop points only). SPEC "RANDOMISED /
  higher elementals". Rounds so tagged: 3,4,7,8,9,14,21,23,27,35,40,49,53,55,56.
- [x] Boss SPAWN + ENDING MEASURED LIVE 2026-09-10 (`boss_spawn.szx` / `boss_killed.szx`): the boss
  is absent through "ROUND 80 READY!", then POPS IN whole at f41 top-centre ($A8C1 draws $FE02, no
  entrance effect) and descends. Death: bolt -> HP 0 -> +100000 -> "WELL DONE!" (row 10, flashing
  cyan $C5) + defeat graphic -> round 80->81 at f347. Round 81 = the TREASURE ROOM: 25 type-9
  diamonds at +10,000 each. SPEC "Boss SPAWN / DEATH + ENDING".
- [x] ENDGAME LOOP MEASURED LIVE 2026-09-10 (`last_diamond_81/82.szx`): clearing the treasure room
  runs `$97F8` -> `$8609` = the return lookahead `$FEC7` (reseeded `LD A,R`=30-61 at the boss),
  `$FEC7`++; a 21/41/61 milestone + no-death warps back to another (recoloured) treasure room, else
  drops into the return level. Owner's "81->82->41" is this seed's `$FEC7` walk (40->41 milestone
  bounce->41). SPEC "ENDGAME LOOP".


## C. Milestone gate -- M6 sound

- [x] M6 gate CLOSED 2026-09-09: the 48K/128K decision is the `$FAC3` TIMING PROBE (counts
  `$075E`/`$0763` = 48K); the 48K branch has NO music, 7 inline beeper emitters + the ROM click;
  the 128K branch copies the AY engine over `$C350-$D263`. New 48K states
  afterctrl48/play1p48/round1_48/round1_2p48. SPEC "M6 sound", TRAPS #28, tools/sfxcensus.py.
- [x] Per-emitter edge-train oracles: `tools/sfx_trace.py` -> build/sfx/*.json (collect, jump
  E13..21, hurry, letter, rom_click, blow).
- [ ] M6 engine side (M7): `cmp_sfx.js` + `sfxgate.py` to diff the JS generators against the
  build/sfx oracles; then the AY layer is M10.

## Deferred to M7 / engine (code, not doc facts)

- [ ] RNG faithful-vs-substitute flag (`LD A,R` / manual E1) + its mutation test (house rule 5).
- [ ] High-score persistence (`settingsStore('bb-hiscores')`, `file://` degrade, TRAPS #17).
- [ ] (low) `blitforensics.py` two-region-zero fix (shadow `$E000+$A0` contamination) -- tool fix.
- [ ] (low) Decode the packed round-record segment scheme at `$61A8` -- the live extract already
  ships the geometry, so this is provenance only.
- [ ] (low) Per-type enemy AI patch internals (`$B088`/`$B20D`/`$B25D`) -- code-read; to be diffed
  by the M8 tracediff rather than pinned by hand now.
