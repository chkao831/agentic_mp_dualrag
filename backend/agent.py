"""
Anthropic message loop with allowlisted subprocess execution for skills/*.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
load_dotenv(ROOT / ".env")

# Map tool name -> script path (must stay under skills/).
# Graph skill (query_macro_graph) is deferred; see doc/adr/0004-defer-rdf-graph-skill.md
ALLOWED_SCRIPTS: dict[str, Path] = {
    "search_mpr_vector": SKILLS_DIR / "search_mpr_vector" / "query_chroma.py",
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


def stream_agent_turns(
    user_text: str,
    *,
    model: str = "claude-sonnet-4-20250514",
    on_tool_event: Callable[[dict], None] | None = None,
) -> Iterator[str]:
    """
    Yields assistant text deltas and invokes on_tool_event for each tool_use / tool_result step.
    Final answer should use Markdown links from tool output (enforced in system prompt).
    """
    client = anthropic.Anthropic()
    system = (
        "You are a Federal Reserve Monetary Policy Report assistant. "
        "Use the search_mpr_vector tool to retrieve relevant passages from the Monetary Policy Report. "
        "When you cite facts, use clickable Markdown links using the exact Source URL lines "
        "returned by the tool, e.g. [MPR source](https://www.federalreserve.gov/...). "
        "Never invent URLs.\n\n"
        "Format answers for readability: use short ## section headings for longer replies; "
        "use GitHub-flavored Markdown tables for small comparisons (e.g. years or metrics). "
        "Use ![description](url) only when the URL is a direct image file (e.g. ends in .png, .jpg, .svg, or "
        "is clearly an image asset); do not use image syntax for ordinary HTML report pages."
    )
    tools = load_skill_tool_defs()
    messages: list[dict] = [{"role": "user", "content": user_text}]

    max_turns = 12
    prior_text = False
    for _ in range(max_turns):
        msg = client.messages.create(
            model=model,
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
