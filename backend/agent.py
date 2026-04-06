"""
Anthropic message loop with allowlisted subprocess execution for skills/*.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from collections.abc import Callable, Iterator
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
load_dotenv(ROOT / ".env")

# Presets for POST /chat/stream and env ANTHROPIC_MODEL (sonnet | haiku | full model id).
ANTHROPIC_MODEL_SONNET = "claude-sonnet-4-6"
ANTHROPIC_MODEL_HAIKU = "claude-haiku-4-5-20251001"


def resolve_anthropic_model(preset_or_id: str | None) -> str:
    """
    Map short names to API ids, or pass through a full model string.
    When preset_or_id is None/empty, uses env ANTHROPIC_MODEL, defaulting to sonnet.
    """
    raw = (preset_or_id or "").strip() or os.environ.get("ANTHROPIC_MODEL", "").strip()
    if not raw:
        return ANTHROPIC_MODEL_SONNET
    key = raw.lower()
    if key == "sonnet":
        return ANTHROPIC_MODEL_SONNET
    if key == "haiku":
        return ANTHROPIC_MODEL_HAIKU
    return raw


# Map tool name -> script path (must stay under skills/).
ALLOWED_SCRIPTS: dict[str, Path] = {
    "search_mpr_vector": SKILLS_DIR / "search_mpr_vector" / "query_chroma.py",
    "query_macro_graph": SKILLS_DIR / "query_macro_graph" / "run_sparql.py",
    "list_mpr_data_series": SKILLS_DIR / "query_macro_graph" / "list_data_series.py",
}


def load_skill_tool_defs() -> list[dict]:
    """Minimal tool defs; expand from SKILL.md parsing later."""
    return [
        {
            "name": "search_mpr_vector",
            "description": "Semantic search over Fed MPR chunks in ChromaDB. Returns text and source_url.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User search query"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_mpr_data_series",
            "description": (
                "List chart data series (eco:DataSeries) from the MPR RDF store: IRIs and labels, "
                "with optional substring filter on series or figure name. Use after vector search "
                "to pick the right series before running SPARQL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "contains": {
                        "type": "string",
                        "description": "Case-insensitive substring to match series or figure label (e.g. PCE, trimmed). Empty lists a sample of series.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 80,
                        "description": "Max rows (max 500).",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "query_macro_graph",
            "description": (
                "Run SPARQL against the local Oxigraph MPR store. REQUIRED prefix: "
                "PREFIX eco: <https://example.org/macro#> (exactly this IRI; never qudt.org or other eco namespaces). "
                "Observations use eco:period, eco:value, eco:inSeries, eco:statedIn — not refDate or observedProperty. "
                "list_mpr_data_series often returns year-like series_label; measure names are in figure_label — filter via "
                "join to eco:ChartFigure rdfs:label or use listed series IRIs. Fed '-' placeholder cells are omitted from "
                "the graph; use FILTER(datatype(?value)=xsd:decimal) for numeric-only rows. Duplicate figure titles may "
                "differ only by case (e.g. real GDP vs Real GDP). See skills/query_macro_graph/SKILL.md."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "sparql": {
                        "type": "string",
                        "description": "Full SPARQL query string (include PREFIX lines as needed).",
                    },
                },
                "required": ["sparql"],
            },
        },
    ]


def run_skill_script(name: str, payload: dict) -> str:
    script = ALLOWED_SCRIPTS.get(name)
    if not script or not script.is_file():
        return f"Error: unknown or missing script for {name}"
    if not str(script.resolve()).startswith(str(SKILLS_DIR.resolve())):
        return "Error: path escape"
    argv = [sys.executable, str(script)]
    if name == "search_mpr_vector":
        argv += ["--query", payload.get("query", "")]
        argv += ["--top_k", str(payload.get("top_k", 5))]
    elif name == "query_macro_graph":
        argv += ["--sparql", payload.get("sparql", "")]
    elif name == "list_mpr_data_series":
        argv += ["--contains", str(payload.get("contains", "") or "")]
        try:
            lim = int(payload.get("limit", 80))
        except (TypeError, ValueError):
            lim = 80
        argv += ["--limit", str(max(1, min(lim, 500)))]
    proc = subprocess.run(
        argv,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        return f"Script error (exit {proc.returncode}): {err or out}"
    return out or err


def _mpr_corpus_context() -> str:
    """Human-readable indexed-edition lines + clock date so answers stay anchored to report vintage."""
    today = os.environ.get("MPR_ASSISTANT_TODAY", date.today().isoformat())
    edition_lines = "Indexed MPR edition: configure `data/target_urls.json` (releases with scrape: true)."
    p = ROOT / "data" / "target_urls.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            active = [r for r in (data.get("releases") or []) if r.get("scrape") is True]
            if active:
                parts = []
                for r in active[:5]:
                    ed = r.get("edition", "")
                    lbl = r.get("label", ed)
                    parts.append(f"- {lbl} (edition `{ed}`)")
                edition_lines = "Indexed MPR content (vector + graph) is from:\n" + "\n".join(parts)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return (
        f"**Corpus and time:**\n"
        f"- Calendar date for this session (server; override with env `MPR_ASSISTANT_TODAY` if needed): **{today}**.\n"
        f"- {edition_lines}\n"
        f"- Open with the report vintage when giving numbers (e.g. \"In the June 2025 Monetary Policy Report…\").\n"
        f"- Phrases in the report such as \"12 months ending in April\" describe **reference periods inside that document**, "
        f"not \"the latest macro data as of\" your calendar date above. If the report is older than {today[:4]}, "
        f"say explicitly that figures are **as stated in that report**, not necessarily current today.\n"
        f"- Do not retitle those periods as \"Most recent actual data (as of April 2025)\" unless the source text uses "
        f"that exact framing; prefer quoting the report's wording.\n"
    )


def stream_agent_turns(
    user_text: str,
    *,
    model: str | None = None,
    on_tool_event: Callable[[dict], None] | None = None,
) -> Iterator[str]:
    """
    Yields assistant text deltas and invokes on_tool_event for each tool_use / tool_result step.
    Final answer should use Markdown links from tool output (enforced in system prompt).
    """
    resolved_model = resolve_anthropic_model(model)
    client = anthropic.Anthropic()
    system = (
        "You are a Federal Reserve Monetary Policy Report assistant.\n\n"
        f"{_mpr_corpus_context()}\n"
        "**Retrieval order:**\n"
        "1. For broad or interpretive questions (themes, definitions, \"what does the report say about …\") "
        "or when the user has not named a specific data series, use **search_mpr_vector** first.\n"
        "2. For **exact numeric values** from chart tables, use **list_mpr_data_series** then **query_macro_graph**. "
        "SPARQL must use PREFIX eco: <https://example.org/macro#> exactly (not qudt.org). "
        "Observations: eco:period, eco:value, eco:inSeries, eco:statedIn. "
        "Series list columns are often **years**; **PCE/CPI** text is usually on the **figure** label — join ?series eco:inFigure ?fig "
        "and FILTER on ?fig rdfs:label, or copy the example in skills/query_macro_graph/SKILL.md.\n"
        "3. Do **not** use graph tools alone for vague \"trend\" questions without first narrowing which measure "
        "the MPR uses.\n\n"
        "When you cite facts from vector search, use clickable Markdown links from the exact **Source URL** lines, "
        "e.g. [MPR source](https://www.federalreserve.gov/...). For graph results, cite the **statedIn** / source "
        "URLs returned by the query. Never invent URLs.\n\n"
        "**Tables and citations (mandatory):** Any Markdown **table** of MPR figures, projections, percentages, "
        "or other quantitative Fed data must not stand alone. Immediately **below the table** (same subsection, "
        "before the next `##`), include at least one line with a clickable citation, e.g. "
        "`**Source:** [Monetary Policy Report — Part 3 (SEP summary)](exact Source URL from tools)` "
        "or one link per distinct page if the table blends sources. Use only URLs you received from "
        "`search_mpr_vector` (**Source URL:**) or from graph **statedIn**. If you cannot tie the table to a "
        "returned URL, say so and retrieve again instead of publishing bare numbers.\n\n"
        "Format answers for readability: short ## headings; use Markdown tables for small numeric comparisons.\n"
        "**Formatting (spaces, bold, parsers):** Use normal ASCII spaces (U+0020) between numbers, currency/units, "
        "and words (e.g. `$97 billion`, `3.4 trillion`). Do not use non-breaking space (NBSP) or narrow no-break "
        "space; they confuse rendering. For **bold**, use ASCII `*` only. Put a **normal space** before opening `**` "
        "when bold starts with a digit or `$` after a letter (e.g. `approximately **3.4 trillion**`, "
        "not `approximately**3.4 trillion**`) so Markdown parsers recognize the delimiter. Keep `**` flush to the "
        "number after that opening (no space after `**` before a digit or `$`). Do not put spaces inside the pair "
        "touching the bold text: use `**3.4 trillion**`, not `** 3.4 trillion **`. "
        "Do not wrap long numeric phrases in bold — put emphasis on short labels or headings instead. "
        "Use normal typography: spaces only between words, never between individual letters inside a word or number. "
        "When a vector hit includes `Image URL:` (Fed .svg/.png etc.), include that URL once as "
        "`![short alt from the hit](image_url)` so the chat UI can render the figure; still cite the page "
        "with [MPR source](Source URL). Use ![description](url) only for direct image file URLs, not HTML pages."
    )
    tools = load_skill_tool_defs()
    messages: list[dict] = [{"role": "user", "content": user_text}]

    max_turns = 12
    prior_text = False
    for _ in range(max_turns):
        msg = client.messages.create(
            model=resolved_model,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        tool_uses = []
        text_parts: list[str] = []

        for block in msg.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_parts:
            chunk = "".join(text_parts)
            if prior_text:
                chunk = "\n\n" + chunk
            prior_text = True
            yield chunk

        if not tool_uses:
            break

        messages.append({"role": "assistant", "content": msg.content})

        tool_results: list[dict] = []
        for tu in tool_uses:
            payload = tu.input if isinstance(tu.input, dict) else {}
            if on_tool_event:
                on_tool_event(
                    {
                        "type": "tool_use",
                        "name": tu.name,
                        "input": payload,
                    }
                )
            result = run_skill_script(tu.name, payload)
            if on_tool_event:
                on_tool_event(
                    {
                        "type": "tool_result",
                        "name": tu.name,
                        "output_preview": result[:500],
                    }
                )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result,
                }
            )

        messages.append({"role": "user", "content": tool_results})
