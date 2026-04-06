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


def render_assistant_reply(markdown_text: str) -> None:
    st.markdown(markdown_text)
    urls = extract_http_urls(markdown_text)
    if not urls:
        return
    with st.expander("Sources", expanded=False):
        lines = [f"{i + 1}. [{_url_label(u)}]({u})" for i, u in enumerate(urls)]
        st.markdown("\n".join(lines))


def stream_chat(message: str):
    """Yields (kind, payload) where kind is 'status' | 'token'."""
    url = f"{BACKEND.rstrip('/')}/chat/stream"
    with httpx.stream(
        "POST",
        url,
        json={"message": message},
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
st.title("Federal Reserve MPR — Agentic Dual-RAG (skeleton)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for role, content in st.session_state.messages:
    with st.chat_message(role):
        if role == "assistant":
            render_assistant_reply(content)
        else:
            st.markdown(content)

prompt = st.chat_input("Ask about the Monetary Policy Report…")
if prompt:
    st.session_state.messages.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        assistant_parts: list[str] = []
        status = st.status("Agent steps…", expanded=True)
        try:
            for kind, payload in stream_chat(prompt):
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
