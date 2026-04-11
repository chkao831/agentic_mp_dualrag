"""Render `doc/TECHNICAL.md` in Streamlit with Mermaid diagrams (CDN)."""
from __future__ import annotations

import html
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def render_markdown_with_mermaid(markdown_path: Path) -> None:
    text = markdown_path.read_text(encoding="utf-8")
    pos = 0
    for m in _MERMAID_BLOCK.finditer(text):
        before = text[pos : m.start()]
        if before.strip():
            st.markdown(before)
        _render_mermaid_block(m.group(1).strip())
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        st.markdown(tail)


def _render_mermaid_block(diagram: str) -> None:
    safe = html.escape(diagram, quote=True)
    # Dark theme to match Streamlit default
    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>body{{margin:0;padding:8px 12px;background:#0e1117;color:#fafafa;font-family:system-ui,sans-serif;}}</style>
</head><body>
<div class="mermaid">{safe}</div>
<script>
mermaid.initialize({{startOnLoad:true,theme:"dark",securityLevel:"loose"}});
</script>
</body></html>"""
    components.html(page, height=480, scrolling=True)
