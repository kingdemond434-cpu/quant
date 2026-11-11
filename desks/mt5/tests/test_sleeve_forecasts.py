"""Sleeve forecast ledger, calibration and the anytime-valid outcome test (ALLOC-08/24/28,
DECAY-05/07)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sf = pytest.importorskip("research.sleeve_forecasts", reason="ships with the desk")


def _daily(n: int = 200, seed: int = 0, mus=(0.1, 0.0, -0.2)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D").strftime("%Y-%m-%d")
    return pd.DataFrame({f"s{i}": mu + rng.normal(0, 1, n) for i, mu in enumerate(mus)},
                        index=idx)


def _rows_fn(post_mean):
    def fn(daily):
        names = list(daily.columns)
        return sf.make_rows(names, daily, {n: post_mean[n] for n in names},
                            dict.fromkeys(names, 0.02), cost_r=dict.fromkeys(names, 0.05),
                            version="test")
    return fn


def test_rows_carry_every_named_field() -> None:
    d = _daily()
    rows = _rows_fn({"s0": 0.1, "s1": 0.0, "s2": -0.2})(d)
    r = rows[0]
    for k in ("forecast_id", "sleeve", "model", "model_version", "info_cutoff", "horizon_days",
              "expiry", "expected_r", "mean_se", "predictive_sd", "n_obs", "n_eff", "regime",
              "cost_r_horizon", "corr_to_book"):
        assert k in r, k
    assert r["info_cutoff"] == d.index[-1] and r["expected_r"] == pytest.approx(0.5)
    assert r["predictive_sd"] > r["mean_se"] > 0


def test_ledger_is_append_only_and_deduplicated(tmp_path) -> None:
    led = tmp_path / "f.jsonl"
    rows = _rows_fn({"s0": 0.1, "s1": 0.0, "s2": -0.2})(_daily())
    assert sf.append_new(rows, led) == 3
    assert sf.append_new(rows, led) == 0
    assert len(sf.read_ledger(led)) == 3


def test_scoring_waits_for_maturity_and_computes_pits() -> None:
    d = _daily(120)
    early = _rows_fn({"s0": 0.1, "s1": 0.0, "s2": -0.2})(d.iloc[:100])
    assert sf.score(early, d.iloc[:103]) == []                # horizon not in the matrix yet
    scored = sf.score(early, d)
    assert len(scored) == 3 and all(0.0 <= r["pit"] <= 1.0 for r in scored)
    s0 = next(r for r in scored if r["sleeve"] == "s0")
    assert s0["realized_r"] == pytest.approx(float(d["s0"].iloc[100:105].sum()))


def test_e_process_is_flat_under_calibration_and_grows_on_optimism() -> None:
    rng = np.random.default_rng(3)
    calm = [sf.e_value(rng.uniform(0, 1, 200)) for _ in range(200)]
    assert np.mean(calm) < 1.6                    # a supermartingale: mean <= 1 up to noise
    assert np.mean([c >= 1 / sf.ALPHA for c in calm]) <= sf.ALPHA
    optimistic = sf.e_value(rng.beta(1.0, 3.0, 60))          # PIT piled low: worse than said
    assert optimistic > 1 / sf.ALPHA


def test_overlapping_daily_forecasts_keep_the_error_rate(
        ) -> None:
    """Daily forecasts over 5-day windows overlap by 4 days; the judged e-process must still hold
    its level under a calibrated model (rejection rate <= alpha over many seeds)."""
    from math import erf, sqrt
    rejections = 0
    seeds = 300
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        x = rng.normal(0, 1, 260)
        idx = [f"d{i:04d}" for i in range(260)]
        rows = []
        for i in range(len(x) - 5):
            real = float(x[i + 1:i + 6].sum())
            pit = 0.5 * (1 + erf(real / sqrt(5.0) / sqrt(2.0)))
            rows.append({"sleeve": "s", "info_cutoff": idx[i], "outcome_end": idx[i + 5],
                         "pit": pit})
        if sf.judge(rows)["per_sleeve"]["s"]["verdict"] == "WORSE_THAN_FORECAST":
            rejections += 1
    assert rejections / seeds <= sf.ALPHA + 0.02
    assert len(sf.non_overlapping(rows)) == pytest.approx(len(rows) / 5, abs=1)


def test_late_rows_are_not_point_in_time() -> None:
    assert sf._point_in_time({"info_cutoff": "2026-01-02", "published_utc": "2026-01-04T00:00"})
    assert not sf._point_in_time({"info_cutoff": "2026-01-02",
                                  "published_utc": "2026-01-09T00:00"})


def test_e_bh_controls_across_sleeves() -> None:
    assert sf.e_bh({"a": 500.0, "b": 1.0, "c": 0.5}, 0.05) == ["a"]
    assert sf.e_bh({"a": 10.0, "b": 10.0}, 0.05) == []
    assert sf.e_bh({}, 0.05) == []


def test_research_requests_flag_cost_and_uncertainty() -> None:
    rows = [{"sleeve": "x", "expected_r": 0.01, "cost_r_horizon": 0.05, "predictive_sd": 1.0,
             "mean_se": 0.1},
            {"sleeve": "y", "expected_r": 0.5, "cost_r_horizon": 0.0, "predictive_sd": 1.0,
             "mean_se": 0.9}]
    kinds = {(r["sleeve"], r["kind"]) for r in sf.research_requests(rows)}
    assert kinds == {("x", "cost_dominated"), ("y", "uncertainty_bound")}


def test_a_desk_pass_publishes_scores_and_judges(tmp_path) -> None:
    d = _daily(160, mus=(0.3, 0.0, -0.4))
    led, out = tmp_path / "f.jsonl", tmp_path / "r.json"
    believed = {"s0": 0.3, "s1": 0.0, "s2": 0.4}              # s2 is believed, wrongly, to win
    for k in range(60, 155, 5):                              # a forecast every 5 days
        sf.run(led, out, daily=d.iloc[:k], rows_fn=_rows_fn(believed))
    doc = sf.run(led, out, daily=d, rows_fn=_rows_fn(believed))
    assert doc["status"] == "MEASURED" and doc["n_scored"] > 0
    j = doc["outcomes_vs_forecast"]["per_sleeve"]
    assert j["s2"]["verdict"] == "WORSE_THAN_FORECAST"
    assert j["s0"]["verdict"] != "WORSE_THAN_FORECAST"
    assert doc["calibration"]["status"] == "MEASURED"
    assert json.loads(out.read_text())["authority"].startswith("none")


def test_an_evidence_refusal_is_unmeasured_not_a_crash(tmp_path, monkeypatch) -> None:
    from research import pf_allocator as pa

    def refuse(**_k):
        raise SystemExit("REFUSING to project")

    monkeypatch.setattr(pa, "build_evidence", refuse)
    doc = sf.run(tmp_path / "f.jsonl", tmp_path / "r.json")
    assert doc["status"] == "UNMEASURED" and doc["n_scored"] == 0
    assert json.loads((tmp_path / "r.json").read_text())["status"] == "UNMEASURED"


def test_the_leg_is_on_the_hourly_clock() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/sleeve_forecasts.py"' in src and '"sleeve_forecasts": sfc' in src
    from libs.research import layers
    assert layers.LEG_LAYER["sleeve_forecasts"] == "prediction"
