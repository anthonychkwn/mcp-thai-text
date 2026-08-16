"""
HarfBuzz-shaped Thai text rasterization onto a PIL canvas.

Vendored from https://github.com/anthonychkwn/thai-text-render (same author).
Pillow builds without libraqm silently drop stacked Thai marks; shaping with
uharfbuzz applies the font's GPOS rules so tone marks stay where they belong.
"""

import numpy as np
import uharfbuzz as hb
import freetype
from PIL import Image, ImageFilter

_HB = {}            # font path -> (hb.Font, units-per-em)
_FT = {}            # font path -> freetype.Face
_LAYER_CACHE = {}   # layer key -> RGBA Image


def _hb_font(path):
    if path not in _HB:
        data = open(path, "rb").read()
        face = hb.Face(data)
        font = hb.Font(face)
        font.scale = (face.upem, face.upem)
        _HB[path] = (font, face.upem)
    return _HB[path]


def _ft_face(path):
    if path not in _FT:
        _FT[path] = freetype.Face(path)
    return _FT[path]


def _line_mask(text, path, size, tracking=0):
    """Shape and rasterize one line. Returns (mask, width, height, baseline)."""
    font, upem = _hb_font(path)
    ft = _ft_face(path)
    ft.set_pixel_sizes(0, size)
    scale = size / upem

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    infos, poss = buf.glyph_infos, buf.glyph_positions

    total = sum(p.x_advance * scale + tracking for p in poss)
    asc = ft.size.ascender >> 6
    desc = -(ft.size.descender >> 6)
    pad = max(6, size // 5)
    W = int(total) + pad * 2
    H = asc + desc + pad * 2
    baseline = asc + pad

    mask = np.zeros((H, W), dtype=np.uint16)
    penx = float(pad)
    for info, pos in zip(infos, poss):
        ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        bmp = ft.glyph.bitmap
        w, h = bmp.width, bmp.rows
        if w > 0 and h > 0:
            arr = np.array(bmp.buffer, dtype=np.uint8).reshape(h, w)
            dx = int(penx + pos.x_offset * scale + ft.glyph.bitmap_left)
            dy = int(baseline - pos.y_offset * scale - ft.glyph.bitmap_top)
            x0, y0 = max(0, dx), max(0, dy)
            x1, y1 = min(W, dx + w), min(H, dy + h)
            if x1 > x0 and y1 > y0:
                sub = arr[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
                region = mask[y0:y1, x0:x1]
                np.maximum(region, sub, out=region)
        penx += pos.x_advance * scale + tracking

    return np.clip(mask, 0, 255).astype(np.uint8), W, H, baseline


def _colorize(mask, color):
    H, W = mask.shape
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = color
    rgba[:, :, 3] = mask
    return Image.fromarray(rgba, "RGBA")


def make_layer(text, path, size, color=(255, 255, 255),
               glow=0, glow_color=(0, 0, 0), tracking=0, line_gap=None):
    """Build a tight RGBA layer for (possibly multi-line) text. Cached."""
    key = (text, path, size, tuple(color), glow, tuple(glow_color), tracking, line_gap)
    if key in _LAYER_CACHE:
        return _LAYER_CACHE[key]

    lines = text.split("\n")
    masks = [_line_mask(ln, path, size, tracking) for ln in lines]
    if line_gap is None:
        line_gap = int(size * 0.18)

    total_w = max(m[1] for m in masks)
    total_h = sum(m[2] for m in masks) + line_gap * (len(masks) - 1)
    big = np.zeros((total_h, total_w), dtype=np.uint8)
    y = 0
    for mask, w, h, _base in masks:
        x = (total_w - w) // 2
        big[y:y + h, x:x + w] = np.maximum(big[y:y + h, x:x + w], mask)
        y += h + line_gap

    text_img = _colorize(big, color)
    if glow > 0:
        pad = int(glow * 3) + 6
        glow_img = _colorize(np.pad(big, pad, mode="constant"), glow_color)
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(glow))
        ga = glow_img.split()[3].point(lambda v: min(255, int(v * 1.85)))
        glow_img.putalpha(ga)
        base = Image.new("RGBA", glow_img.size, (0, 0, 0, 0))
        base.alpha_composite(text_img, (pad, pad))
        out = Image.alpha_composite(glow_img, base)
    else:
        out = text_img

    _LAYER_CACHE[key] = out
    return out
