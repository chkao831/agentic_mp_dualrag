"""
Same time-series path as `graph_tools_viz.py`: load decimal `eco:Observation` rows for one
`eco:DataSeries` IRI from local Oxigraph, then `st.line_chart(period → value)`.

Used by the main chat when `query_macro_graph` SPARQL fixes the series with `eco:inSeries <…>`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
OXIGRAPH_DB = REPO_ROOT / "data" / "oxigraph_db"


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


def _iri_term_for_sparql(series_iri: str) -> str:
    s = (series_iri or "").strip()
    if not s:
        return "<>"
    if s.startswith("<") and s.endswith(">"):
        return s
    return f"<{s}>"


def _run_sparql_local(
    sparql: str,
    store_dir: Path,
) -> tuple[str, pd.DataFrame | None, str]:
    from pyoxigraph import QueryBoolean, QuerySolutions, QueryTriples, Store

    sparql = (sparql or "").strip()
    if not sparql:
        return "error", None, "Empty query."
    if not store_dir.is_dir() or not any(store_dir.iterdir()):
        return "error", None, f"No Oxigraph data at `{store_dir}`."

    store = Store.read_only(str(store_dir.resolve()))
    try:
        results = store.query(sparql)
    except Exception as e:
        return "error", None, str(e)

    if isinstance(results, QueryBoolean):
        return "ask", None, str(bool(results)).lower()
    if isinstance(results, QueryTriples):
        return "triples", None, "(triples)"
    if isinstance(results, QuerySolutions):
        vars_ = [str(v) for v in results.variables]
        rows = []
        for row in results:
            rows.append([str(row[i]) for i in range(len(vars_))])
        if not rows:
            return "empty", None, "0 rows."
        return "select", pd.DataFrame(rows, columns=vars_), f"{len(rows)} row(s)."
    return "error", None, f"Unexpected result type: {type(results)}"


def _series_display_context(series_iri: str) -> tuple[str | None, str | None]:
    """
    Labels from the MPR RDF store: (series name, figure / chart title).
    Matches what users see from list_mpr_data_series (series_label, figure_label).
    """
    term = _iri_term_for_sparql(series_iri)
    sparql = f"""PREFIX eco: <https://example.org/macro#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?seriesLabel ?figLabel WHERE {{
  VALUES ?s {{ {term} }}
  OPTIONAL {{ ?s rdfs:label ?seriesLabel . }}
  OPTIONAL {{ ?s eco:inFigure ?fig . ?fig rdfs:label ?figLabel . }}
}}
LIMIT 1
"""
    kind, df, _ = _run_sparql_local(sparql, OXIGRAPH_DB)
    if kind != "select" or df is None or df.empty:
        return None, None

    df = df.copy()
    df.columns = [str(c).lstrip("?") for c in df.columns]
    row = df.iloc[0]

    def _cell(col: str) -> str | None:
        if col not in df.columns:
            return None
        raw = row[col]
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        s = _prettify_rdf_term(str(raw)).strip()
        return s or None

    return _cell("seriesLabel"), _cell("figLabel")


def _chart_caption_for_user(series_label: str | None, figure_label: str | None) -> str:
    """Plain language; no RDF vocabulary."""
    s = (series_label or "").strip()
    f = (figure_label or "").strip()
    if f and s and f.lower() != s.lower():
        return (
            f"**{f}** (Monetary Policy Report). The line shows **{s}** at each reporting period."
        )
    if f:
        return f"**{f}** — numeric values over time from the Monetary Policy Report."
    if s:
        return f"**{s}** over time (Monetary Policy Report)."
    return "Numeric values over time from the Monetary Policy Report."


def _series_title_fallback(series_iri: str) -> str:
    s = (series_iri or "").strip().rstrip("/")
    if "#" in s:
        return s.rsplit("#", 1)[-1]
    if "/" in s:
        return s.rsplit("/", 1)[-1]
    return s or "series"


def decimal_observations_for_series(series_iri: str) -> tuple[pd.DataFrame | None, str | None]:
    """Pull eco:Observation rows for one eco:DataSeries (xsd:decimal values only)."""
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
            "No decimal observations for this series — check the IRI or Oxigraph store."
        )
    df = df.copy()
    df.columns = [str(c).lstrip("?") for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).map(_prettify_rdf_term)
    return df, None


def extract_series_iri_from_macro_sparql(sparql: str) -> str | None:
    """
    Detect a fixed series IRI in model SPARQL, e.g. `?obs eco:inSeries <https://example.org/macro#series_…>`.
    """
    found = extract_all_series_iris_from_text(sparql)
    return found[0] if found else None


def extract_all_series_iris_from_text(text: str) -> list[str]:
    """
    All distinct series IRIs in arbitrary text (SPARQL, code fences, or assistant prose).
    Used when chat session has no stored `series_iris` (legacy 2-tuples) or tool SSE pairing misses.
    """
    if not (text or "").strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"eco:inSeries\s+<([^>]+)>", text, re.IGNORECASE | re.DOTALL):
        u = m.group(1).strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    for m in re.finditer(
        r"VALUES\s+\?(?:series|s)\s*\{\s*<([^>]+)>\s*\}",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        u = m.group(1).strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def render_observations_line_chart_for_series(series_iri: str) -> bool:
    """
    Same chart as graph_tools_viz “Plot time series” after resolving observations locally.
    Returns True if a chart was drawn.
    """
    if not series_iri.strip():
        return False
    if not OXIGRAPH_DB.is_dir() or not any(OXIGRAPH_DB.iterdir()):
        return False

    obs, err = decimal_observations_for_series(series_iri)
    if err:
        st.caption(f"_{err}_")
        return False
    if obs is None or obs.empty or "value" not in obs.columns or "period" not in obs.columns:
        return False

    plot = obs[["period", "value"]].copy()
    plot["value"] = pd.to_numeric(plot["value"], errors="coerce")
    plot = plot.dropna(subset=["value"])
    if plot.empty:
        return False

    series_lbl, fig_lbl = _series_display_context(series_iri)
    title = series_lbl if series_lbl else _series_title_fallback(series_iri)
    st.markdown(f"##### {title}")
    st.caption(_chart_caption_for_user(series_lbl, fig_lbl))

    st.line_chart(
        plot,
        x="period",
        y="value",
        x_label="Period",
        y_label="Value",
        use_container_width=True,
    )
    if "src" in obs.columns:
        with st.expander("Source pages (Fed URLs)", expanded=False):
            st.dataframe(obs[["period", "value", "src"]], use_container_width=True, hide_index=True)
    return True
