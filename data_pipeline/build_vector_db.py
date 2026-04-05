"""
Chunk intermediate JSON and upsert into ChromaDB with source_url metadata.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parents[1]
JSON_DIR = ROOT / "data" / "intermediate_json"
CHROMA_PATH = ROOT / "data" / "chroma_db"
COLLECTION = "mpr_chunks"


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def main() -> None:
    files = list(JSON_DIR.glob("*.json"))
    if not files:
        print("No JSON in intermediate_json/", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    coll = client.get_or_create_collection(COLLECTION)

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    n = 0
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        url = data.get("url", "")
        edition = data.get("edition") or ""
        section_id = data.get("section_id") or ""
        section_title = data.get("section_title") or ""
        for block in data.get("blocks", []):
            tag = block.get("tag", "")
            src = block.get("source_url", url)
            for piece in chunk_text(block.get("text", "")):
                n += 1
                ids.append(f"{fp.stem}_{n}")
                documents.append(piece)
                meta = {"source_url": src, "tag": tag}
                if edition:
                    meta["edition"] = edition
                if section_id:
                    meta["section_id"] = section_id
                if section_title:
                    meta["section_title"] = section_title
                metadatas.append(meta)

    if not documents:
        print("Nothing to embed.", file=sys.stderr)
        sys.exit(1)

    coll.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Added {len(ids)} chunks to {COLLECTION} at {CHROMA_PATH}")


if __name__ == "__main__":
    main()
