"""The state vector must describe the world honestly, including the parts it does not know.

Two properties carry the weight. A missing asset state must be RECORDED as missing rather than
quietly replaced by the global one -- otherwise gold's regime masquerades as GBPUSD's and no
consumer can tell. And the id must be stable across passes that describe the same world, or it
identifies nothing and cannot be stamped on an order.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.asset_state import CLOCKS, AssetState, FitCache, cache_key, fit_asset_state  # noqa: E402
from libs.regime.state_vector import StateVector  # noqa: E402
from research import state_vector_build as svb  # noqa: E402


def _state(sym: str = "XAUUSD", clock: str = "daily", top: str = "trend",
           age: int = 5) -> AssetState:
    probs = {top: 0.7, "range": 0.2, "stress": 0.1}
    return AssetState(symbol=sym, clock=clock, labels=tuple(sorted(probs)), probs=probs,
                      filtered=dict(probs), age_bars=age, p_leave={1: 0.1},
                      entropy={1: 0.4}, duration_weight=0.6, n_obs=900,
                      last_bar="2026-09-04", engine_confidence=0.7)


def _series(n: int = 900, seed: int = 3) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n * 24, freq="h", tz="UTC")
    px = np.exp(np.cumsum(rng.normal(scale=0.001, size=idx.size))) * 100
    return pd.Series(px, index=idx)


# ------------------------------------------------------------------------------------------
# The container
# ------------------------------------------------------------------------------------------

def test_a_missing_asset_state_is_a_recorded_gap_not_a_silent_substitution():
    sv = StateVector(at=datetime.now(tz=UTC).isoformat(), global_state=_state(),
                     assets={"EURUSD@daily": _state("EURUSD", top="range")},
                     gaps={"asset:GBPUSD@daily": "no H1 parquet for GBPUSD"})
    assert sv.asset("EURUSD").top == "range"
    # The fallback is available, but the gap says out loud that it IS a fallback.
    assert sv.asset("GBPUSD") is sv.global_state
    assert "asset:GBPUSD@daily" in sv.gaps


def test_the_id_is_stable_across_passes_describing_the_same_world():
    a = StateVector(at="2026-09-04T10:00:00+00:00", global_state=_state())
    b = StateVector(at="2026-09-04T10:05:00+00:00", global_state=_state())
    assert a.id == b.id, "the id must not change merely because time passed"


def test_the_id_moves_when_the_world_does():
    a = StateVector(at="2026-09-04T10:00:00+00:00", global_state=_state(top="trend"))
    b = StateVector(at="2026-09-04T10:00:00+00:00", global_state=_state(top="stress"))
    c = StateVector(at="2026-09-04T10:00:00+00:00", global_state=_state(),
                    session={"phase": "london_open"})
    assert len({a.id, b.id, c.id}) == 3


def test_the_id_ignores_noise_below_the_rounding():
    base = _state()
    jittered = AssetState(**{**base.__dict__,
                             "probs": {k: v + 0.0009 for k, v in base.probs.items()}})
    a = StateVector(at="t", global_state=base)
    b = StateVector(at="t", global_state=jittered)
    assert a.id == b.id, "an id that moves on the fourth decimal identifies nothing"


def test_bucket_names_a_bucket_for_every_requested_dimension():
    sv = StateVector(at="t", global_state=_state(top="trend"),
                     factors={"USD": _state("USDX", top="strengthening")},
                     session={"phase": "london_open"}, event={"phase": "PRE"},
                     liquidity={"state": "wide"})
    assert sv.bucket("global", "session") == "trend|london_open"
    assert sv.bucket("USD", "event", "liquidity") == "USD:strengthening|PRE|wide"
    assert sv.bucket("nonexistent") == "?"


def test_round_trips_through_json():
    sv = StateVector(at=datetime.now(tz=UTC).isoformat(), global_state=_state(),
                     assets={"EURUSD@H4": _state("EURUSD", "H4")},
                     factors={"USD": _state("USDX")},
                     session={"phase": "ny_open"}, event={"phase": "NORMAL"},
                     liquidity={"state": "normal"}, gaps={"x": "y"})
    back = StateVector.from_dict(json.loads(json.dumps(sv.to_dict(), default=str)))
    assert back.id == sv.id
    assert back.assets["EURUSD@H4"].top == sv.assets["EURUSD@H4"].top
    assert back.gaps == sv.gaps


def test_age_is_measured_and_a_missing_stamp_is_infinitely_old():
    fresh = StateVector(at=datetime.now(tz=UTC).isoformat())
    assert fresh.age_seconds() < 5
    assert StateVector(at="not a timestamp").age_seconds() == float("inf")


def test_a_stale_artifact_is_refused_rather_than_used(tmp_path, monkeypatch):
    """Conditioning on yesterday's world is worse than conditioning on nothing."""
    old = StateVector(at=(datetime.now(tz=UTC) - timedelta(hours=9)).isoformat(),
                      global_state=_state())
    path = tmp_path / "sv.json"
    path.write_text(json.dumps(old.to_dict(), default=str), "utf-8")
    monkeypatch.setattr(svb, "OUT", path)
    sv, why = svb.load(max_age_s=7200)
    assert sv is None and "old" in why
    sv, why = svb.load(max_age_s=50 * 3600)
    assert sv is not None and sv.id == old.id


# ------------------------------------------------------------------------------------------
# The fits
# ------------------------------------------------------------------------------------------

def test_every_clock_declares_its_own_windows_and_horizons():
    for clock, spec in CLOCKS.items():
        assert spec["min_obs"] < spec["max_obs"]
        assert spec["horizons"] and all(h > 0 for h in spec["horizons"])


def test_too_little_history_refuses_with_a_reason():
    short = _series(n=20)
    st, why = fit_asset_state(short, "TEST", "daily")
    assert st is None
    assert "needs" in why


def test_a_constant_series_refuses_rather_than_fitting_a_regime_to_nothing():
    idx = pd.date_range("2020-01-01", periods=900 * 24, freq="h", tz="UTC")
    st, why = fit_asset_state(pd.Series(100.0, index=idx), "FLAT", "daily")
    assert st is None
    assert "constant" in why


def test_an_unknown_clock_refuses():
    st, why = fit_asset_state(_series(), "TEST", "M3")
    assert st is None and "unknown clock" in why


def test_the_cache_key_moves_with_the_last_bar_and_not_with_the_wall_clock():
    s = _series().groupby(_series().index.date).last()
    k1 = cache_key("X", "daily", s)
    k2 = cache_key("X", "daily", s)
    k3 = cache_key("X", "daily", s.iloc[:-1])
    assert k1 == k2 != k3


def test_the_cache_keeps_a_fit_and_hands_it_back(tmp_path):
    cache = FitCache(path=tmp_path / "fits.json")
    s = _series(n=400)
    first, why1 = fit_asset_state(s, "TEST", "daily", cache=cache)
    if first is None:
        pytest.skip(f"engine cannot fit here: {why1}")
    cache.flush()
    again = FitCache(path=tmp_path / "fits.json")
    second, why2 = fit_asset_state(s, "TEST", "daily", cache=again)
    assert why2 == "cached"
    assert second is not None and second.top == first.top
    assert second.probs == first.probs


# ------------------------------------------------------------------------------------------
# The producer
# ------------------------------------------------------------------------------------------

def test_the_book_scopes_the_asset_fits():
    """Fitting regimes for instruments nobody holds spends the budget on nobody's question."""
    syms = svb.book_symbols()
    assert isinstance(syms, list)
    assert all(isinstance(s, str) and s.isupper() for s in syms)


def test_an_exhausted_budget_is_recorded_rather_than_silently_truncating():
    sv = svb.build(budget_s=-1.0, symbols=["XAUUSD"])
    assert sv.gaps, "a build that fitted nothing must say why"
    assert any("budget" in v for v in sv.gaps.values())


def test_event_phases_are_the_five_the_desk_reasons_about():
    ev, why = svb.event_state(datetime.now(tz=UTC))
    if why:
        pytest.skip(why)
    assert ev["phase"] in {"PRE", "SHOCK", "DISCOVERY", "DRIFT", "NORMAL"}


def test_liquidity_reports_a_state_or_says_it_is_unmeasured():
    liq, why = svb.liquidity_state(["XAUUSD"])
    if why:
        pytest.skip(why)
    assert liq["state"] in {"cheap", "normal", "wide", "toxic", "UNMEASURED"}
