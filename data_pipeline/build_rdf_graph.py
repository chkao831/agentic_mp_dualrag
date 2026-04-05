"""
Use Anthropic to extract RDF triples from scraped JSON; attach Fed URL as provenance.

Requires ANTHROPIC_API_KEY. Loads/stores Oxigraph on disk under data/oxigraph_db.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

JSON_DIR = ROOT / "data" / "intermediate_json"
RDF_DIR = ROOT / "data" / "oxigraph_db"


def main() -> None:
    try:
        import anthropic
        from pyoxigraph import Store
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    files = list(JSON_DIR.glob("*.json"))
    if not files:
        print("No JSON in intermediate_json/", file=sys.stderr)
        sys.exit(1)

    RDF_DIR.mkdir(parents=True, exist_ok=True)
    store = Store(path=str(RDF_DIR))
    # TODO: iterate blocks, call Claude for triples (Turtle or N-Triples), store.load_* 

    client = anthropic.Anthropic()
    for fp in files[:1]:  # skeleton: first file only
        data = json.loads(fp.read_text(encoding="utf-8"))
        url = data.get("url", "")
        text_sample = "\n".join(b.get("text", "")[:500] for b in data.get("blocks", [])[:3])
        _ = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"From this MPR excerpt, output 3 plausible RDF triples as N-Triples "
                        f"using prefix eco: <https://example.org/macro#> . "
                        f"Include provenance: <{url}> as object of eco:statedIn for the claim.\n\n"
                        f"{text_sample}"
                    ),
                }
            ],
        )
        # Parse model output -> store.load_from_string(...) in full implementation

    _ = store  # silence unused until triples are loaded
    print("Skeleton: wire Claude N-Triples parsing into pyoxigraph Store.load().")
    print(f"Store directory: {RDF_DIR}")


if __name__ == "__main__":
    main()
