---
name: query_macro_graph
description: Oxigraph RDF over the MPR store — SPARQL for numeric series/observations and list_data_series for discovery. Use after vector search when you need exact values.
---

# Graph tools — Fed MPR (Oxigraph)

Two tools work together with **search_mpr_vector**:

| Tool | Use when |
|------|----------|
| **search_mpr_vector** | First for vague or interpretive questions; discover what the report calls measures (PCE, CPI, figure titles, table wording). |
| **list_mpr_data_series** | You need **IRIs** before SPARQL — optional `--contains` substring (e.g. `PCE`, `inflation`). Returns TSV: `series_iri`, `series_label`, `figure_label`. **Important:** `series_label` is usually the **table column** name (often a **year** like `2020`, `2021`), not the measure name. **Measure names** (e.g. `PCE inflation`) appear in **`figure_label`**. Do not filter SPARQL with `CONTAINS(?series_label, "pce")` unless you know the column is named that way — join to the figure and filter `?figLabel` instead, or use IRIs from this listing. |
| **query_macro_graph** | You have a **specific SPARQL** query over `eco:` / `skos:` / `dct:` (see `ontology_ref.md`). Ideal for `eco:Observation` rows, periods, `eco:statedIn` provenance. |

## Orchestration (required)

1. For **broad** questions (*“trend in inflation”*, *“recent prices”*) → call **search_mpr_vector** first to see which **measures and figures** the MPR uses.
2. Then call **list_mpr_data_series** with a **short substring** from those hits (e.g. `PCE`, `trimmed`) to get exact **series IRIs and labels**.
3. Run **query_macro_graph** with SPARQL that filters on those labels or IRIs and returns **period + value + statedIn** URLs.
4. In the final answer, cite **Source URL** lines from vector hits and **IRIs/URLs** from graph results; never invent links.

Do **not** use graph tools alone when the user has not narrowed **which series or table** — empty or wrong results are likely.

## SPARQL reminders (read carefully)

- **Namespace (mandatory):** use **exactly**  
  `PREFIX eco: <https://example.org/macro#>`  
  Do **not** use `qudt.org`, `schema.org`, or any other `eco:` IRI — queries will return **no rows** or parse errors.
- **Observations:** `eco:Observation` with **`eco:period`**, **`eco:value`**, **`eco:inSeries`**, **`eco:statedIn`**  
  There is **no** `eco:refDate`, **no** `eco:observedProperty` — those are wrong for this store.
- **Series:** `eco:DataSeries` with `rdfs:label`, `eco:inFigure` → `eco:ChartFigure` with `rdfs:label` (figure title).
- **Projection / SEP tables:** the same measure may appear twice with different casing (e.g. `Change in real GDP` vs `Change in Real GDP`). Use `FILTER(REGEX(LCASE(?figLabel), "change in real gdp"))` or two `CONTAINS` clauses.
- **Numeric-only pulls:** many cells are real numbers as `xsd:decimal`. Placeholder dashes from the Fed HTML are **not** ingested as observations (so you are not flooded with `"-"^^xsd:string`). For extra safety use  
  `FILTER(datatype(?value) = <http://www.w3.org/2001/XMLSchema#decimal>)`.
- Prose: `eco:ProseDocument`, `eco:ContentBlock` (see `ontology_ref.md`).

### Example — PCE-style figure (filter by figure title, not series column name)

```sparql
PREFIX eco: <https://example.org/macro#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?period ?value ?seriesLabel ?figLabel ?src WHERE {
  ?obs a eco:Observation .
  ?obs eco:period ?period .
  ?obs eco:value ?value .
  ?obs eco:inSeries ?series .
  ?obs eco:statedIn ?src .
  ?series rdfs:label ?seriesLabel .
  ?series eco:inFigure ?fig .
  ?fig rdfs:label ?figLabel .
  FILTER(CONTAINS(LCASE(?figLabel), "pce"))
}
ORDER BY ?figLabel ?seriesLabel ?period
LIMIT 80
```

### Example — real GDP projection / SEP (decimals only, both GDP figure title variants)

```sparql
PREFIX eco: <https://example.org/macro#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?rowStub ?yearCol ?value ?figLabel ?src WHERE {
  ?obs a eco:Observation .
  ?obs eco:period ?rowStub .
  ?obs eco:value ?value .
  ?obs eco:inSeries ?series .
  ?obs eco:statedIn ?src .
  ?series rdfs:label ?yearCol .
  ?series eco:inFigure ?fig .
  ?fig rdfs:label ?figLabel .
  FILTER(REGEX(LCASE(?figLabel), "change in real gdp"))
  FILTER(datatype(?value) = xsd:decimal)
}
ORDER BY ?figLabel ?rowStub ?yearCol
LIMIT 200
```

`run_sparql.py` stdout: TSV rows for SELECT; `true`/`false` for ASK; N-Triples-style lines for CONSTRUCT.

## Output contract

- **list_mpr_data_series**: first line is the header `series_iri\tseries_label\tfigure_label`, then TSV rows.
- **query_macro_graph**: same as `run_sparql.py` (no header unless the query projects column names as data).
