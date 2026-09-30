"""Tier S measurement layers (S15, S19, S26, S29, S34, S35, S37): the halves their ledger rows named
as remaining on 2026-09-30.

  S15  trade-overlap and exposure-simulation ranks beside the descriptor and live-P&L ranks
  S19  a SAT/constraint lab and a Gaussian-process lab beside the eight traditions
  S26  MAE/MFE, hold and slippage forecasts scored beside R
  S29  inventory rows for gate backlog, compute timeouts and allocator binding constraints
  S34  a real-episode suite beside the synthetic one
  S35  each acquisition ranker resolved on its own metric, compared in normalised gain
  S37  DSR, PBO and cost-model quantities in the epistemic census
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.tiers import acquisition_resolution as acq  # noqa: E402
from libs.tiers import (  # noqa: E402
    bitemporal,
    cross_science,
    epistemic,
    meta_benchmark,
    prediction_accounting,
    real_episodes,
    self_model,
    topology,
    traps,
)

H = 3600.0


# ---------------------------------------------------------------- S15 topology simulations

def test_legs_and_leg_cosine() -> None:
    assert topology.legs("EURUSD") == {"EUR": 1.0, "USD": -1.0}
    assert topology.legs("US500") == {"US500": 1.0}
    assert topology.leg_cosine("EURUSD", "EURUSD") == pytest.approx(1.0)
    # long EURUSD and long USDCHF share the dollar leg with opposite signs
    assert topology.leg_cosine("EURUSD", "USDCHF") == pytest.approx(-0.5)
    assert topology.leg_cosine("EURUSD", "AUDJPY") == 0.0


def test_trade_overlap_sees_one_dollar_bet_and_ignores_disjoint_time() -> None:
    t0 = 1_700_000_000.0
    a = [(t0 + d * 24 * H, t0 + d * 24 * H + 3 * H, 1.0, "EURUSD") for d in range(5)]
    # short USDCHF at the same hours: the same side of the dollar as long EURUSD
    b = [(s, e, -1.0, "USDCHF") for s, e, _x, _y in a]
    # same instrument, never at the same time
    c = [(s + 12 * H, e + 12 * H, 1.0, "EURUSD") for s, e, _x, _y in a]
    out = topology.trade_overlap({"A": a, "B": b, "C": c})
    assert out["status"] == "MEASURED"
    names = out["names"]
    sim = out["similarity"]
    ia, ib, ic = names.index("A"), names.index("B"), names.index("C")
    assert sim[ia, ib] == pytest.approx(0.5)          # |(-1)(+1)(-0.5)| per shared hour
    assert sim[ia, ic] == 0.0
    assert out["trade_overlap"] < 3.0
    assert topology.trade_overlap({"A": a})["status"] == "UNMEASURED"


def test_exposure_simulation_ranks_clones_as_one() -> None:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-01-01", periods=800, freq="h", tz="UTC")
    rets = {s: pd.Series(rng.normal(0, 1e-3, len(idx)), index=idx) for s in ("EURUSD", "USDJPY")}
    sleeves = [{"name": "a", "symbol": "EURUSD", "direction": "LONG", "selector": "continuous"},
               {"name": "b", "symbol": "EURUSD", "direction": "LONG", "selector": "continuous"},
               {"name": "c", "symbol": "USDJPY", "direction": "LONG", "selector": "asia"},
               {"name": "d", "symbol": "USDJPY", "direction": "LONG", "selector": "mystery"}]
    names, panel = topology.simulate_exposure(sleeves, rets, {"asia": range(0, 8)})
    assert names == ["a", "b", "c"], "an unplaceable window is left out, never always-on"
    rep = topology.rank_report(panel, names, None)
    assert rep["linear"] < 2.2                         # a and b are one exposure
    comb = topology.combined_with({"combined": 3.0}, ["a", "b", "c", "x"], None,
                                  {"exposure_sim": (names, topology.pnl_similarity(panel))})
    assert comb["readings"] == {"exposure_sim": 3}
    assert comb["combined"] < 4.0


# ---------------------------------------------------------------- S19 constraint + GP labs

def test_constraint_search_finds_a_planted_conjunction_and_prunes() -> None:
    rng = np.random.default_rng(1)
    n = 3000
    a = rng.choice((-1.0, 1.0), n)
    b = rng.choice((-1.0, 1.0), n)
    c = rng.choice((-1.0, 1.0), n)
    fwd = rng.normal(0, 1.0, n)
    fwd[(a > 0) & (b < 0)] += 0.6
    res = cross_science.constraint_search(fwd, {"a": a, "b": b, "c": c})
    clauses = [tuple(s["clause"]) for s in res["satisfying"]]
    assert ("a+", "b-") in clauses
    # minimality: no satisfying clause strictly contains another satisfying clause
    sets = [set(x) for x in clauses]
    assert not any(x < y for x in sets for y in sets)
    assert res["evaluated"] < 6 + 12 + 8 * 1 + 50


def test_constraint_expressions_are_grammar_valid_or_none() -> None:
    long_ = cross_science.constraint_expression([["up1", 1], ["trend24", -1]], 1.0)
    short = cross_science.constraint_expression([["busy", -1], ["wide_range", -1]], -1.0)
    for e in (long_, short):
        assert e is not None and ag.is_valid(ag.from_str(e)), e
    deep = cross_science.constraint_expression(
        [["busy", -1], ["trend5", -1], ["up1", -1]], 1.0)
    assert deep is None, "an inexpressible clause is None, never truncated"
    assert ts.xsci_expression({"lab": "constraint", "atoms": [["up1", 1]], "direction": 1.0})


def test_literal_signs_are_causal() -> None:
    rng = np.random.default_rng(2)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, 700)))
    full = cross_science.literal_signs(px, rng.random(700))
    cut = cross_science.literal_signs(px[:500], rng.random(500))
    for k in cut:
        a, b = full[k][:499], cut[k]
        ok = np.isfinite(a) & np.isfinite(b)
        assert np.array_equal(a[ok], b[ok]), k


def test_gp_gradient_matches_finite_differences() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=(40, 3))
    y = np.sin(x[:, 0]) + 0.1 * rng.normal(size=40)
    sq = (x.T[:, :, None] - x.T[:, None, :]) ** 2
    th = np.array([0.1, -0.2, 0.3, -0.5, -1.0])
    _f0, g = cross_science._gp_nll(th, sq, y)
    for i in range(len(th)):
        e = np.zeros_like(th)
        e[i] = 1e-5
        fd = (cross_science._gp_nll(th + e, sq, y)[0] - cross_science._gp_nll(th - e, sq, y)[0]
              ) / 2e-5
        assert g[i] == pytest.approx(fd, rel=1e-3, abs=1e-4)


def test_gp_lab_finds_predictability_and_orients_its_expression() -> None:
    rng = np.random.default_rng(4)
    r = np.zeros(1400)
    e = rng.normal(0, 1e-3, 1400)
    for t in range(1, 1400):
        r[t] = 0.45 * r[t - 1] + e[t]
    px = 100 * np.exp(np.cumsum(r))
    hits = cross_science.gp_lab({"EURUSD": px}, n_train=200, n_test=300)
    assert hits and hits[0]["lab"] == "gaussian_process"
    expr = ts.xsci_expression(hits[0])
    assert expr is not None and ag.is_valid(ag.from_str(expr))
    assert not expr.startswith("neg("), "positive autocorrelation is momentum"
    noise = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, 1400)))
    assert cross_science.gp_lab({"X": noise}, n_train=200, n_test=300) == []


# ---------------------------------------------------------------- S26 quantity forecasts

def _hist(n: int = 12) -> dict[str, dict[str, list[tuple[str, float]]]]:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    return {q: {"EURUSD.asia": [((t0 + timedelta(hours=6 * i)).isoformat(), 0.5 + 0.1 * (i % 3))
                                for i in range(n)]} for q in prediction_accounting.QUANTITIES}


def test_prequential_scores_every_quantity_from_strictly_earlier_outcomes() -> None:
    out = prediction_accounting.prequential(_hist())
    for q in prediction_accounting.QUANTITIES:
        assert out[q]["status"] == "MEASURED"
        assert out[q]["n_scored"] == 11           # the first outcome has no past
    assert prediction_accounting.prequential({})["mae_r"]["status"] == "UNMEASURED"


def test_quantity_forecasts_register_once_per_open_horizon_and_resolve() -> None:
    hist = _hist()
    ledger: list[prediction_accounting.Forecast] = []
    now = datetime(2026, 9, 10, tzinfo=UTC)
    hz = (now + timedelta(days=2)).isoformat()
    made = prediction_accounting.register_quantities(ledger, hist, ["EURUSD.asia", "NONE.x"],
                                                     now.isoformat(), hz)
    assert made == 4 * 2                           # NONE.x forecast from the desk pool
    again = prediction_accounting.register_quantities(ledger, hist, ["EURUSD.asia"],
                                                      (now + timedelta(hours=1)).isoformat(), hz)
    assert again == 0, "one open promise per key and quantity"
    later = (now + timedelta(hours=5)).isoformat()
    for q in hist:
        hist[q]["EURUSD.asia"].append((later, 0.6))
    sc = prediction_accounting.score_quantities(ledger, hist)
    assert all(sc[q]["n_scored"] == 1 for q in prediction_accounting.QUANTITIES)
    assert prediction_accounting.forecast_from("hold_h", [], []) is None


# ---------------------------------------------------------------- S29 operational inventory

def test_operational_inventory_rows_and_unmeasured() -> None:
    rows, facts = self_model.operational_inventory(
        queue_status={"QUEUED_CANONICAL_GAUNTLET": 700, "DONE": 5}, oldest_waiting_h=40.0,
        verdicts_per_h=10.0,
        compute=[{"run": "a", "outcome": "ok"}, {"run": "b", "outcome": "TIMEOUT", "wall_s": 9},
                 {"run": "b", "outcome": "interrupted"}, {"run": "c", "outcome": "ok"}],
        allocation={"heat": {"binding": "ceiling", "held": False, "free_optimum": 0.4,
                             "total": 0.3}})
    by = {r["area"]: r for r in rows}
    assert by["throughput.gate_backlog"]["gap"] == pytest.approx(70.0 / 168.0, abs=1e-3)
    assert by["compute.timeouts"]["gap"] == 0.5
    assert by["allocator.binding"]["gap"] == pytest.approx(0.25)
    assert facts["compute_timeouts"]["by_run"] == {"b": 2}
    rows2, facts2 = self_model.operational_inventory(queue_status=None, oldest_waiting_h=None,
                                                     verdicts_per_h=None, compute=None,
                                                     allocation=None)
    assert {r["gap"] for r in rows2} == {0.5}
    assert all("UNMEASURED" in r["why"] for r in rows2)
    assert facts2["allocator_binding"]["status"] == "UNMEASURED"
    ranked = self_model.rank(rows)
    assert ranked[0]["expected_improvement"] >= ranked[-1]["expected_improvement"]


def test_a_floor_binding_is_not_counted_as_growth_left() -> None:
    rows, _f = self_model.operational_inventory(
        queue_status={}, oldest_waiting_h=None, verdicts_per_h=0.0, compute=[],
        allocation={"heat": {"binding": "floor", "held": False, "free_optimum": 0.15,
                             "total": 0.20}})
    assert {r["area"]: r for r in rows}["allocator.binding"]["gap"] == 0.0


def test_self_model_organ_carries_the_operational_rows(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "_operational_self_facts", lambda: {
        "queue_status": {"PENDING": 10}, "oldest_waiting_h": 1.0, "verdicts_per_h": 0.0,
        "compute": [{"outcome": "TIMEOUT"}], "allocation": None})
    out = ts.organ_self_model({})
    areas = {d["area"] for d in out["deficiencies"]}
    assert {"throughput.gate_backlog", "compute.timeouts", "allocator.binding"} <= areas
    assert out["operations"]["gate_backlog"]["waiting"] == 10


# ---------------------------------------------------------------- S34 real episodes

def _panel(n_sym: int = 3, n: int = 2500) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(5)
    out = {}
    for i in range(n_sym):
        vol = np.exp(np.cumsum(rng.normal(0, 0.05, n)) * 0.2)        # clustered volatility
        out[f"S{i}"] = rng.standard_t(3, n) * 1e-3 * vol
    return out


def test_real_episode_cases_are_direction_free_and_every_kind_builds() -> None:
    panel = _panel()
    for kind in traps.ALL_KINDS:
        case, truth, used = real_episodes.generate(kind, 7, panel, n=400)
        assert truth.genuine == (kind in traps.TRUE_KINDS)
        assert len(case.prices) == 401 and np.all(np.isfinite(case.prices))
        assert used and used[0][0] in panel
    src = real_episodes.Innovations(panel, np.random.default_rng(0))
    x = src.draw(2000)
    assert abs(float(x.std()) - real_episodes.SIGMA) < 1e-3
    assert abs(float(np.corrcoef(x[:-1], x[1:])[0, 1])) < 0.08


def test_real_suite_scores_seals_and_compares() -> None:
    suite = real_episodes.RealSuite(panel=_panel(), per_kind=2, n=400)
    rows = list(suite.cases())
    assert len(rows) == 2 * len(traps.ALL_KINDS)
    seal = suite.seal(rows)
    assert seal == suite.seal(list(real_episodes.RealSuite(panel=_panel(), per_kind=2,
                                                           n=400).cases()))
    other = real_episodes.RealSuite(panel=_panel(4), per_kind=2, n=400)
    assert other.seal(list(other.cases())) != seal, "a changed input set is a changed seal"
    res = meta_benchmark.score(meta_benchmark.reference_validator(), cases=rows)
    cmp_ = real_episodes.compare(res, res)
    assert set(cmp_["accept_rate_gap"].values()) == {0.0}


def test_real_episode_immune_is_unmeasured_without_bars(monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "_returns_panel", lambda *a, **k: ({}, {}, {}))
    out = ts.real_episode_immune(meta_benchmark.ValidatorConfig(), {})
    assert out["status"] == "UNMEASURED"


# ---------------------------------------------------------------- S35 own-metric resolution

def _vod(v: float) -> dict[str, Any]:
    return {"top": [{"need_id": "n1", "kind": "missing_variable", "value": v},
                    {"need_id": "n2", "kind": "dataset", "value": 2 * v}]}


def test_each_ranker_resolves_on_its_own_metric() -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    preds: list[bitemporal.Prediction] = []
    assert acq.register(preds, "value_of_data", acq.observe("value_of_data", _vod(0.1)),
                        t0.isoformat()) == 2
    src_doc = {"rows": [{"id": "s1", "u_prior_sd": 0.5, "evig": 0.01, "cost_s": 10, "ok": 0}]}
    acq.register(preds, "source_evig", acq.observe("source_evig", src_doc), t0.isoformat())
    early = (t0 + timedelta(hours=1)).isoformat()
    assert acq.resolve(preds, {"value_of_data": acq.observe("value_of_data", _vod(0.05))},
                       early) == 0, "never before MIN_HOURS"
    later = (t0 + timedelta(hours=12)).isoformat()
    # the source was re-listed but NOT collected: its prediction stays open
    obs = {"value_of_data": acq.observe("value_of_data", {"top": [
               {"need_id": "n1", "value": 0.05}]}),
           "source_evig": acq.observe("source_evig", {"rows": [dict(src_doc["rows"][0],
                                                                    u_prior_sd=0.4)]})}
    assert acq.resolve(preds, obs, later) == 1           # n1 only; n2 unlisted is not evidence
    n1 = next(p for p in preds if p.item == "n1")
    assert n1.realised_gain == pytest.approx(0.05)
    obs["source_evig"] = acq.observe("source_evig", {"rows": [dict(src_doc["rows"][0],
                                                                   u_prior_sd=0.4, ok=3)]})
    assert acq.resolve(preds, obs, later) == 1
    s1 = next(p for p in preds if p.item == "s1")
    assert s1.realised_gain == pytest.approx(0.1) and s1.predicted_gain == pytest.approx(0.1)


def test_normalised_gain_puts_rankers_in_one_currency() -> None:
    now = "2026-09-01T00:00:00+00:00"
    preds = [bitemporal.Prediction("a", "dataset", "value_of_data", 0.01, 0.0, 0.1,
                                   "vod.remaining_value", 0.01, now),
             bitemporal.Prediction("b", "dataset", "evig_acquisition", 1000.0, 0.0, 0.1,
                                   "evig.remaining", 1000.0, now)]
    cal = acq.calibration(preds)
    assert all(v["status"] == "UNMEASURED" for v in cal.values())
    top = acq.rank(preds, cal)
    assert {r["normalised_gain"] for r in top} == {1.0}, "raw units never outrank"
    for p, frac in zip(preds, (0.5, 0.5), strict=True):
        p.resolved, p.realised_gain = True, p.predicted_gain * frac
    cal = acq.calibration(preds)
    assert cal["value_of_data"]["status"] == "MEASURED"
    assert cal["value_of_data"]["calibration"] == pytest.approx((0.5 + 5) / 6, abs=1e-3)


def test_dataset_acquisition_resolves_on_the_rankers_roi_ledger() -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    doc = {"ranked": [{"dataset": "cot", "terms": {"redundancy": 0.2,
                                                   "information_gain": 0.6}}],
           "source_roi": {"rows": [{"dataset": "cot", "acquired": False}]}}
    preds: list[bitemporal.Prediction] = []
    acq.register(preds, "data_acquisition_scientist",
                 acq.observe("data_acquisition_scientist", doc), t0.isoformat())
    held = {"ranked": [], "source_roi": {"rows": [{"dataset": "cot", "acquired": True}]}}
    n = acq.resolve(preds, {"data_acquisition_scientist": acq.observe(
        "data_acquisition_scientist", held)}, (t0 + timedelta(hours=8)).isoformat())
    assert n == 1 and preds[0].realised_gain == pytest.approx(0.8)


# ---------------------------------------------------------------- S37 certifier quantities

def test_dsr_quantity_reproduces_the_certificates_dsr() -> None:
    q = epistemic.dsr_quantity("dsr_excess:x", 0.3177, 0.131, 179)
    z = q.value / ((q.hi - q.value) / epistemic.Z95)
    assert 0.5 * (1 + math.erf(z / math.sqrt(2))) == pytest.approx(0.9929, abs=5e-3)
    assert epistemic.decide(q, 0.0) == epistemic.Decision.YES
    assert epistemic.dsr_quantity("d", None, 0.1, 100).label() == epistemic.Label.UNKNOWN


def test_pbo_and_cost_quantities_label_from_their_evidence() -> None:
    p = epistemic.pbo_quantity("pbo:x", 0.14, 15)
    assert p.lo is not None and p.lo < 0.14 < p.hi and p.n == 15
    assert p.label(0.5) == epistemic.Label.WEAK, "15 CSCV splits is a small sample"
    c = epistemic.cost_stress_quantity("cost_x3:x", 0.11, 0.39, 0.32, 179)
    assert c.lo is not None and c.lo > 0
    assert epistemic.cost_stress_quantity("c", 0.1, None, None, 50).label() == \
        epistemic.Label.WEAK
    m = epistemic.cost_model_quantity("cost_model:EURZAR", [217.0] * 24, 912.0)
    assert m.value == pytest.approx(math.log(217 / 912)) and m.n == 24
    assert epistemic.decide(m, 0.0) == epistemic.Decision.NO     # the model overcharges


def test_census_carries_certifier_families(monkeypatch: Any) -> None:
    row = {"days": 179, "gates": {"in_sample_screen": {"sharpe": 0.3177},
                                  "deflated_sharpe": {"sr0": 0.131},
                                  "pbo": {"pbo": 0.14}, "cpcv": {"folds": 15},
                                  "stress_costs": {"exp_x3": 0.11},
                                  "expected_value": {"ev": 0.39}},
           "shadow_spec": {"symbol": "EURUSD", "selector": "asia"}}
    monkeypatch.setattr(ts, "survivors", lambda: {"k": row})
    monkeypatch.setattr(ts, "shadow_rows", lambda: {})
    monkeypatch.setattr(ts, "registry", lambda: {})
    out = ts.epistemic_census({})
    assert {"dsr_excess", "pbo", "cost_x3", "forward_edge"} <= set(out["by_family"])
    assert out["certifier_undecided"]["pbo"] == 1
    assert out["metric"]["decidable_dsr_excess"] == 1.0
