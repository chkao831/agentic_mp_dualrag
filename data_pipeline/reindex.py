"""
One-shot vector RAG reindex: optional JSON cleanup, scrape, wipe Chroma, embed.

Usage (from repo root):
  uv run python data_pipeline/reindex.py
  uv run python data_pipeline/reindex.py --skip-scrape      # rebuild Chroma from existing JSON only
  uv run python data_pipeline/reindex.py --clean-json       # full reset of bronze JSON + index
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INTERMEDIATE = DATA / "intermediate_json"
CHROMA = DATA / "chroma_db"


def wipe_chroma_except_gitkeep(chroma_dir: Path) -> None:
    chroma_dir.mkdir(parents=True, exist_ok=True)
    for child in chroma_dir.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def clean_intermediate_json() -> None:
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    for f in INTERMEDIATE.glob("*.json"):
        f.unlink()


def run_step(script_name: str) -> None:
    script = ROOT / "data_pipeline" / script_name
    if not script.is_file():
        print(f"Missing script: {script}", file=sys.stderr)
        sys.exit(1)
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Scrape MPR HTML → JSON, wipe Chroma, rebuild embeddings.")
    p.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Do not run scrape_html_to_json.py (use existing data/intermediate_json/*.json).",
    )
    p.add_argument(
        "--clean-json",
        action="store_true",
        help="Delete data/intermediate_json/*.json before scraping (no effect if --skip-scrape).",
    )
    args = p.parse_args()

    if args.clean_json and not args.skip_scrape:
        print("Removing data/intermediate_json/*.json …")
        clean_intermediate_json()

    if not args.skip_scrape:
        print("Scraping → data/intermediate_json/ …")
        run_step("scrape_html_to_json.py")
    else:
        files = list(INTERMEDIATE.glob("*.json"))
        if not files:
            print("No JSON in data/intermediate_json/. Run without --skip-scrape first.", file=sys.stderr)
            sys.exit(1)

    print("Wiping data/chroma_db/ (keeping .gitkeep) …")
    wipe_chroma_except_gitkeep(CHROMA)

    print("Building Chroma collection …")
    run_step("build_vector_db.py")

    print("Done.")


if __name__ == "__main__":
    main()
