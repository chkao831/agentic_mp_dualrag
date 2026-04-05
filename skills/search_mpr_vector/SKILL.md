---
name: search_mpr_vector
description: Semantic search over scraped Federal Reserve MPR HTML chunks in ChromaDB.
---

# Vector RAG — Fed MPR

When the user asks for narrative context, themes, or wording from the report, call the `search_mpr_vector` tool.

## Output contract

The subprocess script prints lines the model must preserve:

- `Text: ...` for each hit
- `Source URL: https://www.federalreserve.gov/...` per hit

In final answers, turn every `Source URL` into a Markdown link next to the cited sentence.
