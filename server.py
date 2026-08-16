# -*- coding: utf-8 -*-
"""
mcp-thai-text: an MCP server for Thai text handling.

Gives any MCP client (Claude Code, Claude Desktop, or your own agent) three
things agents routinely get wrong about Thai:

  segment_words     Thai has no spaces between words; agents that need word
                    boundaries (for wrapping, counting, alignment) cannot get
                    them by splitting on whitespace.

  wrap_caption_lines
                    Breaking Thai for on-screen captions has to happen at real
                    word boundaries, and some words must not start or end a
                    line. Splitting on character count alone splits words in
                    half.

  render_text_png   Most renderers on machines without proper complex-script
                    shaping silently drop stacked Thai tone marks. This tool
                    shapes with HarfBuzz and rasterizes with FreeType so the
                    output is spelled correctly.

Run over stdio:

    python server.py

Claude Code registration:

    claude mcp add thai-text -- python /path/to/server.py
"""

import os

from mcp.server import MCPServer

import thai_shaping

server = MCPServer(
    name="thai-text",
    version="1.0.0",
    instructions=(
        "Thai text utilities: word segmentation, caption line wrapping at "
        "word boundaries, and Thai-correct PNG text rendering. Use "
        "render_text_png instead of drawing Thai with renderers that lack "
        "complex-script shaping (they silently drop tone marks)."
    ),
)

# Words that read badly at a line edge. A line that ends on a lead-in leaves
# the viewer hanging; a line that starts with an enclitic reads as a fragment.
LEAD_IN = set("คือ ถ้า แล้ว เพราะ ก็ แต่ และ ที่ ซึ่ง กับ หรือ พอ จน ว่า ใน ของ ให้ เรา ผม".split())
ENCLITIC = set("ไหม มั้ย นะ น่ะ ครับ คับ ค่ะ คะ ล่ะ หรอ เหรอ สิ ซิ แหละ ไง ด้วย เลย กัน อีก".split())

# Common Thai font locations checked in order when font_path is not given.
FONT_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\Kanit-SemiBold.ttf"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\Kanit-Regular.ttf"),
    r"C:\Windows\Fonts\LeelawUI.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Sukhumvit.ttc",
]


def _visible_len(s: str) -> int:
    return len(s.replace(" ", ""))


def _tokenize(text: str, engine: str = "newmm") -> list[str]:
    from pythainlp.tokenize import word_tokenize
    return [t for t in word_tokenize(text.strip(), engine=engine) if t.strip()]


@server.tool()
def segment_words(text: str, engine: str = "newmm") -> list[str]:
    """Split Thai text into words.

    Thai is written without spaces between words, so word boundaries need a
    dictionary-based tokenizer (PyThaiNLP), not str.split(). Returns the words
    in order. engine: "newmm" (default, fast and accurate) or any other
    PyThaiNLP engine name.
    """
    return _tokenize(text, engine)


@server.tool()
def wrap_caption_lines(text: str, max_chars: int = 16) -> list[str]:
    """Break Thai text into caption/subtitle lines at word boundaries.

    Lines are packed greedily up to max_chars visible characters, then two
    readability rules are applied: lead-in words (คือ ถ้า แล้ว เพราะ ...) never
    end a line, and enclitics (ครับ ค่ะ นะ ไหม ...) never start one. Use this
    for on-screen captions instead of breaking on character count, which splits
    words in half.
    """
    tokens = _tokenize(text)
    lines: list[str] = []
    cur = ""
    for t in tokens:
        if cur and _visible_len(cur) + _visible_len(t) > max_chars:
            lines.append(cur)
            cur = t
        else:
            cur += t
    if cur:
        lines.append(cur)

    for i in range(len(lines) - 1):
        toks = _tokenize(lines[i])
        if toks and toks[-1] in LEAD_IN and _visible_len(lines[i]) > _visible_len(toks[-1]):
            lines[i] = "".join(toks[:-1])
            lines[i + 1] = toks[-1] + lines[i + 1]

    for i in range(1, len(lines)):
        toks = _tokenize(lines[i])
        if toks and toks[0] in ENCLITIC \
                and _visible_len(lines[i - 1]) + _visible_len(toks[0]) <= max_chars + 4:
            lines[i - 1] += toks[0]
            lines[i] = "".join(toks[1:])

    return [ln for ln in lines if ln.strip()]


@server.tool()
def render_text_png(
    text: str,
    out_path: str,
    font_path: str = "",
    size: int = 64,
    color: str = "#ffffff",
    background: str = "transparent",
    glow: int = 0,
) -> dict:
    """Render Thai text to a PNG with correct mark stacking.

    Renderers without complex-script shaping (Pillow without libraqm, libass
    subtitle burn-in) silently drop stacked Thai tone marks, turning เนื่อง
    into เนือง. This tool shapes the text with HarfBuzz so GPOS mark
    positioning is applied, then rasterizes with FreeType.

    text may contain \\n for multiple centred lines. color and background are
    hex like #ffffff; background "transparent" keeps alpha. glow > 0 draws a
    soft halo of that blur radius behind the text (useful over video).
    Returns the written path and image dimensions.
    """
    font = font_path or next((p for p in FONT_CANDIDATES if os.path.exists(p)), "")
    if not font or not os.path.exists(font):
        raise ValueError(
            "No Thai font found. Pass font_path pointing to a Thai-capable "
            ".ttf (Kanit, Sarabun, Noto Sans Thai)."
        )

    def hex_rgb(h: str) -> tuple:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    layer = thai_shaping.make_layer(
        text, font, size, color=hex_rgb(color),
        glow=glow, glow_color=(0, 0, 0),
    )
    if background != "transparent":
        from PIL import Image
        bg = Image.new("RGBA", layer.size, hex_rgb(background) + (255,))
        bg.alpha_composite(layer)
        layer = bg

    out = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    layer.save(out)
    return {"path": out, "width": layer.size[0], "height": layer.size[1], "font": font}


if __name__ == "__main__":
    server.run()
