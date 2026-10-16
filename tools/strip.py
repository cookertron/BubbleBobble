"""Tile the dumps in build/frames into one contact strip.

Not a gate -- this is the LOOK step (manual phase 16).  `node test/filmstrip.js`
writes the dumps; this renders them through the same display-file decoder the
rest of the kit uses and tiles them with their frame numbers.

    python tools/strip.py [out.png] [--cols N] [--scale N]
"""
import sys, os, glob
sys.path.insert(0, 'tools')
from screen import render
from PIL import Image, ImageDraw

def main():
    args = sys.argv[1:]
    out = 'build/strip.png'
    cols, scale = 4, 2
    if args and not args[0].startswith('--'):
        out = args.pop(0)
    if '--cols' in args:
        i = args.index('--cols'); cols = int(args[i + 1]); del args[i:i + 2]
    if '--scale' in args:
        i = args.index('--scale'); scale = int(args[i + 1]); del args[i:i + 2]

    files = sorted(glob.glob('build/frames/*.bin'))
    if not files:
        raise SystemExit('no dumps -- run `node test/filmstrip.js` first')
    tiles = []
    for f in files:
        mem = open(f, 'rb').read()
        img = render(mem, 0x4000, 0x5800)
        if scale != 1:
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        tiles.append((os.path.basename(f)[1:-4].lstrip('0') or '0', img))

    tw, th = tiles[0][1].size
    pad, lab = 6, 14
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (tw + pad) + pad,
                              rows * (th + pad + lab) + pad), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(tiles):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad + lab)
        sheet.paste(img, (x, y))
        d.text((x + 2, y + th + 2), 'frame ' + name, fill=(170, 170, 180))
    sheet.save(out)
    print('wrote %s (%dx%d, %d frames)' % (out, sheet.width, sheet.height, len(tiles)))


if __name__ == '__main__':
    main()
