"""Observers release real SQLite handles on every return and query failure."""
from __future__ import annotations

import importlib
import sqlite3

import pytest


@pytest.mark.parametrize("module,function", [
    ("run_conversion_control", "_candidate_counts"),
    ("run_coexistence", "_families"),
    ("estimate_contributions", "_table_rows"),
    ("watch_pnl", "_has_fills"),
])
@pytest.mark.parametrize("tables", [True, False])
def test_observer_closes_connection(tmp_path, monkeypatch, module, function, tables):
    path = tmp_path / "metrics.sqlite"
    connection = sqlite3.connect(path)
    if tables:
        connection.executescript(
            "CREATE TABLE research_candidates(survived INT, status TEXT, capacity_usd REAL, "
            "rejection_reason TEXT); CREATE TABLE alpha_performance(family TEXT, pnl REAL); "
            "CREATE TABLE fills(ticket INT);"
        )
    connection.close()
    observer = importlib.import_module("scripts." + module)
    monkeypatch.setattr(observer, "METRICS", path, raising=False)
    original = sqlite3.connect
    opened = []

    def connect(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(sqlite3, "connect", connect)
    args = (path,) if function == "_candidate_counts" else (
        ("fills",) if function == "_table_rows" else ())
    getattr(observer, function)(*args)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
