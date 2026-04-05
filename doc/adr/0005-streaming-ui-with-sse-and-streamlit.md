# ADR-0005: Streaming UI with SSE and Streamlit

## Issue

Users need to see **what the agent is doing** (tool choice, parameters, partial outputs) while a response is generated, not only the final narrative. We must choose a **client–server streaming pattern** and a **UI stack** compatible with Python skill execution and FastAPI **now**, without overbuilding a SPA framework.

## Decision

- Backend: expose **`POST /chat/stream`** on FastAPI using **Server-Sent Events (SSE)**—`event: status` for tool and step metadata, `event: token` for assistant text segments (currently aligned to **post-turn** text chunks from the agent loop).
- Frontend: **Streamlit** chat UI that consumes the SSE stream over HTTP (e.g. `httpx` streaming) and renders intermediate steps in **`st.status`** (collapsible), with final assistant text rendered as **Markdown** (including citation links).

## Status

Approved

## Group

Presentation; Integration (HTTP streaming)

## Assumptions

- Users run UI and API in a **trusted local** or low-threat environment initially; **authn/z** and strict CORS are follow-ons.
- **SSE** over HTTP is sufficient for server→client push of status + text; bidirectional WebSockets are unnecessary for read-only observation.
- Streamlit’s **rerun** model is acceptable; chat flow uses **session state** to avoid duplicate messages.

## Constraints

- Long-running streams need **client timeouts** configured appropriately on `httpx`/Streamlit side.
- Fine-grained **token** streaming from Anthropic is **not** yet mapped 1:1 to SSE events; UX may show text in **larger** chunks until a future change.

## Positions

1. **SSE + Streamlit (selected).**
2. **WebSocket + React/Vue SPA:** Maximum UI flexibility; higher build and ops cost for this research codebase.
3. **Polling REST:** Simple but poor latency and noisy server load for “live” steps.
4. **Server-rendered Jinja + HTMX:** Viable; team standard here is Python data apps → Streamlit.

## Argument

SSE is **simple to debug** (curl, browser devtools) and maps cleanly to **status** vs **content** channels, supporting **FR-05** and **NFR-06** visibility. Streamlit delivers **Markdown** rendering for **FR-03** links with minimal front-end code. WebSockets and custom SPAs are **deferred** until productization demands richer interaction.

## Implications

- May add **Anthropic streaming** API support later to shrink `token` event granularity.
- Production deployment requires **CORS**, **auth**, and possibly **reverse-proxy** SSE buffering configuration (e.g. nginx).
- **FR-05** for SPARQL text in UI awaits graph skill re-enablement (**ADR-0004**); status events already carry tool names and previews.

## Related decisions

- [ADR-0003](0003-agent-orchestration-via-anthropic-api-and-subprocess-skills.md) — Produces tool events to surface.
- [ADR-0004](0004-defer-rdf-graph-skill.md) — Limits which tools appear in status until GraphRAG ships.

## Related requirements

- **FR-05** — Transparent reasoning in the UI (tool steps; SPARQL when graph skill is on).
- **FR-03** — Markdown hyperlinks in final assistant content.
- **NFR-06** — Observable intermediate steps via SSE status events.

## Related artifacts

- `backend/main.py` (SSE endpoint)
- `frontend/app.py`
- [`doc/requirements.md`](../requirements.md)

## Related principles

- **Progressive disclosure** of technical detail (`st.status`) for non-expert users (informal UX principle).

## Notes

- If Streamlit fragments or async patterns evolve, revisit single-request SSE consumption for very long generations.
