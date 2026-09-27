"""The orthogonal frontier: exact recipes for the registered families nothing emitted.

Every row must be something the gauntlet can BUILD (no unexecutable key), on a chart the family
can mean, on an instrument the hypothesis lane may hunt -- otherwise it is intake noise.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import orthogonal_frontier as of  # noqa: E402
from research.sweep_breadth import unexecutable_reason  # noqa: E402
from research.universe_policy import may_hypothesise  # noqa: E402


def _all_charts(_sym: str, _tf: str) -> bool:
    return True


def test_the_grid_covers_every_named_orthogonal_cell():
    rows, gaps = of.grid(has_chart=_all_charts)
    fams = Counter(r["family"] for r in rows)
    for fam in ("multi_speed_trend", "trend_ma_cross", "cross_sectional", "style_premia",
                "overnight_drift", "monday_gap", "relative_value", "turn_of_month"):
        assert fams[fam] > 0, fam
    charts = Counter(r["chart"] for r in rows)
    assert charts["D1"] > 0 and charts["H4"] > 0
    # calendar_month's month and side are SOURCE evidence; enumerating them is the search its
    # own docstring refuses.
    assert fams["calendar_month"] == 0
    assert not any(k.startswith("off_domain") for k in gaps), gaps


def test_every_row_is_buildable_lane_legal_and_names_its_chart():
    rows, _ = of.grid(has_chart=_all_charts)
    for r in rows:
        assert unexecutable_reason(r["family"], r["params"]) is None, r
        assert may_hypothesise(r["symbol"]), r["symbol"]
        assert r["params"]["timeframe"] == r["chart"]
        assert r["mechanism"] and r["title"]


def test_trend_is_emitted_on_the_slow_charts_of_the_untested_classes_only():
    rows, _ = of.grid(has_chart=_all_charts)
    trend = [r for r in rows if r["family"] in ("multi_speed_trend", "trend_ma_cross")]
    assert {r["bucket"] for r in trend} <= set(of.TREND_BUCKETS)
    assert {r["chart"] for r in trend} == {"D1", "H4"}


def test_cross_sectional_rows_carry_a_real_named_panel():
    rows, _ = of.grid(has_chart=_all_charts)
    xs = [r for r in rows if r["family"] == "cross_sectional"]
    for r in xs:
        peers = r["params"]["peer_symbols"]
        assert len(peers) >= 10 and r["symbol"] in peers
        assert r["params"]["mode"] == "momentum"


def test_a_missing_chart_is_reported_and_never_emitted():
    rows, gaps = of.grid(has_chart=lambda s, tf: tf == "H1")
    assert all(r["chart"] == "H1" for r in rows)
    assert gaps.get("chart_absent:D1", 0) > 0 and gaps.get("chart_absent:H4", 0) > 0


def test_donation_is_due_only_when_the_grid_changes_or_ages(tmp_path, monkeypatch):
    monkeypatch.setattr(of, "INTEL", tmp_path)
    assert of._last_donation(tmp_path) == (None, None)
    d = tmp_path / of.SOURCE
    d.mkdir()
    (d / "discoveries_20260925_0000.json").write_text(
        json.dumps({"grid_digest": "abc", "discoveries": []}), "utf-8")
    age, digest = of._last_donation(tmp_path)
    assert digest == "abc" and age is not None and age < 1.0
    monkeypatch.setattr(of, "grid", lambda: ([], {}))
    doc = of.run(apply=False)
    assert doc["donated"] == 0 and doc["path"] is None


def test_report_only_never_donates(monkeypatch):
    called: list[int] = []
    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", lambda *a, **k: called.append(1))
    doc = of.run(apply=False)
    assert called == [] and doc["donated"] == 0


# ------------------------------------------------------- the cross-sectional input rebuild
def _bars(seed: int, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close,
                         "tick_volume": 100, "spread": 1}, index=idx)


def test_family_inputs_rebuilds_the_named_panel_on_the_cells_chart(monkeypatch):
    from mt5desk import family_inputs

    from research import orthogonal_sweep

    seen: list[tuple[str, str]] = []

    def fake(sym: str, tf: str = "H1"):
        seen.append((sym, tf))
        return _bars(abs(hash(sym)) % 1000)

    monkeypatch.setattr(orthogonal_sweep, "_bars", fake)
    own = _bars(1)
    names = [f"P{i}" for i in range(12)]
    extra, why = family_inputs.resolve("SELF", "cross_sectional",
                                       {"peer_symbols": names, "timeframe": "D1"}, own)
    assert why == "ok" and extra is not None
    assert set(extra["peers"]) == {"SELF", *names} and extra["symbol"] == "SELF"
    assert extra["peers"]["SELF"] is own
    assert all(tf == "D1" for _s, tf in seen)
    assert "peer_symbols" in family_inputs.IDENTITY_KEYS
    assert "peer_symbols" not in family_inputs.strip_identity_keys(
        "cross_sectional", {"peer_symbols": names, "horizon": 20})
    missing, why = family_inputs.resolve("SELF", "cross_sectional", {}, own)
    assert missing is None and "peer_symbols" in why
