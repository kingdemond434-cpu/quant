"""Prediction-market intelligence: calibration, resolution truth, dependencies, terms, Kelly.

Nothing here touches a network. The venue table's ACCESS decisions are asserted first, because
they are the part a later edit is most likely to loosen by accident -- a venue quietly flipped
from PUBLIC_WITH_TERMS to PUBLIC would turn a documented-API path into a scraper without anybody
changing a line of fetch code.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import prediction_markets as pm  # noqa: E402


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield R
    R.set_path(None)


def _planted(n: int, slope: float, *, category: str = "rates", seed: int = 1,
             intercept: float = 0.0) -> list[dict]:
    """Forecasts whose TRUE probability is a known logit transform of the stated one."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        p = float(np.clip(rng.beta(2.0, 2.0), 0.02, 0.98))
        true_p = pm._sigmoid(intercept + slope * pm._logit(p))
        rows.append({"forecast_id": f"{category}{i}", "source": "planted", "category": category,
                     "horizon_bucket": "short", "liquidity_bucket": "deep", "p": p,
                     "outcome": float(rng.random() < true_p)})
    return rows


# --------------------------------------------------------------------- terms and access
def test_every_venue_is_mined_and_unclear_access_is_a_label_not_a_quarantine():
    """LAWS 5e (2026-09-23). This test asserted the opposite until then: PUBLIC_WITH_TERMS venues
    carried `machine_use_allowed is False` and `iem` (ACCESS_UNCLEAR) was quarantined with its
    content unconsumed. Both were discovery brakes. Every venue is read and tested now; what the
    terms still withhold is REDISTRIBUTION, and `quarantined` is empty by construction."""
    terms = pm.venue_terms()
    assert terms["scraped"] == []
    assert terms["quarantined"] == [], "the access quarantine was deleted on 2026-09-23"
    assert terms["refused"] == []
    assert set(terms["mined"]) == {v.name for v in pm.VENUES}
    assert terms["redistributable"] == [], "no venue here grants redistribution"
    for row in terms["venues"]:
        assert row["machine_use_allowed"] is True, f"{row['venue']} must be mined"
        assert row["may_consume_content"] is True
        assert row["redistribute_allowed"] is False
        assert row["terms_note"], f"{row['venue']} must carry its routing label"


def test_the_three_labels_travel_with_every_venue():
    for v in pm.VENUES:
        row = v.as_row()
        assert row["access_label"] in pm.SC.ACCESS_LABELS
        assert row["credibility"] in pm.SC.CREDIBILITY_LABELS
        assert row["predictive_state"] in pm.SC.PREDICTIVE_STATES
        assert row["evidence_weight"] > 0, "a low-credibility venue is discounted, never deleted"
    play_money = next(v for v in pm.VENUES if v.name == "manifold")
    assert play_money.credibility == "UNRELIABLE"
    assert play_money.as_row()["may_consume_content"] is True


def test_load_markets_never_fetches_by_default_and_names_a_missing_endpoint_not_a_refusal():
    """A venue with no API credential on this box is UNMEASURED -- and the reason must say the
    ENDPOINT is missing, not that the terms forbid it (LAWS 5e, 2026-09-23). "never scraped" was
    the old wording and it was a brake in prose."""
    off = pm.load_markets(fetch=False)
    assert off["fetched"] is False and off["n"] > 0
    walled = pm.load_markets(fetch=True, venue="polymarket")
    assert walled["fetched"] is False and walled["verdict"] == pm.UNMEASURED
    assert "MINED AND TESTED" in walled["why"] and "never a refusal" in walled["why"]
    assert "never scraped" not in walled["why"]
    unclear = pm.load_markets(fetch=True, venue="iem")
    assert unclear["verdict"] == pm.UNMEASURED and "ACCESS_UNCLEAR" in unclear["why"]


# --------------------------------------------------------------------- calibration
def test_the_recalibration_slope_is_fitted_and_recovers_a_planted_one():
    rows = _planted(3000, 1.18, seed=11)
    fit = pm.fit_recalibration([r["p"] for r in rows], [r["outcome"] for r in rows])
    assert fit["verdict"] == "MEASURED"
    assert fit["slope"] == pytest.approx(1.18, abs=0.12)
    assert fit["published_prior"] == 1.18
    assert 1.18 in fit["prior_ladder"] and len(fit["prior_ladder"]) > 1


def test_a_flat_market_fits_a_slope_of_one_and_earns_no_recalibration():
    rows = _planted(3000, 1.0, seed=12)
    fit = pm.fit_recalibration([r["p"] for r in rows], [r["outcome"] for r in rows])
    assert fit["slope"] == pytest.approx(1.0, abs=0.12)
    assert pm.recalibrate(0.7, fit) == pytest.approx(0.7, abs=0.05)


def test_calibration_is_fitted_per_category_not_pooled():
    rows = _planted(1500, 1.6, category="rates", seed=21) + \
        _planted(1500, 0.6, category="geopolitics", seed=22)
    cal = pm.calibrate(rows)
    assert cal["n_cells"] == 2
    rate_cell = next(v for k, v in cal["cells"].items() if k.startswith("rates|"))
    geo_cell = next(v for k, v in cal["cells"].items() if k.startswith("geopolitics|"))
    assert rate_cell["fit"]["slope"] > 1.2 > geo_cell["fit"]["slope"]
    assert len(cal["fitted_cells"]) == 2


def test_a_thin_cell_is_unmeasured_by_name_and_keeps_its_row():
    cal = pm.calibrate(_planted(10, 1.18, seed=31))
    assert cal["fitted_cells"] == []
    assert len(cal["unmeasured_cells"]) == 1
    cell = next(iter(cal["cells"].values()))
    assert cell["fit"]["verdict"] == pm.UNMEASURED and str(pm.MIN_FORECASTS) in cell["fit"]["why"]


def test_an_unmeasured_fit_never_applies_somebody_elses_slope():
    unfitted = {"verdict": pm.UNMEASURED}
    assert pm.recalibrate(0.8, unfitted) == pytest.approx(0.8)


def test_the_favourite_longshot_asymmetry_is_measured_on_both_halves():
    rng = np.random.default_rng(41)
    rows = []
    for _ in range(2000):
        p = float(np.clip(rng.beta(2.0, 2.0), 0.02, 0.98))
        true_p = max(0.0, min(1.0, p - 0.10 if p < 0.5 else p + 0.10))   # the classic pattern
        rows.append((p, float(rng.random() < true_p)))
    out = pm.favourite_longshot([r[0] for r in rows], [r[1] for r in rows])
    assert out["verdict"] == "MEASURED"
    assert out["longshot_gap"] < 0 < out["favourite_gap"]
    assert out["classic_pattern"] is True
    thin = pm.favourite_longshot([0.9] * 20, [1.0] * 20)
    assert thin["verdict"] == pm.UNMEASURED


def test_calibration_error_returns_the_bin_table_not_just_a_headline():
    rows = _planted(600, 1.0, seed=51)
    ece = pm.calibration_error([r["p"] for r in rows], [r["outcome"] for r in rows])
    assert ece["verdict"] == "MEASURED" and 0.0 <= ece["ece"] < 0.2
    assert len(ece["bins"]) >= 4
    assert all("gap" in b and "n" in b for b in ece["bins"])


def test_momentum_on_a_probability_is_bounded():
    rising = [0.1, 0.2, 0.35, 0.5, 0.7, 0.9]
    out = pm.bounded_momentum(rising, cap=0.10, lookback=5)
    assert out["raw"] == pytest.approx(0.8)
    assert out["bounded"] == pytest.approx(0.10), "an unbounded momentum on a probability"
    assert pm.bounded_momentum([0.5])["verdict"] == pm.UNMEASURED


# --------------------------------------------------------------------- resolution truth
def test_a_forecast_is_recorded_before_resolution_or_not_at_all(tmp_path):
    ok = pm.record_forecast({"forecast_id": "f1", "p": 0.4, "category": "rates",
                             "source": "kalshi"}, path=tmp_path / "f.jsonl")
    assert ok["stored"] is True and ok["row"]["p"] == pytest.approx(0.4)
    assert (tmp_path / "f.jsonl").exists()

    late = pm.record_forecast({"forecast_id": "f2", "p": 0.4, "outcome": 1.0},
                              path=tmp_path / "f.jsonl")
    assert late["stored"] is False and "BEFORE" in late["why"]


def test_record_forecast_dry_run_writes_nothing(tmp_path):
    out = pm.record_forecast({"forecast_id": "f", "p": 0.5}, path=tmp_path / "f.jsonl",
                             dry_run=True)
    assert out["stored"] is True and not (tmp_path / "f.jsonl").exists()


def test_resolution_scores_sit_beside_the_base_rate_and_the_beta_baseline():
    sharp = _planted(1200, 1.0, category="rates", seed=61)
    for r in sharp:
        r["source"] = "sharp"
    rng = np.random.default_rng(62)
    noise = [{**r, "source": "noise", "p": float(rng.random())} for r in sharp]
    out = pm.score_forecasts(sharp + noise, by="source")
    assert set(out["groups"]) == {"sharp", "noise"}
    s, n = out["groups"]["sharp"], out["groups"]["noise"]
    assert s["brier"] < n["brier"]
    assert s["brier_skill_vs_base"] > n["brier_skill_vs_base"]
    assert s["beats_beta_baseline"] is True
    assert n["beats_beta_baseline"] is False
    assert "calibration" in s and s["n"] == len(sharp)


def test_resolution_scores_group_by_seat_as_well_as_source():
    rows = _planted(200, 1.0, seed=71)
    for i, r in enumerate(rows):
        r["seat"] = "seat_a" if i % 2 else "seat_b"
    out = pm.score_forecasts(rows, by="seat")
    assert set(out["groups"]) == {"seat_a", "seat_b"}
    assert out["grouped_by"] == "seat"


# --------------------------------------------------------------------- disagreement vector
def test_the_disagreement_vector_never_imputes_a_missing_leg():
    out = pm.disagreement_vector({"p_market": 0.8, "p_news": 0.3})
    assert out["verdict"] == "MEASURED"
    assert out["legs"]["p_macro"] is None
    assert out["unmeasured_legs"] == ["p_macro", "p_options", "p_smart"]
    assert out["stance"] == "disagreement" and out["spread"] == pytest.approx(0.5, abs=0.01)
    assert out["most_bullish"] == "p_market" and out["most_bearish"] == "p_news"

    agree = pm.disagreement_vector({"p_market": 0.5, "p_news": 0.52, "p_macro": 0.55})
    assert agree["stance"] == "agreement"
    assert pm.disagreement_vector({"p_market": 0.5})["verdict"] == pm.UNMEASURED
    assert list(pm.DISAGREEMENT_LEGS) == ["p_market", "p_news", "p_macro", "p_options", "p_smart"]


# --------------------------------------------------------------------- dependency constraints
def test_dependency_deviations_on_a_planted_inconsistent_group():
    contracts = {"a": 0.5, "b": 0.5, "c": 0.3, "specific": 0.7, "general": 0.4}
    out = pm.dependency_deviations(contracts, sum_to_one=[["a", "b", "c"]],
                                   implications=[("specific", "general")])
    group = out["sum_to_one"][0]
    assert group["verdict"] == "MEASURED" and group["complete"] is True
    assert group["sum"] == pytest.approx(1.3) and group["deviation"] == pytest.approx(0.3)
    assert group["violation"] is True

    chain = out["implications"][0]
    assert chain["deviation"] == pytest.approx(0.3) and chain["violation"] is True
    assert out["n_violations"] == 2
    assert out["traded"] is False, "a deviation must never be presented as a trade"


def test_a_consistent_group_shows_no_violation():
    out = pm.dependency_deviations({"a": 0.5, "b": 0.3, "c": 0.2, "x": 0.2, "y": 0.6},
                                   sum_to_one=[["a", "b", "c"]], implications=[("x", "y")])
    assert out["n_violations"] == 0
    assert out["sum_to_one"][0]["deviation"] == pytest.approx(0.0, abs=1e-6)
    assert out["implications"][0]["deviation"] < 0


def test_a_partial_group_is_unmeasured_rather_than_a_deviation():
    out = pm.dependency_deviations({"a": 0.5, "b": 0.3}, sum_to_one=[["a", "b", "missing"]],
                                   implications=[("a", "absent")])
    group = out["sum_to_one"][0]
    assert group["complete"] is False and group["deviation"] is None
    assert group["violation"] is False, "an incomplete partition cannot be a violation"
    assert out["implications"][0]["verdict"] == pm.UNMEASURED
    only_one = pm.dependency_deviations({"a": 0.5}, sum_to_one=[["a", "b"]])
    assert only_one["sum_to_one"][0]["verdict"] == pm.UNMEASURED


# --------------------------------------------------------------------- lead / lag
def test_lead_lag_against_an_instrument_reports_a_permutation_null():
    rng = np.random.default_rng(81)
    odds = rng.normal(0, 1, 600)
    instrument = np.concatenate([np.zeros(4), odds[:-4]]) + rng.normal(0, 0.3, 600)
    out = pm.lead_lag_vs_instrument(odds, instrument, permutations=150)
    assert out["verdict"] == "MEASURED"
    assert out["peak_lag"] == 4 and out["direction"] == "odds lead the instrument"
    assert out["p_value"] <= 0.05 and out["significant"] is True
    assert out["permutations"] == 150


def test_lead_lag_on_independent_series_is_usually_not_significant():
    rng = np.random.default_rng(82)
    out = pm.lead_lag_vs_instrument(rng.normal(0, 1, 600), rng.normal(0, 1, 600),
                                    permutations=150)
    assert out["verdict"] == "MEASURED" and out["p_value"] > 0.05


# --------------------------------------------------------------------- the Kelly reference
def test_the_kelly_reference_is_never_a_sizing_authority():
    out = pm.kelly_reference(0.60, 0.50, fraction=0.25)
    assert out["sizing_authority"] is False
    assert out["full_kelly"] == pytest.approx(0.2)          # (0.60 - 0.50) / (1 - 0.50)
    assert out["fractional_kelly"] == pytest.approx(0.05)
    assert out["side"] == "yes" and out["edge"] == pytest.approx(0.10)
    assert "never sizes anything" in out["rule"]


def test_the_kelly_reference_finds_the_no_side_and_refuses_a_negative_stake():
    out = pm.kelly_reference(0.20, 0.50)
    assert out["side"] == "no" and out["f_no"] == pytest.approx(0.6)
    flat = pm.kelly_reference(0.50, 0.50)
    assert flat["fractional_kelly"] == pytest.approx(0.0)
    assert flat["full_kelly"] == pytest.approx(0.0)


# --------------------------------------------------------------------- the pass
def test_dry_run_writes_nothing(tmp_path, monkeypatch, registry):
    monkeypatch.setattr(pm, "REPORT", tmp_path / "PREDICTION_MARKETS.json")
    out = pm.run_pass(no_fetch=True, dry_run=True, budget_s=20.0)
    assert out["dry_run"] is True and out["no_fetch"] is True
    assert not (tmp_path / "PREDICTION_MARKETS.json").exists()
    assert not R.path().exists(), "a dry run opened the registry"
    assert out["discoveries"] == len(pm.MACRO_LEGS)


def test_a_real_pass_mints_macro_leg_discoveries_and_writes_one_report(tmp_path, monkeypatch,
                                                                      registry):
    report = tmp_path / "PREDICTION_MARKETS.json"
    monkeypatch.setattr(pm, "REPORT", report)
    out = pm.run_pass(no_fetch=True, dry_run=False, budget_s=30.0)
    assert report.exists()
    assert len(out["calibration"]["fitted_cells"]) == out["calibration"]["n_cells"]
    discs = R.discoveries()
    assert len(discs) == len(pm.MACRO_LEGS)
    assert all(str(d["source_type"]) == "prediction_market" for d in discs)
    assets = {str(d["assets_json"]) for d in discs}
    assert len(assets) == len(pm.MACRO_LEGS)
    assert all(any(leg in a for leg in pm.MACRO_LEGS) for a in assets)
