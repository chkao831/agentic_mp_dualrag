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

### Tables

If the answer includes a **Markdown table** of numbers or projections from the MPR, put **at least one** citation line **directly under the table** using an exact `Source URL` from the hits you used, for example:

`**Source:** [MPR — relevant section title](https://www.federalreserve.gov/...)`  

Do not end the reply with a table of Fed data and no `[text](url)` link.
