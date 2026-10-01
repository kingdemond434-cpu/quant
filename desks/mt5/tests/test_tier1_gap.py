"""The tier-1 gap reads the box's own artifacts and never turns an absence into a zero."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import tier1_gap as tg  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _point(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tg, "DATA", tmp_path / "data")
    monkeypatch.setattr(tg, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(tg, "HYP", tmp_path / "data" / "hypotheses")
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    (tmp_path / "reports").mkdir()


def test_absent_inputs_read_unmeasured(monkeypatch, tmp_path: Path) -> None:
    _point(monkeypatch, tmp_path)
    doc = tg.build(NOW)
    gaps = {g["measure"]: g for g in doc["gaps"]}
    assert gaps["effective_breadth"]["us"] == tg.UNMEASURED
    assert gaps["unknown_share_7d"]["us"] == tg.UNMEASURED
    assert gaps["effective_breadth"]["times_short"] == tg.UNMEASURED


def test_measures_are_read_and_ranked(monkeypatch, tmp_path: Path) -> None:
    _point(monkeypatch, tmp_path)
    d = tmp_path / "data"
    (d / "effective_breadth.jsonl").write_text(json.dumps(
        {"at": NOW.isoformat(), "n_nominal": 453, "effective_breadth": 2.5,
         "n_clusters_occupied": 9, "n_clusters_empty": 6}) + "\n", "utf-8")
    rows = [{"at": NOW.isoformat(), "terminal_gate": g} for g in
            ["UNKNOWN"] * 43 + ["in_sample_screen"] * 55 + ["PASSED"] * 2]
    (d / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    (tmp_path / "reports" / "JUDGING_RATE.json").write_text(json.dumps(
        {"created_per_day": 8303.0, "verdicts_per_day": 5266.0}), "utf-8")
    (d / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps({"survivors": {
        "external.EURCHF.carry.a": {"sym": "EURCHF"},
        "external.EURCHF.carry.b": {"sym": "EURCHF"},
        "external.XAUUSD.formula.c": {"sym": "XAUUSD", "family": "formula"}}}), "utf-8")
    doc = tg.build(NOW)
    mj, el = doc["mining_and_judging"], doc["edges_and_live"]
    assert mj["unknown_share_7d"] == 0.43 and mj["passed_7d"] == 2
    assert el["certificates"] == 3 and el["cert_families"] == 2 and el["cert_symbols"] == 2
    gaps = {g["measure"]: g for g in doc["gaps"]}
    assert gaps["effective_breadth"]["times_short"] == 200.0
    assert gaps["unknown_share_7d"]["times_short"] == round(0.43 / 0.02, 2)
    ordered = [g["orders_short"] for g in doc["gaps"] if isinstance(g["orders_short"], float)]
    assert ordered == sorted(ordered, reverse=True)


def test_write_is_windows_safe(tmp_path: Path) -> None:
    out = tmp_path / "X.json"
    tg.write({"a": 1}, out)
    tg.write({"a": 2}, out)
    assert json.loads(out.read_text("utf-8")) == {"a": 2}
