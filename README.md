# agentic_mp_dualrag

Agentic chat over Federal Reserve **Monetary Policy Report (MPR)** content using **HTML-derived chunks**, **ChromaDB** semantic search, and **live federalreserve.gov URLs** for citations. A second pipeline branch (RDF / Oxigraph / SPARQL skill) is prepared but **not** exposed to the agent yet; see `doc/adr/0004-defer-rdf-graph-skill.md`.

**Functional and non-functional requirements:** [`doc/requirements.md`](doc/requirements.md) (**FR-xx**, **NFR-xx**). **Architecture decisions:** [`doc/adr/`](doc/adr/README.md) (Tyree & Akerman template).

**Layout:** Single project at this repo root — `pyproject.toml`, `uv.lock`, `backend/`, `data_pipeline/`, `frontend/`, `skills/`, `doc/`.

**Dependencies:** Package names in `pyproject.toml` are **unversioned**; **`uv.lock`** pins what `uv sync` installs. To add a library, use **`uv add <package>`** (updates TOML + lock + venv). To refresh the lock after hand-editing `pyproject.toml`, run **`uv lock`**.

---

## Runtime prerequisites

| Item | Notes |
|------|--------|
| **[uv](https://docs.astral.sh/uv/getting-started/installation/)** | Creates `.venv`, installs from `uv.lock`. |
| **Python** | 3.10+ per `requires-python` in `pyproject.toml`. |
| **OS** | macOS ARM64 supported; Linux should work for Chroma, pyoxigraph, ONNXRuntime where wheels exist. |
| **Network** | `uv sync`, scraping, Anthropic API, first-time embedding downloads. |
| **Disk** | `.venv/`, `data/chroma_db/`, optional `data/oxigraph_db/`. |

**Install `uv`** (if `command not found: uv`):

- **macOS (Homebrew):** `brew install uv`
- **Other platforms:** [Astral installation guide](https://docs.astral.sh/uv/getting-started/installation/) (e.g. standalone installer, `pipx`, `pip install uv`)

Then run `uv --version` to confirm it is on your `PATH`.

---

## Dependencies vs secrets

| What | Where |
|------|--------|
| **Libraries** | Names in [`pyproject.toml`](pyproject.toml); **exact versions** in [`uv.lock`](uv.lock) — commit the lockfile. |
| **API keys** | **Never** in TOML. Use env vars or a gitignored `.env` + `uv run --env-file .env`. |

There is no `pip install -r requirements.txt`. Use **`uv sync`** to install from the lockfile, and **`uv add <name>`** when you need a new dependency (preferred over editing TOML by hand).

---

## Credentials

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY (and optionally HUGGINGFACE_HUB_TOKEN)
```

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (agent / optional RDF script) | [Anthropic Console](https://console.anthropic.com/) |
| `HUGGINGFACE_HUB_TOKEN` | Optional | HF-gated models only |

**Security:** `.env` is gitignored. Tools run only allowlisted scripts under `skills/`.

---

## Setup

```bash
cd agentic_mp_dualrag
uv sync
uv run python -c "from backend.main import app; print(app.title)"
```

---

## Data pipeline (vector RAG)

1. Maintain **`data/target_urls.json`**: list each semiannual report under **`releases`** with an **`edition`** (e.g. `2025-06`) and ordered **`sections`** (`id`, `title`, `path` or full `url`). See `_meta` in that file for the Fed [MPR catalog](https://www.federalreserve.gov/monetarypolicy/mpr_default.htm). Use **`scrape": false`** on a whole release or section to skip it. Skip `*-accessible.htm` pages unless you want duplicate accessible-format text. The default **`target_urls.json`** omits **Data Notes** and **Abbreviations**; add those sections only if you want them in the index.
2. Scrape → JSON: `uv run python data_pipeline/scrape_html_to_json.py`
3. Build Chroma: `uv run python data_pipeline/build_vector_db.py`

Optional: `data_pipeline/build_rdf_graph.py` (not required for the vector-only agent).

---

## Run the application

```bash
cd agentic_mp_dualrag
uv run --env-file .env python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
uv run --env-file .env streamlit run frontend/app.py
```

Set `MPR_BACKEND_URL` if the API is not on `http://127.0.0.1:8000`.

**`http://localhost:8000/`** serves a small info page (not the chat). Use **`http://localhost:8000/docs`** for Swagger, **`/health`** for a JSON ping, or Streamlit for chatting.

`backend/agent.py` also calls `load_dotenv(.env)` when you run **`python`** without `--env-file` (optional fallback).

---

## Project layout

| Path | Role |
|------|------|
| `pyproject.toml` | Dependency **names** (no `>=` pins) |
| `uv.lock` | Pinned versions for reproducible installs |
| `data/` | URLs config, bronze JSON, Chroma, Oxigraph |
| `data_pipeline/` | Scrape, embed, optional RDF |
| `backend/` | FastAPI + Anthropic loop + SSE |
| `skills/` | Subprocess tools (`search_mpr_vector`, deferred graph skill) |
| `frontend/app.py` | Streamlit UI |
| `doc/` | Requirements + ADRs |

---

## Compliance

Respect [federalreserve.gov](https://www.federalreserve.gov) terms of use, `robots.txt`, and reasonable rate limits.
