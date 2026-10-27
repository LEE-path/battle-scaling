#!/usr/bin/env python3
"""Optional Pillow collage helper. Creates a PNG; no rating or acceptance workflow."""
import argparse
import json
from pathlib import Path

DEFAULT_TITLE = '论战圈你不得不承认的事实'
ASSETS = Path(__file__).resolve().parents[1] / 'runtime' / 'media-assets.local.json'


def open_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert('RGBA')


def font_file(explicit=None):
    paths = [explicit] if explicit else [
        str(Path(__file__).resolve().parents[1] / 'assets/media/fonts/SmileySans-Oblique.ttf'),
        'C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/msyh.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/System/Library/Fonts/PingFang.ttc']
    for path in paths:
        if path and Path(path).is_file():
            return path
    raise OSError('Provide a Chinese font with --font.')


def wrap_text(text, draw, font, width):
    lines, line = [], ''
    for char in text:
        if char == '\n':
            lines.append(line)
            line = ''
        elif line and draw.textlength(line + char, font=font) > width:
            lines.append(line)
            line = char
        else:
            line += char
    return lines + [line]


def draw_text(canvas, text, box, path, size, emoji=None):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = box
    for point in range(round(size), 9, -1):
        font = ImageFont.truetype(path, point)
        icon_side = round(point * 1.1) if emoji else 0
        gap = round(point * .15) if emoji else 0
        lines = wrap_text(text, draw, font, right - left - icon_side - gap)
        row = round(point * 1.35)
        if len(lines) * row <= bottom - top:
            break
    y = (top + bottom - len(lines) * row) / 2
    for index, line in enumerate(lines):
        suffix = icon_side + gap if emoji and index == len(lines) - 1 else 0
        width = draw.textlength(line, font=font)
        x = (left + right - width - suffix) / 2
        draw.text((x, y), line, font=font, fill='black', anchor='lt')
        if suffix:
            from PIL import Image, ImageOps
            icon = ImageOps.contain(emoji, (icon_side, icon_side), Image.Resampling.LANCZOS)
            canvas.alpha_composite(icon, (round(x + width + gap), round(y)))
        y += row


def place(canvas, image, slot):
    from PIL import Image, ImageOps
    left, top, right, bottom = slot
    fitted = ImageOps.contain(image, (right - left, bottom - top), Image.Resampling.LANCZOS)
    x, y = (left + right - fitted.width) // 2, (top + bottom - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return x, y, fitted.width, fitted.height


def emoji_image(path=None):
    from PIL import Image, ImageDraw, ImageFont
    if path:
        return open_image(path)
    candidates = ['C:/Windows/Fonts/seguiemj.ttf', '/System/Library/Fonts/Apple Color Emoji.ttc']
    for candidate in candidates:
        if Path(candidate).is_file():
            icon = Image.new('RGBA', (160, 160))
            ImageDraw.Draw(icon).text((10, 10), '😂', font=ImageFont.truetype(candidate, 100),
                                      embedded_color=True, anchor='lt')
            return icon.crop(icon.getbbox())
    raise OSError('Provide an emoji image with --emoji-image, or omit --emoji.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--winner', required=True)
    parser.add_argument('--loser', required=True)
    parser.add_argument('--winner-name', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--surrender')
    parser.add_argument('--face-box', type=float, nargs=4, metavar=('LEFT','TOP','RIGHT','BOTTOM'),
                        help='Optional normalized face/core position in loser image, used only for layout')
    parser.add_argument('--title', default=DEFAULT_TITLE)
    parser.add_argument('--address', default='爸爸')
    parser.add_argument('--font')
    parser.add_argument('--emoji', action='store_true')
    parser.add_argument('--emoji-image')
    parser.add_argument('--width', type=int, default=1080)
    parser.add_argument('--height', type=int, default=1080)
    args = parser.parse_args(argv)
    try:
        from PIL import Image, ImageOps
        surrender = args.surrender
        if not surrender and ASSETS.is_file():
            surrender = json.loads(ASSETS.read_text(encoding='utf-8-sig')).get('surrender', {}).get('image')
        if not surrender:
            parser.error('Provide the Suiryu image with --surrender.')
        output = Path(args.output).expanduser().resolve()
        if output.exists():
            parser.error('Choose a new output filename; source files are kept intact.')
        if args.width < 320 or args.height < 320:
            parser.error('Use a canvas of at least 320 pixels per side.')
        target = args.face_box or (.3, .15, .7, .65)
        a, b, c, d = target
        if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
            parser.error('--face-box uses normalized left top right bottom coordinates.')
        font = font_file(args.font)
        canvas = Image.new('RGBA', (args.width, args.height), 'white')
        w, h = args.width, args.height
        slot = lambda x0, y0, x1, y1: tuple(round(v * scale) for v, scale in zip((x0,y0,x1,y1), (w,h,w,h)))
        place(canvas, open_image(args.winner), slot(.05,.28,.43,.76))
        x, y, lw, lh = place(canvas, open_image(args.loser), slot(.57,.28,.95,.76))
        box = (round(x+a*lw), round(y+b*lh), round(x+c*lw), round(y+d*lh))
        overlay = ImageOps.fit(open_image(surrender), (box[2]-box[0], box[3]-box[1]),
                               method=Image.Resampling.LANCZOS)
        canvas.alpha_composite(overlay, (box[0], box[1]))
        icon = emoji_image(args.emoji_image) if args.emoji or args.emoji_image else None
        draw_text(canvas, args.title, slot(.05,.04,.95,.23), font, min(w*.056,h*.09), icon)
        draw_text(canvas, '>', slot(.455,.42,.545,.67), font, min(w*.14,h*.20))
        draw_text(canvas, args.winner_name + args.address + '我错了', slot(.35,.80,.97,.97),
                  font, min(w*.055,h*.085))
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert('RGB').save(output, format='PNG')
        print(str(output))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
