# -*- coding: utf-8 -*-
"""The SUBSTITUTE BANNER FONT -> build/bannerfont.json.  A DECLARED DEPARTURE.

$802E is the game's string printer and $8044 builds every glyph address as
$3C00 + 8*code -- THE SPECTRUM ROM CHARACTER SET.  This project ships no ROM
transcription (README), so the port cannot use those cells.  THREE printers
address that one set, and every string the port prints through any of them is
listed in STRINGS, by address:

  $802E, in play (its base is $804A's `LD BC,$3C00`):
    $9A06  "ROUND    n"       $98C4's round banner, single height  (M7.28)
    $9A11  "READY    !"       $98D4, the same loop's second row     (M7.28)
    $9A1C  "HURRY UP !"       $9037's banner, single height   (M7.19/M7.20)
    $9A27  "WELL DONE!"       $8E9D's boss banner, single height   (M7.29)
    $9AB8  "CREDIT 6"         $9758's credit line, single height   (M7.30)
    $9A95  "GAME OVER"        $8CE7's game-over loop, single height (M7.31)
    $9A9F  "PERFECT !"        $8F78's treasure-room tally, DOUBLE height
    $9AA9  "N I C E      P"   $94C2's EXTEND fanfare, DOUBLE height, with
                              $9AB3 overwritten by '1' or '2' at $94E7
    $85C1  "    1UP    HIGH SCORE    2UP"    $7FE9's HUD row 0    (M7.36)
    $85DE  "      00     1000000       00"   $7FEF's HUD row 1    (M7.36,
                                          the tape's bytes since M7.40)
      *** $85C1 AND $85DE ARE ONE 59-BYTE STATIC TEMPLATE FROM THE TAPE, NOT A
      BUFFER. ***  Measured zero writes to $85C1..$85FB over 17,400 driven
      frames; the only bytes ever written inside it are $85E9..$85F0, by $7FC0's
      own RRD conversion of the four BCD record bytes.  $7FEF does not LOAD its
      pointer -- $802E's `INC IX` carries it past the first NUL at $85DD.
    $9A32  "B U B B L E  B O B B L E"        $9729's title, DOUBLE height
    $9A4B  "By Software Creations"           chained by $802E's INC IX, DOUBLE
    $9A61  "Program: Mike Follin"            chained, DOUBLE height
    $9A76  "1 OR 2 TO PLAY"                  chained, DOUBLE height (GROUP 1)
  $F80B, the control select's OWN printer (its base read from CHARS, $5C36,
  which holds $3C00 at every front-end state) -- GROUP 3, H-a, M7.53:
    $F893 .. $F967  the seven control-select strings, '@'-terminated, DOUBLE height
  the ROM's own channel-2 printer, behind $FA71's RST $10 (GROUP 3, H-a, M7.53):
    $FA88  "  LICENSED BY FIREBIRD SOFTWARE "  SINGLE height

*** THIS FONT IS INDEXED BY CHARACTER CODE, not by position in one string. ***
make_hurry.py produced a ten-cell list for one string, which meant the port held
a second, position-indexed transliteration of $802E beside the general one.  One
routine, one transliteration: this file replaces build/hurryfont.json's role and
the SEVEN codes that string uses kept make_hurry's exact bytes, so the HURRY
banner did not move a pixel and M7.20's gates held it in place -- until M7.53,
which redrew the 'P' (below) and re-derived build/hurryfont.json with it
(--refreeze-hurry).  Every normal run checks that record against these cells.

*** AND THE ASSERT IS A MINIMUM, NOT MERELY AN INEQUALITY. ***  The first drafts
of T and F differed from the ROM's cells in ONE and TWO bytes of eight -- enough
to satisfy "not identical" and not enough to be a different face.  An inked
glyph must now differ in at least MIN_DIFF of its eight bytes, and the per-glyph
count is reported as evidence rather than as a promise.  A blank cell is eight
zero bytes in any font, so the space is exempt in both directions: it may not
carry ink here, and it is not asked to differ.

*** AND NOT ONLY FROM THE ALIGNED CELL (M7.53, the review's F7). ***  That check
compares a glyph with the ROM cell at its own code, and nothing else -- and
M7.20's 'P' was BYTE FOR BYTE an eight-byte window of the ROM (another cell's
rows, a row out of line), while M7.53's first 'K' and '.' sat two bytes from
their own cells moved down one row.  Two more rules, both refusing:
    no inked glyph may EQUAL any eight-byte window of the 16K ROM;
    every inked glyph differs in >= MIN_DIFF bytes from its own ROM cell moved
    -2..+2 rows.
Only per-glyph MINIMUM COUNTS are reported (rows[].rom_window_min and
rows[].displaced_min, and the least of each), never a ROM byte.

The ROM is read from the analysis harness for those comparisons ONLY.  No ROM byte
is written to build/bannerfont.json or to any other artifact, and no comment here
may quote one: M7.53 took the S's and G's ROM rows out of their notes.

CONSEQUENCE, carried in the README and in M8: none of these banners will be
pixel-identical to the original, so a frame-level differential must EXEMPT the
cells they occupy.  Everything else is faithful and gated: which cells are
addressed, the eight-bit `INC L` walk, the $803C mode operand that switches $802E
between the single-height $804F and the double-height $8058, and the attribute
runs through $994F.

    python tools/make_banner.py                    -> build/bannerfont.json
    python tools/make_banner.py --refreeze-hurry   -> ...and build/hurryfont.json
"""
import sys, os, json, base64
sys.path.insert(0, 'tools')

CHARSET = 0x3C00                  # $804A LD BC,$3C00
MIN_DIFF = 3                      # of eight bytes, for any glyph carrying ink
OUT = 'build/bannerfont.json'

STRINGS = {
    '9A06': 'ROUND    0',
    '9A11': 'READY    !',
    '9A1C': 'HURRY UP !',
    '9A27': 'WELL DONE!',
    '9A9F': 'PERFECT !',
    '9AA9': 'N I C E      P',
    '9AB8': 'CREDIT 6',
    '9A95': 'GAME OVER',
    '85C1': '    1UP    HIGH SCORE    2UP',
    #  THE TAPE'S BYTES (M7.40).  M7.36 shipped `000200000`, a value $7FC0 had
    #  ALREADY converted from the 20,000 record -- the run image, not the load
    #  image.  tape, boot, title and afterctrl48 all hold `  1000000` here.
    '85DE': '      00     1000000       00',
    #  The title screen's four DOUBLE-HEIGHT strings (GROUP 1, $9729..$974F):
    #  IX is loaded ONCE at $9729 and $802E's own `INC IX` chains all four, so
    #  the machine sees one 79-character walk from $9A32 to the NUL at $9A84.
    '9A32': 'B U B B L E  B O B B L E',
    '9A4B': 'By Software Creations',
    '9A61': 'Program: Mike Follin',
    '9A76': '1 OR 2 TO PLAY',
    #  THE CONTROL-SELECT SCREEN (GROUP 3, H-a, M7.53) -- the SECOND of the three printers
    #  over this one table: $F80B's walk is '@'-terminated and reads its charset base from
    #  CHARS ($5C36), which holds $3C00 at every front-end state (boot, title), so the same
    #  code-indexed cells serve it.  Seven strings, DOUBLE height; $F932 is the player digit
    #  ('1' on the tape, '2' on player 2's pass -- both in EXTRA).
    'F893': 'B U B B L E   B O B B L E',
    'F918': 'CHOOSE CONTROL FOR PLAYER 1',
    'F934': '1. KEYBOARD',
    'F940': '2. SINCLAIR',
    'F94C': '3. KEMPSTON',
    'F958': '4. CURSOR TYPE',
    'F967': '                   ',
    #  ...and the THIRD: $FA71's `RST $10` stream through the ROM's channel-2 printer, SINGLE
    #  height, at AT 21,0.  The seven control bytes before it (INK 8, PAPER 8, AT 21,0) print
    #  nothing; the key is the address of the first PRINTABLE byte, $FA81 + 7.
    'FA88': '  LICENSED BY FIREBIRD SOFTWARE ',
    #  THE REDEFINE SCREEN (GROUP 3, H-c, M7.62) -- $F80B again, six strings, DOUBLE height; $F8C4
    #  is the player digit.  The ECHO over each '?' is ECHO below.
    'F8AD': 'CHOOSE KEYS FOR PLAYER 1',
    'F8C6': '   LEFT :?',
    'F8D1': '  RIGHT :?',
    'F8DC': '   FIRE :?',
    'F8E7': '   JUMP :?',
    'F8F2': '  ALL OK ?',
}
#  $94E7 writes '1' or '2' over $9AB3, and $7F94/$7FA6 write the round number
#  over $9A0E/$9A0F -- so every digit is reachable.  (The tape's own copy holds
#  $20 $30, "ROUND    0"; this said '9', which was extcomp's, until M7.41.)
EXTRA = '0123456789'
#  ...and the redefine screen's ECHO ($F7F6 CALL $F850 with $F850 a NOP): the key read's filter
#  passes '0'..'Z', and the keys reach the digits, the capitals, SPACE as '_' ($F803), ENTER as ']'
#  ($F807) and SYMBOL SHIFT's X, 0 and H as '@', '?' and '>' (tools/ctrlmenu.py's decode)
ECHO = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_]@?>'

#  Drawn by hand.  Bit 7 is the leftmost pixel; the face is a five-wide slab on
#  bits 6..2 against the ROM's six- and seven-wide cells on bits 7..1.
GLYPHS = {
    #  ---- the SEVEN that "HURRY UP !" already froze (make_hurry.py) --------
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    '!': [0x00, 0x30, 0x30, 0x30, 0x20, 0x00, 0x30, 0x00],   # tapered stem
    'H': [0x00, 0x44, 0x44, 0x44, 0x7C, 0x44, 0x44, 0x00],
    #  *** REDRAWN BY M7.53 (the review's F7). ***  M7.20's P was a bowl of two rows over a
    #  one-pixel stem, and those eight bytes were, byte for byte, an eight-byte window of
    #  the ROM -- another cell's rows, one row out of line -- which the aligned MIN_DIFF
    #  check could not see.  Now the bowl is SQUARE, its bars the E's full width, and the
    #  stem ends on the F's two-pixel foot.  build/hurryfont.json re-derived with it.
    'P': [0x00, 0x7C, 0x44, 0x44, 0x7C, 0x40, 0x60, 0x00],
    'R': [0x00, 0x78, 0x44, 0x44, 0x78, 0x50, 0x48, 0x00],
    'U': [0x00, 0x44, 0x44, 0x44, 0x44, 0x44, 0x38, 0x00],
    'Y': [0x00, 0x44, 0x7C, 0x10, 0x10, 0x10, 0x38, 0x00],
    #  ---- and the EIGHT this increment adds, in the same face -------------
    'C': [0x00, 0x7C, 0x40, 0x40, 0x40, 0x40, 0x7C, 0x00],   # square bracket,
                                                             #   no ROM in-curve
    'E': [0x00, 0x7C, 0x40, 0x78, 0x40, 0x40, 0x7C, 0x00],
    #  F's first draft was [.. 7C 40 78 40 40 40 ..] and differed from the ROM
    #  in TWO bytes of eight.  A two-pixel foot on the stem, which is the slab
    #  detail the rest of the face carries.
    'F': [0x00, 0x7C, 0x40, 0x78, 0x40, 0x40, 0x60, 0x00],
    'I': [0x00, 0x38, 0x10, 0x10, 0x10, 0x10, 0x38, 0x00],
    'N': [0x00, 0x44, 0x64, 0x54, 0x4C, 0x44, 0x44, 0x00],
    #  T's first draft was [.. 7C 10 10 10 10 10 ..] -- a narrower crossbar and
    #  NOTHING else, ONE byte of eight.  A shoulder under the bar and a flared
    #  foot, both of which the Y already uses.
    #  *** AND THE SHOULDER MADE IT AN I (M7.41). ***  [.. 7C 38 10 10 10 38 ..]
    #  sits one narrow row from the I's [.. 38 10 10 10 10 38 ..], and on the
    #  title screen a reviewer read "1 OR 2 IO PLAY" and "CREDII 6".  The bar is
    #  now TWO FULL ROWS -- a heavy slab no I has -- and the flared foot stays.
    'T': [0x00, 0x7C, 0x7C, 0x10, 0x10, 0x10, 0x38, 0x00],
    '1': [0x00, 0x10, 0x30, 0x10, 0x10, 0x10, 0x38, 0x00],
    '2': [0x00, 0x78, 0x04, 0x04, 0x38, 0x40, 0x7C, 0x00],
    #  ---- and the ELEVEN M7.28 adds for "ROUND    n" and "READY    !" ------
    'A': [0x00, 0x38, 0x44, 0x44, 0x7C, 0x44, 0x44, 0x00],
    #  D's first draft was the ROM's with a straight right side -- TWO bytes of
    #  eight.  A clipped bottom-right corner instead, which is the slab the rest
    #  of the face carries.
    'D': [0x00, 0x7C, 0x44, 0x44, 0x44, 0x48, 0x70, 0x00],
    'O': [0x00, 0x38, 0x44, 0x44, 0x44, 0x44, 0x38, 0x00],   # round, against
    #  ...against a SLASHED zero.  It was a SQUARE box (7C 44 44 44 44 7C), and with the HUD's other digits
    #  drawn by $804F from BB_DIGITS -- a different face -- a player read the unchanged score cells as empty
    #  boxes (2026-10-08).  The machine draws both from ONE font (the ROM's), so the port does too: this
    #  font's ten digits ARE make_digits.py's (BB_DIGITS), and the zero says zero.
    '0': [0x00, 0x38, 0x4C, 0x54, 0x64, 0x44, 0x38, 0x00],
    '3': [0x00, 0x78, 0x04, 0x38, 0x04, 0x04, 0x78, 0x00],
    '4': [0x00, 0x44, 0x44, 0x7C, 0x04, 0x04, 0x04, 0x00],
    '5': [0x00, 0x7C, 0x40, 0x78, 0x04, 0x04, 0x78, 0x00],
    '6': [0x00, 0x38, 0x40, 0x78, 0x44, 0x44, 0x38, 0x00],
    '7': [0x00, 0x7C, 0x04, 0x08, 0x10, 0x10, 0x10, 0x00],
    '8': [0x00, 0x38, 0x44, 0x38, 0x44, 0x44, 0x38, 0x00],
    '9': [0x00, 0x38, 0x44, 0x44, 0x3C, 0x04, 0x38, 0x00],
    #  ---- and the TWO M7.29 adds for "WELL DONE!" -------------------------
    #  L's first draft was the ROM's with a shorter foot -- ONE byte of eight,
    #  the same trap T and F fell into.  A two-pixel stem with a waist, which
    #  is the taper the '!' and the T already carry.
    'L': [0x00, 0x60, 0x60, 0x40, 0x40, 0x60, 0x7C, 0x00],
    'W': [0x00, 0x44, 0x44, 0x44, 0x54, 0x54, 0x28, 0x00],
    #  ---- and the ONE M7.36 adds for the HUD's two rows --------------------
    #  The ROM's S is a six-wide face with a one-pixel spine.  This one is the
    #  five-wide slab the rest of the face carries, with SQUARE terminals like the
    #  C and the G rather than the ROM's tucked ones.
    'S': [0x00, 0x7C, 0x40, 0x78, 0x04, 0x44, 0x78, 0x00],
    #  ---- and the THREE M7.31 adds for "GAME OVER" ------------------------
    #  The ROM's G is the round O with a spur.  This one is
    #  the SQUARE bracket the C already uses, with a full foot and an inward
    #  spur on the same row -- five bytes of eight differ, and they differ
    #  because the face is square, not because a pixel was nudged.
    'G': [0x00, 0x7C, 0x40, 0x40, 0x4C, 0x44, 0x7C, 0x00],
    #  M is NOT the W flipped: the W's vertex is at the bottom and its stems
    #  start at the top, so flipping it puts M's vertex above its stems.  The
    #  stems run the full height and the diagonals converge inward from row 2.
    'M': [0x00, 0x44, 0x6C, 0x54, 0x44, 0x44, 0x44, 0x00],
    #  V converges onto bit 4, which is the column the Y's stem already stands
    #  in, so the two share a centre line.
    'V': [0x00, 0x44, 0x44, 0x44, 0x44, 0x28, 0x10, 0x00],
    #  ---- and the SEVENTEEN GROUP 1 adds for the title screen's strings ----
    #  B's bowls are square like the D's and the P's, the top one a row shorter
    #  than the bottom.  Against the round 8 the LEFT STEM is continuous; against
    #  P and R the lower bowl closes; against D the waist bar at row 3 is there.
    'B': [0x00, 0x78, 0x44, 0x78, 0x44, 0x44, 0x78, 0x00],
    #  Two square dots, the '!''s two-by-two point stacked twice.
    ':': [0x00, 0x00, 0x30, 0x30, 0x00, 0x30, 0x30, 0x00],
    #  *** THE LOWERCASE.  x-height rows 2..6, ascenders from row 1 (the capital
    #  height), and the descenders of g and y in row 7, which no capital uses.
    #  A five-wide slab on bits 6..2 with ONE-pixel stems is the ROM's lowercase
    #  almost exactly: the first square n and round o came back at ZERO bytes of
    #  eight, because rows 3..5 of any 44-stemmed letter are 44 in both.  So the
    #  lowercase carries the face's own TWO-PIXEL STEM (the L's, the '!''s) as
    #  VERTICAL STRESS: every left-hand vertical is bits 6,5.  That is a
    #  different face, not a nudge -- it moves the rows the ROM and a plain
    #  slab would share.  Square terminals throughout, as the C, G and S.
    'a': [0x00, 0x00, 0x78, 0x04, 0x7C, 0x64, 0x7C, 0x00],   # single storey
    'e': [0x00, 0x00, 0x7C, 0x64, 0x7C, 0x60, 0x7C, 0x00],
    #  f, i, l and t stand on a two-pixel stem at bits 5,4; each has a foot,
    #  which is the F's and the T's slab detail.
    'f': [0x00, 0x3C, 0x30, 0x78, 0x30, 0x30, 0x78, 0x00],
    #  g's bowl is square and closed; its tail is a full square hook.  y below
    #  is the OPEN u with the U's rounded join, so the pair differs at the top,
    #  the join and the tail rather than at one row.
    'g': [0x00, 0x00, 0x7C, 0x64, 0x64, 0x7C, 0x04, 0x7C],
    'i': [0x00, 0x30, 0x00, 0x70, 0x30, 0x30, 0x78, 0x00],
    'k': [0x00, 0x60, 0x64, 0x68, 0x70, 0x68, 0x64, 0x00],
    'l': [0x00, 0x70, 0x30, 0x30, 0x30, 0x30, 0x38, 0x00],
    #  m cannot carry the stress -- three stems fill five columns -- and a
    #  square m (7C 54 54 54 54) was ONE byte from the ROM's.  So it takes the
    #  T's SHOULDER under the bar and INWARD FEET on the outer stems; w takes
    #  the same feet, which is what keeps it off the capital W.
    'm': [0x00, 0x00, 0x7C, 0x7C, 0x54, 0x54, 0x6C, 0x00],
    'n': [0x00, 0x00, 0x78, 0x64, 0x64, 0x64, 0x64, 0x00],
    #  o is ROUND, as the capital O is against the square zero.
    'o': [0x00, 0x00, 0x38, 0x64, 0x64, 0x64, 0x38, 0x00],
    'r': [0x00, 0x00, 0x6C, 0x70, 0x60, 0x60, 0x60, 0x00],
    's': [0x00, 0x00, 0x7C, 0x60, 0x7C, 0x04, 0x7C, 0x00],
    't': [0x00, 0x30, 0x78, 0x30, 0x30, 0x30, 0x3C, 0x00],
    'w': [0x00, 0x00, 0x44, 0x44, 0x44, 0x54, 0x6C, 0x00],
    'y': [0x00, 0x00, 0x64, 0x64, 0x64, 0x3C, 0x04, 0x78],
    #  ---- and the TWO the control-select screen adds (GROUP 3, H-a, M7.53) --
    #  The full stop is the ':''s two-pixel width, THREE rows tall on rows 4..6, standing on
    #  the capitals' baseline.  A two-row stop lying on the same two rows as the ROM's own
    #  differs from it in at most two bytes, and the displaced check slides the ROM's stop
    #  over rows 3..8 -- so every two-row stop on rows 3..7 meets it at two bytes somewhere
    #  (the first drafts, on rows 5-6 and 6-7, both did).  The third row is the difference.
    '.': [0x00, 0x00, 0x00, 0x00, 0x30, 0x30, 0x30, 0x00],
    #  K's first draft -- the stem with the arms meeting it at row 3 -- sat ONE byte from
    #  the ROM's K, and its second -- the upper arm dropping straight for two rows -- TWO
    #  bytes from the ROM's K moved down a row.  This one keeps the capitals' one-pixel stem
    #  and runs both arms as diagonals into a JUNCTION BLOCK at row 4 (the stem and two
    #  pixels), which no ROM cell in reach of it has.  Not the lowercase k, which carries
    #  the two-pixel stress and meets at row 4 from row 2.
    'K': [0x00, 0x44, 0x48, 0x50, 0x70, 0x48, 0x44, 0x00],
    #  ---- and the NINE the redefine screen adds (GROUP 3, H-c, M7.62): its prompts' '?' and
    #  the ECHO, which prints whatever code the key read's filter passes -- every capital, the
    #  digits, SPACE as '_', ENTER as ']' and the three SYMBOL SHIFT codes it lets through
    #  ('@', '?', '>').  The same five-wide slab on bits 6..2.
    'J': [0x00, 0x1C, 0x04, 0x04, 0x04, 0x44, 0x7C, 0x00],   # the square foot of C and G
    'Q': [0x00, 0x38, 0x44, 0x44, 0x54, 0x48, 0x34, 0x00],
    'X': [0x00, 0x44, 0x28, 0x10, 0x10, 0x28, 0x44, 0x00],   # (a flat top sat 1 byte from a ROM window)
    #  a one-pixel diagonal between the bars sits two bytes from the ROM's Z: this one is the
    #  two-pixel stress of the lowercase, three rows of the difference
    'Z': [0x00, 0x7C, 0x0C, 0x18, 0x30, 0x60, 0x7C, 0x00],
    '?': [0x00, 0x78, 0x0C, 0x18, 0x30, 0x00, 0x30, 0x00],   # the '!''s two-pixel dot
    '>': [0x00, 0x00, 0x60, 0x18, 0x04, 0x18, 0x60, 0x00],
    '@': [0x00, 0x7C, 0x44, 0x5C, 0x5C, 0x40, 0x7C, 0x00],
    ']': [0x00, 0x3C, 0x0C, 0x0C, 0x0C, 0x0C, 0x3C, 0x00],
    #  a bar on row 6 alone sits two bytes from the ROM's '_' moved up a row, and so does any
    #  one- or two-row bar near it: a HOLLOW bar, rows 5..7, is three from all five placings
    '_': [0x00, 0x00, 0x00, 0x00, 0x00, 0x7C, 0x44, 0x7C],
}


def _rom_path():
    import skoolkit
    return os.path.join(os.path.dirname(skoolkit.__file__), 'resources', '48.rom')


HURRY = 'build/hurryfont.json'


def _d8(a, b):
    return sum(1 for i in range(8) if a[i] != b[i])


def _window_min(rom, g):
    """the fewest bytes by which the eight-byte cell g differs from ANY eight-byte window of
       the ROM -- a COUNT; 0 means the glyph IS a ROM window"""
    best = 9
    for s in range(len(rom) - 7):
        n = 0
        for i in range(8):
            if rom[s + i] != g[i]:
                n += 1
                if n >= best:
                    break
        if n < best:
            best = n
            if not best:
                break
    return best


def check_hurry(rom, refreeze):
    """build/hurryfont.json is the frozen record of what this font draws for "HURRY UP !".  A
       redraw that moves any of its cells must RE-DERIVE it, on purpose (--refreeze-hurry), or
       the run stops -- the record can never go stale silently."""
    H = json.load(open(HURRY))
    text = H['text']
    cells = [list(GLYPHS[ch]) for ch in text]
    if cells == H['glyphs']:
        return 'unchanged'
    if not refreeze:
        raise SystemExit('build/hurryfont.json no longer matches the cells this font draws for %r: a '
                         'redraw moved the HURRY UP ! banner.  Re-derive it with --refreeze-hurry and say '
                         'why in the commit.' % text)
    rows, inked, diff = [], 0, 0
    for k, ch in enumerate(text):
        a = CHARSET + ord(ch) * 8
        theirs = list(rom[a:a + 8])
        blank = not any(theirs)
        n = _d8(cells[k], theirs)
        if not blank:
            inked += 1
            diff += n
        rows.append({'index': k, 'char': ch, 'code': ord(ch), 'rom_at': '0x%04X' % a,
                     'blank_in_rom': blank, 'glyph': cells[k], 'bytes_differing': n})
    moved = [k for k in range(len(text)) if cells[k] != H['glyphs'][k]]
    H['glyphs'] = cells
    H['rows'] = rows
    H['inked_glyphs'] = inked
    H['bytes_differing_from_rom'] = diff
    H['bytes_total'] = 8 * inked
    H['b64'] = base64.b64encode(bytes(b for c in cells for b in c)).decode()
    H['frozen'] += ('  RE-DERIVED BY M7.53 (python tools/make_banner.py --refreeze-hurry): the P M7.20 '
                    'drew was byte for byte an eight-byte window of the ROM, so the font redrew it and '
                    'this record follows -- position%s %s moved, the other cells are M7.20\'s bytes; now '
                    '%d inked cells, %d of %d bytes differing from the ROM\'s own.'
                    % ('s' if len(moved) > 1 else '', ', '.join(str(k) for k in moved), inked, diff, 8 * inked))
    json.dump(H, open(HURRY, 'w'), indent=1)
    return 'moved %s' % moved


def main():
    refreeze = '--refreeze-hurry' in sys.argv[1:]
    needed = set(EXTRA) | set(ECHO)
    for s in STRINGS.values():
        needed |= set(s)
    missing = needed - set(GLYPHS)
    assert not missing, 'no glyph for %r' % sorted(missing)
    spare = set(GLYPHS) - needed
    assert not spare, 'glyph drawn for a character no string uses: %r' % sorted(spare)

    #  *** AND NO TWO INKED GLYPHS MAY BE THE SAME EIGHT BYTES. ***  The
    #  ROM-diff assert below asks whether each glyph differs from the ROM's; it
    #  cannot see two glyphs of THIS font being identical to each other.  That
    #  is the same class of fault as the one-byte T, F and L drafts (TRAPS #155)
    #  -- a glyph that is present and not distinct -- and O/0 and V/W are the
    #  pairs most at risk of it.
    byrow = {}
    for ch, cell in GLYPHS.items():
        if not any(cell):
            continue                      # the space is blank in any font
        byrow.setdefault(tuple(cell), []).append(ch)
    dup = sorted(v for v in byrow.values() if len(v) > 1)
    assert not dup, 'two glyphs are the same cell: %r' % dup

    rom = open(_rom_path(), 'rb').read()
    rows = []
    diff = total = inked = 0
    worst = (99, None)
    for ch in sorted(GLYPHS):
        a = CHARSET + ord(ch) * 8
        theirs = list(rom[a:a + 8])
        mine = GLYPHS[ch]
        blank = not any(theirs)
        n = sum(1 for i in range(8) if mine[i] != theirs[i])
        if blank:
            if any(mine):
                raise SystemExit('%r draws ink where the ROM has a blank' % ch)
        else:
            inked += 1
            if mine == theirs:
                raise SystemExit('%r REPRODUCES the ROM cell at $%04X' % (ch, a))
            if n < MIN_DIFF:
                raise SystemExit(
                    '%r differs from the ROM cell at $%04X in only %d of 8 bytes '
                    '(minimum %d).  "Not identical" is not "a different face".'
                    % (ch, a, n, MIN_DIFF))
            diff += n
            total += 8
            if n < worst[0]:
                worst = (n, ch)
        rec = {'char': ch, 'code': ord(ch), 'rom_at': '0x%04X' % a,
               'blank_in_rom': blank, 'glyph': mine, 'bytes_differing': n}
        if not blank:
            #  the M7.53 rules (F7): never ANY ROM window, and never within MIN_DIFF of its own
            #  cell moved -2..+2 rows.  Counts only.
            wmin = _window_min(rom, mine)
            if wmin == 0:
                raise SystemExit('%r IS an eight-byte window of the ROM' % ch)
            dmin = min(_d8(mine, rom[a - k:a - k + 8]) for k in (-2, -1, 0, 1, 2))
            if dmin < MIN_DIFF:
                raise SystemExit('%r is within %d bytes of its own ROM cell moved up or down a row or '
                                 'two (minimum %d)' % (ch, dmin, MIN_DIFF))
            rec['rom_window_min'] = wmin
            rec['displaced_min'] = dmin
        rows.append(rec)

    #  PER-STRING AGGREGATES, so this file strictly subsumes the one
    #  make_hurry.py used to write.  That tool covered "HURRY UP !" alone (8
    #  inked cells, 43 of 64 bytes differing until M7.53 redrew the P); the
    #  numbers are reproduced here CHARACTER BY CHARACTER rather than being lost
    #  when the tool was retired.  A string's counts include a repeated letter
    #  twice, because the printer indexes the STRING and not the alphabet.
    per = {}
    for at, text in sorted(STRINGS.items()):
        n_inked = n_diff = n_tot = 0
        cells = []
        for ch in text:
            a = CHARSET + ord(ch) * 8
            theirs = list(rom[a:a + 8])
            mine = GLYPHS[ch]
            blank = not any(theirs)
            d = sum(1 for i in range(8) if mine[i] != theirs[i])
            if not blank:
                n_inked += 1
                n_diff += d
                n_tot += 8
            cells.append({'char': ch, 'code': ord(ch), 'blank_in_rom': blank,
                          'bytes_differing': d})
        per[at] = {'text': text, 'cells': cells, 'inked_glyphs': n_inked,
                   'bytes_differing_from_rom': n_diff, 'bytes_total': n_tot,
                   'blank_chars': ''.join(c['char'] for c in cells
                                          if c['blank_in_rom'])}

    by_code = {str(ord(ch)): GLYPHS[ch] for ch in GLYPHS}
    json.dump({
        'note': ('SUBSTITUTE BANNER glyphs, DRAWN FOR THIS PORT -- a DECLARED '
                 'DEPARTURE.  $802E prints through $8044, which builds '
                 '$3C00 + 8*code out of the SPECTRUM ROM CHARACTER SET, and '
                 'this project ships no ROM.  Indexed BY CHARACTER CODE so one '
                 'cell serves all three printers.  Every inked cell differs from '
                 'the ROM\'s in at least %d of its 8 bytes, from its own ROM cell '
                 'moved up to two rows either way by as many, and equals no '
                 'eight-byte window of the ROM; the space is eight zero bytes in '
                 'any font and is exempt in both directions.  No ROM byte appears '
                 'in this file.' % MIN_DIFF),
        'charset_base': '0x%04X' % CHARSET, 'min_diff': MIN_DIFF,
        'strings': STRINGS, 'extra': EXTRA, 'per_string': per,
        'by_code': by_code, 'rows': rows,
        'inked_glyphs': inked, 'closest': {'char': worst[1], 'bytes': worst[0]},
        'rom_window_min': min(r['rom_window_min'] for r in rows if 'rom_window_min' in r),
        'displaced_min': min(r['displaced_min'] for r in rows if 'displaced_min' in r),
        'bytes_differing_from_rom': diff, 'bytes_total': total,
        'b64': base64.b64encode(
            bytes(b for ch in sorted(GLYPHS) for b in GLYPHS[ch])).decode(),
    }, open(OUT, 'w'), indent=1)
    print('wrote %s: %d cells for %d codes, %d inked, %d of %d bytes differ from '
          'the ROM\'s (closest: %r at %d of 8, minimum %d)'
          % (OUT, len(GLYPHS), len(GLYPHS), inked, diff, total,
             worst[1], worst[0], MIN_DIFF))
    for at in sorted(per):
        p = per[at]
        print('   $%s %-16r %d inked, %d of %d bytes differ, %d blank'
              % (at, p['text'], p['inked_glyphs'], p['bytes_differing_from_rom'],
                 p['bytes_total'], len(p['blank_chars'])))
    for r in rows:
        print('   %r (%02X) ROM %s  %-13s %d/8 differ%s'
              % (r['char'], r['code'], r['rom_at'],
                 'BLANK IN BOTH' if r['blank_in_rom'] else 'drawn',
                 r['bytes_differing'],
                 '' if r['blank_in_rom'] else
                 ', own cell moved -2..+2: >= %d, any ROM window: >= %d' % (r['displaced_min'], r['rom_window_min'])))
    print('   build/hurryfont.json: %s' % check_hurry(rom, refreeze))


if __name__ == '__main__':
    main()
