#!/usr/bin/env python3
"""Run SPARQL against the local Oxigraph store; stdout one line per result (TSV for SELECT)."""
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
        from pyoxigraph import QueryBoolean, QuerySolutions, QueryTriples, Store
    except ImportError:
        print("pyoxigraph not installed", file=sys.stderr)
        sys.exit(1)

    if not RDF_DIR.exists() or not any(RDF_DIR.iterdir()):
        print("empty RDF store at data/oxigraph_db/ — populate it (see README).", file=sys.stderr)
        sys.exit(1)

    store = Store.read_only(str(RDF_DIR))
    try:
        results = store.query(args.sparql)
    except Exception as e:
        print(f"SPARQL error: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(results, QueryBoolean):
        print(str(bool(results)).lower())
        return
    if isinstance(results, QuerySolutions):
        vars_ = list(results.variables)
        for row in results:
            print("\t".join(str(row[i]) for i in range(len(vars_))))
        return
    if isinstance(results, QueryTriples):
        for triple in results:
            print(triple)
        return
    print(results, file=sys.stderr)


if __name__ == "__main__":
    main()
