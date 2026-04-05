# ADR-0001: Use HTML scraping for MPR ingestion

## Issue

We must choose a **primary ingestion representation** for Federal Reserve Monetary Policy Report (MPR) content before chunking and indexing. PDF is the traditional archival format; HTML is the native web publication form. The choice affects pipeline cost, time-to-index, semantic fidelity of tables and headings, and ongoing maintenance. This decision is required **now** because downstream components (bronze JSON schema, chunk boundaries, metadata) depend on it.

## Decision

Ingest MPR text and tables by **scraping HTML** from configured Fed URLs, extracting logical blocks aligned to tags such as `p`, `h2`, `h3`, and `table`, and persisting each block with its **page URL** into bronze JSON under `data/intermediate_json/`.

## Status

Approved

## Group

Data

## Assumptions

- MPR sections remain published as **machine-readable HTML** with reasonably stable DOM patterns around main content.
- The program may perform **polite, policy-compliant** HTTP retrieval (rate limits, terms of use, `robots.txt`).
- Team can maintain **selectors** when templates change; full automation of DOM drift detection is out of scope for the first milestone.
- PDF editions may still exist for human reading but are **not** the primary ingestion path for this system.

## Constraints

- Selectors in `data_pipeline/scrape_html_to_json.py` must be **updated** when the Fed changes layout; otherwise ingestion quality degrades.
- Ingestion must attach **canonical page URLs** per block to support citation requirements (see ADR-0002, FR-03).

## Positions

1. **HTML scraping (selected):** Parse structured HTML with BeautifulSoup (or equivalent), target main content regions, emit JSON blocks with `source_url`.
2. **PDF parsing:** Use PDF text/table extractors; higher compute and layout ambiguity; harder table fidelity without bespoke tuning per report.
3. **Hybrid:** HTML for body text, PDF only for select tables—adds dual pipelines and reconciliation complexity.
4. **Manual / CMS upload:** Operators paste or upload content—reduces automation and repeatability for recurring MPR releases.

## Argument

HTML aligns with **publisher structure** (headings, paragraphs, tables) at lower **CPU and wall-clock** cost than robust PDF extraction for comparable coverage (**NFR-01**). It directly supports **FR-01** (semantic boundaries) and pairs naturally with **per-block URLs** for provenance. PDF remains a fallback for edge cases but would dominate engineering time for table recovery. Hybrid and manual paths fail **time-to-market** and **repeatability** for recurring MPR cycles.

## Implications

- Requires **ongoing** maintenance of scrape targets in `data/target_urls.json` and content selectors.
- Suggests **smoke tests** or sample golden pages after each major Fed template change.
- Chunking and embedding scripts assume **JSON block** shape from this pipeline.
- PDF-specific tooling is **not** prioritized in `pyproject.toml` unless a future ADR reverses this.

## Related decisions

- [ADR-0002](0002-provenance-through-live-source-urls.md) — URLs attached at ingest feed citation metadata.
- [ADR-0004](0004-defer-rdf-graph-skill.md) — RDF branch may consume the same bronze JSON later.

## Related requirements

- **FR-01** — HTML ingestion with semantic boundaries.
- **FR-07** — Configurable target URL list.
- **NFR-01** — Compute efficiency vs PDF.

## Related artifacts

- `data_pipeline/scrape_html_to_json.py`
- `data/target_urls.json`
- `data/intermediate_json/` (bronze output)
- [`doc/requirements.md`](../requirements.md)

## Related principles

- **N/A** (no formal enterprise principle set recorded for this repository).

## Notes

- Fed MPR landing for URL discovery: `https://www.federalreserve.gov/monetarypolicy/mpr_default.htm`
- If HTML tables prove incomplete versus PDF in practice, reopen with a focused ADR on **table-only** supplementation rather than full PDF default.
