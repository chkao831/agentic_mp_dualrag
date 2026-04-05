# Deferred: `query_macro_graph`

This skill is **not** registered in `backend/agent.py`. The active path is vector RAG only (`search_mpr_vector`).

When you are ready to add GraphRAG:

1. Re-register the tool in `load_skill_tool_defs()` and `ALLOWED_SCRIPTS`.
2. Restore the subprocess branch in `run_skill_script()` for `--sparql`.
3. Complete `data_pipeline/build_rdf_graph.py` and populate `data/oxigraph_db/`.

See `doc/adr/0004-defer-rdf-graph-skill.md`.
