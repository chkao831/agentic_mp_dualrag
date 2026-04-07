"""
FastAPI app: POST /chat/stream emits SSE (status events + final text chunks).

Run from repo root:
  uv run python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Literal

from pydantic import BaseModel

from backend.agent import stream_agent_turns

app = FastAPI(title="MPR Agentic Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    # Overrides ANTHROPIC_MODEL for this request; backend default is haiku when unset.
    model: Literal["sonnet", "haiku"] | None = None


def sse_line(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_events(user_message: str, *, model: str | None = None) -> Iterator[str]:
    status_buffer: list[dict] = []

    def on_tool_event(ev: dict) -> None:
        status_buffer.append(ev)

    for chunk in stream_agent_turns(user_message, model=model, on_tool_event=on_tool_event):
        while status_buffer:
            ev = status_buffer.pop(0)
            yield sse_line("status", ev)
        yield sse_line("token", {"text": chunk})

    while status_buffer:
        ev = status_buffer.pop(0)
        yield sse_line("status", ev)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Browser-friendly landing; the chat UI is Streamlit (or use /docs to try the API)."""
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MPR Agent API</title></head>
<body style="font-family: system-ui; max-width: 40rem; margin: 2rem;">
  <h1>MPR Agentic Backend</h1>
  <p>This service has no web chat here. Use one of:</p>
  <ul>
    <li><a href="/docs">OpenAPI docs (Swagger)</a> — try <code>POST /chat/stream</code></li>
    <li><a href="/health"><code>GET /health</code></a> — liveness check</li>
    <li>Run <code>streamlit run frontend/app.py</code> for the chat UI (points at this API).</li>
  </ul>
</body></html>"""


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    return StreamingResponse(
        sse_events(body.message, model=body.model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    return {"ok": True}
