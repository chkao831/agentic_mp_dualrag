# Requirements — Fed MPR agentic RAG

This document is the **authoritative checklist** for functional and non-functional requirements. Architecture decisions under [`doc/adr/`](adr/README.md) map to these IDs in **Related requirements** for traceability.

**Scope note (current milestone):** The **vector RAG** path is in scope for the running agent. The **RDF / SPARQL graph skill** is **deferred** (see [ADR-0004](adr/0004-defer-rdf-graph-skill.md)); related requirements remain valid for the full target architecture and for offline pipeline work.

---

## Functional requirements

| ID | Requirement |
|----|----------------|
| **FR-01** | **HTML ingestion:** Scrape MPR content from Federal Reserve HTML pages (e.g. Summary, Part 1, Part 2), using structural tags (`p`, `h2`, `h3`, `table`, etc.) to preserve semantic boundaries; exclude non-content chrome where practical. |
| **FR-02** | **Vector retrieval index:** Build and query a local semantic index over ingested MPR chunks, with **source URL** stored as metadata for every chunk. |
| **FR-03** | **Live URL citations:** Every grounded claim in the assistant’s answer must be supportable with a **clickable Markdown link** to the **exact federalreserve.gov URL** returned from retrieval (no fabricated URLs). |
| **FR-04** | **Autonomous tool execution:** When the model emits `tool_use`, the backend SHALL invoke **allowlisted** local Python entrypoints via **`subprocess`**, append structured tool output to the conversation, and continue the loop until completion. |
| **FR-05** | **Transparent reasoning (UI):** The client SHALL surface **intermediate steps** (e.g. tool name, arguments, truncated tool output / query text) while the agent runs. *For the graph skill (when enabled): include SPARQL visibility; until then, vector tool steps satisfy this ID for the active path.* |
| **FR-06** | **Dual-ingestion (target architecture):** The offline pipeline SHALL be capable of producing **both** vector embeddings (FR-02) **and** RDF triples with **provenance** tied to the same live Fed URLs. *Agent exposure of the graph via a SPARQL skill is deferred per ADR-0004.* |
| **FR-07** | **Configuration:** Target MPR URLs SHALL be listed in a maintained config (e.g. `data/target_urls.json`) for repeatable scraping. |

---

## Non-functional requirements

| ID | Requirement |
|----|----------------|
| **NFR-01** | **Compute efficiency:** Prefer **HTML-based ingestion** over PDF parsing for the primary offline path to reduce CPU, IO, and pipeline duration for comparable text/table coverage. |
| **NFR-02** | **Trust & verification:** Citations MUST reference **primary** Fed URLs so users can verify content at the source; the system design SHALL not rely on undocumented local mirrors for citation provenance. |
| **NFR-03** | **Maintainability:** Agent orchestration SHALL use the **Anthropic Python SDK** with an **explicit** control loop (no mandatory agent framework) so behavior is easy to debug and evolve. |
| **NFR-04** | **Security:** Tool execution SHALL be **restricted** to known scripts under `skills/` with validated arguments—no arbitrary shell execution driven by model output. |
| **NFR-05** | **Deployability / local-first:** Core persistence (intermediate JSON, Chroma, optional Oxigraph) SHALL be configurable under `data/` for local development and reproducible runs. |
| **NFR-06** | **Observability (minimum):** Tool boundaries and outcomes SHALL be observable enough to debug retrieval and citation failures (logs, SSE status events, or equivalent). |

---

## Traceability

- Use the **Related requirements** field in each ADR to list IDs (e.g. `FR-01`, `NFR-03`).
- For portfolio-level reviews, a spreadsheet or matrix can copy this table and add columns per ADR (contributes / satisfies / partial).

---

## Related artifacts

- [`README.md`](../README.md) — setup and runbook
- [`pyproject.toml`](../pyproject.toml) — Python dependency names (unpinned)
- [`uv.lock`](../uv.lock) — pinned versions (commit to Git)
- [`doc/adr/README.md`](adr/README.md) — ADR index and template reference
