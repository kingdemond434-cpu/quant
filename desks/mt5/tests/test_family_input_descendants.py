from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from libs.data.pit import is_stamped
from research import family_input_descendants as fid


def identity(row: dict) -> str:
    return json.dumps({"symbol": row.get("symbol"), "family": row.get("family"),
                       "params": row.get("params") or {}}, sort_keys=True)


def test_missing_factor_becomes_fresh_child_without_rewriting_parent(monkeypatch) -> None:
    parent = {"symbol": "EURUSD", "family": "cross_asset_residual", "params": {},
              "available_time": "2026-09-01T00:00:00+00:00", "old_verdict": "UNKNOWN"}

    def complete(row, ctx, meta):
        return {**row, "params": {"factor_symbols": ["USDJPY", "US500"]},
                "input_completed": "factor_symbols"}

    monkeypatch.setattr(fid.compiler, "complete_inputs", complete)
    now = datetime(2026, 10, 2, 23, 0, tzinfo=UTC)
    children, report = fid.derive([parent], identity=identity, ctx=object(), meta={}, now=now)
    assert report["created"] == 1
    assert report["targets"] == 1
    assert parent["params"] == {}
    assert parent["old_verdict"] == "UNKNOWN"
    child = children[0]
    assert child["params"]["factor_symbols"] == ["USDJPY", "US500"]
    assert "old_verdict" not in child
    assert child["available_time"] == now.isoformat(timespec="seconds")
    assert child["input_descendant"]["parent_identity"] == identity(parent)
    assert is_stamped(child)
    again, repeated = fid.derive([parent, child], identity=identity, ctx=object(),
                                 meta={}, now=now)
    assert again == []
    assert repeated["already_present"] == 1


def test_unresolved_input_has_explicit_reason(monkeypatch) -> None:
    parent = {"symbol": "XAUUSD", "family": "relative_value", "params": {}}
    monkeypatch.setattr(fid.compiler, "complete_inputs", lambda row, ctx, meta: row)
    children, report = fid.derive([parent], identity=identity, ctx=object(), meta={})
    assert children == []
    assert report["unresolved"] == 1
    assert report["unresolved_by_reason"] == {"no_compatible_input_on_H1": 1}


def test_named_inputs_are_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(fid.compiler, "complete_inputs", lambda *_: 1 / 0)
    rows = [{"symbol": "USDJPY", "family": "lead_lag",
             "params": {"driver_symbol": "US500"}}]
    children, report = fid.derive(rows, identity=identity)
    assert children == []
    assert report["targets"] == 0
