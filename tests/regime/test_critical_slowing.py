"""Critical slowing down (GAP_MAP row 40): the indicators, the state labels and the organ.

The decisive case is the textbook one: an AR(1) process whose coefficient drifts toward 1 shows
rising lag-1 autocorrelation and variance, while white noise does not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import critical_slowing as cs  # noqa: E402


def _approaching_transition(n: int = 400, seed: int = 1) -> list[float]:
    rng = np.random.default_rng(seed)
    phi = np.linspace(0.0, 0.97, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi[i] * x[i - 1] + rng.normal(0, 0.01)
    return [float(v) for v in x]


def test_kendall_tau_reads_a_monotone_trend() -> None:
    assert cs.kendall_tau(list(range(20))) == 1.0
    assert cs.kendall_tau(list(range(20, 0, -1))) == -1.0
    assert np.isnan(cs.kendall_tau([1.0, 2.0]))


def test_bimodality_coefficient_separates_two_basins_from_one() -> None:
    rng = np.random.default_rng(3)
    one = rng.normal(0, 1, 2000)
    two = np.concatenate([rng.normal(-3, 0.5, 1000), rng.normal(3, 0.5, 1000)])
    for x, bimodal in ((one, False), (two, True)):
        _var, skew, kurt = cs._moments(x - x.mean())
        bc = cs.bimodality_coefficient(skew, kurt, len(x))
        assert (bc > cs.BIMODAL_BC) is bimodal


def test_an_ar1_drifting_to_one_warns_and_white_noise_does_not() -> None:
    near = cs.early_warning(_approaching_transition(), surrogates=40)
    assert near["state"] in {"WARNING", "RISING"}
    assert "ar1" in near["rising"]
    assert near["tau"]["ar1"] >= cs.TAU_RISING and near["p_surrogate"]["ar1"] <= cs.SURROGATE_P
    noise = cs.early_warning(list(np.random.default_rng(7).normal(0, 0.01, 400)),
                             surrogates=40)
    assert noise["state"] == "CALM"


def test_too_little_tape_is_unmeasured_never_calm() -> None:
    out = cs.early_warning([0.01] * 50)
    assert out["state"] == "UNMEASURED" and out["n_obs"] == 50


def test_point_in_time_only_the_trailing_tape_is_read() -> None:
    x = _approaching_transition()
    need = cs.WINDOW + cs.TREND_WINDOWS - 1
    a = cs.early_warning(x, surrogates=20)
    b = cs.early_warning([0.5] * 100 + x[-need:], surrogates=20)
    assert a["tau"] == b["tau"] and a["state"] == b["state"]


def test_the_organ_writes_its_report_and_names_what_it_could_not_measure(tmp_path,
                                                                         monkeypatch) -> None:
    import critical_slowing_state as org
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    idx = pd.date_range("2025-01-01", periods=24 * 330, freq="h")
    close = np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.002, len(idx)))) * 1.1
    pd.DataFrame({"close": close}, index=idx).to_parquet(uni / "EURUSD_H1.parquet")
    pd.DataFrame({"close": close[:24 * 20]}, index=idx[:24 * 20]).to_parquet(
        uni / "GBPUSD_H1.parquet")
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"symbol": "EURUSD", "status": "LIVE"}, {"symbol": "XAUUSD", "status": "RETIRED"}]}))
    monkeypatch.setattr(org, "DESK", tmp_path)
    monkeypatch.setattr(org, "hypothesis_symbols", lambda: ["EURUSD", "GBPUSD", "USDJPY"])
    assert org.main(["--budget-s", "120"]) == 0
    doc = json.loads((tmp_path / "reports" / "CRITICAL_SLOWING.json").read_text())
    assert doc["symbols"]["EURUSD"]["state"] in {"CALM", "RISING", "WARNING"}
    assert doc["symbols"]["GBPUSD"]["state"] == "UNMEASURED"
    assert doc["symbols"]["USDJPY"] == {"state": "UNMEASURED",
                                        "why": "no readable H1/D1 bar file"}
    assert doc["book"]["symbols"] == ["EURUSD"]
    assert doc["book"]["state"] in {"CALM", "RISING", "WARNING"}
    assert "NOT WIRED" in doc["consumers"]["allocator_state_input"]


def test_the_leg_is_on_a_clock_with_a_layer_and_a_budget() -> None:
    import hourly_cycle as hc

    from libs.research import layers
    assert hc.LEG_BUDGET_SEC["critical_slowing"] >= 280
    assert hc.department_of("critical_slowing") == "macro"
    assert hc.in_plan("critical_slowing", "heavy")
    assert layers.LEG_LAYER["critical_slowing"] == "information"


def test_the_vectorised_windows_match_the_scalar_definitions() -> None:
    r = np.random.default_rng(11).normal(0, 1, 90)
    ind = cs.rolling_indicators(list(r), 60)
    for i in (0, 13, 30):
        x = r[i:i + 60] - r[i:i + 60].mean()
        var, skew, kurt = cs._moments(x)
        assert np.isclose(ind["ar1"][i], cs._ar1(x))
        assert np.isclose(ind["variance"][i], var)
        assert np.isclose(ind["skew_abs"][i], abs(skew))
        assert np.isclose(ind["bimodality"][i], cs.bimodality_coefficient(skew, kurt, 60))
    flat = cs.rolling_indicators([0.0] * 70, 60)
    assert np.all(flat["variance"] == 0) and np.all(np.isnan(flat["ar1"]))
