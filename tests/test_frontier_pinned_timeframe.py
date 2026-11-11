"""A docket row of a family the judge pins to one chart names the judge's own cell."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_pinned_family_row_names_the_judges_chart() -> None:
    """`lvc_asia_london` is judged on M5 whatever its row says; its docket row must name the same
    cell (the 13 rows that never joined, audit 2026-09-30)."""
    fi = importlib.import_module("research.frontier_identity")
    src = (ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py").read_text("utf-8")
    pinned = next(ast.literal_eval(n.value) for n in ast.parse(src).body
                  if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "")
                  == "_PINNED_TIMEFRAME")
    assert pinned == fi.PINNED_TIMEFRAME
    row = {"symbol": "GBPJPY", "family": "lvc_asia_london", "params": {}}
    assert fi.docket_cell_id(row).startswith("GBPJPY@M5.lvc_asia_london.p=")
    judge = {"sym": "GBPJPY", "family": "lvc_asia_london", "params": {}, "timeframe": "M5"}
    assert fi.docket_cell_id(row) == fi.cell_id(judge)


def test_an_unpinned_family_keeps_its_reference_chart() -> None:
    fi = importlib.import_module("research.frontier_identity")
    row = {"symbol": "EURUSD", "family": "carry", "params": {}}
    assert "timeframe" not in fi.docket_cell(row)
