"""Streamlit dashboard server — renders :func:`build_dashboard` across the seven sections.

Run with: ``streamlit run app/dashboard_app.py -- --db <path-to-sor.sqlite>``. Requires the
``streamlit`` package (not installed in the sandbox); the aggregation in ``app.dashboard`` is
framework-free and fully tested, so this module is a thin, untestable rendering shell.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.dashboard import DashboardState, build_dashboard
from libs.store.connection import Database

_SECTIONS = (
    "research", "research_lab", "alpha_registry", "portfolio", "risk", "execution", "monitoring",
    "system_health",
)


def render(state: DashboardState) -> None:  # pragma: no cover - requires streamlit
    import streamlit as st

    st.set_page_config(page_title="Quant Platform", layout="wide")
    st.title("Quant Platform - Unified Dashboard")
    st.caption(f"generated_at: {state.generated_at}")
    data = state.model_dump()
    columns = st.columns(2)
    for i, section in enumerate(_SECTIONS):
        with columns[i % 2]:
            st.subheader(section.replace("_", " ").title())
            st.json(data[section])


def main() -> None:  # pragma: no cover - requires streamlit + a terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor.sqlite")
    args, _ = parser.parse_known_args()
    db = Database(Path(args.db))
    try:
        render(build_dashboard(db))
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
