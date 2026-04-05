---
name: query_macro_graph
description: SPARQL over the local Oxigraph RDF store (macro triples + provenance).
---

> **Deferred:** This skill is not wired into the agent yet. See `DEFERRED.md` and `doc/adr/0004-defer-rdf-graph-skill.md`.

# Graph RAG — placeholder (future)

When enabled, use `query_macro_graph` for explicit relationships once the RDF pipeline is populated.

## Output contract

`run_sparql.py` should print raw bindings or a short summary plus any `source` / provenance URIs returned from the graph.

See `ontology_ref.md` for prefixes.
