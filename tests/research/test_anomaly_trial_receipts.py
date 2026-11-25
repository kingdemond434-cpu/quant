"""Anomaly receipts count the searched population without claiming certification."""
import json

import numpy as np
import pandas as pd
import pytest

from libs.research import anomaly_miner as am


def bars(n=1800, seed=14, drift=0.001):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.001, n)))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close}, index=pd.date_range("2025-01-01", periods=n,
                                                               freq="h", tz="UTC"))


def test_effective_sample_and_every_failed_trial_are_receipted(monkeypatch):
    frame = bars()
    masks = {"all": np.ones(len(frame), dtype=bool), "too_thin": np.arange(len(frame)) < 3}
    monkeypatch.setattr(am, "_conditions", lambda *_: masks)
    found, trials = am.scan_symbol("USDJPY", frame)
    assert trials == len(masks) * len(am.HORIZONS)
    assert found
    for anomaly in found:
        fwd = frame.close.shift(-anomaly.horizon) / frame.close - 1
        observed = fwd.dropna().to_numpy()
        effective = len(observed) / anomaly.horizon
        expected = observed.mean() / (observed.std(ddof=1) / np.sqrt(effective))
        assert anomaly.n == int(effective)
        assert anomaly.t_stat == pytest.approx(expected, abs=0.00051)
        receipt = anomaly.as_row()
        assert receipt["mechanism_status"] == "UNNAMED" and receipt["kind"] == "anomaly"
        assert "not a candidate" in receipt["note"]
    assert am.scan_symbol("USDJPY", frame[:100]) == ([], 0)
    assert am.scan_symbol("USDJPY", None) == ([], 0)
    flat = frame.copy()
    flat["close"] = 100.0
    assert am.scan_symbol("USDJPY", flat) == ([], trials)


def test_canonical_primitive_conditions_are_causal(monkeypatch):
    from research import acquire_datasets

    monkeypatch.setattr(acquire_datasets, "acquired_series", lambda _: {})
    original = bars(1500, drift=0)
    perturbed = original.copy()
    perturbed.iloc[1000:] *= 7
    left = am._conditions(original, "USDJPY")
    right = am._conditions(perturbed, "USDJPY")
    assert left
    for name in set(left) & set(right):
        np.testing.assert_array_equal(left[name][:1000], right[name][:1000])
        assert not left[name][:199].any()


def test_aligned_cross_trials_include_unreported_nulls():
    first = bars(1900, 1, 0)
    second = bars(1900, 2, 0)
    rows, trials = am.scan_cross_section({"USDJPY": first, "CHFSGD": second})
    assert trials == 6
    assert all(row["kind"] == "anomaly" and row["mechanism_status"] == "UNNAMED"
               for row in rows)
    assert am.scan_cross_section({"a": first[:100], "b": second[:100]}) == ([], 0)
    assert am.scan_cross_section({"a": first, "b": second}, max_pairs=0) == ([], 0)
    # Shared timestamps, rather than equal lengths, determine whether the test exists.
    shifted = second.copy()
    shifted.index += pd.Timedelta(days=200)
    assert am.scan_cross_section({"a": first, "b": shifted}) == ([], 0)


def test_lagged_driver_is_reported_as_unnamed_not_certified():
    rng = np.random.default_rng(65)
    driver = rng.normal(0, 0.001, 1800)
    target = np.r_[0, driver[:-1]] + rng.normal(0, 0.00001, 1800)
    index = pd.date_range("2025-01-01", periods=1800, freq="h", tz="UTC")
    frames = {"A": pd.DataFrame({"close": np.exp(np.cumsum(target))}, index=index),
              "B": pd.DataFrame({"close": np.exp(np.cumsum(driver))}, index=index)}
    rows, trials = am.scan_cross_section(frames)
    lead = [r for r in rows if r["condition"] == "lead_lag_B_lag1"]
    assert trials == 6 and lead and lead[0]["corr"] > 0.99
    assert "may never be traded" in lead[0]["question"]


def test_rotating_scan_delivers_owned_parquet_and_explicit_bad_file(tmp_path, monkeypatch):
    monkeypatch.setattr(am, "_BARS", tmp_path / "bars")
    monkeypatch.setattr(am, "_OUT", tmp_path / "out")
    monkeypatch.setattr(am, "_CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(am, "_SCAN_PER_RUN", 2)
    monkeypatch.setattr(am, "_conditions", lambda frame, _: {
        "all": np.ones(len(frame), dtype=bool)})
    am._BARS.mkdir()
    for i, symbol in enumerate(("AUDNZD", "CHFSGD", "USDJPY")):
        bars(seed=i).to_parquet(am._BARS / f"{symbol}_H1.parquet")
    (am._BARS / "ZZBAD_H1.parquet").write_bytes(b"broken footer")
    first = am.scan()
    second = am.scan()
    assert first["symbols_scanned"] == 2
    assert second["symbols_scanned"] == 1 and second["symbols_skipped"][0]["symbol"] == "ZZBAD"
    assert first["universe_coverage"]["symbols_with_bars"] == 4
    assert first["trials"] == 2 * len(am.HORIZONS) + first["cross_sectional_trials"]
    assert all(r["selection_trials"] == len(am.HORIZONS)
               for r in first["anomalies"] if "selection_trials" in r)
    receipt = json.loads(next(am._OUT.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["honesty"]["trials_counted"] == second["trials"]
    assert am.scan(symbols=["USDJPY"], limit=1)["symbols_scanned"] == 1
    am._CURSOR.write_text("invalid", encoding="utf-8")
    assert am._cursor_take(["a", "b", "c"], 2) == ["a", "b"]
    assert am._cursor_take(["a", "b", "c"], 2) == ["c", "a"]
    assert am._cursor_take([], 2) == []
