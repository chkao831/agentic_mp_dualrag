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

import httpx
import streamlit as st

BACKEND = os.environ.get("MPR_BACKEND_URL", "http://127.0.0.1:8000")


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
        except Exception as e:
            status.update(label="Error", state="error")
            st.error(str(e))
            assistant_parts = [f"_(Request failed: {e})_"]

        final_text = "".join(assistant_parts)
        st.markdown(final_text)

    st.session_state.messages.append(("assistant", final_text))
