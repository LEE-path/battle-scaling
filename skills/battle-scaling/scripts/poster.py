#!/usr/bin/env python3
"""Compose the default PK cover from images and names; no rating input or verdict."""
import argparse
import math
from pathlib import Path

from one_image import font_file, open_image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / 'assets/media/pk-cover/template-1920x1080.png'


def side_image(image, size, focus=(.5, .4), fit='cover'):
    from PIL import Image, ImageFilter, ImageOps
    if len(focus) != 2 or any(not math.isfinite(x) or not 0 <= x <= 1 for x in focus):
        raise ValueError('Focus must contain two finite numbers between 0 and 1.')
    if fit not in ('cover', 'contain'):
        raise ValueError('Fit must be cover or contain.')
    base = ImageOps.fit(image.convert('RGB'), size, Image.Resampling.LANCZOS, centering=focus)
    if fit == 'contain':
        base = base.filter(ImageFilter.GaussianBlur(max(size) * .025)).convert('RGBA')
        foreground = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
        base.alpha_composite(foreground, ((size[0] - foreground.width) // 2,
                                          (size[1] - foreground.height) // 2))
    return base.convert('RGBA')


def caption(canvas, text, x, y, width, font_path, size):
    from PIL import ImageDraw, ImageFont
    if not text:
        return
    if '\n' in text or '\r' in text:
        raise ValueError('Use a short single-line name/version; do not pass a report.')
    draw = ImageDraw.Draw(canvas)
    for point in range(size, 11, -1):
        font = ImageFont.truetype(font_path, point)
        if draw.textlength(text, font=font) <= width:
            break
    draw.text((x, y), text, font=font, anchor='mt', fill='white',
              stroke_width=max(1, round(point * .045)), stroke_fill='black')


def compose(*, left, right, left_name, right_name, output,
            left_version='', right_version='', template=DEFAULT_TEMPLATE, font=None,
            left_focus=(.5, .4), right_focus=(.5, .4), left_fit='cover', right_fit='cover'):
    from PIL import Image, ImageDraw
    destination = Path(output).expanduser().resolve()
    sources = [Path(p).expanduser().resolve() for p in (left, right, template)]
    if destination in sources or destination.exists():
        raise ValueError('Choose a new output filename; inputs and existing files are kept intact.')
    overlay = open_image(template)
    if overlay.size != (1920, 1080) or overlay.getextrema()[3][0] == 255:
        raise ValueError('Use a native transparent 1920x1080 template, not a flattened cover.')
    canvas = Image.new('RGBA', (1920, 1080), 'black')
    for position, image, focus, fit in (
            ((0, 0), open_image(left), left_focus, left_fit),
            ((960, 0), open_image(right), right_focus, right_fit)):
        canvas.alpha_composite(side_image(image, (960, 1080), focus, fit), position)
    # The foreground owns VS, divider and brand. Never re-create its outline.
    canvas.alpha_composite(overlay)
    shade = Image.new('RGBA', canvas.size)
    draw = ImageDraw.Draw(shade)
    for y in range(820, 1080):
        draw.line((0, y, 1919, y), fill=(0, 0, 0, round(190 * (y - 820) / 260)))
    canvas.alpha_composite(shade)
    font_path = font_file(font)
    for name, version, x in ((left_name, left_version, 450), (right_name, right_version, 1470)):
        caption(canvas, name, x, 915, 800, font_path, 88)
        caption(canvas, version, x, 1010, 800, font_path, 32)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(destination, format='PNG')
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('left', 'right', 'left-name', 'right-name', 'output'):
        parser.add_argument('--' + name, required=True)
    for name in ('left-version', 'right-version'):
        parser.add_argument('--' + name, default='')
    parser.add_argument('--template', default=str(DEFAULT_TEMPLATE))
    parser.add_argument('--font')
    for side in ('left', 'right'):
        parser.add_argument('--' + side + '-focus', type=float, nargs=2, default=(.5, .4))
        parser.add_argument('--' + side + '-fit', choices=('cover', 'contain'), default='cover')
    args = parser.parse_args(argv)
    try:
        print(compose(**vars(args)))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
