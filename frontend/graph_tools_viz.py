"""
Visualize graph-tool output from the MPR agent: paste SSE `status` JSON or tool JSON.

Helps interpret `list_mpr_data_series` (TSV + figure↔series graph) and `query_macro_graph` (SPARQL).

In the main app: sidebar → **Knowledge Graph**. Optional standalone (e.g. port 8502):
  uv run streamlit run frontend/graph_tools_viz_standalone.py --server.port 8502
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

REPO_ROOT = Path(__file__).resolve().parents[1]
OXIGRAPH_DB = REPO_ROOT / "data" / "oxigraph_db"
LIST_DATA_SERIES_SCRIPT = REPO_ROOT / "skills" / "list_mpr_data_series" / "list_data_series.py"

SAMPLE_LIST_JSON = json.dumps(
    {
        "type": "tool_use",
        "name": "list_mpr_data_series",
        "input": {"contains": "unemployment", "limit": 20},
    },
    indent=2,
)

SAMPLE_QUERY_JSON = json.dumps(
    {
        "type": "tool_use",
        "name": "query_macro_graph",
        "input": {
            "sparql": (
                "PREFIX eco: <https://example.org/macro#>\n"
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
                "SELECT ?year ?value ?source WHERE {\n"
                "  ?obs eco:inSeries ?series ;\n"
                "       eco:period ?year ;\n"
                "       eco:value ?value ;\n"
                "       eco:statedIn ?source .\n"
                "  ?series rdfs:label ?label .\n"
                '  FILTER(?label IN ("2025", "2026", "2027", "Longer run"))\n'
                '  ?fig rdfs:label "Unemployment rate" .\n'
                "  ?series eco:inFigure ?fig .\n"
                "}\n"
                "ORDER BY ?year"
            ),
        },
    },
    indent=2,
)


def _from_first_brace(s: str) -> str:
    """Drop Streamlit status prefixes like `**** — ` before `{`."""
    s = s.strip()
    i = s.find("{")
    return s[i:] if i >= 0 else s


def _parse_json_blobs(raw: str) -> list[dict]:
    raw = _from_first_brace(raw)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    out: list[dict] = []
    for line in raw.splitlines():
        line = _from_first_brace(line)
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


def _parse_sse_data_lines(raw: str) -> list[dict]:
    """Extract JSON objects from lines like `data: {...}` (Streamlit status log)."""
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        line = _from_first_brace(line)
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


def _tsv_to_df(text: str) -> pd.DataFrame:
    text = (text or "").strip()
    if not text or text.startswith("# no matching"):
        return pd.DataFrame()
    reader = csv.reader(StringIO(text), delimiter="\t")
    rows = list(reader)
    if len(rows) < 2:
        return pd.DataFrame()
    header = [c.strip().strip('"') for c in rows[0]]
    body = rows[1:]
    if len(header) < 3:
        return pd.DataFrame()
    df = pd.DataFrame(body, columns=header[:3])
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.strip('"')
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = list(df.columns)
    low = [c.lower().replace(" ", "_") for c in cols]
    rename = {cols[i]: low[i] for i in range(len(cols)) if low[i] in ("series_iri", "series_label", "figure_label")}
    if len(rename) == 3:
        return df.rename(columns=rename)
    if len(cols) >= 3:
        return df.rename(
            columns={cols[0]: "series_iri", cols[1]: "series_label", cols[2]: "figure_label"}
        )
    return df


def _normalize_iri_key(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("<") and t.endswith(">"):
        return t[1:-1]
    return t


def _decimal_observation_counts_by_series() -> dict[str, int]:
    """IRI (no brackets) -> count of distinct observations with xsd:decimal value."""
    sparql = """PREFIX eco: <https://example.org/macro#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?series (COUNT(DISTINCT ?obs) AS ?c) WHERE {
  ?obs eco:inSeries ?series .
  ?obs eco:value ?v .
  FILTER(datatype(?v) = xsd:decimal)
}
GROUP BY ?series
"""
    kind, df, _ = _run_sparql_local(sparql, OXIGRAPH_DB)
    if kind != "select" or df is None or df.empty:
        return {}
    df = df.copy()
    df.columns = [str(c).lstrip("?") for c in df.columns]
    out: dict[str, int] = {}
    for _, row in df.iterrows():
        raw_s = str(row.get("series", ""))
        k = _normalize_iri_key(_prettify_rdf_term(raw_s))
        if not k:
            continue
        cv_raw = str(row.get("c", "0"))
        if "^^" in cv_raw:
            cv_raw = cv_raw.split("^^", 1)[0].strip().strip('"')
        try:
            out[k] = int(float(cv_raw))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def _build_pyvis_html(
    df: pd.DataFrame,
    *,
    counts: dict[str, int] | None = None,
    max_rows: int = 250,
) -> str | None:
    if df.empty or not all(c in df.columns for c in ("series_iri", "series_label", "figure_label")):
        return None
    sub = df.head(max_rows).copy()
    counts = counts or {}
    from pyvis.network import Network

    net = Network(
        height="860px",
        width="100%",
        directed=True,
        bgcolor="#1a1c24",
        font_color="#e8e8e8",
    )
    net.set_edge_smooth("dynamic")

    fig_ids: dict[str, str] = {}
    fig_totals: dict[str, int] = {}
    for _, row in sub.iterrows():
        sid = str(row["series_iri"])
        k = _normalize_iri_key(sid)
        n = int(counts.get(k, 0))
        fl = str(row["figure_label"])
        fig_totals[fl] = fig_totals.get(fl, 0) + n

    for _, row in sub.iterrows():
        fig_lbl = str(row["figure_label"])
        if fig_lbl not in fig_ids:
            fid = "fig:" + hashlib.md5(fig_lbl.encode("utf-8")).hexdigest()[:16]
            fig_ids[fig_lbl] = fid
            tot = fig_totals.get(fig_lbl, 0)
            net.add_node(
                fid,
                label=(fig_lbl[:52] + ("…" if len(fig_lbl) > 52 else "")),
                title=(
                    f"Chart figure (eco:ChartFigure)\n{fig_lbl}\n\n"
                    f"Decimal observations (listed series on this subgraph): **{tot}**"
                ),
                shape="box",
                color="#3d6fb0",
                font={"size": 18},
                margin=12,
            )
        sid = _normalize_iri_key(str(row["series_iri"]))
        sl = str(row["series_label"])
        n = int(counts.get(sid, 0))
        lbl = f"{sl[:28]}{'…' if len(sl) > 28 else ''}\n(n={n})"
        net.add_node(
            sid,
            label=lbl,
            title=(
                f"DataSeries\nIRI: {sid}\nColumn / label: {sl}\n"
                f"Decimal datapoints: **{n}**\n\n"
                "Hover or click: bottom panel shows Selected IRI + Copy button."
            ),
            shape="dot",
            size=max(18, min(36, 14 + min(n, 50) // 3)),
            color="#6baed6",
            font={"size": 15},
        )
        net.add_edge(
            sid,
            fig_ids[fig_lbl],
            title="eco:inFigure",
            width=2,
        )

    net.set_options(
        """
{
  "interaction": { "hover": true },
  "edges": { "font": { "size": 12, "color": "#aaaaaa" } },
  "physics": {
    "enabled": true,
    "solver": "forceAtlas2Based",
    "forceAtlas2Based": { "gravitationalConstant": -120, "springLength": 180, "springConstant": 0.04 }
  }
}
"""
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "g.html"
        net.write_html(str(p), open_browser=False, notebook=False)
        raw = p.read_text(encoding="utf-8")
        return _inject_graph_hover_iri_panel(raw)


def _inject_graph_hover_iri_panel(html: str) -> str:
    """After PyVis creates `network`, show a fixed bottom panel with plain `Selected IRI <…>` on series hover.

    Native vis-network tooltips are not practical to select; figure nodes do not open this panel.
    """
    marker = "network = new vis.Network(container, data, options);"
    hook_js = """
                  (function () {
                    var gtvHideT = null;
                    var gtvIgnoreBlurUntil = 0;
                    function gtvCancelHide() {
                      if (gtvHideT) {
                        clearTimeout(gtvHideT);
                        gtvHideT = null;
                      }
                    }
                    function gtvScheduleHide() {
                      gtvCancelHide();
                      gtvHideT = setTimeout(function () {
                        var p = document.getElementById("gtv-hover-panel");
                        if (p) p.style.display = "none";
                      }, 2200);
                    }
                    function gtvEnsurePanel() {
                      var p = document.getElementById("gtv-hover-panel");
                      if (p) return p;
                      p = document.createElement("div");
                      p.id = "gtv-hover-panel";
                      p.setAttribute("style", "display:none;position:fixed;bottom:0;left:0;right:0;background:#1a1c24;color:#e8ffe8;padding:10px 14px;z-index:2147483646;font-family:ui-monospace,monospace;font-size:13px;line-height:1.4;box-shadow:0 -6px 24px rgba(0,0,0,0.5);border-top:1px solid #3d4458;pointer-events:auto;");
                      var row = document.createElement("div");
                      row.setAttribute("style", "display:flex;align-items:flex-start;gap:10px;width:100%;box-sizing:border-box;");
                      var ta = document.createElement("textarea");
                      ta.id = "gtv-hover-panel-ta";
                      ta.readOnly = true;
                      ta.setAttribute("style", "flex:1;min-width:0;min-height:2.5em;max-height:30vh;font:inherit;background:#252836;color:#e8ffe8;border:1px solid #3d4458;border-radius:4px;padding:8px;resize:vertical;box-sizing:border-box;");
                      var btn = document.createElement("button");
                      btn.type = "button";
                      btn.id = "gtv-hover-panel-copy";
                      btn.textContent = "Copy";
                      btn.setAttribute("style", "flex-shrink:0;margin-top:2px;padding:8px 14px;font:inherit;cursor:pointer;background:#3d5a80;color:#e8ffe8;border:1px solid #5a7aae;border-radius:4px;");
                      btn.addEventListener("click", function (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        var t = (ta.value || "").trim();
                        if (!t) return;
                        function fallbackCopy() {
                          ta.focus();
                          ta.select();
                          ta.setSelectionRange(0, ta.value.length);
                          try { document.execCommand("copy"); } catch (e) {}
                        }
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                          navigator.clipboard.writeText(t).catch(fallbackCopy);
                        } else {
                          fallbackCopy();
                        }
                        var prev = btn.textContent;
                        btn.textContent = "Copied!";
                        setTimeout(function () { btn.textContent = prev; }, 1600);
                      });
                      row.appendChild(ta);
                      row.appendChild(btn);
                      p.appendChild(row);
                      document.body.appendChild(p);
                      p.addEventListener("mouseenter", gtvCancelHide);
                      p.addEventListener("mouseleave", gtvScheduleHide);
                      ta.addEventListener("click", function () {
                        ta.focus();
                        ta.select();
                        ta.setSelectionRange(0, ta.value.length);
                      });
                      return p;
                    }
                    function gtvBareIri(nodeId) {
                      var s = nodeId != null ? String(nodeId).trim() : "";
                      if (s.length >= 2 && s.charAt(0) === "<" && s.charAt(s.length - 1) === ">") {
                        s = s.slice(1, -1).trim();
                      }
                      return s;
                    }
                    function gtvIsHttpSeries(nodeId) {
                      var s = gtvBareIri(nodeId);
                      return s.indexOf("http://") === 0 || s.indexOf("https://") === 0;
                    }
                    function gtvShowHoverPanel(nodeId) {
                      if (!gtvIsHttpSeries(nodeId)) {
                        var ex = document.getElementById("gtv-hover-panel");
                        if (ex) ex.style.display = "none";
                        gtvCancelHide();
                        return;
                      }
                      var inner = gtvBareIri(nodeId);
                      var p = gtvEnsurePanel();
                      var ta = document.getElementById("gtv-hover-panel-ta");
                      gtvCancelHide();
                      gtvIgnoreBlurUntil = Date.now() + 800;
                      ta.value = "Selected IRI <" + inner + ">";
                      p.style.display = "block";
                    }
                    function gtvOnBlurNode() {
                      if (Date.now() < gtvIgnoreBlurUntil) return;
                      gtvScheduleHide();
                    }
                    network.on("hoverNode", function (params) {
                      var nid = params && params.node != null ? params.node : null;
                      if (nid == null && params && params.nodes && params.nodes.length) nid = params.nodes[0];
                      if (nid != null) gtvShowHoverPanel(nid);
                    });
                    network.on("blurNode", gtvOnBlurNode);
                    network.on("click", function (params) {
                      if (!params || !params.nodes || params.nodes.length === 0) {
                        gtvScheduleHide();
                        return;
                      }
                      gtvShowHoverPanel(params.nodes[0]);
                    });
                  })();"""
    if marker in html:
        return html.replace(marker, marker + hook_js, 1)
    return html


def _select_variables_ordered(sparql: str) -> list[str]:
    """Outer SELECT variables in order (best-effort; ignores subqueries)."""
    m = re.search(r"(?is)\bSELECT\s+(?:DISTINCT\s+)?(.+?)\s+WHERE\b", sparql)
    if not m:
        return []
    clause = m.group(1)
    return re.findall(r"\?[a-zA-Z_][a-zA-Z0-9_]*", clause)


def _prettify_rdf_term(cell: str) -> str:
    s = (cell or "").strip()
    m = re.match(r'^"(.*)"\^\^<(http://www\.w3\.org/2001/XMLSchema#[^>]+)>$', s, re.DOTALL)
    if m:
        return m.group(1).replace('\\"', '"')
    m = re.match(r'^"(.*)"@([a-zA-Z-]+)$', s)
    if m:
        return m.group(1)
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"')
    return s


def _tool_result_tsv_lines_to_df(text: str) -> pd.DataFrame:
    """Oxigraph SELECT stdout: one tab-separated row per line, no header."""
    rows: list[list[str]] = []
    for line in (text or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = next(csv.reader(StringIO(line), delimiter="\t"))
        except StopIteration:
            continue
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    return pd.DataFrame(padded)


def _pair_query_macro_use_and_result(
    events: list[dict],
) -> tuple[list[tuple[str | None, str, bool]], list[str]]:
    """
    Walk in order: each tool_result pairs with the latest unmatched tool_use SPARQL.
    Returns (pairs of (sparql_or_none, output_preview, likely_truncated), orphan_sparql_only).
    """
    pairs: list[tuple[str | None, str, bool]] = []
    orphans: list[str] = []
    pending: str | None = None

    for ev in events:
        if ev.get("type") == "tool_use" and ev.get("name") == "query_macro_graph":
            inp = ev.get("input") or {}
            q = inp.get("sparql")
            if not isinstance(q, str) or not q.strip():
                continue
            if pending is not None:
                orphans.append(pending)
            pending = q.strip()
        elif ev.get("type") == "tool_result" and ev.get("name") == "query_macro_graph":
            preview = ev.get("output_preview")
            if not isinstance(preview, str) or not preview.strip():
                continue
            prev = len(preview) >= 499
            pairs.append((pending, preview, prev))
            pending = None

    if pending is not None:
        orphans.append(pending)
    return pairs, orphans


def _pair_list_mpr_use_and_result(
    events: list[dict],
) -> tuple[list[tuple[dict | None, str, bool]], list[dict]]:
    """
    Each list_mpr tool_result pairs with the latest unmatched list_mpr tool_use input.
    Returns (pairs of (input_or_none, output_preview, likely_truncated), orphan tool_use inputs).
    """
    pairs: list[tuple[dict | None, str, bool]] = []
    orphan_inputs: list[dict] = []
    pending: dict | None = None

    for ev in events:
        if ev.get("type") == "tool_use" and ev.get("name") == "list_mpr_data_series":
            if pending is not None:
                orphan_inputs.append(pending)
            inp = ev.get("input")
            pending = inp if isinstance(inp, dict) else {}
        elif ev.get("type") == "tool_result" and ev.get("name") == "list_mpr_data_series":
            preview = ev.get("output_preview")
            if not isinstance(preview, str) or not preview.strip():
                continue
            trunc = len(preview) >= 3999
            pairs.append((pending, preview, trunc))
            pending = None

    if pending is not None:
        orphan_inputs.append(pending)
    return pairs, orphan_inputs


def _run_list_data_series_subprocess(contains: str, limit: int) -> tuple[bool, str]:
    if not LIST_DATA_SERIES_SCRIPT.is_file():
        return False, f"Script not found: `{LIST_DATA_SERIES_SCRIPT}`"
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 80
    lim = max(1, min(lim, 500))
    argv = [
        sys.executable,
        str(LIST_DATA_SERIES_SCRIPT),
        "--contains",
        str(contains or ""),
        "--limit",
        str(lim),
    ]
    proc = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "error").strip()
    return True, proc.stdout


def _list_local_rerun_ui(inp: dict | None, *, state_prefix: str) -> None:
    """Button + optional fresh graph from list_data_series.py (same args as tool_use)."""
    if not inp:
        return
    contains = str(inp.get("contains") or "")
    try:
        limit = int(inp.get("limit", 80))
    except (TypeError, ValueError):
        limit = 80
    btn_key = f"{state_prefix}_btn"
    out_key = f"{state_prefix}_stdout"
    err_key = f"{state_prefix}_err"
    if st.button(
        "Run `list_data_series.py` locally (same `contains` / `limit`)",
        key=btn_key,
    ):
        ok, text = _run_list_data_series_subprocess(contains, limit)
        if ok:
            st.session_state[out_key] = text
            st.session_state.pop(err_key, None)
        else:
            st.session_state[err_key] = text
            st.session_state.pop(out_key, None)
    if err_key in st.session_state and st.session_state[err_key]:
        st.error(st.session_state[err_key])
    out = st.session_state.get(out_key)
    if out:
        st.markdown("**Live stdout (full):**")
        _render_list_df(
            _normalize_columns(_tsv_to_df(out)),
            False,
            ts_state_prefix=f"{state_prefix}_live",
        )


def _render_query_macro_formatted(
    sparql: str | None,
    preview: str,
    truncated: bool,
) -> None:
    if truncated:
        st.warning(
            "`output_preview` is likely **truncated** (~500 chars for `query_macro_graph` in the chat UI). "
            "Use **Run on local Oxigraph** below for the full result set."
        )
    vars_sel = _select_variables_ordered(sparql) if sparql else []
    df_raw = _tool_result_tsv_lines_to_df(preview)
    if df_raw.empty:
        st.caption("No result rows parsed from preview.")
        return
    names: list[str] = []
    for i in range(df_raw.shape[1]):
        if i < len(vars_sel):
            names.append(vars_sel[i].lstrip("?"))
        else:
            names.append(f"col_{i + 1}")
    df_raw.columns = names

    df_show = df_raw.copy()
    for c in df_show.columns:
        df_show[c] = df_show[c].astype(str).map(_prettify_rdf_term)

    st.dataframe(df_show, use_container_width=True, hide_index=True)
    if sparql:
        with st.expander("SPARQL for this result", expanded=False):
            st.code(sparql, language="sql")


def _summarize_sparql(q: str) -> list[str]:
    hints: list[str] = []
    if "eco:Observation" in q or " a eco:Observation" in q:
        hints.append("Touches **eco:Observation** (table cells).")
    if "eco:DataSeries" in q:
        hints.append("Touches **eco:DataSeries**.")
    if "eco:ChartFigure" in q or "eco:inFigure" in q:
        hints.append("Joins to **figure** via `eco:inFigure` / `eco:ChartFigure`.")
    if "skos:Concept" in q:
        hints.append("Uses **SKOS** (abbreviations).")
    vars_ = re.findall(r"\?([a-zA-Z_][a-zA-Z0-9_]*)", q)
    if vars_:
        u = sorted(set(vars_))
        tail = "…" if len(u) > 12 else ""
        hints.append(f"Variables: {', '.join(u[:12])}{tail}")
    return hints


def _run_sparql_local(
    sparql: str,
    store_dir: Path,
    *,
    triple_limit: int = 800,
) -> tuple[str, pd.DataFrame | None, str]:
    """
    Returns (kind, dataframe_or_none, message).
    kind: 'select' | 'ask' | 'triples' | 'error' | 'empty'
    """
    from pyoxigraph import QueryBoolean, QuerySolutions, QueryTriples, Store

    sparql = (sparql or "").strip()
    if not sparql:
        return "error", None, "Empty query."

    if not store_dir.is_dir() or not any(store_dir.iterdir()):
        return "error", None, f"No Oxigraph data at `{store_dir}` (see README)."

    store = Store.read_only(str(store_dir.resolve()))
    try:
        results = store.query(sparql)
    except Exception as e:
        return "error", None, str(e)

    if isinstance(results, QueryBoolean):
        return "ask", None, str(bool(results)).lower()
    if isinstance(results, QueryTriples):
        lines = [str(t) for t in results]
        tail = f"\n… ({len(lines) - triple_limit} more)" if len(lines) > triple_limit else ""
        body = "\n".join(lines[:triple_limit]) + tail
        return "triples", None, body or "(no triples)"
    if isinstance(results, QuerySolutions):
        vars_ = [str(v) for v in results.variables]
        rows = []
        for row in results:
            rows.append([str(row[i]) for i in range(len(vars_))])
        if not rows:
            return "empty", None, "0 rows."
        return "select", pd.DataFrame(rows, columns=vars_), f"{len(rows)} row(s)."
    return "error", None, f"Unexpected result type: {type(results)}"


def _sparql_local_run_block(sparql: str, *, state_prefix: str) -> None:
    """Editable SPARQL + Run button + results (same as former standalone tab)."""
    area_key = f"{state_prefix}_sparql"
    seed_key = f"{state_prefix}_sparql_seed"
    h = hashlib.sha256((sparql or "").encode()).hexdigest()[:16]
    if st.session_state.get(seed_key) != h:
        st.session_state[area_key] = sparql
        st.session_state[seed_key] = h
    sparql_run = st.text_area("SPARQL", height=220, key=area_key)
    btn_key = f"{state_prefix}_run_btn"
    if st.button("Run on local Oxigraph", type="primary", key=btn_key):
        kind, df, msg = _run_sparql_local(sparql_run, OXIGRAPH_DB)
        if kind == "error":
            st.error(msg)
        elif kind == "ask":
            st.success(f"ASK → **{msg}**")
        elif kind == "triples":
            st.text_area("Triples", msg, height=320)
        elif kind == "empty":
            st.warning(msg)
        elif kind == "select" and df is not None:
            st.caption(msg)
            st.dataframe(df, use_container_width=True, hide_index=True)


def _iri_term_for_sparql(series_iri: str) -> str:
    s = (series_iri or "").strip()
    if not s:
        return "<>"
    if s.startswith("<") and s.endswith(">"):
        return s
    return f"<{s}>"


def _parse_pasted_series_iri(text: str) -> str:
    """First non-empty line; if it matches `Selected IRI <…>`, return inner IRI; else strip RDF <…> wrapper."""
    s = (text or "").strip()
    if not s:
        return ""
    line = s.splitlines()[0].strip()
    m = re.match(r"^Selected\s+IRI\s*<([^>]+)>\s*$", line, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return _normalize_iri_key(line)


def _decimal_observations_for_series(series_iri: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Pull eco:Observation rows for one eco:DataSeries (decimal values only).
    Returns (dataframe period/value/source, error_message).
    """
    term = _iri_term_for_sparql(series_iri)
    sparql = f"""PREFIX eco: <https://example.org/macro#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?period ?value ?src WHERE {{
  ?obs eco:inSeries {term} ;
       eco:period ?period ;
       eco:value ?value .
  OPTIONAL {{ ?obs eco:statedIn ?src . }}
  FILTER(datatype(?value) = xsd:decimal)
}}
ORDER BY ?period
"""
    kind, df, msg = _run_sparql_local(sparql, OXIGRAPH_DB)
    if kind == "error":
        return None, msg
    if kind != "select" or df is None or df.empty:
        return None, (
            "No decimal observations for this series — check the IRI, "
            "or this column may have no numeric cells in the store."
        )
    df = df.copy()
    df.columns = [str(c).lstrip("?") for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).map(_prettify_rdf_term)
    return df, None


def _render_series_timeseries_block(
    df: pd.DataFrame,
    *,
    state_prefix: str,
    counts_map: dict[str, int],
) -> None:
    """Paste series IRI (or full `Selected IRI <…>` line from the graph panel) → line chart."""
    if df.empty or "series_iri" not in df.columns:
        return
    st.subheader("Plot time series")
    if not OXIGRAPH_DB.is_dir() or not any(OXIGRAPH_DB.iterdir()):
        st.warning(f"No Oxigraph store at `{OXIGRAPH_DB}`.")
        return

    def _row_for_iri(target: str) -> int | None:
        key = _normalize_iri_key(target)
        for pos, (_, hit) in enumerate(df.iterrows()):
            if _normalize_iri_key(str(hit["series_iri"])) == key:
                return pos + 1
        return None

    paste_key = f"{state_prefix}_ts_paste_iri"
    pasted = st.text_area(
        "Paste series IRI (or the full Selected IRI line copied from the graph panel)",
        key=paste_key,
        height=88,
        placeholder="Selected IRI <https://…>  or paste https://… only",
    )
    pick = _parse_pasted_series_iri(pasted)
    if not pick:
        st.info("Paste an IRI above to plot.")
        return

    rn_show = _row_for_iri(pick)
    if rn_show is not None:
        st.caption(f"Table row **#{rn_show}** · decimal datapoints in store: **{counts_map.get(_normalize_iri_key(pick), 0)}**")
    else:
        st.caption("IRI not in the table above — still querying Oxigraph.")

    obs, err = _decimal_observations_for_series(pick)
    if err:
        st.warning(err)
        return
    if obs is None or obs.empty:
        st.info("No rows returned.")
        return
    if "value" not in obs.columns or "period" not in obs.columns:
        st.dataframe(obs, use_container_width=True, hide_index=True)
        return
    plot = obs[["period", "value"]].copy()
    plot["value"] = pd.to_numeric(plot["value"], errors="coerce")
    plot = plot.dropna(subset=["value"])
    if plot.empty:
        st.warning("No numeric values to plot.")
        return
    plot = plot.set_index("period")
    st.line_chart(plot["value"])
    if "src" in obs.columns:
        with st.expander("Provenance (`eco:statedIn`)", expanded=False):
            st.dataframe(obs[["period", "value", "src"]], use_container_width=True, hide_index=True)


def _render_list_df(df: pd.DataFrame, trunc_guess: bool, *, ts_state_prefix: str | None = None) -> None:
    if trunc_guess:
        st.warning(
            "`output_preview` may be **truncated** (~500 chars in the chat UI). "
            "For a full graph, run **`list_data_series.py` locally** (same `contains` / `limit`) or "
            "`uv run python skills/list_mpr_data_series/list_data_series.py --contains …`."
        )
    if df.empty:
        st.info("No TSV rows parsed.")
        return
    counts_map: dict[str, int] = {}
    if OXIGRAPH_DB.is_dir() and any(OXIGRAPH_DB.iterdir()):
        counts_map = _decimal_observation_counts_by_series()
    view = df.copy()
    view.insert(0, "#", list(range(1, len(view) + 1)))
    view["decimal_pts"] = view["series_iri"].astype(str).map(
        lambda x: int(counts_map.get(_normalize_iri_key(x), 0))
    )
    show_cols = ["#", "series_label", "figure_label", "series_iri", "decimal_pts"]
    view = view[[c for c in show_cols if c in view.columns]]
    st.dataframe(view, use_container_width=True, hide_index=True)
    html_g = _build_pyvis_html(df, counts=counts_map)
    if html_g:
        components.html(html_g, height=900, scrolling=True)
    else:
        st.caption("Graph skipped (empty or unexpected columns).")
    if ts_state_prefix:
        _render_series_timeseries_block(df, state_prefix=ts_state_prefix, counts_map=counts_map)


def render_knowledge_graph_sidebar() -> None:
    """Sample payloads (use from unified app or standalone)."""
    if st.button("Load sample: list_mpr", key="gtv_sb_list"):
        st.session_state["gtv_json"] = SAMPLE_LIST_JSON
        st.rerun()
    if st.button("Load sample: query_macro", key="gtv_sb_query"):
        st.session_state["gtv_json"] = SAMPLE_QUERY_JSON
        st.rerun()


def render_knowledge_graph_main() -> None:
    """Main panel: paste tool JSON / SSE, render tables, PyVis, SPARQL runner."""
    if "gtv_json" not in st.session_state:
        st.session_state["gtv_json"] = ""

    raw = st.text_area(
        "JSON object, JSON array, NDJSON, or pasted log lines containing `data: {…}`. "
        "Leading text before the first `{` is ignored (e.g. `**** — ` from Streamlit status).",
        height=260,
        key="gtv_json",
    )
    events = _parse_json_blobs(raw)
    if not events and "data:" in raw:
        events = _parse_sse_data_lines(raw)

    if not events:
        st.info("Paste a `tool_result` / `tool_use` object, or SSE lines with `data: {...}`.")
        return

    st.caption(f"Parsed **{len(events)}** object(s).")

    list_pairs, orphan_list_inputs = _pair_list_mpr_use_and_result(events)
    for i, (inp, preview, trunc) in enumerate(list_pairs):
        st.markdown(f"#### list_mpr_data_series — #{i + 1}")
        if inp:
            st.caption(
                f"`tool_use` inputs: `contains` = {inp.get('contains', '')!r}, "
                f"`limit` = {inp.get('limit', '')!r}"
            )
        df_list = _normalize_columns(_tsv_to_df(preview))
        _render_list_df(df_list, trunc, ts_state_prefix=f"gtv_list_pair_{i}")
        _list_local_rerun_ui(inp, state_prefix=f"gtv_list_pair_{i}")

    for i, inp in enumerate(orphan_list_inputs):
        st.markdown(f"#### list_mpr_data_series — tool_use only #{i + 1}")
        st.json(inp)
        _list_local_rerun_ui(inp, state_prefix=f"gtv_list_orphan_{i}")

    macro_pairs, orphan_sparql = _pair_query_macro_use_and_result(events)

    for i, (sp_sql, prev, trunc) in enumerate(macro_pairs):
        st.markdown(f"#### query_macro_graph — formatted result #{i + 1}")
        st.caption(
            "Parsed `output_preview` TSV; column titles from the **preceding** `tool_use` `SELECT` variables."
        )
        _render_query_macro_formatted(sp_sql, prev, trunc)

    for i, sparql in enumerate(orphan_sparql):
        st.markdown(f"#### query_macro_graph — SPARQL only (no matching `tool_result` in paste) #{i + 1}")
        st.info(
            "Paste a matching **`tool_result`** to see a **formatted preview table**, or run on **`data/oxigraph_db/`** below."
        )
        for h in _summarize_sparql(sparql):
            st.markdown(f"- {h}")
        st.code(sparql, language="sql")
        st.markdown("**Run on local Oxigraph**")
        _sparql_local_run_block(sparql, state_prefix=f"gtv_macro_orphan_{i}")

    if not list_pairs and not orphan_list_inputs and not macro_pairs and not orphan_sparql:
        st.warning(
            "No `list_mpr_data_series` or `query_macro_graph` events found. "
            "Use `tool_use` / `tool_result` pairs (or at least one recognizable event)."
        )


def render_graph_tools_standalone_page() -> None:
    """Full page when running `streamlit run frontend/graph_tools_viz_standalone.py` (or legacy port)."""
    st.set_page_config(page_title="MPR graph tools — viz", layout="wide")
    st.title("MPR graph tools — output inspector")
    with st.sidebar:
        render_knowledge_graph_sidebar()
    render_knowledge_graph_main()
