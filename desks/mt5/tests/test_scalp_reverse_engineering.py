from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from desks.mt5.research import scalp_reverse_engineering as scalp


def test_four_entries_share_one_basket_risk() -> None:
    stop = 99.0
    entries = [100.0, 100.5, 101.0, 101.5]
    units = [scalp.risk_sized_units(p, stop, 0.25) for p in entries]
    worst = sum(u * (p - stop) for p, u in zip(entries, units, strict=True))
    assert worst == pytest.approx(1.0)


def test_invalid_risk_geometry_is_refused() -> None:
    with pytest.raises(ValueError):
        scalp.risk_sized_units(100.0, 100.0, 0.25)
    with pytest.raises(ValueError):
        scalp.risk_sized_units(100.0, 99.0, 1.25)


@pytest.mark.parametrize("values", [None, [float("nan")], [-1], [float("inf")], ["bad"]])
def test_missing_or_invalid_spreads_are_never_free(values):
    frame = pd.DataFrame({"close": [100]})
    if values is not None:
        frame["spread"] = values
    with pytest.raises(ValueError):
        scalp.measured_spreads(frame)


def test_measured_zero_spread_is_distinct_from_missing():
    assert scalp.measured_spreads(pd.DataFrame({"spread": [0, 20]})).tolist() == [0, 0.2]


def test_same_bar_stop_and_target_is_scored_stop_first(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2026-01-01", periods=70, freq="min", tz="UTC")
    df = pd.DataFrame({
        "open": np.full(70, 100.0), "high": np.full(70, 100.2),
        "low": np.full(70, 99.8), "close": np.full(70, 100.0),
        "spread": np.zeros(70),
    }, index=idx)
    # One long entry at bar 45. The following bar crosses both fixed levels.
    signals = np.zeros(70, dtype=np.int8)
    signals[45] = 1
    atr = np.ones(70)
    df.iloc[46, df.columns.get_loc("low")] = 98.0
    df.iloc[46, df.columns.get_loc("high")] = 102.0
    monkeypatch.setattr(scalp, "_signals", lambda *_: signals)
    monkeypatch.setattr(scalp, "_atr", lambda *_: atr)
    cfg = scalp.Config("sweep_reclaim", 20, 1.5, 1.0, 1.0, 5, "single")
    returns = scalp.simulate(df, cfg, cost="frictionless")
    assert returns[0] == pytest.approx(-1.0)


def test_executable_replay_holds_the_bracket_from_the_fill_bar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The fill bar runs through the stop and then recovers to the target. The study arm never
    looks at the fill bar and books a win; the executor's bracket is resting, so it is a loss."""
    idx = pd.date_range("2026-01-01", periods=70, freq="min", tz="UTC")
    df = pd.DataFrame({
        "open": np.full(70, 100.0), "high": np.full(70, 100.2),
        "low": np.full(70, 99.8), "close": np.full(70, 100.0),
        "spread": np.zeros(70),
    }, index=idx)
    signals = np.zeros(70, dtype=np.int8)
    signals[45] = 1
    df.iloc[45, df.columns.get_loc("low")] = 98.5      # fill bar pierces the 1.0 stop
    df.iloc[46, df.columns.get_loc("high")] = 102.0    # next bar reaches the target
    monkeypatch.setattr(scalp, "_signals", lambda *_: signals)
    monkeypatch.setattr(scalp, "_atr", lambda *_: np.ones(70))
    cfg = scalp.Config("sweep_reclaim", 20, 1.5, 1.0, 1.0, 5, "single")
    assert scalp.simulate(df, cfg, cost="frictionless")[0] == pytest.approx(1.0)
    assert scalp.simulate(df, cfg, cost="frictionless", executable=True)[0] == pytest.approx(-1.0)


def test_executable_replay_sizes_the_stop_from_the_last_closed_bar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2026-01-01", periods=70, freq="min", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0,
                       "spread": 0.0}, index=idx)
    signals = np.zeros(70, dtype=np.int8)
    signals[45] = 1
    atr = np.ones(70)
    atr[45] = 5.0                                      # bar 45's own range: unknowable at its open
    df.iloc[47, df.columns.get_loc("low")] = 98.5
    monkeypatch.setattr(scalp, "_signals", lambda *_: signals)
    monkeypatch.setattr(scalp, "_atr", lambda *_: atr)
    cfg = scalp.Config("sweep_reclaim", 20, 1.5, 1.0, 1.0, 5, "single")
    study = scalp.simulate(df, cfg, cost="frictionless", detailed=True)
    live = scalp.simulate(df, cfg, cost="frictionless", detailed=True, executable=True)
    assert study[0]["r"] > -1.0                        # a 5.0 stop survives the dip
    assert live[0]["r"] == pytest.approx(-1.0)         # the 1.0 stop the executor placed does not


def test_no_intraday_bars_is_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scalp, "DATA", tmp_path / "absent")
    monkeypatch.setattr(scalp, "OUT", tmp_path / "report.json")
    report = scalp.run()
    assert report["verdict"].startswith("REJECTED")
    assert all(v["status"] == "UNMEASURED" for v in report["timeframes"].values())
    assert report["shadow_candidates"] == []


def test_detailed_records_expose_one_basket_not_fake_ticket_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    idx = pd.date_range("2026-01-01", periods=70, freq="min", tz="UTC")
    df = pd.DataFrame({
        "open": np.full(70, 100.0), "high": np.full(70, 100.2),
        "low": np.full(70, 99.8), "close": np.full(70, 100.0),
        "spread": np.zeros(70),
    }, index=idx)
    signals = np.zeros(70, dtype=np.int8)
    signals[45] = 1
    df.iloc[46, df.columns.get_loc("high")] = 102.0
    monkeypatch.setattr(scalp, "_signals", lambda *_: signals)
    monkeypatch.setattr(scalp, "_atr", lambda *_: np.ones(70))
    cfg = scalp.Config("sweep_reclaim", 20, 1.5, 1.0, 1.0, 5, "bounded_structural")
    records = scalp.simulate(df, cfg, cost="frictionless", detailed=True)
    assert len(records) == 1
    assert records[0]["depth"] == 1
    assert records[0]["risk_allocated_r"] == 0.25


def test_video_descendant_waits_for_sweep_fvg_retrace() -> None:
    idx = pd.date_range("2026-01-01", periods=30, freq="min", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0] * 30, "high": [100.3] * 30,
        "low": [99.7] * 30, "close": [100.0] * 30,
    }, index=idx)
    # Bar 20 sweeps low; bar 21 displaces and leaves an FVG; bar 22 defines the completed
    # imbalance and bar 23 retraces into it, so the earliest executable signal is bar 24.
    df.iloc[20] = [99.6, 100.2, 98.8, 100.0]
    df.iloc[21] = [100.0, 102.0, 100.7, 101.8]
    df.iloc[22] = [101.2, 101.4, 100.4, 101.1]
    cfg = scalp.Config("sweep_fvg_retrace", 2, 1.0, 1.0, 1.0, 5, "single")
    sig = scalp._signals(df, cfg)
    assert sig[24] == 1
    assert not sig[:24].any()


def test_psr_screen_never_claims_shadow_authority() -> None:
    source = Path(scalp.__file__).read_text(encoding="utf-8")
    assert '"GAUNTLET_REQUIRED"' in source
    assert 'report["shadow_candidates"] = []' in source
