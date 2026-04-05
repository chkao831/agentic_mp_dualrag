#!/usr/bin/env python3
"""CLI entrypoint for Chroma semantic search (subprocess target)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHROMA_PATH = ROOT / "data" / "chroma_db"
COLLECTION = "mpr_chunks"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--query", required=True)
    p.add_argument("--top_k", type=int, default=5)
    args = p.parse_args()

    try:
        import chromadb
    except ImportError:
        print("chromadb not installed", file=sys.stderr)
        sys.exit(1)

    if not CHROMA_PATH.exists():
        print(
            "ChromaDB path missing. Run data_pipeline/build_vector_db.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        coll = client.get_collection(COLLECTION)
    except Exception as e:
        print(f"Collection error: {e}", file=sys.stderr)
        sys.exit(1)

    res = coll.query(query_texts=[args.query], n_results=args.top_k)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    for doc, meta in zip(docs, metas):
        url = (meta or {}).get("source_url", "")
        print(f"Text: {doc}")
        print(f"Source URL: {url}")
        print()


if __name__ == "__main__":
    main()
