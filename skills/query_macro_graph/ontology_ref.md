# RDF prefixes

| Prefix | IRI |
|--------|-----|
| `eco:` | `https://example.org/macro#` |
| `skos:` | `http://www.w3.org/2004/02/skos/core#` |
| `dct:` | `http://purl.org/dc/terms/` |
| `prov:` | `http://www.w3.org/ns/prov#` |

## Chart / table vocabulary

| Class / property | Meaning |
|------------------|---------|
| `eco:ChartFigure` | One accessible chart block (figure title + table). |
| `eco:DataSeries` | One non-period column linked to a figure. |
| `eco:Observation` | One cell: `eco:period` (row stub), `eco:value`, `eco:inSeries`, `eco:statedIn`. |
| `eco:ChartNote` | Note lines with a table. |
| `eco:edition` | Report edition (e.g. `2025-06`). |
| `eco:subsectionLabel` | Subheading under a figure. |
| `eco:tableUnit` | Unit line for the table. |
| `eco:period` | Row stub (first-column label). |
| `eco:value` | Value (`xsd:decimal` when numeric). |
| `eco:inFigure` / `eco:inSeries` | Structure links. |
| `eco:statedIn` | Source page IRI. |
| SKOS | `skos:Concept`, `skos:notation`, `skos:prefLabel`, `skos:altLabel` on abbreviations. |

## Prose vocabulary (if present in store)

| Class / property | Meaning |
|------------------|---------|
| `eco:ProseDocument` | One narrative section: `dct:source`, `eco:edition`, section ids/titles. |
| `eco:ContentBlock` | HTML block text and metadata. |
| `eco:OutlineSection` | `h3` subsection. |
| `eco:EmbeddedFigure` | Image URL / alt from `img` blocks. |

Use **`list_mpr_data_series`** before SPARQL when you need series IRIs and labels.
