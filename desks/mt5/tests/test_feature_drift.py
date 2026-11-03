"""Feature-drift early warning (hourly item 35, 2026-11-03): PSI/KS of each live sleeve's
session inputs against its certificate's in-sample days, a warning that acts on nothing."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import feature_drift as FD  # noqa: E402

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _bars(days: int = 900, shift_from: str | None = None, seed: int = 0,
          spread: float = 18.0, spread_after: float | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(pd.Timestamp(NOW) - pd.Timedelta(days=days), pd.Timestamp(NOW),
                        freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    vol = np.full(len(idx), 1.0)
    if shift_from is not None:
        vol[idx >= pd.Timestamp(shift_from, tz="UTC")] = 3.0
    close = 2000.0 * np.exp(np.cumsum(rng.normal(0, 0.001, len(idx)) * vol))
    hl = np.abs(rng.normal(0, 1.5, len(idx))) * vol
    sp = np.full(len(idx), spread)
    if spread_after is not None:
        sp[idx >= pd.Timestamp(shift_from or NOW, tz="UTC")] = spread_after
    return pd.DataFrame({"open": close, "high": close + hl, "low": close - hl, "close": close,
                         "tick_volume": rng.poisson(500, len(idx)) * vol, "spread": sp},
                        index=idx)


def _canon(end: str = "2026-03-01T00:00:00+00:00", days: int = 600) -> dict:
    return {"survivors": {"x": {
        "cell": "XAUUSD.session_range_breakout.rr=1.5_wb=12", "days": days, "gated_at": end,
        "shadow_spec": {"symbol": "XAUUSD", "selector": "asia"}}}}


def _run(tmp_path: Path, bars: pd.DataFrame, **kw) -> dict:
    return FD.run(NOW, sleeves_doc={"sleeves": []},
                  retired_gold={"gold_london_am": {}, "gold_afternoon": {}},
                  canon=kw.pop("canon", _canon()), decay_doc=kw.pop("decay_doc", {}),
                  bars={"XAUUSD": bars}, state_path=tmp_path / "state.json",
                  report_path=tmp_path / "FEATURE_DRIFT.json", **kw)


def test_psi_is_debiased_so_no_shift_rarely_crosses_the_bar() -> None:
    rng = np.random.default_rng(1)
    null = np.array([FD.psi(rng.normal(size=500), rng.normal(size=FD.RECENT_DAYS))
                     for _ in range(1500)])
    assert abs(null.mean()) < 0.05
    assert (null > FD.PSI_FLAG).mean() < 0.10
    big = np.array([FD.psi(rng.normal(size=500), rng.normal(1.5, 1, size=FD.RECENT_DAYS))
                    for _ in range(300)])
    assert (big > FD.PSI_FLAG).mean() > 0.9
    assert FD.psi([], [1.0]) is None


def test_ks_matches_its_definition() -> None:
    d, p = FD.ks_2samp([1, 2, 3, 4], [1, 2, 3, 4])
    assert d == 0.0 and p == 1.0
    d, p = FD.ks_2samp(np.arange(100.0), np.arange(100.0) + 1000)
    assert d == pytest.approx(1.0) and p < 1e-6


def test_session_features_read_only_the_window_and_are_causal() -> None:
    b = _bars(days=60)
    f = FD.daily_features(b, "asia")
    later = b.copy()
    later.loc[later.index.hour >= 7, ["high", "low"]] *= [1.5, 0.5]   # outside the window
    f2 = FD.daily_features(later, "asia")
    pd.testing.assert_series_equal(f["session_volume"], f2["session_volume"])
    pd.testing.assert_series_equal(f["spread_points"], f2["spread_points"])
    # the future never moves a past date's row
    cut = f.index[30]
    f3 = FD.daily_features(b[b.index < cut + pd.Timedelta(days=1)], "asia")
    pd.testing.assert_frame_equal(f.loc[:cut], f3.loc[:cut])


def test_a_volatility_shift_flags_the_sleeve(tmp_path: Path) -> None:
    doc = _run(tmp_path, _bars(shift_from="2026-05-05", spread_after=30.0))
    (row,) = doc["sleeves"]
    assert row["name"] == "gold_asia" and row["reference"]["source"] == "certificate"
    assert row["verdict"] == "EDGE_DECAY_CANDIDATE", row
    assert "spread_points" in row["flagged_features"]
    assert doc["decay_accuracy_lead"]["gold_asia"]["feature_drift_first_flag_at"]


def test_a_stable_market_reads_stable(tmp_path: Path) -> None:
    doc = _run(tmp_path, _bars(seed=4))
    (row,) = doc["sleeves"]
    assert row["verdict"] in ("STABLE", "EDGE_DECAY_CANDIDATE")
    assert row["max_psi"] is not None and row["n_recent_days"] >= FD.MIN_RECENT
    assert "spread_points" not in row["flagged_features"]


def test_too_little_history_is_unmeasured_not_stable(tmp_path: Path) -> None:
    doc = _run(tmp_path, _bars(days=40))
    (row,) = doc["sleeves"]
    assert row["verdict"].startswith("UNMEASURED")
    doc = FD.run(NOW, sleeves_doc={"sleeves": []}, retired_gold={}, canon={}, decay_doc={},
                 bars={}, state_path=tmp_path / "s2.json", report_path=tmp_path / "r2.json")
    assert all(r["verdict"].startswith("UNMEASURED") for r in doc["sleeves"])
    assert doc["n_sleeves"] == 3


def test_episodes_open_once_and_close_on_stable(tmp_path: Path) -> None:
    flag = [{"name": "a", "verdict": "EDGE_DECAY_CANDIDATE", "flagged_features": ["atr_frac"],
             "max_psi": 0.4}]
    s = FD.update_state({}, flag, "t1")
    s = FD.update_state(s, flag, "t2")
    assert len(s["a"]["episodes"]) == 1 and s["a"]["episodes"][0]["first_flag_at"] == "t1"
    s = FD.update_state(s, [{"name": "a", "verdict": "UNMEASURED: x"}], "t3")
    assert s["a"]["episodes"][0]["cleared_at"] is None
    s = FD.update_state(s, [{"name": "a", "verdict": "STABLE"}], "t4")
    assert s["a"]["episodes"][0]["cleared_at"] == "t4"
    s = FD.update_state(s, flag, "t5")
    assert len(s["a"]["episodes"]) == 2


def test_the_monitor_never_writes_what_the_book_trades_from(tmp_path: Path,
                                                            monkeypatch) -> None:
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": []}), "utf-8")
    before = sleeves.read_bytes()
    monkeypatch.setattr(FD, "SLEEVES_FILE", sleeves)
    FD.run(NOW, retired_gold={}, canon=_canon(), decay_doc={},
           bars={"XAUUSD": _bars(shift_from="2026-05-05", spread_after=30.0)},
           state_path=tmp_path / "state.json", report_path=tmp_path / "r.json")
    assert sleeves.read_bytes() == before
    written = {p.name for p in tmp_path.iterdir()}
    assert written == {"sleeves.json", "state.json", "r.json"}


def test_the_roster_mirrors_the_gold_book_and_live_rows() -> None:
    doc = {"sleeves": [{"name": "eurusd_x", "symbol": "EURUSD", "status": "LIVE"},
                       {"name": "gold_asia_v2", "symbol": "XAUUSD", "status": "LIVE",
                        "window": "asia"},
                       {"name": "old", "symbol": "GBPUSD", "status": "RETIRED"}]}
    names = [r["name"] for r in FD.live_roster(doc, {"gold_afternoon": {}})]
    assert names == ["gold_asia", "gold_london_am", "eurusd_x"]


def test_feature_drift_is_a_contracted_hourly_leg() -> None:
    import hourly_cycle as HC

    from libs.research import layers
    assert "feature_drift" in HC.CORE_LEGS
    assert layers.LEG_LAYER["feature_drift"] == "portfolio"
    root = _DESK.parents[1]
    legs = json.loads((root / "docs/research/experiment_contracts.json").read_text())["legs"]
    assert "feature_drift" in legs
