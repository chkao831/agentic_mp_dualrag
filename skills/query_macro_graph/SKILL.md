---
name: query_macro_graph
description: Run arbitrary SPARQL against the local Oxigraph MPR store (eco:/skos:/dct:). Use after list_mpr_data_series when you need exact numeric observations and provenance URLs.
---

# Tool: `query_macro_graph`

Executes **model-authored SPARQL** via `run_sparql.py` against `data/oxigraph_db/`. For **series discovery** first, use **`list_mpr_data_series`** (`skills/list_mpr_data_series/SKILL.md`).

## How it fits with vector + list

| Tool | Use when |
|------|----------|
| **search_mpr_vector** | Vague or interpretive questions; discover wording and figure titles. |
| **list_mpr_data_series** | Need IRIs and labels before SPARQL (`skills/list_mpr_data_series/`). |
| **query_macro_graph** | Specific SPARQL for `eco:Observation` rows, periods, `eco:statedIn`. |

## SPARQL reminders

- **Namespace (mandatory):** `PREFIX eco: <https://example.org/macro#>` exactly — not `qudt.org` or other `eco` IRIs.
- **Observations:** `eco:Observation` with **`eco:period`**, **`eco:value`**, **`eco:inSeries`**, **`eco:statedIn`**. No `eco:refDate` / `eco:observedProperty` in this store.
- **Series / figures:** `eco:DataSeries` + `eco:inFigure` → `eco:ChartFigure`; labels on `rdfs:label`.
- **Casing:** duplicate figure titles may differ only by case — use `LCASE` / `REGEX` as needed.
- **Numeric pulls:** placeholders (`-`) are usually omitted; use `FILTER(datatype(?value) = xsd:decimal)` when you want decimals only.
- Prose classes (if loaded): `eco:ProseDocument`, `eco:ContentBlock` — see `ontology_ref.md`.

### Example — PCE-style figure (filter by figure title)

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

### Example — real GDP / SEP (decimals only)

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

`run_sparql.py` stdout: TSV for SELECT; `true`/`false` for ASK; triple lines for CONSTRUCT.

## Output contract

Same as `run_sparql.py`: no header row unless your query projects one; TSV columns match solution variables.
