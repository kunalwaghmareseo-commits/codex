"""Turn a text-free hedgehog illustration into a finished quote post.

The quote is lettered here rather than by the image model so spelling is
always exact. Phrases in [square brackets] get a hand-painted highlight.
"""

import random
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONT_PATH = ROOT / "fonts" / "Mali-Bold.ttf"

INK = (43, 36, 32)
HIGHLIGHTS = [(247, 205, 84), (240, 143, 152), (132, 192, 216)]  # yellow, pink, blue


@dataclass(frozen=True)
class Layout:
    size: tuple  # final (width, height)
    text_top: int  # quote area, in final pixels
    text_bottom: int
    footer_center_y: int
    side_margin: int = 80
    max_font: int = 92
    min_font: int = 48


# Output name -> layout. Instagram stories hide ~250px at the top and bottom
# behind the app UI, so the story layout keeps text and footer inside that.
LAYOUTS = {
    "linkedin_3x4": Layout(size=(1080, 1440), text_top=110, text_bottom=610, footer_center_y=1385),
    "instagram_feed_4x5": Layout(size=(1080, 1350), text_top=85, text_bottom=560, footer_center_y=1297),
    "instagram_story_9x16": Layout(size=(1080, 1920), text_top=300, text_bottom=900, footer_center_y=990),
}

# Which illustration each output is cut from.
SOURCE_FORMAT = {
    "linkedin_3x4": "portrait_3x4",
    "instagram_feed_4x5": "portrait_3x4",
    "instagram_story_9x16": "story_9x16",
}


def parse_quote(quote):
    """Split a quote into (word, highlight_index or None, suffix) tuples.

    Punctuation right after a highlight ("[keep going].") becomes the suffix of
    the last highlighted word, so it sits outside the stroke with no gap.
    """
    words = []
    highlight = -1
    for part in re.split(r"(\[[^\]]+\])", quote):
        if not part:
            continue
        if part.startswith("["):
            highlight += 1
            words += [[w, highlight, ""] for w in part[1:-1].split()]
            continue
        tokens = part.split(" ")
        if words and tokens[0]:
            words[-1][2] += tokens.pop(0)
        words += [[w, None, ""] for w in tokens if w]
    return [tuple(w) for w in words]


def plain_quote(quote):
    return re.sub(r"[\[\]]", "", quote)


def _cover(img, size):
    """Scale to cover `size`, centred horizontally and anchored to the bottom
    so the hedgehog is never cropped (only sky is trimmed)."""
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    return img.crop((left, img.height - h, left + w, img.height))


def _line_text(words):
    return " ".join(w + suffix for w, _, suffix in words)


def _wrap(words, font, max_width):
    lines, line = [], []
    for word in words:
        trial = line + [word]
        if line and font.getlength(_line_text(trial)) > max_width:
            lines.append(line)
            line = [word]
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _fit(words, layout):
    max_width = layout.size[0] - 2 * layout.side_margin
    box_height = layout.text_bottom - layout.text_top
    for size in range(layout.max_font, layout.min_font - 1, -2):
        font = ImageFont.truetype(str(FONT_PATH), size)
        lines = _wrap(words, font, max_width)
        if len(lines) * size * 1.38 <= box_height and len(lines) <= 6:
            return font, lines
    return font, lines


def _brush(layer, box, color, rng):
    """Paint a slightly wobbly, semi-transparent marker stroke inside `box`."""
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(layer)
    steps = max(6, int((x1 - x0) / 40))
    top = [(x0 + (x1 - x0) * i / steps, y0 + rng.uniform(-4, 4)) for i in range(steps + 1)]
    bottom = [(x1 - (x1 - x0) * i / steps, y1 + rng.uniform(-4, 4)) for i in range(steps + 1)]
    ends = [(x1 + rng.uniform(4, 12), (y0 + y1) / 2), (x0 - rng.uniform(4, 12), (y0 + y1) / 2)]
    polygon = top + [ends[0]] + bottom + [ends[1]]
    draw.polygon(polygon, fill=color + (205,))
    # Lighter streaks give it a dry-brush feel.
    for _ in range(3):
        y = rng.uniform(y0 + 6, y1 - 6)
        draw.line([(x0 + rng.uniform(0, 30), y), (x1 - rng.uniform(0, 30), y + rng.uniform(-2, 2))],
                  fill=tuple(min(255, c + 25) for c in color) + (120,), width=3)


def _haze(img, layout):
    """Soft cream wash behind the quote so it reads on any sky."""
    w, _ = layout.size
    top, bottom = max(0, layout.text_top - 80), layout.text_bottom + 60
    mask = Image.new("L", (1, bottom - top))
    for y in range(bottom - top):
        t = y / (bottom - top)
        mask.putpixel((0, y), int(110 * min(1, t / 0.25, (1 - t) / 0.45)))
    mask = mask.resize((w, bottom - top))
    wash = Image.new("RGBA", (w, bottom - top), (253, 248, 236, 255))
    wash.putalpha(mask)
    img.alpha_composite(wash, (0, top))


def _footer(img, layout, text):
    font = ImageFont.truetype(str(FONT_PATH), 40)
    tw = font.getlength(text)
    pad_x, h = 34, 66
    cx, cy = layout.size[0] / 2, layout.footer_center_y
    pill = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle(
        (cx - tw / 2 - pad_x, cy - h / 2, cx + tw / 2 + pad_x, cy + h / 2),
        radius=h // 2, fill=(255, 252, 245, 215))
    img.alpha_composite(pill)
    ImageDraw.Draw(img).text((cx, cy), text, font=font, fill=INK, anchor="mm")


def render(illustration_path, quote, output_name, footer, seed):
    layout = LAYOUTS[output_name]
    art = illustration_path if isinstance(illustration_path, Image.Image) else Image.open(illustration_path)
    img = _cover(art.convert("RGB"), layout.size).convert("RGBA")
    _haze(img, layout)

    words = parse_quote(quote)
    font, lines = _fit(words, layout)
    size = font.size
    line_h = size * 1.38
    block_h = len(lines) * line_h
    y = layout.text_top + (layout.text_bottom - layout.text_top - block_h) / 2
    rng = random.Random(seed)
    space = font.getlength(" ")

    strokes = Image.new("RGBA", img.size, (0, 0, 0, 0))
    placed = []
    for line in lines:
        width = font.getlength(_line_text(line))
        x = (layout.size[0] - width) / 2
        cy = y + line_h / 2
        run_start, run_hl = None, None
        positions = []
        for word, hl, suffix in line:
            positions.append((x, word, hl))
            x += font.getlength(word)
            if suffix:
                positions.append((x, suffix, None))
                x += font.getlength(suffix)
            x += space
        # Merge neighbouring words of the same highlight into one stroke.
        for i, (wx, word, hl) in enumerate(positions + [(None, None, None)]):
            if hl != run_hl and run_hl is not None:
                px, pword, _ = positions[i - 1]
                end = px + font.getlength(pword)
                _brush(strokes, (run_start - 14, cy - size * 0.48, end + 14, cy + size * 0.5),
                       HIGHLIGHTS[run_hl % len(HIGHLIGHTS)], rng)
            if hl != run_hl:
                run_start, run_hl = wx, hl
        placed += [(px, cy, word) for px, word, _ in positions]
        y += line_h

    img.alpha_composite(strokes.filter(ImageFilter.GaussianBlur(1.2)))
    draw = ImageDraw.Draw(img)
    for px, cy, word in placed:
        draw.text((px, cy), word, font=font, fill=INK, anchor="lm",
                  stroke_width=3, stroke_fill=(255, 251, 242))

    _footer(img, layout, footer)
    return img.convert("RGB")


def extend_sky(img, ratio=9 / 16, feather=160):
    """Make a taller frame from 3:4 art by adding soft sky above it.

    Each column's colour comes from the art's own top edge, heavily blurred,
    so the new sky reads as a smooth watercolour wash rather than a stretch.
    """
    img = img.convert("RGB")
    w, h = img.size
    new_h = round(w / ratio)
    extra = new_h - h
    if extra <= 0:
        return img
    edge = img.crop((0, 0, w, 24)).resize((w, 1), Image.LANCZOS)
    sky = edge.resize((w, extra + feather), Image.BILINEAR).filter(ImageFilter.GaussianBlur(40))
    # Fade slightly lighter towards the top, like the rest of the sky wash.
    lighten = Image.new("RGB", sky.size, (253, 249, 240))
    fade = Image.linear_gradient("L").resize(sky.size).transpose(Image.FLIP_TOP_BOTTOM)
    sky = Image.composite(lighten, sky, fade.point(lambda v: int(v * 0.35)))
    canvas = Image.new("RGB", (w, new_h))
    canvas.paste(sky, (0, 0))
    mask = Image.linear_gradient("L").resize((w, feather))
    canvas.paste(img.crop((0, 0, w, feather)), (0, extra), mask)
    canvas.paste(img.crop((0, feather, w, h)), (0, extra + feather))
    return canvas
