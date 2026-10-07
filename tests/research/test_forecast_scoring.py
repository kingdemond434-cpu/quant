"""FORECAST SCORING (ARCH-03 / DATA-36 / ALLOC-08): every forecast against what happened.

Each test fences one way a forecast record can lie about its own quality:

  - a perfect forecaster that does NOT score perfectly (the rule is wrong);
  - a biased forecaster whose bias hides inside a plausible average (it must show in reliability);
  - a tail that is breached far more than alpha while coverage reads fine (coverage arithmetic);
  - a duplicate or noise source credited with value it never added (incremental value);
  - a re-published belief pooled twice (idempotence);
  - absent data reported as a zero score (UNMEASURED, never zero).
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import NormalDist

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_RESEARCH = _ROOT / "desks" / "mt5" / "research"
_N = NormalDist()
T0 = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def fs():
    spec = importlib.util.spec_from_file_location("_forecast_scoring",
                                                  _RESEARCH / "forecast_scoring.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _row(model: str, subject: str, kind: str, value, at: datetime, outcome=None, **over):
    r = {"model_id": model, "subject": subject, "kind": kind, "value": value,
         "horizon_s": 3600.0, "at": at.isoformat(), "status": "ACCEPTED",
         "family": "bayesian_edge", "role": "DIRECTION_MEAN",
         "training_cutoff": (at - timedelta(days=1)).isoformat(), "model_version": "v1"}
    if outcome is not None:
        r["outcome"] = outcome
    return r | over


def _gauss_q(mu: float, sd: float) -> dict[str, float]:
    return {str(t): mu + sd * _N.inv_cdf(t) for t in (0.1, 0.25, 0.5, 0.75, 0.9)}


NOW = T0 + timedelta(days=400)


# --------------------------------------------------------------------------- proper rules
def test_perfect_probability_and_magnitude_forecasts_score_perfectly(fs) -> None:
    rows = [_row("m", f"EV{i}/up", "PROBABILITY", float(i % 2), T0 + timedelta(hours=i),
                 float(i % 2)) for i in range(20)]
    rows += [_row("m", f"EV{i}/size", "MAGNITUDE", 0.1 * i, T0 + timedelta(hours=i), 0.1 * i)
             for i in range(20)]
    doc, _ = fs.score_register(rows, fs.OutcomeBook([]), fs.RegimeTimeline([]), NOW)
    p = doc["by_kind"]["PROBABILITY"]["overall"]
    assert p["brier"] == 0.0 and p["log_loss"] < 1e-5
    assert p["reliability"]["reliability"] == 0.0
    m = doc["by_kind"]["MAGNITUDE"]["overall"]
    assert m["mae"] == 0.0 and m["signed_error"] == 0.0 and m["sign_hit_rate"] == 1.0
    # a point-mass distribution at the outcome has CRPS 0
    assert fs.crps_quantiles([(0.1, 2.0), (0.5, 2.0), (0.9, 2.0)], 2.0) == 0.0
    assert fs.crps_gaussian(1.0, 0.0, 1.0) == 0.0


def test_a_biased_forecaster_shows_in_reliability_not_just_brier(fs) -> None:
    # The event happens 30% of the time; the model always says 0.6.
    rows = [_row("hot", f"EV{i}/up", "PROBABILITY", 0.6, T0 + timedelta(hours=i),
                 1.0 if i % 10 < 3 else 0.0) for i in range(100)]
    doc, _ = fs.score_register(rows, fs.OutcomeBook([]), fs.RegimeTimeline([]), NOW)
    p = doc["by_kind"]["PROBABILITY"]["overall"]
    assert p["calibration_in_the_large"] == pytest.approx(0.3, abs=1e-9)
    assert p["reliability"]["reliability"] == pytest.approx(0.09, abs=1e-9)
    (b,) = p["reliability"]["bins"]
    assert b["mean_forecast"] == 0.6 and b["observed_freq"] == 0.3


def test_distribution_coverage_and_pit_are_computed_right(fs) -> None:
    n = 200
    ys = [_N.inv_cdf((i + 0.5) / n) for i in range(n)]       # an exact N(0,1) sample
    good = [_row("cal", f"EV{i}/r", "DISTRIBUTION", _gauss_q(0, 1), T0 + timedelta(hours=i), y)
            for i, y in enumerate(ys)]
    doc, _ = fs.score_register(good, fs.OutcomeBook([]), fs.RegimeTimeline([]), NOW)
    d = doc["by_kind"]["DISTRIBUTION"]["overall"]
    assert d["coverage"]["0.80"]["observed"] == pytest.approx(0.80, abs=0.011)
    assert d["coverage"]["0.50"]["observed"] == pytest.approx(0.50, abs=0.011)
    assert d["pit"]["mean"] == pytest.approx(0.5, abs=0.01)
    # shifted truth: the same quantiles now under-cover and the PIT leans high
    bad = [_row("cal", f"EV{i}/r", "DISTRIBUTION", _gauss_q(0, 1), T0 + timedelta(hours=i),
                y + 1.0) for i, y in enumerate(ys)]
    doc2, _ = fs.score_register(bad, fs.OutcomeBook([]), fs.RegimeTimeline([]), NOW)
    d2 = doc2["by_kind"]["DISTRIBUTION"]["overall"]
    assert d2["coverage"]["0.80"]["observed"] < 0.7
    assert d2["pit"]["mean"] > 0.6
    assert d2["crps"] > d["crps"]
    assert d2["signed_error_vs_median"] == pytest.approx(1.0, abs=0.01)


def test_breakdowns_by_regime_source_and_event_class(fs) -> None:
    log = [{"t": T0.isoformat(), "regime": {"bull/low_vol": 0.7, "bear": 0.3}},
           {"t": (T0 + timedelta(hours=10)).isoformat(), "regime": {"bear": 0.9}}]
    rows = [_row("a", "XAUUSD.asia/up", "PROBABILITY", 0.7, T0 + timedelta(hours=1), 1.0),
            _row("b", "EURUSD/up", "PROBABILITY", 0.2, T0 + timedelta(hours=11), 0.0)]
    doc, _ = fs.score_register(rows, fs.OutcomeBook([]), fs.RegimeTimeline(log), NOW)
    p = doc["by_kind"]["PROBABILITY"]
    assert set(p["by_regime"]) == {"bull/low_vol", "bear"}
    assert set(p["by_source"]) == {"a", "b"}
    assert set(p["by_event_class"]) == {"XAUUSD", "EURUSD"}


def test_outcome_ledger_join_and_counts_never_zero(fs) -> None:
    at = T0
    rows = [_row("m", "S/r", "MAGNITUDE", 0.5, at),                     # resolved by ledger
            _row("m", "S/r", "MAGNITUDE", 0.5, at + timedelta(days=1)),  # due, no outcome
            _row("m", "S/r", "MAGNITUDE", 0.5, NOW),                    # not yet due
            _row("m", "S/r", "MAGNITUDE", 0.5, at) | {"status": "REFUSED"}]
    book = fs.OutcomeBook([{"subject": "S/r", "at": (at + timedelta(hours=1, seconds=20))
                            .isoformat(), "value": 0.25}])
    doc, _ = fs.score_register(rows, book, fs.RegimeTimeline([]), NOW)
    assert (doc["scored"], doc["unresolved"], doc["pending"], doc["refused"]) == (1, 1, 1, 1)
    assert doc["by_kind"]["MAGNITUDE"]["overall"]["mae"] == 0.25
    # a kind with nothing resolved is UNMEASURED with n=0, never a zero score
    prob = doc["by_kind"]["PROBABILITY"]["overall"]
    assert prob["status"] == "UNMEASURED" and "brier" not in prob


def test_empty_desk_is_unmeasured_everywhere(fs) -> None:
    doc = fs.build_report(now=NOW, log_rows=[], register_rows=[], outcome_rows=[], quotes={},
                          trigger_state={})
    assert doc["allocator_forecasts"]["status"] == "UNMEASURED"
    assert doc["register"]["status"] == "UNMEASURED"
    assert doc["pool"]["incremental_value"]["status"] == "UNMEASURED"
    assert doc["frozen_rules"]["online_adaptation"].startswith("NONE")


# --------------------------------------------------------------------------- the allocator
def _alloc_fixture(growths: list[float], m: float, c: float):
    deals = [{"epoch": (T0 - timedelta(days=1)).timestamp(), "type": 2, "profit": 1000.0}]
    bal = 1000.0
    log = []
    for i, g in enumerate(growths):
        t = T0 + timedelta(days=i, hours=1)
        log.append({"t": t.isoformat(), "expected_log_per_day": m,
                    "expected_cvar_per_day": c, "regime": {"bull": 1.0}, "mode": "normal",
                    "decision_id": f"d{i}"})
        pnl = bal * (math.exp(g) - 1.0)
        deals.append({"epoch": (t + timedelta(hours=12)).timestamp(), "type": 0,
                      "profit": pnl, "comm": 0.0, "swap": 0.0, "fee": 0.0})
        bal += pnl
    quotes = {"deals": deals, "at": (T0 + timedelta(days=len(growths) + 2)).isoformat(),
              "account": {"login": 1}}
    return log, quotes


def test_allocator_tail_coverage_counts_var_breaches(fs) -> None:
    m, c, alpha = 0.01, -0.02, 0.20
    sd = (m - c) * alpha / _N.pdf(_N.inv_cdf(alpha))
    var_a = m + _N.inv_cdf(alpha) * sd
    growths = [var_a - 0.01, var_a - 0.02] + [m + 0.001 * k for k in range(8)]   # 2 of 10
    log, quotes = _alloc_fixture(growths, m, c)
    doc = fs.score_allocator(log, fs.account_path(quotes), T0 + timedelta(days=30))
    assert doc["status"] == "MEASURED" and doc["days"] == 10
    dist = doc["overall"]["distribution"]
    assert dist["tail_coverage"]["breaches"] == 2
    assert dist["tail_coverage"]["observed_breach_rate"] == pytest.approx(0.2)
    assert doc["overall"]["signed_error"] == pytest.approx(sum(growths) / 10 - m, abs=1e-6)
    sev = dist["tail_severity"]
    assert sev["mean_realised_in_breach"] == pytest.approx(var_a - 0.015, abs=1e-6)
    assert doc["prob_annual_loss"]["status"] == "UNMEASURED"


def test_allocator_perfectly_calibrated_world_reads_uniform(fs) -> None:
    m, c = 0.0, -0.05
    alpha = 0.2
    sd = (m - c) * alpha / _N.pdf(_N.inv_cdf(alpha))
    n = 100
    growths = [m + sd * _N.inv_cdf((i + 0.5) / n) for i in range(n)]
    random.Random(7).shuffle(growths)
    log, quotes = _alloc_fixture(growths, m, c)
    doc = fs.score_allocator(log, fs.account_path(quotes), T0 + timedelta(days=200))
    dist = doc["overall"]["distribution"]
    assert dist["tail_coverage"]["observed_breach_rate"] == pytest.approx(0.2, abs=0.011)
    assert dist["pit"]["mean"] == pytest.approx(0.5, abs=0.01)
    assert dist["pit"]["variance"] == pytest.approx(1 / 12, rel=0.05)


def test_allocator_only_last_pass_per_day_and_pending_counted(fs) -> None:
    log, quotes = _alloc_fixture([0.01, 0.02], 0.01, -0.01)
    extra = dict(log[0]) | {"t": (T0 + timedelta(hours=2)).isoformat()}
    doc = fs.score_allocator([*log, extra], fs.account_path(quotes), T0 + timedelta(days=1.5))
    assert doc["passes"] == 3 and doc["days"] == 2 and doc["pending"] == 1


# --------------------------------------------------------------------------- the pool
def _events(n: int, models: dict[str, callable], seed: int = 1):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        y = rng.gauss(0, 1)
        at = T0 + timedelta(hours=2 * i)
        for name, fn in models.items():
            rows.append(_row(name, "XAUUSD.asia/r", "DISTRIBUTION", _gauss_q(fn(y, rng), 0.3),
                             at, y))
    return rows


def _resolved(fs, rows):
    _, resolved = fs.score_register(rows, fs.OutcomeBook([]), fs.RegimeTimeline([]), NOW)
    return resolved


def test_incremental_value_informative_positive_noise_negative(fs) -> None:
    rows = _events(80, {"inf": lambda y, r: y + r.gauss(0, 0.2),
                        "noise": lambda y, r: r.gauss(0, 1)})
    iv = fs.incremental_value(_resolved(fs, rows))
    assert iv["status"] == "MEASURED" and iv["events_scored"] == 80
    assert iv["by_source"]["inf"]["mean_delta"] > 0.1
    assert iv["by_source"]["noise"]["mean_delta"] < 0


def test_incremental_value_of_a_duplicate_is_about_zero(fs) -> None:
    def inf(y, r):
        return y + 0.25 * math.sin(7 * y)
    rows = _events(80, {"inf": inf, "twin": inf, "noise": lambda y, r: r.gauss(0, 1)})
    iv = fs.incremental_value(_resolved(fs, rows))
    ref = fs.incremental_value(_resolved(fs, _events(80, {
        "inf": inf, "noise": lambda y, r: r.gauss(0, 1)})))
    informative = ref["by_source"]["inf"]["mean_delta"]
    assert informative > 0.1
    # A copy adds nothing: with its twin present, removing either costs ~0.
    assert abs(iv["by_source"]["twin"]["mean_delta"]) < 0.1 * informative
    assert abs(iv["by_source"]["inf"]["mean_delta"]) < 0.1 * informative


def test_pool_is_idempotent_and_carries_lineage(fs) -> None:
    at = T0
    rows = [_row("a", "S/r", "DISTRIBUTION", _gauss_q(0.1, 0.2), at),
            _row("b", "S/r", "DISTRIBUTION", _gauss_q(0.3, 0.4), at,
                 model_version="v7")]
    once = fs.pool_beliefs(rows)
    twice = fs.pool_beliefs(rows + [dict(r) for r in rows])
    assert once["mean"] == twice["mean"] and once["variance"] == twice["variance"]
    assert twice["duplicates_ignored"] == 2
    assert once["pool_fingerprint"] == twice["pool_fingerprint"]
    # the same belief re-published an hour later (same inputs) is the same evidence
    later = dict(rows[0]) | {"at": (at + timedelta(hours=1)).isoformat()}
    assert fs.pool_beliefs([*rows, later])["mean"] == once["mean"]
    lin = {x["model_id"]: x for x in once["lineage"]}
    assert lin["b"]["model_version"] == "v7" and lin["a"]["training_cutoff"]
    assert sum(x["weight"] for x in once["lineage"]) == pytest.approx(1.0)


def test_pool_disagreement_shrinks_confidence_and_roles_are_enforced(fs) -> None:
    agree = fs.pool_beliefs([_row("a", "S/r", "DISTRIBUTION", _gauss_q(0.0, 0.1), T0),
                             _row("b", "S/r", "DISTRIBUTION", _gauss_q(0.0, 0.1), T0)])
    clash = fs.pool_beliefs([_row("a", "S/r", "DISTRIBUTION", _gauss_q(-1.0, 0.1), T0),
                             _row("b", "S/r", "DISTRIBUTION", _gauss_q(1.0, 0.1), T0)])
    assert clash["confidence"] < agree["confidence"] and clash["inflation"] > 1
    vol = _row("v", "S/r", "DISTRIBUTION", _gauss_q(5.0, 0.1), T0, family="garch_vol")
    p = fs.pool_beliefs([_row("a", "S/r", "DISTRIBUTION", _gauss_q(0.0, 0.1), T0), vol])
    assert p["mean"] == pytest.approx(0.0, abs=1e-9)
    assert any(x["model_id"] == "v" for x in p["excluded"])


def test_pool_log_append_is_idempotent(fs, tmp_path) -> None:
    pools = [fs.pool_beliefs([_row("a", "S/r", "DISTRIBUTION", _gauss_q(0.1, 0.2), T0)])]
    log = tmp_path / "pool.jsonl"
    assert fs.append_pool_log(pools, log) == 1
    assert fs.append_pool_log(pools, log) == 0


def test_cli_writes_the_report_atomically(fs, tmp_path, monkeypatch) -> None:
    rows = _events(30, {"inf": lambda y, r: y, "noise": lambda y, r: r.gauss(0, 1)})
    live = _row("inf", "XAUUSD.asia/r", "DISTRIBUTION", _gauss_q(0.0, 0.3),
                datetime.now(UTC) - timedelta(minutes=5))
    reg = tmp_path / "reg.jsonl"
    reg.write_text("\n".join(json.dumps(r) for r in [*rows, live]) + "\n", "utf-8")
    for name, val in {"REGISTER": reg, "FORECAST_LOG": tmp_path / "none.jsonl",
                      "OUTCOMES": tmp_path / "none2.jsonl", "QUOTES": tmp_path / "q.json",
                      "TRIGGER_STATE": tmp_path / "t.json",
                      "POOL_LOG": tmp_path / "pool.jsonl"}.items():
        monkeypatch.setattr(fs, name, val)
    out = tmp_path / "FORECAST_SCORES.json"
    assert fs.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["register"]["scored"] == 60
    assert doc["pool"]["live_count"] == 1 and doc["pool"]["appended_to_log"] == 1
    assert doc["pool"]["incremental_value"]["by_source"]["inf"]["mean_delta"] > 0
    assert not list(tmp_path.glob(".FORECAST_SCORES.json.*.tmp"))


def test_combine_a_twin_does_not_double_its_pull_on_the_mean(fs) -> None:
    mr = fs._roles

    def est(mid: str, mean: float):
        return mr.Estimate(model_id=mid, family="bayesian_edge", subject="S", horizon_s=3600.0,
                           role="DIRECTION_MEAN", mean=mean, variance=0.01,
                           inputs_as_of=T0.isoformat())
    rho = {frozenset({"a", "a2"}): 1.0, frozenset({"a", "c"}): 0.0,
           frozenset({"a2", "c"}): 0.0}
    twins = mr.combine([est("a", 1.0), est("a2", 1.0), est("c", 0.0)], measured_rho=rho)
    single = mr.combine([est("a", 1.0), est("c", 0.0)], measured_rho=rho)
    assert twins.mean == pytest.approx(single.mean) == pytest.approx(0.5)
    assert twins.n_effective == pytest.approx(2.0)
