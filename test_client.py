# -*- coding: utf-8 -*-
"""
Smoke test: spawn server.py over stdio as a real MCP client and exercise all
three tools. Run:  python test_client.py
"""
import asyncio
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


def payload(result):
    """Unwrap a CallToolResult.

    List-returning tools arrive as structured_content {'result': value};
    dict-returning tools arrive as JSON in the text content block.
    """
    assert not result.is_error, result
    if result.structured_content is not None:
        return result.structured_content["result"]
    return json.loads("".join(c.text for c in result.content if getattr(c, "text", None)))


async def main():
    params = StdioServerParameters(
        command=sys.executable, args=[os.path.join(HERE, "server.py")], cwd=HERE,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("tools:", names)
            assert names == ["render_text_png", "segment_words", "wrap_caption_lines"], names

            r = await session.call_tool("segment_words", {"text": "ตัดคำภาษาไทยไม่มีช่องว่าง"})
            words = payload(r)
            print("segment_words:", words)
            assert isinstance(words, list) and len(words) >= 3

            r = await session.call_tool(
                "wrap_caption_lines",
                {"text": "เพราะภาษาไทยไม่มีช่องว่างระหว่างคำ การตัดบรรทัดจึงต้องตัดที่ขอบเขตของคำจริง",
                 "max_chars": 14},
            )
            lines = payload(r)
            print("wrap_caption_lines:")
            for ln in lines:
                print("   ", ln)
            assert all(len(ln.replace(" ", "")) <= 14 + 4 for ln in lines)
            assert not any(ln and ln.split()[0] in ("ครับ", "นะ") for ln in lines)

            out_png = os.path.join(HERE, "test_out.png")
            r = await session.call_tool(
                "render_text_png",
                {"text": "เนื่องจากราคานี้\nตั้งใจเพิ่มขึ้น", "out_path": out_png,
                 "size": 72, "glow": 6},
            )
            info = payload(r)
            print("render_text_png:", info)
            assert os.path.exists(info["path"]) and info["width"] > 0

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
