# RDF prefixes (skeleton)

| Prefix | IRI |
|--------|-----|
| `eco:` | `https://example.org/macro#` |
| `dct:` | `http://purl.org/dc/terms/` |
| `prov:` | `http://www.w3.org/ns/prov#` |

Example provenance pattern:

```turtle
eco:claim_1 eco:statedIn <https://www.federalreserve.gov/.../part1.htm> .
```

Replace `https://example.org/macro#` with your stable namespace when publishing the graph.
