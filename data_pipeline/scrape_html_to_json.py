"""
Scrape Fed MPR HTML pages listed in data/target_urls.json.
Supports release-oriented config: editions with ordered sections (path or full url).

Persists bronze JSON with source_url on every block; optional edition / section metadata.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "data" / "target_urls.json"
OUT_DIR = ROOT / "data" / "intermediate_json"


def extract_main_content(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Placeholder: refine selector against live Fed DOM (e.g. #article or main)."""
    blocks: list[dict] = []
    main = soup.find("div", id="article") or soup.find("main") or soup.body
    if not main:
        return blocks
    for el in main.find_all(["p", "h2", "h3", "table"]):
        tag = el.name
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        blocks.append(
            {
                "tag": tag,
                "text": text,
                "source_url": page_url,
            }
        )
    return blocks


def scrape_url(url: str) -> dict:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    return {
        "url": url,
        "blocks": extract_main_content(soup, url),
    }


def resolve_section_url(base: str, path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return urljoin(base, path_or_url.lstrip("/"))


def load_jobs(cfg: dict) -> list[tuple[str, str, str, str]]:
    """(edition, section_id, section_title, url)"""
    base = cfg.get("url_base", "https://www.federalreserve.gov/monetarypolicy/")
    jobs: list[tuple[str, str, str, str]] = []
    for rel in cfg.get("releases", []):
        if rel.get("scrape") is False:
            continue
        edition = rel.get("edition", "")
        for sec in rel.get("sections", []):
            if sec.get("scrape") is False:
                continue
            path = sec.get("path") or sec.get("url", "")
            if not path:
                continue
            url = resolve_section_url(base, path)
            sid = sec.get("id", "")
            title = sec.get("title", "")
            jobs.append((edition, sid, title, url))
    return jobs


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(TARGETS.read_text(encoding="utf-8"))
    jobs = load_jobs(cfg)
    if not jobs:
        print("No scrape jobs in target_urls.json (check releases/sections).", file=sys.stderr)
        sys.exit(1)

    for edition, section_id, section_title, url in jobs:
        doc = scrape_url(url)
        doc["edition"] = edition
        doc["section_id"] = section_id
        doc["section_title"] = section_title
        slug = url.rstrip("/").split("/")[-1].replace(".htm", "") or "page"
        out = OUT_DIR / f"{slug}.json"
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
