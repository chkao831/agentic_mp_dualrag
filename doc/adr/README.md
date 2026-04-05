# Architecture Decision Records (ADRs)

Records in this folder use the **Jeff Tyree and Art Akerman** decision description structure from *Architecture Decisions: Demystifying Architecture* (Capital One): **Issue, Decision, Status, Group, Assumptions, Constraints, Positions, Argument, Implications**, plus **Related decisions**, **Related requirements**, **Related artifacts**, **Related principles**, and **Notes**.

**Requirements traceability:** Functional and non-functional requirements are maintained in [`doc/requirements.md`](../requirements.md). Each ADR’s **Related requirements** section maps to stable IDs (`FR-xx`, `NFR-xx`).

## Index

| ADR | Title | Status |
|-----|--------|--------|
| [0001](0001-use-html-scraping-for-mpr-ingestion.md) | Use HTML scraping for MPR ingestion | Approved |
| [0002](0002-provenance-through-live-source-urls.md) | Provenance through live source URLs | Approved |
| [0003](0003-agent-orchestration-via-anthropic-api-and-subprocess-skills.md) | Agent orchestration via Anthropic API and subprocess skills | Approved |
| [0004](0004-defer-rdf-graph-skill.md) | Defer RDF graph skill from the active agent | Approved |
| [0005](0005-streaming-ui-with-sse-and-streamlit.md) | Streaming UI with SSE and Streamlit | Approved |

## Conventions

- **Filename:** `NNNN-short-title-in-kebab-case.md`
- **Status:** Prefer Tyree/Akerman vocabulary (`pending`, `decided`, `approved`); use `deprecated` or `superseded by ADR-XXXX` when retiring a decision.
- **Superseding:** Add a new ADR that references the old one; avoid silent edits that erase decision history.

## Template

Copy [template.md](template.md) when adding `0006-...`.
