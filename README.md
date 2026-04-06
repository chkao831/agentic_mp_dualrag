# Fed MPR agentic chat

Streamlit UI + FastAPI backend. Claude calls allowlisted tools: **Chroma** semantic search (`search_mpr_vector`) and **Oxigraph** SPARQL (`query_macro_graph`, `list_mpr_data_series`). Answers should cite Fed URLs from tool output.

This repo is **runtime-only**: there is no ingest pipeline here. You need a populated **`data/chroma_db/`** and **`data/oxigraph_db/`** (and `ANTHROPIC_API_KEY`).

**Architecture and methodology:** [`doc/TECHNICAL.md`](doc/TECHNICAL.md) (Mermaid diagrams, vector vs graph skills, RDF model).

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+
- **`data/chroma_db/`** — Chroma collection `mpr_chunks` (see `skills/search_mpr_vector/query_chroma.py`)
- **`data/oxigraph_db/`** — Oxigraph store (see `skills/query_macro_graph/run_sparql.py`, `skills/list_mpr_data_series/list_data_series.py`)
- **`data/target_urls.json`** — which edition is indexed (shown in the agent system prompt)

---

## Credentials

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY
```

| Variable | Required | Notes |
|----------|----------|--------|
| `ANTHROPIC_API_KEY` | Yes | [Anthropic Console](https://console.anthropic.com/) |
| `ANTHROPIC_MODEL` | No | Default `sonnet` or `haiku` (Streamlit sidebar overrides per request). |
| `MPR_BACKEND_URL` | No | If the API is not `http://127.0.0.1:8000`. |
| `MPR_ASSISTANT_TODAY` | No | ISO date in the system prompt (else server date). |

`.env` is gitignored. Tools only run scripts under `skills/`.

---

## Run the chat app

```bash
cd agentic_mp_dualrag
uv sync
uv run --env-file .env python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
uv run --env-file .env streamlit run frontend/app.py
```

- Chat: Streamlit (default port 8501).  
- API: `http://127.0.0.1:8000/docs` (Swagger), `/health` ping.

---

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI + Anthropic loop + SSE |
| `frontend/app.py` | Chat UI |
| `skills/` | Subprocess tools (`search_mpr_vector`, `list_mpr_data_series`, `query_macro_graph`) |
| `data/` | `target_urls.json` + generated stores (see `.gitignore`) |
| `doc/TECHNICAL.md` | Architecture, Mermaid diagrams, vector vs graph methodology |

---

## Compliance

Respect [federalreserve.gov](https://www.federalreserve.gov) terms of use, `robots.txt`, and reasonable rate limits.
