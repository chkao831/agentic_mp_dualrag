---
name: list_mpr_data_series
description: List chart data series (eco:DataSeries) from the Oxigraph MPR store — IRIs and labels for SPARQL discovery. Use after vector search; pair with query_macro_graph for exact values.
---

# Tool: `list_mpr_data_series`

Oxigraph **discovery** step: run a fixed SPARQL pattern (see `list_data_series.py`) over `eco:DataSeries` joined to `eco:ChartFigure` labels. Optional `--contains` substring filter.

## When to use

- You need **series IRIs** before writing ad hoc SPARQL.
- After **search_mpr_vector** narrows themes or figure names, call this with a short substring (e.g. `PCE`, `trimmed`).

**Important:** `series_label` is usually the **table column** name (often a **year**), not the economic measure name. **Measure names** (e.g. PCE inflation) usually appear in **`figure_label`**. Do not assume `CONTAINS` on the series column alone — filter `figure_label` or use IRIs from this listing.

## Orchestration (with other tools)

1. Broad / interpretive questions → **search_mpr_vector** first.
2. **list_mpr_data_series** with a substring from those hits.
3. **query_macro_graph** with SPARQL over observations (see `skills/query_macro_graph/SKILL.md`).
4. Cite **Source URL** from vector hits and **statedIn** / graph URLs; never invent links.

Do **not** use graph tools alone when the user has not narrowed which series or table.

## Output contract

First line: header `series_iri\tseries_label\tfigure_label`, then TSV rows.

**Vocabulary reference:** `skills/query_macro_graph/ontology_ref.md` (shared RDF model).
