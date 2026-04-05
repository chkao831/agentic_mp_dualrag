# ADR-0002: Provenance through live source URLs

## Issue

Users and stakeholders must **trust** answers about monetary policy reporting. Without verifiable sources, LLM outputs invite skepticism and compliance risk. We must decide **now** how citations are represented end-to-end: local mirrors, generic links, or **primary** government URLs embedded in retrieval metadata and answers.

## Decision

Use **live federalreserve.gov URLs** as the sole citation surface for user-visible provenance:

- Persist `source_url` on every scraped block in bronze JSON and in **Chroma** chunk metadata.
- Require skill output to include explicit `Source URL:` lines; the **system prompt** instructs the model to render them as **Markdown links** and **never** to invent URLs.

## Status

Approved

## Group

Data (provenance); Presentation (citation UX)

## Assumptions

- Fed-published URLs are **acceptable** citation targets for the intended audience and use case.
- Retrieval layer can always supply **metadata** alongside text; if metadata is dropped, citation quality fails—operations must preserve it.
- Short-term **link stability** is acceptable; long-term archival may later add timestamps or snapshots (optional, not blocking).

## Constraints

- Answers **must not** cite URLs absent from tool output (enforced by prompt + implementation discipline).
- **Deep links** may break if the Fed reorganizes paths; mitigation is to re-scrape and re-index per release, not to fabricate URLs.

## Positions

1. **Live Fed URLs only (selected):** Metadata carries official URLs; UI renders Markdown links.
2. **Hosted local mirror:** Serve copy of report from app storage; simplifies layout control but weakens “click to verify on .gov” narrative and may raise redistribution questions.
3. **Footnotes without URLs:** Academic-style references without hyperlinks—fails usability and **FR-03**.
4. **Generic link to MPR home:** Single landing page per answer—insufficient granularity for **exact** provenance.

## Argument

Live URLs maximize **verifiability** and align with **NFR-02** (trust & verification) and **FR-03** (clickable citations to the originating page). They avoid operating a **document mirror** as the citation authority. Generic or footnote-only approaches undercut accountability. Local mirrors remain a **future** option for offline demos but are not the default trust story.

## Implications

- **FR-03** becomes a cross-cutting acceptance criterion for retrieval and prompt design.
- GraphRAG (when enabled) should reuse the **same URL literals** in provenance triples for consistency across modalities.
- Product may later add **`retrieved_at`** or version tags in metadata for audit trails (new NFR/FR revision via requirements doc).

## Related decisions

- [ADR-0001](0001-use-html-scraping-for-mpr-ingestion.md) — Supplies per-block URLs at ingest.
- [ADR-0004](0004-defer-rdf-graph-skill.md) — Deferred graph should align provenance with this ADR.

## Related requirements

- **FR-03** — Live URL citations in answers.
- **FR-02** — Metadata must carry `source_url` for chunks.
- **FR-06** — Future RDF provenance should reference the same URLs.
- **NFR-02** — Trust & verification via primary sources.

## Related artifacts

- `data_pipeline/build_vector_db.py` (metadata)
- `skills/search_mpr_vector/query_chroma.py` (output contract)
- `backend/agent.py` (system prompt)
- [`doc/requirements.md`](../requirements.md)

## Related principles

- **Transparency / verifiability** for policy-domain Q&A (informal principle for this product).

## Notes

- Socialize with legal/compliance if the deployment context requires **archival** copies in addition to live links.
