"""
Streamlit chat UI: consumes FastAPI SSE and shows tool steps in st.status.

Run:
  uv run streamlit run frontend/app.py
Backend:
  uv run python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

import httpx
import streamlit as st

BACKEND = os.environ.get("MPR_BACKEND_URL", "http://127.0.0.1:8000")

_MD_LINK_URL = re.compile(r"!?\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL = re.compile(r"https?://[^\s\)`'\"<>]+")
_IMAGE_EXT = re.compile(r"\.(svg|png|jpe?g|gif|webp)(\?[^#]*)?(#.*)?$", re.IGNORECASE)

# GFM-style table: header row with pipes + separator row with --- (nudge when no markdown citation).
_MD_TABLE_SEP = re.compile(r"-{3,}")


def _looks_like_gfm_table(s: str) -> bool:
    for para in re.split(r"\n{2,}", s):
        lines = [ln.rstrip() for ln in para.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        first, sep = lines[0].strip(), lines[1].strip()
        if "|" in first and "|" in sep and _MD_TABLE_SEP.search(sep):
            return True
    return False


def _table_missing_markdown_http_link(md: str) -> bool:
    if not _looks_like_gfm_table(md):
        return False
    return not re.search(r"\]\(https?://[^\s\)]+\)", md)


# Streamlit Markdown uses KaTeX: `$...$` is inline math (spaces collapse). Escape `$` → `\$` for currency.
_KATEX_DOLLAR = re.compile(r"(?<!\\)\$")
# Unicode asterisk lookalikes break `**bold**` parsing.
_AST = str.maketrans(
    {
        "\u2217": "*",
        "\u204e": "*",
        "\uff0a": "*",
        "\ufe61": "*",
        "\u066d": "*",
    }
)


def normalize_assistant_markdown(text: str) -> str:
    """Prepare text for st.markdown: unicode * → ASCII, escape $ so KaTeX does not eat currency."""
    t = text.translate(_AST)
    return _KATEX_DOLLAR.sub(r"\\$", t)


def extract_http_urls(text: str) -> list[str]:
    """Collect http(s) URLs from markdown links and bare text; preserve order, dedupe."""
    raw: list[str] = []
    for m in _MD_LINK_URL.finditer(text):
        raw.append(m.group(1).rstrip(").,;]"))
    for m in _BARE_URL.finditer(text):
        raw.append(m.group(0).rstrip(").,;]"))
    out: list[str] = []
    seen: set[str] = set()
    for u in raw:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _url_label(url: str, max_len: int = 72) -> str:
    try:
        p = urlparse(url)
        label = f"{p.netloc}{p.path or ''}" or url
        if p.query:
            label = f"{label}?{p.query[:24]}"
    except Exception:
        label = url
    if len(label) > max_len:
        return label[: max_len - 1] + "…"
    return label


def _is_direct_image_url(url: str) -> bool:
    try:
        path = urlparse(url).path
    except Exception:
        return False
    return bool(_IMAGE_EXT.search(path or ""))


def _image_urls_for_st_image(markdown_text: str, urls: list[str]) -> list[str]:
    """URLs to pass to st.image — skip any already used in ![...](url) to avoid double render."""
    out: list[str] = []
    for u in urls:
        if not _is_direct_image_url(u):
            continue
        if re.search(r"!\[[^\]]*\]\(" + re.escape(u) + r"\)", markdown_text):
            continue
        out.append(u)
    return out


_DEBUG_CHAT = os.environ.get("MPR_DEBUG_CHAT", "").strip().lower() in ("1", "true", "yes")


def render_assistant_reply(markdown_text: str) -> None:
    md = normalize_assistant_markdown(markdown_text)
    if _DEBUG_CHAT:
        with st.expander("Debug (`MPR_DEBUG_CHAT=1`): raw text from API", expanded=False):
            st.code(markdown_text, language=None)
            odd = sorted({c for c in markdown_text if ord(c) > 127}, key=ord)
            if odd:
                st.caption(
                    "Non-ASCII: "
                    + ", ".join(f"U+{ord(c):04X}×{markdown_text.count(c)}" for c in odd)
                )
            else:
                st.caption("Non-ASCII: (none)")
            if md != markdown_text:
                st.caption("After `normalize_assistant_markdown`:")
                st.code(md, language=None)
    st.markdown(md)
    if _table_missing_markdown_http_link(md):
        st.caption(
            "This reply includes a table but no `[label](https://…)` link. "
            "Fed figures should cite the exact Source URL from retrieval directly under the table."
        )
    urls = extract_http_urls(md)
    if not urls:
        return

    # ad5a9b1 added Sources links only; Markdown often does not embed remote SVGs reliably.
    # st.image fetches the URL when the model pasted a bare image URL (or forgot ![](...) syntax).
    img_urls = _image_urls_for_st_image(md, urls)
    if img_urls:
        with st.expander("Figures (image URLs from this reply)", expanded=False):
            for u in img_urls:
                try:
                    st.image(u, caption=_url_label(u), use_container_width=True)
                except Exception as ex:
                    st.caption(f"Could not load `{_url_label(u)}`: {ex}")

    with st.expander("Sources", expanded=False):
        lines = [f"{i + 1}. [{_url_label(u)}]({u})" for i, u in enumerate(urls)]
        st.markdown("\n".join(lines))


def stream_chat(message: str, model: str = "sonnet"):
    """Yields (kind, payload) where kind is 'status' | 'token'."""
    url = f"{BACKEND.rstrip('/')}/chat/stream"
    with httpx.stream(
        "POST",
        url,
        json={"message": message, "model": model},
        timeout=300.0,
    ) as resp:
        resp.raise_for_status()
        event_name = None
        for line in resp.iter_lines():
            if line is None:
                continue
            line = line.strip()
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                raw = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event_name == "status":
                    yield "status", data
                elif event_name == "token":
                    yield "token", data


st.set_page_config(page_title="Fed MPR Agent", layout="wide")
# Chat markdown: break long tokens/URLs; avoid `pre-wrap` here — it preserves single newlines inside
# paragraphs and can make Streamlit’s rendered Markdown look “striped” or oddly broken.
st.markdown(
    """
<style>
section[data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] {
    white-space: normal;
    overflow-wrap: break-word;
    word-break: break-word;
    overflow-x: auto;
}
</style>
""",
    unsafe_allow_html=True,
)
st.title("Federal Reserve MPR — Agentic Dual-RAG (skeleton)")

with st.sidebar:
    st.subheader("Model")
    _model_help = (
        "Backend default when unset: `ANTHROPIC_MODEL` in `.env` (`sonnet` or `haiku`), else Sonnet. "
        "This control overrides that for each chat request."
    )
    model_preset = st.radio(
        "Claude",
        options=["sonnet", "haiku"],
        format_func=lambda m: (
            "Sonnet 4 — stronger (default)" if m == "sonnet" else "Haiku 4.5 — lower cost"
        ),
        key="mpr_claude_model",
        help=_model_help,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for role, content in st.session_state.messages:
    with st.chat_message(role):
        if role == "assistant":
            render_assistant_reply(content)
        else:
            st.markdown(normalize_assistant_markdown(content))

prompt = st.chat_input("Ask about the Monetary Policy Report…")
if prompt:
    st.session_state.messages.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(normalize_assistant_markdown(prompt))

    with st.chat_message("assistant"):
        assistant_parts: list[str] = []
        status = st.status("Agent steps…", expanded=True)
        try:
            for kind, payload in stream_chat(prompt, model=model_preset):
                if kind == "status":
                    step = payload.get("step", "")
                    status.write(f"**{step}** — `{json.dumps(payload, indent=0)[:800]}`")
                elif kind == "token":
                    assistant_parts.append(payload.get("text", ""))
            status.update(label="Done", state="complete")
        except httpx.ConnectError as e:
            status.update(label="Error", state="error")
            st.error(
                f"Cannot reach the API at `{BACKEND}` (connection refused). "
                "Keep the FastAPI server running **in a separate terminal** while you use this app, then retry."
            )
            st.code(
                "uv run --env-file .env python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000",
                language="bash",
            )
            assistant_parts = [f"_(Request failed: {e})_"]
        except Exception as e:
            status.update(label="Error", state="error")
            st.error(str(e))
            assistant_parts = [f"_(Request failed: {e})_"]

        final_text = "".join(assistant_parts)
        render_assistant_reply(final_text)

    st.session_state.messages.append(("assistant", final_text))
