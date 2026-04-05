#!/usr/bin/env python3
"""Placeholder SPARQL executor against pyoxigraph Store (subprocess target)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RDF_DIR = ROOT / "data" / "oxigraph_db"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sparql", required=True)
    args = p.parse_args()

    try:
        from pyoxigraph import Store
    except ImportError:
        print("pyoxigraph not installed", file=sys.stderr)
        sys.exit(1)

    if not RDF_DIR.exists() or not any(RDF_DIR.iterdir()):
        print(
            "RDF store empty or missing. Run data_pipeline/build_rdf_graph.py after populating JSON.",
            file=sys.stderr,
        )
        # Still exit 0 with message so the agent can explain TBD state
        print("GraphRAG: TBD — no triples loaded yet.")
        print(f"Source URL: https://www.federalreserve.gov/monetarypolicy/mpr_default.htm")
        return

    store = Store(path=str(RDF_DIR))
    try:
        results = store.query(args.sparql)
    except Exception as e:
        print(f"SPARQL error: {e}", file=sys.stderr)
        sys.exit(1)

    for row in results:
        print(row)


if __name__ == "__main__":
    main()
