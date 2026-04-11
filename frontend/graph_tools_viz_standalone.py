"""
Optional standalone Knowledge Graph inspector (same UI as the in-app tab).

From repo root:
  uv run streamlit run frontend/graph_tools_viz_standalone.py --server.port 8502
"""
from __future__ import annotations

from graph_tools_viz import render_graph_tools_standalone_page

render_graph_tools_standalone_page()
