#!/usr/bin/env python3
"""List eco:DataSeries labels (and parent figure labels) for SPARQL discovery; optional substring filter."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RDF_DIR = ROOT / "data" / "oxigraph_db"

ECO = "https://example.org/macro#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"


def _escape_sparql_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _build_query(contains: str, limit: int) -> str:
    filt = ""
    if contains.strip():
        esc = _escape_sparql_str(contains.strip())
        filt = f"""
  FILTER(
    CONTAINS(LCASE(?label), LCASE("{esc}")) ||
    CONTAINS(LCASE(?figLabel), LCASE("{esc}"))
  )"""
    return f"""PREFIX eco: <{ECO}>
PREFIX rdfs: <{RDFS}>

SELECT DISTINCT ?series ?label ?figLabel WHERE {{
  ?series a eco:DataSeries .
  ?series rdfs:label ?label .
  ?series eco:inFigure ?fig .
  ?fig rdfs:label ?figLabel .
{filt}
}}
ORDER BY ?label
LIMIT {max(1, min(limit, 500))}
"""


def main() -> int:
    p = argparse.ArgumentParser(description="List MPR data series IRIs and labels from Oxigraph.")
    p.add_argument(
        "--contains",
        default="",
        help="Case-insensitive substring match on series or figure label (optional).",
    )
    p.add_argument("--limit", type=int, default=80, help="Max rows (default 80, max 500).")
    args = p.parse_args()

    try:
        from pyoxigraph import QuerySolutions, Store
    except ImportError:
        print("pyoxigraph not installed", file=sys.stderr)
        return 1

    if not RDF_DIR.exists() or not any(RDF_DIR.iterdir()):
        print("empty RDF store at data/oxigraph_db/ — populate it (see README).", file=sys.stderr)
        return 1

    store = Store.read_only(str(RDF_DIR))
    q = _build_query(args.contains, args.limit)
    try:
        results = store.query(q)
    except Exception as e:
        print(f"SPARQL error: {e}", file=sys.stderr)
        return 1

    if not isinstance(results, QuerySolutions):
        print("unexpected query result type", file=sys.stderr)
        return 1

    rows = list(results)
    if not rows:
        print("# no matching series")
        return 0

    print("series_iri\tseries_label\tfigure_label")
    vars_ = list(results.variables)
    for row in rows:
        print("\t".join(str(row[i]) for i in range(len(vars_))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
