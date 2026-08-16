# mcp-thai-text

An MCP server that gives AI agents correct Thai text handling: word segmentation, caption line wrapping, and tone-mark-safe text rendering.

## Why

Agents working with Thai run into three problems that do not exist in English:

1. **No spaces between words.** Splitting on whitespace returns the whole sentence as one token. Anything that needs word boundaries (wrapping, counting, alignment to speech) needs a dictionary-based tokenizer.
2. **Line breaking is a language problem, not a length problem.** Breaking captions on character count splits words in half. And even at word boundaries, a line that ends on a lead-in word (เพราะ, แล้ว, คือ) or starts with an enclitic (ครับ, นะ, ไหม) reads wrong on screen.
3. **Renderers silently misspell Thai.** Pillow without libraqm and libass subtitle burn-in both drop stacked tone marks: เนื่อง comes out as เนือง, นี้ as นี. No error is raised. The output is just wrong.

This server packages the fixes as three MCP tools so any client (Claude Code, Claude Desktop, or your own agent loop) can call them.

## Tools

| tool | input | output |
|---|---|---|
| `segment_words` | Thai text | list of words (PyThaiNLP newmm) |
| `wrap_caption_lines` | Thai text, max chars per line | caption lines broken at word boundaries, with lead-in and enclitic rules applied |
| `render_text_png` | text, output path, font, size, color, glow | a PNG with HarfBuzz-shaped, correctly stacked Thai text |

## Install

```bash
pip install -r requirements.txt
```

Register with Claude Code:

```bash
claude mcp add thai-text -- python /path/to/mcp-thai-text/server.py
```

Or in any MCP client config:

```json
{
  "mcpServers": {
    "thai-text": {
      "command": "python",
      "args": ["/path/to/mcp-thai-text/server.py"]
    }
  }
}
```

`render_text_png` needs a Thai-capable font (Kanit, Sarabun, Noto Sans Thai). It checks common install locations and takes an explicit `font_path` otherwise.

## Test

```bash
python test_client.py
```

Spawns the server over stdio as a real MCP client, lists the tools, and exercises all three, including writing an actual PNG and asserting it exists.

## Example

`wrap_caption_lines` on a sentence with `max_chars: 14`:

```
เพราะภาษาไทย
ไม่มีช่องว่าง
ระหว่างคำการ
ตัดบรรทัดจึง
ต้องตัด
ที่ขอบเขตของคำ
จริง
```

Every break lands on a word boundary, no line starts with an enclitic, and no line ends on a lead-in.

## Related

- [thai-text-render](https://github.com/anthonychkwn/thai-text-render): the standalone rendering library this server's `render_text_png` is built on, with a visual before/after of the tone-mark bug.
- [thai-talkinghead-autocut](https://github.com/anthonychkwn/thai-talkinghead-autocut): the video pipeline where these rules were battle-tested against real footage.

## License

MIT
