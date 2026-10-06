"""Macro state must fail closed. Absence is never neutral.

The defect this module was written against is III.16 -- a macro vector
computed 24/7 and read by nothing. The defect these tests are written
against is the one that replaces it if the wiring is careless: a STALE macro
vector read as current, which is silent, looks exactly like a healthy read,
and quietly conditions every decision on a world that has moved on.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mt5desk import macro_regime as mr

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _write(tmp_path, updated, states):
    p = tmp_path / "macro_state.json"
    doc = {"states": states}
    if updated is not None:
        doc["updated"] = updated.isoformat()
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_missing_file_is_unusable(tmp_path):
    m = mr.load(tmp_path / "nope.json", now=NOW)
    assert not m.usable
    assert "absent" in m.detail
    assert "UNMEASURED" in m.render()


def test_fresh_state_usable(tmp_path):
    p = _write(tmp_path, NOW - timedelta(hours=2), {"DOLLAR_STATE": 0.805})
    m = mr.load(p, now=NOW)
    assert m.usable and not m.stale
    assert m.get("DOLLAR_STATE") == pytest.approx(0.805)
    assert "+0.805" in m.render()


def test_stale_state_fails_closed_and_hides_its_values(tmp_path):
    """A stale value must not reach a caller OR the rendered block."""
    p = _write(tmp_path, NOW - timedelta(hours=mr.DEFAULT_MAX_AGE_H + 1),
               {"DOLLAR_STATE": 0.805})
    m = mr.load(p, now=NOW)
    assert m.stale and not m.usable
    assert m.get("DOLLAR_STATE") is None
    assert "0.805" not in m.render()


def test_get_never_defaults_to_zero(tmp_path):
    """0.0 would read as a measured neutral at every call site (L1.28a)."""
    p = _write(tmp_path, NOW, {"DOLLAR_STATE": 0.805})
    assert mr.load(p, now=NOW).get("NOT_A_SERIES") is None


def test_missing_timestamp_is_not_fresh(tmp_path):
    p = _write(tmp_path, None, {"DOLLAR_STATE": 0.805})
    m = mr.load(p, now=NOW)
    assert not m.usable
    assert "UNKNOWN" in m.detail


def test_unparseable_json_is_unusable(tmp_path):
    p = tmp_path / "macro_state.json"
    p.write_text("{oops", encoding="utf-8")
    assert not mr.load(p, now=NOW).usable


def test_naive_timestamp_treated_as_utc(tmp_path):
    """A tz-naive stamp must not silently shift the age by the host offset."""
    p = tmp_path / "macro_state.json"
    p.write_text(json.dumps({"updated": "2026-08-22T10:00:00", "states": {}}),
                 encoding="utf-8")
    m = mr.load(p, now=NOW)
    assert m.age_hours == pytest.approx(2.0, abs=0.01)


def test_real_rate_needs_both_inputs(tmp_path):
    p = _write(tmp_path, NOW, {"POLICY_RATE": 3.75})
    assert mr.load(p, now=NOW).real_rate is None
    p2 = _write(tmp_path, NOW, {"POLICY_RATE": 3.75, "INFLATION_STATE": 1.136})
    assert mr.load(p2, now=NOW).real_rate == pytest.approx(2.614)


def test_is_fresh_matches_usable(tmp_path):
    """is_fresh() has no now= parameter (unlike load()) -- it always evaluates against real
    wall-clock time, so this test writes against real now too, not the module's fixed NOW
    constant. Using NOW here was a ticking bug: NOW is a hardcoded calendar date (2026-08-22),
    and is_fresh() silently started reading it as stale the moment enough real time passed
    (caught live 2026-08-26), with no error anywhere -- exactly the class of silent staleness
    this whole module exists to catch, just in the test harness instead of production."""
    real_now = datetime.now(timezone.utc)
    p = _write(tmp_path, real_now, {"X": 1.0})
    assert mr.is_fresh(p) is True
    old = _write(tmp_path, real_now - timedelta(days=30), {"X": 1.0})
    assert mr.is_fresh(old) is False


def test_load_history_absent_returns_none(tmp_path):
    assert mr.load_history(tmp_path / "nope.pkl") is None


def _anchors(tmp_path, *, breakeven_nan=False, days=1500):
    """A small synthetic cross_asset_anchors history, so the loader is tested on inputs the test
    controls rather than on whatever the last box-side refresh left in data/."""
    import numpy as np
    import pandas as pd

    idx = pd.bdate_range("2019-01-01", periods=days)
    t = np.arange(days, dtype=float)
    df = pd.DataFrame({
        "DGS10": 2.5 + 0.5 * np.sin(t / 90.0),
        "T10YIE": np.nan if breakeven_nan else 2.0 + 0.2 * np.cos(t / 120.0),
        "VIX": 18.0 + np.sin(t / 30.0),
    }, index=idx)
    p = tmp_path / "cross_asset_anchors.pkl"
    df.to_pickle(p)
    return p


def test_load_history_adds_real_yield(tmp_path):
    """The real yield is the derived column the whole macro case rests on."""
    h = mr.load_history(_anchors(tmp_path))
    assert h is not None
    assert "REAL_YIELD_10Y" in h.columns
    assert h.attrs["unmeasured"] == {}
    ry = h["REAL_YIELD_10Y"].dropna()
    assert len(ry) > 1000
    # It is nominal minus breakeven, row for row -- not an ordinal index.
    assert (ry - (h["DGS10"] - h["T10YIE"]).dropna()).abs().max() < 1e-12
    # Sanity: a 10y real yield outside [-5%, +5%] means the inputs are not
    # what this column claims they are.
    assert ry.min() > -5.0 and ry.max() < 5.0


def test_load_history_with_no_breakeven_observation_is_unmeasured_not_empty(tmp_path):
    """T10YIE present but all-NaN (the committed pickle, 2026-09-30) must not attach an all-NaN
    REAL_YIELD_10Y that reads as present; the column is withheld and the reason is carried."""
    h = mr.load_history(_anchors(tmp_path, breakeven_nan=True))
    assert h is not None
    assert "REAL_YIELD_10Y" not in h.columns
    reason = h.attrs["unmeasured"]["REAL_YIELD_10Y"]
    assert reason.startswith("UNMEASURED") and "T10YIE" in reason


def test_load_history_on_this_clone_is_measured_or_says_why():
    """Whatever the box last wrote to data/: either a real yield with history, or UNMEASURED."""
    h = mr.load_history()
    if h is None:
        pytest.skip("cross_asset_anchors.pkl absent on this clone (data/ gitignored)")
    if "REAL_YIELD_10Y" in h.columns:
        assert len(h["REAL_YIELD_10Y"].dropna()) > 0
    else:
        assert h.attrs["unmeasured"]["REAL_YIELD_10Y"].startswith("UNMEASURED")
