"""The judging docket is ordered by MARGINAL k_eff -- and the ordering removes nothing.

research/docket_keff.py stamps each cell with its expected contribution to the book's N_eff
(libs/research/effective_breadth.exposure_neff) plus explicit bonuses for an empty alpha cluster
and a vacant high-orthogonality census class; research/judge_coverage.py reads the stamp inside
each family stream and as a one-sided family factor on the remainder.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pd = pytest.importorskip("pandas")

from research import docket_keff as dk  # noqa: E402
from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _panel(n: int = 400, seed: int = 7) -> dict[str, Any]:
    """A: the book's instrument. TWIN: A plus a little noise. INDEP: its own path."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    a = rng.normal(0, 0.01, n)
    return {"A": pd.Series(a, index=idx),
            "TWIN": pd.Series(a + rng.normal(0, 0.001, n), index=idx),
            "INDEP": pd.Series(rng.normal(0, 0.01, n), index=idx),
            "B": pd.Series(rng.normal(0, 0.01, n), index=idx)}


def _loader(panel: dict[str, Any]):
    return lambda s: panel.get(s)


def test_an_independent_instrument_adds_more_breadth_than_a_twin() -> None:
    panel = _panel()
    out = dk.symbol_deltas({"A": 2.0, "B": 1.0}, 3.0, ["TWIN", "INDEP", "A", "NONE"],
                           _loader(panel))
    assert out["INDEP"]["status"] == "MEASURED"
    assert out["INDEP"]["delta_k"] > out["TWIN"]["delta_k"]
    assert out["INDEP"]["delta_k"] > out["A"]["delta_k"]
    # A second unit on what the book is already long of is charged the stacking side.
    assert out["A"]["delta_k"] < 0.5
    assert out["NONE"]["status"] == "UNMEASURED" and out["NONE"]["delta_k"] is None


def test_an_empty_book_makes_every_first_sleeve_one_bet() -> None:
    out = dk.symbol_deltas({}, 0.0, ["INDEP"], _loader(_panel()))
    assert out["INDEP"]["delta_k"] == 1.0


def test_empty_cluster_and_vacant_class_bonuses_are_explicit() -> None:
    panel = _panel()
    breadth = {"exposure_by_instrument": {"A": 1.0, "B": 1.0},
               "nominal": {"sleeves_in_the_measurement": 2},
               "clusters": {"empty_in_both": ["cross_sectional_fx"]},
               "sleeve_clusters": {"A_session_range_breakout_asia": "session_liquidity"}}
    rows = [{"family": "cross_sectional", "symbol": "INDEP"},
            {"family": "session_range_breakout", "symbol": "INDEP"},
            {"family": "cross_asset_residual", "symbol": "INDEP"}]
    doc = dk.score(rows, breadth=breadth, canon={}, loader=_loader(panel))
    t = {r["family"]: doc["_terms"][dk.cell_key(r)] for r in rows}
    assert t["cross_sectional"]["empty_cluster_bonus"] == dk.EMPTY_CLUSTER_BONUS
    assert t["session_range_breakout"]["empty_cluster_bonus"] == 0.0
    assert doc["vacant_classes_status"] == "MEASURED"
    assert any(v["vacant_class_bonus"] > 0 for v in t.values()), "a vacant class pays a bonus"
    assert rows[0]["_keff"] > rows[1]["_keff"], "the empty cluster is judged first"
    assert doc["cluster_targets"]["cross_sectional_fx"]["docket_cells"] == 1
    assert doc["cluster_targets"]["cross_sectional_fx"]["empty_in_book"] is True


def test_unmeasured_inputs_never_demote_a_cell() -> None:
    """No book artifact: every cell at par, every bonus off, and both say UNMEASURED."""
    rows = [{"family": "carry", "symbol": "EURUSD"}, {"family": "trend", "symbol": "ZZZ"}]
    doc = dk.score(rows, breadth=None, canon=None, loader=lambda s: None,
                   read_artifacts=False)
    assert doc["instrument"]["status"] == "UNMEASURED"
    assert doc["clusters_status"] == "UNMEASURED"
    assert doc["vacant_classes_status"] == "UNMEASURED"
    assert {r["_keff"] for r in rows} == {0.0}


def test_a_symbol_without_bars_takes_the_median_not_zero() -> None:
    panel = _panel()
    breadth = {"exposure_by_instrument": {"A": 1.0, "B": 1.0}}
    rows = [{"family": "f", "symbol": s} for s in ("TWIN", "INDEP", "NONE")]
    doc = dk.score(rows, breadth=breadth, canon={}, loader=_loader(panel))
    terms = doc["_terms"]
    lo, hi = sorted((terms["f|TWIN"]["delta_k"], terms["f|INDEP"]["delta_k"]))
    assert terms["f|NONE"]["delta_k_status"] == "PAR"
    assert terms["f|NONE"]["delta_k"] == pytest.approx((lo + hi) / 2)


def _stamped_rows() -> list[dict[str, Any]]:
    seen = (NOW - timedelta(hours=3)).isoformat()
    rows = []
    for fam, n in (("big", 60), ("small", 8)):
        for i in range(n):
            rows.append({"family": fam, "symbol": f"S{i}", "params": {"i": i},
                         "first_seen": seen, "_keff": float((i * 7) % 11)})
    return rows


def test_coverage_order_reorders_by_keff_and_drops_nothing() -> None:
    rows = _stamped_rows()
    quota = {"big": 20, "small": 5}
    legacy = jc.coverage_order([dict(r) for r in rows], quota, use_keff=False)
    shipped = jc.coverage_order([dict(r) for r in rows], quota)
    key = lambda r: (r["family"], r["symbol"])  # noqa: E731
    assert sorted(map(key, shipped)) == sorted(map(key, rows)), "same rows, all of them"
    # The family interleave is untouched: every prefix holds the same family counts.
    for n in (5, 25, 50):
        assert Counter(r["family"] for r in shipped[:n]) == \
            Counter(r["family"] for r in legacy[:n])
    big = [r["_keff"] for r in shipped if r["family"] == "big"]
    assert big == sorted(big, reverse=True), "inside a family the largest k_eff goes first"


def test_rank_by_value_keff_factor_is_one_sided() -> None:
    rows = [{"family": "hi", "params": {}, "_keff": 1.5},
            {"family": "lo", "params": {}, "_keff": -2.0},
            {"family": "none", "params": {}}]
    ranking = {r["family"]: r for r in jc.rank_by_value({"hi": 1, "lo": 1, "none": 1}, rows, 100)}
    assert ranking["hi"]["keff_factor"] == pytest.approx(2.5)
    assert ranking["lo"]["keff_factor"] == 1.0, "a negative mean never demotes a family"
    assert ranking["none"]["keff_factor"] == 1.0
    assert ranking["hi"]["ev_per_cell"] > ranking["lo"]["ev_per_cell"]


def test_order_docket_publishes_the_evidence_and_ships_every_row(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    panel = _panel()
    breadth = tmp_path / "EFFECTIVE_BREADTH.json"
    breadth.write_text(json.dumps({
        "exposure_by_instrument": {"A": 1.0, "B": 1.0},
        "nominal": {"sleeves_in_the_measurement": 2},
        "clusters": {"empty_in_both": ["cross_sectional_fx"]},
        "sleeve_clusters": {"A_carry": "macro_rates"}}), "utf-8")
    monkeypatch.setattr(dk, "BREADTH", breadth)
    monkeypatch.setattr(dk, "CANON", tmp_path / "absent.json")
    monkeypatch.setattr(dk, "daily_returns", _loader(panel))
    monkeypatch.setattr(dk, "REPORT", tmp_path / "DOCKET_KEFF_ORDER.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "ratchet.json")
    monkeypatch.setattr(jc, "STUDY_BANK", tmp_path / "none.json")
    monkeypatch.setattr(jc, "GATE_LEDGER", tmp_path / "gate.jsonl")
    monkeypatch.setattr(jc, "unrunnable_bank", lambda path=None: {})
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable.json")
    seen = (NOW - timedelta(hours=2)).isoformat()
    rows = ([{"family": "carry", "symbol": s, "params": {"i": i}, "first_seen": seen}
             for i, s in enumerate(["TWIN", "INDEP", "A"] * 5)]
            + [{"family": "cross_sectional", "symbol": "INDEP", "params": {"i": i},
                "first_seen": seen} for i in range(4)])
    ordered, doc = jc.order_docket([dict(r) for r in rows], publish=True, now=NOW)
    assert len(ordered) == len(rows), "reorder only: nothing dropped"
    assert all("_keff" not in r and "_cell" not in r for r in ordered)
    ko = doc["keff_order"]
    assert ko["status"] == "MEASURED"
    assert ko["head"]["shipped"]["rows"] == ko["head"]["legacy"]["rows"]
    rep = json.loads((tmp_path / "DOCKET_KEFF_ORDER.json").read_text("utf-8"))
    assert rep["cell_terms_total"] == 5
    assert rep["cluster_targets"]["cross_sectional_fx"]["docket_cells"] == 4
    assert "INDEP" in rep["symbol_deltas"]
    cov = json.loads((tmp_path / "JUDGE_COVERAGE.json").read_text("utf-8"))
    assert "_keff_detail" not in cov and cov["keff_order"]["status"] == "MEASURED"
    carry = [r["symbol"] for r in ordered if r["family"] == "carry"]
    first_seen_by_sym = {s: carry.index(s) for s in ("INDEP", "A")}
    assert first_seen_by_sym["INDEP"] < first_seen_by_sym["A"], \
        "the independent instrument reaches the judge before a second unit of the book's own"
