# ADR-0004: Defer RDF graph skill from the active agent

## Issue

The **target** architecture includes **dual-RAG**: vector search plus an RDF graph (Oxigraph) and a **SPARQL** skill for relational queries. Shipping both simultaneously expands ontology work, extraction quality risk, model prompt complexity, and test surface. We must decide **now** whether the **runtime agent** exposes the graph skill in the first delivery, or whether we **sequence** work behind a stable vector-only experience.

## Decision

**Defer** registration of the `query_macro_graph` skill from the live agent:

- Omit it from `ALLOWED_SCRIPTS` and `load_skill_tool_defs()` in `backend/agent.py`.
- Retain `skills/query_macro_graph/` (scripts, ontology notes, `DEFERRED.md`) for a later milestone.
- Treat `data_pipeline/build_rdf_graph.py` as **non-blocking** for the vector-only chat path.

## Status

Approved

## Group

Application; Data (delivery sequencing)

## Assumptions

- **Vector RAG** can satisfy most information-seeking questions for MPR text with **FR-03** citations in the first release.
- The RDF pipeline is **immature** (extraction, schema, evaluation); exposing SPARQL prematurely would increase **empty-result** and **hallucinated relationship** risk.
- Stakeholders accept **temporary** suspension of **graph-mediated** transparency (**FR-05** partial: vector tool steps only) until GraphRAG meets exit criteria.

## Constraints

- **FR-06** (dual-ingestion target) remains valid for **offline** design; only **agent-facing** graph query is deferred.
- Re-enabling the skill requires a **new ADR** or supersession note with acceptance tests (triple coverage, SPARQL smoke suite).

## Positions

1. **Defer graph skill; ship vector-only agent (selected).**
2. **Ship both:** Vector + SPARQL tools day one—higher integration risk and weaker graph data quality.
3. **Remove graph artifacts entirely:** Clean tree but loses scaffold investment and delays future dual-RAG.
4. **Graph-only:** Contradicts current text-heavy user questions and existing Chroma investment.

## Argument

Sequencing reduces **time-to-trustworthy RAG** by focusing on scrape → chunk → embed → cite (**FR-01, FR-02, FR-03**). A weak graph would **undermine NFR-02** and confuse users with noisy SPARQL. Keeping the folder preserves **option value** for **FR-06** without lying to the model about available capabilities. Full removal would waste prior design and complicate revival.

## Implications

- **FR-05** is **partially** satisfied: UI shows vector tool activity; SPARQL visibility waits on re-enablement.
- **FR-06** implementation is **split**: vector path production-ready first; RDF build script may evolve in parallel without agent binding.
- Future work: ontology stabilization, evaluation harness, and ADR for “Enable `query_macro_graph`.”

## Related decisions

- [ADR-0002](0002-provenance-through-live-source-urls.md) — Graph provenance must align with live URLs when enabled.
- [ADR-0003](0003-agent-orchestration-via-anthropic-api-and-subprocess-skills.md) — Allowlist must be extended when the skill returns.

## Related requirements

- **FR-05** — Transparent reasoning (SPARQL portion deferred; vector path active).
- **FR-06** — Dual-ingestion: **offline** RDF may continue; **agent** graph query deferred.
- **NFR-03** — Simpler agent surface aids maintainability in phase 1.

## Related artifacts

- `skills/query_macro_graph/DEFERRED.md`
- `skills/query_macro_graph/run_sparql.py`, `ontology_ref.md`
- `data_pipeline/build_rdf_graph.py`
- [`doc/requirements.md`](../requirements.md)

## Related principles

- **Incremental delivery** with explicit scope boundaries (informal product principle).

## Notes

- When re-enabling, update **Related requirements** in this ADR’s successor to restore full **FR-05** / **FR-06** agent coverage.
