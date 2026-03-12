#!/usr/bin/env python3
"""
render.py — Render conversation turns JSON as a Claude Desktop-styled HTML widget.

Usage:
    python3 render.py \
        --input /path/to/turns.json \
        --title "Demo Title" \
        [--description "subtitle text"] \
        [--output /path/to/output.html] \
        [--embed-only]
"""

import argparse
import html
import json
import re
from pathlib import Path


# ── Minimal Markdown → HTML converter ────────────────────────────────────────

_FENCED_CODE_RE = re.compile(
    r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL
)


def _convert_fenced_code(md: str) -> str:
    """Replace fenced code blocks with HTML before other processing."""
    def _repl(m):
        lang = m.group(1)
        code = html.escape(m.group(2).rstrip("\n"))
        lang_attr = f' class="language-{lang}"' if lang else ""
        return f'<pre class="cdw-code-block"><code{lang_attr}>{code}</code></pre>'
    return _FENCED_CODE_RE.sub(_repl, md)


def _convert_inline(text: str) -> str:
    """Convert inline markdown: bold, italic, inline code."""
    # Inline code (must come first to protect contents)
    text = re.sub(r"`([^`]+)`", r'<code class="cdw-inline-code">\1</code>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def markdown_to_html(text: str) -> str:
    """Convert markdown text to HTML for display in the demo widget."""
    # Step 1: fenced code blocks (extract before line processing)
    parts = []
    last_end = 0
    for m in _FENCED_CODE_RE.finditer(text):
        # Process text before the code block
        before = text[last_end:m.start()]
        parts.append(("text", before))
        # Code block
        lang = m.group(1)
        code = html.escape(m.group(2).rstrip("\n"))
        lang_attr = f' class="language-{lang}"' if lang else ""
        parts.append(("code", f'<pre class="cdw-code-block"><code{lang_attr}>{code}</code></pre>'))
        last_end = m.end()
    # Remaining text after last code block
    parts.append(("text", text[last_end:]))

    result = []
    for kind, content in parts:
        if kind == "code":
            result.append(content)
        else:
            result.append(_process_text_block(content))

    return "\n".join(result)


def _process_text_block(text: str) -> str:
    """Process a text block (non-code) into HTML."""
    lines = text.split("\n")
    out = []
    in_list = None  # "ul" or "ol"
    paragraph_lines = []

    def flush_paragraph():
        if paragraph_lines:
            p_text = "<br>\n".join(_convert_inline(l) for l in paragraph_lines)
            out.append(f"<p>{p_text}</p>")
            paragraph_lines.clear()

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    for line in lines:
        stripped = line.strip()

        # Empty line = paragraph break
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            flush_paragraph()
            flush_list()
            out.append('<hr class="cdw-hr">')
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            h_text = _convert_inline(heading_match.group(2))
            out.append(f"<h{level} class=\"cdw-heading\">{h_text}</h{level}>")
            continue

        # Unordered list
        ul_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if ul_match:
            flush_paragraph()
            if in_list != "ul":
                flush_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"  <li>{_convert_inline(ul_match.group(1))}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            flush_paragraph()
            if in_list != "ol":
                flush_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"  <li>{_convert_inline(ol_match.group(1))}</li>")
            continue

        # Regular text line
        flush_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(out)


# ── Claude avatar SVG ────────────────────────────────────────────────────────

CLAUDE_AVATAR_SVG = '''<svg class="cdw-avatar" width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg">
  <circle cx="14" cy="14" r="14" fill="#DA7756"/>
  <path d="M10.5 18.5L14 9.5L17.5 18.5M11.5 16H16.5" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>'''

# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """
.claude-demo-widget {
  --cdw-bg: #FAF9F6;
  --cdw-bg-user: #F0EFEB;
  --cdw-text: #1A1A1A;
  --cdw-text-secondary: #5D5D5D;
  --cdw-text-muted: #8B8B8B;
  --cdw-accent: #DA7756;
  --cdw-code-bg: #1E1E1E;
  --cdw-code-text: #D4D4D4;
  --cdw-border: #E8E6E1;
  --cdw-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --cdw-font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  --cdw-max-width: 720px;

  font-family: var(--cdw-font);
  color: var(--cdw-text);
  background: var(--cdw-bg);
  max-width: var(--cdw-max-width);
  margin: 0 auto;
  padding: 0 24px;
  overflow: hidden;
  line-height: 1.6;
  font-size: 15px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.claude-demo-widget *,
.claude-demo-widget *::before,
.claude-demo-widget *::after {
  box-sizing: border-box;
}

/* Header */
.claude-demo-widget .cdw-header {
  padding: 28px 0 20px;
  border-bottom: 1px solid var(--cdw-border);
  margin-bottom: 8px;
}
.claude-demo-widget .cdw-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--cdw-text);
  margin: 0;
}
.claude-demo-widget .cdw-description {
  font-size: 14px;
  color: var(--cdw-text-muted);
  margin: 6px 0 0;
}

/* Conversation container */
.claude-demo-widget .cdw-conversation {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Individual turns */
.claude-demo-widget .cdw-turn {
  padding: 20px 0;
}
.claude-demo-widget .cdw-turn + .cdw-turn {
  border-top: 1px solid var(--cdw-border);
}

/* User turn — plain text, left-aligned, subtle bg like Claude Desktop */
.claude-demo-widget .cdw-turn-user {
  background: var(--cdw-bg-user);
  margin: 0 -24px;
  padding: 20px 24px;
}
.claude-demo-widget .cdw-turn-user .cdw-content p {
  margin: 0;
}
.claude-demo-widget .cdw-turn-user .cdw-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--cdw-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}

/* Assistant turn — left-aligned with avatar */
.claude-demo-widget .cdw-turn-assistant {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.claude-demo-widget .cdw-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}
.claude-demo-widget .cdw-turn-assistant .cdw-content {
  min-width: 0;
  flex: 1;
}

/* Content typography */
.claude-demo-widget .cdw-content p {
  margin: 0 0 12px;
}
.claude-demo-widget .cdw-content p:last-child {
  margin-bottom: 0;
}
.claude-demo-widget .cdw-content h1,
.claude-demo-widget .cdw-content h2,
.claude-demo-widget .cdw-content h3,
.claude-demo-widget .cdw-content h4,
.claude-demo-widget .cdw-content h5,
.claude-demo-widget .cdw-content h6 {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.3;
}
.claude-demo-widget .cdw-content h1 { font-size: 20px; }
.claude-demo-widget .cdw-content h2 { font-size: 18px; }
.claude-demo-widget .cdw-content h3 { font-size: 16px; }

.claude-demo-widget .cdw-content ul,
.claude-demo-widget .cdw-content ol {
  margin: 8px 0;
  padding-left: 24px;
}
.claude-demo-widget .cdw-content li {
  margin: 4px 0;
}

.claude-demo-widget .cdw-content strong {
  font-weight: 600;
}

.claude-demo-widget .cdw-hr {
  border: none;
  border-top: 1px solid var(--cdw-border);
  margin: 16px 0;
}

/* Code blocks */
.claude-demo-widget .cdw-code-block {
  background: var(--cdw-code-bg);
  color: var(--cdw-code-text);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  font-family: var(--cdw-font-mono);
  font-size: 13px;
  line-height: 1.5;
  margin: 12px 0;
  white-space: pre;
}
.claude-demo-widget .cdw-code-block code {
  font-family: inherit;
  font-size: inherit;
  background: none;
  padding: 0;
}

/* Inline code */
.claude-demo-widget .cdw-inline-code {
  background: var(--cdw-bg-user);
  border: 1px solid var(--cdw-border);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: var(--cdw-font-mono);
  font-size: 0.88em;
}

/* Footer */
.claude-demo-widget .cdw-footer {
  padding: 16px 0;
  border-top: 1px solid var(--cdw-border);
  margin-top: 8px;
  text-align: center;
}
.claude-demo-widget .cdw-branding {
  font-size: 12px;
  color: var(--cdw-text-muted);
  letter-spacing: 0.02em;
}

/* Responsive */
@media (max-width: 600px) {
  .claude-demo-widget {
    padding: 0 16px;
  }
  .claude-demo-widget .cdw-turn-user {
    margin: 0 -16px;
    padding: 16px;
  }
  .claude-demo-widget .cdw-turn-assistant {
    gap: 10px;
  }
  .claude-demo-widget .cdw-code-block {
    font-size: 12px;
    padding: 12px;
    border-radius: 6px;
  }
}
"""

# ── HTML rendering ───────────────────────────────────────────────────────────


def render_turn(turn: dict) -> str:
    """Render a single conversation turn as HTML."""
    role = turn["role"]
    text = turn["text"]

    if role == "user":
        content_html = markdown_to_html(text)
        return f'''<div class="cdw-turn cdw-turn-user">
  <div class="cdw-label">You</div>
  <div class="cdw-content">{content_html}</div>
</div>'''

    else:  # assistant
        content_html = markdown_to_html(text)
        return f'''<div class="cdw-turn cdw-turn-assistant">
  {CLAUDE_AVATAR_SVG}
  <div class="cdw-content">{content_html}</div>
</div>'''


def render_widget(turns: list, title: str, description: str = "") -> str:
    """Render the full widget div with scoped CSS."""
    turns_html = "\n".join(render_turn(t) for t in turns)

    desc_html = ""
    if description:
        desc_html = f'\n  <div class="cdw-description">{html.escape(description)}</div>'

    return f'''<div class="claude-demo-widget">
<style>{CSS}</style>

<div class="cdw-header">
  <div class="cdw-title">{html.escape(title)}</div>{desc_html}
</div>

<div class="cdw-conversation">
{turns_html}
</div>

<div class="cdw-footer">
  <span class="cdw-branding">Powered by Claude</span>
</div>
</div>'''


STANDALONE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      background: #FAF9F6;
      display: flex;
      justify-content: center;
      padding: 40px 20px;
      min-height: 100vh;
    }}
  </style>
</head>
<body>
{widget}
</body>
</html>"""


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(
        description="Render conversation turns as a Claude Desktop-styled HTML widget."
    )
    p.add_argument("--input", required=True, help="Path to conversation turns JSON")
    p.add_argument("--title", default="Conversation Demo",
                   help="Demo title displayed at the top")
    p.add_argument("--description", default="",
                   help="Subtitle/description text")
    p.add_argument("--output", default="demo.html",
                   help="Where to write the HTML file")
    p.add_argument("--embed-only", action="store_true",
                   help="Output just the embeddable div (no DOCTYPE wrapper)")
    args = p.parse_args()

    turns = json.loads(Path(args.input).read_text())
    widget_html = render_widget(turns, args.title, args.description)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.embed_only:
        out_path.write_text(widget_html)
        print(f"Wrote embed snippet: {out_path}")
    else:
        standalone = STANDALONE_TEMPLATE.format(
            title=html.escape(args.title),
            widget=widget_html,
        )
        out_path.write_text(standalone)
        print(f"Wrote standalone HTML: {out_path}")

        # Also write the embed-only snippet
        embed_path = out_path.with_suffix(".embed.html")
        embed_path.write_text(widget_html)
        print(f"Wrote embed snippet:  {embed_path}")

    print(f"Turns: {len(turns)}")


if __name__ == "__main__":
    main()
